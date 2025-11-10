"""
Security tests for /align-project-retrofit - Security validation and hardening.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- Path validation (traversal prevention)
- Symlink attack prevention
- Backup permissions enforcement
- Input validation
- Audit logging verification
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# THESE IMPORTS WILL FAIL - Implementation doesn't exist yet
from plugins.autonomous_dev.lib.brownfield_retrofit import BrownfieldRetrofit
from plugins.autonomous_dev.lib.codebase_analyzer import CodebaseAnalyzer
from plugins.autonomous_dev.lib.retrofit_executor import RetrofitExecutor


class TestPathTraversalPrevention:
    """Test prevention of path traversal attacks (CWE-22)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        project = tmp_path / "secure-project"
        project.mkdir()
        return project

    def test_reject_parent_directory_traversal(self, temp_project):
        """Test rejecting '../' path traversal."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        malicious_path = temp_project / ".." / "etc" / "passwd"

        with pytest.raises(ValueError, match="Path traversal"):
            retrofit._validate_path(malicious_path)

    def test_reject_absolute_path_outside_project(self, temp_project):
        """Test rejecting absolute paths outside project."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        malicious_path = Path("/etc/passwd")

        with pytest.raises(ValueError, match="outside project root"):
            retrofit._validate_path(malicious_path)

    def test_reject_encoded_path_traversal(self, temp_project):
        """Test rejecting URL-encoded path traversal."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        # URL-encoded '../'
        malicious_path = temp_project / "%2e%2e%2f" / "etc" / "passwd"

        with pytest.raises(ValueError, match="Path traversal"):
            retrofit._validate_path(malicious_path)

    def test_accept_valid_project_paths(self, temp_project):
        """Test accepting valid paths within project."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        valid_path = temp_project / "src" / "main.py"

        # Should not raise exception
        retrofit._validate_path(valid_path)

    def test_normalize_paths_before_validation(self, temp_project):
        """Test paths are normalized before validation."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        # Path with redundant components
        path_with_dots = temp_project / "src" / "." / ".." / "src" / "main.py"

        # Should normalize to: temp_project / "src" / "main.py"
        normalized = retrofit._normalize_path(path_with_dots)
        assert ".." not in str(normalized)

    @patch("plugins.autonomous_dev.lib.security_utils.validate_path")
    def test_all_path_operations_validated(self, mock_validate, temp_project):
        """Test all path operations go through validation."""
        analyzer = CodebaseAnalyzer(project_root=temp_project)
        analyzer.analyze()

        # Should validate project root
        mock_validate.assert_called()


class TestSymlinkAttackPrevention:
    """Test prevention of symlink attacks (CWE-59, TOCTOU)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        project = tmp_path / "symlink-project"
        project.mkdir()
        return project

    def test_detect_symlink_in_project(self, temp_project):
        """Test detecting symlinks in project."""
        # Create symlink to /etc/passwd
        symlink_path = temp_project / "evil_link"
        try:
            symlink_path.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        retrofit = BrownfieldRetrofit(project_root=temp_project)

        with pytest.raises(ValueError, match="Symlink detected"):
            retrofit._validate_path(symlink_path)

    def test_follow_safe_internal_symlinks(self, temp_project):
        """Test allowing symlinks within project."""
        # Create internal symlink
        src_dir = temp_project / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')\n")

        link_path = temp_project / "main_link.py"
        try:
            link_path.symlink_to(src_dir / "main.py")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        retrofit = BrownfieldRetrofit(project_root=temp_project)

        # Should validate and resolve
        resolved = retrofit._validate_path(link_path, follow_symlinks=True)
        assert resolved == src_dir / "main.py"

    def test_backup_excludes_external_symlinks(self, temp_project):
        """Test backup excludes symlinks pointing outside project."""
        # Create external symlink
        symlink_path = temp_project / "evil_link"
        try:
            symlink_path.symlink_to("/tmp")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)

        backup_path = executor.create_backup()

        # Backup should not include external symlink
        assert not (backup_path / "evil_link").exists()

    def test_toctou_race_condition_prevention(self, temp_project):
        """Test preventing TOCTOU race conditions."""
        # Create file
        test_file = temp_project / "test.txt"
        test_file.write_text("content\n")

        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)

        # Validate path
        executor._validate_path(test_file)

        # Simulate TOCTOU attack: replace file with symlink
        test_file.unlink()
        try:
            test_file.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Re-validation should catch the change
        with pytest.raises(ValueError, match="Symlink detected"):
            executor._validate_path(test_file)


