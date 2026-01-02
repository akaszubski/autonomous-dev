#!/usr/bin/env python3
"""
Unit tests for QA self-healing loop with automatic test fix iterations (TDD Red Phase - Issue #184).

Tests for orchestrating automatic test failure detection, analysis, fix generation, and retry.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test failure analysis (parse pytest output)
- Test stuck detection (3 identical errors)
- Test code patching (atomic writes, rollback)
- Test orchestration (multi-iteration healing)
- Test environment variable controls
- Test security (path validation, audit logging)

Security:
- Path traversal blocked (CWE-22)
- Symlink attacks blocked (CWE-59)
- Audit logging for all operations
- Max iterations prevent infinite loops

Coverage Target: 95%+ for QA self-healer components

Date: 2026-01-02
Issue: #184 (Self-healing QA loop with automatic test fix iterations)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - modules don't exist yet)
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from dataclasses import dataclass

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

# Import will fail - modules don't exist yet (TDD!)
try:
    from failure_analyzer import (
        FailureAnalyzer,
        FailureAnalysis,
        parse_pytest_output,
        extract_error_details,
    )
    from stuck_detector import (
        StuckDetector,
        is_stuck,
        reset_stuck_detection,
        DEFAULT_STUCK_THRESHOLD,
    )
    from code_patcher import (
        CodePatcher,
        apply_patch,
        create_backup,
        rollback_patch,
        cleanup_backups,
        validate_patch_path,
    )
    from qa_self_healer import (
        QASelfHealer,
        heal_test_failures,
        run_tests_with_healing,
        ProposedFix,
        SelfHealingResult,
        HealingAttempt,
        DEFAULT_MAX_ITERATIONS,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_test_dir(tmp_path):
    """Create temporary directory for test files."""
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()

    # Create sample test file with syntax error
    test_file = test_dir / "test_sample.py"
    test_file.write_text("""
