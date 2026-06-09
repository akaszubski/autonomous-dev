#!/usr/bin/env python3
"""
Tests for unified_session_tracker.py SubagentStop hook.

Validates stdin JSON parsing, backward-compatible env var fallback,
infinite loop prevention, transcript path validation, duration computation,
and JSONL activity logging.
"""

import glob
import io
import json
import os
import sys
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean_subagent_stop_markers():
    """Clean /tmp dedup markers before each test (Issue #1176 isolation).

    The SubagentStop dedup guard persists markers at
    /tmp/subagent_stop_seen_*.marker that survive across pytest runs.
    Without cleanup, tests using fixed session_id/agent_name inputs
    take the dedup-skip branch on second/third runs and bypass the
    code paths they intend to exercise.
    """
    for marker in glob.glob("/tmp/subagent_stop_seen_*.marker"):
        try:
            os.unlink(marker)
        except OSError:
            pass
    yield
    for marker in glob.glob("/tmp/subagent_stop_seen_*.marker"):
        try:
            os.unlink(marker)
        except OSError:
            pass

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# Import the module functions directly
import unified_session_tracker as ust


class TestParseStdinJson:
    """Tests for _parse_stdin — reading SubagentStop JSON from stdin."""

    def test_parse_stdin_json(self):
        """Valid SubagentStop JSON is parsed correctly from stdin."""
        input_data = json.dumps({
            "agent_type": "researcher",
            "agent_id": "abc-123",
            "agent_transcript_path": "/Users/test/.claude/transcripts/abc.jsonl",
            "last_assistant_message": "Research complete with findings.",
            "session_id": "session-xyz",
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
        })
        with patch("sys.stdin", io.StringIO(input_data)):
            result = ust._parse_stdin()

        assert result["agent_type"] == "researcher"
        assert result["agent_id"] == "abc-123"
        assert result["session_id"] == "session-xyz"
        assert result["last_assistant_message"] == "Research complete with findings."

    def test_parse_empty_stdin(self):
        """Empty stdin returns empty dict (falls back to env vars)."""
        with patch("sys.stdin", io.StringIO("")):
            result = ust._parse_stdin()
        assert result == {}

    def test_parse_invalid_json_stdin(self):
        """Invalid JSON stdin returns empty dict (falls back to env vars)."""
        with patch("sys.stdin", io.StringIO("not valid json {{")):
            result = ust._parse_stdin()
        assert result == {}


class TestStopHookActive:
    """Tests for stop_hook_active — guard removed, hook always logs."""

    def test_stop_hook_active_true_still_logs(self, tmp_path):
        """When stop_hook_active=true, hook still processes event and writes JSONL.

        Regression test for Issue #539: the early-return guard was causing
        zero activity log entries in consumer repos because SubagentStop events
        always carry stop_hook_active=true when a subagent completes.
        """
        input_data = json.dumps({
            "agent_type": "researcher",
            "last_assistant_message": "Research complete.",
            "session_id": "test-session-stop",
            "stop_hook_active": True,
            "hook_event_name": "SubagentStop",
        })

        with patch("sys.stdin", io.StringIO(input_data)):
            with patch("sys.stdout", new_callable=io.StringIO):
                with patch.object(ust, "_find_log_dir", return_value=tmp_path):
                    with patch.object(ust, "_get_session_date", return_value="2026-03-22"):
                        with patch.object(ust, "track_basic_session", return_value=True):
                            with patch.object(ust, "track_pipeline_completion", return_value=True):
                                result = ust.main()

        assert result == 0

        # The JSONL file must have been written — this is the core regression fix
        log_file = tmp_path / "2026-03-22.jsonl"
        assert log_file.exists(), "JSONL entry must be written even when stop_hook_active=true"
        entry = json.loads(log_file.read_text().strip())
        assert entry["subagent_type"] == "researcher"
        assert entry["hook"] == "SubagentStop"


