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
import re
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
MAX_HOOK_NAME_LENGTH: int = 128
SCHEMA_VERSION: int = 1

# Owner-only permissions for the timing log file (Issue #1056, Finding 2).
# Multi-user systems must not expose internal hook timing data to other users.
LOG_FILE_MODE: int = 0o600

_FALSY_ENV_VALUES = frozenset({"", "0", "false", "no", "off"})

# Path-detection regex used by :func:`_sanitize_os_error` (Issue #1056,
# Finding 3). Matches POSIX absolute paths (``/...``) AND optionally
# quoted variants such as ``'/foo/bar'`` or ``"/foo/bar"``. The match is
# intentionally greedy on non-whitespace, non-quote characters so paths
# containing spaces (which OSError strings typically wrap in quotes) are
# still captured by the quoted-path branch.
_ABS_PATH_PATTERN = re.compile(
    r"""(?P<quoted>['"])(?P<qpath>/[^'"\n]+)(?P=quoted)|(?P<path>/[^\s'"]+)""",
    re.VERBOSE,
)


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


def _sanitize_os_error(exc: BaseException) -> str:
    """Return a stringified OSError with full paths replaced by basenames.

    OSError messages from the standard library frequently embed absolute
    paths (``[Errno 13] Permission denied: '/Users/alice/.claude/logs/x'``).
    Surfacing those raw to stderr leaks internal directory structure to
    anyone reading stderr — including subordinate processes, log
    aggregators, and CI artifacts. This helper rewrites every absolute
    path in the message to just its basename via :class:`pathlib.PurePosixPath`,
    so the failing filename is still visible without revealing the
    surrounding directory tree.

    Handles paths with spaces (when quoted in the message), paths under
    ``/Users/``, ``/tmp/``, ``/home/``, and arbitrary depths. The
    ``filename`` and ``filename2`` attributes (which OSError carries
    separately from the message) are also substituted out of the rendered
    string when they appear, so a custom ``__str__`` that includes them
    is still sanitized.

    Args:
        exc: An OSError (or any BaseException — non-OSError input is
            rendered with ``str()`` and run through the same substitution).

    Returns:
        A safe-to-log string with only basename references.
    """
    try:
        raw = str(exc)
    except Exception:
        return "<unrepresentable error>"

    def _replace(match: "re.Match[str]") -> str:
        qpath = match.group("qpath")
        path = match.group("path")
        full = qpath if qpath is not None else path
        try:
            base = Path(full).name or full
        except Exception:
            base = full
        if qpath is not None:
            quote = match.group("quoted")
            return f"{quote}{base}{quote}"
        return base

    sanitized = _ABS_PATH_PATTERN.sub(_replace, raw)

    # OSError carries filename/filename2 attributes; some Python builds
    # render them outside the main message in subclasses. Substitute any
    # surviving full-path mentions of those attributes too.
    for attr in ("filename", "filename2"):
        try:
            value = getattr(exc, attr, None)
        except Exception:
            value = None
        if isinstance(value, (str, bytes, os.PathLike)):
            try:
                full = os.fspath(value)
            except (TypeError, ValueError):
                continue
            if isinstance(full, bytes):
                try:
                    full = full.decode("utf-8", errors="replace")
                except Exception:
                    continue
            if full and full.startswith("/") and full in sanitized:
                try:
                    base = Path(full).name or full
                except Exception:
                    base = full
                sanitized = sanitized.replace(full, base)

    return sanitized


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

    # Issue #1056, Finding 1: cap hook_name length BEFORE it reaches the
    # log file. Adversarial or malformed hook names could otherwise
    # produce oversized JSONL lines or break downstream parsers that
    # assume bounded fields. The cap is applied here (write-path) rather
    # than at the call site so every code path that emits a row is
    # protected by a single guard.
    if len(safe_hook) > MAX_HOOK_NAME_LENGTH:
        safe_hook = safe_hook[:MAX_HOOK_NAME_LENGTH]

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

        # Issue #1056, Finding 2: enforce owner-only (0o600) permissions
        # on the timing log. The opener sets the mode at file-creation
        # time so newly created files are tight from the first byte.
        # ``os.chmod`` is then re-applied as a backstop for files that
        # already existed (legacy logs created before this guard landed
        # would otherwise retain their old, possibly looser, perms).
        def _secure_opener(path: str, flags: int) -> int:
            return os.open(path, flags, LOG_FILE_MODE)

        with open(log_path, "a", encoding="utf-8", opener=_secure_opener) as fh:
            fh.write(line + "\n")

        # Backstop: tighten perms in case the file pre-existed with
        # looser permissions. Swallow chmod failures — telemetry must
        # never block the host hook over a perm-tightening attempt.
        try:
            os.chmod(log_path, LOG_FILE_MODE)
        except OSError:
            pass

        return
    except OSError as exc:
        # Issue #1056, Finding 3: sanitize the error message so absolute
        # paths (which OSError typically embeds verbatim) do not leak
        # internal directory structure to stderr.
        safe_exc = _sanitize_os_error(exc)
        try:
            sys.stderr.write(f"[hook-timing] {line} (log_write_failed: {safe_exc})\n")
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            safe_exc = _sanitize_os_error(exc)
        except Exception:
            safe_exc = "<unrepresentable error>"
        try:
            sys.stderr.write(f"[hook-timing] {line} (unexpected_error: {safe_exc})\n")
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
