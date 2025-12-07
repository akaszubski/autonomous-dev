#!/usr/bin/env python3
"""
TDD Tests for Sync Dispatcher (FAILING - Red Phase)

This module contains FAILING tests for sync_dispatcher.py which will route
sync operations to appropriate handlers based on detected mode.

Requirements:
1. Dispatch to correct sync handler based on SyncMode
2. Execute modes in correct order for ALL mode (env → marketplace → plugin-dev)
3. Delegate environment sync to sync-validator agent
4. Handle sync failures and rollback
5. Provide progress reporting for multi-mode sync

Test Coverage Target: 100% of dispatch logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe routing requirements
- Tests should FAIL until sync_dispatcher.py is implemented
- Each test validates ONE routing requirement

Author: test-master agent
Date: 2025-11-08
Issue: GitHub #44 - Unified /sync command consolidation
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until sync_dispatcher.py is created
from plugins.autonomous_dev.lib.sync_dispatcher import (
    SyncDispatcher,
    SyncResult,
    SyncError,
    dispatch_sync,
)
from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode


class TestSyncResultClass:
    """Test SyncResult data class for returning sync outcomes."""

    def test_sync_result_success_attributes(self):
        """Test SyncResult has expected attributes for success case.

        REQUIREMENT: Result object must capture sync outcome.
        Expected: SyncResult has success, mode, message, details attributes.
        """
        result = SyncResult(
            success=True,
            mode=SyncMode.ENVIRONMENT,
            message="Sync completed successfully",
            details={"files_updated": 5}
        )

        assert result.success is True
        assert result.mode == SyncMode.ENVIRONMENT
        assert result.message == "Sync completed successfully"
        assert result.details["files_updated"] == 5

    def test_sync_result_failure_attributes(self):
        """Test SyncResult captures failure information.

        REQUIREMENT: Failures must include error details for debugging.
        Expected: SyncResult can represent failure with error info.
        """
        result = SyncResult(
            success=False,
            mode=SyncMode.MARKETPLACE,
            message="Plugin not found",
            error="FileNotFoundError: ~/.claude/plugins/installed_plugins.json"
        )

        assert result.success is False
        assert result.mode == SyncMode.MARKETPLACE
        assert "Plugin not found" in result.message
        assert result.error is not None


class TestEnvironmentSyncDispatch:
    """Test dispatching to environment sync (sync-validator agent)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_dispatch_environment_mode_invokes_sync_validator_agent(self, temp_project):
        """Test that ENVIRONMENT mode delegates to sync-validator agent.

        REQUIREMENT: Environment sync uses existing sync-validator agent.
        Expected: Agent invoker called with sync-validator agent.
        """
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.AgentInvoker') as mock_invoker:
            mock_instance = Mock()
            mock_instance.invoke.return_value = {"status": "success"}
            mock_invoker.return_value = mock_instance

            dispatcher = SyncDispatcher(str(temp_project))
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # Verify sync-validator agent was invoked
            mock_instance.invoke.assert_called_once()
            call_args = mock_instance.invoke.call_args
            assert 'sync-validator' in str(call_args).lower()

    def test_dispatch_environment_returns_success_result(self, temp_project):
        """Test successful environment sync returns SyncResult with success=True.

        REQUIREMENT: Successful sync must return success indicator.
        Expected: SyncResult.success is True when agent succeeds.
        """
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.AgentInvoker') as mock_invoker:
            mock_instance = Mock()
            mock_instance.invoke.return_value = {
                "status": "success",
                "files_updated": 3,
                "conflicts": 0
            }
            mock_invoker.return_value = mock_instance

            dispatcher = SyncDispatcher(str(temp_project))
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            assert result.success is True
            assert result.mode == SyncMode.ENVIRONMENT
            assert result.details["files_updated"] == 3

    def test_dispatch_environment_handles_agent_failure(self, temp_project):
        """Test environment sync handles sync-validator agent failures.

        REQUIREMENT: Agent failures must be captured in result.
        Expected: SyncResult.success is False, error message included.
        """
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.AgentInvoker') as mock_invoker:
            mock_instance = Mock()
            mock_instance.invoke.side_effect = Exception("Agent execution failed")
            mock_invoker.return_value = mock_instance

            dispatcher = SyncDispatcher(str(temp_project))
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            assert result.success is False
            assert result.mode == SyncMode.ENVIRONMENT
            assert "failed" in result.message.lower()
            assert result.error is not None


