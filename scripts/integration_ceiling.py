#!/usr/bin/env python3
"""Failure ceiling for the ``tests/integration/`` tier (Issue #1582).

WHY THIS EXISTS
---------------
Until Issue #1582 the integration tier had never executed. A module-scope
rebind of ``pytest.mark.integration`` in
``tests/integration/test_documentation_references.py`` assigned a ``skipif``
onto pytest's GLOBAL marker namespace, and ``tests/conftest.py`` resolves
auto-markers by name (``getattr(pytest.mark, marker_name)``). Collecting that
one module therefore turned every test under ``tests/integration/`` into a
skip. CI's own ``pytest tests/integration/`` step ran 0 of 1,834 tests and
reported success.

Removing the rebind turns the tier on and reveals a large pre-existing debt.
Shipping that as a raw red check would be a downgrade, not an improvement: a
permanently-red check trains everyone to ignore the whole class, which is the
same dynamic that let this tier stay dark for months. So the tier is turned on
behind a RATCHET instead — a pinned ceiling that failures may sit at or below,
and which may only ever be lowered.

This converts "512 tests are silently failing" into "512 known failures,
tracked, and the number can only go down".

HOW THE BASELINE WAS MEASURED
-----------------------------
The original 512/1844 pin (Issue #1582) was measured on a developer laptop
that carries ``plugins/autonomous_dev``, a symlink listed in ``.gitignore:31``
that has NEVER been committed (``git ls-files plugins/autonomous_dev`` returns
empty). That symlink lets the laptop collect tests no CI checkout can collect,
so the pin was calibrated against an environment the gate never actually runs
in — the same species of error this file exists to catch: trusting a reading
taken from the wrong copy.

Re-measured in the environment where the gate actually executes, GitHub
Actions CI, across two runs bracketing the #1579 alias fix::

    run 32639109196 (BEFORE #1579) -> 1792 collected, 525 failed, 11 errors
    run 32650827370 (AFTER  #1579) -> 1874 collected, 521 failed, 11 errors

The route that changed the collected count is commit ``6657846b``, which
registered the bare ``autonomous_dev`` import spelling in ``tests/conftest.py``.
82 modules that previously died at collection (148 prior collection errors)
now collect and run; their failures are pre-existing, merely uncovered — the
one case this module's own high-water-mark rule treats as an honest raise.

Direction matters: against the first honest CI reading (525 failed) this pin
is a DECREASE, to 521. It reads as a raise only against the invalid laptop
number (512), which was never a CI-valid baseline to begin with.

Caveat, stated rather than hidden: unlike the original pin — which was
verified across two runs with a symmetric-difference check on failing node
IDs — 521/1874 is a SINGLE post-fix CI reading. There is no second CI run yet
confirming the failing-node-ID set is stable. Do not describe this number as
"set-stable across two runs" anywhere in this module; that claim is not true
of it.

WHY THE GATE RUNS SERIALLY, NOT UNDER ``-n auto``
-------------------------------------------------
CI previously ran this tier with ``-n auto``. Measured on the same tree, same
command, two consecutive runs::

    -n auto run 1 -> 498 failed, 11 errors   (509 non-passing node IDs)
    -n auto run 2 -> 503 failed, 11 errors   (514 non-passing node IDs)
    symmetric difference between the two parallel sets: 7 node IDs

``-n auto`` is NONDETERMINISTIC here — its reading moved with nothing changed.
A ratchet cannot be built on an instrument that does that: the gate would flake,
and a flaky gate is the "cries wolf" failure this whole design exists to avoid.

Two further facts make parallel unfit as the pinned instrument:

* Parallel is not a strict SUBSET of serial. Two tests fail ONLY under xdist
  (``test_agent_feedback_integration.py::test_high_volume_feedback_processing``
  and ``test_session_id_fallback_chain.py::TestFallbackChain::
  test_coordinator_subshell_reads_sentinel_when_env_unset``), so a
  serial-derived pin cannot bound the parallel set from above.
* Parallel reports FEWER failures because xdist scatters mutually-polluting
  tests across worker processes. That makes it the optimistic reading; serial
  is the honest upper bound.

Cost of running serially: ~56s versus ~29s. Twenty-seven seconds buys a
deterministic gate.

THE CONSTANT/MEASUREMENT SPLIT
------------------------------
This module deliberately treats two kinds of number differently:

* ``FAILURE_CEILING`` vs ``FAILURE_HIGH_WATER_MARK`` are BOTH in-repo constants
  under the author's control, so their relationship is enforced by STRICT
  EQUALITY in the test suite. Slack between them would be a pre-authorised
  exemption for the next regression.
* ``observed`` versus ``FAILURE_CEILING`` compares a MEASUREMENT against a
  constant. The two pins are unverified along different axes: the original
  512 pin was measured on the developer laptop, not CI, but across two
  serial runs whose failing node-ID sets were diffed and found identical
  (symmetric difference 0) — repeated, but in the wrong environment. 521 is
  measured in the right environment, CI, but as a SINGLE post-fix reading
  with no second CI run yet confirming the failing-node-ID set is stable —
  right environment, but unrepeated. A slack reading could be a genuine fix,
  or it could be ordinary run-to-run variance that one reading cannot
  distinguish from a fix. So growth HARD-FAILS (the direction that hides
  regressions must never be waved through on an unproven measurement), while
  slack is reported as a loud, machine-readable advisory naming the exact
  edit to make rather than auto-applied — pressure toward the correct action
  without asserting a stability this single reading hasn't earned.

See ``tests/unit/scripts/test_integration_ceiling.py`` for the guard that
proves this ceiling can actually refuse, including a subprocess mutation
harness (``TestCeilingIsNotATautology``).
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# THE PIN
# =============================================================================
#
# LOWER THESE FREELY — that is the ratchet advancing, and it needs no
# justification beyond a green run. RAISING either one is a regression being
# waved through; see the high-water marks below.

#: Maximum tolerated ``failed`` count from ``pytest tests/integration``.
#: Measured on CI run 32650827370 — a single post-fix reading, not set-stable
#: across two runs. See module docstring.
FAILURE_CEILING = 521

#: Maximum tolerated ``errors`` count (collection/fixture errors) from the same
#: run. Errors are pinned separately from failures because they have a
#: different root-cause class — an error is usually a broken fixture or import,
#: not a wrong assertion — and collapsing them into one number would let a new
#: import break hide behind a fixed assertion.
ERROR_CEILING = 11

# -----------------------------------------------------------------------------
# HIGH-WATER MARKS — the ceiling on the ceiling.
# -----------------------------------------------------------------------------
#
# A ceiling that the next author can simply raise is decoration. These record
# the highest values ever REVIEWED. The test suite asserts equality with the
# ceilings above, so the residual headroom is held at exactly zero: lowering a
# ceiling without lowering its mark in the SAME diff is itself a failure.
#
# Raising a mark is honest in exactly one case: a NEW ROUTE or INSTRUMENT made
# PRE-EXISTING failures visible (for example, another dark tier being switched
# on and merged into this one). To take that case, in ONE diff, name the route
# in a comment here and raise both constants together.
#
# That case applies here: commit 6657846b (the #1579 alias fix) registered the
# bare ``autonomous_dev`` import spelling in tests/conftest.py, letting 82
# previously-uncollectable modules collect and run. Their failures were
# pre-existing and merely became visible; see the module docstring.

#: Highest reviewed value of ``FAILURE_CEILING``.
FAILURE_HIGH_WATER_MARK = 521

#: Highest reviewed value of ``ERROR_CEILING``.
ERROR_HIGH_WATER_MARK = 11

# -----------------------------------------------------------------------------
# TRUNCATION FLOOR
# -----------------------------------------------------------------------------
#
# A DIFFERENT mechanism with a DIFFERENT purpose from the ceilings above, and
# deliberately not a ratchet. The ceilings ask "did failures grow?"; this asks
# "did the run actually happen?".
#
# Without it, the gate inherits Issue #1582's own bug shape. If pytest dies
# part-way — an OOM, a timeout, a worker crash — it can still leave behind a
# JUnit report containing a handful of tests and a handful of failures. That
# report sails under a 521 ceiling and the step reports success, which is
# exactly "green over nothing" wearing a different hat.
#
# Measured on CI run 32650827370, the same run that produced the pin:
#     <testsuite tests="1874" failures="521" errors="11" ...>
#
# The floor's job is to separate a TRUNCATED run — an OOM, a timeout, or a
# worker crash, any of which loses HUNDREDS of tests — from ordinary PR
# churn, where a change adds or removes a handful of tests. It only needs to
# sit somewhere in the gap between those two regimes: a floor set at exactly
# 1874 would breach on any single legitimate test deletion, which is the
# cry-wolf failure this design exists to avoid. 50 is a round threshold an
# order of magnitude below "hundreds" while still absorbing normal churn — a
# buffer sized for that gap, not a ratio or offset preserved from any prior
# floor value.
MINIMUM_COLLECTED_TESTS = 1824


def verify_pin_invariants() -> None:
    """Assert the ceiling has not been raised and carries no residual slack.

    This lives in the module rather than in the test file on purpose. The
    relationships it checks are constant-versus-constant, which is
    unfalsifiable from inside a normal test: an edit that raises a ceiling AND
    its high-water mark together moves both operands and nothing fires. Keeping
    the assertions HERE gives ``TestCeilingIsNotATautology`` a single entry
    point it can drive over a MUTATED copy of this module in a subprocess,
    which is the only way to watch these invariants actually refuse.

    Raises:
        AssertionError: If a ceiling was raised above its reviewed high-water
            mark, or if a ceiling was lowered without lowering its mark in the
            same diff (leaving headroom the pin could silently grow back into).
    """
    assert FAILURE_CEILING <= FAILURE_HIGH_WATER_MARK, (
        f"FAILURE_CEILING was RAISED to {FAILURE_CEILING}, above the reviewed "
        f"high-water mark of {FAILURE_HIGH_WATER_MARK}. LOWER it freely — that "
        f"is the Issue #1582 ratchet advancing. RAISING it means a new "
        f"integration failure was waved through instead of fixed."
    )
    assert ERROR_CEILING <= ERROR_HIGH_WATER_MARK, (
        f"ERROR_CEILING was RAISED to {ERROR_CEILING}, above the reviewed "
        f"high-water mark of {ERROR_HIGH_WATER_MARK}. A new collection or "
        f"fixture error was waved through instead of fixed."
    )
    assert FAILURE_CEILING == FAILURE_HIGH_WATER_MARK, (
        f"FAILURE_CEILING ({FAILURE_CEILING}) no longer equals "
        f"FAILURE_HIGH_WATER_MARK ({FAILURE_HIGH_WATER_MARK}). That gap is "
        f"{FAILURE_HIGH_WATER_MARK - FAILURE_CEILING} failure(s) of "
        f"pre-authorised headroom: the pin could grow back into it with every "
        f"assertion green. Lower the mark to match, in the same diff."
    )
    assert ERROR_CEILING == ERROR_HIGH_WATER_MARK, (
        f"ERROR_CEILING ({ERROR_CEILING}) no longer equals "
        f"ERROR_HIGH_WATER_MARK ({ERROR_HIGH_WATER_MARK}). Lower the mark to "
        f"match, in the same diff."
    )


@dataclass(frozen=True)
class CeilingResult:
    """Outcome of a ceiling check.

    Attributes:
        passed: True when neither observed count exceeds its ceiling.
        observed_failures: ``failed`` count read from the report.
        observed_errors: ``errors`` count read from the report.
        message: Human-readable verdict, including the exact ratchet edit to
            make when there is slack.
    """

    passed: bool
    observed_failures: int
    observed_errors: int
    message: str

    @property
    def failure_slack(self) -> int:
        """Unused headroom under ``FAILURE_CEILING`` (0 when at or over it)."""
        return max(0, FAILURE_CEILING - self.observed_failures)

    @property
    def error_slack(self) -> int:
        """Unused headroom under ``ERROR_CEILING`` (0 when at or over it)."""
        return max(0, ERROR_CEILING - self.observed_errors)


def check_ceiling(
    *, failed: int, errors: int, collected: int | None = None
) -> CeilingResult:
    """Compare a measured integration-tier result against the pinned ceiling.

    Growth over either ceiling fails. Sitting at or below both passes, with
    any slack reported loudly so an improvement cannot silently rot into a
    pre-authorised exemption for the next regression.

    Args:
        failed: Number of failing tests observed.
        errors: Number of erroring tests observed.
        collected: Total tests in the report. When supplied it is checked
            against :data:`MINIMUM_COLLECTED_TESTS` so a truncated run cannot
            read as an improvement. ``None`` skips the check, for callers that
            are testing the ceiling logic alone.

    Returns:
        A :class:`CeilingResult` describing the verdict.

    Raises:
        ValueError: If either count is negative, which means the report was
            misparsed rather than that the suite improved impossibly.
    """
    if failed < 0 or errors < 0:
        raise ValueError(
            f"Negative test counts: failed={failed}, errors={errors}\n"
            f"Expected: counts >= 0 parsed from a pytest JUnit XML report\n"
            f"This means the report was misparsed, not that the suite improved."
        )

    breaches: list[str] = []
    if collected is not None and collected < MINIMUM_COLLECTED_TESTS:
        breaches.append(
            f"RUN WAS TRUNCATED: only {collected} tests in the report, below "
            f"the floor of {MINIMUM_COLLECTED_TESTS} (Issue #1582 measured "
            f"1874). A low failure count from a partial run is not an "
            f"improvement — it is the same 'green over nothing' this gate "
            f"exists to prevent. Investigate the crash or timeout; do not "
            f"lower the floor."
        )
    if failed > FAILURE_CEILING:
        breaches.append(
            f"FAILURES GREW: {failed} > ceiling {FAILURE_CEILING} "
            f"(+{failed - FAILURE_CEILING}). The integration tier is pinned by "
            f"Issue #1582 at a known-bad baseline that may only DECREASE. "
            f"Something new is failing — fix it, or adjust the test. Raising "
            f"FAILURE_CEILING is not an available resolution."
        )
    if errors > ERROR_CEILING:
        breaches.append(
            f"ERRORS GREW: {errors} > ceiling {ERROR_CEILING} "
            f"(+{errors - ERROR_CEILING}). An error is a broken fixture, "
            f"import, or collection — not a wrong assertion. Fix the cause; "
            f"raising ERROR_CEILING is not an available resolution."
        )

    if breaches:
        return CeilingResult(
            passed=False,
            observed_failures=failed,
            observed_errors=errors,
            message="Integration failure ceiling BREACHED.\n"
            + "\n".join(f"  - {b}" for b in breaches),
        )

    lines = [
        f"Integration failure ceiling OK: "
        f"{failed} failed (ceiling {FAILURE_CEILING}), "
        f"{errors} errors (ceiling {ERROR_CEILING})."
    ]

    # Slack is stated, never hidden. A ratchet whose improvements go unnoticed
    # stops being a ratchet and becomes a permanent allowance.
    slack_failures = max(0, FAILURE_CEILING - failed)
    slack_errors = max(0, ERROR_CEILING - errors)
    if slack_failures or slack_errors:
        lines.append(
            f"RATCHET CAN ADVANCE — {slack_failures} failure(s) and "
            f"{slack_errors} error(s) of unused headroom. Lower the pin in "
            f"scripts/integration_ceiling.py, in ONE diff:"
        )
        if slack_failures:
            lines.append(
                f"    FAILURE_CEILING = {failed}          "
                f"# was {FAILURE_CEILING}"
            )
            lines.append(
                f"    FAILURE_HIGH_WATER_MARK = {failed}  "
                f"# was {FAILURE_HIGH_WATER_MARK}"
            )
        if slack_errors:
            lines.append(
                f"    ERROR_CEILING = {errors}            "
                f"# was {ERROR_CEILING}"
            )
            lines.append(
                f"    ERROR_HIGH_WATER_MARK = {errors}    "
                f"# was {ERROR_HIGH_WATER_MARK}"
            )
    else:
        lines.append("At the pin exactly — no headroom, nothing to lower.")

    return CeilingResult(
        passed=True,
        observed_failures=failed,
        observed_errors=errors,
        message="\n".join(lines),
    )


def parse_junit_report(report_path: Path) -> tuple[int, int, int]:
    """Read ``failures``, ``errors`` and ``tests`` from a pytest JUnit report.

    pytest emits either a ``<testsuites>`` root wrapping one ``<testsuite>``,
    or a bare ``<testsuite>`` root depending on version, so both shapes are
    handled and every ``<testsuite>`` found is summed.

    Args:
        report_path: Path to the ``--junitxml`` output file.

    Returns:
        Tuple of ``(failures, errors, tests)``.

    Raises:
        FileNotFoundError: If the report does not exist. This is fail-closed on
            purpose: a missing report means the pytest step did not run, and
            treating that as "0 failures" would recreate the exact green-over-
            nothing bug Issue #1582 fixed.
        ValueError: If the XML contains no ``<testsuite>`` element.
    """
    if not report_path.exists():
        raise FileNotFoundError(
            f"JUnit report not found: {report_path}\n"
            f"Expected: the XML written by `pytest --junitxml=<path>`\n"
            f"A missing report means the test step did not run. Refusing to "
            f"report success over zero tests — that is Issue #1582 itself."
        )

    root = ET.parse(report_path).getroot()
    suites = (
        [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    )
    if not suites:
        raise ValueError(
            f"No <testsuite> element in {report_path}\n"
            f"Expected: a pytest JUnit XML report with at least one testsuite\n"
            f"Refusing to infer 0 failures from an unreadable report."
        )

    failures = sum(int(s.get("failures", 0)) for s in suites)
    errors = sum(int(s.get("errors", 0)) for s in suites)
    tests = sum(int(s.get("tests", 0)) for s in suites)
    return failures, errors, tests


def main(argv: list[str] | None = None) -> int:
    """CLI entry point used by CI.

    Args:
        argv: Argument list, defaulting to ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 when the ceiling holds, 1 when it is breached or
        the report cannot be read.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Check the tests/integration/ failure count against the "
            "Issue #1582 ratchet."
        )
    )
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Path to the pytest --junitxml report for tests/integration/.",
    )
    args = parser.parse_args(argv)

    try:
        failed, errors, collected = parse_junit_report(args.report)
    except (FileNotFoundError, ValueError, ET.ParseError) as exc:
        print(f"Integration ceiling check FAILED to read its input:\n{exc}")
        return 1

    result = check_ceiling(failed=failed, errors=errors, collected=collected)
    print(result.message)
    return 0 if result.passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    sys.exit(main())
