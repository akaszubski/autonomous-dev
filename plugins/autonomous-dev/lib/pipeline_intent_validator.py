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


# Tool names for agent invocations — Claude Code renamed "Task" to "Agent"
# but old logs still use "Task". Accept both for backward compatibility.
AGENT_TOOL_NAMES = {"Task", "Agent"}


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
    duration_ms: int = 0
    success: bool = True
    agent_transcript_path: str = ""
    total_tokens: int = 0
    tool_uses: int = 0
    batch_issue_number: int = 0
    session_id: str = ""
    pipeline_mode: str = ""
    # Issue #902 / #904: events flagged as part of a remediation cycle
    # (e.g., reviewer re-invoked after BLOCKING findings) are excluded from
    # duplicate-agent ordering findings. The flag is populated from the
    # log entry's ``input_summary.remediation`` field when present.
    remediation: bool = False


@dataclass
class Finding:
    """A pipeline intent violation finding."""

    finding_type: str  # e.g. "step_ordering", "hard_gate_ordering", "context_dropping"
    severity: str  # CRITICAL, WARNING, INFO
    pattern_id: str  # e.g. "implementer_before_planner"
    description: str
    evidence: list = field(default_factory=list)
    recommended_action: Optional[str] = None


# Canonical step ordering: agent type → step index
# Agents with the same index are allowed to run in parallel
STEP_ORDER = {
    "researcher-local": 2,
    "researcher": 2,
    "planner": 3,
    "plan-critic": 3.5,
    "test-master": 4,
    "implementer": 5,
    "pytest-gate": 5.5,
    "reviewer": 6.0,
    "security-auditor": 6.1,
    "doc-master": 6.0,
}

# Agent pairs that MUST be sequential (first must complete before second starts)
SEQUENTIAL_REQUIRED = [
    ("planner", "plan-critic"),
    ("plan-critic", "implementer"),
    ("planner", "implementer"),
    ("implementer", "reviewer"),
    ("implementer", "security-auditor"),
    ("implementer", "doc-master"),
    ("pytest-gate", "reviewer"),
    ("pytest-gate", "security-auditor"),
    ("pytest-gate", "doc-master"),
    ("reviewer", "security-auditor"),
]

# TDD-first mode pairs: only enforced when test-master is in the pipeline.
# In acceptance-first mode (default), test-master is skipped entirely.
# Issue #636: unconditional enforcement blocked implementer in default mode.
TDD_FIRST_PAIRS = [
    ("planner", "test-master"),
    ("test-master", "implementer"),
]

# Agent pairs that SHOULD be parallel (efficiency check)
PARALLEL_EXPECTED = [
    ("researcher-local", "researcher"),
    # reviewer, security-auditor, doc-master are also parallel but checked differently
]

# STEP 6 agents that must wait for test gate
STEP6_AGENTS = {"reviewer", "security-auditor", "doc-master"}

# Pipeline modes that skip the planner step by design.
# Fix mode runs: implementer -> reviewer -> doc-master -> CIA (no planner).
PLANNER_EXEMPT_MODES = {"--fix", "fix"}

# File path patterns that require security-auditor review.
# Any Write/Edit to a matching path triggers the requirement.
# Broad substring matching is intentional — false positives are cheap (an extra
# security review), false negatives are expensive (missed security regression).
# Test file exclusion (tests/ prefix) is applied separately by callers.
SECURITY_SENSITIVE_PATTERNS = (
    # Infrastructure: core pipeline enforcement
    "hooks/",
    "lib/auto_approval_engine",
    "lib/tool_validator",
    "config/auto_approve_policy",
    "lib/security",
    # Application-domain: authentication and access control
    "auth",
    "crypto",
    "permission",
    "session",
    "token",
    "secret",
    "credential",
    "password",
    "oauth",
    "sso",
    "jwt",
    "rbac",
    # Application-domain: financial and transactional
    "trading",
    "payment",
    "billing",
    "financial",
    "transaction",
    "wallet",
    # Application-domain: database schema changes
    "migration",
    "alembic",
    # Environment and secrets files
    ".env",
)

# Minimum agents to consider this a full pipeline run
MIN_FULL_PIPELINE_AGENTS = 4

# Timestamp window for considering agents "parallel" (seconds)
TIMESTAMP_WINDOW_SECONDS = 5

# Threshold for parallel serialization detection (seconds)
PARALLEL_SERIALIZED_THRESHOLD = 30

# Agents whose prompts are security-critical and must not be compressed
COMPRESSION_CRITICAL_AGENTS = {
    "security-auditor",
    "reviewer",
    "researcher-local",
    "researcher",
    "implementer",
    "planner",
    "doc-master",
}

# Post-hoc progressive compression threshold (Issue #757).
# More generous than the real-time hook threshold (25%) because legitimate
# task-level variation causes different prompt sizes between issues.
# The real-time hook (unified_pre_tool.py) handles per-invocation enforcement;
# this post-hoc check catches only severe compression patterns.
MAX_PROMPT_SHRINKAGE_RATIO = 0.40

# Minimum prompt word count for security-critical agents
MIN_CRITICAL_AGENT_PROMPT_WORDS = 80

# Minimum word count for doc-master output to be considered a valid verdict
MIN_DOC_VERDICT_WORDS = 30

# Minimum word count for doc-master output to be considered a real semantic sweep
# (as opposed to a shallow CHANGELOG-only update). Issue #672.
MIN_DOC_SWEEP_WORDS = 100

# Known valid agent types for file path construction (security whitelist)
VALID_AGENT_TYPES = set(STEP_ORDER.keys())


def get_minimum_prompt_content(agent_type: str, agents_dir: Path) -> Optional[str]:
    """Read minimum prompt content from an agent's .md file on disk.

    Validates agent_type against VALID_AGENT_TYPES whitelist before
    constructing file paths. Returns the first ~200 words of the file
    as a minimum prompt baseline.

    Args:
        agent_type: Agent type string (must be in VALID_AGENT_TYPES).
        agents_dir: Path to the agents directory.

    Returns:
        First ~200 words of the agent's .md file, or None if invalid/missing.
    """
    if agent_type not in VALID_AGENT_TYPES:
        return None

    try:
        agent_file = agents_dir / f"{agent_type}.md"
        if not agent_file.exists():
            return None
        content = agent_file.read_text().strip()
        if not content:
            return None
        words = content.split()
        return " ".join(words[:200])
    except (OSError, IOError):
        return None


