"""Detect issues already implemented by prior commits.

Used by /implement --batch --issues STEP I1.3 to skip already-done issues
before mode detection.

Issue: #1110
"""
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


_SYMBOL_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_./]*)`")  # backtick-quoted
_IDENT_RE = re.compile(r"\b([a-z][a-z0-9_]{4,}_[a-z0-9_]+)\b")  # snake_case
_PATH_RE = re.compile(r"([\w/.-]+\.(?:py|md|json|yaml|yml|sh|ts|js))")


def _extract_symbols(title: str, body: str, max_count: int = 5) -> List[str]:
    """Extract candidate code symbols/paths from issue title and body.

    Args:
        title: Issue title text.
        body: Issue body text.
        max_count: Maximum number of symbols to return.

    Returns:
        List of unique symbol strings found, up to max_count.
    """
    text = f"{title}\n{body}"
    syms: list[str] = []
    for pat in (_SYMBOL_RE, _PATH_RE, _IDENT_RE):
        for match in pat.findall(text):
            if match and match not in syms:
                syms.append(match)
            if len(syms) >= max_count:
                return syms
    return syms


def _git_log_grep_issue(repo_root: Path, issue_number: int) -> Optional[Tuple[str, str]]:
    """Search commit messages for #<issue_number> reference.

    Args:
        repo_root: Root directory of the git repository.
        issue_number: GitHub issue number to search for.

    Returns:
        Tuple of (sha, commit_message) if found, None otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--oneline", f"--grep=#{issue_number}", "-1"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        line = result.stdout.strip()
        if line:
            parts = line.split(maxsplit=1)
            if len(parts) >= 2:
                return parts[0], parts[1]
            return parts[0], ""
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _git_log_pickaxe(repo_root: Path, symbol: str) -> Optional[Tuple[str, str]]:
    """Search for a commit that introduced/removed `symbol` in any diff.

    Args:
        repo_root: Root directory of the git repository.
        symbol: Code symbol or path fragment to search for.

    Returns:
        Tuple of (sha, commit_message) if found, None otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-S", symbol, "--oneline", "-1"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        line = result.stdout.strip()
        if line:
            parts = line.split(maxsplit=1)
            if len(parts) >= 2:
                return parts[0], parts[1]
            return parts[0], ""
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def check_issue_already_implemented(
    issue_number: int,
    title: str,
    body: str,
    repo_root: Path,
) -> Optional[Tuple[str, str]]:
    """Return (sha, commit_message) if a prior commit likely implements the issue.

    Strategy:
    1. Search commit messages for `#<issue_number>` reference (fast, definitive).
    2. Extract candidate symbols from title/body; pickaxe-search each.
    3. Return first match; None if nothing found.

    Args:
        issue_number: GitHub issue number to check.
        title: Issue title text.
        body: Issue body text.
        repo_root: Root directory of the git repository.

    Returns:
        Tuple of (sha, commit_message) if a matching commit is found, None otherwise.
    """
    result = _git_log_grep_issue(repo_root, issue_number)
    if result is not None:
        return result
    for sym in _extract_symbols(title, body, max_count=5):
        result = _git_log_pickaxe(repo_root, sym)
        if result is not None:
            return result
    return None
