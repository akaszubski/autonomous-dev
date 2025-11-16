#!/usr/bin/env python3
"""
Verification script for Issue #72 TDD Red Phase

Verifies that all tests are properly failing (TDD red phase).
This ensures we wrote the tests FIRST before implementation.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run_test(test_path: str) -> Tuple[bool, str]:
    """
    Run a single test and check if it fails.

    Returns:
        Tuple of (failed: bool, output: str)
    """
    result = subprocess.run(
        ["python", "-m", "pytest", test_path, "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    # Test should FAIL in red phase (non-zero return code)
    failed = result.returncode != 0

    return failed, result.stdout + result.stderr


def main():
    """Verify TDD red phase for Issue #72."""

    print("=" * 70)
    print("Issue #72 TDD Red Phase Verification")
    print("=" * 70)
    print()

    # Key tests that must fail in red phase
    key_tests = [
        (
            "Token Counting Script Exists",
            "tests/unit/test_agent_output_cleanup_token_counting.py::test_token_counting_script_exists"
        ),
        (
            "Phase 1 Skill References",
            "tests/unit/test_agent_output_cleanup_skill_references.py::test_phase1_target_agents_have_skill_reference"
        ),
        (
            "Section Length Threshold",
            "tests/unit/test_agent_output_cleanup_section_length.py::test_no_agent_exceeds_30_line_threshold"
        ),
    ]

    all_failing = True
    results = []

    for test_name, test_path in key_tests:
        print(f"Testing: {test_name}...")

        failed, output = run_test(test_path)

        if failed:
            print(f"  ✅ FAILED (as expected in red phase)")
            results.append((test_name, "FAIL", "Expected"))
        else:
            print(f"  ❌ PASSED (unexpected - should fail in red phase)")
            results.append((test_name, "PASS", "Unexpected"))
            all_failing = False

        # Extract key error message
        if "AssertionError" in output:
            error_start = output.find("AssertionError:")
            error_end = output.find("\n", error_start)
            error_msg = output[error_start:error_end].strip()
            print(f"     Error: {error_msg}")
        elif "ModuleNotFoundError" in output:
            error_start = output.find("ModuleNotFoundError:")
            error_end = output.find("\n", error_start)
            error_msg = output[error_start:error_end].strip()
            print(f"     Error: {error_msg}")

        print()

    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()

    for test_name, status, expected in results:
        symbol = "✅" if status == "FAIL" else "❌"
        print(f"{symbol} {test_name}: {status} ({expected})")

    print()
    print("-" * 70)
    print()

    if all_failing:
        print("✅ TDD RED PHASE VERIFIED")
        print()
        print("All key tests are FAILING as expected.")
        print("This confirms tests were written FIRST before implementation.")
        print()
        print("Next step: Run implementer agent to make tests pass (TDD green phase).")
        print()
        return 0
    else:
        print("❌ TDD RED PHASE INCOMPLETE")
        print()
        print("Some tests are passing when they should fail.")
        print("This suggests implementation may have happened before tests.")
        print()
        print("Review the passing tests and ensure implementation is removed.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
