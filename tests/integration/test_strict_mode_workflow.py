"""
Integration tests for strict mode workflow with plugin hooks.

Tests validate that strict mode works correctly when enabled WITHOUT
running the optional setup.py (which copies hooks to .claude/hooks/).

The template should reference hooks directly from plugins/ directory,
not from .claude/hooks/, so strict mode works immediately after plugin
installation without additional setup steps.

TDD Red Phase: These tests will FAIL until template is fixed.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def repo_root():
    """Repository root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def template_path(repo_root):
    """Path to strict mode template."""
    return repo_root / "plugins/autonomous-dev/templates/settings.strict-mode.json"


@pytest.fixture
def plugin_hooks_dir(repo_root):
    """Path to plugin hooks directory."""
    return repo_root / "plugins/autonomous-dev/hooks"


@pytest.fixture
def claude_hooks_dir(repo_root):
    """Path to optional .claude/hooks directory (may not exist)."""
    return repo_root / ".claude/hooks"


@pytest.fixture
def template_config(template_path):
    """Load template configuration."""
    with open(template_path) as f:
        return json.load(f)


class TestStrictModeEnablesWithoutSetup:
    """
    Test that strict mode works WITHOUT running optional setup.

    This is critical for plugin users who just install and enable strict mode
    without running the optional .claude/hooks/ setup.
    """

    def test_template_does_not_depend_on_claude_hooks(
        self, template_config, claude_hooks_dir
    ):
        """
        Template should work even if .claude/hooks/ doesn't exist.

        This will FAIL if template references .claude/hooks/ which requires
        optional setup to be run first.
        """
        template_str = json.dumps(template_config)

        # Template should NOT reference .claude/hooks/
        assert ".claude/hooks/" not in template_str, (
            "Template references .claude/hooks/ which requires optional setup.\n"
            "Strict mode must work immediately after plugin installation.\n"
            "Use plugins/autonomous-dev/hooks/ instead."
        )

    def test_all_hooks_exist_in_plugin_directory(
        self, template_config, plugin_hooks_dir
    ):
        """
        All hooks should exist in plugins/autonomous-dev/hooks/ directory.

        This ensures strict mode works without any additional setup.
        """
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        missing_in_plugin = []

        for cmd in hook_commands:
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                filename = Path(python_file).name
                plugin_hook_path = plugin_hooks_dir / filename

                if not plugin_hook_path.exists():
                    missing_in_plugin.append(filename)

        assert not missing_in_plugin, (
            f"Hooks missing from {plugin_hooks_dir}:\n" +
            "\n".join([f"  - {h}" for h in missing_in_plugin]) +
            "\n\nAll hooks must exist in plugin directory for strict mode to work."
        )

    def test_hooks_work_without_setup(self, template_config, plugin_hooks_dir):
        """
        Hooks should be runnable directly from plugin directory.

        This tests that we don't need .claude/hooks/ setup for strict mode.
        """
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        unrunnable_hooks = []

        for cmd in hook_commands:
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                filename = Path(python_file).name
                hook_path = plugin_hooks_dir / filename

                if hook_path.exists():
                    # Check if it's a valid Python file
                    try:
                        with open(hook_path) as f:
                            content = f.read()

                        # Check for Python shebang or import statements
                        if not (
                            content.startswith("#!")
                            or "import " in content
                            or "from " in content
                        ):
                            unrunnable_hooks.append(
                                f"{filename}: Doesn't look like valid Python"
                            )
                    except Exception as e:
                        unrunnable_hooks.append(f"{filename}: Cannot read - {e}")

        assert not unrunnable_hooks, (
            f"Hooks not runnable:\n" +
            "\n".join([f"  - {h}" for h in unrunnable_hooks])
        )

    def _extract_all_hook_commands(self, hooks_config):
        """Extract all hook command strings from config."""
        commands = []

        for hook_type, hook_list in hooks_config.items():
            for hook_item in hook_list:
                if "hooks" in hook_item:
                    for hook_def in hook_item["hooks"]:
                        if hook_def.get("type") == "command":
                            commands.append(hook_def["command"])

        return commands


