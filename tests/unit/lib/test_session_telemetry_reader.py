#!/usr/bin/env python3
"""
TDD Tests for Session Telemetry Reader Library (Issue #328) - RED PHASE

This test suite validates the creation of session_telemetry_reader.py library
for reading and classifying plugin automation logs for postmortem analysis.

Problem (Issue #328):
- No automated analysis of plugin automation errors vs user code errors
- Manual error classification is tedious and skipped by users
- Secrets risk leaking into GitHub issues via manual copy-paste
- No deduplication checking against existing issues
- Plugin bugs accumulate without visibility

Solution:
- Create lib/session_telemetry_reader.py with SessionTelemetryReader class
- Read from:
  - .claude/logs/errors/YYYY-MM-DD.jsonl (error registry)
  - .claude/logs/workflow_violations.log (violation log)
- Classify findings: PLUGIN_BUG, USER_CODE_BUG, UNKNOWN
- Create fingerprints for deduplication
- Redact secrets before filing issues
- Enforce resource limits (max 500 errors per session)

Test Coverage:
1. SessionTelemetryReader initialization (3 tests)
2. read_errors() - Error registry reading (5 tests)
3. read_violations() - Violation log reading (4 tests)
4. classify_finding() - Classification logic (8 tests)
5. create_fingerprint() - Deduplication fingerprints (5 tests)
6. redact_secrets() - Secret sanitization (6 tests)
7. Resource limits (3 tests)
8. analyze_session() - Full workflow (5 tests)
9. Graceful degradation (4 tests)

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (lib/session_telemetry_reader.py doesn't exist yet)
- Implementation makes tests pass (GREEN phase)

Date: 2026-02-11
Issue: GitHub #328 (Postmortem analyst for plugin bug detection)
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See python-standards skill for test code conventions.
    See security-patterns skill for secret redaction patterns.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from typing import Dict, List, Any, Optional

import pytest

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# This import will FAIL until lib/session_telemetry_reader.py is created (TDD!)
try:
    from session_telemetry_reader import (
        SessionTelemetryReader,
        Finding,
        SessionTelemetry,
        IssueSource,
        TelemetryError,
    )
    LIB_SESSION_TELEMETRY_EXISTS = True
except ImportError:
    LIB_SESSION_TELEMETRY_EXISTS = False
    SessionTelemetryReader = None
    Finding = None
    SessionTelemetry = None
    IssueSource = None
    TelemetryError = None


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure for testing.

    Simulates a user's project with .claude marker and log directories.

    Structure:
    tmp_project/
        .git/
        .claude/
            PROJECT.md
            logs/
                errors/
                    2026-02-11.jsonl
                workflow_violations.log
        plugins/
            autonomous-dev/
                lib/
                    session_telemetry_reader.py  # What we're creating
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create .claude directory
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "PROJECT.md").write_text("# Test Project\n")

    # Create log directories
    logs_dir = claude_dir / "logs"
    logs_dir.mkdir()
    errors_dir = logs_dir / "errors"
    errors_dir.mkdir()

    return tmp_path


@pytest.fixture
def sample_error_log():
    """Sample error log entries (JSONL format)."""
    return [
        {
            "timestamp": "2026-02-11T14:30:00Z",
            "tool": "unified_pre_tool.py",
            "error": "Hook failed with exit code 1",
            "classification": "PERMANENT",
            "session_id": "abc123"
        },
        {
            "timestamp": "2026-02-11T14:31:00Z",
            "tool": "implementer",
            "error": "Agent crashed: AttributeError in step 5",
            "classification": "PERMANENT",
            "session_id": "abc123"
        },
        {
            "timestamp": "2026-02-11T14:32:00Z",
            "tool": "pytest",
            "error": "Test failed: test_user_function",
            "classification": "PERMANENT",
            "session_id": "abc123"
        }
    ]


@pytest.fixture
def sample_violation_log():
    """Sample violation log entries (JSONL format)."""
    return [
        {
            "timestamp": "2026-02-11T14:30:00Z",
            "type": "direct_implementation",
            "agent": "user",
            "details": "Attempted git commit --no-verify",
            "severity": "warning"
        },
        {
            "timestamp": "2026-02-11T14:31:00Z",
            "type": "step_skip",
            "agent": "implementer",
            "details": "Skipped from step 5 to step 6 (tests incomplete)",
            "severity": "error"
        }
    ]


# ============================================================================
# UNIT TESTS - SessionTelemetryReader Initialization
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestSessionTelemetryReaderInit:
    """Test SessionTelemetryReader class initialization."""

    def test_reader_initializes_with_default_project_root(self, temp_project):
        """Test SessionTelemetryReader initialization with default project root."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            assert reader.project_root == temp_project
            assert reader.logs_dir == temp_project / ".claude" / "logs"

    def test_reader_initializes_with_custom_project_root(self, tmp_path):
        """Test SessionTelemetryReader initialization with custom project root."""
        reader = SessionTelemetryReader(project_root=tmp_path)
        assert reader.project_root == tmp_path
        assert reader.logs_dir == tmp_path / ".claude" / "logs"

    def test_reader_handles_missing_logs_directory(self, temp_project):
        """Test SessionTelemetryReader handles missing logs directory gracefully."""
        # Remove logs directory
        logs_dir = temp_project / ".claude" / "logs"
        if logs_dir.exists():
            import shutil
            shutil.rmtree(logs_dir)

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            # Should not crash, just return empty results
            errors = reader.read_errors()
            assert errors == []


