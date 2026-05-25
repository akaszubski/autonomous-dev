#!/usr/bin/env python3
"""Unit tests for repo_detector.is_autonomous_dev_repo() marker detection.

Regression lock for Issue #1126: the marker filename in
``_detect_autonomous_dev`` used a bogus ``manifest.json`` path that never
existed on disk, so the function returned False inside the autonomous-dev
repo itself. That broke ``enforce_tdd.py`` and ``stop_quality_gate.py``
self-validation. The correct marker is
``plugins/autonomous-dev/.claude-plugin/marketplace.json``.

These tests exercise the REAL filesystem via ``tmp_path`` and
``monkeypatch.chdir`` — they intentionally do NOT mock ``Path.exists``,
because mocking it would hide the original bug.

Issue: #1126
Phase: Regression lock
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add plugins/autonomous-dev/lib to sys.path so we can import repo_detector.
# parents[0]=lib, [1]=unit, [2]=tests, [3]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from repo_detector import (  # noqa: E402  (sys.path mutation above is required)
    _reset_cache,
    is_autonomous_dev_repo,
)


# Marker content must include the literal string ``"name": "autonomous-dev"``
# so the content sanity check at repo_detector.py:184 (``if "autonomous-dev"
# in content``) passes. Using the same minimal shape as the real
# marketplace.json keeps the test honest.
_MARKER_CONTENT = '{\n  "name": "autonomous-dev",\n  "version": "test"\n}\n'


@pytest.fixture
def clean_cache():
    """Reset repo_detector module cache before and after each test.

    Without this, the first test that runs would cache its answer and
    subsequent tests would see stale state.
    """
    _reset_cache()
    yield
    _reset_cache()


def _make_autonomous_dev_repo(root: Path) -> Path:
    """Build a fake autonomous-dev repo layout under ``root``.

    Creates ``plugins/autonomous-dev/.claude-plugin/marketplace.json`` with
    valid marker content and a top-level ``.git`` directory so it looks
    like a real repo root.

    Returns the repo root path (== root).
    """
    plugin_dir = root / "plugins" / "autonomous-dev" / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "marketplace.json").write_text(_MARKER_CONTENT)
    (root / ".git").mkdir()
    return root


class TestIsAutonomousDevRepoMarker:
    """Regression lock for Issue #1126 marker filename bug."""

    def test_detects_via_marketplace_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_cache: None
    ) -> None:
        """When marketplace.json marker exists, return True."""
        repo = _make_autonomous_dev_repo(tmp_path)
        monkeypatch.chdir(repo)

        assert is_autonomous_dev_repo() is True

    def test_returns_false_when_marker_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_cache: None
    ) -> None:
        """When no marker exists anywhere in the tree, return False."""
        # Empty tmp_path — no plugins/, no .claude-plugin/, no marketplace.json
        monkeypatch.chdir(tmp_path)

        assert is_autonomous_dev_repo() is False

    def test_returns_false_when_legacy_manifest_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_cache: None
    ) -> None:
        """Regression for #1126: the bogus legacy ``manifest.json`` MUST NOT
        satisfy detection. Only the real ``.claude-plugin/marketplace.json``
        marker should count.

        Before the fix, this test would pass spuriously because the code
        looked at ``manifest.json``. After the fix, this layout must
        return False.
        """
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        # Write ONLY the legacy bogus path — no .claude-plugin/marketplace.json
        (plugin_dir / "manifest.json").write_text(_MARKER_CONTENT)
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        assert is_autonomous_dev_repo() is False, (
            "Legacy manifest.json must NOT satisfy detection — only the "
            "real .claude-plugin/marketplace.json marker counts. "
            "This locks the Issue #1126 fix."
        )

    def test_detects_when_running_inside_worktree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_cache: None
    ) -> None:
        """Worktree case: the marker lives at the worktree root and the
        worktree's ``.git`` is a file pointer (not a directory).

        is_autonomous_dev_repo() walks up to 10 levels looking for the
        marker, so a worktree subdir should still detect True.
        """
        # Build a "worktree" layout: marker reachable at tmp_path/, but
        # .git is a file pointer rather than a real .git directory.
        plugin_dir = tmp_path / "plugins" / "autonomous-dev" / ".claude-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "marketplace.json").write_text(_MARKER_CONTENT)
        (tmp_path / ".git").write_text(
            "gitdir: /tmp/fake-main-repo/.git/worktrees/batch-test\n"
        )

        # chdir into the worktree root itself
        monkeypatch.chdir(tmp_path)

        assert is_autonomous_dev_repo() is True

    def test_detects_when_running_from_nested_subdir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_cache: None
    ) -> None:
        """When invoked from a deeply nested subdir, detection still walks
        up the tree and finds the marker."""
        repo = _make_autonomous_dev_repo(tmp_path)
        nested = repo / "src" / "subpackage" / "deep"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        assert is_autonomous_dev_repo() is True
