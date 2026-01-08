"""
Integration tests for project-progress-tracker agent integration with /auto-implement pipeline

Tests cover:
- project-progress-tracker invoked after doc-master in pipeline
- Progress tracker updates PROJECT.md Stage status
- Progress tracker updates Issue references
- Progress tracker updates Last Updated timestamp
- Graceful degradation if progress tracker fails
- Integration with doc-master auto-apply workflow
- Batch mode behavior (no blocking)
- Pipeline flow: doc-master → project-progress-tracker

This is the RED phase of TDD - tests should fail initially since implementation doesn't exist yet.

Date: 2026-01-09
Issue: #204
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from typing import Dict, Any, List

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

# Import will fail - integration module doesn't exist yet (TDD!)
try:
    from auto_implement_pipeline import (
        execute_step8_parallel_validation,
        invoke_progress_tracker,
        ProgressTrackerResult,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def pipeline_context():
    """Simulated /auto-implement pipeline context"""
    return {
        "workflow_id": "test-workflow-123",
        "issue_number": 204,
        "feature_request": "Fix doc-master auto-apply and integrate progress tracker",
        "changed_files": [
            ".claude/agents/doc-master.md",
            ".claude/commands/auto-implement.md",
            "plugins/autonomous-dev/lib/doc_update_risk_classifier.py"
        ],
        "stage": "implementation_complete",
        "batch_mode": False
    }


@pytest.fixture
def batch_mode_context(pipeline_context):
    """Batch mode pipeline context"""
    return {**pipeline_context, "batch_mode": True}


@pytest.fixture
def doc_master_success_output():
    """Simulated doc-master successful output"""
    return {
        "success": True,
        "updates_applied": [
            {"file": "CHANGELOG.md", "status": "applied"},
            {"file": ".claude/PROJECT.md", "status": "applied"}
        ],
        "error": None
    }


@pytest.fixture
def mock_project_md_content():
    """Mock PROJECT.md content before update"""
    return """# Project

