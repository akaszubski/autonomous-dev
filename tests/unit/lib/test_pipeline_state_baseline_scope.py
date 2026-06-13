"""Tests for baseline scope helpers in pipeline_state.py (Issue #990).

Regression test: coordinator and implementer used different test scopes at
STEP 5 / STEP 8, causing 188 false "new-failure" reports in the #972 run.

The fix: record the exact pytest invocation used for baseline capture into
the pipeline sentinel at STEP 1, then require the implementer to read it
back (get_baseline_scope) and use the SAME scope — not a broader one.

Test cases:
1. test_record_baseline_scope_persists_cmd_and_count
   — write to a fresh sentinel, read back via get_baseline_scope, assert
   dict has expected fields.
2. test_get_baseline_scope_returns_none_when_missing
   — call on a sentinel that has no baseline_cmd field.
3. test_record_baseline_scope_merges_with_existing_state
   — sentinel has other fields like {session_id, alignment_passed}; baseline_cmd
   is added without disturbing them.
4. test_record_baseline_scope_returns_false_on_io_error
   — point at a non-writable path and assert False, no raise.
5. test_baseline_cmd_stored_as_list_for_safety
   — verify the persisted JSON keeps the list form (no shell-escape
   concatenation).

Date: 2026-06-14
Issue: #990
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

# Add lib directory to path (tests/unit/lib → plugins/autonomous-dev/lib)
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from bugfix_detector import get_test_count, get_test_count_for_dirs  # noqa: E402
from pipeline_state import (  # noqa: E402
    CANONICAL_BASELINE_CMD,
    get_baseline_scope,
    record_baseline_scope,
)

SAMPLE_CMD: list[str] = ["pytest", "tests/unit", "tests/integration", "-q", "--tb=no"]
SAMPLE_COUNT: int = 1625


class TestRecordBaselineScopePersistsCmdAndCount:
    """record_baseline_scope -> get_baseline_scope roundtrip returns expected fields."""

    def test_record_baseline_scope_persists_cmd_and_count(self, tmp_path: Path) -> None:
        """Write to a fresh sentinel, read back via get_baseline_scope."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"mode": "full", "run_id": "abc123"}))

        result = record_baseline_scope(str(state_file), SAMPLE_CMD, SAMPLE_COUNT)
        assert result is True

        scope = get_baseline_scope(str(state_file))
        assert scope is not None
        assert scope["baseline_cmd"] == SAMPLE_CMD
        assert scope["baseline_count"] == SAMPLE_COUNT

    def test_roundtrip_with_canonical_cmd(self, tmp_path: Path) -> None:
        """The CANONICAL_BASELINE_CMD constant roundtrips correctly."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"mode": "fix"}))

        record_baseline_scope(str(state_file), CANONICAL_BASELINE_CMD, 42)
        scope = get_baseline_scope(str(state_file))

        assert scope is not None
        assert scope["baseline_cmd"] == CANONICAL_BASELINE_CMD
        assert scope["baseline_count"] == 42


class TestGetBaselineScopeReturnsNoneWhenMissing:
    """get_baseline_scope returns None when baseline_cmd is absent or malformed."""

    def test_get_baseline_scope_returns_none_when_missing(self, tmp_path: Path) -> None:
        """Sentinel with no baseline_cmd returns None."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"mode": "full", "session_id": "xyz"}))

        assert get_baseline_scope(str(state_file)) is None

    def test_get_baseline_scope_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Non-existent file returns None."""
        missing = tmp_path / "does_not_exist.json"
        assert get_baseline_scope(str(missing)) is None

    def test_get_baseline_scope_returns_none_when_cmd_not_list(self, tmp_path: Path) -> None:
        """baseline_cmd must be a list; string value returns None."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"baseline_cmd": "pytest tests/unit -q", "baseline_count": 10}))
        assert get_baseline_scope(str(state_file)) is None

    def test_get_baseline_scope_returns_none_when_cmd_empty_list(self, tmp_path: Path) -> None:
        """baseline_cmd empty list is invalid."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"baseline_cmd": [], "baseline_count": 10}))
        assert get_baseline_scope(str(state_file)) is None

    def test_get_baseline_scope_returns_none_when_count_missing(self, tmp_path: Path) -> None:
        """baseline_count absent returns None."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"baseline_cmd": SAMPLE_CMD}))
        assert get_baseline_scope(str(state_file)) is None

    def test_get_baseline_scope_returns_none_when_count_not_int(self, tmp_path: Path) -> None:
        """baseline_count must be an integer; string value returns None."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"baseline_cmd": SAMPLE_CMD, "baseline_count": "1625"}))
        assert get_baseline_scope(str(state_file)) is None

    def test_get_baseline_scope_returns_none_for_malformed_json(self, tmp_path: Path) -> None:
        """Malformed JSON in sentinel returns None."""
        state_file = tmp_path / "state.json"
        state_file.write_text("{not valid json")
        assert get_baseline_scope(str(state_file)) is None


class TestRecordBaselineScopeMergesWithExistingState:
    """record_baseline_scope merges with existing sentinel fields without clobber."""

    def test_record_baseline_scope_merges_with_existing_state(self, tmp_path: Path) -> None:
        """Sentinel with other fields like {session_id, alignment_passed} is preserved."""
        state_file = tmp_path / "state.json"
        original = {
            "session_id": "sess-001",
            "alignment_passed": True,
            "mode": "full",
            "run_id": "deadbeef",
        }
        state_file.write_text(json.dumps(original))

        result = record_baseline_scope(str(state_file), SAMPLE_CMD, SAMPLE_COUNT)
        assert result is True

        # All original fields must survive
        written = json.loads(state_file.read_text())
        assert written["session_id"] == "sess-001"
        assert written["alignment_passed"] is True
        assert written["mode"] == "full"
        assert written["run_id"] == "deadbeef"
        # New fields are present
        assert written["baseline_cmd"] == SAMPLE_CMD
        assert written["baseline_count"] == SAMPLE_COUNT

    def test_record_baseline_scope_overwrites_existing_baseline(self, tmp_path: Path) -> None:
        """Re-baselining within a session overwrites the old baseline_cmd/count."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"baseline_cmd": ["pytest", "tests/old"], "baseline_count": 500}))

        new_cmd = ["pytest", "tests/unit", "tests/integration", "-q", "--tb=no"]
        record_baseline_scope(str(state_file), new_cmd, 1700)

        scope = get_baseline_scope(str(state_file))
        assert scope is not None
        assert scope["baseline_cmd"] == new_cmd
        assert scope["baseline_count"] == 1700


