#!/usr/bin/env python3
"""
Session Resource Manager - System-wide resource tracking and limits.

Features:
1. Global session registry (/tmp/autonomous-dev-sessions.lock)
2. Auto-cleanup of stale sessions (dead PIDs)
3. Pre-flight health checks before heavy operations
4. Block/warn if resource limits exceeded

Environment Variables:
    RESOURCE_MAX_SESSIONS: Max concurrent sessions (default: 3)
    RESOURCE_PROCESS_WARN_THRESHOLD: Warning threshold (default: 1500)
    RESOURCE_PROCESS_HARD_LIMIT: Hard limit (default: 2000)

Issue: #259
"""

import fcntl
import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False

# Import exceptions
try:
    from exceptions import ResourceError, SessionLimitExceededError, ProcessLimitExceededError
except ImportError:
    import sys
    lib_path = Path(__file__).parent
    sys.path.insert(0, str(lib_path))
    from exceptions import ResourceError, SessionLimitExceededError, ProcessLimitExceededError

# Constants
DEFAULT_REGISTRY_FILE = Path("/tmp/autonomous-dev-sessions.lock")
DEFAULT_MAX_SESSIONS = 3
DEFAULT_PROCESS_WARN_THRESHOLD = 1500
DEFAULT_PROCESS_HARD_LIMIT = 2000


@dataclass
class ResourceConfig:
    """Configuration for resource limits and thresholds.

    Args:
        max_sessions: Maximum concurrent sessions allowed
        process_warn_threshold: Process count warning threshold
        process_hard_limit: Process count hard limit

    Raises:
        ValueError: If validation fails
    """

    max_sessions: int = DEFAULT_MAX_SESSIONS
    process_warn_threshold: int = DEFAULT_PROCESS_WARN_THRESHOLD
    process_hard_limit: int = DEFAULT_PROCESS_HARD_LIMIT

    def __post_init__(self):
        """Validate configuration values."""
        if self.max_sessions < 1:
            raise ValueError("max_sessions must be at least 1")

        if self.process_warn_threshold < 0 or self.process_hard_limit < 0:
            raise ValueError("Process limits must be positive")

        if self.process_warn_threshold >= self.process_hard_limit:
            raise ValueError(
                "process_warn_threshold must be less than process_hard_limit"
            )

    @classmethod
    def load_from_env(cls) -> "ResourceConfig":
        """Load configuration from environment variables.

        Returns:
            ResourceConfig with values from environment or defaults
        """
        return cls(
            max_sessions=int(
                os.environ.get("RESOURCE_MAX_SESSIONS", DEFAULT_MAX_SESSIONS)
            ),
            process_warn_threshold=int(
                os.environ.get(
                    "RESOURCE_PROCESS_WARN_THRESHOLD", DEFAULT_PROCESS_WARN_THRESHOLD
                )
            ),
            process_hard_limit=int(
                os.environ.get("RESOURCE_PROCESS_HARD_LIMIT", DEFAULT_PROCESS_HARD_LIMIT)
            ),
        )


