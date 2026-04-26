"""Unit tests for ``hook_telemetry`` library (Issue #972).

Library-level coverage of the public API:

- :func:`hook_telemetry.is_telemetry_disabled`
- :func:`hook_telemetry.log_block_event`
- :func:`hook_telemetry.block_event_decorator`
- :func:`hook_telemetry.can_user_recover`

Plus the back-compat shim in ``hook_recovery.log_block_with_recovery``.

Mirrors ``tests/unit/lib/test_hook_recovery.py`` style.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

# Make hook_telemetry / hook_recovery importable from plugins/autonomous-dev/lib.
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_telemetry  # noqa: E402
import hook_recovery  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_telemetry_env(monkeypatch):
    """Ensure telemetry env vars are unset for each test by default."""
    monkeypatch.delenv(hook_telemetry.DISABLE_ENV_VAR, raising=False)
    monkeypatch.delenv(hook_telemetry.LEGACY_DISABLE_ENV_VAR, raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    # Reset the module-level dedup flag for the legacy-env warning.
    hook_telemetry._legacy_env_warned = False


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch) -> Path:
    """Create an isolated project root with .claude/{logs,config}/ subdirs and chdir."""
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# is_telemetry_disabled()
# ---------------------------------------------------------------------------


class TestIsTelemetryDisabled:
    def test_unset_returns_false(self, monkeypatch):
        monkeypatch.delenv(hook_telemetry.DISABLE_ENV_VAR, raising=False)
        monkeypatch.delenv(hook_telemetry.LEGACY_DISABLE_ENV_VAR, raising=False)
        assert hook_telemetry.is_telemetry_disabled() is False

    def test_truthy_disables(self, monkeypatch):
        monkeypatch.setenv(hook_telemetry.DISABLE_ENV_VAR, "1")
        assert hook_telemetry.is_telemetry_disabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_falsy_values_keep_enabled(self, monkeypatch, value):
        monkeypatch.setenv(hook_telemetry.DISABLE_ENV_VAR, value)
        assert hook_telemetry.is_telemetry_disabled() is False

    def test_legacy_env_var_honored_as_alias(self, monkeypatch, capsys):
        """HOOK_RECOVERY_DISABLED is accepted as an alias with a warning."""
        monkeypatch.setenv(hook_telemetry.LEGACY_DISABLE_ENV_VAR, "1")
        assert hook_telemetry.is_telemetry_disabled() is True
        captured = capsys.readouterr()
        assert "DEPRECATED" in captured.err
        assert "HOOK_RECOVERY_DISABLED" in captured.err

    def test_legacy_env_var_warning_fires_once(self, monkeypatch, capsys):
        """The deprecation warning is rate-limited to one per process."""
        monkeypatch.setenv(hook_telemetry.LEGACY_DISABLE_ENV_VAR, "1")
        hook_telemetry.is_telemetry_disabled()
        hook_telemetry.is_telemetry_disabled()
        hook_telemetry.is_telemetry_disabled()
        captured = capsys.readouterr()
        assert captured.err.count("DEPRECATED") == 1

    def test_new_env_var_takes_precedence_over_legacy(self, monkeypatch):
        """When both are set, the new one wins (and no legacy warning)."""
        monkeypatch.setenv(hook_telemetry.DISABLE_ENV_VAR, "0")
        monkeypatch.setenv(hook_telemetry.LEGACY_DISABLE_ENV_VAR, "1")
        # New is "0" (falsy) so result is False — legacy is ignored entirely.
        assert hook_telemetry.is_telemetry_disabled() is False


# ---------------------------------------------------------------------------
# log_block_event()
# ---------------------------------------------------------------------------


class TestLogBlockEvent:
    def test_writes_jsonl_line(self, project_dir):
        hook_telemetry.log_block_event(
            hook_name="unified_pre_tool.py",
            decision_shape="tuple",
            reason="WORKFLOW ENFORCEMENT: must use /implement",
        )
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        assert log_path.exists()
        content = log_path.read_text().strip()
        row = json.loads(content)
        assert row["hook_name"] == "unified_pre_tool.py"
        assert row["decision_shape"] == "tuple"
        assert "WORKFLOW ENFORCEMENT" in row["reason"]
        assert "ts" in row
        assert "session_id" in row
        assert "cwd" in row
        assert "metadata" in row

    def test_appends_multiple_rows(self, project_dir):
        for i in range(5):
            hook_telemetry.log_block_event(
                hook_name="unified_pre_tool.py",
                decision_shape="tuple",
                reason=f"block #{i}",
            )
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 5
        for i, line in enumerate(lines):
            assert json.loads(line)["reason"] == f"block #{i}"

    def test_disabled_is_noop(self, project_dir, monkeypatch):
        monkeypatch.setenv(hook_telemetry.DISABLE_ENV_VAR, "1")
        hook_telemetry.log_block_event(
            hook_name="unified_pre_tool.py",
            decision_shape="tuple",
            reason="should not appear",
        )
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        assert not log_path.exists()

    def test_caps_long_reason(self, project_dir):
        long_reason = "x" * (hook_telemetry.MAX_REASON_LENGTH + 5000)
        hook_telemetry.log_block_event(
            hook_name="h.py",
            decision_shape="dict",
            reason=long_reason,
        )
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        row = json.loads(log_path.read_text().strip())
        assert len(row["reason"]) == hook_telemetry.MAX_REASON_LENGTH

    def test_metadata_sanitized(self, project_dir):
        hook_telemetry.log_block_event(
            hook_name="h.py",
            decision_shape="exit2",
            reason="r",
            metadata={"tool_name": "Bash", "count": 3},
        )
        row = json.loads(
            (project_dir / hook_telemetry.LOG_FILE_RELATIVE).read_text().strip()
        )
        assert row["metadata"]["tool_name"] == "Bash"
        assert row["metadata"]["count"] == 3

    def test_non_serialisable_metadata_downgrades_to_empty(self, project_dir):
        # An object with no JSON representation (and no __str__ via default=str
        # would still produce something — use a set inside since json.dumps
        # rejects sets even with default=str). Actually json.dumps rejects
        # sets even with default=str only if not handled — let's force
        # serialisation failure by making default=str raise.

        class Unhashable:
            def __str__(self):
                raise RuntimeError("nope")

        # The default=str path will catch this — assert telemetry doesn't crash
        # and falls back to {}.
        hook_telemetry.log_block_event(
            hook_name="h.py",
            decision_shape="exit2",
            reason="r",
            metadata={"bad": Unhashable()},
        )
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        # Should still produce a row (telemetry never raises).
        assert log_path.exists()


# ---------------------------------------------------------------------------
# NEVER-RAISE contract
# ---------------------------------------------------------------------------


class TestNeverRaises:
    def test_log_does_not_raise_on_oserror(self, project_dir, monkeypatch, capsys):
        """Patch Path.open to raise OSError; verify telemetry falls back to stderr."""
        original_open = Path.open

        def fake_open(self, *args, **kwargs):
            if str(self).endswith("hook-blocks.jsonl"):
                raise OSError("read-only filesystem")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", fake_open)

        # Should not raise.
        hook_telemetry.log_block_event(
            hook_name="h.py",
            decision_shape="tuple",
            reason="filesystem failure test",
        )
        captured = capsys.readouterr()
        assert "[hook-telemetry]" in captured.err
        assert "log_write_failed" in captured.err

    def test_log_does_not_raise_on_unrelated_exception(
        self, project_dir, monkeypatch, capsys
    ):
        """Even completely unexpected errors must not propagate."""

        def boom(self, *args, **kwargs):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(Path, "mkdir", boom)
        # Must not raise.
        hook_telemetry.log_block_event(
            hook_name="h.py",
            decision_shape="tuple",
            reason="r",
        )


# ---------------------------------------------------------------------------
# block_event_decorator()
# ---------------------------------------------------------------------------


class TestBlockEventDecorator:
    def test_logs_only_on_deny(self, project_dir):
        @hook_telemetry.block_event_decorator("test_hook.py")
        def output_decision(decision, reason, **kwargs):
            return (decision, reason)

        # Allow — no log row.
        output_decision("allow", "ok")
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        assert not log_path.exists()

        # Deny — log row.
        output_decision("deny", "blocked because")
        assert log_path.exists()
        row = json.loads(log_path.read_text().strip())
        assert row["hook_name"] == "test_hook.py"
        assert row["decision_shape"] == "tuple"
        assert row["reason"] == "blocked because"

        # Ask — no extra log row.
        output_decision("ask", "are you sure?")
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_idempotent_double_wrap(self, project_dir):
        """Wrapping a function twice should be a no-op; only one log per deny."""

        @hook_telemetry.block_event_decorator("h.py")
        def output_decision(decision, reason, **kwargs):
            return (decision, reason)

        # Wrap again.
        wrapped_again = hook_telemetry.block_event_decorator("h.py")(
            output_decision
        )
        # Should be the same object (idempotent).
        assert wrapped_again is output_decision

        wrapped_again("deny", "r")
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_decorator_preserves_return_value(self, project_dir):
        @hook_telemetry.block_event_decorator("h.py")
        def output_decision(decision, reason):
            return f"{decision}:{reason}"

        assert output_decision("deny", "r") == "deny:r"
        assert output_decision("allow", "x") == "allow:x"

    def test_kwargs_decision(self, project_dir):
        """Decision passed as kwarg should still be detected."""

        @hook_telemetry.block_event_decorator("h.py")
        def f(decision="allow", reason=""):
            return (decision, reason)

        f(decision="deny", reason="kw block")
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        assert log_path.exists()
        row = json.loads(log_path.read_text().strip())
        assert row["reason"] == "kw block"


# ---------------------------------------------------------------------------
# Recovery shim delegation (back-compat for #970)
# ---------------------------------------------------------------------------


class TestRecoveryShimDelegation:
    def test_shim_delegates_to_log_block_event(self, project_dir):
        """log_block_with_recovery should write to hook-blocks.jsonl now."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            hook_recovery.log_block_with_recovery(
                hook_name="unified_pre_tool.py",
                tool_name="Bash",
                block_reason="WORKFLOW ENFORCEMENT",
                recovery_hint="use /implement",
            )
            # DeprecationWarning emitted.
            assert any(
                issubclass(warning.category, DeprecationWarning) for warning in w
            ), [str(warning.message) for warning in w]

        # Row was written to the new log path.
        log_path = project_dir / hook_telemetry.LOG_FILE_RELATIVE
        assert log_path.exists()
        row = json.loads(log_path.read_text().strip())
        assert row["hook_name"] == "unified_pre_tool.py"
        assert row["decision_shape"] == "legacy_recovery"
        assert "WORKFLOW ENFORCEMENT" in row["reason"]
        assert row["metadata"]["tool_name"] == "Bash"
        assert row["metadata"]["recovery_hint"] == "use /implement"

    def test_shim_never_raises_when_telemetry_unavailable(self, monkeypatch):
        """If hook_telemetry import fails, shim degrades silently."""
        # Force the import inside the shim to fail.
        with patch.dict(sys.modules, {"hook_telemetry": None}):
            # Should not raise.
            hook_recovery.log_block_with_recovery(
                hook_name="h.py",
                tool_name="t",
                block_reason="r",
                recovery_hint="h",
            )


