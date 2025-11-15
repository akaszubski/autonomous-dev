#!/usr/bin/env python3
"""
Integration Tests for /batch-implement Workflow (FAILING - Red Phase)

This module contains end-to-end integration tests for the /batch-implement
command workflow. Tests verify that all components work together correctly:
- File validation and parsing
- Sequential /auto-implement execution
- Automatic context clearing
- Git automation per feature
- Session logging and progress tracking
- Summary report generation

Integration Points:
1. BatchAutoImplement class orchestrates workflow
2. Task tool invokes /auto-implement for each feature
3. Context clearing between features
4. Git automation hooks (if enabled)
5. Session file logging
6. Summary generation

Performance Targets:
- Process 10 features in < 5 minutes (with mocking)
- Context stays under 8K tokens per feature
- Session file logs accurate metrics

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe integration requirements
- Tests should FAIL until batch_auto_implement.py is implemented
- Each test validates complete workflow

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
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

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
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def integration_project(tmp_path):
    """Create realistic project structure for integration testing."""
    project = tmp_path / "integration_project"
    project.mkdir()

    # Create project structure
    (project / ".claude").mkdir()
    (project / "src").mkdir()
    (project / "tests" / "unit").mkdir(parents=True)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "docs" / "sessions").mkdir(parents=True)
    (project / "logs").mkdir()
    (project / ".git").mkdir()

    # Create PROJECT.md
    project_md = project / ".claude" / "PROJECT.md"
    project_md.write_text("""
## GOALS
- Build authentication system
- Implement user management
- Add role-based access control

## SCOPE
- Authentication and authorization features
- User profile management
- Admin dashboard

## CONSTRAINTS
- Must use JWT for tokens
- Follow OWASP security guidelines
- 80% test coverage minimum

## ARCHITECTURE
- Layered architecture (API -> Business -> Data)
- RESTful API endpoints
- SQLite database for prototyping
""")

    # Create .env file
    env_file = project / ".env"
    env_file.write_text("""
AUTO_GIT_ENABLED=false
AUTO_GIT_PUSH=false
AUTO_GIT_PR=false
""")

    return project


@pytest.fixture
def realistic_features_file(tmp_path):
    """Create realistic features file with authentication features."""
    features_file = tmp_path / "auth_features.txt"
    features_file.write_text("""# Phase 1: Authentication Foundation
Add user registration endpoint
Add user login endpoint
Add JWT token generation

# Phase 2: User Management
Add user profile retrieval
Add password change endpoint
Add user deletion endpoint

