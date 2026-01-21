#!/usr/bin/env python3
"""
Unit tests for auto_implement_pipeline.py.

Tests the auto-implement pipeline integration for progress tracker including:
- ProgressTrackerResult namedtuple
- invoke_progress_tracker function
- execute_step8_parallel_validation function
- Helper functions for updating PROJECT.md

Issue: #234 (Test coverage improvement)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Add project root to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.auto_implement_pipeline import (
    ProgressTrackerResult,
    invoke_progress_tracker,
    invoke_reviewer,
    invoke_security_auditor,
    invoke_doc_master,
    auto_git_workflow,
    execute_step8_parallel_validation,
    _find_project_md,
    _update_stage_status,
    _update_issue_reference,
    _update_timestamp,
)


class TestProgressTrackerResult:
    """Test ProgressTrackerResult namedtuple."""

    def test_success_result(self):
        """Create successful result."""
        result = ProgressTrackerResult(
            success=True,
            project_md_updated=True,
            error=None,
            updates_made=["Stage status", "Timestamp"]
        )
        assert result.success is True
        assert result.project_md_updated is True
        assert result.error is None
        assert len(result.updates_made) == 2

    def test_failure_result(self):
        """Create failure result."""
        result = ProgressTrackerResult(
            success=False,
            project_md_updated=False,
            error="PROJECT.md not found"
        )
        assert result.success is False
        assert result.error == "PROJECT.md not found"

    def test_default_updates_made(self):
        """Default updates_made is empty list."""
        result = ProgressTrackerResult(
            success=True,
            project_md_updated=False
        )
        assert result.updates_made == []


class TestInvokeProgressTracker:
    """Test invoke_progress_tracker function."""

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline._find_project_md')
    def test_returns_failure_when_project_md_not_found(self, mock_find):
        """Return failure when PROJECT.md not found."""
        mock_find.return_value = None

        result = invoke_progress_tracker(issue_number=123)

        assert result.success is False
        assert "PROJECT.md not found" in result.error

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline._find_project_md')
    @patch('builtins.open', new_callable=mock_open, read_data="**Last Updated**: 2026-01-01")
    def test_updates_timestamp(self, mock_file, mock_find):
        """Update timestamp in PROJECT.md."""
        mock_find.return_value = Path("/fake/PROJECT.md")

        result = invoke_progress_tracker(issue_number=123)

        assert result.success is True
        assert "Last Updated timestamp" in result.updates_made

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline._find_project_md')
    @patch('builtins.open', new_callable=mock_open, read_data="**Stage**: planning\n**Last Updated**: 2026-01-01")
    def test_updates_stage_status(self, mock_file, mock_find):
        """Update stage status in PROJECT.md."""
        mock_find.return_value = Path("/fake/PROJECT.md")

        result = invoke_progress_tracker(stage="implementing")

        assert result.success is True
        assert "Stage status" in result.updates_made

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline._find_project_md')
    @patch('builtins.open', new_callable=mock_open, read_data="**Last Updated**: 2026-01-01")
    def test_adds_issue_reference(self, mock_file, mock_find):
        """Add issue reference to PROJECT.md."""
        mock_find.return_value = Path("/fake/PROJECT.md")

        result = invoke_progress_tracker(issue_number=456)

        assert result.success is True
        assert "Issue #456 reference" in result.updates_made

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline._find_project_md')
    @patch('builtins.open', new_callable=mock_open, read_data="Content without markers")
    def test_no_updates_when_no_markers(self, mock_file, mock_find):
        """No updates when PROJECT.md has no markers."""
        mock_find.return_value = Path("/fake/PROJECT.md")

        result = invoke_progress_tracker()

        assert result.success is True
        assert result.project_md_updated is False
        assert result.updates_made == []

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline._find_project_md')
    @patch('builtins.open')
    def test_handles_read_error(self, mock_file, mock_find):
        """Handle file read errors gracefully."""
        mock_find.return_value = Path("/fake/PROJECT.md")
        mock_file.side_effect = IOError("Read error")

        result = invoke_progress_tracker()

        assert result.success is False
        assert result.error is not None

    def test_accepts_context_dict(self):
        """Accept legacy context dict."""
        with patch('plugins.autonomous_dev.lib.auto_implement_pipeline._find_project_md') as mock_find:
            mock_find.return_value = None

            context = {"issue_number": 789, "stage": "testing", "workflow_id": "wf-123"}
            result = invoke_progress_tracker(context=context)

            # Should still fail (no PROJECT.md) but shows context was parsed
            assert result.success is False


class TestStubFunctions:
    """Test stub functions for pipeline integration."""

    def test_invoke_reviewer(self):
        """invoke_reviewer returns success."""
        result = invoke_reviewer({})
        assert result["success"] is True

    def test_invoke_security_auditor(self):
        """invoke_security_auditor returns success."""
        result = invoke_security_auditor({})
        assert result["success"] is True

    def test_invoke_doc_master(self):
        """invoke_doc_master returns success."""
        result = invoke_doc_master({})
        assert result["success"] is True

    def test_auto_git_workflow(self):
        """auto_git_workflow returns success."""
        result = auto_git_workflow({})
        assert result["success"] is True


class TestExecuteStep8ParallelValidation:
    """Test execute_step8_parallel_validation function."""

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline.invoke_progress_tracker')
    def test_invokes_progress_tracker(self, mock_tracker):
        """Step 8 invokes progress tracker."""
        mock_tracker.return_value = ProgressTrackerResult(
            success=True, project_md_updated=True, updates_made=["test"]
        )

        context = {"issue_number": 100, "stage": "validating", "workflow_id": "wf-test"}
        results = execute_step8_parallel_validation(context)

        mock_tracker.assert_called_once()
        assert results["progress_tracker"].success is True

    @patch('plugins.autonomous_dev.lib.auto_implement_pipeline.invoke_progress_tracker')
    def test_returns_all_result_keys(self, mock_tracker):
        """Step 8 returns all expected keys."""
        mock_tracker.return_value = ProgressTrackerResult(
            success=True, project_md_updated=False
        )

        results = execute_step8_parallel_validation({})

        assert "reviewer" in results
        assert "security_auditor" in results
        assert "doc_master" in results
        assert "progress_tracker" in results


class TestFindProjectMd:
    """Test _find_project_md helper function."""

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_symlink')
    def test_finds_claude_project_md(self, mock_symlink, mock_exists):
        """Find PROJECT.md in .claude directory."""
        def exists_side_effect(self=None):
            return str(self) == ".claude/PROJECT.md" if hasattr(self, '__str__') else False

        # Mock Path.exists to return True only for first path
        mock_exists.side_effect = [True, False, False, False]
        mock_symlink.return_value = False

        result = _find_project_md()

        assert result == Path(".claude/PROJECT.md")

    @patch('pathlib.Path.exists')
    def test_returns_none_when_not_found(self, mock_exists):
        """Return None when PROJECT.md not found anywhere."""
        mock_exists.return_value = False

        result = _find_project_md()

        assert result is None


class TestUpdateStageStatus:
    """Test _update_stage_status helper function."""

    def test_updates_bold_stage_pattern(self):
        """Update **Stage**: pattern."""
        content = "Some text\n**Stage**: planning\nMore text"

        new_content, updated = _update_stage_status(content, "implementing")

        assert updated is True
        assert "**Stage**: implementing" in new_content

    def test_updates_current_stage_pattern(self):
        """Update Current stage: pattern."""
        content = "Some text\nCurrent stage: planning\nMore text"

        new_content, updated = _update_stage_status(content, "testing")

        assert updated is True
        assert "Current stage: testing" in new_content

    def test_no_update_when_no_pattern(self):
        """No update when no stage pattern found."""
        content = "Content without stage markers"

        new_content, updated = _update_stage_status(content, "testing")

        assert updated is False
        assert new_content == content


class TestUpdateIssueReference:
    """Test _update_issue_reference helper function."""

    def test_adds_issue_to_last_updated(self):
        """Add issue reference to Last Updated line."""
        content = "**Last Updated**: 2026-01-15"

        new_content, updated = _update_issue_reference(content, 123)

        assert updated is True
        assert "Issue #123" in new_content

    def test_no_duplicate_reference(self):
        """Don't add duplicate issue reference."""
        content = "**Last Updated**: 2026-01-15 (Issue #123)"

        new_content, updated = _update_issue_reference(content, 123)

        assert updated is False
        assert new_content == content

    def test_no_update_when_no_suitable_location(self):
        """No update when no suitable location found."""
        content = "Content without Last Updated or Issues section"

        new_content, updated = _update_issue_reference(content, 999)

        assert updated is False


class TestUpdateTimestamp:
    """Test _update_timestamp helper function."""

    def test_updates_existing_timestamp(self):
        """Update existing timestamp."""
        content = "**Last Updated**: 2025-01-01"
        today = datetime.now().strftime("%Y-%m-%d")

        new_content, updated = _update_timestamp(content)

        assert updated is True
        assert today in new_content

    def test_adds_issue_number_to_timestamp(self):
        """Add issue number to timestamp."""
        content = "**Last Updated**: 2025-01-01"

        new_content, updated = _update_timestamp(content, issue_number=456)

        assert updated is True
        assert "Issue #456" in new_content

    def test_no_update_when_no_timestamp_pattern(self):
        """No update when no timestamp pattern found."""
        content = "Content without timestamp"

        new_content, updated = _update_timestamp(content)

        assert updated is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
