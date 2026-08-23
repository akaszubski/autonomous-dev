"""Guards for the Issue #1582 integration-tier failure ceiling.

Issue #1582: ``tests/integration/`` had never executed. A module-scope rebind
of ``pytest.mark.integration`` turned the whole tier into skips, and CI's
``pytest tests/integration/`` step reported success over 0 of 1,834 tests.

This module holds four independent guards:

1. ``TestCeilingRefusesAndPermits`` — the ceiling watched REFUSING (growth) and
   PERMITTING (the real measured baseline). A guard observed only passing is
   indistinguishable from one that cannot fail.
2. ``TestCeilingIsNotATautology`` — a subprocess mutation harness proving the
   constant-versus-constant pin invariants can actually fire.
3. ``TestMarkerRebindNeverReturns`` — the class-level regression guard. Bans
   the rebind PATTERN repo-wide rather than the two instances that caused this
   bug.
4. ``TestRunIntegrationFlagIsAnInertNoOp`` — pins the decision made about the
   now-consumerless ``--run-integration`` flag.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# tests/unit/scripts/test_integration_ceiling.py
#   parents[0] = tests/unit/scripts
#   parents[1] = tests/unit
#   parents[2] = tests
#   parents[3] = <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
MODULE_PATH = SCRIPTS_DIR / "integration_ceiling.py"

sys.path.insert(0, str(SCRIPTS_DIR))

from integration_ceiling import (  # noqa: E402
    ERROR_CEILING,
    ERROR_HIGH_WATER_MARK,
    FAILURE_CEILING,
    FAILURE_HIGH_WATER_MARK,
    check_ceiling,
    parse_junit_report,
    verify_pin_invariants,
)

# =============================================================================
# THE EXTERNAL WITNESS — the second key
# =============================================================================
#
# These duplicate the pinned high-water marks ON PURPOSE, and it is the one
# place this repo's "never hardcode an intermediary copy" rule is deliberately
# set aside. The reason is structural, and it was MEASURED rather than assumed:
# the first version of this file asserted the pin only from inside
# scripts/integration_ceiling.py, and the mutation harness below proved that
# unfalsifiable — raising FAILURE_CEILING and FAILURE_HIGH_WATER_MARK together
# left `ceiling <= mark` and `ceiling == mark` both satisfied, and the mutant
# printed INVARIANTS_PASSED. No arrangement of constants inside a single module
# can refuse a coordinated edit to all of them.
#
# So the authority to RAISE the pin lives outside the module. A mutation that
# touches only scripts/integration_ceiling.py now trips these, and raising the
# real pin requires editing TWO files in one diff — which is exactly the
# review-visible action a raise should be.
#
# LOWERING never needs to touch this file: the assertion is `<=`.
REVIEWED_FAILURE_HIGH_WATER_MARK = 512
REVIEWED_ERROR_HIGH_WATER_MARK = 11


# =============================================================================
# 1. THE CEILING, WATCHED BOTH WAYS
# =============================================================================


class TestCeilingRefusesAndPermits:
    """The ceiling must refuse growth and permit the measured baseline."""

    def test_permits_the_measured_baseline(self):
        """PERMITTING ARM. The real 2026-08-23 measurement must pass.

        512 failed / 11 errors is what ``pytest tests/integration`` actually
        produced, set-stable across two serial runs. If this arm ever goes red
        the pin is below reality and the tier is a permanently-red check —
        the exact outcome Issue #1582 was written to avoid.
        """
        result = check_ceiling(failed=512, errors=11)
        assert result.passed, result.message
        assert result.failure_slack == 0
        assert result.error_slack == 0

    def test_refuses_one_extra_failure(self):
        """REFUSING ARM. A single new failure over the pin must fail.

        One over, not a round number: the boundary is where a ratchet either
        works or is decoration.
        """
        result = check_ceiling(failed=FAILURE_CEILING + 1, errors=ERROR_CEILING)
        assert not result.passed
        assert "FAILURES GREW" in result.message

    def test_refuses_one_extra_error(self):
        """REFUSING ARM, second axis. Errors are pinned independently.

        Authored to a DIFFERENT shape than the failure arm on purpose: errors
        and failures are separate root-cause classes, and a single combined
        count would let a new import break hide behind a fixed assertion.
        """
        result = check_ceiling(failed=FAILURE_CEILING, errors=ERROR_CEILING + 1)
        assert not result.passed
        assert "ERRORS GREW" in result.message

    def test_an_error_regression_is_not_masked_by_fixed_failures(self):
        """The two axes must not net off against each other.

        Fixing 100 failures while breaking one fixture must still be refused.
        A single aggregate ``failed + errors`` ceiling would pass this.
        """
        result = check_ceiling(
            failed=FAILURE_CEILING - 100, errors=ERROR_CEILING + 1
        )
        assert not result.passed, (
            "100 fixed failures masked a new collection error. The ceiling is "
            "netting its two axes against each other."
        )

    def test_permits_and_reports_slack_when_failures_drop(self):
        """Improvement is never blocked, but never silent either."""
        result = check_ceiling(failed=FAILURE_CEILING - 30, errors=ERROR_CEILING)
        assert result.passed
        assert result.failure_slack == 30
        assert "RATCHET CAN ADVANCE" in result.message
        # The advisory must name the exact edit, or it will be ignored.
        assert f"FAILURE_CEILING = {FAILURE_CEILING - 30}" in result.message

    def test_negative_counts_are_refused_rather_than_treated_as_improvement(self):
        """A misparsed report must be loud, not read as a perfect score."""
        with pytest.raises(ValueError, match="Negative test counts"):
            check_ceiling(failed=-1, errors=0)


class TestReportParsingFailsClosed:
    """A missing or unreadable report must never read as zero failures."""

    def test_missing_report_raises_rather_than_reporting_zero(self, tmp_path):
        """This is Issue #1582's own bug shape: success over nothing."""
        with pytest.raises(FileNotFoundError, match="did not run"):
            parse_junit_report(tmp_path / "absent.xml")

    def test_report_without_testsuite_is_refused(self, tmp_path):
        report = tmp_path / "empty.xml"
        report.write_text("<testsuites></testsuites>", encoding="utf-8")
        with pytest.raises(ValueError, match="No <testsuite>"):
            parse_junit_report(report)

    def test_parses_counts_from_a_real_pytest_report_shape(self, tmp_path):
        """POSITIVE CONTROL for the parser, using pytest's actual XML shape.

        The attribute names and nesting here were copied from a real
        ``--junitxml`` file emitted by this repo's pytest on 2026-08-23, not
        invented, so a pytest upgrade that renames them turns this red.
        """
        report = tmp_path / "junit.xml"
        report.write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<testsuites name="pytest tests">'
            '<testsuite name="pytest" errors="11" failures="512" skipped="209"'
            ' tests="1834" time="55.8">'
            '<testcase classname="a.B" name="test_c" time="0.1"/>'
            "</testsuite></testsuites>",
            encoding="utf-8",
        )
        assert parse_junit_report(report) == (512, 11, 1834)

    def test_parses_a_bare_testsuite_root(self, tmp_path):
        """Some pytest versions emit <testsuite> as the root element."""
        report = tmp_path / "bare.xml"
        report.write_text(
            '<testsuite name="pytest" errors="2" failures="3" tests="9"/>',
            encoding="utf-8",
        )
        assert parse_junit_report(report) == (3, 2, 9)


