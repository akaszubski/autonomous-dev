"""
Tests for plan-critic skip state in pipeline_completion_state.py.

Issue #878: plan-critic added to ordering gate with conditional bypass.
"""

import sys
from pathlib import Path

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_completion_state import (
    clear_session,
    get_plan_critic_skipped,
    get_plan_critic_skipped_plan_path,
    record_plan_critic_skipped,
)


@pytest.fixture(autouse=True)
def cleanup_session():
    """Clean up test session state before and after each test."""
    session_id = "test-plan-critic-878"
    clear_session(session_id)
    yield session_id
    clear_session(session_id)


class TestPlanCriticSkipState:
    """Tests for record_plan_critic_skipped / get_plan_critic_skipped."""

    def test_default_not_skipped(self, cleanup_session):
        """By default, plan-critic is not recorded as skipped."""
        assert get_plan_critic_skipped(cleanup_session) is False

    def test_record_and_read_skipped(self, cleanup_session):
        """After recording skip, get_plan_critic_skipped returns True."""
        record_plan_critic_skipped(cleanup_session)
        assert get_plan_critic_skipped(cleanup_session) is True

    def test_skip_with_issue_number(self, cleanup_session):
        """Skip state is per-issue: issue 42 skipped, issue 43 not."""
        record_plan_critic_skipped(cleanup_session, issue_number=42)
        assert get_plan_critic_skipped(cleanup_session, issue_number=42) is True
        assert get_plan_critic_skipped(cleanup_session, issue_number=43) is False

    def test_skip_default_issue_zero(self, cleanup_session):
        """Default issue_number=0 works independently from other issues."""
        record_plan_critic_skipped(cleanup_session, issue_number=0)
        assert get_plan_critic_skipped(cleanup_session, issue_number=0) is True
        assert get_plan_critic_skipped(cleanup_session, issue_number=1) is False

    def test_nonexistent_session_returns_false(self):
        """Unknown session returns False (not skipped)."""
        assert get_plan_critic_skipped("nonexistent-session-878") is False


class TestPlanCriticSkipPlanPath:
    """Tests for plan_path canonicalization (Issue #1218)."""

    def test_plan_path_default_none(self, cleanup_session):
        """When no plan_path is recorded, getter returns None."""
        assert get_plan_critic_skipped_plan_path(cleanup_session) is None

    def test_plan_path_skip_without_path_returns_none(self, cleanup_session):
        """Recording skip without plan_path leaves getter returning None."""
        record_plan_critic_skipped(cleanup_session, issue_number=1218)
        assert (
            get_plan_critic_skipped_plan_path(cleanup_session, issue_number=1218)
            is None
        )

    def test_plan_path_record_and_read(self, cleanup_session):
        """Recording skip with plan_path persists the path."""
        path = ".claude/plans/1218-fix.md"
        record_plan_critic_skipped(
            cleanup_session, issue_number=1218, plan_path=path
        )
        assert (
            get_plan_critic_skipped_plan_path(cleanup_session, issue_number=1218)
            == path
        )

    def test_plan_path_zero_fallback(self, cleanup_session):
        """plan_path written under issue_number is also readable under "0" scope."""
        path = ".claude/plans/1218-fix.md"
        record_plan_critic_skipped(
            cleanup_session, issue_number=1218, plan_path=path
        )
        # Read under issue=0 should fall back to "0" scope (dual-write).
        assert (
            get_plan_critic_skipped_plan_path(cleanup_session, issue_number=0)
            == path
        )

    def test_plan_path_nonexistent_session_returns_none(self):
        """Unknown session returns None."""
        assert (
            get_plan_critic_skipped_plan_path("nonexistent-session-1218") is None
        )


