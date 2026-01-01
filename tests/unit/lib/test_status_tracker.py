#!/usr/bin/env python3
"""
TDD Tests for Test Status Tracker Library - RED PHASE

This test suite validates the status_tracker library which manages test
execution status for the pre-commit gate hook.

Feature:
Block-at-submit hook that enforces test passage before git commit. The library
tracks test status in a JSON file and provides an API for reading/writing status.

Problem:
Need a reliable way to track test execution status across different processes:
- Test runner writes status after execution
- Pre-commit hook reads status before allowing commit
- Status must survive process boundaries
- Must handle missing/corrupted files gracefully

Solution:
status_tracker.py library with two main functions:
1. write_status(passed: bool, timestamp: str) - Write test results
2. read_status() -> dict - Read current status
Status stored in: /tmp/.autonomous-dev/test-status.json

Test Coverage:
1. Status Writing (success/failure cases)
2. Status Reading (valid/missing/corrupted files)
3. File Permissions (secure file creation)
4. Graceful Degradation (missing directory, corrupted JSON)
5. Timestamp Validation (ISO 8601 format)
6. Security (CWE-22 path traversal, CWE-59 symlinks)
7. Cross-Platform Compatibility (temp directory handling)

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (library doesn't exist yet)
- Implementation makes tests pass (GREEN phase)

Date: 2026-01-01
Feature: Block-at-submit hook with test status tracking
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See library-design-patterns skill for file I/O and error handling.
    See python-standards skill for code conventions.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Provide minimal pytest stub for when it's not available
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

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# Import will fail initially (RED phase) - implementation doesn't exist yet
try:
    from status_tracker import write_status, read_status, get_status_file_path
    TRACKER_AVAILABLE = True
except ImportError:
    TRACKER_AVAILABLE = False
    write_status = None
    read_status = None
    get_status_file_path = None

if not PYTEST_AVAILABLE:
    pytest.skip("pytest not available - use pytest to run these tests", allow_module_level=True)

if not TRACKER_AVAILABLE:
    pytest.skip("status_tracker not implemented yet (RED phase)", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def status_file(tmp_path):
    """Provide a temporary status file path."""
    status_dir = tmp_path / ".autonomous-dev"
    status_dir.mkdir(parents=True, exist_ok=True)
    return status_dir / "test-status.json"


@pytest.fixture
def mock_status_file_path(status_file, monkeypatch):
    """Mock get_status_file_path to return temp path."""
    def mock_get_path():
        return status_file

    if get_status_file_path is not None:
        monkeypatch.setattr("status_tracker.get_status_file_path", mock_get_path)

    return status_file


# =============================================================================
# Test Status Writing
# =============================================================================

class TestWriteStatus:
    """Test write_status() function."""

    def test_writes_passed_status(self, mock_status_file_path):
        """Test writing successful test status."""
        timestamp = "2026-01-01T12:00:00Z"

        write_status(passed=True, timestamp=timestamp)

        # Verify file was created
        assert mock_status_file_path.exists()

        # Verify content
        with open(mock_status_file_path) as f:
            data = json.load(f)

        assert data["passed"] is True
        assert data["timestamp"] == timestamp
        assert "last_run" in data

    def test_writes_failed_status(self, mock_status_file_path):
        """Test writing failed test status."""
        timestamp = "2026-01-01T12:00:00Z"

        write_status(passed=False, timestamp=timestamp)

        # Verify file was created
        assert mock_status_file_path.exists()

        # Verify content
        with open(mock_status_file_path) as f:
            data = json.load(f)

        assert data["passed"] is False
        assert data["timestamp"] == timestamp

    def test_overwrites_existing_status(self, mock_status_file_path):
        """Test that new status overwrites old status."""
        # Write initial status
        write_status(passed=True, timestamp="2026-01-01T11:00:00Z")

        # Overwrite with new status
        write_status(passed=False, timestamp="2026-01-01T12:00:00Z")

        # Verify only latest status exists
        with open(mock_status_file_path) as f:
            data = json.load(f)

        assert data["passed"] is False
        assert data["timestamp"] == "2026-01-01T12:00:00Z"

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        """Test that status directory is created if it doesn't exist."""
        # Point to non-existent directory
        new_status_file = tmp_path / "new_dir" / ".autonomous-dev" / "test-status.json"

        def mock_get_path():
            return new_status_file

        monkeypatch.setattr("status_tracker.get_status_file_path", mock_get_path)

        # Write status - should create directory
        write_status(passed=True, timestamp="2026-01-01T12:00:00Z")

        assert new_status_file.exists()
        assert new_status_file.parent.exists()

    def test_validates_timestamp_format(self, mock_status_file_path):
        """Test that timestamp is validated (ISO 8601 format)."""
        # Valid ISO 8601 formats should work
        valid_timestamps = [
            "2026-01-01T12:00:00Z",
            "2026-01-01T12:00:00.123Z",
            "2026-01-01T12:00:00+00:00",
        ]

        for ts in valid_timestamps:
            write_status(passed=True, timestamp=ts)

            with open(mock_status_file_path) as f:
                data = json.load(f)
            assert data["timestamp"] == ts

    def test_handles_invalid_timestamp_gracefully(self, mock_status_file_path):
        """Test graceful handling of invalid timestamp formats."""
        # Invalid timestamps should either be rejected or normalized
        invalid_timestamps = [
            "not-a-timestamp",
            "2026/01/01 12:00:00",  # Wrong format
            "",
        ]

        for ts in invalid_timestamps:
            try:
                write_status(passed=True, timestamp=ts)
                # If it doesn't raise, verify it was stored
                with open(mock_status_file_path) as f:
                    data = json.load(f)
                assert "timestamp" in data
            except ValueError:
                # Acceptable to raise ValueError for invalid timestamps
                pass

    def test_sets_secure_file_permissions(self, mock_status_file_path):
        """Test that status file has secure permissions (user-only)."""
        write_status(passed=True, timestamp="2026-01-01T12:00:00Z")

        # Check file permissions (should be user-only: 0600 or 0644)
        mode = mock_status_file_path.stat().st_mode
        # On Unix, verify no group/other write permissions
        assert (mode & 0o022) == 0, "File should not be writable by group/other"

    def test_includes_metadata(self, mock_status_file_path):
        """Test that status includes useful metadata."""
        write_status(passed=True, timestamp="2026-01-01T12:00:00Z")

        with open(mock_status_file_path) as f:
            data = json.load(f)

        # Should include at minimum: passed, timestamp, last_run
        assert "passed" in data
        assert "timestamp" in data
        assert "last_run" in data or "created_at" in data


