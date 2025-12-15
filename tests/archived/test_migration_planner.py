"""
Unit tests for migration_planner.py - Phase 3: Migration plan generation.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- Step generation from gaps
- Effort estimation (XS/S/M/L/XL)
- Impact analysis
- Dependency detection
- Execution order optimization
- Edge case: No migration needed
"""

from unittest.mock import Mock

import pytest

# THESE IMPORTS WILL FAIL - Implementation doesn't exist yet
from plugins.autonomous_dev.lib.alignment_assessor import (
    AssessmentReport,
    ComplianceGap,
    GapSeverity,
)
from plugins.autonomous_dev.lib.migration_planner import (
    EffortLevel,
    ImpactLevel,
    MigrationPlan,
    MigrationPlanner,
    MigrationStep,
)


class TestMigrationStepGeneration:
    """Test migration step generation from gaps."""

    @pytest.fixture
    def sample_gaps(self):
        """Create sample compliance gaps."""
        return [
            ComplianceGap(
                id="gap1",
                description="Missing test suite",
                severity=GapSeverity.HIGH,
                affected_factors=[5, 9, 10],
                remediation_steps=[
                    "Install pytest",
                    "Create tests directory",
                    "Write initial tests",
                ],
            ),
            ComplianceGap(
                id="gap2",
                description="No CI/CD pipeline",
                severity=GapSeverity.MEDIUM,
                affected_factors=[5],
                remediation_steps=["Create .github/workflows", "Add CI configuration"],
            ),
        ]

    @pytest.fixture
    def planner(self, sample_gaps):
        """Create MigrationPlanner instance."""
        assessment = Mock(spec=AssessmentReport)
        assessment.gaps = sample_gaps
        return MigrationPlanner(assessment_report=assessment)

    def test_generate_step_for_each_remediation(self, planner):
        """Test generating migration step for each remediation action."""
        plan = planner.generate_plan()

        # gap1 has 3 remediation steps, gap2 has 2 = 5 total
        assert len(plan.steps) >= 5

    def test_step_includes_description(self, planner):
        """Test each step includes clear description."""
        plan = planner.generate_plan()

        for step in plan.steps:
            assert step.description
            assert len(step.description) > 10

    def test_step_links_to_source_gap(self, planner):
        """Test each step links back to source gap."""
        plan = planner.generate_plan()

        for step in plan.steps:
            assert step.gap_id in ["gap1", "gap2"]

    def test_step_includes_verification_criteria(self, planner):
        """Test each step includes verification criteria."""
        plan = planner.generate_plan()

        for step in plan.steps:
            assert len(step.verification_criteria) > 0

    def test_consolidate_duplicate_steps(self, planner):
        """Test duplicate steps are consolidated."""
        # Add gap with duplicate remediation
        gap3 = ComplianceGap(
            id="gap3",
            description="Another issue",
            severity=GapSeverity.LOW,
            affected_factors=[1],
            remediation_steps=["Install pytest"],  # Duplicate from gap1
        )
        planner.assessment_report.gaps.append(gap3)

        plan = planner.generate_plan()

        # "Install pytest" should appear only once
        pytest_steps = [s for s in plan.steps if "pytest" in s.description.lower()]
        assert len(pytest_steps) == 1

    def test_empty_gaps_produces_empty_plan(self):
        """Test empty gaps list produces empty migration plan."""
        assessment = Mock(spec=AssessmentReport)
        assessment.gaps = []
        planner = MigrationPlanner(assessment_report=assessment)

        plan = planner.generate_plan()

        assert len(plan.steps) == 0
        assert plan.is_empty is True


