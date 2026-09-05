#!/usr/bin/env python3
"""Ratchet: the number of append-mode log-writer modules may only go DOWN.

Issue #1718. Every module that opens a file in append mode is a producer of a
growing on-disk stream. Producers are cheap to add and nobody is required to
add a reader, so the tree accumulates write-only streams --
``logs/timing_history.jsonl`` is the worked example: written since 2026-04-10
and read by nothing. This module pins the producer population and refuses
growth. Reduction is always permitted and lowers the pin.

The metric is a PROXY
---------------------
What is measured is *append-mode file writes*, not *log writers*. The two are
not identical and the gap is deliberate, because closing it needs a semantic
judgement AST cannot make. The clearest instance is
``plugins/autonomous-dev/hooks/setup.py``, which appends to ``.gitignore`` --
configuration, not a log. It is pinned anyway. Excluding it would require the
detector to reason about what the opened path *means*, and a detector that
takes judgement calls is a detector that can be argued with.

Scope
-----
``plugins/autonomous-dev/hooks/`` and ``plugins/autonomous-dev/lib/``.
``archived/`` is excluded under PROJECT.md's archived-code rule (dead code held
to a live standard is noise); ``.codex/`` and ``.worktrees/`` are mirrors of
the source tree and would double-count every finding.

AST, not regex
--------------
Detection walks the AST. MEASURED 2026-09-02 over the two scan roots,
``grep -REn '\\bopen\\([^)]*["'"'"']a' --include='*.py'`` versus this detector:

* grep 50 call sites, AST 48 open-append call sites.
* All 4 grep-only sites are in ``lib/python_write_detector.py`` (:29, :91,
  :273, :321) -- an append call written as *text* in a docstring describing
  what that module detects. It writes nothing.
* The 2 AST-only sites are ``os.open`` calls with an opaque flags variable,
  failed closed (see below).
* At file level: grep 33 files, AST 35. ``33 - 1 + 3 = 35`` -- drop the
  ``python_write_detector.py`` false positive, add the three
  ``FileHandler``-family files no text instrument can see.

The ``FileHandler`` family
--------------------------
``logging.FileHandler`` and its ``logging.handlers`` subclasses default to
``mode="a"``. They open in append mode without the letter ``"a"`` appearing
anywhere in the call, so *every* text instrument misses them. The live
instances, each verified by reading the line, are enumerated in
``FILEHANDLER_FAMILY_SITES`` below:

* ``lib/logging_utils.py:61``      -- ``logging.FileHandler(log_file)``
* ``lib/security_utils.py:182``    -- ``RotatingFileHandler(audit_log, maxBytes=...)``

A call to one of these names counts as an append writer UNLESS an explicit
non-append string-literal mode is present.

Fail-closed on non-literal modes
--------------------------------
``open(p, mode_var)`` and ``FileHandler(p, mode=mode_var)`` count as APPEND.
The detector cannot evaluate the variable, and an instrument that resolves its
own uncertainty in favour of "nothing here" is how a population silently
shrinks. Known ambiguity, stated rather than hidden: a single-argument
attribute call ``x.open(v)`` with a non-literal ``v`` is NOT failed closed,
because ``io.open(path)`` and ``Path.open(mode)`` are the same shape and
treating index 0 as a mode would flag every plain ``io.open(path)`` in the
tree.

Escape hatch
------------
Adding writer 34 takes three edits in ONE diff: add the repo-relative path to
:data:`PINNED_APPEND_WRITERS`, raise :data:`APPEND_WRITER_CEILING`, raise
:data:`CEILING_HIGH_WATER_MARK`. The equality assertion forces the second; the
ceiling-may-never-exceed-the-mark assertion forces the third. Reduction is a
two-line diff (drop the path, lower the ceiling) and never touches the mark;
the residual ``mark - ceiling`` is held at zero so a shrink cannot leave
pre-authorised headroom for a silent re-growth.

This is **review visibility, not technical closure.** Nothing stops a reviewer
waving through a three-line diff, and nothing here mechanically requires a new
writer to name a reader -- which is precisely what ``logs/timing_history.jsonl``
lacks.

Day-one limitation
------------------
This module lives under ``tests/unit/``, so it also runs inside CI's unit tier.
That duplicate run is **NOT** the enforcing copy: the unit tier's conclusion is
``failure`` today regardless of this module's verdict (78 standing failures,
tracked as issue #1719), so a refusal landing there is unobservable. The
enforcing copy is the dedicated step in the ``smoke`` job of
``.github/workflows/ci.yml``, whose result gates merge via ``SMOKE_RESULT``.
This is a limitation of where the guard can be observed, not a mitigation of
it: until #1719 closes, the unit-tier run of this file proves nothing.

Runtime: **0.99s** for the whole module, 65 tests from 25 test functions
(MEASURED 2026-09-02:
``pytest tests/unit/lib/test_append_writer_ratchet.py -q -o "addopts="
--durations=5``). The slowest arm is 0.44s -- the single full-tree AST parse,
memoised thereafter; before the memo the module took 19.9s.

Date: 2026-09-02
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pytest

# tests/unit/lib/<this file> -> lib -> unit -> tests -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

PLUGIN_ROOT = _REPO_ROOT / "plugins" / "autonomous-dev"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
LIB_DIR = PLUGIN_ROOT / "lib"

SCAN_ROOTS = (HOOKS_DIR, LIB_DIR)

# Path components that take a file out of scope. See "Scope" above.
EXCLUDED_PATH_PARTS = frozenset({"archived", ".codex", ".worktrees"})

# Logging handlers that open their file in append mode by default.
APPEND_HANDLER_NAMES = frozenset(
    {
        "FileHandler",
        "RotatingFileHandler",
        "TimedRotatingFileHandler",
        "WatchedFileHandler",
    }
)

# Every legal Python file-mode string. An explicit finite set, not a character
# class: ``[rwxab+t]+`` matches the word "rat", so a regex would read
# ``open("rat")`` as an append. Only membership in this set is treated as a
# mode literal.
_VALID_MODES = frozenset(
    base + suffix for base in "rwxa" for suffix in ("", "b", "t", "+", "b+", "t+", "+b", "+t")
)


def _is_mode_literal(node: ast.AST) -> bool:
    """Report whether ``node`` is a string constant that is a legal file mode."""
    return isinstance(node, ast.Constant) and node.value in _VALID_MODES


def _is_append_mode_literal(node: ast.AST) -> bool:
    """Report whether ``node`` is a string constant naming an append mode."""
    return _is_mode_literal(node) and str(node.value).startswith("a")


def _func_name(node: ast.Call) -> Optional[str]:
    """The called name: ``open`` for both ``open(...)`` and ``io.open(...)``."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _keyword(node: ast.Call, name: str) -> Optional[ast.AST]:
    """The value node of keyword ``name``, or None if absent."""
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


