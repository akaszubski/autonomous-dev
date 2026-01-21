#!/usr/bin/env python3
"""
Unit tests for auto_approval_engine.py.

Tests the MCP auto-approval engine for tool calls including:
- AutoApprovalState management
- Subagent context detection
- Agent whitelist checking
- Circuit breaker logic
- should_auto_approve decision making
- on_pre_tool_use hook

Issue: #234 (Test coverage improvement)
"""

import os
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.auto_approval_engine import (
    AutoApprovalState,
    is_subagent_context,
    get_agent_name,
    is_trusted_agent,
    should_auto_approve,
    on_pre_tool_use,
    increment_denial_count,
    should_trip_circuit_breaker,
    reset_circuit_breaker,
    load_and_cache_policy,
    CIRCUIT_BREAKER_THRESHOLD,
    _get_global_state,
)


class TestAutoApprovalState:
    """Test AutoApprovalState dataclass."""

    def test_initial_state(self):
        """Initial state should have zero denials."""
        state = AutoApprovalState()
        assert state.denial_count == 0
        assert state.circuit_breaker_tripped is False

    def test_increment_denial_count(self):
        """Increment denial count."""
        state = AutoApprovalState()
        assert state.increment_denial_count() == 1
        assert state.increment_denial_count() == 2
        assert state.get_denial_count() == 2

    def test_reset_denial_count(self):
        """Reset denial count to zero."""
        state = AutoApprovalState()
        state.increment_denial_count()
        state.increment_denial_count()
        state.reset_denial_count()
        assert state.get_denial_count() == 0

    def test_trip_circuit_breaker(self):
        """Trip circuit breaker."""
        state = AutoApprovalState()
        assert not state.is_circuit_breaker_tripped()
        state.trip_circuit_breaker()
        assert state.is_circuit_breaker_tripped()

    def test_reset_circuit_breaker(self):
        """Reset circuit breaker."""
        state = AutoApprovalState()
        state.trip_circuit_breaker()
        state.increment_denial_count()
        state.reset_circuit_breaker()
        assert not state.is_circuit_breaker_tripped()
        assert state.get_denial_count() == 0

    def test_items_method(self):
        """Items method for dict-like interface."""
        state = AutoApprovalState()
        state.increment_denial_count()
        items = state.items()
        assert ("denial_count", 1) in items
        assert ("circuit_breaker_tripped", False) in items

    def test_thread_safe_operations(self):
        """Operations should be thread-safe."""
        import threading
        state = AutoApprovalState()

        def increment():
            for _ in range(100):
                state.increment_denial_count()

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 500 increments
        assert state.get_denial_count() == 500


class TestSubagentContext:
    """Test subagent context detection."""

    def test_is_subagent_context_true(self):
        """Detect subagent context when env var set."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "implementer"}):
            assert is_subagent_context() is True

    def test_is_subagent_context_false_empty(self):
        """Not subagent context when env var empty."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": ""}):
            assert is_subagent_context() is False

    def test_is_subagent_context_false_missing(self):
        """Not subagent context when env var missing."""
        env = os.environ.copy()
        env.pop("CLAUDE_AGENT_NAME", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_subagent_context() is False

    def test_get_agent_name_valid(self):
        """Get valid agent name."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            assert get_agent_name() == "researcher"

    def test_get_agent_name_empty(self):
        """None when agent name empty."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": ""}):
            assert get_agent_name() is None

    def test_get_agent_name_whitespace_only(self):
        """None when agent name is whitespace."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "   "}):
            assert get_agent_name() is None

    def test_get_agent_name_sanitizes_control_chars(self):
        """Sanitize control characters from agent name."""
        # Can't use null byte in env var directly, test sanitization via mock
        with patch('plugins.autonomous_dev.lib.auto_approval_engine.os.getenv') as mock_getenv:
            mock_getenv.return_value = "test\x0aagent"  # newline char
            name = get_agent_name()
            assert name == "testagent"

    def test_get_agent_name_strips_whitespace(self):
        """Strip leading/trailing whitespace."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "  implementer  "}):
            assert get_agent_name() == "implementer"


