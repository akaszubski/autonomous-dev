"""Regression tests for per-test timeouts across ``.github/workflows/``.

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
copies), so the wiring cannot be silently removed.
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
    """

    workflow: str
    job: str
    step: str
    command: str
    cap_seconds: int

    @property
    def key(self) -> str:
        """Stable identity used for exemption lookup."""
        return f"{self.workflow}::{self.job}::{self.step}"

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


def _iter_run_steps() -> list[tuple[str, str, str, str, int]]:
    """Yield ``(workflow, job_id, step_name, run_body, cap_seconds)`` per step.

    ``cap_seconds`` is the ceiling GitHub really enforces: the tighter of the
    step's own ``timeout-minutes`` (this repo uses one, in ``drain-watchdog``)
    and the job's, falling back to GitHub's documented 360-minute default when
    the job states none.

    Returns:
        One tuple per ``run:`` step across every YAML file in the workflows dir.

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
    steps: list[tuple[str, str, str, str, int]] = []
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
            if not isinstance(job, dict):
                continue
            job_minutes = _timeout_minutes(job, f"{path.name} → job '{job_id}'")
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
                    step, f"{path.name} → job '{job_id}' → step '{step_name}'"
                )
                effective = job_minutes if step_minutes is None else min(step_minutes, job_minutes)
                steps.append((path.name, job_id, step_name, run_body, int(effective * 60)))
    return steps


def discover_pytest_invocations() -> list[PytestInvocation]:
    """Find every pytest invocation in every job of every workflow file.

    Returns:
        All pytest commands discovered, in workflow → job → step order.
    """
    found: list[PytestInvocation] = []
    for workflow_name, job_id, step_name, run_body, cap_seconds in _iter_run_steps():
        for line in _logical_lines(run_body):
            if PYTEST_INVOCATION.search(line):
                found.append(
                    PytestInvocation(
                        workflow=workflow_name,
                        job=job_id,
                        step=step_name,
                        command=line.strip(),
                        cap_seconds=cap_seconds,
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
    for wf, job_id, _, body, _cap in _iter_run_steps():
        if wf != workflow or job_id != job:
            continue
        for line in _logical_lines(body):
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
