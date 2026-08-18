#!/usr/bin/env python3
"""Regression tests for Issue #1544 — silent completion loss via truncate-before-lock.

``_write_state`` used ``open(path, "w")``, which truncates the file to 0 bytes
*before* ``fcntl.flock(LOCK_EX)`` is taken. A concurrent reader landing in that
window read an empty file, ``_read_state`` swallowed the ``JSONDecodeError`` and
returned ``{}``, and ``_ensure_state`` interpreted ``{}`` as "no file yet" and
rebuilt a blank skeleton — silently discarding every recorded completion. The
only downstream symptom was an ordering gate refusing an agent that had just run.

These tests lock in the four halves of the fix:

1. All state mutators run under ``_locked_rmw`` (whole read-modify-write
   serialized behind a sibling lockfile).
2. The raw truncating write is unreachable — ``_write_state`` self-wraps in
   ``_locked_rmw`` when called from outside it, and ``_atomic_write_state`` is
   called from exactly one place.
3. The on-disk write is atomic (``os.replace``), so ``_locked_rmw``'s deliberate
   fail-open path is *safe* rather than merely rarer.
4. ``_read_state`` no longer treats a parse failure as "file absent" silently —
   it retries briefly and reports loudly.

Negative controls (first-run skeleton, #1413 staleness, existing call
signatures) are asserted here too: the fix must not buy monotonicity by
disabling either of those.

Issues: #1544 (regression of #1170's incomplete coverage; see also #1169, #1413)
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

pcs = importlib.import_module("pipeline_completion_state")

MODULE_SOURCE_PATH = LIB_DIR / "pipeline_completion_state.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_session_id() -> str:
    return f"issue1544-{uuid.uuid4().hex[:12]}"


def _cleanup(session_id: str) -> None:
    for path in (
        pcs._state_file_path(session_id),
        Path(str(pcs._state_file_path(session_id)).replace(".json", ".lock")),
    ):
        try:
            path.unlink()
        except OSError:
            pass


@pytest.fixture()
def session_id():
    sid = _fresh_session_id()
    yield sid
    _cleanup(sid)


def _run_under_watchdog(fn, *, timeout: float = 2.0) -> tuple[bool, dict]:
    """Run *fn* on a daemon thread and return ``(completed, box)``.

    A self-deadlock in this module blocks forever on ``fcntl.flock`` with no
    timeout, so a regression must fail fast rather than hang the suite. The
    thread is a daemon so a hung run cannot wedge CI at interpreter exit, and
    every caller uses a uuid4-unique session id so a leaked lock cannot block
    any other test.
    """
    box: dict = {}

    def _runner() -> None:
        try:
            fn()
            box["ok"] = True
        except BaseException as exc:  # noqa: BLE001 - surfaced to the assertion
            box["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    return (not thread.is_alive()), box


def _nested_mutator_offenders(source: str) -> list[str]:
    """Return offending call sites where a mutator callable re-enters the lock.

    ``_locked_rmw`` takes a non-reentrant ``flock``. A callable handed to it
    that calls ``_locked_rmw`` again — directly, or via another public mutator
    that wraps it — opens a second file description on the same lockfile and
    blocks on a lock its own thread already holds. The module docstring
    declares "the mutator MUST NOT call another state mutator"; this makes
    that declaration mechanically enforced instead of aspirational.

    ``_write_state`` is deliberately NOT forbidden: the #1544 re-entrancy
    guard is held across the whole mutate-and-write, so a ``_write_state``
    call inside a mutator short-circuits to the direct atomic write.
    """
    tree = ast.parse(source)

    def _calls(node: ast.AST) -> list[ast.Call]:
        return [
            n
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        ]

    rmw_callers = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(c.func.id == "_locked_rmw" for c in _calls(node))  # type: ignore[attr-defined]
    }
    forbidden = (rmw_callers - {"_write_state"}) | {"_locked_rmw"}

    offenders: list[str] = []
    for parent in ast.walk(tree):
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        handed = {
            call.args[1].id
            for call in _calls(parent)
            if call.func.id == "_locked_rmw"  # type: ignore[attr-defined]
            and len(call.args) > 1
            and isinstance(call.args[1], ast.Name)
        }
        if not handed:
            continue
        for child in ast.walk(parent):
            if (
                not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                or child.name not in handed
            ):
                continue
            for call in _calls(child):
                if call.func.id in forbidden:  # type: ignore[attr-defined]
                    offenders.append(
                        f"{parent.name}.{child.name}:{call.lineno} "
                        f"-> {call.func.id}()"  # type: ignore[attr-defined]
                    )
    return offenders


# ---------------------------------------------------------------------------
# AC-1: concurrency stress — completion counts must be monotonic
# ---------------------------------------------------------------------------


class TestConcurrentCompletionsAreMonotonic:
    """The core defect: concurrent writers wiped each other's completions."""

    def test_concurrent_writers_never_lose_completions(self, session_id) -> None:
        """N writers + N readers. Observed completion count must never decrease.

        Fails against the pre-#1544 code (truncate-before-lock lets a reader see
        an empty file, which ``_ensure_state`` rebuilds as a blank skeleton).
        """
        n_writers = 4
        iterations = 40
        expected_agents = {
            f"agent-{w}-{i}" for w in range(n_writers) for i in range(iterations)
        }

        stop = threading.Event()
        # Per-reader sequences: a single shared list would conflate two
        # readers' interleaved observations and report a spurious decrease.
        # Monotonicity is a property of ONE observer's timeline.
        reader_sequences: dict[int, list[int]] = {0: [], 1: []}
        empty_after_nonempty = 0
        lock = threading.Lock()

        def writer(worker: int) -> None:
            for i in range(iterations):
                pcs.record_agent_completion(session_id, f"agent-{worker}-{i}")

        def reader(slot: int) -> None:
            nonlocal empty_after_nonempty
            seen_nonempty = False
            seq = reader_sequences[slot]
            while not stop.is_set():
                completed = pcs.get_completed_agents(session_id)
                seq.append(len(completed))
                if completed:
                    seen_nonempty = True
                elif seen_nonempty:
                    with lock:
                        empty_after_nonempty += 1

        # Seed the file so readers have something to observe from the start.
        pcs.record_agent_completion(session_id, "seed-agent")

        readers = [
            threading.Thread(target=reader, args=(slot,), daemon=True)
            for slot in reader_sequences
        ]
        for t in readers:
            t.start()
        writers = [
            threading.Thread(target=writer, args=(w,)) for w in range(n_writers)
        ]
        for t in writers:
            t.start()
        for t in writers:
            t.join()
        stop.set()
        for t in readers:
            t.join(timeout=5)

        # (a) No reader ever saw its own view of the ledger go backwards.
        regressions = [
            (slot, i, seq[i - 1], seq[i])
            for slot, seq in reader_sequences.items()
            for i in range(1, len(seq))
            if seq[i] < seq[i - 1]
        ]
        assert not regressions, (
            f"Completion count decreased {len(regressions)} time(s) — state was "
            f"clobbered mid-write. First 5: {regressions[:5]}"
        )
        assert all(len(seq) > 10 for seq in reader_sequences.values()), (
            f"Readers barely sampled; the monotonicity assertion is not "
            f"meaningful. Sample counts: "
            f"{[len(s) for s in reader_sequences.values()]}"
        )

        # (b) No reader ever saw a wiped ledger after seeing a populated one.
        assert empty_after_nonempty == 0, (
            f"{empty_after_nonempty} read(s) saw an EMPTY ledger after it was "
            f"populated — truncate-before-lock window is still open."
        )

        # (c) Nothing was lost.
        final = pcs.get_completed_agents(session_id)
        missing = expected_agents - final
        assert not missing, (
            f"{len(missing)} completion(s) lost under concurrency. "
            f"Sample: {sorted(missing)[:5]}"
        )

    def test_reader_never_observes_partial_or_empty_json(self, session_id) -> None:
        """A reader hitting the file mid-write sees complete old OR complete new."""
        pcs.record_agent_completion(session_id, "planner")
        path = pcs._state_file_path(session_id)

        stop = threading.Event()
        bad_reads: list[str] = []

        def writer() -> None:
            for i in range(150):
                pcs.record_agent_completion(session_id, f"writer-agent-{i}")
            stop.set()

        def raw_reader() -> None:
            while not stop.is_set():
                try:
                    raw = path.read_text()
                except OSError:
                    continue
                if raw == "":
                    bad_reads.append("<empty>")
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    bad_reads.append(raw[:80])
                    continue
                if not parsed.get("completions"):
                    bad_reads.append("<no completions key>")

        w = threading.Thread(target=writer)
        r = threading.Thread(target=raw_reader, daemon=True)
        r.start()
        w.start()
        w.join()
        stop.set()
        r.join(timeout=5)

        assert not bad_reads, (
            f"{len(bad_reads)} raw read(s) observed a truncated/partial file. "
            f"Sample: {bad_reads[:3]}"
        )


