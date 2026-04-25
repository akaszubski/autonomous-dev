#!/usr/bin/env python3
"""Integration tests for ``install.sh --reset-hooks`` — Issue #949.

End-to-end: invoke ``install.sh --reset-hooks`` as a subprocess against a
fake HOME directory containing a settings.json with hook entries. Verify
the recovery flow:
    - Help text exposes the flag
    - --reset-hooks short-circuits the normal install flow
    - The hooks block is stripped while permissions/env/etc. are preserved
    - The backup file exists with the expected suffix and pre-call content
    - Idempotent when no hooks key is present
    - Idempotent when settings.json is absent
    - Real "deliberately break a hook -> recover" smoke flow (acceptance
      criterion #2 from Issue #949)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"


def _run_install(*args: str, fake_home: Path) -> subprocess.CompletedProcess[str]:
    """Invoke install.sh with the given args and HOME=fake_home."""
    env = {**os.environ, "HOME": str(fake_home)}
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _make_fake_home(tmp_path: Path) -> Path:
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    (fake_home / ".claude").mkdir()
    return fake_home


def _settings_with_hooks() -> dict:
    """Return a settings.json dict with hooks + permissions + env."""
    return {
        "permissions": {
            "allow": ["Read", "Write", "Edit"],
            "deny": ["Read(~/.ssh/**)"],
        },
        "env": {"FOO": "bar", "BAZ": "qux"},
        "model": "claude-sonnet-4-5",
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/some_hook.py",
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
                            "command": "python3 ~/.claude/hooks/stop_hook.py",
                        }
                    ],
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_reset_hooks_flag_parsed_in_help(tmp_path: Path) -> None:
    """--reset-hooks must appear in the --help output."""
    fake_home = _make_fake_home(tmp_path)
    result = _run_install("--help", fake_home=fake_home)

    assert result.returncode == 0, (
        f"--help should exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "--reset-hooks" in result.stdout, (
        f"--reset-hooks not documented in help:\n{result.stdout}"
    )


def test_reset_hooks_short_circuits_normal_install(tmp_path: Path) -> None:
    """--reset-hooks must NOT trigger download/staging.

    With an empty fake HOME and no settings.json, --reset-hooks should
    exit 0 cleanly without creating a .autonomous-dev-staging directory or
    running the manifest download.
    """
    fake_home = _make_fake_home(tmp_path)
    # Empty .claude — no settings.json.

    result = _run_install("--reset-hooks", fake_home=fake_home)

    assert result.returncode == 0, (
        f"Expected exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    # Normal install creates ~/.autonomous-dev-staging — verify it's NOT
    # there. (download_manifest, download_files, etc. should be skipped.)
    staging_dir = fake_home / ".autonomous-dev-staging"
    assert not staging_dir.exists(), (
        f"--reset-hooks should not trigger staging download; "
        f"staging dir exists: {staging_dir}"
    )

    # Output should mention something about no hooks / not present, NOT
    # "Downloading manifest" or similar normal-install text.
    combined = result.stdout + result.stderr
    assert "Downloading manifest" not in combined, (
        f"--reset-hooks should not run download_manifest; got:\n{combined}"
    )


def test_reset_hooks_strips_real_settings_file(tmp_path: Path) -> None:
    """settings.json with hooks + permissions + env: hooks gone, others intact."""
    fake_home = _make_fake_home(tmp_path)
    settings_path = fake_home / ".claude" / "settings.json"
    pre = _settings_with_hooks()
    settings_path.write_text(json.dumps(pre, indent=2))

    result = _run_install("--reset-hooks", fake_home=fake_home)

    assert result.returncode == 0, (
        f"Expected exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    post = json.loads(settings_path.read_text())
    assert "hooks" not in post, f"hooks block should be removed; got {post}"
    # All other top-level keys preserved.
    assert post["permissions"] == pre["permissions"]
    assert post["env"] == pre["env"]
    assert post["model"] == pre["model"]


def test_reset_hooks_creates_named_backup(tmp_path: Path) -> None:
    """After invocation, settings.json.preglobal-hooks-strip exists with pre-call content."""
    fake_home = _make_fake_home(tmp_path)
    settings_path = fake_home / ".claude" / "settings.json"
    pre = _settings_with_hooks()
    pre_text = json.dumps(pre, indent=2)
    settings_path.write_text(pre_text)

    result = _run_install("--reset-hooks", fake_home=fake_home)
    assert result.returncode == 0, (
        f"Expected exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    backup = fake_home / ".claude" / "settings.json.preglobal-hooks-strip"
    assert backup.exists(), (
        f"Backup not created at {backup}\nstdout={result.stdout}"
    )
    assert backup.read_text() == pre_text, (
        "Backup contents must equal the pre-call settings.json"
    )


def test_reset_hooks_no_op_when_no_hooks_key(tmp_path: Path) -> None:
    """settings.json without hooks -> exit 0, file unchanged, no backup."""
    fake_home = _make_fake_home(tmp_path)
    settings_path = fake_home / ".claude" / "settings.json"
    content = {"permissions": {"allow": ["Read"]}, "model": "claude-sonnet-4-5"}
    pre_text = json.dumps(content, indent=2)
    settings_path.write_text(pre_text)

    result = _run_install("--reset-hooks", fake_home=fake_home)

    assert result.returncode == 0, (
        f"Expected exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    # Byte-equal pre-run.
    assert settings_path.read_text() == pre_text
    # No backup.
    backup = fake_home / ".claude" / "settings.json.preglobal-hooks-strip"
    assert not backup.exists(), (
        "No-op path must not create a backup file"
    )


def test_reset_hooks_no_op_when_settings_absent(tmp_path: Path) -> None:
    """No ~/.claude/settings.json -> exit 0, helpful info message, no error."""
    fake_home = _make_fake_home(tmp_path)
    settings_path = fake_home / ".claude" / "settings.json"
    assert not settings_path.exists()

    result = _run_install("--reset-hooks", fake_home=fake_home)

    assert result.returncode == 0, (
        f"Expected exit 0 even when settings.json is absent; "
        f"got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    # Helpful message: should mention "not present" or similar.
    combined = result.stdout + result.stderr
    assert (
        "not present" in combined
        or "no hooks" in combined.lower()
        or "settings.json" in combined.lower()
    ), f"Expected helpful info message; got:\n{combined}"
    # Still no settings.json (we never created one).
    assert not settings_path.exists()


def test_break_hook_then_recover_flow(tmp_path: Path) -> None:
    """Acceptance criterion #2: deliberately break a hook -> recover.

    Write a settings.json with hooks pointing to a nonexistent script,
    run install.sh --reset-hooks, verify post-run state has no hooks key,
    is valid JSON, all other top-level keys intact.
    """
    fake_home = _make_fake_home(tmp_path)
    settings_path = fake_home / ".claude" / "settings.json"
    broken_settings = {
        "permissions": {"allow": ["Read", "Write", "Edit"]},
        "env": {"USER_VAR": "preserved"},
        "model": "claude-sonnet-4-5",
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            # Deliberately broken: nonexistent script.
                            "command": "/nonexistent/script.py",
                        }
                    ],
                }
            ],
        },
    }
    settings_path.write_text(json.dumps(broken_settings, indent=2))

    result = _run_install("--reset-hooks", fake_home=fake_home)
    assert result.returncode == 0, (
        f"Recovery should exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    # Post-run settings.json must:
    # 1. Be valid JSON
    post = json.loads(settings_path.read_text())
    # 2. Have no hooks key
    assert "hooks" not in post, (
        f"hooks block should be removed; got {post}"
    )
    # 3. All other top-level keys intact
    assert post["permissions"] == {"allow": ["Read", "Write", "Edit"]}
    assert post["env"] == {"USER_VAR": "preserved"}
    assert post["model"] == "claude-sonnet-4-5"
    # 4. Backup exists for restore-if-needed
    backup = fake_home / ".claude" / "settings.json.preglobal-hooks-strip"
    assert backup.exists()
    backup_data = json.loads(backup.read_text())
    assert "hooks" in backup_data, "Backup should still contain the broken hooks"
    assert backup_data["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == (
        "/nonexistent/script.py"
    )
