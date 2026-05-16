#!/usr/bin/env python3
"""
Subagent Invocation Cache (Issue #1087).

Tiny, dependency-free FIFO queue used to correlate PreToolUse Task/Agent
invocations with SubagentStop events so that `subagent_type` and
`duration_ms` can be recovered when Claude Code's SubagentStop payload
omits them.

Why this exists
---------------
Claude Code's SubagentStop hook payload is unreliable on two fields that
matter for downstream telemetry:

- ``agent_type`` is sometimes empty.
- ``duration_ms`` is always 0.

These break:

- ``detect_ghost_invocations()`` in the CIA agent (can't tell a 10s ghost
  invocation from a 10s legitimate verdict).
- The agent completeness gate (commits show agents "missing" even when
  they actually ran).
- Pipeline timing analysis (duration_ms=0 corrupts per-agent budgets).

Mechanism
---------
- ``cache_invocation(session_id, subagent_type, ...)`` is called from a
  PreToolUse hook (``session_activity_logger.py``) when the user invokes
  the native ``Task`` / ``Agent`` tool.
- ``pop_invocation(session_id, preferred_subagent_type="")`` is called
  from the SubagentStop hook (``unified_session_tracker.py``) to recover
  the matching entry by FIFO with optional type preference.

Cache file
----------
Per-session JSON queue at ``/tmp/subagent_invocations_{sha8}.json`` where
``sha8`` is the first 8 hex chars of ``sha256(session_id)``. Files older
than ``TTL_SECONDS`` (1 hour) are ignored on read, matching the staleness
window used by ``pipeline_completion_state``.

Correlation strategy
--------------------
Claude Code does not expose a stable ``tool_use_id`` across PreToolUse and
SubagentStop. We therefore use a per-session FIFO queue with an optional
preferred-type match:

1. If the SubagentStop stdin DID provide a non-empty ``agent_type``, we
   pop the oldest queue entry whose ``subagent_type`` matches.
2. Otherwise, we pop the oldest entry regardless of type (pure FIFO).

For sequential subagent invocations (the common pipeline case) this is
exact. For parallel invocations it matches by start-time, which is the
best signal available without a correlation id.

Safety
------
Every public function is best-effort and non-raising — instrumentation
must never crash a hook. Failures are silent and the caller continues.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import time
from pathlib import Path
from typing import Optional

#: Files older than this are ignored on read (1 hour).
TTL_SECONDS: int = 3600


def cache_path(session_id: str) -> Path:
    """Compute the per-session queue file path.

    Args:
        session_id: The Claude session identifier.

    Returns:
        Absolute path under /tmp using ``sha256(session_id)[:8]``. This
        avoids injection of arbitrary characters from ``session_id`` into
        the filesystem path.
    """
    h = hashlib.sha256((session_id or "unknown").encode()).hexdigest()[:8]
    return Path(f"/tmp/subagent_invocations_{h}.json")


def cache_invocation(
    session_id: str,
    subagent_type: str,
    *,
    start_time: Optional[float] = None,
    description: str = "",
) -> bool:
    """Append a subagent invocation entry to the per-session FIFO queue.

    Args:
        session_id: The Claude session identifier.
        subagent_type: The agent type (e.g. "implementer"). Empty strings
            are rejected — they would be useless for FIFO correlation.
        start_time: Optional epoch seconds; defaults to ``time.time()``.
        description: Optional human description from Task tool input
            (truncated to 200 chars; for diagnostics only).

    Returns:
        True on successful write, False on any failure or rejected input.
        Never raises.

    Issue: #1087
    """
    if not subagent_type:
        return False
    try:
        path = cache_path(session_id)
        entry = {
            "subagent_type": subagent_type,
            "start_time": float(start_time) if start_time is not None else time.time(),
            "description": (description or "")[:200],
        }
        with open(path, "a+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                raw = f.read()
                try:
                    data = json.loads(raw) if raw.strip() else {"queue": []}
                except (json.JSONDecodeError, ValueError):
                    data = {"queue": []}
                if not isinstance(data, dict) or "queue" not in data:
                    data = {"queue": []}
                queue = data.get("queue")
                if not isinstance(queue, list):
                    queue = []
                queue.append(entry)
                data["queue"] = queue
                f.seek(0)
                f.truncate()
                json.dump(data, f, separators=(",", ":"))
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return True
    except Exception:
        return False


def pop_invocation(
    session_id: str,
    *,
    preferred_subagent_type: str = "",
) -> Optional[dict]:
    """Pop the next subagent invocation from the per-session queue.

    Args:
        session_id: The Claude session identifier.
        preferred_subagent_type: Optional hint when SubagentStop stdin
            DID include a non-empty ``agent_type``. The oldest entry with
            a matching ``subagent_type`` is preferred over pure FIFO.

    Returns:
        The popped entry dict (keys: ``subagent_type``, ``start_time``,
        ``description``), or ``None`` when the queue is missing, empty,
        stale (older than ``TTL_SECONDS``), or unreadable. Never raises.

    Issue: #1087
    """
    try:
        path = cache_path(session_id)
        if not path.exists():
            return None

        try:
            if time.time() - path.stat().st_mtime > TTL_SECONDS:
                return None
        except OSError:
            return None

        with open(path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                raw = f.read()
                if not raw.strip():
                    return None
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    return None
                if not isinstance(data, dict):
                    return None
                queue = data.get("queue")
                if not isinstance(queue, list) or not queue:
                    return None

                popped = None
                pop_index = 0

                if preferred_subagent_type:
                    for idx, entry in enumerate(queue):
                        if (
                            isinstance(entry, dict)
                            and entry.get("subagent_type") == preferred_subagent_type
                        ):
                            popped = entry
                            pop_index = idx
                            break

                if popped is None:
                    first = queue[0]
                    popped = first if isinstance(first, dict) else None
                    pop_index = 0

                if popped is None:
                    return None

                del queue[pop_index]
                data["queue"] = queue
                f.seek(0)
                f.truncate()
                json.dump(data, f, separators=(",", ":"))
                return popped
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        return None


def peek_queue(session_id: str) -> list:
    """Return a copy of the current queue without modifying it.

    Args:
        session_id: The Claude session identifier.

    Returns:
        List of entry dicts. Empty list when missing, stale, or unreadable.

    Issue: #1087
    """
    try:
        path = cache_path(session_id)
        if not path.exists():
            return []
        try:
            if time.time() - path.stat().st_mtime > TTL_SECONDS:
                return []
        except OSError:
            return []
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                raw = f.read()
                if not raw.strip():
                    return []
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    return []
                if not isinstance(data, dict):
                    return []
                queue = data.get("queue")
                if not isinstance(queue, list):
                    return []
                return [e for e in queue if isinstance(e, dict)]
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        return []
