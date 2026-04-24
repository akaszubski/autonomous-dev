"""Tests for the 'unknown'-session merge TTL guard and remediation flag.

Covers Issue #904 (ROOT-CAUSE consolidation):
- Issue #875: stale 'unknown' state must not contaminate fresh pipelines.
- Issue #902: remediation-flagged completions must round-trip.
- Issue #738 / #777: in-flight 'unknown' merge (mtime < TTL) must still work.
"""

import os
import sys
import time
from pathlib import Path

import pytest

# Add lib to path — tests/unit/lib/test_foo.py → parents[3] is the repo root.
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_completion_state import (  # noqa: E402
    STALE_UNKNOWN_TTL_SECONDS,
    _state_file_path,
    clear_session,
    get_completed_agents,
    is_remediation_completion,
    record_agent_completion,
)


@pytest.fixture()
def session_id():
    """Unique session ID per test (avoid cross-test state bleed)."""
    return f"test_ttl_{os.getpid()}_{time.time_ns()}"


@pytest.fixture(autouse=True)
def _cleanup(session_id):
    """Ensure both the test session and the 'unknown' fallback are clean."""
    clear_session("unknown")
    yield
    clear_session(session_id)
    clear_session("unknown")


class TestUnknownSessionTTL:
    """Issue #875: stale 'unknown' state must not leak into fresh sessions."""

    def test_unknown_session_merged_when_recent(self, session_id):
        """Fresh 'unknown' state (mtime < TTL) is merged — preserves #738 behavior."""
        # Record a completion under 'unknown' (simulates coordinator writing
        # before CLAUDE_SESSION_ID was available).
        record_agent_completion("unknown", "planner")

        # Primary session has no record, but the merge should surface 'planner'.
        completed = get_completed_agents(session_id)
        assert "planner" in completed, (
            "Recent 'unknown' state must be merged (Issue #738 / #777)."
        )

    def test_unknown_session_skipped_when_stale(self, session_id):
        """Stale 'unknown' state (mtime > TTL) is NOT merged — fixes #875."""
        record_agent_completion("unknown", "planner")

        # Backdate the 'unknown' state file past the TTL.
        unknown_path = _state_file_path("unknown")
        assert unknown_path.exists(), "precondition: state file written"
        stale_time = time.time() - (STALE_UNKNOWN_TTL_SECONDS + 60)
        os.utime(unknown_path, (stale_time, stale_time))

        completed = get_completed_agents(session_id)
        assert "planner" not in completed, (
            "Stale 'unknown' state must NOT leak into fresh pipeline (Issue #875)."
        )

    def test_primary_session_completions_always_returned(self, session_id):
        """Primary session completions are returned regardless of 'unknown' TTL."""
        record_agent_completion(session_id, "implementer")

        # Backdate 'unknown' state (would normally exist from a prior run).
        record_agent_completion("unknown", "planner")
        unknown_path = _state_file_path("unknown")
        stale_time = time.time() - (STALE_UNKNOWN_TTL_SECONDS + 60)
        os.utime(unknown_path, (stale_time, stale_time))

        completed = get_completed_agents(session_id)
        assert "implementer" in completed
        assert "planner" not in completed, "stale unknown must not merge"


class TestRemediationFlagPersistence:
    """Issue #902: remediation-flagged completions must round-trip."""

    def test_is_remediation_flag_persisted(self, session_id):
        """Writing with is_remediation=True stores the flag; readable via helper."""
        record_agent_completion(
            session_id, "reviewer", is_remediation=True
        )

        # Completion still counts as successful (gate behavior unchanged).
        completed = get_completed_agents(session_id)
        assert "reviewer" in completed

        # Remediation flag retrievable.
        assert is_remediation_completion(session_id, "reviewer") is True

    def test_is_remediation_false_by_default_for_existing_callers(self, session_id):
        """Legacy zero-arg callers remain unflagged (backwards compat)."""
        record_agent_completion(session_id, "reviewer")

        completed = get_completed_agents(session_id)
        assert "reviewer" in completed
        assert is_remediation_completion(session_id, "reviewer") is False

    def test_failed_remediation_not_counted_as_completed(self, session_id):
        """Remediation with success=False must NOT appear in completed set."""
        record_agent_completion(
            session_id, "reviewer", success=False, is_remediation=True
        )
        completed = get_completed_agents(session_id)
        assert "reviewer" not in completed
