#!/usr/bin/env python3
"""
Pipeline Intent Validator - Issue #367

Parses JSONL session logs and validates that the /implement pipeline
coordinator followed step contracts: sequential ordering, hard gate
enforcement, context passing, and correct parallelization.

Used by the continuous-improvement-analyst agent (quality check #8).

Usage:
    from pipeline_intent_validator import validate_pipeline_intent
    findings = validate_pipeline_intent(Path("logs/2026-02-28.jsonl"))
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class PipelineEvent:
    """A pipeline-relevant event from session logs."""

    timestamp: str
    tool: str
    agent: str
    subagent_type: str
    pipeline_action: str
    prompt_word_count: int = 0
    result_word_count: int = 0
    success: bool = True


@dataclass
class Finding:
    """A pipeline intent violation finding."""

    finding_type: str  # e.g. "step_ordering", "hard_gate_ordering", "context_dropping"
    severity: str  # CRITICAL, WARNING, INFO
    pattern_id: str  # e.g. "implementer_before_planner"
    description: str
    evidence: list = field(default_factory=list)


# Canonical step ordering: agent type → step index
# Agents with the same index are allowed to run in parallel
STEP_ORDER = {
    "researcher-local": 2,
    "researcher": 2,
    "planner": 3,
    "test-master": 4,
    "implementer": 5,
    "reviewer": 6,
    "security-auditor": 6,
    "doc-master": 6,
}

# Agent pairs that MUST be sequential (first must complete before second starts)
SEQUENTIAL_REQUIRED = [
    ("planner", "test-master"),
    ("planner", "implementer"),
    ("test-master", "implementer"),
    ("implementer", "reviewer"),
    ("implementer", "security-auditor"),
    ("implementer", "doc-master"),
]

# Agent pairs that SHOULD be parallel (efficiency check)
PARALLEL_EXPECTED = [
    ("researcher-local", "researcher"),
    # reviewer, security-auditor, doc-master are also parallel but checked differently
]

# STEP 6 agents that must wait for test gate
STEP6_AGENTS = {"reviewer", "security-auditor", "doc-master"}

# Minimum agents to consider this a full pipeline run
MIN_FULL_PIPELINE_AGENTS = 4

# Timestamp window for considering agents "parallel" (seconds)
TIMESTAMP_WINDOW_SECONDS = 5

# Threshold for parallel serialization detection (seconds)
PARALLEL_SERIALIZED_THRESHOLD = 30


def parse_session_logs(
    log_path: Path,
    *,
    session_id: Optional[str] = None,
) -> List[PipelineEvent]:
    """Parse JSONL session log into pipeline-relevant events.

    Args:
        log_path: Path to JSONL log file.
        session_id: Optional session ID filter.

    Returns:
        List of PipelineEvent sorted by timestamp.
    """
    events: List[PipelineEvent] = []

    if not log_path.exists():
        return events

    text = log_path.read_text().strip()
    if not text:
        return events

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Filter by session
        if session_id and entry.get("session_id") != session_id:
            continue

        tool = entry.get("tool", "")
        input_summary = entry.get("input_summary", {})
        output_summary = entry.get("output_summary", {})
        pipeline_action = input_summary.get("pipeline_action", "")

        # Include Task (agent invocations) and Bash test_run events
        if tool == "Task" and pipeline_action == "agent_invocation":
            events.append(PipelineEvent(
                timestamp=entry.get("timestamp", ""),
                tool=tool,
                agent=entry.get("agent", "main"),
                subagent_type=input_summary.get("subagent_type", ""),
                pipeline_action=pipeline_action,
                prompt_word_count=input_summary.get("prompt_word_count", 0),
                result_word_count=output_summary.get("result_word_count", 0),
                success=output_summary.get("success", True),
            ))
        elif tool == "Bash" and pipeline_action == "test_run":
            events.append(PipelineEvent(
                timestamp=entry.get("timestamp", ""),
                tool=tool,
                agent=entry.get("agent", "main"),
                subagent_type="",
                pipeline_action="test_run",
                success=output_summary.get("success", True),
            ))

    # Sort by timestamp
    events.sort(key=lambda e: e.timestamp)
    return events


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime."""
    try:
        # Handle various ISO formats
        ts = ts.replace("+00:00", "+0000").replace("Z", "+0000")
        if "+" in ts[10:]:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
        return datetime.fromisoformat(ts)
    except (ValueError, IndexError):
        return None


