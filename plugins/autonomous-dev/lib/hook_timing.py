"""Per-hook timing telemetry (Issue #1012, W0).

Single canonical surface for recording how long each hook invocation takes.
The library is independent of :mod:`hook_telemetry` — they are sibling
modules writing to different files (``hook-blocks.jsonl`` vs
``hook_timings_YYYY-MM-DD.jsonl``) so the deny-decision telemetry surface
and the per-invocation timing surface can evolve independently.

Each ``HookTimer`` context manager invocation emits one JSONL row to
``~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl``. The schema is stable:
``{ts, hook, dur_ns, decision_shape, schema_version}``.

Design constraints (mirrored from :mod:`hook_telemetry`):

- Telemetry must NEVER raise. A logging or filesystem failure must NEVER
  block the underlying hook decision — the hook decision is the
  load-bearing path, telemetry is best-effort.
- Read-only filesystem fallback writes the JSON line to stderr instead.
- ``HOOK_TIMING_DISABLED=<truthy>`` env var is the rollback switch.
- ``HOOK_TIMING_DIR`` env var redirects the daily log directory (used by
  tests and the baseline capture script).
- The timer uses :func:`time.perf_counter_ns` so durations are recorded
  with monotonic, sub-millisecond precision (PEP 564).

Why home-dir path: hooks fire across many cwds within a single Claude
Code session. Using ``Path.home() / ".claude" / "logs"`` produces a
single user-global stream the report consumer can read without
reconciling per-project log files.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

LOG_DIR_RELATIVE_HOME: Path = Path(".claude") / "logs"
LOG_FILE_PREFIX: str = "hook_timings_"
LOG_FILE_SUFFIX: str = ".jsonl"

DISABLE_ENV_VAR: str = "HOOK_TIMING_DISABLED"
LOG_DIR_OVERRIDE_ENV_VAR: str = "HOOK_TIMING_DIR"

MAX_DECISION_SHAPE_LENGTH: int = 64
SCHEMA_VERSION: int = 1

_FALSY_ENV_VALUES = frozenset({"", "0", "false", "no", "off"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_timing_disabled() -> bool:
    """Return True iff timing telemetry is disabled via env var.

    Truthy: any non-empty string NOT in ``{"0", "false", "no", "off"}``.
    """
    raw = os.environ.get(DISABLE_ENV_VAR)
    if raw is None:
        return False
    return raw.strip().lower() not in _FALSY_ENV_VALUES


def _resolve_log_dir(override: Optional[Path] = None) -> Path:
    """Resolve the directory where timing JSONL files are written.

    Resolution order:

    1. The ``override`` argument (used by tests / baseline capture).
    2. ``HOOK_TIMING_DIR`` environment variable.
    3. ``Path.home() / ".claude" / "logs"`` (the production default).
    """
    if override is not None:
        return override

    env_override = os.environ.get(LOG_DIR_OVERRIDE_ENV_VAR)
    if env_override:
        return Path(env_override)

    return Path.home() / LOG_DIR_RELATIVE_HOME


def _resolve_log_path(override: Optional[Path] = None) -> Path:
    """Resolve the daily-rotated JSONL path for today's UTC date."""
    log_dir = _resolve_log_dir(override)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return log_dir / f"{LOG_FILE_PREFIX}{today}{LOG_FILE_SUFFIX}"


def _normalize_decision_shape(shape: str) -> str:
    """Coerce ``shape`` to a short, well-formed ASCII string.

    - Non-strings are coerced via ``str(...)``.
    - Strings longer than :data:`MAX_DECISION_SHAPE_LENGTH` are truncated.
    - On any failure, ``"unknown"`` is returned.
    """
    try:
        s = str(shape)
    except Exception:
        return "unknown"
    if len(s) > MAX_DECISION_SHAPE_LENGTH:
        s = s[:MAX_DECISION_SHAPE_LENGTH]
    return s


