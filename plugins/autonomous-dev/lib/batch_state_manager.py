#!/usr/bin/env python3
"""
Batch State Manager - State-based auto-clearing for /batch-implement command.

Manages persistent state for batch feature processing with automatic context clearing
at the 150K token threshold. Enables crash recovery, resume functionality, and
multi-feature batch processing without context bloat.

Key Features:
1. Persistent state storage (.claude/batch_state.json)
2. Auto-clear threshold detection (150K tokens)
3. Progress tracking (completed, failed, current feature)
4. Atomic writes with file locking
5. Security validations (CWE-22 path traversal, CWE-59 symlinks)
6. Crash recovery and resume

State Structure:
    {
        "batch_id": "batch-20251116-123456",
        "features_file": "/path/to/features.txt",
        "total_features": 10,
        "features": ["feature 1", "feature 2", ...],
        "current_index": 3,
        "completed_features": [0, 1, 2],
        "failed_features": [
            {"feature_index": 5, "error_message": "Tests failed", "timestamp": "..."}
        ],
        "context_token_estimate": 145000,
        "auto_clear_count": 2,
        "auto_clear_events": [
            {"feature_index": 2, "tokens_before": 155000, "timestamp": "..."},
            {"feature_index": 5, "tokens_before": 152000, "timestamp": "..."}
        ],
        "created_at": "2025-11-16T10:00:00Z",
        "updated_at": "2025-11-16T14:30:00Z",
        "status": "in_progress"  # in_progress, completed, failed
    }

Workflow:
    1. /batch-implement reads features.txt
    2. create_batch_state() creates initial state
    3. For each feature:
       a. Process with /auto-implement
       b. update_batch_progress() increments current_index
       c. should_auto_clear() checks if threshold exceeded
       d. If yes: record_auto_clear_event() → /clear → resume
    4. cleanup_batch_state() removes state file on completion

Usage:
    from batch_state_manager import (
        create_batch_state,
        load_batch_state,
        save_batch_state,
        update_batch_progress,
        record_auto_clear_event,
        should_auto_clear,
        get_next_pending_feature,
        cleanup_batch_state,
    )

    # Create new batch
    state = create_batch_state("/path/to/features.txt", ["feature 1", "feature 2"])
    save_batch_state(state_file, state)

    # Process features
    while True:
        next_feature = get_next_pending_feature(state)
        if next_feature is None:
            break

        # Process feature...

        # Update progress
        update_batch_progress(state_file, state.current_index, "completed", 10000)

        # Check auto-clear
        state = load_batch_state(state_file)
        if should_auto_clear(state):
            record_auto_clear_event(state_file, state.current_index, state.context_token_estimate)
            # /clear command...
            state = load_batch_state(state_file)

    # Cleanup
    cleanup_batch_state(state_file)

Date: 2025-11-16
Issue: #76 (State-based Auto-Clearing for /batch-implement)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.


Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See state-management-patterns skill for standardized design patterns.
"""

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import security utilities for path validation
import sys
sys.path.insert(0, str(Path(__file__).parent))
from security_utils import validate_path, audit_log

# =============================================================================
# Constants
# =============================================================================

# Default state file location
DEFAULT_STATE_FILE = Path(".claude/batch_state.json")

# Context token threshold for auto-clearing (150K tokens)
CONTEXT_THRESHOLD = 150000

# File lock timeout (seconds)
LOCK_TIMEOUT = 30

# =============================================================================
# Exceptions
# =============================================================================


class BatchStateError(Exception):
    """Base exception for batch state operations."""
    pass


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class BatchState:
    """Batch processing state.

    Attributes:
        batch_id: Unique batch identifier
        features_file: Path to features file
        total_features: Total number of features in batch
        features: List of feature descriptions
        current_index: Index of current feature being processed
        completed_features: List of completed feature indices
        failed_features: List of failed feature records
        context_token_estimate: Estimated context token count
        auto_clear_count: Number of auto-clear events
        auto_clear_events: List of auto-clear event records
        created_at: ISO 8601 timestamp of batch creation
        updated_at: ISO 8601 timestamp of last update
        status: Batch status (in_progress, completed, failed)
        issue_numbers: Optional list of GitHub issue numbers (for --issues flag)
        source_type: Source type ("file" or "issues")
        state_file: Path to state file
    """
    batch_id: str
    features_file: str
    total_features: int
    features: List[str]
    current_index: int = 0
    completed_features: List[int] = field(default_factory=list)
    failed_features: List[Dict[str, Any]] = field(default_factory=list)
    context_token_estimate: int = 0
    auto_clear_count: int = 0
    auto_clear_events: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    status: str = "in_progress"
    issue_numbers: Optional[List[int]] = None
    source_type: str = "file"
    state_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# Thread-safe file lock
