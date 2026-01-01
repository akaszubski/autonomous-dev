#!/usr/bin/env python3
"""
Consolidated Approval Tests (TDD Red Phase)

Tests for MCP tool auto-approval system (Issue #73):
- Subagent context detection
- Agent whitelist checking
- User consent management
- Policy loading and caching
- Circuit breaker logic
- Command injection prevention (CWE-78)
- Path traversal prevention (CWE-22)
- Privilege escalation blocking

Date: 2025-11-15 (consolidated 2025-12-16)
Issue: #73 (MCP Auto-Approval for Subagent Tool Calls)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Portable path detection (works from any test location)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        PROJECT_ROOT = current
        break
    current = current.parent
else:
    PROJECT_ROOT = Path.cwd()

# Add lib to path
lib_path = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))
hooks_path = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(hooks_path))

# Import auto_approval_engine - skip if not available
try:
    from auto_approval_engine import (
        on_pre_tool_use, should_auto_approve, is_subagent_context,
        get_agent_name, is_trusted_agent, check_user_consent_cached as check_user_consent,
        load_and_cache_policy, increment_denial_count,
        should_trip_circuit_breaker, reset_circuit_breaker,
        AutoApprovalState,
    )
    AUTO_APPROVE_AVAILABLE = True
except ImportError:
    AUTO_APPROVE_AVAILABLE = False

# Import tool_validator - skip if not available
try:
    from tool_validator import (
        ToolValidator, validate_bash_command, validate_file_path,
        CommandInjectionError, PathTraversalError,
    )
    from tool_approval_audit import sanitize_log_input
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_policy():
    """Create mock policy."""
    return {
        "agents": {"trusted": ["researcher", "planner", "test-master", "implementer"], "restricted": ["reviewer"]},
        "bash": {"whitelist": ["pytest*", "ls*"], "blacklist": ["rm -rf*", "sudo*"]},
        "file_paths": {"whitelist": ["/Users/*/Documents/GitHub/*"], "blacklist": ["/etc/*", "/root/*"]}
    }


@pytest.fixture
def temp_policy_file(tmp_path, mock_policy):
    """Create temporary policy file."""
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(mock_policy))
    return policy_file


@pytest.fixture
def temp_state_file(tmp_path):
    """Create temporary user state file."""
    return tmp_path / "user_state.json"


@pytest.fixture
def validator(temp_policy_file):
    """Create ToolValidator instance."""
    return ToolValidator(policy_file=temp_policy_file)


# =============================================================================
# Subagent Context Detection Tests
# =============================================================================

@pytest.mark.skipif(not AUTO_APPROVE_AVAILABLE, reason="auto_approval_engine not available")
class TestSubagentContextDetection:
    """Test subagent context detection via CLAUDE_AGENT_NAME."""

    def test_is_subagent_context_true(self):
        """Test subagent context detected when env var is set."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "researcher"}):
            assert is_subagent_context() is True

    def test_is_subagent_context_false(self):
        """Test subagent context not detected when env var is unset."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_subagent_context() is False

    def test_get_agent_name_returns_name(self):
        """Test get_agent_name returns agent name from env var."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "planner"}):
            assert get_agent_name() == "planner"

    def test_get_agent_name_strips_whitespace(self):
        """Test get_agent_name strips whitespace from agent name."""
        with patch.dict(os.environ, {"CLAUDE_AGENT_NAME": "  implementer  "}):
            assert get_agent_name() == "implementer"


# =============================================================================
# Agent Whitelist Tests
# =============================================================================

@pytest.mark.skipif(not AUTO_APPROVE_AVAILABLE, reason="auto_approval_engine not available")
class TestAgentWhitelistChecking:
    """Test agent whitelist checking (trusted vs untrusted)."""

    def test_is_trusted_agent_true_for_trusted(self, mock_policy):
        """Test is_trusted_agent returns True for trusted agents."""
        with patch("auto_approval_engine.load_and_cache_policy", return_value=mock_policy):
            assert is_trusted_agent("researcher") is True

    def test_is_trusted_agent_false_for_restricted(self, mock_policy):
        """Test is_trusted_agent returns False for restricted agents."""
        with patch("auto_approval_engine.load_and_cache_policy", return_value=mock_policy):
            assert is_trusted_agent("reviewer") is False

    def test_is_trusted_agent_false_for_unknown(self, mock_policy):
        """Test is_trusted_agent returns False for unknown agents."""
        with patch("auto_approval_engine.load_and_cache_policy", return_value=mock_policy):
            assert is_trusted_agent("unknown-agent") is False


