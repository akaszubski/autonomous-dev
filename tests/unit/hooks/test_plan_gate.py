"""Unit tests for plan_gate.py hook.

Tests the hook's decision logic including tool filtering,
doc exemptions, complexity thresholds, plan validation,
and fail-open behavior.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "plan_gate.py"


def run_hook(
    input_data: dict,
    *,
    env_override: dict | None = None,
    plans_dir: Path | None = None,
) -> dict:
    """Run the plan_gate hook as a subprocess and return parsed output.

    Args:
        input_data: JSON input to send via stdin.
        env_override: Additional environment variables.
        plans_dir: If provided, set cwd to parent so .claude/plans is found.

    Returns:
        Parsed JSON output from the hook's stdout.
    """
    env = os.environ.copy()
    # Ensure SKIP_PLAN_CHECK is not set by default
    env.pop("SKIP_PLAN_CHECK", None)
    if env_override:
        env.update(env_override)

    cwd = None
    if plans_dir:
        # The hook looks for .claude/plans relative to cwd or git root
        # Set cwd to the parent of .claude
        cwd = str(plans_dir.parent.parent)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=10,
    )

    assert result.returncode == 0, f"Hook returned non-zero: {result.stderr}"

    # Parse stdout JSON
    stdout = result.stdout.strip()
    assert stdout, f"No stdout output. stderr: {result.stderr}"
    return json.loads(stdout)


class TestToolFiltering:
    """Only Write and Edit tools should be subject to plan checks."""

    def test_non_write_tool_allowed(self):
        output = run_hook({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x.py"}})
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_bash_tool_allowed(self):
        output = run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_grep_tool_allowed(self):
        output = run_hook({"tool_name": "Grep", "tool_input": {"pattern": "foo"}})
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


class TestDocExemption:
    """Documentation files should never be blocked."""

    def test_md_file_allowed(self):
        output = run_hook({
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/README.md", "content": "x" * 200 + "\n" * 200},
        })
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_changelog_allowed(self):
        output = run_hook({
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/CHANGELOG.md", "content": "x\n" * 200},
        })
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_docs_dir_allowed(self):
        output = run_hook({
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/guide.txt", "content": "x\n" * 200},
        })
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


class TestSimpleEditExemption:
    """Simple edits below threshold should never be blocked."""

    def test_small_write_allowed(self):
        output = run_hook({
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/small.py", "content": "print('hello')\n"},
        })
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_small_edit_allowed(self):
        output = run_hook({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/file.py",
                "old_string": "old",
                "new_string": "new",
            },
        })
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


class TestSkipPlanCheck:
    """SKIP_PLAN_CHECK=1 should bypass all checks."""

    def test_skip_env_allows_complex_write(self):
        output = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/complex.py",
                    "content": "x\n" * 200,
                },
            },
            env_override={"SKIP_PLAN_CHECK": "1"},
        )
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


class TestPlanValidation:
    """Tests for plan existence and validation logic."""

    def test_complex_write_without_plan_blocks(self, tmp_path):
        """Complex write with no plan file should be blocked."""
        # Create .claude/plans directory (empty)
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        output = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/complex.py",
                    "content": "x\n" * 200,
                },
            },
            plans_dir=plans_dir,
        )
        decision = output["hookSpecificOutput"]["permissionDecision"]
        # Issue #1589: was "block", which is outside the documented PreToolUse
        # enum allow|deny|ask. The client rejected that envelope and ran the
        # tool anyway, so this test passed while the gate did nothing.
        assert decision == "deny"

    def test_block_message_contains_required_next_action(self, tmp_path):
        """Block message must include REQUIRED NEXT ACTION directive."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        output = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/complex.py",
                    "content": "x\n" * 200,
                },
            },
            plans_dir=plans_dir,
        )
        system_msg = output.get("systemMessage", "")
        assert "REQUIRED NEXT ACTION" in system_msg
        assert "/plan" in system_msg

    def test_valid_plan_allows_complex_write(self, tmp_path):
        """Complex write with valid plan should be allowed."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        plan = plans_dir / "feature.md"
        plan.write_text(
            "# Plan\n\n"
            "## WHY + SCOPE\nReasons.\n\n"
            "## Existing Solutions\nNone found.\n\n"
            "## Minimal Path\nSmall change.\n"
        )

        output = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/complex.py",
                    "content": "x\n" * 200,
                },
            },
            plans_dir=plans_dir,
        )
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_plan_missing_sections_blocks(self, tmp_path):
        """Plan missing required sections should block."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        plan = plans_dir / "incomplete.md"
        plan.write_text(
            "# Plan\n\n"
            "## WHY + SCOPE\nReasons.\n\n"
            # Missing Existing Solutions and Minimal Path
        )

        output = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/complex.py",
                    "content": "x\n" * 200,
                },
            },
            plans_dir=plans_dir,
        )
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"  # Issue #1589: enum-conformant refusal
        system_msg = output.get("systemMessage", "")
        assert "Existing Solutions" in system_msg

    def test_expired_plan_allows_with_warning(self, tmp_path):
        """Expired plan (>72h) should allow but warn."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        plan = plans_dir / "old.md"
        plan.write_text(
            "# Plan\n\n"
            "## WHY + SCOPE\nReasons.\n\n"
            "## Existing Solutions\nNone found.\n\n"
            "## Minimal Path\nSmall change.\n"
        )
        old_time = time.time() - (73 * 3600)
        os.utime(plan, (old_time, old_time))

        output = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/complex.py",
                    "content": "x\n" * 200,
                },
            },
            plans_dir=plans_dir,
        )
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


class TestFailOpen:
    """Hook must fail-open on any exception."""

    def test_invalid_json_input_allows(self):
        """Invalid JSON input should result in allow (fail-open)."""
        env = os.environ.copy()
        env.pop("SKIP_PLAN_CHECK", None)

        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not valid json {{{",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout.strip())
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_empty_input_allows(self):
        """Empty stdin should result in allow (fail-open)."""
        env = os.environ.copy()
        env.pop("SKIP_PLAN_CHECK", None)

        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout.strip())
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"
