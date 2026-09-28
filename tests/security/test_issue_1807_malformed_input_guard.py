#!/usr/bin/env python3
"""Malformed-input fail-closed guard for the shared authority primitive (#1807).

``verify_state_hmac`` is the shared integrity primitive; ``classify_current_run_
authority`` calls it BARE and documents "NEVER raises". Before this guard a
malformed state made ``verify_state_hmac`` RAISE instead of returning a bool:

* a non-str signed field (e.g. ``mode=123``) raised inside ``_compute_state_hmac``'s
  v1/v2 ``"|".join`` (and a non-str ``nonce`` inside the ``secret + nonce`` concat);
* a non-str stored ``hmac`` (e.g. ``123``, a ``dict``) raised inside
  ``hmac.compare_digest``.

The raise only failed closed by accident — hook consumers wrap the call in
``except Exception`` — and it violated the classifier's documented contract
outright. The guard is purely additive fail-closed-BY-RETURN: it changes no MAC
message bytes, so every genuine v1/v2/v3 signature still verifies True.

INVARIANT under test: malformed input ⇒ ``False`` in strict=True AND strict=False
(never raise, never fail-open-True); and ``classify_current_run_authority`` returns
an unauthorized verdict rather than raising, on every malformed shape.

The TAUTOLOGY GUARD arms capture the PRE-FIX raise at the primitive level (so the
negative arms are not vacuous) alongside a benign control that does NOT raise and
verifies True. The negative shapes are deliberately DIFFERENT from one another
(non-dict / non-str MAC / non-str signed field / non-str nonce), not enumerated
members of one shape, so the guard is proven against a class.

EVIDENCE CLASS of every arm here: ``library-route``. A9 / native-boundary is
untouched by this change and remains OPEN.

GitHub Issue: #1807
"""

from __future__ import annotations

import hmac as _stdlib_hmac
import os
import sys
import time
from pathlib import Path

import pytest

