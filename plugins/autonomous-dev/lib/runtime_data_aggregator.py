"""Runtime Data Aggregator - Collect, normalize, rank, and persist improvement signals.

Collects signals from 4 sources:
1. Session activity logs (tool failures, hook errors, agent crashes)
2. Benchmark history (per-category accuracy deficits)
3. CI/session logs (known bypass pattern matches)
4. GitHub issues (auto-improvement labeled issues)

Normalizes severity, computes priority with type-specific weights,
and persists ranked reports as append-only JSONL.

Security:
- CWE-532: Secret scrubbing for API keys, tokens, passwords
- CWE-400: Line cap on session log reading (MAX_LINES = 100_000)
- CWE-78: Subprocess calls use argument lists (no shell invocation)
- CWE-22: Path validation via resolve() within project_root

GitHub Issue: #579
"""

import json
import math
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .benchmark_history import BenchmarkHistory
except ImportError:
    _lib_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(_lib_dir))
    from benchmark_history import BenchmarkHistory


# =============================================================================
# Constants
# =============================================================================

MAX_LINES = 100_000

SEVERITY_WEIGHTS: Dict[str, float] = {
    "bypass_detected": 1.5,
    "hook_failure": 1.4,
    "benchmark_weakness": 1.3,
    "step_skipping": 1.2,
    "github_issue": 1.0,
}

DEFAULT_WEIGHT = 1.0

# Issue #1200: severity-label → float map for the cia_findings collector.
# Mirrors the {info, warning, error} vocabulary used by append_finding.
# Deliberately separate from collect_ci_signals's `sev_map` (which uses
# {critical, warning, info}); the two collectors have different contracts.
CIA_FINDING_SEVERITY_MAP: Dict[str, float] = {
    "info": 0.33,
    "warning": 0.66,
    "error": 1.0,
}

BENCHMARK_ACCURACY_THRESHOLD = 0.70

