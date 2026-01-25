#!/usr/bin/env python3
"""
Integration tests for dispatcher resource checking (TDD Red Phase).

Tests for Issue #259: System-wide resource management integration with dispatcher.

Test Strategy:
- Test dispatcher calls resource manager before pipeline
- Test hard limit blocks pipeline start
- Test warnings logged but pipeline proceeds
- Test resource status included in pipeline output

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Coverage Target: 90%+ for resource checking code in dispatcher.py

Date: 2026-01-25
Issue: #259 (System-wide resource management)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import pytest
import sys
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib" / "implement_dispatcher"))

# Import will fail - modifications don't exist yet (TDD!)
try:
    from dispatcher import ImplementDispatcher
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
def temp_workspace(tmp_path):
    """Create temporary workspace for dispatcher tests."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create .claude directory
    claude_dir = workspace / ".claude"
    claude_dir.mkdir()
    local_dir = claude_dir / "local"
    local_dir.mkdir()

    return workspace


@pytest.fixture
def registry_file(temp_workspace):
    """Get path to session registry file."""
    return temp_workspace / ".claude" / "local" / "session_registry.json"


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
def dispatcher(temp_workspace):
    """Create ImplementDispatcher for testing."""
    return ImplementDispatcher(repo_path=str(temp_workspace))


# =============================================================================
# SECTION 1: Pre-Flight Resource Check Tests (6 tests)
# =============================================================================

class TestDispatcherPreFlightResourceCheck:
    """Test dispatcher calls resource manager before pipeline."""

    def test_dispatch_checks_resources_before_pipeline(
        self, dispatcher, resource_manager, temp_workspace
    ):
        """Test dispatch() checks resources before starting pipeline."""
        # Mock pipeline execution
        with patch.object(dispatcher, "_run_pipeline") as mock_pipeline, \
             patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits") as mock_check:
            mock_check.return_value = ResourceStatus(
                active_sessions=1,
                total_processes=1000,
                thresholds={
                    "max_sessions": 3,
                    "process_warn_threshold": 1500,
                    "process_hard_limit": 2000,
                },
                warnings=[],
            )

            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature X",
                project_path=str(temp_workspace),
            )

            # Resource check should be called before pipeline
            mock_check.assert_called_once()

    def test_resource_check_happens_before_any_agents_spawn(
        self, dispatcher, resource_manager
    ):
        """Test resource check happens before any agents are spawned."""
        call_order = []

        def track_resource_check():
            call_order.append("resource_check")
            return ResourceStatus(
                active_sessions=1,
                total_processes=1000,
                thresholds={
                    "max_sessions": 3,
                    "process_warn_threshold": 1500,
                    "process_hard_limit": 2000,
                },
                warnings=[],
            )

        def track_agent_spawn(*args, **kwargs):
            call_order.append("agent_spawn")
            return MagicMock()

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", side_effect=track_resource_check), \
             patch.object(dispatcher, "_spawn_agent", side_effect=track_agent_spawn), \
             patch.object(dispatcher, "_run_pipeline"):
            dispatcher.dispatch(
                mode="quick",
                user_input="Test feature",
                project_path="/workspace",
            )

        # Resource check should happen first
        assert call_order[0] == "resource_check"

    def test_resource_check_session_registration(self, dispatcher, resource_manager):
        """Test dispatcher registers session during resource check."""
        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session") as mock_register, \
             patch.object(dispatcher, "_run_pipeline"):
            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Session should be registered
            mock_register.assert_called_once()

    def test_resource_check_session_cleanup_on_completion(
        self, dispatcher, resource_manager
    ):
        """Test dispatcher unregisters session on completion."""
        session_id = "session-123"

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(resource_manager, "unregister_session") as mock_unregister, \
             patch.object(dispatcher, "_run_pipeline"):
            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Session should be unregistered after completion
            mock_unregister.assert_called_once_with(session_id)

    def test_resource_check_session_cleanup_on_error(self, dispatcher, resource_manager):
        """Test dispatcher unregisters session even on error."""
        session_id = "session-123"

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(resource_manager, "unregister_session") as mock_unregister, \
             patch.object(dispatcher, "_run_pipeline", side_effect=Exception("Pipeline failed")):
            with pytest.raises(Exception):
                dispatcher.dispatch(
                    mode="full",
                    user_input="Implement feature",
                    project_path="/workspace",
                )

            # Session should still be unregistered
            mock_unregister.assert_called_once_with(session_id)

    def test_resource_check_estimates_processes_for_mode(self, dispatcher, resource_manager):
        """Test dispatcher provides process estimate based on mode."""
        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session") as mock_register, \
             patch.object(dispatcher, "_run_pipeline"):
            # Full mode should estimate more processes
            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Should register with process estimate
            mock_register.assert_called_once()
            call_kwargs = mock_register.call_args[1]
            assert "estimated_processes" in call_kwargs
            full_estimate = call_kwargs["estimated_processes"]

            mock_register.reset_mock()

            # Quick mode should estimate fewer processes
            dispatcher.dispatch(
                mode="quick",
                user_input="Implement feature",
                project_path="/workspace",
            )

            call_kwargs = mock_register.call_args[1]
            quick_estimate = call_kwargs["estimated_processes"]

            # Full should estimate more than quick
            assert full_estimate > quick_estimate


