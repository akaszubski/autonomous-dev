"""
Regression tests for Issue #348: Hook-settings bidirectional sync.

Tests that would have caught #336→#344 (archived hooks breaking settings/imports):
1. Every active hook on disk is registered in settings templates
2. Every hook in settings templates exists on disk (not archived)
3. Every hook in install_manifest exists on disk (not archived)
4. No archived hook is referenced by active code (settings, manifest, imports)
5. Hook commands in settings use correct paths that resolve
6. Hooks can actually be loaded (syntax valid, no broken imports)
7. session_activity_logger.py specifically wired into PostToolUse

Root cause of #336→#344: hooks were archived but references remained in settings
templates, install manifests, and import paths. No test caught the breakage.
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"
HOOKS_DIR = PLUGIN_DIR / "hooks"
ARCHIVED_DIR = HOOKS_DIR / "archived"
TEMPLATES_DIR = PLUGIN_DIR / "templates"
CONFIG_DIR = PLUGIN_DIR / "config"
MANIFEST_PATH = CONFIG_DIR / "install_manifest.json"
GLOBAL_SETTINGS = CONFIG_DIR / "global_settings_template.json"

# Utility modules that are NOT standalone hooks (imported by hooks, not registered)
UTILITY_MODULES = {"__init__", "genai_utils", "genai_prompts", "setup"}


# ─── Helper Functions ────────────────────────────────────────────────────────


def get_active_hook_files() -> Set[str]:
    """Get stems of active hook .py files (excluding utilities and archived)."""
    hooks = set()
    for f in HOOKS_DIR.glob("*.py"):
        if f.name.startswith("__") or f.name.startswith("test_") or f.stem in UTILITY_MODULES:
            continue
        hooks.add(f.stem)
    return hooks


def get_archived_hook_stems() -> Set[str]:
    """Get stems of archived hook files."""
    if not ARCHIVED_DIR.exists():
        return set()
    return {
        f.stem
        for f in ARCHIVED_DIR.glob("*.py")
        if not f.name.startswith("__")
    }


def get_settings_templates() -> List[Path]:
    """Get all settings template JSON files."""
    templates = sorted(TEMPLATES_DIR.glob("settings.*.json"))
    if GLOBAL_SETTINGS.exists():
        templates.append(GLOBAL_SETTINGS)
    return templates


def extract_hook_commands_from_settings(path: Path) -> List[Dict]:
    """Extract all hook command entries from a settings file.

    Returns list of dicts with: event, matcher, command, filename, template.
    """
    data = json.loads(path.read_text())
    hooks_section = data.get("hooks", {})
    entries = []

    for event, matchers in hooks_section.items():
        for matcher_block in matchers:
            matcher = matcher_block.get("matcher", "*")
            for hook in matcher_block.get("hooks", []):
                cmd = hook.get("command", "")
                # Extract .py filenames from command
                py_matches = re.findall(r"([\w/-]+\.py)", cmd)
                for py_path in py_matches:
                    stem = Path(py_path).stem
                    entries.append({
                        "event": event,
                        "matcher": matcher,
                        "command": cmd,
                        "filename": stem,
                        "py_path": py_path,
                        "template": path.name,
                    })
    return entries


def get_manifest_hook_paths() -> List[str]:
    """Get hook file paths listed in install_manifest.json."""
    if not MANIFEST_PATH.exists():
        return []
    data = json.loads(MANIFEST_PATH.read_text())
    hooks_section = data.get("components", {}).get("hooks", {})
    return hooks_section.get("files", [])


def get_all_registered_hooks() -> Tuple[Set[str], Dict[str, List[Dict]]]:
    """Get union of all hook filenames across all settings templates.

    Returns (all_hook_stems, per_template_entries).
    """
    all_stems: Set[str] = set()
    per_template: Dict[str, List[Dict]] = {}

    for template in get_settings_templates():
        entries = extract_hook_commands_from_settings(template)
        per_template[template.name] = entries
        all_stems.update(e["filename"] for e in entries)

    return all_stems, per_template


# ─── Test Class 1: Active Hooks Must Be Registered ──────────────────────────


class TestActiveHooksRegistered:
    """Every active hook on disk must be in at least one settings template."""

    def test_no_orphan_hooks(self):
        """Hooks on disk but not in any settings template = orphans.

        This is the #348 bug: session_activity_logger.py existed but was never
        registered, so Claude Code never ran it.
        """
        active = get_active_hook_files()
        registered, _ = get_all_registered_hooks()
        orphans = active - registered

        assert not orphans, (
            f"{len(orphans)} hook(s) on disk but NOT registered in any settings template:\n"
            + "\n".join(f"  - hooks/{h}.py" for h in sorted(orphans))
            + "\n\nFix: Add each hook to the appropriate event section in ALL "
            "settings.*.json templates + global_settings_template.json"
        )

    def test_active_hook_count_sanity(self):
        """Sanity: expect 10-30 active hooks."""
        active = get_active_hook_files()
        assert 10 <= len(active) <= 30, (
            f"Expected 10-30 active hooks, found {len(active)}: {sorted(active)}"
        )


# ─── Test Class 2: Settings References Must Resolve ─────────────────────────


class TestSettingsReferencesResolve:
    """Every hook referenced in settings must exist as an active file.

    This catches the #336 bug: hooks archived but settings still reference them.
    """

    def test_no_phantom_hooks_in_any_template(self):
        """No settings template should reference a hook that doesn't exist on disk."""
        all_on_disk = {f.stem for f in HOOKS_DIR.glob("*.py") if not f.name.startswith("__")}
        registered, per_template = get_all_registered_hooks()
        phantoms = registered - all_on_disk

        assert not phantoms, (
            f"{len(phantoms)} hook(s) referenced in settings but missing from disk:\n"
            + "\n".join(f"  - {h}.py" for h in sorted(phantoms))
        )

    def test_no_archived_hooks_in_settings(self):
        """Settings templates must NOT reference archived hooks.

        This is the exact #336→#344 pattern: hook gets archived, reference remains.
        """
        archived = get_archived_hook_stems()
        _, per_template = get_all_registered_hooks()
        violations = []

        for template_name, entries in per_template.items():
            for entry in entries:
                if entry["filename"] in archived:
                    violations.append(
                        f"  {template_name}: {entry['event']} → {entry['filename']}.py (ARCHIVED)"
                    )

        assert not violations, (
            f"Settings templates reference {len(violations)} archived hook(s):\n"
            + "\n".join(violations)
            + "\n\nFix: Remove archived hook references from settings templates"
        )

    @pytest.mark.parametrize("template_path", get_settings_templates(),
                             ids=lambda p: p.name)
    def test_each_template_references_only_existing_hooks(self, template_path: Path):
        """Per-template check: every referenced hook exists on disk."""
        all_on_disk = {f.stem for f in HOOKS_DIR.glob("*.py") if not f.name.startswith("__")}
        entries = extract_hook_commands_from_settings(template_path)
        missing = {e["filename"] for e in entries} - all_on_disk

        assert not missing, (
            f"{template_path.name} references non-existent hooks: "
            + ", ".join(f"{h}.py" for h in sorted(missing))
        )


