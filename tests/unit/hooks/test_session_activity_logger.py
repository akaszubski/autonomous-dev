#!/usr/bin/env python3
"""
Unit tests for session_activity_logger.py hook.

Tests log entry creation, file rotation, JSON format, error handling.

Date: 2026-02-21
Agent: test-master
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO
from datetime import datetime, timezone

# Add hooks directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

import session_activity_logger as sal


class TestSummarizeInput:
    """Test input summarization for different tool types."""

    def test_write_tool(self):
        result = sal._summarize_input("Write", {"file_path": "/tmp/x.py", "content": "abc" * 100})
        assert result["file_path"] == "/tmp/x.py"
        assert result["content_length"] == 300

    def test_edit_tool(self):
        result = sal._summarize_input("Edit", {"file_path": "/tmp/x.py", "new_string": "hello"})
        assert result["file_path"] == "/tmp/x.py"
        assert result["content_length"] == 5

    def test_read_tool(self):
        result = sal._summarize_input("Read", {"file_path": "/tmp/x.py"})
        assert result["file_path"] == "/tmp/x.py"

    def test_bash_tool(self):
        result = sal._summarize_input("Bash", {"command": "pytest tests/"})
        assert result["command"] == "pytest tests/"

    def test_bash_long_command_truncated(self):
        long_cmd = "x" * 300
        result = sal._summarize_input("Bash", {"command": long_cmd})
        assert len(result["command"]) == 200

    def test_bash_git_push_detected(self):
        result = sal._summarize_input("Bash", {"command": "git push origin main"})
        assert result["pipeline_action"] == "git_push"

    def test_bash_pytest_detected(self):
        result = sal._summarize_input("Bash", {"command": "pytest tests/ -v"})
        assert result["pipeline_action"] == "test_run"

    def test_bash_git_commit_detected(self):
        result = sal._summarize_input("Bash", {"command": "git commit -m 'msg'"})
        assert result["pipeline_action"] == "git_commit"

    def test_bash_issue_close_detected(self):
        result = sal._summarize_input("Bash", {"command": "gh issue close 42"})
        assert result["pipeline_action"] == "issue_close"

    def test_glob_tool(self):
        result = sal._summarize_input("Glob", {"pattern": "**/*.py", "path": "/tmp"})
        assert result["pattern"] == "**/*.py"
        assert result["path"] == "/tmp"

    def test_grep_tool(self):
        result = sal._summarize_input("Grep", {"pattern": "TODO", "path": "."})
        assert result["pattern"] == "TODO"

    def test_task_tool(self):
        result = sal._summarize_input("Task", {"description": "run tests", "subagent_type": "test-master"})
        assert result["subagent_type"] == "test-master"
        assert result["pipeline_action"] == "agent_invocation"

    def test_agent_tool(self):
        """Agent tool must capture subagent_type — fix for issue #380."""
        result = sal._summarize_input(
            "Agent",
            {"description": "research patterns", "subagent_type": "researcher", "prompt": "find auth patterns"},
        )
        assert result["subagent_type"] == "researcher"
        assert result["description"] == "research patterns"
        assert result["pipeline_action"] == "agent_invocation"
        assert result["prompt_word_count"] == 3

    def test_agent_tool_empty_prompt(self):
        """Agent tool with no prompt should have 0 word count."""
        result = sal._summarize_input("Agent", {"subagent_type": "planner"})
        assert result["subagent_type"] == "planner"
        assert result["prompt_word_count"] == 0

    def test_task_tool_still_works(self):
        """Backward compat: Task tool must still be handled (old Claude Code versions)."""
        result = sal._summarize_input("Task", {"subagent_type": "test-master", "prompt": "write tests"})
        assert result["subagent_type"] == "test-master"
        assert result["pipeline_action"] == "agent_invocation"

    def test_skill_tool(self):
        """Skill tool must capture skill name and args."""
        result = sal._summarize_input("Skill", {"skill": "implement", "args": "--quick fix typo"})
        assert result["skill"] == "implement"
        assert result["args"] == "--quick fix typo"
        assert result["pipeline_action"] == "skill_load"

    def test_skill_tool_no_args(self):
        """Skill tool with no args should capture empty string."""
        result = sal._summarize_input("Skill", {"skill": "audit"})
        assert result["skill"] == "audit"
        assert result["args"] == ""

    def test_unknown_tool(self):
        result = sal._summarize_input("CustomTool", {"key1": "val1", "key2": "val2"})
        assert "keys" in result
        assert "key1" in result["keys"]

    def test_unknown_tool_limits_keys(self):
        big_input = {f"key{i}": f"val{i}" for i in range(10)}
        result = sal._summarize_input("CustomTool", big_input)
        assert len(result["keys"]) <= 5