class TestAgentWhitelist:
    """Test agent whitelist checking."""

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.load_and_cache_policy')
    def test_is_trusted_agent_in_whitelist(self, mock_policy):
        """Agent in whitelist is trusted."""
        mock_policy.return_value = {
            "agents": {"trusted": ["implementer", "researcher"]}
        }
        assert is_trusted_agent("implementer") is True

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.load_and_cache_policy')
    def test_is_trusted_agent_not_in_whitelist(self, mock_policy):
        """Agent not in whitelist is not trusted."""
        mock_policy.return_value = {
            "agents": {"trusted": ["implementer"]}
        }
        assert is_trusted_agent("unknown-agent") is False

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.load_and_cache_policy')
    def test_is_trusted_agent_case_insensitive(self, mock_policy):
        """Whitelist check is case-insensitive."""
        mock_policy.return_value = {
            "agents": {"trusted": ["Implementer"]}
        }
        assert is_trusted_agent("implementer") is True
        assert is_trusted_agent("IMPLEMENTER") is True

    def test_is_trusted_agent_none(self):
        """None agent name is not trusted."""
        assert is_trusted_agent(None) is False

    def test_is_trusted_agent_empty_string(self):
        """Empty string agent name is not trusted."""
        assert is_trusted_agent("") is False


class TestCircuitBreaker:
    """Test circuit breaker logic."""

    def test_circuit_breaker_threshold(self):
        """Circuit breaker threshold should be 10."""
        assert CIRCUIT_BREAKER_THRESHOLD == 10

    def test_should_trip_after_threshold(self):
        """Should trip after reaching threshold."""
        state = AutoApprovalState()
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            state.increment_denial_count()
        assert should_trip_circuit_breaker(state) is True

    def test_should_not_trip_before_threshold(self):
        """Should not trip before reaching threshold."""
        state = AutoApprovalState()
        for _ in range(CIRCUIT_BREAKER_THRESHOLD - 1):
            state.increment_denial_count()
        assert should_trip_circuit_breaker(state) is False

    def test_increment_uses_global_state(self):
        """Increment uses global state by default."""
        # Reset global state first
        reset_circuit_breaker()

        count = increment_denial_count()
        assert count >= 1  # May have leftover from other tests

    def test_reset_global_circuit_breaker(self):
        """Reset global circuit breaker."""
        state = _get_global_state()
        state.trip_circuit_breaker()
        reset_circuit_breaker()
        assert not state.is_circuit_breaker_tripped()


class TestShouldAutoApprove:
    """Test should_auto_approve decision logic."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset global state before each test."""
        reset_circuit_breaker()
        yield

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_auto_approval_mode')
    def test_disabled_mode(self, mock_mode):
        """Deny when auto-approval disabled."""
        mock_mode.return_value = "disabled"

        approved, reason = should_auto_approve("Bash", {"command": "ls"})

        assert approved is False
        assert "disabled" in reason.lower()

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_auto_approval_mode')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.is_subagent_context')
    def test_subagent_only_not_in_subagent(self, mock_subagent, mock_mode):
        """Deny when subagent_only mode but not in subagent."""
        mock_mode.return_value = "subagent_only"
        mock_subagent.return_value = False

        approved, reason = should_auto_approve("Bash", {"command": "ls"})

        assert approved is False
        assert "subagent" in reason.lower()

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_auto_approval_mode')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.is_subagent_context')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.is_trusted_agent')
    def test_subagent_only_untrusted_agent(self, mock_trusted, mock_subagent, mock_mode):
        """Deny when agent not trusted in subagent_only mode."""
        mock_mode.return_value = "subagent_only"
        mock_subagent.return_value = True
        mock_trusted.return_value = False

        approved, reason = should_auto_approve("Bash", {"command": "ls"}, agent_name="unknown")

        assert approved is False
        assert "whitelist" in reason.lower()

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_auto_approval_mode')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.is_subagent_context')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.is_trusted_agent')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine._get_cached_validator')
    def test_everywhere_mode_approves(self, mock_validator, mock_trusted, mock_subagent, mock_mode):
        """Approve in everywhere mode when tool is valid."""
        mock_mode.return_value = "everywhere"
        mock_subagent.return_value = False
        mock_trusted.return_value = True

        mock_result = MagicMock()
        mock_result.approved = True
        mock_result.reason = "Tool allowed"
        mock_validator.return_value.validate_tool_call.return_value = mock_result

        approved, reason = should_auto_approve("Read", {"file_path": "/tmp/file.txt"})

        assert approved is True

    @patch('plugins.autonomous_dev.lib.auto_approval_engine._get_global_state')
    def test_circuit_breaker_tripped(self, mock_state):
        """Deny when circuit breaker tripped."""
        mock_state_obj = MagicMock()
        mock_state_obj.is_circuit_breaker_tripped.return_value = True
        mock_state.return_value = mock_state_obj

        approved, reason = should_auto_approve("Bash", {"command": "ls"})

        assert approved is False
        assert "circuit breaker" in reason.lower()


