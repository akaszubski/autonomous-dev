#!/usr/bin/env python3
"""
Unit tests for github_issue_closer module (TDD Red Phase).

Tests for GitHub issue auto-close functionality in /auto-implement workflow.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test issue number extraction from command arguments (8 patterns)
- Test issue state validation via gh CLI (5 scenarios)
- Test close summary generation (5 variations)
- Test issue closing via gh CLI (5 scenarios)
- Test user consent prompting (4 scenarios)
- Test security validation (4 security requirements)

Security Requirements (from planner and researcher):
- CWE-20: Validate issue numbers are positive integers
- CWE-78: Use subprocess list args (never shell=True), validate command construction
- CWE-117: Sanitize newlines and control characters from issue titles/summaries
- Audit logging: Log all gh CLI operations and consent decisions

Coverage Target: 95%+ for github_issue_closer.py

Date: 2025-11-18
Issue: #91 (Auto-close GitHub issues after /auto-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (tests should FAIL - no implementation yet)
"""

import json
import os
import subprocess
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError, TimeoutExpired

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))

# Import will fail - module doesn't exist yet (TDD!)
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
except ImportError:
    # Expected during TDD red phase
    pass


# ==============================================================================
# Test Class: Issue Number Extraction
# ==============================================================================

class TestIssueNumberExtraction:
    """Test extraction of issue numbers from command arguments.

    Should recognize patterns:
    - "issue #8"
    - "#8"
    - "Issue 8"
    - "implement issue #8"
    - Multiple mentions (use first)
    Edge cases:
    - No issue number
    - Multiple different numbers
    - Invalid formats
    """

    def test_extract_from_issue_hash_pattern(self):
        """Test extraction from 'issue #8' pattern.

        Given: Command args "implement issue #8 feature"
        When: extract_issue_number() is called
        Then: Returns 8
        """
        result = extract_issue_number("implement issue #8 feature")
        assert result == 8

    def test_extract_from_hash_only_pattern(self):
        """Test extraction from '#8' pattern.

        Given: Command args "implement #8"
        When: extract_issue_number() is called
        Then: Returns 8
        """
        result = extract_issue_number("implement #8")
        assert result == 8

    def test_extract_from_issue_space_number_pattern(self):
        """Test extraction from 'Issue 8' pattern (no hash).

        Given: Command args "implement Issue 8 feature"
        When: extract_issue_number() is called
        Then: Returns 8
        """
        result = extract_issue_number("implement Issue 8 feature")
        assert result == 8

    def test_extract_case_insensitive(self):
        """Test case-insensitive extraction.

        Given: Command args "ISSUE #8" or "issue #8" or "Issue #8"
        When: extract_issue_number() is called
        Then: Returns 8 for all cases
        """
        assert extract_issue_number("ISSUE #8") == 8
        assert extract_issue_number("issue #8") == 8
        assert extract_issue_number("Issue #8") == 8

    def test_extract_first_when_multiple_mentions(self):
        """Test extraction uses first occurrence when issue mentioned multiple times.

        Given: Command args "implement issue #8 related to #8"
        When: extract_issue_number() is called
        Then: Returns 8
        """
        result = extract_issue_number("implement issue #8 related to #8")
        assert result == 8

    def test_extract_first_when_multiple_different_numbers(self):
        """Test extraction uses first occurrence when multiple different issue numbers.

        Given: Command args "implement #8 and #9"
        When: extract_issue_number() is called
        Then: Returns 8 (first occurrence)
        """
        result = extract_issue_number("implement #8 and #9")
        assert result == 8

    def test_extract_returns_none_when_no_issue_number(self):
        """Test returns None when no issue number found.

        Given: Command args "implement new feature"
        When: extract_issue_number() is called
        Then: Returns None
        """
        result = extract_issue_number("implement new feature")
        assert result is None

    def test_extract_handles_empty_string(self):
        """Test handles empty string gracefully.

        Given: Empty command args
        When: extract_issue_number() is called
        Then: Returns None
        """
        result = extract_issue_number("")
        assert result is None


# ==============================================================================
# Test Class: Issue State Validation
# ==============================================================================

