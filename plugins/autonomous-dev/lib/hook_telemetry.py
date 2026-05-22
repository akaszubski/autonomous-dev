"""Unified hook block telemetry (Issue #972, #942-D capstone).

Single canonical surface for recording every "deny" decision a hook makes,
across all three deny shapes used in the harness:

- ``("deny", reason)`` tuple shape (used by ``unified_pre_tool.py`` via
  ``output_decision``).
- ``{"decision": "block", ...}`` dict shape (used by
  ``unified_prompt_validator.py``).
- ``sys.exit(2)`` shape (used by ``enforce_orchestrator.py`` and similar
  pre-commit hooks).

Each block emits one JSONL row to ``.claude/logs/hook-blocks.jsonl``. The
schema is stable: ``{ts, hook_name, decision_shape, reason, metadata,
session_id, cwd}``. The ``scripts/hook_block_summary.py`` triage script
reads this file (and the legacy ``hook-recovery.jsonl`` for one release
cycle) to produce per-hook block counts, category breakdowns, and
bypass-usage rates without grepping individual session transcripts.

Design constraints (mirrored from ``hook_bypass.py`` and ``hook_recovery.py``):

- Telemetry must NEVER raise. A logging or filesystem failure must NEVER
  block the underlying hook decision — the hook decision is the load-bearing
  path, telemetry is best-effort.
- Read-only filesystem fallback writes the JSON line to stderr instead.
- ``HOOK_TELEMETRY_DISABLED=<truthy>`` env var is the rollback switch.
- ``HOOK_RECOVERY_DISABLED=<truthy>`` is honored as a deprecation alias so
  existing rollback procedures keep working.
- The exemption registry is parsed defensively — malformed JSON is treated
  as "no exemptions".

Note on rotation: rotation is deferred to a follow-up. Line-level integrity
under concurrent writes is guaranteed via ``fcntl.flock(LOCK_EX)`` (POSIX
advisory lock) wrapped around the ``write`` call. This works for events of
any size — the previous reliance on ``PIPE_BUF`` atomic-append guarantees
(4096B Linux, 512B macOS) is too small for ``MAX_REASON_LENGTH=8000``
events and could produce torn lines on macOS even for typical events
(Issue #992). The lock adds ~1ms per write — negligible relative to hook
runtime — and preserves the 8000B reason headroom that triage relies on
for debugging context. On non-POSIX platforms (e.g. Windows), ``fcntl`` is
unavailable and we fall back to the bare append; concurrent writes on
Windows are vanishingly rare for this telemetry surface and acceptable as
a known limitation.
"""

from __future__ import annotations

import functools
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# ``fcntl`` is POSIX-only. On Windows it is absent; we degrade gracefully
# to a bare append (no advisory locking). The advisory lock guards against
# torn JSONL lines when multiple processes concurrently append events
# larger than PIPE_BUF (4096B Linux, 512B macOS) — see Issue #992.
try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

LOG_FILE_RELATIVE: Path = Path(".claude") / "logs" / "hook-blocks.jsonl"
EXEMPTION_REGISTRY_PATH: Path = (
    Path(".claude") / "config" / "hook_telemetry_exemptions.json"
)
LEGACY_EXEMPTION_PATH: Path = (
    Path(".claude") / "config" / "hook_recovery_exemptions.json"
)

DISABLE_ENV_VAR: str = "HOOK_TELEMETRY_DISABLED"
LEGACY_DISABLE_ENV_VAR: str = "HOOK_RECOVERY_DISABLED"

MAX_REASON_LENGTH: int = 8000

VALID_DECISION_SHAPES = frozenset(
    {"tuple", "dict", "exit2", "legacy_recovery", "mode_skip", "allow"}
)
# ``mode_skip`` (Issue #999, Phase E) is emitted ONLY on the skip path of the
# session-mode enforcement gate. The enforce path stays silent — preserving
# the pre-Phase-E baseline where non-block hook outcomes produced no
# telemetry. ``mode_skip`` is intentionally NOT paired with a ``mode_enforce``
# shape: a single label ("we relaxed a check") is what triage cares about.
# ``allow`` (Issue #1012, W0) is emitted by ``hook_timing.HookTimer`` for
# every hook invocation that did NOT raise an exception and did NOT set a
# more specific decision shape. The constant is documentation-only — this
# module's ``log_block_event`` does not validate against the frozenset.

_FALSY_ENV_VALUES = frozenset({"", "0", "false", "no", "off"})

