"""Cross-repo sentinel isolation tests (Issue #1206).

Verifies that two simulated repos (each with their own ``.git`` marker) resolve
to distinct sentinel paths, and that writes to one do not clobber the other.

Issue: #1206
"""

import json
import sys
from pathlib import Path

import pytest

# Add lib directory to path (tests/integration → plugins/autonomous-dev/lib)
LIB_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_state import (  # noqa: E402
    _atomic_write_json,
    get_legacy_sentinel_path,
)
import path_utils  # noqa: E402


class TestCrossRepoSentinelIsolation:
    """Tests that concurrent /implement in different repos do not collide."""

    def test_two_repos_distinct_paths(self, tmp_path, monkeypatch):
        """Sentinel paths differ when chdir'd into two separate repo roots."""
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        for repo in (repo_a, repo_b):
            repo.mkdir()
            (repo / ".git").mkdir()

        # Resolve sentinel from repo_a
        monkeypatch.chdir(repo_a)
        path_utils.reset_project_root_cache()
        path_a = get_legacy_sentinel_path()

        # Resolve sentinel from repo_b
        monkeypatch.chdir(repo_b)
        path_utils.reset_project_root_cache()
        path_b = get_legacy_sentinel_path()

        assert path_a.resolve() != path_b.resolve(), (
            f"Cross-repo sentinels collided: {path_a} == {path_b}"
        )
        # Each path anchors at its own repo root
        assert repo_a.resolve() in path_a.resolve().parents
        assert repo_b.resolve() in path_b.resolve().parents

    def test_simultaneous_writes_no_clobber(self, tmp_path, monkeypatch):
        """Writing distinct values from each repo preserves both."""
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        for repo in (repo_a, repo_b):
            repo.mkdir()
            (repo / ".git").mkdir()

        # Resolve & write from repo_a
        monkeypatch.chdir(repo_a)
        path_utils.reset_project_root_cache()
        sentinel_a = get_legacy_sentinel_path()
        _atomic_write_json(sentinel_a, {"issue": "A", "run_id": "repo-a-run"})

        # Resolve & write from repo_b
        monkeypatch.chdir(repo_b)
        path_utils.reset_project_root_cache()
        sentinel_b = get_legacy_sentinel_path()
        _atomic_write_json(sentinel_b, {"issue": "B", "run_id": "repo-b-run"})

        # Reload both and assert each retained its own value
        loaded_a = json.loads(sentinel_a.read_text())
        loaded_b = json.loads(sentinel_b.read_text())

        assert loaded_a["issue"] == "A", f"repo_a sentinel was clobbered: {loaded_a}"
        assert loaded_b["issue"] == "B", f"repo_b sentinel was clobbered: {loaded_b}"
        assert loaded_a["run_id"] == "repo-a-run"
        assert loaded_b["run_id"] == "repo-b-run"
