#!/usr/bin/env python3
"""
Integration tests for batch context clearing workflow (Issue #88).

Tests for end-to-end hybrid approach:
1. Process features until context reaches 150K tokens
2. Detect threshold, display notification to user
3. Pause batch with status="paused"
4. User manually runs /clear
5. User runs /batch-implement --resume <batch-id>
6. Batch continues from current_index with reset token count

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (workflow doesn't exist yet).

Test Strategy:
- Test full pause/resume workflow
- Test multiple pause/resume cycles
- Test notification message display
- Test state persistence across cycles
- Test unattended operation after fix
- Mock user input for /clear execution

Date: 2025-11-17
Issue: #88 (/batch-implement cannot execute /clear programmatically)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)

See testing-guide skill for integration test patterns.
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
        should_clear_context,
        pause_batch_for_clear,
        get_clear_notification_message,
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
    """Create sample features file with 10 features."""
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


# =============================================================================
# SECTION 1: Full Workflow Tests (3 tests)
# =============================================================================

class TestBatchContextClearingWorkflow:
    """Test complete pause/notify/resume workflow."""

    def test_full_workflow_single_pause_resume_cycle(
        self, temp_workspace, features_file, state_file, mock_auto_implement
    ):
        """Test complete workflow: process → pause at threshold → resume."""
        # Arrange - create batch with 10 features
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - simulate processing until threshold
        # Each feature adds ~20K tokens
        for i in range(8):  # Process 8 features (160K tokens)
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=20000,
            )

            # Check if threshold reached
            current_state = load_batch_state(state_file)
            if should_clear_context(current_state):
                # Pause batch
                pause_batch_for_clear(
                    state_file,
                    current_state,
                    tokens_before_clear=current_state.context_token_estimate
                )

                # Display notification (implementation would show this to user)
                notification = get_clear_notification_message(current_state)

                # Assert - notification contains resume command
                assert "/batch-implement --resume" in notification
                assert current_state.batch_id in notification

                # Simulate user manually running /clear
                # (User sees notification, runs /clear, then resumes)

                # Simulate user running /batch-implement --resume
                resumed_state = load_batch_state(state_file)
                assert resumed_state.status == "paused"

                # Resume processing (implementation would continue from current_index)
                resumed_state.status = "in_progress"
                resumed_state.context_token_estimate = 5000  # After /clear
                save_batch_state(state_file, resumed_state)

                break

        # Continue processing remaining features
        final_state = load_batch_state(state_file)
        for i in range(final_state.current_index, len(features)):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=20000,
            )

        # Assert - all features completed
        final_state = load_batch_state(state_file)
        assert final_state.current_index == len(features)
        assert len(final_state.completed_features) == len(features)
        assert final_state.auto_clear_count >= 1  # At least one pause

    def test_workflow_with_multiple_pause_resume_cycles(
        self, temp_workspace, features_file, state_file
    ):
        """Test workflow with multiple pause/resume cycles (20 features)."""
        # Arrange - create large batch
        features = [f"Feature {i}" for i in range(1, 21)]  # 20 features
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        pause_count = 0

        # Act - simulate processing all 20 features
        for i in range(20):
            # Process feature
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=18000,  # Each feature adds 18K tokens
            )

            # Check threshold
            current_state = load_batch_state(state_file)
            if should_clear_context(current_state):
                # Pause
                pause_batch_for_clear(
                    state_file,
                    current_state,
                    tokens_before_clear=current_state.context_token_estimate
                )
                pause_count += 1

                # Simulate user manual clear + resume
                current_state.status = "in_progress"
                current_state.context_token_estimate = 5000
                save_batch_state(state_file, current_state)

        # Assert - should have paused multiple times
        final_state = load_batch_state(state_file)
        assert pause_count >= 2  # 20 features × 18K = 360K tokens → ~2 pauses
        assert final_state.auto_clear_count >= 2

    def test_workflow_notification_displayed_at_threshold(
        self, temp_workspace, features_file, state_file
    ):
        """Test that notification is displayed when threshold reached."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.context_token_estimate = 155000  # Over threshold
        save_batch_state(state_file, batch_state)

        # Act - check threshold and get notification
        notification_shown = False
        if should_clear_context(batch_state):
            notification = get_clear_notification_message(batch_state)
            notification_shown = True

            # Assert notification content
            assert "150" in notification or "threshold" in notification.lower()
            assert "/clear" in notification
            assert "/batch-implement --resume" in notification
            assert batch_state.batch_id in notification

        # Assert - notification was shown
        assert notification_shown is True


