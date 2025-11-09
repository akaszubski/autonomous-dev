#!/usr/bin/env python3
"""
Verification Script - Auto Git Workflow TDD Red Phase

Verifies that all tests for automatic git operations integration are properly
failing (TDD red phase) before implementation begins.

Date: 2025-11-09
Feature: Automatic git operations integration
Agent: test-master
Phase: TDD Red Verification
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> tuple[int, str, str]:
    """Run a shell command and capture output."""
    print(f"\n{'='*70}")
    print(f"Testing: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*70}")

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode, result.stdout, result.stderr


def main():
    """Run verification tests."""
    print("="*70)
    print("Auto Git Workflow - TDD Red Phase Verification")
    print("="*70)

    tests = [
        (
            "source test_venv/bin/activate && python -m pytest tests/unit/hooks/test_auto_git_workflow.py -v --tb=no",
            "Hook Unit Tests (44 tests) - Should be SKIPPED (module doesn't exist)"
        ),
        (
            "source test_venv/bin/activate && python -m pytest tests/unit/test_auto_implement_git_integration.py::TestSecurityValidation -v --tb=no",
            "Security Validation Tests (23 tests) - Should FAIL (functions don't exist)"
        ),
        (
            "source test_venv/bin/activate && python -m pytest tests/integration/test_auto_implement_git_end_to_end.py -v --tb=no",
            "Integration Tests (21 tests) - Should be SKIPPED (module doesn't exist)"
        ),
    ]

    results = []

    for cmd, description in tests:
        returncode, stdout, stderr = run_command(cmd, description)
        results.append((description, returncode, stdout, stderr))

    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    all_correct = True

    for description, returncode, stdout, stderr in results:
        # Check for expected failure patterns
        # pytest exit codes: 0=pass, 1=fail, 5=no tests collected/skipped
        is_skipped = "skipped" in stdout.lower() and returncode == 5
        is_failed = "failed" in stdout.lower() and returncode == 1
        has_importerror = "ImportError" in stdout or "ImportError" in stderr

        # Hook and integration tests should be skipped (module doesn't exist)
        # Security tests should fail (functions don't exist)
        expected_state = None
        if "Hook Unit Tests" in description or "Integration Tests" in description:
            # Skipped tests are indicated by "1 skipped" and exit code 5
            expected_state = is_skipped
            status = "✅ PASS" if expected_state else "❌ FAIL"
            reason = "Skipped (module doesn't exist - TDD red)" if expected_state else f"Not skipped (exit code: {returncode})"
        elif "Security Validation" in description:
            # Failed tests are indicated by "X failed" and ImportError
            expected_state = is_failed and has_importerror
            status = "✅ PASS" if expected_state else "❌ FAIL"
            reason = "Failed due to ImportError (TDD red)" if expected_state else f"Not failed or wrong error (exit code: {returncode})"

        print(f"\n{status} - {description}")
        print(f"   Reason: {reason}")
        if has_importerror and not expected_state:
            print(f"   Note: ImportError detected but wrong test state")

        if not expected_state:
            all_correct = False

    print("\n" + "="*70)
    if all_correct:
        print("✅ TDD RED PHASE VERIFIED - All tests failing as expected")
        print("   Ready for implementation (TDD green phase)")
        print("="*70)
        return 0
    else:
        print("❌ TDD RED PHASE VERIFICATION FAILED")
        print("   Some tests not in expected failing state")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
