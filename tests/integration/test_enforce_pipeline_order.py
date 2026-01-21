#!/usr/bin/env python3
"""
Integration tests for enforce_pipeline_order.py (Issue #246 - Layer 2 Defense).

Tests pipeline order enforcement to prevent Claude from skipping steps in /implement.
The enforce_pipeline_order hook ensures the correct agent execution order:

1. researcher-local (codebase analysis)
2. researcher-web / general-purpose (web best practices)
3. planner (implementation plan)
4. test-master (TDD tests)
5. implementer (production code) ← BLOCKED without prerequisites

Test Coverage:
- Prerequisite tracking (researcher-local, researcher-web, planner, test-master)
- Implementer blocking when prerequisites missing
- Implementer allowing when prerequisites met
- Session state management (2-hour timeout)
- State file locking and atomic writes
- Environment variable opt-out (ENFORCE_PIPELINE_ORDER=false)

Author: test-master agent
Date: 2026-01-21
Issue: #246
"""

import json
import os
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# Import hook module - these are optional for unit tests
# Integration tests use subprocess and don't need the imports
_imports_available = False
reset_state = None
record_agent_invocation = None
load_state = None
check_prerequisites_met = None
output_decision = None

try:
    from enforce_pipeline_order import (
        PREREQUISITE_AGENTS,
        PROTECTED_AGENT,
        WEB_RESEARCH_AGENTS,
        check_prerequisites_met as _check_prerequisites_met,
        get_state_file_path,
        load_state as _load_state,
        output_decision as _output_decision,
        record_agent_invocation as _record_agent_invocation,
        reset_state as _reset_state,
        save_state,
    )
    _imports_available = True
    reset_state = _reset_state
    record_agent_invocation = _record_agent_invocation
    load_state = _load_state
    check_prerequisites_met = _check_prerequisites_met
    output_decision = _output_decision
except ImportError:
    pass


@pytest.fixture
def temp_state_file(tmp_path):
    """Provide a temporary state file for testing."""
    state_file = tmp_path / "pipeline_state.json"
    with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(state_file)}):
        yield state_file


@pytest.fixture
def clean_state():
    """Reset state before each test."""
    if _imports_available and reset_state is not None:
        return reset_state()
    return {}


@pytest.mark.skipif(not _imports_available, reason="Hook module not importable")
class TestPrerequisiteTracking:
    """Test prerequisite agent tracking functionality."""

    def test_researcher_local_marks_local_research(self, temp_state_file, clean_state):
        """Test that invoking researcher-local marks local_research as met."""
        state = clean_state
        assert record_agent_invocation is not None
        state = record_agent_invocation(state, "researcher-local")

        assert state["prerequisites_met"]["local_research"] is True
        assert "researcher-local" in state["agents_invoked"]

    def test_researcher_web_marks_web_research(self, temp_state_file, clean_state):
        """Test that invoking researcher-web marks web_research as met."""
        state = clean_state
        state = record_agent_invocation(state, "researcher-web")

        assert state["prerequisites_met"]["web_research"] is True
        assert "researcher-web" in state["agents_invoked"]

    def test_general_purpose_marks_web_research(self, temp_state_file, clean_state):
        """Test that invoking general-purpose (web research agent) marks web_research as met."""
        state = clean_state
        state = record_agent_invocation(state, "general-purpose")

        assert state["prerequisites_met"]["web_research"] is True
        assert "general-purpose" in state["agents_invoked"]

    def test_planner_marks_planner(self, temp_state_file, clean_state):
        """Test that invoking planner marks planner as met."""
        state = clean_state
        state = record_agent_invocation(state, "planner")

        assert state["prerequisites_met"]["planner"] is True
        assert "planner" in state["agents_invoked"]

    def test_test_master_marks_test_master(self, temp_state_file, clean_state):
        """Test that invoking test-master marks test_master as met."""
        state = clean_state
        state = record_agent_invocation(state, "test-master")

        assert state["prerequisites_met"]["test_master"] is True
        assert "test-master" in state["agents_invoked"]

    def test_multiple_prerequisites_tracked_correctly(self, temp_state_file, clean_state):
        """Test that multiple prerequisite agents are tracked correctly."""
        state = clean_state
        state = record_agent_invocation(state, "researcher-local")
        state = record_agent_invocation(state, "researcher-web")
        state = record_agent_invocation(state, "planner")

        assert state["prerequisites_met"]["local_research"] is True
        assert state["prerequisites_met"]["web_research"] is True
        assert state["prerequisites_met"]["planner"] is True
        assert state["prerequisites_met"]["test_master"] is False  # Not invoked yet

        assert len(state["agents_invoked"]) == 3

    def test_duplicate_agent_invocation_not_duplicated_in_list(self, temp_state_file, clean_state):
        """Test that duplicate agent invocations are not duplicated in agents_invoked list."""
        state = clean_state
        state = record_agent_invocation(state, "researcher-local")
        state = record_agent_invocation(state, "researcher-local")  # Duplicate

        # Should only appear once
        assert state["agents_invoked"].count("researcher-local") == 1


