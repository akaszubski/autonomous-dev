#!/usr/bin/env python3
"""
Verification Script for Token Reduction TDD Red Phase (Issues #67-70)

This script verifies that all TDD tests for token reduction are in RED phase
(failing as expected before implementation).

Test Files:
1. tests/unit/skills/test_git_github_workflow_enhancement.py (Issue #67)
2. tests/unit/skills/test_skill_integration_skill.py (Issue #68)
3. tests/unit/skills/test_project_alignment_skill.py (Issue #69)
4. tests/unit/skills/test_error_handling_enhancement.py (Issue #70)
5. tests/integration/test_token_reduction_workflow.py (Integration)

Expected Behavior:
- All tests should FAIL (red phase)
- No implementation exists yet
- Tests validate requirements for Issues #67-70

Usage:
    python tests/verify_token_reduction_tdd_red.py

Exit Codes:
    0 = All tests failing as expected (RED phase successful)
    1 = Some tests passing unexpectedly (implementation exists - not RED)
    2 = Test execution error

Author: test-master agent
Date: 2025-11-12
Issues: #67-70
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict


# Test files to verify
TEST_FILES = [
    "tests/unit/skills/test_git_github_workflow_enhancement.py",
    "tests/unit/skills/test_skill_integration_skill.py",
    "tests/unit/skills/test_project_alignment_skill.py",
    "tests/unit/skills/test_error_handling_enhancement.py",
    "tests/integration/test_token_reduction_workflow.py"
]

# Expected results for each issue
EXPECTED_TESTS = {
    "#67": {
        "file": "test_git_github_workflow_enhancement.py",
        "min_tests": 30,
        "description": "git/github-workflow skill enhancement"
    },
    "#68": {
        "file": "test_skill_integration_skill.py",
        "min_tests": 35,
        "description": "skill-integration skill creation"
    },
    "#69": {
        "file": "test_project_alignment_skill.py",
        "min_tests": 30,
        "description": "project-alignment skill creation"
    },
    "#70": {
        "file": "test_error_handling_enhancement.py",
        "min_tests": 35,
        "description": "error-handling-patterns enhancement"
    },
    "integration": {
        "file": "test_token_reduction_workflow.py",
        "min_tests": 20,
        "description": "Integration tests for token reduction workflow"
    }
}


def print_header(text: str) -> None:
    """Print section header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_status(status: str, message: str) -> None:
    """Print status message with emoji."""
    icons = {
        "PASS": "✓",
        "FAIL": "✗",
        "WARN": "⚠",
        "INFO": "ℹ"
    }
    icon = icons.get(status, "•")
    print(f"  {icon} {message}")


def verify_test_file_exists(test_file: str) -> bool:
    """Verify test file exists."""
    file_path = Path(test_file)
    if not file_path.exists():
        print_status("FAIL", f"Test file not found: {test_file}")
        return False
    print_status("PASS", f"Test file exists: {test_file}")
    return True


def count_tests_in_file(test_file: str) -> int:
    """Count test functions in file."""
    file_path = Path(test_file)
    content = file_path.read_text()

    # Count test functions (def test_)
    test_count = content.count("def test_")

    print_status("INFO", f"Found {test_count} test functions in {Path(test_file).name}")
    return test_count


def run_tests(test_file: str) -> Tuple[bool, int, int]:
    """
    Run tests and check if they fail as expected.

    Returns:
        Tuple of (all_failed, passed_count, failed_count)
    """
    print_status("INFO", f"Running tests in {Path(test_file).name}...")

    try:
        # Run pytest with minimal output
        result = subprocess.run(
            ["pytest", test_file, "-v", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Parse output for passed/failed counts
        output = result.stdout + result.stderr

        # Count passed and failed
        passed_count = output.count(" PASSED")
        failed_count = output.count(" FAILED")

        # In RED phase, we expect ALL tests to fail
        all_failed = (passed_count == 0 and failed_count > 0)

        if all_failed:
            print_status("PASS", f"All tests failing as expected (RED phase): {failed_count} failed")
        elif passed_count > 0:
            print_status("FAIL", f"Some tests passing unexpectedly: {passed_count} passed, {failed_count} failed")
            print_status("WARN", "This suggests implementation already exists (not RED phase)")
        else:
            print_status("WARN", f"No tests executed: {passed_count} passed, {failed_count} failed")

        return all_failed, passed_count, failed_count

    except subprocess.TimeoutExpired:
        print_status("FAIL", "Test execution timed out (>60s)")
        return False, 0, 0
    except Exception as e:
        print_status("FAIL", f"Test execution error: {e}")
        return False, 0, 0


def verify_test_coverage(test_file: str, expected_info: Dict) -> bool:
    """Verify test file has expected coverage."""
    test_count = count_tests_in_file(test_file)
    min_tests = expected_info["min_tests"]

    if test_count >= min_tests:
        print_status("PASS", f"Adequate test coverage: {test_count} >= {min_tests} tests")
        return True
    else:
        print_status("FAIL", f"Insufficient test coverage: {test_count} < {min_tests} tests")
        return False


def main() -> int:
    """Main verification function."""
    print_header("Token Reduction TDD Red Phase Verification (Issues #67-70)")

    print("\nVerifying TDD tests are in RED phase (failing before implementation)...")
    print("Expected: All tests should FAIL (no implementation exists yet)")

    all_red = True
    total_passed = 0
    total_failed = 0

    # Verify each test file
    for issue, expected_info in EXPECTED_TESTS.items():
        print_header(f"Issue {issue}: {expected_info['description']}")

        # Find matching test file
        test_file = None
        for tf in TEST_FILES:
            if expected_info["file"] in tf:
                test_file = tf
                break

        if not test_file:
            print_status("FAIL", f"Test file not found for issue {issue}")
            all_red = False
            continue

        # Verify file exists
        if not verify_test_file_exists(test_file):
            all_red = False
            continue

        # Verify test coverage
        if not verify_test_coverage(test_file, expected_info):
            all_red = False
            continue

        # Run tests and verify they fail
        is_red, passed, failed = run_tests(test_file)
        total_passed += passed
        total_failed += failed

        if not is_red:
            all_red = False

    # Print summary
    print_header("Summary")

    print(f"\nTotal tests: {total_passed + total_failed}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")

    if all_red and total_failed > 0 and total_passed == 0:
        print_status("PASS", "TDD RED PHASE SUCCESSFUL")
        print("\n✓ All tests failing as expected")
        print("✓ No implementation exists yet")
        print("✓ Tests validate requirements for Issues #67-70")
        print("\nNext Steps:")
        print("  1. Review failing tests to understand requirements")
        print("  2. Implement features to make tests pass (GREEN phase)")
        print("  3. Refactor implementation (REFACTOR phase)")
        return 0

    elif total_passed > 0:
        print_status("FAIL", "TDD RED PHASE FAILED")
        print(f"\n✗ {total_passed} tests passing (implementation exists)")
        print("✗ Cannot proceed with TDD if implementation already exists")
        print("\nEither:")
        print("  1. Remove implementation to return to RED phase")
        print("  2. Skip TDD and proceed to refactoring")
        return 1

    else:
        print_status("FAIL", "TDD RED PHASE INCOMPLETE")
        print("\n✗ Test files missing or not executable")
        print("✗ Cannot verify RED phase")
        print("\nFix:")
        print("  1. Ensure all test files exist")
        print("  2. Ensure tests are properly written")
        print("  3. Re-run verification")
        return 2


if __name__ == "__main__":
    sys.exit(main())
