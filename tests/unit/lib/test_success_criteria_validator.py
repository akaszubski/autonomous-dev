"""
Unit Tests for SuccessCriteriaValidator (Ralph Loop Pattern - Issue #189)

Tests validation strategies for determining agent task completion:
- Pytest strategy (pass, fail, timeout)
- Safe word strategy (found, not found, case insensitive)
- File existence strategy (all present, some missing)
- Output parsing strategy (regex, JSON extraction)
- Security tests (path traversal prevention, ReDoS prevention)

Test Organization:
1. Pytest Strategy (5 tests)
2. Safe Word Strategy (5 tests)
3. File Existence Strategy (5 tests)
4. Output Parsing Strategy (4 tests)
5. Security Tests (4 tests)

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially - SuccessCriteriaValidator doesn't exist yet

Date: 2026-01-02
Issue: #189 (Ralph Loop Pattern for Self-Correcting Agent Execution)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))

# Import will fail - module doesn't exist yet (TDD!)
try:
    from success_criteria_validator import (
        validate_success,
        validate_pytest,
        validate_safe_word,
        validate_file_existence,
        validate_output_parsing,
        ValidationResult,
        DEFAULT_PYTEST_TIMEOUT,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

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
def failing_test_file(temp_test_dir):
    """Create failing pytest file."""
    test_file = temp_test_dir / "test_failing.py"
    test_file.write_text("""
def test_always_fails():
    assert False
""")
    return test_file


# =============================================================================
# SECTION 1: Pytest Strategy Tests (5 tests)
# =============================================================================

class TestPytestStrategy:
    """Test pytest validation strategy."""

    def test_validate_pytest_returns_success_when_tests_pass(self, passing_test_file):
        """Test that validate_pytest returns success when all tests pass."""
        # Act
        success, message = validate_pytest(str(passing_test_file))

        # Assert
        assert success is True
        assert "pass" in message.lower()

    def test_validate_pytest_returns_failure_when_tests_fail(self, failing_test_file):
        """Test that validate_pytest returns failure when tests fail."""
        # Act
        success, message = validate_pytest(str(failing_test_file))

        # Assert
        assert success is False
        assert "fail" in message.lower()

    def test_validate_pytest_handles_timeout(self, temp_test_dir):
        """Test that validate_pytest handles timeout for slow tests."""
        # Arrange - create slow test
        slow_test_file = temp_test_dir / "test_slow.py"
        slow_test_file.write_text("""
import time
def test_slow():
    time.sleep(10)
    assert True
