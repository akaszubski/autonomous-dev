"""Pure-function helpers for auto-revert of regressing drain commits (#1292, ADR-002 Phase C Invariant 4)."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_GIT_SHA_RE = re.compile(r"^[a-f0-9]{40}$")


def _is_valid_sha(s: str) -> bool:
    """Strict 40-char lowercase-hex git SHA validation.

    Defense-in-depth against CWE-88 (argument injection). Even with
    shell=False, a malicious SHA-shaped JSONL value like '--exec=cmd'
    would be interpreted by git as a flag. Strict hex validation rejects
    any value that could be misread as a git option.
    """
    return bool(s) and bool(_GIT_SHA_RE.match(s))


def detect_regression(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Tuple[bool, str]:
    """Determine if `after` shows a regression vs `before`.

    Regression := after.failing_tests > before.failing_tests (strict >).
    Conservative: returns (False, "metrics_incomplete") when either snapshot
    has a non-None error key or either failing_tests value is None.

    The conservative path means autonomous revert never fires on incomplete
    data — operators have to investigate manually. Better a false-negative
    revert than a thrashing revert loop on bad metrics.

    Returns:
        (is_regression, reason): reason is "no_regression",
        "metrics_incomplete", or "failing_tests_increased: N -> M".
    """
    if before.get("error") is not None or after.get("error") is not None:
        return (False, "metrics_incomplete")
    b_fail = before.get("failing_tests")
    a_fail = after.get("failing_tests")
    if b_fail is None or a_fail is None:
        return (False, "metrics_incomplete")
    if a_fail > b_fail:
        return (True, f"failing_tests_increased: {b_fail} -> {a_fail}")
    return (False, "no_regression")


def find_fix_commits(
    repo: Path,
    drain_sha: str,
    since: datetime,
    env: Dict[str, str],
    *,
    timeout: int = 30,
) -> List[str]:
    """Return commits authored after `since` whose message references drain_sha.

    Uses: git log --since=<ISO> --grep=<short_sha> --format=%H HEAD
    Short SHA is the first 7 characters of drain_sha (standard git convention).

    Returns empty list on any subprocess failure (treated as "no fix found"
    so revert proceeds — conservative for autonomy: prefer reverting an
    unfixed regression over letting one linger).
    """
    if not _is_valid_sha(drain_sha):
        return []
    short_sha = drain_sha[:7]
    since_iso = since.astimezone(timezone.utc).isoformat()
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since_iso}",
             f"--grep={short_sha}", "--format=%H", "HEAD"],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    # Exclude the drain_sha itself (the drain commit MAY contain its own short SHA in body)
    return [sha for sha in lines if sha != drain_sha]


def revert_drain_commit(
    repo: Path,
    drain_sha: str,
    env: Dict[str, str],
    *,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Run `git revert --no-edit <drain_sha>`.

    On success: returns {status: "reverted", revert_sha: <new HEAD SHA>, error: None}.
    On merge conflict: aborts (git revert --abort), returns
        {status: "conflict", revert_sha: None, error: <stderr>}.
    On any other failure: best-effort restore HEAD, returns
        {status: "error", revert_sha: None, error: <reason>}.

    Always leaves working tree in a clean state when possible.
    """
    if not _is_valid_sha(drain_sha):
        return {"status": "error", "revert_sha": None, "error": "malformed_sha"}

    try:
        result = subprocess.run(
            ["git", "revert", "--no-edit", drain_sha],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _try_abort_revert(repo, env)
        return {"status": "error", "revert_sha": None, "error": "timeout"}
    except (FileNotFoundError, OSError) as exc:
        return {"status": "error", "revert_sha": None, "error": f"subprocess_failed: {exc}"}

    if result.returncode == 0:
        # Read new HEAD SHA
        try:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo),
                env=env,
                capture_output=True,
                text=True,
                shell=False,
                check=False,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return {"status": "error", "revert_sha": None, "error": "head_read_failed"}
        if head.returncode != 0:
            return {"status": "error", "revert_sha": None, "error": "head_read_failed"}
        return {"status": "reverted", "revert_sha": head.stdout.strip(), "error": None}

    # Non-zero — likely conflict. Abort and report.
    stderr_text = (result.stderr or "") + (result.stdout or "")
    _try_abort_revert(repo, env)
    if "conflict" in stderr_text.lower() or "could not revert" in stderr_text.lower():
        return {"status": "conflict", "revert_sha": None, "error": stderr_text.strip()[:500]}
    return {"status": "error", "revert_sha": None, "error": stderr_text.strip()[:500]}


