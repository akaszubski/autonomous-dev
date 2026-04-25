"""Unit tests for strip_global_duplicates and strip_duplicate_hooks CLI.

Issue #944: Per-repo settings.json templates must not redeclare hooks already
registered globally in ~/.claude/settings.json. The strip primitive (in
lib/settings_merger.py) and the CLI wrapper (scripts/strip_duplicate_hooks.py)
remove these duplicates.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add plugins lib path (matches tests/conftest.py pattern)
_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from settings_merger import (  # noqa: E402
    CANONICAL_GLOBAL_HOOKS,
    strip_global_duplicates,
)


PLUGIN_SCRIPTS = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "scripts"
STRIP_CLI = PLUGIN_SCRIPTS / "strip_duplicate_hooks.py"


def _make_settings(*, with_canonical: int = 7, with_custom: int = 0) -> dict:
    """Build a settings dict containing N canonical hooks and M custom hooks."""
    canonical = list(CANONICAL_GLOBAL_HOOKS[:with_canonical])
    hooks: dict = {}
    if "python3 ~/.claude/hooks/unified_prompt_validator.py" in canonical:
        hooks["UserPromptSubmit"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/unified_prompt_validator.py",
                    }
                ],
            }
        ]
    pre_tool = []
    if "python3 ~/.claude/hooks/plan_gate.py" in canonical:
        pre_tool.append(
            {
                "matcher": "Write|Edit",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/plan_gate.py",
                    }
                ],
            }
        )
    for i in range(with_custom):
        pre_tool.append(
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python3 ~/.claude/hooks/custom_{i}.py",
                    }
                ],
            }
        )
    if pre_tool:
        hooks["PreToolUse"] = pre_tool
    post_tool_use = []
    if "python3 ~/.claude/hooks/plan_mode_exit_detector.py" in canonical:
        post_tool_use.append(
            {
                "matcher": "ExitPlanMode",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/plan_mode_exit_detector.py",
                    }
                ],
            }
        )
    if post_tool_use:
        hooks["PostToolUse"] = post_tool_use
    stop = []
    if "python3 ~/.claude/hooks/stop_quality_gate.py" in canonical:
        stop.append(
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/stop_quality_gate.py",
                    }
                ],
            }
        )
    if (
        "CONVERSATION_ARCHIVE=true python3 ~/.claude/hooks/conversation_archiver.py"
        in canonical
    ):
        stop.append(
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "CONVERSATION_ARCHIVE=true python3 ~/.claude/hooks/conversation_archiver.py",
                    }
                ],
            }
        )
    if stop:
        hooks["Stop"] = stop
    if "python3 ~/.claude/hooks/unified_session_tracker.py" in canonical:
        hooks["SubagentStop"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/unified_session_tracker.py",
                    }
                ],
            }
        ]
    if "python3 ~/.claude/hooks/task_completed_handler.py" in canonical:
        hooks["TaskCompleted"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ~/.claude/hooks/task_completed_handler.py",
                    }
                ],
            }
        ]
    return {"permissions": {"allow": ["Read"]}, "hooks": hooks}


class TestStripGlobalDuplicates:
    """Cover the strip_global_duplicates primitive."""

    def test_idempotency(self):
        """Stripping 7 canonicals removes 7; second call removes 0."""
        settings = _make_settings(with_canonical=7, with_custom=2)
        original = copy.deepcopy(settings)

        first, issues_first = strip_global_duplicates(settings, source_label="t.json")
        assert len(issues_first) == 7
        # Second call yields no new issues, identical structure.
        second, issues_second = strip_global_duplicates(first, source_label="t.json")
        assert issues_second == []
        assert second == first
        # Original input is NOT mutated.
        assert settings == original

    def test_empty_group_cleanup(self):
        """When all hooks in an event are canonical, the event key is dropped."""
        settings = _make_settings(with_canonical=7, with_custom=0)
        result, issues = strip_global_duplicates(settings)
        # No custom hooks remain, so "hooks" key MUST be removed entirely.
        assert "hooks" not in result, (
            f"Expected hooks key removed but got: {result.get('hooks')}"
        )
        # permissions key still preserved
        assert result.get("permissions") == {"allow": ["Read"]}
        assert len(issues) == 7

    def test_preserve_customization(self):
        """Custom hooks survive stripping; only canonical commands are removed."""
        settings = _make_settings(with_canonical=7, with_custom=3)
        result, issues = strip_global_duplicates(settings)
        # 7 canonical removed
        assert len(issues) == 7
        # PreToolUse should retain ONLY the 3 custom matchers (plan_gate dropped)
        pre_tool = result["hooks"]["PreToolUse"]
        assert len(pre_tool) == 3, (
            f"Expected 3 custom matchers in PreToolUse, got {len(pre_tool)}: {pre_tool}"
        )
        for matcher in pre_tool:
            cmds = [h["command"] for h in matcher["hooks"]]
            for cmd in cmds:
                assert "custom_" in cmd, (
                    f"Unexpected non-custom command preserved: {cmd}"
                )

    def test_preserve_strict_mode_precommit_hooks(self):
        """Non-canonical PreCommit hooks (e.g., enforce_tdd.py) MUST survive."""
        settings = {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/unified_prompt_validator.py",
                            }
                        ],
                    }
                ],
                "PreCommit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python hooks/validate_project_alignment.py || exit 1",
                            },
                            {
                                "type": "command",
                                "command": "python hooks/enforce_orchestrator.py || exit 1",
                            },
                            {
                                "type": "command",
                                "command": "python hooks/enforce_tdd.py || exit 1",
                            },
                        ],
                    }
                ],
            }
        }
        result, issues = strip_global_duplicates(settings)
        # Only the canonical UserPromptSubmit was stripped.
        assert len(issues) == 1
        # PreCommit hooks fully preserved
        pre_commit = result["hooks"]["PreCommit"]
        assert len(pre_commit) == 1
        assert len(pre_commit[0]["hooks"]) == 3
        cmds = [h["command"] for h in pre_commit[0]["hooks"]]
        assert any("validate_project_alignment" in c for c in cmds)
        assert any("enforce_orchestrator" in c for c in cmds)
        assert any("enforce_tdd" in c for c in cmds)

    def test_no_match_with_extra_args(self):
        """Commands with extra args (e.g., '&& echo') are NOT stripped (exact match)."""
        cmd_with_suffix = (
            "python3 ~/.claude/hooks/unified_prompt_validator.py && echo hi"
        )
        settings = {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": cmd_with_suffix}
                        ],
                    }
                ]
            }
        }
        result, issues = strip_global_duplicates(settings)
        assert issues == []
        assert result["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] == cmd_with_suffix

    def test_returns_validation_issues(self):
        """Each removed hook produces a ValidationIssue with severity=info."""
        settings = _make_settings(with_canonical=2)
        _, issues = strip_global_duplicates(settings, source_label="abc.json")
        assert len(issues) == 2
        for issue in issues:
            assert issue.severity == "info"
            assert issue.category == "hook-dedup"
            assert issue.file_path == "abc.json"
            assert "Stripped global duplicate" in issue.message

    def test_no_hooks_section_returns_unchanged(self):
        """Settings without a hooks key are returned unchanged."""
        settings = {"permissions": {"allow": ["Read"]}}
        result, issues = strip_global_duplicates(settings)
        assert issues == []
        assert result == settings


class TestStripDuplicateHooksCLI:
    """Cover the CLI wrapper script behavior (subprocess)."""

    def test_dogfooding_filename_skip(self, tmp_path):
        """settings.autonomous-dev.json basename triggers dogfooding skip."""
        target = tmp_path / "settings.autonomous-dev.json"
        target.write_text(json.dumps(_make_settings(with_canonical=2)))
        result = subprocess.run(
            [sys.executable, str(STRIP_CLI), "--target", str(target)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["removed_count"] == 0
        assert payload["skipped_reason"] == "dogfooding"

    def test_dogfooding_marker_skip(self, tmp_path):
        """_autonomous_dev_dogfooding=true triggers dogfooding skip."""
        target = tmp_path / "fixture.json"
        settings = _make_settings(with_canonical=3)
        settings["_autonomous_dev_dogfooding"] = True
        target.write_text(json.dumps(settings))
        result = subprocess.run(
            [sys.executable, str(STRIP_CLI), "--target", str(target)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["skipped_reason"] == "dogfooding"
        assert payload["removed_count"] == 0
        # File is NOT modified
        assert json.loads(target.read_text()) == settings

    def test_malformed_json_returns_error(self, tmp_path):
        """Malformed JSON yields success=false with error string, exit 0."""
        target = tmp_path / "bad.json"
        target.write_text("{not valid json")
        result = subprocess.run(
            [sys.executable, str(STRIP_CLI), "--target", str(target)],
            capture_output=True,
            text=True,
        )
        # Lenient: exit 0 even on JSON error so install.sh continues.
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["success"] is False
        assert payload["error"] is not None
        assert "Invalid JSON" in payload["error"] or "JSON" in payload["error"]

    def test_dry_run_does_not_write(self, tmp_path):
        """--dry-run reports counts but does not modify the file."""
        target = tmp_path / "fixture.json"
        original = _make_settings(with_canonical=4)
        target.write_text(json.dumps(original, indent=2))
        result = subprocess.run(
            [
                sys.executable,
                str(STRIP_CLI),
                "--target",
                str(target),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["removed_count"] == 4
        # File unchanged
        assert json.loads(target.read_text()) == original

    def test_target_not_found(self, tmp_path):
        """Missing target yields success=false."""
        target = tmp_path / "nonexistent.json"
        result = subprocess.run(
            [sys.executable, str(STRIP_CLI), "--target", str(target)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["success"] is False
        assert "not found" in payload["error"].lower()
