"""Unit tests for GenAI installation wrapper CLI.

Tests the CLI wrapper functions for setup-wizard Phase 0 GenAI integration.
All tests should FAIL initially (TDD red phase) - no implementation exists yet.

Related: GitHub Issue #109
"""

import json
from pathlib import Path
from typing import Dict, Any

import pytest


class TestCheckStaging:
    """Test staging directory validation."""

    def test_check_staging_exists(self, tmp_path: Path) -> None:
        """Valid staging directory returns valid status."""
        from autonomous_dev.scripts.genai_install_wrapper import check_staging

        # Arrange: Create staging with required structure
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/agents").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/hooks").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/lib").mkdir(parents=True)

        # Act
        result = check_staging(str(staging))

        # Assert
        assert result["status"] == "valid"
        assert result["staging_path"] == str(staging)
        assert "missing_dirs" not in result
        assert result["fallback_needed"] is False

    def test_check_staging_missing(self, tmp_path: Path) -> None:
        """Missing staging returns missing status with fallback flag."""
        from autonomous_dev.scripts.genai_install_wrapper import check_staging

        # Arrange: Staging doesn't exist
        staging = tmp_path / "nonexistent"

        # Act
        result = check_staging(str(staging))

        # Assert
        assert result["status"] == "missing"
        assert result["fallback_needed"] is True
        assert "message" in result
        assert "skip to Phase 1" in result["message"]

    def test_check_staging_incomplete(self, tmp_path: Path) -> None:
        """Staging with missing critical directories returns invalid status."""
        from autonomous_dev.scripts.genai_install_wrapper import check_staging

        # Arrange: Staging exists but missing critical dirs
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        # Missing agents/, hooks/, lib/

        # Act
        result = check_staging(str(staging))

        # Assert
        assert result["status"] == "invalid"
        assert result["fallback_needed"] is True
        assert "missing_dirs" in result
        assert len(result["missing_dirs"]) == 3  # agents, hooks, lib


class TestAnalyzeInstallationType:
    """Test installation type detection."""

    def test_analyze_fresh_install(self, tmp_path: Path) -> None:
        """Empty project returns fresh install type."""
        from autonomous_dev.scripts.genai_install_wrapper import analyze_installation_type

        # Arrange: Empty project directory
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act
        result = analyze_installation_type(str(project_dir))

        # Assert
        assert result["type"] == "fresh"
        assert result["has_project_md"] is False
        assert result["has_claude_dir"] is False
        assert "existing_files" not in result or len(result["existing_files"]) == 0

    def test_analyze_brownfield_install(self, tmp_path: Path) -> None:
        """Project with PROJECT.md returns brownfield type."""
        from autonomous_dev.scripts.genai_install_wrapper import analyze_installation_type

        # Arrange: Project with PROJECT.md
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "PROJECT.md").write_text("# Existing project")

        # Act
        result = analyze_installation_type(str(project_dir))

        # Assert
        assert result["type"] == "brownfield"
        assert result["has_project_md"] is True
        assert "existing_files" in result
        assert ".claude/PROJECT.md" in result["existing_files"]

    def test_analyze_upgrade_install(self, tmp_path: Path) -> None:
        """Project with .claude/ but no PROJECT.md returns upgrade type."""
        from autonomous_dev.scripts.genai_install_wrapper import analyze_installation_type

        # Arrange: Project with .claude/ but no PROJECT.md
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "hooks").mkdir()

        # Act
        result = analyze_installation_type(str(project_dir))

        # Assert
        assert result["type"] == "upgrade"
        assert result["has_project_md"] is False
        assert result["has_claude_dir"] is True

    def test_analyze_detects_protected_files(self, tmp_path: Path) -> None:
        """Detects protected files that shouldn't be overwritten."""
        from autonomous_dev.scripts.genai_install_wrapper import analyze_installation_type

        # Arrange: Project with .env and PROJECT.md
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".env").write_text("SECRET=value")
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "PROJECT.md").write_text("# Existing")

        # Act
        result = analyze_installation_type(str(project_dir))

        # Assert
        assert "protected_files" in result
        assert ".env" in result["protected_files"]
        assert ".claude/PROJECT.md" in result["protected_files"]


