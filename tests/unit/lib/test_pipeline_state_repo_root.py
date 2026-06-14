"""Tests for repo-root resolution in get_legacy_sentinel_path (Issue #1206).

Verifies that the per-repo sentinel path resolver:
- Falls back to ``Path.cwd()`` when no marker file is found.
- Uses ``find_project_root()`` when a ``.git`` or ``.claude`` marker is present.
- Honors an explicit ``repo_root`` argument.

Issue: #1206
"""

import sys
from pathlib import Path

import pytest

# Add lib directory to path (tests/unit/lib → plugins/autonomous-dev/lib)
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

# Import after sys.path mutation
from pipeline_state import LEGACY_SENTINEL_FILENAME, get_legacy_sentinel_path  # noqa: E402
import path_utils  # noqa: E402


class TestRepoRootResolution:
    """Tests for the three-tier fallback in get_legacy_sentinel_path()."""

    def test_wrapper_falls_back_to_cwd_when_no_markers(self, tmp_path, monkeypatch):
        """When no .git or .claude marker is found in the walk, fall back to cwd."""
        # Create an isolated directory with NO marker files
        isolated = tmp_path / "no_markers"
        isolated.mkdir()
        monkeypatch.chdir(isolated)

        # Reset the find_project_root cache so the walk re-runs from new cwd
        path_utils.reset_project_root_cache()

        sentinel = get_legacy_sentinel_path()

        # Sentinel is <cwd>/.claude/local/implement_pipeline_state.json
        # Note: if a parent of tmp_path happens to have .git/.claude (which is
        # possible on dev machines), find_project_root may walk upward. We
        # validate by computing the EXPECTED resolution chain manually.
        try:
            from path_utils import find_project_root as _fpr
            expected_root = _fpr()
        except FileNotFoundError:
            expected_root = Path.cwd().resolve()

        assert sentinel == expected_root / ".claude" / "local" / LEGACY_SENTINEL_FILENAME

    def test_wrapper_uses_find_project_root_when_marker_present(self, tmp_path, monkeypatch):
        """When a .git marker exists, sentinel anchors at that root."""
        # Create a fake repo with .git marker
        repo = tmp_path / "fake_repo"
        repo.mkdir()
        (repo / ".git").mkdir()

        # Nest a subdirectory and chdir into it
        nested = repo / "src" / "deep" / "nested"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        # Reset cache so walk re-runs
        path_utils.reset_project_root_cache()

        sentinel = get_legacy_sentinel_path()

        # Sentinel must anchor at the repo root, NOT at the nested cwd.
        # Use resolve() because tmp_path on macOS may have /private prefix.
        expected = (repo / ".claude" / "local" / LEGACY_SENTINEL_FILENAME).resolve()
        assert sentinel.resolve() == expected

    def test_wrapper_accepts_explicit_repo_root(self, tmp_path):
        """Passing repo_root= bypasses the walk."""
        explicit = tmp_path / "explicit_root"
        explicit.mkdir()

        sentinel = get_legacy_sentinel_path(repo_root=explicit)

        expected = (explicit / ".claude" / "local" / LEGACY_SENTINEL_FILENAME).resolve()
        assert sentinel.resolve() == expected
