#!/usr/bin/env python3
"""Integration tests for ``install.sh --uninstall`` — Issue #951.

End-to-end shell-level tests: invoke ``install.sh --uninstall`` as a
subprocess against a fake HOME directory containing simulated install
artifacts. Verify the uninstall flow:

    1. ``--dry-run`` leaves all files in place
    2. real run removes manifest-owned files
    3. real run creates a timestamped backup directory
    4. re-running on a clean state is idempotent (no errors, no
       new backup root)

The fake HOME contains:
    - ~/.claude/hooks/{unified_pre_tool.py, stop_quality_gate.py}
    - ~/.claude/lib/pipeline_state.py
    - ~/.claude/hooks/extensions/my_custom.py     (must survive)
    - ~/.claude/PROJECT.md                        (must survive)

These tests intentionally avoid creating a settings.json under HOME
to keep the test self-contained and to avoid triggering host-level
hooks; the settings-stripping path is covered in
``tests/unit/scripts/test_uninstall_strip_repo_hooks.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"


def _run_install(*args: str, fake_home: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    """Invoke install.sh with the given args and HOME=fake_home."""
    env = {**os.environ, "HOME": str(fake_home)}
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _make_fake_install(tmp_path: Path) -> Path:
    """Create a fake HOME with a simulated autonomous-dev install.

    Returns the fake_home path.
    """
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()

    claude = fake_home / ".claude"
    claude.mkdir()

    # Manifest-owned hook files (read from real manifest).
    hooks_dir = claude / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "unified_pre_tool.py").write_text("# fake hook\n")
    (hooks_dir / "stop_quality_gate.py").write_text("# fake hook\n")
    (hooks_dir / "auto_format.py").write_text("# fake hook\n")

    # User-owned extension (must survive).
    extensions = hooks_dir / "extensions"
    extensions.mkdir()
    (extensions / "my_custom.py").write_text("# user-added hook\n")

    # Manifest-owned lib files.
    lib_dir = claude / "lib"
    lib_dir.mkdir()
    (lib_dir / "pipeline_state.py").write_text("# fake lib\n")
    (lib_dir / "tool_validator.py").write_text("# fake lib\n")

    # User data that MUST be preserved.
    (claude / "PROJECT.md").write_text("# user project\n")
    (claude / "CLAUDE.md").write_text("# user CLAUDE.md\n")

    return fake_home


# ---------------------------------------------------------------------------
# Tests (4 required)
# ---------------------------------------------------------------------------


def test_dry_run_makes_no_mutations(tmp_path: Path) -> None:
    """--dry-run should leave all installed files in place."""
    fake_home = _make_fake_install(tmp_path)
    claude = fake_home / ".claude"

    # Snapshot file list before.
    before = sorted(p.relative_to(fake_home) for p in fake_home.rglob("*") if p.is_file())

    result = _run_install("--uninstall", "--dry-run", fake_home=fake_home)

    assert result.returncode == 0, (
        f"Expected exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    # Output should mention DRY RUN.
    combined = result.stdout + result.stderr
    assert "DRY RUN" in combined or "dry-run" in combined.lower(), (
        f"Output should mention DRY RUN; got:\n{combined}"
    )

    # Every file present before is still present.
    after = sorted(p.relative_to(fake_home) for p in fake_home.rglob("*") if p.is_file())
    assert before == after, (
        f"Dry-run mutated the file tree.\nBefore: {before}\nAfter:  {after}"
    )

    # No backup root was created.
    backups = claude / "backups"
    assert not backups.exists() or not any(backups.iterdir()), (
        f"Dry-run created backup directory: {list(backups.iterdir())}"
    )

    # Specifically: the manifest-owned hook is still there.
    assert (claude / "hooks" / "unified_pre_tool.py").exists()
    # User extension is still there.
    assert (claude / "hooks" / "extensions" / "my_custom.py").exists()


def test_real_run_removes_manifest_files(tmp_path: Path) -> None:
    """Real run should delete manifest-owned files but keep user files."""
    fake_home = _make_fake_install(tmp_path)
    claude = fake_home / ".claude"

    result = _run_install("--uninstall", fake_home=fake_home)

    assert result.returncode == 0, (
        f"Expected exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    # Manifest-owned hooks: GONE (these are listed in the real manifest).
    assert not (claude / "hooks" / "unified_pre_tool.py").exists(), (
        "unified_pre_tool.py should be removed (manifest-owned)"
    )
    assert not (claude / "hooks" / "stop_quality_gate.py").exists()

    # User extension: PRESERVED.
    assert (claude / "hooks" / "extensions" / "my_custom.py").exists(), (
        "User-added extension was incorrectly removed"
    )

    # Manifest-owned lib: GONE.
    assert not (claude / "lib" / "pipeline_state.py").exists()

    # User data PROJECT.md / CLAUDE.md: PRESERVED.
    assert (claude / "PROJECT.md").exists()
    assert (claude / "CLAUDE.md").exists()


def test_real_run_creates_backup(tmp_path: Path) -> None:
    """Real run should create ~/.claude/backups/uninstall-*/ with copies."""
    fake_home = _make_fake_install(tmp_path)
    claude = fake_home / ".claude"

    result = _run_install("--uninstall", fake_home=fake_home)

    assert result.returncode == 0, (
        f"Expected exit 0; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    backups_dir = claude / "backups"
    assert backups_dir.exists(), (
        f"Backups directory not created at {backups_dir}\n"
        f"stdout={result.stdout}"
    )

    # Exactly one timestamped backup dir.
    backup_roots = [p for p in backups_dir.iterdir() if p.is_dir() and p.name.startswith("uninstall-")]
    assert len(backup_roots) == 1, (
        f"Expected exactly 1 backup root, got {len(backup_roots)}: {backup_roots}"
    )
    backup_root = backup_roots[0]

    # Backup contains hooks subdir with at least one of the removed files.
    hooks_backup = backup_root / "hooks"
    assert hooks_backup.exists(), f"hooks/ subdir missing in backup: {backup_root}"
    backed_up_hooks = list(hooks_backup.iterdir())
    assert any("unified_pre_tool" in p.name for p in backed_up_hooks), (
        f"unified_pre_tool.py not in backup; got {[p.name for p in backed_up_hooks]}"
    )

    # Backup contents match pre-deletion content.
    pretool_backup = next(
        (p for p in backed_up_hooks if "unified_pre_tool" in p.name), None
    )
    assert pretool_backup is not None
    assert pretool_backup.read_text() == "# fake hook\n"


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    """Re-running on a clean state should be a no-op (exit 0, no error)."""
    fake_home = _make_fake_install(tmp_path)
    claude = fake_home / ".claude"

    # First run: real.
    result1 = _run_install("--uninstall", fake_home=fake_home)
    assert result1.returncode == 0, f"First run failed: {result1.stderr}"

    # Snapshot what survived after first run.
    survivors_1 = sorted(
        p.relative_to(fake_home)
        for p in fake_home.rglob("*")
        if p.is_file() and "backups/" not in str(p)
    )

    # Second run: should be idempotent.
    result2 = _run_install("--uninstall", fake_home=fake_home)
    assert result2.returncode == 0, (
        f"Second run failed with exit {result2.returncode}\n"
        f"stdout={result2.stdout}\nstderr={result2.stderr}"
    )

    # Survivors should be the same.
    survivors_2 = sorted(
        p.relative_to(fake_home)
        for p in fake_home.rglob("*")
        if p.is_file() and "backups/" not in str(p)
    )
    assert survivors_1 == survivors_2, (
        f"Second run mutated the file tree.\n"
        f"After first run:  {survivors_1}\n"
        f"After second run: {survivors_2}"
    )

    # PROJECT.md / CLAUDE.md still there.
    assert (claude / "PROJECT.md").exists()
    assert (claude / "CLAUDE.md").exists()
    # User extension still there.
    assert (claude / "hooks" / "extensions" / "my_custom.py").exists()
