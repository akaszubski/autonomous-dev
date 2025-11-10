"""
Unit tests for alignment_assessor.py - Phase 2: 12-Factor compliance assessment.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- PROJECT.md generation from analysis
- 12-Factor scoring (all 12 factors)
- Gap identification with severity
- Gap prioritization algorithm
- Assessment report format
- Edge case: Already compliant project
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# THESE IMPORTS WILL FAIL - Implementation doesn't exist yet
from plugins.autonomous_dev.lib.alignment_assessor import (
    AlignmentAssessor,
    AssessmentReport,
    ComplianceGap,
    GapSeverity,
    TwelveFactorScore,
)
from plugins.autonomous_dev.lib.codebase_analyzer import AnalysisReport, TechStack


class TestTwelveFactorScoring:
    """Test 12-Factor App compliance scoring."""

    @pytest.fixture
    def sample_analysis(self):
        """Create sample analysis report."""
        return AnalysisReport(
            tech_stacks=[TechStack.PYTHON],
            primary_language="python",
            total_files=50,
            total_lines=2500,
            has_tests=True,
            has_ci_cd=True,
            structure_type="organized",
        )

    @pytest.fixture
    def assessor(self, sample_analysis):
        """Create AlignmentAssessor instance."""
        return AlignmentAssessor(analysis_report=sample_analysis)

    def test_factor_1_codebase_single_repo(self, assessor):
        """Test Factor I: Codebase - One codebase tracked in revision control."""
        # Mock git repository detection
        with patch.object(assessor, "_detect_git_repo", return_value=True):
            score = assessor.score_factor_codebase()

        assert score.factor_number == 1
        assert score.factor_name == "Codebase"
        assert score.score >= 80  # Has git
        assert score.compliant is True

    def test_factor_2_dependencies_explicit(self, assessor):
        """Test Factor II: Dependencies - Explicitly declare and isolate dependencies."""
        # Mock dependency files detection
        with patch.object(
            assessor,
            "_detect_dependency_files",
            return_value=["requirements.txt", "pyproject.toml"],
        ):
            score = assessor.score_factor_dependencies()

        assert score.factor_number == 2
        assert score.factor_name == "Dependencies"
        assert score.score >= 80
        assert "requirements.txt" in score.evidence

    def test_factor_3_config_environment(self, assessor):
        """Test Factor III: Config - Store config in the environment."""
        # Mock environment config detection
        with patch.object(assessor, "_detect_env_config", return_value=True):
            score = assessor.score_factor_config()

        assert score.factor_number == 3
        assert score.factor_name == "Config"
        assert score.score >= 60  # Has .env support

    def test_factor_4_backing_services(self, assessor):
        """Test Factor IV: Backing services - Treat backing services as attached resources."""
        # Mock service configuration detection
        with patch.object(
            assessor, "_detect_service_config", return_value=["database", "cache"]
        ):
            score = assessor.score_factor_backing_services()

        assert score.factor_number == 4
        assert score.factor_name == "Backing services"

    def test_factor_5_build_release_run(self, assessor):
        """Test Factor V: Build, release, run - Strictly separate build and run stages."""
        # Mock CI/CD pipeline detection
        with patch.object(assessor, "_detect_build_pipeline", return_value=True):
            score = assessor.score_factor_build_release_run()

        assert score.factor_number == 5
        assert score.factor_name == "Build, release, run"
        assert score.score >= 70  # Has CI/CD

    def test_factor_6_processes_stateless(self, assessor):
        """Test Factor VI: Processes - Execute the app as one or more stateless processes."""
        # Mock stateless architecture detection
        with patch.object(assessor, "_detect_stateless_design", return_value=False):
            score = assessor.score_factor_processes()

        assert score.factor_number == 6
        assert score.factor_name == "Processes"
        # May score low if stateful detected

    def test_factor_7_port_binding(self, assessor):
        """Test Factor VII: Port binding - Export services via port binding."""
        # Mock port binding detection (web framework)
        with patch.object(
            assessor, "_detect_port_binding", return_value={"flask": True}
        ):
            score = assessor.score_factor_port_binding()

        assert score.factor_number == 7
        assert score.factor_name == "Port binding"

    def test_factor_8_concurrency(self, assessor):
        """Test Factor VIII: Concurrency - Scale out via the process model."""
        # Mock concurrency model detection
        with patch.object(assessor, "_detect_concurrency_model", return_value="threads"):
            score = assessor.score_factor_concurrency()

        assert score.factor_number == 8
        assert score.factor_name == "Concurrency"

    def test_factor_9_disposability(self, assessor):
        """Test Factor IX: Disposability - Maximize robustness with fast startup and graceful shutdown."""
        # Mock disposability patterns detection
        with patch.object(
            assessor, "_detect_disposability_patterns", return_value=False
        ):
            score = assessor.score_factor_disposability()

        assert score.factor_number == 9
        assert score.factor_name == "Disposability"

    def test_factor_10_dev_prod_parity(self, assessor):
        """Test Factor X: Dev/prod parity - Keep development, staging, and production as similar as possible."""
        # Mock dev/prod parity detection
        with patch.object(assessor, "_detect_dev_prod_parity", return_value=True):
            score = assessor.score_factor_dev_prod_parity()

        assert score.factor_number == 10
        assert score.factor_name == "Dev/prod parity"
        assert score.score >= 60

    def test_factor_11_logs_event_streams(self, assessor):
        """Test Factor XI: Logs - Treat logs as event streams."""
        # Mock logging configuration detection
        with patch.object(assessor, "_detect_logging_config", return_value=True):
            score = assessor.score_factor_logs()

        assert score.factor_number == 11
        assert score.factor_name == "Logs"

    def test_factor_12_admin_processes(self, assessor):
        """Test Factor XII: Admin processes - Run admin/management tasks as one-off processes."""
        # Mock admin process detection
        with patch.object(
            assessor, "_detect_admin_processes", return_value=["manage.py", "scripts/"]
        ):
            score = assessor.score_factor_admin_processes()

        assert score.factor_number == 12
        assert score.factor_name == "Admin processes"

    def test_calculate_overall_score(self, assessor):
        """Test calculating overall 12-Factor compliance score."""
        assessment = assessor.assess()

        assert 0 <= assessment.overall_score <= 100
        assert len(assessment.factor_scores) == 12

    def test_compliant_threshold_80_percent(self, assessor):
        """Test compliant threshold is 80% or higher."""
        assessment = assessor.assess()

        for factor_score in assessment.factor_scores:
            if factor_score.score >= 80:
                assert factor_score.compliant is True
            else:
                assert factor_score.compliant is False


class TestGapIdentification:
    """Test compliance gap identification."""

    @pytest.fixture
    def low_score_analysis(self):
        """Create analysis report with low compliance."""
        return AnalysisReport(
            tech_stacks=[TechStack.PYTHON],
            primary_language="python",
            total_files=10,
            total_lines=500,
            has_tests=False,  # Gap
            has_ci_cd=False,  # Gap
            structure_type="flat",  # Gap
            has_env_config=False,  # Gap
        )

    @pytest.fixture
    def assessor(self, low_score_analysis):
        """Create assessor with low-compliance analysis."""
        return AlignmentAssessor(analysis_report=low_score_analysis)

    def test_identify_missing_tests_gap(self, assessor):
        """Test identifying missing tests as a gap."""
        assessment = assessor.assess()

        test_gap = next(
            (g for g in assessment.gaps if "test" in g.description.lower()), None
        )
        assert test_gap is not None
        assert test_gap.severity == GapSeverity.HIGH

    def test_identify_missing_ci_cd_gap(self, assessor):
        """Test identifying missing CI/CD as a gap."""
        assessment = assessor.assess()

        ci_gap = next(
            (g for g in assessment.gaps if "ci/cd" in g.description.lower()), None
        )
        assert ci_gap is not None
        assert ci_gap.severity in [GapSeverity.MEDIUM, GapSeverity.HIGH]

    def test_identify_flat_structure_gap(self, assessor):
        """Test identifying flat structure as a gap."""
        assessment = assessor.assess()

        structure_gap = next(
            (g for g in assessment.gaps if "structure" in g.description.lower()), None
        )
        assert structure_gap is not None

    def test_identify_config_management_gap(self, assessor):
        """Test identifying config management gap."""
        assessment = assessor.assess()

        config_gap = next(
            (g for g in assessment.gaps if "config" in g.description.lower()), None
        )
        assert config_gap is not None

    def test_gap_includes_affected_factors(self, assessor):
        """Test gap includes affected 12-Factor factors."""
        assessment = assessor.assess()

        for gap in assessment.gaps:
            assert len(gap.affected_factors) > 0
            assert all(1 <= f <= 12 for f in gap.affected_factors)

    def test_gap_includes_remediation_steps(self, assessor):
        """Test gap includes remediation steps."""
        assessment = assessor.assess()

        for gap in assessment.gaps:
            assert len(gap.remediation_steps) > 0
            assert all(isinstance(step, str) for step in gap.remediation_steps)

    def test_gap_severity_levels(self, assessor):
        """Test gap severity levels are assigned correctly."""
        assessment = assessor.assess()

        severities = {gap.severity for gap in assessment.gaps}
        assert GapSeverity.HIGH in severities  # Missing tests
        assert len(severities) >= 2  # Multiple severity levels


class TestGapPrioritization:
    """Test gap prioritization algorithm."""

    @pytest.fixture
    def multiple_gaps(self):
        """Create multiple gaps with different priorities."""
        return [
            ComplianceGap(
                id="gap1",
                description="Missing tests",
                severity=GapSeverity.HIGH,
                affected_factors=[5, 9, 10],
                impact_score=90,
            ),
            ComplianceGap(
                id="gap2",
                description="No CI/CD",
                severity=GapSeverity.MEDIUM,
                affected_factors=[5],
                impact_score=60,
            ),
            ComplianceGap(
                id="gap3",
                description="Flat structure",
                severity=GapSeverity.LOW,
                affected_factors=[1],
                impact_score=30,
            ),
        ]

    def test_prioritize_by_severity(self, multiple_gaps):
        """Test gaps are prioritized by severity."""
        assessor = AlignmentAssessor(analysis_report=Mock())
        prioritized = assessor.prioritize_gaps(multiple_gaps)

        # HIGH severity should come first
        assert prioritized[0].severity == GapSeverity.HIGH
        assert prioritized[-1].severity == GapSeverity.LOW

    def test_prioritize_by_impact_score(self, multiple_gaps):
        """Test gaps with same severity prioritized by impact."""
        # Add another HIGH severity gap
        multiple_gaps.append(
            ComplianceGap(
                id="gap4",
                description="Security issue",
                severity=GapSeverity.HIGH,
                affected_factors=[2, 3],
                impact_score=95,  # Higher impact
            )
        )

        assessor = AlignmentAssessor(analysis_report=Mock())
        prioritized = assessor.prioritize_gaps(multiple_gaps)

        # Within HIGH severity, higher impact comes first
        high_gaps = [g for g in prioritized if g.severity == GapSeverity.HIGH]
        assert high_gaps[0].impact_score >= high_gaps[-1].impact_score

    def test_prioritize_by_affected_factors_count(self, multiple_gaps):
        """Test gaps affecting more factors prioritized higher."""
        assessor = AlignmentAssessor(analysis_report=Mock())
        prioritized = assessor.prioritize_gaps(multiple_gaps)

        # gap1 affects 3 factors, gap2 affects 1
        gap1 = next(g for g in prioritized if g.id == "gap1")
        gap2 = next(g for g in prioritized if g.id == "gap2")
        assert prioritized.index(gap1) < prioritized.index(gap2)

    def test_calculate_gap_impact_score(self):
        """Test impact score calculation."""
        gap = ComplianceGap(
            id="gap1",
            description="Major issue",
            severity=GapSeverity.HIGH,
            affected_factors=[1, 2, 3, 4],  # 4 factors
            remediation_steps=["step1", "step2"],  # 2 steps
        )

        assessor = AlignmentAssessor(analysis_report=Mock())
        impact = assessor.calculate_impact_score(gap)

        # High severity + many factors = high impact
        assert impact >= 70


class TestProjectMdGeneration:
    """Test PROJECT.md generation from analysis."""

    @pytest.fixture
    def assessor(self):
        """Create assessor with sample analysis."""
        analysis = AnalysisReport(
            tech_stacks=[TechStack.PYTHON, TechStack.JAVASCRIPT],
            primary_language="python",
            total_files=100,
            total_lines=5000,
            has_tests=True,
            has_ci_cd=True,
            structure_type="organized",
        )
        return AlignmentAssessor(analysis_report=analysis)

    def test_generate_project_md_structure(self, assessor):
        """Test generated PROJECT.md has correct structure."""
        project_md = assessor.generate_project_md()

        assert "## GOALS" in project_md
        assert "## SCOPE" in project_md
        assert "## CONSTRAINTS" in project_md
        assert "## ARCHITECTURE" in project_md

    def test_include_tech_stack_in_architecture(self, assessor):
        """Test tech stack included in ARCHITECTURE section."""
        project_md = assessor.generate_project_md()

        assert "Python" in project_md
        assert "JavaScript" in project_md

    def test_include_project_metrics(self, assessor):
        """Test project metrics included."""
        project_md = assessor.generate_project_md()

        assert "100 files" in project_md or "100" in project_md
        assert "5000 lines" in project_md or "5000" in project_md

    def test_include_current_state(self, assessor):
        """Test current state assessment included."""
        assessment = assessor.assess()
        project_md = assessor.generate_project_md(assessment=assessment)

        # Should mention compliance score
        assert "compliance" in project_md.lower()

    def test_include_improvement_goals(self, assessor):
        """Test improvement goals based on gaps."""
        assessment = assessor.assess()
        project_md = assessor.generate_project_md(assessment=assessment)

        # Should list gaps as goals
        for gap in assessment.gaps[:3]:  # Top 3 gaps
            # Gap description should appear in goals
            assert any(
                word in project_md.lower()
                for word in gap.description.lower().split()[:3]
            )

    def test_save_project_md_to_file(self, assessor, tmp_path):
        """Test saving generated PROJECT.md to file."""
        output_path = tmp_path / ".claude" / "PROJECT.md"
        assessor.save_project_md(output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "## GOALS" in content


class TestAssessmentReport:
    """Test assessment report generation."""

    @pytest.fixture
    def sample_assessment(self):
        """Create sample assessment report."""
        return AssessmentReport(
            overall_score=65.5,
            factor_scores=[
                TwelveFactorScore(
                    factor_number=1,
                    factor_name="Codebase",
                    score=90,
                    compliant=True,
                    evidence=["Git repository detected"],
                )
            ],
            gaps=[
                ComplianceGap(
                    id="gap1",
                    description="Missing tests",
                    severity=GapSeverity.HIGH,
                    affected_factors=[5],
                    remediation_steps=["Add pytest", "Write unit tests"],
                )
            ],
            recommendations=["Improve test coverage", "Add CI/CD pipeline"],
        )

    def test_report_to_dict(self, sample_assessment):
        """Test converting assessment to dictionary."""
        data = sample_assessment.to_dict()

        assert isinstance(data, dict)
        assert data["overall_score"] == 65.5
        assert len(data["factor_scores"]) == 1
        assert len(data["gaps"]) == 1

    def test_report_to_json(self, sample_assessment):
        """Test converting assessment to JSON."""
        json_str = sample_assessment.to_json()

        assert isinstance(json_str, str)
        assert "65.5" in json_str
        assert "Codebase" in json_str

    def test_generate_summary(self, sample_assessment):
        """Test generating human-readable summary."""
        summary = sample_assessment.generate_summary()

        assert "65.5" in summary or "66" in summary
        assert "1 gap" in summary.lower()
        assert "HIGH" in summary or "high" in summary

    def test_report_includes_compliance_badge(self, sample_assessment):
        """Test report includes compliance badge/indicator."""
        summary = sample_assessment.generate_summary()

        # Score < 80 = not fully compliant
        assert "compliant" in summary.lower()

    def test_fully_compliant_report(self):
        """Test report for fully compliant project."""
        assessment = AssessmentReport(
            overall_score=95.0,
            factor_scores=[],
            gaps=[],  # No gaps
            recommendations=["Maintain current practices"],
        )

        summary = assessment.generate_summary()
        assert "compliant" in summary.lower()
        assert assessment.is_fully_compliant is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_already_compliant_project(self):
        """Test assessing already compliant project."""
        analysis = AnalysisReport(
            tech_stacks=[TechStack.PYTHON],
            primary_language="python",
            total_files=100,
            total_lines=5000,
            has_tests=True,
            has_ci_cd=True,
            has_env_config=True,
            structure_type="organized",
            has_logging=True,
            has_dependency_management=True,
        )

        assessor = AlignmentAssessor(analysis_report=analysis)
        assessment = assessor.assess()

        # Should have high score, few/no gaps
        assert assessment.overall_score >= 80
        assert len(assessment.gaps) <= 2

    def test_minimal_project_assessment(self):
        """Test assessing minimal project with few features."""
        analysis = AnalysisReport(
            tech_stacks=[TechStack.PYTHON],
            primary_language="python",
            total_files=1,
            total_lines=10,
            has_tests=False,
            has_ci_cd=False,
            structure_type="flat",
        )

        assessor = AlignmentAssessor(analysis_report=analysis)
        assessment = assessor.assess()

        # Should have many gaps
        assert assessment.overall_score < 50
        assert len(assessment.gaps) >= 5

    def test_invalid_analysis_report(self):
        """Test handling invalid analysis report."""
        with pytest.raises(ValueError, match="Invalid analysis report"):
            AlignmentAssessor(analysis_report=None)

    def test_empty_gaps_list(self):
        """Test handling empty gaps list."""
        assessor = AlignmentAssessor(analysis_report=Mock())
        prioritized = assessor.prioritize_gaps([])

        assert prioritized == []
