"""
Unit tests for strict mode template hook references.

Tests validate that settings.strict-mode.json template:
1. References hooks that actually exist in plugin directory
2. Uses correct plugin paths (not deprecated .claude/hooks/)
3. Contains valid JSON structure
4. All referenced hooks are executable Python files

TDD Red Phase: These tests will FAIL until template is fixed.
"""

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def template_path():
    """Path to strict mode template."""
    repo_root = Path(__file__).parent.parent.parent.parent
    return repo_root / "plugins/autonomous-dev/templates/settings.strict-mode.json"


@pytest.fixture
def plugin_hooks_dir():
    """Path to plugin hooks directory."""
    repo_root = Path(__file__).parent.parent.parent.parent
    return repo_root / "plugins/autonomous-dev/hooks"


@pytest.fixture
def template_config(template_path):
    """Load template configuration."""
    with open(template_path) as f:
        return json.load(f)


class TestStrictModeTemplateStructure:
    """Test JSON structure and validity."""

    def test_template_exists(self, template_path):
        """Template file should exist."""
        assert template_path.exists(), f"Template not found at {template_path}"

    def test_json_validity(self, template_path):
        """Template should be valid JSON."""
        with open(template_path) as f:
            config = json.load(f)

        assert isinstance(config, dict), "Template should be a JSON object"
        assert "hooks" in config, "Template should have 'hooks' section"

    def test_has_required_sections(self, template_config):
        """Template should have all required sections."""
        assert "description" in template_config
        assert "customInstructions" in template_config
        assert "permissions" in template_config
        assert "hooks" in template_config

    def test_hooks_section_structure(self, template_config):
        """Hooks section should have expected structure."""
        hooks = template_config["hooks"]

        # Expected lifecycle hooks
        expected_hooks = ["UserPromptSubmit", "PostToolUse", "PreCommit", "SubagentStop"]

        for hook_type in expected_hooks:
            assert hook_type in hooks, f"Missing hook type: {hook_type}"
            assert isinstance(hooks[hook_type], list), f"{hook_type} should be a list"