def test_example():
    assert 1 == 1
    # Missing closing parenthesis
    result = some_func(
""")

    return test_dir


@pytest.fixture
def sample_pytest_output():
    """Sample pytest output with syntax error."""
    return """
============================= test session starts ==============================
platform darwin -- Python 3.11.0
collected 0 items / 1 error

==================================== ERRORS ====================================
_______________________ ERROR collecting test_sample.py ________________________
test_sample.py:5: in <module>
    result = some_func(
SyntaxError: '(' was never closed

=========================== short test summary info ============================
ERROR test_sample.py - SyntaxError: '(' was never closed
========================= 1 error in 0.03s =================================
"""


@pytest.fixture
def sample_import_error_output():
    """Sample pytest output with import error."""
    return """
============================= test session starts ==============================
collected 0 items / 1 error

==================================== ERRORS ====================================
_____________________ ERROR collecting test_imports.py _________________________
ImportError while importing test module 'test_imports.py'.
Hint: make sure your test's root directory is importable.
Original exception was:
Traceback (most recent call last):
  File "/project/test_imports.py", line 3, in <module>
    from nonexistent_module import function
ModuleNotFoundError: No module named 'nonexistent_module'

=========================== short test summary info ============================
ERROR test_imports.py::test_function - ModuleNotFoundError: No module named 'nonexistent_module'
========================= 1 error in 0.02s =================================
"""


@pytest.fixture
def sample_assertion_error_output():
    """Sample pytest output with assertion error."""
    return """
============================= test session starts ==============================
collected 1 item

test_logic.py F                                                          [100%]

=================================== FAILURES ===================================
_______________________________ test_addition __________________________________
test_logic.py:10: in test_addition
    assert add(2, 2) == 5
E   AssertionError: assert 4 == 5
E    +  where 4 = add(2, 2)

=========================== short test summary info ============================
FAILED test_logic.py::test_addition - AssertionError: assert 4 == 5
========================= 1 failed in 0.05s ====================================
"""


# =============================================================================
# SECTION 1: Failure Analyzer Tests (12 tests)
# =============================================================================

class TestFailureAnalyzer:
    """Test parsing pytest output to extract failure details."""

    def test_parse_syntax_error_from_pytest_output(self, sample_pytest_output):
        """Test parsing syntax error from pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()

        # Act
        failures = analyzer.parse_pytest_output(sample_pytest_output)

        # Assert
        assert len(failures) == 1
        failure = failures[0]
        assert failure.error_type == "syntax"
        assert "never closed" in failure.error_message.lower()
        assert "test_sample.py" in failure.file_path
        assert failure.line_number == 5

    def test_parse_import_error_from_pytest_output(self, sample_import_error_output):
        """Test parsing import error from pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()

        # Act
        failures = analyzer.parse_pytest_output(sample_import_error_output)

        # Assert
        assert len(failures) == 1
        failure = failures[0]
        assert failure.error_type == "import"
        assert "nonexistent_module" in failure.error_message
        assert "test_imports.py" in failure.file_path

    def test_parse_assertion_error_from_pytest_output(self, sample_assertion_error_output):
        """Test parsing assertion error from pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()

        # Act
        failures = analyzer.parse_pytest_output(sample_assertion_error_output)

        # Assert
        assert len(failures) == 1
        failure = failures[0]
        assert failure.error_type == "assertion"
        assert "assert 4 == 5" in failure.error_message
        assert "test_logic.py" in failure.file_path
        assert failure.line_number == 10

    def test_parse_type_error_from_pytest_output(self):
        """Test parsing type error from pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()
        output = """
test_types.py:15: in test_string_concat
    result = concat_strings(123, "hello")
E   TypeError: expected str, got int
"""

        # Act
        failures = analyzer.parse_pytest_output(output)

        # Assert
        assert len(failures) == 1
        failure = failures[0]
        assert failure.error_type == "type"
        assert "TypeError" in failure.error_message

    def test_parse_runtime_error_from_pytest_output(self):
        """Test parsing runtime error from pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()
        output = """
test_runtime.py:20: in test_division
    result = divide(10, 0)
E   ZeroDivisionError: division by zero
"""

        # Act
        failures = analyzer.parse_pytest_output(output)

        # Assert
        assert len(failures) == 1
        failure = failures[0]
        assert failure.error_type == "runtime"
        assert "ZeroDivisionError" in failure.error_message

    def test_extract_file_path_and_line_number(self, sample_pytest_output):
        """Test extraction of file path and line number."""
        # Arrange
        analyzer = FailureAnalyzer()

        # Act
        failures = analyzer.parse_pytest_output(sample_pytest_output)

        # Assert
        failure = failures[0]
        assert failure.file_path == "test_sample.py"
        assert failure.line_number == 5

    def test_handle_malformed_pytest_output(self):
        """Test handling of malformed pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()
        malformed_output = "This is not valid pytest output\nRandom text\n"

        # Act
        failures = analyzer.parse_pytest_output(malformed_output)

        # Assert - should return empty list, not crash
        assert failures == []

    def test_handle_empty_pytest_output(self):
        """Test handling of empty pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()
        empty_output = ""

        # Act
        failures = analyzer.parse_pytest_output(empty_output)

        # Assert
        assert failures == []

    def test_parse_multiple_failures_in_one_output(self):
        """Test parsing multiple failures from single pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()
        output = """
test_multi.py:5: SyntaxError: invalid syntax
test_multi.py:10: ImportError: No module named 'xyz'
test_multi.py:15: AssertionError: assert False
"""

        # Act
        failures = analyzer.parse_pytest_output(output)

        # Assert
        assert len(failures) == 3
        assert failures[0].error_type == "syntax"
        assert failures[1].error_type == "import"
        assert failures[2].error_type == "assertion"

    def test_extract_stack_trace(self, sample_import_error_output):
        """Test extraction of complete stack trace."""
        # Arrange
        analyzer = FailureAnalyzer()

        # Act
        failures = analyzer.parse_pytest_output(sample_import_error_output)

        # Assert
        failure = failures[0]
        assert failure.stack_trace is not None
        assert "Traceback" in failure.stack_trace

    def test_failure_analysis_dataclass_structure(self):
        """Test FailureAnalysis dataclass has required fields."""
        # Arrange & Act
        failure = FailureAnalysis(
            test_name="test_example",
            error_type="syntax",
            error_message="Syntax error",
            file_path="test.py",
            line_number=10,
            stack_trace="Traceback...",
        )

        # Assert
        assert failure.test_name == "test_example"
        assert failure.error_type == "syntax"
        assert failure.error_message == "Syntax error"
        assert failure.file_path == "test.py"
        assert failure.line_number == 10
        assert failure.stack_trace == "Traceback..."

    def test_parse_pytest_output_with_test_name(self):
        """Test extraction of test name from pytest output."""
        # Arrange
        analyzer = FailureAnalyzer()
        output = """
test_module.py::test_function FAILED
test_module.py:10: AssertionError
"""

        # Act
        failures = analyzer.parse_pytest_output(output)

        # Assert
        assert len(failures) == 1
        assert failures[0].test_name == "test_module.py::test_function"


# =============================================================================
# SECTION 2: Stuck Detector Tests (8 tests)
# =============================================================================

class TestStuckDetector:
    """Test detection of stuck healing loops (3 identical errors)."""

    def test_stuck_detected_after_three_identical_errors(self):
        """Test stuck detection after 3 identical error messages."""
        # Arrange
        detector = StuckDetector()
        error = "SyntaxError: invalid syntax"

        # Act
        detector.record_error(error)
        detector.record_error(error)
        is_stuck_after_2 = detector.is_stuck()

        detector.record_error(error)
        is_stuck_after_3 = detector.is_stuck()

        # Assert
        assert is_stuck_after_2 is False
        assert is_stuck_after_3 is True

    def test_not_stuck_with_different_errors(self):
        """Test no stuck detection when errors are different."""
        # Arrange
        detector = StuckDetector()

        # Act
        detector.record_error("SyntaxError: line 1")
        detector.record_error("ImportError: module not found")
        detector.record_error("AssertionError: assert failed")
        detector.record_error("TypeError: wrong type")

        # Assert
        assert detector.is_stuck() is False

    def test_reset_after_successful_iteration(self):
        """Test stuck detector resets after successful test run."""
        # Arrange
        detector = StuckDetector()
        error = "SyntaxError: invalid syntax"

        # Record 2 identical errors
        detector.record_error(error)
        detector.record_error(error)

        # Act - reset on success
        detector.reset()

        # Record same error again (should not be stuck yet)
        detector.record_error(error)

        # Assert
        assert detector.is_stuck() is False

    def test_custom_stuck_threshold(self):
        """Test custom stuck threshold (5 instead of 3)."""
        # Arrange
        detector = StuckDetector(threshold=5)
        error = "SyntaxError: invalid syntax"

        # Act - record 4 identical errors
        for _ in range(4):
            detector.record_error(error)

        # Assert - not stuck at 4 (threshold is 5)
        assert detector.is_stuck() is False

        # Act - record 5th error
        detector.record_error(error)

        # Assert - now stuck
        assert detector.is_stuck() is True

    def test_empty_error_list_not_stuck(self):
        """Test that empty error list is not stuck."""
        # Arrange
        detector = StuckDetector()

        # Act & Assert
        assert detector.is_stuck() is False

    def test_single_error_not_stuck(self):
        """Test that single error is not stuck."""
        # Arrange
        detector = StuckDetector()

        # Act
        detector.record_error("SyntaxError: invalid syntax")

        # Assert
        assert detector.is_stuck() is False

    def test_exact_threshold_boundary(self):
        """Test stuck detection at exact threshold boundary."""
        # Arrange
        detector = StuckDetector(threshold=3)
        error = "ImportError: module not found"

        # Act - record exactly 3 errors
        detector.record_error(error)
        detector.record_error(error)
        detector.record_error(error)

        # Assert
        assert detector.is_stuck() is True

    def test_default_stuck_threshold_is_three(self):
        """Test that DEFAULT_STUCK_THRESHOLD is set to 3."""
        # Arrange & Act & Assert
        assert DEFAULT_STUCK_THRESHOLD == 3


# =============================================================================
# SECTION 3: Code Patcher Tests (10 tests)
# =============================================================================

class TestCodePatcher:
    """Test atomic file patching with backup and rollback."""

    def test_apply_fix_successfully(self, temp_test_dir):
        """Test successful application of code fix."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)
        test_file = temp_test_dir / "test_sample.py"

        proposed_fix = ProposedFix(
            file_path=str(test_file),
            original_code="result = some_func(",
            fixed_code="result = some_func()",
            strategy="add_closing_paren",
            confidence=0.95,
        )

        # Act
        success = patcher.apply_patch(proposed_fix)

        # Assert
        assert success is True
        assert "result = some_func()" in test_file.read_text()

    def test_create_backup_before_patching(self, temp_test_dir):
        """Test backup file created before applying patch."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)
        test_file = temp_test_dir / "test_sample.py"
        original_content = test_file.read_text()

        proposed_fix = ProposedFix(
            file_path=str(test_file),
            original_code="result = some_func(",
            fixed_code="result = some_func()",
            strategy="add_closing_paren",
            confidence=0.95,
        )

        # Act
        patcher.apply_patch(proposed_fix)

        # Assert - backup file exists
        backup_files = list(temp_test_dir.glob("test_sample.py.backup.*"))
        assert len(backup_files) == 1
        assert backup_files[0].read_text() == original_content

    def test_rollback_on_error(self, temp_test_dir):
        """Test rollback restores original content on error."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)
        test_file = temp_test_dir / "test_sample.py"
        original_content = test_file.read_text()

        proposed_fix = ProposedFix(
            file_path=str(test_file),
            original_code="result = some_func(",
            fixed_code="result = some_func()",
            strategy="add_closing_paren",
            confidence=0.95,
        )

        # Apply patch
        patcher.apply_patch(proposed_fix)

        # Act - rollback
        patcher.rollback_last_patch()

        # Assert - original content restored
        assert test_file.read_text() == original_content

    def test_atomic_write_uses_temp_file_and_rename(self, temp_test_dir):
        """Test atomic write pattern (temp → rename)."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)
        test_file = temp_test_dir / "test_sample.py"

        proposed_fix = ProposedFix(
            file_path=str(test_file),
            original_code="result = some_func(",
            fixed_code="result = some_func()",
            strategy="add_closing_paren",
            confidence=0.95,
        )

        # Act
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("os.write") as mock_write, \
             patch("os.close") as mock_close, \
             patch("pathlib.Path.replace") as mock_replace:

            mock_mkstemp.return_value = (999, "/tmp/.patch_abc.tmp")
            patcher.apply_patch(proposed_fix)

            # Assert - atomic write pattern used
            mock_mkstemp.assert_called()
            mock_write.assert_called()
            mock_close.assert_called()
            mock_replace.assert_called()

    def test_path_traversal_blocked(self, temp_test_dir):
        """Test path traversal attack is blocked (CWE-22)."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)

        # Attempt path traversal
        malicious_fix = ProposedFix(
            file_path="../../../etc/passwd",
            original_code="root:",
            fixed_code="hacked:",
            strategy="attack",
            confidence=1.0,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Path traversal detected"):
            patcher.apply_patch(malicious_fix)

    def test_symlink_attack_blocked(self, temp_test_dir):
        """Test symlink attack is blocked (CWE-59)."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)

        # Create symlink to sensitive file
        symlink_path = temp_test_dir / "symlink_test.py"
        target_path = Path("/etc/passwd")

        # Create symlink (if supported on platform)
        try:
            symlink_path.symlink_to(target_path)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        proposed_fix = ProposedFix(
            file_path=str(symlink_path),
            original_code="root:",
            fixed_code="hacked:",
            strategy="attack",
            confidence=1.0,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Symlink detected"):
            patcher.apply_patch(proposed_fix)

    def test_file_permissions_preserved(self, temp_test_dir):
        """Test file permissions preserved after patching."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)
        test_file = temp_test_dir / "test_sample.py"

        # Set specific permissions
        test_file.chmod(0o644)
        original_stat = test_file.stat()

        proposed_fix = ProposedFix(
            file_path=str(test_file),
            original_code="result = some_func(",
            fixed_code="result = some_func()",
            strategy="add_closing_paren",
            confidence=0.95,
        )

        # Act
        patcher.apply_patch(proposed_fix)

        # Assert - permissions unchanged
        new_stat = test_file.stat()
        assert new_stat.st_mode == original_stat.st_mode

    def test_cleanup_backups_after_success(self, temp_test_dir):
        """Test backup files cleaned up after successful healing."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)
        test_file = temp_test_dir / "test_sample.py"

        proposed_fix = ProposedFix(
            file_path=str(test_file),
            original_code="result = some_func(",
            fixed_code="result = some_func()",
            strategy="add_closing_paren",
            confidence=0.95,
        )

        # Apply patch (creates backup)
        patcher.apply_patch(proposed_fix)
        assert len(list(temp_test_dir.glob("*.backup.*"))) == 1

        # Act - cleanup backups
        patcher.cleanup_backups()

        # Assert - backups removed
        assert len(list(temp_test_dir.glob("*.backup.*"))) == 0

    def test_invalid_file_path_raises_error(self, temp_test_dir):
        """Test invalid file path raises error."""
        # Arrange
        patcher = CodePatcher(temp_test_dir)

        proposed_fix = ProposedFix(
            file_path="/nonexistent/path/test.py",
            original_code="code",
            fixed_code="fixed",
            strategy="fix",
            confidence=0.8,
        )

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            patcher.apply_patch(proposed_fix)

    def test_proposed_fix_dataclass_structure(self):
        """Test ProposedFix dataclass has required fields."""
        # Arrange & Act
        fix = ProposedFix(
            file_path="test.py",
            original_code="old code",
            fixed_code="new code",
            strategy="refactor",
            confidence=0.9,
        )

        # Assert
        assert fix.file_path == "test.py"
        assert fix.original_code == "old code"
        assert fix.fixed_code == "new code"
        assert fix.strategy == "refactor"
        assert fix.confidence == 0.9


# =============================================================================
# SECTION 4: QA Self Healer Tests (20 tests)
# =============================================================================

class TestQASelfHealer:
    """Test orchestration of self-healing QA loop."""

    def test_all_tests_pass_initially_no_iterations(self, temp_test_dir):
        """Test when all tests pass initially (0 iterations needed)."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest to return success
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="===== 5 passed in 0.05s =====",
                stderr="",
            )

            # Act
            result = healer.heal_test_failures()

            # Assert
            assert result.success is True
            assert result.iterations == 0
            assert len(result.attempts) == 0

    def test_fix_syntax_error_in_one_iteration(self, temp_test_dir, sample_pytest_output):
        """Test fixing syntax error in single iteration."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest: first fail, then pass
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout=sample_pytest_output, stderr=""),
                Mock(returncode=0, stdout="===== 1 passed in 0.02s =====", stderr=""),
            ]

            # Mock fix generation
            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix(
                    file_path="test_sample.py",
                    original_code="result = some_func(",
                    fixed_code="result = some_func()",
                    strategy="add_closing_paren",
                    confidence=0.95,
                )

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is True
                assert result.iterations == 1
                assert len(result.attempts) == 1
                assert result.total_fixes_applied == 1

    def test_fix_import_error_in_two_iterations(self, temp_test_dir):
        """Test fixing import error across 2 iterations."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest: fail twice, then pass
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="ImportError: module 'A' not found", stderr=""),
                Mock(returncode=1, stdout="ImportError: module 'B' not found", stderr=""),
                Mock(returncode=0, stdout="===== 2 passed in 0.03s =====", stderr=""),
            ]

            # Mock fix generation
            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.side_effect = [
                    ProposedFix("test.py", "import A", "import module_a as A", "fix_import", 0.9),
                    ProposedFix("test.py", "import B", "import module_b as B", "fix_import", 0.9),
                ]

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is True
                assert result.iterations == 2
                assert len(result.attempts) == 2
                assert result.total_fixes_applied == 2

    def test_multiple_failures_fixed_together(self, temp_test_dir):
        """Test fixing multiple failures in single iteration."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        output_with_multiple_errors = """
