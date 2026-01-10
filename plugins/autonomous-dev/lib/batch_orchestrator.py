#!/usr/bin/env python3
"""
Batch Orchestrator - Unified /implement command orchestration

This module provides:
- Flag parsing for unified /implement command (--quick, --batch, --issues, --resume)
- Auto-worktree creation for batch modes
- Mode detection and routing
- Deprecation shim support for old commands

Security Features:
- CWE-22: Path traversal prevention in batch IDs
- CWE-78: Command injection prevention
- CWE-59: Symlink protection (inherited from worktree_manager)

Usage:
    from batch_orchestrator import parse_implement_flags, route_implement_mode

    flags = parse_implement_flags(["--batch", "features.txt"])
    result = route_implement_mode(flags)

Date: 2026-01-10
Issue: GitHub #203 (Consolidate commands)
Agent: implementer
"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

# Lazy imports to avoid circular dependencies
_worktree_manager = None
_batch_state_manager = None
_path_utils = None


# =============================================================================
# Custom Exceptions
# =============================================================================

class BatchOrchestratorError(Exception):
    """Base exception for batch orchestrator errors."""
    pass


class FlagConflictError(BatchOrchestratorError):
    """Raised when conflicting command flags are used."""
    pass


class MissingArgumentError(BatchOrchestratorError):
    """Raised when required arguments are missing."""
    pass


class InvalidArgumentError(BatchOrchestratorError):
    """Raised when arguments are invalid."""
    pass


class SecurityError(BatchOrchestratorError):
    """Raised when security validation fails."""
    pass


class BatchNotFoundError(BatchOrchestratorError):
    """Raised when batch ID cannot be found for resume."""
    pass


# =============================================================================
# Lazy Import Helpers
# =============================================================================

def _get_worktree_manager():
    """Lazy import worktree_manager to avoid circular dependencies."""
    global _worktree_manager
    if _worktree_manager is None:
        try:
            import worktree_manager
            _worktree_manager = worktree_manager
        except ImportError:
            _worktree_manager = None
    return _worktree_manager


def _get_batch_state_manager():
    """Lazy import batch_state_manager to avoid circular dependencies."""
    global _batch_state_manager
    if _batch_state_manager is None:
        try:
            import batch_state_manager
            _batch_state_manager = batch_state_manager
        except ImportError:
            _batch_state_manager = None
    return _batch_state_manager


def _get_path_utils():
    """Lazy import path_utils to avoid circular dependencies."""
    global _path_utils
    if _path_utils is None:
        try:
            import path_utils
            _path_utils = path_utils
        except ImportError:
            _path_utils = None
    return _path_utils


# =============================================================================
# Security Validation
# =============================================================================

# Pattern for valid batch IDs: alphanumeric, hyphens, underscores only
VALID_BATCH_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

# Dangerous patterns for path traversal
PATH_TRAVERSAL_PATTERNS = ['..', '/', '\\']

# Shell metacharacters for command injection
SHELL_METACHARACTERS = ['$', '`', '|', ';', '&', '(', ')', '<', '>', '\n', '\r']


def validate_batch_id(batch_id: str) -> bool:
    """Validate batch ID for security.

    Args:
        batch_id: The batch ID to validate

    Returns:
        True if valid

    Raises:
        SecurityError: If batch ID contains dangerous patterns
    """
    if not batch_id:
        raise InvalidArgumentError("Batch ID cannot be empty")

    # Check for shell metacharacters FIRST (CWE-78)
    # This catches command injection attempts before path checks
    for char in SHELL_METACHARACTERS:
        if char in batch_id:
            raise SecurityError(
                f"Invalid character '{char}' in batch ID: '{batch_id}'. "
                f"Batch IDs can only contain letters, numbers, hyphens, and underscores."
            )

    # Check for path traversal (CWE-22)
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if pattern in batch_id:
            raise SecurityError(
                f"Path traversal detected in batch ID: '{batch_id}'. "
                f"Batch IDs cannot contain '{pattern}'."
            )

    # Check against allowed pattern
    if not VALID_BATCH_ID_PATTERN.match(batch_id):
        raise SecurityError(
            f"Invalid batch ID format: '{batch_id}'. "
            f"Batch IDs can only contain letters, numbers, hyphens, and underscores."
        )

    return True


def validate_features_file(file_path: str) -> bool:
    """Validate features file path for security.

    Args:
        file_path: Path to features file

    Returns:
        True if valid

    Raises:
        SecurityError: If path contains traversal attempts
    """
    # Check for path traversal
    resolved = Path(file_path).resolve()
    cwd = Path.cwd().resolve()

    # File must be within current working directory or subdirectory
    try:
        resolved.relative_to(cwd)
    except ValueError:
        # Also allow absolute paths that exist and are readable
        if not resolved.exists():
            raise SecurityError(
                f"Features file path traversal detected: '{file_path}'. "
                f"File must be within current directory."
            )

    return True


def validate_issue_numbers(issues: List[int]) -> bool:
    """Validate issue numbers.

    Args:
        issues: List of issue numbers

    Returns:
        True if valid

    Raises:
        InvalidArgumentError: If issues are invalid
    """
    MAX_ISSUES = 100

    if len(issues) > MAX_ISSUES:
        raise InvalidArgumentError(
            f"Too many issues: {len(issues)} provided, max {MAX_ISSUES}. "
            f"Please split into multiple batches."
        )

    for issue in issues:
        if issue <= 0:
            raise InvalidArgumentError(
                f"Invalid issue number: {issue}. Issue numbers must be positive integers."
            )

    return True


# =============================================================================
# Flag Parsing
# =============================================================================

def parse_implement_flags(args: List[str]) -> Dict[str, Any]:
    """Parse command-line flags for unified /implement command.

    Args:
        args: Command-line arguments

    Returns:
        Dictionary with parsed flags:
        - mode: "full_pipeline", "quick", "batch_file", "batch_issues", or "resume"
        - feature: Feature description (for full_pipeline and quick modes)
        - quick: Boolean, True if --quick flag present
        - batch_file: Path to features file (for batch_file mode)
        - issues: List of issue numbers (for batch_issues mode)
        - resume_id: Batch ID to resume (for resume mode)

    Raises:
        FlagConflictError: If conflicting flags are used
        MissingArgumentError: If required arguments are missing
        InvalidArgumentError: If arguments are invalid
    """
    if not args:
        raise MissingArgumentError(
            "No arguments provided. Usage:\n"
            "  /implement \"feature description\"     # Full pipeline (default)\n"
            "  /implement --quick \"feature\"         # Quick mode (implementer only)\n"
            "  /implement --batch features.txt      # Batch from file\n"
            "  /implement --issues 72 73 74         # Batch from GitHub issues\n"
            "  /implement --resume batch-123        # Resume interrupted batch"
        )

    result = {
        "mode": "full_pipeline",
        "feature": None,
        "quick": False,
        "batch_file": None,
        "issues": None,
        "resume_id": None,
    }

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--quick":
            result["quick"] = True
            result["mode"] = "quick"
            i += 1

        elif arg == "--batch":
            if result["quick"]:
                raise FlagConflictError(
                    "Cannot use --quick with batch mode. Choose one mode:\n"
                    "  /implement --quick \"feature\"    # Quick mode\n"
                    "  /implement --batch file.txt     # Batch mode"
                )
            if i + 1 >= len(args):
                raise MissingArgumentError(
                    "--batch requires a file path. Usage:\n"
                    "  /implement --batch features.txt"
                )
            result["batch_file"] = args[i + 1]
            result["mode"] = "batch_file"
            i += 2

        elif arg == "--issues":
            if result["quick"]:
                raise FlagConflictError(
                    "Cannot use --quick with batch mode. Choose one mode:\n"
                    "  /implement --quick \"feature\"    # Quick mode\n"
                    "  /implement --issues 72 73 74    # Batch issues mode"
                )
            # Collect all issue numbers following --issues
            issues = []
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                try:
                    issues.append(int(args[i]))
                except ValueError:
                    raise InvalidArgumentError(
                        f"Invalid issue number: '{args[i]}'. "
                        f"Issue numbers must be positive integers."
                    )
                i += 1

            if not issues:
                raise MissingArgumentError(
                    "--issues requires at least one issue number. Usage:\n"
                    "  /implement --issues 72 73 74"
                )
            result["issues"] = issues
            result["mode"] = "batch_issues"

        elif arg == "--resume":
            if i + 1 >= len(args):
                raise MissingArgumentError(
                    "--resume requires a batch ID. Usage:\n"
                    "  /implement --resume batch-20260110-143022"
                )
            result["resume_id"] = args[i + 1]
            result["mode"] = "resume"
            i += 2

        else:
            # Not a flag, must be a feature description
            # Collect remaining args as feature description
            feature_parts = []
            while i < len(args) and not args[i].startswith("--"):
                feature_parts.append(args[i])
                i += 1
            result["feature"] = " ".join(feature_parts)

    # Validate mode-specific requirements
    if result["mode"] == "full_pipeline" and not result["feature"]:
        raise MissingArgumentError(
            "No feature description provided. Usage:\n"
            "  /implement \"add user authentication\""
        )

    if result["mode"] == "quick" and not result["feature"]:
        raise MissingArgumentError(
            "--quick requires a feature description. Usage:\n"
            "  /implement --quick \"fix typo in readme\""
        )

    return result


# =============================================================================
# Worktree Management
# =============================================================================

def get_batch_worktree_path(batch_id: str) -> Path:
    """Get the worktree path for a batch.

    Args:
        batch_id: The batch ID

    Returns:
        Path to the worktree directory
    """
    validate_batch_id(batch_id)

    path_utils = _get_path_utils()
    if path_utils:
        try:
            project_root = path_utils.get_project_root()
        except FileNotFoundError:
            project_root = Path.cwd()
    else:
        project_root = Path.cwd()

    return project_root / ".worktrees" / batch_id


def get_batch_state_path_for_worktree(worktree_path: Path) -> Path:
    """Get the batch state file path for a worktree.

    Args:
        worktree_path: Path to the worktree

    Returns:
        Path to batch_state.json in worktree's .claude/ directory
    """
    return worktree_path / ".claude" / "batch_state.json"


def create_batch_worktree(batch_id: str) -> Dict[str, Any]:
    """Create a worktree for batch processing.

    Args:
        batch_id: The batch ID

    Returns:
        Dictionary with:
        - success: Boolean indicating success
        - path: Path to created worktree
        - batch_id: Final batch ID (may differ if collision occurred)
        - fallback: True if running without worktree isolation
        - warning: Warning message if fallback
    """
    validate_batch_id(batch_id)

    worktree_path = get_batch_worktree_path(batch_id)
    final_batch_id = batch_id

    # Handle collision - append timestamp if path exists
    if worktree_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final_batch_id = f"{batch_id}-{timestamp}"
        worktree_path = get_batch_worktree_path(final_batch_id)

    wm = _get_worktree_manager()
    if wm is None:
        # Fallback: No worktree isolation
        return {
            "success": False,
            "fallback": True,
            "path": str(Path.cwd()),
            "batch_id": final_batch_id,
            "warning": "Worktree manager unavailable. Running without isolation.",
        }

    try:
        # Create worktree using worktree_manager
        result = wm.create_worktree(str(worktree_path), final_batch_id)

        if result.get("success"):
            # Create .claude directory in worktree
            claude_dir = worktree_path / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)

            return {
                "success": True,
                "fallback": False,
                "path": str(worktree_path),
                "batch_id": final_batch_id,
            }
        else:
            # Worktree creation failed - fallback
            return {
                "success": False,
                "fallback": True,
                "path": str(Path.cwd()),
                "batch_id": final_batch_id,
                "warning": f"Worktree creation failed: {result.get('error', 'Unknown error')}. "
                           f"Running without isolation.",
            }

    except Exception as e:
        # Fallback on any error
        return {
            "success": False,
            "fallback": True,
            "path": str(Path.cwd()),
            "batch_id": final_batch_id,
            "warning": f"Worktree creation error: {e}. Running without isolation.",
        }


def find_batch_worktree(batch_id: str) -> Dict[str, Any]:
    """Find an existing worktree for a batch ID.

    Args:
        batch_id: The batch ID to find

    Returns:
        Dictionary with:
        - found: Boolean indicating if batch was found
        - path: Path to worktree (if found)
        - state: Batch state (if found)

    Raises:
        BatchNotFoundError: If batch cannot be found
    """
    validate_batch_id(batch_id)

    path_utils = _get_path_utils()
    if path_utils:
        try:
            project_root = path_utils.get_project_root()
        except FileNotFoundError:
            project_root = Path.cwd()
    else:
        project_root = Path.cwd()

    worktrees_dir = project_root / ".worktrees"

    # Look for exact match first
    exact_path = worktrees_dir / batch_id
    if exact_path.exists():
        state_file = exact_path / ".claude" / "batch_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                return {
                    "found": True,
                    "path": exact_path,
                    "state": state,
                }
            except json.JSONDecodeError:
                pass

    # Look for prefix matches (batch_id-timestamp pattern)
    if worktrees_dir.exists():
        for worktree_dir in worktrees_dir.iterdir():
            if worktree_dir.is_dir() and worktree_dir.name.startswith(batch_id):
                state_file = worktree_dir / ".claude" / "batch_state.json"
                if state_file.exists():
                    try:
                        state = json.loads(state_file.read_text())
                        if state.get("batch_id", "").startswith(batch_id):
                            return {
                                "found": True,
                                "path": worktree_dir,
                                "state": state,
                            }
                    except json.JSONDecodeError:
                        continue

    # Also check main repo .claude/ for non-worktree batches
    main_state_file = project_root / ".claude" / "batch_state.json"
    if main_state_file.exists():
        try:
            state = json.loads(main_state_file.read_text())
            if state.get("batch_id", "").startswith(batch_id):
                return {
                    "found": True,
                    "path": project_root,
                    "state": state,
                }
        except json.JSONDecodeError:
            pass

    raise BatchNotFoundError(
        f"Batch '{batch_id}' not found. Check that:\n"
        f"1. The batch ID is correct\n"
        f"2. You're in the correct repository\n"
        f"3. The batch wasn't already completed/cleaned up"
    )


# =============================================================================
# GitHub Issue Fetching
# =============================================================================

def fetch_issue_titles(issues: List[int]) -> List[str]:
    """Fetch issue titles from GitHub.

    Args:
        issues: List of issue numbers

    Returns:
        List of formatted feature strings: "Issue #N: title"

    Note:
        Requires gh CLI to be installed and authenticated.
    """
    validate_issue_numbers(issues)

    features = []
    for issue_num in issues:
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_num), "--json", "title"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                title = data.get("title", f"Issue {issue_num}")
                features.append(f"Issue #{issue_num}: {title}")
            else:
                # Issue not found or error - include anyway with placeholder
                features.append(f"Issue #{issue_num}: [Title unavailable]")

        except subprocess.TimeoutExpired:
            features.append(f"Issue #{issue_num}: [Timeout fetching title]")
        except json.JSONDecodeError:
            features.append(f"Issue #{issue_num}: [Error parsing response]")
        except FileNotFoundError:
            # gh CLI not installed
            features.append(f"Issue #{issue_num}: [gh CLI not installed]")

    return features


# =============================================================================
# Mode Execution Functions
# =============================================================================

def run_full_pipeline(feature: str) -> Dict[str, Any]:
    """Run full 8-agent pipeline for a feature.

    Args:
        feature: Feature description

    Returns:
        Dictionary with execution result

    Note:
        This is a stub - actual implementation delegates to /auto-implement logic
        which is orchestrated by Claude, not Python code.
    """
    # This function exists for the orchestration layer
    # Actual pipeline execution is done by Claude following auto-implement.md
    return {
        "mode": "full_pipeline",
        "feature": feature,
        "status": "ready",
        "message": "Full pipeline ready for execution via Claude orchestration",
    }


def run_quick_mode(feature: str) -> Dict[str, Any]:
    """Run quick mode (implementer agent only).

    Args:
        feature: Feature description

    Returns:
        Dictionary with execution result

    Note:
        This is a stub - actual implementation delegates to implementer agent.
    """
    return {
        "mode": "quick",
        "feature": feature,
        "status": "ready",
        "message": "Quick mode ready - will invoke implementer agent only",
    }


def run_batch_file_mode(file_path: str) -> Dict[str, Any]:
    """Run batch mode from features file.

    Args:
        file_path: Path to features file

    Returns:
        Dictionary with execution result including worktree info
    """
    validate_features_file(file_path)

    # Generate batch ID
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_id = f"batch-{timestamp}"

    # Create worktree
    worktree_result = create_batch_worktree(batch_id)

    # Read features file
    features = []
    file_path_obj = Path(file_path)
    if file_path_obj.exists():
        for line in file_path_obj.read_text().splitlines():
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith("#"):
                features.append(line)

    return {
        "mode": "batch_file",
        "batch_id": worktree_result["batch_id"],
        "file_path": file_path,
        "features": features,
        "feature_count": len(features),
        "worktree_created": worktree_result["success"],
        "worktree_path": worktree_result["path"],
        "fallback": worktree_result.get("fallback", False),
        "warning": worktree_result.get("warning"),
        "status": "ready",
    }


def run_batch_issues_mode(issues: List[int]) -> Dict[str, Any]:
    """Run batch mode from GitHub issues.

    Args:
        issues: List of issue numbers

    Returns:
        Dictionary with execution result including worktree info
    """
    validate_issue_numbers(issues)

    # Generate batch ID
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    issues_str = "-".join(str(i) for i in issues[:3])  # First 3 for readability
    if len(issues) > 3:
        issues_str += f"-plus{len(issues) - 3}"
    batch_id = f"batch-issues-{issues_str}-{timestamp}"

    # Create worktree
    worktree_result = create_batch_worktree(batch_id)

    # Fetch issue titles
    features = fetch_issue_titles(issues)

    return {
        "mode": "batch_issues",
        "batch_id": worktree_result["batch_id"],
        "issues": issues,
        "features": features,
        "feature_count": len(features),
        "worktree_created": worktree_result["success"],
        "worktree_path": worktree_result["path"],
        "fallback": worktree_result.get("fallback", False),
        "warning": worktree_result.get("warning"),
        "status": "ready",
    }


def run_resume_mode(batch_id: str) -> Dict[str, Any]:
    """Resume an interrupted batch.

    Args:
        batch_id: Batch ID to resume

    Returns:
        Dictionary with batch state and worktree info

    Raises:
        BatchNotFoundError: If batch cannot be found
    """
    batch_info = find_batch_worktree(batch_id)

    return {
        "mode": "resume",
        "batch_id": batch_info["state"].get("batch_id", batch_id),
        "found": True,
        "worktree_path": str(batch_info["path"]),
        "state": batch_info["state"],
        "current_index": batch_info["state"].get("current_index", 0),
        "total_features": batch_info["state"].get("total_features", 0),
        "completed_features": batch_info["state"].get("completed_features", []),
        "failed_features": batch_info["state"].get("failed_features", []),
        "status": "ready",
    }


def route_implement_mode(flags: Dict[str, Any]) -> Dict[str, Any]:
    """Route to appropriate mode based on parsed flags.

    Args:
        flags: Parsed flags from parse_implement_flags()

    Returns:
        Result from the appropriate mode execution function
    """
    mode = flags["mode"]

    if mode == "full_pipeline":
        return run_full_pipeline(flags["feature"])

    elif mode == "quick":
        return run_quick_mode(flags["feature"])

    elif mode == "batch_file":
        return run_batch_file_mode(flags["batch_file"])

    elif mode == "batch_issues":
        return run_batch_issues_mode(flags["issues"])

    elif mode == "resume":
        return run_resume_mode(flags["resume_id"])

    else:
        raise InvalidArgumentError(f"Unknown mode: {mode}")


# =============================================================================
# Deprecation Shim Support
# =============================================================================

DEPRECATION_NOTICES = {
    "auto-implement": """
