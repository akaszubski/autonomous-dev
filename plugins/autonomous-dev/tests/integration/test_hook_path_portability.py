"""
Integration tests for hook path portability (Issue #113).

Tests end-to-end hook installation, execution, and migration workflow.
These tests should FAIL initially (TDD red phase).
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


class TestFreshInstallHookPaths:
    """Test fresh installation creates portable hook paths."""

    @pytest.fixture
    def fresh_install_dir(self, tmp_path):
        """Create fresh installation directory."""
        install_dir = tmp_path / "fresh_install"
        install_dir.mkdir()
        claude_dir = install_dir / ".claude"
        claude_dir.mkdir()
        return install_dir

    def test_creates_settings_with_tilde_path(self, fresh_install_dir):
        """Test fresh install creates settings.json with ~/.claude/hooks/ path."""
        from autonomous_dev.scripts.install_hooks import install_hooks

        with patch("pathlib.Path.home", return_value=fresh_install_dir):
            result = install_hooks()

        settings_path = fresh_install_dir / ".claude" / "settings.json"
        assert settings_path.exists()

        settings = json.loads(settings_path.read_text())

        # Should use portable path
        command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert "~/.claude/hooks/pre_tool_use.py" in command
        assert "/Users/" not in command
        assert "/home/" not in command
        assert "C:\\" not in command

    def test_copies_hook_to_claude_directory(self, fresh_install_dir):
        """Test fresh install copies pre_tool_use.py to ~/.claude/hooks/."""
        from autonomous_dev.scripts.install_hooks import install_hooks

        with patch("pathlib.Path.home", return_value=fresh_install_dir):
            install_hooks()

        hook_path = fresh_install_dir / ".claude" / "hooks" / "pre_tool_use.py"

        # Should copy hook file
        assert hook_path.exists()
        assert hook_path.is_file()

    def test_creates_lib_directory(self, fresh_install_dir):
        """Test fresh install creates ~/.claude/lib/ directory."""
        from autonomous_dev.scripts.install_hooks import install_hooks

        with patch("pathlib.Path.home", return_value=fresh_install_dir):
            install_hooks()

        lib_path = fresh_install_dir / ".claude" / "lib"

        # Should create lib directory
        assert lib_path.exists()
        assert lib_path.is_dir()

    def test_copies_required_libraries(self, fresh_install_dir):
        """Test fresh install copies required lib files."""
        from autonomous_dev.scripts.install_hooks import install_hooks

        with patch("pathlib.Path.home", return_value=fresh_install_dir):
            install_hooks()

        lib_path = fresh_install_dir / ".claude" / "lib"

        required_libs = [
            "mcp_permission_validator.py",
            "auto_approve_policy.py"
        ]

        for lib_file in required_libs:
            lib_file_path = lib_path / lib_file
            assert lib_file_path.exists(), f"Missing required library: {lib_file}"

    def test_preserves_existing_hooks(self, fresh_install_dir):
        """Test fresh install preserves existing hook configuration."""
        from autonomous_dev.scripts.install_hooks import install_hooks

        # Create existing settings with other hooks
        settings_path = fresh_install_dir / ".claude" / "settings.json"
        existing_settings = {
            "hooks": {
                "SubagentStop": [{
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/auto_git_workflow.py"}]
                }]
            }
        }
        settings_path.write_text(json.dumps(existing_settings, indent=2))

        with patch("pathlib.Path.home", return_value=fresh_install_dir):
            install_hooks()

        settings = json.loads(settings_path.read_text())

        # Should preserve existing SubagentStop hook
        assert "SubagentStop" in settings["hooks"]
        assert settings["hooks"]["SubagentStop"] == existing_settings["hooks"]["SubagentStop"]

        # Should add PreToolUse hook
        assert "PreToolUse" in settings["hooks"]


class TestHookExecutionFromClaudeHooks:
    """Test hook execution from ~/.claude/hooks/ location."""

    @pytest.fixture
    def installed_hook(self, tmp_path):
        """Create installed hook in ~/.claude/hooks/."""
        claude_dir = tmp_path / ".claude"
        hooks_dir = claude_dir / "hooks"
        lib_dir = claude_dir / "lib"
        hooks_dir.mkdir(parents=True)
        lib_dir.mkdir(parents=True)

        # Copy hook file
        hook_source = Path(__file__).parent.parent.parent / "hooks" / "pre_tool_use.py"
        hook_dest = hooks_dir / "pre_tool_use.py"
        if hook_source.exists():
            hook_dest.write_text(hook_source.read_text())
        else:
            # Create minimal hook for testing
            hook_dest.write_text("""
import json
import sys
from pathlib import Path

def find_lib_directory(hook_path):
    # Stub for testing
    return Path.home() / ".claude" / "lib"

if __name__ == "__main__":
    lib_dir = find_lib_directory(Path(__file__))
    if lib_dir and lib_dir.exists():
        sys.path.insert(0, str(lib_dir))
        print(json.dumps({"allow": True, "source": "claude_hooks"}))
    else:
        print(json.dumps({"allow": True, "error": "lib not found"}))
