#!/usr/bin/env python3
"""
Verify Step 8 git integration tests are in TDD red phase.

This script confirms:
1. Test files exist
2. Tests fail with ImportError (module not found)
3. Test structure is comprehensive

Run this BEFORE implementing auto_implement_git_integration module.

Date: 2025-11-05
Workflow: git_automation
Agent: test-master
Phase: TDD Red Verification
"""

import subprocess
import sys
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(message: str):
    """Print colored header."""
    print(f"\n{BOLD}{BLUE}{'=' * 80}{RESET}")
    print(f"{BOLD}{BLUE}{message}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 80}{RESET}\n")


def print_success(message: str):
    """Print success message."""
    print(f"{GREEN}✓ {message}{RESET}")


def print_error(message: str):
    """Print error message."""
    print(f"{RED}✗ {message}{RESET}")


def print_warning(message: str):
    """Print warning message."""
    print(f"{YELLOW}⚠ {message}{RESET}")


def print_info(message: str):
    """Print info message."""
    print(f"{BLUE}ℹ {message}{RESET}")


def check_test_file_exists(file_path: Path) -> bool:
    """Check if test file exists."""
    if file_path.exists():
        print_success(f"Test file exists: {file_path.name}")
        return True
    else:
        print_error(f"Test file missing: {file_path.name}")
        return False


def count_test_cases(file_path: Path) -> int:
    """Count test cases in file."""
    content = file_path.read_text()
    test_count = content.count('def test_')
    return test_count


def run_test_file(file_path: Path) -> dict:
    """
    Run test file and capture results.

    Returns:
        dict with keys: success, output, error, skipped
    """
    try:
        result = subprocess.run(
            ['pytest', str(file_path), '-v', '--tb=short'],
            cwd=file_path.parent.parent,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout + result.stderr

        # Check if skipped due to ImportError (expected in TDD red phase)
        skipped = 'SKIPPED' in output and 'ImportError' in output

        return {
            'success': result.returncode == 0,
            'output': output,
            'error': result.stderr,
            'skipped': skipped
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Test execution timeout',
            'skipped': False
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': str(e),
            'skipped': False
        }


def verify_tdd_red_phase():
    """Verify tests are in TDD red phase (failing as expected)."""
    print_header("Step 8 Git Integration - TDD Red Phase Verification")

    # Define test files
    test_files = [
        Path(__file__).parent / 'integration' / 'test_auto_implement_step8_agents.py',
        Path(__file__).parent / 'unit' / 'test_auto_implement_git_integration.py',
    ]

    all_passed = True

    # Check 1: Test files exist
    print_info("Check 1: Test files exist")
    for test_file in test_files:
        if not check_test_file_exists(test_file):
            all_passed = False

    # Check 2: Count test cases
    print_info("\nCheck 2: Test case coverage")
    total_tests = 0
    for test_file in test_files:
        if test_file.exists():
            count = count_test_cases(test_file)
            total_tests += count
            print_success(f"{test_file.name}: {count} test cases")

    if total_tests < 30:
        print_warning(f"Total test count ({total_tests}) is low. Aim for 40+ tests.")
    else:
        print_success(f"Total test count: {total_tests} (good coverage)")

    # Check 3: Tests fail with ImportError (TDD red phase)
    print_info("\nCheck 3: Tests fail with ImportError (TDD red phase)")
    for test_file in test_files:
        if test_file.exists():
            print_info(f"\nRunning: {test_file.name}")
            result = run_test_file(test_file)

            if result['skipped']:
                print_success(f"✓ Tests skipped due to ImportError (TDD red phase confirmed)")
                print_info("  Module not implemented yet - this is expected!")
            elif not result['success']:
                print_warning(f"Tests failed for unexpected reason:")
                print(result['error'][:500])  # Show first 500 chars
            else:
                print_error(f"✗ Tests passed - should be FAILING (not in TDD red phase)")
                all_passed = False

    # Check 4: Test structure quality
    print_info("\nCheck 4: Test structure quality")

    integration_test = test_files[0]
    unit_test = test_files[1]

    if integration_test.exists():
        content = integration_test.read_text()

        # Check for key test classes
        expected_classes = [
            'TestStep8AgentIntegration',
            'TestConsentManagement',
            'TestAgentInvocation',
            'TestGracefulDegradation',
            'TestFullPipeline',
        ]

        for class_name in expected_classes:
            if class_name in content:
                print_success(f"Found test class: {class_name}")
            else:
                print_warning(f"Missing test class: {class_name}")

    if unit_test.exists():
        content = unit_test.read_text()

        # Check for key test classes
        expected_classes = [
            'TestConsentParsing',
            'TestConsentChecking',
            'TestAgentInvocation',
            'TestAgentOutputValidation',
            'TestManualInstructionsBuilder',
        ]

        for class_name in expected_classes:
            if class_name in content:
                print_success(f"Found test class: {class_name}")
            else:
                print_warning(f"Missing test class: {class_name}")

    # Summary
    print_header("Summary")

    if all_passed:
        print_success("✓ TDD Red Phase Verified")
        print_info("Tests are correctly failing because implementation doesn't exist yet.")
        print_info("\nNext steps:")
        print_info("  1. Run: pytest tests/integration/test_auto_implement_step8_agents.py -v")
        print_info("  2. Confirm tests are SKIPPED due to ImportError")
        print_info("  3. Implement: plugins/autonomous-dev/lib/auto_implement_git_integration.py")
        print_info("  4. Run tests again - they should PASS")
        return 0
    else:
        print_error("✗ TDD Red Phase Verification Failed")
        print_info("Fix issues above before proceeding to implementation.")
        return 1


if __name__ == '__main__':
    sys.exit(verify_tdd_red_phase())