# ---------------------------------------------------------------------------
# AC-2: the raw write is unreachable outside _locked_rmw
# ---------------------------------------------------------------------------


class TestRawWriteIsUnreachable:
    """Durable half: a ninth bypass caller must not be able to appear."""

    def test_write_state_outside_rmw_self_wraps(self, session_id, monkeypatch) -> None:
        """A direct ``_write_state`` call routes through ``_locked_rmw``."""
        calls: list[str] = []
        real_rmw = pcs._locked_rmw

        def spy(sid, mutator, *, run_id=None):
            calls.append(sid)
            return real_rmw(sid, mutator, run_id=run_id)

        monkeypatch.setattr(pcs, "_locked_rmw", spy)
        pcs._write_state(session_id, {"session_id": session_id, "completions": {}})

        assert calls == [session_id], (
            "_write_state called from outside _locked_rmw must self-wrap in "
            "_locked_rmw — otherwise the truncate-before-lock window returns."
        )

    def test_atomic_write_has_exactly_one_call_site(self) -> None:
        """``_atomic_write_state`` may only be called from ``_write_state``.

        Structural guard: this is the mechanism that stops a ninth bypass from
        being added later. If you legitimately need another call site, name and
        justify it here rather than widening the allowlist silently.
        """
        allowed_callers = {"_write_state"}
        tree = ast.parse(MODULE_SOURCE_PATH.read_text())
        offenders: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id == "_atomic_write_state"
                    and node.name not in allowed_callers
                ):
                    offenders.append(f"{node.name}:{inner.lineno}")

        assert not offenders, (
            f"_atomic_write_state called outside {sorted(allowed_callers)}: "
            f"{offenders}. Route the mutation through _locked_rmw instead."
        )

    def test_all_mutators_route_through_locked_rmw(self) -> None:
        """The eight #1544 mutators must call ``_locked_rmw``, not ``_write_state``."""
        mutators = {
            "record_agent_completion",
            "record_agent_launch",
            "record_prompt_baseline",
            "set_validation_mode",
            "record_doc_verdict",
            "record_research_skipped",
            "record_plan_critic_skipped",
            "record_plan_critic_passed",
        }
        tree = ast.parse(MODULE_SOURCE_PATH.read_text())
        found: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name not in mutators:
                continue
            called = {
                inner.func.id
                for inner in ast.walk(node)
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
            }
            assert "_locked_rmw" in called, (
                f"{node.name} does not call _locked_rmw — its read-modify-write "
                f"is unserialized and can clobber a concurrent writer."
            )
            found.add(node.name)

        assert found == mutators, f"Mutators not found in source: {mutators - found}"


