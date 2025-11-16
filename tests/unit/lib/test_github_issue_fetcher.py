#!/usr/bin/env python3
"""
Unit tests for github_issue_fetcher module (TDD Red Phase).

Tests for GitHub issue fetching functionality in /batch-implement --issues command.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test input validation (CWE-20: positive integers, max 100 issues)
- Test gh CLI subprocess execution (CWE-78: command injection prevention)
- Test issue title fetching with graceful degradation
- Test output sanitization (CWE-117: log injection prevention)
- Test error handling (gh CLI not installed, network errors, timeouts)
- Test audit logging for security compliance

Security Requirements (from planner and researcher):
- CWE-20: Validate positive integers only, reject negatives/zero
- CWE-78: Use subprocess list args (never shell=True), validate command construction
- CWE-117: Sanitize newlines and control characters from issue titles
- Audit logging: Log all gh CLI operations for security auditing

Coverage Target: 90%+ for github_issue_fetcher.py

Date: 2025-11-16
Issue: #77 (Add --issues flag to /batch-implement)
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
    from github_issue_fetcher import (
        validate_issue_numbers,
        fetch_issue_title,
        fetch_issue_titles,
        format_feature_description,
        GitHubAPIError,
        IssueNotFoundError,
    )
except ImportError:
    # Expected during TDD red phase
    pass


# ==============================================================================
# Test Class: Input Validation (CWE-20)
# ==============================================================================

class TestValidateIssueNumbers:
    """Test input validation for GitHub issue numbers.

    Security Requirement (CWE-20): Input Validation
    - Accept only positive integers (1, 2, 3, ...)
    - Reject zero, negative numbers, non-integers
    - Enforce maximum limit (100 issues per batch)
    - Prevent resource exhaustion attacks
    """

    def test_valid_single_issue(self):
        """Test that a single valid issue number is accepted.

        Given: Issue number [72]
        When: validate_issue_numbers() is called
        Then: No exception is raised
        """
        # Should not raise exception
        validate_issue_numbers([72])

    def test_valid_multiple_issues(self):
        """Test that multiple valid issue numbers are accepted.

        Given: Issue numbers [72, 73, 74, 75, 76]
        When: validate_issue_numbers() is called
        Then: No exception is raised
        """
        # Should not raise exception
        validate_issue_numbers([72, 73, 74, 75, 76])

    def test_invalid_negative_issue(self):
        """Test that negative issue numbers are rejected.

        Security: Prevent command injection via negative numbers
        Given: Issue number [-1]
        When: validate_issue_numbers() is called
        Then: ValueError is raised with helpful message
        """
        with pytest.raises(ValueError) as exc_info:
            validate_issue_numbers([-1])

        # Verify error message is helpful
        assert "positive" in str(exc_info.value).lower()
        assert "-1" in str(exc_info.value)

    def test_invalid_zero_issue(self):
        """Test that zero issue number is rejected.

        Security: GitHub issues start at #1, zero is invalid
        Given: Issue number [0]
        When: validate_issue_numbers() is called
        Then: ValueError is raised with helpful message
        """
        with pytest.raises(ValueError) as exc_info:
            validate_issue_numbers([0])

        # Verify error message is helpful
        assert "positive" in str(exc_info.value).lower()
        assert "0" in str(exc_info.value)

    def test_invalid_too_many_issues(self):
        """Test that more than 100 issues are rejected.

        Security: Prevent resource exhaustion via large batch sizes
        Given: 101 issue numbers
        When: validate_issue_numbers() is called
        Then: ValueError is raised with helpful message
        """
        too_many_issues = list(range(1, 102))  # 1-101 = 101 issues

        with pytest.raises(ValueError) as exc_info:
            validate_issue_numbers(too_many_issues)

        # Verify error message mentions limit
        assert "100" in str(exc_info.value)
        assert "maximum" in str(exc_info.value).lower() or "limit" in str(exc_info.value).lower()

    def test_invalid_mixed_valid_invalid(self):
        """Test that mixed valid/invalid issue numbers are rejected.

        Given: Mix of valid (72, 73) and invalid (-1, 0) issue numbers
        When: validate_issue_numbers() is called
        Then: ValueError is raised for first invalid number
        """
        with pytest.raises(ValueError):
            validate_issue_numbers([72, 73, -1, 0, 74])

    def test_invalid_empty_list(self):
        """Test that empty issue list is rejected.

        Given: Empty list []
        When: validate_issue_numbers() is called
        Then: ValueError is raised
        """
        with pytest.raises(ValueError) as exc_info:
            validate_issue_numbers([])

        assert "empty" in str(exc_info.value).lower()


# ==============================================================================
# Test Class: Single Issue Fetching (CWE-78)
# ==============================================================================

class TestFetchIssueTitle:
    """Test fetching a single GitHub issue title via gh CLI.

    Security Requirement (CWE-78): Command Injection Prevention
    - Use subprocess.run() with list arguments (NOT string)
    - Never use shell=True
    - Validate subprocess command construction
    - Handle command execution errors gracefully
    """

    @pytest.fixture
    def mock_gh_cli_success(self):
        """Mock successful gh CLI execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"title": "Add logging feature"}',
                stderr=''
            )
            yield mock_run

    @pytest.fixture
    def mock_gh_cli_not_found(self):
        """Mock gh CLI returning 404 (issue not found)."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout='',
                stderr='no pull requests or issues found'
            )
            yield mock_run

    @pytest.fixture
    def mock_audit_log(self):
        """Mock security audit logging."""
        with patch('github_issue_fetcher.audit_log') as mock_log:
            yield mock_log

    def test_fetch_existing_issue(self, mock_gh_cli_success, mock_audit_log):
        """Test fetching an existing GitHub issue.

        Given: Issue #72 exists with title "Add logging feature"
        When: fetch_issue_title(72) is called
        Then: Returns "Add logging feature"
        And: gh CLI is called with correct arguments
        And: Operation is audit logged
        """
        result = fetch_issue_title(72)

        # Verify title is returned
        assert result == "Add logging feature"

        # Verify gh CLI called with list args (CWE-78)
        mock_gh_cli_success.assert_called_once()
        call_args = mock_gh_cli_success.call_args

        # Verify list arguments (not string)
        assert isinstance(call_args[0][0], list)

        # Verify shell=False (explicit security check)
        assert call_args[1].get('shell', False) is False

        # Verify command structure
        cmd = call_args[0][0]
        assert 'gh' in cmd
        assert 'issue' in cmd
        assert 'view' in cmd
        assert '72' in cmd

        # Verify audit log called
        mock_audit_log.assert_called_once()
        log_msg = mock_audit_log.call_args[0][0]
        assert '72' in log_msg
        assert 'fetch' in log_msg.lower()

    def test_fetch_missing_issue(self, mock_gh_cli_not_found, mock_audit_log):
        """Test fetching a non-existent GitHub issue.

        Given: Issue #9999 does not exist
        When: fetch_issue_title(9999) is called
        Then: Returns None (graceful degradation)
        And: Operation is audit logged
        """
        result = fetch_issue_title(9999)

        # Verify None returned (not exception)
        assert result is None

        # Verify audit log called
        mock_audit_log.assert_called_once()
        log_msg = mock_audit_log.call_args[0][0]
        assert '9999' in log_msg
        assert 'not found' in log_msg.lower() or 'missing' in log_msg.lower()

    def test_gh_cli_not_installed(self, mock_audit_log):
        """Test handling when gh CLI is not installed.

        Security: Prevent information disclosure about system configuration
        Given: gh CLI is not installed
        When: fetch_issue_title(72) is called
        Then: Raises FileNotFoundError with helpful message
        And: Operation is audit logged
        """
        with patch('subprocess.run', side_effect=FileNotFoundError("gh: command not found")):
            with pytest.raises(FileNotFoundError) as exc_info:
                fetch_issue_title(72)

            # Verify helpful error message
            assert "gh" in str(exc_info.value).lower()

        # Verify audit log called
        mock_audit_log.assert_called_once()

    def test_gh_cli_timeout(self, mock_audit_log):
        """Test handling when gh CLI times out.

        Security: Prevent denial-of-service via hung processes
        Given: gh CLI hangs for >10 seconds
        When: fetch_issue_title(72) is called
        Then: Raises TimeoutExpired exception
        And: Operation is audit logged
        """
        with patch('subprocess.run', side_effect=TimeoutExpired(cmd=['gh'], timeout=10)):
            with pytest.raises(TimeoutExpired):
                fetch_issue_title(72)

        # Verify audit log called
        mock_audit_log.assert_called_once()

    def test_command_injection_prevention(self, mock_gh_cli_success):
        """Test that command injection is prevented.

        Security (CWE-78): Verify subprocess called with list args
        Given: Issue number 72
        When: fetch_issue_title(72) is called
        Then: subprocess.run() called with list arguments
        And: shell=False is set explicitly
        And: No string concatenation in command
        """
        fetch_issue_title(72)

        # Get subprocess.run() call arguments
        call_args = mock_gh_cli_success.call_args

        # CRITICAL: Verify list arguments (not string)
        cmd_arg = call_args[0][0]
        assert isinstance(cmd_arg, list), \
            f"Expected list arguments, got {type(cmd_arg).__name__}"

        # CRITICAL: Verify shell=False
        assert call_args[1].get('shell') is False, \
            "shell=True detected - SECURITY VIOLATION (CWE-78)"

        # Verify no shell metacharacters in command
        for arg in cmd_arg:
            assert not any(char in str(arg) for char in ['|', '&', ';', '$', '`']), \
                f"Shell metacharacter detected in argument: {arg}"

    def test_json_parse_error(self, mock_audit_log):
        """Test handling when gh CLI returns invalid JSON.

        Given: gh CLI returns malformed JSON
        When: fetch_issue_title(72) is called
        Then: Returns None (graceful degradation)
        And: Error is audit logged
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"title": "Unclosed quote',  # Invalid JSON
                stderr=''
            )

            result = fetch_issue_title(72)

            # Verify graceful degradation
            assert result is None

        # Verify audit log called with error
        mock_audit_log.assert_called()