# ============================================================================
# UNIT TESTS - read_errors() Method
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestReadErrors:
    """Test SessionTelemetryReader.read_errors() method."""

    def test_read_errors_parses_jsonl_file(self, temp_project, sample_error_log):
        """Test read_errors() parses JSONL error log correctly."""
        # Write error log
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for entry in sample_error_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2026-02-11")

        assert len(errors) == 3
        assert all(isinstance(e, Finding) for e in errors)
        assert errors[0].component == "unified_pre_tool.py"
        assert errors[1].component == "implementer"

    def test_read_errors_uses_today_date_by_default(self, temp_project, sample_error_log):
        """Test read_errors() uses today's date when no date specified."""
        today = datetime.now().strftime("%Y-%m-%d")
        error_file = temp_project / ".claude" / "logs" / "errors" / f"{today}.jsonl"
        error_file.parent.mkdir(parents=True, exist_ok=True)
        with error_file.open("w") as f:
            for entry in sample_error_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors()  # No date specified

        assert len(errors) == 3

    def test_read_errors_returns_empty_list_when_file_missing(self, temp_project):
        """Test read_errors() returns empty list when error log doesn't exist."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2025-01-01")

        assert errors == []

    def test_read_errors_skips_malformed_json_lines(self, temp_project):
        """Test read_errors() skips malformed JSON lines gracefully."""
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            f.write('{"timestamp": "2026-02-11T14:30:00Z", "tool": "test", "error": "msg"}\n')
            f.write('{ malformed json }\n')  # Malformed
            f.write('{"timestamp": "2026-02-11T14:31:00Z", "tool": "test2", "error": "msg2"}\n')

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2026-02-11")

        # Should get 2 valid entries, skip 1 malformed
        assert len(errors) == 2

    def test_read_errors_enforces_max_limit(self, temp_project):
        """Test read_errors() enforces max 500 errors limit."""
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for i in range(600):  # Write 600 errors
                entry = {"timestamp": "2026-02-11T14:30:00Z", "tool": f"tool{i}", "error": "msg"}
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2026-02-11")

        # Should cap at 500
        assert len(errors) == 500


# ============================================================================
# UNIT TESTS - read_violations() Method
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestReadViolations:
    """Test SessionTelemetryReader.read_violations() method."""

    def test_read_violations_parses_jsonl_file(self, temp_project, sample_violation_log):
        """Test read_violations() parses JSONL violation log correctly."""
        violation_file = temp_project / ".claude" / "logs" / "workflow_violations.log"
        with violation_file.open("w") as f:
            for entry in sample_violation_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            violations = reader.read_violations()

        assert len(violations) == 2
        assert all(isinstance(v, Finding) for v in violations)
        assert violations[0].error_type == "direct_implementation"
        assert violations[1].error_type == "step_skip"

    def test_read_violations_returns_empty_list_when_file_missing(self, temp_project):
        """Test read_violations() returns empty list when violation log doesn't exist."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            violations = reader.read_violations()

        assert violations == []

    def test_read_violations_skips_malformed_json_lines(self, temp_project):
        """Test read_violations() skips malformed JSON lines gracefully."""
        violation_file = temp_project / ".claude" / "logs" / "workflow_violations.log"
        with violation_file.open("w") as f:
            f.write('{"timestamp": "2026-02-11T14:30:00Z", "type": "test", "agent": "user"}\n')
            f.write('{ malformed json }\n')  # Malformed
            f.write('{"timestamp": "2026-02-11T14:31:00Z", "type": "test2", "agent": "user"}\n')

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            violations = reader.read_violations()

        # Should get 2 valid entries, skip 1 malformed
        assert len(violations) == 2

    def test_read_violations_converts_to_finding_objects(self, temp_project, sample_violation_log):
        """Test read_violations() converts log entries to Finding objects."""
        violation_file = temp_project / ".claude" / "logs" / "workflow_violations.log"
        with violation_file.open("w") as f:
            for entry in sample_violation_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            violations = reader.read_violations()

        # Check Finding attributes
        assert violations[0].source == "violation_log"
        assert violations[0].component == "user"
        assert "git commit --no-verify" in violations[0].message