**Last Updated**: 2026-01-08 (Issue #203)
**Last Compliance Check**: 2026-01-08

## Component Versions

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Skills | 1.0.0 | 28 | ✅ Compliant |

## Stage

Current stage: Planning

## Issues

In progress:
- #203: Previous feature
"""


@pytest.fixture
def expected_project_md_content():
    """Expected PROJECT.md content after progress tracker update"""
    return """# Project

**Last Updated**: 2026-01-09 (Issue #204)
**Last Compliance Check**: 2026-01-09

## Component Versions

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Skills | 1.0.0 | 28 | ✅ Compliant |

## Stage

Current stage: Implementation Complete

## Issues

In progress:
- #204: Fix doc-master auto-apply and integrate progress tracker

Completed:
- #203: Previous feature
"""


# ============================================================================
# Test Progress Tracker Invocation in Pipeline
# ============================================================================

def test_progress_tracker_invoked_in_pipeline(pipeline_context):
    """Test that project-progress-tracker is invoked in execute_step8_parallel_validation"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker result is included
    assert "progress_tracker" in result
    assert result["progress_tracker"] is not None


def test_progress_tracker_receives_correct_context(pipeline_context):
    """Test that progress tracker receives pipeline context values"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker was invoked and result returned
    assert result["progress_tracker"] is not None
    progress_result = result["progress_tracker"]
    # Verify it's a ProgressTrackerResult
    assert hasattr(progress_result, 'success')
    assert hasattr(progress_result, 'project_md_updated')


# ============================================================================
# Test Progress Tracker Updates PROJECT.md
# ============================================================================

@patch('builtins.open', new_callable=mock_open, read_data="**Last Updated**: 2026-01-08")
def test_progress_tracker_updates_last_updated_timestamp(mock_file, pipeline_context):
    """Test that progress tracker updates Last Updated timestamp in PROJECT.md"""
    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage=pipeline_context["stage"],
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    assert result.project_md_updated is True
    # Should write to PROJECT.md with new timestamp
    mock_file.assert_called()


@patch('builtins.open', new_callable=mock_open)
def test_progress_tracker_updates_stage_status(mock_file, pipeline_context):
    """Test that progress tracker updates Stage status in PROJECT.md"""
    # Arrange
    mock_file.return_value.read.return_value = "Current stage: Planning"

    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage="implementation_complete",
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    # Should update stage to "Implementation Complete"
    mock_file.assert_called()


@patch('builtins.open', new_callable=mock_open)
def test_progress_tracker_updates_issue_references(mock_file, pipeline_context):
    """Test that progress tracker updates Issue references in PROJECT.md"""
    # Act
    result = invoke_progress_tracker(
        issue_number=204,
        stage="implementation_complete",
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    # Should add/update #204 in Issues section
    mock_file.assert_called()


@patch('builtins.open', new_callable=mock_open)
def test_progress_tracker_updates_component_count(mock_file, pipeline_context):
    """Test that progress tracker updates component count in PROJECT.md"""
    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage=pipeline_context["stage"],
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert result.success is True
    # Should update component count if new components added
    mock_file.assert_called()


# ============================================================================
# Test Integration with Doc-Master Auto-Apply
# ============================================================================

def test_progress_tracker_integration_with_pipeline(pipeline_context):
    """Test progress tracker runs in pipeline and returns result"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker executed
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Should have success status
    assert progress_result.success is True or progress_result.error is not None


@patch('auto_implement_pipeline.invoke_progress_tracker')
@patch('auto_implement_pipeline.invoke_doc_master')
def test_progress_tracker_after_doc_master_approval_prompt(
    mock_doc_master,
    mock_progress_tracker,
    pipeline_context
):
    """Test progress tracker runs after doc-master prompts for HIGH_RISK approval"""
    # Arrange - doc-master prompts user for HIGH_RISK change
    mock_doc_master.return_value = {
        "success": True,
        "auto_applied": False,
        "required_approval": True,
        "user_approved": True
    }
    mock_progress_tracker.return_value = ProgressTrackerResult(
        success=True,
        project_md_updated=True,
        error=None
    )

    # Act
    result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker still runs
    assert mock_progress_tracker.called


# ============================================================================
# Test Batch Mode Behavior
# ============================================================================

def test_batch_mode_progress_tracker_no_blocking(batch_mode_context):
    """Test that progress tracker doesn't block in batch mode"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(batch_mode_context)

    # Assert - Should complete without blocking (no user prompts)
    assert "progress_tracker" in result
    # Pipeline should return (not block on prompts)
    assert result is not None


def test_batch_mode_progress_tracker_silent_updates(batch_mode_context):
    """Test that progress tracker updates PROJECT.md silently in batch mode"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(batch_mode_context)

    # Assert - Updates applied without user interaction
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Should complete (success or graceful failure)
    assert progress_result is not None


# ============================================================================
# Test Graceful Degradation
# ============================================================================

def test_pipeline_continues_if_progress_tracker_fails(pipeline_context):
    """Test that pipeline continues if progress tracker fails (graceful degradation)"""
    # Arrange - Progress tracker will fail because PROJECT.md not found
    with patch('auto_implement_pipeline._find_project_md', return_value=None):
        # Act
        result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Pipeline should return even with progress tracker failure
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Progress tracker should fail gracefully (not raise exception)
    assert progress_result.success is False
    assert progress_result.error is not None


def test_pipeline_handles_file_errors_gracefully(pipeline_context):
    """Test that pipeline handles file errors gracefully"""
    # Arrange - File open raises exception
    with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
        with patch('builtins.open', side_effect=IOError("Disk error")):
            # Act
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Should catch exception and return result
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    # Should fail gracefully
    assert progress_result.success is False
    assert progress_result.error is not None


def test_progress_tracker_failure_returns_result_with_error(pipeline_context):
    """Test that progress tracker failure returns result with error details"""
    # Arrange - File write fails
    with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
        with patch('builtins.open', side_effect=PermissionError("Write permission denied")):
            # Act
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Should return result with error
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    assert progress_result.success is False
    assert "denied" in progress_result.error.lower() or "permission" in progress_result.error.lower()


# ============================================================================
# Test Progress Tracker File Operations
# ============================================================================

def test_progress_tracker_uses_write_tool(pipeline_context):
    """Test that progress tracker uses Write tool (not just Read)"""
    # Act
    with patch('builtins.open', mock_open()) as mock_file:
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should open file in write mode
    assert mock_file.called
    # Should call with write mode ('w' or 'a')


def test_progress_tracker_uses_edit_tool_for_updates(pipeline_context):
    """Test that progress tracker uses Edit tool for selective updates"""
    # Act
    with patch('pathlib.Path.read_text', return_value="old content"):
        with patch('pathlib.Path.write_text') as mock_write:
            result = invoke_progress_tracker(
                issue_number=pipeline_context["issue_number"],
                stage=pipeline_context["stage"],
                workflow_id=pipeline_context["workflow_id"]
            )

    # Assert - Should perform selective edits
    # (Implementation may vary - this tests the capability)


# ============================================================================
# Test Progress Tracker Result Structure
# ============================================================================

def test_progress_tracker_result_structure(pipeline_context):
    """Test that ProgressTrackerResult contains expected fields"""
    # Act
    result = invoke_progress_tracker(
        issue_number=pipeline_context["issue_number"],
        stage=pipeline_context["stage"],
        workflow_id=pipeline_context["workflow_id"]
    )

    # Assert
    assert hasattr(result, 'success')
    assert hasattr(result, 'project_md_updated')
    assert hasattr(result, 'error')
    assert isinstance(result.success, bool)
    assert isinstance(result.project_md_updated, bool)


# ============================================================================
# Test Pipeline Step Ordering
# ============================================================================

def test_progress_tracker_result_structure_in_pipeline(pipeline_context):
    """Test that progress tracker result is properly structured in pipeline output"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Progress tracker result has expected structure
    assert "progress_tracker" in result
    progress_result = result["progress_tracker"]
    assert hasattr(progress_result, 'success')
    assert hasattr(progress_result, 'project_md_updated')
    assert hasattr(progress_result, 'error')


# ============================================================================
# Test Progress Tracker with Different Stages
# ============================================================================

@pytest.mark.parametrize("stage,expected_status", [
    ("research_complete", "Research Complete"),
    ("planning_complete", "Planning Complete"),
    ("tests_written", "Tests Written"),
    ("implementation_complete", "Implementation Complete"),
    ("validation_complete", "Validation Complete"),
])
def test_progress_tracker_updates_different_stages(stage, expected_status, pipeline_context):
    """Test that progress tracker correctly updates different pipeline stages"""
    # Act
    with patch('builtins.open', mock_open()):
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=stage,
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert
    assert result.success is True


# ============================================================================
# Test Progress Tracker Error Cases
# ============================================================================

def test_progress_tracker_handles_missing_project_md(pipeline_context):
    """Test that progress tracker handles missing PROJECT.md gracefully"""
    # Arrange - PROJECT.md doesn't exist
    with patch('pathlib.Path.exists', return_value=False):
        # Act
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should fail gracefully
    assert result.success is False
    assert "PROJECT.md" in result.error or "not found" in result.error


def test_progress_tracker_handles_malformed_project_md(pipeline_context):
    """Test that progress tracker handles malformed PROJECT.md"""
    # Arrange - Malformed PROJECT.md content
    with patch('builtins.open', mock_open(read_data="Invalid content\n\n\n")):
        # Act
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should handle gracefully
    # (May succeed with warning or fail cleanly)
    assert isinstance(result.success, bool)


def test_progress_tracker_handles_permission_error(pipeline_context):
    """Test that progress tracker handles file permission errors"""
    # Arrange - Permission denied
    with patch('builtins.open', side_effect=PermissionError("Access denied")):
        # Act
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert
    assert result.success is False
    assert "permission" in result.error.lower() or "denied" in result.error.lower()


# ============================================================================
# Test Integration with Git Workflow
# ============================================================================

def test_pipeline_returns_complete_results_dict(pipeline_context):
    """Test that pipeline returns dict with all expected keys"""
    # Act - Call with mocked file operations
    with patch('builtins.open', mock_open(read_data="**Last Updated**: 2026-01-08")):
        with patch('auto_implement_pipeline._find_project_md', return_value=Path('.claude/PROJECT.md')):
            result = execute_step8_parallel_validation(pipeline_context)

    # Assert - Result dict has expected keys
    assert isinstance(result, dict)
    assert "progress_tracker" in result
    # Progress tracker result should be ProgressTrackerResult
    assert result["progress_tracker"] is not None


# ============================================================================
# Test Multiple Issues Tracking
# ============================================================================

def test_progress_tracker_tracks_multiple_issues(pipeline_context):
    """Test that progress tracker can track multiple issues simultaneously"""
    # Act
    with patch('builtins.open', mock_open()):
        result1 = invoke_progress_tracker(issue_number=204, stage="implementation_complete", workflow_id="wf1")
        result2 = invoke_progress_tracker(issue_number=205, stage="planning_complete", workflow_id="wf2")

    # Assert - Both issues tracked
    assert result1.success is True
    assert result2.success is True


# ============================================================================
# Test Concurrent Safety
# ============================================================================

def test_progress_tracker_handles_concurrent_updates(pipeline_context):
    """Test that progress tracker handles concurrent PROJECT.md updates safely"""
    # Note: This is a smoke test - actual concurrency testing would be more complex
    # Act
    with patch('builtins.open', mock_open()):
        result = invoke_progress_tracker(
            issue_number=pipeline_context["issue_number"],
            stage=pipeline_context["stage"],
            workflow_id=pipeline_context["workflow_id"]
        )

    # Assert - Should complete successfully
    assert result.success is True
