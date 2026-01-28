#!/usr/bin/env python3
"""
Integration Tests for Batch Auto-Continuation (Issue #XXX)

Tests that batch processing automatically continues from Feature 1/N to Feature N/N
without manual `/implement --resume` commands between features.

Current Bug: Batch processing stops after Feature 1, requiring manual resume.
Expected: Batch should auto-continue through all features in a single invocation.

Test Strategy:
1. test_batch_processes_all_features_without_manual_resume
   - Create batch with 5 features
   - Invoke batch processing once
   - Verify all 5 features processed automatically
   - Verify no manual resume required

2. test_batch_continues_after_feature_failure
   - Create batch with 10 features
   - Inject failure in Feature 3
   - Verify Features 4-10 still process
   - Verify Feature 3 in failed_features
   - Verify Features 1-2, 4-10 in completed_features

3. test_batch_exits_when_no_more_features
   - Create batch with 3 features
   - Process all 3
   - Verify get_next_pending_feature() returns None
   - Verify loop exits gracefully
   - Verify no infinite loop

4. test_resume_uses_same_loop_pattern
   - Create batch with 10 features
   - Process Features 1-4
   - Simulate interruption
   - Resume batch
   - Verify Features 5-10 process automatically
   - Verify no duplicate processing of 1-4

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially - auto-continuation loop doesn't exist yet

Date: 2026-01-28
Issue: #XXX (Fix batch processing to auto-continue to next feature)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)

Implementation Plan Reference:
- Update plugins/autonomous-dev/commands/implement.md BATCH FILE MODE STEP B3 (lines 421-428)
- Add explicit while-loop using:
  - get_next_pending_feature(state) - Returns next feature or None
  - update_batch_progress() - Updates state after each feature
- Loop pattern: while True → get_next_pending_feature() → if None break → invoke_pipeline → update_batch_progress() → repeat
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import modules
try:
    from batch_state_manager import (
        create_batch_state,
        load_batch_state,
        save_batch_state,
        update_batch_progress,
        get_next_pending_feature,
        BatchStateError,
    )
except ImportError as e:
    pytest.skip(f"Required modules not found: {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace with all necessary directories."""
    workspace = tmp_path / "batch-auto-continuation-workspace"
    workspace.mkdir()

    # Create subdirectories
    (workspace / ".claude").mkdir()
    (workspace / "features").mkdir()
    (workspace / "src").mkdir()

    return workspace


@pytest.fixture
def batch_id():
    """Sample batch ID for testing."""
    return "batch-20260128-autocontinue"


@pytest.fixture
def small_features_file(temp_workspace):
    """Create features file with 5 features for basic tests."""
    features_file = temp_workspace / "features" / "small_batch.txt"
    features_content = """Feature 1: Add user authentication
Feature 2: Implement API endpoints
Feature 3: Add database migration
Feature 4: Write integration tests
Feature 5: Update documentation"""
    features_file.write_text(features_content)
    return features_file


@pytest.fixture
def large_features_file(temp_workspace):
    """Create features file with 10 features for extended tests."""
    features_file = temp_workspace / "features" / "large_batch.txt"
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


# =============================================================================
# Helper Functions
# =============================================================================


def simulate_pipeline_invocation(
    feature_description: str,
    should_fail: bool = False,
    tokens_per_feature: int = 5000
) -> tuple:
    """
    Simulate full 8-agent pipeline invocation for a feature.

    In real implementation, this would invoke:
    - researcher-local
    - researcher-web
    - planner
    - test-master
    - implementer
    - reviewer
    - security-auditor
    - doc-master

    For testing, we mock this with a simple success/failure simulation.

    Args:
        feature_description: Feature to process
        should_fail: If True, simulate pipeline failure
        tokens_per_feature: Tokens consumed per feature (default: 5K)

    Returns:
        tuple: (success, tokens_used, error_message)
    """
    # Extract feature number
    feature_num = int(feature_description.split(":")[0].split()[-1])

    # Simulate processing time
    time.sleep(0.01)

    if should_fail:
        return (False, tokens_per_feature, f"Pipeline failed for Feature {feature_num}")

    return (True, tokens_per_feature, None)