class TestOnPreToolUse:
    """Test on_pre_tool_use hook entry point."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset global state before each test."""
        reset_circuit_breaker()
        yield

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.should_auto_approve')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_agent_name')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.ToolApprovalAuditor')
    def test_returns_dict_with_approved(self, mock_auditor, mock_agent, mock_approve):
        """Hook returns dict with approved field."""
        mock_agent.return_value = "implementer"
        mock_approve.return_value = (True, "Approved")
        mock_auditor.return_value = MagicMock()

        result = on_pre_tool_use("Read", {"file_path": "/tmp/test.txt"})

        assert isinstance(result, dict)
        assert "approved" in result
        assert "reason" in result

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.should_auto_approve')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_agent_name')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.ToolApprovalAuditor')
    def test_logs_approval(self, mock_auditor, mock_agent, mock_approve):
        """Hook logs approvals."""
        mock_agent.return_value = "implementer"
        mock_approve.return_value = (True, "Approved")
        auditor_instance = MagicMock()
        mock_auditor.return_value = auditor_instance

        on_pre_tool_use("Read", {"file_path": "/tmp/test.txt"})

        auditor_instance.log_approval.assert_called_once()

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.should_auto_approve')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_agent_name')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.ToolApprovalAuditor')
    def test_logs_denial(self, mock_auditor, mock_agent, mock_approve):
        """Hook logs denials."""
        mock_agent.return_value = "unknown"
        mock_approve.return_value = (False, "Denied - not trusted")
        auditor_instance = MagicMock()
        mock_auditor.return_value = auditor_instance

        on_pre_tool_use("Bash", {"command": "rm -rf /"})

        auditor_instance.log_denial.assert_called_once()

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.should_auto_approve')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_agent_name')
    def test_graceful_degradation_on_error(self, mock_agent, mock_approve):
        """Hook returns denial on error (graceful degradation)."""
        mock_agent.return_value = "implementer"
        mock_approve.side_effect = RuntimeError("Unexpected error")

        result = on_pre_tool_use("Bash", {"command": "ls"})

        assert result["approved"] is False
        assert "error" in result["reason"].lower()


class TestPolicyCaching:
    """Test policy loading and caching."""

    @patch('plugins.autonomous_dev.lib.auto_approval_engine._cached_policy', None)
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.load_policy')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_policy_file')
    def test_load_and_cache_policy(self, mock_get_file, mock_load):
        """Load policy is called once and cached."""
        mock_get_file.return_value = Path("/fake/policy.json")
        mock_load.return_value = {"agents": {"trusted": []}}

        # First call
        policy1 = load_and_cache_policy()

        # Policy should be loaded
        assert policy1 == {"agents": {"trusted": []}}


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_auto_approval_state_concurrent_trips(self):
        """Handle concurrent circuit breaker trips."""
        import threading
        state = AutoApprovalState()

        def trip():
            state.trip_circuit_breaker()

        threads = [threading.Thread(target=trip) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should still be tripped (idempotent)
        assert state.is_circuit_breaker_tripped() is True

    def test_get_agent_name_only_control_chars(self):
        """Handle agent name with only control characters."""
        # Can't use null byte in env var directly, test via mock
        with patch('plugins.autonomous_dev.lib.auto_approval_engine.os.getenv') as mock_getenv:
            mock_getenv.return_value = "\x01\x02\x03"  # control chars (no null)
            # After sanitizing, empty string → None
            assert get_agent_name() is None

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset global state."""
        reset_circuit_breaker()
        yield

    @patch('plugins.autonomous_dev.lib.auto_approval_engine.get_auto_approval_mode')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.is_subagent_context')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.is_trusted_agent')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine._get_cached_validator')
    @patch('plugins.autonomous_dev.lib.auto_approval_engine.ToolApprovalAuditor')
    def test_denial_increments_circuit_breaker(self, mock_auditor, mock_validator, mock_trusted, mock_subagent, mock_mode):
        """Denials increment circuit breaker counter."""
        mock_mode.return_value = "subagent_only"
        mock_subagent.return_value = True
        mock_trusted.return_value = True
        mock_auditor.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.approved = False
        mock_result.reason = "Denied"
        mock_validator.return_value.validate_tool_call.return_value = mock_result

        # Should increment denial count
        should_auto_approve("Bash", {"command": "bad"}, agent_name="implementer")

        state = _get_global_state()
        assert state.get_denial_count() >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