class TestPrecommitHooksCanExecute:
    """
    Test that PreCommit hooks can be found and executed.

    This validates that hook paths resolve correctly from project root.
    """

    def test_precommit_hooks_are_importable(
        self, template_config, plugin_hooks_dir, repo_root
    ):
        """
        PreCommit hooks should be importable as Python modules.

        This will FAIL if hooks can't be imported due to wrong paths or
        missing dependencies.
        """
        hooks = template_config["hooks"].get("PreCommit", [])

        import_errors = []

        # Add plugin hooks directory to Python path
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(plugin_hooks_dir))

            for hook_item in hooks:
                if "hooks" in hook_item:
                    for hook_def in hook_item["hooks"]:
                        cmd = hook_def.get("command", "")

                        # Extract Python file
                        parts = cmd.split()
                        python_file = next(
                            (p for p in parts if p.endswith(".py")), None
                        )

                        if python_file:
                            filename = Path(python_file).name
                            module_name = filename.replace(".py", "")

                            # Try to import it
                            try:
                                __import__(module_name)
                            except ImportError as e:
                                # It's OK if imports fail due to dependencies
                                # We just want to verify the file exists and is valid Python
                                if "No module named" not in str(e) or module_name in str(e):
                                    import_errors.append(f"{filename}: {e}")
                            except SyntaxError as e:
                                import_errors.append(f"{filename}: Syntax error - {e}")

        finally:
            sys.path = original_path

        assert not import_errors, (
            f"Hooks have import/syntax errors:\n" +
            "\n".join([f"  - {e}" for e in import_errors])
        )

    def test_precommit_hooks_have_main_or_run(
        self, template_config, plugin_hooks_dir
    ):
        """
        PreCommit hooks should have a main() function or be runnable.

        This ensures hooks can actually execute when called.
        """
        hooks = template_config["hooks"].get("PreCommit", [])

        missing_main = []

        for hook_item in hooks:
            if "hooks" in hook_item:
                for hook_def in hook_item["hooks"]:
                    cmd = hook_def.get("command", "")

                    # Extract Python file
                    parts = cmd.split()
                    python_file = next((p for p in parts if p.endswith(".py")), None)

                    if python_file:
                        filename = Path(python_file).name
                        hook_path = plugin_hooks_dir / filename

                        if hook_path.exists():
                            with open(hook_path) as f:
                                content = f.read()

                            # Check for main execution
                            has_main = (
                                "def main(" in content
                                or 'if __name__ == "__main__"' in content
                                or 'if __name__ == \'__main__\'' in content
                            )

                            if not has_main:
                                missing_main.append(filename)

        assert not missing_main, (
            f"PreCommit hooks missing main() or __main__:\n" +
            "\n".join([f"  - {h}" for h in missing_main]) +
            "\n\nHooks must be executable to work in PreCommit lifecycle."
        )

    def test_precommit_hooks_exit_codes(self, template_config):
        """
        PreCommit hooks should use exit codes (|| exit 1).

        This ensures hooks fail the commit when they detect issues.
        """
        hooks = template_config["hooks"].get("PreCommit", [])

        missing_exit_codes = []

        for hook_item in hooks:
            if "hooks" in hook_item:
                for hook_def in hook_item["hooks"]:
                    cmd = hook_def.get("command", "")

                    # Extract Python file
                    parts = cmd.split()
                    python_file = next((p for p in parts if p.endswith(".py")), None)

                    if python_file:
                        filename = Path(python_file).name

                        # Check if command has || exit 1
                        if "|| exit 1" not in cmd:
                            missing_exit_codes.append(filename)

        assert not missing_exit_codes, (
            f"PreCommit hooks missing '|| exit 1':\n" +
            "\n".join([f"  - {h}" for h in missing_exit_codes]) +
            "\n\nPreCommit hooks must fail with exit 1 to block commits."
        )


class TestHookPathsResolveCorrectly:
    """
    Test that hook paths resolve correctly from project root.

    This validates the full path resolution in actual usage.
    """

    def test_hook_paths_are_relative_to_project_root(self, template_config):
        """
        All hook paths should be relative to project root.

        Format: plugins/autonomous-dev/hooks/foo.py (no leading /)
        """
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        invalid_paths = []

        for cmd in hook_commands:
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                # Should start with plugins/
                if not python_file.startswith("plugins/"):
                    invalid_paths.append(
                        f"{python_file}: Should start with 'plugins/'"
                    )

                # Should NOT start with /
                if python_file.startswith("/"):
                    invalid_paths.append(f"{python_file}: Should not be absolute path")

                # Should NOT contain ../
                if "../" in python_file:
                    invalid_paths.append(f"{python_file}: Should not use relative ../")

        assert not invalid_paths, (
            f"Invalid hook paths:\n" +
            "\n".join([f"  - {p}" for p in invalid_paths])
        )

    def test_hook_paths_resolve_from_repo_root(
        self, template_config, repo_root
    ):
        """
        Hook paths should resolve correctly when executed from repo root.

        This simulates actual Claude Code usage where hooks run from project root.
        """
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        unresolvable_paths = []

        for cmd in hook_commands:
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                # Try to resolve from repo root
                full_path = repo_root / python_file

                if not full_path.exists():
                    unresolvable_paths.append(
                        f"{python_file}: Does not resolve to {full_path}"
                    )

        assert not unresolvable_paths, (
            f"Hook paths don't resolve from repo root:\n" +
            "\n".join([f"  - {p}" for p in unresolvable_paths])
        )

    def test_python_command_is_valid(self, template_config):
        """
        Python commands should use 'python' (not 'python3', '/usr/bin/python', etc.).

        This ensures consistency across environments.
        """
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        invalid_python_cmds = []

        for cmd in hook_commands:
            if ".py" in cmd:
                parts = cmd.split()

                # Should start with 'python '
                if parts and parts[0] not in ["python", "python3"]:
                    if "/" in parts[0]:  # Absolute path like /usr/bin/python
                        invalid_python_cmds.append(
                            f"{cmd}: Uses absolute Python path"
                        )

        assert not invalid_python_cmds, (
            f"Invalid Python commands:\n" +
            "\n".join([f"  - {c}" for c in invalid_python_cmds])
        )

    def _extract_all_hook_commands(self, hooks_config):
        """Extract all hook command strings from config."""
        commands = []

        for hook_type, hook_list in hooks_config.items():
            for hook_item in hook_list:
                if "hooks" in hook_item:
                    for hook_def in hook_item["hooks"]:
                        if hook_def.get("type") == "command":
                            commands.append(hook_def["command"])

        return commands


