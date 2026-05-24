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


# ---------------------------------------------------------------------------
# Issue #965 — defensive hardening tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes only")
def test_backup_file_has_mode_0600(tmp_path: Path) -> None:
    """AC-965-1: Backup is always written with mode 0o600, even when the
    source file has broader permissions (e.g. 0o644)."""
    target = tmp_path / "settings.json"
    _build_settings_with_hooks(target)
    # Give the source a world-readable mode.
    target.chmod(0o644)

    result = rgh.reset_file(target)
    assert result["success"] is True
    assert result["stripped"] is True

    backup = tmp_path / "settings.json.preglobal-hooks-strip"
    assert backup.exists(), "Backup must be created"
    backup_mode = backup.stat().st_mode & 0o777
    assert backup_mode == 0o600, (
        f"Backup file mode should be 0o600, got {oct(backup_mode)}"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes only")
def test_rewritten_settings_has_mode_0600_even_when_original_is_world_readable(
    tmp_path: Path,
) -> None:
    """AC-965-2: Rewritten settings.json has mode 0o600 when the original
    had broader permissions (permission floor enforcement)."""
    target = tmp_path / "settings.json"
    _build_settings_with_hooks(target)
    # World-readable original.
    target.chmod(0o644)

    result = rgh.reset_file(target)
    assert result["success"] is True
    assert result["stripped"] is True

    resulting_mode = target.stat().st_mode & 0o777
    assert resulting_mode == 0o600, (
        f"Rewritten settings.json mode should be 0o600, got {oct(resulting_mode)}"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks only")
def test_settings_symlink_is_preserved_and_real_target_rewritten(
    tmp_path: Path,
) -> None:
    """AC-965-3: When settings.json is a symlink (dotfiles-manager pattern),
    the symlink itself is preserved and the real target file is rewritten."""
    real_file = tmp_path / "real_settings.json"
    _build_settings_with_hooks(real_file)

    symlink = tmp_path / "settings.json"
    symlink.symlink_to(real_file)
    assert symlink.is_symlink(), "Pre-condition: settings.json must be a symlink"

    result = rgh.reset_file(symlink)
    assert result["success"] is True
    assert result["stripped"] is True

    # Symlink must still exist as a symlink.
    assert symlink.is_symlink(), (
        "settings.json should remain a symlink after reset"
    )

    # The real target file must contain the rewritten (hooks-stripped) JSON.
    post = json.loads(real_file.read_text(encoding="utf-8"))
    assert "hooks" not in post, (
        "Real target file must have hooks stripped"
    )
    assert "permissions" in post, (
        "Real target file must preserve other keys"
    )

    # The message must mention symlink / dotfiles manager.
    msg = result.get("message", "").lower()
    assert "symlink" in msg or "dotfiles" in msg, (
        f"message should mention symlink handling, got: {result['message']!r}"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks only")
def test_broken_symlink_is_replaced_with_real_file(tmp_path: Path) -> None:
    """AC-965-4: A broken symlink (dangling pointer) is replaced with a real
    file containing the rewritten settings.json."""
    symlink = tmp_path / "settings.json"
    # Point the symlink at a nonexistent target.
    symlink.symlink_to(tmp_path / "nonexistent_target.json")
    assert symlink.is_symlink(), "Pre-condition: must be a symlink"
    assert not symlink.exists(), "Pre-condition: symlink must be dangling"

    # For reset_file to have content to process, we need a settings file with
    # content — but a broken symlink means target.exists() returns False,
    # so reset_file will take the early-exit path. Instead create a real file
    # at the symlink path after deleting the symlink, to simulate a fresh
    # scenario where we start with a broken symlink that points to a place we
    # can still write.
    # Actually, the correct test is: create a settings.json that IS a symlink
    # to a nonexistent location, but also has readable content so we can
    # proceed past the "file not present" check. That's only possible if the
    # symlink resolves — a broken symlink by definition doesn't.
    # The behavior we're testing: when _atomic_write_json is given a broken
    # symlink path, it replaces it with a real file.
    # Test via _atomic_write_json directly.
    symlink.unlink()
    symlink.symlink_to(tmp_path / "still_missing.json")

    content = {"permissions": {"allow": ["Read"]}, "model": "test"}
    real_target, was_symlink, was_broken_symlink = rgh._atomic_write_json(
        symlink, content
    )

    assert was_symlink is True, "Should have detected the symlink"
    assert was_broken_symlink is True, "Should have detected broken symlink"
    # The symlink entry should now be a real file (broken symlink was replaced).
    assert not symlink.is_symlink(), (
        "settings.json should be a regular file after broken-symlink replacement"
    )
    assert symlink.is_file(), "settings.json should be a regular file"
    post = json.loads(symlink.read_text(encoding="utf-8"))
    assert post["model"] == "test", "File should contain written content"

    # Now test via reset_file with a scenario where the file exists first,
    # then we make the symlink broken mid-test — not practical.
    # Instead, verify the message when reset_file encounters a broken symlink
    # by running a full end-to-end scenario using the public API:
    # Create a settings.json with content that IS readable (a real file),
    # then at call time convert to a broken symlink... which changes exists()
    # result. This is inherently a unit-level test of _atomic_write_json, as
    # proven above.


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks only")
def test_backup_of_symlinked_source_writes_dereferenced_bytes_and_warns(
    tmp_path: Path,
) -> None:
    """AC-965-5: When settings.json is a symlink, the backup contains the
    dereferenced bytes (not the symlink itself) and message mentions it."""
    real_file = tmp_path / "real_settings.json"
    _build_settings_with_hooks(real_file)
    original_bytes = real_file.read_bytes()

    symlink = tmp_path / "settings.json"
    symlink.symlink_to(real_file)

    result = rgh.reset_file(symlink)
    assert result["success"] is True
    assert result["stripped"] is True

    backup = tmp_path / "settings.json.preglobal-hooks-strip"
    assert backup.exists(), "Backup must be created"
    # Backup must be a regular file, not a symlink.
    assert not backup.is_symlink(), "Backup should be a regular file, not a symlink"
    # Backup bytes must equal the original real file bytes (dereferenced).
    assert backup.read_bytes() == original_bytes, (
        "Backup should contain dereferenced contents of the real target file"
    )

    # Message must mention the backup-source-was-symlink situation.
    msg = result.get("message", "").lower()
    assert "symlink" in msg, (
        f"message should mention symlink handling for backup, got: {result['message']!r}"
    )
