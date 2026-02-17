"""
Regression tests for Issue #353: Missing auto-push and auto-close in batch pipeline.

Bug: `/implement --issues` completes successfully, commits and cherry-picks to
master, but does NOT push or close GitHub issues. User must manually run
`git push` and `gh issue close`.

Fix: Explicit `gh issue close` after push in implement-batch.md STEP B4,
and git push + issue close in implement.md STEP 8.

These tests verify the fix infrastructure exists and would break if removed.
"""

import json
from pathlib import Path

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestIssue353BatchTerminalActions:
    """Regression: batch pipeline must push and close issues."""

    def test_implement_batch_md_has_gh_issue_close(self):
        """implement-batch.md must contain explicit gh issue close."""
        content = (PLUGIN_DIR / "commands" / "implement-batch.md").read_text()
        assert "gh issue close" in content, (
            "Regression #353: implement-batch.md must have explicit issue close"
        )

    def test_implement_batch_md_has_git_push(self):
        """implement-batch.md must contain git push."""
        content = (PLUGIN_DIR / "commands" / "implement-batch.md").read_text()
        assert "git push" in content, (
            "Regression #353: implement-batch.md must have git push"
        )

    def test_implement_batch_md_issue_close_is_hard_gate(self):
        """Issue close must be marked as HARD GATE (not optional)."""
        content = (PLUGIN_DIR / "commands" / "implement-batch.md").read_text()
        # Find the section around gh issue close
        close_idx = content.index("gh issue close")
        surrounding = content[max(0, close_idx - 500):close_idx + 500]
        assert "HARD GATE" in surrounding, (
            "Regression #353: issue close must be a HARD GATE"
        )

    def test_implement_md_step8_has_git_push(self):
        """implement.md STEP 8 must contain git push."""
        content = (PLUGIN_DIR / "commands" / "implement.md").read_text()
        step8_section = content.split("### STEP 8")[1].split("# QUICK MODE")[0]
        assert "git push" in step8_section, (
            "Regression #353: STEP 8 must have git push"
        )

    def test_implement_md_step8_has_issue_close(self):
        """implement.md STEP 8 must contain gh issue close."""
        content = (PLUGIN_DIR / "commands" / "implement.md").read_text()
        step8_section = content.split("### STEP 8")[1].split("# QUICK MODE")[0]
        assert "gh issue close" in step8_section, (
            "Regression #353: STEP 8 must have issue close"
        )

    def test_batch_summary_mentions_issues_closed(self):
        """Batch summary template must report issues closed."""
        content = (PLUGIN_DIR / "commands" / "implement-batch.md").read_text()
        assert "Issues closed" in content or "issues closed" in content, (
            "Regression #353: batch summary must report closed issues"
        )


class TestIssue353BypassPatternRegistry:
    """Regression: missing terminal actions must be in bypass patterns."""

    def test_bypass_patterns_has_missing_terminal_actions(self):
        """known_bypass_patterns.json must include missing_terminal_actions pattern."""
        config_path = PLUGIN_DIR / "config" / "known_bypass_patterns.json"
        config = json.loads(config_path.read_text())
        pattern_ids = {p["id"] for p in config["patterns"]}
        assert "missing_terminal_actions" in pattern_ids, (
            "Regression #353: must be in bypass patterns registry"
        )

    def test_expected_end_states_batch_issues_requires_issue_close(self):
        """batch-issues end state must require issue_close."""
        config_path = PLUGIN_DIR / "config" / "known_bypass_patterns.json"
        config = json.loads(config_path.read_text())
        batch_issues = config["expected_end_states"]["batch-issues"]
        assert "issue_close" in batch_issues["required_actions"], (
            "Regression #353: batch-issues must require issue_close"
        )

    def test_expected_end_states_batch_issues_requires_git_push(self):
        """batch-issues end state must require git_push."""
        config_path = PLUGIN_DIR / "config" / "known_bypass_patterns.json"
        config = json.loads(config_path.read_text())
        batch_issues = config["expected_end_states"]["batch-issues"]
        assert "git_push" in batch_issues["required_actions"], (
            "Regression #353: batch-issues must require git_push"
        )
