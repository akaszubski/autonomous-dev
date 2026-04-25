"""Spec validation tests for Staged Plan-Exit Pipeline.

Validates acceptance criteria. Per Issue #926, the enforcement gate moved
from UserPromptSubmit (unified_prompt_validator.py) to PreToolUse
(unified_pre_tool.py). The criteria below have been updated accordingly:

1. plan_mode_exit_detector writes "stage": "plan_exited" in the marker file
2. plan_mode_exit_detector outputs a systemMessage mentioning plan-critic
3. unified_pre_tool blocks Task(implementer) when stage=plan_exited
   (was: blocks /implement prompt — slash commands are now observed via
   their underlying tool calls)
6. unified_pre_tool allows Task(implementer) and Bash(gh issue create ...)
   at stage=critique_done, consuming the marker
   (was: allows /implement / /create-issue / /plan-to-issues prompts)
7. unified_session_tracker advances stage from plan_exited to critique_done
   when plan-critic fires
8. Old markers without stage field treated as critique_done (backward compat)
9. All existing test patterns still pass (no broken tests from changes)
10. At least 19 tests cover the 2-state behavior

REMOVED criteria (per Issue #926):
- (was 4) `--skip-review` is a slash-command flag, not a tool call. The
  escape hatch lives at slash-command level (commands/implement.md), not
  in this hook.
- (was 5) Questions ending in `?` are user prompts and never reach
  PreToolUse. The gate observes tool calls only.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"

# Add hooks to path for direct import
sys.path.insert(0, str(HOOKS_DIR))

from plan_mode_exit_detector import main as detector_main, MARKER_PATH  # noqa: E402
from unified_pre_tool import (  # noqa: E402
    _PLAN_EXIT_MARKER_PATH,
    _check_plan_exit_native,
    _check_plan_exit_mcp,
)
from unified_session_tracker import _advance_plan_mode_stage  # noqa: E402


def _write_marker(tmp_path: Path, *, stage: str = "critique_done", include_stage: bool = True) -> Path:
    """Write a plan mode exit marker file for testing.

    Args:
        tmp_path: Temp directory acting as cwd.
        stage: The stage field value.
        include_stage: Whether to include the stage field at all.

    Returns:
        Path to the created marker file.
    """
    marker_path = tmp_path / _PLAN_EXIT_MARKER_PATH
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "spec-validation-session",
    }
    if include_stage:
        marker_data["stage"] = stage
    marker_path.write_text(json.dumps(marker_data))
    return marker_path


# --------------------------------------------------------------------------
# Criterion 1: plan_mode_exit_detector writes "stage": "plan_exited"
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_1_detector_writes_plan_exited_stage(tmp_path: Path):
    """Criterion 1: ExitPlanMode marker must contain stage='plan_exited'."""
    input_data = json.dumps({"tool_name": "ExitPlanMode"})
    with (
        patch("sys.stdin") as mock_stdin,
        patch("os.getcwd", return_value=str(tmp_path)),
    ):
        mock_stdin.read.return_value = input_data
        result = detector_main()

    assert result == 0
    marker_path = tmp_path / MARKER_PATH
    assert marker_path.exists(), "Marker file was not created"
    marker_data = json.loads(marker_path.read_text())
    assert marker_data.get("stage") == "plan_exited", (
        f"Expected stage='plan_exited', got stage='{marker_data.get('stage')}'"
    )


# --------------------------------------------------------------------------
# Criterion 2: plan_mode_exit_detector outputs systemMessage mentioning plan-critic
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_2_detector_system_message_mentions_plan_critic(tmp_path: Path, capsys):
    """Criterion 2: ExitPlanMode output must contain systemMessage with plan-critic."""
    input_data = json.dumps({"tool_name": "ExitPlanMode"})
    with (
        patch("sys.stdin") as mock_stdin,
        patch("os.getcwd", return_value=str(tmp_path)),
    ):
        mock_stdin.read.return_value = input_data
        detector_main()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert "systemMessage" in output, "Output JSON missing 'systemMessage' key"
    assert "plan-critic" in output["systemMessage"].lower(), (
        "systemMessage does not mention plan-critic"
    )


# --------------------------------------------------------------------------
# Criterion 3 (RETARGETED): PreToolUse blocks Task(implementer) at plan_exited
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_3_implement_blocked_at_plan_exited(tmp_path: Path):
    """Criterion 3 (retargeted): Task(implementer) must be blocked at plan_exited.

    Was: prompt /implement blocked at UserPromptSubmit. Now: the underlying
    tool call Task(implementer) is blocked at PreToolUse. Same semantic
    outcome — Claude cannot run the implementer subagent before plan-critic.
    """
    _write_marker(tmp_path, stage="plan_exited")
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = _check_plan_exit_native(
            "Task",
            {"subagent_type": "implementer", "prompt": "implement plan"},
        )
    assert result is not None, "Expected deny, got None (pass-through)"
    assert result[0] == "deny"


# --------------------------------------------------------------------------
# Criterion 6 (RETARGETED): PreToolUse allows Task(implementer) and Bash(gh issue create) at critique_done, consume marker
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_6a_task_implementer_allowed_at_critique_done(tmp_path: Path):
    """Criterion 6a (retargeted): Task(implementer) passes and consumes marker at critique_done."""
    marker = _write_marker(tmp_path, stage="critique_done")
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = _check_plan_exit_native(
            "Task",
            {"subagent_type": "implementer"},
        )
    assert result is None, f"Expected fall-through (None), got {result}"
    assert not marker.exists(), "Marker should be consumed"


def test_spec_staged_plan_exit_6b_bash_gh_issue_create_allowed_at_critique_done(tmp_path: Path):
    """Criterion 6b (retargeted): Bash(gh issue create) passes and consumes marker at critique_done."""
    marker = _write_marker(tmp_path, stage="critique_done")
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = _check_plan_exit_native(
            "Bash",
            {"command": "gh issue create --title 'foo' --body 'bar'"},
        )
    assert result is None, f"Expected fall-through (None), got {result}"
    assert not marker.exists(), "Marker should be consumed"


def test_spec_staged_plan_exit_6c_task_issue_creator_allowed_at_critique_done(tmp_path: Path):
    """Criterion 6c (retargeted): Task(issue-creator) consumes marker at critique_done."""
    marker = _write_marker(tmp_path, stage="critique_done")
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = _check_plan_exit_native(
            "Task",
            {"subagent_type": "issue-creator"},
        )
    assert result is None
    assert not marker.exists()


# --------------------------------------------------------------------------
# Criterion 7: stage advances from plan_exited to critique_done
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_7_stage_advances_on_proceed_verdict(tmp_path: Path):
    """Criterion 7: `_advance_plan_mode_stage` advances stage from `plan_exited` to `critique_done` ONLY when a PROCEED verdict file is present (Issue #927 gate)."""
    marker_path = tmp_path / ".claude" / "plan_mode_exit.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "spec-validation-session",
        "stage": "plan_exited",
    }
    marker_path.write_text(json.dumps(marker_data, indent=2))

    verdict_path = tmp_path / ".claude" / "plan_critic_verdict.json"
    verdict_path.write_text(json.dumps({
        "verdict": "PROCEED",
        "composite_score": 3.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    with patch("os.getcwd", return_value=str(tmp_path)):
        _advance_plan_mode_stage()

    updated = json.loads(marker_path.read_text())
    assert updated["stage"] == "critique_done", (
        f"Expected stage='critique_done' after advance, got '{updated['stage']}'"
    )


# --------------------------------------------------------------------------
# Criterion 8: old markers without stage treated as critique_done
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_8_no_stage_field_treated_as_critique_done(tmp_path: Path):
    """Criterion 8: Marker without 'stage' field must behave as critique_done.

    PreToolUse retargeting: at critique_done, Task(implementer) passes
    and consumes the marker. The semantic property (back-compat) is
    preserved exactly — old markers don't block.
    """
    marker = _write_marker(tmp_path, include_stage=False)
    with patch("os.getcwd", return_value=str(tmp_path)):
        result = _check_plan_exit_native("Task", {"subagent_type": "implementer"})
    assert result is None, (
        f"Expected fall-through (None) for stageless marker (back-compat), got {result}"
    )
    assert not marker.exists(), "Marker should be consumed"


# --------------------------------------------------------------------------
# Criterion 9: all existing test patterns still pass
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_9_existing_tests_pass():
    """Criterion 9: All existing unit tests for the changed test files must pass.

    Per Issue #926, test_plan_mode_enforcement.py was deleted (superseded
    by test_plan_exit_pretool_enforcement.py). This criterion now verifies
    the new test files pass.
    """
    test_files = [
        str(PROJECT_ROOT / "tests/unit/hooks/test_plan_mode_exit_detector.py"),
        str(PROJECT_ROOT / "tests/unit/hooks/test_plan_exit_pretool_enforcement.py"),
        str(PROJECT_ROOT / "tests/unit/hooks/test_plan_critic_stage_advance.py"),
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + test_files + ["-v", "--tb=short", "-q", "--no-cov"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Existing tests failed with returncode {result.returncode}.\n"
        f"stdout:\n{result.stdout[-2000:]}\n"
        f"stderr:\n{result.stderr[-1000:]}"
    )


# --------------------------------------------------------------------------
# Criterion 10: at least 19 tests cover the 2-state staged behavior
# --------------------------------------------------------------------------

def test_spec_staged_plan_exit_10_minimum_test_count():
    """Criterion 10: At least 19 tests must cover the 2-state staged behavior.

    Per Issue #926, the count is computed across the new PreToolUse test
    file plus the unchanged detector and stage-advance test files.
    """
    test_files = [
        PROJECT_ROOT / "tests/unit/hooks/test_plan_mode_exit_detector.py",
        PROJECT_ROOT / "tests/unit/hooks/test_plan_exit_pretool_enforcement.py",
        PROJECT_ROOT / "tests/unit/hooks/test_plan_critic_stage_advance.py",
    ]

    stage_related_tests = 0
    stage_keywords = [
        "stage", "plan_exited", "critique_done", "skip_review",
        "plan_critic", "advance", "backward_compat", "system_message",
        "marker", "consume",
    ]

    for test_file in test_files:
        content = test_file.read_text()
        # Find all test function/method names
        import re
        test_names = re.findall(r"def (test_\w+)", content)
        for name in test_names:
            name_lower = name.lower()
            if any(kw in name_lower for kw in stage_keywords):
                stage_related_tests += 1

    assert stage_related_tests >= 19, (
        f"Expected at least 19 tests covering 2-state behavior, found {stage_related_tests}"
    )
