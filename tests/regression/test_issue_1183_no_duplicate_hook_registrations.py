"""Regression tests for Issue #1183.

Root-cause follow-up to Issue #1176. The #1176 in-handler dedup guard
addressed the SUBAGENTSTOP-DOUBLE-FIRE symptom; this suite locks the
underlying cause:

Both ``.claude/settings.json`` (written by ``sync_settings_hooks.py``) and
``.claude/settings.local.json`` (merged from ``templates/settings.local.json``)
register hooks at the same project tier. Claude Code merges same-tier
settings, so any hook present in BOTH files fires twice.

The fix:

1. ``templates/settings.local.json`` now carries an empty ``hooks`` block.
2. ``strip_duplicate_hooks.py --audit <project_root>`` detects duplicates
   between ``settings.json`` and ``settings.local.json`` (exit 1 = found).
3. ``sync_settings_hooks.py`` emits ``stale_local_warnings`` so upgrades
   surface a legacy ``settings.local.json`` carrying canonical hooks.
4. The in-handler dedup guard from #1176 is preserved as defense-in-depth.

Tests map 1-to-1 to acceptance criteria AC1-AC6 in the revised plan.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "autonomous-dev"
TEMPLATE_PATH = PLUGIN_ROOT / "templates" / "settings.local.json"
STRIP_SCRIPT = PLUGIN_ROOT / "scripts" / "strip_duplicate_hooks.py"


# Hook-command snippets used by tests 2-3 to fabricate matching settings.json
# / settings.local.json fixtures. The exact path doesn't matter — what
# matters is the basename .py reference for extract_hook_refs().
_GLOBAL_HOOK_CMD = (
    'python3 "$(git rev-parse --show-toplevel)/.claude/hooks/'
    'unified_session_tracker.py"'
)
_LOCAL_HOOK_CMD = (
    'python3 "$(git rev-parse --show-toplevel)/.claude/hooks/'
    'unified_session_tracker.py"'
)


def _make_settings_with_subagent_stop_hook(cmd: str) -> Dict[str, Any]:
    """Build a minimal valid settings.json structure with one SubagentStop hook."""
    return {
        "hooks": {
            "SubagentStop": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": cmd}],
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# AC1: templates/settings.local.json has empty hooks block
# ---------------------------------------------------------------------------
def test_settings_local_template_has_empty_hooks_block() -> None:
    """AC1: templates/settings.local.json MUST NOT register any hooks.

    Hooks live exclusively in settings.json (managed by
    sync_settings_hooks.py). Registering hooks in settings.local.json
    causes same-tier merge duplicates and every hook fires twice.
    """
    assert TEMPLATE_PATH.exists(), f"Template missing: {TEMPLATE_PATH}"
    data = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    hooks_block = data.get("hooks")
    assert hooks_block in ({}, None), (
        f"templates/settings.local.json must have empty hooks block, "
        f"got: {hooks_block!r} (Issue #1183)"
    )


# ---------------------------------------------------------------------------
# AC2 + AC5: strip_duplicate_hooks.py --audit detects overlapping refs
# ---------------------------------------------------------------------------
def test_audit_mode_detects_duplicate_hook_refs(tmp_path: Path) -> None:
    """AC2/AC5: --audit returns exit 1 + duplicates list when overlap exists.

    This is the exact bug Issue #1183 fixes: settings.json registers
    unified_session_tracker.py AND settings.local.json registers
    unified_session_tracker.py → Claude Code merges → hook fires twice.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps(_make_settings_with_subagent_stop_hook(_GLOBAL_HOOK_CMD)),
        encoding="utf-8",
    )
    (claude_dir / "settings.local.json").write_text(
        json.dumps(_make_settings_with_subagent_stop_hook(_LOCAL_HOOK_CMD)),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(STRIP_SCRIPT), "--audit", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert proc.returncode == 1, (
        f"audit must exit 1 when duplicates found; got {proc.returncode}\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    result = json.loads(proc.stdout)
    assert result["success"] is True
    assert result["duplicates_found"] > 0, (
        f"expected duplicates_found > 0, got {result['duplicates_found']}"
    )
    assert "unified_session_tracker.py" in result["duplicate_hook_refs"], (
        f"expected unified_session_tracker.py in duplicate_hook_refs, "
        f"got {result['duplicate_hook_refs']}"
    )


# ---------------------------------------------------------------------------
# AC3: Fresh deploy with current templates yields zero duplicates
# ---------------------------------------------------------------------------
def test_audit_mode_clean_when_template_used(tmp_path: Path) -> None:
    """AC3: audit reports zero duplicates when settings.local.json carries
    the current empty-hooks template content alongside a normal settings.json.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    # settings.json with the canonical hook registration.
    (claude_dir / "settings.json").write_text(
        json.dumps(_make_settings_with_subagent_stop_hook(_GLOBAL_HOOK_CMD)),
        encoding="utf-8",
    )
    # settings.local.json from the current template (empty hooks block).
    (claude_dir / "settings.local.json").write_text(
        TEMPLATE_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(STRIP_SCRIPT), "--audit", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert proc.returncode == 0, (
        f"audit must exit 0 when no duplicates; got {proc.returncode}\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    result = json.loads(proc.stdout)
    assert result["success"] is True
    assert result["duplicates_found"] == 0, (
        f"expected duplicates_found == 0 with current template, "
        f"got {result['duplicates_found']} "
        f"(refs: {result['duplicate_hook_refs']})"
    )


# ---------------------------------------------------------------------------
# AC4: In-handler dedup guard from #1176 remains operative
# ---------------------------------------------------------------------------
def test_dedup_guard_returns_true_then_false_on_same_key(
    tmp_path: Path,
) -> None:
    """AC4: _try_claim_subagent_stop_marker remains the runtime
    defense-in-depth. The root-cause fix removes the duplicate REGISTRATION;
    the guard catches duplicate FIRINGS that survive misconfiguration.

    First claim must return True; second claim for same key must return False.
    """
    # Load the hook module directly so we can pin marker_dir to tmp_path.
    hook_src = (
        PLUGIN_ROOT / "hooks" / "unified_session_tracker.py"
    )
    assert hook_src.exists(), f"hook missing: {hook_src}"
    spec = importlib.util.spec_from_file_location(
        "unified_session_tracker_under_test_1183", hook_src
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    claim = mod._try_claim_subagent_stop_marker
    key = "abc123def456abcd"  # 16-char hex-like key

    first = claim(key, marker_dir=tmp_path)
    second = claim(key, marker_dir=tmp_path)

    assert first is True, (
        f"first claim for fresh key must return True, got {first}"
    )
    assert second is False, (
        f"second claim for same key must return False, got {second}"
    )


# ---------------------------------------------------------------------------
# AC6: sync_settings_hooks.py emits stale_local_warnings on legacy local file
# ---------------------------------------------------------------------------
def test_sync_settings_hooks_emits_stale_local_warning(
    tmp_path: Path,
) -> None:
    """AC6: when settings.local.json on an upgrading repo still registers
    canonical hooks, sync_settings_hooks emits a warning in both
    ``stale_local_warnings`` and the human-readable ``message``.
    """
    # Set up plugin lib import path.
    lib_path = PLUGIN_ROOT / "lib"
    scripts_path = PLUGIN_ROOT / "scripts"
    for p in (str(lib_path), str(scripts_path)):
        if p not in sys.path:
            sys.path.insert(0, p)

    # Load sync_settings_hooks as a module.
    sync_src = scripts_path / "sync_settings_hooks.py"
    spec = importlib.util.spec_from_file_location(
        "sync_settings_hooks_under_test_1183", sync_src
    )
    assert spec is not None and spec.loader is not None
    sync_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync_mod)

    # Build a fake repo: .claude/settings.local.json carries the canonical
    # hook ref that the template would write into settings.json.
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    legacy_local = _make_settings_with_subagent_stop_hook(_LOCAL_HOOK_CMD)
    (claude_dir / "settings.local.json").write_text(
        json.dumps(legacy_local), encoding="utf-8"
    )
    # No settings.json yet — sync will create it.

    result = sync_mod.sync_repo(str(tmp_path), dry_run=False, count_only=False)

    assert result["success"] is True, f"sync_repo failed: {result}"
    assert "stale_local_warnings" in result, (
        f"result missing stale_local_warnings key: {sorted(result.keys())}"
    )
    assert "unified_session_tracker.py" in result["stale_local_warnings"], (
        f"expected unified_session_tracker.py in stale_local_warnings, "
        f"got {result['stale_local_warnings']}"
    )
    assert "settings.local.json still registers" in result["message"], (
        f"expected warning in message, got: {result['message']!r}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