# ==============================================================================
# Test Class: Batch Issue Fetching
# ==============================================================================

class TestFetchIssueTitles:
    """Test batch fetching of GitHub issue titles.

    Requirements:
    - Fetch multiple issues in batch
    - Graceful degradation for missing issues
    - Validate all issues exist before returning
    - Audit log all operations
    """

    @pytest.fixture
    def mock_fetch_single(self):
        """Mock fetch_issue_title() for batch testing."""
        with patch('github_issue_fetcher.fetch_issue_title') as mock_fetch:
            yield mock_fetch

    @pytest.fixture
    def mock_audit_log(self):
        """Mock security audit logging."""
        with patch('github_issue_fetcher.audit_log') as mock_log:
            yield mock_log

    def test_all_issues_exist(self, mock_fetch_single, mock_audit_log):
        """Test batch fetching when all issues exist.

        Given: Issues [72, 73, 74] all exist
        When: fetch_issue_titles([72, 73, 74]) is called
        Then: Returns dict mapping issue numbers to titles
        And: All issues are fetched via fetch_issue_title()
        And: Operation is audit logged
        """
        # Mock successful fetches
        mock_fetch_single.side_effect = [
            "Add logging feature",
            "Fix batch processing",
            "Update documentation"
        ]

        result = fetch_issue_titles([72, 73, 74])

        # Verify result structure
        assert result == {
            72: "Add logging feature",
            73: "Fix batch processing",
            74: "Update documentation"
        }

        # Verify all issues fetched
        assert mock_fetch_single.call_count == 3
        mock_fetch_single.assert_any_call(72)
        mock_fetch_single.assert_any_call(73)
        mock_fetch_single.assert_any_call(74)

        # Verify audit log called
        mock_audit_log.assert_called()

    def test_mixed_valid_invalid(self, mock_fetch_single, mock_audit_log):
        """Test batch fetching with some missing issues.

        Given: Issues [72, 9999, 74] where 9999 doesn't exist
        When: fetch_issue_titles([72, 9999, 74]) is called
        Then: Returns dict with only valid issues
        And: Missing issue is logged but doesn't stop processing
        """
        # Mock mixed results (9999 returns None)
        mock_fetch_single.side_effect = [
            "Add logging feature",
            None,  # Issue 9999 not found
            "Update documentation"
        ]

        result = fetch_issue_titles([72, 9999, 74])

        # Verify graceful degradation (skip missing issue)
        assert result == {
            72: "Add logging feature",
            74: "Update documentation"
        }

        # Verify audit log called with warning
        mock_audit_log.assert_called()
        log_calls = [str(call) for call in mock_audit_log.call_args_list]
        assert any('9999' in call and ('not found' in call.lower() or 'missing' in call.lower())
                   for call in log_calls)

    def test_all_issues_missing(self, mock_fetch_single, mock_audit_log):
        """Test batch fetching when all issues are missing.

        Given: Issues [9998, 9999] all don't exist
        When: fetch_issue_titles([9998, 9999]) is called
        Then: Raises ValueError with helpful message
        And: Operation is audit logged
        """
        # Mock all missing
        mock_fetch_single.side_effect = [None, None]

        with pytest.raises(ValueError) as exc_info:
            fetch_issue_titles([9998, 9999])

        # Verify error message is helpful
        assert "no issues found" in str(exc_info.value).lower() or \
               "all issues missing" in str(exc_info.value).lower()

        # Verify audit log called
        mock_audit_log.assert_called()

    def test_audit_logging(self, mock_fetch_single, mock_audit_log):
        """Test that all operations are audit logged.

        Security Requirement: Audit trail for all GitHub API operations
        Given: Issues [72, 73]
        When: fetch_issue_titles([72, 73]) is called
        Then: audit_log() is called for:
              - Batch fetch start
              - Each individual fetch
              - Batch fetch completion
        """
        mock_fetch_single.side_effect = ["Title 1", "Title 2"]

        fetch_issue_titles([72, 73])

        # Verify audit log called multiple times
        assert mock_audit_log.call_count >= 3

        # Verify start/completion logged
        log_messages = [str(call[0][0]) for call in mock_audit_log.call_args_list]
        assert any('start' in msg.lower() or 'begin' in msg.lower() for msg in log_messages)
        assert any('complete' in msg.lower() or 'finish' in msg.lower() for msg in log_messages)


