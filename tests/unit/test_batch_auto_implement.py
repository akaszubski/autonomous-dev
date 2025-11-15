#!/usr/bin/env python3
"""
Unit Tests for batch_auto_implement Module (FAILING - Red Phase)

This module contains FAILING tests for the batch_auto_implement.py module that
will provide batch processing of multiple features with automatic context management.

Feature Requirements (from implementation plan):
1. Input validation: File path, size limits, encoding (UTF-8)
2. Feature parsing: Deduplication, comment skipping, line length limits
3. Batch execution: Sequential /auto-implement invocation per feature
4. Context management: Auto-clear between features
5. Progress tracking: Session logging with metrics
6. Summary generation: Success/failure counts, timing, git stats
7. Security: CWE-22 path traversal, CWE-400 DoS, CWE-78 command injection
8. Error handling: Continue-on-failure and abort-on-failure modes

Test Coverage Target: 80%+ code coverage

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe feature requirements
- Tests should FAIL until batch_auto_implement.py is implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-15
Issue: batch-implement feature
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock, call, mock_open
import pytest

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

# Import will fail - module doesn't exist yet (TDD!)
try:
    from batch_auto_implement import (
        BatchAutoImplement,
        BatchResult,
        FeatureResult,
        ValidationError,
        BatchExecutionError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project structure for testing."""
    project = tmp_path / "test_project"
    project.mkdir()

    # Create standard directories
    (project / ".claude").mkdir()
    (project / "docs" / "sessions").mkdir(parents=True)
    (project / "logs").mkdir()

    # Create PROJECT.md
    project_md = project / ".claude" / "PROJECT.md"
    project_md.write_text("""
## GOALS
- Goal 1: Implement authentication
- Goal 2: Add user profiles

## SCOPE
- Authentication and user management

## CONSTRAINTS
- Must use standard library only

## ARCHITECTURE
- Modular design with clean interfaces
""")

    return project


@pytest.fixture
def sample_features_file(tmp_path):
    """Create sample features file with valid features."""
    features_file = tmp_path / "features.txt"
    features_file.write_text("""# Authentication features
Add user login
Add user logout

# User management features
Add user profile page
Add password reset
""")
    return features_file


@pytest.fixture
def batch_processor(temp_project_root):
    """Create BatchAutoImplement instance for testing."""
    return BatchAutoImplement(
        project_root=temp_project_root,
        continue_on_failure=True,
        test_mode=True  # Enable test mode for temp paths
    )


# ==============================================================================
# Input Validation Tests
# ==============================================================================

class TestInputValidation:
    """Test input validation for batch file and parameters."""

    def test_validate_features_file_exists(self, batch_processor, tmp_path):
        """Test validation fails if features file doesn't exist.

        Arrange: Non-existent file path
        Act: Validate features file
        Assert: Raises ValidationError
        """
        non_existent = tmp_path / "missing.txt"

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(non_existent)

        assert "not found" in str(exc_info.value).lower()
        assert str(non_existent) in str(exc_info.value)

    def test_validate_features_file_is_file(self, batch_processor, tmp_path):
        """Test validation fails if path is a directory.

        Arrange: Directory path instead of file
        Act: Validate features file
        Assert: Raises ValidationError
        """
        directory = tmp_path / "features_dir"
        directory.mkdir()

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(directory)

        assert "not a file" in str(exc_info.value).lower()

    def test_validate_path_traversal_blocked(self, batch_processor, tmp_path):
        """Test CWE-22: Path traversal attack is blocked.

        Arrange: Malicious path with ../../../etc/passwd
        Act: Validate features file
        Assert: Raises ValidationError with path traversal message
        """
        malicious_path = tmp_path / ".." / ".." / ".." / "etc" / "passwd"

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(malicious_path)

        assert "path traversal" in str(exc_info.value).lower()

    def test_validate_file_size_limit(self, batch_processor, tmp_path):
        """Test CWE-400: File size limit prevents DoS.

        Arrange: File exceeding 1MB size limit
        Act: Validate features file
        Assert: Raises ValidationError with size limit message
        """
        large_file = tmp_path / "large.txt"
        # Write 2MB of data (exceeds 1MB limit)
        large_file.write_bytes(b"x" * (2 * 1024 * 1024))

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(large_file)

        assert "too large" in str(exc_info.value).lower()
        assert "1mb" in str(exc_info.value).lower() or "1048576" in str(exc_info.value)

    def test_validate_encoding_utf8(self, batch_processor, tmp_path):
        """Test that non-UTF-8 files are rejected.

        Arrange: File with invalid UTF-8 encoding
        Act: Validate features file
        Assert: Raises ValidationError with encoding message
        """
        invalid_file = tmp_path / "invalid.txt"
        # Write invalid UTF-8 bytes
        invalid_file.write_bytes(b"\xff\xfe Invalid UTF-8")

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(invalid_file)

        assert "encoding" in str(exc_info.value).lower()

    def test_validate_empty_file(self, batch_processor, tmp_path):
        """Test that empty files are rejected.

        Arrange: Empty features file
        Act: Validate features file
        Assert: Raises ValidationError
        """
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(empty_file)

        assert "empty" in str(exc_info.value).lower()


