#!/usr/bin/env python3
"""
Test for Issue #1285: Mode-aware prerequisite enforcement in light/fix modes.

The agent_ordering_gate helper and unified_pre_tool hook must converge on the
same prerequisite requirements for each pipeline mode.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(HOOKS_DIR))

from agent_ordering_gate import (
    check_ordering_prerequisites,
    check_ordering_with_session_fallback,
    get_required_agents,
    normalize_pipeline_mode,
)


class TestIssue1285ModeAwareOrdering:
    """Tests for Issue #1285 - mode-aware prerequisite enforcement."""

    def test_normalize_pipeline_mode(self):
        """Test mode string normalization handles dashes and case variations."""
        # Test with dashes
        assert normalize_pipeline_mode("--light") == "light"
        assert normalize_pipeline_mode("--fix") == "fix"
        assert normalize_pipeline_mode("--tdd-first") == "tdd-first"
        
        # Test without dashes
        assert normalize_pipeline_mode("light") == "light"
        assert normalize_pipeline_mode("fix") == "fix"
        assert normalize_pipeline_mode("tdd-first") == "tdd-first"
        
        # Test case variations
        assert normalize_pipeline_mode("LIGHT") == "light"
        assert normalize_pipeline_mode("FIX") == "fix"
        assert normalize_pipeline_mode("--LIGHT") == "light"
        assert normalize_pipeline_mode("--FIX") == "fix"
        
        # Test defaults
        assert normalize_pipeline_mode("") == "full"
        assert normalize_pipeline_mode(None) == "full"
        assert normalize_pipeline_mode("unknown") == "full"
        assert normalize_pipeline_mode("invalid") == "full"

    def test_light_mode_implementer_requires_only_planner(self):
        """In light mode, implementer requires only planner, not plan-critic."""
        # Test with normalized mode
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents={"planner"},
            pipeline_mode="light"
        )
        assert result.passed is True
        assert result.missing_agents == []
        
        # Test with dash-prefixed mode (Issue #1285)
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents={"planner"},
            pipeline_mode="--light"
        )
        assert result.passed is True
        assert result.missing_agents == []
        
        # Test with no agents completed
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents=set(),
            pipeline_mode="light"
        )
        assert result.passed is False
        assert "planner" in result.missing_agents
        assert "plan-critic" not in result.missing_agents

    def test_fix_mode_implementer_requires_no_prerequisites(self):
        """In fix mode, implementer has no prerequisites (no planner/plan-critic)."""
        # Test with normalized mode
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents=set(),
            pipeline_mode="fix"
        )
        assert result.passed is True
        assert result.missing_agents == []
        
        # Test with dash-prefixed mode (Issue #1285)
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents=set(),
            pipeline_mode="--fix"
        )
        assert result.passed is True
        assert result.missing_agents == []

    def test_full_mode_implementer_requires_both_planner_and_plan_critic(self):
        """In full mode, implementer requires both planner and plan-critic."""
        # Only planner completed - should fail
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents={"planner"},
            pipeline_mode="full"
        )
        assert result.passed is False
        assert "plan-critic" in result.missing_agents
        
        # Both completed - should pass
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents={"planner", "plan-critic"},
            pipeline_mode="full"
        )
        assert result.passed is True
        assert result.missing_agents == []

    def test_get_required_agents_normalizes_mode(self):
        """get_required_agents should normalize mode strings."""
        # These should all return the same light mode agents
        light_agents_normal = get_required_agents("light")
        light_agents_dashed = get_required_agents("--light")
        light_agents_upper = get_required_agents("LIGHT")
        
        assert light_agents_normal == light_agents_dashed
        assert light_agents_normal == light_agents_upper
        assert "planner" in light_agents_normal
        assert "plan-critic" not in light_agents_normal
        
        # These should all return the same fix mode agents
        fix_agents_normal = get_required_agents("fix")
        fix_agents_dashed = get_required_agents("--fix")
        fix_agents_upper = get_required_agents("FIX")
        
        assert fix_agents_normal == fix_agents_dashed
        assert fix_agents_normal == fix_agents_upper
        assert "planner" not in fix_agents_normal
        assert "plan-critic" not in fix_agents_normal

    @patch("pipeline_completion_state.get_completed_agents")
    @patch("pipeline_completion_state.get_launched_agents")
    @patch("pipeline_completion_state.get_validation_mode")
    @patch("pipeline_completion_state.get_plan_critic_skipped")
    def test_check_ordering_with_session_fallback_normalizes_mode(
        self, mock_plan_critic, mock_validation, mock_launched, mock_completed
    ):
        """check_ordering_with_session_fallback should normalize mode strings."""
        mock_completed.return_value = {"planner"}
        mock_launched.return_value = {"planner", "implementer"}
        mock_validation.return_value = "sequential"
        mock_plan_critic.return_value = False
        
        # Test with dash-prefixed mode
        result = check_ordering_with_session_fallback(
            "implementer",
            "test-session",
            pipeline_mode="--light"
        )
        assert result.passed is True
        
        # Test with uppercase mode
        result = check_ordering_with_session_fallback(
            "implementer",
            "test-session",
            pipeline_mode="LIGHT"
        )
        assert result.passed is True

    @patch("unified_pre_tool._is_pipeline_active")
    @patch("unified_pre_tool._get_current_issue_number")
    @patch("pipeline_completion_state.get_completed_agents")
    @patch("pipeline_completion_state.get_launched_agents")
    @patch("pipeline_completion_state.get_validation_mode")
    @patch("pipeline_completion_state.record_agent_launch")
    def test_hook_handles_mode_variations(
        self,
        mock_record,
        mock_mode,
        mock_launched,
        mock_completed,
        mock_issue,
        mock_active,
        tmp_path,
        monkeypatch
    ):
        """Hook should handle mode variations via the helper's normalization."""
        from unified_pre_tool import validate_pipeline_ordering
        
        # Setup mocks
        mock_active.return_value = True
        mock_issue.return_value = 0
        mock_completed.return_value = {"planner"}
        mock_launched.return_value = {"planner", "implementer"}
        mock_mode.return_value = "sequential"
        
        # Test with various mode formats in state file
        for mode_str in ["light", "--light", "LIGHT"]:
            state_file = tmp_path / f"state_{mode_str}.json"
            state_file.write_text(json.dumps({
                "mode": mode_str,
                "explicitly_invoked": True
            }))
            
            monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_file))
            monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
            
            decision, reason = validate_pipeline_ordering("Agent", {
                "subagent_type": "implementer"
            })
            
            # Should allow in light mode with only planner completed
            assert decision == "allow", f"Failed for mode={mode_str}: {reason}"
            assert "prerequisites met" in reason.lower()


class TestRegressionFullMode:
    """Ensure full mode still enforces all prerequisites (regression test)."""

    def test_full_mode_still_enforces_all_prerequisites(self):
        """Full mode must still require all prerequisites (no regression)."""
        # Implementer with only planner - should fail
        result = check_ordering_prerequisites(
            "implementer",
            completed_agents={"planner"},
            pipeline_mode="full"
        )
        assert result.passed is False
        assert "plan-critic" in result.missing_agents
        
        # Reviewer without implementer - should fail
        result = check_ordering_prerequisites(
            "reviewer",
            completed_agents={"planner", "plan-critic"},
            pipeline_mode="full"
        )
        assert result.passed is False
        assert "implementer" in result.missing_agents
        
        # Security-auditor without reviewer - should fail
        result = check_ordering_prerequisites(
            "security-auditor",
            completed_agents={"implementer", "pytest-gate"},
            pipeline_mode="full"
        )
        assert result.passed is False
        assert "reviewer" in result.missing_agents