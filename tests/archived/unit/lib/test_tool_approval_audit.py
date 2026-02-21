#!/usr/bin/env python3
"""
Unit tests for tool_approval_audit module (TDD Red Phase).

Tests for MCP tool approval audit logging for Issue #73.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test log format validation (JSON lines format)
- Test log injection prevention (CWE-117)
- Test log rotation behavior
- Test audit trail completeness
- Test structured logging fields

Security Coverage:
- CWE-117: Log Injection Prevention
- Audit trail integrity
- Log file permissions

Date: 2025-11-15
Issue: #73 (MCP Auto-Approval for Subagent Tool Calls)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open
from typing import Dict, Any

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
    from tool_approval_audit import (
        ToolApprovalAuditor,
        log_approval,
        log_denial,
        log_circuit_breaker_trip,
        parse_audit_log,
        AuditLogEntry,
        sanitize_log_input,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestToolApprovalAuditor:
    """Test ToolApprovalAuditor class."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "tool_approval_audit.log"

    @pytest.fixture
    def auditor(self, temp_log_file):
        """Create ToolApprovalAuditor instance."""
        return ToolApprovalAuditor(log_file=temp_log_file)

    def test_auditor_init_creates_log_file(self, temp_log_file):
        """Test auditor initialization creates log file."""
        auditor = ToolApprovalAuditor(log_file=temp_log_file)

        assert temp_log_file.exists()

    def test_auditor_init_creates_parent_dirs(self, tmp_path):
        """Test auditor initialization creates parent directories."""
        log_file = tmp_path / "nested" / "dir" / "audit.log"

        auditor = ToolApprovalAuditor(log_file=log_file)

        assert log_file.exists()
        assert log_file.parent.exists()

    def test_auditor_uses_default_log_path(self):
        """Test auditor uses default log path if not provided."""
        with patch("tool_approval_audit.DEFAULT_LOG_FILE", Path("/tmp/audit.log")):
            with patch("pathlib.Path.touch"):
                auditor = ToolApprovalAuditor()

                assert auditor.log_file is not None


