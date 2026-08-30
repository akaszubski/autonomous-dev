"""Run-id stamping and current-run filtering in ``pipeline_completion_state``.

Covers the confused-deputy defect: the agent-completeness gate keyed
completions by SESSION, so a SECOND ``/implement`` run inside the same session
inherited the authority the FIRST run earned. A run in which zero agents had
executed read as "all five required agents completed".

**Why this file is separate from ``test_pipeline_completion_state_run_id.py``.**
Every writer in that file passes ``run_id=`` to ``record_agent_completion``.
ZERO production call sites do — the ``run_id=`` kwarg selects a *different
physical state file* (``/tmp/pipeline_agent_completions_{run_id}.json``) that
no production writer ever populates. Tests written in that shape construct both
sides of their own assertion and cannot fail. Folding these tests in there would
invite copying that shape.

**Hard constraint enforced throughout this file:**

1. Every writer uses the PRODUCTION call shape — no ``run_id=`` kwarg.
2. Every two-run test binds two distinct ``uuid4``-derived literals and asserts
   ``run_a != run_b`` before exercising anything. A fixture whose "current" and
   "recorded" run ids are the same literal cannot fail and is forbidden.

Policy table under test:

===== ================================================= =====================
State  Condition                                         Behaviour
===== ================================================= =====================
(a1)   no ``current_run_id``, no ``completion_run_ids``  permissive, silent
(a2)   no ``current_run_id``, stamps present            refuse, loud stderr
(b)    ``current_run_id`` set, record unstamped         excluded
(c)    ``current_run_id`` set, stamp != current         excluded
(d)    stamp == current                                 included
===== ================================================= =====================

Issues: #1045
"""

import fcntl
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as P  # noqa: E402
from pipeline_completion_state import (  # noqa: E402
    _read_state,
    _state_file_path,
    get_completed_agents,
    record_agent_completion,
    record_pytest_gate_passed,
    record_run_start,
    verify_pipeline_agent_completions,
)

# The five agents ``get_required_agents("fix", ...)`` demands. Bound here so a
# change to the required set surfaces as a readable failure rather than a
# mystery empty-diff.
FIX_MODE_REQUIRED = frozenset(
    {
        "continuous-improvement-analyst",
        "doc-master",
        "implementer",
        "pytest-gate",
        "reviewer",
    }
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def sid() -> str:
    """Per-test unique session id.

    ``/tmp`` state is process-global and is NOT cleared between pytest
    invocations, so a fixed literal would let a leaked file from an earlier run
    poison this one.
    """
    return f"test-1045-stamp-{os.getpid()}-{time.time_ns()}-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def run_a() -> str:
    """First run id. Distinct from :func:`run_b` by construction (uuid4)."""
    return f"runA-{uuid.uuid4().hex}"


@pytest.fixture()
def run_b() -> str:
    """Second run id. Distinct from :func:`run_a` by construction (uuid4)."""
    return f"runB-{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
def isolate_gate_environment(monkeypatch, tmp_path):
    """Remove ambient influences that would make these assertions unfalsifiable.

    Three sources of cross-test / cross-process contamination:

    1. ``SKIP_AGENT_COMPLETENESS_GATE`` — makes ``verify_pipeline_agent_completions``
       return ``(True, set(), set())`` unconditionally, so a refusal test could
       never observe a refusal.
    2. ``/tmp/skip_agent_completeness_gate`` — the file-based one-shot bypass.
       Re-pointed at a nonexistent path under ``tmp_path`` rather than deleted,
       because ``_check_file_bypass`` CONSUMES the real file and deleting a
       maintainer's live bypass from a test would be a side effect.
    3. The ``'unknown'``-session merge — reads a process-global
       ``/tmp`` file that real pipeline runs write. Disabled here by pinning
       the staleness TTL to 0; no test in this file exercises that merge.
    """
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)
    monkeypatch.delenv("SKIP_PYTEST_GATE", raising=False)
    monkeypatch.setattr(P, "SKIP_GATE_FILE", tmp_path / "no-such-bypass-file")
    monkeypatch.setattr(P, "STALE_UNKNOWN_TTL_SECONDS", 0)
    yield


