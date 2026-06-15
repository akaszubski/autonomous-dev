"""Plan freshness re-verification helpers (Issue #1175).

Pure functions used by STEP 4.8 of `commands/implement.md` to verify that
file paths referenced in a pre-validated plan still exist on disk before
seeding the planner. This is the complementary T2 fix to the prompt-integrity
work in Issue #1172 — it catches the case where a plan was previously
validated but the referenced files have since been moved, renamed, or
deleted.

The module exports two pure functions with no side effects, no logging, and
no global state:

- `extract_referenced_paths(plan_content)` — parse a plan markdown blob and
  return a deduplicated, sorted list of file-path-like tokens.
- `verify_paths_exist(paths, repo_root)` — return the subset of `paths` that
  do NOT exist under `repo_root`, sorted alphabetically for deterministic
  output.

The file-path regex mirrors STEP 5.5c structural validation in
`commands/implement.md` (`[\\w/.-]{1,512}\\.(py|md|json|yaml|sh|ts|js)`).
The ``{1,512}`` upper bound on the character-class run is a defensive cap
against pathological inputs that could exercise quadratic regex behaviour
on the unbounded ``+`` quantifier (Issue #1194). 512 chars comfortably
exceeds any plausible file path while keeping worst-case matching
bounded. Keep the two in sync if either changes.
"""

from __future__ import annotations

import re
from pathlib import Path

# Mirror of the STEP 5.5c regex in commands/implement.md. If you change the
# extension list here, update the prose in 5.5c (and vice-versa).
# The ``{1,512}`` upper bound caps the character-class run length to defuse
# the ReDoS surface on the previously-unbounded ``+`` quantifier (Issue #1194).
_FILE_PATH_REGEX = re.compile(r"[\w/.-]{1,512}\.(py|md|json|yaml|sh|ts|js)")


def extract_referenced_paths(plan_content: str) -> list[str]:
    """Extract file paths from plan markdown using the STEP 5.5c regex.

    Args:
        plan_content: Full plan markdown blob (the `PRE_VALIDATED_PLAN_CONTENT`
            stored by STEP 4.7). May be empty.

    Returns:
        Deduplicated, sorted list of path strings matching the regex
        ``[\\w/.-]{1,512}\\.(py|md|json|yaml|sh|ts|js)``. The ``{1,512}``
        upper bound is the ReDoS cap from Issue #1194 — character-class
        runs longer than 512 chars do not match. Sort order is
        deterministic (lexicographic) so callers can rely on stable output.
    """
    if not plan_content:
        return []
    # `findall` with a single-group pattern returns just the group; use
    # `finditer` to recover the full match.
    matches = {m.group(0) for m in _FILE_PATH_REGEX.finditer(plan_content)}
    return sorted(matches)


def verify_paths_exist(paths: list[str], repo_root: Path) -> list[str]:
    """Return paths from `paths` that do NOT exist under `repo_root`.

    Args:
        paths: List of path strings (typically the output of
            `extract_referenced_paths`). May be empty.
        repo_root: Repository root used to resolve relative path strings.
            Absolute paths in `paths` are checked as-is.

    Returns:
        Sorted list of path strings whose resolved location does not exist
        on disk. Empty list means every referenced path was found. Paths
        that escape `repo_root` via traversal (e.g., ``../../etc/passwd``)
        or that fail to resolve are treated as missing — `verify_paths_exist`
        never probes the filesystem outside `repo_root` (Issue #1193).
    """
    repo_root_resolved = repo_root.resolve()
    missing: list[str] = []
    for path_str in paths:
        candidate = Path(path_str)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError):
            missing.append(path_str)
            continue
        # Canonicalize-then-contain: traversal outside repo_root => missing.
        try:
            resolved.relative_to(repo_root_resolved)
        except ValueError:
            missing.append(path_str)
            continue
        if not resolved.exists():
            missing.append(path_str)
    return sorted(missing)
