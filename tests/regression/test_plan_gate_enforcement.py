"""Regression tests for plan_gate hook enforcement.

End-to-end tests that verify the hook produces correct JSON output
for various scenarios. These tests run the actual hook script.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "plan_gate.py"


def _run_hook(input_data: dict, *, cwd: str | None = None, env_extra: dict | None = None) -> dict:
    """Run plan_gate.py and return parsed JSON output."""
    env = os.environ.copy()
    env.pop("SKIP_PLAN_CHECK", None)
    if env_extra:
        env.update(env_extra)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=10,
    )
    assert result.returncode == 0
    return json.loads(result.stdout.strip())


class TestPlanGateEnforcement:
    """E2E regression tests for plan_gate enforcement."""

    def test_e2e_plan_file_allows(self, tmp_path):
        """Create a valid plan file, verify hook allows complex write."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        plan = plans_dir / "feature-x.md"
        plan.write_text(
            "# Plan: Feature X\n\n"
            "## WHY + SCOPE\nImprove performance.\n\n"
            "## Existing Solutions\nSearched, nothing applicable.\n\n"
            "## Minimal Path\nModify engine.py, add cache layer.\n"
        )

        output = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/engine.py", "content": "code\n" * 200},
            },
            cwd=str(tmp_path),
        )
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_e2e_no_plan_blocks_with_correct_json(self, tmp_path):
        """No plan file, verify hook blocks with correct JSON format."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        output = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/engine.py", "content": "code\n" * 200},
            },
            cwd=str(tmp_path),
        )

        hook_output = output["hookSpecificOutput"]
        # Issue #1589: "block" is not in the PreToolUse enum (allow|deny|ask).
        # Claude Code rejected the envelope and executed the write regardless,
        # so the pre-#1589 expectation pinned a refusal that never refused.
        assert hook_output["permissionDecision"] == "deny"
        assert hook_output["hookEventName"] == "PreToolUse"
        assert "REQUIRED NEXT ACTION" in output.get("systemMessage", "")

    def test_e2e_skip_plan_check_bypass(self, tmp_path):
        """SKIP_PLAN_CHECK=1 allows even without plan."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        output = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/engine.py", "content": "code\n" * 200},
            },
            cwd=str(tmp_path),
            env_extra={"SKIP_PLAN_CHECK": "1"},
        )
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_e2e_doc_files_never_blocked(self):
        """Documentation files are never blocked regardless of plan state."""
        for file_path in ["README.md", "docs/guide.md", "CHANGELOG.md", "notes.rst"]:
            output = _run_hook({
                "tool_name": "Write",
                "tool_input": {"file_path": file_path, "content": "content\n" * 200},
            })
            decision = output["hookSpecificOutput"]["permissionDecision"]
            assert decision == "allow", f"{file_path} should be allowed but was {decision}"

    def test_e2e_output_format_matches_hook_protocol(self, tmp_path):
        """Verify output JSON matches the Claude Code hook protocol."""
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)

        output = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/x.py", "content": "x\n" * 200},
            },
            cwd=str(tmp_path),
        )

        # Must have hookSpecificOutput with required fields
        assert "hookSpecificOutput" in output
        hook_output = output["hookSpecificOutput"]
        assert "hookEventName" in hook_output
        assert "permissionDecision" in hook_output
        assert "permissionDecisionReason" in hook_output
        assert hook_output["hookEventName"] == "PreToolUse"
        # Issue #1589: the protocol enum is allow|deny|ask (docs/HOOKS.md).
        # Asserting membership in the enum rather than in a hand-kept tuple is
        # the point — the old tuple ACCEPTED the out-of-enum value that made
        # every refusal fail open.
        assert hook_output["permissionDecision"] in ("allow", "deny", "ask")