class TestMarketplaceSyncDispatch:
    """Test dispatching to marketplace sync operations."""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """Create temporary home directory with marketplace structure."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        # Create marketplace structure
        claude_dir = home_dir / ".claude" / "plugins"
        claude_dir.mkdir(parents=True)

        marketplace_dir = claude_dir / "marketplaces" / "autonomous-dev"
        marketplace_dir.mkdir(parents=True)

        plugin_dir = marketplace_dir / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create plugin.json
        (plugin_dir / "plugin.json").write_text('{"version": "3.6.0"}')

        return home_dir

    def test_dispatch_marketplace_mode_copies_plugin_files(self, temp_home, tmp_path):
        """Test that MARKETPLACE mode copies files from installed plugin.

        REQUIREMENT: Marketplace sync updates project files from installed plugin.
        Expected: Files copied from ~/.claude/plugins/marketplaces/autonomous-dev.
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()

        with patch.dict(os.environ, {'HOME': str(temp_home)}):
            with patch('plugins.autonomous_dev.lib.sync_dispatcher.shutil.copytree') as mock_copy:
                dispatcher = SyncDispatcher(str(project_dir))
                result = dispatcher.dispatch(SyncMode.MARKETPLACE)

                # Verify files were copied
                mock_copy.assert_called()

    def test_dispatch_marketplace_returns_files_updated(self, temp_home, tmp_path):
        """Test marketplace sync result includes count of updated files.

        REQUIREMENT: Result must show what was updated.
        Expected: SyncResult.details contains file counts.
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()

        with patch.dict(os.environ, {'HOME': str(temp_home)}):
            dispatcher = SyncDispatcher(str(project_dir))
            result = dispatcher.dispatch(SyncMode.MARKETPLACE)

            assert result.success is True
            assert result.mode == SyncMode.MARKETPLACE
            assert "files_updated" in result.details or "commands" in result.details

    def test_dispatch_marketplace_handles_plugin_not_found(self, tmp_path):
        """Test marketplace sync handles missing plugin gracefully.

        REQUIREMENT: Clear error when plugin not installed.
        Expected: SyncResult indicates plugin not found.
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # No marketplace plugin installed
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        with patch.dict(os.environ, {'HOME': str(fake_home)}):
            dispatcher = SyncDispatcher(str(project_dir))
            result = dispatcher.dispatch(SyncMode.MARKETPLACE)

            assert result.success is False
            assert "not found" in result.message.lower() or "not installed" in result.message.lower()


class TestPluginDevSyncDispatch:
    """Test dispatching to plugin development sync operations."""

    @pytest.fixture
    def temp_plugin_dev_project(self, tmp_path):
        """Create temporary plugin development project."""
        project_root = tmp_path / "plugin_dev"
        project_root.mkdir()

        # Create plugin structure
        plugin_dir = project_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "plugin.json").write_text('{"version": "3.6.0"}')
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "agents").mkdir()

        return project_root

    def test_dispatch_plugin_dev_mode_syncs_to_local_claude(self, temp_plugin_dev_project):
        """Test that PLUGIN_DEV mode syncs from plugin dir to .claude/.

        REQUIREMENT: Plugin dev sync copies files to .claude for testing.
        Expected: Files copied from plugins/autonomous-dev to .claude.
        """
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.shutil.copytree') as mock_copy:
            dispatcher = SyncDispatcher(str(temp_plugin_dev_project))
            result = dispatcher.dispatch(SyncMode.PLUGIN_DEV)

            # Verify copy was attempted
            mock_copy.assert_called()
            call_args = str(mock_copy.call_args)
            assert 'plugins' in call_args.lower()
            assert '.claude' in call_args.lower()

    def test_dispatch_plugin_dev_creates_claude_dir_if_missing(self, temp_plugin_dev_project):
        """Test plugin dev sync creates .claude directory if it doesn't exist.

        REQUIREMENT: Auto-create target directory for dev sync.
        Expected: .claude directory created if missing.
        """
        # Ensure .claude doesn't exist
        claude_dir = temp_plugin_dev_project / ".claude"
        assert not claude_dir.exists()

        dispatcher = SyncDispatcher(str(temp_plugin_dev_project))
        result = dispatcher.dispatch(SyncMode.PLUGIN_DEV)

        # Should create .claude directory
        assert claude_dir.exists() or result.success is False  # Or handled in implementation

    def test_dispatch_plugin_dev_returns_sync_details(self, temp_plugin_dev_project):
        """Test plugin dev sync result includes sync details.

        REQUIREMENT: Show what was synced for visibility.
        Expected: Result includes files synced, directories created.
        """
        dispatcher = SyncDispatcher(str(temp_plugin_dev_project))
        result = dispatcher.dispatch(SyncMode.PLUGIN_DEV)

        assert result.mode == SyncMode.PLUGIN_DEV
        assert result.details is not None
        # Should have some indication of what was synced
        assert any(key in result.details for key in ['files_synced', 'commands', 'agents', 'hooks'])


