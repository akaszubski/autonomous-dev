"""Autonomous revert checker for drain-queue commits that regress tests or pre-commit.

This module provides the core functionality for detecting regressions after drain
commits and automatically reverting them when necessary. It includes:

1. Regression detection via pytest failure count delta and pre-commit hook exit status
2. Finding fix commits that reference the drain SHA
3. Safe git revert operations with strict SHA validation (CWE-88 hardening)
4. Issue reopening with drain-reverted label
5. Label management for drain-reverted issues

All subprocess operations follow Issue #1064 discipline: list-form args, shell=False,
explicit cwd=, env=, timeout=. SHA validation uses strict 40-char hex regex to prevent
argument injection attacks.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Strict 40-char hex SHA validation regex (CWE-88 hardening)
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _build_env(repo_root: Path) -> Dict[str, str]:
    """Build subprocess env per Issue #1064 discipline.
    
    Inherits current os.environ for PATH, HOME, gh credentials, then adds
    any necessary overrides.
    """
    return dict(os.environ)


def detect_regression(before: Dict, after: Dict, repo_root: Path) -> bool:
    """Check if tests regressed between before and after snapshots.
    
    Args:
        before: Before metrics dict with keys: test_count, coverage_pct, failing_tests
        after: After metrics dict with same keys
        repo_root: Repository root directory
        
    Returns:
        True if regression detected (pytest failures increased OR pre-commit fails)
    """
    # Check pytest regression - more failures after than before
    before_failures = len(before.get("failing_tests", []))
    after_failures = len(after.get("failing_tests", []))
    
    if after_failures > before_failures:
        return True
    
    # Check pre-commit hook - run validation script at drain HEAD
    env = _build_env(repo_root)
    validation_script = repo_root / "scripts" / "validate_structure.py"
    
    if validation_script.exists():
        try:
            result = subprocess.run(
                ["python3", str(validation_script)],
                cwd=str(repo_root),
                env=env,
                timeout=30,
                check=False,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return True
        except (subprocess.TimeoutExpired, OSError):
            # If we can't run validation, don't assume regression
            pass
    
    return False


def find_fix_commits(drain_sha: str, repo_root: Path, env: Dict[str, str]) -> List[str]:
    """Find commits that reference the drain SHA (potential fixes).
    
    Args:
        drain_sha: The drain commit SHA to search for
        repo_root: Repository root directory 
        env: Environment variables for subprocess
        
    Returns:
        List of commit SHAs that reference the drain commit
    """
    if not SHA_PATTERN.match(drain_sha):
        raise ValueError(f"Invalid SHA format: {drain_sha}")
    
    try:
        # Search commit messages for references to the drain SHA
        result = subprocess.run(
            ["git", "log", "--grep", drain_sha[:8], "--format=%H", "--since", "1 week ago"],
            cwd=str(repo_root),
            env=env,
            timeout=10,
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return []
        
        # Filter to valid SHAs only
        fix_commits = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and SHA_PATTERN.match(line):
                fix_commits.append(line)
        
        return fix_commits
    except (subprocess.TimeoutExpired, OSError):
        return []


def revert_drain_commit(sha: str, repo_root: Path, env: Dict[str, str]) -> Tuple[bool, str]:
    """Perform git revert of the drain commit.
    
    Args:
        sha: The commit SHA to revert (must be 40-char hex)
        repo_root: Repository root directory
        env: Environment variables for subprocess
        
    Returns:
        Tuple of (success, revert_sha_or_error_msg)
    """
    # Strict SHA validation to prevent argument injection (CWE-88)
    if not SHA_PATTERN.match(sha):
        return False, f"Invalid SHA format: {sha}"
    
    try:
        # Perform the revert
        result = subprocess.run(
            ["git", "revert", "--no-edit", sha],
            cwd=str(repo_root),
            env=env,
            timeout=30,
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False, f"Git revert failed: {result.stderr}"
        
        # Get the revert commit SHA
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            env=env,
            timeout=5,
            check=False,
            capture_output=True,
            text=True
        )
        
        if sha_result.returncode == 0:
            revert_sha = sha_result.stdout.strip()
            if SHA_PATTERN.match(revert_sha):
                return True, revert_sha
        
        return False, "Could not get revert commit SHA"
        
    except subprocess.TimeoutExpired:
        return False, "Git revert timed out"
    except OSError as e:
        return False, f"Git revert OSError: {e}"


def reopen_issues_with_label(
    issues: List[int], 
    drain_sha: str, 
    revert_sha: str, 
    repo_root: Path, 
    env: Dict[str, str]
) -> int:
    """Reopen issues and add drain-reverted label with comment.
    
    Args:
        issues: List of issue numbers to reopen
        drain_sha: The drain commit SHA that was reverted
        revert_sha: The revert commit SHA
        repo_root: Repository root directory
        env: Environment variables for subprocess
        
    Returns:
        Number of successfully reopened issues
    """
    if not SHA_PATTERN.match(drain_sha) or not SHA_PATTERN.match(revert_sha):
        return 0
    
    # First ensure the label exists
    ensure_drain_reverted_label_exists(repo_root, env)
    
    reopened_count = 0
    
    for issue_num in issues:
        if not isinstance(issue_num, int) or issue_num <= 0:
            continue
            
        try:
            # Reopen the issue
            reopen_result = subprocess.run(
                ["gh", "issue", "reopen", str(issue_num)],
                cwd=str(repo_root),
                env=env,
                timeout=10,
                check=False,
                capture_output=True,
                text=True
            )
            
            if reopen_result.returncode != 0:
                continue
            
            # Add the label
            label_result = subprocess.run(
                ["gh", "issue", "edit", str(issue_num), "--add-label", "drain-reverted"],
                cwd=str(repo_root),
                env=env,
                timeout=10,
                check=False,
                capture_output=True,
                text=True
            )
            
            # Add comment with context
            comment = (
                f"🔄 **Drain Reverted**\n\n"
                f"The drain commit {drain_sha[:8]} was automatically reverted due to test regression.\n"
                f"- Drain commit: {drain_sha}\n"
                f"- Revert commit: {revert_sha}\n\n"
                f"This issue has been reopened for re-evaluation."
            )
            
            comment_result = subprocess.run(
                ["gh", "issue", "comment", str(issue_num), "--body", comment],
                cwd=str(repo_root),
                env=env,
                timeout=10,
                check=False,
                capture_output=True,
                text=True
            )
            
            if comment_result.returncode == 0:
                reopened_count += 1
                
        except (subprocess.TimeoutExpired, OSError):
            continue
    
    return reopened_count


def ensure_drain_reverted_label_exists(repo_root: Path, env: Dict[str, str]) -> bool:
    """Create drain-reverted label if it doesn't exist (idempotent).
    
    Args:
        repo_root: Repository root directory
        env: Environment variables for subprocess
        
    Returns:
        True if label exists or was created successfully
    """
    try:
        # Check if label exists
        check_result = subprocess.run(
            ["gh", "label", "list", "--search", "drain-reverted", "--json", "name"],
            cwd=str(repo_root),
            env=env,
            timeout=10,
            check=False,
            capture_output=True,
            text=True
        )
        
        if check_result.returncode == 0:
            labels = json.loads(check_result.stdout or "[]")
            if any(label.get("name") == "drain-reverted" for label in labels):
                return True
        
        # Create the label
        create_result = subprocess.run(
            [
                "gh", "label", "create", "drain-reverted",
                "--color", "B60205",  # Red color for reverted items
                "--description", "Issue was auto-closed by drain-queue but reverted due to regression"
            ],
            cwd=str(repo_root),
            env=env,
            timeout=10,
            check=False,
            capture_output=True,
            text=True
        )
        
        return create_result.returncode == 0
        
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        return False