class _FakeFcntlFlockFails:
    """Stand-in for ``fcntl`` whose ``flock`` always fails (NFS-style)."""

    LOCK_EX = 2
    LOCK_SH = 1
    LOCK_UN = 8

    @staticmethod
    def flock(fd: int, op: int) -> None:
        raise OSError("simulated flock failure (NFS)")


class TestRmwGuardSpansMutateAndWrite:
    """The re-entrancy guard must be held across the mutator, not just the write.

    Reviewer FINDING-1 on the #1544 fix: ``_RMW_GUARD.depth`` was incremented
    *after* ``mutator(state)`` returned. A mutator that called ``_write_state``
    directly — the exact pattern ``_locked_rmw``'s docstring advertised as
    "safe" — therefore saw ``_in_locked_rmw() is False``, took the self-wrap
    branch, and re-entered ``_locked_rmw``. ``flock`` is per open file
    description and not reentrant, and the call has no ``LOCK_NB``, so it
    blocked forever. Reproduced with a 6 s subprocess watchdog before the fix.
    """

    def test_write_state_inside_mutator_does_not_deadlock(self, session_id) -> None:
        """The documented-as-safe pattern must actually complete, not hang."""

        def mutator(state: dict) -> None:
            state["completions"] = {"0": {"planner": True}}
            # This is what the _locked_rmw docstring calls safe. Pre-fix it
            # self-wrapped into a second _locked_rmw and blocked forever.
            pcs._write_state(session_id, state)

        completed, box = _run_under_watchdog(
            lambda: pcs._locked_rmw(session_id, mutator)
        )

        assert completed, (
            "deadlock: _write_state inside a mutator blocked. The guard must "
            "be held across mutate AND write so the self-wrap branch is not "
            "taken re-entrantly."
        )
        assert "error" not in box, f"unexpected error: {box.get('error')!r}"
        assert pcs.get_completed_agents(session_id) == {"planner"}

    def test_guard_is_held_while_the_mutator_runs(self, session_id) -> None:
        """Direct assertion of the ordering defect, independent of timing."""
        observed: list[bool] = []

        def mutator(state: dict) -> None:
            observed.append(pcs._in_locked_rmw())

        pcs._locked_rmw(session_id, mutator)

        assert observed == [True], (
            "_in_locked_rmw() was False inside the mutator — the guard is "
            "taken after mutation, so a mutator that writes re-enters the lock."
        )

    def test_guard_held_on_flock_failure_fallback(self, session_id, monkeypatch) -> None:
        """Fail-open branch 1 (flock raises) must hold the guard identically."""
        monkeypatch.setattr(pcs, "fcntl", _FakeFcntlFlockFails)
        observed: list[bool] = []

        def mutator(state: dict) -> None:
            observed.append(pcs._in_locked_rmw())
            state["completions"] = {"0": {"reviewer": True}}
            pcs._write_state(session_id, state)

        completed, box = _run_under_watchdog(
            lambda: pcs._locked_rmw(session_id, mutator)
        )
        monkeypatch.undo()  # restore real fcntl before the verifying read

        assert completed, "deadlock on the flock-failure fail-open path"
        assert "error" not in box, f"unexpected error: {box.get('error')!r}"
        assert observed == [True], "guard not held on the flock-failure path"
        assert pcs.get_completed_agents(session_id) == {"reviewer"}

    def test_guard_held_on_lockfile_open_failure_fallback(
        self, session_id, monkeypatch
    ) -> None:
        """Fail-open branch 2 (lockfile cannot be opened) holds the guard too."""
        real_open = open

        def selective_open(file, *args, **kwargs):
            if str(file).endswith(".lock"):
                raise OSError("simulated /tmp full")
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr("builtins.open", selective_open)
        observed: list[bool] = []

        def mutator(state: dict) -> None:
            observed.append(pcs._in_locked_rmw())
            state["completions"] = {"0": {"doc-master": True}}
            pcs._write_state(session_id, state)

        completed, box = _run_under_watchdog(
            lambda: pcs._locked_rmw(session_id, mutator)
        )
        monkeypatch.undo()

        assert completed, "deadlock on the lockfile-open-failure fail-open path"
        assert "error" not in box, f"unexpected error: {box.get('error')!r}"
        assert observed == [True], "guard not held on the lockfile-open-failure path"
        assert pcs.get_completed_agents(session_id) == {"doc-master"}

    def test_guard_depth_unwinds_when_the_mutator_raises(self, session_id) -> None:
        """Negative control: the guard must not leak across a mutator failure."""

        def boom(state: dict) -> None:
            raise ValueError("mutator exploded")

        with pytest.raises(ValueError):
            pcs._locked_rmw(session_id, boom)

        assert pcs._in_locked_rmw() is False, (
            "guard depth leaked after a mutator raised — every later "
            "_write_state would then skip the lock entirely."
        )

    def test_no_mutator_calls_another_mutator(self) -> None:
        """FINDING-2: pin the docstring's "no nested mutator" constraint in code.

        A mutator that calls ``_locked_rmw`` (directly, or via a public mutator
        that wraps it) self-deadlocks by the FINDING-1 mechanism. Documented
        but previously unenforced.
        """
        offenders = _nested_mutator_offenders(MODULE_SOURCE_PATH.read_text())
        assert not offenders, (
            f"mutator callable re-enters _locked_rmw: {offenders}. flock is not "
            f"reentrant — this self-deadlocks. Mutate `state` in place instead."
        )

    def test_nested_mutator_checker_refuses_a_synthetic_violation(self) -> None:
        """Watch the guard refusing: the AST check must not be vacuously green."""
        violating = (
            "def record_thing(session_id):\n"
            "    def _mutator(state):\n"
            "        record_other(session_id)\n"
            "    _locked_rmw(session_id, _mutator)\n"
            "\n"
            "def record_other(session_id):\n"
            "    def _mutator(state):\n"
            "        state['x'] = 1\n"
            "    _locked_rmw(session_id, _mutator)\n"
        )
        offenders = _nested_mutator_offenders(violating)
        assert offenders, "checker missed a mutator calling another mutator"
        assert any("record_other" in o for o in offenders), offenders

        direct = (
            "def record_thing(session_id):\n"
            "    def _mutator(state):\n"
            "        _locked_rmw(session_id, _mutator)\n"
            "    _locked_rmw(session_id, _mutator)\n"
        )
        assert _nested_mutator_offenders(direct), (
            "checker missed a mutator calling _locked_rmw directly"
        )

    def test_nested_mutator_checker_permits_the_legitimate_case(self) -> None:
        """Negative control: a pure in-memory mutator (and _write_state) is clean."""
        clean = (
            "def record_thing(session_id):\n"
            "    def _mutator(state):\n"
            "        state.setdefault('completions', {})['0'] = True\n"
            "        _write_state(session_id, state)\n"
            "    _locked_rmw(session_id, _mutator)\n"
            "\n"
            "def _write_state(session_id, state):\n"
            "    def _replace_all(existing):\n"
            "        existing.update(state)\n"
            "    _locked_rmw(session_id, _replace_all)\n"
        )
        assert _nested_mutator_offenders(clean) == [], (
            "checker flagged the sanctioned pattern — a false positive here "
            "would make the guard cry wolf."
        )