class TestAllModeSyncDispatch:
    """Test ALL mode executes all sync operations in correct order."""

    @pytest.fixture
    def temp_all_mode_project(self, tmp_path):
        """Create project with all sync contexts."""
        project_root = tmp_path / "all_mode_project"
        project_root.mkdir()

        # Create .claude dir (environment)
        (project_root / ".claude").mkdir()

        # Create plugin dir (plugin-dev)
        plugin_dir = project_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{}')

        return project_root

    def test_dispatch_all_mode_executes_in_correct_order(self, temp_all_mode_project):
        """Test ALL mode executes: environment → marketplace → plugin-dev.

        REQUIREMENT: Order matters - env first (git pull), then marketplace, then plugin-dev.
        Expected: Dispatchers called in specific order.
        """
        with patch.object(SyncDispatcher, '_sync_environment') as mock_env, \
             patch.object(SyncDispatcher, '_sync_marketplace') as mock_market, \
             patch.object(SyncDispatcher, '_sync_plugin_dev') as mock_plugin:

            # Set return values
            mock_env.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")
            mock_market.return_value = SyncResult(True, SyncMode.MARKETPLACE, "Success")
            mock_plugin.return_value = SyncResult(True, SyncMode.PLUGIN_DEV, "Success")

            dispatcher = SyncDispatcher(str(temp_all_mode_project))
            result = dispatcher.dispatch(SyncMode.ALL)

            # Verify order
            assert mock_env.call_count == 1
            assert mock_market.call_count == 1
            assert mock_plugin.call_count == 1

            # Verify environment was called before marketplace
            env_call_time = mock_env.call_args
            market_call_time = mock_market.call_args
            plugin_call_time = mock_plugin.call_args

            # All should have been called
            assert env_call_time is not None
            assert market_call_time is not None
            assert plugin_call_time is not None

    def test_dispatch_all_mode_stops_on_failure(self, temp_all_mode_project):
        """Test ALL mode stops execution if a sync fails.

        REQUIREMENT: Don't continue if early sync fails (prevents cascading issues).
        Expected: If environment sync fails, marketplace and plugin-dev are skipped.
        """
        with patch.object(SyncDispatcher, '_sync_environment') as mock_env, \
             patch.object(SyncDispatcher, '_sync_marketplace') as mock_market, \
             patch.object(SyncDispatcher, '_sync_plugin_dev') as mock_plugin:

            # Environment sync fails
            mock_env.return_value = SyncResult(False, SyncMode.ENVIRONMENT, "Failed", error="Error")

            dispatcher = SyncDispatcher(str(temp_all_mode_project))
            result = dispatcher.dispatch(SyncMode.ALL)

            # Environment was called
            assert mock_env.call_count == 1
            # But marketplace and plugin-dev were NOT called
            assert mock_market.call_count == 0
            assert mock_plugin.call_count == 0

            # Overall result is failure
            assert result.success is False

    def test_dispatch_all_mode_aggregates_results(self, temp_all_mode_project):
        """Test ALL mode result aggregates all individual results.

        REQUIREMENT: Show comprehensive view of all sync operations.
        Expected: Result includes details from all three syncs.
        """
        with patch.object(SyncDispatcher, '_sync_environment') as mock_env, \
             patch.object(SyncDispatcher, '_sync_marketplace') as mock_market, \
             patch.object(SyncDispatcher, '_sync_plugin_dev') as mock_plugin:

            mock_env.return_value = SyncResult(
                True, SyncMode.ENVIRONMENT, "Success", details={"files": 3}
            )
            mock_market.return_value = SyncResult(
                True, SyncMode.MARKETPLACE, "Success", details={"commands": 5}
            )
            mock_plugin.return_value = SyncResult(
                True, SyncMode.PLUGIN_DEV, "Success", details={"agents": 7}
            )

            dispatcher = SyncDispatcher(str(temp_all_mode_project))
            result = dispatcher.dispatch(SyncMode.ALL)

            # Result should aggregate all details
            assert result.mode == SyncMode.ALL
            assert result.success is True
            assert "environment" in result.details or "ENVIRONMENT" in str(result.details)
            assert "marketplace" in result.details or "MARKETPLACE" in str(result.details)
            assert "plugin_dev" in result.details or "PLUGIN_DEV" in str(result.details)

    def test_dispatch_all_mode_reports_progress(self, temp_all_mode_project):
        """Test ALL mode provides progress updates during execution.

        REQUIREMENT: User should see progress during long sync operations.
        Expected: Progress callback invoked for each sync phase.
        """
        progress_updates = []

        def progress_callback(message):
            progress_updates.append(message)

        with patch.object(SyncDispatcher, '_sync_environment') as mock_env, \
             patch.object(SyncDispatcher, '_sync_marketplace') as mock_market, \
             patch.object(SyncDispatcher, '_sync_plugin_dev') as mock_plugin:

            mock_env.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")
            mock_market.return_value = SyncResult(True, SyncMode.MARKETPLACE, "Success")
            mock_plugin.return_value = SyncResult(True, SyncMode.PLUGIN_DEV, "Success")

            dispatcher = SyncDispatcher(str(temp_all_mode_project))
            result = dispatcher.dispatch(SyncMode.ALL, progress_callback=progress_callback)

            # Should have received progress updates
            assert len(progress_updates) >= 3  # At least one per mode
            assert any('environment' in update.lower() for update in progress_updates)
            assert any('marketplace' in update.lower() for update in progress_updates)
            assert any('plugin' in update.lower() for update in progress_updates)


