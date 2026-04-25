"""Spec-validation tests for Issue #944 — global hook deduplication.

These tests are derived ONLY from the acceptance criteria. They do not
inspect implementer output, reviewer feedback, or implementation strategy.
They validate observable behavior against the spec.

Acceptance Criteria:
    1. Per-repo templates do NOT embed global hook paths (the 7 canonical
       hooks belonging in ~/.claude/settings.json only).
    2. install.sh and /sync detect and strip duplicated hooks blocks from
       existing per-repo settings.json files.
    3. Defensive hooks (sys.exit(0) on missing deps) — already done in #953.
    4. /health-check validates hook command paths resolve — already done in
       #950.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "plugins/autonomous-dev/templates"
SCRIPTS_DIR = REPO_ROOT / "plugins/autonomous-dev/scripts"
LIB_DIR = REPO_ROOT / "plugins/autonomous-dev/lib"
INSTALL_SH = REPO_ROOT / "install.sh"
SYNC_MD = REPO_ROOT / "plugins/autonomous-dev/commands/sync.md"
STRIP_HELPER = SCRIPTS_DIR / "strip_duplicate_hooks.py"

# The 7 canonical global hooks per the issue spec. These belong in
# ~/.claude/settings.json only.
CANONICAL_GLOBAL_HOOK_FILENAMES = (
    "unified_prompt_validator.py",
    "plan_gate.py",
    "plan_mode_exit_detector.py",
    "stop_quality_gate.py",
    "task_completed_handler.py",
    "unified_session_tracker.py",
    "conversation_archiver.py",
)

PER_REPO_TEMPLATES = (
    "settings.default.json",
    "settings.granular-bash.json",
    "settings.permission-batching.json",
    "settings.strict-mode.json",
)


def _load_template(name: str) -> dict:
    return json.loads((TEMPLATES_DIR / name).read_text(encoding="utf-8"))


def _all_hook_commands(settings: dict) -> list[str]:
    """Flatten every hook command string from a settings.json dict."""
    commands: list[str] = []
    for _event, matchers in (settings.get("hooks") or {}).items():
        if not isinstance(matchers, list):
            continue
        for matcher in matchers:
            if not isinstance(matcher, dict):
                continue
            for entry in matcher.get("hooks") or []:
                if isinstance(entry, dict) and isinstance(entry.get("command"), str):
                    commands.append(entry["command"])
    return commands


# --------------------------------------------------------------------------
# AC1: Per-repo templates do not embed canonical global hook paths.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("template_name", PER_REPO_TEMPLATES)
def test_spec_issue944_1_template_has_no_canonical_global_hooks(template_name):
    """AC1: each per-repo template MUST NOT contain canonical global hooks."""
    settings = _load_template(template_name)
    commands = _all_hook_commands(settings)
    leaked = []
    for cmd in commands:
        for canonical in CANONICAL_GLOBAL_HOOK_FILENAMES:
            if canonical in cmd:
                leaked.append((canonical, cmd))
    assert not leaked, (
        f"{template_name} embeds canonical global hooks (must be in "
        f"~/.claude/settings.json only): {leaked}"
    )


def test_spec_issue944_1_dogfood_template_untouched():
    """AC1-subtle: settings.autonomous-dev.json MUST be untouched.

    Dogfooding intentionally retains its hook configuration. The diff for
    this batch must NOT modify this file.
    """
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "HEAD",
            "--",
            "plugins/autonomous-dev/templates/settings.autonomous-dev.json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == "", (
        "settings.autonomous-dev.json was modified — dogfooding template "
        "must remain untouched per plan."
    )


def test_spec_issue944_1_settings_local_untouched():
    """AC1-subtle: settings.local.json MUST be untouched (deferred per plan)."""
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "HEAD",
            "--",
            "plugins/autonomous-dev/templates/settings.local.json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == "", (
        "settings.local.json was modified — preserved/deferred list per "
        "plan-critic."
    )


def test_spec_issue944_1_strict_mode_preserves_repo_specific_hooks():
    """Strict-mode MUST retain non-canonical PreCommit hooks (project alignment, TDD)."""
    settings = _load_template("settings.strict-mode.json")
    commands_text = "\n".join(_all_hook_commands(settings))
    required_repo_hooks = (
        "validate_project_alignment.py",
        "enforce_orchestrator.py",
        "enforce_tdd.py",
    )
    missing = [h for h in required_repo_hooks if h not in commands_text]
    assert not missing, (
        f"strict-mode lost non-canonical PreCommit hooks: {missing}"
    )


# --------------------------------------------------------------------------
# AC2: install.sh and /sync detect and strip duplicated hooks blocks.
# --------------------------------------------------------------------------


def test_spec_issue944_2_install_sh_invokes_strip_helper():
    """AC2 (install.sh): install.sh MUST invoke strip_duplicate_hooks.py."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "strip_duplicate_hooks.py" in text, (
        "install.sh must invoke strip_duplicate_hooks.py to migrate "
        "existing settings.json files."
    )