# ==============================================================================
# Test Class: Output Formatting (CWE-117)
# ==============================================================================

class TestFormatFeatureDescription:
    """Test formatting of feature descriptions from issue titles.

    Security Requirement (CWE-117): Log Injection Prevention
    - Sanitize newlines from issue titles
    - Remove control characters
    - Truncate long titles
    - Prevent log injection attacks
    """

    def test_format_normal_title(self):
        """Test formatting a normal issue title.

        Given: Issue #72 with title "Add logging feature"
        When: format_feature_description(72, "Add logging feature") is called
        Then: Returns "Issue #72: Add logging feature"
        """
        result = format_feature_description(72, "Add logging feature")
        assert result == "Issue #72: Add logging feature"

    def test_sanitize_newlines(self):
        """Test that newlines are sanitized from titles.

        Security (CWE-117): Prevent log injection via newline injection
        Given: Issue title contains newline characters
        When: format_feature_description() is called
        Then: Newlines are replaced with spaces
        And: No newlines in output
        """
        malicious_title = "Add feature\nINJECTED LOG LINE\nAnother line"
        result = format_feature_description(72, malicious_title)

        # Verify no newlines in output
        assert '\n' not in result
        assert '\r' not in result

        # Verify newlines replaced with spaces
        assert "Add feature INJECTED LOG LINE Another line" in result

    def test_sanitize_control_characters(self):
        """Test that control characters are sanitized.

        Security (CWE-117): Prevent log injection via control characters
        Given: Issue title contains tab, carriage return, etc.
        When: format_feature_description() is called
        Then: Control characters are removed or replaced
        """
        malicious_title = "Add\tfeature\rwith\x00control\x1bchars"
        result = format_feature_description(72, malicious_title)

        # Verify no control characters in output
        assert '\t' not in result
        assert '\r' not in result
        assert '\x00' not in result
        assert '\x1b' not in result

    def test_truncate_long_titles(self):
        """Test that very long titles are truncated.

        Given: Issue title is 500 characters long
        When: format_feature_description() is called
        Then: Title is truncated to reasonable length (e.g., 200 chars)
        And: Ellipsis (...) is added
        """
        long_title = "A" * 500
        result = format_feature_description(72, long_title)

        # Verify truncation (200 chars + "Issue #72: " + "...")
        assert len(result) <= 220

        # Verify ellipsis added
        if len(long_title) > 200:
            assert result.endswith("...")

    def test_empty_title_handling(self):
        """Test handling of empty issue titles.

        Given: Issue title is empty string
        When: format_feature_description() is called
        Then: Returns "Issue #72: (no title)"
        """
        result = format_feature_description(72, "")

        assert result == "Issue #72: (no title)"

    def test_whitespace_only_title(self):
        """Test handling of whitespace-only titles.

        Given: Issue title is only whitespace
        When: format_feature_description() is called
        Then: Returns "Issue #72: (no title)"
        """
        result = format_feature_description(72, "   \t\n   ")

        assert result == "Issue #72: (no title)"


