#!/usr/bin/env python3
"""
TDD Tests for CLI Exception Handling in PR Automation

Tests verify that int() conversions handle edge cases gracefully:
- Non-numeric issue numbers
- Float issue numbers
- Very large numbers
- Negative numbers
- Empty strings

These tests follow TDD principles - written before implementation fixes.
Target: 80%+ coverage of exception handling paths.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.autonomous_dev.lib.pr_automation import parse_commit_messages_for_issues


def test_handles_non_numeric_issue_numbers():
    """Test handling of non-numeric issue numbers."""
    print("TEST: test_handles_non_numeric_issue_numbers")

    test_cases = [
        ("Fix bug #abc", []),  # Non-numeric
        ("Resolve #xyz123", []),  # Non-numeric
        ("Fix issue #ONE", []),  # Word
    ]

    for message, expected in test_cases:
        try:
            result = extract_issue_numbers([message])

            # Should handle gracefully - either return empty or valid integers
            assert isinstance(result, list), f"Should return list for: {message}"

            for num in result:
                assert isinstance(num, int), f"Should only contain integers for: {message}"

            print(f"  ✓ Handled: {message} → {result}")

        except ValueError as e:
            print(f"  ✗ FAIL: ValueError raised for '{message}': {e}")
            print(f"     Should handle gracefully instead of crashing")
            return "FAIL"
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected exception for '{message}': {type(e).__name__}: {e}")
            return "FAIL"

    print("  PASS: All non-numeric cases handled gracefully")
    return "PASS"


def test_handles_float_issue_numbers():
    """Test handling of float-like issue numbers."""
    print("\nTEST: test_handles_float_issue_numbers")

    test_cases = [
        "Fix #42.5",
        "Resolve #123.456",
        "Close #1.0",
    ]

    for message in test_cases:
        try:
            result = extract_issue_numbers([message])

            # Should handle gracefully
            assert isinstance(result, list)

            for num in result:
                assert isinstance(num, int), "Should only return integers"
                assert num > 0, "Should only return positive integers"

            print(f"  ✓ Handled: {message} → {result}")

        except ValueError as e:
            print(f"  ✗ FAIL: ValueError for '{message}': {e}")
            return "FAIL"
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected exception: {type(e).__name__}: {e}")
            return "FAIL"

    print("  PASS: Float-like numbers handled gracefully")
    return "PASS"


def test_handles_very_large_issue_numbers():
    """Test handling of extremely large issue numbers."""
    print("\nTEST: test_handles_very_large_issue_numbers")

    test_cases = [
        f"Fix #{2**31}",  # Max 32-bit int
        f"Fix #{2**63}",  # Max 64-bit int
        f"Fix #{10**20}",  # Very large
    ]

    for message in test_cases:
        try:
            result = extract_issue_numbers([message])

            assert isinstance(result, list)
            print(f"  ✓ Handled: {message[:20]}... → {result}")

        except (ValueError, OverflowError) as e:
            print(f"  ✗ FAIL: Should handle large numbers: {e}")
            return "FAIL"
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected exception: {type(e).__name__}: {e}")
            return "FAIL"

    print("  PASS: Large numbers handled")
    return "PASS"


def test_handles_negative_issue_numbers():
    """Test handling of negative issue numbers (invalid but shouldn't crash)."""
    print("\nTEST: test_handles_negative_issue_numbers")

    test_cases = [
        ("Fix #-42", []),  # Should be filtered out
        ("Resolve #-1", []),
        ("Close #-999", []),
    ]

    for message, expected_behavior in test_cases:
        try:
            result = extract_issue_numbers([message])

            assert isinstance(result, list)

            # Negative numbers should be filtered out
            for num in result:
                assert isinstance(num, int)
                assert num > 0, f"Should only return positive numbers, got {num} from '{message}'"

            print(f"  ✓ Handled: {message} → {result} (negatives filtered)")

        except Exception as e:
            print(f"  ✗ FAIL: Exception for '{message}': {type(e).__name__}: {e}")
            return "FAIL"

    print("  PASS: Negative numbers handled/filtered")
    return "PASS"


def test_handles_empty_issue_references():
    """Test handling of empty # references."""
    print("\nTEST: test_handles_empty_issue_references")

    test_cases = [
        "Fix #",  # Just hash, no number
        "Resolve ##",  # Double hash
        "Close # ",  # Hash with space
    ]

    for message in test_cases:
        try:
            result = extract_issue_numbers([message])

            assert isinstance(result, list)
            print(f"  ✓ Handled: '{message}' → {result}")

        except Exception as e:
            print(f"  ✗ FAIL: Exception for '{message}': {type(e).__name__}: {e}")
            return "FAIL"

    print("  PASS: Empty references handled")
    return "PASS"


def test_handles_mixed_valid_and_invalid():
    """Test handling of messages with both valid and invalid issue refs."""
    print("\nTEST: test_handles_mixed_valid_and_invalid")

    test_cases = [
        ("Fix #123 and #abc", [123]),  # One valid, one invalid
        ("Resolve #42, #xyz, #99", [42, 99]),  # Multiple mixed
        ("Close #1.5 and #2", [2]),  # Float and valid
    ]

    for message, expected_valid in test_cases:
        try:
            result = extract_issue_numbers([message])

            assert isinstance(result, list)

            # Check that valid numbers were extracted
            for expected in expected_valid:
                if expected not in result:
                    print(f"  ✗ FAIL: Expected {expected} in result for '{message}'")
                    return "FAIL"

            print(f"  ✓ Handled: {message} → {result}")

        except Exception as e:
            print(f"  ✗ FAIL: Exception for '{message}': {type(e).__name__}: {e}")
            return "FAIL"

    print("  PASS: Mixed valid/invalid handled correctly")
    return "PASS"


def test_handles_edge_case_formats():
    """Test handling of edge case issue reference formats."""
    print("\nTEST: test_handles_edge_case_formats")

    test_cases = [
        "Fix #0",  # Zero (invalid)
        "Fix #00042",  # Leading zeros
        "Fix #1e5",  # Scientific notation
        "Fix #0x42",  # Hex notation
    ]

    for message in test_cases:
        try:
            result = extract_issue_numbers([message])

            assert isinstance(result, list)
            print(f"  ✓ Handled: '{message}' → {result}")

        except Exception as e:
            print(f"  ✗ FAIL: Exception for '{message}': {type(e).__name__}: {e}")
            return "FAIL"

    print("  PASS: Edge case formats handled")
    return "PASS"


def main():
    """Run all CLI exception handling tests."""
    print("=" * 70)
    print("CLI EXCEPTION HANDLING TESTS (TDD)")
    print("=" * 70)
    print()
    print("Testing int() conversion error handling in pr_automation.py")
    print()

    results = []

    # Run tests
    results.append(("Non-numeric", test_handles_non_numeric_issue_numbers()))
    results.append(("Float numbers", test_handles_float_issue_numbers()))
    results.append(("Large numbers", test_handles_very_large_issue_numbers()))
    results.append(("Negative numbers", test_handles_negative_issue_numbers()))
    results.append(("Empty references", test_handles_empty_issue_references()))
    results.append(("Mixed valid/invalid", test_handles_mixed_valid_and_invalid()))
    results.append(("Edge cases", test_handles_edge_case_formats()))

    # Summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passes = sum(1 for _, r in results if r == "PASS")
    fails = sum(1 for _, r in results if r == "FAIL")

    for name, result in results:
        status = "✓" if result == "PASS" else "✗"
        print(f"{status} {name}: {result}")

    print()
    print(f"PASS: {passes}/{len(results)}")
    print(f"FAIL: {fails}/{len(results)}")

    if fails > 0:
        print()
        print("⚠️  Failures indicate missing error handling for int() conversions")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
