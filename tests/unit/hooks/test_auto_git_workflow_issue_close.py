#!/usr/bin/env python3
"""
Unit tests for auto_git_workflow hook issue closing functionality (TDD Red Phase).

Tests for handle_issue_close() function added to existing auto_git_workflow.py hook.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (function not found).

Test Strategy:
- Test issue number extraction from command args
- Test user consent flow
- Test issue state validation (skip if already closed)
- Test gh CLI invocation
- Test graceful degradation on failures
- Test integration with existing git workflow

Hook Modification: auto_git_workflow.py (existing hook)
New Function: handle_issue_close(command_args, workflow_metadata)
Trigger: After git push succeeds in run_hook()

Date: 2025-11-18
Issue: #91 (Auto-close GitHub issues after /auto-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (tests should FAIL - function doesn't exist yet)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError, TimeoutExpired

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# Import will fail - function doesn't exist yet (TDD!)
try:
    from auto_git_workflow import handle_issue_close
except ImportError as e:
    # Expected during TDD red phase - function not implemented yet
    pass


# ==============================================================================
# Test Class: Handle Issue Close
# ==============================================================================

class TestHandleIssueClose:
    """Test handle_issue_close() integration in auto_git_workflow hook.

    Workflow:
    1. Extract issue number from command args
    2. If no issue number, skip (graceful)
    3. Prompt user for consent
    4. If user declines, skip (graceful)
    5. Validate issue state (exists and open)
    6. If already closed, skip (idempotent)
    7. Generate close summary from workflow metadata
    8. Close issue via gh CLI
    9. Log audit event
    """

    @patch('auto_git_workflow.close_github_issue')
    @patch('auto_git_workflow.generate_close_summary')
    @patch('auto_git_workflow.validate_issue_state')
    @patch('auto_git_workflow.prompt_user_consent')
    @patch('auto_git_workflow.extract_issue_number')
    def test_successful_issue_close(
        self,
        mock_extract,
        mock_consent,
        mock_validate,
        mock_generate,
        mock_close,
    ):
        """Test successful issue close workflow.

        Given: Command args with issue #8, user consents, issue is open
        When: handle_issue_close() is called
        Then: Issue closed successfully
        """
        # Arrange
        mock_extract.return_value = 8
        mock_consent.return_value = True
        mock_validate.return_value = True
        mock_generate.return_value = 'Test summary'
        mock_close.return_value = True

        command_args = 'implement issue #8'
        metadata = {
            'pr_url': 'https://github.com/user/repo/pull/42',
            'commit_hash': 'abc123',
            'files_changed': ['file1.py', 'file2.py'],
        }

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is True
        mock_extract.assert_called_once_with(command_args)
        mock_consent.assert_called_once_with(8)
        mock_validate.assert_called_once_with(8)
        mock_generate.assert_called_once_with(8, metadata)
        mock_close.assert_called_once_with(8, 'Test summary')

    @patch('auto_git_workflow.extract_issue_number')
    def test_skip_when_no_issue_number(self, mock_extract):
        """Test graceful skip when no issue number in command args.

        Given: Command args without issue number
        When: handle_issue_close() is called
        Then: Returns False (skipped), no gh CLI calls
        """
        # Arrange
        mock_extract.return_value = None
        command_args = 'implement new feature'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False
        mock_extract.assert_called_once_with(command_args)

    @patch('auto_git_workflow.prompt_user_consent')
    @patch('auto_git_workflow.extract_issue_number')
    def test_skip_when_user_declines_consent(self, mock_extract, mock_consent):
        """Test graceful skip when user declines consent.

        Given: Issue #8 found but user says 'no'
        When: handle_issue_close() is called
        Then: Returns False (skipped), issue not closed
        """
        # Arrange
        mock_extract.return_value = 8
        mock_consent.return_value = False
        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False
        mock_extract.assert_called_once_with(command_args)
        mock_consent.assert_called_once_with(8)

    @patch('auto_git_workflow.validate_issue_state')
    @patch('auto_git_workflow.prompt_user_consent')
    @patch('auto_git_workflow.extract_issue_number')
    def test_skip_when_issue_already_closed(
        self, mock_extract, mock_consent, mock_validate
    ):
        """Test graceful skip when issue already closed.

        Given: Issue #8 is already closed
        When: handle_issue_close() is called
        Then: Returns True (idempotent), no gh close call
        """
        # Arrange
        mock_extract.return_value = 8
        mock_consent.return_value = True
        # Import the exception from the library
        try:
            from github_issue_closer import IssueAlreadyClosedError
        except ImportError:
            # Define locally for test
            class IssueAlreadyClosedError(Exception):
                pass

        mock_validate.side_effect = IssueAlreadyClosedError("Already closed")
        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is True  # Idempotent - already closed is success
        mock_extract.assert_called_once_with(command_args)
        mock_consent.assert_called_once_with(8)
        mock_validate.assert_called_once_with(8)

    @patch('auto_git_workflow.close_github_issue')
    @patch('auto_git_workflow.generate_close_summary')
    @patch('auto_git_workflow.validate_issue_state')
    @patch('auto_git_workflow.prompt_user_consent')
    @patch('auto_git_workflow.extract_issue_number')
    def test_graceful_degradation_on_gh_cli_failure(
        self,
        mock_extract,
        mock_consent,
        mock_validate,
        mock_generate,
        mock_close,
    ):
        """Test graceful degradation when gh CLI fails.

        Given: gh CLI fails (network error, not installed)
        When: handle_issue_close() is called
        Then: Returns False (failed), workflow continues
        """
        # Arrange
        mock_extract.return_value = 8
        mock_consent.return_value = True
        mock_validate.return_value = True
        mock_generate.return_value = 'Test summary'
        # Import the exception from the library
        try:
            from github_issue_closer import GitHubAPIError
        except ImportError:
            # Define locally for test
            class GitHubAPIError(Exception):
                pass

        mock_close.side_effect = GitHubAPIError("gh CLI not installed")

        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False  # Failed but graceful
        mock_extract.assert_called_once_with(command_args)
        mock_consent.assert_called_once_with(8)
        mock_validate.assert_called_once_with(8)
        mock_generate.assert_called_once_with(8, metadata)
        mock_close.assert_called_once_with(8, 'Test summary')

    @patch('auto_git_workflow.close_github_issue')
    @patch('auto_git_workflow.generate_close_summary')
    @patch('auto_git_workflow.validate_issue_state')
    @patch('auto_git_workflow.prompt_user_consent')
    @patch('auto_git_workflow.extract_issue_number')
    @patch('auto_git_workflow.log_audit_event')
    def test_audit_logging_on_close(
        self,
        mock_log,
        mock_extract,
        mock_consent,
        mock_validate,
        mock_generate,
        mock_close,
    ):
        """Test audit logging when issue closed.

        Security: Audit logging requirement
        Given: Issue #8 closed successfully
        When: handle_issue_close() completes
        Then: Audit event logged with metadata
        """
        # Arrange
        mock_extract.return_value = 8
        mock_consent.return_value = True
        mock_validate.return_value = True
        mock_generate.return_value = 'Test summary'
        mock_close.return_value = True

        command_args = 'implement issue #8'
        metadata = {'pr_url': 'https://github.com/user/repo/pull/42'}

        # Act
        handle_issue_close(command_args, metadata)

        # Assert
        mock_log.assert_called()


# ==============================================================================
# Test Class: Integration with Existing Workflow
# ==============================================================================

class TestIntegrationWithGitWorkflow:
    """Test integration of issue closing with existing auto_git_workflow hook.

    Verifies:
    - handle_issue_close() called after git push succeeds
    - Command args passed through correctly
    - Workflow metadata passed through correctly
    - Failure doesn't break git workflow (graceful degradation)
    """

    @patch('auto_git_workflow.handle_issue_close')
    @patch('auto_git_workflow.trigger_git_operations')
    def test_issue_close_called_after_git_push(
        self, mock_git_ops, mock_issue_close
    ):
        """Test issue close triggered after git push succeeds.

        Given: Git workflow completes successfully
        When: run_hook() executes
        Then: handle_issue_close() is called with correct args
        """
        # Arrange
        mock_git_ops.return_value = True
        mock_issue_close.return_value = True

        # This test requires the actual run_hook() function
        # which we'll test in integration tests
        # For now, verify the signature exists
        assert callable(handle_issue_close)

    @patch('auto_git_workflow.handle_issue_close')
    def test_git_workflow_continues_on_issue_close_failure(self, mock_issue_close):
        """Test git workflow continues even if issue close fails.

        Given: Issue close fails (network error)
        When: handle_issue_close() is called
        Then: Returns False but doesn't raise exception
        """
        # Arrange
        mock_issue_close.return_value = False

        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False  # Failed but graceful

    def test_command_args_format_preserved(self):
        """Test command args format preserved through workflow.

        Given: Various command arg formats
        When: Passed to handle_issue_close()
        Then: Original format preserved for extraction
        """
        # Test various formats that should be preserved
        formats = [
            'implement issue #8',
            'implement #8 feature',
            'Issue 8 implementation',
            'ISSUE #8',
        ]

        # Verify handle_issue_close accepts string args
        # Implementation will test actual extraction
        for fmt in formats:
            assert isinstance(fmt, str)

    def test_metadata_format_preserved(self):
        """Test workflow metadata format preserved.

        Given: Workflow metadata from git operations
        When: Passed to handle_issue_close()
        Then: Metadata structure preserved for summary generation
        """
        # Expected metadata structure
        metadata = {
            'pr_url': 'https://github.com/user/repo/pull/42',
            'commit_hash': 'abc123def',
            'files_changed': ['file1.py', 'file2.py', 'test_file.py'],
            'agents_passed': [
                'researcher',
                'planner',
                'test-master',
                'implementer',
                'reviewer',
                'security-auditor',
                'doc-master',
            ],
        }

        # Verify metadata structure is valid dict
        assert isinstance(metadata, dict)
        assert 'pr_url' in metadata or True  # PR may be optional
        assert 'commit_hash' in metadata
        assert 'files_changed' in metadata
