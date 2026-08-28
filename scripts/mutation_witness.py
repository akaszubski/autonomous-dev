"""Mutation witness: a test counts only once observed FAILING on a mutated target.

Issue #1660. Every gate that accepts a new test measures QUANTITY --
``coverage_baseline.py`` exposes exactly four checks (``check_coverage_regression``,
``check_skip_regression``, ``check_test_count_regression``, ``check_skip_rate``)
and all four are counters. A test that cannot fail raises coverage, raises the
test count, is not a skip, and does not move the skip rate. The counter set is
not merely incomplete, it is *orthogonal* to the defect, so a fifth counter
cannot close it. This module supplies the missing property: DYNAMIC capability
to fail.

RELATIONSHIP TO #1667 -- A DIFFERENT PROPERTY, NOT A SECOND IMPLEMENTATION
--------------------------------------------------------------------------
``tests/unit/lib/test_vacuous_test_ratchet.py`` (#1667) closes the
CONSTANT-ASSERTION half: ``assert True`` / ``None`` / ``1``, detected statically
by ``find_vacuous_tests``. Static detection and mutation detection are different
properties. MEASURED on a minimal target::

    target: def add(a, b): return a + b
      unmutated  test_real     rc=0    assert add(2,3) == 5
      unmutated  test_vacuous  rc=0    assert add(2,3) is not None
    mutate to: return a - b
      MUTATED    test_real     rc=1   <- fails: GENUINE
      MUTATED    test_vacuous  rc=0   <- survives: VACUOUS

``assert add(2,3) is not None`` asserts no constant, so #1667's detector PASSES
it, yet it cannot fail for the reason it exists. That is the gap this module
closes. The zero-match refusal discipline is taken from
``scripts/integration_ceiling.py`` and #1667's subprocess harness -- this is a
third CONSUMER of a proven idiom, not a third implementation.

ENFORCEMENT BOUNDARY: THE HOOK EXISTS BUT IS DELIBERATELY NOT SHIPPED
---------------------------------------------------------------------
``hooks/mutation_witness_gate.py`` is the intended enforcement point and is
proven working under test, but it is **registered nowhere** -- absent from both
``install_manifest.json`` files and from both settings surfaces. Reason: nothing
in this repo PRODUCES a mutation claim yet, so the only behaviour a consumer
would ever see from a blocking ``SubagentStop`` gate is a false refusal. A
blocking hook with no producer is not a defensible default. The producer
(``agents/test-master.md`` plus coordinator wiring) is a separate change that
deserves its own review, and until it lands, **Issue #1660's enforcement loop is
OPEN**. That is recorded honestly rather than papered over.

``step5_quality_gate.run_quality_gate`` composes this module's
``check_mutation_witnesses`` next to the four counters, so the mechanism is
live in the pipeline even while the hook is not.

An earlier draft of this module argued the hook boundary was unaffordable
because a mutation cycle (~5.5 s) exceeds the 5,000 ms hook budget. That
reasoning rested on a false premise -- that raising a timeout slows every call.
**A timeout is a CEILING, not a delay.** MEASURED over a 7-day window (windowed
after 2026-08-21 to exclude the ``hook_timing.py:375`` labelling artifact)::

    total hook invocations in window : 84,339
      exceeded 5s                    :    266   (0.3154%)
      extra wait if allowed to finish : 803.8 SECONDS across the WHOLE window
    unified_pre_tool.py  n=33,408  p50 = 6.4ms  p99 = 2,217ms  max = 13,139ms

The median hook call is single-digit milliseconds; the budget is not binding for
99.7% of calls. Raising ``SubagentStop`` to 60s buys back the gate executions
that currently vanish silently, for ~13 minutes of extra wait spread over a
week. 60s is the value: ``Stop`` already carries a 60s slot in-tree, so the
runtime is known to accept it. Anything above 60s is UNVERIFIED here.

COST IS THE BINDING CONSTRAINT, SO EVERY BATCH IS BOUNDED EXPLICITLY
--------------------------------------------------------------------
MEASURED in THIS repo, not on a toy file. Re-measured with the exact flags
``_run_one_test`` uses::

    python3 -m pytest <real node id> -q --no-header -o addopts= \\
            -p no:cacheprovider -p no:randomly     # x5, PYTHONDONTWRITEBYTECODE=1

    median 3.58 s   (an earlier 3.39 s reading was ~6% optimistic)

A claim is two such runs plus a coverage-instrumented control, so ~7-11 s.
Import, conftest and collection dominate; the assertion is free.

Both consumers therefore schedule against a WALL DEADLINE rather than a claim
count, and claims that do not fit are DEFERRED with every unverified node id
NAMED. A partial verification that reads as a full one is the precise defect
this issue exists to kill.

CONCURRENCY AND CRASH SAFETY ARE NOT OPTIONAL HERE
---------------------------------------------------
This module edits source files in place, so two of its failure modes are
catastrophic rather than merely wrong:

* **Concurrent runs.** Two processes mutating the same target interleave such
  that one captures the other's MUTANT as its own "original" and restores THAT,
  leaving the file permanently corrupted while both report success. Reproduced
  at 3.8 s and 4.3 s stagger. Everything that touches a target or the claims
  queue now runs inside :func:`target_lock`.
* **Uncatchable kills.** ``finally`` covers exceptions and timeouts. It does NOT
  cover ``SIGKILL`` or the Claude Code runtime cutting a hook at its ceiling.
  :func:`_write_journal` parks the pre-mutation bytes and their digest before
  the mutant reaches disk; :func:`recover_inflight` repairs from that journal at
  the start of every entry point.

SCOPE -- deliberately narrow, because cost bounds the design
-------------------------------------------------------------
This applies to NEW tests and to any test CLAIMED as evidence that a guard
works. Full-suite mutation is explicitly out of scope. A per-run budget is
mandatory, and exceeding it produces a LOUD SKIP record -- never a silent pass.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, List, Optional, Sequence, Tuple

try:
    import fcntl

    _FCNTL_AVAILABLE = True
except ImportError:  # pragma: no cover - Windows
    _FCNTL_AVAILABLE = False

__all__ = [
    "ContendedError",
    "InvalidMutationError",
    "MutationClaim",
    "MutationWitnessError",
    "WitnessResult",
    "check_mutation_witnesses",
    "load_claims",
    "recover_inflight",
    "substitute",
    "target_lock",
    "witness_claim",
]

# --- pytest exit codes -------------------------------------------------------
# Named, because "non-zero exit" is NOT the same as "the test detected the
# mutation". Exit 5 (no tests collected) is non-zero and would certify a claim
# pointing at a test that does not exist -- see BYPASS HUNT shape 6 in
# tests/unit/lib/test_mutation_witness.py.
PYTEST_OK = 0
PYTEST_TESTS_FAILED = 1
PYTEST_INTERRUPTED = 2
PYTEST_INTERNAL_ERROR = 3
PYTEST_USAGE_ERROR = 4
PYTEST_NO_TESTS_COLLECTED = 5

#: Per-test wall budget applied to EACH subprocess run (control and mutant), in
#: seconds. Sized against the measured 3.58s median single-run cost with head
#: room for a cold interpreter. Exceeding it is a loud skip, never a pass.
DEFAULT_PER_TEST_BUDGET_S = 30.0

#: Overall wall budget for a whole ``check_mutation_witnesses`` sweep. The
#: pipeline consumer has no hook ceiling, but "no ceiling" is not "unbounded":
#: at ~7.2s per claim a 50-claim queue is ~6 minutes of silent single-threaded
#: work inside STEP 8. Claims past the deadline get ``SKIPPED_BUDGET``.
DEFAULT_OVERALL_BUDGET_S = 300.0

#: How long a claim waits for the exclusive mutation lock before giving up.
#: Sized at roughly two claims (~15s) so an ordinary neighbouring run is waited
#: out rather than declared contended.
DEFAULT_LOCK_TIMEOUT_S = 20.0

VERDICT_GENUINE = "GENUINE"
VERDICT_VACUOUS = "VACUOUS"
VERDICT_BROKEN_CONTROL = "BROKEN_CONTROL"
VERDICT_TAMPERED = "TAMPERED"
VERDICT_INDETERMINATE = "INDETERMINATE"
VERDICT_SKIPPED_BUDGET = "SKIPPED_BUDGET"
#: The named test does not execute the mutated line, so the mutant proves
#: nothing about it. This refuses the CLAIM, not the test.
VERDICT_UNCOUPLED = "UNCOUPLED"
#: The named test was SKIPPED in this environment (platform marker, missing
#: optional dependency). Nothing can be concluded about the test from here.
VERDICT_SKIPPED_ENV = "SKIPPED_ENV"
#: Another process held the mutation lock for longer than the wait. Nothing was
#: mutated and nothing was concluded.
VERDICT_CONTENDED = "CONTENDED"

#: Verdicts that BLOCK the gate.
#:
#: Everything absent from this set is reported LOUDLY and is never counted as
#: witnessed -- it just does not refuse. The distinction is deliberate and is
#: the fix for the false-refusal class (reviewer BLOCKING-4): ``VACUOUS`` is a
#: property of the (test, mutation) PAIR and blocks; ``SKIPPED_ENV``,
#: ``UNCOUPLED``, ``CONTENDED`` and ``SKIPPED_BUDGET`` are properties of the
#: ENVIRONMENT or the CLAIM, and a gate that refuses a sound test because this
#: machine skipped it, or because the anchor pointed at the wrong function, is
#: a wolf-crier.
BLOCKING_VERDICTS = frozenset(
    {VERDICT_VACUOUS, VERDICT_BROKEN_CONTROL, VERDICT_TAMPERED, VERDICT_INDETERMINATE}
)

_PASSED_RE = re.compile(r"(\d+)\s+passed")
_SKIPPED_RE = re.compile(r"(\d+)\s+skipped")

#: Exclusive lock guarding the whole mutate/run/restore sequence AND the claims
#: queue's read-modify-write. One global lock rather than one per target: the
#: queue is shared state too, and two locks would need an ordering rule nobody
#: would remember.
LOCK_RELATIVE = Path(".claude") / "local" / ".mutation_witness.lock"

#: Crash journal. Written BEFORE the target is mutated and deleted after it is
#: restored, so an UNCATCHABLE kill (SIGKILL, or the Claude Code runtime cutting
#: a hook at its ceiling) leaves a repairable record instead of a silently
#: mutated source file.
JOURNAL_RELATIVE = Path(".claude") / "local" / ".mutation_inflight.json"

#: Where the pre-mutation bytes are parked while the mutant is on disk.
BACKUP_DIR_RELATIVE = Path(".claude") / "local" / ".mutation_backup"


class MutationWitnessError(Exception):
    """Base error for the mutation witness harness."""


class ContendedError(MutationWitnessError):
    """Another process held the mutation lock past the wait.

    Raised rather than returned so no caller can mistake it for a verdict about
    the test. :func:`witness_claim` converts it into ``VERDICT_CONTENDED``.
    """


class InvalidMutationError(MutationWitnessError):
    """The proposed mutation cannot prove anything and must not be run.

    Raised when the anchor matches zero or many times, when the target is
    missing or is not Python, when the mutation breaks syntax, or when the
    mutation is semantically inert (a comment/whitespace-only edit).
    """


@contextlib.contextmanager
def target_lock(
    repo_root: Path, *, timeout_s: float = DEFAULT_LOCK_TIMEOUT_S
) -> Iterator[None]:
    """Hold the exclusive mutation lock for the duration of the block.

    WHY THIS EXISTS (reviewer BLOCKING-1, reproduced): the original code read
    ``original_bytes`` BEFORE the control run. A second process starting inside
    the first one's mutation window captured the FIRST process's MUTANT as its
    own "original" and wrote it back on the way out. Both processes then
    compared the file against their own stale snapshot, both reported GENUINE,
    and the target was left permanently mutated. This is reachable in
    production: Claude Code dispatches subagents in parallel, and
    ``step5_quality_gate`` is a second concurrent consumer of the same function.

    The fix is not "read later" -- it is that the whole read/mutate/run/restore
    sequence must be one critical section. Everything that touches the target or
    the claims queue takes THIS lock.

    Args:
        repo_root: Repository root; the lock file lives beneath it.
        timeout_s: How long to wait for the lock before giving up.

    Yields:
        None, with the lock held.

    Raises:
        ContendedError: If the lock was not acquired within ``timeout_s``.
    """
    lock_path = repo_root / LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if not _FCNTL_AVAILABLE:  # pragma: no cover - Windows
        # Stated, not hidden: without fcntl there is no mutual exclusion and the
        # BLOCKING-1 corruption is reachable again. Refuse rather than pretend.
        raise ContendedError(
            "fcntl is unavailable on this platform, so the mutation lock cannot "
            "be taken.\n"
            "Expected: a POSIX platform providing fcntl.flock\n"
            "Running unlocked would permit concurrent runs to corrupt the "
            "target permanently while both report success."
        )

    handle = lock_path.open("a+")
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ContendedError(
                        f"another process held {lock_path} for longer than "
                        f"{timeout_s:g}s.\n"
                        f"Expected: exclusive access to mutate the target\n"
                        f"Nothing was mutated and nothing was concluded about "
                        f"the test."
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _sha256(data: bytes) -> str:
    """Hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def _write_journal(repo_root: Path, target: Path, original_bytes: bytes) -> Path:
    """Park the pre-mutation bytes and record where they went.

    Written BEFORE the mutant hits disk. ``finally`` covers a raised exception
    and a timeout; it does NOT cover SIGKILL, and it does not cover the Claude
    Code runtime cutting a hook at its own ceiling -- which is precisely the
    scenario this whole mechanism runs inside. The journal is what makes those
    recoverable.

    Args:
        repo_root: Repository root; journal and backup live beneath it.
        target: File about to be mutated.
        original_bytes: Its exact current contents.

    Returns:
        Path of the journal file.
    """
    digest = _sha256(original_bytes)
    backup_dir = repo_root / BACKUP_DIR_RELATIVE
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{target.name}.{digest[:16]}.bak"
    backup.write_bytes(original_bytes)

    journal = repo_root / JOURNAL_RELATIVE
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        json.dumps(
            {
                "target": str(target),
                "sha256_original": digest,
                "backup": str(backup),
                "pid": os.getpid(),
                "started": time.time(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return journal


def _clear_journal(repo_root: Path) -> None:
    """Delete the journal and its backup. Never raises."""
    journal = repo_root / JOURNAL_RELATIVE
    try:
        data = json.loads(journal.read_text(encoding="utf-8"))
        backup = Path(str(data.get("backup", "")))
        if backup.name:
            backup.unlink(missing_ok=True)
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    with contextlib.suppress(OSError):
        journal.unlink(missing_ok=True)


def recover_inflight(repo_root: Path) -> List[str]:
    """Repair a target left mutated by an uncatchable kill.

    Called at the START of every entry point, before anything else runs. A
    journal on disk means a previous run died between mutating and restoring;
    the backup is written back and verified by digest.

    Args:
        repo_root: Repository root to inspect.

    Returns:
        Human-readable lines describing what was repaired. Empty when there was
        nothing to repair -- which is the ordinary case, so callers must not
        treat an empty list as a failure.
    """
    journal = repo_root / JOURNAL_RELATIVE
    if not journal.exists():
        return []

    try:
        data = json.loads(journal.read_text(encoding="utf-8"))
        target = Path(str(data["target"]))
        expected = str(data["sha256_original"])
        backup = Path(str(data["backup"]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        _clear_journal(repo_root)
        return [
            f"RECOVERY: a mutation journal at {journal} was unreadable ({exc}); "
            f"it has been removed. Check `git diff` for a target left mutated."
        ]

    lines: List[str] = []
    try:
        current = target.read_bytes() if target.is_file() else b""
        if _sha256(current) == expected:
            lines.append(
                f"RECOVERY: {target} was already intact; a stale journal from a "
                f"killed run has been cleared."
            )
        elif backup.is_file() and _sha256(backup.read_bytes()) == expected:
            shutil.copyfile(backup, target)
            restored_ok = _sha256(target.read_bytes()) == expected
            lines.append(
                f"RECOVERY: {target} was left MUTATED by a killed run and has "
                f"been restored from {backup} "
                f"({'verified' if restored_ok else 'VERIFICATION FAILED'})."
            )
        else:
            lines.append(
                f"RECOVERY FAILED: {target} does not match its pre-mutation "
                f"digest and the backup at {backup} is missing or corrupt.\n"
                f"Expected sha256 {expected}\n"
                f"Restore the file from git before running any further claims."
            )
            return lines
    finally:
        _clear_journal(repo_root)
    return lines


def substitute(source: str, anchor: str, replacement: str) -> str:
    """Replace ``anchor`` exactly once, refusing a zero-match or ambiguous edit.

    This is the ``scripts/integration_ceiling.py`` / #1667 discipline: a harness
    whose anchor matches nothing mutates nothing and then reports a false green.
    A zero-match RAISES; it never silently "passes".

    Args:
        source: Original source text.
        anchor: Exact substring that must appear exactly once.
        replacement: Text to substitute for ``anchor``.

    Returns:
        The mutated source text.

    Raises:
        InvalidMutationError: If ``anchor`` appears zero or more than one time,
            or if ``replacement`` is identical to ``anchor``.
    """
    if anchor == replacement:
        raise InvalidMutationError(
            f"anchor and replacement are identical ({anchor!r})\n"
            f"Expected: a replacement that changes the target's behaviour\n"
            f"A no-op edit produces a mutant identical to the original, so the "
            f"test would 'survive' something that never happened."
        )
    count = source.count(anchor)
    if count != 1:
        raise InvalidMutationError(
            f"anchor {anchor!r} appears {count} time(s), expected exactly 1\n"
            f"Expected: a unique anchor in the target source\n"
            f"A zero-match anchor mutates nothing and reports a false green; an "
            f"ambiguous anchor mutates more than the claim describes. Re-anchor."
        )
    return source.replace(anchor, replacement)


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Return ``tree`` with every docstring removed.

    ``ast.dump`` includes docstring ``Constant`` values, so a docstring-only
    edit produced a DIFFERENT dump and sailed through the inertness check --
    then every test survived it and was condemned as VACUOUS with "delete the
    test" as the remedy (reviewer BLOCKING-4, reproduced through the live hook).
    A docstring is documentation, not behaviour, so it is dropped before the
    comparison and such an edit is refused like a comment-only one.

    Args:
        tree: Parsed module AST. Mutated in place and returned.

    Returns:
        The same tree, with leading string expressions removed from every
        ``Module``, ``FunctionDef``, ``AsyncFunctionDef`` and ``ClassDef``.
    """
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            # A body cannot be empty; leave a Pass so the tree stays valid and
            # two bodies that differ ONLY in docstring still compare equal.
            node.body = body[1:] or [ast.Pass()]
    return tree


def _assert_mutation_is_semantic(original: str, mutated: str, target: Path) -> None:
    """Refuse a mutation that cannot change behaviour.

    A "mutation" that only touches a comment, a docstring or formatting leaves
    behaviour identical. Such an edit proves nothing: every test survives it, so
    a harness that accepted it would report every test as vacuous. The mutation
    must be COUPLED to the assertion, so a behavioural no-op is rejected up
    front rather than converted into a false accusation against the test.

    Args:
        original: Source text before mutation.
        mutated: Source text after mutation.
        target: Path of the mutated file, for the error message.

    Raises:
        InvalidMutationError: If the mutant does not parse, or parses to an AST
            indistinguishable from the original once docstrings are stripped.
    """
    try:
        original_tree = ast.parse(original)
    except SyntaxError as exc:  # pragma: no cover - target is importable code
        raise InvalidMutationError(
            f"target {target} does not parse before mutation: {exc}\n"
            f"Expected: valid Python at the target path\n"
            f"The harness cannot attribute a failure to the mutation if the "
            f"original is already broken."
        ) from exc
    try:
        mutated_tree = ast.parse(mutated)
    except SyntaxError as exc:
        raise InvalidMutationError(
            f"mutation makes {target} unparseable: {exc}\n"
            f"Expected: a mutant that still imports\n"
            f"A syntax-breaking mutant fails EVERY test that imports the target, "
            f"certifying all of them as genuine. Mutate behaviour, not syntax."
        ) from exc

    if ast.dump(_strip_docstrings(original_tree)) == ast.dump(
        _strip_docstrings(mutated_tree)
    ):
        raise InvalidMutationError(
            f"mutation of {target} changes no behaviour (identical AST once "
            f"docstrings are stripped)\n"
            f"Expected: a mutation coupled to the behaviour the test asserts\n"
            f"Comment-only, docstring-only, whitespace-only and formatting-only "
            f"edits are survived by EVERY test, so they say nothing about this "
            f"one. Re-anchor the claim on the expression the test asserts about; "
            f"do not change the test."
        )


@dataclass(frozen=True)
class MutationClaim:
    """A test paired with a mutation of the code it claims to cover.

    Attributes:
        test: pytest node id of the ONE test to re-run (``path::name``).
        target: Path to the ``.py`` file the test claims to cover.
        anchor: Exact, unique source substring to replace in ``target``.
        replacement: Text to substitute for ``anchor``.
    """

    test: str
    target: Path
    anchor: str
    replacement: str

    @classmethod
    def from_dict(cls, data: dict, *, repo_root: Path) -> "MutationClaim":
        """Build a claim from a JSON object, resolving ``target`` under the repo.

        Args:
            data: Mapping with ``test``, ``target``, ``anchor``, ``replacement``.
            repo_root: Root used to resolve a relative ``target``.

        Returns:
            The parsed :class:`MutationClaim`.

        Raises:
            InvalidMutationError: If a required key is missing or not a string.
        """
        missing = [k for k in ("test", "target", "anchor", "replacement") if k not in data]
        if missing:
            raise InvalidMutationError(
                f"mutation claim is missing key(s): {', '.join(missing)}\n"
                f"Expected: {{'test', 'target', 'anchor', 'replacement'}}\n"
                f"Got: {sorted(data)}"
            )
        target = Path(str(data["target"]))
        if not target.is_absolute():
            target = repo_root / target
        return cls(
            test=str(data["test"]),
            target=target,
            anchor=str(data["anchor"]),
            replacement=str(data["replacement"]),
        )


@dataclass(frozen=True)
class WitnessResult:
    """Verdict for one :class:`MutationClaim`.

    Attributes:
        claim: The claim that was driven.
        verdict: One of the ``VERDICT_*`` constants.
        message: Human-readable explanation naming the exact next action.
        control_returncode: Exit code of the unmutated run, or None if not run.
        mutant_returncode: Exit code of the mutated run, or None if not run.
        elapsed_s: Wall time consumed by both runs.
    """

    claim: MutationClaim
    verdict: str
    message: str
    control_returncode: Optional[int] = None
    mutant_returncode: Optional[int] = None
    elapsed_s: float = 0.0

    @property
    def witnessed(self) -> bool:
        """True only when the test was OBSERVED failing against the mutant."""
        return self.verdict == VERDICT_GENUINE

    @property
    def blocking(self) -> bool:
        """True when this verdict must fail the gate."""
        return self.verdict in BLOCKING_VERDICTS


def _run_one_test(
    *, nodeid: str, cwd: Path, budget_s: float, disable_plugin_autoload: bool = False
) -> "subprocess.CompletedProcess[str]":
    """Run exactly one pytest node id in a subprocess.

    ``-o addopts=`` clears the repo's coverage addopts: the witness needs the
    test's verdict, not a coverage report, and coverage roughly triples the run.
    ``PYTHONDONTWRITEBYTECODE`` stops a stale ``__pycache__`` entry shadowing the
    mutated target.

    Args:
        nodeid: pytest node id to run.
        cwd: Working directory for the run.
        budget_s: Per-run wall budget, passed as the subprocess timeout.
        disable_plugin_autoload: Set ``PYTEST_DISABLE_PLUGIN_AUTOLOAD``. MEASURED
            on this repo: 3.53s -> 0.16s per run. Default False because a real
            repo test may need an autoloaded plugin (``pytest-asyncio``,
            ``hypothesis``) and a missing fixture would read as a failure. Turn
            it on only for self-contained targets.

    Returns:
        The completed process.

    Raises:
        subprocess.TimeoutExpired: If the run exceeds ``budget_s``.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if disable_plugin_autoload:
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            nodeid,
            "-q",
            "--no-header",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:randomly",
        ],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
        timeout=budget_s,
    )


def _passed_count(stdout: str) -> int:
    """Number of tests pytest reported as passed, 0 when it reported none."""
    matches = _PASSED_RE.findall(stdout)
    return int(matches[-1]) if matches else 0


def _skipped_count(stdout: str) -> int:
    """Number of tests pytest reported as skipped, 0 when it reported none."""
    matches = _SKIPPED_RE.findall(stdout)
    return int(matches[-1]) if matches else 0


def _anchor_line_number(source: str, anchor: str) -> int:
    """1-based line on which ``anchor`` starts. Assumes a unique match."""
    return source.count("\n", 0, source.index(anchor)) + 1


def _executed_lines(
    *, nodeid: str, target: Path, cwd: Path, budget_s: float, disable_plugin_autoload: bool
) -> "Optional[set[int]]":
    """Lines of ``target`` the named test actually executes.

    Reviewer BLOCKING-4, part 2: a mutation the test never reaches survives, and
    the survival was being reported as VACUOUS -- an accusation against a sound
    test for what is really a mis-anchored CLAIM. Coverage is the honest signal
    for "did this test reach that line".

    Args:
        nodeid: pytest node id to run.
        target: File whose executed lines are wanted.
        cwd: Working directory for the run.
        budget_s: Wall budget for this run.
        disable_plugin_autoload: When True, pytest-cov cannot autoload either, so
            the probe is unavailable and returns None.

    Returns:
        Executed line numbers, or None when coverage could not be measured.
        None means UNKNOWN and callers must not read it as "reached nothing" --
        a probe returning nothing is not evidence of nothing.
    """
    if disable_plugin_autoload:
        return None

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    report = cwd / ".claude" / "local" / f".mutation_cov_{os.getpid()}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                sys.executable, "-m", "pytest", nodeid, "-q", "--no-header",
                "-o", "addopts=", "-p", "no:cacheprovider", "-p", "no:randomly",
                # The target's DIRECTORY, not the file. MEASURED: coverage's
                # source spec silently matches nothing for a file path and the
                # run reports "No data to report" -- which this function would
                # have read as None, i.e. UNKNOWN, i.e. the coupling check
                # quietly never running.
                f"--cov={target.parent}", f"--cov-report=json:{report}",
            ],
            capture_output=True, text=True, cwd=str(cwd), env=env, timeout=budget_s,
        )
        data = json.loads(report.read_text(encoding="utf-8"))
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, ValueError):
        return None
    finally:
        with contextlib.suppress(OSError):
            report.unlink(missing_ok=True)

    files = data.get("files", {})
    if not isinstance(files, dict) or not files:
        return None
    resolved_target = target.resolve()
    for name, entry in files.items():
        # Report keys are relative to the SUBPROCESS cwd, not to ours.
        candidate = Path(name)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        try:
            same = candidate.resolve() == resolved_target
        except OSError:  # pragma: no cover - unresolvable path
            same = False
        if same:
            executed = entry.get("executed_lines")
            return set(executed) if isinstance(executed, list) else None
    return None


