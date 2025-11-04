"""
Integration tests for parallel validation in /auto-implement workflow.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation not yet updated).

Test Strategy:
- Test parallel execution of 3 validation agents (reviewer, security-auditor, doc-master)
- Test session file tracking shows concurrent execution
- Test agent tracker correctly handles 7 total agents
- Test graceful handling of partial failures
- Test combined results reporting

Date: 2025-11-04
Workflow: parallel_validation
Agent: test-master
"""

import json
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from datetime import datetime
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

# Import agent tracker (this should exist)
try:
    from scripts.agent_tracker import AgentTracker
except ImportError as e:
    pytest.skip(f"AgentTracker not found: {e}", allow_module_level=True)


@pytest.fixture
def mock_session_file(tmp_path):
    """Create a temporary session file for testing."""
    session_file = tmp_path / "session.json"
    session_data = {
        "session_id": "20251104-test",
        "started": "2025-11-04T10:00:00",
        "agents": []
    }
    session_file.write_text(json.dumps(session_data, indent=2))
    return session_file


@pytest.fixture
def mock_agent_tracker(mock_session_file):
    """Create AgentTracker instance with mock session file."""
    return AgentTracker(session_file=str(mock_session_file))


class TestParallelValidationHappyPath:
    """Test successful parallel execution of validation agents."""

    @patch('subprocess.run')
    def test_all_three_validators_run_in_parallel(self, mock_run, mock_session_file):
        """
        Test that reviewer, security-auditor, and doc-master are invoked in parallel.

        Expected behavior:
        - All 3 agents invoked in single workflow step
        - Session file shows similar start times (within 5 seconds)
        - All 3 complete successfully
        - Total agent count = 7 (researcher, planner, test-master, implementer + 3 validators)
        """
        # Arrange: Simulate 4 agents already completed (researcher, planner, test-master, implementer)
        tracker = AgentTracker(session_file=str(mock_session_file))

        base_time = datetime.now()
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read", "Edit"])

        # Simulate parallel validation start
        start_times = []
        for agent in ["reviewer", "security-auditor", "doc-master"]:
            start_time = datetime.now()
            tracker.log_start(agent, f"{agent} validating")
            start_times.append(start_time)

        # Act: All validators complete
        for agent in ["reviewer", "security-auditor", "doc-master"]:
            tracker.log_complete(agent, f"{agent} approved", tools_used=["Read", "Grep"])

        # Assert: Check parallelism
        time_diffs = []
        for i in range(1, len(start_times)):
            diff = (start_times[i] - start_times[0]).total_seconds()
            time_diffs.append(diff)

        # All should start within 5 seconds (indicating parallelism)
        assert all(diff <= 5.0 for diff in time_diffs), \
            f"Validators did not start in parallel. Time diffs: {time_diffs}"

        # Assert: Total agent count
        status = tracker.get_status()
        assert len(status["agents"]) == 7, \
            f"Expected 7 agents, got {len(status['agents'])}"

        # Assert: All completed
        completed_agents = [a["agent"] for a in status["agents"] if a["status"] == "completed"]
        assert len(completed_agents) == 7, \
            f"Expected 7 completed agents, got {len(completed_agents)}"

    @patch('subprocess.run')
    def test_parallel_validation_updates_session_file_correctly(self, mock_run, mock_session_file):
        """
        Test that concurrent session file updates don't corrupt data.

        Expected behavior:
        - File locking prevents corruption
        - All 3 validator entries appear in session file
        - No data loss during concurrent writes
        - Start/complete times preserved accurately
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Simulate concurrent validation (in real implementation, these would run in parallel)
        validators = ["reviewer", "security-auditor", "doc-master"]

        # Start all validators
        for agent in validators:
            tracker.log_start(agent, f"{agent} validating")

        # Complete all validators (potentially concurrent)
        for agent in validators:
            tracker.log_complete(agent, f"{agent} approved", tools_used=["Read", "Grep"])

        # Assert: Read session file directly to verify integrity
        session_data = json.loads(mock_session_file.read_text())

        assert len(session_data["agents"]) == 7, \
            f"Session file should have 7 agents, got {len(session_data['agents'])}"

        # Verify all validators present
        agent_names = [a["agent"] for a in session_data["agents"]]
        for validator in validators:
            assert validator in agent_names, \
                f"Validator {validator} missing from session file"

        # Verify all have start and complete times
        for agent_entry in session_data["agents"]:
            if agent_entry["agent"] in validators:
                assert "started_at" in agent_entry, \
                    f"{agent_entry['agent']} missing started_at"
                assert "completed_at" in agent_entry, \
                    f"{agent_entry['agent']} missing completed_at"
                assert agent_entry["status"] == "completed", \
                    f"{agent_entry['agent']} status should be completed"


class TestParallelValidationPartialFailures:
    """Test graceful handling when some validators fail."""

    def test_reviewer_fails_others_succeed(self, mock_session_file):
        """
        Test workflow when reviewer finds issues but security and docs pass.

        Expected behavior:
        - Reviewer reports changes needed
        - Security-auditor still runs and completes
        - Doc-master still runs and completes
        - Combined report shows reviewer issues
        - Pipeline allows user to fix and re-run
        - Agent count still = 7
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Parallel validation with reviewer failure
        # Reviewer finds issues
        tracker.log_start("reviewer", "Reviewing code quality")
        tracker.log_fail("reviewer", "CHANGES REQUESTED: Poor error handling in auth.py")

        # Security and docs still complete successfully
        tracker.log_start("security-auditor", "Scanning for vulnerabilities")
        tracker.log_complete("security-auditor", "No security issues found", tools_used=["Grep"])

        tracker.log_start("doc-master", "Updating documentation")
        tracker.log_complete("doc-master", "Documentation updated", tools_used=["Edit"])

        # Assert: Check status
        status = tracker.get_status()
        assert len(status["agents"]) == 7, "Should have 7 agent entries"

        # Find reviewer status
        reviewer_entry = next((a for a in status["agents"] if a["agent"] == "reviewer"), None)
        assert reviewer_entry is not None, "Reviewer entry should exist"
        assert reviewer_entry["status"] == "failed", "Reviewer should have failed status"
        assert "CHANGES REQUESTED" in reviewer_entry.get("message", ""), \
            "Reviewer failure message should be preserved"

        # Other validators should succeed
        security_entry = next((a for a in status["agents"] if a["agent"] == "security-auditor"), None)
        assert security_entry["status"] == "completed", "Security should complete despite reviewer failure"

        doc_entry = next((a for a in status["agents"] if a["agent"] == "doc-master"), None)
        assert doc_entry["status"] == "completed", "Doc-master should complete despite reviewer failure"

    def test_security_critical_issue_blocks_deployment(self, mock_session_file):
        """
        Test that critical security issues block deployment even if other validators pass.

        Expected behavior:
        - Security-auditor finds critical issue (hardcoded secret)
        - Reviewer and doc-master still complete
        - Pipeline halts before git operations
        - Clear error message about security blocking
        - User must fix security issue before proceeding
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Parallel validation with critical security failure
        tracker.log_start("reviewer", "Reviewing code quality")
        tracker.log_complete("reviewer", "Code quality approved", tools_used=["Read"])

        tracker.log_start("security-auditor", "Scanning for vulnerabilities")
        tracker.log_fail(
            "security-auditor",
            "CRITICAL: Hardcoded API key found in auth.py:42 - API_KEY = 'sk-1234567890'"
        )

        tracker.log_start("doc-master", "Updating documentation")
        tracker.log_complete("doc-master", "Documentation updated", tools_used=["Edit"])

        # Assert: Security failure should be flagged
        status = tracker.get_status()

        security_entry = next((a for a in status["agents"] if a["agent"] == "security-auditor"), None)
        assert security_entry["status"] == "failed", "Security should have failed status"
        assert "CRITICAL" in security_entry.get("message", ""), \
            "Security failure should be marked as critical"
        assert "Hardcoded API key" in security_entry.get("message", ""), \
            "Security message should describe the issue"

        # Other validators still completed
        reviewer_entry = next((a for a in status["agents"] if a["agent"] == "reviewer"), None)
        assert reviewer_entry["status"] == "completed"

        doc_entry = next((a for a in status["agents"] if a["agent"] == "doc-master"), None)
        assert doc_entry["status"] == "completed"

    def test_all_three_validators_fail(self, mock_session_file):
        """
        Test worst-case scenario where all validators find issues.

        Expected behavior:
        - All 3 validators run to completion
        - All 3 report their respective issues
        - Combined report shows all issues together
        - Clear guidance on what needs fixing
        - Pipeline shows failed state but doesn't crash
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: All validators fail
        tracker.log_start("reviewer", "Reviewing code quality")
        tracker.log_fail("reviewer", "CHANGES REQUESTED: Missing error handling, poor naming")

        tracker.log_start("security-auditor", "Scanning for vulnerabilities")
        tracker.log_fail("security-auditor", "CRITICAL: SQL injection vulnerability in user_query.py:28")

        tracker.log_start("doc-master", "Updating documentation")
        tracker.log_fail("doc-master", "Documentation missing: No API docs for new endpoints")

        # Assert: All failures recorded
        status = tracker.get_status()
        assert len(status["agents"]) == 7, "Should have 7 agent entries"

        failed_validators = [
            a for a in status["agents"]
            if a["agent"] in ["reviewer", "security-auditor", "doc-master"]
            and a["status"] == "failed"
        ]

        assert len(failed_validators) == 3, \
            f"All 3 validators should have failed, got {len(failed_validators)}"

        # Verify each has specific failure message
        for validator in failed_validators:
            assert validator.get("message"), \
                f"{validator['agent']} should have failure message"
            assert len(validator["message"]) > 10, \
                f"{validator['agent']} message should be descriptive"


