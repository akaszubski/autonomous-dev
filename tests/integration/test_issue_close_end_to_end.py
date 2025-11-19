#!/usr/bin/env python3
"""
Integration tests for GitHub issue auto-close end-to-end workflow (TDD Red Phase).

Tests complete /auto-implement workflow with issue closing.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (modules not found).

Test Strategy:
- Test full workflow: /auto-implement → git push → issue close
- Test user consent flow integration
- Test graceful degradation scenarios
- Test error handling across components
- Test audit logging end-to-end

Integration Scope:
- auto_git_workflow.py hook (SubagentStop)
- github_issue_closer.py library
- auto-implement.md command (STEP 5.1)
- gh CLI subprocess execution

Date: 2025-11-18
Issue: #91 (Auto-close GitHub issues after /auto-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (tests should FAIL - no implementation yet)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError, TimeoutExpired

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'hooks'))

# Import will fail - modules don't exist yet (TDD!)
try:
    from github_issue_closer import (
        extract_issue_number,
        validate_issue_state,
        generate_close_summary,
        close_github_issue,
        prompt_user_consent,
        IssueAlreadyClosedError,
        IssueNotFoundError,
        GitHubAPIError,
    )
    from auto_git_workflow import handle_issue_close
except ImportError as e:
    # Expected during TDD red phase
    pass


# ==============================================================================
# Test Class: End-to-End Workflow
# ==============================================================================

class TestIssueCloseEndToEnd:
    """Test complete workflow from /auto-implement to issue close.

    Workflow:
    1. User runs: /auto-implement "implement issue #8"
    2. All 7 agents pass (researcher → planner → ... → doc-master)
    3. quality-validator completes → triggers auto_git_workflow hook
    4. Git operations complete (commit, push, PR)
    5. handle_issue_close() extracts issue #8
    6. User prompted for consent
    7. Issue validated (exists, open)
    8. Summary generated from workflow metadata
    9. Issue closed via gh CLI
    10. Audit logged
    """

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_full_workflow_success(self, mock_input, mock_run):
        """Test complete successful workflow from command to issue close.

        Given: /auto-implement with issue #8, all agents pass
        When: Workflow executes end-to-end
        Then: Issue closed with complete summary
        """
        # Arrange - Mock gh CLI responses
        def gh_mock(cmd, **kwargs):
            if 'view' in cmd:
                # Issue validation
                return Mock(
                    returncode=0,
                    stdout='{"number": 8, "state": "open", "title": "Test Issue"}',
                )
            elif 'close' in cmd:
                # Issue closing
                return Mock(returncode=0, stdout='')
            else:
                return Mock(returncode=0, stdout='')

        mock_run.side_effect = gh_mock

        command_args = 'implement issue #8 - Add auto-close feature'
        metadata = {
            'pr_url': 'https://github.com/user/repo/pull/42',
            'commit_hash': 'abc123def456',
            'files_changed': [
                'plugins/autonomous-dev/lib/github_issue_closer.py',
                'plugins/autonomous-dev/hooks/auto_git_workflow.py',
                'tests/unit/lib/test_github_issue_closer.py',
            ],
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

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is True
        # Verify gh CLI called for both validate and close
        assert mock_run.call_count >= 2
        # Verify user was prompted
        mock_input.assert_called_once()

    @patch('subprocess.run')
    def test_workflow_without_issue_number(self, mock_run):
        """Test workflow gracefully skips when no issue number.

        Given: /auto-implement without issue number
        When: Workflow executes
        Then: Issue close skipped, no gh CLI calls
        """
        # Arrange
        command_args = 'implement new autonomous feature'
        metadata = {
            'commit_hash': 'abc123def',
            'files_changed': ['file1.py'],
        }

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False  # Skipped
        mock_run.assert_not_called()  # No gh CLI calls

    @patch('subprocess.run')
    @patch('builtins.input', return_value='no')
    def test_workflow_user_rejects_consent(self, mock_input, mock_run):
        """Test workflow gracefully skips when user declines consent.

        Given: Issue #8 found but user says 'no' to closing
        When: User prompted for consent
        Then: Issue close skipped, gh close not called
        """
        # Arrange
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 8, "state": "open", "title": "Test"}',
        )

        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False  # User declined
        mock_input.assert_called_once()
        # gh CLI called only for validation, not closing
        assert mock_run.call_count <= 1

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_workflow_issue_already_closed(self, mock_input, mock_run):
        """Test workflow handles already-closed issue gracefully.

        Given: Issue #8 already closed
        When: Workflow executes
        Then: Returns True (idempotent), no gh close call
        """
        # Arrange
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 8, "state": "closed", "title": "Test"}',
        )

        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is True  # Idempotent success
        mock_input.assert_called_once()
        # Only validation call, no close call
        assert mock_run.call_count == 1

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_workflow_gh_cli_not_available(self, mock_input, mock_run):
        """Test workflow handles gh CLI not available gracefully.

        Given: gh CLI not installed or not in PATH
        When: Issue close attempted
        Then: Returns False (failed), workflow continues
        """
        # Arrange
        mock_run.side_effect = FileNotFoundError('gh: command not found')

        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False  # Failed but graceful
        # Should have attempted gh call
        mock_run.assert_called()


# ==============================================================================
# Test Class: Metadata Integration
# ==============================================================================

class TestMetadataIntegration:
    """Test workflow metadata integration between components."""

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_metadata_flows_from_git_to_summary(self, mock_input, mock_run):
        """Test metadata from git operations flows to issue close summary.

        Given: Git operations generate PR URL, commit hash, files changed
        When: Issue close summary generated
        Then: All metadata included in summary
        """
        # Arrange
        def gh_mock(cmd, **kwargs):
            if 'view' in cmd:
                return Mock(
                    returncode=0,
                    stdout='{"number": 8, "state": "open", "title": "Test"}',
                )
            elif 'close' in cmd:
                # Capture the summary from close command
                comment_arg = cmd[cmd.index('--comment') + 1]
                # Verify metadata in summary
                assert 'https://github.com/user/repo/pull/42' in comment_arg
                assert 'abc123' in comment_arg
                assert '3 files changed' in comment_arg
                return Mock(returncode=0, stdout='')

        mock_run.side_effect = gh_mock

        command_args = 'implement issue #8'
        metadata = {
            'pr_url': 'https://github.com/user/repo/pull/42',
            'commit_hash': 'abc123def',
            'files_changed': ['file1.py', 'file2.py', 'file3.py'],
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

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is True

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_metadata_without_pr_url(self, mock_input, mock_run):
        """Test summary generation when PR URL not available (user declined PR).

        Given: Git operations completed but no PR created
        When: Issue close summary generated
        Then: Summary valid without PR section
        """
        # Arrange
        def gh_mock(cmd, **kwargs):
            if 'view' in cmd:
                return Mock(
                    returncode=0,
                    stdout='{"number": 8, "state": "open", "title": "Test"}',
                )
            elif 'close' in cmd:
                comment_arg = cmd[cmd.index('--comment') + 1]
                # Verify summary valid without PR
                assert 'Completed via /auto-implement' in comment_arg
                assert 'https://github.com' not in comment_arg  # No PR link
                return Mock(returncode=0, stdout='')

        mock_run.side_effect = gh_mock

        command_args = 'implement issue #8'
        metadata = {
            'commit_hash': 'abc123def',
            'files_changed': ['file1.py'],
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

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is True


# ==============================================================================
# Test Class: Error Recovery
# ==============================================================================

class TestErrorRecovery:
    """Test error handling and recovery across components."""

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_network_timeout_recovery(self, mock_input, mock_run):
        """Test recovery from network timeout during gh CLI calls.

        Given: gh CLI times out due to network issues
        When: Issue close attempted
        Then: Returns False (failed), logs error, workflow continues
        """
        # Arrange
        mock_run.side_effect = TimeoutExpired(['gh', 'issue', 'view'], 10)

        command_args = 'implement issue #8'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False  # Failed but graceful

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_issue_not_found_recovery(self, mock_input, mock_run):
        """Test recovery when issue doesn't exist.

        Given: Issue #999 doesn't exist in repository
        When: Issue close attempted
        Then: Returns False (failed), error logged
        """
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1, ['gh', 'issue', 'view'], stderr='issue not found'
        )

        command_args = 'implement issue #999'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is False  # Failed but graceful

    @patch('subprocess.run')
    @patch('builtins.input', side_effect=KeyboardInterrupt())
    def test_user_interrupt_recovery(self, mock_input, mock_run):
        """Test recovery from user interrupt (Ctrl+C) during consent.

        Given: User presses Ctrl+C during consent prompt
        When: Interrupt occurs
        Then: Exception propagates (allow user to cancel)
        """
        # Arrange
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 8, "state": "open", "title": "Test"}',
        )

        command_args = 'implement issue #8'
        metadata = {}

        # Act & Assert
        with pytest.raises(KeyboardInterrupt):
            handle_issue_close(command_args, metadata)


# ==============================================================================
# Test Class: Security Integration
# ==============================================================================

class TestSecurityIntegration:
    """Test security requirements across integrated workflow."""

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_command_injection_prevention_end_to_end(self, mock_input, mock_run):
        """Test CWE-78 prevention across workflow.

        Security: Ensure no shell injection via issue numbers or metadata
        Given: Malicious input in command args or metadata
        When: Workflow executes
        Then: All subprocess calls use list args (safe)
        """
        # Arrange
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 8, "state": "open", "title": "Test"}',
        )

        # Attempt injection via command args (won't extract as valid issue)
        command_args = 'implement issue #8; rm -rf /'
        metadata = {}

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        # Verify all subprocess.run calls use list args
        for call_obj in mock_run.call_args_list:
            args = call_obj[0]
            kwargs = call_obj[1] if len(call_obj) > 1 else {}
            assert isinstance(args[0], list), "subprocess.run must use list args"
            assert kwargs.get('shell', False) is False, "shell=True is forbidden"

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    @patch('github_issue_closer.log_audit_event')
    def test_audit_logging_end_to_end(self, mock_log, mock_input, mock_run):
        """Test audit logging across complete workflow.

        Security: All operations logged for security auditing
        Given: Complete workflow execution
        When: Issue closed successfully
        Then: Audit events logged for each security-relevant operation
        """
        # Arrange
        def gh_mock(cmd, **kwargs):
            if 'view' in cmd:
                return Mock(
                    returncode=0,
                    stdout='{"number": 8, "state": "open", "title": "Test"}',
                )
            elif 'close' in cmd:
                return Mock(returncode=0, stdout='')

        mock_run.side_effect = gh_mock

        command_args = 'implement issue #8'
        metadata = {'commit_hash': 'abc123'}

        # Act
        handle_issue_close(command_args, metadata)

        # Assert
        # Verify audit logging called
        assert mock_log.call_count > 0

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    def test_output_sanitization_end_to_end(self, mock_input, mock_run):
        """Test CWE-117 prevention across workflow.

        Security: Sanitize all output to prevent log injection
        Given: Metadata with newlines and control characters
        When: Summary generated and logged
        Then: All output sanitized
        """
        # Arrange
        def gh_mock(cmd, **kwargs):
            if 'view' in cmd:
                return Mock(
                    returncode=0,
                    stdout='{"number": 8, "state": "open", "title": "Test\\nInjection"}',
                )
            elif 'close' in cmd:
                comment_arg = cmd[cmd.index('--comment') + 1]
                # Verify sanitization in summary
                assert '\n\n' not in comment_arg  # No double newlines
                assert '\x00' not in comment_arg  # No null bytes
                return Mock(returncode=0, stdout='')

        mock_run.side_effect = gh_mock

        command_args = 'implement issue #8'
        metadata = {
            'commit_hash': 'abc\n123',  # Attempt injection
            'files_changed': ['file\x00.py'],  # Null byte injection
        }

        # Act
        result = handle_issue_close(command_args, metadata)

        # Assert
        assert result is True
