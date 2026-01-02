"""
Unit Tests for RalphLoopManager (Ralph Loop Pattern - Issue #189)

Tests comprehensive loop management functionality for self-correcting agent execution:
- State initialization and persistence
- Iteration tracking (increment, reset, max limit enforcement)
- Circuit breaker logic (threshold 3, trip, reset)
- Cost tracking (token usage, limit enforcement)
- Thread safety for concurrent access

Test Organization:
1. State Initialization (4 tests)
2. Iteration Tracking (5 tests)
3. Circuit Breaker (6 tests)
4. Cost Tracking (5 tests)
5. Thread Safety (3 tests)

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially - RalphLoopManager doesn't exist yet

Date: 2026-01-02
Issue: #189 (Ralph Loop Pattern for Self-Correcting Agent Execution)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import will fail - module doesn't exist yet (TDD!)
try:
    from ralph_loop_manager import (
        RalphLoopManager,
        RalphLoopState,
        MAX_ITERATIONS,
        CIRCUIT_BREAKER_THRESHOLD,
        DEFAULT_TOKEN_LIMIT,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


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
    return "session-20260102-123456"


@pytest.fixture
def manager(temp_state_dir, session_id):
    """Create RalphLoopManager instance."""
    return RalphLoopManager(session_id, state_dir=temp_state_dir)


@pytest.fixture
def sample_state(session_id):
    """Create sample RalphLoopState for testing."""
    return RalphLoopState(
        session_id=session_id,
        current_iteration=0,
        total_attempts=0,
        consecutive_failures=0,
        circuit_breaker_open=False,
        tokens_used=0,
        token_limit=10000,
        created_at="2026-01-02T10:00:00Z",
        updated_at="2026-01-02T10:00:00Z",
    )


# =============================================================================
# SECTION 1: State Initialization Tests (4 tests)
# =============================================================================

class TestStateInitialization:
    """Test state initialization and persistence."""

    def test_manager_initializes_with_default_state(self, manager, session_id):
        """Test that manager initializes with clean state."""
        # Assert - verify default state
        assert manager.session_id == session_id
        assert manager.current_iteration == 0
        assert manager.total_attempts == 0
        assert manager.consecutive_failures == 0
        assert manager.circuit_breaker_open is False
        assert manager.tokens_used == 0

    def test_manager_creates_state_file_on_first_save(self, temp_state_dir, session_id):
        """Test that state file is created on first save."""
        # Arrange
        manager = RalphLoopManager(session_id, state_dir=temp_state_dir)
        state_file = temp_state_dir / f"{session_id}_loop_state.json"

        # Assert - file doesn't exist initially
        assert not state_file.exists()

        # Act - trigger save
        manager.save_state()

        # Assert - file created
        assert state_file.exists()

    def test_manager_loads_existing_state_from_file(self, temp_state_dir, session_id):
        """Test that manager loads existing state from file."""
        # Arrange - create manager and modify state
        manager1 = RalphLoopManager(session_id, state_dir=temp_state_dir)
        manager1.record_attempt(tokens_used=500)
        manager1.record_attempt(tokens_used=300)
        manager1.save_state()

        # Act - create new manager (should load from file)
        manager2 = RalphLoopManager(session_id, state_dir=temp_state_dir)

        # Assert - state loaded
        assert manager2.current_iteration == 2
        assert manager2.tokens_used == 800

    def test_state_file_contains_all_required_fields(self, manager, temp_state_dir, session_id):
        """Test that state file contains all required fields."""
        # Arrange & Act
        manager.save_state()
        state_file = temp_state_dir / f"{session_id}_loop_state.json"
        data = json.loads(state_file.read_text())

        # Assert - all fields present
        required_fields = [
            "session_id",
            "current_iteration",
            "total_attempts",
            "consecutive_failures",
            "circuit_breaker_open",
            "tokens_used",
            "token_limit",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in data


# =============================================================================
# SECTION 2: Iteration Tracking Tests (5 tests)
# =============================================================================

class TestIterationTracking:
    """Test iteration tracking and limits."""

    def test_record_attempt_increments_iteration(self, manager):
        """Test that record_attempt increments current_iteration."""
        # Arrange
        initial_iteration = manager.current_iteration

        # Act
        manager.record_attempt(tokens_used=100)

        # Assert
        assert manager.current_iteration == initial_iteration + 1

    def test_record_attempt_increments_total_attempts(self, manager):
        """Test that record_attempt increments total_attempts."""
        # Arrange
        initial_total = manager.total_attempts

        # Act
        manager.record_attempt(tokens_used=100)
        manager.record_attempt(tokens_used=100)

        # Assert
        assert manager.total_attempts == initial_total + 2

    def test_should_retry_false_when_max_iterations_reached(self, manager):
        """Test that should_retry returns False when max iterations reached."""
        # Arrange - simulate MAX_ITERATIONS attempts
        for _ in range(MAX_ITERATIONS):
            manager.record_attempt(tokens_used=100)

        # Act
        should_retry = manager.should_retry()

        # Assert
        assert should_retry is False

    def test_should_retry_true_under_max_iterations(self, manager):
        """Test that should_retry returns True when under max iterations."""
        # Arrange - simulate fewer than MAX_ITERATIONS attempts
        for _ in range(MAX_ITERATIONS - 2):
            manager.record_attempt(tokens_used=100)

        # Act
        should_retry = manager.should_retry()

        # Assert
        assert should_retry is True

    def test_max_iterations_constant_set_to_5(self):
        """Test that MAX_ITERATIONS constant is set to 5."""
        # Assert
        assert MAX_ITERATIONS == 5


# =============================================================================
# SECTION 3: Circuit Breaker Tests (6 tests)
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker logic."""

    def test_record_failure_increments_consecutive_failures(self, manager):
        """Test that record_failure increments consecutive_failures."""
        # Arrange
        initial_failures = manager.consecutive_failures

        # Act
        manager.record_failure("Test error")

        # Assert
        assert manager.consecutive_failures == initial_failures + 1

    def test_circuit_breaker_opens_after_threshold(self, manager):
        """Test that circuit breaker opens after threshold failures."""
        # Arrange & Act - record threshold failures
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            manager.record_failure("Test error")

        # Assert
        assert manager.circuit_breaker_open is True

    def test_circuit_breaker_threshold_constant_set_to_3(self):
        """Test that CIRCUIT_BREAKER_THRESHOLD constant is set to 3."""
        # Assert
        assert CIRCUIT_BREAKER_THRESHOLD == 3

    def test_should_retry_false_when_circuit_breaker_open(self, manager):
        """Test that should_retry returns False when circuit breaker is open."""
        # Arrange - trip circuit breaker
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            manager.record_failure("Test error")

        # Act
        should_retry = manager.should_retry()

        # Assert
        assert should_retry is False

    def test_record_success_resets_consecutive_failures(self, manager):
        """Test that record_success resets consecutive_failures."""
        # Arrange - record some failures
        manager.record_failure("Error 1")
        manager.record_failure("Error 2")
        assert manager.consecutive_failures == 2

        # Act
        manager.record_success()

        # Assert
        assert manager.consecutive_failures == 0

    def test_is_circuit_breaker_open_returns_correct_state(self, manager):
        """Test that is_circuit_breaker_open returns correct state."""
        # Assert - initially closed
        assert manager.is_circuit_breaker_open() is False

        # Arrange - trip circuit breaker
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            manager.record_failure("Test error")

        # Act & Assert - now open
        assert manager.is_circuit_breaker_open() is True


