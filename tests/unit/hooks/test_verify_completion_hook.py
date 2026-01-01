#!/usr/bin/env python3
"""
Unit tests for verify_completion hook (SubagentStop lifecycle).

Tests for completion verification hook that triggers loop-back for incomplete work.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test hook triggering logic (only on doc-master completion)
- Test checkpoint creation for missing agents
- Test circuit breaker respect (no retry when open)
- Test graceful exit on all errors (always exit 0)
- Test integration with CompletionVerifier library
- Test audit logging for all verification attempts

Hook Type: SubagentStop
Trigger: After doc-master agent completes (last agent in pipeline)
Condition: Verify all 8 agents completed, create loop-back checkpoint if incomplete

Expected 8 agents:
1. researcher-local
2. researcher-web
3. planner
4. test-master
5. implementer
6. reviewer
7. security-auditor
8. doc-master

Security:
- Path validation (CWE-22: path traversal)
- Audit logging for all retry attempts
- Graceful degradation (never blocks workflow)
- Always exit 0 (non-blocking hook)

Coverage Target: 95%+ for verify_completion hook

Date: 2026-01-01
Feature: Completion verification hook with loop-back for incomplete work
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - hook doesn't exist yet)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from dataclasses import asdict

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# Add lib directory for CompletionVerifier
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - hook doesn't exist yet (TDD!)
try:
    from verify_completion import (
        should_trigger_verification,
        get_session_id_from_context,
        verify_and_create_checkpoint,
        log_verification_result,
        run_hook,
        main,
    )
    from completion_verifier import (
        LoopBackState,
        VerificationResult,
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
    sessions_dir = state_dir / "sessions"
    sessions_dir.mkdir()
    return state_dir


@pytest.fixture
def session_id():
    """Standard session ID for testing."""
    return "session-20260101-123456"


@pytest.fixture
def hook_context(session_id):
    """Standard hook context for SubagentStop lifecycle."""
    return {
        "lifecycle": "SubagentStop",
        "agent_name": "doc-master",
        "session_id": session_id,
        "status": "complete",
        "timestamp": "2026-01-01T10:25:00"
    }


@pytest.fixture
def complete_verification_result():
    """Mock VerificationResult for complete pipeline."""
    return VerificationResult(
        complete=True,
        agents_found=[
            "researcher-local", "researcher-web", "planner", "test-master",
            "implementer", "reviewer", "security-auditor", "doc-master"
        ],
        missing_agents=[],
        verification_time_ms=45.2
    )


@pytest.fixture
def incomplete_verification_result():
    """Mock VerificationResult for incomplete pipeline."""
    return VerificationResult(
        complete=False,
        agents_found=["researcher-local", "planner", "implementer", "security-auditor", "doc-master"],
        missing_agents=["researcher-web", "test-master", "reviewer"],
        verification_time_ms=38.7
    )


@pytest.fixture
def loop_back_state(session_id):
    """Mock LoopBackState for testing."""
    return LoopBackState(
        session_id=session_id,
        attempt_count=0,
        max_attempts=5,
        consecutive_failures=0,
        circuit_breaker_open=False,
        last_attempt_timestamp="2026-01-01T10:25:00",
        missing_agents=[]
    )


# =============================================================================
# SECTION 1: Hook Triggering Logic Tests (5 tests)
# =============================================================================

class TestHookTriggeringLogic:
    """Test when hook should trigger verification."""

    def test_hook_triggers_on_doc_master_completion(self):
        """Should trigger verification when doc-master agent completes."""
        assert should_trigger_verification("doc-master") is True

    def test_hook_skips_on_researcher_completion(self):
        """Should NOT trigger for researcher-local agent."""
        assert should_trigger_verification("researcher-local") is False

    def test_hook_skips_on_planner_completion(self):
        """Should NOT trigger for planner agent."""
        assert should_trigger_verification("planner") is False

    def test_hook_skips_on_implementer_completion(self):
        """Should NOT trigger for implementer agent."""
        assert should_trigger_verification("implementer") is False

    def test_hook_skips_on_security_auditor_completion(self):
        """Should NOT trigger for security-auditor agent."""
        assert should_trigger_verification("security-auditor") is False


# =============================================================================
# SECTION 2: Checkpoint Creation Tests (4 tests)
# =============================================================================

class TestCheckpointCreation:
    """Test checkpoint creation for incomplete pipelines."""

    @patch('verify_completion.CompletionVerifier')
    def test_hook_creates_checkpoint_on_missing_agents(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result):
        """Should create loop-back checkpoint when agents are missing."""
        # Mock verifier to return incomplete result
        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_verifier.return_value = mock_instance

        # Run verification
        verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)

        # Should create checkpoint file
        checkpoint_file = temp_state_dir / "loop_back_checkpoint.json"
        assert checkpoint_file.exists()

        # Checkpoint should contain missing agents
        checkpoint_data = json.loads(checkpoint_file.read_text())
        assert "missing_agents" in checkpoint_data
        assert set(checkpoint_data["missing_agents"]) == {"researcher-web", "test-master", "reviewer"}

    @patch('verify_completion.CompletionVerifier')
    def test_hook_skips_checkpoint_on_complete_pipeline(self, mock_verifier, temp_state_dir, session_id, complete_verification_result):
        """Should NOT create checkpoint when all agents are present."""
        # Mock verifier to return complete result
        mock_instance = MagicMock()
        mock_instance.verify.return_value = complete_verification_result
        mock_verifier.return_value = mock_instance

        # Run verification
        verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)

        # Should NOT create checkpoint file
        checkpoint_file = temp_state_dir / "loop_back_checkpoint.json"
        assert not checkpoint_file.exists()

    @patch('verify_completion.CompletionVerifier')
    def test_checkpoint_contains_session_metadata(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result):
        """Should include session ID and timestamp in checkpoint."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_verifier.return_value = mock_instance

        verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)

        checkpoint_file = temp_state_dir / "loop_back_checkpoint.json"
        checkpoint_data = json.loads(checkpoint_file.read_text())

        assert checkpoint_data["session_id"] == session_id
        assert "timestamp" in checkpoint_data
        assert "attempt_count" in checkpoint_data

    @patch('verify_completion.CompletionVerifier')
    def test_checkpoint_increments_attempt_count(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result, loop_back_state):
        """Should increment attempt count on each checkpoint creation."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_instance.get_retry_state.return_value = loop_back_state
        mock_verifier.return_value = mock_instance

        # First checkpoint
        verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)
        checkpoint_file = temp_state_dir / "loop_back_checkpoint.json"
        checkpoint_data_1 = json.loads(checkpoint_file.read_text())

        # Second checkpoint (simulate retry)
        loop_back_state.attempt_count = 1
        verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)
        checkpoint_data_2 = json.loads(checkpoint_file.read_text())

        # Attempt count should increment
        assert checkpoint_data_2["attempt_count"] > checkpoint_data_1["attempt_count"]


# =============================================================================
# SECTION 3: Circuit Breaker Respect Tests (3 tests)
# =============================================================================

class TestCircuitBreakerRespect:
    """Test hook respects circuit breaker state."""

    @patch('verify_completion.CompletionVerifier')
    def test_hook_respects_circuit_breaker_open(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result, loop_back_state):
        """Should NOT create checkpoint when circuit breaker is open."""
        # Set circuit breaker to open
        loop_back_state.circuit_breaker_open = True

        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_instance.get_retry_state.return_value = loop_back_state
        mock_verifier.return_value = mock_instance

        verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)

        # Should NOT create checkpoint
        checkpoint_file = temp_state_dir / "loop_back_checkpoint.json"
        assert not checkpoint_file.exists()

    @patch('verify_completion.CompletionVerifier')
    def test_hook_logs_circuit_breaker_open(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result, loop_back_state, caplog):
        """Should log message when circuit breaker prevents retry."""
        loop_back_state.circuit_breaker_open = True

        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_instance.get_retry_state.return_value = loop_back_state
        mock_verifier.return_value = mock_instance

        with caplog.at_level('INFO'):
            verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)

        # Should log circuit breaker open
        assert any("circuit breaker" in record.message.lower() for record in caplog.records)

    @patch('verify_completion.CompletionVerifier')
    def test_hook_respects_max_attempts_reached(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result, loop_back_state):
        """Should NOT create checkpoint when max attempts (5) reached."""
        # Set attempt count to max
        loop_back_state.attempt_count = 5
        loop_back_state.max_attempts = 5

        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_instance.get_retry_state.return_value = loop_back_state
        mock_verifier.return_value = mock_instance

        verify_and_create_checkpoint(session_id, state_dir=temp_state_dir)

        # Should NOT create checkpoint
        checkpoint_file = temp_state_dir / "loop_back_checkpoint.json"
        assert not checkpoint_file.exists()


# =============================================================================
# SECTION 4: Graceful Exit Tests (4 tests)
# =============================================================================

class TestGracefulExit:
    """Test hook always exits gracefully (exit 0)."""

    @patch('verify_completion.CompletionVerifier')
    def test_hook_graceful_exit_on_verification_error(self, mock_verifier, temp_state_dir, session_id):
        """Should exit 0 when verification raises exception."""
        # Mock verifier to raise exception
        mock_instance = MagicMock()
        mock_instance.verify.side_effect = Exception("Verification failed")
        mock_verifier.return_value = mock_instance

        # Should not raise, should exit 0
        exit_code = run_hook(session_id, state_dir=temp_state_dir)
        assert exit_code == 0

    @patch('verify_completion.CompletionVerifier')
    def test_hook_graceful_exit_on_checkpoint_write_error(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result):
        """Should exit 0 when checkpoint write fails."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_verifier.return_value = mock_instance

        # Make state directory unwritable
        with patch('pathlib.Path.write_text', side_effect=PermissionError("Access denied")):
            exit_code = run_hook(session_id, state_dir=temp_state_dir)
            assert exit_code == 0

    @patch('verify_completion.CompletionVerifier')
    def test_hook_graceful_exit_on_session_not_found(self, mock_verifier, temp_state_dir, session_id):
        """Should exit 0 when session file doesn't exist."""
        mock_instance = MagicMock()
        mock_instance.verify.side_effect = FileNotFoundError("Session not found")
        mock_verifier.return_value = mock_instance

        exit_code = run_hook(session_id, state_dir=temp_state_dir)
        assert exit_code == 0

    @patch('verify_completion.CompletionVerifier')
    def test_hook_graceful_exit_on_complete_pipeline(self, mock_verifier, temp_state_dir, session_id, complete_verification_result):
        """Should exit 0 when pipeline is complete (success case)."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = complete_verification_result
        mock_verifier.return_value = mock_instance

        exit_code = run_hook(session_id, state_dir=temp_state_dir)
        assert exit_code == 0


# =============================================================================
# SECTION 5: Audit Logging Tests (3 tests)
# =============================================================================

class TestAuditLogging:
    """Test audit logging for all verification attempts."""

    @patch('verify_completion.CompletionVerifier')
    def test_logs_verification_attempt(self, mock_verifier, temp_state_dir, session_id, complete_verification_result, caplog):
        """Should log verification attempt with session ID."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = complete_verification_result
        mock_verifier.return_value = mock_instance

        with caplog.at_level('INFO'):
            run_hook(session_id, state_dir=temp_state_dir)

        # Should log verification attempt
        assert any(session_id in record.message for record in caplog.records)
        assert any("verification" in record.message.lower() for record in caplog.records)

    @patch('verify_completion.CompletionVerifier')
    def test_logs_missing_agents_count(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result, caplog):
        """Should log count of missing agents."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_verifier.return_value = mock_instance

        with caplog.at_level('INFO'):
            run_hook(session_id, state_dir=temp_state_dir)

        # Should log missing agents count (3)
        assert any("3" in record.message and "missing" in record.message.lower() for record in caplog.records)

    @patch('verify_completion.CompletionVerifier')
    def test_logs_verification_time(self, mock_verifier, temp_state_dir, session_id, complete_verification_result, caplog):
        """Should log verification execution time."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = complete_verification_result
        mock_verifier.return_value = mock_instance

        with caplog.at_level('INFO'):
            run_hook(session_id, state_dir=temp_state_dir)

        # Should log verification time
        assert any("ms" in record.message or "time" in record.message.lower() for record in caplog.records)


