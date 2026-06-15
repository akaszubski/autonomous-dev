"""Unit tests for plugins/autonomous-dev/lib/flaky_tests.py (Issue #983)."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from flaky_tests import load_known_flaky_tests, mark_test_flaky


def test_load_known_flaky_tests_missing_file_returns_empty_set(tmp_path):
    result = load_known_flaky_tests(tmp_path)
    assert result == set()


def test_load_known_flaky_tests_malformed_json_returns_empty_set(tmp_path):
    state_dir = tmp_path / ".claude" / "local"
    state_dir.mkdir(parents=True)
    (state_dir / "known_flaky_tests.json").write_text("not json {{{")
    result = load_known_flaky_tests(tmp_path)
    assert result == set()


def test_load_known_flaky_tests_valid_json_returns_set(tmp_path):
    state_dir = tmp_path / ".claude" / "local"
    state_dir.mkdir(parents=True)
    (state_dir / "known_flaky_tests.json").write_text(
        json.dumps(["tests/unit/test_a.py::test_x", "tests/unit/test_b.py::test_y"])
    )
    result = load_known_flaky_tests(tmp_path)
    assert result == {"tests/unit/test_a.py::test_x", "tests/unit/test_b.py::test_y"}


def test_load_known_flaky_tests_worktree_cwd(tmp_path, monkeypatch):
    """Issue #983 + round-3 plan-critic: explicit project_root works when Path.cwd() differs."""
    state_dir = tmp_path / ".claude" / "local"
    state_dir.mkdir(parents=True)
    (state_dir / "known_flaky_tests.json").write_text(json.dumps(["tests/foo::bar"]))
    # Change cwd to something else (simulating worktree CWD divergence).
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    # Pass explicit project_root; should still find the file at tmp_path.
    result = load_known_flaky_tests(tmp_path)
    assert result == {"tests/foo::bar"}


def test_mark_test_flaky_writes_atomically_and_is_idempotent(tmp_path):
    mark_test_flaky("tests/foo::bar", "reason", tmp_path)
    first = load_known_flaky_tests(tmp_path)
    assert first == {"tests/foo::bar"}
    mark_test_flaky("tests/foo::bar", "reason", tmp_path)  # idempotent
    second = load_known_flaky_tests(tmp_path)
    assert second == first  # unchanged
