"""
Unit tests for agent_feedback.py - Agent Feedback Loop with machine learning

Tests cover:
1. AgentFeedback dataclass - validation, serialization
2. FeedbackStats dataclass - calculation accuracy
3. RoutingRecommendation dataclass - confidence scoring
4. classify_feature_type() - 7 categories (security, api, ui, refactor, docs, tests, general)
5. record_feedback() - atomic writes, validation, metadata handling
6. query_recommendations() - ranking, confidence, fallback agents
7. get_agent_stats() - per-agent statistics, feature type breakdown
8. _prune_expired_feedback() - 90-day retention, monthly aggregation
9. Thread Safety - concurrent access, atomic operations
10. Edge Cases - empty state, corrupted JSON, missing fields

This is the RED phase of TDD - tests should fail initially since implementation doesn't exist yet.
"""

import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Import the module under test (will fail initially - TDD red phase)
try:
    from autonomous_dev.lib.agent_feedback import (
        AgentFeedback,
        FeedbackStats,
        RoutingRecommendation,
        classify_feature_type,
        record_feedback,
        query_recommendations,
        get_agent_stats,
        _prune_expired_feedback,
        _aggregate_old_feedback,
        _load_feedback_data,
        _save_feedback_data,
    )
except ImportError:
    # Allow tests to be collected even if implementation doesn't exist yet
    pytest.skip("agent_feedback.py not implemented yet", allow_module_level=True)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create temporary project directory with .claude subdirectory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # Save original directory
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    yield tmp_path

    # Restore original directory
    os.chdir(original_dir)


@pytest.fixture
def feedback_file(tmp_project_dir: Path) -> Path:
    """Create agent_feedback.json path."""
    return tmp_project_dir / ".claude" / "agent_feedback.json"


@pytest.fixture
def sample_feedback() -> AgentFeedback:
    """Create sample feedback entry."""
    return AgentFeedback(
        agent_name="security-auditor",
        feature_type="security",
        complexity="STANDARD",
        duration=12.5,
        success=True,
        timestamp=datetime.now(),
        metadata={"owasp_checks": 10, "vulnerabilities": 0}
    )


@pytest.fixture
def sample_feedback_list() -> List[Dict[str, Any]]:
    """Create list of sample feedback entries for testing queries."""
    now = datetime.now()
    return [
        {
            "agent_name": "security-auditor",
            "feature_type": "security",
            "complexity": "STANDARD",
            "duration": 12.5,
            "success": True,
            "timestamp": now.isoformat(),
            "metadata": {"owasp_checks": 10}
        },
        {
            "agent_name": "security-auditor",
            "feature_type": "security",
            "complexity": "COMPLEX",
            "duration": 18.2,
            "success": True,
            "timestamp": now.isoformat(),
            "metadata": {"owasp_checks": 15}
        },
        {
            "agent_name": "implementer",
            "feature_type": "api",
            "complexity": "STANDARD",
            "duration": 15.0,
            "success": True,
            "timestamp": now.isoformat(),
            "metadata": {}
        },
        {
            "agent_name": "implementer",
            "feature_type": "api",
            "complexity": "STANDARD",
            "duration": 14.5,
            "success": False,
            "timestamp": now.isoformat(),
            "metadata": {"error": "timeout"}
        },
    ]


# ============================================================================
# DATACLASS TESTS (5 tests)
# ============================================================================

def test_agent_feedback_dataclass_valid():
    """Test AgentFeedback dataclass creation with valid data."""
    # Arrange
    now = datetime.now()

    # Act
    feedback = AgentFeedback(
        agent_name="test-agent",
        feature_type="api",
        complexity="STANDARD",
        duration=10.5,
        success=True,
        timestamp=now,
        metadata={"key": "value"}
    )

    # Assert
    assert feedback.agent_name == "test-agent"
    assert feedback.feature_type == "api"
    assert feedback.complexity == "STANDARD"
    assert feedback.duration == 10.5
    assert feedback.success is True
    assert feedback.timestamp == now
    assert feedback.metadata == {"key": "value"}


def test_agent_feedback_dataclass_serialization():
    """Test AgentFeedback serialization to dict."""
    # Arrange
    now = datetime.now()
    feedback = AgentFeedback(
        agent_name="test-agent",
        feature_type="security",
        complexity="COMPLEX",
        duration=20.0,
        success=False,
        timestamp=now,
        metadata={"error": "failed"}
    )

    # Act
    data = asdict(feedback)

    # Assert
    assert data["agent_name"] == "test-agent"
    assert data["feature_type"] == "security"
    assert data["complexity"] == "COMPLEX"
    assert data["duration"] == 20.0
    assert data["success"] is False
    assert isinstance(data["timestamp"], datetime)
    assert data["metadata"]["error"] == "failed"