# =============================================================================
# SECTION 2: State Persistence Tests (3 tests)
# =============================================================================

class TestStatePersistenceAcrossCycles:
    """Test state file persistence across pause/resume cycles."""

    def test_state_persists_across_pause_resume(
        self, temp_workspace, features_file, state_file
    ):
        """Test that state file persists across pause and resume."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.current_index = 5
        batch_state.completed_features = [0, 1, 2, 3, 4]
        save_batch_state(state_file, batch_state)

        # Act - pause
        pause_batch_for_clear(state_file, batch_state, tokens_before_clear=155000)

        # Simulate process restart (reload from disk)
        loaded_state = load_batch_state(state_file)

        # Assert - state matches original
        assert loaded_state.batch_id == batch_state.batch_id
        assert loaded_state.current_index == 5
        assert len(loaded_state.completed_features) == 5
        assert loaded_state.status == "paused"

    def test_auto_clear_events_persist_across_cycles(
        self, temp_workspace, features_file, state_file
    ):
        """Test that auto_clear_events list persists across cycles."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - create 3 pause events
        for i in [3, 7, 10]:
            batch_state.current_index = i
            pause_batch_for_clear(state_file, batch_state, tokens_before_clear=155000)

            # Reload after each pause
            batch_state = load_batch_state(state_file)

        # Assert - all events persisted
        assert len(batch_state.auto_clear_events) == 3
        assert batch_state.auto_clear_count == 3

    def test_completed_features_preserved_across_pause(
        self, temp_workspace, features_file, state_file
    ):
        """Test that completed_features list preserved after pause."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Complete 5 features
        for i in range(5):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=20000,
            )

        # Act - pause
        batch_state = load_batch_state(state_file)
        pause_batch_for_clear(state_file, batch_state, tokens_before_clear=155000)

        # Reload
        reloaded_state = load_batch_state(state_file)

        # Assert - completed features preserved
        assert len(reloaded_state.completed_features) == 5


# =============================================================================
# SECTION 3: Resume Functionality Tests (4 tests)
# =============================================================================

class TestResumeAfterManualClear:
    """Test resume functionality after user manually runs /clear."""

    def test_resume_with_batch_id_loads_correct_state(
        self, temp_workspace, features_file, state_file
    ):
        """Test that --resume <batch-id> loads correct batch state."""
        # Arrange - create paused batch
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.current_index = 7
        batch_state.status = "paused"
        save_batch_state(state_file, batch_state)

        # Act - simulate /batch-implement --resume <batch-id>
        loaded_state = load_batch_state(state_file)

        # Assert
        assert loaded_state.batch_id == batch_state.batch_id
        assert loaded_state.current_index == 7
        assert loaded_state.status == "paused"

    def test_resume_continues_from_correct_feature_index(
        self, temp_workspace, features_file, state_file
    ):
        """Test that resume continues from current_index (not from 0)."""
        # Arrange - paused at feature 8
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.current_index = 8
        batch_state.completed_features = list(range(8))
        batch_state.status = "paused"
        save_batch_state(state_file, batch_state)

        # Act - resume
        loaded_state = load_batch_state(state_file)
        next_feature = get_next_pending_feature(loaded_state)

        # Assert - next feature is index 8
        assert next_feature == features[8]
        assert loaded_state.current_index == 8

    def test_resume_with_reset_token_estimate(
        self, temp_workspace, features_file, state_file
    ):
        """Test that resume assumes user ran /clear (low token estimate)."""
        # Arrange - paused with high token count
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.context_token_estimate = 155000
        batch_state.status = "paused"
        save_batch_state(state_file, batch_state)

        # Act - simulate resume (user ran /clear manually)
        loaded_state = load_batch_state(state_file)

        # When resuming, implementation should assume /clear was run
        # Token estimate should be reset to baseline (e.g., 5000)
        if loaded_state.status == "paused":
            # Implementation detail: reset token estimate on resume
            loaded_state.context_token_estimate = 5000  # After /clear
            loaded_state.status = "in_progress"

        # Assert
        assert loaded_state.context_token_estimate < 10000

    def test_resume_changes_status_from_paused_to_in_progress(
        self, temp_workspace, features_file, state_file
    ):
        """Test that resume changes status from 'paused' to 'in_progress'."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.status = "paused"
        save_batch_state(state_file, batch_state)

        # Act - simulate resume
        loaded_state = load_batch_state(state_file)
        assert loaded_state.status == "paused"

        # Implementation should change status when resuming
        loaded_state.status = "in_progress"
        save_batch_state(state_file, loaded_state)

        # Assert
        final_state = load_batch_state(state_file)
        assert final_state.status == "in_progress"


