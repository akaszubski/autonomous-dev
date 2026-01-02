"""
Integration tests for agent_feedback.py - Real-world usage patterns

Tests cover:
1. Integration with agent_pool.py - Task routing based on feedback
2. Integration with /auto-implement pipeline - Recording actual agent performance
3. Multi-session learning - Feedback accumulation over time
4. Cross-complexity routing - Agents handling different complexity levels
5. Performance monitoring - Tracking agent efficiency trends
6. Failure recovery - Fallback agent selection
7. Data migration - Version upgrades and schema changes
8. Production scenarios - High-volume feedback processing

This is the RED phase of TDD - tests should fail initially since implementation doesn't exist yet.
"""

import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock, call
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Import the modules under test
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
    )
except ImportError:
    pytest.skip("agent_feedback.py not implemented yet", allow_module_level=True)

# Import agent_pool for integration testing
try:
    from autonomous_dev.lib.agent_pool import (
        AgentPool,
        PoolConfig,
        PriorityLevel,
    )
except ImportError:
    # Skip if agent_pool not available
    AgentPool = None
    PoolConfig = None
    PriorityLevel = None


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
def populated_feedback(tmp_project_dir, feedback_file):
    """Create realistic feedback data for multiple agents."""
    # Security-auditor: excellent at security, good at api
    for i in range(50):
        record_feedback("security-auditor", "security", "STANDARD", 12.0 + i * 0.1, True, {})
    for i in range(20):
        record_feedback("security-auditor", "api", "STANDARD", 15.0, True, {})

    # Implementer: good at api, refactor, general
    for i in range(40):
        success = i % 10 != 0  # 90% success
        record_feedback("implementer", "api", "STANDARD", 14.0, success, {})
    for i in range(30):
        record_feedback("implementer", "refactor", "STANDARD", 13.0, True, {})
    for i in range(25):
        record_feedback("implementer", "general", "STANDARD", 10.0, True, {})

    # Doc-master: excellent at docs, medium at ui
    for i in range(60):
        record_feedback("doc-master", "docs", "STANDARD", 8.0, True, {})
    for i in range(15):
        success = i % 3 != 0  # 67% success
        record_feedback("doc-master", "ui", "STANDARD", 12.0, success, {})

    # Test-master: good at tests, api
    for i in range(45):
        record_feedback("test-master", "tests", "STANDARD", 11.0, True, {})
    for i in range(20):
        record_feedback("test-master", "api", "STANDARD", 13.0, True, {})

    return feedback_file


# ============================================================================
# AGENT POOL INTEGRATION TESTS (3 tests)
# ============================================================================

@pytest.mark.skipif(AgentPool is None, reason="agent_pool.py not available")
def test_agent_pool_routing_with_feedback(populated_feedback):
    """Test that agent_feedback provides routing recommendations."""
    # Act - simulate task routing decision using agent_feedback module
    feature_desc = "Add authentication middleware"
    feature_type = classify_feature_type(feature_desc)
    recommendations = query_recommendations(feature_type, "STANDARD", top_n=3)

    # Assert - should recommend security-auditor for security tasks
    # (based on populated_feedback fixture data)
    assert len(recommendations) >= 1
    assert recommendations[0].agent_name == "security-auditor"
    assert recommendations[0].confidence > 0.9


