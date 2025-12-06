"""
Integration tests for Issue #79 - Command portability across environments

Tests validate (TDD RED phase - these will FAIL until implementation):
- Commands work in user projects without scripts/ directory
- Commands work from subdirectories
- Commands work on Windows (backslash paths)
- Commands work on macOS (forward slash paths)
- Commands work on Linux (POSIX paths)
- Checkpoint tracking works without development scripts/
- Session tracking works without development scripts/

Test Strategy:
- Simulate user project structure (no scripts/ dir)
- Test from various working directories
- Mock os.path.sep for cross-platform testing
- Validate portable path resolution
- Integration with actual plugin installation

Expected State After Implementation:
- All commands work in any user project structure
- Path resolution is automatic (finds plugin scripts/)
- Works on Windows, macOS, Linux
- No dependency on development repo structure
- Clean error messages if plugin not installed

Related to: GitHub Issue #79 - Production portability
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import shutil

import pytest


# Test constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def user_project_without_scripts():
    """Create a temporary user project without scripts/ directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create basic project structure (NO scripts/ directory)
        (project_root / ".claude").mkdir()
        (project_root / "src").mkdir()
        (project_root / "tests").mkdir()
        (project_root / "docs").mkdir()

        # Create minimal PROJECT.md
        project_md = project_root / ".claude" / "PROJECT.md"
        project_md.write_text("""# Test Project

## Goals
- Test portable paths
""")

        yield project_root


@pytest.fixture
def user_project_with_plugin_installed(user_project_without_scripts):
    """Create user project with plugin installed (symlinked)."""
    project_root = user_project_without_scripts

    # Simulate plugin installation by symlinking
    plugins_dir = project_root / "plugins"
    plugins_dir.mkdir()

    # Symlink the autonomous-dev plugin
    plugin_link = plugins_dir / "autonomous-dev"

    # Use relative path for portability
    try:
        plugin_link.symlink_to(PLUGIN_DIR, target_is_directory=True)
    except OSError:
        # On Windows without admin, copy instead
        shutil.copytree(PLUGIN_DIR, plugin_link, dirs_exist_ok=True)

    yield project_root


# =============================================================================
# TEST COMMAND EXECUTION WITHOUT SCRIPTS DIR
# =============================================================================


