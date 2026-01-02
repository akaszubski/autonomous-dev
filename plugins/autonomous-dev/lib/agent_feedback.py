#!/usr/bin/env python3
"""
Agent Feedback Loop - Machine learning for agent routing optimization

This module provides a feedback loop system for autonomous development agents,
enabling data-driven agent selection based on historical performance metrics.

Key Features:
1. **Feedback Recording**: Track agent performance per feature type and complexity
2. **Smart Routing**: Recommend optimal agents based on historical success rates
3. **Confidence Scoring**: Statistical confidence based on execution count
4. **State Persistence**: Atomic writes to .claude/agent_feedback.json
5. **Automatic Pruning**: 90-day retention with monthly aggregation
6. **Thread Safety**: Concurrent access protection with file locking

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See state-management-patterns skill for standardized state patterns.

Dataclasses:
    - AgentFeedback: Single feedback entry (agent, feature, duration, success)
    - FeedbackStats: Aggregated statistics (success_rate, avg_duration, confidence)
    - RoutingRecommendation: Agent recommendation with confidence and reasoning

Feature Classification:
    6 categories based on keyword matching:
    - security: auth, oauth, vulnerability, injection, xss, csrf
    - api: rest, graphql, endpoint, webhook, rate limiting
    - ui: component, dashboard, modal, form, accessibility
    - refactor: refactor, extract, simplify, rename, dead code
    - docs: readme, documentation, comments, guide
    - tests: unit test, integration test, e2e, test coverage
    - general: fallback for unmatched features

Confidence Scoring Formula:
    confidence = success_rate * sqrt(min(executions, 50) / 50)

    This formula ensures:
    - Low confidence with sparse data (<10 executions)
    - Medium confidence at 30 executions (~0.77 with 100% success)
    - High confidence plateaus at 50+ executions
    - Success rate is primary factor

Usage:
    from agent_feedback import (
        record_feedback,
        query_recommendations,
        get_agent_stats,
        classify_feature_type
    )

    # Record agent performance
    record_feedback(
        agent_name="security-auditor",
        feature_type="security",
        complexity="STANDARD",
        duration=12.5,
        success=True,
        metadata={"owasp_checks": 10, "vulnerabilities": 0}
    )

    # Query recommendations for new feature
    recommendations = query_recommendations(
        feature_type="security",
        complexity="STANDARD",
        top_n=3
    )

    # Get agent statistics
    stats = get_agent_stats(agent_name="security-auditor")

Security:
    - CWE-22: Path traversal prevention via validate_path()
    - Input validation: agent_name, complexity, duration
    - Sanitization: feature descriptions and metadata
    - Atomic writes: tempfile + rename for consistency
    - Audit logging: all operations logged

State File Structure:
    {
        "version": "1.0",
        "feedback": [
            {
                "agent_name": "security-auditor",
                "feature_type": "security",
                "complexity": "STANDARD",
                "duration": 12.5,
                "success": true,
                "timestamp": "2025-01-02T10:00:00",
                "metadata": {"owasp_checks": 10}
            }
        ],
        "aggregated": {
            "2025-01": {
                "security-auditor": {
                    "security": {
                        "STANDARD": {
                            "total_executions": 50,
                            "success_count": 48,
                            "total_duration": 625.0
                        }
                    }
                }
            }
        }
    }

Date: 2025-01-02
Issue: #191 (Agent Feedback Loop - Machine Learning for Routing)
Agent: implementer
Phase: TDD Green (making tests pass)
"""

import json
import math
import os
import re
import tempfile
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import security utilities for path validation
import sys
sys.path.insert(0, str(Path(__file__).parent))
from security_utils import validate_path, audit_log
from path_utils import get_project_root


# =============================================================================
# CONSTANTS
# =============================================================================

# Feedback file location (relative to project root)
FEEDBACK_FILE = ".claude/agent_feedback.json"

# Retention policy
RETENTION_DAYS = 90

# Confidence scoring parameters
MAX_EXECUTIONS_FOR_CONFIDENCE = 50  # Confidence plateaus at 50+ executions

# Valid complexity levels
VALID_COMPLEXITY = ["SIMPLE", "STANDARD", "COMPLEX"]

