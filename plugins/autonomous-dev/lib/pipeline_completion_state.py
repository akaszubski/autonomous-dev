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
isolation and crash-resume without collision. Callers that omit ``run_id``
continue to use the legacy session-hashed path. (#1041)

Run identity within the legacy session file (#1045)
---------------------------------------------------
Omitting ``run_id`` no longer means "no behavior change" — that claim was true
of #1041 and is now false. Because ALL production writers omit ``run_id``, the
session file was the only file the completeness gate ever read, and it carried
no notion of which RUN produced a completion. A second ``/implement`` run in one
session therefore inherited the authority the first run earned (confused
deputy).

``record_run_start`` now stamps ``state["current_run_id"]`` at STEP 0, every
subsequent completion is stamped into the ``completion_run_ids`` sibling map,
and ``get_completed_agents`` credits only completions belonging to the current
run. A file with neither key behaves exactly as before (permissive) — see
``_filter_to_current_run`` for the full policy table.

Issues: #625, #629, #632, #1041, #1045
"""

import fcntl
import glob
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

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

# Validators whose verbatim output implement.md requires the coordinator to
# persist to ``.claude/logs/activity/validators/<run_id>/<agent>.txt``.
# Recording the completion and writing the artifact are two INDEPENDENTLY
# FORGETTABLE writes by the same party (see _missing_validator_artifacts).
_VALIDATOR_ARTIFACT_AGENTS = ("reviewer", "security-auditor")

# Staleness TTL for the 'unknown' session-id fallback merge.
# When the primary-session lookup in get_completed_agents() falls back to
# reading the 'unknown' state file (for the Issue #738/#777 in-flight boot
# case where the coordinator initialized state before CLAUDE_SESSION_ID was
# known), the merge ONLY applies if the 'unknown' state file's mtime is
# within this window. Older 'unknown' state from crashed/stale prior runs
# must not contaminate a fresh pipeline. Issue #875 / Issue #904.
STALE_UNKNOWN_TTL_SECONDS = 3600


def _is_gate_countable_agent(agent_type: Optional[str]) -> bool:
    """Issue #1436: an agent_type is gate-countable only if it is a real,
    attributable identity. Empty / whitespace-only / "unknown" identities are
    unattributable SubagentStop noise and MUST NOT enter the completeness-gate
    completions set (they can never satisfy a NAMED-agent requirement, and
    storing them pollutes ghost-agent detection).

    Sibling (negated mirror): unified_session_tracker._is_unattributable (#1436).
    Kept independent (not delegated) so the hook stays import-robust."""
    if not agent_type:
        return False
    normalized = str(agent_type).strip().lower()
    return bool(normalized) and normalized != "unknown"


def _sanitize_bypass_reason(bypass_reason: Optional[str]) -> Optional[str]:
    """Sanitize bypass_reason by stripping control chars and truncating.
    
    Strips all control characters except newline and tab, then truncates
    to 2048 characters maximum. Prevents log injection and excessive 
    storage consumption.
    
    Args:
        bypass_reason: Raw bypass reason text, may contain control chars.
        
    Returns:
        Sanitized text or None if input was None.
        
    Issue: #1380
    """
    if bypass_reason is None:
        return None
    # Strip control chars except newline and tab    
    sanitized = ''.join(c for c in bypass_reason if c.isprintable() or c in '\n\t')
    # Truncate to 2048 chars
    return sanitized[:2048]


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


def _missing_validator_artifacts(
    state_run_id: Optional[str],
    completed: set[str],
    required: set[str],
    issue_number: int,
    activity_dir: Optional[Path] = None,
) -> frozenset[str]:
    """Cross-check recorded validator completions against artifacts on disk.

    ``implement.md`` (the "Validator artifact write" block) instructs the
    coordinator to persist reviewer / security-auditor output verbatim to
    ``.claude/logs/activity/validators/<run_id>/<agent>.txt``. That instruction
    is prose, and prose is not enforcement: on 2026-08-29 the write was skipped
    entirely and a reviewer REQUEST_CHANGES finding that had driven a full
    remediation cycle existed only in narration, unverifiable by the CIA.

    The value here is narrow and worth stating honestly. The coordinator writes
    BOTH the completion record and the artifact, so there is **no trust-domain
    separation** — this is not a second principal attesting to the first. What
    it buys is a redundant cross-check against a party that skips its own
    mandated write, because the two writes are *independently forgettable*: the
    completion call fires on agent return, the artifact write happens later,
    after both validators return and their verdicts are parsed.

    **Residual, stated plainly**: a coordinator that skips BOTH the completion
    call and the artifact write is NOT caught here. Skipping the record is not
    free — the pre-existing gate blocks on a missing ``reviewer`` in full/fix
    mode. This removes the only currently-free path through the class; it does
    not close the class.

    **Scope — single-issue runs only.** In batch mode the artifact directory
    name is not derivable from ``current_run_id``: ``implement-batch.md`` binds
    ``ISSUE_RUN_ID`` twice, to two different shapes. The value that NAMES the
    validators directory is ``"${BATCH_ID}-issue${ISSUE_NUMBER}"``, while the
    value that reaches ``record_run_start`` (and so becomes ``current_run_id``)
    is ``"issue-${ISSUE_NUMBER}-$(date ...)"``. A batch-scoped check would look
    in the wrong directory, find nothing, and block a batch run that DID write
    its artifacts. Restricting to ``issue_number == 0`` is a response to that
    verified divergence, not caution.

    Emptiness is judged by **zero bytes only**. No byte-count or line-count
    threshold: the smallest genuine artifact in the real corpus is a 138-byte,
    single-line APPROVE verdict, and a ``>=200 bytes AND >=2 lines`` rule
    misclassified 6 of 19 genuine artifacts. Do not reintroduce a threshold.

    INV-7 (fail closed only when determinate):

    * **Determinable-absent** — identity resolved, activity dir resolved, agent
      present in both *completed* and *required*, file missing or zero-byte:
      emit a sentinel (fail closed).
    * **Indeterminate** — batch scope, no ``current_run_id``, a
      ``current_run_id`` failing ``_RUN_ID_RE``, no activity dir, or any
      ``OSError``: contribute nothing, leaving the verdict byte-identical to
      pre-change behaviour.

    Args:
        state_run_id: ``state["current_run_id"]`` for the run under test.
        completed: Agents credited to the current run.
        required: Agents the pipeline mode demands.
        issue_number: Issue scope; only ``0`` (single-issue) is checked.
        activity_dir: Activity-log root. Resolved via ``_find_activity_log_dir``
            when omitted.

    Returns:
        Sentinels of the form ``"<agent>-artifact:<path>(absent-or-empty)"``,
        one per validator credited as complete but lacking its artifact. Empty
        frozenset whenever the answer is indeterminate. Never raises.
    """
    try:
        # (1) Batch scope — the directory name is not derivable here.
        if issue_number != 0:
            return frozenset()

        # (2) No run identity recorded — indeterminate, not absent.
        if not state_run_id:
            return frozenset()

        # (3) PATH-TRAVERSAL GUARD — do NOT remove as redundant. state_run_id
        # comes from a JSON state file on disk and is interpolated directly
        # into a filesystem path below. Re-validating here mirrors the existing
        # checks in record_run_start / _stamp_current_run_id / the run-id-scoped
        # state path builder. A value like "../../etc" must never be stat'd.
        if not _RUN_ID_RE.match(state_run_id):
            return frozenset()

        # (4) Activity dir unresolvable — indeterminate.
        #
        # Assumes the commit-time process CWD resolves to the same
        # ``.claude/logs/activity/`` tree that implement.md's CWD-relative
        # ``mkdir -p`` wrote into. Holds in this harness's persistent-CWD
        # model; implement.md contains no ``cd`` and worktrees are batch-only,
        # and batch completions are invisible under issue key 0
        # (``get_completed_agents`` keys strictly on ``str(issue_number)`` with
        # no union across keys, so *completed* is empty here during a batch run
        # and this helper emits nothing).
        if activity_dir is None:
            activity_dir = _find_activity_log_dir()
        if activity_dir is None:
            return frozenset()

        sentinels: set[str] = set()
        for agent in _VALIDATOR_ARTIFACT_AGENTS:
            # Only agents this mode actually demands AND that were credited.
            if agent not in completed or agent not in required:
                continue
            path = activity_dir / "validators" / state_run_id / f"{agent}.txt"
            # No file reads: st_size answers emptiness without opening it.
            if not path.is_file() or path.stat().st_size == 0:
                sentinels.add(f"{agent}-artifact:{path}(absent-or-empty)")
        return frozenset(sentinels)
    except Exception:
        # Indeterminate by failure — contribute nothing, never raise. This
        # helper must not be able to turn a passing gate into an error.
        return frozenset()


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


def resolve_session_id_affine(
    *,
    sentinel_path: Optional[str] = None,
    max_age_seconds: int = 3600,
) -> Optional[str]:
    """Resolve the current session id using ONLY session-affine sources.

    Unlike :func:`resolve_session_id`, this resolver NEVER falls through to the
    repo-wide activity-log scan (``_resolve_session_id_from_activity_log``).
    That scan returns "today's most-recent real session id" with NO cwd / PID /
    temporal scoping and can therefore return a *different concurrent session's*
    id. In this repo, concurrent Claude Code sessions are a documented regular
    occurrence, so trusting the broad scan in a security gate is unsafe: a second
    idle session's completions could satisfy THIS session's git-commit
    completeness gate (concurrent-session collision, Issue #1228 hardening).

    Affinity sources, first match wins:

        1. ``CLAUDE_SESSION_ID`` env var — THE current session, highest
           affinity. (When set to the literal ``"unknown"`` it is ignored,
           matching :func:`resolve_session_id` step-2 semantics.)
        2. The STEP-0 sentinel file's ``session_id`` — a fresh, current-pipeline
           marker written by the coordinator at STEP 0. Gated by
           ``mtime <= max_age_seconds`` so a STALE sentinel from a prior/abandoned
           run is ignored (temporal affinity). A ``"unknown"`` placeholder is
           ignored.

    Returns the resolved real session id, or ``None`` when neither affine source
    yields a real (non-empty, non-``"unknown"``) id. Returning ``None`` (rather
    than the broad activity-log scan's cross-session guess) lets the gate FAIL
    SAFE toward "run the agents" instead of masking an incomplete pipeline with
    an unrelated session's completions.

    This preserves the legitimate Bash-subprocess-drops-``CLAUDE_SESSION_ID``
    recovery case: the coordinator writes the sentinel with the REAL session id
    at STEP 0, so the sentinel (step 2) still resolves it after the env var is
    lost in a subshell. Only the ambiguous "env dropped AND sentinel is
    'unknown'" case — which is precisely the concurrent-collision hole — is no
    longer rescued via the broad scan.

    NEVER raises. Catches ``OSError``, ``json.JSONDecodeError``, ``ValueError``.

    Issue #1228 (concurrent-session hardening).
    """
    try:
        env_sid = os.environ.get("CLAUDE_SESSION_ID", "")
        if env_sid and env_sid != "unknown":
            return env_sid

        if sentinel_path is None:
            sentinel_path = str(get_legacy_sentinel_path())

        try:
            st = os.stat(sentinel_path)
        except OSError:
            return None
        if (time.time() - st.st_mtime) > max_age_seconds:
            # Stale sentinel — not the current session. Ignore (temporal affinity).
            return None
        try:
            with open(sentinel_path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        if isinstance(data, dict):
            candidate = data.get("session_id")
            if isinstance(candidate, str) and candidate and candidate != "unknown":
                return candidate
        return None
    except Exception:
        # Fail-safe: never let the affine resolver raise into the gate.
        return None


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


# Issue #1544: a parse failure is NOT the same thing as "file absent".
# ``_read_state`` used to collapse both onto ``{}``, and ``_ensure_state``
# reads ``{}`` as "no file yet" and rebuilds a blank skeleton — so one
# transient unreadable read silently discarded every recorded completion.
# We now retry briefly (the truncation window a concurrent writer could open
# is sub-millisecond) and, if the file is still unreadable, report LOUDLY on
# stderr instead of pretending the session never happened.
#
# Deliberately NOT raising: every caller here also gates reads, and a hard
# failure would block the pipeline rather than degrade it. Loud + degraded is
# the correct trade; silent + degraded is the bug.
_READ_RETRY_ATTEMPTS = 3
_READ_RETRY_DELAY_SECONDS = 0.01


def _report_unreadable_state(path: Path, detail: str) -> None:
    """Report an unreadable (but present) state file on stderr.

    Args:
        path: The state file that could not be parsed.
        detail: Short description of the failure (exception text).

    Issues: #1544
    """
    try:
        print(
            f"[pipeline_completion_state] WARNING: state file is present but "
            f"unreadable: {path}\n"
            f"  Cause: {detail}\n"
            f"  Effect: treated as EMPTY for this read — recorded agent "
            f"completions may be rebuilt as a blank skeleton.\n"
            f"  See: plugins/autonomous-dev/docs/TROUBLESHOOTING.md (Issue #1544)",
            file=sys.stderr,
        )
    except Exception:  # pragma: no cover - stderr itself is broken
        pass


def _read_state(session_id: str, *, run_id: Optional[str] = None) -> dict:
    """Read state file with file locking. Returns empty dict on any failure.

    A missing file returns ``{}`` silently — that is normal first-run behavior.
    A file that exists but cannot be parsed is retried
    ``_READ_RETRY_ATTEMPTS`` times and then reported on stderr before ``{}``
    is returned, so a transient truncated read can no longer masquerade as
    "no state" without leaving a trace. (#1544)

    Args:
        session_id: The pipeline session identifier.
        run_id: Optional per-invocation run identifier passed to
            ``_state_file_path``. (#1041)

    Returns:
        Parsed state dict, or empty dict if file missing/corrupt/stale.

    Issues: #1041, #1413, #1544
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

    last_error: Optional[str] = None
    for attempt in range(_READ_RETRY_ATTEMPTS):
        try:
            with open(path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, ValueError) as exc:
            # File exists but did not parse. Under the pre-#1544 writer this
            # was the truncate-before-lock window; under the atomic writer it
            # should be impossible. Retry, then shout.
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < _READ_RETRY_ATTEMPTS - 1:
                time.sleep(_READ_RETRY_DELAY_SECONDS)
                if not path.exists():
                    return {}  # concurrently cleared — genuinely absent now
                continue
            _report_unreadable_state(path, last_error)
            return {}
        except OSError as exc:
            # Unreadable for filesystem reasons (permissions, ENOENT race).
            # Absence is normal; anything else is worth reporting.
            if not path.exists():
                return {}
            _report_unreadable_state(path, f"{type(exc).__name__}: {exc}")
            return {}

        if not isinstance(data, dict):
            _report_unreadable_state(
                path, f"expected a JSON object, got {type(data).__name__}"
            )
            return {}
        # Issue #1413: refresh mtime on successful read so an active session
        # that keeps reading its state file never crosses the 7200s staleness
        # threshold and self-wipes mid-pipeline. Crash-recovery semantics are
        # preserved: a truly abandoned file still ages past the threshold.
        try:
            path.touch()
        except OSError:
            pass  # mtime refresh is best-effort; do not fail the read
        return data

    return {}  # pragma: no cover - loop always returns


# Issue #1544: re-entrancy guard for the raw on-disk write.
#
# ``_write_state`` used to be called directly by eight mutators, each of which
# did an UNSERIALIZED read-modify-write. Now the raw write is only performed
# while this guard is held, and the guard is only taken inside ``_locked_rmw``.
# A ``_write_state`` call made from anywhere else transparently self-wraps in
# ``_locked_rmw`` (see below) rather than being rejected, so a ninth bypass
# caller cannot reintroduce the race by construction — it gets serialized
# whether or not its author knew about the lock.
#
# Thread-local (not a plain module global) so concurrent threads in one process
# cannot see each other's guard state.
_RMW_GUARD = threading.local()


def _in_locked_rmw() -> bool:
    """Return True when the caller is executing inside :func:`_locked_rmw`."""
    return getattr(_RMW_GUARD, "depth", 0) > 0


def _atomic_write_state(path: Path, state: dict) -> None:
    """Serialize *state* to *path* atomically via a temp file + ``os.replace``.

    Defence in depth for the truncate-before-lock defect (#1544). The previous
    implementation used ``open(path, "w")``, which truncates the target to 0
    bytes BEFORE ``fcntl.LOCK_EX`` is acquired; any concurrent reader landing
    in that window read an empty file. Writing to a sibling temp file in the
    same directory and then calling ``os.replace`` makes the swap atomic on
    POSIX: a concurrent reader sees either the complete old file or the
    complete new one, never a truncated one.

    This is what makes ``_locked_rmw``'s deliberate fail-open behaviour SAFE
    rather than merely rarer — on a flock failure the RMW is still unserialized
    (last writer wins), but no reader can ever observe a half-written file.

    The temp file is created by ``tempfile.mkstemp`` (mode 0o600 by default)
    and explicitly chmod'd to ``0o600`` before the rename, preserving #1169:
    the state file carries session-scoped HMAC and completion data and must
    never be world-readable, not even for the duration of the write. chmod
    failure is non-fatal — it can legitimately fail on filesystems without
    POSIX modes.

    Args:
        path: Target state file path.
        state: The state dict to serialize.

    Raises:
        OSError: If the temp file cannot be created, written, or renamed.
            The caller (:func:`_write_state`) swallows this — a state write
            failure must not be fatal to the pipeline.

    Issues: #1169, #1544
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f"{path.name}.", suffix=".tmp"
    )
    try:
        # #1169: tighten permissions on the staging file so the post-rename
        # target is 0o600 the instant it becomes visible. mkstemp already
        # creates at 0o600; this is belt-and-braces for exotic umask/FS setups.
        try:
            os.chmod(tmp_name, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w") as f:
            fd = -1  # ownership transferred to the file object
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_state(session_id: str, state: dict, *, run_id: Optional[str] = None) -> None:
    """Write the state file atomically, always under the RMW lock.

    Two behaviours, selected by whether the caller is already inside
    :func:`_locked_rmw`:

    - **Inside** ``_locked_rmw``: perform the atomic write directly. The whole
      read-modify-write is already serialized by the sibling lockfile.
    - **Outside** ``_locked_rmw``: self-wrap in ``_locked_rmw`` with a
      replace-all mutator. Observable behaviour is identical (the supplied
      ``state`` becomes the file's contents) but the write is now serialized
      against concurrent mutators.

    The self-wrap is what makes the fix durable: the raw truncating write is
    unreachable, so a future caller that reaches for ``_write_state`` gets the
    lock for free instead of quietly reopening the #1544 race. The only direct
    caller of :func:`_atomic_write_state` is this function.

    Args:
        session_id: The pipeline session identifier.
        state: The state dict to write.
        run_id: Optional per-invocation run identifier passed to
            ``_state_file_path``. (#1041)

    Raises:
        ValueError: If ``run_id`` is non-empty and fails ``_RUN_ID_RE``. This
            is pre-existing behaviour — ``_state_file_path`` already raised
            for the same inputs.

    Issues: #1041, #1169, #1544
    """
    if not _in_locked_rmw():
        # Not serialized yet — route through the lock. Replace-all preserves
        # the historical "these are the file's new contents" semantics.
        def _replace_all(existing: dict) -> None:
            existing.clear()
            existing.update(state)

        _locked_rmw(session_id, _replace_all, run_id=run_id)
        return

    path = _state_file_path(session_id, run_id=run_id)
    try:
        _atomic_write_state(path, state)
    except OSError:
        pass  # Non-blocking: state write failure is not fatal


def _new_state_skeleton(session_id: str) -> dict:
    """Return a fresh, empty state skeleton for *session_id*."""
    return {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "validation_mode": "sequential",
        "completions": {},
        "prompt_baselines": {},
    }


def _ensure_state_inplace(state: dict, session_id: str) -> dict:
    """Populate *state* with a fresh skeleton if it is empty, in place.

    The in-place variant of :func:`_ensure_state`, for use inside a
    :func:`_locked_rmw` mutator where the state dict has already been read
    under the lock and must not be re-read (a second read would reopen the
    read-modify-write window the lock exists to close).

    Args:
        state: The state dict supplied by ``_locked_rmw``. Mutated in place.
        session_id: The pipeline session identifier.

    Returns:
        The same dict object, for convenience.

    Issues: #1544
    """
    if not state:
        state.update(_new_state_skeleton(session_id))
    return state


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
        state = _new_state_skeleton(session_id)
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
    # Issue #1436: fail-closed — never store an unattributable identity.
    if not _is_gate_countable_agent(agent_type):
        return

    # Build the completion entry (plain bool or remediation dict).
    if is_remediation:
        entry = {
            "success": bool(success),
            "remediation": True,
        }
    else:
        entry = success  # type: ignore[assignment]  # plain bool, legacy shape

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
        completions = state.setdefault("completions", {})

        if _single_scope:
            # Opt-out path: write only to str(issue_number).
            issue_completions = completions.setdefault(str(issue_number), {})
            issue_completions[agent_type] = entry
            _time_scope_keys = {str(issue_number)}
        else:
            # Tri-scope write: write to the primary key, "0", and "unscoped".
            # Determine the set of scope keys to write to.
            scope_keys: set[str] = {"0", "unscoped"}
            if issue_number != 0:
                scope_keys.add(str(issue_number))
            for key in scope_keys:
                issue_completions = completions.setdefault(key, {})
                issue_completions[agent_type] = entry
            _time_scope_keys = scope_keys

        _record_completion_times(state, _time_scope_keys, agent_type)
        _record_completion_run_ids(state, _time_scope_keys, agent_type)

    _locked_rmw(session_id, _mutator, run_id=run_id)


def _record_completion_times(
    state: dict, scope_keys: set[str], agent_type: str
) -> None:
    """Stamp ``completion_times[scope][agent_type]`` with the current time.

    Issue #1454: record WHEN each agent completed.

    The plan-critic REVISE gate needs to know whether the planner ran AFTER a
    given verdict epoch, but completion entries carry no timestamp -- they are
    a bare bool (or a remediation dict), so get_planner_completion_count()
    could never return non-zero and the gate's allow-branch was dead code. An
    honest REVISE verdict therefore deadlocked the pipeline, and #1457 records
    that both available escapes were dishonest.

    This is a SIBLING map rather than a field inside the completion entry, on
    purpose: the readers below iterate ``issue_completions.items()`` treating
    every key as an agent name, so a nested key would be mistaken for an
    agent, and changing bool -> dict would touch every _completion_is_success
    consumer across ~10 modules. A new top-level key is invisible to all of
    them.

    Args:
        state: The state dict being mutated inside a ``_locked_rmw`` mutator.
        scope_keys: The scope keys that received this completion.
        agent_type: The agent that completed.

    Issues: #1454, #1544
    """
    completion_times = state.setdefault("completion_times", {})
    now = time.time()
    for key in scope_keys:
        completion_times.setdefault(key, {})[agent_type] = now


def _record_completion_run_ids(
    state: dict, scope_keys: set[str], agent_type: str
) -> None:
    """Stamp ``completion_run_ids[scope][agent_type]`` with the current run id.

    Issue #1045 follow-up (confused-deputy): the completeness gate keyed
    completions by SESSION, not by RUN. A second ``/implement`` run inside the
    same session therefore inherited the authority the first run earned — the
    gate read "all five agents completed" for a run in which zero agents had
    executed. Stamping each completion with the run that produced it is what
    lets :func:`_filter_to_current_run` tell "this run" from "a prior run".

    This is a SIBLING map for exactly the reason given in
    :func:`_record_completion_times` — the completion readers iterate
    ``issue_completions.items()`` treating every key as an agent name, so a
    nested key inside the entry would be mistaken for an agent.

    **If ``state["current_run_id"]`` is falsy this writes NOTHING.** That is
    load-bearing, not an optimisation: it is what makes the presence of stamps
    alongside an absent ``current_run_id`` a corruption-only signal (policy
    state (a2)). A pre-migration state file, or any non-``/implement`` session
    that never called :func:`record_run_start`, has no stamps at all and lands
    in the permissive state (a1) instead.

    Args:
        state: The state dict being mutated inside a ``_locked_rmw`` mutator.
        scope_keys: The scope keys that received this completion.
        agent_type: The agent that completed.

    Issues: #1045, #1454
    """
    run_id = state.get("current_run_id")
    if not run_id:
        # No run identity for this session — do not stamp. See docstring.
        return
    completion_run_ids = state.setdefault("completion_run_ids", {})
    for key in scope_keys:
        completion_run_ids.setdefault(key, {})[agent_type] = run_id


def _report_run_start_failure(session_id: str, run_id: str, detail: str) -> None:
    """Report a failed :func:`record_run_start` on stderr.

    Modelled on :func:`_report_unreadable_state`: loud, degraded, non-raising.
    A failure here means completions for this run will be written WITHOUT a run
    stamp, so the gate falls back to today's permissive session-scoped
    behaviour (policy state (a1)) rather than blocking the pipeline.

    Args:
        session_id: The pipeline session identifier.
        run_id: The run identifier that could not be recorded.
        detail: Short description of the failure (exception text).

    Issues: #1045
    """
    try:
        print(
            f"[pipeline_completion_state] WARNING: failed to record run start "
            f"for run_id={run_id!r} (session={session_id!r})\n"
            f"  Cause: {detail}\n"
            f"  Effect: agent completions for this run will NOT be stamped with "
            f"a run id, so the agent-completeness gate degrades to session-"
            f"scoped (pre-#1045) behavior and may credit a prior run's agents.\n"
            f"  See: plugins/autonomous-dev/docs/TROUBLESHOOTING.md",
            file=sys.stderr,
        )
    except Exception:  # pragma: no cover - stderr itself is broken
        pass


def record_run_start(
    session_id: str,
    run_id: str,
    *,
    issue_number: Optional[int] = None,
    _run_id_for_path: Optional[str] = None,
) -> bool:
    """Stamp ``state["current_run_id"]`` for *session_id*.

    Called once per ``/implement`` invocation at STEP 0, BEFORE any agent runs.
    Every subsequent :func:`record_agent_completion` for this session is then
    stamped with *run_id*, and :func:`get_completed_agents` credits only the
    completions belonging to the current run.

    When *issue_number* is supplied the run additionally claims OWNERSHIP of
    that issue scope, in ``state["issue_run_starts"][str(issue_number)]``. That
    is what the batch aggregate gates read; see :func:`_filter_to_owning_run`
    for why they cannot use ``current_run_id``.

    Idempotent: calling twice with the same *run_id* (the ``--resume`` case)
    leaves the state unchanged and returns ``True``.

    **Never raises.** State code must not be able to block the gate, so any
    failure is reported loudly on stderr and reported as ``False`` to the
    caller. The resulting degraded behaviour is the pre-#1045 permissive
    session-scoped gate, not a deadlock.

    Args:
        session_id: The pipeline session identifier.
        run_id: The per-invocation run identifier. Must match
            ``[a-zA-Z0-9_-]{1,64}`` — the same regex :func:`_state_file_path`
            enforces.
        issue_number: The issue this run is processing, when there is one.
            ``None`` (the default, and every non-batch caller) records no
            ownership, leaving the batch gates at their pre-change permissive
            behaviour for that scope.
        _run_id_for_path: Test/advanced hook — the run id used to CHOOSE the
            state file. Defaults to ``None`` (the legacy session-hashed path,
            which is the only shape production uses). This is deliberately
            separate from *run_id*, which is the value STAMPED INTO the file.

    Returns:
        ``True`` when ``current_run_id`` was written (or already matched),
        ``False`` on invalid input or any write failure.

    Issues: #1045
    """
    try:
        if not run_id or not _RUN_ID_RE.match(run_id):
            _report_run_start_failure(
                session_id,
                str(run_id),
                "run_id must match [a-zA-Z0-9_-]{1,64}",
            )
            return False

        def _mutator(state: dict) -> None:
            _ensure_state_inplace(state, session_id)
            # Idempotent by construction: writing the same value twice is a
            # no-op, so --resume re-entering STEP 0 costs nothing.
            state["current_run_id"] = run_id
            if issue_number is not None:
                # Claim ownership of this issue scope. Last writer wins: a
                # retry of issue N supersedes the run that handled it before.
                owners = state.setdefault("issue_run_starts", {})
                owners[str(issue_number)] = run_id

        _locked_rmw(session_id, _mutator, run_id=_run_id_for_path)
        return True
    except Exception as exc:  # noqa: BLE001 - never raise out of state code
        _report_run_start_failure(session_id, str(run_id), f"{type(exc).__name__}: {exc}")
        return False


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


def _report_lost_run_id(issue_key: str, agent_count: int) -> None:
    """Report policy state (a2) — run stamps present, ``current_run_id`` gone.

    Args:
        issue_key: The scope key whose completions are being excluded.
        agent_count: How many completions are being excluded.

    Issues: #1045
    """
    try:
        print(
            f"[pipeline_completion_state] REFUSING: state file carries agent run "
            f"stamps but has NO current_run_id (scope {issue_key!r}, "
            f"{agent_count} completion(s) excluded).\n"
            f"  Cause: the run id written at /implement STEP 0 was LOST. A stamp "
            f"is only ever written while current_run_id is set, so this "
            f"combination cannot arise from normal operation.\n"
            f"  Effect: NO agent completion is credited — the agent-completeness "
            f"gate will refuse, rather than credit records to an unknown run.\n"
            f"  Recovery: re-run /implement STEP 0, or bypass deliberately with "
            f"SKIP_AGENT_COMPLETENESS_GATE (touch "
            f"/tmp/skip_agent_completeness_gate as a SEPARATE Bash call, then "
            f"retry). Every bypass is audited.\n"
            f"  See: plugins/autonomous-dev/docs/TROUBLESHOOTING.md",
            file=sys.stderr,
        )
    except Exception:  # pragma: no cover - stderr itself is broken
        pass


def _filter_to_current_run(state: dict, issue_key: str, agents: set[str]) -> set[str]:
    """Restrict *agents* to those recorded during ``state["current_run_id"]``.

    Fixes a confused-deputy defect: completions were keyed by SESSION, so a
    second ``/implement`` run inside one session inherited the authority the
    first run earned — the completeness gate read "satisfied" for a run in
    which zero agents had executed.

    *state* is the dict the agents were read FROM, not a global. The
    ``'unknown'``-session merge in :func:`get_completed_agents` therefore gets
    filtered by the ``'unknown'`` file's own run identity, not the primary
    session's.

    Policy:

    ===== ================================================= ==================
    State  Condition                                         Behaviour
    ===== ================================================= ==================
    (a1)   no ``current_run_id``, no ``completion_run_ids``  pass through
    (a2)   no ``current_run_id``, stamps present            exclude all, loud
    (b)    ``current_run_id`` set, record unstamped         excluded
    (c)    ``current_run_id`` set, stamp != current         excluded
    (d)    stamp == current                                 included
    ===== ================================================= ==================

    (a1) is the pre-migration state file AND every non-``/implement`` session —
    including the ``unified_session_tracker`` SubagentStop path, which fires for
    ANY subagent and never calls :func:`record_run_start`. It must stay
    permissive and SILENT or the warning fires on ordinary sessions.

    (a2) is unreachable through the public API: :func:`_record_completion_run_ids`
    only stamps while ``current_run_id`` is set, so stamps-without-current means
    the run id was LOST. Crediting those records would credit an unknown run, so
    we refuse — recoverably, via the documented audited bypasses.

    Args:
        state: The state dict *agents* was derived from.
        issue_key: The completions scope key (``str(issue_number)``).
        agents: Candidate agent names, already filtered for success and
            gate-countability by the caller.

    Returns:
        The subset of *agents* attributable to the current run.

    Issues: #1045
    """
    current_run_id = state.get("current_run_id")
    stamp_map = state.get("completion_run_ids")
    if not isinstance(stamp_map, dict):
        stamp_map = {}

    if not current_run_id:
        if stamp_map:
            # (a2) — corruption-only signal. Report ONCE per call.
            _report_lost_run_id(issue_key, len(agents))
            return set()
        # (a1) — pre-migration file or non-pipeline session. Today's behaviour.
        return agents

    # (b) unstamped and (c) stamped-for-another-run both fall out here.
    return _agents_stamped_with(state, issue_key, agents, current_run_id)


def _agents_stamped_with(
    state: dict, issue_key: str, agents: set[str], run_id: str
) -> set[str]:
    """Return the members of *agents* stamped with *run_id* under *issue_key*.

    The single place the ``completion_run_ids`` sibling map is intersected with
    a candidate agent set. Both scoping rules — :func:`_filter_to_current_run`
    (session-wide, keyed on ``current_run_id``) and
    :func:`_filter_to_owning_run` (per-issue, keyed on ``issue_run_starts``) —
    differ only in WHICH run id is authoritative, never in how the match is
    made, so the match lives here once.

    Args:
        state: The state dict *agents* was derived from.
        issue_key: The completions scope key (``str(issue_number)``).
        agents: Candidate agent names.
        run_id: The run id an agent must be stamped with to be credited.

    Returns:
        The subset of *agents* stamped with *run_id*.

    Issues: #1045
    """
    stamp_map = state.get("completion_run_ids")
    if not isinstance(stamp_map, dict):
        stamp_map = {}
    scope_stamps = stamp_map.get(issue_key)
    if not isinstance(scope_stamps, dict):
        scope_stamps = {}
    return {a for a in agents if scope_stamps.get(a) == run_id}


def _report_superseded_scope(issue_key: str, owning_run_id: str, excluded: set[str]) -> None:
    """Report that an issue scope's completions belong to a superseded run.

    Without this the batch gate's refusal is actively misleading: it reports
    "doc-master never ran for #N" for an issue whose doc-master DID run — in a
    run that a later run for the same issue superseded.

    Args:
        issue_key: The issue scope whose completions were excluded.
        owning_run_id: The run that most recently started work on the scope.
        excluded: The agent names that were dropped.

    Issues: #1045
    """
    try:
        print(
            f"[pipeline_completion_state] EXCLUDING issue scope {issue_key!r}: "
            f"{len(excluded)} completion(s) belong to a SUPERSEDED run "
            f"({', '.join(sorted(excluded))}).\n"
            f"  Cause: run {owning_run_id!r} most recently started work on issue "
            f"{issue_key}, but these completions were recorded by an earlier run. "
            f"A later run for the same issue supersedes the earlier one — "
            f"crediting it would let a retry that executed nothing inherit the "
            f"authority the first attempt earned.\n"
            f"  Effect: the batch commit gate reports issue {issue_key} as "
            f"incomplete. This is NOT 'the agent never ran'.\n"
            f"  Recovery: re-run the named agent(s) for issue {issue_key}, or "
            f"bypass deliberately with SKIP_BATCH_CIA_GATE / "
            f"SKIP_BATCH_DOC_MASTER_GATE.\n"
            f"  See: plugins/autonomous-dev/docs/TROUBLESHOOTING.md",
            file=sys.stderr,
        )
    except Exception:  # pragma: no cover - stderr itself is broken
        pass


def _filter_to_owning_run(state: dict, issue_key: str, agents: set[str]) -> set[str]:
    """Restrict *agents* to those recorded by the run that OWNS *issue_key*.

    The scoping rule for the BATCH AGGREGATE gates
    (:func:`verify_batch_cia_completions`,
    :func:`verify_batch_doc_master_completions`). They read
    ``state["completions"]`` directly, never through
    :func:`get_completed_agents`, so the first pass of #1045 left them at the
    pre-fix session-scoped shape and a batch retry inherited a prior run's
    completions.

    **These gates cannot use ``current_run_id``.** Batch mode creates ONE RUN
    PER ISSUE inside ONE session (``implement-batch.md`` sets a fresh
    ``ISSUE_RUN_ID`` per issue), so ``current_run_id`` is overwritten by each
    issue in turn and is the LAST issue's id by the time the batch commits.
    Filtering every scope to it would drop every earlier issue of a perfectly
    healthy batch and refuse the commit — measured: a clean 3-issue batch loses
    issues 1 and 2. The authority for a per-issue aggregate is instead the run
    that most recently STARTED work on that issue.

    Policy:

    ===== ================================================== ==================
    State  Condition                                          Behaviour
    ===== ================================================== ==================
    (o0)   no ``issue_run_starts`` entry for the scope        pass through
    (o1)   owner set, agent stamped with owner                credited
    (o2)   owner set, agent stamped with a superseded run     excluded, loud
    (o3)   owner set, agent unstamped                         excluded
    ===== ================================================== ==================

    (o0) is the pre-migration state file AND every caller that does not pass
    ``issue_number`` to :func:`record_run_start`. It must stay permissive: a
    stale deployment of ``implement-batch.md`` records no ownership, and
    refusing there would block every batch commit rather than degrade to the
    pre-change behaviour.

    Args:
        state: The state dict *agents* was derived from.
        issue_key: The completions scope key (``str(issue_number)``).
        agents: Candidate agent names, already filtered for success by the
            caller.

    Returns:
        The subset of *agents* attributable to the owning run.

    Issues: #1045
    """
    owners = state.get("issue_run_starts")
    if not isinstance(owners, dict):
        return agents
    owning_run_id = owners.get(issue_key)
    if not owning_run_id:
        # (o0) — no run has claimed this scope. Pre-change behaviour.
        return agents

    credited = _agents_stamped_with(state, issue_key, agents, owning_run_id)
    excluded = agents - credited
    if excluded:
        # (o2)/(o3) — say WHY, so the refusal is not read as "never ran".
        _report_superseded_scope(issue_key, owning_run_id, excluded)
    return credited


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
            # #1045: composed with (never replacing) the success and
            # gate-countability filters — an agent must satisfy all three.
            result = _filter_to_current_run(
                state,
                issue_key,
                {
                    k for k, v in issue_completions.items()
                    if _completion_is_success(v) and _is_gate_countable_agent(k)
                },
            )

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
                # #1045: filtered by the 'unknown' FILE'S OWN run identity —
                # fallback_state, not state. The two files are independent; the
                # primary session's run id says nothing about which run wrote
                # the bootstrap records.
                fallback_result = _filter_to_current_run(
                    fallback_state,
                    issue_key,
                    {
                        k for k, v in issue_completions.items()
                        if _completion_is_success(v) and _is_gate_countable_agent(k)
                    },
                )
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
def get_planner_completion_count(session_id: str, since_timestamp: float) -> int:
    """Count planner completions after a given epoch timestamp.
    
    Issue #1417: Used to verify planner was re-invoked after plan-critic REVISE verdict.
    
    Args:
        session_id: The session ID to check
        since_timestamp: Epoch timestamp to count completions after
    
    Returns:
        Number of planner completions after the timestamp
    """
    try:
        import time
        
        # Read completion state file
        state = _read_state(session_id)
        if not state:
            # Try 'unknown' session fallback with TTL check
            if session_id != "unknown":
                unknown_path = _state_file_path("unknown")
                if unknown_path.exists():
                    try:
                        mtime = unknown_path.stat().st_mtime
                        if time.time() - mtime <= STALE_UNKNOWN_TTL_SECONDS:
                            state = _read_state("unknown")
                    except OSError:
                        pass
            
            if not state:
                return 0
        
        # Issue #1454: prefer the completion_times sibling map, which the real
        # writer populates. The legacy walk below is retained unchanged so state
        # files written before this fix still parse.
        #
        # Tri-scope writes record the same completion under "0", "unscoped" and
        # the issue key, so counting raw entries would inflate one planner run
        # into three. Deduplicate on the timestamp itself.
        _times = state.get("completion_times", {})
        if isinstance(_times, dict):
            _seen: set = set()
            for _issue_key, _agents in _times.items():
                if not isinstance(_agents, dict):
                    continue
                _ts = _agents.get("planner")
                if isinstance(_ts, (int, float)) and _ts > since_timestamp:
                    _seen.add(round(float(_ts), 6))
            if _seen:
                return len(_seen)

        # Count planner completions after timestamp across all issue keys
        count = 0
        completions = state.get("completions", {})
        
        # Check all issue scopes (tri-scope pattern)
        for issue_key in completions:
            issue_completions = completions[issue_key]
            if not isinstance(issue_completions, dict):
                continue
            
            completed = issue_completions.get("completed", {})
            if "planner" not in completed:
                continue
            
            # Check completion timestamp
            planner_data = completed["planner"]
            if isinstance(planner_data, dict):
                comp_timestamp = planner_data.get("timestamp")
                if comp_timestamp and comp_timestamp > since_timestamp:
                    count += 1
            # Legacy bool format has no timestamp, skip
        
        return count
    except Exception:
        return 0  # Fail open




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

    Issues: #686, #1544
    """

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
        launches = state.setdefault("launches", {})
        issue_key = str(issue_number)
        issue_launches = launches.setdefault(issue_key, {})
        issue_launches[agent_type] = True

    _locked_rmw(session_id, _mutator)


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

    Issues: #1544
    """

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
        baselines = state.setdefault("prompt_baselines", {})
        baselines[agent_type] = word_count

    _locked_rmw(session_id, _mutator)


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

    Issues: #1214, #1544
    """

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
        state["validation_mode"] = mode

    _locked_rmw(session_id, _mutator, run_id=run_id)


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


def _credited_agents_for_scope(
    state: dict, issue_key: str, issue_completions: dict
) -> set[str]:
    """Agents creditable for *issue_key*: successful AND owned by this run.

    The single read-side rule for the batch aggregate gates. Mirrors the
    composition in :func:`get_completed_agents` — the success filter and the
    run filter are ANDed, neither replaces the other — but scopes to the
    OWNING run rather than ``current_run_id``, for the reason set out in
    :func:`_filter_to_owning_run`.

    Non-agent keys stored alongside completions (``doc-master-verdict`` holds a
    plain string) are dropped by :func:`_completion_is_success`, which treats
    any non-``bool``/non-``dict`` entry as unsuccessful.

    Args:
        state: The state dict *issue_completions* was read from.
        issue_key: The completions scope key (``str(issue_number)``).
        issue_completions: The per-issue completions mapping.

    Returns:
        The agent names creditable for this scope.

    Issues: #1045
    """
    candidates = {
        agent for agent, entry in issue_completions.items()
        if _completion_is_success(entry)
    }
    if not candidates:
        # Nothing to filter. Skipping the call avoids a spurious "0 completions
        # excluded" report; the filtered result would be empty either way.
        return candidates
    return _filter_to_owning_run(state, issue_key, candidates)


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

            # #1045: credit only completions attributable to the run that owns
            # this issue scope. Composed with (never replacing) the existing
            # success filter, exactly as get_completed_agents composes.
            credited = _credited_agents_for_scope(state, issue_key, issue_completions)

            if "continuous-improvement-analyst" in credited:
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

    Issues: #837, #1544
    """

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
        completions = state.setdefault("completions", {})
        issue_key = str(issue_number)
        issue_completions = completions.setdefault(issue_key, {})
        issue_completions["doc-master-verdict"] = verdict

    _locked_rmw(session_id, _mutator)


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

            # #1045: credit only completions attributable to the run that owns
            # this issue scope. The VERDICT below is deliberately still read
            # raw: it is not an agent completion, carries no run stamp, and is
            # only ever consulted once doc-master itself passed this filter.
            # Filtering it would turn an invalid verdict into the
            # backward-compatible "no verdict recorded" branch and WEAKEN the
            # gate.
            credited = _credited_agents_for_scope(state, issue_key, issue_completions)

            if "doc-master" in credited:
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

    Issues: #802, #1213, #1544
    """

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
        research_skipped = state.setdefault("research_skipped", {})
        issue_key = str(issue_number)
        research_skipped[issue_key] = True
        # #1213: Also write to the "0" fallback scope so the commit-time gate
        # (which calls verify_pipeline_agent_completions with issue_number=0)
        # can see the marker. No-op when issue_number is already 0.
        if issue_number != 0:
            research_skipped["0"] = True

    _locked_rmw(session_id, _mutator, run_id=run_id)


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

    Issues: #878, #1213, #1218, #1279, #1325, #1544
    """
    # #1279 / #1380: sanitize before the mutator so the closure captures the
    # cleaned value (the mutator may run inside a retry/fallback path).
    if bypass_reason:
        bypass_reason = _sanitize_bypass_reason(bypass_reason)

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
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

    _locked_rmw(session_id, _mutator, run_id=run_id)

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

    Issues: #1330, #1544

    Since:
        2026-06-27 (Issue #1330)
    """
    if not session_id or session_id == "unknown":
        return

    def _mutator(state: dict) -> None:
        _ensure_state_inplace(state, session_id)
        state["plan_critic_passed"] = True
        state["plan_critic_passed_plan_slug"] = plan_slug
        state["plan_critic_passed_timestamp"] = datetime.now().isoformat()

    _locked_rmw(session_id, _mutator, run_id=run_id)


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
    
    The verdict file is written atomically to `.claude/plan_critic verdict.json`
    with a specific schema that passes hook validation.
    
    Args:
        issue_number: The issue number being processed.
        bypass_reason: The reason for bypassing plan-critic.
        plan_summary: Optional one-line summary of the plan.
        
    Issues: #1279
    """
    import tempfile
    
    # Issue #1380: Sanitize bypass_reason to prevent log injection
    bypass_reason = _sanitize_bypass_reason(bypass_reason) or ""
    
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

    **Validator-artifact cross-check (single-issue runs only)**: for runs with
    ``issue_number == 0``, an agent in ``_VALIDATOR_ARTIFACT_AGENTS`` that is
    both required and recorded complete must also have a non-empty
    ``<activity>/validators/<current_run_id>/<agent>.txt`` on disk — the file
    ``implement.md`` instructs the coordinator to write. A recorded completion
    with no artifact adds a ``<agent>-artifact:<path>(absent-or-empty)``
    sentinel to *missing*. Batch runs are deliberately exempt: the artifact
    directory name there is not derivable from ``current_run_id`` (see
    :func:`_missing_validator_artifacts`), so checking them would block runs
    that DID write their artifacts. Every indeterminate case contributes
    nothing.

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

        # Cross-check the validator artifacts implement.md requires the
        # coordinator to persist. Only single-issue runs are checked (see
        # _missing_validator_artifacts for the batch-divergence reason), so the
        # state re-read is skipped entirely in batch mode. No state object is
        # in hand on this path — get_completed_agents returns a bare set.
        if issue_number == 0:
            _state_run_id = _read_state(session_id, run_id=run_id).get("current_run_id")
            missing = missing | _missing_validator_artifacts(
                _state_run_id, completed, required, issue_number
            )

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
    mutator: Callable[[dict], None],
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

            The mutator MUST NOT call another state mutator (or
            ``_locked_rmw`` directly): ``flock`` locks are per open file
            description, so a nested call in the same thread opens a second
            fd and blocks on a lock it already holds — a self-deadlock. Every
            mutator in this module is a pure in-memory transform of ``state``,
            which is what keeps that safe. Calling ``_write_state`` from
            inside a mutator is safe (the re-entrancy guard is held for the
            whole mutate-and-write, so it short-circuits to the direct atomic
            write instead of re-entering the lock) but pointless — the
            enclosing write follows immediately and supersedes it. Just mutate
            ``state``.
        run_id: Optional per-invocation run identifier. When provided,
            the lockfile key matches the state file's per-run key for
            scope parity. Must match ``_RUN_ID_RE`` (``[a-zA-Z0-9_-]{1,64}``);
            ValueError is raised otherwise.

    Issue #1544 made this the ONLY path to the on-disk write: all state
    mutators route through here, and ``_write_state`` self-wraps in this
    function when called from outside it. The fail-open branches below are
    still deliberate (a flock failure on NFS must not block the gate) but are
    now safe rather than merely rare — the underlying write is atomic
    (``os.replace``), so an unserialized fallback can lose an update but can
    never expose a truncated file to a concurrent reader.

    Issues: #1170, #1188, #1544
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

    def _rmw() -> None:
        """Read, mutate, write — with the raw-write guard held (#1544).

        The guard spans BOTH the mutate and the write. Holding it only across
        the write left a window in which a mutator that called ``_write_state``
        directly saw ``_in_locked_rmw() is False``, took the self-wrap branch,
        and re-entered ``_locked_rmw`` — a second fd on the same lockfile, a
        blocking ``LOCK_EX`` from a thread that already holds it, and a
        permanent hang (``flock`` locks are per open file description, not
        reentrant). Every ``_rmw()`` call site in this function — both
        fail-open branches and the locked path — uses this one closure, so the
        guard discipline is identical on all three.
        """
        _RMW_GUARD.depth = getattr(_RMW_GUARD, "depth", 0) + 1
        try:
            state = _read_state(session_id, run_id=run_id)
            mutator(state)
            _write_state(session_id, state, run_id=run_id)
        finally:
            _RMW_GUARD.depth -= 1

    try:
        # "a+" auto-creates the lockfile and never truncates — important
        # because losing the fd here would lose the lock for any other
        # process that's already blocked on it.
        lock_fh = open(lock_path, "a+")
    except OSError:
        # Lockfile couldn't be opened (permissions, full /tmp). Fall
        # back to the unlocked path — never raise out of state code.
        # #1544: the write itself is atomic, so this fallback can lose a
        # concurrent update but can never expose a truncated file.
        _rmw()
        return

    # #1544: the RMW is deliberately OUTSIDE the lockfile-open try/except so a
    # failure inside the mutator cannot fall through to the fallback branch and
    # apply the mutation a second time.
    try:
        try:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        except OSError:
            # Fail-open: a flock failure is rare (typically NFS) and
            # the gate must keep functioning. Drop straight into the
            # unlocked R-M-W path. Safe since #1544: the write itself
            # is atomic, so a reader never sees a partial file.
            _rmw()
            return

        try:
            _rmw()
        finally:
            # Release even on mutator exception so the lockfile does
            # not stay held — every other concurrent caller would
            # deadlock otherwise.
            try:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        try:
            lock_fh.close()
        except OSError:
            pass


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
        # _ensure_state behavior applied in place so the locked RMW does not
        # need a second read (#1544 made this the shared helper).
        _ensure_state_inplace(state, session_id)
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


# Issue #1481: Synthetic session-id patterns that must never be written to the
# sentinel. If ensure_sentinel_heartbeat is called with one of these shapes,
# refuse to overwrite the sentinel — the heartbeat is a recovery guard and
# recording a synthetic/test/unknown id poisons resolve_session_id()'s
# fallback chain (Issue #904).
_SYNTHETIC_SESSION_ID_PREFIXES = ("stop-", "test-", "unknown")


def _is_synthetic_session_id(session_id: str) -> bool:
    """Return True when ``session_id`` looks like a synthetic/derived id.

    Synthetic ids include:
    - ``stop-N`` — emitted by SubagentStop heartbeat when the real id was
      not resolvable (Issue #1481 root cause)
    - ``test-*`` — leaked in from hook-subprocess tests running against the
      live repo cwd (Issue #1481 secondary vector)
    - ``unknown`` — sentinel default when neither stdin nor env carried an id
    - empty / whitespace — malformed input

    Issue: #1481
    """
    if not isinstance(session_id, str):
        return True
    stripped = session_id.strip()
    if not stripped:
        return True
    lower = stripped.lower()
    for prefix in _SYNTHETIC_SESSION_ID_PREFIXES:
        if lower == prefix or lower.startswith(prefix):
            return True
    return False


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
    - If ``session_id`` is synthetic (``stop-N``, ``test-*``, ``unknown``,
      or empty), refuse to write and return ``False`` without touching the
      sentinel — writing a synthetic id would poison the resolve_session_id
      fallback chain (Issue #1481).
    - If ``state_path`` exists with a valid non-synthetic ``session_id``
      that differs from the argument, preserve the existing sentinel and
      return ``False`` — the heartbeat MUST NOT clobber a real owner
      (Issue #1481).
    - If ``state_path`` exists, is parseable JSON, and its ``session_id``
      field matches ``session_id`` → sentinel is healthy, return ``True``.
    - Otherwise (missing, corrupt, or existing-owner is synthetic) → emit a
      structured log line to stderr, recreate a minimal sentinel, and
      return ``False``.

    The function NEVER raises.  All failure modes degrade gracefully.

    Args:
        session_id: The expected owner's session id (e.g. from
            ``CLAUDE_SESSION_ID`` or the pipeline state file itself).
        state_path: Absolute path to the sentinel file.  Defaults to the
            ``PIPELINE_STATE_FILE`` env var, falling back to the per-repo
            ``<repo>/.claude/local/implement_pipeline_state.json`` (Issue #1206).

    Returns:
        ``True`` when the sentinel was already healthy.
        ``False`` when the sentinel was absent, mismatched, or the caller
        supplied a synthetic id (in which case NO write occurred).

    Issues: #989, #1206, #1481
    """
    if state_path is None:
        state_path = os.environ.get(
            "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
        )

    sentinel = Path(state_path)

    # Issue #1481 guard #1: refuse to write synthetic session_ids at all.
    if _is_synthetic_session_id(session_id):
        try:
            import sys as _sys_hb

            _sys_hb.stderr.write(
                f"[SENTINEL-HEARTBEAT-SYNTHETIC-REFUSED] state_path={state_path}"
                f" refused_session={session_id!r} (Issue #1481)\n"
            )
            _sys_hb.stderr.flush()
        except Exception:
            pass
        return False

    try:
        if sentinel.exists():
            try:
                raw = sentinel.read_text(encoding="utf-8")
                data = json.loads(raw)
            except (OSError, json.JSONDecodeError, ValueError):
                data = None

            if isinstance(data, dict):
                existing = data.get("session_id")
                if existing == session_id:
                    return True  # Sentinel healthy.
                # Issue #1481 guard #2: existing sentinel with a valid
                # non-synthetic owner MUST NOT be clobbered by heartbeat.
                # The heartbeat is a recovery guard, not a takeover
                # mechanism — a different real owner means either two
                # sessions are racing or the caller is confused, and in
                # either case the safe action is to leave the sentinel
                # alone and let downstream error handling surface the
                # divergence.
                if isinstance(existing, str) and not _is_synthetic_session_id(existing):
                    try:
                        import sys as _sys_hb

                        _sys_hb.stderr.write(
                            f"[SENTINEL-HEARTBEAT-PRESERVED] state_path={state_path}"
                            f" existing_owner={existing!r}"
                            f" caller_session={session_id!r} (Issue #1481)\n"
                        )
                        _sys_hb.stderr.flush()
                    except Exception:
                        pass
                    return False
    except Exception:
        # Defensive: any unexpected error falls through to recreation.
        pass

    # Sentinel is missing, corrupt, or the existing owner was synthetic
    # (safe to overwrite in that case — synthetic ids are always
    # replaceable by a real id).
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
    - ``/tmp/pipeline_agent_completions_*.json.*.tmp`` (orphaned ``os.replace``
      staging files left by a process killed mid-write, #1544)
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
        # #1544: os.replace() staging files. A process killed between
        # mkstemp() and os.replace() leaves one behind; the "*.json" glob
        # above does not match it, so reap it on the same cadence.
        ("/tmp/pipeline_agent_completions_*.json.*.tmp", "state_files_removed"),
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
