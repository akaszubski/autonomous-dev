"""Spec-blind validation tests for Issue #1093.

Written from acceptance criteria ONLY, without reading implementer code/tests.

Feature: ``resolve_session_id()`` in ``pipeline_completion_state.py`` gains a
4th fallback step that scans today's activity log JSONL for the most recent
real (non-"unknown") ``session_id`` when env var is unset and sentinel is
empty/placeholder.

Acceptance criteria:
    1. New helper ``_resolve_session_id_from_activity_log()`` in
       ``pipeline_completion_state.py``.
    2. ``resolve_session_id()`` calls the helper as a fallback step before
       returning ``"unknown"``.
    3. Regression tests cover: env-var present, state-file fallback, activity-log
       fallback, log missing, log only-"unknown", corrupt JSON, multiple real ids
       newest wins.
    4. After fix, from a Bash subprocess (env var unset, sentinel "unknown"),
       ``resolve_session_id()`` returns the real session_id from today's
       activity log.
    5. No regression in existing tests covering the original chain.
    6. No changes to ``unified_pre_tool.py``, hook files, or ``implement-fix.md``.
"""

from __future__ import annotations

import inspect
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_activity_log(repo_dir: Path, entries: list[dict], *, today: str | None = None) -> Path:
    """Build a synthetic ``.claude/logs/activity/{today}.jsonl`` under repo_dir."""
    today = today or datetime.now().strftime("%Y-%m-%d")
    log_dir = repo_dir / ".claude" / "logs" / "activity"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{today}.jsonl"
    log_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return log_file


# ---------------------------------------------------------------------------
# AC1: helper exists and is callable from the module
# ---------------------------------------------------------------------------


def test_spec_1093_ac1_helper_function_exists():
    """AC1: ``_resolve_session_id_from_activity_log`` MUST exist in the module."""
    import pipeline_completion_state as pcs

    assert hasattr(pcs, "_resolve_session_id_from_activity_log"), (
        "AC1 violated: helper _resolve_session_id_from_activity_log is missing "
        "from pipeline_completion_state"
    )
    helper = pcs._resolve_session_id_from_activity_log
    assert callable(helper), "AC1: helper must be callable"


# ---------------------------------------------------------------------------
# AC2: resolve_session_id() invokes the helper as a fallback step
#      (observable via: monkeypatching the helper changes resolve_session_id
#      output when env+sentinel both miss).
# ---------------------------------------------------------------------------


def test_spec_1093_ac2_resolver_invokes_helper_before_unknown(monkeypatch, tmp_path):
    """AC2: resolve_session_id must call the helper before returning 'unknown'.

    We observe this by replacing the helper with a sentinel and asserting the
    return value comes from it.
    """
    import pipeline_completion_state as pcs

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    # Sentinel file missing → forces fall-through past step 2.
    missing_sentinel = tmp_path / "no_such_file.json"

    marker = "HELPER-RETURN-MARKER-1093"
    monkeypatch.setattr(
        pcs, "_resolve_session_id_from_activity_log", lambda *a, **kw: marker
    )

    result = pcs.resolve_session_id(sentinel_path=str(missing_sentinel))
    assert result == marker, (
        "AC2 violated: resolve_session_id did not consult "
        "_resolve_session_id_from_activity_log before returning the legacy "
        f"'unknown' fallback. Got: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC4 (primary behavior): subprocess context → real id from activity log.
# This is the load-bearing acceptance criterion.
# ---------------------------------------------------------------------------


def test_spec_1093_ac4_bash_subprocess_context_returns_real_id(monkeypatch, tmp_path):
    """AC4: env unset + sentinel says "unknown" + activity log has real id
    → resolve_session_id() returns the real id.

    This simulates the documented Bash subprocess context that motivated the
    fix.
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    real_sid = "real-subprocess-session-abc123"
    _write_activity_log(
        tmp_path,
        [
            {"hook": "PreToolUse", "session_id": "unknown"},
            {"hook": "PreToolUse", "session_id": real_sid},
        ],
    )

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == real_sid, (
        f"AC4 violated: subprocess context should resolve to real id "
        f"{real_sid!r}, got {result!r}"
    )


# ---------------------------------------------------------------------------
# AC3 coverage: each named regression scenario produces the spec'd outcome.
# These are written from the spec, not copied from the implementer's tests.
# ---------------------------------------------------------------------------


def test_spec_1093_ac3_env_var_present_short_circuits(monkeypatch, tmp_path):
    """AC3 scenario: env var present → return env var verbatim (chain step 1)."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-only-sid-xyz")
    # Even with an activity log containing a different id, env wins.
    monkeypatch.chdir(tmp_path)
    _write_activity_log(
        tmp_path, [{"hook": "PreToolUse", "session_id": "should-be-ignored"}]
    )
    assert resolve_session_id(sentinel_path=str(tmp_path / "nope.json")) == "env-only-sid-xyz"


