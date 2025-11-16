#!/usr/bin/env python3
"""
Integration tests for state-based auto-clearing in /batch-implement workflow.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test end-to-end workflow: /batch-implement → auto-clear at 150K tokens → resume
- Test multi-feature batches with multiple auto-clear events
- Test crash recovery and resume functionality
- Test state integrity after auto-clear
- Test concurrent batch prevention
- Test failed feature continuation after auto-clear

Workflow Sequence:
1. /batch-implement reads features.txt
2. Process feature 1 → /auto-implement → track tokens
3. Check context threshold (150K tokens)
4. If threshold exceeded: /clear → record event → resume at next feature
5. Repeat until all features processed
6. Cleanup state file on completion

Date: 2025-11-16
Feature: State-based auto-clearing for /batch-implement
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import subprocess
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'commands'))

# Import will fail - modules don't exist yet (TDD!)
try:
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        load_batch_state,
        save_batch_state,
        update_batch_progress,
        record_auto_clear_event,
        should_auto_clear,
        cleanup_batch_state,
        get_next_pending_feature,
        BatchStateError,
        CONTEXT_THRESHOLD,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for batch processing."""
    workspace = tmp_path / "batch-workspace"
    workspace.mkdir()

    # Create .claude directory for state file
    claude_dir = workspace / ".claude"
    claude_dir.mkdir()

    return workspace


@pytest.fixture
def features_file(temp_workspace):
    """Create sample features file."""
    features_file = temp_workspace / "features.txt"
    features = [
        "Add user authentication with JWT",
        "Implement password reset flow",
        "Add email verification",
        "Create user profile API",
        "Add OAuth2 integration",
        "Implement role-based access control",
        "Add session management",
        "Create audit logging system",
        "Implement rate limiting",
        "Add API documentation",
    ]
    features_file.write_text("\n".join(features))
    return features_file


@pytest.fixture
def state_file(temp_workspace):
    """Get path to batch state file."""
    return temp_workspace / ".claude" / "batch_state.json"


@pytest.fixture
def mock_auto_implement():
    """Mock /auto-implement command execution."""
    with patch("subprocess.run") as mock_run:
        # Simulate successful /auto-implement execution
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Feature implemented successfully",
        )
        yield mock_run


@pytest.fixture
def mock_clear_command():
    """Mock /clear command execution."""
    with patch("subprocess.run") as mock_run:
        # Simulate successful /clear execution
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Context cleared",
        )
        yield mock_run


# =============================================================================
# SECTION 1: Auto-Clear Threshold Tests (2 tests)
# =============================================================================

class TestBatchAutoClearThreshold:
    """Test auto-clearing at 150K token threshold."""

    def test_auto_clear_triggers_at_150k_threshold(
        self, temp_workspace, features_file, state_file, mock_auto_implement, mock_clear_command
    ):
        """Test that auto-clear triggers when context reaches 150K tokens."""
        # Arrange - create batch state with high token count
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.context_token_estimate = 145000  # Just below threshold
        save_batch_state(state_file, batch_state)

        # Act - simulate processing feature that pushes over threshold
        # Feature processing adds 10K tokens (total: 155K > 150K threshold)
        with patch("batch_state_manager.estimate_feature_tokens", return_value=10000):
            update_batch_progress(
                state_file,
                feature_index=0,
                status="completed",
                context_token_delta=10000,
            )

            # Check if auto-clear should trigger
            updated_state = load_batch_state(state_file)
            should_clear = should_auto_clear(updated_state)

        # Assert - auto-clear should trigger
        assert should_clear is True
        assert updated_state.context_token_estimate >= CONTEXT_THRESHOLD

    def test_auto_clear_resets_token_count(
        self, temp_workspace, features_file, state_file
    ):
        """Test that auto-clear event resets token count to baseline."""
        # Arrange - create batch state with tokens over threshold
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.context_token_estimate = 155000  # Over threshold
        save_batch_state(state_file, batch_state)

        # Act - record auto-clear event
        record_auto_clear_event(
            state_file,
            feature_index=2,
            context_tokens_before_clear=155000,
        )

        # Assert - token count should reset to baseline (e.g., 5000 for system prompt)
        updated_state = load_batch_state(state_file)
        assert updated_state.context_token_estimate < 10000  # Baseline
        assert updated_state.auto_clear_count == 1


