"""Regression tests for Issue #1008 — rm -rf with unresolved variable expansion.

The detection was historically listed in the hard-floor registry without an
implementation. Issue #1004 removed the aspirational entry; Issue #1008
implements the actual catastrophe-prevention guard.

Dangerous patterns (MUST deny):
    rm -rf $VARNAME           — unquoted var; empty expansion -> rm -rf
    rm -rf ${VARNAME}         — brace form, unquoted
    rm -rf $HOME/subpath      — unquoted var with literal suffix
    rm -f  $VAR               — single-file rm with unquoted var

Safe patterns (MUST allow):
    rm -rf "$VARNAME"         — quoted; empty expansion -> rm -rf "" (no-op)
    rm -rf "${VARNAME}"       — quoted brace form
    rm -rf /tmp/foo           — literal path
    ls -la                    — not an rm command

This module covers the 10 tests required by the implementation plan plus
extra robustness cases (heredoc, --body sanitization).

Issue: #1008
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Path arithmetic: tests/regression/<file>.py -> parents[2] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_HARD_FLOOR_CONFIG = (
    _REPO_ROOT / "plugins" / "autonomous-dev" / "config" / "hard_floor_hooks.json"
)

for _p in (_HOOK_DIR, _LIB_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import unified_pre_tool as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Tests 1-3 — Dangerous patterns: MUST return ("deny", reason)
# ---------------------------------------------------------------------------


def test_1_rm_rf_dollar_var_blocked() -> None:
    """`rm -rf $VARNAME` (unquoted, no braces) is blocked."""
    result = hook._check_rm_rf_unresolved_vars("rm -rf $VARNAME")
    assert result is not None, "Unquoted $VARNAME must be flagged"
    decision, reason = result
    assert decision == "deny"
    assert "$VARNAME" in reason
    assert "BLOCKED" in reason


def test_2_rm_rf_brace_var_blocked() -> None:
    """`rm -rf ${VARNAME}` (unquoted, brace form) is blocked."""
    result = hook._check_rm_rf_unresolved_vars("rm -rf ${VARNAME}")
    assert result is not None, "Unquoted ${VARNAME} must be flagged"
    decision, reason = result
    assert decision == "deny"
    assert "${VARNAME}" in reason


def test_3_rm_rf_var_with_subpath_blocked() -> None:
    """`rm -rf $HOME/subpath` is blocked even with a literal suffix.

    Rationale from the spec: if $HOME is empty, the command expands to
    `rm -rf /subpath`, which is still catastrophic.
    """
    result = hook._check_rm_rf_unresolved_vars("rm -rf $HOME/subpath")
    assert result is not None, "Unquoted $HOME with subpath must be flagged"
    decision, reason = result
    assert decision == "deny"
    assert "$HOME" in reason


# ---------------------------------------------------------------------------
# Tests 4-7 — Safe patterns: MUST return None
# ---------------------------------------------------------------------------


def test_4_rm_rf_quoted_dollar_var_allowed() -> None:
    """`rm -rf "$VARNAME"` is safe — quoted variable, empty expansion is no-op."""
    result = hook._check_rm_rf_unresolved_vars('rm -rf "$VARNAME"')
    assert result is None, f"Quoted $VARNAME must NOT be flagged, got {result!r}"


def test_5_rm_rf_quoted_brace_var_allowed() -> None:
    """`rm -rf "${VARNAME}"` is safe — quoted brace form."""
    result = hook._check_rm_rf_unresolved_vars('rm -rf "${VARNAME}"')
    assert result is None, f"Quoted ${{VARNAME}} must NOT be flagged, got {result!r}"


def test_6_rm_rf_literal_path_allowed() -> None:
    """`rm -rf /tmp/foo` (literal path, no vars) is safe."""
    result = hook._check_rm_rf_unresolved_vars("rm -rf /tmp/foo")
    assert result is None, f"Literal path must NOT be flagged, got {result!r}"


def test_7_non_rm_command_allowed() -> None:
    """`ls -la` (not an rm command) is not flagged."""
    result = hook._check_rm_rf_unresolved_vars("ls -la")
    assert result is None, f"Non-rm command must NOT be flagged, got {result!r}"


# ---------------------------------------------------------------------------
# Test 8 — `rm -f` (single-file force) with unquoted var also dangerous
# ---------------------------------------------------------------------------


def test_8_rm_f_unquoted_var_blocked() -> None:
    """`rm -f $VAR` is blocked.

    Even single-file `rm -f` with an unquoted var is dangerous: if $VAR
    expands to a glob (e.g. `*`), or to a critical file path, the deletion
    is silent (`-f` suppresses errors). The catastrophe surface is smaller
    than `-rf`, but the failure mode is the same: trust-broken expansion.
    """
    result = hook._check_rm_rf_unresolved_vars("rm -f $VAR")
    assert result is not None, "rm -f $VAR (unquoted) must be flagged"
    decision, reason = result
    assert decision == "deny"
    assert "$VAR" in reason


# ---------------------------------------------------------------------------
# Test 9 — Integration: dangerous command takes the deny pipeline
# ---------------------------------------------------------------------------


def test_9_integration_dangerous_command_takes_deny_path(monkeypatch) -> None:
    """Integration check: when the function is wired into the bash command
    validator, a dangerous command returns a deny decision.

    We do not exercise the full main() pipeline here (it requires stdin
    setup, settings.json, etc.). Instead we (a) prove the function exists
    on the imported hook module, (b) prove it is referenced from the
    integration path, and (c) prove the returned decision shape is the one
    the integration path consumes.
    """
    # (a) Function present on module.
    assert hasattr(hook, "_check_rm_rf_unresolved_vars")
    fn = hook._check_rm_rf_unresolved_vars
    assert callable(fn)

    # (b) Wire-up verification: the integration path must reference the
    # function by name, otherwise it never fires regardless of detection
    # correctness.
    hook_source = (_HOOK_DIR / "unified_pre_tool.py").read_text(encoding="utf-8")
    assert "_check_rm_rf_unresolved_vars(command)" in hook_source, (
        "The new detector must be called from the bash-command validation "
        "path in unified_pre_tool.main(); otherwise the function exists "
        "but never fires."
    )

    # (c) Decision shape matches the deny-pipeline contract: a tuple of
    # (decision, reason) where decision is the literal string "deny".
    result = fn("rm -rf $UNSET_DIR")
    assert isinstance(result, tuple) and len(result) == 2
    decision, reason = result
    assert decision == "deny"
    assert isinstance(reason, str) and reason.startswith("BLOCKED:")


# ---------------------------------------------------------------------------
# Test 10 — Hard-floor registry entry exists
# ---------------------------------------------------------------------------


def test_10_hard_floor_registry_has_entry() -> None:
    """The new function MUST be registered as hard-floor in
    `config/hard_floor_hooks.json`. Without this entry, session-mode logic
    could (incorrectly) disable it.
    """
    assert _HARD_FLOOR_CONFIG.is_file(), f"Missing config: {_HARD_FLOOR_CONFIG}"
    data = json.loads(_HARD_FLOOR_CONFIG.read_text(encoding="utf-8"))

    entries = data["hard_floor_hooks"]
    matched = [
        entry
        for entry in entries
        if entry.get("hook") == "unified_pre_tool.py"
        and entry.get("function") == "_check_rm_rf_unresolved_vars"
    ]
    assert matched, (
        "hard_floor_hooks.json must list "
        "unified_pre_tool.py::_check_rm_rf_unresolved_vars as a "
        "catastrophe-prevention entry (Issue #1008)."
    )
    # The entry MUST have a non-empty `reason` string for audit clarity.
    entry = matched[0]
    assert isinstance(entry.get("reason"), str) and entry["reason"].strip(), (
        "hard-floor entry must carry a human-readable `reason` describing "
        "the catastrophe it prevents."
    )


# ---------------------------------------------------------------------------
# Robustness: extra coverage that doesn't count toward the 10 spec tests but
# locks important behaviors against future regressions.
# ---------------------------------------------------------------------------


def test_robust_heredoc_body_does_not_trigger() -> None:
    """A `gh issue create` heredoc body that mentions `rm -rf $VAR` text
    must NOT trigger the detector. Same sanitization as
    `_check_bash_state_deletion` (Issue #866).
    """
    cmd = (
        "gh issue create --title bug --body \"$(cat <<'EOF'\n"
        "While testing I ran `rm -rf $VAR` and bad things happened.\n"
        "EOF\n"
        ")\""
    )
    # The --body "$(cat ...)" sanitization strips the body content before
    # scanning, so the inline `rm -rf $VAR` inside the heredoc must not fire.
    result = hook._check_rm_rf_unresolved_vars(cmd)
    assert result is None, (
        f"Heredoc/body text should be sanitized before scanning, got {result!r}"
    )


def test_robust_reversed_flag_order_blocked() -> None:
    """`rm -fr $VAR` (flag order reversed) is still detected."""
    result = hook._check_rm_rf_unresolved_vars("rm -fr $VAR")
    assert result is not None
    assert result[0] == "deny"


def test_robust_capital_flag_blocked() -> None:
    """`rm -Rf $VAR` (capital -R for recursive) is detected."""
    result = hook._check_rm_rf_unresolved_vars("rm -Rf $VAR")
    assert result is not None
    assert result[0] == "deny"


def test_robust_extra_whitespace_blocked() -> None:
    """Extra whitespace between rm, flags, and var is tolerated."""
    result = hook._check_rm_rf_unresolved_vars("rm   -rf   $VAR")
    assert result is not None
    assert result[0] == "deny"


def test_robust_single_quoted_var_allowed() -> None:
    """`rm -rf '$VAR'` — single quoted, also safe (single quotes prevent
    expansion entirely, so the target is the literal string '$VAR'). The
    detector treats this as not-an-unquoted-var and allows it.
    """
    result = hook._check_rm_rf_unresolved_vars("rm -rf '$VAR'")
    assert result is None, f"Single-quoted var must NOT be flagged, got {result!r}"


def test_robust_empty_command_safe() -> None:
    """Empty / whitespace-only command does not raise and returns None."""
    assert hook._check_rm_rf_unresolved_vars("") is None
    assert hook._check_rm_rf_unresolved_vars("   ") is None