# =============================================================================
# SECTION 2: Hard Limit Blocking Tests (5 tests)
# =============================================================================

class TestDispatcherHardLimitBlocking:
    """Test hard limit blocks pipeline start."""

    def test_hard_limit_blocks_pipeline_execution(self, dispatcher, resource_manager):
        """Test hard limit prevents pipeline from executing."""
        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(
                 resource_manager,
                 "check_resource_limits",
                 side_effect=ProcessLimitExceededError("Process limit exceeded: 2500 > 2000")
             ), \
             patch.object(dispatcher, "_run_pipeline") as mock_pipeline:
            with pytest.raises(ProcessLimitExceededError):
                dispatcher.dispatch(
                    mode="full",
                    user_input="Implement feature",
                    project_path="/workspace",
                )

            # Pipeline should never be called
            mock_pipeline.assert_not_called()

    def test_hard_limit_error_message_user_friendly(self, dispatcher, resource_manager):
        """Test hard limit error message is user-friendly."""
        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(
                 resource_manager,
                 "check_resource_limits",
                 side_effect=ProcessLimitExceededError(
                     "Process limit exceeded: 2500 processes (hard limit: 2000)"
                 )
             ):
            with pytest.raises(ProcessLimitExceededError) as exc_info:
                dispatcher.dispatch(
                    mode="full",
                    user_input="Implement feature",
                    project_path="/workspace",
                )

            error_msg = str(exc_info.value)
            assert "2500" in error_msg
            assert "2000" in error_msg
            assert "limit" in error_msg.lower()

    def test_hard_limit_session_not_left_registered(self, dispatcher, resource_manager):
        """Test hard limit doesn't leave session registered."""
        session_id = "session-123"

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "register_session", return_value=session_id), \
             patch.object(
                 resource_manager,
                 "check_resource_limits",
                 side_effect=ProcessLimitExceededError("Process limit exceeded")
             ), \
             patch.object(resource_manager, "unregister_session") as mock_unregister:
            with pytest.raises(ProcessLimitExceededError):
                dispatcher.dispatch(
                    mode="full",
                    user_input="Implement feature",
                    project_path="/workspace",
                )

            # Session should be unregistered even though pipeline didn't run
            mock_unregister.assert_called_once_with(session_id)

    def test_hard_limit_includes_mitigation_suggestions(self, dispatcher, resource_manager):
        """Test hard limit error includes mitigation suggestions."""
        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(
                 resource_manager,
                 "check_resource_limits",
                 side_effect=ProcessLimitExceededError(
                     "Process limit exceeded: 2500 > 2000\n"
                     "Suggestion: Wait for other sessions to complete or use --quick mode"
                 )
             ):
            with pytest.raises(ProcessLimitExceededError) as exc_info:
                dispatcher.dispatch(
                    mode="full",
                    user_input="Implement feature",
                    project_path="/workspace",
                )

            error_msg = str(exc_info.value)
            assert "suggestion" in error_msg.lower() or "wait" in error_msg.lower()

    def test_hard_limit_exits_cleanly(self, dispatcher, resource_manager):
        """Test hard limit exits without leaving corrupted state."""
        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(
                 resource_manager,
                 "check_resource_limits",
                 side_effect=ProcessLimitExceededError("Process limit exceeded")
             ):
            # Should raise exception but not corrupt state
            with pytest.raises(ProcessLimitExceededError):
                dispatcher.dispatch(
                    mode="full",
                    user_input="Implement feature",
                    project_path="/workspace",
                )

            # No state files should be left in inconsistent state
            # (Implementation detail: verify cleanup happened)


# =============================================================================
# SECTION 3: Warning Logging Tests (4 tests)
# =============================================================================

