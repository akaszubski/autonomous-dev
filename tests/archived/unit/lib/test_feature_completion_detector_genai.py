"""Unit tests for GenAI path in feature_completion_detector.py.

Tests the hybrid GenAI + heuristic approach for semantic feature completion detection.
All tests mock GenAI calls — no real API calls made.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# Add lib and hooks dirs to path
_WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
_LIB_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "hooks"

sys.path.insert(0, str(_LIB_PATH))
sys.path.insert(0, str(_HOOKS_PATH))

try:
    from feature_completion_detector import FeatureCompletionDetector, CompletionCheck
except ImportError as exc:
    pytest.skip(f"feature_completion_detector not importable: {exc}", allow_module_level=True)


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_analyzer(response: Optional[str]) -> MagicMock:
    """Return a mock GenAIAnalyzer whose .analyze() returns `response`."""
    mock = MagicMock()
    mock.analyze.return_value = response
    return mock


def _make_detector(tmp_path: Path) -> FeatureCompletionDetector:
    """Create a minimal project and detector."""
    (tmp_path / "CLAUDE.md").write_text("# Test Project\nSome content.")
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude" / "PROJECT.md").write_text("# Goals\nBuild widgets.")
    (tmp_path / ".git").mkdir(exist_ok=True)
    return FeatureCompletionDetector(project_root=tmp_path)


# ============================================================================
# GenAI returns IMPLEMENTED
# ============================================================================


class TestGenAIImplemented:

    def test_genai_implemented_returns_likely_complete(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("IMPLEMENTED\nFeature exists as registration input validation.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="IMPLEMENTED"),
        ):
            result = detector.check_feature("form validation")

        assert result.likely_complete is True
        assert result.confidence == "high"
        assert any("GenAI semantic analysis: IMPLEMENTED" in e for e in result.evidence)

    def test_genai_preserves_heuristic_evidence(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Project\nIssue #99 is complete")
        (tmp_path / ".claude").mkdir(exist_ok=True)
        (tmp_path / ".claude" / "PROJECT.md").write_text("# Goals\nIssue #99 done.")
        (tmp_path / ".git").mkdir(exist_ok=True)
        detector = FeatureCompletionDetector(project_root=tmp_path)
        mock_analyzer = _make_mock_analyzer("IMPLEMENTED\nExists.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="IMPLEMENTED"),
        ):
            result = detector.check_feature("Add form validation (Issue #99)")

        assert result.likely_complete is True
        # Should include heuristic evidence (Issue #99 found) + GenAI evidence
        assert len(result.evidence) >= 2


# ============================================================================
# GenAI returns NOT_IMPLEMENTED
# ============================================================================


class TestGenAINotImplemented:

    def test_genai_not_implemented(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("NOT_IMPLEMENTED\nNo matching functionality found.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="NOT_IMPLEMENTED"),
        ):
            result = detector.check_feature("quantum computing module")

        assert result.likely_complete is False
        assert result.confidence == "high"
        assert any("NOT_IMPLEMENTED" in e for e in result.evidence)


# ============================================================================
# GenAI returns PARTIAL
# ============================================================================


class TestGenAIPartial:

    def test_genai_partial_returns_likely_complete(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("PARTIAL\nCore validation exists but missing email format check.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="PARTIAL"),
        ):
            result = detector.check_feature("email validation")

        assert result.likely_complete is True
        assert result.confidence == "medium"
        assert any("PARTIAL" in e for e in result.evidence)


# ============================================================================
# GenAI fallback scenarios
# ============================================================================


class TestGenAIFallback:

    def test_fallback_when_genai_unavailable(self, tmp_path):
        detector = _make_detector(tmp_path)

        with patch("feature_completion_detector._GENAI_AVAILABLE", False):
            result = detector.check_feature("some feature")

        assert isinstance(result.likely_complete, bool)
        assert result.confidence in ("high", "medium", "low")
        assert not any("GenAI" in e for e in result.evidence)

    def test_fallback_when_feature_flag_disabled(self, tmp_path):
        detector = _make_detector(tmp_path)

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=False),
        ):
            result = detector.check_feature("some feature")

        assert not any("GenAI" in e for e in result.evidence)

    def test_fallback_when_genai_returns_none(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
        ):
            result = detector.check_feature("some feature")

        assert not any("GenAI" in e for e in result.evidence)

    def test_fallback_when_parse_returns_none(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("GIBBERISH")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value=None),
        ):
            result = detector.check_feature("some feature")

        assert not any("GenAI" in e for e in result.evidence)

    def test_fallback_when_genai_raises_exception(self, tmp_path):
        detector = _make_detector(tmp_path)

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", side_effect=Exception("API error")),
        ):
            result = detector.check_feature("some feature")

        assert not any("GenAI" in e for e in result.evidence)


# ============================================================================
# Return type preservation
# ============================================================================


class TestReturnTypePreservation:

    def test_return_type_is_completion_check(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("IMPLEMENTED\nExists.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="IMPLEMENTED"),
        ):
            result = detector.check_feature("test feature")

        assert isinstance(result, CompletionCheck)

    def test_to_dict_works_with_genai_result(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("IMPLEMENTED\nExists.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="IMPLEMENTED"),
        ):
            result = detector.check_feature("test feature")

        d = result.to_dict()
        assert "feature" in d
        assert "likely_complete" in d
        assert "evidence" in d
        assert "confidence" in d

    def test_feature_field_preserved(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("NOT_IMPLEMENTED\nNot found.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="NOT_IMPLEMENTED"),
        ):
            result = detector.check_feature("my specific feature")

        assert result.feature == "my specific feature"

    def test_check_all_features_with_genai(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("IMPLEMENTED\nExists.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="IMPLEMENTED"),
        ):
            results = detector.check_all_features(["feature A", "feature B"])

        assert len(results) == 2
        assert all(r.likely_complete for r in results)


# ============================================================================
# Explanation extraction
# ============================================================================


class TestExplanationExtraction:

    def test_explanation_included_in_evidence(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("IMPLEMENTED\nThe registration input validator covers this.")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="IMPLEMENTED"),
        ):
            result = detector.check_feature("form validation")

        genai_evidence = [e for e in result.evidence if "GenAI" in e]
        assert len(genai_evidence) == 1
        assert "registration input validator" in genai_evidence[0]

    def test_no_explanation_handled(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_analyzer = _make_mock_analyzer("IMPLEMENTED")

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", return_value=True),
            patch("feature_completion_detector.GenAIAnalyzer", return_value=mock_analyzer),
            patch("feature_completion_detector.parse_classification_response", return_value="IMPLEMENTED"),
        ):
            result = detector.check_feature("form validation")

        assert result.likely_complete is True


# ============================================================================
# Environment variable control
# ============================================================================


class TestEnvironmentControl:

    def test_should_use_genai_called_with_completion(self, tmp_path):
        detector = _make_detector(tmp_path)
        mock_should = MagicMock(return_value=False)

        with (
            patch("feature_completion_detector._GENAI_AVAILABLE", True),
            patch("feature_completion_detector.should_use_genai", mock_should),
        ):
            detector.check_feature("test")

        mock_should.assert_called_with("completion")
