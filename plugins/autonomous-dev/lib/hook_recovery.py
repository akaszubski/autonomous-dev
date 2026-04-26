"""Hook recovery telemetry and stale-state cleanup (Issue #970).

Two complementary capabilities for the central hook enforcement gates:

- **Recovery telemetry**: when a hook decides to ``deny`` a tool call, it can
  emit a structured JSONL row recording the block reason and a recovery hint.
  The user can read ``.claude/logs/hook-recovery.jsonl`` to find an actionable
  next step rather than being silently wedged.
- **Stale-state cleanup**: long-running pipelines occasionally leave sentinel
  files behind that belong to a session that has since exited. ``clear_stale_state``
  removes such files when their owning session no longer matches the current one.

Design constraints (mirrored from ``hook_bypass.py``):

- Telemetry must NEVER raise. A logging or filesystem failure must NEVER block
  the underlying hook decision — the hook decision is the load-bearing path.
- Read-only filesystem fallback writes the JSON line to stderr instead.
- ``HOOK_RECOVERY_DISABLED=<truthy>`` env var disables both log writes and
  state clears (telemetry-only safety valve).
- Exemption registry is parsed defensively — malformed JSON is treated as
  "no exemptions" (fail-closed for the recovery-required check).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

LOG_FILE_RELATIVE: Path = Path(".claude") / "logs" / "hook-recovery.jsonl"
EXEMPTION_REGISTRY_PATH: Path = (
    Path(".claude") / "config" / "hook_recovery_exemptions.json"
)
DISABLE_ENV_VAR: str = "HOOK_RECOVERY_DISABLED"

_FALSY_ENV_VALUES = frozenset({"", "0", "false", "no", "off"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_recovery_disabled() -> bool:
    """Return True iff ``HOOK_RECOVERY_DISABLED`` env var is truthy.

    When True, :func:`log_block_with_recovery` and :func:`clear_stale_state`
    become no-ops. Used as a safety valve to roll back recovery telemetry
    without redeploying.

    Truthy: any non-empty string NOT in ``{"0", "false", "no", "off"}``.
    """
    raw = os.environ.get(DISABLE_ENV_VAR)
    if raw is None:
        return False
    return raw.strip().lower() not in _FALSY_ENV_VALUES


def can_user_recover(*, hook_name: str, block_reason: str) -> bool:
    """Return True if a documented recovery path exists for this block.

    Reads the exemption registry at ``.claude/config/hook_recovery_exemptions.json``.
    A block is considered recoverable when an exemption matches both
    ``hook_name`` and ``block_reason`` (substring match on reason).

    Args:
        hook_name: Filename of the hook that is about to deny.
        block_reason: The reason string the hook would output.

    Returns:
        True iff a matching exemption is found in the registry. False on any
        parse error, missing file, or no match.
    """
    try:
        registry_path = _resolve_registry_path()
        if not registry_path.exists():
            return False
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError, OSError):
            return False
        exemptions = data.get("exemptions") if isinstance(data, dict) else None
        if not isinstance(exemptions, list):
            return False
        for entry in exemptions:
            if not isinstance(entry, dict):
                continue
            if entry.get("hook_name") != hook_name:
                continue
            reason_match = entry.get("block_reason_contains", "")
            if not isinstance(reason_match, str):
                continue
            if reason_match and reason_match in block_reason:
                return True
        return False
    except Exception:
        # NEVER raise — recovery checks must not break hook decisions.
        return False


def log_block_with_recovery(
    *,
    hook_name: str,
    tool_name: str,
    block_reason: str,
    recovery_hint: str,
    session_id: Optional[str] = None,
    start_dir: Optional[Path] = None,
) -> None:
    """Append one JSONL line recording a hook block + recovery hint.

    Writes to ``.claude/logs/hook-recovery.jsonl`` relative to ``start_dir``
    (or cwd). Auto-creates the ``.claude/logs/`` directory if missing. On any
    OSError (read-only FS, permission denied), falls back to writing the JSON
    line to stderr prefixed with ``[hook-recovery]``.

    This function NEVER raises. Telemetry must never block hook decisions.

    Args:
        hook_name: Filename of the hook emitting the block.
        tool_name: Tool whose invocation was denied.
        block_reason: Human-readable reason the hook denied the call.
        recovery_hint: Actionable next step the user can take to unblock.
        session_id: Optional session id (defaults to ``CLAUDE_SESSION_ID``).
        start_dir: Project root anchor. Defaults to cwd.
    """
    if is_recovery_disabled():
        return

    if session_id is None:
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")

    event: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hook_name": hook_name,
        "tool_name": tool_name,
        "block_reason": block_reason,
        "recovery_hint": recovery_hint,
        "session_id": session_id,
    }
    try:
        line = json.dumps(event, ensure_ascii=False)
    except (TypeError, ValueError):
        line = json.dumps(
            {"timestamp": event["timestamp"], "hook_name": hook_name}
        )

    try:
        log_path = _resolve_log_path(start_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return
    except OSError as exc:
        try:
            sys.stderr.write(
                f"[hook-recovery] {line} (log_write_failed: {exc})\n"
            )
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            sys.stderr.write(
                f"[hook-recovery] {line} (unexpected_error: {exc})\n"
            )
        except Exception:
            pass


def clear_stale_state(
    state_path: Path, *, owning_session_id: Optional[str] = None
) -> bool:
    """Remove ``state_path`` iff it is stale or owned by a different session.

    A state file is considered "stale" when:

    - It cannot be parsed as JSON (corrupt), OR
    - Its ``session_id`` field does not match ``owning_session_id``.

    A state file is considered "owned" (and kept) when its ``session_id``
    matches ``owning_session_id``. Missing ``owning_session_id`` falls back
    to ``CLAUDE_SESSION_ID``; if neither is available, the file is left in
    place (we don't know who owns it).

    Args:
        state_path: Absolute path to the state file to inspect.
        owning_session_id: Expected owner's session id. Defaults to
            ``CLAUDE_SESSION_ID`` env var.

    Returns:
        True iff the file was removed, False otherwise.
    """
    if is_recovery_disabled():
        return False

    try:
        if not state_path.exists():
            return False

        if owning_session_id is None:
            owning_session_id = os.environ.get("CLAUDE_SESSION_ID", "")

        if not owning_session_id:
            # No way to determine ownership — leave the file alone.
            return False

        # Treat parse failures as "stale" so corrupt files get cleaned up.
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError, OSError):
            try:
                state_path.unlink(missing_ok=True)
                return True
            except OSError:
                return False

        owner = data.get("session_id") if isinstance(data, dict) else None
        if owner == owning_session_id:
            return False  # Owned by current session — keep.

        try:
            state_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    except Exception:
        # NEVER raise.
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_log_path(start_dir: Optional[Path] = None) -> Path:
    """Resolve absolute path to ``.claude/logs/hook-recovery.jsonl``."""
    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")
    return start_dir / LOG_FILE_RELATIVE


def _resolve_registry_path(start_dir: Optional[Path] = None) -> Path:
    """Resolve absolute path to the exemption registry JSON file.

    First checks the in-repo plugins path (development), then falls back to
    the cwd-relative ``.claude/config/`` path.
    """
    # Prefer the source-of-truth file shipped with the plugin if it exists,
    # falling back to a project-local override in cwd.
    here = Path(__file__).resolve().parent
    plugin_config = here.parent / "config" / "hook_recovery_exemptions.json"
    if plugin_config.exists():
        return plugin_config

    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")
    return start_dir / EXEMPTION_REGISTRY_PATH
