#!/usr/bin/env python3
"""GitHub issue creation example from github_issue_automation.py.

See: plugins/autonomous-dev/lib/github_issue_automation.py
"""

import subprocess
from typing import List, Optional


def create_github_issue_safe(
    title: str,
    body: str,
    *,
    labels: Optional[List[str]] = None
) -> str:
    """Create GitHub issue using gh CLI (safe subprocess pattern).

    Args:
        title: Issue title
        body: Issue body (markdown)
        labels: Issue labels (default: None)

    Returns:
        Issue URL

    Security:
        - CWE-78 Prevention: Argument array (no shell injection)
        - Timeout: 30 second limit
        - No shell=True: Safe from command injection
    """
    # Build command as argument array (safe)
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]

    # Add labels if provided
    if labels:
        for label in labels:
            cmd.extend(["--label", label])

    # Execute safely
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        shell=False  # CRITICAL for security
    )

    return result.stdout.strip()


# Example usage
if __name__ == "__main__":
    # Example 1: Simple issue
    url = create_github_issue_safe(
        "Bug: Login button not working",
        "Steps to reproduce:\n1. Go to login page\n2. Click login\n3. Nothing happens"
    )
    print(f"Created: {url}")

    # Example 2: Issue with labels
    url = create_github_issue_safe(
        "Feature: Add dark mode",
        "Users want dark mode support",
        labels=["enhancement", "ui"]
    )
    print(f"Created: {url}")
