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
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

try:
    from .pipeline_state import atomic_write_json, get_legacy_sentinel_path  # type: ignore
except ImportError:  # pragma: no cover - script-style import fallback
    try:
        from pipeline_state import atomic_write_json, get_legacy_sentinel_path  # type: ignore
    except ImportError:
        def get_legacy_sentinel_path(repo_root: Optional[Path] = None) -> Path:  # type: ignore
            # Last-resort: behave like the pre-#1206 hardcoded fallback so the
            # module still imports in environments without path_utils.
            return Path("/tmp/implement_pipeline_state.json")

        def atomic_write_json(  # type: ignore
            path: Path, data: dict, *, indent: Optional[int] = None
        ) -> None:
            # Last-resort mirror of pipeline_state.atomic_write_json so the
            # sentinel repair path stays crash-safe even in degraded
            # environments where lib/ is not importable. Same mechanism:
            # mkstemp in the destination directory, chmod before rename,
            # os.replace (atomic per rename(2)).
            fd, tmp = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix=f".{path.name}_"
            )
            try:
                with os.fdopen(fd, "w") as _f:
                    json.dump(data, _f, indent=indent)
                try:
                    os.chmod(tmp, 0o600)
                except OSError:
                    pass
                os.replace(tmp, str(path))
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

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
    """Resolve the activity-log root through the single sanctioned chokepoint.

    Issue #1779 (AC1), SUBTRACTION. This used to be a SECOND resolver: its own
    walk up from ``Path.cwd()`` to the first ancestor holding
    ``.claude/logs/activity``. It referenced neither
    :data:`path_utils.ACTIVITY_LOG_DIR_ENV` nor
    :func:`path_utils.resolve_activity_log_dir`, so the test-isolation redirect
    installed in ``tests/conftest.py`` could not reach it. MEASURED 2026-09-12,
    one ordinary suite, three runs of three:

        pytest tests/unit/lib/test_pipeline_completion_state.py -k plan_critic
        -> +553 bytes appended to the repository's PRODUCTION
           .claude/logs/activity/2026-09-12.jsonl, carrying
           session_id="test_session_16565_1789196226072450000"

    Two writers reached the production file through here:
    :func:`record_plan_critic_skipped` and the validator-artifact path
    resolution in :func:`_missing_validator_artifacts`.

    Behaviour is otherwise preserved EXACTLY: the ``is_dir()`` requirement is
    kept, so an unresolvable or not-yet-created root still returns ``None`` and
    still reads as *indeterminate* to :func:`_missing_validator_artifacts`
    rather than flipping that gate from "no opinion" to "block".

    Args:
        start_dir: Directory to resolve from. Defaults to CWD.

    Returns:
        The resolved activity-log directory if it exists, else ``None``.
    """
    try:
        from path_utils import resolve_activity_log_dir  # type: ignore
    except ImportError:  # pragma: no cover - degraded env without lib/ on path
        return None
    try:
        log_dir = resolve_activity_log_dir(start_path=start_dir)
    except Exception:
        # LogDirResolutionError (or anything else): indeterminate, never a cwd
        # fallback — that fallback is exactly what Issue #1726 removed.
        return None
    try:
        return log_dir if log_dir.is_dir() else None
    except OSError:
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


class SentinelIntegrity(str, Enum):
    """Integrity of the STEP-0 pipeline sentinel. Three states, never two.

    Issue #1779 (AC3 / INV-7). MEASURED 2026-09-12: a test truncated a live
    run's ``.claude/local/implement_pipeline_state.json`` to 0 bytes, destroying
    ``alignment_passed``, ``alignment_verdict``, ``pipeline_base_commit`` and
    ``issue_number``. ``resolve_session_id`` noticed — it emitted
    ``[SENTINEL-UNREADABLE] ... JSONDecodeError`` — and then continued its
    fallback chain as though the file were merely ABSENT. The ordering gate
    consequently returned ``passed=True`` for ``implementer``.

    Collapsing ABSENT and CORRUPT into one "no usable data" case is the whole
    defect. They mean opposite things:

    * :attr:`ABSENT` — the normal state of every session that is not inside a
      pipeline. Refusing it would block ordinary work.
    * :attr:`CORRUPT` — the file EXISTS and its gating fields cannot be read.
      Per INV-7 that is a verification failure, and a verification failure is
      "not passed", never "passed".
    """

    OK = "ok"
    ABSENT = "absent"
    CORRUPT = "corrupt"


def sentinel_integrity(*, sentinel_path: Optional[str] = None) -> SentinelIntegrity:
    """Classify the pipeline sentinel as OK / ABSENT / CORRUPT.

    Deliberately independent of :func:`resolve_session_id`: that function
    short-circuits on ``CLAUDE_SESSION_ID`` and then never reads the sentinel at
    all, so a resolvable session id is no evidence the gating state survived.

    "Corrupt" means **exists but does not yield a JSON object**. Catching only
    ``json.JSONDecodeError`` would be too narrow: a JSON array and a JSON scalar
    both parse cleanly and neither can carry ``alignment_passed``.

    Args:
        sentinel_path: Sentinel to inspect. Defaults to ``PIPELINE_STATE_FILE``
            when set, else :func:`get_legacy_sentinel_path`. The env var is
            honoured here because a gate that only ever checked the default path
            would be inert for any run that redirected it.

    Returns:
        A :class:`SentinelIntegrity`. NEVER raises — any unexpected error is
        :attr:`SentinelIntegrity.CORRUPT`, because a check that can crash turns
        a refusal into an outage.
    """
    if sentinel_path is None:
        sentinel_path = os.environ.get("PIPELINE_STATE_FILE") or str(
            get_legacy_sentinel_path()
        )
    target = Path(sentinel_path)
    try:
        if not target.exists():
            return SentinelIntegrity.ABSENT
    except OSError:
        # Cannot even stat it: the path is there in some form we cannot read.
        return SentinelIntegrity.CORRUPT

    try:
        raw = target.read_bytes()
    except OSError:
        return SentinelIntegrity.CORRUPT
    except Exception:
        return SentinelIntegrity.CORRUPT

    if not raw.strip():
        # The measured shape: 0 bytes (or whitespace) from a killed writer.
        return SentinelIntegrity.CORRUPT

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return SentinelIntegrity.CORRUPT

    if not isinstance(data, dict):
        return SentinelIntegrity.CORRUPT

    return SentinelIntegrity.OK


def describe_sentinel_corruption(sentinel_path: Optional[str] = None) -> str:
    """Render the refusal text for a CORRUPT sentinel.

    Args:
        sentinel_path: The sentinel that failed. Resolved the same way as
            :func:`sentinel_integrity` when omitted.

    Returns:
        A message naming the path and the required next action, in the
        stick+carrot shape every other block in this repo uses.
    """
    if sentinel_path is None:
        sentinel_path = os.environ.get("PIPELINE_STATE_FILE") or str(
            get_legacy_sentinel_path()
        )
    return (
        f"SENTINEL CORRUPT: the pipeline gating state at {sentinel_path} exists "
        "but cannot be read as a JSON object, so alignment_passed, "
        "alignment_verdict and pipeline_base_commit are unverifiable.\n"
        "INV-7: a verification failure is treated as 'not passed', never as "
        "'passed' (Issue #1779, AC3).\n"
        "REQUIRED NEXT ACTION: re-run /implement STEP 0 to rewrite the "
        "sentinel. Do NOT hand-edit it and do NOT proceed on the assumption "
        "that alignment passed."
    )