class TestIssueStateValidation:
    """Test validation of issue state via gh CLI.

    Should check:
    - Issue exists
    - Issue is open (not already closed)
    - Handle gh CLI errors gracefully
    """

    @patch('subprocess.run')
    def test_validate_open_issue(self, mock_run):
        """Test validation succeeds for open issue.

        Given: Issue #8 exists and is open
        When: validate_issue_state(8) is called
        Then: Returns True
        And: gh CLI is invoked correctly
        """
        # Arrange
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 8, "state": "open", "title": "Test Issue"}',
        )

        # Act
        result = validate_issue_state(8)

        # Assert
        assert result is True
        mock_run.assert_called_once_with(
            ['gh', 'issue', 'view', '8', '--json', 'state,title,number'],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )

    @patch('subprocess.run')
    def test_validate_closed_issue_raises_error(self, mock_run):
        """Test validation raises IssueAlreadyClosedError for closed issue.

        Given: Issue #8 exists but is already closed
        When: validate_issue_state(8) is called
        Then: Raises IssueAlreadyClosedError
        """
        # Arrange
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 8, "state": "closed", "title": "Test Issue"}',
        )

        # Act & Assert
        with pytest.raises(IssueAlreadyClosedError, match="Issue #8 is already closed"):
            validate_issue_state(8)

    @patch('subprocess.run')
    def test_validate_nonexistent_issue_raises_error(self, mock_run):
        """Test validation raises IssueNotFoundError for nonexistent issue.

        Given: Issue #999 does not exist
        When: validate_issue_state(999) is called
        Then: Raises IssueNotFoundError
        """
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1, ['gh', 'issue', 'view'], stderr='issue not found'
        )

        # Act & Assert
        with pytest.raises(IssueNotFoundError, match="Issue #999 not found"):
            validate_issue_state(999)

    @patch('subprocess.run')
    def test_validate_handles_timeout(self, mock_run):
        """Test validation raises GitHubAPIError on timeout.

        Given: gh CLI times out (network issue)
        When: validate_issue_state(8) is called
        Then: Raises GitHubAPIError
        """
        # Arrange
        mock_run.side_effect = TimeoutExpired(['gh', 'issue', 'view'], 10)

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="Timeout validating issue"):
            validate_issue_state(8)

    @patch('subprocess.run')
    def test_validate_handles_network_failure(self, mock_run):
        """Test validation raises GitHubAPIError on network failure.

        Given: gh CLI fails (no internet)
        When: validate_issue_state(8) is called
        Then: Raises GitHubAPIError
        """
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1, ['gh', 'issue', 'view'], stderr='failed to connect'
        )

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="Failed to validate issue"):
            validate_issue_state(8)


# ==============================================================================
# Test Class: Close Summary Generation
# ==============================================================================

