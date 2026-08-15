"""Agent dispatch sentinel — tracks whether an Agent/Task tool dispatch is in flight.

Issue #1296: distinguishes coordinator direct edits from agent-dispatched edits to
protected infrastructure paths.

Sentinel file: <repo>/.claude/local/active_agent_dispatch.json (per-repo isolation,
Issue #1206 pattern).

Lifecycle (Issue #1448 — sliding TTL):
    write()   — armed once when a Task/Agent dispatch starts (PreToolUse). Records
                both ``timestamp`` (slid by refresh()) and ``armed_at`` (fixed;
                anchors the absolute-ceiling backstop from Issue #1479).
    refresh() — slides the timestamp forward on every observed tool use while the
                dispatched agent is still running (PostToolUse). This is what makes
                the TTL a *sliding* window rather than a fixed one: a dispatched
                implementer doing reads, test runs and multi-file edits over many
                minutes stays continuously active as long as it keeps using tools.
                refresh() never creates a sentinel and never resurrects one that has
                already gone stale, and never slides past the absolute ceiling
                (MAX_LIFETIME_SECONDS) anchored on ``armed_at``.
    clear()   — disarmed on SubagentStop (dispatch completion).

DEFAULT_TTL_SECONDS is therefore only the *idle*/crash backstop: how long the
sentinel survives with no tool activity at all (crashed agent, or a SubagentStop
that never fired).

MAX_LIFETIME_SECONDS (Issue #1479) is the absolute ceiling: total time from
``armed_at`` regardless of refresh activity. This prevents an unrelated
coordinator's continued tool use from indefinitely keeping the #1296 gate armed
when a background-dispatched agent crashes/hangs without SubagentStop firing.
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
# Issue #1479: Absolute ceiling on total sentinel lifetime, anchored on the
# initial ``armed_at`` timestamp written by write(). refresh() cannot slide the
# effective active window past this bound, so an unrelated coordinator's tool
# activity cannot indefinitely keep the #1296 protected-path gate armed when a
# background-dispatched agent crashes/hangs without SubagentStop firing.
# Chosen to be larger than any observed legitimate implementer dispatch (up to
# ~2h in production), while still bounding worst-case exposure to a coordinator
# misattribution window.
MAX_LIFETIME_SECONDS = 4 * 3600


def _path(repo_root: Optional[Path] = None) -> Path:
    """Get the sentinel file path.

    Convergence note (Issue #1484): production callers MUST use the default
    (no-arg) branch. In that branch the repo root is resolved via the blessed
    ``path_utils.find_project_root`` resolver so the writer (PreToolUse),
    reader (unified_pre_tool) and clearer (SubagentStop) — all running as
    separate hook subprocesses — converge on one normalized sentinel path even
    when invoked from a subdirectory or a git worktree. ``find_project_root``
    walks up for ``.git``/``.claude`` markers; it does NOT shell out to
    ``git rev-parse --git-common-dir`` (banned by hook_path_validator.py).

    The EXPLICIT ``repo_root`` branch is test-only: it stays literal and is NOT
    ``.resolve()``-normalized, so the 30+ existing ``repo_root=``-passing tests
    (which pass ``tmp_path`` directly) keep asserting against the exact path
    they supplied. Do not rely on the explicit branch in production code.

    Args:
        repo_root: Repository root directory. If None, resolves via
            ``find_project_root`` (falling back to ``Path.cwd().resolve()``).

    Returns:
        Path to the sentinel file
    """
    if repo_root is not None:
        # Test-only branch: literal, unresolved (preserves existing repo_root tests).
        root = Path(repo_root)
    else:
        try:
            from path_utils import find_project_root

            root = find_project_root()
        except (ImportError, FileNotFoundError):
            root = Path.cwd().resolve()
    return root / _SENTINEL_REL


def write(
    agent_name: str,
    repo_root: Optional[Path] = None,
    generation: Optional[str] = None,
) -> None:
    """Write an agent dispatch sentinel.

    This is the SOLE authorization event (Issue #1296): only a real Task/Agent
    dispatch arms the sentinel that authorizes protected-infra edits.

    Args:
        agent_name: Name of the agent being dispatched
        repo_root: Repository root directory. If None, resolves via
            ``find_project_root`` (see ``_path``).
        generation: Per-dispatch generation token (Issue #1484). Recorded in the
            payload so ``clear(expected_generation=...)`` can compare-and-delete
            and avoid the ABA race where an overlapping sibling dispatch's
            SubagentStop disarms this dispatch's still-in-flight sentinel.
    """
    p = _path(repo_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    payload = {
        "agent": agent_name,
        "pid": os.getpid(),
        "timestamp": now,
        # Issue #1479: fixed anchor for the absolute-lifetime ceiling. Never
        # updated by refresh().
        "armed_at": now,
        # Issue #1484: per-dispatch generation token for compare-and-delete.
        "generation": generation,
    }
    p.write_text(json.dumps(payload))


def clear(
    repo_root: Optional[Path] = None,
    expected_generation: Optional[str] = None,
) -> None:
    """Clear the agent dispatch sentinel (compare-and-delete, Issue #1484).

    Semantics:
        - ``expected_generation is None`` -> unconditional ``unlink()``
          (backward-compat / genuine cache-miss path).
        - ``expected_generation`` given -> read+parse the sentinel; if the
          payload is a dict whose ``generation`` is present AND does not match
          ``expected_generation``, a *different* dispatch owns it, so this is a
          no-op (the #1467 ABA fix). Otherwise (generation matches, or is
          absent/legacy, or the sentinel is unreadable) -> ``unlink()``.

    Never raises — a failed disarm must never block a hook.

    Args:
        repo_root: Repository root directory. If None, resolves via
            ``find_project_root`` (see ``_path``).
        expected_generation: The generation token of the dispatch that is
            clearing. When provided, guards against disarming a sibling
            dispatch's sentinel.
    """
    p = _path(repo_root)
    if expected_generation is None:
        # Accepted backcompat gap (Issue #1484, residual amendment #1): a genuine
        # cache-miss (no recovered generation) still unconditionally unlinks, so
        # it can ABA-disarm a sibling dispatch. Preferred over refusing to clear
        # (which would leak sentinels and re-arm the #1447/#1448 keep-alive bug).
        try:
            p.unlink()
        except (FileNotFoundError, OSError):
            pass
        return
    try:
        data = json.loads(p.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError, TypeError):
        # Unreadable/absent/malformed -> fall through to unconditional unlink.
        data = None
    if isinstance(data, dict):
        sentinel_gen = data.get("generation")
        if sentinel_gen is not None and sentinel_gen != expected_generation:
            # A different dispatch owns this sentinel — do not disarm it.
            return
    try:
        p.unlink()
    except (FileNotFoundError, OSError):
        pass


def refresh(
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    repo_root: Optional[Path] = None,
    max_lifetime_seconds: int = MAX_LIFETIME_SECONDS,
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
        - Past absolute ceiling (Issue #1479) -> no-op. The sentinel's total lifetime
          from ``armed_at`` cannot be extended past ``max_lifetime_seconds`` by
          unrelated coordinator tool activity.
        - Malformed payload -> no-op.
        - Existing payload (agent name, pid, armed_at) is preserved; only ``timestamp``
          moves.

    Args:
        ttl_seconds: Staleness threshold. Sentinels older than this are not refreshed.
        repo_root: Repository root directory. If None, uses cwd.
        max_lifetime_seconds: Absolute ceiling on total sentinel lifetime measured
            from the initial ``armed_at``. Once exceeded, refresh() becomes a no-op
            even for actively-refreshed sentinels (Issue #1479).

    Returns:
        True if an existing, non-stale, within-ceiling sentinel was refreshed;
        False otherwise.
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
    now = time.time()
    if now - ts > ttl_seconds:
        # Stale → refusing to resurrect. is_active() cleans it up.
        return False
    # Issue #1479: absolute-ceiling backstop. armed_at defaults to ts for
    # sentinels written before this field was introduced (graceful upgrade).
    armed_at = float(data.get("armed_at", ts))
    if now - armed_at > max_lifetime_seconds:
        return False
    data["timestamp"] = now
    try:
        p.write_text(json.dumps(data))
    except OSError:
        return False
    return True


def is_active(
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    repo_root: Optional[Path] = None,
    max_lifetime_seconds: int = MAX_LIFETIME_SECONDS,
) -> bool:
    """Check if an agent dispatch is currently active.

    Args:
        ttl_seconds: Time-to-live in seconds. Sentinels older than this are stale.
        repo_root: Repository root directory. If None, uses cwd.
        max_lifetime_seconds: Absolute ceiling on total sentinel lifetime measured
            from the initial ``armed_at`` (Issue #1479). A sentinel that has exceeded
            this ceiling is treated as inactive and cleaned up, even if refresh()
            was keeping ``timestamp`` fresh.

    Returns:
        True if an active (non-stale, within-ceiling) agent dispatch is in progress
    """
    p = _path(repo_root)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text())
        # Issue #1480: guard against non-dict payloads (e.g. a JSON list). Without
        # this, .get() raises AttributeError. Mirrors the isinstance guard in refresh().
        if not isinstance(data, dict):
            return False
        ts = float(data.get("timestamp", 0))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return False
    now = time.time()
    age = now - ts
    # Issue #1479: absolute-lifetime ceiling anchored on armed_at. Defaults to
    # ``ts`` for pre-#1479 sentinels (graceful upgrade).
    armed_at = float(data.get("armed_at", ts))
    lifetime = now - armed_at
    if age > ttl_seconds or lifetime > max_lifetime_seconds:
        # stale or past ceiling → treat as inactive, also clean it up opportunistically
        try:
            p.unlink()
        except OSError:
            pass
        return False
    return True
