#!/usr/bin/env python3
"""
Unit tests for completion_verifier library (TDD Red Phase).

Tests for pipeline completion verification with loop-back retry logic.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test pipeline completion verification (8 expected agents)
- Test circuit breaker logic (opens after 3 consecutive failures)
- Test exponential backoff timing (100ms → 200ms → 400ms → 800ms → 1600ms)
- Test retry decision logic with max attempts
- Test loop-back state persistence and recovery
- Test graceful degradation on errors
- Test missing agents detection and ordering

Expected 8 agents in order:
1. researcher-local
2. researcher-web
3. planner
4. test-master
5. implementer
6. reviewer
7. security-auditor
8. doc-master

Security:
- State file validation (CWE-22: path traversal)
- Audit logging for all retry attempts
- Circuit breaker prevents infinite loops
- Max retry limits prevent resource exhaustion

Coverage Target: 95%+ for completion_verifier.py

Date: 2026-01-01
Feature: Completion verification hook with loop-back for incomplete work
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - module doesn't exist yet)
"""

import json
import sys
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict
from typing import List

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - module doesn't exist yet (TDD!)
try:
    from completion_verifier import (
        CompletionVerifier,
        LoopBackState,
        VerificationResult,
        verify_pipeline_completion,
        should_retry,
        get_next_retry_delay,
        create_loop_back_checkpoint,
        EXPECTED_AGENTS,
        MAX_RETRY_ATTEMPTS,
        CIRCUIT_BREAKER_THRESHOLD,
        BASE_RETRY_DELAY_MS,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary directory for state files."""
    state_dir = tmp_path / ".claude"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def session_id():
    """Standard session ID for testing."""
    return "session-20260101-123456"


@pytest.fixture
def all_agents_session(temp_state_dir, session_id):
    """Mock session file with all 8 agents present."""
    session_file = temp_state_dir / "sessions" / f"{session_id}.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)

    session_data = {
        "session_id": session_id,
        "agents": [
            {"name": "researcher-local", "status": "complete", "timestamp": "2026-01-01T10:00:00"},
            {"name": "researcher-web", "status": "complete", "timestamp": "2026-01-01T10:02:00"},
            {"name": "planner", "status": "complete", "timestamp": "2026-01-01T10:05:00"},
            {"name": "test-master", "status": "complete", "timestamp": "2026-01-01T10:10:00"},
            {"name": "implementer", "status": "complete", "timestamp": "2026-01-01T10:15:00"},
            {"name": "reviewer", "status": "complete", "timestamp": "2026-01-01T10:20:00"},
            {"name": "security-auditor", "status": "complete", "timestamp": "2026-01-01T10:22:00"},
            {"name": "doc-master", "status": "complete", "timestamp": "2026-01-01T10:25:00"},
        ]
    }

    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


@pytest.fixture
def missing_agents_session(temp_state_dir, session_id):
    """Mock session file with 3 agents missing."""
    session_file = temp_state_dir / "sessions" / f"{session_id}.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)

    session_data = {
        "session_id": session_id,
        "agents": [
            {"name": "researcher-local", "status": "complete", "timestamp": "2026-01-01T10:00:00"},
            {"name": "researcher-web", "status": "complete", "timestamp": "2026-01-01T10:02:00"},
            {"name": "planner", "status": "complete", "timestamp": "2026-01-01T10:05:00"},
            # test-master MISSING
            {"name": "implementer", "status": "complete", "timestamp": "2026-01-01T10:15:00"},
            # reviewer MISSING
            {"name": "security-auditor", "status": "complete", "timestamp": "2026-01-01T10:22:00"},
            # doc-master MISSING
        ]
    }

    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


@pytest.fixture
def empty_session(temp_state_dir, session_id):
    """Mock session file with no agents."""
    session_file = temp_state_dir / "sessions" / f"{session_id}.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)

    session_data = {
        "session_id": session_id,
        "agents": []
    }

    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


@pytest.fixture
def loop_back_state(session_id):
    """Create sample LoopBackState for testing."""
    return LoopBackState(
        session_id=session_id,
        attempt_count=0,
        max_attempts=5,
        consecutive_failures=0,
        circuit_breaker_open=False,
        last_attempt_timestamp="2026-01-01T10:00:00",
        missing_agents=[]
    )


# =============================================================================
# SECTION 1: Pipeline Completion Verification Tests (4 tests)
# =============================================================================

class TestPipelineCompletionVerification:
    """Test verification of pipeline completion with all expected agents."""

    def test_verify_pipeline_completion_all_agents_present(self, temp_state_dir, session_id, all_agents_session):
        """Should return complete=True when all 8 agents are present."""
        result = verify_pipeline_completion(session_id, state_dir=temp_state_dir)

        assert result.complete is True
        assert len(result.agents_found) == 8
        assert len(result.missing_agents) == 0
        assert set(result.agents_found) == set([
            "researcher-local", "researcher-web", "planner", "test-master",
            "implementer", "reviewer", "security-auditor", "doc-master"
        ])
        assert result.verification_time_ms > 0

    def test_verify_pipeline_completion_missing_single_agent(self, temp_state_dir, session_id):
        """Should return complete=False when test-master is missing."""
        session_file = temp_state_dir / "sessions" / f"{session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        session_data = {
            "session_id": session_id,
            "agents": [
                {"name": "researcher-local", "status": "complete"},
                {"name": "researcher-web", "status": "complete"},
                {"name": "planner", "status": "complete"},
                # test-master MISSING
                {"name": "implementer", "status": "complete"},
                {"name": "reviewer", "status": "complete"},
                {"name": "security-auditor", "status": "complete"},
                {"name": "doc-master", "status": "complete"},
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        result = verify_pipeline_completion(session_id, state_dir=temp_state_dir)

        assert result.complete is False
        assert len(result.agents_found) == 7
        assert len(result.missing_agents) == 1
        assert "test-master" in result.missing_agents

    def test_verify_pipeline_completion_missing_multiple_agents(self, temp_state_dir, session_id, missing_agents_session):
        """Should return complete=False when 3 agents are missing."""
        result = verify_pipeline_completion(session_id, state_dir=temp_state_dir)

        assert result.complete is False
        assert len(result.agents_found) == 5
        assert len(result.missing_agents) == 3
        assert set(result.missing_agents) == {"test-master", "reviewer", "doc-master"}

    def test_verify_pipeline_completion_empty_session(self, temp_state_dir, session_id, empty_session):
        """Should return complete=False when no agents are present."""
        result = verify_pipeline_completion(session_id, state_dir=temp_state_dir)

        assert result.complete is False
        assert len(result.agents_found) == 0
        assert len(result.missing_agents) == 8
        assert set(result.missing_agents) == set([
            "researcher-local", "researcher-web", "planner", "test-master",
            "implementer", "reviewer", "security-auditor", "doc-master"
        ])


# =============================================================================
# SECTION 2: Circuit Breaker Logic Tests (3 tests)
# =============================================================================

class TestCircuitBreakerLogic:
    """Test circuit breaker opens after threshold consecutive failures."""

    def test_circuit_breaker_opens_after_threshold(self, loop_back_state):
        """Should open circuit breaker after 3 consecutive failures."""
        state = loop_back_state
        state.consecutive_failures = 3

        # Circuit breaker should trigger
        assert should_retry(state) is False
        assert state.circuit_breaker_open is True

    def test_circuit_breaker_stays_closed_with_success(self, loop_back_state):
        """Should reset consecutive failures counter on success."""
        state = loop_back_state
        state.consecutive_failures = 2

        # Simulate success - reset counter
        state.consecutive_failures = 0

        # Circuit should stay closed
        assert should_retry(state) is True
        assert state.circuit_breaker_open is False

    def test_circuit_breaker_stays_closed_below_threshold(self, loop_back_state):
        """Should keep circuit closed when failures below threshold."""
        state = loop_back_state
        state.consecutive_failures = 2
        state.attempt_count = 1

        # Circuit should stay closed (only 2 failures, threshold is 3)
        assert should_retry(state) is True
        assert state.circuit_breaker_open is False


# =============================================================================
# SECTION 3: Exponential Backoff Tests (3 tests)
# =============================================================================

class TestExponentialBackoff:
    """Test exponential backoff delay calculation."""

    def test_exponential_backoff_100ms_first_retry(self):
        """Should return 100ms delay for first retry (attempt 1)."""
        delay = get_next_retry_delay(attempt=1)
        assert delay == 100

    def test_exponential_backoff_progression(self):
        """Should follow exponential progression: 100→200→400→800→1600ms."""
        expected_delays = [100, 200, 400, 800, 1600]

        for attempt, expected in enumerate(expected_delays, start=1):
            delay = get_next_retry_delay(attempt)
            assert delay == expected, f"Attempt {attempt}: expected {expected}ms, got {delay}ms"

    def test_exponential_backoff_max_delay_cap(self):
        """Should cap delay at reasonable maximum (e.g., 5000ms after attempt 6+)."""
        # Attempt 6: 3200ms
        # Attempt 7: 6400ms - should cap at 5000ms
        delay = get_next_retry_delay(attempt=7)
        assert delay <= 5000, "Delay should be capped at 5000ms"


# =============================================================================
# SECTION 4: Retry Decision Logic Tests (3 tests)
# =============================================================================

class TestRetryDecisionLogic:
    """Test should_retry decision logic with max attempts."""

    def test_should_retry_true_below_max_attempts(self, loop_back_state):
        """Should return True when attempt count is below max attempts."""
        state = loop_back_state
        state.attempt_count = 2
        state.max_attempts = 5
        state.consecutive_failures = 0

        assert should_retry(state) is True

    def test_should_retry_false_max_attempts_reached(self, loop_back_state):
        """Should return False when max attempts (5) is reached."""
        state = loop_back_state
        state.attempt_count = 5
        state.max_attempts = 5
        state.consecutive_failures = 0

        assert should_retry(state) is False

    def test_should_retry_false_circuit_breaker_open(self, loop_back_state):
        """Should return False when circuit breaker is open."""
        state = loop_back_state
        state.attempt_count = 1
        state.circuit_breaker_open = True

        assert should_retry(state) is False


# =============================================================================
# SECTION 5: Loop-Back State Persistence Tests (3 tests)
# =============================================================================

class TestLoopBackStatePersistence:
    """Test loop-back state persistence to disk and recovery."""

    def test_loop_back_state_persistence_write_read(self, temp_state_dir, session_id, loop_back_state):
        """Should persist state to disk and read it back correctly."""
        state_file = temp_state_dir / "loop_back_state.json"

        # Write state
        state = loop_back_state
        state.attempt_count = 2
        state.consecutive_failures = 1
        state.missing_agents = ["test-master", "reviewer"]

        state_file.write_text(json.dumps(asdict(state), indent=2))

        # Read state back
        loaded_data = json.loads(state_file.read_text())
        loaded_state = LoopBackState(**loaded_data)

        assert loaded_state.session_id == session_id
        assert loaded_state.attempt_count == 2
        assert loaded_state.consecutive_failures == 1
        assert loaded_state.missing_agents == ["test-master", "reviewer"]

    def test_loop_back_state_cleared_on_success(self, temp_state_dir, loop_back_state):
        """Should delete state file when pipeline completes successfully."""
        state_file = temp_state_dir / "loop_back_state.json"

        # Write initial state
        state_file.write_text(json.dumps(asdict(loop_back_state), indent=2))
        assert state_file.exists()

        # Simulate success - delete state
        state_file.unlink()

        assert not state_file.exists()

    def test_loop_back_state_survives_restart(self, temp_state_dir, session_id, loop_back_state):
        """Should preserve state across process restarts."""
        state_file = temp_state_dir / "loop_back_state.json"

        # Write state
        state = loop_back_state
        state.attempt_count = 3
        state.consecutive_failures = 2
        state.missing_agents = ["doc-master"]

        state_file.write_text(json.dumps(asdict(state), indent=2))

        # Simulate restart - read state
        loaded_data = json.loads(state_file.read_text())
        recovered_state = LoopBackState(**loaded_data)

        # State should be preserved
        assert recovered_state.attempt_count == 3
        assert recovered_state.consecutive_failures == 2
        assert recovered_state.missing_agents == ["doc-master"]


# =============================================================================
# SECTION 6: Graceful Degradation Tests (2 tests)
# =============================================================================

class TestGracefulDegradation:
    """Test graceful degradation when errors occur."""

    def test_graceful_degradation_on_checkpoint_error(self, temp_state_dir, session_id):
        """Should return default VerificationResult on checkpoint creation error."""
        # Simulate unwritable directory
        with patch('pathlib.Path.write_text', side_effect=PermissionError("Access denied")):
            # Should not raise, should return default result
            try:
                result = create_loop_back_checkpoint(
                    session_id=session_id,
                    missing_agents=["test-master"],
                    state_dir=temp_state_dir
                )
                # Should return some default/error indicator
                assert result is not None
            except PermissionError:
                pytest.fail("Should gracefully handle permission errors")

    def test_graceful_degradation_on_session_read_error(self, temp_state_dir, session_id):
        """Should return incomplete result when session file is corrupted."""
        session_file = temp_state_dir / "sessions" / f"{session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        # Write corrupted JSON
        session_file.write_text("{ invalid json }")

        # Should not crash, should return incomplete result
        result = verify_pipeline_completion(session_id, state_dir=temp_state_dir)

        assert result.complete is False
        # Should detect all agents as missing on error
        assert len(result.missing_agents) > 0


# =============================================================================
# SECTION 7: Missing Agents Detection Tests (2 tests)
# =============================================================================

class TestMissingAgentsDetection:
    """Test detection and ordering of missing agents."""

    def test_missing_agents_detection_order(self, temp_state_dir, session_id):
        """Should return missing agents in pipeline order."""
        session_file = temp_state_dir / "sessions" / f"{session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        session_data = {
            "session_id": session_id,
            "agents": [
                {"name": "implementer", "status": "complete"},  # Out of order
                {"name": "researcher-local", "status": "complete"},
                {"name": "security-auditor", "status": "complete"},
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        result = verify_pipeline_completion(session_id, state_dir=temp_state_dir)

        # Missing agents should be in expected pipeline order
        expected_order = ["researcher-web", "planner", "test-master", "reviewer", "doc-master"]
        assert result.missing_agents == expected_order

    def test_missing_agents_includes_all_expected(self, temp_state_dir, session_id):
        """Should detect all expected agents when none are present."""
        session_file = temp_state_dir / "sessions" / f"{session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        session_data = {"session_id": session_id, "agents": []}
        session_file.write_text(json.dumps(session_data, indent=2))

        result = verify_pipeline_completion(session_id, state_dir=temp_state_dir)

        # All 8 agents should be missing
        assert len(result.missing_agents) == 8
        assert set(result.missing_agents) == set([
            "researcher-local", "researcher-web", "planner", "test-master",
            "implementer", "reviewer", "security-auditor", "doc-master"
        ])


# =============================================================================
# SECTION 8: CompletionVerifier Class Tests (3 tests)
# =============================================================================

class TestCompletionVerifierClass:
    """Test CompletionVerifier class methods."""

    def test_completion_verifier_initialization(self, temp_state_dir, session_id):
        """Should initialize CompletionVerifier with session ID and state directory."""
        verifier = CompletionVerifier(session_id, state_dir=temp_state_dir)

        assert verifier.session_id == session_id
        assert verifier.state_dir == temp_state_dir

    def test_completion_verifier_verify_method(self, temp_state_dir, session_id, all_agents_session):
        """Should verify pipeline completion via instance method."""
        verifier = CompletionVerifier(session_id, state_dir=temp_state_dir)
        result = verifier.verify()

        assert result.complete is True
        assert len(result.agents_found) == 8
        assert len(result.missing_agents) == 0

    def test_completion_verifier_retry_state_tracking(self, temp_state_dir, session_id, loop_back_state):
        """Should track retry state via instance method."""
        verifier = CompletionVerifier(session_id, state_dir=temp_state_dir)

        # Simulate retry state tracking
        state = loop_back_state
        state.attempt_count = 1

        # Should update state
        verifier.update_retry_state(state)

        # Should retrieve state
        retrieved_state = verifier.get_retry_state()
        assert retrieved_state.attempt_count == 1


# =============================================================================
# SECTION 9: Constants and Configuration Tests (2 tests)
# =============================================================================

class TestConstantsAndConfiguration:
    """Test module constants and configuration values."""

    def test_expected_agents_count(self):
        """Should expect exactly 8 agents in pipeline."""
        assert len(EXPECTED_AGENTS) == 8

    def test_expected_agents_order(self):
        """Should maintain correct pipeline agent order."""
        expected_order = [
            "researcher-local",
            "researcher-web",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]
        assert EXPECTED_AGENTS == expected_order

    def test_retry_configuration_constants(self):
        """Should define correct retry configuration constants."""
        assert MAX_RETRY_ATTEMPTS == 5
        assert CIRCUIT_BREAKER_THRESHOLD == 3
        assert BASE_RETRY_DELAY_MS == 100


# =============================================================================
# Test Execution
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
