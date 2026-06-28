"""Cross-machine claim mutex for /implement vs /drain-queue.

Issue: race condition observed 2026-06-28 where local /implement --issues
and cloud-drain /drain-queue → /implement --issues processed the same
cluster in parallel. The pre-existing local-filesystem sentinel does not
cross machine boundaries; GH Issue label + claim comment do.

The mutex is best-effort and graceful: any gh failure degrades to "not
claimed" so the pipeline never deadlocks on transient network issues.
Stale claims (> CLAIM_MAX_AGE_HOURS) are ignored inline; no separate
reaper is required.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

CLAIM_LABEL = "in-progress"
CLAIM_MAX_AGE_HOURS = 4
GH_TIMEOUT_SECONDS = 10

# Match the FIRST line of a claim comment body.
CLAIM_COMMENT_RE = re.compile(
    r"^🤖 Implementing #(?P<n>\d+) now \[host=(?P<host>[^,\]]+), pid=(?P<pid>\d+), ts=(?P<ts>[^\]]+)\]"
)
RELEASE_COMMENT_PREFIX = "🤖 Released #"


def _actor_string(run_id: str, *, host: Optional[str] = None, pid: Optional[int] = None) -> str:
    """Build the canonical actor string used for claim attribution.

    Args:
        run_id: Pipeline run identifier (e.g. BATCH_ID).
        host: Optional override for hostname (defaults to socket.gethostname()).
        pid: Optional override for PID (defaults to os.getpid()).

    Returns:
        "host:pid:run_id" string.
    """
    host = host or socket.gethostname()
    pid = pid if pid is not None else os.getpid()
    return f"{host}:{pid}:{run_id}"


def _format_claim_comment(issue_number: int, actor: str, ts: Optional[str] = None) -> str:
    """Format a claim comment body for posting to a GH issue.

    Args:
        issue_number: Target issue number.
        actor: "host:pid:run_id" string.
        ts: Optional ISO-8601 timestamp override (defaults to now UTC).

    Returns:
        Multi-line comment body. First line matches CLAIM_COMMENT_RE.
    """
    parts = actor.split(":", 2)
    host = parts[0] if len(parts) >= 1 else "unknown"
    pid = parts[1] if len(parts) >= 2 else "0"
    ts = ts or datetime.now(timezone.utc).isoformat()
    return f"🤖 Implementing #{issue_number} now [host={host}, pid={pid}, ts={ts}]\n\nActor: {actor}"


def _format_release_comment(
    issue_number: int, actor: str, reason: str, ts: Optional[str] = None
) -> str:
    """Format a release marker comment body.

    Args:
        issue_number: Target issue number.
        actor: "host:pid:run_id" string.
        reason: Short reason (e.g. "completed", "failed").
        ts: Optional ISO-8601 timestamp override (defaults to now UTC).

    Returns:
        Single-line comment body prefixed with RELEASE_COMMENT_PREFIX.
    """
    ts = ts or datetime.now(timezone.utc).isoformat()
    return f"🤖 Released #{issue_number} [actor={actor}, reason={reason}, ts={ts}]"


def _parse_claim_comment(body: str) -> Optional[dict]:
    """Parse the canonical claim comment first line.

    Args:
        body: Full comment body (multi-line OK; only the first line is parsed).

    Returns:
        Dict with keys: 'issue' (int), 'host' (str), 'pid' (int),
        'ts' (datetime UTC). Returns None for any non-claim comment,
        including release markers or malformed timestamps.
    """
    if not body:
        return None
    first_line = body.split("\n", 1)[0]
    m = CLAIM_COMMENT_RE.match(first_line)
    if not m:
        return None
    try:
        ts_dt = datetime.fromisoformat(m.group("ts").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return {
        "issue": int(m.group("n")),
        "host": m.group("host"),
        "pid": int(m.group("pid")),
        "ts": ts_dt if ts_dt.tzinfo else ts_dt.replace(tzinfo=timezone.utc),
    }


def _gh_run(args, *, timeout: int = GH_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Thin wrapper around `gh <args>`. Never raises.

    Args:
        args: Argument list passed after the `gh` executable.
        timeout: Subprocess timeout in seconds.

    Returns:
        CompletedProcess. On TimeoutExpired returncode=124 (matches `timeout`
        utility convention). On FileNotFoundError / OSError returncode=127.
    """
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["gh", *args], returncode=124, stdout="", stderr="timeout"
        )
    except (FileNotFoundError, OSError) as e:
        return subprocess.CompletedProcess(
            args=["gh", *args], returncode=127, stdout="", stderr=str(e)
        )