class TestBackupPermissions:
    """Test backup directory and file permissions (CWE-732)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        project = tmp_path / "permission-project"
        project.mkdir()
        (project / "secret.txt").write_text("secret data\n")
        return project

    def test_backup_directory_permissions_0o700(self, temp_project):
        """Test backup directory has 0o700 permissions."""
        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)

        backup_path = executor.create_backup()

        # Check permissions (owner only)
        mode = backup_path.stat().st_mode
        assert oct(mode)[-3:] == "700"

    def test_backup_files_preserve_permissions(self, temp_project):
        """Test backup files preserve original permissions."""
        secret_file = temp_project / "secret.txt"
        secret_file.chmod(0o600)  # Owner read/write only

        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)

        backup_path = executor.create_backup()

        # Backup should preserve permissions
        backed_up_file = backup_path / "secret.txt"
        mode = backed_up_file.stat().st_mode
        assert oct(mode)[-3:] == "600"

    def test_state_file_permissions_0o600(self, temp_project):
        """Test state file has 0o600 permissions."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)
        retrofit.save_state()

        state_file = temp_project / ".retrofit" / "state.json"

        # Check permissions (owner read/write only)
        mode = state_file.stat().st_mode
        assert oct(mode)[-3:] == "600"

    def test_reject_world_readable_backups(self, temp_project):
        """Test rejecting world-readable backup directories."""
        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)

        backup_path = executor.create_backup()

        # Try to make world-readable (should fail or be prevented)
        try:
            backup_path.chmod(0o777)
        except Exception:
            pass

        # Verify still secure
        mode = backup_path.stat().st_mode
        assert oct(mode)[-1] != "7"  # No world permissions

    def test_backup_not_readable_by_other_users(self, temp_project):
        """Test backup not readable by other users."""
        if os.getuid() == 0:  # Skip for root
            pytest.skip("Running as root, cannot test other user permissions")

        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)

        backup_path = executor.create_backup()

        # Check group and other permissions are 0
        mode = backup_path.stat().st_mode
        group_perms = (mode >> 3) & 0o7
        other_perms = mode & 0o7
        assert group_perms == 0
        assert other_perms == 0


