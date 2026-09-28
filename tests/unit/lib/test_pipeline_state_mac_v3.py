"""Issue #1807 — v3 all-six-binding tamper-evidence tests.

The v2 MAC bound only three of the six required run bindings (session_id,
run_id, mode). ``issue_number`` and ``subject`` were absent from the sentinel,
and ``base_commit`` — written to the sentinel AFTER signing by
``set_pipeline_base_commit`` — could be altered without invalidating the MAC.
v3 signs all three remaining fields, and ``set_pipeline_base_commit`` now
re-signs, so every binding is tamper-evident.

Each arm uses the REAL ``sign_state`` / ``verify_state_hmac`` /
``set_pipeline_base_commit``. Every negative arm actually flips the verdict
(a probe that cannot fail cannot inform), and the v2 counterfactual proves the
v3 detection is not a probe-that-cannot-fail: the SAME base_commit mutation
verifies True under v2 and False under v3.

GitHub Issue: #1807
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

# tests/unit/lib/<this file> -> lib -> unit -> tests -> repo root
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_state import (  # noqa: E402
    _STATE_MAC_V1,
    _STATE_MAC_V2,
    _STATE_MAC_V3,
    _compute_state_hmac,
    _get_or_create_pipeline_secret,
    cleanup_pipeline_secret,
    set_pipeline_base_commit,
    sign_state,
    verify_state_hmac,
)

OWNER = "sess-mac-v3-owner"
_A_COMMIT = "0ecedce0a1b2c3d4e5f60718293a4b5c6d7e8f90"
_OTHER_COMMIT = "ffffffffffffffffffffffffffffffffffffffff"


@pytest.fixture
def run_id():
    """A unique run id per test, with its secret reaped afterward (Issue #1184)."""
    rid = "mac-v3-" + uuid.uuid4().hex[:12]
    yield rid
    cleanup_pipeline_secret(rid)


def _base_state(rid: str, **overrides) -> dict:
    state = {
        "session_start": "2026-09-28T12:00:00",
        "mode": "full",
        "run_id": rid,
        "explicitly_invoked": True,
        "session_id": OWNER,
        "issue_number": "1807",
        "subject": "harden the pipeline-state authority MAC",
        "base_commit": _A_COMMIT,
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# 1. base_commit RED->GREEN, with the v2 counterfactual (instrument control)
# ---------------------------------------------------------------------------


def test_base_commit_tamper_is_detected_under_v3(run_id):
    """RED->GREEN: mutating base_commit after signing now fails verification."""
    state = _base_state(run_id)
    sign_state(state, OWNER)
    assert state["hmac_version"] == _STATE_MAC_V3, "sign_state must default to v3"
    assert verify_state_hmac(state, OWNER) is True  # valid v3 signature

    state["base_commit"] = _OTHER_COMMIT  # tamper the post-signing field
    assert verify_state_hmac(state, OWNER) is False  # gap closed


def test_base_commit_tamper_was_undetected_under_v2(run_id):
    """The exact gap v3 closes: under v2 the SAME mutation verified True.

    This is the negative control for the test above — it proves the v3 detection
    is a real signal, not a probe that would refuse anything.
    """
    state = _base_state(run_id, nonce="fixed-nonce-v2-gap")
    secret = _get_or_create_pipeline_secret(run_id)
    state["hmac_version"] = _STATE_MAC_V2
    state["hmac"] = _compute_state_hmac(state, secret, version=_STATE_MAC_V2)
    assert verify_state_hmac(state, OWNER) is True

    state["base_commit"] = _OTHER_COMMIT
    # v2 never signed base_commit, so the mutation is INVISIBLE to verification.
    assert verify_state_hmac(state, OWNER) is True


# ---------------------------------------------------------------------------
# 2. Both arms for EACH newly-bound field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, tampered_value",
    [
        ("issue_number", "9999"),
        ("subject", "an entirely different subject"),
        ("base_commit", _OTHER_COMMIT),
    ],
)
def test_v3_binds_each_new_field_both_arms(run_id, field, tampered_value):
    """Positive: a validly v3-signed state verifies. Negative: tampering exactly
    ONE newly-bound field flips verification to False."""
    state = _base_state(run_id)
    sign_state(state, OWNER)
    assert verify_state_hmac(state, OWNER) is True  # positive arm

    assert state[field] != tampered_value, "the mutation must be a real change"
    state[field] = tampered_value
    assert verify_state_hmac(state, OWNER) is False  # negative arm


def test_v3_state_with_absent_new_fields_round_trips(run_id):
    """Existing sanctioned states set none of the three new fields; they must
    still sign and verify (each defaults to "" in the message, INV-6)."""
    state = {
        "session_start": "2026-09-28T00:00:00",
        "mode": "full",
        "run_id": run_id,
        "explicitly_invoked": True,
        "session_id": OWNER,
    }
    sign_state(state, OWNER)
    assert state["hmac_version"] == _STATE_MAC_V3
    assert verify_state_hmac(state, OWNER) is True


# ---------------------------------------------------------------------------
# 3. Backward compatibility: v1/v2 states still verify byte-identically
# ---------------------------------------------------------------------------


def test_v2_signed_state_still_verifies(run_id):
    """A state signed with the v2 message verifies under the new v3-aware code."""
    state = _base_state(run_id, nonce="nonce-v2-compat")
    secret = _get_or_create_pipeline_secret(run_id)
    state["hmac_version"] = _STATE_MAC_V2
    state["hmac"] = _compute_state_hmac(state, secret, version=_STATE_MAC_V2)
    assert verify_state_hmac(state, OWNER) is True


def test_v1_signed_state_still_verifies(run_id):
    """A pre-#1807 v1 state (binds no owner) still verifies for any caller."""
    state = {
        "session_start": "2026-01-01T00:00:00",
        "mode": "full",
        "run_id": run_id,
        "explicitly_invoked": True,
        "nonce": "nonce-v1-compat",
    }
    secret = _get_or_create_pipeline_secret(run_id)
    state["hmac_version"] = _STATE_MAC_V1
    state["hmac"] = _compute_state_hmac(state, secret, version=_STATE_MAC_V1)
    assert verify_state_hmac(state, "any-caller") is True


# ---------------------------------------------------------------------------
# 4. set_pipeline_base_commit round-trip: re-signs so the MAC keeps covering it
# ---------------------------------------------------------------------------


def test_set_pipeline_base_commit_resigns_signed_state(run_id, tmp_path):
    """After writing base_commit, verification still passes (re-signed); then
    tampering base_commit fails."""
    state = _base_state(run_id)
    state.pop("base_commit", None)  # set it via the function under test
    sign_state(state, OWNER)
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state))

    new_sha = "1234567890abcdef1234567890abcdef12345678"
    assert set_pipeline_base_commit(new_sha, state_path=str(path)) is True

    written = json.loads(path.read_text())
    assert written["base_commit"] == new_sha
    assert verify_state_hmac(written, OWNER) is True  # re-signed, MAC covers it

    written["base_commit"] = "0000000000000000000000000000000000000000"
    assert verify_state_hmac(written, OWNER) is False  # tamper after re-sign


