#!/usr/bin/env python3
"""
Path Utilities - Centralized project root detection and path resolution

This module provides centralized path resolution for tracking infrastructure:
- Dynamic PROJECT_ROOT detection (searches for .git/ or .claude/)
- Session directory resolution
- Batch state file resolution
- Directory creation with proper permissions

Fixes Issue #79: Hardcoded paths in tracking infrastructure

Security Features:
- All paths resolve from PROJECT_ROOT (not current working directory)
- Works from any subdirectory
- Creates directories with safe permissions (0o755)
- No hardcoded relative paths

Usage:
    from path_utils import get_project_root, get_session_dir, get_batch_state_file

    # Get project root
    root = get_project_root()

    # Get session directory (creates if missing)
    session_dir = get_session_dir()

    # Get batch state file path
    state_file = get_batch_state_file()

Date: 2025-11-17
Issue: GitHub #79 (Tracking infrastructure hardcoded paths)
Agent: implementer

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import os
from pathlib import Path
from typing import Optional, List


# Cache for project root (avoid repeated filesystem searches)
_PROJECT_ROOT_CACHE: Optional[Path] = None


def find_project_root(
    marker_files: Optional[List[str]] = None,
    start_path: Optional[Path] = None
) -> Path:
    """Find project root by searching upward for marker files.

    Searches from current working directory upward until it finds a directory
    containing one of the marker files (.git/, .claude/, etc).

    Search strategy:
    - Prioritizes .git over .claude (searches all the way up for .git first)
    - Only searches for .claude if .git not found anywhere
    - This ensures git repos with nested .claude dirs work correctly

    Args:
        marker_files: List of marker files/directories to search for.
                     Defaults to [".git", ".claude"] (priority order)
        start_path: Starting path for search. Defaults to current working directory.

    Returns:
        Path to project root (directory containing marker file)

    Raises:
        FileNotFoundError: If no marker file found (reached filesystem root)

    Examples:
        >>> root = find_project_root()  # Search from cwd
        >>> root = find_project_root(start_path=Path("/path/to/nested/dir"))
        >>> root = find_project_root(marker_files=[".git", "setup.py"])

    Security:
        - No path traversal risk (only searches upward, never downward)
        - Stops at filesystem root (prevents infinite loops)
        - Validates marker files exist before returning
    """
    if marker_files is None:
        marker_files = [".git", ".claude"]

    if start_path is None:
        start_path = Path.cwd()

    # Resolve to absolute path (handles symlinks)
    start = start_path.resolve()

    # Priority-based search: Search ALL the way up for each marker in order
    # This ensures .git takes precedence over .claude even if .claude is closer
    for marker in marker_files:
        current = start
        while True:
            marker_path = current / marker
            if marker_path.exists():
                return current

            # Move to parent directory
            parent = current.parent

            # If we've reached the filesystem root, stop this marker search
            if parent == current:
                break

            current = parent

    # If we get here, no markers were found
    raise FileNotFoundError(
        f"Could not find project root. Searched upward from {start_path} "
        f"looking for: {', '.join(marker_files)}. "
        f"Ensure you're running from within a git repository or have .claude/PROJECT.md"
    )


def get_project_root(use_cache: bool = True) -> Path:
    """Get cached project root (or detect and cache it).

    This function caches the project root to avoid repeated filesystem searches.
    Safe to call multiple times - only searches once per process.

    Args:
        use_cache: If True, use cached value (default). If False, force re-detection.
                  Set to False in tests that change working directory.

    Returns:
        Path to project root

    Raises:
        FileNotFoundError: If no project root found

    Examples:
        >>> root = get_project_root()
        >>> session_dir = root / "docs" / "sessions"

        # In tests that change cwd
        >>> root = get_project_root(use_cache=False)

    Thread Safety:
        Not thread-safe (uses module-level cache). If needed for multi-threading,
        wrap with threading.Lock.
    """
    global _PROJECT_ROOT_CACHE

    if not use_cache or _PROJECT_ROOT_CACHE is None:
        _PROJECT_ROOT_CACHE = find_project_root()

    return _PROJECT_ROOT_CACHE


def get_session_dir(create: bool = True, use_cache: bool = True) -> Path:
    """Get session directory path (PROJECT_ROOT/docs/sessions).

    Args:
        create: If True, create directory if it doesn't exist (default: True)
        use_cache: If True, use cached project root (default). Set False in tests.

    Returns:
        Path to session directory

    Raises:
        FileNotFoundError: If project root not found
        OSError: If directory creation fails

    Examples:
        >>> session_dir = get_session_dir()
        >>> session_file = session_dir / "20251117-session.md"

        # In tests that change cwd
        >>> session_dir = get_session_dir(use_cache=False)

    Security:
        - Creates with restrictive permissions (0o700 = rwx------)
        - No path traversal risk (uses get_project_root())
    """
    project_root = get_project_root(use_cache=use_cache)
    session_dir = project_root / "docs" / "sessions"

    if create and not session_dir.exists():
        session_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (owner only)
        session_dir.chmod(0o700)  # rwx------

    return session_dir


def get_batch_state_file() -> Path:
    """Get batch state file path (PROJECT_ROOT/.claude/batch_state.json).

    Note: Does NOT create the file (only returns path).
    Directory (.claude/) is created if it doesn't exist.

    Returns:
        Path to batch state file

    Raises:
        FileNotFoundError: If project root not found
        OSError: If directory creation fails

    Examples:
        >>> state_file = get_batch_state_file()
        >>> from batch_state_manager import save_batch_state
        >>> save_batch_state(state_file, state)

    Security:
        - Creates parent directory with safe permissions (0o755)
        - No path traversal risk (uses get_project_root())
    """
    project_root = get_project_root()
    claude_dir = project_root / ".claude"

    # Create .claude/ directory if missing
    claude_dir.mkdir(parents=True, exist_ok=True, mode=0o755)

    return claude_dir / "batch_state.json"


def reset_project_root_cache() -> None:
    """Reset cached project root (for testing only).

    Warning: Only use this in test teardown. In production, the cache should
    persist for the lifetime of the process.

    Examples:
        >>> # In test teardown
        >>> reset_project_root_cache()
    """
    global _PROJECT_ROOT_CACHE
    _PROJECT_ROOT_CACHE = None
