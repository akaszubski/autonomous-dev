"""Run-scoping for the BATCH AGGREGATE completeness gates (Issue #1045).

``get_completed_agents`` was made run-scoped by the first pass of #1045, but the
two batch aggregate readers were not:

* ``verify_batch_cia_completions``
* ``verify_batch_doc_master_completions``

Both iterate ``state["completions"]`` directly and never call
``get_completed_agents``, so both kept the pre-fix session-scoped shape. Both are
wired straight into the commit-blocking hook (``unified_pre_tool.py``), so a
batch RETRY of one issue inside the same session silently passed the final batch
commit gate on a previous run's completions — the same confused deputy, in the
highest-volume generator of it.

**Why these gates are NOT filtered by ``current_run_id``.** Batch mode creates
ONE RUN PER ISSUE inside ONE session (``implement-batch.md``: ``ISSUE_RUN_ID``
per issue), and ``current_run_id`` is overwritten by each issue in turn. At the
final batch commit ``current_run_id`` is the LAST issue's run id, so filtering
every scope to it would drop every earlier issue in a perfectly healthy batch
and refuse it. That false refusal is pinned by the positive controls below
(``test_healthy_*``), which are deliberately a DIFFERENT SHAPE from the
reproducer: three issues, three sequential runs, nothing stale.

The authority for a per-issue aggregate is instead the run that most recently
STARTED work on that issue — recorded by ``record_run_start(..., issue_number=N)``
into the ``issue_run_starts`` sibling map, and consumed by
``_filter_to_owning_run``.

Policy under test, per issue scope:

===== ================================================== ===================
State  Condition                                          Behaviour
===== ================================================== ===================
(o0)   no ``issue_run_starts`` entry for the scope        pass through
(o1)   owner set, agent stamped with owner                credited
(o2)   owner set, agent stamped with a superseded run     excluded, loud
(o3)   owner set, agent unstamped                         excluded
===== ================================================== ===================

Issues: #1045
"""

import os
import sys
import time
import uuid
from pathlib import Path

import pytest

# tests/regression/<file>.py -> regression -> tests -> repo root == parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as P  # noqa: E402
from pipeline_completion_state import (  # noqa: E402
    _state_file_path,
    record_agent_completion,
    record_doc_verdict,
    record_run_start,
    verify_batch_cia_completions,
    verify_batch_doc_master_completions,
)

CIA = "continuous-improvement-analyst"
DOC = "doc-master"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def sid() -> str:
    """Per-test unique session id.

    ``/tmp`` is process-global and is NOT cleared between pytest invocations, so
    a fixed literal would let a leaked file from an earlier run poison this one.
    """
    return f"test-1045-batch-{os.getpid()}-{time.time_ns()}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def isolate_batch_gate_environment(monkeypatch, tmp_path):
    """Remove ambient influences that would make these assertions unfalsifiable.

    ``SKIP_BATCH_CIA_GATE`` / ``SKIP_BATCH_DOC_MASTER_GATE`` short-circuit the
    functions under test to ``(True, [], [])``, so a refusal test could never
    observe a refusal. The ``'unknown'`` merge is disabled by pinning the TTL to
    0; no test here exercises it.
    """
    monkeypatch.delenv("SKIP_BATCH_CIA_GATE", raising=False)
    monkeypatch.delenv("SKIP_BATCH_DOC_MASTER_GATE", raising=False)
    monkeypatch.setattr(P, "STALE_UNKNOWN_TTL_SECONDS", 0)
    yield


@pytest.fixture(autouse=True)
def cleanup_state(sid):
    """Remove this test's state and lock files, whatever the outcome."""
    try:
        yield
    finally:
        path = _state_file_path(sid)
        try:
            path.unlink(missing_ok=True)
            path.with_suffix(".lock").unlink(missing_ok=True)
        except OSError:
            pass


def _run_id(issue_number: int) -> str:
    """Build a batch-shaped run id. Distinct per call by construction (uuid4)."""
    return f"issue-{issue_number}-{uuid.uuid4().hex}"