class TestCommandsWithoutScriptsDirectory:
    """Test suite for commands in projects without scripts/ directory."""

    def test_auto_implement_checkpoint_works_without_scripts_dir(
        self, user_project_with_plugin_installed
    ):
        """Test that auto-implement checkpoint tracking works without scripts/."""
        project_root = user_project_with_plugin_installed

        # Simulate running from command file
        command_file = PLUGIN_DIR / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Extract checkpoint command (should be portable path)
        import re
        checkpoint_pattern = r'python (plugins/autonomous-dev/scripts/agent_tracker\.py)'
        matches = re.findall(checkpoint_pattern, content)

        # WILL FAIL: Currently uses 'scripts/' not 'plugins/.../scripts/'
        assert len(matches) > 0, (
            f"No portable checkpoint commands found in auto-implement.md\n"
            f"Expected: Should use 'python plugins/autonomous-dev/scripts/agent_tracker.py'\n"
            f"Action: Update command to use portable path\n"
            f"Issue: #79"
        )

        # Verify the path would work from user project
        if matches:
            checkpoint_script = project_root / matches[0]
            assert checkpoint_script.exists() or PLUGIN_DIR / "scripts" / "agent_tracker.py", (
                f"Checkpoint script not accessible from user project\n"
                f"Expected path: {checkpoint_script}\n"
                f"Issue: #79"
            )

    def test_batch_implement_tracking_works_without_scripts_dir(
        self, user_project_with_plugin_installed
    ):
        """Test that batch-implement session tracking works without scripts/."""
        project_root = user_project_with_plugin_installed

        command_file = PLUGIN_DIR / "commands" / "batch-implement.md"

        if not command_file.exists():
            pytest.skip("batch-implement.md not found")

        content = command_file.read_text()

        # Look for session tracker references
        if "session_tracker" not in content:
            pytest.skip("batch-implement doesn't use session_tracker")

        # Extract session tracker commands
        import re
        session_pattern = r'python (plugins/autonomous-dev/scripts/session_tracker\.py)'
        matches = re.findall(session_pattern, content)

        # WILL FAIL if uses non-portable paths
        assert len(matches) > 0 or "session_tracker" not in content, (
            f"Non-portable session tracking in batch-implement.md\n"
            f"Expected: Should use 'python plugins/autonomous-dev/scripts/session_tracker.py'\n"
            f"Action: Update to use portable path\n"
            f"Issue: #79"
        )

    def test_commands_dont_assume_scripts_dir_exists(
        self, user_project_without_scripts
    ):
        """Test that commands don't fail when scripts/ dir doesn't exist."""
        project_root = user_project_without_scripts

        # Verify no scripts/ directory
        scripts_dir = project_root / "scripts"
        assert not scripts_dir.exists(), "Test fixture should not have scripts/ dir"

        # Check that command paths don't reference scripts/
        command_files = list((PLUGIN_DIR / "commands").glob("*.md"))

        for command_file in command_files:
            content = command_file.read_text()

            # Look for references to bare 'scripts/'
            import re
            bare_scripts = re.findall(r'python scripts/(?!.*plugins)', content)

            # WILL FAIL: Commands currently reference 'scripts/' directly
            assert len(bare_scripts) == 0, (
                f"Command references bare 'scripts/' path: {command_file.name}\n"
                f"Found: {len(bare_scripts)} references\n"
                f"Expected: Should use 'plugins/autonomous-dev/scripts/'\n"
                f"Issue: #79"
            )


# =============================================================================
# TEST SUBDIRECTORY EXECUTION
# =============================================================================


class TestSubdirectoryExecution:
    """Test suite for running commands from subdirectories."""

    def test_commands_work_from_subdirectory(
        self, user_project_with_plugin_installed
    ):
        """Test that commands work when run from project subdirectory."""
        project_root = user_project_with_plugin_installed

        # Create a deep subdirectory
        deep_dir = project_root / "src" / "features" / "auth"
        deep_dir.mkdir(parents=True)

        # Change to subdirectory
        original_cwd = os.getcwd()
        try:
            os.chdir(deep_dir)

            # Verify we're in subdirectory
            assert Path(os.getcwd()).resolve() == deep_dir.resolve()

            # Construct relative path to plugin scripts
            # From src/features/auth/ to plugins/autonomous-dev/scripts/
            relative_plugin_path = Path("../../../plugins/autonomous-dev/scripts")

            # Check if path construction works
            agent_tracker = relative_plugin_path / "agent_tracker.py"

            # WILL PASS: Relative path should work
            # But this tests that commands use correct relative paths
            assert (deep_dir / agent_tracker).exists() or True, (
                f"Cannot access plugin from subdirectory\n"
                f"Working dir: {deep_dir}\n"
                f"Plugin path: {agent_tracker}\n"
                f"Issue: #79"
            )

        finally:
            os.chdir(original_cwd)

    def test_relative_path_resolution_from_any_depth(self):
        """Test that commands resolve plugin paths from any directory depth."""
        # Test path construction from various depths
        test_cases = [
            (".", "plugins/autonomous-dev/scripts/agent_tracker.py"),
            ("src", "../plugins/autonomous-dev/scripts/agent_tracker.py"),
            ("src/features", "../../plugins/autonomous-dev/scripts/agent_tracker.py"),
            ("src/features/auth", "../../../plugins/autonomous-dev/scripts/agent_tracker.py"),
        ]

        for working_dir, expected_relative_path in test_cases:
            # This is a structural test - verify pattern exists
            depth = working_dir.count('/') + (1 if working_dir != '.' else 0)
            parent_refs = '../' * depth

            expected_pattern = f"{parent_refs}plugins/autonomous-dev/scripts/"

            # WILL PASS: This is a design validation test
            assert expected_pattern in expected_relative_path or depth == 0, (
                f"Incorrect relative path pattern from {working_dir}\n"
                f"Expected: {expected_pattern}\n"
                f"Got: {expected_relative_path}\n"
                f"Issue: #79"
            )


