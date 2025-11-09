"""
TDD Red Phase: Unit tests for github_issue_automation.py library

Tests for GitHub issue creation with research integration.
These tests should FAIL until implementation is complete.

Related to: GitHub Issue #58 - Automatic GitHub issue creation with research
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.github_issue_automation import (
    GitHubIssueAutomation,
    IssueCreationResult,
    create_github_issue,
    validate_issue_title,
    validate_issue_body,
    check_gh_available,
    parse_issue_number,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create temporary project directory for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir(parents=True)

    # Create .git directory (indicates git repo)
    git_dir = project_root / ".git"
    git_dir.mkdir()

    return project_root


@pytest.fixture
def automation(temp_project):
    """Create GitHubIssueAutomation instance."""
    return GitHubIssueAutomation(project_root=temp_project)


# =============================================================================
# TEST TITLE VALIDATION
# =============================================================================


class TestValidateIssueTitle:
    """Test title validation for security and correctness."""

    def test_validate_title_valid(self):
        """Test that valid title passes validation."""
        valid_title = "Add automated testing for new feature"
        result = validate_issue_title(valid_title)
        assert result is True

    def test_validate_title_too_long(self):
        """Test that excessively long title is rejected (CWE-20)."""
        long_title = "A" * 300  # Exceeds reasonable GitHub limit
        with pytest.raises(ValueError, match="Title exceeds maximum length"):
            validate_issue_title(long_title)

    def test_validate_title_shell_metacharacters(self):
        """Test that shell metacharacters in title are rejected (CWE-78)."""
        dangerous_titles = [
            "Feature; rm -rf /",
            "Bug && malicious_command",
            "Issue | cat /etc/passwd",
            "Feature `whoami`",
            "Bug $(dangerous)",
        ]

        for title in dangerous_titles:
            with pytest.raises(ValueError, match="contains invalid characters"):
                validate_issue_title(title)

    def test_validate_title_empty_string(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            validate_issue_title("")

    def test_validate_title_whitespace_only(self):
        """Test that whitespace-only title is rejected."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            validate_issue_title("   \t\n   ")

    def test_validate_title_control_characters(self):
        """Test that control characters are rejected (CWE-117)."""
        title_with_control_chars = "Feature\x00\x01\x02"
        with pytest.raises(ValueError, match="contains invalid characters"):
            validate_issue_title(title_with_control_chars)

    def test_validate_title_newlines(self):
        """Test that newlines in title are rejected."""
        title_with_newline = "Feature\nwith newline"
        with pytest.raises(ValueError, match="contains invalid characters"):
            validate_issue_title(title_with_newline)

    def test_validate_title_with_allowed_special_chars(self):
        """Test that allowed special characters pass validation."""
        valid_titles = [
            "Fix bug: authentication fails on mobile",
            "Feature (enhancement): add dark mode",
            "Update README.md - add installation instructions",
            "Refactor code_review.py for better performance",
        ]

        for title in valid_titles:
            result = validate_issue_title(title)
            assert result is True


# =============================================================================
# TEST BODY VALIDATION
# =============================================================================


class TestValidateIssueBody:
    """Test body validation for security and correctness."""

    def test_validate_body_valid(self):
        """Test that valid body passes validation."""
        valid_body = """
## Summary
This is a valid issue body.

## Details
- Point 1
- Point 2
"""
        result = validate_issue_body(valid_body)
        assert result is True

    def test_validate_body_too_long(self):
        """Test that excessively long body is rejected (CWE-20)."""
        long_body = "A" * 100000  # Exceeds reasonable limit
        with pytest.raises(ValueError, match="Body exceeds maximum length"):
            validate_issue_body(long_body)

    def test_validate_body_empty_string(self):
        """Test that empty body is rejected."""
        with pytest.raises(ValueError, match="Body cannot be empty"):
            validate_issue_body("")

    def test_validate_body_whitespace_only(self):
        """Test that whitespace-only body is rejected."""
        with pytest.raises(ValueError, match="Body cannot be empty"):
            validate_issue_body("   \t\n   ")

    def test_validate_body_with_markdown(self):
        """Test that markdown formatting is allowed."""
        markdown_body = """
# Heading 1
## Heading 2

**Bold text** and *italic text*

- List item 1
- List item 2

```python
def example():
    pass
```

[Link](https://example.com)
"""
        result = validate_issue_body(markdown_body)
        assert result is True

    def test_validate_body_with_code_blocks(self):
        """Test that code blocks are allowed and preserved."""
        body_with_code = """
## Code Example

```bash
git commit -m "message"
```
"""
        result = validate_issue_body(body_with_code)
        assert result is True


# =============================================================================
# TEST GH CLI DETECTION
# =============================================================================