def test_spec_issue944_2_install_sh_calls_migration_in_main():
    """AC2 (install.sh): the migration step MUST be wired into main()."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    # The strip step must be invoked, not just defined as a function.
    # Search for an invocation outside the function definition.
    pattern = re.compile(r"^\s*strip_duplicate_global_hooks\b", re.MULTILINE)
    matches = pattern.findall(text)
    # >=2 occurrences: the function definition line + at least one call.
    assert len(matches) >= 2, (
        f"install.sh defines strip_duplicate_global_hooks but does not "
        f"invoke it (matches={len(matches)})."
    )


def test_spec_issue944_2_sync_md_instructs_strip_invocation():
    """AC2 (/sync): commands/sync.md MUST instruct strip helper invocation."""
    text = SYNC_MD.read_text(encoding="utf-8")
    assert "strip_duplicate_hooks.py" in text, (
        "commands/sync.md must instruct the model to invoke "
        "strip_duplicate_hooks.py."
    )


def test_spec_issue944_2_strip_helper_strips_canonical_hooks():
    """AC2 (functional): helper strips canonical global hooks from a settings file."""
    # Construct a settings.json that contains a duplicated global hook.
    duplicated_settings = {
        "permissions": {"allow": ["Read"], "deny": []},
        "hooks": {
            "UserPromptSubmit": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_prompt_validator.py",
                            "timeout": 5,
                        }
                    ],
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo repo-specific",
                            "timeout": 5,
                        }
                    ],
                }
            ],
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "settings.json"
        target.write_text(json.dumps(duplicated_settings), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(STRIP_HELPER), "--target", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"helper exit nonzero: {result.stderr}"
        report = json.loads(result.stdout)
        assert report["success"] is True
        assert report["removed_count"] == 1, (
            f"expected 1 stripped hook, got {report['removed_count']}: "
            f"{report.get('events')}"
        )

        # Verify the file was actually rewritten without the canonical hook.
        rewritten = json.loads(target.read_text(encoding="utf-8"))
        all_cmds = _all_hook_commands(rewritten)
        for cmd in all_cmds:
            assert "unified_prompt_validator.py" not in cmd, (
                f"canonical hook leaked after strip: {cmd}"
            )
        # Repo-specific hook MUST be preserved.
        assert any("echo repo-specific" in c for c in all_cmds), (
            "repo-specific hook was incorrectly stripped"
        )


def test_spec_issue944_2_strip_helper_idempotent():
    """AC2 (idempotency): re-running on a clean file produces removed_count=0."""
    clean_settings = {
        "permissions": {"allow": ["Read"], "deny": []},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo repo-only",
                            "timeout": 5,
                        }
                    ],
                }
            ]
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "settings.json"
        target.write_text(json.dumps(clean_settings), encoding="utf-8")

        # First run.
        r1 = subprocess.run(
            [sys.executable, str(STRIP_HELPER), "--target", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r1.returncode == 0
        report1 = json.loads(r1.stdout)
        assert report1["removed_count"] == 0

        # Second run — must still report 0.
        r2 = subprocess.run(
            [sys.executable, str(STRIP_HELPER), "--target", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r2.returncode == 0
        report2 = json.loads(r2.stdout)
        assert report2["removed_count"] == 0, (
            "strip helper is not idempotent on clean file"
        )


def test_spec_issue944_2_strip_helper_skips_dogfood_file():
    """AC2 (dogfood guard): helper must not modify settings.autonomous-dev.json."""
    duplicated_settings = {
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
            ]
        }
    }
    with tempfile.TemporaryDirectory() as tmp:
        # Filename must be exactly settings.autonomous-dev.json to trigger dogfood guard.
        target = Path(tmp) / "settings.autonomous-dev.json"
        target.write_text(json.dumps(duplicated_settings), encoding="utf-8")
        original = target.read_text(encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(STRIP_HELPER), "--target", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["removed_count"] == 0
        assert report.get("skipped_reason") == "dogfooding"
        # File contents unchanged.
        assert target.read_text(encoding="utf-8") == original


# --------------------------------------------------------------------------
# AC4 presence check (already implemented in #950 in this batch).
# --------------------------------------------------------------------------


def test_spec_issue944_4_hook_path_validator_present():
    """AC4: lib/hook_path_validator.py MUST exist (from #950 in this batch)."""
    target = LIB_DIR / "hook_path_validator.py"
    assert target.exists(), (
        f"hook_path_validator.py expected at {target} (added by #950 in "
        f"this batch)"
    )
    # Sanity: file is non-empty.
    assert target.stat().st_size > 0
