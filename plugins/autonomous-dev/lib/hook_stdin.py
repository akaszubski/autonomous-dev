"""Hook stdin utilities — single-read cache + session_id extraction (Issue #999 — Phase E).

Phase E hooks need to read the PreToolUse JSON payload from stdin AND extract
the session_id without consuming the stream twice (stdin is a one-shot stream).
This module provides:

- ``read_stdin_once()``: Module-level cache of the parsed dict. First call reads
  and parses; subsequent calls return the cached result. Returns ``None`` on
  malformed/empty input (fail-open contract — Phase E hooks must NEVER raise on
  bad stdin).
- ``extract_session_id(data)``: Pulls the session_id from the input dict, with a
  fallback to the ``CLAUDE_SESSION_ID`` env var. Returns ``None`` for missing,
  empty, or sentinel "unknown" values so callers can short-circuit safely.

Design notes:
    - NOT lru_cache — the underlying ``sys.stdin.read()`` exhausts the stream
      after the first call, so the cache is consumed-once behavior, not key-
      indexed memoization.
    - Module-level ``_stdin_data`` + ``_stdin_consumed`` sentinel: required so
      we can distinguish "read returned None because stdin was empty/malformed"
      from "read has not been called yet".
    - Fail-open: any IO/JSON exception path returns ``None``. Phase E hooks
      treat ``None`` as "no session context — enforce normally".

Issue: #999 (Phase E — hook enforcement cutover from observe to enforce).
"""

from __future__ import annotations

import json
import os
import sys

__all__ = ["read_stdin_once", "extract_session_id"]


# Module-level cache. The sentinel guards against re-reading an exhausted stream.
_stdin_data: dict | None = None
_stdin_consumed: bool = False


def read_stdin_once() -> dict | None:
    """Read and parse stdin once; return the cached dict on subsequent calls.

    The first call reads from ``sys.stdin`` and parses as JSON. The result is
    cached at module level so subsequent calls return the same object without
    re-reading (the stream is already exhausted).

    Returns:
        Parsed dict on success. ``None`` if stdin is empty, malformed JSON, or
        any IO error occurred. Callers MUST treat ``None`` as "no payload" and
        fail-open — never raise.
    """
    global _stdin_data, _stdin_consumed

    if _stdin_consumed:
        return _stdin_data

    _stdin_consumed = True
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        _stdin_data = None
        return None

    if not raw or not raw.strip():
        _stdin_data = None
        return None

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        _stdin_data = None
        return None

    if not isinstance(data, dict):
        _stdin_data = None
        return None

    _stdin_data = data
    return _stdin_data


def extract_session_id(data: dict | None) -> str | None:
    """Extract the session_id from a hook input dict, with env-var fallback.

    Lookup order:
        1. ``data["session_id"]`` (top-level field on every PreToolUse payload)
        2. ``CLAUDE_SESSION_ID`` env var (set by Claude Code)

    Sentinel handling: empty strings and the literal string ``"unknown"`` are
    treated as "no session id" and return ``None``. This matches the
    convention in ``session_mode._resolve_session_id`` which treats those
    same values as unknown.

    Args:
        data: Parsed PreToolUse hook input dict, or ``None``.

    Returns:
        A non-empty session_id string, or ``None`` if neither source provides
        a usable value.
    """
    candidate: str | None = None

    if isinstance(data, dict):
        raw = data.get("session_id")
        if isinstance(raw, str):
            candidate = raw

    if not candidate:
        env_val = os.environ.get("CLAUDE_SESSION_ID")
        if isinstance(env_val, str):
            candidate = env_val

    if candidate is None:
        return None
    if candidate == "" or candidate == "unknown":
        return None
    return candidate
