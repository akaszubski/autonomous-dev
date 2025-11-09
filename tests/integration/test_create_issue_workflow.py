"""
TDD Red Phase: Integration tests for GitHub issue creation workflow

Tests for end-to-end workflow including agent coordination and CLI.
These tests should FAIL until implementation is complete.

Related to: GitHub Issue #58 - Automatic GitHub issue creation with research
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.github_issue_automation import (
    GitHubIssueAutomation,
    create_github_issue,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create temporary project with realistic structure."""
    project_root = tmp_path / "test_project"
    project_root.mkdir(parents=True)

    # Create git repo
    git_dir = project_root / ".git"
    git_dir.mkdir()

    # Create docs directory for session logs
    docs_dir = project_root / "docs" / "sessions"
    docs_dir.mkdir(parents=True)

    # Create plugin directory structure
    plugins_dir = project_root / "plugins" / "autonomous-dev"
    plugins_dir.mkdir(parents=True)

    agents_dir = plugins_dir / "agents"
    agents_dir.mkdir()

    return project_root


@pytest.fixture
def mock_session_log(temp_project):
    """Create mock researcher session log."""
    sessions_dir = temp_project / "docs" / "sessions"
    session_file = sessions_dir / "researcher_20250109_120000.json"

    session_data = {
        "agent": "researcher",
        "timestamp": "2025-01-09T12:00:00",
        "research_topic": "Implement caching layer",
        "findings": [
            "Redis is recommended for caching",
            "TTL should be configured per data type",
            "Cache invalidation is critical",
        ],
        "references": [
            "https://redis.io/docs/manual/patterns/",
            "https://aws.amazon.com/caching/best-practices/",
        ],
    }

    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


# =============================================================================
# TEST FULL WORKFLOW
# =============================================================================


class TestFullWorkflow:
    """Test complete GitHub issue creation workflow."""

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_create_issue_workflow_success(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test complete workflow from research to issue creation."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/123",
        )

        # Simulate issue creation from research
        automation = GitHubIssueAutomation(project_root=temp_project)

        result = automation.create_issue(
            title="Implement caching layer for API responses",
            body="""
## Research Summary

Based on research findings, we should implement a caching layer.

### Current Implementation
- No caching currently exists
- API calls hit database directly
- Performance degrades under load

### Proposed Solution
- Add Redis caching layer
- Configure TTL per data type
- Implement cache invalidation strategy

### References
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [AWS Caching Guide](https://aws.amazon.com/caching/best-practices/)
""",
            labels=["enhancement", "performance"],
        )

        assert result.success is True
        assert result.issue_number == 123
        assert result.issue_url == "https://github.com/owner/repo/issues/123"

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_workflow_with_all_metadata(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test workflow with labels, assignee, and milestone."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/456",
        )

        automation = GitHubIssueAutomation(project_root=temp_project)

        result = automation.create_issue(
            title="Security vulnerability in authentication",
            body="Details about security issue",
            labels=["security", "priority:critical"],
            assignee="security-team",
            milestone="v2.0",
        )

        assert result.success is True
        assert result.issue_number == 456

        # Verify gh command included all metadata
        call_args = mock_run.call_args[0][0]
        assert any("security" in str(arg) for arg in call_args)

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_workflow_handles_gh_failure_gracefully(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test that workflow handles gh CLI failures gracefully."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=1,
            stderr="GraphQL: Validation failed",
        )

        automation = GitHubIssueAutomation(project_root=temp_project)

        result = automation.create_issue(
            title="Test issue",
            body="Test body",
        )

        # Should fail gracefully with error message
        assert result.success is False
        assert result.error is not None
        assert "GraphQL" in result.error or "Validation" in result.error


# =============================================================================
# TEST RESEARCHER TO ISSUE-CREATOR COORDINATION
# =============================================================================


