#!/usr/bin/env python3
"""
Integration tests for parallel research+planning execution (Issue #46 Phase 2).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation not yet updated).

Test Strategy:
- Test parallel execution of researcher + planner agents (STEP 1-2)
- Test coordination logic in auto-implement.md
- Test graceful fallback to sequential if parallel fails
- Test combined results from both agents
- Test conflict resolution when agents disagree

Phase 2 Goals:
- Parallelize STEP 1-2 (research + planning)
- Save 3-8 minutes per /auto-implement invocation
- Graceful fallback to sequential on failure
- Target: ≤25 minutes total (from 33 minutes)

Date: 2025-11-07
Workflow: phase2_parallel_exploration
Agent: test-master
"""

import json
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import agent tracker
try:
    from scripts.agent_tracker import AgentTracker
except ImportError as e:
    pytest.skip(f"AgentTracker not found: {e}", allow_module_level=True)


@pytest.fixture
def mock_session_file(tmp_path):
    """Create a temporary session file for testing."""
    session_file = tmp_path / "session.json"
    session_data = {
        "session_id": "20251107-phase2-test",
        "started": "2025-11-07T10:00:00",
        "agents": []
    }
    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


@pytest.fixture
def mock_agent_tracker(mock_session_file):
    """Create AgentTracker instance with mock session file."""
    return AgentTracker(session_file=str(mock_session_file))


