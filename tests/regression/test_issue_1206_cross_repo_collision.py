"""Regression test for Issue #1206: cross-repo sentinel collision.

Bug (session 92097971, 2026-06-11):
    A foreign /implement session running ``--fix 1288`` in a DIFFERENT repo
    overwrote this session's sentinel at the machine-global
    ``/tmp/implement_pipeline_state.json``. The ordering-gate resolver then
    resolved ``issue_number=1288`` from the foreign sentinel and blocked
    spec-validator dispatch in this session.

Root cause:
    The sentinel was hardcoded to ``/tmp/implement_pipeline_state.json`` — a
    machine-global location shared across every repo and every concurrent
    /implement session.

Fix:
    The sentinel is now resolved per-repo via
    ``get_legacy_sentinel_path()`` which anchors at
    ``<repo>/.claude/local/implement_pipeline_state.json``. Two sessions in
    different repos resolve to different paths by construction.

This regression test asserts:
    A foreign sentinel written under repo_foreign's path does NOT leak its
    ``issue_number`` into a resolver call made from repo_local's context.
"""

import json
import sys
from pathlib import Path

import pytest

# tests/regression/regression → repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_state import (  # noqa: E402
    _atomic_write_json,
    get_legacy_sentinel_path,
)
import path_utils  # noqa: E402


class TestIssue1206CrossRepoCollision:
    """Foreign /implement sessions must not leak state into other repos."""

    def test_foreign_session_does_not_leak_issue_number(self, tmp_path, monkeypatch):
        """A foreign sentinel under repo_foreign must not influence repo_local.

        Replays the session-92097971 collision scenario:
          1. A foreign session writes ``issue_number=1288`` to its sentinel.
          2. The local session resolves the sentinel from its OWN cwd.
          3. The local session's resolved path is NOT the foreign path.
          4. Reading the local sentinel returns local state, not foreign state.
        """
        # Two isolated fake repos
        repo_foreign = tmp_path / "repo_foreign"
        repo_local = tmp_path / "repo_local"
        for repo in (repo_foreign, repo_local):
            repo.mkdir()
            (repo / ".git").mkdir()

        # Foreign session writes its sentinel via explicit repo_root anchor.
        foreign_sentinel = get_legacy_sentinel_path(repo_root=repo_foreign)
        _atomic_write_json(
            foreign_sentinel,
            {"issue_number": 1288, "run_id": "foreign-1288"},
        )

        # Sanity: foreign write actually happened where we expect.
        assert foreign_sentinel.exists()
        assert json.loads(foreign_sentinel.read_text())["issue_number"] == 1288

        # Local session resolves sentinel from its own cwd.
        monkeypatch.chdir(repo_local)
        path_utils.reset_project_root_cache()
        local_sentinel = get_legacy_sentinel_path()

        # Foreign and local paths must differ.
        assert foreign_sentinel.resolve() != local_sentinel.resolve(), (
            "Foreign and local sentinels resolved to the same path — "
            "Issue #1206 regression!"
        )

        # Local sentinel must not exist yet (no local write happened).
        assert not local_sentinel.exists(), (
            f"Local sentinel was created at {local_sentinel} — foreign write "
            "leaked across repos."
        )

        # Write a local state and assert it does not contain the foreign issue.
        _atomic_write_json(
            local_sentinel,
            {"issue_number": 999, "run_id": "local-999"},
        )
        local_state = json.loads(local_sentinel.read_text())
        assert local_state["issue_number"] != 1288, (
            f"Local sentinel resolved foreign issue_number=1288: {local_state}"
        )
        assert local_state["issue_number"] == 999

        # Foreign sentinel is unchanged by the local write.
        foreign_state = json.loads(foreign_sentinel.read_text())
        assert foreign_state["issue_number"] == 1288
        assert foreign_state["run_id"] == "foreign-1288"

    def test_legacy_tmp_path_is_not_resolved_by_default(self, tmp_path, monkeypatch):
        """The hardcoded ``/tmp/implement_pipeline_state.json`` literal must
        no longer be the default resolution.

        This pins the fix: any future regression that re-introduces the
        machine-global literal will trip this test.
        """
        # Isolated fake repo
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        monkeypatch.chdir(repo)
        path_utils.reset_project_root_cache()

        resolved = get_legacy_sentinel_path()
        assert str(resolved) != "/tmp/implement_pipeline_state.json", (
            "Resolver still returns the legacy /tmp literal — fix reverted!"
        )
        assert ".claude/local/implement_pipeline_state.json" in str(resolved)
