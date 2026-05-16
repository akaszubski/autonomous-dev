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

# Known reinvocation context strings (Issue #789, #791).
# These represent legitimate secondary agent invocations that produce
# naturally shorter prompts, so the shrinkage threshold is relaxed.
REINVOCATION_CONTEXTS = {"remediation", "re-review", "doc-update-retry"}


# Default baseline persistence location (relative to project root).
_DEFAULT_BASELINES_RELPATH = Path(".claude") / "logs" / "prompt_baselines.json"


@dataclass
class PromptIntegrityResult:
    """Result of a prompt integrity validation check.

    Attributes:
        agent_type: Agent name that was validated.
        word_count: Actual word count of the prompt.
        baseline_word_count: Word count from the first issue (None if first issue).
        shrinkage_pct: Shrinkage percentage vs baseline (0.0 if no baseline).
        passed: Whether the validation passed.
        reason: Human-readable explanation of the result.
        should_reload: True if coordinator should re-read agent source from disk.
    """

    agent_type: str
    word_count: int
    baseline_word_count: Optional[int]
    shrinkage_pct: float
    passed: bool
    reason: str
    should_reload: bool


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


def get_agent_prompt_template(
    agent_type: str,
    *,
    agents_dir: Optional[Path] = None,
) -> str:
    """Read an agent's prompt template from its source file on disk.

    Args:
        agent_type: Agent name (e.g., 'reviewer', 'security-auditor').
        agents_dir: Optional override for agents directory path.

    Returns:
        Full text content of the agent's .md file.

    Raises:
        FileNotFoundError: If agent file does not exist.
    """
    if agents_dir is None:
        root = _find_project_root()
        agents_dir = root / "plugins" / "autonomous-dev" / "agents"

    agent_file = agents_dir / f"{agent_type}.md"
    if not agent_file.exists():
        raise FileNotFoundError(
            f"Agent prompt template not found: {agent_file}\n"
            f"Expected .md file in {agents_dir}/"
        )

    return agent_file.read_text(encoding="utf-8")


def validate_prompt_word_count(
    agent_type: str,
    prompt: str,
    baseline_word_count: Optional[int] = None,
    *,
    max_shrinkage: float = 0.15,
    invocation_context: Optional[str] = None,
) -> PromptIntegrityResult:
    """Validate a constructed prompt against word count thresholds.

    Checks (in order):
    1. Prompt must not be empty.
    2. For critical agents, word count must be >= MIN_CRITICAL_AGENT_PROMPT_WORDS.
    3. If baseline provided, shrinkage must be <= max_shrinkage (default 15%).

    Args:
        agent_type: Agent name for context.
        prompt: The constructed prompt text to validate.
        baseline_word_count: Word count from first issue (None if first issue).
        max_shrinkage: Maximum allowed shrinkage ratio (0.15 = 15%).

    Returns:
        PromptIntegrityResult with validation outcome.
    """
    word_count = len(prompt.split())

    # Check 1: Empty prompt
    if word_count == 0:
        return PromptIntegrityResult(
            agent_type=agent_type,
            word_count=0,
            baseline_word_count=baseline_word_count,
            shrinkage_pct=100.0 if baseline_word_count else 0.0,
            passed=False,
            reason=f"Prompt for {agent_type} is empty (0 words).",
            should_reload=True,
        )

    # Check 2: Critical agent minimum
    if (
        agent_type in COMPRESSION_CRITICAL_AGENTS
        and word_count < MIN_CRITICAL_AGENT_PROMPT_WORDS
    ):
        return PromptIntegrityResult(
            agent_type=agent_type,
            word_count=word_count,
            baseline_word_count=baseline_word_count,
            shrinkage_pct=(
                round((1.0 - word_count / baseline_word_count) * 100, 1)
                if baseline_word_count
                else 0.0
            ),
            passed=False,
            reason=(
                f"Critical agent {agent_type} has only {word_count} words "
                f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS})."
            ),
            should_reload=True,
        )

    # Check 3: Baseline shrinkage
    if baseline_word_count is not None and baseline_word_count > 0:
        shrinkage_pct = round((1.0 - word_count / baseline_word_count) * 100, 1)

        # Relax threshold for known reinvocation contexts (Issue #789, #791)
        effective_max_shrinkage = max_shrinkage
        if invocation_context and invocation_context in REINVOCATION_CONTEXTS:
            effective_max_shrinkage = max_shrinkage * 2.0
            logger.debug(
                "Relaxed shrinkage threshold for %s context: %.0f%% -> %.0f%%",
                invocation_context,
                max_shrinkage * 100,
                effective_max_shrinkage * 100,
            )

        if shrinkage_pct >= effective_max_shrinkage * 100:
            ctx_note = (
                f" [relaxed from {max_shrinkage:.0%} for {invocation_context}]"
                if invocation_context and invocation_context in REINVOCATION_CONTEXTS
                else ""
            )
            return PromptIntegrityResult(
                agent_type=agent_type,
                word_count=word_count,
                baseline_word_count=baseline_word_count,
                shrinkage_pct=shrinkage_pct,
                passed=False,
                reason=(
                    f"Prompt for {agent_type} shrank {shrinkage_pct:.1f}% "
                    f"from baseline ({baseline_word_count} -> {word_count} words, "
                    f"threshold: {effective_max_shrinkage:.0%}{ctx_note})."
                ),
                should_reload=True,
            )
    else:
        shrinkage_pct = 0.0

    # All checks passed
    return PromptIntegrityResult(
        agent_type=agent_type,
        word_count=word_count,
        baseline_word_count=baseline_word_count,
        shrinkage_pct=shrinkage_pct if baseline_word_count else 0.0,
        passed=True,
        reason=f"Prompt for {agent_type} OK ({word_count} words).",
        should_reload=False,
    )


