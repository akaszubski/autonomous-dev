"""Unit tests for ComplexityAssessor._assess_genai() hybrid path.

Tests cover the GenAI hybrid path being added to complexity_assessor.py:
- GenAI available/unavailable paths
- Feature flag (GENAI_COMPLEXITY env var)
- Successful GenAI responses mapped to ComplexityAssessment
- Fallback to heuristic when GenAI returns None or raises
- Return type always ComplexityAssessment with all 5 fields

TDD RED PHASE: These tests will FAIL until _assess_genai() is implemented.

Related:
    - complexity_assessor.py: Module under test
    - genai_utils.py: GenAIAnalyzer and parse_classification_response source
"""

import os
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ============================================================================
# Import path setup
# ============================================================================

# Add lib and hooks dirs to path
_WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
_LIB_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "hooks"

sys.path.insert(0, str(_LIB_PATH))
sys.path.insert(0, str(_HOOKS_PATH))

try:
    from complexity_assessor import ComplexityAssessor, ComplexityLevel, ComplexityAssessment
except ImportError as exc:
    pytest.skip(
        f"complexity_assessor.py not importable: {exc}",
        allow_module_level=True,
    )


# ============================================================================
# Helpers
# ============================================================================

def _make_mock_analyzer(response: Optional[str]) -> MagicMock:
    """Return a mock GenAIAnalyzer whose .analyze() returns `response`."""
    mock = MagicMock()
    mock.analyze.return_value = response
    return mock


def _assert_valid_assessment(result):
    """Assert that result is a valid ComplexityAssessment with all 5 fields."""
    assert isinstance(result, ComplexityAssessment), (
        f"Expected ComplexityAssessment, got {type(result)}"
    )
    assert isinstance(result.level, ComplexityLevel)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0, f"confidence out of range: {result.confidence}"
    assert isinstance(result.reasoning, str)
    assert len(result.reasoning) > 0, "reasoning must not be empty"
    assert isinstance(result.agent_count, int)
    assert result.agent_count in (3, 6, 8), f"unexpected agent_count: {result.agent_count}"
    assert isinstance(result.estimated_time, int)
    assert result.estimated_time in (8, 15, 25), f"unexpected estimated_time: {result.estimated_time}"


# ============================================================================
# Test Class
# ============================================================================