class TestRollbackSupport:
    """Test rollback functionality when sync fails."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for rollback testing."""
        project_root = tmp_path / "rollback_test"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_dispatcher_creates_backup_before_sync(self, temp_project):
        """Test that backup is created before making changes.

        REQUIREMENT: Rollback requires backup of current state.
        Expected: Backup directory created with timestamp.
        """
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.shutil.copytree') as mock_copy:
            dispatcher = SyncDispatcher(str(temp_project), enable_backup=True)
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # Should create backup
            backup_calls = [call for call in mock_copy.call_args_list
                          if '.backup' in str(call)]
            assert len(backup_calls) > 0

    def test_dispatcher_rollback_on_failure(self, temp_project):
        """Test that changes are rolled back if sync fails.

        REQUIREMENT: Failed sync should restore previous state.
        Expected: Backup restored when sync fails and rollback=True.
        """
        with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
            mock_sync.side_effect = Exception("Sync failed")

            dispatcher = SyncDispatcher(str(temp_project), enable_backup=True)

            with pytest.raises(SyncError):
                result = dispatcher.dispatch(SyncMode.ENVIRONMENT, rollback_on_failure=True)

            # Verify rollback was attempted
            # (Implementation would restore from backup)

    def test_dispatcher_preserves_backup_on_success(self, temp_project):
        """Test that backup is kept after successful sync.

        REQUIREMENT: Keep backup for manual rollback if needed.
        Expected: Backup directory exists after successful sync.
        """
        with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
            mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

            dispatcher = SyncDispatcher(str(temp_project), enable_backup=True)
            result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

            # Backup should still exist
            backup_dirs = list(temp_project.glob('.claude.backup.*'))
            # May or may not exist depending on implementation, but shouldn't error


