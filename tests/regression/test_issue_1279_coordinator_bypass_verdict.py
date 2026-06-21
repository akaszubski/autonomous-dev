"""Regression test for coordinator bypass verdict creation (Issue #1279).

When the drain-queue coordinator skips plan-critic for mechanical extensions,
it must create a machine-readable audit trail via both pipeline state and
a verdict file.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Add lib to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"))

from pipeline_completion_state import (
    record_plan_critic_skipped,
    write_coordinator_bypass_verdict,
    _read_state
)


def test_write_coordinator_bypass_verdict_creates_valid_file():
    """Verify coordinator bypass verdict file has correct structure."""
    original_cwd = Path.cwd()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            
            # Write a coordinator bypass verdict
            write_coordinator_bypass_verdict(
                issue_number=1279,
                bypass_reason="mechanical extension test",
                plan_summary="Add test coverage for bypass logging"
            )
            
            # Verify file exists and loads
            verdict_path = Path(".claude/plan_critic_verdict.json")
            assert verdict_path.exists(), "Verdict file should exist"
            
            with open(verdict_path) as f:
                verdict = json.load(f)
            
            # Verify required fields
            assert verdict["verdict"] == "COORDINATOR_BYPASS"
            assert verdict["composite_score"] == 0.0
            assert "timestamp" in verdict
            assert len(verdict["reasoning"]) >= 100, f"Reasoning too short: {len(verdict['reasoning'])} chars"
            
            # Verify axis_scores has >= 3 entries (hook requirement)
            assert len(verdict["axis_scores"]) >= 3, f"Not enough axis scores: {len(verdict['axis_scores'])}"
            assert verdict["axis_scores"]["coordinator_bypass"] == 0
            assert verdict["axis_scores"]["skip_reason_documented"] == 1
            assert verdict["axis_scores"]["audit_trail_present"] == 1
            
            # Verify bypass metadata
            assert verdict["bypass_metadata"]["issue_number"] == 1279
            assert verdict["bypass_metadata"]["bypass_reason"] == "mechanical extension test"
            assert verdict["bypass_metadata"]["plan_summary"] == "Add test coverage for bypass logging"
            
        finally:
            os.chdir(original_cwd)


def test_record_plan_critic_skipped_with_bypass_reason_stores_reason():
    """Verify bypass reason is stored in pipeline state."""
    original_cwd = Path.cwd()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            
            # Use unique session ID to avoid /tmp pollution
            session_id = f"test_bypass_reason_{os.getpid()}"
            
            # Record skip with bypass reason
            record_plan_critic_skipped(
                session_id,
                issue_number=1279,
                bypass_reason="mechanical extension: adding tests"
            )
            
            # Read state and verify bypass reason stored
            state = _read_state(session_id)
            assert state is not None, "State should exist"
            
            # Check bypass reason stored under issue key
            reasons = state.get("plan_critic_bypass_reason", {})
            assert reasons.get("1279") == "mechanical extension: adding tests"
            
            # Check bypass reason also stored under "0" scope (dual-write)
            assert reasons.get("0") == "mechanical extension: adding tests"
            
            # Verify plan_critic_skipped marker also set
            skipped = state.get("plan_critic_skipped", {})
            assert skipped.get("1279") is True
            assert skipped.get("0") is True
            
        finally:
            os.chdir(original_cwd)


def test_bypass_verdict_passes_hook_validation_shape():
    """Verify verdict file contains all required fields with correct types."""
    original_cwd = Path.cwd()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            
            # Write verdict with minimal inputs
            write_coordinator_bypass_verdict(
                issue_number=999,
                bypass_reason="test"
            )
            
            # Load and validate structure
            verdict_path = Path(".claude/plan_critic_verdict.json")
            with open(verdict_path) as f:
                verdict = json.load(f)
            
            # Check all 5 required fields present (hook requirement)
            required_fields = {"verdict", "composite_score", "timestamp", "reasoning", "axis_scores"}
            actual_fields = set(verdict.keys())
            assert required_fields.issubset(actual_fields), f"Missing fields: {required_fields - actual_fields}"
            
            # Check types
            assert isinstance(verdict["verdict"], str)
            assert isinstance(verdict["composite_score"], (int, float))
            assert isinstance(verdict["timestamp"], str)
            assert isinstance(verdict["reasoning"], str)
            assert isinstance(verdict["axis_scores"], dict)
            
            # Verify ISO timestamp format
            assert "T" in verdict["timestamp"], "Timestamp should be ISO format"
            assert verdict["timestamp"].endswith("Z") or "+" in verdict["timestamp"]
            
            # Verify padding worked for short reason
            assert len(verdict["reasoning"]) >= 100
            assert "Coordinator bypass: test." in verdict["reasoning"]
            assert "audit trail purposes" in verdict["reasoning"], "Should include padding text"
            
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])