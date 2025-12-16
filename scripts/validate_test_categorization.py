#!/usr/bin/env python3
"""Validate test file categorization.

This script ensures all test files are properly categorized in the
correct directory structure for automatic marker application.

Test Tier Structure:
  tests/regression/smoke/      - Tier 0: Critical path validation (<5s each)
  tests/regression/regression/ - Tier 1: Feature protection (<30s each)
  tests/regression/extended/   - Tier 2: Deep validation (<5min each)
  tests/regression/progression/ - Tier 3: TDD red phase tests
  tests/unit/                  - Unit tests (isolated function tests)
  tests/integration/           - Integration tests (multi-component)
  tests/security/              - Security-focused tests
  tests/hooks/                 - Hook-specific tests

Usage:
  python scripts/validate_test_categorization.py
  python scripts/validate_test_categorization.py --strict  # Fail on uncategorized
  python scripts/validate_test_categorization.py --report  # Show distribution
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

# Valid test directories (tests in these get auto-marked)
VALID_CATEGORIES = [
    "regression/smoke",
    "regression/regression",
    "regression/extended",
    "regression/progression",
    "unit",
    "integration",
    "security",
    "hooks",
]

# Directories that should NOT contain test files
EXCLUDED_DIRS = [
    "archived",
    "fixtures",
    "helpers",
    "__pycache__",
]


def get_test_files(tests_dir: Path) -> list[Path]:
    """Find all test files in tests directory."""
    return sorted(tests_dir.glob("**/test_*.py"))


def categorize_test(test_path: Path, tests_dir: Path) -> str | None:
    """Determine which category a test file belongs to.

    Returns:
        Category name or None if uncategorized
    """
    relative = test_path.relative_to(tests_dir)
    rel_str = str(relative)

    for category in VALID_CATEGORIES:
        if rel_str.startswith(category):
            return category

    return None


def is_excluded(test_path: Path) -> bool:
    """Check if test is in an excluded directory."""
    parts = test_path.parts
    return any(excl in parts for excl in EXCLUDED_DIRS)


def validate_tests(tests_dir: Path, strict: bool = False) -> tuple[bool, dict]:
    """Validate all test files are properly categorized.

    Args:
        tests_dir: Path to tests directory
        strict: If True, fail on any uncategorized tests

    Returns:
        (success, stats) tuple
    """
    stats = {
        "total": 0,
        "categorized": 0,
        "uncategorized": 0,
        "excluded": 0,
        "by_category": defaultdict(int),
        "uncategorized_files": [],
    }

    test_files = get_test_files(tests_dir)

    for test_path in test_files:
        stats["total"] += 1

        if is_excluded(test_path):
            stats["excluded"] += 1
            continue

        category = categorize_test(test_path, tests_dir)

        if category:
            stats["categorized"] += 1
            stats["by_category"][category] += 1
        else:
            stats["uncategorized"] += 1
            stats["uncategorized_files"].append(test_path)

    # Success if no uncategorized (or not strict mode)
    success = stats["uncategorized"] == 0 or not strict

    return success, stats


def print_report(stats: dict, tests_dir: Path):
    """Print test categorization report."""
    print("=" * 60)
    print("TEST CATEGORIZATION REPORT")
    print("=" * 60)
    print()
    print(f"Total test files: {stats['total']}")
    print(f"  Categorized:    {stats['categorized']}")
    print(f"  Uncategorized:  {stats['uncategorized']}")
    print(f"  Excluded:       {stats['excluded']}")
    print()
    print("Distribution by category:")
    print("-" * 40)

    # Sort by tier (smoke first, then regression, etc.)
    tier_order = {
        "regression/smoke": 0,
        "regression/regression": 1,
        "regression/extended": 2,
        "regression/progression": 3,
        "unit": 4,
        "integration": 5,
        "security": 6,
        "hooks": 7,
    }

    categories = sorted(
        stats["by_category"].items(), key=lambda x: tier_order.get(x[0], 99)
    )

    for category, count in categories:
        pct = count / stats["categorized"] * 100 if stats["categorized"] else 0
        tier_name = category.replace("/", " / ")
        print(f"  {tier_name:30} {count:4} ({pct:5.1f}%)")

    if stats["uncategorized_files"]:
        print()
        print("UNCATEGORIZED FILES (need to be moved):")
        print("-" * 40)
        for f in stats["uncategorized_files"][:20]:  # Show max 20
            rel = f.relative_to(tests_dir)
            print(f"  {rel}")
        if len(stats["uncategorized_files"]) > 20:
            print(f"  ... and {len(stats['uncategorized_files']) - 20} more")

    print()


def print_guidance():
    """Print guidance for test categorization."""
    print("TEST CATEGORIZATION GUIDANCE")
    print("=" * 60)
    print("""
Where to put your tests:

REGRESSION TIERS (protect released features):
  tests/regression/smoke/      - CRITICAL PATH tests
                                 - Must pass for CI to proceed
                                 - < 5 seconds each
                                 - install.sh, /sync, plugin loading

  tests/regression/regression/ - FEATURE PROTECTION tests
                                 - Protect released features
                                 - < 30 seconds each
                                 - One test file per feature

  tests/regression/extended/   - DEEP VALIDATION tests
                                 - Performance baselines
                                 - < 5 minutes each
                                 - Run nightly, not every commit

  tests/regression/progression/ - TDD RED PHASE tests
                                 - Tests for features in development
                                 - Expected to fail until implemented

STANDARD CATEGORIES:
  tests/unit/                  - UNIT tests (single function/class)
  tests/integration/           - INTEGRATION tests (multi-component)
  tests/security/              - SECURITY-focused tests
  tests/hooks/                 - HOOK-specific tests

AUTOMATIC MARKERS:
  Files in these directories automatically get pytest markers applied.
  No need to manually add @pytest.mark decorators!

RUN SPECIFIC TIERS:
  pytest -m smoke              # Smoke tests only (CI gate)
  pytest -m regression         # Regression tests
  pytest -m "smoke or regression"
  pytest -m "not slow"         # Skip slow tests
""")


def main():
    parser = argparse.ArgumentParser(
        description="Validate test categorization"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any tests are uncategorized",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Show detailed distribution report",
    )
    parser.add_argument(
        "--guidance",
        action="store_true",
        help="Show categorization guidance",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=Path(__file__).parent.parent / "tests",
        help="Path to tests directory",
    )

    args = parser.parse_args()

    if args.guidance:
        print_guidance()
        return 0

    success, stats = validate_tests(args.tests_dir, args.strict)

    if args.report or not success:
        print_report(stats, args.tests_dir)

    if success:
        print("✅ Test categorization valid")
        if stats["uncategorized"] > 0:
            print(f"   ({stats['uncategorized']} uncategorized - use --strict to enforce)")
        return 0
    else:
        print("❌ Test categorization FAILED")
        print(f"   {stats['uncategorized']} uncategorized test files")
        print("   Run with --guidance for help")
        return 1


if __name__ == "__main__":
    sys.exit(main())
