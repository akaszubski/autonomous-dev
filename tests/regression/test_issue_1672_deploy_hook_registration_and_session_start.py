"""Regression tests for Issue #1672.

Two defects, one test module:

1. ``SessionStart-batch-recovery.sh`` was documented in CLAUDE.md as the
   session-continuity mechanism but was reportedly bound to no lifecycle
   event. Verify the template ``plugins/autonomous-dev/templates/
   settings.autonomous-dev.json`` registers ``SessionStart`` pointing at
   the shipped script, so ``sync_settings_hooks.py`` propagates it to
   every consumer repo on deploy.

2. ``scripts/deploy-all.sh``'s hook-registration count check was
   permanently red in every repo because it counted only the per-repo
   ``settings.json``, ignoring ``settings.local.json`` and the global
   ``~/.claude/settings.json``. Fixed by ``count_hook_registrations.count_union``.
   Watched here both PERMITTING a correct union (>= 8) and REFUSING a
   deliberate under-registration (< 8) — the negative control the
   original check lacked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import count_hook_registrations  # noqa: E402


_TEMPLATE_PATH = (
    _REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "templates"
    / "settings.autonomous-dev.json"
)
_SESSION_START_SCRIPT = (
    _REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "hooks"
    / "SessionStart-batch-recovery.sh"
)


# =============================================================================
# Defect 1: SessionStart binding present in the settings template.
# =============================================================================
def test_session_start_hook_script_exists_and_is_executable() -> None:
    assert _SESSION_START_SCRIPT.exists(), (
        f"SessionStart script missing: {_SESSION_START_SCRIPT}"
    )
    mode = _SESSION_START_SCRIPT.stat().st_mode
    assert mode & 0o111, "SessionStart script is not executable"


def test_settings_template_registers_session_start() -> None:
    """The shipped template MUST bind SessionStart so consumers pick it up."""

    data = json.loads(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    hooks = data.get("hooks", {})
    assert "SessionStart" in hooks, (
        "SessionStart absent from settings template — the documented "
        "session-continuity mechanism (CLAUDE.md § Session Continuity) "
        "would silently fail to run. See Issue #1672 defect 1."
    )
    session_start = hooks["SessionStart"]
    assert isinstance(session_start, list) and session_start, (
        "SessionStart binding is empty in template"
    )
    # Verify the binding actually references the shipped script.
    entries_text = json.dumps(session_start)
    assert "SessionStart-batch-recovery.sh" in entries_text, (
        "SessionStart binding does not reference SessionStart-batch-recovery.sh"
    )


# =============================================================================
# Defect 2: union hook-count check — PERMIT arm (correct install).
# =============================================================================
def _write_settings(path: Path, event_names: list[str]) -> None:
    payload = {"hooks": {name: [{"matcher": "*", "hooks": []}] for name in event_names}}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_count_union_permits_correct_install(tmp_path: Path) -> None:
    """Split-across-three-files install with 8 unique events must be permitted."""

    proj = tmp_path / "project" / "settings.json"
    local = tmp_path / "project" / "settings.local.json"
    globl = tmp_path / "global" / "settings.json"
    proj.parent.mkdir(parents=True)
    globl.parent.mkdir(parents=True)

    _write_settings(proj, ["PreToolUse", "PostToolUse", "PostCompact", "PreCompact"])
    _write_settings(local, ["PreCompact", "PostCompact"])  # overlap intentional
    _write_settings(
        globl,
        ["Stop", "SubagentStop", "TaskCompleted", "UserPromptSubmit"],
    )

    count = count_hook_registrations.count_union(str(proj), str(local), str(globl))
    assert count >= 8, (
        f"union should count >= 8 (split-by-design install), got {count}"
    )


# =============================================================================
# Defect 2: union hook-count check — REFUSE arm (negative control).
# =============================================================================
def test_count_union_refuses_under_registration(tmp_path: Path) -> None:
    """Deliberate under-registration must produce a count below the threshold."""

    proj = tmp_path / "settings.json"
    local = tmp_path / "settings.local.json"
    globl = tmp_path / "global-settings.json"

    _write_settings(proj, ["PreToolUse"])
    _write_settings(local, ["PreCompact"])
    _write_settings(globl, ["Stop"])

    count = count_hook_registrations.count_union(str(proj), str(local), str(globl))
    assert count < 8, (
        f"under-registered fixture should return < 8, got {count} — a "
        "check that cannot fail cannot detect regressions (Issue #1672)."
    )
    assert count == 3, f"expected 3 distinct events, got {count}"


# =============================================================================
# Defect 2: graceful degradation on missing files.
# =============================================================================
def test_count_union_handles_missing_files(tmp_path: Path) -> None:
    """Missing files (fresh install, no local/global yet) must not raise."""

    proj = tmp_path / "settings.json"
    _write_settings(proj, ["PreToolUse", "PostToolUse"])

    count = count_hook_registrations.count_union(
        str(proj),
        str(tmp_path / "nonexistent-local.json"),
        str(tmp_path / "nonexistent-global.json"),
    )
    assert count == 2


def test_count_union_handles_malformed_json(tmp_path: Path) -> None:
    """Malformed JSON must not raise — count that file's contribution as zero."""

    bad = tmp_path / "settings.json"
    bad.write_text("{not valid json", encoding="utf-8")

    good = tmp_path / "settings.local.json"
    _write_settings(good, ["PreToolUse", "PostToolUse", "Stop"])

    count = count_hook_registrations.count_union(
        str(bad), str(good), str(tmp_path / "missing.json")
    )
    assert count == 3


def test_count_union_all_files_missing_returns_zero(tmp_path: Path) -> None:
    count = count_hook_registrations.count_union(
        str(tmp_path / "a.json"),
        str(tmp_path / "b.json"),
        str(tmp_path / "c.json"),
    )
    assert count == 0