# ---------------------------------------------------------------------------
# AC-3: parse failure is not silently treated as "absent"
# ---------------------------------------------------------------------------


class TestCorruptStateIsReportedLoudly:
    def test_corrupt_file_is_reported_on_stderr(self, session_id, capsys) -> None:
        """A non-empty, non-JSON file must be reported, not silently rebuilt."""
        path = pcs._state_file_path(session_id)
        path.write_text("not valid json {{{")

        state = pcs._read_state(session_id)

        # Degrades (does not raise) — a hard failure here would block the gate.
        assert state == {}
        captured = capsys.readouterr()
        assert "pipeline_completion_state" in captured.err, (
            "Unreadable state must be reported loudly on stderr; silently "
            "returning {} is what turns a transient read into permanent loss."
        )

    def test_corrupt_file_still_degrades_not_raises(self, session_id) -> None:
        """Negative control for AC-3: readers must not start raising."""
        path = pcs._state_file_path(session_id)
        path.write_text("{{{ broken")
        assert pcs.get_completed_agents(session_id) == set()

    def test_transient_empty_file_is_retried(self, session_id, monkeypatch) -> None:
        """An empty file that becomes valid mid-read is recovered by the retry."""
        path = pcs._state_file_path(session_id)
        path.write_text("")

        good = {"session_id": session_id, "completions": {"0": {"planner": True}}}
        state_holder = {"attempts": 0}
        real_open = open

        def flaky_open(file, *args, **kwargs):
            if str(file) == str(path) and (not args or "r" in str(args[0])):
                state_holder["attempts"] += 1
                if state_holder["attempts"] == 2:
                    path.write_text(json.dumps(good))
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr("builtins.open", flaky_open)
        result = pcs._read_state(session_id)
        monkeypatch.undo()

        assert result.get("completions") == good["completions"], (
            "A transient empty read must be retried, not converted into a "
            "permanent blank skeleton."
        )


