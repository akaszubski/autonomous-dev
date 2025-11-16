#!/usr/bin/env python3
"""
TDD Red Phase Verification Script for Issue #58

Verifies that all tests for GitHub issue automation are written and FAIL.
Tests should fail because implementation doesn't exist yet.

Related to: GitHub Issue #58 - Automatic GitHub issue creation with research

Usage:
    python tests/verify_issue58_tdd_red.py
"""

import subprocess
import sys
from pathlib import Path


def run_test_file(test_file: Path) -> dict:
    """Run a single test file and return results."""
    print(f"\n{'='*80}")
    print(f"Running: {test_file.name}")
    print('='*80)

    result = subprocess.run(
        [sys.executable, '-m', 'pytest', str(test_file), '-v', '--tb=short'],
        capture_output=True,
        text=True,
    )

    return {
        'file': test_file.name,
        'returncode': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
    }


def main():
    """Run all Issue #58 tests and verify they fail."""
    project_root = Path(__file__).parent.parent

    test_files = [
        # Unit tests for library
        project_root / "tests" / "unit" / "lib" / "test_github_issue_automation.py",

        # Unit tests for CLI
        project_root / "tests" / "unit" / "test_create_issue_cli.py",

        # Integration tests
        project_root / "tests" / "integration" / "test_create_issue_workflow.py",

        # Agent tests
        project_root / "tests" / "unit" / "agents" / "test_issue_creator.py",
    ]

    print("="*80)
    print("TDD RED PHASE VERIFICATION - Issue #58")
    print("GitHub Issue Automation with Research")
    print("="*80)
    print("\nVerifying tests are written and FAIL (no implementation exists yet)\n")

    results = []
    for test_file in test_files:
        if not test_file.exists():
            print(f"\n❌ ERROR: Test file not found: {test_file}")
            return 1

        result = run_test_file(test_file)
        results.append(result)

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    all_failed = True
    for result in results:
        status = "✅ FAIL (Expected)" if result['returncode'] != 0 else "❌ PASS (Unexpected)"

        if result['returncode'] == 0:
            all_failed = False

        print(f"{status}: {result['file']}")

        # Show test counts
        if 'passed' in result['stdout']:
            # Extract test counts from pytest output
            lines = result['stdout'].split('\n')
            for line in lines:
                if 'passed' in line or 'failed' in line or 'error' in line:
                    print(f"    {line.strip()}")

    print("\n" + "="*80)

    if all_failed:
        print("✅ TDD RED PHASE COMPLETE")
        print("\nAll tests are written and FAIL as expected.")
        print("This is correct - implementation doesn't exist yet!")
        print("\nNext steps:")
        print("  1. Implement github_issue_automation.py library")
        print("  2. Implement create_issue.py CLI script")
        print("  3. Create issue-creator.md agent")
        print("  4. Create create-issue.md command")
        print("  5. Run tests again - they should PASS")
        return 0
    else:
        print("❌ TDD RED PHASE INCOMPLETE")
        print("\nSome tests are passing unexpectedly!")
        print("Tests should FAIL until implementation is complete.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