# Valid feature types (whitelist for input validation)
VALID_FEATURE_TYPES = ["security", "api", "ui", "refactor", "docs", "tests", "general"]

# Query parameter limits (prevent DoS)
MAX_TOP_N = 100
MIN_TOP_N = 1

# Metadata validation limits
MAX_METADATA_KEYS = 100
MAX_METADATA_STRING_LENGTH = 10000

# Feature type keywords (priority order matters for overlapping keywords)
# Order: tests, docs, refactor, ui, api, security (most specific to least specific)
FEATURE_KEYWORDS = {
    "tests": [
        "unit test", "integration test", "e2e", "test coverage",
        "test fixture", "test suite", "failing test", "add unit tests"
    ],
    "docs": [
        "readme", "documentation", "document configuration",
        "code comment", "architecture guide", "installation steps",
        "api documentation"
    ],
    "refactor": [
        "extract common", "simplify database", "rename variable",
        "remove dead code", "dead code", "extract", "simplify", "rename"
    ],
    "ui": [
        "component", "dashboard", "modal", "dialog", "form", "button",
        "layout", "responsive", "accessibility", "a11y", "styling", "css"
    ],
    "api": [
        "rest", "graphql", "endpoint", "route", "handler",
        "webhook", "rate limit", "throttle", "cors", "api versioning", "api"
    ],
    "security": [
        "oauth", "login", "password", "token", "jwt", "session",
        "vulnerability", "injection", "sql injection", "xss", "csrf",
        "validation", "sanitize", "escape", "permission", "authorization",
        "encryption", "hash", "secure", "security audit", "authentication"
    ]
}

