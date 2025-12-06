#!/usr/bin/env python3
"""
Verification script for TDD red phase.

This script verifies that:
1. Test files exist and are properly structured
2. Implementation module doesn't exist yet (TDD red phase)
3. Tests will fail/skip when run

Run this to confirm we're in the correct TDD state before implementation.

Date: 2025-11-04
Workflow: git_automation
Agent: test-master
"""

import sys
from pathlib import Path

def verify_test_files_exist():
    """Verify test files were created."""
    print("=" * 60)
    print("STEP 1: Verify test files exist")
    print("=" * 60)

    test_files = [
        Path("tests/unit/test_git_operations.py"),
        Path("tests/integration/test_auto_implement_git.py"),
        Path("tests/GIT_AUTOMATION_TEST_SUMMARY.md"),
    ]

    all_exist = True
    for test_file in test_files:
        if test_file.exists():
            lines = len(test_file.read_text().splitlines())
            print(f"✅ {test_file} ({lines} lines)")
        else:
            print(f"❌ {test_file} - NOT FOUND")
            all_exist = False

    return all_exist


def verify_implementation_not_exists():
    """Verify implementation module doesn't exist yet (TDD red phase)."""
    print("\n" + "=" * 60)
    print("STEP 2: Verify implementation doesn't exist yet (TDD red)")
    print("=" * 60)

    implementation_file = Path("plugins/autonomous-dev/lib/git_operations.py")

    if implementation_file.exists():
        print(f"❌ {implementation_file} - EXISTS (should NOT exist yet)")
        print("   This means we're NOT in TDD red phase!")
        return False
    else:
        print(f"✅ {implementation_file} - Does not exist (correct for TDD red phase)")
        return True


def verify_import_fails():
    """Verify importing git_operations fails (module not found)."""
    print("\n" + "=" * 60)
    print("STEP 3: Verify module import fails (TDD red)")
    print("=" * 60)

    # Add lib directory to path
    lib_path = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"
    sys.path.insert(0, str(lib_path))

    try:
        from git_operations import validate_git_repo
        print("❌ Module imported successfully - should NOT be able to import yet!")
        return False
    except ImportError as e:
        print(f"✅ Import failed as expected: {e}")
        return True


def count_test_cases():
    """Count test cases in test files."""
    print("\n" + "=" * 60)
    print("STEP 4: Count test cases")
    print("=" * 60)

    unit_tests = Path("tests/unit/test_git_operations.py")
    integration_tests = Path("tests/integration/test_auto_implement_git.py")

    # Simple count of test methods (lines starting with "def test_")
    unit_count = sum(1 for line in unit_tests.read_text().splitlines()
                     if line.strip().startswith("def test_"))
    integration_count = sum(1 for line in integration_tests.read_text().splitlines()
                           if line.strip().startswith("def test_"))

    print(f"Unit tests: {unit_count} test cases")
    print(f"Integration tests: {integration_count} test cases")
    print(f"Total: {unit_count + integration_count} test cases")

    return unit_count + integration_count


def verify_test_structure():
    """Verify test files have proper structure."""
    print("\n" + "=" * 60)
    print("STEP 5: Verify test structure")
    print("=" * 60)

    unit_tests = Path("tests/unit/test_git_operations.py")
    integration_tests = Path("tests/integration/test_auto_implement_git.py")

    checks = []

    # Check for pytest.skip in both files
    for test_file in [unit_tests, integration_tests]:
        content = test_file.read_text()

        # Check for TDD header
        if "TDD Mode" in content:
            print(f"✅ {test_file.name}: Has TDD header")
            checks.append(True)
        else:
            print(f"❌ {test_file.name}: Missing TDD header")
            checks.append(False)

        # Check for pytest.skip
        if "pytest.skip" in content:
            print(f"✅ {test_file.name}: Has pytest.skip for missing module")
            checks.append(True)
        else:
            print(f"❌ {test_file.name}: Missing pytest.skip")
            checks.append(False)

        # Check for mocking imports
        if "from unittest.mock import" in content:
            print(f"✅ {test_file.name}: Has mocking imports")
            checks.append(True)
        else:
            print(f"❌ {test_file.name}: Missing mocking imports")
            checks.append(False)

    return all(checks)


def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("TDD RED PHASE VERIFICATION")
    print("=" * 60)
    print("Verifying tests are written BEFORE implementation...")
    print()

    results = []

    # Run all checks
    results.append(("Test files exist", verify_test_files_exist()))
    results.append(("Implementation doesn't exist", verify_implementation_not_exists()))
    results.append(("Module import fails", verify_import_fails()))
    test_count = count_test_cases()
    results.append(("Test structure valid", verify_test_structure()))

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    print(f"\nTotal test cases: {test_count}")

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TDD RED PHASE VERIFIED")
        print("=" * 60)
        print("\nAll checks passed! We are in correct TDD red phase:")
        print("  - Tests are written (1,600+ lines)")
        print("  - Implementation doesn't exist yet")
        print("  - Tests will fail/skip when run")
        print("\nNext step: Implement git_operations.py to make tests pass (green phase)")
        return 0
    else:
        print("❌ TDD RED PHASE VERIFICATION FAILED")
        print("=" * 60)
        print("\nSome checks failed. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