class TestPlanCriticActivityLogging:
    """Tests for Issue #1325: plan-critic skip activity logging."""

    def test_activity_log_created_on_skip(self, cleanup_session, tmp_path, monkeypatch):
        """When plan-critic is skipped, an activity log entry is written."""
        # Create a mock activity log directory
        activity_dir = tmp_path / ".claude" / "logs" / "activity"
        activity_dir.mkdir(parents=True)
        
        # Patch _find_activity_log_dir to return our test directory
        import pipeline_completion_state
        monkeypatch.setattr(
            pipeline_completion_state,
            "_find_activity_log_dir",
            lambda start_dir=None: activity_dir
        )
        
        # Record the skip with all parameters
        from datetime import datetime
        test_date = datetime.now().strftime("%Y-%m-%d")
        
        record_plan_critic_skipped(
            cleanup_session,
            issue_number=1325,
            plan_path="/test/plan.md",
            bypass_reason="test bypass",
            run_id="test-run-123"
        )
        
        # Check that the log file was created
        log_file = activity_dir / f"{test_date}.jsonl"
        assert log_file.exists(), f"Expected log file {log_file} to exist"
        
        # Read and verify the log entry
        import json
        with open(log_file, "r") as f:
            lines = f.readlines()
        
        assert len(lines) == 1, f"Expected 1 log entry, got {len(lines)}"
        entry = json.loads(lines[0])
        
        # Verify the entry has the expected fields
        assert entry["event_type"] == "plan_critic_skipped"
        assert entry["session_id"] == cleanup_session
        assert entry["issue_number"] == 1325
        assert entry["plan_path"] == "/test/plan.md"
        assert entry["bypass_reason"] == "test bypass"
        assert entry["run_id"] == "test-run-123"
        assert entry["source"] == "pipeline_completion_state"
        assert "timestamp" in entry
        
    def test_activity_log_default_bypass_reason(self, cleanup_session, tmp_path, monkeypatch):
        """When bypass_reason is None, defaults to 'pre-validated plan'."""
        # Create a mock activity log directory
        activity_dir = tmp_path / ".claude" / "logs" / "activity"
        activity_dir.mkdir(parents=True)
        
        # Patch _find_activity_log_dir to return our test directory
        import pipeline_completion_state
        monkeypatch.setattr(
            pipeline_completion_state,
            "_find_activity_log_dir",
            lambda start_dir=None: activity_dir
        )
        
        # Record the skip without bypass_reason
        from datetime import datetime
        test_date = datetime.now().strftime("%Y-%m-%d")
        
        record_plan_critic_skipped(cleanup_session)
        
        # Read and verify the log entry
        import json
        log_file = activity_dir / f"{test_date}.jsonl"
        with open(log_file, "r") as f:
            entry = json.loads(f.readline())
        
        assert entry["bypass_reason"] == "pre-validated plan"
        
    def test_activity_log_failure_does_not_block(self, cleanup_session, monkeypatch):
        """If activity logging fails, the function still completes successfully."""
        # Patch _find_activity_log_dir to return a non-writable directory
        import pipeline_completion_state
        monkeypatch.setattr(
            pipeline_completion_state,
            "_find_activity_log_dir",
            lambda start_dir=None: Path("/non/existent/dir")
        )
        
        # This should not raise an exception
        record_plan_critic_skipped(
            cleanup_session,
            issue_number=1325,
            plan_path="/test/plan.md",
            bypass_reason="test bypass"
        )
        
        # Verify the state was still written (the primary function)
        assert get_plan_critic_skipped(cleanup_session, issue_number=1325) is True
        
    def test_no_activity_log_when_dir_not_found(self, cleanup_session, monkeypatch):
        """When _find_activity_log_dir returns None, no log is written."""
        # Patch _find_activity_log_dir to return None
        import pipeline_completion_state
        monkeypatch.setattr(
            pipeline_completion_state,
            "_find_activity_log_dir",
            lambda start_dir=None: None
        )
        
        # This should complete without errors
        record_plan_critic_skipped(cleanup_session, issue_number=1325)
        
        # Verify the state was still written
        assert get_plan_critic_skipped(cleanup_session, issue_number=1325) is True
