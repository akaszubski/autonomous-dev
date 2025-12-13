#!/usr/bin/env python3
"""
Integration Tests for /sync --uninstall (FAILING - Red Phase)

This module contains FAILING integration tests for the /sync --uninstall command
which integrates uninstall_orchestrator.py with sync_dispatcher.py.

Requirements:
1. SyncMode.UNINSTALL dispatches to uninstall_orchestrator
2. --uninstall flag shows preview by default
3. --uninstall --force executes actual deletion
4. --uninstall --local-only preserves global files
5. Error handling and reporting integrates with sync infrastructure

Test Coverage Target: 100% of sync uninstall integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe integration requirements
- Tests should FAIL until sync_dispatcher.py updated
- Each test validates ONE integration requirement

Author: test-master agent
Date: 2025-12-14
Issue: GitHub #131 - Add uninstall capability to install.sh and /sync command
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# These imports will FAIL/PARTIAL until implementation complete
from plugins.autonomous_dev.lib.sync_dispatcher import (
    SyncDispatcher,
    SyncMode,
    SyncResult,
)
from plugins.autonomous_dev.lib.uninstall_orchestrator import (
    UninstallOrchestrator,
    UninstallResult,
)


class TestSyncUninstallIntegration:
    """Test SyncDispatcher integration with uninstall_orchestrator."""

    @pytest.fixture
    def temp_project_with_install(self, tmp_path):
        """Create temporary project with simulated full install."""
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

        # Create sample files
        (claude_dir / "commands" / "auto-implement.md").write_text("# Auto")
        (claude_dir / "commands" / "sync.md").write_text("# Sync")
        (claude_dir / "agents" / "planner.md").write_text("# Planner")
        (claude_dir / "hooks" / "auto_format.py").write_text("# Format")

        # Create install manifest
        manifest = {
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
                    "files": ["plugins/autonomous-dev/agents/planner.md"]
                },
                "hooks": {
                    "target": ".claude/hooks",
                    "files": ["plugins/autonomous-dev/hooks/auto_format.py"]
                }
            }
        }
        (claude_dir / "config" / "install_manifest.json").write_text(json.dumps(manifest, indent=2))

        # Create protected files
        (claude_dir / "PROJECT.md").write_text("# Project Goals")
        (claude_dir / "config" / "settings.local.json").write_text('{"key": "value"}')

        return project_root

    def test_sync_mode_uninstall_exists(self):
        """Test SyncMode.UNINSTALL enum exists.

        REQUIREMENT: SyncMode must include UNINSTALL option.
        Expected: SyncMode.UNINSTALL is accessible.
        """
        assert hasattr(SyncMode, "UNINSTALL")
        assert SyncMode.UNINSTALL is not None

    def test_sync_dispatcher_uninstall_mode(self, temp_project_with_install):
        """Test SyncDispatcher dispatches to uninstall_orchestrator.

        REQUIREMENT: SyncDispatcher must route UNINSTALL mode to orchestrator.
        Expected: Calls UninstallOrchestrator.execute() correctly.
        """
        dispatcher = SyncDispatcher(project_root=temp_project_with_install)

        with patch.object(UninstallOrchestrator, 'execute') as mock_execute:
            mock_execute.return_value = UninstallResult(
                status="success",
                files_removed=4,
                total_size_bytes=10000,
                backup_path=Path("/tmp/backup.tar.gz"),
                errors=[],
                dry_run=False
            )

            result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)

            # Verify uninstall orchestrator called
            mock_execute.assert_called_once()
            assert result.status == "success"

    def test_sync_uninstall_dry_run_default(self, temp_project_with_install):
        """Test /sync --uninstall shows preview by default (no --force).

        REQUIREMENT: Default behavior is dry-run preview without deletion.
        Expected: force=False shows preview, files not deleted.
        """
        dispatcher = SyncDispatcher(project_root=temp_project_with_install)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=False)

        assert result.status == "success"
        assert result.dry_run is True or "preview" in result.message.lower()

        # Files should still exist
        claude_dir = temp_project_with_install / ".claude"
        assert (claude_dir / "commands" / "auto-implement.md").exists()

    def test_sync_uninstall_force_executes(self, temp_project_with_install):
        """Test /sync --uninstall --force executes actual deletion.

        REQUIREMENT: --force flag enables actual file deletion.
        Expected: Files removed when force=True.
        """
        dispatcher = SyncDispatcher(project_root=temp_project_with_install)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)

        assert result.status == "success"
        assert result.files_removed >= 4

        # Files should be removed
        claude_dir = temp_project_with_install / ".claude"
        assert not (claude_dir / "commands" / "auto-implement.md").exists()
        assert not (claude_dir / "commands" / "sync.md").exists()
        assert not (claude_dir / "agents" / "planner.md").exists()
        assert not (claude_dir / "hooks" / "auto_format.py").exists()

    def test_sync_uninstall_preserves_protected_files(self, temp_project_with_install):
        """Test /sync --uninstall preserves protected files.

        REQUIREMENT: Protected files (PROJECT.md, settings.local.json) never removed.
        Expected: Protected files exist after uninstall.
        """
        dispatcher = SyncDispatcher(project_root=temp_project_with_install)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)

        assert result.status == "success"

        # Protected files should still exist
        claude_dir = temp_project_with_install / ".claude"
        assert (claude_dir / "PROJECT.md").exists()
        assert (claude_dir / "config" / "settings.local.json").exists()

    def test_sync_uninstall_local_only_mode(self, temp_project_with_install, tmp_path):
        """Test /sync --uninstall --local-only preserves global files.

        REQUIREMENT: --local-only flag skips ~/.claude/ and ~/.autonomous-dev/.
        Expected: Only project .claude/ removed, global files preserved.
        """
        # Create global directory
        global_claude = tmp_path / "home" / ".claude"
        global_claude.mkdir(parents=True)
        (global_claude / "hooks").mkdir()
        (global_claude / "hooks" / "auto_format.py").write_text("# Global")

        dispatcher = SyncDispatcher(project_root=temp_project_with_install)

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.Path.home') as mock_home:
            mock_home.return_value = tmp_path / "home"
            result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True, local_only=True)

        assert result.status == "success"

        # Project files removed
        claude_dir = temp_project_with_install / ".claude"
        assert not (claude_dir / "commands" / "auto-implement.md").exists()

        # Global files preserved
        assert (global_claude / "hooks" / "auto_format.py").exists()

    def test_sync_uninstall_error_handling(self, tmp_path):
        """Test error handling when manifest missing.

        REQUIREMENT: Integration must handle errors gracefully.
        Expected: Returns failure status with clear error message.
        """
        # Create project without manifest
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        dispatcher = SyncDispatcher(project_root=project_root)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)

        assert result.status == "failure"
        assert any("manifest" in err.lower() for err in result.errors)

    def test_sync_uninstall_creates_backup(self, temp_project_with_install):
        """Test backup created before uninstallation.

        REQUIREMENT: Integration must create backup via orchestrator.
        Expected: Backup path included in result.
        """
        dispatcher = SyncDispatcher(project_root=temp_project_with_install)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)

        assert result.status == "success"
        assert result.backup_path is not None
        assert result.backup_path.exists()


class TestSyncUninstallCommandParsing:
    """Test command-line argument parsing for /sync --uninstall."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create basic temp project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "config").mkdir()

        # Create minimal manifest
        manifest = {"version": "3.40.0", "components": {}}
        (project_root / ".claude" / "config" / "install_manifest.json").write_text(
            json.dumps(manifest)
        )

        return project_root

    @patch('plugins.autonomous_dev.lib.sync_dispatcher.SyncDispatcher.sync')
    def test_parse_uninstall_flag(self, mock_sync, temp_project):
        """Test --uninstall flag parsed correctly.

        REQUIREMENT: Command must recognize --uninstall flag.
        Expected: SyncMode.UNINSTALL passed to dispatcher.
        """
        # Simulate command-line parsing
        args = ["--uninstall"]

        # Parse and dispatch (this would be in sync.md command)
        mode = SyncMode.UNINSTALL if "--uninstall" in args else SyncMode.GITHUB
        force = "--force" in args

        dispatcher = SyncDispatcher(project_root=temp_project)
        dispatcher.sync(mode=mode, force=force)

        # Verify dispatcher called with correct mode
        mock_sync.assert_called_once_with(mode=SyncMode.UNINSTALL, force=False)

    @patch('plugins.autonomous_dev.lib.sync_dispatcher.SyncDispatcher.sync')
    def test_parse_uninstall_force_flags(self, mock_sync, temp_project):
        """Test --uninstall --force flags parsed correctly.

        REQUIREMENT: Command must handle multiple flags.
        Expected: Both mode and force extracted correctly.
        """
        args = ["--uninstall", "--force"]

        mode = SyncMode.UNINSTALL if "--uninstall" in args else SyncMode.GITHUB
        force = "--force" in args

        dispatcher = SyncDispatcher(project_root=temp_project)
        dispatcher.sync(mode=mode, force=force)

        mock_sync.assert_called_once_with(mode=SyncMode.UNINSTALL, force=True)

    @patch('plugins.autonomous_dev.lib.sync_dispatcher.SyncDispatcher.sync')
    def test_parse_uninstall_local_only_flags(self, mock_sync, temp_project):
        """Test --uninstall --local-only flags parsed correctly.

        REQUIREMENT: Command must support --local-only flag.
        Expected: local_only parameter passed correctly.
        """
        args = ["--uninstall", "--force", "--local-only"]

        mode = SyncMode.UNINSTALL if "--uninstall" in args else SyncMode.GITHUB
        force = "--force" in args
        local_only = "--local-only" in args

        dispatcher = SyncDispatcher(project_root=temp_project)
        dispatcher.sync(mode=mode, force=force, local_only=local_only)

        mock_sync.assert_called_once_with(
            mode=SyncMode.UNINSTALL,
            force=True,
            local_only=True
        )


