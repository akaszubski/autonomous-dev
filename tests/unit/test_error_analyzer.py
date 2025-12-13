#!/usr/bin/env python3
"""
Unit tests for error_analyzer.py library (Issue #124).

Tests the automated error capture and analysis system.

Test Strategy:
- Test error registry reading from JSONL
- Test error classification (transient vs permanent)
- Test fingerprint generation for deduplication
- Test secret redaction (CWE-532)
- Test resource limits (CWE-400)
- Test actionable error filtering
- Test error report generation

Date: 2025-12-13
Issue: #124 (Automated error capture and analysis)
Agent: test-master
"""

import json
import os
import sys
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

from error_analyzer import (
    ErrorAnalyzer,
    ErrorEntry,
    ErrorReport,
    redact_secrets,
    format_error_for_issue,
    write_error_to_registry,
    analyze_errors,
    get_actionable_errors,
    MAX_ERRORS_PER_SESSION,
    MAX_ERROR_MESSAGE_LENGTH,
    SECRET_PATTERNS,
)
from failure_classifier import FailureType


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create temporary project directory with error logs."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create .claude directory structure
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()

    errors_dir = claude_dir / "logs" / "errors"
    errors_dir.mkdir(parents=True)

    return project_dir


@pytest.fixture
def sample_errors():
    """Sample error entries for testing."""
    return [
        {
            "timestamp": "2025-12-13T10:00:00",
            "tool_name": "Bash",
            "exit_code": 1,
            "error_message": "SyntaxError: invalid syntax",
            "context": {"command_preview": "python test.py"},
        },
        {
            "timestamp": "2025-12-13T10:01:00",
            "tool_name": "Bash",
            "exit_code": 1,
            "error_message": "ConnectionError: Failed to connect to API",
            "context": {},
        },
        {
            "timestamp": "2025-12-13T10:02:00",
            "tool_name": "Task",
            "exit_code": None,
            "error_message": "TypeError: Cannot read property of undefined",
            "context": {"agent": "implementer"},
        },
    ]


@pytest.fixture
def error_file(temp_project_dir, sample_errors):
    """Create error file with sample errors."""
    date = datetime.now().strftime("%Y-%m-%d")
    errors_dir = temp_project_dir / ".claude" / "logs" / "errors"
    error_file = errors_dir / f"{date}.jsonl"

    with open(error_file, "w") as f:
        for error in sample_errors:
            f.write(json.dumps(error) + "\n")

    return error_file


# =============================================================================
# Test ErrorEntry Class
# =============================================================================

class TestErrorEntry:
    """Test ErrorEntry dataclass."""

    def test_from_dict(self, sample_errors):
        """Test creating ErrorEntry from dictionary."""
        entry = ErrorEntry.from_dict(sample_errors[0])

        assert entry.timestamp == "2025-12-13T10:00:00"
        assert entry.tool_name == "Bash"
        assert entry.exit_code == 1
        assert entry.error_message == "SyntaxError: invalid syntax"
        assert entry.context == {"command_preview": "python test.py"}

    def test_to_dict(self):
        """Test converting ErrorEntry to dictionary."""
        entry = ErrorEntry(
            timestamp="2025-12-13T10:00:00",
            tool_name="Bash",
            exit_code=1,
            error_message="Test error",
        )
        entry.failure_type = FailureType.PERMANENT
        entry.fingerprint = "abc123"

        d = entry.to_dict()

        assert d["timestamp"] == "2025-12-13T10:00:00"
        assert d["failure_type"] == "permanent"
        assert d["fingerprint"] == "abc123"


# =============================================================================
# Test Error Registry Reading
# =============================================================================

class TestErrorRegistryReading:
    """Test reading errors from registry."""

    def test_read_existing_errors(self, temp_project_dir, error_file, sample_errors):
        """Test reading errors from JSONL file."""
        analyzer = ErrorAnalyzer(temp_project_dir)
        errors = analyzer.read_error_registry()

        assert len(errors) == len(sample_errors)
        assert errors[0].tool_name == "Bash"
        assert errors[1].error_message == "ConnectionError: Failed to connect to API"

    def test_read_nonexistent_file(self, temp_project_dir):
        """Test reading from nonexistent file returns empty list."""
        analyzer = ErrorAnalyzer(temp_project_dir)
        errors = analyzer.read_error_registry("2099-01-01")

        assert errors == []

    def test_skip_malformed_lines(self, temp_project_dir):
        """Test that malformed JSONL lines are skipped."""
        date = datetime.now().strftime("%Y-%m-%d")
        errors_dir = temp_project_dir / ".claude" / "logs" / "errors"
        error_file = errors_dir / f"{date}.jsonl"

        with open(error_file, "w") as f:
            f.write('{"tool_name": "Bash", "error_message": "Valid"}\n')
            f.write('not valid json\n')
            f.write('{"tool_name": "Task", "error_message": "Also valid"}\n')

        analyzer = ErrorAnalyzer(temp_project_dir)
        errors = analyzer.read_error_registry()

        assert len(errors) == 2