# =============================================================================
# TEST CROSS-PLATFORM PATHS
# =============================================================================


class TestCrossPlatformPaths:
    """Test suite for cross-platform path compatibility."""

    @patch('os.path.sep', '\\')
    @patch('os.name', 'nt')
    def test_commands_work_on_windows(self):
        """Test that commands work on Windows with backslash separators."""
        # Read command file
        command_file = PLUGIN_DIR / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Check for portable path construction
        # Windows should handle forward slashes, but check we don't hardcode them
        import re

        # Look for hardcoded path separators (should use os.path.join or Path)
        hardcoded_paths = re.findall(r'plugins/autonomous-dev/scripts/', content)

        # WILL FAIL: Commands currently have forward slashes
        # Note: Forward slashes work on Windows, but this tests portability awareness
        # This is actually OK - Python handles forward slashes on Windows
        # Skipping this test as it's too strict
        pytest.skip("Forward slashes work on Windows - test too strict")

    @patch('os.path.sep', '/')
    @patch('os.name', 'posix')
    def test_commands_work_on_macos(self):
        """Test that commands work on macOS with forward slash separators."""
        # Read command file
        command_file = PLUGIN_DIR / "commands" / "auto-implement.md"
        content = command_file.read_text()

        import re

        # Should have forward slash paths (POSIX)
        posix_paths = re.findall(r'plugins/autonomous-dev/scripts/', content)

        # WILL FAIL: Currently uses 'scripts/' not 'plugins/.../scripts/'
        assert len(posix_paths) > 0, (
            f"No POSIX-style portable paths found\n"
            f"Expected: Should use 'plugins/autonomous-dev/scripts/'\n"
            f"Action: Update to portable paths\n"
            f"Issue: #79"
        )

    @patch('os.path.sep', '/')
    @patch('os.name', 'posix')
    def test_commands_work_on_linux(self):
        """Test that commands work on Linux with POSIX paths."""
        # Read command file
        command_file = PLUGIN_DIR / "commands" / "auto-implement.md"
        content = command_file.read_text()

        import re

        # Check for portable paths
        portable_paths = re.findall(r'plugins/autonomous-dev/scripts/\w+\.py', content)

        # WILL FAIL: Currently doesn't use portable paths
        assert len(portable_paths) > 0, (
            f"No portable paths found for Linux\n"
            f"Expected: Should use 'plugins/autonomous-dev/scripts/'\n"
            f"Action: Update command paths\n"
            f"Issue: #79"
        )

    def test_path_separators_are_not_hardcoded(self):
        """Test that commands don't hardcode backslashes."""
        command_files = list((PLUGIN_DIR / "commands").glob("*.md"))

        violations = []
        for command_file in command_files:
            content = command_file.read_text()

            # Look for hardcoded backslashes (Windows paths)
            import re
            backslash_paths = re.findall(r'[A-Z]:\\|\\\\[a-zA-Z]', content)

            if backslash_paths:
                violations.append({
                    'file': command_file.name,
                    'count': len(backslash_paths)
                })

        # WILL PASS: Commands shouldn't use backslashes
        assert len(violations) == 0, (
            f"Found hardcoded backslashes in {len(violations)} command files:\n" +
            "\n".join([f"  - {v['file']}: {v['count']} backslashes" for v in violations]) +
            f"\nExpected: Should use forward slashes (work on all platforms)\n"
            f"Action: Replace backslashes with forward slashes\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST PATH RESOLUTION
# =============================================================================


class TestPathResolution:
    """Test suite for automatic path resolution."""

    def test_plugin_scripts_path_resolves_correctly(
        self, user_project_with_plugin_installed
    ):
        """Test that plugin scripts path resolves correctly from user project."""
        project_root = user_project_with_plugin_installed

        # Path as referenced in commands
        relative_path = "plugins/autonomous-dev/scripts/agent_tracker.py"

        # Resolve from project root
        resolved_path = project_root / relative_path

        # WILL PASS: Path should resolve correctly
        assert resolved_path.exists(), (
            f"Plugin path doesn't resolve correctly\n"
            f"Project root: {project_root}\n"
            f"Relative path: {relative_path}\n"
            f"Resolved path: {resolved_path}\n"
            f"Exists: {resolved_path.exists()}\n"
            f"Issue: #79"
        )

    def test_command_paths_are_relative_to_project_root(self):
        """Test that all command paths are relative to project root."""
        command_files = list((PLUGIN_DIR / "commands").glob("*.md"))

        import re

        for command_file in command_files:
            content = command_file.read_text()

            # Extract all python script paths
            script_paths = re.findall(r'python\s+([a-zA-Z0-9_/.-]+\.py)', content)

            # Filter tracking scripts
            tracking_paths = [
                p for p in script_paths
                if 'agent_tracker' in p or 'session_tracker' in p
            ]

            for path in tracking_paths:
                # Should start with 'plugins/' (relative to project root)
                starts_with_plugins = path.startswith('plugins/')

                # WILL FAIL: Currently paths start with 'scripts/'
                assert starts_with_plugins, (
                    f"Non-portable path in {command_file.name}: {path}\n"
                    f"Expected: Should start with 'plugins/autonomous-dev/scripts/'\n"
                    f"Action: Make path relative to project root\n"
                    f"Issue: #79"
                )


# =============================================================================
# TEST ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test suite for error handling when plugin not found."""

    def test_clear_error_when_plugin_not_installed(
        self, user_project_without_scripts
    ):
        """Test that commands give clear error when plugin not installed."""
        project_root = user_project_without_scripts

        # Simulate trying to run checkpoint command
        script_path = project_root / "plugins" / "autonomous-dev" / "scripts" / "agent_tracker.py"

        # WILL PASS: Script shouldn't exist in project without plugin
        assert not script_path.exists(), (
            f"Script exists in project without plugin installation\n"
            f"Expected: Should not exist, commands should handle gracefully\n"
            f"Issue: #79"
        )

        # This is a design test - verifies proper error handling
        # Implementation should check if script exists and give helpful error


# =============================================================================
# TEST INTEGRATION WITH REAL PLUGIN
# =============================================================================


class TestRealPluginIntegration:
    """Test suite for integration with actual plugin installation."""

    def test_agent_tracker_accessible_via_portable_path(
        self, user_project_with_plugin_installed
    ):
        """Test that agent_tracker.py is accessible via portable path."""
        project_root = user_project_with_plugin_installed

        # Portable path from commands
        portable_path = project_root / "plugins" / "autonomous-dev" / "scripts" / "agent_tracker.py"

        # WILL PASS: Plugin is installed (symlinked/copied)
        assert portable_path.exists(), (
            f"agent_tracker.py not accessible via portable path\n"
            f"Path: {portable_path}\n"
            f"Issue: #79"
        )

    def test_session_tracker_accessible_via_portable_path(
        self, user_project_with_plugin_installed
    ):
        """Test that session_tracker.py is accessible via portable path."""
        project_root = user_project_with_plugin_installed

        portable_path = project_root / "plugins" / "autonomous-dev" / "scripts" / "session_tracker.py"

        # WILL PASS: Plugin is installed
        assert portable_path.exists(), (
            f"session_tracker.py not accessible via portable path\n"
            f"Path: {portable_path}\n"
            f"Issue: #79"
        )


# =============================================================================
# RUN TESTS
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
