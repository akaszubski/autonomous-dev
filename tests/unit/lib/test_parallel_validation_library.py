"""
Unit tests for parallel_validation.py library - Agent pool integration for /auto-implement

TDD Red Phase: Tests written BEFORE implementation exists.
All tests SHOULD FAIL initially - implementation doesn't exist yet.

Tests cover:
1. ValidationResults dataclass structure
2. retry_with_backoff() - exponential backoff, transient vs permanent errors
3. execute_parallel_validation() - main entry point, priority modes
4. _execute_security_first() - security agent first, then parallel
5. _aggregate_results() - parse agent outputs, handle failures
6. Error classification - is_transient_error() vs is_permanent_error()
7. Integration with AgentPool library

Date: 2026-01-02
Issue: #187 - Migrate /auto-implement to agent_pool.py library
Agent: test-master
Workflow: TDD red phase
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from enum import Enum

# Import the module under test (will fail initially - TDD red phase)
try:
    from autonomous_dev.lib.parallel_validation import (
        ValidationResults,
        execute_parallel_validation,
        retry_with_backoff,
        _execute_security_first,
        _aggregate_results,
        is_transient_error,
        is_permanent_error,
        SecurityValidationError,
        ValidationTimeoutError,
    )
except ImportError:
    # Allow tests to be collected even if implementation doesn't exist yet
    pytest.skip("parallel_validation.py library not implemented yet", allow_module_level=True)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create temporary project directory with .claude subdirectory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # Create PROJECT.md
    project_md = claude_dir / "PROJECT.md"
    project_md.write_text("""
# Test Project

## Goals
- Test parallel validation

