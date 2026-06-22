"""Unit tests for ``hook_bypass`` library (Issue #969 / #942-A).

Library-level coverage of :func:`hook_bypass.is_bypassed` and
:func:`hook_bypass.log_bypass_used`. End-to-end subprocess scenarios live in
``tests/regression/test_universal_hook_bypass.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make hook_bypass importable from the plugins/autonomous-dev/lib tree.
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_bypass  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_bypass_env(monkeypatch):
    """Ensure the bypass env var is unset for every test by default."""
    monkeypatch.delenv(hook_bypass.ENV_VAR_NAME, raising=False)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create an isolated project root with .claude/ subdir."""
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# is_bypassed()
# ---------------------------------------------------------------------------


class TestIsBypassed:
    def test_default_off_no_env_no_file(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        assert hook_bypass.is_bypassed() is False

    def test_env_var_truthy_value_one(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv(hook_bypass.ENV_VAR_NAME, "1")
        assert hook_bypass.is_bypassed() is True

    @pytest.mark.parametrize("value", ["true", "TRUE", "yes", "YES", "on"])
    def test_env_var_other_truthy_values(self, project_dir, monkeypatch, value):
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv(hook_bypass.ENV_VAR_NAME, value)
        assert hook_bypass.is_bypassed() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", ""])
    def test_env_var_falsy_values_do_not_trigger(
        self, project_dir, monkeypatch, value
    ):
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv(hook_bypass.ENV_VAR_NAME, value)
        assert hook_bypass.is_bypassed() is False

    def test_flag_file_in_cwd(self, project_dir, monkeypatch):
        (project_dir / ".claude" / ".bypass").touch()
        monkeypatch.chdir(project_dir)
        assert hook_bypass.is_bypassed() is True

    def test_flag_file_in_ancestor(self, project_dir, monkeypatch):
        nested = project_dir / "src" / "deep" / "nested"
        nested.mkdir(parents=True)
        (project_dir / ".claude" / ".bypass").touch()
        monkeypatch.chdir(nested)
        assert hook_bypass.is_bypassed() is True

    def test_flag_file_removed_restores_default(self, project_dir, monkeypatch):
        flag = project_dir / ".claude" / ".bypass"
        flag.touch()
        monkeypatch.chdir(project_dir)
        assert hook_bypass.is_bypassed() is True
        flag.unlink()
        assert hook_bypass.is_bypassed() is False


# ---------------------------------------------------------------------------
# log_bypass_used()
# ---------------------------------------------------------------------------


class TestLogBypassUsed:
    def test_writes_jsonl_line_with_required_keys(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        hook_bypass.log_bypass_used(
            hook_name="plan_gate.py",
            tool_name="Write",
            reason="env_or_file",
        )
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        event_lines = [
            json.loads(l)
            for l in log_path.read_text(encoding="utf-8").splitlines()
            if l.strip() and '"marker"' not in l
        ]
        assert len(event_lines) == 1
        event = event_lines[0]
        for key in ("timestamp", "hook_name", "tool_name", "reason"):
            assert key in event
        assert event["hook_name"] == "plan_gate.py"

    def test_appends_multiple_calls(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        for i in range(3):
            hook_bypass.log_bypass_used(
                hook_name=f"hook_{i}.py", tool_name="Bash", reason="r"
            )
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        event_lines = [
            l
            for l in log_path.read_text("utf-8").splitlines()
            if l.strip() and '"marker"' not in l
        ]
        assert len(event_lines) == 3

    def test_stderr_fallback_when_log_dir_unwritable(
        self, project_dir, monkeypatch, capsys
    ):
        logs_path = project_dir / ".claude" / "logs"
        logs_path.parent.mkdir(parents=True, exist_ok=True)
        logs_path.write_text("not a dir")
        monkeypatch.chdir(project_dir)
        hook_bypass.log_bypass_used(hook_name="x.py", tool_name="T", reason="r")
        captured = capsys.readouterr()
        assert "[hook-bypass]" in captured.err

    def test_never_raises_on_io_error(self, project_dir, monkeypatch):
        def _bad_resolve(_start=None):
            raise OSError("simulated resolve failure")

        monkeypatch.chdir(project_dir)
        monkeypatch.setattr(hook_bypass, "_resolve_log_path", _bad_resolve)
        # Should not raise.
        hook_bypass.log_bypass_used(hook_name="x.py", tool_name="T", reason="r")


# ---------------------------------------------------------------------------
# Constants and import safety
# ---------------------------------------------------------------------------


class TestBypassOffDefaultNoRegression:
    def test_module_import_does_not_raise(self):
        import importlib

        importlib.reload(hook_bypass)

    def test_default_bypass_is_off(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert hook_bypass.is_bypassed() is False

    def test_constants_are_present(self):
        assert hook_bypass.ENV_VAR_NAME == "AUTONOMOUS_DEV_BYPASS"
        assert hook_bypass.BYPASS_FILE_RELATIVE == Path(".claude") / ".bypass"
        assert (
            hook_bypass.LOG_FILE_RELATIVE
            == Path(".claude") / "logs" / "hook-bypass.jsonl"
        )
        assert hook_bypass.WALK_DEPTH_LIMIT >= 10

# ---------------------------------------------------------------------------
# Issue #1197: Command head and window transition markers
# ---------------------------------------------------------------------------


class TestCommandHeadAndWindowMarkers:
    def test_log_bypass_used_records_command_head(self, project_dir, monkeypatch):
        """Issue #1197: command_head appears in JSONL when provided."""
        monkeypatch.chdir(project_dir)
        hook_bypass.log_bypass_used(
            hook_name="test.py", 
            tool_name="Bash",
            command_head="git status --short"
        )
        
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        lines = log_path.read_text("utf-8").strip().split("\n")
        
        # Find the event line (not the marker line)
        event_line = None
        for line in lines:
            data = json.loads(line)
            if "hook_name" in data:
                event_line = data
                break
        
        assert event_line is not None
        assert event_line["command_head"] == "git status --short"
        assert event_line["tool_name"] == "Bash"

    def test_log_bypass_used_omits_empty_command_head(self, project_dir, monkeypatch):
        """Issue #1197: command_head field absent when not provided."""
        monkeypatch.chdir(project_dir)
        hook_bypass.log_bypass_used(
            hook_name="test.py", 
            tool_name="Write"
        )
        
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        lines = log_path.read_text("utf-8").strip().split("\n")
        
        # Find the event line
        event_line = None
        for line in lines:
            data = json.loads(line)
            if "hook_name" in data:
                event_line = data
                break
        
        assert event_line is not None
        assert "command_head" not in event_line
        assert event_line["tool_name"] == "Write"

    def test_log_bypass_used_truncates_long_command_head(self, project_dir, monkeypatch):
        """Issue #1197: defensive 200-char truncation."""
        monkeypatch.chdir(project_dir)
        long_command = "x" * 300
        hook_bypass.log_bypass_used(
            hook_name="test.py", 
            tool_name="Bash",
            command_head=long_command
        )
        
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        lines = log_path.read_text("utf-8").strip().split("\n")
        
        # Find the event line
        event_line = None
        for line in lines:
            data = json.loads(line)
            if "hook_name" in data:
                event_line = data
                break
        
        assert event_line is not None
        assert event_line["command_head"] == "x" * 200
        assert len(event_line["command_head"]) == 200

    def test_window_transition_open_emits_marker(self, project_dir, monkeypatch):
        """Issue #1197: first call with bypass_active=True emits OPEN marker."""
        monkeypatch.chdir(project_dir)
        
        # Clean state
        state_path = project_dir / hook_bypass.STATE_FILE_RELATIVE
        if state_path.exists():
            state_path.unlink()
        
        # First bypass should emit OPEN marker
        hook_bypass.log_bypass_used(
            hook_name="test.py",
            tool_name="Bash"
        )
        
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        lines = log_path.read_text("utf-8").strip().split("\n")
        
        # Should have marker line
        markers = []
        for line in lines:
            data = json.loads(line)
            if "marker" in data:
                markers.append(data["marker"])
        
        assert "BYPASS-WINDOW-OPEN" in markers

    def test_window_transition_close_emits_marker(self, project_dir, monkeypatch):
        """Issue #1197: after OPEN, check_and_log_window_close emits CLOSE."""
        monkeypatch.chdir(project_dir)
        
        # Clean state
        state_path = project_dir / hook_bypass.STATE_FILE_RELATIVE
        if state_path.exists():
            state_path.unlink()
        
        # First bypass should emit OPEN marker
        hook_bypass.log_bypass_used(
            hook_name="test.py",
            tool_name="Bash"
        )
        
        # Now check for close
        hook_bypass.check_and_log_window_close()
        
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        lines = log_path.read_text("utf-8").strip().split("\n")
        
        # Should have both markers
        markers = []
        for line in lines:
            data = json.loads(line)
            if "marker" in data:
                markers.append(data["marker"])
        
        assert "BYPASS-WINDOW-OPEN" in markers
        assert "BYPASS-WINDOW-CLOSE" in markers

    def test_window_no_transition_no_marker(self, project_dir, monkeypatch):
        """Issue #1197: repeated calls with same state emit no marker."""
        monkeypatch.chdir(project_dir)
        
        # Clean state
        state_path = project_dir / hook_bypass.STATE_FILE_RELATIVE
        if state_path.exists():
            state_path.unlink()
        
        # First bypass should emit OPEN marker
        hook_bypass.log_bypass_used(
            hook_name="test1.py",
            tool_name="Bash"
        )
        
        # Second bypass should NOT emit another OPEN marker
        hook_bypass.log_bypass_used(
            hook_name="test2.py",
            tool_name="Write"
        )
        
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        lines = log_path.read_text("utf-8").strip().split("\n")
        
        # Should have only one OPEN marker
        markers = []
        for line in lines:
            data = json.loads(line)
            if "marker" in data:
                markers.append(data["marker"])
        
        assert markers.count("BYPASS-WINDOW-OPEN") == 1

    def test_window_state_file_corrupt_fails_open(self, project_dir, monkeypatch):
        """Issue #1197: corrupt state file is treated as 'no prior state', no exception."""
        monkeypatch.chdir(project_dir)
        
        # Create corrupt state file
        state_path = project_dir / hook_bypass.STATE_FILE_RELATIVE
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not json {{{ corrupt")
        
        # Should not raise, should treat as no prior state
        hook_bypass.log_bypass_used(
            hook_name="test.py",
            tool_name="Bash"
        )
        
        # Should emit OPEN marker since corrupt state is treated as no state
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        lines = log_path.read_text("utf-8").strip().split("\n")
        
        markers = []
        for line in lines:
            data = json.loads(line)
            if "marker" in data:
                markers.append(data["marker"])
        
        assert "BYPASS-WINDOW-OPEN" in markers

    def test_log_bypass_used_never_raises_on_disk_error(self, project_dir, monkeypatch):
        """Issue #1197: make log path read-only and verify no exception."""
        monkeypatch.chdir(project_dir)
        
        # Create the log file first
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("existing content\n")
        
        # Make parent directory read-only
        import os
        os.chmod(log_path.parent, 0o555)
        
        try:
            # Should not raise even though we can't write
            hook_bypass.log_bypass_used(
                hook_name="test.py",
                tool_name="Bash",
                command_head="test command"
            )
            # Should complete without exception
            assert True
        finally:
            # Restore write permissions for cleanup
            os.chmod(log_path.parent, 0o755)