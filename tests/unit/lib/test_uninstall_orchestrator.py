#!/usr/bin/env python3
"""
TDD Tests for Uninstall Orchestrator (FAILING - Red Phase)

This module contains FAILING tests for uninstall_orchestrator.py which will handle
complete uninstallation of the autonomous-dev plugin with backup and rollback capabilities.

Requirements:
1. Three-phase execution: Validate → Preview → Execute
2. Security: Path validation, whitelist enforcement, protected file preservation
3. Backup: Create backup before deletion, support rollback
4. Modes: Dry-run (preview only), Force (execute), Local-only (preserve global)
5. Audit logging: Log all operations for security tracking

Test Coverage Target: 100% of uninstall logic (three-phase execution + security)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe uninstall requirements
- Tests should FAIL until uninstall_orchestrator.py is implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-12-14
Issue: GitHub #131 - Add uninstall capability to install.sh and /sync command
"""

import json
import os
import sys
import tempfile
import tarfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock
from datetime import datetime

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until uninstall_orchestrator.py is created
from plugins.autonomous_dev.lib.uninstall_orchestrator import (
    UninstallOrchestrator,
    UninstallResult,
    UninstallError,
    uninstall_plugin,
)


class TestUninstallOrchestrator:
    """Test UninstallOrchestrator core functionality."""

    @pytest.fixture
    def temp_project_with_install(self, tmp_path):
        """Create temporary project with simulated full install.

        Structure:
        - .claude/commands/ (7 files)
        - .claude/agents/ (22 files)
        - .claude/hooks/ (5 files)
        - .claude/config/install_manifest.json (manifest)
        - .claude/config/settings.local.json (protected)
        - .claude/PROJECT.md (protected)
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create .claude directory structure
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # Create subdirectories
        (claude_dir / "commands").mkdir()
        (claude_dir / "agents").mkdir()
        (claude_dir / "hooks").mkdir()
        (claude_dir / "config").mkdir()

        # Create command files
        commands = ["auto-implement.md", "batch-implement.md", "sync.md",
                   "align.md", "setup.md", "create-issue.md", "health-check.md"]
        for cmd in commands:
            (claude_dir / "commands" / cmd).write_text(f"# {cmd}")

        # Create agent files
        agents = ["researcher-local.md", "researcher-web.md", "planner.md",
                 "test-master.md", "implementer.md", "reviewer.md",
                 "security-auditor.md", "doc-master.md", "advisor.md",
                 "quality-validator.md", "alignment-validator.md",
                 "commit-message-generator.md", "pr-description-generator.md",
                 "issue-creator.md", "brownfield-analyzer.md",
                 "project-progress-tracker.md", "alignment-analyzer.md",
                 "project-bootstrapper.md", "setup-wizard.md",
                 "project-status-analyzer.md", "sync-validator.md", "orchestrator.md"]
        for agent in agents:
            (claude_dir / "agents" / agent).write_text(f"# {agent}")

        # Create hook files
        hooks = ["auto_format.py", "auto_test.py", "validate_project_alignment.py",
                "auto_git_workflow.py", "pre_tool_use.py"]
        for hook in hooks:
            (claude_dir / "hooks" / hook).write_text(f"# {hook}")

        # Create install manifest
        manifest = {
            "version": "3.40.0",
            "generated": datetime.now().strftime("%Y-%m-%d"),
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [f"plugins/autonomous-dev/commands/{cmd}" for cmd in commands]
                },
                "agents": {
                    "target": ".claude/agents",
                    "files": [f"plugins/autonomous-dev/agents/{agent}" for agent in agents]
                },
                "hooks": {
                    "target": ".claude/hooks",
                    "files": [f"plugins/autonomous-dev/hooks/{hook}" for hook in hooks]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest, indent=2))

        # Create protected files (should NOT be removed)
        (claude_dir / "PROJECT.md").write_text("# Project Goals")
        (claude_dir / "config" / "settings.local.json").write_text('{"key": "value"}')
        (project_root / ".env").write_text("API_KEY=secret")

        return project_root

    @pytest.fixture
    def mock_manifest(self):
        """Return sample install manifest data."""
        return {
            "version": "3.40.0",
            "generated": "2025-12-14",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "plugins/autonomous-dev/commands/auto-implement.md",
                        "plugins/autonomous-dev/commands/sync.md"
                    ]
                },
                "agents": {
                    "target": ".claude/agents",
                    "files": [
                        "plugins/autonomous-dev/agents/planner.md",
                        "plugins/autonomous-dev/agents/implementer.md"
                    ]
                }
            }
        }

    def test_orchestrator_initialization(self, temp_project_with_install):
        """Test UninstallOrchestrator initializes correctly.

        REQUIREMENT: Constructor must validate paths and load manifest.
        Expected: Orchestrator created with valid project_root.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project_with_install)

        assert orchestrator.project_root == temp_project_with_install
        assert orchestrator.claude_dir == temp_project_with_install / ".claude"
        assert orchestrator.manifest_path == temp_project_with_install / ".claude" / "config" / "install_manifest.json"

    def test_initialization_invalid_path(self, tmp_path):
        """Test initialization fails with invalid path.

        REQUIREMENT: Security - path validation must prevent traversal.
        Expected: ValueError raised for path traversal attempt.
        """
        malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

        with pytest.raises(ValueError, match="Path traversal detected"):
            UninstallOrchestrator(project_root=malicious_path)


