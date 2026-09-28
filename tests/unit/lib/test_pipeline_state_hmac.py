"""
Tests for HMAC integrity functions in pipeline_state.py (Issue #557).

Validates that:
1. sign_state adds hmac and nonce fields
2. verify_state_hmac round-trips correctly
3. Tampering with fields invalidates HMAC
4. Different session_id produces different HMAC
5. Nonces are unique across calls
6. Backward compatibility: missing HMAC accepted

Date: 2026-03-25
"""

import sys
from pathlib import Path

import pytest

# Add lib directory to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_state import (
    _compute_state_hmac,
    _get_pipeline_secret_path,
    _read_pipeline_secret,
    cleanup_pipeline_secret,
    sign_state,
    verify_state_hmac,
)


def _make_state(**overrides) -> dict:
    state = {
        "session_start": "2026-03-25T19:00:00",
        "mode": "full",
        "run_id": "test-run-001",
        "explicitly_invoked": True,
    }
    state.update(overrides)
    return state


SESSION_ID = "session-abc-123"


class TestSignState:

    def test_sign_state_adds_hmac_and_nonce(self):
        state = _make_state()
        result = sign_state(state, SESSION_ID)
        assert "hmac" in result
        assert "nonce" in result
        assert len(result["hmac"]) == 64
        assert len(result["nonce"]) == 32

    def test_sign_state_reuses_existing_nonce(self):
        state = _make_state(nonce="existing_nonce_value")
        result = sign_state(state, SESSION_ID)
        assert result["nonce"] == "existing_nonce_value"
        assert "hmac" in result

    def test_nonce_uniqueness(self):
        nonces = set()
        for _ in range(20):
            state = _make_state()
            sign_state(state, SESSION_ID)
            nonces.add(state["nonce"])
        assert len(nonces) == 20


class TestVerifyStateHmac:

    def test_valid_hmac_accepted(self):
        state = _make_state()
        sign_state(state, SESSION_ID)
        assert verify_state_hmac(state, SESSION_ID) is True

    def test_tampered_run_id_rejected(self):
        state = _make_state()
        sign_state(state, SESSION_ID)
        state["run_id"] = "tampered-run-id"
        assert verify_state_hmac(state, SESSION_ID) is False

    def test_tampered_mode_rejected(self):
        state = _make_state()
        sign_state(state, SESSION_ID)
        state["mode"] = "tampered"
        assert verify_state_hmac(state, SESSION_ID) is False

    def test_tampered_explicitly_invoked_rejected(self):
        state = _make_state(explicitly_invoked=False)
        sign_state(state, SESSION_ID)
        state["explicitly_invoked"] = True
        assert verify_state_hmac(state, SESSION_ID) is False

    def test_tampered_session_start_rejected(self):
        state = _make_state()
        sign_state(state, SESSION_ID)
        state["session_start"] = "2099-01-01T00:00:00"
        assert verify_state_hmac(state, SESSION_ID) is False

    def test_different_session_id_does_not_verify(self):
        """A foreign caller cannot present another run's signed state.

        Issue #1807 DELIBERATE AMENDMENT. This node previously asserted the exact
        defect #1807 reports: it was named
        ``test_different_session_id_still_verifies_with_secret_file`` and
        asserted ``is True`` on the grounds that "session ID is no longer the
        HMAC key; the secret file is". That reasoning is sound about the KEY and
        wrong about AUTHORIZATION — it made the owner a field nobody checked, so
        any session could present any run's state as its own. The secret file
        still supplies the key; the owner is now additionally bound INTO the
        signed message and compared against the presented caller.

        Kept (not deleted) because the spec change is the point: a later reader
        must be able to see that the old expectation was retired on purpose, and
        the freeze receipt for this behaviour is
        ``tests/security/test_issue_1807_authority_boundary.py::test_a1_caller_binding_a_foreign_session_must_not_verify``.
        """
        state = _make_state()
        sign_state(state, SESSION_ID)
        assert verify_state_hmac(state, "different-session") is False
        # Control: the SAME state still verifies for its own owner, so the
        # refusal above is caller binding and not a broken signature.
        assert verify_state_hmac(state, SESSION_ID) is True

    def test_missing_secret_file_with_wrong_session_rejects(self):
        """Without the secret file, fallback to session_id — wrong session fails."""
        state = _make_state()
        sign_state(state, SESSION_ID)
        # Remove the secret file to force session_id fallback
        cleanup_pipeline_secret(state["run_id"])
        # Fallback uses session_id; wrong session should fail
        assert verify_state_hmac(state, "wrong-session") is False

    def test_different_run_id_produces_different_hmac(self):
        """Different run_ids generate different secrets, thus different HMACs."""
        state1 = _make_state(run_id="run-aaa")
        state2 = _make_state(run_id="run-bbb")
        state1["nonce"] = "same-nonce"
        state2["nonce"] = "same-nonce"
        sign_state(state1, SESSION_ID)
        sign_state(state2, SESSION_ID)
        assert state1["hmac"] != state2["hmac"]
        # Cleanup
        cleanup_pipeline_secret("run-aaa")
        cleanup_pipeline_secret("run-bbb")

    def test_missing_hmac_backward_compat(self):
        state = _make_state()
        assert verify_state_hmac(state, SESSION_ID) is True

    def test_hmac_present_but_no_nonce_rejected(self):
        state = _make_state(hmac="fake_hmac_value")
        assert verify_state_hmac(state, SESSION_ID) is False

    def test_tampered_hmac_value_rejected(self):
        state = _make_state()
        sign_state(state, SESSION_ID)
        state["hmac"] = "a" * 64
        assert verify_state_hmac(state, SESSION_ID) is False