def _process_issue(session_id: str, issue_number: int, *, verdict: str = "PASS") -> str:
    """Run one issue's batch pipeline the way ``implement-batch.md`` does.

    A fresh run id per issue, ``record_run_start`` before any agent, then the
    two agents the batch commit gates require. Returns the run id used.
    """
    run_id = _run_id(issue_number)
    assert record_run_start(session_id, run_id, issue_number=issue_number) is True
    record_agent_completion(session_id, CIA, issue_number=issue_number)
    record_agent_completion(session_id, DOC, issue_number=issue_number)
    record_doc_verdict(session_id, issue_number, verdict)
    return run_id


# --------------------------------------------------------------------------- #
# 1. THE DEFECT — refusing arm
# --------------------------------------------------------------------------- #


def test_batch_cia_gate_refuses_stale_prior_run_credit(sid) -> None:
    """(o2) Run B executed nothing; the CIA gate must not credit run A.

    RED before the fix: ``verify_batch_cia_completions`` returned
    ``(True, [100], [])`` for a run in which zero agents executed.
    """
    run_a = _process_issue(sid, 100)
    passed_a, with_a, missing_a = verify_batch_cia_completions(sid)
    assert passed_a is True, f"precondition: run A must satisfy the gate ({missing_a})"
    assert with_a == [100]

    # RUN B: same session, same issue, brand new run, ZERO agents executed.
    run_b = _run_id(100)
    assert run_a != run_b, "two-run test requires two distinct run ids"
    assert record_run_start(sid, run_b, issue_number=100) is True

    passed_b, with_b, missing_b = verify_batch_cia_completions(sid)
    assert passed_b is False, (
        "run B executed zero agents but the batch CIA gate passed — it inherited "
        f"run A's authority (with_cia={with_b})"
    )
    assert missing_b == [100], f"issue 100 must be reported missing, got {missing_b}"
    assert with_b == [], f"no issue may be credited to run B, got {with_b}"


def test_batch_doc_master_gate_refuses_stale_prior_run_credit(sid) -> None:
    """(o2) Run B executed nothing; the doc-master gate must not credit run A.

    RED before the fix: ``verify_batch_doc_master_completions`` returned
    ``(True, [100], [])``.
    """
    run_a = _process_issue(sid, 100)
    passed_a, with_a, _ = verify_batch_doc_master_completions(sid)
    assert passed_a is True, "precondition: run A must satisfy the gate"
    assert with_a == [100]

    run_b = _run_id(100)
    assert run_a != run_b, "two-run test requires two distinct run ids"
    assert record_run_start(sid, run_b, issue_number=100) is True

    passed_b, with_b, missing_b = verify_batch_doc_master_completions(sid)
    assert passed_b is False, (
        "run B executed zero agents but the batch doc-master gate passed — it "
        f"inherited run A's authority (with_doc_master={with_b})"
    )
    assert missing_b == [100], f"issue 100 must be reported missing, got {missing_b}"
    assert with_b == []


def test_stale_scope_exclusion_is_reported_on_stderr(sid, capsys) -> None:
    """(o2) The refusal must say WHY, not look like "the agent never ran".

    Without this the batch gate's message is actively misleading: it reports
    "doc-master never ran" for an issue whose doc-master ran — in a prior run.
    """
    _process_issue(sid, 100)
    capsys.readouterr()  # discard anything emitted during setup

    assert record_run_start(sid, _run_id(100), issue_number=100) is True
    verify_batch_cia_completions(sid)

    err = capsys.readouterr().err
    assert (
        "superseded" in err.lower()
    ), f"stale-scope exclusion must be reported on stderr; got {err!r}"
    assert "100" in err, f"the report must name the issue scope; got {err!r}"


# --------------------------------------------------------------------------- #
# 2. POSITIVE CONTROLS — permitting arm.
#
# Deliberately a DIFFERENT SHAPE from the reproducer above: three issues, three
# sequential per-issue runs, nothing stale. These fail against a naive
# "filter every scope to current_run_id" fix, which drops issues 100 and 101
# because current_run_id is issue 102's by the time the batch commits.
# --------------------------------------------------------------------------- #


def test_healthy_multi_issue_batch_still_passes_cia(sid) -> None:
    """A clean 3-issue batch must still pass the CIA gate."""
    for issue in (100, 101, 102):
        _process_issue(sid, issue)

    passed, with_cia, missing = verify_batch_cia_completions(sid)
    assert passed is True, (
        "a healthy 3-issue batch was REFUSED — run scoping must be per-issue "
        f"ownership, not current_run_id (missing={missing})"
    )
    assert with_cia == [100, 101, 102]
    assert missing == []


