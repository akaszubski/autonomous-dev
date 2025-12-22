#!/usr/bin/env python3
"""
Test Install Manifest Completeness

Validates that:
1. All hooks referenced in settings templates exist in the manifest
2. All files listed in the manifest exist in the source
3. Core commands are configured for global installation
4. No orphan files exist that should be in the manifest

This test prevents the bug where:
- pre_tool_use.py existed in source but wasn't in manifest
- Settings templates referenced hooks that weren't installed
- /sync wasn't available globally in new repos

Run with: pytest tests/unit/test_install_manifest_completeness.py -v

Issue: GitHub #157 - Hook installation backwards compatibility
Date: 2025-12-23
"""

import json
import re
from pathlib import Path
import pytest


# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
MANIFEST_PATH = PROJECT_ROOT / "plugins/autonomous-dev/config/install_manifest.json"
HOOKS_DIR = PROJECT_ROOT / "plugins/autonomous-dev/hooks"
COMMANDS_DIR = PROJECT_ROOT / "plugins/autonomous-dev/commands"
SETTINGS_TEMPLATES_DIR = PROJECT_ROOT / "plugins/autonomous-dev/templates"
GLOBAL_SETTINGS_TEMPLATE = PROJECT_ROOT / "plugins/autonomous-dev/config/global_settings_template.json"


@pytest.fixture
def manifest():
    """Load the install manifest."""
    with open(MANIFEST_PATH) as f:
        return json.load(f)


@pytest.fixture
def global_settings_template():
    """Load the global settings template."""
    with open(GLOBAL_SETTINGS_TEMPLATE) as f:
        return json.load(f)


class TestManifestFilesExist:
    """Verify all files in manifest exist in source."""

    def test_all_hook_files_exist(self, manifest):
        """Every hook file in manifest must exist in source."""
        missing = []
        for hook_path in manifest["components"]["hooks"]["files"]:
            full_path = PROJECT_ROOT / hook_path
            if not full_path.exists():
                missing.append(hook_path)

        assert not missing, f"Hook files in manifest but missing from source: {missing}"

    def test_all_command_files_exist(self, manifest):
        """Every command file in manifest must exist in source."""
        missing = []
        for cmd_path in manifest["components"]["commands"]["files"]:
            full_path = PROJECT_ROOT / cmd_path
            if not full_path.exists():
                missing.append(cmd_path)

        assert not missing, f"Command files in manifest but missing from source: {missing}"

    def test_all_lib_files_exist(self, manifest):
        """Every lib file in manifest must exist in source."""
        missing = []
        for lib_path in manifest["components"]["lib"]["files"]:
            full_path = PROJECT_ROOT / lib_path
            if not full_path.exists():
                missing.append(lib_path)

        assert not missing, f"Lib files in manifest but missing from source: {missing}"


class TestSettingsReferencesInManifest:
    """Verify all hooks referenced in settings exist in manifest."""

    def _extract_hook_filenames_from_settings(self, settings_data):
        """Extract hook filenames from settings hooks configuration."""
        hook_files = set()
        hooks_config = settings_data.get("hooks", {})

        for lifecycle, lifecycle_hooks in hooks_config.items():
            if not isinstance(lifecycle_hooks, list):
                continue
            for hook_entry in lifecycle_hooks:
                if not isinstance(hook_entry, dict):
                    continue
                # Check nested hooks array
                inner_hooks = hook_entry.get("hooks", [])
                for hook in inner_hooks:
                    if isinstance(hook, dict):
                        command = hook.get("command", "")
                        # Extract .py filename from command
                        # e.g., "python3 ~/.claude/hooks/unified_pre_tool.py" -> "unified_pre_tool.py"
                        match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*\.py)', command)
                        if match:
                            hook_files.add(match.group(1))

        return hook_files

    def test_global_settings_hooks_in_manifest(self, manifest, global_settings_template):
        """All hooks in global_settings_template.json must be in manifest."""
        referenced_hooks = self._extract_hook_filenames_from_settings(global_settings_template)
        manifest_hooks = {Path(p).name for p in manifest["components"]["hooks"]["files"]}

        missing = referenced_hooks - manifest_hooks
        assert not missing, (
            f"Hooks referenced in global_settings_template.json but not in manifest: {missing}\n"
            f"This will cause 'file not found' errors after installation!"
        )

    def test_settings_templates_hooks_in_manifest(self, manifest):
        """All hooks in settings templates must be in manifest or use project-relative paths."""
        if not SETTINGS_TEMPLATES_DIR.exists():
            pytest.skip("Settings templates directory not found")

        manifest_hooks = {Path(p).name for p in manifest["components"]["hooks"]["files"]}

        for template_file in SETTINGS_TEMPLATES_DIR.glob("settings.*.json"):
            with open(template_file) as f:
                try:
                    settings = json.load(f)
                except json.JSONDecodeError:
                    continue

            referenced_hooks = self._extract_hook_filenames_from_settings(settings)

            # For project-relative paths (plugins/autonomous-dev/hooks/...),
            # check if file exists in source
            for hook_name in referenced_hooks:
                # Check if in manifest (for global paths ~/.claude/hooks/)
                in_manifest = hook_name in manifest_hooks
                # Check if exists in source (for project-relative paths)
                exists_in_source = (HOOKS_DIR / hook_name).exists()

                assert in_manifest or exists_in_source, (
                    f"Hook '{hook_name}' referenced in {template_file.name} but:\n"
                    f"  - Not in manifest (won't be installed globally)\n"
                    f"  - Not in source hooks directory\n"
                    f"This will cause 'file not found' errors!"
                )


