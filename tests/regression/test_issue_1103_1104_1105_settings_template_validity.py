"""Regression tests for Issues #1103, #1104, #1105: settings template validity.

These issues all stemmed from settings.local.json (and siblings) using
Claude-Code-invalid constructs that caused the entire template to be
skipped at load time:

  #1103: ``hooks.PreCommit`` event key — not recognized by Claude Code.
  #1104: ``matcher: {"tools": [...]}`` — object form rejected; must be
         pipe-separated string like ``"Write|Edit"``.
  #1105: ``"Bash(:*)"`` — invalid permission rule grammar. Plain ``Bash``
         (blanket) or specific ``Bash(<cmd>:*)`` is correct.

The fix:
  * Deleted the ``PreCommit`` block from ``settings.local.json`` (the 5
    referenced hook files still exist on disk and can be wired into a
    real git pre-commit hook later if desired — Claude Code's event
    model does not support ``PreCommit``).
  * Converted the ``auto_format`` matcher to the string ``"Write|Edit"``.
  * Replaced ``"Bash(:*)"`` with plain ``"Bash"`` in the two non-granular
    templates (``settings.strict-mode.json``, ``settings.autonomous-dev.json``)
    and deleted it from the granular ``settings.permission-batching.json``
    ``ask`` array (it was a stray entry, not a blanket Bash declaration).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Path depth check: this file lives at tests/regression/test_*.py
# So parents[2] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"

# The 4 settings templates touched by the issues. All MUST remain valid
# JSON and free of the three Claude-Code-invalid constructs.
SETTINGS_TEMPLATES = (
    "settings.local.json",
    "settings.strict-mode.json",
    "settings.permission-batching.json",
    "settings.autonomous-dev.json",
)

# The 5 hook files previously listed under the (broken) ``PreCommit`` event.
# They must still exist on disk so they can be wired into a real
# git pre-commit hook later — the fix removed their registration, not
# the files themselves.
PRECOMMIT_HOOK_FILES = (
    "auto_test.py",
    "security_scan.py",
    "validate_command_file_ops.py",
    "validate_claude_md_size.py",
    "enforce_regression_test.py",
)


def _load_template(name: str) -> dict:
    """Load one settings template as a dict.

    Args:
        name: Template basename, e.g. ``settings.local.json``.

    Returns:
        Parsed JSON dict.

    Raises:
        FileNotFoundError: If the template is missing from the templates dir.
    """
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Settings template missing: {path}\n"
            f"Expected one of: {sorted(p.name for p in TEMPLATES_DIR.glob('settings*.json'))}\n"
            f"See: plugins/autonomous-dev/templates/TEMPLATES.md"
        )
    return json.loads(path.read_text())


def _iter_matchers(template: dict):
    """Yield every ``matcher`` value across every hook event in a template.

    Args:
        template: Parsed settings template.

    Yields:
        Each ``matcher`` value encountered (any JSON type — string, dict, etc.).
    """
    for event_name, event_entries in template.get("hooks", {}).items():
        if not isinstance(event_entries, list):
            continue
        for entry in event_entries:
            if isinstance(entry, dict) and "matcher" in entry:
                yield event_name, entry["matcher"]


# Test 1 (#1103): No ``PreCommit`` event key in any template's hooks dict.
@pytest.mark.parametrize("template_name", SETTINGS_TEMPLATES)
def test_no_precommit_event_key(template_name: str) -> None:
    """Issue #1103: ``PreCommit`` is not a valid Claude Code hook event.

    Its presence causes Claude Code to skip the entire settings file at
    load time. The fix is to delete the block (the underlying hook files
    remain on disk and can be wired into a real git pre-commit hook later).
    """
    template = _load_template(template_name)
    hooks = template.get("hooks", {})
    assert "PreCommit" not in hooks, (
        f"{template_name} still registers hooks under 'PreCommit', "
        f"which Claude Code does not recognize. The entire settings file "
        f"will be skipped at load time.\n"
        f"Expected: 'PreCommit' key absent from hooks dict.\n"
        f"See: Issue #1103"
    )


# Test 2 (#1104): All matcher fields must be strings, never objects.
@pytest.mark.parametrize("template_name", SETTINGS_TEMPLATES)
def test_all_matchers_are_strings(template_name: str) -> None:
    """Issue #1104: ``matcher`` must be a string (pipe-separated for multiple).

    The object form ``{"tools": ["Write", "Edit"]}`` is rejected by
    Claude Code and causes the settings file to be skipped.
    """
    template = _load_template(template_name)
    bad: list[tuple[str, object]] = [
        (event, matcher)
        for event, matcher in _iter_matchers(template)
        if not isinstance(matcher, str)
    ]
    assert not bad, (
        f"{template_name} has non-string matcher(s): {bad}\n"
        f"Expected: matcher must be a string like 'Write|Edit' or '*'.\n"
        f"See: Issue #1104"
    )


# Test 3 (#1105): No ``Bash(:*)`` literal anywhere in permissions arrays.
@pytest.mark.parametrize("template_name", SETTINGS_TEMPLATES)
def test_no_bash_colon_star_permission(template_name: str) -> None:
    """Issue #1105: ``"Bash(:*)"`` is invalid permission-rule grammar.

    Claude Code rejects this literal. Replace with plain ``"Bash"``
    (blanket) or remove entirely.
    """
    template = _load_template(template_name)
    permissions = template.get("permissions", {})
    for bucket_name in ("allow", "deny", "ask"):
        bucket = permissions.get(bucket_name, [])
        if not isinstance(bucket, list):
            continue
        assert "Bash(:*)" not in bucket, (
            f"{template_name} has 'Bash(:*)' in permissions.{bucket_name}. "
            f"This grammar is invalid and Claude Code rejects it.\n"
            f"Expected: use plain 'Bash' (blanket) or a specific "
            f"'Bash(<cmd>:*)' pattern.\n"
            f"See: Issue #1105"
        )


# Test 4: All 4 settings templates parse cleanly as JSON.
@pytest.mark.parametrize("template_name", SETTINGS_TEMPLATES)
def test_template_is_valid_json(template_name: str) -> None:
    """All 4 settings templates must parse cleanly as JSON.

    This is a meta-guard: even if the other tests fail, this one isolates
    the bug class — a non-parseable file gives a useless error elsewhere.
    """
    path = TEMPLATES_DIR / template_name
    assert path.exists(), f"Template missing: {path}"
    # json.loads raises a clear error on parse failure; that IS the assert.
    data = json.loads(path.read_text())
    assert isinstance(data, dict), (
        f"{template_name} root must be a JSON object, got {type(data).__name__}"
    )


# Test 5 (#1103 follow-on): the 5 PreCommit hooks still exist on disk.
# When we removed the broken PreCommit registration, the hook source files
# must remain so they can be re-wired correctly later (e.g., as a real
# git pre-commit hook in .git/hooks/, not as a Claude Code event).
def test_precommit_hook_files_still_exist_on_disk() -> None:
    """Issue #1103: removing the broken PreCommit block must not delete hooks.

    The 5 hook files referenced by the deleted PreCommit block were still
    valid and useful — only the Claude Code event registration was wrong.
    Verify they remain on disk so they can be wired into a real git hook
    or another Claude Code event later.
    """
    missing = [name for name in PRECOMMIT_HOOK_FILES if not (HOOKS_DIR / name).exists()]
    assert not missing, (
        f"PreCommit-block hook files missing from {HOOKS_DIR}: {missing}\n"
        f"Removing the broken 'PreCommit' registration must NOT delete the hook "
        f"sources — they remain valid and can be wired into a real git hook later.\n"
        f"See: Issue #1103"
    )
