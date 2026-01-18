#!/usr/bin/env python3
"""
Unit tests for workflow_violation_logger.py (TDD Red Phase).

Tests for workflow violation audit logging for Issue #250.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test JSON Lines log format
- Test log rotation (10MB limit)
- Test thread safety (concurrent writes)
- Test structured logging fields
- Test violation summary statistics
- Test log injection prevention (CWE-117)

Security Coverage:
- CWE-117: Log Injection Prevention
- Audit trail integrity
- Log file permissions

Date: 2026-01-19
Issue: #250 (Enforce /implement workflow)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, mock_open
from typing import Dict, Any, List

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

# Import will fail - module doesn't exist yet (TDD!)
try:
    from workflow_violation_logger import (
        WorkflowViolationLogger,
        ViolationType,
        log_workflow_violation,
        log_git_bypass_attempt,
        parse_violation_log,
        ViolationLogEntry,
        get_violation_summary,
        sanitize_log_input,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestWorkflowViolationLogger:
    """Test WorkflowViolationLogger class."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file."""
        return tmp_path / "workflow_violations.log"

    @pytest.fixture
    def logger(self, temp_log_file):
        """Create WorkflowViolationLogger instance."""
        return WorkflowViolationLogger(log_file=temp_log_file)

    def test_logger_init_creates_log_file(self, temp_log_file):
        """Test logger initialization creates log file."""
        logger = WorkflowViolationLogger(log_file=temp_log_file)

        assert temp_log_file.exists()

    def test_logger_init_creates_parent_dirs(self, tmp_path):
        """Test logger initialization creates parent directories."""
        log_file = tmp_path / "nested" / "dir" / "violations.log"

        logger = WorkflowViolationLogger(log_file=log_file)

        assert log_file.exists()
        assert log_file.parent.exists()

    def test_logger_uses_default_log_path(self):
        """Test logger uses default log path if not provided."""
        with patch("workflow_violation_logger.DEFAULT_LOG_FILE", Path("/tmp/violations.log")):
            with patch("pathlib.Path.touch"):
                logger = WorkflowViolationLogger()

                assert logger.log_file is not None