class TestGlobalCommandsConfigured:
    """Verify core commands are installed globally."""

    REQUIRED_GLOBAL_COMMANDS = ["sync.md", "setup.md", "health-check.md"]

    def test_core_commands_in_manifest(self, manifest):
        """Core commands required for bootstrapping must be in manifest."""
        manifest_commands = {Path(p).name for p in manifest["components"]["commands"]["files"]}

        missing = set(self.REQUIRED_GLOBAL_COMMANDS) - manifest_commands
        assert not missing, (
            f"Core commands missing from manifest: {missing}\n"
            f"These commands must be available globally for /sync to work in new repos!"
        )

    def test_install_sh_installs_global_commands(self):
        """install.sh must have install_global_commands function."""
        install_sh = PROJECT_ROOT / "install.sh"
        content = install_sh.read_text()

        assert "install_global_commands" in content, (
            "install.sh missing install_global_commands function!\n"
            "/sync won't be available in new repos."
        )

        # Check that core commands are listed
        for cmd in self.REQUIRED_GLOBAL_COMMANDS:
            cmd_name = cmd.replace(".md", "")
            assert cmd in content or cmd_name in content, (
                f"install.sh doesn't reference '{cmd}' in global commands!\n"
                f"This command won't be available globally."
            )


class TestNoOrphanHooks:
    """Verify no important hooks are missing from manifest."""

    # Hooks that MUST be in the manifest
    CRITICAL_HOOKS = [
        "unified_pre_tool.py",
        "unified_prompt_validator.py",
        "pre_tool_use.py",  # For backwards compatibility
    ]

    def test_critical_hooks_in_manifest(self, manifest):
        """Critical hooks must be in manifest."""
        manifest_hooks = {Path(p).name for p in manifest["components"]["hooks"]["files"]}

        missing = []
        for hook in self.CRITICAL_HOOKS:
            if hook not in manifest_hooks:
                # Check if file exists in source
                if (HOOKS_DIR / hook).exists():
                    missing.append(hook)

        assert not missing, (
            f"Critical hooks exist in source but not in manifest: {missing}\n"
            f"These hooks won't be installed to ~/.claude/hooks/!"
        )

    def test_no_untracked_py_hooks(self, manifest):
        """Warn about .py hooks in source but not in manifest."""
        if not HOOKS_DIR.exists():
            pytest.skip("Hooks directory not found")

        manifest_hooks = {Path(p).name for p in manifest["components"]["hooks"]["files"]}
        source_hooks = {f.name for f in HOOKS_DIR.glob("*.py") if not f.name.startswith("_")}

        # Exclude disabled hooks
        source_hooks = {h for h in source_hooks if not h.endswith(".disabled")}

        untracked = source_hooks - manifest_hooks

        # This is a warning, not a failure - some hooks might be intentionally local-only
        if untracked:
            pytest.warns(
                UserWarning,
                match=f"Hooks in source but not manifest: {untracked}"
            ) if False else None  # Just log for now
            print(f"\nWARNING: Hooks in source but not in manifest: {untracked}")
            print("If these should be installed globally, add them to install_manifest.json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
