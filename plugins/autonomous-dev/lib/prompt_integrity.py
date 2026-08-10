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


# Issue #1485: Auto-detect remediation re-dispatches from prompt content when
# the coordinator neglected to pass invocation_context="remediation" explicitly.
# A remediation re-dispatch is legitimately much shorter than the original
# full dispatch (it names one specific finding), so the shrinkage gate should
# not fire. These signals mirror the phrasing the coordinator uses when
# constructing a remediation prompt in response to a reviewer / security-auditor
# / spec-validator finding.
_REMEDIATION_SIGNAL_TOKENS = (
    "remediation",
    "re-dispatch",
    "reviewer flagged",
    "reviewer finding",
    "security-auditor flagged",
    "security-auditor finding",
    "spec-validator failed",
    "spec-validator finding",
    "fix the following finding",
    "fix the following:",
    "address the following finding",
    "address this finding",
    "continuation dispatch",
)


def _is_remediation_dispatch(prompt: str) -> bool:
    """Return True if the prompt text carries a remediation-re-dispatch signal.

    Issue #1485: The shrinkage-baseline gate false-positives on legitimate
    narrow remediation re-dispatches (e.g., "fix the finding at file:line")
    because those prompts are much shorter than the original full-feature
    dispatch that established the baseline. This helper lets the shrinkage
    check identify such follow-up dispatches from the prompt content itself,
    even when the coordinator did not thread ``invocation_context="remediation"``
    through explicitly. Case-insensitive substring match on any of the tokens
    in ``_REMEDIATION_SIGNAL_TOKENS`` is sufficient.
    """
    if not prompt:
        return False
    lowered = prompt.lower()
    return any(tok in lowered for tok in _REMEDIATION_SIGNAL_TOKENS)


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
    shrinkage_pct: float = 0.0
    should_reload: bool = False