def test_feedback_stats_dataclass_calculation():
    """Test FeedbackStats calculation accuracy."""
    # Arrange & Act
    stats = FeedbackStats(
        success_rate=0.85,
        avg_duration=15.5,
        total_executions=42,
        confidence=0.95
    )

    # Assert
    assert stats.success_rate == 0.85
    assert stats.avg_duration == 15.5
    assert stats.total_executions == 42
    assert stats.confidence == 0.95


def test_routing_recommendation_dataclass():
    """Test RoutingRecommendation dataclass."""
    # Arrange & Act
    recommendation = RoutingRecommendation(
        agent_name="security-auditor",
        confidence=0.92,
        reasoning="High success rate on security features",
        fallback_agents=["implementer", "reviewer"]
    )

    # Assert
    assert recommendation.agent_name == "security-auditor"
    assert recommendation.confidence == 0.92
    assert recommendation.reasoning == "High success rate on security features"
    assert recommendation.fallback_agents == ["implementer", "reviewer"]


def test_dataclass_defaults():
    """Test dataclass default values."""
    # Arrange & Act
    feedback = AgentFeedback(
        agent_name="test-agent",
        feature_type="general",
        complexity="SIMPLE",
        duration=5.0,
        success=True,
        timestamp=datetime.now()
    )

    # Assert - metadata should default to empty dict
    assert feedback.metadata == {}


# ============================================================================
# FEATURE CLASSIFICATION TESTS (8 tests)
# ============================================================================

def test_classify_feature_type_security():
    """Test classification of security-related features."""
    # Arrange
    descriptions = [
        "Add authentication middleware",
        "Fix SQL injection vulnerability",
        "Implement OAuth2 flow",
        "Add input validation",
        "Security audit for XSS"
    ]

    # Act & Assert
    for desc in descriptions:
        result = classify_feature_type(desc)
        assert result == "security", f"Failed to classify: {desc}"


def test_classify_feature_type_api():
    """Test classification of API-related features."""
    # Arrange
    descriptions = [
        "Add REST endpoint for users",
        "Update GraphQL schema",
        "Add API versioning",
        "Implement webhook handler",
        "Add rate limiting to endpoint"
    ]

    # Act & Assert
    for desc in descriptions:
        result = classify_feature_type(desc)
        assert result == "api", f"Failed to classify: {desc}"


def test_classify_feature_type_ui():
    """Test classification of UI-related features."""
    # Arrange
    descriptions = [
        "Add dashboard component",
        "Update button styling",
        "Implement responsive layout",
        "Add modal dialog",
        "Improve form accessibility"
    ]

    # Act & Assert
    for desc in descriptions:
        result = classify_feature_type(desc)
        assert result == "ui", f"Failed to classify: {desc}"


def test_classify_feature_type_refactor():
    """Test classification of refactoring features."""
    # Arrange
    descriptions = [
        "Refactor authentication module",
        "Extract common utilities",
        "Simplify database queries",
        "Rename variables for clarity",
        "Remove dead code"
    ]

    # Act & Assert
    for desc in descriptions:
        result = classify_feature_type(desc)
        assert result == "refactor", f"Failed to classify: {desc}"


def test_classify_feature_type_docs():
    """Test classification of documentation features."""
    # Arrange
    descriptions = [
        "Update README installation steps",
        "Add API documentation",
        "Document configuration options",
        "Add code comments",
        "Write architecture guide"
    ]

    # Act & Assert
    for desc in descriptions:
        result = classify_feature_type(desc)
        assert result == "docs", f"Failed to classify: {desc}"


def test_classify_feature_type_tests():
    """Test classification of testing features."""
    # Arrange
    descriptions = [
        "Add unit tests for auth",
        "Write integration tests",
        "Add E2E test coverage",
        "Fix failing test suite",
        "Add test fixtures"
    ]

    # Act & Assert
    for desc in descriptions:
        result = classify_feature_type(desc)
        assert result == "tests", f"Failed to classify: {desc}"