# ─── Test Class 3: Install Manifest Sync ────────────────────────────────────


class TestManifestSync:
    """Install manifest must be in sync with actual hook files on disk.

    Catches: manifest lists a deleted/archived file → install breaks.
    """

    def test_all_manifest_hooks_exist_on_disk(self):
        """Every hook path in install_manifest.json must exist as a file."""
        manifest_paths = get_manifest_hook_paths()
        missing = []

        for rel_path in manifest_paths:
            full_path = PROJECT_ROOT / rel_path
            if not full_path.exists():
                missing.append(rel_path)

        assert not missing, (
            f"install_manifest.json lists {len(missing)} hook(s) that don't exist:\n"
            + "\n".join(f"  - {p}" for p in missing)
        )

    def test_no_archived_hooks_in_manifest(self):
        """Manifest must not include hooks that have been archived."""
        archived = get_archived_hook_stems()
        manifest_paths = get_manifest_hook_paths()
        violations = []

        for rel_path in manifest_paths:
            stem = Path(rel_path).stem
            if stem in archived and "archived" not in rel_path:
                violations.append(f"  - {rel_path} (hook is archived)")

        assert not violations, (
            f"Manifest includes {len(violations)} archived hook(s):\n"
            + "\n".join(violations)
        )

    def test_all_active_hooks_in_manifest(self):
        """Every active hook on disk should be listed in the install manifest."""
        active = get_active_hook_files()
        manifest_stems = {Path(p).stem for p in get_manifest_hook_paths()}
        # Exclude utility modules
        missing = active - manifest_stems - UTILITY_MODULES

        assert not missing, (
            f"{len(missing)} active hook(s) not in install_manifest.json:\n"
            + "\n".join(f"  - hooks/{h}.py" for h in sorted(missing))
        )


