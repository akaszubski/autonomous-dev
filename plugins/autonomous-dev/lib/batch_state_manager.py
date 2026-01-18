#!/usr/bin/env python3
"""
Batch State Manager - State-based tracking for /implement --batch command.

Manages persistent state for batch feature processing. Enables crash recovery,
resume functionality, and multi-feature batch processing.

DESIGN (v3.34.0): Compaction-resilient - all state is externalized (batch_state.json,
git commits, GitHub issues). Batches survive Claude Code's auto-compaction because
each feature bootstraps fresh from external state, not conversation memory.

Key Features:
1. Persistent state storage (.claude/batch_state.json)
2. Progress tracking (completed, failed, current feature)
3. Atomic writes with file locking
4. Security validations (CWE-22 path traversal, CWE-59 symlinks)
5. Crash recovery and resume

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
    1. /implement --batch reads features.txt
    2. create_batch_state() creates initial state
    3. For each feature:
       a. Process with /implement
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
    from path_utils import get_batch_state_file

    # Create new batch
    state = create_batch_state("/path/to/features.txt", ["feature 1", "feature 2"])
    save_batch_state(get_batch_state_file(), state)

    # Process features
    while True:
        next_feature = get_next_pending_feature(state)
        if next_feature is None:
            break

        # Process feature...

        # Update progress
        update_batch_progress(get_batch_state_file(), state.current_index, "completed", 10000)

        # Check auto-clear
        state = load_batch_state(get_batch_state_file())
        if should_auto_clear(state):
            record_auto_clear_event(get_batch_state_file(), state.current_index, state.context_token_estimate)
            # /clear command...
            state = load_batch_state(get_batch_state_file())

    # Cleanup
    cleanup_batch_state(get_batch_state_file())

Date: 2025-11-16
Issue: #76 (State-based Auto-Clearing for /implement --batch)
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
from path_utils import get_batch_state_file
from abstract_state_manager import StateManager
from exceptions import StateError

# Import sanitization functions
try:
    from failure_classifier import sanitize_feature_name
except ImportError:
    # Fallback for tests
    def sanitize_feature_name(name: str) -> str:
        """Fallback sanitization."""
        return name.replace("\n", " ").replace("\r", " ")

# =============================================================================
# Constants
# =============================================================================

# Default state file location (dynamically resolved from PROJECT_ROOT - Issue #79)
# This fixes hardcoded Path(".claude/batch_state.json") which failed from subdirectories
# WARNING: This evaluates at module import time. For testing with mock project roots,
# use get_default_state_file() function instead (evaluates lazily).
try:
    DEFAULT_STATE_FILE = get_batch_state_file()
except FileNotFoundError:
    # Fallback for edge cases (e.g., running outside a git repo)
    # This maintains backward compatibility
    DEFAULT_STATE_FILE = Path(".claude/batch_state.json")

def get_default_state_file():
    """Get default state file path (lazy evaluation - use in tests).

    This is a function (not a constant) to support testing scenarios where
    the project root might change between test cases.

    For production code, use DEFAULT_STATE_FILE constant for performance.
    For tests, use this function for correct behavior with mock project roots.

    Returns:
        Path to default batch state file (PROJECT_ROOT/.claude/batch_state.json)
    """
    try:
        return get_batch_state_file()
    except FileNotFoundError:
        # Fallback for edge cases (e.g., running outside a git repo)
        # This maintains backward compatibility
        return Path(".claude/batch_state.json")

# File lock timeout (seconds)
LOCK_TIMEOUT = 30

# Auto-clear threshold (tokens) - for backward compatibility with tests
CONTEXT_THRESHOLD = 150 * 1000  # 150K tokens

# =============================================================================
# Exceptions
# =============================================================================

# Backward compatibility: BatchStateError is deprecated, use StateError instead
# This alias will be removed in v4.0.0 (Issue #225)
BatchStateError = StateError


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
        status: Batch status (in_progress/running, paused, completed, failed)
        issue_numbers: Optional list of GitHub issue numbers (for --issues flag)
        source_type: Source type ("file" or "issues")
        state_file: Path to state file
        context_tokens_before_clear: Token count before clear (for paused batches, deprecated)
        paused_at_feature_index: Feature index where batch was paused (deprecated)
        retry_attempts: Dict mapping feature index to retry count (Issue #89)
        git_operations: Dict mapping feature index to git operation results (Issue #93)
            Structure: {feature_index: {operation_type: {success, sha, branch, ...}}}
            Example: {0: {"commit": {"success": True, "sha": "abc123", "branch": "feature/test"}}}
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
    context_tokens_before_clear: Optional[int] = None
    paused_at_feature_index: Optional[int] = None
    retry_attempts: Dict[int, int] = field(default_factory=dict)  # Issue #89: Track retry counts per feature
    git_operations: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # Issue #93: Track git operations per feature
    feature_order: List[int] = field(default_factory=list)  # Issue #157: Optimized execution order
    feature_dependencies: Dict[int, List[int]] = field(default_factory=dict)  # Issue #157: Dependency graph
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)  # Issue #157: Analysis info (stats, timing, etc.)
    # Compaction-resilience: Workflow methodology survives context summarization
    workflow_mode: str = "auto-implement"  # "auto-implement" or "direct" - tells Claude HOW to process features
    workflow_reminder: str = "Use /implement for each feature. Do NOT implement directly."  # Reinjects methodology after compaction
    # Issue #254: Quality persistence tracking
    skipped_features: List[Dict[str, Any]] = field(default_factory=list)  # Skipped feature records
    quality_metrics: Dict[str, Any] = field(default_factory=dict)  # Quality metrics per feature

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class BatchCompletionSummary:
    """Summary of batch completion status (Issue #242).

    Provides clear visibility into what was merged vs pending after batch processing.

    Attributes:
        batch_id: The batch identifier
        total_features: Total features in batch
        completed_count: Number of successfully completed features
        failed_count: Number of failed features
        pending_count: Number of features not yet processed
        completed_features: List of completed feature descriptions
        failed_features: List of (feature, error_message) tuples
        pending_features: List of pending feature descriptions
        worktree_commits: Commits in worktree branch (not yet merged)
        main_commits: Commits already merged to main
        issues_completed: Issue numbers for completed features
        issues_pending: Issue numbers for pending/failed features
        next_steps: List of recommended next actions
        resume_command: Command to resume if pending features exist
    """
    batch_id: str
    total_features: int
    completed_count: int
    failed_count: int
    pending_count: int
    completed_features: List[str]
    failed_features: List[tuple]
    pending_features: List[str]
    worktree_commits: int = 0
    main_commits: int = 0
    issues_completed: List[int] = field(default_factory=list)
    issues_pending: List[int] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    resume_command: str = ""

    def format_summary(self) -> str:
        """Format summary as readable text.

        Returns:
            Multi-line formatted summary string
        """
        lines = [
            f"\n{'=' * 60}",
            "BATCH COMPLETION SUMMARY",
            f"{'=' * 60}",
            f"Batch ID: {self.batch_id}",
            "",
            "FEATURE STATUS:",
            f"  Completed: {self.completed_count}/{self.total_features}",
            f"  Failed:    {self.failed_count}/{self.total_features}",
            f"  Pending:   {self.pending_count}/{self.total_features}",
        ]

        if self.worktree_commits > 0 or self.main_commits > 0:
            lines.extend([
                "",
                "GIT STATUS:",
                f"  Commits in worktree: {self.worktree_commits}",
                f"  Commits in main:     {self.main_commits}",
            ])

        if self.issues_completed:
            lines.extend([
                "",
                f"ISSUES COMPLETED: {', '.join(f'#{n}' for n in self.issues_completed)}",
            ])

        if self.issues_pending:
            lines.extend([
                f"ISSUES PENDING:   {', '.join(f'#{n}' for n in self.issues_pending)}",
            ])

        if self.failed_features:
            lines.extend([
                "",
                "FAILED FEATURES:",
            ])
            for feature, error in self.failed_features:
                lines.append(f"  - {feature[:50]}...")
                lines.append(f"    Error: {error[:80]}")

        if self.next_steps:
            lines.extend([
                "",
                "NEXT STEPS:",
            ])
            for i, step in enumerate(self.next_steps, 1):
                lines.append(f"  {i}. {step}")

        if self.resume_command:
            lines.extend([
                "",
                f"RESUME: {self.resume_command}",
            ])

        lines.append(f"{'=' * 60}\n")
        return "\n".join(lines)


def generate_completion_summary(
    state: BatchState,
    worktree_branch: Optional[str] = None,
    target_branch: str = "master"
) -> BatchCompletionSummary:
    """Generate completion summary for a batch (Issue #242).

    Analyzes batch state and git history to provide comprehensive
    summary of completed vs pending work.

    Args:
        state: BatchState object to analyze
        worktree_branch: Branch name in worktree (for commit comparison)
        target_branch: Target branch for merge comparison (default: master)

    Returns:
        BatchCompletionSummary with status breakdown and next steps

    Examples:
        >>> state = load_batch_state(get_batch_state_file())
        >>> summary = generate_completion_summary(state)
        >>> print(summary.format_summary())
    """
    import subprocess

    # Calculate feature counts
    completed_indices = set(state.completed_features)
    failed_indices = {f["feature_index"] for f in state.failed_features}
    all_indices = set(range(state.total_features))
    pending_indices = all_indices - completed_indices - failed_indices

    # Get feature descriptions
    completed_features = [state.features[i] for i in sorted(completed_indices) if i < len(state.features)]
    pending_features = [state.features[i] for i in sorted(pending_indices) if i < len(state.features)]
    failed_features = [
        (state.features[f["feature_index"]] if f["feature_index"] < len(state.features) else f"Feature {f['feature_index']}",
         f.get("error_message", "Unknown error"))
        for f in state.failed_features
    ]

    # Get issue numbers if available
    issues_completed = []
    issues_pending = []
    if state.issue_numbers:
        for i, issue_num in enumerate(state.issue_numbers):
            if i in completed_indices:
                issues_completed.append(issue_num)
            elif i in pending_indices or i in failed_indices:
                issues_pending.append(issue_num)

    # Count commits in worktree vs main
    worktree_commits = 0
    main_commits = 0
    if worktree_branch:
        try:
            # Commits in worktree not in target
            result = subprocess.run(
                ['git', 'rev-list', '--count', f'{target_branch}..{worktree_branch}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                worktree_commits = int(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            pass

        try:
            # Commits in target since branch point
            result = subprocess.run(
                ['git', 'rev-list', '--count', f'{worktree_branch}..{target_branch}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                main_commits = int(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            pass

    # Generate next steps
    next_steps = []
    if pending_features:
        next_steps.append(f"Resume batch to complete {len(pending_features)} pending features")
    if failed_features:
        next_steps.append(f"Review and retry {len(failed_features)} failed features")
    if worktree_commits > 0:
        next_steps.append(f"Merge worktree to {target_branch} ({worktree_commits} commits)")
        next_steps.append("Push changes to remote")
    if issues_completed:
        next_steps.append(f"Close completed issues: {', '.join(f'#{n}' for n in issues_completed)}")
    if not pending_features and not failed_features and worktree_commits == 0:
        next_steps.append("Batch complete! Clean up worktree if no longer needed")

    # Generate resume command
    resume_command = ""
    if pending_features or failed_features:
        resume_command = f"/implement --resume {state.batch_id}"

    return BatchCompletionSummary(
        batch_id=state.batch_id,
        total_features=state.total_features,
        completed_count=len(completed_indices),
        failed_count=len(failed_indices),
        pending_count=len(pending_indices),
        completed_features=completed_features,
        failed_features=failed_features,
        pending_features=pending_features,
        worktree_commits=worktree_commits,
        main_commits=main_commits,
        issues_completed=issues_completed,
        issues_pending=issues_pending,
        next_steps=next_steps,
        resume_command=resume_command
    )


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
    features_file: Optional[str] = None,  # Keyword-only for explicit features_file
    batch_id: Optional[str] = None,  # Optional custom batch ID
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
        batch_id: Optional custom batch ID (keyword-only)

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
        # Use explicit features_file keyword if provided, otherwise empty
        features_file_path = features_file if features_file is not None else ""
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
            features_file_path = ""
        else:
            # Very unlikely case: both are lists?
            raise BatchStateError("Ambiguous arguments: both features_file and features appear to be lists")
    elif isinstance(features_file_or_features, str) and features_or_none is not None:
        # Old style: create_batch_state(features_file, features)
        features_file_path = features_file_or_features
        features_list = features_or_none
    else:
        raise BatchStateError(
            "Invalid arguments. Use either:\n"
            "  create_batch_state(features_file, features)  # Old style\n"
            "  create_batch_state(features=..., state_file=..., issue_numbers=...)  # New style"
        )

    if not features_list:
        raise BatchStateError("Cannot create batch state with no features")

    # Sanitize feature names (CWE-117 log injection, CWE-22 path traversal)
    sanitized_features = [sanitize_feature_name(f) for f in features_list]

    # Validate features_file path (security) - check for obvious path traversal
    # Note: features_file is just metadata, not actively accessed
    if features_file_path and (".." in features_file_path or features_file_path.startswith("/tmp/../../")):
        raise BatchStateError(f"Invalid features file path: path traversal detected")

    # Validate batch_id for path traversal (CWE-22)
    if batch_id and (".." in batch_id or "/" in batch_id or "\\" in batch_id):
        raise BatchStateError(
            f"Invalid batch_id: contains path traversal or directory separators. "
            f"batch_id must be a simple identifier without path components."
        )

    # Generate unique batch ID with timestamp (including microseconds for uniqueness)
    # Use provided batch_id if given, otherwise generate one
    if not batch_id:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
        batch_id = f"batch-{timestamp}"

    # Create timestamps
    now = datetime.utcnow().isoformat() + "Z"

    return BatchState(
        batch_id=batch_id,
        features_file=features_file_path,
        total_features=len(sanitized_features),
        features=sanitized_features,
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
        context_tokens_before_clear=None,
        paused_at_feature_index=None,
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
        >>> from path_utils import get_batch_state_file
        >>> state = create_batch_state("/path/to/features.txt", ["feature 1"])
        >>> save_batch_state(get_batch_state_file(), state)
    """
    # Convert to Path
    state_file = Path(state_file)

    # Resolve relative paths from PROJECT_ROOT (Issue #79)
    # This ensures "custom/state.json" → PROJECT_ROOT/custom/state.json
    if not state_file.is_absolute():
        from path_utils import get_project_root
        try:
            project_root = get_project_root(use_cache=False)
            state_file = project_root / state_file
        except FileNotFoundError:
            # Fallback: if no project root, use cwd (backward compatibility)
            pass

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
                except OSError as close_error:
                    pass  # Ignore errors closing file descriptor
                try:
                    temp_path.unlink()
                except (OSError, IOError) as unlink_error:
                    pass  # Ignore errors during cleanup
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
        >>> from path_utils import get_batch_state_file
        >>> state = load_batch_state(get_batch_state_file())
        >>> state.batch_id
        'batch-20251116-123456'
    """
    # Convert to Path
    state_file = Path(state_file)

    # Resolve relative paths from PROJECT_ROOT (Issue #79)
    # This ensures "custom/state.json" → PROJECT_ROOT/custom/state.json
    if not state_file.is_absolute():
        from path_utils import get_project_root
        try:
            project_root = get_project_root(use_cache=False)
            state_file = project_root / state_file
        except FileNotFoundError:
            # Fallback: if no project root, use cwd (backward compatibility)
            pass

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

            # Backward compatibility: Add default values for new fields (Issue #77, #88)
            # Old state files (pre-v3.23.0) don't have issue_numbers, source_type, state_file
            if 'issue_numbers' not in data:
                data['issue_numbers'] = None
            if 'source_type' not in data:
                data['source_type'] = 'file'
            if 'state_file' not in data:
                data['state_file'] = str(state_file)
            # Issue #88: Deprecated fields (for backward compatibility with old state files)
            if 'context_tokens_before_clear' not in data:
                data['context_tokens_before_clear'] = None
            if 'paused_at_feature_index' not in data:
                data['paused_at_feature_index'] = None
            # Issue #89: Retry tracking (for backward compatibility with old state files)
            if 'retry_attempts' not in data:
                data['retry_attempts'] = {}
            else:
                # JSON converts integer keys to strings, convert back to int
                data['retry_attempts'] = {int(k): v for k, v in data['retry_attempts'].items()}

            # Issue #93: Git operations tracking (for backward compatibility with old state files)
            if 'git_operations' not in data:
                data['git_operations'] = {}
            else:
                # JSON converts integer keys to strings, convert back to int
                data['git_operations'] = {int(k): v for k, v in data['git_operations'].items()}

            # Compaction-resilience: workflow_mode and workflow_reminder (for backward compatibility)
            if 'workflow_mode' not in data:
                data['workflow_mode'] = 'auto-implement'
            if 'workflow_reminder' not in data:
                data['workflow_reminder'] = 'Use /implement for each feature. Do NOT implement directly.'

            # Issue #254: Quality persistence tracking (for backward compatibility)
            if 'skipped_features' not in data:
                data['skipped_features'] = []
            if 'quality_metrics' not in data:
                data['quality_metrics'] = {}

            # Backward compatibility: Accept both 'running' and 'in_progress' as equivalent
            # (Both are valid active states)

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
    token_delta: Optional[int] = None,  # Backward compatibility alias
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
        token_delta: Alias for context_token_delta (backward compatibility)

    Raises:
        BatchStateError: If update fails
        ValueError: If feature_index is invalid

    Example:
        >>> from path_utils import get_batch_state_file
        >>> update_batch_progress(
        ...     state_file=get_batch_state_file(),
        ...     feature_index=0,
        ...     status="completed",
        ...     context_token_delta=5000,
        ... )
    """
    # Backward compatibility: support both parameter names
    if token_delta is not None:
        context_token_delta = token_delta
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
        >>> from path_utils import get_batch_state_file
        >>> record_auto_clear_event(
        ...     state_file=get_batch_state_file(),
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
        True if context token estimate exceeds threshold (150K tokens)

    Example:
        >>> from path_utils import get_batch_state_file
        >>> state = load_batch_state(get_batch_state_file())
        >>> if should_auto_clear(state):
        ...     # Trigger /clear
        ...     pass
    """
    # Auto-clear threshold: 150K tokens (inline value, no constant needed)
    threshold = 150 * 1000
    return state.context_token_estimate >= threshold


def estimate_context_tokens(text: str) -> int:
    """Estimate token count for text (conservative approach).

    Uses a conservative estimate of 1 token ≈ 4 characters.
    This is intentionally conservative to avoid underestimating.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count (chars / 4)

    Example:
        >>> text = "Hello world! " * 100
        >>> tokens = estimate_context_tokens(text)
        >>> tokens
        325
    """
    if not text:
        return 0

    # Conservative estimate: 1 token ≈ 4 characters
    # This is intentionally conservative to trigger clearing before hitting actual limit
    return len(text) // 4


def get_next_pending_feature(state: BatchState) -> Optional[str]:
    """Get next pending feature to process.

    Skips over features that are:
    - Already completed
    - Already failed (permanent failures)
    - Explicitly skipped via mark_feature_skipped()

    Args:
        state: Batch state

    Returns:
        Next feature description, or None if all features processed/skipped

    Example:
        >>> from path_utils import get_batch_state_file
        >>> state = load_batch_state(get_batch_state_file())
        >>> next_feature = get_next_pending_feature(state)
        >>> if next_feature:
        ...     # Process feature
        ...     pass
    """
    # Build set of indices to skip
    completed_indices = set(state.completed_features)
    failed_indices = {f["feature_index"] for f in state.failed_features}
    skipped_indices = {s["feature_index"] for s in state.skipped_features}

    # Find next processable feature starting from current_index
    for i in range(state.current_index, state.total_features):
        if i not in completed_indices and i not in failed_indices and i not in skipped_indices:
            return state.features[i]

    return None


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
        >>> from path_utils import get_batch_state_file
        >>> cleanup_batch_state(get_batch_state_file())
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


# =============================================================================
# Retry Count Tracking (Issue #89)
# =============================================================================

def get_retry_count(state: BatchState, feature_index: int) -> int:
    """
    Get retry count for a specific feature.

    Args:
        state: Batch state
        feature_index: Index of feature

    Returns:
        Number of retry attempts (0 if never retried)

    Examples:
        >>> state = load_batch_state(state_file)
        >>> retry_count = get_retry_count(state, 0)
        >>> print(f"Feature 0 has been retried {retry_count} times")
    """
    return state.retry_attempts.get(feature_index, 0)


def increment_retry_count(state_file: Path | str, feature_index: int) -> None:
    """
    Increment retry count for a feature.

    Thread-safe update using file locking.

    Args:
        state_file: Path to batch state file
        feature_index: Index of feature to increment

    Examples:
        >>> increment_retry_count(state_file, 0)  # Increment retry count for feature 0
    """
    state_path = Path(state_file)

    with _get_file_lock(state_path):
        # Load current state
        state = load_batch_state(state_path)

        # Increment retry count
        current_count = state.retry_attempts.get(feature_index, 0)
        state.retry_attempts[feature_index] = current_count + 1

        # Update timestamp
        state.updated_at = datetime.utcnow().isoformat() + "Z"

        # Save updated state
        save_batch_state(state_path, state)

        # Audit log
        audit_log("retry_count_incremented", "info", {
            "feature_index": feature_index,
            "new_count": state.retry_attempts[feature_index],
        })


def mark_feature_status(
    state_file: Path | str,
    feature_index: int,
    status: str,
    error_message: Optional[str] = None,
    retry_count: Optional[int] = None,
) -> None:
    """
    Mark feature status (completed or failed) with optional retry tracking.

    Thread-safe update using file locking.

    Args:
        state_file: Path to batch state file
        feature_index: Index of feature to mark
        status: Status ("completed" or "failed")
        error_message: Error message if failed
        retry_count: Optional retry count to record

    Examples:
        >>> mark_feature_status(state_file, 0, "completed")
        >>> mark_feature_status(state_file, 1, "failed", "SyntaxError", retry_count=2)
    """
    state_path = Path(state_file)

    with _get_file_lock(state_path):
        # Load current state
        state = load_batch_state(state_path)

        if status == "completed":
            if feature_index not in state.completed_features:
                state.completed_features.append(feature_index)
            # Remove from failed if it was there (retry succeeded)
            state.failed_features = [
                f for f in state.failed_features
                if f.get("feature_index") != feature_index
            ]

        elif status == "failed":
            # Add to failed list if not already there
            if not any(f.get("feature_index") == feature_index for f in state.failed_features):
                failure_record = {
                    "feature_index": feature_index,
                    "error_message": error_message or "Unknown error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                if retry_count is not None:
                    failure_record["retry_count"] = retry_count
                state.failed_features.append(failure_record)

        # Update timestamp
        state.updated_at = datetime.utcnow().isoformat() + "Z"

        # Save updated state
        save_batch_state(state_path, state)

        # Audit log
        audit_log("feature_status_updated", "info", {
            "feature_index": feature_index,
            "status": status,
            "retry_count": retry_count,
        })


def mark_feature_skipped(
    state_file: Path | str,
    feature_index: int,
    reason: str,
    category: str = "quality_gate"
) -> None:
    """
    Mark a feature as skipped (permanently excluded from batch processing).

    Skipped features will not be retried on batch resume. Use this for:
    - Quality gate failures (security issues, test failures after max retries)
    - Manual exclusions requested by user
    - Features that require manual intervention

    Thread-safe update using file locking.

    Args:
        state_file: Path to batch state file
        feature_index: Index of feature to skip
        reason: Reason for skipping (user-visible message)
        category: Skip category ("quality_gate", "manual", "dependency")

    Raises:
        BatchStateError: If update fails
        ValueError: If feature_index is invalid

    Examples:
        >>> mark_feature_skipped(state_file, 2, "Security audit failed", "quality_gate")
        >>> mark_feature_skipped(state_file, 5, "User requested skip", "manual")
    """
    state_path = Path(state_file)

    with _get_file_lock(state_path):
        # Load current state
        state = load_batch_state(state_path)

        # Validate feature index
        if feature_index < 0 or feature_index >= state.total_features:
            raise BatchStateError(
                f"Invalid feature index: {feature_index} (total: {state.total_features})"
            )

        # Check if already skipped
        if any(s.get("feature_index") == feature_index for s in state.skipped_features):
            return  # Already skipped, no-op

        # Create skip record
        skip_record = {
            "feature_index": feature_index,
            "feature_name": state.features[feature_index] if feature_index < len(state.features) else f"Feature {feature_index}",
            "reason": reason,
            "category": category,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Add to skipped_features
        state.skipped_features.append(skip_record)

        # Update timestamp
        state.updated_at = datetime.utcnow().isoformat() + "Z"

        # Save updated state
        save_batch_state(state_path, state)

        # Audit log
        audit_log("feature_skipped", "info", {
            "batch_id": state.batch_id,
            "feature_index": feature_index,
            "reason": reason,
            "category": category,
        })


# =============================================================================
# Git Operations Tracking (Issue #93)
# =============================================================================

def record_git_operation(
    state: BatchState,
    feature_index: int,
    operation: str,
    success: bool,
    commit_sha: Optional[str] = None,
    branch: Optional[str] = None,
    remote: Optional[str] = None,
    pr_number: Optional[int] = None,
    pr_url: Optional[str] = None,
    error_message: Optional[str] = None,
    **kwargs
) -> BatchState:
    """
    Record git operation result for a feature.

    Updates the state object and returns it (immutable pattern).
    For batch workflow, this tracks commit/push/PR operations per feature.

    Args:
        state: Current batch state
        feature_index: Index of feature being processed
        operation: Operation type ('commit', 'push', 'pr')
        success: Whether operation succeeded
        commit_sha: Commit SHA (for commit operations)
        branch: Branch name
        remote: Remote name (for push operations)
        pr_number: PR number (for pr operations)
        pr_url: PR URL (for pr operations)
        error_message: Error message (for failures)
        **kwargs: Additional metadata

    Returns:
        Updated batch state with git operation recorded

    Examples:
        >>> state = load_batch_state(state_file)
        >>> state = record_git_operation(
        ...     state,
        ...     feature_index=0,
        ...     operation='commit',
        ...     success=True,
        ...     commit_sha='abc123',
        ...     branch='feature/test'
        ... )
        >>> save_batch_state(state_file, state)
    """
    # Validate operation type
    valid_operations = ['commit', 'push', 'pr']
    if operation not in valid_operations:
        raise ValueError(f"Invalid operation: {operation}. Must be one of {valid_operations}")

    # Validate feature_index
    if feature_index < 0 or feature_index >= state.total_features:
        raise ValueError(f"Invalid feature_index: {feature_index} (total: {state.total_features})")

    # Initialize feature git_operations if not exists
    if feature_index not in state.git_operations:
        state.git_operations[feature_index] = {}

    # Build operation record
    operation_record = {
        "success": success,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Add operation-specific metadata
    if commit_sha:
        operation_record["sha"] = commit_sha
    if branch:
        operation_record["branch"] = branch
    if remote:
        operation_record["remote"] = remote
    if pr_number is not None:
        operation_record["number"] = pr_number
    if pr_url:
        operation_record["url"] = pr_url
    if error_message:
        operation_record["error"] = error_message

    # Add any additional metadata from kwargs
    for key, value in kwargs.items():
        if key not in operation_record:
            operation_record[key] = value

    # Record operation
    state.git_operations[feature_index][operation] = operation_record

    # Update timestamp
    state.updated_at = datetime.utcnow().isoformat() + "Z"

    # Audit log
    audit_log("git_operation_recorded", "info", {
        "batch_id": state.batch_id,
        "feature_index": feature_index,
        "operation": operation,
        "success": success,
    })

    return state


def get_feature_git_status(
    state: BatchState,
    feature_index: int
) -> Optional[Dict[str, Any]]:
    """
    Get git operation status for a feature.

    Args:
        state: Current batch state
        feature_index: Index of feature

    Returns:
        Dict of git operations for feature, or None if no operations

    Examples:
        >>> state = load_batch_state(state_file)
        >>> status = get_feature_git_status(state, 0)
        >>> if status:
        ...     commit = status.get('commit', {})
        ...     if commit.get('success'):
        ...         print(f"Commit: {commit['sha']}")
    """
    return state.git_operations.get(feature_index)


def get_feature_git_operations(
    state: BatchState,
    feature_index: int
) -> Optional[Dict[str, Any]]:
    """
    Get git operations for a feature (alias for get_feature_git_status).

    This is an alias for backward compatibility and clarity in tests.

    Args:
        state: Current batch state
        feature_index: Index of feature

    Returns:
        Dict of git operations for feature, or None if no operations

    Examples:
        >>> state = load_batch_state(state_file)
        >>> ops = get_feature_git_operations(state, 0)
        >>> if ops and 'issue_close' in ops:
        ...     close = ops['issue_close']
        ...     print(f"Issue closed: {close.get('success')}")
    """
    return get_feature_git_status(state, feature_index)


# =============================================================================
# BatchStateManager Class (Backward Compatibility Wrapper)
# =============================================================================


class BatchStateManager(StateManager[BatchState]):
    """Object-oriented wrapper for batch state functions.

    Inherits from StateManager ABC to provide standardized state management
    interface while maintaining backward compatibility with existing code.

    Implements abstract methods (load_state, save_state, cleanup_state)
    by delegating to existing batch-specific methods (load_batch_state,
    save_batch_state, cleanup_batch_state).

    Examples:
        >>> manager = BatchStateManager()
        >>> state = manager.create_batch_state(["feature 1", "feature 2"])
        >>> manager.save_batch_state(state)
        >>> loaded = manager.load_batch_state()
    """

    def __init__(self, state_file: Optional[Path] = None):
        """Initialize manager with optional custom state file path.

        Args:
            state_file: Optional custom path for state file.
                       If None, uses default (.claude/batch_state.json)
                       Path is validated for security (CWE-22, CWE-59)

        Raises:
            ValueError: If state_file contains path traversal or is outside project
        """
        self.state_file = state_file if state_file else get_default_state_file()

        # Validate path if provided (security requirement)
        # Use inherited _validate_state_path() helper from StateManager ABC
        if state_file:
            self.state_file = self._validate_state_path(Path(state_file))

        # Create parent directory if it doesn't exist
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def create_batch_state(
        self,
        features: List[str],
        batch_id: Optional[str] = None,
        issue_numbers: Optional[List[int]] = None
    ) -> BatchState:
        """Create new batch state (delegates to create_batch_state function).

        Args:
            features: List of feature descriptions
            batch_id: Optional custom batch ID
            issue_numbers: Optional list of GitHub issue numbers

        Returns:
            BatchState object
        """
        return create_batch_state(
            features=features,
            state_file=str(self.state_file),
            batch_id=batch_id,
            issue_numbers=issue_numbers
        )

    def create_batch(
        self,
        features: List[str],
        features_file: Optional[str] = None,
        batch_id: Optional[str] = None,
        issue_numbers: Optional[List[int]] = None
    ) -> BatchState:
        """Create new batch state (alias for create_batch_state).

        Args:
            features: List of feature descriptions
            features_file: Optional path to features file (for validation)
            batch_id: Optional custom batch ID
            issue_numbers: Optional list of GitHub issue numbers

        Returns:
            BatchState object

        Note:
            If features_file is provided, it is validated for security but not used
            (features list is the actual source of truth)
        """
        # Validate features_file if provided (security requirement)
        if features_file:
            from security_utils import validate_path
            validate_path(Path(features_file), "features file", allow_missing=True)

        return create_batch_state(
            features=features,
            state_file=str(self.state_file),
            batch_id=batch_id,
            issue_numbers=issue_numbers
        )

    def load_batch_state(self) -> BatchState:
        """Load batch state from file (delegates to load_batch_state function).

        Returns:
            BatchState object
        """
        return load_batch_state(self.state_file)

    def save_batch_state(self, state: BatchState) -> None:
        """Save batch state to file.

        Uses inherited _atomic_write() and _get_file_lock() for security
        and thread safety.

        Args:
            state: BatchState object to save
        """
        # Update timestamp
        state.updated_at = datetime.utcnow().isoformat() + "Z"

        # Acquire file lock for thread safety
        lock = self._get_file_lock(self.state_file)
        with lock:
            # Convert state to JSON
            json_data = json.dumps(state.to_dict(), indent=2)

            # Use inherited _atomic_write() for atomic file operations
            self._atomic_write(self.state_file, json_data, mode=0o600)

            # Audit log
            self._audit_operation("batch_state_save", "success", {
                "batch_id": state.batch_id,
                "path": str(self.state_file),
                "features_count": state.total_features,
            })

    def update_batch_progress(
        self,
        feature_index: int,
        status: str,
        tokens_consumed: int = 0
    ) -> None:
        """Update batch progress (delegates to update_batch_progress function).

        Args:
            feature_index: Index of completed feature
            status: "completed" or "failed"
            tokens_consumed: Estimated tokens consumed by this feature
        """
        update_batch_progress(
            self.state_file,
            feature_index,
            status,
            tokens_consumed
        )

    def record_auto_clear_event(
        self,
        feature_index: int,
        tokens_before_clear: int
    ) -> None:
        """Record auto-clear event (delegates to record_auto_clear_event function).

        Args:
            feature_index: Feature index when auto-clear triggered
            tokens_before_clear: Estimated tokens before clearing
        """
        record_auto_clear_event(
            self.state_file,
            feature_index,
            tokens_before_clear
        )

    def should_auto_clear(self) -> bool:
        """Check if auto-clear should trigger (delegates to should_auto_clear function).

        Returns:
            True if context should be cleared
        """
        state = self.load_batch_state()
        return should_auto_clear(state)

    def get_next_pending_feature(self) -> Optional[str]:
        """Get next pending feature (delegates to get_next_pending_feature function).

        Returns:
            Next feature description or None if all complete
        """
        state = self.load_batch_state()
        return get_next_pending_feature(state)

    def cleanup_batch_state(self) -> None:
        """Cleanup batch state file (delegates to cleanup_batch_state function)."""
        cleanup_batch_state(self.state_file)

    # =============================================================================
    # StateManager ABC Abstract Method Implementations (Issue #221)
    # =============================================================================

    def load_state(self) -> BatchState:
        """Implement StateManager.load_state() - delegates to load_batch_state().

        Returns:
            BatchState object loaded from storage

        Raises:
            BatchStateError: If load fails

        Note:
            This implements the StateManager ABC abstract method by delegating
            to the existing load_batch_state() method for backward compatibility.
        """
        return self.load_batch_state()

    def save_state(self, state: BatchState) -> None:
        """Implement StateManager.save_state() - delegates to save_batch_state().

        Args:
            state: BatchState object to save

        Raises:
            BatchStateError: If save fails

        Note:
            This implements the StateManager ABC abstract method by delegating
            to the existing save_batch_state() method for backward compatibility.
        """
        self.save_batch_state(state)

    def cleanup_state(self) -> None:
        """Implement StateManager.cleanup_state() - delegates to cleanup_batch_state().

        Raises:
            BatchStateError: If cleanup fails

        Note:
            This implements the StateManager ABC abstract method by delegating
            to the existing cleanup_batch_state() method for backward compatibility.
        """
        self.cleanup_batch_state()