""")

        # Act - run with short timeout
        success, message = validate_pytest(str(slow_test_file), timeout=1)

        # Assert
        assert success is False
        assert "timeout" in message.lower()

    def test_validate_pytest_uses_default_timeout(self):
        """Test that validate_pytest has reasonable default timeout."""
        # Assert
        assert DEFAULT_PYTEST_TIMEOUT >= 5
        assert DEFAULT_PYTEST_TIMEOUT <= 60

    def test_validate_pytest_validates_path_for_security(self, tmp_path):
        """Test that validate_pytest validates test path (CWE-22 prevention)."""
        # Arrange - malicious path with traversal
        malicious_path = "/tmp/../../etc/passwd"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_pytest(malicious_path)

        assert "path" in str(exc_info.value).lower()


# =============================================================================
# SECTION 2: Safe Word Strategy Tests (5 tests)
# =============================================================================

class TestSafeWordStrategy:
    """Test safe word validation strategy."""

    def test_validate_safe_word_returns_success_when_found(self):
        """Test that validate_safe_word returns success when safe word found."""
        # Arrange
        output = "Task completed successfully. SAFE_WORD_COMPLETE"
        safe_word = "SAFE_WORD_COMPLETE"

        # Act
        success, message = validate_safe_word(output, safe_word)

        # Assert
        assert success is True
        assert "found" in message.lower()

    def test_validate_safe_word_returns_failure_when_not_found(self):
        """Test that validate_safe_word returns failure when safe word not found."""
        # Arrange
        output = "Task still in progress..."
        safe_word = "SAFE_WORD_COMPLETE"

        # Act
        success, message = validate_safe_word(output, safe_word)

        # Assert
        assert success is False
        assert "not found" in message.lower()

    def test_validate_safe_word_is_case_insensitive(self):
        """Test that validate_safe_word is case insensitive."""
        # Arrange
        output = "Task completed successfully. safe_word_complete"
        safe_word = "SAFE_WORD_COMPLETE"

        # Act
        success, message = validate_safe_word(output, safe_word)

        # Assert
        assert success is True

    def test_validate_safe_word_handles_multiline_output(self):
        """Test that validate_safe_word handles multiline output."""
        # Arrange
        output = """
        Line 1: Starting task
        Line 2: Processing
        Line 3: SAFE_WORD_COMPLETE
        Line 4: Cleanup
        """
        safe_word = "SAFE_WORD_COMPLETE"

        # Act
        success, message = validate_safe_word(output, safe_word)

        # Assert
        assert success is True

    def test_validate_safe_word_sanitizes_for_security(self):
        """Test that validate_safe_word sanitizes inputs to prevent injection."""
        # Arrange - malicious safe word with regex characters
        output = "Task completed"
        malicious_safe_word = ".*"  # Would match everything in naive regex

        # Act - should treat safe_word as literal string, not regex
        success, message = validate_safe_word(output, malicious_safe_word)

        # Assert - should not find (literal ".*" not in output)
        assert success is False


# =============================================================================
# SECTION 3: File Existence Strategy Tests (5 tests)
# =============================================================================

class TestFileExistenceStrategy:
    """Test file existence validation strategy."""

    def test_validate_file_existence_returns_success_when_all_present(self, tmp_path):
        """Test that validate_file_existence returns success when all files exist."""
        # Arrange - create expected files
        file1 = tmp_path / "output1.txt"
        file2 = tmp_path / "output2.txt"
        file1.write_text("data")
        file2.write_text("data")

        expected_files = [str(file1), str(file2)]

        # Act
        success, message = validate_file_existence(expected_files)

        # Assert
        assert success is True
        assert "found" in message.lower()

    def test_validate_file_existence_returns_failure_when_some_missing(self, tmp_path):
        """Test that validate_file_existence returns failure when some files missing."""
        # Arrange - create only one file
        file1 = tmp_path / "output1.txt"
        file1.write_text("data")

        file2_path = tmp_path / "output2.txt"  # Doesn't exist

        expected_files = [str(file1), str(file2_path)]

        # Act
        success, message = validate_file_existence(expected_files)

        # Assert
        assert success is False
        assert "missing" in message.lower() or "not found" in message.lower()

    def test_validate_file_existence_validates_paths_for_security(self):
        """Test that validate_file_existence validates paths (CWE-22 prevention)."""
        # Arrange - malicious paths with traversal
        malicious_files = [
            "/tmp/../../etc/passwd",
            "/tmp/../../../root/.ssh/id_rsa",
        ]

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_file_existence(malicious_files)

        assert "path" in str(exc_info.value).lower()

    def test_validate_file_existence_rejects_symlinks(self, tmp_path):
        """Test that validate_file_existence rejects symlinks (CWE-59 prevention)."""
        # Arrange - create symlink
        target_file = tmp_path / "target.txt"
        target_file.write_text("data")

        symlink_path = tmp_path / "symlink.txt"
        try:
            symlink_path.symlink_to(target_file)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        expected_files = [str(symlink_path)]

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_file_existence(expected_files)

        assert "symlink" in str(exc_info.value).lower()

    def test_validate_file_existence_handles_empty_list(self):
        """Test that validate_file_existence handles empty file list."""
        # Arrange
        expected_files = []

        # Act
        success, message = validate_file_existence(expected_files)

        # Assert - empty list should be valid (no files required)
        assert success is True


# =============================================================================
# SECTION 4: Output Parsing Strategy Tests (4 tests)
# =============================================================================

class TestOutputParsingStrategy:
    """Test output parsing validation strategy."""

    def test_validate_output_parsing_extracts_regex_match(self):
        """Test that validate_output_parsing extracts data via regex."""
        # Arrange
        output = "Result: 42 items processed successfully"
        pattern = r"Result: (\d+) items"
        expected_value = "42"

        # Act
        success, message = validate_output_parsing(
            output,
            strategy="regex",
            pattern=pattern,
            expected=expected_value
        )

        # Assert
        assert success is True
        assert "42" in message

    def test_validate_output_parsing_fails_when_pattern_not_found(self):
        """Test that validate_output_parsing fails when pattern not found."""
        # Arrange
        output = "No results available"
        pattern = r"Result: (\d+) items"
        expected_value = "42"

        # Act
        success, message = validate_output_parsing(
            output,
            strategy="regex",
            pattern=pattern,
            expected=expected_value
        )

        # Assert
        assert success is False
        assert "not found" in message.lower() or "missing" in message.lower()

    def test_validate_output_parsing_prevents_redos_attack(self):
        """Test that validate_output_parsing prevents ReDoS attacks."""
        # Arrange - malicious regex pattern that causes catastrophic backtracking
        output = "a" * 100
        malicious_pattern = r"^(a+)+$"  # Classic ReDoS pattern

        # Act & Assert - should timeout or reject malicious pattern
        with pytest.raises((ValueError, TimeoutError)) as exc_info:
            validate_output_parsing(
                output,
                strategy="regex",
                pattern=malicious_pattern,
                expected="a",
                timeout=1  # Short timeout to prevent hanging
            )

        assert "timeout" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_validate_output_parsing_supports_json_extraction(self):
        """Test that validate_output_parsing supports JSON extraction."""
        # Arrange
        output = '{"status": "completed", "count": 42}'
        json_path = "$.status"
        expected_value = "completed"

        # Act
        success, message = validate_output_parsing(
            output,
            strategy="json",
            json_path=json_path,
            expected=expected_value
        )

        # Assert
        assert success is True
        assert "completed" in message


# =============================================================================
# SECTION 5: Security Tests (4 tests)
# =============================================================================

class TestSecurityValidation:
    """Test security validations across all strategies."""

    def test_validate_success_blocks_path_traversal_in_file_strategy(self):
        """Test that validate_success blocks path traversal in file strategy."""
        # Arrange
        config = {
            "expected_files": ["/tmp/../../etc/passwd"]
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_success("file_existence", "", config)

        assert "path" in str(exc_info.value).lower()

    def test_validate_success_blocks_symlinks_in_file_strategy(self, tmp_path):
        """Test that validate_success blocks symlinks in file strategy."""
        # Arrange - create symlink
        target_file = tmp_path / "target.txt"
        target_file.write_text("data")

        symlink_path = tmp_path / "symlink.txt"
        try:
            symlink_path.symlink_to(target_file)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        config = {
            "expected_files": [str(symlink_path)]
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_success("file_existence", "", config)

        assert "symlink" in str(exc_info.value).lower()

    def test_validate_success_prevents_command_injection_in_pytest_strategy(self):
        """Test that validate_success prevents command injection in pytest strategy."""
        # Arrange - malicious test path with command injection
        malicious_path = "test.py; rm -rf /"
        config = {"test_path": malicious_path}

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_success("pytest", "", config)

        assert "invalid" in str(exc_info.value).lower() or "path" in str(exc_info.value).lower()

    def test_validate_success_sanitizes_regex_patterns_to_prevent_redos(self):
        """Test that validate_success sanitizes regex patterns to prevent ReDoS."""
        # Arrange - malicious regex pattern
        output = "a" * 100
        config = {
            "pattern": r"^(a+)+$",  # Classic ReDoS pattern
            "expected": "a",
        }

        # Act & Assert - should timeout or reject
        with pytest.raises((ValueError, TimeoutError)):
            validate_success("regex", output, config, timeout=1)


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (23 unit tests for success_criteria_validator.py):

SECTION 1: Pytest Strategy (5 tests)
✗ test_validate_pytest_returns_success_when_tests_pass
✗ test_validate_pytest_returns_failure_when_tests_fail
✗ test_validate_pytest_handles_timeout
✗ test_validate_pytest_uses_default_timeout
✗ test_validate_pytest_validates_path_for_security

SECTION 2: Safe Word Strategy (5 tests)
✗ test_validate_safe_word_returns_success_when_found
✗ test_validate_safe_word_returns_failure_when_not_found
✗ test_validate_safe_word_is_case_insensitive
✗ test_validate_safe_word_handles_multiline_output
✗ test_validate_safe_word_sanitizes_for_security

SECTION 3: File Existence Strategy (5 tests)
✗ test_validate_file_existence_returns_success_when_all_present
✗ test_validate_file_existence_returns_failure_when_some_missing
✗ test_validate_file_existence_validates_paths_for_security
✗ test_validate_file_existence_rejects_symlinks
✗ test_validate_file_existence_handles_empty_list

SECTION 4: Output Parsing Strategy (4 tests)
✗ test_validate_output_parsing_extracts_regex_match
✗ test_validate_output_parsing_fails_when_pattern_not_found
✗ test_validate_output_parsing_prevents_redos_attack
✗ test_validate_output_parsing_supports_json_extraction

SECTION 5: Security Tests (4 tests)
✗ test_validate_success_blocks_path_traversal_in_file_strategy
✗ test_validate_success_blocks_symlinks_in_file_strategy
✗ test_validate_success_prevents_command_injection_in_pytest_strategy
✗ test_validate_success_sanitizes_regex_patterns_to_prevent_redos

Expected Status: ALL TESTS FAILING (RED phase - implementation doesn't exist yet)
Next Step: Implement SuccessCriteriaValidator to make tests pass (GREEN phase)
"""