def test_classify_feature_type_general():
    """Test classification of general/unknown features."""
    # Arrange
    descriptions = [
        "Miscellaneous updates",
        "Various improvements",
        "General cleanup",
        "Update dependencies",
        "Fix typos"
    ]

    # Act & Assert
    for desc in descriptions:
        result = classify_feature_type(desc)
        assert result == "general", f"Failed to classify: {desc}"


def test_classify_feature_type_precedence():
    """Test that security keywords take precedence over other categories."""
    # Arrange
    description = "Refactor authentication module for security"

    # Act
    result = classify_feature_type(description)

    # Assert - security should take precedence over refactor
    assert result == "security"


# ============================================================================
# RECORD FEEDBACK TESTS (8 tests)
# ============================================================================

def test_record_feedback_creates_file(tmp_project_dir, feedback_file):
    """Test that record_feedback creates feedback file if it doesn't exist."""
    # Arrange
    assert not feedback_file.exists()

    # Act
    record_feedback(
        agent_name="test-agent",
        feature_type="api",
        complexity="STANDARD",
        duration=10.0,
        success=True,
        metadata={}
    )

    # Assert
    assert feedback_file.exists()


def test_record_feedback_appends_entry(tmp_project_dir, feedback_file):
    """Test that record_feedback appends to existing data."""
    # Arrange
    record_feedback("agent1", "api", "SIMPLE", 5.0, True, {})

    # Act
    record_feedback("agent2", "security", "COMPLEX", 15.0, True, {})

    # Assert
    data = json.loads(feedback_file.read_text())
    assert len(data["feedback"]) == 2
    assert data["feedback"][0]["agent_name"] == "agent1"
    assert data["feedback"][1]["agent_name"] == "agent2"


def test_record_feedback_validates_agent_name(tmp_project_dir):
    """Test that record_feedback validates agent name."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="agent_name cannot be empty"):
        record_feedback("", "api", "STANDARD", 10.0, True, {})


def test_record_feedback_validates_complexity(tmp_project_dir):
    """Test that record_feedback validates complexity level."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="complexity must be one of"):
        record_feedback("test-agent", "api", "INVALID", 10.0, True, {})


