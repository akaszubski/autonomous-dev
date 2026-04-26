"""Spec-blind validation for Issue #970 — hook recovery invariant.

Tests are derived ONLY from the acceptance criteria in the final plan.
No knowledge of implementation internals is assumed beyond:

- Public function names: ``can_user_recover``, ``log_block_with_recovery``,
  ``clear_stale_state``, ``is_recovery_disabled``
- Public artifact paths declared in the AC text:
    * ``plugins/autonomous-dev/lib/hook_recovery.py`` (module)
    * ``plugins/autonomous-dev/config/hook_recovery_exemptions.json``
    * ``scripts/audit_hook_recovery.py``
    * ``.claude/logs/hook-recovery.jsonl`` (log)
    * ``.claude/plan_critic_verdict.json`` (verdict signal)
    * ``.claude/plan_mode_exit.json`` (marker output)
    * ``tests/regression/test_issue_937_938_941_970.py`` (regression suite)
- Public env vars declared in the AC text:
    * ``HOOK_RECOVERY_DISABLED``
    * ``AUDIT_HOOK_RECOVERY_STRICT``
    * ``CLAUDE_SESSION_ID``

TESTABLE CRITERIA (extracted in Phase 1):

1. AC#1 — module exists, exports 4 callables, none raise on malformed input.
   TEST: import module, getattr each name, assert callable, feed each garbage
   inputs, assert no exception escapes.
2. AC#2 — log_block_with_recovery writes JSONL row with 6 required fields.
   TEST: invoke once, parse last line of log file, assert keys present.
3. AC#3 — race fix: PROCEED verdict + ExitPlanMode → marker stage=critique_done
   AND verdict file consumed AND no second plan-critic needed.
   Negative: verdict=REVISE → stage=plan_exited AND verdict file kept.
   TEST: subprocess plan_mode_exit_detector.py with simulated PostToolUse.
4. AC#4 — _is_pipeline_active() refreshes mtime ONLY when state[session_id] ==
   CLAUDE_SESSION_ID. Owner: refresh. Foreign: do NOT refresh.
   TEST: import _is_pipeline_active, run twice with matching/mismatching sids,
   assert mtime-advance / no-advance.
5. AC#5 — audit script exits 0 in default WARN-ONLY mode; with
   AUDIT_HOOK_RECOVERY_STRICT=1 exits 0 (clean) or 1 (violations).
   TEST: subprocess audit script with/without env var.
6. AC#6 — exemption config exists and parses. Malformed copy is parsed safely
   (can_user_recover does not raise).
   TEST: load real file as JSON. Build malformed temp file, call
   can_user_recover, assert no exception.
7. AC#7 — HOOK_RECOVERY_DISABLED=1 → log_block_with_recovery is a no-op.
   TEST: capture log size, set env var, invoke, assert no growth.
8. AC#8 — at least 3 deny-path log_block_with_recovery() call sites in
   unified_pre_tool.py.
   TEST: read source, count occurrences, assert >= 3.
9. AC#9 — regression suite contains at least one test per AC (>= 9 tests).
   TEST: import the regression module, count test functions, assert >= 9.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path resolution — try multiple locations per spec instructions.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

LIB_CANDIDATES = [
    REPO_ROOT / "plugins" / "autonomous-dev" / "lib",
    Path.home() / ".claude" / "lib",
    Path.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",
]

HOOKS_CANDIDATES = [
    REPO_ROOT / "plugins" / "autonomous-dev" / "hooks",
    Path.home() / ".claude" / "hooks",
    Path.home() / ".claude" / "plugins" / "autonomous-dev" / "hooks",
]


def _find_first(candidates, *, must_exist: bool = True) -> Path:
    for c in candidates:
        if c.exists():
            return c
    if must_exist:
        pytest.fail(f"None of these paths exist: {candidates}")
    return candidates[0]


def _import_module_from_file(name: str, path: Path):
    """Import a python file under a unique module name."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        pytest.fail(f"Cannot build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    # Ensure the lib dir is importable for transitive imports.
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def lib_dir() -> Path:
    return _find_first(LIB_CANDIDATES)


@pytest.fixture(scope="module")
def hooks_dir() -> Path:
    return _find_first(HOOKS_CANDIDATES)


@pytest.fixture(scope="module")
def hook_recovery(lib_dir: Path):
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
    module_path = lib_dir / "hook_recovery.py"
    assert module_path.exists(), f"hook_recovery.py not at {module_path}"
    return _import_module_from_file("hook_recovery_specvalid_970", module_path)


