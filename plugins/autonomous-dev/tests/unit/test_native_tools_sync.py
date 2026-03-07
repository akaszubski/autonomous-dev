"""
Test that all consumers of the native tools list stay in sync.

If this test fails, it means a new tool was added to one place but not others.
Fix: update plugins/autonomous-dev/lib/native_tools.py, then propagate.

See: lib/native_tools.py for the single source of truth.
"""

import json
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent  # plugins/autonomous-dev


def _load_source_of_truth() -> set[str]:
    """Load NATIVE_TOOLS from lib/native_tools.py."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "native_tools", PLUGIN_ROOT / "lib" / "native_tools.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.NATIVE_TOOLS


def _extract_set_from_py(path: Path, var_name: str) -> set[str]:
    """Extract a set literal from a Python file by regex."""
    content = path.read_text()
    # Match: VAR_NAME = { "A", "B", ... }
    pattern = rf'{var_name}\s*=\s*\{{([^}}]+)\}}'
    match = re.search(pattern, content, re.DOTALL)
    assert match, f"Could not find {var_name} in {path}"
    items = re.findall(r'"([^"]+)"', match.group(1))
    return set(items)


def _extract_list_from_json(path: Path, *keys: str) -> set[str]:
    """Extract a list from nested JSON keys."""
    data = json.loads(path.read_text())
    for key in keys:
        data = data[key]
    return set(data)


SOURCE = _load_source_of_truth()


class TestNativeToolsSync:
    """Ensure all 4 consumers match the single source of truth."""

    def test_unified_pre_tool_hook(self):
        """NATIVE_TOOLS in unified_pre_tool.py must match source."""
        hook_path = PLUGIN_ROOT / "hooks" / "unified_pre_tool.py"
        hook_tools = _extract_set_from_py(hook_path, "NATIVE_TOOLS")
        missing = SOURCE - hook_tools
        extra = hook_tools - SOURCE
        assert not missing, f"unified_pre_tool.py missing: {missing}"
        assert not extra, f"unified_pre_tool.py has extra: {extra}"

    def test_auto_approve_policy(self):
        """auto_approve_policy.json tools.always_allowed must be superset of source."""
        policy_path = PLUGIN_ROOT / "config" / "auto_approve_policy.json"
        policy_tools = _extract_list_from_json(
            policy_path, "tools", "always_allowed"
        )
        missing = SOURCE - policy_tools
        assert not missing, f"auto_approve_policy.json missing: {missing}"

    def test_settings_template(self):
        """settings.local.json permissions.allow must be superset of source."""
        template_path = PLUGIN_ROOT / "templates" / "settings.local.json"
        template_tools = _extract_list_from_json(
            template_path, "permissions", "allow"
        )
        missing = SOURCE - template_tools
        assert not missing, f"settings.local.json missing: {missing}"

    def test_tool_validator_defaults(self):
        """tool_validator.py default always_allowed must be superset of source."""
        validator_path = PLUGIN_ROOT / "lib" / "tool_validator.py"
        content = validator_path.read_text()
        # Extract the always_allowed list from _create_default_policy
        pattern = r'"always_allowed":\s*\[([^\]]+)\]'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "Could not find always_allowed in tool_validator.py"
        items = re.findall(r'"([^"]+)"', match.group(1))
        validator_tools = set(items)
        missing = SOURCE - validator_tools
        assert not missing, f"tool_validator.py missing: {missing}"

    def test_no_unknown_tools_in_source(self):
        """Sanity check: source shouldn't have tools that look wrong."""
        for tool in SOURCE:
            assert tool[0].isupper(), f"Tool '{tool}' doesn't start with uppercase"
            assert " " not in tool, f"Tool '{tool}' contains spaces"


class TestWorktreeSync:
    """Ensure worktree setup copies hooks and config, not just settings.json."""

    def test_implement_batch_copies_hooks(self):
        """implement-batch.md must cp hooks dir into worktree.

        Regression: worktrees got stale hooks from git commit, causing
        NATIVE_TOOLS to be outdated and triggering permission prompts.
        """
        batch_cmd = PLUGIN_ROOT / "commands" / "implement-batch.md"
        content = batch_cmd.read_text()
        assert 'cp -rf "$PARENT_REPO/.claude/hooks/"' in content, (
            "implement-batch.md must copy .claude/hooks/ from parent repo into worktree"
        )

    def test_implement_batch_copies_config(self):
        """implement-batch.md must cp config dir into worktree.

        Without config/, auto_approve_policy.json is missing and
        the hook falls through to restrictive defaults.
        """
        batch_cmd = PLUGIN_ROOT / "commands" / "implement-batch.md"
        content = batch_cmd.read_text()
        assert 'cp -rf "$PARENT_REPO/.claude/config/"' in content, (
            "implement-batch.md must copy .claude/config/ from parent repo into worktree"
        )

    def test_implement_batch_copies_settings(self):
        """implement-batch.md must cp settings.json into worktree."""
        batch_cmd = PLUGIN_ROOT / "commands" / "implement-batch.md"
        content = batch_cmd.read_text()
        assert 'cp "$PARENT_REPO/.claude/settings.json"' in content, (
            "implement-batch.md must copy settings.json from parent repo into worktree"
        )