# Module-level guard so the legacy-env-var deprecation warning fires at most
# once per process. The hook decision path runs many times per session, and
# an unbounded warning stream would quickly drown the activity log.
_legacy_env_warned: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_telemetry_disabled() -> bool:
    """Return True iff the telemetry surface is disabled via env var.

    Checks ``HOOK_TELEMETRY_DISABLED`` first; if unset, falls back to
    ``HOOK_RECOVERY_DISABLED`` (the rollback switch shipped with #970).
    The legacy alias emits a single stderr warning per process so users
    know to update to the new variable name.

    Truthy: any non-empty string NOT in ``{"0", "false", "no", "off"}``.
    """
    raw = os.environ.get(DISABLE_ENV_VAR)
    if raw is not None:
        return raw.strip().lower() not in _FALSY_ENV_VALUES

    legacy = os.environ.get(LEGACY_DISABLE_ENV_VAR)
    if legacy is None:
        return False

    if legacy.strip().lower() in _FALSY_ENV_VALUES:
        return False

    global _legacy_env_warned
    if not _legacy_env_warned:
        try:
            sys.stderr.write(
                "[hook-telemetry] DEPRECATED: HOOK_RECOVERY_DISABLED is "
                "honored as an alias for HOOK_TELEMETRY_DISABLED; please "
                "update.\n"
            )
        except Exception:
            pass
        _legacy_env_warned = True
    return True