# =============================================================================
# SECTION 4: Cost Tracking Tests (5 tests)
# =============================================================================

class TestCostTracking:
    """Test token usage tracking and limits."""

    def test_record_attempt_accumulates_tokens(self, manager):
        """Test that record_attempt accumulates token usage."""
        # Arrange
        initial_tokens = manager.tokens_used

        # Act
        manager.record_attempt(tokens_used=500)
        manager.record_attempt(tokens_used=300)

        # Assert
        assert manager.tokens_used == initial_tokens + 800

    def test_should_retry_false_when_token_limit_exceeded(self, manager):
        """Test that should_retry returns False when token limit exceeded."""
        # Arrange - set low token limit
        manager.token_limit = 1000

        # Simulate token usage exceeding limit
        manager.record_attempt(tokens_used=600)
        manager.record_attempt(tokens_used=500)

        # Act
        should_retry = manager.should_retry()

        # Assert
        assert should_retry is False

    def test_default_token_limit_set_to_reasonable_value(self):
        """Test that DEFAULT_TOKEN_LIMIT is set to reasonable value."""
        # Assert - should be high enough for typical loops
        assert DEFAULT_TOKEN_LIMIT >= 10000
        assert DEFAULT_TOKEN_LIMIT <= 100000

    def test_token_limit_configurable_at_initialization(self, temp_state_dir, session_id):
        """Test that token limit can be set at initialization."""
        # Arrange & Act
        custom_limit = 5000
        manager = RalphLoopManager(session_id, state_dir=temp_state_dir, token_limit=custom_limit)

        # Assert
        assert manager.token_limit == custom_limit

    def test_tokens_used_persists_across_manager_instances(self, temp_state_dir, session_id):
        """Test that tokens_used persists across manager instances."""
        # Arrange - create manager and use tokens
        manager1 = RalphLoopManager(session_id, state_dir=temp_state_dir)
        manager1.record_attempt(tokens_used=500)
        manager1.save_state()

        # Act - create new manager
        manager2 = RalphLoopManager(session_id, state_dir=temp_state_dir)

        # Assert - tokens_used persisted
        assert manager2.tokens_used == 500


