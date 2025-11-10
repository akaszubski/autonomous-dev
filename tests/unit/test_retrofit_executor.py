"""
Unit tests for retrofit_executor.py - Phase 4: Migration execution with rollback.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- Backup creation with 0o700 permissions
- Atomic file changes
- Rollback on failure
- Execution modes (DRY_RUN, STEP_BY_STEP, AUTO)
- Step verification
- Edge cases: Backup fails, rollback fails
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import correct class names from implementation
from plugins.autonomous_dev.lib.migration_planner import (
    EffortSize,  # Changed from EffortLevel
    ImpactLevel,
    MigrationPlan,
    MigrationStep,
)
from plugins.autonomous_dev.lib.retrofit_executor import (
    ExecutionMode,
    ExecutionResult,
    RetrofitExecutor,
)
# Note: RollbackError and StepExecutionError don't exist in implementation
# Tests will need to be adapted to use standard exceptions (ValueError, RuntimeError, etc.)


class TestBackupCreation:
    """Test backup creation before execution."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "main.py").write_text("print('original')\n")
        (project / "config.py").write_text("DEBUG = True\n")
        return project

    @pytest.fixture
    def executor(self, temp_project):
        """Create RetrofitExecutor instance."""
        return RetrofitExecutor(project_root=temp_project)

    def test_create_backup_before_execution(self, executor, temp_project):
        """Test backup created before starting execution."""
        backup_path = executor.create_backup()

        assert backup_path.exists()
        assert backup_path.is_dir()

    def test_backup_has_secure_permissions(self, executor):
        """Test backup directory has 0o700 permissions."""
        backup_path = executor.create_backup()

        # Check permissions (owner read/write/execute only)
        assert oct(backup_path.stat().st_mode)[-3:] == "700"

    def test_backup_includes_all_project_files(self, executor, temp_project):
        """Test backup includes all project files."""
        backup_path = executor.create_backup()

        assert (backup_path / "main.py").exists()
        assert (backup_path / "config.py").exists()

    def test_backup_preserves_directory_structure(self, temp_project):
        """Test backup preserves directory structure."""
        src_dir = temp_project / "src"
        src_dir.mkdir()
        (src_dir / "utils.py").write_text("def util(): pass\n")

        executor = RetrofitExecutor(project_root=temp_project)

        backup_path = executor.create_backup()

        assert (backup_path / "src" / "utils.py").exists()

    def test_backup_path_is_timestamped(self, executor):
        """Test backup path includes timestamp."""
        backup_path = executor.create_backup()

        # Should be in format: /tmp/retrofit-backup-YYYYMMDD-HHMMSS
        assert "retrofit-backup-" in str(backup_path)

    def test_backup_excludes_ignored_files(self, executor, temp_project):
        """Test backup excludes .git, __pycache__, etc."""
        git_dir = temp_project / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("gitconfig\n")

        pycache = temp_project / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-39.pyc").write_bytes(b"bytecode")

        backup_path = executor.create_backup()

        # Should exclude .git and __pycache__
        assert not (backup_path / ".git").exists()
        assert not (backup_path / "__pycache__").exists()

    def test_backup_creation_failure_handling(self, executor, temp_project):
        """Test handling backup creation failure."""
        # Make project directory read-only
        temp_project.chmod(0o444)

        try:
            with pytest.raises(OSError, match="Permission denied"):
                executor.create_backup()
        finally:
            temp_project.chmod(0o755)  # Cleanup