# ---------------------------------------------------------------------------
# can_user_recover() — exemption registry resolution
# ---------------------------------------------------------------------------


class TestCanUserRecover:
    def test_new_registry_path_takes_precedence(self, project_dir, monkeypatch):
        # Ensure plugin-shipped files don't shadow the test fixture.
        monkeypatch.setattr(
            hook_telemetry,
            "_resolve_registry_paths",
            lambda start_dir=None: [
                project_dir / hook_telemetry.EXEMPTION_REGISTRY_PATH,
                project_dir / hook_telemetry.LEGACY_EXEMPTION_PATH,
            ],
        )

        new_path = project_dir / hook_telemetry.EXEMPTION_REGISTRY_PATH
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(
            json.dumps(
                {
                    "exemptions": [
                        {
                            "hook_name": "h.py",
                            "block_reason_contains": "FOO",
                        }
                    ]
                }
            )
        )
        assert hook_telemetry.can_user_recover(
            hook_name="h.py", block_reason="FOO BAR"
        ) is True
        assert hook_telemetry.can_user_recover(
            hook_name="h.py", block_reason="QUX"
        ) is False

    def test_legacy_registry_fallback(self, project_dir, monkeypatch):
        monkeypatch.setattr(
            hook_telemetry,
            "_resolve_registry_paths",
            lambda start_dir=None: [
                project_dir / hook_telemetry.EXEMPTION_REGISTRY_PATH,
                project_dir / hook_telemetry.LEGACY_EXEMPTION_PATH,
            ],
        )
        legacy_path = project_dir / hook_telemetry.LEGACY_EXEMPTION_PATH
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(
            json.dumps(
                {
                    "exemptions": [
                        {
                            "hook_name": "h.py",
                            "block_reason_contains": "LEGACY",
                        }
                    ]
                }
            )
        )
        assert hook_telemetry.can_user_recover(
            hook_name="h.py", block_reason="LEGACY MATCH"
        ) is True

    def test_malformed_registry_safe(self, project_dir, monkeypatch):
        monkeypatch.setattr(
            hook_telemetry,
            "_resolve_registry_paths",
            lambda start_dir=None: [
                project_dir / hook_telemetry.EXEMPTION_REGISTRY_PATH
            ],
        )
        bad_path = project_dir / hook_telemetry.EXEMPTION_REGISTRY_PATH
        bad_path.parent.mkdir(parents=True, exist_ok=True)
        bad_path.write_text("not valid json {{{")
        # No crash, just returns False.
        assert hook_telemetry.can_user_recover(
            hook_name="h.py", block_reason="anything"
        ) is False

    def test_missing_registry_safe(self, project_dir, monkeypatch):
        monkeypatch.setattr(
            hook_telemetry,
            "_resolve_registry_paths",
            lambda start_dir=None: [
                project_dir / "nonexistent" / "exemptions.json"
            ],
        )
        assert hook_telemetry.can_user_recover(
            hook_name="h.py", block_reason="anything"
        ) is False
