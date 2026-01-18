#!/usr/bin/env python3
"""
Quality Persistence Enforcer - Central enforcement engine for quality gates in batch workflows.

Ensures quality gates persist across batch retries. System doesn't give up or fake success
when tests fail. Features are only marked as completed when they truly pass quality gates.

Key Features:
1. Completion gate enforcement (100% test pass requirement)
2. Retry strategy selection (different approaches per attempt)
3. Honest summary generation (shows skipped/failed features accurately)
4. Issue close decision logic (only close completed features)
5. Quality metrics tracking (test pass rate, coverage)

Quality Gate Rules:
- ALL tests must pass (not 80%, not "most" - 100%)
- Coverage must meet threshold (80%+)
- Retry attempts are limited (MAX_RETRY_ATTEMPTS)
- Failed features are clearly tracked (not hidden)

Retry Strategy Escalation:
- Attempt 1: Basic retry (same approach)
- Attempt 2: Fix tests first (focus on test failures)
- Attempt 3: Different implementation (try alternative approach)
- Beyond MAX_RETRY_ATTEMPTS: Stop (prevent infinite loops)

Usage:
    from quality_persistence_enforcer import (
        enforce_completion_gate,
        retry_with_different_approach,
        generate_honest_summary,
        should_close_issue,
    )

    # Check if feature passes quality gate
    test_results = {"total": 10, "passed": 10, "failed": 0, "coverage": 85.0}
    result = enforce_completion_gate(feature_index=0, test_results=test_results)

    if result.passed:
        print("Quality gate passed!")
    else:
        print(f"Quality gate failed: {result.reason}")

        # Get retry strategy
        strategy = retry_with_different_approach(0, attempt_number=1, "Tests failed")
        if strategy:
            print(f"Retry with: {strategy.description}")

    # Generate honest summary
    summary = generate_honest_summary(batch_state)
    print(f"Completed: {summary.completed_count}/{summary.total_features}")
    print(f"Failed: {summary.failed_count}")
    print(f"Skipped: {summary.skipped_count}")

Date: 2026-01-19
Issue: #254 (Quality Persistence: System gives up too easily)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
See state-management-patterns skill for state persistence patterns.
"""

import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional, List

# Import security utilities for audit logging
sys.path.insert(0, str(Path(__file__).parent))
from security_utils import audit_log  # type: ignore[import-not-found]

# Import batch state manager for state operations
try:
    from batch_state_manager import BatchState
except ImportError:
    # Fallback for tests
    class BatchState:
        pass


# =============================================================================
# CONSTANTS
# =============================================================================

# Maximum retry attempts per feature
MAX_RETRY_ATTEMPTS = 3

# Coverage threshold (80%)
COVERAGE_THRESHOLD = 80.0


# =============================================================================
# EXCEPTIONS
# =============================================================================


class QualityGateError(Exception):
    """Base exception for quality gate enforcement errors."""
    pass


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class EnforcementResult:
    """Result of completion gate enforcement.

    Attributes:
        passed: Whether the quality gate passed
        reason: Reason for pass/fail
        test_failures: Number of test failures
        coverage: Test coverage percentage
        attempt_number: Retry attempt number
    """
    passed: bool
    reason: str
    test_failures: int = 0
    coverage: float = 0.0
    attempt_number: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RetryStrategy:
    """Retry strategy for failed feature.

    Attributes:
        approach: Strategy approach identifier
        description: Human-readable strategy description
        attempt_number: Retry attempt number
    """
    approach: str
    description: str
    attempt_number: int


@dataclass
class CompletionSummary:
    """Honest summary of batch completion status.

    Attributes:
        total_features: Total number of features in batch
        completed_count: Number of successfully completed features
        failed_count: Number of failed features
        skipped_count: Number of skipped features (not attempted)
        completion_rate: Percentage of completed features
        quality_metrics: Dict mapping feature_index to quality metrics
    """
    total_features: int
    completed_count: int
    failed_count: int
    skipped_count: int
    completion_rate: float
    quality_metrics: Optional[Dict[int, Dict[str, Any]]] = None


# =============================================================================
# COMPLETION GATE ENFORCEMENT
# =============================================================================