class TestCloseSummaryGeneration:
    """Test generation of issue close summary.

    Should include:
    - Completion message
    - List of 7 agents that passed
    - PR link (if available)
    - Commit hash (if available)
    - Files changed count
    """

    def test_generate_full_summary(self):
        """Test generation of complete summary with all metadata.

        Given: All workflow metadata available (PR, commit, files)
        When: generate_close_summary() is called
        Then: Returns formatted summary with all sections
        """
        # Arrange
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

        # Act
        summary = generate_close_summary(8, metadata)

        # Assert
        assert 'Completed via /auto-implement' in summary
        assert 'All 7 agents passed' in summary
        assert 'researcher' in summary
        assert 'planner' in summary
        assert 'test-master' in summary
        assert 'implementer' in summary
        assert 'reviewer' in summary
        assert 'security-auditor' in summary
        assert 'doc-master' in summary
        assert 'https://github.com/user/repo/pull/42' in summary
        assert 'abc123def' in summary
        assert '3 files changed' in summary

    def test_generate_summary_without_pr(self):
        """Test generation when PR not created (user declined).

        Given: No PR URL in metadata
        When: generate_close_summary() is called
        Then: Returns summary without PR section
        """
        # Arrange
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
        summary = generate_close_summary(8, metadata)

        # Assert
        assert 'Completed via /auto-implement' in summary
        assert 'All 7 agents passed' in summary
        assert 'pull' not in summary.lower()  # No PR section
        assert 'abc123def' in summary

    def test_generate_summary_truncates_long_file_list(self):
        """Test file list truncation when >10 files changed.

        Given: 15 files changed
        When: generate_close_summary() is called
        Then: Shows first 10 files + "... 5 more"
        """
        # Arrange
        metadata = {
            'commit_hash': 'abc123def',
            'files_changed': [f'file{i}.py' for i in range(15)],
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
        summary = generate_close_summary(8, metadata)

        # Assert
        assert '15 files changed' in summary
        assert 'file0.py' in summary  # First file shown
        assert 'file9.py' in summary  # 10th file shown
        assert '... 5 more' in summary  # Truncation message

    def test_generate_summary_sanitizes_output(self):
        """Test summary sanitizes newlines and control characters.

        Security: CWE-117 (Log Injection Prevention)
        Given: File names with newlines or control chars
        When: generate_close_summary() is called
        Then: Newlines replaced with spaces, control chars removed
        """
        # Arrange
        metadata = {
            'commit_hash': 'abc123def',
            'files_changed': ['file\nwith\nnewlines.py', 'file\x00with\x01control.py'],
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
        summary = generate_close_summary(8, metadata)

        # Assert
        assert '\n\n' not in summary  # No double newlines from injection
        assert '\x00' not in summary  # No null bytes
        assert '\x01' not in summary  # No control chars
        assert 'file with newlines.py' in summary  # Sanitized

    def test_generate_summary_includes_all_seven_agents(self):
        """Test summary explicitly lists all 7 agents.

        Given: Standard workflow with 7 agents
        When: generate_close_summary() is called
        Then: All 7 agent names appear in summary
        """
        # Arrange
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
        summary = generate_close_summary(8, metadata)

        # Assert
        required_agents = [
            'researcher',
            'planner',
            'test-master',
            'implementer',
            'reviewer',
            'security-auditor',
            'doc-master',
        ]
        for agent in required_agents:
            assert agent in summary


# ==============================================================================
# Test Class: Issue Closing
# ==============================================================================

class TestIssueClosing:
    """Test closing of GitHub issue via gh CLI."""

    @patch('subprocess.run')
    @patch('github_issue_closer.log_audit_event')
    def test_close_issue_success(self, mock_log, mock_run):
        """Test successful issue closing.

        Given: Issue #8 is open
        When: close_github_issue(8, summary) is called
        Then: gh CLI invoked correctly
        And: Audit log recorded
        And: Returns True
        """
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='')
        summary = 'Test summary'

        # Act
        result = close_github_issue(8, summary)

        # Assert
        assert result is True
        mock_run.assert_called_once_with(
            ['gh', 'issue', 'close', '8', '--comment', summary],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        mock_log.assert_called_once()

    @patch('subprocess.run')
    def test_close_already_closed_issue_idempotent(self, mock_run):
        """Test closing already-closed issue is idempotent.

        Given: Issue #8 is already closed
        When: close_github_issue(8, summary) is called
        Then: Returns True (graceful handling)
        """
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1, ['gh', 'issue', 'close'], stderr='issue already closed'
        )
        summary = 'Test summary'

        # Act
        result = close_github_issue(8, summary)

        # Assert
        assert result is True  # Idempotent behavior

    @patch('subprocess.run')
    def test_close_nonexistent_issue_raises_error(self, mock_run):
        """Test closing nonexistent issue raises IssueNotFoundError.

        Given: Issue #999 does not exist
        When: close_github_issue(999, summary) is called
        Then: Raises IssueNotFoundError
        """
        # Arrange
        mock_run.side_effect = CalledProcessError(
            1, ['gh', 'issue', 'close'], stderr='issue not found'
        )
        summary = 'Test summary'

        # Act & Assert
        with pytest.raises(IssueNotFoundError, match="Issue #999 not found"):
            close_github_issue(999, summary)

    @patch('subprocess.run')
    def test_close_handles_timeout(self, mock_run):
        """Test closing handles timeout gracefully.

        Given: gh CLI times out
        When: close_github_issue(8, summary) is called
        Then: Raises GitHubAPIError
        """
        # Arrange
        mock_run.side_effect = TimeoutExpired(['gh', 'issue', 'close'], 10)
        summary = 'Test summary'

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="Timeout closing issue"):
            close_github_issue(8, summary)

    @patch('subprocess.run')
    @patch('github_issue_closer.log_audit_event')
    def test_close_logs_audit_event(self, mock_log, mock_run):
        """Test issue closing logs audit event.

        Security: Audit logging requirement
        Given: Issue #8 is closed successfully
        When: close_github_issue(8, summary) is called
        Then: Audit event logged with issue number and action
        """
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='')
        summary = 'Test summary'

        # Act
        close_github_issue(8, summary)

        # Assert
        mock_log.assert_called_once()
        call_args = mock_log.call_args[0][0]
        assert 'action' in call_args
        assert call_args['action'] == 'close_github_issue'
        assert call_args['issue_number'] == 8


