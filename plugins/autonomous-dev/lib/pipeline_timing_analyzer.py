#!/usr/bin/env python3
"""
Pipeline Timing Analyzer - Issue #621

Analyzes agent execution timings from pipeline session logs to detect
slow, wasteful, and ghost agent invocations. Supports both static
thresholds and adaptive thresholds computed from historical data.

Used by the continuous-improvement-analyst agent (quality check #11).

Usage:
    from pipeline_timing_analyzer import analyze_timings, format_timing_report
    timings = extract_agent_timings(events)
    findings = analyze_timings(timings, history_path=Path("logs/timing_history.jsonl"))
    print(format_timing_report(timings, findings))
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pipeline_intent_validator import (
    STEP_ORDER,
    VALID_AGENT_TYPES,
    PipelineEvent,
    parse_timestamp,
    seconds_between,
)

logger = logging.getLogger(__name__)

# Thread lock for safe concurrent writes to history file
_history_lock = threading.Lock()

# Maximum number of historical entries to keep per agent
MAX_HISTORY_PER_AGENT = 20

# Static thresholds: agent_type -> (max_seconds, min_result_words_or_None)
STATIC_THRESHOLDS: dict[str, tuple[int, int | None]] = {
    "researcher-local": (90, 500),
    "researcher": (120, 300),
    "planner": (180, 500),
    "implementer": (480, None),
    "reviewer": (180, None),
    "security-auditor": (180, None),
    "doc-master": (120, 30),
    "test-master": (180, None),
}

# Adaptive threshold multiplier applied to p95
ADAPTIVE_P95_MULTIPLIER = 1.5

# Minimum observations required for adaptive thresholds
DEFAULT_MIN_OBSERVATIONS = 10

# Wasteful detection: words_per_second threshold
WASTEFUL_WPS_THRESHOLD = 1.0
WASTEFUL_MIN_DURATION = 60.0

# Ghost detection thresholds
GHOST_MAX_DURATION = 10.0
GHOST_MAX_WORDS = 50


@dataclass
class AgentTiming:
    """Timing data for a single agent invocation."""

    agent_type: str
    wall_clock_seconds: float
    result_word_count: int
    invocation_ts: str
    completion_ts: str
    step_number: float = 0.0
    total_tokens: int = 0
    tool_uses: int = 0


@dataclass
class TimingFinding:
    """A timing analysis finding for an agent invocation."""

    agent_type: str
    finding_type: str  # SLOW, WASTEFUL, GHOST, SLOW_REGRESSION
    actual_seconds: float
    threshold_seconds: float
    threshold_type: str  # "static" or "adaptive"
    result_word_count: int = 0
    recommendation: str = ""


@dataclass
class PromptIntegrityRecovery:
    """A paired prompt-integrity block + recovery, joined by block_event_id (Issue #1178).

    Captures the latency between a ``prompt_integrity_block`` deny decision and
    the matching ``prompt_integrity_recovery`` allow decision after the
    coordinator reloads the full agent template and re-dispatches.

    Attributes:
        block_event_id: uuid4 string joining the block and recovery rows.
        agent_type: The agent type that was blocked then recovered.
        block_timestamp_iso: ISO-8601 UTC timestamp of the original block.
        recovery_timestamp_iso: ISO-8601 UTC timestamp of the recovery allow.
        latency_ms: Block-to-recovery wall-clock latency in milliseconds.
        block_reason_category: Categorical reason (e.g. shrinkage_pct_over_threshold).
    """

    block_event_id: str
    agent_type: str
    block_timestamp_iso: str
    recovery_timestamp_iso: str
    latency_ms: int
    block_reason_category: str


def load_prompt_integrity_events(log_path: Path) -> list[dict]:
    """Read prompt-integrity rows from ``.claude/logs/hook-blocks.jsonl`` (Issue #1178).

    Filters rows where ``metadata.event_type`` starts with
    ``"prompt_integrity_"``. Missing file returns ``[]``; malformed JSON
    lines are silently skipped so a single corrupted row does not break
    the whole analysis.

    Args:
        log_path: Absolute path to ``hook-blocks.jsonl``.

    Returns:
        A list of full event dicts (with top-level ``metadata`` preserved).
    """
    if not log_path.exists():
        return []
    rows: list[dict] = []
    try:
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(event, dict):
                    continue
                metadata = event.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                event_type = metadata.get("event_type", "")
                if not isinstance(event_type, str):
                    continue
                if event_type.startswith("prompt_integrity_"):
                    rows.append(event)
    except OSError:
        return []
    return rows


def extract_prompt_integrity_recoveries(
    events: list[dict],
) -> tuple[list[PromptIntegrityRecovery], int]:
    """Pair prompt_integrity_block and prompt_integrity_recovery rows by id (Issue #1178).

    O(1) pairing via dict keyed on ``block_event_id``. First pass builds a
    block index; second pass walks recovery rows and emits a paired
    ``PromptIntegrityRecovery`` for each match. Recovery rows without a
    matching block are ignored (telemetry must not invent data). Block
    rows without a matching recovery contribute to the second return value.

    Args:
        events: List of event dicts from ``load_prompt_integrity_events``.

    Returns:
        Tuple of (paired_recoveries, blocked_without_recovery).
    """
    blocks_by_id: dict[str, dict] = {}
    recoveries_by_id: dict[str, dict] = {}

    for event in events:
        metadata = event.get("metadata") or {}
        event_type = metadata.get("event_type", "")
        block_event_id = metadata.get("block_event_id")
        if not isinstance(block_event_id, str) or not block_event_id:
            continue
        if event_type == "prompt_integrity_block":
            blocks_by_id[block_event_id] = metadata
        elif event_type == "prompt_integrity_recovery":
            recoveries_by_id[block_event_id] = metadata

    paired: list[PromptIntegrityRecovery] = []
    for block_event_id, recovery_meta in recoveries_by_id.items():
        block_meta = blocks_by_id.get(block_event_id)
        if block_meta is None:
            continue
        latency_raw = recovery_meta.get("latency_ms_from_block_to_recovery")
        try:
            latency_ms = int(latency_raw) if latency_raw is not None else 0
        except (TypeError, ValueError):
            latency_ms = 0
        paired.append(
            PromptIntegrityRecovery(
                block_event_id=block_event_id,
                agent_type=str(recovery_meta.get("agent_type", "")),
                block_timestamp_iso=str(block_meta.get("timestamp", "")),
                recovery_timestamp_iso=str(recovery_meta.get("timestamp", "")),
                latency_ms=latency_ms,
                block_reason_category=str(
                    block_meta.get("block_reason_category", "other")
                ),
            )
        )

    blocked_without_recovery = sum(
        1 for block_id in blocks_by_id if block_id not in recoveries_by_id
    )
    return paired, blocked_without_recovery


def extract_agent_timings(events: list[PipelineEvent]) -> list[AgentTiming]:
    """Extract paired agent timings from pipeline events.

    Pairs agent_invocation events with their SubagentStop agent_completion
    events by matching subagent_type. Wall-clock duration is computed from
    timestamp deltas (NOT duration_ms, which is always 0).

    Args:
        events: List of PipelineEvent from session logs, sorted by timestamp.

    Returns:
        List of AgentTiming for each successfully paired invocation/completion.
    """
    invocations = [
        e for e in events
        if e.pipeline_action == "agent_invocation" and e.subagent_type
    ]
    completions = [
        e for e in events
        if e.pipeline_action == "agent_completion" and e.subagent_type
    ]

    used_completions: set[int] = set()
    timings: list[AgentTiming] = []

    for inv in invocations:
        if inv.subagent_type not in VALID_AGENT_TYPES:
            logger.warning("Skipping unknown agent type: %s", inv.subagent_type)
            continue

        best_comp: PipelineEvent | None = None
        best_idx = -1
        best_gap = float("inf")

        for idx, comp in enumerate(completions):
            if idx in used_completions:
                continue
            if comp.subagent_type != inv.subagent_type:
                continue

            gap = seconds_between(inv.timestamp, comp.timestamp)
            if gap is None:
                continue

            inv_dt = parse_timestamp(inv.timestamp)
            comp_dt = parse_timestamp(comp.timestamp)
            if inv_dt is None or comp_dt is None:
                continue
            if comp_dt < inv_dt:
                continue

            if gap < best_gap:
                best_gap = gap
                best_comp = comp
                best_idx = idx

        if best_comp is not None:
            used_completions.add(best_idx)
            step_num = STEP_ORDER.get(inv.subagent_type, 0.0)
            timings.append(AgentTiming(
                agent_type=inv.subagent_type,
                wall_clock_seconds=best_gap,
                result_word_count=best_comp.result_word_count,
                invocation_ts=inv.timestamp,
                completion_ts=best_comp.timestamp,
                step_number=step_num,
                total_tokens=best_comp.total_tokens,
                tool_uses=best_comp.tool_uses,
            ))
        else:
            logger.warning(
                "Unpaired invocation for %s at %s (no matching completion)",
                inv.subagent_type,
                inv.timestamp,
            )

    return timings


def load_timing_history(history_path: Path) -> dict[str, list[float]]:
    """Load historical timing data from JSONL file.

    Each line is a JSON object with keys: agent_type, wall_clock_seconds, timestamp.

    Args:
        history_path: Path to the JSONL history file.

    Returns:
        Dict mapping agent_type to list of past durations (seconds).
        Returns empty dict if file is missing or unreadable.
    """
    result: dict[str, list[float]] = {}

    if not history_path.exists():
        return result

    try:
        text = history_path.read_text().strip()
    except (OSError, IOError) as e:
        logger.warning("Cannot read timing history at %s: %s", history_path, e)
        return result

    if not text:
        return result

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            agent_type = entry.get("agent_type", "")
            duration = float(entry.get("wall_clock_seconds", 0))
            if agent_type and duration > 0:
                result.setdefault(agent_type, []).append(duration)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return result


def save_timing_entry(
    timings: list[AgentTiming],
    history_path: Path,
) -> None:
    """Append current run's timings to history JSONL file.

    Thread-safe. Keeps at most MAX_HISTORY_PER_AGENT entries per agent type.

    Args:
        timings: List of AgentTiming from the current run.
        history_path: Path to the JSONL history file.
    """
    with _history_lock:
        # Load existing history
        existing_lines: list[dict] = []
        if history_path.exists():
            try:
                text = history_path.read_text().strip()
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing_lines.append(json.loads(line))
                    except (json.JSONDecodeError, TypeError):
                        continue
            except (OSError, IOError) as e:
                logger.warning("Cannot read history for save: %s", e)

        # Add new entries
        for t in timings:
            existing_lines.append({
                "agent_type": t.agent_type,
                "wall_clock_seconds": t.wall_clock_seconds,
                "result_word_count": t.result_word_count,
                "total_tokens": t.total_tokens,
                "tool_uses": t.tool_uses,
                "timestamp": t.invocation_ts,
            })

        # Cap per agent
        per_agent: dict[str, list[dict]] = {}
        for entry in existing_lines:
            agent = entry.get("agent_type", "")
            if agent:
                per_agent.setdefault(agent, []).append(entry)

        # Keep only last MAX_HISTORY_PER_AGENT per agent
        capped_lines: list[dict] = []
        for agent, entries in per_agent.items():
            capped_lines.extend(entries[-MAX_HISTORY_PER_AGENT:])

        # Write back
        try:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(history_path, "w") as f:
                for entry in capped_lines:
                    f.write(json.dumps(entry) + "\n")
        except (OSError, IOError) as e:
            logger.warning("Cannot write timing history: %s", e)


def load_full_timing_history(history_path: Path) -> dict[str, list[dict]]:
    """Load complete historical timing entries from JSONL file, grouped by agent_type.

    Unlike load_timing_history() which returns only durations, this returns
    the full entry dicts including token data fields. Entries missing token
    fields default to 0 for total_tokens and tool_uses.

    Args:
        history_path: Path to the JSONL history file.

    Returns:
        Dict mapping agent_type to list of entry dicts.
        Returns empty dict if file is missing or unreadable.
    """
    result: dict[str, list[dict]] = {}

    if not history_path.exists():
        return result

    try:
        text = history_path.read_text().strip()
    except (OSError, IOError) as e:
        logger.warning("Cannot read timing history at %s: %s", history_path, e)
        return result

    if not text:
        return result

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            agent_type = entry.get("agent_type", "")
            if not agent_type:
                continue
            # Ensure token fields have defaults
            entry.setdefault("total_tokens", 0)
            entry.setdefault("tool_uses", 0)
            entry.setdefault("wall_clock_seconds", 0)
            entry.setdefault("result_word_count", 0)
            result.setdefault(agent_type, []).append(entry)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return result


def compute_adaptive_thresholds(
    history: dict[str, list[float]],
    *,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> dict[str, float | None]:
    """Compute adaptive thresholds from historical timing data.

    Returns the rolling p95 * ADAPTIVE_P95_MULTIPLIER for each agent type.
    Returns None for agents with fewer than min_observations data points.

    Args:
        history: Dict mapping agent_type to list of past durations.
        min_observations: Minimum number of observations required.

    Returns:
        Dict mapping agent_type to adaptive threshold (seconds) or None.
    """
    result: dict[str, float | None] = {}

    for agent_type, durations in history.items():
        if len(durations) < min_observations:
            result[agent_type] = None
        else:
            sorted_durations = sorted(durations)
            p95_index = int(len(sorted_durations) * 0.95)
            p95_index = min(p95_index, len(sorted_durations) - 1)
            p95_value = sorted_durations[p95_index]
            result[agent_type] = p95_value * ADAPTIVE_P95_MULTIPLIER

    return result


def analyze_timings(
    timings: list[AgentTiming],
    *,
    history_path: Path | None = None,
) -> list[TimingFinding]:
    """Analyze agent timings and produce findings for anomalies.

    Classification rules:
    - GHOST: duration < 10s AND result_word_count < 50
    - WASTEFUL: words_per_second < 1.0 AND duration > 60s
    - SLOW: duration > threshold (static or adaptive)

    Adaptive thresholds (p95 * 1.5 from history) take precedence over
    static thresholds when enough historical data is available.

    Args:
        timings: List of AgentTiming from the current run.
        history_path: Optional path to historical timing JSONL file.
            If None, only static thresholds are used.

    Returns:
        List of TimingFinding for each detected anomaly.
    """
    findings: list[TimingFinding] = []

    # Load adaptive thresholds if history available
    adaptive: dict[str, float | None] = {}
    if history_path is not None:
        history = load_timing_history(history_path)
        adaptive = compute_adaptive_thresholds(history)

    for t in timings:
        # Ghost detection: very short, very little output
        if t.wall_clock_seconds < GHOST_MAX_DURATION and t.result_word_count < GHOST_MAX_WORDS:
            findings.append(TimingFinding(
                agent_type=t.agent_type,
                finding_type="GHOST",
                actual_seconds=t.wall_clock_seconds,
                threshold_seconds=GHOST_MAX_DURATION,
                threshold_type="static",
                result_word_count=t.result_word_count,
                recommendation=(
                    f"{t.agent_type} completed in {t.wall_clock_seconds:.1f}s with only "
                    f"{t.result_word_count} words. May have failed silently or been skipped."
                ),
            ))
            continue

        # Wasteful detection: slow but low output
        if t.wall_clock_seconds > WASTEFUL_MIN_DURATION and t.result_word_count > 0:
            wps = t.result_word_count / t.wall_clock_seconds
            if wps < WASTEFUL_WPS_THRESHOLD:
                findings.append(TimingFinding(
                    agent_type=t.agent_type,
                    finding_type="WASTEFUL",
                    actual_seconds=t.wall_clock_seconds,
                    threshold_seconds=WASTEFUL_MIN_DURATION,
                    threshold_type="static",
                    result_word_count=t.result_word_count,
                    recommendation=(
                        f"{t.agent_type} took {t.wall_clock_seconds:.1f}s but produced only "
                        f"{t.result_word_count} words ({wps:.2f} words/sec). "
                        f"Consider reducing scope or improving prompt efficiency."
                    ),
                ))
                continue

        # Slow detection: check adaptive first, then static
        threshold: float | None = None
        threshold_type = "static"

        adaptive_val = adaptive.get(t.agent_type)
        if adaptive_val is not None:
            threshold = adaptive_val
            threshold_type = "adaptive"
        else:
            static_entry = STATIC_THRESHOLDS.get(t.agent_type)
            if static_entry is not None:
                threshold = float(static_entry[0])

        if threshold is not None and t.wall_clock_seconds > threshold:
            finding_type = "SLOW"
            recommendation = (
                f"{t.agent_type} took {t.wall_clock_seconds:.1f}s "
                f"(threshold: {threshold:.1f}s, {threshold_type}). "
                f"Consider investigating performance bottlenecks."
            )
            findings.append(TimingFinding(
                agent_type=t.agent_type,
                finding_type=finding_type,
                actual_seconds=t.wall_clock_seconds,
                threshold_seconds=threshold,
                threshold_type=threshold_type,
                result_word_count=t.result_word_count,
                recommendation=recommendation,
            ))

        # Token efficiency detection (Issue #704)
        if t.total_tokens > 0 and t.result_word_count > 0:
            tokens_per_word = t.total_tokens / t.result_word_count
            if tokens_per_word > 500:
                findings.append(TimingFinding(
                    agent_type=t.agent_type,
                    finding_type="TOKEN_EFFICIENCY",
                    actual_seconds=t.wall_clock_seconds,
                    threshold_seconds=0,
                    threshold_type="token_ratio",
                    result_word_count=t.result_word_count,
                    recommendation=(
                        f"{t.agent_type} used {t.total_tokens} tokens to produce "
                        f"{t.result_word_count} words ({tokens_per_word:.0f} tokens/word). "
                        f"Consider using a smaller model tier (Haiku/Sonnet) for this agent."
                    ),
                ))

    return findings


def format_timing_report(
    timings: list[AgentTiming],
    findings: list[TimingFinding],
    *,
    recoveries: "Optional[list[PromptIntegrityRecovery]]" = None,
    blocked_without_recovery: int = 0,
) -> str:
    """Format timing data and findings as a Markdown report.

    Args:
        timings: List of AgentTiming from the current run.
        findings: List of TimingFinding from analysis.
        recoveries: Optional list of PromptIntegrityRecovery rows
            (Issue #1178). When non-None and non-empty, a new
            "Prompt-Integrity Recovery Overhead" section is appended.
            Defaults to None for backward-compatibility with all existing
            callers.
        blocked_without_recovery: Count of prompt_integrity_block events
            that had no matching recovery row. Reported alongside
            recoveries when the recovery section is rendered.

    Returns:
        Markdown-formatted report string with timing table and findings.
    """
    lines: list[str] = []
    lines.append("## Pipeline Timing Report")
    lines.append("")

    has_tokens = any(t.total_tokens > 0 for t in timings)

    if has_tokens:
        lines.append("| Agent | Duration (s) | Words | Words/sec | Tokens | Tok/Word | Step |")
        lines.append("|-------|-------------|-------|-----------|--------|----------|------|")
    else:
        lines.append("| Agent | Duration (s) | Words | Words/sec | Step |")
        lines.append("|-------|-------------|-------|-----------|------|")

    for t in sorted(timings, key=lambda x: x.step_number):
        wps = t.result_word_count / t.wall_clock_seconds if t.wall_clock_seconds > 0 else 0
        if has_tokens:
            tpw = t.total_tokens / t.result_word_count if t.result_word_count > 0 else 0
            lines.append(
                f"| {t.agent_type} | {t.wall_clock_seconds:.1f} | "
                f"{t.result_word_count} | {wps:.1f} | "
                f"{t.total_tokens} | {tpw:.1f} | {t.step_number} |"
            )
        else:
            lines.append(
                f"| {t.agent_type} | {t.wall_clock_seconds:.1f} | "
                f"{t.result_word_count} | {wps:.1f} | {t.step_number} |"
            )

    if findings:
        lines.append("")
        lines.append("### Findings")
        lines.append("")
        for f in findings:
            lines.append(
                f"- **{f.finding_type}** ({f.agent_type}): "
                f"{f.recommendation}"
            )

    total_duration = sum(t.wall_clock_seconds for t in timings)
    lines.append("")
    lines.append(f"**Total pipeline duration**: {total_duration:.1f}s")

    # Issue #1178: Prompt-integrity recovery overhead section. Default-None
    # preserves backward-compat for the dozens of existing callers.
    if recoveries:
        total_ms = sum(r.latency_ms for r in recoveries)
        mean_ms = total_ms // len(recoveries) if recoveries else 0

        def _fmt_ms(ms: int) -> str:
            seconds = ms // 1000
            minutes = seconds // 60
            remainder = seconds % 60
            if minutes > 0:
                return f"{minutes}m {remainder}s ({ms:,} ms)"
            return f"{seconds}s ({ms:,} ms)"

        agent_counts: dict[str, int] = {}
        for r in recoveries:
            agent_counts[r.agent_type] = agent_counts.get(r.agent_type, 0) + 1
        breakdown = ", ".join(
            f"{agent}={count}"
            for agent, count in sorted(agent_counts.items())
        )

        lines.append("")
        lines.append("## Prompt-Integrity Recovery Overhead")
        lines.append(f"- Total recoveries: {len(recoveries)}")
        lines.append(f"- Total overhead: {_fmt_ms(total_ms)}")
        lines.append(f"- Mean per recovery: {_fmt_ms(mean_ms)}")
        lines.append(
            f"- Blocks without observed recovery: {blocked_without_recovery}"
        )
        lines.append(f"- Breakdown by agent: {breakdown}")

    return "\n".join(lines)


def _sanitize_markdown(text: str) -> str:
    """Sanitize text for safe inclusion in GitHub issue Markdown.

    Strips CRLF, escapes Markdown special characters in code context,
    and caps length at 2000 characters.

    Args:
        text: Raw text to sanitize.

    Returns:
        Sanitized text safe for Markdown.
    """
    # Strip CRLF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove control characters except newline
    text = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", text)
    # Cap at 2000 chars
    if len(text) > 2000:
        text = text[:1997] + "..."
    return text


def format_issue_body(
    finding: TimingFinding,
    run_date: str,
    session_id: str,
) -> str:
    """Format a TimingFinding as a GitHub issue body.

    Args:
        finding: The timing finding to format.
        run_date: ISO date string of the pipeline run.
        session_id: Session identifier for the run.

    Returns:
        Sanitized Markdown body for a GitHub issue.
    """
    body_parts = [
        f"## Timing Analysis Finding",
        f"",
        f"**Agent**: {finding.agent_type}",
        f"**Finding**: {finding.finding_type}",
        f"**Run Date**: {run_date}",
        f"**Session**: {session_id}",
        f"",
        f"### Details",
        f"",
        f"```",
        f"Actual duration:    {finding.actual_seconds:.1f}s",
        f"Threshold:          {finding.threshold_seconds:.1f}s ({finding.threshold_type})",
        f"Result word count:  {finding.result_word_count}",
        f"```",
        f"",
        f"### Recommendation",
        f"",
        f"{finding.recommendation}",
    ]

    body = "\n".join(body_parts)
    return _sanitize_markdown(body)


def check_consecutive_violations(
    agent_type: str,
    history_path: Path,
    threshold: float,
) -> int:
    """Count consecutive recent runs where an agent exceeded a threshold.

    Reads the history file and counts backward from the most recent entry
    for the given agent_type, counting how many consecutive entries exceeded
    the threshold.

    Args:
        agent_type: The agent type to check.
        history_path: Path to the JSONL history file.
        threshold: Duration threshold in seconds.

    Returns:
        Number of consecutive recent violations. 0 if no history.
    """
    history = load_timing_history(history_path)
    durations = history.get(agent_type, [])

    if not durations:
        return 0

    count = 0
    for duration in reversed(durations):
        if duration > threshold:
            count += 1
        else:
            break

    return count


# ---------------------------------------------------------------------------
# Per-agent time budget functions (Issue #705)
# ---------------------------------------------------------------------------

# Module-level cache for loaded budgets (reset to None to force reload)
_cached_budgets: dict[str, dict] | None = None

# Default config path relative to this file's location
_DEFAULT_BUDGET_CONFIG = Path(__file__).parent.parent / "config" / "pipeline_time_budgets.json"


def load_time_budgets(config_path: Path | None = None) -> dict[str, dict]:
    """Load per-agent time budgets from config file, falling back to STATIC_THRESHOLDS.

    Args:
        config_path: Path to pipeline_time_budgets.json. Defaults to the canonical
            config location next to this library. Pass a nonexistent path to force
            the static fallback (useful in tests).

    Returns:
        Dict mapping agent_type -> {"budget_seconds": int, "warning_pct": float}.
        Never returns an empty dict — falls back to STATIC_THRESHOLDS if config
        file is missing or invalid.
    """
    global _cached_budgets

    # Use provided path or canonical default
    path = config_path if config_path is not None else _DEFAULT_BUDGET_CONFIG

    # Only use cache when using the default path
    if config_path is None and _cached_budgets is not None:
        return _cached_budgets

    budgets: dict[str, dict] = {}

    if path.exists():
        try:
            raw = json.loads(path.read_text())
            for key, val in raw.items():
                # Skip comment/metadata keys
                if key.startswith("_"):
                    continue
                if isinstance(val, dict) and "budget_seconds" in val and "warning_pct" in val:
                    budgets[key] = {
                        "budget_seconds": float(val["budget_seconds"]),
                        "warning_pct": float(val["warning_pct"]),
                    }
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            logger.warning("Failed to load time budgets from %s: %s — using static fallback", path, exc)

    # Fall back to STATIC_THRESHOLDS for any missing agents (or full fallback)
    for agent_type, (max_seconds, _min_words) in STATIC_THRESHOLDS.items():
        if agent_type not in budgets:
            budgets[agent_type] = {
                "budget_seconds": float(max_seconds),
                "warning_pct": 0.8,
            }

    # Cache the result when using the default path
    if config_path is None:
        _cached_budgets = budgets

    return budgets


def check_budget_violation(
    agent_type: str,
    duration_seconds: float,
    budgets: dict[str, dict] | None = None,
) -> dict | None:
    """Check whether an agent duration exceeds its time budget.

    Args:
        agent_type: The agent type to check (e.g. "implementer").
        duration_seconds: Measured duration in seconds. Values <= 0 are ignored.
        budgets: Budget dict from load_time_budgets(). Loaded from config if None.

    Returns:
        None if within budget, or a violation dict with keys:
            - level: "warning" (>= warning threshold) or "exceeded" (> budget)
            - agent_type: str
            - duration: float (seconds)
            - budget: float (budget_seconds)
            - pct_used: float (0.0–1.0+)
    """
    if duration_seconds <= 0:
        return None

    if budgets is None:
        budgets = load_time_budgets()

    agent_budget = budgets.get(agent_type)
    if agent_budget is None:
        return None

    budget_seconds = agent_budget["budget_seconds"]
    warning_pct = agent_budget["warning_pct"]
    pct_used = duration_seconds / budget_seconds

    if pct_used > 1.0:
        return {
            "level": "exceeded",
            "agent_type": agent_type,
            "duration": duration_seconds,
            "budget": budget_seconds,
            "pct_used": pct_used,
        }
    elif pct_used >= warning_pct:
        return {
            "level": "warning",
            "agent_type": agent_type,
            "duration": duration_seconds,
            "budget": budget_seconds,
            "pct_used": pct_used,
        }

    return None


def format_budget_warning(violation: dict) -> str:
    """Format a human-readable budget warning message (stick+carrot pattern).

    Args:
        violation: Dict returned by check_budget_violation().

    Returns:
        Formatted warning string with REQUIRED NEXT ACTION directive.
    """
    agent_type = violation["agent_type"]
    duration = violation["duration"]
    budget = violation["budget"]
    pct_used = violation["pct_used"]
    level = violation["level"]

    pct_display = f"{pct_used * 100:.0f}%"
    duration_display = f"{duration:.1f}s"
    budget_display = f"{budget:.0f}s"

    if level == "exceeded":
        prefix = f"[BUDGET-EXCEEDED] {agent_type}: {duration_display} used, budget {budget_display} ({pct_display} of budget)"
        action = (
            "REQUIRED NEXT ACTION: "
            "Review this agent's task scope — it ran over its time budget. "
            "Consider breaking the task into smaller steps or raising the budget "
            f"for {agent_type} in plugins/autonomous-dev/config/pipeline_time_budgets.json."
        )
    else:
        prefix = f"[BUDGET-WARNING] {agent_type}: {duration_display} used, budget {budget_display} ({pct_display} of budget)"
        action = (
            "REQUIRED NEXT ACTION: "
            "Monitor this agent — it is approaching its time budget. "
            "If this pattern repeats, review task scope or adjust "
            f"budget_seconds for {agent_type} in plugins/autonomous-dev/config/pipeline_time_budgets.json."
        )

    return f"{prefix}\n{action}"
