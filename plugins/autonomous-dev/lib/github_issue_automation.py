"""
GitHub Issue Automation Library

Provides automated GitHub issue creation with research integration.
Uses gh CLI for GitHub operations with security validation.

Security:
- CWE-78: Command injection prevention (subprocess list args, input validation)
- CWE-117: Log injection prevention (control character sanitization)
- CWE-20: Input validation (length limits, format validation)

Related to: GitHub Issue #58 - Automatic GitHub issue creation with research

See error-handling-patterns skill for exception hierarchy and error handling best practices.


Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See api-integration-patterns skill for standardized design patterns.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

# Import security utilities
from .security_utils import audit_log, validate_input_length, validate_path


# =============================================================================
# EXCEPTIONS
# =============================================================================


# Exception hierarchy pattern from error-handling-patterns skill:
# BaseException -> Exception -> AutonomousDevError -> DomainError(BaseException) -> SpecificError
class IssueCreationError(Exception):
    """Base exception for issue creation errors."""
    pass


class GhCliError(IssueCreationError):
    """Exception raised when gh CLI operations fail."""
    pass


class ValidationError(IssueCreationError):
    """Exception raised when input validation fails."""
    pass


# =============================================================================
# RESULT DATACLASS
# =============================================================================


@dataclass
class IssueCreationResult:
    """Result of GitHub issue creation operation.

    Attributes:
        success: Whether issue creation succeeded
        issue_number: GitHub issue number (None if failed)
        issue_url: URL to created issue (None if failed)
        error: Error message if failed (None if succeeded)
        details: Additional details (labels, assignee, etc.)
    """
    success: bool
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary.

        Returns:
            Dictionary representation of result
        """
        return {
            'success': self.success,
            'issue_number': self.issue_number,
            'issue_url': self.issue_url,
            'error': self.error,
            'details': self.details or {},
        }


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def validate_issue_title(title: str) -> bool:
    """Validate issue title for security and correctness.

    Security validations:
    - CWE-78: Reject shell metacharacters
    - CWE-117: Reject control characters
    - CWE-20: Enforce length limits

    Args:
        title: Issue title to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If title is invalid
    """
    # Check for empty or whitespace-only
    if not title or not title.strip():
        raise ValidationError("Title cannot be empty")

    # Check length (GitHub limit is 256 characters)
    max_length = 256
    if len(title) > max_length:
        raise ValidationError(
            f"Title exceeds maximum length of {max_length} characters "
            f"(got {len(title)} characters)"
        )

    # Check for shell metacharacters (CWE-78)
    # Only reject truly dangerous metacharacters, allow common punctuation
    shell_metacharacters = [';', '|', '`', '$']
    for char in shell_metacharacters:
        if char in title:
            raise ValidationError(
                f"Title contains invalid characters (shell metacharacters not allowed): {char}"
            )

    # Check for compound operators separately (need to check as strings)
    if '&&' in title or '||' in title:
        raise ValidationError(
            "Title contains invalid characters (shell metacharacters not allowed)"
        )

    # Check for control characters (CWE-117)
    # Control characters are \x00-\x1f and \x7f
    if any(ord(c) < 32 or ord(c) == 127 for c in title):
        raise ValidationError(
            "Title contains invalid characters (control characters not allowed)"
        )

    # Check for newlines specifically
    if '\n' in title or '\r' in title:
        raise ValidationError(
            "Title contains invalid characters (newlines not allowed)"
        )

    return True


def validate_issue_body(body: str) -> bool:
    """Validate issue body for security and correctness.

    Security validations:
    - CWE-20: Enforce length limits

    Args:
        body: Issue body to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If body is invalid
    """
    # Check for empty or whitespace-only
    if not body or not body.strip():
        raise ValidationError("Body cannot be empty")

    # Check length (GitHub limit is 65536 characters)
    max_length = 65536
    if len(body) > max_length:
        raise ValidationError(
            f"Body exceeds maximum length of {max_length} characters "
            f"(got {len(body)} characters)"
        )

    return True


def validate_labels(labels: Optional[List[str]]) -> bool:
    """Validate issue labels.

    Args:
        labels: List of label names

    Returns:
        True if valid

    Raises:
        ValidationError: If labels are invalid
    """
    if labels is None:
        return True

    if not isinstance(labels, list):
        raise ValidationError("Labels must be a list")

    # Validate each label
    for label in labels:
        if not isinstance(label, str):
            raise ValidationError(f"Label must be a string, got {type(label)}")

        if not label or not label.strip():
            raise ValidationError("Label cannot be empty")

        # GitHub label length limit is 50 characters
        if len(label) > 50:
            raise ValidationError(
                f"Label '{label}' exceeds maximum length of 50 characters"
            )

        # Check for shell metacharacters
        if any(c in label for c in [';', '&&', '||', '|', '`', '$']):
            raise ValidationError(
                f"Label '{label}' contains invalid characters"
            )

    return True


