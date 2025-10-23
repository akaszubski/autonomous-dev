"""
PR automation library for autonomous-dev plugin.

Provides functions to:
- Validate GitHub CLI prerequisites (installed, authenticated)
- Get current git branch
- Parse commit messages for issue references
- Create GitHub pull requests using gh CLI

Dependencies:
- gh CLI (GitHub CLI) - https://cli.github.com/
- git command-line tool

Author: autonomous-dev
Date: 2025-10-23
Workflow: 20251023_104242
"""

import json
import re
import subprocess
from typing import Dict, Any, List, Tuple, Optional


def validate_gh_prerequisites() -> Tuple[bool, str]:
    """
    Validate that GitHub CLI is installed and authenticated.

    Checks:
    1. gh CLI is installed (gh --version succeeds)
    2. gh CLI is authenticated (gh auth status succeeds)

    Returns:
        Tuple of (valid, error_message):
        - valid: True if all prerequisites met, False otherwise
        - error_message: Empty string if valid, error description if not

    Example:
        >>> valid, error = validate_gh_prerequisites()
        >>> if not valid:
        ...     print(f"Error: {error}")
    """
    try:
        # Check if gh CLI is installed
        subprocess.run(
            ['gh', '--version'],
            check=True,
            capture_output=True,
            text=True,
            timeout=5
        )
    except FileNotFoundError:
        return (False, 'GitHub CLI not installed. Install from https://cli.github.com/')
    except subprocess.CalledProcessError:
        return (False, 'GitHub CLI not installed or not working properly')
    except subprocess.TimeoutExpired:
        return (False, 'GitHub CLI command timed out')

    try:
        # Check if gh CLI is authenticated
        result = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True,
            text=True,
            timeout=5
        )
        # gh auth status returns non-zero exit code when not authenticated
        if result.returncode != 0:
            return (False, 'GitHub CLI not authenticated. Run: gh auth login')
    except subprocess.CalledProcessError as e:
        return (False, 'GitHub CLI not authenticated')
    except subprocess.TimeoutExpired:
        return (False, 'GitHub CLI authentication check timed out')

    return (True, '')


def get_current_branch() -> str:
    """
    Get the name of the current git branch.

    Uses 'git branch' command and parses output to find the current branch
    (marked with * prefix).

    Returns:
        String name of current branch (e.g., 'feature/pr-automation')

    Raises:
        subprocess.CalledProcessError: If not in a git repository or git command fails

    Example:
        >>> branch = get_current_branch()
        >>> print(f"Current branch: {branch}")
        Current branch: feature/pr-automation
    """
    result = subprocess.run(
        ['git', 'branch'],
        check=True,
        capture_output=True,
        text=True,
        timeout=5
    )

    # Parse git branch output to find current branch (marked with *)
    for line in result.stdout.split('\n'):
        if line.startswith('*'):
            # Extract branch name after '* '
            branch = line[2:].strip()

            # Handle detached HEAD state
            if branch.startswith('(HEAD detached'):
                return 'HEAD'

            return branch

    # Fallback if no branch found (shouldn't happen in valid git repo)
    raise RuntimeError('Could not determine current branch')