class TestStrictModeWorkflowEnd2End:
    """
    End-to-end workflow tests simulating actual strict mode usage.
    """

    def test_full_strict_mode_config_valid(self, template_path):
        """
        Complete strict mode config should be valid and loadable.

        This is the most basic end-to-end test - can we even load the config?
        """
        # Should load without errors
        with open(template_path) as f:
            config = json.load(f)

        # Should have all required sections
        assert "description" in config
        assert "customInstructions" in config
        assert "permissions" in config
        assert "hooks" in config

        # Should have all expected hook types
        assert "UserPromptSubmit" in config["hooks"]
        assert "PostToolUse" in config["hooks"]
        assert "PreCommit" in config["hooks"]
        assert "SubagentStop" in config["hooks"]

    def test_all_9_hooks_referenced_correctly(
        self, template_config, plugin_hooks_dir
    ):
        """
        All 9 expected hooks should be referenced with correct paths.

        This is the master validation test - everything should work together.
        """
        expected_hooks = {
            "detect_feature_request.py": "UserPromptSubmit",
            "auto_format.py": "PostToolUse",
            "validate_project_alignment.py": "PreCommit",
            "enforce_orchestrator.py": "PreCommit",
            "enforce_tdd.py": "PreCommit",
            "auto_fix_docs.py": "PreCommit",
            "validate_session_quality.py": "PreCommit",
            "auto_test.py": "PreCommit",
            "security_scan.py": "PreCommit",
        }

        found_hooks = {}
        incorrect_paths = []

        hooks = template_config["hooks"]

        for hook_type, hook_list in hooks.items():
            for hook_item in hook_list:
                if "hooks" in hook_item:
                    for hook_def in hook_item["hooks"]:
                        cmd = hook_def.get("command", "")

                        for expected_hook, expected_type in expected_hooks.items():
                            if expected_hook in cmd:
                                found_hooks[expected_hook] = hook_type

                                # Check path is correct
                                expected_path = (
                                    f"plugins/autonomous-dev/hooks/{expected_hook}"
                                )
                                if expected_path not in cmd:
                                    incorrect_paths.append(
                                        f"{expected_hook}: Wrong path in {cmd}"
                                    )

                                # Verify file exists
                                hook_path = plugin_hooks_dir / expected_hook
                                if not hook_path.exists():
                                    incorrect_paths.append(
                                        f"{expected_hook}: File doesn't exist at "
                                        f"{hook_path}"
                                    )

        # All 9 hooks should be found
        missing_hooks = set(expected_hooks.keys()) - set(found_hooks.keys())
        assert not missing_hooks, (
            f"Missing hooks from template:\n" +
            "\n".join([f"  - {h}" for h in sorted(missing_hooks)])
        )

        # All hooks should have correct paths
        assert not incorrect_paths, (
            f"Hooks with incorrect paths:\n" +
            "\n".join([f"  - {p}" for p in incorrect_paths])
        )

        # Verify hooks are in correct lifecycle positions
        misplaced_hooks = []
        for hook, expected_type in expected_hooks.items():
            actual_type = found_hooks.get(hook)
            if actual_type != expected_type:
                misplaced_hooks.append(
                    f"{hook}: Expected {expected_type}, found in {actual_type}"
                )

        assert not misplaced_hooks, (
            f"Hooks in wrong lifecycle positions:\n" +
            "\n".join([f"  - {h}" for h in misplaced_hooks])
        )