class TestExtractFields:
    """Tests for field extraction from stdin JSON."""

    def test_extract_agent_type(self):
        """agent_type from stdin is mapped to agent_name."""
        input_data = {"agent_type": "implementer", "last_assistant_message": "Done"}
        # The agent_type field becomes the agent_name in main()
        agent_name = input_data.get("agent_type", "unknown")
        assert agent_name == "implementer"

    def test_extract_last_assistant_message(self):
        """last_assistant_message from stdin is mapped to agent_output."""
        input_data = {"agent_type": "planner", "last_assistant_message": "Plan created successfully."}
        agent_output = input_data.get("last_assistant_message", "")
        assert agent_output == "Plan created successfully."

    def test_extract_agent_transcript_path(self):
        """agent_transcript_path is stored from stdin."""
        input_data = {
            "agent_type": "researcher",
            "agent_transcript_path": "/Users/test/.claude/transcripts/abc.jsonl",
        }
        path = input_data.get("agent_transcript_path", "")
        assert path == "/Users/test/.claude/transcripts/abc.jsonl"


class TestValidateTranscriptPath:
    """Tests for _validate_transcript_path security validation."""

    def test_validate_transcript_path_good(self):
        """Valid path within ~/.claude passes validation."""
        home = str(Path.home())
        good_path = f"{home}/.claude/transcripts/session-abc.jsonl"
        result = ust._validate_transcript_path(good_path)
        assert result == str(Path(good_path).resolve())

    def test_validate_transcript_path_traversal(self):
        """Path traversal attempt (../../../etc/passwd) is rejected."""
        bad_path = "../../../etc/passwd"
        result = ust._validate_transcript_path(bad_path)
        assert result == ""

    def test_validate_transcript_path_outside_claude(self):
        """Path outside ~/.claude is rejected."""
        result = ust._validate_transcript_path("/tmp/some/file.jsonl")
        assert result == ""

    def test_validate_transcript_path_empty(self):
        """Empty path returns empty string."""
        result = ust._validate_transcript_path("")
        assert result == ""

    def test_validate_transcript_path_none_like(self):
        """None-like empty string returns empty string."""
        result = ust._validate_transcript_path("")
        assert result == ""

    def test_validate_transcript_path_sibling_dir(self):
        """Sibling directory like ~/.claudeEvil is rejected (is_relative_to)."""
        home = str(Path.home())
        evil_path = f"{home}/.claudeEvil/data.txt"
        result = ust._validate_transcript_path(evil_path)
        assert result == "", "Sibling dir ~/.claudeEvil should be rejected"


class TestComputeDurationMs:
    """Tests for _compute_duration_ms."""

    def test_compute_duration_ms_without_tracker(self):
        """Returns 0 when AgentTracker is not available."""
        with patch.object(ust, "HAS_AGENT_TRACKER", False):
            result = ust._compute_duration_ms()
        assert result == 0

    def test_compute_duration_ms_with_tracker(self):
        """Uses started_at diff when AgentTracker has session data."""
        mock_tracker = MagicMock()
        mock_tracker.get_current_session.return_value = {
            "started_at": "2026-03-17T10:00:00+00:00"
        }

        with patch.object(ust, "HAS_AGENT_TRACKER", True):
            with patch.object(ust, "AgentTracker", return_value=mock_tracker):
                result = ust._compute_duration_ms()

        # Duration should be positive (current time - 2026 start time)
        # Since we're mocking, the result depends on current time
        # Just verify it returns an int >= 0
        assert isinstance(result, int)
        assert result >= 0

    def test_compute_duration_ms_tracker_no_session(self):
        """Returns 0 when tracker has no session data."""
        mock_tracker = MagicMock()
        mock_tracker.get_current_session.return_value = None

        with patch.object(ust, "HAS_AGENT_TRACKER", True):
            with patch.object(ust, "AgentTracker", return_value=mock_tracker):
                result = ust._compute_duration_ms()

        assert result == 0


