"""
Tests for _gc_stale_states() in pipeline_completion_state.py.

Verifies that stale state files, sentinel files, and orphaned lockfiles are
removed while fresh files are preserved.

Issues: #1041 #1048
"""

import glob
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_completion_state import _gc_stale_states


class TestGCStaleStateFiles:
    """Tests for _gc_stale_states() — stale completion state file removal."""

    def _make_file(self, tmp_path: Path, name: str, age_seconds: float) -> Path:
        """Create a file in tmp_path and backdate its mtime by age_seconds."""
        p = tmp_path / name
        p.write_text("{}")
        mtime = time.time() - age_seconds
        os.utime(p, (mtime, mtime))
        return p

    def _patch_glob(self, tmp_path: Path):
        """Return a context manager that redirects glob patterns to tmp_path.

        pipeline_completion_state imports glob at module level, so we patch
        the module-level attribute ``pipeline_completion_state.glob.glob``.
        """
        original_glob = glob.glob

        def fake_glob(pattern: str) -> list:
            # Replace /tmp/ prefix with tmp_path/ so tests only touch tmp_path
            if pattern.startswith("/tmp/"):
                local_pattern = str(tmp_path / pattern[len("/tmp/"):])
                return original_glob(local_pattern)
            return original_glob(pattern)

        # The module imports `glob` at the top level; the function calls
        # glob.glob(pattern).  We patch the `glob` attribute on the glob
        # *module* that pipeline_completion_state holds a reference to.
        import pipeline_completion_state as _pcs

        return patch.object(_pcs.glob, "glob", side_effect=fake_glob)

    # ------------------------------------------------------------------
    # test_gc_removes_stale_state_files
    # ------------------------------------------------------------------
    def test_gc_removes_stale_state_files(self, tmp_path: Path) -> None:
        """Old completion state files are removed."""
        stale = self._make_file(
            tmp_path, "pipeline_agent_completions_abc12345.json", age_seconds=8000
        )
        assert stale.exists()

        with self._patch_glob(tmp_path):
            result = _gc_stale_states(max_age_seconds=7200)

        assert not stale.exists(), "Stale state file should have been removed"
        assert result["state_files_removed"] == 1
        assert result["errors"] == []

    # ------------------------------------------------------------------
    # test_gc_preserves_fresh_state_files
    # ------------------------------------------------------------------
    def test_gc_preserves_fresh_state_files(self, tmp_path: Path) -> None:
        """Fresh completion state files are NOT removed."""
        fresh = self._make_file(
            tmp_path, "pipeline_agent_completions_fresh001.json", age_seconds=60
        )
        assert fresh.exists()

        with self._patch_glob(tmp_path):
            result = _gc_stale_states(max_age_seconds=7200)

        assert fresh.exists(), "Fresh state file should NOT have been removed"
        assert result["state_files_removed"] == 0

    # ------------------------------------------------------------------
    # test_gc_removes_orphaned_lockfiles
    # ------------------------------------------------------------------
    def test_gc_removes_orphaned_lockfiles(self, tmp_path: Path) -> None:
        """Old orphaned lockfiles are removed."""
        lock = self._make_file(tmp_path, "pipeline_abc12345.lock", age_seconds=9000)
        assert lock.exists()

        with self._patch_glob(tmp_path):
            result = _gc_stale_states(max_age_seconds=7200)

        assert not lock.exists(), "Stale lockfile should have been removed"
        assert result["lockfiles_removed"] == 1
        assert result["errors"] == []

    # ------------------------------------------------------------------
    # test_gc_handles_missing_dir_gracefully (no matching files)
    # ------------------------------------------------------------------
    def test_gc_handles_missing_dir_gracefully(self, tmp_path: Path) -> None:
        """GC works cleanly when no files match any pattern."""
        with self._patch_glob(tmp_path):
            result = _gc_stale_states(max_age_seconds=7200)

        assert result["state_files_removed"] == 0
        assert result["sentinels_removed"] == 0
        assert result["lockfiles_removed"] == 0
        assert result["errors"] == []

    # ------------------------------------------------------------------
    # test_gc_returns_correct_counts
    # ------------------------------------------------------------------
    def test_gc_returns_correct_counts(self, tmp_path: Path) -> None:
        """Result dict has correct keys and counts for a mixed scenario."""
        self._make_file(
            tmp_path, "pipeline_agent_completions_aaa00001.json", age_seconds=9000
        )
        self._make_file(
            tmp_path, "pipeline_agent_completions_bbb00002.json", age_seconds=9000
        )
        self._make_file(
            tmp_path, "implement_pipeline_ccc00003.json", age_seconds=9000
        )
        self._make_file(tmp_path, "pipeline_ddd00004.lock", age_seconds=9000)
        # One fresh file that should NOT be removed
        self._make_file(
            tmp_path, "pipeline_agent_completions_fresh9999.json", age_seconds=100
        )

        with self._patch_glob(tmp_path):
            result = _gc_stale_states(max_age_seconds=7200)

        assert result["state_files_removed"] == 2
        assert result["sentinels_removed"] == 1
        assert result["lockfiles_removed"] == 1
        assert result["errors"] == []

    # ------------------------------------------------------------------
    # test_gc_max_age_seconds_param
    # ------------------------------------------------------------------
    def test_gc_max_age_seconds_param(self, tmp_path: Path) -> None:
        """Custom max_age_seconds controls the cutoff boundary."""
        # File is 500 seconds old — stale at 300s TTL, fresh at 7200s TTL
        borderline = self._make_file(
            tmp_path,
            "pipeline_agent_completions_border01.json",
            age_seconds=500,
        )

        with self._patch_glob(tmp_path):
            result_fresh = _gc_stale_states(max_age_seconds=7200)

        assert borderline.exists(), "Should NOT be removed with 7200s TTL"
        assert result_fresh["state_files_removed"] == 0

        # Now set TTL to 300s — same file is now stale
        with self._patch_glob(tmp_path):
            result_stale = _gc_stale_states(max_age_seconds=300)

        assert not borderline.exists(), "Should be removed with 300s TTL"
        assert result_stale["state_files_removed"] == 1

    # ------------------------------------------------------------------
    # test_gc_skips_files_in_use (current-mtime files)
    # ------------------------------------------------------------------
    def test_gc_skips_files_in_use(self, tmp_path: Path) -> None:
        """A file with current mtime is never removed."""
        current = self._make_file(
            tmp_path, "pipeline_agent_completions_current.json", age_seconds=0
        )

        with self._patch_glob(tmp_path):
            result = _gc_stale_states(max_age_seconds=7200)

        assert current.exists(), "Current file should NOT be removed"
        assert result["state_files_removed"] == 0

    # ------------------------------------------------------------------
    # test_gc_handles_permission_errors
    # ------------------------------------------------------------------
    def test_gc_handles_permission_errors(self, tmp_path: Path) -> None:
        """OSError during unlink is captured in errors list, not raised."""
        stale = self._make_file(
            tmp_path, "pipeline_agent_completions_perm_err.json", age_seconds=9000
        )

        original_unlink = os.unlink
        unlink_calls: list = []

        def failing_unlink(path: str) -> None:
            unlink_calls.append(path)
            raise OSError(13, "Permission denied", path)

        with self._patch_glob(tmp_path):
            with patch("pipeline_completion_state.os.unlink", side_effect=failing_unlink):
                result = _gc_stale_states(max_age_seconds=7200)

        # File should still exist (we faked the unlink)
        assert stale.exists()
        assert result["state_files_removed"] == 0
        assert len(result["errors"]) == 1
        assert "Permission denied" in result["errors"][0]

    # ------------------------------------------------------------------
    # test_gc_removes_stale_sentinel_files
    # ------------------------------------------------------------------
    def test_gc_removes_stale_sentinel_files(self, tmp_path: Path) -> None:
        """Per-run sentinel files (/tmp/implement_pipeline_*.json) are removed when stale."""
        sentinel = self._make_file(
            tmp_path, "implement_pipeline_abc123.json", age_seconds=8000
        )
        assert sentinel.exists()

        with self._patch_glob(tmp_path):
            result = _gc_stale_states(max_age_seconds=7200)

        assert not sentinel.exists(), "Stale sentinel file should have been removed"
        assert result["sentinels_removed"] == 1

    # ------------------------------------------------------------------
    # test_gc_result_dict_structure
    # ------------------------------------------------------------------
    def test_gc_result_dict_structure(self, tmp_path: Path) -> None:
        """Result dict always contains the expected keys with correct types."""
        with self._patch_glob(tmp_path):
            result = _gc_stale_states()

        assert "state_files_removed" in result
        assert "sentinels_removed" in result
        assert "lockfiles_removed" in result
        assert "errors" in result
        assert isinstance(result["state_files_removed"], int)
        assert isinstance(result["sentinels_removed"], int)
        assert isinstance(result["lockfiles_removed"], int)
        assert isinstance(result["errors"], list)