# ==============================================================================
# Feature Parsing Tests
# ==============================================================================

class TestFeatureParsing:
    """Test feature parsing logic from input file."""

    def test_parse_features_single_line(self, batch_processor, tmp_path):
        """Test parsing single feature from file.

        Arrange: File with one feature
        Act: Parse features
        Assert: Returns list with one feature
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 1
        assert features[0] == "Add user login"

    def test_parse_features_multiple_lines(self, batch_processor, tmp_path):
        """Test parsing multiple features from file.

        Arrange: File with three features
        Act: Parse features
        Assert: Returns list with three features in order
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add user logout
Add password reset
""")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 3
        assert features[0] == "Add user login"
        assert features[1] == "Add user logout"
        assert features[2] == "Add password reset"

    def test_parse_features_skip_comments(self, batch_processor, tmp_path):
        """Test that comment lines (starting with #) are skipped.

        Arrange: File with comments and features
        Act: Parse features
        Assert: Returns only non-comment lines
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""# Authentication features
Add user login
# User management
Add user profile
""")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 2
        assert features[0] == "Add user login"
        assert features[1] == "Add user profile"

    def test_parse_features_skip_empty_lines(self, batch_processor, tmp_path):
        """Test that empty lines are skipped.

        Arrange: File with empty lines between features
        Act: Parse features
        Assert: Returns only non-empty lines
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login

Add user logout

""")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 2
        assert features[0] == "Add user login"
        assert features[1] == "Add user logout"

    def test_parse_features_strip_whitespace(self, batch_processor, tmp_path):
        """Test that leading/trailing whitespace is stripped.

        Arrange: File with features containing whitespace
        Act: Parse features
        Assert: Returns trimmed features
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""  Add user login
\tAdd user logout\t
""")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 2
        assert features[0] == "Add user login"
        assert features[1] == "Add user logout"

    def test_parse_features_deduplicate(self, batch_processor, tmp_path):
        """Test that duplicate features are removed.

        Arrange: File with duplicate features
        Act: Parse features
        Assert: Returns unique features only
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add user logout
Add user login
Add password reset
Add user logout
""")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 3
        assert features == ["Add user login", "Add user logout", "Add password reset"]

    def test_parse_features_max_line_length(self, batch_processor, tmp_path):
        """Test that lines exceeding 500 characters are rejected.

        Arrange: File with line exceeding 500 chars
        Act: Parse features
        Assert: Raises ValidationError
        """
        features_file = tmp_path / "features.txt"
        long_feature = "Add feature " + ("x" * 500)
        features_file.write_text(long_feature)

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.parse_features(features_file)

        assert "too long" in str(exc_info.value).lower()
        assert "500" in str(exc_info.value)

    def test_parse_features_comments_only_file(self, batch_processor, tmp_path):
        """Test that file with only comments is rejected.

        Arrange: File containing only comments
        Act: Parse features
        Assert: Raises ValidationError
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""# Comment 1
# Comment 2
# Comment 3
""")

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.parse_features(features_file)

        assert "no valid features" in str(exc_info.value).lower()


# ==============================================================================
# Batch Execution Tests
# ==============================================================================

class TestBatchExecution:
    """Test batch execution of multiple features."""

    @patch('batch_auto_implement.Task')
    def test_execute_single_feature(self, mock_task, batch_processor, sample_features_file):
        """Test execution of single feature.

        Arrange: One feature in file
        Act: Execute batch
        Assert: Invokes /auto-implement once
        """
        features_file = sample_features_file.parent / "single.txt"
        features_file.write_text("Add user login\n")

        # Mock Task tool response
        mock_task.return_value.__enter__.return_value = MagicMock(
            status="success",
            output={"message": "Feature completed"}
        )

        result = batch_processor.execute_batch(features_file)

        assert result.total_features == 1
        assert result.successful_features == 1
        assert result.failed_features == 0
        assert mock_task.call_count == 1

    @patch('batch_auto_implement.Task')
    def test_execute_multiple_features_sequential(self, mock_task, batch_processor, tmp_path):
        """Test that features are executed sequentially.

        Arrange: Three features in file
        Act: Execute batch
        Assert: Features executed in order, one at a time
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add user logout
Add password reset
""")

        # Track execution order
        execution_order = []

        def mock_task_context(*args, **kwargs):
            feature = kwargs.get('description', '')
            execution_order.append(feature)
            mock = MagicMock()
            mock.__enter__ = lambda self: MagicMock(status="success")
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_context

        result = batch_processor.execute_batch(features_file)

        assert len(execution_order) == 3
        assert "Add user login" in execution_order[0]
        assert "Add user logout" in execution_order[1]
        assert "Add password reset" in execution_order[2]

    @patch('batch_auto_implement.Task')
    def test_execute_continue_on_failure_mode(self, mock_task, batch_processor, tmp_path):
        """Test continue-on-failure mode continues after errors.

        Arrange: Three features, second one fails
        Act: Execute batch with continue_on_failure=True
        Assert: All three features attempted
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add invalid feature
Add password reset
""")

        # Mock second feature to fail
        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            mock = MagicMock()
            if "invalid" in feature:
                mock.__enter__ = lambda self: MagicMock(status="failed")
            else:
                mock.__enter__ = lambda self: MagicMock(status="success")
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect

        batch_processor.continue_on_failure = True
        result = batch_processor.execute_batch(features_file)

        assert result.total_features == 3
        assert result.successful_features == 2
        assert result.failed_features == 1
        assert mock_task.call_count == 3

    @patch('batch_auto_implement.Task')
    def test_execute_abort_on_failure_mode(self, mock_task, batch_processor, tmp_path):
        """Test abort-on-failure mode stops after first error.

        Arrange: Three features, second one fails
        Act: Execute batch with continue_on_failure=False
        Assert: Only first two features attempted
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add invalid feature
Add password reset
""")

        # Track which features were attempted
        attempted = []

        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            attempted.append(feature)
            mock = MagicMock()
            if "invalid" in feature:
                mock.__enter__ = lambda self: MagicMock(status="failed")
            else:
                mock.__enter__ = lambda self: MagicMock(status="success")
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect

        batch_processor.continue_on_failure = False

        with pytest.raises(BatchExecutionError) as exc_info:
            batch_processor.execute_batch(features_file)

        # Should have attempted first two features only
        assert len(attempted) == 2
        assert "aborted" in str(exc_info.value).lower()

    @patch('batch_auto_implement.Task')
    def test_execute_task_tool_invocation_format(self, mock_task, batch_processor, tmp_path):
        """Test that Task tool is invoked with correct format.

        Arrange: Single feature
        Act: Execute batch
        Assert: Task invoked with correct agent and description
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)

        # Verify Task tool called with correct parameters
        mock_task.assert_called_once()
        call_kwargs = mock_task.call_args[1]
        assert 'agent_file' in call_kwargs
        assert 'auto-implement' in call_kwargs['agent_file']
        assert 'description' in call_kwargs
        assert 'Add user login' in call_kwargs['description']