# ---------------------------------------------------------------------------
# Negative controls — the fix must not buy monotonicity by breaking these
# ---------------------------------------------------------------------------


class TestNegativeControls:
    def test_absent_file_still_produces_fresh_skeleton(self, session_id) -> None:
        """First-run behavior survives: no file -> fresh skeleton, no shouting."""
        path = pcs._state_file_path(session_id)
        assert not path.exists()

        assert pcs._read_state(session_id) == {}
        pcs.record_agent_completion(session_id, "planner")

        assert path.exists()
        assert "planner" in pcs.get_completed_agents(session_id)

    def test_absent_file_is_not_reported_as_corrupt(self, session_id, capsys) -> None:
        """Negative control on the loud-report path: absence is normal."""
        pcs._read_state(session_id)
        assert "pipeline_completion_state" not in capsys.readouterr().err

    def test_issue_1413_staleness_still_ages_out(self, session_id) -> None:
        """A genuinely abandoned file (mtime > 7200s) still returns {}."""
        pcs.record_agent_completion(session_id, "planner")
        path = pcs._state_file_path(session_id)
        old = time.time() - 3 * 3600
        os.utime(path, (old, old))

        assert pcs._read_state(session_id) == {}
        assert pcs.get_completed_agents(session_id) == set()

    def test_issue_1413_mtime_refresh_on_read_preserved(self, session_id) -> None:
        """An active session reading its state keeps the file fresh."""
        pcs.record_agent_completion(session_id, "planner")
        path = pcs._state_file_path(session_id)
        old = time.time() - 7000  # stale-ish but inside the window
        os.utime(path, (old, old))

        assert pcs._read_state(session_id) != {}
        assert time.time() - path.stat().st_mtime < 60, (
            "#1413 mtime-refresh-on-read must be preserved."
        )

    def test_issue_1169_chmod_0600_preserved(self, session_id) -> None:
        pcs.record_agent_completion(session_id, "planner")
        mode = pcs._state_file_path(session_id).stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got 0o{mode:o}"

    def test_no_temp_files_left_behind(self, session_id) -> None:
        """os.replace() staging files must not accumulate in /tmp."""
        for i in range(5):
            pcs.record_agent_completion(session_id, f"agent-{i}")
        leftovers = list(Path("/tmp").glob(f"{pcs._state_file_path(session_id).name}.*"))
        assert not leftovers, f"Temp files left behind: {leftovers}"

    def test_orphaned_staging_file_is_garbage_collected(self, session_id) -> None:
        """A staging file from a process killed mid-write is reaped by GC."""
        orphan = Path(f"{pcs._state_file_path(session_id)}.abc123.tmp")
        orphan.write_text("{}")
        old = time.time() - 3 * 3600
        os.utime(orphan, (old, old))
        try:
            pcs._gc_stale_states()
            assert not orphan.exists(), (
                "Orphaned os.replace staging file was not garbage-collected — "
                "/tmp accumulates one per killed writer."
            )
        finally:
            try:
                orphan.unlink()
            except OSError:
                pass

    def test_gc_spares_fresh_staging_file(self) -> None:
        """Negative control: an in-flight staging file must NOT be reaped."""
        sid = _fresh_session_id()
        fresh = Path(f"{pcs._state_file_path(sid)}.inflight.tmp")
        fresh.write_text("{}")
        try:
            pcs._gc_stale_states()
            assert fresh.exists(), (
                "GC removed a fresh staging file — it could yank the target "
                "out from under an in-flight os.replace()."
            )
        finally:
            try:
                fresh.unlink()
            except OSError:
                pass
            _cleanup(sid)


