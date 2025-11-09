#!/usr/bin/env python3
"""
CLI Script for GitHub Issue Creation

Provides command-line interface for automated GitHub issue creation.
Wraps github_issue_automation library with user-friendly output.

Usage:
    python create_issue.py --title "Bug report" --body "Description..."

Related to: GitHub Issue #58 - Automatic GitHub issue creation with research
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.github_issue_automation import (
    create_github_issue,
    IssueCreationResult,
)


# =============================================================================
# ARGUMENT PARSING
# =============================================================================


def parse_args(args=None):
    """Parse command-line arguments.

    Args:
        args: List of arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Create GitHub issue with automated research integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create basic issue
  %(prog)s --title "Bug: login fails" --body "Users cannot login on mobile"

  # Create issue with labels
  %(prog)s --title "Feature request" --body "Add dark mode" --labels "enhancement,ui"

  # Create issue with assignee
  %(prog)s --title "Bug fix needed" --body "Fix CORS issue" --assignee "username"

  # JSON output for scripting
  %(prog)s --title "Issue" --body "Description" --json
        """
    )

    # Required arguments
    parser.add_argument(
        '--title',
        required=True,
        help='Issue title (max 256 characters)',
    )

    parser.add_argument(
        '--body',
        required=True,
        help='Issue body (markdown supported, max 65536 characters)',
    )

    # Optional arguments
    parser.add_argument(
        '--labels',
        help='Comma-separated list of labels (e.g., "bug,priority:high")',
    )

    parser.add_argument(
        '--assignee',
        help='GitHub username to assign issue to',
    )

    parser.add_argument(
        '--project-root',
        type=Path,
        default=Path.cwd(),
        help='Project root directory (defaults to current directory)',
    )

    # Output options
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output result as JSON (for scripting)',
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output',
    )

    return parser.parse_args(args)


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================


def format_output_human(result: IssueCreationResult) -> str:
    """Format result as human-readable output.

    Args:
        result: Issue creation result

    Returns:
        Formatted string for display
    """
    if result.success:
        output = []
        output.append("✓ Issue created successfully!")
        output.append("")
        output.append(f"  Issue Number: #{result.issue_number}")
        output.append(f"  URL: {result.issue_url}")

        if result.details:
            if result.details.get('labels'):
                labels = ', '.join(result.details['labels'])
                output.append(f"  Labels: {labels}")

            if result.details.get('assignee'):
                output.append(f"  Assignee: {result.details['assignee']}")

        return '\n'.join(output)
    else:
        output = []
        output.append("✗ Issue creation failed")
        output.append("")
        output.append(f"  Error: {result.error}")

        if result.details and result.details.get('error_type'):
            output.append(f"  Error Type: {result.details['error_type']}")

        # Add helpful guidance
        output.append("")
        output.append("Troubleshooting:")

        if "not authenticated" in result.error.lower():
            output.append("  • Run 'gh auth login' to authenticate with GitHub")
        elif "not installed" in result.error.lower():
            output.append("  • Install gh CLI: https://cli.github.com/")
        elif "timed out" in result.error.lower():
            output.append("  • Check your internet connection")
            output.append("  • Try again in a few moments")
        elif "invalid characters" in result.error.lower():
            output.append("  • Remove special characters from title/labels")
            output.append("  • Avoid shell metacharacters: ; && || | ` $")
        elif "exceeds maximum length" in result.error.lower():
            output.append("  • Shorten the title or body")
            output.append("  • Title max: 256 characters")
            output.append("  • Body max: 65536 characters")

        return '\n'.join(output)


def format_output_json(result: IssueCreationResult) -> str:
    """Format result as JSON output.

    Args:
        result: Issue creation result

    Returns:
        JSON string
    """
    data = {
        'success': result.success,
        'issue_number': result.issue_number,
        'issue_url': result.issue_url,
        'error': result.error,
        'details': result.details or {},
    }

    return json.dumps(data, indent=2)


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def main(args=None) -> int:
    """Main entry point for CLI.

    Args:
        args: List of arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 = success, 1 = error)
    """
    # Parse arguments
    parsed_args = parse_args(args)

    # Parse labels if provided
    labels = None
    if parsed_args.labels:
        # Split by comma and strip whitespace
        labels = [label.strip() for label in parsed_args.labels.split(',')]
        # Filter out empty strings
        labels = [label for label in labels if label]

    # Verbose output
    if parsed_args.verbose and not parsed_args.json:
        print(f"Creating GitHub issue...")
        print(f"  Title: {parsed_args.title}")
        print(f"  Body: {parsed_args.body[:100]}...")
        if labels:
            print(f"  Labels: {', '.join(labels)}")
        if parsed_args.assignee:
            print(f"  Assignee: {parsed_args.assignee}")
        print()

    # Create issue
    result = create_github_issue(
        title=parsed_args.title,
        body=parsed_args.body,
        labels=labels,
        assignee=parsed_args.assignee,
        project_root=parsed_args.project_root,
    )

    # Format output
    if parsed_args.json:
        print(format_output_json(result))
    else:
        print(format_output_human(result))

    # Return exit code
    return 0 if result.success else 1


if __name__ == '__main__':
    sys.exit(main())
