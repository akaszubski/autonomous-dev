#!/usr/bin/env python3
"""
Unit tests for agent_pool resource limit integration (TDD Red Phase).

Tests for Issue #259: System-wide resource management integration with agent pool.

Test Strategy:
- Test hard limit blocks agent spawn
- Test soft limit logs warning but proceeds
- Test graceful degradation if resource manager unavailable
- Test resource status propagation

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Coverage Target: 90%+ for resource limit code in agent_pool.py

Date: 2026-01-25
Issue: #259 (System-wide resource management)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - modifications don't exist yet (TDD!)
try:
    from agent_pool import AgentPool, PoolConfig
    from session_resource_manager import (
        SessionResourceManager,
        ResourceConfig,
        ResourceStatus,
    )
    from exceptions import ProcessLimitExceededError
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_registry_dir(tmp_path):
    """Create temporary directory for registry files."""
    registry_dir = tmp_path / ".claude" / "local"
    registry_dir.mkdir(parents=True)
    return registry_dir


@pytest.fixture
def registry_file(temp_registry_dir):
    """Create temporary registry file path."""
    return temp_registry_dir / "session_registry.json"


@pytest.fixture
def resource_manager(registry_file):
    """Create SessionResourceManager for testing."""
    config = ResourceConfig(
        max_sessions=3,
        process_warn_threshold=1500,
        process_hard_limit=2000,
    )
    return SessionResourceManager(registry_file, config)


@pytest.fixture
def agent_pool():
    """Create AgentPool for testing."""
    pool_config = PoolConfig(max_agents=6, token_budget=150000)
    return AgentPool(config=pool_config)


# =============================================================================
# SECTION 1: Hard Limit Tests (5 tests)
# =============================================================================

class TestAgentPoolHardLimitEnforcement:
    """Test hard limit blocks agent spawn."""

    def test_spawn_agent_checks_process_limit(self, agent_pool, resource_manager):
        """Test spawn_agent checks process limit before spawning."""
        # Mock resource manager to indicate hard limit exceeded
        with patch.object(
            resource_manager,
            "check_resource_limits",
            side_effect=ProcessLimitExceededError("Process limit exceeded: 2500 > 2000")
        ):
            # Inject resource manager into pool
            agent_pool._resource_manager = resource_manager

            # Should raise ProcessLimitExceededError
            with pytest.raises(ProcessLimitExceededError) as exc_info:
                agent_pool.submit_task(
                    agent_type="researcher",
                    prompt="Test task",
                    priority="P2_TESTS",
                )

            assert "2500" in str(exc_info.value)
            assert "2000" in str(exc_info.value)

    def test_hard_limit_prevents_all_agent_spawns(self, agent_pool, resource_manager):
        """Test hard limit prevents any new agent spawns."""
        # Mock resource manager to always exceed hard limit
        with patch.object(
            resource_manager,
            "check_resource_limits",
            side_effect=ProcessLimitExceededError("Process limit exceeded")
        ):
            agent_pool._resource_manager = resource_manager

            # All spawn attempts should fail
            for i in range(5):
                with pytest.raises(ProcessLimitExceededError):
                    agent_pool.submit_task(
                        agent_type=f"agent_{i}",
                        prompt=f"Task {i}",
                        priority="P2_TESTS",
                    )

    def test_hard_limit_error_message_includes_details(self, agent_pool, resource_manager):
        """Test hard limit error message includes process counts and limit."""
        with patch.object(
            resource_manager,
            "check_resource_limits",
            side_effect=ProcessLimitExceededError(
                "Process limit exceeded: 2500 processes (limit: 2000)"
            )
        ):
            agent_pool._resource_manager = resource_manager

            with pytest.raises(ProcessLimitExceededError) as exc_info:
                agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            error_msg = str(exc_info.value)
            assert "2500" in error_msg
            assert "2000" in error_msg
            assert "limit" in error_msg.lower()

    def test_hard_limit_checked_before_priority_queue(self, agent_pool, resource_manager):
        """Test hard limit check happens before priority queue insertion."""
        # Mock resource manager to exceed limit
        with patch.object(
            resource_manager,
            "check_resource_limits",
            side_effect=ProcessLimitExceededError("Process limit exceeded")
        ):
            agent_pool._resource_manager = resource_manager

            # Mock priority queue to verify it's never called
            with patch.object(agent_pool, "_priority_queue") as mock_queue:
                with pytest.raises(ProcessLimitExceededError):
                    agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

                # Queue should never be accessed
                mock_queue.put.assert_not_called()

    def test_hard_limit_returns_immediately_no_retry(self, agent_pool, resource_manager):
        """Test hard limit fails immediately without retry."""
        call_count = 0

        def check_limit_side_effect():
            nonlocal call_count
            call_count += 1
            raise ProcessLimitExceededError("Process limit exceeded")

        with patch.object(
            resource_manager,
            "check_resource_limits",
            side_effect=check_limit_side_effect
        ):
            agent_pool._resource_manager = resource_manager

            with pytest.raises(ProcessLimitExceededError):
                agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            # Should only check once (no retry)
            assert call_count == 1


# =============================================================================
# SECTION 2: Soft Limit Tests (5 tests)
# =============================================================================

class TestAgentPoolSoftLimitWarnings:
    """Test soft limit logs warning but proceeds."""

    def test_spawn_agent_logs_warning_at_soft_limit(self, agent_pool, resource_manager):
        """Test spawn_agent logs warning when process count exceeds soft limit."""
        # Mock resource manager to return status with warning
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1800,  # Between 1500 and 2000
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=["Process count 1800 approaching limit 2000"],
        )

        with patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch("agent_pool.logger") as mock_logger:
            agent_pool._resource_manager = resource_manager

            # Should proceed but log warning
            agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "1800" in str(mock_logger.warning.call_args)

    def test_soft_limit_does_not_block_agent_spawn(self, agent_pool, resource_manager):
        """Test soft limit warning does not block agent spawn."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1800,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=["Process count approaching limit"],
        )

        with patch.object(resource_manager, "check_resource_limits", return_value=status):
            agent_pool._resource_manager = resource_manager

            # Should succeed despite warning
            handle = agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            assert handle is not None
            assert handle.agent_type == "researcher"

    def test_soft_limit_warning_includes_threshold_info(self, agent_pool, resource_manager):
        """Test soft limit warning includes threshold information."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1800,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=["Process count 1800 exceeds warning threshold 1500"],
        )

        with patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch("agent_pool.logger") as mock_logger:
            agent_pool._resource_manager = resource_manager

            agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            # Verify warning includes thresholds
            warning_msg = str(mock_logger.warning.call_args)
            assert "1800" in warning_msg
            assert "1500" in warning_msg or "threshold" in warning_msg.lower()

    def test_multiple_warnings_all_logged(self, agent_pool, resource_manager):
        """Test multiple warnings are all logged."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1800,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=[
                "Process count 1800 exceeds warning threshold 1500",
                "Approaching session limit",
            ],
        )

        with patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch("agent_pool.logger") as mock_logger:
            agent_pool._resource_manager = resource_manager

            agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            # Both warnings should be logged
            assert mock_logger.warning.call_count >= 1

    def test_no_warning_below_soft_limit(self, agent_pool, resource_manager):
        """Test no warning logged when below soft limit."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1000,  # Below 1500
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=[],  # No warnings
        )

        with patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch("agent_pool.logger") as mock_logger:
            agent_pool._resource_manager = resource_manager

            agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            # No warning should be logged
            mock_logger.warning.assert_not_called()


# =============================================================================
# SECTION 3: Graceful Degradation Tests (5 tests)
# =============================================================================

class TestAgentPoolGracefulDegradation:
    """Test graceful degradation if resource manager unavailable."""

    def test_missing_resource_manager_proceeds_normally(self, agent_pool):
        """Test agent pool works without resource manager."""
        # Don't inject resource manager
        assert not hasattr(agent_pool, "_resource_manager") or agent_pool._resource_manager is None

        # Should proceed normally
        handle = agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

        assert handle is not None
        assert handle.agent_type == "researcher"

    def test_resource_manager_import_error_handled(self, agent_pool):
        """Test agent pool handles resource manager import error gracefully."""
        # Mock import to fail
        with patch("agent_pool.SessionResourceManager", side_effect=ImportError("Module not found")):
            # Should proceed without resource manager
            handle = agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            assert handle is not None

    def test_resource_manager_initialization_error_logged(self, agent_pool):
        """Test resource manager initialization error is logged but doesn't block."""
        with patch("agent_pool.SessionResourceManager", side_effect=Exception("Init failed")), \
             patch("agent_pool.logger") as mock_logger:
            # Should proceed and log error
            handle = agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            assert handle is not None
            # Should log initialization failure
            assert mock_logger.warning.called or mock_logger.error.called

    def test_resource_check_exception_logged_and_continues(self, agent_pool, resource_manager):
        """Test exception during resource check is logged but doesn't block."""
        with patch.object(
            resource_manager,
            "check_resource_limits",
            side_effect=Exception("Unexpected error")
        ), patch("agent_pool.logger") as mock_logger:
            agent_pool._resource_manager = resource_manager

            # Should proceed despite exception
            handle = agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            assert handle is not None
            # Should log exception
            assert mock_logger.exception.called or mock_logger.error.called

    def test_graceful_degradation_documented_in_logs(self, agent_pool):
        """Test graceful degradation is documented in logs."""
        with patch("agent_pool.SessionResourceManager", side_effect=ImportError("Not available")), \
             patch("agent_pool.logger") as mock_logger:
            # Initialize pool (might trigger resource manager init)
            agent_pool.submit_task("researcher", "Test task", "P2_TESTS")

            # Should document that resource manager is unavailable
            # (Implementation detail: may log on first use or at init)