def _parse_single_log(
    log_path: Path,
    *,
    session_id: Optional[str] = None,
) -> List[PipelineEvent]:
    """Parse a single JSONL log file into pipeline events (internal helper)."""
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
        raw_input_summary = entry.get("input_summary", {})
        output_summary = entry.get("output_summary", {})

        # Guard against non-dict output_summary (e.g. legacy string values)
        if not isinstance(output_summary, dict):
            output_summary = {}

        # Handle non-dict input_summary: try to extract subagent_type from string
        # representation (e.g. "subagent_type: planner") so legacy / test-fixture
        # entries still produce parseable events. (Issue #587)
        if isinstance(raw_input_summary, dict):
            input_summary = raw_input_summary
        else:
            input_summary = {}
            if isinstance(raw_input_summary, str) and "subagent_type:" in raw_input_summary:
                # Parse simple "key: value" format from string input_summary
                for part in raw_input_summary.split(","):
                    part = part.strip()
                    if ":" in part:
                        k, _, v = part.partition(":")
                        input_summary[k.strip()] = v.strip()
                # If we found a subagent_type, synthesize pipeline_action
                if "subagent_type" in input_summary and "pipeline_action" not in input_summary:
                    input_summary["pipeline_action"] = "agent_invocation"

        pipeline_action = input_summary.get("pipeline_action", "")

        # Extract batch_issue_number from input_summary (default 0 = non-batch)
        batch_issue_number = input_summary.get("batch_issue_number", 0)
        if not isinstance(batch_issue_number, int):
            batch_issue_number = 0

        # Extract pipeline_mode from input_summary (e.g. "--fix", "--light", "full")
        # Used by ordering validator to skip planner->implementer check in --fix mode.
        # Issue #732.
        pipeline_mode = input_summary.get("pipeline_mode", "") if isinstance(input_summary, dict) else ""
        if not isinstance(pipeline_mode, str):
            pipeline_mode = ""

        # Extract remediation flag from input_summary (Issue #902 / #904).
        # Remediation events (e.g., reviewer re-run after BLOCKING findings)
        # must not trigger duplicate-agent ordering findings.
        remediation_flag = False
        if isinstance(input_summary, dict):
            raw_remediation = input_summary.get("remediation", False)
            remediation_flag = bool(raw_remediation)

        # Detect raw Bash pytest commands (Bug #620): PreToolUse Bash entries
        # where the command contains "pytest" but pipeline_action is not set.
        # Normalise these as test_run events so hard-gate ordering can find them.
        bash_command: str = input_summary.get("command", "") if isinstance(input_summary, dict) else ""
        is_pytest_bash = (
            tool == "Bash"
            and pipeline_action != "test_run"
            and "pytest" in bash_command
        )

        # Include Task (agent invocations) and Bash test_run events
        if tool in AGENT_TOOL_NAMES and pipeline_action == "agent_invocation":
            events.append(PipelineEvent(
                timestamp=entry.get("timestamp", ""),
                tool=tool,
                agent=entry.get("agent", "main"),
                subagent_type=input_summary.get("subagent_type", ""),
                pipeline_action=pipeline_action,
                prompt_word_count=input_summary.get("prompt_word_count", 0),
                result_word_count=output_summary.get("result_word_count", 0),
                duration_ms=entry.get("duration_ms", 0),
                success=output_summary.get("success", True),
                total_tokens=output_summary.get("total_tokens", 0),
                tool_uses=output_summary.get("tool_uses", 0),
                batch_issue_number=batch_issue_number,
                session_id=entry.get("session_id", ""),
                pipeline_mode=pipeline_mode,
                remediation=remediation_flag,
            ))
        elif tool == "Bash" and pipeline_action == "test_run":
            events.append(PipelineEvent(
                timestamp=entry.get("timestamp", ""),
                tool=tool,
                agent=entry.get("agent", "main"),
                subagent_type="",
                pipeline_action="test_run",
                duration_ms=entry.get("duration_ms", 0),
                success=output_summary.get("success", True),
                session_id=entry.get("session_id", ""),
            ))
        elif is_pytest_bash:
            # Raw PreToolUse Bash entries with pytest in the command — treated
            # as test_run events.  success defaults to True since raw Bash
            # PreToolUse entries don't carry an output_summary yet; the check
            # for "no tests ran" only cares that pytest was invoked.
            events.append(PipelineEvent(
                timestamp=entry.get("timestamp", ""),
                tool=tool,
                agent=entry.get("agent", "main"),
                subagent_type="",
                pipeline_action="test_run",
                duration_ms=entry.get("duration_ms", 0),
                success=output_summary.get("success", True),
                session_id=entry.get("session_id", ""),
            ))
        elif entry.get("hook") == "SubagentStop":
            events.append(PipelineEvent(
                timestamp=entry.get("timestamp", ""),
                tool="Agent",
                agent=entry.get("agent", "main"),
                subagent_type=entry.get("subagent_type", ""),
                pipeline_action="agent_completion",
                result_word_count=entry.get("result_word_count", 0),
                duration_ms=entry.get("duration_ms", 0),
                success=entry.get("success", True),
                total_tokens=entry.get("total_tokens", 0),
                tool_uses=entry.get("tool_uses", 0),
                agent_transcript_path=entry.get("agent_transcript_path", ""),
                session_id=entry.get("session_id", ""),
            ))

    return events