_file_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def audit_log_security_event(event_type: str, details: Dict[str, Any]) -> None:
    """Log security event to audit log.

    This is a wrapper around security_utils.audit_log for security events.

    Args:
        event_type: Type of security event
        details: Event details
    """
    audit_log(event_type, "security", details)


def _get_file_lock(file_path: Path) -> threading.RLock:
    """Get or create thread-safe reentrant lock for file.

    Args:
        file_path: Path to file

    Returns:
        Threading reentrant lock for file (allows same thread to acquire multiple times)
    """
    file_key = str(file_path.resolve())
    with _locks_lock:
        if file_key not in _file_locks:
            _file_locks[file_key] = threading.RLock()  # Reentrant lock
        return _file_locks[file_key]


# =============================================================================
# State Creation
# =============================================================================


def create_batch_state(
    features_file_or_features: Optional[str | List[str]] = None,
    features_or_none: Optional[List[str]] = None,
    issue_numbers: Optional[List[int]] = None,
    source_type: str = "file",
    state_file: Optional[str] = None,
    *,
    features: Optional[List[str]] = None,  # Keyword-only for new calling style
) -> BatchState:
    """Create new batch state.

    Supports two calling styles for backward compatibility:
    1. Old style (positional): create_batch_state(features_file, features)
    2. New style (keyword): create_batch_state(features=..., state_file=..., issue_numbers=...)

    Args:
        features_file_or_features: Features file path (old style) OR features list (new style detection)
        features_or_none: Features list (old style) or None (new style)
        issue_numbers: Optional list of GitHub issue numbers (for --issues flag)
        source_type: Source type ("file" or "issues")
        state_file: Optional path to state file
        features: Features list (keyword-only, for new calling style)

    Returns:
        Newly created BatchState

    Raises:
        BatchStateError: If features list is empty or features_file path is invalid

    Examples:
        Old style (backward compatible):
        >>> state = create_batch_state("/path/to/features.txt", ["feature 1", "feature 2"])
        >>> state.source_type
        'file'

        New style (--issues flag):
        >>> state = create_batch_state(
        ...     features=["Issue #72: Add logging"],
        ...     issue_numbers=[72],
        ...     source_type="issues",
        ...     state_file="/path/to/state.json"
        ... )
        >>> state.issue_numbers
        [72]
    """
    # Detect calling style
    if features is not None:
        # New style: features passed as keyword argument
        features_list = features
        features_file = ""  # No file for --issues
    elif features_file_or_features is None and features_or_none is None:
        # Neither positional argument provided - must use keyword 'features'
        raise BatchStateError(
            "Invalid arguments. Use either:\n"
            "  create_batch_state(features_file, features)  # Old style\n"
            "  create_batch_state(features=..., state_file=..., issue_numbers=...)  # New style"
        )
    elif isinstance(features_file_or_features, list):
        # Ambiguous: first arg is a list (could be new style without keyword)
        # Assume new style if features_or_none is None
        if features_or_none is None:
            features_list = features_file_or_features
            features_file = ""
        else:
            # Very unlikely case: both are lists?
            raise BatchStateError("Ambiguous arguments: both features_file and features appear to be lists")
    elif isinstance(features_file_or_features, str) and features_or_none is not None:
        # Old style: create_batch_state(features_file, features)
        features_file = features_file_or_features
        features_list = features_or_none
    else:
        raise BatchStateError(
            "Invalid arguments. Use either:\n"
            "  create_batch_state(features_file, features)  # Old style\n"
            "  create_batch_state(features=..., state_file=..., issue_numbers=...)  # New style"
        )

    if not features_list:
        raise BatchStateError("Cannot create batch state with no features")

    # Validate features_file path (security) - check for obvious path traversal
    # Note: features_file is just metadata, not actively accessed
    if features_file and (".." in features_file or features_file.startswith("/tmp/../../")):
        raise BatchStateError(f"Invalid features file path: path traversal detected")

    # Generate unique batch ID with timestamp (including microseconds for uniqueness)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
    batch_id = f"batch-{timestamp}"

    # Create timestamps
    now = datetime.utcnow().isoformat() + "Z"

    return BatchState(
        batch_id=batch_id,
        features_file=features_file,
        total_features=len(features_list),
        features=features_list,
        current_index=0,
        completed_features=[],
        failed_features=[],
        context_token_estimate=0,
        auto_clear_count=0,
        auto_clear_events=[],
        created_at=now,
        updated_at=now,
        status="in_progress",
        issue_numbers=issue_numbers,
        source_type=source_type,
        state_file=state_file or "",
    )