class TestTruncatedRunCannotReadAsImprovement:
    """A partial report must not sail under the ceiling (Issue #1582's shape)."""

    def test_refuses_a_truncated_run_with_few_failures(self):
        """REFUSING ARM. 12 failures out of 40 tests is a crash, not a fix.

        This is the shape a mid-run OOM or timeout leaves behind: a tiny report
        whose failure count is comfortably under a 512 ceiling.
        """
        result = check_ceiling(failed=12, errors=0, collected=40)
        assert not result.passed
        assert "TRUNCATED" in result.message

    def test_permits_the_full_measured_run(self):
        """PERMITTING ARM. The real 1844-test report must pass the floor."""
        result = check_ceiling(failed=512, errors=11, collected=1844)
        assert result.passed, result.message

    def test_floor_is_skipped_when_collected_is_not_supplied(self):
        """Ceiling-only callers must not be forced to fabricate a count."""
        assert check_ceiling(failed=512, errors=11, collected=None).passed


# =============================================================================
# 2. ANTI-TAUTOLOGY MUTATION HARNESS
# =============================================================================


class TestCeilingIsNotATautology:
    """``verify_pin_invariants`` must fail on a RAISE, not merely be asserted.

    ``FAILURE_CEILING == FAILURE_HIGH_WATER_MARK`` is unfalsifiable in-process:
    both operands are constants in the same module, so an edit that raises the
    ceiling AND its mark together moves them in lockstep and nothing fires.
    A ratchet that cannot be shown to fail is decoration.

    The arms below therefore drive the invariants over MUTATED copies of
    ``scripts/integration_ceiling.py`` in a subprocess. Every anchor is DERIVED
    from the module's current constants rather than hardcoded, so the harness
    keeps working as the ratchet advances — a hardcoded ``= 512`` anchor would
    stop resolving the moment someone lowers the pin, turning the correct
    maintenance action red.
    """

    @staticmethod
    def _source() -> str:
        return MODULE_PATH.read_text(encoding="utf-8")

    @staticmethod
    def _anchor(name: str, value: int) -> str:
        """Exact source text of a top-level constant assignment."""
        return f"\n{name} = {value}\n"

    @classmethod
    def _substitute(cls, source: str, anchor: str, replacement: str) -> str:
        """Replace ``anchor`` exactly once, refusing a no-op or an ambiguity."""
        count = source.count(anchor)
        assert count == 1, (
            f"mutation anchor {anchor!r} appears {count} time(s), expected "
            f"exactly one. The harness would mutate nothing or the wrong site "
            f"and report a green that means nothing. Re-anchor it."
        )
        return source.replace(anchor, replacement)

    @staticmethod
    def _run_invariants(tmp_path: Path, source: str) -> subprocess.CompletedProcess:
        """Import a mutated copy of the module and run its pin invariants."""
        mutant_dir = tmp_path / "mutant"
        mutant_dir.mkdir(exist_ok=True)
        (mutant_dir / "integration_ceiling.py").write_text(source, encoding="utf-8")

        runner = tmp_path / "run_invariants.py"
        runner.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(mutant_dir)!r})\n"
            "import integration_ceiling as m\n"
            "m.verify_pin_invariants()\n"
            # The external witness, injected from THIS file. Without it a
            # mutation that raises a ceiling and its mark together satisfies
            # every intra-module invariant — measured, see the module-level
            # comment on REVIEWED_FAILURE_HIGH_WATER_MARK.
            f"assert m.FAILURE_HIGH_WATER_MARK <= {REVIEWED_FAILURE_HIGH_WATER_MARK}, (\n"
            f"    'FAILURE_HIGH_WATER_MARK was raised to %s, above the "
            f"externally reviewed high-water mark of "
            f"{REVIEWED_FAILURE_HIGH_WATER_MARK}.' % m.FAILURE_HIGH_WATER_MARK)\n"
            f"assert m.ERROR_HIGH_WATER_MARK <= {REVIEWED_ERROR_HIGH_WATER_MARK}, (\n"
            f"    'ERROR_HIGH_WATER_MARK was raised to %s, above the "
            f"externally reviewed high-water mark of "
            f"{REVIEWED_ERROR_HIGH_WATER_MARK}.' % m.ERROR_HIGH_WATER_MARK)\n"
            "print('INVARIANTS_PASSED')\n",
            encoding="utf-8",
        )
        return subprocess.run(
            [sys.executable, str(runner)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=120,
        )

    def test_control_unmutated_copy_passes(self, tmp_path):
        """NEGATIVE CONTROL for the harness itself.

        Without this, a red from the mutants below could equally mean "a
        subprocess cannot import this module at all". A probe needs a known-good
        input before one cell of its output means anything.
        """
        result = self._run_invariants(tmp_path, self._source())
        assert result.returncode == 0, (
            f"the UNMUTATED module failed its own invariants, so every other "
            f"arm here is uninterpretable.\n{result.stdout}\n{result.stderr}"
        )
        assert "INVARIANTS_PASSED" in result.stdout

    def test_raising_ceiling_and_mark_together_is_refused(self, tmp_path):
        """THE REPRODUCER. The two-constant escape hatch must be RED.

        Raise ``FAILURE_CEILING`` and ``FAILURE_HIGH_WATER_MARK`` in the same
        edit — the shape that would let the next new integration failure be
        absorbed rather than fixed, with every assertion still green.
        """
        target = FAILURE_HIGH_WATER_MARK + 1
        source = self._source()
        source = self._substitute(
            source,
            self._anchor("FAILURE_CEILING", FAILURE_CEILING),
            self._anchor("FAILURE_CEILING", target),
        )
        source = self._substitute(
            source,
            self._anchor("FAILURE_HIGH_WATER_MARK", FAILURE_HIGH_WATER_MARK),
            self._anchor("FAILURE_HIGH_WATER_MARK", target),
        )

        result = self._run_invariants(tmp_path, source)
        assert result.returncode != 0, (
            f"FAILURE_CEILING and FAILURE_HIGH_WATER_MARK were both raised to "
            f"{target} and the invariants still PASSED. The ceiling has no "
            f"ceiling: the next regression can be absorbed by a two-constant "
            f"edit that no assertion sees.\n{result.stdout}"
        )
        assert "high-water mark" in result.stderr, (
            f"the mutant failed for some reason other than the high-water "
            f"assertion, so this proves nothing about it.\n{result.stderr}"
        )

    def test_lowering_ceiling_but_leaving_slack_is_refused(self, tmp_path):
        """Residual headroom must be RED. Slack is a pre-authorised exemption.

        A DIFFERENT mutation shape from the arm above: this one LOWERS the
        ceiling (the sanctioned direction) but forgets the mark, leaving room
        the pin could grow back into.
        """
        source = self._substitute(
            self._source(),
            self._anchor("FAILURE_CEILING", FAILURE_CEILING),
            self._anchor("FAILURE_CEILING", FAILURE_CEILING - 10),
        )
        result = self._run_invariants(tmp_path, source)
        assert result.returncode != 0, (
            "FAILURE_CEILING was lowered by 10 while FAILURE_HIGH_WATER_MARK "
            "stayed put, and the invariants passed. That gap is 10 failures of "
            "headroom the pin can silently grow back into."
        )
        assert "no longer equals" in result.stderr

    def test_error_axis_is_mutation_covered_too(self, tmp_path):
        """The error ceiling gets its own mutation, not just the failure one.

        Covering only ``FAILURE_*`` would leave ``ERROR_*`` asserted but
        unproven — the exact "scoped to the instance" failure this harness
        exists to prevent.
        """
        target = ERROR_HIGH_WATER_MARK + 1
        source = self._source()
        source = self._substitute(
            source,
            self._anchor("ERROR_CEILING", ERROR_CEILING),
            self._anchor("ERROR_CEILING", target),
        )
        source = self._substitute(
            source,
            self._anchor("ERROR_HIGH_WATER_MARK", ERROR_HIGH_WATER_MARK),
            self._anchor("ERROR_HIGH_WATER_MARK", target),
        )
        result = self._run_invariants(tmp_path, source)
        assert result.returncode != 0, (
            f"ERROR_CEILING and ERROR_HIGH_WATER_MARK were both raised to "
            f"{target} and the invariants still passed."
        )

    def test_lowering_both_together_is_permitted(self, tmp_path):
        """THE PERMITTING ARM. Advancing the ratchet must never be blocked.

        Lowering the ceiling and its mark together is the correct maintenance
        action. If this were red, the guard would be applying pressure AGAINST
        fixing integration tests — worse than no guard at all.
        """
        source = self._source()
        source = self._substitute(
            source,
            self._anchor("FAILURE_CEILING", FAILURE_CEILING),
            self._anchor("FAILURE_CEILING", FAILURE_CEILING - 10),
        )
        source = self._substitute(
            source,
            self._anchor("FAILURE_HIGH_WATER_MARK", FAILURE_HIGH_WATER_MARK),
            self._anchor("FAILURE_HIGH_WATER_MARK", FAILURE_HIGH_WATER_MARK - 10),
        )
        result = self._run_invariants(tmp_path, source)
        assert result.returncode == 0, (
            f"lowering FAILURE_CEILING and FAILURE_HIGH_WATER_MARK together — "
            f"the ratchet advancing — was REFUSED. The guard is pressuring "
            f"against the correct action.\n{result.stdout}\n{result.stderr}"
        )

    def test_live_module_satisfies_its_own_invariants(self):
        """The shipped constants must themselves be consistent."""
        verify_pin_invariants()

    def test_live_pin_agrees_with_the_external_witness(self):
        """THE LIVE ENFORCEMENT of the two-key rule.

        Raising the real pin now requires editing scripts/integration_ceiling.py
        AND this file in one diff. Lowering needs only the module — the
        assertion is ``<=`` so the ratchet advances without ceremony.
        """
        assert FAILURE_HIGH_WATER_MARK <= REVIEWED_FAILURE_HIGH_WATER_MARK, (
            f"FAILURE_HIGH_WATER_MARK ({FAILURE_HIGH_WATER_MARK}) was raised "
            f"above the externally reviewed value "
            f"({REVIEWED_FAILURE_HIGH_WATER_MARK}). Raising the Issue #1582 "
            f"pin is a two-key action: justify it here as well, in the same "
            f"diff, naming the new route that made pre-existing failures "
            f"visible."
        )
        assert ERROR_HIGH_WATER_MARK <= REVIEWED_ERROR_HIGH_WATER_MARK, (
            f"ERROR_HIGH_WATER_MARK ({ERROR_HIGH_WATER_MARK}) was raised above "
            f"the externally reviewed value ({REVIEWED_ERROR_HIGH_WATER_MARK})."
        )


# =============================================================================
# 3. THE CLASS-LEVEL REGRESSION GUARD
# =============================================================================

#: Matches an assignment onto pytest's global marker namespace, e.g.
#: ``pytest.mark.integration = pytest.mark.skipif(...)``. The marker name is
#: NOT pinned to "integration": the defect class is "rebinding ANY global
#: pytest marker", and pinning the name would scope the guard to the single
#: instance that prompted it.
_MARKER_REBIND = re.compile(r"^\s*pytest\.mark\.\w+\s*=", re.MULTILINE)


def _all_test_sources() -> list[Path]:
    """Every Python file under tests/, INCLUDING tests/archived/.

    Archived files are deliberately in scope. ``norecursedirs = tests/archived``
    only stops RECURSIVE discovery from ``testpaths``; an explicit path still
    collects them. Measured 2026-08-23::

        pytest tests/archived/unit/test_claude_md_optimization.py --collect-only
        -> 23 tests collected

    So the archived copy of this defect was live, not inert. Excluding archived
    here would move the failure rather than fix it.
    """
    return sorted(p for p in (REPO_ROOT / "tests").rglob("*.py"))


class TestMarkerRebindNeverReturns:
    """No file may rebind a global ``pytest.mark.*`` attribute (Issue #1582)."""

    def test_no_test_file_rebinds_a_global_pytest_marker(self):
        """REFUSING ARM, at repo scope.

        ``tests/conftest.py`` resolves auto-markers by name via
        ``getattr(pytest.mark, marker_name)``. Any module-scope rebind of a
        ``pytest.mark.*`` attribute therefore silently reprograms the marker
        for EVERY test in the corresponding tier, from the moment that one
        module is collected.
        """
        offenders = [
            f"{path.relative_to(REPO_ROOT)}:{content[:m.start()].count(chr(10)) + 1}"
            for path in _all_test_sources()
            for content in [path.read_text(encoding="utf-8", errors="replace")]
            for m in _MARKER_REBIND.finditer(content)
        ]
        assert not offenders, (
            "Global pytest marker rebind(s) found — this is Issue #1582, in "
            "which one such line turned all 1,834 tests under "
            "tests/integration/ into skips and made CI report success over "
            "zero tests:\n"
            + "\n".join(f"  - {o}" for o in offenders)
            + "\nUse a local decorator variable, or apply @pytest.mark.skipif "
            "to the specific tests that need it. Never assign onto "
            "pytest.mark.*."
        )

    def test_positive_control_the_detector_catches_the_original_defect(self, tmp_path):
        """POSITIVE CONTROL. The exact deleted line must still be detected.

        Without this, a green from the sweep above could equally mean the
        regex matches nothing at all. This is the verbatim text removed from
        ``tests/integration/test_documentation_references.py``.
        """
        probe = tmp_path / "reintroduced.py"
        probe.write_text(
            "import pytest\n"
            "\n"
            "pytest.mark.integration = pytest.mark.skipif(\n"
            '    "not config.getoption(\'--run-integration\')",\n'
            '    reason="Integration tests require --run-integration flag"\n'
            ")\n",
            encoding="utf-8",
        )
        assert _MARKER_REBIND.search(
            probe.read_text(encoding="utf-8")
        ), "the detector does not catch the very line that caused Issue #1582"

    def test_positive_control_catches_a_different_marker_name(self, tmp_path):
        """The guard covers the CLASS, not the ``integration`` instance.

        A DIFFERENT shape from the reproducer: a different marker, a different
        right-hand side. If the guard only caught ``pytest.mark.integration``
        it would be scoped to the one bug that prompted it, and the next tier
        to go dark would be ``unit`` or ``smoke``.
        """
        probe = tmp_path / "other_marker.py"
        probe.write_text(
            "import pytest\npytest.mark.smoke = pytest.mark.xfail\n",
            encoding="utf-8",
        )
        assert _MARKER_REBIND.search(probe.read_text(encoding="utf-8"))

    def test_negative_control_legitimate_marker_usage_is_permitted(self, tmp_path):
        """PERMITTING ARM. Real marker usage must NOT trip the detector.

        ``@pytest.mark.integration`` as a decorator, ``pytestmark = [...]``,
        and comparisons are all legitimate and appear throughout this repo
        (e.g. test_distributed_training_coordinator_enhanced.py). A guard that
        flagged these would be unusable and would be disabled within a week.
        """
        probe = tmp_path / "legit.py"
        probe.write_text(
            "import pytest\n"
            "\n"
            "pytestmark = [pytest.mark.integration]\n"
            "\n"
            "@pytest.mark.integration\n"
            "def test_thing():\n"
            "    marker = pytest.mark.integration\n"
            "    assert marker is not None\n",
            encoding="utf-8",
        )
        assert not _MARKER_REBIND.search(probe.read_text(encoding="utf-8")), (
            "the detector flags legitimate marker usage; it would be turned "
            "off rather than obeyed"
        )

    def test_the_real_integration_markers_still_function_as_markers(self):
        """The decorators that use the marker legitimately must survive.

        ``test_distributed_training_coordinator_enhanced.py`` applies
        ``@pytest.mark.integration`` for real. Removing the rebind must leave
        those working as MARKERS — the fix must not trade one breakage for
        another.
        """
        target = (
            REPO_ROOT
            / "tests"
            / "integration"
            / "test_distributed_training_coordinator_enhanced.py"
        )
        assert target.exists(), f"fixture file for this guard is missing: {target}"
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest", str(target),
                "-m", "integration", "--collect-only", "-q",
                "--no-cov", "-p", "no:randomly", "-p", "no:cacheprovider",
            ],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=300,
        )
        assert result.returncode == 0, (
            f"`-m integration` selection failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "no tests ran" not in result.stdout, (
            "`-m integration` selected nothing — the marker is no longer "
            "functioning as a marker."
        )


