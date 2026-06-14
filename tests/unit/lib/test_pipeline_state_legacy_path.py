"""Tests for legacy sentinel path mechanics and _atomic_write_json (Issue #1206).

Verifies:
- Parent directory is created at mode 0o700.
- The resolver is idempotent.
- The filename constant matches the canonical name.
- ``_atomic_write_json`` writes files at mode 0o600.
- ``_atomic_write_json`` does not leak temp files on exception.

Issue: #1206
"""

import json
import os
import stat
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add lib directory to path (tests/unit/lib → plugins/autonomous-dev/lib)
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

# Import after sys.path mutation
from pipeline_state import (  # noqa: E402
    LEGACY_SENTINEL_FILENAME,
    _atomic_write_json,
    get_legacy_sentinel_path,
)


class TestLegacySentinelPath:
    """Tests for get_legacy_sentinel_path() directory handling."""

    def test_creates_parent_dir_with_mode_0o700(self, tmp_path):
        """Parent .claude/local/ directory is chmodded to 0o700."""
        sentinel = get_legacy_sentinel_path(repo_root=tmp_path)
        parent = sentinel.parent

        assert parent.exists(), f"Parent directory not created: {parent}"
        mode = stat.S_IMODE(parent.stat().st_mode)
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_idempotent(self, tmp_path):
        """Calling twice yields the same path with no error."""
        first = get_legacy_sentinel_path(repo_root=tmp_path)
        second = get_legacy_sentinel_path(repo_root=tmp_path)

        assert first == second
        # Both calls succeed even when directory already exists
        assert first.parent.exists()

    def test_filename_constant(self):
        """The filename is the canonical implement_pipeline_state.json."""
        assert LEGACY_SENTINEL_FILENAME == "implement_pipeline_state.json"

    def test_path_anchors_under_claude_local(self, tmp_path):
        """Resolved path is <root>/.claude/local/<filename>."""
        sentinel = get_legacy_sentinel_path(repo_root=tmp_path)

        expected = (tmp_path / ".claude" / "local" / LEGACY_SENTINEL_FILENAME).resolve()
        assert sentinel.resolve() == expected


class TestAtomicWriteJson:
    """Tests for _atomic_write_json() helper."""

    def test_atomic_write_mode_0o600(self, tmp_path):
        """The destination file is chmodded to 0o600 before replace."""
        target = tmp_path / "state.json"
        _atomic_write_json(target, {"key": "value"})

        assert target.exists()
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

        # Content survived the round-trip.
        assert json.loads(target.read_text()) == {"key": "value"}

    def test_atomic_write_no_partial_on_exception(self, tmp_path, monkeypatch):
        """When os.replace raises, the temp file is unlinked and no partial leaks."""
        target = tmp_path / "state.json"

        # Capture temp file paths created during the call
        created_tmps = []
        original_mkstemp = __import__("tempfile").mkstemp

        def tracking_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            created_tmps.append(path)
            return fd, path

        # Force os.replace to fail so the exception path is exercised.
        def failing_replace(_src, _dst):
            raise OSError("simulated rename failure")

        import pipeline_state as _ps
        monkeypatch.setattr(_ps.tempfile, "mkstemp", tracking_mkstemp)
        monkeypatch.setattr(_ps.os, "replace", failing_replace)

        with pytest.raises(OSError):
            _atomic_write_json(target, {"key": "value"})

        # Temp file MUST be cleaned up on failure
        assert created_tmps, "mkstemp was not called — test setup is wrong"
        for tmp in created_tmps:
            assert not os.path.exists(tmp), f"Temp file leaked: {tmp}"

        # The destination must not exist (write failed atomically)
        assert not target.exists(), "Destination file should not exist after failed write"

    def test_atomic_write_with_indent(self, tmp_path):
        """The indent keyword argument is honored."""
        target = tmp_path / "state.json"
        _atomic_write_json(target, {"a": 1}, indent=2)

        # Pretty-printed JSON contains newlines
        content = target.read_text()
        assert "\n" in content
        assert json.loads(content) == {"a": 1}
