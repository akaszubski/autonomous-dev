#!/usr/bin/env python3
"""
Context-File Size and Overlap Guard Hook

``CLAUDE.md``, ``PROJECT.md`` and ``MEMORY.md`` load into the model's context
on EVERY turn. They are maps, not datasheets: every line costs context
permanently. This hook is the thing that refuses when they stop being maps.

Registered on ``PostToolUse`` for the write tools (see the ``.hook.json``
sidecar and ``templates/settings.*.json``). It acts only when the write
targeted one of the four tracked context files; every other write passes
through silently. Invoked with no hook payload on stdin (e.g. from a git
pre-commit script or by hand) it checks everything and reports.

What it checks
--------------
1. **Size, in two bands.**

   =========================== ===== ======  =============================
   File                        Warn  Block   Rationale
   =========================== ===== ======  =============================
   ``<repo>/CLAUDE.md``        200   300     Anthropic best practice
   ``~/.claude/CLAUDE.md``     200   300     loads in EVERY repo (#1636)
   ``<repo>/.claude/PROJECT.md`` 150 225     CONTENT_ALLOCATION.md target
   ``MEMORY.md``               200   300     Anthropic auto-load threshold
   =========================== ===== ======  =============================

   The warn band is the existing target, unchanged: the point of a warning
   is to notice drift early, while an ordinary edit that nudges a file past
   target should advise rather than refuse. The block band is the target
   times ``HARD_CEILING_MULTIPLIER`` (1.5) — see that constant for why 1.5
   and not 1.0 or 2.0.

   **Per-repo ratchet (Issue #1648).** For the two REPO-TRACKED files the
   effective ceiling is ``max(hard_ceiling, line_count_at_git_HEAD)``: *you
   may not make this file worse than it already is at HEAD*. A repo that
   inherited an oversized context file is not refused on every edit — it is
   refused the moment the file GROWS. The mark is the repository's own
   committed history, so there is no baseline file to create, bootstrap or
   forge: raising it requires committing a bigger file past a live refusal,
   visibly, in a diff. See ``_head_line_count`` for the fallbacks, every one
   of which lands on the absolute ceiling rather than relaxing it.

   Two named limitations, both strict by construction rather than by luck:
   a worktree or submodule (``.git`` is a FILE) gets no ratchet, and a
   context file committed as a SYMLINK gets no ratchet either — ``git show``
   returns the link target, not the content, so the mark is 1 and the
   absolute ceiling always wins. THIS repo's ``.claude/PROJECT.md`` is such
   a symlink.

2. **Overlap between the local and global CLAUDE.md.** Size catches volume;
   it cannot catch the same rule stated twice. See ``find_overlaps``.

Missing files are silently skipped — a consumer repo may have no global
``~/.claude/CLAUDE.md`` and that is not an error. Each check runs in
isolation; a failure in one does not suppress the others.

Exit codes:
- 0: Always. A refusal travels as ``{"decision": "block"}`` JSON on stdout
  (the PostToolUse protocol shape), not as an exit code.
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import json
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set, Tuple

# Issue #1611 / INV-1: a refusal that is not recorded is not evidence, and a
# gate declared in prose is not a gate. ``block_event_decorator`` is one of the
# three sanctioned fusing sinks (tests/unit/hooks/test_refusal_sink_ratchet.py):
# it wraps this hook's SOLE refusal emitter, so every refusal records by
# construction and the emitted envelope is left byte-untouched.
try:
    from hook_telemetry import block_event_decorator
except ImportError:  # pragma: no cover — stale-install fallback

    def block_event_decorator(_hook_name, **_kwargs):
        """No-op fallback: refuse unrecorded rather than not refuse at all."""

        def _decorator(fn):
            return fn

        return _decorator


# Issue #1503: classify writes by effect, not by tool name. Used to decide
# whether a PostToolUse payload touched a tracked context file.
try:
    from tool_intent import write_targets
except ImportError:  # pragma: no cover — stale-install fallback
    _FALLBACK_PATH_KEYS = ("file_path", "notebook_path", "relative_path", "path")

    def write_targets(tool_name: str, tool_input: dict) -> list:
        """Fallback target accessor: first non-empty known path key."""
        if not isinstance(tool_input, dict):
            return []
        for _key in _FALLBACK_PATH_KEYS:
            _value = tool_input.get(_key)
            if isinstance(_value, str) and _value:
                return [_value]
        return []


# ---------------------------------------------------------------------------
# Size bands
# ---------------------------------------------------------------------------

# Warn band — the existing content-allocation targets. UNCHANGED by design:
# lowering one to make a currently-passing file fail would be manufacturing a
# red, and raising one would be accommodating bloat.
MAX_LINES = 200                # <repo>/CLAUDE.md (Anthropic best practice)
MAX_PROJECT_LINES = 150        # .claude/PROJECT.md (CONTENT_ALLOCATION.md)
MAX_MEMORY_LINES = 200         # MEMORY.md (Anthropic auto-load threshold)
MAX_GLOBAL_CLAUDE_LINES = 200  # ~/.claude/CLAUDE.md — loads in EVERY repo

#: Hard ceiling = target x 1.5.
#:
#: Chosen, not inherited. 1.0 would make every warning fatal, so a single
#: section added to a file already at target would refuse an ordinary edit —
#: that is a signal that cries wolf, and the whole class gets ignored. 2.0
#: would let a file reach double its target before anything refuses, by which
#: point the drift the warn band exists to catch has already been paid for on
#: every turn for weeks. 1.5 puts the refusal out of reach of any single
#: reasonable edit (the largest section in this repo's CLAUDE.md is 11 lines;
#: the ceiling sits 100 lines above target) while still refusing sustained
#: accumulation. Measured baseline the day this landed — 70 / 150 / 127 / 159
#: lines against targets of 200 / 200 / 150 / 200 — is under every WARN limit,
#: so this lands green and ratchets from a true baseline.
HARD_CEILING_MULTIPLIER = 1.5

BLOCK_LINES = int(MAX_LINES * HARD_CEILING_MULTIPLIER)                  # 300
BLOCK_PROJECT_LINES = int(MAX_PROJECT_LINES * HARD_CEILING_MULTIPLIER)  # 225
BLOCK_MEMORY_LINES = int(MAX_MEMORY_LINES * HARD_CEILING_MULTIPLIER)    # 300
BLOCK_GLOBAL_CLAUDE_LINES = int(
    MAX_GLOBAL_CLAUDE_LINES * HARD_CEILING_MULTIPLIER
)                                                                        # 300

OK = "ok"
WARN = "warn"
BLOCK = "block"


# ---------------------------------------------------------------------------
# Overlap detection thresholds
# ---------------------------------------------------------------------------

#: A local section is a restatement when its heading shares at least one
#: distinctive term with a global heading AND at least this fraction of the
#: smaller section's distinctive vocabulary is shared.
#:
#: MEASURED, not guessed. Across the full cross product of this repo's
#: CLAUDE.md (8 sections) and the global one (20 sections, code fences
#: stripped) — 160 pairs — exactly ZERO pairs have a non-empty heading-term
#: intersection AND non-zero body overlap. Re-running the same measurement
#: with the pre-#1639 ``## Code Navigation (LSP > grep when available)``
#: section restored flags exactly one pair, against
#: ``# Serena for dependencies, grep for strings``, at heading=0.25 body=0.286.
#: So the conjunction separates the one real duplicate from every benign pair
#: with no near misses on either side.
#:
#: The conjunction is load-bearing. Body overlap ALONE ranks four benign pairs
#: above the real duplicate (``Maintainer Escape Hatches`` ~ ``Hook deadlock
#: protocol`` scores 0.455 against the duplicate's 0.286), and an IDF-weighted
#: variant ranks the real duplicate third. Both of those were measured and
#: rejected; a checker that flags everything is as useless as one that flags
#: nothing, and this one is seen on every turn.
OVERLAP_BODY_THRESHOLD = 0.25

#: Headings must share at least this many distinctive terms.
OVERLAP_MIN_SHARED_HEADING_TERMS = 1

#: Sections with fewer distinctive terms than this are skipped: overlap
#: coefficients over a handful of tokens are noise, not evidence.
OVERLAP_MIN_SECTION_TERMS = 8

#: Words carrying no topical signal. Deliberately short — an aggressive list
#: is a second thing to maintain, and the overlap coefficient already
#: normalises for section length.
_STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those of to in on at by for with without
    from as is are was were be been being it its not no nor so such only just also very more
    most you your we our they their he she me my do does did done can could should would may
    might must use used using when where which who whom what how why all any each other same
    own too don now one two three there here into over under out up down off again further
    once about against between per via while every
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9_][a-z0-9_./-]*")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*```")
_MARKDOWN_NOISE_RE = re.compile(r"[*`#>|_\[\]()]")


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One thing the guard noticed about the context files.

    Attributes:
        severity: ``"warn"`` (advise) or ``"block"`` (refuse).
        label: Short identifier of the file or rule, e.g. ``"CLAUDE.md"``.
        message: Full human-readable message, including the REQUIRED NEXT
            ACTION directive when severity is ``"block"``.
    """

    severity: str
    label: str
    message: str


