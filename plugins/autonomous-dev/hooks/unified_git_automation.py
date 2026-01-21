#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Unified Git Automation Hook - Dispatcher for SubagentStop Git Operations

Consolidates SubagentStop git automation hooks:
- auto_git_workflow.py (commit, push, PR creation)

Hook: SubagentStop (runs when doc-master completes)
Matcher: doc-master (last agent in parallel validation phase)

Environment Variables (opt-in/opt-out):
    AUTO_GIT_ENABLED=true/false (default: false)
    AUTO_GIT_PUSH=true/false (default: false)
    AUTO_GIT_PR=true/false (default: false)
    SESSION_FILE=path (default: latest in docs/sessions/)

Environment Variables (provided by Claude Code):
    CLAUDE_AGENT_NAME - Name of the subagent that completed
    CLAUDE_AGENT_STATUS - Status: "success" or "error"

Exit codes:
    0: Always (non-blocking hook - failures are logged but don't block)

Usage:
    # As SubagentStop hook (automatic)
    CLAUDE_AGENT_NAME=doc-master AUTO_GIT_ENABLED=true python unified_git_automation.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


# ============================================================================
# Dynamic Library Discovery
# ============================================================================

def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

def find_lib_dir() -> Optional[Path]:
    """
    Find the lib directory dynamically.

    Searches:
    1. Relative to this file: ../lib
    2. In project root: plugins/autonomous-dev/lib
    3. In global install: ~/.autonomous-dev/lib

    Returns:
        Path to lib directory or None if not found
    """
    candidates = [
        Path(__file__).parent.parent / "lib",  # Relative to hooks/
        Path.cwd() / "plugins" / "autonomous-dev" / "lib",  # Project root
        Path.home() / ".autonomous-dev" / "lib",  # Global install
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


# Add lib to path
LIB_DIR = find_lib_dir()
if LIB_DIR:
    if not is_running_under_uv():
        sys.path.insert(0, str(LIB_DIR))

# ============================================================================
# Logging Infrastructure (Issue #167)
# ============================================================================

def log_warning(message: str, verbose: bool = None) -> None:
    """Log warning to stderr with timestamp."""
    if verbose is None:
        verbose = os.getenv('GIT_AUTOMATION_VERBOSE', 'false').lower() == 'true'
    if verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] GIT-AUTOMATION WARNING: {message}", file=sys.stderr)


def log_info(message: str, verbose: bool = None) -> None:
    """Log info to stderr with timestamp."""
    if verbose is None:
        verbose = os.getenv('GIT_AUTOMATION_VERBOSE', 'false').lower() == 'true'
    if verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] GIT-AUTOMATION INFO: {message}", file=sys.stderr)


# Optional imports with graceful fallback
try:
    from security_utils import validate_path, audit_log
    HAS_SECURITY_UTILS = True
except ImportError as e:
    HAS_SECURITY_UTILS = False
    log_warning(f"security_utils import failed: {e}. Security validation disabled.")
    def audit_log(event_type: str, status: str, context: Dict) -> None:
        pass

try:
    from auto_implement_git_integration import execute_step8_git_operations_from_hook
    HAS_GIT_INTEGRATION = True
except ImportError as e:
    HAS_GIT_INTEGRATION = False
    log_warning(f"auto_implement_git_integration import failed: {e}. Git automation disabled.")

try:
    from path_utils import get_session_dir
    HAS_PATH_UTILS = True
except ImportError as e:
    HAS_PATH_UTILS = False
    log_info(f"path_utils import failed: {e}. Using fallback session discovery.")


# ============================================================================
# Configuration
# ============================================================================

def parse_bool(value: str) -> bool:
    """Parse boolean from various formats (case-insensitive)."""
    return value.lower() in ('true', 'yes', '1')


# Check configuration from environment
AUTO_GIT_ENABLED = parse_bool(os.environ.get('AUTO_GIT_ENABLED', 'false'))
AUTO_GIT_PUSH = parse_bool(os.environ.get('AUTO_GIT_PUSH', 'false')) if AUTO_GIT_ENABLED else False
AUTO_GIT_PR = parse_bool(os.environ.get('AUTO_GIT_PR', 'false')) if AUTO_GIT_ENABLED else False


# ============================================================================
# Git Workflow Trigger
# ============================================================================

def should_trigger_git_workflow(agent_name: Optional[str]) -> bool:
    """
    Check if git workflow should trigger based on agent name or explicit flag.

    Triggers for:
    - doc-master: Last agent in full pipeline mode (SubagentStop hook)
    - FORCE_GIT_TRIGGER=true: Explicit trigger from /implement command (quick/batch modes)

    Issue #258: Git automation now works in all /implement modes:
    - Full pipeline: Triggers on doc-master completion (SubagentStop hook)
    - Quick mode: Triggers via explicit FORCE_GIT_TRIGGER at end of command
    - Batch mode: Triggers via explicit FORCE_GIT_TRIGGER at end of command
    - Coordinator edits: Triggers via explicit FORCE_GIT_TRIGGER at end of command

    Args:
        agent_name: Name of agent that just completed (can be None for explicit trigger)

    Returns:
        True if workflow should trigger, False otherwise
    """
    # Check for explicit trigger (Issue #258 - quick/batch/coordinator modes)
    force_trigger = os.environ.get('FORCE_GIT_TRIGGER', 'false').lower() == 'true'
    if force_trigger:
        log_info("Git automation triggered via FORCE_GIT_TRIGGER (quick/batch/coordinator mode)")
        return True

    if not agent_name:
        return False

    # Trigger for doc-master (last agent in full pipeline)
    if agent_name == 'doc-master':
        return True

    return False