class TestInputValidation:
    """Test input validation and sanitization."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        project = tmp_path / "input-validation"
        project.mkdir()
        return project

    def test_validate_project_root_path(self):
        """Test validating project root path."""
        with pytest.raises(ValueError, match="Invalid project root"):
            BrownfieldRetrofit(project_root="/nonexistent/path")

    def test_validate_project_root_is_directory(self, tmp_path):
        """Test project root must be directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory\n")

        with pytest.raises(ValueError, match="must be a directory"):
            BrownfieldRetrofit(project_root=file_path)

    def test_sanitize_step_description_input(self):
        """Test sanitizing step descriptions for log injection."""
        from plugins.autonomous_dev.lib.migration_planner import MigrationStep

        # Step description with newlines (log injection attempt)
        malicious_description = "Step 1\nFAKE LOG: Admin access granted"

        step = MigrationStep(
            id="step1",
            description=malicious_description,
            gap_id="gap1",
            verification_criteria=["Done"],
        )

        # Description should be sanitized for logging
        sanitized = step._sanitize_for_logging(step.description)
        assert "\n" not in sanitized or "\\n" in sanitized

    def test_validate_phase_name_enum(self, temp_project):
        """Test phase names validated against enum."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        # Invalid phase name
        with pytest.raises(ValueError, match="Invalid phase"):
            retrofit.state.current_phase = "INVALID_PHASE"

    def test_validate_execution_mode_enum(self, temp_project):
        """Test execution mode validated against enum."""
        from plugins.autonomous_dev.lib.retrofit_executor import ExecutionMode

        with pytest.raises(ValueError, match="Invalid execution mode"):
            RetrofitExecutor(
                migration_plan=Mock(),
                project_root=temp_project,
                mode="INVALID_MODE",
            )

    def test_validate_file_path_length(self, temp_project):
        """Test validating file path length."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        # Extremely long path
        long_path = temp_project / ("a" * 1000)

        with pytest.raises(ValueError, match="Path too long"):
            retrofit._validate_path(long_path)

    def test_validate_json_input_size(self, temp_project):
        """Test validating JSON input size."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        # Create huge state data (DoS attempt)
        huge_state = {"data": "x" * 10_000_000}  # 10MB

        with pytest.raises(ValueError, match="State too large"):
            retrofit._validate_state_size(huge_state)


class TestAuditLogging:
    """Test security audit logging."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        project = tmp_path / "audit-project"
        project.mkdir()
        return project

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_retrofit_initialization(self, mock_log, temp_project):
        """Test logging retrofit initialization."""
        BrownfieldRetrofit(project_root=temp_project)

        mock_log.assert_called()
        # Should log initialization with project path
        call_args = mock_log.call_args[1]
        assert "retrofit_init" in call_args.get("action", "")

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_backup_creation(self, mock_log, temp_project):
        """Test logging backup creation."""
        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)
        executor.create_backup()

        # Should log backup creation
        log_calls = [str(call) for call in mock_log.call_args_list]
        assert any("backup" in str(call).lower() for call in log_calls)

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_rollback_operation(self, mock_log, temp_project):
        """Test logging rollback operations."""
        executor = RetrofitExecutor(migration_plan=Mock(), project_root=temp_project)
        executor.backup_path = temp_project / "backup"
        executor.backup_path.mkdir()

        try:
            executor.rollback()
        except Exception:
            pass

        # Should log rollback attempt
        log_calls = [str(call) for call in mock_log.call_args_list]
        assert any("rollback" in str(call).lower() for call in log_calls)

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_phase_transitions(self, mock_log, temp_project):
        """Test logging phase transitions."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)
        retrofit.update_state(current_phase="ASSESS")

        # Should log phase change
        log_calls = [str(call) for call in mock_log.call_args_list]
        assert any("phase" in str(call).lower() for call in log_calls)

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_execution_failures(self, mock_log, temp_project):
        """Test logging execution failures."""
        from plugins.autonomous_dev.lib.migration_planner import (
            MigrationPlan,
            MigrationStep,
        )

        plan = MigrationPlan(
            steps=[
                MigrationStep(
                    id="step1",
                    description="Will fail",
                    gap_id="gap1",
                    verification_criteria=["Impossible"],
                )
            ],
            total_effort_hours=1,
            estimated_duration_days=1,
        )

        executor = RetrofitExecutor(
            migration_plan=plan, project_root=temp_project, mode="AUTO"
        )

        try:
            executor.execute()
        except Exception:
            pass

        # Should log failure
        log_calls = [str(call) for call in mock_log.call_args_list]
        assert any("fail" in str(call).lower() for call in log_calls)

    def test_audit_log_file_permissions(self, temp_project):
        """Test audit log file has secure permissions."""
        from plugins.autonomous_dev.lib.security_utils import audit_log

        audit_log("test_event", action="test", project_root=str(temp_project))

        log_file = Path("logs/security_audit.log")
        if log_file.exists():
            mode = log_file.stat().st_mode
            # Should be owner read/write only or owner/group
            assert oct(mode)[-1] != "7"  # No world write

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_contains_required_fields(self, mock_log, temp_project):
        """Test audit logs contain required fields."""
        retrofit = BrownfieldRetrofit(project_root=temp_project)

        mock_log.assert_called()
        call_kwargs = mock_log.call_args[1]

        # Required fields
        assert "action" in call_kwargs
        assert "project_root" in call_kwargs or "path" in call_kwargs

    @patch("plugins.autonomous_dev.lib.security_utils.audit_log")
    def test_log_does_not_contain_secrets(self, mock_log, temp_project):
        """Test audit logs don't contain secrets."""
        # Create state with fake secret
        retrofit = BrownfieldRetrofit(project_root=temp_project)
        retrofit.state.metadata["api_key"] = "secret_12345"
        retrofit.save_state()

        # Check logs don't contain secret
        for call in mock_log.call_args_list:
            call_str = str(call)
            assert "secret_12345" not in call_str


