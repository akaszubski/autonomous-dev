"""Regression tests for plan-exit enforcement leaks (Issue #926).

Each test targets a specific form of the leak that existed when enforcement
was at UserPromptSubmit. After moving to PreToolUse, these paths are all
covered because every tool call is observed.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import unified_pre_tool  # noqa: E402
from unified_pre_tool import (  # noqa: E402
    _PLAN_EXIT_MARKER_PATH,
    _check_plan_exit_native,
)


@pytest.fixture(autouse=True)
def _force_in_adev_project(monkeypatch):
    """Issue #938: existing leak-regression tests assume in-project context.

    The scope guard added by #938 short-circuits the gate when cwd is not an
    autonomous-dev repo (tmp_path is not). Patch the detector wrapper so
    these regressions keep exercising the deny paths they were written for.
    """
    monkeypatch.setattr(
        unified_pre_tool, "_is_adev_project_fn", lambda: True
    )
    for var in (
        "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW",
        "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT",
    ):
        monkeypatch.delenv(var, raising=False)


def _write_plan_exited_marker(tmp_path: Path) -> Path:
    """Write a fresh plan_exited marker for leak regression tests."""
    marker_path = tmp_path / _PLAN_EXIT_MARKER_PATH
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "regression-test",
        "stage": "plan_exited",
    }
    marker_path.write_text(json.dumps(marker_data))
    return marker_path


def test_in_turn_gh_issue_create_blocked_at_plan_exited(tmp_path: Path):
    """Leak #1: orchestrator in-turn runs `gh issue create` directly via Bash.

    Before #926, UserPromptSubmit never saw this tool call (it was emitted
    by the model during a turn, not from a user prompt), so the old gate
    missed it. The PreToolUse gate observes every tool call and blocks.
    """
    _write_plan_exited_marker(tmp_path)
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = _check_plan_exit_native(
            "Bash",
            {"command": "gh issue create --title 'Foo' --body 'Bar'"},
        )
    assert result is not None, "PreToolUse gate must block in-turn gh issue create"
    assert result[0] == "deny"


def test_in_turn_task_implementer_blocked_at_plan_exited(tmp_path: Path):
    """Leak #2: in-turn Task(implementer) invocation at plan_exited.

    Same root cause: subagent invocations are tool calls, not user prompts,
    so UserPromptSubmit never saw them. PreToolUse observes and blocks.
    """
    _write_plan_exited_marker(tmp_path)
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = _check_plan_exit_native(
            "Task",
            {"subagent_type": "implementer", "prompt": "implement the plan"},
        )
    assert result is not None
    assert result[0] == "deny"


def test_short_user_reply_b_does_not_falseblock(tmp_path: Path):
    """Leak #3: short user reply "b" inside skill conversation doesn't falseblock.

    Before #926, the UserPromptSubmit gate treated any non-question non-allowed
    command prompt as a block at plan_exited — so users replying "proceed"
    or "b" in a /plan-to-issues skill flow got false-blocked. After moving to
    PreToolUse, user prompts are never blocked by the plan-exit gate (they
    don't flow through PreToolUse at all). The gate fires on the follow-up
    tool calls the model makes in response.
    """
    # Smoke test: short user replies aren't checked here because
    # UserPromptSubmit no longer carries the gate. Verify the enforcement
    # lives exclusively at PreToolUse by checking that the old module no
    # longer defines the gate function.
    from unified_prompt_validator import __dict__ as validator_globals
    assert "_check_plan_mode_enforcement" not in validator_globals, (
        "Old UserPromptSubmit gate must be removed (Issue #926)"
    )


def test_xml_wrapped_slash_command_no_longer_relevant(tmp_path: Path):
    """Leak #4: Issue #922 XML-wrapping edge case is structurally irrelevant now.

    The XML-wrapping bug only existed because enforcement was at
    UserPromptSubmit. With PreToolUse, the gate never sees prompts — only
    tool calls. So the leak class doesn't apply.
    """
    _write_plan_exited_marker(tmp_path)
    with patch("os.getcwd", return_value=str(tmp_path)):
        # Whatever the user's prompt form was, the gate observes the Task
        # tool call that Claude issues. If it's Task(implementer), block.
        result = _check_plan_exit_native(
            "Task",
            {"subagent_type": "implementer"},
        )
    assert result is not None
    assert result[0] == "deny"


def test_pretool_blocks_when_userpromptsubmit_blackboxed(tmp_path: Path):
    """Leak #5 (the proof): marker present, only Bash(gh issue create) fired,
    NO UserPromptSubmit invocation. Old gate saw nothing; new gate sees all.

    AC #18: No UserPromptSubmit blocks any prompt due to plan-mode exit
    (the feature was fully migrated).
    """
    _write_plan_exited_marker(tmp_path)
    with patch("os.getcwd", return_value=str(tmp_path)):
        # Simulate Claude issuing gh issue create as its first tool call in a
        # turn, with zero UserPromptSubmit events. PreToolUse catches it.
        result = _check_plan_exit_native(
            "Bash",
            {"command": "gh issue create --title hi"},
        )
    assert result is not None
    assert result[0] == "deny"


def test_skill_in_flight_reply_not_blocked_at_plan_exited_stage(tmp_path: Path):
    """Leak #6 (from #926 comment): skill-in-flight reply "proceed".

    Reproduction: /plan-to-issues asks "confirm?" and the user replies
    "proceed". With the old gate at UserPromptSubmit, "proceed" was
    falseblocked at plan_exited. After moving to PreToolUse, user replies
    never reach the gate — only follow-up tool calls do.

    This test verifies the behavioral property: tool calls the skill makes
    after "proceed" (e.g., Read, Glob, Grep to inspect the plan) fall
    through because they're on the plan_exited allowlist. Task(plan-critic)
    also falls through.
    """
    _write_plan_exited_marker(tmp_path)
    with patch("os.getcwd", return_value=str(tmp_path)):
        # Skill's natural follow-up reads after user says "proceed"
        assert _check_plan_exit_native("Read", {"file_path": "foo.md"}) is None
        assert _check_plan_exit_native("Glob", {"pattern": "**/*.md"}) is None
        assert _check_plan_exit_native("Grep", {"pattern": "AC"}) is None
        # Plan-critic invocation also falls through
        assert _check_plan_exit_native("Task", {"subagent_type": "plan-critic"}) is None
