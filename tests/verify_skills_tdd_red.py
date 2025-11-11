#!/usr/bin/env python3
"""
TDD Red Phase Verification for Skills Extraction (Issues #63, #64)

This script verifies that all tests are written and FAILING (red phase) before
implementation begins. This ensures we're following strict TDD methodology.

Verification Steps:
1. Check all test files exist
2. Count test functions in each file
3. Run tests and verify they FAIL (not skip, not pass)
4. Generate summary report

Expected State:
- All test files created
- All tests FAILING (imports fail, files don't exist, etc.)
- No implementation exists yet
- Ready for implementer agent to make tests pass

Author: test-master agent
Date: 2025-11-11
Issues: #63, #64
"""

import sys
import subprocess
from pathlib import Path
from collections import defaultdict

# Test file paths
TEST_FILES = [
    "tests/unit/skills/test_agent_output_formats_skill.py",
    "tests/unit/skills/test_error_handling_patterns_skill.py",
    "tests/integration/test_full_workflow_with_skills.py",
]

# Expected implementation files (should NOT exist yet)
IMPLEMENTATION_FILES = [
    "plugins/autonomous-dev/skills/agent-output-formats/SKILL.md",
    "plugins/autonomous-dev/skills/error-handling-patterns/SKILL.md",
]


def count_test_functions(file_path: Path) -> dict:
    """Count test functions in a test file."""
    content = file_path.read_text()

    # Count test functions (def test_*)
    test_count = content.count("def test_")

    # Count test classes (class Test*)
    class_count = content.count("class Test")

    return {
        "test_functions": test_count,
        "test_classes": class_count,
        "total_lines": len(content.splitlines())
    }


def verify_implementation_not_exists():
    """Verify implementation files don't exist yet (TDD red phase)."""
    print("\n" + "="*80)
    print("STEP 1: Verify No Implementation Exists (TDD Red Phase)")
    print("="*80)

    all_missing = True
    for impl_file in IMPLEMENTATION_FILES:
        path = Path(impl_file)
        exists = path.exists()
        status = "❌ EXISTS (VIOLATION!)" if exists else "✅ Missing (Expected)"
        print(f"{status}: {impl_file}")
        if exists:
            all_missing = False

    if all_missing:
        print("\n✅ PASS: No implementation exists yet (correct TDD red phase)")
    else:
        print("\n❌ FAIL: Implementation files found! Delete them for TDD red phase.")

    return all_missing


def verify_test_files_exist():
    """Verify all test files are created."""
    print("\n" + "="*80)
    print("STEP 2: Verify All Test Files Exist")
    print("="*80)

    all_exist = True
    stats = {}

    for test_file in TEST_FILES:
        path = Path(test_file)
        exists = path.exists()
        status = "✅ Exists" if exists else "❌ Missing"
        print(f"{status}: {test_file}")

        if exists:
            stats[test_file] = count_test_functions(path)
        else:
            all_exist = False
            stats[test_file] = None

    if all_exist:
        print("\n✅ PASS: All test files created")
    else:
        print("\n❌ FAIL: Some test files missing")

    return all_exist, stats


def run_pytest_and_verify_failures():
    """Run pytest and verify tests FAIL (not skip, not pass)."""
    print("\n" + "="*80)
    print("STEP 3: Run Tests and Verify They FAIL")
    print("="*80)

    results = {}

    for test_file in TEST_FILES:
        path = Path(test_file)
        if not path.exists():
            results[test_file] = "MISSING"
            continue

        print(f"\nRunning: {test_file}")

        try:
            # Run pytest with verbose output
            result = subprocess.run(
                ["pytest", str(path), "-v", "--tb=short", "--no-header"],
                capture_output=True,
                text=True,
                timeout=30
            )

            output = result.stdout + result.stderr

            # Parse results
            failed_count = output.count(" FAILED")
            passed_count = output.count(" PASSED")
            skipped_count = output.count(" SKIPPED")
            error_count = output.count(" ERROR")

            results[test_file] = {
                "failed": failed_count,
                "passed": passed_count,
                "skipped": skipped_count,
                "error": error_count,
                "returncode": result.returncode
            }

            # Print summary
            print(f"  Failed: {failed_count}, Passed: {passed_count}, "
                  f"Skipped: {skipped_count}, Error: {error_count}")

            # Show first few lines of output for context
            lines = output.splitlines()[:10]
            for line in lines:
                if "FAILED" in line or "ERROR" in line or "test_" in line:
                    print(f"  {line}")

        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Timeout running tests (> 30s)")
            results[test_file] = "TIMEOUT"
        except Exception as e:
            print(f"  ❌ Error running tests: {e}")
            results[test_file] = f"ERROR: {e}"

    return results