def log_block_event(
    *,
    hook_name: str,
    decision_shape: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    start_dir: Optional[Path] = None,
) -> None:
    """Append one JSONL line recording a hook deny decision.

    Writes to ``.claude/logs/hook-blocks.jsonl`` relative to ``start_dir``
    (or cwd). Auto-creates the ``.claude/logs/`` directory if missing. On
    any OSError (read-only FS, permission denied), falls back to writing
    the JSON line to stderr prefixed with ``[hook-telemetry]``.

    This function NEVER raises. Telemetry must never block hook decisions.

    Args:
        hook_name: Filename of the hook emitting the block (e.g.
            ``"unified_pre_tool.py"``).
        decision_shape: One of ``"tuple"``, ``"dict"``, ``"exit2"``,
            ``"legacy_recovery"`` (the last is for the back-compat shim),
            or ``"mode_skip"``. ``"allow"`` is emitted by
            ``hook_timing.HookTimer`` (sibling module, separate file).
            Unknown values are logged as-is — readers MUST treat the field
            as opaque.
        reason: Human-readable reason the hook denied. Capped at
            ``MAX_REASON_LENGTH`` characters.
        metadata: Optional structured metadata (tool_name, recovery_hint,
            etc). Must be JSON-serialisable; serialisation failure
            downgrades to ``{}``.
        session_id: Optional session id (defaults to ``CLAUDE_SESSION_ID``).
        start_dir: Project root anchor. Defaults to cwd.
    """
    if is_telemetry_disabled():
        return

    if session_id is None:
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")

    safe_reason = ""
    try:
        safe_reason = str(reason)[:MAX_REASON_LENGTH]
    except Exception:
        safe_reason = ""

    safe_metadata: Dict[str, Any] = {}
    if metadata is not None:
        try:
            # Round-trip through JSON to drop non-serialisable values.
            safe_metadata = json.loads(json.dumps(metadata, default=str))
            if not isinstance(safe_metadata, dict):
                safe_metadata = {}
        except Exception:
            safe_metadata = {}

    try:
        cwd_str = str(Path.cwd())
    except (OSError, FileNotFoundError):
        cwd_str = ""

    event: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hook_name": hook_name,
        "decision_shape": decision_shape,
        "reason": safe_reason,
        "metadata": safe_metadata,
        "session_id": session_id,
        "cwd": cwd_str,
    }

    try:
        line = json.dumps(event, ensure_ascii=False)
    except (TypeError, ValueError):
        line = json.dumps(
            {"ts": event["ts"], "hook_name": hook_name, "reason": safe_reason}
        )

    try:
        log_path = _resolve_log_path(start_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            # Hold an exclusive advisory lock for the duration of the
            # write. On POSIX this prevents concurrent appenders from
            # interleaving bytes within a single line — required because
            # ``MAX_REASON_LENGTH=8000`` exceeds PIPE_BUF on every
            # mainstream platform (Issue #992). On non-POSIX (fcntl=None)
            # we fall through to a bare append; this is the same
            # behavior as before the fix and is acceptable because
            # concurrent writes on Windows are not a realistic threat
            # for this telemetry surface.
            if fcntl is not None:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                except OSError:
                    # NFS or unsupported FS may refuse flock; degrade
                    # to bare append rather than raise. Telemetry must
                    # never break the hook decision path.
                    pass
                try:
                    fh.write(line + "\n")
                finally:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
            else:
                fh.write(line + "\n")
        return
    except OSError as exc:
        try:
            sys.stderr.write(
                f"[hook-telemetry] {line} (log_write_failed: {exc})\n"
            )
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            sys.stderr.write(
                f"[hook-telemetry] {line} (unexpected_error: {exc})\n"
            )
        except Exception:
            pass


def block_event_decorator(hook_name: str) -> Callable:
    """Decorator factory that emits a telemetry row on deny decisions.

    Wraps a function whose first positional argument is the decision string
    (typically ``"allow"``, ``"deny"``, or ``"ask"``). When the decision is
    ``"deny"``, a ``log_block_event`` row is appended with ``decision_shape
    = "tuple"`` and the second positional argument used as ``reason``.

    The decorator is idempotent: re-wrapping a function that has already
    been wrapped is a no-op. This protects against accidental double-decor
    during defensive imports.

    Example::

        @block_event_decorator("unified_pre_tool.py")
        def output_decision(decision, reason, *, system_message=""):
            ...

    Args:
        hook_name: Filename of the hook to attribute blocks to.

    Returns:
        A decorator that wraps a function with telemetry emission.
    """

    def decorator(fn: Callable) -> Callable:
        if getattr(fn, "_telemetry_wrapped", False):
            return fn

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            decision = args[0] if args else kwargs.get("decision", "")
            result = fn(*args, **kwargs)
            try:
                if decision == "deny":
                    if len(args) > 1:
                        reason = args[1]
                    else:
                        reason = kwargs.get("reason", "")
                    log_block_event(
                        hook_name=hook_name,
                        decision_shape="tuple",
                        reason=str(reason),
                    )
            except Exception:
                # NEVER raise from the wrapper — telemetry must not break
                # the underlying hook decision path.
                pass
            return result

        wrapper._telemetry_wrapped = True  # type: ignore[attr-defined]
        return wrapper

    return decorator


def can_user_recover(*, hook_name: str, block_reason: str) -> bool:
    """Return True if a documented recovery path exists for this block.

    Reads the exemption registry. Tries the new path
    ``.claude/config/hook_telemetry_exemptions.json`` first, falls back to
    the legacy ``.claude/config/hook_recovery_exemptions.json`` shipped
    with #970. Both share the same schema: ``{exemptions: [{hook_name,
    block_reason_contains}]}``.

    Args:
        hook_name: Filename of the hook that is about to deny.
        block_reason: The reason string the hook would output.

    Returns:
        True iff a matching exemption is found in either registry. False
        on any parse error, missing file, or no match.
    """
    try:
        for registry_path in _resolve_registry_paths():
            if not registry_path.exists():
                continue
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError, OSError):
                continue
            exemptions = data.get("exemptions") if isinstance(data, dict) else None
            if not isinstance(exemptions, list):
                continue
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_log_path(start_dir: Optional[Path] = None) -> Path:
    """Resolve absolute path to ``.claude/logs/hook-blocks.jsonl``."""
    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")
    return start_dir / LOG_FILE_RELATIVE


def _resolve_registry_paths(start_dir: Optional[Path] = None) -> list[Path]:
    """Resolve registry candidates in priority order: new, then legacy.

    First checks the in-repo plugins paths (development), then falls back
    to the cwd-relative ``.claude/config/`` paths.
    """
    here = Path(__file__).resolve().parent
    plugin_new = here.parent / "config" / "hook_telemetry_exemptions.json"
    plugin_legacy = here.parent / "config" / "hook_recovery_exemptions.json"

    if start_dir is None:
        try:
            start_dir = Path.cwd()
        except (OSError, FileNotFoundError):
            start_dir = Path(".")

    candidates: list[Path] = []
    if plugin_new.exists():
        candidates.append(plugin_new)
    candidates.append(start_dir / EXEMPTION_REGISTRY_PATH)
    if plugin_legacy.exists():
        candidates.append(plugin_legacy)
    candidates.append(start_dir / LEGACY_EXEMPTION_PATH)
    return candidates