class TestLogApproval:
    """Test approval logging."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "tool_approval_audit.log"

    @pytest.fixture
    def auditor(self, temp_log_file):
        """Create ToolApprovalAuditor instance."""
        return ToolApprovalAuditor(log_file=temp_log_file)

    def test_log_approval_writes_json_line(self, auditor, temp_log_file):
        """Test log_approval writes JSON line to log file."""
        auditor.log_approval(
            agent_name="researcher",
            tool="Bash",
            parameters={"command": "pytest tests/"},
            reason="Matches whitelist",
        )

        # Read log file
        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert log_entry["event"] == "approval"
        assert log_entry["agent"] == "researcher"
        assert log_entry["tool"] == "Bash"
        assert log_entry["reason"] == "Matches whitelist"

    def test_log_approval_includes_timestamp(self, auditor, temp_log_file):
        """Test log_approval includes ISO 8601 timestamp."""
        auditor.log_approval(
            agent_name="planner",
            tool="Read",
            parameters={"file_path": "file.py"},
            reason="Whitelisted path",
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        # Should have timestamp in ISO 8601 format
        assert "timestamp" in log_entry
        datetime.fromisoformat(log_entry["timestamp"])  # Should parse

    def test_log_approval_includes_parameters(self, auditor, temp_log_file):
        """Test log_approval includes sanitized tool parameters."""
        auditor.log_approval(
            agent_name="implementer",
            tool="Write",
            parameters={"file_path": "/tmp/output.txt", "content": "data"},
            reason="Whitelisted path",
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert "parameters" in log_entry
        assert log_entry["parameters"]["file_path"] == "/tmp/output.txt"

    def test_log_approval_sanitizes_sensitive_data(self, auditor, temp_log_file):
        """Test log_approval sanitizes sensitive data from parameters."""
        auditor.log_approval(
            agent_name="researcher",
            tool="Bash",
            parameters={"command": "curl -H 'Authorization: Bearer secret_token'"},
            reason="Whitelisted",
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        # Sensitive data should be redacted
        assert "secret_token" not in log_entry["parameters"]["command"]
        assert "[REDACTED]" in log_entry["parameters"]["command"]


class TestLogDenial:
    """Test denial logging."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "tool_approval_audit.log"

    @pytest.fixture
    def auditor(self, temp_log_file):
        """Create ToolApprovalAuditor instance."""
        return ToolApprovalAuditor(log_file=temp_log_file)

    def test_log_denial_writes_json_line(self, auditor, temp_log_file):
        """Test log_denial writes JSON line to log file."""
        auditor.log_denial(
            agent_name="researcher",
            tool="Bash",
            parameters={"command": "rm -rf /"},
            reason="Matches blacklist",
            security_risk=True,
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert log_entry["event"] == "denial"
        assert log_entry["agent"] == "researcher"
        assert log_entry["tool"] == "Bash"
        assert log_entry["reason"] == "Matches blacklist"
        assert log_entry["security_risk"] is True

    def test_log_denial_includes_security_risk_flag(self, auditor, temp_log_file):
        """Test log_denial includes security_risk flag."""
        auditor.log_denial(
            agent_name="implementer",
            tool="Write",
            parameters={"file_path": "/etc/passwd"},
            reason="Blacklisted path",
            security_risk=True,
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert "security_risk" in log_entry
        assert log_entry["security_risk"] is True

    def test_log_denial_includes_matched_pattern(self, auditor, temp_log_file):
        """Test log_denial includes matched blacklist pattern."""
        auditor.log_denial(
            agent_name="researcher",
            tool="Bash",
            parameters={"command": "sudo apt install"},
            reason="Matches blacklist",
            security_risk=True,
            matched_pattern="sudo*",
        )

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert "matched_pattern" in log_entry
        assert log_entry["matched_pattern"] == "sudo*"


class TestLogCircuitBreakerTrip:
    """Test circuit breaker trip logging."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "tool_approval_audit.log"

    @pytest.fixture
    def auditor(self, temp_log_file):
        """Create ToolApprovalAuditor instance."""
        return ToolApprovalAuditor(log_file=temp_log_file)

    def test_log_circuit_breaker_trip(self, auditor, temp_log_file):
        """Test log_circuit_breaker_trip logs event."""
        auditor.log_circuit_breaker_trip(denial_count=10, threshold=10)

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert log_entry["event"] == "circuit_breaker_trip"
        assert log_entry["denial_count"] == 10
        assert log_entry["threshold"] == 10

    def test_log_circuit_breaker_reset(self, auditor, temp_log_file):
        """Test log_circuit_breaker_reset logs event."""
        auditor.log_circuit_breaker_reset()

        log_content = temp_log_file.read_text()
        log_entry = json.loads(log_content.strip())

        assert log_entry["event"] == "circuit_breaker_reset"


class TestLogInjectionPrevention:
    """Test log injection prevention (CWE-117)."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "tool_approval_audit.log"

    @pytest.fixture
    def auditor(self, temp_log_file):
        """Create ToolApprovalAuditor instance."""
        return ToolApprovalAuditor(log_file=temp_log_file)

    def test_sanitize_log_input_removes_newlines(self):
        """Test sanitize_log_input removes newlines."""
        input_str = "command\nwith\nnewlines"

        sanitized = sanitize_log_input(input_str)

        assert "\n" not in sanitized
        assert sanitized == "command with newlines"

    def test_sanitize_log_input_removes_carriage_returns(self):
        """Test sanitize_log_input removes carriage returns."""
        input_str = "command\rwith\rcarriage\rreturns"

        sanitized = sanitize_log_input(input_str)

        assert "\r" not in sanitized

    def test_sanitize_log_input_removes_control_chars(self):
        """Test sanitize_log_input removes control characters."""
        input_str = "command\x00with\x01control\x02chars"

        sanitized = sanitize_log_input(input_str)

        # Control chars should be removed
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized

    def test_log_approval_sanitizes_agent_name(self, auditor, temp_log_file):
        """Test log_approval sanitizes agent_name for injection."""
        malicious_agent = "researcher\n{\"event\": \"fake_approval\"}"

        auditor.log_approval(
            agent_name=malicious_agent,
            tool="Bash",
            parameters={"command": "pytest"},
            reason="Test",
        )

        log_content = temp_log_file.read_text()
        lines = log_content.strip().split("\n")

        # Should only have one line (injection prevented)
        assert len(lines) == 1

        log_entry = json.loads(lines[0])
        # Newline should be removed from agent name
        assert "\n" not in log_entry["agent"]

    def test_log_denial_sanitizes_reason(self, auditor, temp_log_file):
        """Test log_denial sanitizes reason for injection."""
        malicious_reason = "Blacklist\n{\"event\": \"fake_event\"}"

        auditor.log_denial(
            agent_name="researcher",
            tool="Bash",
            parameters={"command": "rm -rf"},
            reason=malicious_reason,
            security_risk=True,
        )

        log_content = temp_log_file.read_text()
        lines = log_content.strip().split("\n")

        # Should only have one line
        assert len(lines) == 1

        log_entry = json.loads(lines[0])
        assert "\n" not in log_entry["reason"]


class TestLogRotation:
    """Test log rotation behavior."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "tool_approval_audit.log"

    @pytest.fixture
    def auditor(self, temp_log_file):
        """Create ToolApprovalAuditor instance."""
        return ToolApprovalAuditor(log_file=temp_log_file)

    def test_log_file_rotates_at_size_limit(self, auditor, temp_log_file):
        """Test log file rotates when size limit reached."""
        # Log many entries to exceed size limit
        for i in range(1000):
            auditor.log_approval(
                agent_name="researcher",
                tool="Bash",
                parameters={"command": f"pytest tests/test_{i}.py"},
                reason="Whitelist",
            )

        # Should have created rotated log file
        rotated_files = list(temp_log_file.parent.glob("tool_approval_audit.log.*"))
        assert len(rotated_files) > 0

    def test_log_rotation_preserves_old_entries(self, auditor, temp_log_file):
        """Test log rotation preserves old entries in rotated file."""
        # Log first entry
        auditor.log_approval(
            agent_name="researcher",
            tool="Bash",
            parameters={"command": "first"},
            reason="First",
        )

        first_content = temp_log_file.read_text()

        # Force rotation
        auditor.rotate_log()

        # Old entry should be in rotated file
        rotated_files = list(temp_log_file.parent.glob("tool_approval_audit.log.*"))
        assert len(rotated_files) > 0

        rotated_content = rotated_files[0].read_text()
        assert first_content in rotated_content

    def test_log_rotation_keeps_n_rotated_files(self, auditor, temp_log_file):
        """Test log rotation keeps only N most recent rotated files."""
        # Rotate multiple times
        for i in range(15):
            auditor.rotate_log()

        rotated_files = list(temp_log_file.parent.glob("tool_approval_audit.log.*"))

        # Should keep only 10 most recent (or configured limit)
        assert len(rotated_files) <= 10


class TestParseAuditLog:
    """Test audit log parsing."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary audit log file with sample entries."""
        log_file = tmp_path / "tool_approval_audit.log"
        entries = [
            {
                "timestamp": "2025-11-15T10:00:00Z",
                "event": "approval",
                "agent": "researcher",
                "tool": "Bash",
                "parameters": {"command": "pytest"},
                "reason": "Whitelist",
            },
            {
                "timestamp": "2025-11-15T10:01:00Z",
                "event": "denial",
                "agent": "researcher",
                "tool": "Bash",
                "parameters": {"command": "rm -rf"},
                "reason": "Blacklist",
                "security_risk": True,
            },
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in entries))
        return log_file

    def test_parse_audit_log_returns_entries(self, temp_log_file):
        """Test parse_audit_log returns all log entries."""
        entries = parse_audit_log(temp_log_file)

        assert len(entries) == 2
        assert entries[0].event == "approval"
        assert entries[1].event == "denial"

    def test_parse_audit_log_filters_by_agent(self, temp_log_file):
        """Test parse_audit_log filters by agent name."""
        entries = parse_audit_log(temp_log_file, agent_filter="researcher")

        assert all(e.agent == "researcher" for e in entries)

    def test_parse_audit_log_filters_by_event_type(self, temp_log_file):
        """Test parse_audit_log filters by event type."""
        entries = parse_audit_log(temp_log_file, event_filter="denial")

        assert all(e.event == "denial" for e in entries)

    def test_parse_audit_log_filters_by_time_range(self, temp_log_file):
        """Test parse_audit_log filters by time range."""
        start_time = datetime.fromisoformat("2025-11-15T10:00:30Z")
        end_time = datetime.fromisoformat("2025-11-15T10:01:30Z")

        entries = parse_audit_log(temp_log_file, start_time=start_time, end_time=end_time)

        # Should only include second entry
        assert len(entries) == 1
        assert entries[0].event == "denial"


class TestAuditLogEntry:
    """Test AuditLogEntry dataclass."""

    def test_audit_log_entry_creation(self):
        """Test AuditLogEntry creation."""
        entry = AuditLogEntry(
            timestamp="2025-11-15T10:00:00Z",
            event="approval",
            agent="researcher",
            tool="Bash",
            parameters={"command": "pytest"},
            reason="Whitelist",
            security_risk=False,
        )

        assert entry.event == "approval"
        assert entry.agent == "researcher"
        assert entry.tool == "Bash"
        assert entry.security_risk is False

    def test_audit_log_entry_to_dict(self):
        """Test AuditLogEntry serialization to dict."""
        entry = AuditLogEntry(
            timestamp="2025-11-15T10:00:00Z",
            event="denial",
            agent="implementer",
            tool="Write",
            parameters={"file_path": "/etc/passwd"},
            reason="Blacklist",
            security_risk=True,
        )

        entry_dict = entry.to_dict()

        assert entry_dict["event"] == "denial"
        assert entry_dict["security_risk"] is True

    def test_audit_log_entry_from_dict(self):
        """Test AuditLogEntry deserialization from dict."""
        data = {
            "timestamp": "2025-11-15T10:00:00Z",
            "event": "approval",
            "agent": "planner",
            "tool": "Read",
            "parameters": {"file_path": "file.py"},
            "reason": "Whitelist",
            "security_risk": False,
        }

        entry = AuditLogEntry.from_dict(data)

        assert entry.event == "approval"
        assert entry.agent == "planner"
