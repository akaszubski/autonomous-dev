#!/usr/bin/env python3
"""
TDD Tests for sync_dispatcher.py CLI Wrapper (FAILING - Red Phase)

This module contains FAILING tests for the CLI wrapper functionality that will be
added to sync_dispatcher.py as an `if __name__ == "__main__":` block with argparse.

Requirements:
1. Parse CLI arguments for sync mode selection
2. Support --github (default), --env, --marketplace, --plugin-dev, --all flags
3. Enforce mutually exclusive flags (only one mode at a time)
4. Return appropriate exit codes (0=success, 1=failure, 2=invalid args)
5. Provide helpful error messages for invalid usage

Test Coverage Target: 100% of CLI argument parsing logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe CLI requirements
- Tests should FAIL until CLI wrapper is implemented
- Each test validates ONE CLI requirement

Author: test-master agent
Date: 2025-12-13
Issue: GitHub #127 - Add CLI wrapper to sync_dispatcher.py
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.sync_dispatcher import (
    SyncDispatcher,
    SyncResult,
    SyncMode,
)


class TestCLIArgumentParsing:
    """Test CLI argument parsing for sync mode selection."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_no_flags_defaults_to_github_mode(self, temp_project):
        """Test that no flags defaults to GITHUB mode.

        REQUIREMENT: Default behavior should fetch latest from GitHub.
        Expected: CLI with no flags → SyncMode.GITHUB
        """
        # Mock SyncDispatcher.dispatch to verify mode
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.GITHUB,
                message="GitHub sync completed"
            )

            # Import and run CLI (will fail until implemented)
            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    # This will fail - CLI wrapper not implemented yet
                    exit_code = sync_dispatcher.main()

            # Verify dispatch was called with GITHUB mode
            assert mock_dispatch.called
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == SyncMode.GITHUB
            assert exit_code == 0

    def test_explicit_github_flag_selects_github_mode(self, temp_project):
        """Test that --github flag explicitly selects GITHUB mode.

        REQUIREMENT: Users should be able to force GitHub sync mode.
        Expected: CLI with --github → SyncMode.GITHUB
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.GITHUB,
                message="GitHub sync completed"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py', '--github']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert mock_dispatch.called
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == SyncMode.GITHUB
            assert exit_code == 0

    def test_env_flag_selects_environment_mode(self, temp_project):
        """Test that --env flag selects ENVIRONMENT mode.

        REQUIREMENT: Support environment sync via sync-validator agent.
        Expected: CLI with --env → SyncMode.ENVIRONMENT
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.ENVIRONMENT,
                message="Environment sync completed"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py', '--env']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert mock_dispatch.called
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == SyncMode.ENVIRONMENT
            assert exit_code == 0

    def test_marketplace_flag_selects_marketplace_mode(self, temp_project):
        """Test that --marketplace flag selects MARKETPLACE mode.

        REQUIREMENT: Support marketplace updates from installed plugin.
        Expected: CLI with --marketplace → SyncMode.MARKETPLACE
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.MARKETPLACE,
                message="Marketplace sync completed"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py', '--marketplace']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert mock_dispatch.called
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == SyncMode.MARKETPLACE
            assert exit_code == 0

    def test_plugin_dev_flag_selects_plugin_dev_mode(self, temp_project):
        """Test that --plugin-dev flag selects PLUGIN_DEV mode.

        REQUIREMENT: Support plugin development workflow.
        Expected: CLI with --plugin-dev → SyncMode.PLUGIN_DEV
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.PLUGIN_DEV,
                message="Plugin dev sync completed"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py', '--plugin-dev']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert mock_dispatch.called
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == SyncMode.PLUGIN_DEV
            assert exit_code == 0

    def test_all_flag_selects_all_mode(self, temp_project):
        """Test that --all flag selects ALL mode.

        REQUIREMENT: Support running all sync modes sequentially.
        Expected: CLI with --all → SyncMode.ALL
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.ALL,
                message="All sync modes completed"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py', '--all']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert mock_dispatch.called
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == SyncMode.ALL
            assert exit_code == 0


class TestCLIMutualExclusion:
    """Test that CLI enforces mutually exclusive sync mode flags."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_multiple_flags_raises_error(self, temp_project):
        """Test that multiple sync mode flags raises error.

        REQUIREMENT: Only one sync mode allowed per invocation.
        Expected: CLI with --github --env → Error + exit code 2
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--github', '--env']):
            with patch('os.getcwd', return_value=str(temp_project)):
                with pytest.raises(SystemExit) as exc_info:
                    sync_dispatcher.main()

                # argparse exits with code 2 for argument errors
                assert exc_info.value.code == 2

    def test_marketplace_and_plugin_dev_raises_error(self, temp_project):
        """Test that --marketplace and --plugin-dev together raises error.

        REQUIREMENT: Prevent conflicting sync modes.
        Expected: CLI with --marketplace --plugin-dev → Error + exit code 2
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--marketplace', '--plugin-dev']):
            with patch('os.getcwd', return_value=str(temp_project)):
                with pytest.raises(SystemExit) as exc_info:
                    sync_dispatcher.main()

                assert exc_info.value.code == 2

    def test_all_with_other_flags_raises_error(self, temp_project):
        """Test that --all with other flags raises error.

        REQUIREMENT: --all mode cannot be combined with specific modes.
        Expected: CLI with --all --github → Error + exit code 2
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--all', '--github']):
            with patch('os.getcwd', return_value=str(temp_project)):
                with pytest.raises(SystemExit) as exc_info:
                    sync_dispatcher.main()

                assert exc_info.value.code == 2


class TestCLIInvalidArguments:
    """Test CLI error handling for invalid arguments."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_unknown_flag_raises_error(self, temp_project):
        """Test that unknown flags raise error.

        REQUIREMENT: Helpful errors for invalid arguments.
        Expected: CLI with --invalid → Error + exit code 2
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--invalid']):
            with patch('os.getcwd', return_value=str(temp_project)):
                with pytest.raises(SystemExit) as exc_info:
                    sync_dispatcher.main()

                # argparse exits with code 2 for unrecognized arguments
                assert exc_info.value.code == 2

    def test_help_flag_shows_usage(self, temp_project):
        """Test that --help flag shows usage and exits.

        REQUIREMENT: Provide help documentation via --help.
        Expected: CLI with --help → Usage message + exit code 0
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--help']):
            with patch('os.getcwd', return_value=str(temp_project)):
                with pytest.raises(SystemExit) as exc_info:
                    sync_dispatcher.main()

                # argparse exits with code 0 for --help
                assert exc_info.value.code == 0