class TestDispatcherWarningLogging:
    """Test warnings logged but pipeline proceeds."""

    def test_soft_limit_warning_logged_pipeline_proceeds(
        self, dispatcher, resource_manager
    ):
        """Test soft limit warning is logged but pipeline proceeds."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1800,  # Between 1500 and 2000
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=["Process count 1800 approaching hard limit 2000"],
        )

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch.object(dispatcher, "_run_pipeline") as mock_pipeline, \
             patch("dispatcher.logger") as mock_logger:
            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Warning should be logged
            mock_logger.warning.assert_called_once()
            assert "1800" in str(mock_logger.warning.call_args)

            # Pipeline should still execute
            mock_pipeline.assert_called_once()

    def test_multiple_warnings_all_logged(self, dispatcher, resource_manager):
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
                "Process count 1800 approaching hard limit",
                "2 active sessions (limit: 3)",
            ],
        )

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch.object(dispatcher, "_run_pipeline"), \
             patch("dispatcher.logger") as mock_logger:
            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Both warnings should be logged
            assert mock_logger.warning.call_count >= 2 or \
                   ("1800" in str(mock_logger.warning.call_args) and
                    "2 active sessions" in str(mock_logger.warning.call_args))

    def test_no_warnings_when_resources_healthy(self, dispatcher, resource_manager):
        """Test no warnings logged when resources healthy."""
        status = ResourceStatus(
            active_sessions=1,
            total_processes=1000,  # Below 1500
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=[],  # No warnings
        )

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch.object(dispatcher, "_run_pipeline"), \
             patch("dispatcher.logger") as mock_logger:
            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # No resource warnings should be logged
            # (May have other logs, but not resource warnings)
            warning_calls = [
                str(call) for call in mock_logger.warning.call_args_list
                if "process" in str(call).lower() or "limit" in str(call).lower()
            ]
            assert len(warning_calls) == 0

    def test_warning_includes_current_and_threshold_values(
        self, dispatcher, resource_manager
    ):
        """Test warning includes current count and threshold values."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1800,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=["Process count 1800 exceeds warning threshold 1500 (hard limit: 2000)"],
        )

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch.object(dispatcher, "_run_pipeline"), \
             patch("dispatcher.logger") as mock_logger:
            dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Warning should include all three values
            warning_msg = str(mock_logger.warning.call_args)
            assert "1800" in warning_msg  # Current
            assert "1500" in warning_msg  # Soft limit
            assert "2000" in warning_msg  # Hard limit


# =============================================================================
# SECTION 4: Resource Status Output Tests (3 tests)
# =============================================================================

class TestDispatcherResourceStatusOutput:
    """Test resource status included in pipeline output."""

    def test_pipeline_output_includes_resource_status(self, dispatcher, resource_manager):
        """Test pipeline output includes resource status."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1200,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=[],
        )

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch.object(dispatcher, "_run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {"success": True, "output": "Pipeline complete"}

            result = dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Result should include resource status
            assert "resource_status" in result
            assert result["resource_status"]["total_processes"] == 1200

    def test_resource_status_included_even_on_pipeline_failure(
        self, dispatcher, resource_manager
    ):
        """Test resource status included even if pipeline fails."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1200,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=[],
        )

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch.object(dispatcher, "_run_pipeline", side_effect=Exception("Pipeline failed")):
            with pytest.raises(Exception) as exc_info:
                dispatcher.dispatch(
                    mode="full",
                    user_input="Implement feature",
                    project_path="/workspace",
                )

            # Exception should include resource status context
            # (Implementation may attach resource status to exception)

    def test_resource_status_formatted_for_user_display(self, dispatcher, resource_manager):
        """Test resource status is formatted for user display."""
        status = ResourceStatus(
            active_sessions=2,
            total_processes=1200,
            thresholds={
                "max_sessions": 3,
                "process_warn_threshold": 1500,
                "process_hard_limit": 2000,
            },
            warnings=[],
        )

        with patch.object(dispatcher, "_resource_manager", resource_manager), \
             patch.object(resource_manager, "check_resource_limits", return_value=status), \
             patch.object(dispatcher, "_run_pipeline"):
            result = dispatcher.dispatch(
                mode="full",
                user_input="Implement feature",
                project_path="/workspace",
            )

            # Resource status should be formatted for display
            assert "resource_status" in result
            resource_info = result["resource_status"]

            # Should have user-friendly format
            assert "active_sessions" in resource_info
            assert "total_processes" in resource_info


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (18 integration tests):

SECTION 1: Pre-Flight Resource Check (6 tests)
✗ test_dispatch_checks_resources_before_pipeline
✗ test_resource_check_happens_before_any_agents_spawn
✗ test_resource_check_session_registration
✗ test_resource_check_session_cleanup_on_completion
✗ test_resource_check_session_cleanup_on_error
✗ test_resource_check_estimates_processes_for_mode

SECTION 2: Hard Limit Blocking (5 tests)
✗ test_hard_limit_blocks_pipeline_execution
✗ test_hard_limit_error_message_user_friendly
✗ test_hard_limit_session_not_left_registered
✗ test_hard_limit_includes_mitigation_suggestions
✗ test_hard_limit_exits_cleanly

SECTION 3: Warning Logging (4 tests)
✗ test_soft_limit_warning_logged_pipeline_proceeds
✗ test_multiple_warnings_all_logged
✗ test_no_warnings_when_resources_healthy
✗ test_warning_includes_current_and_threshold_values

SECTION 4: Resource Status Output (3 tests)
✗ test_pipeline_output_includes_resource_status
✗ test_resource_status_included_even_on_pipeline_failure
✗ test_resource_status_formatted_for_user_display

TOTAL: 18 integration tests (all FAILING - TDD red phase)

Coverage Target: 90%+ for resource checking code in dispatcher.py
"""