# Phase 3: Authorization
Add role-based access control
Add admin middleware
Add permission checking
""")
    return features_file


@pytest.fixture
def batch_processor_integration(integration_project):
    """Create BatchAutoImplement instance for integration testing."""
    return BatchAutoImplement(
        project_root=integration_project,
        continue_on_failure=True,
        test_mode=True  # Enable test mode for temp paths
    )


# ==============================================================================
# End-to-End Workflow Tests
# ==============================================================================

class TestEndToEndWorkflow:
    """Test complete end-to-end batch implementation workflow."""

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_single_feature_complete_workflow(self, mock_clear, mock_task,
                                              batch_processor_integration, tmp_path):
        """Test complete workflow for single feature.

        Arrange: Single feature in file, mock successful execution
        Act: Execute batch workflow
        Assert: Feature processed, context cleared, summary generated
        """
        features_file = tmp_path / "single_feature.txt"
        features_file.write_text("Add user registration endpoint\n")

        # Mock successful Task execution
        mock_task_result = MagicMock(
            status="success",
            output={"message": "Feature completed successfully"},
            git_stats={
                'files_changed': 4,
                'lines_added': 120,
                'lines_removed': 15
            }
        )
        mock_task.return_value.__enter__.return_value = mock_task_result
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify workflow steps
        assert result.total_features == 1
        assert result.successful_features == 1
        assert result.failed_features == 0

        # Verify Task tool invoked
        assert mock_task.call_count == 1
        call_kwargs = mock_task.call_args[1]
        assert 'auto-implement' in call_kwargs['agent_file']
        assert 'Add user registration endpoint' in call_kwargs['description']

        # Verify context cleared
        assert mock_clear.call_count == 1

        # Verify summary can be generated
        summary = batch_processor_integration.generate_summary(result)
        assert "Total features: 1" in summary
        assert "Successful: 1" in summary

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_multiple_features_sequential_execution(self, mock_clear, mock_task,
                                                    batch_processor_integration,
                                                    realistic_features_file):
        """Test sequential execution of multiple features.

        Arrange: Multiple features from realistic file
        Act: Execute batch workflow
        Assert: All features processed sequentially, context cleared between each
        """
        # Track execution order and timing
        execution_log = []

        def mock_task_context(*args, **kwargs):
            feature = kwargs.get('description', '')
            start_time = time.time()
            execution_log.append({
                'feature': feature,
                'start_time': start_time
            })

            mock = MagicMock()
            mock.__enter__ = lambda self: MagicMock(
                status="success",
                git_stats={'files_changed': 2, 'lines_added': 50, 'lines_removed': 5}
            )
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_context
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(realistic_features_file)

        # Verify all features processed
        assert result.total_features == 9  # 9 features in realistic file
        assert result.successful_features == 9
        assert result.failed_features == 0

        # Verify sequential execution (no overlap)
        assert len(execution_log) == 9
        for i in range(len(execution_log) - 1):
            # Each feature should start after previous completes
            assert execution_log[i]['start_time'] <= execution_log[i + 1]['start_time']

        # Verify context cleared 9 times (once per feature)
        assert mock_clear.call_count == 9

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_workflow_with_failures_continue_mode(self, mock_clear, mock_task,
                                                  batch_processor_integration, tmp_path):
        """Test workflow continues after failures in continue-on-failure mode.

        Arrange: Features with some failures, continue_on_failure=True
        Act: Execute batch workflow
        Assert: All features attempted, failed ones tracked
        """
        features_file = tmp_path / "mixed_features.txt"
        features_file.write_text("""Add user registration endpoint
Add invalid feature that will fail
Add user login endpoint
Add another invalid feature
Add JWT token generation
""")

        # Mock some features to fail
        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            mock = MagicMock()

            if "invalid" in feature.lower():
                mock.__enter__ = lambda self: MagicMock(
                    status="failed",
                    error="Implementation failed: Invalid requirements"
                )
            else:
                mock.__enter__ = lambda self: MagicMock(
                    status="success",
                    git_stats={'files_changed': 3, 'lines_added': 80, 'lines_removed': 10}
                )

            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        mock_clear.return_value = True

        batch_processor_integration.continue_on_failure = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify all features attempted
        assert result.total_features == 5
        assert result.successful_features == 3
        assert result.failed_features == 2

        # Verify failed features tracked
        assert len(result.failed_feature_names) == 2
        assert any("invalid" in name.lower() for name in result.failed_feature_names)

        # Verify context cleared for all features (including failed)
        assert mock_clear.call_count == 5

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_workflow_abort_on_first_failure(self, mock_clear, mock_task,
                                            integration_project, tmp_path):
        """Test workflow aborts on first failure in abort mode.

        Arrange: Features with second one failing, continue_on_failure=False
        Act: Execute batch workflow
        Assert: Execution stops after first failure
        """
        features_file = tmp_path / "abort_test.txt"
        features_file.write_text("""Add user registration endpoint