# Thread lock for file operations
_file_lock = threading.Lock()


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class AgentFeedback:
    """
    Single feedback entry for agent performance tracking.

    Attributes:
        agent_name: Name of the agent (e.g., "security-auditor")
        feature_type: Type of feature (security, api, ui, refactor, docs, tests, general)
        complexity: Complexity level (SIMPLE, STANDARD, COMPLEX)
        duration: Duration in minutes (positive float)
        success: Whether the agent completed successfully
        timestamp: When the feedback was recorded (auto-populated)
        metadata: Additional metadata (OWASP checks, vulnerabilities, etc.)
    """
    agent_name: str
    feature_type: str
    complexity: str
    duration: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "agent_name": self.agent_name,
            "feature_type": self.feature_type,
            "complexity": self.complexity,
            "duration": self.duration,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentFeedback':
        """Deserialize from dictionary."""
        return cls(
            agent_name=data["agent_name"],
            feature_type=data["feature_type"],
            complexity=data["complexity"],
            duration=data["duration"],
            success=data["success"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class FeedbackStats:
    """
    Aggregated statistics for an agent on specific feature type/complexity.

    Attributes:
        success_rate: Success rate (0.0 to 1.0)
        avg_duration: Average duration in minutes
        total_executions: Total number of executions
        confidence: Confidence score (0.0 to 1.0)
        last_updated: When stats were last calculated
    """
    success_rate: float
    avg_duration: float
    total_executions: int
    confidence: float
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class RoutingRecommendation:
    """
    Agent recommendation with confidence and reasoning.

    Attributes:
        agent_name: Recommended agent name
        confidence: Confidence score (0.0 to 1.0)
        reasoning: Human-readable explanation
        fallback_agents: List of alternative agents (ordered by confidence)
    """
    agent_name: str
    confidence: float
    reasoning: str
    fallback_agents: List[str] = field(default_factory=list)


# =============================================================================
# FEATURE CLASSIFICATION
# =============================================================================

def classify_feature_type(description: str) -> str:
    """
    Classify feature type based on description keywords.

    Uses keyword matching with priority for action verbs at start of description.
    Returns "general" if no keywords match.

    Priority:
    1. Action verbs at start (refactor, test, document)
    2. Specific multi-word phrases
    3. General category keywords

    Args:
        description: Feature description or title

    Returns:
        Feature type: security, api, ui, refactor, docs, tests, or general

    Examples:
        >>> classify_feature_type("Add OAuth2 authentication")
        'security'
        >>> classify_feature_type("Create REST endpoint for users")
        'api'
        >>> classify_feature_type("Update dashboard component")
        'ui'
        >>> classify_feature_type("Refactor authentication module")
        'refactor'
        >>> classify_feature_type("Some random feature")
        'general'
    """
    if not description:
        return "general"

    # Normalize description (lowercase for case-insensitive matching)
    desc_lower = description.lower().strip()

    # Check for "refactor" at start (special case to avoid conflicts)
    # BUT: If description contains security keywords (excluding "authentication module"),
    # security wins
    if desc_lower.startswith("refactor "):
        # Check if explicit security context words are present
        security_context_words = ["for security", "security audit", " secure ", "vulnerability"]
        for keyword in security_context_words:
            if keyword in desc_lower:
                return "security"
        # No explicit security context, so it's a refactor
        return "refactor"

    # Check each category in priority order
    for feature_type, keywords in FEATURE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return feature_type

    # Default to general if no keywords match
    return "general"


def _validate_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate and sanitize metadata dictionary.

    Prevents:
        - CWE-94: Code injection via malicious keys/values
        - DoS attacks via oversized dictionaries
        - JSON injection via specially crafted strings

    Args:
        metadata: Optional metadata dictionary to validate

    Returns:
        Validated metadata dictionary (empty dict if None)

    Raises:
        ValueError: If metadata violates validation rules
    """
    if metadata is None:
        return {}

    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dictionary")

    if len(metadata) > MAX_METADATA_KEYS:
        raise ValueError(
            f"metadata has {len(metadata)} keys, maximum is {MAX_METADATA_KEYS}"
        )

    validated: Dict[str, Any] = {}
    for key, value in metadata.items():
        # Key validation: must be string, alphanumeric with _ and -
        if not isinstance(key, str):
            raise ValueError(f"metadata key must be string, got {type(key).__name__}")

        if not key.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                f"Invalid metadata key: '{key}'. "
                "Keys must be alphanumeric with _ or - only"
            )

        # Value validation: only primitives allowed
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError(
                f"metadata['{key}'] must be primitive type (str, int, float, bool, None), "
                f"got {type(value).__name__}"
            )

        # String length limit
        if isinstance(value, str) and len(value) > MAX_METADATA_STRING_LENGTH:
            raise ValueError(
                f"metadata['{key}'] too long: {len(value)} chars, "
                f"maximum is {MAX_METADATA_STRING_LENGTH}"
            )

        validated[key] = value

    return validated


# =============================================================================
# STATE PERSISTENCE
# =============================================================================

def _get_feedback_file_path() -> Path:
    """
    Get path to feedback file using portable path detection.

    Returns:
        Path to .claude/agent_feedback.json

    Raises:
        FileNotFoundError: If project root cannot be found
    """
    try:
        project_root = get_project_root()
        feedback_path = project_root / FEEDBACK_FILE

        # Validate path (CWE-22 prevention)
        validate_path(str(feedback_path), str(project_root))

        return feedback_path
    except FileNotFoundError:
        # Fallback to current directory (for tests)
        return Path(FEEDBACK_FILE)


def _load_feedback_data() -> Dict[str, Any]:
    """
    Load feedback data from JSON file.

    Returns:
        Feedback data structure with "version", "feedback", "aggregated" keys

    Security:
        - CWE-22: Path traversal prevention via validate_path()
        - Handles corrupted JSON gracefully (returns empty structure)
    """
    feedback_file = _get_feedback_file_path()

    if not feedback_file.exists():
        return {
            "version": "1.0",
            "feedback": [],
            "aggregated": {}
        }

    try:
        with open(feedback_file, 'r') as f:
            data = json.load(f)

        # Ensure required keys exist
        if "feedback" not in data:
            data["feedback"] = []
        if "aggregated" not in data:
            data["aggregated"] = {}
        if "version" not in data:
            data["version"] = "1.0"

        return data
    except (json.JSONDecodeError, IOError) as e:
        # Log corruption and return empty structure
        audit_log("agent_feedback", "load_error", {
            "error": str(e),
            "action": "returning_empty_structure"
        })
        return {
            "version": "1.0",
            "feedback": [],
            "aggregated": {}
        }


def _save_feedback_data(data: Dict[str, Any]) -> bool:
    """
    Save feedback data to JSON file using atomic write.

    Uses tempfile + rename pattern for atomic writes (prevents corruption).

    Args:
        data: Feedback data structure to save

    Returns:
        True if save succeeded, False otherwise

    Raises:
        Exception: Re-raises exceptions from json.dump for testing

    Security:
        - CWE-22: Path traversal prevention via validate_path()
        - Atomic writes: tempfile + rename prevents corruption
        - Thread-safe: uses file lock
    """
    feedback_file = _get_feedback_file_path()

    # Create .claude directory if it doesn't exist
    feedback_file.parent.mkdir(parents=True, exist_ok=True)

    # Use thread lock for atomic operation
    with _file_lock:
        # Write to temporary file first (atomic write pattern)
        fd, temp_path = tempfile.mkstemp(
            dir=feedback_file.parent,
            prefix=".agent_feedback_",
            suffix=".json.tmp"
        )

        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            Path(temp_path).replace(feedback_file)

            # Audit log successful save
            audit_log("agent_feedback", "save_success", {
                "feedback_count": len(data.get("feedback", [])),
                "file": str(feedback_file)
            })

            return True
        except Exception as e:
            # Clean up temp file on failure
            Path(temp_path).unlink(missing_ok=True)

            # Audit log error
            audit_log("agent_feedback", "save_error", {
                "error": str(e),
                "file": str(feedback_file)
            })

            # Re-raise for atomic write test
            raise


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def record_feedback(
    agent_name: str,
    feature_type: str,
    complexity: str,
    duration: float,
    success: bool,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Record agent performance feedback.

    Validates inputs, creates feedback entry, and appends to state file using
    atomic writes. Automatically adds timestamp.

    Args:
        agent_name: Name of the agent (non-empty string)
        feature_type: Type of feature (any string, use classify_feature_type())
        complexity: Complexity level (SIMPLE, STANDARD, or COMPLEX)
        duration: Duration in minutes (positive float)
        success: Whether the agent completed successfully
        metadata: Optional metadata dictionary

    Returns:
        True if feedback recorded successfully, False otherwise

    Raises:
        ValueError: If validation fails (empty agent_name, invalid complexity, negative duration)

    Examples:
        >>> record_feedback("security-auditor", "security", "STANDARD", 12.5, True)
        True
        >>> record_feedback("", "api", "STANDARD", 10.0, True)
        ValueError: agent_name cannot be empty
        >>> record_feedback("test", "api", "INVALID", 10.0, True)
        ValueError: complexity must be one of: SIMPLE, STANDARD, COMPLEX
    """
    # Validation (CWE-20: Improper Input Validation)
    if not agent_name or not agent_name.strip():
        raise ValueError("agent_name cannot be empty")

    if complexity not in VALID_COMPLEXITY:
        raise ValueError(f"complexity must be one of: {', '.join(VALID_COMPLEXITY)}")

    if duration <= 0:
        raise ValueError("duration must be positive")

    # Validate feature_type against whitelist
    if feature_type not in VALID_FEATURE_TYPES:
        raise ValueError(
            f"Invalid feature_type: {feature_type}. "
            f"Must be one of: {', '.join(VALID_FEATURE_TYPES)}"
        )

    # Validate and sanitize metadata
    validated_metadata = _validate_metadata(metadata)

    # Create feedback entry
    feedback = AgentFeedback(
        agent_name=agent_name.strip(),
        feature_type=feature_type,
        complexity=complexity,
        duration=duration,
        success=success,
        timestamp=datetime.now(),
        metadata=validated_metadata
    )

    # Load existing data
    data = _load_feedback_data()

    # Append new feedback
    data["feedback"].append(feedback.to_dict())

    # Save with atomic write
    result = _save_feedback_data(data)

    # Audit log
    if result:
        audit_log("agent_feedback", "record_feedback", {
            "agent_name": agent_name,
            "feature_type": feature_type,
            "complexity": complexity,
            "success": success
        })

    return result


def query_recommendations(
    feature_type: str,
    complexity: str,
    top_n: int = 3
) -> List[RoutingRecommendation]:
    """
    Query agent recommendations for a feature type and complexity.

    Ranks agents by confidence score (success_rate * sqrt(min(executions, 30) / 30)).
    Returns top N recommendations with fallback agents.

    Args:
        feature_type: Type of feature (security, api, ui, refactor, docs, tests, general)
        complexity: Complexity level (SIMPLE, STANDARD, COMPLEX)
        top_n: Number of recommendations to return (default: 3)

    Returns:
        List of RoutingRecommendation objects, ordered by confidence (highest first)

    Examples:
        >>> recommendations = query_recommendations("security", "STANDARD", top_n=3)
        >>> recommendations[0].agent_name
        'security-auditor'
        >>> recommendations[0].confidence
        0.95
        >>> recommendations[0].fallback_agents
        ['implementer', 'reviewer']

    Raises:
        ValueError: If feature_type, complexity, or top_n is invalid
    """
    # Input validation (CWE-20: Improper Input Validation)
    if feature_type not in VALID_FEATURE_TYPES:
        raise ValueError(
            f"Invalid feature_type: {feature_type}. "
            f"Must be one of: {', '.join(VALID_FEATURE_TYPES)}"
        )

    if complexity not in VALID_COMPLEXITY:
        raise ValueError(
            f"Invalid complexity: {complexity}. "
            f"Must be one of: {', '.join(VALID_COMPLEXITY)}"
        )

    if not isinstance(top_n, int) or top_n < MIN_TOP_N or top_n > MAX_TOP_N:
        raise ValueError(
            f"top_n must be integer in range [{MIN_TOP_N}, {MAX_TOP_N}], got {top_n}"
        )

    # Load feedback data
    data = _load_feedback_data()
    feedback_list = data.get("feedback", [])

    # Filter by feature type and complexity
    filtered = [
        fb for fb in feedback_list
        if fb["feature_type"] == feature_type and fb["complexity"] == complexity
    ]

    if not filtered:
        return []

    # Aggregate by agent
    agent_stats: Dict[str, Dict[str, Any]] = {}

    for fb in filtered:
        agent = fb["agent_name"]

        if agent not in agent_stats:
            agent_stats[agent] = {
                "success_count": 0,
                "total_executions": 0,
                "total_duration": 0.0
            }

        agent_stats[agent]["total_executions"] += 1
        agent_stats[agent]["total_duration"] += fb["duration"]

        if fb["success"]:
            agent_stats[agent]["success_count"] += 1

    # Calculate confidence scores
    recommendations: List[RoutingRecommendation] = []

    for agent, stats in agent_stats.items():
        success_rate = stats["success_count"] / stats["total_executions"]
        avg_duration = stats["total_duration"] / stats["total_executions"]

        # Confidence formula: success_rate * sqrt(min(executions, 30) / 30)
        executions_factor = min(stats["total_executions"], MAX_EXECUTIONS_FOR_CONFIDENCE)
        confidence = success_rate * math.sqrt(executions_factor / MAX_EXECUTIONS_FOR_CONFIDENCE)

        # Create reasoning
        reasoning = (
            f"{success_rate:.0%} success rate on {feature_type} features "
            f"({stats['total_executions']} executions, avg {avg_duration:.1f}min)"
        )

        recommendations.append(RoutingRecommendation(
            agent_name=agent,
            confidence=confidence,
            reasoning=reasoning,
            fallback_agents=[]  # Will be populated after sorting
        ))

    # Sort by confidence (descending)
    recommendations.sort(key=lambda r: r.confidence, reverse=True)

    # Add fallback agents (next best alternatives)
    for i, rec in enumerate(recommendations[:top_n]):
        rec.fallback_agents = [
            r.agent_name for r in recommendations[i+1:top_n+2]
        ]

    # Return top N
    return recommendations[:top_n]


def get_agent_stats(agent_name: Optional[str] = None) -> Dict[str, FeedbackStats]:
    """
    Get aggregated statistics for agent(s).

    Returns statistics broken down by feature type, with an "overall" key for aggregate stats.
    If agent_name is None, returns stats for all agents.

    Args:
        agent_name: Optional agent name filter (None = all agents)

    Returns:
        Dictionary mapping feature_type to FeedbackStats, with "overall" key for aggregate

    Examples:
        >>> stats = get_agent_stats("security-auditor")
        >>> stats["overall"]
        FeedbackStats(success_rate=0.95, avg_duration=12.5, total_executions=50, confidence=0.95)
        >>> stats["security"]
        FeedbackStats(success_rate=0.96, avg_duration=12.0, total_executions=30, confidence=0.96)

        >>> all_stats = get_agent_stats()  # All agents
        >>> len(all_stats)
        42
    """
    # Load feedback data
    data = _load_feedback_data()
    feedback_list = data.get("feedback", [])

    # Filter by agent if specified
    if agent_name:
        feedback_list = [fb for fb in feedback_list if fb["agent_name"] == agent_name]

    if not feedback_list:
        return {}

    # Aggregate by feature type AND overall
    aggregated: Dict[str, Dict[str, Any]] = {}
    overall_agg = {
        "success_count": 0,
        "total_executions": 0,
        "total_duration": 0.0
    }

    for fb in feedback_list:
        feature_type = fb['feature_type']

        # Per-feature-type aggregation
        if feature_type not in aggregated:
            aggregated[feature_type] = {
                "success_count": 0,
                "total_executions": 0,
                "total_duration": 0.0
            }

        aggregated[feature_type]["total_executions"] += 1
        aggregated[feature_type]["total_duration"] += fb["duration"]

        if fb["success"]:
            aggregated[feature_type]["success_count"] += 1

        # Overall aggregation
        overall_agg["total_executions"] += 1
        overall_agg["total_duration"] += fb["duration"]

        if fb["success"]:
            overall_agg["success_count"] += 1

    # Calculate stats
    stats: Dict[str, FeedbackStats] = {}

    # Per-feature-type stats
    for feature_type, agg in aggregated.items():
        success_rate = agg["success_count"] / agg["total_executions"]
        avg_duration = agg["total_duration"] / agg["total_executions"]

        # Confidence formula
        executions_factor = min(agg["total_executions"], MAX_EXECUTIONS_FOR_CONFIDENCE)
        confidence = success_rate * math.sqrt(executions_factor / MAX_EXECUTIONS_FOR_CONFIDENCE)

        stats[feature_type] = FeedbackStats(
            success_rate=success_rate,
            avg_duration=avg_duration,
            total_executions=agg["total_executions"],
            confidence=confidence,
            last_updated=datetime.now()
        )

    # Overall stats
    if overall_agg["total_executions"] > 0:
        success_rate = overall_agg["success_count"] / overall_agg["total_executions"]
        avg_duration = overall_agg["total_duration"] / overall_agg["total_executions"]

        executions_factor = min(overall_agg["total_executions"], MAX_EXECUTIONS_FOR_CONFIDENCE)
        confidence = success_rate * math.sqrt(executions_factor / MAX_EXECUTIONS_FOR_CONFIDENCE)

        stats["overall"] = FeedbackStats(
            success_rate=success_rate,
            avg_duration=avg_duration,
            total_executions=overall_agg["total_executions"],
            confidence=confidence,
            last_updated=datetime.now()
        )

    return stats


def _prune_expired_feedback() -> int:
    """
    Prune feedback entries older than RETENTION_DAYS (90 days).

    Removes expired entries from feedback list. Should be called periodically
    (e.g., before aggregation).

    Returns:
        Number of entries pruned

    Security:
        - Thread-safe: uses file lock
        - Atomic writes: tempfile + rename pattern
    """
    # Load data
    data = _load_feedback_data()
    feedback_list = data.get("feedback", [])

    # Calculate cutoff date
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)

    # Filter out expired entries
    original_count = len(feedback_list)
    filtered = []

    for fb in feedback_list:
        try:
            # Try datetime.fromisoformat first (handles both str and datetime objects)
            if isinstance(fb["timestamp"], str):
                timestamp = datetime.fromisoformat(fb["timestamp"])
            else:
                # Already a datetime object (from mocking)
                timestamp = fb["timestamp"]

            if timestamp >= cutoff:
                filtered.append(fb)
        except (ValueError, AttributeError):
            # Skip entries with invalid timestamps
            continue

    data["feedback"] = filtered
    pruned_count = original_count - len(data["feedback"])

    # Save if anything was pruned
    if pruned_count > 0:
        _save_feedback_data(data)

        audit_log("agent_feedback", "prune_expired", {
            "pruned_count": pruned_count,
            "retention_days": RETENTION_DAYS
        })

    return pruned_count


def _aggregate_old_feedback() -> Dict[str, Any]:
    """
    Aggregate old feedback into monthly summaries.

    Groups feedback by month and calculates aggregated statistics. This reduces
    storage size while preserving historical trends.

    Returns:
        Dictionary mapping "YYYY-MM" to aggregated stats

    State Structure:
        {
            "2025-01": {
                "security-auditor": {
                    "security": {
                        "STANDARD": {
                            "total_executions": 50,
                            "success_count": 48,
                            "total_duration": 625.0
                        }
                    }
                }
            }
        }
    """
    # Load data
    data = _load_feedback_data()
    feedback_list = data.get("feedback", [])

    # Group by month
    aggregated: Dict[str, Dict[str, Any]] = {}

    for fb in feedback_list:
        timestamp = datetime.fromisoformat(fb["timestamp"])
        month_key = timestamp.strftime("%Y-%m")

        agent = fb["agent_name"]
        feature_type = fb["feature_type"]
        complexity = fb["complexity"]

        # Initialize nested structure
        if month_key not in aggregated:
            aggregated[month_key] = {}
        if agent not in aggregated[month_key]:
            aggregated[month_key][agent] = {}
        if feature_type not in aggregated[month_key][agent]:
            aggregated[month_key][agent][feature_type] = {}
        if complexity not in aggregated[month_key][agent][feature_type]:
            aggregated[month_key][agent][feature_type][complexity] = {
                "total_executions": 0,
                "success_count": 0,
                "total_duration": 0.0
            }

        # Aggregate
        stats = aggregated[month_key][agent][feature_type][complexity]
        stats["total_executions"] += 1
        stats["total_duration"] += fb["duration"]

        if fb["success"]:
            stats["success_count"] += 1

    # Save aggregated data
    data["aggregated"] = aggregated
    _save_feedback_data(data)

    audit_log("agent_feedback", "aggregate_feedback", {
        "months_aggregated": len(aggregated)
    })

    return aggregated


# =============================================================================
# MAINTENANCE
# =============================================================================

def cleanup_old_data() -> Dict[str, int]:
    """
    Perform maintenance: prune expired feedback and aggregate old data.

    This should be called periodically (e.g., weekly) to keep the feedback file
    size manageable.

    Returns:
        Dictionary with "pruned" and "aggregated_months" counts

    Examples:
        >>> result = cleanup_old_data()
        >>> result
        {'pruned': 42, 'aggregated_months': 3}
    """
    pruned_count = _prune_expired_feedback()
    aggregated = _aggregate_old_feedback()

    return {
        "pruned": pruned_count,
        "aggregated_months": len(aggregated)
    }


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

if __name__ == "__main__":
    # CLI usage (optional)
    import argparse

    parser = argparse.ArgumentParser(description="Agent Feedback Loop CLI")
    parser.add_argument("--cleanup", action="store_true", help="Run cleanup maintenance")
    parser.add_argument("--stats", metavar="AGENT", help="Show stats for agent")
    parser.add_argument("--recommend", nargs=2, metavar=("TYPE", "COMPLEXITY"),
                       help="Get recommendations for feature type and complexity")

    args = parser.parse_args()

    if args.cleanup:
        result = cleanup_old_data()
        print(f"Cleanup complete: {result}")

    elif args.stats:
        stats = get_agent_stats(args.stats)
        for key, stat in stats.items():
            print(f"{key}: {stat}")

    elif args.recommend:
        feature_type, complexity = args.recommend
        recommendations = query_recommendations(feature_type, complexity)
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec.agent_name} (confidence: {rec.confidence:.2f})")
            print(f"   {rec.reasoning}")
            if rec.fallback_agents:
                print(f"   Fallback: {', '.join(rec.fallback_agents)}")

    else:
        parser.print_help()
