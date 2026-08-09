"""Tests for the alignment_verdict field in pipeline_state.py HMAC (Issue #1467).

Cloned from ``tests/unit/lib/test_pipeline_state_alignment.py`` (Issue #585),
which covers the same property for ``alignment_passed``. The new field must be
protected identically: an attacker who can write the state file must not be
able to flip ``escalate`` to ``auto_pass`` without invalidating the signature.

Validates that:
1. alignment_verdict is included in the HMAC-protected message
2. Tampering with alignment_verdict invalidates the HMAC
3. Backward compatibility: state without alignment_verdict signs/verifies
4. alignment_passed and alignment_verdict are independently protected

GitHub Issue: #1467
"""

import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import pipeline_state  # noqa: E402
from pipeline_state import (  # noqa: E402
    _compute_state_hmac,
    cleanup_pipeline_secret,
    sign_state,
    verify_state_hmac,
)

RUN_ID = "test-alignment-verdict-1467"
SESSION_ID = "session-alignment-verdict-1467"


def _make_state(**overrides) -> dict:
    """Create a base pipeline state dict for testing."""
    state = {
        "session_start": "2026-08-09T10:00:00",
        "mode": "full",
        "run_id": RUN_ID,
        "explicitly_invoked": True,
    }
    state.update(overrides)
    return state


@pytest.fixture(autouse=True)
def _isolate_stale_state_failopen(tmp_path, monkeypatch):
    """Neutralize the Issue #753 stale-state fail-open for tamper assertions.

    ``verify_state_hmac`` deliberately fails OPEN when the legacy sentinel
    (``<repo>/.claude/local/implement_pipeline_state.json``) is more than an
    hour old. In a developer worktree that file exists and ages, so a tamper
    test would pass or fail depending on wall-clock time rather than on the
    HMAC. Point the staleness probe at a freshly written tmp sentinel so these
    tests measure signature verification only (Issue #1184 isolation rule).
    """
    sentinel = tmp_path / "legacy_sentinel.json"
    sentinel.write_text("{}")
    monkeypatch.setattr(pipeline_state, "get_legacy_sentinel_path", lambda: sentinel)


@pytest.fixture(autouse=True)
def _cleanup_secret():
    """Remove the per-run pipeline secret after each test (no cross-test bleed)."""
    yield
    cleanup_pipeline_secret(RUN_ID)


class TestHmacIncludesAlignmentVerdict:
    """Verify alignment_verdict participates in HMAC computation."""

    def test_hmac_changes_when_verdict_changes(self):
        """Two states differing only in alignment_verdict must hash differently."""
        secret = "test-secret-1467"
        escalate = _make_state(alignment_passed=False, alignment_verdict="escalate",
                               nonce="fixed-nonce")
        auto_pass = _make_state(alignment_passed=False, alignment_verdict="auto_pass",
                                nonce="fixed-nonce")
        assert _compute_state_hmac(escalate, secret) != _compute_state_hmac(auto_pass, secret)

    def test_tamper_escalate_to_auto_pass_detected(self):
        """The core attack: flip the verdict to a pass value without re-signing."""
        state = _make_state(alignment_passed=False, alignment_verdict="escalate")
        signed = sign_state(state, SESSION_ID)
        assert verify_state_hmac(signed, SESSION_ID) is True

        signed["alignment_verdict"] = "auto_pass"
        assert verify_state_hmac(signed, SESSION_ID) is False

    def test_tamper_auto_pass_to_user_approved_detected(self):
        """Even a pass-to-pass swap breaks the signature (audit integrity)."""
        state = _make_state(alignment_passed=True, alignment_verdict="auto_pass")
        signed = sign_state(state, SESSION_ID)
        assert verify_state_hmac(signed, SESSION_ID) is True

        signed["alignment_verdict"] = "user_approved"
        assert verify_state_hmac(signed, SESSION_ID) is False

    def test_tamper_block_to_auto_pass_detected(self):
        state = _make_state(alignment_passed=False, alignment_verdict="block")
        signed = sign_state(state, SESSION_ID)
        signed["alignment_verdict"] = "auto_pass"
        assert verify_state_hmac(signed, SESSION_ID) is False


class TestBothFieldsIndependentlyProtected:
    """alignment_passed and alignment_verdict must each be covered."""

    def test_flipping_only_alignment_passed_is_detected(self):
        state = _make_state(alignment_passed=False, alignment_verdict="escalate")
        signed = sign_state(state, SESSION_ID)
        signed["alignment_passed"] = True
        assert verify_state_hmac(signed, SESSION_ID) is False

    def test_flipping_both_fields_is_detected(self):
        """The full forgery attempt — flip verdict AND the boolean together."""
        state = _make_state(alignment_passed=False, alignment_verdict="escalate")
        signed = sign_state(state, SESSION_ID)
        signed["alignment_passed"] = True
        signed["alignment_verdict"] = "auto_pass"
        assert verify_state_hmac(signed, SESSION_ID) is False


class TestBackwardCompatibility:
    """Legacy states written before Issue #1467 must still verify."""

    def test_state_without_alignment_verdict_roundtrips(self):
        """No alignment_verdict key at all — signs and verifies (defaults to '')."""
        state = _make_state(alignment_passed=True)
        assert "alignment_verdict" not in state
        signed = sign_state(state, SESSION_ID)
        assert verify_state_hmac(signed, SESSION_ID) is True

    def test_missing_field_and_empty_string_hash_identically(self):
        """The default MUST be '' so pre-#1467 signatures remain valid."""
        secret = "test-secret-1467"
        without = _make_state(alignment_passed=True, nonce="fixed-nonce")
        with_empty = _make_state(alignment_passed=True, alignment_verdict="",
                                 nonce="fixed-nonce")
        assert _compute_state_hmac(without, secret) == _compute_state_hmac(with_empty, secret)

    def test_full_roundtrip_with_verdict(self):
        state = _make_state(alignment_passed=True, alignment_verdict="user_approved")
        signed = sign_state(state, SESSION_ID)
        assert verify_state_hmac(signed, SESSION_ID) is True
        assert signed["alignment_verdict"] == "user_approved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