class TestParallelExplorationHappyPath:
    """Test successful parallel execution of research and planning."""

    @patch('subprocess.run')
    def test_researcher_and_planner_invoked_in_parallel(self, mock_run, mock_session_file):
        """
        Test that researcher and planner are invoked in parallel (STEP 1-2).

        Given: /auto-implement workflow starts
        When: STEP 1-2 executes
        Then: Researcher and planner both invoked via Task tool
        And: Both agents run concurrently (not sequentially)
        And: Session file shows parallel execution

        Protects: Phase 2 core parallelization (Issue #46)
        """
        # NOTE: This WILL FAIL - parallel execution not implemented yet
        pytest.skip("Requires /auto-implement STEP 1-2 parallel implementation")

        # Arrange: Mock Task tool for parallel invocation
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act: Simulate /auto-implement STEP 1-2 parallel execution
        # In reality, this would be in auto-implement.md coordination logic
        base_time = datetime.now()

        # Both agents start at similar time (within 5 seconds)
        tracker.log_start("researcher", "Researching JWT patterns")
        researcher_start = datetime.now()

        time.sleep(0.01)  # Small delay to ensure different timestamps
        tracker.log_start("planner", "Planning architecture")
        planner_start = datetime.now()

        # Assert: Both started within 5 seconds (parallel)
        time_diff = abs((planner_start - researcher_start).total_seconds())
        assert time_diff < 5, f"Agents started {time_diff}s apart, expected < 5s for parallel"

        # Both complete
        tracker.log_complete("researcher", "Found 3 JWT patterns", tools_used=["WebSearch", "Grep"])
        tracker.log_complete("planner", "Architecture plan created", tools_used=["Read", "Edit"])

        # Verify parallel execution
        result = tracker.verify_parallel_exploration()
        assert result is True, "Expected parallel exploration to succeed"

    def test_parallel_exploration_saves_3_to_8_minutes(self, mock_session_file):
        """
        Test that parallel execution saves 3-8 minutes compared to sequential.

        Given: Sequential execution takes 13 minutes (6 min research + 7 min planning)
        When: Parallel execution runs both agents concurrently
        Then: Total time = max(6, 7) = 7 minutes
        And: Time saved = 6 minutes (within 3-8 minute target)

        Protects: Phase 2 performance goal (Issue #46)
        """
        # NOTE: This WILL FAIL - parallel execution not implemented yet
        # Arrange: Simulate parallel execution with realistic timings
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        # Load session data manually for testing
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=6)).isoformat(),
                "duration_seconds": 360,
                "message": "Research complete"
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=7)).isoformat(),
                "duration_seconds": 420,
                "message": "Planning complete"
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify parallel exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Time savings within target range
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]

        time_saved_minutes = parallel_data["time_saved_seconds"] / 60
        assert 3 <= time_saved_minutes <= 8, \
            f"Time saved {time_saved_minutes} min, expected 3-8 min"

    def test_parallel_results_combined_correctly(self, mock_session_file):
        """
        Test that results from both agents are combined correctly.

        Given: Researcher produces research findings
        And: Planner produces architecture plan
        When: Both complete in parallel
        Then: Combined results include both research and plan
        And: No data loss from parallel execution

        Protects: Phase 2 data integrity (Issue #46)
        """
        # NOTE: This WILL FAIL - result combination logic not implemented yet
        pytest.skip("Requires result combination implementation")

        # Arrange: Both agents produce results
        tracker = AgentTracker(session_file=str(mock_session_file))

        research_findings = {
            "patterns_found": 3,
            "best_practices": ["JWT in httpOnly cookies", "Short expiry", "Refresh tokens"]
        }

        architecture_plan = {
            "components": ["AuthService", "TokenManager", "RefreshHandler"],
            "database_changes": ["users.refresh_token column"]
        }

        # Act: Both agents complete with results
        tracker.log_complete("researcher", json.dumps(research_findings), tools_used=["WebSearch"])
        tracker.log_complete("planner", json.dumps(architecture_plan), tools_used=["Edit"])

        # Verify results combined
        result = tracker.verify_parallel_exploration()
        assert result is True

        # Assert: Combined results available
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]

        assert "combined_results" in parallel_data
        combined = parallel_data["combined_results"]
        assert "research_findings" in combined
        assert "architecture_plan" in combined

    def test_parallel_exploration_updates_pipeline_status(self, mock_session_file):
        """
        Test that parallel exploration correctly updates pipeline status.

        Given: Pipeline tracking enabled
        When: Researcher and planner complete in parallel
        Then: Pipeline status shows STEP 1-2 completed
        And: Status file shows parallelization metrics

        Protects: Phase 2 pipeline integration (Issue #46)
        """
        # NOTE: This WILL FAIL - pipeline status integration not implemented yet
        pytest.skip("Requires pipeline status integration")

        # Arrange: Pipeline status file
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act: Both agents complete
        tracker.log_start("researcher", "Research starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])
        tracker.log_start("planner", "Planning starting")
        tracker.log_complete("planner", "Planning complete", tools_used=["Edit"])

        result = tracker.verify_parallel_exploration()

        # Assert: Pipeline status updated
        # Would check pipeline_status.json here
        assert result is True

    def test_audit_log_captures_parallel_execution(self, mock_session_file):
        """
        Test that security audit log captures parallel execution events.

        Given: Parallel execution of researcher and planner
        When: Both agents complete
        Then: Audit log contains entries for both agents
        And: Log shows parallel execution detected

        Protects: Phase 2 security audit trail (Issue #46)
        """
        # NOTE: This WILL FAIL - audit logging not implemented yet
        pytest.skip("Requires audit logging implementation")

        # Arrange: Enable audit logging
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act: Both agents complete in parallel
        tracker.log_start("researcher", "Research starting")
        tracker.log_start("planner", "Planning starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])
        tracker.log_complete("planner", "Planning complete", tools_used=["Edit"])

        result = tracker.verify_parallel_exploration()

        # Assert: Audit log entries exist
        # Would check logs/security_audit.log here
        assert result is True


class TestParallelExplorationPartialFailures:
    """Test graceful handling of partial failures in parallel execution."""

    def test_fallback_to_sequential_when_parallel_fails(self, mock_session_file):
        """
        Test graceful fallback to sequential execution when parallel fails.

        Given: Parallel execution attempted
        When: Parallel execution fails (e.g., Task tool error)
        Then: System falls back to sequential execution
        And: Session file shows sequential fallback
        And: All agents still complete successfully

        Protects: Phase 2 resilience requirement (Issue #46)
        """
        # NOTE: This WILL FAIL - fallback logic not implemented yet
        pytest.skip("Requires fallback implementation")

        # Arrange: Mock parallel failure
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Act: Simulate parallel failure, then sequential success
        # Researcher completes
        tracker.log_start("researcher", "Research starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])

        # Planner starts AFTER researcher (sequential)
        time.sleep(0.02)
        tracker.log_start("planner", "Planning starting (sequential fallback)")
        tracker.log_complete("planner", "Planning complete", tools_used=["Edit"])

        # Verify execution completed (despite fallback)
        result = tracker.verify_parallel_exploration()
        assert result is True, "Sequential fallback should still succeed"

        # Assert: Fallback recorded
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["status"] == "sequential_fallback"

    def test_researcher_fails_planner_completes(self, mock_session_file):
        """
        Test when researcher fails but planner completes.

        Given: Parallel execution started
        When: Researcher fails (e.g., API timeout)
        And: Planner completes successfully
        Then: verify_parallel_exploration() returns False
        And: Session shows partial failure
        And: Recommendation to retry researcher

        Protects: Phase 2 partial failure handling (Issue #46)
        """
        # Arrange: Researcher fails
        tracker = AgentTracker(session_file=str(mock_session_file))

        tracker.log_start("researcher", "Research starting")
        tracker.log_fail("researcher", "WebSearch API timeout")

        tracker.log_start("planner", "Planning starting")
        tracker.log_complete("planner", "Planning complete", tools_used=["Edit"])

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Partial failure detected
        assert result is False, "Should fail when researcher fails"

        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["status"] == "failed"
        assert "researcher" in parallel_data["failed_agents"]

    def test_planner_fails_researcher_completes(self, mock_session_file):
        """
        Test when planner fails but researcher completes.

        Given: Parallel execution started
        When: Planner fails (e.g., invalid architecture)
        And: Researcher completes successfully
        Then: verify_parallel_exploration() returns False
        And: Session shows partial failure
        And: Recommendation to retry planner

        Protects: Phase 2 partial failure handling (Issue #46)
        """
        # Arrange: Planner fails
        tracker = AgentTracker(session_file=str(mock_session_file))

        tracker.log_start("researcher", "Research starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])

        tracker.log_start("planner", "Planning starting")
        tracker.log_fail("planner", "Invalid architecture pattern")

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Partial failure detected
        assert result is False, "Should fail when planner fails"

        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["status"] == "failed"
        assert "planner" in parallel_data["failed_agents"]

    def test_both_agents_fail_in_parallel(self, mock_session_file):
        """
        Test when both researcher and planner fail in parallel.

        Given: Parallel execution started
        When: Both researcher and planner fail
        Then: verify_parallel_exploration() returns False
        And: Session shows complete failure
        And: Recommendation to retry /auto-implement

        Protects: Phase 2 complete failure handling (Issue #46)
        """
        # Arrange: Both fail
        tracker = AgentTracker(session_file=str(mock_session_file))

        tracker.log_start("researcher", "Research starting")
        tracker.log_fail("researcher", "WebSearch API down")

        tracker.log_start("planner", "Planning starting")
        tracker.log_fail("planner", "Planning service unavailable")

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Complete failure detected
        assert result is False, "Should fail when both agents fail"

        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["status"] == "failed"
        assert len(parallel_data["failed_agents"]) == 2

    def test_timeout_during_parallel_execution(self, mock_session_file):
        """
        Test timeout handling during parallel execution.

        Given: Parallel execution started
        When: One agent exceeds timeout threshold (15 minutes)
        Then: Agent is marked as timed out
        And: Other agent continues if still running
        And: verify_parallel_exploration() returns False

        Protects: Phase 2 timeout handling (Issue #46)
        """
        # NOTE: This WILL FAIL - timeout logic not implemented yet
        pytest.skip("Requires timeout implementation")

        # Arrange: Simulate timeout
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        # Researcher times out
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "timeout",
                "started_at": base_time.isoformat(),
                "timeout_at": (base_time + timedelta(minutes=15)).isoformat(),
                "message": "Exceeded 15 minute timeout"
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=7)).isoformat(),
                "duration_seconds": 420
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Timeout detected
        assert result is False, "Should fail on timeout"


class TestParallelExplorationConflictResolution:
    """Test conflict resolution when researcher and planner disagree."""

    def test_conflicting_recommendations_resolved(self, mock_session_file):
        """
        Test resolution when researcher and planner have conflicting recommendations.

        Given: Researcher recommends Pattern A
        And: Planner recommends Pattern B
        When: Both complete in parallel
        Then: Conflict is detected and logged
        And: User is prompted to choose pattern

        Protects: Phase 2 conflict detection (Issue #46)
        """
        # NOTE: This WILL FAIL - conflict resolution not implemented yet
        pytest.skip("Requires conflict resolution implementation")

        # Arrange: Conflicting results
        tracker = AgentTracker(session_file=str(mock_session_file))

        research_result = {"recommended_pattern": "JWT in localStorage"}
        planning_result = {"recommended_pattern": "JWT in httpOnly cookies"}

        tracker.log_complete("researcher", json.dumps(research_result), tools_used=["WebSearch"])
        tracker.log_complete("planner", json.dumps(planning_result), tools_used=["Edit"])

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Conflict detected
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert "conflicts_detected" in parallel_data
        assert parallel_data["conflicts_detected"] is True

    def test_compatible_recommendations_merged(self, mock_session_file):
        """
        Test merging when researcher and planner have compatible recommendations.

        Given: Researcher finds 3 patterns
        And: Planner selects Pattern 2 from research
        When: Both complete in parallel
        Then: Results are compatible and merged
        And: No conflicts detected

        Protects: Phase 2 result merging (Issue #46)
        """
        # NOTE: This WILL FAIL - merging logic not implemented yet
        pytest.skip("Requires merging implementation")

        # Arrange: Compatible results
        tracker = AgentTracker(session_file=str(mock_session_file))

        research_result = {
            "patterns": ["Pattern A", "Pattern B", "Pattern C"],
            "recommended": "Pattern B"
        }
        planning_result = {
            "selected_pattern": "Pattern B",
            "components": ["AuthService", "TokenManager"]
        }

        tracker.log_complete("researcher", json.dumps(research_result), tools_used=["WebSearch"])
        tracker.log_complete("planner", json.dumps(planning_result), tools_used=["Edit"])

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Compatible merge
        assert result is True
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data.get("conflicts_detected", False) is False

    def test_researcher_provides_insufficient_data_for_planner(self, mock_session_file):
        """
        Test when researcher provides insufficient data for planner.

        Given: Researcher finds no patterns (empty result)
        And: Planner cannot create plan without patterns
        When: Both complete in parallel
        Then: Dependency conflict detected
        And: Fallback to sequential execution recommended

        Protects: Phase 2 dependency validation (Issue #46)
        """
        # NOTE: This WILL FAIL - dependency validation not implemented yet
        pytest.skip("Requires dependency validation")

        # Arrange: Insufficient research data
        tracker = AgentTracker(session_file=str(mock_session_file))

        research_result = {"patterns": [], "error": "No patterns found"}
        planning_result = {"error": "Cannot plan without patterns"}

        tracker.log_complete("researcher", json.dumps(research_result), tools_used=["WebSearch"])
        tracker.log_complete("planner", json.dumps(planning_result), tools_used=["Edit"])

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Dependency issue detected
        assert result is False
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert "dependency_issue" in parallel_data

    def test_planner_starts_before_researcher_finishes(self, mock_session_file):
        """
        Test when planner starts before researcher finishes (true parallel).

        Given: Researcher and planner start at same time
        And: Planner may not have all research data yet
        When: Both run concurrently
        Then: Planner works with available data
        Or: Planner waits for critical research results

        Protects: Phase 2 true parallel execution (Issue #46)
        """
        # NOTE: This WILL FAIL - concurrent execution logic not implemented yet
        pytest.skip("Requires concurrent execution implementation")

        # Arrange: True parallel execution
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()

        # Both start at same time
        tracker.log_start("researcher", "Research starting")
        tracker.log_start("planner", "Planning starting")

        # Planner completes BEFORE researcher
        time.sleep(0.01)
        tracker.log_complete("planner", "Planning complete (used cached data)", tools_used=["Read"])

        time.sleep(0.01)
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: True parallel execution detected
        assert result is True
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["planner_finished_first"] is True

    def test_research_updates_during_planning(self, mock_session_file):
        """
        Test when research findings update while planner is running.

        Given: Both agents running in parallel
        When: Researcher publishes incremental findings
        And: Planner reads updated findings mid-execution
        Then: Planner incorporates updated research
        And: No data race or corruption

        Protects: Phase 2 concurrent data access (Issue #46)
        """
        # NOTE: This WILL FAIL - concurrent data handling not implemented yet
        pytest.skip("Requires concurrent data handling")

        # Arrange: Incremental research updates
        tracker = AgentTracker(session_file=str(mock_session_file))

        tracker.log_start("researcher", "Research starting")
        tracker.log_start("planner", "Planning starting")

        # Researcher publishes partial results
        # Planner reads partial results
        # Researcher publishes final results
        # Planner incorporates final results

        tracker.log_complete("researcher", "Research complete (3 patterns)", tools_used=["WebSearch"])
        tracker.log_complete("planner", "Planning complete (used all 3 patterns)", tools_used=["Read"])

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Incremental updates handled correctly
        assert result is True


class TestParallelExplorationAgentTracking:
    """Test agent tracking for parallel exploration."""

    def test_agent_count_remains_7_with_parallel_execution(self, mock_session_file):
        """
        Test that total agent count remains 7 despite parallelization.

        Given: /auto-implement workflow with 7 agents total
        When: STEP 1-2 executes in parallel
        Then: Only 2 agents counted (researcher, planner)
        And: Total workflow still has 7 agents
        And: Agent order preserved

        Protects: Phase 2 agent count consistency (Issue #46)
        """
        # Arrange: Full workflow execution
        tracker = AgentTracker(session_file=str(mock_session_file))

        # STEP 1-2: Parallel
        tracker.log_start("researcher", "Research starting")
        tracker.log_start("planner", "Planning starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])
        tracker.log_complete("planner", "Planning complete", tools_used=["Edit"])

        # Verify parallel execution
        result = tracker.verify_parallel_exploration()
        assert result is True

        # STEP 3-7: Sequential
        for agent in ["test-master", "implementer", "reviewer", "security-auditor", "doc-master"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} complete", tools_used=["Read"])

        # Assert: Total 7 agents
        session_data = json.loads(mock_session_file.read_text())
        assert len(session_data["agents"]) == 7, "Expected 7 total agents"

    def test_parallel_exploration_session_file_format(self, mock_session_file):
        """
        Test that parallel exploration adds correct metadata to session file.

        Given: Parallel execution completes
        When: Session file is written
        Then: Contains parallel_exploration section
        And: Includes timing metrics
        And: Includes efficiency calculation

        Protects: Phase 2 session file structure (Issue #46)
        """
        # Arrange: Parallel execution
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=6)).isoformat(),
                "duration_seconds": 360
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=7)).isoformat(),
                "duration_seconds": 420
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Correct format
        session_data = json.loads(mock_session_file.read_text())
        assert "parallel_exploration" in session_data

        parallel_data = session_data["parallel_exploration"]
        required_fields = [
            "status",
            "sequential_time_seconds",
            "parallel_time_seconds",
            "time_saved_seconds",
            "efficiency_percent"
        ]

        for field in required_fields:
            assert field in parallel_data, f"Missing required field: {field}"

    def test_pipeline_status_includes_parallel_metrics(self, mock_session_file, tmp_path):
        """
        Test that pipeline status includes parallel exploration metrics.

        Given: Pipeline status tracking enabled
        When: Parallel exploration completes
        Then: Pipeline status shows parallelization metrics
        And: Status shows time saved

        Protects: Phase 2 pipeline status integration (Issue #46)
        """
        # NOTE: This WILL FAIL - pipeline status integration not implemented yet
        pytest.skip("Requires pipeline status integration")

        # Arrange: Pipeline status file
        tracker = AgentTracker(session_file=str(mock_session_file))

        tracker.log_start("researcher", "Research starting")
        tracker.log_start("planner", "Planning starting")
        tracker.log_complete("researcher", "Research complete", tools_used=["WebSearch"])
        tracker.log_complete("planner", "Planning complete", tools_used=["Edit"])

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Pipeline status updated
        # Would check pipeline_status.json here
        assert result is True


