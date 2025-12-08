#!/usr/bin/env python3
"""
MCP Security Enforcer Hook - PreToolUse hook for MCP server security

This hook intercepts MCP server tool calls and validates permissions before
execution to prevent security vulnerabilities:
- CWE-22: Path Traversal
- CWE-59: Improper Link Resolution
- CWE-78: OS Command Injection
- SSRF: Server-Side Request Forgery

Hook Type: PreToolUse
Trigger: Before any MCP tool is executed (mcp__* pattern)
Action: Validate operation against security policy

Security Policy:
- Loaded from .mcp/security_policy.json
- Fallback to development profile if not found
- Validates filesystem, shell, network, environment operations

Error Handling:
- Graceful degradation: Errors default to manual approval (safe failure)
- Policy not found: Falls back to development profile
- Validation errors: Return denial with clear reason

Usage:
    # Hook is automatically invoked by Claude Code for MCP tools
    # Returns {"approved": True/False, "reason": "..."}

Date: 2025-12-07
Issue: #95 (MCP Server Security - Permission Whitelist System)
Agent: implementer
Phase: TDD Green (implementation to make tests pass)
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add lib directory to path for imports
LIB_DIR = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

try:
    from mcp_permission_validator import MCPPermissionValidator
    from security_utils import audit_log
except ImportError:
    # Graceful degradation if imports fail
    MCPPermissionValidator = None
    audit_log = None


def _get_project_root() -> str:
    """Detect project root directory.

    Returns:
        Project root path as string
    """
    # Try environment variable first
    project_root = os.getenv("PROJECT_ROOT", "")
    if project_root and Path(project_root).exists():
        return project_root

    # Fallback to current working directory
    return os.getcwd()


def _detect_policy_path() -> str:
    """Auto-detect security policy file path.

    Returns:
        Path to policy file, or None if not found
    """
    project_root = _get_project_root()
    policy_file = Path(project_root) / ".mcp" / "security_policy.json"

    if policy_file.exists():
        return str(policy_file)

    return None


def _log_operation(event_type: str, approved: bool, reason: str = None, **kwargs) -> None:
    """Log MCP operation to audit log.

    Args:
        event_type: Type of operation (mcp_fs_read, mcp_fs_write, etc.)
        approved: Whether operation was approved
        reason: Reason for approval/denial
        **kwargs: Additional context
    """
    if audit_log is None:
        return  # Graceful degradation if audit_log not available

    status = "approved" if approved else "denied"
    context = {k: v for k, v in kwargs.items()}
    if reason:
        context["reason"] = reason

    try:
        audit_log(event_type, status, context)
    except Exception:
        pass  # Silent failure - don't block operations due to logging errors


class MCPAuditLogger:
    """Audit logger for MCP security events (legacy compatibility).

    This class provides backward compatibility for tests and external code.
    For new code, use _log_operation() function directly.
    """

    def log_operation(self, **kwargs) -> None:
        """Log MCP operation.

        Args:
            **kwargs: Operation details (approved, reason, etc.)
        """
        event_type = kwargs.get("event_type", "mcp_operation")
        approved = kwargs.get("approved", False)
        reason = kwargs.get("reason")

        # Remove internal keys before passing to _log_operation
        context_kwargs = {k: v for k, v in kwargs.items()
                         if k not in ("event_type", "approved", "reason")}

        _log_operation(event_type, approved, reason, **context_kwargs)


class MCPSecurityEnforcer:
    """MCP security enforcer for PreToolUse hook (legacy compatibility).

    This class provides backward compatibility for tests and external code
    that expects the MCPSecurityEnforcer interface.

    For new code, use the on_pre_tool_use() function directly.
    """

    def __init__(self, policy_path: str = None, project_root: str = None):
        """Initialize security enforcer.

        Args:
            policy_path: Path to security policy JSON file
            project_root: Project root directory
        """
        self.policy_path = policy_path or _detect_policy_path()
        self.project_root = project_root or _get_project_root()

        # Create validator
        if MCPPermissionValidator is not None:
            self.validator = MCPPermissionValidator(policy_path=self.policy_path)
            self.validator.project_root = self.project_root
        else:
            self.validator = None

    def validate_operation(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate operation against security policy (legacy interface).

        Args:
            tool_name: MCP tool name (e.g., "filesystem:read")
            arguments: Tool arguments

        Returns:
            Dictionary with "approved" boolean and optional "reason" string
        """
        # Map legacy tool names to mcp__* format
        tool_mapping = {
            "filesystem:read": "mcp__filesystem__read",
            "filesystem:write": "mcp__filesystem__write",
            "fs:read": "mcp__filesystem__read",
            "fs:write": "mcp__filesystem__write",
            "shell:execute": "mcp__shell__execute",
            "shell_execute": "mcp__shell__execute",
            "network:access": "mcp__network__access",
            "network:request": "mcp__network__access",
            "network_access": "mcp__network__access",
            "env:access": "mcp__env__access",
            "env_access": "mcp__env__access",
        }

        mcp_tool_name = tool_mapping.get(tool_name, tool_name)
        return on_pre_tool_use(mcp_tool_name, arguments)

    def reload_policy(self) -> None:
        """Reload security policy from file."""
        # Re-detect policy path from project root
        if self.project_root:
            policy_file = Path(self.project_root) / ".mcp" / "security_policy.json"
            if policy_file.exists():
                self.policy_path = str(policy_file)
            else:
                self.policy_path = None
        else:
            self.policy_path = _detect_policy_path()

        # Recreate validator with new policy
        if MCPPermissionValidator is not None:
            self.validator = MCPPermissionValidator(policy_path=self.policy_path)
            self.validator.project_root = self.project_root