""")

        return tmp_path, hooks_dir / "pre_tool_use.py"

    def test_hook_executes_successfully(self, installed_hook):
        """Test hook executes successfully from ~/.claude/hooks/."""
        tmp_path, hook_path = installed_hook

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = subprocess.run(
                ["python3", str(hook_path)],
                capture_output=True,
                text=True,
                timeout=5
            )

        # Should execute successfully
        assert result.returncode == 0
        assert len(result.stdout) > 0

        # Should output valid JSON
        output = json.loads(result.stdout.strip())
        assert "allow" in output
        assert output["allow"] is True

    def test_hook_finds_lib_directory(self, installed_hook):
        """Test hook finds lib directory from ~/.claude/lib/."""
        tmp_path, hook_path = installed_hook

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = subprocess.run(
                ["python3", str(hook_path)],
                capture_output=True,
                text=True,
                timeout=5
            )

        output = json.loads(result.stdout.strip())

        # Should find lib directory
        assert "error" not in output or "lib not found" not in output.get("error", "")

    def test_hook_loads_mcp_security_module(self, installed_hook):
        """Test hook successfully loads MCP security validation module."""
        tmp_path, hook_path = installed_hook

        # Create minimal MCP security module
        lib_dir = tmp_path / ".claude" / "lib"
        mcp_module = lib_dir / "mcp_permission_validator.py"
        mcp_module.write_text("""
def validate_operation(operation, params):
    return {"allowed": True}
""")

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = subprocess.run(
                ["python3", str(hook_path)],
                capture_output=True,
                text=True,
                timeout=5
            )

        # Should execute without import errors
        assert result.returncode == 0
        assert "ImportError" not in result.stderr
        assert "ModuleNotFoundError" not in result.stderr


class TestHookExecutionFromDevelopment:
    """Test hook execution from development location."""

    @pytest.fixture
    def dev_hook(self, tmp_path):
        """Create hook in development location."""
        dev_dir = tmp_path / "plugins" / "autonomous-dev"
        hooks_dir = dev_dir / "hooks"
        lib_dir = dev_dir / "lib"
        hooks_dir.mkdir(parents=True)
        lib_dir.mkdir(parents=True)

        # Create minimal hook
        hook_path = hooks_dir / "pre_tool_use.py"
        hook_path.write_text("""
import json
import sys
from pathlib import Path

def find_lib_directory(hook_path):
    # Check development location
    dev_lib = hook_path.parent.parent / "lib"
    if dev_lib.exists():
        return dev_lib
    return None

if __name__ == "__main__":
    lib_dir = find_lib_directory(Path(__file__))
    if lib_dir and lib_dir.exists():
        sys.path.insert(0, str(lib_dir))
        print(json.dumps({"allow": True, "source": "development"}))
    else:
        print(json.dumps({"allow": True, "error": "lib not found"}))
""")

        return hook_path

    def test_hook_executes_from_dev_location(self, dev_hook):
        """Test hook executes successfully from development location."""
        result = subprocess.run(
            ["python3", str(dev_hook)],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should execute successfully
        assert result.returncode == 0

        output = json.loads(result.stdout.strip())
        assert output["allow"] is True
        assert output.get("source") == "development"

    def test_hook_finds_dev_lib_directory(self, dev_hook):
        """Test hook finds lib directory from plugins/autonomous-dev/lib/."""
        result = subprocess.run(
            ["python3", str(dev_hook)],
            capture_output=True,
            text=True,
            timeout=5
        )

        output = json.loads(result.stdout.strip())

        # Should find lib directory
        assert "error" not in output or "lib not found" not in output.get("error", "")


class TestGracefulFailureOnMissingLib:
    """Test graceful failure when lib directory not found."""

    @pytest.fixture
    def hook_without_lib(self, tmp_path):
        """Create hook without lib directory."""
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir(parents=True)

        hook_path = hooks_dir / "pre_tool_use.py"
        hook_path.write_text("""
import json
import sys
from pathlib import Path

def find_lib_directory(hook_path):
    # Simulate lib not found
    return None

if __name__ == "__main__":
    lib_dir = find_lib_directory(Path(__file__))
    if lib_dir:
        sys.path.insert(0, str(lib_dir))
        print(json.dumps({"allow": True, "source": "with_lib"}))
    else:
        # Graceful failure - allow operation but log warning
        print(json.dumps({"allow": True, "warning": "lib directory not found, MCP security disabled"}))
