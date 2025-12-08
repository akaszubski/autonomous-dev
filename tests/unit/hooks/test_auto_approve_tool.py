#!/usr/bin/env python3
"""
Unit tests for auto_approve_tool hook (TDD Red Phase).

Tests for PreToolUse hook that auto-approves MCP tool calls for Issue #73.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test subagent context detection (CLAUDE_AGENT_NAME env var)
- Test agent whitelist checking (trusted vs untrusted agents)
- Test user consent checking (enabled/disabled/first-run)
- Test policy loading and caching
- Test circuit breaker logic (10 denials → disable)
- Test audit logging integration
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
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from typing import Dict, Any

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# Add lib directory for dependencies
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
    from auto_approve_tool import (
        on_pre_tool_use,
        should_auto_approve,
        is_subagent_context,
        get_agent_name,
        is_trusted_agent,
        check_user_consent,
        load_and_cache_policy,
        increment_denial_count,
        should_trip_circuit_breaker,
        reset_circuit_breaker,
        AutoApprovalState,
    )
    from tool_validator import ToolValidator, ValidationResult
    from tool_approval_audit import ToolApprovalAuditor
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestSubagentContextDetection:
    """Test subagent context detection via CLAUDE_AGENT_NAME."""

    def test_is_subagent_context_true(self):
        """Test subagent context detected when CLAUDE_AGENT_NAME is set."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            result = is_subagent_context()

            assert result is True

    def test_is_subagent_context_false(self):
        """Test subagent context not detected when CLAUDE_AGENT_NAME is unset."""
        with patch.dict(os.environ, {}, clear=True):
            result = is_subagent_context()

            assert result is False

    def test_get_agent_name_returns_name(self):
        """Test get_agent_name returns agent name from env var."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            agent_name = get_agent_name()

            assert agent_name == "planner"

    def test_get_agent_name_returns_none_if_unset(self):
        """Test get_agent_name returns None if env var unset."""
        with patch.dict(os.environ, {}, clear=True):
            agent_name = get_agent_name()

            assert agent_name is None

    def test_get_agent_name_strips_whitespace(self):
        """Test get_agent_name strips whitespace from agent name."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "  implementer  "}):
            agent_name = get_agent_name()

            assert agent_name == "implementer"

    def test_get_agent_name_empty_string_returns_none(self):
        """Test get_agent_name returns None for empty string."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": ""}):
            agent_name = get_agent_name()

            assert agent_name is None


class TestAgentWhitelistChecking:
    """Test agent whitelist checking (trusted vs untrusted)."""

    @pytest.fixture
    def mock_policy(self):
        """Create mock policy with agent whitelist."""
        return {
            "agents": {
                "trusted": [
                    "researcher",
                    "planner",
                    "test-master",
                    "implementer"
                ],
                "restricted": [
                    "reviewer",
                    "security-auditor"
                ]
            }
        }

    def test_is_trusted_agent_true_for_trusted(self, mock_policy):
        """Test is_trusted_agent returns True for trusted agents."""
        with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
            result = is_trusted_agent("researcher")

            assert result is True

    def test_is_trusted_agent_false_for_restricted(self, mock_policy):
        """Test is_trusted_agent returns False for restricted agents."""
        with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
            result = is_trusted_agent("security-auditor")

            assert result is False

    def test_is_trusted_agent_false_for_unknown(self, mock_policy):
        """Test is_trusted_agent returns False for unknown agents."""
        with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
            result = is_trusted_agent("unknown-agent")

            assert result is False

    def test_is_trusted_agent_case_insensitive(self, mock_policy):
        """Test is_trusted_agent is case-insensitive."""
        with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
            result = is_trusted_agent("RESEARCHER")

            assert result is True

    def test_is_trusted_agent_handles_none(self, mock_policy):
        """Test is_trusted_agent handles None agent name."""
        with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
            result = is_trusted_agent(None)

            assert result is False


class TestUserConsentChecking:
    """Test user consent checking for auto-approval."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary user state file."""
        return tmp_path / "user_state.json"

    def test_check_user_consent_enabled(self, temp_state_file):
        """Test check_user_consent returns True when enabled."""
        state = {
            "preferences": {
                "mcp_auto_approve_enabled": True
            }
        }
        temp_state_file.write_text(json.dumps(state))

        with patch("auto_approve_tool.DEFAULT_STATE_FILE", temp_state_file):
            result = check_user_consent()

            assert result is True

    def test_check_user_consent_disabled(self, temp_state_file):
        """Test check_user_consent returns False when disabled."""
        state = {
            "preferences": {
                "mcp_auto_approve_enabled": False
            }
        }
        temp_state_file.write_text(json.dumps(state))

        with patch("auto_approve_tool.DEFAULT_STATE_FILE", temp_state_file):
            result = check_user_consent()

            assert result is False

    def test_check_user_consent_default_disabled(self, temp_state_file):
        """Test check_user_consent defaults to False (opt-in)."""
        state = {"preferences": {}}  # Missing preference
        temp_state_file.write_text(json.dumps(state))

        with patch("auto_approve_tool.DEFAULT_STATE_FILE", temp_state_file):
            result = check_user_consent()

            assert result is False

    def test_check_user_consent_first_run_prompts(self, temp_state_file):
        """Test check_user_consent prompts on first run."""
        state = {"first_run_complete": False}
        temp_state_file.write_text(json.dumps(state))

        with patch("auto_approve_tool.DEFAULT_STATE_FILE", temp_state_file):
            with patch("auto_approve_tool.prompt_user_for_consent", return_value=True):
                result = check_user_consent()

                assert result is True

    def test_check_user_consent_env_var_override(self, temp_state_file):
        """Test check_user_consent respects MCP_AUTO_APPROVE env var."""
        state = {"preferences": {"mcp_auto_approve_enabled": False}}
        temp_state_file.write_text(json.dumps(state))

        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "true"}):
            with patch("auto_approve_tool.DEFAULT_STATE_FILE", temp_state_file):
                result = check_user_consent()

                # Env var should override state file
                assert result is True


