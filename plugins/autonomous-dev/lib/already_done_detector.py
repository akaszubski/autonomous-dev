"""Detect issues already implemented by prior commits.

Used by /implement --batch --issues STEP I1.3 to skip already-done issues
before mode detection.

This module distinguishes between:
- "closes" markers (Closes #N, Fixes #N, Completed: #N) — strong signal the issue is done
- "anti" markers (Pending: #N, Preflight-skipped: #N, Deferred: #N) — explicit signal NOT done
- "mention" markers (bare #N reference) — weak signal, not enough alone
- "stale_branch" — commit closes the issue but is not an ancestor of HEAD (unmerged side branch)

Issue: #1110, #1125
"""
import re
import subprocess
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple


class MatchResult(NamedTuple):
    """Result of an already-done check for a single issue.

    Attributes:
        sha: Commit SHA that references the issue.
        subject: Commit subject line (first line of the commit message).
        classification: One of "closes", "anti", "mention", "stale_branch".

    Backward compatibility: NamedTuple supports 2-element tuple unpacking
    (e.g. ``sha, subject = result``) as long as callers do not access index 2.
    The detector returns this 3-tuple only when classification == "closes" AND
    the commit is an ancestor of HEAD — otherwise it returns None.
    """

    sha: str
    subject: str
    classification: str


_SYMBOL_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_./]*)`")  # backtick-quoted
_IDENT_RE = re.compile(r"\b([a-z][a-z0-9_]{4,}_[a-z0-9_]+)\b")  # snake_case
_PATH_RE = re.compile(r"([\w/.-]+\.(?:py|md|json|yaml|yml|sh|ts|js))")

# Classification markers.
# A line containing `#<issue>` is examined for these markers.
_CLOSURE_LABELS = r"(?:closes?d?|fix(?:es|ed)?|resolves?d?|implements?)"
_CLOSURE_RE = re.compile(rf"\b{_CLOSURE_LABELS}\b\s*[:\-]?\s*#(\d+)", re.IGNORECASE)
_COMPLETED_RE = re.compile(r"\bCompleted\s*:\s*((?:#\d+\s*,?\s*)+)", re.IGNORECASE)

_ANTI_LABELS = r"(?:pending|preflight[- ]skipped|skipped|deferred|remaining)"
_ANTI_RE = re.compile(
    rf"\b{_ANTI_LABELS}\b\s*:\s*((?:#\d+(?:\s*\([^)]*\))?\s*,?\s*)+)",
    re.IGNORECASE,
)


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


def _classify_issue_in_body(body: str, issue_number: int) -> str:
    """Classify how an issue number is referenced in a commit body.

    Performs line-by-line scanning. For each line containing ``#<issue_number>``:
      - If an anti-marker label (Pending, Preflight-skipped, etc.) on that line: "anti"
      - Else if a closure-marker label (Closes, Fixes, Completed) covering that
        issue on that line: "closes"
      - Else: "mention"

    Across the whole body, precedence is: closes > mention > anti.
    (A single explicit closure outweighs other ambiguous mentions; a mention
    plus an anti-marker resolves to "mention" since the issue is referenced
    but not actively closed.)

    Args:
        body: Full commit body text.
        issue_number: Issue number to classify.

    Returns:
        One of "closes", "mention", "anti", or "none" if not referenced at all.
    """
    needle = f"#{issue_number}"
    # Word-boundary check: ensure #123 doesn't match #1234.
    issue_pattern = re.compile(rf"#{issue_number}\b")

    saw_closes = False
    saw_mention = False
    saw_anti = False

    for line in body.splitlines():
        if not issue_pattern.search(line):
            continue

        # Anti-marker check on this line — match the label and the issue list.
        anti_hit = False
        for m in _ANTI_RE.finditer(line):
            list_text = m.group(1)
            if issue_pattern.search(list_text):
                anti_hit = True
                break
        if anti_hit:
            saw_anti = True
            continue

        # Closure-label check on this line.
        closure_hit = False
        # Direct closures: Closes #N, Fixes #N, etc.
        for m in _CLOSURE_RE.finditer(line):
            if int(m.group(1)) == issue_number:
                closure_hit = True
                break
        # Completed: #N, #M, #K
        if not closure_hit:
            for m in _COMPLETED_RE.finditer(line):
                list_text = m.group(1)
                if issue_pattern.search(list_text):
                    closure_hit = True
                    break

        if closure_hit:
            saw_closes = True
        else:
            saw_mention = True

    if saw_closes:
        return "closes"
    if saw_mention:
        return "mention"
    if saw_anti:
        return "anti"
    return "none"


