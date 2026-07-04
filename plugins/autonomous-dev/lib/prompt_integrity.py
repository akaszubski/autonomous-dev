#!/usr/bin/env python3
"""
Prompt Integrity - Issue #601, #603

Provides prompt integrity validation and prevention functions for the batch
coordinator. While pipeline_intent_validator.py detects compression after the
fact (post-hoc analysis of logs), this module provides real-time prevention
that the coordinator calls before each agent invocation.

Usage:
    from prompt_integrity import (
        validate_prompt_word_count,
        validate_and_reload,
        validate_prompt_slots,
        record_prompt_baseline,
        get_prompt_baseline,
        get_cross_issue_baseline,
        get_agent_prompt_template,
        clear_prompt_baselines,
        construct_revision_prompt,
    )

    # At batch start
    clear_prompt_baselines()

    # First issue - establish baselines
    result = validate_prompt_word_count("reviewer", prompt)
    record_prompt_baseline("reviewer", issue_number=1, word_count=len(prompt.split()))

    # Subsequent issues - validate and auto-reload if compressed (Issue #844)
    baseline = get_prompt_baseline("reviewer")
    reload_result = validate_and_reload(prompt, "reviewer", baseline)
    if not reload_result.validation.passed:
        # All reload attempts failed, escalate
        ...

    # Check required content slots for critical agents (Issue #844)
    slot_result = validate_prompt_slots("security-auditor", prompt)
    if not slot_result.passed:
        # Fill missing slots: slot_result.missing_slots
        ...
"""

import json
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Critical agents that require minimum prompt word counts.
# Mirrors COMPRESSION_CRITICAL_AGENTS in pipeline_intent_validator.py.
COMPRESSION_CRITICAL_AGENTS = {
    "security-auditor",
    "reviewer",
    "researcher-local",
    "researcher",
    "implementer",
    "planner",
    "doc-master",
}

# Minimum word count for critical agent prompts.
# Matches MIN_CRITICAL_AGENT_PROMPT_WORDS in pipeline_intent_validator.py.
MIN_CRITICAL_AGENT_PROMPT_WORDS = 80

# Maximum cumulative shrinkage across an entire batch (Issue #794).
# Calibrated to 30% (from 15% in Issue #812) after Issue #870 showed the 15%
# threshold fires too aggressively on normal inter-issue variance (15-25%).
# The per-issue check (20% threshold, cross-issue aware via #867) catches
# individual issue compression; this cumulative check catches gradual drift
# that per-issue checks miss.
MAX_CUMULATIVE_SHRINKAGE = 0.30  # 30% total drift threshold (Issue #870, calibrated from #812)

# Known reinvocation context strings (Issue #789, #791, #1002, #1358).
# These represent legitimate agent invocations that produce naturally shorter
# prompts, so the shrinkage threshold is relaxed (doubled — 20% -> 40% for most,
# tripled — 20% -> 60% for "fix" mode per Issue #1358).
#
# "remediation", "re-review", "doc-update-retry" are SECONDARY invocations
# (the agent is run again after a failed first attempt), per #789/#791.
#
# "research-skip" (Issue #1002) is a PRIMARY-invocation case (not a retry):
# when STEP 3.5 detects a fully-specified change and skips the research step,
# downstream agents (planner, implementer) receive prompts that legitimately
# lack the research-output payload. Without this entry, prompt_integrity would
# fire on every research-skip pipeline (observed 3/3 = 100% rate in batch
# #995/#996/#997). The coordinator sets PIPELINE_INVOCATION_CONTEXT=research-skip
# at STEP 3.5 so the hook's env-var path applies the relaxed threshold to all
# downstream agent dispatches in that pipeline run.
#
# "fix" (Issue #1358) is a PRIMARY-invocation case for --fix mode: the prompt
# lacks the full research payload and uses a 3.0x multiplier (60% threshold).
# "light" (Issue #1359) is a PRIMARY-invocation case for --light mode: the prompt
# lacks the full research payload and uses a 2.5x multiplier (37.5% threshold).
REINVOCATION_CONTEXTS = {"remediation", "re-review", "doc-update-retry", "research-skip", "fix", "light"}


