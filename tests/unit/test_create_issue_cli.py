"""
TDD Red Phase: Unit tests for create_issue.py CLI script

Tests for command-line interface wrapper for GitHub issue creation.
These tests should FAIL until implementation is complete.

Related to: GitHub Issue #58 - Automatic GitHub issue creation with research
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.scripts.create_issue import (
    parse_args,
    format_output_human,
    format_output_json,
    main,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create temporary project directory for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir(parents=True)

    # Create .git directory
    git_dir = project_root / ".git"
    git_dir.mkdir()

    return project_root


@pytest.fixture
def mock_result_success():
    """Mock successful IssueCreationResult."""
    return Mock(
        success=True,
        issue_number=123,
        issue_url="https://github.com/owner/repo/issues/123",
        error=None,
        details={"labels": ["bug"]},
    )


@pytest.fixture
def mock_result_failure():
    """Mock failed IssueCreationResult."""
    return Mock(
        success=False,
        issue_number=None,
        issue_url=None,
        error="GitHub API error: rate limit exceeded",
        details={"status_code": 403},
    )


# =============================================================================
# TEST ARGUMENT PARSING
# =============================================================================


class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_args_required_only(self):
        """Test parsing with only required arguments."""
        args = parse_args([
            "--title", "Test issue",
            "--body", "Test body",
        ])

        assert args.title == "Test issue"
        assert args.body == "Test body"
        assert args.labels is None or args.labels == []
        assert args.assignee is None
        assert args.json is False
        assert args.verbose is False

    def test_parse_args_with_labels(self):
        """Test parsing with labels."""
        args = parse_args([
            "--title", "Bug report",
            "--body", "Description",
            "--labels", "bug,priority:high",
        ])

        assert args.title == "Bug report"
        assert args.labels == "bug,priority:high" or args.labels == ["bug", "priority:high"]

    def test_parse_args_with_assignee(self):
        """Test parsing with assignee."""
        args = parse_args([
            "--title", "Feature request",
            "--body", "Description",
            "--assignee", "username",
        ])

        assert args.assignee == "username"

    def test_parse_args_with_json_flag(self):
        """Test parsing with JSON output flag."""
        args = parse_args([
            "--title", "Test",
            "--body", "Body",
            "--json",
        ])

        assert args.json is True

    def test_parse_args_with_verbose_flag(self):
        """Test parsing with verbose flag."""
        args = parse_args([
            "--title", "Test",
            "--body", "Body",
            "--verbose",
        ])

        assert args.verbose is True

    def test_parse_args_short_flags(self):
        """Test parsing with short flag variants."""
        args = parse_args([
            "--title", "Test",
            "--body", "Body",
            "-v",  # verbose
        ])

        assert args.verbose is True

    def test_parse_args_with_project_root(self):
        """Test parsing with project root path."""
        args = parse_args([
            "--title", "Test",
            "--body", "Body",
            "--project-root", "/path/to/project",
        ])

        assert args.project_root == "/path/to/project"

    def test_parse_args_missing_required_raises_error(self):
        """Test that missing required arguments raises error."""
        with pytest.raises(SystemExit):
            # Missing --body
            parse_args(["--title", "Test"])

    def test_parse_args_with_milestone(self):
        """Test parsing with milestone."""
        args = parse_args([
            "--title", "Test",
            "--body", "Body",
            "--milestone", "v2.0",
        ])

        assert args.milestone == "v2.0"

    def test_parse_args_with_all_options(self):
        """Test parsing with all options specified."""
        args = parse_args([
            "--title", "Complete test",
            "--body", "Full description",
            "--labels", "bug,urgent",
            "--assignee", "developer",
            "--milestone", "v1.5",
            "--project-root", "/project",
            "--json",
            "--verbose",
        ])

        assert args.title == "Complete test"
        assert args.body == "Full description"
        assert args.assignee == "developer"
        assert args.milestone == "v1.5"
        assert args.project_root == "/project"
        assert args.json is True
        assert args.verbose is True


# =============================================================================
# TEST OUTPUT FORMATTING - HUMAN READABLE
# =============================================================================


class TestOutputFormattingHuman:
    """Test human-readable output formatting."""

    def test_format_output_human_success(self, mock_result_success):
        """Test formatting successful result for human output."""
        output = format_output_human(mock_result_success)

        assert "SUCCESS" in output or "Created" in output
        assert "123" in output  # Issue number
        assert "https://github.com/owner/repo/issues/123" in output

    def test_format_output_human_failure(self, mock_result_failure):
        """Test formatting failed result for human output."""
        output = format_output_human(mock_result_failure)

        assert "FAILED" in output or "Error" in output
        assert "rate limit" in output.lower()

    def test_format_output_human_includes_url(self, mock_result_success):
        """Test that human output includes clickable URL."""
        output = format_output_human(mock_result_success)

        assert "https://github.com/owner/repo/issues/123" in output

    def test_format_output_human_includes_issue_number(self, mock_result_success):
        """Test that human output includes issue number."""
        output = format_output_human(mock_result_success)

        assert "#123" in output or "Issue #123" in output or "123" in output

    def test_format_output_human_shows_error_message(self, mock_result_failure):
        """Test that human output shows error message."""
        output = format_output_human(mock_result_failure)

        assert "rate limit exceeded" in output.lower()


# =============================================================================
# TEST OUTPUT FORMATTING - JSON
# =============================================================================


class TestOutputFormattingJson:
    """Test JSON output formatting."""

    def test_format_output_json_success(self, mock_result_success):
        """Test formatting successful result as JSON."""
        output = format_output_json(mock_result_success)

        # Should be valid JSON
        data = json.loads(output)

        assert data['success'] is True
        assert data['issue_number'] == 123
        assert data['issue_url'] == "https://github.com/owner/repo/issues/123"
        assert data['error'] is None

    def test_format_output_json_failure(self, mock_result_failure):
        """Test formatting failed result as JSON."""
        output = format_output_json(mock_result_failure)

        # Should be valid JSON
        data = json.loads(output)

        assert data['success'] is False
        assert data['issue_number'] is None
        assert data['issue_url'] is None
        assert "rate limit" in data['error']

    def test_format_output_json_includes_details(self, mock_result_success):
        """Test that JSON output includes details."""
        output = format_output_json(mock_result_success)

        data = json.loads(output)

        assert 'details' in data
        assert data['details']['labels'] == ["bug"]

    def test_format_output_json_valid_structure(self, mock_result_success):
        """Test that JSON output has valid structure."""
        output = format_output_json(mock_result_success)

        data = json.loads(output)

        # Required fields
        assert 'success' in data
        assert 'issue_number' in data
        assert 'issue_url' in data
        assert 'error' in data


# =============================================================================
# TEST MAIN FUNCTION - SUCCESS CASES
# =============================================================================


class TestMainFunctionSuccess:
    """Test main() function success cases."""

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_success_human_output(self, mock_stdout, mock_automation_class, temp_project):
        """Test main() with successful issue creation and human output."""
        # Mock automation instance
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=True,
            issue_number=123,
            issue_url="https://github.com/owner/repo/issues/123",
            error=None,
            details={},
            to_dict=lambda: {
                'success': True,
                'issue_number': 123,
                'issue_url': "https://github.com/owner/repo/issues/123",
                'error': None,
            }
        )
        mock_automation_class.return_value = mock_automation

        # Run main
        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test issue',
            '--body', 'Test body',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 0
        output = mock_stdout.getvalue()
        assert "123" in output

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_success_json_output(self, mock_stdout, mock_automation_class, temp_project):
        """Test main() with successful issue creation and JSON output."""
        # Mock automation instance
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=True,
            issue_number=456,
            issue_url="https://github.com/owner/repo/issues/456",
            error=None,
            details={},
            to_dict=lambda: {
                'success': True,
                'issue_number': 456,
                'issue_url': "https://github.com/owner/repo/issues/456",
                'error': None,
            }
        )
        mock_automation_class.return_value = mock_automation

        # Run main with JSON flag
        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test issue',
            '--body', 'Test body',
            '--project-root', str(temp_project),
            '--json',
        ]):
            exit_code = main()

        assert exit_code == 0
        output = mock_stdout.getvalue()

        # Output should be valid JSON
        data = json.loads(output)
        assert data['success'] is True
        assert data['issue_number'] == 456

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    def test_main_success_with_labels(self, mock_automation_class, temp_project):
        """Test main() with labels."""
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=True,
            issue_number=789,
            issue_url="https://github.com/owner/repo/issues/789",
            error=None,
            details={},
        )
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Bug report',
            '--body', 'Description',
            '--labels', 'bug,priority:high',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 0

        # Verify create_issue was called with labels
        call_args = mock_automation.create_issue.call_args
        assert call_args is not None


# =============================================================================
# TEST MAIN FUNCTION - FAILURE CASES
# =============================================================================


class TestMainFunctionFailure:
    """Test main() function failure cases."""

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    @patch('sys.stderr', new_callable=StringIO)
    def test_main_failure_gh_error(self, mock_stderr, mock_automation_class, temp_project):
        """Test main() with GitHub API error."""
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=False,
            issue_number=None,
            issue_url=None,
            error="GitHub API error",
            details={},
            to_dict=lambda: {
                'success': False,
                'issue_number': None,
                'issue_url': None,
                'error': "GitHub API error",
            }
        )
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test',
            '--body', 'Body',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 1

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    def test_main_failure_validation_error(self, mock_automation_class, temp_project):
        """Test main() with validation error."""
        mock_automation = MagicMock()
        mock_automation.create_issue.side_effect = ValueError("Invalid title")
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Invalid; title',
            '--body', 'Body',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 1

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    def test_main_failure_gh_not_installed(self, mock_automation_class, temp_project):
        """Test main() when gh CLI not installed."""
        mock_automation = MagicMock()
        mock_automation.create_issue.side_effect = FileNotFoundError("gh not found")
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test',
            '--body', 'Body',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 1


# =============================================================================
# TEST VERBOSE OUTPUT
# =============================================================================


class TestVerboseOutput:
    """Test verbose output mode."""

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    @patch('sys.stdout', new_callable=StringIO)
    def test_verbose_shows_details(self, mock_stdout, mock_automation_class, temp_project):
        """Test that verbose mode shows detailed information."""
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=True,
            issue_number=123,
            issue_url="https://github.com/owner/repo/issues/123",
            error=None,
            details={"labels": ["bug"], "assignee": "user"},
        )
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test',
            '--body', 'Body',
            '--project-root', str(temp_project),
            '--verbose',
        ]):
            main()

        output = mock_stdout.getvalue()
        # Verbose output should include details
        assert len(output) > 0

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    @patch('sys.stdout', new_callable=StringIO)
    def test_verbose_shows_command_info(self, mock_stdout, mock_automation_class, temp_project):
        """Test that verbose mode shows command information."""
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=True,
            issue_number=123,
            issue_url="https://github.com/owner/repo/issues/123",
            error=None,
            details={},
        )
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test',
            '--body', 'Body',
            '--project-root', str(temp_project),
            '-v',  # Short flag
        ]):
            main()

        output = mock_stdout.getvalue()
        assert len(output) > 0


# =============================================================================
# TEST ERROR MESSAGES
# =============================================================================


class TestErrorMessages:
    """Test error message formatting and clarity."""

    def test_validation_error_message_helpful(self):
        """Test that validation errors provide helpful messages."""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['create_issue.py', '--title', 'Test']):
                # Missing --body should show helpful error
                parse_args(['--title', 'Test'])

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    @patch('sys.stderr', new_callable=StringIO)
    def test_gh_not_found_error_message(self, mock_stderr, mock_automation_class, temp_project):
        """Test error message when gh CLI not found."""
        mock_automation = MagicMock()
        mock_automation.create_issue.side_effect = FileNotFoundError("gh not found")
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test',
            '--body', 'Body',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 1
        # Error output should be helpful
        # (exact message depends on implementation)


# =============================================================================
# TEST EXIT CODES
# =============================================================================


class TestExitCodes:
    """Test exit code behavior."""

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    def test_exit_code_0_on_success(self, mock_automation_class, temp_project):
        """Test that exit code is 0 on success."""
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=True,
            issue_number=123,
            issue_url="https://github.com/owner/repo/issues/123",
            error=None,
            details={},
        )
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test',
            '--body', 'Body',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 0

    @patch('plugins.autonomous_dev.scripts.create_issue.GitHubIssueAutomation')
    def test_exit_code_1_on_failure(self, mock_automation_class, temp_project):
        """Test that exit code is 1 on failure."""
        mock_automation = MagicMock()
        mock_automation.create_issue.return_value = Mock(
            success=False,
            issue_number=None,
            issue_url=None,
            error="Error",
            details={},
        )
        mock_automation_class.return_value = mock_automation

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'Test',
            '--body', 'Body',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 1


# =============================================================================
# END OF TESTS
# =============================================================================