class TestCheckGhAvailable:
    """Test GitHub CLI availability checking."""

    @patch('subprocess.run')
    def test_check_gh_available_success(self, mock_run):
        """Test that gh CLI detected when installed and authenticated."""
        # Mock successful gh --version
        mock_run.return_value = Mock(
            returncode=0,
            stdout="gh version 2.40.0",
        )

        result = check_gh_available()
        assert result is True

        # Verify gh --version was called
        mock_run.assert_called_once()
        assert "gh" in mock_run.call_args[0][0]

    @patch('subprocess.run')
    def test_check_gh_available_not_installed(self, mock_run):
        """Test that FileNotFoundError raised when gh not installed."""
        mock_run.side_effect = FileNotFoundError("gh not found")

        with pytest.raises(FileNotFoundError, match="GitHub CLI.*not installed"):
            check_gh_available()

    @patch('subprocess.run')
    def test_check_gh_available_not_authenticated(self, mock_run):
        """Test that authentication error raised when gh not authenticated."""
        # Mock gh auth status failure
        mock_run.side_effect = [
            Mock(returncode=0, stdout="gh version 2.40.0"),  # Version check passes
            Mock(returncode=1, stderr="not logged in"),  # Auth check fails
        ]

        with pytest.raises(RuntimeError, match="not authenticated"):
            check_gh_available()

    @patch('subprocess.run')
    def test_check_gh_available_network_error(self, mock_run):
        """Test that network errors are handled gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 5)

        with pytest.raises(RuntimeError, match="network error"):
            check_gh_available()


# =============================================================================
# TEST ISSUE NUMBER PARSING
# =============================================================================


class TestParseIssueNumber:
    """Test parsing issue number from gh CLI output."""

    def test_parse_issue_number_from_url(self):
        """Test parsing issue number from GitHub URL."""
        gh_output = "https://github.com/owner/repo/issues/123"
        result = parse_issue_number(gh_output)
        assert result == 123

    def test_parse_issue_number_with_surrounding_text(self):
        """Test parsing issue number from output with extra text."""
        gh_output = "Created issue https://github.com/owner/repo/issues/456\n"
        result = parse_issue_number(gh_output)
        assert result == 456

    def test_parse_issue_number_invalid_format(self):
        """Test that invalid format raises error."""
        invalid_output = "No issue number here"
        with pytest.raises(ValueError, match="Could not parse issue number"):
            parse_issue_number(invalid_output)

    def test_parse_issue_number_multiple_urls(self):
        """Test that first issue number is returned when multiple URLs present."""
        gh_output = "https://github.com/owner/repo/issues/111 and https://github.com/owner/repo/issues/222"
        result = parse_issue_number(gh_output)
        assert result == 111

    def test_parse_issue_number_pr_url_rejected(self):
        """Test that PR URLs are rejected (not issue URLs)."""
        pr_url = "https://github.com/owner/repo/pull/789"
        with pytest.raises(ValueError, match="Expected issue URL"):
            parse_issue_number(pr_url)


# =============================================================================
# TEST COMMAND BUILDING
# =============================================================================


class TestBuildGhCommand:
    """Test GitHub CLI command construction."""

    def test_build_gh_command_basic(self, automation):
        """Test building basic gh issue create command."""
        command = automation._build_gh_command(
            title="Test issue",
            body="Test body",
        )

        assert "gh" in command
        assert "issue" in command
        assert "create" in command
        assert "--title" in command
        assert "Test issue" in command
        assert "--body" in command
        assert "Test body" in command

    def test_build_gh_command_with_labels(self, automation):
        """Test building command with labels."""
        command = automation._build_gh_command(
            title="Test issue",
            body="Test body",
            labels=["bug", "high-priority"],
        )

        assert "--label" in command or "-l" in command
        assert "bug" in command
        assert "high-priority" in command

    def test_build_gh_command_with_assignee(self, automation):
        """Test building command with assignee."""
        command = automation._build_gh_command(
            title="Test issue",
            body="Test body",
            assignee="username",
        )

        assert "--assignee" in command or "-a" in command
        assert "username" in command

    def test_build_gh_command_with_milestone(self, automation):
        """Test building command with milestone."""
        command = automation._build_gh_command(
            title="Test issue",
            body="Test body",
            milestone="v2.0",
        )

        assert "--milestone" in command or "-m" in command
        assert "v2.0" in command

    def test_build_gh_command_escapes_special_chars(self, automation):
        """Test that special characters are properly escaped."""
        command = automation._build_gh_command(
            title='Issue with "quotes"',
            body="Body with 'single quotes'",
        )

        # Command should handle quotes safely
        assert "gh" in command
        # Exact escaping depends on implementation


# =============================================================================
# TEST ISSUE CREATION
# =============================================================================


class TestCreateGitHubIssue:
    """Test GitHub issue creation workflow."""

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_success(self, mock_check_gh, mock_run, automation):
        """Test successful issue creation."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/123",
        )

        result = automation.create_issue(
            title="Test issue",
            body="Test body",
        )

        assert result.success is True
        assert result.issue_number == 123
        assert result.issue_url == "https://github.com/owner/repo/issues/123"
        assert result.error is None

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_with_labels(self, mock_check_gh, mock_run, automation):
        """Test issue creation with labels."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/456",
        )

        result = automation.create_issue(
            title="Bug report",
            body="Description",
            labels=["bug", "priority:high"],
        )

        assert result.success is True
        assert result.issue_number == 456
        # Verify labels were passed to command
        call_args = mock_run.call_args[0][0]
        assert any("bug" in str(arg) for arg in call_args)

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_gh_error(self, mock_check_gh, mock_run, automation):
        """Test handling of gh CLI errors."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=1,
            stderr="GraphQL: Validation failed",
        )

        result = automation.create_issue(
            title="Test issue",
            body="Test body",
        )

        assert result.success is False
        assert result.issue_number is None
        assert result.issue_url is None
        assert "GraphQL" in result.error or "Validation failed" in result.error

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_network_timeout(self, mock_check_gh, mock_run, automation):
        """Test handling of network timeouts."""
        mock_check_gh.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

        result = automation.create_issue(
            title="Test issue",
            body="Test body",
        )

        assert result.success is False
        assert "timeout" in result.error.lower()

    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_gh_not_available(self, mock_check_gh, automation):
        """Test handling when gh CLI not available."""
        mock_check_gh.side_effect = FileNotFoundError("gh not found")

        with pytest.raises(FileNotFoundError):
            automation.create_issue(
                title="Test issue",
                body="Test body",
            )

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_validates_title(self, mock_check_gh, mock_run, automation):
        """Test that title is validated before creation."""
        mock_check_gh.return_value = True

        with pytest.raises(ValueError, match="contains invalid characters"):
            automation.create_issue(
                title="Issue; rm -rf /",
                body="Test body",
            )

        # gh should not be called if validation fails
        mock_run.assert_not_called()

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_validates_body(self, mock_check_gh, mock_run, automation):
        """Test that body is validated before creation."""
        mock_check_gh.return_value = True

        with pytest.raises(ValueError, match="Body cannot be empty"):
            automation.create_issue(
                title="Valid title",
                body="",
            )

        # gh should not be called if validation fails
        mock_run.assert_not_called()


