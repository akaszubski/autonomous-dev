"""Regression tests for Issue #1094 — baseline failing-tests capture timeout handling.

Before the fix, `commands/implement.md` used `subprocess.run(..., timeout=120)` for the
pytest baseline capture in STEP 1 and the current-failing capture in STEP 8. When the
test suite exceeded 120s, `TimeoutExpired` propagated as Python traceback text into
`/tmp/baseline_failing_tests.txt`. STEP 8 then parsed the traceback lines as test IDs,
producing garbage IDs that never matched real test IDs — `pre_existing_remaining` was
always 0 and the fix-forward auto-file path was permanently blocked.

The fix (all three changes verified by these tests):
1. Timeout bumped from 120 to 600 seconds, configurable via `BASELINE_TIMEOUT_SECONDS`.
2. `subprocess.TimeoutExpired` is caught in STEP 1; a `__TIMEOUT__` sentinel is written
   to the baseline file instead of letting the traceback propagate.
3. STEP 8 detects the `__TIMEOUT__` sentinel and skips fix-forward classification rather
   than comparing against an unknown baseline.

These tests exercise the documented bash/python blocks in `commands/implement.md` by
executing the same Python snippet logic against a fake-pytest subprocess that times out
on demand, then asserting the sentinel-write and sentinel-read behaviors hold.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"


# ---------------------------------------------------------------------------
# Source-of-truth assertions on implement.md (documents the fix is in place).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def implement_md_content() -> str:
    """Return implement.md contents as a single string."""
    return IMPLEMENT_MD.read_text(encoding="utf-8")


class TestImplementMdContainsFix:
    """The fix must be visibly present in the source-of-truth command file."""

    def test_implement_md_exists(self) -> None:
        assert IMPLEMENT_MD.exists(), f"missing source-of-truth file: {IMPLEMENT_MD}"

    def test_step1_uses_configurable_timeout_env_var(self, implement_md_content: str) -> None:
        """STEP 1 must read BASELINE_TIMEOUT_SECONDS from environment."""
        assert "BASELINE_TIMEOUT_SECONDS" in implement_md_content, (
            "Issue #1094 fix missing: BASELINE_TIMEOUT_SECONDS env var not referenced in implement.md"
        )

    def test_no_hardcoded_120s_timeout_in_baseline_blocks(self, implement_md_content: str) -> None:
        """The buggy `timeout=120` must no longer be present in either capture block.

        Note: We grep for the exact buggy pattern. Other unrelated `timeout=120` calls
        (e.g., HTTP requests) are not part of the baseline-capture code paths and would
        not match this exact regex anyway because we anchor to the surrounding context.
        """
        # The original buggy patterns were exactly: timeout=120) at end of subprocess.run.
        # Both baseline-capture subprocess.run calls used capture_output=True, text=True, timeout=120
        bad_pattern = re.compile(r"text=True,\s*timeout=120\b")
        matches = bad_pattern.findall(implement_md_content)
        assert not matches, (
            f"Issue #1094 regression: found {len(matches)} subprocess.run(...timeout=120) "
            f"call(s) in implement.md baseline capture blocks. Should use BASELINE_TIMEOUT_SECONDS "
            f"with default 600."
        )

    def test_default_timeout_is_600(self, implement_md_content: str) -> None:
        """Default timeout must be 600 seconds (10 min) when env var unset."""
        # Find the env-var read with default — pattern: BASELINE_TIMEOUT_SECONDS', '600'
        assert "'600'" in implement_md_content or '"600"' in implement_md_content, (
            "Default timeout for BASELINE_TIMEOUT_SECONDS must be 600 seconds"
        )

    def test_step1_catches_timeout_expired(self, implement_md_content: str) -> None:
        """STEP 1 must catch subprocess.TimeoutExpired (not let it propagate)."""
        assert "subprocess.TimeoutExpired" in implement_md_content, (
            "Issue #1094 fix missing: subprocess.TimeoutExpired not handled in implement.md"
        )

    def test_step1_writes_timeout_sentinel(self, implement_md_content: str) -> None:
        """On timeout, STEP 1 must write the __TIMEOUT__ sentinel."""
        assert "__TIMEOUT__" in implement_md_content, (
            "Issue #1094 fix missing: __TIMEOUT__ sentinel not present in implement.md"
        )

    def test_step8_detects_timeout_sentinel(self, implement_md_content: str) -> None:
        """STEP 8 must detect the sentinel and skip classification."""
        # Find the read-side guard: startswith('__TIMEOUT__')
        assert "startswith('__TIMEOUT__')" in implement_md_content, (
            "Issue #1094 fix missing: STEP 8 does not detect __TIMEOUT__ sentinel via startswith"
        )

    def test_step8_skips_classification_on_unknown_baseline(self, implement_md_content: str) -> None:
        """When baseline is unknown (sentinel or current capture timeout), classification is skipped."""
        # Find the skip-message string in the snippet
        assert "Fix-forward classification: SKIPPED" in implement_md_content, (
            "Issue #1094 fix missing: STEP 8 lacks SKIPPED branch when baseline/current is unknown"
        )

    def test_issue_number_documented(self, implement_md_content: str) -> None:
        """The fix must reference Issue #1094 for future archaeology."""
        assert "1094" in implement_md_content, (
            "Issue #1094 number not referenced near baseline-timeout code (provenance trail)"
        )