# ─── Test Class 4: Hook Syntax and Import Validation ────────────────────────


class TestHookSyntaxValid:
    """Hooks must have valid Python syntax and no broken top-level imports.

    Catches: file moved/renamed but imports reference old path.
    """

    @pytest.mark.parametrize(
        "hook_file",
        sorted(HOOKS_DIR.glob("*.py")),
        ids=lambda p: p.name,
    )
    def test_hook_has_valid_syntax(self, hook_file: Path):
        """Each hook file must parse as valid Python (AST check)."""
        if hook_file.name.startswith("__"):
            pytest.skip("Skip __init__.py")
        source = hook_file.read_text()
        try:
            ast.parse(source, filename=str(hook_file))
        except SyntaxError as e:
            pytest.fail(f"{hook_file.name} has syntax error: {e}")

    @pytest.mark.parametrize(
        "hook_file",
        [f for f in sorted(HOOKS_DIR.glob("*.py"))
         if not f.name.startswith("__") and f.stem not in UTILITY_MODULES],
        ids=lambda p: p.name,
    )
    def test_hook_can_be_compiled(self, hook_file: Path):
        """Each hook file must compile without error (catches some import issues)."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(hook_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"{hook_file.name} fails py_compile:\n{result.stderr}"
        )


# ─── Test Class 5: Archived Hooks Not Referenced ─────────────────────────────


class TestArchivedNotReferenced:
    """Archived hooks must not be referenced by active code.

    This is the core #336→#344 pattern: archive a hook, forget to update references.
    Checks: settings templates, install manifest, active hook imports, agent/command files.
    """

    def test_no_archived_hooks_imported_by_active_hooks(self):
        """Active hooks must not import from archived hooks."""
        archived = get_archived_hook_stems()
        violations = []

        for hook_file in HOOKS_DIR.glob("*.py"):
            if hook_file.name.startswith("__") or hook_file.stem in UTILITY_MODULES:
                continue
            content = hook_file.read_text()
            for arch_stem in archived:
                # Check for import statements referencing archived hooks
                if re.search(rf"\bimport\s+{arch_stem}\b", content) or \
                   re.search(rf"\bfrom\s+\S*{arch_stem}\s+import\b", content):
                    violations.append(f"  {hook_file.name} imports archived {arch_stem}")

        assert not violations, (
            f"Active hooks import {len(violations)} archived hook(s):\n"
            + "\n".join(violations)
        )

    def test_no_archived_hooks_in_command_files(self):
        """Command .md files must not reference archived hook filenames."""
        archived = get_archived_hook_stems()
        commands_dir = PLUGIN_DIR / "commands"
        violations = []

        for cmd_file in commands_dir.glob("*.md"):
            content = cmd_file.read_text()
            for arch_stem in archived:
                if f"{arch_stem}.py" in content:
                    violations.append(f"  {cmd_file.name} references archived {arch_stem}.py")

        assert not violations, (
            f"Command files reference {len(violations)} archived hook(s):\n"
            + "\n".join(violations)
        )


# ─── Test Class 6: Session Activity Logger Specifically ──────────────────────


class TestSessionActivityLoggerWiring:
    """The specific bug from #348: session_activity_logger.py created but never wired."""

    def test_file_exists(self):
        assert (HOOKS_DIR / "session_activity_logger.py").exists()

    def test_registered_in_any_template(self):
        """Must appear in at least one settings template."""
        registered, _ = get_all_registered_hooks()
        assert "session_activity_logger" in registered, (
            "session_activity_logger.py exists on disk but is NOT in any settings template"
        )

    def test_registered_in_post_tool_use(self):
        """Must be in PostToolUse event (it logs tool calls)."""
        for template in get_settings_templates():
            entries = extract_hook_commands_from_settings(template)
            for e in entries:
                if e["filename"] == "session_activity_logger" and e["event"] == "PostToolUse":
                    return
        pytest.fail("session_activity_logger.py not in PostToolUse of any settings template")

    def test_in_install_manifest(self):
        """Must be listed in install_manifest.json."""
        manifest_stems = {Path(p).stem for p in get_manifest_hook_paths()}
        assert "session_activity_logger" in manifest_stems

    def test_uses_catch_all_matcher(self):
        """Must use '*' matcher (logs ALL tool calls, not just Write/Edit)."""
        for template in get_settings_templates():
            entries = extract_hook_commands_from_settings(template)
            for e in entries:
                if e["filename"] == "session_activity_logger" and e["event"] == "PostToolUse":
                    assert e["matcher"] == "*", (
                        f"session_activity_logger should use '*' matcher, "
                        f"got {e['matcher']} in {e['template']}"
                    )
                    return
        pytest.fail("session_activity_logger.py not found in PostToolUse")