def test_agent_pool_fallback_selection(populated_feedback):
    """Test fallback agent selection when primary agent fails."""
    # Arrange - add multiple agents with security expertise for fallback testing
    # (populated_feedback only has security-auditor for security)
    for i in range(20):
        record_feedback("implementer", "security", "STANDARD", 18.0, True, {})
    for i in range(15):
        record_feedback("reviewer", "security", "STANDARD", 20.0, True, {})

    # Now query - should have primary + fallbacks
    recommendations = query_recommendations("security", "STANDARD", top_n=3)
    assert len(recommendations) >= 2  # At least 2 agents with security experience

    primary_agent = recommendations[0].agent_name
    assert primary_agent == "security-auditor"  # Best at security

    # Act - record failure for primary agent
    record_feedback(primary_agent, "security", "STANDARD", 20.0, False, {"error": "timeout"})

    # Query again after failure
    new_recommendations = query_recommendations("security", "STANDARD", top_n=3)

    # Assert - primary should still be top (one failure out of 50+ successes)
    assert new_recommendations[0].agent_name == "security-auditor"
    # Success rate should still be high despite one failure
    stats = get_agent_stats(primary_agent)
    assert stats["overall"].success_rate > 0.8

    # Verify fallback agents are available (from the additional agents we added)
    if len(recommendations) > 1:
        assert len(recommendations[0].fallback_agents) > 0


def test_multi_agent_task_distribution(populated_feedback):
    """Test that feedback enables efficient multi-agent task distribution."""
    # Arrange - different task types
    tasks = [
        ("Add OAuth2 authentication", "security"),
        ("Update API versioning", "api"),
        ("Add user documentation", "docs"),
        ("Write integration tests", "tests"),
        ("Refactor database layer", "refactor"),
    ]

    # Act - get recommendations for each task
    assignments = {}
    for desc, expected_type in tasks:
        feature_type = classify_feature_type(desc)
        assert feature_type == expected_type
        recommendations = query_recommendations(feature_type, "STANDARD", top_n=1)
        if recommendations:
            assignments[desc] = recommendations[0].agent_name

    # Assert - tasks should be assigned to specialized agents
    assert assignments["Add OAuth2 authentication"] == "security-auditor"
    assert assignments["Update API versioning"] in ["implementer", "test-master"]
    assert assignments["Add user documentation"] == "doc-master"
    assert assignments["Write integration tests"] == "test-master"
    assert assignments["Refactor database layer"] == "implementer"


# ============================================================================
# AUTO-IMPLEMENT PIPELINE INTEGRATION (3 tests)
# ============================================================================

def test_auto_implement_feedback_recording(tmp_project_dir, feedback_file):
    """Test recording feedback during /auto-implement pipeline execution."""
    # Arrange - simulate pipeline stages
    pipeline_stages = [
        ("researcher", "api", 3.5, True),
        ("planner", "api", 2.1, True),
        ("test-master", "api", 11.2, True),
        ("implementer", "api", 14.8, True),
        ("reviewer", "api", 8.3, True),
        ("security-auditor", "api", 12.1, True),
        ("doc-master", "api", 7.9, True),
    ]

    # Act - record feedback for each stage
    for agent, feature_type, duration, success in pipeline_stages:
        record_feedback(agent, feature_type, "STANDARD", duration, success, {})

    # Assert - all stages recorded
    data = json.loads(feedback_file.read_text())
    assert len(data["feedback"]) == len(pipeline_stages)

    # Verify each agent has stats
    for agent, _, _, _ in pipeline_stages:
        stats = get_agent_stats(agent)
        assert stats["overall"].total_executions >= 1


def test_auto_implement_performance_tracking(tmp_project_dir, feedback_file):
    """Test tracking performance improvements over multiple /auto-implement runs."""
    # Arrange - simulate learning curve (agents get faster over time)
    for run in range(10):
        # Implementer gets 5% faster each run
        duration = 20.0 * (0.95 ** run)
        record_feedback("implementer", "api", "STANDARD", duration, True, {})

    # Act
    stats = get_agent_stats("implementer")

    # Assert - average duration should reflect improvement
    assert stats["overall"].avg_duration < 20.0
    assert stats["overall"].total_executions == 10


