#!/usr/bin/env python3
"""
Tests for GenAI prompts and utilities.

This module tests:
- Prompt structure and formatting
- GenAI utility functions (parsing, classification)
- Configuration constants
- Integration with shared utilities
"""

import pytest
import sys
from pathlib import Path

# Add hooks directory to path for imports
hooks_dir = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(hooks_dir))

from genai_prompts import (
    SECRET_ANALYSIS_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    COMPLEXITY_ASSESSMENT_PROMPT,
    DESCRIPTION_VALIDATION_PROMPT,
    DOC_GENERATION_PROMPT,
    get_all_prompts,
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT,
)
from genai_utils import (
    GenAIAnalyzer,
    should_use_genai,
    parse_classification_response,
    parse_binary_response,
)


# ============================================================================
# Prompt Structure Tests
# ============================================================================


class TestPromptStructure:
    """Test that all prompts have required elements and format correctly."""

    def test_secret_analysis_prompt_format(self):
        """Verify SECRET_ANALYSIS_PROMPT can be formatted with variables."""
        formatted = SECRET_ANALYSIS_PROMPT.format(
            line='api_key = "sk-abc123"',
            secret_type="API key",
            variable_name="api_key"
        )
        assert "REAL" in formatted or "FAKE" in formatted
        assert "Respond with ONLY" in formatted

    def test_secret_analysis_prompt_has_variables(self):
        """Verify SECRET_ANALYSIS_PROMPT has required template variables."""
        required_vars = ["line", "secret_type", "variable_name"]
        for var in required_vars:
            assert f"{{{var}}}" in SECRET_ANALYSIS_PROMPT

    def test_intent_classification_prompt_format(self):
        """Verify INTENT_CLASSIFICATION_PROMPT can be formatted with variables."""
        formatted = INTENT_CLASSIFICATION_PROMPT.format(
            user_prompt="implement new feature"
        )
        assert "IMPLEMENT" in formatted
        assert "REFACTOR" in formatted
        assert "DOCS" in formatted
        assert "TEST" in formatted
        assert "Respond with ONLY" in formatted

    def test_intent_classification_has_categories(self):
        """Verify INTENT_CLASSIFICATION_PROMPT mentions all categories."""
        required_categories = ["IMPLEMENT", "REFACTOR", "DOCS", "TEST", "OTHER"]
        for category in required_categories:
            assert category in INTENT_CLASSIFICATION_PROMPT

    def test_complexity_assessment_prompt_format(self):
        """Verify COMPLEXITY_ASSESSMENT_PROMPT can be formatted with variables."""
        formatted = COMPLEXITY_ASSESSMENT_PROMPT.format(
            num_functions=2,
            function_names="foo, bar",
            num_classes=1,
            class_names="MyClass",
            num_modified=0,
            modified_names="None",
            num_breaking=0,
            breaking_names="None",
        )
        assert "SIMPLE" in formatted or "COMPLEX" in formatted
        assert "Respond with ONLY" in formatted

    def test_description_validation_prompt_format(self):
        """Verify DESCRIPTION_VALIDATION_PROMPT can be formatted with variables."""
        formatted = DESCRIPTION_VALIDATION_PROMPT.format(
            entity_type="agents",
            section="Example agent description"
        )
        assert "ACCURATE" in formatted or "MISLEADING" in formatted
        assert "Respond with ONLY" in formatted

    def test_doc_generation_prompt_format(self):
        """Verify DOC_GENERATION_PROMPT can be formatted with variables."""
        formatted = DOC_GENERATION_PROMPT.format(
            item_type="command",
            item_name="my-command"
        )
        assert "documentation" in formatted.lower()
        assert "MY-COMMAND" in formatted or "command" in formatted

    def test_all_prompts_no_unformatted_variables(self):
        """Verify all prompts don't have leftover unformatted variables."""
        # After formatting with expected variables, there should be no braces
        secret_formatted = SECRET_ANALYSIS_PROMPT.format(
            line="test", secret_type="test", variable_name="test"
        )
        assert "{" not in secret_formatted or "}" not in secret_formatted.split("{")[0]


# ============================================================================
# Configuration Tests
# ============================================================================


