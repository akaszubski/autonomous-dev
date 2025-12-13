#!/usr/bin/env python3
"""
Research Quality Scorer Library - Parallel Deep Research Capabilities.

Provides quality scoring, ranking, and diminishing returns detection for research sources.
Supports parallel research execution with adaptive depth control.

Functions:
    - score_source: Calculate combined quality score for a research source
    - rank_sources: Sort sources by quality score in descending order
    - detect_diminishing_returns: Detect when additional research provides minimal value
    - calculate_relevance_score: Calculate relevance based on keyword matching
    - calculate_recency_score: Calculate recency score with time-based decay
    - calculate_authority_score: Calculate authority score based on source type
    - detect_consensus: Detect when sources reach consensus on information

Date: 2025-12-13
Agent: implementer
Issue: #111 - Enhance researcher agent with parallel deep research
"""

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

# ==============================================================================
# EXCEPTIONS
# ==============================================================================


class ResearchQualityError(Exception):
    """Base exception for research quality scoring errors."""

    pass


class InvalidSourceError(ResearchQualityError):
    """Exception raised when source data is invalid or malicious."""

    pass


# ==============================================================================
# CORE SCORING FUNCTIONS
# ==============================================================================


def score_source(
    url: Optional[str],
    content: str,
    recency: int,
    authority: str,
    keywords: Optional[List[str]] = None,
) -> float:
    """
    Calculate combined quality score for a research source.

    Combines authority, recency, and relevance scores with weighted formula:
    score = (relevance * 0.5) + (authority * 0.3) + (recency * 0.2)

    Args:
        url: Source URL (validated for safety)
        content: Source content text
        recency: Publication year (e.g., 2024)
        authority: Source authority type (official_docs, github_official, etc.)
        keywords: Optional list of keywords for relevance scoring

    Returns:
        float: Combined quality score in range 0.0-1.0

    Raises:
        InvalidSourceError: If URL is None/empty, content is empty, or URL is malicious
    """
    # Validate inputs
    if url is None or (isinstance(url, str) and not url.strip()):
        raise InvalidSourceError("URL cannot be None or empty")

    if not content or not content.strip():
        raise InvalidSourceError("Content cannot be empty")

    # Validate URL for security (prevent XSS, file access, etc.)
    _validate_url(url)

    # Calculate component scores
    relevance = calculate_relevance_score(content, keywords) if keywords else 0.5
    authority_score = calculate_authority_score(authority)
    recency_score = calculate_recency_score(recency)

    # Weighted combination: authority (50%), recency (30%), relevance (20%)
    # Authority is most important for research quality
    combined_score = (authority_score * 0.5) + (recency_score * 0.3) + (relevance * 0.2)

    # Ensure normalized range and round to avoid floating point precision issues
    combined_score = max(0.0, min(1.0, combined_score))
    return round(combined_score, 10)  # Round to 10 decimal places