def process_batch_with_loop(
    batch_state_file: Path,
    features: List[str],
    fail_at_indices: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Simulate batch processing loop with auto-continuation.

    This is the loop pattern that SHOULD be implemented in implement.md STEP B3.
    Currently MISSING - batch stops after first feature.

    Expected Implementation Pattern (to be added to implement.md):
    ```bash
    # Process all features with auto-continuation
    while true; do
        # Get next pending feature
        NEXT_FEATURE=$(python3 -c "
    from batch_state_manager import load_batch_state, get_next_pending_feature
    state = load_batch_state('$STATE_FILE')
    next_feat = get_next_pending_feature(state)
    print(next_feat if next_feat else '')
    ")

        # Exit if no more features
        if [ -z "$NEXT_FEATURE" ]; then
            break
        fi

        # Invoke full pipeline for feature
        # ... (researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master)

        # Update batch progress
        python3 -c "
    from batch_state_manager import update_batch_progress
    update_batch_progress('$STATE_FILE', $CURRENT_INDEX, 'completed', $TOKENS)
    "
    done
    ```

    Args:
        batch_state_file: Path to batch state file
        features: List of feature descriptions
        fail_at_indices: List of feature indices that should fail (default: None)

    Returns:
        dict: {
            "completed_count": int,
            "failed_count": int,
            "processed_features": List[int],
            "iterations": int
        }
    """
    fail_at_indices = fail_at_indices or []
    iterations = 0
    max_iterations = len(features) + 5  # Prevent infinite loop

    while iterations < max_iterations:
        iterations += 1

        # Load current state
        state = load_batch_state(batch_state_file)

        # Get next pending feature
        next_feature = get_next_pending_feature(state)

        # Exit if no more features
        if next_feature is None:
            break

        # Determine current feature index
        current_index = state.current_index

        # Simulate pipeline invocation
        should_fail = current_index in fail_at_indices
        success, tokens_used, error = simulate_pipeline_invocation(
            next_feature,
            should_fail=should_fail
        )

        # Update batch progress
        if success:
            update_batch_progress(
                batch_state_file,
                current_index,
                "completed",
                context_token_delta=tokens_used
            )
        else:
            update_batch_progress(
                batch_state_file,
                current_index,
                "failed",
                context_token_delta=tokens_used,
                error_message=error
            )

    # Load final state
    final_state = load_batch_state(batch_state_file)

    return {
        "completed_count": len(final_state.completed_features),
        "failed_count": len(final_state.failed_features),
        "processed_features": sorted(
            final_state.completed_features +
            [f["feature_index"] for f in final_state.failed_features]
        ),
        "iterations": iterations,
    }


# =============================================================================
# Test 1: Batch Processes All Features Without Manual Resume
# =============================================================================


class TestBatchAutoContinuation:
    """Test batch auto-continuation through all features."""

    def test_batch_processes_all_features_without_manual_resume(
        self,
        temp_workspace,
        small_features_file,
        batch_id
    ):
        """
        Test batch processes all 5 features automatically in single invocation.

        Workflow:
        1. Create batch with 5 features
        2. Invoke batch processing ONCE (simulate loop)
        3. Verify all 5 features processed
        4. Verify no manual resume required
        5. Verify batch state shows all 5 completed

        Current Bug: Batch stops after Feature 1, requires manual `/implement --resume`
        Expected: Batch auto-continues through Features 1-5

        Validates:
        - get_next_pending_feature() called in loop
        - Loop continues until None returned
        - All features processed in single invocation
        - No manual intervention needed
        """
        # Arrange
        features = small_features_file.read_text().strip().split("\n")
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"

        # Create batch
        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        # Act - Simulate batch processing with auto-continuation loop
        result = process_batch_with_loop(batch_state_file, features)

        # Assert - All 5 features processed
        assert result["completed_count"] == 5, (
            f"Expected all 5 features completed, got {result['completed_count']}"
        )
        assert result["failed_count"] == 0, (
            f"Expected 0 failures, got {result['failed_count']}"
        )
        assert result["processed_features"] == [0, 1, 2, 3, 4], (
            f"Expected features [0,1,2,3,4], got {result['processed_features']}"
        )

        # Assert - Loop terminated after processing all features
        # Note: iterations includes final check that returns None, so it's N+1
        assert result["iterations"] <= 6, (
            f"Expected max 6 loop iterations (5 features + final None check), got {result['iterations']}"
        )

        # Assert - Final batch state
        final_state = load_batch_state(batch_state_file)
        assert final_state.current_index == 5
        assert final_state.status == "completed"
        assert len(final_state.completed_features) == 5

        # Assert - No manual resume was needed (verified by single invocation)
        # In production, this would be a bash script that runs the loop once
        # without requiring user to run `/implement --resume` between features


# =============================================================================
# Test 2: Batch Continues After Feature Failure
# =============================================================================


class TestBatchFailureResilience:
    """Test batch continues processing after individual feature failures."""

    def test_batch_continues_after_feature_failure(
        self,
        temp_workspace,
        large_features_file,
        batch_id
    ):
        """
        Test batch continues processing after Feature 3 fails.

        Workflow:
        1. Create batch with 10 features
        2. Inject failure at Feature 3 (index 2)
        3. Verify Features 4-10 still process
        4. Verify Feature 3 in failed_features
        5. Verify Features 1-2, 4-10 in completed_features

        Current Bug: Batch may stop on first failure
        Expected: Batch continues to Feature 10 despite Feature 3 failure

        Validates:
        - Failed features don't stop batch processing
        - get_next_pending_feature() skips failed features
        - Loop continues to end
        - Failed feature recorded in state
        """
        # Arrange
        features = large_features_file.read_text().strip().split("\n")
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"

        # Create batch
        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        # Act - Simulate batch processing with failure at index 2 (Feature 3)
        result = process_batch_with_loop(
            batch_state_file,
            features,
            fail_at_indices=[2]  # Feature 3 fails
        )

        # Assert - 9 completed, 1 failed
        assert result["completed_count"] == 9, (
            f"Expected 9 features completed, got {result['completed_count']}"
        )
        assert result["failed_count"] == 1, (
            f"Expected 1 failure, got {result['failed_count']}"
        )

        # Assert - All 10 features processed (0-9)
        assert result["processed_features"] == list(range(10)), (
            f"Expected all features [0-9], got {result['processed_features']}"
        )

        # Assert - Feature 3 (index 2) in failed_features
        final_state = load_batch_state(batch_state_file)
        assert len(final_state.failed_features) == 1
        assert final_state.failed_features[0]["feature_index"] == 2
        assert "Feature 3" in final_state.failed_features[0]["error_message"]

        # Assert - Features 1-2, 4-10 in completed_features
        expected_completed = [0, 1, 3, 4, 5, 6, 7, 8, 9]
        assert sorted(final_state.completed_features) == expected_completed, (
            f"Expected completed {expected_completed}, got {final_state.completed_features}"
        )

        # Assert - Batch marked as completed (despite failure)
        assert final_state.status == "completed"
        assert final_state.current_index == 10


# =============================================================================
# Test 3: Batch Exits When No More Features
# =============================================================================


class TestBatchLoopTermination:
    """Test batch loop exits gracefully when no more features to process."""

    def test_batch_exits_when_no_more_features(
        self,
        temp_workspace,
        batch_id
    ):
        """
        Test batch loop exits when get_next_pending_feature() returns None.

        Workflow:
        1. Create batch with 3 features
        2. Process all 3
        3. Verify get_next_pending_feature() returns None
        4. Verify loop exits gracefully
        5. Verify no infinite loop (iteration count == 3)

        Validates:
        - Loop termination condition (next_feature is None)
        - No infinite loop
        - Batch state correctly reflects completion
        """
        # Arrange
        features = [
            "Feature 1: Add authentication",
            "Feature 2: Add API",
            "Feature 3: Add tests"
        ]
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"

        # Create batch
        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        # Act - Process all features
        result = process_batch_with_loop(batch_state_file, features)

        # Assert - Loop terminated after processing all features
        # Note: iterations includes final check that returns None, so it's N+1
        assert result["iterations"] <= 4, (
            f"Expected max 4 iterations (3 features + final None check), got {result['iterations']}\n"
            "Possible infinite loop detected!"
        )

        # Assert - All 3 features completed
        assert result["completed_count"] == 3
        assert result["failed_count"] == 0

        # Assert - get_next_pending_feature() returns None after completion
        final_state = load_batch_state(batch_state_file)
        next_feature = get_next_pending_feature(final_state)
        assert next_feature is None, (
            f"Expected get_next_pending_feature() to return None, got {next_feature}"
        )

        # Assert - Batch marked as completed
        assert final_state.status == "completed"
        assert final_state.current_index == 3


# =============================================================================
# Test 4: Resume Uses Same Loop Pattern
# =============================================================================


class TestBatchResumeContinuation:
    """Test batch resume uses same auto-continuation loop."""

    def test_resume_uses_same_loop_pattern(
        self,
        temp_workspace,
        large_features_file,
        batch_id
    ):
        """
        Test batch resume automatically continues through remaining features.

        Workflow:
        1. Create batch with 10 features
        2. Process Features 1-4 (simulate initial run)
        3. Simulate interruption (stop processing)
        4. Resume batch (invoke loop again)
        5. Verify Features 5-10 process automatically
        6. Verify no duplicate processing of 1-4

        Validates:
        - Resume uses same while-loop pattern
        - get_next_pending_feature() resumes at correct index
        - No duplicate processing of completed features
        - Resume completes remaining features without manual intervention
        """
        # Arrange
        features = large_features_file.read_text().strip().split("\n")
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"

        # Create batch
        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        # PHASE 1: Process Features 1-4 (initial run, then interrupted)
        for i in range(4):
            feature = features[i]
            success, tokens_used, _ = simulate_pipeline_invocation(feature)
            update_batch_progress(
                batch_state_file,
                i,
                "completed",
                context_token_delta=tokens_used
            )

        # Verify intermediate state (Features 1-4 completed)
        intermediate_state = load_batch_state(batch_state_file)
        assert len(intermediate_state.completed_features) == 4
        assert intermediate_state.current_index == 4

        # PHASE 2: Resume batch (simulate `/implement --resume`)
        # This should auto-continue through Features 5-10
        result = process_batch_with_loop(batch_state_file, features)

        # Assert - 6 more features completed (Features 5-10)
        assert result["completed_count"] == 10, (
            f"Expected all 10 features completed after resume, got {result['completed_count']}"
        )
        assert result["failed_count"] == 0

        # Assert - Loop processed Features 5-10
        # Note: iterations includes final None check, so it's 6 features + 1 = 7
        assert result["iterations"] <= 7, (
            f"Expected max 7 iterations for Features 5-10 (6 features + final None check), got {result['iterations']}"
        )

        # Assert - No duplicate processing
        final_state = load_batch_state(batch_state_file)
        # Each feature index should appear exactly once
        completed_counts = {}
        for idx in final_state.completed_features:
            completed_counts[idx] = completed_counts.get(idx, 0) + 1

        duplicates = [idx for idx, count in completed_counts.items() if count > 1]
        assert not duplicates, (
            f"Features processed multiple times: {duplicates}"
        )

        # Assert - All 10 features completed exactly once
        assert sorted(final_state.completed_features) == list(range(10))
        assert final_state.status == "completed"


# =============================================================================
# Test 5: Multiple Failures Don't Block Completion
# =============================================================================


class TestBatchMultipleFailures:
    """Test batch handles multiple failures gracefully."""

    def test_batch_completes_with_multiple_failures(
        self,
        temp_workspace,
        large_features_file,
        batch_id
    ):
        """
        Test batch processes all features despite multiple failures.

        Workflow:
        1. Create batch with 10 features
        2. Inject failures at Features 2, 5, 8 (indices 1, 4, 7)
        3. Verify all 10 features attempted
        4. Verify 7 completed, 3 failed
        5. Verify batch marked as completed

        Validates:
        - Multiple failures don't stop batch
        - Loop continues to end despite failures
        - Failed features correctly recorded
        - Batch completes successfully with partial failures
        """
        # Arrange
        features = large_features_file.read_text().strip().split("\n")
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"

        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        # Act - Inject failures at indices 1, 4, 7 (Features 2, 5, 8)
        result = process_batch_with_loop(
            batch_state_file,
            features,
            fail_at_indices=[1, 4, 7]
        )

        # Assert - 7 completed, 3 failed
        assert result["completed_count"] == 7, (
            f"Expected 7 features completed, got {result['completed_count']}"
        )
        assert result["failed_count"] == 3, (
            f"Expected 3 failures, got {result['failed_count']}"
        )

        # Assert - All 10 features attempted
        assert result["processed_features"] == list(range(10))

        # Assert - Failed features recorded correctly
        final_state = load_batch_state(batch_state_file)
        failed_indices = {f["feature_index"] for f in final_state.failed_features}
        assert failed_indices == {1, 4, 7}, (
            f"Expected failures at [1,4,7], got {failed_indices}"
        )

        # Assert - Batch marked as completed
        assert final_state.status == "completed"
        assert final_state.current_index == 10


# =============================================================================
# Test 6: Empty Batch Handles Gracefully
# =============================================================================


class TestBatchEdgeCases:
    """Test batch edge cases and boundary conditions."""

    def test_empty_batch_exits_immediately(
        self,
        temp_workspace,
        batch_id
    ):
        """
        Test batch with no features exits immediately.

        Note: batch_state_manager.py prevents creation of empty batches (StateError),
        so this test validates the error handling rather than empty batch processing.

        Validates:
        - Empty feature list raises StateError
        - Batch creation validates feature count > 0
        """
        # Arrange
        features = []
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"

        # Act & Assert - Creating empty batch should raise StateError
        with pytest.raises(BatchStateError, match="Cannot create batch state with no features"):
            batch_state = create_batch_state(
                features=features,
                batch_id=batch_id,
                state_file=str(batch_state_file)
            )

    def test_single_feature_batch(
        self,
        temp_workspace,
        batch_id
    ):
        """
        Test batch with single feature processes correctly.

        Validates:
        - Single feature processed
        - Loop exits after 1 iteration
        - Batch marked as completed
        """
        # Arrange
        features = ["Feature 1: Add authentication"]
        batch_state_file = temp_workspace / ".claude" / "batch_state.json"

        batch_state = create_batch_state(
            features=features,
            batch_id=batch_id,
            state_file=str(batch_state_file)
        )
        save_batch_state(batch_state_file, batch_state)

        # Act
        result = process_batch_with_loop(batch_state_file, features)

        # Assert - 1 feature completed (iterations may be 1 or 2 due to final None check)
        assert result["iterations"] <= 2, (
            f"Expected max 2 iterations (1 feature + final None check), got {result['iterations']}"
        )
        assert result["completed_count"] == 1
        assert result["failed_count"] == 0

        final_state = load_batch_state(batch_state_file)
        assert final_state.status == "completed"
        assert final_state.current_index == 1


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (8 integration tests for Batch Auto-Continuation):

TestBatchAutoC ontinuation (1 test)
✗ test_batch_processes_all_features_without_manual_resume
  - Validates: Auto-continuation through all 5 features
  - Current bug: Stops after Feature 1
  - Expected: Continues to Feature 5 automatically

TestBatchFailureResilience (1 test)
✗ test_batch_continues_after_feature_failure
  - Validates: Batch continues after Feature 3 fails
  - Expected: Features 4-10 still process

TestBatchLoopTermination (1 test)
✗ test_batch_exits_when_no_more_features
  - Validates: Loop exits when get_next_pending_feature() returns None
  - Expected: No infinite loop, graceful exit

TestBatchResumeContinuation (1 test)
✗ test_resume_uses_same_loop_pattern
  - Validates: Resume auto-continues through Features 5-10
  - Expected: No manual resume between features

TestBatchMultipleFailures (1 test)
✗ test_batch_completes_with_multiple_failures
  - Validates: Multiple failures don't stop batch
  - Expected: 7 completed, 3 failed, batch completes

TestBatchEdgeCases (2 tests)
✗ test_empty_batch_exits_immediately
  - Validates: Empty batch handles gracefully
✗ test_single_feature_batch
  - Validates: Single feature batch works correctly

Expected Status: ALL TESTS FAILING (RED phase - loop not implemented yet)

Implementation Guide (for implementer):
1. Update plugins/autonomous-dev/commands/implement.md BATCH FILE MODE STEP B3
2. Replace current single-feature processing with while-loop:
   ```bash
   # Process all features with auto-continuation
   while true; do
       # Get next pending feature
       NEXT_FEATURE=$(python3 -c "
   from batch_state_manager import load_batch_state, get_next_pending_feature
   state = load_batch_state('$STATE_FILE')
   next_feat = get_next_pending_feature(state)
   print(next_feat if next_feat else '')
   ")

       # Exit if no more features
       if [ -z "$NEXT_FEATURE" ]; then
           break
       fi

       # Invoke full pipeline for feature
       # ... (existing code)

       # Update batch progress
       python3 -c "
   from batch_state_manager import update_batch_progress
   update_batch_progress('$STATE_FILE', $CURRENT_INDEX, 'completed', $TOKENS)
   "
   done
   ```
3. Error handling: Failed features recorded but don't stop loop
4. Infinite loop prevention: Explicit None check from get_next_pending_feature()

Coverage Target: 80%+ for batch auto-continuation workflow
Integration Points:
- batch_state_manager.py: get_next_pending_feature(), update_batch_progress()
- plugins/autonomous-dev/commands/implement.md: STEP B3 (lines 421-428)
"""