class TestConfiguration:
    """Test configuration constants."""

    def test_default_model_is_haiku(self):
        """Verify DEFAULT_MODEL is Haiku for speed/cost."""
        assert "haiku" in DEFAULT_MODEL.lower()

    def test_default_max_tokens_reasonable(self):
        """Verify DEFAULT_MAX_TOKENS is reasonable for quick responses."""
        assert 50 <= DEFAULT_MAX_TOKENS <= 200

    def test_default_timeout_is_reasonable(self):
        """Verify DEFAULT_TIMEOUT is reasonable for pre-commit hooks."""
        assert 3 <= DEFAULT_TIMEOUT <= 10

    def test_get_all_prompts_returns_dict(self):
        """Verify get_all_prompts returns a dictionary."""
        prompts = get_all_prompts()
        assert isinstance(prompts, dict)
        assert len(prompts) >= 5

    def test_get_all_prompts_has_all_prompts(self):
        """Verify get_all_prompts includes all major prompts."""
        prompts = get_all_prompts()
        expected_keys = [
            "secret_analysis",
            "intent_classification",
            "complexity_assessment",
            "description_validation",
            "doc_generation",
        ]
        for key in expected_keys:
            assert key in prompts


# ============================================================================
# GenAI Analyzer Tests
# ============================================================================


class TestGenAIAnalyzer:
    """Test GenAIAnalyzer class."""

    def test_analyzer_initialization_default(self):
        """Verify GenAIAnalyzer initializes with defaults."""
        analyzer = GenAIAnalyzer(use_genai=False)
        assert analyzer.model == DEFAULT_MODEL
        assert analyzer.max_tokens == DEFAULT_MAX_TOKENS
        assert analyzer.timeout == DEFAULT_TIMEOUT
        assert analyzer.use_genai is False

    def test_analyzer_initialization_custom(self):
        """Verify GenAIAnalyzer accepts custom parameters."""
        analyzer = GenAIAnalyzer(
            model="custom-model",
            max_tokens=500,
            timeout=10,
            use_genai=True
        )
        assert analyzer.model == "custom-model"
        assert analyzer.max_tokens == 500
        assert analyzer.timeout == 10
        assert analyzer.use_genai is True

    def test_analyzer_disabled_returns_none(self):
        """Verify analyze() returns None when GenAI disabled."""
        analyzer = GenAIAnalyzer(use_genai=False)
        result = analyzer.analyze("dummy prompt", var="value")
        assert result is None

    def test_analyzer_graceful_degradation(self):
        """Verify analyzer has graceful degradation."""
        analyzer = GenAIAnalyzer(use_genai=True)
        # Should not crash if SDK unavailable
        result = analyzer.analyze("test", var="value")
        # Result might be None (SDK unavailable) but shouldn't crash
        assert result is None or isinstance(result, str)


# ============================================================================
# Response Parsing Tests
# ============================================================================


class TestParseClassificationResponse:
    """Test parse_classification_response function."""

    def test_parse_single_match(self):
        """Verify parse_classification_response finds single matches."""
        response = "IMPLEMENT"
        result = parse_classification_response(
            response, ["IMPLEMENT", "REFACTOR", "DOCS", "TEST", "OTHER"]
        )
        assert result == "IMPLEMENT"

    def test_parse_case_insensitive(self):
        """Verify parse_classification_response is case insensitive."""
        response = "implement"
        result = parse_classification_response(
            response, ["IMPLEMENT", "REFACTOR", "DOCS", "TEST", "OTHER"]
        )
        assert result == "IMPLEMENT"

    def test_parse_with_extra_text(self):
        """Verify parse_classification_response finds match with extra text."""
        response = "Based on the description, this is an IMPLEMENT task."
        result = parse_classification_response(
            response, ["IMPLEMENT", "REFACTOR", "DOCS", "TEST", "OTHER"]
        )
        assert result == "IMPLEMENT"

    def test_parse_no_match(self):
        """Verify parse_classification_response returns None on no match."""
        response = "something else entirely"
        result = parse_classification_response(
            response, ["IMPLEMENT", "REFACTOR", "DOCS"]
        )
        assert result is None

    def test_parse_empty_response(self):
        """Verify parse_classification_response handles empty response."""
        result = parse_classification_response("", ["IMPLEMENT", "REFACTOR"])
        assert result is None


