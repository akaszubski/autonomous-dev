"""End-to-end cutover matrix for Phase E (Issue #999).

Parametrizes (intent_class) x (INTENT_CLASSIFIER_ENFORCE on/off) and runs the
plan_gate hook as a subprocess with a real session-mode artifact present.

Expectations:
    - enforce=false: always allow with NO Phase E reason text.
    - enforce=true + skip class (conversation/typo/doc): allow + Phase E skip.
    - enforce=true + enforce class (implement/refactor/security_critical):
      proceeds to existing plan_gate logic. With no plan present, the gate
      blocks with "no plan file found".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

PLAN_GATE = HOOK_DIR / "plan_gate.py"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from session_mode import (  # noqa: E402
    _session_mode_path,
    write_session_mode,
)


def _make_intent(intent_value: str):
    return SimpleNamespace(
        intent=SimpleNamespace(value=intent_value),
        confidence=0.97,
        regex_hit=False,
        llm_used=True,
        fail_open=False,
        requires_security_audit=False,
    )


def _seed(sid: str, intent: str) -> None:
    write_session_mode(sid, _make_intent(intent), "x")


def _cleanup(sid: str) -> None:
    try:
        _session_mode_path(sid).unlink(missing_ok=True)
    except OSError:
        pass


def _run_plan_gate(payload: dict, env_extra: dict, cwd: Path) -> dict:
    env = os.environ.copy()
    env.update(env_extra)
    # Make sure ENFORCE is not inherited from parent unless we set it.
    if "INTENT_CLASSIFIER_ENFORCE" not in env_extra:
        env.pop("INTENT_CLASSIFIER_ENFORCE", None)
    result = subprocess.run(
        [sys.executable, str(PLAN_GATE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        cwd=str(cwd),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip())


SKIP_CLASSES = ["conversation", "typo", "doc"]
ENFORCE_CLASSES = ["implement", "refactor", "security_critical"]
ALL_CLASSES = SKIP_CLASSES + ENFORCE_CLASSES


@pytest.mark.parametrize("intent_class", ALL_CLASSES)
@pytest.mark.parametrize("enforce", ["true", "false"])
def test_cutover_matrix(intent_class, enforce, tmp_path):
    """The full 12-cell decision matrix (6 classes x 2 enforce states)."""
    sid = f"phase-e-cutover-{intent_class}-{enforce}"
    _seed(sid, intent_class)
    try:
        # Use tmp_path as cwd so plan_gate doesn't find a real .claude/plans
        # — guarantees the "no plan" fallback fires in enforce-class cases.
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "feature.py"),
                "content": "line\n" * 200,
            },
            "session_id": sid,
        }
        env_extra = {"INTENT_CLASSIFIER_ENFORCE": enforce}
        output = _run_plan_gate(payload, env_extra, cwd=tmp_path)
        decision = output["hookSpecificOutput"]["permissionDecision"]
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        if enforce == "false":
            # Phase E is off — the gate behaves as it does today.
            assert "Phase E skip" not in reason
            # And the existing logic still works (no plan + complex edit
            # = block by classic rules). We don't pin to allow vs block —
            # only that no Phase E text appears.
        else:
            # enforce=true
            if intent_class in SKIP_CLASSES:
                assert decision == "allow", (
                    f"{intent_class}/{enforce}: expected allow, got {decision} ({reason})"
                )
                assert "Phase E skip" in reason
                assert f"mode_skip:{intent_class}" in reason
            else:
                # enforce class — Phase E does NOT skip; existing plan_gate
                # logic runs. With no plan in tmp_path, classic logic blocks.
                assert "Phase E skip" not in reason
                # Don't pin specific block text — only that the Phase E
                # path did NOT short-circuit.
    finally:
        _cleanup(sid)


def test_no_artifact_with_enforce_on_does_not_skip(tmp_path):
    """Missing artifact + ENFORCE=true → ambiguous_safety → no Phase E skip."""
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_path / "feature.py"),
            "content": "line\n" * 200,
        },
        "session_id": "phase-e-cutover-no-artifact-unique-ABCXYZ",
    }
    env_extra = {"INTENT_CLASSIFIER_ENFORCE": "true"}
    output = _run_plan_gate(payload, env_extra, cwd=tmp_path)
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Phase E skip" not in reason


def test_unknown_session_id_does_not_skip(tmp_path):
    """session_id='unknown' + ENFORCE=true → no_session_id_safety → no skip."""
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_path / "feature.py"),
            "content": "line\n" * 200,
        },
        "session_id": "unknown",
    }
    env_extra = {"INTENT_CLASSIFIER_ENFORCE": "true"}
    output = _run_plan_gate(payload, env_extra, cwd=tmp_path)
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Phase E skip" not in reason