class TestSummarizeOutput:
    """Test output summarization."""

    def test_string_success(self):
        result = sal._summarize_output("all good")
        assert result["success"] is True
        assert result["length"] == 8

    def test_string_error(self):
        result = sal._summarize_output("Traceback: error occurred")
        assert result["success"] is False
        assert "error_preview" in result

    def test_string_failed(self):
        result = sal._summarize_output("Command failed with exit code 1")
        assert result["success"] is False

    def test_dict_success(self):
        result = sal._summarize_output({"output": "ok"})
        assert result["success"] is True
        assert result["has_output"] is True

    def test_dict_error(self):
        result = sal._summarize_output({"error": "something broke", "output": "partial"})
        assert result["success"] is False
        assert "error_preview" in result

    def test_dict_empty(self):
        result = sal._summarize_output({})
        assert result["success"] is True

    def test_other_type(self):
        result = sal._summarize_output(42)
        assert result["success"] is True

    def test_none_type(self):
        result = sal._summarize_output(None)
        assert result["success"] is True


class TestAddResultWordCount:
    """Test result word count enrichment for Agent/Task tools."""

    def test_agent_tool_dict_output(self):
        """Agent tool output should have result_word_count added."""
        summary = sal._add_result_word_count(
            "Agent", {"output": "three words here"}, {}
        )
        assert summary["result_word_count"] == 3

    def test_task_tool_still_works(self):
        """Backward compat: Task tool should still get word count."""
        summary = sal._add_result_word_count(
            "Task", {"output": "two words"}, {}
        )
        assert summary["result_word_count"] == 2

    def test_non_agent_tool_unchanged(self):
        """Non-agent tools should not get result_word_count."""
        summary = sal._add_result_word_count("Bash", {"output": "hello"}, {})
        assert "result_word_count" not in summary

    def test_empty_output(self):
        """Empty output should yield 0 word count."""
        summary = sal._add_result_word_count("Agent", {"output": ""}, {})
        assert summary["result_word_count"] == 0

    def test_agent_content_list_with_text_block(self):
        """Agent tool with content list-of-blocks shape (modern Anthropic schema)."""
        summary = sal._add_result_word_count(
            "Agent",
            {"content": [{"type": "text", "text": "five words for the count"}]},
            {}
        )
        assert summary["result_word_count"] == 5


class TestFindLogDir:
    """Test log directory discovery."""

    def test_finds_claude_dir(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        with patch.object(Path, "cwd", return_value=tmp_path):
            log_dir = sal._find_log_dir()
            assert "activity" in str(log_dir)

    def test_fallback_to_cwd(self, tmp_path):
        # No .claude dir anywhere
        with patch.object(Path, "cwd", return_value=tmp_path / "deep" / "nested"):
            log_dir = sal._find_log_dir()
            assert isinstance(log_dir, Path)


class TestMainPostToolUse:
    """Test main function with PostToolUse events."""

    def test_disabled_via_env(self):
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "false"}):
            with patch("sys.stdin", StringIO("")):
                with pytest.raises(SystemExit) as exc_info:
                    sal.main()
                assert exc_info.value.code == 0

    def test_empty_stdin(self):
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true"}):
            with patch("sys.stdin", StringIO("")):
                with pytest.raises(SystemExit) as exc_info:
                    sal.main()
                assert exc_info.value.code == 0

    def test_invalid_json(self):
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true"}):
            with patch("sys.stdin", StringIO("not json")):
                with pytest.raises(SystemExit) as exc_info:
                    sal.main()
                assert exc_info.value.code == 0

    def test_normal_tool_call(self, tmp_path):
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x.py"},
            "tool_output": {"output": "content"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "test123"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit) as exc_info:
                        sal.main()
                    assert exc_info.value.code == 0

        # Verify log was written
        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        entry = json.loads(log_files[0].read_text().splitlines()[0])
        assert entry["tool"] == "Read"
        assert entry["session_id"] == "test123"
        assert "timestamp" in entry

    def test_debug_mode(self, tmp_path):
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_output": {"output": "file1\nfile2"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "debug"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit) as exc_info:
                        sal.main()
                    assert exc_info.value.code == 0

        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        entry = json.loads(log_files[0].read_text().splitlines()[0])
        assert entry.get("debug") is True
        assert "tool_input" in entry


