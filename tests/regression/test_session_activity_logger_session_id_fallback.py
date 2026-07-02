#!/usr/bin/env python3
"""
Regression test for session_activity_logger.py session_id fallback (Issue #1344).

Tests that the hook correctly falls back to hook payload session_id when
CLAUDE_SESSION_ID env var is empty or missing, instead of always defaulting
to "unknown".
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest


def test_stop_hook_session_id_fallback_with_empty_env():
    """Test Stop hook uses payload session_id when env var is empty string."""
    # Test both debug and normal mode branches
    for log_level in ["debug", "true"]:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory structure in tmpdir
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir(parents=True)
            
            hook_input = {
                "hook_event_name": "Stop",
                "last_assistant_message": "Test message",
                "session_id": "test-session-123",
                "stop_hook_active": True
            }
            
            env = os.environ.copy()
            env["CLAUDE_SESSION_ID"] = ""  # Empty string should fall through
            env["ACTIVITY_LOGGING"] = log_level
            
            hook_path = Path(__file__).parents[2] / "plugins/autonomous-dev/hooks/session_activity_logger.py"
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(hook_input),
                text=True,
                capture_output=True,
                env=env,
                cwd=tmpdir  # Run from tmpdir so it finds .claude
            )
            
            assert result.returncode == 0
            
            # Check the logged entry
            log_files = list((Path(tmpdir) / ".claude" / "logs" / "activity").glob("*.jsonl"))
            assert len(log_files) == 1
            
            with open(log_files[0]) as f:
                entries = [json.loads(line) for line in f]
            
            assert len(entries) == 1
            assert entries[0]["session_id"] == "test-session-123"
            assert entries[0]["hook"] == "Stop"


def test_stop_hook_session_id_fallback_with_missing_env():
    """Test Stop hook uses payload session_id when env var is not set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .claude directory structure in tmpdir
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir(parents=True)
        
        hook_input = {
            "hook_event_name": "Stop",
            "last_assistant_message": "Test message",
            "session_id": "test-session-456",
            "stop_hook_active": False
        }
        
        env = os.environ.copy()
        # Remove CLAUDE_SESSION_ID if it exists
        env.pop("CLAUDE_SESSION_ID", None)
        env["ACTIVITY_LOGGING"] = "true"
        
        hook_path = Path(__file__).parents[2] / "plugins/autonomous-dev/hooks/session_activity_logger.py"
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            text=True,
            capture_output=True,
            env=env,
            cwd=tmpdir  # Run from tmpdir so it finds .claude
        )
        
        assert result.returncode == 0
        
        # Check the logged entry
        log_files = list((Path(tmpdir) / ".claude" / "logs" / "activity").glob("*.jsonl"))
        assert len(log_files) == 1
        
        with open(log_files[0]) as f:
            entries = [json.loads(line) for line in f]
        
        assert len(entries) == 1
        assert entries[0]["session_id"] == "test-session-456"


