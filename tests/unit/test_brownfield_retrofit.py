"""
Unit tests for brownfield_retrofit.py - Core state management and phase coordination.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- State file operations (load/save/update)
- Phase prerequisite validation
- Phase coordination logic
- State file permissions (0o600)
- Corrupted state file recovery
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# THESE IMPORTS WILL FAIL - Implementation doesn't exist yet
from plugins.autonomous_dev.lib.brownfield_retrofit import (
    BrownfieldRetrofit,
    RetrofitPhase,
    RetrofitState,
    StateError,
)


class TestRetrofitState:
    """Test RetrofitState dataclass and operations."""

    def test_state_initialization_defaults(self):
        """Test state initializes with correct defaults."""
        state = RetrofitState()

        assert state.current_phase == RetrofitPhase.NOT_STARTED
        assert state.completed_phases == []
        assert state.analysis_report is None
        assert state.assessment_report is None
        assert state.migration_plan is None
        assert state.execution_results is None
        assert state.verification_report is None
        assert state.backup_path is None
        assert isinstance(state.metadata, dict)
        assert "created_at" in state.metadata

    def test_state_serialization_to_dict(self):
        """Test state can be serialized to dictionary."""
        state = RetrofitState(
            current_phase=RetrofitPhase.ANALYZE,
            completed_phases=[RetrofitPhase.ANALYZE],
        )

        data = state.to_dict()

        assert isinstance(data, dict)
        assert data["current_phase"] == "ANALYZE"
        assert data["completed_phases"] == ["ANALYZE"]
        assert "metadata" in data

    def test_state_deserialization_from_dict(self):
        """Test state can be deserialized from dictionary."""
        data = {
            "current_phase": "ASSESS",
            "completed_phases": ["ANALYZE", "ASSESS"],
            "analysis_report": {"tech_stack": ["python"]},
            "metadata": {"created_at": "2025-11-11T10:00:00"},
        }

        state = RetrofitState.from_dict(data)

        assert state.current_phase == RetrofitPhase.ASSESS
        assert len(state.completed_phases) == 2
        assert state.analysis_report["tech_stack"] == ["python"]

    def test_state_phase_completion_tracking(self):
        """Test phase completion can be tracked."""
        state = RetrofitState()

        state.mark_phase_complete(RetrofitPhase.ANALYZE)

        assert RetrofitPhase.ANALYZE in state.completed_phases
        assert state.current_phase == RetrofitPhase.ASSESS

    def test_state_phase_prerequisite_check(self):
        """Test prerequisite validation for phases."""
        state = RetrofitState(
            current_phase=RetrofitPhase.ANALYZE,
            completed_phases=[],
        )

        # Can execute current phase
        assert state.can_execute_phase(RetrofitPhase.ANALYZE)

        # Cannot skip ahead
        assert not state.can_execute_phase(RetrofitPhase.EXECUTE)


class TestBrownfieldRetrofit:
    """Test BrownfieldRetrofit main coordinator."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def retrofit_instance(self, temp_project_dir):
        """Create BrownfieldRetrofit instance."""
        return BrownfieldRetrofit(project_root=temp_project_dir)

    def test_initialization_creates_state_directory(self, temp_project_dir):
        """Test initialization creates .retrofit directory."""
        retrofit = BrownfieldRetrofit(project_root=temp_project_dir)

        state_dir = temp_project_dir / ".retrofit"
        assert state_dir.exists()
        assert state_dir.is_dir()

    def test_state_file_has_secure_permissions(self, retrofit_instance, temp_project_dir):
        """Test state file created with 0o600 permissions."""
        state_file = temp_project_dir / ".retrofit" / "state.json"

        # Create initial state
        retrofit_instance.save_state()

        # Check permissions (owner read/write only)
        assert state_file.exists()
        assert oct(state_file.stat().st_mode)[-3:] == "600"

    def test_load_state_from_existing_file(self, retrofit_instance, temp_project_dir):
        """Test loading state from existing state file."""
        state_file = temp_project_dir / ".retrofit" / "state.json"
        state_data = {
            "current_phase": "PLAN",
            "completed_phases": ["ANALYZE", "ASSESS"],
            "metadata": {"created_at": "2025-11-11T10:00:00"},
        }
        state_file.write_text(json.dumps(state_data))

        state = retrofit_instance.load_state()

        assert state.current_phase == RetrofitPhase.PLAN
        assert len(state.completed_phases) == 2

    def test_load_state_creates_new_if_missing(self, retrofit_instance):
        """Test loading state creates new state if file missing."""
        state = retrofit_instance.load_state()

        assert state.current_phase == RetrofitPhase.NOT_STARTED
        assert state.completed_phases == []

    def test_save_state_persists_to_file(self, retrofit_instance, temp_project_dir):
        """Test saving state persists to JSON file."""
        state_file = temp_project_dir / ".retrofit" / "state.json"

        retrofit_instance.state.current_phase = RetrofitPhase.ASSESS
        retrofit_instance.save_state()

        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["current_phase"] == "ASSESS"

    def test_update_state_saves_automatically(self, retrofit_instance, temp_project_dir):
        """Test updating state automatically saves."""
        state_file = temp_project_dir / ".retrofit" / "state.json"

        retrofit_instance.update_state(
            current_phase=RetrofitPhase.PLAN,
            analysis_report={"tech_stack": ["python"]},
        )

        # Verify saved to disk
        data = json.loads(state_file.read_text())
        assert data["current_phase"] == "PLAN"
        assert data["analysis_report"]["tech_stack"] == ["python"]

    def test_corrupted_state_file_recovery(self, retrofit_instance, temp_project_dir):
        """Test recovery from corrupted state file."""
        state_file = temp_project_dir / ".retrofit" / "state.json"
        state_file.write_text("{ invalid json }")

        # Should create backup and return new state
        state = retrofit_instance.load_state()

        assert state.current_phase == RetrofitPhase.NOT_STARTED
        backup_file = temp_project_dir / ".retrofit" / "state.json.backup"
        assert backup_file.exists()

    def test_phase_prerequisite_validation_enforced(self, retrofit_instance):
        """Test phase prerequisites are enforced."""
        # Try to skip to EXECUTE without completing earlier phases
        with pytest.raises(StateError, match="Prerequisites not met"):
            retrofit_instance.execute_phase(RetrofitPhase.EXECUTE)

    def test_phase_coordination_workflow(self, retrofit_instance):
        """Test phase coordination follows correct order."""
        # Start with ANALYZE
        retrofit_instance.state.current_phase = RetrofitPhase.ANALYZE

        # Complete ANALYZE
        retrofit_instance.complete_phase(RetrofitPhase.ANALYZE)

        # Should advance to ASSESS
        assert retrofit_instance.state.current_phase == RetrofitPhase.ASSESS
        assert RetrofitPhase.ANALYZE in retrofit_instance.state.completed_phases

    def test_get_current_phase_status(self, retrofit_instance):
        """Test getting current phase status."""
        retrofit_instance.state.current_phase = RetrofitPhase.PLAN
        retrofit_instance.state.completed_phases = [RetrofitPhase.ANALYZE, RetrofitPhase.ASSESS]

        status = retrofit_instance.get_phase_status()

        assert status["current_phase"] == "PLAN"
        assert len(status["completed_phases"]) == 2
        assert status["remaining_phases"] == ["EXECUTE", "VERIFY"]

    def test_resume_from_saved_state(self, retrofit_instance, temp_project_dir):
        """Test workflow can resume from saved state."""
        # Simulate partial completion
        retrofit_instance.update_state(
            current_phase=RetrofitPhase.PLAN,
            completed_phases=[RetrofitPhase.ANALYZE, RetrofitPhase.ASSESS],
        )

        # Create new instance (simulates restart)
        new_retrofit = BrownfieldRetrofit(project_root=temp_project_dir)
        new_retrofit.load_state()

        assert new_retrofit.state.current_phase == RetrofitPhase.PLAN
        assert len(new_retrofit.state.completed_phases) == 2

    def test_reset_workflow_clears_state(self, retrofit_instance):
        """Test resetting workflow clears state."""
        retrofit_instance.update_state(
            current_phase=RetrofitPhase.EXECUTE,
            completed_phases=[RetrofitPhase.ANALYZE, RetrofitPhase.ASSESS, RetrofitPhase.PLAN],
        )

        retrofit_instance.reset()

        assert retrofit_instance.state.current_phase == RetrofitPhase.NOT_STARTED
        assert retrofit_instance.state.completed_phases == []

    @patch("plugins.autonomous_dev.lib.security_utils.validate_path")
    def test_path_validation_on_initialization(self, mock_validate, temp_project_dir):
        """Test project root path is validated on initialization."""
        BrownfieldRetrofit(project_root=temp_project_dir)

        mock_validate.assert_called_once()
        call_args = mock_validate.call_args[0]
        assert call_args[0] == str(temp_project_dir)

    def test_state_metadata_includes_timestamps(self, retrofit_instance):
        """Test state metadata includes creation and update timestamps."""
        retrofit_instance.save_state()

        assert "created_at" in retrofit_instance.state.metadata
        assert "updated_at" in retrofit_instance.state.metadata

    def test_error_handling_for_permission_denied(self, temp_project_dir):
        """Test error handling when state directory not writable."""
        state_dir = temp_project_dir / ".retrofit"
        state_dir.mkdir()
        state_dir.chmod(0o444)  # Read-only

        try:
            retrofit = BrownfieldRetrofit(project_root=temp_project_dir)
            with pytest.raises(StateError, match="Permission denied"):
                retrofit.save_state()
        finally:
            state_dir.chmod(0o755)  # Cleanup