# ---------------------------------------------------------------------------
# AC#1 — module exists, exports 4 callables, none raise on malformed input.
# ---------------------------------------------------------------------------


def test_spec_970_ac1_module_exports_four_public_callables(hook_recovery):
    required = [
        "can_user_recover",
        "log_block_with_recovery",
        "clear_stale_state",
        "is_recovery_disabled",
    ]
    missing = [n for n in required if not hasattr(hook_recovery, n)]
    assert not missing, f"hook_recovery.py missing public functions: {missing}"
    for name in required:
        attr = getattr(hook_recovery, name)
        assert callable(attr), f"{name} should be callable, got {type(attr).__name__}"


def test_spec_970_ac1_public_functions_never_raise_on_garbage(
    hook_recovery, tmp_path, monkeypatch
):
    """Each public function must swallow malformed inputs and never raise."""
    monkeypatch.chdir(tmp_path)

    # is_recovery_disabled — no inputs, but exercise weird env values.
    for raw in ("", "0", "false", "1", "true", "garbage"):
        monkeypatch.setenv("HOOK_RECOVERY_DISABLED", raw)
        try:
            hook_recovery.is_recovery_disabled()
        except Exception as e:  # pragma: no cover - regression catch
            pytest.fail(f"is_recovery_disabled() raised on env={raw!r}: {e!r}")
    monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)

    # can_user_recover — empty / unicode / None-ish inputs.
    bad_inputs = [
        {"hook_name": "", "block_reason": ""},
        {"hook_name": "x" * 10000, "block_reason": "y" * 10000},
        {"hook_name": "\x00", "block_reason": "\x00\x01"},
        {"hook_name": "missing.py", "block_reason": "no such reason"},
    ]
    for kwargs in bad_inputs:
        try:
            result = hook_recovery.can_user_recover(**kwargs)
        except Exception as e:
            pytest.fail(f"can_user_recover raised on {kwargs}: {e!r}")
        assert isinstance(result, bool), "can_user_recover must return bool"

    # log_block_with_recovery — bizarre inputs and missing dirs.
    for kwargs in [
        {
            "hook_name": "",
            "tool_name": "",
            "block_reason": "",
            "recovery_hint": "",
        },
        {
            "hook_name": "spec.py",
            "tool_name": "Write",
            "block_reason": "x" * 5000,
            "recovery_hint": "y" * 5000,
            "session_id": "spec-validator",
        },
    ]:
        try:
            hook_recovery.log_block_with_recovery(**kwargs)
        except Exception as e:
            pytest.fail(f"log_block_with_recovery raised on {kwargs}: {e!r}")

    # clear_stale_state — non-existent path, corrupt JSON path, dir path.
    nonexistent = tmp_path / "nope" / "nada.json"
    try:
        result = hook_recovery.clear_stale_state(
            nonexistent, owning_session_id="spec-A"
        )
    except Exception as e:
        pytest.fail(f"clear_stale_state(nonexistent) raised: {e!r}")
    assert isinstance(result, bool)

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{this is not json")
    try:
        hook_recovery.clear_stale_state(corrupt, owning_session_id="spec-A")
    except Exception as e:
        pytest.fail(f"clear_stale_state(corrupt) raised: {e!r}")

    a_directory = tmp_path / "adir"
    a_directory.mkdir()
    try:
        hook_recovery.clear_stale_state(a_directory, owning_session_id="spec-A")
    except Exception as e:
        pytest.fail(f"clear_stale_state(directory) raised: {e!r}")


# ---------------------------------------------------------------------------
# AC#2 — JSONL log row schema check.
# ---------------------------------------------------------------------------


def test_spec_970_ac2_log_row_has_required_fields(
    hook_recovery, tmp_path, monkeypatch
):
    """One call → one JSONL line with the 6 declared fields."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "spec-validator-970")

    log_path = tmp_path / ".claude" / "logs" / "hook-recovery.jsonl"
    if log_path.exists():
        log_path.unlink()

    hook_recovery.log_block_with_recovery(
        hook_name="unified_pre_tool.py",
        tool_name="Write",
        block_reason="spec validator probe — AC#2",
        recovery_hint="this is a probe, ignore",
        session_id="spec-validator-970",
    )

    assert log_path.exists(), (
        f"AC#2: expected log file at {log_path} after one call"
    )
    lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
    assert lines, "AC#2: log file is empty after a call"
    last = lines[-1]
    parsed = json.loads(last)  # MUST be valid JSON

    required_fields = {
        "timestamp",
        "hook_name",
        "tool_name",
        "block_reason",
        "recovery_hint",
        "session_id",
    }
    missing = required_fields - set(parsed.keys())
    assert not missing, f"AC#2: row missing required fields: {missing}"


# ---------------------------------------------------------------------------
# AC#3 — #937 race fix.
# ---------------------------------------------------------------------------


def _make_post_tool_use_payload(*, plan_text: str = "test plan body") -> str:
    return json.dumps(
        {
            "tool_name": "ExitPlanMode",
            "tool_response": {"plan": plan_text},
            "session_id": "spec-validator-970-ac3",
        }
    )


def _ensure_adev_marker(repo_dir: Path) -> None:
    """plan_mode_exit_detector requires _is_adev_project() in scope.

    The detector treats the cwd as an autonomous-dev project when a
    ``.claude/`` directory exists with project-level markers. We make the
    test cwd look like a project by creating ``.claude/`` and a sentinel
    PROJECT.md so the in-scope branch fires.
    """
    (repo_dir / ".claude").mkdir(parents=True, exist_ok=True)
    (repo_dir / ".claude" / "PROJECT.md").write_text("# Spec validator project\n")


def _run_plan_exit_detector(
    hooks_dir: Path,
    cwd: Path,
    payload: str,
    *,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_SESSION_ID"] = "spec-validator-970-ac3"
    env["AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT"] = "1"
    env.pop("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", None)
    env.pop("HOOK_RECOVERY_DISABLED", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(hooks_dir / "plan_mode_exit_detector.py")],
        input=payload,
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        timeout=15,
    )


def test_spec_970_ac3_race_proceed_verdict_advances_to_critique_done(
    hooks_dir, tmp_path
):
    """AC#3 happy path: PROCEED verdict + ExitPlanMode = critique_done + consumed."""
    _ensure_adev_marker(tmp_path)
    verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
    marker_path = tmp_path / ".claude" / "plan_mode_exit.json"

    # Seed PROCEED verdict (fresh ISO timestamp).
    from datetime import datetime, timezone
    verdict_path.write_text(
        json.dumps(
            {
                "verdict": "PROCEED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "score": 4.2,
            }
        )
    )

    proc = _run_plan_exit_detector(
        hooks_dir, tmp_path, _make_post_tool_use_payload()
    )
    assert proc.returncode == 0, (
        f"AC#3: hook crashed (rc={proc.returncode})\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}"
    )
    assert marker_path.exists(), "AC#3: plan_mode_exit.json marker not written"
    marker = json.loads(marker_path.read_text())
    assert marker.get("stage") == "critique_done", (
        f"AC#3: expected stage='critique_done', got {marker.get('stage')!r} "
        f"(full marker: {marker})"
    )
    assert not verdict_path.exists(), (
        "AC#3: verdict file should be CONSUMED (deleted) after critique_done"
    )


def test_spec_970_ac3_race_revise_verdict_does_not_advance(hooks_dir, tmp_path):
    """AC#3 negative: REVISE verdict → stage=plan_exited AND verdict kept."""
    _ensure_adev_marker(tmp_path)
    verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
    marker_path = tmp_path / ".claude" / "plan_mode_exit.json"

    from datetime import datetime, timezone
    verdict_path.write_text(
        json.dumps(
            {
                "verdict": "REVISE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "score": 1.9,
            }
        )
    )

    proc = _run_plan_exit_detector(
        hooks_dir, tmp_path, _make_post_tool_use_payload()
    )
    assert proc.returncode == 0, (
        f"AC#3-neg: hook crashed (rc={proc.returncode})\nSTDERR={proc.stderr}"
    )
    assert marker_path.exists(), "AC#3-neg: marker not written"
    marker = json.loads(marker_path.read_text())
    assert marker.get("stage") == "plan_exited", (
        f"AC#3-neg: expected stage='plan_exited', got {marker.get('stage')!r}"
    )
    assert verdict_path.exists(), (
        "AC#3-neg: REVISE verdict must NOT be consumed"
    )


# ---------------------------------------------------------------------------
# AC#4 — #941 fix: _is_pipeline_active does not refresh foreign mtime.
# ---------------------------------------------------------------------------


def test_spec_970_ac4_pipeline_active_only_refreshes_owning_session(
    hooks_dir, lib_dir, tmp_path, monkeypatch
):
    """Owning session refreshes mtime; foreign session does NOT."""
    # Make hook + lib dirs importable.
    for d in (hooks_dir, lib_dir):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))

    upt_path = hooks_dir / "unified_pre_tool.py"
    assert upt_path.exists()

    # Import unified_pre_tool under unique name (it has heavy side-effect-free
    # top-level definitions but defers fs work to function calls).
    upt = _import_module_from_file("upt_specvalid_970", upt_path)

    is_pipeline_active = getattr(upt, "_is_pipeline_active", None)
    assert callable(is_pipeline_active), (
        "AC#4: _is_pipeline_active must exist and be callable"
    )

    # Choose a pipeline agent name dynamically — the test must not hardcode it.
    pipeline_agents = getattr(upt, "PIPELINE_AGENTS", None)
    assert pipeline_agents, "AC#4: PIPELINE_AGENTS missing/empty"
    agent_name = pipeline_agents[0]

    # Use a tmp state file so we don't touch /tmp/implement_pipeline_state.json.
    state_file = tmp_path / "pipeline_state.json"
    monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_file))
    monkeypatch.setenv("CLAUDE_AGENT_NAME", agent_name)

    # ---- Owner refresh test (preserves #636) ----
    monkeypatch.setenv("CLAUDE_SESSION_ID", "session-A")
    state_file.write_text(json.dumps({"session_id": "session-A", "step": "STEP_1"}))
    # Backdate mtime by 5 seconds so refresh shows clearly.
    old_t = time.time() - 5
    os.utime(state_file, (old_t, old_t))
    mtime_before_owner = state_file.stat().st_mtime

    is_pipeline_active()
    mtime_after_owner = state_file.stat().st_mtime
    assert mtime_after_owner > mtime_before_owner, (
        "AC#4: owner-session call MUST refresh mtime (preserves #636). "
        f"before={mtime_before_owner}, after={mtime_after_owner}"
    )

    # ---- Foreign refresh test (the #941 fix) ----
    # Reset state file so it is OWNED by session-A.
    state_file.write_text(json.dumps({"session_id": "session-A", "step": "STEP_1"}))
    older_t = time.time() - 5
    os.utime(state_file, (older_t, older_t))
    mtime_before_foreign = state_file.stat().st_mtime

    # Now run as a DIFFERENT session.
    monkeypatch.setenv("CLAUDE_SESSION_ID", "session-B-foreign")
    is_pipeline_active()
    mtime_after_foreign = state_file.stat().st_mtime

    assert mtime_after_foreign == mtime_before_foreign, (
        "AC#4 (#941): foreign session MUST NOT refresh another session's mtime. "
        f"before={mtime_before_foreign}, after={mtime_after_foreign}"
    )


