#!/usr/bin/env python3
"""
Unit tests for enforce_implementation_workflow.py enforcement level system (Issue #246).

Tests graduated enforcement levels: off → warn → suggest → block.
These tests should FAIL initially (TDD red phase) until implementation is complete.

Hook Enhancement:
- Adds EnforcementLevel enum (off, warn, suggest, block)
- Implements get_enforcement_level() with environment variable precedence
- Graduated responses for each level
- Backward compatibility with ENFORCE_WORKFLOW_STRICT

Test Coverage Target: 95%+

Author: test-master agent
Date: 2026-01-19
Issue: #246
"""

import json
import os
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

# Import will fail initially (TDD red phase) - that's expected
try:
    from enforce_implementation_workflow import (
        EnforcementLevel,
        get_enforcement_level,
        has_significant_additions,
        is_code_file,
        main,
        output_decision,
    )
    _imports_available = True
except ImportError:
    _imports_available = False


class TestEnforcementLevelEnum:
    """Test EnforcementLevel enum values and ordering."""

    def test_enforcement_level_values_exist(self):
        """Test that all enforcement levels exist."""
        assert hasattr(EnforcementLevel, 'OFF')
        assert hasattr(EnforcementLevel, 'WARN')
        assert hasattr(EnforcementLevel, 'SUGGEST')
        assert hasattr(EnforcementLevel, 'BLOCK')

    def test_enforcement_level_ordering(self):
        """Test that enforcement levels have correct ordering."""
        # Should be: off < warn < suggest < block
        assert EnforcementLevel.OFF.value < EnforcementLevel.WARN.value
        assert EnforcementLevel.WARN.value < EnforcementLevel.SUGGEST.value
        assert EnforcementLevel.SUGGEST.value < EnforcementLevel.BLOCK.value

    def test_enforcement_level_string_values(self):
        """Test that enforcement levels have correct string names."""
        assert EnforcementLevel.OFF.name == 'OFF'
        assert EnforcementLevel.WARN.name == 'WARN'
        assert EnforcementLevel.SUGGEST.name == 'SUGGEST'
        assert EnforcementLevel.BLOCK.name == 'BLOCK'


class TestGetEnforcementLevel:
    """Test get_enforcement_level() function with environment variable precedence."""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_is_suggest(self):
        """Test that default enforcement level is 'suggest' when no env vars set."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.SUGGEST

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_enforcement_level_env_var_block(self):
        """Test that ENFORCEMENT_LEVEL=block returns BLOCK level."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "warn"}, clear=True)
    def test_enforcement_level_env_var_warn(self):
        """Test that ENFORCEMENT_LEVEL=warn returns WARN level."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.WARN

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "off"}, clear=True)
    def test_enforcement_level_env_var_off(self):
        """Test that ENFORCEMENT_LEVEL=off returns OFF level."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.OFF

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "suggest"}, clear=True)
    def test_enforcement_level_env_var_suggest(self):
        """Test that ENFORCEMENT_LEVEL=suggest returns SUGGEST level."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.SUGGEST

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "BLOCK"}, clear=True)
    def test_enforcement_level_case_insensitive(self):
        """Test that ENFORCEMENT_LEVEL is case-insensitive."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "WaRn"}, clear=True)
    def test_enforcement_level_mixed_case(self):
        """Test that ENFORCEMENT_LEVEL handles mixed case."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.WARN

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "ENFORCE_WORKFLOW_STRICT": "false"}, clear=True)
    def test_enforcement_level_precedence_over_strict(self):
        """Test that ENFORCEMENT_LEVEL takes precedence over ENFORCE_WORKFLOW_STRICT."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "invalid"}, clear=True)
    def test_invalid_enforcement_level_falls_back_to_suggest(self):
        """Test that invalid ENFORCEMENT_LEVEL value falls back to SUGGEST."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.SUGGEST

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": ""}, clear=True)
    def test_empty_enforcement_level_falls_back_to_suggest(self):
        """Test that empty ENFORCEMENT_LEVEL value falls back to SUGGEST."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.SUGGEST