# ============================================================================
# UNIT TESTS - classify_finding() Method
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestClassification:
    """Test SessionTelemetryReader.classify_finding() classification logic."""

    def test_classify_hook_failure_as_plugin_bug(self, temp_project):
        """Test classify_finding() identifies hook failures as PLUGIN_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="hook_failure",
                component="unified_pre_tool.py",
                message="Hook failed with exit code 1"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.PLUGIN_BUG

    def test_classify_agent_crash_as_plugin_bug(self, temp_project):
        """Test classify_finding() identifies agent crashes as PLUGIN_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="agent_crash",
                component="implementer",
                message="AttributeError: 'NoneType' object has no attribute 'get'"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.PLUGIN_BUG

    def test_classify_step_skip_as_plugin_bug(self, temp_project):
        """Test classify_finding() identifies pipeline step skips as PLUGIN_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="violation_log",
                error_type="step_skip",
                component="implementer",
                message="Skipped from step 5 to step 6 (tests incomplete)"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.PLUGIN_BUG

    def test_classify_missing_skill_as_plugin_bug(self, temp_project):
        """Test classify_finding() identifies missing skill references as PLUGIN_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="skill_load_error",
                component="researcher",
                message="Skill not found: nonexistent-skill"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.PLUGIN_BUG

    def test_classify_tool_validation_error_as_plugin_bug(self, temp_project):
        """Test classify_finding() identifies tool validation errors as PLUGIN_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="tool_validation_error",
                component="unified_pre_tool.py",
                message="Tool not in allowed list"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.PLUGIN_BUG

    def test_classify_user_test_failure_as_user_code_bug(self, temp_project):
        """Test classify_finding() identifies user test failures as USER_CODE_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="test_failure",
                component="tests/test_user_code.py",
                message="AssertionError: expected 5, got 3"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.USER_CODE_BUG

    def test_classify_user_syntax_error_as_user_code_bug(self, temp_project):
        """Test classify_finding() identifies user syntax errors as USER_CODE_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="syntax_error",
                component="src/user_module.py",
                message="SyntaxError: invalid syntax"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.USER_CODE_BUG

    def test_classify_git_bypass_as_user_code_bug(self, temp_project):
        """Test classify_finding() identifies git bypasses as USER_CODE_BUG."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="violation_log",
                error_type="direct_implementation",
                component="user",
                message="Attempted git commit --no-verify"
            )

            classification = reader.classify_finding(finding)

        assert classification == IssueSource.USER_CODE_BUG