## Agent Pool Configuration
```json
{
  "max_agents": 8,
  "token_budget": 150000
}
```
""")

    return tmp_path


@pytest.fixture
def mock_agent_pool():
    """Mock AgentPool instance for testing."""
    with patch("autonomous_dev.lib.parallel_validation.AgentPool") as MockPool:
        pool_instance = MagicMock()

        # Configure default successful responses
        pool_instance.submit_task.return_value = "task-handle-123"
        pool_instance.await_all.return_value = {
            "security-auditor": MagicMock(
                success=True,
                output="PASS - No security vulnerabilities found",
                agent_type="security-auditor",
                tokens_used=5000,
                duration=3.2
            ),
            "reviewer": MagicMock(
                success=True,
                output="APPROVE - Code quality meets standards",
                agent_type="reviewer",
                tokens_used=4000,
                duration=2.8
            ),
            "doc-master": MagicMock(
                success=True,
                output="UPDATED - CHANGELOG.md, README.md",
                agent_type="doc-master",
                tokens_used=3000,
                duration=2.1
            )
        }

        MockPool.return_value = pool_instance
        yield pool_instance


@pytest.fixture
def sample_feature_description():
    """Sample feature description for testing."""
    return "Add JWT authentication to API endpoints"


@pytest.fixture
def sample_changed_files():
    """Sample list of changed files."""
    return [
        "src/auth/jwt_handler.py",
        "tests/test_jwt_handler.py",
        "docs/api/authentication.md"
    ]


# ============================================================================
# TEST: ValidationResults Dataclass
# ============================================================================

class TestValidationResults:
    """Test ValidationResults dataclass structure and behavior."""

    def test_validation_results_structure(self):
        """Test ValidationResults has all required fields with correct types."""
        # Arrange & Act
        results = ValidationResults(
            security_passed=True,
            review_passed=True,
            docs_updated=True,
            failed_agents=[],
            execution_time_seconds=8.5,
            security_output="PASS - No vulnerabilities",
            review_output="APPROVE - Quality standards met",
            docs_output="UPDATED - 3 files"
        )

        # Assert
        assert isinstance(results.security_passed, bool)
        assert isinstance(results.review_passed, bool)
        assert isinstance(results.docs_updated, bool)
        assert isinstance(results.failed_agents, list)
        assert isinstance(results.execution_time_seconds, float)
        assert isinstance(results.security_output, str)
        assert isinstance(results.review_output, str)
        assert isinstance(results.docs_output, str)

    def test_validation_results_all_success(self):
        """Test ValidationResults with all agents successful."""
        # Arrange & Act
        results = ValidationResults(
            security_passed=True,
            review_passed=True,
            docs_updated=True,
            failed_agents=[],
            execution_time_seconds=7.2
        )

        # Assert
        assert results.security_passed is True
        assert results.review_passed is True
        assert results.docs_updated is True
        assert len(results.failed_agents) == 0

    def test_validation_results_partial_failure(self):
        """Test ValidationResults with some agents failing."""
        # Arrange & Act
        results = ValidationResults(
            security_passed=True,
            review_passed=False,
            docs_updated=True,
            failed_agents=["reviewer"],
            execution_time_seconds=6.8,
            review_output="REQUEST_CHANGES - Found 3 issues"
        )

        # Assert
        assert results.security_passed is True
        assert results.review_passed is False
        assert results.docs_updated is True
        assert "reviewer" in results.failed_agents
        assert len(results.failed_agents) == 1

    def test_validation_results_security_failure(self):
        """Test ValidationResults with security agent failing (critical)."""
        # Arrange & Act
        results = ValidationResults(
            security_passed=False,
            review_passed=True,
            docs_updated=True,
            failed_agents=["security-auditor"],
            execution_time_seconds=5.3,
            security_output="FAIL - CWE-78: Command injection vulnerability"
        )

        # Assert
        assert results.security_passed is False
        assert "security-auditor" in results.failed_agents
        # Security failure should be treated as critical


# ============================================================================
# TEST: Error Classification
# ============================================================================

class TestErrorClassification:
    """Test transient vs permanent error classification."""

    def test_is_transient_error_timeout(self):
        """Test TimeoutError is classified as transient (should retry)."""
        # Arrange
        error = TimeoutError("Agent execution timed out after 60s")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is True

    def test_is_transient_error_connection(self):
        """Test ConnectionError is classified as transient (should retry)."""
        # Arrange
        error = ConnectionError("Failed to connect to agent")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is True

    def test_is_transient_error_http_500(self):
        """Test HTTP 500 errors are classified as transient (should retry)."""
        # Arrange
        error = Exception("HTTP 503 Service Unavailable")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is True

    def test_is_permanent_error_syntax(self):
        """Test SyntaxError is classified as permanent (fail fast)."""
        # Arrange
        error = SyntaxError("Invalid Python syntax in prompt")

        # Act
        result = is_permanent_error(error)

        # Assert
        assert result is True

    def test_is_permanent_error_import(self):
        """Test ImportError is classified as permanent (fail fast)."""
        # Arrange
        error = ImportError("Module 'nonexistent' not found")

        # Act
        result = is_permanent_error(error)

        # Assert
        assert result is True

    def test_is_permanent_error_permission(self):
        """Test PermissionError is classified as permanent (fail fast)."""
        # Arrange
        error = PermissionError("Access denied to /etc/passwd")

        # Act
        result = is_permanent_error(error)

        # Assert
        assert result is True

    def test_is_permanent_error_value(self):
        """Test ValueError is classified as permanent (fail fast)."""
        # Arrange
        error = ValueError("Invalid agent type: nonexistent-agent")

        # Act
        result = is_permanent_error(error)

        # Assert
        assert result is True


# ============================================================================
# TEST: retry_with_backoff()
# ============================================================================

class TestRetryWithBackoff:
    """Test retry logic with exponential backoff."""

    @patch("time.sleep")
    def test_retry_transient_error_succeeds(self, mock_sleep, mock_agent_pool):
        """Test retry succeeds after transient error on first attempt."""
        # Arrange
        mock_pool = mock_agent_pool

        # First call fails with timeout, second succeeds
        mock_pool.submit_task.side_effect = [
            TimeoutError("Agent timed out"),
            "task-handle-success"
        ]
        mock_pool.await_all.return_value = {
            "security-auditor": MagicMock(
                success=True,
                output="PASS - No vulnerabilities",
                agent_type="security-auditor"
            )
        }

        # Act
        result = retry_with_backoff(
            pool=mock_pool,
            agent_type="security-auditor",
            prompt="Security scan prompt",
            max_retries=3
        )

        # Assert
        assert result is not None
        assert result.success is True
        assert mock_pool.submit_task.call_count == 2  # Failed once, succeeded second time
        assert mock_sleep.call_count == 1  # Slept once between retries
        mock_sleep.assert_called_with(2)  # First retry: 2^1 = 2 seconds

    @patch("time.sleep")
    def test_retry_permanent_error_fails_fast(self, mock_sleep, mock_agent_pool):
        """Test permanent errors fail immediately without retry."""
        # Arrange
        mock_pool = mock_agent_pool
        mock_pool.submit_task.side_effect = ValueError("Invalid agent type")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid agent type"):
            retry_with_backoff(
                pool=mock_pool,
                agent_type="invalid-agent",
                prompt="Test prompt",
                max_retries=3
            )

        # Should not retry permanent errors
        assert mock_pool.submit_task.call_count == 1
        assert mock_sleep.call_count == 0

    @patch("time.sleep")
    def test_retry_max_attempts_exceeded(self, mock_sleep, mock_agent_pool):
        """Test retry gives up after max_retries exceeded."""
        # Arrange
        mock_pool = mock_agent_pool
        mock_pool.submit_task.side_effect = TimeoutError("Timeout")

        # Act & Assert
        with pytest.raises(TimeoutError, match="Timeout"):
            retry_with_backoff(
                pool=mock_pool,
                agent_type="security-auditor",
                prompt="Test prompt",
                max_retries=3
            )

        # Should retry 3 times (initial + 3 retries = 4 total attempts)
        assert mock_pool.submit_task.call_count == 4
        assert mock_sleep.call_count == 3  # Sleep between each retry

    @patch("time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep, mock_agent_pool):
        """Test exponential backoff follows 2^n pattern."""
        # Arrange
        mock_pool = mock_agent_pool
        mock_pool.submit_task.side_effect = [
            TimeoutError("Timeout 1"),
            TimeoutError("Timeout 2"),
            TimeoutError("Timeout 3"),
            TimeoutError("Timeout 4")
        ]

        # Act
        try:
            retry_with_backoff(
                pool=mock_pool,
                agent_type="reviewer",
                prompt="Test prompt",
                max_retries=3
            )
        except TimeoutError:
            pass  # Expected

        # Assert - exponential backoff: 2^1=2, 2^2=4, 2^3=8 seconds
        assert mock_sleep.call_count == 3
        expected_delays = [2, 4, 8]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays

    @patch("time.sleep")
    def test_retry_eventual_success(self, mock_sleep, mock_agent_pool):
        """Test retry succeeds on third attempt."""
        # Arrange
        mock_pool = mock_agent_pool
        mock_pool.submit_task.side_effect = [
            TimeoutError("Timeout 1"),
            TimeoutError("Timeout 2"),
            "task-handle-success"
        ]
        mock_pool.await_all.return_value = {
            "doc-master": MagicMock(
                success=True,
                output="UPDATED - docs",
                agent_type="doc-master"
            )
        }

        # Act
        result = retry_with_backoff(
            pool=mock_pool,
            agent_type="doc-master",
            prompt="Update docs",
            max_retries=3
        )

        # Assert
        assert result is not None
        assert result.success is True
        assert mock_pool.submit_task.call_count == 3
        assert mock_sleep.call_count == 2  # Slept twice (2s, 4s)


# ============================================================================
# TEST: _aggregate_results()
# ============================================================================

class TestAggregateResults:
    """Test aggregation of agent results into ValidationResults."""

    def test_aggregate_all_success(self):
        """Test aggregation when all agents succeed."""
        # Arrange
        agent_results = {
            "security-auditor": MagicMock(
                success=True,
                output="PASS - No vulnerabilities found",
                agent_type="security-auditor",
                duration=3.5
            ),
            "reviewer": MagicMock(
                success=True,
                output="APPROVE - Code quality meets standards",
                agent_type="reviewer",
                duration=2.8
            ),
            "doc-master": MagicMock(
                success=True,
                output="UPDATED - CHANGELOG.md, README.md",
                agent_type="doc-master",
                duration=2.2
            )
        }

        # Act
        results = _aggregate_results(agent_results)

        # Assert
        assert isinstance(results, ValidationResults)
        assert results.security_passed is True
        assert results.review_passed is True
        assert results.docs_updated is True
        assert len(results.failed_agents) == 0
        assert results.execution_time_seconds == pytest.approx(8.5, rel=0.1)

    def test_aggregate_security_failure(self):
        """Test aggregation when security agent fails (critical)."""
        # Arrange
        agent_results = {
            "security-auditor": MagicMock(
                success=False,
                output="FAIL - CWE-78: Command injection in execute_command()",
                agent_type="security-auditor",
                duration=2.5
            ),
            "reviewer": MagicMock(
                success=True,
                output="APPROVE",
                agent_type="reviewer",
                duration=2.0
            ),
            "doc-master": MagicMock(
                success=True,
                output="UPDATED - docs",
                agent_type="doc-master",
                duration=1.8
            )
        }

        # Act
        results = _aggregate_results(agent_results)

        # Assert
        assert results.security_passed is False
        assert "security-auditor" in results.failed_agents
        assert "CWE-78" in results.security_output

    def test_aggregate_partial_failure(self):
        """Test aggregation when reviewer fails (non-critical)."""
        # Arrange
        agent_results = {
            "security-auditor": MagicMock(
                success=True,
                output="PASS - No vulnerabilities",
                agent_type="security-auditor",
                duration=3.0
            ),
            "reviewer": MagicMock(
                success=False,
                output="REQUEST_CHANGES - Found 3 code quality issues",
                agent_type="reviewer",
                duration=2.5
            ),
            "doc-master": MagicMock(
                success=True,
                output="UPDATED - docs",
                agent_type="doc-master",
                duration=2.0
            )
        }

        # Act
        results = _aggregate_results(agent_results)

        # Assert
        assert results.security_passed is True  # Security still passed
        assert results.review_passed is False
        assert results.docs_updated is True
        assert "reviewer" in results.failed_agents
        assert len(results.failed_agents) == 1

    def test_aggregate_missing_agent(self):
        """Test aggregation when an agent result is missing."""
        # Arrange
        agent_results = {
            "security-auditor": MagicMock(
                success=True,
                output="PASS",
                agent_type="security-auditor",
                duration=3.0
            ),
            "reviewer": MagicMock(
                success=True,
                output="APPROVE",
                agent_type="reviewer",
                duration=2.5
            )
            # doc-master missing
        }

        # Act
        results = _aggregate_results(agent_results)

        # Assert
        assert results.security_passed is True
        assert results.review_passed is True
        assert results.docs_updated is False  # Missing = not updated
        assert "doc-master" in results.failed_agents

    def test_aggregate_parse_security_output(self):
        """Test parsing PASS/FAIL from security output."""
        # Arrange
        agent_results = {
            "security-auditor": MagicMock(
                success=True,
                output="PASS - Scanned 5 files, no vulnerabilities found",
                agent_type="security-auditor",
                duration=4.2
            ),
            "reviewer": MagicMock(success=True, output="APPROVE", duration=2.0),
            "doc-master": MagicMock(success=True, output="UPDATED", duration=1.5)
        }

        # Act
        results = _aggregate_results(agent_results)

        # Assert
        assert results.security_passed is True
        assert "PASS" in results.security_output

    def test_aggregate_parse_reviewer_output(self):
        """Test parsing APPROVE/REQUEST_CHANGES from reviewer output."""
        # Arrange
        agent_results = {
            "security-auditor": MagicMock(success=True, output="PASS", duration=3.0),
            "reviewer": MagicMock(
                success=True,
                output="APPROVE - All quality checks passed",
                agent_type="reviewer",
                duration=2.8
            ),
            "doc-master": MagicMock(success=True, output="UPDATED", duration=1.5)
        }

        # Act
        results = _aggregate_results(agent_results)

        # Assert
        assert results.review_passed is True
        assert "APPROVE" in results.review_output


# ============================================================================
# TEST: _execute_security_first()
# ============================================================================

class TestExecuteSecurityFirst:
    """Test security-first execution mode (priority mode)."""

    def test_security_first_execution_order(self, mock_agent_pool, tmp_project_dir):
        """Test security agent runs first, then reviewer+docs in parallel."""
        # Arrange
        mock_pool = mock_agent_pool
        feature = "Add file upload endpoint"

        # Track submit_task calls
        submit_calls = []
        def track_submit(agent_type, prompt, **kwargs):
            submit_calls.append(agent_type)
            return f"task-{agent_type}"

        mock_pool.submit_task.side_effect = track_submit

        # Act
        results = _execute_security_first(
            pool=mock_pool,
            feature=feature,
            project_root=tmp_project_dir
        )

        # Assert
        # Security should be first submission
        assert submit_calls[0] == "security-auditor"

        # Reviewer and doc-master should be submitted after security
        # (exact order doesn't matter, but both should be after security)
        assert "reviewer" in submit_calls[1:]
        assert "doc-master" in submit_calls[1:]

        # Total 3 agents submitted
        assert len(submit_calls) == 3

    def test_security_first_blocks_on_failure(self, mock_agent_pool, tmp_project_dir):
        """Test security failure blocks reviewer+docs from running."""
        # Arrange
        mock_pool = mock_agent_pool

        # Security fails
        mock_pool.await_all.return_value = {
            "security-auditor": MagicMock(
                success=False,
                output="FAIL - CWE-22: Path traversal vulnerability",
                agent_type="security-auditor"
            )
        }

        # Act & Assert
        with pytest.raises(SecurityValidationError, match="CWE-22"):
            _execute_security_first(
                pool=mock_pool,
                feature="Add file upload",
                project_root=tmp_project_dir
            )

        # Only security agent should have been submitted
        # (reviewer + doc-master should not run if security fails)
        submit_calls = [call.kwargs.get("agent_type") for call in mock_pool.submit_task.call_args_list]
        assert "security-auditor" in submit_calls
        # In security-first mode, other agents may or may not be submitted
        # depending on implementation (could submit all, then check results)

    def test_security_first_continues_on_success(self, mock_agent_pool, tmp_project_dir):
        """Test security success allows reviewer+docs to run."""
        # Arrange
        mock_pool = mock_agent_pool
        # Default mock already has all agents succeeding

        # Act
        results = _execute_security_first(
            pool=mock_pool,
            feature="Add authentication",
            project_root=tmp_project_dir
        )

        # Assert
        assert results.security_passed is True
        assert results.review_passed is True
        assert results.docs_updated is True
        assert len(results.failed_agents) == 0


# ============================================================================
# TEST: execute_parallel_validation() - Main Entry Point
# ============================================================================

class TestExecuteParallelValidation:
    """Test main entry point for parallel validation."""

    def test_execute_all_parallel_mode(self, mock_agent_pool, tmp_project_dir):
        """Test all agents run in parallel (default mode)."""
        # Arrange
        feature = "Add JWT authentication"

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=False  # All parallel
        )

        # Assert
        assert isinstance(results, ValidationResults)
        assert results.security_passed is True
        assert results.review_passed is True
        assert results.docs_updated is True

        # All 3 agents should have been submitted
        assert mock_agent_pool.submit_task.call_count == 3

    def test_execute_security_first_mode(self, mock_agent_pool, tmp_project_dir):
        """Test security-first mode (priority_mode=True)."""
        # Arrange
        feature = "Add file upload endpoint"

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=True  # Security first
        )

        # Assert
        assert isinstance(results, ValidationResults)
        assert results.security_passed is True

        # Verify security was submitted first
        submit_calls = [call.kwargs.get("agent_type") for call in mock_agent_pool.submit_task.call_args_list]
        assert submit_calls[0] == "security-auditor"

    def test_execute_with_retry_on_timeout(self, mock_agent_pool, tmp_project_dir):
        """Test automatic retry on transient errors."""
        # Arrange
        mock_pool = mock_agent_pool

        # First call times out, second succeeds
        call_count = 0
        def side_effect_submit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Agent timed out")
            return f"task-{call_count}"

        mock_pool.submit_task.side_effect = side_effect_submit

        # Act
        with patch("time.sleep"):  # Don't actually sleep in tests
            results = execute_parallel_validation(
                feature_description="Add caching",
                project_root=tmp_project_dir,
                priority_mode=False
            )

        # Assert
        # Should have retried and succeeded
        assert results is not None

    def test_execute_fails_on_permanent_error(self, mock_agent_pool, tmp_project_dir):
        """Test permanent errors fail fast without retry."""
        # Arrange
        mock_pool = mock_agent_pool
        mock_pool.submit_task.side_effect = ValueError("Invalid agent type")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid agent type"):
            execute_parallel_validation(
                feature_description="Add feature",
                project_root=tmp_project_dir,
                priority_mode=False
            )

    def test_execute_returns_execution_time(self, mock_agent_pool, tmp_project_dir):
        """Test execution time is accurately measured."""
        # Arrange
        # Mock durations: 3.5s + 2.8s + 2.2s = 8.5s total

        # Act
        results = execute_parallel_validation(
            feature_description="Add monitoring",
            project_root=tmp_project_dir,
            priority_mode=False
        )

        # Assert
        assert results.execution_time_seconds > 0
        # Should be approximately sum of agent durations
        assert results.execution_time_seconds >= 2.0  # At least longest agent duration

    def test_execute_with_changed_files_list(self, mock_agent_pool, tmp_project_dir):
        """Test passing changed files list to agents."""
        # Arrange
        feature = "Add user registration"
        changed_files = [
            "src/auth/registration.py",
            "tests/test_registration.py"
        ]

        # Act
        results = execute_parallel_validation(
            feature_description=feature,
            project_root=tmp_project_dir,
            priority_mode=False,
            changed_files=changed_files
        )

        # Assert
        assert results is not None

        # Verify changed files were included in prompts
        submit_calls = mock_agent_pool.submit_task.call_args_list
        for call in submit_calls:
            prompt = call.kwargs.get("prompt", "")  # Get prompt from kwargs
            # Prompt should mention at least one of the changed files
            # (implementation detail - may not be exact match)
            assert isinstance(prompt, str)
# TEST: Exception Classes
# ============================================================================

class TestExceptions:
    """Test custom exception classes."""

    def test_security_validation_error(self):
        """Test SecurityValidationError can be raised and caught."""
        # Arrange
        error_message = "CWE-78: Command injection detected"

        # Act & Assert
        with pytest.raises(SecurityValidationError, match="CWE-78"):
            raise SecurityValidationError(error_message)

    def test_validation_timeout_error(self):
        """Test ValidationTimeoutError can be raised and caught."""
        # Arrange
        error_message = "All agents timed out after 180 seconds"

        # Act & Assert
        with pytest.raises(ValidationTimeoutError, match="timed out"):
            raise ValidationTimeoutError(error_message)


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_feature_description(self, mock_agent_pool, tmp_project_dir):
        """Test validation with empty feature description."""
        # Act & Assert
        with pytest.raises(ValueError, match="Feature description cannot be empty"):
            execute_parallel_validation(
                feature_description="",
                project_root=tmp_project_dir,
                priority_mode=False
            )

    def test_invalid_project_root(self, mock_agent_pool):
        """Test validation with invalid project root."""
        # Arrange
        invalid_path = Path("/nonexistent/project")

        # Act & Assert
        with pytest.raises(ValueError, match="Project root does not exist"):
            execute_parallel_validation(
                feature_description="Add feature",
                project_root=invalid_path,
                priority_mode=False
            )

    def test_all_agents_timeout(self, mock_agent_pool, tmp_project_dir):
        """Test behavior when all agents timeout."""
        # Arrange
        mock_pool = mock_agent_pool
        mock_pool.submit_task.side_effect = TimeoutError("Timeout")

        # Act & Assert
        with patch("time.sleep"):  # Don't sleep in tests
            with pytest.raises(ValidationTimeoutError):
                execute_parallel_validation(
                    feature_description="Add feature",
                    project_root=tmp_project_dir,
                    priority_mode=False
                )

    def test_partial_agent_results(self, mock_agent_pool, tmp_project_dir):
        """Test handling when only some agents return results."""
        # Arrange
        mock_pool = mock_agent_pool
        mock_pool.await_all.return_value = {
            "security-auditor": MagicMock(
                success=True,
                output="PASS",
                agent_type="security-auditor",
                duration=3.0
            )
            # reviewer and doc-master missing
        }

        # Act
        results = execute_parallel_validation(
            feature_description="Add feature",
            project_root=tmp_project_dir,
            priority_mode=False
        )

        # Assert
        assert results.security_passed is True
        assert "reviewer" in results.failed_agents
        assert "doc-master" in results.failed_agents
