#!/usr/bin/env python3
"""
Unit Tests for Ralph Loop Manager - Retry History Tracking (Issue #256)

Tests for new retry_history field in RalphLoopState:
- retry_history field exists in dataclass
- record_failure() adds entries to retry_history
- retry_history persists across save/load cycles
- Backward compatibility with old state files missing retry_history

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially

Date: 2026-01-19
Issue: #256 (Enable Ralph Loop by default and fix skipped feature tracking)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)
"""

import json
import os
import sys
import pytest
import time
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import will succeed - module exists but field doesn't
try:
    from ralph_loop_manager import (
        RalphLoopManager,
        RalphLoopState,
        MAX_ITERATIONS,
        CIRCUIT_BREAKER_THRESHOLD,
        DEFAULT_TOKEN_LIMIT,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary directory for state files."""
    state_dir = tmp_path / ".ralph-loop"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def session_id():
    """Sample session ID for testing."""
    return "session-20260119-test"


@pytest.fixture
def manager(temp_state_dir, session_id):
    """Create RalphLoopManager instance."""
    return RalphLoopManager(session_id, state_dir=temp_state_dir)


# =============================================================================
# SECTION 1: retry_history Field Tests (3 tests)
# =============================================================================

class TestRetryHistoryField:
    """Test that retry_history field exists in RalphLoopState dataclass."""

    def test_retry_history_field_exists_in_dataclass(self):
        """Test that RalphLoopState has retry_history field."""
        # Arrange & Act
        state = RalphLoopState(
            session_id="test-session",
            current_iteration=0,
            total_attempts=0,
            consecutive_failures=0,
            circuit_breaker_open=False,
            tokens_used=0,
            token_limit=10000,
        )

        # Assert - retry_history field should exist
        assert hasattr(state, "retry_history"), (
            "RalphLoopState should have retry_history field"
        )

        # Should be a list
        assert isinstance(state.retry_history, list), (
            "retry_history should be a list"
        )

        # Should default to empty list
        assert state.retry_history == [], (
            "retry_history should default to empty list"
        )

    def test_retry_history_type_annotation(self):
        """Test that retry_history has correct type annotation."""
        # Arrange & Act
        # Check type hints on RalphLoopState
        from typing import get_type_hints

        type_hints = get_type_hints(RalphLoopState)

        # Assert - retry_history should be List[Dict]
        assert "retry_history" in type_hints, (
            "retry_history should have type annotation"
        )

        # Type should be List[Dict[str, Any]] or similar
        # We check that it's a list type
        hint_str = str(type_hints["retry_history"])
        assert "list" in hint_str.lower() or "List" in hint_str, (
            f"retry_history type hint should be a List type, got: {hint_str}"
        )

    def test_retry_history_initialized_empty_in_manager(self, manager):
        """Test that manager initializes retry_history as empty list."""
        # Arrange & Act - manager created in fixture

        # Assert - should have empty retry_history
        # Access via manager's state or direct attribute
        assert hasattr(manager, "retry_history") or hasattr(manager, "_state"), (
            "Manager should track retry_history"
        )

        # If manager exposes retry_history directly
        if hasattr(manager, "retry_history"):
            assert manager.retry_history == []

        # If manager stores state internally
        if hasattr(manager, "_state"):
            assert manager._state.retry_history == []


# =============================================================================
# SECTION 2: record_failure() Adds to History (4 tests)
# =============================================================================

class TestRecordFailureHistory:
    """Test that record_failure() adds entries to retry_history."""

    def test_record_failure_adds_to_history(self, manager):
        """Test that record_failure() adds entry to retry_history."""
        # Arrange
        error_message = "Test failed with assertion error"

        # Act
        manager.record_failure(error_message)

        # Assert - retry_history should have 1 entry
        # Access retry_history (either directly or via state)
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history from manager")

        assert len(history) == 1

        # Verify entry structure
        entry = history[0]
        assert "error_message" in entry
        assert entry["error_message"] == error_message
        assert "timestamp" in entry
        assert "iteration" in entry

    def test_record_failure_includes_timestamp(self, manager):
        """Test that record_failure() includes timestamp in history entry."""
        # Act
        before_time = datetime.utcnow().isoformat()
        manager.record_failure("Error message")
        after_time = datetime.utcnow().isoformat()

        # Assert
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        entry = history[0]
        timestamp = entry["timestamp"]

        # Timestamp should be between before and after
        assert before_time <= timestamp <= after_time

    def test_record_failure_includes_iteration_number(self, manager):
        """Test that record_failure() includes current iteration number."""
        # Arrange - record some attempts first
        manager.record_attempt(tokens_used=100)
        manager.record_attempt(tokens_used=100)

        # Act - record failure at iteration 2
        manager.record_failure("Failure at iteration 2")

        # Assert
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        entry = history[0]
        assert entry["iteration"] == 2, (
            "History entry should record current iteration number"
        )

    def test_record_failure_allows_multiple_entries(self, manager):
        """Test that record_failure() allows multiple history entries."""
        # Act - record multiple failures
        manager.record_failure("Error 1")
        manager.record_failure("Error 2")
        manager.record_failure("Error 3")

        # Assert
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        assert len(history) == 3

        # Verify each entry
        assert history[0]["error_message"] == "Error 1"
        assert history[1]["error_message"] == "Error 2"
        assert history[2]["error_message"] == "Error 3"


# =============================================================================
# SECTION 3: Persistence Tests (3 tests)
# =============================================================================

class TestRetryHistoryPersistence:
    """Test that retry_history persists across save/load cycles."""

    def test_retry_history_persists_across_save_load(self, temp_state_dir, session_id):
        """Test that retry_history persists when state is saved and reloaded."""
        # Arrange - create manager and record failures
        manager1 = RalphLoopManager(session_id, state_dir=temp_state_dir)
        manager1.record_failure("Failure 1")
        manager1.record_failure("Failure 2")

        # Save state
        manager1.save_state()

        # Act - create new manager (should load from saved state)
        manager2 = RalphLoopManager(session_id, state_dir=temp_state_dir)

        # Assert - retry_history should be preserved
        if hasattr(manager2, "retry_history"):
            history = manager2.retry_history
        elif hasattr(manager2, "_state"):
            history = manager2._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        assert len(history) == 2
        assert history[0]["error_message"] == "Failure 1"
        assert history[1]["error_message"] == "Failure 2"

    def test_retry_history_field_in_json_file(self, temp_state_dir, session_id):
        """Test that retry_history appears in saved JSON state file."""
        # Arrange
        manager = RalphLoopManager(session_id, state_dir=temp_state_dir)
        manager.record_failure("Test error")

        # Act - save state
        manager.save_state()

        # Assert - check raw JSON file
        state_file = temp_state_dir / f"{session_id}_loop_state.json"
        data = json.loads(state_file.read_text())

        assert "retry_history" in data
        assert len(data["retry_history"]) == 1
        assert data["retry_history"][0]["error_message"] == "Test error"

    def test_retry_history_backward_compat_missing_field(self, temp_state_dir, session_id):
        """Test backward compatibility when loading old state files without retry_history."""
        # Arrange - create old-style state file (no retry_history field)
        state_file = temp_state_dir / f"{session_id}_loop_state.json"
        old_state = {
            "session_id": session_id,
            "current_iteration": 2,
            "total_attempts": 3,
            "consecutive_failures": 1,
            "circuit_breaker_open": False,
            "tokens_used": 5000,
            "token_limit": 50000,
            "created_at": "2026-01-19T10:00:00Z",
            "updated_at": "2026-01-19T10:05:00Z",
            # NO retry_history field (old format)
        }
        state_file.write_text(json.dumps(old_state))

        # Act - load old state (should not crash)
        manager = RalphLoopManager(session_id, state_dir=temp_state_dir)

        # Assert - retry_history should default to empty list
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        assert history == [], (
            "When loading old state without retry_history, should default to empty list"
        )

        # Other fields should still be loaded correctly
        assert manager.current_iteration == 2
        assert manager.total_attempts == 3
        assert manager.tokens_used == 5000


# =============================================================================
# SECTION 4: Integration Tests (3 tests)
# =============================================================================

class TestRetryHistoryIntegration:
    """Integration tests for retry_history workflow."""

    def test_retry_history_workflow_with_circuit_breaker(self, manager):
        """Test retry_history tracks failures leading to circuit breaker."""
        # Act - record failures until circuit breaker trips
        for i in range(CIRCUIT_BREAKER_THRESHOLD):
            manager.record_failure(f"Failure {i+1}")

        # Assert - circuit breaker should be open
        assert manager.is_circuit_breaker_open() is True

        # Verify retry_history has all failures
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        assert len(history) == CIRCUIT_BREAKER_THRESHOLD
        assert history[0]["error_message"] == "Failure 1"
        assert history[1]["error_message"] == "Failure 2"
        assert history[2]["error_message"] == "Failure 3"

    def test_retry_history_cleared_on_success(self, manager):
        """Test that retry_history behavior with successful attempts.

        Note: Implementation can choose to either:
        1. Keep full history (never clear)
        2. Clear on success (only track consecutive failures)

        This test documents the expected behavior.
        """
        # Arrange - record failure, then success
        manager.record_failure("Failure before success")
        manager.record_success()

        # Assert - check if history is preserved or cleared
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        # Implementation choice: either keep history or clear it
        # Both are valid - this test just documents the behavior
        # If cleared: len(history) == 0
        # If kept: len(history) == 1

        # For Issue #256, we document that history is KEPT (not cleared)
        assert len(history) == 1, (
            "retry_history should be preserved across successes to track full attempt history"
        )

    def test_retry_history_with_max_iterations(self, manager):
        """Test retry_history when max iterations limit is reached."""
        # Arrange & Act - record attempts and failures up to max iterations
        for i in range(MAX_ITERATIONS):
            manager.record_attempt(tokens_used=1000)
            manager.record_failure(f"Failure at iteration {i}")

        # Assert - should have MAX_ITERATIONS entries
        if hasattr(manager, "retry_history"):
            history = manager.retry_history
        elif hasattr(manager, "_state"):
            history = manager._state.retry_history
        else:
            pytest.fail("Cannot access retry_history")

        assert len(history) == MAX_ITERATIONS

        # Verify we've hit max iterations
        assert manager.current_iteration == MAX_ITERATIONS
        assert manager.should_retry() is False


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (13 unit tests for ralph_loop_manager.py - retry_history):

SECTION 1: retry_history Field (3 tests)
✗ test_retry_history_field_exists_in_dataclass
✗ test_retry_history_type_annotation
✗ test_retry_history_initialized_empty_in_manager

SECTION 2: record_failure() Adds to History (4 tests)
✗ test_record_failure_adds_to_history
✗ test_record_failure_includes_timestamp
✗ test_record_failure_includes_iteration_number
✗ test_record_failure_allows_multiple_entries

SECTION 3: Persistence Tests (3 tests)
✗ test_retry_history_persists_across_save_load
✗ test_retry_history_field_in_json_file
✗ test_retry_history_backward_compat_missing_field

SECTION 4: Integration Tests (3 tests)
✗ test_retry_history_workflow_with_circuit_breaker
✗ test_retry_history_cleared_on_success
✗ test_retry_history_with_max_iterations

Expected Status: TESTS WILL FAIL (RED phase - implementation not done yet)

Implementation Requirements:
1. Add retry_history field to RalphLoopState dataclass
   - Type: List[Dict[str, Any]]
   - Default: field(default_factory=list)
2. Update record_failure() to add entries to retry_history:
   - Include error_message
   - Include timestamp (ISO 8601 format)
   - Include current iteration number
3. Ensure retry_history persists in JSON save/load
4. Backward compatibility: default to [] if missing in old state files
5. History entries structure:
   {
       "error_message": str,
       "timestamp": str (ISO 8601),
       "iteration": int
   }

Coverage Target: 90%+ for retry_history functionality
Design Decision: Keep full history (don't clear on success) for debugging
"""