class TestPolicyLoadingAndCaching:
    """Test policy loading and caching."""

    @pytest.fixture
    def temp_policy_file(self, tmp_path):
        """Create temporary policy file."""
        policy_file = tmp_path / "auto_approve_policy.json"
        policy = {
            "version": "1.0",
            "bash": {"whitelist": ["pytest*"], "blacklist": ["rm -rf*"]},
            "file_paths": {"whitelist": [], "blacklist": []},
            "agents": {"trusted": ["researcher"], "restricted": []}
        }
        policy_file.write_text(json.dumps(policy))
        return policy_file

    def test_load_and_cache_policy_loads_file(self, temp_policy_file):
        """Test load_and_cache_policy loads policy from file."""
        policy = load_and_cache_policy(temp_policy_file)

        assert policy is not None
        assert policy["version"] == "1.0"

    def test_load_and_cache_policy_caches_result(self, temp_policy_file):
        """Test load_and_cache_policy caches result (doesn't reload)."""
        # First load
        policy1 = load_and_cache_policy(temp_policy_file)

        # Modify file
        temp_policy_file.write_text('{"version": "2.0"}')

        # Second load should return cached value
        policy2 = load_and_cache_policy(temp_policy_file)

        assert policy2["version"] == "1.0"  # Still cached

    def test_load_and_cache_policy_default_path(self):
        """Test load_and_cache_policy uses default path if not provided."""
        with patch("auto_approve_tool.DEFAULT_POLICY_FILE", Path("/tmp/policy.json")):
            with patch("auto_approve_tool.load_policy", return_value={"version": "1.0"}):
                policy = load_and_cache_policy()

                assert policy is not None

    def test_load_and_cache_policy_handles_missing_file(self, tmp_path):
        """Test load_and_cache_policy handles missing file gracefully."""
        missing_file = tmp_path / "missing.json"

        # Should create default policy
        policy = load_and_cache_policy(missing_file)

        assert policy is not None


