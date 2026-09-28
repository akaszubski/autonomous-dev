#!/usr/bin/env python3
"""The SECOND re-sign laundering path: the alignment writer (Issue #1807).

``pipeline_state.set_pipeline_base_commit`` already closed the base-commit
signing oracle. This file freezes the SAME oracle on the NORMAL alignment flow:
``alignment_classifier._update_pipeline_state`` loads the on-disk pipeline state,
writes ``alignment_passed``/``alignment_verdict`` and RE-SIGNS it on EVERY F1
alignment (via ``record_alignment_verdict`` / ``evaluate_and_record``). Before the
fix it re-signed WITHOUT first verifying the existing MAC, so now that v3 binds
``issue_number``/``subject``/``base_commit`` a tampered state could be re-signed
into a FRESH VALID signature — laundering the tampering AND recording an alignment
pass over it.

FREEZE / RED→GREEN. Authored to fail against the pre-fix ``_update_pipeline_state``:

* ``test_tampered_signed_field_is_refused_not_laundered`` — PRE-FIX ``sign_state``
  re-signs the tampered state to a valid v3 MAC (``_update_pipeline_state``
  returns True, ``verify_state_hmac`` True). POST-FIX it refuses, leaves the file
  byte-identical, and the caller path (``record_alignment_verdict``) records no
  laundered pass.
* ``test_v2_resume_state_is_recorded_and_resigned_at_v2_not_upgraded`` — PRE-FIX
  ``sign_state`` UPGRADES the resume state to v3, binding fields the v2 message
  never authenticated. POST-FIX it re-signs AT v2, and the v2-unbound fields stay
  unbound.
* ``test_wrong_secret_signed_state_is_refused`` — PRE-FIX ``sign_state`` re-signs
  under whatever secret is on disk, so a rotated (wrong) secret is accepted.
  POST-FIX strict verify against the wrong secret fails and the write is refused.
* ``test_positive_valid_v3_state_is_recorded_and_reverifies`` — the PERMIT arm:
  without it every refusal above is satisfiable by a writer hard-wired to refuse.

EVIDENCE CLASS: ``library-route`` — in-process calls to the real library with
``tests/helpers/state_isolation.redirect_pipeline_state`` redirecting the sentinel,
the ``$HOME`` per-run secret store and the ledger. A7 at ``native-boundary`` and A9
remain OPEN/UNMEASURED whatever colour these show.

GitHub Issue: #1807
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# tests/security/<this file> -> security -> tests -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
for _p in (str(_REPO_ROOT), str(_LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alignment_classifier  # noqa: E402
import pipeline_state as ps  # noqa: E402

from tests.helpers.state_isolation import redirect_pipeline_state  # noqa: E402

_OWNER = "sess-1807-resign"
_RUN_ID = "run-1807-resign"
_BASE_COMMIT = "ac3e04c3248d162b6346fa34fd33831827057b7d"


@pytest.fixture(name="isolated")
def _isolated(monkeypatch, tmp_path):
    """Redirect sentinel, ``$HOME`` secret store and ledger into ``tmp_path``.

    Fails closed if any redirect does not take (see
    ``state_isolation.redirect_pipeline_state``), so a leaked write is a failed
    test rather than a mutated real secret store.
    """
    return redirect_pipeline_state(monkeypatch, tmp_path, ps)


def _base_state(**overrides: Any) -> Dict[str, Any]:
    """The STEP-0 sentinel shape a signed run carries, UNSIGNED and pre-alignment.

    Args:
        **overrides: Fields replaced over the defaults.

    Returns:
        A fresh dict (no ``hmac``/``nonce`` yet).
    """
    state: Dict[str, Any] = {
        "session_start": "2026-09-27T08:21:57",
        "mode": "fix",
        "run_id": _RUN_ID,
        "explicitly_invoked": True,
        "session_id": _OWNER,
        "issue_number": 1807,
        "subject": "close the alignment re-sign laundering path",
        "base_commit": _BASE_COMMIT,
        "alignment_passed": False,
        "alignment_verdict": "",
    }
    state.update(overrides)
    return state


def _sign_v3(state: Dict[str, Any]) -> Dict[str, Any]:
    """Sign at the CURRENT version (v3) through the production ``sign_state``."""
    return ps.sign_state(state, state["session_id"])


def _sign_v2(state: Dict[str, Any]) -> Dict[str, Any]:
    """Sign at v2 the way a run in flight before the v3 binding landed carries it.

    ``sign_state`` always targets the current version, so a genuine v2 signature
    is reproduced directly: create the per-run secret, then compute the v2 MAC.
    """
    if not state.get("nonce"):
        state["nonce"] = secrets.token_hex(16)
    secret = ps._get_or_create_pipeline_secret(state["run_id"])
    state["hmac_version"] = ps._STATE_MAC_V2
    state["hmac"] = ps._compute_state_hmac(state, secret, version=ps._STATE_MAC_V2)
    return state


def _write(path: Path, state: Dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _read(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _auto_pass_verdict() -> "alignment_classifier.AlignmentVerdict":
    """A minimal AUTO_PASS verdict, mirroring the #1802 test's construction."""
    return alignment_classifier.AlignmentVerdict(
        verdict=alignment_classifier.Verdict.AUTO_PASS,
        feature_text="close the alignment re-sign laundering path",
        citation_verified=True,
    )


