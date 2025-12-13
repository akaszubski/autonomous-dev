#!/usr/bin/env python3
"""
Pipeline Classification Library - Classify feature requests into pipeline types

This library provides keyword-based classification to route user requests
to appropriate execution pipelines:

- MINIMAL: Fast path for typos, style fixes, small changes
- FULL: Standard path for features, improvements, significant changes
- DOCS_ONLY: Documentation-only path (skip TDD, implementation)

Classification improves performance by:
- Skipping expensive phases for simple changes (typos → 1 min vs 20 min)
- Running full validation only when needed
- Routing pure docs work directly to doc-master

Security: All inputs validated, no code execution based on user input

Usage:
    from pipeline_classifier import classify_request, PipelineType

    # Classify user request
    pipeline = classify_request("Fix typo in README")
    # Returns: PipelineType.MINIMAL

    # Use classification to select pipeline
    if pipeline == PipelineType.MINIMAL:
        # Fast path: implementer only, no TDD
        run_minimal_pipeline()
    elif pipeline == PipelineType.DOCS_ONLY:
        # Docs path: doc-master only
        run_docs_pipeline()
    else:
        # Full path: TDD, review, security, docs
        run_full_pipeline()

Design Patterns:
    - Keyword-based heuristics (simple, fast, maintainable)
    - Conservative fallback (ambiguous → FULL)
    - Case-insensitive matching
    - Negation detection (prevent false positives)

Date: 2025-12-13
Issue: GitHub #120 (Performance improvements - pipeline classification)
Agent: implementer
Phase: TDD Green Phase
"""

from enum import Enum
from typing import List
import re


class PipelineType(Enum):
    """Pipeline type enumeration for request classification.

    Values:
        MINIMAL: Fast path for typos, style fixes, simple changes (< 2 min)
        FULL: Standard path for features, improvements (15-25 min)
        DOCS_ONLY: Documentation-only path (< 5 min)
    """
    MINIMAL = "minimal"
    FULL = "full"
    DOCS_ONLY = "docs_only"


# Classification keywords (lowercase for case-insensitive matching)
MINIMAL_KEYWORDS = [
    "typo",
    "spelling",
    "grammar",
    "whitespace",
    "formatting",
    "style",
    "comment",
    "indent",
]

DOCS_KEYWORDS = [
    "documentation",
    "readme",
    "doc",
    "docs",
    "guide",
    "tutorial",
    "example",
    "architecture decision record",
    "adr",
]

FULL_KEYWORDS = [
    "add",
    "create",
    "implement",
    "feature",
    "new",
    "build",
    "develop",
    "enhancement",
    "improve",
    "refactor",
    "update",
    "change",
    "modify",
]

# Negation words (prevent false positives)
NEGATION_KEYWORDS = [
    "not",
    "don't",
    "doesn't",
    "no",
    "never",
    "without",
]


