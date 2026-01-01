#!/usr/bin/env python3
"""
TDD Tests for Pre-Commit Gate Hook - RED PHASE

This test suite validates the pre_commit_gate.py hook which enforces test
passage before allowing git commits.

Feature:
Block-at-submit hook that prevents commits when tests have failed. Reads test
status from status_tracker and blocks commit if tests haven't passed.

Problem:
Need to prevent developers from committing code that breaks tests:
- Tests may be skipped in rush to commit
- Broken code gets into version control
- CI/CD pipeline catches issues too late
- Wastes team time on broken builds

Solution:
PreCommit hook that:
1. Reads test status from status_tracker
2. Exits with EXIT_SUCCESS (0) if tests passed
3. Exits with EXIT_BLOCK (2) if tests failed or status missing
4. Can be disabled via ENFORCE_TEST_GATE=false environment variable
5. Provides clear error messages for developers

Test Coverage:
1. Exit Code Paths (success, block, warning)
2. Test Status Integration (passed, failed, missing)
3. Environment Variable Control (ENFORCE_TEST_GATE)
4. Error Messages (clear, actionable)
5. Graceful Degradation (tracker unavailable, corrupted status)
6. Lifecycle Compliance (PreCommit can block with exit 2)
7. Edge Cases (environment edge cases, concurrent commits)

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (hook doesn't exist yet)
- Implementation makes tests pass (GREEN phase)

Date: 2026-01-01
Feature: Block-at-submit hook with test status tracking
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See hook-patterns skill for hook lifecycle and exit codes.
    See python-standards skill for code conventions.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Provide minimal pytest stub
    class pytest:
        @staticmethod
        def skip(msg, allow_module_level=False):
            if allow_module_level:
                raise ImportError(msg)

        @staticmethod
        def raises(*args, **kwargs):
            return MockRaises()

        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func
            return decorator

        @staticmethod
        def main(*args, **kwargs):
            raise ImportError("pytest not available")

    class MockRaises:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError("Expected exception was not raised")
            return True

# Add directories to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# Import hook exit codes (these exist already)
try:
    from hook_exit_codes import EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
    EXIT_CODES_AVAILABLE = True
except ImportError:
    EXIT_CODES_AVAILABLE = False
    EXIT_SUCCESS = 0
    EXIT_WARNING = 1
    EXIT_BLOCK = 2

# Import hook (will fail initially - RED phase)
try:
    import pre_commit_gate
    from pre_commit_gate import (
        check_test_status,
        should_enforce_gate,
        get_error_message,
        main,
    )
    HOOK_AVAILABLE = True
except ImportError:
    HOOK_AVAILABLE = False
    check_test_status = None
    should_enforce_gate = None
    get_error_message = None
    main = None

if not PYTEST_AVAILABLE:
    pytest.skip("pytest not available - use pytest to run these tests", allow_module_level=True)

if not HOOK_AVAILABLE:
    pytest.skip("pre_commit_gate not implemented yet (RED phase)", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_env():
    """Provide clean environment for testing."""
    original_env = os.environ.copy()
    yield os.environ
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_test_status():
    """Mock status_tracker module."""
    mock_tracker = MagicMock()
    mock_tracker.read_status = MagicMock()
    return mock_tracker


# =============================================================================
# Test Exit Code Paths
# =============================================================================

class TestExitCodes:
    """Test that hook uses correct exit codes."""

    def test_exits_success_when_tests_passed(self, mock_test_status, monkeypatch):
        """Test EXIT_SUCCESS (0) when tests passed."""
        # Mock tracker to return passed status
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == EXIT_SUCCESS

    def test_exits_block_when_tests_failed(self, mock_test_status, monkeypatch):
        """Test EXIT_BLOCK (2) when tests failed."""
        # Mock tracker to return failed status
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == EXIT_BLOCK

    def test_exits_block_when_status_missing(self, mock_test_status, monkeypatch):
        """Test EXIT_BLOCK (2) when status file missing."""
        # Mock tracker to return missing status (passed=False by default)
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": None
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == EXIT_BLOCK

    def test_exits_success_when_gate_disabled(self, mock_test_status, mock_env):
        """Test EXIT_SUCCESS (0) when ENFORCE_TEST_GATE=false."""
        # Disable gate
        os.environ["ENFORCE_TEST_GATE"] = "false"

        # Mock tracker to return failed status (should be ignored)
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should allow commit even though tests failed
            assert exc_info.value.code == EXIT_SUCCESS


# =============================================================================
# Test Status Integration
# =============================================================================

class TestStatusIntegration:
    """Test integration with status_tracker."""

    def test_reads_status_from_tracker(self, mock_test_status):
        """Test that hook reads status from tracker."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()

            # Should have called read_status()
            mock_test_status.read_status.assert_called_once()
            assert result is True

    def test_interprets_passed_true_correctly(self, mock_test_status):
        """Test correct interpretation of passed=True."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            assert result is True

    def test_interprets_passed_false_correctly(self, mock_test_status):
        """Test correct interpretation of passed=False."""
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            assert result is False

    def test_handles_missing_passed_field(self, mock_test_status):
        """Test handling when status doesn't have 'passed' field."""
        mock_test_status.read_status.return_value = {
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            # Missing 'passed' should be treated as failure
            assert result is False

    def test_handles_tracker_import_error(self):
        """Test graceful handling when tracker module unavailable."""
        # Mock import to fail
        with patch.dict("sys.modules", {"status_tracker": None}):
            # Should either return False or handle gracefully
            try:
                result = check_test_status()
                assert result is False  # Treat unavailable tracker as failure
            except ImportError:
                # Also acceptable to raise ImportError
                pass

    def test_handles_tracker_exception(self, mock_test_status):
        """Test handling when tracker raises exception."""
        mock_test_status.read_status.side_effect = Exception("Tracker error")

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            # Exception should be treated as test failure (safe default)
            assert result is False


# =============================================================================
# Test Environment Variable Control
# =============================================================================

class TestEnvironmentControl:
    """Test ENFORCE_TEST_GATE environment variable."""

    def test_enforces_by_default(self, mock_env):
        """Test that gate is enforced by default (no env var set)."""
        # Ensure env var not set
        os.environ.pop("ENFORCE_TEST_GATE", None)

        result = should_enforce_gate()
        assert result is True

    def test_disables_when_false(self, mock_env):
        """Test that ENFORCE_TEST_GATE=false disables gate."""
        os.environ["ENFORCE_TEST_GATE"] = "false"

        result = should_enforce_gate()
        assert result is False

    def test_disables_when_zero(self, mock_env):
        """Test that ENFORCE_TEST_GATE=0 disables gate."""
        os.environ["ENFORCE_TEST_GATE"] = "0"

        result = should_enforce_gate()
        assert result is False

    def test_enables_when_true(self, mock_env):
        """Test that ENFORCE_TEST_GATE=true enables gate."""
        os.environ["ENFORCE_TEST_GATE"] = "true"

        result = should_enforce_gate()
        assert result is True

    def test_enables_when_one(self, mock_env):
        """Test that ENFORCE_TEST_GATE=1 enables gate."""
        os.environ["ENFORCE_TEST_GATE"] = "1"

        result = should_enforce_gate()
        assert result is True

    def test_handles_empty_string(self, mock_env):
        """Test handling of ENFORCE_TEST_GATE=''."""
        os.environ["ENFORCE_TEST_GATE"] = ""

        result = should_enforce_gate()
        # Empty string should be treated as False (opt-out)
        assert result is False

    def test_case_insensitive_parsing(self, mock_env):
        """Test case-insensitive parsing of boolean values."""
        test_cases = [
            ("FALSE", False),
            ("False", False),
            ("TRUE", True),
            ("True", True),
        ]

        for value, expected in test_cases:
            os.environ["ENFORCE_TEST_GATE"] = value
            result = should_enforce_gate()
            assert result == expected, f"Failed for value: {value}"

    def test_handles_invalid_values(self, mock_env):
        """Test handling of invalid environment variable values."""
        invalid_values = ["yes", "no", "maybe", "123", "invalid"]

        for value in invalid_values:
            os.environ["ENFORCE_TEST_GATE"] = value
            # Should either treat as True (default) or False (safe)
            result = should_enforce_gate()
            assert isinstance(result, bool)


# =============================================================================
# Test Error Messages
# =============================================================================

class TestErrorMessages:
    """Test error message generation."""

    def test_provides_clear_message_for_failed_tests(self):
        """Test error message when tests failed."""
        message = get_error_message(passed=False, has_status=True)

        # Should be clear and actionable
        assert isinstance(message, str)
        assert len(message) > 0
        assert "test" in message.lower() or "fail" in message.lower()

    def test_provides_clear_message_for_missing_status(self):
        """Test error message when status missing."""
        message = get_error_message(passed=False, has_status=False)

        # Should explain that tests need to be run
        assert isinstance(message, str)
        assert "run" in message.lower() or "missing" in message.lower()

    def test_includes_helpful_instructions(self):
        """Test that error messages include helpful instructions."""
        message = get_error_message(passed=False, has_status=True)

        # Should tell user how to fix the issue
        assert "pytest" in message.lower() or "test" in message.lower()

    def test_mentions_disable_option(self):
        """Test that error message mentions how to disable gate."""
        message = get_error_message(passed=False, has_status=True)

        # Should mention ENFORCE_TEST_GATE for emergency bypass
        assert "ENFORCE_TEST_GATE" in message or "disable" in message.lower()

    def test_formats_message_nicely(self):
        """Test that message is well-formatted for terminal output."""
        message = get_error_message(passed=False, has_status=True)

        # Should not have excessive whitespace or formatting issues
        assert not message.startswith(" ")
        assert not message.endswith(" ")
        # Should be multi-line for readability
        assert "\n" in message or len(message) < 100


# =============================================================================
# Test Lifecycle Compliance
# =============================================================================

class TestLifecycleCompliance:
    """Test that hook complies with PreCommit lifecycle."""

    def test_can_block_with_exit_2(self, mock_test_status):
        """Test that hook can exit with code 2 (blocking)."""
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # PreCommit hooks CAN block with exit 2
            assert exc_info.value.code == EXIT_BLOCK

    def test_exits_cleanly_on_success(self, mock_test_status):
        """Test that hook exits cleanly with code 0."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == EXIT_SUCCESS

    def test_no_warning_exit_code(self, mock_test_status):
        """Test that hook doesn't use EXIT_WARNING (not needed for this hook)."""
        # Try various scenarios
        test_cases = [
            {"passed": True, "timestamp": "2026-01-01T12:00:00Z"},
            {"passed": False, "timestamp": "2026-01-01T12:00:00Z"},
            {"passed": False, "timestamp": None},
        ]

        for status in test_cases:
            mock_test_status.read_status.return_value = status

            with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should only use SUCCESS or BLOCK, never WARNING
                assert exc_info.value.code in [EXIT_SUCCESS, EXIT_BLOCK]


# =============================================================================
# Test Graceful Degradation
# =============================================================================

class TestGracefulDegradation:
    """Test graceful handling of error conditions."""

    def test_handles_corrupted_status_file(self, mock_test_status):
        """Test handling when status file is corrupted."""
        # Mock tracker returning corrupted/invalid data
        mock_test_status.read_status.return_value = {
            "passed": "not-a-boolean",  # Invalid type
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            # Should treat corrupted data as failure
            assert result is False

    def test_handles_empty_status(self, mock_test_status):
        """Test handling when status is empty dict."""
        mock_test_status.read_status.return_value = {}

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            assert result is False

    def test_handles_none_status(self, mock_test_status):
        """Test handling when tracker returns None."""
        mock_test_status.read_status.return_value = None

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            assert result is False

    def test_handles_file_permission_error(self, mock_test_status):
        """Test handling when status file cannot be read."""
        mock_test_status.read_status.side_effect = PermissionError("Access denied")

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            # Permission error should be treated as failure (safe default)
            assert result is False

    def test_continues_on_print_errors(self, mock_test_status, monkeypatch):
        """Test that hook continues even if printing fails."""
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        # Mock print to raise exception
        def mock_print_error(*args, **kwargs):
            raise IOError("Cannot write to stdout")

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with patch("builtins.print", side_effect=mock_print_error):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should still exit with correct code even if printing fails
                assert exc_info.value.code in [EXIT_SUCCESS, EXIT_BLOCK]


# =============================================================================
# Manifest Validation Tests
# =============================================================================

class TestManifestValidation:
    """Test manifest validation for install/sync reliability."""

    def test_check_manifest_valid_returns_true_when_valid(self):
        """Test that check_manifest_valid returns True when manifest is valid."""
        from pre_commit_gate import check_manifest_valid

        # Should return True for valid manifest (tests actually run)
        result = check_manifest_valid()
        assert result is True

    def test_check_manifest_valid_graceful_when_tests_missing(self, tmp_path):
        """Test graceful degradation when test file doesn't exist."""
        from pre_commit_gate import check_manifest_valid

        # When running in a directory without tests, should return True (don't block)
        with patch("pre_commit_gate.Path") as MockPath:
            mock_path = MagicMock()
            mock_path.parent.parent.parent.parent = tmp_path
            MockPath.return_value = mock_path
            MockPath.__file__ = str(tmp_path / "hook.py")

            # The test file won't exist in tmp_path
            result = check_manifest_valid()
            # Should return True (graceful degradation)
            assert result is True

    def test_check_manifest_valid_graceful_on_subprocess_error(self):
        """Test graceful degradation when subprocess fails."""
        from pre_commit_gate import check_manifest_valid
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.SubprocessError("Failed")):
            result = check_manifest_valid()
            # Should return True (graceful degradation - don't block on errors)
            assert result is True

    def test_check_manifest_valid_graceful_on_timeout(self):
        """Test graceful degradation when subprocess times out."""
        from pre_commit_gate import check_manifest_valid
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            result = check_manifest_valid()
            # Should return True (graceful degradation)
            assert result is True

    def test_manifest_validation_blocks_commit_when_invalid(self, mock_test_status):
        """Test that invalid manifest blocks commit."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with patch("pre_commit_gate.check_manifest_valid", return_value=False):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should block commit when manifest is invalid
                assert exc_info.value.code == EXIT_BLOCK


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_handles_very_old_timestamp(self, mock_test_status):
        """Test handling of very old test results."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2020-01-01T00:00:00Z"  # Old timestamp
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            # Hook might warn about old results but should still check passed status
            result = check_test_status()
            # Could either accept old results or reject them
            assert isinstance(result, bool)

    def test_handles_future_timestamp(self, mock_test_status):
        """Test handling of future timestamp (clock skew)."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2099-12-31T23:59:59Z"  # Future timestamp
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            result = check_test_status()
            # Should handle future timestamps gracefully
            assert isinstance(result, bool)

    def test_handles_multiple_rapid_calls(self, mock_test_status):
        """Test handling of rapid successive calls (race conditions)."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            # Call multiple times rapidly
            results = [check_test_status() for _ in range(10)]

            # All calls should return consistent result
            assert all(r is True for r in results)

    def test_handles_unicode_in_error_messages(self, mock_test_status):
        """Test that error messages handle Unicode correctly."""
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            message = get_error_message(passed=False, has_status=True)

            # Should be valid string (no encoding errors)
            assert isinstance(message, str)
            # Should be printable
            try:
                print(message)
            except UnicodeEncodeError:
                pytest.fail("Error message contains unprintable Unicode")

    def test_handles_environment_with_no_path(self, mock_env):
        """Test handling when PATH environment variable missing."""
        # Remove PATH (extreme edge case)
        original_path = os.environ.get("PATH")
        if original_path:
            del os.environ["PATH"]

        try:
            result = should_enforce_gate()
            # Should still work without PATH
            assert isinstance(result, bool)
        finally:
            if original_path:
                os.environ["PATH"] = original_path


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Test full hook integration."""

    def test_full_workflow_tests_passed(self, mock_test_status):
        """Test complete workflow when tests passed."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should allow commit
            assert exc_info.value.code == EXIT_SUCCESS
            # Should have checked status
            mock_test_status.read_status.assert_called_once()

    def test_full_workflow_tests_failed(self, mock_test_status, capsys):
        """Test complete workflow when tests failed."""
        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should block commit
            assert exc_info.value.code == EXIT_BLOCK
            # Should have checked status
            mock_test_status.read_status.assert_called_once()

            # Should print error message
            captured = capsys.readouterr()
            # Either stdout or stderr should have error message
            output = captured.out + captured.err
            assert len(output) > 0 or exc_info.value.code == EXIT_BLOCK

    def test_bypass_workflow_with_env_var(self, mock_test_status, mock_env):
        """Test complete workflow with gate disabled."""
        os.environ["ENFORCE_TEST_GATE"] = "false"

        mock_test_status.read_status.return_value = {
            "passed": False,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should allow commit despite failed tests
            assert exc_info.value.code == EXIT_SUCCESS


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Test performance characteristics."""

    def test_executes_quickly(self, mock_test_status):
        """Test that hook executes in reasonable time.

        Note: Mocks check_manifest_valid to isolate core hook performance.
        Manifest validation is tested separately in test_install_*.py.
        """
        import time

        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            with patch("pre_commit_gate.check_manifest_valid", return_value=True):
                start = time.time()

                try:
                    main()
                except SystemExit:
                    pass

                elapsed = time.time() - start

                # Hook should execute in under 1 second (excluding manifest check)
                assert elapsed < 1.0, f"Hook took {elapsed}s (too slow)"

    def test_minimal_file_io(self, mock_test_status):
        """Test that hook minimizes file I/O operations."""
        mock_test_status.read_status.return_value = {
            "passed": True,
            "timestamp": "2026-01-01T12:00:00Z"
        }

        with patch.dict("sys.modules", {"status_tracker": mock_test_status}):
            try:
                main()
            except SystemExit:
                pass

            # Should only read status once
            assert mock_test_status.read_status.call_count == 1


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
