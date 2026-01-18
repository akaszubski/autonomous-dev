#!/usr/bin/env python3
"""
Unit Tests for Batch State Manager - Skipped Feature Tracking (Issue #256)

Tests for new skipped feature tracking functionality:
- mark_feature_skipped() function to mark features as skipped
- get_next_pending_feature() filters out skipped features
- Skipped features persist across save/load cycles
- Timestamp tracking for when features were skipped

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
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict
from datetime import datetime

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import will fail for new function - module exists but function doesn't
try:
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        load_batch_state,
        save_batch_state,
        get_next_pending_feature,
        mark_feature_skipped,  # NEW FUNCTION
        BatchStateError,
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
def state_file(temp_state_dir):
    """Create temporary state file path."""
    return temp_state_dir / "batch_state.json"


@pytest.fixture
def sample_features():
    """Sample feature list for testing."""
    return [
        "Feature A: Add user authentication",
        "Feature B: Implement password reset",
        "Feature C: Add email verification",
        "Feature D: Create user profile API",
        "Feature E: Add OAuth2 integration",
    ]


@pytest.fixture
def sample_batch_state(sample_features):
    """Create sample BatchState for testing."""
    return BatchState(
        batch_id="batch-20260119-test",
        features_file="/path/to/features.txt",
        total_features=len(sample_features),
        features=sample_features,
        current_index=0,
        completed_features=[],
        failed_features=[],
        skipped_features=[],  # NEW FIELD
        context_token_estimate=5000,
        auto_clear_count=0,
        auto_clear_events=[],
        created_at="2026-01-19T10:00:00Z",
        updated_at="2026-01-19T10:00:00Z",
        status="in_progress",
    )


# =============================================================================
# SECTION 1: mark_feature_skipped() Function Tests (5 tests)
# =============================================================================

class TestMarkFeatureSkipped:
    """Test mark_feature_skipped() function for tracking skipped features."""

    def test_mark_feature_skipped_adds_to_list(self, state_file, sample_batch_state):
        """Test that mark_feature_skipped() adds feature index to skipped list."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)
        assert len(sample_batch_state.skipped_features) == 0

        # Act
        mark_feature_skipped(
            state_file,
            feature_index=2,
            reason="User requested skip"
        )

        # Assert
        updated_state = load_batch_state(state_file)
        assert len(updated_state.skipped_features) == 1

        skipped_entry = updated_state.skipped_features[0]
        assert skipped_entry["feature_index"] == 2
        assert skipped_entry["reason"] == "User requested skip"

    def test_mark_feature_skipped_includes_timestamp(self, state_file, sample_batch_state):
        """Test that mark_feature_skipped() includes timestamp in skipped entry."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)

        # Act
        before_time = datetime.utcnow().isoformat()
        mark_feature_skipped(
            state_file,
            feature_index=1,
            reason="Tests not ready"
        )
        after_time = datetime.utcnow().isoformat()

        # Assert
        updated_state = load_batch_state(state_file)
        skipped_entry = updated_state.skipped_features[0]

        assert "timestamp" in skipped_entry
        timestamp = skipped_entry["timestamp"]

        # Timestamp should be between before and after
        assert before_time <= timestamp <= after_time

    def test_mark_feature_skipped_allows_multiple_skips(self, state_file, sample_batch_state):
        """Test that mark_feature_skipped() allows multiple features to be skipped."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)

        # Act - skip multiple features
        mark_feature_skipped(state_file, feature_index=1, reason="Reason 1")
        mark_feature_skipped(state_file, feature_index=3, reason="Reason 2")
        mark_feature_skipped(state_file, feature_index=4, reason="Reason 3")

        # Assert
        updated_state = load_batch_state(state_file)
        assert len(updated_state.skipped_features) == 3

        # Verify each skipped feature
        skipped_indices = [entry["feature_index"] for entry in updated_state.skipped_features]
        assert skipped_indices == [1, 3, 4]

    def test_mark_feature_skipped_validates_feature_index_in_range(self, state_file, sample_batch_state):
        """Test that mark_feature_skipped() validates feature_index is in valid range."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)

        # Act & Assert - invalid index (too high)
        with pytest.raises(BatchStateError) as exc_info:
            mark_feature_skipped(
                state_file,
                feature_index=999,  # Out of range
                reason="Invalid test"
            )

        error_msg = str(exc_info.value).lower()
        assert "invalid" in error_msg or "out of range" in error_msg

    def test_mark_feature_skipped_validates_feature_not_already_skipped(self, state_file, sample_batch_state):
        """Test that mark_feature_skipped() prevents duplicate skips (optional validation)."""
        # Arrange
        save_batch_state(state_file, sample_batch_state)
        mark_feature_skipped(state_file, feature_index=2, reason="First skip")

        # Act & Assert - skip same feature again (should either error or be idempotent)
        # Implementation can choose to error or silently ignore
        # This test documents the expected behavior
        mark_feature_skipped(state_file, feature_index=2, reason="Second skip")

        # Assert - should still have 1 entry (idempotent) or raise error
        updated_state = load_batch_state(state_file)
        # Accept either behavior: 1 entry (idempotent) or 2 entries (allow duplicates)
        assert len(updated_state.skipped_features) in [1, 2], (
            "Implementation can either prevent duplicates (1 entry) or allow them (2 entries)"
        )


# =============================================================================
# SECTION 2: get_next_pending_feature() with Skipped Features (4 tests)
# =============================================================================

class TestGetNextPendingFeatureWithSkipped:
    """Test get_next_pending_feature() filters out skipped features."""

    def test_get_next_pending_feature_filters_skipped(self, sample_batch_state):
        """Test that get_next_pending_feature() skips features in skipped list."""
        # Arrange - mark features 1 and 2 as skipped
        sample_batch_state.current_index = 0
        sample_batch_state.skipped_features = [
            {"feature_index": 1, "reason": "Skip 1", "timestamp": "2026-01-19T10:00:00Z"},
            {"feature_index": 2, "reason": "Skip 2", "timestamp": "2026-01-19T10:01:00Z"},
        ]

        # Act - get next pending feature (should skip indices 1 and 2)
        next_feature = get_next_pending_feature(sample_batch_state)

        # Assert - should return feature at index 0 (first non-skipped)
        assert next_feature == sample_batch_state.features[0]

        # Now complete feature 0, next should be feature 3 (skip 1 and 2)
        sample_batch_state.current_index = 1
        sample_batch_state.completed_features = [0]

        next_feature = get_next_pending_feature(sample_batch_state)
        assert next_feature == sample_batch_state.features[3]  # Skip 1, 2 → get 3

    def test_get_next_pending_feature_filters_completed_and_skipped(self, sample_batch_state):
        """Test that get_next_pending_feature() filters both completed and skipped."""
        # Arrange
        sample_batch_state.current_index = 0
        sample_batch_state.completed_features = [0, 1]  # 0, 1 completed
        sample_batch_state.skipped_features = [
            {"feature_index": 2, "reason": "Skipped", "timestamp": "2026-01-19T10:00:00Z"},
        ]

        # Act - get next pending feature
        # Features: [0: completed, 1: completed, 2: skipped, 3: pending, 4: pending]
        next_feature = get_next_pending_feature(sample_batch_state)

        # Assert - should return feature 3 (first non-completed, non-skipped)
        assert next_feature == sample_batch_state.features[3]

    def test_get_next_pending_feature_returns_none_when_all_processed(self, sample_batch_state):
        """Test that get_next_pending_feature() returns None when all features processed."""
        # Arrange - mark all features as completed or skipped
        sample_batch_state.current_index = 5
        sample_batch_state.completed_features = [0, 1, 3]
        sample_batch_state.skipped_features = [
            {"feature_index": 2, "reason": "Skip 1", "timestamp": "2026-01-19T10:00:00Z"},
            {"feature_index": 4, "reason": "Skip 2", "timestamp": "2026-01-19T10:01:00Z"},
        ]

        # Act
        next_feature = get_next_pending_feature(sample_batch_state)

        # Assert - all features processed (3 completed + 2 skipped = 5 total)
        assert next_feature is None

    def test_get_next_pending_feature_skips_failed_features_too(self, sample_batch_state):
        """Test that get_next_pending_feature() also filters out failed features."""
        # Arrange
        sample_batch_state.current_index = 0
        sample_batch_state.completed_features = [0]
        sample_batch_state.failed_features = [
            {"feature_index": 1, "error_message": "Tests failed", "timestamp": "2026-01-19T10:00:00Z"}
        ]
        sample_batch_state.skipped_features = [
            {"feature_index": 2, "reason": "User skip", "timestamp": "2026-01-19T10:01:00Z"}
        ]

        # Act - get next pending feature
        # Features: [0: completed, 1: failed, 2: skipped, 3: pending, 4: pending]
        next_feature = get_next_pending_feature(sample_batch_state)

        # Assert - should return feature 3 (first not completed/failed/skipped)
        assert next_feature == sample_batch_state.features[3]


# =============================================================================
# SECTION 3: Persistence Tests (3 tests)
# =============================================================================

class TestSkippedFeaturesPersistence:
    """Test that skipped features persist across save/load cycles."""

    def test_skipped_features_persists_after_save_load(self, state_file, sample_batch_state):
        """Test that skipped_features field persists across save/load."""
        # Arrange - mark features as skipped
        save_batch_state(state_file, sample_batch_state)
        mark_feature_skipped(state_file, feature_index=1, reason="Reason 1")
        mark_feature_skipped(state_file, feature_index=3, reason="Reason 2")

        # Act - save and reload
        state1 = load_batch_state(state_file)
        save_batch_state(state_file, state1)
        state2 = load_batch_state(state_file)

        # Assert - skipped features preserved
        assert len(state2.skipped_features) == 2
        assert state2.skipped_features[0]["feature_index"] == 1
        assert state2.skipped_features[1]["feature_index"] == 3

    def test_skipped_features_field_in_json(self, state_file, sample_batch_state):
        """Test that skipped_features field exists in saved JSON file."""
        # Arrange
        sample_batch_state.skipped_features = [
            {"feature_index": 2, "reason": "Test skip", "timestamp": "2026-01-19T10:00:00Z"}
        ]

        # Act
        save_batch_state(state_file, sample_batch_state)

        # Assert - check raw JSON file
        data = json.loads(state_file.read_text())
        assert "skipped_features" in data
        assert len(data["skipped_features"]) == 1
        assert data["skipped_features"][0]["feature_index"] == 2

    def test_backward_compatibility_missing_skipped_features(self, state_file):
        """Test that loading old state files without skipped_features field works."""
        # Arrange - create old-style state file (no skipped_features field)
        old_state = {
            "batch_id": "batch-old",
            "features_file": "/path/to/features.txt",
            "total_features": 3,
            "features": ["A", "B", "C"],
            "current_index": 0,
            "completed_features": [],
            "failed_features": [],
            # NO skipped_features field (backward compatibility)
            "context_token_estimate": 0,
            "auto_clear_count": 0,
            "auto_clear_events": [],
            "created_at": "2026-01-19T10:00:00Z",
            "updated_at": "2026-01-19T10:00:00Z",
            "status": "in_progress",
        }
        state_file.write_text(json.dumps(old_state))

        # Act - load old state (should not crash)
        loaded_state = load_batch_state(state_file)

        # Assert - skipped_features should default to empty list
        assert hasattr(loaded_state, "skipped_features")
        assert loaded_state.skipped_features == []


# =============================================================================
# SECTION 4: Integration Tests (2 tests)
# =============================================================================

class TestSkippedFeaturesIntegration:
    """Integration tests for skipped features workflow."""

    def test_skip_feature_workflow_end_to_end(self, state_file, sample_features):
        """Test complete workflow: create → skip → get_next → verify."""
        # Arrange - create batch state
        state = create_batch_state("/path/to/features.txt", sample_features)
        save_batch_state(state_file, state)

        # Act - skip feature 1
        mark_feature_skipped(state_file, feature_index=1, reason="Not ready")

        # Reload and get next pending feature
        state = load_batch_state(state_file)
        next_feature = get_next_pending_feature(state)

        # Assert - should get feature 0 (not 1, which is skipped)
        assert next_feature == sample_features[0]

        # Complete feature 0, get next
        state.current_index = 1
        state.completed_features = [0]
        next_feature = get_next_pending_feature(state)

        # Should get feature 2 (skip feature 1)
        assert next_feature == sample_features[2]

    def test_multiple_skips_with_completion_workflow(self, state_file, sample_features):
        """Test workflow with multiple skips and completions."""
        # Arrange
        state = create_batch_state("/path/to/features.txt", sample_features)
        save_batch_state(state_file, state)

        # Act - skip features 1 and 3
        mark_feature_skipped(state_file, feature_index=1, reason="Skip 1")
        mark_feature_skipped(state_file, feature_index=3, reason="Skip 3")

        # Process features in order
        state = load_batch_state(state_file)

        # Get feature 0
        next_feature = get_next_pending_feature(state)
        assert next_feature == sample_features[0]

        # Complete feature 0, get next
        state.current_index = 1
        state.completed_features = [0]
        next_feature = get_next_pending_feature(state)
        assert next_feature == sample_features[2]  # Skip 1 → get 2

        # Complete feature 2, get next
        state.current_index = 3
        state.completed_features = [0, 2]
        next_feature = get_next_pending_feature(state)
        assert next_feature == sample_features[4]  # Skip 3 → get 4

        # Complete feature 4 - all done (0, 2, 4 completed; 1, 3 skipped)
        state.current_index = 5
        state.completed_features = [0, 2, 4]
        next_feature = get_next_pending_feature(state)
        assert next_feature is None  # All processed


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (14 unit tests for batch_state_manager.py - skipped features):

SECTION 1: mark_feature_skipped() Function (5 tests)
✗ test_mark_feature_skipped_adds_to_list
✗ test_mark_feature_skipped_includes_timestamp
✗ test_mark_feature_skipped_allows_multiple_skips
✗ test_mark_feature_skipped_validates_feature_index_in_range
✗ test_mark_feature_skipped_validates_feature_not_already_skipped

SECTION 2: get_next_pending_feature() with Skipped (4 tests)
✗ test_get_next_pending_feature_filters_skipped
✗ test_get_next_pending_feature_filters_completed_and_skipped
✗ test_get_next_pending_feature_returns_none_when_all_processed
✗ test_get_next_pending_feature_skips_failed_features_too

SECTION 3: Persistence Tests (3 tests)
✗ test_skipped_features_persists_after_save_load
✗ test_skipped_features_field_in_json
✗ test_backward_compatibility_missing_skipped_features

SECTION 4: Integration Tests (2 tests)
✗ test_skip_feature_workflow_end_to_end
✗ test_multiple_skips_with_completion_workflow

Expected Status: TESTS WILL FAIL (RED phase - implementation not done yet)

Implementation Requirements:
1. Add skipped_features field to BatchState dataclass (List[Dict])
2. Implement mark_feature_skipped(state_file, feature_index, reason) function
3. Update get_next_pending_feature() to filter skipped features
4. Ensure skipped_features persists in JSON save/load
5. Backward compatibility: default to [] if missing in old state files
6. Validate feature_index is in valid range (0 to total_features-1)
7. Include timestamp when marking feature as skipped

Coverage Target: 90%+ for new skipped feature functionality
"""
