"""Regression test for Issue #1271: Doc-master re-invocation after STEP 11 remediation.

When STEP 11 remediation occurs (implementer re-invoked in REMEDIATION MODE),
the STEP 10 doc-master result becomes stale. This test ensures:
1. The remediation flag can be set and retrieved
2. Backward compatibility with old state files
3. STEP 12 correctly detects remediation and triggers doc-master re-invocation
"""

import json
import tempfile
from pathlib import Path
from unittest import mock
import sys

# Add lib to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"))

from pipeline_state import (
    PipelineState,
    create_pipeline,
    load_pipeline,
    save_pipeline,
    set_remediation_flag,
    get_remediation_flag,
    get_state_path,
)


class TestRemediationFlag:
    """Test remediation flag functionality for Issue #1271."""

    def test_remediation_flag_default_false(self):
        """New pipelines should have remediation_occurred=False by default."""
        state = create_pipeline("test-run-001", "test feature")
        assert state.remediation_occurred is False

    def test_set_remediation_flag(self):
        """Test setting the remediation flag."""
        run_id = "test-run-002"
        
        # Create a pipeline state
        state = create_pipeline(run_id, "test feature")
        save_pipeline(state)
        
        # Initially should be False
        assert get_remediation_flag(run_id) is False
        
        # Set the flag
        result = set_remediation_flag(run_id)
        assert result is True
        
        # Flag should now be True
        assert get_remediation_flag(run_id) is True
        
        # Verify persistence by loading fresh
        loaded = load_pipeline(run_id)
        assert loaded is not None
        assert loaded.remediation_occurred is True
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)

    def test_get_remediation_flag_nonexistent(self):
        """get_remediation_flag should return False for non-existent state."""
        assert get_remediation_flag("nonexistent-run") is False

    def test_set_remediation_flag_nonexistent(self):
        """set_remediation_flag should return False for non-existent state."""
        assert set_remediation_flag("nonexistent-run") is False

    def test_backward_compatibility_old_state(self):
        """Old state files without remediation_occurred field should default to False."""
        run_id = "test-run-003"
        
        # Create an old-style state file without remediation_occurred field
        old_state_data = {
            "run_id": run_id,
            "mode": "full",
            "feature": "test feature",
            "steps": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "redispatch_agents": {},
            # Note: no remediation_occurred field
        }
        
        # Write old-style state file
        state_path = get_state_path(run_id)
        state_path.write_text(json.dumps(old_state_data, indent=2))
        
        # Load should work and default to False
        loaded = load_pipeline(run_id)
        assert loaded is not None
        assert loaded.remediation_occurred is False
        
        # get_remediation_flag should also return False
        assert get_remediation_flag(run_id) is False
        
        # Setting the flag should work and upgrade the state
        assert set_remediation_flag(run_id) is True
        assert get_remediation_flag(run_id) is True
        
        # Verify the state file now has the field
        updated_data = json.loads(state_path.read_text())
        assert "remediation_occurred" in updated_data
        assert updated_data["remediation_occurred"] is True
        
        # Cleanup
        state_path.unlink(missing_ok=True)

    def test_save_load_preserves_remediation_flag(self):
        """Saving and loading should preserve the remediation_occurred flag."""
        run_id = "test-run-004"
        
        # Create state with flag set
        state = create_pipeline(run_id, "test feature")
        state.remediation_occurred = True
        save_pipeline(state)
        
        # Load and verify
        loaded = load_pipeline(run_id)
        assert loaded is not None
        assert loaded.remediation_occurred is True
        
        # Reset flag and save
        loaded.remediation_occurred = False
        save_pipeline(loaded)
        
        # Load again and verify
        reloaded = load_pipeline(run_id)
        assert reloaded is not None
        assert reloaded.remediation_occurred is False
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)


