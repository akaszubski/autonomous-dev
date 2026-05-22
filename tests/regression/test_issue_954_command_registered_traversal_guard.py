"""Regression test for Issue #954 (M-01 security finding).

``hook_safety.command_registered(name)`` previously constructed a filesystem
path directly from the caller-supplied ``name`` argument in
``_check_command_dir()``::

    (directory / f"{command_name}.md").is_file()

If ``name`` contained path-traversal sequences (e.g. ``"../../../etc/passwd"``)
the resolved path escaped the intended ``.claude/commands/`` tree. No
production caller passed user-controlled input through this entry point — but
defense-in-depth requires the function itself to refuse to take the bait.

This test file validates the fix applied in #954:

1. ``command_name`` containing ``/`` is rejected.
2. ``command_name`` containing ``\\`` is rejected.
3. ``command_name`` containing ``..`` is rejected.
4. A symlink-based escape (creating ``<cmd-dir>/escape`` -> outside) is
   caught by the ``Path.resolve()`` containment backstop.
5. Healthy lookups still work (no regression).
6. The existing fail-CLOSED behavior on unexpected errors is preserved.

The guard MUST be present at BOTH chokepoints: ``_check_command_dir`` (the
filesystem-touching helper, where the bug lived) AND ``command_registered``
(the public entry point, single-chokepoint defense-in-depth).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import hook_safety  # noqa: E402  (sys.path manipulation must precede import)
from hook_safety import _check_command_dir, command_registered  # noqa: E402


class TestIssue954TraversalGuard:
    """Regression for Issue #954 (M-01)."""

    # ------------------------------------------------------------------
    # Test 1-4: Traversal characters in the command name MUST be rejected.
    # ------------------------------------------------------------------

    def test_traversal_via_dotdot_returns_false(self, tmp_path, monkeypatch):
        """command_registered("../../../etc/passwd") MUST return False.

        Critically, it MUST NOT touch /etc/passwd in the process. The guard
        rejects the input before any filesystem lookup is attempted.
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        # If the guard worked, this returns False without ever resolving a
        # path that points at /etc/passwd.
        assert command_registered("../../../etc/passwd") is False

    def test_forward_slash_in_name_returns_false(self, tmp_path, monkeypatch):
        """command_registered("foo/bar") MUST return False — '/' is forbidden."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("foo/bar") is False

    def test_backslash_in_name_returns_false(self, tmp_path, monkeypatch):
        """command_registered("foo\\bar") MUST return False — '\\' is forbidden."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("foo\\bar") is False

    def test_double_dot_alone_returns_false(self, tmp_path, monkeypatch):
        """command_registered("..") MUST return False — '..' is forbidden."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("..") is False

    # ------------------------------------------------------------------
    # Test 5: Healthy path must still work (no regression).
    # ------------------------------------------------------------------

    def test_valid_command_name_still_resolves(self, tmp_path, monkeypatch):
        """A legitimate command name with no traversal chars MUST still work."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "create-issue.md").write_text(
            "# create-issue\n"
        )
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("create-issue") is True

    # ------------------------------------------------------------------
    # Test 6: Symlink-based escape MUST be caught by the resolve-and-contain
    # backstop in _check_command_dir.
    # ------------------------------------------------------------------

    def test_symlink_escape_blocked_by_resolve_backstop(self, tmp_path):
        """A symlink pointing outside the directory MUST be rejected.

        This exercises the second layer of defense — even if a clean name
        gets through the primary guard, ``Path.resolve()`` should detect
        that the resolved candidate has escaped the directory.

        Scenario: ``directory/escape.md`` is a symlink pointing at a file
        outside ``directory``. Since the candidate name ``"escape"`` itself
        contains no traversal chars, the primary guard does not fire — the
        backstop must.
        """
        if sys.platform == "win32":  # pragma: no cover — symlinks gated on Win
            pytest.skip("Symlink semantics differ on Windows")

        cmd_dir = tmp_path / "cmds"
        cmd_dir.mkdir()
        outside = tmp_path / "outside.md"
        outside.write_text("# I am outside the command tree\n")

        # Create a symlink INSIDE cmd_dir that points OUTSIDE.
        symlink = cmd_dir / "escape.md"
        try:
            os.symlink(outside, symlink)
        except (OSError, NotImplementedError) as exc:  # pragma: no cover
            pytest.skip(f"Cannot create symlink in this environment: {exc}")

        # The clean name "escape" contains no traversal chars, so the
        # primary guard does NOT fire. The backstop MUST catch the escape
        # because the resolved path is outside cmd_dir.
        assert _check_command_dir(cmd_dir, "escape") is False

    # ------------------------------------------------------------------
    # Test 7: Empty string preserves the documented fail-CLOSED behavior.
    # ------------------------------------------------------------------

    def test_empty_string_still_returns_true_fail_closed(
        self, tmp_path, monkeypatch
    ):
        """Empty name preserves existing fail-CLOSED behavior.

        The traversal guard MUST NOT regress the documented contract that
        an empty/whitespace name returns True (we cannot say it's missing).
        """
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("") is True

    # ------------------------------------------------------------------
    # Bonus: direct unit test of the _check_command_dir guard.
    # ------------------------------------------------------------------

    def test_check_command_dir_rejects_traversal_directly(self, tmp_path):
        """Verify the inner helper rejects traversal independent of the public API."""
        cmd_dir = tmp_path / "cmds"
        cmd_dir.mkdir()
        # Even if the directory exists and the lookup would otherwise be
        # well-defined, the traversal chars MUST short-circuit to False.
        assert _check_command_dir(cmd_dir, "../../../etc/passwd") is False
        assert _check_command_dir(cmd_dir, "foo/bar") is False
        assert _check_command_dir(cmd_dir, "foo\\bar") is False
        assert _check_command_dir(cmd_dir, "..") is False

    def test_check_command_dir_did_not_touch_etc_passwd(
        self, tmp_path, monkeypatch
    ):
        """Belt-and-suspenders: prove the lookup never reaches the OS.

        Patch ``Path.is_file`` to fail loudly if the traversal got past the
        guard. The patched method MUST NOT be invoked when the name contains
        traversal chars.
        """
        cmd_dir = tmp_path / "cmds"
        cmd_dir.mkdir()

        called: list[Path] = []
        original_is_file = Path.is_file

        def tattletale(self):
            called.append(Path(self))
            return original_is_file(self)

        monkeypatch.setattr(Path, "is_file", tattletale)

        # Run a traversal attempt — guard should short-circuit before is_file.
        result = _check_command_dir(cmd_dir, "../../../etc/passwd")
        assert result is False
        # No is_file() call attributable to /etc/passwd should have happened.
        assert not any("etc/passwd" in str(p) for p in called), (
            f"Traversal reached filesystem: {called}"
        )
