#!/usr/bin/env python3
"""
Agent Output Health Library - Issues #793, #792

Provides zero-word detection, per-agent health verdicts, and batch health
summary generation for agent completions. Complements the existing ghost
detection in pipeline_intent_validator.py with CRITICAL-severity zero-word
detection and structured per-agent health reporting.

Usage:
    from agent_output_health import (
        check_agent_output_health,
        detect_zero_word_completions,
        generate_batch_health_summary,
    )
"""

from dataclasses import dataclass
from typing import List

from pipeline_intent_validator import Finding, PipelineEvent

# Tool names for agent invocations (matches pipeline_intent_validator)
AGENT_TOOL_NAMES = {"Task", "Agent"}

# Per-agent minimum word thresholds. Security-critical agents require higher
# minimums. Agents not listed here use DEFAULT_MIN_WORDS.
AGENT_MIN_WORD_THRESHOLDS: dict[str, int] = {
    "security-auditor": 50,
    "reviewer": 50,
    "doc-master": 30,
    "implementer": 50,
    "planner": 50,
    "researcher": 30,
    "researcher-local": 30,
}

# Completions under 5s with 0 words are classified as ghosts. Tighter than
# the 10s threshold in detect_ghost_invocations because zero-word output
# is unambiguous.
GHOST_MAX_DURATION_MS: int = 5000

# Default minimum word threshold for agents not in AGENT_MIN_WORD_THRESHOLDS.
DEFAULT_MIN_WORDS: int = 10


@dataclass
class AgentHealthVerdict:
    """Health assessment of a single agent completion.

    Attributes:
        agent_type: The subagent_type from the pipeline event.
        word_count: Number of words in the agent's output.
        duration_ms: How long the agent ran in milliseconds.
        status: One of "healthy", "ghost", "zero_output", "shallow".
        timestamp: ISO timestamp of the completion event.
    """

    agent_type: str
    word_count: int
    duration_ms: int
    status: str  # "healthy", "ghost", "zero_output", "shallow"
    timestamp: str = ""


def _get_agent_completions(events: List[PipelineEvent]) -> List[PipelineEvent]:
    """Filter events to agent_completion events only.

    Invocation events always have result_word_count=0 and would cause
    false positives. Only completion events reflect actual agent output.
    Issue #1266: also exclude internal `__dedup_skip__:*` hook markers —
    these are dedup-tracking events, not real agent invocations, and they
    produce false-positive zero_word_agent_output findings.
    """
    return [
        e for e in events
        if e.tool in AGENT_TOOL_NAMES
        and e.subagent_type
        and not e.subagent_type.startswith("__dedup_skip__")
        and e.pipeline_action == "agent_completion"
    ]


def check_agent_output_health(
    events: List[PipelineEvent],
) -> List[AgentHealthVerdict]:
    """Evaluate all agent_completion events and return per-event health verdicts.

    Args:
        events: List of PipelineEvent from a session log.

    Returns:
        List of AgentHealthVerdict, one per agent_completion event.
    """
    completions = _get_agent_completions(events)
    verdicts: List[AgentHealthVerdict] = []

    for event in completions:
        threshold = AGENT_MIN_WORD_THRESHOLDS.get(
            event.subagent_type, DEFAULT_MIN_WORDS
        )

        if event.result_word_count == 0 and event.duration_ms < GHOST_MAX_DURATION_MS:
            status = "ghost"
        elif event.result_word_count == 0:
            status = "zero_output"
        elif event.result_word_count < threshold:
            status = "shallow"
        else:
            status = "healthy"

        verdicts.append(AgentHealthVerdict(
            agent_type=event.subagent_type,
            word_count=event.result_word_count,
            duration_ms=event.duration_ms,
            status=status,
            timestamp=event.timestamp,
        ))

    return verdicts


def detect_zero_word_completions(
    events: List[PipelineEvent],
) -> List[Finding]:
    """Find completions with result_word_count == 0 regardless of duration.

    This is the core fix for issue #793: zero-word agent completions are
    unambiguous failures and always CRITICAL.

    Args:
        events: List of PipelineEvent from a session log.

    Returns:
        List of CRITICAL findings for zero-word completions.
    """
    completions = _get_agent_completions(events)
    findings: List[Finding] = []

    for event in completions:
        if event.result_word_count == 0:
            findings.append(Finding(
                finding_type="zero_word_agent_output",
                severity="CRITICAL",
                pattern_id="zero_word_agent_output",
                description=(
                    f"Agent {event.subagent_type} completed with 0 words "
                    f"in {event.duration_ms}ms — no meaningful output produced"
                ),
                evidence=[
                    f"agent_type: {event.subagent_type}",
                    f"duration_ms: {event.duration_ms}",
                    f"result_word_count: {event.result_word_count}",
                ],
            ))

    return findings


def generate_batch_health_summary(
    events: List[PipelineEvent],
) -> dict:
    """Aggregate per-agent statistics from agent_completion events.

    Args:
        events: List of PipelineEvent from a batch session.

    Returns:
        Dict keyed by agent_type with per-agent stats:
        invocation_count, ghost_count, zero_word_count,
        avg_word_count, total_word_count.
    """
    completions = _get_agent_completions(events)

    if not completions:
        return {}

    summary: dict[str, dict] = {}

    for event in completions:
        agent = event.subagent_type
        if agent not in summary:
            summary[agent] = {
                "invocation_count": 0,
                "ghost_count": 0,
                "zero_word_count": 0,
                "avg_word_count": 0.0,
                "total_word_count": 0,
            }

        stats = summary[agent]
        stats["invocation_count"] += 1
        stats["total_word_count"] += event.result_word_count

        if event.result_word_count == 0:
            stats["zero_word_count"] += 1
            if event.duration_ms < GHOST_MAX_DURATION_MS:
                stats["ghost_count"] += 1

    # Calculate averages
    for agent, stats in summary.items():
        count = stats["invocation_count"]
        stats["avg_word_count"] = stats["total_word_count"] / count if count > 0 else 0.0

    return summary