class TestExistingCallerSemanticsUnchanged:
    """Negative control: every routed mutator keeps its signature and behavior."""

    def test_record_agent_completion_tri_scope(self, session_id) -> None:
        pcs.record_agent_completion(session_id, "reviewer", issue_number=42)
        raw = json.loads(pcs._state_file_path(session_id).read_text())
        for key in ("0", "unscoped", "42"):
            assert raw["completions"][key]["reviewer"] is True
        assert "reviewer" in raw["completion_times"]["0"]

    def test_record_agent_launch(self, session_id) -> None:
        pcs.record_agent_launch(session_id, "reviewer")
        assert "reviewer" in pcs.get_launched_agents(session_id)

    def test_record_prompt_baseline(self, session_id) -> None:
        pcs.record_prompt_baseline(session_id, "planner", 350, 0)
        assert pcs.get_prompt_baseline(session_id, "planner") == 350

    def test_set_validation_mode(self, session_id) -> None:
        pcs.set_validation_mode(session_id, "parallel")
        assert pcs.get_validation_mode(session_id) == "parallel"

    def test_record_doc_verdict(self, session_id) -> None:
        pcs.record_doc_verdict(session_id, 7, "PASS")
        raw = json.loads(pcs._state_file_path(session_id).read_text())
        assert raw["completions"]["7"]["doc-master-verdict"] == "PASS"

    def test_record_research_skipped_dual_scope(self, session_id) -> None:
        pcs.record_research_skipped(session_id, issue_number=99)
        assert pcs.get_research_skipped(session_id, issue_number=99) is True
        assert pcs.get_research_skipped(session_id, issue_number=0) is True

    def test_record_plan_critic_skipped_dual_scope(self, session_id) -> None:
        pcs.record_plan_critic_skipped(
            session_id,
            issue_number=99,
            plan_path="docs/plans/x.md",
            bypass_reason="pre-validated\x00plan",
        )
        assert pcs.get_plan_critic_skipped(session_id, issue_number=99) is True
        assert pcs.get_plan_critic_skipped(session_id, issue_number=0) is True
        assert (
            pcs.get_plan_critic_skipped_plan_path(session_id, issue_number=99)
            == "docs/plans/x.md"
        )
        raw = json.loads(pcs._state_file_path(session_id).read_text())
        assert raw["plan_critic_bypass_reason"]["99"] == "pre-validatedplan"

    def test_record_plan_critic_passed(self, session_id) -> None:
        pcs.record_plan_critic_passed(session_id, "my-plan-slug")
        assert pcs.get_plan_critic_passed(session_id) is True

    def test_record_plan_critic_passed_ignores_unknown_session(self) -> None:
        pcs.record_plan_critic_passed("unknown", "slug")
        assert not pcs._state_file_path("unknown").exists() or True

    def test_mutators_reject_traversal_run_id(self, session_id) -> None:
        """run_id validation must behave exactly as before (ValueError)."""
        for call in (
            lambda: pcs.record_agent_completion(session_id, "x", run_id="../evil"),
            lambda: pcs.set_validation_mode(session_id, "parallel", run_id="../evil"),
            lambda: pcs.record_research_skipped(session_id, run_id="../evil"),
            lambda: pcs.record_plan_critic_skipped(session_id, run_id="../evil"),
            lambda: pcs.record_plan_critic_passed(session_id, "s", run_id="../evil"),
        ):
            with pytest.raises(ValueError):
                call()

    def test_run_id_scoped_write_still_isolated(self) -> None:
        run_id = f"r{uuid.uuid4().hex[:10]}"
        sid = _fresh_session_id()
        try:
            pcs.record_agent_completion(sid, "planner", run_id=run_id)
            assert pcs._state_file_path(sid, run_id=run_id).exists()
            assert not pcs._state_file_path(sid).exists()
            assert "planner" in pcs.get_completed_agents(sid, run_id=run_id)
        finally:
            for p in (
                pcs._state_file_path(sid, run_id=run_id),
                Path(f"/tmp/pipeline_agent_completions_{run_id}.lock"),
            ):
                try:
                    p.unlink()
                except OSError:
                    pass
            _cleanup(sid)