def _seconds_between(ts1: str, ts2: str) -> Optional[float]:
    """Get seconds between two timestamps."""
    dt1 = _parse_timestamp(ts1)
    dt2 = _parse_timestamp(ts2)
    if dt1 is None or dt2 is None:
        return None
    return abs((dt2 - dt1).total_seconds())


def validate_step_ordering(events: List[PipelineEvent]) -> List[Finding]:
    """Validate that pipeline steps executed in correct order.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for ordering violations.
    """
    findings: List[Finding] = []

    # Filter to agent invocations with known step assignments
    agent_events = [
        e for e in events
        if e.tool == "Task" and e.subagent_type in STEP_ORDER
    ]

    # Need at least 2 agents to check ordering
    if len(agent_events) < 2:
        return findings

    # Check for missing required sequential steps (only for full pipelines)
    agent_types_present = {e.subagent_type for e in agent_events}
    core_steps = {"planner", "implementer"}
    if len(agent_events) >= MIN_FULL_PIPELINE_AGENTS and core_steps.issubset(agent_types_present):
        # Check if test-master is missing (should be between planner and implementer)
        if "test-master" not in agent_types_present:
            findings.append(Finding(
                finding_type="step_skipping",
                severity="CRITICAL",
                pattern_id="step_skipping_test_master",
                description="test-master agent not invoked between planner and implementer",
                evidence=[f"Agents present: {sorted(agent_types_present)}"],
            ))

    # Check ordering: for each sequential pair, verify first completed before second
    for first_type, second_type in SEQUENTIAL_REQUIRED:
        first_events = [e for e in agent_events if e.subagent_type == first_type]
        second_events = [e for e in agent_events if e.subagent_type == second_type]

        if not first_events or not second_events:
            continue

        # Use earliest timestamp for each
        first_ts = first_events[0].timestamp
        second_ts = second_events[0].timestamp

        if second_ts < first_ts:
            findings.append(Finding(
                finding_type="step_ordering",
                severity="CRITICAL",
                pattern_id="step_ordering",
                description=f"{second_type} ran before {first_type} (expected {first_type} first)",
                evidence=[
                    f"{first_type} at {first_ts}",
                    f"{second_type} at {second_ts}",
                ],
            ))

    return findings


def detect_hard_gate_ordering(events: List[PipelineEvent]) -> List[Finding]:
    """Detect STEP 6 agents running before STEP 5 test gate passes.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for hard gate ordering violations.
    """
    findings: List[Finding] = []

    # Find STEP 6 agent events
    step6_events = [e for e in events if e.subagent_type in STEP6_AGENTS]
    if not step6_events:
        return findings

    # Find successful test_run events
    test_runs = [e for e in events if e.pipeline_action == "test_run"]
    successful_test_runs = [e for e in test_runs if e.success]

    # No pytest at all but STEP 6 ran
    if not test_runs and step6_events:
        findings.append(Finding(
            finding_type="hard_gate_ordering",
            severity="CRITICAL",
            pattern_id="hard_gate_ordering_bypass",
            description="STEP 6 validation agents ran without any pytest execution (STEP 5 test gate skipped)",
            evidence=[f"STEP 6 agents: {[e.subagent_type for e in step6_events]}"],
        ))
        return findings

    # Pytest ran but failed, and STEP 6 still ran
    if test_runs and not successful_test_runs and step6_events:
        findings.append(Finding(
            finding_type="hard_gate_ordering",
            severity="CRITICAL",
            pattern_id="hard_gate_ordering_bypass",
            description="STEP 6 validation agents ran after pytest failed (STEP 5 test gate not passed)",
            evidence=[
                f"test_run at {test_runs[0].timestamp} success=False",
                f"First STEP 6 agent: {step6_events[0].subagent_type} at {step6_events[0].timestamp}",
            ],
        ))
        return findings

    # Check if any STEP 6 agent ran before the first successful pytest
    if successful_test_runs:
        first_pass_ts = successful_test_runs[0].timestamp
        early_step6 = [e for e in step6_events if e.timestamp < first_pass_ts]
        if early_step6:
            findings.append(Finding(
                finding_type="hard_gate_ordering",
                severity="CRITICAL",
                pattern_id="hard_gate_ordering_bypass",
                description="STEP 6 agents launched before STEP 5 pytest passed",
                evidence=[
                    f"First passing test_run: {first_pass_ts}",
                    f"Early STEP 6 agents: {[(e.subagent_type, e.timestamp) for e in early_step6]}",
                ],
            ))

    return findings