class TestHookPaths:
    """Test that hook paths reference correct locations."""

    def test_no_deprecated_claude_hooks_paths(self, template_config):
        """
        Template should NOT reference .claude/hooks/ (deprecated location).

        This will FAIL until we update all hook paths from:
          .claude/hooks/foo.py
        to:
          plugins/autonomous-dev/hooks/foo.py
        """
        template_str = json.dumps(template_config)

        # Should not contain any .claude/hooks/ references
        assert ".claude/hooks/" not in template_str, (
            "Template contains deprecated .claude/hooks/ references. "
            "All hooks should reference plugins/autonomous-dev/hooks/"
        )

    def test_hook_paths_use_plugin_directory(self, template_config):
        """
        All hook references should use plugins/autonomous-dev/hooks/.

        This will FAIL until we update the template paths.
        """
        hooks = template_config["hooks"]
        plugin_hook_prefix = "plugins/autonomous-dev/hooks/"

        hook_commands = self._extract_all_hook_commands(hooks)
        python_hook_commands = [
            cmd for cmd in hook_commands
            if cmd.strip().startswith("python") and ".py" in cmd
        ]

        for cmd in python_hook_commands:
            # Extract Python file path from command
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                assert python_file.startswith(plugin_hook_prefix), (
                    f"Hook command uses wrong path: {cmd}\n"
                    f"Expected path to start with: {plugin_hook_prefix}\n"
                    f"Found: {python_file}"
                )

    def test_count_hook_references(self, template_config):
        """Template should reference exactly 9 hook files."""
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        # Extract unique Python files
        python_files = set()
        for cmd in hook_commands:
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)
            if python_file:
                python_files.add(python_file)

        # Should have exactly 9 unique hook files
        # (detect_feature_request, auto_format x2, validate_project_alignment,
        #  enforce_orchestrator, enforce_tdd, auto_fix_docs,
        #  validate_session_quality, auto_test, security_scan)
        assert len(python_files) == 9, (
            f"Expected 9 unique hook references, found {len(python_files)}: "
            f"{sorted(python_files)}"
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


class TestHookFilesExist:
    """Test that all referenced hooks exist in plugin directory."""

    def test_all_hooks_exist(self, template_config, plugin_hooks_dir):
        """
        All hooks referenced in template should exist in plugin directory.

        This will FAIL until we verify all 9 hooks exist:
        - detect_feature_request.py
        - auto_format.py
        - validate_project_alignment.py
        - enforce_orchestrator.py
        - enforce_tdd.py
        - auto_fix_docs.py
        - validate_session_quality.py
        - auto_test.py
        - security_scan.py
        """
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        missing_hooks = []

        for cmd in hook_commands:
            # Extract Python file path
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                # Remove the plugin prefix to get just the filename
                filename = Path(python_file).name
                expected_path = plugin_hooks_dir / filename

                if not expected_path.exists():
                    missing_hooks.append({
                        "command": cmd,
                        "expected_path": str(expected_path),
                        "filename": filename
                    })

        assert not missing_hooks, (
            f"Missing hook files in {plugin_hooks_dir}:\n" +
            "\n".join([
                f"  - {h['filename']} (expected at {h['expected_path']})"
                for h in missing_hooks
            ])
        )

    def test_all_hooks_are_executable(self, template_config, plugin_hooks_dir):
        """
        All referenced hooks should be valid Python files.

        This will FAIL if any hook is not a valid Python file.
        """
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        invalid_hooks = []

        for cmd in hook_commands:
            # Extract Python file path
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                filename = Path(python_file).name
                hook_path = plugin_hooks_dir / filename

                if hook_path.exists():
                    # Check it's a file and has .py extension
                    if not hook_path.is_file():
                        invalid_hooks.append(f"{filename}: Not a file")
                    elif not str(hook_path).endswith(".py"):
                        invalid_hooks.append(f"{filename}: Not a Python file")

                    # Try to read it to verify it's readable
                    try:
                        with open(hook_path) as f:
                            content = f.read()
                            if not content.strip():
                                invalid_hooks.append(f"{filename}: Empty file")
                    except Exception as e:
                        invalid_hooks.append(f"{filename}: Cannot read - {e}")

        assert not invalid_hooks, (
            f"Invalid hook files:\n" +
            "\n".join([f"  - {h}" for h in invalid_hooks])
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


class TestSpecificHooks:
    """Test specific hook configurations."""

    def test_detect_feature_request_hook(self, template_config):
        """detect_feature_request.py should be in UserPromptSubmit."""
        hooks = template_config["hooks"]["UserPromptSubmit"]

        # Find the hook command
        found = False
        for hook_item in hooks:
            if "hooks" in hook_item:
                for hook_def in hook_item["hooks"]:
                    cmd = hook_def.get("command", "")
                    if "detect_feature_request.py" in cmd:
                        # Should use plugin path
                        assert "plugins/autonomous-dev/hooks/detect_feature_request.py" in cmd, (
                            f"detect_feature_request.py uses wrong path: {cmd}"
                        )
                        found = True

        assert found, "detect_feature_request.py not found in UserPromptSubmit hooks"

    def test_auto_format_hook(self, template_config):
        """auto_format.py should be in PostToolUse (for Write and Edit)."""
        hooks = template_config["hooks"]["PostToolUse"]

        found_write = False
        found_edit = False

        for hook_item in hooks:
            matcher = hook_item.get("matcher", "")
            if "hooks" in hook_item:
                for hook_def in hook_item["hooks"]:
                    cmd = hook_def.get("command", "")
                    if "auto_format.py" in cmd:
                        # Should use plugin path
                        assert "plugins/autonomous-dev/hooks/auto_format.py" in cmd, (
                            f"auto_format.py uses wrong path: {cmd}"
                        )

                        if matcher == "Write":
                            found_write = True
                        elif matcher == "Edit":
                            found_edit = True

        assert found_write, "auto_format.py not found for Write matcher"
        assert found_edit, "auto_format.py not found for Edit matcher"

    def test_precommit_hooks(self, template_config):
        """All PreCommit hooks should use plugin paths."""
        hooks = template_config["hooks"]["PreCommit"]

        expected_hooks = [
            "validate_project_alignment.py",
            "enforce_orchestrator.py",
            "enforce_tdd.py",
            "auto_fix_docs.py",
            "validate_session_quality.py",
            "auto_test.py",
            "security_scan.py"
        ]

        found_hooks = {}

        for hook_item in hooks:
            if "hooks" in hook_item:
                for hook_def in hook_item["hooks"]:
                    cmd = hook_def.get("command", "")

                    for expected_hook in expected_hooks:
                        if expected_hook in cmd:
                            # Should use plugin path
                            expected_path = f"plugins/autonomous-dev/hooks/{expected_hook}"
                            assert expected_path in cmd, (
                                f"{expected_hook} uses wrong path: {cmd}\n"
                                f"Expected: {expected_path}"
                            )
                            found_hooks[expected_hook] = True

        # Verify all expected hooks were found
        for expected_hook in expected_hooks:
            assert expected_hook in found_hooks, (
                f"PreCommit hook not found: {expected_hook}"
            )


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_no_relative_paths(self, template_config):
        """Hook paths should not use relative paths like ../."""
        template_str = json.dumps(template_config)

        assert "../" not in template_str, (
            "Template should not use relative paths (../)"
        )

    def test_no_absolute_system_paths(self, template_config):
        """Hook paths should not use absolute system paths like /usr/."""
        hooks = template_config["hooks"]
        hook_commands = self._extract_all_hook_commands(hooks)

        for cmd in hook_commands:
            parts = cmd.split()
            python_file = next((p for p in parts if p.endswith(".py")), None)

            if python_file:
                # Should not start with /
                assert not python_file.startswith("/"), (
                    f"Hook uses absolute path: {cmd}\n"
                    f"Use plugin-relative path instead"
                )

    def test_all_hooks_have_descriptions(self, template_config):
        """All hook entries should have descriptions."""
        hooks = template_config["hooks"]

        missing_descriptions = []

        for hook_type, hook_list in hooks.items():
            for i, hook_item in enumerate(hook_list):
                if "description" not in hook_item:
                    missing_descriptions.append(f"{hook_type}[{i}]")

        assert not missing_descriptions, (
            f"Hook entries missing descriptions:\n" +
            "\n".join([f"  - {h}" for h in missing_descriptions])
        )

    def test_hook_commands_are_strings(self, template_config):
        """All hook commands should be strings."""
        hooks = template_config["hooks"]

        invalid_commands = []

        for hook_type, hook_list in hooks.items():
            for hook_item in hook_list:
                if "hooks" in hook_item:
                    for hook_def in hook_item["hooks"]:
                        cmd = hook_def.get("command")
                        if cmd is not None and not isinstance(cmd, str):
                            invalid_commands.append(
                                f"{hook_type}: command is {type(cmd)}, not str"
                            )

        assert not invalid_commands, (
            f"Invalid command types:\n" +
            "\n".join([f"  - {c}" for c in invalid_commands])
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
