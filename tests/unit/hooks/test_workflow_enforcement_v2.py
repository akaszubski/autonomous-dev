#!/usr/bin/env python3
"""
Unit tests for improved workflow enforcement (Issue #XX - workflow discipline enforcement).

Tests opt-in enforcement with improved detection to prevent false positives.

Philosophy:
- Default: OFF (respecting Issue #141 - persuasion over enforcement)
- Opt-in: ENFORCE_WORKFLOW_STRICT=true for teams that want it
- Smart detection: Avoid false positives for docs, configs, minor edits

Test Coverage Target: 95%+

Author: test-master agent
Date: 2026-01-09
Issue: #XX
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / ".claude"
        / "hooks"
    ),
)

from enforce_implementation_workflow import (
    is_code_file,
    has_significant_additions,
)


class TestOptInEnforcement:
    """Test that enforcement is opt-in (disabled by default)."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {}, clear=True)
    def test_enforcement_disabled_by_default(self, mock_stdout, mock_stdin):
        """Test that enforcement is disabled by default (Issue #141)."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def new_function(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        # Should allow because enforcement is OFF by default
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "disabled" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_enforcement_enabled_when_opt_in(self, mock_stdout, mock_stdin):
        """Test that enforcement blocks when ENFORCE_WORKFLOW_STRICT=true."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "api.py",
                "old_string": "",
                "new_string": "def authenticate(user): return True"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        # Should deny because enforcement is ON and this is significant code
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "/implement" in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestImprovedFalsePositiveReduction:
    """Test improved detection to reduce false positives."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_allows_documentation_files(self, mock_stdout, mock_stdin):
        """Test that documentation files are always allowed."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "README.md",
                "old_string": "# Old title",
                "new_string": "# New title\n\nAdded 100 lines of documentation here..."
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_allows_config_files(self, mock_stdout, mock_stdin):
        """Test that config files are always allowed."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "package.json",
                "old_string": '{"version": "1.0.0"}',
                "new_string": '{"version": "2.0.0", "dependencies": {...}}'
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_allows_test_files(self, mock_stdout, mock_stdin):
        """Test that test files are allowed (test-master can write tests)."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "tests/test_feature.py",
                "content": """def test_new_feature():
    assert True
"""
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        # Test files should be allowed (TDD workflow)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_blocks_significant_src_code_changes(self, mock_stdout, mock_stdin):
        """Test that significant src code changes are blocked in strict mode."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/auth.py",
                "old_string": "# TODO: implement auth",
                "new_string": """def authenticate(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return create_jwt_token(user)
    return None
"""
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "/implement" in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestHookAndAgentDetection:
    """Test that hooks and agent-specific files are handled correctly."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_allows_hook_modifications(self, mock_stdout, mock_stdin):
        """Test that hook files can be modified (development workflow)."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": ".claude/hooks/my_hook.py",
                "old_string": "def hook(): pass",
                "new_string": "def hook():\n    return True"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        # Hooks should be allowed (development files)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true", "CLAUDE_AGENT_NAME": "implementer"})
    def test_allows_pipeline_agent_modifications(self, mock_stdout, mock_stdin):
        """Test that pipeline agents (implementer) can modify code."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/feature.py",
                "old_string": "",
                "new_string": "def new_feature(): return 42"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        # Implementer agent should be allowed
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "implementer" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()


class TestGuidanceMessages:
    """Test that denial messages provide helpful guidance."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_denial_suggests_implement_command(self, mock_stdout, mock_stdin):
        """Test that denial message suggests using /implement."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/api.py",
                "old_string": "",
                "new_string": "def api_endpoint(): return {}"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        # Should suggest /implement command
        assert "/implement" in reason
        # Should explain why
        assert ("quality" in reason.lower() or "test" in reason.lower() or "workflow" in reason.lower())

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_denial_explains_how_to_disable(self, mock_stdout, mock_stdin):
        """Test that denial message explains how to disable enforcement."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/utils.py",
                "old_string": "",
                "new_string": "def utility(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        # Should explain how to disable
        assert "ENFORCE_WORKFLOW_STRICT" in reason or ".env" in reason


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "true"})
    def test_allows_lib_directory_modifications(self, mock_stdout, mock_stdin):
        """Test that lib directory (libraries) can be modified."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "lib/helper.py",
                "old_string": "",
                "new_string": "def helper(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        # Lib files should be allowed (infrastructure)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_WORKFLOW_STRICT": "TRUE"})
    def test_case_insensitive_env_var(self, mock_stdout, mock_stdin):
        """Test that env var is case-insensitive."""
        from enforce_implementation_workflow import main

        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/code.py",
                "old_string": "",
                "new_string": "def func(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        # Should still enforce (case-insensitive)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


if __name__ == "__main__":
    # Run tests with minimal verbosity
    pytest.main([__file__, "--tb=line", "-q"])