def test_set_pipeline_base_commit_fails_closed_without_owner(run_id, tmp_path):
    """A SIGNED state with no determinate owner is not re-signed with an empty
    owner (the #1807 forgery shape) — the function fails closed and writes
    nothing."""
    state = _base_state(run_id, session_id="unknown")
    state.pop("base_commit", None)
    sign_state(state, "unknown")
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state))
    before = path.read_bytes()

    assert set_pipeline_base_commit("abc1230000000000000000000000000000000000",
                                    state_path=str(path)) is False
    assert path.read_bytes() == before, "refuse path must leave the file untouched"
    on_disk = json.loads(path.read_text())
    assert on_disk.get("base_commit") in (None, ""), "nothing should be written"


def test_set_pipeline_base_commit_refuses_to_launder_tampered_state(run_id, tmp_path):
    """LAUNDERING RED->GREEN: a validly v3-signed state whose bound field is then
    mutated (so its MAC is now invalid) must NOT be re-signed into validity.

    Pre-fix, set_pipeline_base_commit re-signed WITHOUT first verifying, so this
    returned True and minted a fresh valid v3 signature over the tampered fields —
    a signing oracle. Now it strict-verifies first, returns False, and the file is
    byte-unchanged. Exercised for every bound field, including the owner itself.
    """
    for field, tampered in (
        ("issue_number", "9999"),
        ("subject", "an attacker-chosen subject"),
        ("base_commit", _OTHER_COMMIT),
        ("session_id", "sess-attacker-0000-1111-2222"),
    ):
        state = _base_state(run_id)
        sign_state(state, OWNER)  # valid v3, secret exists
        assert state[field] != tampered, "the mutation must be a real change"
        state[field] = tampered  # MAC now invalid for this state
        path = tmp_path / f"state_{field}.json"
        path.write_text(json.dumps(state))
        before = path.read_bytes()

        result = set_pipeline_base_commit("cafef00d", state_path=str(path))
        assert result is False, f"laundering of tampered {field} must be refused"
        assert path.read_bytes() == before, (
            f"refused {field} tamper must leave the file byte-unchanged"
        )


