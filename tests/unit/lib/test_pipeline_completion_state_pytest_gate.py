"""
Tests for pytest-gate virtual agent in pipeline_completion_state.py.

Issue #838: Pipeline step ordering enforcement — pytest gate.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_completion_state import (
    clear_session,
    get_completed_agents,
    get_pytest_gate_passed,
    record_agent_completion,
    record_pytest_gate_passed,
)


@pytest.fixture()
def session_id():
    """Generate a unique session ID and clean up after test."""
    sid = f"test-pytest-gate-{uuid.uuid4().hex[:8]}"
    yield sid
    clear_session(sid)


class TestRecordPytestGate:
    """Tests for record_pytest_gate_passed and get_pytest_gate_passed."""

    def test_record_pytest_gate_creates_completion(self, session_id: str):
        """Recording pytest gate creates a 'pytest-gate' completion entry."""
        record_pytest_gate_passed(session_id)
        completed = get_completed_agents(session_id)
        assert "pytest-gate" in completed

    def test_get_pytest_gate_false_when_not_recorded(self, session_id: str):
        """Default returns False when nothing has been recorded."""
        assert get_pytest_gate_passed(session_id) is False

    def test_get_pytest_gate_true_after_recording(self, session_id: str):
        """Returns True after recording pytest gate as passed."""
        record_pytest_gate_passed(session_id)
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_with_issue_number(self, session_id: str):
        """Works with non-zero issue numbers."""
        record_pytest_gate_passed(session_id, issue_number=42)
        assert get_pytest_gate_passed(session_id, issue_number=42) is True
        # Different issue number should not have the gate
        assert get_pytest_gate_passed(session_id, issue_number=99) is False

    def test_pytest_gate_skip_env_var(self, session_id: str, monkeypatch: pytest.MonkeyPatch):
        """SKIP_PYTEST_GATE=1 causes get_pytest_gate_passed to return True."""
        monkeypatch.setenv("SKIP_PYTEST_GATE", "1")
        # Not recorded, but env var makes it return True
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_skip_env_var_true(self, session_id: str, monkeypatch: pytest.MonkeyPatch):
        """SKIP_PYTEST_GATE=true also works."""
        monkeypatch.setenv("SKIP_PYTEST_GATE", "true")
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_skip_env_var_yes(self, session_id: str, monkeypatch: pytest.MonkeyPatch):
        """SKIP_PYTEST_GATE=yes also works."""
        monkeypatch.setenv("SKIP_PYTEST_GATE", "YES")
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_unknown_session_fallback(self):
        """Merge from 'unknown' session works for pytest-gate."""
        unknown_sid = "unknown"
        test_sid = f"test-fallback-{uuid.uuid4().hex[:8]}"
        try:
            record_pytest_gate_passed(unknown_sid, issue_number=0)
            # Reading from a different session should merge from 'unknown'
            assert get_pytest_gate_passed(test_sid, issue_number=0) is True
        finally:
            clear_session(unknown_sid)
            clear_session(test_sid)

    def test_pytest_gate_failed_records_false(self, session_id: str):
        """Recording passed=False keeps gate closed."""
        record_pytest_gate_passed(session_id, passed=False)
        assert get_pytest_gate_passed(session_id) is False

    def test_pytest_gate_coexists_with_agents(self, session_id: str):
        """Other agent completions are unaffected by pytest-gate."""
        record_agent_completion(session_id, "implementer", success=True)
        record_pytest_gate_passed(session_id)
        completed = get_completed_agents(session_id)
        assert "implementer" in completed
        assert "pytest-gate" in completed

    def test_pytest_gate_per_issue_isolation(self, session_id: str):
        """Issue 1 passing doesn't affect issue 2."""
        record_pytest_gate_passed(session_id, issue_number=1)
        assert get_pytest_gate_passed(session_id, issue_number=1) is True
        assert get_pytest_gate_passed(session_id, issue_number=2) is False

    def test_record_pytest_gate_idempotent(self, session_id: str):
        """Calling record_pytest_gate_passed multiple times is idempotent (Issue #1238)."""
        # First call - records the gate
        record_pytest_gate_passed(session_id)
        completed_first = get_completed_agents(session_id)
        assert "pytest-gate" in completed_first
        
        # Second call with same session_id - should be idempotent (no error, same state)
        record_pytest_gate_passed(session_id)
        completed_second = get_completed_agents(session_id)
        assert "pytest-gate" in completed_second
        
        # The completion state should be the same after both calls
        assert completed_first == completed_second
        
        # Verify pytest-gate appears exactly once, not duplicated
        pytest_gate_entries = [agent for agent in completed_second if agent == "pytest-gate"]
        assert len(pytest_gate_entries) == 1, "pytest-gate should appear exactly once, not duplicated"
