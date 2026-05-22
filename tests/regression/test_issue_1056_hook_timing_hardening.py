"""Regression tests for Issue #1056 — hook_timing.py hardening (3 MEDIUM findings).

Applies the three security hardening findings carried over from Issue #1012's
security-auditor pass:

1. **hook_name length cap (128 chars)** — Adversarial or malformed hook names
   could produce oversized JSONL log entries or break downstream parsers.
   ``emit_timing_event`` MUST truncate ``hook_name`` to
   :data:`hook_timing.MAX_HOOK_NAME_LENGTH` BEFORE writing.

2. **Log file permissions (0o600)** — On multi-user systems, the timing log
   would otherwise expose internal hook timing data to other users. The file
   MUST be created with owner-only permissions, and re-tightened as a backstop
   for any pre-existing files.

3. **OSError path sanitization** — When OSError fires (disk full, permission
   denied), the raw message frequently embeds the full path involved. That
   message reaches stderr (the read-only-fs fallback) and would otherwise leak
   internal directory structure. The :func:`hook_timing._sanitize_os_error`
   helper MUST replace every absolute path with its basename only.

These regression tests reproduce each finding by exercising the failing
behavior pre-fix and asserting the new guards hold post-fix.
"""

from __future__ import annotations

import builtins
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_timing  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_timing_env(monkeypatch):
    """Strip env vars so each test starts from a deterministic baseline."""
    monkeypatch.delenv(hook_timing.DISABLE_ENV_VAR, raising=False)
    monkeypatch.delenv(hook_timing.LOG_DIR_OVERRIDE_ENV_VAR, raising=False)


@pytest.fixture
def isolated_log_dir(tmp_path: Path) -> Path:
    """Return a tmp directory the timing module will write into."""
    log_dir = tmp_path / "timing_logs"
    return log_dir