class TestEffortEstimation:
    """Test effort estimation for migration steps."""

    @pytest.fixture
    def planner(self):
        """Create planner instance."""
        assessment = Mock(spec=AssessmentReport)
        assessment.gaps = []
        return MigrationPlanner(assessment_report=assessment)

    def test_estimate_extra_small_effort(self, planner):
        """Test estimating XS effort (< 1 hour)."""
        step = MigrationStep(
            id="step1",
            description="Add .env file",
            gap_id="gap1",
            verification_criteria=["File exists"],
        )

        effort = planner.estimate_effort(step)

        assert effort == EffortLevel.EXTRA_SMALL
        assert effort.hours <= 1

    def test_estimate_small_effort(self, planner):
        """Test estimating S effort (1-4 hours)."""
        step = MigrationStep(
            id="step1",
            description="Create basic test suite",
            gap_id="gap1",
            verification_criteria=["Tests exist", "Tests pass"],
        )

        effort = planner.estimate_effort(step)

        assert effort == EffortLevel.SMALL
        assert 1 <= effort.hours <= 4

    def test_estimate_medium_effort(self, planner):
        """Test estimating M effort (4-16 hours)."""
        step = MigrationStep(
            id="step1",
            description="Refactor codebase for dependency injection",
            gap_id="gap1",
            verification_criteria=[
                "Dependencies injected",
                "Tests updated",
                "Documentation updated",
            ],
        )

        effort = planner.estimate_effort(step)

        assert effort == EffortLevel.MEDIUM
        assert 4 <= effort.hours <= 16

    def test_estimate_large_effort(self, planner):
        """Test estimating L effort (16-40 hours)."""
        step = MigrationStep(
            id="step1",
            description="Migrate from monolith to microservices",
            gap_id="gap1",
            verification_criteria=["Services separated", "API contracts defined"],
        )

        effort = planner.estimate_effort(step)

        assert effort == EffortLevel.LARGE
        assert 16 <= effort.hours <= 40

    def test_estimate_extra_large_effort(self, planner):
        """Test estimating XL effort (> 40 hours)."""
        step = MigrationStep(
            id="step1",
            description="Complete system rewrite",
            gap_id="gap1",
            verification_criteria=["All features reimplemented", "Full test coverage"],
        )

        effort = planner.estimate_effort(step)

        assert effort == EffortLevel.EXTRA_LARGE
        assert effort.hours > 40

    def test_effort_level_ordering(self):
        """Test effort levels are correctly ordered."""
        assert EffortLevel.EXTRA_SMALL < EffortLevel.SMALL
        assert EffortLevel.SMALL < EffortLevel.MEDIUM
        assert EffortLevel.MEDIUM < EffortLevel.LARGE
        assert EffortLevel.LARGE < EffortLevel.EXTRA_LARGE


class TestImpactAnalysis:
    """Test impact analysis for migration steps."""

    @pytest.fixture
    def planner(self):
        """Create planner instance."""
        assessment = Mock(spec=AssessmentReport)
        assessment.gaps = []
        return MigrationPlanner(assessment_report=assessment)

    def test_analyze_low_impact(self, planner):
        """Test analyzing low impact changes."""
        step = MigrationStep(
            id="step1",
            description="Add README.md",
            gap_id="gap1",
            verification_criteria=["File exists"],
        )

        impact = planner.analyze_impact(step)

        assert impact == ImpactLevel.LOW
        assert impact.risk_level == "low"

    def test_analyze_medium_impact(self, planner):
        """Test analyzing medium impact changes."""
        step = MigrationStep(
            id="step1",
            description="Reorganize file structure",
            gap_id="gap1",
            verification_criteria=["Files moved", "Imports updated"],
        )

        impact = planner.analyze_impact(step)

        assert impact == ImpactLevel.MEDIUM
        assert impact.risk_level == "medium"

    def test_analyze_high_impact(self, planner):
        """Test analyzing high impact changes."""
        step = MigrationStep(
            id="step1",
            description="Change database schema",
            gap_id="gap1",
            verification_criteria=["Schema migrated", "Data preserved"],
        )

        impact = planner.analyze_impact(step)

        assert impact == ImpactLevel.HIGH
        assert impact.risk_level == "high"

    def test_impact_includes_affected_areas(self, planner):
        """Test impact analysis includes affected areas."""
        step = MigrationStep(
            id="step1",
            description="Add authentication system",
            gap_id="gap1",
            verification_criteria=["Auth works"],
        )

        impact = planner.analyze_impact(step)

        assert len(impact.affected_areas) > 0
        assert any("security" in area.lower() for area in impact.affected_areas)

    def test_impact_includes_rollback_difficulty(self, planner):
        """Test impact includes rollback difficulty assessment."""
        step = MigrationStep(
            id="step1",
            description="Migrate database",
            gap_id="gap1",
            verification_criteria=["Migration complete"],
        )

        impact = planner.analyze_impact(step)

        assert hasattr(impact, "rollback_difficulty")
        assert impact.rollback_difficulty in ["easy", "medium", "hard"]


