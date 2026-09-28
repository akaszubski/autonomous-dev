#!/usr/bin/env python3
"""Arms the frozen #1807 acceptance file does NOT cover (Issue #1807).

The frozen file ``test_issue_1807_authority_boundary.py`` interrogates the three
guarded CONSUMER routes. These arms interrogate the classifier those routes now
share, for four questions the frozen file never asks — each raised by review of
the fix rather than by the original report:

1. **An indeterminate presented caller is a REFUSAL, not a wildcard.** The first
   draft treated ``""``/``"unknown"`` as "cannot tell" and skipped the owner
   comparison, so any caller with no identity inherited a signed run's authority.
   Both spellings are pinned, because ``""`` comes from a hook that has not
   parsed stdin and ``"unknown"`` is what ``resolve_session_id`` returns when its
   whole chain fails — a guard written for one is silently blind to the other.
2. **Legacy v1 MAC compatibility, and its downgrade counterfactual.** A run that
   was already in flight when the owner binding landed carries a v1 signature.
   It must keep working AND be labelled ``legacy_mac=True``; and a v2 state must
   not become v1-verifiable by deleting the unsigned ``hmac_version`` field.
3. **The A9-dependent RESIDUAL, pinned as it actually is.** Both carriers are
   writable by the principal the gate constrains, so a caller willing to write
   both is authorized at library level. That is recorded here as CURRENT
   BEHAVIOUR, not disguised as a refusal the library cannot make.
4. **The pre-#1045 permissive path survives.** A ledger that claims NO run is not
   an uncorroborated claim, and must not start refusing — that is what keeps
   ordering-gate fallback behaviour (#738, #1196) working.

EVIDENCE CLASS of every arm here: ``library-route``. A7 at ``native-boundary``
and A9 remain OPEN/UNMEASURED whatever colour these show.

GitHub Issue: #1807
"""

from __future__ import annotations

import json
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

