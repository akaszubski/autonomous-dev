"""Tests for _extract_wrapped_command function in unified_prompt_validator.py.

Issue #924: Ensure function returns None when <command-args> is absent,
not (name, '') which causes silent marker consumption at critique_done.
"""

import sys
from pathlib import Path
import pytest

# Add hooks directory to path to import the function
hook_dir = Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/hooks"
sys.path.insert(0, str(hook_dir))

from unified_prompt_validator import _extract_wrapped_command


class TestExtractWrappedCommand:
    """Test _extract_wrapped_command behavior per Issue #924."""
    
    def test_both_tags_present(self):
        """When both tags present, returns (name, args)."""
        text = "<command-name>/implement</command-name><command-args>--skip-review</command-args>"
        result = _extract_wrapped_command(text)
        assert result == ("implement", "--skip-review")
    
    def test_command_name_only_returns_none(self):
        """Issue #924: When only command-name present, returns None (not (name, ''))."""
        text = "Use <command-name>implement</command-name> here"
        result = _extract_wrapped_command(text)
        assert result is None, "Should return None when command-args absent, not (name, '')"
    
    def test_command_name_with_slash(self):
        """Handles command-name with leading slash."""
        text = "<command-name>/create-issue</command-name><command-args>--quick</command-args>"
        result = _extract_wrapped_command(text)
        assert result == ("create-issue", "--quick")
    
    def test_empty_command_args(self):
        """When command-args tag present but empty, returns (name, '')."""
        text = "<command-name>implement</command-name><command-args></command-args>"
        result = _extract_wrapped_command(text)
        assert result == ("implement", "")
    
    def test_multiline_args(self):
        """Handles multiline content in command-args."""
        text = """<command-name>implement</command-name><command-args>--fix
        --issue 924
        --verbose</command-args>"""
        result = _extract_wrapped_command(text)
        assert result == ("implement", """--fix
        --issue 924
        --verbose""")
    
    def test_no_tags_returns_none(self):
        """When no XML tags present, returns None."""
        text = "Just use /implement --skip-review"
        result = _extract_wrapped_command(text)
        assert result is None
    
    def test_command_args_only_returns_none(self):
        """When only command-args present (no command-name), returns None."""
        text = "<command-args>--skip-review</command-args>"
        result = _extract_wrapped_command(text)
        assert result is None
    
    def test_nested_text_before_and_after(self):
        """Extracts command even with surrounding text."""
        text = "You should use <command-name>plan-to-issues</command-name><command-args>--quick</command-args> to proceed."
        result = _extract_wrapped_command(text)
        assert result == ("plan-to-issues", "--quick")
    
    def test_hyphenated_command_name(self):
        """Handles hyphenated command names correctly."""
        text = "<command-name>create-issue</command-name><command-args>--title 'Test'</command-args>"
        result = _extract_wrapped_command(text)
        assert result == ("create-issue", "--title 'Test'")


class TestIssue924RegressionScenarios:
    """Specific regression tests for Issue #924 scenarios."""
    
    def test_critique_done_marker_preservation_without_args(self):
        """Simulates critique_done stage: command-name without args should NOT consume marker.
        
        This is the core bug from Issue #924: when _extract_wrapped_command returned
        (name, '') for missing <command-args>, the critique_done gate would incorrectly
        consume the marker even though the command wasn't properly formed.
        """
        # Simulate what happens at critique_done when user enters wrapped command without args
        text = "Run <command-name>implement</command-name> now"
        result = _extract_wrapped_command(text)
        
        # With the fix, this returns None, so the marker is NOT consumed
        assert result is None, "Missing command-args should return None to prevent marker consumption"
    
    def test_plan_exited_marker_preservation_without_args(self):
        """Simulates plan_exited stage: command-name without args should NOT consume marker."""
        text = "<command-name>/implement</command-name>"
        result = _extract_wrapped_command(text)
        
        # With the fix, this returns None, so escape hatch doesn't fire
        assert result is None, "Missing command-args at plan_exited should not trigger escape hatch"
    
    def test_valid_skip_review_consumes_marker(self):
        """Valid wrapped form with skip-review SHOULD allow marker consumption."""
        text = "<command-name>implement</command-name><command-args>--skip-review --verbose</command-args>"
        result = _extract_wrapped_command(text)
        
        # This should work - both tags present
        assert result == ("implement", "--skip-review --verbose")
        
        # Verify --skip-review is detectable in args
        assert "--skip-review" in result[1].split()