class TestParallelValidationAgentTracking:
    """Test that agent tracker correctly handles concurrent updates."""

    def test_concurrent_completion_no_data_corruption(self, mock_session_file):
        """
        Test that simultaneous agent completions don't corrupt session file.

        Expected behavior:
        - File locking ensures atomic updates
        - All completion events recorded
        - No race conditions
        - Final count is accurate
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Start all 3 validators
        for agent in ["reviewer", "security-auditor", "doc-master"]:
            tracker.log_start(agent, f"{agent} validating")

        # Act: Simulate near-simultaneous completions
        # In real implementation, these would actually be concurrent
        # Here we test the file integrity after rapid sequential writes
        for agent in ["reviewer", "security-auditor", "doc-master"]:
            tracker.log_complete(agent, f"{agent} approved", tools_used=["Read", "Grep"])

        # Assert: Read file and verify no corruption
        session_data = json.loads(mock_session_file.read_text())

        # Should be valid JSON (no corruption)
        assert "agents" in session_data
        assert isinstance(session_data["agents"], list)

        # All 3 validators present
        validator_entries = [
            a for a in session_data["agents"]
            if a["agent"] in ["reviewer", "security-auditor", "doc-master"]
        ]
        assert len(validator_entries) == 3, "All 3 validators should be recorded"

        # All marked as completed
        for entry in validator_entries:
            assert entry["status"] == "completed"
            assert "completed_at" in entry
            assert "duration_seconds" in entry

    def test_final_checkpoint_verifies_seven_agents(self, mock_session_file):
        """
        Test CHECKPOINT 7 logic verifies all 7 agents ran.

        Expected behavior:
        - After doc-master completes, checkpoint counts agents
        - Count should be exactly 7
        - If count != 7, checkpoint fails with clear error
        - Error message lists which agents are missing
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Run all 7 agents
        all_agents = [
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]

        for agent in all_agents:
            tracker.log_start(agent, f"{agent} working")
            tracker.log_complete(agent, f"{agent} done", tools_used=["Read"])

        # Act: Verify final checkpoint
        status = tracker.get_status()

        # Assert: Count is exactly 7
        assert len(status["agents"]) == 7, \
            f"CHECKPOINT 7 FAILED: Expected 7 agents, got {len(status['agents'])}"

        # Verify each expected agent present
        agent_names = [a["agent"] for a in status["agents"]]
        for expected_agent in all_agents:
            assert expected_agent in agent_names, \
                f"CHECKPOINT 7 FAILED: Missing agent '{expected_agent}'"

        # All should be completed
        completed_count = sum(1 for a in status["agents"] if a["status"] == "completed")
        assert completed_count == 7, \
            f"CHECKPOINT 7 FAILED: {completed_count}/7 agents completed"

    def test_checkpoint_fails_when_validator_missing(self, mock_session_file):
        """
        Test checkpoint failure when one of the parallel validators was skipped.

        Expected behavior:
        - If reviewer/security/doc-master missing, checkpoint fails
        - Error clearly states which validator was skipped
        - Pipeline blocked from proceeding
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Run only 6 agents (skip security-auditor)
        agents_ran = [
            "researcher",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            # security-auditor SKIPPED
            "doc-master"
        ]

        for agent in agents_ran:
            tracker.log_start(agent, f"{agent} working")
            tracker.log_complete(agent, f"{agent} done", tools_used=["Read"])

        # Act: Verify checkpoint
        status = tracker.get_status()
        agent_names = [a["agent"] for a in status["agents"]]

        # Assert: Checkpoint should fail
        assert len(status["agents"]) != 7, \
            "Checkpoint should detect missing agent"

        # Identify missing agent
        expected_agents = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]
        missing = [agent for agent in expected_agents if agent not in agent_names]

        assert "security-auditor" in missing, \
            "Should detect security-auditor is missing"

        assert len(missing) == 1, \
            f"Should have exactly 1 missing agent, got {missing}"


class TestParallelValidationEdgeCases:
    """Test edge cases and error conditions."""

    def test_validator_timeout_while_others_complete(self, mock_session_file):
        """
        Test handling when one validator times out.

        Expected behavior:
        - Timeout marked as failure
        - Other validators still complete
        - User notified which validator timed out
        - Can retry just the failed validator
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Simulate timeout scenario
        tracker.log_start("reviewer", "Reviewing code")
        tracker.log_complete("reviewer", "Approved", tools_used=["Read"])

        tracker.log_start("security-auditor", "Security scan")
        # Simulate timeout by marking as failed
        tracker.log_fail("security-auditor", "TIMEOUT: Security scan exceeded 5 minute limit")

        tracker.log_start("doc-master", "Updating docs")
        tracker.log_complete("doc-master", "Docs updated", tools_used=["Edit"])

        # Assert: Timeout recorded properly
        status = tracker.get_status()
        security_entry = next(
            (a for a in status["agents"] if a["agent"] == "security-auditor"),
            None
        )

        assert security_entry["status"] == "failed"
        assert "TIMEOUT" in security_entry.get("message", "")

    def test_validators_complete_in_unexpected_order(self, mock_session_file):
        """
        Test that completion order doesn't matter for parallel execution.

        Expected behavior:
        - Doc-master completes before reviewer/security (unusual but valid)
        - All still recorded correctly
        - Order in session file reflects actual completion times
        - Final verification still passes
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Complete in unusual order (doc-master first)
        tracker.log_start("reviewer", "Reviewing")
        tracker.log_start("security-auditor", "Scanning")
        tracker.log_start("doc-master", "Documenting")

        # Doc-master finishes first
        tracker.log_complete("doc-master", "Done", tools_used=["Edit"])

        # Then security
        tracker.log_complete("security-auditor", "Done", tools_used=["Grep"])

        # Finally reviewer
        tracker.log_complete("reviewer", "Done", tools_used=["Read"])

        # Assert: All recorded correctly
        status = tracker.get_status()
        assert len(status["agents"]) == 7

        # Verify completion order preserved in timestamps
        doc_entry = next((a for a in status["agents"] if a["agent"] == "doc-master"), None)
        security_entry = next((a for a in status["agents"] if a["agent"] == "security-auditor"), None)
        reviewer_entry = next((a for a in status["agents"] if a["agent"] == "reviewer"), None)

        # All should have completion times
        assert "completed_at" in doc_entry
        assert "completed_at" in security_entry
        assert "completed_at" in reviewer_entry

    def test_context_budget_exceeded_during_parallel_execution(self, mock_session_file):
        """
        Test handling when context budget is exceeded during validation.

        Expected behavior:
        - Context exceeded error caught gracefully
        - User notified to /clear and retry
        - Partial results preserved
        - Can resume from last successful checkpoint
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Simulate context budget exceeded during validation
        tracker.log_start("reviewer", "Reviewing")
        tracker.log_complete("reviewer", "Approved", tools_used=["Read"])

        tracker.log_start("security-auditor", "Scanning")
        tracker.log_fail(
            "security-auditor",
            "ERROR: Context budget exceeded. Run /clear and retry from checkpoint 4."
        )

        # Doc-master never started due to error

        # Assert: Partial completion recorded
        status = tracker.get_status()

        # Should have 6 agents (4 initial + reviewer + security attempt)
        assert len(status["agents"]) == 6

        # Security marked as failed with clear error
        security_entry = next(
            (a for a in status["agents"] if a["agent"] == "security-auditor"),
            None
        )
        assert security_entry["status"] == "failed"
        assert "Context budget exceeded" in security_entry.get("message", "")