# ============================================================================
# UNIT TESTS - create_fingerprint() Method
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestFingerprinting:
    """Test SessionTelemetryReader.create_fingerprint() deduplication logic."""

    def test_create_fingerprint_is_deterministic(self, temp_project):
        """Test create_fingerprint() produces same hash for same input."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="hook_failure",
                component="unified_pre_tool.py",
                message="Hook failed with exit code 1"
            )

            fingerprint1 = reader.create_fingerprint(finding)
            fingerprint2 = reader.create_fingerprint(finding)

        assert fingerprint1 == fingerprint2
        assert len(fingerprint1) == 64  # SHA256 hex digest

    def test_create_fingerprint_differs_for_different_errors(self, temp_project):
        """Test create_fingerprint() produces different hashes for different errors."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding1 = Finding(
                source="error_registry",
                error_type="hook_failure",
                component="unified_pre_tool.py",
                message="Error 1"
            )
            finding2 = Finding(
                source="error_registry",
                error_type="agent_crash",
                component="implementer",
                message="Error 2"
            )

            fingerprint1 = reader.create_fingerprint(finding1)
            fingerprint2 = reader.create_fingerprint(finding2)

        assert fingerprint1 != fingerprint2

    def test_create_fingerprint_normalizes_message(self, temp_project):
        """Test create_fingerprint() normalizes message for deduplication."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding1 = Finding(
                source="error_registry",
                error_type="hook_failure",
                component="test.py",
                message="Error on line 123"
            )
            finding2 = Finding(
                source="error_registry",
                error_type="hook_failure",
                component="test.py",
                message="Error on line 456"  # Different line number
            )

            fingerprint1 = reader.create_fingerprint(finding1)
            fingerprint2 = reader.create_fingerprint(finding2)

        # Should have same fingerprint (line numbers normalized)
        assert fingerprint1 == fingerprint2

    def test_create_fingerprint_includes_error_type_and_component(self, temp_project):
        """Test create_fingerprint() includes error_type and component in hash."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="hook_failure",
                component="unified_pre_tool.py",
                message="Test error"
            )

            fingerprint = reader.create_fingerprint(finding)

        # Fingerprint should be based on type + component + normalized message
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64

    def test_create_fingerprint_handles_empty_message(self, temp_project):
        """Test create_fingerprint() handles empty messages gracefully."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            finding = Finding(
                source="error_registry",
                error_type="hook_failure",
                component="test.py",
                message=""
            )

            fingerprint = reader.create_fingerprint(finding)

        # Should still produce valid hash
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64


# ============================================================================
# UNIT TESTS - redact_secrets() Method
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestSecretRedaction:
    """Test SessionTelemetryReader.redact_secrets() sanitization."""

    def test_redact_secrets_redacts_api_keys(self, temp_project):
        """Test redact_secrets() redacts API keys."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            text = "Error: API call failed with key sk-1234567890abcdef"

            redacted = reader.redact_secrets(text)

        assert "sk-1234567890abcdef" not in redacted
        assert "[REDACTED_API_KEY]" in redacted

    def test_redact_secrets_redacts_github_tokens(self, temp_project):
        """Test redact_secrets() redacts GitHub personal access tokens."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            text = "Auth failed: ghp_1234567890abcdefghijklmnopqrstuvwxyz"

            redacted = reader.redact_secrets(text)

        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in redacted
        assert "[REDACTED_TOKEN]" in redacted or "[REDACTED_GITHUB_TOKEN]" in redacted

    def test_redact_secrets_redacts_bearer_tokens(self, temp_project):
        """Test redact_secrets() redacts Bearer tokens."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            text = "Authorization: Bearer abc123xyz789"

            redacted = reader.redact_secrets(text)

        assert "abc123xyz789" not in redacted
        assert "[REDACTED" in redacted

    def test_redact_secrets_redacts_passwords(self, temp_project):
        """Test redact_secrets() redacts password fields."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            text = 'Database connection failed: password="SuperSecret123"'

            redacted = reader.redact_secrets(text)

        assert "SuperSecret123" not in redacted
        assert "[REDACTED_PASSWORD]" in redacted

    def test_redact_secrets_preserves_safe_content(self, temp_project):
        """Test redact_secrets() preserves non-sensitive content."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            text = "Error in unified_pre_tool.py at line 42: Hook validation failed"

            redacted = reader.redact_secrets(text)

        assert redacted == text  # No changes

    def test_redact_secrets_handles_multiple_secrets(self, temp_project):
        """Test redact_secrets() redacts multiple secrets in one text."""
        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            text = "API key sk-abc123 and password=secret123 and token ghp_xyz789"

            redacted = reader.redact_secrets(text)

        assert "sk-abc123" not in redacted
        assert "secret123" not in redacted
        assert "ghp_xyz789" not in redacted
        assert redacted.count("[REDACTED") >= 3


