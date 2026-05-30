#!/usr/bin/env python3
"""Regression: _is_autonomous_dev_repo walk-up stops at $HOME.

Bug: The local fallback `_is_autonomous_dev_repo(file_path)` at
unified_pre_tool.py walked up the directory tree looking for
``.claude/commands/implement.md``. With autonomous-dev installed globally at
``~/.claude/commands/implement.md``, the walk-up from ANY project under
``~/`` would eventually reach the user's home directory and find that global
marker — silently classifying every project (even unrelated ones like
``~/Dev/my-side-project/``) as autonomous-dev managed, which then blocked
direct edits to ``agents/*.md``, ``commands/*.md``, ``hooks/*.py``,
``lib/*.py``, ``skills/*/SKILL.md`` via ``_is_protected_infrastructure``.

Fix: stop the walk-up when it reaches ``Path.home().resolve()`` so the
GLOBAL autonomous-dev install no longer pollutes detection for user
projects that don't have their own ``.claude/commands/implement.md``.

These tests exercise the real filesystem via ``tmp_path`` rather than
mocking ``Path.exists``: mocking would hide both the original bug and any
future regression of the walk-up bound.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add hooks dir to sys.path so we can import unified_pre_tool.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOOKS_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import unified_pre_tool as upt  # noqa: E402


class TestWalkUpStopsAtHome:
    """The walk-up must stop at ``Path.home()`` so the global install
    doesn't make every project be classified as autonomous-dev.
    """

    def test_file_under_simulated_home_returns_false_when_only_global_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Bug repro: a file in a project under a simulated home, where ONLY the
        simulated-home ``.claude/commands/implement.md`` exists, must return False.

        Pre-fix this returned True because the walk-up climbed up to ``$HOME``
        and matched the GLOBAL marker there.
        """
        # Build a fake home with the global marker installed.
        fake_home = tmp_path / "fake-home"
        global_marker_dir = fake_home / ".claude" / "commands"
        global_marker_dir.mkdir(parents=True)
        (global_marker_dir / "implement.md").write_text("# global install", encoding="utf-8")

        # Build a sub-project under fake home with NO autonomous-dev install.
        project = fake_home / "Dev" / "my-project"
        project.mkdir(parents=True)
        target_file = project / "some_module.py"
        target_file.write_text("# nothing autonomous-dev about this", encoding="utf-8")

        # Re-point Path.home() to the fake home for the duration of the test.
        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        # Pre-fix: returns True (walk-up hits fake_home/.claude/commands/implement.md).
        # Post-fix: returns False (walk-up stops at home).
        assert upt._is_autonomous_dev_repo(str(target_file)) is False

    def test_file_in_real_autonomous_dev_project_returns_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A project that DOES have its own ``.claude/commands/implement.md``
        below ``$HOME`` is still detected correctly.
        """
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        # No global marker — only a project-local marker.

        project = fake_home / "Dev" / "real-adev-project"
        (project / ".claude" / "commands").mkdir(parents=True)
        (project / ".claude" / "commands" / "implement.md").write_text(
            "# adev installed here", encoding="utf-8"
        )
        target_file = project / "agents" / "planner.md"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("# agent file", encoding="utf-8")

        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        assert upt._is_autonomous_dev_repo(str(target_file)) is True

    def test_file_in_project_overrides_global_via_own_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When both the global marker AND a project-local marker exist, the
        project-local marker wins (walk-up finds it before stopping at home).
        """
        fake_home = tmp_path / "fake-home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "implement.md").write_text(
            "# global install", encoding="utf-8"
        )

        project = fake_home / "Dev" / "real-adev-project"
        (project / ".claude" / "commands").mkdir(parents=True)
        (project / ".claude" / "commands" / "implement.md").write_text(
            "# project-local install", encoding="utf-8"
        )
        target_file = project / "lib" / "thing.py"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("# lib file", encoding="utf-8")

        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        assert upt._is_autonomous_dev_repo(str(target_file)) is True

    def test_file_outside_home_is_not_classified(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A file that is NOT under ``$HOME`` (e.g. ``/tmp/...``) and that has
        no autonomous-dev install in its ancestry must return False.
        """
        fake_home = tmp_path / "fake-home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "implement.md").write_text(
            "# global", encoding="utf-8"
        )

        # File is in tmp_path directly, NOT under fake-home.
        target = tmp_path / "tmp-project" / "foo.py"
        target.parent.mkdir()
        target.write_text("# not in home", encoding="utf-8")

        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        assert upt._is_autonomous_dev_repo(str(target)) is False

    def test_walk_up_hard_limit_still_applies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The 10-level cap remains in force; this just verifies that a file
        very deep below ``$HOME`` (but without project-local marker) still
        terminates and returns False.
        """
        fake_home = tmp_path / "fake-home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "implement.md").write_text(
            "# global", encoding="utf-8"
        )

        deep = fake_home / "a" / "b" / "c" / "d" / "e" / "f" / "g" / "h" / "i" / "j"
        deep.mkdir(parents=True)
        target = deep / "buried.py"
        target.write_text("# deep", encoding="utf-8")

        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        assert upt._is_autonomous_dev_repo(str(target)) is False