class TestResearcherToIssueCreator:
    """Test coordination between researcher and issue-creator agents."""

    @patch('subprocess.run')
    def test_researcher_output_to_issue_format(
        self, mock_run, temp_project, mock_session_log
    ):
        """Test converting researcher session log to issue format."""
        # Mock Task tool invocation for issue-creator agent
        mock_task_response = {
            "success": True,
            "formatted_issue": {
                "title": "Implement caching layer for API responses",
                "body": """
## Research Summary

Research indicates Redis caching would improve performance.

### Current State
- No caching layer exists
- Direct database access for all API calls

### Proposed Solution
- Implement Redis caching
- Configure TTL strategies
- Set up cache invalidation

### References
- https://redis.io/docs/manual/patterns/
- https://aws.amazon.com/caching/best-practices/
""",
                "labels": ["enhancement", "performance"],
            },
        }

        # Simulate issue-creator agent processing research log
        # (In real implementation, this would be via Task tool)

        # Verify the formatted output is suitable for GitHub issue
        formatted = mock_task_response["formatted_issue"]
        assert len(formatted["title"]) < 256
        assert "## Research Summary" in formatted["body"]
        assert len(formatted["labels"]) > 0

    def test_research_session_log_read(self, mock_session_log):
        """Test reading researcher session log."""
        # Verify session log exists and is valid JSON
        assert mock_session_log.exists()

        data = json.loads(mock_session_log.read_text())

        assert data["agent"] == "researcher"
        assert "research_topic" in data
        assert "findings" in data
        assert len(data["findings"]) > 0
        assert "references" in data

    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    @patch('subprocess.run')
    def test_end_to_end_research_to_issue(
        self, mock_run, mock_check_gh, temp_project, mock_session_log
    ):
        """Test complete flow from research log to GitHub issue."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/789",
        )

        # Read research session log
        research_data = json.loads(mock_session_log.read_text())

        # Convert to issue format (simulating issue-creator agent)
        title = f"Implement {research_data['research_topic']}"
        body = f"""
## Research Summary

Research findings from autonomous investigation.

### Key Findings
{chr(10).join(f'- {finding}' for finding in research_data['findings'])}