def witness_claim(
    claim: MutationClaim,
    *,
    repo_root: Path,
    budget_s: float = DEFAULT_PER_TEST_BUDGET_S,
    disable_plugin_autoload: bool = False,
    lock_timeout_s: float = DEFAULT_LOCK_TIMEOUT_S,
) -> WitnessResult:
    """Mutate the target, re-run the ONE test, require a non-zero exit, restore.

    The sequence is control-then-mutant, because a mutant-only reading cannot
    distinguish "the test caught the mutation" from "the test was already
    failing" or "the node id matches nothing" (pytest exits 4 or 5, both
    non-zero).

    CRASH SAFETY, stated precisely. The ``finally`` restore covers a raised
    exception and a subprocess timeout -- both are tested. It does NOT cover
    ``SIGKILL``, and it does not cover the Claude Code runtime cutting a hook
    off at its own ceiling. Those residuals are covered by the JOURNAL: the
    pre-mutation bytes and their digest are written to
    ``.claude/local/.mutation_inflight.json`` before the mutant reaches disk,
    and :func:`recover_inflight` repairs from it at the next entry.

    CONCURRENCY. The entire read/mutate/run/restore sequence runs inside
    :func:`target_lock`. Reading ``original_bytes`` outside it permitted a second
    process to snapshot the first one's MUTANT as its own original, restore that,
    and leave the file permanently corrupted with both runs reporting GENUINE.

    Args:
        claim: Test/target/anchor/replacement to drive.
        repo_root: Working directory for both pytest runs.
        budget_s: Per-run wall budget in seconds. Exceeding it yields
            ``SKIPPED_BUDGET`` -- loud, and never counted as witnessed.
        disable_plugin_autoload: Forwarded to the pytest subprocess; see
            :func:`_run_one_test`. Also disables the coverage-coupling probe,
            since pytest-cov cannot autoload either.
        lock_timeout_s: How long to wait for the mutation lock before returning
            ``VERDICT_CONTENDED``.

    Returns:
        A :class:`WitnessResult`.

    Raises:
        InvalidMutationError: If the target is missing, is not a ``.py`` file,
            the anchor matches other than exactly once, the mutant does not
            parse, or the mutation changes no behaviour.
        MutationWitnessError: If the target could not be restored afterwards.
    """
    target = claim.target
    if not target.is_file():
        raise InvalidMutationError(
            f"mutation target not found: {target}\n"
            f"Expected: an existing .py file the test covers\n"
            f"A claim whose target cannot be located must FAIL CLOSED. Silently "
            f"no-opping would certify the test on the strength of a typo."
        )
    if target.suffix != ".py":
        raise InvalidMutationError(
            f"mutation target is not Python: {target}\n"
            f"Expected: a .py file\n"
            f"Behavioural inertness is checked by comparing ASTs; a non-Python "
            f"target cannot be checked, so it is refused rather than trusted."
        )

    started = _now()
    try:
        lock = target_lock(repo_root, timeout_s=lock_timeout_s)
        lock.__enter__()
    except ContendedError as exc:
        return WitnessResult(
            claim=claim,
            verdict=VERDICT_CONTENDED,
            message=(
                f"CONTENDED: {claim.test} was not verified because {exc}\n"
                f"Nothing was mutated. Re-run when the other process finishes; "
                f"this says NOTHING about the test."
            ),
            elapsed_s=_now() - started,
        )

    control: "subprocess.CompletedProcess[str] | None" = None
    mutant: "subprocess.CompletedProcess[str] | None" = None
    timed_out_phase: Optional[str] = None
    tampered = False
    uncoupled = False
    coupling_measured = False

    try:
        # Read INSIDE the lock. This line's position is the BLOCKING-1 fix.
        original_bytes = target.read_bytes()
        original_text = original_bytes.decode("utf-8")
        mutated_text = substitute(original_text, claim.anchor, claim.replacement)
        _assert_mutation_is_semantic(original_text, mutated_text, target)
        mutated_bytes = mutated_text.encode("utf-8")
        anchor_line = _anchor_line_number(original_text, claim.anchor)

        run_kwargs = {
            "nodeid": claim.test,
            "cwd": repo_root,
            "budget_s": budget_s,
            "disable_plugin_autoload": disable_plugin_autoload,
        }
        journalled = False
        try:
            try:
                control = _run_one_test(**run_kwargs)
            except subprocess.TimeoutExpired:
                timed_out_phase = "control"

            control_usable = (
                timed_out_phase is None
                and control is not None
                and control.returncode == PYTEST_OK
                and _passed_count(control.stdout) >= 1
            )
            if control_usable:
                executed = _executed_lines(
                    nodeid=claim.test,
                    target=target,
                    cwd=repo_root,
                    budget_s=budget_s,
                    disable_plugin_autoload=disable_plugin_autoload,
                )
                # None means the probe could not measure, NOT "reached nothing".
                uncoupled = executed is not None and anchor_line not in executed
                coupling_measured = executed is not None

            if control_usable and not uncoupled:
                _write_journal(repo_root, target, original_bytes)
                journalled = True
                target.write_bytes(mutated_bytes)
                try:
                    mutant = _run_one_test(**run_kwargs)
                except subprocess.TimeoutExpired:
                    timed_out_phase = "mutant"
                # A test that rewrites its own target back would "fail" against a
                # mutant that no longer exists. Read back BEFORE restoring.
                tampered = target.read_bytes() != mutated_bytes
        finally:
            target.write_bytes(original_bytes)
            if journalled:
                _clear_journal(repo_root)

        if target.read_bytes() != original_bytes:  # pragma: no cover - disk failure
            raise MutationWitnessError(
                f"failed to restore {target} after mutation\n"
                f"Expected: byte-identical restoration\n"
                f"The working tree is now dirty; restore it from git before "
                f"continuing."
            )
    finally:
        lock.__exit__(None, None, None)

    return _verdict(
        claim=claim,
        control=control,
        mutant=mutant,
        timed_out_phase=timed_out_phase,
        tampered=tampered,
        uncoupled=uncoupled,
        coupling_measured=coupling_measured,
        anchor_line=anchor_line,
        budget_s=budget_s,
        elapsed_s=_now() - started,
    )


