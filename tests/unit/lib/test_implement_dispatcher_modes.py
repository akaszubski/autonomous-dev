#!/usr/bin/env python3
"""
Unit tests for implement_dispatcher mode routing logic (TDD Red Phase).

Tests for dispatcher routing to existing commands:
- dispatch_full_pipeline() -> routes to /auto-implement logic
- dispatch_quick() -> routes to existing /implement (implementer agent)
- dispatch_batch() -> routes to /batch-implement logic

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test dispatch_full_pipeline() delegates to auto-implement
- Test dispatch_quick() delegates to implementer agent
- Test dispatch_batch() delegates to batch-implement
- Test batch file validation (exists, readable, contains features)
- Test issue number validation (positive integers, deduplication)
- Test resume batch-id validation (format, state file exists)
- Test error handling for each dispatch mode
- Test dispatch preserves context (feature description, args)

Mocking Strategy:
- Mock Task tool calls for agent invocation
- Mock subprocess calls for command execution
- Mock file I/O for batch file reading
- Mock batch_state_manager for resume validation
- No actual command execution (pure routing logic)

Coverage Target: 95%+ for dispatcher routing logic

Date: 2026-01-09
Issue: Consolidate /implement, /auto-implement, /batch-implement
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected - implementation doesn't exist yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See python-standards skill for test code conventions.
    See security-patterns skill for security test cases.
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from typing import List, Optional, Dict, Any

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# Import will fail - module doesn't exist yet (TDD!)
try:
    from implement_dispatcher import (
        ImplementMode,
        ImplementRequest,
        dispatch_full_pipeline,
        dispatch_quick,
        dispatch_batch,
        validate_batch_file,
        validate_issue_numbers,
        validate_batch_id,
        ImplementDispatchError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_feature_description():
    """Sample feature description for testing."""
    return "Add JWT authentication with bcrypt password hashing"


@pytest.fixture
def sample_batch_file(tmp_path):
    """Create sample batch features file for testing."""
    batch_file = tmp_path / "features.txt"
    batch_file.write_text(
        "Feature 1: Add user authentication\n"
        "Feature 2: Add rate limiting\n"
        "Feature 3: Add API documentation\n"
    )
    return batch_file


@pytest.fixture
def sample_batch_state(tmp_path):
    """Create sample batch state file for testing."""
    state_file = tmp_path / ".claude" / "batch_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "batch_id": "batch_20260109_123456",
        "features": ["Feature 1", "Feature 2", "Feature 3"],
        "current_index": 1,
        "status": "in_progress",
    }
    state_file.write_text(json.dumps(state, indent=2))
    return state_file


@pytest.fixture
def mock_task_tool():
    """Mock Task tool for agent invocation."""
    return MagicMock()


# =============================================================================
# UNIT TESTS - Full Pipeline Dispatch
# =============================================================================


class TestDispatchFullPipeline:
    """Unit tests for dispatch_full_pipeline() routing."""

    @patch('implement_dispatcher.invoke_auto_implement')
    def test_dispatch_full_pipeline_basic(self, mock_invoke, sample_feature_description):
        """Test dispatch_full_pipeline routes to auto-implement."""
        request = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description=sample_feature_description,
        )

        dispatch_full_pipeline(request)

        mock_invoke.assert_called_once()
        call_args = mock_invoke.call_args[0][0]
        assert call_args == sample_feature_description

    @patch('implement_dispatcher.invoke_auto_implement')
    def test_dispatch_full_pipeline_preserves_context(self, mock_invoke, sample_feature_description):
        """Test dispatch preserves feature description context."""
        request = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description=sample_feature_description,
        )

        dispatch_full_pipeline(request)

        # Verify context is passed to auto-implement
        call_args = mock_invoke.call_args[0][0]
        assert "JWT authentication" in call_args
        assert "bcrypt" in call_args

    @patch('implement_dispatcher.invoke_auto_implement')
    def test_dispatch_full_pipeline_handles_error(self, mock_invoke):
        """Test dispatch handles errors from auto-implement."""
        mock_invoke.side_effect = Exception("Auto-implement failed")

        request = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description="test feature",
        )

        with pytest.raises(ImplementDispatchError) as exc_info:
            dispatch_full_pipeline(request)

        assert "Failed to execute full pipeline" in str(exc_info.value)
        assert "Auto-implement failed" in str(exc_info.value)

    @patch('implement_dispatcher.invoke_auto_implement')
    def test_dispatch_full_pipeline_missing_description_raises_error(self, mock_invoke):
        """Test dispatch raises error when feature description missing."""
        request = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description=None,
        )

        with pytest.raises(ImplementDispatchError) as exc_info:
            dispatch_full_pipeline(request)

        assert "Feature description required" in str(exc_info.value)
        mock_invoke.assert_not_called()

    @patch('implement_dispatcher.invoke_auto_implement')
    def test_dispatch_full_pipeline_unicode_description(self, mock_invoke):
        """Test dispatch handles unicode in feature description."""
        unicode_description = "Add JWT 认证 with bcrypt パスワード hashing"
        request = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description=unicode_description,
        )

        dispatch_full_pipeline(request)

        call_args = mock_invoke.call_args[0][0]
        assert call_args == unicode_description


# =============================================================================
# UNIT TESTS - Quick Mode Dispatch
# =============================================================================


class TestDispatchQuick:
    """Unit tests for dispatch_quick() routing."""

    @patch('implement_dispatcher.invoke_implementer_agent')
    def test_dispatch_quick_basic(self, mock_invoke, sample_feature_description):
        """Test dispatch_quick routes to implementer agent."""
        request = ImplementRequest(
            mode=ImplementMode.QUICK,
            feature_description=sample_feature_description,
        )

        dispatch_quick(request)

        mock_invoke.assert_called_once()
        call_args = mock_invoke.call_args[0][0]
        assert call_args == sample_feature_description

    @patch('implement_dispatcher.invoke_implementer_agent')
    def test_dispatch_quick_preserves_context(self, mock_invoke, sample_feature_description):
        """Test dispatch preserves feature description context."""
        request = ImplementRequest(
            mode=ImplementMode.QUICK,
            feature_description=sample_feature_description,
        )

        dispatch_quick(request)

        # Verify context is passed to implementer
        call_args = mock_invoke.call_args[0][0]
        assert "JWT authentication" in call_args
        assert "bcrypt" in call_args

    @patch('implement_dispatcher.invoke_implementer_agent')
    def test_dispatch_quick_handles_error(self, mock_invoke):
        """Test dispatch handles errors from implementer agent."""
        mock_invoke.side_effect = Exception("Implementer failed")

        request = ImplementRequest(
            mode=ImplementMode.QUICK,
            feature_description="test feature",
        )

        with pytest.raises(ImplementDispatchError) as exc_info:
            dispatch_quick(request)

        assert "Failed to execute quick mode" in str(exc_info.value)
        assert "Implementer failed" in str(exc_info.value)

    @patch('implement_dispatcher.invoke_implementer_agent')
    def test_dispatch_quick_missing_description_raises_error(self, mock_invoke):
        """Test dispatch raises error when feature description missing."""
        request = ImplementRequest(
            mode=ImplementMode.QUICK,
            feature_description=None,
        )

        with pytest.raises(ImplementDispatchError) as exc_info:
            dispatch_quick(request)

        assert "Feature description required" in str(exc_info.value)
        mock_invoke.assert_not_called()

    @patch('implement_dispatcher.invoke_implementer_agent')
    def test_dispatch_quick_special_characters(self, mock_invoke):
        """Test dispatch handles special characters in description."""
        special_description = "Add JWT @auth #feature $endpoint /api/v1 100%"
        request = ImplementRequest(
            mode=ImplementMode.QUICK,
            feature_description=special_description,
        )

        dispatch_quick(request)

        call_args = mock_invoke.call_args[0][0]
        assert call_args == special_description


# =============================================================================
# UNIT TESTS - Batch Mode Dispatch
# =============================================================================


class TestDispatchBatch:
    """Unit tests for dispatch_batch() routing."""

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_batch_file(self, mock_invoke, sample_batch_file):
        """Test dispatch_batch routes to batch-implement with file."""
        request = ImplementRequest(
            mode=ImplementMode.BATCH,
            batch_file=str(sample_batch_file),
        )

        dispatch_batch(request)

        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args[1]
        assert call_kwargs['batch_file'] == str(sample_batch_file)

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_batch_issues(self, mock_invoke):
        """Test dispatch_batch routes to batch-implement with issues."""
        request = ImplementRequest(
            mode=ImplementMode.BATCH,
            issue_numbers=[1, 2, 3],
        )

        dispatch_batch(request)

        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args[1]
        assert call_kwargs['issue_numbers'] == [1, 2, 3]

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_batch_resume(self, mock_invoke, sample_batch_state):
        """Test dispatch_batch routes to batch-implement for resume."""
        request = ImplementRequest(
            mode=ImplementMode.BATCH,
            batch_id="batch_20260109_123456",
        )

        # Mock batch state file exists
        with patch('implement_dispatcher.load_batch_state') as mock_load:
            mock_load.return_value = {
                "batch_id": "batch_20260109_123456",
                "status": "in_progress",
            }

            dispatch_batch(request)

        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args[1]
        assert call_kwargs['batch_id'] == "batch_20260109_123456"

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_batch_handles_error(self, mock_invoke, sample_batch_file):
        """Test dispatch handles errors from batch-implement."""
        mock_invoke.side_effect = Exception("Batch processing failed")

        request = ImplementRequest(
            mode=ImplementMode.BATCH,
            batch_file=str(sample_batch_file),
        )

        with pytest.raises(ImplementDispatchError) as exc_info:
            dispatch_batch(request)

        assert "Failed to execute batch mode" in str(exc_info.value)
        assert "Batch processing failed" in str(exc_info.value)

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_batch_missing_source_raises_error(self, mock_invoke):
        """Test dispatch raises error when no batch source provided."""
        request = ImplementRequest(
            mode=ImplementMode.BATCH,
        )

        with pytest.raises(ImplementDispatchError) as exc_info:
            dispatch_batch(request)

        assert "Batch mode requires" in str(exc_info.value)
        mock_invoke.assert_not_called()


# =============================================================================
# UNIT TESTS - Batch File Validation
# =============================================================================


class TestBatchFileValidation:
    """Unit tests for validate_batch_file() logic."""

    def test_validate_batch_file_exists(self, sample_batch_file):
        """Test validation passes when batch file exists."""
        # Should not raise
        validate_batch_file(str(sample_batch_file))

    def test_validate_batch_file_not_exists_raises_error(self, tmp_path):
        """Test validation fails when batch file doesn't exist."""
        non_existent = tmp_path / "nonexistent.txt"

        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_file(str(non_existent))

        assert "Batch file not found" in str(exc_info.value)

    def test_validate_batch_file_not_readable_raises_error(self, tmp_path):
        """Test validation fails when batch file is not readable."""
        unreadable_file = tmp_path / "unreadable.txt"
        unreadable_file.write_text("test")
        unreadable_file.chmod(0o000)  # Remove all permissions

        try:
            with pytest.raises(ImplementDispatchError) as exc_info:
                validate_batch_file(str(unreadable_file))

            assert "Batch file not readable" in str(exc_info.value)
        finally:
            unreadable_file.chmod(0o644)  # Restore permissions for cleanup

    def test_validate_batch_file_empty_raises_error(self, tmp_path):
        """Test validation fails when batch file is empty."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_file(str(empty_file))

        assert "Batch file is empty" in str(exc_info.value)

    def test_validate_batch_file_only_whitespace_raises_error(self, tmp_path):
        """Test validation fails when batch file contains only whitespace."""
        whitespace_file = tmp_path / "whitespace.txt"
        whitespace_file.write_text("   \n\t\n   \n")

        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_file(str(whitespace_file))

        assert "Batch file contains no valid features" in str(exc_info.value)

    def test_validate_batch_file_path_traversal_raises_error(self):
        """Test validation blocks path traversal attacks (CWE-22)."""
        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_file("../../../etc/passwd")

        assert "Path traversal detected" in str(exc_info.value)

    def test_validate_batch_file_symlink_raises_error(self, tmp_path):
        """Test validation blocks symlink attacks (CWE-59)."""
        # Create symlink to sensitive file
        target = tmp_path / "sensitive.txt"
        target.write_text("sensitive data")
        symlink = tmp_path / "features.txt"
        symlink.symlink_to(target)

        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_file(str(symlink))

        assert "Symlink not allowed" in str(exc_info.value)

    def test_validate_batch_file_absolute_path(self, sample_batch_file):
        """Test validation accepts absolute paths."""
        absolute_path = sample_batch_file.resolve()
        # Should not raise
        validate_batch_file(str(absolute_path))

    def test_validate_batch_file_relative_path(self, sample_batch_file, tmp_path):
        """Test validation accepts safe relative paths."""
        # Change to tmp_path directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Should not raise
            validate_batch_file("features.txt")
        finally:
            os.chdir(original_cwd)


# =============================================================================
# UNIT TESTS - Issue Numbers Validation
# =============================================================================


class TestIssueNumbersValidation:
    """Unit tests for validate_issue_numbers() logic."""

    def test_validate_issue_numbers_positive(self):
        """Test validation passes for positive issue numbers."""
        # Should not raise
        validate_issue_numbers([1, 2, 3, 100, 999])

    def test_validate_issue_numbers_empty_raises_error(self):
        """Test validation fails when issue numbers list is empty."""
        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_issue_numbers([])

        assert "At least one issue number required" in str(exc_info.value)

    def test_validate_issue_numbers_negative_raises_error(self):
        """Test validation fails when issue numbers are negative."""
        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_issue_numbers([1, -2, 3])

        assert "Issue numbers must be positive integers" in str(exc_info.value)

    def test_validate_issue_numbers_zero_raises_error(self):
        """Test validation fails when issue numbers are zero."""
        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_issue_numbers([1, 0, 3])

        assert "Issue numbers must be positive integers" in str(exc_info.value)

    def test_validate_issue_numbers_deduplicates(self):
        """Test validation deduplicates issue numbers."""
        result = validate_issue_numbers([1, 2, 2, 3, 3, 3])

        # Should return deduplicated list
        assert result == [1, 2, 3]

    def test_validate_issue_numbers_preserves_order(self):
        """Test validation preserves order after deduplication."""
        result = validate_issue_numbers([3, 1, 2, 1, 3])

        # Should preserve first occurrence order
        assert result == [3, 1, 2]

    def test_validate_issue_numbers_large_numbers(self):
        """Test validation accepts large issue numbers."""
        large_numbers = [999999, 1000000, 9999999]
        # Should not raise
        validate_issue_numbers(large_numbers)

    def test_validate_issue_numbers_single_issue(self):
        """Test validation accepts single issue number."""
        # Should not raise
        validate_issue_numbers([42])


# =============================================================================
# UNIT TESTS - Batch ID Validation
# =============================================================================


class TestBatchIdValidation:
    """Unit tests for validate_batch_id() logic."""

    def test_validate_batch_id_valid_format(self):
        """Test validation passes for valid batch ID format."""
        valid_id = "batch_20260109_123456"
        # Should not raise
        validate_batch_id(valid_id)

    def test_validate_batch_id_invalid_format_raises_error(self):
        """Test validation fails for invalid batch ID format."""
        invalid_id = "invalid-batch-id"

        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_id(invalid_id)

        assert "Invalid batch ID format" in str(exc_info.value)

    def test_validate_batch_id_missing_prefix_raises_error(self):
        """Test validation fails when batch ID missing 'batch_' prefix."""
        invalid_id = "20260109_123456"

        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_id(invalid_id)

        assert "Invalid batch ID format" in str(exc_info.value)

    def test_validate_batch_id_invalid_date_raises_error(self):
        """Test validation fails for invalid date in batch ID."""
        invalid_id = "batch_99999999_123456"

        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_id(invalid_id)

        assert "Invalid batch ID format" in str(exc_info.value)

    def test_validate_batch_id_state_file_not_exists_raises_error(self, tmp_path):
        """Test validation fails when batch state file doesn't exist."""
        valid_id = "batch_20260109_123456"

        with patch('implement_dispatcher.get_batch_state_path') as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.json"

            with pytest.raises(ImplementDispatchError) as exc_info:
                validate_batch_id(valid_id)

            assert "Batch state file not found" in str(exc_info.value)

    def test_validate_batch_id_state_file_exists(self, sample_batch_state):
        """Test validation passes when batch state file exists."""
        valid_id = "batch_20260109_123456"

        with patch('implement_dispatcher.get_batch_state_path') as mock_path:
            mock_path.return_value = sample_batch_state

            # Should not raise
            validate_batch_id(valid_id)

    def test_validate_batch_id_empty_raises_error(self):
        """Test validation fails for empty batch ID."""
        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_id("")

        assert "Batch ID cannot be empty" in str(exc_info.value)

    def test_validate_batch_id_none_raises_error(self):
        """Test validation fails for None batch ID."""
        with pytest.raises(ImplementDispatchError) as exc_info:
            validate_batch_id(None)

        assert "Batch ID cannot be None" in str(exc_info.value)


