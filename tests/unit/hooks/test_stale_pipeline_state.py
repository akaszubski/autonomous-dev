"""Tests for stale pipeline session detection (Issue #592).

Validates that _is_stale_session() correctly detects and removes pipeline state
files from previous sessions, preventing stale state from blocking Bash writes
in new sessions.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add lib to path for pipeline_state imports
LIB_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "lib"
)
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

# Import the hook module
HOOK_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "hooks"
)
if HOOK_DIR not in sys.path:
    sys.path.insert(0, HOOK_DIR)

import unified_pre_tool

from tests.helpers.state_isolation import redirect_pipeline_state  # noqa: E402
from tests.helpers.sanctioned_run import (  # noqa: E402
    clear_run_artifacts,
    sanctioned_state,
)


@pytest.fixture(autouse=True)
def _isolate_run_artifacts(monkeypatch, tmp_path):
    """Redirect sentinel, secret store and completion ledger into tmp_path.

    Issue #1807: building a sanctioned run writes a key under ``$HOME`` and a
    ledger under ``/tmp``. ``redirect_pipeline_state`` is the ONE canonical
    redirect for all of it, and ``sanctioned_run`` REFUSES to build without it.
    """
    import pipeline_completion_state as _pcs
    import pipeline_state as _ps

    redirect_pipeline_state(monkeypatch, tmp_path, _ps, _pcs, unified_pre_tool)


def _write_state_file(path: Path, state: dict) -> None:
    """Helper to write a pipeline state JSON file."""
    path.write_text(json.dumps(state))


#: Every session id this module builds a sanctioned run for, so the /tmp ledger
#: receipts can be reaped. /tmp is NOT cleared between pytest invocations
#: (Issue #1184).
_SANCTIONED_SESSIONS = ("session-A", "session-B", "old-session", "current-session")


@pytest.fixture(autouse=True)
def _reap_run_receipts():
    """Remove run-start receipts this module writes, before and after each test."""
    for session_id in _SANCTIONED_SESSIONS:
        clear_run_artifacts(session_id)
    yield
    for session_id in _SANCTIONED_SESSIONS:
        clear_run_artifacts(session_id)


def _make_unsigned_state(session_id: str) -> dict:
    """Build an UNSIGNED state whose owner may be indeterminate.

    Issue #1807: ``sanctioned_state`` refuses a blank/"unknown" owner by design,
    but ``_is_stale_session`` must still be exercised with those spellings —
    that comparison runs BEFORE any authority question and is what these arms
    measure.
    """
    return {
        "session_start": datetime.now().isoformat(),
        "mode": "full",
        "run_id": "test-run",
        "explicitly_invoked": True,
        "session_id": session_id,
    }


def _make_valid_state(session_id: str = "session-A") -> dict:
    """Create a valid pipeline state dict with a recent timestamp.

    Issue #1807: "valid" now means SANCTIONED — owner bound into the MAC and a
    run-start receipt recorded. The pre-#1807 version returned a bare unsigned
    dict, which ``_is_pipeline_active()`` accepted; that shape is exactly the
    forgery the authority classifier now refuses, so a fixture using it would
    have measured the refusal rather than the staleness logic under test.
    """
    return sanctioned_state(
        session_id,
        "test-run",
        session_start=datetime.now().isoformat(),
        mode="full",
        explicitly_invoked=True,
    )


class TestIsStaleSession:
    """Unit tests for _is_stale_session()."""

    def test_stale_session_different_id_returns_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stored 'session-A', current 'session-B' -> True, file removed."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("session-A")
        _write_state_file(state_path, state)

        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-B")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is True
        assert not state_path.exists()

    def test_same_session_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stored 'session-A', current 'session-A' -> False, file kept."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("session-A")
        _write_state_file(state_path, state)

        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-A")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is False
        assert state_path.exists()

    def test_missing_stored_session_id_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No session_id field in state -> False (backward compat)."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state()
        del state["session_id"]
        _write_state_file(state_path, state)

        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-B")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is False

    def test_unknown_stored_session_id_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stored 'unknown' -> False."""
        state_path = tmp_path / "state.json"
        state = _make_unsigned_state("unknown")
        _write_state_file(state_path, state)

        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-B")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is False

    def test_unknown_current_session_id_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Current 'unknown' -> False."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("session-A")
        _write_state_file(state_path, state)

        monkeypatch.setenv("CLAUDE_SESSION_ID", "unknown")
        monkeypatch.setattr(unified_pre_tool, "_session_id", "unknown")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is False

    def test_empty_stored_session_id_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stored '' -> False."""
        state_path = tmp_path / "state.json"
        state = _make_unsigned_state("")
        _write_state_file(state_path, state)

        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-B")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is False

    def test_empty_current_session_id_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Current '' (no env var, _session_id empty) -> False."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("session-A")
        _write_state_file(state_path, state)

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.setattr(unified_pre_tool, "_session_id", "")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is False

    def test_stale_detection_removes_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify file is actually deleted when stale."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("old-session")
        _write_state_file(state_path, state)
        assert state_path.exists()

        monkeypatch.setenv("CLAUDE_SESSION_ID", "new-session")

        unified_pre_tool._is_stale_session(state, state_path)

        assert not state_path.exists()

    def test_file_removal_failure_still_returns_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """OSError on unlink -> still returns True (stale detected)."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("old-session")
        _write_state_file(state_path, state)

        monkeypatch.setenv("CLAUDE_SESSION_ID", "new-session")

        # Make unlink raise OSError
        def broken_unlink(self, *args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "unlink", broken_unlink)

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is True

    def test_no_env_var_falls_back_to_session_id_attr(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When CLAUDE_SESSION_ID env var is absent, uses _session_id module attr."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("old-session")
        _write_state_file(state_path, state)

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.setattr(unified_pre_tool, "_session_id", "new-session")

        result = unified_pre_tool._is_stale_session(state, state_path)

        assert result is True
        assert not state_path.exists()


class TestPipelineActiveWithStaleness:
    """Integration tests: _is_pipeline_active() with stale session detection."""

    def test_pipeline_active_returns_false_on_stale(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_is_pipeline_active() returns False when session_id differs."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("old-session")
        _write_state_file(state_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "new-session")
        # Ensure agent name does not short-circuit
        monkeypatch.setattr(unified_pre_tool, "_agent_type", "")
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)

        result = unified_pre_tool._is_pipeline_active()

        assert result is False
        assert not state_path.exists()

    def test_pipeline_active_returns_true_on_same_session(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_is_pipeline_active() returns True when session_id matches and TTL valid."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("current-session")
        _write_state_file(state_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "current-session")
        # Issue #1807 (defect 1): authority binds to the NATIVE stdin identity.
        monkeypatch.setattr(unified_pre_tool, "_session_id", "current-session")
        monkeypatch.setattr(unified_pre_tool, "_agent_type", "")
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)

        result = unified_pre_tool._is_pipeline_active()

        assert result is True
        assert state_path.exists()


class TestIssue1384RecoveryBreadcrumbNotActive:
    """Regression for Issue #1384: a bare recovery heartbeat is NOT a live pipeline.

    pipeline_completion_state.py writes {"session_id","recovered","recovered_at"}
    on restart. With no run_id/mode/explicitly_invoked and no hmac, it previously
    sailed through the mtime-TTL return True for 30 min, causing context-blind
    gates to treat a dead pipeline as live. A genuine STEP-0 sentinel always
    carries at least one of run_id/mode/explicitly_invoked and MUST still be
    classified active.
    """

    def _bare_recovery(self, session_id: str = "current-session") -> dict:
        """Recovery breadcrumb exactly as pipeline_completion_state writes it."""
        return {
            "session_id": session_id,
            "recovered": True,
            "recovered_at": datetime.now().isoformat(),
        }

    def _setup(self, tmp_path: Path, monkeypatch, state: dict, *, age_seconds: float = 5.0):
        """Write state, wire env vars, and set the mtime age."""
        import time as _time

        state_path = tmp_path / "state.json"
        _write_state_file(state_path, state)
        old = _time.time() - age_seconds
        os.utime(state_path, (old, old))
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", state.get("session_id", "current-session"))
        # Issue #1807 (defect 1): _is_pipeline_active() binds authority to the
        # NATIVE stdin identity, not CLAUDE_SESSION_ID. Pin it to the state owner so
        # the PERMIT arms exercise the run-bearing-AND-authorized path; the refuse
        # arms (unsigned / no run identity) still deny because the state itself
        # fails the classifier, not because identity is absent.
        monkeypatch.setattr(
            unified_pre_tool, "_session_id", state.get("session_id", "current-session")
        )
        monkeypatch.setattr(unified_pre_tool, "_agent_type", "")
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        return state_path

    def test_bare_recovery_breadcrumb_not_active(self, tmp_path, monkeypatch):
        """Fresh, matching-session bare recovery breadcrumb -> not active."""
        self._setup(tmp_path, monkeypatch, self._bare_recovery())
        assert unified_pre_tool._is_pipeline_active() is False

    def test_genuine_step0_sentinel_still_active(self, tmp_path, monkeypatch):
        """PERMIT arm: a genuine STEP-0 sentinel remains active.

        Issue #1807 AMENDMENT. This node replaces three earlier ones
        (``test_sentinel_with_run_id_still_active``,
        ``..._with_mode_...``, ``..._with_explicitly_invoked_...``) which each
        asserted that adding ONE of run_id/mode/explicitly_invoked to a recovery
        breadcrumb promoted it back to "active". That rule was the #1384 rule and
        it is now strictly stronger: being run-bearing is NECESSARY but not
        SUFFICIENT — the state must also name a determinate owner, carry an
        owner-bound MAC, and be corroborated by a run-start receipt. A
        mode-only or explicitly_invoked-only state has no ``run_id``, so it
        identifies no run and cannot be authority for one. The refusal half of
        that amendment is the next test, so nothing was merely deleted.
        """
        state = sanctioned_state(
            "current-session",
            "test-run",
            session_start=datetime.now().isoformat(),
            mode="full",
            explicitly_invoked=True,
        )
        self._setup(tmp_path, monkeypatch, state)
        assert unified_pre_tool._is_pipeline_active() is True

    def test_run_bearing_but_unsigned_sentinel_is_not_active(self, tmp_path, monkeypatch):
        """REFUSE arm (Issue #1807): run-bearing alone does not authorize.

        The counterfactual for the amendment above, and a DIFFERENT shape from
        the bare breadcrumb arms: this state carries run_id, mode AND
        explicitly_invoked — everything the #1384 rule asked for — but no MAC and
        no run-start receipt. Pre-#1807 it was accepted for 30 minutes on mtime
        alone.
        """
        state = self._bare_recovery()
        state.update({"run_id": "test-run", "mode": "full", "explicitly_invoked": True})
        state.pop("recovered", None)
        self._setup(tmp_path, monkeypatch, state)
        assert unified_pre_tool._is_pipeline_active() is False

    def test_breadcrumb_with_spurious_extra_field_not_active(self, tmp_path, monkeypatch):
        """A recovery breadcrumb with an unrelated extra field is still inactive.

        Only run_id/mode/explicitly_invoked promote a recovered marker to active.
        """
        state = self._bare_recovery()
        state["some_unrelated_field"] = "value"
        self._setup(tmp_path, monkeypatch, state)
        assert unified_pre_tool._is_pipeline_active() is False

    def test_breadcrumb_older_than_ttl_not_active(self, tmp_path, monkeypatch):
        """A recovery breadcrumb older than the TTL is inactive (unchanged path)."""
        self._setup(
            tmp_path,
            monkeypatch,
            self._bare_recovery(),
            age_seconds=unified_pre_tool._PIPELINE_STATE_TTL_SECONDS + 600,
        )
        assert unified_pre_tool._is_pipeline_active() is False

    def test_no_recovered_flag_uses_ttl_path(self, tmp_path, monkeypatch):
        """Without a 'recovered' flag, a fresh SANCTIONED state uses the TTL path -> active.

        Issue #1807: the state is signed and receipt-backed now. The pre-#1807
        literal dict reached the TTL branch on nothing but its own assertion of
        ``explicitly_invoked``; the run-bearing-but-unsigned counterfactual above
        pins that refusal.
        """
        state = sanctioned_state(
            "current-session",
            "r",
            mode="full",
            explicitly_invoked=True,
            session_start=datetime.now().isoformat(),
        )
        self._setup(tmp_path, monkeypatch, state)
        assert unified_pre_tool._is_pipeline_active() is True

    def test_recovered_with_falsy_run_id_still_not_active(self, tmp_path, monkeypatch):
        """A recovered marker with a falsy run_id ('') is still inactive.

        The any(...) guard treats '' as falsy, so an empty run_id does not
        promote the breadcrumb to active.
        """
        state = self._bare_recovery()
        state["run_id"] = ""
        state["mode"] = ""
        state["explicitly_invoked"] = False
        self._setup(tmp_path, monkeypatch, state)
        assert unified_pre_tool._is_pipeline_active() is False


class TestExplicitImplementWithStaleness:
    """Integration tests: _is_explicit_implement_active() with stale session detection."""

    def test_explicit_implement_returns_false_on_stale(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_is_explicit_implement_active() returns False when stale."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("old-session")
        state["explicitly_invoked"] = True
        _write_state_file(state_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "new-session")

        result = unified_pre_tool._is_explicit_implement_active()

        assert result is False
        assert not state_path.exists()

    def test_explicit_implement_returns_true_on_same_session(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_is_explicit_implement_active() returns True when session matches."""
        state_path = tmp_path / "state.json"
        state = _make_valid_state("current-session")
        state["explicitly_invoked"] = True
        _write_state_file(state_path, state)

        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "current-session")

        result = unified_pre_tool._is_explicit_implement_active()

        assert result is True
