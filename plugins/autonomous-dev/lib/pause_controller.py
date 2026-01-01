#!/usr/bin/env python3
"""
Pause Controller - File-based signaling for autonomous workflow control.

This module provides human-in-the-loop (HITL) controls for autonomous workflows
using file-based signaling. Enables pausing workflows, providing human input,
and resuming with checkpoint state.

Files:
    .claude/PAUSE - Touch to pause workflow at next checkpoint
    .claude/HUMAN_INPUT.md - Write instructions/questions for the workflow
    .claude/pause_checkpoint.json - Checkpoint state for resume

Security:
    - CWE-22: Path traversal prevention
    - CWE-59: Symlink attack prevention
    - File size limits (1MB max for human input)
    - Path validation for all operations

Workflow:
    1. User creates .claude/PAUSE file to pause at next checkpoint
    2. Optionally: User writes .claude/HUMAN_INPUT.md with instructions
    3. Workflow checks check_pause_requested() at checkpoints
    4. If paused: save_checkpoint() saves current state
    5. Workflow reads read_human_input() for instructions
    6. User provides feedback/approval
    7. User calls clear_pause_state() to resume
    8. Workflow loads load_checkpoint() to continue

Usage:
    from pause_controller import (
        check_pause_requested,
        read_human_input,
        clear_pause_state,
        save_checkpoint,
        load_checkpoint,
        validate_pause_path,
    )

    # In workflow at checkpoint
    if check_pause_requested():
        # Save current state
        save_checkpoint("agent_name", {"step": 3, "data": "..."})

        # Read any human input
        human_input = read_human_input()
        if human_input:
            print(f"Human input: {human_input}")

        # Wait for user to clear pause
        print("Paused. Remove .claude/PAUSE to resume.")
        return

    # On resume
    checkpoint = load_checkpoint()
    if checkpoint:
        # Resume from saved state
        step = checkpoint.get("step", 0)

Date: 2026-01-02
Issue: #182 (Pause controls with PAUSE file and HUMAN_INPUT.md)
Agent: implementer
Phase: TDD Green (making tests pass)

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See state-management-patterns skill for standardized design patterns.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any


# File size limit for human input (1MB max - DoS prevention)
MAX_HUMAN_INPUT_SIZE = 1024 * 1024  # 1MB


def _get_claude_dir() -> Optional[Path]:
    """Get .claude directory path if it exists.

    Returns:
        Path to .claude directory or None if not found
    """
    # Check current directory first
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"

    if claude_dir.exists() and claude_dir.is_dir():
        return claude_dir

    # Search up to 5 levels up for .claude directory
    current = cwd
    for _ in range(5):
        current = current.parent
        claude_dir = current / ".claude"
        if claude_dir.exists() and claude_dir.is_dir():
            return claude_dir
        if current.parent == current:  # Reached filesystem root
            break

    return None


def validate_pause_path(path: str) -> bool:
    """Validate path for pause-related file operations.

    Security validations:
    - CWE-22: Reject path traversal attempts (..)
    - CWE-59: Reject symlinks
    - Ensure path is within .claude/ directory
    - Block null bytes

    Args:
        path: Path to validate

    Returns:
        True if path is valid and safe

    Raises:
        ValueError: If path validation fails (path traversal, symlink, etc.)
    """
    try:
        # Block null bytes (CWE-158)
        if "\x00" in path:
            raise ValueError("Null byte detected in path")

        # Convert to Path object
        path_obj = Path(path)

        # Check for path traversal in string (defense in depth)
        if ".." in str(path):
            raise ValueError("Path traversal detected")

        # Resolve to absolute path (CWE-22 prevention)
        try:
            resolved_path = path_obj.resolve(strict=False)
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Cannot resolve path: {e}")

        # Check for symlink (CWE-59 prevention)
        if path_obj.exists() and path_obj.is_symlink():
            raise ValueError("Symlink detected")

        # Ensure path is within .claude directory
        claude_dir = _get_claude_dir()
        if claude_dir is None:
            raise ValueError("No .claude directory found")

        resolved_claude = claude_dir.resolve()

        # Check if path is within .claude directory
        try:
            resolved_path.relative_to(resolved_claude)
        except ValueError:
            # Path is outside .claude directory (path traversal attempt)
            raise ValueError("Path traversal detected")

        return True

    except ValueError:
        # Re-raise ValueError as-is
        raise
    except Exception as e:
        raise ValueError(f"Path validation failed: {e}")


def check_pause_requested() -> bool:
    """Check if pause is requested via .claude/PAUSE file.

    Returns:
        True if PAUSE file exists, False otherwise

    Security:
        - Rejects symlinks (CWE-59)
        - Returns False if .claude dir doesn't exist
    """
    try:
        claude_dir = _get_claude_dir()
        if claude_dir is None:
            return False

        pause_file = claude_dir / "PAUSE"

        # Check if file exists
        if not pause_file.exists():
            return False

        # Reject symlinks (CWE-59)
        if pause_file.is_symlink():
            return False

        # Validate path (defense in depth)
        try:
            validate_pause_path(str(pause_file))
        except ValueError:
            return False

        return True

    except Exception:
        return False


def read_human_input() -> Optional[str]:
    """Read content from .claude/HUMAN_INPUT.md file.

    Returns:
        File content as string, or None if file doesn't exist
        Content is truncated to 1MB max (DoS prevention)

    Security:
        - Rejects symlinks (CWE-59)
        - 1MB size limit (DoS prevention)
        - Handles unicode properly
        - Returns None on permission errors
    """
    try:
        claude_dir = _get_claude_dir()
        if claude_dir is None:
            return None

        human_input_file = claude_dir / "HUMAN_INPUT.md"

        # Check if file exists
        if not human_input_file.exists():
            return None

        # Reject symlinks (CWE-59)
        if human_input_file.is_symlink():
            return None

        # Validate path (defense in depth)
        try:
            validate_pause_path(str(human_input_file))
        except ValueError:
            return None

        # Check file size (DoS prevention)
        try:
            file_size = human_input_file.stat().st_size
            if file_size > MAX_HUMAN_INPUT_SIZE:
                # Truncate to max size
                with open(human_input_file, "r", encoding="utf-8") as f:
                    return f.read(MAX_HUMAN_INPUT_SIZE)
        except OSError:
            return None

        # Read file content
        try:
            content = human_input_file.read_text(encoding="utf-8")
            return content
        except (OSError, PermissionError, UnicodeDecodeError):
            return None

    except Exception:
        return None


def clear_pause_state() -> None:
    """Remove PAUSE, HUMAN_INPUT.md, and pause_checkpoint.json files.

    Idempotent - no error if files don't exist.

    Security:
        - Validates paths before deletion
        - Only removes PAUSE, HUMAN_INPUT.md, and pause_checkpoint.json
        - Never follows symlinks
    """
    try:
        claude_dir = _get_claude_dir()
        if claude_dir is None:
            return

        # Remove PAUSE file
        pause_file = claude_dir / "PAUSE"
        if pause_file.exists() and not pause_file.is_symlink():
            try:
                validate_pause_path(str(pause_file))
                pause_file.unlink()
            except (ValueError, OSError, PermissionError):
                pass  # Ignore errors, idempotent

        # Remove HUMAN_INPUT.md file
        human_input_file = claude_dir / "HUMAN_INPUT.md"
        if human_input_file.exists() and not human_input_file.is_symlink():
            try:
                validate_pause_path(str(human_input_file))
                human_input_file.unlink()
            except (ValueError, OSError, PermissionError):
                pass  # Ignore errors, idempotent

        # Remove pause_checkpoint.json file
        checkpoint_file = claude_dir / "pause_checkpoint.json"
        if checkpoint_file.exists() and not checkpoint_file.is_symlink():
            try:
                validate_pause_path(str(checkpoint_file))
                checkpoint_file.unlink()
            except (ValueError, OSError, PermissionError):
                pass  # Ignore errors, idempotent

    except Exception:
        pass  # Idempotent - always succeeds


def save_checkpoint(agent_name: str, state: Dict[str, Any]) -> None:
    """Save checkpoint state to .claude/pause_checkpoint.json.

    Args:
        agent_name: Name of the agent saving checkpoint
        state: State dictionary to save

    Security:
        - Atomic write (write to temp, then rename)
        - Validates agent_name is string
        - Path validation

    Note:
        Overwrites existing checkpoint file
    """
    try:
        # Validate agent_name
        if not isinstance(agent_name, str):
            raise ValueError("agent_name must be a string")

        claude_dir = _get_claude_dir()
        if claude_dir is None:
            raise RuntimeError("No .claude directory found")

        checkpoint_file = claude_dir / "pause_checkpoint.json"

        # Validate path (raises ValueError if invalid)
        validate_pause_path(str(checkpoint_file))

        # Build checkpoint data
        checkpoint_data = {
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **state,  # Merge state into checkpoint
        }

        # Atomic write: write to temp file, then rename
        import tempfile
        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(claude_dir),
            prefix=".pause_checkpoint_",
            suffix=".tmp"
        )

        try:
            # Write JSON to temp file
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

            # Rename to final location (atomic on POSIX)
            os.replace(temp_path, str(checkpoint_file))

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise

    except Exception:
        # Re-raise for now - tests may expect exceptions
        raise


def load_checkpoint() -> Optional[Dict[str, Any]]:
    """Load checkpoint from .claude/pause_checkpoint.json.

    Returns:
        Checkpoint data as dictionary, or None if:
        - File doesn't exist
        - JSON is invalid
        - File is empty

    Security:
        - Validates path before reading
        - Handles corrupted JSON gracefully
    """
    try:
        claude_dir = _get_claude_dir()
        if claude_dir is None:
            return None

        checkpoint_file = claude_dir / "pause_checkpoint.json"

        # Check if file exists
        if not checkpoint_file.exists():
            return None

        # Validate path
        try:
            validate_pause_path(str(checkpoint_file))
        except ValueError:
            return None

        # Read and parse JSON
        try:
            content = checkpoint_file.read_text(encoding="utf-8")

            # Handle empty file
            if not content.strip():
                return None

            data = json.loads(content)
            return data

        except (json.JSONDecodeError, UnicodeDecodeError):
            # Invalid JSON or encoding - return None
            return None
        except (OSError, PermissionError):
            # Permission or I/O error - return None
            return None

    except Exception:
        return None