class TestBackwardCompatibility:
    """Test backward compatibility with ENFORCE_WORKFLOW_STRICT."""

    @patch.dict(os.environ, {"ENFORCE_WORKFLOW_STRICT": "true"}, clear=True)
    def test_strict_true_maps_to_block(self):
        """Test that ENFORCE_WORKFLOW_STRICT=true maps to BLOCK level."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCE_WORKFLOW_STRICT": "false"}, clear=True)
    def test_strict_false_maps_to_off(self):
        """Test that ENFORCE_WORKFLOW_STRICT=false maps to OFF level."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.OFF

    @patch.dict(os.environ, {"ENFORCE_WORKFLOW_STRICT": "TRUE"}, clear=True)
    def test_strict_true_case_insensitive(self):
        """Test that ENFORCE_WORKFLOW_STRICT=TRUE (uppercase) maps to BLOCK."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCE_WORKFLOW_STRICT": "FALSE"}, clear=True)
    def test_strict_false_case_insensitive(self):
        """Test that ENFORCE_WORKFLOW_STRICT=FALSE (uppercase) maps to OFF."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.OFF

    @patch.dict(os.environ, {"ENFORCE_WORKFLOW_STRICT": "true"}, clear=True)
    def test_strict_only_no_enforcement_level(self):
        """Test legacy support: ENFORCE_WORKFLOW_STRICT works without ENFORCEMENT_LEVEL."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCE_WORKFLOW_STRICT": "invalid"}, clear=True)
    def test_strict_invalid_value_defaults_to_suggest(self):
        """Test that invalid ENFORCE_WORKFLOW_STRICT value defaults to SUGGEST."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.SUGGEST


class TestEnforcementBehavior:
    """Test enforcement behavior for each level."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "off"}, clear=True)
    def test_off_level_always_allows(self, mock_stdout, mock_stdin):
        """Test that OFF level always allows significant changes."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def significant_function(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "off" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "warn"}, clear=True)
    def test_warn_level_allows_with_warning(self, mock_stderr, mock_stdout, mock_stdin):
        """Test that WARN level allows changes but logs warning to stderr."""
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
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

        # Check that warning was logged to stderr
        stderr_output = mock_stderr.getvalue()
        assert "WARNING" in stderr_output or "warning" in stderr_output.lower()
        assert "/implement" in stderr_output

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "suggest"}, clear=True)
    def test_suggest_level_allows_with_suggestion(self, mock_stdout, mock_stdin):
        """Test that SUGGEST level allows changes but includes suggestion in reason."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def feature_function(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "suggest" in reason.lower() or "recommend" in reason.lower()
        assert "/implement" in reason

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_block_level_denies_significant_changes(self, mock_stdout, mock_stdin):
        """Test that BLOCK level denies significant changes."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def blocked_function(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "/implement" in output["hookSpecificOutput"]["permissionDecisionReason"]

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_block_level_allows_minor_changes(self, mock_stdout, mock_stdin):
        """Test that BLOCK level allows minor changes (typo fixes, small edits)."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "# Calcualte sum",
                "new_string": "# Calculate sum"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestExemptionsUnchanged:
    """Test that exemptions (tests, docs, configs) work at all enforcement levels."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_test_files_exempt_all_levels(self, mock_stdout, mock_stdin):
        """Test that test files are exempt even at BLOCK level."""
        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "tests/test_feature.py",
                "content": "def test_new_feature(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "exempt" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_docs_exempt_all_levels(self, mock_stdout, mock_stdin):
        """Test that documentation files are exempt even at BLOCK level."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "README.md",
                "old_string": "# Old",
                "new_string": "# New\n\nLots of new content here."
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
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_config_exempt_all_levels(self, mock_stdout, mock_stdin):
        """Test that config files are exempt even at BLOCK level."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "config.json",
                "old_string": '{"debug": false}',
                "new_string": '{"debug": true, "verbose": true}'
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
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": "implementer"}, clear=True)
    def test_allowed_agents_exempt_all_levels(self, mock_stdout, mock_stdin):
        """Test that allowed agents (implementer, test-master) are exempt at all levels."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def agent_implementation(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "implementer" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()


class TestUserFeedback:
    """Test user feedback messages for different enforcement levels."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "suggest"}, clear=True)
    def test_suggest_message_includes_implement_command(self, mock_stdout, mock_stdin):
        """Test that SUGGEST level message includes /implement command."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def new_feature(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "/implement" in reason

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_block_message_includes_explanation(self, mock_stdout, mock_stdin):
        """Test that BLOCK level message includes clear explanation."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "class NewClass: pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        # Should explain what was detected and why it was blocked
        assert ("class" in reason.lower() or "function" in reason.lower())
        assert "/implement" in reason

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "warn"}, clear=True)
    def test_warn_message_logged_to_stderr(self, mock_stderr, mock_stdout, mock_stdin):
        """Test that WARN level logs message to stderr."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def warning_test(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

        # Check stderr for warning message
        stderr_output = mock_stderr.getvalue()
        assert len(stderr_output) > 0
        assert "warn" in stderr_output.lower() or "/implement" in stderr_output


class TestEnforcementLevelIntegration:
    """Integration tests for enforcement level system."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "off"}, clear=True)
    def test_off_level_scenario_major_refactor(self, mock_stdout, mock_stdin):
        """Test OFF level allows major refactoring without warnings."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "core.py",
                "old_string": "def old_api(): pass",
                "new_string": """def new_api_v2():
    # Complete rewrite
    pass

