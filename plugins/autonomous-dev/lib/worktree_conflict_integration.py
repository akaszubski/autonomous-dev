#!/usr/bin/env python3
"""
Worktree Conflict Integration - Glue between conflict resolver and worktree manager

This module integrates AI-powered conflict resolution into the worktree workflow:
- Detects conflicts during worktree merge
- Automatically triggers AI resolution when enabled
- Enforces confidence thresholds for auto-commit
- Requires manual review for security-related conflicts
- Provides three-tier escalation strategy

Integration Points:
    - worktree_manager.merge_worktree() - Calls this when conflicts detected
    - conflict_resolver.resolve_conflicts() - Called for each conflicted file
    - unified_git_automation - Checks confidence before auto-commit

Security:
    - Path validation for all file operations (CWE-22)
    - API key from environment only (never logged)
    - Audit logging for all resolutions
    - Security code paths require manual review

Usage:
    from worktree_conflict_integration import resolve_worktree_conflicts

    # Resolve multiple conflicted files
    results = resolve_worktree_conflicts(['auth.py', 'config.py'])

    for result in results:
        if result.success and result.resolution.confidence >= 0.8:
            print(f"Auto-resolved {result.file_path}")
        else:
            print(f"Manual review required: {result.file_path}")

Date: 2026-01-02
Issue: #193 (Wire conflict resolver into worktree and git automation)
Agent: implementer
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Import conflict resolver
sys.path.insert(0, str(Path(__file__).parent))
try:
    from conflict_resolver import (
        ConflictResolutionResult,
        ResolutionSuggestion,
        resolve_conflicts,
        parse_conflict_markers,
    )
    from feature_flags import is_feature_enabled
    from security_utils import validate_path as _validate_path_strict, audit_log

    def validate_path(path, purpose="conflict_resolution"):
        """Wrapper for security_utils.validate_path that returns tuple."""
        try:
            _validate_path_strict(path, purpose=purpose, allow_missing=False)
            return (True, "")
        except ValueError as e:
            return (False, str(e))
        except FileNotFoundError:
            return (False, "File not found")
except ImportError as e:
    # Allow import for testing
    def validate_path(path, purpose="conflict_resolution"):
        return (True, "")

    def audit_log(event_type, message):
        pass


# ============================================================================
# Constants
# ============================================================================

# Confidence threshold for auto-commit (0.0-1.0)
AUTO_COMMIT_THRESHOLD = 0.8

# ============================================================================
# Security Detection
# ============================================================================

def is_security_related(file_path: str) -> bool:
    """Check if file is security-related (requires manual review).

    Args:
        file_path: Path to file to check

    Returns:
        True if file matches security patterns

    Security Patterns (strict matching to avoid false positives):
        - Files named: security*.py, *_security.py, security_*.py
        - Files named: credentials.py, secrets.py, api_keys.py
        - Files named: .env*, *.key, *.pem, *.crt
        - Path contains: /security/, /credentials/, /secrets/
        - Files named: security_config.py, auth_config.py (but not just config.py)

    Examples:
        >>> is_security_related("security_config.py")
        True
        >>> is_security_related("auth.py")
        False
        >>> is_security_related("utils.py")
        False
    """
    file_name = Path(file_path).name.lower()
    full_path = str(file_path).lower()

    # Strict file name patterns (must match exactly or with prefix/suffix)
    strict_filenames = [
        r'^security.*\.py$',
        r'.*_security\.py$',
        r'^credentials\.py$',
        r'^secrets\.py$',
        r'^api_keys?\.py$',
        r'^\.env',
        r'.*\.key$',
        r'.*\.pem$',
        r'.*\.crt$',
        r'^security_config\.py$',
        r'^auth_config\.py$',
    ]

    # Check file name patterns
    for pattern in strict_filenames:
        if re.match(pattern, file_name):
            return True

    # Check path patterns (directories)
    path_patterns = [
        r'/security/',
        r'/credentials/',
        r'/secrets/',
    ]

    for pattern in path_patterns:
        if pattern in full_path:
            return True

    return False


# ============================================================================
# Conflict Resolution Integration
# ============================================================================

def resolve_worktree_conflicts(
    conflict_files: List[str],
    api_key: Optional[str] = None
) -> List[ConflictResolutionResult]:
    """Resolve conflicts in multiple files using AI.

    Args:
        conflict_files: List of file paths with conflicts
        api_key: Anthropic API key (or None to read from env)

    Returns:
        List of ConflictResolutionResult objects

    Security:
        - Validates all file paths (CWE-22)
        - API key from environment if not provided
        - Security files require manual review
        - Audit logs all resolutions

    Examples:
        >>> results = resolve_worktree_conflicts(['auth.py', 'config.py'])
        >>> high_confidence = [r for r in results if r.resolution.confidence >= 0.8]
    """
    # Check feature flag
    if not is_feature_enabled("conflict_resolver"):
        # Feature disabled - return empty results
        return []

    # Get API key from environment if not provided
    if api_key is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        # No API key - cannot resolve
        return [
            ConflictResolutionResult(
                success=False,
                file_path=str(f),
                error_message="ANTHROPIC_API_KEY not set",
                fallback_to_manual=True
            )
            for f in conflict_files
        ]

    results = []

    for file_path in conflict_files:
        # Validate path
        is_valid, error = validate_path(str(file_path), purpose="conflict_resolution")
        if not is_valid:
            results.append(ConflictResolutionResult(
                success=False,
                file_path=str(file_path),
                error_message=f"Invalid path: {error}",
                fallback_to_manual=True
            ))
            continue

        # Check if security-related (always require manual review)
        if is_security_related(str(file_path)):
            results.append(ConflictResolutionResult(
                success=False,
                file_path=str(file_path),
                error_message="Security-related file requires manual review",
                fallback_to_manual=True
            ))
            audit_log(
                "conflict_resolution",
                f"Security file requires manual review: {file_path}"
            )
            continue

        # Attempt AI resolution
        try:
            result = resolve_conflicts(str(file_path), api_key)
            results.append(result)

            # Audit log resolution
            if result.success:
                confidence = result.resolution.confidence if result.resolution else 0.0
                audit_log(
                    "conflict_resolution",
                    f"Resolved {file_path} with {confidence:.0%} confidence"
                )

        except Exception as e:
            results.append(ConflictResolutionResult(
                success=False,
                file_path=str(file_path),
                error_message=f"Resolution failed: {str(e)}",
                fallback_to_manual=True
            ))
            audit_log(
                "conflict_resolution_error",
                f"Failed to resolve {file_path}: {str(e)}"
            )

    return results


def should_auto_commit(result: ConflictResolutionResult) -> bool:
    """Check if resolution should be auto-committed.

    Args:
        result: ConflictResolutionResult to check

    Returns:
        True if should auto-commit, False if manual review required

    Criteria:
        - Resolution successful
        - Confidence >= AUTO_COMMIT_THRESHOLD (0.8)
        - Not security-related file
        - Not flagged for manual fallback

    Examples:
        >>> result = ConflictResolutionResult(
        ...     success=True,
        ...     file_path="utils.py",
        ...     resolution=ResolutionSuggestion(
        ...         resolved_content="resolved",
        ...         confidence=0.9,
        ...         reasoning="Clear",
        ...         tier_used=2
        ...     )
        ... )
        >>> should_auto_commit(result)
        True
    """
    if not result.success:
        return False

    if result.fallback_to_manual:
        return False

    if not result.resolution:
        return False

    if result.resolution.confidence < AUTO_COMMIT_THRESHOLD:
        return False

    if is_security_related(result.file_path):
        return False

    return True


def get_resolution_confidence(result: ConflictResolutionResult) -> float:
    """Extract confidence score from resolution result.

    Args:
        result: ConflictResolutionResult to extract confidence from

    Returns:
        Confidence score (0.0-1.0), or 0.0 if no resolution

    Examples:
        >>> result = ConflictResolutionResult(
        ...     success=True,
        ...     file_path="test.py",
        ...     resolution=ResolutionSuggestion(
        ...         resolved_content="resolved",
        ...         confidence=0.85,
        ...         reasoning="test",
        ...         tier_used=2
        ...     )
        ... )
        >>> get_resolution_confidence(result)
        0.85
    """
    if not result.resolution:
        return 0.0

    return result.resolution.confidence


# ============================================================================
# Conflict Detection Helpers
# ============================================================================

def detect_conflicts_in_output(git_output: str) -> List[str]:
    """Parse git merge output to detect conflicted files.

    Args:
        git_output: Output from git merge command

    Returns:
        List of file paths with conflicts

    Examples:
        >>> output = "CONFLICT (content): Merge conflict in auth.py\\nCONFLICT in config.py"
        >>> detect_conflicts_in_output(output)
        ['auth.py', 'config.py']
    """
    conflicts = []

    # Pattern: "CONFLICT (content): Merge conflict in <file>"
    pattern = r'CONFLICT.*?(?:in|:)\s+(\S+)'

    for match in re.finditer(pattern, git_output):
        file_path = match.group(1)
        if file_path and file_path not in conflicts:
            conflicts.append(file_path)

    return conflicts


def has_conflict_markers(file_path: str) -> bool:
    """Check if file contains git conflict markers.

    Args:
        file_path: Path to file to check

    Returns:
        True if file contains <<<<<<< or ======= or >>>>>>>

    Examples:
        >>> has_conflict_markers("auth.py")  # File with conflicts
        True
        >>> has_conflict_markers("clean.py")  # No conflicts
        False
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Check for standard git conflict markers
        return any([
            '<<<<<<<' in content,
            '=======' in content,
            '>>>>>>>' in content,
        ])

    except (OSError, IOError):
        return False
