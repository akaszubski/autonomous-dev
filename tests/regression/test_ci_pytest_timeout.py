"""Regression tests for CI test-signal integrity across ``.github/workflows/``.

Three classes of defect are guarded here, all instances of the same disease —
CI producing either an ABSENCE where a test result should be, or noise
indistinguishable from one:

* **Issue #1567 — unbounded pytest invocations.** A hung test burns the job's
  whole budget; the job is recorded ``cancelled`` with zero results.
* **Issue #1580 — sibling-step suppression.** A red suite silently SKIPS the
  suites after it, so two thirds of the surface is never seen.
* **Issue #1580, second layer — ungated prerequisites.** The fix for the
  above (``!cancelled()``) REMOVES GitHub's implicit ``success()``, which was
  the only thing stopping the suites running on top of a failed
  ``pip install`` and emitting ``ModuleNotFoundError`` for every test. Each
  prerequisite must therefore be gated on explicitly.

Issue #1567: a single hung test (``test_display_loop_polls_file``) span
forever in a poll loop. The ``Full Test Suite`` job burned its entire
60-minute budget on every push and was recorded by GitHub Actions as
``cancelled`` — producing no test results at all, for roughly three months.

The durable fix is not a bigger job timeout. It is ``pytest-timeout``: a hung
test then fails *by name*, with a stack trace, and the rest of the suite still
runs. ``--timeout-method=signal`` is mandatory — ``thread`` kills the whole
pytest process, which reproduces the exact "no results at all" outcome this is
meant to end.

Scope is the CLASS, not the instance: these tests walk *every* workflow file
under ``.github/workflows/``, *every* job, and *every* ``run:`` step, and
require each pytest invocation they find to be timeout-bounded. A seventh
invocation added next month is caught with no test edit. Nothing here is
hardcoded to a single file or job, and the live YAML is parsed (no snippet
copies), so the wiring cannot be silently removed. The #1580 guards further
down apply the same discipline to step ``if:`` conditions: which jobs count as
multi-suite, and which steps count as prerequisites, are both COMPUTED from the
parsed workflow, never listed — so a fourth suite or a second setup step added
next month is covered without anyone remembering this file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
REQUIREMENTS_DEV = REPO_ROOT / "plugins" / "autonomous-dev" / "requirements-dev.txt"

# A shell line that actually invokes pytest (vs. an echo describing it, a
# comment mentioning it, or a `pip install pytest ...` line).
PYTEST_INVOCATION = re.compile(r"^\s*(python3?\s+-m\s+)?pytest\s")

# Floors for the discovery walk itself (see the guard-the-guard test). These
# are minimums, never equalities — adding an invocation must not fail a test.
MIN_KNOWN_INVOCATIONS = 6
MIN_WORKFLOW_FILES_WITH_PYTEST = 2

# GitHub Actions' documented default when a job declares no `timeout-minutes`.
# Jobs without an explicit cap are NOT skipped by the ratio guard below: an
# unstated cap is still a cap, and skipping such jobs would open a blind spot
# of exactly the shape this guard exists to close.
# https://docs.github.com/actions/reference/workflow-syntax-for-github-actions
GITHUB_DEFAULT_JOB_TIMEOUT_MINUTES = 360

# --------------------------------------------------------------------------
# Ratio ceiling: per-test timeout as a fraction of its job's own cap.
#
# The defect this closes: ci.yml's smoke job carried `--timeout=300` under
# `timeout-minutes: 5` — exactly 300s. The per-test bound and the job-level
# cancellation raced at the same instant, so the bound could never fire and a
# hung smoke test still took the job down as "cancelled, no results" — the
# precise failure mode #1567 exists to eliminate. A bound that cannot fire is
# not a bound; it is decoration that reads as protection. Asserting merely
# that a `--timeout` is *present*, or merely that it is `<=` the job cap, would
# have passed on that config.
#
# Why 0.5, and not something looser: the per-test timeout exists so that ONE
# hung test fails by name AND THE REST OF THE SUITE STILL RUNS. That only
# holds if the job still has budget after the hang burns its full timeout. At
# ratio 1.0 the bound is inert. At 0.9 a single hang eats 90% of the budget
# and the job is cancelled anyway — nearly as useless as no bound at all. Half
# is the loosest ratio under which a job provably survives one full hang with
# a further full timeout's worth of budget left to run and report the
# remainder. It is a ceiling, so only ever lower it.
#
# The ceiling is EXCLUSIVE (`>=`, not `>`). A boundary-exact value has zero
# headroom: genai-validation sat at exactly 300/600 = 0.50, legal only because
# the comparison was strict. Any later tightening of that job's
# `timeout-minutes: 10` would have turned CI red with no warning margin, and a
# bound with no margin is the same decoration this guard exists to reject.
# Demanding a hair of real margin costs nothing and removes the cliff edge.
#
# Known limitation — the ratio is computed against the job's TOTAL
# `timeout-minutes`, not the budget still left once checkout, setup-python and
# pip install have run first. The real margin is therefore somewhat smaller
# than the number printed below. Netting out setup time is deliberately not
# attempted: it varies per run and per cache state, and modelling it would
# trade a simple, auditable ceiling for a fragile estimate. Read these ratios
# as an upper bound on the available margin, not a precise measurement.
#
# Where the current invocations stand against it:
#   ci.yml::smoke             30 / 300  = 0.10
#   ci.yml::test             300 / 3600 = 0.08  (x3 steps)
#   ci.yml::genai-validation 240 / 600  = 0.40
# --------------------------------------------------------------------------
MAX_TIMEOUT_TO_JOB_CAP_RATIO = 0.5

# Captures the per-test bound's value. `[=\s]` deliberately excludes
# `--timeout-method=signal`, whose next character is `-`.
TIMEOUT_VALUE = re.compile(r"--timeout[=\s]+(\d+(?:\.\d+)?)")

# --------------------------------------------------------------------------
# Exemptions — and the ceiling on the exemption mechanism.
#
# A ratchet needs a second ratchet on its own escape hatch, or the first is
# decorative. Every entry below is keyed "<workflow>::<job-id>::<step name>"
# and MUST cite the GitHub issue that tracks its removal. Three separate tests
# police this set: the ceiling (size pinned), the issue reference (format), and
# staleness (an exemption for an invocation that is now bounded must be
# deleted, not left lying around).
#
# This ONE set is also what the ratio guard below exempts. It deliberately
# does not get a parallel allowlist of its own: a second escape hatch with a
# second ceiling is how this ratchet goes slack. The two concerns nest anyway —
# an invocation with no per-test bound has no ratio to check — and
# `test_no_stale_exemptions` closes the loophole from the other side, firing
# the moment an exempted invocation gains a `--timeout` (at which point it must
# leave the allowlist and face the ratio guard like everything else).
#
# INTENDED END STATE: zero exemptions. When #1576 resolves, delete the entry
# below and set MAX_UNBOUNDED_EXEMPTIONS to 0.
# --------------------------------------------------------------------------
UNBOUNDED_INVOCATION_EXEMPTIONS: dict[str, str] = {
    "safety-net.yml::safety-validation::Run Tests with Coverage": (
        "Issue #1576 — safety-net.yml is independently and permanently broken: "
        "it runs `--cov=src --cov-fail-under=80` against a repo that has no "
        "src/ directory, and 40 of its last 40 weekly runs failed. Bounding the "
        "timeout here would be tuning a job that never reaches the tests. "
        "Delete this entry (and drop the ceiling to 0) when #1576 resolves."
    ),
}

# Pinned so a future author cannot quietly append a seventh unbounded
# invocation to the allowlist. Raising this number is the failure mode; the
# ceiling test exists to make raising it a deliberate, reviewed act.
MAX_UNBOUNDED_EXEMPTIONS = 1

ISSUE_REFERENCE = re.compile(r"#\d+")

# An install line that really provides the plugin. Matching the bare string
# "pytest-timeout" anywhere in the job would be satisfied by a comment
# mentioning it — the guard would then pass on a job that installs nothing.
# The `-r requirements-dev.txt` alternative is accepted because that file is
# separately asserted to pin pytest-timeout.
PYTEST_TIMEOUT_INSTALL = re.compile(
    r"pip\s+install\b[^\n]*(\bpytest-timeout\b|-r\s+\S*requirements-dev\.txt)"
)


@dataclass(frozen=True)
class RunStep:
    """One ``run:`` step of one job, with the attributes both guards need.

    Attributes:
        workflow: Workflow file name, e.g. ``ci.yml``.
        job: Job id as written under ``jobs:``.
        step: Step ``name:`` (or a positional placeholder if unnamed).
        body: Raw shell text of the step's ``run:`` block.
        cap_seconds: The wall-clock ceiling GitHub actually enforces on this
            step — ``min(step timeout-minutes, job timeout-minutes)``, with
            GitHub's 360-minute default standing in for an unstated job cap.
        if_condition: The step's raw ``if:`` expression, or None when absent.
        continue_on_error: The step's ``continue-on-error:`` value, or None.
    """

    workflow: str
    job: str
    step: str
    body: str
    cap_seconds: int
    if_condition: str | None
    continue_on_error: object | None


@dataclass(frozen=True)
class PytestInvocation:
    """One pytest command found in a workflow step.

    Attributes:
        workflow: Workflow file name, e.g. ``ci.yml``.
        job: Job id as written under ``jobs:``.
        step: Step ``name:`` (or a positional placeholder if unnamed).
        command: The full logical shell command, line continuations joined.
        cap_seconds: The wall-clock ceiling GitHub actually enforces on this
            step — ``min(step timeout-minutes, job timeout-minutes)``, with
            GitHub's 360-minute default standing in for an unstated job cap.
        if_condition: The step's raw ``if:`` expression, or None when absent.
        continue_on_error: The step's ``continue-on-error:`` value, or None.
    """

    workflow: str
    job: str
    step: str
    command: str
    cap_seconds: int
    if_condition: str | None = None
    continue_on_error: object | None = None

    @property
    def key(self) -> str:
        """Stable identity used for exemption lookup."""
        return f"{self.workflow}::{self.job}::{self.step}"

    @property
    def job_key(self) -> str:
        """Stable identity of the enclosing job."""
        return f"{self.workflow}::{self.job}"

    def describe(self) -> str:
        """Human-readable locator naming file, job, step and command."""
        return f"{self.workflow} → job '{self.job}' → step '{self.step}'\n      {self.command}"


def _logical_lines(body: str) -> list[str]:
    """Split a shell body into logical lines, joining ``\\`` continuations.

    ``safety-net.yml`` spreads one pytest call over six physical lines; without
    joining, the flags would live on lines the invocation regex never sees.

    Args:
        body: Raw shell text from a workflow step's ``run:`` block.

    Returns:
        Logical lines with backslash continuations collapsed into one entry.
    """
    lines: list[str] = []
    pending = ""
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            pending += line[:-1].rstrip() + " "
            continue
        lines.append(pending + line.strip() if pending else line)
        pending = ""
    if pending:
        lines.append(pending.rstrip())
    return lines


def _timeout_minutes(scope: dict, where: str) -> float | None:
    """Read a ``timeout-minutes:`` value off a job or step mapping.

    Args:
        scope: The parsed job or step mapping.
        where: Locator used in the failure message.

    Returns:
        The declared minutes, or None if the key is absent.

    Raises:
        AssertionError: If the value is present but not a number (e.g. a
            ``${{ }}`` expression). Silently treating that as "absent" would
            substitute the 360-minute default for what may be a 2-minute cap,
            turning the ratio guard permissive exactly where it matters.
    """
    if "timeout-minutes" not in scope:
        return None
    raw = scope["timeout-minutes"]
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise AssertionError(
            f"{where} declares a non-numeric timeout-minutes: {raw!r}\n"
            f"Expected: a number of minutes.\n"
            f"Resolve the expression here so the ratio guard can compare "
            f"against a real cap rather than assuming GitHub's "
            f"{GITHUB_DEFAULT_JOB_TIMEOUT_MINUTES}-minute default (Issue #1567)."
        ) from exc


def _iter_workflow_jobs() -> list[tuple[str, str, dict]]:
    """Parse every workflow file once and yield its jobs.

    Shared by the ``run:``-step walk (timeout guards) and the all-step walk
    (predecessor-gating guard) so there is one parse, one set of failure
    messages, and no chance of the two walks disagreeing about what exists.

    Returns:
        ``(workflow file name, job id, job mapping)`` for every job of every
        YAML file under the workflows dir, in file → declaration order.

    Raises:
        AssertionError: If the workflows directory is missing or a file does
            not parse — a silent parse failure would let every assertion below
            pass over an empty set.
    """
    assert WORKFLOWS_DIR.is_dir(), (
        f"Workflow directory not found: {WORKFLOWS_DIR}\n"
        f"Expected .github/workflows/ to exist. If workflows moved, update this "
        f"guard rather than deleting it (Issue #1567)."
    )
    jobs: list[tuple[str, str, dict]] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.y*ml")):
        try:
            workflow = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:  # pragma: no cover - only on broken YAML
            raise AssertionError(
                f"{path.name} does not parse as YAML: {exc}\n"
                f"Expected: a valid GitHub Actions workflow.\n"
                f"A broken workflow file otherwise fails only at push time."
            ) from exc
        for job_id, job in (workflow or {}).get("jobs", {}).items():
            if isinstance(job, dict):
                jobs.append((path.name, job_id, job))
    return jobs


def _iter_run_steps() -> list[RunStep]:
    """Yield one :class:`RunStep` per ``run:`` step of every job of every file.

    ``cap_seconds`` is the ceiling GitHub really enforces: the tighter of the
    step's own ``timeout-minutes`` (this repo uses one, in ``drain-watchdog``)
    and the job's, falling back to GitHub's documented 360-minute default when
    the job states none.

    Returns:
        One RunStep per ``run:`` step across every YAML file in the workflows
        dir, carrying the shell body, the enforced cap, and the two gating
        attributes (``if:`` and ``continue-on-error:``) the suppression guards
        need.
    """
    steps: list[RunStep] = []
    for workflow_name, job_id, job in _iter_workflow_jobs():
        job_minutes = _timeout_minutes(job, f"{workflow_name} → job '{job_id}'")
        if job_minutes is None:
            job_minutes = float(GITHUB_DEFAULT_JOB_TIMEOUT_MINUTES)
        for index, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            run_body = step.get("run")
            if not isinstance(run_body, str):
                continue
            step_name = step.get("name") or f"<step {index}>"
            step_minutes = _timeout_minutes(
                step, f"{workflow_name} → job '{job_id}' → step '{step_name}'"
            )
            effective = job_minutes if step_minutes is None else min(step_minutes, job_minutes)
            raw_if = step.get("if")
            steps.append(
                RunStep(
                    workflow=workflow_name,
                    job=job_id,
                    step=step_name,
                    body=run_body,
                    cap_seconds=int(effective * 60),
                    if_condition=None if raw_if is None else str(raw_if),
                    continue_on_error=step.get("continue-on-error"),
                )
            )
    return steps


def discover_pytest_invocations() -> list[PytestInvocation]:
    """Find every pytest invocation in every job of every workflow file.

    Returns:
        All pytest commands discovered, in workflow → job → step order.
    """
    found: list[PytestInvocation] = []
    for run_step in _iter_run_steps():
        for line in _logical_lines(run_step.body):
            if PYTEST_INVOCATION.search(line):
                found.append(
                    PytestInvocation(
                        workflow=run_step.workflow,
                        job=run_step.job,
                        step=run_step.step,
                        command=line.strip(),
                        cap_seconds=run_step.cap_seconds,
                        if_condition=run_step.if_condition,
                        continue_on_error=run_step.continue_on_error,
                    )
                )
    return found


def _enforced_invocations() -> list[PytestInvocation]:
    """Discovered invocations minus the (issue-linked, size-capped) exemptions."""
    return [
        i for i in discover_pytest_invocations() if i.key not in UNBOUNDED_INVOCATION_EXEMPTIONS
    ]


def _job_installs_pytest_timeout(workflow: str, job: str) -> bool:
    """Whether one job's own steps pip-install the pytest-timeout plugin.

    Comment lines are excluded: a job that only *mentions* pytest-timeout in a
    comment installs nothing, and pytest would hard-error on ``--timeout``.

    Args:
        workflow: Workflow file name.
        job: Job id under ``jobs:``.

    Returns:
        True if some non-comment line in that job installs the plugin.
    """
    for run_step in _iter_run_steps():
        if run_step.workflow != workflow or run_step.job != job:
            continue
        for line in _logical_lines(run_step.body):
            if line.lstrip().startswith("#"):
                continue
            if PYTEST_TIMEOUT_INSTALL.search(line):
                return True
    return False


# --------------------------------------------------------------------------
# Guard the guard: the discovery walk must not silently find nothing.
# --------------------------------------------------------------------------


def test_workflow_discovery_finds_known_invocations() -> None:
    """The walk must find the invocations that exist today, across >1 file.

    Without this, renaming the workflows directory, breaking a YAML parse, or
    restructuring jobs would make every assertion below vacuously pass over an
    empty list — a green test that checks nothing.
    """
    invocations = discover_pytest_invocations()
    assert len(invocations) >= MIN_KNOWN_INVOCATIONS, (
        f"Discovery found only {len(invocations)} pytest invocation(s) under "
        f"{WORKFLOWS_DIR}; expected at least {MIN_KNOWN_INVOCATIONS}.\n"
        f"Found:\n" + "\n".join(f"  - {i.describe()}" for i in invocations)
    )
    workflow_files = {i.workflow for i in invocations}
    assert len(workflow_files) >= MIN_WORKFLOW_FILES_WITH_PYTEST, (
        f"Discovery found pytest invocations in only {sorted(workflow_files)}; "
        f"expected at least {MIN_WORKFLOW_FILES_WITH_PYTEST} distinct workflow "
        f"files. A walk that reaches one file is instance-scoped again."
    )


def test_discovered_invocations_are_fully_attributed() -> None:
    """Every discovery must name its file, job, step and command.

    Failure messages are useless without this — "something is unbounded" does
    not tell the next reader where to look.
    """
    for invocation in discover_pytest_invocations():
        assert invocation.workflow.endswith((".yml", ".yaml")), invocation
        assert invocation.job, f"Missing job id for {invocation.command!r}"
        assert invocation.step, f"Missing step name for {invocation.command!r}"
        assert "pytest" in invocation.command, invocation


# --------------------------------------------------------------------------
# The actual class-wide requirement.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--timeout=", "--timeout-method=signal"])
def test_every_ci_pytest_invocation_is_timeout_bounded(flag: str) -> None:
    """Every pytest run in every workflow job must carry a per-test timeout.

    Issue #1567: an unbounded invocation is one that can silently cancel its
    job again, producing no results at all.
    """
    missing = [i for i in _enforced_invocations() if flag not in i.command]
    assert not missing, (
        f"{len(missing)} pytest invocation(s) missing {flag!r}:\n"
        + "\n".join(f"  - {i.describe()}" for i in missing)
        + f"\nEvery pytest invocation under {WORKFLOWS_DIR.name}/ must be "
        f"per-test timeout bounded so a hang names itself instead of "
        f"cancelling the job (Issue #1567)."
    )


def _parse_timeout_seconds(invocation: PytestInvocation) -> float | None:
    """Extract the per-test timeout value from a command, if it has one.

    Args:
        invocation: A discovered pytest command.

    Returns:
        The ``--timeout`` value in seconds, or None if absent/non-numeric.
    """
    match = TIMEOUT_VALUE.search(invocation.command)
    return float(match.group(1)) if match else None


def test_every_per_test_timeout_is_meaningfully_below_its_job_cap() -> None:
    """A per-test bound at or near its job's cap cannot fire — it is decoration.

    This is the class-level fix for the smoke job's ``--timeout=300`` under
    ``timeout-minutes: 5``: the bound and the job cancellation raced at the
    same instant, so a hung smoke test still took the job down as "cancelled,
    no results". Presence of a ``--timeout`` flag is necessary but not
    sufficient; the value has to be small enough relative to the job cap that
    the timeout fires first AND leaves budget to run and report the rest.

    The ceiling is exclusive: a value landing exactly on it has zero headroom,
    so it is rejected rather than tolerated. The guard therefore cannot be
    satisfied by a config that is one small edit away from failing.

    Applies to every discovered invocation, including jobs that declare no
    ``timeout-minutes`` (they inherit GitHub's 360-minute default). Skipping
    those would reintroduce a blind spot of the same shape.
    """
    unparseable: list[PytestInvocation] = []
    over_ratio: list[str] = []

    for invocation in _enforced_invocations():
        seconds = _parse_timeout_seconds(invocation)
        if seconds is None:
            unparseable.append(invocation)
            continue
        ceiling = MAX_TIMEOUT_TO_JOB_CAP_RATIO * invocation.cap_seconds
        # `>=`, not `>`: the ceiling is exclusive, so a boundary-exact value
        # (zero headroom) is rejected rather than tolerated.
        if seconds >= ceiling:
            over_ratio.append(
                f"  - {invocation.describe()}\n"
                f"      per-test --timeout={seconds:g}s vs job cap "
                f"{invocation.cap_seconds}s "
                f"(ratio {seconds / invocation.cap_seconds:.2f}, "
                f"ceiling {MAX_TIMEOUT_TO_JOB_CAP_RATIO:.2f} "
                f"= must be strictly under {ceiling:g}s)"
            )

    assert not unparseable, (
        f"{len(unparseable)} pytest invocation(s) carry no numeric "
        f"--timeout=<seconds> value:\n"
        + "\n".join(f"  - {i.describe()}" for i in unparseable)
        + "\nThe ratio guard cannot evaluate a bound it cannot read, and an "
        "unreadable bound is not a bound (Issue #1567)."
    )
    assert not over_ratio, (
        f"{len(over_ratio)} per-test timeout(s) too close to their job cap to "
        f"ever fire:\n" + "\n".join(over_ratio) + f"\n\nA per-test timeout at "
        f"{MAX_TIMEOUT_TO_JOB_CAP_RATIO:.0%}+ of the job cap races the job-level "
        f"cancellation instead of pre-empting it, so a hang still ends the job "
        f"as 'cancelled, no results' — the exact outcome #1567 exists to "
        f"eliminate. Lower the --timeout (preferred) or raise the job's "
        f"timeout-minutes, so one full hang leaves budget to run and report "
        f"the remainder of the suite."
    )


def test_no_workflow_uses_thread_timeout_method() -> None:
    """``--timeout-method=thread`` kills the whole pytest process.

    That produces no summary line and no per-test attribution — i.e. the same
    uninformative outcome as the original job cancellation. Negative control
    for the fix: it must not be "solved" with the wrong method.
    """
    offenders = [i for i in discover_pytest_invocations() if "--timeout-method=thread" in i.command]
    assert not offenders, (
        f"{len(offenders)} pytest invocation(s) use --timeout-method=thread:\n"
        + "\n".join(f"  - {i.describe()}" for i in offenders)
        + "\nthread kills the pytest process on timeout, losing all results. "
        "Use signal (Issue #1567)."
    )


def test_every_timeout_bounded_job_installs_pytest_timeout() -> None:
    """A ``--timeout`` flag without the plugin turns a green job hard-red.

    pytest exits with "unrecognized arguments" on an unknown flag, so the
    install must live in the SAME job as the invocation — each job in ci.yml
    has its own install step.
    """
    unbacked: list[PytestInvocation] = []
    for invocation in discover_pytest_invocations():
        if "--timeout" not in invocation.command:
            continue
        if not _job_installs_pytest_timeout(invocation.workflow, invocation.job):
            unbacked.append(invocation)
    assert not unbacked, (
        f"{len(unbacked)} job(s) pass --timeout without installing pytest-timeout:\n"
        + "\n".join(f"  - {i.describe()}" for i in unbacked)
        + "\nAdd pytest-timeout to that job's own pip install step — pytest "
        "hard-errors on an unrecognized argument (Issue #1567)."
    )


# --------------------------------------------------------------------------
# Sibling-step suppression (Issue #1580).
#
# #1567 stopped CI hanging. Run 32333848238 then completed for the first time
# in three months and exposed the NEXT layer of the same problem: unit failed
# (237 failures), and integration + regression were recorded "skipped". Two
# thirds of the surface stayed invisible — different mechanism, identical
# outcome: an absence where a signal should be.
#
# The mechanism is documented, not incidental. GitHub applies "a default status
# check of success()" to any `if:` containing no status-check function, so the
# bare `steps.route.outputs.skip_all != 'true'` on all three steps read as
# `success() && ...`. One red sibling suppressed every later suite. The suites
# are independent; there is no engineering reason for that coupling, and it
# means the true size of the problem stays unknown until the first suite is
# fully green.
#
# What "tolerates a prior failure" accepts, and why:
#   always()      — runs even after failure. Accepted: it satisfies the
#                   invariant. Not what ci.yml uses (see below), but a step
#                   using it is not suppressible, which is what is asserted.
#   !cancelled()  — runs after failure, NOT after a human cancels the run.
#                   GitHub's own docs name this "the recommended alternative"
#                   to always(). This is what ci.yml uses.
#   failure()     — REJECTED. Inverts the gate: the step then runs ONLY after
#                   something else failed, so it never runs on a green run.
#   success()     — REJECTED. That is the default being overridden.
#   cancelled()   — REJECTED. Runs only on cancellation.
#
# Scope is the CLASS: any job holding two or more pytest-running steps, in any
# workflow file, discovered from the parsed YAML. A fourth suite added next
# month is covered with no edit here, and so is a second suite appearing in a
# job that today has only one (which is why multi-suite-ness is computed, not
# listed).
# --------------------------------------------------------------------------

# Status-check operands that survive an earlier sibling step's failure. These
# match a WHOLE operand, not a substring: the expression is split on `&&`/`||`
# first and each term must match end-to-end. A substring match would classify
# `${{ always() == false }}` as failure-tolerant even though it means the
# literal opposite — the "looks compliant but isn't" shape this guard exists to
# catch, sitting inside the guard's own instrument. Anchoring is chosen over
# documenting the hole as a limitation because a textual heuristic at the core
# of a guard has to be able to refuse a legal expression that defeats it.
# Whitespace-tolerant: `! cancelled ( )` is legal in an Actions expression.
FAILURE_TOLERANT_OPERANDS: dict[str, re.Pattern[str]] = {
    "always()": re.compile(r"always\s*\(\s*\)"),
    "!cancelled()": re.compile(r"!\s*cancelled\s*\(\s*\)"),
}

# Actions' two boolean connectives. Splitting on them yields the operands that
# GitHub itself evaluates independently, which is the right granularity: a
# status-check function only overrides the implicit success() when it IS an
# operand, not when it is one side of a comparison.
EXPRESSION_OPERAND_SPLIT = re.compile(r"&&|\|\|")

# Floor for the guard-the-guard test below: ci.yml::test holds three suites.
# A minimum, never an equality — adding a suite must not fail a test.
MIN_MULTI_SUITE_JOBS = 1


def _operands(condition: str) -> list[str]:
    """Split an Actions ``if:`` expression into its top-level boolean operands.

    Strips the optional ``${{ }}`` wrapper, splits on ``&&``/``||``, and peels
    balanced outer parentheses off each term. Terms mangled by the split (a
    connective inside a string literal, say) simply fail to match any operand
    pattern, so the error direction is REJECT — the safe one for a guard.

    Args:
        condition: The step's raw ``if:`` expression.

    Returns:
        The trimmed operand terms, in source order.
    """
    expr = condition.strip()
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2]
    terms: list[str] = []
    for raw in EXPRESSION_OPERAND_SPLIT.split(expr):
        term = raw.strip()
        while term.startswith("(") and term.endswith(")"):
            term = term[1:-1].strip()
        terms.append(term)
    return terms


def _tolerates_prior_failure(condition: str | None) -> bool:
    """Whether an ``if:`` expression still runs after an earlier step failed.

    Args:
        condition: The step's raw ``if:`` expression, or None if it has none.

    Returns:
        True if some top-level operand of the expression IS a status-check
        function that both overrides GitHub's implicit ``success()`` and
        evaluates true after a prior failure. A step with no ``if:`` at all
        returns False — the implicit ``success()`` is precisely what
        suppresses it.
    """
    if condition is None:
        return False
    return any(
        pattern.fullmatch(term)
        for term in _operands(condition)
        for pattern in FAILURE_TOLERANT_OPERANDS.values()
    )


def _test_steps_by_job() -> dict[str, list[PytestInvocation]]:
    """Group discovered invocations into one entry per distinct STEP, by job.

    Two pytest calls inside a single ``run:`` block are one step, not two
    siblings, so they cannot suppress each other and must not make a job look
    multi-suite. Grouping is therefore by step key, not by invocation.

    Returns:
        Mapping of ``"<workflow>::<job>"`` to one PytestInvocation per distinct
        pytest-running step in that job, discovery order preserved.
    """
    by_job: dict[str, list[PytestInvocation]] = {}
    seen_steps: set[str] = set()
    for invocation in discover_pytest_invocations():
        if invocation.key in seen_steps:
            continue
        seen_steps.add(invocation.key)
        by_job.setdefault(invocation.job_key, []).append(invocation)
    return by_job


def multi_suite_test_steps() -> list[PytestInvocation]:
    """Every enforced pytest step living in a job that runs 2+ pytest steps.

    Multi-suite-ness is computed over ALL discovered steps including exempted
    ones — an exempt step is still a sibling whose failure would suppress the
    others, so it must not be able to hide a job from this guard. Only the
    returned (enforced) steps are asserted on, and the exempt set is the single
    allowlist shared with the timeout guards above; there is deliberately no
    second parallel allowlist with a second ceiling.

    Returns:
        The enforced pytest steps of every multi-suite job.
    """
    return [
        step
        for steps in _test_steps_by_job().values()
        if len(steps) >= 2
        for step in steps
        if step.key not in UNBOUNDED_INVOCATION_EXEMPTIONS
    ]


@pytest.mark.parametrize(
    ("condition", "tolerates"),
    [
        # Positive controls — these really do survive a sibling failure.
        ("${{ !cancelled() }}", True),
        ("${{ !cancelled() && steps.route.outputs.skip_all != 'true' }}", True),
        ("${{ ! cancelled ( ) }}", True),  # whitespace is legal in expressions
        ("${{ always() }}", True),
        # Negative controls — each must be REJECTED, and each fails differently.
        (None, False),  # no if: at all -> implicit success()
        ("steps.route.outputs.skip_all != 'true'", False),  # the #1580 bug itself
        ("${{ success() }}", False),  # the default, restated
        ("${{ failure() }}", False),  # inverted: never runs on a green run
        ("${{ cancelled() }}", False),  # runs only on cancellation
        ("${{ github.ref == 'refs/heads/master' }}", False),  # no status function
        # Token present but NOT as an operand — means the literal opposite.
        ("${{ always() == false }}", False),
        ("${{ !cancelled() == false }}", False),
        # Token present only inside a string literal.
        ("${{ contains(github.event.head_commit.message, 'always()') }}", False),
    ],
)
def test_failure_tolerance_classifier_distinguishes_conditions(
    condition: str | None, tolerates: bool
) -> None:
    """Verify the instrument before trusting one cell of its output.

    The suppression guard is only as good as this classifier. A version that
    matched any ``if:`` mentioning a status-check function would wave through
    ``failure()`` — which INVERTS the gate, running the suite only when
    something else already broke — and a version that matched nothing would
    report every workflow as compliant. Both failure modes are silent, so the
    classifier gets explicit positive and negative controls of several shapes.

    The last three negative controls are the ones a substring match fails:
    ``always() == false`` and ``!cancelled() == false`` contain the token but
    assert its negation, and a token inside a string literal is not an operand
    at all. A classifier that accepted these would report a suppressible step
    as compliant.
    """
    assert _tolerates_prior_failure(condition) is tolerates, (
        f"Classifier misread {condition!r}: expected tolerates={tolerates}.\n"
        f"Operands parsed: {_operands(condition) if condition else []}\n"
        f"Accepted operands: {sorted(FAILURE_TOLERANT_OPERANDS)}"
    )


def test_discovery_finds_a_multi_suite_job() -> None:
    """Guard the guard: the suppression test must not run over an empty set.

    ``ci.yml::test`` runs unit, integration and regression as three sibling
    steps. If a restructure, a rename or a YAML parse change made that job
    invisible, the assertion below would pass vacuously — a green test proving
    nothing, which is the same species of defect as the skipped suites it is
    written to prevent.
    """
    multi_suite = {key: steps for key, steps in _test_steps_by_job().items() if len(steps) >= 2}
    assert len(multi_suite) >= MIN_MULTI_SUITE_JOBS, (
        f"Discovery found {len(multi_suite)} job(s) running 2+ pytest steps; "
        f"expected at least {MIN_MULTI_SUITE_JOBS}.\n"
        f"Per-job step counts: "
        f"{ {k: len(v) for k, v in sorted(_test_steps_by_job().items())} }\n"
        f"The sibling-suppression guard has nothing to check without one "
        f"(Issue #1580)."
    )
    assert multi_suite_test_steps(), (
        f"Every step of every multi-suite job is exempted, so the suppression "
        f"guard asserts on nothing.\nMulti-suite jobs: {sorted(multi_suite)}\n"
        f"Exemptions: {sorted(UNBOUNDED_INVOCATION_EXEMPTIONS)}"
    )


def test_multi_suite_steps_survive_a_sibling_failure() -> None:
    """A red suite must not skip the suites after it.

    Issue #1580: in run 32333848238 the unit step failed and integration and
    regression were both recorded ``skipped``, because their ``if:`` carried no
    status-check function and so inherited GitHub's implicit ``success()``.
    The suites are independent; a failure in one may not delete the evidence
    from the others.

    Asserts the ``if:`` of every pytest-running step in every multi-suite job
    contains a status-check function that survives a prior failure. Derived
    from the parsed workflow, so a fourth suite is covered automatically.
    """
    suppressible = [
        step for step in multi_suite_test_steps() if not _tolerates_prior_failure(step.if_condition)
    ]
    accepted = " or ".join(sorted(FAILURE_TOLERANT_OPERANDS))
    assert not suppressible, (
        f"{len(suppressible)} test step(s) can be silently skipped by an "
        f"earlier sibling step's failure:\n"
        + "\n".join(
            f"  - {step.describe()}\n      if: {step.if_condition!r}" for step in suppressible
        )
        + f"\n\nGitHub applies a default status check of success() to any if: "
        f"that contains no status-check function, so a red sibling skips this "
        f"step entirely and its results are never seen. Add {accepted} to the "
        f"condition — e.g.\n"
        f"    if: ${{{{ !cancelled() && <existing condition> }}}}\n"
        f"!cancelled() is preferred over always(): GitHub's docs name it the "
        f"recommended alternative because always() also runs after a human "
        f"cancels the run. The ${{{{ }}}} wrapper is required — a bare leading "
        f"'!' is a YAML tag indicator and will not parse (Issue #1580)."
    )


def test_no_test_step_masks_failure_with_continue_on_error() -> None:
    """Refusing the wrong fix: ``continue-on-error`` on a test step.

    Negative control of a DIFFERENT shape to the bug being fixed. The obvious
    way to make later suites run is ``continue-on-error: true`` — and it is
    strictly worse than the skipping it cures, because the job then reports
    SUCCESS with a red suite underneath. A green check sitting on a failing
    test suite trains everyone to ignore CI permanently; no signal may cry
    wolf, and a signal that can never go red is the loudest false reassurance
    of all.

    The correct fix removes only the SUPPRESSION OF LATER STEPS. The failing
    step must still fail, and must still fail its job. Scope is every pytest
    step in every job, not just multi-suite ones: a lone test step masked this
    way turns the whole workflow into a rubber stamp.
    """
    masked = [
        invocation
        for invocation in _enforced_invocations()
        if invocation.continue_on_error not in (None, False, "false")
    ]
    assert not masked, (
        f"{len(masked)} pytest step(s) carry continue-on-error:\n"
        + "\n".join(
            f"  - {i.describe()}\n      continue-on-error: {i.continue_on_error!r}" for i in masked
        )
        + "\n\ncontinue-on-error lets the job report success while tests fail — "
        "a green check on a red suite, which is worse than no check at all. To "
        "stop a failure suppressing LATER steps, put !cancelled() in those "
        "steps' if: conditions instead; that keeps this step's failure real "
        "and still fails the job (Issue #1580)."
    )


# --------------------------------------------------------------------------
# Prerequisite gating (Issue #1580, second layer).
#
# `!cancelled()` fixes the sibling suppression above, but it does so by
# REMOVING GitHub's implicit `success()` — and that implicit gate was load
# bearing. A bare `if: steps.route.outputs.skip_all != 'true'` silently read as
# `success() && skip_all != 'true'`, which is what made a failed
# `Install dependencies` skip all three suites. Adding `!cancelled()` deletes
# that, so the suites would run on top of a broken install and emit
# ModuleNotFoundError for every test — output indistinguishable in the log from
# genuine test failures, and #1579 records that 77 of the 237 current unit
# failures ALREADY are missing-dependency import errors. The same disease,
# re-entering through a different door.
#
# So each prerequisite must be named back explicitly. Which ones, is COMPUTED
# from the parsed job, never listed: every step declared before the suite that
# is not itself a suite and is not `continue-on-error: true`. A setup step
# added next month is covered with no edit here — the whole reason the name
# `Install dependencies` appears nowhere in the derivation.
#
# The two structural exclusions, and why each is right:
#   sibling suite steps   — gating a suite on another suite IS the #1580 bug.
#   continue-on-error     — an explicit, reviewed declaration that this step's
#                           failure must not stop the job. `route` is exactly
#                           that: it is engineered to fail OPEN (a crash writes
#                           nothing to $GITHUB_OUTPUT, `skip_all` is unset, and
#                           every suite runs), because a broken router must not
#                           silence the suites. Demanding a gate on it would be
#                           wrong. `Install dependencies` is the opposite case.
#                           One predecessor must not gate; the other must.
#
# Accepted gate form, and the two rejected ones:
#   steps.<id>.outcome != 'failure'   — ACCEPTED.
#   steps.<id>.outcome == 'success'   — REJECTED. A step's outcome is `skipped`
#     when its own `if:` is false, which is what happens to
#     `Install dependencies` whenever the router sets skip_all. `== 'success'`
#     treats that skip as grounds to suppress the suites: silent suppression on
#     a non-failure, i.e. #1580 again.
#   steps.<id>.conclusion ...         — REJECTED. `conclusion` is the value
#     AFTER `continue-on-error` is applied, so a prerequisite that later gains
#     `continue-on-error: true` reads `success` while broken. `outcome` reports
#     what happened either way, so the gate cannot be disarmed from elsewhere.
#
# Scope boundary, stated rather than hidden: this walks steps, both `run:` and
# `uses:`. It does NOT model `needs:` between jobs — a failed upstream JOB is
# already handled by GitHub's job-level dependency semantics and by the
# `summary` job's positive assertions.
# --------------------------------------------------------------------------

# The one gate form that is both necessary and sufficient (see above).
GATE_CLAUSE_TEMPLATE = r"steps\s*\.\s*{step_id}\s*\.\s*outcome\s*!=\s*'failure'"

# Any reference to a prerequisite's status, in any form — used only to tell
# "you gated wrongly" apart from "you did not gate at all" in the message.
GATE_REFERENCE_TEMPLATE = r"steps\s*\.\s*{step_id}\s*\.\s*(?:outcome|conclusion)\b.*"

# Floor for the guard-the-guard assertion: ci.yml::test has 3 suite steps, each
# with at least one prerequisite to gate on. A minimum, never an equality.
MIN_CHECKED_PREDECESSOR_PAIRS = 3


@dataclass(frozen=True)
class JobStep:
    """One step of one job — ``run:`` or ``uses:`` alike.

    :class:`RunStep` deliberately sees only ``run:`` steps, because a pytest
    invocation can only live in one. Prerequisite gating has to see every step:
    ``actions/checkout`` and ``actions/setup-python`` are prerequisites whose
    failure makes the suites emit noise just as surely as a broken pip install.

    Attributes:
        workflow: Workflow file name, e.g. ``ci.yml``.
        job: Job id as written under ``jobs:``.
        index: Position within the job's ``steps:`` list, used for ordering.
        name: Step ``name:`` (or a positional placeholder if unnamed).
        step_id: The step's ``id:``, or None — a step with no id cannot be
            referenced from a later ``if:`` at all.
        if_condition: The step's raw ``if:`` expression, or None when absent.
        continue_on_error: The step's ``continue-on-error:`` value, or None.
    """

    workflow: str
    job: str
    index: int
    name: str
    step_id: str | None
    if_condition: str | None
    continue_on_error: object | None

    def describe(self) -> str:
        """Human-readable locator naming file, job and step."""
        return f"{self.workflow} → job '{self.job}' → step '{self.name}'"


def _all_job_steps() -> dict[str, list[JobStep]]:
    """Every step of every job, keyed ``"<workflow>::<job>"``, in source order.

    Returns:
        Mapping of job key to its steps, ``run:`` and ``uses:`` alike.
    """
    by_job: dict[str, list[JobStep]] = {}
    for workflow_name, job_id, job in _iter_workflow_jobs():
        steps: list[JobStep] = []
        for index, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            raw_if = step.get("if")
            raw_id = step.get("id")
            steps.append(
                JobStep(
                    workflow=workflow_name,
                    job=job_id,
                    index=index,
                    name=step.get("name") or f"<step {index}>",
                    step_id=None if raw_id is None else str(raw_id),
                    if_condition=None if raw_if is None else str(raw_if),
                    continue_on_error=step.get("continue-on-error"),
                )
            )
        by_job[f"{workflow_name}::{job_id}"] = steps
    return by_job


def _is_fail_open(step: JobStep) -> bool:
    """Whether a step declares ``continue-on-error: true``.

    Args:
        step: The step to classify.

    Returns:
        True if the step's failure is declared not to stop the job.
    """
    return step.continue_on_error not in (None, False, "false")


def _required_predecessors(
    steps: list[JobStep], suite: JobStep, suite_names: set[str]
) -> list[JobStep]:
    """Prerequisites a suite step must gate on, derived from job structure.

    Args:
        steps: Every step of the enclosing job, in source order.
        suite: The pytest-running step whose ``if:`` is being checked.
        suite_names: Names of every pytest-running step in that job.

    Returns:
        The steps declared before ``suite`` that are neither sibling suites nor
        declared ``continue-on-error: true``.
    """
    return [
        step
        for step in steps
        if step.index < suite.index and step.name not in suite_names and not _is_fail_open(step)
    ]


def _gates_on_failure(condition: str | None, step_id: str) -> bool:
    """Whether an ``if:`` has an operand excluding one step's failure.

    Args:
        condition: The gating step's raw ``if:`` expression, or None.
        step_id: The prerequisite's ``id:``.

    Returns:
        True if some top-level operand is exactly
        ``steps.<step_id>.outcome != 'failure'``.
    """
    if condition is None:
        return False
    pattern = re.compile(GATE_CLAUSE_TEMPLATE.format(step_id=re.escape(step_id)))
    return any(pattern.fullmatch(term) for term in _operands(condition))


def _wrong_gate_form(condition: str | None, step_id: str) -> str | None:
    """The offending operand when a prerequisite is referenced the wrong way.

    Distinguishes "gated with ``== 'success'`` / ``conclusion``" from "not
    gated at all", so the failure message can name the specific mistake instead
    of repeating the whole rule.

    Args:
        condition: The gating step's raw ``if:`` expression, or None.
        step_id: The prerequisite's ``id:``.

    Returns:
        The rejected operand text, or None if there is no such reference.
    """
    if condition is None:
        return None
    reference = re.compile(GATE_REFERENCE_TEMPLATE.format(step_id=re.escape(step_id)))
    accepted = re.compile(GATE_CLAUSE_TEMPLATE.format(step_id=re.escape(step_id)))
    for term in _operands(condition):
        if reference.fullmatch(term) and not accepted.fullmatch(term):
            return term
    return None


def _synthetic_step(index: int, name: str, *, continue_on_error: object | None = None) -> JobStep:
    """Build a JobStep for the classifier controls below.

    Args:
        index: Position within the synthetic job.
        name: Step name.
        continue_on_error: Value for the step's ``continue-on-error:``.

    Returns:
        A JobStep carrying only the attributes the derivation reads.
    """
    return JobStep(
        workflow="synthetic.yml",
        job="synthetic",
        index=index,
        name=name,
        step_id=name,
        if_condition=None,
        continue_on_error=continue_on_error,
    )


@pytest.mark.parametrize(
    ("candidate", "required"),
    [
        ("setup", True),  # a plain earlier step -> must be gated on
        ("router", False),  # continue-on-error: true -> fail-open by design
        ("unit", False),  # a sibling suite -> gating on it IS the #1580 bug
        ("later_setup", False),  # declared after the suite -> cannot gate it
    ],
)
def test_required_predecessor_derivation_excludes_the_right_steps(
    candidate: str, required: bool
) -> None:
    """Verify the instrument: which predecessors the guard demands a gate on.

    Runs on fabricated steps, not the live workflow, so it states a property
    rather than pinning today's ``ci.yml``. A derivation that included
    ``continue-on-error`` steps would demand a gate on ``route`` — which is
    engineered to fail OPEN precisely so a broken router cannot silence the
    suites — and one that included sibling suites would re-create the coupling
    Issue #1580 exists to remove. Both mistakes are silent, so each gets an
    explicit control.
    """
    steps = [
        _synthetic_step(0, "setup"),
        _synthetic_step(1, "router", continue_on_error=True),
        _synthetic_step(2, "unit"),
        _synthetic_step(3, "integration"),
        _synthetic_step(4, "later_setup"),
    ]
    suite = steps[3]
    derived = {step.name for step in _required_predecessors(steps, suite, {"unit", "integration"})}
    assert (candidate in derived) is required, (
        f"Derivation misread {candidate!r}: expected required={required}, "
        f"got required={candidate in derived}.\nDerived set: {sorted(derived)}"
    )


def test_multi_suite_steps_gate_on_their_prerequisites() -> None:
    """A failure-tolerant suite step must still refuse to run on broken setup.

    Issue #1580, second layer. ``!cancelled()`` overrides GitHub's implicit
    ``success()``, which is exactly the gate that used to stop the suites
    running after ``Install dependencies`` failed. Losing it means a failed
    ``pip install`` produces three suites' worth of ModuleNotFoundError — noise
    that reads in the log exactly like real test failures, and #1579 shows real
    import errors are already present to be confused with.

    Every prerequisite is derived from the parsed job, so the step NAME appears
    nowhere here: a second setup step added later is covered without a test
    edit. Steps declared ``continue-on-error: true`` are excluded, which is why
    this does not fire on ``route``.
    """
    suites_by_job = {key: steps for key, steps in _test_steps_by_job().items() if len(steps) >= 2}
    all_steps = _all_job_steps()

    ungated: list[str] = []
    unaddressable: list[str] = []
    misgated: list[str] = []
    checked_pairs = 0

    for job_key, suite_invocations in suites_by_job.items():
        suite_names = {invocation.step for invocation in suite_invocations}
        job_steps = all_steps.get(job_key, [])
        for suite in job_steps:
            if suite.name not in suite_names:
                continue
            # A suite still carrying the implicit success() is already gated by
            # GitHub; test_multi_suite_steps_survive_a_sibling_failure is what
            # refuses that shape. Between the two there is no way out.
            if not _tolerates_prior_failure(suite.if_condition):
                continue
            for predecessor in _required_predecessors(job_steps, suite, suite_names):
                checked_pairs += 1
                if predecessor.step_id is None:
                    unaddressable.append(
                        f"  - {suite.describe()}\n"
                        f"      prerequisite '{predecessor.name}' has no id:, so no "
                        f"later if: can reference it"
                    )
                    continue
                if _gates_on_failure(suite.if_condition, predecessor.step_id):
                    continue
                wrong_form = _wrong_gate_form(suite.if_condition, predecessor.step_id)
                target = misgated if wrong_form else ungated
                target.append(
                    f"  - {suite.describe()}\n"
                    f"      prerequisite '{predecessor.name}' (id: {predecessor.step_id})\n"
                    f"      if: {suite.if_condition!r}"
                    + (f"\n      rejected operand: {wrong_form!r}" if wrong_form else "")
                )

    assert checked_pairs >= MIN_CHECKED_PREDECESSOR_PAIRS, (
        f"Only {checked_pairs} (suite step, prerequisite) pair(s) were checked; "
        f"expected at least {MIN_CHECKED_PREDECESSOR_PAIRS}.\n"
        f"Multi-suite jobs: {sorted(suites_by_job)}\n"
        f"A guard that walks an empty set is a green test proving nothing — the "
        f"same species of defect as the skipped suites it exists to prevent "
        f"(Issue #1580)."
    )
    assert not unaddressable, (
        f"{len(unaddressable)} prerequisite(s) of a failure-tolerant test step "
        f"cannot be gated on because they carry no id::\n"
        + "\n".join(unaddressable)
        + "\n\nAdd an `id:` to the prerequisite, then add "
        "`steps.<id>.outcome != 'failure'` to the suite step's if: (Issue #1580)."
    )
    assert not misgated, (
        f"{len(misgated)} prerequisite gate(s) use a rejected form:\n"
        + "\n".join(misgated)
        + "\n\nUse `steps.<id>.outcome != 'failure'`.\n"
        "NOT `== 'success'`: a prerequisite's outcome is 'skipped' when its own "
        "if: is false, and treating a skip as grounds to suppress the suites is "
        "silent suppression on a non-failure — Issue #1580 again.\n"
        "NOT `conclusion`: that is the value AFTER continue-on-error is applied, "
        "so it reads 'success' for a broken step the moment anyone adds "
        "continue-on-error to it, disarming this gate from another file's diff."
    )
    assert not ungated, (
        f"{len(ungated)} failure-tolerant test step(s) do not gate on a "
        f"prerequisite that can break them:\n"
        + "\n".join(ungated)
        + "\n\n`!cancelled()` REPLACES GitHub's implicit success() check, and "
        "that implicit check is what stopped these suites running after setup "
        "failed. Every prerequisite must therefore be named back explicitly:\n"
        "    if: ${{ !cancelled() && steps.<id>.outcome != 'failure' && ... }}\n"
        "Without it a broken install makes every test raise ModuleNotFoundError, "
        "which is indistinguishable in the log from real failures. Steps marked "
        "`continue-on-error: true` are excluded — they are declared fail-open on "
        "purpose, as `route` is (Issue #1580)."
    )


def test_requirements_dev_pins_pytest_timeout() -> None:
    """Local dev must match CI, so the hang reproduces the same way locally."""
    assert "pytest-timeout" in REQUIREMENTS_DEV.read_text(), (
        f"{REQUIREMENTS_DEV} must list pytest-timeout so local runs behave "
        f"like CI (Issue #1567)."
    )


# --------------------------------------------------------------------------
# The second ratchet: constraints on the exemption mechanism itself.
# --------------------------------------------------------------------------


def test_exemption_ceiling_is_not_raised() -> None:
    """Pin the exemption set's size so the allowlist cannot grow quietly.

    Without this, "just add it to the exemptions" makes the class-wide guard
    decorative one entry at a time. The intended end state is 0 exemptions
    (once #1576 resolves).
    """
    assert len(UNBOUNDED_INVOCATION_EXEMPTIONS) == MAX_UNBOUNDED_EXEMPTIONS, (
        f"Exemption count is {len(UNBOUNDED_INVOCATION_EXEMPTIONS)}, ceiling is "
        f"{MAX_UNBOUNDED_EXEMPTIONS}.\n"
        f"Current entries: {sorted(UNBOUNDED_INVOCATION_EXEMPTIONS)}\n"
        f"Adding an unbounded pytest invocation is not a paperwork problem — "
        f"bound the invocation instead. Only lower this ceiling (Issue #1567)."
    )


def test_every_exemption_cites_a_tracking_issue() -> None:
    """An exemption without a linked issue is permanent by accident."""
    for key, reason in UNBOUNDED_INVOCATION_EXEMPTIONS.items():
        assert ISSUE_REFERENCE.search(reason), (
            f"Exemption {key!r} has no '#<issue>' reference in its reason.\n"
            f"Expected: a GitHub issue tracking removal of the exemption.\n"
            f"Got: {reason!r}"
        )


def test_no_stale_exemptions() -> None:
    """Every exemption must point at a real, still-unbounded invocation.

    Two failure modes are caught here. If the exempted step disappears or is
    renamed, the key is dead weight that would silently cover nothing. If the
    step becomes timeout-bounded, the exemption MUST be deleted and the ceiling
    dropped — that is the intended end state, not a lingering allowlist entry.
    """
    discovered = {i.key: i for i in discover_pytest_invocations()}
    for key in UNBOUNDED_INVOCATION_EXEMPTIONS:
        invocation = discovered.get(key)
        assert invocation is not None, (
            f"Exemption {key!r} matches no pytest invocation in "
            f"{WORKFLOWS_DIR}.\nDiscovered keys: {sorted(discovered)}\n"
            f"Delete the stale exemption and lower MAX_UNBOUNDED_EXEMPTIONS."
        )
        assert "--timeout" not in invocation.command, (
            f"Exemption {key!r} is no longer needed — that invocation is now "
            f"timeout-bounded:\n  {invocation.describe()}\n"
            f"Delete the exemption and lower MAX_UNBOUNDED_EXEMPTIONS by one."
        )
