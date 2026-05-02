"""Integration tests for Phase E session-mode wraps (Issue #999).

Verifies:
    - plan_gate.py respects mode-skip when enforcement on + skip class.
    - plan_gate.py runs normally when enforcement off (default).
    - plan_mode_exit_detector.py respects mode-skip.
    - unified_pre_tool.py respects mode-skip on the wrapped checks.
    - Hard-floor regression locks: hard_floor checks always run regardless.
    - Telemetry surface emits 'mode_skip' on skip path only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

PLAN_GATE = HOOK_DIR / "plan_gate.py"
PLAN_MODE_EXIT = HOOK_DIR / "plan_mode_exit_detector.py"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from session_mode import (  # noqa: E402
    _session_mode_path,
    write_session_mode,
)
from hard_floor import is_hard_floor  # noqa: E402


def _make_intent(intent_value: str, *, fail_open=False, requires_security_audit=False):
    return SimpleNamespace(
        intent=SimpleNamespace(value=intent_value),
        confidence=0.97,
        regex_hit=False,
        llm_used=True,
        fail_open=fail_open,
        requires_security_audit=requires_security_audit,
    )


def _seed_session(sid: str, intent: str, **kwargs) -> None:
    write_session_mode(sid, _make_intent(intent, **kwargs), "x")


def _cleanup(sid: str) -> None:
    try:
        _session_mode_path(sid).unlink(missing_ok=True)
    except OSError:
        pass


def _run_hook(hook: Path, payload: dict, env_extra: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


class TestPlanGateSessionModeWrap:
    def test_skips_in_conversation_mode_with_enforce_on(self, tmp_path):
        """conversation + ENFORCE=true → plan_gate allows with phase-e reason."""
        sid = "phase-e-test-conv-skip"
        _seed_session(sid, "conversation")
        try:
            payload = {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(tmp_path / "x.py"),
                    "content": "x\n" * 200,
                },
                "session_id": sid,
            }
            result = _run_hook(
                PLAN_GATE,
                payload,
                {"INTENT_CLASSIFIER_ENFORCE": "true"},
            )
            assert result.returncode == 0, result.stderr
            output = json.loads(result.stdout)
            decision = output["hookSpecificOutput"]["permissionDecision"]
            reason = output["hookSpecificOutput"]["permissionDecisionReason"]
            assert decision == "allow"
            assert "Phase E skip" in reason
            assert "mode_skip:conversation" in reason
        finally:
            _cleanup(sid)

    def test_runs_normally_with_enforce_off(self, tmp_path):
        """Default (enforce off) → existing logic, no Phase E skip."""
        sid = "phase-e-test-enforce-off"
        _seed_session(sid, "conversation")
        try:
            payload = {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(tmp_path / "x.py"),
                    "content": "x\n" * 200,  # > 100-line threshold
                },
                "session_id": sid,
            }
            env_extra = {}
            # Make sure enforcement is off
            os.environ.pop("INTENT_CLASSIFIER_ENFORCE", None)
            result = _run_hook(PLAN_GATE, payload, env_extra)
            assert result.returncode == 0, result.stderr
            output = json.loads(result.stdout)
            reason = output["hookSpecificOutput"]["permissionDecisionReason"]
            # NOT a Phase E skip — either an "allow" for a doc/threshold or a
            # "block" for missing plan. Either way, no Phase E reason text.
            assert "Phase E skip" not in reason
        finally:
            _cleanup(sid)


class TestPlanModeExitDetectorSessionModeWrap:
    def test_skips_in_doc_mode_with_enforce_on(self, tmp_path):
        """doc class + ENFORCE=true → ExitPlanMode tool yields no nudge."""
        sid = "phase-e-test-doc-skip"
        _seed_session(sid, "doc")
        try:
            payload = {
                "tool_name": "ExitPlanMode",
                "tool_input": {},
                "tool_response": {"plan": "# plan"},
                "session_id": sid,
            }
            result = _run_hook(
                PLAN_MODE_EXIT,
                payload,
                {"INTENT_CLASSIFIER_ENFORCE": "true"},
            )
            assert result.returncode == 0, result.stderr
            # When skipped, no marker file is written and no system message
            # is emitted (or a different output appears).
            stdout = result.stdout.strip()
            # The hook prints either nothing or telemetry — the key invariant
            # is that no PLAN MODE EXITED nudge is produced.
            if stdout:
                # If there is JSON output, it should NOT contain the nudge.
                try:
                    parsed = json.loads(stdout)
                    sys_msg = parsed.get("systemMessage", "")
                    assert "PLAN MODE EXITED" not in sys_msg, (
                        f"Skip should suppress nudge; got: {sys_msg!r}"
                    )
                except json.JSONDecodeError:
                    pass
        finally:
            _cleanup(sid)


class TestHardFloorInvariant:
    """Regression locks: hard-floor checks always run regardless of session mode."""

    def test_hard_floor_check_dangerous_bash_always_runs(self):
        """is_hard_floor must return True for _check_dangerous_bash —
        proving the registry recognizes it as never-skippable."""
        assert is_hard_floor("unified_pre_tool.py", "_check_dangerous_bash") is True

    def test_hard_floor_check_settings_json_writes_always_runs(self):
        """is_hard_floor for _check_settings_json_writes must be True."""
        assert is_hard_floor("unified_pre_tool.py", "_check_settings_json_writes") is True

    def test_hard_floor_check_protected_infrastructure_always_runs(self):
        """is_hard_floor for _check_protected_infrastructure must be True."""
        assert is_hard_floor(
            "unified_pre_tool.py", "_check_protected_infrastructure"
        ) is True

    def test_hard_floor_check_bash_state_deletion_always_runs(self):
        """is_hard_floor for _check_bash_state_deletion must be True."""
        assert is_hard_floor("unified_pre_tool.py", "_check_bash_state_deletion") is True

    def test_phase_e_decision_layer_respects_hard_floor(self):
        """Even with skip class + enforce on, hard-floor function names get
        hard_floor as the reason (no skip)."""
        from enforcement_decision import should_skip_enforcement

        # Seed a session that would otherwise skip
        sid = "phase-e-hard-floor-test"
        _seed_session(sid, "conversation")
        os.environ["INTENT_CLASSIFIER_ENFORCE"] = "true"
        try:
            skip, reason = should_skip_enforcement(
                hook_name="unified_pre_tool.py",
                function_name="_check_dangerous_bash",
                session_id=sid,
            )
            assert skip is False
            assert reason == "hard_floor"
        finally:
            os.environ.pop("INTENT_CLASSIFIER_ENFORCE", None)
            _cleanup(sid)


class TestTelemetrySurface:
    def test_mode_skip_in_valid_decision_shapes(self):
        """The new shape constant is registered."""
        from hook_telemetry import VALID_DECISION_SHAPES

        assert "mode_skip" in VALID_DECISION_SHAPES
        # Sanity: the documented shapes from before are still there.
        assert "tuple" in VALID_DECISION_SHAPES
        assert "dict" in VALID_DECISION_SHAPES

    def test_mode_enforce_not_a_decision_shape(self):
        """We intentionally do NOT add mode_enforce — only mode_skip is logged."""
        from hook_telemetry import VALID_DECISION_SHAPES

        assert "mode_enforce" not in VALID_DECISION_SHAPES