def test_set_pipeline_base_commit_refuses_wrong_secret(run_id, tmp_path):
    """WRONG-SECRET: a state whose per-run secret was rotated after signing no
    longer strict-verifies, so it is refused and the file is unchanged."""
    state = _base_state(run_id)
    sign_state(state, OWNER)  # signed under secret A
    cleanup_pipeline_secret(run_id)
    _get_or_create_pipeline_secret(run_id)  # secret B (different bytes)
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state))
    before = path.read_bytes()

    assert set_pipeline_base_commit("cafef00d", state_path=str(path)) is False
    assert path.read_bytes() == before, "refuse path must leave the file untouched"


def test_set_pipeline_base_commit_refuses_v2_downgrade(run_id, tmp_path):
    """DOWNGRADE: a genuinely valid v2 state (which does NOT bind issue_number/
    subject) must be refused, not upgraded-in-place — otherwise those unbound
    fields would be laundered into an authenticated v3 state."""
    state = _base_state(run_id, nonce="nonce-v2-downgrade")
    secret = _get_or_create_pipeline_secret(run_id)
    state["hmac_version"] = _STATE_MAC_V2
    state["hmac"] = _compute_state_hmac(state, secret, version=_STATE_MAC_V2)
    assert verify_state_hmac(state, OWNER) is True  # the v2 signature IS valid
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state))
    before = path.read_bytes()

    assert set_pipeline_base_commit("cafef00d", state_path=str(path)) is False
    assert path.read_bytes() == before, "refuse path must leave the file untouched"


def test_set_pipeline_base_commit_unsigned_state_left_unsigned(tmp_path):
    """Backward compat: an unsigned legacy state (no 'hmac') is written as-is,
    with no owner required — preserving the pre-#1807 base_commit contract."""
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"mode": "full", "run_id": "x", "alignment_passed": True}))

    assert set_pipeline_base_commit("deadbeef", state_path=str(path)) is True
    written = json.loads(path.read_text())
    assert written["base_commit"] == "deadbeef"
    assert "hmac" not in written  # legacy shape preserved, not force-signed
    assert verify_state_hmac(written, "any") is True  # unsigned still recognized


# ---------------------------------------------------------------------------
# 5. V3 injective encoding: the delimiter-slide collision is closed
# ---------------------------------------------------------------------------