class TestRecordBaselineScopeReturnsFalseOnIoError:
    """record_baseline_scope returns False (no raise) for unwritable/missing paths."""

    def test_record_baseline_scope_returns_false_on_io_error(self, tmp_path: Path) -> None:
        """Point at a non-writable directory; assert False, no exception."""
        ro_dir = tmp_path / "readonly"
        ro_dir.mkdir()
        state_file = ro_dir / "state.json"
        state_file.write_text(json.dumps({"mode": "full"}))
        # Make the directory read-only so mkstemp inside it fails
        ro_dir.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
        try:
            result = record_baseline_scope(str(state_file), SAMPLE_CMD, SAMPLE_COUNT)
            assert result is False
        finally:
            # Restore permissions so tmp_path cleanup works
            ro_dir.chmod(stat.S_IRWXU)

    def test_record_baseline_scope_returns_false_for_missing_file(self, tmp_path: Path) -> None:
        """Sentinel does not exist; returns False without raising."""
        missing = tmp_path / "does_not_exist.json"
        result = record_baseline_scope(str(missing), SAMPLE_CMD, SAMPLE_COUNT)
        assert result is False

    def test_record_baseline_scope_returns_false_for_invalid_json(self, tmp_path: Path) -> None:
        """Malformed sentinel returns False without raising."""
        state_file = tmp_path / "state.json"
        state_file.write_text("{not valid json")
        result = record_baseline_scope(str(state_file), SAMPLE_CMD, SAMPLE_COUNT)
        assert result is False


class TestBaselineCmdStoredAsListForSafety:
    """baseline_cmd is persisted as a JSON list, never as a shell-escaped string."""

    def test_baseline_cmd_stored_as_list_for_safety(self, tmp_path: Path) -> None:
        """Persisted JSON keeps list form — no shell-escape concatenation."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"mode": "full"}))

        record_baseline_scope(str(state_file), SAMPLE_CMD, SAMPLE_COUNT)

        raw = json.loads(state_file.read_text())
        # Must be a JSON array (list), not a string
        assert isinstance(raw["baseline_cmd"], list), (
            f"baseline_cmd must be stored as JSON array, got {type(raw['baseline_cmd'])}"
        )
        # Each element must be a string
        for element in raw["baseline_cmd"]:
            assert isinstance(element, str), (
                f"Each baseline_cmd element must be str, got {type(element)!r}"
            )

    def test_baseline_cmd_elements_are_individual_tokens(self, tmp_path: Path) -> None:
        """List elements match individual pytest arguments, not a joined shell string."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({}))
        cmd = ["pytest", "tests/unit", "tests/integration", "-q", "--tb=no"]
        record_baseline_scope(str(state_file), cmd, 100)

        raw = json.loads(state_file.read_text())
        # The joined string must NOT appear as a single element
        assert "pytest tests/unit" not in raw["baseline_cmd"], (
            "baseline_cmd must not be a shell-joined string stored in a single list element"
        )
        assert raw["baseline_cmd"][0] == "pytest"
        assert raw["baseline_cmd"][1] == "tests/unit"