@pytest.mark.skipif(not _imports_available, reason="Hook module not importable")
class TestPrerequisiteChecking:
    """Test prerequisite checking logic."""

    def test_no_prerequisites_met_returns_all_missing(self, temp_state_file, clean_state):
        """Test that with no prerequisites met, all are reported as missing."""
        state = clean_state
        all_met, missing = check_prerequisites_met(state)

        assert all_met is False
        assert len(missing) == 4
        assert any("researcher-local" in m for m in missing)
        assert any("researcher-web" in m for m in missing)
        assert any("planner" in m for m in missing)
        assert any("test-master" in m for m in missing)

    def test_partial_prerequisites_met_returns_some_missing(self, temp_state_file, clean_state):
        """Test that with partial prerequisites met, only missing ones are reported."""
        state = clean_state
        state = record_agent_invocation(state, "researcher-local")
        state = record_agent_invocation(state, "planner")

        all_met, missing = check_prerequisites_met(state)

        assert all_met is False
        assert len(missing) == 2
        assert any("researcher-web" in m for m in missing)
        assert any("test-master" in m for m in missing)

    def test_all_prerequisites_met_returns_no_missing(self, temp_state_file, clean_state):
        """Test that with all prerequisites met, none are reported as missing."""
        state = clean_state
        state = record_agent_invocation(state, "researcher-local")
        state = record_agent_invocation(state, "researcher-web")
        state = record_agent_invocation(state, "planner")
        state = record_agent_invocation(state, "test-master")

        all_met, missing = check_prerequisites_met(state)

        assert all_met is True
        assert len(missing) == 0


class TestImplementerBlocking:
    """Test implementer agent blocking logic."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    def test_implementer_blocked_when_no_prerequisites_met(self, hook_path, temp_state_file):
        """Test that implementer is blocked when no prerequisites have been met."""
        # Reset state
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state
reset_state()
"""], check=True)

            # Try to invoke implementer
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "implementer",
                    "prompt": "Implement feature X"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should DENY implementer
            assert result.returncode == 0  # Hook exits 0, decision in output
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert "PIPELINE ORDER VIOLATION" in output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "researcher-local" in output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "researcher-web" in output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "planner" in output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "test-master" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_implementer_blocked_when_partial_prerequisites_met(self, hook_path, temp_state_file):
        """Test that implementer is blocked when only some prerequisites have been met."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            # Reset and record partial prerequisites
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state, record_agent_invocation
state = reset_state()
state = record_agent_invocation(state, 'researcher-local')
state = record_agent_invocation(state, 'planner')
"""], check=True)

            # Try to invoke implementer
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "implementer",
                    "prompt": "Implement feature X"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should DENY implementer
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert "researcher-web" in output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "test-master" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_implementer_allowed_when_all_prerequisites_met(self, hook_path, temp_state_file):
        """Test that implementer is allowed when all prerequisites have been met."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            # Reset and record all prerequisites
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state, record_agent_invocation
state = reset_state()
state = record_agent_invocation(state, 'researcher-local')
state = record_agent_invocation(state, 'researcher-web')
state = record_agent_invocation(state, 'planner')
state = record_agent_invocation(state, 'test-master')
"""], check=True)

            # Try to invoke implementer
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "implementer",
                    "prompt": "Implement feature X"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW implementer
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert "prerequisites met" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()


