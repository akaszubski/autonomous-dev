#!/usr/bin/env python3
"""
Pipeline Completion State - Shared state for agent ordering enforcement.

Manages a per-session JSON state file that tracks which pipeline agents
have completed. Written by unified_session_tracker.py (SubagentStop),
read by unified_pre_tool.py (PreToolUse) to enforce ordering.

State file path (legacy): /tmp/pipeline_agent_completions_{hash(session_id)[:8]}.json
State file path (run_id):  /tmp/pipeline_agent_completions_{run_id}.json

When ``run_id`` is provided to any public function, the run-id-scoped path is
used instead of the legacy sha256(session_id) path. This enables per-invocation
isolation and crash-resume without collision. Existing callers that omit
``run_id`` continue to use the legacy path with no behavior change. (#1041)

Issues: #625, #629, #632, #1041
"""

import fcntl
import glob
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from .pipeline_state import get_legacy_sentinel_path  # type: ignore
except ImportError:  # pragma: no cover - script-style import fallback
    try:
        from pipeline_state import get_legacy_sentinel_path  # type: ignore
    except ImportError:
        def get_legacy_sentinel_path(repo_root: Optional[Path] = None) -> Path:  # type: ignore
            # Last-resort: behave like the pre-#1206 hardcoded fallback so the
            # module still imports in environments without path_utils.
            return Path("/tmp/implement_pipeline_state.json")

# Regex for validating run_id values. Only alphanumerics, hyphens, and underscores
# are permitted, with a maximum length of 64 characters. This prevents path
# traversal attacks via run_id. (Security Finding 1 — CRITICAL A03/A01)
_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# File-based bypass for the agent completeness gate.
# The env var SKIP_AGENT_COMPLETENESS_GATE=1 is unreachable from Bash commands
# because the hook runs in a separate process spawned by the harness.
# This file provides a one-shot bypass: touch the file, it's consumed on first check.
# Issue #802
SKIP_GATE_FILE = Path("/tmp/skip_agent_completeness_gate")

# Staleness TTL for the 'unknown' session-id fallback merge.
# When the primary-session lookup in get_completed_agents() falls back to
# reading the 'unknown' state file (for the Issue #738/#777 in-flight boot
# case where the coordinator initialized state before CLAUDE_SESSION_ID was
# known), the merge ONLY applies if the 'unknown' state file's mtime is
# within this window. Older 'unknown' state from crashed/stale prior runs
# must not contaminate a fresh pipeline. Issue #875 / Issue #904.
STALE_UNKNOWN_TTL_SECONDS = 3600