# =============================================================================
# State Persistence
# =============================================================================


def save_batch_state(state_file: Path | str, state: BatchState) -> None:
    """Save batch state to JSON file (atomic write).

    Uses atomic write pattern (temp file + rename) to prevent corruption.
    File permissions set to 0o600 (owner read/write only).

    Args:
        state_file: Path to state file
        state: Batch state to save

    Raises:
        BatchStateError: If save fails
        ValueError: If path validation fails (CWE-22, CWE-59)

    Security:
        - Validates path with security_utils.validate_path()
        - Rejects symlinks (CWE-59)
        - Prevents path traversal (CWE-22)
        - Atomic write (temp file + rename)
        - File permissions 0o600 (owner only)
        - Audit logging

    Atomic Write Design:
    ====================
    1. CREATE: tempfile.mkstemp() creates .tmp file in same directory
    2. WRITE: JSON data written to .tmp file
    3. RENAME: temp_path.replace(target) atomically renames file

    Failure Scenarios:
    ==================
    - Process crash during write: Temp file left, target unchanged
    - Process crash during rename: Atomic, so target is old or new (not partial)
    - Concurrent writes: Each gets unique temp file (last write wins)

    Example:
        >>> state = create_batch_state("/path/to/features.txt", ["feature 1"])
        >>> save_batch_state(Path(".claude/batch_state.json"), state)
    """
    # Convert to Path
    state_file = Path(state_file)

    # Validate path (security)
    try:
        state_file = validate_path(state_file, "batch state file", allow_missing=True)
    except ValueError as e:
        audit_log("batch_state_save", "error", {
            "error": str(e),
            "path": str(state_file),
        })
        raise BatchStateError(str(e))

    # Update timestamp
    state.updated_at = datetime.utcnow().isoformat() + "Z"

    # Acquire file lock
    lock = _get_file_lock(state_file)
    with lock:
        try:
            # Ensure parent directory exists
            state_file.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: temp file + rename
            temp_fd, temp_path_str = tempfile.mkstemp(
                dir=state_file.parent,
                prefix=".batch_state_",
                suffix=".tmp"
            )
            temp_path = Path(temp_path_str)

            try:
                # Write JSON to temp file
                json_data = json.dumps(state.to_dict(), indent=2)
                os.write(temp_fd, json_data.encode('utf-8'))
                os.close(temp_fd)

                # Set permissions (owner read/write only)
                temp_path.chmod(0o600)

                # Atomic rename
                temp_path.replace(state_file)

                # Audit log
                audit_log("batch_state_save", "success", {
                    "batch_id": state.batch_id,
                    "path": str(state_file),
                    "features_count": state.total_features,
                })

            except Exception as e:
                # Cleanup temp file on error
                try:
                    os.close(temp_fd)
                except:
                    pass
                try:
                    temp_path.unlink()
                except:
                    pass
                raise

        except OSError as e:
            audit_log("batch_state_save", "error", {
                "error": str(e),
                "path": str(state_file),
            })
            # Provide more specific error messages
            error_msg = str(e).lower()
            if "space" in error_msg or "disk full" in error_msg:
                raise BatchStateError(f"Disk space error while saving batch state: {e}")
            elif "permission" in error_msg:
                raise BatchStateError(f"Permission error while saving batch state: {e}")
            else:
                raise BatchStateError(f"Failed to save batch state: {e}")


