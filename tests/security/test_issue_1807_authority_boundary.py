#!/usr/bin/env python3
"""FROZEN acceptance: what constitutes current-run authority (Issue #1807).

FREEZE STATUS. Authored BEFORE any fix exists, at HEAD
``ac3e04c3248d162b6346fa34fd33831827057b7d``, inside live run
``66523599c472f49a``. The eight counterfactual arms are EXPECTED TO FAIL at this
commit — that observed failure is the freeze receipt. The four positive/control
arms are expected to pass before and after.

EVIDENCE CLASS OF EVERY ARM HERE: ``library-route`` — in-process calls to the
real library functions and hook helpers, with paths/env redirected by
``tests/helpers/state_isolation.redirect_pipeline_state``. They establish what
the LIBRARY and the ROUTE do when asked in-process. They establish NOTHING about
OS-sandbox containment, native hook/tool ORIGIN, or refusal at the real native
boundary. **A7 at ``native-boundary`` class, and A9, stay RED-or-UNMEASURED
whatever colour these arms show** — see
``tests/manual/probe_1807_native_origin_split.sh``.

ONE DEFECT, THREE FACES, all measured at this HEAD.

1. The MAC does not bind the owner. ``_compute_state_hmac``
   (``plugins/autonomous-dev/lib/pipeline_state.py:377``-``404``) signs
   ``session_start``, ``mode``, ``run_id``, ``explicitly_invoked``,
   ``alignment_passed``, ``alignment_verdict``, ``nonce`` — not ``session_id``.
   Wrong-owner, rewritten-owner and deleted-owner states all verify ``True``.
2. Unsigned state is authorized anyway: ``verify_state_hmac`` returns ``True``
   whenever ``hmac`` is absent (``:427``-``430``), and
   ``commands/implement-fix.md:110`` writes exactly that shape. Legacy
   RECOGNITION is defensible; promoting it to AUTHORIZATION silently is not (A8).
3. The caller holds the signing capability: ``sign_state`` (``:476``) CREATES the
   per-run secret it signs with, so a model-controlled caller mints a valid MAC
   in two public calls and both guarded consumers accept it (A3/A7).

The repair path then destroys what the MAC failed to bind:
``ensure_sentinel_heartbeat`` (``lib/pipeline_completion_state.py:3065``), called
after every SubagentStop, overwrites the WHOLE file with
``{"session_id","recovered","recovered_at"}`` (``:3179``-``:3192``) whenever the
existing owner is absent or synthetic — without ever asking whether the file
carries a run. Measured against a signed run-bearing ownerless sentinel:
``return=False``, ``bytes changed=True``, ``run_id after=None`` (A2). Downstream,
the replacement still parses, so ``sentinel_integrity()`` says OK (``:404``) and
the ordering gate dispatches ``implementer`` with an empty completion set (A5).
A4 pins the converse — the unsigned ledger must not re-establish credit on its
own — so the fix cannot simply relocate the hole.

GUARDED CONSUMER ROUTES INTERROGATED ("current-run authorization" seam):
  * ``hooks/unified_pre_tool.py:_is_pipeline_active`` (``:2699``), consumed at
    ``:2102`` for protected-path write authority.
  * ``hooks/unified_pre_tool.py:_has_alignment_passed`` (``:2974``) via
    ``_load_pipeline_state_verified`` (``:2913``).
  * ``agent_ordering_gate.check_ordering_with_session_fallback`` (``:355``) for
    current-run completion credit.

NOT RE-PROVEN HERE (already covered; do not duplicate):
  * ``tests/unit/lib/test_pipeline_state_hmac.py`` — MAC basics: valid MAC
    accepted, tampered ``run_id``/``mode``/``session_start``/
    ``explicitly_invoked`` rejected, secret-file permissions, forgery impossible
    WITHOUT the secret file. Note ``:104``
    ``test_different_session_id_still_verifies_with_secret_file`` asserts the very
    behaviour A1 refuses: fixing #1807 REQUIRES amending that node, which is a
    spec change to make deliberately, not a test to quietly delete.
  * ``tests/spec_validation/test_spec_issue761_hmac_stale_failopen.py`` — the
    #753/#761 stale-sentinel fail-open, both arms.

GitHub Issue: #1807
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
for _p in (str(_REPO_ROOT), str(_LIB_DIR), str(_HOOKS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_ordering_gate as aog  # noqa: E402
import alignment_classifier  # noqa: E402
import pipeline_completion_state as pcs  # noqa: E402
import pipeline_state as ps  # noqa: E402
import unified_pre_tool as hook  # noqa: E402

from tests.helpers.state_isolation import redirect_pipeline_state  # noqa: E402

_IMPLEMENT_FIX_MD = (
    _REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-fix.md"
)
_FREEZE_BASE_COMMIT = "ac3e04c3248d162b6346fa34fd33831827057b7d"


@dataclass(frozen=True)
class Run:
    """Identities and paths for one isolated arm.

    Attributes:
        sentinel: The redirected sentinel path.
        owner: Session id that owns this arm's run.
        intruder: Session id that owns nothing.
        run_id: Run identifier for this arm.
    """

    sentinel: Path
    owner: str
    intruder: str
    run_id: str

    @property
    def ledger_sessions(self) -> tuple:
        """Every session id this arm can touch, for teardown.

        Returns:
            Tuple of session ids.
        """
        return (self.owner, self.intruder, f"{self.owner}-empty", f"{self.owner}-fresh")


@pytest.fixture(name="run")
def _run(monkeypatch, tmp_path):
    """Yield an isolated :class:`Run`, then reap its /tmp ledger files.

    Isolation (sentinel, ``get_legacy_sentinel_path``, ``$HOME`` secret store,
    ``$PIPELINE_STATE_FILE``) comes from the shared
    ``state_isolation.redirect_pipeline_state``, which fails closed.
    """
    paths = redirect_pipeline_state(monkeypatch, tmp_path, ps, pcs, hook)
    # Instrument control: the hook resolves its own session id from hook stdin at
    # IMPORT time, and ``_is_stale_session`` (``unified_pre_tool.py:2213``)
    # DELETES a sentinel owned by a different real session. Under pytest that id
    # is indeterminate, which is what the foreign-owner arms assume. Pin it so
    # they cannot change meaning silently.
    assert getattr(hook, "_session_id", "unknown") in ("", "unknown", None), (
        "hook resolved a real session id; the foreign-owner arms would be "
        "testing _is_stale_session deletion instead of authority binding"
    )
    tag = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:10]
    arm = Run(
        sentinel=paths.sentinel,
        owner=f"owner-{tag}",
        intruder=f"intruder-{tag}",
        run_id=f"run{tag}",
    )
    try:
        yield arm
    finally:
        for session_id in arm.ledger_sessions:
            key = hashlib.sha256(session_id.encode()).hexdigest()[:8]
            for suffix in (".json", ".lock"):
                try:
                    Path(f"/tmp/pipeline_agent_completions_{key}{suffix}").unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# state shapes: the only difference between `forged` and `genuine` is PROVENANCE
# ---------------------------------------------------------------------------


def state_of(run: Run, **overrides: Any) -> Dict[str, Any]:
    """Return the STEP-0 sentinel shape, mirroring the live run's fields.

    Args:
        run: The arm's identities.
        **overrides: Fields to replace; ``None`` DELETES the key (the
            ``commands/implement-fix.md`` F1 shapes).

    Returns:
        A fresh, UNSIGNED dict.
    """
    state: Dict[str, Any] = {
        "session_start": "2026-09-27T08:21:57",
        "mode": "fix",
        "run_id": run.run_id,
        "explicitly_invoked": True,
        "session_id": run.owner,
        "issue_number": 1807,
        "start_time": 1790461317,
        "base_commit": _FREEZE_BASE_COMMIT,
        "alignment_passed": True,
        "alignment_verdict": "auto_pass",
    }
    for key, value in overrides.items():
        if value is None:
            state.pop(key, None)
        else:
            state[key] = value
    return state


def write(run: Run, state: Dict[str, Any]) -> Dict[str, Any]:
    """Persist ``state`` through the production atomic writer.

    Args:
        run: The arm.
        state: State dict.

    Returns:
        The same dict.
    """
    ps.atomic_write_json(run.sentinel, state, indent=2)
    return state


def read(run: Run) -> Any:
    """Return the parsed sentinel, or ``None`` when unparseable.

    Args:
        run: The arm.

    Returns:
        Parsed JSON value or ``None``.
    """
    try:
        return json.loads(run.sentinel.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def forged(run: Run, **overrides: Any) -> Dict[str, Any]:
    """Mint the A7 forgery: correct bindings, valid MAC, NO run-start receipt.

    Two public calls is the whole attack — ``sign_state`` CREATES the per-run
    secret it signs with (``pipeline_state.py:490``-``496``), so the caller holds
    the key as well as the message.

    Args:
        run: The arm.
        **overrides: Passed to :func:`state_of`.

    Returns:
        The signed, written state.
    """
    state = state_of(run, **overrides)
    return write(run, ps.sign_state(state, state.get("session_id", run.owner)))


def genuine(run: Run, **overrides: Any) -> Dict[str, Any]:
    """Initialize the sanctioned run: ledger run-start receipt AND signed sentinel.

    Args:
        run: The arm.
        **overrides: Passed to :func:`state_of`.

    Returns:
        The signed, written state.
    """
    pcs.record_run_start(run.owner, run.run_id, issue_number=1807)
    return write(run, ps.sign_state(state_of(run, **overrides), run.owner))


def recovery(run: Run) -> Dict[str, Any]:
    """Write the identity-less record the heartbeat produces (``:3180``-``3184``).

    Args:
        run: The arm.

    Returns:
        The written dict.
    """
    return write(
        run,
        {
            "session_id": run.owner,
            "recovered": True,
            "recovered_at": "2026-09-27T08:34:00+00:00",
        },
    )


def has_receipt(session_id: str) -> bool:
    """Whether the ledger carries ``current_run_id`` for a session.

    Args:
        session_id: Session to inspect.

    Returns:
        True when the run-start receipt exists.
    """
    try:
        raw = pcs._state_file_path(session_id).read_text(encoding="utf-8")
        return bool(json.loads(raw).get("current_run_id"))
    except (OSError, ValueError):
        return False


def digest(path: Path) -> str:
    """SHA-256 of ``path``, or ``"<absent>"``. Byte identity, not size or mtime.

    Args:
        path: File to digest.

    Returns:
        Hex digest or ``"<absent>"``.
    """
    if not path.exists():
        return "<absent>"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordering(session_id: str, target: str):
    """Ask the live ordering gate whether ``target`` may be dispatched.

    Args:
        session_id: Session the gate reads completions for.
        target: Agent about to be invoked.

    Returns:
        The ``GateResult``.
    """
    return aog.check_ordering_with_session_fallback(
        target, session_id, issue_number=1807, pipeline_mode="fix"
    )


# ---------------------------------------------------------------------------
# COUNTERFACTUALS — each detects a failure no other arm here detects
# ---------------------------------------------------------------------------


def test_a1_caller_binding_a_foreign_session_must_not_verify(run):
    """A1a (counterfactual, RED pre-fix, library-route): foreign owner refused.

    UNIQUE FAILURE: the verifier never compares the PRESENTED session id with the
    state's owner, so any session can present another run's state as its own.
    Putting ``session_id`` inside the signed message does NOT fix this arm — only
    a caller-identity comparison does, which is why it is separate from the
    mutation arm below.
    """
    state = ps.sign_state(state_of(run), run.owner)

    assert ps.verify_state_hmac(state, run.intruder) is False, (
        f"A1a: state signed by {run.owner!r} verified for {run.intruder!r}. "
        "Verification must bind the presented caller to the state's owner "
        "(INV-7). Seam: pipeline_state.verify_state_hmac."
    )


def test_a1_owner_field_must_be_inside_the_mac(run):
    """A1b+A1c (counterfactual, RED pre-fix, library-route): the owner is signed data.

    UNIQUE FAILURE, distinct from A1a: ``state['session_id']`` is outside the
    signed message, so it can be rewritten or deleted after signing without
    invalidating the MAC. Both shapes are asserted because a ``.get(key, "")``
    style fix covers the rewrite while still colliding an ABSENT owner with an
    empty one.
    """
    write(run, ps.sign_state(state_of(run), run.owner))
    tampered = json.loads(run.sentinel.read_text(encoding="utf-8"))
    tampered["session_id"] = run.intruder

    assert ps.verify_state_hmac(tampered, run.owner) is False, (
        "A1b: state['session_id'] was rewritten after signing and the MAC still "
        "verified — a takeover of an existing run's authority."
    )
    assert ps.verify_state_hmac(tampered, run.intruder) is False, (
        "A1b: the rewritten owner verified for the session that wrote it; "
        "self-serving mutation of signed state must not authenticate."
    )

    ownerless = ps.sign_state(state_of(run), run.owner)
    del ownerless["session_id"]
    assert ps.verify_state_hmac(ownerless, run.owner) is False, (
        "A1c: a signed state with state['session_id'] DELETED still verified. "
        "That is the shape commands/implement-fix.md F1 writes and the shape "
        "ensure_sentinel_heartbeat destroys runs over. An absent owner is an "
        "unverifiable owner, and INV-7 treats a verification failure as 'not "
        "passed', never as 'passed'."
    )


def test_a3_forged_valid_mac_state_is_not_current_run_authority(run):
    """A3 / counterfactual A7 (RED pre-fix, library-route): self-minted MAC refused.

    UNIQUE FAILURE: a state the caller minted itself — every binding correct, a
    valid MAC through the real ``sign_state``, and NO run-start receipt anywhere —
    is accepted as the current run by both guarded consumers. The principal that
    must be constrained holds the signing capability, so owner + MAC equality
    cannot be the boundary; authority needs provenance the writer cannot mint.

    EVIDENCE LIMIT: ``library-route``. Green here would mean the in-process route
    refuses the shape. A7 at ``native-boundary`` (a model-controlled
    Bash/Edit/Write/MCP write refused by the OS sandbox or file permissions, with
    a positive control) remains UNMEASURED regardless.
    """
    forged(run)

    # Preconditions, not the claim: these are what make the state a FORGERY.
    assert has_receipt(run.owner) is False, (
        "A3 precondition: a run-start receipt exists for the forged run, so the "
        "state is not unqualified and the arm cannot speak to A7."
    )
    assert ps.verify_state_hmac(read(run), run.owner) is True, (
        "A3 precondition: the forged MAC does not verify at all, so the arm is "
        "not exercising the forgery it claims to."
    )

    assert hook._is_pipeline_active() is False, (
        "A3/A7: a self-minted sentinel was accepted as an active pipeline, which "
        "is what grants protected-path (agents/ commands/ hooks/ lib/ skills/) "
        "write authority at unified_pre_tool.py:2102."
    )
    assert hook._has_alignment_passed() is False, (
        "A3/A7: alignment_passed=true plus a self-minted MAC was honoured as a "
        "passed alignment gate, so the gate attests only that the caller "
        "asserted it — the #1802 same-principal ceiling reached through the "
        "state file instead of evaluate_and_record."
    )


def test_a8_unsigned_legacy_state_is_not_current_run_authority(run):
    """A8 (counterfactual, RED pre-fix, library-route): legacy is not authorized.

    UNIQUE FAILURE, distinct from A3: no MAC is presented AT ALL, so the
    integrity branch is SKIPPED rather than satisfied
    (``pipeline_state.py:427``). A fix that hardens MAC checking without deciding
    what an UNSIGNED state means leaves this route open — and it is the route fix
    mode uses today (``commands/implement-fix.md:110``).
    """
    unsigned = state_of(run, session_id=run.intruder)
    unsigned.pop("hmac", None)
    unsigned.pop("nonce", None)
    write(run, unsigned)

    assert hook._is_pipeline_active() is False, (
        "A8: an UNSIGNED sentinel owned by a foreign session was reported as an "
        "active pipeline, granting protected-path write authority."
    )
    assert hook._has_alignment_passed() is False, (
        "A8: alignment_passed=true was honoured from an UNSIGNED sentinel "
        "written by a foreign owner."
    )


def test_a4_ledger_only_rebind_is_not_current_run_authority(run):
    """A4 (counterfactual, RED pre-fix, library-route): the ledger cannot promote itself.

    UNIQUE FAILURE, the converse of A3: the completion ledger is UNSIGNED
    (``/tmp/pipeline_agent_completions_*``). With the signed sentinel gone, its
    retained ``current_run_id`` still credits ``implementer`` to "the current
    run", so a fix leaning on the ledger merely moves the forgery target. Both
    destruction shapes are asserted — sentinel ABSENT and sentinel replaced by the
    heartbeat's identity-less record — so the fix removes the category instead of
    keying on "file missing".
    """
    pcs.record_run_start(run.owner, run.run_id, issue_number=1807)
    pcs.record_agent_completion(run.owner, "implementer", success=True, issue_number=1807)
    run.sentinel.unlink(missing_ok=True)

    # Instrument control in the same arm: an EMPTY ledger must list implementer
    # missing, or the assertions below are not measuring crediting at all.
    control = ordering(f"{run.owner}-empty", "reviewer")
    assert "implementer" in control.missing_agents, (
        f"A4 control: an EMPTY ledger did not list implementer as missing "
        f"({control.missing_agents!r}); the crediting instrument is blind."
    )

    absent = ordering(run.owner, "reviewer")
    assert "implementer" in absent.missing_agents, (
        "A4a: with NO signed sentinel, the unsigned ledger's retained run id "
        f"still credited implementer to the current run (missing="
        f"{absent.missing_agents!r}). A ledger-only rebind must never be promoted "
        "into signed run authority."
    )
    assert hook._is_pipeline_active() is False, (
        "A4c: a ledger run-start alone was enough to report an active pipeline."
    )

    recovery(run)
    replaced = ordering(run.owner, "reviewer")
    assert "implementer" in replaced.missing_agents, (
        "A4b: an identity-less recovery record plus an unsigned ledger credited "
        f"implementer to a current run (missing={replaced.missing_agents!r})."
    )


def test_a2_heartbeat_must_not_replace_run_bearing_state(run):
    """A2a+A2b (counterfactual, RED pre-fix, library-route): the run survives repair.

    UNIQUE FAILURE: the REPAIR path substitutes an identity-less record for a
    live run, destroying ``run_id``, ``mode``, ``issue_number`` and
    ``base_commit``. Both triggers of that one branch are asserted — owner ABSENT
    (the F1 shape) and owner SYNTHETIC (``:3148``) — because a fix keyed on the
    missing-owner spelling alone would leave the synthetic route destroying runs.
    """
    ownerless = ps.sign_state(state_of(run), run.owner)
    del ownerless["session_id"]
    write(run, ownerless)
    before = digest(run.sentinel)

    pcs.ensure_sentinel_heartbeat(run.owner, state_path=str(run.sentinel))

    after = read(run) or {}
    assert after.get("run_id") == run.run_id and after.get("mode") == "fix", (
        "A2a: the heartbeat replaced run-bearing gating state with an "
        f"identity-less record. before sha256={before} after "
        f"sha256={digest(run.sentinel)} after_keys={sorted(after)}. Seam: "
        "pipeline_completion_state.ensure_sentinel_heartbeat — an absent owner "
        "is not licence to discard a run."
    )

    write(run, ps.sign_state(state_of(run, session_id="stop-7"), "stop-7"))
    pcs.ensure_sentinel_heartbeat(run.owner, state_path=str(run.sentinel))
    synthetic_after = read(run) or {}
    assert (
        synthetic_after.get("run_id") == run.run_id
        and synthetic_after.get("mode") == "fix"
    ), (
        "A2b: a synthetic OWNER on a run-bearing sentinel let the heartbeat "
        f"discard the run (after_keys={sorted(synthetic_after)})."
    )


def test_a2g_fix_mode_initialization_must_bind_owner_and_run(run):
    """A2g (counterfactual, RED pre-fix, library-route): F1 must write an identity.

    UNIQUE FAILURE: the PRODUCER, not the consumer. Not a docs check — the fenced
    block in ``commands/implement-fix.md`` IS the code the coordinator executes at
    F1, and its literal ``state = {...}`` is what lands in the sentinel. Fixing
    the heartbeat while fix mode keeps writing an ownerless, runless, unsigned
    sentinel would leave A1c and A8 armed on every ``--fix`` run.
    """
    matches = re.findall(
        r"^state = \{.*\}$", _IMPLEMENT_FIX_MD.read_text(encoding="utf-8"), re.MULTILINE
    )

    assert matches, (
        "A2g control: no `state = {...}` literal found in "
        "commands/implement-fix.md. The F1 snippet moved or changed shape, so "
        "this arm can no longer see what fix mode writes and must be re-aimed, "
        "not deleted."
    )
    ownerless = [m for m in matches if "session_id" not in m]
    assert not ownerless, (
        f"A2g: fix-mode state is initialized WITHOUT an owner: {ownerless!r} — "
        "the shape ensure_sentinel_heartbeat destroys runs over (A2) and the "
        "shape whose MAC binds nobody (A1c)."
    )
    runless = [m for m in matches if "run_id" not in m]
    assert not runless, (
        f"A2g: fix-mode state is initialized WITHOUT a run id: {runless!r}. With "
        "no run_id the per-run secret degrades to the shared 'unknown' key "
        "(pipeline_state.py:493) and no run-start receipt can be matched to the "
        "sentinel (A4)."
    )


def test_a5_identity_less_sentinel_must_block_agent_dispatch(run):
    """A5a (counterfactual, RED pre-fix, library-route): no run identity, no dispatch.

    UNIQUE FAILURE: "exists and parses" is read as "identifies a run".
    ``sentinel_integrity()`` classifies the recovery record OK, so the gate
    proceeds and ``--fix`` mode's first agent passes on an empty completion set.
    #1779 (AC3) already settled that a destroyed sentinel must refuse;
    destruction by repair is the same fact.
    """
    recovery(run)

    result = ordering(run.owner, "implementer")

    assert result.passed is False, (
        "A5a: agent dispatch was authorized from a sentinel carrying no run "
        f"identity (keys={sorted(read(run) or {})}), reason={result.reason!r}. "
        "Seam: agent_ordering_gate.check_ordering_with_session_fallback."
    )


# ---------------------------------------------------------------------------
# CONTROLS AND THE POSITIVE — a probe that cannot fail cannot inform
# ---------------------------------------------------------------------------


def test_control_absent_state_refuses_every_consumer(run):
    """Instrument control (GREEN pre-fix, library-route): all three routes can say no.

    UNIQUE FAILURE: a consumer stuck on ``True``/``passed``. Aimed at the same
    three live entry points every counterfactual above uses. This is the single
    absent-state control for the whole file.
    """
    run.sentinel.unlink(missing_ok=True)

    assert hook._is_pipeline_active() is False, (
        "control: no sentinel, yet _is_pipeline_active() reported active."
    )
    assert hook._has_alignment_passed() is False, (
        "control: no sentinel, yet _has_alignment_passed() reported passed."
    )
    assert ordering(f"{run.owner}-fresh", "reviewer").passed is False, (
        "control: the ordering gate passed reviewer with no state whatsoever."
    )


def test_control_heartbeat_existing_guards_and_instrument(run):
    """A2c+A2e+A2f (controls, GREEN pre-fix, library-route): guards and instrument intact.

    THREE UNIQUE FAILURES, all on the function A2 above edits, asserted in an
    order that cannot mask the instrument proof: (1) the recovery branch is
    REACHABLE and observable for a genuinely ABSENT sentinel — which is what
    proves A2's digest instrument can see a change at all, and is the one
    legitimate use of the repair path; (2) #1481 guard #2 — a real foreign owner
    is preserved; (3) #1481 guard #1 — a synthetic CALLER writes nothing.
    """
    run.sentinel.unlink(missing_ok=True)
    assert pcs.ensure_sentinel_heartbeat(run.owner, state_path=str(run.sentinel)) is False, (
        "A2f: recovery reported pre-existing health for an absent sentinel."
    )
    recovered = read(run) or {}
    assert recovered.get("recovered") is True and recovered.get("session_id") == run.owner, (
        f"A2f: the recovery branch wrote nothing for an ABSENT sentinel (got "
        f"{recovered!r}); A2's digest instrument is then unproven."
    )

    write(run, ps.sign_state(state_of(run), run.owner))
    before = digest(run.sentinel)
    assert pcs.ensure_sentinel_heartbeat(run.intruder, state_path=str(run.sentinel)) is False, (
        "A2c: the heartbeat claimed health for a sentinel owned by another session."
    )
    assert digest(run.sentinel) == before, (
        "A2c: the heartbeat clobbered a sentinel owned by a different real "
        "session (#1481 guard #2 regressed)."
    )

    assert pcs.ensure_sentinel_heartbeat("stop-3", state_path=str(run.sentinel)) is False, (
        "A2e: a synthetic caller was reported healthy."
    )
    assert digest(run.sentinel) == before, (
        "A2e: a synthetic session id reached the sentinel and would then poison "
        "the resolve_session_id fallback chain (#1481 guard #1 regressed)."
    )


def test_control_identity_less_record_mints_no_authority(run):
    """A5b + A5c (library-route): an identity-less record mints NO authority.

    TWO UNIQUE FAILURES: (1) #1384 — a bare recovery record is not an active
    pipeline; (2) the alignment writer must not MINT authority onto an
    identity-less record. Pre-#1807 the writer re-signed WHATEVER it found — on
    this shape ``sign_state`` with no ``run_id``, i.e. the shared ``"unknown"``
    secret — a laundering oracle that RETURNED TRUE. Issue #1807 REMOVES the
    mint-on-unsigned branch: recording an alignment pass now requires a state that
    is ALREADY validly signed, so an identity-less/unsigned record is REFUSED
    outright with no write. Refusal IS this control's intent. A5c therefore flips
    from "re-signed but non-verifying" to "refused, nothing minted": RED against
    the pre-#1807 baseline (which minted), GREEN against the fix.
    """
    recovery(run)
    assert hook._is_pipeline_active() is False, (
        "A5b: a bare recovery record was classified as an active pipeline (#1384 "
        "regressed)."
    )

    # Fail closed: the write refuses an identity-less/unsigned record rather than
    # re-signing it (the removed laundering oracle). Refusal, no mint, no write.
    assert alignment_classifier._update_pipeline_state(
        run.sentinel,
        session_id=run.owner,
        alignment_passed=True,
        verdict_value="auto_pass",
    ) is False, (
        "A5c control: the alignment write MINTED onto an identity-less record "
        "instead of failing closed."
    )
    minted = read(run) or {}
    assert "hmac" not in minted, (
        "A5c: the alignment write minted a signature onto an identity-less record."
    )
    assert minted.get("alignment_passed") is not True, (
        "A5c: alignment_passed was written onto a record with no run identity."
    )
    assert hook._has_alignment_passed() is False, (
        "A5c: alignment_passed written onto a record with no run identity was "
        "honoured by the alignment gate."
    )


def test_a6_positive_genuine_initialization_progression_and_authority(run, monkeypatch):
    """A6 (positive control, GREEN pre-fix and post-fix, library-route).

    UNIQUE FAILURE: a fix that refuses the real pipeline. ONE end-to-end path
    stands in for every "the sanctioned run still works" assertion in this file —
    run-start receipt, owner-bound signed sentinel, heartbeat no-op, integrity OK,
    both consumers authorize, alignment verdict recordable and still verifying,
    first agent dispatchable, completion credited. Without it, every
    counterfactual above is satisfiable by refusing everything.

    Issue #1807 F3 AMENDMENT: this arm now pins the hook's NATIVE stdin identity to
    the run owner. Pre-F3 it relied on the ``sentinel_self_referential`` fallback
    — authority read from the sentinel's own ``session_id`` when ``_session_id``
    was indeterminate — which was defect 1. A genuine run HAS a native stdin
    identity equal to its owner, so supplying it is what a real run carries, not a
    weakening. The refusal counterpart (native identity ABSENT => refuse) is
    ``test_f3_d1_refuse_absent_native_identity``.

    EVIDENCE LIMIT: ``library-route``. It shows the sanctioned SEQUENCE works
    in-process and says nothing about native-owned hook initialization, which is
    A9's subject and UNMEASURED until the probe script runs in an installed CLI.
    """
    genuine(run)
    # F3: native stdin identity == owner (what a genuine run actually carries).
    monkeypatch.setattr(hook, "_session_id", run.owner, raising=False)
    assert has_receipt(run.owner) is True, (
        "A6: record_run_start left no receipt, so the sanctioned run is "
        "indistinguishable from the A3 forgery and the positive proves nothing."
    )

    before = digest(run.sentinel)
    assert pcs.ensure_sentinel_heartbeat(run.owner, state_path=str(run.sentinel)) is True, (
        "A6: the owning session's heartbeat did not report its sentinel healthy."
    )
    assert digest(run.sentinel) == before, (
        "A6: a healthy sentinel was rewritten on a SubagentStop heartbeat."
    )
    assert pcs.sentinel_integrity(sentinel_path=str(run.sentinel)) is (
        pcs.SentinelIntegrity.OK
    ), "A6: a genuine signed sentinel was not classified OK."

    assert hook._is_pipeline_active() is True, (
        "A6: a sanctioned run lost protected-path authority."
    )
    assert hook._has_alignment_passed() is True, (
        "A6: a sanctioned run's recorded alignment pass stopped passing."
    )

    assert alignment_classifier._update_pipeline_state(
        run.sentinel,
        session_id=run.owner,
        alignment_passed=True,
        verdict_value="auto_pass",
    ) is True, "A6: the alignment verdict could not be recorded into live state."
    assert ps.verify_state_hmac(read(run) or {}, run.owner) is True, (
        "A6: state re-signed by the alignment write no longer verifies for its "
        "owner, so STEP 2 would break every run."
    )

    first = ordering(run.owner, "implementer")
    assert first.passed is True, (
        f"A6: a genuine fix-mode run could not dispatch implementer: {first.reason!r}"
    )
    pcs.record_agent_completion(run.owner, "implementer", success=True, issue_number=1807)
    assert "implementer" not in ordering(run.owner, "reviewer").missing_agents, (
        "A6: a sanctioned run's own implementer completion was not credited — "
        "every fix-mode pipeline would deadlock."
    )


# ===========================================================================
# F3 — the THREE reviewed run-authority defects (Issue #1807, run 90bc90395fad5026)
# ===========================================================================
#
# FREEZE: docs .../scratchpad/f3_frozen_acceptance.md. Authored BEFORE the F3
# repair. They target the residual the F1/F2 fixes did NOT close. The F1/F2 code
# resolves the AUTHORITY caller identity from the ``CLAUDE_SESSION_ID`` env var
# and from the sentinel's OWN ``session_id`` (the ``sentinel_self_referential``
# carrier), and it grants "pipeline active" on agent ROLE alone. All three are
# refused here; authority binds to the session id observed on the hook's own
# NATIVE stdin (``unified_pre_tool._session_id``, set in ``main()`` from the
# Claude Code PreToolUse payload).
#
# EVIDENCE LIMIT — read before quoting any green here as security. These arms
# prove REDUCED spoofability, NOT native provenance. ``CLAUDE_CODE_SESSION_ID`` is
# available to Bash/hooks/MCP and MATCHES the stdin ``session_id`` (Anthropic env
# docs), so the id is MODEL-KNOWABLE and the hook can be driven with hand-crafted
# stdin bearing it — a forged stdin with the known id would still pass the
# identity check. What these arms establish: a sentinel can no longer vouch for
# its own owner (D1a), an env var can no longer substitute for the stdin id
# (D1b/D2-touch), a role alone confers nothing (D2), and a run-bearing but
# unauthorized sentinel no longer free-passes the first implementer (D3). What
# they do NOT establish: authentic native ORIGIN — that is acceptance case A9,
# evidence class ``native-boundary``, OPEN and UNMEASURED (see
# probe_1807_native_origin_split.sh). Evidence class of these arms is
# ``library-route`` (in-process, paths/env redirected), except the two
# ``native_route`` arms which drive the real ``main()`` stdin entrypoint.


def _native(monkeypatch, sid: str) -> None:
    """Pin the session id observed on the hook's OWN native stdin.

    ``main()`` sets ``unified_pre_tool._session_id`` from
    ``input_data['session_id']`` — the one identity an authority decision may
    trust, because the CLI delivers it to this process and model-controlled Bash
    cannot set it. Tests set it directly; a real run gets it from stdin.
    """
    monkeypatch.setattr(hook, "_session_id", sid, raising=False)


# ---------------------------------------------------------------------------
# Defect 1 — authority binds to native stdin, never env nor the sentinel itself
# ---------------------------------------------------------------------------


def test_f3_d1_permit_genuine_same_owner_native_identity(run, monkeypatch):
    """POSITIVE (permit): stdin sid == sentinel owner, signed, receipt present.

    The instrument's yes. Without it every refusal below is satisfiable by a
    consumer hard-wired to say no.
    """
    genuine(run)
    _native(monkeypatch, run.owner)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    assert hook._is_pipeline_active() is True, (
        "D1 permit: a genuine run whose native stdin identity equals the sentinel "
        "owner lost protected-path authority."
    )
    assert hook._has_alignment_passed() is True, (
        "D1 permit: a genuine run's recorded alignment pass stopped passing when "
        "identity came from native stdin."
    )


def test_f3_d1_refuse_absent_native_identity(run, monkeypatch):
    """OPPOSITE (refuse): native stdin identity absent/unqualified => REFUSE.

    UNIQUE FAILURE: the sentinel's OWN ``session_id`` is used as the caller
    identity (``sentinel_self_referential``), so the artifact under examination
    nominates its own examiner and the owner comparison is vacuous. A genuine,
    signed, receipt-backed sentinel is present; the ONLY thing missing is a
    native caller identity, and that alone must refuse.
    """
    genuine(run)
    _native(monkeypatch, "unknown")  # native stdin unresolved
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    assert hook._is_pipeline_active() is False, (
        "D1a: with NO native stdin identity, authority fell back to the "
        "sentinel's own session_id and reported an active pipeline. A sentinel's "
        "session_id must never be treated as proof of its owner."
    )
    assert hook._has_alignment_passed() is False, (
        "D1a: alignment_passed honoured with identity taken from the very "
        "sentinel being judged."
    )


def test_f3_d1_refuse_env_substitutes_for_native(run, monkeypatch):
    """OPPOSITE (refuse): stdin sid != sentinel owner (env spoof) => REFUSE.

    UNIQUE FAILURE, a DIFFERENT shape from the absent case: a DIFFERENT native
    session (``intruder``) presents while ``CLAUDE_SESSION_ID`` is set to the
    genuine owner. ``CLAUDE_SESSION_ID`` is a MODEL-settable export (the #1137
    exception to the #606 prefix guard), so trusting it for authority lets one
    session inherit another's run. ``_is_stale_session`` does NOT catch this —
    env==owner keeps it from firing — so only native-identity binding can.
    """
    genuine(run)
    _native(monkeypatch, run.intruder)  # the REAL current session
    monkeypatch.setenv("CLAUDE_SESSION_ID", run.owner)  # spoof toward the owner

    assert hook._is_pipeline_active() is False, (
        "D1b: CLAUDE_SESSION_ID substituted for the native stdin identity, so a "
        f"session ({run.intruder!r}) inherited another run's ({run.owner!r}) "
        "protected-path authority. The env var must never substitute for the "
        "stdin-observed identity in an authority decision."
    )
    assert hook._has_alignment_passed() is False, (
        "D1b: alignment_passed honoured for a caller whose native identity does "
        "not own the run, because the env var was trusted instead."
    )


# ---------------------------------------------------------------------------
# Defect 2 — agent role alone is not current-run authority
# ---------------------------------------------------------------------------


def test_f3_d2_refuse_role_without_signed_state(run, monkeypatch):
    """OPPOSITE (refuse): role present + signed current-run state missing.

    UNIQUE FAILURE: ``_is_pipeline_active()`` short-circuits to True the instant
    ``_get_active_agent_name()`` is a pipeline role, BEFORE any state is read. A
    bare/namespaced agent name is thus enough to read as an active pipeline with
    no signed run behind it at all.
    """
    run.sentinel.unlink(missing_ok=True)  # no signed current-run state
    monkeypatch.setattr(hook, "_agent_type", "implementer", raising=False)
    _native(monkeypatch, run.owner)

    assert hook._is_pipeline_active() is False, (
        "D2a: CLAUDE_AGENT_NAME/agent_type=implementer alone reported an active "
        "pipeline with NO signed current-run state. Role is not authority."
    )


def test_f3_d2_refuse_role_with_corrupt_state(run, monkeypatch):
    """OPPOSITE (refuse): role present + state corrupt => NOT authorized.

    DIFFERENT shape from the missing-state arm: the file EXISTS but is 0 bytes,
    so its gating fields are unreadable. Role must not paper over that.
    """
    run.sentinel.write_bytes(b"")  # exists, corrupt
    monkeypatch.setattr(hook, "_agent_type", "implementer", raising=False)
    _native(monkeypatch, run.owner)

    assert hook._is_pipeline_active() is False, (
        "D2b: a pipeline role plus a CORRUPT sentinel reported an active "
        "pipeline; a verification failure is 'not passed' (INV-7)."
    )


def test_f3_d2_refuse_role_with_owner_absent_state(run, monkeypatch):
    """OPPOSITE (refuse): role present + owner-absent signed state.

    The owner field is DELETED after signing (the shape fix-mode F1 used to
    write). Role must not confer authority on a state that names no owner.
    """
    ownerless = ps.sign_state(state_of(run), run.owner)
    del ownerless["session_id"]
    write(run, ownerless)
    monkeypatch.setattr(hook, "_agent_type", "implementer", raising=False)
    _native(monkeypatch, run.owner)

    assert hook._is_pipeline_active() is False, (
        "D2c: a pipeline role plus an OWNER-ABSENT signed state reported active; "
        "an absent owner is an unverifiable owner."
    )


def test_f3_d2_permit_role_with_verified_signed_state(run, monkeypatch):
    """POSITIVE (permit): role present + verified signed state + matching owner.

    The instrument's yes for defect 2: a real subagent inside a genuine run —
    pipeline role, signed sentinel, native stdin equal to the owner — stays
    active. Without it the three refusals are satisfiable by a gate that ignores
    the role branch entirely.
    """
    genuine(run)
    monkeypatch.setattr(hook, "_agent_type", "implementer", raising=False)
    _native(monkeypatch, run.owner)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    assert hook._is_pipeline_active() is True, (
        "D2 permit: a genuine run with a dispatched pipeline agent and matching "
        "native owner lost authority."
    )


# ---------------------------------------------------------------------------
# Defect 3 — the first fix-mode implementer requires current-run authority
# ---------------------------------------------------------------------------


def test_f3_d3_block_first_implementer_on_unauthorized_run_bearing_sentinel(run):
    """OPPOSITE (refuse): run-bearing but UNVERIFIED sentinel => BLOCK.

    UNIQUE FAILURE: a run-bearing sentinel (``run_id``, ``mode=fix``,
    ``explicitly_invoked``) that is NOT corroborated by a run-start receipt (the
    A3/A7 self-mint) free-passes the first fix-mode implementer, because
    ``run_credit_refusal`` early-returned on a missing receipt instead of
    classifying the run-bearing sentinel.

    SCOPE NOTE (independent-signal caveat): the /implement "signal" exercised here
    is the sentinel's OWN ``run_id``/``explicitly_invoked`` fields, i.e. the
    artifact under examination vouching for itself. That is a useful UNIT arm for
    the unverified-sentinel case, but it is NOT the frozen independent-signal case
    — see ``test_f3_d3_block_independent_signal_with_signed_state_absent`` for the
    arm whose /implement signal (the run-start receipt) is INDEPENDENT of the
    sentinel being judged.
    """
    forged(run)  # signed, run-bearing, NO receipt
    assert has_receipt(run.owner) is False, (
        "D3 precondition: a receipt exists, so the sentinel is not the "
        "unverified shape this arm needs."
    )

    result = ordering(run.owner, "implementer")

    assert result.passed is False, (
        "D3a: the first fix-mode implementer was dispatched from a run-bearing "
        "but unverified sentinel (signed, no run-start receipt), "
        f"reason={result.reason!r}. A genuine /implement signal without verified "
        "current-run authority must BLOCK, not free-pass."
    )


def test_f3_d3_permit_first_implementer_on_verified_run(run):
    """POSITIVE (permit): genuine /implement signaled + verified authority.

    The instrument's yes: a genuine run (signed + receipt) dispatches its first
    implementer. Without it, D3a is satisfiable by a gate that blocks everything.
    """
    genuine(run)
    assert ordering(run.owner, "implementer").passed is True, (
        "D3 permit: a verified current-run could not dispatch its first "
        "implementer."
    )


def test_f3_d3_control_ordinary_no_run_is_not_gated(run):
    """CONTROL (unchanged): no genuine /implement signal => not gated.

    A session with NO sentinel and NO run claim is ordinary no-run work. The
    fix must not start gating it — this is the negative control that proves D3a
    is not just "block every implementer".
    """
    run.sentinel.unlink(missing_ok=True)

    assert ordering(f"{run.owner}-fresh", "implementer").passed is True, (
        "D3 control: ordinary no-run tool use (no sentinel, no run claim) was "
        "newly gated by the defect-3 fix."
    )


# ---------------------------------------------------------------------------
# Cross-cutting — a valid MAC after a hand write is not native origin
# ---------------------------------------------------------------------------


def test_f3_crosscut_valid_mac_plus_ledger_but_no_native_origin_refused(run, monkeypatch):
    """REFUSE (library-route UNIT arm): both carriers valid, native origin ABSENT.

    BOTH carriers the classifier requires are present and valid — an owner-bound
    HMAC AND a matching run-start receipt — yet no native caller identity is
    available. A valid MAC after a hand write proves a signing-capable API was
    used, not authentic native origin, so the consumer must still refuse. This is
    the forgery framing of D1a with both carriers explicitly verified as the
    ONLY-variable-changed precondition.

    SCOPE NOTE: this calls the consumer helpers IN-PROCESS (``library-route``).
    The frozen cross-cutting case additionally requires the ACTUAL guarded native
    route — the real ``unified_pre_tool.main()`` stdin entrypoint — which is
    exercised by ``test_f3_native_route_refuses_both_carriers_without_native_origin``.
    """
    genuine(run)
    assert has_receipt(run.owner) is True, (
        "crosscut precondition: the ledger carrier is missing, so this is not the "
        "both-carriers-valid shape."
    )
    assert ps.verify_state_hmac(read(run), run.owner) is True, (
        "crosscut precondition: the MAC carrier does not verify, so this is not "
        "the both-carriers-valid shape."
    )

    _native(monkeypatch, "unknown")  # native origin absent on the guarded route
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    assert hook._is_pipeline_active() is False, (
        "crosscut: a valid HMAC plus a matching ledger receipt were honoured as "
        "an active pipeline with NO native caller origin — a signing-capable API "
        "was used, not authentic native origin."
    )
    assert hook._has_alignment_passed() is False, (
        "crosscut: alignment_passed honoured from a hand-writable both-carriers "
        "state with no native origin."
    )


# ---------------------------------------------------------------------------
# Defect 3 — INDEPENDENT /implement signal (steering GAP 1)
# ---------------------------------------------------------------------------
#
# The frozen defect-3 OPPOSITE case requires a /implement signal INDEPENDENT of
# the sentinel being judged. The run-start receipt (``current_run_id`` stamped by
# record_run_start into the completion ledger at STEP 0, BEFORE any agent runs) is
# such a signal: it is a SEPARATE artifact from the sentinel, so a forged sentinel
# cannot mint it by itself. When that independent signal is present but the SIGNED
# sentinel is ABSENT, the first fix-mode implementer must BLOCK.
#
# EVIDENCE LIMIT, stated honestly: the receipt is a WEAK independent signal — it is
# unsigned and lives in a model-writable ``/tmp`` ledger, so a caller willing to
# write both carriers is still authorized at library level (the A9 residual, OPEN
# and UNMEASURED). A cryptographically-authenticated, unspoofable independent
# /implement signal that binds session/run/mode/issue/base-commit/subject does NOT
# exist today; that is A9/native-boundary. This arm proves ONLY that the signal is
# independent of the sentinel-under-examination, not that it proves native origin.


def test_f3_d3_block_independent_signal_with_signed_state_absent(run):
    """OPPOSITE (refuse): INDEPENDENT /implement signal + signed state ABSENT.

    The /implement signal here is the run-start RECEIPT (ledger ``current_run_id``),
    a SEPARATE artifact from the sentinel — the sentinel being judged does not
    vouch for itself. With that independent signal present and NO signed sentinel
    to authorize it, the first fix-mode implementer must BLOCK (A4 ledger-only
    forgery: a retained run id is not run authority).
    """
    pcs.record_run_start(run.owner, run.run_id, issue_number=1807)  # independent signal
    run.sentinel.unlink(missing_ok=True)  # signed state ABSENT
    assert has_receipt(run.owner) is True, (
        "precondition: the independent run-start signal was not written."
    )

    result = ordering(run.owner, "implementer")

    assert result.passed is False, (
        "D3 independent-signal: a ledger run-start (independent of the sentinel) "
        "with NO signed sentinel free-passed the first fix-mode implementer. A "
        f"retained run id is not run authority. reason={result.reason!r}"
    )


# ---------------------------------------------------------------------------
# Cross-cutting on the ACTUAL guarded native route (steering GAP 2)
# ---------------------------------------------------------------------------
#
# The in-process crosscut above calls the consumer helpers directly. This pair
# drives the REAL hook entrypoint — ``unified_pre_tool.main()`` reading its native
# PreToolUse JSON payload from stdin, from which ``_session_id`` is set — and
# asserts a protected-path Write is REFUSED when the stdin ``session_id`` is absent,
# with the ONLY variable being that stdin id. The sentinel/ledger/secret are
# isolated by the ``run`` fixture's redirect (tmp), so no machine-global state is
# touched. A fully out-of-process subprocess is deliberately NOT used: the
# completion ledger path is hardcoded to machine-global ``/tmp`` in
# ``_state_file_path`` (no env override) and a subprocess's ``verify_state_hmac``
# would consult the LIVE legacy sentinel's mtime (#753 fail-open), so a subprocess
# would break the isolation this task is bound by while exercising the SAME
# in-module decision logic.
#
# WHAT THIS PAIR PROVES, STATED HONESTLY: refusal of a hand-written valid-MAC
# sentinel + matching ledger that carries NO matching stdin id — i.e. a
# SENTINEL-FORGERY refusal. It does NOT prove native PROVENANCE: because
# ``CLAUDE_CODE_SESSION_ID`` is model-knowable and equals the stdin id, a forged
# stdin bearing the known id would still pass the identity check. The OS-level
# native ORIGIN boundary (A9, ``native-boundary``) is NOT proven here and stays
# OPEN/UNMEASURED.


def _drive_main(payload: dict):
    """Drive the REAL ``unified_pre_tool.main()`` stdin entrypoint once.

    Returns the list of ``(decision, reason)`` the hook emitted. ``main()`` sets
    ``_session_id`` from ``payload['session_id']`` — the native origin under test.
    """
    import io
    from unittest.mock import patch

    calls = []

    def _capture(decision, reason, **_kw):
        calls.append((decision, reason))
        raise SystemExit(0)

    # main() assigns the module globals _session_id/_agent_type directly (NOT via
    # monkeypatch), so snapshot and restore them here — otherwise the payload's
    # session_id leaks into the next test and trips the `run` fixture's
    # indeterminate-identity assertion.
    saved_sid = getattr(hook, "_session_id", "unknown")
    saved_agent = getattr(hook, "_agent_type", "")
    try:
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
            with patch.object(hook, "output_decision", side_effect=_capture):
                try:
                    hook.main()
                except SystemExit:
                    pass
    finally:
        hook._session_id = saved_sid
        hook._agent_type = saved_agent
    return calls


def _protected_target() -> str:
    """A repo code path the workflow gate protects when no pipeline is active."""
    return str(_REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "f3_native_probe_1807.py")


def _denied_for_no_pipeline(calls) -> bool:
    return any(d == "deny" and "/implement pipeline" in r for d, r in calls)


def test_f3_native_route_refuses_both_carriers_without_native_origin(run):
    """REFUSE on the REAL native route: SENTINEL-FORGERY refusal (not provenance).

    A hand-built both-carriers-valid run (valid MAC + matching run-start receipt)
    is presented to the actual ``main()`` stdin entrypoint via a protected-path
    Write, with the stdin ``session_id`` ABSENT. The write must be DENIED because
    ``_is_pipeline_active()`` binds to the stdin id, which is absent.

    SCOPE, stated honestly: this asserts refusal of a hand-written sentinel+ledger
    that lacks a matching stdin id — a SENTINEL-FORGERY refusal. It does NOT prove
    native provenance: ``CLAUDE_CODE_SESSION_ID`` is model-knowable and equals the
    stdin id, so a forged stdin bearing the known id would still pass the identity
    check (A9, OPEN/UNMEASURED).
    """
    genuine(run)  # both carriers valid, hand-built via the public APIs
    assert has_receipt(run.owner) is True
    assert ps.verify_state_hmac(read(run), run.owner) is True

    payload = {
        "tool_name": "Write",
        # native origin ABSENT: no session_id in the stdin payload
        "tool_input": {"file_path": _protected_target(), "content": "x = 1\n"},
    }
    calls = _drive_main(payload)

    assert _denied_for_no_pipeline(calls), (
        "native route: both carriers valid but the stdin payload carried NO native "
        f"session_id, yet the protected-path write was not refused. calls={calls!r}"
    )


def test_f3_native_route_permits_with_native_origin_present(run):
    """CONTROL for the native route: same state, native origin PRESENT.

    The ONLY variable changed from the refuse arm is the stdin ``session_id``
    (native origin = the run owner). The protected-path write must NOT be refused
    with the pipeline-inactive reason — proving the refuse above is caused by the
    absent native origin, not by an always-deny harness.
    """
    genuine(run)

    payload = {
        "tool_name": "Write",
        "session_id": run.owner,  # native origin PRESENT and equal to the owner
        "tool_input": {"file_path": _protected_target(), "content": "x = 1\n"},
    }
    calls = _drive_main(payload)

    assert not _denied_for_no_pipeline(calls), (
        "native route control: native origin equals the run owner, yet the write "
        f"was still refused for 'no pipeline'. calls={calls!r}"
    )


# ---------------------------------------------------------------------------
# Defect 2 — mtime refresh must key on native identity (steering points 2b/3)
# ---------------------------------------------------------------------------


def test_f3_d2_same_owner_heartbeat_refreshes(run, monkeypatch):
    """PERMIT (refresh): a genuine same-owner heartbeat refreshes its sentinel.

    The legitimate #636/#941 case must survive the tightening: agent role present,
    signed state owned by the native session, native identity == owner. The
    sentinel mtime is bumped from an old value toward now.
    """
    genuine(run)
    old = time.time() - 1200  # 20 min ago, within TTL but stale enough to see a bump
    os.utime(run.sentinel, (old, old))
    monkeypatch.setattr(hook, "_agent_type", "implementer", raising=False)
    _native(monkeypatch, run.owner)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    assert hook._is_pipeline_active() is True, "same-owner genuine run went inactive"
    assert (time.time() - run.sentinel.stat().st_mtime) < 30, (
        "same-owner heartbeat did NOT refresh its own sentinel mtime — the "
        "legitimate #636/#941 refresh regressed."
    )


def test_f3_d2_spoofed_env_cannot_refresh_foreign_state(run, monkeypatch):
    """REFUSE (no refresh): a spoofed env must not refresh FOREIGN state.

    Native identity is a DIFFERENT session; ``CLAUDE_SESSION_ID`` is spoofed to
    the owner. The mtime-touch must key on native identity, so the foreign-owned
    sentinel's mtime is NOT refreshed and the run is NOT reported active.
    """
    genuine(run)
    old = time.time() - 1200
    os.utime(run.sentinel, (old, old))
    monkeypatch.setattr(hook, "_agent_type", "implementer", raising=False)
    _native(monkeypatch, run.intruder)  # real current session, not the owner
    monkeypatch.setenv("CLAUDE_SESSION_ID", run.owner)  # spoof toward the owner

    assert hook._is_pipeline_active() is False, (
        "a spoofed CLAUDE_SESSION_ID plus a pipeline role reported a foreign run "
        "as active."
    )
    assert (time.time() - run.sentinel.stat().st_mtime) > 60, (
        "a spoofed env refreshed a FOREIGN session's sentinel mtime, keeping "
        "someone else's run state alive."
    )


# ---------------------------------------------------------------------------
# Run-bearing-but-unqualified FAIL-CLOSED chokepoint (Issue #1807 fail-open guard)
# ---------------------------------------------------------------------------
#
# Making _is_pipeline_active() return False on an unqualified native id would, on
# its own, SKIP every downstream `if _is_pipeline_active(): <deny>` gate and PERMIT
# a protected mutation during a live run. The main() chokepoint closes that whole
# class: run detected (_run_transition_detected) + not authority-qualified
# (_is_pipeline_active False) => every guarded mutation is DENIED. These arms drive
# the REAL main() entrypoint per transport, plus the helper unit arms with their
# opposite/control cases. EVIDENCE LIMIT: this is spoofability reduction on the
# read side; native provenance (A9) stays OPEN.


def _main_decision(payload: dict) -> str:
    """Return just the ``main()`` decision string for *payload*."""
    calls = _drive_main(payload)
    return calls[-1][0] if calls else "<none>"


def _run_bearing_unqualified(run, monkeypatch):
    """Set up: a run-bearing sentinel present + NO native identity (unqualified)."""
    forged(run)  # signed, run_id present (run-bearing), NO run-start receipt
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    # native stdin identity stays indeterminate (the `run` fixture pins it), and
    # _drive_main leaves the payload session_id absent unless we add it.


# ---- helper unit arms: _run_transition_detected ----

def test_f3_rt_absent_sentinel_is_no_run(run):
    """CONTROL: a genuinely ABSENT sentinel is ordinary no-run => False."""
    run.sentinel.unlink(missing_ok=True)
    assert hook._run_transition_detected() is False


def test_f3_rt_present_run_bearing_is_detected(run):
    """A present, fresh, run-bearing sentinel => transition detected (True)."""
    forged(run)
    assert hook._run_transition_detected() is True


def test_f3_rt_present_but_corrupt_is_detected_failclosed(run):
    """OPPOSITE (fail closed): a present-but-corrupt sentinel => detected (True).

    A 0-byte sentinel during a run must route the unqualified caller to the deny
    gate, not be read as "no run" (which would skip it)."""
    run.sentinel.write_bytes(b"")
    assert hook._run_transition_detected() is True


def test_f3_rt_present_empty_dict_is_detected_failclosed(run):
    """OPPOSITE (fail closed): a fresh present ``{}`` => detected (True).

    Content-independence: run-detection must NOT gate on run identity, or a
    present-but-identity-less sentinel would SKIP the chokepoint (a fail-open).
    The run-identity distinction belongs to the authority check downstream."""
    run.sentinel.write_text("{}", encoding="utf-8")
    assert hook._run_transition_detected() is True


def test_f3_rt_present_identity_less_dict_is_detected_failclosed(run):
    """OPPOSITE (fail closed): a fresh identity-less breadcrumb => detected (True)."""
    run.sentinel.write_text(
        json.dumps({"session_id": run.owner, "recovered": True, "recovered_at": "now"}),
        encoding="utf-8",
    )
    assert hook._run_transition_detected() is True


# ---- helper unit arms: _is_guarded_mutation ----

def test_f3_gm_editor_write_is_guarded(run):
    """Editor write transport => guarded mutation."""
    assert hook._is_guarded_mutation("Write", {"file_path": "a.py", "content": "x"}) is True
    assert hook._is_guarded_mutation("Edit", {"file_path": "a.py", "old_string": "a", "new_string": "b"}) is True


def test_f3_gm_bash_git_commit_and_settings_are_guarded(run):
    """Bash effects (is_write is EXEC for Bash) => guarded via the shell path."""
    assert hook._is_guarded_mutation("Bash", {"command": "git" + " commit -m x"}) is True
    assert hook._is_guarded_mutation(
        "Bash", {"command": "echo '{}' > .claude/settings.json"}
    ) is True


def test_f3_gm_malformed_mcp_write_shaped_is_guarded(run):
    """OPPOSITE: a write-shaped MCP payload is_write may miss => backstop guards it."""
    assert hook._is_guarded_mutation(
        "mcp__serena__replace_symbol_body", {"body": "def f(): pass"}
    ) is True


def test_f3_gm_read_only_is_not_guarded(run):
    """CONTROL: read-only tools are not mutations."""
    assert hook._is_guarded_mutation("Read", {"file_path": "a.py"}) is False
    assert hook._is_guarded_mutation("Bash", {"command": "ls -la"}) is False


# ---- chokepoint main() arms, per transport ----

def test_f3_chokepoint_denies_editor_write_run_bearing_unqualified(run, monkeypatch):
    """DENY: editor write, run detected, unqualified native => fail closed."""
    _run_bearing_unqualified(run, monkeypatch)
    decision = _main_decision({
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/repo/file.py", "content": "x = 1\n"},
    })
    assert decision == "deny", (
        "editor write during a run-bearing transition with no native identity "
        "was not denied (fail-open)."
    )


def test_f3_chokepoint_denies_mcp_editor_run_bearing_unqualified(run, monkeypatch):
    """DENY: MCP editor write => fail closed (transport-independent)."""
    _run_bearing_unqualified(run, monkeypatch)
    decision = _main_decision({
        "tool_name": "mcp__serena__replace_symbol_body",
        "tool_input": {"name_path": "C/m", "body": "def m(self): pass"},
    })
    assert decision == "deny", "MCP editor write was not denied during unqualified run."


def test_f3_chokepoint_denies_bash_git_commit_run_bearing_unqualified(run, monkeypatch):
    """DENY: Bash git-commit (completeness route) => fail closed."""
    _run_bearing_unqualified(run, monkeypatch)
    decision = _main_decision({
        "tool_name": "Bash",
        "tool_input": {"command": "git" + " commit -m 'x'"},
    })
    assert decision == "deny", "Bash git-commit was not denied during unqualified run."


def test_f3_chokepoint_denies_bash_settings_write_run_bearing_unqualified(run, monkeypatch):
    """DENY: Bash settings.json write (settings route) => fail closed."""
    _run_bearing_unqualified(run, monkeypatch)
    decision = _main_decision({
        "tool_name": "Bash",
        "tool_input": {"command": "echo '{}' > .claude/settings.json"},
    })
    assert decision == "deny", "Bash settings write was not denied during unqualified run."


def test_f3_chokepoint_denies_present_but_corrupt_sentinel(run, monkeypatch):
    """DENY: present-but-corrupt sentinel + editor write => fail closed."""
    run.sentinel.write_bytes(b"")  # corrupt, fresh
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    decision = _main_decision({
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/repo/file.py", "content": "x = 1\n"},
    })
    assert decision == "deny", (
        "a corrupt sentinel during a transition did not fail closed for a write."
    )


def test_f3_chokepoint_denies_identity_less_sentinel(run, monkeypatch):
    """DENY: a fresh identity-less sentinel + editor write => fail closed.

    OPPOSITE of the run-identity-gated fail-open: a present breadcrumb (or ``{}``)
    that carries no run identity is still a live transition; an unqualified caller
    must be DENIED, not skipped."""
    run.sentinel.write_text(
        json.dumps({"session_id": run.owner, "recovered": True, "recovered_at": "now"}),
        encoding="utf-8",
    )
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    decision = _main_decision({
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/repo/file.py", "content": "x = 1\n"},
    })
    assert decision == "deny", (
        "an identity-less sentinel during a transition did not fail closed for a "
        "write (run-detection wrongly gated on run identity)."
    )


def test_f3_chokepoint_denies_on_injected_detector_error(run, monkeypatch):
    """INJECTED-ERROR (fail closed): a detector raising with a sentinel present
    must DENY, never fall through to the skip-prone gates."""
    forged(run)  # run-bearing sentinel present
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    def _boom(*_a, **_k):
        raise RuntimeError("injected classifier failure")

    monkeypatch.setattr(hook, "_is_guarded_mutation", _boom, raising=False)
    decision = _main_decision({
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/repo/file.py", "content": "x = 1\n"},
    })
    assert decision == "deny", (
        "the chokepoint fell through (permit) when its classifier raised while a "
        "sentinel was present — that is the fail-open the chokepoint must close."
    )


def test_f3_chokepoint_control_ordinary_no_run_editor_write_allowed(run, monkeypatch):
    """CONTROL: no sentinel (ordinary no-run) => native editor write NOT gated.

    Proves the chokepoint does not gate normal non-pipeline work — the deciding
    variable is the presence of a run-bearing transition, not the write itself."""
    run.sentinel.unlink(missing_ok=True)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    decision = _main_decision({
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/repo/file.py", "content": "x = 1\n"},
    })
    assert decision != "deny", (
        "ordinary no-run editor write was gated by the chokepoint (over-block)."
    )


def test_f3_chokepoint_control_run_bearing_read_not_gated(run, monkeypatch):
    """CONTROL: run detected + unqualified, but a READ is not a mutation => not gated."""
    _run_bearing_unqualified(run, monkeypatch)
    decision = _main_decision({
        "tool_name": "Read",
        "tool_input": {"file_path": "/some/repo/file.py"},
    })
    assert decision != "deny", "a read-only tool was gated by the mutation chokepoint."


# ---------------------------------------------------------------------------
# Credential-leak-on-denial (Issue #1822, F4 cycle 2)
# ---------------------------------------------------------------------------
#
# The chokepoint's Bash deny path must NOT write raw command text to
# .claude/logs/deviations.jsonl — a command embedding a literal credential would
# leak the secret into the on-disk evidence log on denial. The deny-log subject
# for Bash must be the CONSTANT "bash_command" (matching the sibling #528 path).


def test_f3_chokepoint_bash_deny_does_not_leak_credential_to_deviations_log(
    run, monkeypatch, tmp_path
):
    """FROZEN NEGATIVE (#1822): a denied Bash mutation whose command embeds a
    canary credential must be DENIED, must not mutate authority state, and must
    NOT write the canary into deviations.jsonl. Control: the fixed subject IS
    logged, proving logging still happens without the secret.
    """
    import uuid

    # Isolate the deviations log so we can inspect exactly what was written.
    logs_dir = tmp_path / "isolated_logs_1822"
    logs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(hook, "_resolved_logs_dir", lambda: logs_dir, raising=False)

    # Genuine run present (receipt + signed sentinel) but caller UNqualified
    # (no native identity) => the chokepoint denies guarded mutations.
    genuine(run)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    receipt_before = pcs.get_run_start_receipt(run.owner)
    sentinel_before = digest(run.sentinel)
    assert receipt_before == run.run_id  # precondition: authority state is present

    canary = f"CANARY_TOKEN_1807_{uuid.uuid4().hex}"
    # A guarded Bash mutation (file write) whose command embeds the secret directly.
    command = f"echo '{canary}' > /some/repo/injected_secret_config.py"
    decision = _main_decision({"tool_name": "Bash", "tool_input": {"command": command}})

    # (1) refusal intact — the redaction fix does not weaken the block.
    assert decision == "deny", (
        f"the chokepoint did not deny the guarded Bash mutation: {decision!r}"
    )

    # (2) authority state (receipt + sentinel) unchanged by the denial.
    assert pcs.get_run_start_receipt(run.owner) == receipt_before
    assert digest(run.sentinel) == sentinel_before

    # (3) the canary secret is ABSENT from the deviations log content.
    dev_log = logs_dir / "deviations.jsonl"
    content = dev_log.read_text(encoding="utf-8") if dev_log.exists() else ""
    assert canary not in content, (
        "SECRET LEAK: the canary credential embedded in the Bash command was "
        f"written to deviations.jsonl. Log content:\n{content}"
    )

    # Control: logging DID happen, with the constant subject (no secret).
    assert "bash_command" in content, (
        "the deny was not logged at all — the redaction must keep logging, just "
        f"without the command text. Log content:\n{content!r}"
    )
    assert "run_transition_unqualified_native" in content