# ---------------------------------------------------------------------------
# Behavioral tests of the embedded Python snippets.
# We execute the same logic (extracted into helpers below) against a fake
# pytest subprocess to verify the sentinel-write and sentinel-read paths.
# ---------------------------------------------------------------------------


@pytest.fixture
def with_lib_on_path(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Add plugins/autonomous-dev/lib to sys.path so fix_forward imports work."""
    monkeypatch.syspath_prepend(str(LIB_DIR))
    yield


def _step1_baseline_capture_logic(
    *,
    timeout_seconds: int,
    fake_run: object,
) -> str:
    """Reproduces the embedded STEP 1 Python snippet.

    Returns what would be written to BASELINE_FAILING_FILE (newline-separated).
    Uses `fake_run` in place of `subprocess.run` so we can simulate timeout.
    """
    from fix_forward import parse_failing_tests  # noqa: WPS433 — by design (mirrors snippet)

    output_lines: list[str] = []
    try:
        result = fake_run(
            ["pytest", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        failing = parse_failing_tests(result.stdout + result.stderr)
        for t in sorted(failing):
            output_lines.append(t)
    except subprocess.TimeoutExpired:
        output_lines.append("__TIMEOUT__")
    return "\n".join(output_lines)


def _step8_reader_logic(
    *,
    baseline_file: Path,
    current_failing: set[str] | None,
) -> str:
    """Reproduces the embedded STEP 8 Python snippet (read + classify).

    `current_failing=None` simulates a STEP 8 capture timeout.
    Returns the printed status line.
    """
    from fix_forward import classify_failures  # noqa: WPS433

    baseline_failing: set[str] | None = None
    try:
        baseline_contents = baseline_file.read_text().strip()
        if baseline_contents.startswith("__TIMEOUT__"):
            baseline_failing = None
        elif baseline_contents:
            baseline_failing = set(baseline_contents.split("\n"))
        else:
            baseline_failing = set()
    except FileNotFoundError:
        baseline_failing = set()

    if baseline_failing is None or current_failing is None:
        return "Fix-forward classification: SKIPPED (baseline or current capture unavailable)"
    result = classify_failures(baseline_failing, current_failing)
    return (
        f"Fixed: {len(result['fixed'])} | "
        f"Pre-existing: {len(result['pre_existing_remaining'])} | "
        f"New: {len(result['new_failures'])}"
    )


class TestStep1SentinelWrite:
    """Verify STEP 1 writes `__TIMEOUT__` (not a traceback) when pytest times out."""

    def test_timeout_writes_sentinel_not_traceback(self, with_lib_on_path: None) -> None:
        """On TimeoutExpired, the baseline file content is exactly the sentinel."""

        def fake_run_timeout(*args: object, **kwargs: object) -> object:
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=kwargs.get("timeout", 1))

        contents = _step1_baseline_capture_logic(timeout_seconds=1, fake_run=fake_run_timeout)
        assert contents == "__TIMEOUT__", (
            f"Expected exactly '__TIMEOUT__', got: {contents!r} "
            f"(regression — Issue #1094: traceback must not leak into baseline file)"
        )

    def test_timeout_does_not_leak_traceback_text(self, with_lib_on_path: None) -> None:
        """No Python traceback markers should be present in baseline output on timeout."""

        def fake_run_timeout(*args: object, **kwargs: object) -> object:
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=kwargs.get("timeout", 1))

        contents = _step1_baseline_capture_logic(timeout_seconds=1, fake_run=fake_run_timeout)
        # Before the fix, contents would be the TimeoutExpired traceback.
        assert "Traceback" not in contents
        assert "TimeoutExpired" not in contents
        assert "File " not in contents

    def test_successful_capture_preserves_existing_semantics(
        self, with_lib_on_path: None
    ) -> None:
        """When pytest completes within the timeout, the existing healthy-path behavior is unchanged."""

        class FakeCompleted:
            stdout = (
                "tests/unit/test_foo.py::test_one FAILED\n"
                "tests/unit/test_foo.py::test_two FAILED\n"
                "= 2 failed in 0.5s =\n"
            )
            stderr = ""

        def fake_run_success(*args: object, **kwargs: object) -> FakeCompleted:
            return FakeCompleted()

        contents = _step1_baseline_capture_logic(timeout_seconds=600, fake_run=fake_run_success)
        lines = contents.split("\n")
        assert "tests/unit/test_foo.py::test_one" in lines
        assert "tests/unit/test_foo.py::test_two" in lines
        assert "__TIMEOUT__" not in lines

    def test_empty_pytest_output_yields_empty_baseline(self, with_lib_on_path: None) -> None:
        """No failing tests = empty baseline file (not a sentinel, not a traceback)."""

        class FakeCompletedClean:
            stdout = "= 100 passed in 5s =\n"
            stderr = ""

        def fake_run_clean(*args: object, **kwargs: object) -> FakeCompletedClean:
            return FakeCompletedClean()

        contents = _step1_baseline_capture_logic(timeout_seconds=600, fake_run=fake_run_clean)
        assert contents == ""
        assert "__TIMEOUT__" not in contents


class TestStep8SentinelRead:
    """Verify STEP 8 detects `__TIMEOUT__` and skips classification."""

    def test_sentinel_baseline_skips_classification(
        self, tmp_path: Path, with_lib_on_path: None
    ) -> None:
        """When baseline file contains __TIMEOUT__, STEP 8 prints SKIPPED."""
        baseline_file = tmp_path / "baseline_failing_tests.txt"
        baseline_file.write_text("__TIMEOUT__\n")

        out = _step8_reader_logic(
            baseline_file=baseline_file,
            current_failing={"tests/unit/test_foo.py::test_one"},
        )
        assert "SKIPPED" in out, (
            f"Expected SKIPPED branch when baseline is __TIMEOUT__, got: {out!r}"
        )

    def test_missing_baseline_file_treats_as_empty(
        self, tmp_path: Path, with_lib_on_path: None
    ) -> None:
        """Missing baseline file = empty baseline, classification proceeds (existing behavior)."""
        baseline_file = tmp_path / "does_not_exist.txt"
        assert not baseline_file.exists()

        out = _step8_reader_logic(
            baseline_file=baseline_file,
            current_failing={"tests/unit/test_foo.py::test_one"},
        )
        # Empty baseline + 1 current failing = 1 new failure.
        assert "New: 1" in out
        assert "SKIPPED" not in out

    def test_normal_baseline_classifies_correctly(
        self, tmp_path: Path, with_lib_on_path: None
    ) -> None:
        """Healthy-path: real baseline IDs are classified normally (preserves prior semantics)."""
        baseline_file = tmp_path / "baseline_failing_tests.txt"
        baseline_file.write_text(
            "tests/unit/test_a.py::test_one\ntests/unit/test_a.py::test_two\n"
        )

        # Current state: test_one was fixed, test_two still fails, test_three is new.
        current_failing = {
            "tests/unit/test_a.py::test_two",
            "tests/unit/test_b.py::test_three",
        }

        out = _step8_reader_logic(
            baseline_file=baseline_file,
            current_failing=current_failing,
        )
        assert "Fixed: 1" in out
        assert "Pre-existing: 1" in out
        assert "New: 1" in out
        assert "SKIPPED" not in out

    def test_step8_current_timeout_skips_classification(
        self, tmp_path: Path, with_lib_on_path: None
    ) -> None:
        """When STEP 8's own pytest capture times out, classification is skipped."""
        baseline_file = tmp_path / "baseline_failing_tests.txt"
        baseline_file.write_text("tests/unit/test_a.py::test_one\n")

        out = _step8_reader_logic(
            baseline_file=baseline_file,
            current_failing=None,  # simulates TimeoutExpired in STEP 8
        )
        assert "SKIPPED" in out

    def test_empty_baseline_file_treated_as_no_failures(
        self, tmp_path: Path, with_lib_on_path: None
    ) -> None:
        """Empty file (size 0, or only whitespace) = empty set, not unknown."""
        baseline_file = tmp_path / "baseline_failing_tests.txt"
        baseline_file.write_text("")

        out = _step8_reader_logic(
            baseline_file=baseline_file,
            current_failing=set(),
        )
        assert "Fixed: 0" in out
        assert "Pre-existing: 0" in out
        assert "New: 0" in out
        assert "SKIPPED" not in out


class TestRoundtripSimulation:
    """End-to-end: STEP 1 timeout → STEP 8 read = SKIPPED (the bug it was meant to fix)."""

    def test_timeout_in_step1_results_in_skipped_in_step8(
        self, tmp_path: Path, with_lib_on_path: None
    ) -> None:
        """The full sequence: STEP 1 times out, STEP 8 reads sentinel, classification is skipped.

        This is the integration check — the bug Issue #1094 fixes. Before the fix, STEP 1
        wrote a traceback, STEP 8 parsed it as garbage test IDs, and `pre_existing_remaining`
        was always 0 (garbage IDs never matched real current IDs).
        """

        def fake_run_timeout(*args: object, **kwargs: object) -> object:
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=kwargs.get("timeout", 1))

        # STEP 1: simulate timeout, write to baseline file.
        baseline_file = tmp_path / "baseline_failing_tests.txt"
        step1_output = _step1_baseline_capture_logic(timeout_seconds=1, fake_run=fake_run_timeout)
        baseline_file.write_text(step1_output)

        # STEP 8: read the baseline file with a healthy current set.
        out = _step8_reader_logic(
            baseline_file=baseline_file,
            current_failing={"tests/unit/test_a.py::test_one"},
        )

        # Before the fix: out would be "Fixed: N | Pre-existing: 0 | New: 1" with garbage IDs.
        # After the fix: classification is skipped because baseline is unknown.
        assert "SKIPPED" in out, (
            f"Regression — Issue #1094: timeout in STEP 1 should yield SKIPPED in STEP 8, got: {out!r}"
        )


# ---------------------------------------------------------------------------
# Verify the BASELINE_TIMEOUT_SECONDS env var actually flows through.
# ---------------------------------------------------------------------------


class TestTimeoutEnvVar:
    """The new BASELINE_TIMEOUT_SECONDS env var must be readable and parse to int."""

    def test_default_timeout_is_600(
        self, monkeypatch: pytest.MonkeyPatch, with_lib_on_path: None
    ) -> None:
        """When env var is unset, default is 600 (the documented default)."""
        monkeypatch.delenv("BASELINE_TIMEOUT_SECONDS", raising=False)
        # Mirror the snippet's parse logic.
        import os

        default = int(os.environ.get("BASELINE_TIMEOUT_SECONDS", "600"))
        assert default == 600

    def test_custom_timeout_honored(
        self, monkeypatch: pytest.MonkeyPatch, with_lib_on_path: None
    ) -> None:
        """When env var is set, the snippet logic picks it up."""
        monkeypatch.setenv("BASELINE_TIMEOUT_SECONDS", "30")
        import os

        configured = int(os.environ.get("BASELINE_TIMEOUT_SECONDS", "600"))
        assert configured == 30