# =============================================================================
# SECTION 5: Thread Safety Tests (3 tests)
# =============================================================================

class TestThreadSafety:
    """Test thread safety for concurrent access."""

    def test_concurrent_record_attempts_are_thread_safe(self, manager):
        """Test that concurrent record_attempt calls are thread-safe."""
        # Arrange
        num_threads = 10
        attempts_per_thread = 5
        results = []

        def worker():
            try:
                for _ in range(attempts_per_thread):
                    manager.record_attempt(tokens_used=100)
                results.append("success")
            except Exception as e:
                results.append(f"error: {e}")

        # Act - spawn threads
        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert - all threads succeeded
        assert len(results) == num_threads
        assert all(r == "success" for r in results)

        # Assert - final counts correct
        expected_total = num_threads * attempts_per_thread
        assert manager.total_attempts == expected_total

    def test_state_save_uses_atomic_write(self, manager):
        """Test that save_state uses atomic write (temp + rename)."""
        # Arrange & Act
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.write") as mock_write, \
             patch("os.close") as mock_close, \
             patch("pathlib.Path.replace") as mock_replace:

            mock_mkstemp.return_value = (999, "/tmp/.loop_state_abc.tmp")

            # Trigger save
            manager.save_state()

            # Assert - atomic write pattern used
            mock_mkstemp.assert_called()
            mock_write.assert_called()
            mock_close.assert_called()
            mock_replace.assert_called()

    def test_load_state_handles_corrupted_file_gracefully(self, temp_state_dir, session_id):
        """Test that manager handles corrupted state file gracefully."""
        # Arrange - create corrupted state file
        state_file = temp_state_dir / f"{session_id}_loop_state.json"
        state_file.write_text("{invalid json")

        # Act - should start with fresh state (not crash)
        manager = RalphLoopManager(session_id, state_dir=temp_state_dir)

        # Assert - initialized with clean state
        assert manager.current_iteration == 0
        assert manager.total_attempts == 0


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (23 unit tests for ralph_loop_manager.py):

SECTION 1: State Initialization (4 tests)
✗ test_manager_initializes_with_default_state
✗ test_manager_creates_state_file_on_first_save
✗ test_manager_loads_existing_state_from_file
✗ test_state_file_contains_all_required_fields

SECTION 2: Iteration Tracking (5 tests)
✗ test_record_attempt_increments_iteration
✗ test_record_attempt_increments_total_attempts
✗ test_should_retry_false_when_max_iterations_reached
✗ test_should_retry_true_under_max_iterations
✗ test_max_iterations_constant_set_to_5

SECTION 3: Circuit Breaker (6 tests)
✗ test_record_failure_increments_consecutive_failures
✗ test_circuit_breaker_opens_after_threshold
✗ test_circuit_breaker_threshold_constant_set_to_3
✗ test_should_retry_false_when_circuit_breaker_open
✗ test_record_success_resets_consecutive_failures
✗ test_is_circuit_breaker_open_returns_correct_state

SECTION 4: Cost Tracking (5 tests)
✗ test_record_attempt_accumulates_tokens
✗ test_should_retry_false_when_token_limit_exceeded
✗ test_default_token_limit_set_to_reasonable_value
✗ test_token_limit_configurable_at_initialization
✗ test_tokens_used_persists_across_manager_instances

SECTION 5: Thread Safety (3 tests)
✗ test_concurrent_record_attempts_are_thread_safe
✗ test_state_save_uses_atomic_write
✗ test_load_state_handles_corrupted_file_gracefully

Expected Status: ALL TESTS FAILING (RED phase - implementation doesn't exist yet)
Next Step: Implement RalphLoopManager to make tests pass (GREEN phase)
"""
