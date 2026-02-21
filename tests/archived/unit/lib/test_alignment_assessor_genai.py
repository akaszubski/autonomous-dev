"""Unit tests for AlignmentAssessor GenAI hybrid paths.

Tests cover the two GenAI enhancements added to alignment_assessor.py:

Enhancement A: 12-Factor scoring via _assess_twelve_factor_genai()
- GenAI returns valid JSON scores -> all 12 factors populated
- GenAI returns None -> hardcoded heuristic fallback
- GENAI_ALIGNMENT=false -> GenAI never called
- Return type always TwelveFactorScore

Enhancement B: Goals extraction via _extract_goals_genai()
- GenAI returns goals text -> used in PROJECT.md GOALS section
- GenAI returns None -> heading-search fallback
- GENAI_ALIGNMENT=false -> GenAI never called
- Return type Optional[str]

Issue: #N/A (GenAI hybrid path for alignment_assessor.py)
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Import path setup
# alignment_assessor.py has a try/except for relative vs absolute imports,
# allowing it to be imported directly when lib is on sys.path.
# ============================================================================

_WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
_LIB_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "hooks"

sys.path.insert(0, str(_LIB_PATH))
sys.path.insert(0, str(_HOOKS_PATH))

try:
    from alignment_assessor import (
        AlignmentAssessor,
        TwelveFactorScore,
        ProjectMdDraft,
        Severity,
    )
except ImportError as exc:
    pytest.skip(
        f"alignment_assessor.py not importable: {exc}",
        allow_module_level=True,
    )

# Module path prefix for patching (direct module name since lib is on sys.path)
_MOD = "alignment_assessor"


# ============================================================================
# Helpers
# ============================================================================

VALID_TWELVE_FACTOR_JSON = {
    "codebase": 10,
    "dependencies": 8,
    "config": 7,
    "backing_services": 6,
    "build_release_run": 9,
    "processes": 5,
    "port_binding": 8,
    "concurrency": 4,
    "disposability": 6,
    "dev_prod_parity": 9,
    "logs": 7,
    "admin_processes": 5,
}

REQUIRED_FACTORS = {
    "codebase", "dependencies", "config", "backing_services",
    "build_release_run", "processes", "port_binding", "concurrency",
    "disposability", "dev_prod_parity", "logs", "admin_processes",
}


def _make_mock_analyzer(response: Optional[str]) -> MagicMock:
    """Return a mock GenAIAnalyzer whose .analyze() returns `response`."""
    mock = MagicMock()
    mock.analyze.return_value = response
    return mock


def _make_assessor(tmp_path: Path) -> AlignmentAssessor:
    """Create an AlignmentAssessor with mocked security utils."""
    with (
        patch(f"{_MOD}.validate_path", return_value=str(tmp_path)),
        patch(f"{_MOD}.audit_log"),
    ):
        return AlignmentAssessor(tmp_path)


def _make_mock_analysis(
    *,
    primary_language: str = "python",
    framework: Optional[str] = "flask",
    package_manager: str = "pip",
    dependencies: set = None,
    config_files: list = None,
    total_files: int = 20,
    source_files: int = 15,
    test_files: int = 5,
    has_src_dir: bool = True,
) -> MagicMock:
    """Build a mock AnalysisReport."""
    mock = MagicMock()
    mock.tech_stack = MagicMock()
    mock.tech_stack.primary_language = primary_language
    mock.tech_stack.framework = framework
    mock.tech_stack.package_manager = package_manager
    mock.tech_stack.dependencies = dependencies or {"flask", "pytest"}
    mock.tech_stack.test_framework = "pytest"
    mock.structure = MagicMock()
    mock.structure.total_files = total_files
    mock.structure.source_files = source_files
    mock.structure.test_files = test_files
    mock.structure.doc_files = 1
    mock.structure.has_src_dir = has_src_dir
    mock.structure.config_files = config_files or [".env", ".github/workflows/ci.yml"]
    return mock


# ============================================================================
# Enhancement A: 12-Factor GenAI scoring
# ============================================================================

class TestAssessTwelveFactorGenAI:
    """Tests for _assess_twelve_factor_genai() method."""

    def test_genai_returns_valid_json_all_12_factors_populated(self, tmp_path):
        """GenAI returns valid JSON -> TwelveFactorScore with all 12 factors.

        Arrange: GenAI analyzer returns JSON string with all 12 factor scores
        Act: Call _assess_twelve_factor_genai
        Assert: TwelveFactorScore returned with all 12 factors, not None
        """
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(json.dumps(VALID_TWELVE_FACTOR_JSON))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is not None, "_assess_twelve_factor_genai should return TwelveFactorScore"
        assert isinstance(result, TwelveFactorScore)
        assert REQUIRED_FACTORS.issubset(result.factors.keys()), (
            f"Missing factors: {REQUIRED_FACTORS - set(result.factors.keys())}"
        )

    def test_genai_returns_valid_json_scores_match(self, tmp_path):
        """GenAI JSON scores are correctly parsed and stored in TwelveFactorScore."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(json.dumps(VALID_TWELVE_FACTOR_JSON))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is not None
        assert result.factors["codebase"] == 10
        assert result.factors["dependencies"] == 8
        assert result.factors["config"] == 7
        assert result.factors["processes"] == 5

    def test_genai_returns_none_triggers_heuristic_fallback(self, tmp_path):
        """GenAI returns None -> _assess_twelve_factor_genai returns None for fallback.

        The caller (calculate_twelve_factor_score) should then run heuristics.
        """
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is None, (
            "_assess_twelve_factor_genai should return None when GenAI returns None"
        )

    def test_genai_alignment_false_disables_genai(self, tmp_path):
        """GENAI_ALIGNMENT=false -> GenAI never called, returns None."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(json.dumps(VALID_TWELVE_FACTOR_JSON))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "false"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is None
        mock_analyzer.analyze.assert_not_called()

    def test_genai_not_available_returns_none(self, tmp_path):
        """_GENAI_AVAILABLE=False -> returns None without attempting GenAI."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_cls = MagicMock()

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", False),
            patch(f"{_MOD}.GenAIAnalyzer", mock_cls),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is None
        mock_cls.assert_not_called()

    def test_genai_exception_returns_none_gracefully(self, tmp_path):
        """GenAI raises exception -> _assess_twelve_factor_genai returns None gracefully."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("Connection timeout")

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is None

    def test_calculate_twelve_factor_uses_genai_when_available(self, tmp_path):
        """calculate_twelve_factor_score uses GenAI result when GenAI succeeds.

        Full integration: GenAI result should be returned instead of heuristic.
        """
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(json.dumps(VALID_TWELVE_FACTOR_JSON))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor.calculate_twelve_factor_score(analysis)

        assert isinstance(result, TwelveFactorScore)
        # GenAI result should be used: codebase=10 from our mock JSON
        assert result.factors["codebase"] == 10

    def test_calculate_twelve_factor_falls_back_to_heuristic_when_genai_fails(self, tmp_path):
        """calculate_twelve_factor_score falls back to heuristic when GenAI returns None.

        The heuristic should still produce a valid TwelveFactorScore.
        """
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        # Create .git directory so heuristic gives codebase=10
        (tmp_path / ".git").mkdir()
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor.calculate_twelve_factor_score(analysis)

        assert isinstance(result, TwelveFactorScore)
        # Heuristic should see .git dir -> codebase=10
        assert result.factors["codebase"] == 10
        assert REQUIRED_FACTORS.issubset(result.factors.keys())

    def test_genai_json_with_markdown_fences_parsed_correctly(self, tmp_path):
        """GenAI response wrapped in markdown fences is parsed correctly."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        fenced_response = f"```json\n{json.dumps(VALID_TWELVE_FACTOR_JSON)}\n```"
        mock_analyzer = _make_mock_analyzer(fenced_response)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is not None
        assert isinstance(result, TwelveFactorScore)
        assert len(result.factors) == 12

    def test_genai_scores_clamped_to_valid_range(self, tmp_path):
        """Scores outside 1-10 are clamped to valid range."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        out_of_range = {**VALID_TWELVE_FACTOR_JSON, "codebase": 15, "dependencies": 0}
        mock_analyzer = _make_mock_analyzer(json.dumps(out_of_range))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is not None
        assert result.factors["codebase"] == 10  # Clamped from 15
        assert result.factors["dependencies"] == 1  # Clamped from 0

    def test_genai_missing_factors_returns_none(self, tmp_path):
        """GenAI response missing required factors -> returns None for fallback."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        incomplete = {"codebase": 10, "dependencies": 8}  # Only 2 of 12 factors
        mock_analyzer = _make_mock_analyzer(json.dumps(incomplete))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is None

    def test_twelve_factor_score_total_calculated_correctly(self, tmp_path):
        """TwelveFactorScore from GenAI has correct total_score and compliance_percentage."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        # Sum = 10+8+7+6+9+5+8+4+6+9+7+5 = 84
        mock_analyzer = _make_mock_analyzer(json.dumps(VALID_TWELVE_FACTOR_JSON))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is not None
        expected_total = sum(VALID_TWELVE_FACTOR_JSON.values())
        assert result.total_score == expected_total
        assert result.compliance_percentage == pytest.approx(expected_total / 120 * 100)

    def test_genai_not_all_7_scores_varied(self, tmp_path):
        """GenAI result does not default all factors to 7/10 (the old hardcoded behavior).

        This verifies the GenAI path produces varied scores.
        """
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(json.dumps(VALID_TWELVE_FACTOR_JSON))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is not None
        # Check that not all scores are 7 (the old hardcoded default)
        unique_scores = set(result.factors.values())
        assert len(unique_scores) > 1, (
            "GenAI-scored factors should have varied scores, not all 7/10"
        )


# ============================================================================
# Enhancement B: Goals extraction GenAI
# ============================================================================

class TestExtractGoalsGenAI:
    """Tests for _extract_goals_genai() method."""

    SAMPLE_GOALS_RESPONSE = (
        "- Provide autonomous development capabilities to Claude Code users\n"
        "- Enable AI agents to collaborate on software development tasks\n"
        "- Automate repetitive coding tasks to accelerate development velocity\n"
        "- Maintain code quality through automated review and testing\n"
        "- Support brownfield project retrofit with alignment assessment"
    )

    def test_genai_returns_goals_text_used_in_project_md(self, tmp_path):
        """GenAI returns goals text -> included in GOALS section of PROJECT.md draft.

        Arrange: README exists, GenAI returns bullet-point goals
        Act: Call generate_project_md which calls _extract_goals which calls _extract_goals_genai
        Assert: GOALS section contains the GenAI-synthesized content
        """
        (tmp_path / "README.md").write_text(
            "# My Project\n\nA tool for doing stuff.\n\n## Features\n- Feature A\n- Feature B"
        )
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(self.SAMPLE_GOALS_RESPONSE)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            draft = assessor.generate_project_md(analysis)

        assert "GOALS" in draft.sections
        goals_content = draft.sections["GOALS"]
        # GenAI-synthesized content should be used
        assert "autonomous development" in goals_content.lower() or "GenAI" in goals_content

    def test_genai_returns_goals_directly_via_extract_goals_genai(self, tmp_path):
        """_extract_goals_genai returns formatted goals string when GenAI succeeds."""
        assessor = _make_assessor(tmp_path)
        mock_analyzer = _make_mock_analyzer(self.SAMPLE_GOALS_RESPONSE)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._extract_goals_genai("# Project README\n\nSome content here.")

        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain bullet points from GenAI response
        assert "-" in result

    def test_genai_returns_none_triggers_heading_search_fallback(self, tmp_path):
        """GenAI returns None -> _extract_goals falls back to heading search.

        When README has "## Goals" heading, fallback finds it.
        """
        (tmp_path / "README.md").write_text(
            "# My Project\n\n## Goals\nBuild something great\n"
        )
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            draft = assessor.generate_project_md(analysis)

        # Heading-search fallback should find "## Goals"
        assert "GOALS" in draft.sections
        goals_content = draft.sections["GOALS"]
        # Fallback uses "Extracted from README.md" marker
        assert "README.md" in goals_content or "Goals" in goals_content or "TODO" in goals_content

    def test_genai_alignment_false_disables_goals_genai(self, tmp_path):
        """GENAI_ALIGNMENT=false -> _extract_goals_genai never called, returns None."""
        assessor = _make_assessor(tmp_path)
        mock_analyzer = _make_mock_analyzer(self.SAMPLE_GOALS_RESPONSE)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "false"}, clear=False),
        ):
            result = assessor._extract_goals_genai("# README\n\nContent here.")

        assert result is None
        mock_analyzer.analyze.assert_not_called()

    def test_genai_not_available_goals_returns_none(self, tmp_path):
        """_GENAI_AVAILABLE=False -> _extract_goals_genai returns None immediately."""
        assessor = _make_assessor(tmp_path)
        mock_cls = MagicMock()

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", False),
            patch(f"{_MOD}.GenAIAnalyzer", mock_cls),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._extract_goals_genai("# README\n\nContent here.")

        assert result is None
        mock_cls.assert_not_called()

    def test_genai_goals_exception_returns_none_gracefully(self, tmp_path):
        """GenAI exception -> _extract_goals_genai returns None gracefully."""
        assessor = _make_assessor(tmp_path)
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("API timeout")

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._extract_goals_genai("# README\n\nContent here.")

        assert result is None

    def test_genai_response_without_bullet_points_returns_none(self, tmp_path):
        """GenAI response without any bullet point marker (-) returns None for fallback."""
        assessor = _make_assessor(tmp_path)
        # Response with no bullet points
        mock_analyzer = _make_mock_analyzer("This project does interesting things.")

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._extract_goals_genai("# README\n\nContent here.")

        assert result is None

    def test_genai_goals_response_includes_synth_marker(self, tmp_path):
        """Successful GenAI goals response includes synthesis attribution marker."""
        assessor = _make_assessor(tmp_path)
        mock_analyzer = _make_mock_analyzer(self.SAMPLE_GOALS_RESPONSE)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            result = assessor._extract_goals_genai("# README\n\nContent here.")

        assert result is not None
        # Should include attribution indicating GenAI synthesis
        assert "GenAI" in result or "Synthesized" in result or "README" in result

    def test_goals_extraction_readme_content_capped_at_4000_chars(self, tmp_path):
        """Very long README is capped before sending to GenAI (avoid large API requests)."""
        assessor = _make_assessor(tmp_path)
        mock_analyzer = _make_mock_analyzer(self.SAMPLE_GOALS_RESPONSE)
        long_readme = "# README\n\n" + "x" * 10000  # 10K chars

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
        ):
            assessor._extract_goals_genai(long_readme)

        # Verify analyze was called with content capped to 4000 chars
        call_args = mock_analyzer.analyze.call_args
        assert call_args is not None
        readme_content_arg = call_args[1].get("readme_content", "") or (
            call_args[0][1] if len(call_args[0]) > 1 else ""
        )
        assert len(readme_content_arg) <= 4000, (
            f"README content should be capped at 4000 chars, got {len(readme_content_arg)}"
        )


# ============================================================================
# Return type preservation tests
# ============================================================================

class TestReturnTypePreservation:
    """Verify return types are preserved regardless of GenAI availability."""

    @pytest.mark.parametrize("genai_available,flag_value", [
        (True, "true"),
        (True, "false"),
        (False, "true"),
    ])
    def test_calculate_twelve_factor_always_returns_twelve_factor_score(
        self,
        tmp_path,
        genai_available: bool,
        flag_value: str,
    ):
        """calculate_twelve_factor_score always returns TwelveFactorScore, never None."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(None)  # GenAI fails

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", genai_available),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": flag_value}, clear=False),
        ):
            result = assessor.calculate_twelve_factor_score(analysis)

        assert result is not None, (
            f"calculate_twelve_factor_score returned None with "
            f"_GENAI_AVAILABLE={genai_available}, GENAI_ALIGNMENT={flag_value}"
        )
        assert isinstance(result, TwelveFactorScore)
        assert REQUIRED_FACTORS.issubset(result.factors.keys())

    @pytest.mark.parametrize("genai_available,flag_value", [
        (True, "true"),
        (True, "false"),
        (False, "true"),
    ])
    def test_extract_goals_genai_preserves_optional_str_type(
        self,
        tmp_path,
        genai_available: bool,
        flag_value: str,
    ):
        """_extract_goals_genai returns Optional[str] - either str or None, never other types."""
        assessor = _make_assessor(tmp_path)
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", genai_available),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": flag_value}, clear=False),
        ):
            result = assessor._extract_goals_genai("# README content")

        assert result is None or isinstance(result, str), (
            f"_extract_goals_genai should return str or None, got {type(result)}"
        )

    @pytest.mark.parametrize("genai_available,flag_value", [
        (True, "true"),
        (True, "false"),
        (False, "true"),
    ])
    def test_assess_twelve_factor_genai_preserves_optional_type(
        self,
        tmp_path,
        genai_available: bool,
        flag_value: str,
    ):
        """_assess_twelve_factor_genai returns Optional[TwelveFactorScore] - TwelveFactorScore or None."""
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(None)

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", genai_available),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": flag_value}, clear=False),
        ):
            result = assessor._assess_twelve_factor_genai(analysis)

        assert result is None or isinstance(result, TwelveFactorScore), (
            f"_assess_twelve_factor_genai should return TwelveFactorScore or None, got {type(result)}"
        )


