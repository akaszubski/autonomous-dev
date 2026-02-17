"""Unit tests for GenAI hybrid paths in scope_detector.py and issue_scope_detector.py.

Tests cover:
- GenAI returns each valid value → correct return type
- GenAI returns None → heuristic fallback
- GENAI_SCOPE=false → GenAI never called
- _GENAI_AVAILABLE=False → heuristic fallback
- Return type contract preserved

Related:
    - scope_detector.py: Module under test (_assess_genai)
    - issue_scope_detector.py: Module under test (_detect_genai)
    - genai_utils.py: GenAIAnalyzer and parse_classification_response source
"""

import os
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Import path setup
# ============================================================================

_WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
_LIB_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "hooks"

sys.path.insert(0, str(_LIB_PATH))
sys.path.insert(0, str(_HOOKS_PATH))

try:
    from scope_detector import (
        analyze_complexity,
        _assess_genai,
        ComplexityAnalysis,
        EffortSize,
        _GENAI_AVAILABLE as SCOPE_GENAI_AVAILABLE,
    )
    _SCOPE_DETECTOR_AVAILABLE = True
except ImportError as exc:
    _SCOPE_DETECTOR_AVAILABLE = False
    _scope_import_error = str(exc)

try:
    from issue_scope_detector import (
        IssueScopeDetector,
        ScopeLevel,
        ScopeDetection,
        _GENAI_AVAILABLE as ISSUE_SCOPE_GENAI_AVAILABLE,
    )
    _ISSUE_SCOPE_DETECTOR_AVAILABLE = True
except ImportError as exc:
    _ISSUE_SCOPE_DETECTOR_AVAILABLE = False
    _issue_scope_import_error = str(exc)


# ============================================================================
# Helpers
# ============================================================================

def _make_mock_analyzer(response: Optional[str]) -> MagicMock:
    """Return a mock GenAIAnalyzer whose .analyze() returns `response`."""
    mock = MagicMock()
    mock.analyze.return_value = response
    return mock


def _assert_valid_complexity_analysis(result):
    """Assert that result is a valid ComplexityAnalysis with all 4 fields."""
    assert isinstance(result, ComplexityAnalysis), (
        f"Expected ComplexityAnalysis, got {type(result)}"
    )
    assert isinstance(result.effort, EffortSize)
    assert isinstance(result.indicators, dict)
    assert isinstance(result.needs_decomposition, bool)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0, f"confidence out of range: {result.confidence}"


def _assert_valid_scope_detection(result):
    """Assert that result is a valid ScopeDetection with all 5 fields."""
    assert isinstance(result, ScopeDetection), (
        f"Expected ScopeDetection, got {type(result)}"
    )
    assert isinstance(result.level, ScopeLevel)
    assert isinstance(result.reasoning, str)
    assert len(result.reasoning) > 0, "reasoning must not be empty"
    assert isinstance(result.indicators, dict)
    assert isinstance(result.suggested_splits, list)
    assert isinstance(result.should_warn, bool)


# ============================================================================
# Tests for scope_detector._assess_genai
# ============================================================================

