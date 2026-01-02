#!/usr/bin/env python3
"""
Feature Flags - Configuration for optional features

Provides feature flag management for autonomous-dev plugin features:
- conflict_resolver: AI-powered merge conflict resolution
- auto_git_workflow: Automatic git operations after agent completion

Default Behavior:
    - All features default to ENABLED (opt-out model)
    - Missing feature_flags.json = all features enabled
    - Missing individual flag = feature enabled

Configuration:
    Location: .claude/feature_flags.json

    Format:
    {
        "conflict_resolver": {"enabled": true},
        "auto_git_workflow": {"enabled": true}
    }

Security:
    - Path validation for config file (CWE-22)
    - JSON parsing with error handling
    - No arbitrary code execution

Usage:
    from feature_flags import is_feature_enabled

    if is_feature_enabled("conflict_resolver"):
        resolve_conflicts(file_path, api_key)

Date: 2026-01-02
Issue: #193 (Wire conflict resolver into worktree and git automation)
Agent: implementer
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Import security utilities for path validation
sys.path.insert(0, str(Path(__file__).parent))
try:
    from security_utils import validate_path as _validate_path_strict

    def validate_path(path, purpose="feature_flags", allow_missing=True):
        """Wrapper for security_utils.validate_path that returns bool."""
        try:
            _validate_path_strict(path, purpose=purpose, allow_missing=allow_missing)
            return True
        except (ValueError, FileNotFoundError):
            return False
except ImportError:
    # Fallback if security_utils not available
    def validate_path(path, purpose="feature_flags", allow_missing=True):
        return True


# ============================================================================
# Feature Flag Configuration
# ============================================================================

def _find_project_root() -> Optional[Path]:
    """Find project root by locating .claude or .git directory.

    Returns:
        Path to project root, or None if not found
    """
    current = Path.cwd()

    # Search up to 10 levels (prevent infinite loop)
    for _ in range(10):
        if (current / ".claude").exists() or (current / ".git").exists():
            return current

        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent

    return None


def _get_feature_flags_path() -> Optional[Path]:
    """Get path to feature_flags.json file.

    Returns:
        Path to feature_flags.json, or None if project root not found
    """
    project_root = _find_project_root()
    if not project_root:
        return None

    return project_root / ".claude" / "feature_flags.json"


def _load_feature_flags() -> Dict[str, Dict[str, bool]]:
    """Load feature flags from configuration file.

    Returns:
        Dict of feature flags, or empty dict if file not found/invalid

    Default behavior:
        - Missing file = empty dict (all features enabled by default)
        - Invalid JSON = empty dict (all features enabled by default)
        - Read errors = empty dict (all features enabled by default)
    """
    flags_path = _get_feature_flags_path()

    if not flags_path or not flags_path.exists():
        # No config file = all features enabled (opt-out model)
        return {}

    try:
        # Validate path (prevent directory traversal)
        if not validate_path(str(flags_path), purpose="feature_flags", allow_missing=False):
            return {}

        # Load and parse JSON
        with open(flags_path, 'r', encoding='utf-8') as f:
            flags = json.load(f)

        if not isinstance(flags, dict):
            return {}

        return flags

    except (json.JSONDecodeError, OSError, IOError):
        # Any error = all features enabled (graceful degradation)
        return {}


def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled via feature flags.

    Args:
        feature_name: Name of feature to check (e.g., "conflict_resolver")

    Returns:
        True if feature is enabled, False if explicitly disabled

    Default Behavior:
        - Missing feature_flags.json = True (enabled)
        - Missing feature in file = True (enabled)
        - Feature exists with enabled=false = False (disabled)
        - Any error loading config = True (enabled)

    Examples:
        >>> is_feature_enabled("conflict_resolver")
        True

        >>> # With feature_flags.json: {"conflict_resolver": {"enabled": false}}
        >>> is_feature_enabled("conflict_resolver")
        False

        >>> # With feature_flags.json missing
        >>> is_feature_enabled("conflict_resolver")
        True  # Defaults to enabled
    """
    flags = _load_feature_flags()

    # Feature not in config = enabled (opt-out model)
    if feature_name not in flags:
        return True

    feature_config = flags[feature_name]

    # Invalid config structure = enabled (graceful degradation)
    if not isinstance(feature_config, dict):
        return True

    # Check enabled flag
    return feature_config.get("enabled", True)  # Default to enabled


def get_feature_config(feature_name: str) -> Dict[str, Any]:
    """Get complete configuration for a feature.

    Args:
        feature_name: Name of feature to get config for

    Returns:
        Dict with feature configuration, or {"enabled": True} if not found

    Examples:
        >>> get_feature_config("conflict_resolver")
        {"enabled": True, "confidence_threshold": 0.8}
    """
    flags = _load_feature_flags()

    if feature_name not in flags:
        return {"enabled": True}

    feature_config = flags[feature_name]

    if not isinstance(feature_config, dict):
        return {"enabled": True}

    return feature_config


# ============================================================================
# Feature Flag Defaults
# ============================================================================

DEFAULT_FLAGS = {
    "conflict_resolver": {
        "enabled": True,
        "confidence_threshold": 0.8,
        "security_requires_manual": True
    },
    "auto_git_workflow": {
        "enabled": True,
        "auto_push": False,
        "auto_pr": False
    }
}


def get_default_flags() -> Dict[str, Dict[str, Any]]:
    """Get default feature flag configuration.

    Returns:
        Dict with default flags for all features
    """
    return DEFAULT_FLAGS.copy()