""")

        return hook_path

    def test_outputs_allow_true_on_missing_lib(self, hook_without_lib):
        """Test output {"allow": true} when lib not found (graceful failure)."""
        result = subprocess.run(
            ["python3", str(hook_without_lib)],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should not crash
        assert result.returncode == 0

        output = json.loads(result.stdout.strip())

        # Should allow operation
        assert output["allow"] is True

    def test_includes_warning_message(self, hook_without_lib):
        """Test include warning message when lib not found."""
        result = subprocess.run(
            ["python3", str(hook_without_lib)],
            capture_output=True,
            text=True,
            timeout=5
        )

        output = json.loads(result.stdout.strip())

        # Should include warning
        assert "warning" in output
        assert "lib" in output["warning"].lower()
        assert "not found" in output["warning"].lower()

    def test_does_not_block_operation(self, hook_without_lib):
        """Test doesn't block operation when lib missing."""
        result = subprocess.run(
            ["python3", str(hook_without_lib)],
            capture_output=True,
            text=True,
            timeout=5
        )

        output = json.loads(result.stdout.strip())

        # Should not block (allow: true)
        assert output.get("allow") is True
        assert output.get("block") is not True
        assert output.get("deny") is not True


class TestEndToEndMigrationWorkflow:
    """Test complete migration workflow from hardcoded to portable paths."""

    @pytest.fixture
    def user_environment(self, tmp_path):
        """Create user environment with hardcoded paths."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        settings_path = claude_dir / "settings.json"
        settings = {
            "hooks": {
                "PreToolUse": [{
                    "matcher": "*",
                    "hooks": [{
                        "type": "command",
                        "command": "MCP_AUTO_APPROVE=true python3 /Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/pre_tool_use.py"
                    }]
                }]
            }
        }
        settings_path.write_text(json.dumps(settings, indent=2))

        return tmp_path, settings_path

    def test_migration_updates_settings(self, user_environment):
        """Test migration script updates settings.json."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        tmp_path, settings_path = user_environment

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = migrate_hook_paths(settings_path)

        # Should migrate successfully
        assert result["migrated"] is True
        assert result["changes"] > 0

        # Verify settings updated
        settings = json.loads(settings_path.read_text())
        command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert "~/.claude/hooks/pre_tool_use.py" in command

    def test_migration_creates_backup(self, user_environment):
        """Test migration creates backup of original settings."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths

        tmp_path, settings_path = user_environment
        original_content = settings_path.read_text()

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = migrate_hook_paths(settings_path)

        # Should create backup
        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        assert backup_path.read_text() == original_content

    def test_migrated_hook_executes_successfully(self, user_environment):
        """Test hook executes successfully after migration."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths
        from autonomous_dev.scripts.install_hooks import install_hooks

        tmp_path, settings_path = user_environment

        with patch("pathlib.Path.home", return_value=tmp_path):
            # Migrate settings
            migrate_hook_paths(settings_path)

            # Install hook files
            install_hooks()

        # Read migrated settings
        settings = json.loads(settings_path.read_text())
        command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]

        # Extract hook path from command
        # Command format: "MCP_AUTO_APPROVE=true python3 ~/.claude/hooks/pre_tool_use.py"
        hook_path_str = command.split()[-1].replace("~", str(tmp_path))
        hook_path = Path(hook_path_str)

        # Should execute successfully
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = subprocess.run(
                ["python3", str(hook_path)],
                capture_output=True,
                text=True,
                timeout=5
            )

        assert result.returncode == 0

    def test_rollback_restores_original_settings(self, user_environment):
        """Test rollback functionality restores original settings."""
        from autonomous_dev.scripts.migrate_hook_paths import migrate_hook_paths, rollback_migration

        tmp_path, settings_path = user_environment
        original_content = settings_path.read_text()

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = migrate_hook_paths(settings_path)
            backup_path = Path(result["backup_path"])

            # Rollback migration
            rollback_migration(settings_path, backup_path)

        # Should restore original content
        assert settings_path.read_text() == original_content


class TestMultipleInstallationLocations:
    """Test hook path resolution across different installation scenarios."""

    def test_marketplace_installation(self, tmp_path):
        """Test hook path resolution for marketplace installation."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create marketplace structure
        claude_dir = tmp_path / ".claude"
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        marketplace_lib = claude_dir / "plugins" / "autonomous-dev" / "lib"
        marketplace_lib.mkdir(parents=True)

        hook_path = hooks_dir / "pre_tool_use.py"

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = find_lib_directory(hook_path)

        # Should find marketplace lib
        assert result == marketplace_lib

    def test_local_development_installation(self, tmp_path):
        """Test hook path resolution for local development."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create development structure
        dev_dir = tmp_path / "projects" / "autonomous-dev"
        hooks_dir = dev_dir / "plugins" / "autonomous-dev" / "hooks"
        hooks_dir.mkdir(parents=True)
        lib_dir = dev_dir / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)

        hook_path = hooks_dir / "pre_tool_use.py"

        result = find_lib_directory(hook_path)

        # Should find development lib
        assert result == lib_dir

    def test_custom_installation(self, tmp_path):
        """Test hook path resolution for custom installation location."""
        from autonomous_dev.hooks.pre_tool_use import find_lib_directory

        # Create custom structure
        claude_dir = tmp_path / ".claude"
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        local_lib = claude_dir / "lib"
        local_lib.mkdir(parents=True)

        hook_path = hooks_dir / "pre_tool_use.py"

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = find_lib_directory(hook_path)

        # Should find custom lib
        assert result == local_lib
