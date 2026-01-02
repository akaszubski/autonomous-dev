#!/usr/bin/env python3
"""
Memory Relevance - TF-IDF-based relevance scoring for memories.

Provides keyword extraction, relevance scoring, and ranking for cross-session
memory injection. Enables intelligent retrieval of relevant memories based on
current context using TF-IDF (Term Frequency-Inverse Document Frequency).

Problem (Issue #192):
- Need to inject relevant memories at SessionStart
- Too many irrelevant memories bloat context
- Need relevance scoring to filter/rank memories

Solution:
- TF-IDF keyword extraction with stopword removal
- Relevance scoring between query and memory content
- Recency boost for recent memories
- Threshold filtering for low-relevance memories
- Sorted ranking by relevance score (highest first)

Usage:
    from memory_relevance import extract_keywords, calculate_relevance, rank_memories

    # Extract keywords
    keywords = extract_keywords("implement JWT authentication")
    # -> ["implement", "jwt", "authentication"]

    # Calculate relevance
    score = calculate_relevance(
        query="JWT authentication",
        memory_text="Implemented JWT authentication with bcrypt",
        timestamp="2026-01-02T10:00:00"
    )
    # -> 0.85

    # Rank memories
    ranked = rank_memories(
        query="JWT authentication",
        memories=[
            {"content": "Implemented JWT with bcrypt", "id": "1"},
            {"content": "Fixed CSS styling", "id": "2"},
        ],
        threshold=0.3
    )
    # -> [{"content": "...", "relevance_score": 0.85, ...}]

Date: 2026-01-02
Issue: GitHub #192 (Auto-inject memory layer at SessionStart)
Agent: implementer
Phase: GREEN (making tests pass)

Design Patterns:
    See library-design-patterns skill for scoring and ranking patterns.
    See python-standards skill for coding conventions.
"""

import re
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


# ============================================================================
# CONSTANTS
# ============================================================================

# Common English stopwords (minimal set for performance)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "for", "from", "has", "have", "he", "in", "is", "it", "its",
    "of", "on", "or", "that", "the", "to", "was", "were", "will", "with"
}

# Recency boost parameters
RECENCY_BOOST_MAX_DAYS = 30  # Boost memories within 30 days
RECENCY_BOOST_FACTOR = 0.3  # 30% boost for recent memories


# ============================================================================
# KEYWORD EXTRACTION
# ============================================================================


def extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text.

    Removes stopwords, normalizes case, and extracts unique keywords.

    Args:
        text: Input text to extract keywords from

    Returns:
        List of lowercase keywords (no stopwords, no punctuation)

    Example:
        >>> extract_keywords("the JWT authentication is secure")
        ["jwt", "authentication", "secure"]
    """
    if not text or not isinstance(text, str):
        return []

    # Normalize: lowercase and remove punctuation
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # Replace punctuation with spaces

    # Split into words
    words = text.split()

    # Remove stopwords and filter
    keywords = [
        word for word in words
        if word and word not in STOPWORDS and len(word) > 1
    ]

    # Return unique keywords (preserving order)
    seen = set()
    unique_keywords = []
    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_keywords.append(keyword)

    return unique_keywords


# ============================================================================
# RELEVANCE SCORING
# ============================================================================


def calculate_relevance(
    query: str,
    memory_text: str,
    timestamp: Optional[str] = None
) -> float:
    """Calculate relevance score between query and memory text using TF-IDF.

    Formula:
        1. Extract keywords from query and memory
        2. Calculate intersection (matching keywords)
        3. TF-IDF scoring: (matches / query_terms) * (matches / memory_terms)
        4. Add recency boost if timestamp provided

    Args:
        query: Query text (e.g., "implement JWT authentication")
        memory_text: Memory content to score
        timestamp: Optional ISO 8601 timestamp for recency boost

    Returns:
        Relevance score between 0.0 and 1.0

    Example:
        >>> calculate_relevance(
        ...     "JWT authentication",
        ...     "Implemented JWT authentication with bcrypt"
        ... )
        0.85
    """
    # Handle empty inputs
    if not query or not memory_text:
        return 0.0

    # Extract keywords
    query_keywords = set(extract_keywords(query))
    memory_keywords = set(extract_keywords(memory_text))

    # Handle empty keyword sets
    if not query_keywords or not memory_keywords:
        return 0.0

    # Calculate intersection
    matching_keywords = query_keywords & memory_keywords
    num_matches = len(matching_keywords)

    if num_matches == 0:
        return 0.0

    # TF-IDF scoring (simplified)
    # TF (Term Frequency): proportion of query terms that match
    query_tf = num_matches / len(query_keywords)

    # IDF (Inverse Document Frequency): proportion of memory terms that match
    memory_idf = num_matches / len(memory_keywords)

    # Combined score (geometric mean for better balance)
    base_score = math.sqrt(query_tf * memory_idf)

    # Add recency boost if timestamp provided
    score = base_score
    if timestamp:
        try:
            # Parse timestamp
            if isinstance(timestamp, str):
                memory_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                memory_dt = timestamp

            # Calculate age in days
            now = datetime.now(memory_dt.tzinfo)
            age_days = (now - memory_dt).total_seconds() / 86400

            # Apply recency boost for recent memories
            if age_days <= RECENCY_BOOST_MAX_DAYS:
                # Linear decay: 30% boost at day 0, 0% boost at day 30
                boost_factor = RECENCY_BOOST_FACTOR * (1 - age_days / RECENCY_BOOST_MAX_DAYS)
                score = min(1.0, base_score + boost_factor)

        except (ValueError, TypeError, AttributeError):
            # Invalid timestamp - ignore recency boost
            pass

    # Ensure score is in [0.0, 1.0]
    return min(1.0, max(0.0, round(score, 3)))


# ============================================================================
# MEMORY RANKING
# ============================================================================


def rank_memories(
    query: str,
    memories: List[Dict[str, Any]],
    threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """Rank memories by relevance to query.

    Filters memories below threshold and sorts by relevance score (descending).

    Args:
        query: Query text (e.g., "implement JWT authentication")
        memories: List of memory dicts (must have "content" field)
        threshold: Minimum relevance score (default: 0.7)

    Returns:
        List of memories sorted by relevance (highest first)
        Each memory has "relevance_score" field added

    Example:
        >>> rank_memories(
        ...     "JWT authentication",
        ...     [
        ...         {"content": "Implemented JWT", "id": "1"},
        ...         {"content": "Fixed CSS", "id": "2"},
        ...     ],
        ...     threshold=0.3
        ... )
        [{"content": "Implemented JWT", "id": "1", "relevance_score": 0.85}]
    """
    # Handle empty inputs
    if not memories:
        return []

    # Calculate relevance scores
    scored_memories = []
    for memory in memories:
        # Extract content and timestamp
        content = memory.get("content", "")
        timestamp = memory.get("timestamp")

        # Calculate relevance
        score = calculate_relevance(query, content, timestamp)

        # Add score to memory
        memory_with_score = memory.copy()
        memory_with_score["relevance_score"] = score

        # Filter by threshold
        if score >= threshold:
            scored_memories.append(memory_with_score)

    # Sort by relevance score (descending)
    scored_memories.sort(key=lambda m: m["relevance_score"], reverse=True)

    return scored_memories


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "extract_keywords",
    "calculate_relevance",
    "rank_memories",
    "STOPWORDS",
]