# Required content slots for critical agents (Issue #844).
# Each agent maps to a list of (slot_name, marker_substring) tuples.
# The marker_substring is case-insensitive and checked via `in` on the prompt.
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
    """Result of a prompt slot validation check.

    Attributes:
        agent_type: Agent name that was validated.
        present_slots: Slot names that were found in the prompt.
        missing_slots: Slot names that were NOT found in the prompt.
        passed: True if all required slots are present.
    """

    agent_type: str
    present_slots: List[str] = field(default_factory=list)
    missing_slots: List[str] = field(default_factory=list)
    passed: bool = True


def validate_prompt_slots(
    agent_type: str,
    prompt: str,
) -> PromptSlotResult:
    """Check that a prompt contains required content sections for critical agents.

    For agents listed in REQUIRED_PROMPT_SLOTS, verifies that the prompt
    contains marker substrings indicating required content sections are present.
    For agents not in REQUIRED_PROMPT_SLOTS, always passes.

    Args:
        agent_type: Agent name (e.g., 'security-auditor').
        prompt: The constructed prompt text to validate.

    Returns:
        PromptSlotResult with present/missing slots and pass/fail.
    """
    required = REQUIRED_PROMPT_SLOTS.get(agent_type)
    if not required:
        return PromptSlotResult(agent_type=agent_type, passed=True)

    prompt_lower = prompt.lower()
    present: List[str] = []
    missing: List[str] = []

    for slot_name, marker in required:
        if marker.lower() in prompt_lower:
            present.append(slot_name)
        else:
            missing.append(slot_name)

    return PromptSlotResult(
        agent_type=agent_type,
        present_slots=present,
        missing_slots=missing,
        passed=len(missing) == 0,
    )


@dataclass
class ValidateAndReloadResult:
    """Result of validate_and_reload operation.

    Attributes:
        prompt: The best available prompt (original if passed, or reloaded).
        validation: The final PromptIntegrityResult after all attempts.
        reload_count: Number of reload attempts made.
        reload_succeeded: True if a reload produced a passing prompt.
    """

    prompt: str
    validation: PromptIntegrityResult
    reload_count: int
    reload_succeeded: bool


