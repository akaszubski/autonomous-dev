#!/usr/bin/env python3
"""GitHub PR creation example from auto_implement_git_integration.py.

See: plugins/autonomous-dev/lib/auto_implement_git_integration.py
"""

import subprocess
from typing import Optional


def create_github_pr_safe(
    title: str,
    body: str,
    *,
    base: str = "main",
    draft: bool = False
) -> str:
    """Create GitHub PR using gh CLI (safe subprocess pattern).

    Args:
        title: PR title
        body: PR description (markdown)
        base: Base branch (default: "main")
        draft: Whether to create as draft PR (default: False)

    Returns:
        PR URL

    Security:
        - CWE-78 Prevention: Argument array
        - No shell=True: Safe from command injection
    """
    # Build command as argument array
    cmd = [
        "gh", "pr", "create",
        "--title", title,
        "--body", body,
        "--base", base
    ]

    if draft:
        cmd.append("--draft")

    # Execute safely
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        shell=False
    )

    return result.stdout.strip()


# Example usage
if __name__ == "__main__":
    # Example: Create PR
    pr_body = """## Summary
- Added user authentication
- Fixed login bug
- Updated tests

## Test Plan
- [x] Unit tests pass
- [x] Integration tests pass
- [x] Manual testing complete

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""

    url = create_github_pr_safe(
        "feat: Add user authentication",
        pr_body,
        base="main",
        draft=False
    )
    print(f"Created PR: {url}")