class TestAssessGenAIPath:
    """Tests for the _assess_genai() hybrid path on ComplexityAssessor."""

    # ------------------------------------------------------------------
    # Test 1: GenAI returns "SIMPLE"
    # ------------------------------------------------------------------

    def test_genai_returns_simple_maps_to_simple_assessment(self):
        """When GenAI responds SIMPLE, _assess_genai returns SIMPLE ComplexityAssessment.

        Arrange: GenAI analyzer returns "SIMPLE", parse_classification_response returns "SIMPLE"
        Act: Call _assess_genai with some feature description
        Assert: level=SIMPLE, agent_count=3, confidence=0.9, reasoning contains "GenAI"
        """
        mock_analyzer = _make_mock_analyzer("SIMPLE")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="SIMPLE"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Fix typo in README")

        assert result is not None, "_assess_genai should return an assessment, not None"
        assert result.level == ComplexityLevel.SIMPLE
        assert result.agent_count == 3
        assert result.estimated_time == 8
        assert result.confidence == 0.9
        assert "GenAI" in result.reasoning or "genai" in result.reasoning.lower(), (
            f"reasoning should mention GenAI, got: {result.reasoning!r}"
        )

    # ------------------------------------------------------------------
    # Test 2: GenAI returns "COMPLEX"
    # ------------------------------------------------------------------

    def test_genai_returns_complex_maps_to_complex_assessment(self):
        """When GenAI responds COMPLEX, _assess_genai returns COMPLEX ComplexityAssessment.

        Arrange: GenAI analyzer returns "COMPLEX", parse returns "COMPLEX"
        Act: Call _assess_genai with a complex feature description
        Assert: level=COMPLEX, agent_count=8
        """
        mock_analyzer = _make_mock_analyzer("COMPLEX")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="COMPLEX"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai(
                "Implement OAuth2 with JWT refresh token rotation"
            )

        assert result is not None
        assert result.level == ComplexityLevel.COMPLEX
        assert result.agent_count == 8
        assert result.estimated_time == 25

    # ------------------------------------------------------------------
    # Test 3: GenAI returns "STANDARD"
    # ------------------------------------------------------------------

    def test_genai_returns_standard_maps_to_standard_assessment(self):
        """When GenAI responds STANDARD, _assess_genai returns STANDARD ComplexityAssessment."""
        mock_analyzer = _make_mock_analyzer("STANDARD")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="STANDARD"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Add pagination to user list")

        assert result is not None
        assert result.level == ComplexityLevel.STANDARD
        assert result.agent_count == 6
        assert result.estimated_time == 15

    # ------------------------------------------------------------------
    # Test 4: GenAI returns None (no API key)
    # ------------------------------------------------------------------

    def test_genai_returns_none_triggers_heuristic_fallback(self):
        """When GenAI returns None (missing API key), _assess_genai returns None for fallback.

        The caller (assess()) should then use the heuristic path. _assess_genai
        itself returns None to signal fallback.

        Arrange: analyze() returns None (simulates missing ANTHROPIC_API_KEY)
        Act: Call _assess_genai
        Assert: Returns None (triggers heuristic in caller)
        """
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Add user endpoint")

        assert result is None, (
            "_assess_genai should return None when GenAI returns None (triggers fallback)"
        )

    # ------------------------------------------------------------------
    # Test 5: assess() with GenAI returning None falls back to heuristic
    # ------------------------------------------------------------------

    def test_assess_falls_back_to_heuristic_when_genai_returns_none(self):
        """Full assess() path: GenAI returns None → heuristic runs → valid ComplexityAssessment.

        This tests the full pipeline, not just _assess_genai.
        Even when GenAI fails, the result is always a valid ComplexityAssessment.
        """
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Fix typo in README")

        _assert_valid_assessment(result)
        # Heuristic should still classify "typo" as SIMPLE
        assert result.level == ComplexityLevel.SIMPLE

    # ------------------------------------------------------------------
    # Test 6: GenAI raises an exception
    # ------------------------------------------------------------------

    def test_genai_exception_does_not_crash_assess(self):
        """When GenAI raises an exception, assess() does not crash and returns heuristic result.

        Arrange: GenAIAnalyzer.analyze() raises RuntimeError
        Act: Call assess()
        Assert: No exception raised, valid ComplexityAssessment returned
        """
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("Connection timeout")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Implement authentication system")

        _assert_valid_assessment(result)

    # ------------------------------------------------------------------
    # Test 7: GENAI_COMPLEXITY=false → GenAI never called
    # ------------------------------------------------------------------

    def test_genai_complexity_false_disables_genai_path(self):
        """When GENAI_COMPLEXITY=false, GenAI is never called and heuristic runs.

        Arrange: GENAI_COMPLEXITY=false in env
        Act: Call assess()
        Assert: GenAIAnalyzer.analyze() NOT called, valid heuristic result returned
        """
        mock_analyzer = _make_mock_analyzer("COMPLEX")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer) as mock_cls,
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "false"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Fix typo")

        # GenAIAnalyzer should not be instantiated or called
        mock_analyzer.analyze.assert_not_called()
        _assert_valid_assessment(result)

    def test_genai_complexity_env_var_default_is_true(self):
        """When GENAI_COMPLEXITY is not set, it defaults to enabled (true).

        Arrange: Remove GENAI_COMPLEXITY from env, GenAI returns "SIMPLE"
        Act: Call _assess_genai
        Assert: GenAI IS called (not bypassed by missing flag)
        """
        mock_analyzer = _make_mock_analyzer("SIMPLE")
        env_without_flag = {k: v for k, v in os.environ.items() if k != "GENAI_COMPLEXITY"}

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="SIMPLE"),
            patch.dict(os.environ, env_without_flag, clear=True),
        ):
            result = ComplexityAssessor._assess_genai("Fix typo")

        # GenAI should have been called (default is enabled)
        mock_analyzer.analyze.assert_called_once()

    # ------------------------------------------------------------------
    # Test 8: GenAI returns unrecognized text → parse returns None → heuristic
    # ------------------------------------------------------------------

    def test_genai_unrecognized_response_falls_back_to_heuristic(self):
        """When GenAI returns text not in [SIMPLE, STANDARD, COMPLEX], fallback to heuristic.

        Arrange: analyze() returns "I'm not sure", parse returns None
        Act: Call _assess_genai
        Assert: Returns None (signals heuristic fallback)
        """
        mock_analyzer = _make_mock_analyzer("I'm not sure about the complexity here.")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch(
                "complexity_assessor.parse_classification_response",
                return_value=None,
            ),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Do something")

        assert result is None, (
            "_assess_genai should return None when parse_classification_response returns None"
        )

    def test_assess_with_unrecognized_genai_response_still_returns_valid_result(self):
        """Full assess() with unrecognized GenAI response returns valid heuristic result."""
        mock_analyzer = _make_mock_analyzer("UNKNOWN_LABEL")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch(
                "complexity_assessor.parse_classification_response",
                return_value=None,
            ),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Fix typo in docs")

        _assert_valid_assessment(result)

    # ------------------------------------------------------------------
    # Test 9: _GENAI_AVAILABLE=False → heuristic runs directly
    # ------------------------------------------------------------------

    def test_genai_not_available_module_flag_bypasses_genai(self):
        """When _GENAI_AVAILABLE is False, GenAI is never attempted.

        This simulates the anthropic SDK not being installed.

        Arrange: _GENAI_AVAILABLE=False
        Act: Call _assess_genai
        Assert: Returns None immediately (no GenAIAnalyzer instantiation)
        """
        with (
            patch("complexity_assessor._GENAI_AVAILABLE", False),
            patch("complexity_assessor.GenAIAnalyzer") as mock_cls,
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Fix typo")

        assert result is None, (
            "_assess_genai should return None when _GENAI_AVAILABLE is False"
        )
        mock_cls.assert_not_called()

    def test_genai_not_available_assess_still_returns_heuristic(self):
        """When _GENAI_AVAILABLE=False, assess() falls back to heuristic and returns valid result."""
        with (
            patch("complexity_assessor._GENAI_AVAILABLE", False),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Implement OAuth2 authentication")

        _assert_valid_assessment(result)
        # Heuristic should detect "oauth" and "auth" as COMPLEX
        assert result.level == ComplexityLevel.COMPLEX

    # ------------------------------------------------------------------
    # Test 10: GenAIAnalyzer called with correct parameters
    # ------------------------------------------------------------------

    def test_genai_analyzer_created_with_correct_parameters(self):
        """GenAIAnalyzer is instantiated with max_tokens=150 and timeout=5.

        Arrange: Patch GenAIAnalyzer to capture constructor call
        Act: Call _assess_genai
        Assert: GenAIAnalyzer(max_tokens=150, timeout=5) was called
        """
        mock_instance = _make_mock_analyzer("SIMPLE")
        mock_instance_2 = MagicMock()
        mock_instance_2.analyze.return_value = "SIMPLE"

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch(
                "complexity_assessor.GenAIAnalyzer",
                return_value=mock_instance,
            ) as mock_cls,
            patch("complexity_assessor.parse_classification_response", return_value="SIMPLE"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            ComplexityAssessor._assess_genai("Fix typo")

        # Verify GenAIAnalyzer was called with expected kwargs
        call_kwargs = mock_cls.call_args
        assert call_kwargs is not None, "GenAIAnalyzer should have been instantiated"
        # Check max_tokens and timeout parameters
        kwargs = call_kwargs[1] if call_kwargs[1] else {}
        args = call_kwargs[0] if call_kwargs[0] else ()
        assert 150 in args or kwargs.get("max_tokens") == 150, (
            f"GenAIAnalyzer should be created with max_tokens=150, got args={args} kwargs={kwargs}"
        )
        assert 5 in args or kwargs.get("timeout") == 5, (
            f"GenAIAnalyzer should be created with timeout=5, got args={args} kwargs={kwargs}"
        )

    # ------------------------------------------------------------------
    # Test 11: analyze() called with correct prompt and feature_description
    # ------------------------------------------------------------------

    def test_genai_analyze_called_with_prompt_and_feature_description(self):
        """analyze() is called with COMPLEXITY_CLASSIFICATION_PROMPT and feature_description kwarg.

        Arrange: Capture analyze() call arguments
        Act: Call _assess_genai("some feature text")
        Assert: analyze(COMPLEXITY_CLASSIFICATION_PROMPT, feature_description="some feature text")
        """
        mock_analyzer = _make_mock_analyzer("SIMPLE")
        mock_prompt = "Classify as SIMPLE/STANDARD/COMPLEX: {feature_description}"

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.COMPLEXITY_CLASSIFICATION_PROMPT", mock_prompt),
            patch("complexity_assessor.parse_classification_response", return_value="SIMPLE"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            ComplexityAssessor._assess_genai("some feature text")

        mock_analyzer.analyze.assert_called_once_with(
            mock_prompt,
            feature_description="some feature text",
        )

    # ------------------------------------------------------------------
    # Test 12: parse_classification_response called with correct labels
    # ------------------------------------------------------------------

    def test_parse_classification_called_with_correct_labels(self):
        """parse_classification_response is called with ["SIMPLE", "STANDARD", "COMPLEX"]."""
        mock_analyzer = _make_mock_analyzer("COMPLEX response text")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch(
                "complexity_assessor.parse_classification_response",
                return_value="COMPLEX",
            ) as mock_parse,
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            ComplexityAssessor._assess_genai("implement authentication")

        mock_parse.assert_called_once_with(
            "COMPLEX response text",
            ["SIMPLE", "STANDARD", "COMPLEX"],
        )

    # ------------------------------------------------------------------
    # Test 13: Return type is always ComplexityAssessment (all 5 fields)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("genai_label,expected_level,expected_agents,expected_time", [
        ("SIMPLE", ComplexityLevel.SIMPLE, 3, 8),
        ("STANDARD", ComplexityLevel.STANDARD, 6, 15),
        ("COMPLEX", ComplexityLevel.COMPLEX, 8, 25),
    ])
    def test_return_type_always_has_all_five_fields(
        self,
        genai_label: str,
        expected_level: ComplexityLevel,
        expected_agents: int,
        expected_time: int,
    ):
        """For each GenAI label, verify all 5 ComplexityAssessment fields are populated.

        Fields: level, confidence, reasoning, agent_count, estimated_time
        """
        mock_analyzer = _make_mock_analyzer(genai_label)

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch(
                "complexity_assessor.parse_classification_response",
                return_value=genai_label,
            ),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("test feature")

        assert result is not None
        _assert_valid_assessment(result)
        assert result.level == expected_level
        assert result.agent_count == expected_agents
        assert result.estimated_time == expected_time

    # ------------------------------------------------------------------
    # Test 14: assess() always returns ComplexityAssessment (never None)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("description", [
        "Fix typo",
        "Add OAuth2 authentication",
        "Add pagination",
        "",
        None,
        "x" * 10001,
    ])
    def test_assess_always_returns_complex_assessment_not_none(self, description):
        """assess() NEVER returns None regardless of GenAI availability/response.

        Even when GenAI fails completely, heuristic fallback ensures a valid result.
        """
        mock_analyzer = _make_mock_analyzer(None)  # GenAI returns nothing

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess(description)

        assert result is not None, f"assess() returned None for input: {description!r}"
        assert isinstance(result, ComplexityAssessment)
        # All 5 fields must be present and valid
        assert hasattr(result, "level")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reasoning")
        assert hasattr(result, "agent_count")
        assert hasattr(result, "estimated_time")


