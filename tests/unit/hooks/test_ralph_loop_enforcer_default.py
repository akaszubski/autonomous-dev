#!/usr/bin/env python3
"""
Unit Tests for Ralph Loop Enforcer Default Behavior (Issue #256)

Tests is_ralph_loop_enabled() behavior with opt-out pattern:
- Default enabled (no env vars → True)
- Opt-out via RALPH_LOOP_DISABLED=true
- Backward compatibility with RALPH_LOOP_ENABLED
- Priority rules when both env vars set

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially

Date: 2026-01-19
Issue: #256 (Enable Ralph Loop by default and fix skipped feature tracking)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# Add hooks directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "hooks"))

# Import will succeed - module exists, but behavior will change
try:
    from ralph_loop_enforcer import is_ralph_loop_enabled
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before each test."""
    # Save original values
    original_enabled = os.environ.get("RALPH_LOOP_ENABLED")
    original_disabled = os.environ.get("RALPH_LOOP_DISABLED")

    # Clear both env vars
    os.environ.pop("RALPH_LOOP_ENABLED", None)
    os.environ.pop("RALPH_LOOP_DISABLED", None)

    yield

    # Restore original values
    if original_enabled is not None:
        os.environ["RALPH_LOOP_ENABLED"] = original_enabled
    else:
        os.environ.pop("RALPH_LOOP_ENABLED", None)

    if original_disabled is not None:
        os.environ["RALPH_LOOP_DISABLED"] = original_disabled
    else:
        os.environ.pop("RALPH_LOOP_DISABLED", None)


# =============================================================================
# SECTION 1: Default Enabled Behavior (1 test)
# =============================================================================

class TestDefaultEnabledBehavior:
    """Test that Ralph Loop is enabled by default (opt-out pattern)."""

    def test_ralph_loop_enabled_by_default(self):
        """Test that Ralph Loop is enabled by default when no env vars set.

        CHANGE: Previously returned False (opt-in), now returns True (opt-out).
        This is the core behavior change for Issue #256.
        """
        # Arrange - no environment variables set (clean_env fixture)
        assert "RALPH_LOOP_ENABLED" not in os.environ
        assert "RALPH_LOOP_DISABLED" not in os.environ

        # Act
        result = is_ralph_loop_enabled()

        # Assert - should be enabled by default
        assert result is True, (
            "Ralph Loop should be ENABLED by default (opt-out pattern). "
            "If no env vars are set, return True."
        )


# =============================================================================
# SECTION 2: Opt-Out via RALPH_LOOP_DISABLED (4 tests)
# =============================================================================

class TestOptOutBehavior:
    """Test opt-out behavior via RALPH_LOOP_DISABLED environment variable."""

    def test_ralph_loop_disabled_via_disabled_var_true(self):
        """Test that RALPH_LOOP_DISABLED=true disables Ralph Loop."""
        # Arrange
        os.environ["RALPH_LOOP_DISABLED"] = "true"

        # Act
        result = is_ralph_loop_enabled()

        # Assert
        assert result is False, (
            "RALPH_LOOP_DISABLED=true should DISABLE Ralph Loop"
        )

    def test_ralph_loop_disabled_via_disabled_var_case_insensitive(self):
        """Test that RALPH_LOOP_DISABLED is case-insensitive."""
        # Test various case combinations
        test_cases = ["true", "True", "TRUE", "TrUe"]

        for value in test_cases:
            # Arrange
            os.environ["RALPH_LOOP_DISABLED"] = value

            # Act
            result = is_ralph_loop_enabled()

            # Assert
            assert result is False, (
                f"RALPH_LOOP_DISABLED={value} should DISABLE Ralph Loop (case-insensitive)"
            )

    def test_ralph_loop_enabled_when_disabled_var_false(self):
        """Test that RALPH_LOOP_DISABLED=false keeps Ralph Loop enabled."""
        # Arrange
        os.environ["RALPH_LOOP_DISABLED"] = "false"

        # Act
        result = is_ralph_loop_enabled()

        # Assert - should be enabled (disabled=false means enabled)
        assert result is True, (
            "RALPH_LOOP_DISABLED=false should keep Ralph Loop ENABLED"
        )

    def test_ralph_loop_enabled_when_disabled_var_empty(self):
        """Test that RALPH_LOOP_DISABLED='' (empty) keeps Ralph Loop enabled."""
        # Arrange
        os.environ["RALPH_LOOP_DISABLED"] = ""

        # Act
        result = is_ralph_loop_enabled()

        # Assert - should be enabled (empty is not 'true')
        assert result is True, (
            "RALPH_LOOP_DISABLED='' (empty) should keep Ralph Loop ENABLED"
        )


# =============================================================================
# SECTION 3: Backward Compatibility with RALPH_LOOP_ENABLED (3 tests)
# =============================================================================

