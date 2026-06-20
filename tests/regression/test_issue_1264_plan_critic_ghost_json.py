#!/usr/bin/env python3
"""Regression test for Issue #1264: plan-critic ghost output recurrence.

Tests that both plan_mode_exit_detector and unified_session_tracker hooks
properly validate the plan_critic_verdict.json file has all required fields
with valid content, not just the basic verdict/composite_score/timestamp.

The issue: plan-critic would sometimes output a JSON with only basic fields
(verdict, composite_score, timestamp) but missing the substantive reasoning
and axis_scores fields. This "ghost output" would incorrectly advance the
pipeline because the hooks only checked for PROCEED verdict, not field completeness.

Fix adds validation for:
- All 5 required fields present (verdict, composite_score, timestamp, reasoning, axis_scores)
- reasoning field is non-empty string with >= 100 chars
- axis_scores field is dict with >= 3 numeric entries
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Add hooks directory to path for direct import
HOOKS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

# Import the functions we need to test
from plan_mode_exit_detector import _plan_critic_proceeded
from unified_session_tracker import _advance_plan_mode_stage


def test_plan_critic_proceeded_blocks_when_reasoning_missing(tmp_path):
    """Test that _plan_critic_proceeded returns False when reasoning field is missing."""
    verdict_path = tmp_path / "plan_critic_verdict.json"
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # Missing: reasoning and axis_scores
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    proceeded, ts = _plan_critic_proceeded(verdict_path)
    assert not proceeded, "Should block when reasoning field is missing"
    assert ts is None


def test_plan_critic_proceeded_blocks_when_axis_scores_missing(tmp_path):
    """Test that _plan_critic_proceeded returns False when axis_scores field is missing."""
    verdict_path = tmp_path / "plan_critic_verdict.json"
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reasoning": "This is a sufficiently long reasoning text that definitely exceeds the 100 character minimum requirement for the reasoning field validation check.",
        # Missing: axis_scores
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    proceeded, ts = _plan_critic_proceeded(verdict_path)
    assert not proceeded, "Should block when axis_scores field is missing"
    assert ts is None


def test_plan_critic_proceeded_blocks_when_reasoning_too_short(tmp_path):
    """Test that _plan_critic_proceeded returns False when reasoning is too short."""
    verdict_path = tmp_path / "plan_critic_verdict.json"
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reasoning": "short",  # Way less than 100 chars
        "axis_scores": {"axis1": 4, "axis2": 3, "axis3": 3},
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    proceeded, ts = _plan_critic_proceeded(verdict_path)
    assert not proceeded, "Should block when reasoning is too short"
    assert ts is None


def test_plan_critic_proceeded_blocks_when_axis_scores_too_few(tmp_path):
    """Test that _plan_critic_proceeded returns False when axis_scores has too few entries."""
    verdict_path = tmp_path / "plan_critic_verdict.json"
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reasoning": "This is a sufficiently long reasoning text that definitely exceeds the 100 character minimum requirement for the reasoning field validation check.",
        "axis_scores": {"only_one": 3},  # Less than 3 entries
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    proceeded, ts = _plan_critic_proceeded(verdict_path)
    assert not proceeded, "Should block when axis_scores has fewer than 3 entries"
    assert ts is None


def test_plan_critic_proceeded_success_with_complete_verdict(tmp_path):
    """Test that _plan_critic_proceeded returns True with all valid fields."""
    verdict_path = tmp_path / "plan_critic_verdict.json"
    timestamp = datetime.now(timezone.utc).isoformat()
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": timestamp,
        "reasoning": "This is a sufficiently long reasoning text that definitely exceeds the 100 character minimum requirement for the reasoning field validation check. It contains substantive analysis of the plan.",
        "axis_scores": {
            "Assumption Audit": 4,
            "Existing Solution Search": 3,
            "Minimalism Pressure": 3,
            "Operational Integration Test": 4,
        },
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    proceeded, ts = _plan_critic_proceeded(verdict_path)
    assert proceeded, "Should proceed with complete valid verdict"
    assert ts is not None, "Should return timestamp"


def test_ghost_json_with_only_basic_fields(tmp_path):
    """Test the exact failing case from the issue: only basic fields present."""
    # This is the exact ghost output from the issue
    verdict_path = tmp_path / "plan_critic_verdict.json"
    verdict_data = {
        "verdict": "REVISE",
        "composite_score": 2.7,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    proceeded, ts = _plan_critic_proceeded(verdict_path)
    assert not proceeded, "Should block ghost JSON with only basic fields"
    assert ts is None


def test_advance_blocked_when_reasoning_missing(tmp_path, monkeypatch):
    """Test that _advance_plan_mode_stage returns None when reasoning is missing."""
    # Set up the working directory to tmp_path
    monkeypatch.chdir(tmp_path)
    
    # Create the marker file at the expected stage
    marker_path = tmp_path / ".claude" / "plan_mode_exit.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "stage": "plan_exited",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    marker_path.write_text(json.dumps(marker_data))
    
    # Create a verdict file missing reasoning
    verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # Missing: reasoning and axis_scores
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    result = _advance_plan_mode_stage()
    assert result is None, "Should not advance when reasoning is missing"


def test_advance_blocked_when_axis_scores_invalid(tmp_path, monkeypatch):
    """Test that _advance_plan_mode_stage returns None when axis_scores is invalid."""
    # Set up the working directory to tmp_path
    monkeypatch.chdir(tmp_path)
    
    # Create the marker file at the expected stage
    marker_path = tmp_path / ".claude" / "plan_mode_exit.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "stage": "plan_exited",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    marker_path.write_text(json.dumps(marker_data))
    
    # Create a verdict file with invalid axis_scores
    verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reasoning": "This is a sufficiently long reasoning text that definitely exceeds the 100 character minimum requirement for the reasoning field validation check.",
        "axis_scores": "not_a_dict",  # Invalid: should be dict
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    result = _advance_plan_mode_stage()
    assert result is None, "Should not advance when axis_scores is not a dict"


def test_advance_proceeds_with_complete_verdict(tmp_path, monkeypatch):
    """Test that _advance_plan_mode_stage works with complete valid verdict."""
    # Set up the working directory to tmp_path
    monkeypatch.chdir(tmp_path)
    
    # Create the marker file at the expected stage
    marker_path = tmp_path / ".claude" / "plan_mode_exit.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_timestamp = datetime.now(timezone.utc)
    marker_data = {
        "stage": "plan_exited", 
        "timestamp": marker_timestamp.isoformat(),
    }
    marker_path.write_text(json.dumps(marker_data))
    
    # Create a complete valid verdict file (must be newer than marker)
    verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
    # Make verdict timestamp slightly newer than marker
    verdict_timestamp = marker_timestamp  # Use same timestamp to avoid staleness check
    verdict_data = {
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": verdict_timestamp.isoformat(),
        "reasoning": "This is a sufficiently long reasoning text that definitely exceeds the 100 character minimum requirement for the reasoning field validation check. It contains substantive analysis.",
        "axis_scores": {
            "Assumption Audit": 4,
            "Existing Solution Search": 3,
            "Minimalism Pressure": 3,
        },
    }
    verdict_path.write_text(json.dumps(verdict_data))
    
    result = _advance_plan_mode_stage()
    # Should return the suggestion message when successful
    assert result is not None, "Should advance with complete valid verdict"
    assert "plan-to-issues" in result.lower() or "implement" in result.lower()