@pytest.fixture(autouse=True)
def cleanup_state(sid):
    """Remove this test's state and lock files, whatever the outcome."""
    try:
        yield
    finally:
        _purge(sid)


def _purge(session_id: str) -> None:
    """Delete the session-hashed state file and its sibling lockfile."""
    path = _state_file_path(session_id)
    try:
        path.unlink(missing_ok=True)
        path.with_suffix(".lock").unlink(missing_ok=True)
    except OSError:
        pass


def _record_five(session_id: str) -> None:
    """Record the five fix-mode agents using the PRODUCTION writer shape."""
    for agent in sorted(FIX_MODE_REQUIRED):
        if agent == "pytest-gate":
            record_pytest_gate_passed(session_id)
        else:
            record_agent_completion(session_id, agent)


def _strip_current_run_id(session_id: str) -> None:
    """Delete ``current_run_id`` from the on-disk state, leaving stamps intact.

    This is the only way to construct policy state (a2): the writer refuses to
    stamp when ``current_run_id`` is falsy, so "stamps present, current absent"
    is unreachable through the public API and is therefore a corruption-only
    signal.
    """
    path = _state_file_path(session_id)
    state = json.loads(path.read_text())
    assert "current_run_id" in state, "precondition: run start must have been recorded"
    assert state.get("completion_run_ids"), "precondition: stamps must be present"
    del state["current_run_id"]
    path.write_text(json.dumps(state))


# --------------------------------------------------------------------------- #
# 1. (d) positive arm
# --------------------------------------------------------------------------- #


def test_current_run_agents_are_credited(sid, run_a) -> None:
    """(d): agents recorded during the current run satisfy the gate."""
    assert record_run_start(sid, run_a) is True

    _record_five(sid)

    passed, completed, missing = verify_pipeline_agent_completions(
        sid, "fix", issue_number=0
    )
    assert passed is True, f"current-run agents must be credited; missing={missing}"
    assert missing == set()
    assert FIX_MODE_REQUIRED <= completed, (
        f"expected all of {sorted(FIX_MODE_REQUIRED)}, got {sorted(completed)}"
    )


# --------------------------------------------------------------------------- #
# 2. (c) negative arm — THE DEFECT
# --------------------------------------------------------------------------- #


def test_second_run_does_not_inherit_first_runs_authority(sid, run_a, run_b) -> None:
    """(c) THE DEFECT: run B must not be credited with run A's agents.

    Confused deputy: before this change the gate believed run B held authority
    that only run A earned. Observed in production — a spec-validator was
    stopped mid-run and the gate still read satisfied.
    """
    assert run_a != run_b, "two-run test requires two distinct run ids"

    # RUN A: full pipeline, all five agents recorded (production writer shape).
    assert record_run_start(sid, run_a) is True
    _record_five(sid)
    passed_a, _, _ = verify_pipeline_agent_completions(sid, "fix", issue_number=0)
    assert passed_a is True, "precondition: run A must satisfy the gate"

    # RUN B: same session, brand new run, ZERO agents executed.
    assert record_run_start(sid, run_b) is True

    passed_b, completed_b, missing_b = verify_pipeline_agent_completions(
        sid, "fix", issue_number=0
    )
    assert passed_b is False, (
        "run B executed zero agents but the gate passed — run B inherited run "
        f"A's authority. completed={sorted(completed_b)}"
    )
    assert missing_b == set(FIX_MODE_REQUIRED), (
        f"all five agents must be reported missing for run B, got {sorted(missing_b)}"
    )
    assert completed_b == set(), (
        f"run B must have zero credited agents, got {sorted(completed_b)}"
    )


# --------------------------------------------------------------------------- #
# 3. (b) prior/non-pipeline unstamped records
# --------------------------------------------------------------------------- #