# ---------------------------------------------------------------------------
# PERMIT arm — the writer can say yes to a genuine signed run.
# ---------------------------------------------------------------------------


def test_positive_valid_v3_state_is_recorded_and_reverifies(isolated):
    """A genuine v3 state is recorded and still verifies for its owner.

    Without this control every refusal below is satisfiable by a writer that
    refuses everything, and the fix would be indistinguishable from a break.
    """
    sentinel = isolated.sentinel
    _write(sentinel, _sign_v3(_base_state()))

    ok = alignment_classifier._update_pipeline_state(
        sentinel, session_id=_OWNER, alignment_passed=True, verdict_value="auto_pass"
    )
    assert ok is True, "the alignment write refused a genuine v3 run"

    after = _read(sentinel)
    assert after["alignment_passed"] is True
    assert after["alignment_verdict"] == "auto_pass"
    assert after["hmac_version"] == ps._STATE_MAC_V3
    assert ps.verify_state_hmac(after, _OWNER, strict=True) is True, (
        "a genuine run re-signed by the alignment write no longer verifies"
    )


# ---------------------------------------------------------------------------
# REFUSE arm 1 — a tampered signed field must not be laundered into a valid MAC.
# ---------------------------------------------------------------------------


def test_tampered_signed_field_is_refused_not_laundered(isolated):
    """Tamper a v3-bound run-identity field; the re-sign must refuse, not launder.

    PRE-FIX ``_update_pipeline_state`` called ``sign_state`` unconditionally,
    minting a FRESH VALID v3 signature over ``issue_number=9999`` AND recording
    ``alignment_passed=True`` — the signing oracle. POST-FIX it strict-verifies
    the existing MAC first, sees it is invalid, and refuses with no write.
    """
    sentinel = isolated.sentinel
    state = _sign_v3(_base_state())
    # Tamper a v3-bound field AFTER signing: the stored MAC is now invalid.
    state["issue_number"] = 9999
    _write(sentinel, state)

    # The shape a fix must refuse to launder: on-disk MAC does not verify.
    assert ps.verify_state_hmac(_read(sentinel), _OWNER, strict=True) is False

    before = _digest(sentinel)
    ok = alignment_classifier._update_pipeline_state(
        sentinel, session_id=_OWNER, alignment_passed=True, verdict_value="auto_pass"
    )
    assert ok is False, (
        "the alignment write re-signed a tampered state (laundering "
        "issue_number=9999 + alignment_passed=True into a valid signature)"
    )
    assert _digest(sentinel) == before, "a refused write must leave the file untouched"
    laundered = _read(sentinel)
    assert ps.verify_state_hmac(laundered, _OWNER, strict=True) is False
    assert laundered.get("alignment_passed") is False, (
        "alignment_passed was written onto a tampered state"
    )

    # The real caller path fails closed too: record_alignment_verdict may write
    # its artifact, but must NOT persist a valid re-signed state carrying the pass.
    alignment_classifier.record_alignment_verdict(
        _auto_pass_verdict(),
        state_path=sentinel,
        session_id=_OWNER,
        repo_root=isolated.root,
    )
    after_caller = _read(sentinel)
    assert ps.verify_state_hmac(after_caller, _OWNER, strict=True) is False, (
        "record_alignment_verdict laundered a tampered state into a valid signature"
    )
    assert _digest(sentinel) == before, (
        "record_alignment_verdict wrote a re-signed state on the refuse path"
    )