# ==============================================================================
# Context Management Tests
# ==============================================================================

class TestContextManagement:
    """Test automatic context clearing between features."""

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_clear_context_after_each_feature(self, mock_clear, mock_task, batch_processor, tmp_path):
        """Test that /clear is called after each feature.

        Arrange: Three features
        Act: Execute batch
        Assert: /clear called 3 times (once after each feature)
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add user logout
Add password reset
""")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.return_value = True

        result = batch_processor.execute_batch(features_file)

        # Should clear context after each feature (3 times)
        assert mock_clear.call_count == 3

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_clear_context_on_failure(self, mock_clear, mock_task, batch_processor, tmp_path):
        """Test that context is cleared even if feature fails.

        Arrange: Feature that fails
        Act: Execute batch
        Assert: /clear still called
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add invalid feature\n")

        mock_task.return_value.__enter__.return_value = MagicMock(status="failed")
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.return_value = True

        batch_processor.continue_on_failure = True
        result = batch_processor.execute_batch(features_file)

        # Should clear context even after failure
        assert mock_clear.call_count == 1

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_handle_clear_command_failure(self, mock_clear, mock_task, batch_processor, tmp_path):
        """Test graceful handling when /clear command fails.

        Arrange: /clear command fails
        Act: Execute batch
        Assert: Continues execution, logs warning
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.side_effect = Exception("Clear failed")

        # Should not raise exception, continues execution
        result = batch_processor.execute_batch(features_file)

        assert result.successful_features == 1