def test_unstamped_records_excluded_once_a_run_is_current(sid, run_a) -> None:
    """(b): records written before any ``record_run_start`` are excluded.

    An unstamped record carries no evidence that it belongs to the current run,
    so once the run has an identity the record cannot be credited to it.
    """
    record_agent_completion(sid, "implementer")
    record_agent_completion(sid, "reviewer")
    assert get_completed_agents(sid) == {"implementer", "reviewer"}, (
        "precondition: legacy unstamped records are visible before run start"
    )

    assert record_run_start(sid, run_a) is True

    assert get_completed_agents(sid) == set(), (
        "unstamped legacy records must not be credited to the current run"
    )


# --------------------------------------------------------------------------- #
# 4. (a1) permissive, silent
# --------------------------------------------------------------------------- #


def test_no_run_identity_is_permissive_and_silent(sid, capsys) -> None:
    """(a1): no ``current_run_id`` and no stamps behaves exactly as before.

    This is the pre-migration state file and the non-``/implement`` session.
    Asserts BOTH arms of the requirement: the completed set is unchanged, and
    nothing is written to stderr (a warning here would fire on every ordinary
    non-pipeline session).
    """
    _record_five(sid)
    capsys.readouterr()  # discard anything emitted during recording

    completed = get_completed_agents(sid)
    passed, _, missing = verify_pipeline_agent_completions(sid, "fix", issue_number=0)

    assert completed == set(FIX_MODE_REQUIRED), (
        f"(a1) must be byte-identical to pre-change behaviour, got {sorted(completed)}"
    )
    assert passed is True and missing == set()

    state = _read_state(sid)
    assert "current_run_id" not in state
    assert not state.get("completion_run_ids"), (
        "the writer must not stamp when current_run_id is absent — that is what "
        "makes stamps-without-current a corruption-only signal"
    )

    err = capsys.readouterr().err
    assert "[pipeline_completion_state]" not in err, (
        f"(a1) is the ordinary case and MUST be silent; got stderr: {err!r}"
    )


# --------------------------------------------------------------------------- #
# 5. (a2) refusal, with (a1) as the negative control
# --------------------------------------------------------------------------- #


def test_lost_run_id_with_stamps_present_refuses_loudly(sid, run_a, capsys) -> None:
    """(a2): stamps present but ``current_run_id`` gone -> refuse, loudly.

    ``_record_completion_run_ids`` only writes a stamp when ``current_run_id``
    is set, so this combination is unreachable through the public API and can
    only mean the run id was LOST. Crediting those records would credit an
    unknown run. Recoverable via the documented audited bypass, so it cannot
    deadlock.

    Negative control (below): state (a1) differs from (a2) ONLY in the presence
    of ``completion_run_ids`` and must NOT refuse.
    """
    assert record_run_start(sid, run_a) is True
    _record_five(sid)
    _strip_current_run_id(sid)
    capsys.readouterr()

    completed = get_completed_agents(sid)
    passed, _, missing = verify_pipeline_agent_completions(sid, "fix", issue_number=0)

    assert completed == set(), f"(a2) must credit nothing, got {sorted(completed)}"
    assert passed is False, "(a2) must refuse"
    assert missing == set(FIX_MODE_REQUIRED)

    err = capsys.readouterr().err
    assert "SKIP_AGENT_COMPLETENESS_GATE" in err, (
        f"(a2) refusal must name the documented recovery; got stderr: {err!r}"
    )