class TestCircuitBreakerLogic:
    """Test circuit breaker logic (10 denials → disable)."""

    @pytest.fixture
    def state(self):
        """Create AutoApprovalState instance."""
        return AutoApprovalState()

    def test_increment_denial_count(self, state):
        """Test increment_denial_count increases count."""
        initial_count = state.denial_count

        increment_denial_count(state)

        assert state.denial_count == initial_count + 1

    def test_should_trip_circuit_breaker_false_under_threshold(self, state):
        """Test should_trip_circuit_breaker returns False under threshold."""
        state.denial_count = 5

        result = should_trip_circuit_breaker(state)

        assert result is False

    def test_should_trip_circuit_breaker_true_at_threshold(self, state):
        """Test should_trip_circuit_breaker returns True at threshold."""
        state.denial_count = 10

        result = should_trip_circuit_breaker(state)

        assert result is True

    def test_should_trip_circuit_breaker_true_above_threshold(self, state):
        """Test should_trip_circuit_breaker returns True above threshold."""
        state.denial_count = 15

        result = should_trip_circuit_breaker(state)

        assert result is True

    def test_circuit_breaker_disables_auto_approval(self, state):
        """Test circuit breaker disables auto-approval when tripped."""
        state.denial_count = 10

        # Mock check_user_consent to return True initially
        with patch("auto_approve_tool.check_user_consent", return_value=True):
            result = should_auto_approve("researcher", {"tool": "Bash"}, state)

            # Should be disabled due to circuit breaker
            assert result is False

    def test_reset_circuit_breaker_resets_count(self, state):
        """Test reset_circuit_breaker resets denial count."""
        state.denial_count = 10

        reset_circuit_breaker(state)

        assert state.denial_count == 0

    def test_circuit_breaker_logs_trip_event(self, state):
        """Test circuit breaker logs event when tripped."""
        state.denial_count = 10

        with patch("auto_approve_tool.audit_log") as mock_audit:
            should_trip_circuit_breaker(state)

            # Should log circuit breaker trip
            mock_audit.assert_called()


class TestShouldAutoApprove:
    """Test high-level should_auto_approve function."""

    @pytest.fixture
    def state(self):
        """Create AutoApprovalState instance."""
        return AutoApprovalState()

    @pytest.fixture
    def mock_policy(self):
        """Create mock policy."""
        return {
            "agents": {"trusted": ["researcher"], "restricted": []},
            "bash": {"whitelist": ["pytest*"], "blacklist": []},
            "file_paths": {"whitelist": [], "blacklist": []}
        }

    def test_should_auto_approve_true_for_trusted_agent(self, state, mock_policy):
        """Test should_auto_approve returns True for trusted agent."""
        tool_call = {"tool": "Bash", "parameters": {"command": "pytest tests/"}}

        with patch("auto_approve_tool.is_subagent_context", return_value=True):
            with patch("auto_approve_tool.get_agent_name", return_value="researcher"):
                with patch("auto_approve_tool.check_user_consent", return_value=True):
                    with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
                        with patch("auto_approve_tool.ToolValidator") as mock_validator:
                            mock_validator.return_value.validate_tool_call.return_value = ValidationResult(
                                approved=True, reason="Whitelist", security_risk=False, matched_pattern="pytest*"
                            )

                            result = should_auto_approve("researcher", tool_call, state)

                            assert result is True

    def test_should_auto_approve_false_for_untrusted_agent(self, state, mock_policy):
        """Test should_auto_approve returns False for untrusted agent."""
        tool_call = {"tool": "Bash", "parameters": {"command": "pytest tests/"}}

        with patch("auto_approve_tool.is_subagent_context", return_value=True):
            with patch("auto_approve_tool.get_agent_name", return_value="unknown-agent"):
                with patch("auto_approve_tool.check_user_consent", return_value=True):
                    with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
                        result = should_auto_approve("unknown-agent", tool_call, state)

                        assert result is False

    def test_should_auto_approve_false_if_consent_disabled(self, state, mock_policy):
        """Test should_auto_approve returns False if user consent disabled."""
        tool_call = {"tool": "Bash", "parameters": {"command": "pytest tests/"}}

        with patch("auto_approve_tool.is_subagent_context", return_value=True):
            with patch("auto_approve_tool.get_agent_name", return_value="researcher"):
                with patch("auto_approve_tool.check_user_consent", return_value=False):
                    result = should_auto_approve("researcher", tool_call, state)

                    assert result is False

    def test_should_auto_approve_false_if_not_subagent(self, state):
        """Test should_auto_approve returns False if not subagent context."""
        tool_call = {"tool": "Bash", "parameters": {"command": "pytest tests/"}}

        with patch("auto_approve_tool.is_subagent_context", return_value=False):
            result = should_auto_approve(None, tool_call, state)

            assert result is False

    def test_should_auto_approve_false_for_blacklisted_command(self, state, mock_policy):
        """Test should_auto_approve returns False for blacklisted command."""
        tool_call = {"tool": "Bash", "parameters": {"command": "rm -rf /"}}

        with patch("auto_approve_tool.is_subagent_context", return_value=True):
            with patch("auto_approve_tool.get_agent_name", return_value="researcher"):
                with patch("auto_approve_tool.check_user_consent", return_value=True):
                    with patch("auto_approve_tool.load_and_cache_policy", return_value=mock_policy):
                        with patch("auto_approve_tool.ToolValidator") as mock_validator:
                            mock_validator.return_value.validate_tool_call.return_value = ValidationResult(
                                approved=False, reason="Blacklist", security_risk=True, matched_pattern="rm -rf*"
                            )

                            result = should_auto_approve("researcher", tool_call, state)

                            assert result is False