# tests/security/<this file> -> security -> tests -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
for _p in (str(_REPO_ROOT), str(_LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pipeline_completion_state as pcs  # noqa: E402
import pipeline_state as ps  # noqa: E402

from tests.helpers.sanctioned_run import (  # noqa: E402
    clear_run_artifacts,
    sanctioned_state,
)
from tests.helpers.state_isolation import redirect_pipeline_state  # noqa: E402

_OWNER = "sess-1807-malformed"
_FIXED_NONCE = "0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Redirect sentinel, secret store and ledger into tmp_path, then reap.

    Every per-run secret this module mints via ``_get_or_create_pipeline_secret``
    lands in the redirected ``$HOME`` under tmp_path, so nothing touches the
    operator's real ``~/.claude/pipeline_secrets/`` (Issue #1807 / #1779).
    """
    redirect_pipeline_state(monkeypatch, tmp_path, ps, pcs)
    yield
    clear_run_artifacts(_OWNER)


def _base_state(*, run_id: str = "malformed", **overrides) -> dict:
    """A well-formed pipeline state dict; ``overrides`` inject the malformation."""
    state = {
        "session_start": "2026-09-27T08:21:57",
        "mode": "fix",
        "run_id": run_id,
        "explicitly_invoked": True,
        "alignment_passed": True,
        "alignment_verdict": "auto_pass",
        "nonce": _FIXED_NONCE,
        "session_id": _OWNER,
    }
    state.update(overrides)
    return state


def _signed_state(version: int, *, run_id: str) -> dict:
    """Build a genuine per-run-secret-signed state at the given MAC version."""
    secret = ps._get_or_create_pipeline_secret(run_id)
    state = _base_state(run_id=run_id)
    if version >= ps._STATE_MAC_V2:
        state["hmac_version"] = version
    state["hmac"] = ps._compute_state_hmac(state, secret, version=version)
    return state


def _arm_stale_753() -> None:
    """Create the (redirected) legacy sentinel and age its mtime past 3600s.

    Arms the #753 stale fail-open: with it armed, a MISMATCHING MAC on a
    well-typed state returns True under strict=False. The type-reject arms rely on
    this being armed to prove they refuse a wrong-TYPE field BEFORE #753 could
    rescue it; the well-typed control proves #753 is genuinely armed (non-vacuous).
    """
    legacy = ps.get_legacy_sentinel_path()
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("{}", encoding="utf-8")
    old = time.time() - 3601
    os.utime(legacy, (old, old))


#: The signed fields verify_state_hmac str-requires. Mirrors
#: ``pipeline_state._STR_REQUIRED_SIGNED_FIELDS``; asserted in lockstep below.
#: subject/base_commit are str-required (always-str in production, no int golden
#: case); issue_number is EXCLUDED (intentionally JSON-native int — the golden 1807).
_STR_REQUIRED = (
    "session_start",
    "mode",
    "run_id",
    "alignment_verdict",
    "nonce",
    "session_id",
    "subject",
    "base_commit",
)


# ---------------------------------------------------------------------------
# 0. TAUTOLOGY GUARD — the pre-fix RAISE is real, the benign control is not
# ---------------------------------------------------------------------------


def test_tautology_nonstr_mode_raises_at_primitive_under_secret_key():
    """PRE-FIX evidence (strict path): a non-str signed field RAISES in the raw
    v1 ``"|".join`` under the per-run-secret key, and verify now returns False.

    Without this arm the strict negative below could pass against an input that
    never raised — a vacuous refusal. Captures the exact pre-fix ``TypeError``.
    """
    secret = ps._get_or_create_pipeline_secret("taut-mode-strict")
    try:
        state = _base_state(run_id="taut-mode-strict", mode=123)
        # PRE-FIX: the raw primitive raises (this is what verify used to propagate).
        with pytest.raises(TypeError):
            ps._compute_state_hmac(state, secret, version=ps._STATE_MAC_V1)
        # POST-FIX: verify converts that raise into a fail-closed False.
        state["hmac"] = "a" * 64
        assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
    finally:
        ps.cleanup_pipeline_secret("taut-mode-strict")


def test_tautology_nonstr_mode_raises_at_primitive_under_session_key():
    """PRE-FIX evidence (strict=False fallback path): the SAME field raises under
    the session-id fallback key too, so the legacy-path False is also real work.

    This is the second required tautology capture (one strict=True, one
    strict=False), covering the secret-MISSING session-id fallback branch.
    """
    state = _base_state(run_id="taut-mode-legacy", mode=123)
    # No secret exists for this run_id -> the session-id fallback is the branch used.
    assert ps._read_pipeline_secret("taut-mode-legacy") is None
    with pytest.raises(TypeError):
        ps._compute_state_hmac(state, _OWNER, version=ps._STATE_MAC_V1)
    state["hmac"] = "a" * 64
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is False


def test_tautology_nonstr_hmac_raises_at_compare_digest():
    """PRE-FIX evidence: a non-str stored MAC RAISES inside compare_digest, the
    primitive the up-front guard now short-circuits in both modes."""
    with pytest.raises(TypeError):
        _stdlib_hmac.compare_digest(123, "a" * 64)  # type: ignore[arg-type]
    state = _base_state(run_id="taut-hmac", hmac=123)
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is False


def test_tautology_nondict_raises_at_get():
    """PRE-FIX evidence: ``.get`` on a non-dict RAISES; the up-front isinstance
    guard now returns False before any attribute access, in both modes."""
    with pytest.raises(AttributeError):
        [1, 2, 3].get("hmac")  # type: ignore[attr-defined]
    assert ps.verify_state_hmac([1, 2, 3], _OWNER, strict=True) is False
    assert ps.verify_state_hmac([1, 2, 3], _OWNER, strict=False) is False


def test_tautology_nonstr_run_id_raises_at_secret_path():
    """WHY run_id is str-required: a non-str ``run_id`` raises TypeError at the
    SECRET-PATH ``re.sub`` (a raise site outside the MAC computation). That raise
    is the underlying reason ``run_id`` is in the str-require set; verify now
    refuses it up front (type check) in BOTH modes rather than reaching re.sub.
    """
    with pytest.raises(TypeError):
        ps._read_pipeline_secret(123)  # type: ignore[arg-type]
    state = _base_state(run_id=123, hmac="0" * 64)
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is False


def test_tautology_benign_control_does_not_raise_and_verifies_true():
    """CONTROL: a genuine state's primitive does NOT raise and verify returns
    True — so the raises above belong to the malformed inputs, not everything."""
    state = _signed_state(ps._STATE_MAC_V3, run_id="taut-benign")
    try:
        # No raise on the genuine input:
        ps._compute_state_hmac(
            state, ps._read_pipeline_secret("taut-benign"), version=ps._STATE_MAC_V3
        )
        assert ps.verify_state_hmac(state, _OWNER, strict=True) is True
    finally:
        ps.cleanup_pipeline_secret("taut-benign")


# ---------------------------------------------------------------------------
# 1. MESSAGE BYTES UNCHANGED — the guard is purely additive
# ---------------------------------------------------------------------------


def test_compute_state_hmac_message_bytes_are_frozen():
    """GOLDEN freeze: v1/v2/v3 digests over a fixed (state, secret) are byte-for-
    byte identical to the pre-guard values, proving no message construction moved.

    If any of these three drifts, a real in-flight signature stops verifying —
    which is exactly the backward-incompatibility this change must NOT introduce.
    """
    secret = "fixed-secret-for-golden-test"
    base = {
        "session_start": "2026-09-27T08:21:57",
        "mode": "fix",
        "run_id": "golden-run",
        "explicitly_invoked": True,
        "alignment_passed": True,
        "alignment_verdict": "auto_pass",
        "nonce": _FIXED_NONCE,
        "session_id": "sess-golden-owner",
        "issue_number": 1807,
        "subject": "freeze the message",
        "base_commit": "deadbeef",
    }
    assert (
        ps._compute_state_hmac(dict(base), secret, version=ps._STATE_MAC_V1)
        == "863c610fce67d8c2151b534ee4e4052784d57330a149e8578e9664b4f977fd1e"
    )
    assert (
        ps._compute_state_hmac(dict(base), secret, version=ps._STATE_MAC_V2)
        == "f30ffd243535c904eec667751dab327b3a32a58e8f269af6686db8df2034949b"
    )
    assert (
        ps._compute_state_hmac(dict(base), secret, version=ps._STATE_MAC_V3)
        == "3c3e708fea63fe0cfa59ed56b6f5e58ecb0558a2e92e019f977e3221b354a751"
    )


# ---------------------------------------------------------------------------
# 2. POSITIVE — genuine signed states still verify True (both modes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version", [ps._STATE_MAC_V1, ps._STATE_MAC_V2, ps._STATE_MAC_V3]
)
def test_positive_genuine_signed_state_verifies_true(version):
    """A per-run-secret-signed v1/v2/v3 state verifies True in strict AND legacy.

    This is the PERMIT arm: without it every False below could be produced by a
    verifier that never returns True.
    """
    run_id = f"pos-v{version}"
    state = _signed_state(version, run_id=run_id)
    try:
        assert ps.verify_state_hmac(state, _OWNER, strict=True) is True
        assert ps.verify_state_hmac(state, _OWNER, strict=False) is True
    finally:
        ps.cleanup_pipeline_secret(run_id)


# ---------------------------------------------------------------------------
# 3. ABSENT-HMAC — recognition preserved, but authority still denies
# ---------------------------------------------------------------------------


def test_absent_hmac_verifies_true_in_both_modes():
    """PRESERVED: a state with NO ``hmac`` verifies True (legacy recognition),
    unchanged, in strict AND legacy modes — the guard must not break this."""
    state = _base_state(run_id="absent-hmac")
    assert "hmac" not in state
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is True
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is True


def test_absent_hmac_is_recognized_but_not_current_run_authority():
    """Recognition != authority: verify's True for an unsigned state must NOT
    translate to authorization. The classifier denies it as UNSIGNED_LEGACY."""
    state = _base_state(run_id="absent-hmac-authority")
    assert "hmac" not in state
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is True  # recognition

    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is False
    assert verdict.authority is ps.RunAuthority.UNSIGNED_LEGACY


# ---------------------------------------------------------------------------
# 4. NEGATIVE — malformed input returns False (never raise), in BOTH modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [[1, 2, 3], 42, None, "a string", 3.14, (1, 2)])
def test_negative_nondict_state_returns_false_both_modes(bad):
    """A non-dict state carries no verifiable claim: False, both modes, no raise."""
    assert ps.verify_state_hmac(bad, _OWNER, strict=True) is False
    assert ps.verify_state_hmac(bad, _OWNER, strict=False) is False


@pytest.mark.parametrize("bad_hmac", [123, {"k": "v"}, 3.14, ["a"], True])
def test_negative_nonstr_hmac_returns_false_both_modes(bad_hmac):
    """A stored MAC that is not a str is refused up front in both modes."""
    state = _base_state(run_id="neg-hmac", hmac=bad_hmac)
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is False


def test_negative_nonstr_mode_strict_with_secret_present_returns_false():
    """strict=True, secret PRESENT, ``mode=123``: False, not raise.

    ``mode`` is str-required, so the up-front type check refuses it before the
    secret-keyed computation the authority path uses. A live secret is present to
    confirm the refusal is the type check, not merely a missing secret.
    """
    ps._get_or_create_pipeline_secret("neg-mode-strict")
    try:
        state = _base_state(run_id="neg-mode-strict", mode=123, hmac="a" * 64)
        assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
    finally:
        ps.cleanup_pipeline_secret("neg-mode-strict")


def test_negative_nonstr_mode_legacy_secret_missing_is_false_not_failopen():
    """strict=False, secret MISSING, ``mode=123`` (v1 default): False, and NOT
    fail-open-True even though the #753 stale branch is armed.

    The legacy sentinel is aged past 3600s so the stale fail-open WOULD return True
    if a wrong-TYPE field reached it. It must not: the up-front type check refuses
    ``mode=123`` before secret resolution and before #753. (For a v1 state the old
    ``"|".join`` would also raise into the except backstop; the type check fires
    first and — unlike the backstop — also covers v3, where json.dumps would NOT
    raise. See the v3 parametrized arm in section 4b.)
    """
    assert ps._read_pipeline_secret("neg-mode-legacy") is None
    state = _base_state(run_id="neg-mode-legacy", mode=123, hmac="a" * 64)

    _arm_stale_753()

    assert ps.verify_state_hmac(state, _OWNER, strict=False) is False


@pytest.mark.parametrize("bad_run_id", [123, 3.14, ["r"], {"r": 1}])
def test_negative_nonstr_run_id_returns_false_both_modes(bad_run_id):
    """A non-str ``run_id`` (str-required) is refused up front by the type check in
    BOTH modes — before the secret-path ``re.sub`` it would otherwise raise in."""
    state = _base_state(run_id=bad_run_id, hmac="0" * 64)
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is False


def test_negative_nonstr_nonce_returns_false_both_modes():
    """A non-str ``nonce`` (str-required) is refused up front by the type check in
    both modes — before the ``secret + nonce`` concat it would otherwise raise in."""
    ps._get_or_create_pipeline_secret("neg-nonce")
    try:
        state = _base_state(run_id="neg-nonce", nonce=123, hmac="a" * 64)
        assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
        assert ps.verify_state_hmac(state, _OWNER, strict=False) is False
    finally:
        ps.cleanup_pipeline_secret("neg-nonce")


# ---------------------------------------------------------------------------
# 4b. SIGNED-SCHEMA TYPE validation — the v3 json.dumps hole (both modes)
# ---------------------------------------------------------------------------
#
# v3 serializes the whole message with json.dumps, which does NOT raise on a
# non-str field (unlike the v1/v2 "|".join). So a v3 state with a non-str
# str-required field + bad hmac + NO secret + STALE sentinel would compute a
# mismatching MAC, fall through the compare, and hit the #753 stale fail-open —
# returning True under strict=False. The up-front type check closes this.


def test_str_required_fields_match_library_constant():
    """Lockstep: the fields this suite exercises are exactly the library's set.

    If _compute_state_hmac gains a str-required field and the library tuple is
    updated but this suite is not (or vice-versa), this fails — so the type-reject
    coverage below cannot silently fall out of sync.
    """
    assert tuple(ps._STR_REQUIRED_SIGNED_FIELDS) == _STR_REQUIRED


@pytest.mark.parametrize("field", _STR_REQUIRED)
def test_str_required_field_nonstr_is_false_both_modes_even_when_stale(field):
    """RED->GREEN: each str-required field, present-but-non-str, on a v3 state with
    bad hmac + NO secret + STALE sentinel ⇒ False in BOTH modes.

    Pre-fix, strict=False returned True here for the JSON-serializable value (123):
    json.dumps did not raise, the compare missed, and #753 (armed below) failed
    OPEN. The well-typed control that follows proves #753 IS armed for this exact
    setup, so these refusals are the type check doing real work — not a vacuously
    unreachable #753.
    """
    state = _base_state(run_id="typereject", hmac="0" * 64, hmac_version=ps._STATE_MAC_V3)
    state[field] = 123  # present-but-non-str (JSON-serializable: v3 would not raise)
    _arm_stale_753()

    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False, field
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is False, field


def test_well_typed_value_tamper_still_fails_open_under_753_strict_false():
    """NEGATIVE CONTROL: the fix is TYPE-only, not value-based, and #753 is armed.

    SAME setup as the type-reject arms — bad hmac, no secret, STALE sentinel — but
    ``mode`` is a well-typed str with a WRONG VALUE. strict=False must STILL return
    True (the deliberate, pre-existing #753 non-strict fail-open, UNCHANGED), while
    strict=True (the authority path) is fully fail-closed (False). The ONLY variable
    vs the mode arm above is the TYPE of ``mode``.
    """
    state = _base_state(run_id="welltyped-value", hmac="0" * 64, hmac_version=ps._STATE_MAC_V3)
    state["mode"] = "WRONGSTR"  # valid str, wrong value
    _arm_stale_753()

    assert ps.verify_state_hmac(state, _OWNER, strict=False) is True  # #753 preserved
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False  # authority closed


def test_genuine_v3_with_int_issue_number_verifies_true_both_modes():
    """PERMIT arm the type check must NOT break: a genuine v3 state whose
    ``issue_number`` is the INT 1807 verifies True in BOTH modes.

    v3 intentionally preserves JSON-native types (1807 and "1807" are DISTINCT
    signed tokens), so issue_number/subject/base_commit are deliberately EXCLUDED
    from the str-require set. Str-requiring them would reject this valid state and
    break the golden freeze. subject/base_commit are set here too, as strings, to
    confirm the free-form trio round-trips.
    """
    run_id = "v3-int-issue"
    secret = ps._get_or_create_pipeline_secret(run_id)
    try:
        state = _base_state(run_id=run_id)
        state["hmac_version"] = ps._STATE_MAC_V3
        state["issue_number"] = 1807  # INT — JSON-native, valid by v3 design
        state["subject"] = "int issue number"
        state["base_commit"] = "deadbeef"
        state["hmac"] = ps._compute_state_hmac(state, secret, version=ps._STATE_MAC_V3)

        assert ps.verify_state_hmac(state, _OWNER, strict=True) is True
        assert ps.verify_state_hmac(state, _OWNER, strict=False) is True
    finally:
        ps.cleanup_pipeline_secret(run_id)


def test_genuine_v3_int_issue_number_classifies_authorized():
    """The JSON-native int issue_number also authorizes through the classifier —
    the type check does not over-reject on the authority path either.

    Built manually (secret + receipt + v3 signature over an INT issue_number) so
    the authority-path assertion is unambiguous.
    """
    run_id = "v3-int-issue-cls"
    pcs.record_run_start(_OWNER, run_id)  # second carrier the classifier requires
    secret = ps._get_or_create_pipeline_secret(run_id)
    try:
        state = _base_state(run_id=run_id)
        state["hmac_version"] = ps._STATE_MAC_V3
        state["issue_number"] = 1807  # INT
        state["hmac"] = ps._compute_state_hmac(state, secret, version=ps._STATE_MAC_V3)

        verdict = ps.classify_current_run_authority(state, _OWNER)
        assert verdict.authorized is True, verdict.detail
        assert verdict.authority is ps.RunAuthority.AUTHORIZED
    finally:
        ps.cleanup_pipeline_secret(run_id)


# ---------------------------------------------------------------------------
# 5. classify_current_run_authority — NEVER raises, denies every malformed shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [[1, 2, 3], 42, None, "a string", 3.14])
def test_classify_never_raises_on_nondict_state(bad):
    """A non-dict state is NO_STATE (unauthorized), not an exception."""
    verdict = ps.classify_current_run_authority(bad, _OWNER)
    assert verdict.authorized is False
    assert verdict.authority is ps.RunAuthority.NO_STATE


def test_classify_never_raises_on_nonstr_hmac():
    """A dict whose ``hmac`` is a non-str reaches verify, which returns False
    (guard #2) rather than raising through classify -> MAC_INVALID."""
    state = _base_state(run_id="cls-hmac", hmac=123)
    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is False
    assert verdict.authority is ps.RunAuthority.MAC_INVALID


def test_classify_never_raises_on_nonstr_mode_with_live_secret():
    """``mode=123`` with a live per-run secret exercises verify's INTERNAL raise-
    then-catch. classify must return MAC_INVALID, not propagate the TypeError.

    This is the arm that would have RAISED out of classify pre-fix, breaking its
    documented "NEVER raises" contract.
    """
    ps._get_or_create_pipeline_secret("cls-mode")
    try:
        state = _base_state(run_id="cls-mode", mode=123, hmac="a" * 64)
        verdict = ps.classify_current_run_authority(state, _OWNER)
        assert verdict.authorized is False
        assert verdict.authority is ps.RunAuthority.MAC_INVALID
    finally:
        ps.cleanup_pipeline_secret("cls-mode")


def test_classify_never_raises_on_nonstr_nonce_with_live_secret():
    """A non-str ``nonce`` with a live secret: classify returns MAC_INVALID."""
    ps._get_or_create_pipeline_secret("cls-nonce")
    try:
        state = _base_state(run_id="cls-nonce", nonce=123, hmac="a" * 64)
        verdict = ps.classify_current_run_authority(state, _OWNER)
        assert verdict.authorized is False
        assert verdict.authority is ps.RunAuthority.MAC_INVALID
    finally:
        ps.cleanup_pipeline_secret("cls-nonce")


def test_classify_never_raises_on_nonstr_run_id():
    """classify guards ``run_id`` with its OWN isinstance+regex check
    (NO_RUN_IDENTITY) before verify, so a non-str run_id never even reaches the
    raising secret path. Confirms classify is safe on this shape by a DIFFERENT
    mechanism than the field shapes above (which are caught inside verify)."""
    state = _base_state(run_id=123, hmac="0" * 64)
    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is False
    assert verdict.authority is ps.RunAuthority.NO_RUN_IDENTITY


def test_classify_positive_control_genuine_run_is_authorized():
    """CONTROL: the classifier CAN authorize a genuine run, so the denials above
    are the malformed inputs — not a classifier hardwired to refuse everything."""
    state = sanctioned_state(_OWNER, "cls-positive")
    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is True
    assert verdict.authority is ps.RunAuthority.AUTHORIZED