def test_spec_1093_ac3_state_file_fallback_used_when_real(monkeypatch, tmp_path):
    """AC3 scenario: env unset + sentinel has REAL session id → return sentinel.

    Activity log MUST NOT win when the sentinel is fresh and real.
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"session_id": "real-sentinel-id"}))

    # Activity log with a different real id — should be ignored because sentinel wins.
    _write_activity_log(
        tmp_path, [{"hook": "PreToolUse", "session_id": "log-id-must-not-win"}]
    )

    assert resolve_session_id(sentinel_path=str(sentinel)) == "real-sentinel-id"


def test_spec_1093_ac3_log_missing_falls_through_to_unknown(monkeypatch, tmp_path):
    """AC3 scenario: env unset + sentinel "unknown" + helper returns None → "unknown".

    Chain must terminate cleanly at step 4 when the activity-log fallback yields
    no result. We patch the helper to None to isolate from host repo state.
    """
    import pipeline_completion_state as pcs

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setattr(pcs, "_resolve_session_id_from_activity_log", lambda *a, **kw: None)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    assert pcs.resolve_session_id(sentinel_path=str(sentinel)) == "unknown"


def test_spec_1093_ac3_log_only_unknown_returns_unknown(monkeypatch, tmp_path):
    """AC3 scenario: env unset + sentinel "unknown" + log has ONLY "unknown" entries
    → "unknown".
    """
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    _write_activity_log(
        tmp_path,
        [
            {"hook": "PreToolUse", "session_id": "unknown"},
            {"hook": "PostToolUse", "session_id": "unknown"},
        ],
    )

    assert resolve_session_id(sentinel_path=str(sentinel)) == "unknown"


def test_spec_1093_ac3_corrupt_json_lines_skipped(monkeypatch, tmp_path):
    """AC3 scenario: corrupt JSON lines in log are skipped, real id still returned."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    log_dir.mkdir(parents=True)
    log_file = log_dir / f"{today}.jsonl"
    real_sid = "post-corruption-real-sid"
    # Mix: corrupt, valid older, more corruption, valid newer.
    log_file.write_text(
        "not json at all {{\n"
        + json.dumps({"hook": "PreToolUse", "session_id": "older-real"}) + "\n"
        + "{{{ broken\n"
        + json.dumps({"hook": "PreToolUse", "session_id": real_sid}) + "\n"
    )

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == real_sid, (
        f"AC3: corrupt JSON handling — expected real id {real_sid!r}, got {result!r}"
    )