class APIHandler:
    def __init__(self):
        self.version = 2
"""
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
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "warn"}, clear=True)
    def test_warn_level_scenario_feature_addition(self, mock_stdout, mock_stdin):
        """Test WARN level allows feature addition but provides warning."""
        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "new_feature.py",
                "content": """def process_data(items):
    return [item.upper() for item in items]
"""
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
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "suggest"}, clear=True)
    def test_suggest_level_scenario_bug_fix(self, mock_stdout, mock_stdin):
        """Test SUGGEST level allows bug fix with helpful suggestion."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "buggy.py",
                "old_string": "if user.is_admin:",
                "new_string": """if user and user.is_admin:
    # Fixed null reference bug"""
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
    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block"}, clear=True)
    def test_block_level_scenario_unauthorized_implementation(self, mock_stdout, mock_stdin):
        """Test BLOCK level denies unauthorized implementation."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "api.py",
                "old_string": "# TODO: Add rate limiting",
                "new_string": """def rate_limit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Rate limiting implementation
        return func(*args, **kwargs)
    return wrapper
"""
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestEdgeCases:
    """Test edge cases for enforcement level system."""

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "   block   "}, clear=True)
    def test_enforcement_level_with_whitespace(self):
        """Test that ENFORCEMENT_LEVEL handles whitespace in value."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "ENFORCE_WORKFLOW_STRICT": "true"}, clear=True)
    def test_both_env_vars_set_enforcement_level_wins(self):
        """Test that ENFORCEMENT_LEVEL takes precedence when both are set."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.BLOCK

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "off", "ENFORCE_WORKFLOW_STRICT": "true"}, clear=True)
    def test_enforcement_level_off_overrides_strict_true(self):
        """Test that ENFORCEMENT_LEVEL=off overrides ENFORCE_WORKFLOW_STRICT=true."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.OFF

    @patch.dict(os.environ, {}, clear=True)
    def test_no_env_vars_returns_default_suggest(self):
        """Test that no environment variables returns default SUGGEST level."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.SUGGEST

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "123"}, clear=True)
    def test_numeric_enforcement_level_falls_back_to_suggest(self):
        """Test that numeric ENFORCEMENT_LEVEL value falls back to SUGGEST."""
        level = get_enforcement_level()
        assert level == EnforcementLevel.SUGGEST


if __name__ == "__main__":
    # Run tests with minimal verbosity (Issue #90 - prevent subprocess deadlock)
    pytest.main([__file__, "--tb=line", "-q"])
