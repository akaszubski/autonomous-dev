#!/usr/bin/env python3
"""
Workflow Violation Logger - Audit logging for workflow enforcement violations.

This module provides comprehensive audit logging for workflow violations detected
by hooks enforcing the /implement workflow. It implements security best practices:

1. JSON Lines format (one event per line for easy parsing)
2. Log injection prevention (CWE-117)
3. Log rotation (10MB max size, keep 10 backups)
4. Thread-safe logging (concurrent hook executions)
5. Structured logging fields (timestamp, violation_type, file_path, agent, reason)

Security Features:
- CWE-117 prevention: Sanitize all user input before logging
- Audit trail integrity: Immutable JSON lines format
- Log rotation: Prevent disk exhaustion
- Thread-safe: Safe for concurrent hook executions

Usage:
    from workflow_violation_logger import WorkflowViolationLogger, ViolationType

    # Initialize logger
    logger = WorkflowViolationLogger()

    # Log direct implementation violation
    logger.log_violation(
        violation_type=ViolationType.DIRECT_IMPLEMENTATION,
        file_path="module.py",
        agent_name="researcher",
        reason="New Python function detected",
        details="def authenticate_user():"
    )

    # Log git bypass attempt
    logger.log_git_bypass_attempt(
        command="git commit --no-verify -m 'bypass hooks'",
        agent_name="researcher",
        reason="--no-verify flag detected"
    )

Date: 2026-01-19
Issue: #250 (Enforce /implement workflow)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

import json
import re
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional


# Default violation log file location
DEFAULT_LOG_FILE = Path(__file__).parent.parent.parent.parent / "logs" / "workflow_violations.log"

# Log injection prevention patterns (CWE-117)
# All control characters from \x00 to \x1f except \t (tab is visible)
INJECTION_CHARS = [chr(i) for i in range(0x00, 0x20) if i != 0x09]  # Exclude tab (0x09)


class ViolationType(Enum):
    """Types of workflow violations."""

    DIRECT_IMPLEMENTATION = "direct_implementation"
    GIT_BYPASS_ATTEMPT = "git_bypass_attempt"
    PROTECTED_PATH_EDIT = "protected_path_edit"


@dataclass
class ViolationLogEntry:
    """Structured violation log entry.

    Attributes:
        timestamp: ISO 8601 timestamp with timezone
        violation_type: Type of violation (direct_implementation, git_bypass_attempt, protected_path_edit)
        file_path: Path to file being modified (optional)
        agent_name: Name of agent that triggered violation
        reason: Human-readable explanation of violation
        details: Additional details about violation
        command: Git command for git_bypass_attempt violations (optional)
    """

    timestamp: str
    violation_type: str
    agent_name: str
    reason: str
    details: str = ""
    file_path: Optional[str] = None
    command: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values.

        Returns:
            Dictionary representation
        """
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ViolationLogEntry":
        """Create ViolationLogEntry from dictionary.

        Args:
            data: Dictionary with log entry fields

        Returns:
            ViolationLogEntry instance
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class WorkflowViolationLogger:
    """Logger for workflow violations.

    This class provides thread-safe audit logging with:
    - JSON Lines format (one event per line)
    - Log injection prevention (CWE-117)
    - Log rotation (10MB max, 10 backups)

    Thread-safe: Uses threading.Lock for concurrent access.

    Example:
        >>> logger = WorkflowViolationLogger()
        >>> logger.log_violation(
        ...     violation_type=ViolationType.DIRECT_IMPLEMENTATION,
        ...     file_path="module.py",
        ...     agent_name="researcher",
        ...     reason="New function detected",
        ...     details="def authenticate():"
        ... )
    """

    def __init__(self, log_file: Optional[Path] = None, max_size_mb: int = 10):
        """Initialize WorkflowViolationLogger.

        Args:
            log_file: Path to violation log file (default: logs/workflow_violations.log)
            max_size_mb: Maximum log file size in MB before rotation (default: 10)
        """
        self.log_file = log_file or DEFAULT_LOG_FILE
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_backups = 10
        self._lock = threading.Lock()
        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self) -> None:
        """Create log file and parent directories if they don't exist."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_file.exists():
            self.log_file.touch()

    def _should_rotate(self) -> bool:
        """Check if log file should be rotated.

        Returns:
            True if file size exceeds max_size_bytes
        """
        try:
            return self.log_file.stat().st_size >= self.max_size_bytes
        except FileNotFoundError:
            return False

    def rotate_log(self) -> None:
        """Rotate log file if size limit is reached.

        Renames current log to workflow_violations.log.YYYYMMDD_HHMMSS
        and creates new empty log file.
        """
        with self._lock:
            if not self.log_file.exists():
                return

            # Generate timestamp suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_file = self.log_file.parent / f"{self.log_file.name}.{timestamp}"

            # Rename current log
            self.log_file.rename(rotated_file)

            # Create new log file
            self.log_file.touch()

            # Clean up old rotated files (keep only max_backups)
            self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """Remove old rotated log files, keeping only max_backups most recent."""
        rotated_files = sorted(
            self.log_file.parent.glob(f"{self.log_file.name}.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Remove files beyond max_backups
        for old_file in rotated_files[self.max_backups:]:
            try:
                old_file.unlink()
            except OSError:
                pass

    def log_violation(
        self,
        violation_type: ViolationType,
        file_path: str,
        agent_name: str,
        reason: str,
        details: str = "",
    ) -> None:
        """Log workflow violation.

        Args:
            violation_type: Type of violation
            file_path: Path to file being modified
            agent_name: Name of agent that triggered violation
            reason: Human-readable explanation
            details: Additional details
        """
        # Sanitize inputs to prevent log injection
        sanitized_file_path = sanitize_log_input(file_path)
        sanitized_reason = sanitize_log_input(reason)
        sanitized_details = sanitize_log_input(details)

        # Create log entry
        entry = ViolationLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            violation_type=violation_type.value,
            file_path=sanitized_file_path,
            agent_name=agent_name,
            reason=sanitized_reason,
            details=sanitized_details,
        )

        self._write_log_entry(entry)

    def log_git_bypass_attempt(
        self,
        command: str,
        agent_name: str,
        reason: str,
    ) -> None:
        """Log git bypass attempt.

        Args:
            command: Git command that attempted bypass
            agent_name: Name of agent that attempted bypass
            reason: Human-readable explanation
        """
        # Sanitize inputs
        sanitized_command = sanitize_log_input(command)
        sanitized_reason = sanitize_log_input(reason)

        # Create log entry
        entry = ViolationLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            violation_type=ViolationType.GIT_BYPASS_ATTEMPT.value,
            agent_name=agent_name,
            reason=sanitized_reason,
            details="",
            command=sanitized_command,
        )

        self._write_log_entry(entry)

    def _write_log_entry(self, entry: ViolationLogEntry) -> None:
        """Write log entry to file (thread-safe).

        Args:
            entry: Log entry to write
        """
        with self._lock:
            try:
                # Check if rotation is needed
                if self._should_rotate():
                    self.rotate_log()

                # Write JSON line
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry.to_dict()) + '\n')
            except (OSError, PermissionError):
                # Graceful degradation - don't block workflow if logging fails
                pass


