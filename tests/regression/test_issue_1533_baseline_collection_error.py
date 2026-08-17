"""Regression tests for Issue #1533 — a zeroed baseline that looked measured.

THE DEFECT
----------
The pipeline's baseline capture (STEP 1 of `commands/implement.md`) ran pytest,
handed the output to `fix_forward.parse_failing_tests()`, and wrote the
resulting test IDs to `/tmp/baseline_failing_tests.txt`. When pytest aborted
during COLLECTION — one test module importing a module that only exists under
`hooks/archived/` was enough — zero tests executed, no `FAILED` lines were
emitted, the parse returned an empty set, and STEP 1 printed
"Baseline failing tests: 0".

That `0` is indistinguishable from a genuinely green tree. STEP 8's fix-forward
classifier then compared real failures against an empty baseline and would have
called every one of them NEW. The timeout route was already sentinel-guarded
(Issue #1094); every other route to "zero tests executed" was silently rounded
down to a legitimate zero.

THE INVARIANT NOW ENCODED
-------------------------
A capture that executed zero tests is a measurement failure, never a baseline.
`fix_forward.detect_capture_failure()` checks three independent signals (exit
code, abort markers, executed-test count) so routes not yet identified are
caught too, and writes a distinct `__COLLECTION_ERROR__` sentinel that STEP 8
treats exactly as it treats `__TIMEOUT__`.

THREE STATES, ALL ASSERTED HERE
-------------------------------
- clean scope        -> a real count (a measured 0 stays 0);
- collection error   -> `__COLLECTION_ERROR__`, never 0;
- timeout            -> `__TIMEOUT__` (Issue #1094 behaviour, unbroken).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"

sys.path.insert(0, str(LIB_DIR))

from fix_forward import (  # noqa: E402
    COLLECTION_ERROR_SENTINEL,
    TIMEOUT_SENTINEL,
    classify_failures,
    detect_capture_failure,
    is_capture_failure_sentinel,
    parse_failing_tests,
)

# The measured output of the defect, verbatim (pytest 9.1.1, exit code 2).
COLLECTION_ERROR_OUTPUT = """\
ERROR tests/integration/test_auto_add_to_regression_workflow.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
================== 10 skipped, 12 warnings, 1 error in 3.73s ===================
"""

CLEAN_OUTPUT = "=============== 11324 passed, 4 skipped in 182.10s ===============\n"

FAILING_OUTPUT = """\
tests/unit/test_alpha.py::test_one FAILED
tests/unit/test_beta.py::test_two FAILED
=================== 2 failed, 11322 passed in 180.44s ===================
"""

NO_TESTS_OUTPUT = "==================== no tests ran in 0.01s ====================\n"


# ---------------------------------------------------------------------------
# Snippet mirrors — the exact logic embedded in implement.md STEP 1 / STEP 8.
# ---------------------------------------------------------------------------


def _step1_capture(*, fake_run, timeout_seconds: int = 600) -> str:
    """Mirror of the STEP 1 baseline capture; returns the baseline file body."""
    lines: list[str] = []
    try:
        result = fake_run(
            ["pytest", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        output = result.stdout + result.stderr
        failure = detect_capture_failure(output, returncode=result.returncode)
        if failure is not None:
            lines.append(failure.sentinel)
        else:
            lines.extend(sorted(parse_failing_tests(output)))
    except subprocess.TimeoutExpired:
        lines.append(TIMEOUT_SENTINEL)
    return "\n".join(lines)


def _step8_classify(*, baseline_body: str, current_failing: set[str] | None) -> str:
    """Mirror of the STEP 8 read + classify; returns the printed status line."""
    baseline_contents = baseline_body.strip()
    if baseline_contents.startswith(TIMEOUT_SENTINEL):
        baseline_failing = None
    elif baseline_contents.startswith(COLLECTION_ERROR_SENTINEL):
        baseline_failing = None
    elif baseline_contents:
        baseline_failing = set(baseline_contents.split("\n"))
    else:
        baseline_failing = set()

    if baseline_failing is None or current_failing is None:
        return "Fix-forward classification: SKIPPED (baseline or current capture unavailable)"
    result = classify_failures(baseline_failing, current_failing)
    return (
        f"Fixed: {len(result['fixed'])} | "
        f"Pre-existing: {len(result['pre_existing_remaining'])} | "
        f"New: {len(result['new_failures'])}"
    )


class _FakeResult:
    def __init__(self, stdout: str, returncode: int) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _runner(stdout: str, returncode: int):
    def run(*_args: object, **_kwargs: object) -> _FakeResult:
        return _FakeResult(stdout, returncode)

    return run


def _timeout_runner(*_args: object, **kwargs: object):
    raise subprocess.TimeoutExpired(cmd="pytest", timeout=kwargs.get("timeout", 1))


# ---------------------------------------------------------------------------
# AC1 / AC2 — a failed measurement is never reported as a baseline of 0.
# ---------------------------------------------------------------------------


class TestCollectionErrorIsNotZero:
    """A collection error yields a distinct sentinel, never `0`."""

    def test_collection_error_output_is_detected(self):
        failure = detect_capture_failure(COLLECTION_ERROR_OUTPUT, returncode=2)
        assert failure is not None, (
            "the measured collection-error output was accepted as a real "
            "measurement — this is exactly Issue #1533"
        )
        assert failure.sentinel == COLLECTION_ERROR_SENTINEL

    def test_collection_error_baseline_body_is_sentinel_not_empty(self):
        body = _step1_capture(fake_run=_runner(COLLECTION_ERROR_OUTPUT, 2))
        assert body == COLLECTION_ERROR_SENTINEL, (
            f"expected the collection-error sentinel, got {body!r}. An empty "
            "body would be read downstream as 'baseline: 0 failing tests'."
        )
        assert body != ""

    def test_abort_marker_alone_is_enough(self):
        """Detection must not depend solely on the exit code being available."""
        failure = detect_capture_failure(COLLECTION_ERROR_OUTPUT, returncode=None)
        assert failure is not None
        assert failure.sentinel == COLLECTION_ERROR_SENTINEL

    @pytest.mark.parametrize("returncode", [2, 3, 4, 5])
    def test_non_measuring_exit_codes_are_failures(self, returncode: int):
        """Interrupted / internal error / usage error / nothing collected."""
        failure = detect_capture_failure(CLEAN_OUTPUT, returncode=returncode)
        assert failure is not None
        assert failure.sentinel == COLLECTION_ERROR_SENTINEL

    def test_zero_executed_tests_is_a_measurement_failure(self):
        """AC2: the general invariant, independent of the collection-error route."""
        failure = detect_capture_failure(NO_TESTS_OUTPUT, returncode=None)
        assert failure is not None, (
            "a capture that executed zero tests must be a measurement failure, "
            "not an empty baseline"
        )

    def test_unparseable_output_is_a_measurement_failure(self):
        """No summary line at all means nothing can be trusted."""
        failure = detect_capture_failure("", returncode=None)
        assert failure is not None

    def test_summary_only_zero_counts_is_a_measurement_failure(self):
        """A summary line accounting for zero tests is not a baseline."""
        failure = detect_capture_failure(
            "============ 0 passed, 3 warnings in 0.42s ============\n", returncode=None
        )
        assert failure is not None


# ---------------------------------------------------------------------------
# AC4 — NEGATIVE CONTROL: a real 0 stays a real 0.
# ---------------------------------------------------------------------------


class TestCleanRunStillReportsRealZero:
    """A fix that makes everything 'unknown' is worse than the bug."""

    def test_clean_run_is_not_a_capture_failure(self):
        assert detect_capture_failure(CLEAN_OUTPUT, returncode=0) is None

    def test_clean_run_yields_empty_baseline_not_a_sentinel(self):
        body = _step1_capture(fake_run=_runner(CLEAN_OUTPUT, 0))
        assert body == ""
        assert not is_capture_failure_sentinel(body)

    def test_clean_baseline_is_classified_not_skipped(self):
        body = _step1_capture(fake_run=_runner(CLEAN_OUTPUT, 0))
        out = _step8_classify(baseline_body=body, current_failing=set())
        assert out == "Fixed: 0 | Pre-existing: 0 | New: 0"
        assert "SKIPPED" not in out

    def test_the_three_states_are_mutually_distinguishable(self):
        clean = _step1_capture(fake_run=_runner(CLEAN_OUTPUT, 0))
        collection_error = _step1_capture(fake_run=_runner(COLLECTION_ERROR_OUTPUT, 2))
        timed_out = _step1_capture(fake_run=_timeout_runner)
        assert len({clean, collection_error, timed_out}) == 3, (
            f"states collapsed: clean={clean!r} "
            f"collection_error={collection_error!r} timeout={timed_out!r}"
        )
        assert collection_error == COLLECTION_ERROR_SENTINEL
        assert timed_out == TIMEOUT_SENTINEL
        assert clean == ""


# ---------------------------------------------------------------------------
# AC5 — NEGATIVE CONTROL: fix-forward still works.
# ---------------------------------------------------------------------------


class TestFixForwardStillClassifies:
    """A real new failure must still be classified as NEW."""

    def test_real_failures_are_parsed_from_a_measured_run(self):
        assert detect_capture_failure(FAILING_OUTPUT, returncode=1) is None
        assert parse_failing_tests(FAILING_OUTPUT) == {
            "tests/unit/test_alpha.py::test_one",
            "tests/unit/test_beta.py::test_two",
        }

    def test_new_failure_is_still_new(self):
        body = _step1_capture(fake_run=_runner(FAILING_OUTPUT, 1))
        out = _step8_classify(
            baseline_body=body,
            current_failing={
                "tests/unit/test_alpha.py::test_one",
                "tests/unit/test_gamma.py::test_three",
            },
        )
        assert "New: 1" in out, out
        assert "Fixed: 1" in out
        assert "Pre-existing: 1" in out
        assert "SKIPPED" not in out


class TestAbortMarkersAreLineAnchored:
    """Abort markers must match pytest BANNERS, not any text that contains them.

    THE REGRESSION (found by review of the Issue #1533 fix)
    -------------------------------------------------------
    The first cut matched each abort marker as a case-insensitive substring of
    the whole output blob. `tests/unit/hooks/test_prompt_integrity_fail_closed.py`
    really does define `class TestGateInternalErrorsFailClosed`, so pytest's own
    short-summary line for any failure in that class lowercases to a string
    containing `internalerror`. A genuine, measured, exit-code-1 failing run was
    therefore classified as `__COLLECTION_ERROR__` and its real failure silently
    discarded — the exact defect class #1533 exists to kill, reintroduced by a
    different route, landing on the class that guards the prompt-integrity gate
    against silent fail-open.

    Detection is now anchored to the banner shapes pytest actually emits:
    `!!! Interrupted: ... !!!`, `INTERNALERROR>` at line start, and the
    `no tests ran` summary line. A marker word inside a test ID, class name, or
    assertion message can no longer be read as an abort banner.
    """

    #: The real colliding line, verbatim in shape: this class exists on disk at
    #: tests/unit/hooks/test_prompt_integrity_fail_closed.py:61.
    REAL_COLLIDING_FAILURE = (
        "=========================== short test summary info ===========================\n"
        "FAILED tests/unit/hooks/test_prompt_integrity_fail_closed.py::"
        "TestGateInternalErrorsFailClosed::"
        "test_validate_word_count_internal_error_denies[AttributeError] - "
        "AssertionError: expected deny\n"
        "======================== 1 failed, 5 passed in 0.42s =========================\n"
    )

    def test_real_colliding_class_name_is_not_an_abort_marker(self):
        """A measured failure in TestGateInternalErrorsFailClosed stays measured."""
        assert detect_capture_failure(self.REAL_COLLIDING_FAILURE, returncode=1) is None, (
            "a genuine exit-1 failing run was misread as a capture failure because "
            "'internalerror' appears inside a real test class name"
        )

    def test_real_colliding_failure_id_survives_into_the_baseline(self):
        """The signal must reach the baseline file, not be replaced by a sentinel."""
        body = _step1_capture(fake_run=_runner(self.REAL_COLLIDING_FAILURE, 1))
        assert not is_capture_failure_sentinel(body), body
        assert body == (
            "tests/unit/hooks/test_prompt_integrity_fail_closed.py::"
            "TestGateInternalErrorsFailClosed::"
            "test_validate_word_count_internal_error_denies[AttributeError]"
        ), body

    def test_colliding_baseline_still_classifies_instead_of_skipping(self):
        """End to end: the discarded measurement used to force STEP 8 to SKIP."""
        body = _step1_capture(fake_run=_runner(self.REAL_COLLIDING_FAILURE, 1))
        out = _step8_classify(
            baseline_body=body,
            current_failing={"tests/unit/test_new.py::test_broken"},
        )
        assert "SKIPPED" not in out, out
        assert "New: 1" in out, out

    @pytest.mark.parametrize(
        "test_id",
        [
            # The real one, on disk today.
            "tests/unit/hooks/test_prompt_integrity_fail_closed.py::"
            "TestGateInternalErrorsFailClosed::test_denies",
            # `::` after a class named for the thing it tests reproduces the
            # `interrupted:` marker verbatim.
            "tests/unit/test_capture.py::TestInterrupted::test_interrupted_banner",
            # Parametrize values carry spaces, so they can reproduce the
            # multi-word markers exactly. No current in-repo collision for these,
            # but "does not collide today" is not "cannot collide".
            "tests/unit/test_capture.py::test_marker[error during collection]",
            "tests/unit/test_capture.py::test_marker[3 errors during collection]",
            "tests/unit/test_capture.py::test_marker[no tests ran]",
            "tests/unit/test_capture.py::test_error_during_collection_is_detected",
            "tests/unit/test_capture.py::test_no_tests_ran_is_a_capture_failure",
        ],
    )
    def test_marker_words_inside_test_ids_are_not_banners(self, test_id: str):
        """Every marker, not just the one with a known collision."""
        short_summary = (
            f"FAILED {test_id} - AssertionError: nope\n"
            "==================== 1 failed, 3 passed in 0.20s ====================\n"
        )
        assert detect_capture_failure(short_summary, returncode=1) is None, test_id

        verbose = (
            f"{test_id} FAILED\n"
            "==================== 1 failed, 3 passed in 0.20s ====================\n"
        )
        assert detect_capture_failure(verbose, returncode=1) is None, test_id

    def test_marker_words_inside_assertion_messages_are_not_banners(self):
        """Failure reasons quote pytest's own vocabulary all the time."""
        output = (
            "FAILED tests/unit/test_a.py::test_one - AssertionError: expected "
            "'INTERNALERROR> boom' / 'Interrupted: 1 error during collection' / "
            "'no tests ran', got nothing\n"
            "==================== 1 failed, 3 passed in 0.20s ====================\n"
        )
        assert detect_capture_failure(output, returncode=1) is None

    @pytest.mark.parametrize(
        "banner",
        [
            "!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!",
            "!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!",
            "!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors !!!!!!!!!!!!!!!!!!!!!!!!",
            "INTERNALERROR> Traceback (most recent call last):",
            "==================== no tests ran in 0.01s ====================",
            "no tests ran in 0.01s",
        ],
    )
    def test_real_banners_are_still_detected(self, banner: str):
        """POSITIVE CONTROL: anchoring must not blind the detector."""
        output = banner + "\n=============== 9 passed in 1.00s ===============\n"
        failure = detect_capture_failure(output, returncode=None)
        assert failure is not None, f"banner no longer detected: {banner!r}"
        assert failure.sentinel == COLLECTION_ERROR_SENTINEL

    def test_banner_wins_even_when_a_failed_line_is_present(self):
        """A partially-measured, then-aborted run is still untrustworthy."""
        output = (
            "FAILED tests/unit/test_a.py::test_one - assert False\n"
            "!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!\n"
            "=============== 1 failed, 1 error in 1.00s ===============\n"
        )
        failure = detect_capture_failure(output, returncode=None)
        assert failure is not None
        assert failure.sentinel == COLLECTION_ERROR_SENTINEL


class TestShortSummaryFormatIsParsed:
    """The second zeroing route, found by the three-state check.

    `-q` (the pipeline's own baseline invocation) emits no verbose per-test
    lines. Failures appear ONLY in pytest's short test summary, as
    `FAILED <id> - <reason>`. The parser matched only the verbose shape, so a
    run with real failures produced an empty baseline — the same silent zero as
    a collection error, reached by a different route.
    """

    def test_short_summary_line_is_parsed(self):
        output = (
            "=========== short test summary info ===========\n"
            "FAILED tests/unit/test_a.py::test_one - AssertionError: nope\n"
            "=================== 1 failed, 5 passed in 0.32s ===================\n"
        )
        assert parse_failing_tests(output) == {"tests/unit/test_a.py::test_one"}

    def test_short_summary_without_reason_is_parsed(self):
        assert parse_failing_tests("FAILED tests/unit/test_a.py::test_one\n") == {
            "tests/unit/test_a.py::test_one"
        }

    def test_parametrized_id_with_spaces_is_preserved(self):
        output = "FAILED tests/unit/test_a.py::test_one[a b] - assert False\n"
        assert parse_failing_tests(output) == {"tests/unit/test_a.py::test_one[a b]"}

    def test_parametrized_id_containing_the_reason_separator_is_not_truncated(self):
        """`- ` inside a parametrize value must not be mistaken for the reason split.

        pytest separates the test ID from the failure reason with ` - `, but a
        parametrize value may legitimately contain that same sequence. Splitting
        on the first occurrence produced the truncated ID
        `tests/foo.py::test_bar[a`, which matches nothing downstream and would be
        classified as a spurious NEW failure while the real ID went missing.
        """
        output = "FAILED tests/foo.py::test_bar[a - b] - AssertionError: x\n"
        assert parse_failing_tests(output) == {"tests/foo.py::test_bar[a - b]"}

    def test_both_shapes_agree_and_deduplicate(self):
        output = (
            "tests/unit/test_a.py::test_one FAILED\n"
            "FAILED tests/unit/test_a.py::test_one - assert False\n"
            "= 1 failed in 0.10s =\n"
        )
        assert parse_failing_tests(output) == {"tests/unit/test_a.py::test_one"}

    def test_unparseable_failure_shape_is_a_capture_failure(self):
        """Instrument self-check: 'N failed' with zero parsed IDs is never a baseline."""
        output = "!! 2 tests blew up !!\n=========== 2 failed, 3 passed in 0.10s ===========\n"
        failure = detect_capture_failure(output, returncode=1)
        assert failure is not None, (
            "pytest reported failures but none could be parsed — that empty set "
            "must not be handed downstream as a baseline"
        )

    def test_live_pytest_failure_is_parsed_end_to_end(self, tmp_path: Path):
        """Against the real pytest binary, in the real -q shape, not a fixture."""
        scope = tmp_path / "scope"
        scope.mkdir()
        (scope / "test_live.py").write_text(
            "def test_passes():\n    assert True\n\n\ndef test_fails():\n    assert False\n"
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(scope), "--tb=no", "-q",
             "--no-cov", "-p", "no:cacheprovider", "-p", "no:randomly"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr
        assert detect_capture_failure(output, returncode=result.returncode) is None, output[-1500:]
        parsed = parse_failing_tests(output)
        assert len(parsed) == 1, f"expected 1 parsed failure, got {parsed}\n{output[-1500:]}"
        assert any(t.endswith("::test_fails") for t in parsed), parsed


# ---------------------------------------------------------------------------
# AC3 — STEP 8 treats the new sentinel exactly as it treats __TIMEOUT__.
# ---------------------------------------------------------------------------


class TestStep8SkipsOnEitherSentinel:
    """Symmetry with Issue #1094 — an unknown baseline is never compared."""

    @pytest.mark.parametrize("sentinel", [TIMEOUT_SENTINEL, COLLECTION_ERROR_SENTINEL])
    def test_sentinel_baseline_skips_classification(self, sentinel: str):
        out = _step8_classify(
            baseline_body=sentinel,
            current_failing={"tests/unit/test_alpha.py::test_one"},
        )
        assert "SKIPPED" in out, out

    @pytest.mark.parametrize("sentinel", [TIMEOUT_SENTINEL, COLLECTION_ERROR_SENTINEL])
    def test_sentinel_is_recognised_by_helper(self, sentinel: str):
        assert is_capture_failure_sentinel(sentinel + "\n")

    def test_real_baseline_is_not_mistaken_for_a_sentinel(self):
        assert not is_capture_failure_sentinel("tests/unit/test_a.py::test_one\n")
        assert not is_capture_failure_sentinel("")

    def test_collection_error_roundtrip_does_not_report_new_failures(self):
        """The end-to-end defect: broken capture must never manufacture NEW."""
        body = _step1_capture(fake_run=_runner(COLLECTION_ERROR_OUTPUT, 2))
        out = _step8_classify(
            baseline_body=body,
            current_failing={
                "tests/unit/test_alpha.py::test_one",
                "tests/unit/test_beta.py::test_two",
            },
        )
        assert "SKIPPED" in out, out
        assert "New: 2" not in out

    def test_step8_current_capture_failure_also_skips(self):
        """Symmetric: a broken CURRENT capture must not report everything fixed."""
        failure = detect_capture_failure(COLLECTION_ERROR_OUTPUT, returncode=2)
        current_failing = None if failure is not None else set()
        out = _step8_classify(
            baseline_body="tests/unit/test_alpha.py::test_one",
            current_failing=current_failing,
        )
        assert "SKIPPED" in out
        assert "Fixed: 1" not in out


# ---------------------------------------------------------------------------
# The fix must be visibly present in the source-of-truth command file.
# ---------------------------------------------------------------------------


class TestImplementMdWiring:
    """STEP 1 writes the sentinel; STEP 8 reads it. Both must be in the file."""

    @pytest.fixture(scope="class")
    def implement_md(self) -> str:
        return IMPLEMENT_MD.read_text(encoding="utf-8")

    def test_step1_calls_the_detector(self, implement_md: str):
        assert "detect_capture_failure" in implement_md

    def test_step1_writes_collection_error_sentinel(self, implement_md: str):
        assert COLLECTION_ERROR_SENTINEL in implement_md

    def test_step8_detects_collection_error_sentinel(self, implement_md: str):
        assert "startswith('__COLLECTION_ERROR__')" in implement_md

    def test_step8_still_detects_timeout_sentinel(self, implement_md: str):
        """Issue #1094 must remain wired — this fix does not disturb it."""
        assert "startswith('__TIMEOUT__')" in implement_md

    def test_issue_number_documented(self, implement_md: str):
        assert "1533" in implement_md


# ---------------------------------------------------------------------------
# AC6 — the canonical baseline scope collects without aborting.
# ---------------------------------------------------------------------------


class TestCanonicalScopeCollects:
    """The measurement instrument itself must work."""

    def test_canonical_baseline_scope_collects_cleanly(self):
        from pipeline_state import CANONICAL_BASELINE_CMD

        dirs = [a for a in CANONICAL_BASELINE_CMD[1:] if not a.startswith("-")]
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov",
             "-p", "no:randomly", *dirs],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        combined = result.stdout + result.stderr
        assert result.returncode not in (2, 3, 4), (
            f"collection of the canonical baseline scope aborted "
            f"(exit {result.returncode}). Zero tests would execute and the "
            f"pipeline baseline would read as 0.\n{combined[-2000:]}"
        )
        # The final summary line is the verdict: "N tests collected in Xs" on a
        # healthy run, "M errors in Xs" when collection aborted. Asserting on the
        # whole buffer would trip over test IDs that quote pytest's own markers.
        tail = [ln.strip().strip("=").strip() for ln in combined.splitlines() if ln.strip()]
        summary = next(
            (ln for ln in reversed(tail) if re.search(r"\bin\s+[\d.]+\s*s\b", ln)), ""
        )
        assert re.search(r"\b\d+\s+tests?\s+collected\b", summary), (
            f"collect-only did not report a test count; summary was {summary!r}\n"
            f"{combined[-2000:]}"
        )
        assert "error" not in summary.lower(), summary
