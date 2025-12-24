"""
Integration tests for /align-project-retrofit workflow - End-to-end testing.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- End-to-end workflow (all 5 phases)
- Phase interdependency verification
- State persistence and resume
- Rollback scenario
- Interactive mode with mocked input
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# THESE IMPORTS WILL FAIL - Implementation doesn't exist yet
from plugins.autonomous_dev.lib.alignment_assessor import AlignmentAssessor
from plugins.autonomous_dev.lib.brownfield_retrofit import (
    BrownfieldRetrofit,
    RetrofitPhase,
)
from plugins.autonomous_dev.lib.codebase_analyzer import CodebaseAnalyzer
from plugins.autonomous_dev.lib.migration_planner import MigrationPlanner
from plugins.autonomous_dev.lib.retrofit_executor import ExecutionMode, RetrofitExecutor
from plugins.autonomous_dev.lib.retrofit_verifier import RetrofitVerifier


class TestEndToEndWorkflow:
    """Test complete end-to-end workflow."""

    @pytest.fixture
    def brownfield_project(self, tmp_path):
        """Create sample brownfield project."""
        project = tmp_path / "brownfield-app"
        project.mkdir()

        # Create typical brownfield structure
        (project / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
        (project / "utils.py").write_text("def helper(): pass\n")
        (project / "config.py").write_text("DEBUG = True\n")
        (project / "requirements.txt").write_text("flask==2.0.0\n")
        (project / "README.md").write_text("# Old Project\n")

        return project

    @pytest.fixture
    def retrofit(self, brownfield_project):
        """Create BrownfieldRetrofit coordinator."""
        return BrownfieldRetrofit(project_root=brownfield_project)

    def test_complete_workflow_all_phases(self, retrofit, brownfield_project):
        """Test running complete workflow through all 5 phases."""
        # Phase 1: ANALYZE
        analyzer = CodebaseAnalyzer(project_root=brownfield_project)
        analysis = analyzer.analyze()
        retrofit.update_state(
            current_phase=RetrofitPhase.ASSESS,
            analysis_report=analysis.to_dict(),
        )

        assert analysis.primary_language == "python"
        assert analysis.total_files >= 3

        # Phase 2: ASSESS
        assessor = AlignmentAssessor(analysis_report=analysis)
        assessment = assessor.assess()
        retrofit.update_state(
            current_phase=RetrofitPhase.PLAN,
            assessment_report=assessment.to_dict(),
        )

        assert 0 <= assessment.overall_score <= 100
        assert len(assessment.gaps) > 0  # Brownfield will have gaps

        # Phase 3: PLAN
        planner = MigrationPlanner(assessment_report=assessment)
        plan = planner.generate_plan()
        retrofit.update_state(
            current_phase=RetrofitPhase.EXECUTE,
            migration_plan=plan.to_dict(),
        )

        assert len(plan.steps) > 0
        assert plan.total_effort_hours > 0

        # Phase 4: EXECUTE (dry run)
        executor = RetrofitExecutor(
            migration_plan=plan,
            project_root=brownfield_project,
            mode=ExecutionMode.DRY_RUN,
        )
        execution_result = executor.execute()
        retrofit.update_state(
            current_phase=RetrofitPhase.VERIFY,
            execution_results=execution_result.to_dict(),
        )

        assert execution_result.success is True
        assert execution_result.dry_run is True

        # Phase 5: VERIFY
        verifier = RetrofitVerifier(project_root=brownfield_project)
        verification = verifier.assess_readiness()
        retrofit.update_state(
            current_phase=RetrofitPhase.COMPLETE,
            verification_report=verification.to_dict(),
        )

        assert verification is not None
        assert hasattr(verification, "readiness_score")

    def test_workflow_phase_sequence(self, retrofit):
        """Test phases execute in correct sequence."""
        assert retrofit.state.current_phase == RetrofitPhase.NOT_STARTED

        # Can't skip to EXECUTE
        with pytest.raises(Exception):
            retrofit.execute_phase(RetrofitPhase.EXECUTE)

        # Must follow sequence
        retrofit.state.current_phase = RetrofitPhase.ANALYZE
        retrofit.complete_phase(RetrofitPhase.ANALYZE)
        assert retrofit.state.current_phase == RetrofitPhase.ASSESS

    def test_workflow_state_persistence(self, retrofit, brownfield_project):
        """Test workflow state persists across phases."""
        # Execute ANALYZE phase
        analyzer = CodebaseAnalyzer(project_root=brownfield_project)
        analysis = analyzer.analyze()
        retrofit.update_state(
            current_phase=RetrofitPhase.ASSESS,
            analysis_report=analysis.to_dict(),
        )

        # State should be saved
        state_file = brownfield_project / ".retrofit" / "state.json"
        assert state_file.exists()

        # Load state and verify
        loaded_state = retrofit.load_state()
        assert loaded_state.current_phase == RetrofitPhase.ASSESS
        assert loaded_state.analysis_report is not None

    def test_workflow_generates_artifacts(self, retrofit, brownfield_project):
        """Test workflow generates expected artifacts."""
        # Run through ASSESS phase
        analyzer = CodebaseAnalyzer(project_root=brownfield_project)
        analysis = analyzer.analyze()

        assessor = AlignmentAssessor(analysis_report=analysis)
        assessment = assessor.assess()

        # Generate PROJECT.md
        project_md_path = brownfield_project / ".claude" / "PROJECT.md"
        assessor.save_project_md(project_md_path)

        assert project_md_path.exists()
        content = project_md_path.read_text()
        assert "## GOALS" in content


class TestPhaseInterdependencies:
    """Test phase interdependencies and data flow."""

    @pytest.fixture
    def sample_project(self, tmp_path):
        """Create sample project."""
        project = tmp_path / "test-project"
        project.mkdir()
        (project / "main.py").write_text("print('hello')\n")
        return project

    def test_assess_phase_requires_analyze_output(self, sample_project):
        """Test ASSESS phase requires ANALYZE output."""
        # Can't assess without analysis
        with pytest.raises((ValueError, AttributeError)):
            assessor = AlignmentAssessor(analysis_report=None)

    def test_plan_phase_requires_assess_output(self, sample_project):
        """Test PLAN phase requires ASSESS output."""
        # Can't plan without assessment
        with pytest.raises((ValueError, AttributeError)):
            planner = MigrationPlanner(assessment_report=None)

    def test_execute_phase_requires_plan_output(self, sample_project):
        """Test EXECUTE phase requires PLAN output."""
        # Can't execute without plan
        with pytest.raises((ValueError, AttributeError)):
            executor = RetrofitExecutor(
                migration_plan=None, project_root=sample_project
            )

    def test_data_flows_through_phases(self, sample_project):
        """Test data flows correctly through all phases."""
        # ANALYZE produces analysis_report
        analyzer = CodebaseAnalyzer(project_root=sample_project)
        analysis = analyzer.analyze()
        assert hasattr(analysis, "primary_language")

        # ASSESS consumes analysis_report, produces assessment_report
        assessor = AlignmentAssessor(analysis_report=analysis)
        assessment = assessor.assess()
        assert hasattr(assessment, "gaps")

        # PLAN consumes assessment_report, produces migration_plan
        planner = MigrationPlanner(assessment_report=assessment)
        plan = planner.generate_plan()
        assert hasattr(plan, "steps")

        # EXECUTE consumes migration_plan, produces execution_result
        executor = RetrofitExecutor(
            migration_plan=plan,
            project_root=sample_project,
            mode=ExecutionMode.DRY_RUN,
        )
        result = executor.execute()
        assert hasattr(result, "success")

        # VERIFY operates on final project state
        verifier = RetrofitVerifier(project_root=sample_project)
        verification = verifier.assess_readiness()
        assert hasattr(verification, "is_ready")


class TestStateResume:
    """Test resuming workflow from saved state."""

    @pytest.fixture
    def project_with_partial_state(self, tmp_path):
        """Create project with partial completion state."""
        project = tmp_path / "partial-project"
        project.mkdir()

        # Create .retrofit directory and state
        retrofit_dir = project / ".retrofit"
        retrofit_dir.mkdir()

        state = {
            "current_phase": "PLAN",
            "completed_phases": ["ANALYZE", "ASSESS"],
            "analysis_report": {
                "primary_language": "python",
                "total_files": 10,
            },
            "assessment_report": {
                "overall_score": 65,
                "gaps": [{"id": "gap1", "description": "Missing tests"}],
            },
            "metadata": {"created_at": "2025-11-11T10:00:00"},
        }

        state_file = retrofit_dir / "state.json"
        state_file.write_text(json.dumps(state))

        return project

    def test_resume_from_saved_state(self, project_with_partial_state):
        """Test resuming workflow from saved state."""
        retrofit = BrownfieldRetrofit(project_root=project_with_partial_state)
        state = retrofit.load_state()

        assert state.current_phase == RetrofitPhase.PLAN
        assert len(state.completed_phases) == 2
        assert state.analysis_report is not None

    def test_resume_skips_completed_phases(self, project_with_partial_state):
        """Test resume skips already completed phases."""
        retrofit = BrownfieldRetrofit(project_root=project_with_partial_state)
        state = retrofit.load_state()

        # ANALYZE and ASSESS already complete
        assert RetrofitPhase.ANALYZE in state.completed_phases
        assert RetrofitPhase.ASSESS in state.completed_phases

        # Should start from PLAN
        assert state.current_phase == RetrofitPhase.PLAN

    def test_resume_preserves_previous_results(self, project_with_partial_state):
        """Test resume preserves results from previous phases."""
        retrofit = BrownfieldRetrofit(project_root=project_with_partial_state)
        state = retrofit.load_state()

        # Should have analysis and assessment results
        assert state.analysis_report["primary_language"] == "python"
        assert state.assessment_report["overall_score"] == 65

    def test_resume_after_crash(self, tmp_path):
        """Test resuming after unexpected crash."""
        project = tmp_path / "crashed-project"
        project.mkdir()

        # Start workflow
        retrofit1 = BrownfieldRetrofit(project_root=project)
        retrofit1.update_state(
            current_phase=RetrofitPhase.EXECUTE,
            analysis_report={"data": "analysis"},
        )

        # Simulate crash (create new instance)
        retrofit2 = BrownfieldRetrofit(project_root=project)
        state = retrofit2.load_state()

        # Should resume from EXECUTE
        assert state.current_phase == RetrofitPhase.EXECUTE
        assert state.analysis_report["data"] == "analysis"


class TestRollbackScenario:
    """Test rollback scenarios and error recovery."""

    @pytest.fixture
    def project_for_rollback(self, tmp_path):
        """Create project for rollback testing."""
        project = tmp_path / "rollback-project"
        project.mkdir()
        (project / "original.py").write_text("# Original code\n")
        return project

    def test_rollback_on_execution_failure(self, project_for_rollback):
        """Test rollback when execution fails."""
        from plugins.autonomous_dev.lib.migration_planner import (
            MigrationPlan,
            MigrationStep,
        )

        # Create plan with failing step
        plan = MigrationPlan(
            steps=[
                MigrationStep(
                    id="step1",
                    description="Will fail",
                    gap_id="gap1",
                    verification_criteria=["Impossible condition"],
                )
            ],
            total_effort_hours=1,
            estimated_duration_days=1,
        )

        executor = RetrofitExecutor(
            migration_plan=plan,
            project_root=project_for_rollback,
            mode=ExecutionMode.AUTO,
        )

        # Should create backup
        backup_path = executor.create_backup()
        assert backup_path.exists()

        # Execute (will fail)
        result = executor.execute()

        # Should rollback
        assert result.rolled_back is True
        assert (project_for_rollback / "original.py").exists()

    def test_rollback_restores_original_state(self, project_for_rollback):
        """Test rollback fully restores original state."""
        original_content = (project_for_rollback / "original.py").read_text()

        # Simulate failed migration
        executor = RetrofitExecutor(
            migration_plan=Mock(),
            project_root=project_for_rollback,
            mode=ExecutionMode.AUTO,
        )

        backup_path = executor.create_backup()
        (project_for_rollback / "original.py").write_text("# Modified\n")

        # Rollback
        executor.rollback()

        # Should restore original
        assert (project_for_rollback / "original.py").read_text() == original_content

    def test_rollback_failure_logged(self, project_for_rollback):
        """Test rollback failure is logged."""
        executor = RetrofitExecutor(
            migration_plan=Mock(), project_root=project_for_rollback
        )

        # Set invalid backup path
        executor.backup_path = project_for_rollback / "nonexistent"

        with patch("plugins.autonomous_dev.lib.security_utils.audit_log") as mock_log:
            try:
                executor.rollback()
            except Exception:
                pass

            # Should log rollback attempt
            mock_log.assert_called()


class TestInteractiveMode:
    """Test interactive mode with user prompts."""

    @pytest.fixture
    def interactive_project(self, tmp_path):
        """Create project for interactive testing."""
        project = tmp_path / "interactive"
        project.mkdir()
        (project / "main.py").write_text("print('test')\n")
        return project

    @patch("builtins.input")
    def test_step_by_step_mode_prompts_user(self, mock_input, interactive_project):
        """Test STEP_BY_STEP mode prompts for each step."""
        from plugins.autonomous_dev.lib.migration_planner import (
            MigrationPlan,
            MigrationStep,
        )

        plan = MigrationPlan(
            steps=[
                MigrationStep(
                    id="step1",
                    description="First step",
                    gap_id="gap1",
                    verification_criteria=["Done"],
                ),
                MigrationStep(
                    id="step2",
                    description="Second step",
                    gap_id="gap1",
                    verification_criteria=["Done"],
                ),
            ],
            total_effort_hours=2,
            estimated_duration_days=1,
        )

        mock_input.return_value = "y"  # Execute all steps

        executor = RetrofitExecutor(
            migration_plan=plan,
            project_root=interactive_project,
            mode=ExecutionMode.STEP_BY_STEP,
        )

        result = executor.execute()

        # Should prompt twice (once per step)
        assert mock_input.call_count >= 2

    @patch("builtins.input")
    def test_interactive_can_abort(self, mock_input, interactive_project):
        """Test interactive mode allows aborting."""
        from plugins.autonomous_dev.lib.migration_planner import (
            MigrationPlan,
            MigrationStep,
        )

        plan = MigrationPlan(
            steps=[
                MigrationStep(
                    id="step1",
                    description="Step",
                    gap_id="gap1",
                    verification_criteria=["Done"],
                )
            ],
            total_effort_hours=1,
            estimated_duration_days=1,
        )

        mock_input.return_value = "abort"  # Abort execution

        executor = RetrofitExecutor(
            migration_plan=plan,
            project_root=interactive_project,
            mode=ExecutionMode.STEP_BY_STEP,
        )

        result = executor.execute()

        assert result.aborted is True

    @patch("builtins.input")
    def test_interactive_shows_step_preview(self, mock_input, interactive_project):
        """Test interactive mode shows step preview."""
        from plugins.autonomous_dev.lib.migration_planner import (
            EffortLevel,
            ImpactLevel,
            MigrationPlan,
            MigrationStep,
        )

        step = MigrationStep(
            id="step1",
            description="Important step",
            gap_id="gap1",
            verification_criteria=["Done"],
            effort=EffortLevel.MEDIUM,
            impact=ImpactLevel.HIGH,
        )

        plan = MigrationPlan(
            steps=[step], total_effort_hours=10, estimated_duration_days=1
        )

        mock_input.return_value = "y"

        executor = RetrofitExecutor(
            migration_plan=plan,
            project_root=interactive_project,
            mode=ExecutionMode.STEP_BY_STEP,
        )

        with patch("builtins.print") as mock_print:
            executor.execute()

            # Should print step details
            printed_output = " ".join(
                str(call) for call in mock_print.call_args_list
            )
            assert "Important step" in printed_output or "step1" in printed_output


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    def test_corrupted_state_recovery(self, tmp_path):
        """Test recovery from corrupted state file."""
        project = tmp_path / "corrupted-project"
        project.mkdir()

        retrofit_dir = project / ".retrofit"
        retrofit_dir.mkdir()

        state_file = retrofit_dir / "state.json"
        state_file.write_text("{ invalid json }")

        # Should recover by creating new state
        retrofit = BrownfieldRetrofit(project_root=project)
        state = retrofit.load_state()

        assert state.current_phase == RetrofitPhase.NOT_STARTED

    def test_disk_full_during_backup(self, tmp_path):
        """Test handling disk full during backup."""
        project = tmp_path / "disk-full-project"
        project.mkdir()

        executor = RetrofitExecutor(migration_plan=Mock(), project_root=project)

        with patch("shutil.copytree", side_effect=OSError("No space left")):
            with pytest.raises(OSError, match="No space"):
                executor.create_backup()

    def test_permission_denied_during_execution(self, tmp_path):
        """Test handling permission denied during execution."""
        project = tmp_path / "no-permission-project"
        project.mkdir()
        project.chmod(0o444)  # Read-only

        try:
            from plugins.autonomous_dev.lib.migration_planner import (
                MigrationPlan,
                MigrationStep,
            )

            plan = MigrationPlan(
                steps=[
                    MigrationStep(
                        id="step1",
                        description="Create file",
                        gap_id="gap1",
                        verification_criteria=["File exists"],
                    )
                ],
                total_effort_hours=1,
                estimated_duration_days=1,
            )

            executor = RetrofitExecutor(
                migration_plan=plan, project_root=project, mode=ExecutionMode.AUTO
            )

            result = executor.execute()

            # Should handle gracefully
            assert result.success is False
        finally:
            project.chmod(0o755)  # Cleanup

    def test_timeout_during_verification(self, tmp_path):
        """Test handling timeout during verification."""
        project = tmp_path / "timeout-project"
        project.mkdir()

        verifier = RetrofitVerifier(project_root=project)

        with patch("subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)

            check = verifier.run_test_suite(timeout=60)

            assert check.status in [
                "WARNING",
                "FAIL",
            ]  # Should handle timeout gracefully