class TestBackwardCompatibility:
    """Test backward compatibility with RALPH_LOOP_ENABLED environment variable."""

    def test_ralph_loop_disabled_via_enabled_var_false(self):
        """Test that RALPH_LOOP_ENABLED=false disables Ralph Loop (backward compat)."""
        # Arrange
        os.environ["RALPH_LOOP_ENABLED"] = "false"

        # Act
        result = is_ralph_loop_enabled()

        # Assert
        assert result is False, (
            "RALPH_LOOP_ENABLED=false should DISABLE Ralph Loop (backward compatibility)"
        )

    def test_ralph_loop_enabled_via_enabled_var_true(self):
        """Test that RALPH_LOOP_ENABLED=true enables Ralph Loop (backward compat)."""
        # Arrange
        os.environ["RALPH_LOOP_ENABLED"] = "true"

        # Act
        result = is_ralph_loop_enabled()

        # Assert
        assert result is True, (
            "RALPH_LOOP_ENABLED=true should ENABLE Ralph Loop (backward compatibility)"
        )

    def test_ralph_loop_enabled_var_case_insensitive(self):
        """Test that RALPH_LOOP_ENABLED is case-insensitive (backward compat)."""
        # Test case variations
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
        ]

        for value, expected in test_cases:
            # Arrange
            os.environ["RALPH_LOOP_ENABLED"] = value

            # Act
            result = is_ralph_loop_enabled()

            # Assert
            assert result is expected, (
                f"RALPH_LOOP_ENABLED={value} should return {expected} (case-insensitive)"
            )


# =============================================================================
# SECTION 4: Priority Rules When Both Env Vars Set (2 tests)
# =============================================================================

class TestPriorityRules:
    """Test priority rules when both RALPH_LOOP_ENABLED and RALPH_LOOP_DISABLED are set."""

    def test_disabled_takes_precedence_over_enabled_true(self):
        """Test that RALPH_LOOP_DISABLED takes precedence over RALPH_LOOP_ENABLED.

        DISABLED=true + ENABLED=true → DISABLED wins (False)
        """
        # Arrange
        os.environ["RALPH_LOOP_DISABLED"] = "true"
        os.environ["RALPH_LOOP_ENABLED"] = "true"

        # Act
        result = is_ralph_loop_enabled()

        # Assert - DISABLED wins
        assert result is False, (
            "When both set, RALPH_LOOP_DISABLED should take precedence. "
            "DISABLED=true + ENABLED=true → return False"
        )

    def test_disabled_false_defers_to_enabled(self):
        """Test that RALPH_LOOP_DISABLED=false defers to RALPH_LOOP_ENABLED.

        DISABLED=false + ENABLED=false → ENABLED determines outcome (False)
        DISABLED=false + ENABLED=true → ENABLED determines outcome (True)
        """
        # Test case 1: DISABLED=false, ENABLED=false → False
        os.environ["RALPH_LOOP_DISABLED"] = "false"
        os.environ["RALPH_LOOP_ENABLED"] = "false"
        result = is_ralph_loop_enabled()
        assert result is False, (
            "DISABLED=false + ENABLED=false → return False (ENABLED wins)"
        )

        # Test case 2: DISABLED=false, ENABLED=true → True
        os.environ["RALPH_LOOP_DISABLED"] = "false"
        os.environ["RALPH_LOOP_ENABLED"] = "true"
        result = is_ralph_loop_enabled()
        assert result is True, (
            "DISABLED=false + ENABLED=true → return True (ENABLED wins)"
        )


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (10 unit tests for ralph_loop_enforcer.py - is_ralph_loop_enabled()):

SECTION 1: Default Enabled Behavior (1 test)
✗ test_ralph_loop_enabled_by_default

SECTION 2: Opt-Out via RALPH_LOOP_DISABLED (4 tests)
✗ test_ralph_loop_disabled_via_disabled_var_true
✗ test_ralph_loop_disabled_via_disabled_var_case_insensitive
✗ test_ralph_loop_enabled_when_disabled_var_false
✗ test_ralph_loop_enabled_when_disabled_var_empty

SECTION 3: Backward Compatibility with RALPH_LOOP_ENABLED (3 tests)
✗ test_ralph_loop_disabled_via_enabled_var_false
✗ test_ralph_loop_enabled_via_enabled_var_true
✗ test_ralph_loop_enabled_var_case_insensitive

SECTION 4: Priority Rules When Both Env Vars Set (2 tests)
✗ test_disabled_takes_precedence_over_enabled_true
✗ test_disabled_false_defers_to_enabled

Expected Status: TESTS WILL FAIL (RED phase - behavior change not implemented yet)
Current Behavior: is_ralph_loop_enabled() returns False by default (opt-in)
Target Behavior: is_ralph_loop_enabled() returns True by default (opt-out)

Implementation Requirements:
1. Change default return from False to True (no env vars → enabled)
2. Add RALPH_LOOP_DISABLED env var check (true → disabled)
3. Maintain RALPH_LOOP_ENABLED backward compatibility
4. RALPH_LOOP_DISABLED takes precedence when both set
5. Both env vars are case-insensitive

Coverage Target: 100% for is_ralph_loop_enabled() function
"""