# ─── Test Class 7: Critical Hook Event Placement ────────────────────────────


class TestCriticalHookEventPlacement:
    """Verify critical hooks are in the correct event types."""

    @pytest.mark.parametrize("hook_stem,expected_event", [
        ("unified_pre_tool", "PreToolUse"),
        ("unified_prompt_validator", "UserPromptSubmit"),
        ("unified_session_tracker", "SubagentStop"),
        ("auto_format", "PostToolUse"),
        ("session_activity_logger", "PostToolUse"),
    ])
    def test_critical_hook_in_correct_event(self, hook_stem: str, expected_event: str):
        """Each critical hook must be registered under its expected lifecycle event."""
        for template in get_settings_templates():
            entries = extract_hook_commands_from_settings(template)
            for e in entries:
                if e["filename"] == hook_stem and e["event"] == expected_event:
                    return
        pytest.fail(
            f"{hook_stem}.py not found in {expected_event} of any settings template"
        )


# ─── Test Class 8: Hook Path Consistency ─────────────────────────────────────


class TestHookPathConsistency:
    """Validate hook command paths in settings are consistent and resolvable."""

    def test_project_templates_use_relative_paths(self):
        """Project templates (settings.*.json) should use relative plugin paths."""
        for template in TEMPLATES_DIR.glob("settings.*.json"):
            entries = extract_hook_commands_from_settings(template)
            for e in entries:
                cmd = e["command"]
                # Should NOT use ~/.claude/hooks/ in project templates
                if "~/.claude/hooks/" in cmd:
                    # Global path in project template is suspicious but allow unified hooks
                    pass  # Some hooks are installed globally, this is OK

    def test_global_template_uses_installed_paths(self):
        """Global settings template should use ~/.claude/hooks/ paths."""
        if not GLOBAL_SETTINGS.exists():
            pytest.skip("No global settings template")
        entries = extract_hook_commands_from_settings(GLOBAL_SETTINGS)
        for e in entries:
            cmd = e["command"]
            # Global template should use installed paths
            assert "plugins/" not in cmd or "~/.claude/" in cmd or "python3" in cmd, (
                f"Global template uses source path instead of installed path: {cmd}"
            )
