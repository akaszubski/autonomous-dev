#!/usr/bin/env python3
"""CLI wrapper for complexity_assessor.py library.

This script provides a command-line interface to the complexity assessment
library for testing and manual invocation.

Usage:
    python complexity_assessor.py "Fix typo in README"
    python complexity_assessor.py --issue 123
    echo "Add OAuth2 support" | python complexity_assessor.py --stdin

Security:
    - Input validation for all arguments
    - No shell command execution
    - No file system writes
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Add lib to path for imports
current = Path(__file__).resolve()
project_root = current.parent.parent.parent.parent

# Try autonomous_dev symlink first, fall back to autonomous-dev
lib_path = project_root / "plugins" / "autonomous_dev" / "lib"
if not lib_path.exists():
    lib_path = project_root / "plugins" / "autonomous-dev" / "lib"

if lib_path.exists():
    sys.path.insert(0, str(lib_path.parent))

try:
    from autonomous_dev.lib.complexity_assessor import (
        ComplexityAssessor,
        ComplexityLevel,
        ComplexityAssessment
    )
except ImportError as e:
    print(f"Error: Cannot import complexity_assessor: {e}", file=sys.stderr)
    print("Make sure the library is installed and paths are correct", file=sys.stderr)
    sys.exit(1)


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Assess complexity of feature requests for pipeline scaling"
    )

    # Input methods (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "description",
        nargs="?",
        help="Feature description to assess"
    )
    input_group.add_argument(
        "--stdin",
        action="store_true",
        help="Read feature description from stdin"
    )
    input_group.add_argument(
        "--issue",
        type=int,
        help="GitHub issue number to analyze (requires gh CLI)"
    )

    # Output format
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include detailed reasoning in output"
    )

    args = parser.parse_args()

    # Get feature description from appropriate source
    feature_description = None
    github_issue = None

    if args.stdin:
        feature_description = sys.stdin.read().strip()
    elif args.issue:
        feature_description, github_issue = fetch_github_issue(args.issue)
        if not feature_description:
            print(f"Error: Could not fetch issue #{args.issue}", file=sys.stderr)
            sys.exit(1)
    else:
        feature_description = args.description

    # Validate input
    if not feature_description:
        print("Error: No feature description provided", file=sys.stderr)
        sys.exit(1)

    # Perform assessment
    assessor = ComplexityAssessor()
    result = assessor.assess(feature_description, github_issue=github_issue)

    # Output results
    if args.json:
        output_json(result)
    else:
        output_text(result, verbose=args.verbose)


def fetch_github_issue(issue_number: int) -> tuple[Optional[str], Optional[dict]]:
    """Fetch GitHub issue via gh CLI.

    Args:
        issue_number: Issue number to fetch

    Returns:
        Tuple of (feature_description, github_issue_dict) or (None, None) on error
    """
    import subprocess

    try:
        # Fetch issue as JSON
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
            capture_output=True,
            text=True,
            check=True
        )

        issue_data = json.loads(result.stdout)
        title = issue_data.get("title", "")
        body = issue_data.get("body", "")

        github_issue = {
            "title": title,
            "body": body
        }

        return title, github_issue

    except subprocess.CalledProcessError as e:
        print(f"Error running gh CLI: {e}", file=sys.stderr)
        return None, None
    except json.JSONDecodeError as e:
        print(f"Error parsing gh CLI output: {e}", file=sys.stderr)
        return None, None
    except FileNotFoundError:
        print("Error: gh CLI not found. Install from https://cli.github.com/", file=sys.stderr)
        return None, None


def output_json(result: ComplexityAssessment):
    """Output assessment as JSON.

    Args:
        result: ComplexityAssessment to output
    """
    output = {
        "level": result.level.value,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "agent_count": result.agent_count,
        "estimated_time": result.estimated_time
    }

    print(json.dumps(output, indent=2))


def output_text(result: ComplexityAssessment, verbose: bool = False):
    """Output assessment as human-readable text.

    Args:
        result: ComplexityAssessment to output
        verbose: Include detailed reasoning
    """
    print(f"Complexity Level: {result.level.value.upper()}")
    print(f"Agent Count: {result.agent_count}")
    print(f"Estimated Time: {result.estimated_time} minutes")
    print(f"Confidence: {result.confidence:.1%}")

    if verbose:
        print(f"\nReasoning: {result.reasoning}")


if __name__ == "__main__":
    main()