# ---------------------------------------------------------------------------
# REFUSE arm 2 — a resume/legacy v2 state re-signs AT v2, never upgraded to v3.
# ---------------------------------------------------------------------------


def test_v2_resume_state_is_recorded_and_resigned_at_v2_not_upgraded(isolated):
    """A valid v2 resume state is recorded and re-signed AT v2, not upgraded.

    PRE-FIX ``sign_state`` upgraded it to v3, binding ``issue_number``/``subject``/
    ``base_commit`` that the v2 signature never authenticated — laundering
    unauthenticated values into an authenticated v3. POST-FIX the re-sign happens
    at the DECLARED version, so those fields stay unbound.
    """
    sentinel = isolated.sentinel
    signed_v2 = _sign_v2(_base_state())
    assert signed_v2["hmac_version"] == ps._STATE_MAC_V2
    _write(sentinel, signed_v2)
    assert ps.verify_state_hmac(_read(sentinel), _OWNER, strict=True) is True

    ok = alignment_classifier._update_pipeline_state(
        sentinel, session_id=_OWNER, alignment_passed=True, verdict_value="auto_pass"
    )
    assert ok is True, "the alignment write refused a genuine v2 resume run"

    after = _read(sentinel)
    assert after["alignment_passed"] is True
    assert after["alignment_verdict"] == "auto_pass"
    assert after["hmac_version"] == ps._STATE_MAC_V2, (
        "the v2 resume state was UPGRADED to v3 by the re-sign (no-upgrade broken)"
    )
    assert ps.verify_state_hmac(after, _OWNER, strict=True) is True

    # No accidental upgrade: issue_number/subject are NOT in the v2 signed
    # message, so altering them on the re-signed state must STILL verify at v2.
    probe = dict(after)
    probe["issue_number"] = 4242
    probe["subject"] = "a totally different subject"
    assert ps.verify_state_hmac(probe, _OWNER, strict=True) is True, (
        "the re-sign bound v2-unbound fields, i.e. it silently upgraded to v3"
    )


# ---------------------------------------------------------------------------
# REFUSE arm 3 — a state whose per-run secret does not match is refused.
# ---------------------------------------------------------------------------


def test_wrong_secret_signed_state_is_refused(isolated):
    """A state signed under a different per-run secret must be refused.

    PRE-FIX ``sign_state`` re-signed under whatever secret was on disk, so a
    rotated secret was silently accepted. POST-FIX strict verify uses the current
    secret against the old-secret MAC, fails, and the write is refused.
    """
    sentinel = isolated.sentinel
    _write(sentinel, _sign_v3(_base_state()))

    # Rotate the per-run secret: the stored MAC was computed under the old one.
    secret_path = ps._get_pipeline_secret_path(_RUN_ID)
    secret_path.write_text("deadbeef" * 8, encoding="utf-8")

    before = _digest(sentinel)
    ok = alignment_classifier._update_pipeline_state(
        sentinel, session_id=_OWNER, alignment_passed=True, verdict_value="auto_pass"
    )
    assert ok is False, "the alignment write accepted a wrong-secret state"
    assert _digest(sentinel) == before, "a refused write must leave the file untouched"
    assert ps.verify_state_hmac(_read(sentinel), _OWNER, strict=True) is False