# ==============================================================================
# Progress Tracking Tests
# ==============================================================================

class TestProgressTracking:
    """Test progress tracking and session logging."""

    @patch('batch_auto_implement.Task')
    def test_track_feature_timing(self, mock_task, batch_processor, tmp_path):
        """Test that feature execution time is tracked.

        Arrange: Single feature
        Act: Execute batch
        Assert: Result contains timing information
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)

        assert hasattr(result, 'total_time_seconds')
        assert result.total_time_seconds > 0
        assert len(result.feature_results) == 1
        assert hasattr(result.feature_results[0], 'duration_seconds')

    @patch('batch_auto_implement.Task')
    def test_session_file_logging(self, mock_task, batch_processor, tmp_path, temp_project_root):
        """Test that progress is logged to session file.

        Arrange: Batch execution
        Act: Execute batch
        Assert: Session file created with progress log
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)

        # Verify session file exists
        session_dir = temp_project_root / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))
        assert len(session_files) > 0

        # Verify session file contains batch info
        with open(session_files[-1], 'r') as f:
            session_data = json.load(f)
        assert 'batch_id' in session_data
        assert 'features' in session_data

    @patch('batch_auto_implement.Task')
    def test_track_git_statistics(self, mock_task, batch_processor, tmp_path):
        """Test that git statistics are tracked per feature.

        Arrange: Feature with git changes
        Act: Execute batch
        Assert: Result contains files changed, lines added/removed
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        # Mock git stats in task result
        mock_result = MagicMock(
            status="success",
            git_stats={
                'files_changed': 3,
                'lines_added': 50,
                'lines_removed': 10
            }
        )
        mock_task.return_value.__enter__.return_value = mock_result
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)

        feature_result = result.feature_results[0]
        assert hasattr(feature_result, 'git_stats')
        assert feature_result.git_stats['files_changed'] == 3

    @patch('batch_auto_implement.Task')
    def test_track_failed_features_list(self, mock_task, batch_processor, tmp_path):
        """Test that failed features are tracked in result.

        Arrange: Mix of successful and failed features
        Act: Execute batch
        Assert: Result contains list of failed features
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add invalid feature
Add password reset
""")

        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            mock = MagicMock()
            if "invalid" in feature:
                mock.__enter__ = lambda self: MagicMock(status="failed", error="Test error")
            else:
                mock.__enter__ = lambda self: MagicMock(status="success")
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        batch_processor.continue_on_failure = True

        result = batch_processor.execute_batch(features_file)

        assert len(result.failed_feature_names) == 1
        assert "Add invalid feature" in result.failed_feature_names


# ==============================================================================
# Summary Generation Tests
# ==============================================================================

class TestSummaryGeneration:
    """Test summary report generation."""

    @patch('batch_auto_implement.Task')
    def test_generate_summary_basic_metrics(self, mock_task, batch_processor, tmp_path):
        """Test summary includes basic metrics.

        Arrange: Batch execution completed
        Act: Generate summary
        Assert: Summary contains total, success, failure counts
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add user logout
""")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)
        summary = batch_processor.generate_summary(result)

        assert "Total features: 2" in summary
        assert "Successful: 2" in summary
        assert "Failed: 0" in summary

    @patch('batch_auto_implement.Task')
    def test_generate_summary_timing_info(self, mock_task, batch_processor, tmp_path):
        """Test summary includes timing information.

        Arrange: Batch execution completed
        Act: Generate summary
        Assert: Summary contains total time
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)
        summary = batch_processor.generate_summary(result)

        assert "Total time" in summary
        assert "seconds" in summary or "minutes" in summary

    @patch('batch_auto_implement.Task')
    def test_generate_summary_failed_features_list(self, mock_task, batch_processor, tmp_path):
        """Test summary lists failed features.

        Arrange: Batch with failures
        Act: Generate summary
        Assert: Summary lists failed feature names
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add invalid feature
""")

        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            mock = MagicMock()
            if "invalid" in feature:
                mock.__enter__ = lambda self: MagicMock(status="failed")
            else:
                mock.__enter__ = lambda self: MagicMock(status="success")
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        batch_processor.continue_on_failure = True

        result = batch_processor.execute_batch(features_file)
        summary = batch_processor.generate_summary(result)

        assert "Failed features:" in summary
        assert "Add invalid feature" in summary

    @patch('batch_auto_implement.Task')
    def test_generate_summary_git_statistics(self, mock_task, batch_processor, tmp_path):
        """Test summary includes aggregated git statistics.

        Arrange: Batch execution with git changes
        Act: Generate summary
        Assert: Summary includes total files/lines changed
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add user logout
""")

        # Mock git stats
        mock_result = MagicMock(
            status="success",
            git_stats={
                'files_changed': 2,
                'lines_added': 30,
                'lines_removed': 5
            }
        )
        mock_task.return_value.__enter__.return_value = mock_result
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)
        summary = batch_processor.generate_summary(result)

        assert "files changed" in summary.lower()
        assert "lines added" in summary.lower()