_OWNER = "sess-1807-classifier"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Redirect sentinel, secret store and ledger into tmp_path, then reap."""
    redirect_pipeline_state(monkeypatch, tmp_path, ps, pcs)
    yield
    clear_run_artifacts(_OWNER)


def _sanctioned() -> dict:
    """Return a state whose owner and run are both corroborated."""
    return sanctioned_state(_OWNER, "classifier-run")


# ---------------------------------------------------------------------------
# 1. An unavailable caller identity fails closed
# ---------------------------------------------------------------------------


def test_positive_control_determinate_owner_is_authorized():
    """PERMIT arm: the instrument can say yes.

    Without this, every refusal below is satisfiable by a classifier hard-wired
    to refuse, and the two arms after it would prove nothing.
    """
    verdict = ps.classify_current_run_authority(_sanctioned(), _OWNER)

    assert verdict.authorized is True, verdict.detail
    assert verdict.authority is ps.RunAuthority.AUTHORIZED
    assert verdict.legacy_mac is False, (
        "a freshly signed state must be v2 (owner bound into the MAC)"
    )


@pytest.mark.parametrize(
    "presented,why",
    [
        ("", "a hook that has not parsed its stdin yet"),
        ("unknown", "resolve_session_id's last-resort return value"),
        ("   ", "whitespace, which strips to the blank case"),
        ("UNKNOWN", "case must not be an escape hatch"),
    ],
)
def test_indeterminate_presented_caller_is_refused(presented, why):
    """REFUSE arm: no caller identity, no authority — even with both carriers valid.

    A signed state AND a matching run-start receipt are present, so the ONLY
    variable is the presented identity. Pre-review this returned AUTHORIZED for
    every value here, which made an unidentified caller the most privileged one.
    """
    state = _sanctioned()

    verdict = ps.classify_current_run_authority(state, presented)

    assert verdict.authorized is False, (
        f"presented={presented!r} ({why}) was authorized against a signed, "
        f"receipt-backed state: {verdict.detail}"
    )
    assert verdict.authority is ps.RunAuthority.IDENTITY_UNAVAILABLE, (
        f"expected IDENTITY_UNAVAILABLE, got {verdict.authority.value}"
    )
    assert "native transport" in verdict.detail, (
        "the refusal must say where identity is supposed to come from"
    )


#: A real Claude session id shape. Used as the positive control for the synthetic
#: arms below: without it, refusing every id would look like a working guard.
_NATIVE_ID = "9f3c1d2e-4b5a-4c6d-8e7f-0a1b2c3d4e5f"

#: The synthetic spellings ``pipeline_completion_state.is_synthetic_session_id``
#: owns. ``stop-N`` is minted by the SubagentStop heartbeat when the real id was
#: unresolvable; ``test-*`` leaks in from hook-subprocess tests. Both are exactly
#: the band ``_is_determinate_session_id`` alone let through.
_SYNTHETIC_IDS = ("stop-7", "STOP-99", "stop-", "test-7", "test-", "TEST-abc")


@pytest.mark.parametrize("synthetic", _SYNTHETIC_IDS)
def test_synthetic_owner_is_not_current_run_authority(synthetic):
    """REFUSE arm: a synthetic OWNER cannot hold authority, receipt or not.

    MEASURED DEFECT (isolated HOME + ledger, 2026-09-27): a signed state with a
    matching run-start receipt and owner ``stop-7`` classified AUTHORIZED, as did
    ``test-7``, while ``unknown`` already refused. The determinacy predicate
    rejected only blank/``unknown``/``none``/``null``, so the synthetic-but-not-
    blank band passed — and ``stop-N`` is an id the pipeline MINTS for itself when
    it cannot resolve the real one, which is the opposite of an authorized owner.
    ``ensure_sentinel_heartbeat`` already refuses to WRITE these (#1481); the
    authority boundary now refuses to BELIEVE them.
    """
    state = sanctioned_state(synthetic, "synthetic-owner-run")

    verdict = ps.classify_current_run_authority(state, synthetic)

    assert verdict.authorized is False, (
        f"owner={synthetic!r} was authorized with a matching receipt: {verdict.detail}"
    )
    assert verdict.authority is ps.RunAuthority.OWNER_UNAVAILABLE, verdict.authority
    assert "SYNTHETIC" in verdict.detail


@pytest.mark.parametrize("synthetic", _SYNTHETIC_IDS)
def test_synthetic_presented_caller_is_not_current_run_authority(synthetic):
    """REFUSE arm on the other half: a synthetic CALLER cannot claim a genuine run.

    A DIFFERENT shape from the arm above — here the state is owned by a real
    session id and only the PRESENTED identity is synthetic. A guard written for
    the owner field alone would be blind to this, and it is the live shape: the
    SubagentStop path calls into these routes with a ``stop-N`` id whenever the
    real session id is unresolvable.
    """
    state = sanctioned_state(_NATIVE_ID, "synthetic-caller-run")
    try:
        verdict = ps.classify_current_run_authority(state, synthetic)

        assert verdict.authorized is False, (
            f"caller={synthetic!r} was authorized against a genuine run: "
            f"{verdict.detail}"
        )
        assert verdict.authority is ps.RunAuthority.IDENTITY_UNAVAILABLE
    finally:
        clear_run_artifacts(_NATIVE_ID)


def test_native_shaped_identity_is_authorized_on_the_same_route():
    """PERMIT arm for both synthetic refusals: a real session id still works.

    Same function, same construction, ONE variable changed — a UUID-shaped id
    instead of a synthetic one. Without this the two arms above are satisfiable
    by a predicate that rejects everything, which would brick every real run.
    """
    state = sanctioned_state(_NATIVE_ID, "native-id-run")
    try:
        verdict = ps.classify_current_run_authority(state, _NATIVE_ID)

        assert verdict.authorized is True, verdict.detail
        assert verdict.authority is ps.RunAuthority.AUTHORIZED
    finally:
        clear_run_artifacts(_NATIVE_ID)


def test_synthetic_predicate_is_not_a_third_divergent_list():
    """The synthetic rule has ONE home, and this is how it stays that way.

    ``pipeline_state`` delegates to
    ``pipeline_completion_state.is_synthetic_session_id`` rather than restating
    the spellings. Pinned because a copied list is how this defect reproduces:
    the pre-fix gap existed precisely because two modules held two different
    notions of "unusable id" and only one of them knew about ``stop-N``.
    """
    for synthetic in _SYNTHETIC_IDS + ("unknown", "", "   "):
        assert pcs.is_synthetic_session_id(synthetic) is True, synthetic
        assert ps._is_usable_owner_identity(synthetic) is False, synthetic
    assert pcs.is_synthetic_session_id(_NATIVE_ID) is False
    assert ps._is_usable_owner_identity(_NATIVE_ID) is True


def test_classifier_does_not_default_identity_from_the_state_it_examines():
    """The artifact under examination must not nominate its own examiner.

    A tempting "repair" for the arm above is to fall back to
    ``state['session_id']`` when the caller presents nothing. That makes the
    comparison vacuous by construction, so it is pinned as FORBIDDEN here: the
    state names ``_OWNER`` and presenting nothing still refuses.
    """
    state = _sanctioned()
    assert state["session_id"] == _OWNER  # precondition, not the claim

    assert ps.classify_current_run_authority(state, "").authorized is False


# ---------------------------------------------------------------------------
# 2. Legacy v1 MAC: in-flight compatibility, and no silent downgrade
# ---------------------------------------------------------------------------


def _v1_signed(owner: str, run_id: str) -> dict:
    """Sign a state with the PRE-#1807 message, as an in-flight run carries it."""
    pcs.record_run_start(owner, run_id)
    state = {
        "session_start": "2026-09-27T08:21:57",
        "mode": "fix",
        "run_id": run_id,
        "explicitly_invoked": True,
        "session_id": owner,
        "alignment_passed": True,
        "alignment_verdict": "auto_pass",
        "nonce": "0123456789abcdef0123456789abcdef",
    }
    secret = ps._get_or_create_pipeline_secret(run_id)
    state["hmac"] = ps._compute_state_hmac(state, secret, version=ps._STATE_MAC_V1)
    return state


def test_legacy_v1_mac_run_stays_authorized_and_is_labelled():
    """A run signed before the owner binding landed must not break mid-flight.

    MEASURED need: run ``66523599c472f49a`` was live in this repository while the
    fix was written, its sentinel signed by the v1 message. Refusing v1 would
    have hard-failed the agent-ordering, completion and commit gates of a running
    pipeline. Compatibility is EXPLICIT — ``legacy_mac=True`` — not silent, so a
    reader can tell an owner that is cryptographically bound from one corroborated
    by the receipt alone.
    """
    state = _v1_signed(_OWNER, "legacy-v1-run")
    try:
        verdict = ps.classify_current_run_authority(state, _OWNER)

        assert verdict.authorized is True, verdict.detail
        assert verdict.legacy_mac is True, (
            "a v1 signature must be REPORTED as legacy, or the compatibility path "
            "is indistinguishable from a fully bound one"
        )
        assert "legacy" in verdict.detail.lower()
    finally:
        ps.cleanup_pipeline_secret("legacy-v1-run")


def test_v2_state_cannot_be_downgraded_by_stripping_the_version_field():
    """REFUSE arm for the compatibility path: no self-service downgrade.

    ``hmac_version`` is itself inside the signed message, so deleting it — the
    obvious way to make a v2 state verify under the weaker v1 rules, which do not
    bind the owner — breaks verification instead of relaxing it. Without this,
    v1 compatibility would be a universal bypass.
    """
    state = _sanctioned()
    # Precondition: a freshly signed state is at the CURRENT owner-binding version
    # (v3 since #1807 all-six binding). The downgrade this refuses is identical
    # for any owner-binding version, so pin to _STATE_MAC_CURRENT, not a literal.
    assert state["hmac_version"] == ps._STATE_MAC_CURRENT

    del state["hmac_version"]

    assert ps.verify_state_hmac(state, _OWNER) is False
    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authority is ps.RunAuthority.MAC_INVALID, verdict.detail


def test_unrecognized_mac_version_is_refused_not_guessed():
    """An unknown message version fails closed rather than picking a shape."""
    state = _sanctioned()
    state["hmac_version"] = 99

    assert ps.verify_state_hmac(state, _OWNER) is False


# ---------------------------------------------------------------------------
# 2b. The #753 stale-MAC fail-open must NOT reach the authority path (Issue #1807)
# ---------------------------------------------------------------------------
#
# verify_state_hmac's #753 branch returns True for ANY invalid MAC when the LEGACY
# sentinel's mtime is > 3600s (a "don't block later sessions" convenience). If the
# AUTHORITY path inherited that, an attacker could tamper a SIGNED field other than
# run_id/owner, let the legacy sentinel go stale, and — with a still-matching
# run-start receipt — get a tampered state AUTHORIZED. The authority path now calls
# verify_state_hmac(..., strict=True), which disables the stale fail-open.


def _age_legacy_sentinel_stale() -> Path:
    """Create the (redirected) legacy sentinel and age its mtime past 3600s."""
    legacy = ps.get_legacy_sentinel_path()
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("{}", encoding="utf-8")
    old = time.time() - 3601
    os.utime(legacy, (old, old))
    return legacy


def test_stale_sentinel_does_not_fail_open_the_authority_mac():
    """FROZEN OPPOSITE (refuse): tampered signed field + STALE legacy sentinel +
    matching receipt => authority REFUSED (MAC_INVALID).

    Exact minimal reproduction (coordinator audit): a sanctioned run (signed v2 +
    matching native owner + matching run-start receipt), a signed NON-owner field
    (``alignment_passed``) mutated after signing, and the LEGACY sentinel aged past
    3600s. Pre-strict the classifier AUTHORIZED this (verify_state_hmac hit the
    #753 stale fallback and returned True). The instrument controls in the same arm
    show the mechanism: the LEGACY (non-strict) verify STILL fails open here, and
    only ``strict=True`` refuses it.
    """
    state = sanctioned_state(_OWNER, "stale-mac-tampered", alignment_passed=True)
    assert pcs.get_run_start_receipt(_OWNER) == state["run_id"]  # receipt matches run_id

    state["alignment_passed"] = False  # tamper a SIGNED, non-owner field
    _age_legacy_sentinel_stale()

    # Instrument control: the LEGACY (#753) path DOES fail open on this shape...
    assert ps.verify_state_hmac(state, _OWNER) is True, (
        "precondition: the #753 stale fail-open no longer triggers for the legacy "
        "API, so this arm would not be exercising the fail-open it guards against"
    )
    # ...but the STRICT verifier the authority path uses refuses it.
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False

    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is False, (
        f"a tampered signed field on a stale-sentinel run was AUTHORIZED: "
        f"{verdict.detail}"
    )
    assert verdict.authority is ps.RunAuthority.MAC_INVALID, verdict.authority


def test_stale_sentinel_untampered_same_owner_still_authorized():
    """POSITIVE control: strict verification does not break a genuine run.

    ONE variable changed from the negative above — no tampering. An untampered
    sanctioned run whose legacy sentinel is stale (secret present, MAC verifies)
    must still AUTHORIZE, proving the strict tightening refuses only invalid MACs,
    not merely stale ones.
    """
    state = sanctioned_state(_OWNER, "stale-mac-untampered", alignment_passed=True)
    _age_legacy_sentinel_stale()

    assert ps.verify_state_hmac(state, _OWNER, strict=True) is True
    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is True, verdict.detail
    assert verdict.authority is ps.RunAuthority.AUTHORIZED


def test_stale_mac_red_counterfactual_strict_flag_is_the_deciding_variable():
    """RED counterfactual + GREEN, with the strict flag as the ONLY difference.

    Same input, RECEIPT HELD PRESENT AND MATCHING throughout (so a refusal cannot
    be attributed to a missing receipt), only two variables mutated: (a) a signed
    NON-owner field tampered after signing, (b) the legacy sentinel mtime aged past
    3600s. Then:

    * ``strict=False`` — the #753 LEGACY verify path a PRE-STRICT authority decision
      used — returns ``True`` (FAIL OPEN): a classifier calling this would AUTHORIZE
      the tampered state. This is the RED counterfactual, in-line.
    * ``strict=True`` — the FIXED authority path — returns ``False``, and the
      classifier (which now passes ``strict=True``) returns ``MAC_INVALID`` (GREEN).

    The disposable-clone replay in ``scratchpad/red_stale_mac.py`` shows the same
    RED at the CLASSIFIER-VERDICT level on the pre-strict candidate.
    """
    state = sanctioned_state(_OWNER, "stale-mac-cf", alignment_passed=True)
    # Receipt PRESENT and matching run_id — held fixed across both arms.
    assert pcs.get_run_start_receipt(_OWNER) == state["run_id"]

    state["alignment_passed"] = False  # (a) tampered signed field; owner/run_id intact
    assert state["session_id"] == _OWNER and state["run_id"]
    _age_legacy_sentinel_stale()       # (b) stale mtime only

    # RED counterfactual (legacy / strict=False): fails OPEN -> would authorize.
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is True, (
        "RED counterfactual not exercised: the legacy #753 stale fail-open did not "
        "trigger, so this arm does not demonstrate the fail-open the fix closes"
    )
    # Receipt STILL present and matching (isolates signature freshness, not receipt).
    assert pcs.get_run_start_receipt(_OWNER) == state["run_id"]

    # GREEN (strict authority path): refused.
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False
    assert ps.classify_current_run_authority(state, _OWNER).authority is (
        ps.RunAuthority.MAC_INVALID
    )


def test_legacy_753_stale_failopen_preserved_for_non_authority_callers():
    """The #753 stale fail-open is UNCHANGED for the LEGACY (non-authority) API.

    A non-authority caller using ``verify_state_hmac`` with the default
    (``strict=False``) still gets ``True`` for an invalid MAC on a stale sentinel —
    behavior unchanged. Named legacy caller retaining this path:
    ``unified_pre_tool._is_explicit_implement_active`` (the #557 integrity check for
    the ``explicitly_invoked`` flag, whose #753 convenience covers batch/worktree
    runs after ``/clear``). Only ``classify_current_run_authority`` passes
    ``strict=True``.
    """
    state = sanctioned_state(_OWNER, "stale-mac-legacy", alignment_passed=True)
    state["alignment_passed"] = False  # invalid MAC
    _age_legacy_sentinel_stale()

    # Default (strict omitted) == legacy path == #753 fail-open preserved.
    assert ps.verify_state_hmac(state, _OWNER) is True
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is True


# ---------------------------------------------------------------------------
# 2c. Secret-free session-id-keyed v2 forgery must NOT satisfy strict (F4 remediation)
# ---------------------------------------------------------------------------
#
# The session-id fallback keys the MAC on the PRESENTED session_id, which is
# MODEL-KNOWABLE (CLAUDE_CODE_SESSION_ID). If it ran under strict, a caller could
# compute _compute_state_hmac(state, own_session_id, version=2) with NO access to
# ~/.claude/pipeline_secrets/ and be AUTHORIZED (legacy_mac=False) — a secret-free
# forgery. The strict short-circuit now runs BEFORE the fallback, so strict is
# satisfiable ONLY by the per-run SECRET-keyed MAC.


def _session_key_forged_v2_state(owner: str, run_id: str) -> dict:
    """Mint a v2-shaped state signed with the OWNER/session-id key — NOT the
    per-run secret — and record a genuine matching run-start receipt.

    No ``_get_or_create_pipeline_secret`` call, so ``_read_pipeline_secret(run_id)``
    is ``None``: the ONLY thing that could accept this MAC is the session-id
    fallback. Receipt is written so a refusal cannot be blamed on a missing receipt.
    """
    pcs.record_run_start(owner, run_id)  # genuine receipt, matching run_id
    state = {
        "session_start": "2026-09-27T08:21:57",
        "mode": "fix",
        "run_id": run_id,
        "explicitly_invoked": True,
        "session_id": owner,
        "alignment_passed": True,
        "alignment_verdict": "auto_pass",
        "nonce": "0123456789abcdef0123456789abcdef",
        "hmac_version": ps._STATE_MAC_V2,
    }
    # SIGNED WITH THE OWNER KEY (model-knowable), NOT the per-run secret.
    state["hmac"] = ps._compute_state_hmac(state, owner, version=ps._STATE_MAC_V2)
    return state


def test_secret_free_session_key_v2_forgery_refused_under_strict():
    """FROZEN NEGATIVE (F4): a secret-free, session-id-keyed v2 MAC + matching
    receipt => authority REFUSED (MAC_INVALID) under strict.

    RED counterfactual (strict=False, the session-id fallback route): the SAME
    forged input is ACCEPTED (fail-open). GREEN (strict=True): refused, and the
    classifier (which uses strict) returns MAC_INVALID. The per-run secret is
    required — this closes the public-key/secret-free forgery. (Not "unforgeable":
    the secret is still model-mintable via sign_state()/record_run_start(); that
    dual-carrier residual is the still-open A9 gap, #1807 OPEN.)
    """
    run_id = "secret-free-v2-forgery"
    state = _session_key_forged_v2_state(_OWNER, run_id)

    # Preconditions: NO per-run secret exists, receipt present + matching run_id.
    assert ps._read_pipeline_secret(run_id) is None, (
        "precondition: a per-run secret exists, so this is not the secret-FREE "
        "forgery this arm must exercise"
    )
    assert pcs.get_run_start_receipt(_OWNER) == run_id

    # RED counterfactual (strict=False / session-id fallback): forgery ACCEPTED.
    assert ps.verify_state_hmac(state, _OWNER, strict=False) is True, (
        "RED counterfactual not exercised: the session-id fallback did not accept "
        "the owner-keyed MAC, so this arm does not demonstrate the secret-free hole"
    )

    # GREEN (strict): the secret-free forgery is refused because the strict
    # short-circuit runs before the session-id fallback.
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is False

    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is False, (
        f"a secret-free session-id-keyed v2 MAC was AUTHORIZED: {verdict.detail}"
    )
    assert verdict.authority is ps.RunAuthority.MAC_INVALID, verdict.authority


def test_secret_signed_run_still_authorized_under_strict_control():
    """POSITIVE control for the F4 tightening: a genuine SECRET-signed run still
    AUTHORIZES under strict, so requiring the per-run secret does not break real
    runs. ONE variable changed from the negative — the MAC key is the per-run
    secret (via sign_state) instead of the owner/session-id key.
    """
    state = sanctioned_state(_OWNER, "secret-signed-control", alignment_passed=True)
    assert ps.verify_state_hmac(state, _OWNER, strict=True) is True
    verdict = ps.classify_current_run_authority(state, _OWNER)
    assert verdict.authorized is True, verdict.detail
    assert verdict.authority is ps.RunAuthority.AUTHORIZED
    assert verdict.legacy_mac is False


# ---------------------------------------------------------------------------
# 3. The A9-dependent residual, recorded as it is
# ---------------------------------------------------------------------------


def test_residual_both_carriers_are_self_mintable_at_library_level():
    """PINS CURRENT BEHAVIOUR, and it is not a refusal.

    Issue #1807 A9 / origin edge, stated rather than hidden. The two carriers the
    classifier requires are an ordinary file under ``$HOME`` and an ordinary file
    in ``/tmp``, and BOTH are reachable from model-controlled Bash:
    ``record_run_start`` writes the receipt and ``sign_state`` creates the very
    secret it signs with. So a caller willing to write both is AUTHORIZED here —
    exactly what this arm asserts.

    What the conjunction does buy is the removal of the SINGLE-artifact forgeries
    (frozen A3: a lone self-minted sentinel; frozen A4: a lone retained ledger run
    id). What it does NOT buy is provenance. That requires the ORIGIN split —
    model-controlled tool calls refused at the OS boundary on the sentinel, the
    secret store AND the ledger, while native hook processes still write them —
    which is acceptance case A9, evidence class ``native-boundary``, OPEN and
    UNMEASURED.

    This arm is deliberately NOT written as ``assert refused``: faking a refusal
    the library cannot make would be worse than the gap. If a future change makes
    this refuse, or makes it weaker still, the diff will surface here.
    """
    minted_owner = "sess-1807-self-minted"
    try:
        state = sanctioned_state(minted_owner, "self-minted-run")
        verdict = ps.classify_current_run_authority(state, minted_owner)

        assert verdict.authorized is True, (
            "if this now refuses, the origin boundary or the classifier changed — "
            f"re-derive the A9 residual rather than deleting this arm: {verdict.detail}"
        )
        assert pcs.get_run_start_receipt(minted_owner) == state["run_id"], (
            "precondition: the receipt this arm relies on was really written by "
            "the public API"
        )
    finally:
        clear_run_artifacts(minted_owner)


# ---------------------------------------------------------------------------
# 4. The pre-#1045 permissive path is unchanged
# ---------------------------------------------------------------------------


def test_ledger_with_no_run_claim_is_not_an_uncorroborated_claim(tmp_path):
    """A ledger that claims NO run must not start refusing.

    ``run_credit_refusal`` keys on the ledger CLAIMING a run
    (``current_run_id``). A session with completions but no run-start is the
    pre-#1045 session-scoped path, which #1807 does not touch — and which the
    ordering-gate fallback arms (#738, #1196) depend on. Without this arm the
    obvious over-broad fix ("no authorized sentinel => never credit") would look
    correct here and break those suites instead.
    """
    sentinel = tmp_path / "absent_sentinel.json"
    pcs.record_agent_completion("sess-no-run-claim", "implementer", issue_number=0)

    assert pcs.get_run_start_receipt("sess-no-run-claim") is None
    assert pcs.run_credit_refusal("sess-no-run-claim", sentinel_path=str(sentinel)) is None


def test_ledger_run_claim_without_a_sentinel_is_refused(tmp_path):
    """REFUSE arm on the same function, with ONE variable changed.

    Same session shape as above plus a run-start receipt, and the sentinel still
    absent: the unsigned ledger now claims a run nothing authorizes. Pairing the
    two makes the deciding variable the CLAIM, not the missing file.
    """
    sentinel = tmp_path / "absent_sentinel.json"
    pcs.record_run_start("sess-run-claim", "orphan-run")

    refusal = pcs.run_credit_refusal("sess-run-claim", sentinel_path=str(sentinel))

    assert refusal is not None
    assert "LEDGER-ONLY RUN CLAIM" in refusal
    assert "REQUIRED NEXT ACTION" in refusal


def test_identity_less_sentinel_refuses_credit_regardless_of_the_ledger(tmp_path):
    """A sentinel that parses but names no run refuses, ledger claim or not.

    Distinct from both arms above: here the file EXISTS. Covers the class "exists
    and parses" != "identifies a run", which is the shape the repair path wrote.
    """
    sentinel = tmp_path / "recovered_sentinel.json"
    sentinel.write_text(
        json.dumps({"session_id": _OWNER, "recovered": True, "recovered_at": "now"}),
        encoding="utf-8",
    )

    refusal = pcs.run_credit_refusal(_OWNER, sentinel_path=str(sentinel))

    assert refusal is not None
    assert "RUN IDENTITY DESTROYED" in refusal