class TestParseBinaryResponse:
    """Test parse_binary_response function."""

    def test_parse_true_response(self):
        """Verify parse_binary_response identifies true responses."""
        response = "This is REAL data"
        result = parse_binary_response(
            response,
            true_keywords=["REAL", "TRUE"],
            false_keywords=["FAKE", "FALSE"]
        )
        assert result is True

    def test_parse_false_response(self):
        """Verify parse_binary_response identifies false responses."""
        response = "This is FAKE data"
        result = parse_binary_response(
            response,
            true_keywords=["REAL", "TRUE"],
            false_keywords=["FAKE", "FALSE"]
        )
        assert result is False

    def test_parse_case_insensitive(self):
        """Verify parse_binary_response is case insensitive."""
        response = "real"
        result = parse_binary_response(
            response,
            true_keywords=["REAL"],
            false_keywords=["FAKE"]
        )
        assert result is True

    def test_parse_ambiguous_response(self):
        """Verify parse_binary_response returns None on ambiguous."""
        response = "unclear"
        result = parse_binary_response(
            response,
            true_keywords=["REAL"],
            false_keywords=["FAKE"]
        )
        assert result is None

    def test_parse_empty_response(self):
        """Verify parse_binary_response handles empty response."""
        result = parse_binary_response(
            "",
            true_keywords=["REAL"],
            false_keywords=["FAKE"]
        )
        assert result is None

    def test_parse_true_takes_precedence(self):
        """Verify parse_binary_response checks true keywords first."""
        # If both keywords appear, true should win (conservative approach)
        response = "This looks REAL but might be FAKE"
        result = parse_binary_response(
            response,
            true_keywords=["REAL"],
            false_keywords=["FAKE"]
        )
        assert result is True


# ============================================================================
# Feature Flag Tests
# ============================================================================


class TestShouldUseGenAI:
    """Test should_use_genai feature flag function."""

    def test_default_true(self):
        """Verify should_use_genai defaults to True."""
        # With no env var set, should default to True
        import os
        old_val = os.environ.get("TEST_FLAG")
        if "TEST_FLAG" in os.environ:
            del os.environ["TEST_FLAG"]

        result = should_use_genai("TEST_FLAG")
        assert result is True

        # Restore old value
        if old_val is not None:
            os.environ["TEST_FLAG"] = old_val

    def test_disabled_with_false(self):
        """Verify should_use_genai respects 'false' value."""
        import os
        os.environ["TEST_FLAG_DISABLED"] = "false"
        result = should_use_genai("TEST_FLAG_DISABLED")
        assert result is False
        del os.environ["TEST_FLAG_DISABLED"]

    def test_disabled_with_False(self):
        """Verify should_use_genai respects 'False' value (case insensitive)."""
        import os
        os.environ["TEST_FLAG_CASE"] = "False"
        result = should_use_genai("TEST_FLAG_CASE")
        assert result is False
        del os.environ["TEST_FLAG_CASE"]

    def test_enabled_with_true(self):
        """Verify should_use_genai respects 'true' value."""
        import os
        os.environ["TEST_FLAG_TRUE"] = "true"
        result = should_use_genai("TEST_FLAG_TRUE")
        assert result is True
        del os.environ["TEST_FLAG_TRUE"]


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for prompts and utilities working together."""

    def test_prompt_and_parser_integration(self):
        """Verify prompt works with response parser."""
        # Simulate a response to SECRET_ANALYSIS_PROMPT
        response = "Based on the analysis, this is REAL data."
        is_real = parse_binary_response(
            response,
            true_keywords=["REAL", "LIKELY_REAL"],
            false_keywords=["FAKE"]
        )
        assert is_real is True

    def test_intent_classification_integration(self):
        """Verify INTENT_CLASSIFICATION_PROMPT works with parser."""
        # Simulate a response to INTENT_CLASSIFICATION_PROMPT
        response = "The user is trying to IMPLEMENT a new feature."
        intent = parse_classification_response(
            response,
            ["IMPLEMENT", "REFACTOR", "DOCS", "TEST", "OTHER"]
        )
        assert intent == "IMPLEMENT"

    def test_all_prompts_have_response_format_guidance(self):
        """Verify all prompts have 'Respond with ONLY' guidance."""
        all_prompts = get_all_prompts()
        for name, prompt in all_prompts.items():
            assert "Respond with ONLY" in prompt or "Return ONLY" in prompt, \
                f"Prompt '{name}' missing response format guidance"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