class TestCLIExitCodes:
    """Test CLI exit codes for different scenarios."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_success_returns_exit_code_zero(self, temp_project):
        """Test that successful sync returns exit code 0.

        REQUIREMENT: Standard Unix exit codes (0 = success).
        Expected: Successful sync → exit code 0
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.GITHUB,
                message="Sync completed"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert exit_code == 0

    def test_sync_failure_returns_exit_code_one(self, temp_project):
        """Test that sync failure returns exit code 1.

        REQUIREMENT: Standard Unix exit codes (1 = failure).
        Expected: Failed sync → exit code 1
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=False,
                mode=SyncMode.GITHUB,
                message="Sync failed",
                error="Network error"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert exit_code == 1

    def test_invalid_arguments_returns_exit_code_two(self, temp_project):
        """Test that invalid arguments return exit code 2.

        REQUIREMENT: Standard Unix exit codes (2 = invalid args).
        Expected: Invalid arguments → exit code 2
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--invalid']):
            with patch('os.getcwd', return_value=str(temp_project)):
                with pytest.raises(SystemExit) as exc_info:
                    sync_dispatcher.main()

                assert exc_info.value.code == 2

    def test_exception_during_sync_returns_exit_code_one(self, temp_project):
        """Test that unexpected exceptions return exit code 1.

        REQUIREMENT: Handle unexpected errors gracefully.
        Expected: Exception during sync → exit code 1
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.side_effect = Exception("Unexpected error")

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

            assert exit_code == 1


class TestCLIOutputFormatting:
    """Test CLI output formatting for user feedback."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_success_prints_result_message(self, temp_project, capsys):
        """Test that successful sync prints result message.

        REQUIREMENT: Provide clear feedback on sync outcome.
        Expected: Success → prints SyncResult.message
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.GITHUB,
                message="GitHub sync completed: 47 files updated"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py', '--github']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    sync_dispatcher.main()

            captured = capsys.readouterr()
            assert "GitHub sync completed" in captured.out
            assert "47 files updated" in captured.out

    def test_failure_prints_error_message(self, temp_project, capsys):
        """Test that failed sync prints error message.

        REQUIREMENT: Provide clear error messages for failures.
        Expected: Failure → prints error to stderr
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=False,
                mode=SyncMode.GITHUB,
                message="Sync failed",
                error="Network timeout"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    sync_dispatcher.main()

            captured = capsys.readouterr()
            # Error should be printed to stderr
            assert "failed" in captured.err.lower() or "error" in captured.err.lower()

    def test_verbose_output_shows_mode_selection(self, temp_project, capsys):
        """Test that CLI shows which mode was selected (optional verbose output).

        REQUIREMENT: Transparency in mode selection for debugging.
        Expected: Output indicates selected sync mode
        """
        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.ENVIRONMENT,
                message="Environment sync completed"
            )

            from plugins.autonomous_dev.lib import sync_dispatcher

            with patch('sys.argv', ['sync_dispatcher.py', '--env']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    sync_dispatcher.main()

            captured = capsys.readouterr()
            # Output should indicate mode (either explicitly or via message)
            output = captured.out + captured.err
            assert "environment" in output.lower() or "ENVIRONMENT" in output


class TestCLIProjectPathHandling:
    """Test CLI handling of project path detection."""

    def test_uses_current_directory_as_project_root(self, tmp_path):
        """Test that CLI uses current working directory as project root.

        REQUIREMENT: Auto-detect project root from cwd.
        Expected: CLI passes cwd to SyncDispatcher
        """
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()

        with patch.object(SyncDispatcher, '__init__', return_value=None) as mock_init:
            with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
                mock_dispatch.return_value = SyncResult(
                    success=True,
                    mode=SyncMode.GITHUB,
                    message="Sync completed"
                )

                from plugins.autonomous_dev.lib import sync_dispatcher

                with patch('sys.argv', ['sync_dispatcher.py']):
                    with patch('os.getcwd', return_value=str(project_root)):
                        sync_dispatcher.main()

                # Verify SyncDispatcher was initialized with project root
                assert mock_init.called
                call_args = mock_init.call_args
                # Check if project_root is in kwargs or args
                assert str(project_root) in str(call_args)

    def test_handles_missing_project_directory_gracefully(self, tmp_path):
        """Test that CLI handles invalid project directory gracefully.

        REQUIREMENT: Helpful errors for missing project directory.
        Expected: Clear error message + exit code 1
        """
        # Use non-existent directory
        nonexistent = tmp_path / "does_not_exist"

        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py']):
            with patch('os.getcwd', return_value=str(nonexistent)):
                exit_code = sync_dispatcher.main()

        # Should fail gracefully with exit code 1
        assert exit_code == 1