# =============================================================================
# TEST SECURITY VALIDATION
# =============================================================================


class TestSecurityValidation:
    """Test security validation and audit logging."""

    def test_path_validation_called_on_init(self, temp_project):
        """Test that path validation is called during initialization."""
        with patch('plugins.autonomous_dev.lib.security_utils.validate_path') as mock_validate:
            mock_validate.return_value = temp_project
            automation = GitHubIssueAutomation(project_root=temp_project)

            # Verify path validation was called
            mock_validate.assert_called_once_with(
                temp_project,
                "project_root"
            )

    def test_path_traversal_blocked_via_project_root(self):
        """Test that path traversal attacks are blocked (CWE-22)."""
        malicious_path = Path("/tmp/../../../etc/passwd")

        with pytest.raises(ValueError, match="Path.*not in whitelist"):
            GitHubIssueAutomation(project_root=malicious_path)

    def test_symlink_attack_blocked(self, tmp_path):
        """Test that symlink attacks are blocked (CWE-59)."""
        # Create symlink to sensitive directory
        target = tmp_path / "target"
        target.mkdir()
        symlink = tmp_path / "symlink"
        symlink.symlink_to(target)

        with pytest.raises(ValueError, match="Symlink.*not allowed"):
            GitHubIssueAutomation(project_root=symlink)

    @patch('plugins.autonomous_dev.lib.security_utils.audit_log')
    def test_audit_logging_on_issue_creation(self, mock_audit, automation):
        """Test that issue creation is logged to audit log."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="https://github.com/owner/repo/issues/123",
            )

            with patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available', return_value=True):
                automation.create_issue(
                    title="Test issue",
                    body="Test body",
                )

            # Verify audit log was called
            assert mock_audit.called
            call_args = mock_audit.call_args[1]
            assert call_args['action'] == 'github_issue_create'
            assert 'issue_number' in call_args['details']

    def test_command_injection_prevention(self, automation):
        """Test that command injection is prevented (CWE-78)."""
        dangerous_inputs = [
            "Title; malicious_command",
            "Title && dangerous",
            "Title | cat /etc/passwd",
        ]

        for dangerous_title in dangerous_inputs:
            with pytest.raises(ValueError):
                automation.create_issue(
                    title=dangerous_title,
                    body="Body",
                )


# =============================================================================
# TEST RESULT DATA CLASS
# =============================================================================


class TestIssueCreationResult:
    """Test IssueCreationResult dataclass."""

    def test_result_success_attributes(self):
        """Test that successful result has expected attributes."""
        result = IssueCreationResult(
            success=True,
            issue_number=123,
            issue_url="https://github.com/owner/repo/issues/123",
            error=None,
            details={"labels": ["bug"]},
        )

        assert result.success is True
        assert result.issue_number == 123
        assert result.issue_url == "https://github.com/owner/repo/issues/123"
        assert result.error is None
        assert result.details == {"labels": ["bug"]}

    def test_result_failure_attributes(self):
        """Test that failure result has expected attributes."""
        result = IssueCreationResult(
            success=False,
            issue_number=None,
            issue_url=None,
            error="GitHub API error",
            details={"error_code": 500},
        )

        assert result.success is False
        assert result.issue_number is None
        assert result.issue_url is None
        assert result.error == "GitHub API error"
        assert result.details == {"error_code": 500}

    def test_result_to_dict(self):
        """Test conversion to dictionary for JSON serialization."""
        result = IssueCreationResult(
            success=True,
            issue_number=123,
            issue_url="https://github.com/owner/repo/issues/123",
            error=None,
            details={},
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict['success'] is True
        assert result_dict['issue_number'] == 123
        assert result_dict['issue_url'] == "https://github.com/owner/repo/issues/123"


# =============================================================================
# TEST CONVENIENCE FUNCTION
# =============================================================================


class TestConvenienceFunction:
    """Test high-level create_github_issue() convenience function."""

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_github_issue_convenience_function(self, mock_check_gh, mock_run, temp_project):
        """Test that convenience function works correctly."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/789",
        )

        result = create_github_issue(
            title="Convenience test",
            body="Test body",
            project_root=temp_project,
        )

        assert result.success is True
        assert result.issue_number == 789

    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_github_issue_with_defaults(self, mock_check_gh, temp_project):
        """Test that convenience function uses sensible defaults."""
        mock_check_gh.return_value = True

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="https://github.com/owner/repo/issues/111",
            )

            result = create_github_issue(
                title="Test",
                body="Body",
                project_root=temp_project,
            )

            assert result.success is True
            # Default project_root should be used if not specified