class TestAssessGenAIEdgeCases:
    """Edge case tests for the GenAI hybrid path."""

    def test_genai_exception_from_initializer_falls_back(self):
        """GenAIAnalyzer constructor raising an exception triggers fallback."""
        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch(
                "complexity_assessor.GenAIAnalyzer",
                side_effect=ImportError("anthropic not installed"),
            ),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Fix typo in README")

        _assert_valid_assessment(result)

    def test_genai_assess_genai_returns_none_on_exception(self):
        """_assess_genai returns None when an exception occurs inside it."""
        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch(
                "complexity_assessor.GenAIAnalyzer",
                side_effect=RuntimeError("SDK init failed"),
            ),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Fix typo")

        assert result is None

    def test_genai_complexity_env_false_string_variants(self):
        """GENAI_COMPLEXITY=false (case insensitive) disables GenAI.

        The 'false' check should be case-insensitive.
        """
        mock_analyzer = _make_mock_analyzer("COMPLEX")

        for false_value in ("false", "FALSE", "False", "0", "no"):
            with (
                patch("complexity_assessor._GENAI_AVAILABLE", True),
                patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
                patch.dict(os.environ, {"GENAI_COMPLEXITY": false_value}, clear=False),
            ):
                # Should not raise, should use heuristic
                result = ComplexityAssessor.assess("Fix typo")

            assert result is not None, f"assess() returned None with GENAI_COMPLEXITY={false_value}"

    def test_genai_reasoning_mentions_classification_source(self):
        """When GenAI classification succeeds, reasoning explains the GenAI source."""
        mock_analyzer = _make_mock_analyzer("SIMPLE")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="SIMPLE"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Fix typo in README")

        assert result is not None
        # Reasoning should indicate GenAI was used (not just heuristic)
        reasoning_lower = result.reasoning.lower()
        assert any(
            keyword in reasoning_lower
            for keyword in ("genai", "ai", "llm", "classification", "classified")
        ), f"reasoning should mention GenAI classification, got: {result.reasoning!r}"

    def test_genai_confidence_for_successful_genai_response(self):
        """GenAI-classified results have reasonable confidence (0.9 per spec)."""
        mock_analyzer = _make_mock_analyzer("COMPLEX")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="COMPLEX"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Implement JWT auth")

        assert result is not None
        assert result.confidence == 0.9, (
            f"GenAI-classified results should have confidence=0.9, got {result.confidence}"
        )