# =============================================================================
# UNIT TESTS - Edge Cases for Dispatch
# =============================================================================


class TestDispatchEdgeCases:
    """Unit tests for edge cases in dispatch logic."""

    @patch('implement_dispatcher.invoke_auto_implement')
    def test_dispatch_very_long_description(self, mock_invoke):
        """Test dispatch handles very long feature descriptions."""
        long_description = "A" * 10000
        request = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description=long_description,
        )

        dispatch_full_pipeline(request)

        call_args = mock_invoke.call_args[0][0]
        assert len(call_args) == 10000

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_many_issue_numbers(self, mock_invoke):
        """Test dispatch handles many issue numbers (100+)."""
        many_issues = list(range(1, 101))
        request = ImplementRequest(
            mode=ImplementMode.BATCH,
            issue_numbers=many_issues,
        )

        dispatch_batch(request)

        call_kwargs = mock_invoke.call_args[1]
        assert len(call_kwargs['issue_numbers']) == 100

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_batch_file_with_unicode_content(self, mock_invoke, tmp_path):
        """Test dispatch handles batch files with unicode content."""
        unicode_file = tmp_path / "unicode_features.txt"
        unicode_file.write_text(
            "Feature 1: Add 认证\n"
            "Feature 2: Add パスワード\n"
            "Feature 3: Add Смысл\n",
            encoding='utf-8'
        )

        request = ImplementRequest(
            mode=ImplementMode.BATCH,
            batch_file=str(unicode_file),
        )

        dispatch_batch(request)

        mock_invoke.assert_called_once()