def check_git_workflow_consent() -> Dict[str, bool]:
    """
    Check user consent for git operations via environment variables.

    Reads environment variables directly for runtime flexibility.

    Returns:
        Dict with consent flags:
        {
            'git_enabled': bool,      # Master switch
            'push_enabled': bool,     # Push consent
            'pr_enabled': bool,       # PR consent
            'all_enabled': bool       # All three enabled
        }
    """
    # Read environment variables directly (not module constants)
    # This allows tests to patch environment and get correct values
    git_enabled = parse_bool(os.environ.get('AUTO_GIT_ENABLED', 'false'))
    push_enabled = parse_bool(os.environ.get('AUTO_GIT_PUSH', 'false')) if git_enabled else False
    pr_enabled = parse_bool(os.environ.get('AUTO_GIT_PR', 'false')) if git_enabled else False
    all_enabled = git_enabled and push_enabled and pr_enabled

    return {
        'git_enabled': git_enabled,
        'push_enabled': push_enabled,
        'pr_enabled': pr_enabled,
        'all_enabled': all_enabled,
    }


def get_session_file_path() -> Optional[Path]:
    """
    Get path to session file for workflow metadata (Issue #167 - optional).

    Uses portable path discovery via path_utils.get_session_dir() when available.
    Falls back to hardcoded docs/sessions/ for backward compatibility.

    Checks SESSION_FILE environment variable first, otherwise finds latest
    session file in session directory.

    Returns:
        Path to session file or None if not found/invalid (graceful degradation)
    """
    session_file_env = os.environ.get('SESSION_FILE')

    if session_file_env:
        # Use explicit session file (validate security if available)
        session_path = Path(session_file_env).resolve()

        if HAS_SECURITY_UTILS:
            try:
                validated_path = validate_path(
                    session_path,
                    purpose='session file reading',
                    allow_missing=True,
                )
                return validated_path
            except ValueError as e:
                log_warning(f"Session file security validation failed: {e}")
                audit_log(
                    event_type='session_file_path_validation',
                    status='rejected',
                    context={'session_file': str(session_path), 'error': str(e)},
                )
                return None
        else:
            return session_path if session_path.exists() else None

    # Use portable path discovery if available (Issue #167)
    if HAS_PATH_UTILS:
        session_dir = get_session_dir()
        if session_dir is None:
            log_info("Session directory not found. Git automation will continue with reduced features.")
            return None
    else:
        # Fallback to hardcoded path for backward compatibility
        session_dir = Path("docs/sessions")
        if not session_dir.exists():
            log_info("Session directory not found (docs/sessions). Git automation will continue with reduced features.")
            return None

    # Find latest session file
    session_files = list(session_dir.glob("*-pipeline.json"))
    if not session_files:
        log_info(f"No session files found in {session_dir}. Git automation will continue with reduced features.")
        return None

    return sorted(session_files)[-1]


def execute_git_workflow(session_file: Optional[Path], consent: Dict[str, bool]) -> bool:
    """
    Execute git workflow operations (Issue #167 - session file optional).

    Args:
        session_file: Path to session file with workflow metadata (optional)
        consent: Consent flags for git operations

    Returns:
        True if executed successfully, False otherwise
    """
    if not HAS_GIT_INTEGRATION:
        log_warning("Git integration library not available. Cannot execute git workflow.")
        return False

    try:
        # Execute git operations via library (session_file is optional)
        result = execute_step8_git_operations_from_hook(
            session_file=session_file,
            git_enabled=consent['git_enabled'],
            push_enabled=consent['push_enabled'],
            pr_enabled=consent['pr_enabled'],
        )
        return result.get('success', False)
    except Exception as e:
        log_warning(f"Git workflow execution failed: {e}")
        if HAS_SECURITY_UTILS:
            audit_log(
                event_type='git_workflow_execution',
                status='error',
                context={'error': str(e)},
            )
        return False


# ============================================================================
# Main Hook Entry Point
# ============================================================================

def main() -> int:
    """
    Main hook entry point (Issue #167 - session file optional).

    Reads agent info from environment, executes git workflow if appropriate.

    Returns:
        Always 0 (non-blocking hook - failures logged but don't block)
    """
    # Get agent info from environment
    agent_name = os.environ.get("CLAUDE_AGENT_NAME")
    agent_status = os.environ.get("CLAUDE_AGENT_STATUS", "success")

    # Check if workflow should trigger
    if not should_trigger_git_workflow(agent_name):
        # Not the right agent - skip
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop"
            }
        }
        print(json.dumps(output))
        return 0

    # Only trigger on success
    if agent_status != "success":
        log_info(f"Agent {agent_name} completed with status {agent_status}. Skipping git workflow.")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop"
            }
        }
        print(json.dumps(output))
        return 0

    # Check consent
    consent = check_git_workflow_consent()
    if not consent['git_enabled']:
        # Git automation disabled
        log_info("Git automation disabled (AUTO_GIT_ENABLED not set).")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop"
            }
        }
        print(json.dumps(output))
        return 0

    # Get session file (optional - Issue #167)
    session_file = get_session_file_path()
    # Note: session_file can be None - execute_git_workflow handles gracefully

    # Execute git workflow (non-blocking - errors logged but don't fail hook)
    try:
        execute_git_workflow(session_file, consent)
    except Exception as e:
        # Graceful degradation with logging (Issue #167)
        log_warning(f"Unexpected error in git workflow: {e}")

    # Always succeed (non-blocking hook)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop"
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