def validate_and_reload(
    prompt: str,
    agent_type: str,
    baseline_word_count: Optional[int] = None,
    *,
    max_shrinkage: float = 0.15,
    max_reload_attempts: int = 2,
    agents_dir: Optional[Path] = None,
    invocation_context: Optional[str] = None,
) -> ValidateAndReloadResult:
    """Validate a prompt and reload from disk template if validation fails.

    This function addresses Issue #844: after a prompt integrity block + reload,
    the reloaded prompt was NOT validated before re-invocation. This function
    validates, and if the prompt fails, reads the agent template from disk,
    re-validates, and returns the best available prompt.

    The key insight is that after a block, the coordinator's in-memory state may
    still produce a compressed prompt. Reading the source template from disk
    bypasses stale context memory.

    Args:
        prompt: The constructed prompt text to validate.
        agent_type: Agent name (e.g., 'implementer', 'security-auditor').
        baseline_word_count: Word count from first issue (None if first issue).
        max_shrinkage: Maximum allowed shrinkage ratio (0.15 = 15%).
        max_reload_attempts: Maximum number of reload attempts (default: 2).
        agents_dir: Optional override for agents directory path.
        invocation_context: Optional context for reinvocation threshold relaxation.

    Returns:
        ValidateAndReloadResult with the best prompt and validation outcome.
    """
    # First: validate the prompt as-is
    result = validate_prompt_word_count(
        agent_type, prompt, baseline_word_count,
        max_shrinkage=max_shrinkage,
        invocation_context=invocation_context,
    )

    if result.passed:
        return ValidateAndReloadResult(
            prompt=prompt,
            validation=result,
            reload_count=0,
            reload_succeeded=False,
        )

    # Prompt failed validation -- try reloading from disk template
    best_prompt = prompt
    best_result = result
    reload_count = 0

    for attempt in range(max_reload_attempts):
        reload_count += 1
        logger.info(
            "Prompt integrity reload attempt %d/%d for %s (reason: %s)",
            reload_count, max_reload_attempts, agent_type, best_result.reason,
        )

        try:
            template = get_agent_prompt_template(agent_type, agents_dir=agents_dir)
        except FileNotFoundError:
            logger.warning(
                "Cannot reload agent template for %s: file not found", agent_type
            )
            break

        # Validate the reloaded template
        reloaded_result = validate_prompt_word_count(
            agent_type, template, baseline_word_count,
            max_shrinkage=max_shrinkage,
            invocation_context=invocation_context,
        )

        if reloaded_result.passed:
            logger.info(
                "Reload attempt %d succeeded for %s (%d words)",
                reload_count, agent_type, reloaded_result.word_count,
            )
            return ValidateAndReloadResult(
                prompt=template,
                validation=reloaded_result,
                reload_count=reload_count,
                reload_succeeded=True,
            )

        # Reloaded template also failed -- keep the better one (more words)
        if reloaded_result.word_count > best_result.word_count:
            best_prompt = template
            best_result = reloaded_result

        logger.warning(
            "Reload attempt %d for %s still below threshold (%d words, %s)",
            reload_count, agent_type, reloaded_result.word_count, reloaded_result.reason,
        )

    # All reload attempts exhausted
    logger.error(
        "All %d reload attempts failed for %s. Best: %d words. Reason: %s",
        reload_count, agent_type, best_result.word_count, best_result.reason,
    )
    return ValidateAndReloadResult(
        prompt=best_prompt,
        validation=best_result,
        reload_count=reload_count,
        reload_succeeded=False,
    )


def _get_baselines_path(state_dir: Optional[Path] = None) -> Path:
    """Resolve the path to the prompt baselines JSON file.

    Args:
        state_dir: Optional override directory. If None, uses project root.

    Returns:
        Absolute path to prompt_baselines.json.
    """
    if state_dir is not None:
        return state_dir / "prompt_baselines.json"
    root = _find_project_root()
    return root / _DEFAULT_BASELINES_RELPATH