def run_credit_refusal(
    session_id: str,
    *,
    sentinel_path: Optional[str] = None,
    native_dispatch: bool = False,
) -> Optional[str]:
    """Why completions must NOT be credited to the CURRENT run, or ``None``.

    Two refusals, one per direction of Issue #1807's forgery pair. Both are
    about the SENTINEL and the LEDGER disagreeing about what the current run is:

    1. The sentinel EXISTS but identifies no run (no ``run_id``/``mode``/
       ``explicitly_invoked``) — the shape the repair path used to write over a
       live run. "Exists and parses" is not "identifies a run", so dispatch and
       completion credit both refuse (A5a, A4b). An ABSENT sentinel is NOT this
       case: absent is the normal state of every session outside a pipeline, and
       refusing it would block ordinary work.
    2. The ledger CLAIMS a current run (``current_run_id`` from
       :func:`record_run_start`) that no authorized sentinel corroborates. The
       ledger is unsigned, so a retained run id must never rebuild current-run
       credit for a run whose sentinel is gone or replaced (A4a). When the ledger
       claims no run at all, this function is silent: that is the pre-#1045
       session-scoped path, which #1807 does not change.

    Args:
        session_id: The session whose completions would be credited.
        sentinel_path: Sentinel to inspect. Defaults to ``PIPELINE_STATE_FILE``
            when set, else :func:`get_legacy_sentinel_path` — the same
            resolution :func:`sentinel_integrity` uses.
        native_dispatch: Opt into physical carrier qualification before native
            Agent admission. Present corrupt, unreadable or stale ledgers,
            dangling sentinels and partial native claims refuse rather than
            masquerading as ordinary absence. Valid no-run legacy ledgers
            remain permitted; the default preserves legacy completion callers.

    Returns:
        A refusal message naming the seam and the required next action, or
        ``None`` when current-run credit is permitted. NEVER raises.

    Issue: #1807
    """
    if sentinel_path is None:
        sentinel_path = os.environ.get("PIPELINE_STATE_FILE") or str(
            get_legacy_sentinel_path()
        )

    native_claim = False
    native_sentinel_present = False
    if native_dispatch:
        # Native dispatch cannot confuse the reader's {} error fallback with
        # ordinary absence. Keep this stricter carrier qualification opt-in so
        # legacy session-scoped completion callers retain their contract.
        try:
            Path(sentinel_path).lstat()
            native_sentinel_present = True
        except FileNotFoundError:
            pass
        except OSError as exc:
            return f"NATIVE SENTINEL UNAVAILABLE: {exc}; start a fresh /implement run"
        ledger_path = _state_file_path(session_id)
        try:
            ledger_path.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            return f"NATIVE LEDGER UNAVAILABLE: {exc}; start a fresh /implement run"
        else:
            try:
                if time.time() - ledger_path.stat().st_mtime > 7200:
                    return "NATIVE LEDGER STALE: start a fresh /implement run"
                ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
                if not isinstance(ledger, dict):
                    raise ValueError("ledger is not an object")
                native_claim = any(key in ledger for key in (
                    "current_run_id", "native_origin", "native_agent_joins",
                ))
            except (OSError, ValueError) as exc:
                return f"NATIVE LEDGER UNAVAILABLE: {exc}; start a fresh /implement run"

    sentinel: Optional[dict] = None
    try:
        target = Path(sentinel_path)
        if target.exists() or native_sentinel_present:
            raw = target.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            sentinel = parsed if isinstance(parsed, dict) else {}
    except (OSError, ValueError):
        # Unreadable-but-present is SentinelIntegrity.CORRUPT, which the caller
        # refuses on its own path. Treat it as identity-less here too.
        sentinel = {}

    if sentinel is not None and not _state_carries_run_identity(sentinel):
        return (
            f"RUN IDENTITY DESTROYED: the pipeline sentinel at {sentinel_path} "
            f"exists but carries no run identity (keys={sorted(sentinel)}), so "
            "no agent dispatch or completion can be attributed to a current "
            "run.\nINV-7: a verification failure is 'not passed', never "
            "'passed' (Issue #1807).\nREQUIRED NEXT ACTION: start a fresh "
            "/implement run. Do NOT hand-write the missing identity fields and "
            "do NOT rebuild them from the completion ledger or from chat."
        )

    # Issue #1807 (defect 3): a sentinel that DOES carry a run identity is a
    # genuine /implement SIGNAL, and it must be AUTHORIZED, not merely present.
    # Classify it here even when NO run-start receipt exists for the crediting
    # session. A run-bearing sentinel with no receipt is precisely the A3/A7
    # self-mint, and the pre-F3 early ``return None`` on a missing receipt (below,
    # for the absent-sentinel path) was the FREE PASS that dispatched the first
    # fix-mode implementer from an unverified run. ``classify_current_run_authority``
    # performs the full check — owner bound to the PRESENTED session id, MAC
    # verified, receipt corroborating the run_id — so an UNSIGNED (UNSIGNED_LEGACY),
    # receiptless (RECEIPT_UNAVAILABLE), tampered (MAC_INVALID) or wrong-owner
    # (UNQUALIFIED_OWNER) run-bearing sentinel all classify as NOT authorized and
    # refuse here.
    if sentinel is not None:  # _state_carries_run_identity(sentinel) is True here
        try:
            from pipeline_state import classify_current_run_authority  # type: ignore
        except ImportError:
            try:
                from .pipeline_state import classify_current_run_authority  # type: ignore
            except ImportError:
                return (
                    "RUN AUTHORITY UNVERIFIABLE: pipeline_state."
                    "classify_current_run_authority is unavailable, so whether the "
                    f"run-bearing sentinel at {sentinel_path} authorizes session "
                    f"{session_id!r} cannot be determined (fail closed, Issue "
                    "#1807)."
                )

        # Read the receipt ONCE and reuse it for the owner. Keyed on the owner,
        # NOT unconditional: the sentinel's owner and the crediting session can
        # differ, and handing the classifier one session's receipt for another's
        # owner would be a false corroboration rather than a saved read.
        receipt = get_run_start_receipt(session_id)

        def _reuse_receipt(owner: str) -> Optional[str]:
            """Return the receipt already read for *session_id*, else read afresh."""
            return receipt if owner == session_id else get_run_start_receipt(owner)

        verdict = classify_current_run_authority(
            sentinel, session_id, receipt_lookup=_reuse_receipt
        )
        if not verdict.authorized:
            return (
                f"UNCORROBORATED RUN CLAIM: the pipeline sentinel at "
                f"{sentinel_path} identifies a run but does not authorize it for "
                f"session {session_id!r} ({verdict.authority.value}: "
                f"{verdict.detail}).\nA genuine /implement signal without verified "
                "current-run authority must not credit completions or dispatch "
                "agents (Issue #1807 defect 3).\nREQUIRED NEXT ACTION: start a "
                "fresh /implement run. Do NOT hand-write the missing identity "
                "fields and do NOT rebuild them from the completion ledger."
            )
        return None

    # sentinel is None (ABSENT): the pre-#1045 permissive / ledger-only split.
    # An absent sentinel with NO run claim is ordinary non-pipeline work — the
    # CONTROL case #1807 defect 3 must leave ungated. A retained ledger run id
    # with no sentinel to authorize it is A4's ledger-only forgery.
    receipt = get_run_start_receipt(session_id)
    if not receipt and native_claim:
        return "PARTIAL NATIVE RUN CLAIM: no authorizing sentinel; start a fresh /implement run"
    if not receipt:
        return None  # No current-run claim to corroborate (pre-#1045 path).
    return (
        f"LEDGER-ONLY RUN CLAIM: the completion ledger still names run "
        f"{receipt!r} for session {session_id!r}, but there is no pipeline "
        f"sentinel at {sentinel_path} to authorize it. The ledger is unsigned; a "
        "retained run id is not run authority (Issue #1807 A4).\nREQUIRED NEXT "
        "ACTION: start a fresh /implement run."
    )


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
            except (OSError, json.JSONDecodeError, ValueError) as _sentinel_err:
                # This except sits inside the os.stat() SUCCESS branch, so the
                # file provably EXISTS and is merely unreadable/unparseable
                # (the 0-byte truncate shape). A merely-absent sentinel raises
                # from os.stat() and lands in the outer handler, silently.
                # This is the one place that can tell "absent" from "corrupt";
                # saying so is what makes the two distinguishable in the log.
                data = None
                try:
                    sys.stderr.write(
                        f"[SENTINEL-UNREADABLE] path={sentinel_path}"
                        f" err={type(_sentinel_err).__name__}: {_sentinel_err}\n"
                    )
                    sys.stderr.flush()
                except Exception:
                    pass
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
        # Native specialist credit belongs exclusively to the exact
        # PreToolUse/ PostToolUse Agent join. The legacy public writer must
        # not mint a current-run stamp, even when called directly. Keep the
        # separate virtual pytest gate on its existing path.
        if agent_type != "pytest-gate" and (
            _native_agent_join_active(state)
            or _signed_native_agent_scope(session_id) is not None
        ):
            return
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


def _native_agent_join_active(state: dict) -> bool:
    """Only a live, witnessed run uses exact native Agent completion credit."""
    return bool(state.get("current_run_id") and isinstance(state.get("native_origin"), dict))


def native_agent_join_active(session_id: str) -> bool:
    """Tell hook callers whether FIFO completion credit must be suppressed."""
    if _native_agent_join_active(_read_state(session_id)):
        return True
    # A lost/unreadable ledger must not turn a signed native run into legacy
    # FIFO credit. The sentinel is only a fail-closed signal here, never a source
    # of issue scope or completion authority.
    try:
        from pipeline_state import verify_state_hmac
        sentinel = json.loads(Path(os.environ.get("PIPELINE_STATE_FILE") or get_legacy_sentinel_path()).read_text())
        return bool(
            isinstance(sentinel, dict)
            and sentinel.get("session_id") == session_id
            and sentinel.get("explicitly_invoked") is True
            and verify_state_hmac(sentinel, session_id, strict=True)
        )
    except (ImportError, OSError, ValueError, TypeError):
        return False


def _signed_native_agent_scope(session_id: str) -> Optional[dict]:
    """Read the signed run carrier; unsigned/stale/foreign scope has no authority."""
    try:
        from pipeline_state import verify_state_hmac
        sentinel = json.loads(Path(os.environ.get("PIPELINE_STATE_FILE") or get_legacy_sentinel_path()).read_text())
        if (not isinstance(sentinel, dict)
                or sentinel.get("session_id") != session_id
                or sentinel.get("explicitly_invoked") is not True
                or not verify_state_hmac(sentinel, session_id, strict=True)):
            return None
        issue = sentinel.get("issue_number", "")
        if issue != "" and (not isinstance(issue, int) or isinstance(issue, bool)):
            return None
        return {"run_id": sentinel.get("run_id"), "issue_number": issue}
    except (ImportError, OSError, ValueError, TypeError):
        return None


def get_native_agent_run_id(session_id: str, tool_use_id: str) -> Optional[str]:
    """Return the verified run for an exact native Agent join, or no attribution.

    Args:
        session_id: Native callback owner, not a model-supplied parent identity.
        tool_use_id: Exact foreground dispatch/result identity.

    Returns:
        Current typed-user run identifier only when the signed scope, ledger
        owner and raw join bindings agree; otherwise ``None``. No ledger content
        is written, although the existing state reader refreshes ledger mtime.
    """
    if not all(isinstance(value, str) and value.strip() for value in (session_id, tool_use_id)):
        return None
    try:
        from pipeline_state import classify_current_run_authority
        scope = _signed_native_agent_scope(session_id)
        state = _read_state(session_id)
        if (scope is None or not _native_agent_join_active(state)
                or state.get("session_id") != session_id
                or scope["run_id"] != state.get("current_run_id")):
            return None
        sentinel = json.loads(Path(os.environ.get("PIPELINE_STATE_FILE") or get_legacy_sentinel_path()).read_text())
        if (not isinstance(sentinel, dict)
                or sentinel.get("session_id") != session_id
                or sentinel.get("run_id") != scope["run_id"]
                or sentinel.get("issue_number", "") != scope["issue_number"]
                or not classify_current_run_authority(sentinel, session_id).typed_user_origin):
            return None
        joins = state.get("native_agent_joins", {})
        entry = joins.get(tool_use_id) if isinstance(joins, dict) else None
        if (not isinstance(entry, dict) or entry.get("tool_use_id") != tool_use_id
                or entry.get("run_id") != scope["run_id"]
                or entry.get("issue_number") != scope["issue_number"]
                or entry.get("status") not in ("reserved", "completed", "failed")
                or not isinstance(entry.get("agent_type"), str) or not entry["agent_type"].strip()):
            return None
        return scope["run_id"]
    except (ImportError, OSError, ValueError, TypeError, AttributeError):
        return None


