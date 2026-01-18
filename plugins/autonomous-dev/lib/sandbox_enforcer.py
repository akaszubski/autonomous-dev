#!/usr/bin/env python3
"""
Sandbox Enforcer - Command Classification and Sandboxing

This module provides command classification (SAFE/BLOCKED/NEEDS_APPROVAL) and
OS-specific sandboxing for reducing permission prompts by 84%.

Features:
1. Command classification using blacklist-first policy
2. Shell injection detection (;, &&, ||, |, `, $(), >, >>)
3. Path traversal protection (.. detection)
4. Circuit breaker (trips after threshold blocks)
5. OS-specific sandbox binary detection (bwrap, sandbox-exec)
6. Sandbox argument building for command wrapping
7. Cascade policy resolution (project-local → plugin default)
8. Audit logging integration

Security Architecture:
- Blacklist-first: Safe commands auto-approved, blocked commands denied
- Shell injection patterns: Block dangerous shell metacharacters
- Path traversal: Block .. in paths and blocked file patterns
- Circuit breaker: Auto-disable after repeated blocks
- Audit logging: All decisions logged

Usage:
    from sandbox_enforcer import SandboxEnforcer, CommandClassification

    enforcer = SandboxEnforcer(policy_path=None, profile="development")
    result = enforcer.is_command_safe("cat README.md")

    if result.classification == CommandClassification.SAFE:
        # Auto-approve, skip permission prompt
        pass
    elif result.classification == CommandClassification.BLOCKED:
        # Deny, show reason
        print(result.reason)
    else:  # NEEDS_APPROVAL
        # Continue to Layer 1 (existing flow)
        pass

Date: 2026-01-02
Issue: #171 (Sandboxing for reduced permission prompts)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

import json
import logging
import os
import platform
import re
import shutil
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)


class CommandClassification(Enum):
    """Command classification for permission decision."""
    SAFE = "safe"  # Auto-approve, skip permission prompt
    BLOCKED = "blocked"  # Deny immediately, log to audit
    NEEDS_APPROVAL = "needs_approval"  # Continue to Layer 1 (existing flow)


class SandboxBinary(Enum):
    """OS-specific sandbox binaries."""
    BWRAP = "bwrap"  # Linux (bubblewrap)
    SANDBOX_EXEC = "sandbox-exec"  # macOS
    NONE = "none"  # Windows or unavailable


class PolicyValidationError(Exception):
    """Raised when policy validation fails."""
    pass


@dataclass
class CommandResult:
    """Result of command classification."""
    classification: CommandClassification
    reason: Optional[str] = None
    can_sandbox: bool = False


class SandboxEnforcer:
    """
    Sandbox enforcer for command classification and sandboxing.

    Provides:
    - Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
    - Shell injection detection
    - Path traversal protection
    - Circuit breaker logic
    - OS-specific sandbox binary detection
    - Sandbox argument building

    Thread-safe: Uses threading.Lock for circuit breaker state.
    """

    def __init__(
        self,
        policy_path: Optional[Path] = None,
        profile: Optional[str] = None
    ):
        """
        Initialize SandboxEnforcer.

        Args:
            policy_path: Path to policy file (None = use cascade resolution)
            profile: Profile to use (None = use env var or default)
        """
        # Load policy with cascade resolution
        self.policy_path = self._resolve_policy_path(policy_path)
        self.profile = self._resolve_profile(profile)
        self.policy = self._load_policy(self.policy_path, self.profile)

        # Validate policy
        if not self.validate_policy(self.policy):
            raise PolicyValidationError(f"Invalid policy schema: missing required fields")

        # Extract configuration (with defaults for optional security features)
        self.safe_commands = self.policy.get("safe_commands", [])
        self.blocked_patterns = self.policy.get("blocked_patterns", [])

        # Provide sensible defaults for security patterns if not specified
        # This ensures basic protection even if policy doesn't define them
        default_injection_patterns = [";", "&&", "||", "|", "`", "$(", ")", ">", ">>", "<", "\x00"]
        default_blocked_paths = []  # Don't block paths by default - let policy decide
        default_traversal_patterns = [".."]  # Always check for path traversal

        self.shell_injection_patterns = self.policy.get("shell_injection_patterns", default_injection_patterns)
        self.blocked_paths = self.policy.get("blocked_paths", default_blocked_paths)
        self.path_traversal_patterns = self.policy.get("path_traversal_patterns", default_traversal_patterns)
        self.sandbox_enabled = self.policy.get("sandbox_enabled", True)

        # Circuit breaker configuration
        circuit_breaker_config = self.policy.get("circuit_breaker", {})
        self.circuit_breaker_enabled = circuit_breaker_config.get("enabled", True)
        self.circuit_breaker_threshold = circuit_breaker_config.get("threshold", 10)

        # Circuit breaker state (thread-safe)
        self._circuit_breaker_count = 0
        self._circuit_breaker_tripped = False
        self._lock = threading.Lock()

        # Check environment variable override
        env_enabled = os.getenv("SANDBOX_ENABLED", "true").lower()
        if env_enabled == "false":
            self.sandbox_enabled = False

    def _resolve_policy_path(self, policy_path: Optional[Path]) -> Path:
        """
        Resolve policy path with cascade resolution.

        Checks in order:
        1. Explicit policy_path argument
        2. Project-local root: .claude/sandbox_policy.json
        3. Project-local config: .claude/config/sandbox_policy.json (Issue #248)
        4. Plugin default: config/sandbox_policy.json

        Args:
            policy_path: Explicit policy path (optional)

        Returns:
            Resolved policy path
        """
        # 1. Explicit path (convert to Path if string)
        if policy_path is not None:
            if isinstance(policy_path, str):
                policy_path = Path(policy_path)
            return policy_path

        # 2. Project-local (root of .claude/)
        project_local = Path.cwd() / ".claude" / "sandbox_policy.json"
        if project_local.exists():
            return project_local

        # 2b. Project-local in config subdirectory (Issue #248 fix)
        # install.sh and /sync put config files in .claude/config/
        project_config = Path.cwd() / ".claude" / "config" / "sandbox_policy.json"
        if project_config.exists():
            return project_config

        # 3. Plugin default
        plugin_default = Path(__file__).parent.parent / "config" / "sandbox_policy.json"
        return plugin_default

    def _resolve_profile(self, profile: Optional[str]) -> str:
        """
        Resolve profile with environment variable override.

        Args:
            profile: Explicit profile name (optional)

        Returns:
            Resolved profile name
        """
        # 1. Explicit profile
        if profile is not None:
            return profile

        # 2. Environment variable
        env_profile = os.getenv("SANDBOX_PROFILE", "").strip()
        if env_profile:
            return env_profile

        # 3. Default
        return "development"

    def _load_policy(self, policy_path: Path, profile: str) -> Dict[str, Any]:
        """
        Load policy from file.

        Args:
            policy_path: Path to policy file
            profile: Profile to load

        Returns:
            Policy dictionary for the specified profile

        Raises:
            PolicyValidationError: If policy file is invalid
        """
        # Load policy file
        if not policy_path.exists():
            # Use default policy
            return self._get_default_policy()

        try:
            with open(policy_path, 'r') as f:
                policy_data = json.load(f)
        except json.JSONDecodeError as e:
            # Corrupt JSON - use default policy
            logger.warning(f"Corrupt policy file, using default: {e}")
            return self._get_default_policy()

        # Validate schema
        if "profiles" not in policy_data:
            raise PolicyValidationError("Missing 'profiles' key in policy")

        # Get profile
        profiles = policy_data["profiles"]
        if profile not in profiles:
            # Fall back to default profile
            default_profile = policy_data.get("default_profile", "development")
            if default_profile not in profiles:
                raise PolicyValidationError(f"Default profile '{default_profile}' not found")
            profile = default_profile
            # Update instance profile
            self.profile = profile

        return profiles[profile]

    def _get_default_policy(self) -> Dict[str, Any]:
        """
        Get default policy when file not found or invalid.

        Returns:
            Default policy dictionary
        """
        return {
            "safe_commands": ["cat", "echo", "grep", "ls", "pwd", "git status", "pytest"],
            "blocked_patterns": ["rm -rf", "sudo", "git push --force", "eval"],
            "shell_injection_patterns": [";", "&&", "||", "|", "`", "$(", ")", ">", ">>", "<"],
            "blocked_paths": [],  # Don't block paths by default - let external policy decide
            "path_traversal_patterns": [".."],
            "sandbox_enabled": True,
            "circuit_breaker": {
                "enabled": True,
                "threshold": 10
            }
        }

    def validate_policy(self, policy: Dict[str, Any]) -> bool:
        """
        Validate policy schema.

        Args:
            policy: Policy dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        required_fields = ["safe_commands", "blocked_patterns", "sandbox_enabled"]
        for field in required_fields:
            if field not in policy:
                return False

        # Check field types
        if not isinstance(policy["safe_commands"], list):
            return False
        if not isinstance(policy["blocked_patterns"], list):
            return False
        if not isinstance(policy["sandbox_enabled"], bool):
            return False

        return True

    def is_command_safe(self, command: str) -> CommandResult:
        """
        Classify command as SAFE, BLOCKED, or NEEDS_APPROVAL.

        Args:
            command: Command to classify

        Returns:
            CommandResult with classification, reason, and can_sandbox
        """
        # Check circuit breaker first
        if self._is_circuit_breaker_tripped():
            logger.error(f"Circuit breaker tripped: command blocked")
            return CommandResult(
                classification=CommandClassification.BLOCKED,
                reason="Circuit breaker tripped after repeated blocks",
                can_sandbox=False
            )

        # Handle empty/whitespace commands
        if not command or not command.strip():
            return CommandResult(
                classification=CommandClassification.NEEDS_APPROVAL,
                reason="Empty command",
                can_sandbox=True
            )

        # Check for fork bomb FIRST (most specific/dangerous pattern)
        fork_bomb_pattern = r":\(\)\{.*\};"
        if re.search(fork_bomb_pattern, command):
            self._increment_circuit_breaker()
            logger.warning(f"BLOCKED command (fork bomb): {command}")
            return CommandResult(
                classification=CommandClassification.BLOCKED,
                reason="Fork bomb pattern detected",
                can_sandbox=False
            )

        # Check for shell injection (metacharacters)
        injection_detected, injection_char = self._check_shell_injection_detailed(command)
        if injection_detected:
            self._increment_circuit_breaker()
            logger.warning(f"BLOCKED command (shell injection '{injection_char}'): {command}")
            return CommandResult(
                classification=CommandClassification.BLOCKED,
                reason=f"Shell injection pattern detected: '{injection_char}'",
                can_sandbox=False
            )

        # Check for path traversal
        if self._check_path_traversal(command):
            self._increment_circuit_breaker()
            logger.warning(f"BLOCKED command (path traversal): {command}")
            return CommandResult(
                classification=CommandClassification.BLOCKED,
                reason="Path traversal pattern detected (..)",
                can_sandbox=False
            )

        # Check for blocked paths
        if self._check_blocked_paths(command):
            self._increment_circuit_breaker()
            logger.warning(f"BLOCKED command (blocked path): {command}")
            return CommandResult(
                classification=CommandClassification.BLOCKED,
                reason="Blocked path detected",
                can_sandbox=False
            )

        # Check other blocked patterns
        for pattern in self.blocked_patterns:
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    self._increment_circuit_breaker()
                    logger.warning(f"BLOCKED command (pattern '{pattern}'): {command}")
                    return CommandResult(
                        classification=CommandClassification.BLOCKED,
                        reason=f"Matched blocked pattern: {pattern}",
                        can_sandbox=False
                    )
            except re.error:
                # Invalid regex - skip
                continue

        # Check safe commands
        for safe_cmd in self.safe_commands:
            if command.strip().startswith(safe_cmd):
                self._reset_circuit_breaker()
                logger.info(f"SAFE command: {command}")
                return CommandResult(
                    classification=CommandClassification.SAFE,
                    reason=None,
                    can_sandbox=self._can_sandbox_command()
                )

        # Unknown command - needs approval
        logger.info(f"NEEDS_APPROVAL command: {command}")
        return CommandResult(
            classification=CommandClassification.NEEDS_APPROVAL,
            reason="Unknown command, not in safe or blocked lists",
            can_sandbox=self._can_sandbox_command()
        )

    def _check_shell_injection(self, command: str) -> bool:
        """
        Check for shell injection patterns.

        Args:
            command: Command to check

        Returns:
            True if injection detected, False otherwise
        """
        for pattern in self.shell_injection_patterns:
            if pattern in command:
                return True
        return False

    def _check_shell_injection_detailed(self, command: str) -> tuple[bool, Optional[str]]:
        """
        Check for shell injection patterns with detailed detection.

        Args:
            command: Command to check

        Returns:
            Tuple of (detected, pattern_found)
        """
        for pattern in self.shell_injection_patterns:
            if pattern in command:
                return (True, pattern)
        return (False, None)

    def _check_path_traversal(self, command: str) -> bool:
        """
        Check for path traversal patterns.

        Args:
            command: Command to check

        Returns:
            True if traversal detected, False otherwise
        """
        for pattern in self.path_traversal_patterns:
            if pattern in command:
                return True
        return False

    def _check_blocked_paths(self, command: str) -> bool:
        """
        Check for blocked paths.

        Args:
            command: Command to check

        Returns:
            True if blocked path detected, False otherwise
        """
        for pattern in self.blocked_paths:
            # Simple glob-style matching
            if "*" in pattern:
                # Convert glob to regex
                regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
                try:
                    if re.search(regex_pattern, command):
                        return True
                except re.error:
                    continue
            else:
                # Exact substring match
                if pattern in command:
                    return True
        return False

    def _can_sandbox_command(self) -> bool:
        """
        Check if command can be sandboxed.

        Returns:
            True if sandbox binary available and enabled, False otherwise
        """
        if not self.sandbox_enabled:
            return False

        binary = self.get_sandbox_binary()
        return binary != SandboxBinary.NONE

    def get_sandbox_binary(self) -> SandboxBinary:
        """
        Detect OS-specific sandbox binary.

        Returns:
            SandboxBinary enum value
        """
        system = platform.system()

        if system == "Linux":
            # Check for bubblewrap
            if shutil.which("bwrap"):
                return SandboxBinary.BWRAP
            return SandboxBinary.NONE

        elif system == "Darwin":
            # Check for sandbox-exec
            if shutil.which("sandbox-exec"):
                return SandboxBinary.SANDBOX_EXEC
            return SandboxBinary.NONE

        else:  # Windows or unknown
            return SandboxBinary.NONE

    def build_sandbox_args(
        self,
        command: str,
        boundaries: Dict[str, Any]
    ) -> List[str]:
        """
        Build sandbox arguments for command wrapping.

        Args:
            command: Command to wrap
            boundaries: Sandbox boundaries (read_only, read_write, network)

        Returns:
            List of command arguments including sandbox wrapper
        """
        binary = self.get_sandbox_binary()

        if binary == SandboxBinary.BWRAP:
            return self._build_bwrap_args(command, boundaries)
        elif binary == SandboxBinary.SANDBOX_EXEC:
            return self._build_sandbox_exec_args(command, boundaries)
        else:
            # No sandboxing - return original command
            return command.split()

    def _build_bwrap_args(
        self,
        command: str,
        boundaries: Dict[str, Any]
    ) -> List[str]:
        """
        Build bubblewrap (Linux) sandbox arguments.

        Args:
            command: Command to wrap
            boundaries: Sandbox boundaries

        Returns:
            List of bwrap command arguments
        """
        args = ["/usr/bin/bwrap"]

        # Add read-only binds
        for path in boundaries.get("read_only", []):
            args.extend(["--ro-bind", path, path])

        # Add read-write binds
        for path in boundaries.get("read_write", []):
            args.extend(["--bind", path, path])

        # Network isolation
        if not boundaries.get("network", False):
            args.append("--unshare-net")

        # Add command
        args.extend(command.split())

        return args

    def _build_sandbox_exec_args(
        self,
        command: str,
        boundaries: Dict[str, Any]
    ) -> List[str]:
        """
        Build sandbox-exec (macOS) sandbox arguments.

        Args:
            command: Command to wrap
            boundaries: Sandbox boundaries

        Returns:
            List of sandbox-exec command arguments
        """
        # sandbox-exec uses a profile file
        # For simplicity, we'll use a basic profile
        args = ["/usr/bin/sandbox-exec", "-f", "/tmp/sandbox_profile.sb"]

        # Add command
        args.extend(command.split())

        return args

    def _increment_circuit_breaker(self):
        """Increment circuit breaker count (thread-safe)."""
        with self._lock:
            self._circuit_breaker_count += 1
            if self._circuit_breaker_count >= self.circuit_breaker_threshold:
                self._circuit_breaker_tripped = True
                logger.error(
                    f"Circuit breaker tripped after {self._circuit_breaker_count} blocks"
                )

    def _reset_circuit_breaker(self):
        """Reset circuit breaker count (thread-safe)."""
        with self._lock:
            self._circuit_breaker_count = 0

    def _is_circuit_breaker_tripped(self) -> bool:
        """
        Check if circuit breaker is tripped (thread-safe).

        Returns:
            True if tripped, False otherwise
        """
        if not self.circuit_breaker_enabled:
            return False

        with self._lock:
            return self._circuit_breaker_tripped


# Module-level logger configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