def _try_abort_revert(repo: Path, env: Dict[str, str]) -> None:
    """Best-effort: abort an in-progress revert and clean working tree."""
    try:
        subprocess.run(
            ["git", "revert", "--abort"],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=15,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["git", "checkout", "-f", "HEAD"],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=15,
        )
    except Exception:
        pass


def ensure_drain_reverted_label_exists(
    repo: Path,
    env: Dict[str, str],
    *,
    timeout: int = 30,
) -> bool:
    """Idempotent: ensure the 'drain-reverted' label exists on the GH repo.

    Returns True if label exists (or was created); False on unexpected error.
    Catches "already exists" specifically — exit 1 with stderr containing
    "already exists" means the label is already there and that is success.
    """
    try:
        result = subprocess.run(
            ["gh", "label", "create", "drain-reverted",
             "--description", "Drain commit auto-reverted due to regression",
             "--color", "d93f0b"],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    if result.returncode == 0:
        return True
    stderr = (result.stderr or "").lower()
    if "already exists" in stderr or "name already exists" in stderr:
        return True
    return False


def reopen_issues_with_label(
    repo: Path,
    issue_numbers: List[int],
    drain_sha: str,
    revert_sha: str,
    env: Dict[str, str],
    *,
    timeout: int = 30,
) -> Dict[int, str]:
    """Reopen each issue and add 'drain-reverted' label + explanatory comment.

    Per issue, runs (in order):
      1. gh issue reopen N
      2. gh issue edit N --add-label drain-reverted
      3. gh issue comment N --body "..."

    Returns dict mapping issue_number to outcome:
      "reopened" | "already_open" | "reopen_failed" |
      "label_failed" | "comment_failed" | "error"

    Failures per-issue do not stop processing other issues.
    """
    outcomes: Dict[int, str] = {}
    comment_body = (
        f"This issue was auto-reopened because the drain commit `{drain_sha[:7]}` "
        f"introduced a regression (new failing tests). The drain was reverted "
        f"in commit `{revert_sha[:7]}`. See ADR-002 Phase C Invariant 4."
    )
    for n in issue_numbers:
        # 1. reopen
        try:
            r = subprocess.run(
                ["gh", "issue", "reopen", str(n)],
                cwd=str(repo), env=env,
                capture_output=True, text=True,
                shell=False, check=False, timeout=timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            outcomes[n] = "error"
            continue
        if r.returncode != 0:
            stderr = (r.stderr or "").lower()
            if "already open" in stderr or "is already open" in stderr:
                outcomes[n] = "already_open"
            else:
                outcomes[n] = "reopen_failed"
                continue
        # 2. add label
        try:
            r2 = subprocess.run(
                ["gh", "issue", "edit", str(n), "--add-label", "drain-reverted"],
                cwd=str(repo), env=env,
                capture_output=True, text=True,
                shell=False, check=False, timeout=timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            outcomes[n] = "label_failed"
            continue
        if r2.returncode != 0:
            outcomes[n] = "label_failed"
            continue
        # 3. comment
        try:
            r3 = subprocess.run(
                ["gh", "issue", "comment", str(n), "--body", comment_body],
                cwd=str(repo), env=env,
                capture_output=True, text=True,
                shell=False, check=False, timeout=timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            outcomes[n] = "comment_failed"
            continue
        if r3.returncode != 0:
            outcomes[n] = "comment_failed"
            continue
        # Only override "already_open" if we got here successfully
        if outcomes.get(n) != "already_open":
            outcomes[n] = "reopened"
    return outcomes


__all__ = [
    "detect_regression",
    "find_fix_commits",
    "revert_drain_commit",
    "ensure_drain_reverted_label_exists",
    "reopen_issues_with_label",
]