@dataclass(frozen=True)
class Section:
    """A markdown section: one heading plus the body beneath it.

    Attributes:
        heading: Heading text with the leading ``#`` markers stripped.
        body: Raw body text up to the next heading.
    """

    heading: str
    body: str


@dataclass(frozen=True)
class Overlap:
    """A local section that restates a global one.

    Attributes:
        local_heading: Heading of the offending local section.
        global_heading: Heading of the global section it restates.
        heading_similarity: Overlap coefficient over heading terms.
        body_similarity: Overlap coefficient over body terms.
        shared_terms: The distinctive terms both bodies contain.
    """

    local_heading: str
    global_heading: str
    heading_similarity: float
    body_similarity: float
    shared_terms: Tuple[str, ...]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def get_repo_root() -> Path:
    """Find repository root by traversing up to .git directory.

    Returns:
        The nearest ancestor containing ``.git``, or the cwd if there is none.
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd()


def derive_memory_path() -> Path:
    """Derive the auto-load MEMORY.md path for the current working directory.

    Claude stores per-project auto-memory at
    ``~/.claude/projects/<slug>/memory/MEMORY.md`` where ``<slug>`` is the
    absolute path of the current working directory with '/' replaced by '-'.

    Returns:
        Path to MEMORY.md for the current cwd. The file may not exist —
        callers must handle that case.
    """
    slug = str(Path.cwd()).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory" / "MEMORY.md"


def global_claude_md_path() -> Path:
    """Path of the user-global CLAUDE.md.

    This is the highest-leverage file in the system: unlike the repo
    ``CLAUDE.md`` it loads in EVERY repo, so a line added here is paid for in
    every session everywhere. It had no limit before Issue #1639.

    Returns:
        ``~/.claude/CLAUDE.md``. The file may not exist — a consumer repo may
        have no global file, and callers must handle that case.
    """
    return Path.home() / ".claude" / "CLAUDE.md"


# ---------------------------------------------------------------------------
# Size checks
# ---------------------------------------------------------------------------


def classify_size(line_count: int, warn_limit: int, block_limit: int) -> str:
    """Band a line count.

    Args:
        line_count: Lines in the file.
        warn_limit: Target size; above this advises.
        block_limit: Hard ceiling; above this refuses.

    Returns:
        ``"ok"``, ``"warn"``, or ``"block"``.
    """
    if line_count > block_limit:
        return BLOCK
    if line_count > warn_limit:
        return WARN
    return OK


def _read_line_count(path: Path) -> Optional[int]:
    """Count lines in a file, tolerating absence and unreadability.

    Args:
        path: File to measure.

    Returns:
        The line count, or None if the file is missing or unreadable.
    """
    if not path.exists():
        return None
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return None


@lru_cache(maxsize=64)
def _head_line_count(path: Path, repo_root: Path) -> Optional[int]:
    """Lines in ``path`` as committed at git HEAD — the per-repo ratchet mark.

    Issue #1648. Every failure path returns None, and None means "no mark",
    which means the absolute ceiling stands. There is no branch on which a
    failure here can RELAX a limit.

    The ``lru_cache`` is a CORRECTNESS requirement, not a performance one.
    Each of the two repo-tracked specs is built twice per invocation (once via
    its ``check_*`` wrapper, once in ``collect_size_findings``'s ``specs``
    map), so uncached this would be 4 subprocesses x ``timeout=2`` = 8s
    against the sidecar's 5s budget. A hook killed mid-run emits nothing, and
    PostToolUse reads silence as approval — the guard would fail OPEN. Cached,
    it is 2 x 2s = 4s plus the hook's own measured 0.044s. Any IN-PROCESS
    caller that re-commits the same ``(path, repo_root)`` must call
    ``_head_line_count.cache_clear()``.

    Args:
        path: Absolute path of the context file to measure.
        repo_root: Absolute path of the repository root.

    Returns:
        The committed line count, or None when no mark can be established.
    """
    git_dir = repo_root / ".git"
    if not git_dir.is_dir():
        # A ``.git`` FILE means a worktree or submodule. ``--git-dir`` does not
        # accept one, so the ratchet is unavailable there — by design, strict.
        return None
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        # Outside the repo (``~/.claude/CLAUDE.md``, ``MEMORY.md``): no mark.
        return None
    try:
        # ``--git-dir`` PINS the repository, and that pin is load-bearing.
        # ``get_repo_root`` stops at the first ancestor where ``.git`` EXISTS;
        # git does not stop there — it walks PAST an invalid ``.git`` into an
        # ancestor repo and returns THAT repo's HEAD. Unpinned, a repo with a
        # malformed ``.git`` would read a foreign repository's file as its own
        # size mark. Pinned, an invalid ``.git`` is a non-zero returncode.
        #
        # ``HEAD:<rel>`` is cwd-independent because the gitrevisions
        # ``<rev>:<path>`` rule resolves the path relative to the TOP OF THE
        # TREE unless it is prefixed ``./`` or ``../`` — NOT because this is
        # bare mode. Measured: with ``--git-dir`` set and no ``--work-tree``,
        # ``rev-parse --is-bare-repository`` returns ``false`` and
        # ``--show-toplevel`` returns the CWD.
        proc = subprocess.run(
            ["git", f"--git-dir={git_dir}", "show", f"HEAD:{rel.as_posix()}"],
            capture_output=True,
            text=True,
            timeout=2,
            stdin=subprocess.DEVNULL,  # stdin carries the hook payload
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        # git absent; the subprocess hung; the blob is not valid UTF-8.
        return None
    if proc.returncode != 0:
        # Not a valid repo, no commits, or the file is untracked at HEAD. This
        # branch is what separates a strict fallback from silently counting a
        # git error's empty stdout as a 0-line mark.
        return None
    return len(proc.stdout.splitlines())


def _ratcheted(spec: dict, repo_root: Path) -> dict:
    """Apply the per-repo ratchet to one size spec, in place.

    A mark can only RELAX, and only above the hard ceiling: ``max`` semantics
    mean a file committed SMALLER than the ceiling changes nothing, so the
    ratchet can never tighten a limit. When the mark is in force, BOTH bands
    move to it — otherwise a repo sitting permanently above target would warn
    on every single edit forever, and a permanently-yellow check trains
    everyone to ignore the whole class.

    Args:
        spec: A size spec as built by ``_claude_md_spec``/``_project_md_spec``.
        repo_root: Absolute path of the repository root.

    Returns:
        The same dict, with limits and ``ceiling_note`` updated if in force.
    """
    mark = _head_line_count(spec["path"], repo_root)
    if mark is None:
        return spec

    # D1, the entire ratchet: max(absolute_ceiling, committed_size). Written as
    # a max rather than a bare comparison because the max is what makes "a mark
    # can never TIGHTEN" true by CONSTRUCTION — a mark below the ceiling is
    # clamped away before it can reach the limits, so even an inverted guard
    # below cannot narrow a band.
    effective_limit = max(spec["block_limit"], mark)
    if effective_limit > spec["block_limit"]:
        # Populated BEFORE the clobber below, or the original ceiling and
        # target are lost and the refusal can only name the mark.
        spec["ceiling_note"] = (
            f"absolute ceiling {spec['block_limit']}, target {spec['warn_limit']}"
        )
        spec["block_limit"] = spec["warn_limit"] = effective_limit
    return spec


def _size_finding(
    *,
    path: Path,
    label: str,
    display: str,
    warn_limit: int,
    block_limit: int,
    target_note: str,
    ceiling_note: str = "",
) -> Tuple[int, str, str]:
    """Measure one file and build its banded message.

    Args:
        path: File to measure.
        label: Short identifier used in Finding.label.
        display: How the file is named in the message.
        warn_limit: Target size.
        block_limit: Hard ceiling.
        target_note: Where the target comes from, for the warning text.
        ceiling_note: Set by ``_ratcheted`` ONLY when a git-HEAD mark is in
            force, naming the absolute ceiling and target the mark displaced.
            Empty — the default, and the case for every non-ratcheted file —
            selects the pre-#1648 block message byte for byte.

    Returns:
        Tuple of (line_count, severity, message). line_count is 0 and
        severity is ``"ok"`` when the file is missing or unreadable;
        message is empty unless severity is ``"warn"`` or ``"block"``.
    """
    line_count = _read_line_count(path)
    if line_count is None:
        return 0, OK, ""

    severity = classify_size(line_count, warn_limit, block_limit)
    if severity == OK:
        return line_count, OK, ""

    if severity == WARN:
        message = (
            f"WARNING: {display} is {line_count} lines "
            f"({target_note}: {warn_limit}). "
            f"Current: {line_count}/{warn_limit} — file: {path}"
        )
        return line_count, WARN, message

    if ceiling_note:
        # Ratcheted refusal (#1648). The pre-#1648 text is wrong here: with
        # warn_limit == block_limit == the mark it renders the same integer
        # three times and tells the developer to trim to the size they are one
        # line above. This variant carries four DISTINCT integers — the
        # measured count, the growth, the in-force mark, and (via
        # ceiling_note) the absolute ceiling and target the mark displaced.
        message = (
            f"BLOCKED: {display} is {line_count} lines — "
            f"{line_count - block_limit} more than its own committed size of "
            f"{block_limit} lines at git HEAD, which is the limit in force "
            f"here because this file was already above the {ceiling_note}. "
            f"This file loads into context on every turn.\n"
            f"REQUIRED NEXT ACTION: bring {display} back to {block_limit} "
            f"lines or fewer — its size at git HEAD — before continuing. It "
            f"may not grow; shrinking toward the target named above is the "
            f"real goal. See realign#1681.\n"
            f"File: {path}"
        )
        return line_count, BLOCK, message

    message = (
        f"BLOCKED: {display} is {line_count} lines — over the hard ceiling of "
        f"{block_limit} (target {warn_limit}). This file loads into context on "
        f"every turn, so every line above target is paid for permanently.\n"
        f"REQUIRED NEXT ACTION: trim {display} back to {warn_limit} lines or "
        f"fewer before continuing. Move detail into docs/ and link to it; "
        f"keep the context file a map, not a datasheet.\n"
        f"File: {path}"
    )
    return line_count, BLOCK, message


def _claude_md_spec(repo_root: Path) -> dict:
    """Check spec for the repo CLAUDE.md. Repo-tracked, so it ratchets."""
    return _ratcheted(
        {
            "path": repo_root / "CLAUDE.md",
            "label": "CLAUDE.md",
            "display": "CLAUDE.md",
            "warn_limit": MAX_LINES,
            "block_limit": BLOCK_LINES,
            "target_note": "Anthropic best practice: keep under",
        },
        repo_root,
    )


def _global_claude_md_spec() -> dict:
    """Check spec for ``~/.claude/CLAUDE.md``.

    ``display`` is worded so that the substring ``"CLAUDE.md is"`` — which
    discriminates the REPO file's warning in the existing test suite — stays
    unique to the repo file.
    """
    return {
        "path": global_claude_md_path(),
        "label": "global CLAUDE.md",
        "display": "~/.claude/CLAUDE.md (global)",
        "warn_limit": MAX_GLOBAL_CLAUDE_LINES,
        "block_limit": BLOCK_GLOBAL_CLAUDE_LINES,
        "target_note": "loads in EVERY repo; keep under",
    }


def _project_md_spec(repo_root: Path) -> dict:
    """Check spec for ``.claude/PROJECT.md``. Repo-tracked, so it ratchets."""
    return _ratcheted(
        {
            "path": repo_root / ".claude" / "PROJECT.md",
            "label": "PROJECT.md",
            "display": ".claude/PROJECT.md",
            "warn_limit": MAX_PROJECT_LINES,
            "block_limit": BLOCK_PROJECT_LINES,
            "target_note": "content-allocation target: keep under",
        },
        repo_root,
    )


def _memory_md_spec() -> dict:
    """Check spec for the per-project auto-memory ``MEMORY.md``."""
    return {
        "path": derive_memory_path(),
        "label": "MEMORY.md",
        "display": "MEMORY.md",
        "warn_limit": MAX_MEMORY_LINES,
        "block_limit": BLOCK_MEMORY_LINES,
        "target_note": "Anthropic auto-load threshold",
    }


def check_claude_md_size(repo_root: Path) -> Tuple[int, str]:
    """Check the repo CLAUDE.md against the 200-line target.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        Tuple of (line_count, message). line_count is 0 if CLAUDE.md is
        missing. message is empty when the file is within target.
    """
    count, _severity, message = _size_finding(**_claude_md_spec(repo_root))
    return count, message


def check_global_claude_md_size() -> Tuple[int, str]:
    """Check ``~/.claude/CLAUDE.md`` — the file that loads in every repo.

    Absence is not an error: a consumer repo may have no global file.

    Returns:
        Tuple of (line_count, message). line_count is 0 if the file is
        missing or unreadable; message is empty when within target.
    """
    count, _severity, message = _size_finding(**_global_claude_md_spec())
    return count, message


def check_project_md_size(repo_root: Path) -> Tuple[int, str]:
    """Check .claude/PROJECT.md size against the content-allocation target.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        Tuple of (line_count, message). line_count is 0 if PROJECT.md is
        missing or unreadable; message is empty when within target.
    """
    count, _severity, message = _size_finding(**_project_md_spec(repo_root))
    return count, message


def check_memory_md_size() -> Tuple[int, str]:
    """Check the per-project auto-memory MEMORY.md against Anthropic's threshold.

    Returns:
        Tuple of (line_count, message). line_count is 0 if MEMORY.md is
        missing or unreadable; message is empty when within target.
    """
    count, _severity, message = _size_finding(**_memory_md_spec())
    return count, message


def collect_size_findings(repo_root: Path) -> List[Finding]:
    """Run every size check, each isolated from the others.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        One Finding per file that is over target. Files within target,
        missing, or unreadable contribute nothing.
    """
    findings: List[Finding] = []

    # Indirected through the module-level ``check_*`` wrappers so that a test
    # (or a caller) monkeypatching one of them sees the same behaviour here.
    checks = (
        ("CLAUDE.md", lambda: check_claude_md_size(repo_root)),
        ("global CLAUDE.md", check_global_claude_md_size),
        ("PROJECT.md", lambda: check_project_md_size(repo_root)),
        ("MEMORY.md", check_memory_md_size),
    )

    specs = {
        "CLAUDE.md": _claude_md_spec(repo_root),
        "global CLAUDE.md": _global_claude_md_spec(),
        "PROJECT.md": _project_md_spec(repo_root),
        "MEMORY.md": _memory_md_spec(),
    }

    for label, check in checks:
        try:
            count, message = check()
        except OSError:
            # One check's failure must not suppress the others.
            continue
        if not message:
            continue
        spec = specs[label]
        severity = classify_size(count, spec["warn_limit"], spec["block_limit"])
        findings.append(Finding(severity=severity, label=label, message=message))

    return findings


# ---------------------------------------------------------------------------
# Overlap detection — the part size cannot see
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> Set[str]:
    """Reduce markdown prose to its distinctive lowercase terms.

    Args:
        text: Markdown source.

    Returns:
        Set of terms with markdown punctuation, stopwords and 1-2 character
        fragments removed.
    """
    cleaned = _MARKDOWN_NOISE_RE.sub(" ", text.lower())
    return {
        token
        for token in _TOKEN_RE.findall(cleaned)
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _overlap_coefficient(left: Set[str], right: Set[str]) -> float:
    """Fraction of the SMALLER set's terms that also appear in the larger.

    Overlap coefficient rather than Jaccard: a short local section that
    restates a long global one is exactly the case to catch, and Jaccard
    penalises the length difference until that case scores near zero.

    Args:
        left: First term set.
        right: Second term set.

    Returns:
        Value in [0, 1]; 0 when either set is empty.
    """
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def extract_sections(markdown: str) -> List[Section]:
    """Split markdown into heading-delimited sections.

    Fenced code blocks are stripped FIRST. Without that, a ``# Recent
    sessions`` comment inside a ```bash fence is parsed as a heading — the
    global CLAUDE.md has two such lines, and both produced spurious sections
    that a naive body-overlap rule then flagged.

    Args:
        markdown: Markdown source.

    Returns:
        Sections in document order. Text before the first heading is
        discarded (it belongs to no section).
    """
    lines: List[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)

    sections: List[Section] = []
    heading: Optional[str] = None
    body: List[str] = []
    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            if heading is not None:
                sections.append(Section(heading=heading, body="\n".join(body)))
            heading, body = match.group(2).strip(), []
        elif heading is not None:
            body.append(line)
    if heading is not None:
        sections.append(Section(heading=heading, body="\n".join(body)))
    return sections


def find_overlaps(local_markdown: str, global_markdown: str) -> List[Overlap]:
    """Find local sections that restate a global one.

    The failure mode size cannot see is the same rule stated twice. Both
    copies are usually correct; together they cost context on every turn to
    say one thing. The real instance this was built from: a 9-line
    ``## Code Navigation (LSP > grep when available)`` section in this repo's
    CLAUDE.md restating the global ``# Serena for dependencies, grep for
    strings`` almost point for point.

    The rule is a CONJUNCTION — headings must name a common topic AND the
    bodies must share vocabulary. Either half alone was measured and rejected;
    see ``OVERLAP_BODY_THRESHOLD``.

    What this deliberately does NOT do is judge whether a rule earns its
    place. That needs judgment, not computation.

    Args:
        local_markdown: Contents of the repo CLAUDE.md.
        global_markdown: Contents of ``~/.claude/CLAUDE.md``.

    Returns:
        One Overlap per (local section, global section) pair that trips both
        thresholds. Empty when either document has no sections.
    """
    local_sections = extract_sections(local_markdown)
    global_sections = extract_sections(global_markdown)

    overlaps: List[Overlap] = []
    for local in local_sections:
        local_heading_terms = _tokenize(local.heading)
        local_body_terms = _tokenize(local.body)
        if len(local_body_terms) < OVERLAP_MIN_SECTION_TERMS:
            continue

        for remote in global_sections:
            remote_body_terms = _tokenize(remote.body)
            if len(remote_body_terms) < OVERLAP_MIN_SECTION_TERMS:
                continue

            shared_heading = local_heading_terms & _tokenize(remote.heading)
            if len(shared_heading) < OVERLAP_MIN_SHARED_HEADING_TERMS:
                continue

            body_similarity = _overlap_coefficient(local_body_terms, remote_body_terms)
            if body_similarity < OVERLAP_BODY_THRESHOLD:
                continue

            overlaps.append(
                Overlap(
                    local_heading=local.heading,
                    global_heading=remote.heading,
                    heading_similarity=_overlap_coefficient(
                        local_heading_terms, _tokenize(remote.heading)
                    ),
                    body_similarity=body_similarity,
                    shared_terms=tuple(sorted(local_body_terms & remote_body_terms)),
                )
            )

    return overlaps


def collect_overlap_findings(repo_root: Path) -> List[Finding]:
    """Compare the repo CLAUDE.md against the global one.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        One blocking Finding per restated section. Empty when either file is
        missing — a consumer repo with no global file must not error.
    """
    local_path = repo_root / "CLAUDE.md"
    global_path = global_claude_md_path()
    if not local_path.exists() or not global_path.exists():
        return []

    try:
        local_markdown = local_path.read_text(encoding="utf-8")
        global_markdown = global_path.read_text(encoding="utf-8")
    except OSError:
        return []

    findings: List[Finding] = []
    for overlap in find_overlaps(local_markdown, global_markdown):
        findings.append(
            Finding(
                severity=BLOCK,
                label="overlap",
                message=(
                    f"BLOCKED: CLAUDE.md section '{overlap.local_heading}' restates the "
                    f"global rule '{overlap.global_heading}' "
                    f"(heading overlap {overlap.heading_similarity:.2f}, body overlap "
                    f"{overlap.body_similarity:.2f}; shared terms: "
                    f"{', '.join(overlap.shared_terms[:12])}). Both copies load on every "
                    f"turn to say one thing.\n"
                    f"REQUIRED NEXT ACTION: delete the local section, or cut it to the "
                    f"repo-specific residue only and let the global rule stand. Do not "
                    f"restate the global rule here.\n"
                    f"Local: {local_path}\nGlobal: {global_path}"
                ),
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Hook plumbing
# ---------------------------------------------------------------------------


@block_event_decorator(
    "validate_claude_md_size.py",
    decision_shape="dict",
    refusal_values=frozenset({"block"}),
    metadata={"gate": "context-file-size-and-overlap", "issue": 1639},
)
def _output_decision(decision: str, reason: str, *, system_message: str = "") -> None:
    """Print this hook's decision as PostToolUse JSON on stdout.

    This is the hook's SOLE refusal emitter, which is what makes the
    ``block_event_decorator`` wrap fuse recording to refusal by construction:
    there is no path on which this hook can refuse and leave no row.

    Args:
        decision: ``"block"``. Allows emit nothing at all — PostToolUse
            treats silence as approval, so there is no allow envelope to
            preserve.
        reason: Model-visible reason, carrying the REQUIRED NEXT ACTION.
        system_message: Optional user-visible message.
    """
    output = {"decision": decision, "reason": reason}
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output))


def _read_payload() -> Tuple[bool, Optional[dict]]:
    """Read the hook payload from stdin, if there is one.

    Three states are distinguished, and the distinction matters:

    * ``(False, None)`` — no stdin at all. The hook was invoked by hand or
      from a git pre-commit script; run every check.
    * ``(True, dict)`` — a lifecycle payload; act only if it touched a
      tracked context file.
    * ``(True, None)`` — stdin carried something this hook cannot parse. It
      is a lifecycle invocation whose TARGET IS UNKNOWN, so the honest
      response is to do nothing. Treating it as a bare CLI invocation would
      run every check on a write we cannot attribute, which is how a signal
      starts crying wolf.

    Returns:
        Tuple of (stdin carried content, parsed payload or None).
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        return False, None
    if not raw or not raw.strip():
        return False, None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return True, None
    return True, (payload if isinstance(payload, dict) else None)


def tracked_context_files(repo_root: Path) -> List[Path]:
    """The four files this guard governs.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        Absolute paths, whether or not they exist.
    """
    return [
        repo_root / "CLAUDE.md",
        repo_root / ".claude" / "PROJECT.md",
        global_claude_md_path(),
        derive_memory_path(),
    ]


def payload_touches_context_file(payload: dict, repo_root: Path) -> bool:
    """Did this write target one of the tracked context files?

    Scoping the TRIGGER to the files being checked is what keeps this signal
    from crying wolf: refusing an unrelated edit because CLAUDE.md is long
    trains everyone to ignore the whole class.

    Args:
        payload: PostToolUse hook payload.
        repo_root: Path to the repository root directory.

    Returns:
        True if any write target resolves to a tracked context file.
    """
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False

    targets = write_targets(tool_name, tool_input)
    if not targets:
        return False

    tracked = set()
    for path in tracked_context_files(repo_root):
        try:
            tracked.add(path.expanduser().resolve())
        except OSError:
            continue

    for target in targets:
        if not isinstance(target, str) or not target:
            continue
        try:
            resolved = Path(target).expanduser().resolve()
        except OSError:
            continue
        if resolved in tracked:
            return True
    return False


def main() -> int:
    """Run the context-file size and overlap checks.

    In hook mode (a JSON payload on stdin) the checks run only when the write
    targeted a tracked context file. Invoked with no payload, every check
    runs.

    Warnings go to stderr and do not block. A blocking finding is emitted as
    ``{"decision": "block", "reason": ...}`` on stdout — the PostToolUse
    refusal shape — carrying the REQUIRED NEXT ACTION.

    Returns:
        Always 0. The refusal travels in the JSON, not the exit code.
    """
    # Universal bypass (Issue #969): env var or .claude/.bypass falls through.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(hook_name=Path(__file__).name, tool_name="validate_claude_md_size")
            return 0
    except ImportError:
        pass

    repo_root = get_repo_root()

    had_stdin, payload = _read_payload()
    if had_stdin and (
        payload is None or not payload_touches_context_file(payload, repo_root)
    ):
        return 0

    findings = collect_size_findings(repo_root)
    try:
        findings.extend(collect_overlap_findings(repo_root))
    except OSError:
        pass

    for finding in findings:
        if finding.severity == WARN:
            print(finding.message, file=sys.stderr)

    blocking = [f for f in findings if f.severity == BLOCK]
    if blocking:
        reason = (
            "Context-file guard: "
            + f"{len(blocking)} blocking finding(s).\n\n"
            + "\n\n".join(f.message for f in blocking)
        )
        _output_decision("block", reason, system_message=reason)

    return 0



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