def parse_session_logs(
    log_path: Path,
    *,
    session_id: Optional[str] = None,
    additional_log_paths: Optional[List[Path]] = None,
) -> List[PipelineEvent]:
    """Parse JSONL session log into pipeline-relevant events.

    Args:
        log_path: Path to JSONL log file.
        session_id: Optional session ID filter.
        additional_log_paths: Optional list of additional JSONL log files to
            merge.  Events are deduplicated by (timestamp, tool, session_id)
            so the same event appearing in multiple files is only returned once.

    Returns:
        List of PipelineEvent sorted by timestamp.
    """
    events = _parse_single_log(log_path, session_id=session_id)

    # Parse additional log paths and merge
    if additional_log_paths:
        for extra_path in additional_log_paths:
            if extra_path and extra_path.exists():
                extra_events = _parse_single_log(
                    extra_path, session_id=session_id
                )
                events.extend(extra_events)

    # Deduplicate by (timestamp, tool, session_id)
    seen: set = set()
    unique_events: List[PipelineEvent] = []
    for evt in events:
        key = (evt.timestamp, evt.tool, evt.session_id)
        if key not in seen:
            seen.add(key)
            unique_events.append(evt)

    # Sort by timestamp
    unique_events.sort(key=lambda e: e.timestamp)
    return unique_events


def parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime.

    Handles timestamps with and without microseconds, e.g.:
    - ``2026-01-01T12:00:00Z``
    - ``2026-01-01T12:00:00.123456Z``
    - ``2026-01-01T12:00:00+00:00``
    - ``2026-01-01T12:00:00.123456+00:00``

    Uses ``datetime.fromisoformat()`` first (handles all Python 3.11+
    ISO formats natively), with a manual fallback for older runtimes.
    """
    try:
        # Normalise timezone suffixes so fromisoformat() accepts them on
        # Python 3.7-3.10 as well (3.11+ handles "+00:00" directly).
        normalised = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(normalised)
    except (ValueError, AttributeError):
        pass

    # Legacy fallback: try explicit strptime patterns (microseconds first)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            # strptime needs numeric timezone like +0000, not +00:00
            ts_norm = ts.replace("+00:00", "+0000").replace("Z", "+0000")
            return datetime.strptime(ts_norm, fmt)
        except ValueError:
            continue

    return None


def seconds_between(ts1: str, ts2: str) -> Optional[float]:
    """Get seconds between two timestamps."""
    dt1 = parse_timestamp(ts1)
    dt2 = parse_timestamp(ts2)
    if dt1 is None or dt2 is None:
        return None
    return abs((dt2 - dt1).total_seconds())


# Backward-compatible aliases for internal/external callers using the old private names
_parse_timestamp = parse_timestamp
_seconds_between = seconds_between


def _validate_step_ordering_for_group(
    agent_events: List[PipelineEvent],
    all_events: List[PipelineEvent],
) -> List[Finding]:
    """Validate step ordering for a single group of agent events.

    Internal helper used by validate_step_ordering to check ordering within
    a single issue (batch mode) or the entire session (non-batch mode).

    Args:
        agent_events: Agent events filtered to a single group (by issue or all).
        all_events: All events in the session (for parallel STEP 10 detection).

    Returns:
        List of findings for ordering violations within this group.
    """
    findings: List[Finding] = []

    if len(agent_events) < 2:
        return findings

    # Detect parallel STEP 10 mode upfront so we can skip intra-STEP-6 ordering
    # checks (Issue #615): reviewer/security-auditor/doc-master complete in
    # non-deterministic order when launched in parallel.
    step6_are_parallel = _is_parallel_step10_launch(all_events)
    # Set of STEP 6 pairs where ordering should not be flagged in parallel mode
    STEP6_PAIRS = frozenset({("reviewer", "security-auditor"), ("security-auditor", "reviewer")})

    # Include TDD-first pairs if test-master was used in this group
    all_pairs = list(SEQUENTIAL_REQUIRED)
    if any(e.subagent_type == "test-master" for e in agent_events):
        all_pairs.extend(TDD_FIRST_PAIRS)

    # Issue #788: Detect planner-exempt modes at the group level.
    # If any event in this group has a planner-exempt pipeline_mode,
    # remove the (planner, implementer) pair from enforcement.
    # Empty/unknown pipeline_mode defaults to full enforcement (fail-safe).
    group_modes = {e.pipeline_mode for e in agent_events if e.pipeline_mode}
    is_planner_exempt = bool(group_modes & PLANNER_EXEMPT_MODES)
    if is_planner_exempt:
        all_pairs = [
            pair for pair in all_pairs
            if pair != ("planner", "implementer")
        ]

    for first_type, second_type in all_pairs:
        # Skip STEP 6 inter-ordering when parallel launch detected (#615)
        if step6_are_parallel and (first_type, second_type) in STEP6_PAIRS:
            continue

        # Exclude remediation events when looking at "the agent's first run"
        # timestamps. Remediation events (e.g. reviewer re-run after BLOCKING
        # findings) are legitimate repeat invocations — they must not be
        # compared against their own original completion and flagged as a
        # duplicate-agent ordering violation. Issue #902 / #904.
        first_events = [
            e for e in agent_events
            if e.subagent_type == first_type and not e.remediation
        ]
        second_events = [
            e for e in agent_events
            if e.subagent_type == second_type and not e.remediation
        ]

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


def validate_step_ordering(events: List[PipelineEvent]) -> List[Finding]:
    """Validate that pipeline steps executed in correct order.

    When batch events are present (batch_issue_number > 0), ordering is checked
    independently within each issue group. This prevents false positives in
    mixed-mode batches where --fix issues (no planner/researcher) run alongside
    full-pipeline issues. (#680)

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for ordering violations.
    """
    # Filter to agent invocations with known step assignments
    agent_events = [
        e for e in events
        if e.tool in AGENT_TOOL_NAMES and e.subagent_type in STEP_ORDER
    ]

    # Need at least 2 agents to check ordering
    if len(agent_events) < 2:
        return []

    # Check ordering: for each sequential pair, verify first completed before second
    # NOTE: test-master absence is intentionally NOT checked here. In acceptance-first mode
    # (the default), test-master is never invoked — it only runs in --tdd-first mode.
    # The pipeline coordinator (implement.md STEP 7) is responsible for mode-specific agent
    # inclusion. Post-hoc log validation must not second-guess mode selection. (#518)

    # Group by (session_id, batch_issue_number) to isolate independent
    # pipeline runs and batch issues. The tuple key prevents cross-pipeline
    # contamination that previously arose when two simultaneous pipelines
    # wrote into the same log file with overlapping batch_issue_numbers or
    # both used batch_issue_number=0 (Issue #875 / Issue #904).
    #
    # Non-batch events with session_id='' and batch_issue_number=0 still
    # group together under the single key ('', 0) — behavior unchanged for
    # legacy single-session logs. The per-issue isolation added in #680 is
    # preserved because different batch_issue_number values still produce
    # distinct groups even within the same session_id.
    group_key_fn = lambda e: (e.session_id, e.batch_issue_number if e.batch_issue_number > 0 else 0)
    issue_groups: dict[tuple, List[PipelineEvent]] = {}
    for e in agent_events:
        key = group_key_fn(e)
        if key not in issue_groups:
            issue_groups[key] = []
        issue_groups[key].append(e)

    findings: List[Finding] = []
    for group_events in issue_groups.values():
        findings.extend(_validate_step_ordering_for_group(group_events, events))
    return findings


def _is_parallel_step10_launch(events: List[PipelineEvent]) -> bool:
    """Detect whether STEP 6 agents were launched in parallel (commit 2b87c40 mode).

    In parallel STEP 10 mode, reviewer, security-auditor, and doc-master are
    launched in a single message, so their start timestamps are nearly identical.
    If all present STEP 6 agents started within TIMESTAMP_WINDOW_SECONDS of each
    other, they were launched in parallel and ordering between them does not apply.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        True if STEP 6 agents appear to have been launched in parallel.
    """
    step6_events = [e for e in events if e.subagent_type in STEP6_AGENTS]
    if len(step6_events) < 2:
        # Only one STEP 6 agent — no ordering concern
        return False

    # Collect earliest launch timestamp per STEP 6 agent type
    agent_first_ts: dict[str, str] = {}
    for e in step6_events:
        if e.subagent_type not in agent_first_ts:
            agent_first_ts[e.subagent_type] = e.timestamp

    timestamps = list(agent_first_ts.values())
    if len(timestamps) < 2:
        return False

    # If every pair of STEP 6 launch timestamps is within the window, parallel mode
    for i in range(len(timestamps)):
        for j in range(i + 1, len(timestamps)):
            gap = seconds_between(timestamps[i], timestamps[j])
            if gap is None or gap > TIMESTAMP_WINDOW_SECONDS:
                return False

    return True


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

    # Find test_run events (pipeline_action == "test_run")
    # Also detect raw PreToolUse Bash entries where the command contains "pytest"
    # (Bug #620: pipeline_action may be absent for raw Bash log entries)
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
    agent_events = [e for e in events if e.tool in AGENT_TOOL_NAMES and e.subagent_type]

    # Detect whether this is a batch session — if so, skip cross-issue
    # comparisons that would produce false positives (#681)
    has_batch_events = any(e.batch_issue_number > 0 for e in agent_events)

    for i in range(1, len(agent_events)):
        prev = agent_events[i - 1]
        curr = agent_events[i]

        # Skip cross-issue comparisons in batch mode (#681): reviewer result
        # from issue N → researcher prompt from issue N+1 is not context dropping
        if has_batch_events and prev.batch_issue_number != curr.batch_issue_number:
            continue

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

    agent_events = [e for e in events if e.tool in AGENT_TOOL_NAMES and e.subagent_type]

    # Build lookup: agent_type → earliest timestamp
    agent_timestamps: dict[str, str] = {}
    for e in agent_events:
        if e.subagent_type not in agent_timestamps:
            agent_timestamps[e.subagent_type] = e.timestamp

    # Check sequential pairs that were incorrectly parallelized
    # Include TDD-first pairs if test-master was used
    all_pairs_parallel = list(SEQUENTIAL_REQUIRED)
    if any(e.subagent_type == "test-master" for e in agent_events):
        all_pairs_parallel.extend(TDD_FIRST_PAIRS)
    for first_type, second_type in all_pairs_parallel:
        if first_type not in agent_timestamps or second_type not in agent_timestamps:
            continue

        gap = seconds_between(agent_timestamps[first_type], agent_timestamps[second_type])
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

        gap = seconds_between(agent_timestamps[a_type], agent_timestamps[b_type])
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


def detect_ghost_invocations(
    events: List[PipelineEvent],
    *,
    max_duration_ms: int = 10000,
    max_result_words: int = 50,
) -> List[Finding]:
    """Detect ghost invocations: agent calls that completed too fast with minimal output.

    A ghost invocation is an agent call with duration < max_duration_ms AND
    result_word_count < max_result_words, suggesting the agent did not actually
    perform meaningful work.

    Args:
        events: List of PipelineEvent sorted by timestamp.
        max_duration_ms: Maximum duration in milliseconds to consider suspicious.
        max_result_words: Maximum result word count to consider suspicious.

    Returns:
        List of findings for ghost invocations.
    """
    findings: List[Finding] = []

    # Filter to completion events only. Invocation events (pipeline_action=
    # 'agent_invocation') always have result_word_count=0 and duration_ms=1
    # because the agent hasn't run yet, producing false-positive ghost
    # findings. Issue #781.
    agent_events = [
        e for e in events
        if e.tool in AGENT_TOOL_NAMES
        and e.subagent_type
        and e.pipeline_action == "agent_completion"
    ]

    for event in agent_events:
        # Both conditions must be true: fast AND low output
        if event.duration_ms > 0 and event.duration_ms < max_duration_ms and event.result_word_count < max_result_words:
            findings.append(Finding(
                finding_type="ghost_invocation",
                severity="WARNING",
                pattern_id="ghost_invocation",
                description=(
                    f"Agent {event.subagent_type} completed in {event.duration_ms}ms "
                    f"with only {event.result_word_count} result words "
                    f"(thresholds: <{max_duration_ms}ms, <{max_result_words} words) [GHOST]"
                ),
                evidence=[
                    f"subagent_type: {event.subagent_type}",
                    f"duration_ms: {event.duration_ms}",
                    f"result_word_count: {event.result_word_count}",
                    f"timestamp: {event.timestamp}",
                ],
            ))

    return findings


def detect_progressive_compression(events: List[PipelineEvent], *, agents_dir: Optional[Path] = None) -> List[Finding]:
    """Detect progressive prompt compression across batch issues.

    Groups agent events by batch_issue_number and compares prompt_word_count
    across issues for each agent type. Flags when prompts shrink beyond
    MAX_PROMPT_SHRINKAGE_RATIO from the baseline (issue with lowest number).

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for progressive compression violations.
    """
    findings: List[Finding] = []

    # Filter to batch agent invocations with valid batch_issue_number
    batch_events = [
        e for e in events
        if e.tool in AGENT_TOOL_NAMES
        and e.subagent_type
        and e.batch_issue_number > 0
        and e.prompt_word_count > 0
    ]

    if not batch_events:
        return findings

    # Group by agent type -> {issue_number: prompt_word_count}
    # Use the first (earliest) event per agent per issue as representative
    agent_issue_prompts: dict[str, dict[int, int]] = {}
    for e in batch_events:
        agent_type = e.subagent_type
        if agent_type not in agent_issue_prompts:
            agent_issue_prompts[agent_type] = {}
        # Only record the first prompt per agent per issue
        if e.batch_issue_number not in agent_issue_prompts[agent_type]:
            agent_issue_prompts[agent_type][e.batch_issue_number] = e.prompt_word_count

    # For each agent, compare later issues against the baseline (lowest issue number)
    for agent_type, issue_prompts in agent_issue_prompts.items():
        if len(issue_prompts) < 2:
            continue

        sorted_issues = sorted(issue_prompts.keys())
        baseline_issue = sorted_issues[0]
        baseline_words = issue_prompts[baseline_issue]

        if baseline_words == 0:
            continue

        for issue_num in sorted_issues[1:]:
            current_words = issue_prompts[issue_num]
            ratio = current_words / baseline_words

            if ratio < (1 - MAX_PROMPT_SHRINKAGE_RATIO):
                shrinkage_pct = (1 - ratio) * 100

                severity = (
                    "CRITICAL"
                    if agent_type in COMPRESSION_CRITICAL_AGENTS
                    else "WARNING"
                )

                recommended_action = (
                    f"Reload prompt from agents/{agent_type}.md before "
                    f"processing issue #{issue_num}. Re-read the agent prompt "
                    f"file from disk instead of reusing compressed context."
                )
                evidence_list = [
                    f"baseline (issue #{baseline_issue}): {baseline_words} words",
                    f"current (issue #{issue_num}): {current_words} words",
                    f"ratio: {ratio:.3f} (threshold: {1 - MAX_PROMPT_SHRINKAGE_RATIO})",
                    f"agent_type: {agent_type}",
                ]
                if agents_dir is not None:
                    evidence_list.append(f"prompt_source: {agents_dir / f'{agent_type}.md'}")
                findings.append(Finding(
                    finding_type="progressive_compression",
                    severity=severity,
                    pattern_id="progressive_prompt_compression",
                    description=(
                        f"Agent {agent_type} prompt shrank {shrinkage_pct:.0f}% "
                        f"from issue #{baseline_issue} ({baseline_words} words) to "
                        f"issue #{issue_num} ({current_words} words) "
                        f"— progressive compression detected "
                        f"(threshold: {MAX_PROMPT_SHRINKAGE_RATIO:.0%} shrinkage)"
                    ),
                    evidence=evidence_list,
                    recommended_action=recommended_action,
                ))

    return findings


def detect_minimum_prompt_violation(events: List[PipelineEvent]) -> List[Finding]:
    """Check security-critical agents have minimum prompt word counts.

    Ensures that agents in COMPRESSION_CRITICAL_AGENTS receive prompts of at
    least MIN_CRITICAL_AGENT_PROMPT_WORDS words. Returns CRITICAL findings
    for violations.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for minimum prompt violations.
    """
    findings: List[Finding] = []

    # Filter to agent invocations for security-critical agents
    critical_events = [
        e for e in events
        if e.tool in AGENT_TOOL_NAMES
        and e.subagent_type in COMPRESSION_CRITICAL_AGENTS
        and e.prompt_word_count > 0
    ]

    for event in critical_events:
        if event.prompt_word_count < MIN_CRITICAL_AGENT_PROMPT_WORDS:
            findings.append(Finding(
                finding_type="minimum_prompt_violation",
                severity="CRITICAL",
                pattern_id="minimum_prompt_violation",
                description=(
                    f"Security-critical agent {event.subagent_type} received only "
                    f"{event.prompt_word_count} prompt words "
                    f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS}) "
                    f"— prompt too short for meaningful analysis"
                ),
                evidence=[
                    f"agent_type: {event.subagent_type}",
                    f"prompt_word_count: {event.prompt_word_count}",
                    f"minimum_required: {MIN_CRITICAL_AGENT_PROMPT_WORDS}",
                    f"timestamp: {event.timestamp}",
                ],
            ))

    return findings


def _correlate_invocation_completion(
    events: List[PipelineEvent],
    *,
    max_window_seconds: float = 600,
) -> List[tuple]:
    """Pair agent invocation events with their completion events.

    Matches PostToolUse agent_invocation events with SubagentStop
    agent_completion events by subagent_type and temporal proximity.
    Each invocation is paired with the closest subsequent completion
    of the same subagent_type within max_window_seconds.

    Args:
        events: List of PipelineEvent sorted by timestamp.
        max_window_seconds: Maximum seconds between invocation and completion
            to consider them a pair.

    Returns:
        List of (invocation_event, completion_event_or_None) tuples.
    """
    invocations = [
        e for e in events
        if e.pipeline_action == "agent_invocation" and e.subagent_type
    ]
    completions = [
        e for e in events
        if e.pipeline_action == "agent_completion" and e.subagent_type
    ]

    used_completions: set[int] = set()  # indices into completions list
    pairs: List[tuple] = []

    for inv in invocations:
        best_completion = None
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

            # Completion must be AFTER invocation (or very close)
            inv_dt = parse_timestamp(inv.timestamp)
            comp_dt = parse_timestamp(comp.timestamp)
            if inv_dt is None or comp_dt is None:
                continue
            if comp_dt < inv_dt:
                continue

            if gap <= max_window_seconds and gap < best_gap:
                best_gap = gap
                best_completion = comp
                best_idx = idx

        if best_completion is not None:
            used_completions.add(best_idx)
            pairs.append((inv, best_completion))
        else:
            pairs.append((inv, None))

    return pairs


def detect_doc_verdict_missing(events: List[PipelineEvent]) -> List[Finding]:
    """Detect doc-master invocations that produced no output or failed.

    Correlates doc-master agent_invocation events with their matching
    agent_completion (SubagentStop) events to get actual result word counts.
    PostToolUse invocation events always have result_word_count=0, so this
    function uses the completion event's word count instead.

    Flags when:
    - No completion event exists for a doc-master invocation
    - Completion result_word_count < MIN_DOC_VERDICT_WORDS (too short for verdict)
    - Completion success is False

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for doc-master verdict issues.
    """
    findings: List[Finding] = []

    # Get all correlated pairs
    pairs = _correlate_invocation_completion(events)

    # Filter to doc-master pairs
    doc_pairs = [(inv, comp) for inv, comp in pairs if inv.subagent_type == "doc-master"]

    for inv, comp in doc_pairs:
        if comp is None:
            # No completion event found via correlation — but correlation can fail
            # due to session grouping, timestamp parsing, or window boundary issues.
            # Fallback: check if ANY doc-master completion exists in the full event list
            # with sufficient word count and success=True (Issue #650).
            any_healthy_completion = any(
                e for e in events
                if e.pipeline_action == "agent_completion"
                and e.subagent_type == "doc-master"
                and e.success
                and e.result_word_count >= MIN_DOC_VERDICT_WORDS
            )
            if any_healthy_completion:
                continue  # Skip this false positive

            # No completion event found — doc-master may have timed out or crashed
            findings.append(Finding(
                finding_type="doc_verdict_missing",
                severity="CRITICAL",
                pattern_id="doc_verdict_missing",
                description=(
                    f"[DOC-VERDICT-MISSING] doc-master invocation at {inv.timestamp} "
                    f"has no matching completion event — agent may have timed out or crashed. "
                    f"Documentation drift may go undetected."
                ),
                evidence=[
                    f"subagent_type: {inv.subagent_type}",
                    f"invocation_timestamp: {inv.timestamp}",
                    f"completion: not found",
                    f"success: unknown",
                ],
            ))
        elif not comp.success:
            # Completion exists but failed
            findings.append(Finding(
                finding_type="doc_verdict_missing",
                severity="CRITICAL",
                pattern_id="doc_verdict_missing",
                description=(
                    f"[DOC-VERDICT-MISSING] doc-master failed (success=False) "
                    f"at {comp.timestamp} — no DOC-DRIFT-VERDICT generated. "
                    f"Documentation drift may go undetected."
                ),
                evidence=[
                    f"subagent_type: {comp.subagent_type}",
                    f"result_word_count: {comp.result_word_count}",
                    f"invocation_timestamp: {inv.timestamp}",
                    f"completion_timestamp: {comp.timestamp}",
                    f"success: {comp.success}",
                ],
            ))
        elif comp.result_word_count < MIN_DOC_VERDICT_WORDS:
            # Completion exists but output too short for a meaningful verdict
            findings.append(Finding(
                finding_type="doc_verdict_missing",
                severity="CRITICAL",
                pattern_id="doc_verdict_missing",
                description=(
                    f"[DOC-VERDICT-MISSING] doc-master produced only "
                    f"{comp.result_word_count} result words at {comp.timestamp} "
                    f"(minimum: {MIN_DOC_VERDICT_WORDS}) — output too short for "
                    f"meaningful DOC-DRIFT-VERDICT. Documentation drift may go undetected."
                ),
                evidence=[
                    f"subagent_type: {comp.subagent_type}",
                    f"result_word_count: {comp.result_word_count}",
                    f"minimum_required: {MIN_DOC_VERDICT_WORDS}",
                    f"invocation_timestamp: {inv.timestamp}",
                    f"completion_timestamp: {comp.timestamp}",
                    f"success: {comp.success}",
                ],
            ))
        # else: completion has sufficient output and success=True — no finding

    return findings

def detect_doc_verdict_shallow(events: List[PipelineEvent]) -> List[Finding]:
    """Detect doc-master invocations that produced shallow output (Issue #672).

    A doc-master completion that passes the MIN_DOC_VERDICT_WORDS threshold
    (so it is NOT caught by detect_doc_verdict_missing) but falls below
    MIN_DOC_SWEEP_WORDS indicates the agent likely only updated CHANGELOG
    without performing a real semantic drift sweep.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of WARNING findings for shallow doc-master output.
    """
    findings: List[Finding] = []

    pairs = _correlate_invocation_completion(events)
    doc_pairs = [(inv, comp) for inv, comp in pairs if inv.subagent_type == "doc-master"]

    for inv, comp in doc_pairs:
        if comp is not None:
            # Only flag if completion succeeded and passes the "missing" threshold
            # but falls below the "sweep" threshold
            if (
                comp.success
                and comp.result_word_count >= MIN_DOC_VERDICT_WORDS
                and comp.result_word_count < MIN_DOC_SWEEP_WORDS
            ):
                findings.append(Finding(
                    finding_type="doc_verdict_shallow",
                    severity="WARNING",
                    pattern_id="doc_verdict_shallow",
                    description=(
                        f"[DOC-VERDICT-SHALLOW] doc-master produced only "
                        f"{comp.result_word_count} result words at {comp.timestamp} "
                        f"(minimum for real sweep: {MIN_DOC_SWEEP_WORDS}) — "
                        f"output too short for a semantic drift check. "
                        f"Only CHANGELOG may have been updated."
                    ),
                    evidence=[
                        f"subagent_type: {comp.subagent_type}",
                        f"result_word_count: {comp.result_word_count}",
                        f"minimum_sweep_words: {MIN_DOC_SWEEP_WORDS}",
                        f"invocation_timestamp: {inv.timestamp}",
                        f"completion_timestamp: {comp.timestamp}",
                        f"success: {comp.success}",
                    ],
                ))
        else:
            # Fallback: correlation failed — check if ANY doc-master completion
            # exists that is healthy but shallow (Issue #650 pattern applied to #672)
            any_shallow_completion = any(
                e for e in events
                if e.pipeline_action == "agent_completion"
                and e.subagent_type == "doc-master"
                and e.success
                and e.result_word_count >= MIN_DOC_VERDICT_WORDS
                and e.result_word_count < MIN_DOC_SWEEP_WORDS
            )
            if any_shallow_completion:
                # Find the actual completion for evidence
                shallow_comp = next(
                    e for e in events
                    if e.pipeline_action == "agent_completion"
                    and e.subagent_type == "doc-master"
                    and e.success
                    and e.result_word_count >= MIN_DOC_VERDICT_WORDS
                    and e.result_word_count < MIN_DOC_SWEEP_WORDS
                )
                findings.append(Finding(
                    finding_type="doc_verdict_shallow",
                    severity="WARNING",
                    pattern_id="doc_verdict_shallow",
                    description=(
                        f"[DOC-VERDICT-SHALLOW] doc-master produced only "
                        f"{shallow_comp.result_word_count} result words "
                        f"(minimum for real sweep: {MIN_DOC_SWEEP_WORDS}) — "
                        f"output too short for a semantic drift check. "
                        f"Only CHANGELOG may have been updated."
                    ),
                    evidence=[
                        f"subagent_type: doc-master",
                        f"result_word_count: {shallow_comp.result_word_count}",
                        f"minimum_sweep_words: {MIN_DOC_SWEEP_WORDS}",
                        f"invocation_timestamp: {inv.timestamp}",
                        f"completion_timestamp: {shallow_comp.timestamp}",
                        f"success: {shallow_comp.success}",
                    ],
                ))

    return findings


def detect_batch_cia_skip(events: List[PipelineEvent]) -> List[Finding]:
    """Detect batch issues where continuous-improvement-analyst was not invoked.

    Identifies batch sessions by looking for events with batch_issue_number > 0,
    groups events by issue_number, and checks whether the continuous-improvement-analyst
    agent was invoked for each issue. The last issue missing CIA is flagged as WARNING
    (known regression pattern, Issue #505); non-last issues are flagged as INFO.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for batch CIA skip violations.
    """
    findings: List[Finding] = []

    # Filter to batch agent invocations with valid batch_issue_number
    batch_events = [
        e for e in events
        if e.tool in AGENT_TOOL_NAMES
        and e.subagent_type
        and e.batch_issue_number > 0
    ]

    if not batch_events:
        return findings

    # Group by issue number -> set of agent types that ran
    issue_agents: dict[int, set[str]] = {}
    for e in batch_events:
        issue_num = e.batch_issue_number
        if issue_num not in issue_agents:
            issue_agents[issue_num] = set()
        issue_agents[issue_num].add(e.subagent_type)

    if not issue_agents:
        return findings

    sorted_issues = sorted(issue_agents.keys())
    last_issue = sorted_issues[-1]

    for issue_num in sorted_issues:
        agents_ran = issue_agents[issue_num]
        if "continuous-improvement-analyst" not in agents_ran:
            is_last = issue_num == last_issue
            severity = "WARNING" if is_last else "INFO"
            pattern_id = (
                "batch_last_issue_cia_skip" if is_last
                else "batch_issue_cia_skip"
            )

            findings.append(Finding(
                finding_type="batch_cia_skip",
                severity=severity,
                pattern_id=pattern_id,
                description=(
                    f"Batch issue #{issue_num} missing continuous-improvement-analyst "
                    f"invocation{' (LAST ISSUE — known regression, Issue #505)' if is_last else ''}"
                ),
                evidence=[
                    f"issue_number: {issue_num}",
                    f"agents_ran: {sorted(agents_ran)}",
                    f"is_last_issue: {is_last}",
                    f"total_batch_issues: {len(sorted_issues)}",
                ],
            ))

    return findings


def detect_cia_skip(events: List[PipelineEvent]) -> List[Finding]:
    """Detect missing continuous-improvement-analyst in non-batch pipeline runs.

    Complements detect_batch_cia_skip (which handles batch_issue_number > 0).
    This function detects CIA skip in single /implement runs where the full
    pipeline ran but CIA was never invoked.

    Args:
        events: List of PipelineEvent sorted by timestamp.

    Returns:
        List of findings for single-pipeline CIA skip violations.
    """
    findings: List[Finding] = []

    # Collect all agent types from both invocation and completion events
    agent_events = [
        e for e in events
        if e.pipeline_action in ("agent_invocation", "agent_completion")
        and e.subagent_type
        and e.tool in AGENT_TOOL_NAMES
    ]

    if not agent_events:
        return findings

    # Skip if this looks like a batch run (handled by detect_batch_cia_skip)
    if any(e.batch_issue_number > 0 for e in agent_events):
        return findings

    # Build set of all agent types that ran
    agents_ran: set[str] = {e.subagent_type for e in agent_events}

    # Core agents that indicate a full pipeline run
    core_agents = {"implementer", "planner", "reviewer", "security-auditor"}
    core_present = agents_ran & core_agents

    # Only flag if this looks like a full pipeline run (at least 3 core agents)
    if len(core_present) < 3:
        return findings

    # Check if CIA ran
    if "continuous-improvement-analyst" not in agents_ran:
        findings.append(Finding(
            finding_type="cia_skip",
            severity="WARNING",
            pattern_id="single_pipeline_cia_skip",
            description=(
                f"[INCOMPLETE] Full pipeline run missing continuous-improvement-analyst. "
                f"Agents that ran: {sorted(agents_ran)}. "
                f"CIA was not invoked — quality check skipped."
            ),
            evidence=[
                f"agents_ran: {sorted(agents_ran)}",
                f"core_agents_present: {sorted(core_present)}",
                f"cia_invoked: False",
            ],
        ))

    return findings


def detect_missing_security_review(
    log_path: Path,
    events: List[PipelineEvent],
    *,
    session_id: Optional[str] = None,
) -> List[Finding]:
    """Detect security-sensitive file changes without security-auditor review.

    Scans the JSONL log for Write/Edit tool entries targeting security-sensitive
    paths (hooks, auto-approval engine, tool validator, security libs).  If any
    such path is modified and no security-auditor event exists in the session,
    a WARNING finding is emitted.

    Test files (paths starting with ``tests/``) are excluded — modifying a test
    that touches hook-related paths is not a security concern.

    Args:
        log_path: Path to the JSONL log file.
        events: List of PipelineEvent for the session/group.
        session_id: Optional session ID filter for JSONL entries.

    Returns:
        List of findings (empty if no issues detected).
    """
    findings: List[Finding] = []

    # Scan JSONL for Write/Edit tool entries
    security_paths: List[str] = []

    if not log_path.exists():
        return findings

    text = log_path.read_text().strip()
    if not text:
        return findings

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Filter by session if provided
        if session_id and entry.get("session_id") != session_id:
            continue

        tool = entry.get("tool", "")
        if tool not in ("Write", "Edit"):
            continue

        input_summary = entry.get("input_summary", {})
        if not isinstance(input_summary, dict):
            continue

        file_path = input_summary.get("file_path", "")
        if not file_path:
            continue

        # Skip test files — they are not security-sensitive
        if file_path.startswith("tests/"):
            continue

        # Check against security-sensitive patterns
        for pattern in SECURITY_SENSITIVE_PATTERNS:
            if pattern in file_path:
                security_paths.append(file_path)
                break

    if not security_paths:
        return findings

    # Check if security-auditor is present in the events
    agents_ran = {e.subagent_type for e in events if e.subagent_type}
    if "security-auditor" not in agents_ran:
        findings.append(Finding(
            finding_type="missing_security_review",
            severity="WARNING",
            pattern_id="missing_security_review",
            description=(
                f"Security-sensitive files modified without security-auditor review: "
                f"{security_paths}"
            ),
            evidence=[
                f"security_sensitive_paths: {security_paths}",
                f"agents_ran: {sorted(agents_ran)}",
                f"security_auditor_present: False",
            ],
        ))

    return findings


def _run_checks_on_events(events: List[PipelineEvent]) -> List[Finding]:
    """Run all check functions on a list of events from a single session.

    Args:
        events: List of PipelineEvent from one session (or ungrouped events).

    Returns:
        Combined list of all findings from all checks.
    """
    findings: List[Finding] = []
    findings.extend(validate_step_ordering(events))
    findings.extend(detect_hard_gate_ordering(events))
    findings.extend(detect_context_dropping(events))
    findings.extend(detect_parallelization_violations(events))
    findings.extend(detect_ghost_invocations(events))
    # Lazy import to avoid circular dependency (agent_output_health imports from this module)
    from agent_output_health import detect_zero_word_completions as _detect_zero_word
    findings.extend(_detect_zero_word(events))
    findings.extend(detect_progressive_compression(events))
    findings.extend(detect_minimum_prompt_violation(events))
    findings.extend(detect_doc_verdict_missing(events))
    findings.extend(detect_doc_verdict_shallow(events))
    findings.extend(detect_batch_cia_skip(events))
    findings.extend(detect_cia_skip(events))
    return findings


def validate_pipeline_intent(
    log_path: Path,
    *,
    session_id: Optional[str] = None,
) -> List[Finding]:
    """Orchestrate all intent validation checks on a session log.

    When session_id is provided, only events from that session are checked
    (existing single-session behavior is unchanged).

    When session_id is not provided, events are grouped by their session_id
    field and each session's events are checked independently. This prevents
    false CRITICAL "step_ordering" findings that arise from comparing events
    across different sessions in the same daily JSONL log file (Issue #587).

    Events with an empty session_id (legacy logs without session tracking) are
    grouped together as a fallback and checked as a single virtual session.

    Args:
        log_path: Path to JSONL log file.
        session_id: Optional session ID filter. When provided, only events
            from this session are validated (single-session mode).

    Returns:
        Combined list of all findings, aggregated across all session groups.
    """
    # Detect worktree context and resolve main repo log path (Issue #593)
    additional_log_paths: Optional[List[Path]] = None
    try:
        from path_utils import get_main_repo_activity_log_dir
        main_log_dir = get_main_repo_activity_log_dir()
        if main_log_dir is not None:
            main_log_file = main_log_dir / log_path.name
            if main_log_file.exists() and main_log_file != log_path.resolve():
                additional_log_paths = [main_log_file]
    except (ImportError, Exception):
        pass

    events = parse_session_logs(
        log_path, session_id=session_id,
        additional_log_paths=additional_log_paths,
    )
    if not events:
        return []

    # When an explicit session_id filter was provided, all returned events
    # already belong to that session — run checks on the flat list directly.
    if session_id:
        findings = _run_checks_on_events(events)
        findings.extend(detect_missing_security_review(
            log_path, events, session_id=session_id,
        ))
        return findings

    # Group events by session_id to avoid cross-session false positives.
    # Events with empty session_id share a fallback group ("").
    session_groups: dict[str, List[PipelineEvent]] = {}
    for event in events:
        key = event.session_id  # "" for legacy events without session tracking
        if key not in session_groups:
            session_groups[key] = []
        session_groups[key].append(event)

    findings: List[Finding] = []
    for _sid, session_events in session_groups.items():
        findings.extend(_run_checks_on_events(session_events))
        findings.extend(detect_missing_security_review(
            log_path, session_events, session_id=_sid or None,
        ))
    return findings