Add invalid feature that will fail
Add user login endpoint
""")

        # Track which features were attempted
        attempted_features = []

        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            attempted_features.append(feature)
            mock = MagicMock()

            if "invalid" in feature.lower():
                mock.__enter__ = lambda self: MagicMock(
                    status="failed",
                    error="Feature validation failed"
                )
            else:
                mock.__enter__ = lambda self: MagicMock(status="success")

            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        mock_clear.return_value = True

        # Create processor with abort-on-failure mode
        processor = BatchAutoImplement(
            project_root=integration_project,
            continue_on_failure=False
        )

        # Execute workflow - should raise exception
        from batch_auto_implement import BatchExecutionError
        with pytest.raises(BatchExecutionError) as exc_info:
            processor.execute_batch(features_file)

        # Verify only first two features attempted
        assert len(attempted_features) == 2
        assert "Add user registration endpoint" in attempted_features[0]
        assert "invalid feature" in attempted_features[1].lower()

        # Third feature should not have been attempted
        assert not any("login" in f.lower() for f in attempted_features)

        # Verify error message
        assert "aborted" in str(exc_info.value).lower()


# ==============================================================================
# Context Management Integration Tests
# ==============================================================================

class TestContextManagementIntegration:
    """Test context management integration with real workflow."""

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    @patch('batch_auto_implement.measure_context_size')
    def test_context_stays_under_limit(self, mock_measure, mock_clear, mock_task,
                                      batch_processor_integration, tmp_path):
        """Test that context stays under 8K tokens between features.

        Arrange: Multiple features, mock context measurement
        Act: Execute batch
        Assert: Context measured and cleared, stays under limit
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
Add password reset
""")

        # Mock context size measurement
        context_sizes = []

        def mock_measure_side_effect():
            size = 7500  # Just under 8K limit
            context_sizes.append(size)
            return size

        mock_measure.side_effect = mock_measure_side_effect
        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify context measured after each feature
        assert len(context_sizes) == 3

        # Verify all measurements under 8K
        assert all(size < 8000 for size in context_sizes)

        # Verify clear called to prevent bloat
        assert mock_clear.call_count == 3

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_context_clearing_failure_handling(self, mock_clear, mock_task,
                                               batch_processor_integration, tmp_path):
        """Test graceful handling when context clearing fails.

        Arrange: Context clear command fails
        Act: Execute batch
        Assert: Workflow continues, warning logged
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
""")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None

        # Mock clear to fail
        clear_call_count = [0]

        def mock_clear_side_effect():
            clear_call_count[0] += 1
            if clear_call_count[0] == 1:
                raise Exception("Clear command failed")
            return True

        mock_clear.side_effect = mock_clear_side_effect

        # Execute workflow - should not raise exception
        result = batch_processor_integration.execute_batch(features_file)

        # Verify workflow completed despite clear failure
        assert result.successful_features == 2

        # Verify clear was attempted for both features
        assert clear_call_count[0] == 2


# ==============================================================================
# Git Automation Integration Tests
# ==============================================================================

class TestGitAutomationIntegration:
    """Test git automation integration per feature."""

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    @patch('batch_auto_implement.git_operations')
    def test_git_automation_per_feature(self, mock_git, mock_clear, mock_task,
                                       batch_processor_integration, tmp_path):
        """Test that git operations execute for each feature if enabled.

        Arrange: Features with AUTO_GIT_ENABLED=true
        Act: Execute batch
        Assert: Git commit/push per feature
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
""")

        # Enable git automation
        with patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true'}):
            mock_task.return_value.__enter__.return_value = MagicMock(
                status="success",
                git_stats={'files_changed': 2}
            )
            mock_task.return_value.__exit__ = lambda self, *args: None
            mock_clear.return_value = True
            mock_git.auto_commit_and_push.return_value = {
                'success': True,
                'commit_sha': 'abc123'
            }

            # Execute workflow
            result = batch_processor_integration.execute_batch(features_file)

            # Verify git operations called per feature
            # Note: Actual implementation depends on git automation design
            assert result.successful_features == 2

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_git_stats_aggregation(self, mock_clear, mock_task,
                                   batch_processor_integration, tmp_path):
        """Test that git statistics are aggregated across features.

        Arrange: Features with varying git stats
        Act: Execute batch
        Assert: Summary contains aggregated stats
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
Add password reset
""")

        # Mock different git stats per feature
        git_stats_sequence = [
            {'files_changed': 3, 'lines_added': 80, 'lines_removed': 10},
            {'files_changed': 2, 'lines_added': 45, 'lines_removed': 5},
            {'files_changed': 4, 'lines_added': 120, 'lines_removed': 20},
        ]

        call_count = [0]

        def mock_task_side_effect(*args, **kwargs):
            stats = git_stats_sequence[call_count[0]]
            call_count[0] += 1

            mock = MagicMock()
            mock.__enter__ = lambda self: MagicMock(
                status="success",
                git_stats=stats
            )
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify git stats aggregated
        summary = batch_processor_integration.generate_summary(result)

        # Should show total files changed, lines added/removed
        assert "files changed" in summary.lower()
        # Total: 3+2+4 = 9 files, 80+45+120 = 245 lines added, 10+5+20 = 35 removed


# ==============================================================================
# Session Logging Integration Tests
# ==============================================================================

class TestSessionLoggingIntegration:
    """Test session file logging integration."""

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_session_file_created_with_metadata(self, mock_clear, mock_task,
                                                batch_processor_integration,
                                                integration_project, tmp_path):
        """Test that session file is created with batch metadata.

        Arrange: Batch execution
        Act: Execute batch
        Assert: Session file created in docs/sessions/ with metadata
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("Add user registration\n")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify session file created
        session_dir = integration_project / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))

        assert len(session_files) > 0

        # Verify session file contains batch metadata
        with open(session_files[-1], 'r') as f:
            session_data = json.load(f)

        assert 'batch_id' in session_data
        assert 'timestamp' in session_data
        assert 'total_features' in session_data
        assert session_data['total_features'] == 1

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_session_file_logs_feature_progress(self, mock_clear, mock_task,
                                                batch_processor_integration,
                                                integration_project, tmp_path):
        """Test that session file logs progress for each feature.

        Arrange: Multiple features
        Act: Execute batch
        Assert: Session file contains entry per feature with status
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
Add password reset
""")

        mock_task.return_value.__enter__.return_value = MagicMock(status="success")
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify session file has entries for all features
        session_dir = integration_project / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))

        with open(session_files[-1], 'r') as f:
            session_data = json.load(f)

        assert 'features' in session_data
        assert len(session_data['features']) == 3

        # Verify each feature entry has status and timing
        for feature_entry in session_data['features']:
            assert 'name' in feature_entry
            assert 'status' in feature_entry
            assert 'duration_seconds' in feature_entry

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_session_file_logs_failures(self, mock_clear, mock_task,
                                       batch_processor_integration,
                                       integration_project, tmp_path):
        """Test that session file logs failure details.

        Arrange: Features with failures
        Act: Execute batch with continue_on_failure
        Assert: Session file contains error details for failed features
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add invalid feature
""")

        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            mock = MagicMock()

            if "invalid" in feature.lower():
                mock.__enter__ = lambda self: MagicMock(
                    status="failed",
                    error="Validation failed: Invalid requirements"
                )
            else:
                mock.__enter__ = lambda self: MagicMock(status="success")

            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify session file has error details
        session_dir = integration_project / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))

        with open(session_files[-1], 'r') as f:
            session_data = json.load(f)

        # Find failed feature entry
        failed_entries = [f for f in session_data['features'] if f['status'] == 'failed']
        assert len(failed_entries) == 1
        assert 'error' in failed_entries[0]
        assert "Validation failed" in failed_entries[0]['error']


