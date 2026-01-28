"""
End-to-End Integration Tests for Batch Auto-Compact Resume (Issue #277)

Tests complete batch workflow with auto-compact → checkpoint → SessionStart hook → resume.
This validates the full integration of RALPH checkpoints with Claude's auto-compact lifecycle.

Test Scenario:
1. Start batch with 10 features
2. Process features until context threshold (185K tokens)
3. Trigger auto-compact (checkpoint created beforehand)
4. SessionStart hook fires after compact
5. Batch resumes from checkpoint at correct feature
6. Complete remaining features

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially - integration doesn't exist yet

Date: 2026-01-28
Issue: #277 (Integrate RALPH checkpoint with Claude auto-compact lifecycle)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call, mock_open

import pytest

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import modules
try:
    from ralph_loop_manager import RalphLoopManager
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        load_batch_state,
        save_batch_state,
        should_auto_clear,
        record_auto_clear_event,
        get_next_pending_feature,
    )
except ImportError as e:
    pytest.skip(f"Required modules not found: {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace with all necessary directories."""
    workspace = tmp_path / "batch-auto-compact-workspace"
    workspace.mkdir()

    # Create subdirectories
    (workspace / ".ralph-checkpoints").mkdir()
    (workspace / ".claude").mkdir()
    (workspace / "features").mkdir()

    return workspace


@pytest.fixture
def batch_id():
    """Sample batch ID for testing."""
    return "batch-20260128-autocompact"


@pytest.fixture
def features_file(temp_workspace):
    """Create features file with 10 features."""
    features_file = temp_workspace / "features" / "batch_features.txt"
    features_content = """Feature 1: Add user authentication
Feature 2: Implement API endpoints
Feature 3: Add database migration
Feature 4: Write integration tests
Feature 5: Update documentation
Feature 6: Add error handling
Feature 7: Implement caching layer
Feature 8: Add monitoring and alerts
Feature 9: Performance optimization
Feature 10: Security audit and fixes"""
    features_file.write_text(features_content)
    return features_file


@pytest.fixture
def sessionstart_hook_path():
    """Path to SessionStart-batch-recovery.sh hook."""
    return project_root / "plugins" / "autonomous-dev" / "hooks" / "SessionStart-batch-recovery.sh"


@pytest.fixture
def batch_resume_helper_path():
    """Path to batch_resume_helper.py script."""
    return project_root / "plugins" / "autonomous-dev" / "lib" / "batch_resume_helper.py"


# =============================================================================
# Helper Functions
# =============================================================================

def simulate_feature_execution(feature_description: str, tokens_per_feature: int = 25000) -> tuple:
    """
    Simulate feature execution with token consumption.

    Args:
        feature_description: Feature to process
        tokens_per_feature: Tokens consumed per feature (default: 25K)

    Returns:
        tuple: (success, tokens_used, error_message)
    """
    # Extract feature number
    feature_num = int(feature_description.split(":")[0].split()[-1])

    # Simulate processing time
    time.sleep(0.01)

    return (True, tokens_per_feature, None)


def trigger_sessionstart_hook(
    hook_path: Path,
    workspace: Path,
    batch_id: str,
    checkpoint_dir: Path
) -> subprocess.CompletedProcess:
    """
    Trigger SessionStart hook with auto-compact event.

    Args:
        hook_path: Path to SessionStart-batch-recovery.sh
        workspace: Workspace directory
        batch_id: Batch ID
        checkpoint_dir: Checkpoint directory

    Returns:
        subprocess.CompletedProcess with hook output
    """
    # Create hook input JSON (simulating auto-compact event)
    hook_input = {
        "source": "compact",  # Key trigger for SessionStart hook
        "timestamp": "2026-01-28T15:00:00Z"
    }

    env = os.environ.copy()
    env["CHECKPOINT_DIR"] = str(checkpoint_dir)

    # Invoke hook
    result = subprocess.run(
        ["bash", str(hook_path)],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        env=env,
        cwd=workspace,
        timeout=10
    )

    return result


# =============================================================================
# End-to-End Integration Test
# =============================================================================