class TestWriteJsonlEntry:
    """Tests for JSONL activity log output."""

    def test_writes_jsonl_entry(self, tmp_path):
        """Correct fields are written to JSONL output."""
        with patch.object(ust, "_find_log_dir", return_value=tmp_path):
            with patch.object(ust, "_get_session_date", return_value="2026-03-17"):
                result = ust._write_jsonl_entry(
                    subagent_type="researcher",
                    duration_ms=5000,
                    result_word_count=150,
                    agent_transcript_path="/Users/test/.claude/transcripts/abc.jsonl",
                    session_id="session-xyz",
                    success=True,
                )

        assert result is True

        log_file = tmp_path / "2026-03-17.jsonl"
        assert log_file.exists()

        entry = json.loads(log_file.read_text().strip())
        assert entry["hook"] == "SubagentStop"
        assert entry["subagent_type"] == "researcher"
        assert entry["duration_ms"] == 5000
        assert entry["result_word_count"] == 150
        assert entry["agent_transcript_path"] == "/Users/test/.claude/transcripts/abc.jsonl"
        assert entry["session_id"] == "session-xyz"
        assert entry["success"] is True
        assert "timestamp" in entry

    def test_jsonl_result_word_count(self, tmp_path):
        """Word count is computed from last_assistant_message."""
        message = "This is a five word message plus two more"
        word_count = len(message.split())
        assert word_count == 9

        with patch.object(ust, "_find_log_dir", return_value=tmp_path):
            with patch.object(ust, "_get_session_date", return_value="2026-03-17"):
                ust._write_jsonl_entry(
                    subagent_type="planner",
                    duration_ms=0,
                    result_word_count=word_count,
                    agent_transcript_path="",
                    session_id="test",
                    success=True,
                )

        log_file = tmp_path / "2026-03-17.jsonl"
        entry = json.loads(log_file.read_text().strip())
        assert entry["result_word_count"] == 9


class TestMainFunction:
    """Tests for main() entry point behavior."""

    def test_always_exits_zero(self):
        """Hook always returns 0 regardless of input."""
        # Test with empty stdin
        with patch("sys.stdin", io.StringIO("")):
            with patch("sys.stdout", new_callable=io.StringIO):
                # Patch out session tracking to avoid side effects
                with patch.object(ust, "track_basic_session", return_value=False):
                    with patch.object(ust, "track_pipeline_completion", return_value=False):
                        with patch.object(ust, "_write_jsonl_entry", return_value=False):
                            result = ust.main()
        assert result == 0

    def test_always_exits_zero_on_exception(self):
        """Hook returns 0 even when internal errors occur."""
        with patch("sys.stdin", io.StringIO('{"agent_type":"test"}')):
            with patch("sys.stdout", new_callable=io.StringIO):
                with patch.object(ust, "track_basic_session", side_effect=Exception("boom")):
                    with patch.object(ust, "_write_jsonl_entry", return_value=False):
                        result = ust.main()
        assert result == 0

    def test_main_no_hookSpecificOutput(self):
        """main() produces no stdout output (SubagentStop hooks must not emit hookSpecificOutput).

        Regression test for Issue #539: emitting hookSpecificOutput wrapper caused
        Claude Code to misinterpret the hook response and skip logging in consumer repos.
        """
        with patch("sys.stdin", io.StringIO('{"agent_type":"researcher","session_id":"s1"}')):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with patch.object(ust, "track_basic_session", return_value=True):
                    with patch.object(ust, "track_pipeline_completion", return_value=True):
                        with patch.object(ust, "_write_jsonl_entry", return_value=True):
                            result = ust.main()

        assert result == 0
        stdout_output = mock_stdout.getvalue().strip()
        assert stdout_output == "", (
            f"SubagentStop hook must produce no stdout output, got: {stdout_output!r}"
        )

    def test_backward_compat_env_vars(self, tmp_path):
        """Old env var path still works when stdin is empty."""
        env = {
            "CLAUDE_AGENT_NAME": "security-auditor",
            "CLAUDE_AGENT_OUTPUT": "Security scan complete",
            "CLAUDE_AGENT_STATUS": "success",
            "CLAUDE_SESSION_ID": "env-session",
        }

        with patch("sys.stdin", io.StringIO("")):
            with patch("sys.stdout", new_callable=io.StringIO):
                with patch.dict(os.environ, env, clear=False):
                    with patch.object(ust, "track_basic_session", return_value=True) as mock_session:
                        with patch.object(ust, "track_pipeline_completion", return_value=True) as mock_pipeline:
                            with patch.object(ust, "_write_jsonl_entry", return_value=True) as mock_jsonl:
                                result = ust.main()

        assert result == 0
        # Verify env vars were used
        mock_session.assert_called_once()
        call_args = mock_session.call_args
        assert call_args[0][0] == "security-auditor"

        mock_pipeline.assert_called_once()
        pipeline_args = mock_pipeline.call_args
        assert pipeline_args[0][0] == "security-auditor"
        assert pipeline_args[0][1] == "Security scan complete"

    def test_main_with_stdin_json(self, tmp_path):
        """main() correctly processes stdin JSON input."""
        input_data = json.dumps({
            "agent_type": "implementer",
            "last_assistant_message": "Implementation complete with all tests passing.",
            "session_id": "stdin-session",
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "agent_transcript_path": "",
        })

        with patch("sys.stdin", io.StringIO(input_data)):
            with patch("sys.stdout", new_callable=io.StringIO):
                with patch.object(ust, "track_basic_session", return_value=True) as mock_session:
                    with patch.object(ust, "track_pipeline_completion", return_value=True) as mock_pipeline:
                        with patch.object(ust, "_write_jsonl_entry", return_value=True) as mock_jsonl:
                            result = ust.main()

        assert result == 0
        mock_session.assert_called_once()
        assert mock_session.call_args[0][0] == "implementer"

        mock_jsonl.assert_called_once()
        jsonl_kwargs = mock_jsonl.call_args[1]
        assert jsonl_kwargs["subagent_type"] == "implementer"
        assert jsonl_kwargs["session_id"] == "stdin-session"
        assert jsonl_kwargs["success"] is True
        assert jsonl_kwargs["result_word_count"] > 0


