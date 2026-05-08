"""End-to-end integration: AMBIGUOUS round-trip flips the enforcement gate.

Issue #1024 (M2). Exercises the complete chain:

    1. Write an AMBIGUOUS session-mode artifact (simulates the
       UserPromptSubmit hook having classified the prompt as AMBIGUOUS).
    2. Invoke ``persist_intent_answer.py --session-id ... --intent
       implement`` (simulates Claude calling AskUserQuestion and
       persisting the user's answer).
    3. Assert ``should_skip_enforcement`` returns the clarified verdict
       — not the AMBIGUOUS-pessimism verdict it would have returned
       without the clarification.

The script is invoked via subprocess (the way Claude actually calls it)
to give us coverage of:

    - argparse argument validation
    - sys.path setup for ``session_mode`` import
    - exit codes (0 success, 1 validation failure, 0 silent fail-open)

The artifact lives at ``/tmp/session_mode_*.json`` — same path the hook
writes — so we use unique session ids per test and clean up in finally
blocks. NEVER reuse session ids across tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Add lib to sys.path so we can read/write the artifact directly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_SCRIPT_PATH = (
    _REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "scripts"
    / "persist_intent_answer.py"
)

if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

from enforcement_decision import should_skip_enforcement  # noqa: E402
from session_mode import (  # noqa: E402
    _session_mode_path,
    read_session_mode,
    write_session_mode,
)


def _ambiguous_intent_result() -> SimpleNamespace:
    """Build a duck-typed IntentResult mirroring the AMBIGUOUS fail-open path."""
    return SimpleNamespace(
        intent=SimpleNamespace(value="ambiguous"),
        confidence=0.4,
        regex_hit=False,
        llm_used=True,
        fail_open=True,
        requires_security_audit=True,
    )


def _cleanup(session_id: str) -> None:
    try:
        _session_mode_path(session_id).unlink(missing_ok=True)
    except OSError:
        pass


def _run_persist(session_id: str, intent: str) -> subprocess.CompletedProcess:
    """Invoke persist_intent_answer.py with the given args."""
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--session-id",
            session_id,
            "--intent",
            intent,
        ],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class TestAmbiguousRoundTrip:
    """Full chain: AMBIGUOUS → persist → enforcement_decision."""

    def test_full_round_trip_ambiguous_to_implement_flips_gate(
        self, monkeypatch
    ) -> None:
        """AMBIGUOUS artifact + clarified=implement → clarified_enforce:implement.

        Without the clarification, the AMBIGUOUS artifact has fail_open=True
        and requires_security_audit=True, so the gate would short-circuit
        to "classifier_fail_open" or "security_audit_required". The user's
        clarification flips that to "clarified_enforce:implement".
        """
        sid = "integration-ambig-implement"
        _cleanup(sid)
        try:
            # Step 1: write the AMBIGUOUS artifact.
            write_session_mode(sid, _ambiguous_intent_result(), "vague prompt")

            # Sanity: confirm baseline behavior (no clarification yet).
            monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
            skip_before, reason_before = should_skip_enforcement(
                hook_name="plan_gate.py", session_id=sid
            )
            assert skip_before is False
            assert reason_before == "classifier_fail_open", (
                f"baseline should be fail_open, got {reason_before!r}"
            )

            # Step 2: persist the user's answer via the CLI.
            proc = _run_persist(sid, "implement")
            assert proc.returncode == 0, (
                f"persist returned {proc.returncode}\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )

            # Step 3: gate now honors the user's clarification.
            skip_after, reason_after = should_skip_enforcement(
                hook_name="plan_gate.py", session_id=sid
            )
            assert skip_after is False
            assert reason_after == "clarified_enforce:implement", (
                f"after clarification, expected "
                f"'clarified_enforce:implement', got {reason_after!r}"
            )

            # And the artifact reflects the round-trip.
            mode = read_session_mode(sid)
            assert mode is not None
            assert mode["clarified_intent"] == "implement"
            assert mode["clarification_asked"] is True
        finally:
            _cleanup(sid)

    def test_round_trip_to_doc_skips_pipeline(self, monkeypatch) -> None:
        """Clarified=doc → clarified_skip:doc, the enforcement gate skips."""
        sid = "integration-ambig-doc"
        _cleanup(sid)
        try:
            write_session_mode(sid, _ambiguous_intent_result(), "doc question")
            monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")

            proc = _run_persist(sid, "doc")
            assert proc.returncode == 0

            skip, reason = should_skip_enforcement(
                hook_name="plan_gate.py", session_id=sid
            )
            assert skip is True
            assert reason == "clarified_skip:doc"
        finally:
            _cleanup(sid)

    def test_round_trip_rejects_security_critical_intent(self) -> None:
        """--intent security_critical exits 1 and does NOT mutate the artifact."""
        sid = "integration-ambig-sec"
        _cleanup(sid)
        try:
            write_session_mode(sid, _ambiguous_intent_result(), "x")
            mode_before = read_session_mode(sid)
            assert mode_before is not None
            assert mode_before["clarified_intent"] is None

            proc = _run_persist(sid, "security_critical")
            assert proc.returncode == 1, (
                f"persist should reject security_critical with exit 1, "
                f"got {proc.returncode}\nstderr: {proc.stderr}"
            )
            assert "not user-selectable" in proc.stderr.lower()

            # Artifact is unchanged.
            mode_after = read_session_mode(sid)
            assert mode_after is not None
            assert mode_after["clarified_intent"] is None
            assert mode_after["clarification_asked"] is False
        finally:
            _cleanup(sid)

    def test_round_trip_rejects_ambiguous_intent(self) -> None:
        """--intent ambiguous is rejected — that's the state being resolved."""
        sid = "integration-ambig-ambig"
        _cleanup(sid)
        try:
            write_session_mode(sid, _ambiguous_intent_result(), "x")
            proc = _run_persist(sid, "ambiguous")
            assert proc.returncode == 1, (
                f"persist should reject ambiguous, got {proc.returncode}"
            )
            mode = read_session_mode(sid)
            assert mode is not None
            assert mode["clarified_intent"] is None
        finally:
            _cleanup(sid)

    def test_round_trip_rejects_unknown_intent(self) -> None:
        """Unknown intent values are rejected with exit 1."""
        sid = "integration-ambig-unknown"
        _cleanup(sid)
        try:
            write_session_mode(sid, _ambiguous_intent_result(), "x")
            proc = _run_persist(sid, "totally_made_up_intent")
            assert proc.returncode == 1
            assert "not in the allowed set" in proc.stderr.lower()
        finally:
            _cleanup(sid)

    def test_round_trip_no_op_when_artifact_missing(self) -> None:
        """Missing artifact ⇒ silent fail-open (exit 0, no file created)."""
        sid = "integration-ambig-missing"
        _cleanup(sid)
        # Confirm no artifact pre-exists.
        assert not _session_mode_path(sid).exists()

        proc = _run_persist(sid, "implement")
        assert proc.returncode == 0, (
            f"silent fail-open should exit 0, got {proc.returncode}\n"
            f"stderr: {proc.stderr}"
        )
        # No file lazily created.
        assert not _session_mode_path(sid).exists()
