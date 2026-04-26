"""Universal hook bypass mechanism (Issue #969 / #942-A).

Two equivalent bypass signals:

- ``AUTONOMOUS_DEV_BYPASS=1`` (env var, process-scoped)
- ``.claude/.bypass`` (file flag, project-scoped, walks up from cwd)

When either is active, every hook should fall through to allow with a logged
warning. This module is the single source of truth for both signals; every
hook imports ``is_bypassed()`` and (optionally) ``log_bypass_used()``.

Design constraints:

- Telemetry must NEVER raise. A bypass is a transient developer convenience —
  failing telemetry must not block the bypass itself.
- File walk is bounded by ``WALK_DEPTH_LIMIT`` and does not follow symlinks
  (defense against symlink cycles).
- Env var precedence: any "truthy" non-empty value triggers bypass. Falsy
  values (``"0"``, ``"false"``, ``"no"``, ``""``) do NOT trigger.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ENV_VAR_NAME = "AUTONOMOUS_DEV_BYPASS"
BYPASS_FILE_RELATIVE = Path(".claude") / ".bypass"
LOG_FILE_RELATIVE = Path(".claude") / "logs" / "hook-bypass.jsonl"
WALK_DEPTH_LIMIT = 30  # safety cap for parent walk

# Values that count as "explicitly off" when set as the env var.
_FALSY_ENV_VALUES = frozenset({"", "0", "false", "no", "off"})


def _env_var_active() -> bool:
    """Return True iff AUTONOMOUS_DEV_BYPASS env var is set to a truthy value.

    Truthy: any non-empty string NOT in {"0", "false", "no", "off"} (case-insensitive).
    Falsy:  empty string OR explicit falsy value.
    Unset:  False.
    """
    raw = os.environ.get(ENV_VAR_NAME)
    if raw is None:
        return False
    normalized = raw.strip().lower()
    return normalized not in _FALSY_ENV_VALUES


def _flag_file_in_chain(start_dir: Path) -> bool:
    """Return True if ``.claude/.bypass`` exists in ``start_dir`` or any ancestor.

    Walks parent directories up to ``WALK_DEPTH_LIMIT`` levels. Terminates at
    the filesystem root (when ``parent == current``). Does NOT follow symlinks
    on the walk (only ``start_dir`` itself is resolved once).

    Args:
        start_dir: Directory to begin the walk from.

    Returns:
        True if ``.claude/.bypass`` is found anywhere up the chain.
    """
    try:
        # Resolve only the starting directory; subsequent traversal uses
        # ``.parent`` which doesn't follow symlinks (avoids infinite loops).
        current = start_dir.resolve()
    except (OSError, RuntimeError):
        # Fallback if resolve() fails (e.g. broken symlink).
        current = start_dir

    for _ in range(WALK_DEPTH_LIMIT):
        candidate = current / BYPASS_FILE_RELATIVE
        try:
            if candidate.exists():
                return True
        except OSError:
            # Permission errors etc. — keep walking up.
            pass

        parent = current.parent
        if parent == current:
            # Filesystem root reached.
            break
        current = parent

    return False


def is_bypassed(start_dir: Path | None = None) -> bool:
    """Return True iff the universal hook bypass is active.

    Two independent signals; either one is sufficient:

    - ``AUTONOMOUS_DEV_BYPASS`` env var set to a truthy value
    - ``.claude/.bypass`` file exists in ``start_dir`` (or cwd if None) or in
      any ancestor directory up to ``WALK_DEPTH_LIMIT``

    Args:
        start_dir: Directory to start the file walk from. Defaults to cwd.

    Returns:
        True if either signal is active, False otherwise.
    """
    if _env_var_active():
        return True

    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            # cwd may be deleted or inaccessible — env var is the only path.
            return False

    return _flag_file_in_chain(start_dir)


def _resolve_log_path(start_dir: Path | None = None) -> Path:
    """Resolve the absolute path to ``.claude/logs/hook-bypass.jsonl``.

    Uses ``start_dir`` (or cwd) as the project root anchor.
    """
    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")
    return start_dir / LOG_FILE_RELATIVE


def log_bypass_used(
    *,
    hook_name: str,
    tool_name: str = "",
    reason: str = "env_or_file",
    start_dir: Path | None = None,
) -> None:
    """Append one JSONL line recording a bypass event.

    Writes to ``.claude/logs/hook-bypass.jsonl`` relative to ``start_dir`` (or
    cwd). Auto-creates the ``.claude/logs/`` directory if missing. On any
    OSError (read-only FS, permission denied, etc.), falls back to writing the
    JSON line to stderr prefixed with ``[hook-bypass]``.

    This function NEVER raises. Bypass logging must not block the bypass itself.

    Args:
        hook_name: Filename of the hook that observed the bypass.
        tool_name: Optional tool name from the hook's input payload.
        reason: Free-form reason tag. Defaults to ``"env_or_file"``.
        start_dir: Project root to anchor the log path. Defaults to cwd.
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hook_name": hook_name,
        "tool_name": tool_name,
        "reason": reason,
    }
    try:
        line = json.dumps(event, ensure_ascii=False)
    except (TypeError, ValueError):
        # Should never happen with primitive str values, but be defensive.
        line = json.dumps({"timestamp": event["timestamp"], "hook_name": hook_name})

    try:
        log_path = _resolve_log_path(start_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return
    except OSError as exc:
        # Fall back to stderr — never raise.
        try:
            sys.stderr.write(f"[hook-bypass] {line} (log_write_failed: {exc})\n")
        except Exception:
            # Even stderr failed — give up silently.
            pass
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            sys.stderr.write(f"[hook-bypass] {line} (unexpected_error: {exc})\n")
        except Exception:
            pass