# ==============================================================================
# Performance Integration Tests
# ==============================================================================

class TestPerformanceIntegration:
    """Test performance characteristics of batch workflow."""

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_ten_features_under_five_minutes(self, mock_clear, mock_task,
                                            batch_processor_integration, tmp_path):
        """Test that 10 features complete in under 5 minutes (with mocking).

        Arrange: 10 features in file
        Act: Execute batch with minimal mock delays
        Assert: Total time under 5 minutes
        """
        features_file = tmp_path / "ten_features.txt"
        features = [f"Add feature {i}" for i in range(10)]
        features_file.write_text("\n".join(features))

        # Mock with minimal delay
        def mock_task_context(*args, **kwargs):
            time.sleep(0.01)  # 10ms delay per feature
            mock = MagicMock()
            mock.__enter__ = lambda self: MagicMock(status="success")
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_context
        mock_clear.return_value = True

        # Execute workflow
        start_time = time.time()
        result = batch_processor_integration.execute_batch(features_file)
        elapsed_time = time.time() - start_time

        # Verify completed successfully
        assert result.successful_features == 10

        # Verify under 5 minutes (300 seconds)
        # With mocking, should be very fast (< 1 second)
        assert elapsed_time < 300

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_timing_accuracy(self, mock_clear, mock_task,
                            batch_processor_integration, tmp_path):
        """Test that timing measurements are accurate.

        Arrange: Features with known delays
        Act: Execute batch
        Assert: Recorded times match actual execution times
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
""")

        # Mock with specific delays
        delays = [0.1, 0.2]  # 100ms and 200ms
        call_count = [0]

        def mock_task_context(*args, **kwargs):
            delay = delays[call_count[0]]
            call_count[0] += 1
            time.sleep(delay)

            mock = MagicMock()
            mock.__enter__ = lambda self: MagicMock(status="success")
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_context
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)

        # Verify timing accuracy (within 10% tolerance)
        assert result.feature_results[0].duration_seconds >= 0.09  # 100ms - tolerance
        assert result.feature_results[0].duration_seconds <= 0.15  # 100ms + tolerance
        assert result.feature_results[1].duration_seconds >= 0.18  # 200ms - tolerance
        assert result.feature_results[1].duration_seconds <= 0.25  # 200ms + tolerance


