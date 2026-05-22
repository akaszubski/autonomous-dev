#!/usr/bin/env python3
"""Unit tests for ``scripts/uninstall_strip_repo_hooks.py`` — Issue #951.

Covers:
    - Strip autonomous-dev entries while preserving user-added entries
    - Backup creation under the requested backup_root before any mutation
    - Dry-run mode performs no file writes and creates no backup
    - Idempotency when the hooks key is absent (no backup, no rewrite)
    - Malformed JSON: refuse to modify, no backup
    - User-owned ~/.claude/hooks/extensions/ entries are preserved
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


# Make the script importable as a module — match other tests in this dir.
_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "autonomous-dev"
    / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import uninstall_strip_repo_hooks as usrh  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _autonomous_settings() -> dict:
    """settings.json with two autonomous-dev hooks + permissions/env."""
    return {
        "permissions": {
            "allow": ["Read", "Write", "Edit"],
        },
        "env": {"USER_VAR": "keep_me"},
        "model": "claude-sonnet-4-5",
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/stop_quality_gate.py",
                        }
                    ],
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Tests (6 required)
# ---------------------------------------------------------------------------


def test_strip_removes_autonomous_dev_entries(tmp_path: Path) -> None:
    """Autonomous-dev hook entries are removed; other top-level keys intact."""
    target = tmp_path / "settings.json"
    backup_root = tmp_path / "backup"
    pre = _autonomous_settings()
    target.write_text(json.dumps(pre, indent=2))

    result = usrh.strip_repo_hooks(target, backup_root, dry_run=False)

    assert result["success"] is True
    assert result["stripped"] is True
    assert result["error"] is None
    assert set(result["hook_keys_removed"]) == {"PreToolUse", "Stop"}

    post = json.loads(target.read_text())
    assert "hooks" not in post
    assert post["permissions"] == pre["permissions"]
    assert post["env"] == pre["env"]
    assert post["model"] == pre["model"]


def test_strip_creates_backup_before_mutate(tmp_path: Path) -> None:
    """A backup is created under backup_root with the pre-call content."""
    target = tmp_path / "settings.json"
    backup_root = tmp_path / "uninstall-20260101-000000"
    pre_text = json.dumps(_autonomous_settings(), indent=2)
    target.write_text(pre_text)

    result = usrh.strip_repo_hooks(target, backup_root, dry_run=False)

    assert result["success"] is True
    assert result["stripped"] is True
    backup_path = Path(result["backup_path"])
    assert backup_path.exists(), f"Backup not created at {backup_path}"
    assert backup_path.read_text() == pre_text, (
        "Backup must equal pre-call content byte-for-byte"
    )
    # Backup is under the requested backup_root.
    assert backup_root in backup_path.parents or backup_path.parent == backup_root


def test_dry_run_makes_no_writes(tmp_path: Path) -> None:
    """Dry-run leaves target untouched and creates no backup."""
    target = tmp_path / "settings.json"
    backup_root = tmp_path / "backup"
    pre_text = json.dumps(_autonomous_settings(), indent=2)
    target.write_text(pre_text)

    result = usrh.strip_repo_hooks(target, backup_root, dry_run=True)

    assert result["success"] is True
    assert result["stripped"] is False
    assert result["would_strip"] is True
    assert result["backup_path"] is None
    # Target unchanged.
    assert target.read_text() == pre_text
    # Backup dir not created (because no file written there).
    assert not backup_root.exists() or not any(backup_root.iterdir())


def test_user_extensions_preserved(tmp_path: Path) -> None:
    """Hooks under ~/.claude/hooks/extensions/ are NOT stripped."""
    target = tmp_path / "settings.json"
    backup_root = tmp_path / "backup"
    content = {
        "permissions": {"allow": ["Read"]},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write",
                    "hooks": [
                        # User-added extension - must survive.
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/extensions/my_custom.py",
                        }
                    ],
                },
                {
                    "matcher": "Edit",
                    "hooks": [
                        # autonomous-dev hook - must be removed.
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                        }
                    ],
                },
            ]
        },
    }
    target.write_text(json.dumps(content, indent=2))

    result = usrh.strip_repo_hooks(target, backup_root, dry_run=False)

    assert result["success"] is True
    assert result["stripped"] is True

    post = json.loads(target.read_text())
    # PreToolUse must survive (user entry remains).
    assert "PreToolUse" in post["hooks"]
    surviving = post["hooks"]["PreToolUse"]
    assert len(surviving) == 1
    assert "extensions/my_custom.py" in surviving[0]["hooks"][0]["command"]
    # autonomous-dev entry gone.
    for entry in surviving:
        for sub in entry["hooks"]:
            assert "unified_pre_tool.py" not in sub["command"]


def test_idempotent_when_no_hooks_key(tmp_path: Path) -> None:
    """No hooks key -> success=True, stripped=False, no backup."""
    target = tmp_path / "settings.json"
    backup_root = tmp_path / "backup"
    content = {"permissions": {"allow": ["Read"]}, "model": "claude-sonnet-4-5"}
    pre_text = json.dumps(content, indent=2)
    target.write_text(pre_text)

    result = usrh.strip_repo_hooks(target, backup_root, dry_run=False)

    assert result["success"] is True
    assert result["stripped"] is False
    assert result["backup_path"] is None
    assert result["hook_keys_removed"] == []
    # File unchanged.
    assert target.read_text() == pre_text


def test_malformed_json_refuses_to_modify(tmp_path: Path) -> None:
    """Unparseable settings.json -> success=False, file untouched, no backup."""
    target = tmp_path / "settings.json"
    backup_root = tmp_path / "backup"
    bogus = b"{not valid json at all"
    target.write_bytes(bogus)

    result = usrh.strip_repo_hooks(target, backup_root, dry_run=False)

    assert result["success"] is False
    assert result["stripped"] is False
    err = (result.get("error") or "").lower()
    assert "json" in err or "malformed" in err

    # File unchanged on disk.
    assert target.read_bytes() == bogus
    # No backup created.
    assert not backup_root.exists() or not any(backup_root.iterdir())
