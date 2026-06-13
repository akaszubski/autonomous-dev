"""Regression tests for baseline_guardrail.py (Issue #1139).

Validates that warn_if_baseline_missing:
1. Returns True and writes to stderr when sentinel exists but baseline_cmd absent.
2. Returns False when baseline_cmd is present.
3. Returns False when sentinel does not exist.
4. Writes the expected WARNING text to stderr.
5. NEVER raises regardless of bad inputs.
"""

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from baseline_guardrail import warn_if_baseline_missing, _WARNING_MSG  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_sentinel(path: Path, data: dict) -> None:
    """Write a minimal pipeline sentinel JSON file."""
    path.write_text(json.dumps(data))


def _make_sentinel_with_baseline(tmp_path: Path) -> Path:
    """Return a sentinel path that has a valid baseline_cmd recorded."""
    sentinel = tmp_path / "implement_pipeline_state.json"
    _write_sentinel(
        sentinel,
        {
            "session_start": "2026-06-14T10:00:00",
            "mode": "full",
            "run_id": "test-1139",
            "explicitly_invoked": True,
            "baseline_cmd": ["pytest", "tests/unit/", "--tb=no", "-q"],
            "baseline_count": 42,
        },
    )
    return sentinel


def _make_sentinel_without_baseline(tmp_path: Path) -> Path:
    """Return a sentinel path that has NO baseline_cmd recorded."""
    sentinel = tmp_path / "implement_pipeline_state.json"
    _write_sentinel(
        sentinel,
        {
            "session_start": "2026-06-14T10:00:00",
            "mode": "full",
            "run_id": "test-1139-no-baseline",
            "explicitly_invoked": True,
        },
    )
    return sentinel


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWarnIfBaselineMissing:
    """Regression suite for Issue #1139: baseline_guardrail.warn_if_baseline_missing."""

    def test_warn_if_baseline_missing_returns_true_when_baseline_absent_but_sentinel_exists(
        self, tmp_path: Path
    ) -> None:
        """Returns True when sentinel exists but baseline_cmd is absent.

        This is the primary detection case: coordinator skipped STEP 1 and the
        pipeline sentinel was created without recording baseline scope.
        Regression for Issue #1139.
        """
        sentinel = _make_sentinel_without_baseline(tmp_path)
        result = warn_if_baseline_missing(str(sentinel))
        assert result is True

    def test_warn_if_baseline_missing_returns_false_when_baseline_present(
        self, tmp_path: Path
    ) -> None:
        """Returns False when baseline_cmd is recorded in the sentinel.

        Normal case — STEP 1 ran correctly.  No warning should fire.
        Regression for Issue #1139.
        """
        sentinel = _make_sentinel_with_baseline(tmp_path)
        result = warn_if_baseline_missing(str(sentinel))
        assert result is False

    def test_warn_if_baseline_missing_returns_false_when_sentinel_missing(
        self, tmp_path: Path
    ) -> None:
        """Returns False when no sentinel file exists at the given path.

        Pipeline may not have started yet — guardrail is a no-op.
        Regression for Issue #1139.
        """
        non_existent = str(tmp_path / "does_not_exist.json")
        result = warn_if_baseline_missing(non_existent)
        assert result is False

    def test_warn_if_baseline_missing_writes_to_stderr_when_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Writes structured WARNING text to stderr when baseline is missing.

        The exact message format is specified in Issue #1139:
        '[BASELINE-MISSING-WARNING] <state_path> exists but no baseline_cmd recorded.'
        Regression for Issue #1139.
        """
        sentinel = _make_sentinel_without_baseline(tmp_path)
        warn_if_baseline_missing(str(sentinel))

        captured = capsys.readouterr()
        assert "[BASELINE-MISSING-WARNING]" in captured.err
        assert str(sentinel) in captured.err
        assert "baseline_cmd" in captured.err
        assert "git stash" in captured.err

    def test_warn_if_baseline_missing_never_raises(self, tmp_path: Path) -> None:
        """Never raises regardless of bad or unusual inputs.

        The guardrail is advisory only — it must not crash the coordinator.
        Regression for Issue #1139.
        """
        # Completely invalid path (not a valid JSON file)
        invalid_path = str(tmp_path / "not_a_json_file.json")
        (tmp_path / "not_a_json_file.json").write_text("THIS IS NOT JSON {{{{")
        try:
            result = warn_if_baseline_missing(invalid_path)
            # May return True or False — the important thing is it did not raise.
            assert isinstance(result, bool)
        except Exception as exc:
            pytest.fail(f"warn_if_baseline_missing raised unexpectedly: {exc}")

        # None-like string
        try:
            result = warn_if_baseline_missing("")
            assert isinstance(result, bool)
        except Exception as exc:
            pytest.fail(f"warn_if_baseline_missing raised on empty string: {exc}")

        # Sentinel with malformed baseline_cmd (not a list)
        bad_sentinel = tmp_path / "bad_state.json"
        _write_sentinel(
            bad_sentinel,
            {
                "baseline_cmd": "not-a-list",
                "baseline_count": 5,
            },
        )
        try:
            result = warn_if_baseline_missing(str(bad_sentinel))
            assert isinstance(result, bool)
        except Exception as exc:
            pytest.fail(
                f"warn_if_baseline_missing raised on malformed sentinel: {exc}"
            )