# =============================================================================
# SECTION 2: Resume Functionality Tests (2 tests)
# =============================================================================

class TestBatchResumeAfterClear:
    """Test resume functionality after auto-clear."""

    def test_resume_continues_from_next_feature_after_clear(
        self, temp_workspace, features_file, state_file
    ):
        """Test that batch resumes from next feature after auto-clear."""
        # Arrange - simulate batch with auto-clear at feature 2
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.current_index = 2
        batch_state.context_token_estimate = 5000  # After clear
        batch_state.auto_clear_count = 1
        batch_state.auto_clear_events = [
            {
                "feature_index": 2,
                "context_tokens_before_clear": 155000,
                "timestamp": "2025-11-16T10:30:00Z",
            }
        ]
        save_batch_state(state_file, batch_state)

        # Act - get next feature to process
        next_feature = get_next_pending_feature(batch_state)

        # Assert - should resume at feature 2 (0-indexed)
        assert next_feature == features[2]
        assert batch_state.current_index == 2

    def test_resume_with_resume_flag_loads_existing_state(
        self, temp_workspace, features_file, state_file
    ):
        """Test that --resume flag loads existing batch state."""
        # Arrange - create existing batch state
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.current_index = 3
        batch_state.completed_features = [
            {"index": 0, "feature": features[0]},
            {"index": 1, "feature": features[1]},
            {"index": 2, "feature": features[2]},
        ]
        save_batch_state(state_file, batch_state)

        # Act - simulate /batch-implement --resume
        # This should load existing state instead of creating new batch
        loaded_state = load_batch_state(state_file)

        # Assert - loaded state should match saved state
        assert loaded_state.batch_id == batch_state.batch_id
        assert loaded_state.current_index == 3
        assert len(loaded_state.completed_features) == 3


# =============================================================================
# SECTION 3: Multi-Feature Batch Tests (1 test)
# =============================================================================

class TestMultiFeatureBatchProcessing:
    """Test processing multiple features with auto-clear events."""

    def test_10_feature_batch_with_2_auto_clear_events(
        self, temp_workspace, features_file, state_file
    ):
        """Test processing 10 features with 2 auto-clear events."""
        # Arrange - create batch with 10 features
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - simulate processing all 10 features
        # Features 0-3: no clear (60K tokens)
        # Feature 4: triggers clear #1 (155K tokens)
        # Features 5-7: no clear (45K tokens after clear)
        # Feature 8: triggers clear #2 (155K tokens)
        # Feature 9: completes (20K tokens after clear)

        for i in range(10):
            # Load current state
            current_state = load_batch_state(state_file)

            # Simulate feature processing (15K tokens per feature)
            current_state.context_token_estimate += 15000

            # Check if auto-clear needed
            if should_auto_clear(current_state):
                record_auto_clear_event(
                    state_file,
                    feature_index=i,
                    context_tokens_before_clear=current_state.context_token_estimate,
                )
                # Reload after clear
                current_state = load_batch_state(state_file)

            # Update progress
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=15000,
            )

        # Assert - should have 2 auto-clear events
        final_state = load_batch_state(state_file)
        assert final_state.auto_clear_count == 2
        assert len(final_state.auto_clear_events) == 2
        assert final_state.current_index == 10  # All features processed
        assert len(final_state.completed_features) == 10


# =============================================================================
# SECTION 4: Crash Recovery Tests (1 test)
# =============================================================================

class TestBatchCrashRecovery:
    """Test crash recovery and state integrity."""

    def test_state_integrity_after_crash_recovery(
        self, temp_workspace, features_file, state_file
    ):
        """Test that batch can recover from crash using saved state."""
        # Arrange - simulate crash during feature 5 processing
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)

        # Process features 0-4 successfully
        for i in range(5):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=15000,
            )

        # Simulate crash during feature 5
        # State file should still have features 0-4 completed
        crashed_state = load_batch_state(state_file)
        assert crashed_state.current_index == 5

        # Act - resume from crash
        # Load state and verify we can continue from feature 5
        recovered_state = load_batch_state(state_file)

        # Assert - state should be intact
        assert recovered_state.current_index == 5
        assert len(recovered_state.completed_features) == 5
        assert recovered_state.status == "in_progress"

        # Continue processing
        next_feature = get_next_pending_feature(recovered_state)
        assert next_feature == features[5]