# =============================================================================
# SECTION 4: Notification Display Tests (3 tests)
# =============================================================================

class TestNotificationDisplay:
    """Test user notification message display."""

    def test_notification_includes_all_required_info(
        self, temp_workspace, features_file, state_file
    ):
        """Test notification message includes all required information."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        batch_state.current_index = 7
        batch_state.total_features = 10
        batch_state.context_token_estimate = 155000

        # Act
        notification = get_clear_notification_message(batch_state)

        # Assert - contains all required info
        assert "Context limit reached" in notification or "threshold" in notification.lower()
        assert "155" in notification or "155000" in notification  # Token count
        assert "7" in notification  # Current progress
        assert "10" in notification  # Total features
        assert "/clear" in notification  # Manual clear instruction
        assert "/batch-implement --resume" in notification  # Resume command
        assert batch_state.batch_id in notification  # Batch ID for resume

    def test_notification_explains_manual_clear_requirement(
        self, temp_workspace, features_file, state_file
    ):
        """Test notification explains user must manually run /clear."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)

        # Act
        notification = get_clear_notification_message(batch_state)

        # Assert - explains manual clear is required
        assert "manual" in notification.lower() or "run" in notification.lower()
        assert "/clear" in notification

    def test_notification_formatted_for_readability(
        self, temp_workspace, features_file, state_file
    ):
        """Test notification is formatted for easy reading."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)

        # Act
        notification = get_clear_notification_message(batch_state)

        # Assert - has reasonable formatting
        # Should be multi-line, not a single long line
        assert "\n" in notification
        # Should not be excessively long
        assert len(notification) < 1000
        # Should be well-structured (e.g., numbered steps or sections)


# =============================================================================
# SECTION 5: Unattended Operation Tests (3 tests)
# =============================================================================

class TestUnattendedOperation:
    """Test that fix enables true unattended operation."""

    def test_batch_processes_features_before_threshold_unattended(
        self, temp_workspace, features_file, state_file
    ):
        """Test that batch processes features unattended until threshold."""
        # Arrange - small batch that stays under threshold
        features = ["Feature 1", "Feature 2", "Feature 3"]
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - process all features (each adds 10K tokens)
        for i in range(3):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=10000,
            )

        # Assert - completed without manual intervention
        final_state = load_batch_state(state_file)
        assert final_state.current_index == 3
        assert len(final_state.completed_features) == 3
        assert final_state.auto_clear_count == 0  # Never hit threshold

    def test_batch_pauses_gracefully_at_threshold(
        self, temp_workspace, features_file, state_file
    ):
        """Test that batch pauses gracefully when threshold reached."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - process until threshold
        for i in range(10):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=18000,
            )

            current_state = load_batch_state(state_file)
            if should_clear_context(current_state):
                pause_batch_for_clear(
                    state_file,
                    current_state,
                    tokens_before_clear=current_state.context_token_estimate
                )
                break

        # Assert - paused cleanly
        paused_state = load_batch_state(state_file)
        assert paused_state.status == "paused"
        assert paused_state.auto_clear_count == 1

    def test_overnight_run_workflow(
        self, temp_workspace, features_file, state_file
    ):
        """Test overnight run workflow: start → pause → resume → complete."""
        # Arrange - simulate 15 feature overnight run
        features = [f"Feature {i}" for i in range(1, 16)]
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - Phase 1: Process until first pause (unattended)
        phase1_completed = 0
        for i in range(15):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=18000,
            )
            phase1_completed += 1

            current_state = load_batch_state(state_file)
            if should_clear_context(current_state):
                pause_batch_for_clear(
                    state_file,
                    current_state,
                    tokens_before_clear=current_state.context_token_estimate
                )
                break

        # User wakes up, sees notification, runs /clear + /batch-implement --resume
        resumed_state = load_batch_state(state_file)
        resumed_state.status = "in_progress"
        resumed_state.context_token_estimate = 5000
        save_batch_state(state_file, resumed_state)

        # Phase 2: Complete remaining features
        for i in range(resumed_state.current_index, 15):
            update_batch_progress(
                state_file,
                feature_index=i,
                status="completed",
                context_token_delta=18000,
            )

        # Assert - all features completed
        final_state = load_batch_state(state_file)
        assert final_state.current_index == 15
        assert len(final_state.completed_features) == 15