def _shared_v3(rid: str) -> dict:
    return {
        "session_start": "2026-09-28T00:00:00",
        "mode": "full",
        "run_id": rid,
        "explicitly_invoked": True,
        "alignment_passed": False,
        "alignment_verdict": "",
        "session_id": OWNER,
        "nonce": "nonce-shared-v3",
        "hmac_version": _STATE_MAC_V3,
    }


def _old_v3_tail(iss, sub, bc) -> str:
    """The pre-fix, NON-injective v3 tail: unescaped 'field:value' joined by '|'."""
    return "|".join([f"issue_number:{iss}", f"subject:{sub}", f"base_commit:{bc}"])


def test_v3_subject_base_commit_slide_collision_closed(run_id):
    """Collision RED->GREEN for the reported subject/base_commit delimiter slide."""
    # RED (pre-fix): the two DISTINCT tuples produced an IDENTICAL message tail
    # (identical prefix + identical tail => identical MAC).
    assert _old_v3_tail("x", "a|base_commit:b", "c") == _old_v3_tail(
        "x", "a", "b|base_commit:c"
    )

    # GREEN (post-fix): under the v3 injective JSON encoding the MACs now differ.
    secret = _get_or_create_pipeline_secret(run_id)
    common = _shared_v3(run_id)
    a = dict(common, issue_number="x", subject="a|base_commit:b", base_commit="c")
    b = dict(common, issue_number="x", subject="a", base_commit="b|base_commit:c")
    assert _compute_state_hmac(a, secret, version=_STATE_MAC_V3) != _compute_state_hmac(
        b, secret, version=_STATE_MAC_V3
    )


def test_v3_issue_number_subject_variants_are_distinct(run_id):
    """Distinct (issue_number, subject) tuples yield distinct MACs.

    This pair did NOT collide even pre-fix (issue_number is not adjacent to the
    terminal field), so this is a non-vacuous injectivity check, not a RED->GREEN.
    """
    secret = _get_or_create_pipeline_secret(run_id)
    common = _shared_v3(run_id)
    a = dict(common, issue_number="1", subject="2", base_commit="z")
    b = dict(common, issue_number="1|subject:2", subject="", base_commit="z")
    assert _compute_state_hmac(a, secret, version=_STATE_MAC_V3) != _compute_state_hmac(
        b, secret, version=_STATE_MAC_V3
    )


def test_v3_benign_equal_tuples_share_a_mac(run_id):
    """Control so the collision test is not vacuous: genuinely equal field tuples
    still produce the SAME MAC."""
    secret = _get_or_create_pipeline_secret(run_id)
    common = _shared_v3(run_id)
    a = dict(common, issue_number="1", subject="a", base_commit="b")
    b = dict(common, issue_number="1", subject="a", base_commit="b")
    assert _compute_state_hmac(a, secret, version=_STATE_MAC_V3) == _compute_state_hmac(
        b, secret, version=_STATE_MAC_V3
    )


def test_v3_issue_number_int_and_str_do_not_collide(run_id):
    """Type policy: int 1807 and str "1807" serialize to distinct JSON tokens
    (1807 vs "1807"), so they do NOT collide; and a signed-then-reloaded state
    still verifies because JSON preserves the field type across the roundtrip
    (no sign/verify drift)."""
    secret = _get_or_create_pipeline_secret(run_id)
    common = _shared_v3(run_id)
    as_int = dict(common, issue_number=1807)
    as_str = dict(common, issue_number="1807")
    assert _compute_state_hmac(
        as_int, secret, version=_STATE_MAC_V3
    ) != _compute_state_hmac(as_str, secret, version=_STATE_MAC_V3)

    # Production shape (str issue_number from env) round-trips and still verifies.
    st = _base_state(run_id, issue_number="1807")
    sign_state(st, OWNER)
    assert verify_state_hmac(json.loads(json.dumps(st)), OWNER) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