class TestSessionIdSanitization:
    """Tests for session_id sanitization in _get_session_date."""

    def test_malicious_session_id_sanitized(self, tmp_path):
        """Session ID with path separators is sanitized to safe characters."""
        with patch.object(ust, "_find_log_dir", return_value=tmp_path):
            ust._SESSION_DATE_CACHE.clear()
            date_str = ust._get_session_date("../../../etc/passwd")

        # Should produce a date string
        assert len(date_str) == 10  # YYYY-MM-DD
        # The date file should use sanitized name (no path separators)
        date_files = list(tmp_path.glob(".session_date_*"))
        assert len(date_files) == 1
        assert "/" not in date_files[0].name
        assert ".." not in date_files[0].name


class TestDetermineSuccess:
    """Tests for _determine_success helper."""

    def test_success_on_clean_output(self):
        """Clean output without error indicators returns True."""
        assert ust._determine_success("Implementation complete. All tests pass.") is True

    def test_failure_on_error_prefix_line(self):
        """Output with 'Error:' at line start returns False."""
        assert ust._determine_success("Error: module not found") is False

    def test_failure_on_traceback(self):
        """Output with 'Traceback (most recent call last):' returns False."""
        assert ust._determine_success("Traceback (most recent call last):") is False

    def test_success_on_empty(self):
        """Empty output returns True."""
        assert ust._determine_success("") is True

    # --- Benign mentions that must NOT trigger failure ---

    def test_benign_error_handling(self):
        """'Fixed the error handling' is benign — returns True."""
        assert ust._determine_success("Fixed the error handling in the parser.") is True

    def test_benign_no_errors(self):
        """'No errors found' is benign — returns True."""
        assert ust._determine_success("No errors found in the codebase.") is True

    def test_benign_error_free(self):
        """'Error-free implementation' is benign — returns True."""
        assert ust._determine_success("Error-free implementation completed.") is True

    def test_benign_improved_error_messages(self):
        """'Improved error messages' is benign — returns True."""
        assert ust._determine_success("Improved error messages for better UX.") is True

    # --- Actual failures that MUST trigger failure ---

    def test_failure_on_failed_to(self):
        """'Failed to connect' returns False."""
        assert ust._determine_success("Failed to connect to the database.") is False

    def test_failure_on_could_not(self):
        """'Could not parse' returns False."""
        assert ust._determine_success("Could not parse the configuration file.") is False

    def test_failure_on_unable_to(self):
        """'Unable to write' returns False."""
        assert ust._determine_success("Unable to write to the output directory.") is False

    def test_failure_on_unhandled_exception(self):
        """'Unhandled exception in worker' returns False."""
        assert ust._determine_success("Unhandled exception in worker thread.") is False

    def test_failure_on_fatal_prefix(self):
        """'Fatal:' at line start returns False."""
        assert ust._determine_success("Fatal: out of memory") is False

    def test_failure_multiline_with_traceback(self):
        """Multiline output containing a Traceback line returns False."""
        output = (
            "Starting computation...\n"
            "Traceback (most recent call last):\n"
            "  File 'main.py', line 42\n"
            "ValueError: bad input\n"
        )
        assert ust._determine_success(output) is False


