#!/usr/bin/env python3
"""
Unit tests for alignment_assessor.py.

Tests the alignment assessment for brownfield projects including:
- TwelveFactorScore calculation
- AlignmentGap detection
- ProjectMdDraft generation
- AssessmentResult coordination
- AlignmentAssessor orchestration

Issue: #234 (Test coverage improvement)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.alignment_assessor import (
    Severity,
    TwelveFactorScore,
    AlignmentGap,
    ProjectMdDraft,
    AssessmentResult,
    AlignmentAssessor,
)


class TestSeverityEnum:
    """Test Severity enum values."""

    def test_severity_critical(self):
        """CRITICAL severity should exist."""
        assert Severity.CRITICAL.value == "CRITICAL"

    def test_severity_high(self):
        """HIGH severity should exist."""
        assert Severity.HIGH.value == "HIGH"

    def test_severity_medium(self):
        """MEDIUM severity should exist."""
        assert Severity.MEDIUM.value == "MEDIUM"

    def test_severity_low(self):
        """LOW severity should exist."""
        assert Severity.LOW.value == "LOW"


class TestTwelveFactorScore:
    """Test TwelveFactorScore dataclass."""

    def test_empty_factors(self):
        """Empty factors should give zero score."""
        score = TwelveFactorScore()
        assert score.total_score == 0
        assert score.compliance_percentage == 0.0

    def test_single_factor(self):
        """Single factor score calculation."""
        score = TwelveFactorScore(factors={"codebase": 10})
        assert score.total_score == 10
        assert score.compliance_percentage == 100.0

    def test_multiple_factors(self):
        """Multiple factors score calculation."""
        factors = {
            "codebase": 10,
            "dependencies": 8,
            "config": 6
        }
        score = TwelveFactorScore(factors=factors)
        assert score.total_score == 24
        # 24 / 30 * 100 = 80.0%
        assert score.compliance_percentage == 80.0

    def test_all_twelve_factors(self):
        """Full 12-factor calculation."""
        factors = {f"factor_{i}": 5 for i in range(12)}
        score = TwelveFactorScore(factors=factors)
        assert score.total_score == 60
        # 60 / 120 * 100 = 50.0%
        assert score.compliance_percentage == 50.0

    def test_perfect_score(self):
        """Perfect 12-factor score."""
        factors = {f"factor_{i}": 10 for i in range(12)}
        score = TwelveFactorScore(factors=factors)
        assert score.total_score == 120
        assert score.compliance_percentage == 100.0

    def test_post_init_calculation(self):
        """__post_init__ should calculate scores."""
        score = TwelveFactorScore(factors={"a": 7, "b": 3})
        # Post init should have calculated
        assert score.total_score == 10
        assert score.compliance_percentage == 50.0


class TestAlignmentGap:
    """Test AlignmentGap dataclass."""

    def test_basic_gap_creation(self):
        """Create a basic alignment gap."""
        gap = AlignmentGap(
            category="testing",
            severity=Severity.HIGH,
            description="Missing tests",
            current_state="No tests",
            desired_state="80% coverage",
            fix_steps=["Add tests", "Run coverage"]
        )
        assert gap.category == "testing"
        assert gap.severity == Severity.HIGH
        assert gap.description == "Missing tests"
        assert len(gap.fix_steps) == 2

    def test_gap_with_scores(self):
        """Gap with impact and effort scores."""
        gap = AlignmentGap(
            category="documentation",
            severity=Severity.CRITICAL,
            description="Missing PROJECT.md",
            current_state="No file",
            desired_state="Complete PROJECT.md",
            fix_steps=["Create file"],
            impact_score=100,
            effort_hours=0.5
        )
        assert gap.impact_score == 100
        assert gap.effort_hours == 0.5

    def test_gap_default_scores(self):
        """Default impact and effort are zero."""
        gap = AlignmentGap(
            category="ci",
            severity=Severity.LOW,
            description="No CI",
            current_state="None",
            desired_state="GitHub Actions",
            fix_steps=[]
        )
        assert gap.impact_score == 0
        assert gap.effort_hours == 0.0


class TestProjectMdDraft:
    """Test ProjectMdDraft dataclass."""

    def test_empty_draft(self):
        """Empty draft should work."""
        draft = ProjectMdDraft()
        assert draft.sections == {}
        assert draft.confidence == 0.0
        assert draft.source_files == []

    def test_draft_with_sections(self):
        """Draft with sections."""
        draft = ProjectMdDraft(
            sections={"GOALS": "Build a thing", "SCOPE": "Everything"},
            confidence=0.8,
            source_files=["README.md"]
        )
        assert "GOALS" in draft.sections
        assert draft.confidence == 0.8

    def test_to_markdown_basic(self):
        """Convert to markdown format."""
        draft = ProjectMdDraft(
            sections={"GOALS": "Build amazing things"},
            confidence=0.9,
            source_files=["README.md"]
        )
        md = draft.to_markdown()
        assert "# Project Overview" in md
        assert "## GOALS" in md
        assert "Build amazing things" in md
        assert "Confidence: 0.90" in md

    def test_to_markdown_section_order(self):
        """Sections should be in standard order."""
        draft = ProjectMdDraft(
            sections={
                "TESTING": "pytest",
                "GOALS": "Goals first",
                "SCOPE": "Scope second"
            }
        )
        md = draft.to_markdown()
        # Check order - GOALS should come before SCOPE which should come before TESTING
        goals_pos = md.find("## GOALS")
        scope_pos = md.find("## SCOPE")
        testing_pos = md.find("## TESTING")
        assert goals_pos < scope_pos < testing_pos

    def test_to_markdown_extra_sections(self):
        """Extra sections should be included at end."""
        draft = ProjectMdDraft(
            sections={"GOALS": "Goals", "CUSTOM": "Custom section"}
        )
        md = draft.to_markdown()
        assert "## CUSTOM" in md


class TestAssessmentResult:
    """Test AssessmentResult dataclass."""

    def test_basic_result(self):
        """Create basic assessment result."""
        result = AssessmentResult(
            project_md=ProjectMdDraft(),
            twelve_factor_score=TwelveFactorScore()
        )
        assert result.gaps == []
        assert result.priority_list == []

    def test_result_with_gaps(self):
        """Result with alignment gaps."""
        gap = AlignmentGap(
            category="testing",
            severity=Severity.HIGH,
            description="No tests",
            current_state="0 tests",
            desired_state="80% coverage",
            fix_steps=["Add tests"]
        )
        result = AssessmentResult(
            project_md=ProjectMdDraft(),
            twelve_factor_score=TwelveFactorScore(),
            gaps=[gap],
            priority_list=[gap]
        )
        assert len(result.gaps) == 1
        assert len(result.priority_list) == 1

    def test_to_dict(self):
        """Convert result to dictionary."""
        draft = ProjectMdDraft(sections={"GOALS": "Build"}, confidence=0.5)
        score = TwelveFactorScore(factors={"codebase": 10})
        gap = AlignmentGap(
            category="testing",
            severity=Severity.HIGH,
            description="No tests",
            current_state="None",
            desired_state="Tests",
            fix_steps=["Add"],
            impact_score=80,
            effort_hours=2.0
        )
        result = AssessmentResult(
            project_md=draft,
            twelve_factor_score=score,
            gaps=[gap],
            priority_list=[gap]
        )

        d = result.to_dict()
        assert "project_md" in d
        assert d["project_md"]["confidence"] == 0.5
        assert "twelve_factor_score" in d
        assert d["twelve_factor_score"]["total_score"] == 10
        assert "gaps" in d
        assert len(d["gaps"]) == 1
        assert d["gaps"][0]["severity"] == "HIGH"


class TestAlignmentAssessor:
    """Test AlignmentAssessor class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        # Create README
        (project_dir / "README.md").write_text("# Test Project\n## Goals\nBuild something")
        # Create a Python file
        (project_dir / "main.py").write_text("print('hello')")
        return project_dir

    @pytest.fixture
    def mock_analysis(self):
        """Create mock AnalysisReport."""
        mock = MagicMock()
        mock.tech_stack = MagicMock()
        mock.tech_stack.primary_language = "python"
        mock.tech_stack.framework = "flask"
        mock.tech_stack.package_manager = "pip"
        mock.tech_stack.dependencies = {"flask", "pytest"}
        mock.tech_stack.test_framework = "pytest"
        mock.structure = MagicMock()
        mock.structure.total_files = 10
        mock.structure.source_files = 8
        mock.structure.test_files = 2
        mock.structure.doc_files = 1
        mock.structure.has_src_dir = True
        mock.structure.config_files = [".env", ".github/workflows/ci.yml"]
        return mock

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_assessor_init(self, mock_audit, mock_validate, temp_project):
        """Initialize assessor with valid project."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)
        assert assessor.project_root == temp_project
        mock_validate.assert_called_once()

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_assess_requires_analysis(self, mock_audit, mock_validate, temp_project):
        """Assess should require analysis input."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)

        with pytest.raises(ValueError, match="Analysis result required"):
            assessor.assess(None)

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_assess_returns_result(self, mock_audit, mock_validate, temp_project, mock_analysis):
        """Assess should return AssessmentResult."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)

        result = assessor.assess(mock_analysis)

        assert isinstance(result, AssessmentResult)
        assert isinstance(result.project_md, ProjectMdDraft)
        assert isinstance(result.twelve_factor_score, TwelveFactorScore)

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_generate_project_md(self, mock_audit, mock_validate, temp_project, mock_analysis):
        """Generate PROJECT.md draft from analysis."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)

        draft = assessor.generate_project_md(mock_analysis)

        assert isinstance(draft, ProjectMdDraft)
        assert "SCOPE" in draft.sections
        assert "python" in draft.sections["SCOPE"].lower()

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_calculate_twelve_factor_score(self, mock_audit, mock_validate, temp_project, mock_analysis):
        """Calculate 12-factor compliance score."""
        mock_validate.return_value = str(temp_project)
        # Create .git directory
        (temp_project / ".git").mkdir()

        assessor = AlignmentAssessor(temp_project)

        score = assessor.calculate_twelve_factor_score(mock_analysis)

        assert isinstance(score, TwelveFactorScore)
        assert "codebase" in score.factors
        assert score.factors["codebase"] == 10  # Has .git

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_identify_alignment_gaps_missing_project_md(self, mock_audit, mock_validate, temp_project, mock_analysis):
        """Identify gap when PROJECT.md is missing."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)
        score = TwelveFactorScore(factors={"codebase": 10})

        gaps = assessor.identify_alignment_gaps(mock_analysis, score)

        # Should find missing PROJECT.md
        project_md_gap = next((g for g in gaps if "PROJECT.md" in g.description), None)
        assert project_md_gap is not None
        assert project_md_gap.severity == Severity.CRITICAL

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_identify_alignment_gaps_no_tests(self, mock_audit, mock_validate, temp_project, mock_analysis):
        """Identify gap when no tests exist."""
        mock_validate.return_value = str(temp_project)
        mock_analysis.structure.test_files = 0
        assessor = AlignmentAssessor(temp_project)
        score = TwelveFactorScore(factors={"codebase": 10})

        gaps = assessor.identify_alignment_gaps(mock_analysis, score)

        # Should find missing tests
        test_gap = next((g for g in gaps if g.category == "testing" and "No test files" in g.description), None)
        assert test_gap is not None
        assert test_gap.severity == Severity.HIGH

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_prioritize_gaps(self, mock_audit, mock_validate, temp_project):
        """Prioritize gaps by impact/effort ratio."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)

        gaps = [
            AlignmentGap(
                category="a",
                severity=Severity.LOW,
                description="Low priority",
                current_state="",
                desired_state="",
                fix_steps=[],
                impact_score=10,
                effort_hours=10
            ),
            AlignmentGap(
                category="b",
                severity=Severity.CRITICAL,
                description="High priority",
                current_state="",
                desired_state="",
                fix_steps=[],
                impact_score=100,
                effort_hours=1
            ),
        ]

        prioritized = assessor.prioritize_gaps(gaps)

        # Critical should come first
        assert prioritized[0].severity == Severity.CRITICAL
        assert prioritized[0].category == "b"

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_twelve_factor_no_git(self, mock_audit, mock_validate, temp_project, mock_analysis):
        """Low score when no .git directory."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)

        score = assessor.calculate_twelve_factor_score(mock_analysis)

        assert score.factors["codebase"] == 3  # No .git = low score

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_twelve_factor_with_docker(self, mock_audit, mock_validate, temp_project, mock_analysis):
        """Higher dev/prod parity with Docker."""
        mock_validate.return_value = str(temp_project)
        mock_analysis.structure.config_files = ["Dockerfile"]
        assessor = AlignmentAssessor(temp_project)

        score = assessor.calculate_twelve_factor_score(mock_analysis)

        assert score.factors["dev_prod_parity"] == 9  # Has Docker


class TestAlignmentAssessorEdgeCases:
    """Test edge cases for AlignmentAssessor."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create minimal temp project."""
        project_dir = tmp_path / "edge_case_project"
        project_dir.mkdir()
        return project_dir

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_assess_with_empty_tech_stack(self, mock_audit, mock_validate, temp_project):
        """Handle analysis with no tech stack detected."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)

        mock_analysis = MagicMock()
        mock_analysis.tech_stack = MagicMock()
        mock_analysis.tech_stack.primary_language = None
        mock_analysis.tech_stack.framework = None
        mock_analysis.tech_stack.package_manager = None
        mock_analysis.tech_stack.dependencies = set()
        mock_analysis.tech_stack.test_framework = None
        mock_analysis.structure = MagicMock()
        mock_analysis.structure.total_files = 0
        mock_analysis.structure.source_files = 0
        mock_analysis.structure.test_files = 0
        mock_analysis.structure.doc_files = 0
        mock_analysis.structure.has_src_dir = False
        mock_analysis.structure.config_files = []

        result = assessor.assess(mock_analysis)

        assert isinstance(result, AssessmentResult)

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_low_test_coverage_gap(self, mock_audit, mock_validate, temp_project):
        """Detect insufficient test coverage gap."""
        mock_validate.return_value = str(temp_project)
        assessor = AlignmentAssessor(temp_project)

        mock_analysis = MagicMock()
        mock_analysis.tech_stack = MagicMock()
        mock_analysis.tech_stack.primary_language = "python"
        mock_analysis.tech_stack.framework = None
        mock_analysis.tech_stack.package_manager = "pip"
        mock_analysis.tech_stack.dependencies = set()
        mock_analysis.structure = MagicMock()
        mock_analysis.structure.total_files = 100
        mock_analysis.structure.source_files = 80
        mock_analysis.structure.test_files = 10  # Low ratio
        mock_analysis.structure.doc_files = 2
        mock_analysis.structure.has_src_dir = False
        mock_analysis.structure.config_files = []

        score = TwelveFactorScore(factors={"codebase": 10})
        gaps = assessor.identify_alignment_gaps(mock_analysis, score)

        # Should find insufficient coverage
        coverage_gap = next((g for g in gaps if "Insufficient test coverage" in g.description), None)
        assert coverage_gap is not None
        assert coverage_gap.severity == Severity.MEDIUM

    @patch('plugins.autonomous_dev.lib.alignment_assessor.validate_path')
    @patch('plugins.autonomous_dev.lib.alignment_assessor.audit_log')
    def test_extract_goals_from_readme(self, mock_audit, mock_validate, temp_project):
        """Extract goals section from README."""
        mock_validate.return_value = str(temp_project)
        (temp_project / "README.md").write_text("# Project\n## Goals\nBuild awesome things")

        assessor = AlignmentAssessor(temp_project)

        mock_analysis = MagicMock()
        mock_analysis.tech_stack = MagicMock()
        mock_analysis.tech_stack.primary_language = "python"
        mock_analysis.tech_stack.framework = None
        mock_analysis.tech_stack.package_manager = None
        mock_analysis.tech_stack.dependencies = set()
        mock_analysis.structure = MagicMock()
        mock_analysis.structure.total_files = 1
        mock_analysis.structure.source_files = 1
        mock_analysis.structure.test_files = 0
        mock_analysis.structure.doc_files = 1

        draft = assessor.generate_project_md(mock_analysis)

        assert "GOALS" in draft.sections


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