#: Names under which the ``os`` module is imported in the scanned tree.
#: MEASURED 2026-09-02: ``os`` and ``_os`` (``lib/pipeline_state.py`` uses the
#: underscore alias). Membership is not the only test -- see
#: :func:`_is_os_open` for the alias-proof fallback.
OS_MODULE_ALIASES = frozenset({"os", "_os"})


def _o_flag_names(node: ast.AST) -> "set[str]":
    """Every ``O_*`` constant named anywhere inside ``node``."""
    found: "set[str]" = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr.startswith("O_"):
            found.add(sub.attr)
        elif isinstance(sub, ast.Name) and sub.id.startswith("O_"):
            found.add(sub.id)
    return found


def _is_os_open(node: ast.Call) -> bool:
    """Report whether the call is ``os.open`` rather than builtin/``Path`` open.

    ``os.open`` is a DIFFERENT API: its second argument is an integer flags
    word, not a mode string. Reading it as a mode is how a detector reports
    six phantom append writers -- MEASURED: exactly that, before this branch
    existed, and it inflated the population from 35 files to 36.
    """
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "open"):
        return False
    if isinstance(func.value, ast.Name) and func.value.id in OS_MODULE_ALIASES:
        return True
    # Alias-proof fallback: an ``O_*`` flag constant anywhere in the arguments
    # identifies the fd-level API even under an unrecognised module alias.
    return any(_o_flag_names(arg) for arg in node.args)


def _is_append_os_open(node: ast.Call) -> bool:
    """Report whether an ``os.open`` call opens the descriptor for appending.

    At the fd level, append is ``O_APPEND`` in the flags word. MEASURED
    2026-09-02: zero occurrences of ``O_APPEND`` across the scan roots, so
    every live ``os.open`` here is a non-append descriptor. An opaque flags
    variable fails CLOSED -- it could carry ``O_APPEND``.
    """
    flags = node.args[1] if len(node.args) >= 2 else _keyword(node, "flags")
    if flags is None:
        return False
    names = _o_flag_names(flags)
    if names:
        return "O_APPEND" in names
    return True


def _is_append_open(node: ast.Call) -> bool:
    """Report whether an ``open``-family call opens in append mode.

    Covers ``open(p, "a")``, ``open(p, mode="a")``, ``io.open(p, "ab+")`` and
    ``p.open("a")`` / ``p.open(mode="a")``. Positional indices 0 and 1 are both
    inspected because ``Path.open`` takes the mode first while the builtin and
    ``io.open`` take it second; the finite :data:`_VALID_MODES` set is what
    keeps a path argument from being misread as a mode.
    """
    mode_kw = _keyword(node, "mode")
    if mode_kw is not None:
        # Fail closed: a non-literal mode counts as append.
        return _is_append_mode_literal(mode_kw) or not isinstance(mode_kw, ast.Constant)

    candidates = node.args[:2]
    if any(_is_append_mode_literal(arg) for arg in candidates):
        return True
    if any(_is_mode_literal(arg) for arg in candidates):
        return False  # an explicit non-append literal mode
    # Fail closed on a non-literal SECOND positional argument only; see the
    # "Fail-closed on non-literal modes" section of the module docstring for
    # why index 0 is deliberately not failed closed.
    if len(node.args) >= 2 and not isinstance(node.args[1], ast.Constant):
        return True
    return False


def _is_append_handler(node: ast.Call) -> bool:
    """Report whether a logging-handler call opens its file in append mode.

    The handler family defaults to ``mode="a"``, so the call counts unless an
    explicit non-append string-literal mode is present (keyword or second
    positional, which is where every handler in the family takes it).
    """
    mode_kw = _keyword(node, "mode")
    if mode_kw is not None:
        return not (_is_mode_literal(mode_kw) and not _is_append_mode_literal(mode_kw))
    if len(node.args) >= 2 and _is_mode_literal(node.args[1]):
        return _is_append_mode_literal(node.args[1])
    return True