def test_a1_negative_control_does_not_refuse(sid, capsys) -> None:
    """Negative control for (a2): same helper, no stamps -> permissive, silent.

    Differs from ``test_lost_run_id_with_stamps_present_refuses_loudly`` in
    exactly one bit: whether ``completion_run_ids`` is present. Without this
    control the (a2) refusal is indistinguishable from a guard that refuses
    everything.
    """
    from pipeline_completion_state import _filter_to_current_run

    agents = {"implementer", "reviewer"}

    a1_state = {"completions": {"0": {"implementer": True, "reviewer": True}}}
    a2_state = dict(a1_state)
    a2_state["completion_run_ids"] = {"0": {"implementer": "some-lost-run"}}

    capsys.readouterr()
    assert _filter_to_current_run(a1_state, "0", set(agents)) == agents, (
        "(a1) must pass every agent through untouched"
    )
    a1_err = capsys.readouterr().err
    assert a1_err == "", f"(a1) must be silent, got {a1_err!r}"

    assert _filter_to_current_run(a2_state, "0", set(agents)) == set(), (
        "(a2) must exclude every record"
    )
    a2_err = capsys.readouterr().err
    assert "SKIP_AGENT_COMPLETENESS_GATE" in a2_err, (
        f"(a2) must report loudly, got {a2_err!r}"
    )


# --------------------------------------------------------------------------- #
# 6. Concurrency — the documented fail-open lock branch
# --------------------------------------------------------------------------- #


def _classify_state(state: dict) -> str:
    """Map an on-disk state dict onto a policy-table state name."""
    if not state.get("current_run_id"):
        return "a2" if state.get("completion_run_ids") else "a1"
    return "d"


RACE_AGENTS = ("implementer", "reviewer", "doc-master")