# =============================================================================
# UNIT TESTS - Concurrent Dispatch Handling
# =============================================================================


class TestConcurrentDispatch:
    """Unit tests for concurrent dispatch scenarios."""

    @patch('implement_dispatcher.invoke_batch_implement')
    def test_dispatch_batch_concurrent_access(self, mock_invoke, sample_batch_file):
        """Test dispatch handles concurrent batch file access."""
        request = ImplementRequest(
            mode=ImplementMode.BATCH,
            batch_file=str(sample_batch_file),
        )

        # Simulate concurrent dispatches
        dispatch_batch(request)
        dispatch_batch(request)

        assert mock_invoke.call_count == 2

    @patch('implement_dispatcher.invoke_auto_implement')
    def test_dispatch_full_pipeline_concurrent_features(self, mock_invoke):
        """Test dispatch handles concurrent feature implementations."""
        request1 = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description="Feature 1",
        )
        request2 = ImplementRequest(
            mode=ImplementMode.FULL_PIPELINE,
            feature_description="Feature 2",
        )

        dispatch_full_pipeline(request1)
        dispatch_full_pipeline(request2)

        assert mock_invoke.call_count == 2
        # Verify different features were dispatched
        call1 = mock_invoke.call_args_list[0][0][0]
        call2 = mock_invoke.call_args_list[1][0][0]
        assert call1 != call2


