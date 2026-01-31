#!/usr/bin/env python3
"""
Batch Resume Helper for SessionStart Hook (Issue #277)

Python helper that loads RALPH checkpoints for SessionStart hook batch resumption.
Called by SessionStart-batch-recovery.sh after auto-compact to display batch context.

Exit Codes:
    0: Success (valid checkpoint loaded)
    1: Missing checkpoint file
    2: Corrupted JSON
    3: Insecure file permissions
    4: Security violation (path traversal)

Usage:
    python batch_resume_helper.py <batch_id>

Environment Variables:
    CHECKPOINT_DIR: Directory containing checkpoints (default: .ralph-checkpoints)

Output:
    JSON checkpoint data on stdout (exit 0)
    Error message on stderr (exit 1-4)

Security:
    - CWE-22: Path traversal validation
    - File permissions: 0o600 only (owner read/write)
    - Backup fallback on corruption

Date: 2026-01-28
Issue: #277 (Integrate RALPH checkpoint with Claude auto-compact lifecycle)
Agent: implementer
Status: Implementation (TDD green phase)
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional


# =============================================================================
# Security Validation Functions
# =============================================================================

def validate_batch_id(batch_id: str) -> None:
    """
    Validate batch_id for security (CWE-22: Path Traversal).

    Args:
        batch_id: Batch identifier to validate

    Raises:
        ValueError: If batch_id contains path traversal patterns

    Security:
        - Rejects ".." (parent directory)
        - Rejects "/" and "\\" (path separators)
        - Ensures batch_id is a simple identifier
    """
    if ".." in batch_id or "/" in batch_id or "\\" in batch_id:
        raise ValueError(
            f"Invalid batch_id: path traversal detected\n"
            f"batch_id must be a simple identifier without path separators\n"
            f"Received: {batch_id}"
        )


def validate_file_permissions(checkpoint_file: Path) -> None:
    """
    Validate checkpoint file has secure permissions (0o600).

    Args:
        checkpoint_file: Path to checkpoint file

    Raises:
        PermissionError: If file permissions are not 0o600

    Security:
        - Only accepts 0o600 (owner read/write only)
        - Rejects world-readable, group-readable, read-only
        - Prevents information disclosure
    """
    file_mode = checkpoint_file.stat().st_mode & 0o777
    if file_mode != 0o600:
        raise PermissionError(
            f"Checkpoint file has insecure permissions: {oct(file_mode)}\n"
            f"Expected: 0o600 (owner read/write only)\n"
            f"File: {checkpoint_file}\n"
            f"Fix: chmod 600 {checkpoint_file}"
        )


# =============================================================================
# Checkpoint Loading Functions
# =============================================================================

def load_checkpoint_file(checkpoint_file: Path) -> Dict[str, Any]:
    """
    Load checkpoint file with corruption recovery.

    Args:
        checkpoint_file: Path to checkpoint JSON file

    Returns:
        Parsed checkpoint data as dictionary

    Raises:
        json.JSONDecodeError: If both main and backup files are corrupted
        FileNotFoundError: If checkpoint file doesn't exist
        PermissionError: If file permissions are insecure

    Backup Recovery:
        - If main checkpoint is corrupted, attempts .bak file
        - Logs warning to stderr when using backup
    """
    # Validate file permissions first
    validate_file_permissions(checkpoint_file)

    # Attempt to load main checkpoint
    try:
        checkpoint_data = json.loads(checkpoint_file.read_text())
        return checkpoint_data
    except json.JSONDecodeError as e:
        # Try backup file
        backup_file = Path(str(checkpoint_file) + ".bak")
        if backup_file.exists():
            try:
                # Validate backup permissions
                validate_file_permissions(backup_file)

                # Load from backup
                checkpoint_data = json.loads(backup_file.read_text())

                # Warn about using backup
                print(
                    f"WARNING: Main checkpoint corrupted, using backup file\n"
                    f"Main: {checkpoint_file}\n"
                    f"Backup: {backup_file}",
                    file=sys.stderr
                )

                return checkpoint_data
            except (json.JSONDecodeError, PermissionError) as backup_error:
                # Both main and backup corrupted - re-raise original error
                raise

        # No backup available - re-raise original error
        raise


def load_checkpoint(batch_id: str, checkpoint_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load RALPH checkpoint for batch resumption.

    Args:
        batch_id: Batch identifier (e.g., "batch-20260128-123456")
        checkpoint_dir: Directory containing checkpoints (default: from CHECKPOINT_DIR env)

    Returns:
        Checkpoint data as dictionary with keys:
            - batch_id: Batch identifier
            - current_feature_index: Next feature to process (0-indexed)
            - total_features: Total number of features
            - features: List of feature descriptions
            - completed_features: List of completed feature indices
            - failed_features: List of failed feature records
            - status: Batch status ("in_progress", "completed", etc.)

    Raises:
        ValueError: If batch_id contains path traversal
        FileNotFoundError: If checkpoint file not found
        json.JSONDecodeError: If checkpoint is corrupted
        PermissionError: If file permissions are insecure

    Security:
        - CWE-22: Path traversal validation
        - File permissions: 0o600 only
        - JSON-only serialization (no pickle/exec)

    Example:
        >>> checkpoint = load_checkpoint("batch-20260128-123456")
        >>> print(f"Resume at feature {checkpoint['current_feature_index'] + 1}")
        Resume at feature 4
    """
    # Validate batch_id for security (CWE-22)
    validate_batch_id(batch_id)

    # Determine checkpoint directory
    if checkpoint_dir is None:
        from path_utils import get_project_root
        try:
            checkpoint_dir = Path(os.environ.get("CHECKPOINT_DIR", str(get_project_root() / ".ralph-checkpoints")))
        except FileNotFoundError:
            # Fallback if project root detection fails
            checkpoint_dir = Path(os.environ.get("CHECKPOINT_DIR", ".ralph-checkpoints"))

    # Build checkpoint file path
    checkpoint_file = checkpoint_dir / f"ralph-{batch_id}_checkpoint.json"

    # Check if checkpoint exists
    if not checkpoint_file.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_file}\n"
            f"Batch ID: {batch_id}\n"
            f"Checkpoint directory: {checkpoint_dir}"
        )

    # Load checkpoint with corruption recovery
    checkpoint_data = load_checkpoint_file(checkpoint_file)

    return checkpoint_data


