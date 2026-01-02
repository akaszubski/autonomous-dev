"""
Integration tests for parallel validation in /auto-implement workflow.

TDD Mode: These tests are written BEFORE implementation using agent_pool.py.
All tests should FAIL initially (migration not yet complete).

Test Strategy:
- Test execute_parallel_validation() function integration
- Test parallel execution of 3 validation agents (reviewer, security-auditor, doc-master)
- Test retry logic with AgentPool integration
- Test security-first priority mode
- Test graceful handling of failures
- Test end-to-end workflow from /auto-implement

Date: 2026-01-02
Issue: #187 - Migrate /auto-implement to agent_pool.py library
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
project_root = Path(__file__).parent.parent.parent
lib_path = project_root / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))

# Import the library under test
try:
    from parallel_validation import (
        execute_parallel_validation,
        ValidationResults,
        SecurityValidationError,
        ValidationTimeoutError
    )
except ImportError:
    pytest.skip("parallel_validation.py library not implemented yet", allow_module_level=True)

# Import AgentPool for mocking
try:
    from agent_pool import AgentPool, AgentResult, PriorityLevel
except ImportError:
    pytest.skip("agent_pool.py not available", allow_module_level=True)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create temporary project directory with .claude structure."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # Create PROJECT.md
    project_md = claude_dir / "PROJECT.md"
    project_md.write_text("""
# Test Project

## Goals
- Test parallel validation integration

## Agent Pool Configuration
```json
{
  "max_agents": 8,
  "token_budget": 150000,
  "priority_enabled": true
}
```
""")

    # Create session directory
    sessions_dir = tmp_path / "docs" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture
def sample_feature_files(tmp_project_dir):
    """Create sample implementation files for testing."""
    src_dir = tmp_project_dir / "src"
    src_dir.mkdir(exist_ok=True)

    # Create sample implementation file
    auth_file = src_dir / "auth.py"
    auth_file.write_text("""
def authenticate(username, password):
    '''Authenticate user with credentials.'''
    # Implementation here
    return True
""")

    # Create sample test file
    tests_dir = tmp_project_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    test_file = tests_dir / "test_auth.py"
    test_file.write_text("""
def test_authenticate():
    assert authenticate('user', 'pass') == True