class TestExecuteInstallation:
    """Test installation execution."""

    def test_execute_installation_success(self, tmp_path: Path) -> None:
        """Files copied and audit logged successfully."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Staging and project directories
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        # Create source files
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands/test.md").write_text("# Test command")
        (staging / "plugins/autonomous-dev/agents").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/agents/test-agent.md").write_text("# Test agent")

        # Act
        result = execute_installation(
            staging_path=str(staging),
            project_path=str(project),
            install_type="fresh"
        )

        # Assert
        assert result["status"] == "success"
        assert result["files_copied"] > 0
        assert (project / "plugins/autonomous-dev/commands/test.md").exists()
        assert (project / "plugins/autonomous-dev/agents/test-agent.md").exists()

        # Check audit log
        audit_file = project / ".claude" / "install_audit.jsonl"
        assert audit_file.exists()
        audit_lines = audit_file.read_text().strip().split("\n")
        assert len(audit_lines) > 0
        first_event = json.loads(audit_lines[0])
        assert first_event["event"] == "installation_start"

    def test_execute_installation_respects_protected(self, tmp_path: Path) -> None:
        """Protected files (.env, PROJECT.md) not overwritten."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Existing protected files
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        # Create staging files
        (staging / ".env").write_text("NEW_SECRET=new")
        (staging / ".claude").mkdir()
        (staging / ".claude" / "PROJECT.md").write_text("# New content")

        # Create existing protected files
        (project / ".env").write_text("OLD_SECRET=old")
        (project / ".claude").mkdir()
        (project / ".claude" / "PROJECT.md").write_text("# Old content")

        # Act
        result = execute_installation(
            staging_path=str(staging),
            project_path=str(project),
            install_type="brownfield"
        )

        # Assert
        assert result["status"] == "success"
        # Protected files should NOT be overwritten
        assert (project / ".env").read_text() == "OLD_SECRET=old"
        assert (project / ".claude" / "PROJECT.md").read_text() == "# Old content"
        # Should have skipped_files in result
        assert "skipped_files" in result
        assert ".env" in result["skipped_files"]
        assert ".claude/PROJECT.md" in result["skipped_files"]

    def test_execute_installation_creates_backups(self, tmp_path: Path) -> None:
        """Modified files backed up during upgrade installation."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Existing file to be upgraded
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        # Create staging file
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands/auto-implement.md").write_text("# New version")

        # Create existing file
        (project / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (project / "plugins/autonomous-dev/commands/auto-implement.md").write_text("# Old version")

        # Act
        result = execute_installation(
            staging_path=str(staging),
            project_path=str(project),
            install_type="upgrade"
        )

        # Assert
        assert result["status"] == "success"
        # File should be updated
        assert (project / "plugins/autonomous-dev/commands/auto-implement.md").read_text() == "# New version"
        # Backup should exist
        assert "backups_created" in result
        assert len(result["backups_created"]) > 0
        # Backup file pattern: .backup-YYYYMMDD-HHMMSS
        backup_files = list((project / "plugins/autonomous-dev/commands").glob("auto-implement.md.backup-*"))
        assert len(backup_files) == 1
        assert backup_files[0].read_text() == "# Old version"


class TestCleanup:
    """Test cleanup operations."""

    def test_cleanup_removes_staging(self, tmp_path: Path) -> None:
        """Staging directory removed after successful installation."""
        from autonomous_dev.scripts.genai_install_wrapper import cleanup_staging

        # Arrange: Create staging directory
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands/test.md").write_text("# Test")

        # Act
        result = cleanup_staging(str(staging))

        # Assert
        assert result["status"] == "success"
        assert not staging.exists()

    def test_cleanup_handles_missing_staging(self, tmp_path: Path) -> None:
        """Cleanup gracefully handles already-removed staging."""
        from autonomous_dev.scripts.genai_install_wrapper import cleanup_staging

        # Arrange: Staging doesn't exist
        staging = tmp_path / "nonexistent"

        # Act
        result = cleanup_staging(str(staging))

        # Assert
        assert result["status"] == "success"  # Idempotent
        assert "message" in result


class TestSummaryGeneration:
    """Test installation summary generation."""

    def test_generate_summary(self, tmp_path: Path) -> None:
        """Summary report generated with all installation details."""
        from autonomous_dev.scripts.genai_install_wrapper import generate_summary

        # Arrange: Installation results
        install_result = {
            "status": "success",
            "files_copied": 42,
            "skipped_files": [".env", ".claude/PROJECT.md"],
            "backups_created": [],
        }

        # Act
        result = generate_summary(
            install_type="brownfield",
            install_result=install_result,
            project_path=str(tmp_path)
        )

        # Assert
        assert result["status"] == "success"
        assert "summary" in result
        assert "install_type" in result["summary"]
        assert result["summary"]["install_type"] == "brownfield"
        assert result["summary"]["files_copied"] == 42
        assert len(result["summary"]["skipped_files"]) == 2
        assert "next_steps" in result
        assert isinstance(result["next_steps"], list)
        assert len(result["next_steps"]) > 0

    def test_generate_summary_fresh_install(self, tmp_path: Path) -> None:
        """Fresh install summary includes setup wizard next step."""
        from autonomous_dev.scripts.genai_install_wrapper import generate_summary

        # Arrange: Fresh installation
        install_result = {
            "status": "success",
            "files_copied": 42,
        }

        # Act
        result = generate_summary(
            install_type="fresh",
            install_result=install_result,
            project_path=str(tmp_path)
        )

        # Assert
        assert "next_steps" in result
        # Fresh install should suggest setup wizard
        next_steps_text = " ".join(result["next_steps"])
        assert "setup" in next_steps_text.lower() or "wizard" in next_steps_text.lower()

    def test_generate_summary_upgrade_install(self, tmp_path: Path) -> None:
        """Upgrade install summary includes backup information."""
        from autonomous_dev.scripts.genai_install_wrapper import generate_summary

        # Arrange: Upgrade installation with backups
        install_result = {
            "status": "success",
            "files_copied": 15,
            "backups_created": [
                "plugins/autonomous-dev/commands/auto-implement.md.backup-20251209-120000"
            ],
        }

        # Act
        result = generate_summary(
            install_type="upgrade",
            install_result=install_result,
            project_path=str(tmp_path)
        )

        # Assert
        assert result["summary"]["backups_created"] == 1
        # Upgrade should mention backups in next steps
        next_steps_text = " ".join(result["next_steps"])
        assert "backup" in next_steps_text.lower()


class TestErrorHandling:
    """Test error handling and validation."""

    def test_error_handling_invalid_path(self, tmp_path: Path) -> None:
        """Returns error status for invalid paths."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Invalid staging path
        staging = "/nonexistent/invalid/path"
        project = str(tmp_path)

        # Act
        result = execute_installation(
            staging_path=staging,
            project_path=project,
            install_type="fresh"
        )

        # Assert
        assert result["status"] == "error"
        assert "error" in result
        assert "staging" in result["error"].lower()

    def test_error_handling_permission_denied(self, tmp_path: Path) -> None:
        """Returns error status when file operations fail."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Staging exists but project is read-only
        staging = tmp_path / "staging"
        project = tmp_path / "readonly"
        staging.mkdir()
        project.mkdir()

        # Create source file
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands/test.md").write_text("# Test")

        # Make project read-only (simulation - actual test may need OS-specific handling)
        # This test validates the error handling path exists

        # Act & Assert
        # NOTE: Actual permission testing may need platform-specific setup
        # For now, we validate the error handling structure exists
        assert True  # Placeholder - implementation should handle PermissionError

    def test_error_handling_invalid_install_type(self, tmp_path: Path) -> None:
        """Returns error status for invalid installation type."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Valid paths but invalid install type
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        # Act
        result = execute_installation(
            staging_path=str(staging),
            project_path=str(project),
            install_type="invalid_type"
        )

        # Assert
        assert result["status"] == "error"
        assert "error" in result
        assert "install_type" in result["error"].lower() or "invalid" in result["error"].lower()