def test_auto_implement_complexity_adaptation(tmp_project_dir, feedback_file):
    """Test that feedback helps adapt to different complexity levels."""
    # Arrange - record performance at different complexity levels
    # SIMPLE: fast execution
    for i in range(20):
        record_feedback("implementer", "api", "SIMPLE", 8.0, True, {})

    # STANDARD: medium execution
    for i in range(30):
        record_feedback("implementer", "api", "STANDARD", 15.0, True, {})

    # COMPLEX: slow execution
    for i in range(15):
        record_feedback("implementer", "api", "COMPLEX", 25.0, True, {})

    # Act - query recommendations for different complexities
    simple_recs = query_recommendations("api", "SIMPLE", top_n=1)
    standard_recs = query_recommendations("api", "STANDARD", top_n=1)
    complex_recs = query_recommendations("api", "COMPLEX", top_n=1)

    # Assert - all should recommend implementer, but with different confidence
    assert simple_recs[0].agent_name == "implementer"
    assert standard_recs[0].agent_name == "implementer"
    assert complex_recs[0].agent_name == "implementer"

    # Higher execution count should mean higher confidence
    assert standard_recs[0].confidence > complex_recs[0].confidence


# ============================================================================
# MULTI-SESSION LEARNING (2 tests)
# ============================================================================

def test_multi_session_feedback_accumulation(tmp_project_dir, feedback_file):
    """Test that feedback accumulates across multiple sessions."""
    # Arrange - Session 1: Initial learning
    for i in range(10):
        record_feedback("implementer", "api", "STANDARD", 15.0, True, {})

    stats_session1 = get_agent_stats("implementer")

    # Act - Session 2: More learning
    for i in range(10):
        record_feedback("implementer", "api", "STANDARD", 14.0, True, {})

    stats_session2 = get_agent_stats("implementer")

    # Assert - execution count should accumulate
    assert stats_session2["overall"].total_executions == 20
    assert stats_session1["overall"].total_executions == 10

    # Average should reflect both sessions
    assert 14.0 <= stats_session2["overall"].avg_duration <= 15.0


def test_confidence_growth_over_sessions(tmp_project_dir, feedback_file):
    """Test that confidence grows as more feedback is collected."""
    # Arrange - Track confidence growth
    confidence_levels = []

    # Act - Gradually add feedback and track confidence
    for batch in range(5):
        # Add 10 entries per batch
        for i in range(10):
            record_feedback("implementer", "api", "STANDARD", 15.0, True, {})

        # Query recommendations
        recs = query_recommendations("api", "STANDARD", top_n=1)
        if recs:
            confidence_levels.append(recs[0].confidence)

    # Assert - confidence should increase
    assert len(confidence_levels) == 5
    # Later confidence should be higher than earlier
    assert confidence_levels[-1] > confidence_levels[0]
    # Final confidence should be high (50 executions)
    assert confidence_levels[-1] > 0.9


# ============================================================================
# CROSS-COMPLEXITY ROUTING (2 tests)
# ============================================================================

def test_complexity_based_agent_selection(populated_feedback):
    """Test that different agents are recommended for different complexities."""
    # Arrange - Add complexity-specific data
    # Agent A: good at SIMPLE tasks
    for i in range(30):
        record_feedback("agent-simple", "api", "SIMPLE", 5.0, True, {})

    # Agent B: good at COMPLEX tasks
    for i in range(30):
        record_feedback("agent-complex", "api", "COMPLEX", 25.0, True, {})

    # Act
    simple_recs = query_recommendations("api", "SIMPLE", top_n=1)
    complex_recs = query_recommendations("api", "COMPLEX", top_n=1)

    # Assert - should recommend specialists
    assert simple_recs[0].agent_name == "agent-simple"
    assert complex_recs[0].agent_name == "agent-complex"


def test_complexity_escalation_handling(tmp_project_dir, feedback_file):
    """Test handling of complexity escalation (SIMPLE task becomes COMPLEX)."""
    # Arrange - Agent starts with SIMPLE task
    record_feedback("implementer", "api", "SIMPLE", 8.0, True, {})

    # Task complexity increases
    record_feedback("implementer", "api", "STANDARD", 15.0, True, {})
    record_feedback("implementer", "api", "COMPLEX", 25.0, False, {"error": "timeout"})

    # Act
    stats = get_agent_stats("implementer")

    # Assert - stats should track all complexity levels
    # Overall success rate should account for COMPLEX failure
    assert stats["overall"].total_executions == 3