def load_batch_state(state_file: Path | str) -> BatchState:
    """Load batch state from JSON file.

    Args:
        state_file: Path to state file

    Returns:
        Loaded BatchState

    Raises:
        BatchStateError: If load fails or file doesn't exist
        ValueError: If path validation fails (CWE-22, CWE-59)

    Security:
        - Validates path with security_utils.validate_path()
        - Rejects symlinks (CWE-59)
        - Prevents path traversal (CWE-22)
        - Graceful degradation on corrupted JSON
        - Audit logging

    Example:
        >>> state = load_batch_state(Path(".claude/batch_state.json"))
        >>> state.batch_id
        'batch-20251116-123456'
    """
    # Convert to Path
    state_file = Path(state_file)

    # Validate path (security)
    try:
        state_file = validate_path(state_file, "batch state file", allow_missing=False)
    except ValueError as e:
        audit_log("batch_state_load", "error", {
            "error": str(e),
            "path": str(state_file),
        })
        raise BatchStateError(str(e))

    # Check if file exists
    if not state_file.exists():
        raise BatchStateError(f"Batch state file not found: {state_file}")

    # Acquire file lock
    lock = _get_file_lock(state_file)
    with lock:
        try:
            # Read JSON
            with open(state_file, 'r') as f:
                data = json.load(f)

            # Validate required fields
            required_fields = [
                "batch_id", "features_file", "total_features", "features",
                "current_index", "status"
            ]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise BatchStateError(f"Missing required fields: {missing_fields}")

            # Backward compatibility: Add default values for new fields (Issue #77)
            # Old state files (pre-v3.23.0) don't have issue_numbers, source_type, state_file
            if 'issue_numbers' not in data:
                data['issue_numbers'] = None
            if 'source_type' not in data:
                data['source_type'] = 'file'
            if 'state_file' not in data:
                data['state_file'] = str(state_file)

            # Create BatchState from data
            state = BatchState(**data)

            # Audit log
            audit_log("batch_state_load", "success", {
                "batch_id": state.batch_id,
                "path": str(state_file),
            })

            return state

        except json.JSONDecodeError as e:
            audit_log("batch_state_load", "error", {
                "error": f"Corrupted JSON: {e}",
                "path": str(state_file),
            })
            raise BatchStateError(f"Corrupted batch state file: {e}")
        except OSError as e:
            audit_log("batch_state_load", "error", {
                "error": str(e),
                "path": str(state_file),
            })
            # Provide more specific error messages
            error_msg = str(e).lower()
            if "permission" in error_msg:
                raise BatchStateError(f"Permission error while loading batch state: {e}")
            else:
                raise BatchStateError(f"Failed to load batch state: {e}")


# =============================================================================
# State Updates
# =============================================================================


