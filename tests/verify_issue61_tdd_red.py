#!/usr/bin/env python3
"""
Verification script for Issue #61 TDD Red Phase.

Verifies that all tests for Zero Manual Git Operations by Default are failing
as expected (modules not yet implemented).

Tests should fail with ImportError or assertion failures.

Date: 2025-11-11
Issue: #61 (Enable Zero Manual Git Operations by Default)
Agent: test-master
Phase: TDD Red Verification
"""

import subprocess
import sys
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def run_test_file(test_file: Path) -> dict:
    """Run a single test file and return results."""
    print(f"\n{YELLOW}Running: {test_file.name}{RESET}")

    try:
        result = subprocess.run(
            ["pytest", str(test_file), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60
        )

        return {
            "file": test_file.name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "file": test_file.name,
            "returncode": -1,
            "stdout": "",
            "stderr": "Test timed out",
            "passed": False
        }
    except Exception as e:
        return {
            "file": test_file.name,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "passed": False
        }


def main():
    """Run all Issue #61 test files and verify they fail (TDD red phase)."""
    print(f"{YELLOW}=" * 80)
    print("Issue #61 TDD Red Phase Verification")
    print("Testing: Zero Manual Git Operations by Default")
    print("=" * 80)
    print(f"{RESET}")

    # Define test files for Issue #61
    test_dir = Path(__file__).parent
    test_files = [
        test_dir / "unit" / "lib" / "test_user_state_manager.py",
        test_dir / "unit" / "lib" / "test_first_run_warning.py",
        test_dir / "unit" / "lib" / "test_parse_consent_value_defaults.py",
        test_dir / "integration" / "test_first_run_flow.py",
    ]

    results = []

    # Run each test file
    for test_file in test_files:
        if not test_file.exists():
            print(f"{RED}ERROR: Test file not found: {test_file}{RESET}")
            continue

        result = run_test_file(test_file)
        results.append(result)

    # Summary
    print(f"\n{YELLOW}=" * 80)
    print("TDD Red Phase Verification Summary")
    print("=" * 80)
    print(f"{RESET}")

    all_failing = True
    expected_failures = 0
    unexpected_passes = 0

    for result in results:
        if result["passed"]:
            # Tests should NOT pass in red phase
            print(f"{RED}✗ UNEXPECTED PASS: {result['file']}{RESET}")
            print(f"  Tests are passing but should be failing (implementation exists?)")
            unexpected_passes += 1
            all_failing = False
        else:
            # Check if it's the expected failure (ImportError or assertion failures)
            if "ImportError" in result["stderr"] or "ImportError" in result["stdout"]:
                print(f"{GREEN}✓ EXPECTED FAIL: {result['file']}{RESET}")
                print(f"  Reason: Module not found (implementation not yet created)")
                expected_failures += 1
            elif "AssertionError" in result["stderr"] or "AssertionError" in result["stdout"]:
                print(f"{GREEN}✓ EXPECTED FAIL: {result['file']}{RESET}")
                print(f"  Reason: Assertion failures (behavior not yet implemented)")
                expected_failures += 1
            elif "SKIPPED" in result["stdout"]:
                print(f"{GREEN}✓ EXPECTED SKIP: {result['file']}{RESET}")
                print(f"  Reason: Module not found (skipped as expected)")
                expected_failures += 1
            else:
                print(f"{YELLOW}? UNEXPECTED ERROR: {result['file']}{RESET}")
                print(f"  Error: {result['stderr'][:200]}")

    print(f"\n{YELLOW}Test Coverage:{RESET}")
    print(f"  User State Manager:       15 tests")
    print(f"  First Run Warning:        10 tests")
    print(f"  Parse Consent Defaults:    5 tests")
    print(f"  First Run Integration:     8 tests")
    print(f"  {YELLOW}Total:                    38 tests{RESET}")

    print(f"\n{YELLOW}Results:{RESET}")
    print(f"  Expected Failures: {expected_failures}")
    print(f"  Unexpected Passes: {unexpected_passes}")

    if all_failing and expected_failures > 0:
        print(f"\n{GREEN}✓ TDD RED PHASE VERIFIED{RESET}")
        print(f"All tests are failing as expected.")
        print(f"Ready to implement features to make tests pass (TDD green phase).")
        return 0
    elif unexpected_passes > 0:
        print(f"\n{RED}✗ TDD RED PHASE FAILED{RESET}")
        print(f"Some tests are passing but should be failing.")
        print(f"Check if implementation already exists.")
        return 1
    else:
        print(f"\n{YELLOW}⚠ INCOMPLETE VERIFICATION{RESET}")
        print(f"Unable to verify all test files.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