def sanitize_log_input(text: str) -> str:
    """Sanitize text input to prevent log injection (CWE-117).

    Removes newlines, carriage returns, and control characters that could
    be used to inject fake log entries or break log parsing.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text with injection characters replaced by spaces
    """
    sanitized = text

    # Remove individual injection characters
    for char in INJECTION_CHARS:
        sanitized = sanitized.replace(char, ' ')

    # Remove ANSI escape sequences
    ansi_escape_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    sanitized = ansi_escape_pattern.sub(' ', sanitized)

    return sanitized


def parse_violation_log(
    log_file: Optional[Path] = None,
    violation_type_filter: Optional[str] = None,
    agent_filter: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[ViolationLogEntry]:
    """Parse violation log file into structured entries.

    Args:
        log_file: Path to violation log file (default: logs/workflow_violations.log)
        violation_type_filter: Filter by violation type
        agent_filter: Filter by agent name
        start_time: Filter by start time (inclusive)
        end_time: Filter by end time (inclusive)

    Returns:
        List of ViolationLogEntry objects matching filters
    """
    log_file = log_file or DEFAULT_LOG_FILE

    if not log_file.exists():
        return []

    entries = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                entry = ViolationLogEntry.from_dict(data)

                # Apply filters
                if violation_type_filter and entry.violation_type != violation_type_filter:
                    continue

                if agent_filter and entry.agent_name != agent_filter:
                    continue

                if start_time or end_time:
                    entry_time = datetime.fromisoformat(entry.timestamp)
                    if start_time and entry_time < start_time:
                        continue
                    if end_time and entry_time > end_time:
                        continue

                entries.append(entry)
            except (json.JSONDecodeError, TypeError, ValueError):
                # Skip malformed lines
                continue

    return entries


def get_violation_summary(log_file: Optional[Path] = None) -> Dict[str, Any]:
    """Get summary statistics for violation log.

    Args:
        log_file: Path to violation log file (default: logs/workflow_violations.log)

    Returns:
        Dictionary with summary statistics:
        - total_violations: Total number of violations
        - by_type: Count by violation type
        - by_agent: Count by agent name
        - earliest_violation: Timestamp of earliest violation
        - latest_violation: Timestamp of latest violation
    """
    entries = parse_violation_log(log_file)

    if not entries:
        return {
            "total_violations": 0,
            "by_type": {},
            "by_agent": {},
        }

    # Count by type
    by_type: Dict[str, int] = {}
    for entry in entries:
        by_type[entry.violation_type] = by_type.get(entry.violation_type, 0) + 1

    # Count by agent
    by_agent: Dict[str, int] = {}
    for entry in entries:
        by_agent[entry.agent_name] = by_agent.get(entry.agent_name, 0) + 1

    # Get time range
    timestamps = [datetime.fromisoformat(entry.timestamp) for entry in entries]
    earliest = min(timestamps).isoformat()
    latest = max(timestamps).isoformat()

    return {
        "total_violations": len(entries),
        "by_type": by_type,
        "by_agent": by_agent,
        "earliest_violation": earliest,
        "latest_violation": latest,
    }


# Convenience functions for direct usage

# Global logger instance (lazy initialization)
_global_logger: Optional[WorkflowViolationLogger] = None
_global_logger_lock = threading.Lock()


def _get_global_logger() -> WorkflowViolationLogger:
    """Get or create global logger instance.

    Returns:
        Global WorkflowViolationLogger instance
    """
    global _global_logger, _global_logger_lock

    with _global_logger_lock:
        if _global_logger is None:
            _global_logger = WorkflowViolationLogger()
        return _global_logger


def log_workflow_violation(
    violation_type: ViolationType,
    file_path: str,
    agent_name: str,
    reason: str,
    details: str = "",
) -> None:
    """Log workflow violation (convenience function).

    Args:
        violation_type: Type of violation
        file_path: Path to file being modified
        agent_name: Name of agent
        reason: Human-readable explanation
        details: Additional details
    """
    logger = _get_global_logger()
    logger.log_violation(violation_type, file_path, agent_name, reason, details)


def log_git_bypass_attempt(
    command: str,
    agent_name: str,
    reason: str,
) -> None:
    """Log git bypass attempt (convenience function).

    Args:
        command: Git command
        agent_name: Name of agent
        reason: Human-readable explanation
    """
    logger = _get_global_logger()
    logger.log_git_bypass_attempt(command, agent_name, reason)
