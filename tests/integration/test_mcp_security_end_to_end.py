#!/usr/bin/env python3
"""
Integration tests for MCP Security End-to-End (TDD Red Phase).

Tests for complete MCP security workflow with PreToolUse hook (Issue #95).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test end-to-end filesystem read operations (allowed/denied)
- Test end-to-end filesystem write operations (allowed/denied)
- Test end-to-end shell command execution (allowed/denied)
- Test end-to-end network access (allowed/denied)
- Test hook integration with MCP server
- Test audit logging for all operations
- Test policy reload on file change

Date: 2025-12-07
Issue: #95 (MCP Server Security - Permission Whitelist System)
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

# Add lib directory for dependencies
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
    from mcp_security_enforcer import (
        on_pre_tool_use,
        MCPSecurityEnforcer,
    )
    from mcp_permission_validator import MCPPermissionValidator
    from mcp_profile_manager import MCPProfileManager, ProfileType
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestFilesystemReadEndToEnd:
    """Test end-to-end filesystem read operations."""

    def test_mcp_filesystem_read_allowed_src_file(self):
        """Test MCP filesystem:read allows reading src/main.py."""
        # Setup: Create temporary project with src/main.py
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            src_dir = project_dir / "src"
            src_dir.mkdir()
            main_file = src_dir / "main.py"
            main_file.write_text("print('hello')")

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "filesystem:read",
                "arguments": {
                    "path": str(main_file)
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:read",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation approved
            assert result["approved"] is True
            assert "reason" not in result or result["reason"] is None

    def test_mcp_filesystem_read_denied_env_file(self):
        """Test MCP filesystem:read denies reading .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            env_file = project_dir / ".env"
            env_file.write_text("API_KEY=secret123")

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "filesystem:read",
                "arguments": {
                    "path": str(env_file)
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:read",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert ".env" in result["reason"].lower()

    def test_mcp_filesystem_read_denied_git_config(self):
        """Test MCP filesystem:read denies reading .git/config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            git_dir = project_dir / ".git"
            git_dir.mkdir()
            config_file = git_dir / "config"
            config_file.write_text("[user]\nemail=test@example.com")

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "filesystem:read",
                "arguments": {
                    "path": str(config_file)
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:read",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert ".git" in result["reason"].lower() or "config" in result["reason"].lower()


class TestFilesystemWriteEndToEnd:
    """Test end-to-end filesystem write operations."""

    def test_mcp_filesystem_write_allowed_src_file(self):
        """Test MCP filesystem:write allows writing to src/new_file.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            src_dir = project_dir / "src"
            src_dir.mkdir()

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            new_file = src_dir / "new_file.py"
            tool_call = {
                "tool": "filesystem:write",
                "arguments": {
                    "path": str(new_file),
                    "content": "print('new')"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:write",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation approved
            assert result["approved"] is True

    def test_mcp_filesystem_write_denied_outside_project(self):
        """Test MCP filesystem:write denies writing outside project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call to write outside project
            external_file = Path(tmpdir) / "external.txt"
            tool_call = {
                "tool": "filesystem:write",
                "arguments": {
                    "path": str(external_file),
                    "content": "malicious"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:write",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert "outside" in result["reason"].lower() or "project" in result["reason"].lower()

    def test_mcp_filesystem_write_denied_env_file(self):
        """Test MCP filesystem:write denies overwriting .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            env_file = project_dir / ".env"
            env_file.write_text("API_KEY=original")

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call to overwrite .env
            tool_call = {
                "tool": "filesystem:write",
                "arguments": {
                    "path": str(env_file),
                    "content": "API_KEY=stolen"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:write",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert ".env" in result["reason"].lower()


class TestShellExecutionEndToEnd:
    """Test end-to-end shell command execution."""

    def test_mcp_shell_execute_allowed_pytest(self):
        """Test MCP shell:execute allows running pytest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "shell:execute",
                "arguments": {
                    "command": "pytest tests/"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="shell:execute",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation approved
            assert result["approved"] is True

    def test_mcp_shell_execute_allowed_git_status(self):
        """Test MCP shell:execute allows running git status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "shell:execute",
                "arguments": {
                    "command": "git status"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="shell:execute",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation approved
            assert result["approved"] is True

    def test_mcp_shell_execute_denied_rm_rf(self):
        """Test MCP shell:execute denies destructive rm -rf command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "shell:execute",
                "arguments": {
                    "command": "rm -rf /"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="shell:execute",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert "destructive" in result["reason"].lower() or "dangerous" in result["reason"].lower()

    def test_mcp_shell_execute_denied_command_injection(self):
        """Test MCP shell:execute denies command injection attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call with injection
            tool_call = {
                "tool": "shell:execute",
                "arguments": {
                    "command": "git status; rm -rf /"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="shell:execute",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert "injection" in result["reason"].lower()


class TestNetworkAccessEndToEnd:
    """Test end-to-end network access operations."""

    def test_mcp_network_access_allowed_github_api(self):
        """Test MCP network:access allows GitHub API calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "network:request",
                "arguments": {
                    "url": "https://api.github.com/repos/test/repo"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="network:request",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation approved
            assert result["approved"] is True

    def test_mcp_network_access_denied_localhost(self):
        """Test MCP network:access denies localhost connections (SSRF)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call to localhost
            tool_call = {
                "tool": "network:request",
                "arguments": {
                    "url": "http://127.0.0.1:8080/admin"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="network:request",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert "localhost" in result["reason"].lower() or "127.0.0.1" in result["reason"].lower()

    def test_mcp_network_access_denied_metadata_service(self):
        """Test MCP network:access denies AWS metadata service (169.254.169.254)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call to metadata service
            tool_call = {
                "tool": "network:request",
                "arguments": {
                    "url": "http://169.254.169.254/latest/meta-data/"
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="network:request",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Operation denied
            assert result["approved"] is False
            assert "metadata" in result["reason"].lower() or "169.254" in result["reason"].lower()


class TestAuditLogging:
    """Test audit logging for MCP operations."""

    @patch('mcp_security_enforcer.MCPAuditLogger')
    def test_audit_log_approved_operation(self, mock_logger):
        """Test audit logging records approved operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            src_dir = project_dir / "src"
            src_dir.mkdir()

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call
            tool_call = {
                "tool": "filesystem:read",
                "arguments": {
                    "path": str(src_dir / "main.py")
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:read",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Audit log called
            mock_logger.return_value.log_operation.assert_called_once()
            call_args = mock_logger.return_value.log_operation.call_args
            assert call_args[1]["approved"] is True

    @patch('mcp_security_enforcer.MCPAuditLogger')
    def test_audit_log_denied_operation(self, mock_logger):
        """Test audit logging records denied operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Simulate MCP tool call (denied)
            tool_call = {
                "tool": "filesystem:read",
                "arguments": {
                    "path": str(project_dir / ".env")
                }
            }

            # Execute hook
            result = on_pre_tool_use(
                tool_name="filesystem:read",
                arguments=tool_call["arguments"],
                context={"project_root": str(project_dir)}
            )

            # Verify: Audit log called with denial
            mock_logger.return_value.log_operation.assert_called_once()
            call_args = mock_logger.return_value.log_operation.call_args
            assert call_args[1]["approved"] is False
            assert "reason" in call_args[1]


class TestPolicyReload:
    """Test policy reload on configuration change."""

    def test_policy_reload_on_file_change(self):
        """Test security policy reloads when .mcp/security_policy.json changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            src_dir = project_dir / "src"
            src_dir.mkdir()

            # Create initial security policy (restrictive)
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.PRODUCTION)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Create enforcer (should load restrictive policy)
            enforcer = MCPSecurityEnforcer(project_root=str(project_dir))

            # Verify initial policy is restrictive
            result = enforcer.validate_operation("filesystem:write", {"path": str(src_dir / "new.py")})
            assert result["approved"] is False  # Production profile restricts writes

            # Update policy to development (permissive)
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Reload policy
            enforcer.reload_policy()

            # Verify policy updated
            result = enforcer.validate_operation("filesystem:write", {"path": str(src_dir / "new.py")})
            assert result["approved"] is True  # Development profile allows writes


class TestHookIntegration:
    """Test PreToolUse hook integration."""

    def test_hook_registered_in_lifecycle(self):
        """Test mcp_security_enforcer hook is registered for PreToolUse lifecycle."""
        # This test verifies hook registration (metadata check)
        from mcp_security_enforcer import HOOK_METADATA

        assert HOOK_METADATA["lifecycle"] == "PreToolUse"
        assert HOOK_METADATA["description"] is not None

    def test_hook_receives_correct_arguments(self):
        """Test hook receives tool_name and arguments from MCP server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Call hook with expected signature
            result = on_pre_tool_use(
                tool_name="filesystem:read",
                arguments={"path": "/project/src/main.py"},
                context={"project_root": str(project_dir)}
            )

            # Verify hook processes arguments
            assert "approved" in result
            assert isinstance(result["approved"], bool)

    def test_hook_returns_approval_result(self):
        """Test hook returns approval result with approved boolean and reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create security policy
            policy_path = project_dir / ".mcp" / "security_policy.json"
            policy_path.parent.mkdir()
            policy = MCPProfileManager().create_profile(ProfileType.DEVELOPMENT)
            with open(policy_path, 'w') as f:
                json.dump(policy, f)

            # Test denied operation
            result = on_pre_tool_use(
                tool_name="filesystem:read",
                arguments={"path": str(project_dir / ".env")},
                context={"project_root": str(project_dir)}
            )

            # Verify result structure
            assert "approved" in result
            assert result["approved"] is False
            assert "reason" in result
            assert isinstance(result["reason"], str)