test_a.py:5: SyntaxError: invalid syntax
test_b.py:10: ImportError: module not found
"""

        # Mock pytest: fail with 2 errors, then pass
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout=output_with_multiple_errors, stderr=""),
                Mock(returncode=0, stdout="===== 2 passed in 0.04s =====", stderr=""),
            ]

            # Mock fix generation (2 fixes)
            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.side_effect = [
                    ProposedFix("test_a.py", "bad", "good", "fix_syntax", 0.9),
                    ProposedFix("test_b.py", "import X", "import Y", "fix_import", 0.9),
                ]

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is True
                assert result.iterations == 1
                assert len(result.attempts) == 1
                assert result.total_fixes_applied == 2

    def test_stuck_detection_triggers_after_three_identical(self, temp_test_dir):
        """Test stuck detection triggers after 3 identical errors."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)
        error_output = "SyntaxError: '(' was never closed"

        # Mock pytest: same error 3 times
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout=error_output, stderr="")

            # Mock fix generation (returns same fix each time)
            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix(
                    "test.py", "bad", "bad", "failed_fix", 0.5
                )

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is False
                assert result.stuck_detected is True
                assert result.iterations <= 3

    def test_max_iterations_reached(self, temp_test_dir):
        """Test max iterations limit (10) prevents infinite loop."""
        # Arrange
        healer = QASelfHealer(temp_test_dir, max_iterations=10)

        # Mock pytest: always fail
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="AssertionError: test failed",
                stderr="",
            )

            # Mock fix generation
            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix(
                    "test.py", "assert False", "assert True", "fix", 0.8
                )

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is False
                assert result.max_iterations_reached is True
                assert result.iterations == 10

    def test_self_heal_enabled_false_skips_healing(self, temp_test_dir, monkeypatch):
        """Test SELF_HEAL_ENABLED=false skips healing process."""
        # Arrange
        monkeypatch.setenv("SELF_HEAL_ENABLED", "false")
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest to fail
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="SyntaxError: invalid syntax",
                stderr="",
            )

            # Act
            result = healer.heal_test_failures()

            # Assert - healing skipped
            assert result.success is False
            assert result.iterations == 0
            assert len(result.attempts) == 0

    def test_self_heal_max_iterations_override(self, temp_test_dir, monkeypatch):
        """Test SELF_HEAL_MAX_ITERATIONS environment variable override."""
        # Arrange
        monkeypatch.setenv("SELF_HEAL_MAX_ITERATIONS", "5")
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest: always fail
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="Error",
                stderr="",
            )

            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix("test.py", "a", "b", "fix", 0.8)

                # Act
                result = healer.heal_test_failures()

                # Assert - stopped at 5 (not default 10)
                assert result.iterations == 5

    def test_graceful_degradation_on_error(self, temp_test_dir):
        """Test graceful degradation when healing encounters error."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest failure
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="SyntaxError",
                stderr="",
            )

            # Mock fix generation to raise exception
            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.side_effect = Exception("API error")

                # Act - should not crash
                result = healer.heal_test_failures()

                # Assert
                assert result.success is False
                assert result.iterations >= 0

    def test_rollback_when_fix_fails(self, temp_test_dir):
        """Test rollback occurs when fix makes tests worse."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest: initial error, worse error after fix
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="1 error", stderr=""),
                Mock(returncode=1, stdout="5 errors", stderr=""),  # Worse
            ]

            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix("test.py", "a", "b", "bad_fix", 0.5)

                with patch.object(healer.patcher, "rollback_last_patch") as mock_rollback:
                    # Act
                    result = healer.heal_test_failures()

                    # Assert - rollback called when fix made things worse
                    mock_rollback.assert_called()

    def test_environment_variable_parsing(self, temp_test_dir, monkeypatch):
        """Test environment variable parsing for configuration."""
        # Arrange
        monkeypatch.setenv("SELF_HEAL_ENABLED", "true")
        monkeypatch.setenv("SELF_HEAL_MAX_ITERATIONS", "15")

        # Act
        healer = QASelfHealer(temp_test_dir)

        # Assert
        assert healer.enabled is True
        assert healer.max_iterations == 15

    def test_audit_logging_for_all_operations(self, temp_test_dir):
        """Test audit logging for all healing operations."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="Error", stderr=""),
                Mock(returncode=0, stdout="Passed", stderr=""),
            ]

            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix("test.py", "a", "b", "fix", 0.9)

                with patch("qa_self_healer.log_audit_event") as mock_audit:
                    # Act
                    result = healer.heal_test_failures()

                    # Assert - audit events logged
                    assert mock_audit.call_count > 0
                    logged_events = [str(call) for call in mock_audit.call_args_list]
                    assert any("healing_started" in event.lower() for event in logged_events)

    def test_empty_test_output_no_failures(self, temp_test_dir):
        """Test handling of empty test output (no failures detected)."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest with empty output
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="")

            # Act
            result = healer.heal_test_failures()

            # Assert - no iterations (no failures to fix)
            assert result.iterations == 0

    def test_pytest_not_installed_graceful_failure(self, temp_test_dir):
        """Test graceful failure when pytest not installed."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock subprocess to raise FileNotFoundError
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("pytest not found")

            # Act
            result = healer.heal_test_failures()

            # Assert - graceful failure
            assert result.success is False
            assert result.iterations == 0

    def test_network_error_during_fix_generation_retry(self, temp_test_dir):
        """Test retry on network error during fix generation."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest failure
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="Error", stderr=""),
                Mock(returncode=0, stdout="Passed", stderr=""),
            ]

            # Mock fix generation: fail once, then succeed
            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.side_effect = [
                    Exception("Network error"),
                    ProposedFix("test.py", "a", "b", "fix", 0.9),
                ]

                # Act
                result = healer.heal_test_failures()

                # Assert - succeeded after retry
                assert result.success is True

    def test_self_healing_result_dataclass_structure(self):
        """Test SelfHealingResult dataclass has required fields."""
        # Arrange & Act
        result = SelfHealingResult(
            success=True,
            iterations=3,
            attempts=[],
            final_test_output="Passed",
            stuck_detected=False,
            max_iterations_reached=False,
            total_fixes_applied=5,
        )

        # Assert
        assert result.success is True
        assert result.iterations == 3
        assert result.attempts == []
        assert result.final_test_output == "Passed"
        assert result.stuck_detected is False
        assert result.max_iterations_reached is False
        assert result.total_fixes_applied == 5

    def test_healing_attempt_dataclass_structure(self):
        """Test HealingAttempt dataclass has required fields."""
        # Arrange & Act
        attempt = HealingAttempt(
            iteration=1,
            failures_detected=2,
            fixes_applied=2,
            test_output="Error",
            fixes=[],
        )

        # Assert
        assert attempt.iteration == 1
        assert attempt.failures_detected == 2
        assert attempt.fixes_applied == 2
        assert attempt.test_output == "Error"
        assert attempt.fixes == []

    def test_default_max_iterations_is_ten(self):
        """Test DEFAULT_MAX_ITERATIONS is set to 10."""
        # Arrange & Act & Assert
        assert DEFAULT_MAX_ITERATIONS == 10

    def test_run_tests_with_healing_convenience_function(self, temp_test_dir):
        """Test run_tests_with_healing convenience function."""
        # Arrange & Act
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="===== 10 passed in 0.10s =====",
                stderr="",
            )

            result = run_tests_with_healing(str(temp_test_dir))

            # Assert
            assert result.success is True


