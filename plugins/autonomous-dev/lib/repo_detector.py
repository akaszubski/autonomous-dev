#!/usr/bin/env python3
"""
Repository Detector - Detect autonomous-dev repository context.

Enables autonomous-dev to enforce quality gates on itself by detecting:
- Whether current repo is autonomous-dev (vs user project)
- Whether running in worktree (batch processing)
- Whether running in CI environment (GitHub Actions, etc.)

Detection Strategy:
- Multi-marker detection (plugins/autonomous-dev/ directory + manifest.json)
- Worktree detection via .git file parsing
- CI detection via environment variables
- Thread-safe caching for performance

Purpose:
Allows hooks and libraries to enforce stricter quality gates on autonomous-dev's
own codebase while maintaining backward compatibility for user projects.

Security:
- Uses security_utils.audit_log() for all enforcement decisions
- Thread-safe caching with reset capability
- Graceful degradation on detection failures

Date: 2026-01-26
Issue: #271 (meta(enforcement): Autonomous-dev doesn't enforce its own quality gates)
Agent: implementer
Phase: Implementation (TDD Green)

Design Patterns:
    See library-design-patterns skill for caching and error handling patterns.
"""

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class RepoContext:
    """
    Repository context information.

    Attributes:
        is_autonomous_dev: True if current repo is autonomous-dev
        is_worktree: True if running in git worktree
        is_ci: True if running in CI environment
    """

    is_autonomous_dev: bool
    is_worktree: bool
    is_ci: bool


# =============================================================================
# Caching
# =============================================================================

# Cache for detection results (thread-safe)
_cache_lock = threading.Lock()
_cached_is_autonomous_dev: Optional[bool] = None
_cached_is_worktree: Optional[bool] = None
_cached_is_ci: Optional[bool] = None
_cached_context: Optional[RepoContext] = None


def _reset_cache() -> None:
    """
    Reset all cached detection results.

    Used for test isolation and when detection needs to be re-run.
    Thread-safe.

    Examples:
        >>> _reset_cache()
        >>> # All cached values cleared
    """
    global _cached_is_autonomous_dev, _cached_is_worktree, _cached_is_ci, _cached_context

    with _cache_lock:
        _cached_is_autonomous_dev = None
        _cached_is_worktree = None
        _cached_is_ci = None
        _cached_context = None


# =============================================================================
# Detection Functions
# =============================================================================


def is_autonomous_dev_repo() -> bool:
    """
    Detect if current repository is autonomous-dev.

    Detection Strategy:
        1. Look for plugins/autonomous-dev/ directory
        2. Verify manifest.json exists
        3. Traverse up directory tree to find repo root
        4. Cache result for performance

    Returns:
        True if current repo is autonomous-dev, False otherwise

    Thread Safety:
        Results are cached with thread-safe locking.

    Graceful Degradation:
        - Missing .git directory: Returns False
        - Permission errors: Returns False
        - Corrupted manifest: Returns False
        - Any exception: Returns False (safe default)

    Examples:
        >>> # In autonomous-dev repo
        >>> is_autonomous_dev_repo()
        True

        >>> # In user project
        >>> is_autonomous_dev_repo()
        False
    """
    global _cached_is_autonomous_dev

    # Check cache first (thread-safe)
    with _cache_lock:
        if _cached_is_autonomous_dev is not None:
            return _cached_is_autonomous_dev

    # Perform detection
    result = _detect_autonomous_dev()

    # Cache result (thread-safe)
    with _cache_lock:
        _cached_is_autonomous_dev = result

    # Log detection for audit trail
    try:
        from security_utils import audit_log

        audit_log(
            "repo_detection",
            "success",
            {
                "operation": "is_autonomous_dev_repo",
                "result": result,
                "cwd": str(Path.cwd()),
            },
        )
    except (ImportError, Exception):
        # Graceful degradation - audit logging is best-effort
        pass

    return result


def _detect_autonomous_dev() -> bool:
    """
    Internal detection logic for autonomous-dev repository.

    Returns:
        True if autonomous-dev detected, False otherwise
    """
    try:
        # Start from current directory and traverse up
        current = Path.cwd().resolve()

        # Limit traversal to 10 levels (prevent infinite loops)
        for _ in range(10):
            # Check for autonomous-dev signature files
            manifest_path = current / "plugins" / "autonomous-dev" / "manifest.json"

            if manifest_path.exists():
                # Verify it's a valid manifest (contains "autonomous-dev")
                try:
                    content = manifest_path.read_text()
                    if "autonomous-dev" in content:
                        return True
                except Exception:
                    # Corrupted manifest or permission error
                    return False

            # Move to parent directory
            parent = current.parent
            if parent == current:
                # Reached filesystem root
                break
            current = parent

        # No autonomous-dev signature found
        return False

    except Exception:
        # Any exception during detection = not autonomous-dev (safe default)
        return False