def _now() -> float:
    """Monotonic seconds; isolated so tests can reason about elapsed time."""
    return time.monotonic()


def _verdict(
    *,
    claim: MutationClaim,
    control: "subprocess.CompletedProcess[str] | None",
    mutant: "subprocess.CompletedProcess[str] | None",
    timed_out_phase: Optional[str],
    tampered: bool,
    uncoupled: bool,
    coupling_measured: bool,
    anchor_line: int,
    budget_s: float,
    elapsed_s: float,
) -> WitnessResult:
    """Turn two subprocess outcomes into a verdict. Pure, so it is testable."""

    def build(verdict: str, message: str) -> WitnessResult:
        return WitnessResult(
            claim=claim,
            verdict=verdict,
            message=message,
            control_returncode=None if control is None else control.returncode,
            mutant_returncode=None if mutant is None else mutant.returncode,
            elapsed_s=elapsed_s,
        )

    pair = f"claim ({claim.test} <-> {claim.target}:{anchor_line})"

    if timed_out_phase is not None:
        return build(
            VERDICT_SKIPPED_BUDGET,
            f"SKIPPED (budget): {claim.test} exceeded the {budget_s:g}s per-test "
            f"budget during the {timed_out_phase} run. This test is NOT witnessed "
            f"and does NOT count as covered. Shorten it, or raise budget_s "
            f"deliberately -- a slow test is not evidence of a vacuous one, and a "
            f"budget skip is never a silent pass.",
        )

    control_skipped = (
        control is not None
        and control.returncode == PYTEST_OK
        and _passed_count(control.stdout) < 1
        and _skipped_count(control.stdout) >= 1
    )
    if control_skipped:
        return build(
            VERDICT_SKIPPED_ENV,
            f"SKIPPED (environment): {claim.test} was SKIPPED on this machine "
            f"(platform marker, missing optional dependency, or a conditional "
            f"skipif), so it never executed and nothing can be concluded about "
            f"it. NOT a verdict on the test and NOT a refusal. Re-run where the "
            f"test is applicable, or move the claim to a test that runs here.",
        )

    if control is None or control.returncode != PYTEST_OK or _passed_count(control.stdout) < 1:
        rc = "n/a" if control is None else control.returncode
        detail = ""
        if control is not None and control.returncode in (
            PYTEST_USAGE_ERROR,
            PYTEST_NO_TESTS_COLLECTED,
        ):
            detail = (
                f" pytest exit {control.returncode} means the node id matched "
                f"NOTHING -- almost always a stale or mistyped node id in the "
                f"CLAIM. Non-zero exit alone would have certified this claim; "
                f"the control run is what catches it."
            )
        return build(
            VERDICT_BROKEN_CONTROL,
            f"BROKEN CONTROL for {pair}: the test did not pass on the UNMUTATED "
            f"target (exit {rc}, "
            f"{0 if control is None else _passed_count(control.stdout)} passed)."
            f"{detail}\nA mutant verdict is uninterpretable until the control "
            f"passes. Resolutions, in order: (1) correct the node id in the "
            f"claim; (2) if the test is genuinely failing for an unrelated "
            f"reason, fix that first; (3) withdraw the claim.",
        )

    if uncoupled:
        return build(
            VERDICT_UNCOUPLED,
            f"UNCOUPLED {pair}: the test PASSES, but coverage shows it never "
            f"executes {claim.target.name}:{anchor_line}, so mutating that line "
            f"could not possibly have made it fail. This refuses the CLAIM, not "
            f"the test -- re-anchor onto a line this test actually reaches, or "
            f"name a different test. NOT a refusal and NOT witnessed.",
        )

    if tampered:
        return build(
            VERDICT_TAMPERED,
            f"TAMPERED: {claim.test} rewrote {claim.target} during the run, so "
            f"the mutant it was judged against no longer existed on disk. If the "
            f"test does not write to that path, suspect a fixture or a sibling "
            f"process; otherwise remove the write.",
        )

    assert mutant is not None  # timed_out_phase is None and control passed
    if mutant.returncode == PYTEST_TESTS_FAILED:
        return build(
            VERDICT_GENUINE,
            f"GENUINE: {claim.test} passed on the original and FAILED on the "
            f"mutant ({claim.anchor!r} -> {claim.replacement!r}). Witnessed in "
            f"{elapsed_s:.1f}s.",
        )
    if mutant.returncode == PYTEST_OK:
        # Only claim reachability when the coverage probe actually measured it.
        # Asserting "the test reaches line N" off an UNKNOWN would be the same
        # unearned confidence this module exists to remove.
        reach = (
            f"the test reaches {claim.target.name}:{anchor_line} and"
            if coupling_measured
            else (
                f"coverage could not be measured here, so whether the test even "
                f"reaches {claim.target.name}:{anchor_line} is UNKNOWN; it"
            )
        )
        return build(
            VERDICT_VACUOUS,
            f"VACUOUS {pair}: {reach} "
            f"still passes when it is changed "
            f"({claim.anchor!r} -> {claim.replacement!r}), so it is not evidence "
            f"that line works. VACUOUS is a property of the (test, mutation) "
            f"PAIR, not a judgement of the test alone. Resolutions, in order: "
            f"(1) re-anchor the claim if it targets the wrong behaviour; "
            f"(2) strengthen the assertion to depend on the mutated value; "
            f"(3) withdraw the claim. A static constant-assertion detector "
            f"(#1667) passes this shape, which is why the mutation is needed.",
        )
    return build(
        VERDICT_INDETERMINATE,
        f"INDETERMINATE: the mutated run of {claim.test} exited "
        f"{mutant.returncode}, which is neither pass (0) nor test-failure (1). "
        f"Exit 2/3/4/5 mean interrupted, internal error, usage error or nothing "
        f"collected -- none of them is the test detecting the mutation. Failing "
        f"closed.\n{mutant.stdout[-2000:]}",
    )