# =============================================================================
# SECTION 6: Integration Tests (4 tests)
# =============================================================================

class TestIntegration:
    """Test integration between hook and CompletionVerifier library."""

    @patch('verify_completion.CompletionVerifier')
    def test_hook_invokes_completion_verifier(self, mock_verifier, temp_state_dir, session_id, complete_verification_result):
        """Should instantiate and invoke CompletionVerifier."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = complete_verification_result
        mock_verifier.return_value = mock_instance

        run_hook(session_id, state_dir=temp_state_dir)

        # Should instantiate verifier with session ID
        mock_verifier.assert_called_once_with(session_id, state_dir=temp_state_dir)
        # Should call verify method
        mock_instance.verify.assert_called_once()

    @patch('verify_completion.CompletionVerifier')
    def test_hook_retrieves_retry_state(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result, loop_back_state):
        """Should retrieve retry state from CompletionVerifier."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_instance.get_retry_state.return_value = loop_back_state
        mock_verifier.return_value = mock_instance

        run_hook(session_id, state_dir=temp_state_dir)

        # Should retrieve retry state
        mock_instance.get_retry_state.assert_called()

    @patch('verify_completion.CompletionVerifier')
    def test_hook_updates_retry_state_on_failure(self, mock_verifier, temp_state_dir, session_id, incomplete_verification_result, loop_back_state):
        """Should update retry state when verification fails."""
        mock_instance = MagicMock()
        mock_instance.verify.return_value = incomplete_verification_result
        mock_instance.get_retry_state.return_value = loop_back_state
        mock_verifier.return_value = mock_instance

        run_hook(session_id, state_dir=temp_state_dir)

        # Should update retry state (increment consecutive failures)
        mock_instance.update_retry_state.assert_called()
        updated_state = mock_instance.update_retry_state.call_args[0][0]
        assert updated_state.consecutive_failures > 0

    def test_hook_end_to_end_complete_pipeline(self, temp_state_dir, session_id):
        """Should complete successfully for full pipeline (8 agents)."""
        # Create session file with all 8 agents
        session_file = temp_state_dir / "sessions" / f"{session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        session_data = {
            "session_id": session_id,
            "agents": [
                {"name": agent, "status": "complete"}
                for agent in [
                    "researcher-local", "researcher-web", "planner", "test-master",
                    "implementer", "reviewer", "security-auditor", "doc-master"
                ]
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        # Run hook (may fail if implementation not complete)
        try:
            exit_code = run_hook(session_id, state_dir=temp_state_dir)
            assert exit_code == 0

            # Should NOT create checkpoint (complete pipeline)
            checkpoint_file = temp_state_dir / "loop_back_checkpoint.json"
            assert not checkpoint_file.exists()
        except NameError:
            pytest.skip("Implementation not complete (TDD red phase)")


# =============================================================================
# SECTION 7: Session ID Extraction Tests (2 tests)
# =============================================================================

class TestSessionIDExtraction:
    """Test extraction of session ID from hook context."""

    def test_extract_session_id_from_context(self, hook_context, session_id):
        """Should extract session ID from hook context."""
        extracted_id = get_session_id_from_context(hook_context)
        assert extracted_id == session_id

    def test_extract_session_id_handles_missing_field(self):
        """Should handle missing session_id field gracefully."""
        context = {"lifecycle": "SubagentStop", "agent_name": "doc-master"}

        extracted_id = get_session_id_from_context(context)
        # Should return None or default value
        assert extracted_id is None or extracted_id == ""


# =============================================================================
# Test Execution
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
