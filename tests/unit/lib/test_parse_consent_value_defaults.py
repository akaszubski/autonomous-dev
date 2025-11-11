#!/usr/bin/env python3
"""
Unit tests for parse_consent_value() default behavior changes (TDD Red Phase).

Tests for Issue #61: parse_consent_value() should default to True when env var is None.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially because parse_consent_value() currently defaults to False.

Test Strategy:
- Test None defaults to True (NEW BEHAVIOR)
- Test custom default parameter
- Test empty string uses default
- Test explicit false overrides default
- Test backward compatibility

Date: 2025-11-11
Issue: #61 (Enable Zero Manual Git Operations by Default)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import existing function - tests will FAIL until changes implemented
try:
    from auto_implement_git_integration import parse_consent_value
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


class TestParseConsentValueDefaults:
    """Test parse_consent_value() with new default behavior."""

    def test_parse_consent_value_none_defaults_to_true(self):
        """Test parse_consent_value(None) returns True (NEW BEHAVIOR - Issue #61)."""
        # CRITICAL: This test will FAIL until implementation changes
        # Current behavior: parse_consent_value(None) returns False
        # Expected behavior: parse_consent_value(None) returns True
        assert parse_consent_value(None) is True

    def test_parse_consent_value_empty_string_defaults_to_true(self):
        """Test parse_consent_value('') returns True (NEW BEHAVIOR - Issue #61)."""
        # CRITICAL: This test will FAIL until implementation changes
        # Current behavior: parse_consent_value('') returns False
        # Expected behavior: parse_consent_value('') returns True
        assert parse_consent_value("") is True

    def test_parse_consent_value_whitespace_defaults_to_true(self):
        """Test parse_consent_value with whitespace returns True (NEW BEHAVIOR)."""
        # CRITICAL: This test will FAIL until implementation changes
        assert parse_consent_value("  ") is True
        assert parse_consent_value("\n") is True
        assert parse_consent_value("\t") is True

    def test_parse_consent_value_explicit_false_overrides_default(self):
        """Test parse_consent_value('false') returns False (explicit opt-out)."""
        # This should STILL work - explicit false overrides default
        assert parse_consent_value("false") is False
        assert parse_consent_value("False") is False
        assert parse_consent_value("FALSE") is False

    def test_parse_consent_value_explicit_no_overrides_default(self):
        """Test parse_consent_value('no') returns False (explicit opt-out)."""
        # This should STILL work - explicit no overrides default
        assert parse_consent_value("no") is False
        assert parse_consent_value("No") is False
        assert parse_consent_value("NO") is False

    def test_parse_consent_value_explicit_zero_overrides_default(self):
        """Test parse_consent_value('0') returns False (explicit opt-out)."""
        # This should STILL work - explicit 0 overrides default
        assert parse_consent_value("0") is False

    def test_parse_consent_value_explicit_true_still_works(self):
        """Test parse_consent_value('true') returns True (explicit opt-in)."""
        # This should STILL work - explicit true
        assert parse_consent_value("true") is True
        assert parse_consent_value("True") is True
        assert parse_consent_value("TRUE") is True

    def test_parse_consent_value_explicit_yes_still_works(self):
        """Test parse_consent_value('yes') returns True (explicit opt-in)."""
        # This should STILL work - explicit yes
        assert parse_consent_value("yes") is True
        assert parse_consent_value("Yes") is True
        assert parse_consent_value("YES") is True


class TestParseConsentValueCustomDefault:
    """Test parse_consent_value() with custom default parameter."""

    def test_parse_consent_value_custom_default_false(self):
        """Test parse_consent_value(None, default=False) returns False."""
        # NEW FEATURE: Allow custom default
        assert parse_consent_value(None, default=False) is False

    def test_parse_consent_value_custom_default_true(self):
        """Test parse_consent_value(None, default=True) returns True."""
        # NEW FEATURE: Allow custom default
        assert parse_consent_value(None, default=True) is True

    def test_parse_consent_value_empty_uses_custom_default(self):
        """Test parse_consent_value('', default=False) returns False."""
        # Empty string should use custom default
        assert parse_consent_value("", default=False) is False

    def test_parse_consent_value_explicit_overrides_custom_default(self):
        """Test explicit value overrides custom default."""
        # Explicit false should override default=True
        assert parse_consent_value("false", default=True) is False
        # Explicit true should override default=False
        assert parse_consent_value("true", default=False) is True


class TestBackwardCompatibility:
    """Test backward compatibility for existing code."""

    def test_parse_consent_value_true_values_unchanged(self):
        """Test existing truthy values still return True."""
        # These should continue to work exactly as before
        assert parse_consent_value("true") is True
        assert parse_consent_value("yes") is True
        assert parse_consent_value("1") is True
        assert parse_consent_value("y") is True

    def test_parse_consent_value_false_values_unchanged(self):
        """Test existing falsy values still return False."""
        # These should continue to work exactly as before
        assert parse_consent_value("false") is False
        assert parse_consent_value("no") is False
        assert parse_consent_value("0") is False
        assert parse_consent_value("n") is False

    def test_parse_consent_value_case_insensitive_unchanged(self):
        """Test case-insensitive behavior unchanged."""
        # Case-insensitivity should still work
        assert parse_consent_value("TRUE") is True
        assert parse_consent_value("YES") is True
        assert parse_consent_value("FALSE") is False
        assert parse_consent_value("NO") is False

    def test_parse_consent_value_strips_whitespace_unchanged(self):
        """Test whitespace stripping still works for explicit values."""
        # Whitespace stripping should still work for explicit values
        assert parse_consent_value("  true  ") is True
        assert parse_consent_value("  false  ") is False


class TestIntegrationWithCheckConsentViaEnv:
    """Test integration with check_consent_via_env() function."""

    def test_check_consent_via_env_defaults_to_true_when_unset(self):
        """Test check_consent_via_env() defaults to True when env vars unset."""
        # Import check_consent_via_env
        from auto_implement_git_integration import check_consent_via_env

        # Clear all env vars
        with patch.dict(os.environ, {}, clear=True):
            consent = check_consent_via_env()

            # NEW BEHAVIOR: Should default to True
            assert consent["enabled"] is True
            assert consent["push"] is True
            assert consent["pr"] is True

    def test_check_consent_via_env_respects_explicit_false(self):
        """Test check_consent_via_env() respects explicit false."""
        from auto_implement_git_integration import check_consent_via_env

        # Explicitly set to false
        with patch.dict(os.environ, {
            "AUTO_GIT_ENABLED": "false",
            "AUTO_GIT_PUSH": "false",
            "AUTO_GIT_PR": "false"
        }):
            consent = check_consent_via_env()

            # Should respect explicit opt-out
            assert consent["enabled"] is False
            assert consent["push"] is False
            assert consent["pr"] is False

    def test_check_consent_via_env_respects_explicit_true(self):
        """Test check_consent_via_env() respects explicit true."""
        from auto_implement_git_integration import check_consent_via_env

        # Explicitly set to true
        with patch.dict(os.environ, {
            "AUTO_GIT_ENABLED": "true",
            "AUTO_GIT_PUSH": "true",
            "AUTO_GIT_PR": "true"
        }):
            consent = check_consent_via_env()

            # Should respect explicit opt-in
            assert consent["enabled"] is True
            assert consent["push"] is True
            assert consent["pr"] is True

    def test_check_consent_via_env_mixed_values(self):
        """Test check_consent_via_env() with mixed explicit/default values."""
        from auto_implement_git_integration import check_consent_via_env

        # Mix of explicit and unset
        with patch.dict(os.environ, {
            "AUTO_GIT_ENABLED": "true",
            # AUTO_GIT_PUSH unset - should default to True
            "AUTO_GIT_PR": "false"
        }):
            consent = check_consent_via_env()

            assert consent["enabled"] is True
            assert consent["push"] is True  # Default
            assert consent["pr"] is False  # Explicit


class TestDocumentationExamples:
    """Test examples from documentation match expected behavior."""

    def test_example_env_var_not_set(self):
        """Test example: Environment variable not set."""
        # Example: AUTO_GIT_ENABLED is not set
        # NEW BEHAVIOR: Should default to True
        assert parse_consent_value(None) is True

    def test_example_explicit_opt_out(self):
        """Test example: User explicitly opts out."""
        # Example: AUTO_GIT_ENABLED=false in .env
        assert parse_consent_value("false") is False

    def test_example_explicit_opt_in(self):
        """Test example: User explicitly opts in."""
        # Example: AUTO_GIT_ENABLED=true in .env
        assert parse_consent_value("true") is True

    def test_example_empty_env_var(self):
        """Test example: Environment variable set to empty string."""
        # Example: AUTO_GIT_ENABLED= in .env
        # NEW BEHAVIOR: Should default to True
        assert parse_consent_value("") is True