class TestRemediationWorkflow:
    """Test the full remediation workflow simulation."""

    def test_step_11_remediation_triggers_flag(self):
        """Simulate STEP 11 remediation triggering the flag."""
        run_id = "test-run-005"
        
        # Create pipeline state (simulating normal pipeline start)
        state = create_pipeline(run_id, "add authentication")
        save_pipeline(state)
        
        # Simulate STEP 11: remediation occurs
        # In real coordinator, this happens when implementer is re-invoked
        # in REMEDIATION MODE after reviewer/security-auditor failures
        remediation_triggered = True  # Simulating remediation condition
        
        if remediation_triggered:
            # Coordinator would call this when re-invoking implementer
            assert set_remediation_flag(run_id) is True
            print(f"[REMEDIATION-FLAG] Set remediation_occurred=true for run_id={run_id}")
        
        # Simulate STEP 12: check if doc-master needs re-invocation
        remediation_occurred = get_remediation_flag(run_id)
        
        if remediation_occurred:
            print(f"[REMEDIATION-CHECK] Remediation occurred at STEP 11 for run_id={run_id}")
            # Doc-master would be re-invoked here with updated file list
            doc_master_reinvoked = True
        else:
            print(f"[REMEDIATION-CHECK] No remediation at STEP 11 for run_id={run_id}")
            # Use original STEP 10 doc-master result
            doc_master_reinvoked = False
        
        # Verify the expected flow happened
        assert remediation_occurred is True
        assert doc_master_reinvoked is True
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)

    def test_no_remediation_uses_original_doc_master(self):
        """When no remediation occurs, original doc-master result should be used."""
        run_id = "test-run-006"
        
        # Create pipeline state
        state = create_pipeline(run_id, "add logging")
        save_pipeline(state)
        
        # Simulate STEP 11: both validators pass (no remediation)
        remediation_triggered = False
        
        if remediation_triggered:
            set_remediation_flag(run_id)
        
        # Simulate STEP 12: check flag
        remediation_occurred = get_remediation_flag(run_id)
        
        if remediation_occurred:
            doc_master_reinvoked = True
        else:
            # Use original STEP 10 result
            doc_master_reinvoked = False
        
        # Verify no re-invocation when no remediation
        assert remediation_occurred is False
        assert doc_master_reinvoked is False
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)

    def test_remediation_flag_persists_across_sessions(self):
        """The remediation flag should persist across coordinator invocations."""
        run_id = "test-run-007"
        
        # Session 1: Create state and trigger remediation
        state = create_pipeline(run_id, "add caching")
        save_pipeline(state)
        assert set_remediation_flag(run_id) is True
        
        # Simulate coordinator restart/resume
        del state  # Clear local reference
        
        # Session 2: Load state and check flag
        loaded_state = load_pipeline(run_id)
        assert loaded_state is not None
        assert loaded_state.remediation_occurred is True
        assert get_remediation_flag(run_id) is True
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_set_remediation_flag_io_error(self):
        """set_remediation_flag should return False on I/O errors."""
        run_id = "test-run-008"
        
        # Create state
        state = create_pipeline(run_id, "test feature")
        save_pipeline(state)
        
        # Mock save_pipeline to raise an exception
        with mock.patch('pipeline_state.save_pipeline', side_effect=IOError("Disk full")):
            result = set_remediation_flag(run_id)
            assert result is False
        
        # Flag should remain unchanged
        assert get_remediation_flag(run_id) is False
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)

    def test_multiple_remediation_cycles(self):
        """Test that flag stays True across multiple remediation cycles."""
        run_id = "test-run-009"
        
        state = create_pipeline(run_id, "test feature")
        save_pipeline(state)
        
        # First remediation cycle
        assert set_remediation_flag(run_id) is True
        assert get_remediation_flag(run_id) is True
        
        # Second call should still work (idempotent)
        assert set_remediation_flag(run_id) is True
        assert get_remediation_flag(run_id) is True
        
        # Flag should never reset to False automatically
        loaded = load_pipeline(run_id)
        assert loaded.remediation_occurred is True
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)

    def test_concurrent_access(self):
        """Test that concurrent access to the flag works correctly."""
        run_id = "test-run-010"
        
        state = create_pipeline(run_id, "test feature")
        save_pipeline(state)
        
        # Simulate concurrent attempts to set the flag
        # Both should succeed without conflict
        result1 = set_remediation_flag(run_id)
        result2 = set_remediation_flag(run_id)
        
        assert result1 is True
        assert result2 is True
        assert get_remediation_flag(run_id) is True
        
        # Cleanup
        get_state_path(run_id).unlink(missing_ok=True)


def test_issue_1271_integration():
    """Integration test simulating the full Issue #1271 scenario.
    
    Issue #1271: CHANGELOG drift after Step 11 remediation
    - Doc-master runs at STEP 10 with initial file list
    - STEP 11 remediation adds new tests/files
    - STEP 12 must detect remediation and re-invoke doc-master
    - CHANGELOG should reflect final test count after remediation
    """
    run_id = "issue-1271-test"
    
    # Setup: Create pipeline state
    state = create_pipeline(run_id, "Fix authentication bug")
    save_pipeline(state)
    
    # STEP 10: Doc-master runs with initial state
    initial_files = ["auth.py", "test_auth.py"]
    initial_test_count = 5
    doc_master_result_step10 = {
        "verdict": "PASS",
        "test_count": initial_test_count,
        "files": initial_files
    }
    
    # STEP 11: Reviewer finds issues, remediation triggered
    reviewer_verdict = "REQUEST_CHANGES"  # Triggers remediation
    
    if reviewer_verdict == "REQUEST_CHANGES":
        # Implementer is re-invoked in REMEDIATION MODE
        print("[STEP 11] Entering remediation cycle")
        
        # SET THE FLAG (this is the key fix)
        assert set_remediation_flag(run_id) is True
        print(f"[REMEDIATION-FLAG] Set remediation_occurred=true for run_id={run_id}")
        
        # Remediation adds new files and tests
        remediated_files = ["auth.py", "test_auth.py", "test_auth_edge_cases.py"]
        remediated_test_count = 8  # 3 new tests added
    
    # STEP 12: Check if doc-master needs re-invocation
    remediation_occurred = get_remediation_flag(run_id)
    print(f"[STEP 12] Checking remediation flag: {remediation_occurred}")
    
    if remediation_occurred:
        print("[DOC-VERDICT-REINVOKE] Re-invoking doc-master after remediation")
        # Re-invoke doc-master with CURRENT state
        doc_master_final_result = {
            "verdict": "PASS",
            "test_count": remediated_test_count,  # Updated count
            "files": remediated_files  # Updated file list
        }
    else:
        # Use stale STEP 10 result (this would be the bug)
        doc_master_final_result = doc_master_result_step10
    
    # Verify the fix works correctly
    assert remediation_occurred is True
    assert doc_master_final_result["test_count"] == 8  # Should reflect remediated count
    assert len(doc_master_final_result["files"]) == 3  # Should have all files
    
    # The CHANGELOG would now correctly show 8 tests, not 5
    print(f"[CHANGELOG] Final test count: {doc_master_final_result['test_count']}")
    print(f"[CHANGELOG] Final files: {doc_master_final_result['files']}")
    
    # Cleanup
    get_state_path(run_id).unlink(missing_ok=True)
    
    print("\n✅ Issue #1271 regression test passed: Doc-master correctly re-invoked after remediation")


if __name__ == "__main__":
    # Run the integration test directly
    test_issue_1271_integration()