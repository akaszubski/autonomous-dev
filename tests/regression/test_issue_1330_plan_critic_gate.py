#!/usr/bin/env python3
"""Regression test for Issue #1330: plan-critic gate for ADR/architectural-issue creation.

Tests that ADR creation and architectural-issue creation are blocked unless
plan-critic has passed in the session.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

import pytest

# Add lib to path for imports
repo_root = Path(__file__).resolve().parents[2]
lib_path = repo_root / "plugins/autonomous-dev/lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))

import pipeline_completion_state as pcs

# Import the hook module
hooks_path = repo_root / "plugins/autonomous-dev/hooks"
if hooks_path.exists():
    sys.path.insert(0, str(hooks_path))

from unified_pre_tool import _detect_architectural_decision_without_plan_critic


class TestPlanCriticGate:
    """Test the plan-critic gate for architectural decisions."""

    def test_blocks_new_adr_creation_without_plan_critic(self, tmp_path, monkeypatch):
        """Test that new ADR creation is blocked without plan-critic."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        # Create a non-existing ADR path
        adr_path = str(tmp_path / "docs" / "architecture" / "adr-042-test.md")
        
        tool_input = {"file_path": adr_path}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Write", tool_input)
        
        # Assert
        assert result is not None
        assert "BLOCKED: Architectural-decision creation detected" in result
        assert "plan-critic has not run in this session" in result

    def test_allows_existing_adr_edit(self, tmp_path, monkeypatch):
        """Test that edits to existing ADR files are allowed."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        # Create an existing ADR file
        adr_dir = tmp_path / "docs" / "architecture"
        adr_dir.mkdir(parents=True)
        adr_path = adr_dir / "adr-001-existing.md"
        adr_path.write_text("Existing content")
        
        tool_input = {"file_path": str(adr_path)}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Write", tool_input)
        
        # Assert
        assert result is None  # Should allow edits to existing files

    def test_blocks_gh_issue_create_with_architectural_keyword(self, monkeypatch):
        """Test that gh issue create with architectural keywords is blocked."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        command = 'gh issue create --title "Architectural Review" --body "Status: Proposed\n\narchitectural-debt"'
        tool_input = {"command": command}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Bash", tool_input)
        
        # Assert
        assert result is not None
        assert "BLOCKED: Architectural-decision creation detected" in result

    def test_allows_after_plan_critic_passed(self, tmp_path, monkeypatch):
        """Test that ADR creation is allowed after plan-critic passed."""
        # Setup
        session_id = "test-session"
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        
        # Mock the state file path to use tmp_path
        state_file = tmp_path / f"pipeline_agent_completions_{session_id}.json"
        
        def mock_state_file_path(sid, run_id=None):
            return state_file
        
        monkeypatch.setattr(pcs, "_state_file_path", mock_state_file_path)
        
        # Record that plan-critic passed
        pcs.record_plan_critic_passed(session_id, "test-plan")
        
        # Create a non-existing ADR path
        adr_path = str(tmp_path / "docs" / "architecture" / "adr-042-test.md")
        tool_input = {"file_path": adr_path}
        
        # Act
        with patch.object(pcs, 'get_plan_critic_passed', return_value=True):
            result = _detect_architectural_decision_without_plan_critic("Write", tool_input)
        
        # Assert
        assert result is None  # Should allow after plan-critic passed

    def test_bypass_file_consumed_on_first_check(self, tmp_path, monkeypatch):
        """Test that bypass file is consumed on first check."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        # Create bypass file
        bypass_file = Path("/tmp/skip_plan_critic_gate")
        bypass_file.touch()
        
        # Create a non-existing ADR path
        adr_path = str(tmp_path / "docs" / "architecture" / "adr-042-test.md")
        tool_input = {"file_path": adr_path}
        
        # Act - First call should consume bypass
        result1 = _detect_architectural_decision_without_plan_critic("Write", tool_input)
        
        # Assert - First call allowed
        assert result1 is None
        assert not bypass_file.exists()  # File should be consumed
        
        # Act - Second call should be blocked
        result2 = _detect_architectural_decision_without_plan_critic("Write", tool_input)
        
        # Assert - Second call blocked
        assert result2 is not None
        assert "BLOCKED: Architectural-decision creation detected" in result2

    def test_allows_typo_fix_on_existing_adr(self, tmp_path, monkeypatch):
        """Test that typo fixes on existing ADRs are allowed."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        # Create an existing ADR file with a typo
        adr_dir = tmp_path / "docs" / "architecture"
        adr_dir.mkdir(parents=True)
        adr_path = adr_dir / "adr-001-example.md"
        adr_path.write_text("This is a exapmle ADR")  # Typo: exapmle
        
        tool_input = {"file_path": str(adr_path)}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Write", tool_input)
        
        # Assert
        assert result is None  # Should allow edits to existing files

    def test_detects_adr_pattern_in_gh_issue(self, monkeypatch):
        """Test detection of ADR-NNN pattern in gh issue body."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        command = 'gh issue create --title "Review needed" --body "Please review ADR-1234 for implementation"'
        tool_input = {"command": command}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Bash", tool_input)
        
        # Assert
        assert result is not None
        assert "BLOCKED: Architectural-decision creation detected" in result

    def test_detects_open_questions_header(self, monkeypatch):
        """Test detection of '## Open Questions' header in gh issue."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        command = 'gh issue create --title "Design Review" --body "## Open Questions\n\n1. Should we use X or Y?"'
        tool_input = {"command": command}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Bash", tool_input)
        
        # Assert
        assert result is not None
        assert "BLOCKED: Architectural-decision creation detected" in result

    def test_detects_implementation_phases_header(self, monkeypatch):
        """Test detection of '## Implementation Phases' header in gh issue."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        command = 'gh issue create --title "Feature Plan" --body "## Implementation Phases\n\nPhase 1: Setup"'
        tool_input = {"command": command}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Bash", tool_input)
        
        # Assert
        assert result is not None
        assert "BLOCKED: Architectural-decision creation detected" in result

    def test_allows_regular_gh_issue_create(self, monkeypatch):
        """Test that regular gh issue create without keywords is allowed."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        command = 'gh issue create --title "Bug fix" --body "Fix the broken login"'
        tool_input = {"command": command}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Bash", tool_input)
        
        # Assert
        assert result is None  # Should allow regular issues

    def test_allows_non_adr_file_writes(self, tmp_path, monkeypatch):
        """Test that non-ADR file writes are allowed."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        regular_path = str(tmp_path / "docs" / "README.md")
        tool_input = {"file_path": regular_path}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Write", tool_input)
        
        # Assert
        assert result is None  # Should allow non-ADR files

    def test_handles_body_file_argument(self, tmp_path, monkeypatch):
        """Test detection with --body-file argument."""
        # Setup
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session")
        
        # Create a body file with architectural keywords
        body_file = tmp_path / "issue_body.md"
        body_file.write_text("Status: Proposed\n\nThis is an architectural review")
        
        command = f'gh issue create --title "Review" --body-file {body_file}'
        tool_input = {"command": command}
        
        # Act
        result = _detect_architectural_decision_without_plan_critic("Bash", tool_input)
        
        # Assert
        assert result is not None
        assert "BLOCKED: Architectural-decision creation detected" in result