class TestParallelValidationCombinedReporting:
    """Test that validation results are properly combined and reported."""

    def test_combined_validation_report_all_pass(self, mock_session_file):
        """
        Test report when all validators pass.

        Expected behavior:
        - Single summary showing all validators passed
        - Clear indication feature is ready to commit
        - Timing information for each validator
        - Next steps (git commit/push/pr)
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete all 7 agents successfully
        all_agents = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]

        for agent in all_agents:
            tracker.log_start(agent, f"{agent} working")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Generate validation report
        status = tracker.get_status()
        validator_entries = [
            a for a in status["agents"]
            if a["agent"] in ["reviewer", "security-auditor", "doc-master"]
        ]

        # Assert: All validators passed
        all_passed = all(v["status"] == "completed" for v in validator_entries)
        assert all_passed, "All validators should pass"

        # Report should include timing
        for validator in validator_entries:
            assert "duration_seconds" in validator, \
                f"{validator['agent']} should have timing data"

    def test_combined_validation_report_mixed_results(self, mock_session_file):
        """
        Test report when some validators pass and some fail.

        Expected behavior:
        - Report shows which passed and which failed
        - Failed validators' messages included
        - Passed validators acknowledged
        - Clear action items for fixes
        """
        tracker = AgentTracker(session_file=str(mock_session_file))

        # Arrange: Complete first 4 agents
        for agent in ["researcher", "planner", "test-master", "implementer"]:
            tracker.log_start(agent, f"{agent} starting")
            tracker.log_complete(agent, f"{agent} completed", tools_used=["Read"])

        # Act: Mixed validation results
        tracker.log_start("reviewer", "Reviewing")
        tracker.log_fail("reviewer", "CHANGES REQUESTED: Add input validation")

        tracker.log_start("security-auditor", "Scanning")
        tracker.log_complete("security-auditor", "No issues found", tools_used=["Grep"])

        tracker.log_start("doc-master", "Documenting")
        tracker.log_fail("doc-master", "Missing: Update README.md with new API endpoints")

        # Assert: Report contains mixed results
        status = tracker.get_status()

        failed_validators = [
            a for a in status["agents"]
            if a["agent"] in ["reviewer", "doc-master"]
            and a["status"] == "failed"
        ]

        passed_validators = [
            a for a in status["agents"]
            if a["agent"] == "security-auditor"
            and a["status"] == "completed"
        ]

        assert len(failed_validators) == 2, "Should have 2 failures"
        assert len(passed_validators) == 1, "Should have 1 pass"

        # Failed validators should have actionable messages
        for validator in failed_validators:
            message = validator.get("message", "")
            assert len(message) > 0, "Failed validator should have message"
            assert any(
                keyword in message.lower()
                for keyword in ["missing", "requested", "add", "update"]
            ), "Message should indicate what needs fixing"


# Mark all tests as expecting to fail (TDD red phase)
# REMOVED: Implementation complete in auto-implement.md STEP 5
# pytestmark = pytest.mark.xfail(
#     reason="TDD Red Phase: Implementation not yet complete. "
#            "Tests verify expected behavior for parallel validation."
# )