class TestAssessGenAIModuleFlags:
    """Tests for module-level _GENAI_AVAILABLE flag behavior."""

    def test_genai_available_false_at_module_level(self):
        """When module-level _GENAI_AVAILABLE=False, _assess_genai is bypassed entirely."""
        mock_analyzer = MagicMock()

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", False),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer) as mock_cls,
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Any text")

        assert result is None
        mock_cls.assert_not_called()
        mock_analyzer.analyze.assert_not_called()

    def test_genai_available_true_but_flag_false(self):
        """_GENAI_AVAILABLE=True but GENAI_COMPLEXITY=false → GenAI skipped."""
        mock_analyzer = _make_mock_analyzer("COMPLEX")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "false"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Fix typo")

        assert result is None
        mock_analyzer.analyze.assert_not_called()

    def test_both_flags_true_genai_runs(self):
        """Both _GENAI_AVAILABLE=True and GENAI_COMPLEXITY=true → GenAI runs."""
        mock_analyzer = _make_mock_analyzer("STANDARD")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="STANDARD"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor._assess_genai("Add pagination feature")

        mock_analyzer.analyze.assert_called_once()
        assert result is not None
        assert result.level == ComplexityLevel.STANDARD


# ============================================================================
# Integration tests: assess() with GenAI hybrid path
# ============================================================================

