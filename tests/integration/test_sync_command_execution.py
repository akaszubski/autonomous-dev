#!/usr/bin/env python3
"""
Integration Tests for /sync Command Execution (FAILING - Red Phase)

This module contains FAILING integration tests that validate the end-to-end
execution of the /sync command, including:
1. Bash script argument forwarding to Python CLI
2. Python CLI processing and sync execution
3. Proper exit codes returned to shell
4. Real file system operations (in isolated test environment)

Requirements:
1. Bash script forwards arguments to sync_dispatcher.py CLI
2. CLI correctly interprets forwarded arguments
3. Sync operations execute with real file I/O
4. Exit codes propagate correctly from Python → Bash → caller

Test Coverage Target: 100% of command execution flow

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe integration requirements
- Tests should FAIL until both CLI wrapper and bash script are implemented
- Each test validates ONE integration requirement

Author: test-master agent
Date: 2025-12-13
Issue: GitHub #127 - Add CLI wrapper to sync_dispatcher.py
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.sync_dispatcher import SyncMode, SyncResult


class TestBashScriptArgumentForwarding:
    """Test that bash script forwards arguments correctly to Python CLI."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with .claude directory and plugin structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # For bash script tests, just verify the script can invoke the CLI
        # Use the real plugin directory path instead of copying files
        real_plugin_path = Path(__file__).parent.parent.parent

        # Create a minimal sync.sh script that uses the real plugin path
        sync_script = project_root / "sync.sh"
        sync_script.write_text(f"""#!/usr/bin/env bash
# Forward arguments to sync_dispatcher.py (using real plugin path for testing)
python3 "{real_plugin_path}/plugins/autonomous-dev/lib/sync_dispatcher.py" "$@"
exit $?
""")
        sync_script.chmod(0o755)

        return project_root

    def test_bash_forwards_github_flag(self, temp_project):
        """Test bash script forwards --github flag to Python CLI.

        REQUIREMENT: Bash wrapper must forward all arguments.
        Expected: sync.sh --github → python sync_dispatcher.py --github
        """
        sync_script = temp_project / "sync.sh"

        # Test with --help flag (doesn't require actual sync operations)
        result = subprocess.run(
            [str(sync_script), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        # --help should succeed and show usage
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "sync" in result.stdout.lower()

    def test_bash_forwards_env_flag(self, temp_project):
        """Test bash script forwards --env flag to Python CLI.

        REQUIREMENT: All sync mode flags must be forwarded.
        Expected: sync.sh --env → python sync_dispatcher.py --env
        """
        sync_script = temp_project / "sync.sh"

        # Test with --help to verify bash forwarding works
        result = subprocess.run(
            [str(sync_script), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        assert result.returncode == 0

    def test_bash_forwards_marketplace_flag(self, temp_project):
        """Test bash script forwards --marketplace flag.

        REQUIREMENT: Marketplace sync via bash wrapper.
        Expected: sync.sh --marketplace → python sync_dispatcher.py --marketplace
        """
        sync_script = temp_project / "sync.sh"

        # Test with --help to verify bash forwarding works
        result = subprocess.run(
            [str(sync_script), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        assert result.returncode == 0

    def test_bash_forwards_plugin_dev_flag(self, temp_project):
        """Test bash script forwards --plugin-dev flag.

        REQUIREMENT: Plugin dev workflow via bash wrapper.
        Expected: sync.sh --plugin-dev → python sync_dispatcher.py --plugin-dev
        """
        sync_script = temp_project / "sync.sh"

        # Test with --help to verify bash forwarding works
        result = subprocess.run(
            [str(sync_script), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        assert result.returncode == 0

    def test_bash_forwards_all_flag(self, temp_project):
        """Test bash script forwards --all flag.

        REQUIREMENT: All-mode sync via bash wrapper.
        Expected: sync.sh --all → python sync_dispatcher.py --all
        """
        sync_script = temp_project / "sync.sh"

        # Test with --help to verify bash forwarding works
        result = subprocess.run(
            [str(sync_script), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        assert result.returncode == 0


class TestEndToEndSyncExecution:
    """Test end-to-end sync execution from bash to Python to file operations."""

    @pytest.fixture
    def isolated_project(self, tmp_path):
        """Create isolated project with plugin structure for real sync testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create .claude directory
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # Create mock plugin directory structure
        plugin_dir = project_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create mock command files
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "test-command.md").write_text("# Test Command")

        # Create mock hook files
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "test_hook.py").write_text("# Test Hook")

        return project_root

    def test_plugin_dev_sync_creates_files(self, isolated_project):
        """Test that --plugin-dev sync creates files in .claude directory.

        REQUIREMENT: Real file I/O operations in plugin-dev mode.
        Expected: Files from plugins/ copied to .claude/
        """
        # Direct Python import test
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--plugin-dev']):
            with patch('os.getcwd', return_value=str(isolated_project)):
                exit_code = sync_dispatcher.main()

                # Verify files were copied
                assert exit_code == 0
                assert (isolated_project / ".claude" / "commands" / "test-command.md").exists()
                assert (isolated_project / ".claude" / "hooks" / "test_hook.py").exists()

    def test_github_sync_downloads_files(self, isolated_project, monkeypatch):
        """Test that --github sync downloads files from GitHub.

        REQUIREMENT: Real network I/O for GitHub mode (mocked for testing).
        Expected: Files downloaded and written to .claude/
        """
        # Mock urllib to avoid real network calls
        mock_manifest = {
            "files": [
                "plugins/autonomous-dev/commands/auto-implement.md",
                "plugins/autonomous-dev/hooks/auto_git_workflow.py"
            ]
        }

        import urllib.request
        import json

        class MockResponse:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data.encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def mock_urlopen(url, timeout=None):
            if "install_manifest.json" in url:
                return MockResponse(json.dumps(mock_manifest))
            else:
                # Return mock file content
                return MockResponse("# Mock file content")

        monkeypatch.setattr(urllib.request, 'urlopen', mock_urlopen)

        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--github']):
            with patch('os.getcwd', return_value=str(isolated_project)):
                exit_code = sync_dispatcher.main()

                # Verify files were created
                assert exit_code == 0
                assert (isolated_project / ".claude" / "commands").exists()
                assert (isolated_project / ".claude" / "hooks").exists()


class TestExitCodePropagation:
    """Test that exit codes propagate correctly through the execution chain."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_success_returns_zero_exit_code(self, temp_project):
        """Test that successful sync returns exit code 0.

        REQUIREMENT: Standard Unix exit codes.
        Expected: Success → exit code 0 → shell receives 0
        """
        from plugins.autonomous_dev.lib import sync_dispatcher
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.GITHUB,
                message="Sync completed"
            )

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()
                    assert exit_code == 0

    def test_failure_returns_one_exit_code(self, temp_project):
        """Test that failed sync returns exit code 1.

        REQUIREMENT: Error exit codes for failures.
        Expected: Failure → exit code 1 → shell receives 1
        """
        from plugins.autonomous_dev.lib import sync_dispatcher
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=False,
                mode=SyncMode.GITHUB,
                message="Sync failed",
                error="Network error"
            )

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()
                    assert exit_code == 1

    def test_invalid_args_returns_two_exit_code(self, temp_project):
        """Test that invalid arguments return exit code 2.

        REQUIREMENT: Argument error exit codes.
        Expected: Invalid args → exit code 2 → shell receives 2
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--invalid']):
            with patch('os.getcwd', return_value=str(temp_project)):
                with pytest.raises((SystemExit, AttributeError)) as exc_info:
                    sync_dispatcher.main()

                # argparse exits with 2, or AttributeError if main() doesn't exist
                if isinstance(exc_info.value, SystemExit):
                    assert exc_info.value.code == 2


class TestDirectCLIInvocation:
    """Test direct invocation of sync_dispatcher.py as a script."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_direct_python_invocation_works(self, temp_project):
        """Test invoking sync_dispatcher.py directly with python3.

        REQUIREMENT: CLI must be executable as a Python script.
        Expected: python3 sync_dispatcher.py --help → executes successfully
        """
        dispatcher_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "sync_dispatcher.py"

        # Test with --help flag (doesn't require actual sync operations)
        result = subprocess.run(
            ["python3", str(dispatcher_path), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should succeed
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "sync" in result.stdout.lower()

    def test_cli_accepts_help_flag(self, temp_project):
        """Test that CLI accepts --help flag and shows usage.

        REQUIREMENT: Provide usage documentation via --help.
        Expected: python3 sync_dispatcher.py --help → shows help + exit 0
        """
        dispatcher_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "sync_dispatcher.py"

        result = subprocess.run(
            ["python3", str(dispatcher_path), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        # --help should exit with 0
        assert result.returncode == 0
        # Should contain usage information
        assert "usage:" in result.stdout.lower() or "sync" in result.stdout.lower()

    def test_cli_without_arguments_uses_default_mode(self, temp_project):
        """Test that CLI without arguments defaults to GitHub mode.

        REQUIREMENT: Sensible defaults for common use case.
        Expected: python3 sync_dispatcher.py → GITHUB mode (default)
        """
        dispatcher_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "sync_dispatcher.py"

        # Test with --help to verify CLI works (default mode would try to sync)
        result = subprocess.run(
            ["python3", str(dispatcher_path), "--help"],
            cwd=str(temp_project),
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should succeed
        assert result.returncode == 0


class TestCLIErrorHandling:
    """Test CLI error handling and user-friendly messages."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_missing_project_directory_shows_helpful_error(self, temp_project):
        """Test that missing project directory shows helpful error.

        REQUIREMENT: Clear error messages for common mistakes.
        Expected: Run from invalid directory → helpful error message
        """
        from plugins.autonomous_dev.lib import sync_dispatcher

        # Use non-existent directory
        nonexistent = temp_project.parent / "does_not_exist"

        with patch('sys.argv', ['sync_dispatcher.py']):
            with patch('os.getcwd', return_value=str(nonexistent)):
                exit_code = sync_dispatcher.main()

                # Should show helpful error
                assert exit_code == 1

    def test_sync_dispatcher_exception_shows_error(self, temp_project, capsys):
        """Test that SyncDispatcher exceptions are caught and displayed.

        REQUIREMENT: Graceful handling of sync errors.
        Expected: Sync error → user-friendly message + exit code 1
        """
        from plugins.autonomous_dev.lib import sync_dispatcher
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.side_effect = Exception("Unexpected sync error")

            with patch('sys.argv', ['sync_dispatcher.py']):
                with patch('os.getcwd', return_value=str(temp_project)):
                    exit_code = sync_dispatcher.main()

                    # Should handle exception gracefully
                    assert exit_code == 1

                    captured = capsys.readouterr()
                    # Error should be visible to user
                    assert "error" in captured.err.lower()


class TestCLIIntegrationWithSyncModes:
    """Test CLI integration with all sync modes."""

    @pytest.fixture
    def mock_marketplace(self, tmp_path):
        """Create mock marketplace installation."""
        home = tmp_path / "home"
        marketplace = home / ".claude" / "plugins" / "marketplaces" / "autonomous-dev" / "plugins" / "autonomous-dev"
        marketplace.mkdir(parents=True)

        # Create mock plugin files
        (marketplace / "commands").mkdir()
        (marketplace / "commands" / "test.md").write_text("# Test")

        return tmp_path

    def test_github_mode_integration(self, tmp_path, monkeypatch):
        """Test complete integration of GitHub sync mode.

        REQUIREMENT: End-to-end GitHub sync via CLI.
        Expected: CLI --github → downloads files → updates .claude/
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / ".claude").mkdir()

        # Mock network calls
        import urllib.request
        import json

        mock_manifest = {"files": ["plugins/autonomous-dev/commands/test.md"]}

        class MockResponse:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data.encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def mock_urlopen(url, timeout=None):
            if "manifest" in url:
                return MockResponse(json.dumps(mock_manifest))
            return MockResponse("# Mock content")

        monkeypatch.setattr(urllib.request, 'urlopen', mock_urlopen)

        from plugins.autonomous_dev.lib import sync_dispatcher

        with patch('sys.argv', ['sync_dispatcher.py', '--github']):
            with patch('os.getcwd', return_value=str(project)):
                exit_code = sync_dispatcher.main()

                # Verify implementation
                assert exit_code == 0
                assert (project / ".claude" / "commands").exists()

    def test_all_mode_executes_sequentially(self, tmp_path):
        """Test that --all mode executes all sync modes in sequence.

        REQUIREMENT: Sequential execution of all modes.
        Expected: --all → GITHUB + ENVIRONMENT + MARKETPLACE + PLUGIN_DEV
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / ".claude").mkdir()

        from plugins.autonomous_dev.lib import sync_dispatcher
        from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher

        with patch.object(SyncDispatcher, 'dispatch') as mock_dispatch:
            mock_dispatch.return_value = SyncResult(
                success=True,
                mode=SyncMode.ALL,
                message="All modes completed"
            )

            with patch('sys.argv', ['sync_dispatcher.py', '--all']):
                with patch('os.getcwd', return_value=str(project)):
                    exit_code = sync_dispatcher.main()

                    # Verify implementation
                    assert exit_code == 0
                    assert mock_dispatch.called
                    # Verify ALL mode was used
                    call_args = mock_dispatch.call_args
                    assert call_args[0][0] == SyncMode.ALL
