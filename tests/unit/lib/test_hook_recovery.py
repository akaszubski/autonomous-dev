"""Unit tests for ``hook_recovery`` library (Issue #970).

Library-level coverage of the four public functions:

- :func:`hook_recovery.is_recovery_disabled`
- :func:`hook_recovery.can_user_recover`
- :func:`hook_recovery.log_block_with_recovery`
- :func:`hook_recovery.clear_stale_state`

Mirrors ``tests/unit/lib/test_hook_bypass.py`` style.
"""

from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import pytest

# Make hook_recovery importable from plugins/autonomous-dev/lib.
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_recovery  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_recovery_env(monkeypatch):
    """Ensure recovery env vars are unset for each test by default."""
    monkeypatch.delenv(hook_recovery.DISABLE_ENV_VAR, raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create an isolated project root with .claude/{logs,config}/ subdirs."""
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "config").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def isolated_registry(monkeypatch, project_dir):
    """Force registry resolution to the project_dir, bypassing the plugin file.

    The plugin-shipped registry is the default; tests need to override it to
    write their own malformed/well-formed copies.
    """
    def _resolver(start_dir=None):
        return project_dir / hook_recovery.EXEMPTION_REGISTRY_PATH

    monkeypatch.setattr(hook_recovery, "_resolve_registry_path", _resolver)
    return project_dir / hook_recovery.EXEMPTION_REGISTRY_PATH


# ---------------------------------------------------------------------------
# is_recovery_disabled()
# ---------------------------------------------------------------------------


class TestIsRecoveryDisabled:
    def test_is_recovery_disabled_env_var_truthy(self, monkeypatch):
        monkeypatch.setenv(hook_recovery.DISABLE_ENV_VAR, "1")
        assert hook_recovery.is_recovery_disabled() is True

    def test_is_recovery_disabled_env_var_unset(self, monkeypatch):
        monkeypatch.delenv(hook_recovery.DISABLE_ENV_VAR, raising=False)
        assert hook_recovery.is_recovery_disabled() is False

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_falsy_values_keep_recovery_enabled(self, monkeypatch, value):
        monkeypatch.setenv(hook_recovery.DISABLE_ENV_VAR, value)
        assert hook_recovery.is_recovery_disabled() is False


# ---------------------------------------------------------------------------
# can_user_recover()
# ---------------------------------------------------------------------------


class TestCanUserRecover:
    def test_can_user_recover_exempted_returns_true(self, isolated_registry):
        isolated_registry.write_text(
            json.dumps(
                {
                    "version": 1,
                    "exemptions": [
                        {
                            "hook_name": "unified_pre_tool.py",
                            "block_reason_contains": "WORKFLOW ENFORCEMENT",
                        }
                    ],
                }
            )
        )
        assert hook_recovery.can_user_recover(
            hook_name="unified_pre_tool.py",
            block_reason="WORKFLOW ENFORCEMENT: delegate to implementer",
        ) is True

    def test_can_user_recover_no_exemption_returns_false(self, isolated_registry):
        isolated_registry.write_text(
            json.dumps({"version": 1, "exemptions": []})
        )
        assert hook_recovery.can_user_recover(
            hook_name="unified_pre_tool.py",
            block_reason="WORKFLOW ENFORCEMENT: delegate to implementer",
        ) is False

    def test_exemption_registry_parse_failure_safe(self, isolated_registry):
        # Malformed JSON must be treated as "no exemptions" without raising.
        isolated_registry.write_text("{this is not valid json")
        assert hook_recovery.can_user_recover(
            hook_name="unified_pre_tool.py",
            block_reason="anything",
        ) is False

    def test_missing_registry_returns_false(self, isolated_registry):
        # File doesn't exist — caller should get False, not an exception.
        assert not isolated_registry.exists()
        assert hook_recovery.can_user_recover(
            hook_name="unified_pre_tool.py",
            block_reason="anything",
        ) is False


# ---------------------------------------------------------------------------
# log_block_with_recovery()
# ---------------------------------------------------------------------------


class TestLogBlockWithRecovery:
    def test_log_writes_jsonl_row(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        hook_recovery.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="WORKFLOW ENFORCEMENT: delegate to implementer",
            recovery_hint="Invoke the implementer agent via Task tool.",
            session_id="sess-123",
        )
        log_path = project_dir / hook_recovery.LOG_FILE_RELATIVE
        assert log_path.exists()
        line = log_path.read_text().strip()
        event = json.loads(line)
        assert event["hook_name"] == "unified_pre_tool.py"
        assert event["tool_name"] == "Bash"
        assert event["block_reason"].startswith("WORKFLOW ENFORCEMENT")
        assert "Invoke the implementer agent" in event["recovery_hint"]
        assert event["session_id"] == "sess-123"
        assert "timestamp" in event

    def test_log_never_raises_on_readonly_fs(self, project_dir, monkeypatch):
        """When file open fails with OSError, log MUST fall back, not crash."""
        monkeypatch.chdir(project_dir)
        # Patch Path.open so any call from hook_recovery raises OSError.
        from pathlib import Path as _Path

        original_open = _Path.open

        def fail_open(self, *args, **kwargs):
            if str(self).endswith("hook-recovery.jsonl"):
                raise OSError("read-only file system")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(_Path, "open", fail_open)

        # Must not raise.
        hook_recovery.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="reason",
            recovery_hint="hint",
        )

    def test_log_falls_back_to_stderr_on_io_failure(
        self, project_dir, monkeypatch
    ):
        monkeypatch.chdir(project_dir)
        from pathlib import Path as _Path

        original_open = _Path.open

        def fail_open(self, *args, **kwargs):
            if str(self).endswith("hook-recovery.jsonl"):
                raise OSError("permission denied")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(_Path, "open", fail_open)

        # Capture sys.stderr.write directly.
        captured: list[str] = []
        import sys as _sys

        original_write = _sys.stderr.write

        def capture_write(text):
            captured.append(text)
            return original_write(text)

        monkeypatch.setattr(_sys.stderr, "write", capture_write)

        hook_recovery.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="boom",
            recovery_hint="reset",
        )
        joined = "".join(captured)
        assert "[hook-recovery]" in joined
        assert "boom" in joined

    def test_log_disabled_when_env_var_set(
        self, project_dir, monkeypatch
    ):
        """HOOK_RECOVERY_DISABLED makes log a no-op (no file written)."""
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv(hook_recovery.DISABLE_ENV_VAR, "1")
        hook_recovery.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="reason",
            recovery_hint="hint",
        )
        log_path = project_dir / hook_recovery.LOG_FILE_RELATIVE
        assert not log_path.exists()


# ---------------------------------------------------------------------------
# clear_stale_state()
# ---------------------------------------------------------------------------


class TestClearStaleState:
    def test_clear_stale_state_removes_when_session_id_mismatch(self, tmp_path):
        state = tmp_path / "pipeline_state.json"
        state.write_text(json.dumps({"session_id": "owner-OLD"}))
        removed = hook_recovery.clear_stale_state(
            state, owning_session_id="current-NEW"
        )
        assert removed is True
        assert not state.exists()

    def test_clear_stale_state_keeps_when_session_id_matches(self, tmp_path):
        state = tmp_path / "pipeline_state.json"
        state.write_text(json.dumps({"session_id": "same-owner"}))
        removed = hook_recovery.clear_stale_state(
            state, owning_session_id="same-owner"
        )
        assert removed is False
        assert state.exists()

    def test_clear_stale_state_corrupt_json_treated_as_stale_removes(
        self, tmp_path
    ):
        state = tmp_path / "pipeline_state.json"
        state.write_text("{not valid json")
        removed = hook_recovery.clear_stale_state(
            state, owning_session_id="any"
        )
        assert removed is True
        assert not state.exists()

    def test_clear_stale_state_missing_file_returns_false(self, tmp_path):
        state = tmp_path / "does_not_exist.json"
        removed = hook_recovery.clear_stale_state(
            state, owning_session_id="any"
        )
        assert removed is False

    def test_clear_stale_state_no_owner_keeps_file(self, tmp_path, monkeypatch):
        """Without owner info, we can't decide — leave file alone (safe)."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        state = tmp_path / "pipeline_state.json"
        state.write_text(json.dumps({"session_id": "owner-X"}))
        removed = hook_recovery.clear_stale_state(state, owning_session_id=None)
        assert removed is False
        assert state.exists()

    def test_clear_stale_state_disabled_when_env_var_set(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(hook_recovery.DISABLE_ENV_VAR, "1")
        state = tmp_path / "pipeline_state.json"
        state.write_text(json.dumps({"session_id": "owner-OLD"}))
        removed = hook_recovery.clear_stale_state(
            state, owning_session_id="current-NEW"
        )
        # Disabled -> no-op, even though session id mismatched.
        assert removed is False
        assert state.exists()