# =============================================================================
# TEST ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test comprehensive error handling."""

    def test_nonexistent_project_root_raises_error(self):
        """Test that nonexistent project root raises error."""
        nonexistent = Path("/nonexistent/path/to/project")

        with pytest.raises(ValueError):
            GitHubIssueAutomation(project_root=nonexistent)

    def test_file_instead_of_directory_raises_error(self, tmp_path):
        """Test that file path instead of directory raises error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        with pytest.raises(ValueError):
            GitHubIssueAutomation(project_root=file_path)

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_malformed_gh_output_handled_gracefully(self, mock_check_gh, mock_run, automation):
        """Test that malformed gh output is handled gracefully."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Unexpected output format",
        )

        result = automation.create_issue(
            title="Test",
            body="Body",
        )

        # Should fail gracefully, not crash
        assert result.success is False
        assert "Could not parse" in result.error or "parse" in result.error.lower()

    def test_empty_labels_list_handled_correctly(self, automation):
        """Test that empty labels list is handled correctly."""
        command = automation._build_gh_command(
            title="Test",
            body="Body",
            labels=[],
        )

        # Empty labels should not cause errors
        assert "gh" in command

    def test_none_assignee_handled_correctly(self, automation):
        """Test that None assignee is handled correctly."""
        command = automation._build_gh_command(
            title="Test",
            body="Body",
            assignee=None,
        )

        # None assignee should not cause errors
        assert "gh" in command


# =============================================================================
# TEST INTEGRATION WITH RESEARCH
# =============================================================================


class TestResearchIntegration:
    """Test integration with researcher agent output."""

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_from_research_output(self, mock_check_gh, mock_run, automation):
        """Test creating issue from researcher agent session log."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/999",
        )

        # Simulate research output
        research_title = "Implement caching layer for API responses"
        research_body = """
## Research Summary

### Current Implementation
- API calls are not cached
- Performance degrades with high request volume

### Proposed Solution
- Add Redis caching layer
- Implement cache invalidation strategy
- Set TTL based on data type

### References
- [Redis Best Practices](https://example.com)
- [Caching Patterns](https://example.com)
"""

        result = automation.create_issue(
            title=research_title,
            body=research_body,
            labels=["enhancement", "performance"],
        )

        assert result.success is True
        assert result.issue_number == 999

    def test_validate_research_output_format(self):
        """Test that research output format is validated."""
        # Research output should have required sections
        required_sections = ["Summary", "Details", "References"]

        research_body = """
## Summary
Brief overview

## Details
Detailed information

## References
- Reference 1
"""

        # Body should pass validation
        assert validate_issue_body(research_body) is True


# =============================================================================
# END OF TESTS
# =============================================================================
