#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Unified PreToolUse Hook - Consolidated Permission & Security Validation

This hook consolidates four PreToolUse validators into a single dispatcher:
0. Sandbox Enforcer (sandbox_enforcer.py) - Command classification & sandboxing (Issue #171)
1. MCP Security Validator (pre_tool_use.py) - Path traversal, injection, SSRF protection
2. Agent Authorization (enforce_implementation_workflow.py) - Pipeline agent detection
3. Batch Permission Approver (batch_permission_approver.py) - Permission batching

Decision Logic:
- If ANY validator returns "deny" → output "deny" (block operation)
- If ALL validators return "allow" → output "allow" (approve operation)
- Otherwise → output "ask" (prompt user)

Layer Execution Order (short-circuit on deny):
0. Layer 0 (Sandbox): Command classification (SAFE → auto-approve, BLOCKED → deny, NEEDS_APPROVAL → continue)
1. Layer 1 (MCP Security): Path traversal, injection, SSRF checks
2. Layer 2 (Agent Auth): Pipeline agent detection
3. Layer 3 (Batch Permission): Permission batching

Environment Variables:
- SANDBOX_ENABLED: Enable/disable sandbox layer (default: false for opt-in)
- SANDBOX_PROFILE: Sandbox profile (default: development)
- PRE_TOOL_MCP_SECURITY: Enable/disable MCP security (default: true)
- PRE_TOOL_AGENT_AUTH: Enable/disable agent authorization (default: true)
- PRE_TOOL_BATCH_PERMISSION: Enable/disable batch permission (default: false)
- MCP_AUTO_APPROVE: Enable/disable auto-approval (default: false)

Input (stdin):
{
  "tool_name": "Bash",
  "tool_input": {"command": "pytest tests/"}
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Combined validator reasons"
  }
}

Exit code: 0 (always - let Claude Code process the decision)

Date: 2026-01-02
Issue: GitHub #171 (Sandboxing for reduced permission prompts)
Agent: implementer
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, Tuple, List


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

def find_lib_directory(hook_path: Path) -> Path | None:
    """
    Find lib directory dynamically (Issue #113).

    Checks multiple locations in order:
    1. Development: plugins/autonomous-dev/lib (relative to hook)
    2. Local install: ~/.claude/lib
    3. Marketplace: ~/.claude/plugins/autonomous-dev/lib

    Args:
        hook_path: Path to this hook script

    Returns:
        Path to lib directory if found, None otherwise (graceful failure)
    """
    # Try development location first
    dev_lib = hook_path.parent.parent / "lib"
    if dev_lib.exists() and dev_lib.is_dir():
        return dev_lib

    # Try local install
    home = Path.home()
    local_lib = home / ".claude" / "lib"
    if local_lib.exists() and local_lib.is_dir():
        return local_lib

    # Try marketplace location
    marketplace_lib = home / ".claude" / "plugins" / "autonomous-dev" / "lib"
    if marketplace_lib.exists() and marketplace_lib.is_dir():
        return marketplace_lib

    return None


# Add lib directory to path dynamically
LIB_DIR = find_lib_directory(Path(__file__))
if LIB_DIR:
    if not is_running_under_uv():
        sys.path.insert(0, str(LIB_DIR))


def load_env():
    """Load .env file from project root if it exists."""
    env_file = Path(os.getcwd()) / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass  # Silently skip


# Agents authorized for code changes (pipeline agents)
# Issue #147: Consolidated to only active agents that write code/tests/docs
PIPELINE_AGENTS = [
    'implementer',
    'test-master',
    'doc-master',
]