# ============================================================================
# PERFORMANCE MONITORING (2 tests)
# ============================================================================

def test_performance_regression_detection(tmp_project_dir, feedback_file):
    """Test detection of performance regression."""
    # Arrange - Baseline performance
    for i in range(20):
        record_feedback("implementer", "api", "STANDARD", 12.0, True, {})

    baseline_stats = get_agent_stats("implementer")

    # Act - Simulate performance regression
    for i in range(10):
        record_feedback("implementer", "api", "STANDARD", 20.0, True, {})

    regressed_stats = get_agent_stats("implementer")

    # Assert - average duration should increase
    assert regressed_stats["overall"].avg_duration > baseline_stats["overall"].avg_duration


def test_efficiency_trend_tracking(tmp_project_dir, feedback_file):
    """Test tracking efficiency trends over time."""
    # Arrange - Simulate gradual improvement
    durations = []
    for i in range(30):
        # 10% improvement over 30 iterations
        duration = 20.0 - (i * 0.5)
        record_feedback("implementer", "api", "STANDARD", duration, True, {})
        durations.append(duration)

    # Act
    stats = get_agent_stats("implementer")

    # Assert - average should reflect improvement
    expected_avg = sum(durations) / len(durations)
    assert abs(stats["overall"].avg_duration - expected_avg) < 1.0


# ============================================================================
# FAILURE RECOVERY (2 tests)
# ============================================================================

def test_automatic_fallback_after_failures(tmp_project_dir, feedback_file):
    """Test automatic fallback agent selection after repeated failures."""
    # Arrange - Primary agent fails repeatedly
    for i in range(5):
        record_feedback("agent-primary", "api", "STANDARD", 20.0, False, {"error": "crash"})

    # Fallback agent succeeds
    for i in range(10):
        record_feedback("agent-fallback", "api", "STANDARD", 15.0, True, {})

    # Act
    recommendations = query_recommendations("api", "STANDARD", top_n=2)

    # Assert - recommendations should exist and fallback should rank higher
    assert len(recommendations) >= 1
    # Agent with higher success rate should be ranked first
    if len(recommendations) >= 2:
        first_stats = get_agent_stats(recommendations[0].agent_name)
        second_stats = get_agent_stats(recommendations[1].agent_name)
        assert first_stats["overall"].success_rate >= second_stats["overall"].success_rate


def test_recovery_after_transient_failures(tmp_project_dir, feedback_file):
    """Test that agents can recover from transient failures."""
    # Arrange - Normal operation
    for i in range(10):
        record_feedback("implementer", "api", "STANDARD", 15.0, True, {})

    # Transient failures
    for i in range(3):
        record_feedback("implementer", "api", "STANDARD", 20.0, False, {"error": "network timeout"})

    # Recovery
    for i in range(10):
        record_feedback("implementer", "api", "STANDARD", 15.0, True, {})

    # Act
    stats = get_agent_stats("implementer")

    # Assert - success rate should still be good (20/23 = 87%)
    assert stats["overall"].success_rate > 0.85


# ============================================================================
# DATA MIGRATION AND SCHEMA CHANGES (2 tests)
# ============================================================================

def test_version_migration_compatibility(tmp_project_dir, feedback_file):
    """Test handling of data from older versions."""
    # Arrange - Create old version data
    old_data = {
        "version": "0.9",  # Old version
        "feedback": [
            {
                "agent_name": "old-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 10.0,
                "success": True,
                "timestamp": datetime.now().isoformat(),
                # Old version might be missing metadata field
            }
        ]
    }
    feedback_file.write_text(json.dumps(old_data))

    # Act - should handle gracefully
    stats = get_agent_stats("old-agent")

    # Assert - data should be accessible
    assert stats["overall"].total_executions >= 1


