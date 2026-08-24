"""Ratchet: no NEW vacuous test may enter the live corpus (Issue #1667).

A vacuous test asserts only a constant (``assert True`` / ``None`` / ``1``) and
can never fail. ``find_vacuous_tests`` is IMPORTED from
``plugins/autonomous-dev/lib/test_pruning_analyzer.py``, never re-expressed
here: a second definition inside a reader is the defect, not the fix. This
ratchet is repo-local and does NOT ship -- ``install_manifest.json`` holds zero
``tests/`` paths, so consumers get the detector without this gate.

WHY THE SUBPROCESS HARNESS: both ceiling operands are constants in this file,
so the assertion is unfalsifiable in-process. Per CHANGELOG.md (#1611) a
literal-plus-equality form "is green at today's values, green after one
legitimate advance (pin 3->2, ceiling 3->2), **and green again when the pin is
re-grown to 3**, which is exactly the hole ``test_the_residual_headroom_is_zero``
was added to close in #1612". ``TestCeilingIsNotATautology`` runs the real
ceiling test over mutants and watches it refuse AND permit.

PIN IS 29, NOT THE 13 PREDICTED: the 13 are a strict subset; the 16 extra are
member-for-member the ``KNOWN_TAUTOLOGICAL`` allowlist of
``tests/regression/smoke/test_tautological_assertions.py``, which the
predicting instrument silently subtracted. Each was AST-verified as a bare
``assert True`` with ``msg is None``. The allowlists stay separate on purpose:
that guard exempts ``assert True, "msg"``, this detector flags it.

Date: 2026-08-25
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# tests/unit/lib/<this file> -> lib -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from test_pruning_analyzer import find_vacuous_tests  # noqa: E402

#: ``tests/archived/`` is dead code; holding it to a live standard is noise.
EXCLUDED_DIR_PREFIXES = ("tests/archived/",)

EXCLUDED_FILES = frozenset(
    {
        # The two tautology guards' own FIXTURE data: pinning them would go red
        # the moment someone adds a detector test case, punishing the correct
        # action.
        "tests/regression/smoke/test_tautological_assertions.py",
        "tests/spec_validation/test_spec_tautological_assertions.py",
        # Issue #1667's own remediation scope, not this ratchet's.
        "tests/test_sync_dev_command.py",
    }
)

#: Vacuous tests existing on 2026-08-25, measured by running the detector over
#: the live corpus. DEBT, not a permission slip: removing an entry is never
#: blocked, adding one is refused.
PINNED_VACUOUS_TESTS: frozenset[tuple[str, str]] = frozenset({
    ("tests/integration/test_agent_tracker_cli_wrapper_issue79.py", "test_cli_shows_deprecation_warning_on_direct_use"),
    ("tests/integration/test_agent_tracker_cli_wrapper_issue79.py", "test_deprecation_warning_mentions_migration_path"),
    ("tests/integration/test_performance_profiling_integration.py", "test_file_writes_dont_block_agent_execution"),
    ("tests/integration/test_performance_profiling_integration.py", "test_metrics_exportable_to_csv"),
    ("tests/integration/test_performance_profiling_integration.py", "test_metrics_provide_trend_analysis"),
    ("tests/integration/test_performance_profiling_integration.py", "test_parallel_agents_profiled_correctly"),
    ("tests/integration/test_performance_profiling_integration.py", "test_performance_summary_includes_total_time"),
    ("tests/integration/test_performance_profiling_integration.py", "test_profiling_ends_after_agent_completes"),
    ("tests/integration/test_performance_profiling_integration.py", "test_profiling_failure_doesnt_stop_workflow"),
    ("tests/integration/test_performance_profiling_integration.py", "test_profiling_overhead_less_than_5_percent_e2e"),
    ("tests/integration/test_performance_profiling_integration.py", "test_profiling_starts_before_agent_invocation"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_handles_disk_full"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_handles_read_only_project"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_handles_symlinks"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_partial_install_cleanup"),
    ("tests/integration/test_uv_execution.py", "test_hook_handles_sigint"),
    ("tests/regression/progression/test_issue_216_escape_sequence_fix.py", "test_warning_detection_with_compile_simulation"),
    ("tests/regression/regression/test_issue_312_batch_git_env_worktree.py", "test_all_dotenv_loading_paths_covered"),
    ("tests/regression/regression/test_issue_312_batch_git_env_worktree.py", "test_all_security_scenarios_covered"),
    ("tests/unit/agents/test_issue_creator.py", "test_agent_has_required_frontmatter"),
    ("tests/unit/agents/test_issue_creator.py", "test_agent_instructions_clear"),
    ("tests/unit/agents/test_issue_creator.py", "test_agent_uses_relevant_skills"),
    ("tests/unit/hooks/test_enforce_tdd.py", "test_neither_found_gives_benefit"),
    ("tests/unit/lib/test_claude_md_updater.py", "test_summary"),
    ("tests/unit/lib/test_hook_bypass.py", "test_log_bypass_used_never_raises_on_disk_error"),
    ("tests/unit/lib/test_performance_profiler.py", "test_concurrent_timer_writes_dont_corrupt_log"),
    ("tests/unit/lib/test_performance_profiler.py", "test_log_rotation_supported"),
    ("tests/unit/scripts/test_genai_install_wrapper.py", "test_error_handling_permission_denied"),
    ("tests/unit/test_issue_1231_multi_issue_extraction.py", "test_issue_extraction_bash_logic_correct"),
})

# An escape hatch without a ceiling on itself is decorative. LOWERING is the
# ratchet advancing and needs no justification (lower the mark in the same
# diff); RAISING is honest only when a new detector shape or widened corpus
# exposed PRE-EXISTING vacuous tests -- say which, in the same diff.
VACUOUS_CEILING = 29

# Highest ceiling ever REVIEWED, so a raise costs a second visible edit. Named,
# not inlined, so every mutation arm derives from it. KNOWN BOUNDED RESIDUAL:
# an upper bound, not a lockstep -- ``test_the_residual_headroom_is_zero``
# holds the gap at zero.
CEILING_HIGH_WATER_MARK = 29

#: Anchor for the line opening the pin literal; resolves populated or empty.
_PIN_DECLARATION_PREFIX = "PINNED_VACUOUS_TESTS: "


def _is_excluded(rel_path: str) -> bool:
    """Report whether ``rel_path`` sits outside this ratchet's corpus.

    Args:
        rel_path: POSIX path relative to the repository root.

    Returns:
        True when excluded by directory prefix or by name.
    """
    return rel_path in EXCLUDED_FILES or rel_path.startswith(EXCLUDED_DIR_PREFIXES)


def scan_live_corpus(repo_root: Path = REPO_ROOT) -> "set[tuple[str, str]]":
    """Return every vacuous ``(relpath, funcname)`` in the live corpus.

    Args:
        repo_root: Repository root to scan beneath.

    Returns:
        Set of ``(posix relative path, test function name)`` pairs.

    Raises:
        RuntimeError: If zero files were scanned -- an empty corpus makes the
            refusing arm trivially true, so it is an error, not a pass.
    """
    findings: "set[tuple[str, str]]" = set()
    scanned = 0
    for path in sorted(repo_root.glob("tests/**/*.py")):
        rel = path.relative_to(repo_root).as_posix()
        if _is_excluded(rel):
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        findings.update((rel, f.name) for f in find_vacuous_tests(text, rel))

    if scanned == 0:
        raise RuntimeError(
            f"Zero test files scanned beneath {repo_root}.\n"
            f"Expected: hundreds under tests/. An empty corpus makes this "
            f"ratchet inert; the scanner is broken, not the repo."
        )
    return findings


class TestScannerPremises:
    """Verify the instrument before trusting one cell of its output."""

    def test_detector_is_the_shipped_one_not_a_local_copy(self) -> None:
        """Object identity, so a local fallback copy cannot creep in."""
        import test_pruning_analyzer

        assert find_vacuous_tests is test_pruning_analyzer.find_vacuous_tests

    def test_the_scan_is_not_empty(self) -> None:
        """POSITIVE CONTROL: a probe returning zero is not evidence of zero."""
        assert scan_live_corpus(), (
            f"the scan found ZERO vacuous tests while the pin holds "
            f"{len(PINNED_VACUOUS_TESTS)}. Either the ratchet fully advanced "
            f"(empty pin and ceiling in the same diff) or the scanner is broken."
        )

    def test_exclusion_filter_discriminates(self) -> None:
        """NEGATIVE CONTROL: it must not pass or reject everything."""
        # Literal paths, NOT derived from EXCLUDED_FILES: iterating that set and
        # asserting each member is in it is the exact tautology (#1147) this
        # file ratchets -- it survives the set being emptied. These go red if
        # the set is emptied, an entry dropped, or the filter inverted.
        assert _is_excluded("tests/regression/smoke/test_tautological_assertions.py")
        assert _is_excluded("tests/test_sync_dev_command.py")
        assert _is_excluded("tests/archived/unit/lib/test_scope_detector.py")
        assert not _is_excluded("tests/unit/lib/test_vacuous_test_ratchet.py")


class TestVacuousRatchet:
    """Refusing growth, permitting advance."""

    def test_no_new_vacuous_tests(self) -> None:
        """REFUSING ARM: a vacuous test not already pinned blocks."""
        new = sorted(scan_live_corpus() - PINNED_VACUOUS_TESTS)
        assert not new, (
            f"{len(new)} vacuous test(s) entered the corpus unpinned:\n"
            + "\n".join(f"  {p}::{n}" for p, n in new)
            + "\nA constant assertion gives zero regression signal. Give it a "
            "real assertion or delete it; pinning it is blocked by the ceiling."
        )

    def test_pin_has_no_stale_entries(self) -> None:
        """PERMITTING ARM: a FIXED test must leave the pin, not linger."""
        stale = sorted(PINNED_VACUOUS_TESTS - scan_live_corpus())
        assert not stale, (
            f"{len(stale)} pinned entr(y/ies) are no longer vacuous:\n"
            + "\n".join(f"  {p}::{n}" for p, n in stale)
            + "\nRemove them and lower VACUOUS_CEILING and "
            "CEILING_HIGH_WATER_MARK to match. That IS the ratchet advancing."
        )

    def test_vacuous_pin_has_a_ceiling(self) -> None:
        """The ceiling. Driven over mutants by TestCeilingIsNotATautology.

        Excludes the residual check so the sanctioned two-constant advance
        stays green under the harness.
        """
        assert len(PINNED_VACUOUS_TESTS) <= VACUOUS_CEILING, (
            f"pin grew to {len(PINNED_VACUOUS_TESTS)}, over VACUOUS_CEILING "
            f"({VACUOUS_CEILING}): a vacuous test was pinned instead of fixed."
        )
        assert VACUOUS_CEILING <= CEILING_HIGH_WATER_MARK, (
            f"VACUOUS_CEILING RAISED to {VACUOUS_CEILING}, over the reviewed "
            f"mark of {CEILING_HIGH_WATER_MARK}. Lower freely; to raise, name "
            f"the cause and raise the mark in the same diff."
        )
        assert VACUOUS_CEILING == len(PINNED_VACUOUS_TESTS), (
            f"VACUOUS_CEILING ({VACUOUS_CEILING}) no longer equals the pin size "
            f"({len(PINNED_VACUOUS_TESTS)}). Slack pre-authorises the next "
            f"vacuous test; lower the ceiling to match."
        )
        assert len(PINNED_VACUOUS_TESTS) <= CEILING_HIGH_WATER_MARK, (
            f"pin ({len(PINNED_VACUOUS_TESTS)}) is above the highest reviewed "
            f"ceiling ({CEILING_HIGH_WATER_MARK}); no ceiling edit authorises "
            f"that on its own."
        )

    def test_the_residual_headroom_is_zero(self) -> None:
        """State the hole rather than hide it, and hold it at zero.

        Kept OUT of the ceiling test so the sanctioned two-constant advance
        stays green under the mutation harness.
        """
        residual = CEILING_HIGH_WATER_MARK - VACUOUS_CEILING
        assert residual >= 0, (
            f"VACUOUS_CEILING ({VACUOUS_CEILING}) exceeds the reviewed mark "
            f"({CEILING_HIGH_WATER_MARK}); the bound is inverted and inert."
        )
        assert residual == 0, (
            f"ceiling is {VACUOUS_CEILING} while the mark stayed "
            f"{CEILING_HIGH_WATER_MARK}, pre-authorising {residual} more pin "
            f"entr(y/ies) no ceiling assertion would see. Lower the mark to "
            f"{VACUOUS_CEILING} -- the last step of the edit you already made."
        )


def _ceiling_anchor(value: int) -> str:
    """Exact source text of the ``VACUOUS_CEILING`` assignment."""
    return f"\nVACUOUS_CEILING = {value}\n"


def _mark_anchor(value: int) -> str:
    """Exact source text of the ``CEILING_HIGH_WATER_MARK`` assignment."""
    return f"\nCEILING_HIGH_WATER_MARK = {value}\n"


class TestCeilingIsNotATautology:
    """Watch the ceiling refuse AND permit, over mutants, out of process.

    Five arms, each pinned to the invariant it must trip -- asserted on the
    failure TEXT, not the exit code, so an arm proves WHICH invariant caught it.
    Control passes; lowering pin+ceiling together is permitted; dropping a pin
    entry with the ceiling left high is refused by ``ceiling == len(pin)``;
    raising the ceiling alone is refused by ``ceiling <= mark`` (the #1612
    re-growth shape); raising all THREE constants is refused only by the
    EXTERNAL WITNESS ``_run`` appends -- MEASURED: against intra-module
    invariants alone that mutant exited 0, since each relates two operands that
    both moved. That witness is the discipline
    ``tests/unit/scripts/test_integration_ceiling.py`` uses.

    WHY THE ANTI-SLACK ARM SHRINKS THE PIN: a growing pin cannot reach
    ``ceiling == len(pin)``. MEASURED -- growing the pin alone trips
    ``len(pin) <= ceiling`` first, and holding the ceiling above a grown pin
    needs a raised mark, which the witness refuses at import. Only a SHRINKING
    pin leaves the ceiling with slack, which is what that invariant is for.
    """

    @staticmethod
    def _source() -> str:
        """This module's own source text."""
        return Path(__file__).resolve().read_text(encoding="utf-8")

    @staticmethod
    def _sub(source: str, anchor: str, replacement: str) -> str:
        """Replace ``anchor`` exactly once; a no-op or ambiguity is an error."""
        count = source.count(anchor)
        assert count == 1, (
            f"anchor {anchor!r} appears {count} time(s), expected one. The "
            f"harness would mutate nothing and report a false green. Re-anchor."
        )
        return source.replace(anchor, replacement)

    @classmethod
    def _line(cls, source: str, prefix: str) -> str:
        """The single line of ``source`` starting with ``prefix``."""
        lines = [ln for ln in source.splitlines(keepends=True) if ln.startswith(prefix)]
        assert len(lines) == 1, (
            f"{prefix!r} matches {len(lines)} line(s), expected one. Re-anchor."
        )
        return lines[0]

    @classmethod
    def _mutate(cls, arm: str) -> str:
        """Build the mutated source for ``arm``."""
        src = cls._source()
        if arm == "control":
            return src
        if arm == "raise_ceiling_alone":
            return cls._sub(src, _ceiling_anchor(VACUOUS_CEILING),
                            _ceiling_anchor(VACUOUS_CEILING + 1))
        if arm in ("lower_both", "slack_after_advance"):
            assert PINNED_VACUOUS_TESTS, "premise: there is an entry to drop"
            victim = sorted(PINNED_VACUOUS_TESTS)[-1]
            src = cls._sub(src, cls._line(src, f'    ("{victim[0]}", "{victim[1]}"),'), "")
            if arm == "slack_after_advance":
                # The two arms differ by EXACTLY this one edit. Leaving the
                # ceiling and mark untouched keeps them consistent with each
                # other, so the first two assertions hold and only the
                # anti-slack invariant is left to catch the mutant.
                return src
            return cls._sub(src, _ceiling_anchor(VACUOUS_CEILING),
                            _ceiling_anchor(VACUOUS_CEILING - 1))
        assert arm == "raise_all_three", f"unknown arm {arm!r}"
        decl = cls._line(src, _PIN_DECLARATION_PREFIX)
        src = cls._sub(src, decl, decl + '    ("tests/unit/synthetic.py", "test_synthetic"),\n')
        src = cls._sub(src, _ceiling_anchor(VACUOUS_CEILING),
                       _ceiling_anchor(VACUOUS_CEILING + 1))
        return cls._sub(src, _mark_anchor(CEILING_HIGH_WATER_MARK),
                        _mark_anchor(CEILING_HIGH_WATER_MARK + 1))

    @staticmethod
    def _run(tmp_path: Path, source: str) -> subprocess.CompletedProcess:
        """Run only ``test_vacuous_pin_has_a_ceiling`` against ``source``.

        The mutant runs out of tree, so ``-k`` restricts the run to the ceiling
        test (constants only) and ``PYTHONPATH`` keeps the detector import
        resolvable. The appended external-witness assertion carries this
        module's reviewed mark so a three-constant raise cannot pass.
        """
        witness = (
            f"\nassert CEILING_HIGH_WATER_MARK <= {CEILING_HIGH_WATER_MARK}, (\n"
            f"    'CEILING_HIGH_WATER_MARK raised to %s, above the externally "
            f"reviewed mark of {CEILING_HIGH_WATER_MARK}.' % CEILING_HIGH_WATER_MARK)\n"
        )
        mutant = tmp_path / "test_ceiling_mutant.py"
        mutant.write_text(source + witness, encoding="utf-8")

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(LIB_DIR), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

        return subprocess.run(
            [sys.executable, "-m", "pytest", str(mutant), "-k",
             "test_vacuous_pin_has_a_ceiling", "-q", "--no-header",
             "-p", "no:cacheprovider", "-p", "no:randomly"],
            capture_output=True, text=True, cwd=str(tmp_path), env=env, timeout=180,
        )

    @pytest.mark.parametrize(
        "arm,must_refuse,expect,why",
        [
            ("control", False, None,
             "the UNMUTATED module must pass, else no arm is interpretable"),
            # The expected strings carry INTERPOLATED values on purpose. pytest
            # prints the source of the assertions PRECEDING the failing one, so
            # a bare literal from any message body appears in later arms' output
            # too -- MEASURED: "VACUOUS_CEILING RAISED to" matched the slack arm
            # as well, and would have passed on the wrong invariant.
            ("slack_after_advance", True,
             f"no longer equals the pin size ({len(PINNED_VACUOUS_TESTS) - 1})",
             "a dropped pin entry with the ceiling left high is slack that "
             "pre-authorises the next vacuous test"),
            ("lower_both", False, None,
             "lowering both is the ratchet advancing, never blocked"),
            ("raise_ceiling_alone", True,
             f"VACUOUS_CEILING RAISED to {VACUOUS_CEILING + 1},",
             "a ceiling raised past the reviewed mark is the #1612 re-growth bypass"),
            ("raise_all_three", True, "above the externally reviewed mark",
             "the external witness must refuse a three-constant raise"),
        ],
    )
    def test_ceiling_arm(
        self, tmp_path: Path, arm: str, must_refuse: bool, expect: "str | None", why: str
    ) -> None:
        """Drive one mutation arm and assert the ceiling's verdict."""
        result = self._run(tmp_path, self._mutate(arm))
        refused = result.returncode != 0

        assert refused == must_refuse, (
            f"arm {arm!r}: expected {'REFUSED' if must_refuse else 'PERMITTED'}, "
            f"got {'REFUSED' if refused else 'PERMITTED'} -- {why}.\n"
            f"{result.stdout}\n{result.stderr}"
        )
        if expect is not None:
            assert expect in result.stdout, (
                f"arm {arm!r} refused, but not on the invariant it targets: "
                f"expected {expect!r} in the failure text. A return code alone "
                f"cannot tell two arms apart -- before #1667 remediation, two "
                f"of them tripped one invariant and left the others unwatched."
                f"\n{result.stdout}\n{result.stderr}"
            )
        if arm == "control":
            assert "1 passed" in result.stdout, (
                f"the harness selected {result.stdout!r}; a `-k` matching "
                f"nothing exits 0 and would read as a pass on every arm."
            )