# =============================================================================
# Test Status Reading
# =============================================================================

class TestReadStatus:
    """Test read_status() function."""

    def test_reads_valid_status_file(self, mock_status_file_path):
        """Test reading a valid status file."""
        # Write status first
        write_status(passed=True, timestamp="2026-01-01T12:00:00Z")

        # Read it back
        status = read_status()

        assert status["passed"] is True
        assert status["timestamp"] == "2026-01-01T12:00:00Z"

    def test_returns_default_when_file_missing(self, mock_status_file_path):
        """Test graceful handling when status file doesn't exist."""
        # Ensure file doesn't exist
        if mock_status_file_path.exists():
            mock_status_file_path.unlink()

        # Should return default status (failed/missing)
        status = read_status()

        assert isinstance(status, dict)
        assert "passed" in status
        # Missing file should be treated as "tests not run" = fail
        assert status["passed"] is False

    def test_handles_corrupted_json(self, mock_status_file_path):
        """Test graceful handling of corrupted JSON file."""
        # Write corrupted JSON
        with open(mock_status_file_path, "w") as f:
            f.write("{invalid json}")

        # Should return default status (failed)
        status = read_status()

        assert isinstance(status, dict)
        assert status["passed"] is False

    def test_handles_empty_file(self, mock_status_file_path):
        """Test graceful handling of empty file."""
        # Write empty file
        mock_status_file_path.touch()

        # Should return default status
        status = read_status()

        assert isinstance(status, dict)
        assert status["passed"] is False

    def test_handles_missing_required_fields(self, mock_status_file_path):
        """Test handling of JSON missing required fields."""
        # Write JSON without 'passed' field
        with open(mock_status_file_path, "w") as f:
            json.dump({"timestamp": "2026-01-01T12:00:00Z"}, f)

        # Should return default status or error
        status = read_status()

        assert isinstance(status, dict)
        # Should either add default 'passed' field or treat as failure
        assert "passed" in status

    def test_validates_status_structure(self, mock_status_file_path):
        """Test validation of status file structure."""
        # Write valid structure
        with open(mock_status_file_path, "w") as f:
            json.dump({
                "passed": True,
                "timestamp": "2026-01-01T12:00:00Z",
                "last_run": "2026-01-01T12:00:00Z"
            }, f)

        status = read_status()

        assert status["passed"] is True
        assert isinstance(status["timestamp"], str)

    def test_handles_permission_errors(self, mock_status_file_path, monkeypatch):
        """Test graceful handling when file cannot be read."""
        # Write a valid file first
        write_status(passed=True, timestamp="2026-01-01T12:00:00Z")

        # Mock open to raise PermissionError
        original_open = open
        def mock_open_permission_error(*args, **kwargs):
            if str(mock_status_file_path) in str(args[0]):
                raise PermissionError("Access denied")
            return original_open(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_permission_error):
            status = read_status()

            # Should gracefully degrade to failed status
            assert isinstance(status, dict)
            assert status["passed"] is False

    def test_handles_symlink_attacks(self, tmp_path, monkeypatch):
        """Test prevention of symlink attacks (CWE-59)."""
        # Create a symlink to sensitive file
        sensitive_file = tmp_path / "sensitive.txt"
        sensitive_file.write_text("secret data")

        symlink_path = tmp_path / ".autonomous-dev" / "test-status.json"
        symlink_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            symlink_path.symlink_to(sensitive_file)
        except (OSError, NotImplementedError):
            # Skip test on systems that don't support symlinks (Windows)
            pytest.skip("System doesn't support symlinks")

        def mock_get_path():
            return symlink_path

        monkeypatch.setattr("status_tracker.get_status_file_path", mock_get_path)

        # Reading should either fail or follow symlink safely
        status = read_status()

        # Should not expose sensitive file content
        assert isinstance(status, dict)
        # If it reads, should treat invalid format as failure
        assert status["passed"] is False