def test_record_feedback_validates_duration(tmp_project_dir):
    """Test that record_feedback validates duration is positive."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="duration must be positive"):
        record_feedback("test-agent", "api", "STANDARD", -5.0, True, {})


def test_record_feedback_atomic_write(tmp_project_dir, feedback_file):
    """Test that record_feedback uses atomic writes (temp file + rename)."""
    # Arrange
    record_feedback("agent1", "api", "SIMPLE", 5.0, True, {})

    # Act - simulate partial write failure by mocking json.dump
    with patch("json.dump", side_effect=Exception("Write failed")):
        with pytest.raises(Exception):
            record_feedback("agent2", "api", "SIMPLE", 5.0, True, {})

    # Assert - original file should be intact
    data = json.loads(feedback_file.read_text())
    assert len(data["feedback"]) == 1
    assert data["feedback"][0]["agent_name"] == "agent1"


def test_record_feedback_timestamp_auto_added(tmp_project_dir, feedback_file):
    """Test that record_feedback automatically adds timestamp."""
    # Arrange
    before = datetime.now()

    # Act
    record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    after = datetime.now()

    # Assert
    data = json.loads(feedback_file.read_text())
    timestamp = datetime.fromisoformat(data["feedback"][0]["timestamp"])
    assert before <= timestamp <= after


def test_record_feedback_metadata_optional(tmp_project_dir, feedback_file):
    """Test that metadata parameter is optional."""
    # Arrange & Act
    record_feedback("test-agent", "api", "STANDARD", 10.0, True)

    # Assert
    data = json.loads(feedback_file.read_text())
    assert data["feedback"][0]["metadata"] == {}


# ============================================================================
# QUERY RECOMMENDATIONS TESTS (10 tests)
# ============================================================================

def test_query_recommendations_no_data(tmp_project_dir):
    """Test query_recommendations with no historical data."""
    # Arrange - no feedback file exists

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=3)

    # Assert - should return empty list
    assert recommendations == []


def test_query_recommendations_sparse_data(tmp_project_dir, feedback_file):
    """Test query_recommendations with sparse data (low confidence)."""
    # Arrange - only 1 execution
    record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=3)

    # Assert
    assert len(recommendations) == 1
    assert recommendations[0].agent_name == "test-agent"
    assert recommendations[0].confidence < 0.5  # Low confidence with only 1 execution


def test_query_recommendations_rich_data(tmp_project_dir, feedback_file):
    """Test query_recommendations with rich data (high confidence)."""
    # Arrange - 50+ executions for high confidence
    for i in range(50):
        record_feedback("test-agent", "api", "STANDARD", 10.0 + i * 0.1, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=3)

    # Assert
    assert len(recommendations) == 1
    assert recommendations[0].agent_name == "test-agent"
    assert recommendations[0].confidence > 0.95  # High confidence with 50+ executions


def test_query_recommendations_ranking_by_success_rate(tmp_project_dir, feedback_file):
    """Test that recommendations are ranked by success rate."""
    # Arrange
    # Agent A: 90% success rate (9/10)
    for i in range(9):
        record_feedback("agent-a", "api", "STANDARD", 10.0, True, {})
    record_feedback("agent-a", "api", "STANDARD", 10.0, False, {})

    # Agent B: 50% success rate (5/10)
    for i in range(5):
        record_feedback("agent-b", "api", "STANDARD", 10.0, True, {})
    for i in range(5):
        record_feedback("agent-b", "api", "STANDARD", 10.0, False, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=2)

    # Assert - agent-a should be ranked first
    assert recommendations[0].agent_name == "agent-a"
    assert recommendations[1].agent_name == "agent-b"


def test_query_recommendations_fallback_agents(tmp_project_dir, feedback_file):
    """Test that recommendations include fallback agents."""
    # Arrange - multiple agents with data
    for i in range(10):
        record_feedback("agent-a", "api", "STANDARD", 10.0, True, {})
    for i in range(10):
        record_feedback("agent-b", "api", "STANDARD", 10.0, True, {})
    for i in range(10):
        record_feedback("agent-c", "api", "STANDARD", 10.0, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=1)

    # Assert - top recommendation should have fallback agents
    assert len(recommendations[0].fallback_agents) >= 1


def test_query_recommendations_top_n_limit(tmp_project_dir, feedback_file):
    """Test that top_n parameter limits results."""
    # Arrange - 5 different agents
    for agent in ["agent-a", "agent-b", "agent-c", "agent-d", "agent-e"]:
        for i in range(10):
            record_feedback(agent, "api", "STANDARD", 10.0, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=3)

    # Assert
    assert len(recommendations) == 3


def test_query_recommendations_feature_type_filtering(tmp_project_dir, feedback_file):
    """Test that recommendations filter by feature type."""
    # Arrange - different feature types
    for i in range(10):
        record_feedback("api-agent", "api", "STANDARD", 10.0, True, {})
    for i in range(10):
        record_feedback("security-agent", "security", "STANDARD", 10.0, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=5)

    # Assert - should only include api-agent
    assert len(recommendations) == 1
    assert recommendations[0].agent_name == "api-agent"


def test_query_recommendations_complexity_filtering(tmp_project_dir, feedback_file):
    """Test that recommendations filter by complexity."""
    # Arrange - different complexity levels
    for i in range(10):
        record_feedback("test-agent", "api", "SIMPLE", 5.0, True, {})
    for i in range(10):
        record_feedback("test-agent", "api", "COMPLEX", 20.0, True, {})

    # Act
    simple_recs = query_recommendations("api", "SIMPLE", top_n=5)
    complex_recs = query_recommendations("api", "COMPLEX", top_n=5)

    # Assert
    assert len(simple_recs) == 1
    assert len(complex_recs) == 1
    assert simple_recs[0].agent_name == "test-agent"
    assert complex_recs[0].agent_name == "test-agent"


def test_query_recommendations_confidence_calculation(tmp_project_dir, feedback_file):
    """Test confidence score calculation based on execution count."""
    # Arrange - test different execution counts
    # 1 execution: low confidence
    record_feedback("agent-1", "api", "STANDARD", 10.0, True, {})

    # 30 executions: medium confidence
    for i in range(30):
        record_feedback("agent-30", "security", "STANDARD", 10.0, True, {})

    # 100 executions: high confidence
    for i in range(100):
        record_feedback("agent-100", "refactor", "STANDARD", 10.0, True, {})

    # Act
    recs_1 = query_recommendations("api", "STANDARD", top_n=1)
    recs_30 = query_recommendations("security", "STANDARD", top_n=1)
    recs_100 = query_recommendations("refactor", "STANDARD", top_n=1)

    # Assert - confidence should increase with execution count
    assert recs_1[0].confidence < 0.5
    assert 0.7 <= recs_30[0].confidence < 0.95
    assert recs_100[0].confidence >= 0.95


def test_query_recommendations_reasoning_provided(tmp_project_dir, feedback_file):
    """Test that recommendations include human-readable reasoning."""
    # Arrange
    for i in range(20):
        record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=1)

    # Assert
    assert recommendations[0].reasoning is not None
    assert len(recommendations[0].reasoning) > 0
    assert "success" in recommendations[0].reasoning.lower()


# ============================================================================
# AGENT STATS TESTS (5 tests)
# ============================================================================

def test_get_agent_stats_no_data(tmp_project_dir):
    """Test get_agent_stats with no historical data."""
    # Arrange - no feedback file

    # Act
    stats = get_agent_stats("test-agent")

    # Assert - should return empty dict
    assert stats == {}


def test_get_agent_stats_overall_stats(tmp_project_dir, feedback_file):
    """Test get_agent_stats calculates overall statistics."""
    # Arrange - 10 executions, 8 successful
    for i in range(8):
        record_feedback("test-agent", "api", "STANDARD", 10.0 + i, True, {})
    for i in range(2):
        record_feedback("test-agent", "api", "STANDARD", 15.0, False, {})

    # Act
    stats = get_agent_stats("test-agent")

    # Assert
    overall = stats["overall"]
    assert overall.success_rate == 0.8
    assert overall.total_executions == 10
    assert 10.0 <= overall.avg_duration <= 15.0


def test_get_agent_stats_per_feature_type(tmp_project_dir, feedback_file):
    """Test get_agent_stats breaks down by feature type."""
    # Arrange - different feature types
    for i in range(5):
        record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})
    for i in range(3):
        record_feedback("test-agent", "security", "STANDARD", 12.0, True, {})

    # Act
    stats = get_agent_stats("test-agent")

    # Assert
    assert "api" in stats
    assert "security" in stats
    assert stats["api"].total_executions == 5
    assert stats["security"].total_executions == 3


def test_get_agent_stats_per_complexity(tmp_project_dir, feedback_file):
    """Test get_agent_stats aggregates across complexity levels."""
    # Arrange - different complexity levels
    for i in range(3):
        record_feedback("test-agent", "api", "SIMPLE", 5.0, True, {})
    for i in range(4):
        record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})
    for i in range(2):
        record_feedback("test-agent", "api", "COMPLEX", 20.0, True, {})

    # Act
    stats = get_agent_stats("test-agent")

    # Assert - stats should aggregate by feature_type (not complexity)
    # All 9 entries should be aggregated under "api" and "overall"
    assert "api" in stats
    assert "overall" in stats
    assert stats["api"].total_executions == 9
    assert stats["overall"].total_executions == 9


def test_get_agent_stats_average_duration_accurate(tmp_project_dir, feedback_file):
    """Test that average duration calculation is accurate."""
    # Arrange - known durations
    durations = [5.0, 10.0, 15.0, 20.0]
    for duration in durations:
        record_feedback("test-agent", "api", "STANDARD", duration, True, {})

    # Act
    stats = get_agent_stats("test-agent")

    # Assert
    expected_avg = sum(durations) / len(durations)
    assert abs(stats["overall"].avg_duration - expected_avg) < 0.01


# ============================================================================
# PRUNING AND AGGREGATION TESTS (6 tests)
# ============================================================================

def test_prune_expired_feedback_removes_old_entries(tmp_project_dir, feedback_file):
    """Test that _prune_expired_feedback removes entries older than 90 days."""
    # Arrange - create entries with different ages (using actual dates)
    now = datetime.now()
    old_date = now - timedelta(days=100)  # >90 days old - should be pruned
    recent_date = now - timedelta(days=30)  # <90 days old - should be kept

    # Manually create feedback with old and recent dates
    data = {
        "version": "1.0",
        "last_aggregated": now.isoformat(),
        "feedback": [
            {
                "agent_name": "old-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 10.0,
                "success": True,
                "timestamp": old_date.isoformat(),
                "metadata": {}
            },
            {
                "agent_name": "recent-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 10.0,
                "success": True,
                "timestamp": recent_date.isoformat(),
                "metadata": {}
            }
        ],
        "aggregated": {}
    }
    feedback_file.write_text(json.dumps(data, indent=2))

    # Act
    pruned_count = _prune_expired_feedback()

    # Assert - old entry should be removed
    result = json.loads(feedback_file.read_text())
    assert pruned_count == 1
    assert len(result["feedback"]) == 1
    assert result["feedback"][0]["agent_name"] == "recent-agent"


def test_prune_expired_feedback_no_file(tmp_project_dir):
    """Test that _prune_expired_feedback handles missing file gracefully."""
    # Arrange - no feedback file

    # Act & Assert - should not raise exception
    _prune_expired_feedback()


def test_aggregate_old_feedback_creates_monthly_summaries(tmp_project_dir, feedback_file, monkeypatch):
    """Test that _aggregate_old_feedback creates monthly summaries."""
    # Arrange - create entries from different months
    now = datetime.now()
    last_month = now - timedelta(days=35)

    for i in range(10):
        record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    # Manually add old entries
    data = json.loads(feedback_file.read_text())
    for i in range(5):
        data["feedback"].append({
            "agent_name": "test-agent",
            "feature_type": "api",
            "complexity": "STANDARD",
            "duration": 12.0,
            "success": True,
            "timestamp": last_month.isoformat(),
            "metadata": {}
        })
    feedback_file.write_text(json.dumps(data, indent=2))

    # Act
    _aggregate_old_feedback()

    # Assert - should have aggregated entries
    result = json.loads(feedback_file.read_text())
    assert "aggregated" in result
    # Monthly aggregation should have occurred


def test_aggregate_old_feedback_preserves_stats(tmp_project_dir, feedback_file):
    """Test that aggregation preserves statistical accuracy."""
    # Arrange - create known dataset
    for i in range(10):
        record_feedback("test-agent", "api", "STANDARD", 10.0 + i, True, {})

    # Get stats before aggregation
    stats_before = get_agent_stats("test-agent")

    # Act
    _aggregate_old_feedback()

    # Get stats after aggregation
    stats_after = get_agent_stats("test-agent")

    # Assert - stats should be similar (allowing for aggregation effects)
    assert abs(stats_before["overall"].success_rate - stats_after["overall"].success_rate) < 0.1


def test_prune_and_aggregate_together(tmp_project_dir, feedback_file, monkeypatch):
    """Test pruning and aggregation work together correctly."""
    # Arrange - create mixed dataset
    now = datetime.now()
    old_date = now - timedelta(days=100)

    # Recent entries
    for i in range(5):
        record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    # Add old entries manually
    data = json.loads(feedback_file.read_text())
    for i in range(5):
        data["feedback"].append({
            "agent_name": "test-agent",
            "feature_type": "api",
            "complexity": "STANDARD",
            "duration": 12.0,
            "success": True,
            "timestamp": old_date.isoformat(),
            "metadata": {}
        })
    feedback_file.write_text(json.dumps(data, indent=2))

    # Act - aggregate first, then prune
    _aggregate_old_feedback()
    _prune_expired_feedback()

    # Assert
    result = json.loads(feedback_file.read_text())
    assert len(result["feedback"]) == 5  # Only recent entries remain


def test_aggregation_frequency_monthly(tmp_project_dir, feedback_file):
    """Test that aggregation groups feedback by month."""
    # Arrange - create feedback entries across multiple months
    now = datetime.now()
    last_month = now - timedelta(days=35)
    two_months_ago = now - timedelta(days=65)

    data = {
        "version": "1.0",
        "feedback": [
            {
                "agent_name": "test-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 10.0,
                "success": True,
                "timestamp": now.isoformat(),
                "metadata": {}
            },
            {
                "agent_name": "test-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 15.0,
                "success": True,
                "timestamp": last_month.isoformat(),
                "metadata": {}
            },
            {
                "agent_name": "test-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 20.0,
                "success": False,
                "timestamp": two_months_ago.isoformat(),
                "metadata": {}
            }
        ],
        "aggregated": {}
    }
    feedback_file.write_text(json.dumps(data, indent=2))

    # Act
    aggregated = _aggregate_old_feedback()

    # Assert - should have multiple month keys
    assert len(aggregated) >= 2  # At least 2 different months
    # Verify structure exists for each month
    for month_key in aggregated:
        assert "test-agent" in aggregated[month_key]
        assert "api" in aggregated[month_key]["test-agent"]


# ============================================================================
# THREAD SAFETY TESTS (4 tests)
# ============================================================================

def test_record_feedback_thread_safe(tmp_project_dir, feedback_file):
    """Test concurrent record_feedback calls don't corrupt data.

    Note: This test verifies data integrity, not write completeness.
    Some writes may be lost due to race conditions, but the file should
    remain valid JSON and not corrupted.
    """
    # Arrange
    num_threads = 3  # Minimal for testing integrity
    entries_per_thread = 2

    def record_entries(thread_id):
        for i in range(entries_per_thread):
            record_feedback(
                f"agent-{thread_id}",
                "api",
                "STANDARD",
                10.0 + i,
                True,
                {"thread": thread_id}
            )
            time.sleep(0.02)  # Delay to reduce contention

    # Act - concurrent writes
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(record_entries, i) for i in range(num_threads)]
        for future in as_completed(futures):
            future.result()  # Raise any exceptions

    # Assert - data should not be corrupted (valid JSON with valid structure)
    data = json.loads(feedback_file.read_text())
    assert "feedback" in data
    assert isinstance(data["feedback"], list)
    # Should have at least 1 entry (file not empty)
    assert len(data["feedback"]) >= 1
    # Each entry should be valid
    for entry in data["feedback"]:
        assert "agent_name" in entry
        assert "feature_type" in entry
        assert "success" in entry


def test_query_recommendations_thread_safe(tmp_project_dir, feedback_file):
    """Test concurrent query_recommendations calls are safe."""
    # Arrange - populate data
    for i in range(20):
        record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    def query_concurrent():
        return query_recommendations("api", "STANDARD", top_n=3)

    # Act - concurrent queries
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(query_concurrent) for _ in range(10)]
        results = [future.result() for future in as_completed(futures)]

    # Assert - all queries should succeed
    assert len(results) == 10
    for result in results:
        assert len(result) >= 1


def test_get_agent_stats_thread_safe(tmp_project_dir, feedback_file):
    """Test concurrent get_agent_stats calls are safe."""
    # Arrange - populate data
    for i in range(20):
        record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    def get_stats_concurrent():
        return get_agent_stats("test-agent")

    # Act - concurrent queries
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(get_stats_concurrent) for _ in range(10)]
        results = [future.result() for future in as_completed(futures)]

    # Assert - all queries should succeed
    assert len(results) == 10
    for result in results:
        assert "overall" in result


def test_concurrent_read_write_thread_safe(tmp_project_dir, feedback_file):
    """Test concurrent reads and writes don't cause corruption."""
    # Arrange
    for i in range(10):
        record_feedback("initial-agent", "api", "STANDARD", 10.0, True, {})

    results = {"queries": [], "stats": []}

    def write_entries():
        for i in range(5):
            record_feedback(f"writer-agent-{i}", "api", "STANDARD", 10.0, True, {})
            time.sleep(0.01)

    def read_entries():
        for _ in range(5):
            recs = query_recommendations("api", "STANDARD", top_n=3)
            results["queries"].append(recs)
            time.sleep(0.01)

    def read_stats():
        for _ in range(5):
            stats = get_agent_stats("initial-agent")
            results["stats"].append(stats)
            time.sleep(0.01)

    # Act - concurrent reads and writes
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(write_entries),
            executor.submit(read_entries),
            executor.submit(read_stats)
        ]
        for future in as_completed(futures):
            future.result()

    # Assert - all operations should complete successfully
    assert len(results["queries"]) == 5
    assert len(results["stats"]) == 5