class TestPrerequisiteAgentsAllowed:
    """Test that prerequisite agents are always allowed."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    @pytest.mark.parametrize("agent_type", [
        "researcher-local",
        "researcher-web",
        "planner",
        "test-master",
    ])
    def test_prerequisite_agent_always_allowed(self, hook_path, temp_state_file, agent_type):
        """Test that prerequisite agents are always allowed regardless of state."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            # Reset state
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state
reset_state()
"""], check=True)

            # Try to invoke prerequisite agent
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": agent_type,
                    "prompt": f"Run {agent_type}"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW prerequisite agent
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert agent_type in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestPostImplementerAgents:
    """Test that post-implementer agents (reviewer, security-auditor, doc-master) are allowed."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    @pytest.mark.parametrize("agent_type", [
        "reviewer",
        "security-auditor",
        "doc-master",
    ])
    def test_post_implementer_agent_allowed(self, hook_path, temp_state_file, agent_type):
        """Test that post-implementer agents are allowed without prerequisites."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            # Reset state (no prerequisites)
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state
reset_state()
"""], check=True)

            # Try to invoke post-implementer agent
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": agent_type,
                    "prompt": f"Run {agent_type}"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW post-implementer agent
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert agent_type in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestNonTaskTools:
    """Test that non-Task tools are not subject to pipeline order enforcement."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    @pytest.mark.parametrize("tool_name", [
        "Edit",
        "Write",
        "Read",
        "Bash",
        "Grep",
    ])
    def test_non_task_tool_allowed(self, hook_path, temp_state_file, tool_name):
        """Test that non-Task tools are always allowed."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            tool_input = {
                "tool_name": tool_name,
                "tool_input": {
                    "file_path": "/tmp/test.py",
                    "content": "print('hello')"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW non-Task tool
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert "not subject to pipeline order enforcement" in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestEnforcementOptOut:
    """Test environment variable opt-out functionality."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    def test_enforcement_disabled_with_env_var(self, hook_path, temp_state_file):
        """Test that ENFORCE_PIPELINE_ORDER=false disables enforcement."""
        with patch.dict(os.environ, {
            "PIPELINE_STATE_FILE": str(temp_state_file),
            "ENFORCE_PIPELINE_ORDER": "false"
        }):
            # Reset state (no prerequisites)
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state
reset_state()
"""], check=True)

            # Try to invoke implementer without prerequisites
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "implementer",
                    "prompt": "Implement feature X"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW implementer (enforcement disabled)
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert "enforcement disabled" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()


@pytest.mark.skipif(not _imports_available, reason="Hook module not importable")
class TestStateFilePersistence:
    """Test state file persistence and atomic writes."""

    def test_state_persists_across_invocations(self, temp_state_file, clean_state):
        """Test that state persists across multiple invocations."""
        # Record first agent
        state = clean_state
        state = record_agent_invocation(state, "researcher-local")

        # Load state from file
        loaded_state = load_state()

        # Should contain the recorded agent
        assert "researcher-local" in loaded_state["agents_invoked"]
        assert loaded_state["prerequisites_met"]["local_research"] is True

    def test_state_file_created_atomically(self, temp_state_file, clean_state):
        """Test that state file is created atomically (no corrupt writes)."""
        state = clean_state
        state = record_agent_invocation(state, "planner")

        # Verify file exists and is valid JSON
        assert temp_state_file.exists()

        with open(temp_state_file) as f:
            loaded = json.load(f)

        assert "planner" in loaded["agents_invoked"]


class TestSessionTimeout:
    """Test session timeout and state reset logic."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    def test_session_resets_after_2_hours(self, hook_path, temp_state_file):
        """Test that session state resets after 2 hours of inactivity."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            # Create old state (3 hours ago)
            from datetime import datetime, timedelta
            old_time = (datetime.now() - timedelta(hours=3)).isoformat()

            state = {
                "session_start": old_time,
                "agents_invoked": ["researcher-local", "planner"],
                "prerequisites_met": {
                    "local_research": True,
                    "web_research": False,
                    "planner": True,
                    "test_master": False,
                }
            }

            with open(temp_state_file, "w") as f:
                json.dump(state, f)

            # Invoke any agent (should trigger state reset)
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "researcher-local",
                    "prompt": "Research codebase"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Load state - should be reset
            with open(temp_state_file) as f:
                loaded_state = json.load(f)

            # Session should have been reset (new session_start)
            assert loaded_state["session_start"] != old_time

            # Only the new agent should be in the list
            assert "researcher-local" in loaded_state["agents_invoked"]
            # Old agents should be cleared
            # Note: researcher-local is re-added in this invocation, but planner should be gone
            assert len(loaded_state["agents_invoked"]) == 1


