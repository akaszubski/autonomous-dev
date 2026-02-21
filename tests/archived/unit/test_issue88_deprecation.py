"""
Unit tests for Issue #88 - Deprecate manual context clearing functions

Tests validate (TDD RED phase - these will FAIL until implementation):
- should_clear_context() issues DeprecationWarning
- pause_batch_for_clear() issues DeprecationWarning
- get_clear_notification_message() issues DeprecationWarning
- CONTEXT_THRESHOLD constant still exists (backward compatibility)
- Functions still work (don't break existing code)
- Old state files with auto_clear_events still load

Test Strategy:
- Deprecation warning tests (pytest.warns)
- Backward compatibility tests (constants, state loading)
- Function behavior tests (verify they still work)
- Documentation tests (verify deprecation notices)

Expected State After Implementation:
- batch_state_manager.py: Functions issue DeprecationWarning
- batch_state_manager.py: CONTEXT_THRESHOLD constant remains
- batch_state_manager.py: Functions still functional (no breaking changes)
- Old state files: Load successfully despite deprecated fields

Related to: GitHub Issue #88 - Fix broken context clearing mechanism
Phase: Deprecation (Phase 1 of 2)
"""

import json
import pytest
import sys
import warnings
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will succeed but functions will issue deprecation warnings
try:
    from batch_state_manager import (
        BatchState,
        should_clear_context,
        pause_batch_for_clear,
        get_clear_notification_message,
        load_batch_state,
        save_batch_state,
        CONTEXT_THRESHOLD,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


# =============================================================================
# SECTION 1: Deprecation Warning Tests (3 tests)
# =============================================================================


class TestDeprecationWarnings:
    """Test that deprecated functions issue DeprecationWarning."""

    def test_should_clear_context_issues_deprecation_warning(self):
        """Test that should_clear_context() issues DeprecationWarning.

        Arrange: Create batch state with tokens above threshold
        Act: Call should_clear_context()
        Assert: DeprecationWarning raised with specific message
        """
        # Arrange
        state = BatchState(
            batch_id="batch-test-001",
            features_file="features.txt",
            total_features=5,
            features=["feat1", "feat2", "feat3"],
            current_index=2,
            context_token_estimate=160000,  # Above threshold
            auto_clear_count=0,
            auto_clear_events=[],
            created_at="2025-11-17T10:00:00Z",
            updated_at="2025-11-17T10:00:00Z",
            status="in_progress",
        )

        # Act & Assert
        # WILL FAIL: Function doesn't issue warning yet
        with pytest.warns(DeprecationWarning, match=r"should_clear_context.*deprecated.*automatic compression"):
            result = should_clear_context(state)

        # Function should still return expected value (backward compatibility)
        assert result is True, "Function should still work despite deprecation"

    def test_pause_batch_for_clear_issues_deprecation_warning(self, tmp_path):
        """Test that pause_batch_for_clear() issues DeprecationWarning.

        Arrange: Create batch state file
        Act: Call pause_batch_for_clear()
        Assert: DeprecationWarning raised with specific message
        """
        # Arrange
        state_file = tmp_path / "batch_state.json"
        state = BatchState(
            batch_id="batch-test-002",
            features_file="features.txt",
            total_features=5,
            features=["feat1", "feat2", "feat3"],
            current_index=2,
            context_token_estimate=160000,
            auto_clear_count=0,
            auto_clear_events=[],
            created_at="2025-11-17T10:00:00Z",
            updated_at="2025-11-17T10:00:00Z",
            status="in_progress",
        )
        save_batch_state(state_file, state)

        # Act & Assert
        # WILL FAIL: Function doesn't issue warning yet
        with pytest.warns(DeprecationWarning, match=r"pause_batch_for_clear.*deprecated.*automatic compression"):
            pause_batch_for_clear(state_file, 2, 160000)

        # Function should still work (backward compatibility)
        updated_state = load_batch_state(state_file)
        assert updated_state.status == "paused", "Function should still work despite deprecation"

    def test_get_clear_notification_message_issues_deprecation_warning(self):
        """Test that get_clear_notification_message() issues DeprecationWarning.

        Arrange: Prepare batch ID and feature index
        Act: Call get_clear_notification_message()
        Assert: DeprecationWarning raised with specific message
        """
        # Act & Assert
        # WILL FAIL: Function doesn't issue warning yet
        with pytest.warns(DeprecationWarning, match=r"get_clear_notification_message.*deprecated.*automatic compression"):
            message = get_clear_notification_message("batch-test-003", 5, 160000)

        # Function should still return a message (backward compatibility)
        assert isinstance(message, str), "Function should still work despite deprecation"
        assert "batch-test-003" in message, "Message should contain batch ID"


# =============================================================================
# SECTION 2: Backward Compatibility Tests (4 tests)
# =============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_context_threshold_constant_exists(self):
        """Test that CONTEXT_THRESHOLD constant still exists.

        Arrange: Import module
        Act: Access CONTEXT_THRESHOLD
        Assert: Constant exists and has expected value
        """
        # Act & Assert
        assert CONTEXT_THRESHOLD == 150000, (
            f"CONTEXT_THRESHOLD constant should remain at 150000 for backward compatibility\n"
            f"Found: {CONTEXT_THRESHOLD}\n"
            f"Expected: 150000"
        )

    def test_deprecated_functions_still_callable(self):
        """Test that deprecated functions are still callable.

        Arrange: Create batch state
        Act: Call deprecated functions
        Assert: No AttributeError raised
        """
        # Arrange
        state = BatchState(
            batch_id="batch-test-004",
            features_file="features.txt",
            total_features=3,
            features=["feat1", "feat2", "feat3"],
            current_index=1,
            context_token_estimate=100000,
            auto_clear_count=0,
            auto_clear_events=[],
            created_at="2025-11-17T10:00:00Z",
            updated_at="2025-11-17T10:00:00Z",
            status="in_progress",
        )

        # Act & Assert - Functions should exist and be callable
        assert callable(should_clear_context), "should_clear_context should still be callable"
        assert callable(pause_batch_for_clear), "pause_batch_for_clear should still be callable"
        assert callable(get_clear_notification_message), "get_clear_notification_message should still be callable"

    def test_old_state_files_load_successfully(self, tmp_path):
        """Test that old state files with auto_clear_events load successfully.

        Arrange: Create state file with auto_clear_events field
        Act: Load state file
        Assert: No error, auto_clear_events preserved
        """
        # Arrange - Old state format with auto_clear_events
        state_file = tmp_path / "batch_state.json"
        old_state_data = {
            "batch_id": "batch-old-001",
            "features_file": "features.txt",
            "total_features": 10,
            "features": ["feat1", "feat2", "feat3", "feat4", "feat5"],
            "current_index": 4,
            "completed_features": [0, 1, 2, 3],
            "failed_features": [],
            "context_token_estimate": 50000,
            "auto_clear_count": 2,
            "auto_clear_events": [
                {
                    "feature_index": 2,
                    "tokens_before": 155000,
                    "timestamp": "2025-11-16T12:00:00Z"
                },
                {
                    "feature_index": 4,
                    "tokens_before": 152000,
                    "timestamp": "2025-11-16T14:00:00Z"
                }
            ],
            "created_at": "2025-11-16T10:00:00Z",
            "updated_at": "2025-11-16T14:30:00Z",
            "status": "in_progress"
        }

        state_file.write_text(json.dumps(old_state_data, indent=2))

        # Act
        # WILL SUCCEED: Load should work despite deprecated fields
        loaded_state = load_batch_state(state_file)

        # Assert
        assert loaded_state.batch_id == "batch-old-001", "Batch ID should be preserved"
        assert loaded_state.current_index == 4, "Current index should be preserved"
        assert loaded_state.auto_clear_count == 2, "Auto clear count should be preserved"
        assert len(loaded_state.auto_clear_events) == 2, "Auto clear events should be preserved"
        assert loaded_state.auto_clear_events[0]["feature_index"] == 2, "Event data should be preserved"

    def test_deprecated_functions_maintain_behavior(self, tmp_path):
        """Test that deprecated functions maintain original behavior.

        Arrange: Create batch state and state file
        Act: Call deprecated functions
        Assert: Original behavior preserved
        """
        # Arrange
        state_file = tmp_path / "batch_state.json"
        state = BatchState(
            batch_id="batch-test-005",
            features_file="features.txt",
            total_features=5,
            features=["feat1", "feat2", "feat3", "feat4", "feat5"],
            current_index=2,
            context_token_estimate=160000,  # Above threshold
            auto_clear_count=0,
            auto_clear_events=[],
            created_at="2025-11-17T10:00:00Z",
            updated_at="2025-11-17T10:00:00Z",
            status="in_progress",
        )
        save_batch_state(state_file, state)

        # Act - Suppress deprecation warnings for behavior testing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            # Test should_clear_context
            should_clear = should_clear_context(state)
            assert should_clear is True, "should_clear_context should return True when above threshold"

            # Test pause_batch_for_clear
            pause_batch_for_clear(state_file, 2, 160000)
            paused_state = load_batch_state(state_file)
            assert paused_state.status == "paused", "pause_batch_for_clear should set status to paused"

            # Test get_clear_notification_message
            message = get_clear_notification_message("batch-test-005", 2, 160000)
            assert "batch-test-005" in message, "Notification message should contain batch ID"
            assert "2" in message or "3" in message, "Notification message should reference feature index"


# =============================================================================
# SECTION 3: Documentation Tests (2 tests)
# =============================================================================


class TestDeprecationDocumentation:
    """Test that deprecation is properly documented."""

    def test_function_docstrings_mention_deprecation(self):
        """Test that deprecated functions have deprecation notices in docstrings.

        Arrange: Import deprecated functions
        Act: Read docstrings
        Assert: Deprecation notice present
        """
        # WILL FAIL: Docstrings don't mention deprecation yet
        assert should_clear_context.__doc__ is not None, "should_clear_context should have docstring"
        assert "deprecated" in should_clear_context.__doc__.lower(), (
            "should_clear_context docstring should mention deprecation"
        )

        assert pause_batch_for_clear.__doc__ is not None, "pause_batch_for_clear should have docstring"
        assert "deprecated" in pause_batch_for_clear.__doc__.lower(), (
            "pause_batch_for_clear docstring should mention deprecation"
        )

        assert get_clear_notification_message.__doc__ is not None, "get_clear_notification_message should have docstring"
        assert "deprecated" in get_clear_notification_message.__doc__.lower(), (
            "get_clear_notification_message docstring should mention deprecation"
        )

    def test_deprecation_warnings_have_clear_messages(self):
        """Test that deprecation warnings have clear, actionable messages.

        Arrange: Create batch state
        Act: Call deprecated functions and capture warnings
        Assert: Warning messages are clear and actionable
        """
        # Arrange
        state = BatchState(
            batch_id="batch-test-006",
            features_file="features.txt",
            total_features=3,
            features=["feat1", "feat2", "feat3"],
            current_index=1,
            context_token_estimate=160000,
            auto_clear_count=0,
            auto_clear_events=[],
            created_at="2025-11-17T10:00:00Z",
            updated_at="2025-11-17T10:00:00Z",
            status="in_progress",
        )

        # Act & Assert - Check warning message quality
        # WILL FAIL: Warning messages don't exist yet
        with pytest.warns(DeprecationWarning) as warning_list:
            should_clear_context(state)

        assert len(warning_list) > 0, "Should issue at least one warning"
        warning_message = str(warning_list[0].message)

        # Warning should mention:
        # 1. What's deprecated
        # 2. Why it's deprecated
        # 3. What to do instead
        assert "automatic compression" in warning_message.lower(), (
            "Warning should explain that Claude Code handles compression automatically"
        )
        assert "no longer needed" in warning_message.lower() or "not needed" in warning_message.lower(), (
            "Warning should explain why manual clearing is no longer needed"
        )


# =============================================================================
# SUMMARY
# =============================================================================

"""
Test Coverage Summary:

SECTION 1: Deprecation Warning Tests (3 tests)
- test_should_clear_context_issues_deprecation_warning
- test_pause_batch_for_clear_issues_deprecation_warning
- test_get_clear_notification_message_issues_deprecation_warning

SECTION 2: Backward Compatibility Tests (4 tests)
- test_context_threshold_constant_exists
- test_deprecated_functions_still_callable
- test_old_state_files_load_successfully
- test_deprecated_functions_maintain_behavior

SECTION 3: Documentation Tests (2 tests)
- test_function_docstrings_mention_deprecation
- test_deprecation_warnings_have_clear_messages

Total: 9 tests (all will FAIL in TDD red phase)

Expected Failures:
- Functions don't issue DeprecationWarning yet
- Docstrings don't mention deprecation yet
- Warning messages don't exist yet

Test File: tests/unit/test_issue88_deprecation.py
Related Issue: #88 - Fix broken context clearing mechanism
Phase: TDD RED (tests written BEFORE implementation)
Agent: test-master
Date: 2025-11-17
"""