class TestThreePhaseExecution:
    """Test three-phase execution: Validate → Preview → Execute."""

    @pytest.fixture
    def temp_project_with_install(self, tmp_path):
        """Create temporary project with simulated install."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "commands").mkdir()
        (claude_dir / "config").mkdir()

        # Create files
        (claude_dir / "commands" / "auto-implement.md").write_text("# Auto")
        (claude_dir / "commands" / "sync.md").write_text("# Sync")

        # Create manifest
        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "plugins/autonomous-dev/commands/auto-implement.md",
                        "plugins/autonomous-dev/commands/sync.md"
                    ]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        return project_root

    def test_validate_success(self, temp_project_with_install):
        """Test Phase 1: Validate succeeds with valid manifest.

        REQUIREMENT: Validate phase must check manifest exists and paths are valid.
        Expected: Validation returns success, no errors.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project_with_install)
        result = orchestrator.validate()

        assert result.status == "success"
        assert result.errors == []
        assert result.manifest_found is True

    def test_validate_failure_missing_manifest(self, tmp_path):
        """Test Phase 1: Validate fails when manifest missing.

        REQUIREMENT: Validation must detect missing manifest and fail gracefully.
        Expected: Validation returns failure with clear error message.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        orchestrator = UninstallOrchestrator(project_root=project_root)
        result = orchestrator.validate()

        assert result.status == "failure"
        assert result.manifest_found is False
        assert any("manifest not found" in err.lower() for err in result.errors)

    def test_preview_returns_file_list(self, temp_project_with_install):
        """Test Phase 2: Preview returns list of files to remove.

        REQUIREMENT: Preview must show what will be deleted without deleting.
        Expected: Returns list of file paths, files still exist.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project_with_install)
        result = orchestrator.preview()

        assert result.status == "success"
        assert result.files_to_remove >= 2  # At least auto-implement.md, sync.md
        assert result.total_size_bytes > 0

        # Files should still exist after preview
        claude_dir = temp_project_with_install / ".claude"
        assert (claude_dir / "commands" / "auto-implement.md").exists()
        assert (claude_dir / "commands" / "sync.md").exists()

    def test_preview_excludes_protected_files(self, temp_project_with_install):
        """Test Phase 2: Preview excludes protected files.

        REQUIREMENT: Protected files (PROJECT.md, .env, settings.local.json) must not be removed.
        Expected: Preview file list does not include protected files.
        """
        # Add protected files
        claude_dir = temp_project_with_install / ".claude"
        (claude_dir / "PROJECT.md").write_text("# Goals")
        (claude_dir / "config" / "settings.local.json").write_text('{}')
        (temp_project_with_install / ".env").write_text("SECRET=value")

        orchestrator = UninstallOrchestrator(project_root=temp_project_with_install)
        result = orchestrator.preview()

        # Check protected files are excluded
        file_paths = [str(f) for f in result.file_list]
        assert not any("PROJECT.md" in f for f in file_paths)
        assert not any("settings.local.json" in f for f in file_paths)
        assert not any(".env" in f for f in file_paths)

    def test_execute_creates_backup(self, temp_project_with_install):
        """Test Phase 3: Execute creates backup before deletion.

        REQUIREMENT: Must create timestamped backup tar.gz before removing files.
        Expected: Backup file exists with all files, named with timestamp.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project_with_install)
        result = orchestrator.execute(force=True)

        assert result.status == "success"
        assert result.backup_path is not None
        assert result.backup_path.exists()
        assert result.backup_path.suffix == ".gz"

        # Verify backup contains files
        with tarfile.open(result.backup_path, "r:gz") as tar:
            members = tar.getmembers()
            assert len(members) >= 2
            names = [m.name for m in members]
            assert any("auto-implement.md" in n for n in names)

    def test_execute_removes_files(self, temp_project_with_install):
        """Test Phase 3: Execute actually removes files.

        REQUIREMENT: Execute must delete files listed in manifest.
        Expected: Files no longer exist after execution.
        """
        claude_dir = temp_project_with_install / ".claude"

        # Verify files exist before
        assert (claude_dir / "commands" / "auto-implement.md").exists()
        assert (claude_dir / "commands" / "sync.md").exists()

        orchestrator = UninstallOrchestrator(project_root=temp_project_with_install)
        result = orchestrator.execute(force=True)

        assert result.status == "success"
        assert result.files_removed >= 2

        # Verify files removed
        assert not (claude_dir / "commands" / "auto-implement.md").exists()
        assert not (claude_dir / "commands" / "sync.md").exists()

    def test_rollback_restores_files(self, temp_project_with_install):
        """Test rollback restores files from backup.

        REQUIREMENT: Rollback must restore all files from backup tar.gz.
        Expected: Deleted files are restored to original locations.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project_with_install)

        # Execute uninstall
        result = orchestrator.execute(force=True)
        backup_path = result.backup_path

        claude_dir = temp_project_with_install / ".claude"
        assert not (claude_dir / "commands" / "auto-implement.md").exists()

        # Rollback
        rollback_result = orchestrator.rollback(backup_path=backup_path)

        assert rollback_result.status == "success"
        assert rollback_result.files_restored >= 2

        # Verify files restored
        assert (claude_dir / "commands" / "auto-implement.md").exists()
        assert (claude_dir / "commands" / "sync.md").exists()