# Default baseline persistence location (relative to project root).
_DEFAULT_BASELINES_RELPATH = Path(".claude") / "logs" / "prompt_baselines.json"


@dataclass
class PromptIntegrityResult:
    """Result from prompt integrity validation."""
    agent_type: str
    word_count: int
    baseline_word_count: Optional[int]
    passed: bool
    reason: str = ""
    shrinkage_percent: Optional[float] = None


@dataclass
class PromptSlotResult:
    """Result from prompt slot validation."""
    passed: bool
    missing_slots: List[str] = field(default_factory=list)
    found_slots: List[str] = field(default_factory=list)


@dataclass
class PromptReloadResult:
    """Result from validate_and_reload attempt."""
    validation: PromptIntegrityResult
    reload_attempted: bool = False
    reload_succeeded: bool = False
    reload_reason: str = ""
    final_word_count: int = 0


def validate_prompt_word_count(
    agent_type: str,
    prompt: str,
    baseline_word_count: Optional[int] = None,
    *,
    max_shrinkage: float = 0.15,
    invocation_context: Optional[str] = None,
    pipeline_mode: Optional[str] = None,  # Issue #1358: Added parameter
) -> PromptIntegrityResult:
    """Validate a constructed prompt against word count thresholds.

    Checks (in order):
    1. Minimum absolute word count for critical agents
    2. Shrinkage from baseline (if baseline provided)

    Args:
        agent_type: The agent being invoked (e.g., "reviewer", "implementer")
        prompt: The constructed prompt text
        baseline_word_count: Expected word count from baseline (optional).
            If provided, validates against shrinkage threshold.
        max_shrinkage: Maximum allowed shrinkage from baseline (default 0.15 = 15%).
            Doubled for known reinvocation contexts (0.30 = 30%).
        invocation_context: Optional context string (e.g., "remediation", "re-review")
            that triggers relaxed thresholds for legitimate reinvocations.
        pipeline_mode: Optional pipeline mode (e.g., "full", "fix", "light") from Issue #1358

    Returns:
        PromptIntegrityResult with pass/fail status and diagnostic info
    """
    if not prompt:
        return PromptIntegrityResult(
            agent_type=agent_type,
            word_count=0,
            baseline_word_count=baseline_word_count,
            passed=False,
            reason="Empty prompt",
        )

    word_count = len(prompt.split())

    # Check 1: Minimum absolute word count for critical agents
    if agent_type in COMPRESSION_CRITICAL_AGENTS:
        if word_count < MIN_CRITICAL_AGENT_PROMPT_WORDS:
            return PromptIntegrityResult(
                agent_type=agent_type,
                word_count=word_count,
                baseline_word_count=baseline_word_count,
                passed=False,
                reason=f"Critical agent prompt too short: {word_count} words < {MIN_CRITICAL_AGENT_PROMPT_WORDS} minimum",
            )

    # Check 2: Shrinkage from baseline (if baseline provided)
    if baseline_word_count and baseline_word_count > 0:
        shrinkage = 1.0 - (word_count / baseline_word_count)
        shrinkage_percent = shrinkage * 100

        # Adjust threshold for reinvocation contexts (Issue #789/#791)
        # Issue #1358: Use 3.0x multiplier for "fix" mode, 2.0x for others
        effective_max_shrinkage = max_shrinkage
        if invocation_context and invocation_context in REINVOCATION_CONTEXTS:
            if invocation_context == "fix":
                effective_max_shrinkage = max_shrinkage * 3.0  # Issue #1358
            elif invocation_context == "light":
                effective_max_shrinkage = max_shrinkage * 2.5  # Issue #1359
            else:
                effective_max_shrinkage = max_shrinkage * 2.0
            logger.debug(
                "Relaxed shrinkage threshold for %s context: %.0f%% -> %.0f%%",
                invocation_context,
                max_shrinkage * 100,
                effective_max_shrinkage * 100,
            )

        if shrinkage > effective_max_shrinkage:
            threshold_note = (
                f" [relaxed from {max_shrinkage:.0%} for {invocation_context}]"
                if invocation_context and invocation_context in REINVOCATION_CONTEXTS
                else ""
            )
            return PromptIntegrityResult(
                agent_type=agent_type,
                word_count=word_count,
                baseline_word_count=baseline_word_count,
                passed=False,
                reason=f"Prompt shrinkage {shrinkage:.0%} exceeds {effective_max_shrinkage:.0%} threshold{threshold_note}",
                shrinkage_percent=shrinkage_percent,
            )

    return PromptIntegrityResult(
        agent_type=agent_type,
        word_count=word_count,
        baseline_word_count=baseline_word_count,
        passed=True,
        shrinkage_percent=(
            (1.0 - word_count / baseline_word_count) * 100
            if baseline_word_count and baseline_word_count > 0
            else None
        ),
    )