# ---------------------------------------------------------------------------
# REFUSE arm 4 — Hole A: a signed state with `hmac` DELETED must not be re-minted.
# ---------------------------------------------------------------------------


def test_missing_hmac_signed_state_is_refused_not_minted(isolated):
    """Strip ``hmac`` from a signed v3 state + tamper a field -> refuse, no mint.

    PRE-FIX (of this second pass) this routed to the ``else: sign_state()``
    unsigned-legacy branch and was handed a FRESH VALID v3 signature carrying
    ``alignment_passed=True`` — laundering ``issue_number=9999`` (returned True,
    verified True, tampered value survived). An unsigned file and a hmac-stripped
    signed file are observationally identical here, so the only safe answer is to
    fail closed. POST-FIX no signature is minted and nothing is written.
    """
    sentinel = isolated.sentinel
    state = _sign_v3(_base_state())
    # The Hole-A attack: delete the signature, tamper a bound field.
    del state["hmac"]
    state["issue_number"] = 9999
    _write(sentinel, state)

    before = _digest(sentinel)
    ok = alignment_classifier._update_pipeline_state(
        sentinel, session_id=_OWNER, alignment_passed=True, verdict_value="auto_pass"
    )
    assert ok is False, (
        "a hmac-stripped tampered state was minted a fresh valid signature "
        "(the unsigned-legacy laundering oracle)"
    )
    assert _digest(sentinel) == before, "a refused write must leave the file untouched"
    after = _read(sentinel)
    assert "hmac" not in after, "a signature was minted onto a hmac-stripped state"
    assert after.get("alignment_passed") is False, (
        "an alignment pass was recorded onto a hmac-stripped tampered state"
    )


# ---------------------------------------------------------------------------
# REFUSE arm 5 — Hole B: a non-dict JSON payload must return False, not raise.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", [[1, 2, 3], 42, "a bare string", None])
def test_non_dict_state_is_refused_without_raising(isolated, payload):
    """Non-dict JSON (list, scalar, null) returns False instead of AttributeError.

    PRE-FIX ``state.get(...)`` raised ``AttributeError`` on a non-dict payload.
    """
    sentinel = isolated.sentinel
    sentinel.write_text(json.dumps(payload), encoding="utf-8")

    before = _digest(sentinel)
    ok = alignment_classifier._update_pipeline_state(
        sentinel, session_id=_OWNER, alignment_passed=True, verdict_value="auto_pass"
    )
    assert ok is False, f"non-dict payload {payload!r} was not refused"
    assert _digest(sentinel) == before, "a refused write must leave the file untouched"


# ---------------------------------------------------------------------------
# REFUSE arm 6 — a genuinely-unsigned (never-signed) state fails closed.
# ---------------------------------------------------------------------------


def test_unsigned_never_signed_state_is_refused(isolated):
    """A never-signed state (no ``hmac``) fails closed — no auto-sign mint.

    Documents the named backward-compat reduction: the alignment path no longer
    migrates a genuinely-unsigned historical state into a signed one; that
    requires a SEPARATE explicitly-authenticated / reinitialized path (a fresh
    run). ``test_control_identity_less_record_mints_no_authority`` in the frozen
    acceptance file pins the same fail-closed intent for the recovery-record shape.
    """
    sentinel = isolated.sentinel
    _write(sentinel, _base_state())  # determinate owner + run_id, but NO hmac

    before = _digest(sentinel)
    ok = alignment_classifier._update_pipeline_state(
        sentinel, session_id=_OWNER, alignment_passed=True, verdict_value="auto_pass"
    )
    assert ok is False, "an unsigned state was auto-signed (mint-on-unsigned oracle)"
    assert _digest(sentinel) == before, "a refused write must leave the file untouched"
    after = _read(sentinel)
    assert "hmac" not in after, "a signature was minted onto an unsigned state"
    assert after.get("alignment_passed") is False, (
        "an alignment pass was recorded onto an unsigned state"
    )