def parse_commit_messages_for_issues(base: str = 'main', head: Optional[str] = None) -> List[int]:
    """
    Parse commit messages for GitHub issue references.

    Searches for keywords: Closes, Close, Fixes, Fix, Resolves, Resolve
    Followed by issue numbers like #42, #123, etc.

    Args:
        base: Base branch to compare against (default: 'main')
        head: Head branch to compare (default: current branch)

    Returns:
        List of unique issue numbers found in commit messages, sorted ascending

    Example:
        >>> issues = parse_commit_messages_for_issues(base='main')
        >>> print(f"Found issues: {issues}")
        Found issues: [42, 123, 456]
    """
    # Get commit messages between base and head
    if head is None:
        head = 'HEAD'

    try:
        result = subprocess.run(
            ['git', 'log', f'{base}..{head}', '--pretty=format:%B'],
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # If git log fails (e.g., no commits) or times out, return empty list
        return []

    commit_text = result.stdout

    # Regex pattern to match issue references
    # Matches: Closes #42, fixes #123, RESOLVES #456, etc.
    # Case-insensitive, supports singular and plural forms
    pattern = r'\b(?:close|closes|fix|fixes|resolve|resolves)\s+#(\d+)\b'

    matches = re.finditer(pattern, commit_text, re.IGNORECASE)

    # Extract issue numbers and deduplicate
    issue_numbers = set()
    for match in matches:
        issue_numbers.add(int(match.group(1)))

    # Return sorted list
    return sorted(list(issue_numbers))


def create_pull_request(
    title: Optional[str] = None,
    body: Optional[str] = None,
    draft: bool = True,
    base: str = 'main',
    head: Optional[str] = None,
    reviewer: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a GitHub pull request using gh CLI.

    Args:
        title: Optional PR title (if None, uses --fill from commits)
        body: Optional PR body (if None, uses --fill-verbose from commits)
        draft: Create as draft PR (default True for autonomous workflow)
        base: Target branch (default 'main')
        head: Source branch (default current branch from git)
        reviewer: Optional GitHub handle(s) for reviewer assignment (comma-separated)

    Returns:
        Dictionary with:
        - success: Boolean indicating if PR was created
        - pr_number: Integer PR number (if success)
        - pr_url: String URL to created PR (if success)
        - draft: Boolean indicating if PR is draft
        - linked_issues: List of issue numbers auto-linked from commits
        - error: Optional error message if failed

    Raises:
        ValueError: If current branch is main/master (cannot create PR from default branch)
        ValueError: If no commits found to create PR

    Example:
        >>> result = create_pull_request(
        ...     title="Add PR automation",
        ...     reviewer="alice"
        ... )
        >>> if result['success']:
        ...     print(f"Created PR #{result['pr_number']}: {result['pr_url']}")
    """
    # Validate prerequisites
    valid, error_message = validate_gh_prerequisites()
    if not valid:
        return {
            'success': False,
            'error': error_message,
            'pr_number': None,
            'pr_url': None,
            'draft': draft,
            'linked_issues': []
        }

    # Get current branch if head not specified
    if head is None:
        try:
            head = get_current_branch()
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'error': f'Failed to get current branch: {e}',
                'pr_number': None,
                'pr_url': None,
                'draft': draft,
                'linked_issues': []
            }

    # Validate we're not on main/master branch
    if head in ['main', 'master']:
        raise ValueError(f'Cannot create PR from {head} branch. Switch to a feature branch first.')

    # Check if there are commits to create PR from
    try:
        result = subprocess.run(
            ['git', 'log', f'{base}..{head}', '--oneline'],
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        if not result.stdout.strip():
            raise ValueError(f'No commits found between {base} and {head}. Nothing to create PR for.')
    except subprocess.CalledProcessError:
        # If git log fails, we can't check commits, so proceed anyway
        # (may fail later during gh pr create)
        pass
    except subprocess.TimeoutExpired:
        # If git log times out, we can't check commits, so proceed anyway
        # (may fail later during gh pr create)
        pass

    # Parse commit messages for linked issues
    linked_issues = parse_commit_messages_for_issues(base=base, head=head)

    # Build gh pr create command
    cmd = ['gh', 'pr', 'create']

    # Add draft flag if requested
    if draft:
        cmd.append('--draft')

    # Add base branch
    cmd.extend(['--base', base])

    # Add title and body (or use auto-fill)
    if title is not None:
        cmd.extend(['--title', title])

    if body is not None:
        cmd.extend(['--body', body])

    # If no custom title/body, use auto-fill from commits
    if title is None and body is None:
        cmd.append('--fill-verbose')

    # Add reviewer if specified
    if reviewer is not None:
        cmd.extend(['--reviewer', reviewer])

    # Execute gh pr create command
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Parse PR URL from output (last line)
        pr_url = result.stdout.strip().split('\n')[-1].strip()

        # Extract PR number from URL
        # URL format: https://github.com/owner/repo/pull/42
        match = re.search(r'/pull/(\d+)', pr_url)
        if match:
            pr_number = int(match.group(1))
        else:
            pr_number = None

        return {
            'success': True,
            'pr_number': pr_number,
            'pr_url': pr_url,
            'draft': draft,
            'linked_issues': linked_issues,
            'error': None
        }

    except subprocess.CalledProcessError as e:
        # Parse error message from stderr attribute
        # CalledProcessError might have stderr as an attribute set by the test mock
        error_msg = ''
        if hasattr(e, 'stderr') and e.stderr:
            error_msg = str(e.stderr)
        else:
            error_msg = str(e)

        # Provide helpful error messages
        if 'rate limit' in error_msg.lower():
            error = 'GitHub API rate limit exceeded. Try again later.'
        elif 'permission' in error_msg.lower() or 'protected' in error_msg.lower() or 'saml' in error_msg.lower():
            error = f'Permission denied. Check repository permissions and SAML authorization: {error_msg}'
        else:
            error = f'Failed to create PR: {error_msg}'

        return {
            'success': False,
            'error': error,
            'pr_number': None,
            'pr_url': None,
            'draft': draft,
            'linked_issues': linked_issues
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'GitHub CLI command timeout after 30 seconds. Check network connection.',
            'pr_number': None,
            'pr_url': None,
            'draft': draft,
            'linked_issues': linked_issues
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error creating PR: {e}',
            'pr_number': None,
            'pr_url': None,
            'draft': draft,
            'linked_issues': linked_issues
        }
