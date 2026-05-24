#!/usr/bin/env python3
"""
Integration tests for worktree plugin artifact bootstrapping (Issue #1115).

After a fresh ``git worktree add`` via ``create_worktree()``, pytest collection
must succeed without any manual fixup.  Two artifacts are required:

1. ``<worktree>/plugins/__init__.py``  — makes ``plugins`` a package.
2. ``<worktree>/plugins/autonomous_dev`` — symlink pointing at ``autonomous-dev``.

These files are build outputs (not tracked by git), so a freshly-checked-out
worktree is missing them.  The fix is a best-effort bootstrap called from
``create_worktree()`` after the git checkout step.

Test Strategy:
- Use real git commands with ``tmp_path`` fixture (no mocks for git operations).
- The bootstrap helper is exercised indirectly through ``create_worktree()``.
- AC5 (OSError graceful degradation) is tested with monkeypatching.

Date: 2026-05-24
Issue: GitHub #1115
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest

# ---------------------------------------------------------------------------
# Path setup: make the lib importable from any CWD
# ---------------------------------------------------------------------------
_LIB_PATH = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

try:
    from worktree_manager import create_worktree, _bootstrap_worktree_plugin_artifacts
except ImportError as exc:
    pytest.skip(f"worktree_manager not importable: {exc}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Shared git-repo fixture (mirrors style of test_worktree_batch_isolation.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a minimal git repository with one commit and a plugins/ dir."""
    repo = tmp_path / "test-repo"
    repo.mkdir()

    for cmd in [
        ["git", "init"],
        ["git", "config", "user.name", "Test User"],
        ["git", "config", "user.email", "test@example.com"],
    ]:
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)

    # Create plugins/autonomous-dev sub-tree so bootstrap has something to work with.
    # Git only tracks files, not empty directories — we must commit at least one
    # file inside plugins/autonomous-dev/ so the directory tree materialises in
    # the fresh worktree checkout.
    plugins_dir = repo / "plugins"
    plugins_dir.mkdir()
    autonomous_dev_dir = plugins_dir / "autonomous-dev"
    autonomous_dev_dir.mkdir()
    lib_dir = autonomous_dev_dir / "lib"
    lib_dir.mkdir()
    (lib_dir / "__init__.py").write_text("# lib package\n")

    # Initial commit
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    original_cwd = Path.cwd()
    os.chdir(repo)
    try:
        yield repo
    finally:
        os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# AC2: plugins/__init__.py created with correct content
# ---------------------------------------------------------------------------

class TestCreateWorktreeCreatesPluginsInit:
    """AC2 — plugins/__init__.py exists with expected content after create_worktree."""

    def test_create_worktree_creates_plugins_init(self, git_repo: Path) -> None:
        """create_worktree() must produce <wt>/plugins/__init__.py."""
        success, result = create_worktree("feature-ac2", "master")

        assert success is True, f"create_worktree failed: {result}"
        worktree_path: Path = result  # type: ignore[assignment]

        init_file = worktree_path / "plugins" / "__init__.py"
        assert init_file.exists(), f"plugins/__init__.py missing in {worktree_path}"
        assert init_file.read_text() == "# Make plugins a package\n", (
            f"Unexpected content in {init_file}: {init_file.read_text()!r}"
        )


# ---------------------------------------------------------------------------
# AC3: plugins/autonomous_dev symlink created correctly
# ---------------------------------------------------------------------------

class TestCreateWorktreeCreatesAutonomousDevSymlink:
    """AC3 — plugins/autonomous_dev symlink points at autonomous-dev directory."""

    def test_create_worktree_creates_autonomous_dev_symlink(self, git_repo: Path) -> None:
        """create_worktree() must produce a valid plugins/autonomous_dev symlink."""
        success, result = create_worktree("feature-ac3", "master")

        assert success is True, f"create_worktree failed: {result}"
        worktree_path: Path = result  # type: ignore[assignment]

        symlink = worktree_path / "plugins" / "autonomous_dev"
        assert symlink.is_symlink(), f"plugins/autonomous_dev is not a symlink in {worktree_path}"
        # The symlink target must resolve to an existing directory.
        assert symlink.resolve().is_dir(), (
            f"plugins/autonomous_dev symlink does not resolve to a directory: "
            f"target={os.readlink(symlink)!r}"
        )


# ---------------------------------------------------------------------------
# AC1: pytest can import plugins.autonomous_dev from within the worktree
# ---------------------------------------------------------------------------

class TestCreateWorktreePytestCanImportPlugins:
    """AC1 — python can import plugins.autonomous_dev with worktree as CWD."""

    def test_create_worktree_pytest_can_import_plugins(self, git_repo: Path) -> None:
        """After create_worktree(), python -c 'import plugins.autonomous_dev' must succeed."""
        success, result = create_worktree("feature-ac1", "master")

        assert success is True, f"create_worktree failed: {result}"
        worktree_path: Path = result  # type: ignore[assignment]

        proc = subprocess.run(
            [sys.executable, "-c", "import plugins.autonomous_dev"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0, (
            f"import plugins.autonomous_dev failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


# ---------------------------------------------------------------------------
# AC4: idempotency — bootstrap is a no-op when artifacts already exist
# ---------------------------------------------------------------------------

class TestBootstrapIdempotent:
    """AC4 — calling create_worktree() (and thus bootstrap) when artifacts already
    exist must not raise and must leave pre-existing content unchanged."""

    def test_bootstrap_idempotent(self, git_repo: Path) -> None:
        """Pre-creating artifacts before create_worktree() must be a no-op."""
        # First create the worktree to get the path.
        success, result = create_worktree("feature-ac4", "master")
        assert success is True, f"First create_worktree failed: {result}"
        worktree_path: Path = result  # type: ignore[assignment]

        # Overwrite the __init__.py with sentinel content.
        init_file = worktree_path / "plugins" / "__init__.py"
        sentinel = "# sentinel content — must not be overwritten\n"
        init_file.write_text(sentinel)

        # Calling bootstrap again (directly, since create_worktree won't re-create
        # the same worktree path) must not overwrite the existing file.
        _bootstrap_worktree_plugin_artifacts(worktree_path)

        assert init_file.read_text() == sentinel, (
            "Bootstrap overwrote plugins/__init__.py even though it already existed."
        )

        # The symlink must still be valid.
        symlink = worktree_path / "plugins" / "autonomous_dev"
        assert symlink.is_symlink(), "Symlink was removed or replaced by re-running bootstrap."


# ---------------------------------------------------------------------------
# AC5: graceful degradation on OSError
# ---------------------------------------------------------------------------

class TestBootstrapHandlesOsErrorGracefully:
    """AC5 — if symlink/file creation fails with OSError, create_worktree()
    still returns (True, path) and emits a stderr warning."""

    def test_bootstrap_handles_oserror_gracefully(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """OSError during symlink creation must not propagate out of create_worktree."""
        original_symlink_to = Path.symlink_to

        call_count = 0

        def patched_symlink_to(self: Path, target: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise OSError("simulated permission denied")

        monkeypatch.setattr(Path, "symlink_to", patched_symlink_to)

        success, result = create_worktree("feature-ac5", "master")

        # create_worktree must still succeed despite the OSError.
        assert success is True, (
            f"create_worktree returned failure even though OSError should be swallowed: {result}"
        )

        # A warning must have been written to stderr.
        captured = capsys.readouterr()
        assert "WARNING" in captured.err, (
            f"Expected a WARNING on stderr; got: {captured.err!r}"
        )
        assert call_count >= 1, "symlink_to was never called — test did not exercise the OSError path"
