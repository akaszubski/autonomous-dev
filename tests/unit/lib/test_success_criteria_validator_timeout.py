#!/usr/bin/env python3
"""
Unit Tests for Success Criteria Validator - Pytest Timeout (Issue #256)

Tests for pytest timeout configuration changes:
- DEFAULT_PYTEST_TIMEOUT changed from 30 to 60 seconds
- PYTEST_TIMEOUT environment variable override
- Invalid env var values handled gracefully

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
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import will succeed - module exists but constant will change
try:
    from success_criteria_validator import (
        DEFAULT_PYTEST_TIMEOUT,
        validate_pytest,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clean_env():
    """Clean PYTEST_TIMEOUT environment variable before each test."""
    # Save original value
    original_timeout = os.environ.get("PYTEST_TIMEOUT")

    # Clear env var
    os.environ.pop("PYTEST_TIMEOUT", None)

    yield

    # Restore original value
    if original_timeout is not None:
        os.environ["PYTEST_TIMEOUT"] = original_timeout
    else:
        os.environ.pop("PYTEST_TIMEOUT", None)


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create temporary directory for test files."""
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    return test_dir


@pytest.fixture
def passing_test_file(temp_test_dir):
    """Create passing pytest file."""
    test_file = temp_test_dir / "test_passing.py"
    test_file.write_text("""
def test_always_passes():
    assert True
""")
    return test_file


@pytest.fixture
def slow_test_file(temp_test_dir):
    """Create slow test file for timeout testing."""
    test_file = temp_test_dir / "test_slow.py"
    test_file.write_text("""
import time
def test_slow():
    time.sleep(5)
    assert True
""")
    return test_file


# =============================================================================
# SECTION 1: Default Timeout Constant Tests (2 tests)
# =============================================================================

class TestDefaultTimeoutConstant:
    """Test DEFAULT_PYTEST_TIMEOUT constant value change."""

    def test_default_pytest_timeout_is_60(self):
        """Test that DEFAULT_PYTEST_TIMEOUT is set to 60 seconds.

        CHANGE: Previously 30 seconds, now 60 seconds.
        This gives agents more time to run complex test suites.
        """
        # Assert
        assert DEFAULT_PYTEST_TIMEOUT == 60, (
            "DEFAULT_PYTEST_TIMEOUT should be 60 seconds (was 30). "
            "This gives agents more time for complex test suites."
        )

    def test_default_timeout_is_reasonable_range(self):
        """Test that DEFAULT_PYTEST_TIMEOUT is in a reasonable range.

        Should be:
        - At least 30 seconds (enough for basic test suites)
        - At most 300 seconds (5 minutes - prevents infinite hangs)
        """
        # Assert
        assert 30 <= DEFAULT_PYTEST_TIMEOUT <= 300, (
            f"DEFAULT_PYTEST_TIMEOUT ({DEFAULT_PYTEST_TIMEOUT}s) should be "
            f"between 30 and 300 seconds for practical use"
        )


# =============================================================================
# SECTION 2: Environment Variable Override Tests (5 tests)
# =============================================================================

class TestPytestTimeoutEnvVar:
    """Test PYTEST_TIMEOUT environment variable override."""

    def test_pytest_timeout_env_var_override(self, passing_test_file):
        """Test that PYTEST_TIMEOUT env var overrides default timeout."""
        # Arrange
        os.environ["PYTEST_TIMEOUT"] = "10"

        # Act - run with env var set
        # Mock subprocess.run to verify timeout is passed correctly
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")

            validate_pytest(str(passing_test_file))

            # Assert - timeout should be 10 (from env var), not 60 (default)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("timeout") == 10, (
                "PYTEST_TIMEOUT=10 should override default timeout of 60"
            )

    def test_pytest_timeout_env_var_uses_default_when_not_set(self, passing_test_file):
        """Test that default timeout is used when PYTEST_TIMEOUT not set."""
        # Arrange - no env var set
        assert "PYTEST_TIMEOUT" not in os.environ

        # Act - run without env var
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")

            validate_pytest(str(passing_test_file))

            # Assert - timeout should be DEFAULT_PYTEST_TIMEOUT (60)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("timeout") == DEFAULT_PYTEST_TIMEOUT, (
                f"Should use DEFAULT_PYTEST_TIMEOUT ({DEFAULT_PYTEST_TIMEOUT}) when env var not set"
            )

    def test_pytest_timeout_env_var_accepts_integer_string(self, passing_test_file):
        """Test that PYTEST_TIMEOUT accepts integer string values."""
        # Test various integer string values
        test_cases = ["30", "60", "120", "300"]

        for timeout_str in test_cases:
            # Arrange
            os.environ["PYTEST_TIMEOUT"] = timeout_str

            # Act
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")

                validate_pytest(str(passing_test_file))

                # Assert - timeout should match env var
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs.get("timeout") == int(timeout_str), (
                    f"PYTEST_TIMEOUT={timeout_str} should set timeout to {timeout_str} seconds"
                )

    def test_invalid_pytest_timeout_env_var_ignored(self, passing_test_file):
        """Test that invalid PYTEST_TIMEOUT values are ignored and default is used."""
        # Test invalid values
        invalid_values = ["not_a_number", "", "abc", "-10", "0"]

        for invalid_value in invalid_values:
            # Arrange
            os.environ["PYTEST_TIMEOUT"] = invalid_value

            # Act
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")

                # Should not crash - use default timeout
                validate_pytest(str(passing_test_file))

                # Assert - should fall back to default timeout
                call_kwargs = mock_run.call_args[1]
                timeout_used = call_kwargs.get("timeout")

                assert timeout_used == DEFAULT_PYTEST_TIMEOUT, (
                    f"Invalid PYTEST_TIMEOUT='{invalid_value}' should fall back to "
                    f"DEFAULT_PYTEST_TIMEOUT ({DEFAULT_PYTEST_TIMEOUT})"
                )

    def test_pytest_timeout_env_var_allows_custom_timeout_parameter(self, passing_test_file):
        """Test that explicit timeout parameter takes precedence over env var."""
        # Arrange
        os.environ["PYTEST_TIMEOUT"] = "30"
        explicit_timeout = 15

        # Act
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")

            # Pass explicit timeout parameter
            validate_pytest(str(passing_test_file), timeout=explicit_timeout)

            # Assert - explicit parameter should take precedence
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("timeout") == explicit_timeout, (
                f"Explicit timeout={explicit_timeout} should take precedence over "
                f"PYTEST_TIMEOUT=30 env var"
            )