class TestBatchAutoCompactResume:
    """Test full batch workflow with auto-compact and resume."""

    def test_full_batch_with_auto_compact_and_resume(
        self,
        temp_workspace,
        features_file,
        batch_id,
        sessionstart_hook_path,
        batch_resume_helper_path
    ):
        """
        Test complete batch processing with auto-compact → checkpoint → resume.

        Workflow:
        1. Create batch with 10 features
        2. Process features 1-3 (75K tokens)
        3. Feature 4 triggers auto-compact (100K tokens → exceeds 185K threshold with overhead)
        4. Checkpoint created before auto-compact
        5. SessionStart hook fires after compact
        6. Hook displays batch context and next feature
        7. Batch resumes at feature 4
        8. Complete features 4-10

        Validates:
        - Checkpoint creation before auto-compact
        - SessionStart hook detects checkpoint
        - Hook displays correct batch context
        - Batch resumes at correct feature index
        - All 10 features completed
        """
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"
        checkpoint_dir = temp_workspace / ".ralph-checkpoints"

        # Create batch
        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        # Create RALPH manager
        ralph_manager = RalphLoopManager(f"ralph-{batch_id}", state_dir=checkpoint_dir)

        # PHASE 1: Process features 1-3 until auto-compact threshold
        tokens_per_feature = 25000  # 25K tokens per feature
        auto_compact_triggered = False

        for i in range(10):  # Process all features with auto-compact
            feature = features[i]

            # Execute feature
            success, tokens_used, error = simulate_feature_execution(feature, tokens_per_feature)

            ralph_manager.record_attempt(tokens_used=tokens_used)
            ralph_manager.record_success()

            # Update batch state
            batch_state = load_batch_state(batch_state_file)
            batch_state.completed_features.append(i)
            batch_state.current_index = i + 1
            batch_state.context_token_estimate += tokens_used
            save_batch_state(batch_state_file, batch_state)

            # Check if auto-compact needed (185K threshold)
            if should_auto_clear(batch_state):
                # PHASE 2: Checkpoint BEFORE auto-compact
                ralph_manager.checkpoint(batch_state=batch_state)

                # Verify checkpoint exists
                checkpoint_file = checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
                assert checkpoint_file.exists(), "Checkpoint not created before auto-compact"

                # Verify checkpoint has correct current_index
                checkpoint_data = json.loads(checkpoint_file.read_text())
                assert checkpoint_data["current_feature_index"] == i + 1

                # Record auto-clear event
                record_auto_clear_event(batch_state_file, i, batch_state.context_token_estimate)

                # Simulate auto-compact (context cleared)
                batch_state = load_batch_state(batch_state_file)
                batch_state.context_token_estimate = 0
                save_batch_state(batch_state_file, batch_state)

                auto_compact_triggered = True

                # PHASE 3: Trigger SessionStart hook (simulating post-compact)
                hook_result = trigger_sessionstart_hook(
                    sessionstart_hook_path,
                    temp_workspace,
                    batch_id,
                    checkpoint_dir
                )

                # Verify hook fired successfully
                assert hook_result.returncode == 0, f"SessionStart hook failed: {hook_result.stderr}"

                # Verify hook output contains batch context
                hook_output = hook_result.stdout
                assert "BATCH PROCESSING RESUMED" in hook_output
                assert batch_id in hook_output
                assert f"Feature {i + 2} of {len(features)}" in hook_output  # Next feature

                # PHASE 4: Resume from checkpoint
                resumed_manager = RalphLoopManager.resume_batch(batch_id, state_dir=checkpoint_dir)
                resumed_batch_state = resumed_manager.get_batch_state()

                # Verify resumed at correct feature
                assert resumed_batch_state.current_index == i + 1
                assert len(resumed_batch_state.completed_features) == i + 1

                # Continue with resumed manager
                ralph_manager = resumed_manager
                break

        # Assert auto-compact was triggered
        assert auto_compact_triggered is True, "Auto-compact threshold never reached"

        # PHASE 5: Complete remaining features after resume
        final_state = load_batch_state(batch_state_file)
        for i in range(final_state.current_index, len(features)):
            feature = features[i]
            success, tokens_used, error = simulate_feature_execution(feature, tokens_per_feature)

            ralph_manager.record_attempt(tokens_used=tokens_used)
            ralph_manager.record_success()

            final_state.completed_features.append(i)
            final_state.current_index = i + 1
            save_batch_state(batch_state_file, final_state)

        # Final assertions
        final_state = load_batch_state(batch_state_file)
        assert len(final_state.completed_features) == 10, "Not all features completed"
        assert final_state.completed_features == list(range(10))
        assert final_state.current_index == 10

    def test_sessionstart_hook_invokes_batch_resume_helper(
        self,
        temp_workspace,
        features_file,
        batch_id,
        sessionstart_hook_path,
        batch_resume_helper_path
    ):
        """
        Test SessionStart hook invokes batch_resume_helper.py to load checkpoint.

        Validates:
        - Hook calls Python helper with batch_id
        - Helper returns JSON checkpoint data
        - Hook parses JSON and displays context
        """
        # Arrange - create checkpoint
        checkpoint_dir = temp_workspace / ".ralph-checkpoints"
        features = features_file.read_text().strip().split("\n")

        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 3,
            "completed_features": [0, 1, 2],
            "failed_features": [],
            "skipped_features": [],
            "total_features": len(features),
            "features": features,
        }
        checkpoint_file = checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o600)

        # Create batch state
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"
        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        batch_state.current_index = 3
        batch_state.completed_features = [0, 1, 2]
        batch_state.status = "in_progress"
        save_batch_state(batch_state_file, batch_state)

        # Act - trigger SessionStart hook
        hook_result = trigger_sessionstart_hook(
            sessionstart_hook_path,
            temp_workspace,
            batch_id,
            checkpoint_dir
        )

        # Assert - hook invoked successfully
        assert hook_result.returncode == 0

        # Verify hook output includes checkpoint data
        hook_output = hook_result.stdout
        assert batch_id in hook_output
        assert "Feature 4 of 10" in hook_output  # Next feature (current_index=3 → feature 4)
        assert "BATCH PROCESSING RESUMED" in hook_output

    def test_auto_compact_preserves_batch_workflow(
        self,
        temp_workspace,
        features_file,
        batch_id
    ):
        """
        Test that auto-compact doesn't lose batch state or workflow methodology.

        Validates:
        - Batch state persists across auto-compact
        - RALPH checkpoint captures current progress
        - Workflow methodology reminder included
        - Next feature can be determined after resume
        """
        # Arrange
        features = features_file.read_text().strip().split("\n")
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"
        checkpoint_dir = temp_workspace / ".ralph-checkpoints"

        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        ralph_manager = RalphLoopManager(f"ralph-{batch_id}", state_dir=checkpoint_dir)

        # Process 5 features
        for i in range(5):
            success, tokens_used, _ = simulate_feature_execution(features[i])
            ralph_manager.record_attempt(tokens_used=tokens_used)
            ralph_manager.record_success()

            batch_state.completed_features.append(i)
            batch_state.current_index = i + 1
            batch_state.context_token_estimate += tokens_used
            save_batch_state(batch_state_file, batch_state)

        # Trigger checkpoint before auto-compact
        ralph_manager.checkpoint(batch_state=batch_state)

        # Simulate auto-compact
        record_auto_clear_event(batch_state_file, 4, batch_state.context_token_estimate)
        batch_state = load_batch_state(batch_state_file)
        batch_state.context_token_estimate = 0
        save_batch_state(batch_state_file, batch_state)

        # Act - resume from checkpoint
        resumed_manager = RalphLoopManager.resume_batch(batch_id, state_dir=checkpoint_dir)
        resumed_batch_state = resumed_manager.get_batch_state()

        # Assert - batch state preserved
        assert resumed_batch_state.batch_id == batch_id
        assert resumed_batch_state.current_index == 5
        assert len(resumed_batch_state.completed_features) == 5
        assert resumed_batch_state.total_features == 10

        # Verify workflow methodology preserved
        assert resumed_batch_state.workflow_mode == "auto-implement"
        assert "Use /implement" in resumed_batch_state.workflow_reminder

        # Verify next feature can be determined
        next_feature = get_next_pending_feature(resumed_batch_state)
        assert next_feature == features[5]  # Feature 6