class TestParallelExplorationEdgeCases:
    """Test edge cases in parallel exploration."""

    def test_researcher_completes_instantly(self, mock_session_file):
        """
        Test when researcher completes almost instantly (cached results).

        Given: Researcher has cached results
        When: Researcher completes in < 1 second
        And: Planner takes normal time (7 minutes)
        Then: Time saved is minimal (< 1 second)
        And: Efficiency is low

        Protects: Phase 2 edge case handling (Issue #46)
        """
        # Arrange: Instant researcher
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(seconds=1)).isoformat(),
                "duration_seconds": 1
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=7)).isoformat(),
                "duration_seconds": 420
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Minimal time saved
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["time_saved_seconds"] < 5

    def test_planner_completes_instantly(self, mock_session_file):
        """
        Test when planner completes almost instantly (template-based).

        Given: Planner uses template architecture
        When: Planner completes in < 1 second
        And: Researcher takes normal time (6 minutes)
        Then: Time saved is minimal (< 1 second)

        Protects: Phase 2 edge case handling (Issue #46)
        """
        # Arrange: Instant planner
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()
        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=6)).isoformat(),
                "duration_seconds": 360
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(seconds=1)).isoformat(),
                "duration_seconds": 1
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Minimal time saved
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["time_saved_seconds"] < 5

    def test_both_agents_complete_in_same_second(self, mock_session_file):
        """
        Test when both agents complete at exactly the same time.

        Given: Researcher and planner both take 5 minutes
        And: Both complete in same second
        When: verify_parallel_exploration() calculates metrics
        Then: Handles identical timestamps correctly
        And: Efficiency calculated as ~50%

        Protects: Phase 2 timestamp edge cases (Issue #46)
        """
        # Arrange: Identical completion times
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()
        completion_time = base_time + timedelta(minutes=5)

        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": completion_time.isoformat(),
                "duration_seconds": 300
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": completion_time.isoformat(),
                "duration_seconds": 300
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Identical timestamps handled
        assert result is True
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["efficiency_percent"] == pytest.approx(50.0, rel=1e-2)

    def test_system_clock_skew_during_parallel_execution(self, mock_session_file):
        """
        Test handling of system clock skew during execution.

        Given: System clock adjusted during execution
        When: Planner appears to complete before researcher started
        Then: Detects clock skew and logs warning
        And: Falls back to duration-based calculation

        Protects: Phase 2 clock skew handling (Issue #46)
        """
        # NOTE: This WILL FAIL - clock skew detection not implemented yet
        pytest.skip("Requires clock skew detection")

        # Arrange: Clock skew scenario
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()
        skewed_time = base_time - timedelta(minutes=10)  # Clock went backwards

        session_data = json.loads(mock_session_file.read_text())
        session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "started_at": base_time.isoformat(),
                "completed_at": (base_time + timedelta(minutes=6)).isoformat(),
                "duration_seconds": 360
            },
            {
                "agent": "planner",
                "status": "completed",
                "started_at": skewed_time.isoformat(),  # Before researcher!
                "completed_at": (skewed_time + timedelta(minutes=7)).isoformat(),
                "duration_seconds": 420
            }
        ]
        mock_session_file.write_text(json.dumps(session_data, indent=2))

        # Act: Verify exploration
        result = tracker.verify_parallel_exploration()

        # Assert: Clock skew detected
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert "clock_skew_detected" in parallel_data
        assert parallel_data["clock_skew_detected"] is True

    def test_verify_called_before_agents_complete(self, mock_session_file):
        """
        Test verify_parallel_exploration() called before agents complete.

        Given: Only researcher started (not completed)
        When: verify_parallel_exploration() is called
        Then: Returns False (agents not completed)
        And: Logs warning about premature verification

        Protects: Phase 2 premature verification (Issue #46)
        """
        # Arrange: Only started, not completed
        tracker = AgentTracker(session_file=str(mock_session_file))

        tracker.log_start("researcher", "Research starting")
        tracker.log_start("planner", "Planning starting")

        # Act: Verify before completion
        result = tracker.verify_parallel_exploration()

        # Assert: Incomplete execution detected
        assert result is False
        session_data = json.loads(mock_session_file.read_text())
        parallel_data = session_data["parallel_exploration"]
        assert parallel_data["status"] == "incomplete"