# =============================================================================
# Test Error Classification
# =============================================================================

class TestErrorClassification:
    """Test error classification."""

    def test_classify_permanent_syntax_error(self, temp_project_dir, error_file):
        """Test SyntaxError is classified as permanent."""
        analyzer = ErrorAnalyzer(temp_project_dir)
        errors = analyzer.read_error_registry()
        errors = analyzer.classify_errors(errors)

        # First error is SyntaxError
        assert errors[0].failure_type == FailureType.PERMANENT

    def test_classify_transient_connection_error(self, temp_project_dir, error_file):
        """Test ConnectionError is classified as transient."""
        analyzer = ErrorAnalyzer(temp_project_dir)
        errors = analyzer.read_error_registry()
        errors = analyzer.classify_errors(errors)

        # Second error is ConnectionError
        assert errors[1].failure_type == FailureType.TRANSIENT


# =============================================================================
# Test Fingerprinting
# =============================================================================

class TestFingerprinting:
    """Test error fingerprint generation."""

    def test_fingerprint_is_consistent(self, temp_project_dir):
        """Test same error generates same fingerprint."""
        analyzer = ErrorAnalyzer(temp_project_dir)

        entry1 = ErrorEntry(
            timestamp="2025-12-13T10:00:00",
            tool_name="Bash",
            exit_code=1,
            error_message="SyntaxError: line 42",
        )
        entry1.failure_type = FailureType.PERMANENT

        entry2 = ErrorEntry(
            timestamp="2025-12-13T11:00:00",  # Different time
            tool_name="Bash",
            exit_code=1,
            error_message="SyntaxError: line 99",  # Different line number
        )
        entry2.failure_type = FailureType.PERMANENT

        fp1 = analyzer.create_fingerprint(entry1)
        fp2 = analyzer.create_fingerprint(entry2)

        # Line numbers normalized to N, so fingerprints should match
        assert fp1 == fp2

    def test_fingerprint_differs_for_different_tools(self, temp_project_dir):
        """Test different tools generate different fingerprints."""
        analyzer = ErrorAnalyzer(temp_project_dir)

        entry1 = ErrorEntry(
            timestamp="2025-12-13T10:00:00",
            tool_name="Bash",
            exit_code=1,
            error_message="SyntaxError",
        )
        entry1.failure_type = FailureType.PERMANENT

        entry2 = ErrorEntry(
            timestamp="2025-12-13T10:00:00",
            tool_name="Task",
            exit_code=1,
            error_message="SyntaxError",
        )
        entry2.failure_type = FailureType.PERMANENT

        fp1 = analyzer.create_fingerprint(entry1)
        fp2 = analyzer.create_fingerprint(entry2)

        assert fp1 != fp2


# =============================================================================
# Test Deduplication
# =============================================================================

class TestDeduplication:
    """Test error deduplication."""

    def test_deduplicate_removes_duplicates(self, temp_project_dir):
        """Test deduplication removes duplicate errors."""
        analyzer = ErrorAnalyzer(temp_project_dir)

        # Create two identical errors (different timestamps)
        errors = [
            ErrorEntry(
                timestamp="2025-12-13T10:00:00",
                tool_name="Bash",
                exit_code=1,
                error_message="SyntaxError",
            ),
            ErrorEntry(
                timestamp="2025-12-13T10:01:00",
                tool_name="Bash",
                exit_code=1,
                error_message="SyntaxError",
            ),
        ]
        for e in errors:
            e.failure_type = FailureType.PERMANENT

        unique, duplicates = analyzer.deduplicate_errors(errors)

        assert len(unique) == 1
        assert len(duplicates) == 1


# =============================================================================
# Test Secret Redaction
# =============================================================================

class TestSecretRedaction:
    """Test secret redaction (CWE-532)."""

    def test_redact_openai_key(self):
        """Test OpenAI API key is redacted."""
        message = "Error with key sk-abcdefghijklmnopqrstuvwxyz123456789012345678"
        redacted = redact_secrets(message)

        assert "sk-" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_github_token(self):
        """Test GitHub token is redacted."""
        message = "Error with token ghp_abcdefghijklmnopqrstuvwxyz123456"
        redacted = redact_secrets(message)

        assert "ghp_" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_api_key_assignment(self):
        """Test API key assignment is redacted."""
        message = 'Config: api_key = "supersecretkey1234567890"'
        redacted = redact_secrets(message)

        assert "supersecret" not in redacted
        assert "[REDACTED]" in redacted

    def test_no_redaction_for_safe_message(self):
        """Test safe messages are not modified."""
        message = "SyntaxError: unexpected indent at line 42"
        redacted = redact_secrets(message)

        assert redacted == message