class TestSecurityEdgeCases:
    """Test security edge cases and attack scenarios."""

    def test_zip_slip_vulnerability_prevention(self, tmp_path):
        """Test prevention of zip slip attacks during backup."""
        import zipfile

        # Create malicious zip with path traversal
        malicious_zip = tmp_path / "malicious.zip"
        with zipfile.ZipFile(malicious_zip, "w") as zf:
            zf.writestr("../../../etc/passwd", "fake content")

        project = tmp_path / "zip-project"
        project.mkdir()

        executor = RetrofitExecutor(migration_plan=Mock(), project_root=project)

        # Should detect and prevent extraction
        with pytest.raises(ValueError, match="Path traversal"):
            executor._extract_backup(malicious_zip)

    def test_command_injection_prevention(self, tmp_path):
        """Test prevention of command injection in verification."""
        from plugins.autonomous_dev.lib.retrofit_verifier import RetrofitVerifier

        project = tmp_path / "injection-project"
        project.mkdir()

        verifier = RetrofitVerifier(project_root=project)

        # Malicious command in criteria
        malicious_criteria = "File exists && rm -rf /"

        # Should sanitize and prevent execution
        result = verifier.verify_criteria(malicious_criteria)
        assert result is False  # Should fail safely

    def test_arbitrary_file_read_prevention(self, tmp_path):
        """Test prevention of arbitrary file read."""
        project = tmp_path / "read-project"
        project.mkdir()

        analyzer = CodebaseAnalyzer(project_root=project)

        # Try to analyze file outside project
        with pytest.raises(ValueError, match="outside project"):
            analyzer._analyze_file(Path("/etc/passwd"))

    def test_denial_of_service_prevention(self, tmp_path):
        """Test prevention of DoS via large inputs."""
        project = tmp_path / "dos-project"
        project.mkdir()

        # Create project with huge number of files (DoS attempt)
        for i in range(100_000):
            (project / f"file_{i}.txt").write_text("x\n")

        analyzer = CodebaseAnalyzer(project_root=project)

        # Should have file count limit
        with pytest.raises(ValueError, match="Too many files"):
            analyzer.analyze()

    def test_race_condition_in_state_file(self, tmp_path):
        """Test handling race condition in state file updates."""
        project = tmp_path / "race-project"
        project.mkdir()

        retrofit1 = BrownfieldRetrofit(project_root=project)
        retrofit2 = BrownfieldRetrofit(project_root=project)

        # Simulate concurrent updates
        retrofit1.update_state(current_phase="ASSESS")
        retrofit2.update_state(current_phase="PLAN")

        # Should detect conflict
        state = retrofit1.load_state()
        assert state.current_phase in ["ASSESS", "PLAN"]  # One should win

    def test_file_inclusion_vulnerability_prevention(self, tmp_path):
        """Test prevention of file inclusion attacks."""
        project = tmp_path / "inclusion-project"
        project.mkdir()

        retrofit = BrownfieldRetrofit(project_root=project)

        # Try to include sensitive file
        malicious_path = "file:///etc/passwd"

        with pytest.raises(ValueError, match="Invalid path"):
            retrofit._validate_path(malicious_path)
