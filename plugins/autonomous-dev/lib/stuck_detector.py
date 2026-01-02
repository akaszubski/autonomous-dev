#!/usr/bin/env python3
"""
Stuck Detector - Detect infinite healing loops from repeated identical errors.

Detects when the self-healing loop is stuck (same error repeating) to prevent
infinite iteration. Triggers circuit breaker after threshold consecutive identical errors.

Key Features:
1. Error signature computation (normalized for comparison)
2. Consecutive error tracking
3. Configurable stuck threshold (default: 3)
4. Reset on successful test run
5. Thread-safe operation

Stuck Detection Logic:
    1. Compute error signature (file + line + error type)
    2. Compare with previous errors
    3. If same signature appears N times consecutively → STUCK
    4. Otherwise → continue healing

Usage:
    from stuck_detector import (
        StuckDetector,
        is_stuck,
        reset_stuck_detection,
        DEFAULT_STUCK_THRESHOLD,
    )

    # Create detector
    detector = StuckDetector(threshold=3)

    # Record errors
    detector.record_error("SyntaxError at test.py:10")
    detector.record_error("SyntaxError at test.py:10")
    detector.record_error("SyntaxError at test.py:10")

    # Check if stuck
    if detector.is_stuck():
        print("Circuit breaker triggered!")

    # Reset after successful iteration
    detector.reset()

Security:
- No code execution
- Bounded memory (only stores recent error signatures)
- Thread-safe with locks

Date: 2026-01-02
Issue: #184 (Self-healing QA loop with automatic test fix iterations)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
"""

import hashlib
import threading
from typing import List, Optional


# =============================================================================
# Constants
# =============================================================================

# Default stuck threshold (3 consecutive identical errors)
DEFAULT_STUCK_THRESHOLD = 3


# =============================================================================
# Stuck Detector Class
# =============================================================================

class StuckDetector:
    """Detect stuck healing loops via repeated identical errors."""

    def __init__(self, threshold: int = DEFAULT_STUCK_THRESHOLD):
        """
        Initialize stuck detector.

        Args:
            threshold: Number of consecutive identical errors before stuck (default: 3)
        """
        self.threshold = threshold
        self.error_history: List[str] = []
        self._lock = threading.Lock()

    def record_error(self, error_signature: str) -> None:
        """
        Record an error signature for stuck detection.

        Args:
            error_signature: Normalized error signature (file + line + type)
        """
        with self._lock:
            self.error_history.append(error_signature)

            # Keep only last N errors (prevent unbounded growth)
            max_history = max(self.threshold * 2, 10)
            if len(self.error_history) > max_history:
                self.error_history = self.error_history[-max_history:]

    def is_stuck(self) -> bool:
        """
        Check if healing loop is stuck (threshold consecutive identical errors).

        Returns:
            True if stuck, False otherwise
        """
        with self._lock:
            # Need at least threshold errors
            if len(self.error_history) < self.threshold:
                return False

            # Check if last N errors are identical
            recent_errors = self.error_history[-self.threshold:]
            first_error = recent_errors[0]

            # All must match
            return all(error == first_error for error in recent_errors)

    def reset(self) -> None:
        """Reset stuck detector (clear error history)."""
        with self._lock:
            self.error_history = []

    def compute_error_signature(self, failures: List) -> str:
        """
        Compute normalized error signature from failure list.

        Args:
            failures: List of FailureAnalysis objects

        Returns:
            Normalized error signature for comparison
        """
        if not failures:
            return ""

        # Sort failures for consistent signature
        sorted_failures = sorted(
            failures,
            key=lambda f: (f.file_path, f.line_number, f.error_type)
        )

        # Build signature from file + line + error type
        signature_parts = []
        for failure in sorted_failures:
            part = f"{failure.file_path}:{failure.line_number}:{failure.error_type}"
            signature_parts.append(part)

        # Join and hash for consistent signature
        signature_str = "|".join(signature_parts)
        return hashlib.sha256(signature_str.encode()).hexdigest()[:16]


# =============================================================================
# Standalone Functions (for convenience)
# =============================================================================

# Global detector instance for convenience functions
_global_detector = StuckDetector()


def is_stuck() -> bool:
    """
    Check if global stuck detector is stuck (convenience function).

    Returns:
        True if stuck, False otherwise
    """
    return _global_detector.is_stuck()


def reset_stuck_detection() -> None:
    """Reset global stuck detector (convenience function)."""
    _global_detector.reset()
