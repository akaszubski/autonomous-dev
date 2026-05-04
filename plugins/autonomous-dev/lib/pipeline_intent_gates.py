"""Phase 2 (#961) classifier-gated pipeline skip predicates.

Pure functions; no I/O. The implement.md coordinator imports these and
acts on the boolean result. Telemetry persistence is the caller's job
(via pipeline_completion_state).

Issues: #961
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from intent_classifier import IntentClass, IntentResult, classify_prompt  # type: ignore[import-not-found]
except ImportError:
    IntentClass = None  # type: ignore[assignment]
    IntentResult = None  # type: ignore[assignment]
    classify_prompt = None  # type: ignore[assignment]


WEB_RESEARCH_SKIP_INTENTS = frozenset({"config", "doc", "refactor"})
PLAN_CRITIC_SKIP_INTENTS = frozenset({"refactor", "config", "doc", "typo"})

CONFIDENCE_THRESHOLD = 0.85
MAX_FILES_FOR_PLAN_CRITIC_SKIP = 3


def _truthy(val: Optional[str]) -> bool:
    """Strict truthy parse for env vars: only 'true'/'1'/'yes' (case-insensitive).

    Args:
        val: Environment variable value string, or None if unset.

    Returns:
        True only when val is "true", "1", or "yes" (case-insensitive).
    """
    if val is None:
        return False
    return val.strip().lower() in ("true", "1", "yes")


def classifier_enabled() -> bool:
    """Check if INTENT_CLASSIFIER_ENABLED env var is explicitly truthy.

    Returns:
        True when INTENT_CLASSIFIER_ENABLED is explicitly truthy. Default: False.
    """
    return _truthy(os.environ.get("INTENT_CLASSIFIER_ENABLED"))


def strict_mode(arguments: str) -> bool:
    """Check if --strict appears as a whole token in ARGUMENTS.

    Args:
        arguments: The ARGUMENTS string from the pipeline context.

    Returns:
        True when --strict appears as a whole token in ARGUMENTS.
    """
    if not arguments:
        return False
    return "--strict" in arguments.split()


def should_skip_web_research(
    *,
    feature_description: str,
    arguments: str = "",
    classifier_result: Optional["IntentResult"] = None,  # type: ignore[type-arg]
) -> tuple[bool, str]:
    """Decide whether to skip web research (researcher agent) at STEP 4.

    Args:
        feature_description: The feature description string to classify.
        arguments: The ARGUMENTS string from the pipeline context.
        classifier_result: Optional pre-computed IntentResult. If None, will
            call classify_prompt(feature_description). Accepts pre-computed
            results to avoid redundant LLM calls when both gates share a run.

    Returns:
        Tuple of (skip: bool, reason: str). When skip is True, reason is
        "classifier:{intent}". When skip is False, reason explains why.

    Issues: #961
    """
    if not classifier_enabled():
        return False, "disabled"
    if strict_mode(arguments):
        return False, "strict"
    if classify_prompt is None:
        return False, "classifier_unavailable"

    result = classifier_result
    if result is None:
        try:
            result = classify_prompt(feature_description)
        except Exception:  # noqa: BLE001
            return False, "classifier_exception"

    if result.fail_open or result.intent.value == "ambiguous":
        return False, "fail_open"
    if result.confidence < CONFIDENCE_THRESHOLD:
        return False, "low_confidence"
    if result.intent.value not in WEB_RESEARCH_SKIP_INTENTS:
        return False, f"intent:{result.intent.value}"
    return True, f"classifier:{result.intent.value}"


def should_skip_plan_critic(
    *,
    feature_description: str,
    arguments: str = "",
    classifier_result: Optional["IntentResult"] = None,  # type: ignore[type-arg]
) -> tuple[bool, str]:
    """Decide whether to skip plan-critic (5.5b) for small REFACTOR/CONFIG/DOC/TYPO.

    Args:
        feature_description: The feature description string to classify.
        arguments: The ARGUMENTS string from the pipeline context.
        classifier_result: Optional pre-computed IntentResult. If None, will
            call classify_prompt(feature_description). Accepts pre-computed
            results to avoid redundant LLM calls when both gates share a run.

    Returns:
        Tuple of (skip: bool, reason: str). When skip is True, reason is
        "classifier:{intent}". When skip is False, reason explains why.

    Issues: #961
    """
    if not classifier_enabled():
        return False, "disabled"
    if strict_mode(arguments):
        return False, "strict"
    if classify_prompt is None:
        return False, "classifier_unavailable"

    result = classifier_result
    if result is None:
        try:
            result = classify_prompt(feature_description)
        except Exception:  # noqa: BLE001
            return False, "classifier_exception"

    if result.fail_open or result.intent.value == "ambiguous":
        return False, "fail_open"
    if result.confidence < CONFIDENCE_THRESHOLD:
        return False, "low_confidence"
    if result.intent.value not in PLAN_CRITIC_SKIP_INTENTS:
        return False, f"intent:{result.intent.value}"
    if result.predicted_file_count > MAX_FILES_FOR_PLAN_CRITIC_SKIP:
        return False, f"file_count:{result.predicted_file_count}"
    return True, f"classifier:{result.intent.value}"