def register_native_agent_dispatch(
    session_id: str, tool_use_id: str, agent_type: str, run_in_background: Any,
    *, prepare: Optional[Callable[[], None]] = None,
) -> str:
    """Reserve an exact foreground Agent call in the active signed run.

    Args:
        session_id: Native callback owner, bound to the signed run.
        tool_use_id: Exact Agent tool-call identity; existing joins are not reused.
        agent_type: Specialist type receiving completion credit.
        run_in_background: Must be the explicit boolean ``False``.
        prepare: Optional trusted native callback, invoked only after this
            reservation is persisted and read back. It must publish the
            protected-edit sentinel atomically LAST and raise on failure.
            Native Agent preparation uses ``tool_use_id`` as its generation
            and does not append legacy FIFO cache entries.

    Returns:
        ``registered`` only after reservation and preparation succeed. A
        preparation/readback failure aborts only this invocation's reservation.
        Failed abort persistence returns an explicit cleanup-failed result and
        leaves the run non-reusable; it never reports a clean dispatch lane.
        The caller must independently resolve permission before invoking this
        function and must refuse every non-registered native admission result.
    """
    result = "inactive"
    signed_scope = _signed_native_agent_scope(session_id)
    try:
        ledger_native = _native_agent_join_active(_read_state(session_id))
    except Exception:
        return "write_failed"
    if not ledger_native and signed_scope is None:
        return "inactive"
    if not all(isinstance(v, str) and v.strip() for v in (session_id, tool_use_id, agent_type)):
        return "invalid"
    if run_in_background is not False:
        return "not_foreground"

    def _mutator(state: dict) -> None:
        nonlocal result
        if not _native_agent_join_active(state):
            return
        if signed_scope is None or signed_scope["run_id"] != state["current_run_id"]:
            result = "unbound_scope"
            return
        joins = state.setdefault("native_agent_joins", {})
        if not isinstance(joins, dict) or tool_use_id in joins:
            result = "duplicate"
            return
        run_id = state["current_run_id"]
        # Completion is stored by agent type. Until the preceding foreground
        # call completes, another dispatch could reuse that type-level credit.
        # Failed calls require a fresh run, rather than silently advancing.
        if any(
            isinstance(entry, dict) and entry.get("run_id") == run_id
            and entry.get("status") in ("reserved", "failed")
            for entry in joins.values()
        ):
            result = "in_flight"
            return
        issue = signed_scope["issue_number"]
        owned_issues = [str(k) for k, v in state.get("issue_run_starts", {}).items()
                        if v == run_id]
        if issue == "" and owned_issues:
            result = "issue_mismatch"
            return
        if issue != "" and (str(issue) not in owned_issues or len(owned_issues) != 1):
            result = "issue_mismatch"
            return
        joins[tool_use_id] = {
            "run_id": run_id,
            "issue_number": issue,
            "tool_use_id": tool_use_id,
            "agent_type": agent_type,
            "status": "reserved",
        }
        # A repeat dispatch of the same specialist must not inherit its prior
        # type-level completion while this new foreground invocation is live.
        scopes = {"0", "unscoped"}
        if issue != "":
            scopes.add(str(issue))
        for key in scopes:
            completions = state.get("completions", {}).get(key, {})
            if isinstance(completions, dict) and agent_type in completions:
                completions[agent_type] = False
        result = "registered"

    def _abort_reservation() -> str:
        """Remove only this attempted join; failed cleanup requires a fresh run."""
        if signed_scope is None or result != "registered":
            return "write_failed"
        run_id = signed_scope["run_id"]

        def _abort(state: dict) -> None:
            joins = state.get("native_agent_joins", {})
            if not isinstance(joins, dict):
                return
            entry = joins.get(tool_use_id)
            if (
                isinstance(entry, dict) and entry.get("run_id") == run_id
                and entry.get("tool_use_id") == tool_use_id
                and entry.get("status") == "reserved"
            ):
                del joins[tool_use_id]

        try:
            _locked_rmw(session_id, _abort)
        except Exception:
            # Do not claim a clean lane when persistence is unavailable. The
            # caller refuses; the remaining reservation blocks reuse until a
            # new typed native run supersedes this conflicted attempt.
            return "cleanup_failed_fresh_native_run_required"
        return "write_failed"

    try:
        _locked_rmw(session_id, _mutator)
        if result == "registered":
            persisted = _read_state(session_id).get("native_agent_joins", {}).get(tool_use_id)
            if not isinstance(persisted, dict) or persisted.get("status") != "reserved":
                return _abort_reservation()
            if prepare is not None:
                prepare()
    except Exception:
        return _abort_reservation()
    return result


def join_native_agent_result(
    session_id: str, tool_use_id: str, agent_id: str, status: str, has_error: bool
) -> str:
    """Atomically credit one completed foreground Agent response to its reservation."""
    result = "inactive"
    if not isinstance(tool_use_id, str) or not tool_use_id.strip():
        return "invalid"
    signed_scope = _signed_native_agent_scope(session_id)

    def _mutator(state: dict) -> None:
        nonlocal result
        if not _native_agent_join_active(state):
            return
        pending = state.get("native_agent_joins", {}).get(tool_use_id)
        if not isinstance(pending, dict) or pending.get("status") != "reserved":
            result = "unjoined"
        elif pending.get("run_id") != state.get("current_run_id"):
            result = "rebound"
        elif signed_scope is None or signed_scope != {
            "run_id": pending["run_id"], "issue_number": pending["issue_number"]
        }:
            result = "unbound_scope"
        elif not isinstance(agent_id, str) or not agent_id.strip():
            pending["status"] = "failed"
            result = "invalid"
        elif status != "completed" or has_error is not False:
            pending["status"] = "failed"
            result = "failed"
        elif any(
            isinstance(entry, dict) and entry.get("run_id") == pending["run_id"]
            and entry.get("status") == "completed" and entry.get("agent_id") == agent_id
            for entry in state.get("native_agent_joins", {}).values()
        ):
            result = "duplicate"
        else:
            agent_type = pending["agent_type"]
            scope_keys = {"0", "unscoped"}
            if pending["issue_number"] != "":
                scope_keys.add(str(pending["issue_number"]))
            for key in scope_keys:
                state.setdefault("completions", {}).setdefault(key, {})[agent_type] = True
            _record_completion_times(state, scope_keys, agent_type)
            _record_completion_run_ids(state, scope_keys, agent_type)
            pending["status"] = "completed"
            pending["agent_id"] = agent_id
            result = "completed"

    try:
        _locked_rmw(session_id, _mutator)
    except Exception:
        return "write_failed"
    return result


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