class TestOnPreToolUseHook:
    """Test on_pre_tool_use hook function."""

    @pytest.fixture
    def mock_event(self):
        """Create mock PreToolUse event."""
        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}
        return event

    @pytest.fixture
    def state(self):
        """Create AutoApprovalState instance."""
        return AutoApprovalState()

    def test_on_pre_tool_use_approves_valid_call(self, mock_event, state):
        """Test on_pre_tool_use approves valid tool call."""
        with patch("auto_approve_tool.should_auto_approve", return_value=True):
            with patch("auto_approve_tool.ToolApprovalAuditor") as mock_auditor:
                result = on_pre_tool_use(mock_event, state)

                # Should approve
                assert result["approved"] is True

    def test_on_pre_tool_use_denies_invalid_call(self, mock_event, state):
        """Test on_pre_tool_use denies invalid tool call."""
        with patch("auto_approve_tool.should_auto_approve", return_value=False):
            with patch("auto_approve_tool.ToolApprovalAuditor") as mock_auditor:
                result = on_pre_tool_use(mock_event, state)

                # Should deny
                assert result["approved"] is False

    def test_on_pre_tool_use_logs_approval(self, mock_event, state):
        """Test on_pre_tool_use logs approval to audit log."""
        with patch("auto_approve_tool.should_auto_approve", return_value=True):
            with patch("auto_approve_tool.ToolApprovalAuditor") as mock_auditor:
                on_pre_tool_use(mock_event, state)

                # Should log approval
                mock_auditor.return_value.log_approval.assert_called_once()

    def test_on_pre_tool_use_logs_denial(self, mock_event, state):
        """Test on_pre_tool_use logs denial to audit log."""
        with patch("auto_approve_tool.should_auto_approve", return_value=False):
            with patch("auto_approve_tool.ToolApprovalAuditor") as mock_auditor:
                on_pre_tool_use(mock_event, state)

                # Should log denial
                mock_auditor.return_value.log_denial.assert_called_once()

    def test_on_pre_tool_use_increments_denial_count(self, mock_event, state):
        """Test on_pre_tool_use increments denial count on denial."""
        with patch("auto_approve_tool.should_auto_approve", return_value=False):
            with patch("auto_approve_tool.ToolApprovalAuditor"):
                on_pre_tool_use(mock_event, state)

                # Should increment denial count
                assert state.denial_count > 0

    def test_on_pre_tool_use_handles_errors_gracefully(self, mock_event, state):
        """Test on_pre_tool_use handles errors gracefully (fails open)."""
        with patch("auto_approve_tool.should_auto_approve", side_effect=Exception("Test error")):
            result = on_pre_tool_use(mock_event, state)

            # Should fail open (deny by default for safety)
            assert result["approved"] is False
            assert "error" in result

    def test_on_pre_tool_use_extracts_agent_from_env(self, mock_event, state):
        """Test on_pre_tool_use extracts agent name from environment."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            with patch("auto_approve_tool.should_auto_approve", return_value=True) as mock_should_approve:
                with patch("auto_approve_tool.ToolApprovalAuditor"):
                    on_pre_tool_use(mock_event, state)

                    # Should pass agent name
                    mock_should_approve.assert_called()
                    call_args = mock_should_approve.call_args[0]
                    assert call_args[0] == "researcher"


class TestGracefulDegradation:
    """Test graceful degradation on errors."""

    @pytest.fixture
    def mock_event(self):
        """Create mock PreToolUse event."""
        event = Mock()
        event.tool = "Bash"
        event.parameters = {"command": "pytest tests/"}
        return event

    @pytest.fixture
    def state(self):
        """Create AutoApprovalState instance."""
        return AutoApprovalState()

    def test_missing_policy_file_fails_safe(self, mock_event, state):
        """Test missing policy file fails safe (denies)."""
        with patch("auto_approve_tool.load_and_cache_policy", side_effect=FileNotFoundError):
            result = on_pre_tool_use(mock_event, state)

            # Should fail safe (deny)
            assert result["approved"] is False

    def test_invalid_policy_fails_safe(self, mock_event, state):
        """Test invalid policy fails safe (denies)."""
        with patch("auto_approve_tool.load_and_cache_policy", side_effect=json.JSONDecodeError("", "", 0)):
            result = on_pre_tool_use(mock_event, state)

            # Should fail safe (deny)
            assert result["approved"] is False

    def test_validator_error_fails_safe(self, mock_event, state):
        """Test validator error fails safe (denies)."""
        with patch("auto_approve_tool.ToolValidator", side_effect=Exception("Validator error")):
            result = on_pre_tool_use(mock_event, state)

            # Should fail safe (deny)
            assert result["approved"] is False

    def test_audit_log_error_continues(self, mock_event, state):
        """Test audit log error doesn't block approval decision."""
        with patch("auto_approve_tool.should_auto_approve", return_value=True):
            with patch("auto_approve_tool.ToolApprovalAuditor") as mock_auditor:
                mock_auditor.return_value.log_approval.side_effect = Exception("Log error")

                result = on_pre_tool_use(mock_event, state)

                # Should still approve despite log error
                assert result["approved"] is True