# =============================================================================
# User Consent Tests
# =============================================================================

@pytest.mark.skipif(not AUTO_APPROVE_AVAILABLE, reason="auto_approval_engine not available")
class TestUserConsentChecking:
    """Test user consent checking for auto-approval."""

    @pytest.mark.skip(reason="Requires mocking user_state_manager internals - needs refactor")
    def test_check_user_consent_enabled(self, temp_state_file):
        """Test check_user_consent returns True when enabled."""
        state = {"preferences": {"mcp_auto_approve_enabled": True}}
        temp_state_file.write_text(json.dumps(state))

        with patch("auto_approval_engine.DEFAULT_STATE_FILE", temp_state_file):
            assert check_user_consent() is True

    @pytest.mark.skip(reason="Requires mocking user_state_manager internals - needs refactor")
    def test_check_user_consent_disabled(self, temp_state_file):
        """Test check_user_consent returns False when disabled."""
        state = {"preferences": {"mcp_auto_approve_enabled": False}}
        temp_state_file.write_text(json.dumps(state))

        with patch("auto_approval_engine.DEFAULT_STATE_FILE", temp_state_file):
            assert check_user_consent() is False

    def test_check_user_consent_env_var_override(self, temp_state_file):
        """Test check_user_consent respects MCP_AUTO_APPROVE env var."""
        state = {"preferences": {"mcp_auto_approve_enabled": False}}
        temp_state_file.write_text(json.dumps(state))

        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "true"}):
            with patch("auto_approval_engine.DEFAULT_STATE_FILE", temp_state_file):
                assert check_user_consent() is True


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

@pytest.mark.skipif(not AUTO_APPROVE_AVAILABLE, reason="auto_approval_engine not available")
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
        assert should_trip_circuit_breaker(state) is False

    def test_should_trip_circuit_breaker_true_at_threshold(self, state):
        """Test should_trip_circuit_breaker returns True at threshold."""
        state.denial_count = 10
        assert should_trip_circuit_breaker(state) is True

    def test_reset_circuit_breaker_resets_count(self, state):
        """Test reset_circuit_breaker resets denial count."""
        state.denial_count = 10
        reset_circuit_breaker(state)
        assert state.denial_count == 0


# =============================================================================
# Command Injection Prevention Tests (CWE-78)
# =============================================================================

@pytest.mark.skipif(not VALIDATOR_AVAILABLE, reason="tool_validator not available")
class TestCommandInjectionAttacks:
    """Test command injection attack prevention (CWE-78)."""

    def test_semicolon_command_injection_blocked(self, validator):
        """Test semicolon command injection is blocked."""
        result = validator.validate_bash_command("pytest tests/; rm -rf /")
        assert result.approved is False
        assert result.security_risk is True

    def test_ampersand_command_injection_blocked(self, validator):
        """Test ampersand command injection is blocked."""
        result = validator.validate_bash_command("ls && rm -rf /")
        assert result.approved is False
        assert result.security_risk is True

    def test_pipe_command_injection_blocked(self, validator):
        """Test pipe command injection is blocked."""
        result = validator.validate_bash_command("cat file.txt | bash")
        assert result.approved is False
        assert result.security_risk is True

    def test_backtick_command_substitution_blocked(self, validator):
        """Test backtick command substitution is blocked."""
        result = validator.validate_bash_command("echo `rm -rf /`")
        assert result.approved is False
        assert result.security_risk is True

    def test_dollar_paren_command_substitution_blocked(self, validator):
        """Test $(command) substitution is blocked."""
        result = validator.validate_bash_command("echo $(rm -rf /)")
        assert result.approved is False
        assert result.security_risk is True

    def test_newline_command_injection_blocked(self, validator):
        """Test newline command injection is blocked."""
        result = validator.validate_bash_command("pytest tests/\nrm -rf /")
        assert result.approved is False
        assert result.security_risk is True


# =============================================================================
# Path Traversal Prevention Tests (CWE-22)
# =============================================================================

