"""Integration tests for the install.sh strip-migration step (Issue #944).

End-to-end check: invoke ``strip_duplicate_hooks.py`` as a subprocess
against a fixture settings file containing 4 canonical duplicates. Verify
the JSON return contract, atomic write, and that ``permissions`` is left
untouched.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STRIP_CLI = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "scripts" / "strip_duplicate_hooks.py"
)


def _build_fixture_with_4_canonical(tmp_path: Path) -> Path:
    """Return a fixture file path containing 4 canonical hook duplicates."""
    target = tmp_path / "fixture_944.json"
    content = {
        "permissions": {
            "allow": ["Read", "Write", "Edit"],
            "deny": ["Read(~/.ssh/**)"],
        },
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
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/plan_gate.py",
                        }
                    ],
                },
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/custom_user_hook.py",
                        }
                    ],
                },
            ],
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/stop_quality_gate.py",
                        }
                    ],
                },
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "CONVERSATION_ARCHIVE=true python3 ~/.claude/hooks/conversation_archiver.py",
                        }
                    ],
                },
            ],
        },
    }
    target.write_text(json.dumps(content, indent=2))
    return target


def test_install_strip_migration_end_to_end(tmp_path):
    """Subprocess invocation strips 4 duplicates and preserves customization.

    Mirrors what install.sh does: call the CLI on a settings file, parse the
    JSON, observe the file was rewritten with the 4 commands removed but the
    user's custom hook + permissions untouched.
    """
    target = _build_fixture_with_4_canonical(tmp_path)
    pre_image = json.loads(target.read_text())

    result = subprocess.run(
        [sys.executable, str(STRIP_CLI), "--target", str(target)],
        capture_output=True,
        text=True,
    )

    # Always exit 0 (lenient migration contract).
    assert result.returncode == 0, (
        f"CLI exit {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    payload = json.loads(result.stdout)
    assert payload["success"] is True, payload
    assert payload["error"] is None
    assert payload["skipped_reason"] is None
    assert payload["removed_count"] == 4, payload
    assert len(payload["events"]) == 4

    # Each event entry has both keys
    for event in payload["events"]:
        assert "event" in event
        assert "command" in event

    # Re-read the file: the 4 canonical commands MUST be gone, but the
    # custom hook and permissions block MUST be preserved.
    post_image = json.loads(target.read_text())
    assert post_image["permissions"] == pre_image["permissions"]

    canonical_cmds = {
        "python3 ~/.claude/hooks/unified_prompt_validator.py",
        "python3 ~/.claude/hooks/plan_gate.py",
        "python3 ~/.claude/hooks/stop_quality_gate.py",
        "CONVERSATION_ARCHIVE=true python3 ~/.claude/hooks/conversation_archiver.py",
    }

    def _all_commands(settings: dict) -> set:
        out: set = set()
        for matchers in settings.get("hooks", {}).values():
            if not isinstance(matchers, list):
                continue
            for matcher in matchers:
                for hook in matcher.get("hooks", []):
                    out.add(hook.get("command", ""))
        return out

    post_cmds = _all_commands(post_image)
    assert canonical_cmds.isdisjoint(post_cmds), (
        f"Canonical commands NOT removed: {canonical_cmds & post_cmds}"
    )
    assert "python3 ~/.claude/hooks/custom_user_hook.py" in post_cmds, (
        f"Custom user hook was incorrectly removed; remaining: {post_cmds}"
    )

    # PreToolUse should now contain ONLY the custom matcher (one of two).
    assert len(post_image["hooks"]["PreToolUse"]) == 1
    assert post_image["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == (
        "python3 ~/.claude/hooks/custom_user_hook.py"
    )

    # Stop event had only canonical entries — should be entirely removed.
    assert "Stop" not in post_image.get("hooks", {})
    # UserPromptSubmit had only canonical entry — should be removed.
    assert "UserPromptSubmit" not in post_image.get("hooks", {})


def test_install_strip_migration_idempotent(tmp_path):
    """A second invocation reports removed_count=0 (idempotent contract)."""
    target = _build_fixture_with_4_canonical(tmp_path)

    # First run.
    subprocess.run(
        [sys.executable, str(STRIP_CLI), "--target", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    # Second run.
    result = subprocess.run(
        [sys.executable, str(STRIP_CLI), "--target", str(target)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["removed_count"] == 0
    assert payload["events"] == []