def is_append_writer_call(node: ast.AST) -> bool:
    """Report whether ``node`` is a call that opens a file for appending."""
    if not isinstance(node, ast.Call):
        return False
    name = _func_name(node)
    if name is None:
        return False
    if name in APPEND_HANDLER_NAMES:
        return _is_append_handler(node)
    if name == "open":
        if _is_os_open(node):
            return _is_append_os_open(node)
        return _is_append_open(node)
    return False


def _scan_paths(roots: Iterable[Path]) -> List[Path]:
    """Every in-scope ``*.py`` file beneath ``roots``, sorted."""
    paths: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if EXCLUDED_PATH_PARTS.intersection(path.parts):
                continue
            paths.append(path)
    return paths


def _key(path: Path) -> str:
    """Repo-relative POSIX key for ``path``.

    Repo-relative, NOT basename. MEASURED collisions in the scanned tree:
    ``__init__.py`` x5, ``models.py`` x3, ``cli.py`` x3 (for example
    ``lib/implement_dispatcher/cli.py`` versus ``lib/sync_dispatcher/cli.py``),
    ``dispatcher.py`` x2, ``modes.py`` x2. None is a writer today, so 35 is
    correct under either keying now -- but the moment two same-named modules
    both gain a writer, a basename-keyed set records ONE entry and the count
    silently understates. Repo-relative keying is the majority precedent here
    (``test_vacuous_test_ratchet.py:136``, ``test_hook_reachability_ratchet.py:1346``).
    """
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def unparseable_files(roots: Optional[Iterable[Path]] = None) -> List[str]:
    """Files in scope that could not be parsed.

    DELIBERATE DEVIATION from ``test_anthropic_client_ratchet.py:143-146``,
    which swallows ``SyntaxError``/``UnicodeDecodeError`` with ``continue``.
    That is a fail-open hole: a file that stops parsing silently leaves the
    population and the count still reads green. Here the offenders are
    collected and asserted empty, so a file that stops parsing FAILS the run.
    """
    bad: List[str] = []
    for path in _scan_paths(roots if roots is not None else SCAN_ROOTS):
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            bad.append(_key(path))
    return bad


#: Memo for the DEFAULT-roots scan only. Parsing both roots costs ~0.45s
#: (``hooks/unified_pre_tool.py`` alone is over 9,000 lines) and the module
#: scans them ~40 times, which took the run to 19.9s -- over the 5s target.
#: Explicit ``roots`` are NEVER memoised: the synthetic-tree arms rewrite a
#: file between two calls with the same root, and a cache there would return
#: the first content and read as a pass.
_LIVE_SITES_MEMO: Optional[Dict[str, List[int]]] = None


def _scan_sites(roots: Iterable[Path]) -> Dict[str, List[int]]:
    """Uncached scan of ``roots``. See :func:`append_writer_sites`."""
    sites: Dict[str, List[int]] = {}
    for path in _scan_paths(roots):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            # Not swallowed: unparseable_files() asserts this set is empty.
            continue
        for node in ast.walk(tree):
            if is_append_writer_call(node):
                sites.setdefault(_key(path), []).append(node.lineno)
    return sites


def append_writer_sites(
    roots: Optional[Iterable[Path]] = None,
) -> Dict[str, List[int]]:
    """Scan ``roots`` for calls that open a file in append mode.

    Args:
        roots: Directories to scan. Defaults to :data:`SCAN_ROOTS`. Overridable
            so the guard can be watched refusing on a synthetic tree.

    Returns:
        Mapping of repo-relative POSIX path to the line numbers of the append
        calls it contains. See :func:`_key` for why not basenames. A fresh dict
        is returned every call, so a caller cannot corrupt the memo.
    """
    if roots is not None:
        return _scan_sites(roots)
    global _LIVE_SITES_MEMO
    if _LIVE_SITES_MEMO is None:
        _LIVE_SITES_MEMO = _scan_sites(SCAN_ROOTS)
    return {key: list(lines) for key, lines in _LIVE_SITES_MEMO.items()}


def _ceiling_violations(pin_size: int, ceiling: int, mark: int) -> List[str]:
    """Every ceiling invariant ``(pin_size, ceiling, mark)`` breaks.

    Pure function so the arithmetic can be table-tested against values other
    than this module's own constants -- an assertion over two constants in the
    same file is unfalsifiable in-process.

    Args:
        pin_size: Number of entries in the pin.
        ceiling: The declared ceiling.
        mark: The highest ceiling ever reviewed.

    Returns:
        List of human-readable violation strings; empty when consistent.
    """
    violations: List[str] = []
    if pin_size > ceiling:
        violations.append(
            f"pin grew to {pin_size}, over APPEND_WRITER_CEILING ({ceiling}): "
            f"an append writer was pinned instead of removed."
        )
    if ceiling > mark:
        violations.append(
            f"APPEND_WRITER_CEILING RAISED to {ceiling}, over the reviewed mark "
            f"of {mark}. Lower freely; to raise, name the new writer and raise "
            f"the mark in the same diff."
        )
    if ceiling != pin_size:
        violations.append(
            f"APPEND_WRITER_CEILING ({ceiling}) no longer equals the pin size "
            f"({pin_size}). Slack pre-authorises the next writer."
        )
    residual = mark - ceiling
    if residual != 0:
        violations.append(
            f"residual headroom is {residual}: ceiling is {ceiling} while the "
            f"mark stayed {mark}. Lower the mark to {ceiling} -- the last step "
            f"of the edit you already made."
        )
    return violations