# =============================================================================
# 4. THE --run-integration DECISION
# =============================================================================


class TestCiRunsTheTierThroughTheCeiling:
    """The gate is worthless if CI does not invoke it (Issue #1582).

    Verifying the SOURCE I edited is not verifying the copy that EXECUTES.
    These read .github/workflows/ci.yml as parsed YAML — the same text the
    runner consumes — rather than trusting that the edit landed.
    """

    @staticmethod
    def _integration_step() -> dict:
        # DELIBERATELY UNGUARDED import. `pytest.importorskip("yaml")` was
        # tried first and rejected: it would turn these four guards into
        # silent skips on any machine without PyYAML, and a guard that cannot
        # fail cannot inform — the CI step could drift back to green-over-
        # nothing with this file reporting "passed". PyYAML is installed
        # explicitly by every job in ci.yml ("pip install pytest ... pyyaml"),
        # so an ImportError here is a real breakage and must be loud.
        import yaml

        workflow = yaml.safe_load(
            (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
                encoding="utf-8"
            )
        )
        for step in workflow["jobs"]["test"]["steps"]:
            if step.get("name") == "Run integration tests":
                return step
        pytest.fail("no 'Run integration tests' step in ci.yml")

    def test_ci_invokes_the_ceiling_check(self):
        """Without this call the step is green-over-nothing again."""
        run = self._integration_step()["run"]
        assert "integration_ceiling.py" in run, (
            "CI runs the integration tier but does not check it against the "
            "Issue #1582 ceiling. Either the failures are unbounded or the "
            "step is reporting success over a run nobody inspected."
        )
        assert "--junitxml" in run, "the ceiling has no report to read"

    def test_ci_runs_the_tier_serially(self):
        """`-n auto` is nondeterministic here — see the module docstring.

        Measured: two consecutive `-n auto` runs gave 498 and 503 failures,
        their failing-node sets differing by 7. Serial gave 512 twice with an
        identical set. Reintroducing `-n auto` would make this gate flake.
        """
        run = self._integration_step()["run"]
        assert "-n auto" not in run, (
            "`-n auto` was reintroduced to the integration step. Its failure "
            "count is nondeterministic (measured 498 vs 503 on identical "
            "runs), which makes the ceiling flaky."
        )

    def test_ci_still_bounds_the_run_with_a_timeout(self):
        """A hung tier must not burn the runner budget."""
        run = self._integration_step()["run"]
        assert "--timeout=300" in run
        assert "--timeout-method=signal" in run

    def test_ceiling_decides_the_step_not_pytest_exit_code(self):
        """pytest exits nonzero at 512 failures; the ratchet must arbitrate.

        Without discarding pytest's status the step is permanently red, which
        trains everyone to ignore it — the failure mode this design exists to
        prevent.
        """
        run = self._integration_step()["run"]
        pytest_line = next(
            ln for ln in run.splitlines() if "pytest tests/integration/" in ln
        )
        assert pytest_line.rstrip().endswith("|| true"), (
            f"the pytest invocation does not discard its exit code, so the "
            f"step is permanently red regardless of the ceiling: "
            f"{pytest_line!r}"
        )