# ---------------------------------------------------------------------------
# AC#5 — audit script exit codes.
# ---------------------------------------------------------------------------


def test_spec_970_ac5_audit_script_warn_only_default(tmp_path):
    audit_script = REPO_ROOT / "scripts" / "audit_hook_recovery.py"
    assert audit_script.exists(), f"AC#5: missing {audit_script}"

    env = os.environ.copy()
    env.pop("AUDIT_HOOK_RECOVERY_STRICT", None)
    proc = subprocess.run(
        [sys.executable, str(audit_script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, (
        f"AC#5: WARN-ONLY default must exit 0, got rc={proc.returncode}\n"
        f"STDOUT={proc.stdout}\nSTDERR={proc.stderr}"
    )


def test_spec_970_ac5_audit_script_strict_mode_exit_code(tmp_path):
    audit_script = REPO_ROOT / "scripts" / "audit_hook_recovery.py"
    env = os.environ.copy()
    env["AUDIT_HOOK_RECOVERY_STRICT"] = "1"
    proc = subprocess.run(
        [sys.executable, str(audit_script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode in (0, 1), (
        f"AC#5: strict mode must exit 0 (clean) or 1 (violations), "
        f"got rc={proc.returncode}\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}"
    )


# ---------------------------------------------------------------------------
# AC#6 — exemption registry exists, parses, and malformed copy is safe.
# ---------------------------------------------------------------------------


def test_spec_970_ac6_exemption_registry_exists_and_parses():
    """Registry file must exist somewhere on the canonical paths and parse."""
    candidates = [
        REPO_ROOT / "plugins" / "autonomous-dev" / "config" / "hook_recovery_exemptions.json",
        REPO_ROOT / ".claude" / "config" / "hook_recovery_exemptions.json",
    ]
    found = [c for c in candidates if c.exists()]
    assert found, f"AC#6: registry file not found at any of {candidates}"
    for path in found:
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            pytest.fail(f"AC#6: registry at {path} does not parse: {e!r}")
        # AC#6 says "empty in Phase 1" — accept any dict; just confirm parseable.
        assert isinstance(data, (dict, list)), (
            f"AC#6: parsed registry should be JSON object/array, got {type(data).__name__}"
        )


def test_spec_970_ac6_can_user_recover_safe_on_malformed_registry(
    hook_recovery, tmp_path, monkeypatch
):
    """Even if the registry file is malformed JSON, can_user_recover MUST NOT raise."""
    # Build a malformed registry in a tmp dir and set cwd to it so the
    # cwd-relative fallback path resolves to it.
    monkeypatch.chdir(tmp_path)
    cfg_dir = tmp_path / ".claude" / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "hook_recovery_exemptions.json").write_text(
        '{"exemptions": [malformed,,,'  # invalid JSON
    )

    # Also try to redirect any module-level constants that point to a registry
    # path — we cannot rely on internals, so we just verify behavior is safe.
    try:
        result = hook_recovery.can_user_recover(
            hook_name="some_hook.py", block_reason="some reason"
        )
    except Exception as e:
        pytest.fail(f"AC#6: can_user_recover raised on malformed registry: {e!r}")
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# AC#7 — HOOK_RECOVERY_DISABLED=1 → no log growth.
# ---------------------------------------------------------------------------


def test_spec_970_ac7_disabled_env_var_no_ops_log_writes(
    hook_recovery, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / ".claude" / "logs" / "hook-recovery.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("")  # baseline

    monkeypatch.setenv("HOOK_RECOVERY_DISABLED", "1")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "spec-validator-ac7")

    size_before = log_path.stat().st_size
    hook_recovery.log_block_with_recovery(
        hook_name="unified_pre_tool.py",
        tool_name="Write",
        block_reason="should be no-op",
        recovery_hint="should be no-op",
    )
    size_after = log_path.stat().st_size
    assert size_after == size_before, (
        f"AC#7: HOOK_RECOVERY_DISABLED=1 should make telemetry no-op, "
        f"but log grew from {size_before} to {size_after} bytes."
    )


# ---------------------------------------------------------------------------
# AC#8 — at least 3 deny-paired log_block_with_recovery sites in unified_pre_tool.
# ---------------------------------------------------------------------------


def test_spec_970_ac8_minimum_three_log_block_with_recovery_sites(hooks_dir):
    upt = hooks_dir / "unified_pre_tool.py"
    assert upt.exists(), f"AC#8: {upt} missing"
    src = upt.read_text()
    # Count CALL sites (the trailing "(") rather than mere mentions.
    count = src.count("log_block_with_recovery(")
    # The import or function-def line itself uses the bare name without "(",
    # so this counter measures call sites + the def site if any. To be safe,
    # subtract any "def log_block_with_recovery(" lines.
    def_count = src.count("def log_block_with_recovery(")
    call_sites = count - def_count
    assert call_sites >= 3, (
        f"AC#8: expected >= 3 log_block_with_recovery() call sites in "
        f"unified_pre_tool.py (Phase 1 minimum). Found: {call_sites} "
        f"(raw matches={count}, defs={def_count})."
    )


# ---------------------------------------------------------------------------
# AC#9 — regression suite has at least one passing test per AC.
# ---------------------------------------------------------------------------


def test_spec_970_ac9_regression_suite_has_one_test_per_ac():
    regression_path = (
        REPO_ROOT / "tests" / "regression" / "test_issue_937_938_941_970.py"
    )
    assert regression_path.exists(), (
        f"AC#9: regression file missing: {regression_path}"
    )
    src = regression_path.read_text()

    # Count test functions (top-level and class methods).
    import re
    test_funcs = re.findall(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", src, re.MULTILINE)
    assert len(test_funcs) >= 9, (
        f"AC#9: regression suite must contain at least 9 tests "
        f"(one per AC#1-9). Found {len(test_funcs)}: {test_funcs}"
    )