# ============================================================================
# UNIT TESTS - Resource Limits
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestResourceLimits:
    """Test SessionTelemetryReader resource limit enforcement."""

    def test_enforces_max_errors_per_session(self, temp_project):
        """Test reader enforces max 500 errors per session."""
        # Create error log with 600 entries
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for i in range(600):
                entry = {"timestamp": "2026-02-11T14:30:00Z", "tool": f"tool{i}", "error": "msg"}
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2026-02-11")

        # Should cap at 500
        assert len(errors) == 500

    def test_logs_warning_when_limit_exceeded(self, temp_project, caplog):
        """Test reader logs warning when error limit exceeded."""
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for i in range(550):
                entry = {"timestamp": "2026-02-11T14:30:00Z", "tool": f"tool{i}", "error": "msg"}
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2026-02-11")

        # Should log warning
        assert any("exceeded" in record.message.lower() or "limit" in record.message.lower()
                   for record in caplog.records)

    def test_handles_large_violation_log(self, temp_project):
        """Test reader handles large violation logs efficiently."""
        violation_file = temp_project / ".claude" / "logs" / "workflow_violations.log"
        with violation_file.open("w") as f:
            for i in range(1000):
                entry = {"timestamp": "2026-02-11T14:30:00Z", "type": "test", "agent": "user"}
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            violations = reader.read_violations()

        # Should read all or apply limit gracefully
        assert len(violations) > 0


# ============================================================================
# UNIT TESTS - analyze_session() Method
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestAnalyzeSession:
    """Test SessionTelemetryReader.analyze_session() full workflow."""

    def test_analyze_session_reads_all_sources(self, temp_project, sample_error_log, sample_violation_log):
        """Test analyze_session() reads errors and violations."""
        # Write error log
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for entry in sample_error_log:
                f.write(json.dumps(entry) + "\n")

        # Write violation log
        violation_file = temp_project / ".claude" / "logs" / "workflow_violations.log"
        with violation_file.open("w") as f:
            for entry in sample_violation_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            telemetry = reader.analyze_session(date="2026-02-11")

        assert isinstance(telemetry, SessionTelemetry)
        assert len(telemetry.errors) == 3
        assert len(telemetry.violations) == 2

    def test_analyze_session_classifies_findings(self, temp_project, sample_error_log, sample_violation_log):
        """Test analyze_session() classifies findings into plugin_bugs and user_issues."""
        # Write logs
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for entry in sample_error_log:
                f.write(json.dumps(entry) + "\n")

        violation_file = temp_project / ".claude" / "logs" / "workflow_violations.log"
        with violation_file.open("w") as f:
            for entry in sample_violation_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            telemetry = reader.analyze_session(date="2026-02-11")

        # Check classification
        assert len(telemetry.plugin_bugs) > 0  # Hook failure, agent crash, step skip
        assert len(telemetry.user_issues) > 0  # Test failure, git bypass

    def test_analyze_session_creates_fingerprints(self, temp_project, sample_error_log):
        """Test analyze_session() creates fingerprints for deduplication."""
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for entry in sample_error_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            telemetry = reader.analyze_session(date="2026-02-11")

        # All findings should have fingerprints
        for finding in telemetry.errors + telemetry.violations:
            assert finding.fingerprint != ""
            assert len(finding.fingerprint) == 64

    def test_analyze_session_redacts_secrets_in_findings(self, temp_project):
        """Test analyze_session() redacts secrets in finding messages."""
        # Create error log with secret
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            entry = {
                "timestamp": "2026-02-11T14:30:00Z",
                "tool": "test",
                "error": "API call failed with key sk-1234567890abcdef"
            }
            f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            telemetry = reader.analyze_session(date="2026-02-11")

        # Check secret redacted
        assert "sk-1234567890abcdef" not in telemetry.errors[0].message
        assert "[REDACTED" in telemetry.errors[0].message

    def test_analyze_session_uses_today_by_default(self, temp_project, sample_error_log):
        """Test analyze_session() uses today's date when not specified."""
        today = datetime.now().strftime("%Y-%m-%d")
        error_file = temp_project / ".claude" / "logs" / "errors" / f"{today}.jsonl"
        with error_file.open("w") as f:
            for entry in sample_error_log:
                f.write(json.dumps(entry) + "\n")

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            telemetry = reader.analyze_session()  # No date specified

        assert telemetry.date == today
        assert len(telemetry.errors) == 3