#: Matches an actual READ of the flag — ``getoption("--run-integration")`` in
#: either quote style, with optional whitespace. Deliberately NOT a substring
#: test for the two words; see ``test_no_code_consumes_the_flag``.
_FLAG_CONSUMPTION = re.compile(
    r"""getoption\(\s*['"]--run-integration['"]"""
)


class TestRunIntegrationFlagIsAnInertNoOp:
    """``--run-integration`` is retained, registered, and consumed by nothing."""

    def test_flag_is_still_registered_so_old_invocations_do_not_hard_error(self):
        """Deleting a registered flag breaks callers that still pass it.

        pytest exits with "unrecognized arguments" on an unknown flag, so a
        local script or shell alias still passing ``--run-integration`` would
        hard-error. It stays registered for that reason.
        """
        conftest = (REPO_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
        assert '"--run-integration"' in conftest

    def test_flag_help_text_no_longer_claims_to_gate_anything(self):
        """The old help text was false and was the misleading affordance.

        It advertised "Run integration tests (skipped by default)", which
        described the SYMPTOM of the rebind bug as if it were policy.
        """
        conftest = (REPO_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
        assert "skipped by default" not in conftest, (
            "the --run-integration help text still claims integration tests "
            "are skipped by default; after Issue #1582 they always run"
        )
        assert "DEPRECATED" in conftest

    def test_no_code_consumes_the_flag(self):
        """Zero behavioural consumers — the claim, checked rather than assumed.

        ``getoption("--run-integration")`` is the only way to read the flag.
        Both call sites were the rebind itself and are now gone. Archived files
        are in scope for the reason given in ``_all_test_sources``.

        The match is on the CALL EXPRESSION, not on the two words appearing
        somewhere in the same file. A substring probe was tried first and
        reported this very file and tests/conftest.py as consumers, because
        both merely discuss the flag in prose — a probe that flags its own
        documentation cannot distinguish a consumer from a comment.
        """
        consumers = [
            str(path.relative_to(REPO_ROOT))
            for path in _all_test_sources()
            if path.resolve() != Path(__file__).resolve()
            and _FLAG_CONSUMPTION.search(
                path.read_text(encoding="utf-8", errors="replace")
            )
        ]
        assert not consumers, (
            f"--run-integration is documented as an inert no-op but is read "
            f"by: {consumers}. Either remove the consumer or update the "
            f"deprecation note in tests/conftest.py."
        )

    def test_positive_control_the_consumption_detector_catches_a_real_read(
        self, tmp_path
    ):
        """POSITIVE CONTROL. An empty consumer list must mean something.

        A probe that returns zero is not evidence of zero until it has been
        shown flagging a known-positive input.
        """
        probe = tmp_path / "consumer.py"
        probe.write_text(
            "def f(config):\n"
            "    return config.getoption('--run-integration')\n",
            encoding="utf-8",
        )
        assert _FLAG_CONSUMPTION.search(probe.read_text(encoding="utf-8"))

    def test_negative_control_prose_mentions_are_not_consumers(self, tmp_path):
        """Discussing the flag in a comment must not count as consuming it."""
        probe = tmp_path / "prose.py"
        probe.write_text(
            "# The --run-integration flag is a deprecated no-op; nothing\n"
            "# calls getoption for it any more.\n",
            encoding="utf-8",
        )
        assert not _FLAG_CONSUMPTION.search(probe.read_text(encoding="utf-8"))