def test_userpromptsubmit_hook_session_id_fallback():
    """Test UserPromptSubmit hook uses payload session_id when env var is empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .claude directory structure in tmpdir
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir(parents=True)
        
        hook_input = {
            "hook_event_name": "UserPromptSubmit",
            "user_prompt": "Test prompt from user",
            "session_id": "test-session-789"
        }
        
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = ""  # Empty string should fall through
        env["ACTIVITY_LOGGING"] = "true"
        
        hook_path = Path(__file__).parents[2] / "plugins/autonomous-dev/hooks/session_activity_logger.py"
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            text=True,
            capture_output=True,
            env=env,
            cwd=tmpdir  # Run from tmpdir so it finds .claude
        )
        
        assert result.returncode == 0
        
        # Check the logged entry
        log_files = list((Path(tmpdir) / ".claude" / "logs" / "activity").glob("*.jsonl"))
        assert len(log_files) == 1
        
        with open(log_files[0]) as f:
            entries = [json.loads(line) for line in f]
        
        assert len(entries) == 1
        assert entries[0]["session_id"] == "test-session-789"
        assert entries[0]["hook"] == "UserPromptSubmit"


def test_posttooluse_hook_session_id_fallback():
    """Test PostToolUse hook uses payload session_id when env var is empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .claude directory structure in tmpdir
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir(parents=True)
        
        hook_input = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/test/file.py"},
            "tool_output": {"success": True, "content": "test content"},
            "session_id": "test-session-abc"
        }
        
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = ""  # Empty string should fall through
        env["ACTIVITY_LOGGING"] = "true"
        
        hook_path = Path(__file__).parents[2] / "plugins/autonomous-dev/hooks/session_activity_logger.py"
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            text=True,
            capture_output=True,
            env=env,
            cwd=tmpdir  # Run from tmpdir so it finds .claude
        )
        
        assert result.returncode == 0
        
        # Check the logged entry
        log_files = list((Path(tmpdir) / ".claude" / "logs" / "activity").glob("*.jsonl"))
        assert len(log_files) == 1
        
        with open(log_files[0]) as f:
            entries = [json.loads(line) for line in f]
        
        # Filter out Heartbeat entries (they're timing-dependent)
        main_entries = [e for e in entries if e.get("hook") != "Heartbeat"]
        
        assert len(main_entries) == 1
        assert main_entries[0]["session_id"] == "test-session-abc"
        assert main_entries[0]["hook"] == "PostToolUse"
        assert main_entries[0]["tool"] == "Read"


def test_warning_logged_when_session_id_unknown():
    """Test that a warning is logged to stderr when session_id resolves to 'unknown'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .claude directory structure in tmpdir
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir(parents=True)
        
        # Test with no session_id in payload or env
        hook_input = {
            "hook_event_name": "Stop",
            "last_assistant_message": "Test message"
            # No session_id field
        }
        
        env = os.environ.copy()
        env.pop("CLAUDE_SESSION_ID", None)  # No env var
        env["ACTIVITY_LOGGING"] = "true"
        
        hook_path = Path(__file__).parents[2] / "plugins/autonomous-dev/hooks/session_activity_logger.py"
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            text=True,
            capture_output=True,
            env=env,
            cwd=tmpdir  # Run from tmpdir so it finds .claude
        )
        
        assert result.returncode == 0
        assert "[session_activity_logger] WARNING: session_id resolved to 'unknown' for hook=Stop" in result.stderr
        
        # Check the logged entry has 'unknown' session_id
        log_files = list((Path(tmpdir) / ".claude" / "logs" / "activity").glob("*.jsonl"))
        assert len(log_files) == 1
        
        with open(log_files[0]) as f:
            entries = [json.loads(line) for line in f]
        
        assert len(entries) == 1
        assert entries[0]["session_id"] == "unknown"


def test_env_var_takes_precedence_when_not_empty():
    """Test that non-empty env var takes precedence over hook payload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .claude directory structure in tmpdir
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir(parents=True)
        
        hook_input = {
            "hook_event_name": "Stop",
            "last_assistant_message": "Test message",
            "session_id": "payload-session",
        }
        
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = "env-session"  # Non-empty env var
        env["ACTIVITY_LOGGING"] = "true"
        
        hook_path = Path(__file__).parents[2] / "plugins/autonomous-dev/hooks/session_activity_logger.py"
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            text=True,
            capture_output=True,
            env=env,
            cwd=tmpdir  # Run from tmpdir so it finds .claude
        )
        
        assert result.returncode == 0
        
        # Check env var value was used
        log_files = list((Path(tmpdir) / ".claude" / "logs" / "activity").glob("*.jsonl"))
        assert len(log_files) == 1
        
        with open(log_files[0]) as f:
            entries = [json.loads(line) for line in f]
        
        assert len(entries) == 1
        assert entries[0]["session_id"] == "env-session"  # env var wins