@pytest.mark.skipif(not VALIDATOR_AVAILABLE, reason="tool_validator not available")
class TestPathTraversalAttacks:
    """Test path traversal attack prevention (CWE-22)."""

    def test_dotdot_path_traversal_blocked(self, validator):
        """Test ../ path traversal is blocked."""
        result = validator.validate_file_path("/Users/user/Documents/GitHub/repo/../../../etc/passwd")
        assert result.approved is False
        assert result.security_risk is True

    def test_relative_path_traversal_blocked(self, validator):
        """Test relative path traversal is blocked."""
        result = validator.validate_file_path("../../../../etc/passwd")
        assert result.approved is False
        assert result.security_risk is True

    def test_url_encoded_traversal_blocked(self, validator):
        """Test URL-encoded path traversal is blocked."""
        result = validator.validate_file_path("/Users/user/%2e%2e/%2e%2e/etc/passwd")
        assert result.approved is False
        assert result.security_risk is True


# =============================================================================
# Privilege Escalation Prevention Tests
# =============================================================================

@pytest.mark.skipif(not VALIDATOR_AVAILABLE, reason="tool_validator not available")
class TestPrivilegeEscalationAttempts:
    """Test privilege escalation attempts."""

    def test_sudo_privilege_escalation_blocked(self, validator):
        """Test sudo privilege escalation is blocked."""
        result = validator.validate_bash_command("sudo bash")
        assert result.approved is False
        assert result.security_risk is True

    def test_su_privilege_escalation_blocked(self, validator):
        """Test su privilege escalation is blocked."""
        result = validator.validate_bash_command("su root")
        assert result.approved is False


# =============================================================================
# Log Injection Prevention Tests (CWE-117)
# =============================================================================

@pytest.mark.skipif(not VALIDATOR_AVAILABLE, reason="tool_approval_audit not available")
class TestLogInjectionAttacks:
    """Test log injection attack prevention (CWE-117)."""

    def test_newline_log_injection_blocked(self):
        """Test newline log injection is sanitized."""
        malicious_input = 'researcher\n{"event": "fake_approval"}'
        sanitized = sanitize_log_input(malicious_input)
        assert "\n" not in sanitized

    def test_carriage_return_log_injection_blocked(self):
        """Test carriage return log injection is sanitized."""
        malicious_input = 'researcher\r{"event": "fake_approval"}'
        sanitized = sanitize_log_input(malicious_input)
        assert "\r" not in sanitized

    def test_control_char_injection_blocked(self):
        """Test control character injection is sanitized."""
        malicious_input = 'researcher\x00\x01\x02{"event": "fake"}'
        sanitized = sanitize_log_input(malicious_input)
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized


# =============================================================================
# Policy Caching Tests
# =============================================================================

@pytest.mark.skipif(not VALIDATOR_AVAILABLE, reason="tool_validator not available")
class TestPolicyCaching:
    """Test policy caching prevents tampering."""

    def test_modified_policy_file_uses_cache(self, temp_policy_file):
        """Test modified policy file uses cached version."""
        validator = ToolValidator(policy_file=temp_policy_file)

        # Tamper with policy file
        tampered_policy = json.loads(temp_policy_file.read_text())
        tampered_policy["bash"]["whitelist"].append("rm -rf*")
        temp_policy_file.write_text(json.dumps(tampered_policy))

        # Should use cached policy
        result = validator.validate_bash_command("rm -rf /")
        assert result.approved is False


# =============================================================================
# Hook Function Tests
# =============================================================================

@pytest.mark.skipif(not AUTO_APPROVE_AVAILABLE, reason="auto_approval_engine not available")
class TestOnPreToolUseHook:
    """Test on_pre_tool_use hook function."""

    def test_on_pre_tool_use_approves_valid_call(self):
        """Test on_pre_tool_use approves valid tool call."""
        with patch("auto_approval_engine.should_auto_approve", return_value=(True, "Auto-approved")):
            with patch("auto_approval_engine.ToolApprovalAuditor"):
                result = on_pre_tool_use("Bash", {"command": "pytest tests/"})
                assert result["approved"] is True

    def test_on_pre_tool_use_denies_invalid_call(self):
        """Test on_pre_tool_use denies invalid tool call."""
        with patch("auto_approval_engine.should_auto_approve", return_value=(False, "Denied")):
            with patch("auto_approval_engine.ToolApprovalAuditor"):
                result = on_pre_tool_use("Bash", {"command": "pytest tests/"})
                assert result["approved"] is False

    def test_on_pre_tool_use_handles_errors_gracefully(self):
        """Test on_pre_tool_use handles errors gracefully (fails open)."""
        with patch("auto_approval_engine.should_auto_approve", side_effect=Exception("Test error")):
            result = on_pre_tool_use("Bash", {"command": "pytest tests/"})
            assert result["approved"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
