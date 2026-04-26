"""Regression tests for Issues #937, #938, #941, #970.

Acceptance criteria coverage:

- AC#3 (#937, #970): pre-existing PROCEED verdict at ExitPlanMode time → marker
  is born ``stage="critique_done"``, verdict file is consumed, subsequent
  /implement is allowed.
- AC#4 (#941): ``_is_pipeline_active()`` only refreshes mtime when the state
  file's ``session_id`` matches ``CLAUDE_SESSION_ID``. #636 (owning session)
  is preserved.
- AC#5: audit script default mode is WARN-ONLY (exit 0).
- AC#7: ``HOOK_RECOVERY_DISABLED=1`` env var makes telemetry a no-op.

These are end-to-end style tests that drive the real hook entry points via
subprocess to ensure the full I/O contract is preserved.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


def _load_pmed():
    """Load plan_mode_exit_detector as a module for in-process testing."""
    path = HOOKS_DIR / "plan_mode_exit_detector.py"
    spec = importlib.util.spec_from_file_location("plan_mode_exit_detector", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["plan_mode_exit_detector"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_pmed_subprocess(stdin_payload: str, cwd: Path, env: dict | None = None):
    """Invoke plan_mode_exit_detector.py as a real subprocess from ``cwd``."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Force scope ON so the hook actually executes its main path even when
    # cwd is a tmp_path that is not auto-detected as autonomous-dev.
    full_env.setdefault("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / "plan_mode_exit_detector.py")],
        input=stdin_payload,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd),
        env=full_env,
    )


def _make_proceed_verdict(cwd: Path, *, freshness_seconds: int = 0) -> Path:
    """Write a PROCEED verdict file at the conventional location."""
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = claude_dir / "plan_critic_verdict.json"
    ts = datetime.now(timezone.utc).timestamp() - freshness_seconds
    verdict_path.write_text(
        json.dumps(
            {
                "verdict": "PROCEED",
                "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                "round": 1,
            }
        )
    )
    return verdict_path


def _make_revise_verdict(cwd: Path) -> Path:
    """Write a REVISE verdict file (must NOT advance the gate)."""
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = claude_dir / "plan_critic_verdict.json"
    verdict_path.write_text(
        json.dumps(
            {
                "verdict": "REVISE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "round": 1,
            }
        )
    )
    return verdict_path


def _exit_plan_mode_stdin(plan_text: str = "Sample plan body") -> str:
    """Construct the stdin payload Claude Code sends when ExitPlanMode fires."""
    return json.dumps(
        {
            "tool_name": "ExitPlanMode",
            "tool_response": {"plan": plan_text},
        }
    )


# ---------------------------------------------------------------------------
# AC#3 (#937): pre-existing PROCEED verdict at ExitPlanMode time
# ---------------------------------------------------------------------------


class TestSubagentStopBeforeExitPlanMode:
    def test_subagentstop_before_exitplanmode_writes_critique_done(
        self, tmp_path
    ):
        """AC#3 primary regression: PROCEED verdict written BEFORE ExitPlanMode
        fires must result in marker stage='critique_done'."""
        _make_proceed_verdict(tmp_path)
        result = _run_pmed_subprocess(_exit_plan_mode_stdin(), tmp_path)
        assert result.returncode == 0, f"hook crashed: {result.stderr}"
        marker = tmp_path / ".claude" / "plan_mode_exit.json"
        assert marker.exists(), "marker file was not written"
        data = json.loads(marker.read_text())
        assert data["stage"] == "critique_done", (
            f"AC#3 FAIL: expected stage=critique_done when PROCEED verdict "
            f"existed before ExitPlanMode, got {data}"
        )
        assert "critique_completed_at" in data
        # Verdict file must be consumed.
        assert not (tmp_path / ".claude" / "plan_critic_verdict.json").exists(), (
            "verdict file was not consumed after stage advance"
        )

    def test_normal_order_exitplanmode_then_critic_still_works(self, tmp_path):
        """No verdict yet → marker stays plan_exited so plan-critic still runs."""
        result = _run_pmed_subprocess(_exit_plan_mode_stdin(), tmp_path)
        assert result.returncode == 0
        marker = tmp_path / ".claude" / "plan_mode_exit.json"
        assert marker.exists()
        data = json.loads(marker.read_text())
        assert data["stage"] == "plan_exited"

    def test_no_verdict_file_writes_plan_exited(self, tmp_path):
        """Existing behavior preserved when no verdict file is present."""
        # No verdict file at all.
        result = _run_pmed_subprocess(_exit_plan_mode_stdin(), tmp_path)
        assert result.returncode == 0
        data = json.loads((tmp_path / ".claude" / "plan_mode_exit.json").read_text())
        assert data["stage"] == "plan_exited"

    def test_revise_verdict_does_not_advance(self, tmp_path):
        """REVISE verdict must NOT advance — gate stays closed."""
        _make_revise_verdict(tmp_path)
        result = _run_pmed_subprocess(_exit_plan_mode_stdin(), tmp_path)
        assert result.returncode == 0
        data = json.loads((tmp_path / ".claude" / "plan_mode_exit.json").read_text())
        assert data["stage"] == "plan_exited", (
            "REVISE verdict must not advance the gate"
        )
        # REVISE verdict file must be retained for the next round.
        assert (tmp_path / ".claude" / "plan_critic_verdict.json").exists()