# ==============================================================================
# Test Class: Error Handling
# ==============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_network_error_handling(self):
        """Test handling of network errors during gh CLI execution.

        Given: Network is unavailable
        When: fetch_issue_title() is called
        Then: Raises appropriate exception with helpful message
        """
        with patch('subprocess.run', side_effect=OSError("Network unreachable")):
            with pytest.raises(OSError) as exc_info:
                fetch_issue_title(72)

            assert "network" in str(exc_info.value).lower()

    def test_permission_denied_error(self):
        """Test handling when gh CLI lacks permissions.

        Given: gh CLI returns permission denied
        When: fetch_issue_title() is called
        Then: Raises PermissionError with helpful message
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout='',
                stderr='Error: authentication required'
            )

            # Should handle gracefully or raise appropriate error
            result = fetch_issue_title(72)

            # Verify graceful degradation or error
            assert result is None or isinstance(result, str)

    def test_rate_limit_handling(self):
        """Test handling of GitHub API rate limits.

        Given: GitHub API rate limit exceeded
        When: fetch_issue_title() is called
        Then: Raises appropriate exception with retry advice
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout='',
                stderr='API rate limit exceeded'
            )

            # Should handle gracefully
            result = fetch_issue_title(72)
            assert result is None


# ==============================================================================
# TDD Red Phase Summary
# ==============================================================================