def _find_activity_log_dir(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Locate the ``.claude/logs/activity/`` directory by walking up from *start_dir*.

    Mirrors the pattern in ``coordinator_log.py`` / ``session_activity_logger.py``.
    The search starts at *start_dir* (defaults to ``Path.cwd()``) and checks
    each ancestor for a ``.claude`` directory.  Does NOT create the directory
    (read-only resolver).

    Args:
        start_dir: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to ``<repo>/.claude/logs/activity/`` if found, else ``None``.
    """
    cwd = start_dir or Path.cwd()
    candidates = [cwd] + list(cwd.parents)
    for parent in candidates:
        log_dir = parent / ".claude" / "logs" / "activity"
        if log_dir.is_dir():
            return log_dir
    return None


def _resolve_session_id_from_activity_log(
    log_dir: Optional[Path] = None,
    today: Optional[str] = None,
) -> Optional[str]:
    """Scan today's activity log JSONL for the most recent real session id.

    The activity log is written by ``session_activity_logger.py`` (PreToolUse,
    PostToolUse, SubagentStop). Those hooks see the real ``session_id`` from
    Claude Code's stdin, so the log is the source of truth in subprocess
    contexts that lack ``CLAUDE_SESSION_ID``.

    Scans the last 200 lines of the file for the FIRST encountered entry
    (newest first) with a ``session_id`` field that is:
      - a non-empty string, AND
      - not the literal ``"unknown"``.

    Args:
        log_dir: Activity log directory. Defaults to
            ``<repo>/.claude/logs/activity`` resolved from CWD.
        today: Date string in ``YYYY-MM-DD`` format. Defaults to today (UTC-free
            local clock — matches the writer in ``session_activity_logger.py``).

    Returns:
        Real session id string, or ``None`` if the log is missing/empty/has
        only ``"unknown"`` / corrupt JSON throughout. Never raises.

    Issues: #1093
    """
    if log_dir is None:
        log_dir = _find_activity_log_dir()
    if log_dir is None:
        return None
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")

    log_file = log_dir / f"{today}.jsonl"
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return None

    # Newest entries are at the end (append-only log).
    # Bound the scan to the last 200 lines for performance.
    tail = lines[-200:]
    for raw in reversed(tail):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            # Skip corrupt lines, don't abort the whole scan.
            continue
        if not isinstance(entry, dict):
            continue
        sid = entry.get("session_id")
        if isinstance(sid, str) and sid and sid != "unknown":
            return sid
    return None


def resolve_session_id(
    *,
    sentinel_path: Optional[str] = None,
    max_age_seconds: int = 3600,
) -> str:
    """Resolve the current Claude session id via fallback chain.

    Issue #1081 (drift fix); Issue #1093 (activity-log fallback);
    semantics from Issue #904.

    Fallback chain (first match wins):
        1. ``CLAUDE_SESSION_ID`` env var, if set and non-empty.
        2. ``sentinel_path`` JSON file's ``session_id`` field, if file
           exists, mtime is within ``max_age_seconds``, JSON parses,
           the field is a non-empty string, AND the value is not the
           literal ``"unknown"`` (a stale sentinel from boot-time).
        3. Today's activity log (``.claude/logs/activity/{YYYY-MM-DD}.jsonl``)
           scanned for the most recent entry with a real ``session_id``.
           This is the load-bearing fallback for Bash subprocess contexts
           that lack the env var AND whose sentinel was written under
           ``"unknown"``. (#1093)
        4. The literal string ``"unknown"``.

    NEVER raises. Catches ``OSError``, ``json.JSONDecodeError``,
    ``ValueError`` and unexpected types — all paths return ``"unknown"``.

    Used by ``commands/implement.md`` STEP 0, STEP 2, and the
    Pre-Dispatch Ordering Protocol to recover session id in subshell
    contexts that drop the env var (nested heredocs, pipe subshells).

    Issue #1206: ``sentinel_path`` now defaults to the per-repo path
    ``<repo>/.claude/local/implement_pipeline_state.json`` resolved at call
    time so cross-repo concurrent sessions stay isolated.
    """
    if sentinel_path is None:
        sentinel_path = str(get_legacy_sentinel_path())
    env_sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if env_sid:
        return env_sid

    # Step 2: sentinel file. Only return its session_id when it is a real
    # value (not the boot-time "unknown" placeholder) — otherwise fall
    # through to the activity-log scan.
    sentinel_sid: Optional[str] = None
    try:
        st = os.stat(sentinel_path)
        if (time.time() - st.st_mtime) <= max_age_seconds:
            try:
                with open(sentinel_path) as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError, ValueError):
                data = None
            if isinstance(data, dict):
                candidate = data.get("session_id")
                if isinstance(candidate, str) and candidate and candidate != "unknown":
                    sentinel_sid = candidate
    except OSError:
        pass

    if sentinel_sid is not None:
        return sentinel_sid

    # Step 3: activity log scan (Issue #1093).
    log_sid = _resolve_session_id_from_activity_log()
    if log_sid is not None:
        return log_sid

    # Step 4: legacy fallback.
    return "unknown"


def _check_file_bypass() -> bool:
    """Check and consume the file-based bypass for the agent completeness gate.

    If the bypass file exists, delete it (one-shot consumption) and return True.
    Fail-open on deletion errors to avoid blocking commits.

    Returns:
        True if bypass file was found (and consumed), False otherwise.

    **IMPORTANT — Chained && does not work**: The hook intercepts the entire
    compound Bash command before any part of it executes. If you chain the
    touch and git commit with ``&&`` (e.g.,
    ``touch /tmp/skip_agent_completeness_gate && git commit -m "..."``), the
    hook's pre-tool phase runs first and checks for the bypass file — but
    ``touch`` has not executed yet, so the file is absent and the bypass has
    no effect. You MUST run ``touch /tmp/skip_agent_completeness_gate`` as a
    SEPARATE Bash call first, wait for it to complete, then run ``git commit``
    as a second, separate Bash call. Chaining with ``&&`` WILL NOT WORK.

    Issues: #802, #1212
    """
    try:
        if SKIP_GATE_FILE.exists():
            try:
                SKIP_GATE_FILE.unlink()
            except OSError:
                pass  # Fail-open: bypass even if unlink fails
            return True
    except OSError:
        pass  # Fail-open on existence check errors
    return False


def _state_file_path(session_id: str, *, run_id: Optional[str] = None) -> Path:
    """Compute the state file path for a given session.

    When ``run_id`` is provided (non-None, non-empty), the path is
    ``/tmp/pipeline_agent_completions_{run_id}.json``. Otherwise, the legacy
    sha256(session_id)[:8] hash scheme is used. (#1041)

    Args:
        session_id: The pipeline session identifier.
        run_id: Optional per-invocation run identifier. When set, takes
            precedence over the session-based hash.

    Returns:
        Path to the state file in /tmp.
    """
    if run_id:
        if not _RUN_ID_RE.match(run_id):
            raise ValueError(
                f"run_id contains invalid characters: {run_id!r}\n"
                f"Expected: 1-64 characters matching [a-zA-Z0-9_-]\n"
                f"See: docs/ARCHITECTURE-OVERVIEW.md"
            )
        return Path(f"/tmp/pipeline_agent_completions_{run_id}.json")
    h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    return Path(f"/tmp/pipeline_agent_completions_{h}.json")


def _read_state(session_id: str, *, run_id: Optional[str] = None) -> dict:
    """Read state file with file locking. Returns empty dict on any failure.

    Args:
        session_id: The pipeline session identifier.
        run_id: Optional per-invocation run identifier passed to
            ``_state_file_path``. (#1041)

    Returns:
        Parsed state dict, or empty dict if file missing/corrupt/stale.
    """
    path = _state_file_path(session_id, run_id=run_id)
    if not path.exists():
        return {}

    # Stale check: ignore files older than 2 hours
    try:
        mtime = path.stat().st_mtime
        if time.time() - mtime > 7200:
            return {}
    except OSError:
        return {}

    try:
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _write_state(session_id: str, state: dict, *, run_id: Optional[str] = None) -> None:
    """Write state file atomically with file locking.

    The state file is chmod'd to ``0o600`` (owner read/write only) immediately
    after open. This narrows the previously world-readable default in /tmp
    and protects session-scoped HMAC + completion data from unprivileged
    inspection on multi-user systems. chmod failure is non-fatal: the write
    still proceeds. (#1169)

    Args:
        session_id: The pipeline session identifier.
        state: The state dict to write.
        run_id: Optional per-invocation run identifier passed to
            ``_state_file_path``. (#1041)
    """
    path = _state_file_path(session_id, run_id=run_id)
    try:
        with open(path, "w") as f:
            # #1169: tighten permissions to 0o600 before holding the lock so
            # the file is never world-readable, even during the brief window
            # before the lock is released. Failure here is non-fatal — chmod
            # can legitimately fail on filesystems that don't support POSIX
            # modes (e.g. tmpfs mounted noexec/nosuid on some configs).
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass  # Non-blocking: state write failure is not fatal


def _ensure_state(session_id: str, *, run_id: Optional[str] = None) -> dict:
    """Read existing state or create a new skeleton.

    Args:
        session_id: The pipeline session identifier.
        run_id: Optional per-invocation run identifier passed to
            ``_read_state``. (#1041)

    Returns:
        A valid state dict (may be freshly created).
    """
    state = _read_state(session_id, run_id=run_id)
    if not state:
        from datetime import datetime, timezone

        state = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "validation_mode": "sequential",
            "completions": {},
            "prompt_baselines": {},
        }
    return state


def record_agent_completion(
    session_id: str,
    agent_type: str,
    *,
    issue_number: int = 0,
    success: bool = True,
    is_remediation: bool = False,
    run_id: Optional[str] = None,
    _single_scope: bool = False,
) -> None:
    """Record that an agent has completed for a given session and issue.

    By default writes under THREE scope keys (tri-scope write), eliminating
    the manual workaround of calling this function multiple times with
    different ``issue_number`` values:

    - ``str(issue_number)`` — the primary key (e.g., ``"42"`` for issue 42)
    - ``"0"`` — the unscoped/default key (always written)
    - ``"unscoped"`` — a stable third key for readers that need an
      issue-agnostic view

    When ``issue_number=0`` is passed, the ``"0"`` and ``"unscoped"``
    entries are written (no separate numeric key since N==0 is the same as
    the default key). (#1046)

    Pass ``_single_scope=True`` to opt out of tri-scope writes and write
    only to ``str(issue_number)``. This is intended for tests that verify
    single-scope state shape; it should not be used in production callers.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type (e.g., "researcher-local", "planner").
        issue_number: The issue number (0 for non-batch).
        success: Whether the agent completed successfully.
        is_remediation: When True, this completion is part of a remediation
            pass (e.g., reviewer re-run after BLOCKING findings). The stored
            entry is marked so the intent validator can skip duplicate-agent
            ordering findings for remediation events. Issue #902 / Issue #904.
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1041)
        _single_scope: When True, write only to ``str(issue_number)`` (back-
            compat opt-out). Intended for test isolation only. (#1046)

    Notes:
        Backwards compatible: existing callers that do not pass
        ``is_remediation`` continue to work — the stored value is the plain
        boolean ``success`` (legacy shape). When ``is_remediation=True`` is
        passed, the stored value becomes a dict ``{"success": <bool>,
        "remediation": True}``. All readers in this module tolerate both
        shapes (see ``_completion_is_success``).

    Issues: #1046
    """
    # Build the completion entry (plain bool or remediation dict).
    if is_remediation:
        entry = {
            "success": bool(success),
            "remediation": True,
        }
    else:
        entry = success  # type: ignore[assignment]  # plain bool, legacy shape

    state = _ensure_state(session_id, run_id=run_id)
    completions = state.setdefault("completions", {})

    if _single_scope:
        # Opt-out path: write only to str(issue_number).
        issue_completions = completions.setdefault(str(issue_number), {})
        issue_completions[agent_type] = entry
    else:
        # Tri-scope write: write to the primary key, "0", and "unscoped".
        # Determine the set of scope keys to write to.
        scope_keys: set[str] = {"0", "unscoped"}
        if issue_number != 0:
            scope_keys.add(str(issue_number))
        for key in scope_keys:
            issue_completions = completions.setdefault(key, {})
            issue_completions[agent_type] = entry

    _write_state(session_id, state, run_id=run_id)


def _completion_is_success(entry) -> bool:
    """Interpret a stored completion entry as a success boolean.

    Completion entries may be stored as:
      - ``bool`` (legacy shape — ``True`` means success).
      - ``dict`` with a ``"success"`` key (Issue #902 / #904 remediation shape).

    Any other type is treated as non-success (fail-safe).

    Args:
        entry: Value read from ``completions[issue_key][agent_type]``.

    Returns:
        True when the entry represents a successful completion.
    """
    if isinstance(entry, bool):
        return entry
    if isinstance(entry, dict):
        return bool(entry.get("success", False))
    return False


def is_remediation_completion(
    session_id: str,
    agent_type: str,
    *,
    issue_number: int = 0,
) -> bool:
    """Check whether a recorded completion was flagged as remediation.

    Reads both the primary session state and the 'unknown' fallback state
    (respecting the TTL in ``STALE_UNKNOWN_TTL_SECONDS``) so the result is
    consistent with ``get_completed_agents``. Returns False when no matching
    completion exists or the recorded entry has no remediation flag.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type (e.g., "reviewer").
        issue_number: The issue number (0 for non-batch).

    Returns:
        True if the completion entry exists and has ``remediation=True``.

    Issues: #902, #904.
    """
    def _read(sid: str) -> dict:
        state = _read_state(sid)
        if not state:
            return {}
        completions = state.get("completions", {})
        issue_completions = completions.get(str(issue_number), {})
        return issue_completions if isinstance(issue_completions, dict) else {}

    primary = _read(session_id)
    entry = primary.get(agent_type)
    if isinstance(entry, dict) and entry.get("remediation") is True:
        return True

    # Check unknown-session fallback (with TTL guard) for completeness.
    if session_id != "unknown":
        path = _state_file_path("unknown")
        try:
            if path.exists():
                mtime = path.stat().st_mtime
                if time.time() - mtime <= STALE_UNKNOWN_TTL_SECONDS:
                    fallback = _read("unknown")
                    f_entry = fallback.get(agent_type)
                    if isinstance(f_entry, dict) and f_entry.get("remediation") is True:
                        return True
        except OSError:
            pass

    return False


def get_completed_agents(
    session_id: str,
    *,
    issue_number: int = 0,
    run_id: Optional[str] = None,
) -> set[str]:
    """Get the set of agents that have completed for a session/issue.

    Falls back to checking the 'unknown' session state when the primary
    session lookup returns empty. This handles the case where the coordinator
    initialized pipeline state before CLAUDE_SESSION_ID was set — state is
    written under session_id='unknown' but the hook reads with the real session
    ID. Issue #738.

    Staleness guard (Issue #875 / #904): the 'unknown'-session merge is
    skipped when the 'unknown' state file's mtime is older than
    ``STALE_UNKNOWN_TTL_SECONDS``. This prevents cross-pipeline contamination
    from a crashed / abandoned prior run whose state file still lingers in
    ``/tmp/`` — the old 'unknown' state must not bleed into a fresh session.

    Note: when ``run_id`` is provided, the unknown-session fallback merge is
    skipped — run-id-scoped state files are per-invocation and do not use the
    'unknown' bootstrap path. (#1041)

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1041)

    Returns:
        Set of agent type strings that completed successfully.
    """
    result: set[str] = set()
    state = _read_state(session_id, run_id=run_id)
    if state:
        completions = state.get("completions", {})
        issue_key = str(issue_number)
        issue_completions = completions.get(issue_key, {})
        if isinstance(issue_completions, dict):
            result = {
                k for k, v in issue_completions.items()
                if _completion_is_success(v)
            }

    # Skip the unknown-session fallback merge when run_id is set.
    # Run-id-scoped state files are per-invocation; the 'unknown' bootstrap
    # path only applies to the legacy session-id-hashed scheme. (#1041)
    if run_id:
        return result

    # Merge completions from the 'unknown' session. The coordinator may have
    # recorded some agent completions before CLAUDE_SESSION_ID was available,
    # writing them under session_id='unknown'. We MERGE (not fallback) because
    # the primary session may have SOME completions but be MISSING agents that
    # were recorded under 'unknown'. Issues #738, #777.
    #
    # Staleness guard (Issue #875 / #904): skip merge if 'unknown' state is
    # older than STALE_UNKNOWN_TTL_SECONDS — prevents contamination from a
    # crashed / abandoned prior pipeline whose /tmp state file survived.
    if session_id != "unknown":
        path = _state_file_path("unknown")
        try:
            if path.exists():
                mtime = path.stat().st_mtime
                if time.time() - mtime > STALE_UNKNOWN_TTL_SECONDS:
                    # Stale 'unknown' state — do NOT merge.
                    return result
            else:
                return result
        except OSError:
            # Fail-safe: if stat fails we can't verify freshness, skip merge.
            return result

        fallback_state = _read_state("unknown")
        if fallback_state:
            completions = fallback_state.get("completions", {})
            issue_key = str(issue_number)
            issue_completions = completions.get(issue_key, {})
            if isinstance(issue_completions, dict):
                fallback_result = {
                    k for k, v in issue_completions.items()
                    if _completion_is_success(v)
                }
                if fallback_result - result:
                    import logging
                    logging.getLogger("pipeline_completion_state").info(
                        "Merging completions from session_id='unknown' (%s) into "
                        "primary session_id=%r (%s). Issues #738, #777.",
                        fallback_result - result,
                        session_id,
                        result,
                    )
                    result |= fallback_result

    return result


def record_agent_launch(
    session_id: str,
    agent_type: str,
    *,
    issue_number: int = 0,
) -> None:
    """Record that an agent has been launched (started) for a given session and issue.

    Called from PreToolUse BEFORE the agent runs. Tracks which agents have been
    started, separate from completions. Used by the parallel-mode defense-in-depth
    guard to distinguish "running concurrently" from "skipped entirely".

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type (e.g., "reviewer", "security-auditor").
        issue_number: The issue number (0 for non-batch).

    Issues: #686
    """
    state = _ensure_state(session_id)
    launches = state.setdefault("launches", {})
    issue_key = str(issue_number)
    issue_launches = launches.setdefault(issue_key, {})
    issue_launches[agent_type] = True
    _write_state(session_id, state)


def get_launched_agents(
    session_id: str,
    *,
    issue_number: int = 0,
) -> set[str]:
    """Get the set of agents that have been launched for a session/issue.

    Falls back to checking the 'unknown' session state when the primary
    session lookup returns empty. This mirrors the fallback in
    get_completed_agents. Issue #738.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).

    Returns:
        Set of agent type strings that have been launched.

    Issues: #686, #738
    """
    result = set()
    state = _read_state(session_id)
    if state:
        launches = state.get("launches", {})
        issue_key = str(issue_number)
        issue_launches = launches.get(issue_key, {})
        result = {k for k, v in issue_launches.items() if v}

    # Merge launches from 'unknown' session (same rationale as
    # get_completed_agents — see Issues #738, #777).
    if session_id != "unknown":
        fallback_state = _read_state("unknown")
        if fallback_state:
            launches = fallback_state.get("launches", {})
            issue_key = str(issue_number)
            issue_launches = launches.get(issue_key, {})
            fallback_result = {k for k, v in issue_launches.items() if v}
            result |= fallback_result

    return result


def record_prompt_baseline(
    session_id: str,
    agent_type: str,
    word_count: int,
    issue_number: int,
) -> None:
    """Record baseline prompt word count for an agent.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type.
        word_count: The prompt word count.
        issue_number: The issue number.
    """
    state = _ensure_state(session_id)
    baselines = state.setdefault("prompt_baselines", {})
    baselines[agent_type] = word_count
    _write_state(session_id, state)


def get_prompt_baseline(session_id: str, agent_type: str) -> Optional[int]:
    """Get baseline prompt word count for an agent.

    Args:
        session_id: The pipeline session identifier.
        agent_type: The agent type.

    Returns:
        Word count if recorded, None otherwise.
    """
    state = _read_state(session_id)
    if not state:
        return None
    baselines = state.get("prompt_baselines", {})
    value = baselines.get(agent_type)
    return int(value) if value is not None else None


def set_validation_mode(
    session_id: str,
    mode: str,
    *,
    issue_number: int = 0,  # noqa: ARG001 — accepted for call-signature parity (#1214)
    run_id: Optional[str] = None,
) -> None:
    """Set the validation mode for ordering enforcement.

    Validation mode is a session-scoped (not issue-scoped) setting. The
    ``issue_number`` parameter is accepted for call-signature parity with
    the rest of the module's API (record_agent_completion, record_agent_launch,
    record_research_skipped, etc.) and is intentionally discarded — callers
    that pass it by reflex no longer get a TypeError mid-pipeline. (#1214)

    Args:
        session_id: The pipeline session identifier.
        mode: "sequential" or "parallel".
        issue_number: Accepted-but-ignored. Validation mode is session-scoped;
            this parameter exists only so the function shares its kwargs with
            the rest of the module. (#1214)
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path.
            (#1041 — symmetry with the rest of the module's API)
    """
    state = _ensure_state(session_id, run_id=run_id)
    state["validation_mode"] = mode
    _write_state(session_id, state, run_id=run_id)


def get_validation_mode(
    session_id: str,
    *,
    run_id: Optional[str] = None,
) -> str:
    """Get the validation mode for ordering enforcement.

    Args:
        session_id: The pipeline session identifier.
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path.
            (#1041 — symmetry with the rest of the module's API)

    Returns:
        "sequential" (default) or "parallel".
    """
    state = _read_state(session_id, run_id=run_id)
    if not state:
        return "sequential"
    return state.get("validation_mode", "sequential")


def verify_batch_cia_completions(session_id: str) -> tuple[bool, list[int], list[int]]:
    """Verify CIA completed for all batch issues.

    Checks the completion state for a given session and verifies that
    'continuous-improvement-analyst' has been recorded as completed for
    every tracked issue. Designed to be called from the unified_pre_tool
    hook before allowing git commit in batch mode.

    Fail-open: returns (True, [], []) on any error to avoid blocking
    legitimate commits due to state file issues.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Tuple of (all_passed, issues_with_cia, issues_missing_cia).
        all_passed is True when every tracked issue has CIA completion.
        issues_with_cia lists issue numbers that have CIA.
        issues_missing_cia lists issue numbers missing CIA.

    Issues: #712
    """
    # Escape hatch: skip gate entirely if env var set
    if os.environ.get("SKIP_BATCH_CIA_GATE", "").strip().lower() in ("1", "true", "yes"):
        return (True, [], [])

    try:
        state = _read_state(session_id)
        if not state:
            # No state file — fail-open (nothing to enforce)
            return (True, [], [])

        completions = state.get("completions", {})
        if not completions:
            # No completions tracked — fail-open
            return (True, [], [])

        issues_with_cia: list[int] = []
        issues_missing_cia: list[int] = []

        for issue_key, issue_completions in completions.items():
            # Skip the "0" key (non-batch single-issue pipeline)
            if issue_key == "0":
                continue

            try:
                issue_num = int(issue_key)
            except (ValueError, TypeError):
                continue

            if not isinstance(issue_completions, dict):
                continue

            if _completion_is_success(
                issue_completions.get("continuous-improvement-analyst")
            ):
                issues_with_cia.append(issue_num)
            else:
                issues_missing_cia.append(issue_num)

        # If no batch issues found (only "0" key or empty), fail-open
        if not issues_with_cia and not issues_missing_cia:
            return (True, [], [])

        all_passed = len(issues_missing_cia) == 0
        return (all_passed, sorted(issues_with_cia), sorted(issues_missing_cia))

    except Exception:
        # Fail-open: any error returns pass
        return (True, [], [])


def record_doc_verdict(
    session_id: str,
    issue_number: int,
    verdict: str,
) -> None:
    """Record a doc-master verdict for a specific issue.

    Persists the verdict string to the completion state JSON under
    a "doc-master-verdict" key at the issue level. Uses the same
    fcntl locking pattern as record_agent_completion.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number.
        verdict: The verdict string (e.g., "PASS", "FAIL", "DOCS-UPDATED",
                 "NO-UPDATE-NEEDED", "DOCS-DRIFT-FOUND", "MISSING", "SHALLOW").

    Issues: #837
    """
    state = _ensure_state(session_id)
    completions = state.setdefault("completions", {})
    issue_key = str(issue_number)
    issue_completions = completions.setdefault(issue_key, {})
    issue_completions["doc-master-verdict"] = verdict
    _write_state(session_id, state)


# Valid doc-master verdicts that count as "verdict present".
_VALID_DOC_VERDICTS: set[str] = {
    "PASS",
    "FAIL",
    "DOCS-UPDATED",
    "NO-UPDATE-NEEDED",
    "DOCS-DRIFT-FOUND",
}


def verify_batch_doc_master_completions(session_id: str) -> tuple[bool, list[int], list[int]]:
    """Verify doc-master completed with a valid verdict for all batch issues.

    Checks the completion state for a given session and verifies that
    'doc-master' has been recorded as completed AND has a valid verdict
    for every tracked issue. Issues where doc-master completed but the
    verdict is MISSING, SHALLOW, or absent are treated as incomplete.

    Backward compatible: old state entries without a "doc-master-verdict"
    field but WITH doc-master completion pass through (fail-open on
    missing verdict field for backward compatibility).

    Fail-open: returns (True, [], []) on any error to avoid blocking
    legitimate commits due to state file issues.

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Tuple of (all_passed, issues_with_doc_master, issues_missing_doc_master).
        all_passed is True when every tracked issue has doc-master completion
        AND a valid verdict (or no verdict field at all for backward compat).
        issues_with_doc_master lists issue numbers that have doc-master.
        issues_missing_doc_master lists issue numbers missing doc-master
        or having an invalid verdict (MISSING/SHALLOW).

    Issues: #786, #837
    """
    # Escape hatch: skip gate entirely if env var set
    if os.environ.get("SKIP_BATCH_DOC_MASTER_GATE", "").strip().lower() in ("1", "true", "yes"):
        return (True, [], [])

    try:
        state = _read_state(session_id)
        if not state:
            # No state file — fail-open (nothing to enforce)
            return (True, [], [])

        completions = state.get("completions", {})
        if not completions:
            # No completions tracked — fail-open
            return (True, [], [])

        issues_with_doc_master: list[int] = []
        issues_missing_doc_master: list[int] = []

        for issue_key, issue_completions in completions.items():
            # Skip the "0" key (non-batch single-issue pipeline)
            if issue_key == "0":
                continue

            try:
                issue_num = int(issue_key)
            except (ValueError, TypeError):
                continue

            if not isinstance(issue_completions, dict):
                continue

            if _completion_is_success(issue_completions.get("doc-master")):
                # Doc-master completed — now check verdict if present
                verdict = issue_completions.get("doc-master-verdict")
                if verdict is None:
                    # Backward compat: no verdict field recorded (old state).
                    # Treat as valid — fail-open on missing field.
                    issues_with_doc_master.append(issue_num)
                elif verdict in _VALID_DOC_VERDICTS:
                    # Valid verdict present
                    issues_with_doc_master.append(issue_num)
                else:
                    # Invalid verdict (MISSING, SHALLOW, etc.) — treat as incomplete
                    issues_missing_doc_master.append(issue_num)
            else:
                issues_missing_doc_master.append(issue_num)

        # If no batch issues found (only "0" key or empty), fail-open
        if not issues_with_doc_master and not issues_missing_doc_master:
            return (True, [], [])

        all_passed = len(issues_missing_doc_master) == 0
        return (all_passed, sorted(issues_with_doc_master), sorted(issues_missing_doc_master))

    except Exception:
        # Fail-open: any error returns pass
        return (True, [], [])


def record_pytest_gate_passed(
    session_id: str,
    *,
    issue_number: int = 0,
    passed: bool = True,
    run_id: Optional[str] = None,
) -> None:
    """Record pytest gate result as a virtual agent completion.

    Uses the existing record_agent_completion infrastructure with
    agent_type='pytest-gate'. This means get_completed_agents() will
    automatically include 'pytest-gate' when the gate has passed.

    Args:
        session_id: Current session ID.
        issue_number: Issue number (0 for single-issue pipeline).
        passed: Whether pytest gate passed (True) or failed (False).
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1041)

    Issues: #838
    """
    record_agent_completion(
        session_id, "pytest-gate", issue_number=issue_number, success=passed, run_id=run_id
    )


def get_pytest_gate_passed(
    session_id: str,
    *,
    issue_number: int = 0,
) -> bool:
    """Check if pytest gate has been recorded as passed.

    Args:
        session_id: Current session ID.
        issue_number: Issue number (0 for single-issue pipeline).

    Returns:
        True if pytest gate passed or SKIP_PYTEST_GATE env var is set.
        False if not recorded or recorded as failed.

    Issues: #838
    """
    skip = os.environ.get("SKIP_PYTEST_GATE", "").strip().lower()
    if skip in ("1", "true", "yes"):
        return True
    return "pytest-gate" in get_completed_agents(session_id, issue_number=issue_number)


def record_research_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
    run_id: Optional[str] = None,
) -> None:
    """Record that research was skipped for a given session/issue.

    Called by the coordinator after STEP 3.5 determines that research
    agents should be skipped (fully-specified change detection).

    When ``issue_number`` is non-zero, the marker is recorded under BOTH
    ``str(issue_number)`` AND ``"0"`` in a single atomic write. The "0"
    fallback key is required because the commit-time gate
    (verify_pipeline_agent_completions) is invoked from a hook that does
    not parse the issue number out of the commit message and therefore
    queries with ``issue_number=0``. Writing under both keys preserves
    the existing reader contract — get_research_skipped() looks up
    whichever key the caller supplies. This mirrors the multi-scope
    auto-write pattern already used by record_agent_completion(). (#1213)

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1041)

    Issues: #802, #1213
    """
    state = _ensure_state(session_id, run_id=run_id)
    research_skipped = state.setdefault("research_skipped", {})
    issue_key = str(issue_number)
    research_skipped[issue_key] = True
    # #1213: Also write to the "0" fallback scope so the commit-time gate
    # (which calls verify_pipeline_agent_completions with issue_number=0)
    # can see the marker. No-op when issue_number is already 0.
    if issue_number != 0:
        research_skipped["0"] = True
    _write_state(session_id, state, run_id=run_id)


def get_research_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
    run_id: Optional[str] = None,
) -> bool:
    """Check if research was skipped for a given session/issue.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1045)

    Returns:
        True if research was recorded as skipped, False otherwise.

    Issues: #802, #1045
    """
    state = _read_state(session_id, run_id=run_id)
    if not state:
        return False
    research_skipped = state.get("research_skipped", {})
    issue_key = str(issue_number)
    return bool(research_skipped.get(issue_key, False))


def record_plan_critic_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
    run_id: Optional[str] = None,
    plan_path: Optional[str] = None,
    bypass_reason: Optional[str] = None,
) -> None:
    """Record that plan-critic was skipped for a given session/issue.

    Called by the coordinator at STEP 5.5a when a pre-validated plan
    is found in `.claude/plans/`, bypassing plan-critic invocation.

    When ``issue_number`` is non-zero, the marker is recorded under BOTH
    ``str(issue_number)`` AND ``"0"`` in a single atomic write. Symmetric
    to the record_research_skipped() fix in #1213 — same writer-compensates-
    for-reader rationale: the commit-time gate queries with
    ``issue_number=0`` and the reader contract is preserved.

    When ``plan_path`` is provided (Issue #1218), it is recorded under the
    ``plan_critic_skipped_plan_path`` namespace so STEP 8.5 can extract the
    canonical Acceptance Criteria section verbatim from the pre-validated
    plan file rather than relying on the planner's STEP 5 paraphrase.

    When ``bypass_reason`` is provided (Issue #1279), it is recorded under
    the ``plan_critic_bypass_reason`` namespace for audit trail purposes.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1041)
        plan_path: Optional canonical plan file path (Issue #1218). When set,
            recorded so STEP 8.5 can canonicalize ACs from the plan file.
        bypass_reason: Optional reason why plan-critic was bypassed (#1279).

    Issues: #878, #1213, #1218, #1279, #1325
    """
    state = _ensure_state(session_id, run_id=run_id)
    plan_critic_skipped = state.setdefault("plan_critic_skipped", {})
    issue_key = str(issue_number)
    plan_critic_skipped[issue_key] = True
    # #1213: Also write to the "0" fallback scope so the commit-time gate
    # (which calls verify_pipeline_agent_completions with issue_number=0)
    # can see the marker. No-op when issue_number is already 0.
    if issue_number != 0:
        plan_critic_skipped["0"] = True
    # #1218: Record the canonical plan path for STEP 8.5 AC canonicalization.
    if plan_path:
        plan_paths = state.setdefault("plan_critic_skipped_plan_path", {})
        plan_paths[issue_key] = plan_path
        if issue_number != 0:
            plan_paths["0"] = plan_path
    # #1279: Record the bypass reason for audit trail.
    if bypass_reason:
        reasons = state.setdefault("plan_critic_bypass_reason", {})
        reasons[issue_key] = bypass_reason
        if issue_number != 0:
            reasons["0"] = bypass_reason
    _write_state(session_id, state, run_id=run_id)

    # Issue #1325: Emit activity log event when plan-critic is skipped
    # so CIA can verify the skip has a corresponding logged justification.
    log_dir = _find_activity_log_dir()
    if log_dir is not None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "plan_critic_skipped",
            "session_id": session_id,
            "issue_number": issue_number,
            "plan_path": plan_path,
            "bypass_reason": bypass_reason or "pre-validated plan",
            "run_id": run_id,
            "source": "pipeline_completion_state",
        }
        log_file = log_dir / (datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
            # Set file permissions to 0600 (owner read/write only) for security
            os.chmod(log_file, 0o600)
        except OSError:
            # Non-blocking: activity logging failures should not disrupt pipeline
            pass


def get_plan_critic_skipped(
    session_id: str,
    *,
    issue_number: int = 0,
    run_id: Optional[str] = None,
) -> bool:
    """Check if plan-critic was skipped for a given session/issue.

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1045)

    Returns:
        True if plan-critic was recorded as skipped, False otherwise.

    Issues: #878, #1045
    """
    state = _read_state(session_id, run_id=run_id)
    if not state:
        return False
    plan_critic_skipped = state.get("plan_critic_skipped", {})
    issue_key = str(issue_number)
    return bool(plan_critic_skipped.get(issue_key, False))


def get_plan_critic_skipped_plan_path(
    session_id: str,
    *,
    issue_number: int = 0,
    run_id: Optional[str] = None,
) -> Optional[str]:
    """Return the canonical plan path recorded at STEP 5.5a (Issue #1218).

    When STEP 5.5a found a pre-validated plan and called
    ``record_plan_critic_skipped(..., plan_path=...)``, this returns that
    plan path so STEP 8.5 can extract the canonical ``## Acceptance
    Criteria`` section verbatim from the plan file rather than relying on
    the planner's STEP 5 paraphrase (which may diverge and cause
    spec-validator FAIL on phantom mismatches).

    Args:
        session_id: The pipeline session identifier.
        issue_number: The issue number (0 for non-batch).
        run_id: Optional per-invocation run identifier.

    Returns:
        The recorded plan path as a string, or None if no path was recorded.

    Issues: #1218
    """
    state = _read_state(session_id, run_id=run_id)
    if not state:
        return None
    plan_paths = state.get("plan_critic_skipped_plan_path", {})
    issue_key = str(issue_number)
    val = plan_paths.get(issue_key)
    if isinstance(val, str) and val:
        return val
    # Fallback to "0" scope (symmetric with the dual-write in record_*).
    val = plan_paths.get("0")
    if isinstance(val, str) and val:
        return val
    return None


def record_plan_critic_passed(
    session_id: str,
    plan_slug: str,
    *,
    run_id: Optional[str] = None,
) -> None:
    """Record that plan-critic passed for this session.

    Args:
        session_id: Session identifier.
        plan_slug: Slug identifier for the plan that passed critic.
        run_id: Optional test run identifier.

    Since:
        2026-06-27 (Issue #1330)
    """
    if not session_id or session_id == "unknown":
        return

    state = _ensure_state(session_id, run_id=run_id)
    state["plan_critic_passed"] = True
    state["plan_critic_passed_plan_slug"] = plan_slug
    state["plan_critic_passed_timestamp"] = datetime.now().isoformat()
    _write_state(session_id, state, run_id=run_id)


def get_plan_critic_passed(
    session_id: str,
    *,
    run_id: Optional[str] = None,
) -> bool:
    """Check if plan-critic passed for this session.

    Args:
        session_id: Session identifier.
        run_id: Optional test run identifier.

    Returns:
        True if plan_critic_passed was recorded, False otherwise.

    Since:
        2026-06-27 (Issue #1330)
    """
    if not session_id or session_id == "unknown":
        return False

    state = _read_state(session_id, run_id=run_id)
    if not state:
        return False
    
    return bool(state.get("plan_critic_passed", False))


def write_coordinator_bypass_verdict(
    issue_number: int, 
    bypass_reason: str, 
    plan_summary: Optional[str] = None
) -> None:
    """Write a coordinator bypass verdict file for audit trail.
    
    When the coordinator decides to skip plan-critic (e.g., for "mechanical 
    extension" issues), this creates a machine-readable verdict file that 
    signals the bypass was intentional.
    
    The verdict file is written atomically to `.claude/plan_critic_verdict.json`
    with a specific schema that passes hook validation.
    
    Args:
        issue_number: The issue number being processed.
        bypass_reason: The reason for bypassing plan-critic.
        plan_summary: Optional one-line summary of the plan.
        
    Issues: #1279
    """
    import tempfile
    
    # Prepare the verdict data
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Ensure reasoning is >= 100 chars (hook constraint)
    base_reasoning = f"Coordinator bypass: {bypass_reason}."
    if plan_summary:
        base_reasoning += f" {plan_summary}"
    
    # Pad if needed to meet 100 char minimum
    if len(base_reasoning) < 100:
        padding = " This bypass was recorded for audit trail purposes to distinguish intentional skips from missed invocations."
        base_reasoning = base_reasoning + padding[:max(0, 100 - len(base_reasoning))]
    
    verdict = {
        "verdict": "COORDINATOR_BYPASS",
        "composite_score": 0.0,
        "timestamp": timestamp,
        "reasoning": base_reasoning,
        "axis_scores": {
            "coordinator_bypass": 0,
            "skip_reason_documented": 1,
            "audit_trail_present": 1
        },
        "bypass_metadata": {
            "issue_number": issue_number,
            "bypass_reason": bypass_reason,
            "plan_summary": plan_summary or "Not provided"
        }
    }
    
    # Ensure .claude directory exists
    claude_dir = Path.cwd() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    
    # Write atomically using tempfile + os.replace pattern
    verdict_path = claude_dir / "plan_critic_verdict.json"
    
    with tempfile.NamedTemporaryFile(
        mode='w', 
        dir=claude_dir, 
        delete=False,
        prefix='.plan_critic_verdict_',
        suffix='.tmp'
    ) as tmp:
        json.dump(verdict, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = tmp.name
    
    # Atomic replace
    os.replace(temp_path, verdict_path)


def verify_pipeline_agent_completions(
    session_id: str,
    pipeline_mode: str = "full",
    *,
    issue_number: int = 0,
    run_id: Optional[str] = None,
) -> tuple[bool, set[str], set[str]]:
    """Verify all required agents completed for a pipeline run.

    Reads completed agents from state, determines required agents based on
    pipeline_mode and research_skipped, and returns whether all are present.

    Fail-open: returns (True, set(), set()) on any error to avoid blocking
    legitimate commits due to state file issues.

    Escape hatch (in order of reliability): (1) touch /tmp/skip_agent_completeness_gate
    as a separate command, then retry — file-based, works mid-session;
    (2) export SKIP_AGENT_COMPLETENESS_GATE=1 BEFORE launching claude (env vars
    don't propagate mid-session — Issue #779). (Issue #802)

    **IMPORTANT — Chaining with && WILL NOT WORK**: Run
    ``touch /tmp/skip_agent_completeness_gate`` as a SEPARATE Bash call first,
    then retry ``git commit`` in a second Bash call. The hook intercepts the
    entire compound command before touch executes, so the bypass file is absent
    when the gate checks it. (Issue #1212)

    Args:
        session_id: The pipeline session identifier.
        pipeline_mode: Pipeline mode — "full", "light", "fix", or "tdd-first".
        issue_number: The issue number (0 for non-batch).
        run_id: Optional per-invocation run identifier. When set, the run-id-
            scoped state file is used instead of the legacy sha256 path. (#1041)

    Returns:
        Tuple of (passed, completed_agents, missing_agents).
        passed is True when all required agents have completed.

    Issues: #802
    """
    # Escape hatch: env var (works when set in harness command) or file-based bypass
    # (works from Bash: touch /tmp/skip_agent_completeness_gate)
    if os.environ.get("SKIP_AGENT_COMPLETENESS_GATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return (True, set(), set())

    if _check_file_bypass():
        return (True, set(), set())

    try:
        completed = get_completed_agents(session_id, issue_number=issue_number, run_id=run_id)
        research_skipped = get_research_skipped(session_id, issue_number=issue_number, run_id=run_id)
        plan_critic_skipped = get_plan_critic_skipped(session_id, issue_number=issue_number, run_id=run_id)

        # Import agent_ordering_gate for get_required_agents
        try:
            from agent_ordering_gate import get_required_agents
        except ImportError:
            # Try relative import path
            import importlib.util

            gate_path = Path(__file__).resolve().parent / "agent_ordering_gate.py"
            if gate_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "agent_ordering_gate", str(gate_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    get_required_agents = mod.get_required_agents
                else:
                    return (True, set(), set())  # Fail-open
            else:
                return (True, set(), set())  # Fail-open

        required = get_required_agents(
            pipeline_mode,
            research_skipped=research_skipped,
            plan_critic_skipped=plan_critic_skipped,
        )
        missing = required - completed

        if missing:
            return (False, completed, missing)

        return (True, completed, set())

    except Exception:
        # Fail-open: any error returns pass
        return (True, set(), set())


def clear_session(session_id: str) -> None:
    """Remove the state file for a session.

    Args:
        session_id: The pipeline session identifier.
    """
    path = _state_file_path(session_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Phase 2 (Issue #1146): Sliding-window tier-1 ring buffer
# ---------------------------------------------------------------------------
#
# The classifier emits Tier-1 (`fix`) allows for small individual edits. A
# series of Tier-1 allows to the same file within a short window can sum to
# a Tier-2 (`light`) sized change without any single edit triggering the
# gate ("emergent bypass via tool-call granularity mismatch"). The ring
# buffer records timestamp + lines-added for each recent Tier-1 allow, per
# (session, file). The gate queries it before returning an allow and
# escalates to Tier-2 deny when the cumulative window exceeds the existing
# `TIER_LIGHT_LINE_THRESHOLD` (20 lines).
#
# Design choices (locked in plan + Round 3 plan-critic):
#   - Soft FIFO cap = 10 entries per (session, file). On append we
#     prune-then-cap so the oldest entry drops first.
#   - TTL pruning: entries older than ``window_seconds`` are dropped on
#     every read. The default window is 60 s (matches plan).
#   - No new state file. Buffers nest inside the existing per-session
#     state under key ``"tier1_ring_buffers"`` keyed by file_path. The
#     ring-buffer mutators run under ``_locked_rmw`` (#1170) — an
#     external lockfile guards the read-modify-write sequence so two
#     concurrent writers cannot lose entries via interleaved RMW. The
#     prior reliance on ``_write_state``'s ``fcntl.LOCK_EX`` alone only
#     covered the WRITE half of RMW and was racy. ``clear_session``
#     already unlinks the whole state file — buffers are wiped with
#     the rest.

_TIER1_RING_BUFFER_KEY = "tier1_ring_buffers"
_TIER1_RING_BUFFER_CAP = 10


def _locked_rmw(
    session_id: str,
    mutator,
    *,
    run_id: Optional[str] = None,
) -> None:
    """Read-modify-write the per-session state under an external lockfile.

    The original ring-buffer mutators read state, mutated it in-process,
    then called ``_write_state`` which only took ``fcntl.LOCK_EX`` for
    the write half. Two concurrent callers could each read the same
    pre-mutation state, both mutate, and the later writer would
    silently clobber the earlier writer's append. Symptom: lost
    Tier-1 ring buffer entries under concurrent classifier calls and
    spurious gate misses.

    The fix is a coarse mutex external to the JSON file itself: a
    sibling lockfile at ``/tmp/pipeline_agent_completions_{key}.lock``
    serializes the entire R-M-W. The lockfile is opened in ``"a+"``
    mode so it auto-creates and is never truncated. Failure to acquire
    is fail-open — we proceed with the unlocked path rather than
    block the gate. (#1170)

    Args:
        session_id: The pipeline session identifier (used as the lock
            key when ``run_id`` is unset).
        mutator: Callable ``(state: dict) -> None`` that mutates
            ``state`` in place. Return value is ignored.
        run_id: Optional per-invocation run identifier. When provided,
            the lockfile key matches the state file's per-run key for
            scope parity. Must match ``_RUN_ID_RE`` (``[a-zA-Z0-9_-]{1,64}``);
            ValueError is raised otherwise.

    Issues: #1170, #1188
    """
    if run_id:
        if not _RUN_ID_RE.match(run_id):
            raise ValueError(
                f"run_id contains invalid characters: {run_id!r}\n"
                f"Expected: 1-64 characters matching [a-zA-Z0-9_-]\n"
                f"See: docs/ARCHITECTURE-OVERVIEW.md"
            )
        key = run_id
    else:
        key = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    lock_path = Path(f"/tmp/pipeline_agent_completions_{key}.lock")

    try:
        # "a+" auto-creates the lockfile and never truncates — important
        # because losing the fd here would lose the lock for any other
        # process that's already blocked on it.
        with open(lock_path, "a+") as lock_fh:
            try:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            except OSError:
                # Fail-open: a flock failure is rare (typically NFS) and
                # the gate must keep functioning. Drop straight into the
                # unlocked R-M-W path.
                state = _read_state(session_id, run_id=run_id)
                mutator(state)
                _write_state(session_id, state, run_id=run_id)
                return

            try:
                state = _read_state(session_id, run_id=run_id)
                mutator(state)
                _write_state(session_id, state, run_id=run_id)
            finally:
                # Release even on mutator exception so the lockfile does
                # not stay held — every other concurrent caller would
                # deadlock otherwise.
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        # Lockfile couldn't be opened (permissions, full /tmp). Fall
        # back to the unlocked path — never raise out of state code.
        state = _read_state(session_id, run_id=run_id)
        mutator(state)
        _write_state(session_id, state, run_id=run_id)


def record_tier1_allow(
    session_id: str,
    file_path: str,
    lines_added: int,
    *,
    run_id: Optional[str] = None,
) -> None:
    """Append a Tier-1 allow to the ring buffer for ``(session_id, file_path)``.

    Reuses the existing atomic-write primitive in this module so we benefit
    from the same locking guarantees the rest of the pipeline state has.
    Soft FIFO cap of ``_TIER1_RING_BUFFER_CAP`` entries per file — the
    oldest entry drops when the cap is exceeded.

    Args:
        session_id: The pipeline session identifier.
        file_path: The target file path (used as the per-buffer key).
        lines_added: How many lines this Tier-1 allow added. Must be
            non-negative; negative values are clamped to 0.
        run_id: Optional per-invocation run identifier. Passed through to
            the underlying state read/write so per-run isolation works
            consistently with the rest of this module.

    Issues: #1146
    """
    if not session_id or not file_path:
        return
    lines_added = max(0, int(lines_added))

    def _mutator(state: dict) -> None:
        # _ensure_state behavior inlined for the empty-state path so the
        # locked RMW does not need a second read.
        if not state:
            from datetime import datetime, timezone

            state.update({
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "validation_mode": "sequential",
                "completions": {},
                "prompt_baselines": {},
            })
        buffers = state.setdefault(_TIER1_RING_BUFFER_KEY, {})
        entries = buffers.setdefault(file_path, [])

        entries.append({"ts": time.time(), "lines": lines_added})

        # Soft FIFO drop-oldest cap.
        if len(entries) > _TIER1_RING_BUFFER_CAP:
            del entries[: len(entries) - _TIER1_RING_BUFFER_CAP]

        buffers[file_path] = entries
        state[_TIER1_RING_BUFFER_KEY] = buffers

    _locked_rmw(session_id, _mutator, run_id=run_id)


def get_recent_tier1_allows(
    session_id: str,
    file_path: str,
    *,
    window_seconds: int = 60,
    run_id: Optional[str] = None,
) -> list:
    """Return the ring-buffer entries for ``(session_id, file_path)`` newer than ``window_seconds``.

    Performs read-time pruning: drops entries older than the window from
    the in-memory copy returned to the caller. Does NOT rewrite the state
    file from a pure read — callers that want the pruning to persist
    should call :func:`record_tier1_allow` (which writes) or
    :func:`clear_tier1_ring_buffer`.

    Args:
        session_id: The pipeline session identifier.
        file_path: The file path whose ring buffer to fetch.
        window_seconds: Only return entries whose timestamp is within
            this many seconds of the current wall clock. Default 60.
        run_id: Optional per-invocation run identifier.

    Returns:
        A list of ``{"ts": float, "lines": int}`` dicts sorted oldest
        first. Empty list when the buffer is missing, stale, or the
        session has no recorded allows.

    Issues: #1146
    """
    if not session_id or not file_path:
        return []

    state = _read_state(session_id, run_id=run_id)
    buffers = state.get(_TIER1_RING_BUFFER_KEY, {})
    if not isinstance(buffers, dict):
        return []
    entries = buffers.get(file_path, [])
    if not isinstance(entries, list):
        return []

    cutoff = time.time() - max(0, int(window_seconds))
    fresh = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ts = entry.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        if ts >= cutoff:
            lines = entry.get("lines", 0)
            if not isinstance(lines, (int, float)):
                lines = 0
            fresh.append({"ts": float(ts), "lines": int(lines)})
    return fresh


def clear_tier1_ring_buffer(
    session_id: str,
    file_path: str,
    *,
    run_id: Optional[str] = None,
) -> None:
    """Drop the ring buffer for ``(session_id, file_path)``.

    Called by the classifier after an escalation deny so a single
    threshold trigger does not keep firing on subsequent edits — the
    deny itself is the signal; afterwards the counter resets.

    Args:
        session_id: The pipeline session identifier.
        file_path: The file path whose buffer to clear.
        run_id: Optional per-invocation run identifier.

    Issues: #1146
    """
    if not session_id or not file_path:
        return

    def _mutator(state: dict) -> None:
        if not state:
            return
        buffers = state.get(_TIER1_RING_BUFFER_KEY)
        if not isinstance(buffers, dict):
            return
        if file_path in buffers:
            buffers.pop(file_path, None)
            state[_TIER1_RING_BUFFER_KEY] = buffers

    _locked_rmw(session_id, _mutator, run_id=run_id)


def ensure_sentinel_heartbeat(
    session_id: str,
    state_path: Optional[str] = None,
) -> bool:
    """Verify the pipeline sentinel file is intact; recreate it if missing or mismatched.

    Called after each SubagentStop agent completion to guard against
    ``clear_stale_state`` (in hook_recovery.py) deleting the sentinel when a
    subprocess runs with a different ``CLAUDE_SESSION_ID`` than the one that
    created the file.

    Behaviour:
    - If ``state_path`` exists, is parseable JSON, and its ``session_id``
      field matches ``session_id`` → sentinel is healthy, return ``True``.
    - Otherwise (missing, corrupt, or session_id mismatch) → emit a structured
      log line to stderr, recreate a minimal sentinel, and return ``False``.

    The function NEVER raises.  All failure modes degrade gracefully.

    Args:
        session_id: The expected owner's session id (e.g. from
            ``CLAUDE_SESSION_ID`` or the pipeline state file itself).
        state_path: Absolute path to the sentinel file.  Defaults to the
            ``PIPELINE_STATE_FILE`` env var, falling back to the per-repo
            ``<repo>/.claude/local/implement_pipeline_state.json`` (Issue #1206).

    Returns:
        ``True`` when the sentinel was already healthy.
        ``False`` when the sentinel was absent or mismatched and was recreated.

    Issues: #989, #1206
    """
    if state_path is None:
        state_path = os.environ.get(
            "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
        )

    sentinel = Path(state_path)

    try:
        if sentinel.exists():
            try:
                raw = sentinel.read_text(encoding="utf-8")
                data = json.loads(raw)
            except (OSError, json.JSONDecodeError, ValueError):
                data = None

            if isinstance(data, dict) and data.get("session_id") == session_id:
                return True  # Sentinel healthy.
    except Exception:
        # Defensive: any unexpected error falls through to recreation.
        pass

    # Sentinel is missing, corrupt, or owned by a different session.
    try:
        import sys as _sys_hb

        _sys_hb.stderr.write(
            f"[SENTINEL-HEARTBEAT-MISSING] state_path={state_path}"
            f" recovering_for_session={session_id}\n"
        )
        _sys_hb.stderr.flush()
    except Exception:
        pass

    try:
        recovered_sentinel = {
            "session_id": session_id,
            "recovered": True,
            "recovered_at": datetime.now(timezone.utc).isoformat(),
        }
        sentinel.write_text(
            json.dumps(recovered_sentinel, indent=2), encoding="utf-8"
        )
        try:
            os.chmod(sentinel, 0o600)
        except OSError:
            pass
    except Exception:
        # NEVER raise — sentinel recreation is best-effort.
        pass

    return False


def _gc_stale_states(max_age_seconds: int = 7200) -> dict:
    """Garbage-collect stale state files and orphaned lockfiles in /tmp.

    Deletes files older than ``max_age_seconds``:

    - ``/tmp/pipeline_agent_completions_*.json`` (both legacy sha256 and new
      run_id paths)
    - ``/tmp/implement_pipeline_*.json`` (per-run sentinel files)
    - ``/tmp/pipeline_*.lock`` (orphaned lockfiles)

    Default is 2× the existing ``STALE_UNKNOWN_TTL_SECONDS`` (3600 → 7200).

    Args:
        max_age_seconds: Files with mtime older than this many seconds are
            removed.  Default 7200 (2× TTL).

    Returns:
        A dict with removal counts and any errors encountered::

            {
                'state_files_removed': int,
                'sentinels_removed': int,
                'lockfiles_removed': int,
                'errors': list[str],
            }

    Issues: #1041 #1048
    """
    now = time.time()
    cutoff = now - max_age_seconds

    counts: dict = {
        "state_files_removed": 0,
        "sentinels_removed": 0,
        "lockfiles_removed": 0,
        "errors": [],
    }

    patterns = [
        ("/tmp/pipeline_agent_completions_*.json", "state_files_removed"),
        ("/tmp/implement_pipeline_*.json", "sentinels_removed"),
        # The "pipeline_*.lock" glob also matches the per-session R-M-W
        # lockfiles introduced in #1170
        # (/tmp/pipeline_agent_completions_*.lock), so orphaned R-M-W
        # locks are reaped on the same cadence as state files.
        ("/tmp/pipeline_*.lock", "lockfiles_removed"),
    ]

    for pattern, key in patterns:
        for path in glob.glob(pattern):
            try:
                if os.stat(path).st_mtime < cutoff:
                    os.unlink(path)
                    counts[key] += 1
            except OSError as exc:
                counts["errors"].append(f"{path}: {exc}")

    return counts