def load_claims(claims_path: Path, *, repo_root: Path) -> List[MutationClaim]:
    """Read mutation claims from JSON.

    Accepts either a bare list of claim objects or ``{"claims": [...]}``.

    Args:
        claims_path: File to read.
        repo_root: Root used to resolve relative ``target`` paths.

    Returns:
        The parsed claims, empty when the file does not exist.

    Raises:
        InvalidMutationError: If the file exists but is not readable JSON of the
            expected shape. A malformed claims file fails closed -- treating it
            as "no claims" is the silent pass this module exists to remove.
    """
    if not claims_path.exists():
        return []
    try:
        data: Any = json.loads(claims_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise InvalidMutationError(
            f"mutation claims file is unreadable: {claims_path}: {exc}\n"
            f"Expected: JSON list, or an object with a 'claims' list\n"
            f"Refusing to read an unparseable claims file as 'no claims'."
        ) from exc

    if isinstance(data, dict):
        data = data.get("claims", [])
    if not isinstance(data, list):
        raise InvalidMutationError(
            f"mutation claims file has the wrong shape: {claims_path}\n"
            f"Expected: JSON list, or an object with a 'claims' list\n"
            f"Got: {type(data).__name__}"
        )
    return [MutationClaim.from_dict(item, repo_root=repo_root) for item in data]


def check_mutation_witnesses(
    claims: Optional[Sequence[MutationClaim]] = None,
    *,
    repo_root: Optional[Path] = None,
    claims_path: Optional[Path] = None,
    budget_s: float = DEFAULT_PER_TEST_BUDGET_S,
    disable_plugin_autoload: bool = False,
    overall_budget_s: float = DEFAULT_OVERALL_BUDGET_S,
) -> Tuple[bool, str]:
    """Drive every claim and report a single ``(passed, message)`` verdict.

    Composed by ``step5_quality_gate.run_quality_gate`` ALONGSIDE the four
    counters in ``coverage_baseline.py``, not as a fifth counter: this check
    asks whether a test CAN fail, which no count can answer.

    Args:
        claims: Claims to drive. When None they are loaded from ``claims_path``.
        repo_root: Working directory for the runs. Defaults to ``Path.cwd()``.
        claims_path: Claims JSON, default ``.claude/local/mutation_claims.json``
            under ``repo_root``, overridable via ``$MUTATION_CLAIMS_PATH``.
        budget_s: Per-test wall budget in seconds.
        disable_plugin_autoload: Forwarded to each run; see :func:`_run_one_test`.
        overall_budget_s: Wall budget for the whole sweep. This consumer has no
            hook ceiling, but "no ceiling" is not "unbounded" -- a 50-claim queue
            is minutes of silent single-threaded work inside STEP 8. Claims past
            the deadline are reported as ``SKIPPED_BUDGET`` and NAMED.

    Returns:
        ``(passed, message)``. ``passed`` is False when any claim is VACUOUS,
        TAMPERED, INDETERMINATE, has a broken control, or is itself invalid.
        Zero claims passes with an explicit "0 claims" message -- an absent
        declaration is a known, NAMED gap, not a silent success.
    """
    root = (repo_root or Path.cwd()).resolve()
    # Repair before anything else: a journal on disk means a previous run was
    # killed between mutating and restoring, and every reading taken against a
    # still-mutated target would be wrong.
    recovery = recover_inflight(root)
    if claims is None:
        if claims_path is None:
            env_path = os.environ.get("MUTATION_CLAIMS_PATH")
            claims_path = (
                Path(env_path)
                if env_path
                else root / ".claude" / "local" / "mutation_claims.json"
            )
        try:
            claims = load_claims(claims_path, repo_root=root)
        except InvalidMutationError as exc:
            return (False, f"Mutation witness FAILED to read its input: {exc}")

    if not claims:
        return (
            True,
            "\n".join(
                recovery
                + [
                    "Mutation witness: 0 claims declared (nothing was proven "
                    "capable of failing). Declare NEW tests and any test claimed "
                    "as guard evidence in .claude/local/mutation_claims.json."
                ]
            ),
        )

    results: List[WitnessResult] = []
    invalid: List[str] = []
    unreached: List[MutationClaim] = []
    deadline = _now() + overall_budget_s
    for index, claim in enumerate(claims):
        if _now() >= deadline:
            unreached.extend(claims[index:])
            break
        try:
            results.append(
                witness_claim(
                    claim,
                    repo_root=root,
                    budget_s=budget_s,
                    disable_plugin_autoload=disable_plugin_autoload,
                )
            )
        except InvalidMutationError as exc:
            invalid.append(f"{claim.test}: {exc}")

    witnessed = [r for r in results if r.witnessed]
    blocked = [r for r in results if r.blocking]
    # Loud, non-blocking outcomes: reported by name, never counted as witnessed.
    inconclusive = [
        r for r in results if not r.witnessed and not r.blocking
    ]

    lines = list(recovery)
    lines.append(
        f"Mutation witness: {len(witnessed)}/{len(claims)} claim(s) observed "
        f"failing against a mutated target."
    )
    if unreached:
        lines.append(
            f"SKIPPED (budget): {len(unreached)} claim(s) were not reached "
            f"within the {overall_budget_s:g}s sweep budget. NOT verified, NOT "
            f"passed:"
        )
        lines.extend(f"    {c.test}" for c in unreached)
    for r in inconclusive:
        lines.append(f"  - {r.message}")
    for r in blocked:
        lines.append(f"  - {r.message}")
    for text in invalid:
        lines.append(f"  - INVALID MUTATION: {text}")

    passed = not blocked and not invalid
    return (passed, "\n".join(lines))