def test_healthy_multi_issue_batch_still_passes_doc_master(sid) -> None:
    """A clean 3-issue batch must still pass the doc-master gate."""
    for issue in (100, 101, 102):
        _process_issue(sid, issue)

    passed, with_doc, missing = verify_batch_doc_master_completions(sid)
    assert passed is True, (
        "a healthy 3-issue batch was REFUSED — run scoping must be per-issue "
        f"ownership, not current_run_id (missing={missing})"
    )
    assert with_doc == [100, 101, 102]
    assert missing == []


def test_batch_retry_that_actually_reruns_the_agents_passes(sid) -> None:
    """(o1) A retry that DOES re-run its agents must be credited, not refused.

    The guard must reject stale credit, not reject retries.
    """
    _process_issue(sid, 100)

    run_b = _run_id(100)
    assert record_run_start(sid, run_b, issue_number=100) is True
    record_agent_completion(sid, CIA, issue_number=100)
    record_agent_completion(sid, DOC, issue_number=100)
    record_doc_verdict(sid, 100, "PASS")

    passed_cia, with_cia, missing_cia = verify_batch_cia_completions(sid)
    assert passed_cia is True, f"re-run agents must be credited (missing={missing_cia})"
    assert with_cia == [100]

    passed_doc, with_doc, missing_doc = verify_batch_doc_master_completions(sid)
    assert passed_doc is True, f"re-run agents must be credited (missing={missing_doc})"
    assert with_doc == [100]


def test_unwired_run_start_leaves_batch_gates_permissive(sid) -> None:
    """(o0) No ownership record -> today's behaviour, no refusal, no stderr.

    ``record_run_start`` without ``issue_number`` is the pre-change call shape
    and every non-batch caller. It must not start refusing batch state, or a
    stale deployment of ``implement-batch.md`` would block every batch commit.
    """
    assert record_run_start(sid, _run_id(100)) is True  # NO issue_number
    record_agent_completion(sid, CIA, issue_number=100)
    record_agent_completion(sid, DOC, issue_number=100)
    record_doc_verdict(sid, 100, "PASS")

    # A second run, also unwired, executing nothing.
    assert record_run_start(sid, _run_id(100)) is True

    passed_cia, with_cia, _ = verify_batch_cia_completions(sid)
    assert passed_cia is True, "unwired state must stay permissive (no regression)"
    assert with_cia == [100]

    passed_doc, with_doc, _ = verify_batch_doc_master_completions(sid)
    assert passed_doc is True, "unwired state must stay permissive (no regression)"
    assert with_doc == [100]


# --------------------------------------------------------------------------- #
# 3. Semantics that must survive the change
# --------------------------------------------------------------------------- #


def test_doc_master_verdict_semantics_survive_run_scoping(sid) -> None:
    """A current-run doc-master with a SHALLOW verdict is still incomplete.

    Guards against a filter that drops ``doc-master-verdict`` along with the
    agents: that would silently convert an invalid verdict into the
    backward-compatible "no verdict recorded" branch and WEAKEN the gate.
    """
    run_b = _run_id(100)
    assert record_run_start(sid, run_b, issue_number=100) is True
    record_agent_completion(sid, DOC, issue_number=100)
    record_doc_verdict(sid, 100, "SHALLOW")

    passed, with_doc, missing = verify_batch_doc_master_completions(sid)
    assert passed is False, "SHALLOW verdict must remain incomplete"
    assert missing == [100]
    assert with_doc == []


def test_record_run_start_issue_number_is_optional(sid) -> None:
    """The new keyword is optional and does not change the return contract."""
    assert record_run_start(sid, _run_id(0)) is True
    assert record_run_start(sid, _run_id(7), issue_number=7) is True
    # Invalid run ids still report False rather than raising.
    assert record_run_start(sid, "bad id with spaces", issue_number=7) is False


def test_ownership_is_recorded_per_issue_scope(sid) -> None:
    """Each issue scope records its OWN owning run, not a single global one."""
    run_100 = _process_issue(sid, 100)
    run_101 = _process_issue(sid, 101)
    assert run_100 != run_101

    state = P._read_state(sid)
    owners = state.get("issue_run_starts", {})
    assert owners.get("100") == run_100, f"issue 100 owner wrong: {owners}"
    assert owners.get("101") == run_101, f"issue 101 owner wrong: {owners}"