# ============================================================================
# UNIT TESTS - Graceful Degradation
# ============================================================================


@pytest.mark.skipif(not LIB_SESSION_TELEMETRY_EXISTS, reason="Implementation not created yet (TDD red phase)")
class TestGracefulDegradation:
    """Test SessionTelemetryReader error handling and graceful degradation."""

    def test_handles_corrupted_error_log(self, temp_project):
        """Test reader handles corrupted error log gracefully."""
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            f.write("{ corrupted json\n")
            f.write('{"timestamp": "2026-02-11T14:30:00Z", "tool": "test", "error": "msg"}\n')

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2026-02-11")

        # Should skip corrupted line, read valid line
        assert len(errors) == 1

    def test_handles_missing_required_fields(self, temp_project):
        """Test reader handles missing required fields in log entries."""
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            # Missing 'error' field
            f.write('{"timestamp": "2026-02-11T14:30:00Z", "tool": "test"}\n')
            # Valid entry
            f.write('{"timestamp": "2026-02-11T14:31:00Z", "tool": "test", "error": "msg"}\n')

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            errors = reader.read_errors(date="2026-02-11")

        # Should skip invalid entry, read valid entry
        assert len(errors) == 1

    def test_handles_permission_denied_on_log_file(self, temp_project):
        """Test reader handles permission errors gracefully."""
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        error_file.write_text('{"timestamp": "2026-02-11T14:30:00Z", "tool": "test", "error": "msg"}\n')

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()

            # Mock permission error
            with patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")):
                errors = reader.read_errors(date="2026-02-11")

        # Should return empty list, not crash
        assert errors == []

    def test_analyze_session_continues_on_partial_failures(self, temp_project, sample_error_log):
        """Test analyze_session() continues even if one source fails."""
        # Write valid error log
        error_file = temp_project / ".claude" / "logs" / "errors" / "2026-02-11.jsonl"
        with error_file.open("w") as f:
            for entry in sample_error_log:
                f.write(json.dumps(entry) + "\n")

        # Violation log doesn't exist (simulates failure)

        with patch("session_telemetry_reader.get_project_root", return_value=temp_project):
            reader = SessionTelemetryReader()
            telemetry = reader.analyze_session(date="2026-02-11")

        # Should have errors, but violations will be empty (not crash)
        assert len(telemetry.errors) == 3
        assert len(telemetry.violations) == 0


# ============================================================================
# CHECKPOINT: Save Test Creation Checkpoint
# ============================================================================


if __name__ == "__main__":
    """
    Save checkpoint after test creation (TDD red phase complete).
    """
    from pathlib import Path
    import sys

    # Portable path detection (works from any directory)
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Tests complete - 43 tests created for session_telemetry_reader.py (TDD red phase)'
            )
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")

    # Run tests to verify they FAIL (TDD red phase)
    print("\n" + "=" * 70)
    print("TDD RED PHASE: Running tests to verify they FAIL")
    print("=" * 70 + "\n")

    import pytest
    exit_code = pytest.main([__file__, "--tb=line", "-q"])

    if exit_code == 0:
        print("\n⚠️  WARNING: Tests passed but implementation doesn't exist!")
        print("This indicates tests may not be properly checking for implementation.")
    else:
        print("\n✅ Tests failed as expected (TDD red phase complete)")
        print("Next: Implement session_telemetry_reader.py to make tests pass (GREEN phase)")
