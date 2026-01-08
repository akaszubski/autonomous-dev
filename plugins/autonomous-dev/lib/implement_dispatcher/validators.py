#!/usr/bin/env python3
"""
Validation functions for implement dispatcher.

Provides validation for:
    - Batch files (existence, readability, content)
    - Issue numbers (positive integers, deduplication)
    - Batch IDs (format, state file existence)
    - Security checks (path traversal, symlinks)

Date: 2026-01-09
Issue: Consolidate /implement, /auto-implement, /batch-implement
Agent: implementer
Status: GREEN (implementation complete)
"""

import os
import re
from pathlib import Path
from typing import List, Optional

# Import module itself for testability
import implement_dispatcher


class ImplementDispatchError(Exception):
    """Exception raised for implement dispatch validation errors."""
    pass


def validate_batch_file(file_path: str) -> None:
    """
    Validate batch features file.

    Args:
        file_path: Path to batch features file

    Raises:
        ImplementDispatchError: If file is invalid

    Validation checks:
        - File exists
        - File is readable
        - File is not empty
        - File contains valid features (not just whitespace)
        - No path traversal (CWE-22)
        - No symlinks (CWE-59)
    """
    if not file_path:
        raise ImplementDispatchError("Batch file path cannot be empty")

    # Security: Check for path traversal (CWE-22)
    if ".." in file_path:
        raise ImplementDispatchError("Path traversal detected in batch file path")

    # Convert to Path object
    path = Path(file_path)

    # Security: Check for symlinks (CWE-59)
    if path.exists() and path.is_symlink():
        raise ImplementDispatchError("Symlink not allowed for batch file (security policy)")

    # Check file exists
    if not path.exists():
        raise ImplementDispatchError(f"Batch file not found: {file_path}")

    # Check file is readable
    if not os.access(path, os.R_OK):
        raise ImplementDispatchError(f"Batch file not readable: {file_path}")

    # Check file is not empty
    if path.stat().st_size == 0:
        raise ImplementDispatchError(f"Batch file is empty: {file_path}")

    # Check file contains valid features (not just whitespace)
    content = path.read_text(encoding='utf-8')
    if not content.strip():
        raise ImplementDispatchError(f"Batch file contains no valid features: {file_path}")


def validate_issue_numbers(issue_numbers: List[int]) -> List[int]:
    """
    Validate and deduplicate GitHub issue numbers.

    Args:
        issue_numbers: List of GitHub issue numbers

    Returns:
        List[int]: Deduplicated list of issue numbers (preserves order)

    Raises:
        ImplementDispatchError: If issue numbers are invalid

    Validation checks:
        - At least one issue number
        - All numbers are positive integers
        - Deduplicates while preserving order
    """
    if not issue_numbers:
        raise ImplementDispatchError("At least one issue number required for batch mode")

    if len(issue_numbers) == 0:
        raise ImplementDispatchError("At least one issue number required for batch mode")

    # Check all numbers are positive integers
    for num in issue_numbers:
        if not isinstance(num, int):
            raise ImplementDispatchError(f"Issue numbers must be integers, got: {type(num)}")
        if num <= 0:
            raise ImplementDispatchError(f"Issue numbers must be positive integers, got: {num}")

    # Deduplicate while preserving order
    seen = set()
    deduplicated = []
    for num in issue_numbers:
        if num not in seen:
            seen.add(num)
            deduplicated.append(num)

    return deduplicated


def validate_batch_id(batch_id: Optional[str]) -> None:
    """
    Validate batch ID format and state file existence.

    Args:
        batch_id: Batch ID to validate

    Raises:
        ImplementDispatchError: If batch ID is invalid

    Validation checks:
        - Not None or empty
        - Valid format: batch_YYYYMMDD_HHMMSS
        - Batch state file exists

    Expected format: batch_20260109_123456
    """
    if batch_id is None:
        raise ImplementDispatchError("Batch ID cannot be None")

    if not batch_id or not batch_id.strip():
        raise ImplementDispatchError("Batch ID cannot be empty")

    # Validate format: batch_YYYYMMDD_HHMMSS
    pattern = r'^batch_\d{8}_\d{6}$'
    if not re.match(pattern, batch_id):
        raise ImplementDispatchError(
            f"Invalid batch ID format: {batch_id} "
            f"(expected format: batch_YYYYMMDD_HHMMSS, e.g., batch_20260109_123456)"
        )

    # Extract date components for validation
    parts = batch_id.split('_')
    if len(parts) != 3:
        raise ImplementDispatchError(f"Invalid batch ID format: {batch_id}")

    date_str = parts[1]
    year = int(date_str[:4])
    month = int(date_str[4:6])
    day = int(date_str[6:8])

    # Basic date validation
    if year < 2020 or year > 2100:
        raise ImplementDispatchError(f"Invalid batch ID format: {batch_id} (invalid year)")
    if month < 1 or month > 12:
        raise ImplementDispatchError(f"Invalid batch ID format: {batch_id} (invalid month)")
    if day < 1 or day > 31:
        raise ImplementDispatchError(f"Invalid batch ID format: {batch_id} (invalid day)")

    # Check if batch state file exists (call via module for testability)
    state_file = implement_dispatcher.get_batch_state_path(batch_id)
    if not state_file.exists():
        raise ImplementDispatchError(
            f"Batch state file not found for {batch_id}. "
            f"Cannot resume non-existent batch."
        )


def get_batch_state_path(batch_id: str) -> Path:
    """
    Get path to batch state file for given batch ID.

    Args:
        batch_id: Batch ID

    Returns:
        Path: Path to batch state file
    """
    # Look for .claude/batch_state.json
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"

    if claude_dir.exists():
        return claude_dir / "batch_state.json"

    # Fallback to current directory
    return cwd / "batch_state.json"


def validate_args(request) -> None:
    """
    Validate ImplementRequest arguments based on mode.

    Args:
        request: ImplementRequest to validate

    Raises:
        ImplementDispatchError: If request is invalid for its mode
    """
    from .modes import ImplementMode

    if request.mode == ImplementMode.FULL_PIPELINE:
        if not request.feature_description:
            raise ImplementDispatchError("Feature description required for FULL_PIPELINE mode")
        if not request.feature_description.strip():
            raise ImplementDispatchError("Feature description cannot be empty or whitespace")

    elif request.mode == ImplementMode.QUICK:
        if not request.feature_description:
            raise ImplementDispatchError("Feature description required for QUICK mode")
        if not request.feature_description.strip():
            raise ImplementDispatchError("Feature description cannot be empty or whitespace")

    elif request.mode == ImplementMode.BATCH:
        # Must have one of: batch_file, issue_numbers, or batch_id
        has_batch_file = request.batch_file is not None
        has_issue_numbers = request.issue_numbers is not None and len(request.issue_numbers) > 0
        has_batch_id = request.batch_id is not None

        # Check for empty issue_numbers list specifically
        if request.issue_numbers is not None and len(request.issue_numbers) == 0:
            raise ImplementDispatchError("At least one issue number required for batch mode")

        if not (has_batch_file or has_issue_numbers or has_batch_id):
            raise ImplementDispatchError(
                "Batch mode requires either a batch file, issue numbers, or batch ID for resume"
            )

        # Validate batch file if provided
        if has_batch_file:
            validate_batch_file(request.batch_file)

        # Validate issue numbers if provided
        if has_issue_numbers:
            request.issue_numbers = validate_issue_numbers(request.issue_numbers)

        # Validate batch ID if provided
        if has_batch_id:
            validate_batch_id(request.batch_id)