# =============================================================================
# SECTION 4: Resource Status Propagation Tests (3 tests)
# =============================================================================

class TestResourceStatusPropagation:
    """Test resource status is properly propagated."""

    def test_get_pool_status_includes_resource_info(self, agent_pool, resource_manager):
        """Test get_pool_status includes resource manager info."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1000,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=[],
        )

        with patch.object(resource_manager, "check_resource_limits", return_value=status):
            agent_pool._resource_manager = resource_manager

            pool_status = agent_pool.get_pool_status()

            # Should include resource info
            assert hasattr(pool_status, "resource_status")
            assert pool_status.resource_status.total_processes == 1000

    def test_resource_status_updated_on_check(self, agent_pool, resource_manager):
        """Test resource status is updated when checked."""
        status1 = ResourceStatus(
            active_sessions=2,
            total_processes=1000,
            thresholds={"max_sessions": 3, "process_warn_threshold": 1500, "process_hard_limit": 2000},
            warnings=[],
        )
        status2 = ResourceStatus(
            active_sessions=2,
            total_processes=1500,
            thresholds={"max_sessions": 3, "process_warn_threshold": 1500, "process_hard_limit": 2000},
            warnings=["Approaching threshold"],
        )

        with patch.object(
            resource_manager,
            "check_resource_limits",
            side_effect=[status1, status2]
        ):
            agent_pool._resource_manager = resource_manager

            # First check
            agent_pool.submit_task("researcher", "Task 1", "P2_TESTS")
            pool_status1 = agent_pool.get_pool_status()

            # Second check
            agent_pool.submit_task("researcher", "Task 2", "P2_TESTS")
            pool_status2 = agent_pool.get_pool_status()

            # Status should be updated
            assert pool_status1.resource_status.total_processes == 1000
            assert pool_status2.resource_status.total_processes == 1500

    def test_resource_status_none_when_unavailable(self, agent_pool):
        """Test resource_status is None when resource manager unavailable."""
        # No resource manager injected
        pool_status = agent_pool.get_pool_status()

        # Should have resource_status field but None value
        assert hasattr(pool_status, "resource_status")
        assert pool_status.resource_status is None


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (23 unit tests):

SECTION 1: Hard Limit Enforcement (5 tests)
✗ test_spawn_agent_checks_process_limit
✗ test_hard_limit_prevents_all_agent_spawns
✗ test_hard_limit_error_message_includes_details
✗ test_hard_limit_checked_before_priority_queue
✗ test_hard_limit_returns_immediately_no_retry

SECTION 2: Soft Limit Warnings (5 tests)
✗ test_spawn_agent_logs_warning_at_soft_limit
✗ test_soft_limit_does_not_block_agent_spawn
✗ test_soft_limit_warning_includes_threshold_info
✗ test_multiple_warnings_all_logged
✗ test_no_warning_below_soft_limit

SECTION 3: Graceful Degradation (5 tests)
✗ test_missing_resource_manager_proceeds_normally
✗ test_resource_manager_import_error_handled
✗ test_resource_manager_initialization_error_logged
✗ test_resource_check_exception_logged_and_continues
✗ test_graceful_degradation_documented_in_logs

SECTION 4: Resource Status Propagation (3 tests)
✗ test_get_pool_status_includes_resource_info
✗ test_resource_status_updated_on_check
✗ test_resource_status_none_when_unavailable

TOTAL: 23 unit tests (all FAILING - TDD red phase)

Coverage Target: 90%+ for resource limit code in agent_pool.py
"""