def update_batch_progress(
    state_file: Path | str,
    feature_index: int,
    status: str,
    context_token_delta: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """Update batch progress after processing a feature.

    This function is thread-safe - it uses file locking to serialize concurrent updates.
    Multiple threads can call this function simultaneously with different feature indices.

    Args:
        state_file: Path to state file
        feature_index: Index of processed feature
        status: Feature status ("completed" or "failed")
        context_token_delta: Tokens added during feature processing
        error_message: Error message if status is "failed"

    Raises:
        BatchStateError: If update fails
        ValueError: If feature_index is invalid

    Example:
        >>> update_batch_progress(
        ...     state_file=Path(".claude/batch_state.json"),
        ...     feature_index=0,
        ...     status="completed",
        ...     context_token_delta=5000,
        ... )
    """
    # Convert to Path
    state_file_path = Path(state_file)

    # Acquire file lock for atomic read-modify-write
    # Using RLock (reentrant) so we can call load_batch_state/save_batch_state
    # which also acquire the same lock
    lock = _get_file_lock(state_file_path)
    with lock:
        # Load current state (lock is reentrant, so this is safe)
        state = load_batch_state(state_file)

        # Validate feature index
        if feature_index < 0 or feature_index >= state.total_features:
            raise BatchStateError(f"Invalid feature index: {feature_index} (total: {state.total_features})")

        # Update state based on status
        if status == "completed":
            if feature_index not in state.completed_features:
                state.completed_features.append(feature_index)
        elif status == "failed":
            failure_record = {
                "feature_index": feature_index,
                "error_message": error_message or "Unknown error",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            state.failed_features.append(failure_record)
        else:
            raise ValueError(f"Invalid status: {status} (must be 'completed' or 'failed')")

        # Update context token estimate
        state.context_token_estimate += context_token_delta

        # Update current_index to max of (current, feature_index + 1)
        # This ensures we track progress even with concurrent updates
        state.current_index = max(state.current_index, feature_index + 1)

        # Update status if all features processed
        if state.current_index >= state.total_features:
            state.status = "completed"

        # Save updated state (lock is reentrant, so this is safe)
        save_batch_state(state_file, state)


def record_auto_clear_event(
    state_file: Path | str,
    feature_index: int,
    context_tokens_before_clear: int,
) -> None:
    """Record auto-clear event in batch state.

    Args:
        state_file: Path to state file
        feature_index: Index of feature that triggered auto-clear
        context_tokens_before_clear: Token count before /clear

    Raises:
        BatchStateError: If record fails

    Example:
        >>> record_auto_clear_event(
        ...     state_file=Path(".claude/batch_state.json"),
        ...     feature_index=2,
        ...     context_tokens_before_clear=155000,
        ... )
    """
    # Load current state
    state = load_batch_state(state_file)

    # Create auto-clear event record
    event = {
        "feature_index": feature_index,
        "context_tokens_before_clear": context_tokens_before_clear,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Update state
    state.auto_clear_events.append(event)
    state.auto_clear_count += 1

    # Reset context token estimate after clear
    state.context_token_estimate = 0

    # Save updated state
    save_batch_state(state_file, state)

    # Audit log
    audit_log("batch_auto_clear", "success", {
        "batch_id": state.batch_id,
        "feature_index": feature_index,
        "tokens_before": context_tokens_before_clear,
        "clear_count": state.auto_clear_count,
    })


# =============================================================================
# State Queries
# =============================================================================


def should_auto_clear(state: BatchState) -> bool:
    """Check if context should be auto-cleared.

    Args:
        state: Batch state

    Returns:
        True if context token estimate exceeds threshold

    Example:
        >>> state = load_batch_state(Path(".claude/batch_state.json"))
        >>> if should_auto_clear(state):
        ...     # Trigger /clear
        ...     pass
    """
    return state.context_token_estimate >= CONTEXT_THRESHOLD


def get_next_pending_feature(state: BatchState) -> Optional[str]:
    """Get next pending feature to process.

    Args:
        state: Batch state

    Returns:
        Next feature description, or None if all features processed

    Example:
        >>> state = load_batch_state(Path(".claude/batch_state.json"))
        >>> next_feature = get_next_pending_feature(state)
        >>> if next_feature:
        ...     # Process feature
        ...     pass
    """
    if state.current_index >= state.total_features:
        return None
    return state.features[state.current_index]


# =============================================================================
# State Cleanup
# =============================================================================


def cleanup_batch_state(state_file: Path | str) -> None:
    """Remove batch state file safely.

    Args:
        state_file: Path to state file

    Raises:
        BatchStateError: If cleanup fails

    Example:
        >>> cleanup_batch_state(Path(".claude/batch_state.json"))
    """
    # Convert to Path
    state_file = Path(state_file)

    # Validate path (security)
    try:
        state_file = validate_path(state_file, "batch state file", allow_missing=True)
    except ValueError as e:
        audit_log("batch_state_cleanup", "error", {
            "error": str(e),
            "path": str(state_file),
        })
        raise BatchStateError(str(e))

    # Acquire file lock
    lock = _get_file_lock(state_file)
    with lock:
        try:
            if state_file.exists():
                state_file.unlink()
                audit_log("batch_state_cleanup", "success", {
                    "path": str(state_file),
                })
        except OSError as e:
            audit_log("batch_state_cleanup", "error", {
                "error": str(e),
                "path": str(state_file),
            })
            raise BatchStateError(f"Failed to cleanup batch state: {e}")