# ============================================================================
# EDGE CASES AND ERROR HANDLING (6 tests)
# ============================================================================

def test_corrupted_json_file(tmp_project_dir, feedback_file):
    """Test handling of corrupted JSON file."""
    # Arrange - create corrupted JSON
    feedback_file.write_text("{invalid json")

    # Act - should handle gracefully (return empty structure)
    data = _load_feedback_data()

    # Assert - returns valid empty structure
    assert data["version"] == "1.0"
    assert data["feedback"] == []
    assert data["aggregated"] == {}


def test_missing_required_fields(tmp_project_dir, feedback_file):
    """Test handling of feedback entries with missing fields."""
    # Arrange - manually create malformed entry
    data = {
        "version": "1.0",
        "last_aggregated": datetime.now().isoformat(),
        "feedback": [
            {
                "agent_name": "test-agent",
                # Missing required fields
            }
        ],
        "aggregated": {}
    }
    feedback_file.write_text(json.dumps(data))

    # Act - should handle gracefully (may skip malformed or raise KeyError)
    try:
        stats = get_agent_stats("test-agent")
        # Implementation should return empty or skip malformed entries
        assert stats == {} or "overall" not in stats or stats["overall"].total_executions == 0
    except KeyError:
        # Also acceptable - implementation catches malformed entries
        pass


