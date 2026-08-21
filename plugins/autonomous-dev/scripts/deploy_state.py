#!/usr/bin/env python3
"""Deploy provenance: make what is EXECUTING knowable and attributable.

WHY THIS EXISTS (Issue #1610)
-----------------------------
``scripts/deploy-all.sh`` copies from the WORKING TREE, not from ``HEAD``. Any
uncommitted work-in-progress under ``plugins/autonomous-dev/`` reached the
executing hook stack the moment anyone deployed — routing around the reviewer,
the security auditor, doc-master and the commit gate simultaneously, because
every one of those gates sits on the path to a *commit*.

Measured on this machine while #1588 was under review — one file, three copies:

  HEAD (committed)              347 lines,   0 HookDecision, 0 fixes
  .claude/lib (EXECUTING)       684 lines,  15 HookDecision, 0 fixes, 1 silent
                                            fail-open the audit had BLOCKED
  working tree (staged)         892 lines,  21 HookDecision, 3 fixes

The executing copy existed in **no commit** — an intermediate snapshot of
somebody's work-in-progress frozen onto the running system. Three properties
made it worth a dedicated mechanism rather than a warning:

1. **Partial deployment produced something worse than either endpoint.** Had
   deploy tracked HEAD, the running system would have carried the 347-line
   version — no HookDecision, no silent-emission path, safe by absence.
2. **Git could not undo it.** The content corresponded to no object, so there
   was nothing to revert to. "What is running?" was unanswerable from the
   repository.
3. **It defeats every gate at once**, and the stronger commit-time enforcement
   gets, the more attractive that route becomes.

HOW "UNCOMMITTED" IS DERIVED — AND WHY NOT FROM ``git status``
--------------------------------------------------------------
The first version of this file derived the dirty set from
``git status --porcelain --untracked-files=all``. That derivation **failed
open**, and the docstring that shipped with it asserted a byte-identity
property that was **false**. Measured on this repo 2026-08-22, before the fix:

    what the gate saw (no --ignored):        2 entries
    files it could NOT see (gitignored):    55  (46 outside __pycache__)
    already executing in a consumer repo:   38 ``,cover`` files, 13 .DS_Store,
                                            1 stray session markdown

``git status`` omits ignored paths; ``rsync -a`` ships them regardless. Three
further shapes broke the same parse: a source tree whose ``--source`` was not
the git toplevel discarded EVERY entry and returned ``[]`` (read as clean);
C-quoted non-ASCII filenames never matched a digest key; and a single directory
entry for an embedded repo stood in for its whole contents.

The derivation is therefore no longer a text parse of ``git status``. It is a
set comparison over the set that is actually shipped:

    shipped   = filesystem walk of plugin_src/<subdir>, minus DEPLOY_EXCLUDES
                (the same exclusions rsync is given, so the two cannot diverge)
    in_head   = git ls-tree -r -z HEAD -- <subdirs>
    modified  = git diff --name-only -z HEAD -- <subdirs>

    uncommitted = (shipped - in_head)  |  (modified & shipped)

``shipped - in_head`` is one measurement that catches untracked, ignored AND
staged-new files at once; it cannot be scoped to the shape that prompted it,
and it cannot be silently empty without the deployed set itself being empty.
Every path is NUL-separated, so quoting and newlines are non-issues.

Only with THAT derivation is the following true, and it is now true by
construction: when the gate reports clean, every path this script ships is
present in HEAD with identical content, so "deploy from HEAD" is achieved
WITHOUT changing the copy step.

WHAT THIS DOES *NOT* DO
-----------------------
It does not change WHERE anything is copied. It does narrow WHAT is copied, by
one measured class: build artifacts (see DEPLOY_EXCLUDES). Those are excluded
from the *deployed set*, not merely from the gate — shipping them was itself a
(small) defect, and excluding them only from the gate would have left the gate
blind to the whole ignored-file class rather than to one enumerated slice of it.

THREE SUBCOMMANDS
-----------------
``gate``   Refuse a deploy whose deployed subdirs carry content in no commit,
           unless ``--dirty`` is passed. Refusing (rather than warning) is
           deliberate: a warning that fires routinely is ignored, which is the
           cry-wolf failure this project treats as a defect in its own right.

``stamp``  Write ``<target>/.deploy-state.json`` recording the source commit,
           the dirty flag, every uncommitted file shipped, and a content digest
           per deployed file. This converts "what is running?" from
           unanswerable into a file read — on any machine, without git.

``check``  Re-digest the EXECUTING tree and report drift, in BOTH directions:
           recorded-but-changed/missing, and present-but-unrecorded. Runs from
           an installed ``.claude/scripts/`` in a consumer repo with no git and
           no plugin source, following the #1586 precedent that verification
           artifacts must ship and run per-repo rather than existing only as
           tests here.

MEASURED EXCLUSIONS
-------------------
Measured on this repo 2026-08-22: 1,721 files under the eight deployed subdirs,
of which 1,160 are build artifacts (1,055 ``__pycache__`` contents plus 105
coverage/OS strays) — 561 tracked files remain.

Of those 561, EXACTLY ONE is excluded: ``hooks/extensions/.gitkeep``, via the
deliberate ``extensions/`` directory exclusion that Issue #560 exists to
preserve (that directory holds consumer-local additions ``--delete`` must not
remove, so the placeholder that creates it is not shipped either). The
behaviour is correct; an earlier draft of this docstring claimed "zero source
files are excluded", which was false by one. It was measured as zero because
the measurement reimplemented the predicate with ``fnmatch`` instead of calling
``is_excluded()`` — ``extensions/`` carries a trailing slash and does not
fnmatch the bare path component. The claim is now enforced rather than
asserted: a regression test runs ``is_excluded()`` over ``git ls-files`` for
the deployed subdirs and pins the excluded set to that one named path, so a
pattern that starts hiding a tracked file fails a test rather than a manual
count.

Every OTHER excluded path is a regenerated artifact or an OS turd. With the
exclusions applied, the gate on this repo names exactly 3 paths, all genuine.
The counts are written into the artifact so the exclusion stays measured
rather than assumed.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

# The subdirectories deploy-all.sh copies (its $SUBDIRS). The global target
# receives only a subset; the walk simply skips those that are absent.
# PARITY: tests/regression/regression/test_issue_1610_deploy_state.py asserts
# set equality against the SUBDIRS assignment in scripts/deploy-all.sh, so a
# subdir added to one and not the other fails a test instead of silently
# removing itself from the gate's coverage.
DEPLOY_SUBDIRS: tuple[str, ...] = (
    "hooks",
    "commands",
    "agents",
    "lib",
    "templates",
    "config",
    "skills",
    "scripts",
)

# Directory names never shipped and never digested. ``extensions`` is here
# because rsync has always excluded it (Issue #560: it holds consumer-local
# additions that --delete must not remove); the rest are build artifacts.
EXCLUDED_DIR_NAMES: tuple[str, ...] = (
    "__pycache__",
    "extensions",
    "htmlcov",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)

# File globs never shipped and never digested. Every entry was OBSERVED in the
# deployed set of a consumer repo on 2026-08-22 (38 ``,cover``, 13 .DS_Store,
# a stray coverage.xml and a .backup) or is the direct machine-generated
# sibling of one. They are gitignored, so ``git status`` could not see them and
# the pre-fix gate shipped them while reporting a clean tree.
EXCLUDED_FILE_GLOBS: tuple[str, ...] = (
    "*.pyc",
    "*.pyo",
    "*,cover",
    ".DS_Store",
    ".coverage",
    ".coverage.*",
    "coverage.xml",
    "*.backup",
    "*.orig",
    "*.rej",
    "*.swp",
)

# Directory PATHS (not bare names) never shipped and never digested, matched
# against any trailing run of path components.
#
# Session/pipeline working files land under deployed subdirs because several
# hooks write to the RELATIVE path ``Path("docs/sessions")``, so a hook run with
# cwd=plugins/autonomous-dev/hooks creates
# ``hooks/docs/sessions/<ts>-session.md``. One was already shipped into a
# consumer repo.
#
# NARROWED (Issue #1610 final remediation). The previous form was three FILENAME
# globs — ``*-session.md``, ``*-pipeline.json``, ``*.pipeline.json``. A filename
# class is a blind spot with a public name: anything ``is_excluded()`` hides is
# invisible to the digest map AND to ``check``'s reverse comparison, in BOTH
# directions, so an attacker-named ``payload-session.md`` rode into the
# executing tree unmeasured. Measured 2026-08-22 before narrowing: across the
# whole repo and every deployed tree, EVERY file matching any of the three globs
# lived under ``docs/sessions/`` — one instance,
# ``hooks/docs/sessions/20260606-132224-session.md``, and zero instances of
# either pipeline glob anywhere. So the filename classes bought no coverage the
# path exclusion does not, and cost an unmeasured naming class.
#
# Scoped to the observed path rather than to ``docs/`` wholesale, because
# excluding ``docs/`` would also drop the tracked ``skills/*/docs`` trees — a
# scoping control asserts that still ships. The pattern form is what rsync
# matches against the end of a pathname, verified empirically rather than read
# off the man page: it excludes ``docs/sessions/`` at any depth and leaves
# ``skills/x/docs/authentication.md`` and a bare ``attacker-named-session.md``
# delivered, and therefore measured.
EXCLUDED_DIR_PATHS: tuple[str, ...] = ("docs/sessions",)

STATE_FILENAME = ".deploy-state.json"
SCHEMA_VERSION = 2
DIGEST_ALGORITHM = "sha256"
SYMLINK_PREFIX = "symlink:"
DEFAULT_PLUGIN_REL = "plugins/autonomous-dev"

EXIT_CLEAN = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2


class DeployStateError(Exception):
    """Deploy provenance could not be established."""


def rsync_exclude_patterns() -> tuple[str, ...]:
    """Return the exclusions in rsync ``--exclude=`` pattern form.

    Returns:
        Directory patterns first (trailing slash), then file globs. The
        deploy-all.sh ``DEPLOY_EXCLUDES`` array must match this set exactly;
        a regression test asserts it.
    """
    return tuple(
        [f"{name}/" for name in EXCLUDED_DIR_NAMES]
        + [f"{path}/" for path in EXCLUDED_DIR_PATHS]
        + list(EXCLUDED_FILE_GLOBS)
    )


def _matches_excluded_dir_path(rel: Path) -> bool:
    """Whether any trailing run of ``rel``'s components equals an excluded dir path.

    Mirrors rsync's rule for a pattern that contains a ``/`` and is not anchored
    with a leading ``/``: it is matched against the END of the pathname, at any
    depth. So ``docs/sessions`` matches both ``docs/sessions/x.md`` and
    ``hooks/docs/sessions/x.md``, and matches the directory itself.
    """
    parts = rel.parts
    for excluded in EXCLUDED_DIR_PATHS:
        segments = tuple(excluded.split("/"))
        width = len(segments)
        for start in range(len(parts) - width + 1):
            if parts[start : start + width] == segments:
                return True
    return False


def is_excluded(rel: Path) -> bool:
    """Whether ``rel`` (relative to a deploy root) is excluded from the deployed set.

    Args:
        rel: Path relative to a deploy root. May name a file OR a directory.

    Returns:
        True if rsync is given a pattern that skips it, which is also the set
        this tool refuses to digest. Anything True here is invisible to the
        digest map and to ``check``'s reverse comparison in BOTH directions, so
        every pattern is measured before it is added, never assumed.
    """
    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
        return True
    if rel.name in EXCLUDED_DIR_NAMES:
        return True
    if _matches_excluded_dir_path(rel):
        return True
    return any(fnmatch.fnmatch(rel.name, pattern) for pattern in EXCLUDED_FILE_GLOBS)


def _iter_deployable(root: Path, base: Path) -> Iterator[Path]:
    """Yield every path under ``root`` that rsync would ship, in stable order.

    Symlinks are yielded rather than skipped: ``rsync -a`` preserves them, so a
    skipped symlink would be permanently unrecorded and therefore permanently
    unverifiable — a blind spot in the very tool meant to remove blind spots.

    Args:
        root: Directory to walk.
        base: Root the returned paths are conceptually relative to.

    Yields:
        Regular files and symlinks (including symlinks to directories).
    """
    if not root.is_dir() or root.is_symlink():
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        descend: list[str] = []
        for name in sorted(dirnames):
            child = here / name
            # One predicate for directories AND files, so a path-shaped
            # exclusion (``docs/sessions``) prunes the subtree exactly the way
            # a name-shaped one (``__pycache__``) always did.
            if is_excluded(child.relative_to(base)):
                continue
            if child.is_symlink():
                # A symlinked directory is one rsync entry, not a subtree.
                yield child
            else:
                descend.append(name)
        dirnames[:] = descend
        for name in sorted(filenames):
            child = here / name
            if is_excluded(child.relative_to(base)):
                continue
            yield child


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    """Run git in ``repo`` and return stdout.

    Args:
        repo: Repository root.
        *args: git arguments.

    Returns:
        Captured stdout.

    Raises:
        DeployStateError: If git is unavailable or the command fails.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError) as exc:  # git missing / bad argv
        raise DeployStateError(
            f"Could not run git in {repo}: {exc}\n"
            f"Expected: a git working copy of autonomous-dev\n"
            f"See: docs/RUNBOOK.md"
        ) from exc
    if result.returncode != 0:
        raise DeployStateError(
            f"git {' '.join(args)} failed in {repo} (exit {result.returncode})\n"
            f"Expected: a git working copy of autonomous-dev\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result.stdout


def head_commit(repo: Path) -> str:
    """Return the full SHA of HEAD in ``repo``."""
    return _git(repo, "rev-parse", "HEAD").strip()


def git_toplevel(repo: Path) -> Path:
    """Return the git toplevel git itself resolves for ``repo``."""
    return Path(_git(repo, "rev-parse", "--show-toplevel").strip()).resolve()


def require_source_is_toplevel(repo: Path) -> Path:
    """Refuse to guess when ``--source`` is not the repository root.

    git finds a repository by walking UP, so a checkout nested inside another
    git repository resolves to the OUTER toplevel. Every path git then emits is
    relative to that outer root. The pre-fix code filtered those paths by an
    inner-root prefix, matched none, and returned an empty list — which reads as
    "clean". It did not break loudly; it asserted the opposite of the truth and
    permitted (Issue #1610 remediation, BLOCKING 2).

    Args:
        repo: The resolved ``--source`` path.

    Returns:
        The verified toplevel (equal to ``repo``).

    Raises:
        DeployStateError: If git resolves a different toplevel.
    """
    top = git_toplevel(repo)
    if top != repo.resolve():
        raise DeployStateError(
            f"--source {repo} is not the git toplevel; git resolves it to {top}\n"
            f"Expected: --source to BE the repository root, because every path git\n"
            f"          reports is relative to the toplevel it found by walking up.\n"
            f"          Guessing here returns an empty dirty set, which reads as CLEAN.\n"
            f"See: scripts/deploy-all.sh (REPO_DIR)"
        )
    return top


def _plugin_rel(repo: Path, plugin_src: Path) -> str:
    """Return ``plugin_src`` relative to ``repo`` as a POSIX path."""
    try:
        return plugin_src.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as exc:
        raise DeployStateError(
            f"Plugin source {plugin_src} is not inside the source repo {repo}\n"
            f"Expected: <repo>/plugins/autonomous-dev\n"
            f"See: scripts/deploy-all.sh"
        ) from exc


def _nul_paths(raw: str, prefix: str) -> set[str]:
    """Split NUL-separated git output and strip a ``<prefix>/`` from each path."""
    head = prefix + "/"
    return {entry[len(head) :] for entry in raw.split("\0") if entry.startswith(head)}


def source_deployed_files(plugin_src: Path) -> set[str]:
    """Every path rsync would ship, relative to ``plugin_src``.

    This is the measurement the gate is derived from. It is a filesystem walk,
    not a git query, so it sees untracked and gitignored files identically to
    the way ``rsync -a`` does.
    """
    shipped: set[str] = set()
    for subdir in DEPLOY_SUBDIRS:
        for path in _iter_deployable(plugin_src / subdir, plugin_src):
            shipped.add(path.relative_to(plugin_src).as_posix())
    return shipped


def uncommitted_deploy_paths(repo: Path, plugin_src: Path) -> list[str]:
    """List DEPLOYED files whose content is not in HEAD.

    Scoped deliberately to ``plugin_src/<subdir>`` for each entry in
    ``DEPLOY_SUBDIRS``. Dirt anywhere else (``README.md``, ``docs/``, the repo's
    own ``scripts/``) is never copied by deploy-all.sh, so counting it would
    make the gate fire routinely — the cry-wolf failure.

    Args:
        repo: Repository root (MUST be the git toplevel).
        plugin_src: Path to ``plugins/autonomous-dev``.

    Returns:
        Sorted plugin-relative POSIX paths, e.g. ``["lib/hook_safety.py"]``.

    Raises:
        DeployStateError: If git fails, or ``repo`` is not the git toplevel.
    """
    require_source_is_toplevel(repo)
    prefix = _plugin_rel(repo, plugin_src)
    pathspecs = [f"{prefix}/{subdir}" for subdir in DEPLOY_SUBDIRS]

    shipped = source_deployed_files(plugin_src)
    in_head = _nul_paths(
        _git(repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", *pathspecs),
        prefix,
    )
    modified = _nul_paths(
        _git(repo, "diff", "--name-only", "-z", "HEAD", "--", *pathspecs),
        prefix,
    )
    return sorted((shipped - in_head) | (modified & shipped))


def head_blob_matches(repo: Path, plugin_rel: str, rel: str, path: Path) -> bool:
    """Whether ``path``'s bytes are now the content HEAD holds for ``rel``.

    Used by ``check`` to self-heal: a file recorded as uncommitted at deploy
    time may have been committed since, with the executing bytes untouched. A
    check that stays red after the operator did the right thing is the one
    people learn to skip.
    """
    try:
        want = _git(repo, "rev-parse", f"HEAD:{plugin_rel}/{rel}").strip()
        have = _git(repo, "hash-object", "--", str(path)).strip()
    except DeployStateError:
        return False
    return bool(want) and want == have


# ---------------------------------------------------------------------------
# digests
# ---------------------------------------------------------------------------


def iter_deployed_files(target: Path) -> Iterable[Path]:
    """Yield every digestible entry in a deployed ``.claude`` tree.

    Args:
        target: The deployed directory (e.g. ``<repo>/.claude``).

    Yields:
        Regular files and symlinks under the deployed subdirs, excluding
        build artifacts (see ``DEPLOY_EXCLUDES``).
    """
    for subdir in DEPLOY_SUBDIRS:
        yield from _iter_deployable(target / subdir, target)


def count_excluded_files(target: Path) -> int:
    """Count entries the digest walk skipped, so the exclusion stays measured."""
    total = 0
    for subdir in DEPLOY_SUBDIRS:
        root = target / subdir
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                continue
            if is_excluded(path.relative_to(target)):
                total += 1
    return total


def digest_file(path: Path) -> str:
    """Return the sha256 hex digest of ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_entry(path: Path) -> str:
    """Return the recorded fingerprint for one deployed entry.

    Symlinks record ``symlink:<target>`` rather than the digest of whatever
    they point at, so that replacing a recorded regular file with a symlink —
    or repointing a recorded symlink — is drift, not a match.
    """
    if path.is_symlink():
        return SYMLINK_PREFIX + os.readlink(path)
    return digest_file(path)


def digest_tree(target: Path) -> dict[str, str]:
    """Map target-relative POSIX path -> fingerprint for every deployed entry."""
    return {
        path.relative_to(target).as_posix(): digest_entry(path)
        for path in iter_deployed_files(target)
    }


# ---------------------------------------------------------------------------
# state artifact
# ---------------------------------------------------------------------------


def match_uncommitted_to_target(
    uncommitted: Iterable[str], digests: dict[str, str], target: Path
) -> tuple[list[str], list[str]]:
    """Split the source-side uncommitted list against what THIS target received.

    Three outcomes, and none of them is a silent discard (Issue #1610
    remediation, BLOCKING 3). An intersection filter used as a correctness gate
    that drops what it cannot name reports ``dirty: false`` for a tree that is
    executing uncommitted content:

    * the path is a digest key -> shipped here
    * the path is a directory prefix of digest keys -> its contents shipped here
    * the path's subdir is absent from this target -> genuinely not shipped here
      (the global target receives three subdirs, not eight), dropped
    * anything else -> UNMATCHED, reported and forced to ``dirty: true``

    Args:
        uncommitted: Plugin-relative paths that are not in HEAD.
        digests: The digest map just computed for ``target``.
        target: The deployed directory.

    Returns:
        ``(shipped_here, unmatched)``, both sorted and deduplicated.
    """
    keys = set(digests)
    target_subdirs = {name for name in DEPLOY_SUBDIRS if (target / name).is_dir()}
    shipped: set[str] = set()
    unmatched: set[str] = set()
    for rel in uncommitted:
        top = rel.split("/", 1)[0]
        if top not in target_subdirs:
            continue  # this target never receives that subdir
        if rel in keys:
            shipped.add(rel)
            continue
        prefix = rel.rstrip("/") + "/"
        expanded = {key for key in keys if key.startswith(prefix)}
        if expanded:
            shipped.update(expanded)
        else:
            unmatched.add(rel)
    return sorted(shipped), sorted(unmatched)


def target_only_files(digests: dict[str, str], expected: set[str], target: Path) -> list[str]:
    """Digest keys present in the TARGET that no source file accounts for.

    Why this exists (Issue #1610 final remediation, BLOCKING A). ``check``'s
    reverse comparison computes ``executing - recorded``, which is empty BY
    CONSTRUCTION for a stray that was already sitting in the target when the
    record was built: ``digest_tree`` walks the target and records whatever it
    finds, so the stray is adopted into ``recorded`` as legitimate and every
    later check reports OK.

    That is not hypothetical. Two of the three transports do not delete —
    ``deploy_global`` (rsync without ``--delete``) and the remote copy — and
    remote targets have never been stamped, so the first remote stamp after
    this ships would adopt whatever has accumulated. A live instance on this
    machine: ``~/.claude/hooks/.claude/logs/activity/2026-06-06.jsonl``, 52,502
    bytes, in no commit, matching no exclusion glob.

    The fix is a set comparison against the SOURCE rather than against the
    record the source is about to become.

    Args:
        digests: The digest map just computed by walking ``target``.
        expected: ``source_deployed_files(plugin_src)`` — everything the source
            could legitimately have put there.
        target: The deployed directory, used to scope ``expected`` to the
            subdirs this target actually receives (the global target receives
            three of eight, so the extra members would never match a key).

    Returns:
        Sorted target-relative POSIX paths present in the target and absent
        from the source.
    """
    target_subdirs = {name for name in DEPLOY_SUBDIRS if (target / name).is_dir()}
    scoped = {rel for rel in expected if rel.split("/", 1)[0] in target_subdirs}
    return sorted(set(digests) - scoped)


def build_state(
    *,
    source_repo: Path,
    plugin_src: Path,
    target: Path,
    dirty_allowed: bool,
    uncommitted: list[str],
    commit: str,
    expected_source: Optional[set[str]] = None,
) -> dict:
    """Build the ``.deploy-state.json`` payload for one deployed target.

    Args:
        source_repo: Repository the deploy read from.
        plugin_src: ``plugins/autonomous-dev`` inside ``source_repo``.
        target: The deployed directory that was just written.
        dirty_allowed: Whether the operator passed ``--dirty``.
        uncommitted: Source-side uncommitted paths, computed ONCE by the caller
            (hoisted out of the per-target loop: it costs two git subprocesses
            and a filesystem walk, and is identical for every target).
        commit: Source HEAD sha, likewise computed once.
        expected_source: ``source_deployed_files(plugin_src)``, likewise hoisted
            by the caller. Computed here when absent so this stays usable
            standalone.

    Returns:
        A JSON-serialisable dict.
    """
    digests = digest_tree(target)
    shipped_uncommitted, unmatched = match_uncommitted_to_target(uncommitted, digests, target)
    if expected_source is None:
        expected_source = source_deployed_files(plugin_src)
    target_only = target_only_files(digests, expected_source, target)
    return {
        "schema": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_repo": str(source_repo),
        "source_plugin_rel": _plugin_rel(source_repo, plugin_src),
        "source_commit": commit,
        "source_commit_short": commit[:8],
        # Fail CLOSED: anything we could not attribute still marks the tree
        # dirty rather than vanishing from the record. ``target_only`` is in the
        # disjunction for the same reason ``unmatched`` is — a file the source
        # cannot account for is not made legitimate by being recorded.
        "dirty": bool(shipped_uncommitted or unmatched or target_only),
        "dirty_flag_used": dirty_allowed,
        "uncommitted_files": shipped_uncommitted,
        "unmatched_uncommitted": unmatched,
        "target_only": target_only,
        "digest_algorithm": DIGEST_ALGORITHM,
        "file_count": len(digests),
        "digests": digests,
        "excluded": {
            "patterns": list(rsync_exclude_patterns()),
            "file_count": count_excluded_files(target),
            "rationale": (
                "build artifacts and OS strays, excluded from the DEPLOYED SET "
                "(rsync is given the same patterns); exactly one tracked file is "
                "excluded — hooks/extensions/.gitkeep, via the deliberate "
                "extensions/ exclusion that Issue #560 exists to preserve"
            ),
        },
    }


def write_state(target: Path, state: dict) -> Path:
    """Write the state artifact atomically next to the deployed tree."""
    path = target / STATE_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def read_state(target: Path) -> tuple[Optional[dict], Optional[str]]:
    """Read the state artifact.

    A corrupt record is NOT an absent record: reporting "no deploy state" for a
    file that exists and is unparseable sends the operator to "re-deploy" when
    the real problem is a truncated write or tampering — which is inside this
    feature's threat model.

    Args:
        target: The deployed directory.

    Returns:
        ``(state, error)``. Exactly one is non-None, unless the file is absent,
        in which case both are None.
    """
    path = target / STATE_FILENAME
    if not path.is_file():
        return None, None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"unreadable ({exc})"
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        return None, f"not valid JSON ({exc})"
    if not isinstance(parsed, dict):
        return None, f"top level is {type(parsed).__name__}, expected object"
    return parsed, None


def unsafe_digest_keys(recorded: dict, target: Path) -> list[str]:
    """Return recorded keys that would escape the deployed tree (CWE-22).

    The record is untrusted input: it lives in a gitignored file that nothing
    reviews. ``Path(target) / key`` with an absolute key silently REPLACES the
    base, and ``..`` walks out of it, so an attacker with write access to the
    record could make ``check`` read and digest arbitrary files.

    Two checks, and this is the ONLY place either runs — a second, later
    containment check that ``continue``\\ s on failure would be a silent
    discard, which is the exact defect class this remediation removes:

    1. Lexical: absolute, ``..``-bearing, ``~``-prefixed or non-string keys.
    2. Resolved: the key's PARENT directory must still be under ``target``,
       which catches a symlinked directory inside the tree redirecting the
       join. The leaf is deliberately NOT resolved — a recorded file replaced
       by a symlink pointing outside must be reported as DRIFT, not silently
       skipped as an escape.

    Args:
        recorded: The digest map from the state artifact.
        target: The deployed directory the keys are relative to.

    Returns:
        Sorted list of offending keys.
    """
    unsafe: list[str] = []
    base = target.resolve()
    for key in recorded:
        if not isinstance(key, str) or not key:
            unsafe.append(repr(key))
            continue
        candidate = Path(key)
        if candidate.is_absolute() or ".." in candidate.parts or key.startswith("~"):
            unsafe.append(key)
            continue
        try:
            parent = (base / key).parent.resolve()
        except (OSError, ValueError):
            unsafe.append(key)
            continue
        if parent != base and base not in parent.parents:
            unsafe.append(key)
    return sorted(unsafe)


# ---------------------------------------------------------------------------
# activity log
# ---------------------------------------------------------------------------


def log_activity_row(repo: Path, states: list[dict], targets: list[Path]) -> Optional[Path]:
    """Append one findable row to ``.claude/logs/activity/``.

    That sink carries 6,472-23,997 rows/day and NO existing row carries a
    top-level ``type`` field, so ``"type": "deploy"`` selects exactly these
    rows. A row that is written but unfindable is the same defect as one never
    written.

    Failure to write is reported on stderr and swallowed: observability must
    never break the thing it observes, and it must never break a deploy.

    Args:
        repo: Source repository whose activity sink to append to.
        states: The per-target state payloads just written.
        targets: The deployed target directories.

    Returns:
        The log file written, or None on failure.
    """
    uncommitted: set[str] = set()
    unmatched: set[str] = set()
    target_only: set[str] = set()
    for state in states:
        uncommitted.update(state.get("uncommitted_files", []))
        unmatched.update(state.get("unmatched_uncommitted", []))
        target_only.update(state.get("target_only", []))
    first = states[0] if states else {}
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "deploy",
        "hook": "deploy_state",
        "source_commit": first.get("source_commit"),
        "source_commit_short": first.get("source_commit_short"),
        "dirty": any(s.get("dirty") for s in states),
        "uncommitted_files": sorted(uncommitted),
        "unmatched_uncommitted": sorted(unmatched),
        "target_only": sorted(target_only),
        "targets": [str(t) for t in targets],
        "file_count": sum(s.get("file_count", 0) for s in states),
    }
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = repo / ".claude" / "logs" / "activity" / f"{day}.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    except OSError as exc:
        sys.stderr.write(f"deploy_state: could not log activity row: {exc}\n")
        return None
    return path


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def cmd_gate(args: argparse.Namespace) -> int:
    """Refuse a deploy from a dirty tree unless ``--dirty`` was passed.

    Exit codes are three-valued on purpose, so the caller can tell a guard that
    REFUSED from a guard that BROKE — the distinction #1471 showed is the whole
    difference between deliberate and accidental fail-open:

        0 — permitted (clean tree, or dirty with --dirty)
        1 — REFUSED
        2 — provenance could not be determined; caller fails open, loudly
    """
    source = Path(args.source).resolve()
    plugin_src = Path(args.plugin_src).resolve()
    try:
        uncommitted = uncommitted_deploy_paths(source, plugin_src)
        commit_short = head_commit(source)[:8]
    except DeployStateError as exc:
        # Not a git checkout, or --source is not the toplevel: we cannot
        # establish provenance, and refusing here would break deploys from
        # tarball/installed layouts. Say so loudly, never silently.
        sys.stderr.write(f"DEPLOY-GATE: provenance UNKNOWN — {exc}\n")
        return EXIT_UNKNOWN

    if not uncommitted:
        print(f"DEPLOY-GATE: clean tree at {commit_short} — deploying HEAD content")
        return EXIT_CLEAN

    listing = "\n".join(f"    {rel}" for rel in uncommitted)
    if args.dirty:
        print(
            f"DEPLOY-GATE: --dirty — shipping {len(uncommitted)} uncommitted file(s) "
            f"on top of {commit_short}:\n{listing}\n"
            "  These will be recorded by name and digest in .claude/.deploy-state.json."
        )
        return EXIT_CLEAN

    sys.stderr.write(
        f"DEPLOY-GATE: REFUSED — {len(uncommitted)} file(s) under the deployed "
        f"subdirs are not in HEAD and would reach the executing hook stack "
        f"unreviewed:\n"
        f"{listing}\n"
        "\n"
        "  Every gate in this pipeline sits on the path to a commit. Deploying the\n"
        "  working tree routes around all of them at once, and git cannot revert\n"
        "  what was never committed (Issue #1610).\n"
        "\n"
        "  REQUIRED NEXT ACTION — one of:\n"
        "    1. Commit the changes, then re-run deploy-all.sh (preferred)\n"
        "    2. Delete the stray file if it is not meant to execute\n"
        "    3. Re-run with --dirty to ship them anyway; every file above is then\n"
        "       recorded by name and digest and surfaced by /health-check\n"
    )
    return EXIT_FINDING


def cmd_stamp(args: argparse.Namespace) -> int:
    """Record provenance for each freshly deployed target."""
    source = Path(args.source).resolve()
    plugin_src = Path(args.plugin_src).resolve()
    targets = [Path(t).resolve() for t in args.target]

    # Hoisted out of the per-target loop: identical for every target, and each
    # call costs a filesystem walk plus two git subprocesses.
    try:
        uncommitted = uncommitted_deploy_paths(source, plugin_src)
        commit = head_commit(source)
        expected_source = source_deployed_files(plugin_src)
    except DeployStateError as exc:
        sys.stderr.write(f"deploy_state: could not stamp: {exc}\n")
        return EXIT_UNKNOWN

    states: list[dict] = []
    written: list[Path] = []
    for target in targets:
        if not target.is_dir():
            sys.stderr.write(f"deploy_state: skipping absent target {target}\n")
            continue
        try:
            state = build_state(
                source_repo=source,
                plugin_src=plugin_src,
                target=target,
                dirty_allowed=args.dirty,
                uncommitted=uncommitted,
                commit=commit,
                expected_source=expected_source,
            )
        except DeployStateError as exc:
            sys.stderr.write(f"deploy_state: could not stamp {target}: {exc}\n")
            return EXIT_UNKNOWN
        write_state(target, state)
        states.append(state)
        written.append(target)

    if not states:
        sys.stderr.write("deploy_state: nothing stamped (no existing targets)\n")
        return EXIT_UNKNOWN

    first = states[0]
    flag = "DIRTY" if any(s["dirty"] for s in states) else "clean"
    print(
        f"DEPLOY-STATE: stamped {len(written)} target(s) at "
        f"{first['source_commit_short']} ({flag})"
    )
    for state in states:
        for rel in state.get("unmatched_uncommitted", []):
            sys.stderr.write(
                f"DEPLOY-STATE: could not attribute uncommitted path {rel!r} to a "
                f"deployed file — recorded under unmatched_uncommitted and the "
                f"target is marked dirty\n"
            )
        for rel in state.get("target_only", []):
            sys.stderr.write(
                f"DEPLOY-STATE: {rel!r} was ALREADY in the target and no source file "
                f"accounts for it — recorded under target_only, not adopted into the "
                f"deploy record as legitimate, and the target is marked dirty\n"
            )
    if args.log_activity:
        path = log_activity_row(source, states, written)
        if path is not None:
            print(f"DEPLOY-STATE: activity row -> {path}  (type: deploy)")
    return EXIT_CLEAN


def symlink_escapes_tree(target: Path, path: Path) -> bool:
    """Whether a symlink at ``path`` points outside the deployed tree.

    A recorded symlink's POINTEE is never digested — the record stores
    ``symlink:<target>``, which is honest but governs no content. So a recorded
    symlink that still matches its record can front for arbitrary bytes outside
    anything this tool measures, and ``check`` would exit 0 over it.

    Latent rather than live: zero symlinks exist under any deployed subdir
    today. Reported rather than treated as drift, because the record IS
    accurate — what is missing is coverage, and saying so is the honest arm.
    """
    try:
        base = target.resolve()
        resolved = path.resolve()
    except (OSError, ValueError):
        return True  # cannot establish containment -> report it
    return resolved != base and base not in resolved.parents


def _resolve_source_for_check(state: dict) -> tuple[Optional[Path], str, Optional[str]]:
    """Return the source repo to re-verify against, if it can be TRUSTED here.

    ``source_repo`` and ``source_plugin_rel`` come from the same gitignored,
    unreviewed ``.deploy-state.json`` that ``unsafe_digest_keys`` exists to
    sanitise, and the self-heal path feeds ``source_repo`` to ``git`` as a
    subprocess cwd and ``source_plugin_rel`` into a ``HEAD:<rel>/<file>``
    revision. Policing the digest keys while trusting these two was the
    remaining unsanitised arm of the same record.

    Refusing here fails CLOSED: without the self-heal, files stay reported as
    uncommitted, which is louder, not quieter.

    Args:
        state: The parsed deploy record (untrusted).

    Returns:
        ``(repo, plugin_rel, reason)``. ``repo`` is None when the self-heal must
        not run; ``reason`` is a human-readable refusal when the record NAMED a
        source that failed validation, and None when it simply named none.
    """
    raw = state.get("source_repo")
    plugin_rel = state.get("source_plugin_rel") or DEFAULT_PLUGIN_REL

    if not isinstance(plugin_rel, str) or not plugin_rel:
        return None, DEFAULT_PLUGIN_REL, "source_plugin_rel is not a non-empty string"
    rel_path = Path(plugin_rel)
    if rel_path.is_absolute() or ".." in rel_path.parts or plugin_rel.startswith("~"):
        return None, DEFAULT_PLUGIN_REL, f"source_plugin_rel escapes the repo: {plugin_rel!r}"

    if not isinstance(raw, str) or not raw:
        return None, plugin_rel, None  # no source named: nothing to refuse
    repo = Path(raw)
    if not (repo / ".git").exists():
        return None, plugin_rel, None  # source not reachable from here: normal
    try:
        top = git_toplevel(repo)
    except DeployStateError as exc:
        return None, plugin_rel, f"source_repo is not a usable git checkout ({exc})"
    if top != repo.resolve():
        return None, plugin_rel, (
            f"source_repo {raw!r} is not a git toplevel (git resolves {top}); "
            "refusing to run git there"
        )
    return repo, plugin_rel, None


def cmd_check(args: argparse.Namespace) -> int:
    """Report what is executing, and name anything that diverges.

    Exit codes:
        0 — the executing tree matches a clean deploy record (stays QUIET)
        1 — uncommitted content is executing, a recorded file drifted, an
            UNRECORDED file is present in the executing tree, a TARGET-ONLY file
            was present before the stamp, or a recorded symlink escapes the tree
        2 — no deploy record, or a record that verifies nothing
    """
    repo = Path(args.repo).resolve()
    target = repo / ".claude"
    state, error = read_state(target)

    if error is not None:
        print(
            f"DEPLOY-STATE: UNKNOWN — .claude/{STATE_FILENAME} exists but is {error}.\n"
            "  This is NOT the same as an unstamped tree: something truncated or\n"
            "  altered the record. Nothing here can be verified.\n"
            "  REQUIRED NEXT ACTION: re-deploy to rewrite the record, and check\n"
            "  what truncated it."
        )
        return EXIT_UNKNOWN

    if state is None:
        deployed_here = any((target / name).is_dir() for name in DEPLOY_SUBDIRS)
        has_source = (repo / DEFAULT_PLUGIN_REL).is_dir()
        detail = (
            "  This tree has an executing .claude/ but has never been stamped."
            if deployed_here
            else "  Nothing appears to be deployed here yet."
        )
        origin = (
            "  REQUIRED NEXT ACTION: re-deploy with scripts/deploy-all.sh (or /sync)."
            if has_source
            else (
                "  There is no autonomous-dev source in this tree, so the deploy that\n"
                "  wrote it ran from elsewhere (another checkout, or another machine).\n"
                "  It becomes knowable the next time THAT deploy runs — no action is\n"
                "  possible or required from here."
            )
        )
        print(
            "DEPLOY-STATE: UNKNOWN — no .claude/.deploy-state.json.\n"
            "  Nothing records which commit the executing hooks came from.\n"
            f"{detail}\n{origin}"
        )
        return EXIT_UNKNOWN

    commit = state.get("source_commit_short") or "unknown"
    recorded = state.get("digests")
    if not isinstance(recorded, dict) or not recorded:
        # A probe that checked nothing must never announce success. The pre-fix
        # success branch fired whenever the three finding lists were empty, and
        # an empty digest map guarantees exactly that (BLOCKING 5).
        print(
            "DEPLOY-STATE: UNKNOWN — the deploy record is malformed or empty "
            f"(digests: {type(recorded).__name__}, "
            f"{len(recorded) if isinstance(recorded, dict) else 'n/a'} entries).\n"
            "  It verifies ZERO files, so it cannot report a healthy tree.\n"
            "  REQUIRED NEXT ACTION: re-deploy with scripts/deploy-all.sh to "
            "rewrite the record."
        )
        return EXIT_UNKNOWN

    unsafe = unsafe_digest_keys(recorded, target)
    if unsafe:
        print(
            f"DEPLOY-STATE: {len(unsafe)} record key(s) point OUTSIDE the deployed "
            "tree — the record is malformed or has been tampered with:"
        )
        for key in unsafe:
            print(f"    {key}")
        print(
            "  Nothing was read from those paths.\n"
            "  REQUIRED NEXT ACTION: re-deploy with scripts/deploy-all.sh, and "
            "check who can write .claude/.deploy-state.json."
        )
        return EXIT_FINDING

    changed: list[str] = []
    missing: list[str] = []
    escaping: list[str] = []
    for rel, expected in sorted(recorded.items()):
        path = target / rel
        if not path.is_symlink() and not path.is_file():
            missing.append(rel)
            continue
        if digest_entry(path) != expected:
            changed.append(rel)
            continue
        # Matches the record — but a recorded symlink's POINTEE is never
        # digested, so a symlink out of the tree governs ungoverned content.
        if path.is_symlink() and symlink_escapes_tree(target, path):
            escaping.append(rel)

    # The reverse comparison. Without it, ``check`` can only ever see what the
    # record already lists, so a file ADDED to the executing tree after the
    # stamp is invisible — and hooks insert the deployed lib dir at sys.path[0],
    # so an added module shadowing a lazily-imported one executes INSIDE the
    # enforcement layer while the check prints exit 0 (BLOCKING 4).
    executing = {path.relative_to(target).as_posix() for path in iter_deployed_files(target)}
    unrecorded = sorted(executing - set(recorded))

    uncommitted = [rel for rel in state.get("uncommitted_files", []) if isinstance(rel, str)]
    unmatched = [rel for rel in state.get("unmatched_uncommitted", []) if isinstance(rel, str)]
    # BLOCKING A: recorded at stamp time as present-in-target-but-absent-from-
    # source. The reverse comparison above cannot see these — they were adopted
    # into ``recorded`` before it existed.
    target_only = [rel for rel in state.get("target_only", []) if isinstance(rel, str)]

    # Self-heal: a file uncommitted AT DEPLOY TIME may have been committed
    # since, with the executing bytes untouched. A check that stays red after
    # the operator did the right thing is the one people learn to skip.
    now_committed: list[str] = []
    source_repo, plugin_rel, source_refusal = _resolve_source_for_check(state)
    if source_refusal is not None:
        print(
            "DEPLOY-STATE: not re-verifying against the recorded source — "
            f"{source_refusal}.\n"
            "  The record is untrusted input; nothing below was downgraded by it."
        )
    if source_repo is not None and uncommitted:
        for rel in list(uncommitted):
            path = target / rel
            if path.is_file() and head_blob_matches(source_repo, plugin_rel, rel, path):
                now_committed.append(rel)
        uncommitted = [rel for rel in uncommitted if rel not in now_committed]

    stamped = state.get("timestamp", "?")
    findings = (
        uncommitted or unmatched or target_only or changed or missing or unrecorded or escaping
    )
    if not findings:
        healed = f", {len(now_committed)} since committed" if now_committed else ""
        print(
            f"DEPLOY-STATE: OK — executing {commit}, "
            f"{len(recorded)} files match the deploy record "
            f"(stamped {stamped}{healed})"
        )
        return EXIT_CLEAN

    print(f"DEPLOY-STATE: executing {commit} — {len(recorded)} files recorded")
    if uncommitted:
        print(
            f"DEPLOY-STATE: {len(uncommitted)} file(s) executing content that was "
            f"uncommitted at deploy time (stamped {stamped}):"
        )
        for rel in uncommitted:
            print(f"    {rel}")
    if unmatched:
        print(
            f"DEPLOY-STATE: {len(unmatched)} uncommitted path(s) could not be "
            "attributed to a deployed file at stamp time (recorded fail-closed):"
        )
        for rel in unmatched:
            print(f"    {rel}")
    if target_only:
        print(
            f"DEPLOY-STATE: {len(target_only)} executing file(s) were ALREADY in the "
            "target at deploy time and NO source file accounts for them (recorded "
            "fail-closed, never adopted as legitimate):"
        )
        for rel in target_only:
            print(f"    {rel}")
    if changed:
        print(
            f"DEPLOY-STATE: {len(changed)} executing file(s) DRIFT from the deploy "
            "record (edited in place after deploy):"
        )
        for rel in changed:
            print(f"    {rel}")
    if missing:
        print(f"DEPLOY-STATE: {len(missing)} recorded file(s) missing from the executing tree:")
        for rel in missing:
            print(f"    {rel}")
    if unrecorded:
        print(
            f"DEPLOY-STATE: {len(unrecorded)} executing file(s) are NOT in the deploy "
            "record (added after the stamp — no deploy put them there):"
        )
        for rel in unrecorded:
            print(f"    {rel}")
    if escaping:
        print(
            f"DEPLOY-STATE: {len(escaping)} recorded symlink(s) match the record but "
            "point OUTSIDE the deployed tree, so the bytes they serve are governed "
            "by nothing this tool digests:"
        )
        for rel in escaping:
            print(f"    {rel} -> {os.readlink(target / rel)}")
    if now_committed:
        print(
            f"DEPLOY-STATE: {len(now_committed)} previously-uncommitted file(s) now "
            "match a commit and are no longer reported."
        )
    # A directive the operator cannot act on trains bypass of the whole command,
    # so name the action that matches the finding rather than one blanket line.
    if uncommitted or unmatched or changed or missing:
        print(
            "  REQUIRED NEXT ACTION: commit the listed files, then re-run "
            "scripts/deploy-all.sh so the executing tree matches a real commit."
        )
    if target_only or unrecorded:
        print(
            "  REQUIRED NEXT ACTION for the files no source accounts for: no deploy "
            "put them there. Delete them, or if they are meant to execute, add them "
            "to the plugin source and re-run scripts/deploy-all.sh."
        )
    if escaping:
        print(
            "  REQUIRED NEXT ACTION for the escaping symlink(s): replace them with "
            "content inside the deployed tree, or accept that nothing verifies what "
            "they serve."
        )
    return EXIT_FINDING


def cmd_excludes(args: argparse.Namespace) -> int:
    """Print the deploy exclusions, one rsync pattern per line."""
    for pattern in rsync_exclude_patterns():
        print(pattern)
    return EXIT_CLEAN


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="deploy_state.py",
        description="Deploy provenance: record and report what is executing (Issue #1610).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gate = sub.add_parser("gate", help="refuse a dirty-tree deploy unless --dirty")
    gate.add_argument("--source", required=True, help="source repository root")
    gate.add_argument("--plugin-src", required=True, help="path to plugins/autonomous-dev")
    gate.add_argument("--dirty", action="store_true", help="permit shipping uncommitted work")
    gate.set_defaults(func=cmd_gate)

    stamp = sub.add_parser("stamp", help="write .deploy-state.json for deployed targets")
    stamp.add_argument("--source", required=True, help="source repository root")
    stamp.add_argument("--plugin-src", required=True, help="path to plugins/autonomous-dev")
    stamp.add_argument("--target", action="append", required=True, help="deployed .claude dir")
    stamp.add_argument("--dirty", action="store_true", help="the deploy used --dirty")
    stamp.add_argument(
        "--log-activity",
        action="store_true",
        help="append one type='deploy' row to .claude/logs/activity/",
    )
    stamp.set_defaults(func=cmd_stamp)

    check = sub.add_parser("check", help="report what is executing and name divergences")
    check.add_argument("--repo", default=".", help="repo root whose .claude/ is executing")
    check.set_defaults(func=cmd_check)

    excludes = sub.add_parser("excludes", help="print the rsync exclusion patterns")
    excludes.set_defaults(func=cmd_excludes)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except DeployStateError as exc:
        # A provenance tool must never hand the operator a traceback: the
        # message IS the product. Deploy is not blocked by our own breakage.
        sys.stderr.write(f"deploy_state: {exc}\n")
        return EXIT_UNKNOWN
    except (TypeError, AttributeError, ValueError) as exc:
        # A type-confused record (digests as a list, a digest as an int) must
        # not produce a traceback with exit 1 — /health-check cannot tell that
        # apart from a genuine drift finding.
        sys.stderr.write(
            f"deploy_state: the deploy record is not the shape this tool expects "
            f"({type(exc).__name__}: {exc}).\n"
            f"deploy_state: nothing could be verified. Re-deploy to rewrite it.\n"
        )
        return EXIT_UNKNOWN


if __name__ == "__main__":
    sys.exit(main())