class TestEverywhereMode:
    """Test everywhere mode (auto-approve in main conversation + subagents)."""

    @pytest.fixture
    def mock_policy(self):
        """Create mock policy."""
        return {
            "agents": {"trusted": ["researcher"], "restricted": []},
            "bash": {"whitelist": ["gh issue list*", "pytest*"], "blacklist": []},
            "file_paths": {"whitelist": [], "blacklist": []}
        }

    def test_everywhere_mode_approves_in_main_conversation(self, mock_policy):
        """Test everywhere mode approves whitelisted commands in main conversation."""
        tool = "Bash"
        parameters = {"command": "gh issue list --limit 20"}

        with patch("auto_approve_tool.get_auto_approval_mode", return_value="everywhere"):
            with patch("auto_approve_tool.is_subagent_context", return_value=False):
                with patch("auto_approve_tool._get_cached_validator") as mock_validator:
                    mock_validator.return_value.validate_tool_call.return_value = ValidationResult(
                        approved=True, reason="Whitelist match: gh issue list*", security_risk=False, matched_pattern="gh issue list*"
                    )

                    approved, reason = should_auto_approve(tool, parameters, agent_name=None)

                    assert approved is True
                    assert "Whitelist" in reason

    def test_everywhere_mode_denies_blacklisted_in_main_conversation(self, mock_policy):
        """Test everywhere mode denies blacklisted commands in main conversation."""
        tool = "Bash"
        parameters = {"command": "rm -rf /"}

        with patch("auto_approve_tool.get_auto_approval_mode", return_value="everywhere"):
            with patch("auto_approve_tool.is_subagent_context", return_value=False):
                with patch("auto_approve_tool._get_cached_validator") as mock_validator:
                    mock_validator.return_value.validate_tool_call.return_value = ValidationResult(
                        approved=False, reason="Blacklist match: rm -rf*", security_risk=True, matched_pattern="rm -rf*"
                    )

                    approved, reason = should_auto_approve(tool, parameters, agent_name=None)

                    assert approved is False
                    assert "Blacklist" in reason

    def test_subagent_only_mode_denies_in_main_conversation(self):
        """Test subagent_only mode denies in main conversation."""
        tool = "Bash"
        parameters = {"command": "gh issue list --limit 20"}

        with patch("auto_approve_tool.get_auto_approval_mode", return_value="subagent_only"):
            with patch("auto_approve_tool.is_subagent_context", return_value=False):
                approved, reason = should_auto_approve(tool, parameters, agent_name=None)

                assert approved is False
                assert "subagent_only" in reason

    def test_subagent_only_mode_approves_in_subagent(self, mock_policy):
        """Test subagent_only mode approves in subagent context."""
        tool = "Bash"
        parameters = {"command": "pytest tests/"}

        with patch("auto_approve_tool.get_auto_approval_mode", return_value="subagent_only"):
            with patch("auto_approve_tool.is_subagent_context", return_value=True):
                with patch("auto_approve_tool.is_trusted_agent", return_value=True):
                    with patch("auto_approve_tool._get_cached_validator") as mock_validator:
                        mock_validator.return_value.validate_tool_call.return_value = ValidationResult(
                            approved=True, reason="Whitelist match: pytest*", security_risk=False, matched_pattern="pytest*"
                        )

                        approved, reason = should_auto_approve(tool, parameters, agent_name="researcher")

                        assert approved is True

    def test_disabled_mode_denies_everywhere(self):
        """Test disabled mode denies in both main conversation and subagents."""
        tool = "Bash"
        parameters = {"command": "gh issue list --limit 20"}

        # Test main conversation
        with patch("auto_approve_tool.get_auto_approval_mode", return_value="disabled"):
            with patch("auto_approve_tool.is_subagent_context", return_value=False):
                approved, reason = should_auto_approve(tool, parameters, agent_name=None)

                assert approved is False
                assert "disabled" in reason.lower()

        # Test subagent
        with patch("auto_approve_tool.get_auto_approval_mode", return_value="disabled"):
            with patch("auto_approve_tool.is_subagent_context", return_value=True):
                approved, reason = should_auto_approve(tool, parameters, agent_name="researcher")

                assert approved is False
                assert "disabled" in reason.lower()

    def test_main_conversation_skips_agent_whitelist_check(self, mock_policy):
        """Test main conversation skips agent whitelist check."""
        tool = "Bash"
        parameters = {"command": "gh issue list --limit 20"}

        with patch("auto_approve_tool.get_auto_approval_mode", return_value="everywhere"):
            with patch("auto_approve_tool.is_subagent_context", return_value=False):
                with patch("auto_approve_tool._get_cached_validator") as mock_validator:
                    mock_validator.return_value.validate_tool_call.return_value = ValidationResult(
                        approved=True, reason="Whitelist match", security_risk=False, matched_pattern="gh issue list*"
                    )

                    # agent_name is None (main conversation), should still approve
                    approved, reason = should_auto_approve(tool, parameters, agent_name=None)

                    assert approved is True