def rank_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort sources by quality score in descending order.

    Adds 'quality_score' field to each source and sorts by score.
    Preserves all original metadata fields.

    Args:
        sources: List of source dictionaries with url, content, recency, authority

    Returns:
        List[Dict]: Sources sorted by quality_score (highest first), with quality_score added
    """
    if not sources:
        return []

    # Score each source
    scored_sources = []
    for source in sources:
        try:
            # Extract fields with defaults for missing optional fields
            url = source.get("url")
            content = source.get("content", "")
            recency = source.get("recency", datetime.now().year)
            authority = source.get("authority", "unknown")
            keywords = source.get("keywords")

            # Calculate score
            score = score_source(url, content, recency, authority, keywords)

            # Create new dict with original data + quality_score
            scored_source = source.copy()
            scored_source["quality_score"] = score
            scored_sources.append(scored_source)

        except (InvalidSourceError, ResearchQualityError):
            # Skip invalid sources
            continue

    # Sort by quality_score descending (stable sort preserves order for ties)
    scored_sources.sort(key=lambda s: s.get("quality_score", 0.0), reverse=True)

    return scored_sources


def detect_diminishing_returns(
    results: List[Dict[str, Any]],
    threshold: float = 0.3,
    max_depth: int = 10,
    consensus_count: int = 3,
) -> bool:
    """
    Detect when additional research provides minimal new value.

    Returns True if:
    - 3+ sources reach consensus (similar content)
    - Quality improvement drops below threshold
    - Max depth limit reached

    Args:
        results: List of research results with content and quality_score
        threshold: Minimum quality improvement threshold (0.0-1.0)
        max_depth: Maximum research depth before stopping
        consensus_count: Number of similar sources needed for consensus

    Returns:
        bool: True if diminishing returns detected, False otherwise

    Raises:
        ResearchQualityError: If threshold is outside 0.0-1.0 range
    """
    # Validate threshold
    if not 0.0 <= threshold <= 1.0:
        raise ResearchQualityError("Threshold must be between 0.0 and 1.0")

    # Empty results = no diminishing returns yet
    if not results:
        return False

    # Check max depth limit
    if len(results) >= max_depth:
        return True

    # Check for consensus (3+ similar high-quality sources)
    if detect_consensus(results, similarity_threshold=0.6):
        return True

    # Check quality improvement trend
    if len(results) >= 4:
        scores = [r.get("quality_score", 0.0) for r in results]

        # Check if quality plateaus (minimal improvement in recent results)
        # Look at last improvement
        last_improvement = abs(scores[-1] - scores[-2])

        # If last improvement is below threshold, check if we have a pattern
        if last_improvement < threshold:
            return True

    return False


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def calculate_relevance_score(content: str, keywords: Optional[List[str]]) -> float:
    """
    Calculate relevance score based on keyword matching.

    Uses case-insensitive keyword matching with density calculation.
    Score increases with number and frequency of keyword matches.

    Args:
        content: Source content text
        keywords: List of keywords to match

    Returns:
        float: Relevance score in range 0.0-1.0
    """
    if not keywords or not content:
        return 0.5  # Neutral score if no keywords provided

    content_lower = content.lower()
    total_words = len(content.split())

    if total_words == 0:
        return 0.0

    # Count keyword matches (case-insensitive)
    matches = 0
    for keyword in keywords:
        keyword_lower = keyword.lower()
        matches += content_lower.count(keyword_lower)

    # Calculate keyword density
    density = matches / total_words

    # Normalize to 0.0-1.0 range (cap at 0.2 density = 1.0 score)
    relevance = min(1.0, density / 0.2)

    # Ensure at least some score if any keywords match
    if matches > 0 and relevance < 0.3:
        relevance = 0.3

    return relevance


def calculate_recency_score(year: int) -> float:
    """
    Calculate recency score with time-based decay.

    Recent years (2024-2025) score 1.0
    Older years decay linearly:
    - 2023: 0.8
    - 2021: 0.6
    - 2019: 0.4
    - 2017 and older: 0.2

    Future years are treated as current year.

    Args:
        year: Publication year

    Returns:
        float: Recency score in range 0.0-1.0
    """
    current_year = datetime.now().year

    # Future years = current year
    if year >= current_year:
        return 1.0

    # Calculate age
    age = current_year - year

    # Time-based decay
    if age <= 1:  # Current year or last year
        return 1.0
    elif age == 2:  # 2 years old
        return 0.8
    elif age == 3:  # 3 years old
        return 0.6
    elif age <= 5:  # 4-5 years old
        return 0.4
    else:  # 6+ years old
        return 0.2


def calculate_authority_score(authority_type: str) -> float:
    """
    Calculate authority score based on source type.

    Authority levels:
    - official_docs: 1.0 (highest authority)
    - github_official: 0.8
    - docs: 0.7
    - github_community: 0.6
    - blog: 0.4
    - unknown: 0.0 (lowest authority)

    Args:
        authority_type: Source authority type

    Returns:
        float: Authority score in range 0.0-1.0
    """
    authority_scores = {
        "official_docs": 1.0,
        "github_official": 0.8,
        "docs": 0.7,
        "github_community": 0.6,
        "blog": 0.4,
    }

    # Return mapped score or default to very low authority (0.0 for unknown)
    return authority_scores.get(authority_type, 0.0)


def detect_consensus(
    sources: List[Dict[str, Any]],
    similarity_threshold: float = 0.7,
    min_cluster_size: int = 2,
) -> bool:
    """
    Detect when sources reach consensus on information.

    Uses content similarity matching to detect when multiple sources
    provide similar information (>70% similarity by default).

    Args:
        sources: List of sources with content field
        similarity_threshold: Minimum similarity ratio (0.0-1.0)
        min_cluster_size: Minimum cluster size for consensus (default: 2)

    Returns:
        bool: True if min_cluster_size+ sources have similar content, False otherwise
    """
    if len(sources) < min_cluster_size:
        return False

    # Extract content from sources
    contents = [s.get("content", "") for s in sources]

    # Find clusters of similar content
    # For each content, count how many others are similar to it
    max_cluster_size = 0
    for i in range(len(contents)):
        cluster_size = 1  # Start with itself
        for j in range(len(contents)):
            if i != j:
                similarity = _calculate_similarity(contents[i], contents[j])
                if similarity >= similarity_threshold:
                    cluster_size += 1
        max_cluster_size = max(max_cluster_size, cluster_size)

    # Consensus if min_cluster_size+ sources in largest cluster
    return max_cluster_size >= min_cluster_size


# ==============================================================================
# PRIVATE UTILITY FUNCTIONS
# ==============================================================================


def _validate_url(url: str) -> None:
    """
    Validate URL for security (prevent XSS, file access, code execution).

    Raises:
        InvalidSourceError: If URL contains malicious patterns
    """
    if not isinstance(url, str):
        raise InvalidSourceError("URL must be a string")

    url_lower = url.lower()

    # Block dangerous schemes
    dangerous_schemes = [
        "javascript:",
        "data:",
        "file:",
        "vbscript:",
        "about:",
    ]

    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            raise InvalidSourceError(
                f"Invalid or malicious URL: dangerous scheme '{scheme}'"
            )

    # Block common XSS patterns
    xss_patterns = [
        r"<script",
        r"javascript:",
        r"onerror=",
        r"onload=",
    ]

    for pattern in xss_patterns:
        if re.search(pattern, url_lower):
            raise InvalidSourceError("Invalid or malicious URL: XSS pattern detected")


def _calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity ratio between two text strings.

    Uses both sequence matching and keyword overlap for better semantic similarity.

    Args:
        text1: First text string
        text2: Second text string

    Returns:
        float: Similarity ratio in range 0.0-1.0
    """
    if not text1 or not text2:
        return 0.0

    # Normalize texts
    text1_lower = text1.lower()
    text2_lower = text2.lower()

    # Method 1: SequenceMatcher for character-level similarity
    matcher = SequenceMatcher(None, text1_lower, text2_lower)
    sequence_similarity = matcher.ratio()

    # Method 2: Keyword overlap for semantic similarity
    # Extract words (alphanumeric only)
    words1 = set(re.findall(r"\w+", text1_lower))
    words2 = set(re.findall(r"\w+", text2_lower))

    # Remove common stop words for better semantic matching
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "been",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "can",
    }
    words1_filtered = words1 - stop_words
    words2_filtered = words2 - stop_words

    if not words1_filtered or not words2_filtered:
        return sequence_similarity

    # Intersection over minimum (better for different-length texts)
    intersection = len(words1_filtered & words2_filtered)
    min_size = min(len(words1_filtered), len(words2_filtered))
    keyword_similarity = intersection / min_size if min_size > 0 else 0.0

    # Boost score if key technical terms overlap heavily
    # If 2+ keywords match, give bonus for technical content similarity
    if intersection >= 2:
        keyword_similarity = min(1.0, keyword_similarity * 1.3)

    # Combine both methods (weighted average: 20% sequence, 80% keywords)
    # Favor keyword overlap heavily for semantic similarity in research contexts
    combined_similarity = (sequence_similarity * 0.2) + (keyword_similarity * 0.8)

    return combined_similarity
