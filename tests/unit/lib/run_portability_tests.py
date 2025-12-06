#!/usr/bin/env python3
"""
Minimal test runner for batch_state_manager_portability tests.

This is a fallback runner for when pytest is not available.
It runs the tests manually and reports results.
"""

import sys
from pathlib import Path

# Add lib directory to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# Import test functions
from test_batch_state_manager_portability import (
    find_hardcoded_paths_in_docstring,
    check_for_portable_path_usage,
)

import batch_state_manager
import inspect


def run_tests():
    """Run all docstring validation tests manually."""
    print("=" * 80)
    print("BATCH STATE MANAGER PORTABILITY TESTS (Issue #85)")
    print("=" * 80)
    print()

    failures = []
    passes = []

    # Test 1: Module docstring
    print("Test 1: Module docstring uses portable path examples")
    module_doc = batch_state_manager.__doc__
    hardcoded = find_hardcoded_paths_in_docstring(module_doc)
    portable = check_for_portable_path_usage(module_doc)

    if hardcoded:
        print(f"  ✗ FAIL - Found hardcoded paths:")
        for pattern, line in hardcoded:
            print(f"    - {line}")
        failures.append("Module docstring has hardcoded paths")
    elif not portable:
        print(f"  ✗ FAIL - No portable path examples found")
        failures.append("Module docstring missing portable path examples")
    else:
        print(f"  ✓ PASS - Uses portable path functions")
        passes.append("Module docstring")
    print()

    # Test 2: save_batch_state docstring
    print("Test 2: save_batch_state() docstring uses portable examples")
    from batch_state_manager import save_batch_state
    save_doc = inspect.getdoc(save_batch_state)
    hardcoded = find_hardcoded_paths_in_docstring(save_doc)

    if hardcoded:
        print(f"  ✗ FAIL - Found hardcoded paths:")
        for pattern, line in hardcoded:
            print(f"    - {line}")
        failures.append("save_batch_state docstring has hardcoded paths")
    else:
        print(f"  ✓ PASS - No hardcoded paths")
        passes.append("save_batch_state docstring")
    print()

    # Test 3: load_batch_state docstring
    print("Test 3: load_batch_state() docstring uses portable examples")
    from batch_state_manager import load_batch_state
    load_doc = inspect.getdoc(load_batch_state)
    hardcoded = find_hardcoded_paths_in_docstring(load_doc)

    if hardcoded:
        print(f"  ✗ FAIL - Found hardcoded paths:")
        for pattern, line in hardcoded:
            print(f"    - {line}")
        failures.append("load_batch_state docstring has hardcoded paths")
    else:
        print(f"  ✓ PASS - No hardcoded paths")
        passes.append("load_batch_state docstring")
    print()

    # Test 4: update_batch_progress docstring
    print("Test 4: update_batch_progress() docstring uses portable examples")
    from batch_state_manager import update_batch_progress
    update_doc = inspect.getdoc(update_batch_progress)
    hardcoded = find_hardcoded_paths_in_docstring(update_doc)

    if hardcoded:
        print(f"  ✗ FAIL - Found hardcoded paths:")
        for pattern, line in hardcoded:
            print(f"    - {line}")
        failures.append("update_batch_progress docstring has hardcoded paths")
    else:
        print(f"  ✓ PASS - No hardcoded paths")
        passes.append("update_batch_progress docstring")
    print()

    # Test 5: record_auto_clear_event docstring
    print("Test 5: record_auto_clear_event() docstring uses portable examples")
    from batch_state_manager import record_auto_clear_event
    record_doc = inspect.getdoc(record_auto_clear_event)
    hardcoded = find_hardcoded_paths_in_docstring(record_doc)

    if hardcoded:
        print(f"  ✗ FAIL - Found hardcoded paths:")
        for pattern, line in hardcoded:
            print(f"    - {line}")
        failures.append("record_auto_clear_event docstring has hardcoded paths")
    else:
        print(f"  ✓ PASS - No hardcoded paths")
        passes.append("record_auto_clear_event docstring")
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Passed: {len(passes)}")
    print(f"Failed: {len(failures)}")
    print()

    if failures:
        print("FAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        print()
        print("STATUS: RED PHASE (as expected - docstrings need fixing)")
        return 1
    else:
        print("STATUS: All tests passed (docstrings already use portable paths)")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
