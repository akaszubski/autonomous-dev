"""Prior-art search: mechanical closed-issue lookup for the planner.

Issue #1669 background: on 2026-08-25 a /implement run produced a plan to
hand-roll a mutation engine, and only the plan-critic discovered that
mutation testing had already been shipped and closed under #770. The
"search closed issues first" rule was in always-loaded prose and was
skipped by both the coordinator and the planner. Prose is advisory,
never enforcement (INV-1).

This module ships the *mechanism* half: a deterministic, network-tolerant
closed-issue lookup that returns machine-readable hits. Wiring it into
``commands/implement.md`` so it runs mechanically before the planner is
dispatched is deferred to a follow-up — #1669 stays OPEN for that
wiring. See the commit body of the drain that landed this file.

Contract:
    * NEVER raises. NEVER blocks. Returns ``[]`` on any failure.
    * Empty result for a genuinely novel topic is legitimate — not a
      failure signal.
    * Degrades: gh missing / unauthenticated / no network → falls back
      to ``git log --all --grep``; if that also fails, returns ``[]``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

_GH_TIMEOUT_SECONDS = 15
_GIT_TIMEOUT_SECONDS = 10
_LIMIT_PER_KEYWORD = 10


class _GhFailure(Exception):
    """Sentinel: ``gh`` was not usable (missing / timeout / non-zero / bad JSON).

    Distinct from ``gh`` succeeding with an empty result, so callers can
    decide whether to try the git-log fallback (only on failure).
    """


def _run_gh_search(keyword: str, repo_root: Path) -> list[dict]:
    """Query ``gh issue list --state closed`` for one keyword.

    Returns the parsed list on success (possibly empty). Raises
    ``_GhFailure`` when gh is unusable — the caller then tries the
    git-log fallback. Never raises anything else.
    """

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--state",
                "closed",
                "--search",
                keyword,
                "--json",
                "number,title,state,closedAt",
                "--limit",
                str(_LIMIT_PER_KEYWORD),
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise _GhFailure(str(exc)) from exc

    if result.returncode != 0:
        raise _GhFailure(f"gh exit {result.returncode}: {result.stderr!r}")

    stdout = (result.stdout or "").strip()
    if not stdout:
        # gh SUCCEEDED with no output — treat as "no prior art via gh"
        # (do not fall back to git-log; empty is a valid answer).
        return []
    try:
        parsed = json.loads(stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        raise _GhFailure(f"malformed gh JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise _GhFailure(f"gh returned non-list JSON: {type(parsed).__name__}")
    return [item for item in parsed if isinstance(item, dict)]


def _run_git_grep_fallback(keyword: str, repo_root: Path) -> list[dict]:
    """Last-resort offline fallback via ``git log --all --grep``.

    Emits synthetic records with ``number=None`` since git log has no
    issue-number context — callers can still surface the hits as
    "possible prior art" without a #N link. Returns ``[]`` on any error.
    """

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--all",
                "--grep",
                keyword,
                "--format=%H %s",
                "-n",
                "5",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    if result.returncode != 0:
        return []

    hits: list[dict] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        sha, _, subject = line.partition(" ")
        hits.append(
            {
                "number": None,
                "title": subject,
                "state": "GIT_LOG",
                "sha": sha,
            }
        )
    return hits


def search_prior_art(
    keywords: Iterable[str],
    repo_root: Path | None = None,
) -> list[dict]:
    """Return closed-issue prior-art hits for the given keywords.

    Parameters
    ----------
    keywords:
        One or more keyword strings to search for. Blank / whitespace-only
        entries are ignored. Duplicates are permitted; the returned list
        is deduplicated by ``number`` (or by ``sha`` for git-log hits).
    repo_root:
        Working directory for the underlying subprocess calls. Defaults
        to the current process cwd.

    Returns
    -------
    list[dict]
        Zero or more hits. Each ``gh``-sourced hit has keys
        ``number``, ``title``, ``state``, ``closedAt``. Git-log hits
        have ``number=None``, ``state="GIT_LOG"``, and ``sha``.
        NEVER raises. Empty list is a valid, non-error result.
    """

    cwd = (repo_root or Path.cwd()).resolve()
    seen_numbers: set[int] = set()
    seen_shas: set[str] = set()
    aggregated: list[dict] = []

    for kw in keywords:
        if not isinstance(kw, str):
            continue
        kw = kw.strip()
        if not kw:
            continue

        try:
            gh_hits = _run_gh_search(kw, cwd)
        except _GhFailure:
            # gh not usable — fall back to git-log (offline, degraded).
            for hit in _run_git_grep_fallback(kw, cwd):
                sha = hit.get("sha", "")
                if sha and sha in seen_shas:
                    continue
                if sha:
                    seen_shas.add(sha)
                aggregated.append(hit)
            continue

        # gh succeeded (possibly with empty results — that is a valid
        # answer, not a signal to fall back).
        for hit in gh_hits:
            n = hit.get("number")
            if isinstance(n, int) and n in seen_numbers:
                continue
            if isinstance(n, int):
                seen_numbers.add(n)
            aggregated.append(hit)

    return aggregated


def _main(argv: list[str]) -> int:
    """CLI entry: ``python3 prior_art_search.py <keyword> [<keyword> ...]``.

    Prints the JSON result to stdout. Always exits 0 — the whole point
    of the module is deterministic non-blocking.
    """

    keywords = [a for a in argv if a.strip()]
    hits = search_prior_art(keywords)
    print(json.dumps(hits, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))