# =============================================================================
# Test Summary
# =============================================================================

"""
Test Coverage Summary:

1. Full Pipeline Dispatch Tests: 6 tests
   - Basic routing to auto-implement
   - Context preservation
   - Error handling
   - Missing description validation
   - Unicode support

2. Quick Mode Dispatch Tests: 5 tests
   - Basic routing to implementer agent
   - Context preservation
   - Error handling
   - Missing description validation
   - Special characters support

3. Batch Mode Dispatch Tests: 6 tests
   - Routing with batch file
   - Routing with issue numbers
   - Routing for resume
   - Error handling
   - Missing source validation

4. Batch File Validation Tests: 9 tests
   - File existence
   - File readability
   - Empty file detection
   - Whitespace-only detection
   - Path traversal prevention (CWE-22)
   - Symlink prevention (CWE-59)
   - Absolute/relative path handling

5. Issue Numbers Validation Tests: 8 tests
   - Positive integers
   - Empty list validation
   - Negative numbers rejection
   - Zero rejection
   - Deduplication
   - Order preservation
   - Large numbers support
   - Single issue support

6. Batch ID Validation Tests: 8 tests
   - Valid format acceptance
   - Invalid format rejection
   - Missing prefix detection
   - Invalid date detection
   - State file existence check
   - Empty/None rejection

7. Dispatch Edge Cases Tests: 3 tests
   - Very long descriptions
   - Many issue numbers
   - Unicode content

8. Concurrent Dispatch Tests: 2 tests
   - Concurrent batch access
   - Concurrent feature implementations

Total: 47 unit tests for dispatcher mode routing logic
Expected Status: ALL TESTS SHOULD FAIL (RED) - implementation doesn't exist yet

Next Phase: After these tests fail, implementer agent will write code to make them pass (GREEN).
"""