def _race_round(session_id: str, run_id: str) -> tuple[str, frozenset, int]:
    """Start a run concurrently with three completions.

    Returns:
        ``(policy_state, credited_agents, surviving_completion_count)``. The
        third element is how many of the three completions survived to disk —
        the lock's job. Lost updates show up there, run attribution shows up in
        the first two.
    """
    agents = RACE_AGENTS
    barrier = threading.Barrier(1 + len(agents))
    errors: list[BaseException] = []

    def _guarded(fn):
        def _run() -> None:
            try:
                barrier.wait(timeout=10)
                fn()
            except BaseException as exc:  # noqa: BLE001 - surfaced via assert below
                errors.append(exc)

        return _run

    threads = [threading.Thread(target=_guarded(lambda: record_run_start(session_id, run_id)))]
    threads += [
        threading.Thread(target=_guarded(lambda a=a: record_agent_completion(session_id, a)))
        for a in agents
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    assert not errors, f"worker raised: {errors!r}"
    assert not any(t.is_alive() for t in threads), "worker deadlocked"

    state = _read_state(session_id)
    survivors = state.get("completions", {}).get("0", {})
    return (
        _classify_state(state),
        frozenset(get_completed_agents(session_id)),
        len(survivors),
    )


def test_locked_rmw_intact_loses_no_completion_and_always_reaches_state_d(
    sid, run_a
) -> None:
    """Positive control for the fail-open race test.

    With ``flock`` working, the four concurrent mutations are SERIALIZED, so:

    * every one of the three completions survives to disk (no lost updates), and
    * ``current_run_id`` survives, i.e. the outcome is always policy state (d).

    How MANY agents end up credited is NOT asserted, and must not be: the four
    threads are serialized but their order is arbitrary, so a completion that
    happens to win the lock before ``record_run_start`` is legitimately
    unstamped and legitimately excluded by policy (b). An earlier draft of this
    test asserted "all three credited" and failed on the first round for exactly
    that reason — the assertion was wrong, not the code.

    Without this control the broken-lock arm below proves nothing: an
    implementation that always lost updates would look identical.
    """
    for i in range(15):
        session = f"{sid}-ctl-{i}"
        try:
            state, credited, survivors = _race_round(session, run_a)
            assert state == "d", f"round {i}: expected (d) with lock held, got ({state})"
            assert survivors == len(RACE_AGENTS), (
                f"round {i}: the lock must lose no update; only {survivors} of "
                f"{len(RACE_AGENTS)} completions survived"
            )
            stamps = _read_state(session).get("completion_run_ids", {}).get("0", {})
            for agent in credited:
                assert stamps.get(agent) == run_a, (
                    f"round {i}: credited {agent!r} stamped {stamps.get(agent)!r}"
                )
        finally:
            _purge(session)


def test_fail_open_lock_race_never_credits_an_unstamped_record(
    sid, run_a, monkeypatch
) -> None:
    """Under ``_locked_rmw``'s documented fail-open branch, the filter stays SOUND.

    ``_locked_rmw`` drops to an UNSERIALIZED read-modify-write when ``flock``
    fails (typically NFS). Only ``LOCK_EX`` is broken here — ``_read_state``
    takes ``LOCK_SH``, and failing that would make every read return ``{}``
    and destroy the state rather than race it.

    **Measured, and contrary to the plan brief.** The brief required asserting
    the outcome is "(d) or (a2), never (a1)". That is false: across 40
    interleavings, 27 landed in (a1) and 13 in (d); (a2) never occurred. The
    unlocked path loses updates in BOTH directions — a completion write can
    clobber the ``current_run_id`` written microseconds earlier. Asserting
    "never (a1)" would be red, and flaky-red at that.

    What DOES hold, and is asserted here, is the property the filter itself
    enforces rather than the lock: whenever the run has an identity (state (d)),
    every credited agent carries a stamp equal to it. Lost updates cost
    COMPLETENESS (an agent silently drops out) but never SOUNDNESS (a foreign
    run's agent is never credited). Contrast the control above, where the lock
    guarantees completeness too.

    The reachability of (a1) is recorded as an ACCEPTED RESIDUAL: it degrades
    the gate to pre-#1045 permissive behaviour, identical to the residual
    characterized in ``test_record_run_start_failure_degrades_to_permissive``.
    If the fail-open branch is ever made safe, this assertion goes red on
    purpose so the change is made deliberately.
    """
    real_flock = fcntl.flock

    def only_shared_locks_work(fd, operation):
        if operation & fcntl.LOCK_EX:
            raise OSError("simulated NFS flock failure (LOCK_EX)")
        return real_flock(fd, operation)

    monkeypatch.setattr(P.fcntl, "flock", only_shared_locks_work)

    observed: set[str] = set()
    lost_update_seen = False
    for i in range(60):
        session = f"{sid}-race-{i}"
        try:
            state, credited, survivors = _race_round(session, run_a)
            observed.add(state)
            lost_update_seen = lost_update_seen or survivors < len(RACE_AGENTS)

            if state == "d":
                stamps = _read_state(session).get("completion_run_ids", {}).get("0", {})
                for agent in credited:
                    assert stamps.get(agent) == run_a, (
                        f"round {i}: SOUNDNESS VIOLATED — credited {agent!r} whose "
                        f"stamp is {stamps.get(agent)!r}, not the current run {run_a!r}"
                    )
            elif state == "a1":
                assert not _read_state(session).get("completion_run_ids"), (
                    f"round {i}: classified (a1) but stamps are present"
                )
            else:  # a2
                assert credited == set(), f"round {i}: (a2) must credit nothing"
        finally:
            _purge(session)

        if lost_update_seen and "a1" in observed:
            break

    assert lost_update_seen, (
        "expected the UNLOCKED read-modify-write to lose at least one completion "
        "across 60 interleavings — the control above proves the locked path "
        "loses none, so seeing no loss here means the fail-open branch was not "
        "actually taken and this test proved nothing."
    )
    assert "a1" in observed, (
        "expected the fail-open branch to lose at least one current_run_id write "
        f"across 60 interleavings (measured ~27/40); observed states={sorted(observed)}. "
        "If the fail-open race has been fixed, delete this assertion deliberately."
    )


# --------------------------------------------------------------------------- #
# 7. Silent stamp failure — accepted residual
# --------------------------------------------------------------------------- #


def test_record_run_start_failure_degrades_to_permissive(sid, monkeypatch, capsys) -> None:
    """``record_run_start`` never raises; it reports False and degrades to (a1).

    Characterization of an ACCEPTED RESIDUAL, not an endorsement: if STEP 0's
    stamp is lost the gate silently returns to the pre-#1045 session-scoped
    behaviour, which is the original defect. It is reported loudly on stderr so
    the degradation is at least visible.

    State code must never be able to block the gate, so raising here is not an
    option.
    """

    def exploding_rmw(*args, **kwargs):
        raise RuntimeError("simulated state write failure")

    monkeypatch.setattr(P, "_locked_rmw", exploding_rmw)
    capsys.readouterr()

    result = record_run_start(sid, "runX")  # must not raise

    assert result is False, "a failed stamp must be reported to the caller"
    err = capsys.readouterr().err
    assert "failed to record run start" in err, f"failure must be loud; got {err!r}"
    assert "runX" in err, "the report must name the run id that was lost"

    monkeypatch.undo()

    _record_five(sid)
    state = _read_state(sid)
    assert "current_run_id" not in state
    assert not state.get("completion_run_ids")
    passed, _, _ = verify_pipeline_agent_completions(sid, "fix", issue_number=0)
    assert passed is True, "the residual is (a1)-permissive, not a deadlock"


# --------------------------------------------------------------------------- #
# 8. pytest-gate is a stamped virtual agent
# --------------------------------------------------------------------------- #


def test_pytest_gate_is_stamped_and_drops_out_of_a_later_run(sid, run_a, run_b) -> None:
    """``record_pytest_gate_passed`` routes through the stamped writer.

    It is a virtual agent recorded via ``record_agent_completion``, so a green
    pytest gate from run A must not satisfy run B.
    """
    assert run_a != run_b

    assert record_run_start(sid, run_a) is True
    record_pytest_gate_passed(sid)
    assert "pytest-gate" in get_completed_agents(sid)

    stamps = _read_state(sid).get("completion_run_ids", {}).get("0", {})
    assert stamps.get("pytest-gate") == run_a, (
        f"pytest-gate must carry run A's stamp, got {stamps!r}"
    )

    assert record_run_start(sid, run_b) is True
    assert "pytest-gate" not in get_completed_agents(sid), (
        "run A's green pytest gate must not satisfy run B"
    )


# --------------------------------------------------------------------------- #
# 9/10. SubagentStop-shaped records (unified_session_tracker's call shape)
# --------------------------------------------------------------------------- #


def test_subagentstop_record_without_run_start_is_permissive(sid, capsys) -> None:
    """(9) ``unified_session_tracker`` fires for ANY subagent, including ad hoc
    dispatch that never entered ``/implement`` STEP 0.

    That path writes into the same session-keyed file with no run identity, so
    it must land in (a1) and behave exactly as before this change. This is the
    live, ongoing category — not a shrinking pre-migration edge case.
    """
    record_agent_completion(sid, "reviewer", issue_number=0, success=True)
    capsys.readouterr()

    assert get_completed_agents(sid) == {"reviewer"}
    assert "[pipeline_completion_state]" not in capsys.readouterr().err


def test_subagentstop_record_after_run_start_is_credited_to_current_run(
    sid, run_a
) -> None:
    """(10) ACCEPTED behaviour: once a run is current, an out-of-band
    SubagentStop record is credited to it.

    The SubagentStop hook cannot know which run dispatched the subagent, so a
    subagent completing during run A is attributed to run A. This is the right
    default — that IS the run in flight — but it means an ad hoc Agent dispatch
    made during a pipeline run counts toward that run's completeness.

    Asserted explicitly so a future change to this attribution fails visibly
    rather than silently altering what the gate credits.
    """
    assert record_run_start(sid, run_a) is True
    record_agent_completion(sid, "reviewer", issue_number=0, success=True)

    assert get_completed_agents(sid) == {"reviewer"}
    stamps = _read_state(sid).get("completion_run_ids", {}).get("0", {})
    assert stamps.get("reviewer") == run_a