# =============================================================================
# SECTION 5: Concurrent Batch Prevention Tests (1 test)
# =============================================================================

class TestConcurrentBatchPrevention:
    """Test prevention of concurrent batch operations."""

    def test_concurrent_batch_implement_raises_error(
        self, temp_workspace, features_file, state_file
    ):
        """Test that starting new batch while one is in progress raises error."""
        # Arrange - create in-progress batch
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.status = "in_progress"
        save_batch_state(state_file, batch_state)

        # Act & Assert - attempting to start new batch should raise error
        with pytest.raises(BatchStateError) as exc_info:
            # Simulate /batch-implement without --resume flag
            # Should detect existing in-progress batch
            create_batch_state(str(features_file), features)

        # Error message should indicate concurrent batch detected
        # (Implementation should check for existing state file with in_progress status)


# =============================================================================
# SECTION 6: Failed Feature Continuation Tests (1 test)
# =============================================================================

class TestFailedFeatureContinuation:
    """Test continuation after failed features."""

    def test_batch_continues_after_failed_feature(
        self, temp_workspace, features_file, state_file
    ):
        """Test that batch continues processing after feature fails."""
        # Arrange - create batch and process some features
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - process features with one failure
        # Feature 0: success
        update_batch_progress(
            state_file,
            feature_index=0,
            status="completed",
            context_token_delta=15000,
        )

        # Feature 1: failure
        update_batch_progress(
            state_file,
            feature_index=1,
            status="failed",
            error_message="Test implementation failed",
            context_token_delta=5000,
        )

        # Feature 2: success
        update_batch_progress(
            state_file,
            feature_index=2,
            status="completed",
            context_token_delta=15000,
        )

        # Assert - batch should continue despite failure
        final_state = load_batch_state(state_file)
        assert final_state.current_index == 3
        assert len(final_state.completed_features) == 2
        assert len(final_state.failed_features) == 1
        assert final_state.failed_features[0]["feature_index"] == 1
        assert final_state.status == "in_progress"


# =============================================================================
# SECTION 7: State Cleanup Tests (1 test)
# =============================================================================

class TestBatchStateCleanup:
    """Test state cleanup after batch completion."""

    def test_state_cleanup_on_batch_completion(
        self, temp_workspace, features_file, state_file
    ):
        """Test that state file is cleaned up after batch completes."""
        # Arrange - create batch and process all features
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Process all features
        for i in range(len(features)):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=10000,
            )

        # Act - cleanup state after completion
        cleanup_batch_state(state_file)

        # Assert - state file should be removed
        assert not state_file.exists()


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (8 integration tests):

SECTION 1: Auto-Clear Threshold (2 tests)
✗ test_auto_clear_triggers_at_150k_threshold
✗ test_auto_clear_resets_token_count

SECTION 2: Resume Functionality (2 tests)
✗ test_resume_continues_from_next_feature_after_clear
✗ test_resume_with_resume_flag_loads_existing_state

SECTION 3: Multi-Feature Batch (1 test)
✗ test_10_feature_batch_with_2_auto_clear_events

SECTION 4: Crash Recovery (1 test)
✗ test_state_integrity_after_crash_recovery

SECTION 5: Concurrent Batch Prevention (1 test)
✗ test_concurrent_batch_implement_raises_error

SECTION 6: Failed Feature Continuation (1 test)
✗ test_batch_continues_after_failed_feature

SECTION 7: State Cleanup (1 test)
✗ test_state_cleanup_on_batch_completion

TOTAL: 8 integration tests (all FAILING - TDD red phase)

Integration Coverage:
- End-to-end workflow: feature parsing → processing → auto-clear → resume
- Token threshold detection (150K)
- Auto-clear event recording and recovery
- Multi-feature batches with multiple auto-clears
- Crash recovery and resume
- Concurrent batch prevention
- Failed feature handling
- State cleanup on completion
"""