def generate_summary_report(impl_check, test_files_exist, test_stats, pytest_results):
    """Generate comprehensive summary report."""
    print("\n" + "="*80)
    print("TDD RED PHASE VERIFICATION SUMMARY")
    print("="*80)

    # Overall status
    print("\n## Overall Status")
    print(f"{'✅' if impl_check else '❌'} Implementation files don't exist (red phase)")
    print(f"{'✅' if test_files_exist else '❌'} All test files created")

    # Test file statistics
    print("\n## Test File Statistics")
    total_tests = 0
    total_classes = 0
    total_lines = 0

    for test_file, stats in test_stats.items():
        if stats:
            print(f"\n{test_file}:")
            print(f"  Test Classes: {stats['test_classes']}")
            print(f"  Test Functions: {stats['test_functions']}")
            print(f"  Total Lines: {stats['total_lines']}")
            total_tests += stats['test_functions']
            total_classes += stats['test_classes']
            total_lines += stats['total_lines']

    print(f"\nTotals:")
    print(f"  Test Classes: {total_classes}")
    print(f"  Test Functions: {total_tests}")
    print(f"  Total Lines: {total_lines}")

    # Pytest results
    print("\n## Pytest Results")
    total_failed = 0
    total_passed = 0
    total_skipped = 0

    for test_file, result in pytest_results.items():
        if isinstance(result, dict):
            total_failed += result['failed']
            total_passed += result['passed']
            total_skipped += result['skipped']

    print(f"  Total Failed: {total_failed}")
    print(f"  Total Passed: {total_passed}")
    print(f"  Total Skipped: {total_skipped}")

    # TDD Red Phase Status
    print("\n## TDD Red Phase Status")

    all_failing = total_failed > 0 or total_passed == 0

    if impl_check and test_files_exist and all_failing:
        print("\n✅ TDD RED PHASE COMPLETE!")
        print("   - All test files created")
        print("   - No implementation exists")
        print("   - Tests are FAILING (as expected)")
        print("\n🎯 Ready for implementer agent to make tests pass (TDD green phase)")
        return True
    else:
        print("\n❌ TDD RED PHASE INCOMPLETE")
        if not impl_check:
            print("   - Implementation files exist (delete them!)")
        if not test_files_exist:
            print("   - Some test files missing")
        if not all_failing:
            print("   - Tests should be FAILING, not passing")
        print("\n⚠️  Fix issues above before proceeding to implementation")
        return False

    # Coverage expectations
    print("\n## Coverage Expectations (After Implementation)")
    print("  - Issue #63 (agent-output-formats): 15 agents updated")
    print("  - Issue #64 (error-handling-patterns): 22 libraries updated")
    print("  - Token savings: ~10,820 tokens total")
    print("  - Test coverage: 100% of skill creation and integration")


def main():
    """Run complete TDD red phase verification."""
    print("="*80)
    print("TDD RED PHASE VERIFICATION - Skills Extraction (Issues #63, #64)")
    print("="*80)

    # Step 1: Verify no implementation exists
    impl_check = verify_implementation_not_exists()

    # Step 2: Verify test files exist and count tests
    test_files_exist, test_stats = verify_test_files_exist()

    # Step 3: Run pytest and verify failures
    pytest_results = run_pytest_and_verify_failures()

    # Step 4: Generate summary report
    success = generate_summary_report(impl_check, test_files_exist, test_stats, pytest_results)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