### References
{chr(10).join(f'- {ref}' for ref in research_data['references'])}
"""

        # Create issue
        automation = GitHubIssueAutomation(project_root=temp_project)
        result = automation.create_issue(
            title=title,
            body=body,
            labels=["research", "enhancement"],
        )

        assert result.success is True
        assert result.issue_number == 789


# =============================================================================
# TEST CLI INTEGRATION
# =============================================================================


class TestCliIntegration:
    """Test CLI integration with library."""

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_cli_creates_issue_successfully(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test that CLI script creates issue successfully."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/999",
        )

        # Simulate CLI invocation
        from plugins.autonomous_dev.scripts.create_issue import main

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'CLI test issue',
            '--body', 'Created via CLI',
            '--project-root', str(temp_project),
        ]):
            exit_code = main()

        assert exit_code == 0

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_cli_json_output(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test that CLI JSON output is valid."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/111",
        )

        from plugins.autonomous_dev.scripts.create_issue import main
        from io import StringIO

        with patch('sys.argv', [
            'create_issue.py',
            '--title', 'JSON test',
            '--body', 'Body',
            '--project-root', str(temp_project),
            '--json',
        ]):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = main()

                assert exit_code == 0
                output = mock_stdout.getvalue()

                # Output should be valid JSON
                data = json.loads(output)
                assert data['success'] is True
                assert data['issue_number'] == 111


# =============================================================================
# TEST ERROR RECOVERY
# =============================================================================


class TestErrorRecovery:
    """Test error recovery in integration scenarios."""

    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_graceful_degradation_no_gh_cli(self, mock_check_gh, temp_project):
        """Test graceful degradation when gh CLI not available."""
        mock_check_gh.side_effect = FileNotFoundError("gh not found")

        automation = GitHubIssueAutomation(project_root=temp_project)

        with pytest.raises(FileNotFoundError):
            automation.create_issue(
                title="Test",
                body="Body",
            )

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_retry_on_network_error(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test retry logic on network errors."""
        mock_check_gh.return_value = True

        # First call times out, second succeeds
        mock_run.side_effect = [
            subprocess.TimeoutExpired("gh", 30),
            Mock(
                returncode=0,
                stdout="https://github.com/owner/repo/issues/222",
            ),
        ]

        automation = GitHubIssueAutomation(project_root=temp_project)

        # First attempt should fail
        result1 = automation.create_issue(
            title="Test",
            body="Body",
        )
        assert result1.success is False

        # Second attempt should succeed
        result2 = automation.create_issue(
            title="Test",
            body="Body",
        )
        assert result2.success is True

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_validation_before_api_call(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test that validation happens before making API calls."""
        mock_check_gh.return_value = True

        automation = GitHubIssueAutomation(project_root=temp_project)

        with pytest.raises(ValueError):
            automation.create_issue(
                title="Invalid; title",
                body="Body",
            )

        # gh should never be called if validation fails
        mock_run.assert_not_called()


# =============================================================================
# TEST CONCURRENT OPERATIONS
# =============================================================================


class TestConcurrentOperations:
    """Test handling of concurrent issue creation."""

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_multiple_issues_created_sequentially(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test creating multiple issues sequentially."""
        mock_check_gh.return_value = True

        # Mock responses for multiple issues
        mock_run.side_effect = [
            Mock(returncode=0, stdout="https://github.com/owner/repo/issues/1"),
            Mock(returncode=0, stdout="https://github.com/owner/repo/issues/2"),
            Mock(returncode=0, stdout="https://github.com/owner/repo/issues/3"),
        ]

        automation = GitHubIssueAutomation(project_root=temp_project)

        results = []
        for i in range(3):
            result = automation.create_issue(
                title=f"Issue {i+1}",
                body=f"Body {i+1}",
            )
            results.append(result)

        # All should succeed
        assert all(r.success for r in results)
        assert [r.issue_number for r in results] == [1, 2, 3]


# =============================================================================
# TEST DATA VALIDATION
# =============================================================================


class TestDataValidation:
    """Test data validation across integration points."""

    def test_session_log_format_validation(self, mock_session_log):
        """Test that session log format is validated."""
        data = json.loads(mock_session_log.read_text())

        # Required fields
        assert "agent" in data
        assert "timestamp" in data
        assert "research_topic" in data
        assert "findings" in data

        # Data types
        assert isinstance(data["agent"], str)
        assert isinstance(data["findings"], list)

    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_issue_body_markdown_preserved(
        self, mock_check_gh, mock_run, temp_project
    ):
        """Test that markdown formatting is preserved in issue body."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/333",
        )

        markdown_body = """
# Main Heading

## Subheading

**Bold text** and *italic text*

- List item 1
- List item 2

```python
def example():
    pass
```
"""

        automation = GitHubIssueAutomation(project_root=temp_project)
        result = automation.create_issue(
            title="Markdown test",
            body=markdown_body,
        )

        assert result.success is True

        # Verify markdown was passed to gh command
        call_args = mock_run.call_args[0][0]
        # Body should be in the command somewhere
        assert any("```" in str(arg) or "python" in str(arg) for arg in call_args)


# =============================================================================
# TEST AUDIT LOGGING
# =============================================================================


class TestAuditLogging:
    """Test audit logging across integration points."""

    @patch('plugins.autonomous_dev.lib.security_utils.audit_log')
    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_audit_log_records_issue_creation(
        self, mock_check_gh, mock_run, mock_audit, temp_project
    ):
        """Test that issue creation is logged to audit log."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/444",
        )

        automation = GitHubIssueAutomation(project_root=temp_project)
        automation.create_issue(
            title="Audit test",
            body="Body",
        )

        # Verify audit log was called
        assert mock_audit.called
        call_args = mock_audit.call_args[1]
        assert call_args['action'] == 'github_issue_create'

    @patch('plugins.autonomous_dev.lib.security_utils.audit_log')
    @patch('subprocess.run')
    @patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
    def test_audit_log_records_failures(
        self, mock_check_gh, mock_run, mock_audit, temp_project
    ):
        """Test that failures are logged to audit log."""
        mock_check_gh.return_value = True
        mock_run.return_value = Mock(
            returncode=1,
            stderr="Error",
        )

        automation = GitHubIssueAutomation(project_root=temp_project)
        automation.create_issue(
            title="Failure test",
            body="Body",
        )

        # Verify audit log captured the failure
        assert mock_audit.called


# =============================================================================
# END OF TESTS
# =============================================================================