class TestAtomicFileChanges:
    """Test atomic file change operations."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create executor instance."""
        return RetrofitExecutor(project_root=tmp_path)

    def test_atomic_file_write(self, executor, tmp_path):
        """Test atomic file write operation."""
        target_file = tmp_path / "test.txt"
        target_file.write_text("original\n")

        executor.atomic_write(target_file, "updated\n")

        assert target_file.read_text() == "updated\n"

    def test_atomic_write_uses_temp_file(self, executor, tmp_path):
        """Test atomic write uses temporary file."""
        target_file = tmp_path / "test.txt"

        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            executor.atomic_write(target_file, "content\n")
            mock_temp.assert_called_once()

    def test_atomic_write_preserves_on_failure(self, executor, tmp_path):
        """Test original file preserved if write fails."""
        target_file = tmp_path / "test.txt"
        target_file.write_text("original\n")

        # Simulate write failure
        with patch("pathlib.Path.rename", side_effect=OSError("Write failed")):
            with pytest.raises(OSError):
                executor.atomic_write(target_file, "updated\n")

        # Original content should be preserved
        assert target_file.read_text() == "original\n"

    def test_atomic_directory_creation(self, executor, tmp_path):
        """Test atomic directory creation."""
        new_dir = tmp_path / "tests"

        executor.atomic_mkdir(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_atomic_file_deletion(self, executor, tmp_path):
        """Test atomic file deletion."""
        target_file = tmp_path / "to_delete.txt"
        target_file.write_text("delete me\n")

        executor.atomic_delete(target_file)

        assert not target_file.exists()


class TestStepExecution:
    """Test migration step execution."""

    @pytest.fixture
    def sample_step(self):
        """Create sample migration step."""
        return MigrationStep(
            step_id="step1",  # Changed from id to step_id
            description="Create tests directory",
            gap_id="gap1",
            verification_criteria=["Directory exists", "Directory is writable"],
            effort=EffortSize.EXTRA_SMALL,  # Changed from EffortLevel to EffortSize
            impact=ImpactLevel.LOW,
        )

    @pytest.fixture
    def executor(self, tmp_path):
        """Create executor with sample step."""
        return RetrofitExecutor(project_root=tmp_path)

    def test_execute_single_step(self, executor, sample_step, tmp_path):
        """Test executing single migration step."""
        result = executor.execute_step(sample_step)

        assert result.success is True
        assert (tmp_path / "tests").exists()

    def test_step_verification_after_execution(self, executor, sample_step):
        """Test step verification runs after execution."""
        result = executor.execute_step(sample_step)

        # Should verify all criteria
        assert result.verified is True
        assert len(result.verification_results) == 2

    def test_step_execution_failure_handling(self, executor):
        """Test handling step execution failure."""
        failing_step = MigrationStep(
            step_id="step2",  # Changed from id to step_id
            description="Invalid operation",
            gap_id="gap1",
            verification_criteria=["Should fail"],
        )

        with pytest.raises(Exception):  # Changed from StepExecutionError (not implemented)
            executor.execute_step(failing_step)

    def test_step_execution_logs_progress(self, executor, sample_step):
        """Test step execution logs progress."""
        with patch("plugins.autonomous_dev.lib.retrofit_executor.audit_log") as mock_log:
            executor.execute_step(sample_step)

            # Should log start and completion
            assert mock_log.call_count >= 2

    def test_verification_failure_rolls_back_step(self, executor):
        """Test verification failure triggers step rollback."""
        step = MigrationStep(
            step_id="step1",  # Changed from id to step_id
            description="Create file",
            gap_id="gap1",
            verification_criteria=["File has 1000 lines"],  # Won't meet this
        )

        result = executor.execute_step(step)

        assert result.success is False
        assert result.rolled_back is True


class TestExecutionModes:
    """Test different execution modes."""

    @pytest.fixture
    def sample_plan(self):
        """Create sample migration plan."""
        return MigrationPlan(
            steps=[
                MigrationStep(
                    step_id="step1",  # Changed from id to step_id
                    description="Create directory",
                    gap_id="gap1",
                    verification_criteria=["Dir exists"],
                ),
                MigrationStep(
                    step_id="step2",  # Changed from id to step_id
                    description="Create file",
                    gap_id="gap1",
                    verification_criteria=["File exists"],
                ),
            ],
            total_effort_hours=2,
            estimated_duration_days=1,
        )

    def test_dry_run_mode_no_changes(self, sample_plan, tmp_path):
        """Test DRY_RUN mode makes no actual changes."""
        executor = RetrofitExecutor(project_root=tmp_path)

        result = executor.execute(plan=sample_plan, mode=ExecutionMode.DRY_RUN)

        # No directories/files should be created
        assert result.success is True
        assert result.dry_run is True
        assert not any(tmp_path.iterdir())

    def test_dry_run_mode_reports_planned_changes(self, sample_plan, tmp_path):
        """Test DRY_RUN mode reports what would be changed."""
        executor = RetrofitExecutor(project_root=tmp_path)

        result = executor.execute(plan=sample_plan, mode=ExecutionMode.DRY_RUN)

        assert len(result.planned_changes) == 2
        assert "Create directory" in result.planned_changes[0]

    def test_step_by_step_mode_prompts_confirmation(self, sample_plan, tmp_path):
        """Test STEP_BY_STEP mode prompts for each step."""
        executor = RetrofitExecutor(project_root=tmp_path)

        with patch("builtins.input", return_value="y"):
            result = executor.execute(plan=sample_plan, mode=ExecutionMode.STEP_BY_STEP)

        assert result.success is True

    def test_step_by_step_mode_can_skip_steps(self, sample_plan, tmp_path):
        """Test STEP_BY_STEP mode allows skipping steps."""
        executor = RetrofitExecutor(project_root=tmp_path)

        # Skip first step, execute second
        with patch("builtins.input", side_effect=["n", "y"]):
            result = executor.execute(plan=sample_plan, mode=ExecutionMode.STEP_BY_STEP)

        assert result.steps_skipped == 1
        assert result.steps_executed == 1

    def test_auto_mode_executes_all_steps(self, sample_plan, tmp_path):
        """Test AUTO mode executes all steps without prompts."""
        executor = RetrofitExecutor(project_root=tmp_path)

        result = executor.execute(plan=sample_plan, mode=ExecutionMode.AUTO)

        assert result.success is True
        assert result.steps_executed == 2
        assert result.steps_skipped == 0

    def test_auto_mode_stops_on_critical_failure(self, tmp_path):
        """Test AUTO mode stops on critical failure."""
        plan = MigrationPlan(
            steps=[
                MigrationStep(
            step_id="step1",
                    description="Will succeed",
                    gap_id="gap1",
                    verification_criteria=["Always true"],
                ),
                MigrationStep(
            step_id="step2",
                    description="Will fail critically",
                    gap_id="gap1",
                    verification_criteria=["Will fail"],
                    impact=ImpactLevel.HIGH,
                ),
                MigrationStep(
            step_id="step3",
                    description="Should not execute",
                    gap_id="gap1",
                    verification_criteria=["N/A"],
                ),
            ],
            total_effort_hours=3,
            estimated_duration_days=1,
        )

        executor = RetrofitExecutor(project_root=tmp_path)

        result = executor.execute(plan=plan, mode=ExecutionMode.AUTO)

        assert result.success is False
        assert result.steps_executed == 1  # Only first step
        assert result.critical_failure is True


class TestRollbackMechanism:
    """Test rollback mechanism on failure."""

    @pytest.fixture
    def project_with_backup(self, tmp_path):
        """Create project with backup."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "main.py").write_text("original\n")

        backup = tmp_path / "backup"
        backup.mkdir()
        (backup / "main.py").write_text("original\n")

        return project, backup

    @pytest.fixture
    def executor(self, project_with_backup):
        """Create executor with backup."""
        project, backup = project_with_backup
        executor = RetrofitExecutor(project_root=project)
        executor.backup_path = backup
        return executor

    def test_rollback_restores_backup(self, executor, project_with_backup):
        """Test rollback restores from backup."""
        project, backup = project_with_backup

        # Modify project file
        (project / "main.py").write_text("modified\n")

        # Rollback
        executor.rollback()

        # Should restore original content
        assert (project / "main.py").read_text() == "original\n"

    def test_rollback_on_execution_failure(self, tmp_path):
        """Test automatic rollback on execution failure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "main.py").write_text("original\n")

        plan = MigrationPlan(
            steps=[
                MigrationStep(
            step_id="step1",
                    description="Will fail",
                    gap_id="gap1",
                    verification_criteria=["Will not meet"],
                )
            ],
            total_effort_hours=1,
            estimated_duration_days=1,
        )

        executor = RetrofitExecutor(project_root=project)

        result = executor.execute(plan=plan, mode=ExecutionMode.AUTO)

        # Should rollback on failure
        assert result.rolled_back is True
        assert (project / "main.py").read_text() == "original\n"

    def test_rollback_logs_actions(self, executor):
        """Test rollback logs all actions."""
        with patch("plugins.autonomous_dev.lib.retrofit_executor.audit_log") as mock_log:
            executor.rollback()

            # Should log rollback operation
            mock_log.assert_called()

    def test_rollback_failure_handling(self, executor, project_with_backup):
        """Test handling rollback failure."""
        project, backup = project_with_backup

        # Delete backup to simulate failure
        import shutil

        shutil.rmtree(backup)

        with pytest.raises(Exception):  # Changed from RollbackError (not implemented)
            executor.rollback()

    def test_partial_rollback_on_corruption(self, executor, project_with_backup):
        """Test partial rollback if backup corrupted."""
        project, backup = project_with_backup

        # Corrupt backup file
        (backup / "main.py").write_bytes(b"\x00\xff\xfe")

        with pytest.raises(Exception):  # Changed from RollbackError (not implemented)
            executor.rollback()

    def test_no_rollback_in_dry_run_mode(self, tmp_path):
        """Test no rollback needed in DRY_RUN mode."""
        plan = MigrationPlan(steps=[], total_effort_hours=0, estimated_duration_days=0)
        executor = RetrofitExecutor(project_root=tmp_path)

        result = executor.execute(plan=plan, mode=ExecutionMode.AUTO)

        assert result.backup_created is False
        assert result.rolled_back is False