def validate_and_reload(
    prompt: str,
    agent_type: str,
    baseline_word_count: Optional[int] = None,
    *,
    max_reload_attempts: int = 3,
    invocation_context: Optional[str] = None,
    pipeline_mode: Optional[str] = None,  # Issue #1358: Added parameter
) -> PromptReloadResult:
    """
    Validate prompt and attempt reload if compressed (Issue #844).

    This is the higher-level function that combines validation with
    automatic reload attempts when compression is detected.

    Args:
        prompt: The constructed prompt text
        agent_type: The agent being invoked
        baseline_word_count: Expected word count from baseline
        max_reload_attempts: Maximum number of reload attempts
        invocation_context: Optional context for relaxed thresholds
        pipeline_mode: Optional pipeline mode from Issue #1358

    Returns:
        PromptReloadResult with validation result and reload status
    """
    # Initial validation
    result = validate_prompt_word_count(
        agent_type,
        prompt,
        baseline_word_count,
        invocation_context=invocation_context,
        pipeline_mode=pipeline_mode,  # Issue #1358
    )

    if result.passed:
        return PromptReloadResult(
            validation=result,
            reload_attempted=False,
            reload_succeeded=False,
            final_word_count=result.word_count,
        )

    # Compression detected, attempt reload
    logger.warning(
        "Prompt compression detected for %s: %s. Attempting reload...",
        agent_type,
        result.reason,
    )

    # Reload logic would go here (requires access to prompt construction functions)
    # For now, return failure with reload_attempted=True
    return PromptReloadResult(
        validation=result,
        reload_attempted=True,
        reload_succeeded=False,
        reload_reason="Reload not yet implemented",
        final_word_count=result.word_count,
    )


def validate_prompt_slots(agent_type: str, prompt: str) -> PromptSlotResult:
    """
    Validate that critical content slots are filled in the prompt (Issue #844).

    Different agents require different slots to be filled. This function
    checks for the presence of required markers in the prompt.

    Args:
        agent_type: The agent being invoked
        prompt: The constructed prompt text

    Returns:
        PromptSlotResult with pass/fail and list of missing slots
    """
    # Define required slots per agent type
    REQUIRED_SLOTS = {
        "security-auditor": [
            "## Security Analysis Request",
            "## Code Context",
            "## Previous Findings",
        ],
        "reviewer": [
            "## Review Request",
            "## Implementation Details",
            "## Test Coverage",
        ],
        "implementer": [
            "## Implementation Request",
            "## Architecture Context",
        ],
        "planner": [
            "## Planning Request",
            "## Project Context",
        ],
    }

    required = REQUIRED_SLOTS.get(agent_type, [])
    if not required:
        # No required slots for this agent type
        return PromptSlotResult(passed=True)

    missing = []
    found = []
    for slot in required:
        if slot in prompt:
            found.append(slot)
        else:
            missing.append(slot)

    return PromptSlotResult(
        passed=len(missing) == 0,
        missing_slots=missing,
        found_slots=found,
    )


