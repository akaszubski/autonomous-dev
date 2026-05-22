"""Unit tests for ``hook_timing`` library (Issue #1012, W0).

Library-level coverage of the public API:

- :func:`hook_timing.is_timing_disabled`
- :func:`hook_timing.emit_timing_event`
- :class:`hook_timing.HookTimer`

Schema: ``{ts, hook, dur_ns, decision_shape, schema_version}``.

Mirrors ``tests/unit/lib/test_hook_telemetry.py`` style.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Make hook_timing importable from plugins/autonomous-dev/lib.
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_timing  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_timing_env(monkeypatch):
    """Ensure timing env vars are unset for each test by default."""
    monkeypatch.delenv(hook_timing.DISABLE_ENV_VAR, raising=False)
    monkeypatch.delenv(hook_timing.LOG_DIR_OVERRIDE_ENV_VAR, raising=False)


@pytest.fixture
def home_dir(tmp_path: Path, monkeypatch) -> Path:
    """Redirect $HOME so timing logs go to an isolated tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Some platforms also use these for Path.home() resolution.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def _read_today_log(home: Path) -> list[dict]:
    """Read all rows from the daily-rotated log under ``home``."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log = home / ".claude" / "logs" / f"hook_timings_{today}.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# is_timing_disabled()
# ---------------------------------------------------------------------------


class TestIsTimingDisabled:
    def test_unset_returns_false(self, monkeypatch):
        monkeypatch.delenv(hook_timing.DISABLE_ENV_VAR, raising=False)
        assert hook_timing.is_timing_disabled() is False

    def test_truthy_disables(self, monkeypatch):
        monkeypatch.setenv(hook_timing.DISABLE_ENV_VAR, "1")
        assert hook_timing.is_timing_disabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_falsy_values_keep_enabled(self, monkeypatch, value):
        monkeypatch.setenv(hook_timing.DISABLE_ENV_VAR, value)
        assert hook_timing.is_timing_disabled() is False

    @pytest.mark.parametrize("value", ["true", "yes", "on", "TRUE", "Yes"])
    def test_other_truthy_values_disable(self, monkeypatch, value):
        monkeypatch.setenv(hook_timing.DISABLE_ENV_VAR, value)
        assert hook_timing.is_timing_disabled() is True


# ---------------------------------------------------------------------------
# HookTimer happy path
# ---------------------------------------------------------------------------


class TestHookTimerHappyPath:
    def test_writes_one_event_per_invocation(self, home_dir):
        with hook_timing.HookTimer("test_hook.py"):
            pass
        rows = _read_today_log(home_dir)
        assert len(rows) == 1, f"expected 1 row, got {len(rows)}: {rows}"

    def test_schema_fields_present(self, home_dir):
        with hook_timing.HookTimer("test_hook.py"):
            pass
        row = _read_today_log(home_dir)[0]
        assert set(row.keys()) >= {
            "ts", "hook", "dur_ns", "decision_shape", "schema_version"
        }

    def test_dur_ns_is_positive_int(self, home_dir):
        with hook_timing.HookTimer("test_hook.py"):
            pass
        row = _read_today_log(home_dir)[0]
        assert isinstance(row["dur_ns"], int)
        assert row["dur_ns"] >= 0

    def test_schema_version_is_one(self, home_dir):
        with hook_timing.HookTimer("test_hook.py"):
            pass
        row = _read_today_log(home_dir)[0]
        assert row["schema_version"] == 1

    def test_hook_name_recorded(self, home_dir):
        with hook_timing.HookTimer("auto_format.py"):
            pass
        row = _read_today_log(home_dir)[0]
        assert row["hook"] == "auto_format.py"

    def test_log_dir_override_arg_takes_precedence(self, tmp_path, monkeypatch):
        custom_dir = tmp_path / "custom"
        with hook_timing.HookTimer("test.py", log_dir=custom_dir):
            pass
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log = custom_dir / f"hook_timings_{today}.jsonl"
        assert log.exists()

    def test_env_var_override_directs_to_custom_dir(
        self, tmp_path, monkeypatch, home_dir
    ):
        custom_dir = tmp_path / "via_env"
        monkeypatch.setenv(hook_timing.LOG_DIR_OVERRIDE_ENV_VAR, str(custom_dir))
        with hook_timing.HookTimer("test.py"):
            pass
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log = custom_dir / f"hook_timings_{today}.jsonl"
        assert log.exists()


# ---------------------------------------------------------------------------
# HookTimer exception path
# ---------------------------------------------------------------------------


class TestHookTimerExceptionPath:
    def test_emit_event_even_when_main_raises(self, home_dir):
        with pytest.raises(ValueError):
            with hook_timing.HookTimer("test_hook.py"):
                raise ValueError("boom")
        rows = _read_today_log(home_dir)
        assert len(rows) == 1, "timer must emit even when body raises"

    def test_records_exception_decision_shape(self, home_dir):
        with pytest.raises(RuntimeError):
            with hook_timing.HookTimer("test_hook.py"):
                raise RuntimeError("boom")
        row = _read_today_log(home_dir)[0]
        assert row["decision_shape"] == "exception"

    def test_exception_propagates(self, home_dir):
        # The original exception type and message must propagate.
        with pytest.raises(KeyError, match="missing_key"):
            with hook_timing.HookTimer("test_hook.py"):
                raise KeyError("missing_key")


# ---------------------------------------------------------------------------
# Decision shape semantics
# ---------------------------------------------------------------------------


class TestHookTimerDecisionShape:
    def test_default_decision_shape_is_allow(self, home_dir):
        with hook_timing.HookTimer("test_hook.py"):
            pass
        row = _read_today_log(home_dir)[0]
        assert row["decision_shape"] == "allow"

    def test_set_decision_shape_overrides_default(self, home_dir):
        with hook_timing.HookTimer("test_hook.py") as t:
            t.set_decision_shape("tuple")
        row = _read_today_log(home_dir)[0]
        assert row["decision_shape"] == "tuple"

    def test_set_decision_shape_truncates_long_values(self, home_dir):
        long = "x" * (hook_timing.MAX_DECISION_SHAPE_LENGTH + 100)
        with hook_timing.HookTimer("test_hook.py") as t:
            t.set_decision_shape(long)
        row = _read_today_log(home_dir)[0]
        assert len(row["decision_shape"]) <= hook_timing.MAX_DECISION_SHAPE_LENGTH

    def test_exception_overrides_explicit_shape(self, home_dir):
        # Even when a hook explicitly sets a shape, an exception in the
        # body must record "exception" — the timer reports what actually
        # happened, not what the hook intended to happen.
        with pytest.raises(ValueError):
            with hook_timing.HookTimer("test_hook.py") as t:
                t.set_decision_shape("allow")
                raise ValueError("after-set")
        row = _read_today_log(home_dir)[0]
        assert row["decision_shape"] == "exception"


# ---------------------------------------------------------------------------
# Daily rotation
# ---------------------------------------------------------------------------


class TestHookTimerDailyRotation:
    def test_file_path_contains_todays_utc_date(self, home_dir):
        with hook_timing.HookTimer("test_hook.py"):
            pass
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log = home_dir / ".claude" / "logs" / f"hook_timings_{today}.jsonl"
        assert log.exists(), f"expected daily-rotated log at {log}"


# ---------------------------------------------------------------------------
# Disabled fast-path
# ---------------------------------------------------------------------------


class TestHookTimerDisabledFastPath:
    def test_disabled_writes_no_file(self, home_dir, monkeypatch):
        monkeypatch.setenv(hook_timing.DISABLE_ENV_VAR, "1")
        with hook_timing.HookTimer("test_hook.py"):
            pass
        log_dir = home_dir / ".claude" / "logs"
        files = list(log_dir.glob("hook_timings_*.jsonl")) if log_dir.exists() else []
        assert files == [], f"expected no log files when disabled, got {files}"

    def test_disabled_does_not_raise_on_exception(self, home_dir, monkeypatch):
        monkeypatch.setenv(hook_timing.DISABLE_ENV_VAR, "1")
        with pytest.raises(ValueError):
            with hook_timing.HookTimer("test_hook.py"):
                raise ValueError("boom")


# ---------------------------------------------------------------------------
# Read-only filesystem fallback
# ---------------------------------------------------------------------------


class TestEmitTimingEventReadOnlyFs:
    def test_falls_back_to_stderr_on_oserror(self, monkeypatch, capsys, home_dir):
        # Patch the builtin ``open`` seen by the hook_timing module so the
        # OSError-on-write path is hit. ``hook_timing.emit_timing_event``
        # uses ``open(log_path, "a", ..., opener=...)``; replacing that
        # name in the module's namespace exercises the OSError branch
        # without depending on which underlying syscall pattern is used.
        import builtins

        original_open = builtins.open

        def raise_oserror(path, *args, **kwargs):
            try:
                pstr = os.fspath(path)
            except TypeError:
                pstr = str(path)
            if "hook_timings_" in pstr:
                raise OSError("read-only filesystem")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(hook_timing, "open", raise_oserror, raising=False)

        # Must not raise.
        hook_timing.emit_timing_event(
            hook_name="test.py", dur_ns=12345, decision_shape="allow"
        )

        err = capsys.readouterr().err
        assert "[hook-timing]" in err
        assert "log_write_failed" in err

    def test_falls_back_when_directory_creation_fails(
        self, monkeypatch, capsys, home_dir
    ):
        # Make mkdir fail to simulate a read-only / permission-denied parent.
        def boom(self, *args, **kwargs):
            raise OSError("perm denied")

        monkeypatch.setattr(Path, "mkdir", boom)
        hook_timing.emit_timing_event(
            hook_name="test.py", dur_ns=1, decision_shape="allow"
        )
        err = capsys.readouterr().err
        assert "[hook-timing]" in err


# ---------------------------------------------------------------------------
# Never-raises invariant
# ---------------------------------------------------------------------------


class TestNeverRaises:
    def test_emit_with_unserializable_metadata_safe(self, home_dir):
        # No metadata field in the schema, but pass an object that breaks
        # int() to confirm dur_ns coercion is defensive.
        class WeirdObj:
            def __int__(self):
                raise RuntimeError("can't be int")

        # Must not raise.
        hook_timing.emit_timing_event(
            hook_name="test.py", dur_ns=WeirdObj(), decision_shape="allow"
        )
        rows = _read_today_log(home_dir)
        assert len(rows) == 1
        assert rows[0]["dur_ns"] == 0  # safe coercion fallback

    def test_timer_never_raises_on_emit_failure(
        self, home_dir, monkeypatch, capsys
    ):
        # Force the underlying emit to blow up.
        def boom(**kwargs):
            raise RuntimeError("synthetic emit failure")

        monkeypatch.setattr(hook_timing, "emit_timing_event", boom)

        # The HookTimer must swallow this error rather than propagate.
        with hook_timing.HookTimer("test.py"):
            pass
        # Reaching here without exception is the assertion.

    def test_set_decision_shape_with_non_string(self, home_dir):
        with hook_timing.HookTimer("test.py") as t:
            t.set_decision_shape(12345)  # non-string
        row = _read_today_log(home_dir)[0]
        # Non-strings are coerced via str().
        assert row["decision_shape"] == "12345"


# ---------------------------------------------------------------------------
# Independence from hook_telemetry
# ---------------------------------------------------------------------------


class TestIndependenceFromHookTelemetry:
    def test_hook_timing_does_not_import_hook_telemetry(self):
        """Critical: sibling modules must not be coupled at import time."""
        source = (LIB_DIR / "hook_timing.py").read_text()
        assert "import hook_telemetry" not in source
        assert "from hook_telemetry" not in source