def validate_assignee(assignee: Optional[str]) -> bool:
    """Validate issue assignee.

    Args:
        assignee: GitHub username

    Returns:
        True if valid

    Raises:
        ValidationError: If assignee is invalid
    """
    if assignee is None:
        return True

    if not isinstance(assignee, str):
        raise ValidationError("Assignee must be a string")

    if not assignee or not assignee.strip():
        raise ValidationError("Assignee cannot be empty")

    # GitHub username constraints: alphanumeric + hyphens, max 39 chars
    if len(assignee) > 39:
        raise ValidationError(
            f"Assignee '{assignee}' exceeds maximum length of 39 characters"
        )

    # Username must be alphanumeric + hyphens only
    if not re.match(r'^[a-zA-Z0-9-]+$', assignee):
        raise ValidationError(
            f"Assignee '{assignee}' contains invalid characters "
            "(only alphanumeric and hyphens allowed)"
        )

    return True


# =============================================================================
# GH CLI FUNCTIONS
# =============================================================================


def check_gh_available() -> bool:
    """Check if gh CLI is available and authenticated.

    Returns:
        True if gh CLI is available and authenticated

    Raises:
        FileNotFoundError: If gh CLI is not installed
        RuntimeError: If gh CLI is not authenticated or network error
    """
    # Check if gh is installed
    try:
        result = subprocess.run(
            ['gh', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise FileNotFoundError("GitHub CLI (gh) is not installed or not in PATH")
    except FileNotFoundError:
        raise FileNotFoundError("GitHub CLI (gh) is not installed or not in PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitHub CLI check network error: timed out")

    # Check if authenticated
    try:
        result = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "GitHub CLI is not authenticated. Run 'gh auth login' to authenticate."
            )
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitHub CLI auth check network error: timed out")

    return True


def build_gh_command(
    title: str,
    body: str,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    milestone: Optional[str] = None,
) -> List[str]:
    """Build gh CLI command for issue creation.

    Security: Uses list arguments (not shell=True) to prevent CWE-78.

    Args:
        title: Issue title
        body: Issue body
        labels: Optional list of labels
        assignee: Optional assignee username
        milestone: Optional milestone name

    Returns:
        Command as list of arguments
    """
    cmd = ['gh', 'issue', 'create', '--title', title, '--body', body]

    if labels:
        # Add each label separately
        for label in labels:
            cmd.extend(['--label', label])

    if assignee:
        cmd.extend(['--assignee', assignee])

    if milestone:
        cmd.extend(['--milestone', milestone])

    return cmd


def parse_issue_number(gh_output: str) -> int:
    """Parse issue number from gh CLI output.

    The gh CLI returns issue URL like:
    https://github.com/owner/repo/issues/123

    Args:
        gh_output: Output from gh issue create command

    Returns:
        Issue number (integer)

    Raises:
        ValueError: If no issue number found or PR URL instead of issue URL
    """
    # Check for PR URLs (should be rejected)
    if '/pull/' in gh_output:
        raise ValueError(
            "Expected issue URL but found PR URL. "
            "Use 'gh issue create' not 'gh pr create'."
        )

    # Extract issue number from output
    # URL format: https://github.com/owner/repo/issues/123
    # May have surrounding text
    match = re.search(r'/issues/(\d+)', gh_output)
    if match:
        return int(match.group(1))

    # No issue number found
    raise ValueError(
        "Could not parse issue number from gh CLI output. "
        f"Expected GitHub issue URL format: .../issues/NUMBER"
    )


def execute_gh_command(
    cmd: List[str],
    project_root: Path,
) -> str:
    """Execute gh CLI command and return output.

    Args:
        cmd: Command as list of arguments
        project_root: Project root directory

    Returns:
        Command output (stdout)

    Raises:
        GhCliError: If command fails
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            raise GhCliError(f"gh issue create failed: {error_msg}")

        return result.stdout

    except subprocess.TimeoutExpired:
        raise GhCliError("gh issue create command timed out after 30 seconds")
    except FileNotFoundError:
        raise GhCliError("gh CLI is not installed or not in PATH")


# =============================================================================
# MAIN CLASS
# =============================================================================


class GitHubIssueAutomation:
    """Main class for automated GitHub issue creation.

    Provides:
    - Input validation
    - gh CLI integration
    - Security audit logging
    - Error handling

    Example:
        automation = GitHubIssueAutomation(project_root=Path.cwd())
        result = automation.create_issue(
            title="Bug: login fails",
            body="Description of bug...",
            labels=["bug", "priority:high"],
            assignee="username",
        )
    """

    def __init__(self, project_root: Path):
        """Initialize GitHub issue automation.

        Args:
            project_root: Root directory of project

        Raises:
            ValueError: If project_root fails security validation
        """
        # Validate project_root for security (CWE-22, CWE-59)
        validated_path = validate_path(project_root, "project_root")
        self.project_root = validated_path

    def _build_gh_command(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        milestone: Optional[str] = None,
    ) -> List[str]:
        """Build gh CLI command for issue creation.

        Security: Uses list arguments (not shell=True) to prevent CWE-78.

        Args:
            title: Issue title
            body: Issue body
            labels: Optional list of labels
            assignee: Optional assignee username
            milestone: Optional milestone name

        Returns:
            Command as list of arguments
        """
        return build_gh_command(title, body, labels, assignee, milestone)

    def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        milestone: Optional[str] = None,
    ) -> IssueCreationResult:
        """Create GitHub issue with validation and audit logging.

        Args:
            title: Issue title
            body: Issue body (markdown supported)
            labels: Optional list of labels
            assignee: Optional assignee username
            milestone: Optional milestone name

        Returns:
            IssueCreationResult with success status and details
        """
        # Audit log the attempt
        audit_log(
            event_type="github_issue_create_attempt",
            status="started",
            context={
                "title": title[:100],  # Truncate for logging
                "has_labels": labels is not None,
                "has_assignee": assignee is not None,
            }
        )

        try:
            # Validate inputs
            validate_issue_title(title)
            validate_issue_body(body)
            validate_labels(labels)
            validate_assignee(assignee)

            # Check gh CLI availability
            check_gh_available()

            # Build command
            cmd = build_gh_command(title, body, labels, assignee, milestone)

            # Execute command
            output = execute_gh_command(cmd, self.project_root)

            # Parse issue number from output
            issue_number = parse_issue_number(output)

            # Extract issue URL from output
            issue_url = None
            for line in output.strip().split('\n'):
                line = line.strip()
                if line.startswith('http') and '/issues/' in line:
                    issue_url = line
                    break

            # Build result
            result = IssueCreationResult(
                success=True,
                issue_number=issue_number,
                issue_url=issue_url,
                details={
                    "labels": labels or [],
                    "assignee": assignee,
                }
            )

            # Audit log success
            audit_log(
                event_type="github_issue_create_success",
                status="success",
                context={
                    "issue_number": issue_number,
                    "issue_url": issue_url,
                }
            )

            return result

        except (ValidationError, GhCliError, IssueCreationError) as e:
            # Audit log failure
            audit_log(
                event_type="github_issue_create_failure",
                status="error",
                context={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )

            return IssueCreationResult(
                success=False,
                error=str(e),
                details={
                    "error_type": type(e).__name__,
                }
            )

        except Exception as e:
            # Unexpected error
            audit_log(
                event_type="github_issue_create_failure",
                status="error",
                context={
                    "error": str(e),
                    "error_type": "unexpected",
                }
            )

            return IssueCreationResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                details={
                    "error_type": "unexpected",
                }
            )


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================


def create_github_issue(
    title: str,
    body: str,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    milestone: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> IssueCreationResult:
    """Convenience function for creating GitHub issues.

    Args:
        title: Issue title
        body: Issue body (markdown supported)
        labels: Optional list of labels
        assignee: Optional assignee username
        milestone: Optional milestone name
        project_root: Project root directory (defaults to current directory)

    Returns:
        IssueCreationResult with success status and details

    Example:
        result = create_github_issue(
            title="Bug: login fails",
            body="Description...",
            labels=["bug"],
            project_root=Path("/path/to/project"),
        )

        if result.success:
            print(f"Created issue #{result.issue_number}")
        else:
            print(f"Failed: {result.error}")
    """
    if project_root is None:
        project_root = Path.cwd()

    automation = GitHubIssueAutomation(project_root=project_root)
    return automation.create_issue(
        title=title,
        body=body,
        labels=labels,
        assignee=assignee,
        milestone=milestone,
    )