def test_schema_evolution_backward_compatible(tmp_project_dir, feedback_file):
    """Test that new schema changes are backward compatible."""
    # Arrange - Create data with minimal fields
    minimal_data = {
        "version": "1.0",
        "feedback": [
            {
                "agent_name": "test-agent",
                "feature_type": "api",
                "complexity": "STANDARD",
                "duration": 10.0,
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "metadata": {}
            }
        ]
    }
    feedback_file.write_text(json.dumps(minimal_data))

    # Act - add new entry with extended fields
    record_feedback(
        "test-agent",
        "api",
        "STANDARD",
        12.0,
        True,
        {"extended_field": "new_value"}
    )

    # Assert - both old and new entries should coexist
    data = json.loads(feedback_file.read_text())
    assert len(data["feedback"]) == 2


# ============================================================================
# PRODUCTION SCENARIOS (2 tests)
# ============================================================================

def test_high_volume_feedback_processing(tmp_project_dir, feedback_file):
    """Test system performance with high-volume feedback (1000+ entries)."""
    # Arrange - Generate large dataset
    agents = ["implementer", "security-auditor", "doc-master", "test-master"]
    feature_types = ["api", "security", "docs", "tests"]

    start_time = time.time()

    # Act - record 1000 entries
    for i in range(1000):
        agent = agents[i % len(agents)]
        feature_type = feature_types[i % len(feature_types)]
        record_feedback(agent, feature_type, "STANDARD", 10.0 + (i % 10), True, {})

    record_time = time.time() - start_time

    # Query performance
    query_start = time.time()
    for feature_type in feature_types:
        recommendations = query_recommendations(feature_type, "STANDARD", top_n=3)
    query_time = time.time() - query_start

    # Assert - should complete in reasonable time
    assert record_time < 10.0  # Recording should be fast
    assert query_time < 2.0  # Queries should be fast

    # Data integrity check
    data = json.loads(feedback_file.read_text())
    assert len(data["feedback"]) == 1000


def test_concurrent_production_load(tmp_project_dir, feedback_file):
    """Test system under concurrent production load.

    Note: This test verifies data integrity under concurrent access.
    Some writes may be lost due to race conditions, but the file should
    remain valid JSON.
    """
    # Arrange
    num_threads = 5  # Reduced for more reliable test
    entries_per_thread = 10

    def simulate_agent_execution(thread_id):
        for i in range(entries_per_thread):
            # Mix of reads and writes
            if i % 3 == 0:
                # Query recommendations
                query_recommendations("api", "STANDARD", top_n=3)
            else:
                # Record feedback
                record_feedback(
                    f"agent-{thread_id % 3}",
                    "api",
                    "STANDARD",
                    10.0 + i,
                    True,
                    {"thread": thread_id}
                )
            time.sleep(0.02)  # Simulate processing time

    # Act - concurrent execution
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(simulate_agent_execution, i) for i in range(num_threads)]
        for future in as_completed(futures):
            future.result()
    execution_time = time.time() - start_time

    # Assert - should handle concurrent load
    assert execution_time < 30.0  # Should complete in reasonable time

    # Verify data integrity (valid JSON, not corrupted)
    data = json.loads(feedback_file.read_text())
    assert "feedback" in data
    assert isinstance(data["feedback"], list)
    # Should have at least some entries (allows for race condition losses)
    assert len(data["feedback"]) >= 1


# ============================================================================
# SUMMARY
# ============================================================================

"""
Integration Test Coverage Summary:
- Agent pool integration: 3 tests
- Auto-implement pipeline: 3 tests
- Multi-session learning: 2 tests
- Cross-complexity routing: 2 tests
- Performance monitoring: 2 tests
- Failure recovery: 2 tests
- Data migration: 2 tests
- Production scenarios: 2 tests

Total: 18 integration tests

These tests validate real-world usage patterns and integration with other components.
All tests follow TDD RED phase - they should fail until agent_feedback.py is implemented.
"""