def emit_timing_event(
    *,
    hook_name: str,
    dur_ns: int,
    decision_shape: str = "unknown",
    log_dir: Optional[Path] = None,
) -> None:
    """Append one JSONL row for a single hook invocation.

    Writes to ``<log_dir>/hook_timings_YYYY-MM-DD.jsonl`` with the schema
    ``{ts, hook, dur_ns, decision_shape, schema_version}``. Auto-creates
    the directory if missing. On any OSError (read-only FS, permission
    denied, JSON-serialization error), falls back to writing the JSON
    line to stderr prefixed with ``[hook-timing]``.

    This function NEVER raises. Telemetry must never block hooks.

    Args:
        hook_name: Filename of the hook (e.g. ``"unified_pre_tool.py"``).
        dur_ns: Duration of the hook invocation in nanoseconds.
        decision_shape: One of ``"allow"``, ``"tuple"``, ``"dict"``,
            ``"exit2"``, ``"legacy_recovery"``, ``"mode_skip"``, or
            ``"exception"``. Unknown values are logged as-is.
        log_dir: Optional directory override. Falls back to the
            ``HOOK_TIMING_DIR`` env var, then to
            ``~/.claude/logs``.
    """
    if is_timing_disabled():
        return

    try:
        safe_hook = str(hook_name) if hook_name is not None else "unknown"
    except Exception:
        safe_hook = "unknown"

    try:
        safe_dur = int(dur_ns)
    except Exception:
        safe_dur = 0

    safe_shape = _normalize_decision_shape(decision_shape)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hook": safe_hook,
        "dur_ns": safe_dur,
        "decision_shape": safe_shape,
        "schema_version": SCHEMA_VERSION,
    }

    try:
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        # Last-resort serialization with stringified values.
        try:
            line = json.dumps(
                {
                    "ts": event["ts"],
                    "hook": safe_hook,
                    "dur_ns": safe_dur,
                    "decision_shape": safe_shape,
                    "schema_version": SCHEMA_VERSION,
                }
            )
        except Exception:
            return

    try:
        log_path = _resolve_log_path(log_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return
    except OSError as exc:
        try:
            sys.stderr.write(f"[hook-timing] {line} (log_write_failed: {exc})\n")
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            sys.stderr.write(f"[hook-timing] {line} (unexpected_error: {exc})\n")
        except Exception:
            pass


class HookTimer:
    """Context manager that emits one timing event on ``__exit__``.

    Default ``decision_shape`` is ``"allow"``. Hooks that produce a
    non-allow outcome should call :meth:`set_decision_shape` before
    leaving the ``with`` block. If the hook raises an exception, the
    timer records ``decision_shape="exception"`` and the exception
    propagates normally — the timer NEVER swallows errors.

    Example:

    >>> with HookTimer("auto_format.py") as timer:
    ...     timer.set_decision_shape("allow")
    ...     # hook body

    Honors the :envvar:`HOOK_TIMING_DISABLED` rollback switch and the
    :envvar:`HOOK_TIMING_DIR` directory override.
    """

    def __init__(
        self,
        hook_name: str,
        *,
        log_dir: Optional[Path] = None,
    ) -> None:
        self.hook_name = hook_name
        self._log_dir = log_dir
        self._decision_shape: str = "allow"
        self._explicitly_set: bool = False
        self._start_ns: int = 0
        self._disabled: bool = False

    def __enter__(self) -> "HookTimer":
        # Fast-path: short-circuit when disabled. ``__exit__`` becomes a no-op.
        if is_timing_disabled():
            self._disabled = True
            return self
        self._start_ns = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # ``return None`` → propagate any exception unchanged.
        if self._disabled:
            return None

        try:
            dur_ns = time.perf_counter_ns() - self._start_ns
            shape = "exception" if exc_type is not None else self._decision_shape
            emit_timing_event(
                hook_name=self.hook_name,
                dur_ns=dur_ns,
                decision_shape=shape,
                log_dir=self._log_dir,
            )
        except Exception:
            # Last-resort guard: a bug in emit_timing_event must not block
            # the host hook. ``emit_timing_event`` already swallows errors
            # internally; this is defense in depth.
            pass
        # Returning None / falsy → exception (if any) propagates.
        return None

    def set_decision_shape(self, shape: str) -> None:
        """Record the outcome shape for this invocation.

        Acceptable values mirror :data:`hook_telemetry.VALID_DECISION_SHAPES`
        plus ``"allow"``. Unknown strings are logged as-is — readers MUST
        treat the field as opaque.
        """
        self._decision_shape = _normalize_decision_shape(shape)
        self._explicitly_set = True