def _is_ancestor_of_head(repo_root: Path, sha: str) -> bool:
    """Check whether ``sha`` is an ancestor of HEAD.

    Uses ``git merge-base --is-ancestor``. Returns False if the command fails
    (e.g. sha not found) or HEAD doesn't exist.

    Args:
        repo_root: Root directory of the git repository.
        sha: Commit SHA to test.

    Returns:
        True iff ``sha`` is reachable from HEAD via parent pointers.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", sha, "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _git_log_grep_issue(
    repo_root: Path, issue_number: int
) -> List[Tuple[str, str, str]]:
    """Search commit messages on ALL branches for ``#<issue_number>``.

    Returns the full commit body (not just the subject) so the caller can
    classify markers like ``Pending: #N`` that only appear in the body.

    Args:
        repo_root: Root directory of the git repository.
        issue_number: GitHub issue number to search for.

    Returns:
        List of (sha, subject, body) tuples for all matching commits.
        Empty list if none found or on error.
    """
    try:
        # %H = sha, %B = raw body (subject + body). Use NUL byte (%x00) as a
        # field separator and a per-commit terminator so we can split unambiguously.
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "--all",
                "--format=%H%x00%B%x00",
                f"--grep=#{issue_number}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    matches: list[tuple[str, str, str]] = []
    raw = result.stdout
    if not raw:
        return matches

    # Records are terminated by NUL+NUL (end of body NUL, then next commit start
    # or end of stream). Split on the outermost record boundary.
    # Each record: <sha>\x00<full_body>\x00
    parts = raw.split("\x00")
    # parts will be: [sha1, body1, sha2, body2, ..., ""]  (trailing empty)
    i = 0
    while i + 1 < len(parts):
        sha = parts[i].strip()
        body = parts[i + 1]
        i += 2
        if not sha:
            continue
        # Subject = first line of body.
        subject = body.splitlines()[0] if body else ""
        matches.append((sha, subject, body))
    return matches


def _git_log_pickaxe(repo_root: Path, symbol: str) -> Optional[Tuple[str, str]]:
    """Search ALL branches for a commit that introduced/removed ``symbol``.

    Args:
        repo_root: Root directory of the git repository.
        symbol: Code symbol or path fragment to search for.

    Returns:
        Tuple of (sha, commit_subject) if found, None otherwise.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "--all",
                "-S",
                symbol,
                "--oneline",
                "-1",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
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
) -> Optional[MatchResult]:
    """Return a MatchResult if a prior merged commit likely implements the issue.

    Strategy:
      1. Search ALL branches for commits referencing ``#<issue_number>``.
      2. Classify each match (closes / mention / anti / none).
      3. Skip anti-marker results (the commit explicitly says NOT done).
      4. For closes matches, require the commit to be an ancestor of HEAD;
         otherwise downgrade to "stale_branch" and skip.
      5. Return the first valid "closes" match.
      6. Fall back to symbol pickaxe search (returns classification "mention")
         only when no commit references #N at all.

    Returns None when no qualifying match is found. The caller should treat
    None as "issue is NOT already done — proceed normally".

    Args:
        issue_number: GitHub issue number to check.
        title: Issue title text.
        body: Issue body text.
        repo_root: Root directory of the git repository.

    Returns:
        MatchResult(sha, subject, classification) when a merged commit closes
        the issue. classification will always be "closes" for non-None returns
        from this function (anti / stale_branch results are filtered out).
        None when no qualifying match is found.
    """
    grep_matches = _git_log_grep_issue(repo_root, issue_number)

    # First pass: look for an explicit closure on a HEAD-ancestor commit.
    for sha, subject, commit_body in grep_matches:
        classification = _classify_issue_in_body(commit_body, issue_number)
        if classification == "anti":
            # Explicit signal NOT done.
            continue
        if classification == "closes":
            if _is_ancestor_of_head(repo_root, sha):
                return MatchResult(sha=sha, subject=subject, classification="closes")
            # Closes the issue but on an unmerged side branch.
            continue
        # "mention" or "none" — skip; require a closure marker for a confident match.

    # Fall back to pickaxe only when no grep match referenced the issue at all.
    # If grep found references but none qualified (all anti / stale_branch / mention),
    # respect that signal and return None.
    if grep_matches:
        return None

    for sym in _extract_symbols(title, body, max_count=5):
        result = _git_log_pickaxe(repo_root, sym)
        if result is not None:
            sha, subject = result
            # Pickaxe results have no body-level closure marker — classify as mention.
            # Per spec, only "closes" matches are returned, so skip.
            # (Kept here for future extension; pickaxe is currently advisory only.)
            return MatchResult(sha=sha, subject=subject, classification="mention")
    return None
