#!/usr/bin/env python3
"""
Coordinator-side activity log for background agent completions.

When agents run with ``run_in_background=true``, the SubagentStop hook
(``unified_session_tracker.py``) often fails to fire.  This module provides a
reusable function that the **coordinator** can call after confirming a
background agent has finished, ensuring the completion event is always recorded
in the JSONL activity log.

Fixes Issue #868: Doc-master completion events missing from activity log.

Usage:
    from coordinator_log import log_background_agent_completion, ensure_doc_master_logged

    log_background_agent_completion(
        agent_type="doc-master",
        issue_number=123,
        result_word_count=450,
        duration_seconds=12.5,
        session_id="abc-123",
    )

    # Convenience wrapper for the most common case:
    ensure_doc_master_logged(
        issue_number=123,
        result_word_count=450,
        duration_seconds=12.5,
        session_id="abc-123",
    )
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _find_activity_log_dir(*, start_dir: Optional[Path] = None) -> Optional[Path]:
    """Locate the ``.claude/logs/activity/`` directory by walking up from *start_dir*.

    The search starts at *start_dir* (defaults to ``Path.cwd()``) and checks
    each ancestor for a ``.claude`` directory.  If found, returns the
    ``logs/activity`` sub-path (creating it if necessary).

    Args:
        start_dir: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to the activity log directory, or ``None`` if no ``.claude``
        directory is found in any ancestor.
    """
    cwd = start_dir or Path.cwd()
    candidates = [cwd] + list(cwd.parents)
    for parent in candidates:
        claude_dir = parent / ".claude"
        if claude_dir.is_dir():
            log_dir = claude_dir / "logs" / "activity"
            try:
                log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            except OSError:
                return None
            return log_dir
    return None


def log_background_agent_completion(
    agent_type: str,
    issue_number: int,
    *,
    batch_id: Optional[str] = None,
    result_word_count: int = 0,
    duration_seconds: float = 0.0,
    session_id: str = "",
    start_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Write a JSONL activity log entry for a background agent completion.

    This is the coordinator-side fallback for when the SubagentStop hook does
    not fire (common with ``run_in_background=true``).  The entry is tagged
    with ``"source": "coordinator_fallback"`` so downstream consumers can
    distinguish it from native hook entries and deduplicate if both fired.

    Args:
        agent_type: Agent identifier (e.g. ``"doc-master"``).
        issue_number: GitHub issue number the agent worked on.
        batch_id: Optional batch identifier.
        result_word_count: Approximate word count of the agent's output.
        duration_seconds: Wall-clock seconds the agent ran.
        session_id: Claude session ID. Falls back to ``CLAUDE_SESSION_ID``
            environment variable if empty.
        start_dir: Override for directory search start (useful in tests).

    Returns:
        Path to the JSONL file the entry was appended to, or ``None`` if the
        activity log directory could not be found.

    Raises:
        No exceptions are raised.  Logging failures are silently ignored to
        avoid disrupting the coordinator workflow.
    """
    log_dir = _find_activity_log_dir(start_dir=start_dir)
    if log_dir is None:
        return None

    resolved_session_id = session_id or os.environ.get("CLAUDE_SESSION_ID", "unknown")

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hook": "CoordinatorCompletionLog",
        "tool": "Agent",
        "subagent_type": agent_type,
        "issue_number": issue_number,
        "batch_id": batch_id,
        "result_word_count": result_word_count,
        "duration_seconds": duration_seconds,
        "session_id": resolved_session_id,
        "source": "coordinator_fallback",
    }

    log_file = log_dir / (datetime.now().strftime("%Y-%m-%d") + ".jsonl")

    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        os.chmod(log_file, 0o600)
    except OSError:
        return None

    return log_file


def ensure_doc_master_logged(
    issue_number: int,
    *,
    batch_id: Optional[str] = None,
    result_word_count: int = 0,
    duration_seconds: float = 0.0,
    session_id: str = "",
    start_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Convenience wrapper to log a doc-master background completion.

    Doc-master is the most common background agent whose SubagentStop event
    is missed.  This function calls :func:`log_background_agent_completion`
    with ``agent_type="doc-master"``.

    Args:
        issue_number: GitHub issue number the doc-master worked on.
        batch_id: Optional batch identifier.
        result_word_count: Approximate word count of the agent's output.
        duration_seconds: Wall-clock seconds the agent ran.
        session_id: Claude session ID.
        start_dir: Override for directory search start (useful in tests).

    Returns:
        Path to the JSONL file the entry was appended to, or ``None``.
    """
    return log_background_agent_completion(
        agent_type="doc-master",
        issue_number=issue_number,
        batch_id=batch_id,
        result_word_count=result_word_count,
        duration_seconds=duration_seconds,
        session_id=session_id,
        start_dir=start_dir,
    )