class TestSecurityValidation:
    """Test security validation (CWE-22, CWE-59, CWE-367)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create basic temp project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "config").mkdir()
        return project_root

    def test_path_traversal_blocked(self, temp_project):
        """Test path traversal attack is blocked (CWE-22).

        REQUIREMENT: Security - must reject path traversal attempts.
        Expected: ValueError raised for ../../etc/passwd in manifest.
        """
        # Create malicious manifest
        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "../../../etc/passwd"
                    ]
                }
            }
        }
        (temp_project / ".claude" / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=temp_project)

        with pytest.raises(ValueError, match="Path traversal detected"):
            orchestrator.preview()

    def test_symlink_attack_blocked(self, temp_project):
        """Test symlink attack is blocked (CWE-59).

        REQUIREMENT: Security - must reject symlinks to sensitive files.
        Expected: ValueError raised for symlink to /etc/passwd.
        """
        # Create symlink to sensitive file
        claude_dir = temp_project / ".claude"
        (claude_dir / "commands").mkdir()

        sensitive_file = temp_project / "sensitive.txt"
        sensitive_file.write_text("SECRET")

        symlink_path = claude_dir / "commands" / "malicious.md"
        symlink_path.symlink_to(sensitive_file)

        # Create manifest referencing symlink
        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "plugins/autonomous-dev/commands/malicious.md"
                    ]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=temp_project)

        with pytest.raises(ValueError, match="Symlink detected"):
            orchestrator.preview()

    @patch('plugins.autonomous_dev.lib.uninstall_orchestrator.audit_log')
    def test_toctou_detection(self, mock_audit_log, temp_project):
        """Test TOCTOU race condition detection (CWE-367).

        REQUIREMENT: Security - detect file changes between preview and execute.
        Expected: Warning logged if file modified between phases.
        """
        claude_dir = temp_project / ".claude"
        (claude_dir / "commands").mkdir()

        cmd_file = claude_dir / "commands" / "auto-implement.md"
        cmd_file.write_text("# Original")

        # Create manifest
        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "plugins/autonomous-dev/commands/auto-implement.md"
                    ]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=temp_project)

        # Preview (captures file state)
        orchestrator.preview()

        # Modify file (simulating TOCTOU race)
        cmd_file.write_text("# Modified during race condition")

        # Execute (should detect modification)
        result = orchestrator.execute(force=True)

        # Should log warning
        mock_audit_log.assert_called()
        calls = [str(call) for call in mock_audit_log.call_args_list]
        assert any("TOCTOU" in call or "file changed" in call.lower() for call in calls)

    def test_whitelist_validation(self, temp_project):
        """Test only whitelisted directories allowed.

        REQUIREMENT: Security - only operate within ~/.claude/, ~/.autonomous-dev/, .claude/.
        Expected: Operations outside whitelist are rejected.
        """
        # Try to create orchestrator targeting non-whitelisted directory
        invalid_dir = temp_project / "random_directory"
        invalid_dir.mkdir()

        # Create manifest trying to target outside whitelist
        manifest = {
            "version": "3.40.0",
            "components": {
                "malicious": {
                    "target": "../../../etc",
                    "files": ["passwd"]
                }
            }
        }
        (temp_project / ".claude" / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=temp_project)

        with pytest.raises(ValueError, match="not in whitelist"):
            orchestrator.preview()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create basic temp project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "config").mkdir()
        return project_root

    def test_already_uninstalled(self, temp_project):
        """Test graceful handling when already uninstalled.

        REQUIREMENT: Edge case - handle re-running uninstall gracefully.
        Expected: Returns success with 0 files removed (no-op).
        """
        # Create empty manifest
        manifest = {
            "version": "3.40.0",
            "components": {}
        }
        (temp_project / ".claude" / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=temp_project)
        result = orchestrator.preview()

        assert result.status == "success"
        assert result.files_to_remove == 0

    def test_partial_install_uninstall(self, temp_project):
        """Test uninstalling partial installation.

        REQUIREMENT: Edge case - handle missing files gracefully.
        Expected: Only existing files removed, missing files skipped.
        """
        claude_dir = temp_project / ".claude"
        (claude_dir / "commands").mkdir()

        # Create only one of two files in manifest
        (claude_dir / "commands" / "auto-implement.md").write_text("# Auto")
        # sync.md deliberately missing

        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "plugins/autonomous-dev/commands/auto-implement.md",
                        "plugins/autonomous-dev/commands/sync.md"  # Missing
                    ]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=temp_project)
        result = orchestrator.execute(force=True)

        assert result.status == "success"
        assert result.files_removed == 1  # Only existing file
        assert len(result.errors) == 0  # No errors for missing file

    @patch('plugins.autonomous_dev.lib.uninstall_orchestrator.audit_log')
    def test_multi_project_detection(self, mock_audit_log, tmp_path):
        """Test warning when .claude/ exists in multiple projects.

        REQUIREMENT: Edge case - warn about multiple project installations.
        Expected: Warning logged if .claude/ detected in multiple locations.
        """
        # Create multiple project directories with .claude/
        project1 = tmp_path / "project1"
        project1.mkdir()
        (project1 / ".claude").mkdir()
        (project1 / ".claude" / "config").mkdir()

        project2 = tmp_path / "project2"
        project2.mkdir()
        (project2 / ".claude").mkdir()

        # Create minimal manifest
        manifest = {"version": "3.40.0", "components": {}}
        (project1 / ".claude" / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=project1)

        # Execute with multi-project detection
        with patch('plugins.autonomous_dev.lib.uninstall_orchestrator.Path.home') as mock_home:
            mock_home.return_value = tmp_path
            result = orchestrator.validate()

        # Should log warning
        mock_audit_log.assert_called()

    def test_permission_denied_continues(self, temp_project, monkeypatch):
        """Test continues processing despite permission errors.

        REQUIREMENT: Edge case - log errors but continue uninstallation.
        Expected: Permission error logged, other files still removed.
        """
        claude_dir = temp_project / ".claude"
        (claude_dir / "commands").mkdir()

        # Create files
        file1 = claude_dir / "commands" / "auto-implement.md"
        file2 = claude_dir / "commands" / "sync.md"
        file1.write_text("# Auto")
        file2.write_text("# Sync")

        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "plugins/autonomous-dev/commands/auto-implement.md",
                        "plugins/autonomous-dev/commands/sync.md"
                    ]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=temp_project)

        # Mock permission error for first file
        original_unlink = Path.unlink
        def mock_unlink(self, *args, **kwargs):
            if "auto-implement" in str(self):
                raise PermissionError("Access denied")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        result = orchestrator.execute(force=True)

        # Should log error but continue
        assert result.status == "success"  # Partial success
        assert result.files_removed >= 1  # At least sync.md removed
        assert any("permission" in err.lower() for err in result.errors)

    def test_spaces_in_paths(self, tmp_path):
        """Test handling of paths with spaces.

        REQUIREMENT: Edge case - correctly handle directory/file names with spaces.
        Expected: Paths with spaces processed correctly.
        """
        # Create project with spaces in path
        project_root = tmp_path / "my project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "commands").mkdir()
        (claude_dir / "config").mkdir()

        # Create file with space in name
        (claude_dir / "commands" / "auto implement.md").write_text("# Auto")

        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": [
                        "plugins/autonomous-dev/commands/auto implement.md"
                    ]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        orchestrator = UninstallOrchestrator(project_root=project_root)
        result = orchestrator.execute(force=True)

        assert result.status == "success"
        assert not (claude_dir / "commands" / "auto implement.md").exists()


class TestDryRunAndForceMode:
    """Test dry-run and force mode behavior."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temp project with install."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "commands").mkdir()
        (claude_dir / "config").mkdir()

        (claude_dir / "commands" / "auto-implement.md").write_text("# Auto")

        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": ["plugins/autonomous-dev/commands/auto-implement.md"]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        return project_root

    def test_dry_run_no_deletion(self, temp_project):
        """Test dry_run=True shows preview without deleting.

        REQUIREMENT: Dry-run must preview without making changes.
        Expected: Files still exist after dry-run.
        """
        claude_dir = temp_project / ".claude"

        orchestrator = UninstallOrchestrator(project_root=temp_project)
        result = orchestrator.execute(force=False, dry_run=True)

        assert result.status == "success"
        assert result.dry_run is True
        assert result.files_removed == 0  # Preview only

        # File should still exist
        assert (claude_dir / "commands" / "auto-implement.md").exists()

    def test_force_required(self, temp_project):
        """Test force=False returns error without confirmation.

        REQUIREMENT: Force mode required for actual deletion.
        Expected: Returns error asking for --force confirmation.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project)
        result = orchestrator.execute(force=False, dry_run=False)

        assert result.status == "failure"
        assert any("--force" in err.lower() or "confirmation" in err.lower() for err in result.errors)

        # File should still exist
        claude_dir = temp_project / ".claude"
        assert (claude_dir / "commands" / "auto-implement.md").exists()

    def test_force_executes(self, temp_project):
        """Test force=True actually removes files.

        REQUIREMENT: Force mode enables actual deletion.
        Expected: Files removed when force=True.
        """
        claude_dir = temp_project / ".claude"

        orchestrator = UninstallOrchestrator(project_root=temp_project)
        result = orchestrator.execute(force=True)

        assert result.status == "success"
        assert result.files_removed >= 1

        # File should be removed
        assert not (claude_dir / "commands" / "auto-implement.md").exists()

    def test_local_only_preserves_global(self, temp_project, tmp_path):
        """Test --local-only preserves global ~/.claude/ files.

        REQUIREMENT: Local-only mode must skip ~/.claude/ and ~/.autonomous-dev/.
        Expected: Only .claude/ in project removed, global files untouched.
        """
        # Create global directory structure
        global_claude = tmp_path / "home" / ".claude"
        global_claude.mkdir(parents=True)
        (global_claude / "hooks").mkdir()
        (global_claude / "hooks" / "auto_format.py").write_text("# Global hook")

        orchestrator = UninstallOrchestrator(project_root=temp_project)

        with patch('plugins.autonomous_dev.lib.uninstall_orchestrator.Path.home') as mock_home:
            mock_home.return_value = tmp_path / "home"
            result = orchestrator.execute(force=True, local_only=True)

        assert result.status == "success"

        # Local file removed
        assert not (temp_project / ".claude" / "commands" / "auto-implement.md").exists()

        # Global file preserved
        assert (global_claude / "hooks" / "auto_format.py").exists()


class TestUninstallFunction:
    """Test standalone uninstall_plugin() function."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temp project with install."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "commands").mkdir()
        (claude_dir / "config").mkdir()

        (claude_dir / "commands" / "auto-implement.md").write_text("# Auto")

        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": ["plugins/autonomous-dev/commands/auto-implement.md"]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        return project_root

    def test_uninstall_plugin_function(self, temp_project):
        """Test standalone uninstall_plugin() function.

        REQUIREMENT: Convenience function for simple uninstallation.
        Expected: Function performs complete uninstall workflow.
        """
        result = uninstall_plugin(
            project_root=temp_project,
            force=True,
            dry_run=False
        )

        assert result.status == "success"
        assert result.files_removed >= 1

        # File removed
        assert not (temp_project / ".claude" / "commands" / "auto-implement.md").exists()

    def test_uninstall_plugin_dry_run(self, temp_project):
        """Test standalone function dry-run mode.

        REQUIREMENT: Function supports dry-run preview.
        Expected: Preview returned, no files deleted.
        """
        result = uninstall_plugin(
            project_root=temp_project,
            force=False,
            dry_run=True
        )

        assert result.status == "success"
        assert result.dry_run is True

        # File preserved
        assert (temp_project / ".claude" / "commands" / "auto-implement.md").exists()


