"""Agent dispatch sentinel — tracks whether an Agent/Task tool dispatch is in flight.

Issue #1296: distinguishes coordinator direct edits from agent-dispatched edits to
protected infrastructure paths.

Sentinel file: <repo>/.claude/local/active_agent_dispatch.json (per-repo isolation,
Issue #1206 pattern). TTL 30s — beyond this, treat as stale (crashed agent or
forgotten PostToolUse clear).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional


_SENTINEL_REL = ".claude/local/active_agent_dispatch.json"
DEFAULT_TTL_SECONDS = 30


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