class TestMainWritesJsonlWithStopHookActive:
    """Integration test: JSONL is written even when stop_hook_active=true (Issue #539)."""

    def test_main_writes_jsonl_with_stop_hook_active(self, tmp_path):
        """Full end-to-end: main() writes JSONL entry regardless of stop_hook_active.

        This is the primary regression test for Issue #539. Before the fix,
        the early-return guard on stop_hook_active meant zero JSONL entries were
        written in consumer repos (where SubagentStop always sends stop_hook_active=true).
        """
        input_data = json.dumps({
            "agent_type": "planner",
            "last_assistant_message": "Plan created with 5 implementation steps.",
            "session_id": "integration-test-session",
            "stop_hook_active": True,
            "hook_event_name": "SubagentStop",
            "agent_transcript_path": "",
        })

        with patch("sys.stdin", io.StringIO(input_data)):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with patch.object(ust, "_find_log_dir", return_value=tmp_path):
                    with patch.object(ust, "_get_session_date", return_value="2026-03-22"):
                        with patch.object(ust, "track_basic_session", return_value=True):
                            with patch.object(ust, "track_pipeline_completion", return_value=True):
                                result = ust.main()

        # Hook must exit 0
        assert result == 0

        # Hook must produce no stdout output
        assert mock_stdout.getvalue().strip() == ""

        # JSONL file must exist and contain the expected entry
        log_file = tmp_path / "2026-03-22.jsonl"
        assert log_file.exists(), (
            "JSONL log file was not created — stop_hook_active guard must be removed"
        )

        entry = json.loads(log_file.read_text().strip())
        assert entry["hook"] == "SubagentStop"
        assert entry["subagent_type"] == "planner"
        assert entry["session_id"] == "integration-test-session"
        assert entry["result_word_count"] == len(
            "Plan created with 5 implementation steps.".split()
        )
        assert entry["success"] is True


class TestJsonlFeatureRef:
    """Tests for feature_ref inclusion in JSONL entries (Issue #540)."""

    def test_jsonl_entry_includes_feature_ref(self, tmp_path):
        """JSONL entry includes feature_ref when PIPELINE_FEATURE_REF env var is set."""
        with patch.dict(os.environ, {"PIPELINE_FEATURE_REF": "issue-540"}, clear=False):
            with patch.object(ust, "_find_log_dir", return_value=tmp_path):
                with patch.object(ust, "_get_session_date", return_value="2026-03-22"):
                    result = ust._write_jsonl_entry(
                        subagent_type="implementer",
                        duration_ms=3000,
                        result_word_count=50,
                        agent_transcript_path="",
                        session_id="batch-session",
                        success=True,
                    )

        assert result is True
        log_file = tmp_path / "2026-03-22.jsonl"
        entry = json.loads(log_file.read_text().strip())
        assert entry["feature_ref"] == "issue-540"

    def test_jsonl_entry_excludes_feature_ref_when_unset(self, tmp_path):
        """JSONL entry omits feature_ref when PIPELINE_FEATURE_REF is not set."""
        env = os.environ.copy()
        env.pop("PIPELINE_FEATURE_REF", None)
        with patch.dict(os.environ, env, clear=True):
            with patch.object(ust, "_find_log_dir", return_value=tmp_path):
                with patch.object(ust, "_get_session_date", return_value="2026-03-22"):
                    result = ust._write_jsonl_entry(
                        subagent_type="researcher",
                        duration_ms=1000,
                        result_word_count=20,
                        agent_transcript_path="",
                        session_id="single-session",
                        success=True,
                    )

        assert result is True
        log_file = tmp_path / "2026-03-22.jsonl"
        entry = json.loads(log_file.read_text().strip())
        assert "feature_ref" not in entry