# =============================================================================
# SECTION 3: Integration Tests with Real Timeouts (3 tests)
# =============================================================================

class TestPytestTimeoutIntegration:
    """Integration tests for timeout behavior with real subprocess calls."""

    def test_validate_pytest_uses_60_second_timeout_by_default(self, passing_test_file):
        """Test that validate_pytest actually uses 60 second timeout in subprocess."""
        # This test verifies the integration works end-to-end
        # We don't actually wait 60 seconds, just verify the timeout is set correctly

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")

            # Act - call without any timeout override
            validate_pytest(str(passing_test_file))

            # Assert - subprocess.run called with timeout=60
            assert mock_run.called
            call_kwargs = mock_run.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 60

    def test_validate_pytest_respects_env_var_timeout(self, passing_test_file):
        """Test that validate_pytest respects PYTEST_TIMEOUT env var in subprocess."""
        # Arrange
        os.environ["PYTEST_TIMEOUT"] = "45"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")

            # Act
            validate_pytest(str(passing_test_file))

            # Assert - subprocess.run called with timeout=45
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 45

    def test_validate_pytest_handles_timeout_exception(self, slow_test_file):
        """Test that validate_pytest handles subprocess timeout exceptions gracefully."""
        # Arrange - set very short timeout to trigger timeout
        os.environ["PYTEST_TIMEOUT"] = "1"

        # Act - this should timeout since slow_test_file sleeps for 5 seconds
        success, message = validate_pytest(str(slow_test_file))

        # Assert - should return failure with timeout message
        assert success is False
        assert "timeout" in message.lower()


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (10 unit tests for success_criteria_validator.py - timeout):

SECTION 1: Default Timeout Constant (2 tests)
✗ test_default_pytest_timeout_is_60
✗ test_default_timeout_is_reasonable_range

SECTION 2: Environment Variable Override (5 tests)
✗ test_pytest_timeout_env_var_override
✗ test_pytest_timeout_env_var_uses_default_when_not_set
✗ test_pytest_timeout_env_var_accepts_integer_string
✗ test_invalid_pytest_timeout_env_var_ignored
✗ test_pytest_timeout_env_var_allows_custom_timeout_parameter

SECTION 3: Integration Tests (3 tests)
✗ test_validate_pytest_uses_60_second_timeout_by_default
✗ test_validate_pytest_respects_env_var_timeout
✗ test_validate_pytest_handles_timeout_exception

Expected Status: TESTS WILL FAIL (RED phase - implementation not done yet)
Current Behavior: DEFAULT_PYTEST_TIMEOUT = 30
Target Behavior: DEFAULT_PYTEST_TIMEOUT = 60

Implementation Requirements:
1. Change DEFAULT_PYTEST_TIMEOUT from 30 to 60 seconds
2. Add PYTEST_TIMEOUT environment variable support:
   - Read from os.environ.get("PYTEST_TIMEOUT")
   - Parse as integer
   - Use as default timeout if valid
   - Fall back to DEFAULT_PYTEST_TIMEOUT if invalid/missing
3. Explicit timeout parameter takes precedence over env var
4. Handle invalid env var values gracefully (non-numeric, negative, zero)
5. Update validate_pytest() to use env var timeout

Coverage Target: 100% for timeout configuration logic
"""