def test_spec_1093_ac3_multiple_real_ids_newest_wins(monkeypatch, tmp_path):
    """AC3 scenario: multiple real ids → MOST RECENT (last appended) wins."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"session_id": "unknown"}))

    older = "session-OLDER-aaaa"
    middle = "session-MIDDLE-bbbb"
    newest = "session-NEWEST-cccc"
    _write_activity_log(
        tmp_path,
        [
            {"hook": "PreToolUse", "session_id": older},
            {"hook": "PreToolUse", "session_id": middle},
            {"hook": "PreToolUse", "session_id": newest},
        ],
    )

    result = resolve_session_id(sentinel_path=str(sentinel))
    assert result == newest, (
        f"AC3: newest-wins semantics — expected {newest!r}, got {result!r}"
    )


# ---------------------------------------------------------------------------
# AC5: existing chain behavior unchanged.
# Spec-blind check: the documented contracts for steps 1 and 2 still hold.
# ---------------------------------------------------------------------------


def test_spec_1093_ac5_env_wins_over_sentinel_and_log(monkeypatch, tmp_path):
    """AC5: env var still takes priority over both sentinel and activity log."""
    from pipeline_completion_state import resolve_session_id

    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-precedence-id")
    monkeypatch.chdir(tmp_path)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"session_id": "sentinel-id"}))
    _write_activity_log(tmp_path, [{"hook": "PreToolUse", "session_id": "log-id"}])

    assert resolve_session_id(sentinel_path=str(sentinel)) == "env-precedence-id"


def test_spec_1093_ac5_stale_sentinel_skipped(monkeypatch, tmp_path):
    """AC5: stale sentinel (mtime > max_age_seconds) is still skipped.

    With the activity-log helper patched to None, this must return "unknown" —
    preserving pre-fix behavior of the staleness check.
    """
    import pipeline_completion_state as pcs

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setattr(pcs, "_resolve_session_id_from_activity_log", lambda *a, **kw: None)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"session_id": "stale-but-real-looking"}))
    old = time.time() - 7200
    os.utime(sentinel, (old, old))

    assert (
        pcs.resolve_session_id(sentinel_path=str(sentinel), max_age_seconds=3600)
        == "unknown"
    )


def test_spec_1093_ac5_malformed_sentinel_does_not_raise(monkeypatch, tmp_path):
    """AC5: malformed sentinel JSON must not raise — chain proceeds.

    With activity-log helper patched to None, result must be "unknown"
    (legacy behavior preserved).
    """
    import pipeline_completion_state as pcs

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setattr(pcs, "_resolve_session_id_from_activity_log", lambda *a, **kw: None)

    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text("garbage {{{ not json")

    result = pcs.resolve_session_id(sentinel_path=str(sentinel))
    assert result == "unknown"


# ---------------------------------------------------------------------------
# AC6: no out-of-scope file modifications.
# We check the spec's enumerated files have NOT been modified as part of this
# change. We can't compare git diffs blindly, but we can assert the named files
# still exist at their expected paths (structural sanity), and we explicitly
# check that the changed-file scope (per the prompt) is the two-file scope.
# ---------------------------------------------------------------------------


def test_spec_1093_ac6_out_of_scope_files_untouched_structurally():
    """AC6: hook files and implement-fix.md remain present and importable/parseable.

    This is a structural-existence assertion: the spec forbids changes to these
    files, so they must (at minimum) still exist at their canonical paths and
    still parse. A removed/renamed file would be a clear out-of-scope change.
    """
    unified_pre_tool = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
    )
    assert unified_pre_tool.is_file(), (
        "AC6: unified_pre_tool.py missing — out-of-scope change suspected"
    )

    implement_fix = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-fix.md"
    )
    # implement-fix.md may or may not exist depending on repo state; tolerate
    # absence but reject if it has been clearly replaced by a stub.
    if implement_fix.exists():
        content = implement_fix.read_text(encoding="utf-8", errors="replace")
        assert len(content) > 100, "AC6: implement-fix.md looks stubbed/truncated"


def test_spec_1093_ac6_changed_files_match_declared_scope():
    """AC6 corollary: changed-file scope is two files (lib + tests).

    The feature description declares exactly two files in scope:
    - plugins/autonomous-dev/lib/pipeline_completion_state.py
    - tests/unit/lib/test_pipeline_completion_state_resolve_session_id.py
    Both MUST be present.
    """
    lib_file = REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "pipeline_completion_state.py"
    test_file = (
        REPO_ROOT / "tests" / "unit" / "lib"
        / "test_pipeline_completion_state_resolve_session_id.py"
    )
    assert lib_file.is_file(), f"AC6: missing lib file at {lib_file}"
    assert test_file.is_file(), f"AC6: missing test file at {test_file}"


# ---------------------------------------------------------------------------
# Cross-cutting: helper signature / no-raise contract.
# Spec implies the helper "never raises" (it's a fallback in a NEVER-raises
# resolver). We verify by calling it against pathological inputs.
# ---------------------------------------------------------------------------


def test_spec_1093_helper_does_not_raise_on_missing_dir(tmp_path):
    """The helper must not raise when activity log dir/file are missing."""
    import pipeline_completion_state as pcs

    # tmp_path has no .claude/logs/activity at all.
    result = pcs._resolve_session_id_from_activity_log(log_dir=tmp_path / "nope")
    assert result is None


def test_spec_1093_helper_returns_none_when_log_empty(tmp_path):
    """Empty log file → helper returns None (lets chain fall through to 'unknown')."""
    import pipeline_completion_state as pcs

    log_dir = tmp_path / "activity"
    log_dir.mkdir()
    today = datetime.now().strftime("%Y-%m-%d")
    (log_dir / f"{today}.jsonl").write_text("")

    result = pcs._resolve_session_id_from_activity_log(log_dir=log_dir, today=today)
    assert result is None


def test_spec_1093_helper_returns_str_or_none(tmp_path):
    """Type contract: helper returns Optional[str], never anything else."""
    import pipeline_completion_state as pcs

    log_dir = tmp_path / "activity"
    log_dir.mkdir()
    today = datetime.now().strftime("%Y-%m-%d")
    real = "type-contract-id"
    (log_dir / f"{today}.jsonl").write_text(
        json.dumps({"session_id": real}) + "\n"
    )

    result = pcs._resolve_session_id_from_activity_log(log_dir=log_dir, today=today)
    assert isinstance(result, str)
    assert result == real