def record_prompt_baseline(
    agent_type: str,
    issue_number: int,
    word_count: int,
    *,
    state_dir: Optional[Path] = None,
) -> None:
    """Record prompt word count as baseline for comparison across issues.

    Persists to .claude/logs/prompt_baselines.json (or state_dir override).
    Structure: {agent_type: {str(issue_number): word_count}}

    Args:
        agent_type: Agent name (e.g., 'reviewer').
        issue_number: GitHub issue number being processed.
        word_count: Word count of the prompt sent to this agent.
        state_dir: Optional override for state directory.
    """
    baselines_path = _get_baselines_path(state_dir)
    baselines_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if baselines_path.exists():
        try:
            data = json.loads(baselines_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read baselines file, starting fresh: %s", baselines_path)
            data = {}

    if agent_type not in data:
        data[agent_type] = {}

    data[agent_type][str(issue_number)] = word_count

    baselines_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.debug(
        "Recorded baseline: %s issue #%d = %d words", agent_type, issue_number, word_count
    )


def get_prompt_baseline(
    agent_type: str,
    *,
    issue_number: Optional[int] = None,
    state_dir: Optional[Path] = None,
) -> Optional[int]:
    """Get the baseline word count for an agent (per-issue isolated).

    When ``issue_number`` is provided, returns the baseline for THAT specific
    issue ONLY (per-issue isolation — Issue #764). If no baseline exists for
    that exact issue, returns ``None`` — the caller is expected to seed a new
    baseline from the first observed prompt. This is the contract that makes
    the first dispatch of a new issue safe in batch mode (Issue #1082 Phase 1a):
    a new issue MUST NOT be compared against a prior issue's baseline because
    that would guarantee a false-positive shrinkage block on first dispatch.

    When ``issue_number`` is None, falls back to the original single-issue
    behavior: returns the word count from the lowest-numbered issue. This
    preserves backward compatibility for non-batch callers.

    For cross-issue baseline comparison (the value of the lowest-issue baseline
    across the batch), use :func:`get_cross_issue_baseline`. For cross-issue
    drift detection (the recommended path), use
    :func:`record_batch_observation` + :func:`get_cumulative_shrinkage`
    (Issue #794) — that mechanism tracks the trajectory across the entire
    batch rather than collapsing it to a single first-issue value.

    History:
        - Issue #764 introduced per-issue baselines.
        - Issue #867 added a silent cross-issue fallback inside this function;
          that fallback contradicted #764 and caused first-dispatch blocks on
          every new issue in a batch.
        - Issue #1082 Phase 1a removed the silent fallback. Cross-issue
          baseline lookup is now an explicit, opt-in call to
          :func:`get_cross_issue_baseline`.

    Args:
        agent_type: Agent name to look up.
        issue_number: Specific issue to get baseline for. When provided, only
            returns the baseline recorded for this exact issue (no fallback).
            When None, returns the baseline from the lowest-numbered issue
            (backward-compat single-issue mode).
        state_dir: Optional override for state directory.

    Returns:
        Word count baseline for the requested issue, or None if no baseline
        exists for that issue. Callers that previously relied on the implicit
        cross-issue fallback should switch to :func:`get_cross_issue_baseline`
        or :func:`get_cumulative_shrinkage`.
    """
    baselines_path = _get_baselines_path(state_dir)

    if not baselines_path.exists():
        return None

    try:
        data = json.loads(baselines_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read baselines file: %s", baselines_path)
        return None

    agent_data = data.get(agent_type)
    if not agent_data:
        return None

    # Per-issue lookup (Issue #764, #1082 Phase 1a): return baseline for this
    # specific issue ONLY. If absent, return None so the caller seeds a new
    # baseline from observation instead of inheriting a prior issue's value.
    if issue_number is not None:
        issue_key = str(issue_number)
        baseline = agent_data.get(issue_key)
        if baseline is not None:
            logger.debug(
                "Per-issue baseline lookup: %s issue #%s = %d words",
                agent_type, issue_key, baseline,
            )
            return baseline
        logger.debug(
            "No per-issue baseline for %s issue #%s; returning None "
            "(caller should seed from observation). For cross-issue lookup, "
            "use get_cross_issue_baseline().",
            agent_type, issue_key,
        )
        return None

    # Backward compat: find entry with lowest issue number (single-issue mode)
    try:
        lowest_issue = min(agent_data.keys(), key=lambda k: int(k))
        return agent_data[lowest_issue]
    except (ValueError, TypeError):
        return None


def get_cross_issue_baseline(
    agent_type: str,
    *,
    exclude_issue: Optional[int] = None,
    state_dir: Optional[Path] = None,
) -> Optional[int]:
    """Get the lowest-issue baseline across all recorded issues for an agent.

    Returns the word-count baseline from the lowest-numbered issue that has a
    recorded baseline for ``agent_type``. When ``exclude_issue`` is provided,
    that issue is excluded from consideration — useful for the "compare against
    OTHER issues' baselines" pattern (e.g., on the second+ dispatch within an
    issue, callers may want to compare against prior issues' baselines without
    re-considering the current issue's own first-dispatch value).

    This is the explicit cross-issue lookup that was previously implemented as
    a silent fallback inside :func:`get_prompt_baseline` (Issue #867). It was
    extracted in Issue #1082 Phase 1a to resolve the contradiction with #764's
    per-issue isolation contract. The two intents — per-issue isolation and
    cross-issue baseline lookup — now live in separate functions so callers
    can pick the one they actually want.

    For cross-issue *drift detection* in batch mode, prefer
    :func:`record_batch_observation` + :func:`get_cumulative_shrinkage`
    (Issue #794). That mechanism tracks the full trajectory of word counts
    across the batch and reports cumulative drift against
    :data:`MAX_CUMULATIVE_SHRINKAGE`, rather than collapsing the batch history
    to a single first-issue value. Use ``get_cross_issue_baseline`` only when
    you need the specific lowest-issue baseline value itself (e.g., for
    diagnostics or one-shot threshold comparisons).

    Args:
        agent_type: Agent name to look up.
        exclude_issue: If provided, skip this issue when selecting the
            lowest-numbered issue. Used by callers that want "the lowest OTHER
            issue's baseline".
        state_dir: Optional override for state directory.

    Returns:
        Word count baseline from the lowest-numbered issue (excluding
        ``exclude_issue`` if provided), or None if no qualifying baseline
        exists.
    """
    baselines_path = _get_baselines_path(state_dir)

    if not baselines_path.exists():
        return None

    try:
        data = json.loads(baselines_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read baselines file: %s", baselines_path)
        return None

    agent_data = data.get(agent_type)
    if not agent_data:
        return None

    candidate_keys = list(agent_data.keys())
    if exclude_issue is not None:
        exclude_key = str(exclude_issue)
        candidate_keys = [k for k in candidate_keys if k != exclude_key]

    if not candidate_keys:
        return None

    try:
        lowest_issue = min(candidate_keys, key=lambda k: int(k))
    except (ValueError, TypeError):
        return None

    baseline = agent_data[lowest_issue]
    logger.debug(
        "Cross-issue baseline lookup: %s -> using issue #%s baseline = %d words "
        "(exclude_issue=%s)",
        agent_type, lowest_issue, baseline, exclude_issue,
    )
    return baseline


def clear_prompt_baselines(*, state_dir: Optional[Path] = None) -> None:
    """Clear all prompt baselines and batch observations. Call at batch start.

    Also clears batch observations (Issue #794) so cumulative drift tracking
    resets alongside baselines.

    Args:
        state_dir: Optional override for state directory.
    """
    baselines_path = _get_baselines_path(state_dir)
    if baselines_path.exists():
        baselines_path.unlink()
        logger.debug("Cleared prompt baselines: %s", baselines_path)
    # Also clear batch observations (Issue #794)
    clear_batch_observations(state_dir=state_dir)


def compute_template_baselines(*, agents_dir: Optional[Path] = None) -> dict:
    """Compute word counts for each critical agent's prompt template.

    Reads each agent's .md file from disk and measures its word count.
    Agents with missing template files are skipped with a warning.

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
            logger.debug(
                "Template baseline computed: %s = %d words", agent_type, baselines[agent_type]
            )
        except OSError as exc:
            logger.warning(
                "Template baseline: could not read %s: %s", agent_file, exc
            )

    return baselines


def seed_baselines_from_templates(
    *,
    agents_dir: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> dict:
    """No-op: template-based baseline seeding is deprecated (Issue #810).

    Previously, this function seeded baselines at 0.70x template word count
    (~477-1877 words) before the first batch issue. However, actual task-specific
    prompts are 200-600 words, causing a systematic 25-50% false positive block
    rate. The hook's else-branch correctly seeds from the first observed prompt
    when no baseline exists — template seeding was pre-empting this correct path.

    The observation-based path (seeding from the first real prompt per agent per
    issue) is the correct approach. Call ``clear_prompt_baselines()`` at batch
    start to reset state; baselines are then established automatically from the
    first observed prompt for each agent.

    Args:
        agents_dir: Ignored (kept for backwards-compatible signature).
        state_dir: Ignored (kept for backwards-compatible signature).

    Returns:
        Empty dict — no baselines are written.
    """
    logger.warning(
        "seed_baselines_from_templates() is deprecated (Issue #810). "
        "Baselines are now established automatically from the first observed prompt. "
        "Call clear_prompt_baselines() at batch start instead."
    )
    return {}


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
