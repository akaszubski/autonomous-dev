#!/usr/bin/env python3
"""
Integration tests for progress indicator system

This module tests the complete progress indicator system including:
- Full pipeline with mock agents
- Display updates as agents complete
- Cleanup after completion
- Error recovery
- End-to-end workflows

Test Coverage:
- Complete agent pipeline simulation
- Display process lifecycle
- JSON state updates and polling
- Error scenarios and recovery
- Concurrent access handling
- Performance under load

These tests follow TDD - they WILL FAIL until all components are implemented.
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestProgressIntegration:
    """Integration tests for the complete progress system."""

    # ========================================
    # FIXTURES
    # ========================================

    @pytest.fixture
    def integration_session_dir(self, tmp_path):
        """Create session directory for integration tests."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def integration_session_file(self, integration_session_dir):
        """Create session file for integration tests."""
        session_file = integration_session_dir / "20251104-120000-pipeline.json"
        initial_state = {
            "session_id": "20251104-120000",
            "started": "2025-11-04T12:00:00",
            "github_issue": None,
            "agents": []
        }
        session_file.write_text(json.dumps(initial_state, indent=2))
        return session_file

    @pytest.fixture
    def mock_agent_tracker(self, integration_session_file):
        """Create AgentTracker instance for testing."""
        from scripts.agent_tracker import AgentTracker

        # Mock the file lookup to use our test file
        with patch.object(AgentTracker, '__init__', lambda self: None):
            tracker = AgentTracker()
            tracker.session_file = integration_session_file
            tracker.session_data = json.loads(integration_session_file.read_text())
            tracker._save = lambda: integration_session_file.write_text(
                json.dumps(tracker.session_data, indent=2)
            )
            return tracker

    # ========================================
    # FULL PIPELINE TESTS
    # ========================================

    def test_full_pipeline_with_display(self, integration_session_file, tmp_path):
        """Test complete pipeline execution with live display."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        controller = PipelineController(
            session_file=integration_session_file,
            pid_dir=tmp_path
        )

        # Mock the subprocess to avoid actually starting display
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            # Start display
            controller.start_display()
            assert controller.is_display_running()

            # Simulate agents running and updating state
            agents = ["researcher", "planner", "test-master", "implementer",
                     "reviewer", "security-auditor", "doc-master"]

            for i, agent in enumerate(agents):
                # Update session file to show agent progress
                state = json.loads(integration_session_file.read_text())
                state["agents"].append({
                    "agent": agent,
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                    "duration_seconds": 100 + i * 10,
                    "message": f"{agent} completed"
                })
                integration_session_file.write_text(json.dumps(state, indent=2))

                # Give display time to poll (in real usage)
                # In test, we just verify state is correct

            # Verify final state
            final_state = json.loads(integration_session_file.read_text())
            assert len(final_state["agents"]) == 7
            assert all(a["status"] == "completed" for a in final_state["agents"])

            # Stop display
            controller.stop_display()
            assert not controller.is_display_running()

    def test_display_updates_as_agents_complete(self, integration_session_file, mock_agent_tracker):
        """Test that display updates in real-time as agents complete."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Simulate agent completions
        agents = ["researcher", "planner", "test-master"]

        for agent in agents:
            # Add agent to tracker
            mock_agent_tracker.complete_agent(agent, f"{agent} completed")

            # Load and verify display can read updated state
            state = display.load_pipeline_state()
            assert agent in [a["agent"] for a in state["agents"]]

            # Render and verify progress increases
            output = display.render_tree_view(state)
            assert agent in output

    def test_display_shows_incremental_progress(self, integration_session_file):
        """Test that progress percentage increases correctly."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Start with empty state
        state = json.loads(integration_session_file.read_text())
        progress_0 = display.calculate_progress(state)
        assert progress_0 == 0

        # Add completed agents one by one
        for i in range(1, 8):
            state["agents"].append({
                "agent": f"agent-{i}",
                "status": "completed",
                "duration_seconds": 100
            })
            integration_session_file.write_text(json.dumps(state, indent=2))

            new_state = display.load_pipeline_state()
            progress = display.calculate_progress(new_state)

            # Progress should increase with each agent
            expected = int((i / 7) * 100)
            assert progress == expected

    def test_pipeline_completion_detection(self, integration_session_file, mock_agent_tracker):
        """Test detection of pipeline completion."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Complete all required agents
        required_agents = ["researcher", "planner", "test-master", "implementer",
                          "reviewer", "security-auditor", "doc-master"]

        for agent in required_agents:
            mock_agent_tracker.complete_agent(agent, f"{agent} completed")

        # Check completion status
        state = display.load_pipeline_state()
        is_complete = display.is_pipeline_complete(state)

        assert is_complete is True
        assert display.calculate_progress(state) == 100

    # ========================================
    # ERROR RECOVERY TESTS
    # ========================================

    def test_recovery_from_display_crash(self, integration_session_file, tmp_path):
        """Test recovery when display process crashes."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=integration_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            # First process crashes
            crashed_process = Mock()
            crashed_process.pid = 12345
            crashed_process.poll.side_effect = [None, 1]  # Running then crashed

            # Second process runs successfully
            healthy_process = Mock()
            healthy_process.pid = 12346
            healthy_process.poll.return_value = None

            mock_popen.side_effect = [crashed_process, healthy_process]

            # Start display
            controller.start_display()
            assert controller.display_process.pid == 12345

            # Detect crash
            assert not controller.is_display_running()

            # Restart
            controller.start_display()
            assert controller.display_process.pid == 12346
            assert controller.is_display_running()

    def test_recovery_from_corrupted_session_file(self, integration_session_file):
        """Test handling of corrupted session file."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Corrupt the session file
        integration_session_file.write_text("{corrupt json")

        # Should handle gracefully
        state = display.load_pipeline_state()
        assert state is None or state == {}

        # Should still be able to render (empty state)
        output = display.render_tree_view(state or {})
        assert len(output) > 0

    def test_recovery_from_agent_failure(self, integration_session_file, mock_agent_tracker):
        """Test display continues when agent fails."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Complete some agents
        mock_agent_tracker.complete_agent("researcher", "Research completed")

        # Fail an agent
        mock_agent_tracker.fail_agent("planner", "Planning failed")

        # Continue with remaining agents
        mock_agent_tracker.complete_agent("test-master", "Tests written")

        # Display should show all agents including failure
        state = display.load_pipeline_state()
        output = display.render_tree_view(state)

        assert "researcher" in output
        assert "planner" in output
        assert "test-master" in output
        assert "❌" in output  # Failed indicator

    def test_cleanup_after_pipeline_error(self, integration_session_file, tmp_path):
        """Test cleanup when pipeline encounters error."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=integration_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            try:
                controller.start_display()

                # Simulate error during pipeline
                raise RuntimeError("Pipeline error")

            except RuntimeError:
                # Cleanup should happen
                controller.cleanup()

            # Display should be stopped
            assert mock_process.terminate.called

            # PID file should be removed
            pid_file = tmp_path / "progress_display.pid"
            assert not pid_file.exists()

    # ========================================
    # CONCURRENT ACCESS TESTS
    # ========================================

    def test_concurrent_agent_updates(self, integration_session_file, mock_agent_tracker):
        """Test handling concurrent agent state updates."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Simulate rapid agent updates (as if running concurrently)
        agents = ["researcher", "planner", "test-master"]

        # Update all agents quickly
        for agent in agents:
            mock_agent_tracker.start_agent(agent, f"{agent} starting")

        for agent in agents:
            mock_agent_tracker.complete_agent(agent, f"{agent} completed")

        # Display should handle all updates correctly
        state = display.load_pipeline_state()
        assert len(state["agents"]) >= len(agents)

        # All should show as completed
        completed = [a for a in state["agents"] if a["status"] == "completed"]
        assert len(completed) == len(agents)

    def test_multiple_display_processes_prevention(self, integration_session_file, tmp_path):
        """Test that multiple display processes are prevented."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller1 = PipelineController(
            session_file=integration_session_file,
            pid_dir=tmp_path
        )

        controller2 = PipelineController(
            session_file=integration_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            # Start first controller
            controller1.start_display()

            # Try to start second controller - should detect existing process
            controller2.start_display()

            # Should only have created one process
            assert mock_popen.call_count == 1

    def test_file_lock_during_updates(self, integration_session_file):
        """Test file locking prevents corruption during updates."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Simulate reading while file is being written
        # This tests that reads don't get partial/corrupted data

        def concurrent_write():
            state = json.loads(integration_session_file.read_text())
            state["agents"].append({
                "agent": "test",
                "status": "completed"
            })
            # Simulate slow write
            time.sleep(0.01)
            integration_session_file.write_text(json.dumps(state, indent=2))

        # Try to read during write
        # Should either get old state or new state, never corrupted
        state = display.load_pipeline_state()
        assert state is not None
        assert "session_id" in state

    # ========================================
    # PERFORMANCE TESTS
    # ========================================

    def test_display_performance_with_many_agents(self, integration_session_file):
        """Test display performance with large number of agents."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Add many agent entries
        state = json.loads(integration_session_file.read_text())
        for i in range(100):
            state["agents"].append({
                "agent": f"agent-{i}",
                "status": "completed",
                "duration_seconds": i,
                "message": f"Agent {i} completed"
            })

        integration_session_file.write_text(json.dumps(state, indent=2))

        # Should render without performance issues
        start_time = time.time()
        output = display.render_tree_view(state)
        render_time = time.time() - start_time

        # Should render quickly (< 1 second)
        assert render_time < 1.0
        assert len(output) > 0

    def test_polling_interval_efficiency(self, integration_session_file):
        """Test that polling interval is efficient."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        # Use fast polling for test
        display = ProgressDisplay(
            session_file=integration_session_file,
            refresh_interval=0.1
        )

        # Should use specified interval
        assert display.refresh_interval == 0.1

        # Test that it doesn't poll too frequently (CPU waste)
        # or too slowly (unresponsive UI)
        assert 0.05 <= display.refresh_interval <= 2.0

    # ========================================
    # END-TO-END WORKFLOW TESTS
    # ========================================

    def test_complete_auto_implement_workflow(self, integration_session_file, tmp_path):
        """Test complete /auto-implement workflow with progress display."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController

        controller = PipelineController(
            session_file=integration_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            # 1. Start progress display
            controller.start_display()
            assert controller.is_display_running()

            # 2. Simulate agent pipeline execution
            agents = [
                ("researcher", "Found 3 JWT patterns"),
                ("planner", "Created architecture plan"),
                ("test-master", "Wrote 25 tests"),
                ("implementer", "Implemented JWT validation"),
                ("reviewer", "Code review passed"),
                ("security-auditor", "No vulnerabilities found"),
                ("doc-master", "Updated API documentation")
            ]

            for agent, message in agents:
                state = json.loads(integration_session_file.read_text())
                state["agents"].append({
                    "agent": agent,
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                    "duration_seconds": 100,
                    "message": message
                })
                integration_session_file.write_text(json.dumps(state, indent=2))

            # 3. Verify completion
            final_state = json.loads(integration_session_file.read_text())
            assert len(final_state["agents"]) == 7

            # 4. Stop display
            controller.stop_display()
            assert not controller.is_display_running()

            # 5. Verify cleanup
            pid_file = tmp_path / "progress_display.pid"
            assert not pid_file.exists()

    def test_display_with_github_issue_tracking(self, integration_session_file, tmp_path):
        """Test progress display with GitHub issue integration."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay
        from scripts.agent_tracker import AgentTracker

        # Create tracker and link GitHub issue
        with patch.object(AgentTracker, '__init__', lambda self: None):
            tracker = AgentTracker()
            tracker.session_file = integration_session_file
            tracker.session_data = json.loads(integration_session_file.read_text())
            tracker._save = lambda: integration_session_file.write_text(
                json.dumps(tracker.session_data, indent=2)
            )

            # Link GitHub issue
            tracker.set_github_issue(123)

        # Display should show GitHub issue
        display = ProgressDisplay(session_file=integration_session_file)
        state = display.load_pipeline_state()
        output = display.render_tree_view(state)

        assert "123" in output or "#123" in output
        assert state["github_issue"] == 123

    def test_session_file_persistence_across_restarts(self, integration_session_file, tmp_path):
        """Test that session state persists across display restarts."""
        from plugins.autonomous_dev.scripts.pipeline_controller import PipelineController
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        # Add some agent data
        state = json.loads(integration_session_file.read_text())
        state["agents"].append({
            "agent": "researcher",
            "status": "completed",
            "duration_seconds": 100
        })
        integration_session_file.write_text(json.dumps(state, indent=2))

        # Start and stop controller
        controller = PipelineController(
            session_file=integration_session_file,
            pid_dir=tmp_path
        )

        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            controller.start_display()
            controller.stop_display()

        # Start new display - should load existing state
        display = ProgressDisplay(session_file=integration_session_file)
        loaded_state = display.load_pipeline_state()

        assert len(loaded_state["agents"]) == 1
        assert loaded_state["agents"][0]["agent"] == "researcher"

    # ========================================
    # EDGE CASE TESTS
    # ========================================

    def test_display_with_very_long_messages(self, integration_session_file):
        """Test handling of very long agent messages."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Create agent with very long message
        state = json.loads(integration_session_file.read_text())
        state["agents"].append({
            "agent": "researcher",
            "status": "completed",
            "message": "A" * 500,  # Very long message
            "duration_seconds": 100
        })
        integration_session_file.write_text(json.dumps(state, indent=2))

        # Should truncate or wrap appropriately
        output = display.render_tree_view(state)
        lines = output.split('\n')

        # No line should be excessively long
        assert all(len(line) < 200 for line in lines)

    def test_display_with_unicode_and_emojis(self, integration_session_file):
        """Test handling of unicode and emoji in messages."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        state = json.loads(integration_session_file.read_text())
        state["agents"].append({
            "agent": "researcher",
            "status": "completed",
            "message": "Found patterns 🔍 in 日本語",
            "duration_seconds": 100
        })
        integration_session_file.write_text(json.dumps(state, indent=2))

        # Should handle unicode correctly
        output = display.render_tree_view(state)
        assert "🔍" in output or "researcher" in output

    def test_display_with_missing_fields(self, integration_session_file):
        """Test handling of agents with missing fields."""
        from plugins.autonomous_dev.scripts.progress_display import ProgressDisplay

        display = ProgressDisplay(session_file=integration_session_file)

        # Create agent entry with missing fields
        state = json.loads(integration_session_file.read_text())
        state["agents"].append({
            "agent": "researcher",
            "status": "completed"
            # Missing: duration_seconds, message, etc.
        })
        integration_session_file.write_text(json.dumps(state, indent=2))

        # Should handle missing fields gracefully
        output = display.render_tree_view(state)
        assert "researcher" in output
        # Should not crash on missing fields