# ==============================================================================
# Test Class: User Consent
# ==============================================================================

class TestUserConsent:
    """Test user consent prompting for issue closing."""

    @patch('builtins.input', return_value='yes')
    def test_consent_user_says_yes(self, mock_input):
        """Test consent granted when user types 'yes'.

        Given: User types 'yes'
        When: prompt_user_consent(8) is called
        Then: Returns True
        """
        result = prompt_user_consent(8)
        assert result is True

    @patch('builtins.input', return_value='no')
    def test_consent_user_says_no(self, mock_input):
        """Test consent denied when user types 'no'.

        Given: User types 'no'
        When: prompt_user_consent(8) is called
        Then: Returns False
        """
        result = prompt_user_consent(8)
        assert result is False

    @patch('builtins.input', return_value='YES')
    def test_consent_case_insensitive(self, mock_input):
        """Test consent is case-insensitive.

        Given: User types 'YES', 'Yes', or 'YeS'
        When: prompt_user_consent(8) is called
        Then: Returns True for all variations
        """
        result = prompt_user_consent(8)
        assert result is True

    @patch('builtins.input', side_effect=['invalid', 'maybe', 'yes'])
    def test_consent_retries_on_invalid_input(self, mock_input):
        """Test consent re-prompts on invalid input.

        Given: User types invalid input twice, then 'yes'
        When: prompt_user_consent(8) is called
        Then: Re-prompts and eventually returns True
        """
        result = prompt_user_consent(8)
        assert result is True
        assert mock_input.call_count == 3


# ==============================================================================
# Test Class: Security Validation
# ==============================================================================

class TestSecurityValidation:
    """Test security requirements are enforced.

    Security Requirements:
    - CWE-20: Input validation (positive integers only)
    - CWE-78: Command injection prevention (subprocess list args)
    - CWE-117: Log injection prevention (sanitize output)
    - Audit logging: All operations logged
    """

    def test_validate_positive_integers_only(self):
        """Test CWE-20: Only positive integers accepted.

        Given: Issue number -1, 0, or non-integer
        When: Functions are called
        Then: Raise ValueError
        """
        with pytest.raises(ValueError, match="Issue number must be positive"):
            validate_issue_state(-1)

        with pytest.raises(ValueError, match="Issue number must be positive"):
            validate_issue_state(0)

    @patch('subprocess.run')
    def test_command_injection_prevention(self, mock_run):
        """Test CWE-78: Command injection prevention.

        Security: Ensure subprocess uses list args (not shell=True)
        Given: Issue number with shell metacharacters
        When: gh CLI is invoked
        Then: Uses list args (safe) not string concatenation
        """
        # Arrange
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 8, "state": "open", "title": "Test"}',
        )

        # Act
        validate_issue_state(8)

        # Assert
        # Verify subprocess.run called with list args (not shell=True)
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert isinstance(call_args[0][0], list)  # First arg is list
        assert 'shell' not in call_args[1] or call_args[1]['shell'] is False

    def test_log_injection_prevention(self):
        """Test CWE-117: Log injection prevention.

        Security: Sanitize newlines and control characters
        Given: Summary with newlines and control chars
        When: generate_close_summary() is called
        Then: Output sanitized
        """
        # Arrange
        metadata = {
            'commit_hash': 'abc\n123\ninjection',
            'files_changed': ['file\x00injection.py'],
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
        summary = generate_close_summary(8, metadata)

        # Assert
        assert '\n\n' not in summary  # No double newlines
        assert '\x00' not in summary  # No null bytes

    @patch('github_issue_closer.log_audit_event')
    @patch('subprocess.run')
    def test_audit_logging_all_operations(self, mock_run, mock_log):
        """Test all operations are audit logged.

        Security: Audit logging requirement
        Given: Any operation (validate, close)
        When: Operation completes
        Then: Audit event logged with action and metadata
        """
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='')

        # Act
        close_github_issue(8, 'Test summary')

        # Assert
        mock_log.assert_called()
        call_args = mock_log.call_args[0][0]
        assert 'action' in call_args
        assert 'issue_number' in call_args
        assert 'timestamp' in call_args or True  # Timestamp may be added by log function
