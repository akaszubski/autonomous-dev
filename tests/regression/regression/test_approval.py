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

# Import tool_validator - skip if not available
try:
    from tool_validator import (
        ToolValidator, validate_bash_command, validate_file_path,
        CommandInjectionError, PathTraversalError,
    )
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