def is_claimed(
    issue_number: int,
    *,
    actor: Optional[str] = None,
    max_age_hours: float = CLAIM_MAX_AGE_HOURS,
    now: Optional[datetime] = None,
) -> Tuple[bool, Optional[dict]]:
    """Check whether an issue is currently claimed by a different actor.

    Args:
        issue_number: GH issue number to check.
        actor: Optional actor string for the caller. If the latest claim was
            made by this actor (host:pid prefix match), the result is False —
            self-claims do not block.
        max_age_hours: Claim age beyond which the claim is considered stale.
        now: Optional override for "now" (UTC). Defaults to datetime.now(UTC).

    Returns:
        (True, info) iff the issue has CLAIM_LABEL AND a fresh claim comment
        from a DIFFERENT actor. info dict has keys: host, pid, ts, actor,
        age_seconds.
        (False, None) otherwise (no label, no claim, self-claim, stale, or
        released after claim).
    """
    now = now or datetime.now(timezone.utc)
    proc = _gh_run(["issue", "view", str(issue_number), "--json", "labels,comments"])
    if proc.returncode != 0:
        return (False, None)
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return (False, None)

    label_names = {(label.get("name") or "").lower() for label in data.get("labels", [])}
    if CLAIM_LABEL.lower() not in label_names:
        return (False, None)

    # Walk comments to find the latest claim marker and latest release marker.
    # If a release comment appears AFTER the claim (later createdAt), the
    # claim is considered released.
    comments = data.get("comments", []) or []
    latest_claim = None
    latest_claim_ts = None
    latest_release_ts = None
    for c in comments:
        body = c.get("body", "") or ""
        c_ts_raw = c.get("createdAt") or ""
        try:
            c_ts = datetime.fromisoformat(c_ts_raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if body.startswith(RELEASE_COMMENT_PREFIX):
            if latest_release_ts is None or c_ts > latest_release_ts:
                latest_release_ts = c_ts
            continue
        parsed = _parse_claim_comment(body)
        if parsed and parsed["issue"] == issue_number:
            if latest_claim_ts is None or c_ts > latest_claim_ts:
                latest_claim = parsed
                latest_claim_ts = c_ts

    if not latest_claim:
        return (False, None)

    # Released after claimed -> not held.
    if latest_release_ts and latest_claim_ts and latest_release_ts > latest_claim_ts:
        return (False, None)

    age = now - latest_claim["ts"]
    if age > timedelta(hours=max_age_hours):
        return (False, None)  # stale

    parsed_actor = f"{latest_claim['host']}:{latest_claim['pid']}"
    if actor and actor.startswith(parsed_actor + ":"):
        return (False, None)  # self
    if actor and actor == parsed_actor:
        return (False, None)  # self (no run_id part)

    info = {
        "host": latest_claim["host"],
        "pid": latest_claim["pid"],
        "ts": latest_claim["ts"].isoformat(),
        "actor": parsed_actor,
        "age_seconds": int(age.total_seconds()),
    }
    return (True, info)


def claim_issue(issue_number: int, actor: str) -> bool:
    """Acquire a claim on an issue: post comment first, then add label.

    Args:
        issue_number: GH issue number to claim.
        actor: "host:pid:run_id" actor string (typically from _actor_string).

    Returns:
        True iff BOTH the comment post and label add succeeded.
    """
    body = _format_claim_comment(issue_number, actor)
    c_proc = _gh_run(["issue", "comment", str(issue_number), "--body", body])
    if c_proc.returncode != 0:
        logger.warning(f"claim_issue: comment failed for #{issue_number}: {c_proc.stderr}")
        return False
    l_proc = _gh_run(["issue", "edit", str(issue_number), "--add-label", CLAIM_LABEL])
    if l_proc.returncode != 0:
        logger.warning(f"claim_issue: label add failed for #{issue_number}: {l_proc.stderr}")
        return False
    return True


def release_issue(issue_number: int, actor: str, *, reason: str = "completed") -> bool:
    """Release a claim: remove label first, then post release comment.

    Args:
        issue_number: GH issue number to release.
        actor: "host:pid:run_id" actor string (typically from _actor_string).
        reason: Short reason recorded in the release marker comment.

    Returns:
        True iff BOTH the label remove and release comment post succeeded.
        Best-effort: callers should not fail the pipeline on a False return.
    """
    l_proc = _gh_run(["issue", "edit", str(issue_number), "--remove-label", CLAIM_LABEL])
    label_ok = l_proc.returncode == 0
    body = _format_release_comment(issue_number, actor, reason)
    c_proc = _gh_run(["issue", "comment", str(issue_number), "--body", body])
    comment_ok = c_proc.returncode == 0
    return label_ok and comment_ok