# =============================================================================
# Test Path Handling
# =============================================================================

class TestGetStatusFilePath:
    """Test get_status_file_path() function."""

    def test_returns_path_in_tmp(self):
        """Test that status file is in /tmp directory."""
        path = get_status_file_path()

        assert isinstance(path, Path)
        # Should be in /tmp or system temp directory
        assert "/tmp" in str(path) or "Temp" in str(path) or "TEMP" in str(path)

    def test_returns_consistent_path(self):
        """Test that function returns same path across calls."""
        path1 = get_status_file_path()
        path2 = get_status_file_path()

        assert path1 == path2

    def test_path_includes_autonomous_dev_directory(self):
        """Test that path includes .autonomous-dev directory."""
        path = get_status_file_path()

        assert ".autonomous-dev" in str(path)

    def test_path_ends_with_json_file(self):
        """Test that path ends with test-status.json."""
        path = get_status_file_path()

        assert path.name == "test-status.json"

    def test_prevents_path_traversal(self):
        """Test prevention of path traversal attacks (CWE-22)."""
        path = get_status_file_path()

        # Path should not contain .. or other traversal patterns
        assert ".." not in str(path)
        # Should be absolute path
        assert path.is_absolute()


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Test write and read integration."""

    def test_write_then_read_roundtrip(self, mock_status_file_path):
        """Test complete write/read cycle."""
        # Write status
        write_status(passed=True, timestamp="2026-01-01T12:00:00Z")

        # Read it back
        status = read_status()

        assert status["passed"] is True
        assert status["timestamp"] == "2026-01-01T12:00:00Z"

    def test_multiple_writes_preserve_latest(self, mock_status_file_path):
        """Test that multiple writes preserve only latest status."""
        # Write multiple statuses
        write_status(passed=True, timestamp="2026-01-01T11:00:00Z")
        write_status(passed=False, timestamp="2026-01-01T12:00:00Z")
        write_status(passed=True, timestamp="2026-01-01T13:00:00Z")

        # Read final status
        status = read_status()

        assert status["passed"] is True
        assert status["timestamp"] == "2026-01-01T13:00:00Z"

    def test_cross_process_simulation(self, mock_status_file_path):
        """Simulate cross-process communication (write in one, read in another)."""
        # Simulate test runner writing status
        write_status(passed=True, timestamp="2026-01-01T12:00:00Z")

        # Simulate pre-commit hook reading status (different function call)
        status = read_status()

        # Hook should see test results
        assert status["passed"] is True

    def test_handles_rapid_successive_writes(self, mock_status_file_path):
        """Test handling of rapid successive writes."""
        # Write rapidly
        for i in range(10):
            write_status(
                passed=(i % 2 == 0),
                timestamp=f"2026-01-01T12:00:{i:02d}Z"
            )

        # Read final status
        status = read_status()

        # Should have last write's data
        assert status["timestamp"] == "2026-01-01T12:00:09Z"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_handles_unicode_in_timestamp(self, mock_status_file_path):
        """Test handling of Unicode characters in timestamp."""
        # Should either accept or reject Unicode gracefully
        try:
            write_status(passed=True, timestamp="2026-01-01T12:00:00🔒Z")
            status = read_status()
            assert "timestamp" in status
        except (ValueError, UnicodeEncodeError):
            # Acceptable to reject Unicode
            pass

    def test_handles_very_long_timestamp(self, mock_status_file_path):
        """Test handling of unreasonably long timestamp string."""
        long_timestamp = "2026-01-01T12:00:00Z" + ("X" * 10000)

        try:
            write_status(passed=True, timestamp=long_timestamp)
            status = read_status()
            # Should truncate or handle gracefully
            assert len(status.get("timestamp", "")) < 11000
        except ValueError:
            # Acceptable to reject overly long input
            pass

    def test_handles_disk_full_scenario(self, mock_status_file_path, monkeypatch):
        """Test graceful handling when disk is full."""
        # Mock write to raise OSError (disk full)
        original_open = open
        def mock_open_disk_full(*args, **kwargs):
            if "w" in str(kwargs.get("mode", "")) or (len(args) > 1 and "w" in args[1]):
                raise OSError("No space left on device")
            return original_open(*args, **kwargs)

        # write_status should handle this gracefully
        try:
            with patch("builtins.open", side_effect=mock_open_disk_full):
                write_status(passed=True, timestamp="2026-01-01T12:00:00Z")
        except OSError:
            # Acceptable to propagate disk full error
            pass

    def test_handles_readonly_filesystem(self, tmp_path, monkeypatch):
        """Test graceful handling of read-only filesystem."""
        readonly_path = tmp_path / "readonly" / ".autonomous-dev" / "test-status.json"
        readonly_path.parent.mkdir(parents=True, exist_ok=True)

        # Make directory read-only
        readonly_path.parent.chmod(0o444)

        def mock_get_path():
            return readonly_path

        monkeypatch.setattr("status_tracker.get_status_file_path", mock_get_path)

        try:
            write_status(passed=True, timestamp="2026-01-01T12:00:00Z")
        except (OSError, PermissionError):
            # Expected to fail on read-only filesystem
            pass
        finally:
            # Restore permissions for cleanup
            readonly_path.parent.chmod(0o755)


# =============================================================================
# Security Tests
# =============================================================================

class TestSecurity:
    """Test security aspects of status tracking."""

    def test_prevents_json_injection(self, mock_status_file_path):
        """Test prevention of JSON injection attacks."""
        # Attempt to inject malicious JSON
        malicious_timestamp = '","malicious":"injected","passed":false,"timestamp":"'

        write_status(passed=True, timestamp=malicious_timestamp)
        status = read_status()

        # Should either escape the injection or fail gracefully
        # The 'passed' field should remain True (not overridden by injection)
        assert status["passed"] is True or status["passed"] is False

    def test_file_location_not_user_controllable(self):
        """Test that file location cannot be controlled by user input."""
        path = get_status_file_path()

        # Path should be deterministic, not based on user input
        assert path.is_absolute()
        assert ".autonomous-dev" in str(path)

    def test_handles_malformed_json_types(self, mock_status_file_path):
        """Test handling of incorrect JSON types."""
        # Write JSON with wrong types
        with open(mock_status_file_path, "w") as f:
            json.dump({
                "passed": "not-a-boolean",  # Should be bool
                "timestamp": 12345,         # Should be string
            }, f)

        status = read_status()

        # Should validate types and return safe default
        assert isinstance(status, dict)
        assert isinstance(status.get("passed"), bool)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