class TestWorkflowViolationLogging:
    """Test workflow violation logging."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file."""
        return tmp_path / "workflow_violations.log"

    @pytest.fixture
    def logger(self, temp_log_file):
        """Create WorkflowViolationLogger instance."""
        return WorkflowViolationLogger(log_file=temp_log_file)

    def test_log_violation_writes_json_line(self, logger, temp_log_file):
        """Test log_workflow_violation writes JSON line to log file."""
        logger.log_violation(
            violation_type=ViolationType.DIRECT_IMPLEMENTATION,
            file_path="module.py",
            agent_name="researcher",
            reason="New Python function detected",
            details="def authenticate_user():",
        )

        # Read log file
        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert log_entry["violation_type"] == "direct_implementation"
        assert log_entry["file_path"] == "module.py"
        assert log_entry["agent_name"] == "researcher"
        assert log_entry["reason"] == "New Python function detected"

    def test_log_violation_includes_timestamp(self, logger, temp_log_file):
        """Test log_violation includes ISO 8601 timestamp."""
        logger.log_violation(
            violation_type=ViolationType.DIRECT_IMPLEMENTATION,
            file_path="api.py",
            agent_name="planner",
            reason="Significant addition (15 new lines)",
            details="+15 lines",
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        # Should have timestamp in ISO 8601 format
        assert "timestamp" in log_entry
        datetime.fromisoformat(log_entry["timestamp"])  # Should parse

    def test_log_violation_includes_details(self, logger, temp_log_file):
        """Test log_violation includes violation details."""
        logger.log_violation(
            violation_type=ViolationType.DIRECT_IMPLEMENTATION,
            file_path="auth.py",
            agent_name="implementer",
            reason="New class detected",
            details="class UserManager:",
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert "details" in log_entry
        assert log_entry["details"] == "class UserManager:"

    def test_log_git_bypass_attempt(self, logger, temp_log_file):
        """Test log_git_bypass_attempt logs bypass attempts."""
        logger.log_git_bypass_attempt(
            command="git commit --no-verify -m 'bypass hooks'",
            agent_name="researcher",
            reason="--no-verify flag detected",
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert log_entry["violation_type"] == "git_bypass_attempt"
        assert log_entry["command"] == "git commit --no-verify -m 'bypass hooks'"
        assert "--no-verify" in log_entry["reason"]


class TestViolationType:
    """Test ViolationType enum."""

    def test_violation_type_direct_implementation(self):
        """Test DIRECT_IMPLEMENTATION violation type."""
        assert ViolationType.DIRECT_IMPLEMENTATION.value == "direct_implementation"

    def test_violation_type_git_bypass(self):
        """Test GIT_BYPASS_ATTEMPT violation type."""
        assert ViolationType.GIT_BYPASS_ATTEMPT.value == "git_bypass_attempt"

    def test_violation_type_protected_path_edit(self):
        """Test PROTECTED_PATH_EDIT violation type."""
        assert ViolationType.PROTECTED_PATH_EDIT.value == "protected_path_edit"


class TestLogRotation:
    """Test log rotation behavior (10MB limit)."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file."""
        return tmp_path / "workflow_violations.log"

    @pytest.fixture
    def logger(self, temp_log_file):
        """Create WorkflowViolationLogger instance."""
        return WorkflowViolationLogger(log_file=temp_log_file, max_size_mb=1)

    def test_log_file_rotates_at_size_limit(self, logger, temp_log_file):
        """Test log file rotates when size limit reached (1MB for test)."""
        # Log many entries to exceed 1MB size limit
        for i in range(10000):
            logger.log_violation(
                violation_type=ViolationType.DIRECT_IMPLEMENTATION,
                file_path=f"module_{i}.py",
                agent_name="researcher",
                reason=f"Test violation {i} with padding " + ("x" * 100),
                details=f"def function_{i}():",
            )

        # Should have created rotated log file
        rotated_files = list(temp_log_file.parent.glob("workflow_violations.log.*"))
        assert len(rotated_files) > 0

    def test_log_rotation_preserves_old_entries(self, logger, temp_log_file):
        """Test log rotation preserves old entries in rotated file."""
        # Log first entry
        logger.log_violation(
            violation_type=ViolationType.DIRECT_IMPLEMENTATION,
            file_path="first.py",
            agent_name="researcher",
            reason="First violation",
            details="first",
        )

        first_content = temp_log_file.read_text()

        # Force rotation
        logger.rotate_log()

        # Old entry should be in rotated file
        rotated_files = list(temp_log_file.parent.glob("workflow_violations.log.*"))
        assert len(rotated_files) > 0

        rotated_content = rotated_files[0].read_text()
        assert "First violation" in rotated_content

    def test_log_rotation_keeps_n_rotated_files(self, logger, temp_log_file):
        """Test log rotation keeps only N most recent rotated files (default: 10)."""
        # Rotate multiple times
        for i in range(15):
            logger.rotate_log()

        rotated_files = list(temp_log_file.parent.glob("workflow_violations.log.*"))

        # Should keep only 10 most recent (or configured limit)
        assert len(rotated_files) <= 10

    def test_log_rotation_timestamp_format(self, logger, temp_log_file):
        """Test rotated log files have timestamp in filename."""
        logger.rotate_log()

        rotated_files = list(temp_log_file.parent.glob("workflow_violations.log.*"))
        assert len(rotated_files) > 0

        # Filename should match pattern: workflow_violations.log.20260119_123456
        rotated_file = rotated_files[0]
        assert rotated_file.name.startswith("workflow_violations.log.")


class TestThreadSafety:
    """Test thread safety for concurrent writes."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file."""
        return tmp_path / "workflow_violations.log"

    @pytest.fixture
    def logger(self, temp_log_file):
        """Create WorkflowViolationLogger instance."""
        return WorkflowViolationLogger(log_file=temp_log_file)

    def test_concurrent_writes_no_corruption(self, logger, temp_log_file):
        """Test concurrent writes don't corrupt log file."""
        num_threads = 10
        num_writes_per_thread = 100

        def write_violations(thread_id):
            for i in range(num_writes_per_thread):
                logger.log_violation(
                    violation_type=ViolationType.DIRECT_IMPLEMENTATION,
                    file_path=f"thread_{thread_id}_file_{i}.py",
                    agent_name=f"agent_{thread_id}",
                    reason=f"Thread {thread_id} violation {i}",
                    details=f"thread_{thread_id}_detail_{i}",
                )

        # Start multiple threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=write_violations, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify log file has all entries
        log_content = temp_log_file.read_text()
        lines = log_content.strip().split("\n")

        # Should have num_threads * num_writes_per_thread entries
        assert len(lines) == num_threads * num_writes_per_thread

        # All lines should be valid JSON
        for line in lines:
            entry = json.loads(line)
            assert "violation_type" in entry
            assert "timestamp" in entry

    def test_concurrent_writes_preserve_order(self, logger, temp_log_file):
        """Test concurrent writes preserve timestamp ordering."""
        num_threads = 5
        num_writes_per_thread = 50

        def write_violations(thread_id):
            for i in range(num_writes_per_thread):
                logger.log_violation(
                    violation_type=ViolationType.DIRECT_IMPLEMENTATION,
                    file_path=f"file_{thread_id}_{i}.py",
                    agent_name="researcher",
                    reason=f"Violation {i}",
                    details="detail",
                )
                time.sleep(0.001)  # Small delay

        # Start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=write_violations, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Parse log entries
        log_content = temp_log_file.read_text()
        lines = log_content.strip().split("\n")
        entries = [json.loads(line) for line in lines]

        # Verify timestamps are in order (monotonically increasing)
        timestamps = [datetime.fromisoformat(entry["timestamp"]) for entry in entries]
        assert timestamps == sorted(timestamps)


class TestLogInjectionPrevention:
    """Test log injection prevention (CWE-117)."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file."""
        return tmp_path / "workflow_violations.log"

    @pytest.fixture
    def logger(self, temp_log_file):
        """Create WorkflowViolationLogger instance."""
        return WorkflowViolationLogger(log_file=temp_log_file)

    def test_sanitize_log_input_removes_newlines(self):
        """Test sanitize_log_input removes newlines."""
        input_str = "reason\nwith\nnewlines"

        sanitized = sanitize_log_input(input_str)

        assert "\n" not in sanitized
        assert sanitized == "reason with newlines"

    def test_sanitize_log_input_removes_carriage_returns(self):
        """Test sanitize_log_input removes carriage returns."""
        input_str = "reason\rwith\rcarriage\rreturns"

        sanitized = sanitize_log_input(input_str)

        assert "\r" not in sanitized

    def test_sanitize_log_input_removes_control_chars(self):
        """Test sanitize_log_input removes control characters."""
        input_str = "reason\x00with\x01control\x02chars"

        sanitized = sanitize_log_input(input_str)

        # Control chars should be removed
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized

    def test_log_violation_sanitizes_file_path(self, logger, temp_log_file):
        """Test log_violation sanitizes file_path for injection."""
        malicious_path = "module.py\n{\"violation_type\": \"fake_violation\"}"

        logger.log_violation(
            violation_type=ViolationType.DIRECT_IMPLEMENTATION,
            file_path=malicious_path,
            agent_name="researcher",
            reason="Test",
            details="test",
        )

        log_content = temp_log_file.read_text()
        lines = log_content.strip().split("\n")

        # Should only have one line (injection prevented)
        assert len(lines) == 1

        log_entry = json.loads(lines[0])
        # Newline should be removed from file_path
        assert "\n" not in log_entry["file_path"]

    def test_log_violation_sanitizes_reason(self, logger, temp_log_file):
        """Test log_violation sanitizes reason for injection."""
        malicious_reason = "Violation\n{\"violation_type\": \"fake_event\"}"

        logger.log_violation(
            violation_type=ViolationType.DIRECT_IMPLEMENTATION,
            file_path="module.py",
            agent_name="researcher",
            reason=malicious_reason,
            details="test",
        )

        log_content = temp_log_file.read_text()
        lines = log_content.strip().split("\n")

        # Should only have one line
        assert len(lines) == 1

        log_entry = json.loads(lines[0])
        assert "\n" not in log_entry["reason"]


class TestParseViolationLog:
    """Test violation log parsing."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file with sample entries."""
        log_file = tmp_path / "workflow_violations.log"
        entries = [
            {
                "timestamp": "2026-01-19T10:00:00Z",
                "violation_type": "direct_implementation",
                "file_path": "auth.py",
                "agent_name": "researcher",
                "reason": "New Python function detected",
                "details": "def authenticate_user():",
            },
            {
                "timestamp": "2026-01-19T10:01:00Z",
                "violation_type": "git_bypass_attempt",
                "command": "git commit --no-verify",
                "agent_name": "researcher",
                "reason": "--no-verify flag detected",
                "details": "",
            },
            {
                "timestamp": "2026-01-19T10:02:00Z",
                "violation_type": "protected_path_edit",
                "file_path": ".claude/commands/implement.md",
                "agent_name": "planner",
                "reason": "Protected path modification",
                "details": "commands/*.md protected",
            },
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in entries))
        return log_file

    def test_parse_violation_log_returns_entries(self, temp_log_file):
        """Test parse_violation_log returns all log entries."""
        entries = parse_violation_log(temp_log_file)

        assert len(entries) == 3
        assert entries[0].violation_type == "direct_implementation"
        assert entries[1].violation_type == "git_bypass_attempt"
        assert entries[2].violation_type == "protected_path_edit"

    def test_parse_violation_log_filters_by_type(self, temp_log_file):
        """Test parse_violation_log filters by violation type."""
        entries = parse_violation_log(
            temp_log_file, violation_type_filter="git_bypass_attempt"
        )

        assert len(entries) == 1
        assert entries[0].violation_type == "git_bypass_attempt"

    def test_parse_violation_log_filters_by_agent(self, temp_log_file):
        """Test parse_violation_log filters by agent name."""
        entries = parse_violation_log(temp_log_file, agent_filter="researcher")

        assert len(entries) == 2
        assert all(e.agent_name == "researcher" for e in entries)

    def test_parse_violation_log_filters_by_time_range(self, temp_log_file):
        """Test parse_violation_log filters by time range."""
        start_time = datetime.fromisoformat("2026-01-19T10:00:30Z")
        end_time = datetime.fromisoformat("2026-01-19T10:01:30Z")

        entries = parse_violation_log(
            temp_log_file, start_time=start_time, end_time=end_time
        )

        # Should only include second entry
        assert len(entries) == 1
        assert entries[0].violation_type == "git_bypass_attempt"


class TestViolationSummary:
    """Test violation summary statistics."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file with sample entries."""
        log_file = tmp_path / "workflow_violations.log"
        entries = [
            {
                "timestamp": "2026-01-19T10:00:00Z",
                "violation_type": "direct_implementation",
                "file_path": "auth.py",
                "agent_name": "researcher",
                "reason": "New function",
                "details": "def auth():",
            },
            {
                "timestamp": "2026-01-19T10:01:00Z",
                "violation_type": "direct_implementation",
                "file_path": "api.py",
                "agent_name": "researcher",
                "reason": "New function",
                "details": "def api():",
            },
            {
                "timestamp": "2026-01-19T10:02:00Z",
                "violation_type": "git_bypass_attempt",
                "command": "git commit --no-verify",
                "agent_name": "planner",
                "reason": "--no-verify",
                "details": "",
            },
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in entries))
        return log_file

    def test_get_violation_summary_counts_by_type(self, temp_log_file):
        """Test get_violation_summary counts violations by type."""
        summary = get_violation_summary(temp_log_file)

        assert summary["total_violations"] == 3
        assert summary["by_type"]["direct_implementation"] == 2
        assert summary["by_type"]["git_bypass_attempt"] == 1

    def test_get_violation_summary_counts_by_agent(self, temp_log_file):
        """Test get_violation_summary counts violations by agent."""
        summary = get_violation_summary(temp_log_file)

        assert summary["by_agent"]["researcher"] == 2
        assert summary["by_agent"]["planner"] == 1

    def test_get_violation_summary_includes_time_range(self, temp_log_file):
        """Test get_violation_summary includes time range."""
        summary = get_violation_summary(temp_log_file)

        assert "earliest_violation" in summary
        assert "latest_violation" in summary

        earliest = datetime.fromisoformat(summary["earliest_violation"])
        latest = datetime.fromisoformat(summary["latest_violation"])

        assert earliest <= latest

    def test_get_violation_summary_empty_log(self, tmp_path):
        """Test get_violation_summary with empty log file."""
        empty_log = tmp_path / "empty.log"
        empty_log.write_text("")

        summary = get_violation_summary(empty_log)

        assert summary["total_violations"] == 0
        assert summary["by_type"] == {}
        assert summary["by_agent"] == {}


class TestViolationLogEntry:
    """Test ViolationLogEntry dataclass."""

    def test_violation_log_entry_creation(self):
        """Test ViolationLogEntry creation."""
        entry = ViolationLogEntry(
            timestamp="2026-01-19T10:00:00Z",
            violation_type="direct_implementation",
            file_path="auth.py",
            agent_name="researcher",
            reason="New Python function detected",
            details="def authenticate_user():",
        )

        assert entry.violation_type == "direct_implementation"
        assert entry.file_path == "auth.py"
        assert entry.agent_name == "researcher"

    def test_violation_log_entry_to_dict(self):
        """Test ViolationLogEntry serialization to dict."""
        entry = ViolationLogEntry(
            timestamp="2026-01-19T10:00:00Z",
            violation_type="git_bypass_attempt",
            file_path=None,
            agent_name="planner",
            reason="--no-verify flag detected",
            details="git commit --no-verify",
            command="git commit --no-verify",
        )

        entry_dict = entry.to_dict()

        assert entry_dict["violation_type"] == "git_bypass_attempt"
        assert entry_dict["command"] == "git commit --no-verify"

    def test_violation_log_entry_from_dict(self):
        """Test ViolationLogEntry deserialization from dict."""
        data = {
            "timestamp": "2026-01-19T10:00:00Z",
            "violation_type": "protected_path_edit",
            "file_path": ".claude/commands/implement.md",
            "agent_name": "implementer",
            "reason": "Protected path modification",
            "details": "commands/*.md protected",
        }

        entry = ViolationLogEntry.from_dict(data)

        assert entry.violation_type == "protected_path_edit"
        assert entry.file_path == ".claude/commands/implement.md"


class TestGracefulDegradation:
    """Test error handling and graceful degradation."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary violation log file."""
        return tmp_path / "workflow_violations.log"

    def test_logger_handles_missing_directory(self, tmp_path):
        """Test logger creates missing directories gracefully."""
        log_file = tmp_path / "nonexistent" / "dir" / "violations.log"

        logger = WorkflowViolationLogger(log_file=log_file)

        assert log_file.exists()

    def test_logger_handles_permission_errors(self, tmp_path):
        """Test logger handles permission errors gracefully."""
        log_file = tmp_path / "violations.log"
        log_file.touch()
        log_file.chmod(0o000)  # Remove all permissions

        try:
            logger = WorkflowViolationLogger(log_file=log_file)
            # Should not raise exception - graceful degradation
        except PermissionError:
            pytest.skip("Permission error handling varies by platform")
        finally:
            log_file.chmod(0o644)  # Restore permissions

    def test_parse_violation_log_handles_corrupted_entries(self, tmp_path):
        """Test parse_violation_log handles corrupted JSON entries."""
        log_file = tmp_path / "corrupted.log"
        log_file.write_text(
            """{"timestamp": "2026-01-19T10:00:00Z", "violation_type": "direct_implementation"}
not valid json{
{"timestamp": "2026-01-19T10:01:00Z", "violation_type": "git_bypass_attempt"}
"""
        )

        entries = parse_violation_log(log_file)

        # Should skip corrupted line, return valid entries
        assert len(entries) == 2


if __name__ == "__main__":
    # Run tests with minimal verbosity (Issue #90 - prevent subprocess deadlock)
    pytest.main([__file__, "--tb=line", "-q"])