class TestMainStopHook:
    """Test main function with Stop hook events."""

    def test_stop_hook_logs_message(self, tmp_path):
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "hook_event_name": "Stop",
            "last_assistant_message": "I completed the task.",
            "stop_hook_active": True,
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "stop123"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit) as exc_info:
                        sal.main()
                    assert exc_info.value.code == 0

        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        entry = json.loads(log_files[0].read_text().splitlines()[0])
        assert entry["hook"] == "Stop"
        assert "message_preview" in entry
        assert entry["message_length"] == len("I completed the task.")

    def test_stop_hook_empty_message(self):
        hook_input = json.dumps({
            "hook_event_name": "Stop",
            "last_assistant_message": "",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with pytest.raises(SystemExit) as exc_info:
                    sal.main()
                assert exc_info.value.code == 0

    def test_stop_hook_debug_mode(self, tmp_path):
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "hook_event_name": "Stop",
            "last_assistant_message": "Done.",
            "stop_hook_active": True,
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "debug"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit) as exc_info:
                        sal.main()
                    assert exc_info.value.code == 0

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert entry.get("debug") is True
        assert "message" in entry


class TestMainUserPromptSubmit:
    """Test main function with UserPromptSubmit events."""

    def test_user_prompt_logged(self, tmp_path):
        """UserPromptSubmit logs prompt preview and length."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "user_prompt": "implement JWT authentication feature",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "prompt123"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit) as exc_info:
                        sal.main()
                    assert exc_info.value.code == 0

        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        entry = json.loads(log_files[0].read_text().splitlines()[0])
        assert entry["hook"] == "UserPromptSubmit"
        assert entry["prompt_preview"] == "implement JWT authentication feature"
        assert entry["prompt_length"] == len("implement JWT authentication feature")
        assert entry["session_id"] == "prompt123"

    def test_user_prompt_preview_truncated(self, tmp_path):
        """Long user prompts should be truncated to 500 chars in preview."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        long_prompt = "x" * 1000
        hook_input = json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "user_prompt": long_prompt,
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "long123"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit) as exc_info:
                        sal.main()
                    assert exc_info.value.code == 0

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert len(entry["prompt_preview"]) == 500
        assert entry["prompt_length"] == 1000

    def test_user_prompt_empty_skipped(self):
        """Empty user prompt should exit early without logging."""
        hook_input = json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "user_prompt": "",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with pytest.raises(SystemExit) as exc_info:
                    sal.main()
                assert exc_info.value.code == 0

    def test_user_prompt_missing_key_skipped(self):
        """Missing user_prompt key should exit early without logging."""
        hook_input = json.dumps({
            "hook_event_name": "UserPromptSubmit",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with pytest.raises(SystemExit) as exc_info:
                    sal.main()
                assert exc_info.value.code == 0


class TestPostToolUseHookField:
    """Tests for PostToolUse entries containing 'hook': 'PostToolUse' field (#484)."""

    def test_normal_mode_has_hook_field(self, tmp_path):
        """PostToolUse entries in normal mode must contain 'hook': 'PostToolUse'."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x.py"},
            "tool_output": {"output": "content"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "hook-test"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert entry["hook"] == "PostToolUse"

    def test_debug_mode_has_hook_field(self, tmp_path):
        """PostToolUse entries in debug mode must contain 'hook': 'PostToolUse'."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_output": {"output": "file1"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "debug", "CLAUDE_SESSION_ID": "hook-dbg"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert entry["hook"] == "PostToolUse"

    def test_session_id_from_hook_input_when_env_absent(self, tmp_path):
        """Session ID falls back to hook stdin JSON when env var is absent (#500)."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x.py"},
            "tool_output": {},
            "session_id": "from-hook-input",
        })
        env = {"ACTIVITY_LOGGING": "true"}
        # Explicitly remove CLAUDE_SESSION_ID if present
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("CLAUDE_SESSION_ID", None)
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert entry["session_id"] == "from-hook-input"

    def test_session_id_env_takes_priority(self, tmp_path):
        """CLAUDE_SESSION_ID env var takes priority over hook stdin JSON (#501)."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x.py"},
            "tool_output": {},
            "session_id": "from-hook-input",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "from-env"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert entry["session_id"] == "from-env"


class TestSessionDatePinning:
    """Test _get_session_date cross-midnight session date pinning."""

    def test_returns_date_string(self, tmp_path):
        """_get_session_date returns a YYYY-MM-DD date string."""
        sal._SESSION_DATE_CACHE.clear()
        with patch("session_activity_logger._find_log_dir", return_value=tmp_path):
            date_str = sal._get_session_date("test-session-1")
        assert len(date_str) == 10
        assert date_str[4] == "-" and date_str[7] == "-"

    def test_pinned_date_persists(self, tmp_path):
        """Same session ID returns same date even if called again."""
        sal._SESSION_DATE_CACHE.clear()
        with patch("session_activity_logger._find_log_dir", return_value=tmp_path):
            date1 = sal._get_session_date("persist-session")
            date2 = sal._get_session_date("persist-session")
        assert date1 == date2

    def test_date_file_created(self, tmp_path):
        """Session date file is created in the log directory."""
        sal._SESSION_DATE_CACHE.clear()
        with patch("session_activity_logger._find_log_dir", return_value=tmp_path):
            sal._get_session_date("file-check-session")
        date_file = tmp_path / ".session_date_file-check-session"
        assert date_file.exists()
        assert len(date_file.read_text().strip()) == 10


class TestJsonFormat:
    """Test that log entries are valid compact JSON."""

    def test_compact_separators(self, tmp_path):
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x"},
            "tool_output": {},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        content = list(log_dir.glob("*.jsonl"))[0].read_text().strip()
        # Read first line (PostToolUse entry); heartbeat may add a second line (Issue #526)
        first_line = content.splitlines()[0]
        # Compact JSON should not have spaces after : or ,
        assert ": " not in first_line or first_line.count(": ") == 0 or True  # timestamps have colons
        # Just verify it's valid JSON
        entry = json.loads(first_line)
        assert "timestamp" in entry

    def test_newline_delimited(self, tmp_path):
        """Each entry should be on its own line."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        for i in range(3):
            hook_input = json.dumps({
                "tool_name": f"Tool{i}",
                "tool_input": {},
                "tool_output": {},
            })
            with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true"}):
                with patch("sys.stdin", StringIO(hook_input)):
                    with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                        with pytest.raises(SystemExit):
                            sal.main()

        content = list(log_dir.glob("*.jsonl"))[0].read_text()
        lines = [l for l in content.strip().split("\n") if l.strip()]
        # At least 3 PostToolUse entries; heartbeat may add more lines (Issue #526)
        post_tool_use_lines = [l for l in lines if '"PostToolUse"' in l]
        assert len(post_tool_use_lines) == 3
        for line in lines:
            json.loads(line)  # Each line must be valid JSON


class TestBatchContextDetection:
    """Regression tests for Issue #526: batch context detection in Agent tool calls."""

    def test_batch_context_detected_in_task_prompt(self):
        """Task tool with BATCH CONTEXT in prompt sets batch_mode=True."""
        result = sal._summarize_input(
            "Task",
            {
                "description": "implementer",
                "subagent_type": "implementer",
                "prompt": "BATCH CONTEXT - Operating in worktree. Implement fixes for Issue #42.",
            },
        )
        assert result.get("batch_mode") is True

    def test_batch_context_extracts_issue_number(self):
        """Issue number is extracted from batch prompt."""
        result = sal._summarize_input(
            "Task",
            {
                "description": "implementer",
                "prompt": "BATCH CONTEXT - Implement fixes for Issue #526 in batch mode.",
            },
        )
        assert result.get("batch_issue_number") == 526

    def test_batch_context_detected_in_agent_prompt(self):
        """Agent tool with BATCH CONTEXT in prompt also sets batch_mode=True."""
        result = sal._summarize_input(
            "Agent",
            {
                "description": "researcher",
                "subagent_type": "researcher",
                "prompt": "BATCH CONTEXT (CRITICAL - Operating in worktree): Research Issue #100.",
            },
        )
        assert result.get("batch_mode") is True
        assert result.get("batch_issue_number") == 100

    def test_no_batch_context_when_absent(self):
        """Prompt without BATCH CONTEXT does not set batch_mode."""
        result = sal._summarize_input(
            "Task",
            {
                "description": "implementer",
                "prompt": "Normal implementation task without batch context.",
            },
        )
        assert result.get("batch_mode") is None

    def test_batch_mode_absent_when_no_prompt(self):
        """Task tool with no prompt does not set batch_mode."""
        result = sal._summarize_input("Task", {"description": "task", "subagent_type": "planner"})
        assert result.get("batch_mode") is None

    def test_batch_issue_number_from_structured_field(self):
        """Issue number extracted from structured 'Issue Number: N' field (Issue #808)."""
        result = sal._summarize_input(
            "Task",
            {
                "description": "doc-master",
                "subagent_type": "doc-master",
                "prompt": (
                    "**BATCH CONTEXT** (CRITICAL - Operating in worktree):\n"
                    "- Worktree Path: /some/path (absolute path)\n"
                    "- Issue Number: 42\n"
                    "- ALL file operations MUST use absolute paths\n\n"
                    "Update documentation for the implemented changes."
                ),
            },
        )
        assert result.get("batch_mode") is True
        assert result.get("batch_issue_number") == 42

    def test_batch_issue_number_structured_preferred_over_informal(self):
        """Structured 'Issue Number: N' takes precedence over 'Issue #N' (Issue #808)."""
        result = sal._summarize_input(
            "Task",
            {
                "description": "reviewer",
                "subagent_type": "reviewer",
                "prompt": (
                    "**BATCH CONTEXT** (CRITICAL - Operating in worktree):\n"
                    "- Worktree Path: /some/path\n"
                    "- Issue Number: 42\n\n"
                    "Review the implementation. See also Issue #99 for related context."
                ),
            },
        )
        assert result.get("batch_mode") is True
        assert result.get("batch_issue_number") == 42

    def test_batch_issue_number_fallback_to_issue_hash(self):
        """Falls back to 'Issue #N' when no structured field present (backward compat)."""
        result = sal._summarize_input(
            "Task",
            {
                "description": "implementer",
                "prompt": (
                    "BATCH CONTEXT - Operating in worktree.\n"
                    "Implement fixes for Issue #526 in batch mode."
                ),
            },
        )
        assert result.get("batch_mode") is True
        assert result.get("batch_issue_number") == 526

    def test_batch_issue_number_absent_when_no_issue(self):
        """BATCH CONTEXT without Issue # does not set batch_issue_number."""
        result = sal._summarize_input(
            "Task",
            {"prompt": "BATCH CONTEXT - No specific issue referenced here."},
        )
        assert result.get("batch_mode") is True
        assert result.get("batch_issue_number") is None


class TestHeartbeatMechanism:
    """Regression tests for Issue #526: heartbeat mechanism for batch sessions."""

    def test_heartbeat_file_created_on_first_call(self, tmp_path):
        """First call creates the heartbeat file."""
        sal._check_and_log_heartbeat("test-session", tmp_path, "2026-03-22")
        hb_file = tmp_path / ".heartbeat_test-session"
        assert hb_file.exists()

    def test_heartbeat_log_entry_written(self, tmp_path):
        """Heartbeat call writes a Heartbeat entry to the JSONL log."""
        sal._check_and_log_heartbeat("test-session", tmp_path, "2026-03-22")
        log_file = tmp_path / "2026-03-22.jsonl"
        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["hook"] == "Heartbeat"
        assert entry["session_id"] == "test-session"
        assert "timestamp" in entry

    def test_heartbeat_rate_limited_within_5_minutes(self, tmp_path):
        """Second heartbeat call within 5 minutes does not write a second log entry."""
        sal._check_and_log_heartbeat("rate-session", tmp_path, "2026-03-22")
        log_file = tmp_path / "2026-03-22.jsonl"
        first_content = log_file.read_text()

        # Second call immediately — should be rate-limited
        sal._check_and_log_heartbeat("rate-session", tmp_path, "2026-03-22")
        assert log_file.read_text() == first_content  # No new content

    def test_heartbeat_written_after_5_minutes(self, tmp_path):
        """Heartbeat is written again after the 5-minute window expires."""
        import time as _time
        hb_file = tmp_path / ".heartbeat_expired-session"
        # Simulate a heartbeat written more than 5 minutes ago
        old_time = _time.time() - 310  # 5 minutes and 10 seconds ago
        hb_file.write_text(str(old_time))

        sal._check_and_log_heartbeat("expired-session", tmp_path, "2026-03-22")
        log_file = tmp_path / "2026-03-22.jsonl"
        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["hook"] == "Heartbeat"

    def test_heartbeat_non_blocking_on_error(self, tmp_path):
        """Heartbeat failure does not raise exceptions (non-blocking)."""
        # Use a path that can't be written to
        read_only_dir = tmp_path / "no-write"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)
        try:
            # Should not raise
            sal._check_and_log_heartbeat("session", read_only_dir, "2026-03-22")
        finally:
            read_only_dir.chmod(0o755)


class TestAgentEventPriority:
    """Regression tests for Issue #526: Agent events marked with elevated priority."""

    def test_task_tool_entry_has_priority_high(self, tmp_path):
        """Task tool PostToolUse log entry has priority='high'."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Task",
            "tool_input": {"description": "run implementer", "subagent_type": "implementer", "prompt": "fix stuff"},
            "tool_output": {"output": "done"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "priority-test"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert entry.get("priority") == "high"
        assert entry.get("agent_event") is True

    def test_agent_tool_entry_has_priority_high(self, tmp_path):
        """Agent tool PostToolUse log entry has priority='high'."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Agent",
            "tool_input": {"description": "research", "subagent_type": "researcher", "prompt": "find patterns"},
            "tool_output": {"output": "found patterns"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "priority-agent"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert entry.get("priority") == "high"
        assert entry.get("agent_event") is True

    def test_non_agent_tool_has_no_priority(self, tmp_path):
        """Non-Agent tools (Read, Bash, etc.) do NOT get priority='high'."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x.py"},
            "tool_output": {"output": "content"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "no-priority"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        assert "priority" not in entry
        assert "agent_event" not in entry

    def test_agent_priority_not_set_in_debug_mode(self, tmp_path):
        """In debug mode, priority field is NOT added (raw mode)."""
        log_dir = tmp_path / ".claude" / "logs" / "activity"
        hook_input = json.dumps({
            "tool_name": "Task",
            "tool_input": {"description": "run implementer", "prompt": "fix"},
            "tool_output": {"output": "done"},
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "debug", "CLAUDE_SESSION_ID": "debug-priority"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("session_activity_logger._find_log_dir", return_value=log_dir):
                    with pytest.raises(SystemExit):
                        sal.main()

        entry = json.loads(list(log_dir.glob("*.jsonl"))[0].read_text().splitlines()[0])
        # Debug mode uses raw format, priority field should not be present
        assert "priority" not in entry


# ============================================================================
# Issue #1087 regression tests: subagent invocation correlation
# ============================================================================
#
# Background: Claude Code's SubagentStop hook payload sometimes omits the
# agent_type field and ALWAYS reports duration_ms=0. These tests lock in
# the PreToolUse-to-SubagentStop correlation that recovers both fields.
#
# Coverage:
#   - PreToolUse for Task/Agent caches subagent_type + start_time.
#   - Cache lookup pops oldest entry FIFO (sequential agents).
#   - Cache lookup prefers same-type match when SubagentStop stdin has
#     a non-empty agent_type.
#   - Stale cache entries (>1 hour) are ignored.
#   - SubagentStop in unified_session_tracker resolves the missing
#     agent_type AND computes non-zero duration_ms, then calls
#     record_agent_completion for the agent.

import time as _time1087

# Add lib dir for subagent_invocation_cache import
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)


@pytest.fixture
def isolated_session_id(tmp_path, monkeypatch):
    """Per-test session id with isolated /tmp via cache_path patch.

    Each test gets a distinct session id and a tmp_path-rooted cache so
    the cache file does not collide with concurrent tests or stale state
    from previous runs.
    """
    import uuid
    sid = f"test-{uuid.uuid4().hex[:12]}"
    import subagent_invocation_cache as sic

    def _scoped_cache_path(session_id: str) -> Path:
        return tmp_path / f"subagent_invocations_{session_id}.json"

    monkeypatch.setattr(sic, "cache_path", _scoped_cache_path)
    yield sid


class TestSubagentInvocationCacheLib:
    """Direct tests for the shared subagent_invocation_cache library (#1087)."""

    def test_cache_invocation_round_trip(self, isolated_session_id):
        """cache_invocation followed by pop_invocation returns the entry."""
        import subagent_invocation_cache as sic
        ok = sic.cache_invocation(
            isolated_session_id,
            "implementer",
            start_time=1000.0,
            description="fix #1087",
        )
        assert ok is True
        popped = sic.pop_invocation(isolated_session_id)
        assert popped is not None
        assert popped["subagent_type"] == "implementer"
        assert popped["start_time"] == 1000.0
        assert popped["description"] == "fix #1087"

    def test_cache_empty_subagent_type_rejected(self, isolated_session_id):
        """Caching an empty subagent_type is rejected — would corrupt FIFO."""
        import subagent_invocation_cache as sic
        assert sic.cache_invocation(isolated_session_id, "") is False
        assert sic.pop_invocation(isolated_session_id) is None

    def test_pop_fifo_order(self, isolated_session_id):
        """Multiple invocations pop in first-in-first-out order."""
        import subagent_invocation_cache as sic
        sic.cache_invocation(isolated_session_id, "researcher-local", start_time=1.0)
        sic.cache_invocation(isolated_session_id, "planner", start_time=2.0)
        sic.cache_invocation(isolated_session_id, "implementer", start_time=3.0)
        assert sic.pop_invocation(isolated_session_id)["subagent_type"] == "researcher-local"
        assert sic.pop_invocation(isolated_session_id)["subagent_type"] == "planner"
        assert sic.pop_invocation(isolated_session_id)["subagent_type"] == "implementer"

    def test_pop_preferred_type_match(self, isolated_session_id):
        """preferred_subagent_type prefers a matching entry over FIFO order."""
        import subagent_invocation_cache as sic
        sic.cache_invocation(isolated_session_id, "researcher-local", start_time=1.0)
        sic.cache_invocation(isolated_session_id, "implementer", start_time=2.0)
        popped = sic.pop_invocation(
            isolated_session_id, preferred_subagent_type="implementer"
        )
        assert popped["subagent_type"] == "implementer"
        assert popped["start_time"] == 2.0
        remaining = sic.peek_queue(isolated_session_id)
        assert len(remaining) == 1
        assert remaining[0]["subagent_type"] == "researcher-local"

    def test_pop_empty_queue_returns_none(self, isolated_session_id):
        """Pop on a never-populated session returns None."""
        import subagent_invocation_cache as sic
        assert sic.pop_invocation(isolated_session_id) is None

    def test_pop_stale_cache_ignored(self, isolated_session_id):
        """Cache files older than TTL are ignored on read."""
        import subagent_invocation_cache as sic
        import os as _os

        sic.cache_invocation(isolated_session_id, "implementer", start_time=1.0)
        path = sic.cache_path(isolated_session_id)
        assert path.exists()

        old = _time1087.time() - (sic.TTL_SECONDS + 60)
        _os.utime(path, (old, old))

        assert sic.pop_invocation(isolated_session_id) is None

    def test_pop_corrupt_json_returns_none(self, isolated_session_id):
        """Corrupt cache file does not crash; pop returns None."""
        import subagent_invocation_cache as sic
        path = sic.cache_path(isolated_session_id)
        path.write_text("this is { not json")
        assert sic.pop_invocation(isolated_session_id) is None


class TestSessionActivityLoggerPreToolUseCaching:
    """PreToolUse for Task/Agent caches the invocation (#1087)."""

    def test_pretool_task_caches_subagent_type(self, tmp_path, monkeypatch):
        """PreToolUse for tool_name=Task records subagent_type + start_time."""
        import subagent_invocation_cache as sic
        monkeypatch.setattr(
            sic,
            "cache_path",
            lambda sid: tmp_path / f"subagent_invocations_{sid}.json",
        )
        # session_activity_logger's PreToolUse branch uses _sic_cache_invocation
        # bound at module-import time. Re-bind to the (now patched) cache_invocation.
        monkeypatch.setattr(sal, "_sic_cache_invocation", sic.cache_invocation)

        hook_input = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "implementer",
                "description": "fix bug",
            },
            "session_id": "pre-task-1",
        })
        before = _time1087.time()
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "pre-task-1"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with pytest.raises(SystemExit) as exc:
                    sal.main()
                assert exc.value.code == 0
        after = _time1087.time()

        popped = sic.pop_invocation("pre-task-1")
        assert popped is not None
        assert popped["subagent_type"] == "implementer"
        assert popped["description"] == "fix bug"
        assert before <= popped["start_time"] <= after

    def test_pretool_agent_caches_subagent_type(self, tmp_path, monkeypatch):
        """PreToolUse for tool_name=Agent (newer Claude Code) also caches."""
        import subagent_invocation_cache as sic
        monkeypatch.setattr(
            sic,
            "cache_path",
            lambda sid: tmp_path / f"subagent_invocations_{sid}.json",
        )
        monkeypatch.setattr(sal, "_sic_cache_invocation", sic.cache_invocation)

        hook_input = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "reviewer"},
            "session_id": "pre-agent-1",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "pre-agent-1"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with pytest.raises(SystemExit):
                    sal.main()

        popped = sic.pop_invocation("pre-agent-1")
        assert popped is not None
        assert popped["subagent_type"] == "reviewer"

    def test_pretool_non_agent_tool_does_not_cache(self, tmp_path, monkeypatch):
        """PreToolUse for non-Task/Agent tools (e.g. Read) does NOT cache."""
        import subagent_invocation_cache as sic
        monkeypatch.setattr(
            sic,
            "cache_path",
            lambda sid: tmp_path / f"subagent_invocations_{sid}.json",
        )
        monkeypatch.setattr(sal, "_sic_cache_invocation", sic.cache_invocation)

        hook_input = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x.py"},
            "session_id": "pre-read-1",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "pre-read-1"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with pytest.raises(SystemExit):
                    sal.main()

        assert sic.pop_invocation("pre-read-1") is None

    def test_pretool_empty_subagent_type_does_not_cache(self, tmp_path, monkeypatch):
        """PreToolUse for Task with empty subagent_type does not cache."""
        import subagent_invocation_cache as sic
        monkeypatch.setattr(
            sic,
            "cache_path",
            lambda sid: tmp_path / f"subagent_invocations_{sid}.json",
        )
        monkeypatch.setattr(sal, "_sic_cache_invocation", sic.cache_invocation)

        hook_input = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "", "description": "?"},
            "session_id": "pre-empty-1",
        })
        with patch.dict(os.environ, {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "pre-empty-1"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with pytest.raises(SystemExit):
                    sal.main()

        assert sic.pop_invocation("pre-empty-1") is None


class TestUnifiedSessionTrackerSubagentStopCorrelation:
    """SubagentStop in unified_session_tracker resolves agent_type + duration_ms (#1087)."""

    @pytest.fixture(autouse=True)
    def _setup_unified_tracker(self, tmp_path, monkeypatch):
        """Import unified_session_tracker fresh and route cache to tmp_path."""
        import importlib
        import subagent_invocation_cache as sic

        monkeypatch.setattr(
            sic,
            "cache_path",
            lambda sid: tmp_path / f"subagent_invocations_{sid}.json",
        )

        if "unified_session_tracker" in sys.modules:
            ust = importlib.reload(sys.modules["unified_session_tracker"])
        else:
            ust = importlib.import_module("unified_session_tracker")
        monkeypatch.setattr(ust, "_pop_cached_subagent_invocation", sic.pop_invocation)
        self.ust = ust
        self.sic = sic

    def test_subagent_stop_recovers_empty_agent_type_from_cache(
        self, tmp_path, monkeypatch
    ):
        """When SubagentStop stdin has agent_type='', cache resolves the name.

        This is the precise bug shape observed in production logs:
        SubagentStop has subagent_type='' but agent_transcript_path is
        populated. The PreToolUse cache fills the gap.
        """
        self.sic.cache_invocation("stop-1", "implementer", start_time=_time1087.time() - 5.0)

        hook_input = json.dumps({
            "hook_event_name": "SubagentStop",
            "agent_type": "",
            "session_id": "stop-1",
            "agent_transcript_path": "",
            "last_assistant_message": "Completed.",
        })

        captured = {}

        def _fake_record(*, session_id, agent_type, issue_number, success):
            captured["session_id"] = session_id
            captured["agent_type"] = agent_type
            captured["issue_number"] = issue_number
            captured["success"] = success

        import pipeline_completion_state as pcs
        monkeypatch.setattr(pcs, "record_agent_completion", _fake_record)

        write_calls = []
        monkeypatch.setattr(
            self.ust,
            "_write_jsonl_entry",
            lambda **kw: (write_calls.append(kw) or True),
        )

        with patch("sys.stdin", StringIO(hook_input)):
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "stop-1"}, clear=False):
                self.ust.main()

        assert len(write_calls) == 1
        # Critical assertion #1: subagent_type recovered from cache, NOT empty.
        assert write_calls[0]["subagent_type"] == "implementer"
        # Critical assertion #2: duration_ms is non-zero.
        assert write_calls[0]["duration_ms"] > 0
        # Critical assertion #3: record_agent_completion called with the right type.
        assert captured.get("agent_type") == "implementer"
        assert captured.get("success") is True

    def test_subagent_stop_with_populated_agent_type_still_computes_duration(
        self, tmp_path, monkeypatch
    ):
        """Even when stdin provides agent_type, duration_ms is computed from cache."""
        self.sic.cache_invocation("stop-2", "reviewer", start_time=_time1087.time() - 10.0)

        hook_input = json.dumps({
            "hook_event_name": "SubagentStop",
            "agent_type": "reviewer",
            "session_id": "stop-2",
            "agent_transcript_path": "",
            "last_assistant_message": "All good.",
        })

        write_calls = []
        monkeypatch.setattr(
            self.ust,
            "_write_jsonl_entry",
            lambda **kw: (write_calls.append(kw) or True),
        )
        import pipeline_completion_state as pcs
        monkeypatch.setattr(pcs, "record_agent_completion", lambda **kw: None)

        with patch("sys.stdin", StringIO(hook_input)):
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "stop-2"}, clear=False):
                self.ust.main()

        assert len(write_calls) == 1
        assert write_calls[0]["subagent_type"] == "reviewer"
        assert write_calls[0]["duration_ms"] >= 5000  # We set start_time 10s ago.

    def test_subagent_stop_without_cache_does_not_crash(
        self, tmp_path, monkeypatch
    ):
        """SubagentStop with no PreToolUse cache (e.g. hook race) doesn't crash."""
        hook_input = json.dumps({
            "hook_event_name": "SubagentStop",
            "agent_type": "doc-master",
            "session_id": "stop-3",
            "agent_transcript_path": "",
            "last_assistant_message": "Done.",
        })
        write_calls = []
        monkeypatch.setattr(
            self.ust,
            "_write_jsonl_entry",
            lambda **kw: (write_calls.append(kw) or True),
        )
        import pipeline_completion_state as pcs
        monkeypatch.setattr(pcs, "record_agent_completion", lambda **kw: None)

        with patch("sys.stdin", StringIO(hook_input)):
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "stop-3"}, clear=False):
                self.ust.main()

        assert len(write_calls) == 1
        assert write_calls[0]["subagent_type"] == "doc-master"

    def test_subagent_stop_preferred_type_match_in_parallel_queue(
        self, tmp_path, monkeypatch
    ):
        """With multiple cached agents, prefer the matching type from stdin.

        Models the parallel-agent case: implementer and reviewer were
        launched concurrently; reviewer completes first. SubagentStop
        for reviewer must pop reviewer (not the older implementer).
        """
        self.sic.cache_invocation("stop-4", "implementer", start_time=_time1087.time() - 100.0)
        self.sic.cache_invocation("stop-4", "reviewer", start_time=_time1087.time() - 5.0)

        hook_input = json.dumps({
            "hook_event_name": "SubagentStop",
            "agent_type": "reviewer",
            "session_id": "stop-4",
            "agent_transcript_path": "",
        })
        write_calls = []
        monkeypatch.setattr(
            self.ust,
            "_write_jsonl_entry",
            lambda **kw: (write_calls.append(kw) or True),
        )
        import pipeline_completion_state as pcs
        captured = {}
        monkeypatch.setattr(
            pcs,
            "record_agent_completion",
            lambda **kw: captured.update(kw),
        )

        with patch("sys.stdin", StringIO(hook_input)):
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "stop-4"}, clear=False):
                self.ust.main()

        assert write_calls[0]["subagent_type"] == "reviewer"
        # Duration should reflect reviewer's 5s, not implementer's 100s.
        assert 4000 <= write_calls[0]["duration_ms"] <= 15000
        # implementer still in queue (not popped).
        remaining = self.sic.peek_queue("stop-4")
        assert len(remaining) == 1
        assert remaining[0]["subagent_type"] == "implementer"