class TestSyncUninstallOutput:
    """Test output formatting for /sync --uninstall."""

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

    def test_dry_run_output_shows_preview(self, temp_project):
        """Test dry-run output shows preview information.

        REQUIREMENT: Output must clearly show preview mode.
        Expected: Result includes preview details, file list.
        """
        dispatcher = SyncDispatcher(project_root=temp_project)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=False)

        assert result.status == "success"
        assert result.dry_run is True or "preview" in result.message.lower()
        assert result.files_to_remove is not None
        assert result.total_size_bytes is not None

    def test_force_output_shows_summary(self, temp_project):
        """Test force mode output shows deletion summary.

        REQUIREMENT: Output must show what was deleted.
        Expected: Result includes files_removed, backup_path.
        """
        dispatcher = SyncDispatcher(project_root=temp_project)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)

        assert result.status == "success"
        assert result.files_removed >= 1
        assert result.backup_path is not None

    def test_error_output_shows_details(self, tmp_path):
        """Test error output shows clear error details.

        REQUIREMENT: Errors must be clearly communicated.
        Expected: Result includes error list with details.
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        dispatcher = SyncDispatcher(project_root=project_root)

        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)

        assert result.status == "failure"
        assert len(result.errors) > 0
        assert any("manifest" in err.lower() for err in result.errors)


class TestSyncUninstallRollback:
    """Test rollback functionality in /sync --uninstall."""

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

    def test_rollback_after_uninstall(self, temp_project):
        """Test rollback restores files after uninstallation.

        REQUIREMENT: Integration must support rollback via orchestrator.
        Expected: Files restored from backup after uninstall.
        """
        dispatcher = SyncDispatcher(project_root=temp_project)

        # Execute uninstall
        result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True)
        backup_path = result.backup_path

        # Verify file removed
        claude_dir = temp_project / ".claude"
        assert not (claude_dir / "commands" / "auto-implement.md").exists()

        # Rollback
        orchestrator = UninstallOrchestrator(project_root=temp_project)
        rollback_result = orchestrator.rollback(backup_path=backup_path)

        assert rollback_result.status == "success"
        assert (claude_dir / "commands" / "auto-implement.md").exists()

    def test_rollback_with_invalid_backup(self, temp_project):
        """Test rollback handles invalid backup gracefully.

        REQUIREMENT: Rollback must validate backup before restoring.
        Expected: Returns failure with clear error for invalid backup.
        """
        orchestrator = UninstallOrchestrator(project_root=temp_project)

        invalid_backup = temp_project / "nonexistent_backup.tar.gz"

        rollback_result = orchestrator.rollback(backup_path=invalid_backup)

        assert rollback_result.status == "failure"
        assert any("backup" in err.lower() for err in rollback_result.errors)


class TestSyncUninstallGlobalDirectories:
    """Test uninstalling global ~/.claude/ and ~/.autonomous-dev/ directories."""

    @pytest.fixture
    def temp_global_install(self, tmp_path):
        """Create temporary global installation structure."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        # Create ~/.claude/ structure
        global_claude = home_dir / ".claude"
        global_claude.mkdir()
        (global_claude / "hooks").mkdir()
        (global_claude / "lib").mkdir()

        (global_claude / "hooks" / "auto_format.py").write_text("# Global hook")
        (global_claude / "lib" / "security_utils.py").write_text("# Global lib")

        # Create ~/.autonomous-dev/ structure
        autonomous_dev = home_dir / ".autonomous-dev"
        autonomous_dev.mkdir()
        (autonomous_dev / "user_state.json").write_text('{"initialized": true}')

        # Create install manifest in global location
        (global_claude / "config").mkdir()
        manifest = {
            "version": "3.40.0",
            "components": {
                "hooks": {
                    "target": ".claude/hooks",
                    "files": ["plugins/autonomous-dev/hooks/auto_format.py"]
                },
                "lib": {
                    "target": ".claude/lib",
                    "files": ["plugins/autonomous-dev/lib/security_utils.py"]
                }
            }
        }
        (global_claude / "config" / "install_manifest.json").write_text(json.dumps(manifest))

        return home_dir

    def test_uninstall_global_directories(self, temp_global_install):
        """Test uninstalling global ~/.claude/ directories.

        REQUIREMENT: Must support uninstalling global installations.
        Expected: Global files removed when project_root is home directory.
        """
        with patch('plugins.autonomous_dev.lib.uninstall_orchestrator.Path.home') as mock_home:
            mock_home.return_value = temp_global_install

            orchestrator = UninstallOrchestrator(project_root=temp_global_install)
            result = orchestrator.execute(force=True)

            assert result.status == "success"
            assert result.files_removed >= 2

            # Verify global files removed
            global_claude = temp_global_install / ".claude"
            assert not (global_claude / "hooks" / "auto_format.py").exists()
            assert not (global_claude / "lib" / "security_utils.py").exists()

    def test_local_only_skips_global_directories(self, temp_global_install, tmp_path):
        """Test --local-only preserves global directories.

        REQUIREMENT: --local-only must skip global ~/.claude/ directories.
        Expected: Global files preserved when local_only=True.
        """
        # Create project directory with local install
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

        with patch('plugins.autonomous_dev.lib.uninstall_orchestrator.Path.home') as mock_home:
            mock_home.return_value = temp_global_install

            dispatcher = SyncDispatcher(project_root=project_root)
            result = dispatcher.sync(mode=SyncMode.UNINSTALL, force=True, local_only=True)

            assert result.status == "success"

            # Local file removed
            assert not (claude_dir / "commands" / "auto-implement.md").exists()

            # Global files preserved
            global_claude = temp_global_install / ".claude"
            assert (global_claude / "hooks" / "auto_format.py").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