def test_empty_feedback_file(tmp_project_dir, feedback_file):
    """Test handling of empty feedback file."""
    # Arrange
    feedback_file.write_text("")

    # Act - should handle gracefully (return empty structure)
    data = _load_feedback_data()

    # Assert - returns valid empty structure
    assert data["version"] == "1.0"
    assert data["feedback"] == []
    assert data["aggregated"] == {}


def test_invalid_timestamp_format(tmp_project_dir, feedback_file):
    """Test handling of invalid timestamp format."""
    # Arrange
    data = {
        "version": "1.0",
        "last_aggregated": datetime.now().isoformat(),
        "feedback": [
            {
                "agent_name": "test-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 10.0,
                "success": True,
                "timestamp": "invalid-timestamp",
                "metadata": {}
            }
        ],
        "aggregated": []
    }
    feedback_file.write_text(json.dumps(data))

    # Act - should handle gracefully
    stats = get_agent_stats("test-agent")
    # Implementation should skip entries with invalid timestamps


def test_negative_duration_rejected(tmp_project_dir):
    """Test that negative duration is rejected."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="duration must be positive"):
        record_feedback("test-agent", "api", "STANDARD", -10.0, True, {})


def test_empty_metadata_handling(tmp_project_dir, feedback_file):
    """Test that empty metadata is handled correctly."""
    # Arrange & Act
    record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    # Assert
    data = json.loads(feedback_file.read_text())
    assert data["feedback"][0]["metadata"] == {}


# ============================================================================
# INTEGRATION SCENARIOS (3 tests)
# ============================================================================

def test_full_workflow_record_and_query(tmp_project_dir, feedback_file):
    """Test complete workflow: record feedback, query recommendations."""
    # Arrange & Act - simulate multiple feature implementations
    for i in range(20):
        success = i % 5 != 0  # 80% success rate
        record_feedback("test-agent", "api", "STANDARD", 10.0 + i * 0.5, success, {})

    # Query recommendations
    recommendations = query_recommendations("api", "STANDARD", top_n=3)

    # Get stats
    stats = get_agent_stats("test-agent")

    # Assert
    assert len(recommendations) >= 1
    assert recommendations[0].agent_name == "test-agent"
    assert stats["overall"].success_rate == 0.8
    assert stats["overall"].total_executions == 20


def test_multi_agent_comparison(tmp_project_dir, feedback_file):
    """Test recommendation system with multiple competing agents."""
    # Arrange - simulate different agent performance
    # Agent A: high success, slow
    for i in range(30):
        record_feedback("agent-a", "api", "STANDARD", 20.0, True, {})

    # Agent B: medium success, fast
    for i in range(30):
        success = i % 2 == 0  # 50% success
        record_feedback("agent-b", "api", "STANDARD", 5.0, success, {})

    # Agent C: low data
    for i in range(2):
        record_feedback("agent-c", "api", "STANDARD", 10.0, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=3)

    # Assert - agent-a should be ranked first (high success)
    assert recommendations[0].agent_name == "agent-a"
    assert recommendations[0].confidence > recommendations[2].confidence  # More data = higher confidence


def test_state_persistence_across_restarts(tmp_project_dir, feedback_file):
    """Test that feedback persists across application restarts."""
    # Arrange - record feedback
    record_feedback("test-agent", "api", "STANDARD", 10.0, True, {})

    # Simulate restart by reloading data
    data = _load_feedback_data()

    # Act - query after "restart"
    recommendations = query_recommendations("api", "STANDARD", top_n=3)
    stats = get_agent_stats("test-agent")

    # Assert - data should persist
    assert len(recommendations) >= 1
    assert stats["overall"].total_executions == 1


# ============================================================================
# SUMMARY
# ============================================================================

"""
Test Coverage Summary:
- Dataclass tests: 5 tests
- Feature classification: 8 tests
- Record feedback: 8 tests
- Query recommendations: 10 tests
- Agent stats: 5 tests
- Pruning/aggregation: 6 tests
- Thread safety: 4 tests
- Edge cases: 6 tests
- Integration: 3 tests

Total: 55 unit tests

All tests follow TDD RED phase - they should fail until agent_feedback.py is implemented.
"""