# =============================================================================
# SessionStart Hook Integration Tests
# =============================================================================

class TestSessionStartHookIntegration:
    """Test SessionStart hook behavior with batch checkpoints."""

    def test_hook_displays_correct_feature_index(
        self,
        temp_workspace,
        batch_id,
        sessionstart_hook_path
    ):
        """
        Test SessionStart hook displays correct next feature index.

        Validates Issue #277 requirement:
        - Hook reads checkpoint
        - Displays "Resume at Feature X of Y"
        - X = current_feature_index + 1 (human-readable, 1-indexed)
        """
        # Arrange
        checkpoint_dir = temp_workspace / ".ralph-checkpoints"
        features = [f"Feature {i}: Task {i}" for i in range(1, 11)]

        checkpoint_data = {
            "session_id": f"ralph-{batch_id}",
            "batch_id": batch_id,
            "current_feature_index": 6,  # Completed 1-6, next is 7
            "completed_features": [0, 1, 2, 3, 4, 5],
            "failed_features": [],
            "skipped_features": [],
            "total_features": 10,
            "features": features,
        }
        checkpoint_file = checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"
        checkpoint_dir.mkdir(exist_ok=True)
        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        checkpoint_file.chmod(0o600)

        # Create batch state
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"
        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        batch_state.current_index = 6
        batch_state.status = "in_progress"
        save_batch_state(batch_state_file, batch_state)

        # Act
        hook_result = trigger_sessionstart_hook(
            sessionstart_hook_path,
            temp_workspace,
            batch_id,
            checkpoint_dir
        )

        # Assert
        assert hook_result.returncode == 0
        hook_output = hook_result.stdout

        # Verify feature index display (7 of 10)
        assert "Feature 7 of 10" in hook_output

    def test_hook_does_not_fire_on_normal_session_start(
        self,
        temp_workspace,
        batch_id,
        sessionstart_hook_path
    ):
        """
        Test SessionStart hook does NOT fire on normal session start (only after compact).

        Validates:
        - Hook checks source == "compact"
        - Normal session start (source != "compact") → no output
        """
        # Arrange
        checkpoint_dir = temp_workspace / ".ralph-checkpoints"

        # Create hook input for normal session start
        hook_input = {
            "source": "normal",  # NOT "compact"
            "timestamp": "2026-01-28T15:00:00Z"
        }

        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(checkpoint_dir)

        # Act
        result = subprocess.run(
            ["bash", str(sessionstart_hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=temp_workspace,
            timeout=10
        )

        # Assert - hook exits without output
        assert result.returncode == 0
        assert result.stdout.strip() == "" or "BATCH" not in result.stdout

    def test_hook_does_not_fire_if_no_batch_in_progress(
        self,
        temp_workspace,
        batch_id,
        sessionstart_hook_path
    ):
        """
        Test SessionStart hook does NOT fire if no batch is in progress.

        Validates:
        - Checks batch_state.json status
        - If status != "in_progress" → no output
        - If no batch_state.json → no output
        """
        # Arrange - no batch state file
        checkpoint_dir = temp_workspace / ".ralph-checkpoints"

        hook_input = {
            "source": "compact",
            "timestamp": "2026-01-28T15:00:00Z"
        }

        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(checkpoint_dir)

        # Act
        result = subprocess.run(
            ["bash", str(sessionstart_hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=temp_workspace,
            timeout=10
        )

        # Assert - hook exits without batch resumption output
        assert result.returncode == 0
        assert "BATCH PROCESSING RESUMED" not in result.stdout


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (6 end-to-end integration tests for Batch Auto-Compact Resume):

TestBatchAutoCompactResume (3 tests)
✗ test_full_batch_with_auto_compact_and_resume
✗ test_sessionstart_hook_invokes_batch_resume_helper
✗ test_auto_compact_preserves_batch_workflow

TestSessionStartHookIntegration (3 tests)
✗ test_hook_displays_correct_feature_index
✗ test_hook_does_not_fire_on_normal_session_start
✗ test_hook_does_not_fire_if_no_batch_in_progress

Expected Status: ALL TESTS FAILING (RED phase - integration not implemented yet)
Next Steps:
1. Implement batch_resume_helper.py (Python checkpoint loader)
2. Enhance SessionStart-batch-recovery.sh (invoke helper, display context)
3. Verify checkpoint_callback in should_auto_clear() (batch_state_manager.py line 1086)

Coverage Target: 80%+ for batch auto-compact → resume workflow
Integration Points:
- batch_resume_helper.py: load_checkpoint()
- SessionStart-batch-recovery.sh: Lines 18-21, 35-50
- batch_state_manager.py: should_auto_clear(checkpoint_callback=...)
- RalphLoopManager: checkpoint(), resume_batch()
"""