# ==============================================================================
# Security Tests
# ==============================================================================

class TestSecurity:
    """Test security validation (CWE-22, CWE-400, CWE-78)."""

    def test_cwe22_path_traversal_prevention(self, batch_processor, tmp_path):
        """Test CWE-22: Path traversal attacks are blocked.

        Arrange: Malicious file path with ../../../
        Act: Validate file
        Assert: Raises ValidationError
        """
        malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(malicious_path)

        assert "path traversal" in str(exc_info.value).lower()

    def test_cwe400_dos_file_size_limit(self, batch_processor, tmp_path):
        """Test CWE-400: DoS via large file is prevented.

        Arrange: File exceeding size limit
        Act: Validate file
        Assert: Raises ValidationError
        """
        large_file = tmp_path / "large.txt"
        # Create 2MB file (exceeds 1MB limit)
        large_file.write_bytes(b"x" * (2 * 1024 * 1024))

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.validate_features_file(large_file)

        assert "too large" in str(exc_info.value).lower()

    def test_cwe400_dos_line_count_limit(self, batch_processor, tmp_path):
        """Test CWE-400: DoS via excessive line count is prevented.

        Arrange: File with 10,000+ lines
        Act: Parse features
        Assert: Raises ValidationError
        """
        many_lines_file = tmp_path / "many.txt"
        # Create file with 11,000 lines (exceeds 10,000 limit)
        many_lines_file.write_text("\n".join([f"Feature {i}" for i in range(11000)]))

        with pytest.raises(ValidationError) as exc_info:
            batch_processor.parse_features(many_lines_file)

        assert "too many features" in str(exc_info.value).lower()

    @patch('batch_auto_implement.subprocess.run')
    def test_cwe78_command_injection_prevention(self, mock_run, batch_processor, tmp_path):
        """Test CWE-78: Command injection via feature names is prevented.

        Arrange: Feature with shell metacharacters
        Act: Execute batch
        Assert: Feature name is properly escaped
        """
        features_file = tmp_path / "features.txt"
        # Try to inject command via feature name
        features_file.write_text("Add user; rm -rf /\n")

        # Should not execute injected command
        # Implementation should properly escape/sanitize inputs
        batch_processor.validate_features_file(features_file)
        features = batch_processor.parse_features(features_file)

        # Feature should be treated as literal string
        assert features[0] == "Add user; rm -rf /"

        # Verify no shell command execution
        mock_run.assert_not_called()

    def test_audit_logging_enabled(self, batch_processor, tmp_path):
        """Test that security events are logged to audit log.

        Arrange: Batch execution
        Act: Execute batch
        Assert: Audit log contains entries
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user login\n")

        with patch('batch_auto_implement.audit_log') as mock_audit:
            batch_processor.validate_features_file(features_file)

            # Verify audit logging was called
            assert mock_audit.called


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_very_long_feature_name(self, batch_processor, tmp_path):
        """Test handling of maximum length feature name (500 chars).

        Arrange: Feature name exactly 500 characters
        Act: Parse features
        Assert: Feature accepted
        """
        features_file = tmp_path / "features.txt"
        max_length_feature = "Add feature " + ("x" * 488)  # Total = 500
        features_file.write_text(max_length_feature + "\n")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 1
        assert len(features[0]) == 500

    def test_unicode_feature_names(self, batch_processor, tmp_path):
        """Test handling of Unicode characters in feature names.

        Arrange: Feature with Unicode characters
        Act: Parse features
        Assert: Unicode preserved correctly
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user profile with emoji 🚀\n", encoding='utf-8')

        features = batch_processor.parse_features(features_file)

        assert len(features) == 1
        assert "🚀" in features[0]

    def test_windows_line_endings(self, batch_processor, tmp_path):
        """Test handling of Windows line endings (CRLF).

        Arrange: File with CRLF line endings
        Act: Parse features
        Assert: Features parsed correctly
        """
        features_file = tmp_path / "features.txt"
        features_file.write_bytes(b"Add user login\r\nAdd user logout\r\n")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 2
        assert features[0] == "Add user login"

    def test_mixed_comment_styles(self, batch_processor, tmp_path):
        """Test that only # comments are recognized.

        Arrange: File with # comments and // comments
        Act: Parse features
        Assert: Only # lines skipped
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""# This is a comment
Add user login
// This is NOT a comment
Add user logout
""")

        features = batch_processor.parse_features(features_file)

        assert len(features) == 3  # "Add user login", "// This...", "Add user logout"
        assert "// This is NOT a comment" in features

    @patch('batch_auto_implement.Task')
    def test_all_features_fail(self, mock_task, batch_processor, tmp_path):
        """Test handling when all features fail.

        Arrange: All features configured to fail
        Act: Execute batch with continue_on_failure
        Assert: Result shows 0 successful, all failed
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add invalid 1
Add invalid 2
Add invalid 3
""")

        mock_task.return_value.__enter__.return_value = MagicMock(status="failed")
        mock_task.return_value.__exit__ = lambda self, *args: None

        batch_processor.continue_on_failure = True
        result = batch_processor.execute_batch(features_file)

        assert result.total_features == 3
        assert result.successful_features == 0
        assert result.failed_features == 3

    @patch('batch_auto_implement.Task')
    def test_all_features_succeed(self, mock_task, batch_processor, tmp_path):
        """Test handling when all features succeed.

        Arrange: All features configured to succeed
        Act: Execute batch
        Assert: Result shows all successful, 0 failed
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user login
Add user logout
Add password reset
""")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None

        result = batch_processor.execute_batch(features_file)

        assert result.total_features == 3
        assert result.successful_features == 3
        assert result.failed_features == 0