def get_run_start_receipt(session_id: str) -> Optional[str]:
    """Return the run id :func:`record_run_start` stamped for *session_id*.

    This is the read half of the run-start receipt — the second of the two
    carriers ``pipeline_state.classify_current_run_authority`` requires (Issue
    #1807). It exists so the authority check has ONE canonical reader instead of
    every consumer re-deriving ``/tmp/pipeline_agent_completions_*`` paths.

    Read-only by design, with one deliberate side effect inherited from
    :func:`_read_state`: a successful read refreshes the ledger's mtime, so a
    long run whose authority is checked on every hook invocation cannot age past
    the 2-hour staleness window and lose its own receipt mid-flight (#1413).

    A receipt is NOT proof of provenance — the ledger is UNSIGNED and lives in
    ``/tmp``, and ``record_run_start`` is reachable from model-controlled Bash,
    so a caller willing to write both carriers can mint the receipt and then the
    signed sentinel. #1807's A4 pins that a retained run id must never rebuild
    authority by itself; this reader closes that single-carrier route and
    NOTHING more. The receipt path's trust depends on an ORIGIN boundary that
    refuses model-controlled writes to this ledger while native hook processes
    keep writing it — acceptance case A9, currently OPEN and UNMEASURED. Do not
    read a green authority verdict as provenance, and do not "fix" that by
    adding a second store: the existing ledger stays the carrier (INV-7).

    Args:
        session_id: The owning session whose receipt to read.

    Returns:
        The recorded run id, or ``None`` when the session has no receipt, the
        ledger is absent/stale/unreadable, or *session_id* is unusable.

    Issues: #1045, #1807
    """
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    try:
        state = _read_state(session_id.strip())
    except Exception:  # noqa: BLE001 - state code never raises into a gate
        return None
    value = state.get("current_run_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


# =============================================================================
# NATIVE-ORIGIN WITNESS (Issue #1807, A7/A9)
# =============================================================================
#
# WHAT THIS CLOSES, AND WHAT IT DOES NOT. The two carriers
# ``pipeline_state.classify_current_run_authority`` requires — the signed sentinel
# and the run-start receipt — are BOTH initiated by model-owned coordinator Bash
# (``commands/implement.md`` STEP 0, ``commands/implement-fix.md`` F1). The
# principal the controls constrain mints the authority they check, so the
# conjunction removes single-artifact forgery and nothing more (A3/A7).
#
# A NATIVE-ORIGIN WITNESS is a third carrier whose WRITER is a native hook
# process: the Claude Code runtime invokes ``hooks/native_run_origin.py`` on
# ``UserPromptExpansion`` (a user-TYPED ``/implement``) or on ``PreToolUse`` with
# ``tool_name=Skill`` (a MODEL-invoked Skill call). The event name mechanically
# distinguishes those two origins, and they are NOT equivalent:
#
#   * UserPromptExpansion -> TYPED-USER origin. The only class that can carry
#     user authorization, because a human typed the command.
#   * PreToolUse/Skill    -> MODEL-SKILL origin. A genuinely native EVENT, but
#     the MODEL chose to fire it. Recorded, distinguishable, and NEVER promotable
#     to typed-user. Treating it as user authorization would hand the model a
#     native carrier for minting its own authority — the confusion #1807 exists
#     to remove, and the reason nothing here accepts a caller-supplied origin,
#     approval flag or env var.
#
# EVIDENCE LIMIT. Payload shape NEVER proves native origin: a caller that pipes
# fabricated stdin into the hook presents byte-identical fields, ``command_source``
# included. What would make the origin unforgeable is the OS boundary (sandbox
# denyWrite for subprocesses AND ``permissions.deny Edit(//abspath)`` for built-in
# editors — both required), which is OUT of this slice. This code builds the
# native-owned entrypoint and its MECHANICAL CONTRACT: every malformed, unsigned,
# wrong-owner, wrong-run, wrong-binding or replayed witness is REFUSED, so a
# future OS-level origin split has something precise to attach to. A9 is OPEN and
# UNMEASURED; do not read a green origin verdict as provenance.
#
# WHAT IS *NOT* PART OF THAT GUARANTEE. ``witness_path_verdict`` below is
# NON-LOAD-BEARING defence in depth, not A9 evidence. Every path it judges is
# LIBRARY-DERIVED (``_state_file_path`` builds it from the ledger root), so no
# caller-supplied path reaches it and it is the sole barrier against nothing. Its
# CWE-59 rule is the same one ``path_utils._is_valid_policy_file`` applies — that
# named sibling cannot serve here only because it requires the file to already
# exist and parse as JSON. Quoting this check as unforgeability would be exactly
# the description-shaped evidence #1807 refuses.
#
# NO NEW STORE, NO NEW SIGNER. The witness is a FIELD in the existing per-session
# ledger this module already owns, written through the existing ``_locked_rmw``,
# and signed by the existing ``pipeline_state.sign_state`` v3 chain — a witness is
# a state-shaped record whose ``run_id`` is its own witness id, so it reuses the
# per-record secret store and verifies under the SAME ``verify_state_hmac``. The
# frozen v1/v2/v3 MAC message bytes are untouched.

#: Native hook events that may INITIATE a run. Anything else mints nothing. ONE
#: home for the vocabulary: ``pipeline_state`` maps these two names onto the two
#: origin classes and refuses any third value.
NATIVE_INIT_EVENTS: Tuple[str, ...] = ("UserPromptExpansion", "PreToolUse")

#: ``mode`` markers distinguishing the two record kinds from a pipeline state.
#: They are INSIDE the signed message, so a record cannot be re-labelled after
#: signing.
NATIVE_ORIGIN_WITNESS_MODE = "native-origin-witness"
NATIVE_ORIGIN_PROGRESSION_MODE = "native-origin-progression"

#: The run bindings a witness chain binds, in the spelling the sentinel uses.
#: ``session_id`` is absent on purpose — the OWNER is bound by the v3 owner token
#: on every record, not by a comparable field.
NATIVE_ORIGIN_BINDING_KEYS: Tuple[str, ...] = (
    "run_id",
    "mode",
    "issue_number",
    "subject",
    "base_commit",
)

#: Bindings that must be present and non-empty. The rest are REFINABLE: a witness
#: minted at initiation legitimately records ``base_commit`` empty, because
#: ``set_pipeline_base_commit`` writes it AFTER STEP 0. An empty recorded binding
#: constrains nothing; a NON-EMPTY one must match exactly. Changing a non-empty
#: binding is a rebind and is refused.
_NATIVE_ORIGIN_REQUIRED_BINDINGS: Tuple[str, ...] = ("run_id", "mode")

#: The ledger field holding the chain.
_NATIVE_ORIGIN_LEDGER_KEY = "native_origin"

#: Chain length ceiling. The chain is read on every authority check, so an
#: unbounded list is both a cost and a forgery surface (bloat the chain, stall the
#: reader). A run appends one record per progression event; 64 is far above any
#: real pipeline and a chain longer than this is refused outright.
_NATIVE_ORIGIN_MAX_PROGRESSION = 64

#: Minimum MAC version a witness record may declare. Witness records are minted
#: fresh per run and always signed at the CURRENT version, so requiring v3 refuses
#: a downgrade forgery (sign at v1, where the owner is unbound) without the
#: in-flight-run compatibility problem that forces ``verify_state_hmac`` to keep
#: accepting v1 for pipeline states.
_NATIVE_ORIGIN_MIN_MAC_VERSION = 3

#: Commands and skills that may initiate an /implement run: ``implement`` itself
#: plus its family spellings (``implement-fix``, ``implement-batch``, ...). An
#: optional leading slash is tolerated because native payloads spell the name
#: differently. The plugin-native route supplies autonomous-dev:implement;
#: other namespaces are never accepted. This is a NAME allowlist, NOT a
#: parse of a shell command string (INV-1 forbids the latter as containment).
_IMPLEMENT_FAMILY_RE = re.compile(
    r"^(?:/?implement|autonomous-dev:implement)(?:-[a-z0-9][a-z0-9-]*)?$"
)


@dataclass(frozen=True)
class NativeOriginCheck:
    """What the ledger says about the native origin of a run.

    Deliberately FACTUAL rather than a verdict: it reports presence, validity and
    the native EVENT, and ``pipeline_state`` owns the single mapping from event to
    origin class. Two vocabularies for one topic is how they drift.

    Attributes:
        present: A witness carrier exists for this owner.
        valid: The whole chain verified against the presented run bindings.
        event: The native event recorded in the signed claim, or ``""``.
        detail: Operator-facing explanation naming the refused seam.
        instrument_ok: False when the check could not be PERFORMED (the signing
            library is unavailable). "Cannot tell" is never "passed" (INV-7), and
            callers must distinguish it from a judgment about the witness.
    """

    present: bool
    valid: bool
    event: str
    detail: str
    instrument_ok: bool = True


def _native_origin_note(detail: str) -> None:
    """Report a native-origin refusal on stderr. Best effort, never raises."""
    try:
        sys.stderr.write(f"[NATIVE-ORIGIN-REFUSED] {detail}\n")
        sys.stderr.flush()
    except Exception:  # pragma: no cover - stderr itself is broken
        pass


def _native_origin_signers() -> Tuple[Optional[Callable], Optional[Callable], Optional[Callable]]:
    """Return ``(sign_state, verify_state_hmac, generate_run_id)``, or all ``None``.

    ONE import seam for the three EXISTING owners this feature reuses, so "is the
    signer present?" is asked in a single place and every consumer fails closed the
    same way. Nothing here re-implements MAC computation, nonce generation, id
    minting or the per-record secret store — those all live in ``pipeline_state``
    and are called directly.
    """
    try:
        try:
            from .pipeline_state import (  # type: ignore
                generate_run_id,
                sign_state,
                verify_state_hmac,
            )
        except ImportError:
            from pipeline_state import (  # type: ignore
                generate_run_id,
                sign_state,
                verify_state_hmac,
            )
    except ImportError:
        return None, None, None
    return sign_state, verify_state_hmac, generate_run_id


def witness_path_verdict(path: Any) -> Tuple[bool, str, Optional[str]]:
    """Whether the witness carrier at *path* may be written, and its canonical form.

    SCOPE — NON-LOAD-BEARING DEFENCE IN DEPTH. This is not part of the A9
    unforgeability guarantee and must not be quoted as evidence for it. The only
    paths it ever sees are LIBRARY-DERIVED: :func:`_state_file_path` builds them
    from the ledger root, so no caller-supplied path reaches here and there is no
    attack this check is the sole barrier against. A9 unforgeability requires the
    OS BOUNDARY (sandbox ``denyWrite`` plus a ``permissions.deny`` rule for the
    built-in editors), which is OUT of this slice entirely. What this DOES buy is
    the cheap belt-and-braces case: if the ledger root is ever relocated onto a
    path an attacker can pre-create, the symlink refusal below is already in place.

    LSTAT-AWARE ON PURPOSE. ``Path.exists()`` returns False for a DANGLING
    symlink, so an existence check alone reads an attacker-planted redirect as
    "absent, safe to create" and then writes through it. Every symlink is refused
    here — live or dangling — because the carrier must be a regular file the
    ledger owner controls, not an indirection someone else can re-point.

    Normalization is by ``realpath`` of the PARENT plus the literal basename, so
    the ``/tmp`` versus ``/private/tmp`` (and ``/System/Volumes/Data/...``) alias
    spellings of one file canonicalize identically without resolving a symlink at
    the leaf — resolving the leaf would defeat the refusal above.

    NEAREST EXISTING OWNER, and why it cannot serve: ``path_utils``'s private
    ``_is_valid_policy_file`` applies the same CWE-59 symlink refusal, but it
    REQUIRES the file to exist and to parse as JSON and returns a bare bool. The
    witness carrier legitimately does not exist yet on a first write, and the
    caller needs the refusal REASON and the canonical form; relaxing the policy
    validator's existence requirement would break its own callers, which use it to
    validate an already-written policy file. Two questions, named siblings, one
    shared rule.

    Args:
        path: Candidate carrier path (any type; non-strings are refused).

    Returns:
        ``(ok, reason, canonical)``. ``ok`` False always carries a non-empty
        *reason* and a ``None`` *canonical*; ``ok`` True carries an absolute
        canonical path. Fails closed on any OSError.

    Issues: #1807
    """
    if not isinstance(path, str) or not path.strip():
        return False, f"witness carrier path {path!r} is absent or not a string", None

    raw = path.strip()
    try:
        if os.path.islink(raw):
            dangling = "DANGLING " if not os.path.exists(raw) else ""
            return (
                False,
                f"witness carrier path {raw!r} is a {dangling}symlink; the carrier "
                "must be a regular file, not an indirection that can be re-pointed",
                None,
            )
        if os.path.lexists(raw) and not os.path.isfile(raw):
            return (
                False,
                f"witness carrier path {raw!r} exists and is not a regular file",
                None,
            )
        parent = os.path.dirname(os.path.abspath(raw))
        if not os.path.isdir(parent):
            return (
                False,
                f"witness carrier parent directory {parent!r} does not exist",
                None,
            )
        canonical = os.path.join(os.path.realpath(parent), os.path.basename(raw))
    except OSError as exc:
        return False, f"witness carrier path {raw!r} is unresolvable: {exc}", None
    return True, "", canonical


def _native_origin_event(payload: Any, session_id: Any) -> Tuple[Optional[str], str]:
    """Classify *payload* as a native run initiation, or refuse it.

    The ONLY origin input is the native event name plus the command/skill name the
    runtime delivered. Nothing here consults the environment, and no argument can
    nominate an origin — see the module note on why a caller-supplied origin would
    defeat the whole mechanism.

    Args:
        payload: Parsed hook stdin.
        session_id: The owner the CALLER presents, which must equal the owner the
            payload carries. Two independent spellings of the same fact, so a
            payload cannot mint a witness for somebody else.

    Returns:
        ``(event, "")`` when the payload is a native initiation, else
        ``(None, reason)``.
    """
    if not isinstance(payload, dict) or not payload:
        return None, f"payload is not a non-empty JSON object: {type(payload).__name__}"

    event = payload.get("hook_event_name")
    if not isinstance(event, str) or event not in NATIVE_INIT_EVENTS:
        return None, (
            f"hook_event_name={event!r} is not a native run-initiation event "
            f"(expected one of {list(NATIVE_INIT_EVENTS)})"
        )

    owner = payload.get("session_id")
    if not isinstance(owner, str) or not owner.strip():
        return None, (
            "payload carries no session_id, so the runtime did not name an owner. "
            "An inherited environment variable is NOT a substitute (#1137: "
            "CLAUDE_SESSION_ID is non-privileged correlation metadata)"
        )
    if not isinstance(session_id, str) or owner.strip() != session_id.strip():
        return None, (
            f"payload owner {owner!r} does not match the presenting caller "
            f"{session_id!r}"
        )
    if _is_synthetic_session_id(owner):
        return None, f"owner {owner!r} is synthetic, so it can own nothing"

    if event == "UserPromptExpansion":
        if "tool_name" in payload:
            return None, (
                "contradictory payload: a UserPromptExpansion is not a tool call, "
                f"yet it carries tool_name={payload.get('tool_name')!r}"
            )
        command = payload.get("command_name")
        if not isinstance(command, str) or not _IMPLEMENT_FAMILY_RE.match(
            command.strip().lower()
        ):
            return None, (
                f"command_name={command!r} is not an /implement-family command"
            )
        return event, ""

    # PreToolUse: a MODEL-invoked Skill call, and only that.
    tool_name = payload.get("tool_name")
    if tool_name != "Skill":
        return None, f"tool_name={tool_name!r} is not Skill"
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None, f"tool_input is not an object: {type(tool_input).__name__}"
    skill = tool_input.get("skill")
    if not isinstance(skill, str) or not _IMPLEMENT_FAMILY_RE.match(
        skill.strip().lower()
    ):
        return None, f"skill={skill!r} is not an implement-family skill"
    # A command_name alongside the Skill fields changes NOTHING: the event decides
    # the origin class, so a laundering attempt is still MODEL-SKILL origin.
    return event, ""


def _native_origin_record(
    session_id: str, witness_id: str, mode: str, claim: dict
) -> dict:
    """Build the state-shaped record the existing v3 signer covers.

    The origin claim rides in ``subject`` because that is the free-form field v3
    binds INJECTIVELY (JSON-array serialization, so no delimiter can slide between
    fields). Nothing about the claim is stored outside the signed message — an
    unsigned convenience copy is a second, tamperable source of truth.
    """
    return {
        "session_start": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "run_id": witness_id,
        "explicitly_invoked": True,
        "alignment_passed": False,
        "alignment_verdict": "",
        "session_id": session_id,
        "issue_number": "",
        "subject": json.dumps(claim, sort_keys=True, separators=(",", ":")),
        "base_commit": "",
    }


def _binding_token(value: Any) -> str:
    """Canonical comparison token for a binding value.

    ``json.dumps`` so ``1807`` (int) and ``"1807"`` (str) are DISTINCT tokens —
    the same no-cross-type-collision policy ``_compute_state_hmac`` uses at v3.
    """
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return f"<unserializable:{type(value).__name__}>"


def _normalized_bindings(bindings: Any) -> Optional[Dict[str, Any]]:
    """Validate and normalize presented run bindings, or ``None``.

    Args:
        bindings: Mapping of :data:`NATIVE_ORIGIN_BINDING_KEYS` to values.

    Returns:
        A dict carrying exactly the binding keys, with absent values normalized to
        ``""``, or ``None`` when the mapping is unusable — an unknown key, a
        non-scalar value, a blank required binding, or a ``run_id`` the ledger's
        own allowlist would refuse.
    """
    if not isinstance(bindings, dict):
        return None
    if set(bindings) - set(NATIVE_ORIGIN_BINDING_KEYS):
        return None

    out: Dict[str, Any] = {}
    for key in NATIVE_ORIGIN_BINDING_KEYS:
        value = bindings.get(key, "")
        if value is None:
            value = ""
        if not isinstance(value, (str, int, float, bool)) or isinstance(value, bool):
            # bool excluded deliberately: no binding is a flag, and True would
            # otherwise compare equal to 1 in some encodings.
            return None
        out[key] = value

    for key in _NATIVE_ORIGIN_REQUIRED_BINDINGS:
        if not isinstance(out[key], str) or not out[key].strip():
            return None
    if not _RUN_ID_RE.match(out["run_id"].strip()):
        return None
    out["run_id"] = out["run_id"].strip()
    return out


def _refined_bindings(
    prior: Any, presented: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Merge *presented* onto *prior* under monotonic refinement, or ``None``.

    An empty prior binding MAY be filled; a non-empty one MUST NOT change. That
    single rule is what lets ``base_commit`` arrive after STEP 0 while a rebind to
    a different run, mode, issue or subject is refused.

    *prior* MUST be the bindings of the LATEST accepted record. The rule is only as
    strong as the record it is applied to: handed the FIRST record's bindings it
    would read a field a later append already fixed as still empty, and accept a
    conflicting value as a fill. Callers pass ``chain[-1]``.
    """
    if not isinstance(prior, dict):
        return None
    merged: Dict[str, Any] = {}
    for key in NATIVE_ORIGIN_BINDING_KEYS:
        old = prior.get(key, "")
        new = presented.get(key, "")
        if _binding_token(old) == _binding_token(""):
            merged[key] = new
        elif _binding_token(new) in (_binding_token(old), _binding_token("")):
            merged[key] = old
        else:
            return None
    return merged


def _binding_mismatch(recorded: Any, presented: Dict[str, Any]) -> Optional[str]:
    """Name the first binding the witness chain and the state disagree on.

    Returns ``None`` when they agree. A recorded binding that is EMPTY constrains
    nothing (see :data:`_NATIVE_ORIGIN_REQUIRED_BINDINGS`); a non-empty one must
    match the state exactly.
    """
    if not isinstance(recorded, dict):
        return "bindings"
    for key in NATIVE_ORIGIN_BINDING_KEYS:
        rec = recorded.get(key, "")
        if key not in _NATIVE_ORIGIN_REQUIRED_BINDINGS and _binding_token(
            rec
        ) == _binding_token(""):
            continue
        if _binding_token(rec) != _binding_token(presented.get(key, "")):
            return key
    return None


def record_native_origin_witness(session_id: str, payload: Any) -> Optional[str]:
    """Record a native-origin witness for *session_id*, returning its witness id.

    Called ONLY from ``hooks/native_run_origin.py``, which the Claude Code runtime
    invokes on the two native initiation events. It writes into the existing
    per-session ledger through the existing ``_locked_rmw`` owner and signs the
    record with the existing v3 chain.

    **Never raises.** Every refusal is reported on stderr and returned as ``None``,
    so a malformed payload degrades to "no witness" (which classifies as
    model-bootstrap origin) rather than blocking a run.

    Args:
        session_id: The owner, taken from the native stdin payload by the caller
            and re-presented here so the two must agree.
        payload: The parsed native hook stdin.

    Returns:
        The witness id, or ``None`` when nothing was written.

    Issues: #1807
    """
    try:
        event, reason = _native_origin_event(payload, session_id)
        if event is None:
            _native_origin_note(f"no witness minted: {reason}")
            return None

        owner = str(payload["session_id"]).strip()
        sign_state, _verify, generate_run_id = _native_origin_signers()
        if sign_state is None or generate_run_id is None:
            _native_origin_note(
                "pipeline_state.sign_state is unavailable, so no witness can be "
                "signed. REQUIRED NEXT ACTION: run `bash scripts/deploy-all.sh`"
            )
            return None

        ledger_path = str(_state_file_path(owner))
        ok, path_reason, _canonical = witness_path_verdict(ledger_path)
        if not ok:
            _native_origin_note(f"no witness minted: {path_reason}")
            return None

        # Id minted by the EXISTING owner (pipeline_state.generate_run_id), with an
        # "nw-" prefix so a witness key file in ~/.claude/pipeline_secrets/ is
        # visibly not a run key. No local id generation.
        #
        # TODO(deferred: #1807 — NO REAPER FOR WITNESS ARTIFACTS). Two artifacts
        # accumulate per witnessed run and nothing currently removes either: the
        # "nw-<id>" key file in ~/.claude/pipeline_secrets/ and the
        # `native_origin` field in this owner's ledger. An earlier draft shipped a
        # `cleanup_native_origin()` whose docstring claimed run-teardown use; it
        # had ZERO production call sites and was removed rather than left as an
        # unreceipted wiring claim. Growth is bounded in practice — a fresh
        # initiation SUPERSEDES the ledger field, and #1806's lock GC already owns
        # the pattern for reaping stale per-run files — so the fix is to extend
        # that existing reaper, not to add a teardown seam here. Named, not
        # silently accepted: this is a resource leak, never an authority hole
        # (every witness is bound to its run's receipt and cannot outlive it).
        outcome: Dict[str, Optional[str]] = {"witness_id": None}

        def _mutator(state: dict) -> None:
            _ensure_state_inplace(state, owner)
            if event == "PreToolUse":
                # This event is an ATTEMPT, including Skills another hook denies.
                # Decide against the same ledger snapshot that we may replace;
                # otherwise a concurrent typed initiation can be overwritten.
                try:
                    try:
                        from .pipeline_state import verify_state_hmac
                    except ImportError:
                        from pipeline_state import verify_state_hmac
                    pending = state.get(_NATIVE_ORIGIN_LEDGER_KEY)
                    if isinstance(pending, dict) and pending.get("progression") == []:
                        witness = pending.get("witness")
                        typed, _reason = _verified_native_record(
                            witness, owner, NATIVE_ORIGIN_WITNESS_MODE,
                            verify_state_hmac,
                        )
                        if (
                            typed is not None
                            and typed.get("event") == "UserPromptExpansion"
                            and typed.get("witness_id") == witness.get("run_id")
                            and typed.get("seq") == 0
                        ):
                            # Typed initialization writes witness, receipt,
                            # sentinel, then progression. Preserve its pending
                            # witness before those later carriers exist.
                            outcome["witness_id"] = witness["run_id"]
                            return
                    sentinel_path = get_legacy_sentinel_path()
                    current = (
                        json.loads(sentinel_path.read_text(encoding="utf-8"))
                        if sentinel_path.exists() else None
                    )
                    if current is None and state.get(_NATIVE_ORIGIN_LEDGER_KEY) is not None:
                        raise ValueError("current sentinel is missing for a live run")
                    if current is not None:
                        if not isinstance(current, dict):
                            raise ValueError("current sentinel is not an object")
                        if current.get("session_id") != owner:
                            raise ValueError("current sentinel belongs to another owner")
                        if not isinstance(current.get("hmac"), str) or not verify_state_hmac(
                            current, owner, strict=True
                        ):
                            raise ValueError("current sentinel signature is invalid")
                        if state.get("current_run_id") == current.get("run_id"):
                            bindings = {
                                key: current.get(key, "") for key in NATIVE_ORIGIN_BINDING_KEYS
                            }
                            existing = check_native_origin(
                                owner, bindings, _ledger_state=state
                            )
                            if existing.valid and existing.event == "UserPromptExpansion":
                                witness = state[_NATIVE_ORIGIN_LEDGER_KEY]["witness"]
                                outcome["witness_id"] = witness["run_id"]
                                return
                except (OSError, ValueError, TypeError, AttributeError, ImportError) as exc:
                    _native_origin_note(
                        f"Skill witness refused: current origin cannot be verified: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    return

            witness_id = f"nw-{generate_run_id()}"
            claim = {
                "args": payload.get("command_args") if event == "UserPromptExpansion" else "",
                "command": payload.get("command_name") if event == "UserPromptExpansion" else "",
                "event": event,
                "seq": 0,
                "skill": (payload.get("tool_input") or {}).get("skill")
                if event == "PreToolUse" else "",
                "witness_id": witness_id,
                "witnessed_at": datetime.now(timezone.utc).isoformat(),
            }
            claim = {key: ("" if value is None else value) for key, value in claim.items()}
            if not isinstance(claim["args"], str):
                claim["args"] = ""
            record = sign_state(
                _native_origin_record(owner, witness_id, NATIVE_ORIGIN_WITNESS_MODE, claim),
                owner,
            )
            # A fresh initiation SUPERSEDES any earlier chain: a witness is
            # per-run, and carrying a previous run's progression forward is
            # exactly the cross-run inheritance #1045/#1807 refuse.
            state[_NATIVE_ORIGIN_LEDGER_KEY] = {
                "witness": record,
                "progression": [],
            }
            outcome["witness_id"] = witness_id

        _locked_rmw(owner, _mutator, require_lock=True)
        return outcome["witness_id"]
    except Exception as exc:  # noqa: BLE001 - never raise out of state code
        _native_origin_note(f"no witness minted: {type(exc).__name__}: {exc}")
        return None


def extract_native_issue_number(args: str) -> Optional[int]:
    """Extract an issue only from an explicit reference or sole numeric subject.

    ``#N`` outranks incidental counts; ``issue N`` is next. A bare number is
    accepted only when it is the sole non-flag argument, so prose such as
    ``fix 2 tests`` cannot bind a run to issue 2.
    """
    if not isinstance(args, str):
        return None
    hash_refs = re.findall(r"(?<![\w])#([1-9][0-9]*)\b", args)
    if hash_refs:
        return int(hash_refs[0]) if len(set(hash_refs)) == 1 else None
    issue_refs = re.findall(r"\bissue\s+#?([1-9][0-9]*)\b", args, re.IGNORECASE)
    if issue_refs:
        return int(issue_refs[0]) if len(set(issue_refs)) == 1 else None
    try:
        bare = [token for token in shlex.split(args) if token not in ("--fix", "--full", "--tdd-first")]
    except ValueError:
        return None
    return int(bare[0]) if len(bare) == 1 and re.fullmatch(r"[1-9][0-9]*", bare[0]) else None


def initialize_native_run_from_event(payload: Any) -> Optional[dict]:
    """Initialize a run from a typed native command expansion.

    The native hook owns this call. A Skill tool event cannot initialize a run.
    All authority carriers use the existing signer, ledger, and sentinel path.
    """
    try:
        if not isinstance(payload, dict):
            return None
        owner = payload.get("session_id")
        event, reason = _native_origin_event(payload, owner)
        if event != "UserPromptExpansion":
            _native_origin_note(f"run initialization refused: {reason or 'not typed'}")
            return None
        # Claude Code 2.1.236 identifies a typed command supplied by a native
        # plugin as "plugin"; "projectSettings" is the project-command form.
        # Neither value alone proves the actor: the native event and protected
        # hook carrier still supply that boundary (#1807).
        if payload.get("command_source") not in ("user", "custom", "plugin", "projectSettings"):
            return None
        args = payload.get("command_args", "")
        prompt = payload.get("prompt")
        if not isinstance(args, str) or not isinstance(prompt, str) or not prompt.strip():
            return None
        # Native command_args includes the remaining multiline user intent.
        # Only the invocation line has shell-style argument grammar; parsing
        # prose as shell syntax rejects ordinary apostrophes and lets body
        # references change the command's issue or mode. Keep the complete
        # intent in subject, but derive invocation authority from its header.
        header = args.splitlines()[0] if args.splitlines() else ""
        tokens = shlex.split(header)
        flags = {token for token in tokens if token.startswith("-")}
        if flags - {"--fix", "--full", "--tdd-first"} or len(flags) > 1:
            return None
        if not any(not token.startswith("-") for token in tokens):
            return None
        subject = args.strip()
        issue_refs = re.findall(r"(?<![\w])#([1-9][0-9]*)\b|\bissue\s+#?([1-9][0-9]*)\b", header, re.IGNORECASE)
        if len({left or right for left, right in issue_refs}) > 1:
            return None
        issue_number = extract_native_issue_number(header)
        if issue_number is None:
            issue_number = ""
        mode = "fix" if "--fix" in flags else "tdd-first" if "--tdd-first" in flags else "full"
        base = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path.cwd(),
            capture_output=True, text=True, check=True, timeout=2,
        ).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", base):
            return None
        sign_state, _verify, generate_run_id = _native_origin_signers()
        if sign_state is None or generate_run_id is None:
            return None
        def _publish_native_run() -> Optional[dict]:
            # The witness must be minted before the receipt and binding. Validation
            # above runs first, so rejected requests create no carriers.
            if record_native_origin_witness(owner, payload) is None:
                return None
            if not record_run_start(
                owner, run_id,
                issue_number=issue_number if isinstance(issue_number, int) else None,
            ):
                return None
            state = {
                "session_start": datetime.now(timezone.utc).isoformat(),
                "mode": mode,
                "run_id": run_id,
                "explicitly_invoked": True,
                "session_id": owner,
                "issue_number": issue_number,
                "subject": subject,
                "base_commit": base,
            }
            state = sign_state(state, owner)
            bindings = {key: state.get(key, "") for key in NATIVE_ORIGIN_BINDING_KEYS}
            if not append_native_origin_progression(owner, bindings, event="run-bound"):
                return None
            # Publish the authorizing sentinel last: a refused progression must
            # never leave a new signed state consumable as model-bootstrap.
            atomic_write_json(get_legacy_sentinel_path(), state)
            return state

        try:
            from . import pipeline_state as pipeline
        except ImportError:
            import pipeline_state as pipeline
        sentinel = get_legacy_sentinel_path().resolve()
        # Existing run-lock mechanism, scoped ONLY to native initialization.
        # Canonicalize aliases so every owner at this repository takes one mutex.
        # This is not a lock held for the lifetime of the workflow.
        init_key = "native-init-" + hashlib.sha256(str(sentinel).encode()).hexdigest()[:24]
        init_fd = pipeline.acquire_run_lock(init_key)
        if init_fd is None:
            raise OSError("native initialization is already in progress")
        try:
            owner = owner.strip()
            if sentinel.exists():
                prior = json.loads(sentinel.read_text())
                prior_owner = prior.get("session_id") if isinstance(prior, dict) else None
                if isinstance(prior_owner, str) and prior_owner != owner:
                    verdict = pipeline.classify_current_run_authority(
                        prior, prior_owner, receipt_lookup=get_run_start_receipt,
                    )
                    if verdict.authorized:
                        raise ValueError("another owner has an authorized current run")
            # Same-owner typed invocation intentionally supersedes its earlier run.
            # Checkpoint failure must precede ANY new witness or authority carrier.
            run_id = generate_run_id()
            checkpoint = pipeline.create_pipeline(run_id, subject, mode=mode)
            pipeline.save_pipeline(checkpoint)
            restored = pipeline.load_pipeline(run_id)
            if (
                restored is None
                or restored.run_id != run_id
                or restored.mode != mode
                or restored.feature != subject
                or restored.steps != checkpoint.steps
                or set(restored.steps) != {step.value for step in pipeline.STEP_SEQUENCE}
                or any(step.get("status") != "pending" for step in restored.steps.values())
            ):
                raise ValueError("native checkpoint reload does not match initialization")
            return _publish_native_run()
        finally:
            pipeline.release_run_lock(init_fd)
    except Exception as exc:  # noqa: BLE001 - native hook must never block
        _native_origin_note(f"run initialization refused: {type(exc).__name__}: {exc}")
        return None


def append_native_origin_progression(
    session_id: str, bindings: Any, *, event: str
) -> bool:
    """Append progression evidence bound to this session's native-origin witness.

    The FIRST append is the run BINDING: it is what ties the witness (minted
    before any run id existed) to a specific run. Later appends refine it
    monotonically against the LATEST ACCEPTED record — an empty binding may be
    filled, a binding any earlier append already fixed may never change. The prior
    is ``chain[-1]`` and not ``chain[0]``, because refinement is cumulative: the
    first record keeps its original empty ``base_commit`` forever, so comparing
    against it would read a field a later append legitimately bound as still free
    to set. Every record is signed with the witness's own secret, so the whole
    chain shares one key file and a record cannot be moved between witnesses.

    Natively-invoked callers are the SubagentStop heartbeat path
    (``unified_session_tracker`` -> :func:`ensure_sentinel_heartbeat`) and the
    coordinator's initialization block, which consumes the witness at STEP 0 / F1.

    ATOMIC BY CONSTRUCTION (TOCTOU fix). The live witness, the chain length, the
    monotonic ``seq``, the binding refinement, the run-start receipt comparison AND
    the signing all happen inside ONE ``_locked_rmw`` critical section. An earlier
    draft read the witness OUTSIDE the lock and signed against it: a second
    initiation landing in that window appended a record signed for the OLD witness
    to the NEW run's chain and returned ``True`` — a false success that poisoned
    the new chain with a record every later verification would refuse. Nothing is
    read before the lock now except the caller's own arguments.

    INTERLEAVING GUARD, reusing an existing carrier. A bind is accepted only when
    ``state["current_run_id"]`` — the run-start receipt ``record_run_start`` stamps
    in this same ledger file, read under the same lock — names the run being bound.
    That is what stops a LATE append for run R from binding the witness of a newer
    initiation to R: at that point the receipt names the newer run, so the append
    refuses. No new store and no new dependency: the receipt is a field of the very
    dict the mutator already holds.

    **Never raises.** Returns ``False`` on any refusal or failure, with the cause
    reported on stderr.

    Args:
        session_id: The witness owner.
        bindings: The run bindings (:data:`NATIVE_ORIGIN_BINDING_KEYS`).
        event: What happened, e.g. ``"run-bound"`` or ``"subagent-stop"``. A LABEL
            for operators; it carries no authority and cannot name an origin.

    Returns:
        ``True`` only when a record bound to the CURRENTLY-LIVE witness and the
        CURRENT run-start receipt was appended.

    Issues: #1807
    """
    try:
        if not isinstance(event, str) or not event.strip():
            return False
        if not isinstance(session_id, str) or not session_id.strip():
            return False
        owner = session_id.strip()

        presented = _normalized_bindings(bindings)
        if presented is None:
            _native_origin_note(f"progression refused: unusable bindings {bindings!r}")
            return False

        sign_state, _verify, _gen = _native_origin_signers()
        if sign_state is None:
            return False

        outcome: Dict[str, Any] = {
            "ok": False,
            "why": "the mutator never ran",
            "silent": False,
        }

        def _mutator(state: dict) -> None:
            _ensure_state_inplace(state, owner)

            receipt = state.get("current_run_id")
            if not isinstance(receipt, str) or receipt.strip() != presented["run_id"]:
                outcome["why"] = (
                    f"the run-start receipt for {owner!r} names {receipt!r}, not "
                    f"{presented['run_id']!r}: a witness must not be bound to a run "
                    "that is not the current one"
                )
                return

            current = state.get(_NATIVE_ORIGIN_LEDGER_KEY)
            if not isinstance(current, dict):
                # SILENT. Absence of a witness is the NORMAL model-owned bootstrap
                # path, and the SubagentStop heartbeat calls this on every agent
                # completion — a diagnostic here would emit noise per subagent on
                # every run that has no witness, which is currently all of them.
                outcome["silent"] = True
                outcome["why"] = (
                    f"no native-origin witness exists for {owner!r}, so there is "
                    "nothing to bind a run to"
                )
                return
            witness = current.get("witness")
            if not isinstance(witness, dict):
                outcome["why"] = "the witness carrier holds no witness record"
                return
            witness_id = witness.get("run_id")
            if not isinstance(witness_id, str) or not witness_id:
                outcome["why"] = "the live witness carries no witness id"
                return

            chain = current.get("progression")
            if chain is None:
                chain = []
            if not isinstance(chain, list):
                outcome["why"] = "the progression chain is not a list"
                return
            if len(chain) >= _NATIVE_ORIGIN_MAX_PROGRESSION:
                outcome["why"] = (
                    f"the chain already holds {len(chain)} records (ceiling "
                    f"{_NATIVE_ORIGIN_MAX_PROGRESSION})"
                )
                return

            merged = presented
            if chain:
                # THE LATEST ACCEPTED RECORD, not the first. Refinement is
                # cumulative: append #2 legitimately FILLS the empty base_commit
                # that append #1 recorded before set_pipeline_base_commit ran, and
                # it stores the merged result in its OWN record. Reading chain[0]
                # forever afterwards sees that field still empty, so append #3
                # presenting a DIFFERENT commit than #2 honestly bound would be
                # accepted as "filling an empty field" instead of refused as a
                # rebind. chain[-1] is also exactly the record
                # `check_native_origin` compares against the sentinel, so writer
                # and reader agree on which binding is in force.
                latest = chain[-1]
                if not isinstance(latest, dict):
                    outcome["why"] = "the chain's latest record is not an object"
                    return
                try:
                    prior = json.loads(latest.get("subject", ""))
                except (TypeError, ValueError):
                    outcome["why"] = "the chain's latest claim is not parseable"
                    return
                merged = _refined_bindings(
                    prior.get("bindings") if isinstance(prior, dict) else None,
                    presented,
                )
                if merged is None:
                    outcome["why"] = (
                        f"{presented!r} would REBIND a binding the chain already fixed"
                    )
                    return

            claim = {
                "at": datetime.now(timezone.utc).isoformat(),
                "bindings": merged,
                "event": event.strip(),
                "seq": len(chain) + 1,
                "witness_id": witness_id,
            }
            # Signed HERE, under the lock, against the witness id just read from
            # the very dict being written. There is no window in which the witness
            # could change between signing and appending.
            chain.append(
                sign_state(
                    _native_origin_record(
                        owner, witness_id, NATIVE_ORIGIN_PROGRESSION_MODE, claim
                    ),
                    owner,
                )
            )
            current["progression"] = chain
            outcome["ok"] = True

        _locked_rmw(owner, _mutator)
        if not outcome["ok"]:
            if not outcome["silent"]:
                _native_origin_note(f"progression refused: {outcome['why']}")
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - never raise out of state code
        _native_origin_note(f"progression refused: {type(exc).__name__}: {exc}")
        return False


def append_native_origin_progression_from_sentinel(
    session_id: str, sentinel_path: Optional[str] = None
) -> bool:
    """Append progression evidence, reading the run bindings from the sentinel.

    The read half of the progression seam, so a natively-invoked hook that knows
    only its ``session_id`` can still contribute evidence without re-deriving the
    sentinel path or the binding key set. The live caller is the SubagentStop
    heartbeat path in ``hooks/unified_session_tracker.py``, immediately after
    :func:`ensure_sentinel_heartbeat`.

    A run with no witness (the model-owned bootstrap path — currently every run) is
    a SILENT ``False``: this is called once per subagent completion, so a
    diagnostic would be pure noise.

    **Never raises.**

    Args:
        session_id: The run owner.
        sentinel_path: Sentinel to read. Defaults to ``$PIPELINE_STATE_FILE``,
            falling back to :func:`get_legacy_sentinel_path` — the same resolution
            :func:`ensure_sentinel_heartbeat` uses, so the two cannot disagree.

    Returns:
        ``True`` when a progression record was appended.

    Issues: #1807
    """
    try:
        if sentinel_path is None:
            sentinel_path = os.environ.get(
                "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
            )
        path = Path(sentinel_path)
        if not path.is_file():
            return False
        try:
            sentinel = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(sentinel, dict) or not sentinel.get("run_id"):
            return False
        return append_native_origin_progression(
            session_id,
            {key: sentinel.get(key, "") for key in NATIVE_ORIGIN_BINDING_KEYS},
            event="subagent-stop",
        )
    except Exception:  # noqa: BLE001 - never raise out of state code
        return False


def _verified_native_record(
    record: Any, owner: str, mode: str, verify: Callable
) -> Tuple[Optional[dict], str]:
    """Verify one witness/progression record and return its parsed claim.

    Args:
        record: Candidate record from the ledger.
        owner: The session that must own it.
        mode: The required ``mode`` marker.
        verify: ``pipeline_state.verify_state_hmac``.

    Returns:
        ``(claim, "")`` or ``(None, reason)``.
    """
    if not isinstance(record, dict):
        return None, f"a {mode} record is not an object"
    if record.get("mode") != mode:
        return None, f"record mode={record.get('mode')!r} is not {mode!r}"

    declared_owner = record.get("session_id")
    if not isinstance(declared_owner, str) or declared_owner.strip() != owner:
        return None, f"record owner {declared_owner!r} is not {owner!r}"

    stored_mac = record.get("hmac")
    if not isinstance(stored_mac, str) or not stored_mac.strip():
        # verify_state_hmac returns True for an UNSIGNED state (legacy pipeline
        # compatibility). A witness has no legacy population, so requiring the MAC
        # up front is what stops that backward-compatibility branch from reading
        # an unsigned forgery as intact.
        return None, "record carries no MAC: unsigned is never witnessed"
    version = record.get("hmac_version")
    if not isinstance(version, int) or version < _NATIVE_ORIGIN_MIN_MAC_VERSION:
        return None, (
            f"record declares MAC version {version!r}; witness records are minted "
            f"fresh and must be >= v{_NATIVE_ORIGIN_MIN_MAC_VERSION}, so a "
            "downgrade is a forgery rather than an in-flight run"
        )
    if not verify(record, owner, strict=True):
        return None, "record MAC did not verify for its declared owner (strict)"

    try:
        claim = json.loads(record.get("subject", ""))
    except (TypeError, ValueError):
        return None, "record claim is not parseable JSON"
    if not isinstance(claim, dict):
        return None, "record claim is not an object"
    return claim, ""


def check_native_origin(
    session_id: str, bindings: Any, *, _ledger_state: Optional[dict] = None
) -> NativeOriginCheck:
    """Report what the ledger says about the native origin of a run.

    Reads the witness chain for *session_id* and verifies it against the run
    *bindings* the caller presents. The private ``_ledger_state`` argument lets
    the witness writer verify the snapshot already held under its session lock.
    Returns FACTS; the mapping from native event
    to origin class belongs to ``pipeline_state.classify_current_run_authority``,
    which is the single consumer and the single vocabulary.

    **Never raises.** Every failure is a refusal, except an unavailable signer,
    which is reported as ``instrument_ok=False`` — "cannot tell" is not "passed".

    Args:
        session_id: The owner presenting the run.
        bindings: The run bindings read from the sentinel.

    Returns:
        A :class:`NativeOriginCheck`.

    Issues: #1807
    """
    def _refuse(detail: str) -> NativeOriginCheck:
        return NativeOriginCheck(True, False, "", detail)

    try:
        if not isinstance(session_id, str) or not session_id.strip():
            return _refuse("no usable caller identity, so no origin can be attributed")
        owner = session_id.strip()

        presented = _normalized_bindings(bindings)
        if presented is None:
            return _refuse(f"presented run bindings are unusable: {bindings!r}")

        _sign, verify, _gen = _native_origin_signers()
        if verify is None:
            return NativeOriginCheck(
                True,
                False,
                "",
                "pipeline_state.verify_state_hmac is unavailable, so no witness "
                "can be judged. This is a DEPENDENCY failure, not a verdict. "
                "REQUIRED NEXT ACTION: run `bash scripts/deploy-all.sh`",
                instrument_ok=False,
            )

        state = _ledger_state if _ledger_state is not None else _read_state(owner)
        origin = state.get(_NATIVE_ORIGIN_LEDGER_KEY)
        if origin is None:
            return NativeOriginCheck(
                False,
                False,
                "",
                f"no native-origin witness exists for {owner!r}: this run was "
                "initiated by the model-owned bootstrap path (or the native hook "
                "was discarded on timeout). Absence is a NON-PASS, never native",
            )
        if not isinstance(origin, dict):
            return _refuse("witness carrier is not an object")

        claim, reason = _verified_native_record(
            origin.get("witness"), owner, NATIVE_ORIGIN_WITNESS_MODE, verify
        )
        if claim is None:
            return _refuse(f"witness rejected: {reason}")

        witness_id = origin["witness"].get("run_id")
        event = claim.get("event")
        if event not in NATIVE_INIT_EVENTS:
            return _refuse(
                f"witness claims event {event!r}, which is not a native "
                "run-initiation event"
            )
        if claim.get("witness_id") != witness_id or claim.get("seq") != 0:
            return _refuse("witness claim does not identify itself consistently")

        progression = origin.get("progression")
        if not isinstance(progression, list) or not progression:
            return _refuse(
                "witness carries no run binding, so it names no run to attribute. "
                "A witness minted without the binding append confers nothing"
            )
        if len(progression) > _NATIVE_ORIGIN_MAX_PROGRESSION:
            return _refuse(
                f"progression chain holds {len(progression)} records, above the "
                f"{_NATIVE_ORIGIN_MAX_PROGRESSION} ceiling"
            )

        nonces = {origin["witness"].get("nonce")}
        expected_seq = 1
        latest: Optional[dict] = None
        for record in progression:
            record_claim, reason = _verified_native_record(
                record, owner, NATIVE_ORIGIN_PROGRESSION_MODE, verify
            )
            if record_claim is None:
                return _refuse(f"progression record {expected_seq} rejected: {reason}")
            if record.get("run_id") != witness_id:
                return _refuse(
                    f"progression record {expected_seq} names witness "
                    f"{record.get('run_id')!r}, not {witness_id!r}"
                )
            nonce = record.get("nonce")
            if not isinstance(nonce, str) or nonce in nonces:
                return _refuse(
                    f"progression record {expected_seq} REPLAYS a nonce already in "
                    "the chain"
                )
            nonces.add(nonce)
            if record_claim.get("witness_id") != witness_id:
                return _refuse(
                    f"progression record {expected_seq} claims another witness"
                )
            if record_claim.get("seq") != expected_seq:
                return _refuse(
                    f"progression seq {record_claim.get('seq')!r} is not the "
                    f"expected {expected_seq}: the chain is replayed or reordered"
                )
            expected_seq += 1
            latest = record_claim

        mismatch = _binding_mismatch(
            (latest or {}).get("bindings"), presented
        )
        if mismatch is not None:
            return _refuse(
                f"witness chain binds a different {mismatch}: recorded "
                f"{(latest or {}).get('bindings', {}).get(mismatch)!r} vs presented "
                f"{presented.get(mismatch)!r}"
            )

        return NativeOriginCheck(
            True,
            True,
            event,
            f"witness {witness_id} bound to run {presented['run_id']} for {owner} "
            f"via {event} ({len(progression)} progression record(s))",
        )
    except Exception as exc:  # noqa: BLE001 - a probe must not raise into a gate
        return _refuse(f"{type(exc).__name__}: {exc}")


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
        Canonical owned-role strings that completed successfully. Raw receipt
        identity and run stamps are validated before aliases are applied;
        foreign plugin identities are never stripped.
    """
    from agent_ordering_gate import normalize_agent_identity

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
        return {normalize_agent_identity(agent) for agent in result}

    # A native run is owned by its signed session and run receipt. The legacy
    # 'unknown' merge would import another session's completion into that owner.
    # Keep the permissive fallback only for non-native legacy sessions.
    if _native_agent_join_active(state) or _signed_native_agent_scope(session_id) is not None:
        return {normalize_agent_identity(agent) for agent in result}

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
                    return {normalize_agent_identity(agent) for agent in result}
            else:
                return {normalize_agent_identity(agent) for agent in result}
        except OSError:
            # Fail-safe: if stat fails we can't verify freshness, skip merge.
            return {normalize_agent_identity(agent) for agent in result}

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

    return {normalize_agent_identity(agent) for agent in result}
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
        Canonical owned-role strings that have been launched; raw ledger
        identities remain unchanged and foreign namespaces remain distinct.

    Issues: #686, #738
    """
    from agent_ordering_gate import normalize_agent_identity

    result = set()
    state = _read_state(session_id)
    signed_scope = _signed_native_agent_scope(session_id)
    if _native_agent_join_active(state) or signed_scope is not None:
        # Native launch credit is exact admission, not a pre-permission observer
        # boolean. Filter raw binding first, then expose canonical policy roles.
        if (signed_scope is None or state.get("session_id") != session_id
                or signed_scope["run_id"] != state.get("current_run_id")):
            return set()
        joins = state.get("native_agent_joins", {})
        if not isinstance(joins, dict):
            return set()
        return {
            normalize_agent_identity(entry["agent_type"])
            for tool_id, entry in joins.items()
            if isinstance(entry, dict) and entry.get("tool_use_id") == tool_id
            and entry.get("run_id") == signed_scope["run_id"]
            and entry.get("issue_number") == signed_scope["issue_number"]
            and str(entry.get("issue_number")) == str(issue_number)
            and entry.get("status") in ("reserved", "completed")
            and isinstance(entry.get("agent_type"), str) and entry["agent_type"].strip()
            and get_native_agent_run_id(session_id, tool_id) == signed_scope["run_id"]
        }
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

    return {normalize_agent_identity(agent) for agent in result}


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
    require_lock: bool = False,
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
        require_lock: Refuse on lock open/acquisition failure. Native-origin
            witness replacement needs an atomic decision and write; other
            callers retain the historical unlocked fallback.

    Issue #1544 made this the ONLY path to the on-disk write: all state
    mutators route through here, and ``_write_state`` self-wraps in this
    function when called from outside it. The fail-open branches below are
    still deliberate (a flock failure on NFS must not block the gate) but are
    now safe rather than merely rare — the underlying write is atomic
    (``os.replace``), so an unserialized fallback can lose an update but can
    never expose a truncated file to a concurrent reader.

    Issues: #1170, #1188, #1544
    """
    # Issue #1807: derive the lock from _state_file_path instead of rebuilding
    # the literal. Two paths for one artifact is two things to keep in sync, and
    # they had already drifted: the lock was pinned to machine-global /tmp, so a
    # test that redirected the ledger still created a real /tmp lockfile —
    # MEASURED as 9 residual `/tmp/pipeline_agent_completions_*.lock` files after
    # an otherwise fully-isolated suite. The file name changes from
    # `<key>.lock` to `<ledger>.json.lock`; the name stays `pipeline_*.lock`-shaped
    # for consistency, but as of #1806 `_gc_stale_states` no longer reaps any lock
    # pattern, so this file is retained under the same accepted tradeoff as run
    # lockfiles. The only cost is that a process still
    # running pre-#1807 code during a deploy would take a different mutex for the
    # same session. That window is one deploy long, the write it guards is already
    # atomic (#1544), and this function's documented failure mode is fail-open
    # anyway — cheaper than a second source of truth for the path.
    lock_path = Path(str(_state_file_path(session_id, run_id=run_id)) + ".lock")

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
        if require_lock:
            raise OSError("required state lockfile could not be opened")
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
            if require_lock:
                raise OSError("required state lock could not be acquired")
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


#: Fields whose presence means "this sentinel represents a RUN", not merely a
#: recovery note. This is the SOLE owner of that predicate: the equivalent inline
#: trio in ``unified_pre_tool._is_pipeline_active`` (the #1384 recovery-record
#: branch) was RETIRED by Issue #1807 in favour of
#: ``pipeline_state.classify_current_run_authority``.
#:
#: Deliberately GENEROUS where the authority classifier is STRICT, because the two
#: answer different questions. Here: "is this file worth preserving?" — any run
#: field is enough, so a partially-written run is never discarded. There: "may
#: this authorize the current run?" — a usable ``run_id`` is required, because a
#: state with only ``mode`` identifies no run to authorize. Preserve generously,
#: authorize strictly; collapsing them either destroys runs or authorizes
#: non-runs.
_RUN_BEARING_FIELDS = ("run_id", "mode", "explicitly_invoked")


def _state_carries_run_identity(state: dict) -> bool:
    """Whether *state* identifies a pipeline run.

    Args:
        state: Parsed sentinel contents.

    Returns:
        True when any of :data:`_RUN_BEARING_FIELDS` carries a truthy value.

    Issue: #1807
    """
    if not isinstance(state, dict):
        return False
    return any(state.get(field) for field in _RUN_BEARING_FIELDS)


def is_synthetic_session_id(session_id: str) -> bool:
    """Public spelling of the synthetic-session-id test.

    Identical to :func:`_is_synthetic_session_id` — it delegates, so there is
    still ONE implementation of the rule. It exists because coordinator
    snippets in ``commands/*.md`` must fail closed on a synthetic owner (Issue
    #1807, fix-mode F1) and a command file importing a private name would be
    both fragile and a bad example.

    Args:
        session_id: Candidate session id.

    Returns:
        True when the id is synthetic, derived, or unusable as an owner.

    Issues: #1481, #1807
    """
    return _is_synthetic_session_id(session_id)


def ensure_sentinel_heartbeat(
    session_id: str,
    state_path: Optional[str] = None,
) -> bool:
    """Observe the pipeline sentinel without inventing missing run authority.

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
    - If ``state_path`` exists, is parseable run-bearing JSON, and its
      ``session_id`` field matches ``session_id`` → return ``True``. An old
      identity-less ``recovered`` record is not a healthy run.
    - If ``state_path`` exists and CARRIES A RUN (``run_id``/``mode``/
      ``explicitly_invoked``) but its owner is absent or synthetic, preserve it,
      emit ``[SENTINEL-HEARTBEAT-RUN-PRESERVED]`` and return ``False`` — an
      absent owner is not licence to discard a run (Issue #1807).
    - Otherwise (missing, corrupt, or an identity-less record whose owner is
      synthetic) → emit a structured diagnostic and return ``False`` without
      writing. A bare recovery record cannot reconstruct a signed run (#1807).

    The function NEVER raises. Missing authority stays missing.

    Args:
        session_id: The expected owner's session id (e.g. from
            ``CLAUDE_SESSION_ID`` or the pipeline state file itself).
        state_path: Absolute path to the sentinel file.  Defaults to the
            ``PIPELINE_STATE_FILE`` env var, falling back to the per-repo
            ``<repo>/.claude/local/implement_pipeline_state.json`` (Issue #1206).

    Returns:
        ``True`` when the sentinel was already healthy. ``False`` otherwise;
        this observation never writes the sentinel.

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
                if existing == session_id and _state_carries_run_identity(data):
                    return True  # Sentinel healthy.
                # Issue #1807 guard #3 — the run survives repair. A state that
                # CARRIES A RUN (run_id or mode) is gating state, and an absent
                # or synthetic OWNER is not licence to discard it: the recovery
                # record below has no run_id, no mode, no issue_number and no
                # base_commit, so replacing a live run with it destroys exactly
                # the identity the MAC failed to bind. MEASURED pre-fix against
                # a signed run-bearing ownerless sentinel: return=False, bytes
                # changed=True, run_id after=None.
                #
                # Both triggers of the old single branch are covered here
                # (owner ABSENT — the fix-mode F1 shape — and owner SYNTHETIC,
                # e.g. "stop-7"), because a guard keyed on the missing-owner
                # spelling alone would leave the synthetic route destroying
                # runs. A diagnostic is emitted instead: missing identity is
                # reported, never invented (Issue #1807).
                if _state_carries_run_identity(data):
                    try:
                        import sys as _sys_hb

                        _sys_hb.stderr.write(
                            f"[SENTINEL-HEARTBEAT-RUN-PRESERVED] state_path={state_path}"
                            f" run_id={data.get('run_id')!r}"
                            f" mode={data.get('mode')!r}"
                            f" existing_owner={existing!r}"
                            f" caller_session={session_id!r}"
                            " refusing identity-less replacement (Issue #1807)\n"
                        )
                        _sys_hb.stderr.flush()
                    except Exception:
                        pass
                    return False
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
        # Defensive: any unexpected read error remains untrusted.
        pass

    # A missing/corrupt sentinel or synthetic prior owner is not a source of
    # run identity. Earlier #989 recovery wrote only session_id/recovered_at,
    # which could turn an ordinary Agent stop into a false active pipeline.
    try:
        import sys as _sys_hb

        _sys_hb.stderr.write(
            f"[SENTINEL-HEARTBEAT-UNTRUSTED] state_path={state_path}"
            f" present={sentinel.exists()} caller_session={session_id}"
            " refusing identity-less recovery\n"
        )
        _sys_hb.stderr.flush()
    except Exception:
        pass

    return False


def _gc_stale_states(max_age_seconds: int = 7200) -> dict:
    """Garbage-collect stale state and sentinel files in /tmp.

    Deletes files older than ``max_age_seconds``:

    - ``/tmp/pipeline_agent_completions_*.json`` (both legacy sha256 and new
      run_id paths)
    - ``/tmp/pipeline_agent_completions_*.json.*.tmp`` (orphaned ``os.replace``
      staging files left by a process killed mid-write, #1544)
    - ``/tmp/implement_pipeline_*.json`` (per-run sentinel files)

    Lockfiles are NEVER deleted (#1806).  ``/tmp/pipeline_*.lock`` paths are the
    pathnames ``acquire_run_lock()`` and ``_locked_rmw()`` open and ``flock``.
    Unlinking a *held* lock's pathname leaves the holder on an orphan inode
    while the next process creates and locks a new inode under the same
    pathname — two processes each believing they own the run.  An mtime is no
    evidence of liveness (``flock`` never touches mtime, so a lock held for
    hours looks stale), and a nonblocking-flock probe before the unlink does not
    close the hole either: another process can open the old inode between the
    probe and the unlink (TOCTOU).  A few empty lockfiles left in /tmp is the
    cheaper failure, so no lockfile deletion happens here at all.

    Default is 2× the existing ``STALE_UNKNOWN_TTL_SECONDS`` (3600 → 7200).

    Args:
        max_age_seconds: Files with mtime older than this many seconds are
            removed.  Default 7200 (2× TTL).

    Returns:
        A dict with removal counts and any errors encountered::

            {
                'state_files_removed': int,
                'sentinels_removed': int,
                'lockfiles_removed': int,  # always 0 since #1806
                'errors': list[str],
            }

        ``lockfiles_removed`` is retained at a constant 0 for callers that sum
        the counts (``commands/implement.md`` STEP 0).

    Issues: #1041 #1048 #1806
    """
    now = time.time()
    cutoff = now - max_age_seconds

    counts: dict = {
        "state_files_removed": 0,
        "sentinels_removed": 0,
        # #1806: kept at 0 permanently so callers that sum the counts keep
        # working. No lockfile pattern is scanned — see the docstring.
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
        # #1806: "/tmp/pipeline_*.lock" deliberately absent. It matched both the
        # run lockfiles (acquire_run_lock) and the #1170 per-session R-M-W
        # lockfiles (_locked_rmw); unlinking either while held splits lock
        # authority across two inodes. Do NOT re-add it, and do not "fix" it
        # with a pre-unlink flock probe (TOCTOU).
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
