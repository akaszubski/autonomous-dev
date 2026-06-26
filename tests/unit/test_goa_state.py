"""Tests for goa_state.py — Issue #1320."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure lib is importable
_LIB = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import goa_state


class TestGoaState:
    """Unit tests for GOA state management helpers."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Saving then loading a manifest returns the same dict."""
        data = {
            "version": 1,
            "thresholds": {"drop_rate_pct": 70},
        }
        manifest_path = tmp_path / ".claude/local/goa_manifest.json"

        with patch.object(goa_state, "get_manifest_path", return_value=manifest_path):
            goa_state.save_manifest(data)
            loaded = goa_state.load_manifest()

        assert loaded == data

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        """load_manifest returns None when the file does not exist."""
        missing = tmp_path / "nonexistent/goa_manifest.json"

        with patch.object(goa_state, "get_manifest_path", return_value=missing):
            result = goa_state.load_manifest()

        assert result is None

    def test_delete_manifest_removes_file(self, tmp_path: Path) -> None:
        """delete_manifest removes the manifest file."""
        manifest_path = tmp_path / "goa_manifest.json"
        manifest_path.write_text(json.dumps({"version": 1}), encoding="utf-8")

        with patch.object(goa_state, "get_manifest_path", return_value=manifest_path):
            goa_state.delete_manifest()

        assert not manifest_path.exists()

    def test_delete_manifest_noop_when_missing(self, tmp_path: Path) -> None:
        """delete_manifest is a no-op when the manifest does not exist."""
        missing = tmp_path / "nonexistent.json"

        with patch.object(goa_state, "get_manifest_path", return_value=missing):
            # Should not raise
            goa_state.delete_manifest()

    def test_atomic_write_json_backward_compat_alias_works(self, tmp_path: Path) -> None:
        """_atomic_write_json alias imported from pipeline_state must be callable."""
        _ps_lib = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
        if str(_ps_lib) not in sys.path:
            sys.path.insert(0, str(_ps_lib))
        from pipeline_state import _atomic_write_json, atomic_write_json

        # The alias should be the same object or at least callable
        assert callable(_atomic_write_json)
        assert callable(atomic_write_json)

        # Both should write the same data
        dest = tmp_path / "test_alias.json"
        atomic_write_json(dest, {"key": "value"})
        assert dest.exists()
        assert json.loads(dest.read_text()) == {"key": "value"}
