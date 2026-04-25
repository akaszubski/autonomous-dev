#!/usr/bin/env python3
"""Unit tests for ``scripts/reset_global_hooks.py`` — Issue #949.

Covers:
    - Strip the hooks block while preserving all other top-level keys
    - Backup creation with the ``.preglobal-hooks-strip`` suffix
    - Idempotency when the hooks key is absent (no backup, no rewrite)
    - Backup overwrite behavior when a backup already exists
    - Malformed JSON: refuse to modify, no backup
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

import reset_global_hooks as rgh  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_settings_with_hooks(target: Path) -> bytes:
    """Write a settings.json with a hooks block + 4 other top-level keys.

    Returns the raw bytes written, for byte-level equality assertions.
    """
    content = {
        "permissions": {
            "allow": ["Read", "Write", "Edit"],
            "deny": ["Read(~/.ssh/**)"],
        },
        "mcpServers": {
            "github": {"command": "docker", "args": ["run", "ghcr.io/x"]}
        },
        "env": {"FOO": "bar"},
        "model": "claude-sonnet-4-5",
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 /broken/path.py",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "python3 /also/broken.py"}
                    ],
                }
            ],
        },
    }
    payload = json.dumps(content, indent=2).encode("utf-8")
    target.write_bytes(payload)
    return payload


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_reset_strips_hooks_block(tmp_path: Path) -> None:
    """Removing hooks preserves every other top-level key bit-for-bit."""
    target = tmp_path / "settings.json"
    pre_bytes = _build_settings_with_hooks(target)
    pre_image = json.loads(pre_bytes)

    result = rgh.reset_file(target)

    # Return value contract.
    assert result["success"] is True
    assert result["stripped"] is True
    assert result["error"] is None
    assert sorted(result["hook_keys_removed"]) == ["PreToolUse", "Stop"]
    assert result["target"] == str(target)

    # On-disk: hooks key gone, other 4 keys preserved bit-for-bit.
    post_image = json.loads(target.read_text(encoding="utf-8"))
    assert "hooks" not in post_image
    for key in ("permissions", "mcpServers", "env", "model"):
        assert key in post_image, f"Missing key after strip: {key}"
        assert post_image[key] == pre_image[key], (
            f"Value drift on key {key}: pre={pre_image[key]!r} "
            f"post={post_image[key]!r}"
        )
    # And no other keys appeared.
    assert set(post_image.keys()) == {"permissions", "mcpServers", "env", "model"}


def test_reset_creates_backup_with_correct_suffix(tmp_path: Path) -> None:
    """Backup file is named <target>.preglobal-hooks-strip and matches the
    pre-call bytes exactly."""
    target = tmp_path / "settings.json"
    pre_bytes = _build_settings_with_hooks(target)

    result = rgh.reset_file(target)
    assert result["success"] is True
    assert result["stripped"] is True

    backup = tmp_path / "settings.json.preglobal-hooks-strip"
    assert backup.exists(), f"Backup not created at {backup}"
    assert backup.read_bytes() == pre_bytes, (
        "Backup contents must equal the pre-call settings.json bytes"
    )
    # And the JSON output reports the same path.
    assert result["backup_path"] == str(backup)


def test_reset_idempotent_when_no_hooks_key(tmp_path: Path) -> None:
    """No hooks key -> success=True, stripped=False, no backup file."""
    target = tmp_path / "settings.json"
    content = {
        "permissions": {"allow": ["Read"]},
        "model": "claude-sonnet-4-5",
    }
    pre_bytes = json.dumps(content, indent=2).encode("utf-8")
    target.write_bytes(pre_bytes)

    result = rgh.reset_file(target)

    assert result["success"] is True
    assert result["stripped"] is False
    assert result["hook_keys_removed"] == []
    assert result["backup_path"] is None
    assert "no hooks block" in result["message"].lower()

    # File unchanged on disk.
    assert target.read_bytes() == pre_bytes
    # No backup file created.
    backup = tmp_path / "settings.json.preglobal-hooks-strip"
    assert not backup.exists(), "Idempotent path must not create a backup"


def test_reset_overwrites_existing_backup(tmp_path: Path) -> None:
    """A pre-existing backup file is overwritten with the current
    pre-strip state — no timestamp suffix logic, by design."""
    target = tmp_path / "settings.json"
    backup = tmp_path / "settings.json.preglobal-hooks-strip"

    # Pre-create a backup with sentinel content from a hypothetical earlier
    # run. The recovery contract: re-running the strip OVERWRITES this.
    sentinel = b'{"sentinel": "OLD_BACKUP_FROM_PREVIOUS_RUN"}'
    backup.write_bytes(sentinel)
    assert backup.read_bytes() == sentinel

    # Now write the real settings file and run the reset.
    pre_bytes = _build_settings_with_hooks(target)

    result = rgh.reset_file(target)
    assert result["success"] is True
    assert result["stripped"] is True

    # Backup now contains the pre-call settings.json bytes — sentinel gone.
    assert backup.exists()
    assert backup.read_bytes() == pre_bytes, (
        "Backup must reflect the current pre-strip state, overwriting any "
        "previous backup contents"
    )
    assert backup.read_bytes() != sentinel


def test_reset_handles_malformed_json_gracefully(tmp_path: Path) -> None:
    """Unparseable settings.json -> success=False, file untouched, no backup.

    The recovery tool refuses to risk overwriting a file it cannot parse.
    The user must fix the JSON syntax manually before retrying.
    """
    target = tmp_path / "settings.json"
    bogus = b"{not valid json at all"
    target.write_bytes(bogus)

    result = rgh.reset_file(target)

    assert result["success"] is False
    assert result["stripped"] is False
    # Error message mentions JSON.
    err = (result.get("error") or "").lower()
    assert "json" in err or "malformed" in err, (
        f"Error message should mention JSON: {result['error']!r}"
    )

    # File unchanged on disk.
    assert target.read_bytes() == bogus
    # No backup created.
    backup = tmp_path / "settings.json.preglobal-hooks-strip"
    assert not backup.exists(), "Malformed-JSON path must not create a backup"


# ---------------------------------------------------------------------------
# Bonus coverage — edge cases worth locking in (do not count against the 5
# required, but cheap insurance).
# ---------------------------------------------------------------------------


def test_reset_missing_target_is_success(tmp_path: Path) -> None:
    """Target file absent -> success=True, stripped=False, no backup."""
    target = tmp_path / "does_not_exist.json"
    assert not target.exists()

    result = rgh.reset_file(target)

    assert result["success"] is True
    assert result["stripped"] is False
    assert result["backup_path"] is None
    assert result["hook_keys_removed"] == []
    backup = tmp_path / "does_not_exist.json.preglobal-hooks-strip"
    assert not backup.exists()


def test_reset_handles_non_dict_hooks_value(tmp_path: Path) -> None:
    """hooks value is None / list / string -> still remove key, empty list."""
    for bogus_value in (None, [], "not-a-dict", 42):
        target = tmp_path / "s.json"
        content = {
            "permissions": {"allow": ["Read"]},
            "hooks": bogus_value,
        }
        target.write_text(json.dumps(content, indent=2))

        result = rgh.reset_file(target)

        assert result["success"] is True
        assert result["stripped"] is True
        assert result["hook_keys_removed"] == []
        post = json.loads(target.read_text())
        assert "hooks" not in post
        assert post.get("permissions") == {"allow": ["Read"]}

        # Cleanup for the next iteration.
        backup = tmp_path / "s.json.preglobal-hooks-strip"
        if backup.exists():
            backup.unlink()
        target.unlink()