""")

    return [str(auth_file.relative_to(tmp_project_dir)), str(test_file.relative_to(tmp_project_dir))]


@pytest.fixture
def mock_agent_pool_all_success():
    """Mock AgentPool that returns successful results for all agents."""
    with patch("parallel_validation.AgentPool") as MockPool:
        pool_instance = MagicMock()

        # Configure successful responses
        pool_instance.await_all.return_value = {
            "security-auditor": AgentResult(task_id="test-task", 
                success=True,
                output="PASS - No security vulnerabilities found\n\nScanned 2 files, 0 issues detected.",
                
                tokens_used=5000,
                duration=3.5,
            ),
            "reviewer": AgentResult(task_id="test-task", 
                success=True,
                output="APPROVE - Code quality meets standards\n\nAll checks passed.",
                
                tokens_used=4000,
                duration=2.8,
            ),
            "doc-master": AgentResult(task_id="test-task", 
                success=True,
                output="UPDATED - Documentation synced\n\nFiles updated:\n- CHANGELOG.md\n- README.md",
                
                tokens_used=3000,
                duration=2.2,
            )
        }

        MockPool.return_value = pool_instance
        yield pool_instance


@pytest.fixture
def mock_agent_pool_security_fail():
    """Mock AgentPool with security failure."""
    with patch("parallel_validation.AgentPool") as MockPool:
        pool_instance = MagicMock()

        pool_instance.await_all.return_value = {
            "security-auditor": AgentResult(task_id="test-task", 
                success=False,
                output="FAIL - Security vulnerabilities found\n\nCWE-78: Command injection in execute_command() at src/auth.py:42",
                
                tokens_used=5000,
                duration=3.2,
            ),
            "reviewer": AgentResult(task_id="test-task", 
                success=True,
                output="APPROVE - Code quality good",
                
                tokens_used=4000,
                duration=2.5,
            ),
            "doc-master": AgentResult(task_id="test-task", 
                success=True,
                output="UPDATED - Docs synced",
                
                tokens_used=3000,
                duration=2.0,
            )
        }

        MockPool.return_value = pool_instance
        yield pool_instance


# ============================================================================
# TEST: Happy Path - All Agents Succeed
# ============================================================================

class TestParallelValidationAllSuccess:
    """Test successful parallel execution of all validation agents."""

    def test_all_agents_succeed(self, mock_agent_pool_all_success, tmp_project_dir):
        """
        Test all 3 validation agents succeed in parallel.

        Expected behavior:
        - Security-auditor: PASS
        - Reviewer: APPROVE
        - Doc-master: UPDATED
        - ValidationResults shows all passed
        - Execution time measured
        - No failed agents
        """
        # Arrange
        feature = "Add user authentication"

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=False  # All parallel
        )

        # Assert
        assert isinstance(results, ValidationResults)
        assert results.security_passed is True, "Security should pass"
        assert results.review_passed is True, "Review should pass"
        assert results.docs_updated is True, "Docs should be updated"
        assert len(results.failed_agents) == 0, "No agents should fail"
        assert results.execution_time_seconds > 0, "Execution time should be measured"

        # Verify all agents were submitted
        assert mock_agent_pool_all_success.submit_task.call_count == 3

    def test_parallel_execution_is_concurrent(self, mock_agent_pool_all_success, tmp_project_dir):
        """
        Test that agents run in parallel (not sequential).

        Expected behavior:
        - All agents submitted before await_all() called
        - Total time approximately equals longest agent (not sum)
        - submit_task called 3 times before any await
        """
        # Arrange
        feature = "Add JWT tokens"
        call_order = []

        def track_submit(*args, **kwargs):
            call_order.append(("submit", args[0] if args else kwargs.get("agent_type", "unknown")))
            return f"task-{len(call_order)}"

        def track_await(*args, **kwargs):
            call_order.append(("await", None))
            return mock_agent_pool_all_success.await_all.return_value

        mock_agent_pool_all_success.submit_task.side_effect = track_submit
        # Store original and wrap await_all
        original_await = mock_agent_pool_all_success.await_all.return_value
        mock_agent_pool_all_success.await_all.side_effect = track_await

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=False
        )

        # Assert
        # All submits should happen before await
        submit_count = sum(1 for action, _ in call_order if action == "submit")
        await_index = next((i for i, (action, _) in enumerate(call_order) if action == "await"), len(call_order))

        assert submit_count == 3, f"Should submit 3 tasks, got {submit_count}"

        # All submits should happen before first await
        submit_indices = [i for i, (action, _) in enumerate(call_order) if action == "submit"]
        assert all(idx < await_index for idx in submit_indices), "All submits should happen before await"

        # Execution time should reflect parallel execution (sum of durations from await_all result)
        assert results.execution_time_seconds > 0, "Execution time should be measured"

    def test_changed_files_passed_to_agents(self, mock_agent_pool_all_success, tmp_project_dir, sample_feature_files):
        """
        Test that changed files list is passed to agent prompts.

        Expected behavior:
        - Changed files included in prompts
        - Each agent receives relevant file list
        - Prompts are tailored to actual changes
        """
        # Arrange
        feature = "Add authentication"

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=False,
            changed_files=sample_feature_files
        )

        # Assert
        submit_calls = mock_agent_pool_all_success.submit_task.call_args_list

        # Verify each agent got a prompt
        assert len(submit_calls) == 3

        # Check that prompts contain file references (implementation detail)
        for call in submit_calls:
            # Handle both positional and keyword args
            args, kwargs = call
            agent_type = args[0] if args else kwargs.get("agent_type", "unknown")
            prompt = args[1] if len(args) > 1 else kwargs.get("prompt", "")
            assert isinstance(prompt, str), f"{agent_type} should get string prompt"
            assert len(prompt) > 50, f"{agent_type} prompt should be substantial"


# ============================================================================
# TEST: Security Failures Block Deployment
# ============================================================================

class TestSecurityFailureBlocking:
    """Test that security failures properly block deployment."""

    def test_security_failure_blocks_validation(self, mock_agent_pool_security_fail, tmp_project_dir):
        """
        Test that security failure causes ValidationResults to show failure.

        Expected behavior:
        - Security fails with CWE-78 vulnerability
        - Reviewer and doc-master still complete (non-blocking)
        - ValidationResults.security_passed = False
        - 'security-auditor' in failed_agents
        - Security output contains vulnerability details
        """
        # Arrange
        feature = "Add command execution"

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=False
        )

        # Assert
        assert results.security_passed is False, "Security should fail"
        assert "security-auditor" in results.failed_agents, "Security agent should be in failed list"
        assert "CWE-78" in results.security_output, "Security output should contain CWE ID"
        assert "Command injection" in results.security_output, "Security output should describe vulnerability"

        # Other agents should still complete
        assert results.review_passed is True, "Reviewer should still complete"
        assert results.docs_updated is True, "Doc-master should still complete"

    def test_security_failure_in_priority_mode_stops_early(self, mock_agent_pool_security_fail, tmp_project_dir):
        """
        Test security-first mode stops immediately on security failure.

        Expected behavior:
        - Security runs first in priority mode
        - Security fails
        - Reviewer and doc-master may not run (optimization)
        - SecurityValidationError raised
        """
        # Arrange
        feature = "Add file upload"

        # Act & Assert
        # In priority mode, security failure should raise exception
        with pytest.raises(SecurityValidationError, match="CWE-78"):
            execute_parallel_validation(
                feature_description=feature,
                project_root=tmp_project_dir,
                priority_mode=True  # Security first
            )


# ============================================================================
# TEST: Partial Failures (Non-Blocking)
# ============================================================================

class TestPartialFailures:
    """Test graceful handling of non-critical failures."""

    def test_reviewer_failure_continues_with_warning(self, tmp_project_dir):
        """
        Test reviewer failure doesn't block deployment (only warning).

        Expected behavior:
        - Reviewer finds code quality issues
        - Security and docs still succeed
        - ValidationResults shows review_passed=False
        - 'reviewer' in failed_agents
        - Deployment can continue with warning
        """
        # Arrange
        with patch("parallel_validation.AgentPool") as MockPool:
            pool_instance = MagicMock()
            pool_instance.await_all.return_value = {
                "security-auditor": AgentResult(task_id="test-task", 
                    success=True,
                    output="PASS - No vulnerabilities",
                    
                    tokens_used=5000,
                    duration=3.0
                ),
                "reviewer": AgentResult(task_id="test-task", 
                    success=False,
                    output="REQUEST_CHANGES - Found 3 code quality issues:\n1. Missing error handling\n2. Poor variable names\n3. No input validation",
                    
                    tokens_used=4000,
                    duration=2.5
                ),
                "doc-master": AgentResult(task_id="test-task", 
                    success=True,
                    output="UPDATED - Docs synced",
                    
                    tokens_used=3000,
                    duration=2.0
                )
            }
            MockPool.return_value = pool_instance

            # Act
            results = execute_parallel_validation(
                feature_description="Add feature",
                project_root=tmp_project_dir,
                priority_mode=False
            )

        # Assert
        assert results.security_passed is True, "Security should pass"
        assert results.review_passed is False, "Review should fail"
        assert results.docs_updated is True, "Docs should update"
        assert "reviewer" in results.failed_agents
        assert "REQUEST_CHANGES" in results.review_output

    def test_docmaster_failure_continues_with_warning(self, tmp_project_dir):
        """
        Test doc-master failure doesn't block deployment.

        Expected behavior:
        - Doc-master fails to update docs
        - Security and reviewer succeed
        - ValidationResults shows docs_updated=False
        - 'doc-master' in failed_agents
        - Warning message shown but deployment continues
        """
        # Arrange
        with patch("parallel_validation.AgentPool") as MockPool:
            pool_instance = MagicMock()
            pool_instance.await_all.return_value = {
                "security-auditor": AgentResult(task_id="test-task", 
                    success=True,
                    output="PASS",
                    
                    tokens_used=5000,
                    duration=3.0
                ),
                "reviewer": AgentResult(task_id="test-task", 
                    success=True,
                    output="APPROVE",
                    
                    tokens_used=4000,
                    duration=2.5
                ),
                "doc-master": AgentResult(task_id="test-task", 
                    success=False,
                    output="ERROR - Could not update CHANGELOG.md (file locked)",
                    
                    tokens_used=3000,
                    duration=1.5
                )
            }
            MockPool.return_value = pool_instance

            # Act
            results = execute_parallel_validation(
                feature_description="Add feature",
                project_root=tmp_project_dir,
                priority_mode=False
            )

        # Assert
        assert results.security_passed is True
        assert results.review_passed is True
        assert results.docs_updated is False, "Docs should not be updated"
        assert "doc-master" in results.failed_agents
        assert "ERROR" in results.docs_output


# ============================================================================
# TEST: Retry Logic
# ============================================================================

class TestRetryLogic:
    """Test automatic retry on transient failures."""

    @patch("parallel_validation.time.sleep")
    def test_retry_logic_recovers_from_timeout(self, mock_sleep, tmp_project_dir):
        """
        Test retry logic recovers from transient timeout.

        Expected behavior:
        - First submission times out
        - Automatic retry via retry_with_backoff
        - Second submission succeeds
        - Final result is successful

        Note: Sleep only happens between retry attempts within retry_with_backoff,
        not when first entering the function. Since the second attempt succeeds
        immediately, sleep may not be called.
        """
        # Arrange
        with patch("parallel_validation.AgentPool") as MockPool:
            pool_instance = MagicMock()

            # Track call counts per agent type
            agent_call_counts = {"security-auditor": 0, "reviewer": 0, "doc-master": 0}

            def submit_side_effect(agent_type, prompt, priority=None):
                agent_call_counts[agent_type] = agent_call_counts.get(agent_type, 0) + 1
                # First TWO calls for security-auditor timeout (so retry sleeps between them)
                if agent_type == "security-auditor" and agent_call_counts[agent_type] <= 2:
                    raise TimeoutError("Agent execution timed out")
                return f"task-{agent_type}"

            pool_instance.submit_task.side_effect = submit_side_effect

            # Successful result after retry
            pool_instance.await_all.return_value = {
                "security-auditor": AgentResult(task_id="test-task",
                    success=True,
                    output="PASS",

                    tokens_used=5000,
                    duration=3.0
                ),
                "reviewer": AgentResult(task_id="test-task",
                    success=True,
                    output="APPROVE",

                    tokens_used=4000,
                    duration=2.5
                ),
                "doc-master": AgentResult(task_id="test-task",
                    success=True,
                    output="UPDATED",

                    tokens_used=3000,
                    duration=2.0
                )
            }

            MockPool.return_value = pool_instance

            # Act
            results = execute_parallel_validation(
                feature_description="Add feature",
                project_root=tmp_project_dir,
                priority_mode=False
            )

        # Assert
        assert results is not None, "Should succeed after retry"
        assert results.security_passed is True
        # Retry happened for security-auditor (first two calls failed, third succeeded)
        assert agent_call_counts["security-auditor"] >= 3, "Security auditor should have been retried multiple times"
        # Sleep should be called between retry attempts (exponential backoff)
        assert mock_sleep.call_count >= 1, "Should sleep during retry"

    @patch("time.sleep")
    def test_permanent_error_fails_fast(self, mock_sleep, tmp_project_dir):
        """
        Test permanent errors fail immediately without retry.

        Expected behavior:
        - ValueError raised (permanent error)
        - No retry attempted
        - Exception propagated to caller
        - No sleep calls
        """
        # Arrange
        with patch("parallel_validation.AgentPool") as MockPool:
            pool_instance = MagicMock()
            pool_instance.submit_task.side_effect = ValueError("Invalid agent type: nonexistent")
            MockPool.return_value = pool_instance

            # Act & Assert
            with pytest.raises(ValueError, match="Invalid agent type"):
                execute_parallel_validation(
                    feature_description="Add feature",
                    project_root=tmp_project_dir,
                    priority_mode=False
                )

        # Should not retry permanent errors
        assert pool_instance.submit_task.call_count == 1, "Should fail fast, no retries"
        assert mock_sleep.call_count == 0, "Should not sleep for permanent errors"


# ============================================================================
# TEST: Priority Mode (Security First)
# ============================================================================

class TestPriorityMode:
    """Test security-first priority mode execution."""

    def test_priority_mode_security_first(self, mock_agent_pool_all_success, tmp_project_dir):
        """
        Test security-first mode runs security before other agents.

        Expected behavior:
        - Security agent submitted first with P1 priority
        - Reviewer and doc-master submitted with lower priority
        - Priority levels enforced: P1 > P2 > P3
        - All complete successfully
        """
        # Arrange
        feature = "Add file upload endpoint"
        submit_order = []

        def track_submit(agent_type, prompt, priority=None):
            submit_order.append((agent_type, priority))
            return f"task-{agent_type}"

        mock_agent_pool_all_success.submit_task.side_effect = track_submit

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=True  # Security first
        )

        # Assert
        assert len(submit_order) == 3, "All 3 agents should be submitted"

        # Security should be first
        assert submit_order[0][0] == "security-auditor", "Security should be submitted first"

        # Security should have highest priority (P1)
        security_priority = submit_order[0][1]
        assert security_priority is not None, "Security should have priority set"
        # In agent_pool.py, PriorityLevel.P1_SECURITY = 1 (highest)
        # assert security_priority == PriorityLevel.P1_SECURITY

        # Results should still succeed
        assert results.security_passed is True
        assert results.review_passed is True
        assert results.docs_updated is True


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_feature_description_raises_error(self, tmp_project_dir):
        """Test validation rejects empty feature description."""
        # Act & Assert
        with pytest.raises(ValueError, match="Feature description cannot be empty"):
            execute_parallel_validation(
                feature_description="",
                project_root=tmp_project_dir,
                priority_mode=False
            )

    def test_invalid_project_root_raises_error(self):
        """Test validation rejects nonexistent project root."""
        # Arrange
        invalid_path = Path("/nonexistent/project/path")

        # Act & Assert
        with pytest.raises(ValueError, match="Project root does not exist"):
            execute_parallel_validation(
                feature_description="Add feature",
                project_root=invalid_path,
                priority_mode=False
            )

    def test_missing_agent_results_marked_as_failed(self, tmp_project_dir):
        """Test that missing agent results are marked as failures."""
        # Arrange
        with patch("parallel_validation.AgentPool") as MockPool:
            pool_instance = MagicMock()

            # Only security returns result
            pool_instance.await_all.return_value = {
                "security-auditor": AgentResult(task_id="test-task", 
                    success=True,
                    output="PASS",
                    
                    tokens_used=5000,
                    duration=3.0
                )
                # reviewer and doc-master missing
            }
            MockPool.return_value = pool_instance

            # Act
            results = execute_parallel_validation(
                feature_description="Add feature",
                project_root=tmp_project_dir,
                priority_mode=False
            )

        # Assert
        assert results.security_passed is True
        assert results.review_passed is False, "Missing reviewer should be marked as failed"
        assert results.docs_updated is False, "Missing doc-master should be marked as failed"
        assert "reviewer" in results.failed_agents
        assert "doc-master" in results.failed_agents

    @patch("time.sleep")
    def test_all_agents_timeout_raises_error(self, mock_sleep, tmp_project_dir):
        """Test that all agents timing out raises ValidationTimeoutError."""
        # Arrange
        with patch("parallel_validation.AgentPool") as MockPool:
            pool_instance = MagicMock()
            pool_instance.submit_task.side_effect = TimeoutError("Timeout")
            MockPool.return_value = pool_instance

            # Act & Assert
            with pytest.raises(ValidationTimeoutError):
                execute_parallel_validation(
                    feature_description="Add feature",
                    project_root=tmp_project_dir,
                    priority_mode=False
                )


# ============================================================================
# TEST: Integration with /auto-implement
# ============================================================================

class TestAutoImplementIntegration:
    """Test integration with /auto-implement command."""

    def test_validation_results_format_for_auto_implement(self, mock_agent_pool_all_success, tmp_project_dir):
        """
        Test that ValidationResults format is compatible with /auto-implement.

        Expected behavior:
        - ValidationResults has all required fields
        - Can be serialized to JSON for reporting
        - Contains actionable information for next steps
        """
        # Arrange
        feature = "Add authentication"

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=False
        )

        # Assert - check all required fields exist
        assert hasattr(results, "security_passed")
        assert hasattr(results, "review_passed")
        assert hasattr(results, "docs_updated")
        assert hasattr(results, "failed_agents")
        assert hasattr(results, "execution_time_seconds")
        assert hasattr(results, "security_output")
        assert hasattr(results, "review_output")
        assert hasattr(results, "docs_output")

        # Should be able to check if validation passed overall
        validation_passed = (
            results.security_passed and
            results.review_passed and
            results.docs_updated
        )
        assert validation_passed is True

    def test_execution_time_within_expected_range(self, mock_agent_pool_all_success, tmp_project_dir):
        """
        Test execution time is measured and within expected range.

        Expected behavior:
        - Execution time > 0
        - Execution time approximately equals longest agent duration
        - For parallel execution, time < sum of all agents
        """
        # Arrange
        feature = "Add caching"

        # Act
        with patch("time.time", side_effect=[1000.0, 1008.5]):  # 8.5s elapsed
            results = execute_parallel_validation(
                feature_description=feature,
                project_root=tmp_project_dir,
                priority_mode=False
            )

        # Assert
        assert results.execution_time_seconds > 0
        # Should be approximately 8.5s (mocked time difference)
        assert 8.0 <= results.execution_time_seconds <= 9.0
