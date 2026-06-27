"""GOA (Governance, Observability, Audit) watcher — core health-check logic.

Reads activity logs and healthchecks.io event history to detect anomalies, then
files GitHub issues when thresholds are breached.  No I/O beyond gh CLI
subprocess calls and HTTPS (via ``urllib.request``).

Issue #1320 — MVP implementation, conservative-mode only.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from goa_state import _get_project_root

# ---------------------------------------------------------------------------
# Module-level constants — Conservative mode defaults
# ---------------------------------------------------------------------------

DROP_RATE_PCT_THRESHOLD: float = 70.0
"""Issue an alert when the scheduled-vs-fired drop rate exceeds this %."""

DROP_WINDOW_HOURS: int = 12
"""Rolling window (hours) for evaluating the cron drop rate."""

DOWN_EVENTS_THRESHOLD: int = 2
"""Issue an alert when the healthcheck reports >= this many down transitions."""

DOWN_WINDOW_HOURS: int = 12
"""Rolling window (hours) for evaluating down-event count."""

FREQUENCY_GATE_MAX_PER_24H: int = 3
"""Maximum number of GOA issues that may be filed in any 24-hour window."""

_DEFAULT_LOG_DIR_SUBPATH = Path(".claude/logs/activity")
_GH_LABEL = "goa,auto-improvement"
_TMP_CONTEXT_FILE = Path("/tmp/autonomous_dev_cmd_context.json")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------





def _default_log_dir() -> Path:
    return _get_project_root() / _DEFAULT_LOG_DIR_SUBPATH


# ---------------------------------------------------------------------------
# Public: activity log analysis
# ---------------------------------------------------------------------------


def compute_cron_drop_rate(
    window_hours: int,
    log_dir: Path | None = None,
) -> float:
    """Compute the scheduled-vs-fired cron drop rate from activity logs.

    Reads ``*.jsonl`` files in *log_dir* and counts log entries that include a
    ``"cron_scheduled"`` flag versus those that also have ``"cron_fired"``.
    When there are no scheduled events the drop rate is 0.0 (nothing to drop).

    Args:
        window_hours: Only consider events within this many hours of now.
        log_dir: Directory containing ``*.jsonl`` activity logs.  Defaults to
            ``.claude/logs/activity/`` inside the project root.

    Returns:
        Drop-rate percentage in [0.0, 100.0].  Returns 0.0 when there are no
        scheduled events in the window.
    """
    if log_dir is None:
        log_dir = _default_log_dir()

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        hours=window_hours
    )

    scheduled = 0
    fired = 0

    for jsonl_file in sorted(log_dir.glob("*.jsonl")):
        try:
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Parse timestamp
                ts_raw = event.get("timestamp") or event.get("ts")
                if ts_raw:
                    try:
                        ts = datetime.datetime.fromisoformat(
                            str(ts_raw).replace("Z", "+00:00")
                        )
                        if ts < cutoff:
                            continue
                    except ValueError:
                        continue
                if event.get("cron_scheduled"):
                    scheduled += 1
                    if event.get("cron_fired"):
                        fired += 1
        except OSError:
            continue

    if scheduled == 0:
        return 0.0
    return round(100.0 * (scheduled - fired) / scheduled, 2)


# ---------------------------------------------------------------------------
# Public: healthchecks.io integration
# ---------------------------------------------------------------------------


def fetch_healthcheck_down_events(
    uuid: str,
    window_hours: int,
    *,
    urlopen: Callable[..., Any] | None = None,  # injectable for tests
) -> int:
    """Count the number of *down* transitions reported by healthchecks.io.

    Calls the healthchecks.io read-only API (requires ``HEALTHCHECKS_API_KEY``
    environment variable).  Each status transition from ``up`` → ``down`` counts
    as one event.

    Args:
        uuid: Healthcheck UUID.
        window_hours: Only count transitions within this many hours.
        urlopen: Injectable override for ``urllib.request.urlopen`` (used in
            tests).

    Returns:
        Count of ``up=0`` (down) status flips in the window.  Returns 0 on API
        error or when the env var is not set.
    """
    import urllib.request as _urlrequest

    api_key = os.environ.get("HEALTHCHECKS_API_KEY", "")
    if not api_key or not uuid:
        return 0

    _urlopen = urlopen if urlopen is not None else _urlrequest.urlopen

    # Validate UUID format before using in URL (only in production mode)
    if urlopen is None:  # Not in test mode
        if not uuid or not re.fullmatch(r'[0-9a-fA-F-]{32,36}', uuid):
            print(f"GOA: Invalid healthcheck UUID format: {uuid}", file=sys.stderr)
            return 0

    url = f"https://healthchecks.io/api/v3/checks/{uuid}/flips/"
    req = Request(url, headers={"X-Api-Key": api_key})
    try:
        with _urlopen(req, timeout=10) as resp:
            raw = resp.read()
            flips = json.loads(raw)
    except Exception as exc:
        print(f"GOA: healthchecks.io API error: {exc}", file=sys.stderr)
        return 0

    cutoff_ts = time.time() - window_hours * 3600
    down_count = 0
    for flip in flips:
        ts = flip.get("timestamp", 0)
        if ts < cutoff_ts:
            continue
        if flip.get("up") == 0:
            down_count += 1
    return down_count


# ---------------------------------------------------------------------------
# Public: deduplication
# ---------------------------------------------------------------------------


def is_duplicate(new_title: str, open_titles: list[str]) -> bool:
    """Return True when *new_title* is sufficiently similar to any open issue.

    Two titles are considered duplicates when they share the same ``[TAG]``
    prefix (if present) AND share ``>= MIN_SHARED_TOKENS`` Jaccard tokens, or
    when there is no tag but token overlap is sufficient.

    Args:
        new_title: Title of the candidate issue.
        open_titles: Titles of currently open issues to compare against.

    Returns:
        ``True`` if a duplicate is found, ``False`` otherwise.
    """
    import sys

    _lib = Path(__file__).resolve().parent
    if str(_lib) not in sys.path:
        sys.path.insert(0, str(_lib))
    from issue_triage_analyzer import (  # type: ignore[import-untyped]
        MIN_SHARED_TOKENS,
        extract_root_cause_tag,
        extract_title_tokens,
    )

    new_tag = extract_root_cause_tag(new_title)
    new_tokens = extract_title_tokens(new_title)

    for existing in open_titles:
        existing_tag = extract_root_cause_tag(existing)
        existing_tokens = extract_title_tokens(existing)

        # Both have a tag and they differ → definitely not a duplicate.
        if new_tag != "UNTAGGED" and existing_tag != "UNTAGGED":
            if new_tag != existing_tag:
                continue

        shared = new_tokens & existing_tokens
        if len(shared) >= MIN_SHARED_TOKENS:
            return True
    return False


# ---------------------------------------------------------------------------
# Public: issue filing with frequency gate
# ---------------------------------------------------------------------------


def file_issue_if_breach(
    metric: str,
    value: float,
    threshold: float,
    recent_filings: list[dict[str, Any]],
) -> int | None:
    """File a GitHub issue if a metric breaches its threshold, subject to a
    frequency gate.

    Applies the ``FREQUENCY_GATE_MAX_PER_24H`` gate: if *recent_filings*
    already contains ``>= FREQUENCY_GATE_MAX_PER_24H`` entries in the last 24
    hours, this function returns ``None`` without filing.

    Writes the hook-contract context file to ``/tmp/autonomous_dev_cmd_context.json``
    BEFORE calling ``gh issue create``, then removes it.

    Args:
        metric: Short metric name, e.g. ``"drop_rate"`` or ``"down_events"``.
        value: Observed metric value that breached the threshold.
        threshold: The threshold that was exceeded.
        recent_filings: List of dicts with at least ``"filed_utc"`` (ISO-8601
            string) for issues filed previously.  Used for frequency gating.

    Returns:
        The GitHub issue number (int) on success, or ``None`` if gated or
        filing failed.
    """
    # ---- Frequency gate ----
    cutoff = time.time() - 86400  # 24 h
    recent_count = 0
    for filing in recent_filings:
        ts_raw = filing.get("filed_utc", "")
        try:
            ts = datetime.datetime.fromisoformat(
                str(ts_raw).replace("Z", "+00:00")
            ).timestamp()
            if ts >= cutoff:
                recent_count += 1
        except (ValueError, TypeError):
            continue

    if recent_count >= FREQUENCY_GATE_MAX_PER_24H:
        return None

    # ---- Build issue ----
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    title = f"[GOA] {metric} breach: {value:.1f} (threshold {threshold:.1f})"
    body = (
        f"**GOA autonomous health observer** detected a threshold breach.\n\n"
        f"- **Metric**: `{metric}`\n"
        f"- **Observed**: `{value:.2f}`\n"
        f"- **Threshold**: `{threshold:.2f}`\n"
        f"- **Detected at**: `{now_utc}`\n\n"
        f"_Auto-filed by `/goa watch` (Issue #1320)._"
    )

    # ---- Write hook-contract context file ----
    context = {
        "command": "goa",
        "timestamp": now_utc,
    }
    try:
        _TMP_CONTEXT_FILE.write_text(json.dumps(context), encoding="utf-8")
        os.chmod(str(_TMP_CONTEXT_FILE), 0o600)
    except OSError:
        pass

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--label",
                _GH_LABEL,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    finally:
        try:
            _TMP_CONTEXT_FILE.unlink()
        except FileNotFoundError:
            pass

    # Extract issue number from gh output (e.g. https://github.com/…/issues/42)
    output = result.stdout.strip()
    match = re.search(r"/issues/(\d+)", output)
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Internal: load recent filings from GitHub for frequency gate
# ---------------------------------------------------------------------------


def _load_recent_filings_from_github() -> list[dict[str, Any]]:
    """Query GitHub for GOA issues created in the last 24 h.

    Uses ``gh issue list`` with a ``created:>`` date filter to retrieve issues
    labelled ``goa`` that were filed within the frequency-gate window.  Each
    result is converted to the same dict shape that :func:`file_issue_if_breach`
    expects (``{"filed_utc": <ISO-8601 str>}``).

    Returns an empty list on any error (network down, ``gh`` not installed,
    unauthenticated) so the caller degrades gracefully.

    Returns:
        List of dicts with ``"filed_utc"`` key for each recent GOA issue.
    """
    cutoff_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    # GitHub search date format: YYYY-MM-DDTHH:MM:SSZ
    cutoff_str = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--label", "goa",
                "--search", f"created:>{cutoff_str}",
                "--json", "number,createdAt,title",
                "--limit", "50",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        issues = json.loads(result.stdout)
    except Exception as exc:
        print(f"GOA: GitHub recent filings dedup error: {exc}", file=sys.stderr)
        return []

    filings: list[dict[str, Any]] = []
    for issue in issues:
        created_at = issue.get("createdAt", "")
        if created_at:
            filings.append({"filed_utc": created_at})
    return filings


# ---------------------------------------------------------------------------
# Public: top-level run_watch
# ---------------------------------------------------------------------------


def run_watch() -> int:
    """Run a single GOA health-check cycle.

    1. Load the manifest to get thresholds and healthcheck UUID.
    2. Compute the cron drop rate and fetch down-event count.
    3. File issues for any breaches (subject to frequency gate).
    4. Return 0 on success.

    Returns:
        0 on success, 1 on configuration error.
    """
    from goa_state import load_manifest  # type: ignore[import-untyped]

    manifest = load_manifest()
    if manifest is None:
        print("GOA: no manifest found — run `/goa start` first.")
        return 1

    thresholds = manifest.get("thresholds", {})
    drop_rate_pct = float(thresholds.get("drop_rate_pct", DROP_RATE_PCT_THRESHOLD))
    drop_window_h = int(thresholds.get("drop_window_h", DROP_WINDOW_HOURS))
    down_events_threshold = int(thresholds.get("down_events", DOWN_EVENTS_THRESHOLD))
    down_window_h = int(thresholds.get("down_window_h", DOWN_WINDOW_HOURS))
    hc_uuid = manifest.get("healthcheck_uuid", "")

    # ---- Fetch open GOA issue titles for dedup ----
    open_titles: list[str] = []
    try:
        r = subprocess.run(
            ["gh", "issue", "list", "--label", "goa", "--state", "open",
             "--json", "title", "--limit", "100"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            issues = json.loads(r.stdout)
            open_titles = [i.get("title", "") for i in issues]
    except Exception:
        pass

    # ---- Load recent filings from GitHub (frequency gate — AC9) ----
    # Query existing GOA issues created within the last 24h as ground truth.
    # This survives process restarts between cron invocations.
    recent_filings: list[dict[str, Any]] = _load_recent_filings_from_github()

    # ---- Check drop rate ----
    actual_drop = compute_cron_drop_rate(drop_window_h)
    if actual_drop > drop_rate_pct:
        candidate_title = f"[GOA] drop_rate breach: {actual_drop:.1f} (threshold {drop_rate_pct:.1f})"
        if not is_duplicate(candidate_title, open_titles):
            issue_num = file_issue_if_breach(
                "drop_rate", actual_drop, drop_rate_pct, recent_filings
            )
            if issue_num is not None:
                print(f"GOA: filed drop_rate issue #{issue_num}")
                recent_filings.append({
                    "filed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })

    # ---- Check healthcheck down events ----
    if hc_uuid:
        down_count = fetch_healthcheck_down_events(hc_uuid, down_window_h)
        if down_count > down_events_threshold:
            candidate_title = f"[GOA] down_events breach: {down_count} (threshold {down_events_threshold})"
            if not is_duplicate(candidate_title, open_titles):
                issue_num = file_issue_if_breach(
                    "down_events", float(down_count), float(down_events_threshold),
                    recent_filings
                )
                if issue_num is not None:
                    print(f"GOA: filed down_events issue #{issue_num}")

    return 0