def detect_context_dropping(
    events: List[PipelineEvent],
    *,
    threshold: float = 0.2,
) -> List[Finding]:
    """Detect when agent prompts are much smaller than prior agent results.

    Args:
        events: List of PipelineEvent sorted by timestamp.
        threshold: Minimum prompt/result ratio (below = context dropping).

    Returns:
        List of findings for context dropping.
    """
    findings: List[Finding] = []

    # Filter to agent invocations only
    agent_events = [e for e in events if e.tool == "Task" and e.subagent_type]

    for i in range(1, len(agent_events)):
        prev = agent_events[i - 1]
        curr = agent_events[i]

        # Skip if word counts are missing/zero
        if prev.result_word_count == 0 or curr.prompt_word_count == 0:
            continue

        ratio = curr.prompt_word_count / prev.result_word_count
        if ratio < threshold:
            findings.append(Finding(
                finding_type="context_dropping",
                severity="WARNING",
                pattern_id="context_dropping",
                description=(
                    f"Agent {curr.subagent_type} prompt ({curr.prompt_word_count} words) is "
                    f"{ratio:.1%} of {prev.subagent_type} result ({prev.result_word_count} words) "
                    f"— possible context summarization (threshold: {threshold:.0%})"
                ),
                evidence=[
                    f"{prev.subagent_type} result_word_count: {prev.result_word_count}",
                    f"{curr.subagent_type} prompt_word_count: {curr.prompt_word_count}",
                    f"Ratio: {ratio:.3f} (threshold: {threshold})",
                ],
            ))

    return findings


def detect_parallelization_violations(events: List[PipelineEvent]) -> List[Finding]:
    """Detect incorrect parallelization of pipeline steps.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for parallelization violations.
    """
    findings: List[Finding] = []

    agent_events = [e for e in events if e.tool == "Task" and e.subagent_type]

    # Build lookup: agent_type → earliest timestamp
    agent_timestamps: dict[str, str] = {}
    for e in agent_events:
        if e.subagent_type not in agent_timestamps:
            agent_timestamps[e.subagent_type] = e.timestamp

    # Check sequential pairs that were incorrectly parallelized
    for first_type, second_type in SEQUENTIAL_REQUIRED:
        if first_type not in agent_timestamps or second_type not in agent_timestamps:
            continue

        gap = _seconds_between(agent_timestamps[first_type], agent_timestamps[second_type])
        if gap is not None and gap <= TIMESTAMP_WINDOW_SECONDS:
            findings.append(Finding(
                finding_type="parallelization_violation",
                severity="CRITICAL",
                pattern_id="sequential_step_parallelized",
                description=(
                    f"{first_type} and {second_type} launched within {gap:.0f}s "
                    f"(must be sequential — {first_type} must complete before {second_type})"
                ),
                evidence=[
                    f"{first_type} at {agent_timestamps[first_type]}",
                    f"{second_type} at {agent_timestamps[second_type]}",
                    f"Gap: {gap:.1f}s (threshold: {TIMESTAMP_WINDOW_SECONDS}s)",
                ],
            ))

    # Check parallel pairs that were unnecessarily serialized
    for a_type, b_type in PARALLEL_EXPECTED:
        if a_type not in agent_timestamps or b_type not in agent_timestamps:
            continue

        gap = _seconds_between(agent_timestamps[a_type], agent_timestamps[b_type])
        if gap is not None and gap > PARALLEL_SERIALIZED_THRESHOLD:
            findings.append(Finding(
                finding_type="parallelization_suggestion",
                severity="INFO",
                pattern_id="parallel_step_serialized",
                description=(
                    f"{a_type} and {b_type} ran {gap:.0f}s apart "
                    f"(should be parallel for efficiency)"
                ),
                evidence=[
                    f"{a_type} at {agent_timestamps[a_type]}",
                    f"{b_type} at {agent_timestamps[b_type]}",
                    f"Gap: {gap:.1f}s (threshold: {PARALLEL_SERIALIZED_THRESHOLD}s)",
                ],
            ))

    return findings


def validate_pipeline_intent(
    log_path: Path,
    *,
    session_id: Optional[str] = None,
) -> List[Finding]:
    """Orchestrate all intent validation checks on a session log.

    Args:
        log_path: Path to JSONL log file.
        session_id: Optional session ID filter.

    Returns:
        Combined list of all findings.
    """
    events = parse_session_logs(log_path, session_id=session_id)
    if not events:
        return []

    findings: List[Finding] = []
    findings.extend(validate_step_ordering(events))
    findings.extend(detect_hard_gate_ordering(events))
    findings.extend(detect_context_dropping(events))
    findings.extend(detect_parallelization_violations(events))
    return findings
