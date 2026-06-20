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
