"""Phase B: standardized hook command paths in settings templates. Issue: #996

These tests lock in the canonical pattern
``$(git rev-parse --show-toplevel)/.claude/hooks/<NAME>.<py|sh>`` for every
hook command in every settings template shipped by the plugin. Two legacy
patterns are explicitly rejected: ``~/.claude/...`` (hardcodes the global
cache path) and ``--git-common-dir`` (resolves to the main repo's git dir,
breaking worktree-local hook deployments).

Personal-data permission entries (``~/.ssh/**``, ``~/.aws/**``) are NOT hook
commands and MUST be preserved verbatim in the ``permissions`` block.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"
TEMPLATE_NAMES = (
    "settings.autonomous-dev.json",
    "settings.default.json",
    "settings.granular-bash.json",
    "settings.local.json",
    "settings.permission-batching.json",
    "settings.strict-mode.json",
)
CANONICAL_RE = re.compile(
    r"\$\(git rev-parse --show-toplevel\)/\.claude/hooks/[A-Za-z0-9_\-/]+\.(py|sh)"
)


def _iter_hook_commands():
    """Yield ``(template_name, command_str)`` for every hook command."""
    for name in TEMPLATE_NAMES:
        data = json.loads((TEMPLATES_DIR / name).read_text())
        for entries in data.get("hooks", {}).values():
            for entry in entries:
                for h in entry.get("hooks", []):
                    cmd = h.get("command", "")
                    if cmd:
                        yield name, cmd


def test_all_six_templates_exist():
    """All 6 settings templates referenced by the plan ship with the plugin."""
    missing = [n for n in TEMPLATE_NAMES if not (TEMPLATES_DIR / n).is_file()]
    assert not missing, f"Missing templates: {missing}"


def test_no_tilde_paths_in_hook_commands():
    """No hook command may reference ``~/.claude/`` (Issue #996, Phase B)."""
    offenders = [(n, c) for n, c in _iter_hook_commands() if "~/.claude/" in c]
    assert not offenders, (
        "Hook commands must not reference ~/.claude/. "
        f"Offenders: {offenders}"
    )


def test_no_legacy_git_common_dir_in_hook_commands():
    """No hook command may use ``--git-common-dir`` (Issue #996, Phase B).

    ``--git-common-dir`` resolves to the main repo's git directory which
    breaks worktree-local hook deployments. The canonical alternative is
    ``--show-toplevel``.
    """
    offenders = [(n, c) for n, c in _iter_hook_commands() if "--git-common-dir" in c]
    assert not offenders, (
        "Hook commands must use --show-toplevel, not --git-common-dir. "
        f"Offenders: {offenders}"
    )


def test_script_hook_commands_use_canonical_pattern():
    """Every ``.py``/``.sh`` hook command matches the canonical regex."""
    missing = []
    for name, cmd in _iter_hook_commands():
        # Skip non-script commands (e.g. ``echo`` lines in strict-mode).
        if not re.search(r"\.(py|sh)\b", cmd):
            continue
        if not CANONICAL_RE.search(cmd):
            missing.append((name, cmd))
    assert not missing, (
        "Script hook commands must match "
        "$(git rev-parse --show-toplevel)/.claude/hooks/<X>.<py|sh>. "
        f"Offenders: {missing}"
    )


def test_personal_permission_entries_preserved():
    """``~/.ssh`` / ``~/.aws`` deny entries are NOT hook commands and must remain.

    Phase B's path-style enforcement only targets hook commands. Personal
    data deny entries in ``permissions.deny`` must survive verbatim, otherwise
    we silently weaken the security posture every template ships with.
    """
    expected_tokens = ("~/.ssh/", "~/.aws/")
    for name in TEMPLATE_NAMES:
        text = (TEMPLATES_DIR / name).read_text()
        # Only assert preservation for templates that originally had these
        # permission entries — not every template includes them.
        if not any(token in text for token in expected_tokens):
            continue
        data = json.loads(text)
        perms = data.get("permissions", {})
        all_perm_strings = " ".join(
            perms.get("allow", []) + perms.get("deny", []) + perms.get("ask", [])
        )
        assert any(token in all_perm_strings for token in expected_tokens), (
            f"{name}: personal permission entries (~/.ssh, ~/.aws) were "
            f"stripped from permissions section"
        )