class TestDependencyDetection:
    """Test dependency detection between steps."""

    @pytest.fixture
    def planner(self):
        """Create planner with multiple steps."""
        assessment = Mock(spec=AssessmentReport)
        assessment.gaps = []
        return MigrationPlanner(assessment_report=assessment)

    @pytest.fixture
    def sample_steps(self):
        """Create sample migration steps with dependencies."""
        return [
            MigrationStep(
                id="step1",
                description="Create tests directory",
                gap_id="gap1",
                verification_criteria=["Directory exists"],
            ),
            MigrationStep(
                id="step2",
                description="Write unit tests in tests/",
                gap_id="gap1",
                verification_criteria=["Tests exist"],
            ),
            MigrationStep(
                id="step3",
                description="Run test suite",
                gap_id="gap1",
                verification_criteria=["Tests pass"],
            ),
        ]

    def test_detect_sequential_dependencies(self, planner, sample_steps):
        """Test detecting sequential dependencies."""
        dependencies = planner.detect_dependencies(sample_steps)

        # step2 depends on step1 (needs directory)
        assert "step1" in dependencies["step2"]
        # step3 depends on step2 (needs tests)
        assert "step2" in dependencies["step3"]

    def test_detect_parallel_steps(self, planner):
        """Test detecting steps that can run in parallel."""
        steps = [
            MigrationStep(
                id="step1",
                description="Add .env file",
                gap_id="gap1",
                verification_criteria=["File exists"],
            ),
            MigrationStep(
                id="step2",
                description="Add .gitignore",
                gap_id="gap2",
                verification_criteria=["File exists"],
            ),
        ]

        dependencies = planner.detect_dependencies(steps)

        # No dependencies - can run in parallel
        assert len(dependencies["step1"]) == 0
        assert len(dependencies["step2"]) == 0

    def test_detect_file_based_dependencies(self, planner):
        """Test detecting dependencies based on file operations."""
        steps = [
            MigrationStep(
                id="step1",
                description="Create pyproject.toml",
                gap_id="gap1",
                verification_criteria=["File exists"],
            ),
            MigrationStep(
                id="step2",
                description="Update dependencies in pyproject.toml",
                gap_id="gap1",
                verification_criteria=["Dependencies listed"],
            ),
        ]

        dependencies = planner.detect_dependencies(steps)

        # step2 depends on step1 (modifies file created by step1)
        assert "step1" in dependencies["step2"]

    def test_detect_circular_dependencies(self, planner):
        """Test detecting and preventing circular dependencies."""
        steps = [
            MigrationStep(
                id="step1",
                description="Configure service A to use service B",
                gap_id="gap1",
                verification_criteria=["A uses B"],
            ),
            MigrationStep(
                id="step2",
                description="Configure service B to use service A",
                gap_id="gap1",
                verification_criteria=["B uses A"],
            ),
        ]

        with pytest.raises(ValueError, match="Circular dependency detected"):
            planner.detect_dependencies(steps)


class TestExecutionOrderOptimization:
    """Test execution order optimization."""

    @pytest.fixture
    def planner(self):
        """Create planner instance."""
        assessment = Mock(spec=AssessmentReport)
        assessment.gaps = []
        return MigrationPlanner(assessment_report=assessment)

    @pytest.fixture
    def unordered_steps(self):
        """Create unordered steps with dependencies."""
        return [
            MigrationStep(
                id="step3",
                description="Run tests",
                gap_id="gap1",
                verification_criteria=["Tests pass"],
                dependencies=["step2"],
            ),
            MigrationStep(
                id="step1",
                description="Create directory",
                gap_id="gap1",
                verification_criteria=["Dir exists"],
                dependencies=[],
            ),
            MigrationStep(
                id="step2",
                description="Write tests",
                gap_id="gap1",
                verification_criteria=["Tests exist"],
                dependencies=["step1"],
            ),
        ]

    def test_optimize_execution_order(self, planner, unordered_steps):
        """Test optimizing execution order based on dependencies."""
        ordered = planner.optimize_execution_order(unordered_steps)

        # Should be: step1 -> step2 -> step3
        assert ordered[0].id == "step1"
        assert ordered[1].id == "step2"
        assert ordered[2].id == "step3"

    def test_group_parallel_steps(self, planner):
        """Test grouping steps that can run in parallel."""
        steps = [
            MigrationStep(
                id="step1",
                description="Task A",
                gap_id="gap1",
                verification_criteria=["Done"],
                dependencies=[],
            ),
            MigrationStep(
                id="step2",
                description="Task B",
                gap_id="gap2",
                verification_criteria=["Done"],
                dependencies=[],
            ),
            MigrationStep(
                id="step3",
                description="Task C (needs A and B)",
                gap_id="gap3",
                verification_criteria=["Done"],
                dependencies=["step1", "step2"],
            ),
        ]

        grouped = planner.group_parallel_steps(steps)

        # Should have 2 groups: [step1, step2] then [step3]
        assert len(grouped) == 2
        assert len(grouped[0]) == 2  # Parallel group
        assert len(grouped[1]) == 1  # Sequential

    def test_prioritize_high_impact_steps(self, planner):
        """Test prioritizing high-impact steps."""
        steps = [
            MigrationStep(
                id="step1",
                description="Low priority",
                gap_id="gap1",
                verification_criteria=["Done"],
                impact=ImpactLevel.LOW,
            ),
            MigrationStep(
                id="step2",
                description="High priority",
                gap_id="gap2",
                verification_criteria=["Done"],
                impact=ImpactLevel.HIGH,
            ),
        ]

        ordered = planner.optimize_execution_order(steps)

        # High impact should come first (when no dependencies)
        assert ordered[0].impact == ImpactLevel.HIGH