class TestComputeStateHmac:

    def test_deterministic(self):
        state = _make_state(nonce="fixed-nonce")
        h1 = _compute_state_hmac(state, SESSION_ID)
        h2 = _compute_state_hmac(state, SESSION_ID)
        assert h1 == h2

    def test_different_nonce_different_hmac(self):
        state1 = _make_state(nonce="nonce-aaa")
        state2 = _make_state(nonce="nonce-bbb")
        assert _compute_state_hmac(state1, SESSION_ID) != _compute_state_hmac(state2, SESSION_ID)



class TestSecretFileManagement:
    """Tests for the per-run secret file approach (F1 remediation)."""

    def test_sign_state_creates_secret_file(self):
        state = _make_state(run_id="test-secret-create")
        sign_state(state, SESSION_ID)
        secret_path = _get_pipeline_secret_path("test-secret-create")
        assert secret_path.exists()
        cleanup_pipeline_secret("test-secret-create")

    def test_secret_file_has_restricted_permissions(self):
        import os
        state = _make_state(run_id="test-secret-perms")
        sign_state(state, SESSION_ID)
        secret_path = _get_pipeline_secret_path("test-secret-perms")
        mode = os.stat(secret_path).st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600 but got {oct(mode)}"
        cleanup_pipeline_secret("test-secret-perms")

    def test_secret_not_in_state_dict(self):
        """The secret must NOT be stored in the state dict itself."""
        state = _make_state(run_id="test-no-secret-in-state")
        sign_state(state, SESSION_ID)
        secret = _read_pipeline_secret("test-no-secret-in-state")
        assert secret is not None
        # Verify secret is not in any state field value
        state_json = str(state)
        assert secret not in state_json
        cleanup_pipeline_secret("test-no-secret-in-state")

    def test_forgery_impossible_without_secret_file(self):
        """An attacker who controls the state file but not the secret cannot forge HMAC.

        This is the core regression test for F1: when CLAUDE_SESSION_ID is absent
        (session_id='unknown'), an attacker who knows nonce and all state fields
        still cannot produce a valid HMAC because the key comes from the secret file.
        """
        state = _make_state(run_id="test-forgery-prevention")
        sign_state(state, "unknown")  # Simulate missing session ID

        # Attacker crafts state with known nonce + "unknown" session
        forged = dict(state)
        forged["explicitly_invoked"] = False  # Tamper
        # Attacker tries to re-sign with session_id="unknown" — but lacks the secret
        nonce = forged["nonce"]
        import hashlib, hmac
        attacker_key = ("unknown" + nonce).encode("utf-8")
        parts = [
            forged.get("session_start", ""),
            forged.get("mode", ""),
            forged.get("run_id", ""),
            str(forged.get("explicitly_invoked", False)),
            nonce,
        ]
        message = "|".join(parts).encode("utf-8")
        forged["hmac"] = hmac.new(attacker_key, message, hashlib.sha256).hexdigest()

        # Verification should FAIL because the real secret is not "unknown"+nonce
        assert verify_state_hmac(forged, "unknown") is False
        cleanup_pipeline_secret("test-forgery-prevention")

    def test_cleanup_pipeline_secret_removes_file(self):
        state = _make_state(run_id="test-cleanup-secret")
        sign_state(state, SESSION_ID)
        secret_path = _get_pipeline_secret_path("test-cleanup-secret")
        assert secret_path.exists()
        cleanup_pipeline_secret("test-cleanup-secret")
        assert not secret_path.exists()

    def test_cleanup_nonexistent_secret_no_error(self):
        """Cleaning up a nonexistent secret should not raise."""
        cleanup_pipeline_secret("nonexistent-run-id-xyz")

    def test_same_run_id_reuses_secret(self):
        """Multiple sign_state calls with same run_id use the same secret.

        Issue #1807 AMENDMENT: the SUBJECT is secret REUSE, and the way to
        observe it changed. Two states with the same run_id, the same nonce AND
        the same owner still produce the same MAC — same secret, same message.
        Signing under two DIFFERENT owners now produces different MACs, because
        the owner is inside the message; asserting equality there (the pre-#1807
        expectation) would assert that the MAC ignores the owner.
        """
        state1 = _make_state(run_id="test-reuse-secret", nonce="nonce1")
        state2 = _make_state(run_id="test-reuse-secret", nonce="nonce1")
        sign_state(state1, "session-a")
        sign_state(state2, "session-a")
        # Same run_id + same owner => same secret => same HMAC (nonce is shared)
        assert state1["hmac"] == state2["hmac"]

        other_owner = _make_state(run_id="test-reuse-secret", nonce="nonce1")
        sign_state(other_owner, "session-b")
        assert other_owner["hmac"] != state1["hmac"], (
            "the owner is signed data: two owners must not share a MAC even with "
            "the same secret, run_id and nonce (Issue #1807)"
        )
        cleanup_pipeline_secret("test-reuse-secret")