# ==============================================================================
# Data Classes Tests
# ==============================================================================

class TestDataClasses:
    """Test BatchResult and FeatureResult data classes."""

    def test_feature_result_creation(self):
        """Test FeatureResult data class creation.

        Arrange: Feature result parameters
        Act: Create FeatureResult instance
        Assert: All fields set correctly
        """
        feature_result = FeatureResult(
            feature_name="Add user login",
            status="success",
            duration_seconds=120.5,
            git_stats={'files_changed': 3},
            error=None
        )

        assert feature_result.feature_name == "Add user login"
        assert feature_result.status == "success"
        assert feature_result.duration_seconds == 120.5
        assert feature_result.git_stats['files_changed'] == 3
        assert feature_result.error is None

    def test_batch_result_creation(self):
        """Test BatchResult data class creation.

        Arrange: Batch result parameters
        Act: Create BatchResult instance
        Assert: All fields set correctly
        """
        feature_results = [
            FeatureResult("Feature 1", "success", 100, {}, None),
            FeatureResult("Feature 2", "failed", 50, {}, "Error message")
        ]

        batch_result = BatchResult(
            batch_id="batch-123",
            total_features=2,
            successful_features=1,
            failed_features=1,
            feature_results=feature_results,
            failed_feature_names=["Feature 2"],
            total_time_seconds=150
        )

        assert batch_result.batch_id == "batch-123"
        assert batch_result.total_features == 2
        assert batch_result.successful_features == 1
        assert len(batch_result.feature_results) == 2
        assert "Feature 2" in batch_result.failed_feature_names

    def test_batch_result_calculated_metrics(self):
        """Test BatchResult calculates success rate.

        Arrange: BatchResult with mixed results
        Act: Access success_rate property
        Assert: Correct percentage calculated
        """
        batch_result = BatchResult(
            batch_id="batch-123",
            total_features=10,
            successful_features=7,
            failed_features=3,
            feature_results=[],
            failed_feature_names=[],
            total_time_seconds=300
        )

        assert batch_result.success_rate == 70.0