class TestStepVerification:
    """Test step verification logic."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create executor instance."""
        return RetrofitExecutor(project_root=tmp_path)

    def test_verify_directory_exists_criteria(self, executor, tmp_path):
        """Test verifying 'directory exists' criteria."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        result = executor.verify_criteria("Directory tests/ exists")

        assert result is True

    def test_verify_file_exists_criteria(self, executor, tmp_path):
        """Test verifying 'file exists' criteria."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content\n")

        result = executor.verify_criteria("File test.txt exists")

        assert result is True

    def test_verify_file_content_criteria(self, executor, tmp_path):
        """Test verifying file content criteria."""
        test_file = tmp_path / "config.py"
        test_file.write_text("DEBUG = False\n")

        result = executor.verify_criteria("File config.py contains 'DEBUG = False'")

        assert result is True

    def test_verify_command_execution_criteria(self, executor):
        """Test verifying command execution criteria."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = executor.verify_criteria("Command 'pytest' succeeds")

        assert result is True

    def test_verification_failure_returns_false(self, executor, tmp_path):
        """Test verification failure returns False."""
        result = executor.verify_criteria("File nonexistent.txt exists")

        assert result is False

    def test_all_criteria_must_pass(self, executor):
        """Test all criteria must pass for step to succeed."""
        step = MigrationStep(
            step_id="step1",
            description="Multi-criteria step",
            gap_id="gap1",
            verification_criteria=["Will pass", "Will fail"],
        )

        with patch.object(executor, "verify_criteria", side_effect=[True, False]):
            result = executor.verify_step(step)

        assert result.success is False


class TestExecutionResult:
    """Test execution result reporting."""

    @pytest.fixture
    def sample_result(self):
        """Create sample execution result."""
        return ExecutionResult(
            success=True,
            steps_executed=5,
            steps_skipped=1,
            steps_failed=0,
            backup_created=True,
            backup_path="/tmp/backup-123",
            rolled_back=False,
            execution_time_seconds=45.2,
        )

    def test_result_to_dict(self, sample_result):
        """Test converting result to dictionary."""
        data = sample_result.to_dict()

        assert isinstance(data, dict)
        assert data["success"] is True
        assert data["steps_executed"] == 5

    def test_result_to_json(self, sample_result):
        """Test converting result to JSON."""
        json_str = sample_result.to_json()

        assert isinstance(json_str, str)
        assert "true" in json_str
        assert "45.2" in json_str

    def test_result_summary_generation(self, sample_result):
        """Test generating result summary."""
        summary = sample_result.generate_summary()

        assert "5 steps executed" in summary.lower()
        assert "success" in summary.lower()

    def test_result_includes_timing(self, sample_result):
        """Test result includes execution timing."""
        assert sample_result.execution_time_seconds == 45.2
        assert "45" in sample_result.generate_summary()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_backup_fails_stops_execution(self, tmp_path):
        """Test backup failure prevents execution."""
        plan = MigrationPlan(steps=[], total_effort_hours=0, estimated_duration_days=0)
        executor = RetrofitExecutor(project_root=tmp_path)

        with patch.object(executor, "create_backup", side_effect=OSError("Disk full")):
            with pytest.raises(OSError, match="Disk full"):
                executor.execute(plan=plan, mode=ExecutionMode.AUTO)

    def test_rollback_fails_raises_critical_error(self, tmp_path):
        """Test rollback failure raises critical error."""
        executor = RetrofitExecutor(project_root=tmp_path)
        executor.backup_path = tmp_path / "nonexistent"

        with pytest.raises(Exception):  # Changed from RollbackError (not implemented)
            executor.rollback()

    def test_empty_plan_execution(self, tmp_path):
        """Test executing empty migration plan."""
        plan = MigrationPlan(steps=[], total_effort_hours=0, estimated_duration_days=0)
        executor = RetrofitExecutor(project_root=tmp_path)

        result = executor.execute(plan=plan, mode=ExecutionMode.AUTO)

        assert result.success is True
        assert result.steps_executed == 0

    def test_invalid_project_root(self):
        """Test handling invalid project root."""
        with pytest.raises(ValueError, match="Invalid project root|Path validation failed"):
            RetrofitExecutor(project_root="/nonexistent/path")

    def test_concurrent_execution_prevention(self, tmp_path):
        """Test preventing concurrent execution."""
        plan = MigrationPlan(steps=[], total_effort_hours=0, estimated_duration_days=0)
        executor = RetrofitExecutor(project_root=tmp_path)

        # Start execution in background (simulate)
        executor._execution_in_progress = True

        with pytest.raises(RuntimeError, match="Execution already in progress"):
            executor.execute(plan=plan, mode=ExecutionMode.AUTO)
