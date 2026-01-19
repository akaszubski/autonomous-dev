#!/usr/bin/env python3
"""
Unit tests for enforce_implementation_workflow.py protected paths (Issue #250).

Tests extension of enforce_implementation_workflow.py to block edits to:
- .claude/commands/*.md (command definitions)
- .claude/agents/*.md (agent definitions)
- plugins/autonomous-dev/lib/*.py (core library infrastructure)

TDD Mode: These tests extend existing tests for new protected paths feature.
Tests should FAIL initially until implementation is added.

Test Strategy:
- Test PROTECTED_PATHS pattern matching
- Test agent exemption (ALLOWED_AGENTS can still edit)
- Test violation logging integration
- Test helpful error messages with guidance
- Test interaction with ENFORCE_WORKFLOW_STRICT env var

Hook Purpose:
- Prevents Claude from autonomously editing command/agent definitions
- Prevents Claude from editing core library infrastructure
- Logs violations for analysis
- Still allows exempted agents (implementer, test-master, etc.)

Test Coverage Target: 95%+

Author: test-master agent
Date: 2026-01-19
Issue: #250 (Enforce /implement workflow)
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Fixture to enable enforcement for all tests in this file
@pytest.fixture(autouse=True)
def enable_enforcement_by_default(monkeypatch):
    """Enable enforcement for all tests in this file."""
    monkeypatch.setenv("ENFORCE_WORKFLOW_STRICT", "true")


# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent / ".claude" / "hooks"),
)

# Import will fail - is_protected_path doesn't exist yet (TDD!)
try:
    from enforce_implementation_workflow import (
        is_protected_path,
        main,
        output_decision,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestProtectedPathDetection:
    """Test detection of protected paths."""

    def test_detects_command_file_edit(self):
        """Test detection of .claude/commands/*.md edit."""
        file_path = ".claude/commands/implement.md"

        assert is_protected_path(file_path) is True

    def test_detects_agent_file_edit(self):
        """Test detection of .claude/agents/*.md edit."""
        file_path = ".claude/agents/implementer.md"

        assert is_protected_path(file_path) is True

    def test_detects_lib_file_edit(self):
        """Test detection of plugins/autonomous-dev/lib/*.py edit."""
        file_path = "plugins/autonomous-dev/lib/agent_tracker.py"

        assert is_protected_path(file_path) is True

    def test_detects_nested_command_file(self):
        """Test detection of nested command files."""
        file_path = ".claude/commands/batch/implement-batch.md"

        assert is_protected_path(file_path) is True

    def test_detects_nested_lib_file(self):
        """Test detection of nested lib files."""
        file_path = "plugins/autonomous-dev/lib/utils/helper.py"

        assert is_protected_path(file_path) is True

    def test_allows_non_protected_paths(self):
        """Test non-protected paths are allowed."""
        file_paths = [
            "src/app.py",
            "README.md",
            "config.json",
            ".claude/skills/testing-guide/index.md",
            "plugins/autonomous-dev/hooks/auto_test.py",
        ]

        for file_path in file_paths:
            assert is_protected_path(file_path) is False, f"Should allow: {file_path}"

    def test_detects_absolute_paths(self):
        """Test detection works with absolute paths."""
        file_path = "/Users/dev/project/.claude/commands/implement.md"

        assert is_protected_path(file_path) is True

    def test_case_insensitive_detection(self):
        """Test detection is case-insensitive."""
        file_path = ".CLAUDE/COMMANDS/IMPLEMENT.MD"

        assert is_protected_path(file_path) is True


class TestProtectedPathBlocking:
    """Test blocking of protected path edits."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_blocks_command_file_edit(self, mock_stdout, mock_stdin):
        """Test blocks unauthorized edit to command file."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "protected" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "planner"})
    def test_blocks_agent_file_edit(self, mock_stdout, mock_stdin):
        """Test blocks unauthorized edit to agent file."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/agents/implementer.md",
                        "old_string": "## Role",
                        "new_string": "## Role (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_blocks_lib_file_edit(self, mock_stdout, mock_stdin):
        """Test blocks unauthorized edit to lib file."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "plugins/autonomous-dev/lib/agent_tracker.py",
                        "old_string": "class AgentTracker:",
                        "new_string": "class AgentTracker:  # Modified",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_blocks_write_to_protected_path(self, mock_stdout, mock_stdin):
        """Test blocks Write tool to protected path."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": ".claude/commands/new-command.md",
                        "content": "# New Command\nContent here",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestAgentExemption:
    """Test exempted agents can still edit protected paths."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "implementer"})
    def test_implementer_can_edit_protected_paths(self, mock_stdout, mock_stdin):
        """Test implementer agent can edit protected paths."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Updated)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "implementer" in output["hookSpecificOutput"]["permissionDecisionReason"]

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "test-master"})
    def test_test_master_can_edit_protected_paths(self, mock_stdout, mock_stdin):
        """Test test-master agent can edit protected paths."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "plugins/autonomous-dev/lib/test_helper.py",
                        "old_string": "def helper():",
                        "new_string": "def helper():  # Updated",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestViolationLogging:
    """Test integration with workflow_violation_logger."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    @patch("enforce_implementation_workflow.WorkflowViolationLogger")
    def test_logs_protected_path_violation(
        self, mock_logger_class, mock_stdout, mock_stdin
    ):
        """Test violation is logged when blocking protected path edit."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should have logged the violation
        mock_logger.log_violation.assert_called_once()
        call_args = mock_logger.log_violation.call_args
        # Compare enum value (ViolationType.PROTECTED_PATH_EDIT.value == "protected_path_edit")
        violation_type = call_args[1]["violation_type"]
        assert getattr(violation_type, "value", violation_type) == "protected_path_edit"
        assert "implement.md" in call_args[1]["file_path"]
        assert call_args[1]["agent_name"] == "researcher"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "implementer"})
    @patch("enforce_implementation_workflow.WorkflowViolationLogger")
    def test_no_logging_for_exempted_agents(
        self, mock_logger_class, mock_stdout, mock_stdin
    ):
        """Test no violation logged for exempted agents."""
        mock_logger = MagicMock()
        mock_logger_class.return_value = mock_logger

        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Updated)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should NOT have logged a violation (agent is exempted)
        mock_logger.log_violation.assert_not_called()


class TestBlockingMessages:
    """Test helpful error messages for protected path violations."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_blocking_message_explains_protected_path(self, mock_stdout, mock_stdin):
        """Test blocking message explains protected path restriction."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        assert "protected" in reason.lower()
        assert "commands" in reason.lower() or "implement.md" in reason

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "planner"})
    def test_blocking_message_includes_file_path(self, mock_stdout, mock_stdin):
        """Test blocking message includes the protected file path."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/agents/implementer.md",
                        "old_string": "## Role",
                        "new_string": "## Role (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        assert "implementer.md" in reason or "agents" in reason.lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_blocking_message_includes_workflow_guidance(self, mock_stdout, mock_stdin):
        """Test blocking message includes workflow guidance."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "plugins/autonomous-dev/lib/agent_tracker.py",
                        "old_string": "class AgentTracker:",
                        "new_string": "class AgentTracker:  # Modified",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        # Should mention /implement or proper workflow
        assert "/implement" in reason or "workflow" in reason.lower()


class TestEnforcementToggle:
    """Test interaction with ENFORCE_WORKFLOW_STRICT env var."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "false"}, clear=True)
    def test_disabled_enforcement_allows_protected_path_edits(
        self, mock_stdout, mock_stdin
    ):
        """Test disabled enforcement allows protected path edits."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "disabled" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"}, clear=True)
    def test_enabled_enforcement_blocks_protected_path_edits(
        self, mock_stdout, mock_stdin
    ):
        """Test enabled enforcement blocks protected path edits."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_handles_relative_path_with_dots(self, mock_stdout, mock_stdin):
        """Test handles relative paths with .. correctly."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "src/../.claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        # Should still detect as protected path
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_handles_symlink_paths(self, mock_stdout, mock_stdin):
        """Test handles symlink paths correctly."""
        # Note: Actual symlink resolution would require filesystem access
        # This tests that the path matching works with various path formats
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "/link/to/.claude/commands/implement.md",
                        "old_string": "# Implement",
                        "new_string": "# Implement (Modified)",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        # Should detect as protected path
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_handles_empty_file_path(self, mock_stdout, mock_stdin):
        """Test handles empty file path gracefully."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "",
                        "old_string": "old",
                        "new_string": "new",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        # Should allow (graceful degradation)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestIntegrationScenarios:
    """Test complete workflow scenarios."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_scenario_claude_tries_edit_command_autonomously(
        self, mock_stdout, mock_stdin
    ):
        """Test scenario: Claude autonomously tries to modify command definition."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": ".claude/commands/implement.md",
                        "old_string": "## Usage",
                        "new_string": "## Usage\n\nAdded by Claude",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "protected" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "implementer"})
    def test_scenario_implement_workflow_updates_lib(self, mock_stdout, mock_stdin):
        """Test scenario: /implement workflow updates lib file (allowed)."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "plugins/autonomous-dev/lib/agent_tracker.py",
                        "old_string": "def track():",
                        "new_string": "def track():  # Enhanced",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_scenario_claude_creates_new_command_file(self, mock_stdout, mock_stdin):
        """Test scenario: Claude tries to create new command file (blocked)."""
        mock_stdin.write(
            json.dumps(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": ".claude/commands/new-feature.md",
                        "content": "# New Feature Command\n\nContent",
                    },
                }
            )
        )
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


if __name__ == "__main__":
    # Run tests with minimal verbosity (Issue #90 - prevent subprocess deadlock)
    pytest.main([__file__, "--tb=line", "-q"])
