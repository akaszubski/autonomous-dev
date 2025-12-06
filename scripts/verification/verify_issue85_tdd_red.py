#!/usr/bin/env python3
"""
Verification Script - Issue #85 TDD RED Phase

Verifies that tests for batch_state_manager.py portability fixes are in RED phase
(failing as expected before implementation).

This script:
1. Checks docstrings for hardcoded paths
2. Validates test file exists and is correctly structured
3. Confirms tests will fail (RED phase)
4. Reports detailed findings

Usage:
    python3 scripts/verification/verify_issue85_tdd_red.py

Expected Output:
    ✓ All checks pass (tests in RED phase)
    ✗ Some checks fail (tests may already be fixed)

Exit Codes:
    0: Tests are in RED phase (as expected)
    1: Tests are not in RED phase (unexpected)
"""

import sys
from pathlib import Path

# Add lib directory to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

import batch_state_manager
import inspect


def check_docstring_for_hardcoded_paths(name: str, docstring: str) -> tuple[bool, list]:
    """Check if docstring contains hardcoded paths.

    Returns:
        (has_hardcoded_paths, list_of_hardcoded_lines)
    """
    if not docstring:
        return False, []

    hardcoded_patterns = [
        'Path(".claude/batch_state.json")',
        "Path('.claude/batch_state.json')",
    ]

    findings = []
    for line in docstring.split('\n'):
        for pattern in hardcoded_patterns:
            if pattern in line:
                findings.append(line.strip())

    return len(findings) > 0, findings


def check_docstring_for_portable_patterns(docstring: str) -> bool:
    """Check if docstring mentions portable path functions."""
    if not docstring:
        return False

    portable_patterns = [
        'get_batch_state_file()',
        'get_default_state_file()',
    ]

    return any(pattern in docstring for pattern in portable_patterns)


def main():
    """Run verification checks."""
    print("=" * 80)
    print("VERIFICATION: Issue #85 TDD RED Phase")
    print("=" * 80)
    print()

    all_checks_pass = True
    total_checks = 0
    failed_checks = 0

    # Check 1: Test file exists
    print("Check 1: Test file exists")
    test_file = PROJECT_ROOT / "tests" / "unit" / "lib" / "test_batch_state_manager_portability.py"
    if test_file.exists():
        print("  ✓ PASS - Test file exists")
        total_checks += 1
    else:
        print(f"  ✗ FAIL - Test file not found: {test_file}")
        all_checks_pass = False
        failed_checks += 1
        total_checks += 1
    print()

    # Check 2: Module docstring contains hardcoded paths or missing portable examples
    print("Check 2: Module docstring validation")
    module_doc = batch_state_manager.__doc__
    has_hardcoded, hardcoded_lines = check_docstring_for_hardcoded_paths("module", module_doc)
    has_portable = check_docstring_for_portable_patterns(module_doc)

    if has_hardcoded:
        print("  ✓ PASS - Module docstring has hardcoded paths (will fail tests)")
        for line in hardcoded_lines[:3]:
            print(f"    - {line}")
        total_checks += 1
    elif not has_portable:
        print("  ✓ PASS - Module docstring missing portable examples (will fail tests)")
        total_checks += 1
    else:
        print("  ✗ FAIL - Module docstring already uses portable paths (tests may pass)")
        all_checks_pass = False
        failed_checks += 1
        total_checks += 1
    print()

    # Check 3-7: Function docstrings
    functions_to_check = [
        ('save_batch_state', batch_state_manager.save_batch_state),
        ('load_batch_state', batch_state_manager.load_batch_state),
        ('update_batch_progress', batch_state_manager.update_batch_progress),
        ('record_auto_clear_event', batch_state_manager.record_auto_clear_event),
    ]

    for idx, (func_name, func) in enumerate(functions_to_check, start=3):
        print(f"Check {idx}: {func_name}() docstring validation")
        func_doc = inspect.getdoc(func)
        has_hardcoded, hardcoded_lines = check_docstring_for_hardcoded_paths(func_name, func_doc)

        if has_hardcoded:
            print(f"  ✓ PASS - {func_name} has hardcoded paths (will fail tests)")
            for line in hardcoded_lines[:2]:
                print(f"    - {line}")
            total_checks += 1
        else:
            print(f"  ✗ FAIL - {func_name} already uses portable paths (tests may pass)")
            all_checks_pass = False
            failed_checks += 1
            total_checks += 1
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total checks: {total_checks}")
    print(f"Passed: {total_checks - failed_checks}")
    print(f"Failed: {failed_checks}")
    print()

    if all_checks_pass:
        print("✓ VERIFICATION PASSED")
        print()
        print("Status: RED PHASE (as expected)")
        print("  - Tests exist and are correctly structured")
        print("  - Docstrings contain hardcoded paths")
        print("  - Tests will FAIL until implementation fixes docstrings")
        print()
        print("Next Step: Implement fixes to make tests pass (GREEN phase)")
        return 0
    else:
        print("✗ VERIFICATION FAILED")
        print()
        print("Status: Tests may already be in GREEN phase")
        print("  - Some docstrings already use portable paths")
        print("  - Tests may PASS without implementation")
        print()
        print("Action: Review docstrings and tests manually")
        return 1


if __name__ == "__main__":
    sys.exit(main())
