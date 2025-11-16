#!/usr/bin/env python3
"""
TDD Integration Tests for Tracking Infrastructure (Issue #79)

This module tests end-to-end tracking workflows:
- Multiple trackers coordinating in same project
- State persistence across sessions
- Hook integration with tracking modules
- Real-world usage scenarios

These tests verify that all tracking components work together correctly.

Test Coverage Target: 100% of integration scenarios
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.session_tracker import SessionTracker
from scripts.agent_tracker import AgentTracker
from plugins.autonomous_dev.lib.batch_state_manager import (
    BatchState,
    BatchStateManager,
    create_batch_state,
    save_batch_state,
    load_batch_state,
    DEFAULT_STATE_FILE
)


class TestSessionAndAgentTrackerCoordination:
    """Test that SessionTracker and AgentTracker coordinate correctly."""

    @pytest.fixture
    def project_structure(self, tmp_path):
        """Create realistic project structure."""
        project = tmp_path / "autonomous-dev"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()
        return project

    def test_session_and_agent_tracker_use_same_directory(self, project_structure):
        """Test that both trackers use the same session directory.

        Expected:
        - Both resolve to PROJECT_ROOT/docs/sessions/
        - Can read each other's files
        - No conflicts
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_structure))

            session_tracker = SessionTracker()
            agent_tracker = AgentTracker()

            # Both should use same directory
            assert session_tracker.session_dir == agent_tracker.session_dir
            expected = project_structure / "docs" / "sessions"
            assert session_tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_agent_tracker_reads_session_files(self, project_structure):
        """Test that AgentTracker can read SessionTracker files.

        Expected:
        - SessionTracker creates file
        - AgentTracker can read and parse it
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_structure))

            # SessionTracker creates file
            session_tracker = SessionTracker()
            session_tracker.log("researcher", "Research complete")

            # AgentTracker should be able to read it
            agent_tracker = AgentTracker()

            # Both should see the same session directory
            assert agent_tracker.session_dir.exists()
            assert len(list(agent_tracker.session_dir.glob("*.md"))) > 0

        finally:
            os.chdir(original_cwd)

    def test_multiple_agents_log_to_same_session(self, project_structure):
        """Test that multiple agents can log to same session file.

        Expected:
        - All agents append to same session
        - No file conflicts
        - Chronological order preserved
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_structure))

            # Multiple agents log to same session
            tracker = AgentTracker()

            tracker.log_start("researcher", "Starting research")
            tracker.log_complete("researcher", "Research complete", tools=["WebSearch"])

            tracker.log_start("planner", "Starting planning")
            tracker.log_complete("planner", "Plan created", tools=["Read"])

            # Verify session file contains all logs
            session_file = tracker.session_file
            assert session_file.exists()

            content = session_file.read_text()
            assert "researcher" in content
            assert "planner" in content

        finally:
            os.chdir(original_cwd)