def enforce_completion_gate(
    feature_index: int,
    test_results: Dict[str, Any],
    attempt_number: int = 1
) -> EnforcementResult:
    """
    Enforce completion gate for a feature.

    Quality Gate Requirements:
    - ALL tests must pass (100%, not 80%)
    - Coverage must meet threshold (80%+)
    - Attempt number must not exceed MAX_RETRY_ATTEMPTS

    Args:
        feature_index: Index of feature being checked
        test_results: Test results dict with keys:
            - total: Total number of tests
            - passed: Number of passed tests
            - failed: Number of failed tests
            - skipped: Number of skipped tests
            - coverage: Test coverage percentage
        attempt_number: Retry attempt number (default: 1)

    Returns:
        EnforcementResult with pass/fail status and reason

    Raises:
        QualityGateError: If attempt_number exceeds MAX_RETRY_ATTEMPTS
        QualityGateError: If test_results format is invalid

    Examples:
        >>> test_results = {"total": 10, "passed": 10, "failed": 0, "coverage": 85.0}
        >>> result = enforce_completion_gate(0, test_results)
        >>> result.passed
        True
        >>> result.reason
        'all_tests_passed'
    """
    # Validate attempt number
    if attempt_number > MAX_RETRY_ATTEMPTS:
        raise QualityGateError(
            f"Max retry attempts exceeded: {attempt_number} > {MAX_RETRY_ATTEMPTS}"
        )

    # Validate test results format
    required_keys = ['total', 'passed', 'failed', 'skipped', 'coverage']
    missing_keys = [key for key in required_keys if key not in test_results]
    if missing_keys:
        raise QualityGateError(
            f"Invalid test results format: missing keys {missing_keys}"
        )

    # Extract test metrics
    total = test_results['total']
    passed = test_results['passed']
    failed = test_results['failed']
    coverage = test_results['coverage']

    # Quality Gate 1: ALL tests must pass (100%)
    if failed > 0:
        result = EnforcementResult(
            passed=False,
            reason="test_failures",
            test_failures=failed,
            coverage=coverage,
            attempt_number=attempt_number
        )

        # Audit log
        audit_log(
            "quality_gate_enforced",
            "failed",
            {
                "feature_index": feature_index,
                "reason": "test_failures",
                "test_failures": failed,
                "coverage": coverage,
                "attempt_number": attempt_number,
            }
        )

        return result

    # Quality Gate 2: Coverage must meet threshold (80%+)
    if coverage < COVERAGE_THRESHOLD:
        result = EnforcementResult(
            passed=False,
            reason="low_coverage",
            test_failures=0,
            coverage=coverage,
            attempt_number=attempt_number
        )

        # Audit log
        audit_log(
            "quality_gate_enforced",
            "failed",
            {
                "feature_index": feature_index,
                "reason": "low_coverage",
                "coverage": coverage,
                "threshold": COVERAGE_THRESHOLD,
                "attempt_number": attempt_number,
            }
        )

        return result

    # All quality gates passed
    result = EnforcementResult(
        passed=True,
        reason="all_tests_passed",
        test_failures=0,
        coverage=coverage,
        attempt_number=attempt_number
    )

    # Audit log
    audit_log(
        "quality_gate_enforced",
        "success",
        {
            "feature_index": feature_index,
            "reason": "all_tests_passed",
            "coverage": coverage,
            "attempt_number": attempt_number,
        }
    )

    return result


# =============================================================================
# RETRY STRATEGY SELECTION
# =============================================================================


