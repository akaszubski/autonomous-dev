#!/usr/bin/env python3
"""
Unified Session Tracker Hook - Dispatcher for SubagentStop Session Tracking

Consolidates SubagentStop session tracking hooks:
- session_tracker.py (basic session logging)
- log_agent_completion.py (structured pipeline tracking)
- auto_update_project_progress.py (PROJECT.md progress updates)

Hook: SubagentStop (runs when a subagent completes)

Input: JSON via stdin (provided by Claude Code SubagentStop hook).
Fields: agent_type, agent_id, agent_transcript_path, last_assistant_message,
        session_id, hook_event_name, stop_hook_active.

Environment Variables (opt-in/opt-out):
    TRACK_SESSIONS=true/false (default: true)
    TRACK_PIPELINE=true/false (default: true)
    AUTO_UPDATE_PROGRESS=true/false (default: false)

Exit codes:
    0: Always (non-blocking hook)

Usage:
    # As SubagentStop hook (automatic via stdin)
    echo '{"agent_type":"researcher",...}' | python unified_session_tracker.py
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


# Issue #970: defensive hook_recovery import for telemetry on stage advance.
try:
    from hook_recovery import log_block_with_recovery as _log_block_with_recovery_970
except ImportError:
    def _log_block_with_recovery_970(**kwargs):
        return None


import glob
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


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

# Optional imports with graceful fallback
try:
    from agent_tracker import AgentTracker
    HAS_AGENT_TRACKER = True
except ImportError:
    HAS_AGENT_TRACKER = False

try:
    from project_md_updater import ProjectMdUpdater
    HAS_PROJECT_UPDATER = True
except ImportError:
    HAS_PROJECT_UPDATER = False

try:
    from version_reader import get_plugin_version
    HAS_VERSION_READER = True
except ImportError:
    HAS_VERSION_READER = False

# Issue #1206: per-repo sentinel path resolver. Imported from lib.pipeline_state
# so the hook subprocess uses the same path the coordinator uses (CWD-inherited).
try:
    from pipeline_state import get_legacy_sentinel_path  # type: ignore
except ImportError:
    def get_legacy_sentinel_path(repo_root=None):  # type: ignore
        return Path("/tmp/implement_pipeline_state.json")

# Issue #1087: subagent invocation cache for recovering missing
# agent_type and duration_ms in SubagentStop payloads. Cache writes
# happen in session_activity_logger.py on PreToolUse; we read here.
try:
    from subagent_invocation_cache import pop_invocation as _pop_cached_subagent_invocation
except ImportError:
    # Fallback: cache lib missing → fall back to pre-#1087 behavior.
    def _pop_cached_subagent_invocation(*_args, **_kwargs):
        return None


# ============================================================================
# Configuration
# ============================================================================

# Check configuration from environment
TRACK_SESSIONS = os.environ.get("TRACK_SESSIONS", "true").lower() == "true"
TRACK_PIPELINE = os.environ.get("TRACK_PIPELINE", "true").lower() == "true"
AUTO_UPDATE_PROGRESS = os.environ.get("AUTO_UPDATE_PROGRESS", "false").lower() == "true"


# ============================================================================
# Pipeline Constants
# ============================================================================

# Active agents in the /implement pipeline (Issue #147)
EXPECTED_PIPELINE_AGENTS: List[str] = [
    "researcher-local",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master",
]


# ============================================================================
# Log Directory Discovery
# ============================================================================

# In-process cache for session date
_SESSION_DATE_CACHE: dict = {}


def _get_current_issue_number() -> int:
    """Get the current pipeline issue number with file-based fallback.

    Issue #779: Env vars set via ``export`` in one Bash tool call do NOT
    persist to subsequent Bash calls.  The hook process inherits env from
    the Claude Code parent process, not from a previous Bash session.

    Resolution order:
        1. ``PIPELINE_ISSUE_NUMBER`` env var
        2. ``issue_number`` from pipeline state file
        3. ``0`` as safe default

    Returns:
        The current issue number, or 0 if unavailable.
    """
    env_val = os.getenv("PIPELINE_ISSUE_NUMBER")
    if env_val and env_val != "0":
        try:
            return int(env_val)
        except (ValueError, TypeError):
            pass

    pipeline_state_file = os.getenv(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json

            with open(state_path) as f:
                state = _json.load(f)
            issue_num = state.get("issue_number", 0)
            if isinstance(issue_num, int) and issue_num > 0:
                return issue_num
            if isinstance(issue_num, str) and issue_num.isdigit():
                return int(issue_num)
    except Exception:
        pass

    return 0


def _find_log_dir() -> Path:
    """Find the .claude/logs/activity directory.

    Walks up from cwd to find an existing .claude directory, then uses
    its logs/activity subdirectory. Falls back to cwd/.claude/logs/activity.

    Returns:
        Path to the activity log directory.
    """
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        claude_dir = parent / ".claude"
        if claude_dir.exists():
            return claude_dir / "logs" / "activity"

    # Fallback to cwd
    return cwd / ".claude" / "logs" / "activity"


def _get_session_date(session_id: str) -> str:
    """Get the pinned date for a session, preventing cross-midnight mislabeling.

    Each session gets a date pinned on first activity. If the session spans
    midnight, all entries still use the original date so they land in the
    same log file.

    Args:
        session_id: The Claude session identifier.

    Returns:
        Date string in YYYY-MM-DD format.
    """
    # Check in-process cache first
    if session_id in _SESSION_DATE_CACHE:
        return _SESSION_DATE_CACHE[session_id]

    # Check for session date file
    log_dir = _find_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_session_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", session_id)
    date_file = log_dir / f".session_date_{safe_session_id}"

    try:
        if date_file.exists():
            stored_date = date_file.read_text().strip()
            # Validate freshness: if file is older than 24 hours, start fresh
            file_age_seconds = time.time() - date_file.stat().st_mtime
            if file_age_seconds < 86400 and stored_date:
                _SESSION_DATE_CACHE[session_id] = stored_date
                return stored_date
    except Exception:
        pass

    # Fall back to current date and persist it
    date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        date_file.write_text(date_str)
    except Exception:
        pass
    _SESSION_DATE_CACHE[session_id] = date_str
    return date_str


# ============================================================================
# Stdin Parsing
# ============================================================================

def _parse_stdin() -> Dict:
    """Read and parse JSON from stdin (SubagentStop hook input).

    Returns:
        Parsed dict from stdin, or empty dict if stdin is empty/unparseable.
    """
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return {}


def _validate_transcript_path(path_str: str) -> str:
    """Validate agent_transcript_path is within ~/.claude.

    Args:
        path_str: Raw transcript path string.

    Returns:
        Validated path string, or empty string if invalid/unsafe.
    """
    if not path_str:
        return ""

    try:
        resolved = Path(path_str).resolve()
        claude_home = (Path.home() / ".claude").resolve()
        if resolved.is_relative_to(claude_home):
            return str(resolved)
        return ""
    except Exception:
        return ""


def _compute_duration_ms() -> int:
    """Compute duration_ms by diffing against agent_tracker started_at.

    Returns:
        Duration in milliseconds, or 0 if not available.
    """
    if not HAS_AGENT_TRACKER:
        return 0

    try:
        tracker = AgentTracker()
        session_data = tracker.get_current_session()
        if session_data and "started_at" in session_data:
            started_at_str = session_data["started_at"]
            # Parse ISO format timestamp
            started_at = datetime.fromisoformat(started_at_str)
            now = datetime.now(timezone.utc)
            # Handle naive datetime
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            delta = now - started_at
            return max(0, int(delta.total_seconds() * 1000))
    except Exception:
        pass

    return 0


# Issue #1179: transcript-flush settling threshold. Reads below this word
# count are suspected to be racing Claude Code's async JSONL write; we
# poll-until-stable and re-read once.
_TRANSCRIPT_FLUSH_THRESHOLD_WORDS = 10


def _wait_for_transcript_flush(
    path: "Path",
    max_wait_seconds: float = 2.0,
    poll_interval_seconds: float = 0.1,
    stability_samples: int = 3,
) -> None:
    """Block until transcript file size stops changing or timeout elapses.

    Issue #1179: SubagentStop fires while Claude Code is still writing the
    JSONL transcript async. Poll-until-stable adds ~0ms when the file is
    already flushed (size stable from first sample), ~300ms in the race
    case (stability_samples * poll_interval_seconds), capped at
    max_wait_seconds.

    Assumes the transcript is append-only; if Claude Code ever rotates or
    truncates the file mid-write, settling may exit prematurely.

    Returns silently on missing file or OSError — caller's second read
    surfaces whatever is on disk.
    """
    if not path.exists():
        return
    deadline = time.monotonic() + max_wait_seconds
    last_size = -1
    stable_count = 0
    while time.monotonic() < deadline:
        try:
            current_size = path.stat().st_size
        except OSError:
            return
        if current_size == last_size:
            stable_count += 1
            if stable_count >= stability_samples:
                return
        else:
            stable_count = 0
            last_size = current_size
        time.sleep(poll_interval_seconds)


def _read_count(transcript_path: "Path | str") -> int:
    """Internal: single-shot read of transcript JSONL and word tally.

    Extracted from _count_words_in_transcript() for Issue #1179 so the
    public function can read twice with a settling gap between reads.
    """
    try:
        path = Path(transcript_path)
        if not path.exists():
            return 0

        total = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # Malformed JSONL lines skipped (defense in depth against partial writes)
                    continue

                if entry.get("type") != "assistant":
                    continue

                raw_msg = entry.get("message", {})
                msg = raw_msg if isinstance(raw_msg, dict) else {}
                content = msg.get("content")

                # Delegate to shared helper (Issue #925)
                import sys as _sys_wc
                _lib_dir_wc = str(Path(__file__).parent.parent / "lib")
                if _lib_dir_wc not in _sys_wc.path:
                    _sys_wc.path.insert(0, _lib_dir_wc)
                from word_count_helpers import count_words_in_content
                total += count_words_in_content(content)
        return total
    except Exception:
        return 0


# Shape mirrors conversation_archiver._extract_metadata (str-content legacy + list-of-blocks modern)
def _count_words_in_transcript(transcript_path: "Path | str") -> int:
    """Count total words across all assistant turns in a JSONL transcript.

    Handles both content shapes:
    - str-content (legacy): ``{"type": "assistant", "message": {"content": "text..."}}``
    - list-of-blocks (modern): ``{"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}``

    Args:
        transcript_path: Path to JSONL transcript file.

    Returns:
        Total word count of all assistant text content, or 0 on any failure.

    Issue #1179: if the first read returns fewer than
    _TRANSCRIPT_FLUSH_THRESHOLD_WORDS, wait for the transcript file size
    to stabilize and re-read once. The second read is returned directly
    (the transcript is append-only, so second >= first).
    """
    count = _read_count(transcript_path)
    if count < _TRANSCRIPT_FLUSH_THRESHOLD_WORDS:
        _wait_for_transcript_flush(Path(transcript_path))
        count = _read_count(transcript_path)
    return count


def _determine_success(output: str) -> bool:
    """Determine success from last_assistant_message content.

    Uses contextual pattern matching to distinguish actual failures from
    benign mentions of error-related words (e.g. "error handling", "no error").

    Args:
        output: The last assistant message text.

    Returns:
        True if no actual failure indicators found in output.
    """
    if not output:
        return True

    # Benign contexts that should NOT be treated as failures
    benign_patterns = [
        r"\berror[\s-]?handling\b",
        r"\bno\s+errors?\b",
        r"\berror[\s-]?free\b",
        r"\bfixed\s+(?:the\s+)?error\b",
        r"\bimproved?\s+error\b",
        r"\berror\s+message\b",
        r"\bwithout\s+errors?\b",
    ]

    # Actual failure patterns that indicate a real problem
    failure_line_prefixes = re.compile(
        r"^(Error|ERROR|Fatal|FATAL|Exception)\s*:"
        r"|^Traceback\s*\(",  # Handles "Traceback (most recent call last):"
        re.MULTILINE,
    )
    failure_phrases = re.compile(
        r"\b(failed\s+to|could\s+not|unable\s+to|crashed|unhandled\s+exception)\b",
        re.IGNORECASE,
    )

    # Build a version of the output with benign matches removed so that
    # benign mentions don't trigger the failure checks below
    scrubbed = output
    for pattern in benign_patterns:
        scrubbed = re.sub(pattern, "", scrubbed, flags=re.IGNORECASE)

    # Check for actual failures in the scrubbed text
    if failure_line_prefixes.search(scrubbed):
        return False
    if failure_phrases.search(scrubbed):
        return False

    return True


# ============================================================================
# Session Logging (Basic)
# ============================================================================

class SessionTracker:
    """Basic session logging to docs/sessions/."""

    def __init__(self):
        """Initialize session tracker.

        When CLAUDE_SESSION_ID is set, session files include the session ID in
        their filename to prevent cross-session contamination (Issue #594).
        """
        self.session_dir = Path("docs/sessions")
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Read CLAUDE_SESSION_ID for session isolation (Issue #594)
        claude_session_id = os.environ.get("CLAUDE_SESSION_ID")

        # Find or create session file for today
        today = datetime.now().strftime("%Y%m%d")
        session_files = list(self.session_dir.glob(f"{today}-*.md"))

        if session_files:
            if claude_session_id:
                # Filter by session ID substring in filename
                # Files created with this session ID include it in the name
                safe_sid = claude_session_id.replace("/", "_").replace("\\", "_")
                matching = [f for f in session_files if safe_sid in f.name]
                if matching:
                    self.session_file = sorted(matching)[-1]
                else:
                    # No match — create new session file for this session
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    safe_sid = claude_session_id[:16].replace("/", "_").replace("\\", "_")
                    self.session_file = self.session_dir / f"{timestamp}-{safe_sid}-session.md"
                    self.session_file.write_text(
                        f"# Session {timestamp}\n\n"
                        f"**Started**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"**Claude Session ID**: {claude_session_id}\n\n"
                        f"---\n\n"
                    )
            else:
                # No CLAUDE_SESSION_ID — fall back to most recent file (backward compat)
                self.session_file = sorted(session_files)[-1]
        else:
            # Create new session file
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            if claude_session_id:
                safe_sid = claude_session_id[:16].replace("/", "_").replace("\\", "_")
                filename = f"{timestamp}-{safe_sid}-session.md"
                session_header = (
                    f"# Session {timestamp}\n\n"
                    f"**Started**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"**Claude Session ID**: {claude_session_id}\n\n"
                    f"---\n\n"
                )
            else:
                filename = f"{timestamp}-session.md"
                session_header = (
                    f"# Session {timestamp}\n\n"
                    f"**Started**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"---\n\n"
                )
            self.session_file = self.session_dir / filename
            self.session_file.write_text(session_header)

    def log(self, agent_name: str, message: str) -> None:
        """
        Log agent action to session file.

        Args:
            agent_name: Name of agent
            message: Message to log
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"**{timestamp} - {agent_name}**: {message}\n\n"

        # Append to session file
        with open(self.session_file, "a") as f:
            f.write(entry)


def track_basic_session(agent_name: str, message: str) -> bool:
    """
    Track agent completion in basic session log.

    Args:
        agent_name: Name of agent
        message: Completion message

    Returns:
        True if logged successfully, False otherwise
    """
    if not TRACK_SESSIONS:
        return False

    try:
        tracker = SessionTracker()
        tracker.log(agent_name, message)
        return True
    except Exception:
        return False


# ============================================================================
# Pipeline Tracking (Structured)
# ============================================================================

def extract_tools_from_output(output: str) -> Optional[List[str]]:
    """
    Best-effort extraction of tools used from agent output.

    Args:
        output: Agent output text

    Returns:
        List of tool names or None if no tools detected
    """
    tools = []

    # Common tool mentions in output
    if "Read tool" in output or "reading file" in output.lower():
        tools.append("Read")
    if "Write tool" in output or "writing file" in output.lower():
        tools.append("Write")
    if "Edit tool" in output or "editing file" in output.lower():
        tools.append("Edit")
    if "Bash tool" in output or "running command" in output.lower():
        tools.append("Bash")
    if "Grep tool" in output or "searching" in output.lower():
        tools.append("Grep")
    if "WebSearch" in output or "web search" in output.lower():
        tools.append("WebSearch")
    if "WebFetch" in output or "fetching URL" in output.lower():
        tools.append("WebFetch")
    if "Task tool" in output or "invoking agent" in output.lower():
        tools.append("Task")

    return tools if tools else None


def track_pipeline_completion(agent_name: str, agent_output: str, agent_status: str) -> bool:
    """
    Track agent completion in structured pipeline.

    Args:
        agent_name: Name of agent
        agent_output: Agent output text
        agent_status: "success" or "error"

    Returns:
        True if tracked successfully, False otherwise
    """
    if not TRACK_PIPELINE or not HAS_AGENT_TRACKER:
        return False

    try:
        tracker = AgentTracker()

        # Read feature_ref from environment (batch mode)
        feature_ref = os.environ.get("PIPELINE_FEATURE_REF", "")

        if agent_status == "success":
            # Extract tools used
            tools = extract_tools_from_output(agent_output)

            # Create summary (first 100 chars)
            summary = agent_output[:100].replace("\n", " ") if agent_output else "Completed"
            if feature_ref:
                summary = f"[{feature_ref}] {summary}"

            # Auto-track agent first (idempotent)
            tracker.auto_track_from_environment(message=summary)

            # Complete the agent
            tracker.complete_agent(agent_name, summary, tools)
        else:
            # Extract error message
            error_msg = agent_output[:100].replace("\n", " ") if agent_output else "Failed"
            if feature_ref:
                error_msg = f"[{feature_ref}] {error_msg}"

            # Auto-track even for failures
            tracker.auto_track_from_environment(message=error_msg)

            # Fail the agent
            tracker.fail_agent(agent_name, error_msg)

        return True
    except Exception:
        return False


# ============================================================================
# PROJECT.md Progress Updates
# ============================================================================

def should_trigger_progress_update(agent_name: str) -> bool:
    """
    Check if PROJECT.md progress update should trigger.

    Only triggers for doc-master (last agent in pipeline).

    Args:
        agent_name: Name of agent that completed

    Returns:
        True if should trigger, False otherwise
    """
    return agent_name == "doc-master"


def check_pipeline_complete() -> bool:
    """
    Check if all 7 agents in pipeline completed.

    Filters candidate session files by CLAUDE_SESSION_ID when available to
    prevent cross-session contamination (Issue #594).

    Returns:
        True if pipeline complete, False otherwise
    """
    if not HAS_AGENT_TRACKER:
        return False

    try:
        # Check latest session file
        session_dir = Path("docs/sessions")
        session_files = list(session_dir.glob("*-pipeline.json"))

        if not session_files:
            return False

        # Filter by CLAUDE_SESSION_ID when available (Issue #594)
        claude_session_id = os.environ.get("CLAUDE_SESSION_ID")
        if claude_session_id:
            matching = []
            for f in session_files:
                try:
                    data = json.loads(f.read_text())
                    if data.get("claude_session_id") == claude_session_id:
                        matching.append(f)
                except (json.JSONDecodeError, OSError):
                    continue
            # Use matching files if any; otherwise fall back to all files
            if matching:
                session_files = matching

        # Read latest session
        latest_session = sorted(session_files)[-1]
        session_data = json.loads(latest_session.read_text())

        # Check if all expected agents completed
        # Issue #147: Consolidated to only active agents in /implement pipeline
        expected_agents = EXPECTED_PIPELINE_AGENTS

        completed_agents = {
            entry["agent"] for entry in session_data.get("agents", [])
            if entry.get("status") == "completed"
        }

        return set(expected_agents).issubset(completed_agents)
    except Exception:
        return False


def update_project_progress() -> bool:
    """
    Update PROJECT.md with goal progress.

    Returns:
        True if updated successfully, False otherwise
    """
    if not AUTO_UPDATE_PROGRESS or not HAS_PROJECT_UPDATER:
        return False

    try:
        # Note: Progress tracking feature deprioritized (Issue #147: Agent consolidation)
        # Would update PROJECT.md via ProjectMdUpdater if implemented.
        return False
    except Exception:
        return False


# ============================================================================
# SubagentStop Dedup Guard (Issue #1176)
# ============================================================================
#
# SubagentStop fires twice per agent due to dual hook registration in some
# settings templates. The duplicate firing pollutes JSONL logs, double-counts
# durations, and triggers downstream consumers (ghost-agent detection,
# pipeline completion state, plan-critic stage advance) twice.
#
# This guard uses an atomic file-based marker in /tmp keyed by a hash of the
# agent_transcript_path (falling back to session_id:agent_name when missing).
# os.open(O_CREAT|O_EXCL) is atomically race-safe — only one caller can
# successfully create the marker; subsequent callers see FileExistsError and
# return False so main() can write a debuggable skip entry and exit early.
#
# Markers are swept after TTL_SECONDS (default 300s) to prevent /tmp pollution.
# Sweep is gated to at most once per 60s via _LAST_SWEEP_TS.

_LAST_SWEEP_TS: float = 0.0
_DEFAULT_MARKER_DIR = Path("/tmp")
_MARKER_PREFIX = "subagent_stop_seen_"
_MARKER_SUFFIX = ".marker"


def _try_claim_subagent_stop_marker(
    key: str,
    ttl_seconds: int = 300,
    *,
    marker_dir: Optional[Path] = None,
) -> bool:
    """Atomically claim a SubagentStop dedup marker.

    Uses ``os.open(O_CREAT|O_EXCL)`` to ensure only one caller wins when
    multiple firings race for the same key.

    Args:
        key: Already-hashed key (e.g., sha256(transcript_path)[:16]).
            Sanitized defensively in case it contains path-unsafe chars.
        ttl_seconds: How long markers are considered fresh before sweep
            removes them. Default 300s (firings arrive within ms; 300s
            is generous and prevents /tmp accumulation).
        marker_dir: Directory for marker files. Defaults to /tmp.
            Parameter exists for test hermeticity.

    Returns:
        True if marker was successfully claimed (first/only caller for
        this key), False if another caller has already claimed it.
        Fails OPEN (returns True) on unexpected errors to ensure
        legitimate firings are not silently dropped.
    """
    global _LAST_SWEEP_TS
    base_dir = marker_dir if marker_dir is not None else _DEFAULT_MARKER_DIR

    # Defensive: sanitize key (caller passes pre-hashed; this guards against
    # accidental path-traversal injection if the API is later misused).
    safe_key = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)[:32]
    if not safe_key:
        return True  # Fail open on empty key

    marker_path = base_dir / f"{_MARKER_PREFIX}{safe_key}{_MARKER_SUFFIX}"

    # Sweep stale markers, gated to <=1/60s to avoid per-firing glob overhead.
    now = time.time()
    if now - _LAST_SWEEP_TS > 60:
        _LAST_SWEEP_TS = now
        try:
            pattern = str(base_dir / f"{_MARKER_PREFIX}*{_MARKER_SUFFIX}")
            for stale in glob.glob(pattern):
                try:
                    if now - os.path.getmtime(stale) > ttl_seconds:
                        os.unlink(stale)
                except OSError:
                    pass  # Best-effort sweep; race with another sweeper is fine
        except Exception:
            pass  # Sweep failure must not block claim

    # Atomic claim attempt.
    try:
        fd = os.open(
            str(marker_path),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception as e:
        # Fail OPEN: better to allow a duplicate log entry than to silently
        # drop a legitimate SubagentStop firing.
        try:
            print(
                f"unified_session_tracker: dedup guard fail-open: {e}",
                file=sys.stderr,
            )
        except Exception:
            pass
        return True


# ============================================================================
# JSONL Activity Logging
# ============================================================================

def _write_jsonl_entry(
    *,
    subagent_type: str,
    duration_ms: int,
    result_word_count: int,
    agent_transcript_path: str,
    session_id: str,
    success: bool,
) -> bool:
    """Write a structured JSONL entry for the SubagentStop event.

    Args:
        subagent_type: The agent type that completed.
        duration_ms: Computed duration in milliseconds.
        result_word_count: Word count of last_assistant_message.
        agent_transcript_path: Validated transcript path or empty string.
        session_id: Session identifier.
        success: Whether the agent completed successfully.

    Returns:
        True if written successfully, False otherwise.
    """
    try:
        log_dir = _find_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        date_str = _get_session_date(session_id)
        log_file = log_dir / f"{date_str}.jsonl"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook": "SubagentStop",
            "subagent_type": subagent_type,
            "duration_ms": duration_ms,
            "result_word_count": result_word_count,
            "agent_transcript_path": agent_transcript_path,
            "session_id": session_id,
            "success": success,
        }

        # Include feature_ref from environment when in batch mode
        feature_ref = os.environ.get("PIPELINE_FEATURE_REF", "")
        if feature_ref:
            entry["feature_ref"] = feature_ref

        # Include plugin version for diagnostics (Issue #630)
        entry["plugin_version"] = get_plugin_version() if HAS_VERSION_READER else "unknown"

        with open(log_file, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

        return True
    except Exception:
        return False


# ============================================================================
# Plan-Critic Stage Advance (Staged Plan-Exit Pipeline)
# ============================================================================

PLAN_MODE_EXIT_MARKER = ".claude/plan_mode_exit.json"


_PLAN_TO_ISSUES_SUGGESTION = (
    "Plan approved. Next steps:\n"
    "- `/plan-to-issues --quick` to create GitHub issues from this plan\n"
    "- `/implement` to begin implementation directly"
)


def _advance_plan_mode_stage() -> Optional[str]:
    """Advance plan mode exit marker from plan_exited to critique_done.

    Called when plan-critic SubagentStop fires. If the marker exists and
    is at stage ``plan_exited``, advances it to ``critique_done`` so that
    unified_prompt_validator allows /implement and related commands.

    Returns:
        A suggestion message string when the stage successfully advances
        from ``plan_exited`` to ``critique_done``, otherwise ``None``.
        Never raises — failures are silently ignored to avoid blocking
        the SubagentStop hook.
    """
    try:
        cwd = Path(os.getcwd())
        marker_path = cwd / PLAN_MODE_EXIT_MARKER
        if not marker_path.exists():
            return None
        marker_data = json.loads(marker_path.read_text())
        if marker_data.get("stage") != "plan_exited":
            return None  # Back-compat: critique_done (or other) short-circuits BEFORE verdict IO.

        # HARD GATE (Issue #927): only advance to critique_done when plan-critic returned PROCEED.
        # Verdict file written by plan-critic agent at end of every round.
        verdict_path = cwd / ".claude" / "plan_critic_verdict.json"
        if not verdict_path.exists():
            return None  # No critique yet — do not advance.

        verdict_data = json.loads(verdict_path.read_text())
        if verdict_data.get("verdict") != "PROCEED":
            return None  # REVISE or BLOCKED — gate stays closed; verdict file retained.

        # Staleness check: verdict must be at least as recent as the marker.
        verdict_ts = datetime.fromisoformat(verdict_data["timestamp"])
        marker_ts = datetime.fromisoformat(marker_data["timestamp"])
        if verdict_ts < marker_ts:
            return None  # Stale verdict from a previous plan — ignore.

        # PROCEED accepted — consume verdict file so it cannot replay.
        verdict_path.unlink(missing_ok=True)

        marker_data["stage"] = "critique_done"
        marker_data["critique_completed_at"] = datetime.now(timezone.utc).isoformat()
        marker_path.write_text(json.dumps(marker_data, indent=2))

        # Issue #970: telemetry — record successful stage advance for audit.
        # Telemetry-only; no behavior change. NEVER raises.
        try:
            _log_block_with_recovery_970(
                hook_name="unified_session_tracker.py",
                tool_name="SubagentStop",
                block_reason="STAGE_ADVANCE: plan_exited -> critique_done",
                recovery_hint="Pipeline gate cleared. Run /implement to proceed.",
            )
        except Exception:
            pass

        return _PLAN_TO_ISSUES_SUGGESTION
    except Exception:
        return None  # Never crash on stage advance failure


# ============================================================================
# Main Hook Entry Point
# ============================================================================

def main() -> int:
    """
    Main hook entry point.

    Reads agent info from stdin JSON (SubagentStop hook input), with
    fallback to environment variables for backward compatibility.

    Returns:
        Always 0 (non-blocking hook)
    """
    try:
        # Parse stdin JSON (SubagentStop provides input via stdin)
        hook_input = _parse_stdin()

        # Extract fields from stdin, fall back to env vars
        if hook_input:
            agent_name = hook_input.get("agent_type", "unknown")
            agent_output = hook_input.get("last_assistant_message", "")
            session_id = hook_input.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "unknown"))
            agent_transcript_path_raw = hook_input.get("agent_transcript_path", "")
        else:
            # Backward compatibility: fall back to environment variables
            agent_name = os.environ.get("CLAUDE_AGENT_NAME", "unknown")
            agent_output = os.environ.get("CLAUDE_AGENT_OUTPUT", "")
            session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
            agent_transcript_path_raw = ""

        # Issue #1176: Dedup guard — SubagentStop fires twice per agent due to
        # dual hook registration. Claim a marker BEFORE any downstream side
        # effects (cache pop, JSONL write, stage advance) so duplicates exit
        # early. Key prefers agent_transcript_path (unique per firing pair);
        # falls back to session_id:agent_name when transcript_path is empty.
        dedup_key_source = agent_transcript_path_raw or f"{session_id}:{agent_name}"
        dedup_key = hashlib.sha256(dedup_key_source.encode("utf-8")).hexdigest()[:16]
        if not _try_claim_subagent_stop_marker(dedup_key):
            # Duplicate firing — log a debug entry and exit.
            try:
                _write_jsonl_entry(
                    subagent_type=f"__dedup_skip__:{agent_name}",
                    duration_ms=0,
                    result_word_count=0,
                    agent_transcript_path=_validate_transcript_path(
                        agent_transcript_path_raw
                    ),
                    session_id=session_id,
                    success=True,
                )
            except Exception:
                pass  # Non-blocking: skip entry is advisory only
            return 0

        # Issue #1087: Recover missing subagent_type and duration_ms via the
        # subagent invocation cache populated by session_activity_logger on
        # PreToolUse. Claude Code's SubagentStop payload frequently omits
        # agent_type (showing "") and always reports a 0 duration. Without
        # this cache, downstream consumers (ghost-agent detection, agent
        # completeness gate, pipeline timing analyzer) have no way to know
        # which agent stopped or how long it took.
        cached_invocation = _pop_cached_subagent_invocation(
            session_id,
            preferred_subagent_type=(agent_name or "").strip()
            if agent_name not in ("", "unknown")
            else "",
        )
        if (not agent_name) or agent_name in ("", "unknown"):
            if cached_invocation and cached_invocation.get("subagent_type"):
                agent_name = cached_invocation["subagent_type"]

        # Determine status with correct priority (Issue #541):
        # 1. CLAUDE_AGENT_STATUS env var (structural signal) — authoritative
        # 2. _determine_success() text scan — fallback only when env var absent
        # Previously, the text scan always ran and could override a "success" env var
        # when the output happened to contain benign failure-pattern words.
        env_status = os.environ.get("CLAUDE_AGENT_STATUS")
        if env_status:
            agent_status = env_status
        elif agent_output and not _determine_success(agent_output):
            agent_status = "error"
        else:
            agent_status = "success"

        # Validate transcript path
        agent_transcript_path = _validate_transcript_path(agent_transcript_path_raw)

        # Compute duration. Prefer the PreToolUse cache (Issue #1087) since
        # _compute_duration_ms() relies on agent_tracker's "started_at" which
        # is not populated for native Task/Agent invocations.
        duration_ms = 0
        if cached_invocation and isinstance(
            cached_invocation.get("start_time"), (int, float)
        ):
            try:
                duration_ms = max(
                    0,
                    int((time.time() - float(cached_invocation["start_time"])) * 1000),
                )
            except (TypeError, ValueError):
                duration_ms = 0
        if duration_ms == 0:
            duration_ms = _compute_duration_ms()

        # Compute word count
        # Prefer full transcript aggregation to capture multi-turn output (#872/#907)
        transcript_count = 0
        if agent_transcript_path:
            try:
                transcript_count = _count_words_in_transcript(agent_transcript_path)
            except Exception:
                transcript_count = 0
        result_word_count = transcript_count or (len(agent_output.split()) if agent_output else 0)

        # Determine success
        success = _determine_success(agent_output)

        # Create summary message
        summary = agent_output[:100].replace("\n", " ") if agent_output else "Completed"

        # Dispatch tracking (all are non-blocking)
        # Basic session logging
        track_basic_session(agent_name, summary)

        # Structured pipeline tracking
        track_pipeline_completion(agent_name, agent_output, agent_status)

        # JSONL activity logging for CI agent visibility
        _write_jsonl_entry(
            subagent_type=agent_name,
            duration_ms=duration_ms,
            result_word_count=result_word_count,
            agent_transcript_path=agent_transcript_path,
            session_id=session_id,
            success=success,
        )

        # Pipeline ordering state — record agent completion (Issues #625, #629, #632)
        try:
            from pipeline_completion_state import record_agent_completion
            record_agent_completion(
                session_id=session_id,
                agent_type=agent_name,
                issue_number=_get_current_issue_number(),
                success=success,
            )
        except Exception:
            pass  # Non-blocking: ordering state is advisory

        # Sentinel heartbeat check (Issue #989): after recording completion,
        # verify the <repo>/.claude/local/implement_pipeline_state.json sentinel
        # (was /tmp/implement_pipeline_state.json pre-#1206) still exists
        # with the correct session_id. If clear_stale_state() deleted it (e.g.,
        # because a subprocess ran with a different CLAUDE_SESSION_ID), recreate
        # a minimal sentinel so downstream steps can still record completions.
        try:
            from pipeline_completion_state import ensure_sentinel_heartbeat
            ensure_sentinel_heartbeat(session_id)
        except Exception:
            pass  # Non-blocking: heartbeat is a recovery guard, never a gate

        # Plan-critic stage advance (Staged Plan-Exit Pipeline)
        if agent_name == "plan-critic":
            suggestion = _advance_plan_mode_stage()
            if suggestion is not None:
                try:
                    print(json.dumps({"systemMessage": suggestion}))
                except Exception:
                    pass  # Non-blocking: message output is advisory only

        # PROJECT.md progress updates (only for doc-master)
        if should_trigger_progress_update(agent_name) and check_pipeline_complete():
            update_project_progress()

    except Exception:
        # Graceful degradation - never block workflow
        pass

    # Always succeed (non-blocking hook)
    return 0



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
