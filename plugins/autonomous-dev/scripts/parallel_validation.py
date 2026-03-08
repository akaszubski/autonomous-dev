#!/usr/bin/env python3
"""
Parallel Validation Script - CLI wrapper for parallel_validation.py library

Executes parallel validation using agent_pool.py library integration.
Replaces prompt engineering with library-based execution.

Usage:
    python parallel_validation.py \
        --feature "Add authentication" \
        --project-root /path/to/project \
        --changed-files src/auth.py tests/test_auth.py \
        --priority-mode

Output (JSON):
    {
        "security_passed": true,
        "review_passed": true,
        "docs_updated": true,
        "failed_agents": [],
        "execution_time_seconds": 8.5
    }

Date: 2026-01-02
Issue: GitHub #187 (Migrate /auto-implement to agent_pool.py)
Agent: implementer
"""

import argparse
import json
import sys
from pathlib import Path

# Add lib to path for imports
script_dir = Path(__file__).parent.resolve()
lib_dir = script_dir.parent / "lib"
sys.path.insert(0, str(lib_dir))

try:
    from parallel_validation import (
        execute_parallel_validation,
        ValidationResults,
        SecurityValidationError,
        ValidationTimeoutError
    )
except ImportError as e:
    print(f"Error: Failed to import parallel_validation library: {e}", file=sys.stderr)
    print("Ensure plugins/autonomous-dev/lib/parallel_validation.py exists", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Execute parallel validation using agent pool"
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="Feature description"
    )
    parser.add_argument(
        "--project-root",
        required=True,
        help="Project root directory"
    )
    parser.add_argument(
        "--priority-mode",
        action="store_true",
        help="Run security first (blocks on failure)"
    )
    parser.add_argument(
        "--changed-files",
        nargs="+",
        help="List of changed files"
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for transient errors (default: 3)"
    )

    args = parser.parse_args()

    # Validate project root
    project_root = Path(args.project_root)
    if not project_root.exists():
        print(f"Error: Project root does not exist: {project_root}", file=sys.stderr)
        sys.exit(1)

    try:
        # Execute validation
        results = execute_parallel_validation(
            feature_description=args.feature,
            project_root=project_root,
            priority_mode=args.priority_mode,
            changed_files=args.changed_files,
            max_retries=args.max_retries
        )

        # Output results
        if args.output_format == "json":
            print(json.dumps({
                "security_passed": results.security_passed,
                "review_passed": results.review_passed,
                "docs_updated": results.docs_updated,
                "failed_agents": results.failed_agents,
                "execution_time_seconds": results.execution_time_seconds,
                "security_output": results.security_output,
                "review_output": results.review_output,
                "docs_output": results.docs_output
            }, indent=2))
        else:
            # Text format
            print("=" * 70)
            print("PARALLEL VALIDATION RESULTS")
            print("=" * 70)
            print(f"Feature: {args.feature}")
            print(f"Execution time: {results.execution_time_seconds:.2f}s")
            print()
            print(f"Security: {'PASS' if results.security_passed else 'FAIL'}")
            if results.security_output:
                print(f"  {results.security_output[:100]}...")
            print()
            print(f"Review: {'PASS' if results.review_passed else 'FAIL'}")
            if results.review_output:
                print(f"  {results.review_output[:100]}...")
            print()
            print(f"Docs: {'UPDATED' if results.docs_updated else 'NOT UPDATED'}")
            if results.docs_output:
                print(f"  {results.docs_output[:100]}...")
            print()
            if results.failed_agents:
                print(f"Failed agents: {', '.join(results.failed_agents)}")
            else:
                print("All agents succeeded!")
            print("=" * 70)

        # Exit code based on results
        if not results.security_passed:
            sys.exit(1)  # Security failure is critical
        elif not results.review_passed:
            sys.exit(2)  # Review failure (non-critical)
        else:
            sys.exit(0)  # Success

    except SecurityValidationError as e:
        print(f"SECURITY VALIDATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    except ValidationTimeoutError as e:
        print(f"VALIDATION TIMEOUT: {e}", file=sys.stderr)
        sys.exit(3)

    except ValueError as e:
        print(f"INVALID INPUT: {e}", file=sys.stderr)
        sys.exit(4)

    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    main()