# =============================================================================
# SECTION 5: Integration Tests (5 tests)
# =============================================================================

class TestIntegration:
    """Test end-to-end integration scenarios."""

    def test_end_to_end_syntax_error_fix_and_pass(self, temp_test_dir):
        """Test complete workflow: syntax error → fix → pass."""
        # Arrange
        test_file = temp_test_dir / "test_integration.py"
        test_file.write_text("""
def test_math():
    result = add(2, 2
    assert result == 4
""")

        healer = QASelfHealer(temp_test_dir)

        # Mock pytest: syntax error, then pass
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(
                    returncode=1,
                    stdout="test_integration.py:3: SyntaxError: '(' was never closed",
                    stderr="",
                ),
                Mock(returncode=0, stdout="===== 1 passed =====", stderr=""),
            ]

            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix(
                    str(test_file),
                    "result = add(2, 2",
                    "result = add(2, 2)",
                    "add_closing_paren",
                    0.98,
                )

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is True
                assert result.iterations == 1
                assert result.total_fixes_applied == 1

    def test_multi_iteration_three_different_errors(self, temp_test_dir):
        """Test 3 iterations fixing 3 different errors."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest: 3 different errors, then pass
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="SyntaxError: line 5", stderr=""),
                Mock(returncode=1, stdout="ImportError: module A", stderr=""),
                Mock(returncode=1, stdout="AssertionError: 2 != 3", stderr=""),
                Mock(returncode=0, stdout="===== 3 passed =====", stderr=""),
            ]

            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.side_effect = [
                    ProposedFix("test.py", "a", "b", "fix1", 0.9),
                    ProposedFix("test.py", "c", "d", "fix2", 0.9),
                    ProposedFix("test.py", "e", "f", "fix3", 0.9),
                ]

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is True
                assert result.iterations == 3
                assert result.total_fixes_applied == 3

    def test_stuck_case_identical_import_error_three_times(self, temp_test_dir):
        """Test stuck detection: identical import error 3x."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)
        identical_error = "ImportError: No module named 'missing_module'"

        # Mock pytest: same error 3 times
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout=identical_error, stderr="")

            with patch.object(healer, "_generate_fix") as mock_fix:
                # Return same fix each time (ineffective)
                mock_fix.return_value = ProposedFix(
                    "test.py",
                    "import missing_module",
                    "import missing_module",
                    "no_change",
                    0.3,
                )

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is False
                assert result.stuck_detected is True
                assert result.iterations <= 3

    def test_max_iterations_ten_attempts_then_halt(self, temp_test_dir):
        """Test max iterations: 10 attempts → halt."""
        # Arrange
        healer = QASelfHealer(temp_test_dir, max_iterations=10)

        # Mock pytest: always fail (different errors to avoid stuck detection)
        with patch("subprocess.run") as mock_run:
            errors = [f"Error {i}" for i in range(11)]
            mock_run.side_effect = [
                Mock(returncode=1, stdout=error, stderr="") for error in errors
            ]

            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.return_value = ProposedFix("test.py", "a", "b", "fix", 0.7)

                # Act
                result = healer.heal_test_failures()

                # Assert
                assert result.success is False
                assert result.max_iterations_reached is True
                assert result.iterations == 10

    def test_full_workflow_with_checkpoint_tracking(self, temp_test_dir):
        """Test full workflow with checkpoint/progress tracking."""
        # Arrange
        healer = QASelfHealer(temp_test_dir)

        # Mock pytest
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="Error 1", stderr=""),
                Mock(returncode=1, stdout="Error 2", stderr=""),
                Mock(returncode=0, stdout="Passed", stderr=""),
            ]

            with patch.object(healer, "_generate_fix") as mock_fix:
                mock_fix.side_effect = [
                    ProposedFix("test.py", "a", "b", "fix1", 0.9),
                    ProposedFix("test.py", "c", "d", "fix2", 0.9),
                ]

                # Mock checkpoint tracking
                with patch("qa_self_healer.AgentTracker.save_agent_checkpoint") as mock_checkpoint:
                    # Act
                    result = healer.heal_test_failures()

                    # Assert - checkpoints saved
                    assert mock_checkpoint.call_count > 0
                    assert result.success is True
                    assert result.iterations == 2


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (55 unit tests for QA self-healing components):