def _today_log(log_dir: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return log_dir / f"hook_timings_{today}.jsonl"


def _read_rows(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Finding 1: hook_name length cap (128 chars)
# ---------------------------------------------------------------------------


class TestIssue1056Finding1HookNameLengthCap:
    """The on-disk hook field must never exceed MAX_HOOK_NAME_LENGTH chars."""

    def test_module_constant_is_128(self):
        """MAX_HOOK_NAME_LENGTH is the documented cap (Issue #1056, Finding 1)."""
        assert hook_timing.MAX_HOOK_NAME_LENGTH == 128

    def test_long_hook_name_truncated_in_on_disk_line(self, isolated_log_dir: Path):
        """A 200-char hook_name must be truncated to <=128 in the JSONL row."""
        long_name = "x" * 200
        hook_timing.emit_timing_event(
            hook_name=long_name,
            dur_ns=12345,
            decision_shape="allow",
            log_dir=isolated_log_dir,
        )
        rows = _read_rows(_today_log(isolated_log_dir))
        assert len(rows) == 1, f"expected 1 row, got {rows}"
        assert len(rows[0]["hook"]) <= hook_timing.MAX_HOOK_NAME_LENGTH, (
            f"hook field too long: {len(rows[0]['hook'])} chars "
            f"(expected <= {hook_timing.MAX_HOOK_NAME_LENGTH})"
        )
        # Confirm it is the prefix of the original — truncation, not corruption.
        assert rows[0]["hook"] == long_name[: hook_timing.MAX_HOOK_NAME_LENGTH]

    def test_exact_boundary_not_truncated(self, isolated_log_dir: Path):
        """A name of exactly MAX_HOOK_NAME_LENGTH chars must be preserved."""
        name = "y" * hook_timing.MAX_HOOK_NAME_LENGTH
        hook_timing.emit_timing_event(
            hook_name=name,
            dur_ns=1,
            decision_shape="allow",
            log_dir=isolated_log_dir,
        )
        row = _read_rows(_today_log(isolated_log_dir))[0]
        assert row["hook"] == name
        assert len(row["hook"]) == hook_timing.MAX_HOOK_NAME_LENGTH

    def test_short_hook_name_unchanged(self, isolated_log_dir: Path):
        """A short, normal hook_name must pass through untouched."""
        hook_timing.emit_timing_event(
            hook_name="auto_format.py",
            dur_ns=1,
            decision_shape="allow",
            log_dir=isolated_log_dir,
        )
        row = _read_rows(_today_log(isolated_log_dir))[0]
        assert row["hook"] == "auto_format.py"

    def test_truncation_via_HookTimer_context_manager(self, isolated_log_dir: Path):
        """The 128-char cap must apply when emitted via HookTimer too."""
        long_name = "z" * 500
        with hook_timing.HookTimer(long_name, log_dir=isolated_log_dir):
            pass
        row = _read_rows(_today_log(isolated_log_dir))[0]
        assert len(row["hook"]) <= hook_timing.MAX_HOOK_NAME_LENGTH


# ---------------------------------------------------------------------------
# Finding 2: log file permissions (0o600)
# ---------------------------------------------------------------------------


class TestIssue1056Finding2LogFilePermissions:
    """The timing log file must be owner-only readable/writable (0o600)."""

    def test_module_constant_is_owner_only(self):
        """LOG_FILE_MODE must be 0o600 (Issue #1056, Finding 2)."""
        assert hook_timing.LOG_FILE_MODE == 0o600

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX permission bits do not apply on Windows",
    )
    def test_fresh_log_file_has_0600_perms(self, isolated_log_dir: Path):
        """Newly created log file must have mode 0o600 (owner-only)."""
        hook_timing.emit_timing_event(
            hook_name="t.py",
            dur_ns=1,
            decision_shape="allow",
            log_dir=isolated_log_dir,
        )
        log_path = _today_log(isolated_log_dir)
        assert log_path.exists(), f"log file not created: {log_path}"
        mode = stat.S_IMODE(os.stat(log_path).st_mode)
        assert mode == 0o600, (
            f"expected mode 0o600, got 0o{mode:o} "
            f"(group/other should have no perms)"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX permission bits do not apply on Windows",
    )
    def test_loose_perms_on_existing_file_tightened_to_0600(
        self, isolated_log_dir: Path
    ):
        """Pre-existing file with looser perms must be re-tightened by the backstop."""
        # Seed a log file with intentionally-loose permissions.
        isolated_log_dir.mkdir(parents=True, exist_ok=True)
        log_path = _today_log(isolated_log_dir)
        log_path.write_text("")
        os.chmod(log_path, 0o644)
        assert stat.S_IMODE(os.stat(log_path).st_mode) == 0o644

        # Now emit — the chmod backstop should clamp perms back to 0o600.
        hook_timing.emit_timing_event(
            hook_name="t.py",
            dur_ns=1,
            decision_shape="allow",
            log_dir=isolated_log_dir,
        )
        mode = stat.S_IMODE(os.stat(log_path).st_mode)
        assert mode == 0o600, (
            f"backstop chmod did not tighten existing-file perms: "
            f"expected 0o600, got 0o{mode:o}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX permission bits do not apply on Windows",
    )
    def test_no_group_or_other_read_perms_after_repeated_writes(
        self, isolated_log_dir: Path
    ):
        """Repeated writes must not loosen the perms by accident."""
        for i in range(5):
            hook_timing.emit_timing_event(
                hook_name=f"hook_{i}.py",
                dur_ns=i,
                decision_shape="allow",
                log_dir=isolated_log_dir,
            )
        log_path = _today_log(isolated_log_dir)
        mode = stat.S_IMODE(os.stat(log_path).st_mode)
        # No group or other bits set.
        assert mode & 0o077 == 0, (
            f"group/other perms leaked: mode=0o{mode:o}"
        )


# ---------------------------------------------------------------------------
# Finding 3: OSError path sanitization
# ---------------------------------------------------------------------------


class TestIssue1056Finding3OSErrorPathSanitization:
    """OSError messages reaching stderr must not leak full filesystem paths."""

    def test_sanitizer_replaces_user_path_with_basename(self):
        """A /Users/... path in the message becomes its basename only."""
        full = "/Users/akaszubski/Dev/autonomous-dev/.claude/logs/secret.jsonl"
        exc = OSError(13, "Permission denied", full)
        sanitized = hook_timing._sanitize_os_error(exc)
        assert "secret.jsonl" in sanitized, sanitized
        assert "/Users/akaszubski" not in sanitized, (
            f"full path leaked: {sanitized!r}"
        )
        assert "Dev/autonomous-dev" not in sanitized, (
            f"directory structure leaked: {sanitized!r}"
        )

    def test_sanitizer_handles_tmp_path(self):
        """A /tmp/... path must also be reduced to its basename."""
        full = "/tmp/secret_dir/internal_state.json"
        exc = OSError(28, "No space left on device", full)
        sanitized = hook_timing._sanitize_os_error(exc)
        assert "internal_state.json" in sanitized
        assert "/tmp/secret_dir" not in sanitized, (
            f"tmp directory structure leaked: {sanitized!r}"
        )

    def test_sanitizer_handles_path_with_spaces(self):
        """OSError messages with quoted paths (containing spaces) are sanitized."""
        full = "/Users/akaszubski/My Documents/notes file.txt"
        # The stdlib renders OSError filenames in single-quotes; mirror that.
        exc = OSError(2, "No such file or directory", full)
        sanitized = hook_timing._sanitize_os_error(exc)
        assert "notes file.txt" in sanitized, sanitized
        assert "My Documents" not in sanitized or "/Users/" not in sanitized, (
            f"spaced path not sanitized: {sanitized!r}"
        )
        # The most important assertion: the parent directory must be gone.
        assert "/Users/akaszubski" not in sanitized

    def test_sanitizer_handles_home_path(self):
        """A /home/<user>/... path is treated the same as /Users/<user>/..."""
        full = "/home/alice/.claude/logs/private.jsonl"
        exc = OSError(13, "Permission denied", full)
        sanitized = hook_timing._sanitize_os_error(exc)
        assert "private.jsonl" in sanitized
        assert "/home/alice" not in sanitized, (
            f"home dir leaked: {sanitized!r}"
        )

    def test_sanitizer_handles_multiple_paths_in_message(self):
        """Multiple absolute paths in one message all get reduced."""
        msg = (
            "Failed to rename /Users/alice/old.txt to "
            "/Users/alice/Documents/new.txt — permission denied"
        )
        exc = OSError(msg)
        sanitized = hook_timing._sanitize_os_error(exc)
        assert "/Users/alice" not in sanitized, (
            f"path leaked: {sanitized!r}"
        )
        assert "old.txt" in sanitized
        assert "new.txt" in sanitized

    def test_sanitizer_preserves_non_path_content(self):
        """Errno code, message words, and non-path content survive sanitization."""
        full = "/Users/alice/x.log"
        exc = OSError(13, "Permission denied", full)
        sanitized = hook_timing._sanitize_os_error(exc)
        assert "Permission denied" in sanitized
        assert "13" in sanitized

    def test_oserror_falls_back_to_stderr_with_sanitized_message(
        self, isolated_log_dir: Path, monkeypatch, capsys
    ):
        """End-to-end: forced OSError on write produces sanitized stderr output."""
        secret_path = "/Users/akaszubski/Dev/autonomous-dev/.claude/logs/secret.jsonl"

        # Force the write to fail with an OSError carrying a sensitive path.
        original_open = builtins.open

        def raise_oserror(path, *args, **kwargs):
            try:
                pstr = os.fspath(path)
            except TypeError:
                pstr = str(path)
            if "hook_timings_" in pstr:
                # Simulate an OSError that embeds an internal absolute path.
                raise OSError(13, "Permission denied", secret_path)
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(hook_timing, "open", raise_oserror, raising=False)

        # Must not raise — telemetry is never load-bearing.
        hook_timing.emit_timing_event(
            hook_name="t.py",
            dur_ns=1,
            decision_shape="allow",
            log_dir=isolated_log_dir,
        )

        err = capsys.readouterr().err
        assert "[hook-timing]" in err, "expected stderr fallback prefix"
        assert "log_write_failed" in err
        # The basename MUST be visible (operators need to know which file).
        assert "secret.jsonl" in err, f"basename missing from stderr: {err!r}"
        # The full directory tree MUST NOT be visible.
        assert "/Users/akaszubski" not in err, (
            f"full path leaked to stderr: {err!r}"
        )
        assert "/Users/akaszubski/Dev/autonomous-dev" not in err