def is_worktree() -> bool:
    """
    Detect if current directory is a git worktree.

    Detection Strategy:
        1. Check if .git is a file (worktrees have .git file, not directory)
        2. Parse .git file for "gitdir:" pointer
        3. Cache result for performance

    Returns:
        True if running in worktree, False otherwise

    Thread Safety:
        Results are cached with thread-safe locking.

    Graceful Degradation:
        - Missing .git: Returns False
        - .git is directory (main repo): Returns False
        - Corrupted .git file: Returns False
        - Any exception: Returns False (safe default)

    Examples:
        >>> # In main repo
        >>> is_worktree()
        False

        >>> # In worktree
        >>> is_worktree()
        True
    """
    global _cached_is_worktree

    # Check cache first (thread-safe)
    with _cache_lock:
        if _cached_is_worktree is not None:
            return _cached_is_worktree

    # Perform detection
    result = _detect_worktree()

    # Cache result (thread-safe)
    with _cache_lock:
        _cached_is_worktree = result

    # Log detection for audit trail
    try:
        from security_utils import audit_log

        audit_log(
            "repo_detection",
            "success",
            {
                "operation": "is_worktree",
                "result": result,
                "cwd": str(Path.cwd()),
            },
        )
    except (ImportError, Exception):
        # Graceful degradation - audit logging is best-effort
        pass

    return result


def _detect_worktree() -> bool:
    """
    Internal detection logic for git worktree.

    Returns:
        True if worktree detected, False otherwise
    """
    try:
        # Look for .git in current directory and parents
        current = Path.cwd().resolve()

        # Limit traversal to 10 levels
        for _ in range(10):
            git_path = current / ".git"

            if git_path.exists():
                # Check if .git is a file (worktree) or directory (main repo)
                if git_path.is_file():
                    # Worktrees have .git file containing "gitdir: ..." pointer
                    try:
                        content = git_path.read_text()
                        if "gitdir:" in content:
                            return True
                    except Exception:
                        # Corrupted .git file
                        return False

                # .git is directory (main repo)
                return False

            # Move to parent directory
            parent = current.parent
            if parent == current:
                # Reached filesystem root
                break
            current = parent

        # No .git found
        return False

    except Exception:
        # Any exception during detection = not worktree (safe default)
        return False


def is_ci_environment() -> bool:
    """
    Detect if running in CI environment.

    Detection Strategy:
        1. Check for CI environment variables (CI, GITHUB_ACTIONS, etc.)
        2. Support multiple CI platforms
        3. Cache result for performance

    Supported CI Platforms:
        - GitHub Actions: GITHUB_ACTIONS
        - GitLab CI: GITLAB_CI
        - Jenkins: JENKINS_URL
        - Travis CI: TRAVIS
        - Generic: CI

    Returns:
        True if running in CI, False otherwise

    Thread Safety:
        Results are cached with thread-safe locking.

    Examples:
        >>> # In local development
        >>> is_ci_environment()
        False

        >>> # In GitHub Actions
        >>> os.environ["GITHUB_ACTIONS"] = "true"
        >>> is_ci_environment()
        True
    """
    global _cached_is_ci

    # Check cache first (thread-safe)
    with _cache_lock:
        if _cached_is_ci is not None:
            return _cached_is_ci

    # Perform detection
    result = _detect_ci_environment()

    # Cache result (thread-safe)
    with _cache_lock:
        _cached_is_ci = result

    # Log detection for audit trail
    try:
        from security_utils import audit_log

        audit_log(
            "repo_detection",
            "success",
            {
                "operation": "is_ci_environment",
                "result": result,
                "detected_vars": _get_detected_ci_vars(),
            },
        )
    except (ImportError, Exception):
        # Graceful degradation - audit logging is best-effort
        pass

    return result


def _detect_ci_environment() -> bool:
    """
    Internal detection logic for CI environment.

    Returns:
        True if CI detected, False otherwise
    """
    try:
        # CI environment variables to check
        ci_vars = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "TRAVIS"]

        for var in ci_vars:
            value = os.environ.get(var, "").strip().lower()

            # Check for truthy values
            if value in ("true", "1", "yes"):
                return True

            # JENKINS_URL is set to URL (not boolean)
            if var == "JENKINS_URL" and value:
                return True

        # No CI indicators found
        return False

    except Exception:
        # Any exception during detection = not CI (safe default)
        return False


def _get_detected_ci_vars() -> list:
    """
    Get list of detected CI environment variables.

    Returns:
        List of CI variable names that are set
    """
    detected = []
    ci_vars = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "TRAVIS"]

    for var in ci_vars:
        if os.environ.get(var):
            detected.append(var)

    return detected


def get_repo_context() -> RepoContext:
    """
    Get complete repository context information.

    Combines all detection results into single context object.
    Caches entire context for performance.

    Returns:
        RepoContext with all detection results

    Thread Safety:
        Context is cached with thread-safe locking.

    Examples:
        >>> context = get_repo_context()
        >>> context.is_autonomous_dev
        True
        >>> context.is_worktree
        False
        >>> context.is_ci
        False
    """
    global _cached_context

    # Check cache first (thread-safe)
    with _cache_lock:
        if _cached_context is not None:
            return _cached_context

    # Build context from individual detections
    context = RepoContext(
        is_autonomous_dev=is_autonomous_dev_repo(),
        is_worktree=is_worktree(),
        is_ci=is_ci_environment(),
    )

    # Cache context (thread-safe)
    with _cache_lock:
        _cached_context = context

    return context


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "RepoContext",
    "is_autonomous_dev_repo",
    "is_worktree",
    "is_ci_environment",
    "get_repo_context",
    "_reset_cache",  # Exported for testing
]