# ---------------------------------------------------------------------------
# AC#4 (#941): conditional touch of pipeline state file
# ---------------------------------------------------------------------------


def _load_unified_pre_tool():
    """Load unified_pre_tool as a module for direct function testing."""
    path = HOOKS_DIR / "unified_pre_tool.py"
    spec = importlib.util.spec_from_file_location("unified_pre_tool_test_load", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["unified_pre_tool_test_load"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestPipelineActiveTouch:
    def test_concurrent_session_does_not_refresh_owners_mtime(
        self, tmp_path, monkeypatch
    ):
        """AC#4 (#941): when CLAUDE_SESSION_ID does not match state's
        session_id, ``_is_pipeline_active`` MUST NOT touch the file."""
        state_file = tmp_path / "implement_pipeline_state.json"
        # Owning session is "OWNER-A".
        state_file.write_text(json.dumps({"session_id": "OWNER-A"}))
        original_mtime = state_file.stat().st_mtime
        # Force the mtime back into the past so we can detect a change.
        old_time = original_mtime - 3600
        os.utime(state_file, (old_time, old_time))

        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_file))
        # Concurrent session is "OWNER-B".
        monkeypatch.setenv("CLAUDE_SESSION_ID", "OWNER-B")
        # Pipeline-agent name forces the touch branch.
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")

        upt = _load_unified_pre_tool()
        # Reset module-level _agent_type so _get_active_agent_name uses env var.
        upt._agent_type = ""
        upt._is_pipeline_active()

        # mtime MUST be unchanged.
        new_mtime = state_file.stat().st_mtime
        assert new_mtime == old_time, (
            f"AC#4 FAIL: foreign-owned state file was refreshed "
            f"(old={old_time}, new={new_mtime})"
        )

    def test_owner_session_still_refreshes_mtime(self, tmp_path, monkeypatch):
        """AC#4 inverse: owning session keeps mtime fresh (#636 preserved)."""
        state_file = tmp_path / "implement_pipeline_state.json"
        state_file.write_text(json.dumps({"session_id": "MY-SESSION"}))
        old_time = state_file.stat().st_mtime - 3600
        os.utime(state_file, (old_time, old_time))

        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_file))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "MY-SESSION")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")

        upt = _load_unified_pre_tool()
        upt._agent_type = ""
        upt._is_pipeline_active()

        new_mtime = state_file.stat().st_mtime
        assert new_mtime > old_time, (
            f"#636 REGRESSION: owner session did not refresh mtime "
            f"(old={old_time}, new={new_mtime})"
        )


# ---------------------------------------------------------------------------
# AC#5: audit script WARN-ONLY default
# ---------------------------------------------------------------------------


class TestAuditWarnOnlyDefault:
    def test_audit_warn_only_default(self):
        """AC#5: audit script default mode exits 0 (WARN-ONLY for Phase 1)."""
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "audit_hook_recovery.py")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# AC#7: HOOK_RECOVERY_DISABLED rollback switch
# ---------------------------------------------------------------------------