@pytest.mark.skipif(not _imports_available, reason="Hook module not importable")
class TestOutputFormat:
    """Test hook output format compliance."""

    def test_output_decision_format_allow(self):
        """Test that output_decision produces correct JSON format for allow."""
        with patch("sys.stdout", new=StringIO()) as mock_stdout:
            output_decision("allow", "Test reason")

            output = json.loads(mock_stdout.getvalue())

            assert "hookSpecificOutput" in output
            assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert output["hookSpecificOutput"]["permissionDecisionReason"] == "Test reason"

    def test_output_decision_format_deny(self):
        """Test that output_decision produces correct JSON format for deny."""
        with patch("sys.stdout", new=StringIO()) as mock_stdout:
            output_decision("deny", "Test blocking reason")

            output = json.loads(mock_stdout.getvalue())

            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert output["hookSpecificOutput"]["permissionDecisionReason"] == "Test blocking reason"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    def test_missing_subagent_type_allowed(self, hook_path, temp_state_file):
        """Test that missing subagent_type is allowed (no blocking on malformed input)."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "Do something"
                    # No subagent_type
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW (fail open on malformed input)
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_invalid_json_input_allowed(self, hook_path, temp_state_file):
        """Test that invalid JSON input is allowed (fail open on parse errors)."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input="{ invalid json",
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW (fail open on parse errors)
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert "parse error" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_empty_subagent_type_allowed(self, hook_path, temp_state_file):
        """Test that empty subagent_type is allowed."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "",
                    "prompt": "Do something"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            # Parse output
            output = json.loads(result.stdout)

            # Should ALLOW
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestCompleteWorkflow:
    """Test complete /implement workflow simulation."""

    @pytest.fixture
    def hook_path(self):
        """Get path to enforce_pipeline_order.py hook."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "enforce_pipeline_order.py"
        )

    def test_full_pipeline_sequence_allows_implementer(self, hook_path, temp_state_file):
        """Test complete pipeline sequence: all agents invoked in correct order."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            # Reset state
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state
reset_state()
"""], check=True)

            # Run agents in correct order
            agents = [
                "researcher-local",
                "researcher-web",
                "planner",
                "test-master",
                "implementer",  # Should be allowed after prerequisites
            ]

            for agent in agents:
                tool_input = {
                    "tool_name": "Task",
                    "tool_input": {
                        "subagent_type": agent,
                        "prompt": f"Run {agent}"
                    }
                }

                result = subprocess.run(
                    [sys.executable, str(hook_path)],
                    input=json.dumps(tool_input),
                    capture_output=True,
                    text=True,
                )

                output = json.loads(result.stdout)

                # All agents should be allowed in this sequence
                assert output["hookSpecificOutput"]["permissionDecision"] == "allow", \
                    f"Agent {agent} was denied: {output['hookSpecificOutput']['permissionDecisionReason']}"

    def test_skipping_test_master_blocks_implementer(self, hook_path, temp_state_file):
        """Test that skipping test-master blocks implementer (TDD enforcement)."""
        with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(temp_state_file)}):
            # Reset state
            subprocess.run([sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{hook_path.parent}')
from enforce_pipeline_order import reset_state
reset_state()
"""], check=True)

            # Run agents but SKIP test-master
            agents = [
                "researcher-local",
                "researcher-web",
                "planner",
                # test-master SKIPPED!
            ]

            for agent in agents:
                tool_input = {
                    "tool_name": "Task",
                    "tool_input": {
                        "subagent_type": agent,
                        "prompt": f"Run {agent}"
                    }
                }

                subprocess.run(
                    [sys.executable, str(hook_path)],
                    input=json.dumps(tool_input),
                    capture_output=True,
                    text=True,
                )

            # Try to invoke implementer
            tool_input = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "implementer",
                    "prompt": "Implement feature"
                }
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(tool_input),
                capture_output=True,
                text=True,
            )

            output = json.loads(result.stdout)

            # Should DENY implementer (test-master missing)
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert "test-master" in output["hookSpecificOutput"]["permissionDecisionReason"]
