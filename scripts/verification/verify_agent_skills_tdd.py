#!/usr/bin/env python3
"""
Verification script for Issue #35 TDD tests (RED phase)

This script runs all TDD tests for agent skills integration and verifies
they fail as expected before implementation.

Expected: All tests should FAIL (red phase) until implementation is complete.

Usage:
    python tests/verify_agent_skills_tdd.py
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('=' * 60)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        return result.returncode == 0, result.stdout
    except subprocess.TimeoutExpired:
        print("ERROR: Command timed out after 60 seconds")
        return False, ""
    except Exception as e:
        print(f"ERROR: {e}")
        return False, ""


def main():
    """Run all TDD tests and verify they fail."""

    print("=" * 60)
    print("Issue #35: Agents should actively use skills")
    print("TDD Verification Script (RED PHASE)")
    print("=" * 60)
    print("\nThis script verifies that all tests FAIL before implementation.")
    print("Tests should PASS only after implementation is complete.\n")

    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent

    # Test files to run
    test_files = [
        ("Unit tests - Agent skill sections", "tests/unit/test_agent_skills.py"),
        ("Integration tests - Skill activation", "tests/integration/test_skill_activation.py"),
    ]

    results = []

    for description, test_file in test_files:
        full_path = project_root / test_file

        if not full_path.exists():
            print(f"\n❌ ERROR: Test file not found: {test_file}")
            results.append((description, False, "Test file not found"))
            continue

        # Run pytest with verbose output
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(full_path),
            "-v",
            "--tb=short",
            "--no-header",
        ]

        success, output = run_command(cmd, description)

        # For TDD RED phase, we EXPECT failures
        if success:
            status = "⚠️  UNEXPECTED PASS"
            message = "Tests should FAIL in red phase!"
        else:
            status = "✅ EXPECTED FAIL"
            message = "Tests failing as expected (red phase)"

        results.append((description, not success, message))
        print(f"\n{status}: {message}")

    # Summary
    print("\n" + "=" * 60)
    print("TDD RED PHASE VERIFICATION SUMMARY")
    print("=" * 60)

    expected_failures = 0
    unexpected_passes = 0

    for description, expected_fail, message in results:
        if expected_fail:
            print(f"✅ {description}: {message}")
            expected_failures += 1
        else:
            print(f"⚠️  {description}: {message}")
            unexpected_passes += 1

    print("\n" + "=" * 60)
    print(f"Expected failures (red phase): {expected_failures}/{len(results)}")
    print(f"Unexpected passes: {unexpected_passes}/{len(results)}")
    print("=" * 60)

    if expected_failures == len(results):
        print("\n✅ TDD RED PHASE VERIFIED!")
        print("All tests fail as expected before implementation.")
        print("\nNext steps:")
        print("1. Implement 'Relevant Skills' sections in 13 agent files")
        print("2. Run tests again to verify they pass (green phase)")
        print("3. Refactor as needed (refactor phase)")
        return 0
    else:
        print("\n⚠️  TDD RED PHASE INCOMPLETE")
        print(f"{unexpected_passes} test suite(s) passed unexpectedly.")
        print("Tests should fail before implementation!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
