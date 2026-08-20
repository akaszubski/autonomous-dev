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

USAGE
-----
    python3 proof_of_block.py            # replay, exit 1 on any failure
    python3 proof_of_block.py --record   # write artifacts
    python3 proof_of_block.py --json
    python3 proof_of_block.py --no-fault # happy-path arms only
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "plugins" / "autonomous-dev" / "hooks"
ARTIFACTS = REPO / "tests" / "proofs"

BLOCKED = {"deny", "block", "ask"}


# --------------------------------------------------------------------------
# scenario fixtures
# --------------------------------------------------------------------------

def _adev_repo(root: Path) -> Path:
    """A directory that repo_detector recognises as autonomous-dev.

    Requires BOTH a .git directory AND a marketplace.json whose CONTENT
    contains the string "autonomous-dev". Learned the hard way: an empty
    ``{}`` passes the exists() check, fails the content check, and silently
    reproduces nothing -- a fixture that cannot observe the behaviour it names.
    """
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

    This is safe: PreToolUse only RETURNS a decision. The hook never performs
    the tool call, so pointing at real protected paths mutates nothing. Both
    scenarios below are decision-only.

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
               "gate switches on; its corruption branch unlinks the marker and "
               "returns None",
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


def drive_raw(hook: Path, tool_name: str, tool_input: dict, cwd: Path,
              *, env_overrides: Optional[dict] = None) -> dict:
    """Run the hook the way Claude Code does, keeping stderr and log deltas.

    Args:
        hook: Path to the hook script.
        tool_name: PreToolUse tool name.
        tool_input: PreToolUse tool input.
        cwd: Working directory for the subprocess (also CLAUDE_PROJECT_DIR).
        env_overrides: Extra environment entries (used to install the shim).

    Returns:
        dict with ``decision``, ``reason``, ``stderr`` (shim markers removed),
        ``markers`` (the shim lines), and ``log_growth`` in bytes.
    """
    payload = {
        "session_id": "proof-of-block",
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
    env.update(env_overrides or {})

    before = _log_rows(cwd)
    p = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=120,
                       cwd=str(cwd), env=env)
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
            target = root / fault["path"]
            if target.exists():
                out["outcome"] = UNVERIFIED_INJECTION
                out["detail"] = (
                    f"{fault['path']} still present after the run -- the "
                    "corrupt-marker branch (which unlinks it) never ran, so "
                    "the fault was not reached")
                return out
            landed_proof = f"{fault['path']} consumed (unlinked) by the hook"
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
    out["outcome"], out["trace"] = classify_outcome(
        res, ambient_rows=ambient_rows, ambient_stderr=ambient_stderr)
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
    spec = GUARDS[0]                      # protected-infra floor, deny expected
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
        dec, reason = drive(hook, pos["tool_name"], pos["tool_input"](root), root)
        out["positive"] = {"tool": pos["tool_name"], "decision": dec,
                           "reason": reason[:180], "why": pos["why"],
                           "ok": dec in BLOCKED}

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
    elif not out["positive"]["ok"]:
        out["verdict"] = "FAILS-OPEN"      # the dangerous one
    else:
        out["verdict"] = "OVER-BLOCKS"     # also a regression

    if with_fault:
        out["fault"] = run_fault(spec, hook)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true", help="write artifacts")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-fault", action="store_true",
                    help="skip the fault-injection arm (happy path only)")
    args = ap.parse_args()

    instrument = None
    if not args.no_fault:
        instrument = verify_injection_instrument()

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
                flag = "ok " if s["ok"] else "FAIL"
                want = "must refuse" if side == "positive" else "must permit"
                print(f"  [{flag}] {side:<8} {want:<12} {s['tool']:<34} -> {s['decision']}")
                if not s["ok"]:
                    print(f"         why: {s['why']}")
                    print(f"         got: {s['reason'][:120]}")
            f = r.get("fault")
            if f:
                print(f"  [   ] fault    {f['fault']:<45} -> {f['outcome']}")
                if f["outcome"] == UNVERIFIED_INJECTION:
                    print(f"         {f.get('detail', '')}")
                else:
                    print(f"         landed: {f['injection_landed']}")
                    print(f"         trace:  {f.get('trace', '-')}")

    proven = sum(1 for r in results if r["verdict"] == "PROVEN")
    print(f"\n{proven}/{len(results)} guards PROVEN"
          f"   (PROVEN = watched refusing AND still permitting)")
    for r in results:
        if r["verdict"] != "PROVEN":
            print(f"  {r['verdict']}: {r['guard']}")

    instrument_ok = True
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

        silent = [r["guard"] for r in results
                  if r.get("fault", {}).get("outcome") == SILENT]
        if silent:
            print(f"\n  FINDING -- {len(silent)} guard(s) fail open SILENTLY "
                  "under fault (the #1471 shape). Reported, not patched:")
            for g in silent:
                print(f"    {g}")
        bad = [r["guard"] for r in results
               if r.get("fault", {}).get("outcome") == UNVERIFIED_INJECTION]
        if bad:
            print(f"\n  INJECTION-UNVERIFIED for: {', '.join(bad)}")

    if args.record:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        art = {"recorded": datetime.now(timezone.utc).isoformat(),
               "commit": sha, "instrument": instrument, "results": results}
        (ARTIFACTS / "proof-of-block.json").write_text(json.dumps(art, indent=2) + "\n")
        print(f"\nrecorded -> {ARTIFACTS / 'proof-of-block.json'} @ {sha}")

    # Exit code polarity: the fault OUTCOMES never gate. Fail-open is often
    # the right call, and the deliverable is the classification -- a guard
    # that fails open silently is a FINDING for a human, not a build break.
    # A broken INSTRUMENT does gate, because unverified injection makes every
    # fault result vacuous, which is the exact defect this arm exists to find.
    ok = proven == len(results) and instrument_ok
    if instrument is not None:
        unverified = sum(1 for r in results
                         if r.get("fault", {}).get("outcome")
                         == UNVERIFIED_INJECTION)
        ok = ok and unverified == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