# Required content slots for critical agents (Issue #844).
# Each agent maps to a list of (slot_name, marker_substring) tuples.
# The marker_substring is case-insensitive and checked via `in` on the prompt.
# (Restored in #1471 — dropped by d29c3163; tests/unit/lib/test_prompt_integrity.py
# and the #844 slot-validation contract import it.)
REQUIRED_PROMPT_SLOTS: Dict[str, List[Tuple[str, str]]] = {
    "security-auditor": [
        ("implementer output", "implementer"),
        ("changed files", "changed file"),
        ("test results", "test"),
    ],
    "reviewer": [
        ("implementer output", "implementer"),
        ("changed files", "changed file"),
        ("test results", "test"),
    ],
}


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
            shrinkage_pct=100.0 if (baseline_word_count and baseline_word_count > 0) else 0.0,
            should_reload=True,
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
                # Issue #1471: reason must name the agent (test contract)
                reason=(
                    f"{agent_type}: critical agent prompt too short: "
                    f"{word_count} words < {MIN_CRITICAL_AGENT_PROMPT_WORDS} minimum"
                ),
                shrinkage_pct=(
                    round((1.0 - word_count / baseline_word_count) * 100, 1)
                    if baseline_word_count and baseline_word_count > 0
                    else 0.0
                ),
                should_reload=True,
            )

    # Check 2: Shrinkage from baseline (if baseline provided)
    if baseline_word_count and baseline_word_count > 0:
        shrinkage = 1.0 - (word_count / baseline_word_count)
        shrinkage_pct = shrinkage * 100

        # Adjust threshold for reinvocation contexts (Issue #789/#791)
        # Issue #1358: Use 3.0x multiplier for "fix" mode, 2.0x for others
        # Issue #1485: Auto-detect remediation dispatch from prompt content
        # when the coordinator did not thread invocation_context through
        # explicitly. Applies only when a baseline exists (i.e., this is a
        # follow-up dispatch, not the first). This prevents four separate
        # blocks per pipeline observed in session b0926f9b (issue #1467)
        # where narrow same-issue remediation re-dispatches were compared
        # against the original 1270-word full-feature baseline.
        effective_context = invocation_context
        if (effective_context is None or effective_context not in REINVOCATION_CONTEXTS) \
                and _is_remediation_dispatch(prompt):
            effective_context = "remediation"
            logger.debug(
                "Issue #1485: auto-detected remediation dispatch for %s "
                "(prompt matches remediation signal token)",
                agent_type,
            )
        effective_max_shrinkage = max_shrinkage
        if effective_context and effective_context in REINVOCATION_CONTEXTS:
            if effective_context == "fix":
                effective_max_shrinkage = max_shrinkage * 3.0  # Issue #1358
            elif effective_context == "light":
                effective_max_shrinkage = max_shrinkage * 2.5  # Issue #1359
            else:
                effective_max_shrinkage = max_shrinkage * 2.0
            logger.debug(
                "Relaxed shrinkage threshold for %s context: %.0f%% -> %.0f%%",
                effective_context,
                max_shrinkage * 100,
                effective_max_shrinkage * 100,
            )

        if shrinkage > effective_max_shrinkage:
            threshold_note = (
                f" [relaxed from {max_shrinkage:.0%} for {effective_context}]"
                if effective_context and effective_context in REINVOCATION_CONTEXTS
                else ""
            )
            return PromptIntegrityResult(
                agent_type=agent_type,
                word_count=word_count,
                baseline_word_count=baseline_word_count,
                passed=False,
                # Issue #1471: "shrank" + one-decimal pct are test contract
                reason=(
                    f"Prompt shrank {shrinkage_pct:.1f}% — exceeds "
                    f"{effective_max_shrinkage:.0%} threshold{threshold_note}"
                ),
                shrinkage_pct=round(shrinkage_pct, 1),
                should_reload=True,
            )

    return PromptIntegrityResult(
        agent_type=agent_type,
        word_count=word_count,
        baseline_word_count=baseline_word_count,
        passed=True,
        shrinkage_pct=(
            round((1.0 - word_count / baseline_word_count) * 100, 1)
            if baseline_word_count and baseline_word_count > 0
            else 0.0
        ),
        should_reload=False,
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


def get_agent_prompt_template(
    agent_type: str,
    *,
    agents_dir: Optional[Path] = None,
) -> str:
    """Read an agent's prompt template from its source file on disk.

    Restored from commit b7face59 (Issue #1471) — regressed to a stub
    returning None, breaking the coordinator's reload-from-disk path.

    Args:
        agent_type: Agent name (e.g., 'reviewer').
        agents_dir: Optional override for agents directory path.

    Returns:
        Full text content of the agent's .md file.

    Raises:
        FileNotFoundError: If agent file does not exist.
    """
    if agents_dir is None:
        root = _find_project_root()
        agents_dir = root / "plugins" / "autonomous-dev" / "agents"
        if not agents_dir.exists():
            agents_dir = root / ".claude" / "agents"

    agent_file = agents_dir / f"{agent_type}.md"
    if not agent_file.exists():
        raise FileNotFoundError(
            f"Agent prompt template not found: {agent_file}\n"
            f"Expected .md file in {agents_dir}/"
        )

    return agent_file.read_text(encoding="utf-8")


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


def _find_project_root(start: Optional[Path] = None) -> Path:
    """Walk up from start directory looking for project root markers.

    Args:
        start: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to project root.

    Raises:
        FileNotFoundError: If no project root can be found.
    """
    current = start or Path.cwd()
    while current != current.parent:
        if (current / "plugins" / "autonomous-dev" / "agents").is_dir():
            return current
        if (current / ".git").exists() or (current / ".claude").exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        f"Could not find project root from {start or Path.cwd()}.\n"
        f"Expected a directory containing plugins/autonomous-dev/agents/ or .git/"
    )


def _get_observations_path(state_dir: Optional[Path] = None) -> Path:
    """Resolve the path to the batch observations JSON file.

    Args:
        state_dir: Optional override directory. If None, uses project root.

    Returns:
        Absolute path to prompt_batch_observations.json.
    """
    if state_dir is not None:
        return state_dir / "prompt_batch_observations.json"
    root = _find_project_root()
    return root / ".claude" / "logs" / "prompt_batch_observations.json"


