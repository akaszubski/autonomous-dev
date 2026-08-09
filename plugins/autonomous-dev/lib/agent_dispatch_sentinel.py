"""Agent dispatch sentinel — tracks whether an Agent/Task tool dispatch is in flight.

Issue #1296: distinguishes coordinator direct edits from agent-dispatched edits to
protected infrastructure paths.

Sentinel file: <repo>/.claude/local/active_agent_dispatch.json (per-repo isolation,
Issue #1206 pattern).

Lifecycle (Issue #1448 — sliding TTL):
    write()   — armed once when a Task/Agent dispatch starts (PreToolUse).
    refresh() — slides the timestamp forward on every observed tool use while the
                dispatched agent is still running (PostToolUse). This is what makes
                the TTL a *sliding* window rather than a fixed one: a dispatched
                implementer doing reads, test runs and multi-file edits over many
                minutes stays continuously active as long as it keeps using tools.
                refresh() never creates a sentinel and never resurrects one that has
                already gone stale.
    clear()   — disarmed on SubagentStop (dispatch completion).

DEFAULT_TTL_SECONDS is therefore only the *idle*/crash backstop: how long the
sentinel survives with no tool activity at all (crashed agent, or a SubagentStop
that never fired).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional


_SENTINEL_REL = ".claude/local/active_agent_dispatch.json"
# Issue #1447/#1448 (recurrence 2026-08-09, during #1471): 30s was shorter than
# real implementer dispatch latency — system-prompt/skill loading + one Read +
# streaming a multi-line Edit call reliably exceeds it, structurally denying
# every large protected-path edit. SubagentStop still clears the sentinel on
# agent completion; combined with refresh()-on-tool-use (Issue #1448) the TTL is
# only the idle/crash backstop, so 600s is safe.
DEFAULT_TTL_SECONDS = 600


def _path(repo_root: Optional[Path] = None) -> Path:
    """Get the sentinel file path.
    
    Args:
        repo_root: Repository root directory. If None, uses cwd.
    
    Returns:
        Path to the sentinel file
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    return root / _SENTINEL_REL


def write(agent_name: str, repo_root: Optional[Path] = None) -> None:
    """Write an agent dispatch sentinel.
    
    Args:
        agent_name: Name of the agent being dispatched
        repo_root: Repository root directory. If None, uses cwd.
    """
    p = _path(repo_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agent": agent_name,
        "pid": os.getpid(),
        "timestamp": time.time(),
    }
    p.write_text(json.dumps(payload))


def clear(repo_root: Optional[Path] = None) -> None:
    """Clear the agent dispatch sentinel.
    
    Args:
        repo_root: Repository root directory. If None, uses cwd.
    """
    p = _path(repo_root)
    try:
        p.unlink()
    except FileNotFoundError:
        pass


def refresh(
    ttl_seconds: int = DEFAULT_TTL_SECONDS, repo_root: Optional[Path] = None
) -> bool:
    """Slide an existing sentinel's TTL forward (Issue #1448).

    Called from the hook that observes ongoing tool activity while a dispatched
    agent is running. Each tool use is evidence the agent is still alive, so the
    sentinel's timestamp is moved to now — turning the fixed TTL window into a
    sliding one.

    Deliberately conservative:
        - No sentinel file  -> no-op (never creates one). Otherwise the coordinator
          could arm the protected-path gate without a real dispatch.
        - Already stale     -> no-op (never resurrects a dead dispatch), preserving
          the crash backstop.
        - Malformed payload -> no-op.
        - Existing payload (agent name, pid) is preserved; only the timestamp moves.

    Args:
        ttl_seconds: Staleness threshold. Sentinels older than this are not refreshed.
        repo_root: Repository root directory. If None, uses cwd.

    Returns:
        True if an existing, non-stale sentinel was refreshed; False otherwise.
    """
    p = _path(repo_root)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text())
        if not isinstance(data, dict):
            return False
        ts = float(data.get("timestamp", 0))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return False
    if time.time() - ts > ttl_seconds:
        # Stale → refusing to resurrect. is_active() cleans it up.
        return False
    data["timestamp"] = time.time()
    try:
        p.write_text(json.dumps(data))
    except OSError:
        return False
    return True


def is_active(ttl_seconds: int = DEFAULT_TTL_SECONDS, repo_root: Optional[Path] = None) -> bool:
    """Check if an agent dispatch is currently active.
    
    Args:
        ttl_seconds: Time-to-live in seconds. Sentinels older than this are stale.
        repo_root: Repository root directory. If None, uses cwd.
    
    Returns:
        True if an active (non-stale) agent dispatch is in progress
    """
    p = _path(repo_root)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text())
        ts = float(data.get("timestamp", 0))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return False
    age = time.time() - ts
    if age > ttl_seconds:
        # stale → treat as inactive, also clean it up opportunistically
        try:
            p.unlink()
        except OSError:
            pass
        return False
    return True
