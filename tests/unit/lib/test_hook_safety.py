"""Unit tests for plugins/autonomous-dev/lib/hook_safety.py — Issue #953.

Covers safe_main (hook-failure swallowing) and command_registered (slash
command precondition probing). Both helpers are critical to the
"hooks must never block Claude Code due to their own infrastructure
failure" acceptance criterion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import hook_safety  # noqa: E402  (sys.path manipulation must precede import)
from hook_safety import command_registered, safe_main  # noqa: E402


# ---------------------------------------------------------------------------
# safe_main tests
# ---------------------------------------------------------------------------


class TestSafeMain:
    """Tests for the safe_main() outer wrap."""

    def test_safe_main_passes_through_normal_completion(self, capsys):
        """A function that returns None exits 0 with no warning."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: None)
        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert "[hook warning]" not in captured.err

    def test_safe_main_swallows_exception_and_exits_zero(self, capsys):
        """An unhandled exception is converted to exit 0 + stderr warning."""
        def crashing():
            raise RuntimeError("simulated hook bug")

        with pytest.raises(SystemExit) as excinfo:
            safe_main(crashing)
        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert captured.err.startswith("[hook warning]")
        assert "RuntimeError" in captured.err
        assert "simulated hook bug" in captured.err

    def test_safe_main_propagates_keyboardinterrupt(self):
        """Ctrl+C MUST NOT be swallowed (debugging UX)."""
        def interrupted():
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            safe_main(interrupted)

    def test_safe_main_propagates_systemexit(self):
        """Explicit SystemExit (e.g. sys.exit(2)) MUST pass through unchanged."""
        def exiting():
            raise SystemExit(2)

        with pytest.raises(SystemExit) as excinfo:
            safe_main(exiting)
        assert excinfo.value.code == 2

    def test_safe_main_propagates_systemexit_zero(self):
        """sys.exit(0) MUST pass through (not be caught as 'normal' return)."""
        def exiting():
            sys.exit(0)

        with pytest.raises(SystemExit) as excinfo:
            safe_main(exiting)
        assert excinfo.value.code == 0

    def test_safe_main_preserves_int_return(self):
        """An int return value MUST be the exit code (preserves block/warn)."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: 2)
        assert excinfo.value.code == 2

    def test_safe_main_preserves_int_return_one(self):
        """Return-1 (warning convention) MUST exit 1."""
        with pytest.raises(SystemExit) as excinfo:
            safe_main(lambda: 1)
        assert excinfo.value.code == 1

    def test_safe_main_swallows_importerror(self, capsys):
        """Broken imports inside main MUST NOT block."""
        def broken_import():
            import nonexistent_module_xyz_953  # noqa: F401

        with pytest.raises(SystemExit) as excinfo:
            safe_main(broken_import)
        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert "[hook warning]" in captured.err
        # ModuleNotFoundError is a subclass of ImportError; either name is fine
        assert ("ImportError" in captured.err
                or "ModuleNotFoundError" in captured.err)

    def test_safe_main_warning_includes_hook_name(self, capsys):
        """Warning line MUST include the calling file name for diagnosis."""
        def crashing():
            raise ValueError("boom")

        with pytest.raises(SystemExit):
            safe_main(crashing)
        captured = capsys.readouterr()
        # The caller is this test file; safe_main walks one frame up.
        assert "test_hook_safety.py" in captured.err


# ---------------------------------------------------------------------------
# command_registered tests
# ---------------------------------------------------------------------------


class TestCommandRegistered:
    """Tests for command_registered() slash-command lookup."""

    def test_command_registered_finds_user_global_command(
        self, tmp_path, monkeypatch
    ):
        """A command file under ~/.claude/commands/ MUST be discovered."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "create-issue.md").write_text(
            "# create-issue\n"
        )
        # Move cwd somewhere with no .claude/commands so only home matches.
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("create-issue") is True

    def test_command_registered_finds_project_command(
        self, tmp_path, monkeypatch
    ):
        """A command file under ./.claude/commands/ MUST be discovered."""
        project = tmp_path / "project"
        (project / ".claude" / "commands").mkdir(parents=True)
        (project / ".claude" / "commands" / "my-cmd.md").write_text("# my-cmd\n")
        # Empty fake home so the project-local lookup is the only hit.
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(project)

        assert command_registered("my-cmd") is True

    def test_command_registered_finds_installed_plugin_command(
        self, tmp_path, monkeypatch
    ):
        """An entry in installed_plugins.json MUST be discovered."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude").mkdir(parents=True)
        manifest = fake_home / ".claude" / "installed_plugins.json"
        manifest.write_text(json.dumps({
            "commands": [{"name": "from-manifest"}],
        }))
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("from-manifest") is True

    def test_command_registered_finds_plugins_subdir_manifest(
        self, tmp_path, monkeypatch
    ):
        """Manifest at ~/.claude/plugins/installed_plugins.json MUST work."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "plugins").mkdir(parents=True)
        manifest = fake_home / ".claude" / "plugins" / "installed_plugins.json"
        manifest.write_text(json.dumps({
            "installed_plugins": {
                "autonomous-dev": {"commands": [{"name": "deep-cmd"}]},
            },
        }))
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("deep-cmd") is True

    def test_command_registered_returns_false_when_truly_missing(
        self, tmp_path, monkeypatch
    ):
        """No command anywhere → False (the only fail-OPEN signal)."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("does-not-exist-953") is False

    def test_command_registered_strips_leading_slash(
        self, tmp_path, monkeypatch
    ):
        """Both 'foo' and '/foo' MUST resolve to the same lookup."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "foo.md").write_text("# foo\n")
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("foo") is True
        assert command_registered("/foo") is True

    def test_command_registered_handles_bad_json_gracefully(
        self, tmp_path, monkeypatch
    ):
        """Malformed installed_plugins.json MUST NOT crash the lookup."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude").mkdir(parents=True)
        manifest = fake_home / ".claude" / "installed_plugins.json"
        manifest.write_text("{this is not valid json")
        # Provide a real command file in the project dir so we get a
        # deterministic True (proves the bad-JSON path didn't blow up).
        project = tmp_path / "project"
        (project / ".claude" / "commands").mkdir(parents=True)
        (project / ".claude" / "commands" / "lookup-me.md").write_text("# x\n")
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(project)

        # Should not raise — bad JSON is treated as "no info".
        assert command_registered("lookup-me") is True
        # And a missing command should still resolve to False (not crash).
        assert command_registered("nope-953") is False

    def test_command_registered_empty_name_returns_true(
        self, tmp_path, monkeypatch
    ):
        """An empty name is fail-CLOSED (we cannot say it's missing)."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        # Empty/whitespace names are not actionable — fail-CLOSED.
        assert command_registered("") is True
        assert command_registered("/") is True

    def test_command_registered_fail_closed_on_unexpected_error(
        self, monkeypatch
    ):
        """If lookup raises unexpectedly, return True (fail-CLOSED).

        This protects the security barrier: a programming bug or unexpected
        runtime failure MUST NOT silently downgrade a deny path to allow.
        We simulate the unexpected error by patching the leading-slash
        helper to raise — that runs early in command_registered() before
        the per-step try/except blocks would catch it.
        """
        def boom(_name):
            raise RuntimeError("simulated unexpected lookup failure")

        monkeypatch.setattr(hook_safety, "_strip_leading_slash", boom)

        # Even with the lookup unexpectedly broken, fail-CLOSED → True.
        assert command_registered("anything") is True

    def test_command_registered_string_command_entries(
        self, tmp_path, monkeypatch
    ):
        """Manifest entries that are strings (not dicts) MUST also work."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude").mkdir(parents=True)
        manifest = fake_home / ".claude" / "installed_plugins.json"
        manifest.write_text(json.dumps({
            "commands": ["string-style-cmd"],
        }))
        empty_cwd = tmp_path / "elsewhere"
        empty_cwd.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.chdir(empty_cwd)

        assert command_registered("string-style-cmd") is True