class TestMigrationPlan:
    """Test migration plan generation and operations."""

    @pytest.fixture
    def sample_plan(self):
        """Create sample migration plan."""
        return MigrationPlan(
            steps=[
                MigrationStep(
                    id="step1",
                    description="Create tests",
                    gap_id="gap1",
                    verification_criteria=["Tests exist"],
                    effort=EffortLevel.SMALL,
                    impact=ImpactLevel.MEDIUM,
                ),
                MigrationStep(
                    id="step2",
                    description="Add CI/CD",
                    gap_id="gap2",
                    verification_criteria=["Pipeline runs"],
                    effort=EffortLevel.MEDIUM,
                    impact=ImpactLevel.HIGH,
                ),
            ],
            total_effort_hours=20,
            estimated_duration_days=3,
        )

    def test_plan_to_dict(self, sample_plan):
        """Test converting plan to dictionary."""
        data = sample_plan.to_dict()

        assert isinstance(data, dict)
        assert len(data["steps"]) == 2
        assert data["total_effort_hours"] == 20

    def test_plan_to_json(self, sample_plan):
        """Test converting plan to JSON."""
        json_str = sample_plan.to_json()

        assert isinstance(json_str, str)
        assert "step1" in json_str
        assert "20" in json_str

    def test_calculate_total_effort(self, sample_plan):
        """Test calculating total effort from steps."""
        total = sample_plan.calculate_total_effort()

        # SMALL (4h) + MEDIUM (10h) = 14h
        assert total >= 14

    def test_estimate_duration_in_days(self, sample_plan):
        """Test estimating duration in calendar days."""
        duration = sample_plan.estimate_duration()

        # 20 hours / 8 hours per day = 2.5 days
        assert 2 <= duration <= 3

    def test_plan_summary_generation(self, sample_plan):
        """Test generating plan summary."""
        summary = sample_plan.generate_summary()

        assert "2 steps" in summary.lower()
        assert "20 hours" in summary.lower() or "20h" in summary.lower()

    def test_export_plan_to_markdown(self, sample_plan):
        """Test exporting plan to markdown format."""
        markdown = sample_plan.to_markdown()

        assert "# Migration Plan" in markdown
        assert "step1" in markdown
        assert "Create tests" in markdown

    def test_empty_plan(self):
        """Test empty migration plan."""
        plan = MigrationPlan(steps=[], total_effort_hours=0, estimated_duration_days=0)

        assert plan.is_empty is True
        assert plan.calculate_total_effort() == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_no_migration_needed(self):
        """Test handling case where no migration needed."""
        assessment = Mock(spec=AssessmentReport)
        assessment.gaps = []  # No gaps
        planner = MigrationPlanner(assessment_report=assessment)

        plan = planner.generate_plan()

        assert plan.is_empty is True
        assert len(plan.steps) == 0

    def test_invalid_assessment_report(self):
        """Test handling invalid assessment report."""
        with pytest.raises(ValueError, match="Invalid assessment report"):
            MigrationPlanner(assessment_report=None)

    def test_step_without_verification_criteria(self):
        """Test handling step without verification criteria."""
        step = MigrationStep(
            id="step1",
            description="Do something",
            gap_id="gap1",
            verification_criteria=[],  # Empty
        )

        with pytest.raises(ValueError, match="verification criteria"):
            step.validate()

    def test_extremely_complex_dependencies(self):
        """Test handling very complex dependency graph."""
        planner = MigrationPlanner(assessment_report=Mock())
        steps = [
            MigrationStep(
                id=f"step{i}",
                description=f"Task {i}",
                gap_id="gap1",
                verification_criteria=["Done"],
                dependencies=[f"step{j}" for j in range(max(0, i - 3), i)],
            )
            for i in range(20)
        ]

        # Should handle without errors
        ordered = planner.optimize_execution_order(steps)
        assert len(ordered) == 20
