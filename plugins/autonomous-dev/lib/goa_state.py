"""GOA (Governance, Observability, Audit) state management.

Manages the GOA manifest at ``.claude/local/goa_manifest.json`` — a lightweight
JSON file that records which cron triggers are registered and what thresholds are
active.  All writes go through ``pipeline_state.atomic_write_json`` for
atomicity (temp-file + rename, 0o600 permissions).

Issue #1320 — MVP implementation, conservative-mode only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path helpers (lazy imports to avoid circular deps)
# ---------------------------------------------------------------------------


def _get_project_root() -> Path:
    """Return the project root, using path_utils if available."""
    try:
        import sys
        import os

        _lib = Path(__file__).resolve().parent
        if str(_lib) not in sys.path:
            sys.path.insert(0, str(_lib))
        from path_utils import get_project_root  # type: ignore[import-untyped]

        return get_project_root()
    except Exception:
        # Fallback: walk up from this file until we find .git or .claude
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / ".git").exists() or (parent / ".claude").exists():
                return parent
        return Path.cwd()


# ---------------------------------------------------------------------------
# Manifest schema constants
# ---------------------------------------------------------------------------

MANIFEST_VERSION = 1

#: Default Conservative-mode thresholds.
DEFAULT_THRESHOLDS: dict[str, Any] = {
    "drop_rate_pct": 70,
    "drop_window_h": 12,
    "down_events": 2,
    "down_window_h": 12,
}

_MANIFEST_SUBPATH = Path(".claude/local/goa_manifest.json")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_manifest_path() -> Path:
    """Return the absolute path to the GOA manifest file.

    Returns:
        Absolute ``Path`` to ``.claude/local/goa_manifest.json`` inside the
        current project root.
    """
    return _get_project_root() / _MANIFEST_SUBPATH


def load_manifest() -> dict[str, Any] | None:
    """Load and return the GOA manifest, or ``None`` if it does not exist.

    Returns:
        The parsed JSON dict, or ``None`` when the manifest file is absent or
        unreadable.
    """
    path = get_manifest_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_manifest(data: dict[str, Any]) -> None:
    """Atomically write *data* to the GOA manifest file.

    Creates parent directories if they do not exist.

    Args:
        data: JSON-serialisable dict to persist.

    Raises:
        OSError: If the parent directory cannot be created or the write fails.
        TypeError: If *data* is not JSON-serialisable.
    """
    from pipeline_state import atomic_write_json  # type: ignore[import-untyped]

    path = get_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, data, indent=2)


def delete_manifest() -> None:
    """Remove the GOA manifest file if it exists.

    No-op when the file is absent.
    """
    path = get_manifest_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass
