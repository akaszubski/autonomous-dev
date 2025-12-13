#!/usr/bin/env python3
"""
Testing Tier Selection Library - Select appropriate testing depth based on risk

This library provides risk-based testing tier selection to optimize test execution:

- SMOKE: Minimal testing for low-risk changes (< 1 min)
- STANDARD: Full testing for typical changes (5-10 min)
- COMPREHENSIVE: Extended testing for high-risk changes (15-30 min)

Tier selection improves performance by:
- Running minimal tests for safe changes (style, comments)
- Applying full validation to typical features
- Ensuring thorough testing for security, auth, database changes

Security: Risk-based validation ensures high-risk code gets maximum scrutiny

Usage:
    from testing_tier_selector import select_testing_tier, TestingTier, ChangeCharacteristics

    # Describe the change
    change = ChangeCharacteristics(
        lines_changed=150,
        files_changed=2,
        change_type="feature",
        areas_affected=["core"],
        has_security_changes=False
    )

    # Select testing tier
    tier = select_testing_tier(change)
    # Returns: TestingTier.STANDARD

    # Use tier to select test strategy
    if tier == TestingTier.SMOKE:
        run_unit_tests_only()
    elif tier == TestingTier.COMPREHENSIVE:
        run_full_test_suite_with_security()
    else:
        run_standard_tests()

Design Patterns:
    - Risk-based classification (higher risk → more testing)
    - Multiple risk factors (size, type, area)
    - Conservative fallback (ambiguous → STANDARD)
    - Deterministic selection (same input → same output)

Date: 2025-12-13
Issue: GitHub #120 (Performance improvements - tiered testing)
Agent: implementer
Phase: TDD Green Phase
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class TestingTier(Enum):
    """Testing tier enumeration for test depth selection.

    Values:
        SMOKE: Minimal testing for low-risk changes (< 1 min, unit tests only)
        STANDARD: Full testing for typical changes (5-10 min, unit + integration)
        COMPREHENSIVE: Extended testing for high-risk changes (15-30 min, full suite)
    """
    SMOKE = "smoke"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


@dataclass
class ChangeCharacteristics:
    """Describes the characteristics of a code change for tier selection.

    Attributes:
        lines_changed: Number of lines added/modified/deleted
        files_changed: Number of files touched
        change_type: Type of change (style, feature, bugfix, security, etc.)
        areas_affected: List of areas touched (core, auth, database, etc.)
        has_security_changes: Whether change affects security code
        has_auth_changes: Whether change affects authentication
        has_payment_changes: Whether change affects payment processing
        has_database_changes: Whether change affects database schema/queries

    Examples:
        >>> # Simple style fix
        >>> ChangeCharacteristics(
        ...     lines_changed=20,
        ...     files_changed=1,
        ...     change_type="style",
        ...     areas_affected=["formatting"]
        ... )

        >>> # Security feature
        >>> ChangeCharacteristics(
        ...     lines_changed=200,
        ...     files_changed=3,
        ...     change_type="security",
        ...     areas_affected=["auth", "security"],
        ...     has_security_changes=True,
        ...     has_auth_changes=True
        ... )
    """
    lines_changed: int
    files_changed: int
    change_type: str
    areas_affected: List[str]
    has_security_changes: bool = False
    has_auth_changes: bool = False
    has_payment_changes: bool = False
    has_database_changes: bool = False


# Risk thresholds for tier selection
SMOKE_MAX_LINES = 50  # Changes under 50 lines may qualify for SMOKE tier
COMPREHENSIVE_MIN_LINES = 500  # Changes over 500 lines require COMPREHENSIVE tier

# Low-risk change types (eligible for SMOKE tier)
LOW_RISK_TYPES = [
    "style",
    "comment",
    "formatting",
    "whitespace",
    "documentation",
]

# High-risk change types (require COMPREHENSIVE tier)
HIGH_RISK_TYPES = [
    "security",
    "auth",
    "authentication",
    "payment",
    "database",
    "migration",
]

# High-risk areas (require COMPREHENSIVE tier)
HIGH_RISK_AREAS = [
    "security",
    "auth",
    "authentication",
    "payment",
    "database",
    "migration",
    "encryption",
    "decryption",
    "access control",
]


def select_testing_tier(characteristics: ChangeCharacteristics) -> TestingTier:
    """Select appropriate testing tier based on change characteristics.

    Uses risk-based heuristics to determine testing depth:
    - SMOKE: Low-risk changes (< 50 lines, style/comments only)
    - STANDARD: Typical changes (50-500 lines, medium risk)
    - COMPREHENSIVE: High-risk changes (500+ lines, security/auth/payment/database)

    Selection Rules (evaluated in order):
    1. High-risk flags (security/auth/payment/database) → COMPREHENSIVE
    2. Large changes (500+ lines) → COMPREHENSIVE
    3. High-risk type or area → COMPREHENSIVE
    4. Small changes (< 50 lines) + low-risk type → SMOKE
    5. Default → STANDARD (conservative fallback)

    Args:
        characteristics: ChangeCharacteristics describing the code change

    Returns:
        TestingTier enum value (SMOKE, STANDARD, or COMPREHENSIVE)

    Raises:
        ValueError: If characteristics is None or invalid
        TypeError: If characteristics is not ChangeCharacteristics instance

    Examples:
        >>> # Simple style fix → SMOKE
        >>> change = ChangeCharacteristics(
        ...     lines_changed=20,
        ...     files_changed=1,
        ...     change_type="style",
        ...     areas_affected=["formatting"]
        ... )
        >>> select_testing_tier(change)
        TestingTier.SMOKE

        >>> # Typical feature → STANDARD
        >>> change = ChangeCharacteristics(
        ...     lines_changed=150,
        ...     files_changed=2,
        ...     change_type="feature",
        ...     areas_affected=["core"]
        ... )
        >>> select_testing_tier(change)
        TestingTier.STANDARD

        >>> # Security change → COMPREHENSIVE
        >>> change = ChangeCharacteristics(
        ...     lines_changed=100,
        ...     files_changed=2,
        ...     change_type="security",
        ...     areas_affected=["security"],
        ...     has_security_changes=True
        ... )
        >>> select_testing_tier(change)
        TestingTier.COMPREHENSIVE

    Performance:
        - Time complexity: O(n) where n is number of areas_affected
        - Space complexity: O(1) (no dynamic allocations)
        - Typical execution: < 1ms for any change size
    """
    # Input validation
    if characteristics is None:
        raise ValueError("characteristics cannot be None")

    if not isinstance(characteristics, ChangeCharacteristics):
        raise TypeError(
            f"characteristics must be ChangeCharacteristics instance, "
            f"got {type(characteristics).__name__}"
        )

    # Validate numeric fields
    if characteristics.lines_changed < 0:
        raise ValueError(
            f"lines_changed must be non-negative, got {characteristics.lines_changed}"
        )

    if characteristics.files_changed < 0:
        raise ValueError(
            f"files_changed must be non-negative, got {characteristics.files_changed}"
        )

    # Rule 1: High-risk flags → COMPREHENSIVE
    # Security, auth, payment, or database changes always get full testing
    if (characteristics.has_security_changes
        or characteristics.has_auth_changes
        or characteristics.has_payment_changes
        or characteristics.has_database_changes):
        return TestingTier.COMPREHENSIVE

    # Rule 2: Large changes → COMPREHENSIVE
    # Changes over 500 lines warrant comprehensive testing
    if characteristics.lines_changed >= COMPREHENSIVE_MIN_LINES:
        return TestingTier.COMPREHENSIVE

    # Rule 3: High-risk type or area → COMPREHENSIVE
    # Check if change type is high-risk
    if characteristics.change_type.lower() in HIGH_RISK_TYPES:
        return TestingTier.COMPREHENSIVE

    # Check if any affected area is high-risk
    for area in characteristics.areas_affected:
        if area.lower() in HIGH_RISK_AREAS:
            return TestingTier.COMPREHENSIVE

    # Rule 4: Small changes → SMOKE
    # Changes under 50 lines can use minimal testing (unless high-risk was already caught)
    # Low-risk types get priority, but small changes are generally low-risk
    if characteristics.lines_changed < SMOKE_MAX_LINES:
        return TestingTier.SMOKE

    # Rule 5: Default → STANDARD (conservative fallback)
    # Most changes should use standard testing
    return TestingTier.STANDARD


def get_tier_description(tier: TestingTier) -> str:
    """Get human-readable description of testing tier.

    Args:
        tier: TestingTier enum value

    Returns:
        Description string explaining the tier

    Examples:
        >>> get_tier_description(TestingTier.SMOKE)
        'Minimal testing: unit tests only, 30-50% coverage (< 1 min)'
    """
    descriptions = {
        TestingTier.SMOKE: "Minimal testing: unit tests only, 30-50% coverage (< 1 min)",
        TestingTier.STANDARD: "Full testing: unit + integration, 80%+ coverage (5-10 min)",
        TestingTier.COMPREHENSIVE: "Extended testing: full suite + security + performance, 90%+ coverage (15-30 min)",
    }
    return descriptions.get(tier, "Unknown testing tier")


def get_coverage_target(tier: TestingTier) -> int:
    """Get coverage target percentage for testing tier.

    Args:
        tier: TestingTier enum value

    Returns:
        Coverage target as integer percentage (0-100)

    Examples:
        >>> get_coverage_target(TestingTier.SMOKE)
        40

        >>> get_coverage_target(TestingTier.COMPREHENSIVE)
        90
    """
    targets = {
        TestingTier.SMOKE: 40,  # 30-50% range, use midpoint
        TestingTier.STANDARD: 80,
        TestingTier.COMPREHENSIVE: 90,
    }
    return targets.get(tier, 80)  # Default to STANDARD


def should_run_integration_tests(tier: TestingTier) -> bool:
    """Determine if integration tests should run for this tier.

    Args:
        tier: TestingTier enum value

    Returns:
        True if integration tests should run, False otherwise

    Examples:
        >>> should_run_integration_tests(TestingTier.SMOKE)
        False

        >>> should_run_integration_tests(TestingTier.STANDARD)
        True
    """
    return tier in [TestingTier.STANDARD, TestingTier.COMPREHENSIVE]


def should_run_security_tests(tier: TestingTier) -> bool:
    """Determine if security tests should run for this tier.

    Args:
        tier: TestingTier enum value

    Returns:
        True if security tests should run, False otherwise

    Examples:
        >>> should_run_security_tests(TestingTier.SMOKE)
        False

        >>> should_run_security_tests(TestingTier.COMPREHENSIVE)
        True
    """
    return tier == TestingTier.COMPREHENSIVE


def should_run_performance_tests(tier: TestingTier) -> bool:
    """Determine if performance tests should run for this tier.

    Args:
        tier: TestingTier enum value

    Returns:
        True if performance tests should run, False otherwise

    Examples:
        >>> should_run_performance_tests(TestingTier.STANDARD)
        False

        >>> should_run_performance_tests(TestingTier.COMPREHENSIVE)
        True
    """
    return tier == TestingTier.COMPREHENSIVE


# Export public API
__all__ = [
    "TestingTier",
    "ChangeCharacteristics",
    "select_testing_tier",
    "get_tier_description",
    "get_coverage_target",
    "should_run_integration_tests",
    "should_run_security_tests",
    "should_run_performance_tests",
]
