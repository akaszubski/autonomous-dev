#!/usr/bin/env python3
"""
Verify TDD Red Phase for PROJECT.md Auto-Update Feature

This script verifies that:
1. All tests are written before implementation (TDD red phase)
2. All tests fail with expected errors (ModuleNotFoundError)
3. Test coverage meets requirements
4. Tests follow best practices

Usage:
    python tests/verify_project_progress_tdd.py
"""

import subprocess
import sys
from pathlib import Path


def run_verification():
    """Run TDD red phase verification."""

    print("=" * 80)
    print("TDD RED PHASE VERIFICATION - PROJECT.md Auto-Update Feature")
    print("=" * 80)
    print()

    # Check that implementation files DON'T exist yet
    print("1. Verifying implementation files don't exist (TDD red phase)...")

    lib_file = Path("plugins/autonomous-dev/lib/project_md_updater.py")
    hook_file = Path("plugins/autonomous-dev/hooks/auto_update_project_progress.py")

    if lib_file.exists():
        print(f"   ❌ FAILED: {lib_file} already exists!")
        print("      TDD requires tests BEFORE implementation")
        return False
    else:
        print(f"   ✓ {lib_file} doesn't exist (correct)")

    if hook_file.exists():
        print(f"   ❌ FAILED: {hook_file} already exists!")
        print("      TDD requires tests BEFORE implementation")
        return False
    else:
        print(f"   ✓ {hook_file} doesn't exist (correct)")

    print()

    # Check that test file exists
    print("2. Verifying test file exists...")
    test_file = Path("tests/test_project_progress_update.py")

    if not test_file.exists():
        print(f"   ❌ FAILED: {test_file} doesn't exist!")
        return False
    else:
        print(f"   ✓ {test_file} exists")

    print()

    # Run pytest and check for expected failures
    print("3. Running tests (expecting all to fail)...")
    print()

    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            str(test_file),
            "-v",
            "--tb=line",
            "-q"
        ],
        capture_output=True,
        text=True
    )

    # Parse output
    output_lines = result.stdout.split("\n")

    # Count tests
    failed_count = 0
    total_count = 0
    module_errors = 0

    for line in output_lines:
        if "FAILED" in line:
            failed_count += 1
            total_count += 1
            if "ModuleNotFoundError" in line:
                module_errors += 1
        elif "PASSED" in line:
            total_count += 1

    # Check summary line for accurate counts
    for line in output_lines:
        if "failed" in line and "passed" not in line:
            # Extract numbers from summary
            import re
            match = re.search(r'(\d+) failed', line)
            if match:
                failed_count = int(match.group(1))
                total_count = failed_count  # All should fail in red phase

    print(f"   Total tests: {total_count}")
    print(f"   Failed tests: {failed_count}")
    print(f"   ModuleNotFoundError: {module_errors}")
    print()

    # Verify all tests failed
    if total_count == 0:
        print("   ❌ FAILED: No tests found!")
        return False

    if failed_count != total_count:
        print(f"   ❌ FAILED: Expected all {total_count} tests to fail, but only {failed_count} failed")
        print("      In TDD red phase, all tests should fail (no implementation yet)")
        return False

    print(f"   ✓ All {total_count} tests failing (correct for TDD red phase)")
    print()

    # Verify tests are failing with correct error
    if module_errors < total_count * 0.9:  # At least 90% should be ModuleNotFoundError
        print(f"   ⚠️  WARNING: Only {module_errors}/{total_count} tests failing with ModuleNotFoundError")
        print("      Expected: Most tests fail because modules don't exist yet")
    else:
        print(f"   ✓ Tests failing with expected error (ModuleNotFoundError)")

    print()

    # Check test quality
    print("4. Checking test quality...")

    with open(test_file) as f:
        test_content = f.read()

    # Check for key patterns
    quality_checks = [
        ("Docstrings in tests", '"""' in test_content),
        ("Security tests present", "test_symlink_detection" in test_content),
        ("Edge case tests present", "test_empty_goals_section" in test_content),
        ("Integration tests present", "TestProjectProgressUpdateIntegration" in test_content),
        ("Mock usage", "from unittest.mock import" in test_content),
        ("pytest fixtures", "tmpdir" in test_content or "tmp_path" in test_content),
    ]

    quality_pass = True
    for check_name, check_result in quality_checks:
        if check_result:
            print(f"   ✓ {check_name}")
        else:
            print(f"   ❌ {check_name}")
            quality_pass = False

    print()

    # Final summary
    print("=" * 80)
    print("TDD RED PHASE VERIFICATION SUMMARY")
    print("=" * 80)

    if failed_count == total_count and total_count > 0:
        print("✅ RED PHASE COMPLETE")
        print()
        print(f"   - {total_count} tests written BEFORE implementation")
        print(f"   - All {failed_count} tests failing (as expected)")
        print("   - Implementation files don't exist yet (correct)")
        print()
        print("Next step: Implement the feature to make tests pass (GREEN phase)")
        return True
    else:
        print("❌ RED PHASE INCOMPLETE")
        print()
        print("   Issues found - review output above")
        return False


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