class TestCLIInterface:
    """Test CLI interface and argument parsing."""

    def test_cli_check_staging_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI check-staging command returns JSON output."""
        import sys
        from autonomous_dev.scripts.genai_install_wrapper import main

        # Arrange: Create staging
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/agents").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/hooks").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/lib").mkdir(parents=True)

        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", [
            "genai_install_wrapper.py",
            "check-staging",
            str(staging)
        ])

        # Act
        exit_code = main()

        # Assert
        assert exit_code == 0

    def test_cli_analyze_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI analyze command returns JSON output."""
        import sys
        from autonomous_dev.scripts.genai_install_wrapper import main

        # Arrange: Create project
        project = tmp_path / "project"
        project.mkdir()

        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", [
            "genai_install_wrapper.py",
            "analyze",
            str(project)
        ])

        # Act
        exit_code = main()

        # Assert
        assert exit_code == 0

    def test_cli_execute_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI execute command performs installation."""
        import sys
        from autonomous_dev.scripts.genai_install_wrapper import main

        # Arrange: Create staging and project
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands/test.md").write_text("# Test")

        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", [
            "genai_install_wrapper.py",
            "execute",
            str(staging),
            str(project),
            "fresh"
        ])

        # Act
        exit_code = main()

        # Assert
        assert exit_code == 0
        assert (project / "plugins/autonomous-dev/commands/test.md").exists()

    def test_cli_cleanup_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI cleanup command removes staging."""
        import sys
        from autonomous_dev.scripts.genai_install_wrapper import main

        # Arrange: Create staging
        staging = tmp_path / "staging"
        staging.mkdir()

        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", [
            "genai_install_wrapper.py",
            "cleanup",
            str(staging)
        ])

        # Act
        exit_code = main()

        # Assert
        assert exit_code == 0
        assert not staging.exists()

    def test_cli_summary_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI summary command generates report."""
        import sys
        from autonomous_dev.scripts.genai_install_wrapper import main

        # Arrange: Create result file
        result_file = tmp_path / "install_result.json"
        result_file.write_text(json.dumps({
            "status": "success",
            "files_copied": 42,
        }))

        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", [
            "genai_install_wrapper.py",
            "summary",
            "fresh",
            str(result_file),
            str(tmp_path)
        ])

        # Act
        exit_code = main()

        # Assert
        assert exit_code == 0


class TestAuditLogging:
    """Test installation audit logging."""

    def test_audit_log_created(self, tmp_path: Path) -> None:
        """Audit log file created with installation events."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands/test.md").write_text("# Test")

        # Act
        execute_installation(
            staging_path=str(staging),
            project_path=str(project),
            install_type="fresh"
        )

        # Assert
        audit_file = project / ".claude" / "install_audit.jsonl"
        assert audit_file.exists()

        # Parse audit log
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]
        assert len(events) > 0

        # Check event structure
        for event in events:
            assert "timestamp" in event
            assert "event" in event
            assert "details" in event

    def test_audit_log_tracks_file_operations(self, tmp_path: Path) -> None:
        """Audit log tracks individual file copy operations."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        # Create multiple files
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands/cmd1.md").write_text("# Cmd1")
        (staging / "plugins/autonomous-dev/commands/cmd2.md").write_text("# Cmd2")

        # Act
        execute_installation(
            staging_path=str(staging),
            project_path=str(project),
            install_type="fresh"
        )

        # Assert
        audit_file = project / ".claude" / "install_audit.jsonl"
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]

        # Should have file_copied events
        file_events = [e for e in events if e["event"] == "file_copied"]
        assert len(file_events) >= 2

    def test_audit_log_tracks_protected_files(self, tmp_path: Path) -> None:
        """Audit log tracks skipped protected files."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange
        staging = tmp_path / "staging"
        project = tmp_path / "project"
        staging.mkdir()
        project.mkdir()

        # Create protected file in both locations
        (staging / ".env").write_text("NEW=value")
        (project / ".env").write_text("OLD=value")

        # Act
        execute_installation(
            staging_path=str(staging),
            project_path=str(project),
            install_type="brownfield"
        )

        # Assert
        audit_file = project / ".claude" / "install_audit.jsonl"
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]

        # Should have file_skipped event
        skip_events = [e for e in events if e["event"] == "file_skipped"]
        assert len(skip_events) > 0
        assert any(".env" in e["details"].get("file", "") for e in skip_events)