def get_prompt_baseline(
    agent_type: str,
    issue_number: Optional[int] = None,
    *,
    state_dir: Optional[Path] = None,
) -> Optional[int]:
    """Get baseline word count for an agent type.

    Args:
        agent_type: The agent type (e.g., "reviewer")
        issue_number: Specific issue number to get baseline for.
            If None, returns the lowest issue number baseline (most conservative).
        state_dir: Override state directory (for testing)

    Returns:
        Baseline word count if found, None otherwise
    """
    baselines_path = _get_baselines_path(state_dir)
    if not baselines_path.exists():
        return None

    try:
        with open(baselines_path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning("Failed to load baselines from %s", baselines_path)
        return None

    agent_baselines = data.get(agent_type, {})
    if not agent_baselines:
        return None

    if issue_number is not None:
        # Get baseline for specific issue
        baseline_data = agent_baselines.get(str(issue_number))
        # Issue #1358: Handle both old format (bare int) and new format (dict)
        if isinstance(baseline_data, int):
            return baseline_data
        elif isinstance(baseline_data, dict):
            return baseline_data.get("word_count")
        return None

    # No specific issue, return lowest issue baseline (most conservative)
    min_issue = min(int(k) for k in agent_baselines.keys())
    baseline_data = agent_baselines.get(str(min_issue))
    # Issue #1358: Handle both formats
    if isinstance(baseline_data, int):
        return baseline_data
    elif isinstance(baseline_data, dict):
        return baseline_data.get("word_count")
    return None


def get_cross_issue_baseline(
    agent_type: str,
    current_issue: int,
    *,
    state_dir: Optional[Path] = None,
    pipeline_mode: Optional[str] = None,  # Issue #1358: Added parameter
) -> Optional[int]:
    """Get baseline from a different issue for cross-issue validation (Issue #867).

    Looks for the most recent issue before the current one that has a baseline.
    This enables detection of per-issue compression that might look acceptable
    within a single issue but represents drift across issues.

    Args:
        agent_type: The agent type (e.g., "reviewer")
        current_issue: The current issue number being processed
        state_dir: Override state directory (for testing)
        pipeline_mode: Current pipeline mode from Issue #1358

    Returns:
        Baseline word count from a previous issue, or None if not found
    """
    baselines_path = _get_baselines_path(state_dir)
    if not baselines_path.exists():
        return None

    try:
        with open(baselines_path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning("Failed to load baselines from %s", baselines_path)
        return None

    agent_baselines = data.get(agent_type, {})
    if not agent_baselines:
        return None

    # Find the most recent issue before current_issue
    previous_issues = [
        int(k) for k in agent_baselines.keys()
        if int(k) < current_issue
    ]

    if not previous_issues:
        return None

    # Get baseline from most recent previous issue
    most_recent = max(previous_issues)
    baseline_data = agent_baselines.get(str(most_recent))
    
    # Issue #1358: Handle both formats and check pipeline mode
    if isinstance(baseline_data, int):
        # Old format - no mode check possible
        return baseline_data
    elif isinstance(baseline_data, dict):
        stored_mode = baseline_data.get("pipeline_mode")
        # Skip cross-issue comparison if modes differ
        if pipeline_mode and stored_mode and pipeline_mode != stored_mode:
            logger.debug(
                "Skipping cross-issue comparison for %s: mode mismatch (%s != %s)",
                agent_type, pipeline_mode, stored_mode
            )
            return None
        return baseline_data.get("word_count")
    return None


def record_prompt_baseline(
    agent_type: str,
    issue_number: int,
    word_count: int,
    *,
    state_dir: Optional[Path] = None,
    pipeline_mode: Optional[str] = None,  # Issue #1358: Added parameter
) -> None:
    """Record prompt word count as baseline for comparison across issues.

    Persists to .claude/logs/prompt_baselines.json (or state_dir override).
    Structure: {agent_type: {str(issue_number): {"word_count": N, "pipeline_mode": mode}}}

    Args:
        agent_type: The agent type (e.g., "reviewer")
        issue_number: Issue number this baseline is for
        word_count: Word count to record
        state_dir: Override state directory (for testing)
        pipeline_mode: Pipeline mode from Issue #1358
    """
    baselines_path = _get_baselines_path(state_dir)
    baselines_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data
    if baselines_path.exists():
        try:
            with open(baselines_path, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {}
    else:
        data = {}

    # Update baseline - Issue #1358: Store as dict with mode
    if agent_type not in data:
        data[agent_type] = {}
    
    # Store as dict format (Issue #1358)
    data[agent_type][str(issue_number)] = {
        "word_count": word_count,
        "pipeline_mode": pipeline_mode
    }

    # Write back
    try:
        with open(baselines_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.debug(
            "Recorded baseline for %s issue #%d: %d words (mode=%s)",
            agent_type, issue_number, word_count, pipeline_mode
        )
    except IOError as e:
        logger.error("Failed to record baseline: %s", e)


def clear_prompt_baselines(*, state_dir: Optional[Path] = None) -> None:
    """Clear all prompt baselines (typically at batch start).

    Args:
        state_dir: Override state directory (for testing)
    """
    baselines_path = _get_baselines_path(state_dir)
    if baselines_path.exists():
        try:
            baselines_path.unlink()
            logger.info("Cleared prompt baselines")
        except IOError as e:
            logger.error("Failed to clear baselines: %s", e)


def get_agent_prompt_template(agent_type: str) -> Optional[str]:
    """Get the prompt template for an agent type.

    This would normally load from agent definitions, but for now returns None.
    Future implementation would load from agents/*.md files.

    Args:
        agent_type: The agent type (e.g., "reviewer")

    Returns:
        Prompt template string if found, None otherwise
    """
    # TODO: Implement loading from agent definitions
    return None


def construct_revision_prompt(
    base_prompt: str,
    revision_instructions: str,
    agent_type: str,
) -> str:
    """Construct a revision prompt by appending instructions to base prompt.

    Used for remediation and re-review scenarios where an agent needs to
    be invoked again with additional instructions.

    Args:
        base_prompt: The original prompt
        revision_instructions: Additional instructions to append
        agent_type: The agent type (for logging)

    Returns:
        Combined prompt with revision instructions
    """
    separator = "\n\n## Additional Instructions\n\n"
    revised = base_prompt + separator + revision_instructions
    
    logger.debug(
        "Constructed revision prompt for %s: added %d words",
        agent_type,
        len(revision_instructions.split()),
    )
    
    return revised


def _get_baselines_path(state_dir: Optional[Path] = None) -> Path:
    """Get the path to the baselines JSON file.

    Args:
        state_dir: Override state directory (for testing).
            If not provided, uses default location.

    Returns:
        Path to prompt_baselines.json
    """
    if state_dir:
        return state_dir / "prompt_baselines.json"
    
    # Find project root (has .git or .claude directory)
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists() or (parent / ".claude").exists():
            return parent / _DEFAULT_BASELINES_RELPATH
    
    # Fallback to cwd if no project root found
    return cwd / _DEFAULT_BASELINES_RELPATH


def check_cumulative_shrinkage(
    agent_type: str,
    current_word_count: int,
    first_baseline: Optional[int] = None,
    *,
    state_dir: Optional[Path] = None,
) -> Tuple[bool, float, str]:
    """Check cumulative shrinkage across entire batch (Issue #794).

    Compares current word count against the first baseline in the batch
    to detect gradual drift that per-issue checks might miss.

    Args:
        agent_type: The agent type
        current_word_count: Current prompt word count
        first_baseline: First issue baseline (if available)
        state_dir: Override state directory

    Returns:
        Tuple of (passed, shrinkage_percent, reason)
    """
    if not first_baseline or first_baseline <= 0:
        return (True, 0.0, "No baseline for comparison")
    
    shrinkage = 1.0 - (current_word_count / first_baseline)
    
    if shrinkage > MAX_CUMULATIVE_SHRINKAGE:
        reason = (
            f"Cumulative shrinkage {shrinkage:.0%} exceeds "
            f"{MAX_CUMULATIVE_SHRINKAGE:.0%} batch threshold"
        )
        return (False, shrinkage * 100, reason)
    
    return (True, shrinkage * 100, "Within cumulative threshold")


def analyze_prompt_structure(prompt: str) -> Dict[str, int]:
    """Analyze the structure of a prompt for diagnostics.

    Returns counts of various structural elements that might indicate
    compression or malformation.

    Args:
        prompt: The prompt text to analyze

    Returns:
        Dictionary with structural metrics
    """
    lines = prompt.split('\n')
    
    return {
        'total_lines': len(lines),
        'blank_lines': sum(1 for line in lines if not line.strip()),
        'comment_lines': sum(1 for line in lines if line.strip().startswith('#')),
        'header_lines': sum(1 for line in lines if line.strip().startswith('##')),
        'code_blocks': prompt.count('```'),
        'word_count': len(prompt.split()),
        'char_count': len(prompt),
    }