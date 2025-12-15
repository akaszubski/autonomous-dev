"""
Smoke tests for unified hooks architecture (Issue #144).

These tests verify that unified hooks exist and are importable.
For detailed function testing, see tests/unit/hooks/test_*.py

Smoke test criteria:
- Fast (< 5 seconds)
- Check existence only
- No complex logic testing
"""

import sys
from pathlib import Path
import pytest
import importlib.util

# Portable path detection
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

hooks_dir = project_root / "plugins/autonomous-dev/hooks"


@pytest.fixture
def hooks_path():
    """Return path to hooks directory."""
    return hooks_dir


class TestUnifiedHooksExist:
    """Smoke test: All 10 unified hooks exist."""

    # The 10 unified hooks after Issue #144 consolidation
    UNIFIED_HOOKS = [
        "unified_pre_tool",
        "unified_post_tool",
        "unified_prompt_validator",
        "unified_git_automation",
        "unified_session_tracker",
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_manifest_sync",
    ]

    @pytest.mark.parametrize("hook_name", UNIFIED_HOOKS)
    def test_unified_hook_file_exists(self, hooks_path, hook_name):
        """Test that unified hook file exists."""
        hook_file = hooks_path / f"{hook_name}.py"
        assert hook_file.exists(), f"Unified hook {hook_name}.py not found"

    def test_hooks_directory_exists(self, hooks_path):
        """Test that hooks directory exists."""
        assert hooks_path.exists(), "Hooks directory not found"

    def test_at_least_10_unified_hooks(self, hooks_path):
        """Test that at least 10 unified hooks exist."""
        unified_hooks = list(hooks_path.glob("unified_*.py"))
        assert len(unified_hooks) >= 10, f"Expected 10+ unified hooks, found {len(unified_hooks)}"


class TestCriticalHooksImportable:
    """Smoke test: Critical hooks are importable."""

    CRITICAL_HOOKS = [
        "unified_pre_tool",
        "unified_prompt_validator",
        "unified_git_automation",
    ]

    @pytest.mark.parametrize("hook_name", CRITICAL_HOOKS)
    def test_critical_hook_importable(self, hook_name):
        """Test that critical hooks can be imported without errors."""
        hook_path = hooks_dir / f"{hook_name}.py"
        if not hook_path.exists():
            pytest.skip(f"Hook not found: {hook_name}")

        spec = importlib.util.spec_from_file_location(hook_name, hook_path)
        module = importlib.util.module_from_spec(spec)

        # Should not raise ImportError
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import {hook_name}: {e}")


class TestHookSettingsIntegration:
    """Smoke test: Hooks are configured in settings templates."""

    def test_settings_template_references_hooks(self):
        """Test that settings template references unified hooks."""
        settings_path = project_root / "plugins/autonomous-dev/templates/settings.local.json"
        if not settings_path.exists():
            pytest.skip("Settings template not found")

        content = settings_path.read_text()

        # Should reference at least the critical hooks
        assert "unified_pre_tool" in content or "hooks" in content, \
            "Settings template should reference hooks"