SECRET_PATTERNS: List[Tuple[str, str]] = [
    (r"sk-[a-zA-Z0-9]{6,}", "[REDACTED]"),
    (r"ghp_[a-zA-Z0-9]{6,}", "[REDACTED]"),
    (r"gho_[a-zA-Z0-9]{6,}", "[REDACTED]"),
    (r"ghr_[a-zA-Z0-9]{6,}", "[REDACTED]"),
    (r"anthropic_[a-zA-Z0-9_-]{6,}", "[REDACTED]"),
    (r"Bearer\s+[a-zA-Z0-9_\-]+", "[REDACTED]"),
    (r"password[\"']?\s*[=:]\s*[\"']?[^\s\"']+", "[REDACTED]"),
    (r"api[_-]?key[\"']?\s*[=:]\s*[\"']?[a-zA-Z0-9_-]{6,}", "[REDACTED]"),
    (r"secret[\"']?\s*[=:]\s*[\"']?[a-zA-Z0-9_-]{6,}", "[REDACTED]"),
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AggregatedSignal:
    """A single aggregated improvement signal.

    Args:
        source: Origin of the signal (session, benchmark, ci, github)
        signal_type: Classification (hook_failure, benchmark_weakness, bypass_detected, etc.)
        description: Human-readable description of the signal
        frequency: How many times this signal was observed in the window
        severity: Normalized severity score (0.0-1.0)
        raw_data: Original data for traceability
        timestamp: ISO 8601 timestamp of the most recent occurrence
    """

    source: str
    signal_type: str
    description: str
    frequency: int = 1
    severity: float = 0.0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SourceHealth:
    """Health status of a signal source.

    Args:
        source: Name of the signal source
        status: Health status (ok, error, empty)
        signal_count: Number of signals collected
        error_message: Error details if status is 'error'
    """

    source: str
    status: str = "ok"
    signal_count: int = 0
    error_message: str = ""


@dataclass
class AggregatedReport:
    """Complete aggregated report with ranked signals and source health.

    Args:
        signals: Ranked list of aggregated signals (highest priority first)
        source_health: Health status for each signal source
        window_start: ISO 8601 start of the analysis window
        window_end: ISO 8601 end of the analysis window
        generated_at: ISO 8601 timestamp of report generation
        top_n: Maximum number of signals included
    """

    signals: List[AggregatedSignal]
    source_health: List[SourceHealth]
    window_start: str
    window_end: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    top_n: int = 10


# =============================================================================
# Security Utilities
# =============================================================================

def scrub_secrets(text: str) -> str:
    """Remove API keys, tokens, and passwords from text.

    Args:
        text: Text that may contain secrets

    Returns:
        Text with secrets replaced by [REDACTED]
    """
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def _sanitize_string(text: str) -> str:
    """Strip control characters and scrub secrets from a string.

    Args:
        text: Raw string to sanitize

    Returns:
        Sanitized string with CR/LF/tab stripped and secrets scrubbed
    """
    cleaned = text.replace("\r", "").replace("\n", " ").replace("\t", " ")
    return scrub_secrets(cleaned)


def _validate_path(path: Path, project_root: Path) -> bool:
    """Validate that a path resolves within project_root.

    Args:
        path: Path to validate
        project_root: Allowed root directory

    Returns:
        True if path is within project_root
    """
    try:
        resolved = path.resolve()
        root_resolved = project_root.resolve()
        return resolved.is_relative_to(root_resolved)
    except (OSError, ValueError):
        return False


# =============================================================================
# Utility Functions
# =============================================================================

def normalize_severity(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalize a value to [0, 1].

    Args:
        value: Raw value to normalize
        min_val: Minimum of the range
        max_val: Maximum of the range

    Returns:
        Normalized value clamped to [0.0, 1.0]
    """
    if min_val >= max_val:
        return 0.0
    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def compute_priority(signal: AggregatedSignal) -> float:
    """Compute priority score for ranking signals.

    Formula: SEVERITY_WEIGHTS[signal_type] * severity * log(1 + frequency)

    Higher priority = more urgent. Uses type-specific weights to
    prioritize bypasses and hook failures over informational signals.

    Args:
        signal: Signal to compute priority for

    Returns:
        Priority score (higher = more urgent)
    """
    weight = SEVERITY_WEIGHTS.get(signal.signal_type, DEFAULT_WEIGHT)
    return weight * signal.severity * math.log(1 + signal.frequency)


# =============================================================================
# Collectors
# =============================================================================

def collect_session_signals(
    logs_dir: Path,
    window_days: int = 7,
) -> Tuple[List[AggregatedSignal], SourceHealth]:
    """Collect signals from session activity logs.

    Reads .claude/logs/activity/*.jsonl files, filters by time window,
    and extracts tool failures (success=false), hook errors, and agent crashes.
    Groups by (signal_type, description) and counts frequency.

    Args:
        logs_dir: Path to .claude/logs/activity/ directory
        window_days: Number of days to look back

    Returns:
        Tuple of (signals, source_health)
    """
    source_name = "session"
    try:
        if not logs_dir.exists():
            return [], SourceHealth(source=source_name, status="empty", signal_count=0)

        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        signal_groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
        total_lines = 0

        jsonl_files = sorted(logs_dir.glob("*.jsonl"))
        for jsonl_file in jsonl_files:
            try:
                with open(jsonl_file, "r") as f:
                    for line in f:
                        if total_lines >= MAX_LINES:
                            break
                        total_lines += 1

                        line = line.strip()
                        if not line:
                            continue

                        try:
                            event = json.loads(line)
                        except (json.JSONDecodeError, ValueError):
                            continue

                        # Filter by timestamp
                        ts_str = event.get("timestamp", "")
                        try:
                            ts = datetime.fromisoformat(ts_str)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts < cutoff:
                                continue
                        except (ValueError, TypeError):
                            continue

                        # Extract failure signals
                        success = event.get("success", True)
                        if success is True:
                            continue

                        tool = event.get("tool", "unknown")
                        output_summary = event.get("output_summary", "")
                        hook = event.get("hook", "")

                        # Determine signal type
                        if hook and "error" in str(output_summary).lower():
                            signal_type = "hook_failure"
                        elif "agent" in str(event.get("agent", "") or "").lower():
                            signal_type = "agent_crash"
                        else:
                            signal_type = "tool_failure"

                        description = _sanitize_string(
                            f"{tool}: {output_summary}"[:200]
                        )
                        key = (signal_type, description)

                        if key not in signal_groups:
                            signal_groups[key] = {
                                "frequency": 0,
                                "latest_ts": ts_str,
                                "raw_data": event,
                            }
                        signal_groups[key]["frequency"] += 1
                        signal_groups[key]["latest_ts"] = ts_str

            except (OSError, PermissionError):
                continue

            if total_lines >= MAX_LINES:
                break

        signals = []
        for (sig_type, desc), data in signal_groups.items():
            signals.append(
                AggregatedSignal(
                    source=source_name,
                    signal_type=sig_type,
                    description=desc,
                    frequency=data["frequency"],
                    severity=normalize_severity(data["frequency"], 1, 20),
                    raw_data=data["raw_data"],
                    timestamp=data["latest_ts"],
                )
            )

        health = SourceHealth(
            source=source_name,
            status="ok" if signals else "empty",
            signal_count=len(signals),
        )
        return signals, health

    except Exception as e:
        return [], SourceHealth(
            source=source_name, status="error", signal_count=0,
            error_message=str(e)[:200],
        )


def collect_benchmark_signals(
    history_path: Path,
    window_days: int = 7,
) -> Tuple[List[AggregatedSignal], SourceHealth]:
    """Collect signals from benchmark history.

    Uses BenchmarkHistory to load entries, filters by time window,
    and converts per-category accuracy deficits (below threshold) into signals.

    Args:
        history_path: Path to benchmark history JSONL file
        window_days: Number of days to look back

    Returns:
        Tuple of (signals, source_health)
    """
    source_name = "benchmark"
    try:
        history = BenchmarkHistory(history_path)
        entries = history.load_all()

        if not entries:
            return [], SourceHealth(source=source_name, status="empty", signal_count=0)

        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        signals = []

        for entry in entries:
            ts_str = entry.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                continue

            per_defect = entry.get("per_defect_category", {})
            if not isinstance(per_defect, dict):
                continue

            for category, stats in per_defect.items():
                if not isinstance(stats, dict):
                    continue

                accuracy = stats.get("accuracy", 1.0)
                total = stats.get("total", 0)

                if accuracy < BENCHMARK_ACCURACY_THRESHOLD and total > 0:
                    deficit = BENCHMARK_ACCURACY_THRESHOLD - accuracy
                    signals.append(
                        AggregatedSignal(
                            source=source_name,
                            signal_type="benchmark_weakness",
                            description=_sanitize_string(
                                f"Category '{category}' accuracy {accuracy:.2f} "
                                f"(threshold {BENCHMARK_ACCURACY_THRESHOLD})"
                            ),
                            frequency=total,
                            severity=normalize_severity(deficit, 0.0, BENCHMARK_ACCURACY_THRESHOLD),
                            raw_data={"category": category, **stats},
                            timestamp=ts_str,
                        )
                    )

        health = SourceHealth(
            source=source_name,
            status="ok" if signals else "empty",
            signal_count=len(signals),
        )
        return signals, health

    except Exception as e:
        return [], SourceHealth(
            source=source_name, status="error", signal_count=0,
            error_message=str(e)[:200],
        )


def collect_ci_signals(
    logs_dir: Path,
    patterns_path: Path,
    window_days: int = 7,
) -> Tuple[List[AggregatedSignal], SourceHealth]:
    """Collect signals by matching session logs against known bypass patterns.

    Reads session activity logs and cross-references against
    known_bypass_patterns.json to detect model intent bypasses.

    Args:
        logs_dir: Path to .claude/logs/activity/ directory
        patterns_path: Path to known_bypass_patterns.json
        window_days: Number of days to look back

    Returns:
        Tuple of (signals, source_health)
    """
    source_name = "ci"
    try:
        if not patterns_path.exists():
            return [], SourceHealth(
                source=source_name, status="error", signal_count=0,
                error_message=f"Patterns file not found: {patterns_path}",
            )

        try:
            patterns_data = json.loads(patterns_path.read_text())
        except (json.JSONDecodeError, ValueError) as e:
            return [], SourceHealth(
                source=source_name, status="error", signal_count=0,
                error_message=f"Invalid patterns JSON: {e}",
            )

        patterns = patterns_data.get("patterns", [])
        if not patterns:
            return [], SourceHealth(source=source_name, status="empty", signal_count=0)

        # Build indicator lookup by pattern
        indicator_map: Dict[str, Dict[str, Any]] = {}
        for pat in patterns:
            pat_id = pat.get("id", "")
            detection = pat.get("detection", {})
            indicators = detection.get("indicators", [])
            indicator_map[pat_id] = {
                "name": pat.get("name", pat_id),
                "severity": pat.get("severity", "warning"),
                "indicators": [ind.lower() for ind in indicators],
            }

        if not logs_dir.exists():
            return [], SourceHealth(source=source_name, status="empty", signal_count=0)

        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        # Track (pattern_id, date) for deduplication
        seen: set = set()
        signals = []
        total_lines = 0

        jsonl_files = sorted(logs_dir.glob("*.jsonl"))
        for jsonl_file in jsonl_files:
            try:
                with open(jsonl_file, "r") as f:
                    for line in f:
                        if total_lines >= MAX_LINES:
                            break
                        total_lines += 1

                        line = line.strip()
                        if not line:
                            continue

                        try:
                            event = json.loads(line)
                        except (json.JSONDecodeError, ValueError):
                            continue

                        ts_str = event.get("timestamp", "")
                        try:
                            ts = datetime.fromisoformat(ts_str)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts < cutoff:
                                continue
                            event_date = ts.strftime("%Y-%m-%d")
                        except (ValueError, TypeError):
                            continue

                        # Build a searchable text from the event
                        event_text = json.dumps(event, default=str).lower()

                        for pat_id, pat_info in indicator_map.items():
                            for indicator in pat_info["indicators"]:
                                if indicator in event_text:
                                    dedup_key = (pat_id, event_date)
                                    if dedup_key in seen:
                                        break
                                    seen.add(dedup_key)

                                    sev_map = {"critical": 0.9, "warning": 0.5, "info": 0.2}
                                    sev = sev_map.get(pat_info["severity"], 0.5)

                                    signals.append(
                                        AggregatedSignal(
                                            source=source_name,
                                            signal_type="bypass_detected",
                                            description=_sanitize_string(
                                                f"Bypass pattern '{pat_info['name']}' detected"
                                            ),
                                            frequency=1,
                                            severity=sev,
                                            raw_data={"pattern_id": pat_id, "date": event_date},
                                            timestamp=ts_str,
                                        )
                                    )
                                    break  # One match per pattern per event

            except (OSError, PermissionError):
                continue

            if total_lines >= MAX_LINES:
                break

        health = SourceHealth(
            source=source_name,
            status="ok" if signals else "empty",
            signal_count=len(signals),
        )
        return signals, health

    except Exception as e:
        return [], SourceHealth(
            source=source_name, status="error", signal_count=0,
            error_message=str(e)[:200],
        )


def fetch_issues_with_label(
    repo: str = "akaszubski/autonomous-dev",
    label: str = "auto-improvement",
    limit: int = 200,
    state: str = "open",
    closed_within_days: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], SourceHealth]:
    """Fetch raw GitHub issues with a given label via the ``gh`` CLI.

    Generalizes :func:`fetch_open_issues_with_label` to support open/closed/all
    state filters (Issue #1201). When ``state != "open"``, the ``--json`` field
    list is extended to include ``closedAt`` so post-filtering by
    ``closed_within_days`` is possible. When ``closed_within_days`` is set,
    issues whose ``closedAt`` is older than ``now - timedelta(days=closed_within_days)``
    are dropped from the result.

    Args:
        repo: GitHub repository in ``owner/repo`` format.
        label: Label to filter on (e.g., ``"auto-improvement"``).
        limit: Maximum number of issues to request (``--limit`` to gh).
        state: One of ``"open"``, ``"closed"``, ``"all"`` (passed to ``gh issue list --state``).
        closed_within_days: When set, drop issues closed more than N days ago.
            Only meaningful for ``state != "open"``.

    Returns:
        Tuple of (issues, source_health). On failure ``issues`` is empty and
        ``source_health.status`` is ``"error"`` with a populated ``error_message``.
    """
    source_name = "github"
    json_fields = "number,title,body,labels,createdAt"
    if state != "open":
        json_fields = json_fields + ",closedAt"
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", repo,
                "--label", label,
                "--state", state,
                "--limit", str(limit),
                "--json", json_fields,
            ],
            capture_output=True,
            timeout=30,
            text=True,
        )

        if result.returncode != 0:
            return [], SourceHealth(
                source=source_name, status="error", signal_count=0,
                error_message=_sanitize_string(result.stderr[:200]),
            )

        try:
            issues = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return [], SourceHealth(
                source=source_name, status="error", signal_count=0,
                error_message="Invalid JSON from gh CLI",
            )

        if not isinstance(issues, list):
            return [], SourceHealth(
                source=source_name, status="error", signal_count=0,
                error_message="Unexpected gh JSON shape (expected list)",
            )

        # Post-filter by closed_within_days when applicable.
        if closed_within_days is not None and state != "open":
            cutoff = datetime.now(timezone.utc) - timedelta(days=closed_within_days)
            filtered: List[Dict[str, Any]] = []
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                closed_at = issue.get("closedAt", "")
                # Issues still open (state=all) have empty closedAt — keep them.
                if not closed_at:
                    filtered.append(issue)
                    continue
                dt = _parse_iso_ts(closed_at)
                if dt is None:
                    # Unparseable: keep (fail-open) — we'd rather over-include.
                    filtered.append(issue)
                    continue
                if dt >= cutoff:
                    filtered.append(issue)
            issues = filtered

        if not issues:
            return [], SourceHealth(source=source_name, status="empty", signal_count=0)

        return issues, SourceHealth(
            source=source_name, status="ok", signal_count=len(issues),
        )

    except FileNotFoundError:
        return [], SourceHealth(
            source=source_name, status="error", signal_count=0,
            error_message="gh CLI not found",
        )
    except subprocess.TimeoutExpired:
        return [], SourceHealth(
            source=source_name, status="error", signal_count=0,
            error_message="gh CLI timed out after 30s",
        )
    except Exception as e:
        return [], SourceHealth(
            source=source_name, status="error", signal_count=0,
            error_message=str(e)[:200],
        )


def fetch_open_issues_with_label(
    repo: str = "akaszubski/autonomous-dev",
    label: str = "auto-improvement",
    limit: int = 200,
) -> Tuple[List[Dict[str, Any]], SourceHealth]:
    """Backward-compatible alias for ``fetch_issues_with_label(state="open")``.

    Preserved for callers in :mod:`issue_triage_analyzer` and
    :func:`collect_github_signals` that pre-date Issue #1201's macro promotion
    work. New callers should use :func:`fetch_issues_with_label` directly.

    Args:
        repo: GitHub repository in ``owner/repo`` format.
        label: Label to filter on.
        limit: Maximum number of issues to request.

    Returns:
        Tuple of (issues, source_health).
    """
    return fetch_issues_with_label(
        repo=repo, label=label, limit=limit, state="open",
    )


def collect_github_signals(
    repo: str = "akaszubski/autonomous-dev",
) -> Tuple[List[AggregatedSignal], SourceHealth]:
    """Collect signals from GitHub issues labeled auto-improvement.

    Wraps :func:`fetch_open_issues_with_label` and converts each raw issue into an
    :class:`AggregatedSignal`. Preserves the original external contract for callers that
    were already using this function (existing tests must pass unchanged).

    Args:
        repo: GitHub repository in owner/repo format

    Returns:
        Tuple of (signals, source_health)
    """
    issues, health = fetch_open_issues_with_label(
        repo=repo, label="auto-improvement", limit=200,
    )

    if health.status != "ok":
        return [], health

    source_name = "github"
    signals: List[AggregatedSignal] = []
    for issue in issues:
        title = _sanitize_string(issue.get("title", ""))
        created = issue.get("createdAt", "")
        signals.append(
            AggregatedSignal(
                source=source_name,
                signal_type="github_issue",
                description=title[:200],
                frequency=1,
                severity=0.5,
                raw_data={"title": title, "createdAt": created},
                timestamp=created,
            )
        )

    return signals, SourceHealth(
        source=source_name, status="ok", signal_count=len(signals),
    )


# =============================================================================
# CIA Findings Collector (Issue #1200)
# =============================================================================


def _parse_iso_ts(ts_str: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp into a tz-aware datetime, or None on failure."""
    if not isinstance(ts_str, str) or not ts_str.strip():
        return None
    text = ts_str.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def collect_cia_findings(
    findings_dir: Path,
    window_days: int = 90,
) -> Tuple[List[AggregatedSignal], SourceHealth]:
    """Collect CIA findings from ``.claude/logs/findings/YYYY-MM.jsonl`` files.

    Algorithm:
    1. Validate that ``findings_dir`` is absolute (worktree-safety regression).
    2. Enumerate only monthly files whose filename month falls inside the
       window (chronological filename sort).
    3. Stream-parse with a :data:`MAX_LINES` guard; skip malformed lines and
       records with no ``ts`` or with ``ts < cutoff``.
    4. Group records by ``root_cause_tag``; within each tag, cluster by
       title-token Jaccard similarity using
       :func:`issue_triage_analyzer.cluster_within_tag` (so the contract
       matches the existing triage analyzer).
    5. Emit one :class:`AggregatedSignal` per sub-cluster with:

       * ``signal_type`` = ``root_cause_tag``
       * ``frequency`` = cluster size
       * ``severity`` = ``CIA_FINDING_SEVERITY_MAP[max_severity_label]``
       * ``raw_data`` = ``{distinct_sessions, file_refs_union,
         sub_cluster_size, max_severity_label, root_cause_tag}``

    Args:
        findings_dir: ABSOLUTE path to the findings root directory.
        window_days: Number of days to look back.

    Returns:
        Tuple of (signals, source_health). Status is ``"empty"`` when no
        signals were produced (including when the directory does not exist),
        ``"ok"`` on success, and ``"error"`` if a top-level exception was
        caught.
    """
    source_name = "cia_findings"

    if not isinstance(findings_dir, Path):
        findings_dir = Path(findings_dir)
    if not findings_dir.is_absolute():
        raise ValueError("findings_dir must be absolute (worktree safety)")

    try:
        # Import lazily so the runtime_data_aggregator module doesn't have a
        # hard import-time dependency on issue_triage_analyzer (and the
        # circular-import risk: issue_triage_analyzer already imports from
        # runtime_data_aggregator).
        try:
            from .issue_triage_analyzer import cluster_within_tag  # type: ignore
        except ImportError:
            _lib_dir = Path(__file__).parent.resolve()
            if str(_lib_dir) not in sys.path:
                sys.path.insert(0, str(_lib_dir))
            from issue_triage_analyzer import cluster_within_tag  # type: ignore

        if not findings_dir.exists():
            return [], SourceHealth(source=source_name, status="empty", signal_count=0)

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=window_days)
        cutoff_month = (cutoff.year, cutoff.month)

        # Enumerate ``YYYY-MM.jsonl`` files chronologically; skip files whose
        # month is strictly before the cutoff month.
        monthly_files: List[Path] = []
        for p in sorted(findings_dir.glob("*.jsonl")):
            stem = p.stem  # e.g. "2026-06"
            parts = stem.split("-")
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                continue
            year, month = int(parts[0]), int(parts[1])
            if (year, month) < cutoff_month:
                continue
            monthly_files.append(p)

        # Stream parse records.
        records: List[Dict[str, Any]] = []
        total_lines = 0
        for monthly in monthly_files:
            try:
                with open(monthly, "r", encoding="utf-8") as fh:
                    for line in fh:
                        if total_lines >= MAX_LINES:
                            break
                        total_lines += 1
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        if not isinstance(rec, dict):
                            continue
                        ts_str = rec.get("ts", "")
                        dt = _parse_iso_ts(ts_str)
                        if dt is None:
                            # Missing/malformed ts → skip per spec.
                            continue
                        if dt < cutoff:
                            continue
                        # Default missing session_id to literal "unknown".
                        if not rec.get("session_id"):
                            rec["session_id"] = "unknown"
                        records.append(rec)
            except (OSError, PermissionError):
                continue
            if total_lines >= MAX_LINES:
                break

        if not records:
            return [], SourceHealth(source=source_name, status="empty", signal_count=0)

        # Group by root_cause_tag.
        by_tag: Dict[str, List[Dict[str, Any]]] = {}
        for rec in records:
            tag = str(rec.get("root_cause_tag", "UNTAGGED"))
            by_tag.setdefault(tag, []).append(rec)

        severity_order = {"info": 0, "warning": 1, "error": 2}
        severity_inv = {v: k for k, v in severity_order.items()}

        signals: List[AggregatedSignal] = []
        for tag in sorted(by_tag):
            bucket = by_tag[tag]
            # Build synthetic ``issue``-shaped dicts for cluster_within_tag:
            # the function needs ``number`` (int) and ``title`` (str) only.
            synthetic_issues = [
                {"number": i, "title": str(rec.get("title", ""))}
                for i, rec in enumerate(bucket)
            ]
            sub_clusters = cluster_within_tag(synthetic_issues)

            for cluster in sub_clusters:
                cluster_records = [bucket[idx] for idx in cluster]
                titles = [str(rec.get("title", "")) for rec in cluster_records]
                # Pick the shortest non-empty title as the description (so
                # the signal stays human-readable in reports).
                non_empty_titles = [t for t in titles if t]
                if non_empty_titles:
                    description = min(non_empty_titles, key=len)
                else:
                    description = ""
                description = _sanitize_string(description)[:200]

                # Max severity across the cluster.
                max_sev_int = 0
                for rec in cluster_records:
                    sev = str(rec.get("severity", "info"))
                    max_sev_int = max(max_sev_int, severity_order.get(sev, 0))
                max_sev_label = severity_inv[max_sev_int]
                severity_float = CIA_FINDING_SEVERITY_MAP[max_sev_label]

                # Distinct sessions + file_refs union.
                distinct_sessions = {
                    str(rec.get("session_id", "unknown")) for rec in cluster_records
                }
                file_refs_union: set = set()
                for rec in cluster_records:
                    refs = rec.get("file_refs", [])
                    if isinstance(refs, (list, tuple)):
                        for ref in refs:
                            if ref:
                                file_refs_union.add(str(ref))

                # Latest ts in cluster (already parseable since we filtered).
                latest_ts = ""
                latest_dt: Optional[datetime] = None
                for rec in cluster_records:
                    dt = _parse_iso_ts(str(rec.get("ts", "")))
                    if dt is None:
                        continue
                    if latest_dt is None or dt > latest_dt:
                        latest_dt = dt
                        latest_ts = str(rec.get("ts", ""))

                # Determine target_repo: preserve if present, otherwise classify
                target_repo = None
                for rec in cluster_records:
                    # Take the first non-empty target_repo value in the cluster
                    tr = rec.get("target_repo")
                    if tr:
                        target_repo = tr
                        break
                
                # If no target_repo found, classify based on content
                if not target_repo:
                    from .finding_target_classifier import classify_finding_target
                    # Use the first record's title for classification
                    first_rec = cluster_records[0] if cluster_records else {}
                    finding_title = str(first_rec.get("title", ""))
                    finding_evidence = str(first_rec.get("evidence", ""))
                    target_repo = classify_finding_target(finding_title, finding_evidence)

                signals.append(
                    AggregatedSignal(
                        source=source_name,
                        signal_type=tag,
                        description=description,
                        frequency=len(cluster_records),
                        severity=severity_float,
                        raw_data={
                            "root_cause_tag": tag,
                            "distinct_sessions": len(distinct_sessions),
                            "file_refs_union": sorted(file_refs_union),
                            "sub_cluster_size": len(cluster_records),
                            "max_severity_label": max_sev_label,
                            "target_repo": target_repo,
                        },
                        timestamp=latest_ts,
                    )
                )

        health = SourceHealth(
            source=source_name,
            status="ok" if signals else "empty",
            signal_count=len(signals),
        )
        return signals, health

    except ValueError:
        # Re-raise programmer errors (absolute-path guard).
        raise
    except Exception as e:
        return [], SourceHealth(
            source=source_name, status="error", signal_count=0,
            error_message=str(e)[:200],
        )


# =============================================================================
# Persistence
# =============================================================================

def persist_report(report: AggregatedReport, output_path: Path) -> None:
    """Persist an aggregated report as a single JSONL line.

    Appends to the output file (creates parent dirs if needed).

    Args:
        report: Report to persist
        output_path: Path to the JSONL output file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report_dict = asdict(report)
    with open(output_path, "a") as f:
        f.write(json.dumps(report_dict, default=str) + "\n")


# =============================================================================
# Main Entry Point
# =============================================================================

def aggregate(
    project_root: Path,
    *,
    window_days: int = 7,
    top_n: int = 10,
    repo: str = "akaszubski/autonomous-dev",
) -> AggregatedReport:
    """Aggregate signals from all sources, rank by priority, persist report.

    Collects from session logs, benchmark history, CI bypass patterns,
    and GitHub issues. Computes priority for each signal, sorts descending,
    caps at top_n, and persists to .claude/logs/aggregated_reports.jsonl.

    Args:
        project_root: Root directory of the project
        window_days: Number of days to look back (default: 7)
        top_n: Maximum signals to include in report (default: 10)
        repo: GitHub repository for issue collection

    Returns:
        AggregatedReport with ranked signals and source health
    """
    project_root = Path(project_root).resolve()
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(days=window_days)).isoformat()
    window_end = now.isoformat()

    logs_activity_dir = project_root / ".claude" / "logs" / "activity"
    benchmark_path = project_root / ".claude" / "logs" / "benchmark_history.jsonl"
    patterns_path = (
        project_root / "plugins" / "autonomous-dev" / "config" / "known_bypass_patterns.json"
    )
    findings_dir = project_root / ".claude" / "logs" / "findings"

    # Collect from all sources
    session_signals, session_health = collect_session_signals(logs_activity_dir, window_days)
    benchmark_signals, benchmark_health = collect_benchmark_signals(benchmark_path, window_days)
    ci_signals, ci_health = collect_ci_signals(logs_activity_dir, patterns_path, window_days)
    github_signals, github_health = collect_github_signals(repo)
    # Issue #1200: CIA findings — use a 90-day window minimum so single
    # findings don't drop off the report after one week.
    cia_signals, cia_health = collect_cia_findings(
        findings_dir, window_days=max(window_days, 90),
    )

    # Merge all signals
    all_signals = (
        session_signals + benchmark_signals + ci_signals + github_signals + cia_signals
    )
    all_health = [
        session_health, benchmark_health, ci_health, github_health, cia_health,
    ]

    # Sort by priority (highest first) and cap at top_n
    all_signals.sort(key=compute_priority, reverse=True)
    top_signals = all_signals[:top_n]

    report = AggregatedReport(
        signals=top_signals,
        source_health=all_health,
        window_start=window_start,
        window_end=window_end,
        top_n=top_n,
    )

    # Persist
    output_path = project_root / ".claude" / "logs" / "aggregated_reports.jsonl"
    if _validate_path(output_path, project_root):
        persist_report(report, output_path)

    return report