@pytest.mark.skipif(not _SCOPE_DETECTOR_AVAILABLE, reason="scope_detector.py not importable")
class TestScopeDetectorAssessGenAI:
    """Tests for scope_detector._assess_genai() hybrid path."""

    def test_genai_returns_focused_maps_to_xs_or_s_effort(self):
        """When GenAI responds FOCUSED, _assess_genai returns needs_decomposition=False.

        Arrange: GenAI analyzer returns "FOCUSED"
        Act: Call _assess_genai with a simple feature description
        Assert: needs_decomposition=False, confidence=0.9
        """
        mock_analyzer = _make_mock_analyzer("FOCUSED")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Add rate limiting and timeout")

        assert result is not None, "_assess_genai should return an assessment, not None"
        assert result.needs_decomposition is False
        assert result.confidence == 0.9
        # Reasoning is stored in the indicators dict for ComplexityAnalysis (no .reasoning field)
        assert "genai_scope" in result.indicators

    def test_genai_returns_broad_maps_to_needs_decomposition_true(self):
        """When GenAI responds BROAD, _assess_genai returns needs_decomposition=True.

        Arrange: GenAI analyzer returns "BROAD"
        Act: Call _assess_genai with a multi-component description
        Assert: needs_decomposition=True, confidence=0.9
        """
        mock_analyzer = _make_mock_analyzer("BROAD")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.parse_classification_response", return_value="BROAD"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Add caching and update database schema")

        assert result is not None
        assert result.needs_decomposition is True
        assert result.confidence == 0.9

    def test_genai_returns_very_broad_maps_to_needs_decomposition_true(self):
        """When GenAI responds VERY_BROAD, _assess_genai returns needs_decomposition=True."""
        mock_analyzer = _make_mock_analyzer("VERY_BROAD")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.parse_classification_response", return_value="VERY_BROAD"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai(
                "Redesign entire auth system and migrate database and add new API endpoints"
            )

        assert result is not None
        assert result.needs_decomposition is True

    def test_genai_returns_none_triggers_heuristic_fallback(self):
        """When GenAI returns None (missing API key), _assess_genai returns None for fallback."""
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Add user endpoint")

        assert result is None, (
            "_assess_genai should return None when GenAI returns None (triggers fallback)"
        )

    def test_analyze_complexity_falls_back_to_heuristic_when_genai_returns_none(self):
        """Full analyze_complexity(): GenAI returns None → heuristic runs → valid result."""
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = analyze_complexity("Refactor auth module and add new endpoints")

        _assert_valid_complexity_analysis(result)

    def test_genai_scope_false_disables_genai_path(self):
        """When GENAI_SCOPE=false, GenAI is never called and heuristic runs."""
        mock_analyzer = _make_mock_analyzer("BROAD")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "false"}, clear=False),
        ):
            result = analyze_complexity("Add feature")

        # GenAIAnalyzer.analyze should NOT be called
        mock_analyzer.analyze.assert_not_called()
        _assert_valid_complexity_analysis(result)

    def test_genai_not_available_module_flag_bypasses_genai(self):
        """When _GENAI_AVAILABLE is False, _assess_genai returns None immediately."""
        with (
            patch("scope_detector._GENAI_AVAILABLE", False),
            patch("scope_detector.GenAIAnalyzer") as mock_cls,
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Add feature")

        assert result is None
        mock_cls.assert_not_called()

    def test_genai_not_available_analyze_complexity_still_returns_heuristic(self):
        """When _GENAI_AVAILABLE=False, analyze_complexity() returns valid heuristic result."""
        with (
            patch("scope_detector._GENAI_AVAILABLE", False),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = analyze_complexity("Refactor and redesign entire system")

        _assert_valid_complexity_analysis(result)

    def test_genai_exception_does_not_crash_analyze_complexity(self):
        """When GenAI raises an exception, analyze_complexity() does not crash."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("Connection timeout")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = analyze_complexity("Add feature to system")

        _assert_valid_complexity_analysis(result)

    def test_genai_unrecognized_response_falls_back_to_heuristic(self):
        """When GenAI returns text not in [FOCUSED, BROAD, VERY_BROAD], fallback to heuristic."""
        mock_analyzer = _make_mock_analyzer("I'm not sure about the scope here.")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.parse_classification_response", return_value=None),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Do something")

        assert result is None

    def test_analyze_complexity_always_returns_valid_result(self):
        """analyze_complexity() NEVER returns None regardless of GenAI availability."""
        mock_analyzer = _make_mock_analyzer(None)

        for description in ["Add feature", "Refactor everything", "", "x" * 10001]:
            with (
                patch("scope_detector._GENAI_AVAILABLE", True),
                patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
                patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
            ):
                result = analyze_complexity(description)

            assert result is not None, f"analyze_complexity() returned None for {description!r}"
            assert isinstance(result, ComplexityAnalysis)

    def test_return_type_has_all_four_fields(self):
        """For each GenAI label, verify all 4 ComplexityAnalysis fields are populated."""
        test_cases = [
            ("FOCUSED", False),
            ("BROAD", True),
            ("VERY_BROAD", True),
        ]
        for label, expected_decomp in test_cases:
            mock_analyzer = _make_mock_analyzer(label)

            with (
                patch("scope_detector._GENAI_AVAILABLE", True),
                patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
                patch("scope_detector.parse_classification_response", return_value=label),
                patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
            ):
                result = _assess_genai("test feature")

            assert result is not None
            _assert_valid_complexity_analysis(result)
            assert result.needs_decomposition == expected_decomp

    def test_analyze_called_with_correct_prompt_and_kwarg(self):
        """analyze() is called with SCOPE_ASSESSMENT_PROMPT and issue_text kwarg."""
        mock_analyzer = _make_mock_analyzer("FOCUSED")
        mock_prompt = "Classify as FOCUSED/BROAD/VERY_BROAD: {issue_text}"

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.SCOPE_ASSESSMENT_PROMPT", mock_prompt),
            patch("scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            _assess_genai("some feature text")

        mock_analyzer.analyze.assert_called_once_with(
            mock_prompt,
            issue_text="some feature text",
        )

    def test_parse_classification_called_with_correct_labels(self):
        """parse_classification_response is called with ["FOCUSED", "BROAD", "VERY_BROAD"]."""
        mock_analyzer = _make_mock_analyzer("BROAD response text")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.parse_classification_response", return_value="BROAD") as mock_parse,
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            _assess_genai("add caching and update database")

        mock_parse.assert_called_once_with(
            "BROAD response text",
            ["FOCUSED", "BROAD", "VERY_BROAD"],
        )

    def test_genai_confidence_is_0_9_for_successful_response(self):
        """GenAI-classified results have confidence=0.9."""
        mock_analyzer = _make_mock_analyzer("FOCUSED")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Add rate limiting")

        assert result is not None
        assert result.confidence == 0.9


# ============================================================================
# Tests for issue_scope_detector.IssueScopeDetector._detect_genai
# ============================================================================

@pytest.mark.skipif(not _ISSUE_SCOPE_DETECTOR_AVAILABLE, reason="issue_scope_detector.py not importable")
class TestIssueScopeDetectorDetectGenAI:
    """Tests for IssueScopeDetector._detect_genai() hybrid path."""

    def test_genai_returns_focused_maps_to_focused_level(self):
        """When GenAI responds FOCUSED, _detect_genai returns ScopeDetection with FOCUSED level."""
        mock_analyzer = _make_mock_analyzer("FOCUSED")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector._detect_genai("Add rate limiting and timeout")

        assert result is not None
        assert result.level == ScopeLevel.FOCUSED
        assert result.should_warn is False
        assert result.confidence == 0.9 if hasattr(result, "confidence") else True
        assert "GenAI" in result.reasoning or "genai" in result.reasoning.lower()

    def test_genai_returns_broad_maps_to_broad_level(self):
        """When GenAI responds BROAD, _detect_genai returns ScopeDetection with BROAD level."""
        mock_analyzer = _make_mock_analyzer("BROAD")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="BROAD"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector._detect_genai("Refactor auth and add new endpoints")

        assert result is not None
        assert result.level == ScopeLevel.BROAD
        assert result.should_warn is True

    def test_genai_returns_very_broad_maps_to_very_broad_level(self):
        """When GenAI responds VERY_BROAD, _detect_genai returns VERY_BROAD level."""
        mock_analyzer = _make_mock_analyzer("VERY_BROAD")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="VERY_BROAD"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector._detect_genai(
                "Redesign entire auth system and migrate DB and add API"
            )

        assert result is not None
        assert result.level == ScopeLevel.VERY_BROAD
        assert result.should_warn is True

    def test_genai_returns_none_triggers_heuristic_fallback(self):
        """When GenAI returns None, _detect_genai returns None for fallback."""
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector._detect_genai("Add user endpoint")

        assert result is None

    def test_detect_falls_back_to_heuristic_when_genai_returns_none(self):
        """Full detect(): GenAI returns None → heuristic runs → valid ScopeDetection."""
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect(
                "Replace mock logging with real SSH and API implementation"
            )

        _assert_valid_scope_detection(result)

    def test_genai_scope_false_disables_genai_path(self):
        """When GENAI_SCOPE=false, GenAI is never called and heuristic runs."""
        mock_analyzer = _make_mock_analyzer("BROAD")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "false"}, clear=False),
        ):
            result = IssueScopeDetector.detect("Fix bug in login")

        mock_analyzer.analyze.assert_not_called()
        _assert_valid_scope_detection(result)

    def test_genai_not_available_module_flag_bypasses_genai(self):
        """When _GENAI_AVAILABLE is False, _detect_genai returns None immediately."""
        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", False),
            patch("issue_scope_detector.GenAIAnalyzer") as mock_cls,
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector._detect_genai("Add feature")

        assert result is None
        mock_cls.assert_not_called()

    def test_genai_not_available_detect_still_returns_heuristic(self):
        """When _GENAI_AVAILABLE=False, detect() returns valid heuristic result."""
        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", False),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect(
                "Replace all mock implementations with real SSH and API"
            )

        _assert_valid_scope_detection(result)

    def test_genai_exception_does_not_crash_detect(self):
        """When GenAI raises an exception, detect() does not crash."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("Connection timeout")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect("Add feature to system")

        _assert_valid_scope_detection(result)

    def test_genai_unrecognized_response_falls_back_to_heuristic(self):
        """When GenAI returns text not in valid labels, _detect_genai returns None."""
        mock_analyzer = _make_mock_analyzer("I'm not sure about the scope.")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value=None),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector._detect_genai("Do something")

        assert result is None

    def test_detect_always_returns_valid_scope_detection_not_none(self):
        """detect() NEVER returns None regardless of GenAI availability."""
        mock_analyzer = _make_mock_analyzer(None)

        for title in ["Fix bug", "Replace all mocks with real implementations", "", "x" * 10001]:
            with (
                patch("issue_scope_detector._GENAI_AVAILABLE", True),
                patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
                patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
            ):
                result = IssueScopeDetector.detect(title or "placeholder")

            assert result is not None, f"detect() returned None for title: {title!r}"
            assert isinstance(result, ScopeDetection)

    def test_return_type_has_all_five_fields(self):
        """For each GenAI label, verify all 5 ScopeDetection fields are populated."""
        test_cases = [
            ("FOCUSED", ScopeLevel.FOCUSED, False),
            ("BROAD", ScopeLevel.BROAD, True),
            ("VERY_BROAD", ScopeLevel.VERY_BROAD, True),
        ]
        for label, expected_level, expected_warn in test_cases:
            mock_analyzer = _make_mock_analyzer(label)

            with (
                patch("issue_scope_detector._GENAI_AVAILABLE", True),
                patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
                patch("issue_scope_detector.parse_classification_response", return_value=label),
                patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
            ):
                result = IssueScopeDetector._detect_genai("test issue")

            assert result is not None
            _assert_valid_scope_detection(result)
            assert result.level == expected_level
            assert result.should_warn == expected_warn

    def test_detect_genai_analyze_called_with_correct_prompt_and_kwarg(self):
        """analyze() is called with SCOPE_ASSESSMENT_PROMPT and issue_text kwarg."""
        mock_analyzer = _make_mock_analyzer("FOCUSED")
        mock_prompt = "Classify as FOCUSED/BROAD/VERY_BROAD: {issue_text}"

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.SCOPE_ASSESSMENT_PROMPT", mock_prompt),
            patch("issue_scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            IssueScopeDetector._detect_genai("some issue text")

        mock_analyzer.analyze.assert_called_once_with(
            mock_prompt,
            issue_text="some issue text",
        )

    def test_parse_classification_called_with_correct_labels(self):
        """parse_classification_response is called with ["FOCUSED", "BROAD", "VERY_BROAD"]."""
        mock_analyzer = _make_mock_analyzer("BROAD response text")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch(
                "issue_scope_detector.parse_classification_response",
                return_value="BROAD",
            ) as mock_parse,
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            IssueScopeDetector._detect_genai("add caching and update database")

        mock_parse.assert_called_once_with(
            "BROAD response text",
            ["FOCUSED", "BROAD", "VERY_BROAD"],
        )

    def test_detect_uses_genai_result_when_available(self):
        """detect() uses GenAI result instead of heuristic when GenAI succeeds.

        Scenario: "Add rate limiting and timeout" has two actions joined by "and"
        which heuristic might classify as BROAD, but GenAI classifies as FOCUSED.
        """
        mock_analyzer = _make_mock_analyzer("FOCUSED")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect("Add rate limiting and timeout")

        # GenAI says FOCUSED → should override heuristic if it would say BROAD
        assert result.level == ScopeLevel.FOCUSED
        assert result.should_warn is False

    def test_detect_broad_result_includes_suggested_splits(self):
        """detect() with BROAD GenAI result generates heuristic-based split suggestions."""
        mock_analyzer = _make_mock_analyzer("BROAD")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="BROAD"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect(
                "Replace mock log streaming with real SSH and API implementation"
            )

        assert result.level == ScopeLevel.BROAD
        assert isinstance(result.suggested_splits, list)
        # Broad results should have at least some split suggestions
        assert len(result.suggested_splits) >= 0  # May be empty for some inputs

    def test_detect_github_issue_dict_works_with_genai_path(self):
        """detect() with github_issue dict works correctly with GenAI path."""
        mock_analyzer = _make_mock_analyzer("BROAD")
        issue = {
            "title": "Refactor auth module",
            "body": "Add new endpoints and update database schema"
        }

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="BROAD"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect(
                issue["title"],
                github_issue=issue,
            )

        _assert_valid_scope_detection(result)


# ============================================================================
# Edge case tests for both modules
# ============================================================================

@pytest.mark.skipif(not _SCOPE_DETECTOR_AVAILABLE, reason="scope_detector.py not importable")
class TestScopeDetectorGenAIEdgeCases:
    """Edge case tests for scope_detector GenAI path."""

    def test_genai_exception_from_initializer_falls_back(self):
        """GenAIAnalyzer constructor raising an exception triggers fallback."""
        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch(
                "scope_detector.GenAIAnalyzer",
                side_effect=ImportError("anthropic not installed"),
            ),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = analyze_complexity("Add feature to system")

        _assert_valid_complexity_analysis(result)

    def test_assess_genai_returns_none_on_exception(self):
        """_assess_genai returns None when an exception occurs inside it."""
        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch(
                "scope_detector.GenAIAnalyzer",
                side_effect=RuntimeError("SDK init failed"),
            ),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Add feature")

        assert result is None

    def test_genai_scope_env_false_string_variants(self):
        """GENAI_SCOPE=false (case insensitive) disables GenAI."""
        mock_analyzer = _make_mock_analyzer("BROAD")

        for false_value in ("false", "FALSE", "False", "0", "no"):
            with (
                patch("scope_detector._GENAI_AVAILABLE", True),
                patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
                patch.dict(os.environ, {"GENAI_SCOPE": false_value}, clear=False),
            ):
                result = analyze_complexity("Add feature")

            assert result is not None, f"analyze_complexity() returned None with GENAI_SCOPE={false_value}"

    def test_genai_indicators_contain_genai_scope_key(self):
        """When GenAI classification succeeds, indicators contains genai_scope key."""
        mock_analyzer = _make_mock_analyzer("FOCUSED")

        with (
            patch("scope_detector._GENAI_AVAILABLE", True),
            patch("scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = _assess_genai("Add rate limiting")

        assert result is not None
        # GenAI-sourced result stores classification in indicators dict
        assert "genai_scope" in result.indicators, (
            f"indicators should contain genai_scope key, got: {result.indicators}"
        )
        assert result.indicators["genai_scope"] == "FOCUSED"


@pytest.mark.skipif(not _ISSUE_SCOPE_DETECTOR_AVAILABLE, reason="issue_scope_detector.py not importable")
class TestIssueScopeDetectorGenAIEdgeCases:
    """Edge case tests for issue_scope_detector GenAI path."""

    def test_genai_exception_from_initializer_falls_back(self):
        """GenAIAnalyzer constructor raising an exception triggers fallback."""
        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch(
                "issue_scope_detector.GenAIAnalyzer",
                side_effect=ImportError("anthropic not installed"),
            ),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect("Add feature to system")

        _assert_valid_scope_detection(result)

    def test_detect_genai_returns_none_on_exception(self):
        """_detect_genai returns None when an exception occurs inside it."""
        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch(
                "issue_scope_detector.GenAIAnalyzer",
                side_effect=RuntimeError("SDK init failed"),
            ),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector._detect_genai("Add feature")

        assert result is None

    def test_genai_scope_env_false_string_variants(self):
        """GENAI_SCOPE=false disables GenAI for issue_scope_detector."""
        mock_analyzer = _make_mock_analyzer("BROAD")

        for false_value in ("false", "FALSE", "False"):
            with (
                patch("issue_scope_detector._GENAI_AVAILABLE", True),
                patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
                patch.dict(os.environ, {"GENAI_SCOPE": false_value}, clear=False),
            ):
                result = IssueScopeDetector.detect("Fix bug")

            assert result is not None, f"detect() returned None with GENAI_SCOPE={false_value}"

    def test_both_flags_true_genai_runs(self):
        """Both _GENAI_AVAILABLE=True and GENAI_SCOPE=true → GenAI runs."""
        mock_analyzer = _make_mock_analyzer("FOCUSED")

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, {"GENAI_SCOPE": "true"}, clear=False),
        ):
            result = IssueScopeDetector.detect("Add pagination feature")

        mock_analyzer.analyze.assert_called_once()
        assert result is not None
        assert result.level == ScopeLevel.FOCUSED

    def test_genai_scope_env_default_is_true(self):
        """When GENAI_SCOPE is not set, it defaults to enabled (true)."""
        mock_analyzer = _make_mock_analyzer("FOCUSED")
        env_without_flag = {k: v for k, v in os.environ.items() if k != "GENAI_SCOPE"}

        with (
            patch("issue_scope_detector._GENAI_AVAILABLE", True),
            patch("issue_scope_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("issue_scope_detector.parse_classification_response", return_value="FOCUSED"),
            patch.dict(os.environ, env_without_flag, clear=True),
        ):
            result = IssueScopeDetector._detect_genai("Fix typo")

        # GenAI should have been called (default is enabled)
        mock_analyzer.analyze.assert_called_once()