def _git_tracked_files() -> "set[str]":
    """Repo-relative POSIX paths tracked at git HEAD.

    Raises:
        RuntimeError: If ``git`` is unavailable or the command fails. The
            environment-stability arm FAILS rather than skips -- a skip here
            would read as a pass over an unverified population.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--full-name"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            f"cannot verify population stability: `git ls-files` did not run "
            f"in {_REPO_ROOT} ({exc}).\n"
            f"Expected: a working git checkout.\n"
            f"This arm fails rather than skips -- an unverifiable population "
            f"is not a verified one."
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"cannot verify population stability: `git ls-files` exited "
            f"{proc.returncode} in {_REPO_ROOT}.\nstderr: {proc.stderr.strip()}"
        )
    return {entry for entry in proc.stdout.split("\0") if entry}


# ---------------------------------------------------------------------------
# The pin
# ---------------------------------------------------------------------------

#: Every module in ``hooks/`` and ``lib/`` that opens a file in append mode,
#: measured 2026-09-02 by running :func:`append_writer_sites` over the live
#: tree. DEBT, not a permission slip: removing an entry is never blocked,
#: adding one is refused by the ceiling.
#:
#: ``hooks/setup.py`` appends to ``.gitignore``, not to a log. It is pinned
#: anyway -- see "The metric is a PROXY" above.
#: ``lib/logging_utils.py`` and ``lib/security_utils.py`` are here via the
#: ``FileHandler`` family and contain no ``"a"`` literal at all.
PINNED_APPEND_WRITERS: "frozenset[str]" = frozenset(
    {
        "plugins/autonomous-dev/hooks/cloud_drain_telemetry.py",
        "plugins/autonomous-dev/hooks/enforce_tier_distribution.py",
        "plugins/autonomous-dev/hooks/session_activity_logger.py",
        "plugins/autonomous-dev/hooks/setup.py",  # appends .gitignore, not a log
        "plugins/autonomous-dev/hooks/task_completed_handler.py",
        "plugins/autonomous-dev/hooks/unified_pre_tool.py",
        "plugins/autonomous-dev/hooks/unified_prompt_validator.py",
        "plugins/autonomous-dev/hooks/unified_session_tracker.py",
        "plugins/autonomous-dev/lib/alignment_classifier.py",
        "plugins/autonomous-dev/lib/alignment_gate.py",
        "plugins/autonomous-dev/lib/autoresearch_engine.py",
        "plugins/autonomous-dev/lib/benchmark_history.py",
        "plugins/autonomous-dev/lib/cia_finding_store.py",
        "plugins/autonomous-dev/lib/conflict_resolver.py",
        "plugins/autonomous-dev/lib/coordinator_log.py",
        "plugins/autonomous-dev/lib/drain_queue_state.py",
        "plugins/autonomous-dev/lib/drain_runner.py",
        "plugins/autonomous-dev/lib/error_analyzer.py",
        "plugins/autonomous-dev/lib/hook_bypass.py",
        "plugins/autonomous-dev/lib/hook_telemetry.py",
        "plugins/autonomous-dev/lib/hook_timing.py",
        "plugins/autonomous-dev/lib/install_audit.py",
        "plugins/autonomous-dev/lib/intent_classifier.py",
        "plugins/autonomous-dev/lib/logging_utils.py",  # FileHandler:61
        "plugins/autonomous-dev/lib/orphan_file_cleaner.py",
        "plugins/autonomous-dev/lib/performance_profiler.py",
        "plugins/autonomous-dev/lib/pipeline_completion_state.py",
        "plugins/autonomous-dev/lib/runtime_data_aggregator.py",
        "plugins/autonomous-dev/lib/security_utils.py",  # RotatingFileHandler:182
        "plugins/autonomous-dev/lib/semantic_gate.py",
        "plugins/autonomous-dev/lib/session_tracker.py",
        "plugins/autonomous-dev/lib/subagent_invocation_cache.py",
        "plugins/autonomous-dev/lib/workflow_violation_logger.py",
    }
)

#: Ceiling on the pin, asserted by EQUALITY (see the escape hatch above).
#: History -- the ratchet may only count DOWN:
#:   35  Issue #1718: landed at the live population, measured by AST.
#:   33  The approval-subsystem deletion. -2, both REMOVALS not repairs:
#:        ``lib/batch_retry_manager.py`` and ``lib/tool_approval_audit.py``
#:        were deleted with the never-executed approval cluster, so their
#:        pin entries protected nothing. ``tool_approval_audit.py`` was
#:        ALSO pinned in ``FILEHANDLER_FAMILY_SITES`` by file AND line
#:        number -- a shape no import graph can see -- and that tuple
#:        drops from 3 sites to 2 in the same diff.
APPEND_WRITER_CEILING = 33

#: Highest ceiling ever REVIEWED, so a raise costs a second visible edit.
CEILING_HIGH_WATER_MARK = 33

#: The ``FileHandler``-family sites, each verified by reading the line. These
#: are the sites no text instrument can see, so they are controlled by hand.
FILEHANDLER_FAMILY_SITES: Tuple[Tuple[str, int, str], ...] = (
    ("plugins/autonomous-dev/lib/logging_utils.py", 61, "logging.FileHandler("),
    ("plugins/autonomous-dev/lib/security_utils.py", 182, "RotatingFileHandler("),
)


# ---------------------------------------------------------------------------
# Instrument integrity -- verify the probe before trusting one cell of output
# ---------------------------------------------------------------------------


class TestInstrumentIntegrity:
    """A probe that returns zero is not evidence of zero."""

    def test_scan_roots_all_exist(self) -> None:
        """A vanished scan root silently shrinks the population to zero."""
        for root in SCAN_ROOTS:
            assert root.is_dir(), (
                f"Scan root {root} does not exist. The detector would report "
                f"fewer append writers than are really present, and the "
                f"ratchet would read green while measuring nothing."
            )

    def test_live_population_is_non_empty(self) -> None:
        """FAIL-CLOSED CANARY: zero is instrument failure, not a clean repo."""
        sites = append_writer_sites()
        assert sites, (
            "Zero append-mode writers found across hooks/ and lib/. Zero is "
            "instrument failure, not a clean repo -- lib/hook_telemetry.py "
            "alone must always be found. Fix the detector before touching the "
            "pin."
        )

    def test_the_non_empty_canary_can_actually_fail(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """CONTROL ON THE CANARY: point the scan at an empty tree, get zero.

        ``test_live_population_is_non_empty`` above is only informative if a
        zero result is REACHABLE -- a canary observed passing and never failing
        is indistinguishable from one that cannot fail. Both the scan roots and
        the memo are patched, so the arm exercises the same code path the real
        canary uses, and ``monkeypatch`` restores the populated memo on
        teardown.
        """
        module = sys.modules[__name__]
        monkeypatch.setattr(module, "SCAN_ROOTS", (tmp_path / "gone",))
        monkeypatch.setattr(module, "_LIVE_SITES_MEMO", None)
        assert append_writer_sites() == {}, (
            "The scan returned a population from a directory that does not "
            "exist. SCAN_ROOTS is not what the detector actually reads, so the "
            "non-empty canary is watching the wrong thing."
        )

    def test_the_memo_cannot_be_corrupted_by_a_caller(self) -> None:
        """The default-roots scan is memoised; the memo must stay private.

        Without this, one arm mutating its result would silently change every
        later arm's population -- and the run would still be green.
        """
        first = append_writer_sites()
        first.clear()
        first["plugins/autonomous-dev/lib/injected.py"] = [1]
        second = append_writer_sites()
        assert "plugins/autonomous-dev/lib/injected.py" not in second, (
            "A caller's mutation leaked into the memo. append_writer_sites() "
            "must return a fresh dict on every call."
        )
        assert len(second) == 33, (
            f"the memo returned {len(second)} entries after a caller cleared "
            f"its copy; the population is not stable within a run."
        )

    def test_no_file_in_scope_fails_to_parse(self) -> None:
        """FAIL-CLOSED CANARY: an unparseable file must not leave the population.

        This is the deliberate deviation from
        ``test_anthropic_client_ratchet.py:143-146``, which ``continue``s past
        ``SyntaxError``. Under that behaviour a file that stops parsing exits
        the population and the count still reads green.
        """
        offenders = unparseable_files()
        assert not offenders, (
            f"{len(offenders)} file(s) in scope could not be parsed: "
            f"{offenders}. Each one has silently left the measured population. "
            f"Fix the file -- this ratchet refuses to count around it."
        )

    def test_every_live_writer_is_tracked_at_git_head(self) -> None:
        """ENVIRONMENT STABILITY: the population must be reproducible.

        An untracked file in the population means the count depends on one
        working tree. If ``git`` is unavailable this arm FAILS -- it never
        skips, because an unverifiable population is not a verified one.
        """
        tracked = _git_tracked_files()
        assert tracked, (
            "git ls-files returned nothing: cannot verify population "
            "stability. A zero from the instrument is not a zero in the repo."
        )
        untracked = sorted(set(append_writer_sites()) - tracked)
        assert not untracked, (
            f"{len(untracked)} append writer(s) are not tracked at git HEAD: "
            f"{untracked}. The measured population depends on this working "
            f"tree, so the pin is not reproducible in CI."
        )


class TestPositiveControls:
    """Inputs the detector is KNOWN to flag. Each asserts its own premise."""

    def test_hook_telemetry_is_detected(self) -> None:
        """``lib/hook_telemetry.py`` appends via ``Path.open("a")``.

        Premise asserted first so this cannot pass vacuously if the file is
        rewritten -- and it exercises the attribute-open shape specifically.
        """
        path = LIB_DIR / "hook_telemetry.py"
        assert path.exists(), "premise: the positive-control file still exists"
        assert '.open("a"' in path.read_text(encoding="utf-8"), (
            "premise: hook_telemetry.py still opens its log in append mode. If "
            "it was changed, this control no longer exercises detection -- "
            "pick another append writer and drop this one from the pin."
        )
        key = "plugins/autonomous-dev/lib/hook_telemetry.py"
        assert key in append_writer_sites(), (
            "hook_telemetry.py was not detected. The AST detector has "
            "regressed on the Path.open('a') shape and the ratchet is "
            "under-counting."
        )

    @pytest.mark.parametrize("rel_path,line,anchor", FILEHANDLER_FAMILY_SITES)
    def test_filehandler_family_site_is_detected(
        self, rel_path: str, line: int, anchor: str
    ) -> None:
        """Each handler site that defaults to ``mode="a"``.

        Every non-AST instrument misses these: the letter ``"a"`` appears
        nowhere in the call. The premise asserts the anchor is still on the
        recorded line, so a moved call re-points the control instead of
        silently making it vacuous.
        """
        path = _REPO_ROOT / rel_path
        assert path.exists(), f"premise: {rel_path} still exists"
        source_line = path.read_text(encoding="utf-8").splitlines()[line - 1]
        assert anchor in source_line, (
            f"premise: {rel_path}:{line} no longer reads {anchor!r} (it reads "
            f"{source_line.strip()!r}). Re-point FILEHANDLER_FAMILY_SITES at "
            f"the call's new line -- a control aimed at the wrong line proves "
            f"nothing."
        )
        sites = append_writer_sites()
        assert rel_path in sites, (
            f"{rel_path} was not detected. The FileHandler family defaults to "
            f"mode='a'; losing it drops a real append writer from the "
            f"population with no visible failure."
        )
        assert line in sites[rel_path], (
            f"{rel_path} was detected, but not at line {line} (found "
            f"{sites[rel_path]}). The handler call itself is not what was "
            f"matched."
        )


class TestNegativeControls:
    """Inputs the detector is KNOWN to pass. Each asserts its own premise."""

    def test_write_mode_open_is_not_detected(self, tmp_path: Path) -> None:
        """``open(p, "w")`` truncates; it is not an append writer."""
        (tmp_path / "writer.py").write_text(
            'def f(p):\n    with open(p, "w") as fh:\n        fh.write("x")\n',
            encoding="utf-8",
        )
        assert append_writer_sites(roots=[tmp_path]) == {}, (
            "A write-mode open was reported as an append writer. The detector "
            "flags every open() and the ratchet measures nothing useful."
        )

    def test_append_call_written_as_text_is_not_detected(self, tmp_path: Path) -> None:
        """THE REGEX-VS-AST PROOF: an append call inside a string is text.

        Mirrors the live false positive: ``lib/python_write_detector.py``
        documents ``open(path, 'w'/'a')`` in a docstring and writes nothing.
        grep flags it at four lines; the AST detector flags it at none.
        """
        (tmp_path / "documenter.py").write_text(
            "DOC = \"call open(path, 'a') to append\"\n"
            "\n"
            "def describe():\n"
            '    """Detects open(path, "a") calls."""\n'
            "    return DOC\n",
            encoding="utf-8",
        )
        assert append_writer_sites(roots=[tmp_path]) == {}, (
            "An append call written as TEXT was reported as an append writer. "
            "The detector has lost AST-awareness and is matching text again."
        )

    def test_live_python_write_detector_is_not_detected(self) -> None:
        """The same proof against the real tree, with its premise asserted."""
        path = LIB_DIR / "python_write_detector.py"
        assert path.exists(), "premise: the negative-control file still exists"
        assert "open(path, 'w'/'a'" in path.read_text(encoding="utf-8"), (
            "premise: python_write_detector.py still describes append opens as "
            "text, so a text instrument would still flag it. If the wording "
            "changed, pick another prose mention."
        )
        key = "plugins/autonomous-dev/lib/python_write_detector.py"
        assert key not in append_writer_sites(), (
            "python_write_detector.py is reported as an append writer. It only "
            "describes append opens in a docstring; it writes nothing."
        )

    def test_filehandler_with_explicit_write_mode_is_not_detected(self, tmp_path: Path) -> None:
        """THE DISCRIMINATING CONTROL for the handler family.

        Without this, the positive handler arms pass just as well
        against a detector that flags every ``FileHandler`` unconditionally --
        which would be a detector that cannot tell append from truncate.
        """
        (tmp_path / "handler.py").write_text(
            "import logging\n"
            "\n"
            "def build(p):\n"
            '    return logging.FileHandler(p, mode="w")\n',
            encoding="utf-8",
        )
        assert append_writer_sites(roots=[tmp_path]) == {}, (
            "FileHandler(p, mode='w') was reported as an append writer. The "
            "detector flags the NAME rather than the behaviour, so the handler "
            "arms above prove nothing."
        )

    def test_os_open_is_classified_by_its_flags_not_by_its_shape(self, tmp_path: Path) -> None:
        """``os.open`` takes int flags, not a mode string.

        This is the class that inflated the first measurement from 35 to 36:
        the flags word was read as a positional mode argument and failed
        closed. Both directions are asserted -- ``O_APPEND`` must still count,
        so this is a correction of the classification and not an exclusion.
        """
        fd_file = tmp_path / "fd.py"
        fd_file.write_text(
            "import os\n"
            "\n"
            "def lock(p):\n"
            "    return os.open(str(p), os.O_CREAT | os.O_WRONLY, 0o600)\n",
            encoding="utf-8",
        )
        assert append_writer_sites(roots=[tmp_path]) == {}, (
            "An os.open() with no O_APPEND was reported as an append writer. "
            "Its second argument is an integer flags word, not a mode string."
        )
        fd_file.write_text(
            "import os\n"
            "\n"
            "def appender(p):\n"
            "    return os.open(str(p), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)\n",
            encoding="utf-8",
        )
        assert append_writer_sites(roots=[tmp_path]), (
            "An os.open() WITH O_APPEND was not detected. Excluding os.open "
            "wholesale would remove a real append shape from the population."
        )

    def test_archived_writers_are_excluded_and_exclusions_cannot_widen(self) -> None:
        """``archived/`` really does contain an append writer, so the premise is live."""
        archived = HOOKS_DIR / "archived" / "session_tracker.py"
        assert archived.exists(), "premise: the archived control file still exists"
        line = archived.read_text(encoding="utf-8").splitlines()[62]
        assert 'open(self.session_file, "a")' in line, (
            f"premise: hooks/archived/session_tracker.py:63 no longer appends "
            f"(it reads {line.strip()!r}). The exclusion would be doing no "
            f"work; re-point this control at another archived append writer."
        )
        leaked = [k for k in append_writer_sites() if "archived" in Path(k).parts]
        assert not leaked, (
            f"Archived file(s) leaked into the scan: {leaked}. The exclusion "
            f"has broken and the PROJECT.md archived-code rule is not applied."
        )
        assert EXCLUDED_PATH_PARTS == {"archived", ".codex", ".worktrees"}, (
            f"EXCLUDED_PATH_PARTS changed to {sorted(EXCLUDED_PATH_PARTS)}. "
            f"Widening this set is how a real append writer disappears from "
            f"the ratchet without anyone noticing."
        )


class TestGuardRefusesAndPermits:
    """The guard watched BOTH ways, on a synthetic tree."""

    def test_guard_refuses_a_new_append_writer(self, tmp_path: Path) -> None:
        """WATCHED REFUSING, on a shape unlike all 35 pinned writers.

        ``io.open(..., mode="a+")`` inside a nested function inside a class:
        the module-attribute open form, the ``mode=`` keyword, the ``"a+"``
        mode, and two levels of nesting. No pinned writer combines these. A
        guard authored to the shape that prompted it is scoped to the
        instance, not to the class of defect.

        COVERED CLASS: any call in ``hooks/`` or ``lib/`` that opens a file
        for appending, by any open/handler shape the detector recognises, at
        any nesting depth -- not merely "a new file resembling the 35".
        """
        offender = tmp_path / "brand_new_producer.py"
        offender.write_text(
            "import io\n"
            "\n"
            "class Producer:\n"
            "    def emit(self, path):\n"
            "        def _write(payload):\n"
            '            with io.open(path, mode="a+") as fh:\n'
            "                fh.write(payload)\n"
            "\n"
            "        return _write\n",
            encoding="utf-8",
        )
        detected = append_writer_sites(roots=[tmp_path])
        key = _key(offender)
        assert key in detected, (
            "A newly added append writer was NOT detected. The ratchet cannot "
            "fail, so it is not enforcement."
        )
        assert set(detected) - PINNED_APPEND_WRITERS == {key}, (
            f"The offender must surface as an unpinned writer -- that "
            f"difference is what makes test_live_state_matches_pin fail. Got "
            f"{sorted(set(detected) - PINNED_APPEND_WRITERS)}."
        )

    def test_guard_permits_a_non_append_writer(self, tmp_path: Path) -> None:
        """WATCHED PERMITTING: a truncating writer refuses nothing.

        A guard that refuses everything is equally useless. The file mentions
        appending in its docstring so the permitting arm also proves the
        detector is not reacting to the word.
        """
        innocent = tmp_path / "truncating_producer.py"
        innocent.write_text(
            '"""Writes a snapshot. Deliberately does NOT append."""\n'
            "\n"
            "def snapshot(path, payload):\n"
            '    with open(path, "w", encoding="utf-8") as fh:\n'
            "        fh.write(payload)\n",
            encoding="utf-8",
        )
        detected = append_writer_sites(roots=[tmp_path])
        assert detected == {}, (
            f"A truncating writer was reported as an append writer: "
            f"{detected}. The guard now refuses the legitimate path."
        )
        assert (
            not set(detected) - PINNED_APPEND_WRITERS
        ), "The permitting arm must leave the ratchet's difference empty."

    def test_two_same_named_modules_are_counted_separately(self, tmp_path: Path) -> None:
        """PATH-COLLISION REGRESSION: repo-relative keying, not basename.

        Measured collisions in the live tree include ``cli.py`` x3. Under
        basename keying this returns ONE entry and the count understates by
        one for every colliding pair.
        """
        for package in ("alpha", "beta"):
            pkg = tmp_path / package
            pkg.mkdir()
            (pkg / "cli.py").write_text(
                "def log(path, msg):\n"
                '    with open(path, "a") as fh:\n'
                "        fh.write(msg)\n",
                encoding="utf-8",
            )
        detected = append_writer_sites(roots=[tmp_path])
        assert len(detected) == 2, (
            f"Two same-named append writers in different directories "
            f"collapsed to {len(detected)} entr(y/ies): {sorted(detected)}. "
            f"The detector is keyed by basename and the population "
            f"understates."
        )
        assert len({Path(k).name for k in detected}) == 1, (
            "premise: both synthetic writers really are called cli.py, so a "
            "basename-keyed detector really would collide them."
        )


class TestCeilingArithmetic:
    """The ceiling invariants, table-tested away from this module's constants.

    :func:`_ceiling_violations` is a pure function precisely so these cases can
    be driven with values other than the file's own literals: an assertion
    relating two constants declared in the same file is unfalsifiable
    in-process and stays green through a coordinated re-growth.
    """

    @pytest.mark.parametrize(
        "pin_size,ceiling,mark,expect,why",
        [
            (35, 35, 35, None, "the aligned state must be clean"),
            (
                36,
                35,
                35,
                "pin grew to 36",
                "a writer pinned without raising the ceiling must be refused",
            ),
            (
                35,
                36,
                35,
                "RAISED to 36",
                "a ceiling raised past the reviewed mark is the re-growth bypass",
            ),
            (
                34,
                34,
                35,
                "residual headroom is 1",
                "a shrink that leaves the mark high pre-authorises one silent " "re-addition",
            ),
            (
                35,
                34,
                35,
                "pin grew to 35",
                "a ceiling below the pin must be refused",
            ),
        ],
    )
    def test_ceiling_violation_table(
        self,
        pin_size: int,
        ceiling: int,
        mark: int,
        expect: Optional[str],
        why: str,
    ) -> None:
        """Drive one arithmetic case and assert WHICH invariant fires."""
        violations = _ceiling_violations(pin_size, ceiling, mark)
        if expect is None:
            assert violations == [], f"{why}; got {violations}"
        else:
            assert violations, f"{why}; got no violation at all"
            assert any(expect in v for v in violations), (
                f"{why}: expected a violation containing {expect!r}, got "
                f"{violations}. A non-empty list alone cannot tell two cases "
                f"apart."
            )

    def test_a_coordinated_three_constant_raise_is_visible_not_silent(self) -> None:
        """State the residual hole rather than hide it.

        Raising all three constants together produces NO arithmetic violation
        -- that is the sanctioned escape hatch, and it is review visibility,
        not technical closure. This arm exists so the hole is asserted and
        named, and cannot be mistaken for a case the arithmetic catches.
        """
        assert _ceiling_violations(36, 36, 36) == [], (
            "The sanctioned three-edit escape hatch must be arithmetically "
            "clean -- if it is not, a legitimate new writer cannot be landed "
            "and the ratchet will be deleted instead of respected."
        )

    def test_this_modules_constants_are_consistent(self) -> None:
        """The live constants, run through the same pure function."""
        violations = _ceiling_violations(
            len(PINNED_APPEND_WRITERS), APPEND_WRITER_CEILING, CEILING_HIGH_WATER_MARK
        )
        assert violations == [], "\n".join(violations)

    def test_ceiling_equals_pin_size(self) -> None:
        """Equality, not ``<=``: growth AND shrink must be a deliberate diff."""
        assert APPEND_WRITER_CEILING == len(PINNED_APPEND_WRITERS), (
            f"APPEND_WRITER_CEILING is {APPEND_WRITER_CEILING} but the pin "
            f"holds {len(PINNED_APPEND_WRITERS)} entries. These move together: "
            f"if you removed a writer, lower the ceiling AND the mark in the "
            f"same commit."
        )

    def test_residual_headroom_is_zero(self) -> None:
        """A shrink may not leave pre-authorised headroom behind."""
        residual = CEILING_HIGH_WATER_MARK - APPEND_WRITER_CEILING
        assert residual == 0, (
            f"ceiling is {APPEND_WRITER_CEILING} while the mark stayed "
            f"{CEILING_HIGH_WATER_MARK}, pre-authorising {residual} more "
            f"writer(s) no ceiling assertion would see. Lower the mark to "
            f"{APPEND_WRITER_CEILING} -- the last step of the edit you "
            f"already made."
        )


class TestRatchet:
    """The ratchet proper: reality must equal the pin, in both directions."""

    def test_live_state_matches_pin(self) -> None:
        """Refusing growth and refusing staleness are separate messages."""
        live = set(append_writer_sites())
        unpinned = sorted(live - PINNED_APPEND_WRITERS)
        stale = sorted(PINNED_APPEND_WRITERS - live)

        assert not unpinned, (
            f"{len(unpinned)} NEW append-mode writer(s): {unpinned}. Every "
            f"append writer starts a growing on-disk stream, and nothing "
            f"requires it to have a reader -- logs/timing_history.jsonl has "
            f"been written since 2026-04-10 and read by nothing. Adding an "
            f"entry to PINNED_APPEND_WRITERS is NOT an acceptable resolution "
            f"unless the writer is genuinely needed; if it is, use the escape "
            f"hatch in the module docstring (three edits in one diff) and name "
            f"the reader in the commit message."
        )
        assert not stale, (
            f"PINNED_APPEND_WRITERS names {len(stale)} module(s) that no "
            f"longer append: {stale}. Delete them from the pin and lower "
            f"APPEND_WRITER_CEILING and CEILING_HIGH_WATER_MARK by the same "
            f"amount -- that deletion IS the ratchet advancing."
        )

    def test_pin_size_is_the_landing_measurement(self) -> None:
        """The literal, so a pin edit cannot pass by moving both constants."""
        assert len(PINNED_APPEND_WRITERS) == APPEND_WRITER_CEILING == 33, (
            f"pin={len(PINNED_APPEND_WRITERS)}, "
            f"ceiling={APPEND_WRITER_CEILING}. The literal 33 here is the "
            f"landing measurement (Issue #1718); lowering it is the ratchet "
            f"advancing and requires editing this line too."
        )


@pytest.mark.parametrize("rel_path", sorted(PINNED_APPEND_WRITERS))
def test_every_pinned_writer_still_exists_and_still_appends(rel_path: str) -> None:
    """No pinned entry may go vacuous while still consuming headroom.

    A pin entry for a deleted or converted module protects nothing and holds a
    slot open for a future writer. This forces its removal.
    """
    path = _REPO_ROOT / rel_path
    assert path.exists(), (
        f"{rel_path} is pinned but no longer exists. Remove it from "
        f"PINNED_APPEND_WRITERS and lower APPEND_WRITER_CEILING and "
        f"CEILING_HIGH_WATER_MARK from {APPEND_WRITER_CEILING} to "
        f"{APPEND_WRITER_CEILING - 1}."
    )
    assert rel_path in append_writer_sites(), (
        f"{rel_path} is pinned but no longer opens any file in append mode. "
        f"Remove it from PINNED_APPEND_WRITERS and lower both constants from "
        f"{APPEND_WRITER_CEILING} to {APPEND_WRITER_CEILING - 1} -- that "
        f"deletion IS the ratchet advancing."
    )
