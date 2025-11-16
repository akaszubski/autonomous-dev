#!/usr/bin/env python3
"""GitHub API integration template.

See: skills/api-integration-patterns/docs/github-cli-integration.md
"""

import subprocess
import json
import os
from typing import List, Optional, Dict, Any


class GitHubAPIError(Exception):
    """Raised when GitHub API call fails."""
    pass


def get_github_token() -> str:
    """Get GitHub token from environment.

    Returns:
        GitHub personal access token

    Raises:
        RuntimeError: If token not found

    Security:
        - Environment Variables: Never hardcode tokens
        - No Logging: Never log credentials
    """
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN not found in environment\n"
            "Set with: export GITHUB_TOKEN=your_token\n"
            "Or add to .env file"
        )

    return token


def create_issue(
    title: str,
    body: str,
    *,
    labels: Optional[List[str]] = None,
    timeout: int = 30
) -> str:
    """Create GitHub issue using gh CLI.

    Args:
        title: Issue title
        body: Issue body (markdown)
        labels: Issue labels (default: None)
        timeout: Command timeout in seconds (default: 30)

    Returns:
        Issue URL

    Raises:
        GitHubAPIError: If issue creation fails

    Example:
        >>> url = create_issue(
        ...     "Bug: Login fails",
        ...     "Login button doesn't work",
        ...     labels=["bug", "p1"]
        ... )
        >>> print(url)
        'https://github.com/owner/repo/issues/123'
    """
    # Build gh command (argument array)
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]

    if labels:
        for label in labels:
            cmd.extend(["--label", label])

    # Execute safely
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
            shell=False  # CRITICAL
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        raise GitHubAPIError(f"Failed to create issue: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise GitHubAPIError(f"Issue creation timed out after {timeout}s")


def list_issues(
    *,
    state: str = "open",
    limit: int = 30,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """List GitHub issues.

    Args:
        state: Issue state ("open", "closed", "all")
        limit: Maximum number of issues
        timeout: Command timeout in seconds

    Returns:
        List of issue dictionaries

    Example:
        >>> issues = list_issues(state="open", limit=10)
        >>> for issue in issues:
        ...     print(f"#{issue['number']}: {issue['title']}")
    """
    cmd = [
        "gh", "issue", "list",
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,state,url"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
            shell=False
        )
        return json.loads(result.stdout)

    except subprocess.CalledProcessError as e:
        raise GitHubAPIError(f"Failed to list issues: {e.stderr}")


# Example usage
if __name__ == "__main__":
    # Create issue
    try:
        url = create_issue(
            "Example Issue",
            "This is a test issue created via gh CLI",
            labels=["example"]
        )
        print(f"Created: {url}")
    except GitHubAPIError as e:
        print(f"Error: {e}")

    # List issues
    try:
        issues = list_issues(limit=5)
        for issue in issues:
            print(f"#{issue['number']}: {issue['title']}")
    except GitHubAPIError as e:
        print(f"Error: {e}")