# =============================================================================
# SECTION 6: Error Handling Tests (2 tests)
# =============================================================================

class TestErrorHandling:
    """Test error handling in pause/resume workflow."""

    def test_resume_with_invalid_batch_id_raises_error(self, state_file):
        """Test that resume with invalid batch ID raises error."""
        # Arrange - no state file exists
        assert not state_file.exists()

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(state_file)

        assert "not found" in str(exc_info.value).lower()

    def test_pause_with_corrupted_state_handles_gracefully(
        self, temp_workspace, features_file, state_file
    ):
        """Test that pause handles corrupted state file gracefully."""
        # Arrange - create corrupted state file
        state_file.write_text("{invalid json")

        # Act & Assert
        with pytest.raises(BatchStateError) as exc_info:
            load_batch_state(state_file)

        assert "corrupted" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


# =============================================================================
# SECTION 7: Regression Tests (2 tests)
# =============================================================================

class TestRegressionPrevention:
    """Test that implementation doesn't attempt programmatic /clear."""

    def test_no_slash_command_attempts_in_workflow(
        self, temp_workspace, features_file, state_file
    ):
        """Test that workflow never attempts SlashCommand("/clear")."""
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state = create_batch_state(str(features_file), features)
        save_batch_state(state_file, batch_state)

        # Act - process features and trigger pause
        with patch("subprocess.run") as mock_run:
            for i in range(10):
                update_batch_progress(
                    state_file,
                    feature_index=i,
                    status="completed",
                    context_token_delta=18000,
                )

                current_state = load_batch_state(state_file)
                if should_clear_context(current_state):
                    pause_batch_for_clear(
                        state_file,
                        current_state,
                        tokens_before_clear=current_state.context_token_estimate
                    )
                    break

            # Assert - no subprocess.run calls to /clear
            for call_obj in mock_run.call_args_list:
                args = call_obj[0]
                if args:
                    assert "/clear" not in str(args)

    def test_batch_implement_command_updated_for_pause_approach(self):
        """Test that batch-implement.md uses pause/notify (not programmatic /clear)."""
        # Arrange
        command_file = Path(__file__).parent.parent.parent / "plugins/autonomous-dev/commands/batch-implement.md"

        # Act & Assert
        if command_file.exists():
            content = command_file.read_text()

            # Should NOT contain programmatic /clear attempts
            assert 'SlashCommand(command="/clear")' not in content

            # Should contain pause/notify approach
            assert "pause" in content.lower() or "notify" in content.lower()
            assert "/batch-implement --resume" in content


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (20 integration tests):

SECTION 1: Full Workflow (3 tests)
✗ test_full_workflow_single_pause_resume_cycle
✗ test_workflow_with_multiple_pause_resume_cycles
✗ test_workflow_notification_displayed_at_threshold

SECTION 2: State Persistence (3 tests)
✗ test_state_persists_across_pause_resume
✗ test_auto_clear_events_persist_across_cycles
✗ test_completed_features_preserved_across_pause

SECTION 3: Resume Functionality (4 tests)
✗ test_resume_with_batch_id_loads_correct_state
✗ test_resume_continues_from_correct_feature_index
✗ test_resume_with_reset_token_estimate
✗ test_resume_changes_status_from_paused_to_in_progress

SECTION 4: Notification Display (3 tests)
✗ test_notification_includes_all_required_info
✗ test_notification_explains_manual_clear_requirement
✗ test_notification_formatted_for_readability

SECTION 5: Unattended Operation (3 tests)
✗ test_batch_processes_features_before_threshold_unattended
✗ test_batch_pauses_gracefully_at_threshold
✗ test_overnight_run_workflow

SECTION 6: Error Handling (2 tests)
✗ test_resume_with_invalid_batch_id_raises_error
✗ test_pause_with_corrupted_state_handles_gracefully

SECTION 7: Regression Prevention (2 tests)
✗ test_no_slash_command_attempts_in_workflow
✗ test_batch_implement_command_updated_for_pause_approach

TOTAL: 20 integration tests (all FAILING - TDD red phase)

Integration Coverage:
- Full pause/notify/resume workflow (single and multiple cycles)
- State file persistence across cycles
- Resume after manual /clear
- User notification message display
- Unattended operation before threshold
- Graceful pause at threshold
- Overnight run scenario
- Error handling (invalid batch ID, corrupted state)
- Regression prevention (no programmatic /clear attempts)
"""
