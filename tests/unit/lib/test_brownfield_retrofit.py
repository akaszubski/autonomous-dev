#!/usr/bin/env python3
"""
Unit tests for brownfield_retrofit.py.

Tests the brownfield retrofit workflow including:
- RetrofitPhase enum and phase ordering
- RetrofitState state management
- BrownfieldRetrofit coordinator
- Phase prerequisites and transitions
- State persistence and recovery

Issue: #234 (Test coverage improvement)
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.brownfield_retrofit import (
    RetrofitPhase,
    RetrofitState,
    BrownfieldRetrofit,
    PHASE_ORDER,
    PHASE_PREREQUISITES,
    create_retrofit_instance,
)
from plugins.autonomous_dev.lib.exceptions import StateError


class TestRetrofitPhaseEnum:
    """Test RetrofitPhase enum."""

    def test_all_phases_exist(self):
        """All expected phases should exist."""
        assert RetrofitPhase.NOT_STARTED.value == "NOT_STARTED"
        assert RetrofitPhase.ANALYZE.value == "ANALYZE"
        assert RetrofitPhase.ASSESS.value == "ASSESS"
        assert RetrofitPhase.PLAN.value == "PLAN"
        assert RetrofitPhase.EXECUTE.value == "EXECUTE"
        assert RetrofitPhase.VERIFY.value == "VERIFY"
        assert RetrofitPhase.COMPLETE.value == "COMPLETE"

    def test_phase_str(self):
        """__str__ returns value."""
        assert str(RetrofitPhase.ANALYZE) == "ANALYZE"

    def test_from_string_valid(self):
        """Convert valid string to phase."""
        phase = RetrofitPhase.from_string("ANALYZE")
        assert phase == RetrofitPhase.ANALYZE

    def test_from_string_invalid(self):
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid phase"):
            RetrofitPhase.from_string("INVALID")


class TestPhaseOrder:
    """Test phase ordering and prerequisites."""

    def test_phase_order_count(self):
        """Should have 7 phases total."""
        assert len(PHASE_ORDER) == 7

    def test_phase_order_sequence(self):
        """Phases should be in correct order."""
        assert PHASE_ORDER[0] == RetrofitPhase.NOT_STARTED
        assert PHASE_ORDER[1] == RetrofitPhase.ANALYZE
        assert PHASE_ORDER[2] == RetrofitPhase.ASSESS
        assert PHASE_ORDER[3] == RetrofitPhase.PLAN
        assert PHASE_ORDER[4] == RetrofitPhase.EXECUTE
        assert PHASE_ORDER[5] == RetrofitPhase.VERIFY
        assert PHASE_ORDER[6] == RetrofitPhase.COMPLETE

    def test_analyze_has_no_prerequisites(self):
        """ANALYZE phase has no prerequisites."""
        assert PHASE_PREREQUISITES[RetrofitPhase.ANALYZE] == []

    def test_assess_requires_analyze(self):
        """ASSESS requires ANALYZE."""
        assert RetrofitPhase.ANALYZE in PHASE_PREREQUISITES[RetrofitPhase.ASSESS]

    def test_plan_requires_analyze_and_assess(self):
        """PLAN requires both ANALYZE and ASSESS."""
        prereqs = PHASE_PREREQUISITES[RetrofitPhase.PLAN]
        assert RetrofitPhase.ANALYZE in prereqs
        assert RetrofitPhase.ASSESS in prereqs

    def test_complete_requires_all_phases(self):
        """COMPLETE requires all previous phases."""
        prereqs = PHASE_PREREQUISITES[RetrofitPhase.COMPLETE]
        assert len(prereqs) == 5  # All phases except NOT_STARTED and COMPLETE


class TestRetrofitState:
    """Test RetrofitState dataclass."""

    def test_default_state(self):
        """Default state is NOT_STARTED."""
        state = RetrofitState()
        assert state.current_phase == RetrofitPhase.NOT_STARTED
        assert state.completed_phases == []

    def test_state_with_phase(self):
        """Create state with specific phase."""
        state = RetrofitState(current_phase=RetrofitPhase.ANALYZE)
        assert state.current_phase == RetrofitPhase.ANALYZE

    def test_metadata_timestamps(self):
        """Metadata should have timestamps."""
        state = RetrofitState()
        assert "created_at" in state.metadata
        assert "updated_at" in state.metadata

    def test_to_dict(self):
        """Serialize state to dictionary."""
        state = RetrofitState(
            current_phase=RetrofitPhase.PLAN,
            completed_phases=[RetrofitPhase.ANALYZE, RetrofitPhase.ASSESS]
        )
        d = state.to_dict()
        assert d["current_phase"] == "PLAN"
        assert "ANALYZE" in d["completed_phases"]
        assert "ASSESS" in d["completed_phases"]

    def test_from_dict(self):
        """Deserialize state from dictionary."""
        data = {
            "current_phase": "EXECUTE",
            "completed_phases": ["ANALYZE", "ASSESS", "PLAN"],
            "analysis_report": {"key": "value"},
            "metadata": {"custom": "data"}
        }
        state = RetrofitState.from_dict(data)
        assert state.current_phase == RetrofitPhase.EXECUTE
        assert len(state.completed_phases) == 3
        assert state.analysis_report == {"key": "value"}

    def test_mark_phase_complete(self):
        """Mark phase as complete advances state."""
        state = RetrofitState()
        state.mark_phase_complete(RetrofitPhase.ANALYZE)
        assert RetrofitPhase.ANALYZE in state.completed_phases
        assert state.current_phase == RetrofitPhase.ASSESS

    def test_mark_phase_complete_idempotent(self):
        """Marking same phase twice is idempotent."""
        state = RetrofitState()
        state.mark_phase_complete(RetrofitPhase.ANALYZE)
        state.mark_phase_complete(RetrofitPhase.ANALYZE)
        # Should only appear once
        assert state.completed_phases.count(RetrofitPhase.ANALYZE) == 1

    def test_can_execute_phase_no_prereqs(self):
        """Can execute phase with no prerequisites."""
        state = RetrofitState()
        assert state.can_execute_phase(RetrofitPhase.ANALYZE) is True

    def test_can_execute_phase_with_prereqs_met(self):
        """Can execute phase when prerequisites met."""
        state = RetrofitState(completed_phases=[RetrofitPhase.ANALYZE])
        assert state.can_execute_phase(RetrofitPhase.ASSESS) is True

    def test_cannot_execute_phase_prereqs_not_met(self):
        """Cannot execute phase when prerequisites not met."""
        state = RetrofitState()
        assert state.can_execute_phase(RetrofitPhase.ASSESS) is False

    def test_backup_path_serialization(self):
        """Backup path serializes correctly."""
        state = RetrofitState(backup_path=Path("/tmp/backup"))
        d = state.to_dict()
        assert d["backup_path"] == "/tmp/backup"

    def test_from_dict_with_backup_path(self):
        """Deserialize backup path."""
        data = {
            "current_phase": "ANALYZE",
            "completed_phases": [],
            "backup_path": "/tmp/backup",
            "metadata": {}
        }
        state = RetrofitState.from_dict(data)
        assert state.backup_path == Path("/tmp/backup")


class TestBrownfieldRetrofit:
    """Test BrownfieldRetrofit coordinator."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        return project_dir

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_init_creates_state_dir(self, mock_audit, mock_validate, temp_project):
        """Initialize creates .retrofit directory."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        assert (temp_project / ".retrofit").exists()

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_init_loads_existing_state(self, mock_audit, mock_validate, temp_project):
        """Initialize loads existing state file."""
        mock_validate.return_value = str(temp_project)

        # Create state directory and file
        state_dir = temp_project / ".retrofit"
        state_dir.mkdir()
        state_file = state_dir / "state.json"
        state_file.write_text(json.dumps({
            "current_phase": "PLAN",
            "completed_phases": ["ANALYZE", "ASSESS"],
            "metadata": {}
        }))

        retrofit = BrownfieldRetrofit(temp_project)

        assert retrofit.state.current_phase == RetrofitPhase.PLAN
        assert len(retrofit.state.completed_phases) == 2

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_save_state(self, mock_audit, mock_validate, temp_project):
        """Save state persists to file."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.state.current_phase = RetrofitPhase.ANALYZE
        retrofit.save_state()

        state_file = temp_project / ".retrofit" / "state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["current_phase"] == "ANALYZE"

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_update_state(self, mock_audit, mock_validate, temp_project):
        """Update state with kwargs."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.update_state(analysis_report={"findings": "test"})

        assert retrofit.state.analysis_report == {"findings": "test"}

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_update_state_phase_conversion(self, mock_audit, mock_validate, temp_project):
        """Update state converts string phases."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.update_state(current_phase="PLAN")

        assert retrofit.state.current_phase == RetrofitPhase.PLAN

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_get_phase_status(self, mock_audit, mock_validate, temp_project):
        """Get phase status report."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.state.completed_phases = [RetrofitPhase.ANALYZE]
        retrofit.state.current_phase = RetrofitPhase.ASSESS

        status = retrofit.get_phase_status()

        assert status["current_phase"] == "ASSESS"
        assert "ANALYZE" in status["completed_phases"]
        assert status["total_phases"] == 5  # Excluding NOT_STARTED and COMPLETE

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_execute_phase_success(self, mock_audit, mock_validate, temp_project):
        """Execute phase when prerequisites met."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)

        # ANALYZE has no prerequisites
        retrofit.execute_phase(RetrofitPhase.ANALYZE)

        # Should not raise

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_execute_phase_fails_prereqs(self, mock_audit, mock_validate, temp_project):
        """Execute phase fails when prerequisites not met."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)

        with pytest.raises(StateError, match="Prerequisites not met"):
            retrofit.execute_phase(RetrofitPhase.ASSESS)

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_complete_phase(self, mock_audit, mock_validate, temp_project):
        """Complete phase advances workflow."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)

        retrofit.complete_phase(RetrofitPhase.ANALYZE)

        assert RetrofitPhase.ANALYZE in retrofit.state.completed_phases
        assert retrofit.state.current_phase == RetrofitPhase.ASSESS

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_reset(self, mock_audit, mock_validate, temp_project):
        """Reset workflow to initial state."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.complete_phase(RetrofitPhase.ANALYZE)
        retrofit.complete_phase(RetrofitPhase.ASSESS)

        retrofit.reset()

        assert retrofit.state.current_phase == RetrofitPhase.NOT_STARTED
        assert retrofit.state.completed_phases == []

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_corrupted_state_recovery(self, mock_audit, mock_validate, temp_project):
        """Recover from corrupted state file."""
        mock_validate.return_value = str(temp_project)

        # Create corrupted state file
        state_dir = temp_project / ".retrofit"
        state_dir.mkdir()
        state_file = state_dir / "state.json"
        state_file.write_text("{ invalid json")

        retrofit = BrownfieldRetrofit(temp_project)

        # Should recover with new state
        assert retrofit.state.current_phase == RetrofitPhase.NOT_STARTED
        # Backup should be created
        assert (state_dir / "state.json.backup").exists()


class TestBrownfieldRetrofitEdgeCases:
    """Test edge cases for BrownfieldRetrofit."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project_dir = tmp_path / "edge_project"
        project_dir.mkdir()
        return project_dir

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_progress_percent_calculation(self, mock_audit, mock_validate, temp_project):
        """Progress percentage calculation."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.state.completed_phases = [
            RetrofitPhase.ANALYZE,
            RetrofitPhase.ASSESS
        ]

        status = retrofit.get_phase_status()

        # 2 out of 5 phases = 40%
        assert status["progress_percent"] == 40.0

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_state_permissions_set(self, mock_audit, mock_validate, temp_project):
        """State file should have secure permissions."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.save_state()

        state_file = temp_project / ".retrofit" / "state.json"
        # 0o600 = user read/write only
        mode = state_file.stat().st_mode & 0o777
        assert mode == 0o600

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_remaining_phases(self, mock_audit, mock_validate, temp_project):
        """Get remaining phases in status."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)
        retrofit.state.completed_phases = [RetrofitPhase.ANALYZE]
        retrofit.state.current_phase = RetrofitPhase.ASSESS

        status = retrofit.get_phase_status()

        # PLAN, EXECUTE, VERIFY remaining
        assert "PLAN" in status["remaining_phases"]
        assert "EXECUTE" in status["remaining_phases"]
        assert "VERIFY" in status["remaining_phases"]
        # NOT_STARTED and COMPLETE excluded
        assert "NOT_STARTED" not in status["remaining_phases"]
        assert "COMPLETE" not in status["remaining_phases"]

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_full_workflow(self, mock_audit, mock_validate, temp_project):
        """Complete full workflow through all phases."""
        mock_validate.return_value = str(temp_project)
        retrofit = BrownfieldRetrofit(temp_project)

        # Execute all phases in order
        retrofit.execute_phase(RetrofitPhase.ANALYZE)
        retrofit.complete_phase(RetrofitPhase.ANALYZE)

        retrofit.execute_phase(RetrofitPhase.ASSESS)
        retrofit.complete_phase(RetrofitPhase.ASSESS)

        retrofit.execute_phase(RetrofitPhase.PLAN)
        retrofit.complete_phase(RetrofitPhase.PLAN)

        retrofit.execute_phase(RetrofitPhase.EXECUTE)
        retrofit.complete_phase(RetrofitPhase.EXECUTE)

        retrofit.execute_phase(RetrofitPhase.VERIFY)
        retrofit.complete_phase(RetrofitPhase.VERIFY)

        assert retrofit.state.current_phase == RetrofitPhase.COMPLETE
        assert len(retrofit.state.completed_phases) == 5


class TestCreateRetrofitInstance:
    """Test convenience function."""

    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.validate_path')
    @patch('plugins.autonomous_dev.lib.brownfield_retrofit.security_utils.audit_log')
    def test_create_instance(self, mock_audit, mock_validate, tmp_path):
        """Create instance via convenience function."""
        project_dir = tmp_path / "test"
        project_dir.mkdir()
        mock_validate.return_value = str(project_dir)

        retrofit = create_retrofit_instance(project_dir)

        assert isinstance(retrofit, BrownfieldRetrofit)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