# =============================================================================
# CLI Entry Point
# =============================================================================

def main() -> int:
    """
    CLI entry point for batch resume helper.

    Returns:
        Exit code (0=success, 1=missing, 2=corrupted, 3=permissions, 4=security)

    Usage:
        python batch_resume_helper.py <batch_id>

    Environment:
        CHECKPOINT_DIR: Checkpoint directory (default: .ralph-checkpoints)

    Output:
        stdout: JSON checkpoint data (on success)
        stderr: Error messages (on failure)
    """
    # Check arguments
    if len(sys.argv) != 2:
        print(
            "Usage: python batch_resume_helper.py <batch_id>\n"
            "Example: python batch_resume_helper.py batch-20260128-123456",
            file=sys.stderr
        )
        return 1

    batch_id = sys.argv[1]

    try:
        # Load checkpoint
        checkpoint_data = load_checkpoint(batch_id)

        # Output JSON to stdout
        print(json.dumps(checkpoint_data, indent=2))

        return 0

    except json.JSONDecodeError as e:
        # Corrupted JSON (must be before ValueError since JSONDecodeError inherits from ValueError)
        print(f"Error: Checkpoint corrupted - {e}", file=sys.stderr)
        return 2

    except PermissionError as e:
        # Insecure file permissions
        print(f"Error: Insecure permissions - {e}", file=sys.stderr)
        return 3

    except ValueError as e:
        # Security violation (path traversal)
        print(f"Error: Security violation - {e}", file=sys.stderr)
        return 4

    except FileNotFoundError as e:
        # Missing checkpoint
        print(f"Error: Checkpoint not found - {e}", file=sys.stderr)
        return 1

    except Exception as e:
        # Unexpected error
        print(f"Error: Unexpected error - {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