# =============================================================================
# Test Actionable Filtering
# =============================================================================

class TestActionableFiltering:
    """Test filtering for actionable errors."""

    def test_filter_returns_permanent_only(self, temp_project_dir, error_file):
        """Test filter returns only permanent errors."""
        analyzer = ErrorAnalyzer(temp_project_dir)
        errors = analyzer.read_error_registry()
        errors = analyzer.classify_errors(errors)

        actionable, transient = analyzer.filter_actionable(errors)

        # Should have permanent errors (SyntaxError, TypeError)
        assert len(actionable) == 2
        # Should have transient errors (ConnectionError)
        assert len(transient) == 1

        for error in actionable:
            assert error.failure_type == FailureType.PERMANENT


# =============================================================================
# Test Full Analysis Pipeline
# =============================================================================

class TestFullAnalysis:
    """Test full analysis pipeline."""

    def test_analyze_returns_report(self, temp_project_dir, error_file, sample_errors):
        """Test analyze() returns complete ErrorReport."""
        analyzer = ErrorAnalyzer(temp_project_dir)
        report = analyzer.analyze()

        assert isinstance(report, ErrorReport)
        assert report.total_errors == len(sample_errors)
        assert report.session_date == datetime.now().strftime("%Y-%m-%d")
        assert len(report.actionable_errors) > 0

    def test_analyze_classifies_all_errors(self, temp_project_dir, error_file):
        """Test all errors are classified after analysis."""
        analyzer = ErrorAnalyzer(temp_project_dir)
        report = analyzer.analyze()

        for error in report.actionable_errors + report.transient_errors:
            assert error.failure_type is not None
            assert error.fingerprint is not None


# =============================================================================
# Test Error Writing
# =============================================================================

class TestErrorWriting:
    """Test writing errors to registry."""

    def test_write_error_creates_file(self, temp_project_dir):
        """Test writing error creates JSONL file."""
        success = write_error_to_registry(
            tool_name="Bash",
            exit_code=1,
            error_message="Test error message",
            project_root=temp_project_dir,
        )

        assert success

        date = datetime.now().strftime("%Y-%m-%d")
        error_file = temp_project_dir / ".claude" / "logs" / "errors" / f"{date}.jsonl"
        assert error_file.exists()

    def test_write_error_appends(self, temp_project_dir):
        """Test writing multiple errors appends to file."""
        write_error_to_registry(
            tool_name="Bash",
            exit_code=1,
            error_message="Error 1",
            project_root=temp_project_dir,
        )
        write_error_to_registry(
            tool_name="Task",
            exit_code=None,
            error_message="Error 2",
            project_root=temp_project_dir,
        )

        date = datetime.now().strftime("%Y-%m-%d")
        error_file = temp_project_dir / ".claude" / "logs" / "errors" / f"{date}.jsonl"

        with open(error_file) as f:
            lines = f.readlines()

        assert len(lines) == 2


# =============================================================================
# Test Format for Issue
# =============================================================================

class TestFormatForIssue:
    """Test formatting errors for GitHub issues."""

    def test_format_includes_all_fields(self):
        """Test formatted output includes all error fields."""
        entry = ErrorEntry(
            timestamp="2025-12-13T10:00:00",
            tool_name="Bash",
            exit_code=1,
            error_message="SyntaxError: invalid syntax",
            context={"command_preview": "python test.py"},
        )
        entry.failure_type = FailureType.PERMANENT
        entry.fingerprint = "abc123def456"

        formatted = format_error_for_issue(entry)

        assert "Bash" in formatted
        assert "1" in formatted  # exit code
        assert "permanent" in formatted
        assert "abc123def456" in formatted
        assert "SyntaxError" in formatted
        assert "python test.py" in formatted

    def test_format_redacts_secrets(self):
        """Test formatted output redacts secrets."""
        entry = ErrorEntry(
            timestamp="2025-12-13T10:00:00",
            tool_name="Bash",
            exit_code=1,
            error_message="Failed with key sk-abcdefghijklmnopqrstuvwxyz123456789012345678",
        )
        entry.failure_type = FailureType.PERMANENT
        entry.fingerprint = "test"

        formatted = format_error_for_issue(entry)

        assert "sk-" not in formatted
        assert "[REDACTED]" in formatted


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_analyze_errors_function(self, temp_project_dir, error_file):
        """Test analyze_errors convenience function."""
        report = analyze_errors(project_root=temp_project_dir)

        assert isinstance(report, ErrorReport)
        assert report.total_errors > 0

    def test_get_actionable_errors_function(self, temp_project_dir, error_file):
        """Test get_actionable_errors convenience function."""
        errors = get_actionable_errors(project_root=temp_project_dir)

        assert len(errors) > 0
        for error in errors:
            assert error.failure_type == FailureType.PERMANENT