# ==============================================================================
# Summary Report Integration Tests
# ==============================================================================

class TestSummaryReportIntegration:
    """Test summary report generation in realistic scenarios."""

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_summary_with_mixed_results(self, mock_clear, mock_task,
                                       batch_processor_integration, tmp_path):
        """Test summary generation with mixed success/failure.

        Arrange: Batch with successes and failures
        Act: Generate summary
        Assert: Summary includes all relevant metrics
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add invalid feature 1
Add user login
Add invalid feature 2
Add password reset
""")

        def mock_task_side_effect(*args, **kwargs):
            feature = kwargs.get('description', '')
            mock = MagicMock()

            if "invalid" in feature.lower():
                mock.__enter__ = lambda self: MagicMock(
                    status="failed",
                    error="Implementation failed"
                )
            else:
                mock.__enter__ = lambda self: MagicMock(
                    status="success",
                    git_stats={'files_changed': 3, 'lines_added': 75, 'lines_removed': 12}
                )

            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)
        summary = batch_processor_integration.generate_summary(result)

        # Verify summary completeness
        assert "Total features: 5" in summary
        assert "Successful: 3" in summary
        assert "Failed: 2" in summary
        assert "Success rate: 60.0%" in summary
        assert "Failed features:" in summary
        assert "Add invalid feature 1" in summary
        assert "Add invalid feature 2" in summary

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_summary_with_all_successes(self, mock_clear, mock_task,
                                       batch_processor_integration, tmp_path):
        """Test summary generation when all features succeed.

        Arrange: All features successful
        Act: Generate summary
        Assert: Summary shows 100% success rate
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
Add password reset
""")

        mock_task.return_value.__enter__.return_value = MagicMock(
            status="success",
            git_stats={'files_changed': 2, 'lines_added': 50, 'lines_removed': 5}
        )
        mock_task.return_value.__exit__ = lambda self, *args: None
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)
        summary = batch_processor_integration.generate_summary(result)

        # Verify success summary
        assert "Total features: 3" in summary
        assert "Successful: 3" in summary
        assert "Failed: 0" in summary
        assert "Success rate: 100.0%" in summary
        assert "Failed features:" not in summary or "None" in summary

    @patch('batch_auto_implement.Task')
    @patch('batch_auto_implement.execute_clear_command')
    def test_summary_includes_git_metrics(self, mock_clear, mock_task,
                                         batch_processor_integration, tmp_path):
        """Test that summary includes aggregated git metrics.

        Arrange: Features with git statistics
        Act: Generate summary
        Assert: Summary shows total git changes
        """
        features_file = tmp_path / "features.txt"
        features_file.write_text("""Add user registration
Add user login
""")

        # Mock git stats
        git_stats_sequence = [
            {'files_changed': 4, 'lines_added': 100, 'lines_removed': 15},
            {'files_changed': 3, 'lines_added': 75, 'lines_removed': 10},
        ]

        call_count = [0]

        def mock_task_side_effect(*args, **kwargs):
            stats = git_stats_sequence[call_count[0]]
            call_count[0] += 1

            mock = MagicMock()
            mock.__enter__ = lambda self: MagicMock(
                status="success",
                git_stats=stats
            )
            mock.__exit__ = lambda self, *args: None
            return mock

        mock_task.side_effect = mock_task_side_effect
        mock_clear.return_value = True

        # Execute workflow
        result = batch_processor_integration.execute_batch(features_file)
        summary = batch_processor_integration.generate_summary(result)

        # Verify git metrics in summary
        # Total: 4+3=7 files, 100+75=175 added, 15+10=25 removed
        assert "7" in summary  # files changed
        assert "175" in summary  # lines added
        assert "25" in summary  # lines removed
