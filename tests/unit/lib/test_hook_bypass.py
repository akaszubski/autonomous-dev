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
        line = log_path.read_text(encoding="utf-8").strip()
        event = json.loads(line)
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
        lines = [
            l for l in log_path.read_text("utf-8").splitlines() if l.strip()
        ]
        assert len(lines) == 3

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
