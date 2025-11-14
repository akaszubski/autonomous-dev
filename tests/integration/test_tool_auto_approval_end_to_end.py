#!/usr/bin/env python3
"""
Integration tests for MCP tool auto-approval (TDD Red Phase).

Tests end-to-end workflow for Issue #73: MCP Auto-Approval for Subagent Tool Calls.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: modules not found).

Test Strategy:
- Test complete workflow: subagent → validation → auto-approval → audit
- Test researcher WebSearch auto-approval
- Test implementer Bash (whitelist) auto-approval
- Test Bash (blacklist) denial
- Test first-run consent prompt flow
- Test circuit breaker trip after 10 denials
- Test graceful degradation on errors

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
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any

# Add directories to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - modules don't exist yet (TDD!)
try:
    from auto_approve_tool import on_pre_tool_use, AutoApprovalState
    from tool_validator import ToolValidator
    from tool_approval_audit import ToolApprovalAuditor
    from user_state_manager import UserStateManager
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestResearcherWebSearchAutoApproval:
    """Test researcher agent WebSearch auto-approval."""

    @pytest.fixture
    def setup_env(self, tmp_path):
        """Setup test environment."""
        # Create policy file
        policy_file = tmp_path / "auto_approve_policy.json"
        policy = {
            "version": "1.0",
            "bash": {"whitelist": [], "blacklist": []},
            "file_paths": {"whitelist": [], "blacklist": []},
            "agents": {"trusted": ["researcher"], "restricted": []}
        }
        policy_file.write_text(json.dumps(policy))

        # Create state file with consent enabled
        state_file = tmp_path / "user_state.json"
        state = {
            "preferences": {"mcp_auto_approve_enabled": True},
            "auto_approval_first_run_complete": True
        }
        state_file.write_text(json.dumps(state))

        # Create audit log file
        audit_log = tmp_path / "audit.log"

        return policy_file, state_file, audit_log

    def test_researcher_websearch_auto_approved(self, setup_env, tmp_path):
        """Test researcher WebSearch tool call is auto-approved."""
        policy_file, state_file, audit_log = setup_env

        # Mock PreToolUse event
        event = Mock()
        event.tool = "WebSearch"
        event.parameters = {"query": "Python async patterns"}

        # Set agent context
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        result = on_pre_tool_use(event, state)

                        # Should be approved
                        assert result["approved"] is True
                        assert result["reason"] is not None

    def test_researcher_websearch_logged_to_audit(self, setup_env, tmp_path):
        """Test researcher WebSearch approval is logged to audit."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "WebSearch"
        event.parameters = {"query": "Python patterns"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        on_pre_tool_use(event, state)

                        # Should log to audit
                        assert audit_log.exists()
                        log_content = audit_log.read_text()
                        assert "approval" in log_content
                        assert "researcher" in log_content
                        assert "WebSearch" in log_content


class TestImplementerBashWhitelistAutoApproval:
    """Test implementer Bash (whitelist) auto-approval."""

    @pytest.fixture
    def setup_env(self, tmp_path):
        """Setup test environment."""
        policy_file = tmp_path / "auto_approve_policy.json"
        policy = {
            "version": "1.0",
            "bash": {
                "whitelist": ["pytest*", "git status", "git diff*"],
                "blacklist": ["rm -rf*", "sudo*"]
            },
            "file_paths": {"whitelist": [], "blacklist": []},
            "agents": {"trusted": ["implementer"], "restricted": []}
        }
        policy_file.write_text(json.dumps(policy))

        state_file = tmp_path / "user_state.json"
        state = {
            "preferences": {"mcp_auto_approve_enabled": True},
            "auto_approval_first_run_complete": True
        }
        state_file.write_text(json.dumps(state))

        audit_log = tmp_path / "audit.log"

        return policy_file, state_file, audit_log

    def test_implementer_pytest_command_auto_approved(self, setup_env):
        """Test implementer pytest command is auto-approved."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/unit/"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "implementer"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        result = on_pre_tool_use(event, state)

                        assert result["approved"] is True
                        assert "pytest*" in result["reason"]

    def test_implementer_git_status_auto_approved(self, setup_env):
        """Test implementer 'git status' command is auto-approved."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "git status"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "implementer"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        result = on_pre_tool_use(event, state)

                        assert result["approved"] is True
                        assert "git status" in result["reason"]


class TestBashBlacklistDenial:
    """Test Bash blacklist denial."""

    @pytest.fixture
    def setup_env(self, tmp_path):
        """Setup test environment."""
        policy_file = tmp_path / "auto_approve_policy.json"
        policy = {
            "version": "1.0",
            "bash": {
                "whitelist": ["pytest*"],
                "blacklist": ["rm -rf*", "sudo*"]
            },
            "file_paths": {"whitelist": [], "blacklist": []},
            "agents": {"trusted": ["researcher"], "restricted": []}
        }
        policy_file.write_text(json.dumps(policy))

        state_file = tmp_path / "user_state.json"
        state = {
            "preferences": {"mcp_auto_approve_enabled": True},
            "auto_approval_first_run_complete": True
        }
        state_file.write_text(json.dumps(state))

        audit_log = tmp_path / "audit.log"

        return policy_file, state_file, audit_log

    def test_rm_rf_command_denied(self, setup_env):
        """Test 'rm -rf' command is denied."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "rm -rf /tmp/data"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        result = on_pre_tool_use(event, state)

                        assert result["approved"] is False
                        assert "rm -rf*" in result["reason"]

    def test_sudo_command_denied(self, setup_env):
        """Test 'sudo' command is denied."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "sudo apt install python3"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        result = on_pre_tool_use(event, state)

                        assert result["approved"] is False
                        assert "sudo*" in result["reason"]

    def test_blacklist_denial_logged_with_security_risk(self, setup_env):
        """Test blacklist denial logged with security_risk flag."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "rm -rf /"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        on_pre_tool_use(event, state)

                        # Check audit log
                        log_content = audit_log.read_text()
                        log_entry = json.loads(log_content.strip())

                        assert log_entry["event"] == "denial"
                        assert log_entry["security_risk"] is True


class TestFirstRunConsentPrompt:
    """Test first-run consent prompt flow."""

    @pytest.fixture
    def setup_env(self, tmp_path):
        """Setup test environment."""
        policy_file = tmp_path / "auto_approve_policy.json"
        policy = {
            "version": "1.0",
            "bash": {"whitelist": ["pytest*"], "blacklist": []},
            "file_paths": {"whitelist": [], "blacklist": []},
            "agents": {"trusted": ["researcher"], "restricted": []}
        }
        policy_file.write_text(json.dumps(policy))

        # State file without consent
        state_file = tmp_path / "user_state.json"
        state = {"auto_approval_first_run_complete": False}
        state_file.write_text(json.dumps(state))

        audit_log = tmp_path / "audit.log"

        return policy_file, state_file, audit_log

    def test_first_run_prompts_for_consent(self, setup_env):
        """Test first run prompts for consent before auto-approving."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        with patch("auto_approve_tool.prompt_user_for_consent", return_value=True) as mock_prompt:
                            state = AutoApprovalState()
                            result = on_pre_tool_use(event, state)

                            # Should have prompted
                            mock_prompt.assert_called_once()

    def test_first_run_accept_enables_auto_approval(self, setup_env):
        """Test accepting first-run consent enables auto-approval."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        with patch("auto_approve_tool.prompt_user_for_consent", return_value=True):
                            state = AutoApprovalState()
                            result = on_pre_tool_use(event, state)

                            # Should be approved
                            assert result["approved"] is True

    def test_first_run_reject_disables_auto_approval(self, setup_env):
        """Test rejecting first-run consent disables auto-approval."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        with patch("auto_approve_tool.prompt_user_for_consent", return_value=False):
                            state = AutoApprovalState()
                            result = on_pre_tool_use(event, state)

                            # Should be denied
                            assert result["approved"] is False


class TestCircuitBreakerTrip:
    """Test circuit breaker trip after 10 denials."""

    @pytest.fixture
    def setup_env(self, tmp_path):
        """Setup test environment."""
        policy_file = tmp_path / "auto_approve_policy.json"
        policy = {
            "version": "1.0",
            "bash": {"whitelist": ["pytest*"], "blacklist": ["rm -rf*"]},
            "file_paths": {"whitelist": [], "blacklist": []},
            "agents": {"trusted": ["researcher"], "restricted": []}
        }
        policy_file.write_text(json.dumps(policy))

        state_file = tmp_path / "user_state.json"
        state = {
            "preferences": {"mcp_auto_approve_enabled": True},
            "auto_approval_first_run_complete": True
        }
        state_file.write_text(json.dumps(state))

        audit_log = tmp_path / "audit.log"

        return policy_file, state_file, audit_log

    def test_circuit_breaker_trips_after_10_denials(self, setup_env):
        """Test circuit breaker trips after 10 consecutive denials."""
        policy_file, state_file, audit_log = setup_env

        state = AutoApprovalState()

        # Make 10 denied calls
        for i in range(10):
            event = Mock()
            event.tool = "Bash"
            event.parameters = {"command": f"rm -rf /tmp/file{i}"}

            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
                with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                    with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                        with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                            result = on_pre_tool_use(event, state)

                            assert result["approved"] is False

        # Circuit breaker should have tripped
        assert state.denial_count >= 10

        # Next call should be denied even if valid
        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        result = on_pre_tool_use(event, state)

                        # Should be denied due to circuit breaker
                        assert result["approved"] is False
                        assert "circuit breaker" in result["reason"].lower()

    def test_circuit_breaker_logged_to_audit(self, setup_env):
        """Test circuit breaker trip is logged to audit."""
        policy_file, state_file, audit_log = setup_env

        state = AutoApprovalState()

        # Make 10 denied calls
        for i in range(10):
            event = Mock()
            event.tool = "Bash"
            event.parameters = {"command": f"rm -rf /tmp/file{i}"}

            with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
                with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                    with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                        with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                            on_pre_tool_use(event, state)

        # Check audit log for circuit breaker event
        log_content = audit_log.read_text()
        assert "circuit_breaker_trip" in log_content


class TestGracefulDegradation:
    """Test graceful degradation on errors."""

    @pytest.fixture
    def setup_env(self, tmp_path):
        """Setup test environment."""
        policy_file = tmp_path / "auto_approve_policy.json"
        state_file = tmp_path / "user_state.json"
        audit_log = tmp_path / "audit.log"

        return policy_file, state_file, audit_log

    def test_missing_policy_file_fails_safe(self, setup_env):
        """Test missing policy file fails safe (denies)."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        result = on_pre_tool_use(event, state)

                        # Should fail safe (deny)
                        assert result["approved"] is False

    def test_invalid_agent_name_fails_safe(self, setup_env):
        """Test invalid agent name fails safe (denies)."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}

        # Invalid agent name
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": ""}):
            with patch("auto_approve_tool.DEFAULT_POLICY_FILE", policy_file):
                with patch("auto_approve_tool.DEFAULT_STATE_FILE", state_file):
                    with patch("auto_approve_tool.DEFAULT_AUDIT_LOG", audit_log):
                        state = AutoApprovalState()
                        result = on_pre_tool_use(event, state)

                        # Should fail safe
                        assert result["approved"] is False

    def test_validator_exception_fails_safe(self, setup_env):
        """Test validator exception fails safe (denies)."""
        policy_file, state_file, audit_log = setup_env

        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}

        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.ToolValidator", side_effect=Exception("Validator error")):
                state = AutoApprovalState()
                result = on_pre_tool_use(event, state)

                # Should fail safe
                assert result["approved"] is False