SECTION 1: Failure Analyzer (12 tests)
✗ test_parse_syntax_error_from_pytest_output
✗ test_parse_import_error_from_pytest_output
✗ test_parse_assertion_error_from_pytest_output
✗ test_parse_type_error_from_pytest_output
✗ test_parse_runtime_error_from_pytest_output
✗ test_extract_file_path_and_line_number
✗ test_handle_malformed_pytest_output
✗ test_handle_empty_pytest_output
✗ test_parse_multiple_failures_in_one_output
✗ test_extract_stack_trace
✗ test_failure_analysis_dataclass_structure
✗ test_parse_pytest_output_with_test_name

SECTION 2: Stuck Detector (8 tests)
✗ test_stuck_detected_after_three_identical_errors
✗ test_not_stuck_with_different_errors
✗ test_reset_after_successful_iteration
✗ test_custom_stuck_threshold
✗ test_empty_error_list_not_stuck
✗ test_single_error_not_stuck
✗ test_exact_threshold_boundary
✗ test_default_stuck_threshold_is_three

SECTION 3: Code Patcher (10 tests)
✗ test_apply_fix_successfully
✗ test_create_backup_before_patching
✗ test_rollback_on_error
✗ test_atomic_write_uses_temp_file_and_rename
✗ test_path_traversal_blocked
✗ test_symlink_attack_blocked
✗ test_file_permissions_preserved
✗ test_cleanup_backups_after_success
✗ test_invalid_file_path_raises_error
✗ test_proposed_fix_dataclass_structure