def classify_request(description: str) -> PipelineType:
    """Classify user request into appropriate pipeline type.

    Uses keyword-based heuristics to determine the best pipeline:
    - MINIMAL: Typos, style fixes, small changes (fast path)
    - FULL: Features, improvements, significant changes (standard path)
    - DOCS_ONLY: Pure documentation work (docs-only path)

    Classification Rules:
    1. Empty/whitespace → FULL (safe default)
    2. Negation detected → Skip keyword (prevent false positives)
    3. MINIMAL keywords → MINIMAL (highest priority for speed)
    4. DOCS keywords + no code keywords → DOCS_ONLY
    5. FULL keywords → FULL
    6. Ambiguous → FULL (conservative fallback)

    Args:
        description: User request description (e.g., "Fix typo in README")

    Returns:
        PipelineType enum value (MINIMAL, FULL, or DOCS_ONLY)

    Examples:
        >>> classify_request("Fix typo in README")
        PipelineType.MINIMAL

        >>> classify_request("Add authentication system")
        PipelineType.FULL

        >>> classify_request("Update documentation")
        PipelineType.DOCS_ONLY

        >>> classify_request("")
        PipelineType.FULL

        >>> classify_request("This is not a typo")
        PipelineType.FULL

    Security:
        - Input validation: No code execution based on user input
        - Length check: Handles very long descriptions efficiently
        - Injection prevention: Only string matching, no eval/exec

    Performance:
        - Time complexity: O(n) where n is description length
        - Space complexity: O(1) (no dynamic allocations)
        - Typical execution: < 1ms for any description length
    """
    # Validate input (handle None, empty, whitespace)
    if not description or not description.strip():
        return PipelineType.FULL  # Safe default for empty input

    # Normalize description (lowercase for case-insensitive matching)
    normalized = description.lower()

    # Check for negation words (prevent false positives)
    # If negation found near keywords, skip classification
    has_negation = any(
        negation in normalized
        for negation in NEGATION_KEYWORDS
    )

    # Priority 1: MINIMAL keywords (highest priority for speed)
    # Typos, style fixes should use fast path
    for keyword in MINIMAL_KEYWORDS:
        if keyword in normalized:
            # Check if negated (e.g., "not a typo")
            if has_negation:
                # Look for negation near the keyword
                keyword_pos = normalized.find(keyword)
                # Check 20 chars before keyword for negation
                context_start = max(0, keyword_pos - 20)
                context = normalized[context_start:keyword_pos + len(keyword)]

                if any(neg in context for neg in NEGATION_KEYWORDS):
                    continue  # Skip this keyword, it's negated

            return PipelineType.MINIMAL

    # Priority 2: DOCS_ONLY keywords (check before FULL)
    # Pure documentation work should skip TDD and implementation
    # Note: Check this BEFORE FULL because words like "update", "add" are in FULL_KEYWORDS
    # but "update documentation" should be DOCS_ONLY
    has_docs_keyword = any(keyword in normalized for keyword in DOCS_KEYWORDS)

    if has_docs_keyword:
        # Check if there are code-related keywords that suggest actual implementation
        # Exclude generic words like "update", "add" when they apply to docs
        code_specific_keywords = [
            "implement", "feature", "new", "build", "develop",
            "enhancement", "refactor", "change", "modify"
        ]
        has_code_specific = any(keyword in normalized for keyword in code_specific_keywords)

        if not has_code_specific:
            # Pure docs work (no specific code changes mentioned)
            return PipelineType.DOCS_ONLY

    # Priority 3: FULL keywords
    # Feature requests, improvements, changes
    for keyword in FULL_KEYWORDS:
        if keyword in normalized:
            return PipelineType.FULL

    # Fallback: Conservative default
    # If classification is uncertain, use FULL pipeline
    # Better to do extra work than skip needed validation
    return PipelineType.FULL


def get_pipeline_description(pipeline_type: PipelineType) -> str:
    """Get human-readable description of pipeline type.

    Args:
        pipeline_type: PipelineType enum value

    Returns:
        Description string explaining the pipeline

    Examples:
        >>> get_pipeline_description(PipelineType.MINIMAL)
        'Fast path: implementer only, no TDD (< 2 min)'
    """
    descriptions = {
        PipelineType.MINIMAL: "Fast path: implementer only, no TDD (< 2 min)",
        PipelineType.FULL: "Standard path: TDD, review, security, docs (15-25 min)",
        PipelineType.DOCS_ONLY: "Documentation-only path: doc-master only (< 5 min)",
    }
    return descriptions.get(pipeline_type, "Unknown pipeline type")


def get_pipeline_agents(pipeline_type: PipelineType) -> List[str]:
    """Get list of agents for pipeline type.

    Args:
        pipeline_type: PipelineType enum value

    Returns:
        List of agent names that should execute in this pipeline

    Examples:
        >>> get_pipeline_agents(PipelineType.MINIMAL)
        ['implementer']

        >>> get_pipeline_agents(PipelineType.FULL)
        ['researcher', 'planner', 'test-master', 'implementer', 'reviewer', 'security-auditor', 'doc-master']
    """
    agent_lists = {
        PipelineType.MINIMAL: [
            "implementer"  # Fast path: just make the fix
        ],
        PipelineType.FULL: [
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ],
        PipelineType.DOCS_ONLY: [
            "doc-master"  # Docs-only: skip code phases
        ],
    }
    return agent_lists.get(pipeline_type, agent_lists[PipelineType.FULL])


# Export public API
__all__ = [
    "PipelineType",
    "classify_request",
    "get_pipeline_description",
    "get_pipeline_agents",
]