def record_batch_observation(
    agent_type: str,
    issue_number: int,
    word_count: int,
    *,
    state_dir: Optional[Path] = None,
) -> None:
    """Record a prompt word count observation for cumulative drift tracking.

    Appends to prompt_batch_observations.json file. Each agent_type gets a list
    of observations recording the word count at each issue in the batch.

    Args:
        agent_type: Agent name (e.g., 'reviewer').
        issue_number: GitHub issue number being processed.
        word_count: Word count of the prompt sent to this agent.
        state_dir: Optional override for state directory.
    """
    obs_path = _get_observations_path(state_dir)
    obs_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if obs_path.exists():
        try:
            data = json.loads(obs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning(
                "Could not read batch observations file, starting fresh: %s", obs_path
            )
            data = {}

    if agent_type not in data:
        data[agent_type] = []

    data[agent_type].append({"issue": issue_number, "word_count": word_count})

    obs_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.debug(
        "Recorded batch observation: %s issue #%d = %d words",
        agent_type,
        issue_number,
        word_count,
    )


def get_cumulative_shrinkage(
    agent_type: str,
    *,
    state_dir: Optional[Path] = None,
) -> Optional[float]:
    """Get cumulative shrinkage percentage for an agent across the batch.

    Computes drift from the first observation to the latest observation for
    the specified agent_type.

    Args:
        agent_type: Agent name to look up.
        state_dir: Optional override for state directory.

    Returns:
        Shrinkage percentage (e.g., 20.0 for 20%), or None if fewer than
        2 observations exist for this agent. Returns 0.0 if latest >= first.
    """
    obs_path = _get_observations_path(state_dir)

    if not obs_path.exists():
        return None

    try:
        data = json.loads(obs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read batch observations file: %s", obs_path)
        return None

    observations = data.get(agent_type)
    if not observations or len(observations) < 2:
        return None

    # Issue #934: skip drift check for single-issue remediation loops.
    distinct_issues = {obs.get("issue", obs.get("issue_number")) for obs in observations}
    distinct_issues.discard(None)
    if len(distinct_issues) < 2:
        return None

    first_wc = observations[0]["word_count"]
    latest_wc = observations[-1]["word_count"]

    if first_wc <= 0:
        return None

    shrinkage = (first_wc - latest_wc) / first_wc * 100
    return max(0.0, round(shrinkage, 1))


def clear_batch_observations(*, state_dir: Optional[Path] = None) -> None:
    """Clear all batch observations. Call at batch start.

    Args:
        state_dir: Optional override for state directory.
    """
    obs_path = _get_observations_path(state_dir)
    obs_path.unlink(missing_ok=True)
    logger.debug("Cleared batch observations: %s", obs_path)


def compute_template_baselines(*, agents_dir: Optional[Path] = None) -> dict:
    """Compute word counts for each critical agent's prompt template.

    Restored verbatim from commit b7face59 (Issue #1471).

    Args:
        agents_dir: Optional override for agents directory path.

    Returns:
        Mapping of {agent_type: word_count} for agents with found templates.
    """
    if agents_dir is None:
        root = _find_project_root()
        agents_dir = root / "plugins" / "autonomous-dev" / "agents"

    baselines: dict = {}
    for agent_type in COMPRESSION_CRITICAL_AGENTS:
        agent_file = agents_dir / f"{agent_type}.md"
        if not agent_file.exists():
            logger.warning(
                "Template baseline: agent file not found, skipping: %s", agent_file
            )
            continue
        try:
            template = agent_file.read_text(encoding="utf-8")
            baselines[agent_type] = len(template.split())
        except OSError as exc:
            logger.warning("Template baseline: could not read %s: %s", agent_file, exc)

    return baselines


def seed_baselines_from_templates(
    *,
    agents_dir: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> dict:
    """No-op: template-based baseline seeding is deprecated (Issue #810).

    Restored verbatim from commit b7face59 (Issue #1471). Previously seeded
    baselines at 0.70x template word count, causing a systematic 25-50% false
    positive block rate. The hook's else-branch correctly seeds from the
    first observed prompt when no baseline exists.

    Args:
        agents_dir: Ignored (kept for backwards-compatible signature).
        state_dir: Ignored (kept for backwards-compatible signature).

    Returns:
        Empty dict — no baselines are written.
    """
    logger.warning(
        "seed_baselines_from_templates() is deprecated (Issue #810). "
        "Baselines are now established automatically from the first observed prompt."
    )
    return {}


def set_redispatch_flag(agent_type: str, *, state_dir: Optional[Path] = None) -> None:
    """Set a one-shot redispatch flag for an agent.

    Restored verbatim from commit b7face59 (Issue #1471, originally #1227).
    Called when an agent invocation is denied (e.g., by agent_ordering_gate).
    The flag indicates the coordinator will re-dispatch the agent with the
    canonical template, so prompt shrinkage check should be skipped.

    Args:
        agent_type: Agent name (e.g., 'reviewer', 'security-auditor').
        state_dir: Optional override for state directory.
    """
    del state_dir  # reserved; resolved via sentinel
    try:
        from pipeline_state import load_pipeline, save_pipeline, get_legacy_sentinel_path
        sentinel = get_legacy_sentinel_path()
        if not sentinel.exists():
            logger.debug(
                "No active pipeline sentinel - skipping redispatch flag set for '%s'",
                agent_type,
            )
            return
        try:
            sentinel_data = json.loads(sentinel.read_text(encoding="utf-8"))
            run_id = sentinel_data.get("run_id")
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Could not read sentinel for redispatch flag set: %s", e)
            return
        if not run_id:
            return
        state = load_pipeline(run_id)
        if state is None:
            logger.debug("No pipeline state for run_id %s - skipping redispatch flag set", run_id)
            return
        if not hasattr(state, "redispatch_agents") or state.redispatch_agents is None:
            state.redispatch_agents = {}
        state.redispatch_agents[agent_type] = True
        save_pipeline(state)
        logger.debug("Set redispatch flag for agent '%s' on run %s", agent_type, run_id)
    except Exception as e:
        logger.debug("Could not set redispatch flag for '%s': %s", agent_type, e)


def consume_redispatch_flag(agent_type: str, *, state_dir: Optional[Path] = None) -> bool:
    """Consume and clear a one-shot redispatch flag for an agent.

    Restored verbatim from commit b7face59 (Issue #1471, originally #1227).
    Returns True if the flag was set (and clears it), False otherwise.
    This is a one-shot mechanism: the flag is deleted after being read.

    Args:
        agent_type: Agent name (e.g., 'reviewer', 'security-auditor').
        state_dir: Optional override for state directory.

    Returns:
        True if redispatch flag was set for this agent, False otherwise.
    """
    del state_dir  # reserved; resolved via sentinel
    try:
        from pipeline_state import load_pipeline, save_pipeline, get_legacy_sentinel_path
        sentinel = get_legacy_sentinel_path()
        if not sentinel.exists():
            return False
        try:
            sentinel_data = json.loads(sentinel.read_text(encoding="utf-8"))
            run_id = sentinel_data.get("run_id")
        except (json.JSONDecodeError, OSError):
            return False
        if not run_id:
            return False
        state = load_pipeline(run_id)
        if state is None:
            return False
        if not hasattr(state, "redispatch_agents") or state.redispatch_agents is None:
            return False
        if agent_type in state.redispatch_agents and state.redispatch_agents[agent_type]:
            del state.redispatch_agents[agent_type]
            save_pipeline(state)
            logger.debug("Consumed redispatch flag for agent '%s' on run %s", agent_type, run_id)
            return True
        return False
    except Exception as e:
        logger.debug("Could not consume redispatch flag for '%s': %s", agent_type, e)
        return False


def is_canonical_template_match(
    agent_type: str,
    content: str,
    *,
    tolerance: float = 0.10,
    agents_dir: Optional[Path] = None,
) -> bool:
    """Check if content matches canonical template word count within tolerance.

    Restored verbatim from commit b7face59 (Issue #1471, originally #1227).

    Args:
        agent_type: Agent name (e.g., 'reviewer', 'security-auditor').
        content: The prompt content to check.
        tolerance: Maximum relative difference (0.10 = 10% tolerance).
        agents_dir: Optional override for agents directory path.

    Returns:
        True if word count is within tolerance of canonical template.
    """
    try:
        template = get_agent_prompt_template(agent_type, agents_dir=agents_dir)
        canonical_wc = len(template.split())
        actual_wc = len(content.split())
        if canonical_wc == 0:
            return False

        rel_diff = abs(actual_wc - canonical_wc) / canonical_wc
        is_match = rel_diff <= tolerance

        if is_match:
            logger.debug(
                "Canonical template match for %s: actual=%d, canonical=%d, diff=%.1f%%",
                agent_type, actual_wc, canonical_wc, rel_diff * 100
            )

        return is_match
    except Exception as e:
        logger.debug("Could not check canonical match for '%s': %s", agent_type, e)
        return False


@dataclass
class ValidateAndReloadResult:
    """Result of validate_and_reload operation.

    Attributes:
        prompt: The best available prompt (original if passed, or reloaded).
        validation: The final PromptIntegrityResult after all attempts.
        reload_count: Number of reload attempts made.
        reload_succeeded: True if a reload produced a passing prompt.

    Restored in #1471 (dropped by d29c3163). NOTE: the current module also has
    PromptReloadResult (the #1358-era rewrite's equivalent); reconciling the two
    result types is tracked in the validate_prompt_word_count-divergence
    follow-up issue — this restoration only unblocks module collection for
    tests/unit/lib/test_prompt_integrity.py (63 tests dark since d29c3163).
    """

    prompt: str
    validation: PromptIntegrityResult
    reload_count: int
    reload_succeeded: bool