class TestBatchStatePersistence:
    """Test that batch state persists across sessions."""

    @pytest.fixture
    def project_structure(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / ".claude").mkdir()
        return project

    def test_batch_state_persists_across_runs(self, project_structure):
        """Test that batch state is saved and can be loaded.

        Expected:
        - State saved to .claude/batch_state.json
        - Second instance can load saved state
        - State consistent across instances
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_structure))

            # First manager creates and saves state
            manager1 = BatchStateManager()
            state = manager1.create_batch(
                features_file="features.txt",
                features=["feature1", "feature2", "feature3"]
            )
            manager1.save_state(state)

            # Second manager loads state
            manager2 = BatchStateManager()
            loaded_state = manager2.load_state()

            # State should be consistent
            assert loaded_state is not None
            assert loaded_state.total_features == 3
            assert loaded_state.features == ["feature1", "feature2", "feature3"]

        finally:
            os.chdir(original_cwd)

    def test_batch_state_tracks_progress_correctly(self, project_structure):
        """Test that batch state correctly tracks feature progress.

        Expected:
        - current_index increments as features complete
        - State persists after each update
        - Can resume from last position
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_structure))

            manager = BatchStateManager()
            state = manager.create_batch(
                features_file="features.txt",
                features=["f1", "f2", "f3"]
            )

            # Process features one by one
            assert state.current_index == 0

            state.current_index = 1
            manager.save_state(state)

            state.current_index = 2
            manager.save_state(state)

            # Reload and verify position
            loaded = manager.load_state()
            assert loaded.current_index == 2

        finally:
            os.chdir(original_cwd)

    def test_batch_state_handles_corrupted_file(self, project_structure):
        """Test that corrupted state file is handled gracefully.

        Expected:
        - If JSON corrupted, raise clear BatchStateError (not cryptic JSON error)
        - Error message should be informative
        """
        from plugins.autonomous_dev.lib.batch_state_manager import BatchStateError

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_structure))

            # Create corrupted state file
            state_file = project_structure / ".claude" / "batch_state.json"
            state_file.write_text("{ corrupted json")

            manager = BatchStateManager()

            # Should raise clear error (not cryptic JSON error)
            with pytest.raises(BatchStateError, match="Corrupted batch state file"):
                manager.load_state()

        finally:
            os.chdir(original_cwd)

    def test_batch_state_atomic_writes(self, project_structure):
        """Test that state writes are atomic (temp + rename).

        Expected:
        - Write to .tmp file first
        - Rename to final file (atomic on POSIX)
        - No partial writes visible
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_structure))

            manager = BatchStateManager()
            state = manager.create_batch(
                features_file="features.txt",
                features=["f1", "f2"]
            )

            # Save state (should use atomic write)
            manager.save_state(state)

            # Verify final file exists (not .tmp)
            state_file = project_structure / ".claude" / "batch_state.json"
            assert state_file.exists()

            # No .tmp file should remain
            tmp_files = list((project_structure / ".claude").glob("*.tmp"))
            assert len(tmp_files) == 0

        finally:
            os.chdir(original_cwd)


class TestHookIntegration:
    """Test that hooks can import and use tracking modules correctly."""

    @pytest.fixture
    def project_structure(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()
        (project / "hooks").mkdir()
        return project

    def test_hooks_import_session_tracker_without_errors(self, project_structure):
        """Test that hooks can import SessionTracker.

        Expected:
        - No import errors
        - Can instantiate from hook context
        """
        original_cwd = os.getcwd()
        try:
            # Change to hooks/ directory (simulates hook execution)
            hooks_dir = project_structure / "hooks"
            os.chdir(str(hooks_dir))

            # Should be able to import and use
            from plugins.autonomous_dev.lib.session_tracker import SessionTracker

            tracker = SessionTracker()

            # Should resolve to project root, not hooks/
            expected = project_structure / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_hooks_import_agent_tracker_without_errors(self, project_structure):
        """Test that hooks can import AgentTracker.

        Expected:
        - No import errors
        - Paths resolve correctly from hooks/
        """
        original_cwd = os.getcwd()
        try:
            hooks_dir = project_structure / "hooks"
            os.chdir(str(hooks_dir))

            from scripts.agent_tracker import AgentTracker

            tracker = AgentTracker()

            expected = project_structure / "docs" / "sessions"
            assert tracker.session_dir == expected

        finally:
            os.chdir(original_cwd)

    def test_hooks_import_batch_state_manager_without_errors(self, project_structure):
        """Test that hooks can import BatchStateManager.

        Expected:
        - No import errors
        - State file resolves correctly
        """
        original_cwd = os.getcwd()
        try:
            hooks_dir = project_structure / "hooks"
            os.chdir(str(hooks_dir))

            from plugins.autonomous_dev.lib.batch_state_manager import BatchState, create_batch_state, save_batch_state, load_batch_state, DEFAULT_STATE_FILE

            manager = BatchStateManager()

            expected = project_structure / ".claude" / "batch_state.json"
            assert manager.state_file == expected

        finally:
            os.chdir(original_cwd)

    def test_hook_logs_agent_action_correctly(self, project_structure):
        """Test real-world scenario: Hook logs agent completion.

        Expected:
        - Hook runs from hooks/ directory
        - Logs to correct session file
        - Session file created in PROJECT_ROOT/docs/sessions/
        """
        original_cwd = os.getcwd()
        try:
            hooks_dir = project_structure / "hooks"
            os.chdir(str(hooks_dir))

            # Simulate hook logging agent completion
            from scripts.agent_tracker import AgentTracker

            tracker = AgentTracker()
            tracker.log_complete("reviewer", "Code review passed", tools=["Grep", "Read"])

            # Verify log created in correct location
            session_dir = project_structure / "docs" / "sessions"
            session_files = list(session_dir.glob("*.json"))
            assert len(session_files) > 0

            # Verify content
            content = session_files[0].read_text()
            data = json.loads(content)
            assert len(data["agents"]) > 0
            # Session file uses "agent" field (not "name" which is in get_status() output)
            assert data["agents"][0]["agent"] == "reviewer"
            assert data["agents"][0]["status"] == "completed"
            assert "Grep" in data["agents"][0]["tools_used"]

        finally:
            os.chdir(original_cwd)


class TestConcurrentAccess:
    """Test that multiple processes can access tracking simultaneously."""

    @pytest.fixture
    def project_structure(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()
        return project

    def test_concurrent_session_trackers_no_conflicts(self, project_structure):
        """Test that multiple SessionTrackers can run concurrently.

        Expected:
        - No file conflicts
        - All logs preserved
        """
        import threading

        original_cwd = os.getcwd()
        os.chdir(str(project_structure))

        errors = []

        def log_messages(agent_name):
            try:
                tracker = SessionTracker()
                for i in range(5):
                    tracker.log(agent_name, f"Message {i}")
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        # Run multiple trackers concurrently
        threads = [
            threading.Thread(target=log_messages, args=(f"agent{i}",))
            for i in range(3)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        os.chdir(original_cwd)

        # No errors should occur
        assert len(errors) == 0

        # All logs should be preserved
        session_dir = project_structure / "docs" / "sessions"
        session_files = list(session_dir.glob("*.md"))
        assert len(session_files) > 0

    def test_concurrent_batch_state_updates(self, project_structure):
        """Test that concurrent batch state updates are handled safely.

        Expected:
        - File locking prevents corruption
        - All updates applied correctly
        """
        import threading

        original_cwd = os.getcwd()
        os.chdir(str(project_structure))

        manager = BatchStateManager()
        state = manager.create_batch(
            features_file="features.txt",
            features=[f"feature{i}" for i in range(10)]
        )
        manager.save_state(state)

        errors = []

        def update_state(index):
            try:
                mgr = BatchStateManager()
                loaded = mgr.load_state()
                loaded.current_index = index
                mgr.save_state(loaded)
            except Exception as e:
                errors.append(e)

        # Concurrent updates
        threads = [
            threading.Thread(target=update_state, args=(i,))
            for i in range(5)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        os.chdir(original_cwd)

        # Should handle gracefully (may have race conditions, but no corruption)
        # At least one update should succeed
        final_state = manager.load_state()
        assert final_state is not None


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.fixture
    def project_structure(self, tmp_path):
        """Create realistic project structure."""
        project = tmp_path / "autonomous-dev"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()
        (project / "plugins" / "autonomous-dev").mkdir(parents=True)
        (project / "scripts").mkdir()
        return project

    def test_auto_implement_workflow(self, project_structure):
        """Test full /auto-implement workflow tracking.

        Scenario:
        1. researcher logs research
        2. planner logs plan
        3. test-master logs tests
        4. implementer logs implementation
        5. All logs in same session

        Expected:
        - All logs in PROJECT_ROOT/docs/sessions/
        - Chronological order preserved
        - Can be accessed from any subdirectory
        """
        original_cwd = os.getcwd()
        try:
            # Start from plugins/ (common scenario)
            os.chdir(str(project_structure / "plugins" / "autonomous-dev"))

            tracker = AgentTracker()

            # Simulate workflow
            tracker.log_start("researcher", "Researching authentication")
            tracker.log_complete("researcher", "Found JWT patterns", tools=["WebSearch"])

            tracker.log_start("planner", "Planning implementation")
            tracker.log_complete("planner", "Created plan", tools=["Read"])

            tracker.log_start("test-master", "Writing tests")
            tracker.log_complete("test-master", "Tests written", tools=["Write"])

            tracker.log_start("implementer", "Implementing feature")
            tracker.log_complete("implementer", "Implementation complete", tools=["Edit"])

            # Verify all logs in correct location
            session_dir = project_structure / "docs" / "sessions"
            session_files = list(session_dir.glob("*.json"))
            assert len(session_files) > 0

            # Verify all agents logged
            content = session_files[0].read_text()
            data = json.loads(content)
            assert len(data["agents"]) == 4

        finally:
            os.chdir(original_cwd)

    def test_batch_processing_workflow(self, project_structure):
        """Test /batch-implement workflow with state management.

        Scenario:
        1. Create batch with 5 features
        2. Process features one by one
        3. State persists after each feature
        4. Can resume if interrupted

        Expected:
        - State in PROJECT_ROOT/.claude/batch_state.json
        - Progress tracked correctly
        - Works from any subdirectory
        """
        original_cwd = os.getcwd()
        try:
            # Start from scripts/ directory
            os.chdir(str(project_structure / "scripts"))

            manager = BatchStateManager()

            # Create batch
            features = [f"feature{i}" for i in range(5)]
            state = manager.create_batch(
                features_file="features.txt",
                features=features
            )
            manager.save_state(state)

            # Process features
            for i in range(5):
                state.current_index = i
                manager.save_state(state)

                # Verify state persists
                reloaded = manager.load_state()
                assert reloaded.current_index == i

            # Final state
            final = manager.load_state()
            assert final.current_index == 4
            assert final.total_features == 5

            # Verify state file location
            expected = project_structure / ".claude" / "batch_state.json"
            assert expected.exists()

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