class TestCanonicalBaselineCmdConstant:
    """CANONICAL_BASELINE_CMD constant has the expected shape."""

    def test_canonical_baseline_cmd_is_list(self) -> None:
        """CANONICAL_BASELINE_CMD is a list of strings."""
        assert isinstance(CANONICAL_BASELINE_CMD, list)
        assert len(CANONICAL_BASELINE_CMD) > 0
        for item in CANONICAL_BASELINE_CMD:
            assert isinstance(item, str)

    def test_canonical_baseline_cmd_starts_with_pytest(self) -> None:
        """CANONICAL_BASELINE_CMD starts with 'pytest'."""
        assert CANONICAL_BASELINE_CMD[0] == "pytest"

    def test_canonical_baseline_cmd_targets_unit_and_integration(self) -> None:
        """CANONICAL_BASELINE_CMD targets tests/unit and tests/integration."""
        cmd_str = " ".join(CANONICAL_BASELINE_CMD)
        assert "tests/unit" in cmd_str, "Canonical cmd must include tests/unit"
        assert "tests/integration" in cmd_str, "Canonical cmd must include tests/integration"


class TestGetTestCountForDirs:
    """Regression tests for get_test_count_for_dirs — Issue #990 scope mismatch fix.

    Verifies that get_test_count_for_dirs counts only the specified dirs,
    not the full tests/ tree, so that baseline_count matches CANONICAL_BASELINE_CMD scope.
    """

    def test_get_test_count_for_dirs_only_counts_specified_dirs(self, tmp_path: Path) -> None:
        """Only count test functions in specified dirs; exclude other test dirs."""
        # Create tests/unit/X with one test function
        unit_dir = tmp_path / "tests" / "unit"
        unit_dir.mkdir(parents=True)
        (unit_dir / "test_unit_x.py").write_text("def test_unit_only():\n    pass\n")

        # Create tests/regression/Y with one test function (NOT in the specified dirs)
        regression_dir = tmp_path / "tests" / "regression"
        regression_dir.mkdir(parents=True)
        (regression_dir / "test_regression_y.py").write_text("def test_regression_only():\n    pass\n")

        # Only "tests/unit" is specified — should count 1, not 2
        result = get_test_count_for_dirs(["tests/unit"], tmp_path)
        assert result == 1, (
            f"Expected 1 (only tests/unit), got {result}. "
            "get_test_count_for_dirs must not scan tests/regression."
        )

    def test_get_test_count_for_dirs_handles_missing_dirs(self, tmp_path: Path) -> None:
        """Pass non-existent dir; must return 0 without raising."""
        result = get_test_count_for_dirs(["tests/nonexistent"], tmp_path)
        assert result == 0, f"Expected 0 for missing dir, got {result}"

    def test_get_test_count_for_dirs_handles_missing_dirs_no_raise(self, tmp_path: Path) -> None:
        """Multiple missing dirs must return 0, not raise."""
        # Should never raise regardless of path existence
        try:
            result = get_test_count_for_dirs(["tests/does_not_exist", "tests/also_missing"], tmp_path)
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(
                f"get_test_count_for_dirs raised unexpectedly: {exc!r}"
            ) from exc
        assert result == 0

    def test_get_test_count_for_dirs_matches_canonical_scope(self) -> None:
        """Scoped count for canonical dirs is <= full tests/ count.

        Verifies that get_test_count_for_dirs(["tests/unit", "tests/integration"])
        is a strict subset of (or equal to) the full get_test_count() count.
        This is the core invariant that prevents the #990 scope mismatch.
        """
        repo_root = Path(__file__).resolve().parents[3]
        scoped = get_test_count_for_dirs(["tests/unit", "tests/integration"], repo_root)
        full = get_test_count(repo_root)
        assert scoped <= full, (
            f"Scoped count ({scoped}) must be <= full count ({full}). "
            "If this fails the scope mapping is broken."
        )