class TestAssessWithGenAIIntegration:
    """Integration tests verifying the full assess() → GenAI → fallback chain."""

    def test_assess_uses_genai_result_when_available(self):
        """assess() uses GenAI result instead of heuristic when GenAI succeeds.

        Scenario: "Fix typo in JWT auth" would be COMPLEX by heuristics (jwt, auth)
        but GenAI could classify it as SIMPLE. We verify GenAI result wins.
        """
        mock_analyzer = _make_mock_analyzer("SIMPLE")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="SIMPLE"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Fix typo in JWT auth error message")

        # GenAI says SIMPLE → should override heuristic COMPLEX
        assert result.level == ComplexityLevel.SIMPLE
        assert result.agent_count == 3

    def test_assess_heuristic_runs_when_genai_disabled(self):
        """assess() uses heuristic when _GENAI_AVAILABLE=False."""
        with (
            patch("complexity_assessor._GENAI_AVAILABLE", False),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Implement OAuth2 authentication")

        # Heuristic should detect auth/oauth2 as COMPLEX
        assert result.level == ComplexityLevel.COMPLEX
        assert result.agent_count == 8

    def test_assess_returns_genai_result_with_all_fields(self):
        """Full assess() with GenAI success returns ComplexityAssessment with all fields."""
        mock_analyzer = _make_mock_analyzer("COMPLEX")

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="COMPLEX"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess("Build authentication system")

        _assert_valid_assessment(result)
        assert result.level == ComplexityLevel.COMPLEX
        assert result.agent_count == 8
        assert result.estimated_time == 25

    def test_assess_github_issue_with_genai(self):
        """assess() with github_issue parameter works correctly with GenAI path."""
        mock_analyzer = _make_mock_analyzer("COMPLEX")
        issue = {
            "title": "Add JWT authentication",
            "body": "Implement JWT-based auth with refresh tokens"
        }

        with (
            patch("complexity_assessor._GENAI_AVAILABLE", True),
            patch("complexity_assessor.GenAIAnalyzer", return_value=mock_analyzer),
            patch("complexity_assessor.parse_classification_response", return_value="COMPLEX"),
            patch.dict(os.environ, {"GENAI_COMPLEXITY": "true"}, clear=False),
        ):
            result = ComplexityAssessor.assess(
                issue["title"],
                github_issue=issue,
            )

        _assert_valid_assessment(result)


# ============================================================================
# Checkpoint integration
# ============================================================================

if __name__ == "__main__":
    from pathlib import Path
    import sys

    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                "test-master",
                "Tests complete - 22 GenAI hybrid path tests created for complexity_assessor",
            )
            print("Checkpoint saved")
        except ImportError:
            print("Checkpoint skipped (user project)")
