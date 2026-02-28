"""Regression tests for Issues #368 and #369.

#368: Prompt validator regex misses conversational feature requests
#369: CI analyst false positives on consumer repos
"""

import sys
from pathlib import Path

import pytest

# Add hooks directory to path for direct import
HOOKS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "hooks"
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"
COMMANDS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "commands"
sys.path.insert(0, str(HOOKS_DIR))

from unified_prompt_validator import detect_command_intent


class TestIssue368ConversationalBypass:
    """Regression: 'how do we develop an app' must route to /implement."""

    def test_exact_bypass_prompt(self):
        """The exact prompt that exposed the bug must match /implement."""
        result = detect_command_intent("how do we develop an app")
        assert result is not None, "Exact bypass prompt 'how do we develop an app' must route to /implement"
        assert result["command"] == "/implement"

    def test_lets_build_pattern(self):
        """'let's build X' is a common conversational coding request."""
        result = detect_command_intent("let's build a dashboard")
        assert result is not None
        assert result["command"] == "/implement"

    def test_we_should_add_pattern(self):
        """'we should add X' is a common conversational coding request."""
        result = detect_command_intent("we should add a wizard")
        assert result is not None
        assert result["command"] == "/implement"


class TestIssue369CIAnalystRepoAwareness:
    """Regression: CI analyst must be repo-aware for sections 1 and 2."""

    def test_ci_analyst_contains_repo_aware_calibration(self):
        """CI analyst agent must reference repo-specific hook/pipeline checks."""
        agent_file = AGENTS_DIR / "continuous-improvement-analyst.md"
        assert agent_file.exists(), "CI analyst agent file must exist"
        content = agent_file.read_text()

        # Must contain repo-aware calibration for hook and pipeline checks
        has_repo_awareness = any(term in content.lower() for term in [
            "registered_hooks",
            "settings.json",
            "repo-aware",
            "target repo",
            "consumer repo",
        ])
        assert has_repo_awareness, (
            "CI analyst must contain repo-aware calibration text "
            "(e.g., 'registered_hooks', 'settings.json', 'target repo'). "
            "Without this, it applies autonomous-dev expectations to consumer repos."
        )

    def test_ci_analyst_does_not_hardcode_hook_layer_count(self):
        """CI analyst should not expect exactly 4 hook layers in all repos."""
        agent_file = AGENTS_DIR / "continuous-improvement-analyst.md"
        content = agent_file.read_text()

        # Check that it doesn't hardcode "4 layers" or "4 hook layers" as a universal expectation
        # After the fix, it should calibrate based on the target repo
        lines = content.split("\n")
        hardcoded_4_layers = any(
            "4 layers" in line.lower() or "4 hook layers" in line.lower()
            for line in lines
            if "calibrat" not in line.lower() and "repo" not in line.lower()
        )
        # This is a soft check -- the fix should either remove hardcoded counts
        # or qualify them with "autonomous-dev" / "if registered"
        if hardcoded_4_layers:
            # Verify it's qualified with repo context
            assert any(
                ("4 layers" in line.lower() or "4 hook layers" in line.lower())
                and ("autonomous-dev" in line.lower() or "if" in line.lower() or "when" in line.lower())
                for line in lines
            ), "Hardcoded '4 layers' must be qualified with repo context"

    def test_improve_command_gathers_repo_context(self):
        """The /improve command should instruct gathering repo context before analysis."""
        improve_file = COMMANDS_DIR / "improve.md"
        assert improve_file.exists(), "/improve command file must exist"
        content = improve_file.read_text()

        has_repo_context = any(term in content.lower() for term in [
            "settings.json",
            "registered",
            "repo context",
            "target repo",
        ])
        assert has_repo_context, (
            "/improve command must instruct gathering repo context "
            "(settings.json, registered hooks) before running CI analysis"
        )
