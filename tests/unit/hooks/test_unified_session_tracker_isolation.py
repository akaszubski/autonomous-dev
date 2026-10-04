#!/usr/bin/env python3
"""
Tests for unified_session_tracker.py session isolation (Issue #594).

Validates that check_pipeline_complete() and SessionTracker filter session
files by CLAUDE_SESSION_ID to prevent cross-session contamination when
multiple /implement pipelines run concurrently (e.g., batch worktrees).

Date: 2026-03-29
Issue: GitHub #594 - pipeline.json session mixing
Agent: implementer
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

import unified_session_tracker as ust


def _write_pipeline_json(
    session_dir: Path,
    filename: str,
    *,
    claude_session_id: str | None,
    completed_agents: list[str] | None = None,
) -> Path:
    """Write a minimal pipeline JSON file for testing."""
    f = session_dir / filename
    agents = []
    for agent in (completed_agents or []):
        agents.append({"agent": agent, "status": "completed"})
    data: dict = {
        "session_id": filename.replace("-pipeline.json", ""),
        "started": datetime.now().isoformat(),
        "github_issue": None,
        "agents": agents,
    }
    if claude_session_id is not None:
        data["claude_session_id"] = claude_session_id
    f.write_text(json.dumps(data))
    return f




class TestCheckPipelineCompleteFiltering:
    """Tests for check_pipeline_complete() session filtering (Issue #594)."""

    def test_check_pipeline_complete_filters_by_session(self, tmp_path, monkeypatch):
        """check_pipeline_complete returns True only for the matching session.

        Session A is fully complete; session B has no agents. Without filtering,
        check_pipeline_complete() would read session A's file (the latest) and
        incorrectly report session B as complete.
        """
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)

        today = datetime.now().strftime("%Y%m%d")

        # Session A: fully complete (older file)
        _write_pipeline_json(
            session_dir,
            f"{today}-060000-pipeline.json",
            claude_session_id="session-aaa",
            completed_agents=ust.EXPECTED_PIPELINE_AGENTS,
        )

        # Session B: no agents completed (newer file)
        _write_pipeline_json(
            session_dir,
            f"{today}-070000-pipeline.json",
            claude_session_id="session-bbb",
            completed_agents=[],
        )

        # Use monkeypatch to make Path("docs/sessions") resolve under tmp_path
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ust, "HAS_AGENT_TRACKER", True)

        # Session B should NOT be complete (its file has no agents)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-bbb")
        result_b = ust.check_pipeline_complete()
        assert not result_b, (
            "Session B has no completed agents; check_pipeline_complete must return False"
        )

        # Session A should be complete (all agents present)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "session-aaa")
        result_a = ust.check_pipeline_complete()
        assert result_a, (
            "Session A has all agents completed; check_pipeline_complete must return True"
        )

    def test_check_pipeline_complete_fallback_no_env(self, tmp_path, monkeypatch):
        """Without CLAUDE_SESSION_ID, latest file is used (backward compatibility)."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)

        today = datetime.now().strftime("%Y%m%d")

        # Older file: fully complete
        _write_pipeline_json(
            session_dir,
            f"{today}-060000-pipeline.json",
            claude_session_id="session-old",
            completed_agents=ust.EXPECTED_PIPELINE_AGENTS,
        )

        # Newer file: no agents (this is what would be picked without env var)
        _write_pipeline_json(
            session_dir,
            f"{today}-070000-pipeline.json",
            claude_session_id="session-new",
            completed_agents=[],
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ust, "HAS_AGENT_TRACKER", True)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        result = ust.check_pipeline_complete()

        # Latest file has no agents — not complete
        assert not result, (
            "Without CLAUDE_SESSION_ID, latest (empty) file should be used — not complete"
        )


class TestSessionTrackerIsolation:
    """Tests for SessionTracker session file isolation (Issue #594)."""

    def test_session_tracker_creates_file_with_session_id_in_name(self, tmp_path, monkeypatch):
        """SessionTracker includes CLAUDE_SESSION_ID in filename when set."""
        session_dir = tmp_path / "docs" / "sessions"

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "abc12345")

        tracker = ust.SessionTracker()

        assert ust.hashlib.sha256(b"abc12345").hexdigest() in tracker.session_file.name, (
            f"Session file name should include session ID, got: {tracker.session_file.name}"
        )

    def test_session_tracker_selects_matching_file(self, tmp_path, monkeypatch):
        """SessionTracker picks the file containing session ID in its name."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)

        today = datetime.now().strftime("%Y%m%d")
        # Create two files: one for session A (older), one for session B (newer)
        file_a = session_dir / f"{today}-060000-abc12345-session.md"
        file_b = session_dir / f"{today}-070000-xyz99999-session.md"
        file_a.write_text("# Session A\n**Claude Session ID**: abc12345\n")
        file_b.write_text("# Session B\n**Claude Session ID**: xyz99999\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "abc12345")

        tracker = ust.SessionTracker()

        assert tracker.session_file.resolve() == file_a.resolve(), (
            f"Should pick session A's file, got: {tracker.session_file}"
        )

    def test_session_tracker_fallback_to_latest_without_env(self, tmp_path, monkeypatch):
        """Without CLAUDE_SESSION_ID, SessionTracker uses the most recent file."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)

        today = datetime.now().strftime("%Y%m%d")
        file_old = session_dir / f"{today}-060000-aaa-session.md"
        file_new = session_dir / f"{today}-070000-bbb-session.md"
        file_old.write_text("# Old\n")
        file_new.write_text("# New\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        tracker = ust.SessionTracker()

        assert tracker.session_file.resolve() == file_new.resolve(), (
            f"Without env var, should pick the latest file, got: {tracker.session_file}"
        )
