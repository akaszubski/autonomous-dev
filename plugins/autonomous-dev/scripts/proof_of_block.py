#!/usr/bin/env python3
"""Proof-of-block: a guard is not enforcement until it has been watched
refusing something. (Issue #1520)

WHY THIS EXISTS
---------------
Unit tests prove a function runs. They do not prove a guard is registered,
reachable, loaded from the copy production uses, or capable of refusing
anything. Measured in one session:

  - 5 of 6 block-capable hooks in a consumer repo had never emitted a block in
    3.5 months, with green tests throughout
  - plan_gate failed OPEN for every MCP editing tool (#1503); its tests passed
    because they only covered enumerated tools
  - a fixed function's production call site passed different arguments, so the
    fixed branch could never execute
  - three merged fixes were absent from the deployed copies that actually run

Every one of those is invisible to a log reader, because a guard that never
fires produces no logs. This harness stops waiting to OBSERVE enforcement and
instead DEMANDS that each guard refuse something on command.

THE CONTRACT
------------
Each guard declares three scenarios:

  positive  - a realistic action it MUST refuse
  negative  - the closest legitimate action it MUST allow
  fault     - the same positive action, run while one of the guard's own
              dependencies is BROKEN

positive+negative are required and decide the PROVEN verdict. A guard that
blocks everything is as broken as one that blocks nothing, and only the pair
distinguishes them. A guard with no current proof is reported UNVERIFIED and
must not be counted as enforcement.

Hooks are driven END-TO-END as subprocesses with real payloads on stdin and
real decision JSON parsed from stdout -- the same path Claude Code uses -- so
"registered but unreachable" and "fixed but not wired" both surface.

THE FAULT ARM (Issue #1471)
---------------------------
The happy-path pair never asks what a guard does when its OWN machinery
breaks. #1471 is the recorded answer: the prompt-integrity shrinkage gate
stopped enforcing after a field rename -- the deny-message f-string raised
AttributeError, a broad ``except Exception: pass`` swallowed it, and control
fell through to ``return ("allow", ...)``. The guard still FIRED. It just
stopped REFUSING, and nobody noticed, because a guard that allows writes no
log. An audit of unified_pre_tool.py counted 127 fail-open paths (93 bare
``except: pass``, 34 returning an allow-shaped value).

Fail-open is frequently the CORRECT choice -- a broken hook must not lock a
user out of their own editor. The defect is that nothing distinguishes a
deliberate, visible fail-open from an accidental, silent one. So the fault arm
does not assert; it CLASSIFIES, into exactly three outcomes:

  REFUSES               - still denies with its dependency broken. Strongest.
  FAILS OPEN LOUDLY     - allows, but leaves a trace (stderr or a log row).
                          Acceptable when deliberate.
  FAILS OPEN SILENTLY   - allows and leaves no trace. The #1471 shape. This is
                          reported as a FINDING, not as a pass.

The fault arm is ADDITIVE: it never changes a PROVEN/FAILS-OPEN/OVER-BLOCKS
verdict, and its outcomes never change the exit code. Only a broken INSTRUMENT
does (see below) -- because a shim that silently fails to land would make every
fault case pass vacuously, which is this harness committing the exact defect it
exists to detect.

HOW THE FAULT IS INJECTED
-------------------------
A generated ``sitecustomize.py`` is placed on PYTHONPATH of the hook
subprocess, so it runs at interpreter startup BEFORE the hook imports
anything. It patches the named dependency to raise / to lose an attribute /
to refuse log writes. Fixture-level faults (corrupt state file) are applied to
the temp fixture directly.

Every shim-injected fault carries its own positive control: the shim prints
``POB_FAULT_HIT:<target>`` to stderr at the moment it actually intercepts. A
fault case whose FAULT_HIT is absent is reported INJECTION-UNVERIFIED and
fails the run. ``verify_injection_instrument()`` additionally runs a matched
pair before any guard: a shim aimed at a module the hook DOES load (must show
FAULT_HIT) and a shim aimed at a module nothing imports (must show
SHIM_INSTALLED, must NOT show FAULT_HIT, and must reproduce the unfaulted
decision exactly). A probe that returns zero is not evidence of zero.

THE REPO OPT-OUT (Issue #1685)
------------------------------
``.claude/.bypass`` is a SUPPORTED per-repo opt-out: a repo that commits it has
deliberately turned autonomous-dev enforcement off, except for the #1435
protected-infrastructure hard floor, which survives it. A guard that allows
under an active bypass is therefore the design WORKING, and must not be counted
as a guard that broke.

Before this fix the header printed ``bypass : present`` and the per-guard
verdict ignored it entirely, so in an opted-out repo an ordinary inert gate was
labelled ``FAILS-OPEN`` / ``FAILS OPEN SILENTLY`` -- indistinguishable from a
guard that genuinely broke under fault. That inflates the silent count AND
blinds the harness to the very failure it exists to catch. Measured in spektiv
(committed ``.bypass``, 17 Jun): write-pipeline-gate reported FAILS-OPEN with
the hook's own reason reading ``Universal bypass active (#969)``.

Bypass is read through ``hook_bypass.is_bypassed()`` -- the SAME function the
hooks call -- and evaluated PER SCENARIO against the exact cwd the hook
subprocess was given, never once against the project root. That distinction is
load-bearing: five of the eight guards run against temp fixtures that are NOT
under the repo's ``.bypass``, so they stay fully measured even in an opted-out
repo, and a fail-open there is still reported as genuine.

What this CANNOT do: for a scenario that IS under an active bypass, a genuine
fail-open is indistinguishable from the opt-out, because the only way to
neutralise a file bypass is to remove the file -- a mutation of the user's repo
this harness will not make. That limitation is PRINTED, per guard, rather than
resolved silently in either direction.

PORTABILITY (Issue #1586)
-------------------------
This harness ships to consumer repos, so it may NOT assume the autonomous-dev
source layout. Every path is resolved at runtime -- no fixed-depth parent-index
arithmetic, which silently resolves to the wrong directory the moment the file
moves or is installed at a different depth. ``REPO`` comes from the canonical
``path_utils.find_project_root()`` (the sanctioned sink, not a private copy),
and ``HOOKS``/``ARTIFACTS`` are resolved against candidate lists that cover
both the source tree and the installed ``.claude/`` tree.

USAGE
-----
    python3 proof_of_block.py            # replay, exit 1 on any failure
    python3 proof_of_block.py --record   # write artifacts
    python3 proof_of_block.py --json
    python3 proof_of_block.py --no-fault # happy-path arms only
    python3 proof_of_block.py --artifacts DIR       # redirect --record
    python3 proof_of_block.py --check-silent-regression --baseline P
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------
# path resolution
# --------------------------------------------------------------------------
# Exit code used for every "cannot resolve a required directory" case. Distinct
# from 1 (a guard finding) so a caller can tell "the harness could not run"
# apart from "the harness ran and found something".
EXIT_UNRESOLVABLE = 2


def _find_lib_dir() -> Optional[Path]:
    """Locate the autonomous-dev ``lib`` directory across both layouts.

    Mirrors the verified idiom in ``persist_intent_answer.py``: the install
    manifest maps ``scripts`` -> ``.claude/scripts`` and ``lib`` -> ``.claude/lib``
    as siblings, so ``<this file>/../lib`` resolves in the installed tree, and
    the same relative step resolves in the source tree
    (``plugins/autonomous-dev/scripts`` -> ``plugins/autonomous-dev/lib``).

    Returns:
        The first existing candidate directory, or None if none exist.
    """
    for candidate in _lib_dir_candidates():
        if candidate.exists():
            return candidate
    return None


def _lib_dir_candidates() -> list:
    """Candidate ``lib`` directories, in priority order.

    Split out from :func:`_find_lib_dir` so the failure path can print exactly
    what was tried rather than a bare "not found".
    """
    return [
        # Sibling of this script: works in BOTH source and installed layouts.
        Path(__file__).resolve().parent.parent / "lib",
        # Running from a source checkout with a different cwd.
        Path.cwd() / "plugins" / "autonomous-dev" / "lib",
        # Installed into a consumer repo.
        Path.cwd() / ".claude" / "lib",
        # Global install.
        Path.home() / ".autonomous-dev" / "lib",
        # Marketplace install.
        Path.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",
    ]


_LIB_DIR = _find_lib_dir()
if _LIB_DIR is not None and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

try:
    from path_utils import find_project_root
except ImportError:  # pragma: no cover - exercised by the exit-2 path below
    # D1: no inline fallback. A fallback here would be a third copy of
    # _detect_project_root, and if lib/ is unreachable the hooks under test
    # cannot load their own dependencies either -- so failing is correct.
    sys.stderr.write(
        "proof_of_block: cannot import path_utils.find_project_root\n"
        "Expected the autonomous-dev lib/ directory at one of:\n"
        + "".join(f"  {c}\n" for c in _lib_dir_candidates())
        + "See: plugins/autonomous-dev/config/install_manifest.json "
          "(components.lib.target)\n"
    )
    sys.exit(EXIT_UNRESOLVABLE)

try:
    # ONE reader of the bypass rule (Issue #1685). ``is_bypassed`` is the exact
    # function every hook calls, so this harness cannot drift from the hooks it
    # measures. The two underscored names are hook_bypass's OWN readers for the
    # flag file and its git-tracked status; importing them keeps the count of
    # readers at one. Re-deriving either here -- a local ``.exists()`` or a
    # local ``git ls-files`` -- would be a SECOND implementation of a rule that
    # already has one, which is the defect class this repo keeps filing against
    # itself.
    from hook_bypass import ENV_VAR_NAME as BYPASS_ENV_VAR
    from hook_bypass import _find_flag_file_in_chain as find_bypass_flag
    from hook_bypass import _is_git_tracked as bypass_flag_is_committed
    from hook_bypass import check_bypass_staleness, is_bypassed
except ImportError:  # pragma: no cover - same lib/ that path_utils came from
    sys.stderr.write(
        "proof_of_block: cannot import hook_bypass\n"
        "Expected it beside path_utils in the autonomous-dev lib/ directory.\n"
        "Without it this harness cannot tell a deliberate repo opt-out "
        "(.claude/.bypass) apart from a guard that genuinely broke, and a "
        "verdict that cannot carry its own governing configuration is worse "
        "than no verdict.\n"
        "See: plugins/autonomous-dev/config/install_manifest.json "
        "(components.lib.files)\n"
    )
    sys.exit(EXIT_UNRESOLVABLE)


def resolve_hooks_dir(repo: Path, script: Optional[Path] = None) -> Optional[Path]:
    """Resolve the directory holding the hooks under test.

    Args:
        repo: Project root, as returned by ``find_project_root()``.
        script: Path of this script; defaults to ``__file__``. Injectable so
            the tests can drive synthetic source/installed trees.

    Returns:
        The first existing candidate, or None when none exist.
    """
    for candidate in hooks_dir_candidates(repo, script):
        if candidate.is_dir():
            return candidate
    return None


def hooks_dir_candidates(repo: Path, script: Optional[Path] = None) -> list:
    """Candidate hook directories, in priority order.

    Sibling-of-script comes first so an INSTALLED copy tests the installed
    hooks (the ones that actually run) rather than a source tree that may also
    be present. Verifying the copy that executes is the entire point.
    """
    here = Path(script).resolve() if script is not None else Path(__file__).resolve()
    return [
        here.parent.parent / "hooks",
        repo / "plugins" / "autonomous-dev" / "hooks",
        repo / ".claude" / "hooks",
    ]


def resolve_artifacts_dir(repo: Path, override: Optional[str] = None) -> Path:
    """Resolve where ``--record`` writes.

    D2: always ``<repo>/.claude/proofs`` unless overridden. ``.claude/`` exists
    wherever the plugin is installed; ``tests/`` does not, so keying off
    ``tests/`` would make the artifact path depend on whether the consumer repo
    happens to have a test suite.

    Args:
        repo: Project root.
        override: Value of ``--artifacts``, if supplied.

    Returns:
        Directory path (not created here; ``--record`` creates it).
    """
    if override:
        return Path(override).expanduser().resolve()
    return repo / ".claude" / "proofs"


try:
    REPO = find_project_root()
except FileNotFoundError:
    sys.stderr.write(
        "proof_of_block: cannot locate a project root\n"
        f"Expected a .git or .claude directory at or above: {Path.cwd()}\n"
        "Run this from inside a repository.\n"
    )
    sys.exit(EXIT_UNRESOLVABLE)

HOOKS = resolve_hooks_dir(REPO)
if HOOKS is None:
    sys.stderr.write(
        "proof_of_block: cannot locate the hooks directory\n"
        "Tried:\n"
        + "".join(f"  {c}\n" for c in hooks_dir_candidates(REPO))
        + "Install the plugin (/sync) so .claude/hooks/ exists.\n"
    )
    sys.exit(EXIT_UNRESOLVABLE)

# Default only; main() re-resolves once --artifacts is parsed.
ARTIFACTS = resolve_artifacts_dir(REPO)

BLOCKED = {"deny", "block", "ask"}


# --------------------------------------------------------------------------
# the repo opt-out (Issue #1685)
# --------------------------------------------------------------------------
# A guard that allows under an active .claude/.bypass is INERT BY REQUEST, not
# broken. These helpers carry that governing configuration into the verdict so
# a reader never has to correlate the header against a table two screens down
# -- which is exactly how a correct spektiv result was first written up as a
# fail-open finding.

# Verdict for a guard that allowed its positive case while subject to an active
# bypass. Deliberately NOT one of PROVEN / FAILS-OPEN: it is neither proof of
# enforcement nor evidence of breakage.
NOT_ENFORCED = "NOT-ENFORCED"

# Bypass forms. CLAUDE.md gives them different meanings and #1434/#1601 give
# them different staleness rules, so they must not be merged.
BYPASS_ABSENT = "absent"
BYPASS_COMMITTED = "committed"      # durable per-repo opt-out (supported)
BYPASS_UNCOMMITTED = "uncommitted"  # emergency escape hatch (#1434)


def describe_bypass(start_dir: Path) -> dict:
    """Classify the ``.claude/.bypass`` governing ``start_dir``.

    Reports the FORM, not merely presence. A committed flag is the documented
    durable opt-out; an uncommitted one is an emergency escape hatch that
    #1434 warns about once it goes stale. Reporting them as one state loses
    the only thing that distinguishes a policy decision from a forgotten file.

    The env-var arm is reported separately by :func:`env_bypass_note` because
    :func:`drive_raw` strips it from every hook subprocess -- it cannot be the
    cause of anything measured here.

    Args:
        start_dir: Directory to begin the upward walk from (a project root).

    Returns:
        dict with ``active``, ``form``, ``path`` (str or None) and ``warning``
        (the #1434/#1601 staleness string, or None).
    """
    flag = find_bypass_flag(start_dir)
    if flag is None:
        return {"active": False, "form": BYPASS_ABSENT, "path": None,
                "warning": None}
    form = (BYPASS_COMMITTED if bypass_flag_is_committed(flag)
            else BYPASS_UNCOMMITTED)
    return {
        "active": True,
        "form": form,
        "path": str(flag),
        "warning": check_bypass_staleness(start_dir),
    }


def env_bypass_note() -> Optional[str]:
    """Return a note if the OPERATOR's shell exports the bypass env var.

    :func:`drive_raw` removes ``AUTONOMOUS_DEV_BYPASS`` from every hook
    subprocess, so an exported value governs nothing that this harness
    measures. Silence about it would still be wrong: a reader who knows they
    set it deserves to be told it was neutralised rather than left to assume
    the run was permissive.

    Returns:
        A one-line note, or None when the variable is unset.
    """
    if os.environ.get(BYPASS_ENV_VAR) is None:
        return None
    return (f"{BYPASS_ENV_VAR} is set in this shell but is STRIPPED from every "
            f"hook subprocess by this harness -- it governs nothing below")


def scenario_bypassed(root: Path) -> bool:
    """Was the hook subprocess for a scenario rooted at ``root`` bypassed?

    Asks ``hook_bypass.is_bypassed`` with the SAME start directory the hook
    itself used: :func:`drive_raw` runs the subprocess with ``cwd=root`` and
    the hook calls ``is_bypassed()`` with no argument, which defaults to its
    cwd. Evaluating this against the PROJECT ROOT instead would be wrong for
    the five guards that run against temp fixtures outside the repo -- they
    are not under the repo's flag, so a fail-open there is genuine and must
    keep saying so.

    The env arm is neutralised for the duration of the call because
    :func:`drive_raw` strips ``AUTONOMOUS_DEV_BYPASS`` from the subprocess
    environment. Consulting it unfiltered would relabel every genuine
    fail-open as a repo opt-out on any machine whose shell happens to export
    the variable -- a probe reporting the operator's environment instead of
    the system under test.

    Args:
        root: The cwd the hook subprocess was given.

    Returns:
        True iff the hook saw an active bypass for that scenario.
    """
    saved = os.environ.pop(BYPASS_ENV_VAR, None)
    try:
        return is_bypassed(root)
    finally:
        if saved is not None:
            os.environ[BYPASS_ENV_VAR] = saved


# --------------------------------------------------------------------------
# scenario fixtures
# --------------------------------------------------------------------------

def _adev_repo(root: Path) -> Path:
    """A directory that repo_detector recognises as autonomous-dev.

    Requires BOTH a .git directory AND a marketplace.json whose CONTENT
    contains the string "autonomous-dev". Learned the hard way: an empty
    ``{}`` passes the exists() check, fails the content check, and silently
    reproduces nothing -- a fixture that cannot observe the behaviour it names.

    Args:
        root: Throwaway directory to build the fixture in.

    Returns:
        ``root``, populated.

    Raises:
        RuntimeError: If ``root`` is the real repository. This function runs
            ``git init`` and OVERWRITES ``marketplace.json`` with a 31-byte
            stub; the real file is the marker CLAUDE.md documents as the
            detector for self-maintenance mode. The refusal lives HERE rather
            than at a call site because a call-site check only covers the call
            sites that exist today -- ``_plan_exited`` also delegates here, and
            reordering ``GUARDS`` is an ordinary maintenance edit.
    """
    if Path(root).resolve() == REPO.resolve():
        raise RuntimeError(
            f"refusing to build the autonomous-dev fixture inside the real "
            f"repo: {REPO}\n"
            f"This fixture runs `git init` and overwrites "
            f"plugins/autonomous-dev/.claude-plugin/marketplace.json with a "
            f"stub.\n"
            f"Expected: a throwaway temp directory. Guards that must target "
            f"the canonical source use the _real_repo fixture instead."
        )
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "."], cwd=str(root),
                   capture_output=True, check=False)
    md = root / "plugins" / "autonomous-dev" / ".claude-plugin"
    md.mkdir(parents=True, exist_ok=True)
    (md / "marketplace.json").write_text('{"name": "autonomous-dev"}')
    (root / "plugins" / "autonomous-dev" / "lib").mkdir(parents=True, exist_ok=True)
    return root


def _plan_exited(root: Path) -> Path:
    """An autonomous-dev repo sitting at the plan_exited stage."""
    _adev_repo(root)
    (root / ".claude" / "plan_mode_exit.json").write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "proof-of-block",
        "stage": "plan_exited",
    }))
    return root


def _real_repo(root: Path) -> Path:
    """Use the REAL repo as the target, ignoring the temp dir.

    Required for guards whose scoping keys off the canonical autonomous-dev
    source. A synthetic temp repo does NOT trigger canonical-source detection,
    so the guard correctly declines to fire there -- and a harness using a temp
    fixture reports a false FAILS-OPEN.

    The hook never performs the tool call -- PreToolUse only RETURNS a
    decision -- so the ACTION under test mutates nothing.

    That is not the same as "this mutates nothing", and an earlier revision of
    this docstring claimed the stronger thing. It was false. Deciding is not
    free: the hook reads and prunes its own state on the way to a decision, and
    two of those pruning arms delete real files under this cwd.

      - ``_is_stale_session()`` treats the driven ``session_id`` as an
        OWNERSHIP CLAIM and unlinks ``.claude/local/implement_pipeline_state.json``
        when the stored id differs. Measured: a sentinel carrying a real
        session id was DELETED, while one carrying the probe's own tag, one
        carrying ``unknown``, and one driven with a matching id all SURVIVED.
      - ``_read_plan_exit_marker()`` unlinks ``.claude/plan_mode_exit.json``
        when it is stale-by-TTL or corrupt. Measured: 5 of 8 real-repo runs
        deleted a planted stale marker; a fresh marker and a no-hook-run
        control both survived.

    Both are neutralised in :func:`drive_raw` -- by redirecting
    ``PIPELINE_STATE_FILE`` to a throwaway path, and by snapshot/restore of the
    marker -- so the claim above is now true BY CONSTRUCTION rather than by
    assertion. See :func:`drive_raw` and :func:`_preserved_plan_exit_marker`.

    Caught by comparing against a control that ran the same payload against the
    real repo and got `deny` -- the first draft of this harness reported two
    false FAILS-OPEN before that comparison.
    """
    return REPO


# --------------------------------------------------------------------------
# fault injection
# --------------------------------------------------------------------------
# A guard's happy-path pair says nothing about what it does when its OWN
# dependencies break. These fault descriptors name a dependency the guard
# actually touches (verified by reading the guard, not guessed) and break it.

# Marker prefix the shim writes to stderr. Everything with this prefix is
# instrument chatter and is stripped before judging whether the GUARD was loud.
MARKER = "POB_"
MARK_INSTALLED = MARKER + "SHIM_INSTALLED:"
MARK_HIT = MARKER + "FAULT_HIT:"

# A module name no dependency chain in this repo imports. Used as the
# instrument's NEGATIVE control: the shim must install and never fire.
INERT_MODULE = "pob_module_that_does_not_exist"

FAULT_TOOL_INTENT_IMPORT = {
    "id": "import_raises:tool_intent",
    "kind": "import_raises",
    "module": "tool_intent",
    "what": "the tool_intent import raises ImportError (a required import "
            "raises -- the #1471 shape)",
    "touches": "_ti_is_write() delegates every write classification to "
               "tool_intent.is_write; on import failure it falls back to the "
               "literal 4-tuple ('Write','Edit','MultiEdit','NotebookEdit')",
}

FAULT_TOOL_INTENT_ATTR = {
    "id": "attr_missing:tool_intent.is_write",
    "kind": "attr_missing",
    "module": "tool_intent",
    "attr": "is_write",
    "what": "tool_intent loads but no longer exposes is_write (a helper that "
            "no longer has the attribute -- the #1471 mechanism precisely)",
    "touches": "_ti_is_write() capability-probes with hasattr because "
               "tool_intent is spec_from_file_location-loaded; a stale install "
               "can expose classify/write_targets but not is_write",
}

FAULT_TIER_CLASSIFIER_IMPORT = {
    "id": "import_raises:edit_tier_classifier",
    "kind": "import_raises",
    "module": "edit_tier_classifier",
    "what": "the edit_tier_classifier import raises ImportError",
    "touches": "_check_write_pipeline_required() calls "
               "_safe_classify_edit_tier() to pick the fix/light/full tier "
               "printed in the deny directive",
}

FAULT_LOGS_UNWRITABLE = {
    "id": "logs_unwritable",
    "kind": "logs_unwritable",
    "module": "<log destination>",
    "what": "every write/append open() under a logs/ directory raises "
            "OSError(EACCES) -- does enforcement survive telemetry failure?",
    "touches": "output_decision is wrapped by hook_telemetry's "
               "block_event_decorator, which appends to "
               ".claude/logs/hook-blocks.jsonl on every deny; "
               "_log_pretool_activity appends to .claude/logs/activity/",
}

# FAULTS CONSIDERED AND REJECTED -- recorded so the next reader does not
# redo the analysis. A fault the guard never touches proves nothing; a fault
# that lands on an unreachable branch proves less than nothing, because it
# looks like a result.
#
#   agent_dispatch_sentinel (#1296) -- named as a candidate, NOT injected.
#     _enforce_protected_infrastructure imports it only inside the
#     ``if pipeline_active:`` branch. None of the seven fixtures has an
#     active pipeline, so the import never executes and the shim would emit
#     no FAULT_HIT. Reaching it means writing real pipeline state into the
#     canonical repo, which this harness must not do. Its fail-CLOSED
#     ImportError handler is therefore UNVERIFIED here, not proven.
#
#   prompt_integrity (#1471, :1351) -- the module whose silent fail-open
#     motivated this whole arm, and still NOT injectable through this
#     registry: it is reached from validate_prompt_integrity on the Task
#     tool, and all seven guards drive Write/Edit/MCP tools. Faulting it
#     needs a Task-shaped guard in GUARDS first.
#
#   repo_detector -- _is_adev_project falls back to True (fail-closed) on
#     import failure, so the fault is a no-op for every scenario here.

FAULT_PLAN_MARKER_CORRUPT = {
    "id": "state_corrupt:.claude/plan_mode_exit.json",
    "kind": "state_corrupt",
    "module": ".claude/plan_mode_exit.json",
    "path": ".claude/plan_mode_exit.json",
    "what": "the plan-exit state file is unreadable (truncated garbage)",
    "touches": "_read_plan_exit_marker() is the sole source of the stage this "
               "gate switches on; its corruption branch decides whether an "
               "unverifiable stage restricts or passes through",
    # Positive marker the corruption branch emits when it runs (Issue #1684),
    # the state-file analogue of the shim's FAULT_HIT. Needed because the
    # previous landing proof -- "the marker file was unlinked" -- was coupled
    # to the fail-open behavior #1684 removed, and reported the branch as
    # unreached the moment the branch stopped unlinking.
    "landing_marker": "plan_exit_marker_corrupt:",
}


SHIM_SOURCE = r'''
"""Generated by proof_of_block.py. Breaks ONE dependency at interpreter
startup, before the hook under test imports anything.

Two interception mechanisms are needed because unified_pre_tool.py loads its
libraries BOTH ways:
  1. sys.meta_path finder      -> plain ``from foo import bar`` (sys.path)
  2. spec_from_file_location   -> the defensive importlib.util path-loads
A shim covering only (1) would silently miss tool_intent entirely and every
fault case would pass vacuously.
"""
import builtins
import io
import json
import os
import sys

_CFG = {}
try:
    _CFG = json.loads(os.environ.get("POB_FAULT") or "{}")
except Exception:
    _CFG = {}

_KIND = _CFG.get("kind") or ""
_MODULE = _CFG.get("module") or ""
_ATTR = _CFG.get("attr") or ""
_TARGET = _MODULE or _KIND


def _mark(tag):
    try:
        sys.stderr.write("POB_%s:%s\n" % (tag, _TARGET))
        sys.stderr.flush()
    except Exception:
        pass


if _KIND:
    _mark("SHIM_INSTALLED")


class _Injected(ImportError):
    """Raised in place of the real import."""


def _strip_attr(module):
    """Positive control fires HERE: the attribute is really gone."""
    if _ATTR and hasattr(module, _ATTR):
        try:
            delattr(module, _ATTR)
            _mark("FAULT_HIT")
        except Exception:
            setattr(module, _ATTR, None)
            _mark("FAULT_HIT")


class _StrippingLoader:
    """Delegates to the real loader, then removes the target attribute."""

    def __init__(self, inner):
        self._inner = inner

    def create_module(self, spec):
        return self._inner.create_module(spec)

    def exec_module(self, module):
        self._inner.exec_module(module)
        _strip_attr(module)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _is_target(fullname, location):
    if fullname and str(fullname).rsplit(".", 1)[-1] == _MODULE:
        return True
    base = os.path.basename(str(location or ""))
    return bool(_MODULE) and base == _MODULE + ".py"


if _KIND in ("import_raises", "attr_missing"):
    import importlib.util as _ilu

    _orig_sffl = _ilu.spec_from_file_location

    def _patched_sffl(name=None, location=None, *args, **kwargs):
        if _is_target(name, location):
            if _KIND == "import_raises":
                _mark("FAULT_HIT")
                raise _Injected("POB injected fault: %s" % _MODULE)
            spec = _orig_sffl(name, location, *args, **kwargs)
            if spec is not None and getattr(spec, "loader", None) is not None:
                spec.loader = _StrippingLoader(spec.loader)
            return spec
        return _orig_sffl(name, location, *args, **kwargs)

    _ilu.spec_from_file_location = _patched_sffl

    class _Finder:
        """meta_path entry for plain sys.path imports of the target."""

        _busy = False

        def find_spec(self, fullname, path=None, target=None):
            if fullname.rsplit(".", 1)[-1] != _MODULE:
                return None
            if _KIND == "import_raises":
                _mark("FAULT_HIT")
                raise _Injected("POB injected fault: %s" % _MODULE)
            if _Finder._busy:
                return None
            _Finder._busy = True
            try:
                for finder in sys.meta_path:
                    if isinstance(finder, _Finder):
                        continue
                    try:
                        spec = finder.find_spec(fullname, path, target)
                    except Exception:
                        continue
                    if spec is not None:
                        if getattr(spec, "loader", None) is not None:
                            spec.loader = _StrippingLoader(spec.loader)
                        return spec
            finally:
                _Finder._busy = False
            return None

    sys.meta_path.insert(0, _Finder())


if _KIND == "logs_unwritable":
    _WRITE_MODES = ("w", "a", "x", "+")

    def _blocked(path, mode):
        try:
            text = os.fspath(path)
        except TypeError:
            return False
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
        text = str(text).replace("\\", "/")
        if "/logs/" not in text and not text.endswith("/logs"):
            return False
        return any(m in str(mode) for m in _WRITE_MODES)

    _orig_open = builtins.open

    def _patched_open(file, mode="r", *args, **kwargs):
        if _blocked(file, mode):
            _mark("FAULT_HIT")
            raise OSError(13, "POB injected fault: log destination unwritable")
        return _orig_open(file, mode, *args, **kwargs)

    # pathlib.Path.open goes through io.open, which is a SEPARATE binding
    # from builtins.open even though they start as the same object. Patching
    # only builtins.open misses hook_telemetry's log_path.open("a") entirely.
    builtins.open = _patched_open
    io.open = _patched_open
'''


# --------------------------------------------------------------------------
# the guard registry
# --------------------------------------------------------------------------
# Each entry: positive (must refuse) + negative control (must permit)
# + fault (classify what it does with a real dependency broken).

GUARDS = [
    {
        "guard": "protected-infrastructure-hard-floor",
        "issue": "#1435",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "direct Write to a protected lib path must be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "plugins/autonomous-dev/lib/pipeline_state.py"),
                "content": "x = 1\n"},
        },
        "negative": {
            "why": "an ordinary docs write must NOT be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "docs" / "notes.md"),
                "content": "# notes\n"},
        },
        "fault": FAULT_TOOL_INTENT_IMPORT,
    },
    {
        "guard": "mcp-write-classification",
        "issue": "#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "an MCP editor must be refused on a protected path, "
                   "classified by EFFECT not by tool name",
            "tool_name": "mcp__serena__replace_content",
            "tool_input": lambda r: {
                "relative_path": "plugins/autonomous-dev/lib/pipeline_state.py",
                "needle": "a", "repl": "b", "mode": "literal"},
        },
        "negative": {
            "why": "a read-only MCP tool must NOT be refused",
            "tool_name": "mcp__serena__find_symbol",
            "tool_input": lambda r: {"name_path": "foo"},
        },
        "fault": FAULT_TOOL_INTENT_IMPORT,
    },
    {
        "guard": "plan-exit-gate",
        "issue": "#926/#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _plan_exited,
        "positive": {
            "why": "at plan_exited an MCP writer must be refused",
            "tool_name": "mcp__serena__replace_content",
            "tool_input": lambda r: {
                "relative_path": "src/a.py", "needle": "a",
                "repl": "b", "mode": "literal"},
        },
        "negative": {
            "why": "at plan_exited the mandated search path must still work; "
                   "reading is not acting",
            "tool_name": "mcp__searxng__search",
            "tool_input": lambda r: {"query": "python"},
        },
        "fault": FAULT_PLAN_MARKER_CORRUPT,
    },
    {
        # I hit this one myself today: it correctly refused a new script.
        "guard": "write-pipeline-gate",
        "issue": "#1142",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "creating a NEW production code file outside the pipeline "
                   "must be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "scripts" / "pob_probe_newfile.py"),
                "content": "print('x')\n"},
        },
        "negative": {
            "why": "a markdown doc must NOT be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "docs" / "pob_probe_note.md"),
                "content": "# note\n"},
        },
        "fault": FAULT_TIER_CLASSIFIER_IMPORT,
    },
    {
        "guard": "mcp-rename-symbol-is-a-write",
        "issue": "#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "rename_symbol mutates files and must be classified as a "
                   "write even though its name contains no write verb",
            "tool_name": "mcp__serena__rename_symbol",
            "tool_input": lambda r: {
                "relative_path": "plugins/autonomous-dev/lib/pipeline_state.py",
                "name_path": "save_pipeline", "new_name": "x"},
        },
        "negative": {
            "why": "get_symbols_overview only reads",
            "tool_name": "mcp__serena__get_symbols_overview",
            "tool_input": lambda r: {"relative_path": "README.md"},
        },
        "fault": FAULT_TOOL_INTENT_ATTR,
    },
    {
        "guard": "mcp-side-effect-set",
        "issue": "#1503 AC#19",
        "hook": "unified_pre_tool.py",
        "fixture": _plan_exited,
        "positive": {
            "why": "browser_evaluate executes arbitrary JS and carries NO path "
                   "or content argument, so no shape test can catch it -- it "
                   "must be caught by the explicit side-effect set",
            "tool_name": "mcp__playwright__browser_evaluate",
            "tool_input": lambda r: {"function": "() => document.title"},
        },
        "negative": {
            "why": "browser_snapshot only observes",
            "tool_name": "mcp__playwright__browser_snapshot",
            "tool_input": lambda r: {},
        },
        "fault": FAULT_LOGS_UNWRITABLE,
    },
    {
        "guard": "unenumerated-mcp-writer-by-shape",
        "issue": "#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _plan_exited,
        "positive": {
            "why": "a tool from a server nobody enumerated, carrying a path "
                   "AND content, must be refused BY SHAPE -- this is the whole "
                   "point of classifying by effect rather than by name",
            "tool_name": "mcp__someserver__apply_patch",
            "tool_input": lambda r: {
                "relative_path": "src/a.py", "content": "x = 1\n"},
        },
        "negative": {
            "why": "the same unknown server's read tool must NOT be refused",
            "tool_name": "mcp__someserver__list_things",
            "tool_input": lambda r: {"query": "x"},
        },
        "fault": FAULT_TOOL_INTENT_IMPORT,
    },
    {
        # The first spec in this registry aimed at a hook OTHER than
        # unified_pre_tool.py. The other seven all point at that one file, so
        # plan_gate -- a live PreToolUse gate whose refusals went entirely
        # unrecorded until #1611 -- was uncovered here despite this module's
        # own docstring naming it as the motivating fail-open.
        #
        # WHAT THIS PROVES, and what it does NOT. drive_raw() runs the hook as
        # a subprocess and reads the envelope it prints on stdout. So this
        # spec proves plan_gate EMITS a refusal on the bad case and permits
        # the closest legitimate one -- the both-arms evidence that was
        # missing. It does NOT prove Claude Code HONOURS that refusal, and no
        # arm of this harness can: plan_gate emits
        # ``permissionDecision: "block"``, which is outside PreToolUse's
        # ``allow|deny|ask`` enum, and only the real client can say what it
        # does with an out-of-enum value. That is #1589's question, and the
        # recorded rows carry ``honoured: "unverified"`` until it is answered.
        # BLOCKED includes "block", so this harness reads the emitted value at
        # face value -- which is exactly the assumption #1589 is testing.
        "guard": "plan-gate-requires-a-plan",
        "issue": "#1611/#1589",
        "hook": "plan_gate.py",
        "fixture": _adev_repo,
        "positive": {
            "why": "a large NEW production-code write with no plan file "
                   "present must be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "src" / "a.py"),
                "content": "x = 1\n" * 200},
        },
        "negative": {
            "why": "a documentation file must NOT be refused -- the doc "
                   "exemption is the closest legitimate action to the one "
                   "above, differing only in extension",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "docs" / "notes.md"),
                "content": "# note\n"},
        },
        "fault": FAULT_TOOL_INTENT_IMPORT,
    },
]


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

SESSION_TAG = "proof-of-block"


def _log_rows(cwd: Path, tag: str = SESSION_TAG) -> int:
    """Count hook-log rows attributable to THIS harness under ``cwd``.

    The "did the guard leave a trace?" probe for the fault arm.

    Counts ROWS CARRYING ``tag``, not bytes. A byte-delta probe is wrong here
    and the first draft used one: four of the seven guards run against the
    REAL repo, whose ``.claude/logs/activity/`` the live Claude Code session
    is appending to concurrently. That probe reported 434B of "trace" on runs
    where the hook may have written nothing -- it was measuring the observer.
    Every row this harness provokes carries ``session_id: "proof-of-block"``
    (set in the drive payload and preserved by _sanitize_session_id, which
    permits hyphens), so filtering on it excludes every other writer by
    construction.

    Args:
        cwd: Project root whose ``.claude/logs`` tree to scan.
        tag: Substring identifying this harness's rows.

    Returns:
        Number of matching lines across all hook log files.
    """
    total = 0
    logs = cwd / ".claude" / "logs"
    seen: set = set()
    for pattern in ("hook-blocks.jsonl", "activity/*.jsonl", "*.jsonl"):
        for path in logs.glob(pattern):
            if path in seen:
                continue
            seen.add(path)
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            total += sum(1 for line in text.splitlines() if tag in line)
    return total


def _log_lines_containing(cwd: Path, needle: str) -> int:
    """Count hook-log lines under ``cwd`` containing ``needle``.

    The landing proof for ``state_corrupt`` faults: a branch that emits an
    attributable row has demonstrably executed. Unlike :func:`_log_rows`
    this does not filter on the harness session tag -- a state fixture is a
    private temp tree with no concurrent writers, and the needle is itself
    specific enough to exclude every other producer.

    Args:
        cwd: Fixture root whose ``.claude/logs`` tree to scan.
        needle: Substring the branch under test is known to emit.

    Returns:
        Number of matching lines; 0 when ``needle`` is empty.
    """
    if not needle:
        return 0
    total = 0
    logs = cwd / ".claude" / "logs"
    seen: set = set()
    for pattern in ("hook-blocks.jsonl", "activity/*.jsonl", "*.jsonl"):
        for path in logs.glob(pattern):
            if path in seen:
                continue
            seen.add(path)
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            total += sum(1 for line in text.splitlines() if needle in line)
    return total


def _write_shim(fault: Optional[dict], stage: Path) -> dict:
    """Materialise the sitecustomize shim and return env overrides.

    Args:
        fault: Fault descriptor, or None for an unfaulted run.
        stage: Directory to write ``sitecustomize.py`` into. Must outlive the
            subprocess.

    Returns:
        Env overrides to merge into the subprocess environment. Empty when
        ``fault`` is None or is a fixture-level (non-shim) fault.
    """
    if not fault or fault["kind"] == "state_corrupt":
        return {}
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "sitecustomize.py").write_text(SHIM_SOURCE)
    cfg = {k: fault.get(k, "") for k in ("kind", "module", "attr")}
    existing = os.environ.get("PYTHONPATH", "")
    return {
        "PYTHONPATH": str(stage) + (os.pathsep + existing if existing else ""),
        "POB_FAULT": json.dumps(cfg),
    }


_PLAN_EXIT_MARKER_REL = ".claude/plan_mode_exit.json"


@contextmanager
def _preserved_plan_exit_marker(cwd: Path):
    """Snapshot and restore the REAL repo's plan-mode-exit marker.

    ``unified_pre_tool._read_plan_exit_marker()`` resolves
    ``.claude/plan_mode_exit.json`` from ``os.getcwd()`` and UNLINKS it when it
    is stale-by-TTL or corrupt. For the four ``_real_repo`` guards that cwd is
    the user's repository, so an ordinary probe run silently consumed real
    plan-mode state. Measured: 5 of 8 real-repo guard runs deleted a planted
    stale marker; a planted-but-not-driven marker and a fresh (in-TTL) marker
    both survived, so the deletions were signal and not an artefact.

    Unlike the pipeline sentinel there is no environment override to redirect
    (the path is a module constant joined to the cwd), so the hazard is removed
    by snapshot/restore instead.

    Scoped to ``cwd == REPO`` deliberately. Temp fixtures are throwaway, AND
    restoring there would break :func:`run_fault`'s positive control for
    ``FAULT_PLAN_MARKER_CORRUPT``, which proves the fault landed precisely BY
    the hook having consumed the fixture's marker.

    Args:
        cwd: Working directory the hook subprocess will run in.

    Yields:
        None.
    """
    if Path(cwd).resolve() != REPO.resolve():
        yield
        return

    marker = REPO / _PLAN_EXIT_MARKER_REL
    try:
        snapshot = marker.read_bytes()
    except OSError:
        snapshot = None

    try:
        yield
    finally:
        try:
            if snapshot is None:
                # The probe must not LEAVE one either: a plan-exit marker this
                # harness created would gate the user's next write.
                marker.unlink(missing_ok=True)
            elif not marker.exists() or marker.read_bytes() != snapshot:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_bytes(snapshot)
        except OSError as exc:
            sys.stderr.write(
                f"proof_of_block: could not restore {marker}: {exc}\n"
                f"Real plan-mode state may have been consumed by a probe run.\n"
            )


def drive_raw(hook: Path, tool_name: str, tool_input: dict, cwd: Path,
              *, env_overrides: Optional[dict] = None) -> dict:
    """Run the hook the way Claude Code does, keeping stderr and log deltas.

    Every run is isolated from the REAL repository's pipeline state by
    construction. ``session_id`` below is not merely a label: the hook reads it
    as an OWNERSHIP CLAIM over the sentinel, and ``_is_stale_session()`` unlinks
    ``.claude/local/implement_pipeline_state.json`` outright when the stored id
    differs from the incoming one. Every run of this harness therefore used to
    DELETE the live sentinel of whatever session happened to be in flight --
    against the real repo for four of the seven guards -- reaching the exact
    deletion Issue #803's Bash guard hard-blocks, without ever traversing it.
    ``/health-check`` invokes this script, so a developer could degrade their
    own enforcement posture mid-``/implement`` with no indication.

    ``PIPELINE_STATE_FILE`` is already honoured by ``unified_pre_tool`` (it is
    the sanctioned override), so pointing it at a throwaway directory removes
    the hazard by construction rather than by remembering to avoid it. It also
    makes the harness DETERMINISTIC: results no longer depend on whether a
    pipeline happens to be active on the machine at the moment it runs, which is
    an uncontrolled variable in an instrument whose whole purpose is measurement.

    Args:
        hook: Path to the hook script.
        tool_name: PreToolUse tool name.
        tool_input: PreToolUse tool input.
        cwd: Working directory for the subprocess (also CLAUDE_PROJECT_DIR).
        env_overrides: Extra environment entries (used to install the shim).

    Returns:
        dict with ``decision``, ``reason``, ``stderr`` (shim markers removed),
        ``markers`` (the shim lines), and ``log_rows``.
    """
    payload = {
        # Same value _log_rows() filters on -- see its docstring.
        "session_id": SESSION_TAG,
        "transcript_path": "/dev/null",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(cwd)
    for k in ("AUTONOMOUS_DEV_BYPASS", "ENFORCEMENT_LEVEL", "SKIP_PLAN_CHECK",
              "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW"):
        env.pop(k, None)

    with tempfile.TemporaryDirectory(prefix="pob-state-") as state_dir:
        env["PIPELINE_STATE_FILE"] = str(
            Path(state_dir) / "implement_pipeline_state.json")
        # env_overrides last so a caller can still aim a fault at the sentinel
        # deliberately; nothing in this module does.
        env.update(env_overrides or {})

        with _preserved_plan_exit_marker(cwd):
            before = _log_rows(cwd)
            p = subprocess.run([sys.executable, str(hook)],
                               input=json.dumps(payload), capture_output=True,
                               text=True, timeout=120, cwd=str(cwd), env=env)
            after = _log_rows(cwd)

    decision, reason = "allow", ""
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        hso = d.get("hookSpecificOutput", {})
        decision = hso.get("permissionDecision") or d.get("decision") or decision
        reason = (hso.get("permissionDecisionReason") or d.get("reason") or reason)

    markers, noise = [], []
    for line in (p.stderr or "").splitlines():
        (markers if line.strip().startswith(MARKER) else noise).append(line)

    return {
        "decision": decision,
        "reason": reason.strip(),
        "stderr": "\n".join(noise).strip(),
        "markers": markers,
        "log_rows": max(0, after - before),
    }


def drive(hook: Path, tool_name: str, tool_input: dict, cwd: Path) -> tuple:
    """Run the hook the way Claude Code does. Returns (decision, reason)."""
    r = drive_raw(hook, tool_name, tool_input, cwd)
    return r["decision"], r["reason"]


REFUSES = "REFUSES"
LOUD = "FAILS OPEN LOUDLY"
SILENT = "FAILS OPEN SILENTLY"
UNVERIFIED_INJECTION = "INJECTION-UNVERIFIED"

# A FOURTH outcome (Issue #1685), applied AFTER classify_outcome and only to a
# fail-open observed while the scenario was subject to an active repo opt-out.
# REFUSES is never rewritten: a guard that still denies under bypass is the
# #1435 hard floor doing its job, and folding that into an "opt-out" bucket
# would erase the strongest result in the run.
NOT_ENFORCED_OUTCOME = "NOT ENFORCED (repo opt-out)"


def _apply_state_corruption(root: Path, fault: dict) -> str:
    """Corrupt a state file in the fixture and prove the corruption landed.

    Args:
        root: Fixture root.
        fault: A ``state_corrupt`` descriptor carrying ``path``.

    Returns:
        The garbage bytes actually present on disk after writing, read back.

    Raises:
        RuntimeError: If the target does not already exist (a fixture that
            never had the state file would make the fault a no-op) or if the
            corruption did not survive the write.
    """
    target = root / fault["path"]
    if root == REPO:
        raise RuntimeError(
            "refusing to corrupt state inside the real repo; "
            f"{fault['id']} requires a temp fixture")
    if not target.exists():
        raise RuntimeError(
            f"fixture has no {fault['path']} to corrupt -- the fault would be "
            "a no-op and the fault case would pass vacuously")
    garbage = '{"stage": "plan_ex'  # truncated mid-JSON
    target.write_text(garbage)
    readback = target.read_text()
    if readback != garbage:
        raise RuntimeError(f"corruption did not land: {readback!r}")
    return readback


def run_fault(spec: dict, hook: Path) -> dict:
    """Run the guard's positive action with one of its dependencies broken.

    Classifies into REFUSES / FAILS OPEN LOUDLY / FAILS OPEN SILENTLY. Does
    NOT assert a preferred outcome -- fail-open is often correct, and the
    deliverable is the classification. Returns
    ``INJECTION-UNVERIFIED`` when the fault cannot be proven to have landed.
    """
    fault = spec.get("fault")
    if not fault:
        return {"outcome": UNVERIFIED_INJECTION,
                "detail": "no fault declared for this guard"}

    pos, neg = spec["positive"], spec["negative"]
    out = {"fault": fault["id"], "what": fault["what"],
           "touches": fault["touches"], "tool": pos["tool_name"]}

    with tempfile.TemporaryDirectory(prefix="pob-fault-") as d:
        stage = Path(d)
        root = spec["fixture"](stage / "fixture")
        # Read the governing configuration against the cwd this scenario will
        # actually run in, BEFORE the run, so the outcome can carry it.
        bypassed = scenario_bypassed(root)
        out["bypassed"] = bypassed
        landed_proof = ""

        if fault["kind"] == "state_corrupt":
            try:
                _apply_state_corruption(root, fault)
            except RuntimeError as exc:
                out["outcome"] = UNVERIFIED_INJECTION
                out["detail"] = str(exc)
                return out

        # AMBIENT BASELINE for the trace probe.
        #
        # unified_pre_tool writes one PreToolUse activity row for EVERY call
        # it permits, fault or no fault. Measured side by side, an ordinary
        # legitimate allow and a faulted fail-open produce structurally
        # identical rows -- same hook, same decision, same reason shape, only
        # the tool name differs. Nothing in the row says a dependency broke.
        #
        # So "a row exists" is NOT evidence the guard was loud, and the first
        # draft of this probe reported four guards LOUD on exactly that
        # basis. A trace only counts when the FAULTED run leaves something an
        # ordinary permitted call does not. The guard's own negative arm --
        # a legitimate allow through the same hook, unfaulted -- is that
        # baseline.
        amb = drive_raw(hook, neg["tool_name"], neg["tool_input"](root), root)
        ambient_rows, ambient_stderr = amb["log_rows"], amb["stderr"]

        overrides = _write_shim(fault, stage / "shim")
        res = drive_raw(hook, pos["tool_name"], pos["tool_input"](root), root,
                        env_overrides=overrides)

        # ---- positive control for the injection itself -------------------
        # A shim that fails to land makes every fault case pass vacuously.
        # The shim prints FAULT_HIT at the moment it actually intercepts;
        # fixture faults prove themselves by the state file being consumed.
        if fault["kind"] == "state_corrupt":
            # Two independent proofs the branch ran; either suffices.
            #   (a) the branch emitted its attributable marker row, or
            #   (b) the marker file was consumed (the stale/no-clock paths).
            # (a) is primary: (b) alone was the old proof and it silently
            # inverted when the branch stopped unlinking (Issue #1684).
            target = root / fault["path"]
            consumed = not target.exists()
            traced = _log_lines_containing(root, fault.get("landing_marker", ""))
            if not consumed and not traced:
                out["outcome"] = UNVERIFIED_INJECTION
                out["detail"] = (
                    f"{fault['path']} still present after the run AND no "
                    f"{fault.get('landing_marker')!r} row in the fixture logs "
                    "-- the corrupt-marker branch never ran, so the fault was "
                    "not reached")
                return out
            landed_proof = (
                f"{traced} {fault.get('landing_marker')!r} row(s) in fixture logs"
                if traced
                else f"{fault['path']} consumed (unlinked) by the hook")
        else:
            hits = [m for m in res["markers"] if m.startswith(MARK_HIT)]
            if not hits:
                out["outcome"] = UNVERIFIED_INJECTION
                out["detail"] = (
                    f"no {MARK_HIT} on stderr -- the shim did not intercept "
                    f"{fault['module']}; markers seen: {res['markers']}")
                return out
            landed_proof = hits[0]

    out["injection_landed"] = landed_proof
    out["decision"] = res["decision"]
    out["reason"] = res["reason"][:180]
    out["log_rows"] = res["log_rows"]
    out["ambient_rows"] = ambient_rows
    out["stderr"] = res["stderr"][:240]
    outcome, trace = classify_outcome(
        res, ambient_rows=ambient_rows, ambient_stderr=ambient_stderr)

    # Issue #1685: a fail-open under an active opt-out is the documented
    # behaviour of a supported feature. Relabel it, keep the raw classification
    # so nothing is hidden, and state the limit -- under a file bypass a
    # GENUINE fail-open here is indistinguishable from the opt-out, and an
    # honest "cannot distinguish" beats a confident wrong label.
    if bypassed and outcome in (SILENT, LOUD):
        out["raw_outcome"] = outcome
        trace = (f"allowed while a repo opt-out (.claude/.bypass) was active "
                 f"for this scenario; on the trace evidence alone it would "
                 f"read {outcome} -- {trace}. A genuine fail-open is NOT "
                 f"distinguishable here: re-run with the bypass removed.")
        outcome = NOT_ENFORCED_OUTCOME
    out["outcome"], out["trace"] = outcome, trace
    return out


def classify_outcome(res: dict, *, ambient_rows: int,
                     ambient_stderr: str) -> tuple:
    """Sort one faulted run into REFUSES / LOUD / SILENT.

    Extracted from :func:`run_fault` so :func:`verify_classifier` can drive
    all three branches directly. Collapsing these three is the failure this
    whole arm exists to fix, so the classifier itself must be watched
    emitting each label -- a branch that has never been observed firing is
    indistinguishable from a branch that cannot fire.

    Args:
        res: A :func:`drive_raw` result.
        ambient_rows: Log rows an ORDINARY permitted call writes through this
            hook. Subtracted, because a bare activity row is bookkeeping, not
            a warning.
        ambient_stderr: stderr an ordinary permitted call produces.

    Returns:
        ``(outcome, trace)``.
    """
    if res["decision"] in BLOCKED:
        return REFUSES, f"denied; {res['log_rows']} log row(s)"

    # It allowed. Loud only if it left MORE than an ordinary permitted call.
    extra_stderr = bool(res["stderr"]) and res["stderr"] != ambient_stderr
    extra_rows = res["log_rows"] - ambient_rows
    if extra_stderr or extra_rows > 0:
        parts = []
        if extra_stderr:
            parts.append(f"stderr: {res['stderr'].splitlines()[0][:90]}")
        if extra_rows > 0:
            parts.append(f"{extra_rows} log row(s) beyond the ambient "
                         f"{ambient_rows} an ordinary allow writes")
        return LOUD, "; ".join(parts)
    return SILENT, (
        f"none -- {res['log_rows']} log row(s) vs {ambient_rows} ambient, "
        "no stderr; indistinguishable from an ordinary permitted call")


# Synthetic single-file hooks used ONLY to exercise the classifier. They are
# not guards and never touch the real hook stack; each emits one known shape.
_STUB = (
    'import json, sys\n'
    'sys.stdin.read()\n'
    '{extra}'
    'print(json.dumps({{"hookSpecificOutput": {{'
    '"hookEventName": "PreToolUse", "permissionDecision": "{decision}", '
    '"permissionDecisionReason": "synthetic classifier control"}}}}))\n'
)

CLASSIFIER_CASES = [
    ("refuses", REFUSES, "deny", ""),
    ("loud", LOUD, "allow",
     'sys.stderr.write("[stub] allowing because a dependency broke\\n")\n'),
    ("silent", SILENT, "allow", ""),
]


def verify_classifier() -> dict:
    """Prove the three-way classifier can actually emit all three labels.

    Every real fault below lands on REFUSES or SILENT. That leaves LOUD
    unobserved, and an unobserved branch is not evidence of a working branch
    -- if a typo collapsed LOUD into SILENT, every result would still look
    plausible. Three synthetic stub hooks (deny / allow+stderr / allow+
    nothing) are driven through the same :func:`drive_raw` and
    :func:`classify_outcome` path used for the real guards, and each must
    produce its expected label.

    Returns:
        dict with ``ok`` and a per-case record.
    """
    out = {"cases": []}
    with tempfile.TemporaryDirectory(prefix="pob-classifier-") as d:
        root = Path(d)
        for name, expected, decision, extra in CLASSIFIER_CASES:
            stub = root / f"stub_{name}.py"
            stub.write_text(_STUB.format(decision=decision, extra=extra))
            res = drive_raw(stub, "Write", {"file_path": "x"}, root)
            got, trace = classify_outcome(res, ambient_rows=0,
                                          ambient_stderr="")
            out["cases"].append({
                "case": name, "expected": expected, "got": got,
                "ok": got == expected, "trace": trace,
            })
    out["ok"] = all(c["ok"] for c in out["cases"])
    return out


def _first_real_repo_guard() -> dict:
    """The guard :func:`verify_injection_instrument` drives, selected BY FIXTURE.

    This was ``GUARDS[0]``, which was safe for one accidental reason:
    ``GUARDS[0]``'s fixture happens to be :func:`_real_repo`, which ignores the
    root it is handed. Reordering ``GUARDS`` -- an ordinary maintenance edit --
    would have handed the real repository to a temp-dir fixture. Selecting by
    fixture identity removes the positional coupling rather than documenting it.

    Returns:
        The first guard whose fixture is :func:`_real_repo`.

    Raises:
        RuntimeError: If no guard uses it. Caught in :func:`main` and reported
            as EXIT_UNRESOLVABLE, because a harness that cannot verify its own
            instrument has not run -- it has not found anything.
    """
    for guard in GUARDS:
        if guard["fixture"] is _real_repo:
            return guard
    raise RuntimeError(
        "no guard uses the _real_repo fixture\n"
        "Expected at least one, because the injection instrument must be "
        "verified against a scenario that exercises the canonical source.\n"
        "See GUARDS in this file."
    )


def verify_injection_instrument() -> dict:
    """Prove the injection mechanism before trusting a single fault result.

    Runs a matched pair against the same real scenario:

      positive control - shim aimed at ``tool_intent``, which the hook DOES
        path-load. Must emit FAULT_HIT.
      negative control - shim aimed at a module nothing imports. Must emit
        SHIM_INSTALLED, must NOT emit FAULT_HIT, and must reproduce the
        unfaulted decision byte-for-byte.

    Without the negative control a shim that fired on everything would look
    identical to one that worked. Without the positive control a shim that
    never landed would make every fault case pass vacuously.

    The loud-vs-silent TRACE probe gets the same treatment, because a probe
    that cannot see a trace would report every fault as SILENT and a probe
    that counts other writers would report every fault as LOUD:

      trace positive - a run known to deny (and therefore to log) must make
        the attributable row count go UP.
      trace negative - the same count taken twice with NO hook run in between
        must not move, proving concurrent writers to the real repo's
        ``.claude/logs/`` are excluded by the session tag.

    Returns:
        dict with ``ok`` plus the observed evidence for each control.
    """
    hook = HOOKS / "unified_pre_tool.py"
    spec = _first_real_repo_guard()       # protected-infra floor, deny expected
    pos = spec["positive"]
    root = spec["fixture"](REPO)
    out = {"scenario": f"{spec['guard']} / {pos['tool_name']}"}

    # --- trace probe negative control: no hook run, count must not move ---
    quiet_before = _log_rows(root)
    subprocess.run([sys.executable, "-c", "pass"], capture_output=True,
                   cwd=str(root), timeout=60)
    quiet_after = _log_rows(root)

    baseline = drive_raw(hook, pos["tool_name"], pos["tool_input"](root), root)
    out["baseline_decision"] = baseline["decision"]

    out["trace_probe"] = {
        "positive": {
            "aimed_at": "a run that denies (must log an attributable row)",
            "observed": f"{baseline['log_rows']} row(s) tagged "
                        f"{SESSION_TAG!r}",
            "ok": baseline["log_rows"] > 0,
        },
        "negative": {
            "aimed_at": "the same count with no hook run in between",
            "observed": f"{quiet_before} -> {quiet_after}",
            "ok": quiet_before == quiet_after,
        },
    }

    with tempfile.TemporaryDirectory(prefix="pob-instr-") as d:
        stage = Path(d)
        ov = _write_shim(FAULT_TOOL_INTENT_IMPORT, stage / "pos")
        got = drive_raw(hook, pos["tool_name"], pos["tool_input"](root), root,
                        env_overrides=ov)
        hits = [m for m in got["markers"] if m.startswith(MARK_HIT)]
        out["positive_control"] = {
            "aimed_at": "tool_intent (hook path-loads it)",
            "markers": got["markers"],
            "ok": bool(hits),
            "detail": "FAULT_HIT observed" if hits else
                      "NO FAULT_HIT -- shim never intercepted; every fault "
                      "result below would be vacuous",
        }

        inert = dict(FAULT_TOOL_INTENT_IMPORT, module=INERT_MODULE,
                     id=f"import_raises:{INERT_MODULE}")
        ov = _write_shim(inert, stage / "neg")
        got = drive_raw(hook, pos["tool_name"], pos["tool_input"](root), root,
                        env_overrides=ov)
        installed = [m for m in got["markers"] if m.startswith(MARK_INSTALLED)]
        hits = [m for m in got["markers"] if m.startswith(MARK_HIT)]
        same = got["decision"] == baseline["decision"]
        out["negative_control"] = {
            "aimed_at": f"{INERT_MODULE} (nothing imports it)",
            "markers": got["markers"],
            "decision": got["decision"],
            "ok": bool(installed) and not hits and same,
            "detail": (
                "shim installed, never fired, decision unchanged"
                if (installed and not hits and same) else
                f"installed={bool(installed)} spurious_hits={hits} "
                f"decision={got['decision']!r} vs baseline "
                f"{baseline['decision']!r} -- the instrument contaminates "
                "results and no fault outcome below can be trusted"),
        }

    out["classifier"] = verify_classifier()
    out["ok"] = (out["positive_control"]["ok"]
                 and out["negative_control"]["ok"]
                 and out["trace_probe"]["positive"]["ok"]
                 and out["trace_probe"]["negative"]["ok"]
                 and out["classifier"]["ok"])
    return out


def run_guard(spec: dict, *, with_fault: bool = True) -> dict:
    hook = HOOKS / spec["hook"]
    out = {"guard": spec["guard"], "issue": spec["issue"], "hook": spec["hook"]}

    if not hook.exists():
        out["verdict"] = "UNVERIFIED"
        out["detail"] = f"hook missing: {hook}"
        return out

    with tempfile.TemporaryDirectory(prefix="pob-pos-") as d:
        root = spec["fixture"](Path(d))
        pos = spec["positive"]
        # Issue #1685: recorded per scenario, against the cwd the hook is
        # given -- not against the project root. Five guards run against temp
        # fixtures that no .bypass governs, and those stay fully measured even
        # in an opted-out repo.
        pos_bypassed = scenario_bypassed(root)
        dec, reason = drive(hook, pos["tool_name"], pos["tool_input"](root), root)
        out["positive"] = {"tool": pos["tool_name"], "decision": dec,
                           "reason": reason[:180], "why": pos["why"],
                           "ok": dec in BLOCKED, "bypassed": pos_bypassed}

    with tempfile.TemporaryDirectory(prefix="pob-neg-") as d:
        root = spec["fixture"](Path(d))
        neg = spec["negative"]
        dec, reason = drive(hook, neg["tool_name"], neg["tool_input"](root), root)
        out["negative"] = {"tool": neg["tool_name"], "decision": dec,
                           "reason": reason[:180], "why": neg["why"],
                           "ok": dec not in BLOCKED}

    # The verdict is decided by the happy-path pair ONLY. The fault arm is
    # additive by construction: it is computed after the verdict is fixed and
    # never feeds back into it. If adding a fault descriptor moves a verdict,
    # that is a bug in this harness, not a finding about the guard.
    if out["positive"]["ok"] and out["negative"]["ok"]:
        out["verdict"] = "PROVEN"
    elif not out["positive"]["ok"] and pos_bypassed:
        # Issue #1685: it allowed, but a repo opt-out told it to. That is the
        # design working. Reported -- never suppressed -- because a repo that
        # opted out still needs to see which guards are consequently inert.
        # Guards the #1435 hard floor exempts never reach here: they deny under
        # the bypass, so they are PROVEN above. No guard name is enumerated,
        # which is what keeps this a category rather than an allowlist.
        out["verdict"] = NOT_ENFORCED
        out["detail"] = (
            "allowed because a repo opt-out (.claude/.bypass) is active for "
            "this scenario; a genuine fail-open is not distinguishable from "
            "the opt-out here -- re-run with the bypass removed to measure it")
    elif not out["positive"]["ok"]:
        out["verdict"] = "FAILS-OPEN"      # the dangerous one
    else:
        out["verdict"] = "OVER-BLOCKS"     # also a regression

    if with_fault:
        out["fault"] = run_fault(spec, hook)
    return out


# --------------------------------------------------------------------------
# exit floor
# --------------------------------------------------------------------------

def compute_exit_code(results: list, instrument: Optional[dict]) -> int:
    """Decide the process exit code from the run's results.

    Extracted so the floor is testable. The floor is RUNTIME-ENUMERATED --
    ``proven == len(results)`` -- and must stay that way. A literal (e.g. "7")
    rots the moment ``GUARDS`` changes and would silently pass a run that lost
    a guard. ``test_compute_exit_code_three_guards_all_proven`` is the
    anti-substitution control: it exits 0 with only three guards, which a
    hardcoded 7 cannot do.

    Exit code polarity: the fault OUTCOMES never gate. Fail-open is often the
    right call, and the deliverable is the classification -- a guard that fails
    open silently is a FINDING for a human, not a build break. A broken
    INSTRUMENT does gate, because unverified injection makes every fault result
    vacuous, which is the exact defect that arm exists to find.

    Issue #1685: ``NOT-ENFORCED`` does not gate either. A repo that committed
    ``.claude/.bypass`` asked for those guards to be inert, and a permanently
    red check in every opted-out repo trains its readers to ignore this whole
    class of signal. The anti-vacuity floor below keeps that from becoming a
    free pass: a run in which NOTHING was proven is not a success, however it
    got there.

    Args:
        results: Per-guard result dicts from :func:`run_guard`.
        instrument: Instrument health dict, or None when ``--no-fault``.

    Returns:
        0 when every guard is PROVEN or NOT-ENFORCED, at least one is PROVEN,
        and the instrument is trustworthy; else 1.
    """
    # An empty result set is NOT a pass. `proven == len(results)` alone is
    # vacuously true for zero guards, which would report success for a run that
    # proved nothing -- a probe returning zero is not evidence of zero.
    if not results:
        return 1

    proven = sum(1 for r in results if r["verdict"] == "PROVEN")
    accounted = sum(1 for r in results
                    if r["verdict"] in ("PROVEN", NOT_ENFORCED))
    # The same anti-vacuity rule as the empty-results check above, now that a
    # verdict exists which is neither pass nor fail: an all-NOT-ENFORCED run
    # observed no guard refusing anything, and must not exit 0.
    ok = accounted == len(results) and proven > 0

    if instrument is not None:
        ok = ok and bool(instrument.get("ok"))
        unverified = sum(1 for r in results
                         if r.get("fault", {}).get("outcome")
                         == UNVERIFIED_INJECTION)
        ok = ok and unverified == 0

    return 0 if ok else 1


def silent_set(results: list) -> set:
    """Names of guards that fail open silently FOR REAL in ``results``.

    Issue #1685: a guard inert under a repo opt-out carries
    ``NOT ENFORCED (repo opt-out)`` rather than ``FAILS OPEN SILENTLY``, so it
    is excluded here by construction -- no name list, no second rule. This set
    is what feeds the ratchet, the FINDING line and the goal's abort threshold,
    all of which must count genuine breakage only.
    """
    return {r["guard"] for r in results
            if r.get("fault", {}).get("outcome") == SILENT}


def not_enforced_set(results: list) -> set:
    """Names of guards that are inert because the repo opted out (#1685).

    Reported ALONGSIDE :func:`silent_set`, never merged into it and never
    suppressed: a repo that opted out still needs to see which guards are
    consequently inert. A guard appears here if either arm says so -- the
    positive arm allowed under the opt-out, or the fault arm did.
    """
    return {r["guard"] for r in results
            if r.get("verdict") == NOT_ENFORCED
            or r.get("fault", {}).get("outcome") == NOT_ENFORCED_OUTCOME}


def compare_silent_set(current_results: list, baseline_path: Path) -> tuple:
    """Compare the current SILENT set against a recorded baseline.

    Membership is compared as a SET, never as a count: one guard going silent
    while another is fixed nets out to an unchanged count, which is exactly the
    regression this ratchet exists to catch.

    Args:
        current_results: Per-guard results from the current run.
        baseline_path: Path to a recorded ``proof-of-block.json``.

    Returns:
        ``(newly_silent, no_longer_silent)`` as sets of guard names.

    Raises:
        FileNotFoundError: If the baseline does not exist.
        ValueError: If the baseline is unusable -- unparseable, not a JSON
            object, ``results`` not an array, empty, carrying non-object
            entries, or carrying no fault data. The last case matters most: a
            baseline recorded with ``--no-fault`` has an empty SILENT set for
            the trivial reason that nothing was classified, so reporting "no
            new silent guards" from it would be a vacuous pass -- the precise
            failure mode this ratchet exists to prevent.

    Note:
        The shape checks below exist so that a MALFORMED INSTRUMENT is never
        reported as a GUARD FINDING. Only ``json.JSONDecodeError`` was caught
        originally; a baseline of ``5``, ``[]`` or ``{"results": [1, 2]}``
        raised AttributeError/TypeError straight past ``main()``'s
        ``except (FileNotFoundError, ValueError)`` and exited 1 -- the code that
        means "the harness ran and found a guard problem" -- sending an operator
        hunting for a broken guard that does not exist. Every case below raises
        ``ValueError`` in the established message shape so the existing handler
        catches it and the run exits ``EXIT_UNRESOLVABLE``.
    """
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"proof-of-block baseline not found: {baseline_path}\n"
            f"Expected a recorded artifact with fault data.\n"
            f"Record one with: proof_of_block.py --record --artifacts "
            f"{baseline_path.parent}"
        )

    try:
        baseline = json.loads(baseline_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"proof-of-block baseline is not valid JSON: {baseline_path}\n"
            f"Parse error: {exc}\n"
            f"Re-record it with: proof_of_block.py --record --artifacts "
            f"{baseline_path.parent}"
        ) from exc

    if not isinstance(baseline, dict):
        raise ValueError(
            f"proof-of-block baseline is not a JSON object: {baseline_path}\n"
            f"Expected a top-level object carrying a 'results' array; got "
            f"{type(baseline).__name__}.\n"
            f"Re-record it with: proof_of_block.py --record --artifacts "
            f"{baseline_path.parent}"
        )

    baseline_results = baseline.get("results") or []
    if not isinstance(baseline_results, list):
        raise ValueError(
            f"proof-of-block baseline 'results' is not an array: "
            f"{baseline_path}\n"
            f"Expected a list of per-guard result objects; got "
            f"{type(baseline_results).__name__}.\n"
            f"Re-record it with: proof_of_block.py --record"
        )
    if not baseline_results:
        raise ValueError(
            f"proof-of-block baseline has no results: {baseline_path}\n"
            f"Expected at least one recorded guard.\n"
            f"Re-record it with: proof_of_block.py --record"
        )

    malformed = [i for i, r in enumerate(baseline_results)
                 if not isinstance(r, dict)]
    if malformed:
        raise ValueError(
            f"proof-of-block baseline has non-object result entries: "
            f"{baseline_path}\n"
            f"Expected every entry in 'results' to be an object; indices "
            f"{malformed} are not.\n"
            f"Re-record it with: proof_of_block.py --record"
        )

    with_fault = [r for r in baseline_results if "fault" in r]
    if not with_fault:
        raise ValueError(
            f"proof-of-block baseline carries no fault data: {baseline_path}\n"
            f"Expected a 'fault' key on each of its {len(baseline_results)} "
            f"result(s); found 0. It was recorded with --no-fault, so its "
            f"SILENT set is empty for a trivial reason and comparing against "
            f"it would pass vacuously.\n"
            f"Re-record it WITHOUT --no-fault: proof_of_block.py --record"
        )

    base_silent = silent_set(baseline_results)
    cur_silent = silent_set(current_results)
    return cur_silent - base_silent, base_silent - cur_silent


def split_no_longer_silent(no_longer_silent: set, results: list) -> tuple:
    """Split "left the SILENT set" into RECOVERED and WENT UNMEASURED (#1685).

    Leaving the set has two causes that must not be reported as one. A guard
    that now denies under fault recovered; a guard that is inert because the
    repo opted out did not -- it stopped being measured. Re-recording a
    baseline on the second would pin an absence as a fix, which is how a
    ratchet quietly stops ratcheting.

    Extracted from :func:`main` so both arms are testable: a branch never
    watched firing is indistinguishable from one that cannot fire.

    Args:
        no_longer_silent: Guards in the baseline's SILENT set but not the
            current one.
        results: Current per-guard results.

    Returns:
        ``(went_unmeasured, recovered)`` as sets of guard names.
    """
    went_unmeasured = set(no_longer_silent) & not_enforced_set(results)
    return went_unmeasured, set(no_longer_silent) - went_unmeasured


def log_activity_row(repo: Path, results: list, exit_code: int) -> Optional[Path]:
    """Append one findable row to the activity sink (D4's machine reader).

    The sink carries 6,472-23,997 rows/day and its existing readers are
    pipeline-intent-shaped, so the row MUST carry a top-level
    ``"type": "proof_of_block"`` -- a row that is written but unfindable is the
    same defect as one never written. No existing row in that sink carries a
    ``type`` field, so this value selects exactly this harness's rows.

    Failure to write is swallowed deliberately: observability must never break
    the thing it observes. The path is returned so callers can report it.

    Args:
        repo: Project root.
        results: Per-guard results.
        exit_code: The exit code this run will return.

    Returns:
        The log file written, or None if the write failed.
    """
    # The fault arm may be off (--no-fault, which is what /health-check uses).
    # In that case the SILENT set is empty for a TRIVIAL reason -- nothing was
    # classified -- and emitting `"silent": []` would tell a reader "no guards
    # fail open silently", which is the vacuous-empty-set trap this harness
    # exists to detect. Emit null plus an explicit fault_arm flag instead, so
    # "not measured" and "measured, none found" are distinguishable.
    fault_arm = any("fault" in r for r in results)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "proof_of_block",
        "hook": "proof_of_block",
        "session_id": SESSION_TAG,
        "exit_code": exit_code,
        "proven": sum(1 for r in results if r["verdict"] == "PROVEN"),
        "total": len(results),
        "verdicts": {r["guard"]: r["verdict"] for r in results},
        "fault_arm": fault_arm,
        "silent": sorted(silent_set(results)) if fault_arm else None,
        # Issue #1685: kept as its own field so a machine reader counting
        # silent fail-opens against the goal's abort threshold never has to
        # subtract opted-out guards, and never accidentally includes them.
        "not_enforced": sorted(not_enforced_set(results)),
        "bypass": describe_bypass(repo)["form"],
    }
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = repo / ".claude" / "logs" / "activity" / f"{day}.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError as exc:
        sys.stderr.write(f"proof_of_block: could not log activity row: {exc}\n")
        return None
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true", help="write artifacts")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-fault", action="store_true",
                    help="skip the fault-injection arm (happy path only)")
    ap.add_argument("--artifacts", metavar="DIR", default=None,
                    help="directory --record writes to "
                         "(default: <project root>/.claude/proofs)")
    ap.add_argument("--baseline", metavar="PATH", default=None,
                    help="recorded artifact to ratchet the SILENT set against "
                         "(default: <artifacts>/proof-of-block.json)")
    ap.add_argument("--check-silent-regression", action="store_true",
                    help="exit 1 if any guard is newly SILENT vs --baseline")
    ap.add_argument("--log-activity", action="store_true",
                    help="append one 'type: proof_of_block' row to "
                         ".claude/logs/activity/ for the improvement loop")
    args = ap.parse_args()

    artifacts = resolve_artifacts_dir(REPO, args.artifacts)

    # Header: every run states which copy it resolved, BEFORE any verdict.
    # Committed is not deployed and deployed is not loaded -- a reader must be
    # able to tell which tree was actually exercised. The bypass line matters
    # because under a committed durable opt-out an ordinary guard legitimately
    # allows, and that must be distinguishable from breakage. Issue #1685: the
    # header is no longer the ONLY place that knows -- each verdict below
    # carries it too. The header said "present" for six weeks while the table
    # under it said FAILS-OPEN, and the table is what got quoted.
    bypass = describe_bypass(REPO)
    print("--- proof-of-block ---")
    print(f"  REPO      : {REPO}")
    print(f"  HOOKS     : {HOOKS}")
    print(f"  ARTIFACTS : {artifacts}")
    print(f"  bypass    : {bypass['form']}"
          + (f"   ({bypass['path']})" if bypass["active"] else ""))
    if bypass["active"]:
        print("              a committed .bypass is the SUPPORTED per-repo "
              "opt-out (CLAUDE.md); the #1435"
              if bypass["form"] == BYPASS_COMMITTED else
              "              an uncommitted .bypass is the EMERGENCY escape "
              "hatch (#1434), not a durable opt-out; the #1435")
        print("              protected-infrastructure hard floor still "
              "refuses under it")
    if bypass["warning"]:
        print(f"  WARNING   : {bypass['warning']}")
    env_note = env_bypass_note()
    if env_note:
        print(f"  note      : {env_note}")

    if args.check_silent_regression and args.no_fault:
        sys.stderr.write(
            "proof_of_block: --check-silent-regression requires the fault "
            "arm\nExpected: drop --no-fault. With no fault data the current "
            "SILENT set is empty for a trivial reason and the ratchet would "
            "pass vacuously.\n"
        )
        return EXIT_UNRESOLVABLE

    instrument = None
    if not args.no_fault:
        try:
            instrument = verify_injection_instrument()
        except RuntimeError as exc:
            # Instrument-broken is NOT a guard finding. Exit 2, not 1.
            sys.stderr.write(f"\nproof_of_block: {exc}\n")
            return EXIT_UNRESOLVABLE

    results = [run_guard(g, with_fault=not args.no_fault) for g in GUARDS]

    if args.json:
        print(json.dumps({"instrument": instrument, "results": results},
                         indent=2))
    else:
        for r in results:
            v = r["verdict"]
            print(f"\n{r['guard']}  ({r['issue']})   -> {v}")
            for side in ("positive", "negative"):
                if side not in r:
                    print(f"  {r.get('detail','')}")
                    continue
                s = r[side]
                # Issue #1685: an allow that the repo ASKED for is not a FAIL.
                # Labelling it one is how a correct result got quoted as a
                # finding in the first place.
                if s["ok"]:
                    flag = "ok "
                elif s.get("bypassed"):
                    flag = "opt"
                else:
                    flag = "FAIL"
                want = "must refuse" if side == "positive" else "must permit"
                print(f"  [{flag}] {side:<8} {want:<12} {s['tool']:<34} -> {s['decision']}")
                if not s["ok"]:
                    print(f"         why: {s['why']}")
                    print(f"         got: {s['reason'][:120]}")
                    # Printed against the arm it explains, not after the pair:
                    # a caveat that floats free gets attached to the wrong row.
                    if side == "positive" and v == NOT_ENFORCED:
                        print(f"         note: {r.get('detail', '')}")
            f = r.get("fault")
            if f:
                print(f"  [   ] fault    {f['fault']:<45} -> {f['outcome']}")
                if f["outcome"] == UNVERIFIED_INJECTION:
                    print(f"         {f.get('detail', '')}")
                else:
                    print(f"         landed: {f['injection_landed']}")
                    print(f"         trace:  {f.get('trace', '-')}")

    proven = sum(1 for r in results if r["verdict"] == "PROVEN")
    not_enforced = [r["guard"] for r in results
                    if r["verdict"] == NOT_ENFORCED]
    print(f"\n{proven}/{len(results)} guards PROVEN"
          f"   (PROVEN = watched refusing AND still permitting)")
    for r in results:
        if r["verdict"] != "PROVEN":
            print(f"  {r['verdict']}: {r['guard']}")
    if not_enforced:
        print(f"  {len(not_enforced)} guard(s) above are NOT-ENFORCED because "
              "this repo opted out (.claude/.bypass), not")
        print("  because they broke.")
        print("  A genuine fail-open in these is NOT distinguishable from the "
              "opt-out; to measure them,")
        print("  remove the bypass file and re-run. Every other guard above "
              "was measured normally.")

    if instrument is not None:
        instrument_ok = instrument["ok"]
        print("\n--- fault injection ---")
        print(f"instrument: {'OK' if instrument_ok else 'BROKEN'}"
              f"   (scenario: {instrument['scenario']})")
        for name in ("positive_control", "negative_control"):
            c = instrument[name]
            print(f"  [{'ok ' if c['ok'] else 'FAIL'}] {name:<17} "
                  f"{c['aimed_at']}")
            print(f"         {c['detail']}")
        for name in ("positive", "negative"):
            c = instrument["trace_probe"][name]
            print(f"  [{'ok ' if c['ok'] else 'FAIL'}] trace/{name:<11} "
                  f"{c['aimed_at']}")
            print(f"         observed: {c['observed']}")
        for c in instrument["classifier"]["cases"]:
            print(f"  [{'ok ' if c['ok'] else 'FAIL'}] "
                  f"classifier/{c['case']:<6} synthetic hook must classify as "
                  f"{c['expected']} -> {c['got']}")

        faults = [r["fault"] for r in results if r.get("fault")]
        width = max((len(x["fault"]) for x in faults), default=10)
        print(f"\n  {'guard':<34} {'fault injected':<{width}}  outcome")
        for r in results:
            f = r.get("fault")
            if not f:
                continue
            print(f"  {r['guard']:<34} {f['fault']:<{width}}  {f['outcome']}")

        # Issue #1685: the two counts are reported SEPARATELY and only the
        # first is a finding. Merging them inflates the silent count in every
        # opted-out repo -- and the goal's abort condition 3 reads this line.
        silent = sorted(silent_set(results))
        opted_out = sorted(
            r["guard"] for r in results
            if r.get("fault", {}).get("outcome") == NOT_ENFORCED_OUTCOME)
        print(f"\n  {len(silent)} silent fail-open(s), "
              f"{len(opted_out)} not enforced by repo opt-out")
        if silent:
            print(f"\n  FINDING -- {len(silent)} guard(s) fail open SILENTLY "
                  "under fault (the #1471 shape). Reported, not patched:")
            for g in silent:
                print(f"    {g}")
        if opted_out:
            print(f"\n  NOT A FINDING -- {len(opted_out)} guard(s) allowed "
                  "under this repo's opt-out (.claude/.bypass). Listed "
                  "because")
            print("  an opted-out repo still needs to see which guards are "
                  "inert -- but a genuine fail-open in")
            print("  these is indistinguishable from the opt-out, so they are "
                  "UNMEASURED, not clean:")
            for g in opted_out:
                print(f"    {g}")
        bad = [r["guard"] for r in results
               if r.get("fault", {}).get("outcome") == UNVERIFIED_INJECTION]
        if bad:
            print(f"\n  INJECTION-UNVERIFIED for: {', '.join(bad)}")

    if args.record:
        artifacts.mkdir(parents=True, exist_ok=True)
        sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        art = {"recorded": datetime.now(timezone.utc).isoformat(),
               "commit": sha, "instrument": instrument, "results": results}
        (artifacts / "proof-of-block.json").write_text(json.dumps(art, indent=2) + "\n")
        print(f"\nrecorded -> {artifacts / 'proof-of-block.json'} @ {sha}")

    exit_code = compute_exit_code(results, instrument)

    # D5: the exit code above gates on PROVEN count + instrument health only,
    # so it gives ZERO protection against a guard becoming newly SILENT. The
    # ratchet closes that, as a SET comparison against a recorded baseline.
    if args.check_silent_regression:
        baseline_path = (Path(args.baseline).expanduser().resolve()
                         if args.baseline
                         else artifacts / "proof-of-block.json")
        try:
            newly_silent, no_longer_silent = compare_silent_set(
                results, baseline_path)
        except (FileNotFoundError, ValueError) as exc:
            sys.stderr.write(f"\nproof_of_block: {exc}\n")
            return EXIT_UNRESOLVABLE

        print(f"\n--- silent-set ratchet (baseline: {baseline_path}) ---")
        print(f"  newly SILENT     : {sorted(newly_silent) or '(none)'}")
        print(f"  no longer SILENT : {sorted(no_longer_silent) or '(none)'}")
        # Issue #1685: leaving the SILENT set has two very different causes.
        # A guard that went UNMEASURED because this repo opted out has not
        # recovered, and re-recording a baseline on that basis would pin an
        # absence as a fix.
        went_unmeasured, recovered = split_no_longer_silent(
            no_longer_silent, results)
        if went_unmeasured:
            print("  NOT recovered -- these left the SILENT set only because "
                  "this repo opted out (.claude/.bypass);")
            print("  they are UNMEASURED here. Do NOT re-record the baseline "
                  "from this repo:")
            for g in sorted(went_unmeasured):
                print(f"    {g}")
        if recovered:
            print("  a guard recovered -- re-record the baseline in this same "
                  "PR so the pin ratchets down:")
            print(f"    proof_of_block.py --record --artifacts "
                  f"{baseline_path.parent}")
        if newly_silent:
            print("  FAIL -- these guards began failing open SILENTLY since "
                  "the baseline:")
            for g in sorted(newly_silent):
                print(f"    {g}")
            exit_code = 1

    if args.log_activity:
        written = log_activity_row(REPO, results, exit_code)
        if written is not None:
            print(f"\nactivity row -> {written}  (type: proof_of_block)")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