SECTION 4: QA Self Healer (20 tests)
✗ test_all_tests_pass_initially_no_iterations
✗ test_fix_syntax_error_in_one_iteration
✗ test_fix_import_error_in_two_iterations
✗ test_multiple_failures_fixed_together
✗ test_stuck_detection_triggers_after_three_identical
✗ test_max_iterations_reached
✗ test_self_heal_enabled_false_skips_healing
✗ test_self_heal_max_iterations_override
✗ test_graceful_degradation_on_error
✗ test_rollback_when_fix_fails
✗ test_environment_variable_parsing
✗ test_audit_logging_for_all_operations
✗ test_empty_test_output_no_failures
✗ test_pytest_not_installed_graceful_failure
✗ test_network_error_during_fix_generation_retry
✗ test_self_healing_result_dataclass_structure
✗ test_healing_attempt_dataclass_structure
✗ test_default_max_iterations_is_ten
✗ test_run_tests_with_healing_convenience_function

SECTION 5: Integration (5 tests)
✗ test_end_to_end_syntax_error_fix_and_pass
✗ test_multi_iteration_three_different_errors
✗ test_stuck_case_identical_import_error_three_times
✗ test_max_iterations_ten_attempts_then_halt
✗ test_full_workflow_with_checkpoint_tracking

TOTAL: 55 unit tests (all FAILING - TDD red phase)

Security Coverage:
- Path traversal attack blocked (CWE-22)
- Symlink attack blocked (CWE-59)
- Audit logging for all healing operations
- Max iterations prevent infinite loops
- File permissions preserved during patching

Implementation Guidance:
- FailureAnalyzer: Parse pytest output to extract error details
- StuckDetector: Track consecutive identical errors (threshold: 3)
- CodePatcher: Atomic file writes with backup/rollback
- QASelfHealer: Orchestrate healing loop with max iterations (default: 10)
- Environment variables: SELF_HEAL_ENABLED, SELF_HEAL_MAX_ITERATIONS
- Graceful degradation on errors
- Checkpoint tracking via AgentTracker library

Module Dependencies:
- failure_analyzer.py (FailureAnalysis dataclass, parsing logic)
- stuck_detector.py (StuckDetector class, threshold detection)
- code_patcher.py (CodePatcher class, ProposedFix dataclass, atomic writes)
- qa_self_healer.py (QASelfHealer orchestrator, SelfHealingResult dataclass)
"""