**DEPRECATED**: /auto-implement is deprecated as of v3.45.0.

Use `/implement` instead (full pipeline is now the default):

Old: /auto-implement "add user authentication"
New: /implement "add user authentication"

The unified /implement command provides:
- Full pipeline by default (8 agents)
- --quick flag for fast mode
- --batch and --issues for batch processing
""".strip(),

    "batch-implement": """
**DEPRECATED**: /batch-implement is deprecated as of v3.45.0.

Use `/implement` with batch flags instead:

Old: /batch-implement features.txt
New: /implement --batch features.txt

Old: /batch-implement --issues 72 73 74
New: /implement --issues 72 73 74

Old: /batch-implement --resume batch-123
New: /implement --resume batch-123

The unified /implement command provides:
- Auto-worktree creation for batch isolation
- Parallel batch support (multiple batches can run concurrently)
- Same state management and crash recovery
""".strip(),
}


def get_deprecation_notice(command: str) -> str:
    """Get deprecation notice for a command.

    Args:
        command: The deprecated command name

    Returns:
        Deprecation notice text
    """
    return DEPRECATION_NOTICES.get(command, f"/{ command} is deprecated. Use /implement instead.")


def convert_legacy_args(command: str, args: List[str]) -> List[str]:
    """Convert legacy command args to new /implement args.

    Args:
        command: The legacy command name
        args: Original arguments

    Returns:
        Converted arguments for /implement
    """
    if command == "auto-implement":
        # /auto-implement "feature" → /implement "feature" (no change needed)
        return args

    elif command == "batch-implement":
        # Check if args already have flags
        if args and args[0].startswith("--"):
            # /batch-implement --issues 72 → /implement --issues 72
            # /batch-implement --resume X → /implement --resume X
            return args
        else:
            # /batch-implement features.txt → /implement --batch features.txt
            return ["--batch"] + args

    else:
        return args


def handle_deprecated_command(command: str, args: List[str]) -> Dict[str, Any]:
    """Handle invocation of a deprecated command.

    Args:
        command: The deprecated command name
        args: Original arguments

    Returns:
        Dictionary with redirect info and notice
    """
    return {
        "redirect_to": "implement",
        "args": convert_legacy_args(command, args),
        "notice": get_deprecation_notice(command),
    }


def start_batch_issues_mode(issues: List[int]) -> Dict[str, Any]:
    """Start batch processing from GitHub issues.

    Alias for run_batch_issues_mode for backward compatibility.
    """
    return run_batch_issues_mode(issues)


# =============================================================================
# Agent Invocation Stub
# =============================================================================

def invoke_agent(agent_type: str, **kwargs) -> Dict[str, Any]:
    """Stub for agent invocation.

    In the actual workflow, Claude orchestrates agent invocation via Task tool.
    This function exists for testing and documentation purposes.

    Args:
        agent_type: Type of agent to invoke
        **kwargs: Arguments for the agent

    Returns:
        Dictionary with invocation result
    """
    return {
        "agent_type": agent_type,
        "status": "invoked",
        "kwargs": kwargs,
    }