@dataclass
class SessionEntry:
    """Session entry in the registry.

    Args:
        session_id: Unique session identifier
        pid: Process ID of the session
        repo_path: Repository path for the session
        start_time: ISO 8601 timestamp of session start
        estimated_processes: Estimated process count for this session
    """

    session_id: str
    pid: int
    repo_path: str
    start_time: str
    estimated_processes: int = 15

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict representation of SessionEntry
        """
        return asdict(self)


@dataclass
class SessionRegistry:
    """Registry of active sessions.

    Args:
        sessions: List of session entries (SessionEntry objects or dicts)
        last_cleanup: ISO 8601 timestamp of last cleanup (None if never cleaned)
    """

    sessions: List[Any] = field(default_factory=list)
    last_cleanup: Optional[str] = None


@dataclass
class ResourceStatus:
    """Current resource status and limits.

    Args:
        active_sessions: Number of currently active sessions
        max_sessions: Maximum allowed sessions
        total_processes: Total system process count
        process_warn_threshold: Warning threshold for processes
        process_hard_limit: Hard limit for processes
        sessions: List of active SessionEntry objects
        warnings: List of warning messages
    """

    active_sessions: int
    max_sessions: int
    total_processes: int
    process_warn_threshold: int
    process_hard_limit: int
    sessions: List[SessionEntry]
    warnings: List[str] = field(default_factory=list)

    @property
    def thresholds(self) -> Dict[str, int]:
        """Get threshold values as a dictionary.

        Returns:
            Dict with threshold values
        """
        return {
            "max_sessions": self.max_sessions,
            "process_warn_threshold": self.process_warn_threshold,
            "process_hard_limit": self.process_hard_limit,
        }


class SessionResourceManager:
    """System-wide session resource manager.

    Manages session registration, cleanup, and resource limit enforcement.

    Args:
        registry_file: Path to registry file (defaults to /tmp/autonomous-dev-sessions.lock)
        config: Resource configuration (defaults to env-based config)

    Raises:
        ResourceError: If registry_file is a symlink (security)
    """

    def __init__(
        self,
        registry_file: Optional[Path] = None,
        config: Optional[ResourceConfig] = None,
    ):
        """Initialize SessionResourceManager.

        Args:
            registry_file: Path to registry file
            config: Resource configuration
        """
        self.config = config or ResourceConfig.load_from_env()
        self.registry_file = registry_file or DEFAULT_REGISTRY_FILE

        # Security: Reject symlinks (CWE-59)
        if self.registry_file.exists() and self.registry_file.is_symlink():
            raise ResourceError(
                f"Registry file is a symlink (security violation): {self.registry_file}"
            )

        self._lock = threading.RLock()

    def register_session(
        self, repo_path: str, estimated_processes: int = 15
    ) -> str:
        """Register new session.

        Args:
            repo_path: Repository path for the session
            estimated_processes: Estimated process count

        Returns:
            str: Session ID

        Raises:
            ResourceError: If path traversal detected
            SessionLimitExceededError: If max sessions exceeded
        """
        # Validate path (CWE-22)
        if ".." in repo_path:
            raise ResourceError(f"Path traversal detected: {repo_path}")

        with self._lock:
            registry = self._load_registry()
            self._cleanup_stale_sessions_internal(registry)

            # Check session limit
            if len(registry.sessions) >= self.config.max_sessions:
                raise SessionLimitExceededError(
                    f"Maximum sessions ({self.config.max_sessions}) exceeded"
                )

            # Check for existing session from same repo (deduplication)
            # Only deduplicate if same repo AND same PID (stale sessions cleaned above)
            current_pid = os.getpid()
            for session in registry.sessions:
                session_data = session if isinstance(session, dict) else asdict(session)
                if (
                    session_data.get("repo_path") == repo_path
                    and session_data.get("pid") == current_pid
                ):
                    return session_data["session_id"]

            # Create new session
            now = datetime.utcnow()
            session_id = f"session-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            entry = SessionEntry(
                session_id=session_id,
                pid=current_pid,
                repo_path=repo_path,
                start_time=now.isoformat(),
                estimated_processes=estimated_processes,
            )
            registry.sessions.append(entry)
            self._save_registry(registry)
            return session_id

    def unregister_session(self, session_id: str) -> None:
        """Remove session from registry.

        Args:
            session_id: Session ID to unregister
        """
        with self._lock:
            registry = self._load_registry()
            new_sessions = []
            for s in registry.sessions:
                sid = s.session_id if isinstance(s, SessionEntry) else s.get("session_id")
                if sid != session_id:
                    new_sessions.append(s)
            registry.sessions = new_sessions
            registry.last_cleanup = datetime.utcnow().isoformat()
            self._save_registry(registry)

    def check_resource_limits(self, operation: str = "general") -> ResourceStatus:
        """Check resource limits.

        Args:
            operation: Operation name (for logging)

        Returns:
            ResourceStatus with current resource usage

        Raises:
            ProcessLimitExceededError: If hard limit exceeded
        """
        with self._lock:
            registry = self._load_registry()
            self._cleanup_stale_sessions_internal(registry)

            total_processes = self._get_process_count()
            warnings = []

            # Check hard limit
            if total_processes >= self.config.process_hard_limit:
                raise ProcessLimitExceededError(
                    f"Process limit exceeded: {total_processes}/{self.config.process_hard_limit}"
                )

            # Check soft limit (warning only)
            if total_processes >= self.config.process_warn_threshold:
                warnings.append(
                    f"Process count high: {total_processes}/{self.config.process_hard_limit}"
                )

            # Check session capacity
            if len(registry.sessions) >= self.config.max_sessions:
                warnings.append(
                    f"At maximum session capacity ({self.config.max_sessions}/{self.config.max_sessions})"
                )

            # Convert to SessionEntry objects if needed
            sessions = []
            for s in registry.sessions:
                if isinstance(s, SessionEntry):
                    sessions.append(s)
                else:
                    try:
                        sessions.append(SessionEntry(**s))
                    except (TypeError, ValueError):
                        pass

            return ResourceStatus(
                active_sessions=len(registry.sessions),
                max_sessions=self.config.max_sessions,
                total_processes=total_processes,
                process_warn_threshold=self.config.process_warn_threshold,
                process_hard_limit=self.config.process_hard_limit,
                sessions=sessions,
                warnings=warnings,
            )

    def cleanup_stale_sessions(self) -> int:
        """Remove stale sessions.

        Returns:
            int: Count of sessions removed
        """
        with self._lock:
            registry = self._load_registry()
            return self._cleanup_stale_sessions_internal(registry)

    def get_resource_status(self) -> ResourceStatus:
        """Get current resource status without raising exceptions.

        Returns:
            ResourceStatus with current resource usage
        """
        try:
            return self.check_resource_limits()
        except Exception:
            # Return minimal status on error
            return ResourceStatus(
                active_sessions=0,
                max_sessions=self.config.max_sessions,
                total_processes=self._get_process_count(),
                process_warn_threshold=self.config.process_warn_threshold,
                process_hard_limit=self.config.process_hard_limit,
                sessions=[],
                warnings=["Failed to load session registry"],
            )

    def _cleanup_stale_sessions_internal(self, registry: SessionRegistry) -> int:
        """Internal cleanup. Modifies registry in place.

        Args:
            registry: SessionRegistry to clean

        Returns:
            int: Count of sessions removed
        """
        original_count = len(registry.sessions)
        new_sessions = []
        for s in registry.sessions:
            pid = s.pid if isinstance(s, SessionEntry) else s.get("pid", 0)
            if self._is_pid_alive(pid):
                new_sessions.append(s)
        registry.sessions = new_sessions
        removed = original_count - len(registry.sessions)
        # Always update last_cleanup timestamp
        registry.last_cleanup = datetime.utcnow().isoformat()
        if removed > 0 or original_count == 0:
            self._save_registry(registry)
        return removed

    def _is_pid_alive(self, pid: int) -> bool:
        """Check if process is alive.

        Args:
            pid: Process ID to check

        Returns:
            bool: True if process is alive
        """
        # Current process is always alive
        if pid == os.getpid():
            return True

        if not PSUTIL_AVAILABLE:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False
        return psutil.pid_exists(pid)

    def _get_process_count(self) -> int:
        """Get total process count for current user.

        Returns:
            int: Total process count (0 if psutil unavailable)
        """
        if not PSUTIL_AVAILABLE:
            return 0
        try:
            return len(psutil.pids())
        except Exception:
            return 0

    def _load_registry(self) -> SessionRegistry:
        """Load registry from file with locking.

        Returns:
            SessionRegistry: Loaded registry or empty default
        """
        try:
            if not self.registry_file.exists():
                return SessionRegistry()

            with open(self.registry_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    sessions_data = data.get("sessions", [])
                    # Convert dicts to SessionEntry objects
                    sessions = []
                    for s in sessions_data:
                        try:
                            sessions.append(SessionEntry(**s))
                        except (TypeError, ValueError):
                            # Skip invalid entries
                            pass
                    return SessionRegistry(
                        sessions=sessions,
                        last_cleanup=data.get("last_cleanup"),
                    )
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, IOError, PermissionError):
            return SessionRegistry()

    def _save_registry(self, registry: SessionRegistry) -> None:
        """Save registry atomically with locking.

        Args:
            registry: SessionRegistry to save

        Raises:
            ResourceError: If write fails
        """
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert SessionEntry objects to dicts for JSON serialization
            sessions_data = []
            for s in registry.sessions:
                if isinstance(s, SessionEntry):
                    sessions_data.append(s.to_dict())
                else:
                    sessions_data.append(s)

            # Atomic write: temp file + rename
            fd, temp_path = tempfile.mkstemp(
                dir=self.registry_file.parent,
                prefix=".session_registry_",
                suffix=".tmp",
            )
            try:
                data = {
                    "sessions": sessions_data,
                    "last_cleanup": registry.last_cleanup,
                }
                json_data = json.dumps(data, indent=2).encode("utf-8")
                os.write(fd, json_data)
                os.close(fd)

                # Set secure permissions (0o600)
                os.chmod(temp_path, 0o600)

                # Atomic rename
                Path(temp_path).replace(self.registry_file)
            except OSError as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise ResourceError(
                    f"Failed to write registry (disk full or permission error): {e}"
                )
        except Exception as e:
            if not isinstance(e, ResourceError):
                raise ResourceError(f"Failed to save registry: {e}")
            raise