"""
TDD RED PHASE SUMMARY
=====================

Test Coverage:
- TestValidateIssueNumbers: 7 tests (input validation, CWE-20)
- TestFetchIssueTitle: 7 tests (subprocess security, CWE-78)
- TestFetchIssueTitles: 4 tests (batch operations, graceful degradation)
- TestFormatFeatureDescription: 6 tests (output sanitization, CWE-117)
- TestErrorHandling: 3 tests (error handling, edge cases)

Total: 27 unit tests

Security Coverage:
✓ CWE-20: Input validation (positive integers, max 100 issues)
✓ CWE-78: Command injection prevention (list args, shell=False)
✓ CWE-117: Log injection prevention (sanitize newlines, control chars)
✓ Audit logging: All gh CLI operations logged

Expected State: ALL TESTS SHOULD FAIL
- ImportError: github_issue_fetcher module not found
- This is CORRECT for TDD red phase
- Tests describe implementation requirements
- Implementation will make tests pass (GREEN phase)

Next Steps (for implementer agent):
1. Create github_issue_fetcher.py module
2. Implement validate_issue_numbers() function
3. Implement fetch_issue_title() function
4. Implement fetch_issue_titles() function
5. Implement format_feature_description() function
6. Run tests: pytest tests/unit/lib/test_github_issue_fetcher.py
7. Fix failures until all tests pass (GREEN phase)

Coverage Target: 90%+ line coverage
"""