# ============================================================================
# Integration tests: GenAI path in full assess() pipeline
# ============================================================================

class TestGenAIIntegrationWithAssess:
    """Integration tests verifying GenAI paths work within full assess() call."""

    VALID_GOALS = (
        "- Enable developers to build autonomous AI agent pipelines\n"
        "- Automate code review and quality assessment\n"
        "- Support brownfield project integration"
    )

    def test_full_assess_with_genai_twelve_factor(self, tmp_path):
        """Full assess() uses GenAI for 12-factor when GenAI succeeds."""
        (tmp_path / "README.md").write_text("# Project\n\nA great project.")
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = _make_mock_analyzer(json.dumps(VALID_TWELVE_FACTOR_JSON))

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "true"}, clear=False),
            patch(f"{_MOD}.audit_log"),
        ):
            # Re-create assessor without the outer patch context
            with patch(f"{_MOD}.validate_path", return_value=str(tmp_path)):
                assessor2 = AlignmentAssessor(tmp_path)
            result = assessor2.assess(analysis)

        assert result.twelve_factor_score is not None
        assert isinstance(result.twelve_factor_score, TwelveFactorScore)

    def test_full_assess_genai_disabled_uses_heuristic(self, tmp_path):
        """Full assess() with GENAI_ALIGNMENT=false uses heuristic for all scoring."""
        (tmp_path / "README.md").write_text("# Project\n\n## Goals\nBuild things.")
        (tmp_path / ".git").mkdir()
        assessor = _make_assessor(tmp_path)
        analysis = _make_mock_analysis()
        mock_analyzer = MagicMock()

        with (
            patch(f"{_MOD}._GENAI_AVAILABLE", True),
            patch(f"{_MOD}.GenAIAnalyzer", return_value=mock_analyzer),
            patch.dict(os.environ, {"GENAI_ALIGNMENT": "false"}, clear=False),
            patch(f"{_MOD}.audit_log"),
            patch(f"{_MOD}.validate_path", return_value=str(tmp_path)),
        ):
            assessor3 = AlignmentAssessor(tmp_path)
            result = assessor3.assess(analysis)

        # GenAI should not have been called
        mock_analyzer.analyze.assert_not_called()
        # Result should still be valid (heuristic ran)
        assert result.twelve_factor_score is not None
        assert isinstance(result.twelve_factor_score, TwelveFactorScore)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