class TestRecoveryDisabled:
    def test_recovery_disabled_env_var_makes_telemetry_noop(
        self, tmp_path, monkeypatch
    ):
        """AC#7: when HOOK_RECOVERY_DISABLED=1, log_block_with_recovery and
        clear_stale_state become no-ops."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOOK_RECOVERY_DISABLED", "1")

        import importlib
        # Force a fresh import to pick up env var.
        if "hook_recovery" in sys.modules:
            importlib.reload(sys.modules["hook_recovery"])
        else:
            import hook_recovery  # noqa: F401

        import hook_recovery as hr
        hr.log_block_with_recovery(
            hook_name="any.py",
            tool_name="Bash",
            block_reason="reason",
            recovery_hint="hint",
        )
        log_path = tmp_path / hr.LOG_FILE_RELATIVE
        assert not log_path.exists(), "recovery log should not be written when disabled"

        state = tmp_path / "state.json"
        state.write_text(json.dumps({"session_id": "OWNER-OLD"}))
        removed = hr.clear_stale_state(state, owning_session_id="CURRENT-NEW")
        assert removed is False
        assert state.exists()


# ---------------------------------------------------------------------------
# AC#1 + AC#2: hook_recovery module public API + JSONL telemetry shape
# ---------------------------------------------------------------------------


class TestHookRecoveryModuleApiAndTelemetryShape:
    def test_hook_recovery_module_api_and_telemetry_shape(
        self, tmp_path, monkeypatch
    ):
        """AC#1 + AC#2: Module exports 4 public callables; telemetry JSONL is well-formed.

        AC#1: hook_recovery exports can_user_recover, log_block_with_recovery,
        clear_stale_state, is_recovery_disabled — all callable, none raise on
        introspection.

        AC#2: log_block_with_recovery writes a JSONL row to
        .claude/logs/hook-recovery.jsonl containing the six required fields:
        timestamp, hook_name, tool_name, block_reason, recovery_hint, session_id.
        """
        # --- AC#1: import module from the in-repo plugins lib path. ----------
        # LIB_DIR is already on sys.path at module import time, but we reload
        # to ensure a clean module state (other tests may have set
        # HOOK_RECOVERY_DISABLED in env and cached the result).
        import importlib

        monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)
        if "hook_recovery" in sys.modules:
            hr = importlib.reload(sys.modules["hook_recovery"])
        else:
            import hook_recovery as hr  # type: ignore

        required_exports = (
            "can_user_recover",
            "log_block_with_recovery",
            "clear_stale_state",
            "is_recovery_disabled",
        )
        for name in required_exports:
            assert hasattr(hr, name), (
                f"AC#1 FAIL: hook_recovery is missing public export {name!r}"
            )
            assert callable(getattr(hr, name)), (
                f"AC#1 FAIL: hook_recovery.{name} is not callable"
            )

        # Smoke: introspection-only calls must not raise.
        assert hr.is_recovery_disabled() is False
        assert hr.can_user_recover(
            hook_name="nonexistent.py", block_reason="never matches"
        ) is False

        # --- AC#2: write a telemetry row and validate its shape. -------------
        monkeypatch.chdir(tmp_path)

        hr.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="dangerous rm -rf detected",
            recovery_hint="re-run with explicit --force flag",
            session_id="TEST-SESSION-AC2",
        )

        log_path = tmp_path / hr.LOG_FILE_RELATIVE
        assert log_path.exists(), (
            f"AC#2 FAIL: telemetry log not created at {log_path}"
        )

        lines = [
            ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        assert len(lines) == 1, (
            f"AC#2 FAIL: expected exactly 1 JSONL row, got {len(lines)}"
        )

        try:
            row = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"AC#2 FAIL: telemetry row is not valid JSON: {lines[0]!r} ({exc})"
            )

        required_fields = {
            "timestamp",
            "hook_name",
            "tool_name",
            "block_reason",
            "recovery_hint",
            "session_id",
        }
        missing = required_fields - set(row.keys())
        assert not missing, (
            f"AC#2 FAIL: telemetry row missing required fields {missing}; "
            f"got keys {sorted(row.keys())}"
        )

        # Field-value sanity (echoes what we passed in).
        assert row["hook_name"] == "unified_pre_tool.py"
        assert row["tool_name"] == "Bash"
        assert row["block_reason"] == "dangerous rm -rf detected"
        assert row["recovery_hint"] == "re-run with explicit --force flag"
        assert row["session_id"] == "TEST-SESSION-AC2"
        # timestamp must be an ISO-8601 string parseable by datetime.
        ts = row["timestamp"]
        assert isinstance(ts, str) and len(ts) > 0
        # fromisoformat handles the timezone-aware ISO string we emit.
        datetime.fromisoformat(ts)