def on_pre_tool_use(
    tool: str = None,
    parameters: Dict[str, Any] = None,
    tool_name: str = None,
    arguments: Dict[str, Any] = None,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """PreToolUse lifecycle hook for MCP security enforcement.

    This hook is called by Claude Code before each MCP tool execution.
    It validates the operation against security policy and returns approval/denial.

    Args:
        tool: Tool name (e.g., "mcp__filesystem__read", "Bash", "Read", etc.)
        parameters: Tool parameters dictionary
        tool_name: Legacy parameter name (backward compatibility)
        arguments: Legacy parameter name (backward compatibility)
        context: Additional context (project_root, etc.)

    Returns:
        Dictionary with:
        - approved: bool (True = auto-approve, False = manual approval)
        - reason: str (human-readable explanation)

    Error Handling:
        - Graceful degradation: Any error results in manual approval
        - Missing imports: Returns manual approval
        - Invalid parameters: Returns denial with clear reason
    """
    # Support both old (tool_name, arguments) and new (tool, parameters) signatures
    if tool_name is not None:
        tool = tool_name
    if arguments is not None:
        parameters = arguments

    # Validate inputs
    if tool is None or parameters is None:
        return {
            "approved": False,
            "reason": "Missing tool or parameters argument"
        }

    # Handle context parameter for project_root override
    project_root = _get_project_root()
    if context and "project_root" in context:
        project_root = context["project_root"]

    try:
        # Graceful degradation if imports failed
        if MCPPermissionValidator is None:
            return {
                "approved": False,
                "reason": "MCP security libraries not available (manual approval required)"
            }

        # Map legacy tool names (filesystem:read) to new format (mcp__filesystem__read)
        tool_mapping = {
            "filesystem:read": "mcp__filesystem__read",
            "filesystem:write": "mcp__filesystem__write",
            "fs:read": "mcp__filesystem__read",
            "fs:write": "mcp__filesystem__write",
            "shell:execute": "mcp__shell__execute",
            "shell_execute": "mcp__shell__execute",
            "network:access": "mcp__network__access",
            "network:request": "mcp__network__access",
            "network_access": "mcp__network__access",
            "env:access": "mcp__env__access",
            "env_access": "mcp__env__access",
        }

        # Apply mapping if needed
        if tool in tool_mapping:
            tool = tool_mapping[tool]

        # Only validate MCP tools (mcp__* pattern)
        # Let non-MCP tools (Bash, Read, Write, etc.) pass through
        if not tool.startswith("mcp__"):
            return {"approved": True, "reason": "Non-MCP tool (no validation needed)"}

        # Parse MCP tool name (format: mcp__category__operation)
        # Examples: mcp__filesystem__read, mcp__shell__execute
        parts = tool.split("__")
        if len(parts) < 3:
            return {
                "approved": False,
                "reason": f"Invalid MCP tool format: {tool} (expected mcp__category__operation)"
            }

        category = parts[1]  # filesystem, shell, network, env
        operation = parts[2]  # read, write, execute, access

        # Auto-detect policy path from project root
        if context and "project_root" in context:
            policy_file = Path(context["project_root"]) / ".mcp" / "security_policy.json"
            policy_path = str(policy_file) if policy_file.exists() else None
        else:
            policy_path = _detect_policy_path()

        # Create validator
        validator = MCPPermissionValidator(policy_path=policy_path)
        validator.project_root = project_root

        # Route to appropriate validation method
        result = None
        if category == "filesystem" or category == "fs":
            if operation == "read":
                path = parameters.get("path")
                if not path:
                    return {"approved": False, "reason": "Missing path parameter"}
                result = validator.validate_fs_read(path)
                _log_operation("mcp_fs_read", result.approved, result.reason, path=path)

            elif operation == "write":
                path = parameters.get("path")
                if not path:
                    return {"approved": False, "reason": "Missing path parameter"}
                result = validator.validate_fs_write(path)
                _log_operation("mcp_fs_write", result.approved, result.reason, path=path)

        elif category == "shell":
            command = parameters.get("command")
            if not command:
                return {"approved": False, "reason": "Missing command parameter"}
            result = validator.validate_shell_execute(command)
            _log_operation("mcp_shell_execute", result.approved, result.reason, command=command)

        elif category == "network":
            url = parameters.get("url")
            if not url:
                return {"approved": False, "reason": "Missing url parameter"}
            result = validator.validate_network_access(url)
            _log_operation("mcp_network_access", result.approved, result.reason, url=url)

        elif category == "env":
            var_name = parameters.get("var_name") or parameters.get("name")
            if not var_name:
                return {"approved": False, "reason": "Missing var_name parameter"}
            result = validator.validate_env_access(var_name)
            _log_operation("mcp_env_access", result.approved, result.reason, var_name=var_name)

        else:
            # Unknown category - deny by default
            return {
                "approved": False,
                "reason": f"Unknown MCP tool category: {category}"
            }

        # Return validation result
        if result is None:
            return {
                "approved": False,
                "reason": f"No validation handler for {category}:{operation}"
            }

        return result.to_dict()

    except Exception as e:
        # Graceful degradation - deny on error
        _log_operation(
            "mcp_validation_error",
            approved=False,
            reason=f"Validation error: {e}",
            tool=tool
        )

        return {
            "approved": False,
            "reason": f"MCP security validation error (defaulting to manual approval): {e}"
        }


if __name__ == "__main__":
    # Test hook with example operations
    print("Testing MCP Security Enforcer Hook")
    print("=" * 60)

    # Test filesystem read
    result = on_pre_tool_use(
        tool="mcp__filesystem__read",
        parameters={"path": "/project/src/main.py"}
    )
    print(f"fs:read /project/src/main.py: {result}")

    # Test filesystem write to .env (should deny)
    result = on_pre_tool_use(
        tool="mcp__filesystem__write",
        parameters={"path": "/project/.env"}
    )
    print(f"fs:write /project/.env: {result}")

    # Test shell command injection (should deny)
    result = on_pre_tool_use(
        tool="mcp__shell__execute",
        parameters={"command": "git status; rm -rf /"}
    )
    print(f"shell:execute 'git status; rm -rf /': {result}")

    # Test network access to localhost (should deny)
    result = on_pre_tool_use(
        tool="mcp__network__access",
        parameters={"url": "http://127.0.0.1:8080/admin"}
    )
    print(f"network:access http://127.0.0.1:8080/admin: {result}")

    # Test non-MCP tool (should pass through)
    result = on_pre_tool_use(
        tool="Bash",
        parameters={"command": "ls"}
    )
    print(f"Bash ls: {result}")

    print("=" * 60)
    print("Hook testing complete")


# Hook metadata for Claude Code plugin system
HOOK_METADATA = {
    "lifecycle": "PreToolUse",
    "description": "Validate MCP tool operations against security policy",
    "version": "1.0.0",
    "tool_pattern": "mcp__*"
}
