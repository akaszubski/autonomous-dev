"""Universal hook bypass mechanism (Issue #969 / #942-A, #1197).

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
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

ENV_VAR_NAME = "AUTONOMOUS_DEV_BYPASS"
BYPASS_FILE_RELATIVE = Path(".claude") / ".bypass"
LOG_FILE_RELATIVE = Path(".claude") / "logs" / "hook-bypass.jsonl"
STATE_FILE_RELATIVE = Path(".claude") / "state" / "bypass_window.json"
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


def _resolve_state_path(start_dir: Path | None = None) -> Path:
    """Resolve the absolute path to .claude/state/bypass_window.json.
    
    Issue #1197: Used for tracking bypass window state transitions.
    """
    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")
    return start_dir / STATE_FILE_RELATIVE


def _read_window_state(start_dir: Path | None = None) -> Dict[str, Any]:
    """Read bypass window state from disk.
    
    Issue #1197: Returns {"active": bool, "since": iso} or empty dict if missing/corrupt.
    NEVER raises.
    """
    try:
        state_path = _resolve_state_path(start_dir)
        if state_path.exists():
            with state_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception:
        return {}


def _write_window_state(active: bool, start_dir: Path | None = None) -> None:
    """Write bypass window state to disk atomically.
    
    Issue #1197: Uses tempfile + os.replace for atomic writes. NEVER raises.
    """
    try:
        state_path = _resolve_state_path(start_dir)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            "active": active,
            "since": datetime.now(timezone.utc).isoformat()
        }
        
        # Atomic write via tempfile + replace
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=state_path.parent,
            prefix=".bypass_window.",
            suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp_path, state_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception:
        pass


def _emit_window_transition_marker(
    bypass_active: bool, 
    start_dir: Path | None = None
) -> None:
    """Emit window transition markers on state changes.
    
    Issue #1197: Emits [BYPASS-WINDOW-OPEN] or [BYPASS-WINDOW-CLOSE] markers
    to the bypass log when the bypass state transitions. NEVER raises.
    """
    try:
        prev_state = _read_window_state(start_dir)
        prev_active = prev_state.get("active", False)
        
        # Determine if there's a transition
        if bypass_active and not prev_active:
            marker = "BYPASS-WINDOW-OPEN"
        elif not bypass_active and prev_active:
            marker = "BYPASS-WINDOW-CLOSE"
        else:
            # No transition, do nothing
            return
        
        # Write the marker
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "marker": marker
        }
        
        try:
            line = json.dumps(event, ensure_ascii=False)
        except (TypeError, ValueError):
            line = json.dumps({"timestamp": event["timestamp"], "marker": marker})
        
        try:
            log_path = _resolve_log_path(start_dir)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            try:
                sys.stderr.write(f"[hook-bypass] {line} (marker_write_failed)\n")
            except Exception:
                pass
        
        # Update state file
        _write_window_state(bypass_active, start_dir)
        
    except Exception:
        pass


def log_bypass_used(
    *,
    hook_name: str,
    tool_name: str = "",
    reason: str = "env_or_file",
    command_head: str = "",
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
        command_head: Optional truncated Bash command excerpt (Issue #1197).
        start_dir: Project root to anchor the log path. Defaults to cwd.
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hook_name": hook_name,
        "tool_name": tool_name,
        "reason": reason,
    }
    
    # Issue #1197: Include command_head only when non-empty, truncate defensively
    if command_head:
        event["command_head"] = command_head[:200]
    
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
    
    # Issue #1197: After writing the per-event JSONL, emit window transition marker
    _emit_window_transition_marker(bypass_active=True, start_dir=start_dir)


def check_and_log_window_close(start_dir: Path | None = None) -> None:
    """Check if bypass is inactive and emit close marker if needed.

    Issue #1197: Called when bypass is NOT active to detect close transitions.
    This is needed because log_bypass_used is only called when bypass IS active.
    NEVER raises.
    """
    _emit_window_transition_marker(bypass_active=False, start_dir=start_dir)


def warn_global_enforcement_deprecated_once() -> None:
    """Print stderr deprecation notice when AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT is set.

    Issue #1361: After the plan-exit polarity flip, ``AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT``
    is a no-op — enforcement fires in every repo by default. The env var stays parseable
    for backward-compat (setting it does not break anything), but when observed we emit
    a stderr notice so users know to unset it.

    Since each hook invocation is a fresh subprocess, this is effectively "one line per
    tool call" when the var is set — that's the trade-off for zero state complexity, and
    the noise is a self-correcting incentive to unset the var.

    NEVER raises.
    """
    try:
        raw = os.environ.get("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "").strip().lower()
        if raw not in ("1", "true", "yes", "on"):
            return
        print(
            "DEPRECATION: AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT is now the default and no "
            "longer needed. Set AUTONOMOUS_DEV_BYPASS=1 or touch .claude/.bypass to "
            "opt out. Remove the variable to suppress this notice.",
            file=sys.stderr,
        )
    except Exception:
        # Deprecation telemetry must NEVER break the hook.
        pass
