"""Hard-floor hook registry — explicit always-on enforcement list.

This module provides a read-only registry of hooks (and specific hook functions)
that MUST always fire regardless of session mode. The registry exists so that
session-mode logic can never accidentally disable catastrophe-prevention hooks.

Design (dual-source with safe fallback)
---------------------------------------
- Authoritative source: ``plugins/autonomous-dev/config/hard_floor_hooks.json``
  is read at runtime via :func:`_load_config`. The plugin directory is already
  a trust boundary (Claude Code installs the plugin contents as a unit), so a
  simple relative-to-this-file path resolution is appropriate.
- Fallback: if the JSON file is missing, malformed, or unreadable, the lookup
  functions fall back to module-level constants
  (:data:`_FALLBACK_HARD_FLOOR_HOOKS`,
  :data:`_FALLBACK_OBSERVABILITY_HOOKS`). The fallback returns ``True`` ONLY
  for entries that are explicitly listed in the constant — it does NOT
  over-block by treating every hook as a hard floor.
- No caching: every call re-reads the JSON. Hook invocation rates are low
  (low double digits per second at most), and JSON parse cost on a ~1 KB file
  is negligible. Caching would add invalidation complexity for no measurable
  benefit.

Phase status (Issue #997)
-------------------------
This is Phase C — the registry exists, but no production hook consumes it yet.
Phase D (a separate issue) wires session-mode logic to call :func:`is_hard_floor`
before considering any disable/skip path.

Public API
----------
- :func:`is_hard_floor` — returns True if a (hook, function) pair is hard-floor.
- :func:`get_observability_hooks` — returns the always-run observability list.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["is_hard_floor", "get_observability_hooks"]


# Fallback constants used when the JSON config cannot be read or parsed.
# These MUST stay in sync with config/hard_floor_hooks.json — drift is asserted
# by ``test_fallback_constant_matches_shipped_json`` in the test suite.
_FALLBACK_HARD_FLOOR_HOOKS: tuple[tuple[str, str | None], ...] = (
    ("security_scan.py", None),
    ("unified_pre_tool.py", "_check_bash_state_deletion"),
    ("unified_pre_tool.py", "_detect_settings_json_write"),
    ("unified_pre_tool.py", "_is_protected_infrastructure"),
    ("unified_pre_tool.py", "_detect_git_bypass"),
    ("unified_pre_tool.py", "_check_rm_rf_unresolved_vars"),
)

_FALLBACK_OBSERVABILITY_HOOKS: tuple[str, ...] = (
    "session_activity_logger.py",
    "conversation_archiver.py",
    "unified_session_tracker.py",
)


def _get_config_path() -> Path:
    """Return the path to the bundled hard-floor config JSON.

    The path is resolved relative to this module's location, since the JSON
    ships inside the plugin directory and shares its trust boundary.

    Returns:
        Absolute path to ``config/hard_floor_hooks.json``.
    """
    return Path(__file__).parent.parent / "config" / "hard_floor_hooks.json"


def _load_config() -> dict | None:
    """Load and parse the hard-floor config JSON.

    Returns:
        Parsed dict on success. ``None`` if the file is missing, malformed,
        or otherwise unreadable. Callers MUST treat ``None`` as "fall back to
        module constants" — never as "everything is hard-floor".
    """
    path = _get_config_path()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def is_hard_floor(hook_name: str, function_name: str | None = None) -> bool:
    """Return True if the given hook (optionally scoped to a function) is hard-floor.

    A hook is hard-floor when session-mode logic must never disable it. The
    primary source is ``config/hard_floor_hooks.json``; on read failure the
    fallback constant is consulted.

    Matching rules:
        - File-level entry (no ``function`` key in JSON, or ``None`` in fallback):
          matches when ``function_name is None``.
        - Function-level entry: matches when ``function_name`` equals the
          entry's function name.

    Args:
        hook_name: The hook filename, e.g. ``"security_scan.py"``.
        function_name: Optional function name within the hook for fine-grained
            matching, e.g. ``"_detect_git_bypass"``.

    Returns:
        True if the (hook, function) pair is hard-floor, False otherwise.
    """
    config = _load_config()
    if config is not None:
        entries = config.get("hard_floor_hooks")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("hook") != hook_name:
                    continue
                entry_function = entry.get("function")
                # Entry without a function key is a file-level rule; matches
                # only when caller asks for the file (function_name is None).
                if entry_function is None and function_name is None:
                    return True
                if entry_function is not None and entry_function == function_name:
                    return True
            return False

    # Fallback: config missing or malformed. Match against the constant — and
    # ONLY against the constant. Do NOT default-allow arbitrary hooks.
    for fallback_hook, fallback_function in _FALLBACK_HARD_FLOOR_HOOKS:
        if fallback_hook == hook_name and fallback_function == function_name:
            return True
    return False


def get_observability_hooks() -> list[str]:
    """Return the list of always-run observability hooks.

    These hooks always run but are NOT enforcement — they only log. Returned
    as a fresh list so callers can mutate it without affecting the registry.

    Returns:
        List of hook filenames, e.g. ``["session_activity_logger.py", ...]``.
    """
    config = _load_config()
    if config is not None:
        observability = config.get("always_run_observability")
        if isinstance(observability, list) and all(isinstance(h, str) for h in observability):
            return list(observability)
    return list(_FALLBACK_OBSERVABILITY_HOOKS)