def validate_sandbox_layer(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate sandbox layer (Layer 0) - command classification and sandboxing.

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if sandbox is enabled
    enabled = os.getenv("SANDBOX_ENABLED", "false").lower() == "true"
    if not enabled:
        return ("allow", "Sandbox layer disabled - pass through")

    # Only validate Bash commands
    if tool_name != "Bash":
        return ("allow", "Sandbox layer only validates Bash commands - pass through")

    # Extract command from tool_input
    command = tool_input.get("command", "")
    if not command:
        return ("allow", "No command to validate - pass through")

    try:
        # Try to import sandbox enforcer
        try:
            from sandbox_enforcer import SandboxEnforcer, CommandClassification

            # Create enforcer
            enforcer = SandboxEnforcer(policy_path=None, profile=None)

            # Classify command
            result = enforcer.is_command_safe(command)

            if result.classification == CommandClassification.SAFE:
                # Safe command - auto-approve
                return ("allow", "Sandbox: SAFE command auto-approved")
            elif result.classification == CommandClassification.BLOCKED:
                # Blocked command - deny
                return ("deny", f"Sandbox: BLOCKED - {result.reason}")
            else:  # NEEDS_APPROVAL
                # Unknown command - continue to next layer
                return ("ask", "Sandbox: NEEDS_APPROVAL - unknown command")

        except ImportError:
            # Sandbox enforcer not available - continue to next layer
            return ("ask", "Sandbox enforcer unavailable")

    except Exception as e:
        # Error in validation - continue to next layer (don't block on errors)
        return ("ask", f"Sandbox error: {e}")


def validate_mcp_security(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate MCP security (path traversal, injection, SSRF).

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if MCP security is enabled
    enabled = os.getenv("PRE_TOOL_MCP_SECURITY", "true").lower() == "true"
    if not enabled:
        return ("allow", "MCP security disabled")

    try:
        # Try to import MCP security validator
        try:
            from mcp_security_validator import validate_mcp_operation

            # Validate the operation
            is_safe, reason = validate_mcp_operation(tool_name, tool_input)

            if not is_safe:
                # Security risk detected
                return ("deny", f"MCP Security: {reason}")
            else:
                return ("allow", f"MCP Security: {reason}")

        except ImportError:
            # MCP security validator not available - check auto-approval
            auto_approve_enabled = os.getenv("MCP_AUTO_APPROVE", "false").lower()

            if auto_approve_enabled == "false":
                # Auto-approval disabled, no MCP security - ask user
                return ("ask", "MCP security validator unavailable, auto-approval disabled")

            # Auto-approval enabled - try to use it
            try:
                from auto_approval_engine import should_auto_approve

                agent_name = os.getenv("CLAUDE_AGENT_NAME", "main")
                approved, reason = should_auto_approve(tool_name, tool_input, agent_name)

                if approved:
                    return ("allow", f"Auto-approved: {reason}")
                elif "circuit breaker" in reason.lower():
                    return ("deny", f"Blocked: {reason}")  # Only circuit breaker is hard deny
                elif "blacklist" in reason.lower() or "injection" in reason.lower() or "security" in reason.lower():
                    return ("ask", f"Requires approval: {reason}")  # Dangerous but can override
                else:
                    return ("ask", f"Not whitelisted: {reason}")

            except ImportError:
                # Neither validator available but MCP_AUTO_APPROVE=true - allow
                return ("allow", "MCP security validators unavailable, MCP_AUTO_APPROVE=true - pass through")

    except Exception as e:
        # Error in validation - allow if MCP_AUTO_APPROVE=true, otherwise ask
        auto_approve = os.getenv("MCP_AUTO_APPROVE", "false").lower() == "true"
        if auto_approve:
            return ("allow", f"MCP security error but MCP_AUTO_APPROVE=true - pass through: {e}")
        return ("ask", f"MCP security error: {e}")


def validate_agent_authorization(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate agent authorization for code changes.

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if agent authorization is enabled
    enabled = os.getenv("PRE_TOOL_AGENT_AUTH", "true").lower() == "true"
    if not enabled:
        return ("allow", "Agent authorization disabled")

    # Check if running inside a pipeline agent
    agent_name = os.getenv("CLAUDE_AGENT_NAME", "").strip().lower()
    if agent_name in PIPELINE_AGENTS:
        return ("allow", f"Pipeline agent '{agent_name}' authorized")

    # Issue #141: Intent detection removed
    # All changes allowed - rely on persuasion, convenience, and skills
    return ("allow", f"Tool '{tool_name}' allowed (intent detection removed per Issue #141)")


def validate_batch_permission(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate batch permission for auto-approval.

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if batch permission is enabled
    enabled = os.getenv("PRE_TOOL_BATCH_PERMISSION", "false").lower() == "true"
    if not enabled:
        return ("allow", "Batch permission disabled")

    try:
        # Try to import permission classifier
        try:
            from permission_classifier import PermissionClassifier, PermissionLevel

            # Classify operation
            classifier = PermissionClassifier()
            level = classifier.classify(tool_name, tool_input)

            if level == PermissionLevel.SAFE:
                return ("allow", f"Batch permission: SAFE operation auto-approved")
            elif level == PermissionLevel.BOUNDARY:
                return ("allow", f"Batch permission: BOUNDARY operation allowed")
            else:  # PermissionLevel.SENSITIVE
                return ("ask", f"Batch permission: SENSITIVE operation requires user approval")

        except ImportError:
            # Permission classifier not available - allow (don't block)
            return ("allow", "Batch permission classifier unavailable")

    except Exception as e:
        # Error in validation - allow (don't block on errors)
        return ("allow", f"Batch permission error: {e}")


def combine_decisions(validators_results: List[Tuple[str, str, str]]) -> Tuple[str, str]:
    """
    Combine multiple validator decisions into single decision.

    Decision Logic:
    - If ANY validator returns "deny" → "deny" (block operation)
    - If ALL validators return "allow" → "allow" (approve operation)
    - Otherwise → "ask" (prompt user)

    Args:
        validators_results: List of (validator_name, decision, reason) tuples

    Returns:
        Tuple of (final_decision, combined_reason)
    """
    decisions = []
    reasons = []

    for validator_name, decision, reason in validators_results:
        decisions.append(decision)
        reasons.append(f"[{validator_name}] {reason}")

    # If ANY deny → deny
    if "deny" in decisions:
        deny_reasons = [r for v, d, r in validators_results if d == "deny"]
        return ("deny", "; ".join(deny_reasons))

    # If ALL allow → allow
    if all(d == "allow" for d in decisions):
        return ("allow", "; ".join(reasons))

    # Otherwise → ask
    ask_reasons = [r for v, d, r in validators_results if d == "ask"]
    if ask_reasons:
        return ("ask", "; ".join(ask_reasons))
    else:
        return ("ask", "; ".join(reasons))


def output_decision(decision: str, reason: str):
    """Output the hook decision in required format."""
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }
    print(json.dumps(output))


def main():
    """Main entry point - dispatch to all validators and combine decisions."""
    try:
        # Load environment variables
        load_env()

        # Read input from stdin
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            # Invalid JSON - ask user (don't block on invalid input)
            output_decision("ask", f"Invalid input JSON: {e}")
            sys.exit(0)

        # Extract tool information
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        if not tool_name:
            # No tool name - ask user
            output_decision("ask", "No tool name provided")
            sys.exit(0)

        # Run all validators in sequence (Layer 0 → Layer 1 → Layer 2 → Layer 3)
        validators_results = []

        # 0. Sandbox Layer (Layer 0) - Command classification & sandboxing
        decision, reason = validate_sandbox_layer(tool_name, tool_input)
        validators_results.append(("Sandbox", decision, reason))

        # 1. MCP Security Validator (Layer 1)
        decision, reason = validate_mcp_security(tool_name, tool_input)
        validators_results.append(("MCP Security", decision, reason))

        # 2. Agent Authorization (Layer 2)
        decision, reason = validate_agent_authorization(tool_name, tool_input)
        validators_results.append(("Agent Auth", decision, reason))

        # 3. Batch Permission Approver (Layer 3)
        decision, reason = validate_batch_permission(tool_name, tool_input)
        validators_results.append(("Batch Permission", decision, reason))

        # Combine all decisions
        final_decision, combined_reason = combine_decisions(validators_results)

        # Output final decision
        output_decision(final_decision, combined_reason)

    except Exception as e:
        # Error in hook - ask user (don't block on hook errors)
        output_decision("ask", f"Hook error: {e}")

    # Always exit 0 - let Claude Code process the decision
    sys.exit(0)


if __name__ == "__main__":
    main()