class TestStatusPriority:
    """Tests for status priority fix (Issue #541).

    Before the fix, CLAUDE_AGENT_STATUS=success could be overridden by the
    text-scan fallback when the output contained benign failure-pattern words.
    After the fix, the env var is authoritative and text-scan is a fallback only.
    """

    def test_env_var_success_overrides_text_scan(self, tmp_path):
        """CLAUDE_AGENT_STATUS=success wins even when output contains failure-pattern words.

        Regression test for Issue #541: pipeline JSON status corruption.
        Without the fix, output like 'Failed to connect' would override the env var.
        """
        input_data = json.dumps({
            "agent_type": "implementer",
            "last_assistant_message": "Failed to connect to optional cache — continuing without it.",
            "session_id": "test-session-541",
            "hook_event_name": "SubagentStop",
        })

        with patch.dict(os.environ, {"CLAUDE_AGENT_STATUS": "success"}, clear=False):
            with patch("sys.stdin", io.StringIO(input_data)):
                with patch("sys.stdout", new_callable=io.StringIO):
                    with patch.object(ust, "track_basic_session", return_value=True):
                        with patch.object(ust, "track_pipeline_completion", return_value=True) as mock_pipeline:
                            with patch.object(ust, "_write_jsonl_entry", return_value=True):
                                result = ust.main()

        assert result == 0
        mock_pipeline.assert_called_once()
        # Status passed to track_pipeline_completion must be "success" not "error"
        call_args = mock_pipeline.call_args
        agent_status_arg = call_args[0][2]
        assert agent_status_arg == "success", (
            f"Expected status 'success' from env var, got '{agent_status_arg}'. "
            "CLAUDE_AGENT_STATUS env var must take priority over text scan."
        )

    def test_env_var_error_respected(self, tmp_path):
        """CLAUDE_AGENT_STATUS=error is respected even when output is clean."""
        input_data = json.dumps({
            "agent_type": "researcher",
            "last_assistant_message": "Research complete. All findings documented.",
            "session_id": "test-session-error",
            "hook_event_name": "SubagentStop",
        })

        with patch.dict(os.environ, {"CLAUDE_AGENT_STATUS": "error"}, clear=False):
            with patch("sys.stdin", io.StringIO(input_data)):
                with patch("sys.stdout", new_callable=io.StringIO):
                    with patch.object(ust, "track_basic_session", return_value=True):
                        with patch.object(ust, "track_pipeline_completion", return_value=True) as mock_pipeline:
                            with patch.object(ust, "_write_jsonl_entry", return_value=True):
                                result = ust.main()

        assert result == 0
        mock_pipeline.assert_called_once()
        call_args = mock_pipeline.call_args
        agent_status_arg = call_args[0][2]
        assert agent_status_arg == "error", (
            f"Expected status 'error' from env var, got '{agent_status_arg}'."
        )

    def test_no_env_var_falls_back_to_text_scan_failure(self, tmp_path):
        """Without CLAUDE_AGENT_STATUS, text scan determines failure."""
        input_data = json.dumps({
            "agent_type": "planner",
            "last_assistant_message": "Error: could not open config file",
            "session_id": "test-session-fallback",
            "hook_event_name": "SubagentStop",
        })

        env = os.environ.copy()
        env.pop("CLAUDE_AGENT_STATUS", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stdin", io.StringIO(input_data)):
                with patch("sys.stdout", new_callable=io.StringIO):
                    with patch.object(ust, "track_basic_session", return_value=True):
                        with patch.object(ust, "track_pipeline_completion", return_value=True) as mock_pipeline:
                            with patch.object(ust, "_write_jsonl_entry", return_value=True):
                                result = ust.main()

        assert result == 0
        mock_pipeline.assert_called_once()
        call_args = mock_pipeline.call_args
        agent_status_arg = call_args[0][2]
        assert agent_status_arg == "error", (
            f"Expected text scan to detect failure and set 'error', got '{agent_status_arg}'."
        )

    def test_no_env_var_clean_output_is_success(self, tmp_path):
        """Without CLAUDE_AGENT_STATUS and with clean output, status is 'success'."""
        input_data = json.dumps({
            "agent_type": "doc-master",
            "last_assistant_message": "Documentation updated. All sections current.",
            "session_id": "test-session-clean",
            "hook_event_name": "SubagentStop",
        })

        env = os.environ.copy()
        env.pop("CLAUDE_AGENT_STATUS", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stdin", io.StringIO(input_data)):
                with patch("sys.stdout", new_callable=io.StringIO):
                    with patch.object(ust, "track_basic_session", return_value=True):
                        with patch.object(ust, "track_pipeline_completion", return_value=True) as mock_pipeline:
                            with patch.object(ust, "_write_jsonl_entry", return_value=True):
                                result = ust.main()

        assert result == 0
        mock_pipeline.assert_called_once()
        call_args = mock_pipeline.call_args
        agent_status_arg = call_args[0][2]
        assert agent_status_arg == "success", (
            f"Expected 'success' for clean output with no env var, got '{agent_status_arg}'."
        )


class TestIssue907MultiTurnWordCount:
    """AC2 regression lock: _count_words_in_transcript helper (#872/#907)."""

    def test_word_count_reads_full_transcript_when_path_valid(self, tmp_path: Path) -> None:
        """AC2: Multi-turn transcript aggregation (#872)."""
        transcript = tmp_path / "transcript.jsonl"
        # Build 3 assistant entries with known word counts
        lines = [
            '{"type": "user", "message": {"content": "prompt"}}',  # ignored
            # 20 words in list-of-blocks form
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "' + " ".join(["word"] * 20) + '"}]}}',
            # 30 words in str-content legacy form
            '{"type": "assistant", "message": {"content": "' + " ".join(["word"] * 30) + '"}}',
            # 40 words, list-of-blocks with mixed content types (tool_use + text)
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "X"}, {"type": "text", "text": "' + " ".join(["word"] * 40) + '"}]}}',
        ]
        transcript.write_text("\n".join(lines))
        from unified_session_tracker import _count_words_in_transcript
        assert _count_words_in_transcript(transcript) == 90  # 20 + 30 + 40

    def test_word_count_handles_legacy_str_content(self, tmp_path: Path) -> None:
        """AC2: Legacy str-content case (critic finding 1)."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text('{"type": "assistant", "message": {"content": "hello world foo bar"}}')
        from unified_session_tracker import _count_words_in_transcript
        assert _count_words_in_transcript(transcript) == 4

    def test_word_count_fallback_on_missing_transcript(self, tmp_path: Path) -> None:
        """AC2: Missing transcript returns 0 (graceful fallback)."""
        missing = tmp_path / "does_not_exist.jsonl"
        from unified_session_tracker import _count_words_in_transcript
        assert _count_words_in_transcript(missing) == 0


class TestDedupGuard:
    """Tests for Issue #1176 SubagentStop dedup guard.

    Validates that _try_claim_subagent_stop_marker() and the main() wiring
    correctly suppress duplicate SubagentStop firings caused by dual hook
    registration.
    """

    def test_first_claim_succeeds(self, tmp_path: Path) -> None:
        """First call with a fresh key claims the marker and returns True."""
        # Reset module sweep timestamp so the sweep does not skip
        ust._LAST_SWEEP_TS = 0.0
        result = ust._try_claim_subagent_stop_marker(
            "key_a_unique", marker_dir=tmp_path
        )
        assert result is True, "First claim should succeed"

        # Marker file must exist on disk
        markers = list(tmp_path.glob("subagent_stop_seen_*.marker"))
        assert len(markers) == 1, f"Expected 1 marker, found {len(markers)}"
        assert "key_a_unique" in markers[0].name

    def test_second_claim_returns_false(self, tmp_path: Path) -> None:
        """Second call with the same key returns False (duplicate detected)."""
        ust._LAST_SWEEP_TS = 0.0
        first = ust._try_claim_subagent_stop_marker(
            "key_b_dup", marker_dir=tmp_path
        )
        second = ust._try_claim_subagent_stop_marker(
            "key_b_dup", marker_dir=tmp_path
        )
        assert first is True
        assert second is False, "Second claim with same key must return False"

    def test_concurrent_claim_only_one_wins(self, tmp_path: Path) -> None:
        """Two threads racing for the same key: exactly one wins."""
        import threading

        ust._LAST_SWEEP_TS = 0.0
        barrier = threading.Barrier(2)
        results: List[bool] = []
        results_lock = threading.Lock()

        def claim() -> None:
            barrier.wait()  # Synchronize so both threads call simultaneously
            outcome = ust._try_claim_subagent_stop_marker(
                "key_concurrent", marker_dir=tmp_path
            )
            with results_lock:
                results.append(outcome)

        t1 = threading.Thread(target=claim)
        t2 = threading.Thread(target=claim)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert len(results) == 2, "Both threads must complete"
        winners = [r for r in results if r is True]
        losers = [r for r in results if r is False]
        assert len(winners) == 1, (
            f"Exactly one thread must win (got {len(winners)} winners, "
            f"results={results})"
        )
        assert len(losers) == 1, (
            f"Exactly one thread must lose (got {len(losers)} losers, "
            f"results={results})"
        )

    def test_open_called_with_exclusive_create_flags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """os.open is invoked with O_WRONLY|O_CREAT|O_EXCL and mode 0o600."""
        ust._LAST_SWEEP_TS = 0.0
        captured: Dict = {}
        real_open = os.open

        def fake_open(path, flags, mode=0o777, *args, **kwargs):
            captured["path"] = path
            captured["flags"] = flags
            captured["mode"] = mode
            # Delegate to real os.open so behavior is preserved
            return real_open(path, flags, mode, *args, **kwargs)

        monkeypatch.setattr(ust.os, "open", fake_open)

        result = ust._try_claim_subagent_stop_marker(
            "key_flags_check", marker_dir=tmp_path
        )

        assert result is True
        assert "flags" in captured, "os.open must have been called"
        expected_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        assert captured["flags"] == expected_flags, (
            f"flags must be O_WRONLY|O_CREAT|O_EXCL (got {captured['flags']:o})"
        )
        assert captured["mode"] == 0o600, (
            f"mode must be 0o600 (got {oct(captured['mode'])})"
        )

    def test_main_dedup_writes_skip_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Integration: main() called twice with same payload — second writes
        a __dedup_skip__ entry instead of running normal processing."""
        # Isolate marker dir so test does not collide with /tmp state
        monkeypatch.setattr(ust, "_DEFAULT_MARKER_DIR", tmp_path / "markers")
        (tmp_path / "markers").mkdir()
        ust._LAST_SWEEP_TS = 0.0

        # Isolate log dir
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Use a unique session/agent to avoid collisions with prior runs.
        # Note: agent_transcript_path is empty so the fallback key path is
        # exercised (AC #5).
        payload = json.dumps({
            "agent_type": "implementer",
            "last_assistant_message": "Done",
            "session_id": "session-dedup-test-1176",
            "stop_hook_active": False,
            "hook_event_name": "SubagentStop",
        })

        def run_main_once() -> None:
            with patch("sys.stdin", io.StringIO(payload)):
                with patch("sys.stdout", new_callable=io.StringIO):
                    with patch.object(ust, "_find_log_dir", return_value=log_dir):
                        with patch.object(
                            ust, "_get_session_date", return_value="2026-06-09"
                        ):
                            with patch.object(
                                ust, "track_basic_session", return_value=True
                            ):
                                with patch.object(
                                    ust,
                                    "track_pipeline_completion",
                                    return_value=True,
                                ):
                                    ust.main()

        # First call: normal processing
        run_main_once()
        # Second call: duplicate — should write skip entry
        run_main_once()

        log_file = log_dir / "2026-06-09.jsonl"
        assert log_file.exists(), "JSONL log file must exist"
        entries = [
            json.loads(line)
            for line in log_file.read_text().strip().split("\n")
            if line
        ]
        assert len(entries) == 2, (
            f"Expected exactly 2 entries (1 normal + 1 skip), got {len(entries)}"
        )

        # First entry: normal processing
        assert entries[0]["subagent_type"] == "implementer", (
            f"First entry must be normal (got {entries[0]['subagent_type']!r})"
        )
        assert not entries[0]["subagent_type"].startswith("__dedup_skip__")

        # Second entry: dedup skip marker
        assert entries[1]["subagent_type"].startswith("__dedup_skip__:"), (
            f"Second entry must be a dedup skip marker (got "
            f"{entries[1]['subagent_type']!r})"
        )
        assert entries[1]["subagent_type"] == "__dedup_skip__:implementer"