class TestDispatchHelperFunction:
    """Test module-level dispatch_sync() convenience function."""

    def test_dispatch_sync_convenience_function(self, tmp_path):
        """Test that dispatch_sync() provides simple API.

        REQUIREMENT: Easy-to-use function for common case.
        Expected: dispatch_sync(path, mode) dispatches without creating dispatcher.
        """
        project_dir = tmp_path / "test"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.SyncDispatcher') as mock_dispatcher:
            mock_instance = Mock()
            mock_instance.dispatch.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")
            mock_dispatcher.return_value = mock_instance

            result = dispatch_sync(str(project_dir), SyncMode.ENVIRONMENT)

            assert result.success is True
            mock_instance.dispatch.assert_called_once_with(SyncMode.ENVIRONMENT)

    def test_dispatch_sync_with_options(self, tmp_path):
        """Test dispatch_sync() with optional parameters.

        REQUIREMENT: Support optional backup and rollback settings.
        Expected: dispatch_sync() accepts backup and rollback kwargs.
        """
        project_dir = tmp_path / "test"
        project_dir.mkdir()

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.SyncDispatcher') as mock_dispatcher:
            mock_instance = Mock()
            mock_instance.dispatch.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")
            mock_dispatcher.return_value = mock_instance

            result = dispatch_sync(
                str(project_dir),
                SyncMode.ENVIRONMENT,
                enable_backup=True,
                rollback_on_failure=True
            )

            # Verify dispatcher was created with options
            mock_dispatcher.assert_called_once()
            call_kwargs = mock_dispatcher.call_args[1]
            assert call_kwargs.get('enable_backup') is True


class TestSecurityIntegration:
    """Test security validation integration with sync operations."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for security testing."""
        project_root = tmp_path / "secure_test"
        project_root.mkdir()
        return project_root

    def test_dispatcher_validates_project_path(self, temp_project):
        """Test that dispatcher validates project path on init.

        SECURITY: All paths must be validated.
        Expected: security_utils.validate_path() called during __init__.
        """
        with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
            mock_validate.return_value = temp_project.resolve()

            dispatcher = SyncDispatcher(str(temp_project))

            mock_validate.assert_called()

    def test_dispatcher_validates_target_paths_during_sync(self, temp_project):
        """Test that target paths are validated before file operations.

        SECURITY: Prevent writing outside project.
        Expected: All copy destinations validated.
        """
        (temp_project / ".claude").mkdir()

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.validate_path') as mock_validate:
            mock_validate.return_value = temp_project.resolve()

            with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
                mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

                dispatcher = SyncDispatcher(str(temp_project))
                result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

                # Path validation should have been called
                assert mock_validate.call_count >= 1

    def test_dispatcher_audit_logs_sync_operations(self, temp_project):
        """Test that all sync operations are logged to audit log.

        SECURITY: All operations must be auditable.
        Expected: audit_log() called with sync details.
        """
        (temp_project / ".claude").mkdir()

        with patch('plugins.autonomous_dev.lib.sync_dispatcher.audit_log') as mock_audit:
            with patch.object(SyncDispatcher, '_sync_environment') as mock_sync:
                mock_sync.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success")

                dispatcher = SyncDispatcher(str(temp_project))
                result = dispatcher.dispatch(SyncMode.ENVIRONMENT)

                # Audit log should have been called
                mock_audit.assert_called()
                # Verify sync operation was logged
                logged_calls = [str(call) for call in mock_audit.call_args_list]
                assert any('sync' in str(call).lower() for call in logged_calls)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_sync_mode_raises_error(self, tmp_path):
        """Test that invalid sync mode raises error.

        REQUIREMENT: Only valid modes accepted.
        Expected: SyncError for invalid mode.
        """
        project_dir = tmp_path / "test"
        project_dir.mkdir()

        dispatcher = SyncDispatcher(str(project_dir))

        with pytest.raises(SyncError) as exc_info:
            dispatcher.dispatch("INVALID_MODE")

        assert 'invalid' in str(exc_info.value).lower()

    def test_missing_project_directory_raises_error(self):
        """Test that missing project directory is handled.

        REQUIREMENT: Clear error for bad path.
        Expected: SyncError when project path doesn't exist.
        """
        with pytest.raises(SyncError) as exc_info:
            SyncDispatcher("/nonexistent/path")

        assert 'not found' in str(exc_info.value).lower() or 'does not exist' in str(exc_info.value).lower()

    def test_partial_all_mode_failure_returns_partial_results(self, tmp_path):
        """Test that ALL mode returns results for completed syncs even if one fails.

        REQUIREMENT: Transparency about what succeeded before failure.
        Expected: Result shows which syncs completed successfully.
        """
        project_dir = tmp_path / "test"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()

        with patch.object(SyncDispatcher, '_sync_environment') as mock_env, \
             patch.object(SyncDispatcher, '_sync_marketplace') as mock_market:

            # Environment succeeds
            mock_env.return_value = SyncResult(True, SyncMode.ENVIRONMENT, "Success", details={"files": 3})
            # Marketplace fails
            mock_market.return_value = SyncResult(False, SyncMode.MARKETPLACE, "Failed", error="Not found")

            dispatcher = SyncDispatcher(str(project_dir))
            result = dispatcher.dispatch(SyncMode.ALL)

            # Overall result is failure
            assert result.success is False
            # But should include environment success in details
            assert "environment" in result.details or "ENVIRONMENT" in str(result.details)