def retry_with_different_approach(
    feature_index: int,
    attempt_number: int,
    previous_error: str
) -> Optional[RetryStrategy]:
    """
    Select retry strategy based on attempt number.

    Retry Strategy Escalation:
    - Attempt 1: Basic retry (same approach)
    - Attempt 2: Fix tests first (focus on test failures)
    - Attempt 3: Different implementation (try alternative approach)
    - Beyond MAX_RETRY_ATTEMPTS: None (stop retrying)

    Args:
        feature_index: Index of feature to retry
        attempt_number: Retry attempt number (1-based)
        previous_error: Error message from previous attempt

    Returns:
        RetryStrategy for this attempt, or None if max attempts exceeded

    Examples:
        >>> strategy = retry_with_different_approach(0, 1, "Tests failed")
        >>> strategy.approach
        'basic_retry'
        >>> strategy = retry_with_different_approach(0, 2, "Tests failed")
        >>> strategy.approach
        'fix_tests_first'
    """
    # Check if max attempts exceeded
    if attempt_number > MAX_RETRY_ATTEMPTS:
        return None

    # Attempt 1: Basic retry (same approach)
    if attempt_number == 1:
        return RetryStrategy(
            approach="basic_retry",
            description="Retry with same approach",
            attempt_number=attempt_number
        )

    # Attempt 2: Fix tests first
    elif attempt_number == 2:
        return RetryStrategy(
            approach="fix_tests_first",
            description="Fix failing tests before retrying implementation",
            attempt_number=attempt_number
        )

    # Attempt 3: Different implementation approach
    elif attempt_number == 3:
        return RetryStrategy(
            approach="different_implementation",
            description="Try a different approach to implementation",
            attempt_number=attempt_number
        )

    # Beyond MAX_RETRY_ATTEMPTS: stop
    return None


# =============================================================================
# HONEST SUMMARY GENERATION
# =============================================================================


def generate_honest_summary(state: BatchState) -> CompletionSummary:
    """
    Generate honest summary of batch completion status.

    Does NOT hide or misrepresent failures. Shows exact counts of:
    - Completed features (quality gates passed)
    - Failed features (quality gates failed)
    - Skipped features (not attempted)

    Args:
        state: Batch state containing completion tracking

    Returns:
        CompletionSummary with accurate status breakdown

    Examples:
        >>> state = create_batch_state(features=["F1", "F2", "F3"])
        >>> state.completed_features = [0]
        >>> state.failed_features = [{"feature_index": 1, "error_message": "Tests failed"}]
        >>> summary = generate_honest_summary(state)
        >>> summary.completed_count
        1
        >>> summary.failed_count
        1
        >>> summary.skipped_count
        1
    """
    total_features = state.total_features

    # Calculate completed count
    completed_indices = set(state.completed_features)
    completed_count = len(completed_indices)

    # Calculate failed count
    failed_indices = {f["feature_index"] for f in state.failed_features}
    failed_count = len(failed_indices)

    # Calculate skipped count (features neither completed nor failed)
    all_indices = set(range(total_features))
    skipped_indices = all_indices - completed_indices - failed_indices
    skipped_count = len(skipped_indices)

    # Calculate completion rate (percentage of completed features)
    completion_rate = (completed_count / total_features * 100) if total_features > 0 else 0.0

    # Extract quality metrics if available
    quality_metrics = None
    if hasattr(state, 'quality_metrics') and state.quality_metrics:
        quality_metrics = state.quality_metrics

    return CompletionSummary(
        total_features=total_features,
        completed_count=completed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        completion_rate=completion_rate,
        quality_metrics=quality_metrics
    )


# =============================================================================
# ISSUE CLOSE DECISION LOGIC
# =============================================================================


def should_close_issue(feature_status: Dict[str, Any]) -> bool:
    """
    Decide if issue should be closed based on feature status.

    Only closes issue if:
    - Feature is completed (not failed or skipped)
    - Quality gate passed

    Args:
        feature_status: Dict with keys:
            - completed: bool - Whether feature is completed
            - failed: bool - Whether feature failed
            - skipped: bool - Whether feature was skipped
            - quality_gate_passed: bool - Whether quality gate passed

    Returns:
        True if issue should be closed, False otherwise

    Examples:
        >>> status = {"completed": True, "failed": False, "skipped": False, "quality_gate_passed": True}
        >>> should_close_issue(status)
        True
        >>> status = {"completed": False, "failed": True, "skipped": False, "quality_gate_passed": False}
        >>> should_close_issue(status)
        False
    """
    # Only close if feature is completed AND quality gate passed
    if feature_status.get("completed") and feature_status.get("quality_gate_passed"):
        return True

    # Don't close if failed or skipped
    return False


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "enforce_completion_gate",
    "retry_with_different_approach",
    "generate_honest_summary",
    "should_close_issue",
    "EnforcementResult",
    "RetryStrategy",
    "CompletionSummary",
    "QualityGateError",
    "MAX_RETRY_ATTEMPTS",
    "COVERAGE_THRESHOLD",
]