class TestUninstallResult:
    """Test UninstallResult dataclass."""

    def test_result_dataclass_fields(self):
        """Test UninstallResult has required fields.

        REQUIREMENT: Result must include status, counts, errors.
        Expected: All fields accessible.
        """
        result = UninstallResult(
            status="success",
            files_removed=10,
            total_size_bytes=50000,
            backup_path=Path("/tmp/backup.tar.gz"),
            errors=[],
            dry_run=False
        )

        assert result.status == "success"
        assert result.files_removed == 10
        assert result.total_size_bytes == 50000
        assert result.backup_path == Path("/tmp/backup.tar.gz")
        assert result.errors == []
        assert result.dry_run is False

    def test_result_to_dict(self):
        """Test UninstallResult converts to dictionary.

        REQUIREMENT: Result must serialize to dict for JSON output.
        Expected: to_dict() returns valid dictionary.
        """
        result = UninstallResult(
            status="success",
            files_removed=5,
            total_size_bytes=10000,
            backup_path=Path("/tmp/backup.tar.gz"),
            errors=["warning 1"],
            dry_run=True
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["status"] == "success"
        assert result_dict["files_removed"] == 5
        assert result_dict["backup_path"] == "/tmp/backup.tar.gz"


class TestAuditLogging:
    """Test audit logging for security tracking."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temp project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "commands").mkdir()
        (claude_dir / "config").mkdir()

        (claude_dir / "commands" / "auto-implement.md").write_text("# Auto")

        manifest = {
            "version": "3.40.0",
            "components": {
                "commands": {
                    "target": ".claude/commands",
                    "files": ["plugins/autonomous-dev/commands/auto-implement.md"]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        return project_root

    @patch('plugins.autonomous_dev.lib.uninstall_orchestrator.audit_log')
    def test_audit_log_uninstall_start(self, mock_audit_log, temp_project):
        """Test audit log records uninstall start.

        REQUIREMENT: Security - audit all uninstall operations.
        Expected: Audit log called with uninstall start event.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project)
        orchestrator.execute(force=True)

        # Check audit_log called with start event
        calls = [str(call) for call in mock_audit_log.call_args_list]
        assert any("uninstall" in call.lower() and "start" in call.lower() for call in calls)

    @patch('plugins.autonomous_dev.lib.uninstall_orchestrator.audit_log')
    def test_audit_log_file_deletion(self, mock_audit_log, temp_project):
        """Test audit log records each file deletion.

        REQUIREMENT: Security - audit individual file deletions.
        Expected: Each deleted file logged to audit trail.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project)
        orchestrator.execute(force=True)

        # Check audit_log called with file deletion
        calls = [str(call) for call in mock_audit_log.call_args_list]
        assert any("auto-implement.md" in call for call in calls)

    @patch('plugins.autonomous_dev.lib.uninstall_orchestrator.audit_log')
    def test_audit_log_backup_creation(self, mock_audit_log, temp_project):
        """Test audit log records backup creation.

        REQUIREMENT: Security - audit backup operations.
        Expected: Backup creation logged with path.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project)
        orchestrator.execute(force=True)

        # Check audit_log called with backup event
        calls = [str(call) for call in mock_audit_log.call_args_list]
        assert any("backup" in call.lower() for call in calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