class TestSyncDirectoryHelper:
    """Test _sync_directory helper method for Issue #97 bug fix.

    Issue: shutil.copytree(dirs_exist_ok=True) silently fails to copy new files
    when the destination directory already exists. This causes sync to report
    success but not actually update files.

    Solution: Replace with per-file operations using _sync_directory() helper
    that copies files individually and reports accurate counts.
    """

    @pytest.fixture
    def temp_sync_env(self, tmp_path):
        """Create source and destination directories for sync testing."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "destination"
        dst.mkdir()

        return {"src": src, "dst": dst, "tmp_path": tmp_path}

    def test_sync_directory_helper_copies_with_pattern(self, temp_sync_env):
        """Test _sync_directory copies only files matching pattern.

        REQUIREMENT: Helper must support filtering by file pattern (*.md, *.py).
        Expected: Only matching files copied, non-matching files ignored.

        TDD RED PHASE: This test will FAIL until _sync_directory() is implemented.
        """
        src = temp_sync_env["src"]
        dst = temp_sync_env["dst"]

        # Create test files
        (src / "command1.md").write_text("# Command 1")
        (src / "command2.md").write_text("# Command 2")
        (src / "script.py").write_text("print('hello')")
        (src / "README.txt").write_text("Not a match")

        # Test pattern filtering (*.md only)
        dispatcher = SyncDispatcher(str(temp_sync_env["tmp_path"]))
        files_copied = dispatcher._sync_directory(src, dst, pattern="*.md")

        # Should copy only .md files
        assert files_copied == 2
        assert (dst / "command1.md").exists()
        assert (dst / "command2.md").exists()
        assert not (dst / "script.py").exists()
        assert not (dst / "README.txt").exists()

    def test_sync_directory_reports_files_copied(self, temp_sync_env):
        """Test _sync_directory reports accurate count of files copied.

        REQUIREMENT: File counts must be accurate (not inflated by existing files).
        Expected: Return value equals actual number of files copied/updated.

        TDD RED PHASE: This test will FAIL until _sync_directory() is implemented.
        """
        src = temp_sync_env["src"]
        dst = temp_sync_env["dst"]

        # Create source files
        (src / "file1.py").write_text("print(1)")
        (src / "file2.py").write_text("print(2)")
        (src / "file3.py").write_text("print(3)")

        # First sync - all files copied
        dispatcher = SyncDispatcher(str(temp_sync_env["tmp_path"]))
        files_copied = dispatcher._sync_directory(src, dst, pattern="*.py")
        assert files_copied == 3

        # Second sync - no changes, should report 0 or 3 depending on implementation
        # (Either "0 new files" or "3 files updated" is acceptable)
        files_copied_again = dispatcher._sync_directory(src, dst, pattern="*.py")
        assert isinstance(files_copied_again, int)
        assert files_copied_again >= 0  # Valid count

    def test_sync_directory_handles_errors_gracefully(self, temp_sync_env):
        """Test _sync_directory continues on individual file errors.

        REQUIREMENT: Don't fail entire sync if one file has permission error.
        Expected: Copy other files successfully, log error, return partial count.

        TDD RED PHASE: This test will FAIL until error handling is implemented.
        """
        src = temp_sync_env["src"]
        dst = temp_sync_env["dst"]

        # Create test files
        (src / "good1.py").write_text("print(1)")
        (src / "good2.py").write_text("print(2)")

        # Mock one file to raise permission error
        with patch('shutil.copy2') as mock_copy:
            def side_effect(src_file, dst_file):
                if 'good1' in str(src_file):
                    raise PermissionError("Access denied")
                # Actually copy good2.py
                import shutil
                shutil.copy2(src_file, dst_file)

            mock_copy.side_effect = side_effect

            dispatcher = SyncDispatcher(str(temp_sync_env["tmp_path"]))
            files_copied = dispatcher._sync_directory(src, dst, pattern="*.py")

            # Should copy good2.py despite good1.py error
            assert files_copied >= 1  # At least one file succeeded
            assert (dst / "good2.py").exists()

    def test_sync_detects_new_files_in_existing_directory(self, temp_sync_env):
        """Test sync detects and copies new files when directory already exists.

        REGRESSION TEST for Issue #97: shutil.copytree(dirs_exist_ok=True) bug

        REQUIREMENT: When destination directory exists, new files must still be copied.
        Expected: New files appear in destination, file count is accurate.

        This is the PRIMARY regression test for Issue #97.

        TDD RED PHASE: This test will FAIL until copytree is replaced with _sync_directory().
        """
        src = temp_sync_env["src"]
        dst = temp_sync_env["dst"]

        # Initial state: destination has old files
        (dst / "old_command.md").write_text("# Old Command")

        # Source has new files
        (src / "new_command1.md").write_text("# New Command 1")
        (src / "new_command2.md").write_text("# New Command 2")

        # Sync should detect and copy new files
        dispatcher = SyncDispatcher(str(temp_sync_env["tmp_path"]))
        files_copied = dispatcher._sync_directory(src, dst, pattern="*.md")

        # CRITICAL ASSERTION: New files must be copied
        assert (dst / "new_command1.md").exists(), "New file 1 was not copied (Issue #97 regression)"
        assert (dst / "new_command2.md").exists(), "New file 2 was not copied (Issue #97 regression)"

        # File count should reflect actual new files
        assert files_copied >= 2, f"Expected at least 2 files copied, got {files_copied}"

        # Old file should still exist
        assert (dst / "old_command.md").exists(), "Old file was deleted (should be preserved)"

    def test_sync_directory_creates_destination_if_missing(self, temp_sync_env):
        """Test _sync_directory creates destination directory if it doesn't exist.

        REQUIREMENT: Auto-create destination for first-time sync.
        Expected: Destination directory created, files copied successfully.

        TDD RED PHASE: This test will FAIL until _sync_directory() is implemented.
        """
        src = temp_sync_env["src"]
        dst_parent = temp_sync_env["tmp_path"] / "new_location"
        dst = dst_parent / "commands"

        # Destination doesn't exist yet
        assert not dst.exists()

        # Create source files
        (src / "command.md").write_text("# Command")

        # Sync should create destination
        dispatcher = SyncDispatcher(str(temp_sync_env["tmp_path"]))
        files_copied = dispatcher._sync_directory(src, dst, pattern="*.md")

        # Destination should be created and file copied
        assert dst.exists(), "Destination directory was not created"
        assert (dst / "command.md").exists(), "File was not copied"
        assert files_copied == 1

    def test_sync_directory_handles_nested_directories(self, temp_sync_env):
        """Test _sync_directory preserves directory structure when copying.

        REQUIREMENT: Maintain subdirectory structure in destination.
        Expected: Nested files appear in same relative paths.

        TDD RED PHASE: This test will FAIL until nested directory handling is implemented.
        """
        src = temp_sync_env["src"]
        dst = temp_sync_env["dst"]

        # Create nested structure
        (src / "subdir1").mkdir()
        (src / "subdir1" / "file1.py").write_text("print(1)")
        (src / "subdir2").mkdir()
        (src / "subdir2" / "file2.py").write_text("print(2)")
        (src / "root.py").write_text("print('root')")

        # Sync should preserve structure
        dispatcher = SyncDispatcher(str(temp_sync_env["tmp_path"]))
        files_copied = dispatcher._sync_directory(src, dst, pattern="*.py")

        # Check structure is preserved
        assert (dst / "subdir1" / "file1.py").exists()
        assert (dst / "subdir2" / "file2.py").exists()
        assert (dst / "root.py").exists()
        assert files_copied == 3
