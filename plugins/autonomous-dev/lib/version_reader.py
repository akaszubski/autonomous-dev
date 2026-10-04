"""Version reader for the autonomous-dev plugin.

Provides lightweight version + git SHA stamping for use in session logs,
auto-filed issues, and diagnostics.

Uses ONLY stdlib (json, subprocess, pathlib) -- no external dependencies.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

# Module-level cache to avoid repeated file reads / subprocess calls
_cached_version: Optional[str] = None


def get_plugin_version(*, plugin_root: Optional[Path] = None) -> str:
    """Return the plugin version string with optional git SHA.

    Format: ``"X.Y.Z (abc1234)"`` when git is available,
    ``"X.Y.Z"`` when git is unavailable, or ``"unknown"`` on any failure.

    The result is cached after the first successful call.

    Returns:
        Human-readable version string.

    Args:
        plugin_root: Executing installed plugin root. When supplied, read only
            its manifest and omit consumer git SHA and global cache.
    """
    # An explicit executing-plugin root never falls back to consumer CWD and
    # never stamps that consumer's git revision. Legacy callers retain caching.
    if plugin_root is not None:
        for manifest in (plugin_root / ".claude-plugin" / "plugin.json",
                         plugin_root / "plugin.json"):
            if manifest.is_file():
                return _read_version(manifest) or "unknown"
        return "unknown"

    global _cached_version
    if _cached_version is not None:
        return _cached_version

    version = _read_version()
    if version is None:
        _cached_version = "unknown"
        return _cached_version

    sha = _get_git_sha()
    if sha:
        _cached_version = f"{version} ({sha})"
    else:
        _cached_version = version

    return _cached_version


def _find_plugin_json() -> Optional[Path]:
    """Discover the plugin.json file from multiple candidate locations.

    Search order:
      1. Relative to this file: ``../../plugin.json``
      2. CWD-based: ``plugins/autonomous-dev/plugin.json``
      3. Global install: ``~/.autonomous-dev/plugin.json``

    Returns:
        Path to plugin.json if found, None otherwise.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / "plugin.json",
        Path.cwd() / "plugins" / "autonomous-dev" / "plugin.json",
        Path.home() / ".autonomous-dev" / "plugin.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _read_version(path: Optional[Path] = None) -> Optional[str]:
    """Parse the ``version`` field from plugin.json.

    Returns:
        Semver string (e.g. ``"3.50.0"``) or None on any error.

    Args:
        path: Explicit manifest, bypassing ambient discovery when provided.
    """
    path = path if path is not None else _find_plugin_json()
    if path is None:
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("version") if isinstance(data, dict) else None
        if isinstance(version, str) and version.strip():
            return version.strip()
        return None
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def _get_git_sha() -> Optional[str]:
    """Return the short git SHA of HEAD.

    Returns:
        Short SHA string (e.g. ``"abc1234"``) or None if git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if sha:
                return sha
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def reset_cache() -> None:
    """Reset the cached version string. Primarily for testing."""
    global _cached_version
    _cached_version = None
