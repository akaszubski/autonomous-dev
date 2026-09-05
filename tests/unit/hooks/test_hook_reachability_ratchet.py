#!/usr/bin/env python3
"""Ratchet: a hook that can refuse must be REACHABLE. Issue #1612.

The blind spot this exists to close
-----------------------------------
A hook that is never invoked and a hook that is invoked but never needed
produce the SAME observable: zero rows in ``.claude/logs/hook-blocks.jsonl``.
Nothing in this repository distinguished them, so "never blocked" was read as
"correctly never needed" for guards that could not fire at all.

This is the *never fires* state named in
``docs/audits/unified-pre-tool-51-check-audit.md``, the first of three states
in which only the third is enforcement:

1. Never fires — unreachable, or flag-off
2. Fires and returns nothing that acts
3. Fires and refuses

Registering the currently-unreachable hooks would fix the INSTANCE. The next
gate added without a registration would be equally invisible. So this module
makes the CONDITION detectable instead: for every hook in the corpus it derives
two facts independently and cross-references them.

Why a block-row COUNT is the wrong instrument — measured, not argued
--------------------------------------------------------------------
``enforce_orchestrator.py`` carries 280 rows in the block log, which reads as a
live, firing gate. It is registered on no lifecycle event and nothing in the
repo invokes it. Running ``tests/unit/hooks/test_enforce_orchestrator.py`` took
the count 280 -> 281: every one of those rows is its own unit suite exercising
``main()``. A gate's block count can be manufactured entirely by the tests that
cover it, which is precisely why reachability has to be derived from
registration rather than from telemetry. It is also why ``tests/`` is excluded
from the invoker corpus below (see ``_invoker_corpus``) — counting a test
import as reachability would re-import this exact error into the guard.

The two derived facts
---------------------
1. **Refusal evidence.** Taken from the #1588 ratchet's instruments by IMPORT —
   ``_iter_hook_files``, ``_python_refusal_evidence``, ``_shell_refusal_evidence``
   — never reimplemented. A second copy of the classifier drifts from the first,
   and this repo has that defect class on record (``_strip_body_arg_values``:
   2 callers against 17 reimplementations). ``test_refusal_instruments_are_
   imported_not_reimplemented`` enforces the no-copy rule structurally.
2. **Lifecycle registration.** Derived by walking the registration surfaces and
   extracting the event under which a hook path appears. Only a subtree keyed by
   one of the eight ``LIFECYCLE_EVENTS`` counts.

A hook with refusal evidence and no reachability route fails, named, with its
evidence and the surfaces searched.

What is NOT a registration
--------------------------
``install_manifest.json`` ships a file. ``component_classifications.json`` is
metadata. Both MENTION the unreachable hooks, which is what made them look
"in the config" while nothing invoked them — treating either as a registration
is the mistake that let this run unnoticed. They are excluded by name in
``_registration_surfaces`` AND cannot qualify structurally, since neither
carries a lifecycle-event key; ``test_manifest_and_classifications_are_not_
registrations`` proves the structural rule alone suffices, with the mention
asserted as a premise so the control cannot pass vacuously.

The second route, and why it also needs a guard
-----------------------------------------------
The hook-metadata schema's ``type: "utility"`` means *"imported by other hooks,
not registered directly"*. That is a legitimate way to be reachable, and a
guard that accepted the DECLARATION alone could be satisfied by a one-line
sidecar edit — inheriting the defect it polices.

Commit ``51743c87`` is that edit. It reclassified three hooks as ``utility`` to
clear a red CI check (``generate_hook_config.py --check`` was correctly
reporting shipped hooks wired to nothing), justified by claims that
``enforce_prunable_threshold.py`` is "imported by ``lib/hook_safety.py``" and
``enforce_regression_test.py`` is "referenced by ``lib/bugfix_detector.py``".
Resolved by AST, both are false: ``hook_safety.py:6`` is a module docstring
line and ``bugfix_detector.py:4``/``:34`` are a docstring and a comment.
Nothing imports either hook; nothing calls either hook. A drift check that was
telling the truth was silenced by declaring the hooks to be something they are
not.

So a ``utility`` declaration confers reachability here only when an actual
importer or invoker resolves — ``ast.Import``/``ast.ImportFrom`` naming the
module, a string argument to an INVOCATION-shaped call naming the file, or a
shell line that EXECUTES it. Substring matching is specifically rejected: a
docstring mention is exactly what produced the false claim.

"Invocation-shaped" is load-bearing and was measured. An earlier rule accepted a
filename constant anywhere inside ANY ``ast.Call``, which drew the line at
Expr-versus-Call when the property that matters is MENTION-versus-INVOCATION.
Each of ``logging.info("gate.py is deprecated")``, ``print(...)``,
``raise ValueError(...)`` and ``add_argument(help=...)`` cleared a
``utility``-declared gate on one line of prose, and the live flagged set dropped
5 -> 4 against a ``lib/`` file whose entire content was an import of ``logging``
and one log call. The callee must now be one of ``INVOCATION_CALLEES``.

And the CHAIN has to terminate somewhere that runs. Two ``utility`` hooks that
invoke each other were both permitted while neither was reachable from any
lifecycle event — ``51743c87`` with two files instead of one sidecar. See
``_utility_route_is_grounded``, and item 4 of the CANNOT-detect list for where
that recursion stops.

The shell arm rejects MENTIONS, which is not the same as being narrow.
``scripts/test-autonomous-workflow.sh:86`` reads
``[ -f plugins/autonomous-dev/hooks/enforce_tdd.py ]`` — an existence check.
A loose "filename appears in a non-comment line" rule counted it as an invoker,
which is presence-as-proof, the same error one level down. So
``_shell_invocation_pattern`` requires an interpreter prefix or a path in
COMMAND position.

Its first cut was also too narrow, and in a way that is easy to mistake for
rigour: excluding ``(``, ``)`` and spaces from the path character class made
this repo's OWN template command —
``python3 "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/...py"`` —
invisible, along with ``"$PYTHON" path``, ``uv run path``, ``if path; then``,
``path --check`` and ``python3 -m stem``. Those misses fail SAFE (a missed
invoker under-reports reachability and produces a loud false red, never a silent
green), which is why the pattern was widened rather than replaced.
``_PATH_CHAR`` now matches ``${...}`` and ``$(...)`` as units and
``_COMMAND_POSITION`` names the positions at which a bare path is a command.
``source`` was DROPPED from the interpreter list in the same pass: the shell
reads a ``source``d file as shell, so ``source gate.py`` cannot run a Python
hook.

Corpus choices, and what each gives up
--------------------------------------
* **Hooks:** ``HOOKS_DIR`` from the #1588 ratchet — the TRACKED source tree, not
  the gitignored ``.claude/hooks/`` deploy artifact. Derived from disk, never
  hardcoded: a hardcoded hook list inherits the defect it polices.
* **Registration surfaces:** the TRACKED ones only (``templates/*.json``,
  ``config/*.json``). ``.claude/settings*.json`` and ``~/.claude/settings*.json``
  are untracked and machine-local; a guard that let them confer registration
  would be green locally and red in CI for the same commit. Measured across
  every ``settings*.json`` under ``.claude/`` and ``~/.claude/`` on the
  reporting machine: exactly two hooks are registered in a local surface but not
  in a tracked one — ``batch_permission_approver.py`` and
  ``mcp_security_enforcer.py`` — and NEITHER is present in ``HOOKS_DIR``, so
  neither is in the corpus this guard classifies and the exclusion costs it no
  coverage. That is the claim the code supports; the earlier wording here said
  "ZERO hooks", which is falsifiable and false, and
  ``test_no_corpus_hook_is_registered_only_in_a_local_surface`` now measures the
  conclusion rather than asserting it in prose. The residual risk fails safe — a
  registration added only to an untracked file leaves this guard red rather than
  falsely green.

What this guard CANNOT detect
-----------------------------
1. **Registration by a mechanism that is not a settings surface.** Git hooks,
   CI workflows and dispatchers that shell out are outside the enumerated
   globs. This under-reports reachability, so it can flag a reachable hook (a
   loud, correctable failure) but cannot pass an unreachable one.
2. **Registered but matcher-dead.** A hook registered under a ``matcher`` that
   can never match is registered as far as this guard is concerned. That is
   state 2 (fires and returns nothing that acts), a different defect.
3. **Dynamically constructed importers.** ``importlib.import_module(name)``
   where ``name`` is computed is invisible to the AST resolver.
4. **A dead LIBRARY still vouches — MEASURED since #1698, no longer merely
   documented.** ``_utility_route_is_grounded`` treats any importer outside
   ``HOOKS_DIR`` — a ``lib/`` or ``scripts/`` file — as grounded without asking
   whether THAT file is reached. The recursion stops at the edge of the hook
   corpus. Cycles WITHIN the corpus are refused (two ``utility`` hooks vouching
   for each other ground nothing), but a hook invoked only by an orphaned
   library function reads as reachable.

   #1698 adds the missing corpus: see the ``ISSUE #1698`` section below, which
   walks ``lib/`` transitively over all three invocation styles and pins the
   set for which no route resolves. The hook rule's grounding logic is
   deliberately UNCHANGED — that is #1612's, and rewriting it here would
   silently re-verdict five pinned hooks — but the condition it could not see
   is now visible, and ``test_limitation_four_is_measured_not_merely_
   documented`` cross-references the two corpora on every run, naming any
   ``utility`` hook whose only voucher is a library module that is itself
   UNKNOWN. That set is EMPTY today; the arm carries a positive control so its
   emptiness is a measurement rather than an inert probe.
5. It inherits every limitation of the #1588 refusal instruments, including
   their under-reporting of unnamed refusal forms.

Scope note, RESOLVED by #1639: ``validate_claude_md_size.py`` used to sit
exactly here — reclassified ``utility``, described as "(orphan, kept for size
enforcement)", an admission it was unreferenced, and carrying no refusal
evidence, so it read as an OBSERVER and fell outside this issue. It now refuses
through ``block_event_decorator`` and is registered on ``PostToolUse`` in every
shipped template, so this guard classifies it on the refuser route like any
other. It is retained as a worked example of the state this ratchet exists to
detect: a correct check that nothing invoked.
"""

import ast
import contextlib
import json
import re
import subprocess
import sys
import warnings
from pathlib import Path
from typing import NamedTuple

import pytest

# tests/unit/hooks/test_hook_reachability_ratchet.py
#   -> hooks -> unit -> tests -> repo root = parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# The #1588 instruments live beside this file. Inserted explicitly rather than
# relying on pytest's rootdir insertion, so the mutation harness below (which
# runs a copy of this module out of tree, with PYTHONPATH pointed back here)
# and a direct ``python3 <file>`` invocation both resolve the same module.
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from test_refusal_sink_ratchet import (  # noqa: E402  (path set up above)
    DECISION_KEYS,
    HOOKS_DIR,
    INSTRUMENTS,
    REFUSAL_DECISION_VALUES,
    REFUSAL_EMITTER_NAMES,
    _iter_hook_files,
    _python_refusal_evidence,
    _refusal_evidence,
    _SHELL_COMMENT,
    _shell_refusal_evidence,
    refusal_candidates,
)

# The eight lifecycle events a hook can be registered under. A JSON subtree is
# a registration only when it hangs off one of these keys.
LIFECYCLE_EVENTS = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "SessionStart",
        "Stop",
        "SubagentStop",
        "PreCompact",
        "Notification",
    }
)

# Tracked registration surfaces. See the module docstring for why the untracked
# local settings files are excluded and what that measurably costs (nothing).
REGISTRATION_SURFACE_GLOBS = (
    "plugins/autonomous-dev/templates/*.json",
    "plugins/autonomous-dev/config/*.json",
)

# Shipping a file is not invoking it; classifying a file is not invoking it.
#
# DEFENCE IN DEPTH, and labelled as such after measurement. Lifting this set
# entirely leaves the live flagged set BYTE-IDENTICAL, because the structural
# lifecycle-key rule in ``_events_in`` already refuses both files on its own —
# ``test_the_manifest_exclusion_is_defence_in_depth_not_the_refusal`` drives
# that measurement, and ``test_the_lifecycle_key_gate_is_what_refuses_the_
# manifest`` shows which rule IS load-bearing by removing it and watching 200+
# registrations leak out of the two metadata files.
NON_REGISTRATION_SURFACES = frozenset(
    {"install_manifest.json", "component_classifications.json"}
)

# Files that may legitimately import or invoke a ``utility`` hook. ``tests/`` is
# DELIBERATELY absent: enforce_orchestrator.py's 280 block rows are produced by
# its own unit suite (measured 280 -> 281 by running it), so a test import is
# evidence of coverage, not of reachability. ``hooks/archived/`` is absent for
# the same reason the #1588 corpus excludes it — retired hooks invoke nothing.
INVOKER_CORPUS_GLOBS = (
    "plugins/autonomous-dev/hooks/*.py",
    "plugins/autonomous-dev/hooks/*.sh",
    "plugins/autonomous-dev/lib/*.py",
    "scripts/*.py",
    "scripts/*.sh",
    "scripts/**/*.py",
    "scripts/**/*.sh",
    "scripts/hooks/*",
)

# The hook-metadata schema's category for "imported by other hooks, not
# registered directly".
UTILITY_TYPE = "utility"

# Why a refusing hook failed. Pinned so a new reason cannot appear incidentally
# and so each pin entry records WHICH condition it fails — a pin that says only
# "exempt" cannot tell you what changed when it is fixed.
UNREACHABILITY_REASONS = frozenset(
    {
        "no-lifecycle-registration",
        "utility-declared-without-importer",
        "no-utility-declaration",
    }
)

# A shell line that EXECUTES a file, as opposed to one that merely names it.
# Built per-filename by ``_shell_invocation_pattern``. The distinction is
# load-bearing: ``[ -f .../enforce_tdd.py ]`` is an existence check and counting
# it as an invoker is presence-as-proof.
#
# ``source`` was REMOVED from this list: ``source x.py`` is not meaningful
# Python execution — the shell would read the file as shell script — so
# accepting it as an invoker was accepting a shape that cannot run a hook.
_SHELL_INTERPRETERS = (
    "python3",
    "python",
    "bash",
    "sh",
    "zsh",
    "exec",
    "env",
    "uvx",
    r"uv\s+run",
)

# One character of a path token, or a whole ``${...}`` / ``$(...)`` expansion.
# The expansions are matched as UNITS so that their parentheses and braces do
# not have to be excluded character-by-character. Excluding them was what made
# this repo's OWN template shape —
# ``python3 "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/..."`` —
# invisible to the invocation arm.
_PATH_CHAR = r"(?:\$\{[^}]*\}|\$\([^)]*\)|[^\s;|&()\"'])"

# Positions at which a bare path is a COMMAND rather than an argument. A path
# that appears anywhere else (``[ -f path ]``, ``echo path``, ``grep path``) is
# being named, not run.
_COMMAND_POSITION = r"(?:^|[;&|`]|\$\(|\b(?:then|else|elif|if|while|until|do)\b)"

# Hook filenames as they appear inside a settings command string.
_HOOK_FILENAME = re.compile(r"[\w.\-]+\.(?:py|sh)")

# Callees whose string arguments are things being RUN, not things being
# described. ``filename in some_constant`` inside ANY call was the #1612
# reviewer's BLOCKING-2 finding: ``logging.info("x.py is deprecated")``,
# ``print(...)``, ``raise ValueError(...)`` and ``add_argument(help=...)`` each
# cleared a ``utility``-declared gate on the strength of one line of prose.
INVOCATION_CALLEES = frozenset(
    {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "run_path",
        "execv",
        "execvp",
        "spawn",
        "system",
    }
)

# Callees that LOAD a module out of a file path — the ``importlib`` route. The
# whole set is one verb because it is the only one this repo uses; the count
# was MEASURED, not assumed (``grep -c spec_from_file_location`` over
# ``hooks/`` and ``lib/``).
#
# THE NAME ARGUMENT IS THE EDGE, NOT THE PATH ARGUMENT. By the ``importlib``
# contract the FIRST POSITIONAL argument is the module name, and in every live
# shape in this repo it is a string LITERAL. The path argument is not usable:
# the three shapes in ``hooks/unified_pre_tool.py`` DIFFER, and only one of
# them carries a ``.py`` literal at all —
#
#   :9249  spec_from_file_location("baseline_guardrail",
#                                  str(_bg_lib_dir / "baseline_guardrail.py"))
#   :8817  spec_from_file_location("prompt_quality_rules", str(_pq_mod_path))
#   :93    spec_from_file_location("python_write_detector", str(_detector_path))
#
# — and even that one nests its literal inside a ``str()`` Call, which
# ``_argument_constants`` deliberately STOPS at (see its docstring: that
# stop-at-nested-call rule is #1612's BLOCKING-2 protection and must not be
# widened, or a ``.py`` filename inside ``print()`` or ``raise`` grounds a
# module again). The other two carry no literal path whatsoever. What all
# three share is the name.
MODULE_LOADER_CALLEES = frozenset({"spec_from_file_location"})

# Every hook below fails BOTH available routes: no lifecycle registration, and a
# ``utility`` declaration with no importer or invoker anywhere in the corpus.
_UNREGISTERED_UTILITY = frozenset(
    {"no-lifecycle-registration", "utility-declared-without-importer"}
)

# Hooks known to be able to refuse while being reachable by nothing. This
# mapping may only SHRINK, and each value records WHICH conditions the entry
# fails, so a partial fix (registering it, or giving it a real importer) trips
# the staleness arm instead of sitting silently under a blanket exemption.
#
# Adding an entry is NOT an acceptable resolution for a guard failure: register
# the hook on the lifecycle event it is meant to gate, give it a real importer,
# or delete it. Whether each of these four should be registered or deleted is
# the policy half of #1612 and is deliberately NOT decided here.
#
# RESOLVED and REMOVED — ``PreToolUseWrite-protect-sensitive.sh``. It was pinned
# here because it emitted a refusal through its own fusing ``deny_and_record``
# shell function while nothing in the repo invoked it, exactly the state this
# ratchet exists to make visible. #1588 wired it up: its sidecar now declares
# ``type: "lifecycle"`` with a ``PreToolUse`` registration, and every settings
# surface that registers ``unified_pre_tool.py`` registers it too. The ratchet
# advanced by five to four; ``REACHABILITY_CEILING`` and
# ``CEILING_HIGH_WATER_MARK`` were lowered in the same diff.
#
#  * enforce_orchestrator.py — refuses via ``sys.exit(2)`` (line 320). It has
#    280 block rows, every one of them manufactured by its own unit suite; see
#    the module docstring. NOT among the four hooks named in #1612's body: the
#    issue selected on zero-block-rows, and this one's non-zero count concealed
#    it. That the count is the wrong instrument is the finding, not an aside.
#  * enforce_prunable_threshold.py — ``return 2`` (line 157). Sidecar claims
#    ``utility``; the claimed importer ``lib/hook_safety.py`` mentions it in a
#    module docstring only.
#  * enforce_regression_test.py — ``return 2`` (line 183). Sidecar claims
#    ``utility``; the claimed importer ``lib/bugfix_detector.py`` mentions it in
#    a docstring and a comment only.
#  * enforce_tdd.py — ``return 2  # Block commit`` (line 458). Its only corpus
#    mention is ``scripts/test-autonomous-workflow.sh:86``, an ``[ -f ... ]``
#    existence check.
PINNED_UNREACHABLE: "dict[str, frozenset[str]]" = {
    "enforce_orchestrator.py": _UNREGISTERED_UTILITY,
    "enforce_prunable_threshold.py": _UNREGISTERED_UTILITY,
    "enforce_regression_test.py": _UNREGISTERED_UTILITY,
    "enforce_tdd.py": _UNREGISTERED_UTILITY,
}

# Ceiling on the pin. An escape hatch without a ceiling on itself is decorative:
# the next hook that fails gets added to the list instead of wired up.
#
# LOWERING needs no justification and is never blocked; that is the ratchet
# advancing as #1612's other half resolves each hook. Lower
# ``CEILING_HIGH_WATER_MARK`` in the SAME diff. RAISING is honest in exactly one
# case: a NEW ROUTE or a NEW INSTRUMENT made PRE-EXISTING unreachable hooks
# visible, in which case say which, in the same diff.
REACHABILITY_CEILING = 4

# The highest ceiling ever REVIEWED. Its only job is to make a RAISE cost a
# second, visible constant edit — tying the ceiling only to
# ``len(PINNED_UNREACHABLE)`` makes both operands constants in this file, so an
# edit that adds an entry AND bumps the ceiling moves them together and nothing
# fires.
#
# It is a NAMED constant rather than a literal inside the assertion because the
# literal was unreadable to the mutation harness, which had to hardcode ``5`` to
# match it. Naming it lets every arm of ``TestCeilingIsNotATautology`` derive
# its mutation from it and keep working as the ratchet advances.
#
# KNOWN, BOUNDED RESIDUAL — stated rather than hidden. This is an upper bound,
# not a lockstep. Lowering ``REACHABILITY_CEILING`` without lowering this
# constant leaves exactly ``CEILING_HIGH_WATER_MARK - REACHABILITY_CEILING``
# units of headroom in which the pin could grow back with every assertion green.
# LOWER THIS IN THE SAME DIFF as the ceiling and the residual is zero. It is an
# upper bound rather than an equality on purpose: an equality would turn the
# sanctioned edit — wiring a hook up and lowering the pin — red until a third
# constant was also touched, and pressure on the correct action is the failure
# mode this whole class exists to prevent.
CEILING_HIGH_WATER_MARK = 4


#: Prefix of the single line that opens the ``PINNED_UNREACHABLE`` literal. Used
#: as a mutation anchor that exists whether the pin is populated or empty, so
#: the harness below does not have to be re-anchored as the ratchet advances.
_PIN_DECLARATION_PREFIX = "PINNED_UNREACHABLE: "


def _ceiling_anchor(ceiling: int) -> str:
    """Build the mutation anchor for ``REACHABILITY_CEILING``.

    Derived from the constant rather than hardcoded. A hardcoded ``= 5``
    anchor stops resolving the moment the ratchet advances, which turns the
    correct maintenance action — lowering the pin and the ceiling together —
    into three red tests demanding a re-anchor. That is pressure to leave
    hooks pinned, which is the failure this whole module exists to prevent,
    one level up.

    Args:
        ceiling: The ceiling value the anchor should match.

    Returns:
        The exact source text of the ceiling assignment line.
    """
    return f"\nREACHABILITY_CEILING = {ceiling}\n"


def _high_water_anchor(mark: int) -> str:
    """Build the mutation anchor for ``CEILING_HIGH_WATER_MARK``.

    Args:
        mark: The high-water value the anchor should match.

    Returns:
        The exact source text of the high-water assignment line.
    """
    return f"\nCEILING_HIGH_WATER_MARK = {mark}\n"


def _unique_line(source: str, prefix: str, description: str) -> str:
    """Return the single line of ``source`` beginning with ``prefix``.

    Args:
        source: Module source text.
        prefix: Line prefix to search for.
        description: What the caller is anchoring on, for the failure message.

    Returns:
        The matching line, newline included.

    Raises:
        AssertionError: When the prefix matches zero or several lines. A
            harness that mutates nothing reports a green that means nothing.
    """
    lines = [ln for ln in source.splitlines(keepends=True) if ln.startswith(prefix)]
    assert len(lines) == 1, (
        f"{description}: {len(lines)} line(s) in this module start with "
        f"{prefix!r}, expected exactly one. The mutation harness would mutate "
        f"nothing (or the wrong site) and report a green that means nothing."
    )
    return lines[0]


def _pin_add_mutation(
    source: str, pinned: "dict[str, frozenset[str]]", count: int
) -> "tuple[str, str]":
    """Build the ``(anchor, replacement)`` that ADDS ``count`` entries to the pin.

    Anchored on the declaration line rather than on any particular member, so
    it resolves for a populated pin AND for an empty one — the state #1612's
    other half is working towards.

    Args:
        source: Module source text to mutate.
        pinned: The pin as it currently stands, read for its emptiness only.
        count: How many synthetic entries to add.

    Returns:
        Anchor text and its replacement.

    Raises:
        AssertionError: When ``count`` is not positive — a zero-entry "growth"
            mutation is a no-op that would read as a green refusing arm.
    """
    assert count > 0, (
        f"a growth mutation of {count} entries adds nothing. The refusing arm "
        f"would run against an unmutated copy and pass for the wrong reason."
    )
    declaration = _unique_line(source, _PIN_DECLARATION_PREFIX, "pin declaration")
    entries = "".join(
        f'    "synthetic_growth_offender_{i}.py": _UNREGISTERED_UTILITY,\n'
        for i in range(count)
    )
    if not pinned:
        # ``... = {}`` — the whole literal has to be reopened.
        return declaration, declaration.replace("{}", "{\n" + entries + "}")
    return declaration, declaration + entries


def _pin_drop_mutation(
    source: str, pinned: "dict[str, frozenset[str]]"
) -> "tuple[str, str]":
    """Build the ``(anchor, replacement)`` that REMOVES one entry from the pin.

    Args:
        source: Module source text to mutate.
        pinned: The pin as it currently stands; its last member is dropped.

    Returns:
        Anchor text and its replacement (the empty string).

    Raises:
        AssertionError: If the pin is empty, or its last member's line cannot
            be located uniquely.
    """
    assert pinned, "premise: there is an entry to drop"
    name = sorted(pinned)[-1]
    line = _unique_line(source, f'    "{name}":', f"pin entry for {name}")
    return line, ""


def _registration_surfaces(project_root: Path = PROJECT_ROOT) -> "list[Path]":
    """Enumerate the JSON files that can carry a lifecycle registration.

    Args:
        project_root: Repository root to resolve ``REGISTRATION_SURFACE_GLOBS``
            against.

    Returns:
        Sorted, de-duplicated surface paths, excluding the manifest and the
        classification metadata.

    Raises:
        RuntimeError: If the enumeration is empty. A zero-surface search makes
            every "not registered" verdict trivially true and every permitting
            assertion vacuous, so it is a hard error rather than a pass.
    """
    found: "set[Path]" = set()
    for pattern in REGISTRATION_SURFACE_GLOBS:
        for path in project_root.glob(pattern):
            if path.is_file() and path.name not in NON_REGISTRATION_SURFACES:
                found.add(path)
    if not found:
        raise RuntimeError(
            f"Zero registration surfaces found under {project_root} for globs "
            f"{list(REGISTRATION_SURFACE_GLOBS)}.\n"
            f"Expected: at least one settings template carrying a lifecycle "
            f"event key. An empty search makes every hook read as unregistered "
            f"and every permitting assertion vacuous — the search is broken, "
            f"not the repo.\n"
            f"See: the module docstring of this file."
        )
    return sorted(found)


def _strip_shell_comments(text: str) -> str:
    """Remove ``#`` comments from every line of ``text``.

    Uses the #1588 module's ``_SHELL_COMMENT`` rather than a second copy of the
    same regex — the pattern is applied per line because that regex is
    deliberately not ``MULTILINE``.

    Args:
        text: Shell text, one or more lines.

    Returns:
        The same text with comments removed.
    """
    return "\n".join(_SHELL_COMMENT.sub("", line) for line in text.splitlines())


def _command_strings_under(node: object) -> "list[str]":
    """Collect the ``command`` of every ``{"type": "command", ...}`` entry.

    ONLY a self-declared command entry can invoke anything. Every other string
    beneath a lifecycle-event key is a ``matcher`` glob, a ``_comment``, a
    timeout or free prose — and collecting those was the #1612 reviewer's
    BLOCKING-1 finding: a one-line JSON note reading
    ``{"_note": "TODO(#1612): decide whether enforce_tdd.py belongs here"}``
    cleared a hook from the live flagged set, reproduced against
    ``templates/settings.default.json`` (5 flagged -> 4).

    Args:
        node: Decoded JSON value.

    Returns:
        Every declared command string found, in traversal order.
    """
    found: "list[str]" = []
    if isinstance(node, dict):
        if node.get("type") == "command" and isinstance(node.get("command"), str):
            found.append(node["command"])
        for value in node.values():
            found.extend(_command_strings_under(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_command_strings_under(value))
    return found


def _events_in(node: object) -> "list[tuple[str, str]]":
    """Find ``(event, command_string)`` pairs under lifecycle-event keys.

    The walk is structural rather than positional so that it does not depend on
    whether the events hang off a top-level ``hooks`` object, a nested one, or
    neither — the surfaces in this repo differ.

    Args:
        node: Decoded JSON value.

    Returns:
        Pairs of lifecycle event name and a declared command string beneath it.
    """
    found: "list[tuple[str, str]]" = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in LIFECYCLE_EVENTS:
                found.extend((key, s) for s in _command_strings_under(value))
            else:
                found.extend(_events_in(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_events_in(value))
    return found


def _lifecycle_registrations(
    surfaces: "list[Path]",
) -> "dict[str, set[tuple[str, str]]]":
    """Map each registered hook filename to the surfaces and events naming it.

    Args:
        surfaces: Registration surface paths to read.

    Returns:
        Mapping of hook filename to a set of ``(surface_name, event)`` pairs.
        Unparseable surfaces are skipped — a malformed JSON file cannot confer
        a registration, and the positive control below is what proves the
        search as a whole still works.
    """
    registrations: "dict[str, set[tuple[str, str]]]" = {}
    for surface in surfaces:
        try:
            data = json.loads(surface.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for event, command in _events_in(data):
            # A commented-out command runs nothing. Stripping is what stops
            # ``{"type": "command", "command": "# python3 .../gate.py"}`` from
            # conferring a registration on a hook that is switched off.
            for name in _HOOK_FILENAME.findall(_strip_shell_comments(command)):
                registrations.setdefault(name, set()).add((surface.name, event))
    return registrations


def _sidecar_type(hook_path: Path) -> "str | None":
    """Return the ``type`` declared in a hook's ``.hook.json`` sidecar.

    Args:
        hook_path: Path to the hook script.

    Returns:
        The declared type, or ``None`` when there is no readable sidecar.
    """
    sidecar = hook_path.with_name(f"{hook_path.stem}.hook.json")
    if not sidecar.is_file():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8")).get("type")
    except (json.JSONDecodeError, OSError):
        return None


def _invoker_corpus(project_root: Path = PROJECT_ROOT) -> "list[Path]":
    """Enumerate files that may legitimately import or invoke a utility hook.

    Args:
        project_root: Repository root to resolve ``INVOKER_CORPUS_GLOBS``
            against.

    Returns:
        Sorted, de-duplicated file paths. Empty is permitted here and is not a
        hard error: it makes the guard STRICTER (nothing resolves as an
        importer), and ``test_invoker_corpus_is_populated`` covers the live
        repo. The registration search is the one whose emptiness would be
        vacuous, and that one raises.
    """
    found: "set[Path]" = set()
    for pattern in INVOKER_CORPUS_GLOBS:
        for path in project_root.glob(pattern):
            if path.is_file():
                found.add(path)
    return sorted(found)


def _shell_invocation_pattern(filename: str) -> "re.Pattern[str]":
    """Build a regex matching shell lines that EXECUTE ``filename``.

    Four accepted shapes, all of them RUNNING the file:

    * A named interpreter prefix — ``python3 path/to/hook.py``, ``uv run
      path/to/hook.py``, ``env python3 ...``. The path may contain ``${...}``
      and ``$(...)`` expansions, which is this repo's own template shape.
    * A variable interpreter in COMMAND position — ``"$PYTHON" path/hook.py``.
      Command position is required here (a bare ``$VAR`` alternative would
      match ``echo "$MSG path/hook.py"``, which runs nothing).
    * A path in command position containing at least one ``/`` — ``if
      plugins/.../hook.py; then``, ``"$HOOKS_DIR/hook.py" || exit 1``,
      ``plugins/.../hook.py --check``.
    * Module form — ``python3 -m hook_stem``.

    A bare mention matches none of them. ``[ -f path/to/hook.py ]`` is the
    measured instance (``scripts/test-autonomous-workflow.sh:86``): the path
    there sits after ``-f``, which is not a command position.

    Args:
        filename: Hook filename to look for.

    Returns:
        Compiled pattern for use against comment-stripped shell lines.
    """
    quoted = re.escape(filename)
    stem = re.escape(Path(filename).stem)
    interpreters = "|".join(_SHELL_INTERPRETERS)
    # Not preceded by a word character, so ``sh`` does not match inside
    # ``finish`` and turn ``finish path/hook.py`` into an invocation.
    named = rf"(?<![\w.\-/])(?:{interpreters})\s+"
    var_interp = rf"{_COMMAND_POSITION}\s*[\"']?\$\{{?\w+\}}?[\"']?\s+"
    return re.compile(
        # interpreter (named, or a variable in command position) + path
        rf"(?:{named}|{var_interp})(?:-\w+\s+)*[\"']?{_PATH_CHAR}*{quoted}"
        # a slash-bearing path in command position
        rf"|{_COMMAND_POSITION}\s*[\"']?{_PATH_CHAR}*/{_PATH_CHAR}*{quoted}"
        # python3 -m <stem>
        rf"|{named}(?:-\w+\s+)*-m\s+[\"']?{stem}\b"
    )


#: Exact string constants a copy of the #1588 refusal classifier must contain to
#: work at all. Derived from that module's own vocabulary, never restated here —
#: a hardcoded list would drift from the thing it is checking for.
_CLASSIFIER_VOCABULARY = frozenset(
    set(DECISION_KEYS)
    | set(REFUSAL_DECISION_VALUES)
    | set(REFUSAL_EMITTER_NAMES)
    | set(INSTRUMENTS)
)


def _reimplementation_suspects(source: str) -> "list[str]":
    """Find MODULE-LEVEL functions that look like a copy of the classifier.

    Shape-based rather than name-based. A guard keyed on the five borrowed
    names is invisible to a drifting copy called anything else — the
    ``_strip_body_arg_values`` case on record in this repo grew to 17
    reimplementations under 17 names. Any working copy of the refusal
    classifier must carry its vocabulary as string constants, whatever it is
    called.

    Scoped to module-level functions on purpose: the synthetic hook bodies in
    the test classes below legitimately contain ``"permissionDecision": "deny"``
    as fixture data.

    Args:
        source: Module source text to inspect.

    Returns:
        Sorted ``name (tokens)`` descriptions of suspect functions.
    """
    tree = ast.parse(source)
    suspects: "list[str]" = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        docstring = ast.get_docstring(node)
        hits = {
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and child.value in _CLASSIFIER_VOCABULARY
            and child.value != docstring
        }
        if hits:
            suspects.append(f"{node.name} ({', '.join(sorted(hits))})")
    return sorted(suspects)


def _callee_name(call: ast.Call) -> "str | None":
    """Return the bare name of a call's callee.

    Args:
        call: The call node.

    Returns:
        ``run`` for both ``run(...)`` and ``subprocess.run(...)``; ``None`` for
        a callee that is neither a name nor an attribute.
    """
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _argument_constants(call: ast.Call) -> "list[str]":
    """String constants passed as arguments to ``call`` itself.

    Descends through lists, tuples and f-string parts so that
    ``subprocess.run(["python3", "hooks/gate.py"])`` resolves, but STOPS at a
    nested call so that a mention inside ``run(cmd, stderr=log("gate.py"))`` is
    attributed to ``log`` rather than to ``run``.

    Args:
        call: The call node whose own arguments are being read.

    Returns:
        Every string constant in the argument subtrees.
    """
    found: "list[str]" = []
    stack: "list[ast.AST]" = list(call.args) + [kw.value for kw in call.keywords]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Call):
            continue
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                found.append(node.value)
            continue
        stack.extend(ast.iter_child_nodes(node))
    return found


def _resolve_importers(
    hook_path: Path, project_root: Path = PROJECT_ROOT
) -> "dict[Path, list[str]]":
    """Resolve real imports and invocations of a hook, by AST where possible.

    Three accepted shapes, none of them a substring match:

    * ``ast.Import`` / ``ast.ImportFrom`` naming the hook's module stem.
    * A string CONSTANT naming the hook file passed as an argument to an
      INVOCATION-shaped call — a callee in ``INVOCATION_CALLEES``. Requiring
      the call to be invocation-shaped is the #1612 reviewer's BLOCKING-2 fix:
      accepting any call let ``logging.info("gate.py is deprecated")``,
      ``print(...)``, ``raise ValueError(...)`` and ``add_argument(help=...)``
      each confer reachability, and would have let
      ``scripts/capture_baseline.py``'s dict LITERAL of hook names do the same
      the moment anyone rewrote it as ``dict(...)``. A module docstring is a
      bare ``Expr`` and is invisible for the same reason — the ``utility``
      reclassification in ``51743c87`` rested on exactly such a line.
    * For non-Python invokers, a comment-stripped shell line that EXECUTES the
      file (see ``_shell_invocation_pattern``).

    Args:
        hook_path: The hook whose importers are being resolved.
        project_root: Repository root for the invoker corpus.

    Returns:
        Mapping of importer path to its sorted ``file:line kind`` evidence
        strings; empty when nothing imports or invokes the hook.
    """
    stem = hook_path.stem
    filename = hook_path.name
    pattern = _shell_invocation_pattern(filename)
    resolved: "dict[Path, set[str]]" = {}

    for path in _invoker_corpus(project_root):
        if path.resolve() == hook_path.resolve():
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if filename not in source and stem not in source:
            continue
        evidence: "set[str]" = set()

        if path.suffix != ".py":
            for lineno, raw in enumerate(source.splitlines(), 1):
                if pattern.search(_SHELL_COMMENT.sub("", raw)):
                    evidence.add(f"{path.name}:{lineno} shell-invocation")
            if evidence:
                resolved[path] = evidence
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.rsplit(".", 1)[-1] == stem:
                        evidence.add(f"{path.name}:{node.lineno} import")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").rsplit(".", 1)[-1] == stem:
                    evidence.add(f"{path.name}:{node.lineno} from-import")
            elif isinstance(node, ast.Call):
                if _callee_name(node) not in INVOCATION_CALLEES:
                    continue
                if any(filename in c for c in _argument_constants(node)):
                    evidence.add(f"{path.name}:{node.lineno} call-argument")
        if evidence:
            resolved[path] = evidence
    return {path: sorted(ev) for path, ev in resolved.items()}


def _importer_evidence(
    hook_path: Path, project_root: Path = PROJECT_ROOT
) -> "list[str]":
    """Flatten ``_resolve_importers`` to sorted evidence strings.

    Args:
        hook_path: The hook whose importers are being resolved.
        project_root: Repository root for the invoker corpus.

    Returns:
        Sorted ``file:line kind`` evidence strings; empty when nothing imports
        or invokes the hook.
    """
    return sorted(
        e for ev in _resolve_importers(hook_path, project_root).values() for e in ev
    )


def _utility_route_is_grounded(
    hook_path: Path,
    registrations: "dict[str, set[tuple[str, str]]]",
    hooks_dir: Path,
    project_root: Path,
    seen: "set[Path] | None" = None,
) -> bool:
    """Does the hook's importer chain TERMINATE outside the unwired hook set?

    A ``utility`` hook is reachable only if something that is itself reached
    invokes it. Three grounds, checked per importer:

    1. The importer is not a hook in ``hooks_dir`` — a ``lib/`` or ``scripts/``
       consumer. Treated as grounded; see the CANNOT-detect list for what that
       gives up.
    2. The importer is a hook and is registered on a lifecycle event.
    3. The importer is a ``utility`` hook that is itself grounded, recursively.

    A CYCLE grounds nothing. Two ``utility`` hooks that invoke each other were
    both permitted before this — measured ``{}`` on a synthetic pair — while
    neither was reachable from any lifecycle event. Mutual vouching is the
    ``51743c87`` defect with two files instead of one sidecar.

    Args:
        hook_path: The utility hook being checked.
        registrations: Lifecycle registrations keyed by hook filename.
        hooks_dir: Directory of hook scripts, used to tell a hook importer from
            a library or script importer.
        project_root: Repository root for the invoker corpus.
        seen: Hooks already on the current chain; a revisit is a cycle.

    Returns:
        True when some importer chain terminates at a grounded consumer.
    """
    if seen is None:
        seen = set()
    resolved_self = hook_path.resolve()
    if resolved_self in seen:
        return False
    seen.add(resolved_self)

    hooks_root = hooks_dir.resolve()
    for importer in _resolve_importers(hook_path, project_root):
        if importer.resolve().parent != hooks_root:
            return True
        if registrations.get(importer.name):
            return True
        if _sidecar_type(importer) == UTILITY_TYPE and _utility_route_is_grounded(
            importer, registrations, hooks_dir, project_root, seen
        ):
            return True
    return False


def unreachable_refusers(
    hooks_dir: Path = HOOKS_DIR, project_root: Path = PROJECT_ROOT
) -> "dict[str, list[str]]":
    """THE RULE: hooks that can refuse and are reachable by nothing.

    A refusing hook is reachable when EITHER it is registered on at least one
    lifecycle event, OR it declares ``type: "utility"`` and a real importer or
    invoker resolves whose OWN chain is grounded (see
    ``_utility_route_is_grounded`` — two utility hooks vouching for each other
    ground nothing). Hooks with no refusal evidence are observers and are
    ignored entirely.

    Factored out so the live corpus and every synthetic control drive the
    IDENTICAL code path. A control that re-implements the rule proves nothing
    about the rule.

    Args:
        hooks_dir: Directory of hook scripts to classify.
        project_root: Repository root for registration surfaces and invokers.

    Returns:
        Mapping of flagged hook filename to its sorted failure reasons, drawn
        from ``UNREACHABILITY_REASONS``.

    Raises:
        RuntimeError: If zero registration surfaces are found.
        SyntaxError: If a ``.py`` hook does not parse, propagated from the
            #1588 instruments. Deliberately loud.
    """
    registrations = _lifecycle_registrations(_registration_surfaces(project_root))
    flagged: "dict[str, list[str]]" = {}

    for path in _iter_hook_files(hooks_dir):
        if not _refusal_evidence(path):
            continue
        if registrations.get(path.name):
            continue

        reasons = {"no-lifecycle-registration"}
        if _sidecar_type(path) == UTILITY_TYPE:
            if _utility_route_is_grounded(
                path, registrations, hooks_dir, project_root
            ):
                continue
            reasons.add("utility-declared-without-importer")
        else:
            reasons.add("no-utility-declaration")
        flagged[path.name] = sorted(reasons)

    return flagged


# =====================================================================
# ISSUE #1698 — THE LIBRARY CORPUS
#
# Everything below extends the corpus of this ratchet from ``HOOKS_DIR``
# to ``LIB_DIR``, closing limitation 4 of the module docstring: a hook
# invoked only by an orphaned library function read as reachable because
# nothing in the repository ever asked whether THAT library file is
# reached. ``lib/`` was not ratcheted at all.
#
# ``prior_art_search.py`` is the measured case. It shipped under #1669
# with 7,054 bytes, an entry in ``install_manifest.json``, deployment to
# every consumer repo and nine green tests — and ZERO production
# consumers, for a day. ``git show b5f9e726^:.../commands/implement.md |
# grep -c prior_art_search`` returns 0; the same grep against the wired
# state returns 5. Nothing failed while it was dead.
#
# THE CONTRACT: REACHED or UNKNOWN. Never ABSENT.
# -----------------------------------------------
# A false "this module is dead" carries mechanical authority and would
# license deleting live code, which is strictly worse than no ratchet at
# all. So every ambiguity resolves towards REACHED: a stem collision
# across sub-packages credits both, a shell shape that might be an
# invocation credits it, an unparseable embedded snippet credits nothing
# but is never counted as proof of death. ``prior_art_search`` itself
# ships this contract (``PRIOR ART: UNKNOWN — ...``); this inherits it.
# The output vocabulary carries no ``absent``/``dead``/``unused`` term,
# and ``test_the_instrument_never_asserts_a_module_is_dead`` enforces
# that, together with ``library_verdict``, which is the only sanctioned
# way to phrase a verdict and can emit no third value.
#
# WHY NOT IMPORT-ONLY — measured, and the reason a naive version deletes
# live code: 28 library modules (15,317 lines at the time of writing,
# both figures DERIVED at runtime by
# ``test_permitting_arm_modules_reached_only_without_an_import``) are
# reached by NO ``import`` anywhere in the corpus. They run as
# ``python3 path/to/X.py`` out of a command file, or through a settings
# binding, or through Python embedded in a markdown fence. An
# import-only walk calls all 28 dead.
#
# WHY NOT SERENA — stated because the instruments disagree and the
# disagreement is the finding, not something to resolve quietly.
# ``find_referencing_symbols`` on ``search_prior_art`` returns exactly
# one hit, its own ``_main``. Its only production consumer is a
# ``python3 -c`` script inside a ```bash fence at
# ``commands/implement.md:1001``, and no LSP can see into a markdown
# code fence. The instrument used HERE is AST over sources RECOVERED
# from those carriers (see ``_embedded_python_sources``) — grep locates
# the carrier, ``ast`` reads what is inside it. Same class as the
# ``importlib`` blind spot CLAUDE.md already documents.
# =====================================================================

LIB_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"

# Path components that take a file out of the library analysis entirely.
#
# ``.claude`` is the gitignored DEPLOY copy of the plugin tree and
# ``.worktrees``/``.codex`` are mirrors: counting any of them would let a
# module vouch for itself through its own deployed duplicate. ``tests``
# is excluded for the reason the hook corpus excludes it — a test import
# is evidence of COVERAGE, not of reachability, and ``prior_art_search``
# is the proof: nine passing tests over a module nothing called.
LIBRARY_EXCLUDED_PATH_PARTS = frozenset(
    {
        "archived",
        "__pycache__",
        "htmlcov",
        "node_modules",
        ".venv",
        ".claude",
        ".codex",
        ".worktrees",
        "tests",
    }
)

#: The corpus this half of the ratchet classifies. Derived from disk on
#: every run — a hardcoded module list is stale the moment anything is
#: added, and inherits the defect it polices.
LIBRARY_CORPUS_GLOBS = ("plugins/autonomous-dev/lib/**/*.py",)

#: Python files that are BOTH potential consumers and potential targets.
#: A file here is reached only when something already reached names it;
#: that recursion is what limitation 4 was missing.
LIBRARY_CONSUMER_GLOBS = (
    "plugins/autonomous-dev/hooks/**/*.py",
    "plugins/autonomous-dev/lib/**/*.py",
    "plugins/autonomous-dev/scripts/**/*.py",
    "scripts/**/*.py",
)

#: Surfaces that RUN on their own authority and therefore need nothing to
#: vouch for them: slash commands and agent definitions (invoked by the
#: user or dispatched by a coordinator), CI workflows, git hooks, and
#: shell scripts (operator-invoked).
#:
#: ``docs/**/*.md`` is DELIBERATELY absent. Eleven modules are "invoked"
#: only inside documentation prose; crediting that would make a tutorial
#: a reachability route. Those are #1690's subject, not this one's.
#:
#: ``scripts/*.py`` is NON-RECURSIVE, deliberately. A repo-root script is
#: operator-invoked on exactly the same authority as the ``scripts/**/*.sh``
#: two lines above it — ``scripts/improve_reviewer.py`` and
#: ``scripts/run_reviewer_benchmark.py`` are run by hand, and their plain
#: ``from X import`` lines are the ONLY consumers three library modules
#: have. Widening to ``scripts/**/*.py`` would additionally ground
#: ``scripts/verification/verify_issue94_tdd_red.py``, which is already
#: stale (it references ``tests/unit/hooks/test_git_hooks_issue94.py``, a
#: file that does not exist) — a stale verifier must not vouch for
#: anything. Do NOT confuse this tuple with ``INVOKER_CORPUS_GLOBS``: that
#: one serves the HOOK rule and its scripts globs are unrelated to this.
LIBRARY_ENTRY_SURFACE_GLOBS = (
    "plugins/autonomous-dev/commands/*.md",
    "plugins/autonomous-dev/agents/*.md",
    "plugins/autonomous-dev/hooks/**/*.sh",
    "scripts/**/*.sh",
    "scripts/hooks/*",
    "scripts/*.py",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
)

#: Where to LOOK for a settings surface. Which of them IS one is decided
#: by CONTENT, never by filename — see ``_binding_surfaces``.
LIBRARY_BINDING_SURFACE_GLOBS = ("plugins/autonomous-dev/**/*.json",)

#: The two classifications this instrument may emit. ``absent``,
#: ``dead`` and ``unused`` are deliberately NOT here: see the contract
#: note above, ``library_verdict`` (which joins each verdict to the
#: result field of the same name) and
#: ``test_the_instrument_never_asserts_a_module_is_dead``.
LIBRARY_VERDICTS = frozenset({"REACHED", "UNKNOWN"})

#: A ``.py`` filename inside a command string or a shell line.
_ANY_PY_TARGET = r"([\w.\-]+)\.py"

#: The interpreter-prefix and variable-interpreter fragments of
#: ``_shell_invocation_pattern``, restated here ONLY as composition —
#: every character class they are built from (``_SHELL_INTERPRETERS``,
#: ``_PATH_CHAR``, ``_COMMAND_POSITION``) is the #1612 constant itself,
#: so the two patterns cannot drift in what they consider a command.
_NAMED_INTERPRETER = rf"(?<![\w.\-/])(?:{'|'.join(_SHELL_INTERPRETERS)})\s+"
_VARIABLE_INTERPRETER = rf"{_COMMAND_POSITION}\s*[\"']?\$\{{?\w+\}}?[\"']?\s+"

#: The generic form of ``_shell_invocation_pattern``: the same accepted
#: shapes, with the filename left OPEN so one pass over a file yields
#: every module it runs. Building one pattern per module instead would
#: be 242 regex passes per file.
#:
#: The SECOND alternative — a slash-bearing path in command position with
#: no interpreter — is correct for a file that IS a shell program (``.sh``,
#: a workflow step, a settings command string), where every line is a
#: command by construction. It is NOT correct for markdown narrative,
#: where line-start is prose position and a path is a citation. See
#: ``_SHELL_INVOCATION_INTERPRETED`` and ``_references_in``.
_SHELL_INVOCATION_ANY = re.compile(
    rf"(?:{_NAMED_INTERPRETER}|{_VARIABLE_INTERPRETER})"
    rf"(?:-\w+\s+)*[\"']?{_PATH_CHAR}*?{_ANY_PY_TARGET}"
    rf"|{_COMMAND_POSITION}\s*[\"']?{_PATH_CHAR}*?/{_PATH_CHAR}*?{_ANY_PY_TARGET}"
    rf"|{_NAMED_INTERPRETER}(?:-\w+\s+)*-m\s+[\"']?([\w.]+)\b"
)

#: The NARRATIVE form. An EXPLICIT INTERPRETER TOKEN is required; the
#: bare-path and variable-interpreter alternatives are dropped.
#:
#: The rule the rest of this file enforces by AST — presence in text is
#: not proof of use — was unenforced on the LARGEST entry surface
#: (``commands/*.md`` + ``agents/*.md``), because that surface is read by
#: regex and ``^`` is a command position in shell but a sentence start in
#: prose. Four lines of documentation were grounding a cluster of
#: modules, MEASURED before this constant existed:
#:
#: * ``commands/audit.md:56`` — a MARKDOWN TABLE ROW whose cell holds the
#:   glob ``**/models.py``. That one cell grounded three ``models.py``
#:   modules (``agent_tracker/``, ``implement_dispatcher/``,
#:   ``sync_dispatcher/``), which rooted ~20 more through legitimate
#:   relative imports. The largest grounding root in the corpus was a
#:   docs table cell.
#: * ``commands/triage.md:80`` — ``…/daily_aggregate_manager.py::open_or_
#:   supersede_daily_aggregate`` cited in a sentence.
#: * ``commands/improve.md:187`` — a backticked path ending a sentence.
#: * ``agents/plan-critic.md:133`` — a backticked path inside parentheses.
#:
#: None of those four lines runs anything. Note what is NOT done here: no
#: file is special-cased, no stem is allowlisted, no threshold is tuned.
#: The category — "a bare path in markdown narrative is a command" — is
#: removed. Fenced blocks keep the full pattern, because inside a fence
#: line-start IS command position again.
#:
#: MEASURED 2026-08-28 — THIS ARM IS FORWARD HEADROOM, NOT LOAD-BEARING.
#: Replacing this pattern with a never-matching one and re-walking the live
#: tree changes the answer by **0 modules** (re-measured 2026-09-04 after
#: the #1723 repairs: 121 UNKNOWN either way, empty
#: delta). It does credit 7 modules — ``genai_validate.py``, ``goa_cli.py``,
#: ``hook_path_validator.py``, ``retrofit_executor.py``,
#: ``sync_dispatcher.py``, ``validator_diversity.py``,
#: ``worktree_command.py`` — but every one of them is ALSO credited by a
#: FENCED block in the same file, so the arm is redundant rather than
#: unused. 26 modules ground directly through a ``.md``;
#: ``prior_art_search.py`` is among the fence-credited ones.
#:
#: RETAINED anyway, deliberately: an unfenced instruction to run something
#: should not be silently dropped, and when the vocabulary is
#: REACHED|UNKNOWN the permissive direction is the safe one. Two permitting
#: arms exercise it, which makes it LOOK load-bearing — this note exists so
#: the next reader can tell decoration from load-bearing without
#: re-measuring.
_SHELL_INVOCATION_INTERPRETED = re.compile(
    rf"{_NAMED_INTERPRETER}(?:-\w+\s+)*[\"']?{_PATH_CHAR}*?{_ANY_PY_TARGET}"
    rf"|{_NAMED_INTERPRETER}(?:-\w+\s+)*-m\s+[\"']?([\w.]+)\b"
)

#: Suffixes read as NARRATIVE: prose with occasional embedded code, where
#: a bare path is a citation. Everything else is read as a program.
NARRATIVE_SUFFIXES = frozenset({".md", ".markdown"})

#: A fenced markdown code block opener/closer.
#:
#: KNOWN UNRECOGNISED, declared rather than left to be discovered — and
#: NOT widened, because untested breadth is worse than a declared gap:
#:
#: * ``~~~`` fences (CommonMark's alternative delimiter). This is a NEW
#:   miss introduced by the narrative rule above: before it, the full
#:   command grammar ran over the whole ``.md`` and a ``~~~`` block was
#:   read as commands like any other line. MEASURED 2026-08-28: **0**
#:   ``~~~`` fence lines across all 43 narrative entry surfaces.
#: * Attributed fences — ```` ```python title="x" ```` — where the info
#:   string carries more than a bare language token. MEASURED 2026-08-28:
#:   **0** occurrences across the same 43 surfaces.
#:
#: Both fail toward UNKNOWN, never toward asserting a module dead, so the
#: REACHED-or-UNKNOWN contract holds: an unrecognised fence under-credits
#: reachability, which produces a loud false red rather than a silent
#: green. Latent, not live. If either count stops being zero, widen the
#: pattern AND add a permitting arm for the new shape in the same diff.
_MD_FENCE = re.compile(r"^\s*```([\w+-]*)\s*$")

#: Languages whose fenced block is Python source.
_PYTHON_FENCE_LANGUAGES = frozenset({"python", "py", "python3"})

#: ``python3 -c '<script>'`` — the carrier that holds ``implement.md``'s
#: only consumer of ``search_prior_art``. Non-greedy to the matching
#: quote; ``ast`` decides whether what came out is really Python.
_INLINE_PYTHON_C = re.compile(
    r"python3?\s+(?:-\w+\s+)*-c\s+('|\")(.*?)(?<!\\)\1", re.DOTALL
)

#: ``python3 - <<'PY' ... PY`` — the heredoc carrier.
_PYTHON_HEREDOC = re.compile(
    r"python3?\s+(?:-\s+)?<<-?\s*[\"']?(\w+)[\"']?\r?\n(.*?)\r?\n\1", re.DOTALL
)


class LibraryReachability(NamedTuple):
    """The result of one library reachability walk.

    Attributes:
        corpus: Mapping of module key (posix path relative to ``lib/``)
            to its absolute path. DERIVED from disk, never hardcoded.
        reached: Mapping of module key to the evidence that reached it.
        unknown: Sorted module keys with no route found. NOT "absent" —
            see the contract note above.
        grounded: Every file the walk reached, mapped to its evidence.
        surfaces: The settings surfaces discovered by content.
    """

    corpus: "dict[str, Path]"
    reached: "dict[str, str]"
    unknown: "list[str]"
    grounded: "dict[Path, str]"
    surfaces: "list[Path]"


def _library_paths(project_root: Path, globs: "tuple[str, ...]") -> "list[Path]":
    """Resolve ``globs`` under ``project_root``, minus the excluded parts.

    Args:
        project_root: Repository root to glob against.
        globs: Glob patterns, relative to the root.

    Returns:
        Sorted, de-duplicated existing file paths.
    """
    found: "set[Path]" = set()
    for pattern in globs:
        for path in project_root.glob(pattern):
            if not path.is_file():
                continue
            if LIBRARY_EXCLUDED_PATH_PARTS.intersection(path.parts):
                continue
            found.add(path)
    return sorted(found)


def _library_corpus(project_root: Path = PROJECT_ROOT) -> "dict[str, Path]":
    """The library modules this ratchet classifies.

    Args:
        project_root: Repository root.

    Returns:
        Mapping of ``lib/``-relative posix path to absolute path.
        ``__init__.py`` is excluded: a package initialiser is reached
        through its package, and classifying FIVE of them by the same
        stem would collide. Five is the measured count on the CORPUS
        BASIS — ``find plugins/autonomous-dev/lib -name __init__.py``,
        i.e. initialisers inside ``lib/`` itself, which is the tree this
        function is relative to. Counting the wider consumer globs would
        give a different, irrelevant number. Since #1725 those five ARE
        walkable: ``_consumer_nodes`` keys them by package directory
        name. They remain outside the CORPUS, so an initialiser can
        never be pinned nor counted against the ceiling.
    """
    lib_dir = project_root / "plugins" / "autonomous-dev" / "lib"
    return {
        path.relative_to(lib_dir).as_posix(): path
        for path in _library_paths(project_root, LIBRARY_CORPUS_GLOBS)
        if path.name != "__init__.py"
    }


def _consumer_nodes(project_root: Path = PROJECT_ROOT) -> "dict[str, list[Path]]":
    """Python files addressable by module stem.

    Keyed by STEM because that is how this repo addresses them: every
    consumer does ``sys.path.insert(0, lib_path)`` and then ``import
    X``, so ``lib/agent_tracker/state.py`` and any other ``state.py``
    are indistinguishable to the resolver. A collision credits BOTH,
    which is the REACHED-or-UNKNOWN direction.

    ``__init__.py`` is the ONE stem that cannot be addressed this way,
    because EVERY package carries it: keying five initialisers under
    ``__init__`` makes the package directory unreachable by name and the
    stem itself meaningless. So an initialiser is keyed by its PACKAGE
    DIRECTORY name instead, which is how Python addresses it and how
    every consumer writes it (``from agent_tracker import AgentTracker``).

    This is a change to ADDRESSABILITY ONLY. Nothing is grounded here;
    the walk still has to arrive. And note that corpus membership is not
    node membership: ``_library_corpus`` continues to EXCLUDE
    ``__init__.py`` (:func:`_library_corpus`), so an initialiser is
    walkable but can never be pinned or counted against the ceiling.

    The re-key also un-shadows a real collision. ``lib/agent_tracker.py``
    is a 49-line SHIM that re-exports the package of the same name; under
    stem keying it OWNED the name ``agent_tracker`` and the package
    directory beside it was never entered, so seven live modules read
    UNKNOWN while ten grounded surfaces named the package.

    Args:
        project_root: Repository root.

    Returns:
        Mapping of module stem to every file carrying that stem, with
        ``__init__.py`` keyed by ``path.parent.name``.
    """
    nodes: "dict[str, list[Path]]" = {}
    for path in _library_paths(project_root, LIBRARY_CONSUMER_GLOBS):
        key = path.parent.name if path.name == "__init__.py" else path.stem
        nodes.setdefault(key, []).append(path)
    return nodes


def _shell_invoked_stems(
    text: str, pattern: "re.Pattern[str]" = _SHELL_INVOCATION_ANY
) -> "set[str]":
    """Module stems that ``text`` EXECUTES as a shell command.

    Comment-stripped per line with the #1588 ``_SHELL_COMMENT``, so a
    commented-out command runs nothing.

    Args:
        text: Shell text, a settings command string, or a fenced block.
        pattern: Which invocation grammar to apply.
            ``_SHELL_INVOCATION_ANY`` for text that IS a program (a
            ``.sh`` file, a workflow step, a settings command string, the
            inside of a fence), where line-start is command position;
            ``_SHELL_INVOCATION_INTERPRETED`` for markdown NARRATIVE,
            where line-start is a sentence and a bare path is a citation.

    Returns:
        The stems of every ``.py`` file in an invocation position, plus
        the module names of every ``-m`` form.
    """
    found: "set[str]" = set()
    for raw in text.splitlines():
        line = _SHELL_COMMENT.sub("", raw)
        for match in pattern.finditer(line):
            for group in match.groups():
                if group:
                    found.add(group.rsplit(".", 1)[-1])
    return found


def _fenced_code_blocks(text: str) -> "list[tuple[str, str]]":
    """Split ``text`` into its fenced code blocks.

    One walker, two consumers: ``_embedded_python_sources`` takes the
    Python-language blocks, and ``_references_in`` takes ALL of them so
    that a shell command inside a fence is still read as a command while
    the surrounding narrative is not.

    Args:
        text: Markdown text.

    Returns:
        ``(language, contents)`` pairs in document order. An unterminated
        final fence is DROPPED — its extent is unknowable, and guessing
        it would let the rest of the document be read as code.
    """
    blocks: "list[tuple[str, str]]" = []
    language: "str | None" = None
    buffer: "list[str]" = []
    for line in text.splitlines():
        fence = _MD_FENCE.match(line)
        if fence:
            if language is None:
                language = fence.group(1).lower()
                buffer = []
            else:
                blocks.append((language, "\n".join(buffer)))
                language = None
            continue
        if language is not None:
            buffer.append(line)
    return blocks


def _embedded_python_sources(text: str) -> "list[str]":
    """Recover Python source EMBEDDED in a non-Python carrier.

    Three carriers, all of them live in this repo:

    * A fenced ```python block in a command or agent definition.
    * ``python3 -c '<script>'`` inside a ```bash fence. This is the one
      that matters: ``commands/implement.md:1001`` carries
      ``from prior_art_search import search_prior_art`` here, and it is
      the module's ONLY production consumer. Serena returns one hit for
      that symbol — its own ``_main`` — because no LSP reads into a
      markdown fence.
    * A ``python3 - <<'PY'`` heredoc.

    Args:
        text: Markdown, shell or workflow text.

    Returns:
        Candidate Python sources. ``ast`` decides which really parse;
        this only locates the carriers.
    """
    sources: "list[str]" = [
        contents
        for language, contents in _fenced_code_blocks(text)
        if language in _PYTHON_FENCE_LANGUAGES
    ]
    sources.extend(m.group(2) for m in _INLINE_PYTHON_C.finditer(text))
    sources.extend(m.group(2) for m in _PYTHON_HEREDOC.finditer(text))
    return sources


def _python_referenced_stems(
    source: str, *, origin: "Path | None" = None
) -> "set[str]":
    """Module stems a Python source IMPORTS or INVOKES.

    AST, never regex — for the reason ``test_anthropic_client_ratchet``
    records: ``lib/semantic_gate.py`` and ``lib/secret_patterns.py``
    MENTION module names in a docstring and in regex pattern data, and a
    text search reports both as consumers.

    Args:
        source: Python source text.
        origin: The file ``source`` was read from, when there is one.
            Supplies the PACKAGE CONTEXT a relative import needs. When
            ``None`` — a fenced block in a markdown file, a ``python3 -c``
            payload — there is no package to be relative to, so the bare
            stem is emitted exactly as before. That is the
            over-approximating direction and it is the correct default
            for a snippet with no home.

    Returns:
        Stems named by an import, by a ``.py`` filename passed to an
        INVOCATION-shaped call (``INVOCATION_CALLEES``), or by the FIRST
        POSITIONAL name argument of a MODULE-LOADER call
        (``MODULE_LOADER_CALLEES`` — the ``importlib`` route). A syntax
        error yields the empty set: an unreadable file vouches for
        nothing, and never counts as proof that anything is dead.
    """
    try:
        with warnings.catch_warnings():
            # A recovered snippet may carry a stale escape sequence. That is
            # the AUTHOR's problem, not this instrument's, and a wall of
            # SyntaxWarning from ``<unknown>`` line numbers hides real output.
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    found: "set[str]" = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.rsplit(".", 1)[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.level and origin is not None:
                if _relative_import_targets(node, origin):
                    # RESOLVED RELATIVELY, so the bare stem is a FALSE
                    # address and must not be emitted. ``agent_tracker/
                    # tracker.py`` says ``from .models import ...``; the
                    # stem ``models`` maps to THREE files —
                    # ``agent_tracker/``, ``implement_dispatcher/`` and
                    # ``sync_dispatcher/models.py`` — and emitting it
                    # would credit two packages this file cannot reach.
                    # The resolved path went to the frontier instead.
                    #
                    # THIS IS THE ONLY LINE THAT CAN MOVE A MODULE
                    # REACHED -> UNKNOWN. It is gated on the import
                    # ACTUALLY RESOLVING on disk: when it does not, the
                    # stem is emitted unchanged, because an unrecognised
                    # edge form defaults to REACHABLE and never to dead.
                    continue
            if node.module:
                found.add(node.module.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Call):
            callee = _callee_name(node)
            if callee in MODULE_LOADER_CALLEES:
                # The importlib route. Read the FIRST POSITIONAL argument
                # only, and only when it is a string literal: by the
                # ``importlib`` contract that argument IS the module name.
                # See MODULE_LOADER_CALLEES for why the path argument cannot
                # be used and why ``_argument_constants`` must NOT be widened
                # to reach it.
                if node.args and isinstance(node.args[0], ast.Constant):
                    name = node.args[0].value
                    if isinstance(name, str) and name:
                        stem = name.rsplit("/", 1)[-1]
                        if stem.endswith(".py"):
                            stem = stem[: -len(".py")]
                        found.add(stem.rsplit(".", 1)[-1])
                continue
            if callee not in INVOCATION_CALLEES:
                continue
            for constant in _argument_constants(node):
                for token in re.findall(r"([\w.\-]+)\.py\b", constant):
                    found.add(token.rsplit("/", 1)[-1])
    return found



def _relative_import_targets(node: "ast.ImportFrom", anchor: Path) -> "set[Path]":
    """Files ONE relative ``from`` statement resolves to on disk.

    THE THIRD EDGE, at statement granularity. Split from
    :func:`_relative_package_targets` so that both consumers ask the
    IDENTICAL question of the IDENTICAL resolver: the walk needs the
    file-level union, and the stem suppression in
    :func:`_python_referenced_stems` needs to know whether THIS node
    resolved. Two resolvers would be two answers, and the suppression is
    the one direction that can move a module REACHED -> UNKNOWN.

    DIVERGENCE FROM THE TWO EXISTING RESOLVERS IN ``lib/``, argued here
    rather than silently re-derived. ``lib/hook_budgets.py:610`` and
    ``lib/tech_debt_detector.py:362`` both already resolve
    ``node.level``, and ``hook_budgets`` records this exact defect class
    in its own docstring ("The previous version filtered these out via
    ``node.level == 0`` and under-credited every relative import"). Both
    answer in NAMES — a stem set, a dotted module string — because their
    consumers are name-keyed. This walk's worklist is keyed by ``Path``,
    and the whole point of this edge is that the NAME is the thing that
    collapses: every package initialiser is named ``__init__``, and
    ``models`` names three different files. So resolution here is to
    FILE PATHS ON DISK, which is the one form a name-keyed answer cannot
    carry. The ``from . import cli`` case IS mirrored from
    ``hook_budgets.py:610`` — when ``node.module`` is falsy the module is
    the package itself, so the edge is each imported NAME.

    Resolution is by DIRECTORY existence, never by ``__init__.py``
    existence. Under PEP 420 a package directory need not contain an
    initialiser, and keying on one would make this edge silently vanish
    for a namespace package. No namespace package exists in this corpus
    today — every directory under ``lib/`` carries an ``__init__.py`` —
    so the rule costs nothing and a control defending a shape that is
    not present would.

    Args:
        node: The ``from ... import ...`` statement.
        anchor: The file the statement was parsed from. Levels are
            counted UP from its directory.

    Returns:
        Absolute paths that EXIST on disk. Empty when the import is
        absolute, when the level walks past the filesystem root, or when
        nothing resolves — and an empty answer means the caller falls
        back to today's bare-stem behaviour, never to "dead".
    """
    if not node.level:
        return set()
    base = anchor.parent
    for _ in range(node.level - 1):
        if base.parent == base:
            # Walked off the top of the filesystem. Nothing above the
            # root can be a package, so this addresses nothing.
            return set()
        base = base.parent
    candidates: "set[Path]" = set()
    if node.module:
        base = base.joinpath(*node.module.split("."))
        candidates.add(base.with_suffix(".py"))
        candidates.add(base / "__init__.py")
    for alias in node.names:
        candidates.add(base / f"{alias.name}.py")
        candidates.add(base / alias.name / "__init__.py")
    return {candidate for candidate in candidates if candidate.is_file()}


def _relative_package_targets(path: Path) -> "set[Path]":
    """Every file ``path`` reaches by relative import.

    The file-level union of :func:`_relative_import_targets`, and the
    channel the walk consults. Without it a package's own modules are
    unreachable: ``from agent_tracker import AgentTracker`` resolves
    through :func:`_consumer_nodes` to the package INITIALISER, and the
    initialiser's ``from .tracker import AgentTracker`` then has to be
    followed as a PATH, because its stem ``tracker`` is not the address
    Python used.

    Args:
        path: A Python source file.

    Returns:
        Absolute existing paths. An unreadable or unparseable file
        yields nothing — #1389's contract, restated: a file this
        instrument cannot read vouches for nothing, and never counts as
        proof that anything is dead.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return set()
    targets: "set[Path]" = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            targets |= _relative_import_targets(node, path)
    return targets


def _references_in(path: Path) -> "set[str]":
    """Every module stem ``path`` imports, runs, or embeds a call to.

    THE LIVE CALL PATH. Every control in this file must be aimed here
    rather than at one of the three helpers below it: for a ``.md`` file
    the shell arm runs FIRST, so a control that exercises only
    ``_embedded_python_sources`` verifies a function this walk calls
    second and proves nothing about the half that over-credits. That
    exact defect shipped in the first cut of #1698 and is now pinned by
    ``test_negative_control_is_aimed_at_the_live_call_path``.

    Three dispatches, by what the file IS:

    * ``.py`` — AST only.
    * NARRATIVE (``.md``) — an EXPLICIT INTERPRETER TOKEN is required in
      the prose, because a sentence start is not a command position. The
      full command grammar is then applied INSIDE each fenced block,
      where line-start is command position again.
    * Everything else (``.sh``, ``.yml``, git hooks) IS a program, so the
      full grammar applies throughout.

    Embedded Python is recovered from all three (a ``python3 -c`` payload
    can appear in any of them).

    Args:
        path: A consumer or entry-surface file.

    Returns:
        Referenced module stems. All three invocation styles are
        credited; missing one of them is what makes an import-only walk
        call 28 live modules dead.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    if path.suffix == ".py":
        return _python_referenced_stems(text, origin=path)
    if path.suffix.lower() in NARRATIVE_SUFFIXES:
        found = _shell_invoked_stems(text, _SHELL_INVOCATION_INTERPRETED)
        for _language, contents in _fenced_code_blocks(text):
            found |= _shell_invoked_stems(contents, _SHELL_INVOCATION_ANY)
    else:
        found = _shell_invoked_stems(text, _SHELL_INVOCATION_ANY)
    for source in _embedded_python_sources(text):
        found |= _python_referenced_stems(source)
    return found


def _command_entries_under_hooks(node: object) -> "list[str]":
    """Command strings beneath ANY ``hooks`` key, at any depth.

    Deliberately looser than ``_events_in``, which requires one of the
    eight ``LIFECYCLE_EVENTS``. ``.claude-plugin/default-settings.json``
    binds ``auto_fix_docs.py`` under ``PreCommit``, which is not a
    lifecycle event and which ``_events_in`` therefore refuses. For the
    HOOK rule that strictness is correct. For the LIBRARY rule the safe
    direction is the other one: a binding that might run is credited, so
    the module reads REACHED rather than falsely dead.

    Args:
        node: Decoded JSON value.

    Returns:
        Every declared command string under a ``hooks`` key.
    """
    found: "list[str]" = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "hooks":
                found.extend(_command_strings_under(value))
            else:
                found.extend(_command_entries_under_hooks(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_command_entries_under_hooks(value))
    return found


def _binding_surfaces(project_root: Path = PROJECT_ROOT) -> "list[Path]":
    """Settings surfaces, discovered by CONTENT and never by filename.

    A ``settings*.json`` glob finds five of the seven tracked surfaces in
    this repo and misses ``config/global_settings_template.json`` (16
    command entries, sole binder of ``enforce_tier_distribution.py``) and
    ``.claude-plugin/default-settings.json`` (sole binder of
    ``auto_fix_docs.py``). Both numbers are MEASURED by
    ``test_content_discovery_finds_surfaces_a_filename_glob_misses``,
    which fails if either becomes reachable by a name glob.

    Args:
        project_root: Repository root.

    Returns:
        Sorted paths of every JSON carrying command entries under a
        ``hooks`` key.
    """
    surfaces: "list[Path]" = []
    for path in _library_paths(project_root, LIBRARY_BINDING_SURFACE_GLOBS):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if _command_entries_under_hooks(data):
            surfaces.append(path)
    return surfaces


def _bound_stems(surfaces: "list[Path]") -> "set[str]":
    """Module stems bound to a hook event in ``surfaces``.

    Args:
        surfaces: Binding surfaces from ``_binding_surfaces``.

    Returns:
        Stems named in an invocation position inside a command entry.
    """
    found: "set[str]" = set()
    for surface in surfaces:
        try:
            data = json.loads(surface.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        for command in _command_entries_under_hooks(data):
            found |= _shell_invoked_stems(command)
    return found


#: Walk results, keyed by resolved project root. The walk parses every
#: consumer and every entry surface, so re-running it per test is the
#: difference between a fast tier-3 file and a slow one. Any test that
#: MUTATES a module global feeding the walk must clear it — see
#: ``_clear_library_reachability_cache``.
_LIBRARY_REACHABILITY_CACHE: "dict[Path, LibraryReachability]" = {}


def _clear_library_reachability_cache() -> None:
    """Drop every memoised walk. Call after mutating a module global."""
    _LIBRARY_REACHABILITY_CACHE.clear()


def library_reachability(
    project_root: Path = PROJECT_ROOT, *, use_cache: bool = True
) -> LibraryReachability:
    """THE LIBRARY RULE: which ``lib/`` modules something can actually run.

    A file is GROUNDED when it is an entry surface, when a settings
    surface binds its stem, or when some already-grounded file imports,
    invokes or embeds a call to it. The walk is transitive, so a module
    imported only by an orphan is NOT grounded — which is exactly the
    recursion limitation 4 of the module docstring says stops at the edge
    of the hook corpus.

    Args:
        project_root: Repository root to analyse. Overridable so the
            rule can be watched refusing and permitting on a synthetic
            tree, driving the IDENTICAL code path as the live corpus.
        use_cache: Read and write ``_LIBRARY_REACHABILITY_CACHE``. Pass
            ``False`` from any arm that mutates a module global.

    Returns:
        A :class:`LibraryReachability`. ``unknown`` means NO ROUTE WAS
        FOUND — it does not mean the module is dead, and nothing in this
        file may present it as such.
    """
    key = project_root.resolve()
    if use_cache and key in _LIBRARY_REACHABILITY_CACHE:
        return _LIBRARY_REACHABILITY_CACHE[key]

    corpus = _library_corpus(project_root)
    nodes = _consumer_nodes(project_root)
    surfaces = _binding_surfaces(project_root)

    grounded: "dict[Path, str]" = {}
    frontier: "list[Path]" = []

    for path in _library_paths(project_root, LIBRARY_ENTRY_SURFACE_GLOBS):
        grounded[path] = f"entry-surface {path.name}"
        frontier.append(path)

    for stem in sorted(_bound_stems(surfaces)):
        for path in nodes.get(stem, ()):
            if path not in grounded:
                grounded[path] = f"settings-binding {stem}"
                frontier.append(path)

    while frontier:
        source_file = frontier.pop()
        for stem in _references_in(source_file):
            for path in nodes.get(stem, ()):
                if path not in grounded:
                    grounded[path] = f"referenced by {source_file.name}"
                    frontier.append(path)
        if source_file.suffix == ".py":
            # THE RELATIVE CHANNEL, consulted at WALK TIME and nowhere
            # else. Nothing is credited while the graph is built; a
            # target is grounded only once its importer has been
            # DEQUEUED, which is what makes the credit conditional on the
            # package being reached, at a cost of zero extra lines.
            # ``implement_dispatcher/validators.py`` says ``import
            # implement_dispatcher`` and now resolves to that package's
            # initialiser — but ``validators.py`` is never dequeued, so
            # the edge is never traversed and the package stays UNKNOWN.
            # An ``if parent_is_reached`` guard here would move the
            # credit back to build time and destroy that property.
            for target in _relative_package_targets(source_file):
                if target in grounded:
                    continue
                if project_root not in target.parents:
                    # A level count that climbs out of the tree under
                    # analysis must not drag an outside file onto the
                    # frontier, where it would be parsed and its own
                    # imports credited.
                    continue
                origin = f"{source_file.parent.name}/{source_file.name}"
                grounded[target] = f"package re-export from {origin}"
                frontier.append(target)

    reached = {k: grounded[p] for k, p in corpus.items() if p in grounded}
    unknown = sorted(k for k, p in corpus.items() if p not in grounded)
    result = LibraryReachability(corpus, reached, unknown, grounded, surfaces)
    if use_cache:
        _LIBRARY_REACHABILITY_CACHE[key] = result
    return result


def unreached_library_modules(
    project_root: Path = PROJECT_ROOT, *, use_cache: bool = True
) -> "list[str]":
    """Library modules for which no invocation route resolved.

    Args:
        project_root: Repository root to analyse.
        use_cache: See :func:`library_reachability`.

    Returns:
        Sorted ``lib/``-relative keys classified UNKNOWN.

    Raises:
        RuntimeError: When the corpus is empty. A zero-module corpus
            makes "nothing is unreached" trivially true and every
            permitting assertion vacuous — an instrument failure, not a
            clean repository.
    """
    result = library_reachability(project_root, use_cache=use_cache)
    if not result.corpus:
        raise RuntimeError(
            f"Zero library modules found under {project_root} for globs "
            f"{list(LIBRARY_CORPUS_GLOBS)}.\n"
            f"Expected: the plugin's lib/ tree. An empty corpus makes "
            f"every reachability verdict vacuous — the search is broken, "
            f"not the repository.\n"
            f"See: the #1698 section of this module's source."
        )
    return result.unknown


# Library modules for which NO invocation route resolved, as measured on
# 2026-08-27 over 248 modules (the corpus size is DERIVED at runtime and
# deliberately not restated as a constant — a hardcoded population is
# stale the moment anything is added). 59,297 lines sit behind this pin.
#
# THIS IS NOT A LIST OF DEAD CODE. Every entry is UNKNOWN, never ABSENT:
# no route was found by the three styles this instrument reads. Deleting
# a module on the strength of its membership here is precisely the harm
# the REACHED-or-UNKNOWN contract exists to prevent — the instrument
# cannot see a dynamically-constructed import, a consumer in an untracked
# local settings file, or a route through a surface glob it does not
# enumerate. What membership DOES mean is that nothing this repository
# can mechanically check will notice if the module stops working.
#
# THE SET MAY ONLY SHRINK. Adding an entry is NOT an acceptable
# resolution for a failure of this guard: wire the module into the
# pipeline that is supposed to run it (that is what b5f9e726 did for
# prior_art_search.py), or open an issue to retire it. Every removal
# lowers LIBRARY_REACHABILITY_CEILING in the same diff.
#
# Worked examples of what is in here and why it matters:
#  * step5_quality_gate.py — named four times across implement.md and
#    implementer.md as the gate that "blocks", and invoked by neither.
#    A gate described in prose is not enforcement (INV-1).
#  * active_security_scanner.py — named in secret_patterns.py's module
#    docstring at line 6 as ``lib/active_security_scanner.py``. A
#    filename-level grep reads that bullet as a consumer; the AST
#    instrument does not, which is why it is still visible here.
#  * ideators/*.py — five modules under a sub-package whose only
#    consumer, ideation_engine.py, is itself UNKNOWN. That transitive
#    orphan is exactly limitation 4 of the module docstring, one corpus
#    over: before #1698 nothing asked whether the importer was reached.
#  * agent_tracker/*, implement_dispatcher/*, sync_dispatcher/* — three
#    plainly LIVE packages. Read the paragraph below before drawing any
#    conclusion about them.
#
# ON THE THREE PACKAGES — a RE-VERDICT, not a discovery of dead code.
# 24 modules moved REACHED -> UNKNOWN when the narrative-markdown rule
# was tightened (see LIBRARY_REACHABILITY_CEILING's history). Their
# previous REACHED verdict was FALSE: it rested on four lines of
# documentation prose, of which the load-bearing one was a table cell in
# ``commands/audit.md:56`` holding the glob ``**/models.py``. That cell
# grounded three ``models.py`` modules, and ~20 more hung off them by
# legitimate relative imports — real edges, rooted in a citation.
#
# So the packages are live and their INTERNAL wiring is sound; what no
# tracked surface does is invoke their ENTRY POINT visibly. UNKNOWN is
# the correct verdict for exactly that state, and it is the state this
# ratchet exists to make visible. NOTHING HERE IS TO BE DELETED — least
# of all a whole package. If you know the route, wire it so the
# instrument can see it, or widen the instrument and say which carrier
# it was missing.
PINNED_UNREACHED_LIBRARY: "frozenset[str]" = frozenset({
    "acceptance_criteria_parser.py",
    "active_security_scanner.py",
    "agent_feedback.py",
    "agent_pool.py",
    "alignment_fixer.py",
    "alignment_gate.py",
    "auto_implement_pipeline.py",
    "auto_inject_memory.py",
    "auto_install_deps.py",
    "batch_agent_verifier.py",
    "batch_git_finalize.py",
    "batch_mode_detector.py",
    "batch_resume_helper.py",
    "blocking_signal_classifier.py",
    "brownfield_retrofit.py",
    "checkpoint.py",
    "cia_promotion_filter.py",
    "claude_md_updater.py",
    "code_patcher.py",
    "code_path_analyzer.py",
    "completion_verifier.py",
    "complexity_assessor.py",
    "comprehensive_doc_validator.py",
    "context_budget_monitor.py",
    "coordinator_log.py",
    "copy_system.py",
    "daily_aggregate_manager.py",
    "distributed_training_validator.py",
    "doc_master_auto_apply.py",
    "doc_update_risk_classifier.py",
    "doc_verdict_validator.py",
    "drain_revert.py",
    "error_analyzer.py",
    "eval_metrics.py",
    "failure_analyzer.py",
    "feature_completion_detector.py",
    "feature_dependency_analyzer.py",
    "flaky_tests.py",
    "github_issue_fetcher.py",
    "hardware_calibrator.py",
    "headless_mode.py",
    "health_check.py",
    "ideation_engine.py",
    "ideation_report_generator.py",
    "ideators/accessibility_ideator.py",
    "ideators/performance_ideator.py",
    "ideators/quality_ideator.py",
    "ideators/security_ideator.py",
    "ideators/tech_debt_ideator.py",
    "implement_dispatcher/cli.py",
    "implement_dispatcher/dispatcher.py",
    "implement_dispatcher/models.py",
    "implement_dispatcher/modes.py",
    "implement_dispatcher/validators.py",
    "install_audit.py",
    "install_orchestrator.py",
    "installation_analyzer.py",
    "installation_validator.py",
    "macro_promotion.py",
    "math_utils.py",
    "mcp_profile_manager.py",
    "memory_formatter.py",
    "memory_layer.py",
    "memory_relevance.py",
    "orchestrator.py",
    "parallel_validation.py",
    "performance_profiler.py",
    "plan_critic_verdict.py",
    "plugin_updater.py",
    "pool_config.py",
    "project_md_parser.py",
    "qa_self_healer.py",
    "ralph_loop_manager.py",
    "realign_orchestrator.py",
    "retrofit_verifier.py",
    "retrospective_analyzer.py",
    "runtime_verification_classifier.py",
    "scope_detector.py",
    "search_utils.py",
    "selector_stall_detector.py",
    "session_resource_manager.py",
    "session_state_manager.py",
    "session_telemetry_reader.py",
    "skill_loader.py",
    "staging_manager.py",
    "status_tracker.py",
    "step5_quality_gate.py",
    "stuck_detector.py",
    "success_criteria_validator.py",
    "test_routing.py",
    "test_runner.py",
    "token_tracker.py",
    "tool_validator.py",
    "training_metrics.py",
    "update_plugin.py",
    "validate_marketplace_version.py",
    "worker_consistency_validator.py",
    "workflow_coordinator.py",
    "workflow_violation_logger.py",
})

# Ceiling on the library pin, asserted by EQUALITY against the pin size —
# the ``test_anthropic_client_ratchet`` form, which is the stronger one:
# the set cannot move in EITHER direction without appearing in a diff, so
# a swap (one module wired, another orphaned) cannot hide behind an
# unchanged total. Equal counts hiding a changed set is a defect this
# repository has on record.
#
# LOWERING needs no justification and is never blocked; that is the
# ratchet advancing. Lower LIBRARY_CEILING_HIGH_WATER_MARK in the SAME
# diff. RAISING is honest in exactly one case: a NEW INVOCATION STYLE or
# a NEW CORPUS made PRE-EXISTING orphans visible — say which, in the
# same diff.
#
# History — this ratchet may only count DOWN, with ONE sanctioned
# exception, taken once here and documented in full:
#   108  Issue #1698, first cut. Derived by running
#        ``library_reachability()`` over the live tree, NOT copied from
#        any report. Three figures were in circulation for "how many
#        modules are unreachable" — 124 (import-only, misses script
#        invocation), 111 (measured before prior_art_search was wired),
#        110 (a wider corpus of 255 including hooks/ and scripts/). None
#        of them answers THIS question, which is scoped to lib/.
#   132  Issue #1698, review round 1. A RAISE, under the one honest case
#        this constant's contract allows: A SHARPER INSTRUMENT MADE
#        PRE-EXISTING ORPHANS VISIBLE. No module changed; the instrument
#        stopped reading markdown narrative as shell (see
#        ``_SHELL_INVOCATION_INTERPRETED``). The 108 was wrong, not the
#        132: 24 modules had been credited to four lines of prose.
#
#        The 24, and why each moved — all REACHED -> UNKNOWN, none the
#        other way, attributed BY SET and not by count:
#          agent_tracker/{cli,display,metrics,models,state,tracker,
#            verification}.py, implement_dispatcher/{cli,dispatcher,
#            models,modes,validators}.py, sync_dispatcher/{cli,dispatcher,
#            models,modes}.py — 16 modules rooted in ONE table cell,
#            ``commands/audit.md:56``, whose ``**/models.py`` glob
#            grounded three ``models.py`` files that then rooted the rest
#            by real relative imports.
#          daily_aggregate_manager.py — ``commands/triage.md:80``, a
#            ``path.py::symbol`` citation in a sentence.
#          macro_promotion.py — ``commands/improve.md:187``, a backticked
#            path ending a sentence.
#          plan_critic_verdict.py — ``agents/plan-critic.md:133``, a
#            backticked path inside parentheses.
#          file_discovery.py, hook_activator.py, sync_mode_detector.py,
#            uninstall_orchestrator.py, version_detector.py — reached
#            only through one of the 16 above.
#
#        CROSS-CHECK, because a re-verdict of 24 modules should not rest
#        on one instrument. A blunter mutation — dropping the bare-path
#        alternative for EVERY file type, not just narrative — lands on
#        132 as well, and the difference set between the two is EMPTY.
#        The bare-path rule currently grounds nothing outside markdown.
#        It is nonetheless kept for ``.sh``/``.yml``/settings commands,
#        where line-start genuinely IS command position and #1612's shell
#        arms prove it must resolve.
#   121  Issue #1723. A LOWER, and the first time this ratchet has moved
#        DOWN since it was pinned. Two repairs plus five deletions, all
#        attributed BY SET:
#          -6 REACHED, because the walk gained two carriers it never had.
#            ``MODULE_LOADER_CALLEES`` (the ``importlib`` route):
#            baseline_guardrail.py and prompt_quality_rules.py, each
#            ``referenced by unified_pre_tool.py``; python_write_detector
#            .py, ``referenced by tool_intent.py``. ``scripts/*.py`` as
#            an entry surface: reviewer_benchmark.py and skill_evaluator
#            .py, ``referenced by run_reviewer_benchmark.py``;
#            reviewer_weakness_analyzer.py, ``referenced by
#            improve_reviewer.py``. Every route is the string the walk
#            itself printed, not a predicted one.
#          -5 DELETED, having no consumer in ANY of the now-five styles:
#            workflow_tracker.py, mcp_server_detector.py,
#            context_skill_injector.py, git_hooks.py, native_tools.py
#            (1,646 lines).
#        NOTHING moved UNKNOWN -> pinned in the other direction: the
#        measured ``live - pin`` difference set is EMPTY, so the two
#        repairs credited exactly six modules and over-credited none.
#   105  Issue #1725. A LOWER, and the largest single move so far: -16,
#        all REPAIR, nothing deleted. The walk gained its THIRD edge —
#        the relative import — after the instrument reported seven live
#        ``agent_tracker/*`` modules dead while TEN grounded surfaces
#        named the package. Two barriers stacked: ``lib/agent_tracker
#        .py`` is a 49-line SHIM whose STEM shadowed the package
#        directory beside it, and a package initialiser collapsed to the
#        stem ``__init__``, which every package shares. Attributed BY
#        SET, each route being the string the walk itself PRINTED:
#          -7 agent_tracker/: tracker.py, models.py and cli.py ``package
#            re-export from agent_tracker/__init__.py``; display.py,
#            metrics.py, state.py and verification.py ``package
#            re-export from agent_tracker/tracker.py``.
#          -4 sync_dispatcher/: dispatcher.py, models.py and cli.py
#            ``package re-export from sync_dispatcher/__init__.py``;
#            modes.py ``package re-export from sync_dispatcher/
#            dispatcher.py``. This one was PREDICTED UNCERTAIN — its
#            importers are themselves pinned, so the answer depended on
#            transitive closure. The closure resolved.
#          -5 TRANSITIVE TAIL, credited by the pre-existing STEM channel
#            once the four ``sync_dispatcher`` modules were dequeued:
#            file_discovery.py, hook_activator.py, uninstall_orchestrator
#            .py ``referenced by dispatcher.py``; sync_mode_detector.py
#            ``referenced by __init__.py``; version_detector.py, whose
#            printed route ALTERNATES across runs between ``referenced
#            by dispatcher.py`` and ``referenced by models.py`` — both
#            ``sync_dispatcher/`` files, both real. Route strings are a
#            WITNESS, not a contract: ``_references_in`` returns a set,
#            so which of several true importers gets recorded follows
#            frontier order. Recorded as observed rather than as one
#            run's string presented as THE route.
#        NOT moved, and this is the DISCRIMINATOR rather than an
#        omission: ``implement_dispatcher/*`` (5) and ``ideators/*`` (5)
#        stay UNKNOWN, all ten. ``implement_dispatcher/validators.py``
#        says ``import implement_dispatcher`` and NOW resolves to that
#        package's initialiser under the new keying — but ``validators
#        .py`` is never dequeued, so the edge is never traversed. The
#        credit is conditional because it happens at WALK time, and the
#        conditionality falls out of the WORKLIST at a cost of zero
#        lines; no ``if parent_is_reached`` guard exists, and adding one
#        would move the credit back to build time.
#        MEASURED, not asserted. The build-time variant was actually
#        run: grounding every relative target of every consumer before
#        the walk begins credits 15 MODULES MORE and lands the ceiling
#        at 90 — all five ``implement_dispatcher/*`` plus a ten-module
#        tail (agent_pool, batch_retry_consent, code_patcher,
#        copy_system, failure_analyzer, hardware_calibrator,
#        installation_validator, pool_config, stuck_detector,
#        token_tracker). ``ideators/*`` does NOT move even then, and an
#        earlier draft of this comment claiming it would was WRONG:
#        ``ideators/__init__.py`` imports absolutely, so the relative
#        resolver finds nothing there and the package still needs a
#        route through the stem channel. Corrected against the
#        measurement rather than left as the plausible number.
#        NOTHING moved REACHED -> UNKNOWN: the measured ``live - pin``
#        difference set is EMPTY. That direction was the real risk here,
#        because suppressing the bare stem of a resolved relative import
#        is the one change in #1725 that CAN take credit away.
#        PREDICTION vs MEASUREMENT, recorded because a wrong prediction
#        reported as wrong is worth more than one quietly adjusted: the
#        plan predicted 110 (band 105-112). Measured 105 — inside the
#        band, 5 below the point estimate. The whole miss is the
#        transitive tail: the plan counted the packages and not what
#        their modules would then reach.
#    99  The approval-subsystem deletion. A LOWER of -6, and the first
#        move on this ratchet made entirely of REMOVALS rather than
#        repairs: nothing was re-credited, six modules stopped
#        existing. The cluster was built, tested, shipped to five
#        consumer repos and NEVER ONCE EXECUTED --
#        auto_approval_engine.py, auto_approval_consent.py,
#        mcp_permission_validator.py, tool_approval_audit.py,
#        batch_retry_consent.py, batch_retry_manager.py (3,223 lines).
#        Two INDEPENDENT signals agreed before a line was cut: this
#        ratchet measured all six UNREACHED (static), and 541,492
#        activity-log lines resolved every mention of them to a Read,
#        Grep, Glob, Edit or Bash file operation -- agents looking AT
#        the files while investigating the deletion -- with zero
#        executions (runtime). Every external non-test importer was
#        under hooks/archived/, which the reachability corpus excludes
#        and no lifecycle event registers.
#        PREDICTION vs MEASUREMENT: the plan predicted 99, on the
#        reasoning that all six were already pinned so the unknown set
#        should drop by exactly six with no cascade. MEASURED 99 --
#        the prediction was exact. That is the expected shape for a
#        pure removal: a cascade needs a re-credited edge, and
#        deleting a node adds none.
#        NOTHING moved REACHED -> UNKNOWN and nothing moved the other
#        way: both measured difference sets, ``live - pin`` and
#        ``pin - live``, are EMPTY.
LIBRARY_REACHABILITY_CEILING = 99

# The highest library ceiling ever REVIEWED. Its only job is to make a
# RAISE cost a second, visible constant edit — tying the ceiling only to
# ``len(PINNED_UNREACHED_LIBRARY)`` makes both operands constants in this
# file, so one edit that adds an entry AND bumps the ceiling moves them
# together and nothing fires. Same residual-headroom contract as
# ``CEILING_HIGH_WATER_MARK``: lower it in the same diff and the residual
# is zero.
LIBRARY_CEILING_HIGH_WATER_MARK = 99


#: The functions ``_references_in`` DISPATCHES TO for a non-Python file.
#: Reaching for one of these directly is the hazard: they each see part of
#: what the walk sees, so a control aimed at one can be silent while the
#: walk is loud. Derived from the dispatch in ``_references_in``.
#:
#: ``_python_referenced_stems`` is DELIBERATELY absent. It is the Python
#: arm, not a markdown carrier, and a test exercising it on Python source
#: (``test_positive_control_the_reference_extractor_resolves_a_real_import``)
#: is not making a claim about markdown grounding.
MARKDOWN_CARRIER_HELPERS = frozenset(
    {"_embedded_python_sources", "_shell_invoked_stems", "_fenced_code_blocks"}
)

#: Entry points that see EVERYTHING the walk sees. Consulting any one of
#: them is what makes a markdown claim trustworthy.
LIVE_REACHABILITY_ENTRY_POINTS = frozenset(
    {"_references_in", "library_reachability", "unreached_library_modules"}
)


def _direct_calls(node: ast.AST) -> "set[str]":
    """Bare callee names invoked anywhere inside ``node``.

    Args:
        node: Any AST node.

    Returns:
        Callee names, ``self.helper()`` reduced to ``helper``.
    """
    found: "set[str]" = set()
    for call in ast.walk(node):
        if isinstance(call, ast.Call):
            name = _callee_name(call)
            if name is not None:
                found.add(name)
    return found


def _call_closure(source: str) -> "dict[str, set[str]]":
    """Map every function in ``source`` to what it can TRANSITIVELY call.

    Needed because the synthetic-corpus arms reach the walk through a
    class helper (``self._unknown`` -> ``unreached_library_modules``).
    Requiring a LEXICAL call to a live entry point would flag five
    perfectly good end-to-end tests, and the natural way to silence that
    is an allowlist — which is what makes a structural guard vacuous.

    Args:
        source: Module source text.

    Returns:
        Mapping of function name to every name reachable from it.
    """
    direct: "dict[str, set[str]]" = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            direct.setdefault(node.name, set()).update(_direct_calls(node))

    closure: "dict[str, set[str]]" = {}

    def _resolve(name: str, seen: "set[str]") -> "set[str]":
        if name in seen:
            return set()
        seen.add(name)
        reachable = set(direct.get(name, ()))
        for callee in list(reachable):
            reachable |= _resolve(callee, seen)
        return reachable

    for name in direct:
        closure[name] = _resolve(name, set())
    return closure


def controls_bypassing_the_live_call_path(source: str) -> "list[str]":
    """Test functions that consult a markdown carrier and NOTHING live.

    THE RULE: if a test reaches directly for one of
    :data:`MARKDOWN_CARRIER_HELPERS`, it is reasoning about how markdown
    grounds a module, and it MUST also reach — directly or through a
    helper defined in this file — one of
    :data:`LIVE_REACHABILITY_ENTRY_POINTS`, so the two answers are
    compared rather than one being assumed.

    Why this is a CATEGORY guard and not a second regression pin: the
    round-1 defect was a control aimed at ``_embedded_python_sources``,
    which the walk calls SECOND for a ``.md`` file. On the identical
    input the helper returned ``[]`` while ``_references_in`` returned
    ``['prior_art_search']`` — the control was green over the half that
    does not over-credit. Pinning that one fixture leaves the recurrence
    one new test away; a ``test_negative_control_for_workflow_yaml``
    calling ``_shell_invoked_stems(text)`` directly reintroduces it and a
    fixture pin stays green. This flags it.

    The asymmetry is deliberate. The TRIGGER is a DIRECT call (you
    personally reached for a partial view). SATISFACTION uses the call
    CLOSURE (you may reach the live path through a helper). Keying the
    trigger on the closure instead would flag ``_bound_stems``' callers,
    which consult a settings command string and never markdown.

    An earlier form keyed the trigger on FIXTURE SHAPE — a literal
    containing a fence, an ATX heading or a table row. Measured, it
    produced a false positive: ``test_utility_arm_refuses_a_declaration_
    backed_only_by_a_mention`` builds a synthetic PYTHON file whose
    ``# synthetic_utility_gate.py consumes ...`` comment reads as a
    markdown heading. Shape is what the fixture looks like; the call is
    what the test actually consults, which is the property that matters.

    Args:
        source: Module source text to inspect. Overridable so the rule
            can be watched REFUSING on synthetic sources — a structural
            guard only ever observed green over a corpus that already
            complies is unproven, which is the rule this whole file
            enforces on everything else.

    Returns:
        Sorted ``name (carriers=[...])`` descriptions of offenders.
    """
    closure = _call_closure(source)
    offenders: "list[str]" = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        direct = _direct_calls(node)
        carriers = direct & MARKDOWN_CARRIER_HELPERS
        if not carriers:
            continue
        reachable = set(direct)
        for callee in direct:
            reachable |= closure.get(callee, set())
        if not (reachable & LIVE_REACHABILITY_ENTRY_POINTS):
            offenders.append(f"{node.name} (carriers={sorted(carriers)})")
    return sorted(offenders)


def library_verdict(module_key: str, result: LibraryReachability) -> str:
    """The verdict for one module — the ONLY sanctioned way to phrase one.

    Every verdict in :data:`LIBRARY_VERDICTS` maps to the identically
    named (lower-cased) field of :class:`LibraryReachability`, and this
    function is the join. That makes the vocabulary LOAD-BEARING rather
    than decorative: it was previously a frozenset whose only consumer
    was an assertion comparing two literals in this same file, which
    costs nothing and proves nothing. Now, renaming a result field or
    inventing a third verdict breaks this lookup at runtime, on the path
    the failure message actually takes.

    Args:
        module_key: A ``lib/``-relative corpus key.
        result: A completed walk.

    Returns:
        ``"REACHED"`` or ``"UNKNOWN"`` — never ``"ABSENT"``.

    Raises:
        KeyError: When the module is in the corpus but in neither bucket,
            or in both. Either is a broken partition, and a broken
            partition must be loud rather than silently resolved to the
            convenient answer.
    """
    holders = sorted(
        verdict
        for verdict in LIBRARY_VERDICTS
        if module_key in getattr(result, verdict.lower())
    )
    if len(holders) != 1:
        raise KeyError(
            f"{module_key!r} resolves to verdicts {holders} — expected "
            f"exactly one of {sorted(LIBRARY_VERDICTS)}.\n"
            f"Expected: every corpus member sits in exactly one bucket. "
            f"Zero means the walk dropped it; two means the buckets "
            f"overlap and 'reached' no longer excludes 'unknown'.\n"
            f"See: the #1698 section of this module's source."
        )
    return holders[0]


def library_failure_message(new: "list[str]", project_root: Path = PROJECT_ROOT) -> str:
    """Build the message shown when a library module falls out of reach.

    Factored out so the REACHED-or-UNKNOWN contract can be checked
    MECHANICALLY rather than trusted — see
    ``test_the_instrument_never_asserts_a_module_is_dead``. A guard that
    told a maintainer "this module is unused" would license deleting live
    code, which is strictly worse than no guard.

    Args:
        new: Module keys that are UNKNOWN and not pinned.
        project_root: Repository root, for the surfaces line.

    Returns:
        The failure text.
    """
    result = library_reachability(project_root)
    surfaces = [p.name for p in result.surfaces]
    # Rendered THROUGH ``library_verdict`` rather than by pasting the
    # word "UNKNOWN" into an f-string: the vocabulary has to cost
    # something on the live path, or it is decoration.
    verdicts = {
        key: library_verdict(key, result)
        for key in sorted(new)
        if key in result.corpus
    }
    return (
        f"Library module(s) classified UNKNOWN — no invocation route was "
        f"found by any of the three styles: {sorted(new)}\n"
        f"Per-module verdict: {verdicts or '(synthetic keys, not in corpus)'}\n"
        f"UNKNOWN means NO ROUTE WAS FOUND. It does NOT mean the module is "
        f"unused, and it is NOT authority to remove anything.\n"
        f"Styles searched: (1) import/from-import and invocation-shaped "
        f"calls, by AST; (2) `python3 path/to/module.py` from an "
        f"executable surface, including Python recovered from a markdown "
        f"fence; (3) a hook binding in a settings surface discovered by "
        f"CONTENT.\n"
        f"Settings surfaces discovered: {surfaces}\n"
        f"Expected: wire the module into the pipeline that is supposed to "
        f"run it — that is what b5f9e726 did for prior_art_search.py, "
        f"which shipped manifest-registered, deployed and green on nine "
        f"tests with zero production consumers. If the route exists and "
        f"this instrument cannot see it, widen the instrument and say "
        f"which carrier it was missing.\n"
        f"Adding the module to PINNED_UNREACHED_LIBRARY is NOT a "
        f"resolution: the pin has a ceiling of "
        f"{LIBRARY_REACHABILITY_CEILING} and may only shrink."
    )


class TestInstrumentPremises:
    """Verify the search before trusting one cell of its output."""

    def test_registration_surfaces_are_populated(self):
        """A zero-surface search makes every verdict below vacuous."""
        surfaces = _registration_surfaces()
        assert len(surfaces) >= 5, (
            f"Only {len(surfaces)} registration surface(s) found: "
            f"{[p.name for p in surfaces]}. Expected the settings templates "
            f"plus the global template. Verify REGISTRATION_SURFACE_GLOBS."
        )
        names = {p.name for p in surfaces}
        assert any(n.startswith("settings.") for n in names), (
            f"No settings.*.json template among {sorted(names)} — the surface "
            f"globs no longer reach the templates directory."
        )

    def test_empty_surface_enumeration_is_a_hard_error(self, tmp_path):
        """Zero surfaces must RAISE, never silently pass.

        With no surfaces every hook reads as unregistered and every permitting
        assertion in this module becomes trivially true. That is an instrument
        failure and must be loud.
        """
        with pytest.raises(RuntimeError, match="Zero registration surfaces"):
            _registration_surfaces(tmp_path)

    def test_positive_control_unified_pre_tool_is_registered(self):
        """The search must FIND the repo's largest refuser as registered.

        If this ever fails the search has broken, and every "not registered"
        verdict it produces is meaningless rather than alarming.
        """
        registrations = _lifecycle_registrations(_registration_surfaces())
        hits = registrations.get("unified_pre_tool.py", set())
        assert hits, (
            "unified_pre_tool.py resolved to ZERO lifecycle registrations. It "
            "is the repo's largest refuser (9,164 recorded blocks) and is "
            "registered under PreToolUse in every settings template. The "
            "registration search is broken — do not read any other result in "
            "this module as evidence."
        )
        assert {event for _, event in hits} == {"PreToolUse"}, (
            f"unified_pre_tool.py resolved to events "
            f"{sorted({e for _, e in hits})}, expected exactly PreToolUse."
        )
        assert len({surface for surface, _ in hits}) >= 5, (
            f"unified_pre_tool.py resolved to only "
            f"{len({s for s, _ in hits})} surface(s): "
            f"{sorted({s for s, _ in hits})}. It is registered in five "
            f"settings templates plus the global template; a collapse to one "
            f"means the walk stopped descending."
        )

    def test_invoker_corpus_is_populated(self):
        """An empty invoker corpus would make every ``utility`` hook fail."""
        corpus = _invoker_corpus()
        assert len(corpus) >= 50, (
            f"Only {len(corpus)} invoker file(s) found. The utility-import arm "
            f"would flag every utility hook for want of a corpus to search."
        )

    def test_positive_control_importer_resolver_finds_a_real_import(self):
        """``hook_telemetry`` is genuinely imported by ``lib/hook_safety.py``.

        The resolver's control. Without it, "no importer found" is
        indistinguishable from "the resolver is broken", and every
        ``utility-declared-without-importer`` verdict below is meaningless.
        """
        telemetry = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "hook_telemetry.py"
        assert telemetry.is_file(), "premise: the control module still exists"
        evidence = _importer_evidence(telemetry)
        from_hook_safety = [e for e in evidence if e.startswith("hook_safety.py:")]
        assert from_hook_safety, (
            f"the importer resolver found no import of hook_telemetry in "
            f"lib/hook_safety.py, which contains two real `from hook_telemetry "
            f"import` statements. The resolver is broken; every "
            f"'no importer' verdict in this module is uninterpretable. "
            f"All evidence: {evidence}"
        )
        assert any("from-import" in e for e in from_hook_safety), (
            f"hook_telemetry resolved in hook_safety.py but not through the "
            f"import instrument: {from_hook_safety}"
        )

    def test_positive_control_importer_resolver_finds_a_shell_invocation(self):
        """``scripts/hooks/pre-commit`` really does execute a hook script.

        The shell arm needs its own control: the Python arm passing proves
        nothing about a regex that was tightened to reject ``[ -f ... ]``.
        """
        invoked = (
            PROJECT_ROOT
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "archived"
            / "validate_commands.py"
        )
        assert invoked.is_file(), "premise: the invoked script still exists"
        pre_commit = PROJECT_ROOT / "scripts" / "hooks" / "pre-commit"
        assert pre_commit.is_file(), "premise: the invoking shell script exists"
        assert "python3 plugins/autonomous-dev/hooks/archived/validate_commands.py" in (
            pre_commit.read_text(encoding="utf-8")
        ), (
            "premise: pre-commit still invokes validate_commands.py with an "
            "interpreter prefix. If the call was reworded, this control no "
            "longer exercises the shell arm — pick another instance."
        )
        evidence = _importer_evidence(invoked)
        assert any("pre-commit:" in e and "shell-invocation" in e for e in evidence), (
            f"the shell arm found no invocation of validate_commands.py in "
            f"scripts/hooks/pre-commit, which runs it under python3. The shell "
            f"arm is broken. Evidence: {evidence}"
        )

    def test_refusal_instruments_are_imported_not_reimplemented(self):
        """No second copy of the #1588 classifier may live in this file.

        A second copy drifts from the first. This repo has that defect class on
        record (``_strip_body_arg_values``: 2 callers, 17 reimplementations),
        and the brief for #1612 names it explicitly.
        """
        for fn in (
            _iter_hook_files,
            _python_refusal_evidence,
            _shell_refusal_evidence,
            _refusal_evidence,
            refusal_candidates,
        ):
            assert fn.__module__.endswith("test_refusal_sink_ratchet"), (
                f"{fn.__name__} resolves to module {fn.__module__!r}, not the "
                f"#1588 ratchet. It has been reimplemented or shadowed."
            )

        tree = ast.parse(Path(__file__).resolve().read_text(encoding="utf-8"))
        local_defs = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        borrowed = {
            "_iter_hook_files",
            "_python_refusal_evidence",
            "_shell_refusal_evidence",
            "_refusal_evidence",
            "refusal_candidates",
        }
        collision = sorted(local_defs & borrowed)
        assert not collision, (
            f"{collision} is defined locally in this module, shadowing the "
            f"#1588 instrument of the same name. Import it; do not copy it."
        )

    def test_no_reimplementation_hides_behind_a_different_name(self):
        """The name-exact arm above cannot see a copy called something else.

        A drifting copy named ``_local_refusal_evidence`` passes every
        assertion in the test above: it collides with no borrowed name and
        ``__module__`` still resolves for the five that were imported. This arm
        is keyed on SHAPE — the classifier's own string vocabulary — so the
        copy's name does not matter.
        """
        suspects = _reimplementation_suspects(
            Path(__file__).resolve().read_text(encoding="utf-8")
        )
        assert not suspects, (
            f"module-level function(s) in this file carry the #1588 refusal "
            f"vocabulary as string constants: {suspects}. That is a second "
            f"copy of the classifier under a new name. Import the instrument "
            f"from test_refusal_sink_ratchet; do not restate its vocabulary."
        )

    def test_positive_control_the_reimplementation_detector_can_fire(self):
        """A probe that returns zero is not evidence of zero.

        The arm above reports an empty list. Without an input it is KNOWN to
        flag, that empty list is indistinguishable from a detector that matches
        nothing — and this module deliberately contains no such function, so
        the control has to be driven over a synthetic source.
        """
        marker = sorted(_CLASSIFIER_VOCABULARY)[0]
        copied = (
            "def _local_refusal_evidence(source):\n"
            '    """A copy of the #1588 classifier under a different name."""\n'
            f"    return {marker!r} in source\n"
        )
        flagged = _reimplementation_suspects(copied)
        assert any(s.startswith("_local_refusal_evidence") for s in flagged), (
            f"POSITIVE CONTROL FAILED: a module-level function restating the "
            f"classifier vocabulary ({marker!r}) was not detected. The arm "
            f"above proves nothing — its empty result is an inert probe, not a "
            f"clean module. Got: {flagged}"
        )

        clean = (
            "def _unrelated_helper(path):\n"
            '    """Names no refusal vocabulary at all."""\n'
            '    return path.endswith(".py")\n'
        )
        assert _reimplementation_suspects(clean) == [], (
            "NEGATIVE CONTROL FAILED: a function naming none of the "
            "vocabulary was flagged, so the detector flags everything and its "
            "positive result above means nothing."
        )

    def test_manifest_and_classifications_are_not_registrations(self):
        """Shipping a file and classifying it are not invoking it.

        Both files MENTION the unreachable hooks — asserted here as a premise,
        so the control cannot pass vacuously — and both must contribute ZERO
        lifecycle registrations. This drives the extractor over the two files
        DIRECTLY, bypassing the name exclusion, which proves the structural
        rule alone is what refuses them.
        """
        config = PROJECT_ROOT / "plugins" / "autonomous-dev" / "config"
        manifest = config / "install_manifest.json"
        classifications = config / "component_classifications.json"
        assert manifest.is_file() and classifications.is_file(), (
            "premise: both metadata files still exist"
        )
        assert "enforce_tdd.py" in manifest.read_text(encoding="utf-8"), (
            "premise: install_manifest.json still ships enforce_tdd.py, so "
            "counting it as a registration would still change the answer"
        )
        assert "enforce_orchestrator" in classifications.read_text(encoding="utf-8"), (
            "premise: component_classifications.json still classifies "
            "enforce_orchestrator, so counting it would still change the answer"
        )

        leaked = _lifecycle_registrations([manifest, classifications])
        assert leaked == {}, (
            f"install_manifest.json / component_classifications.json produced "
            f"lifecycle registrations {sorted(leaked)}. The first ships a file "
            f"and the second is metadata; neither invokes anything. Treating "
            f"either as a registration is the mistake that let #1612 run "
            f"unnoticed."
        )

        surfaces = {p.name for p in _registration_surfaces()}
        assert not (surfaces & NON_REGISTRATION_SURFACES), (
            f"{sorted(surfaces & NON_REGISTRATION_SURFACES)} is enumerated as "
            f"a registration surface."
        )

    def test_the_manifest_exclusion_is_defence_in_depth_not_the_refusal(self):
        """Which rule is load-bearing, measured rather than asserted.

        ``NON_REGISTRATION_SURFACES`` was described as load-bearing on the
        strength of "279 leaked registrations". That figure belongs to a
        DIFFERENT mutant. Lifting the name exclusion and re-running the rule
        leaves the flagged set byte-identical, because the structural
        lifecycle-key requirement already refuses both metadata files. The
        exclusion is defence in depth and is now labelled as such.
        """
        import test_hook_reachability_ratchet as module

        with_exclusion = unreachable_refusers()
        original = module.NON_REGISTRATION_SURFACES
        try:
            module.NON_REGISTRATION_SURFACES = frozenset()
            lifted = module.unreachable_refusers()
        finally:
            module.NON_REGISTRATION_SURFACES = original

        assert lifted == with_exclusion, (
            f"lifting NON_REGISTRATION_SURFACES changed the answer: "
            f"{sorted(set(with_exclusion) ^ set(lifted))}. If that ever "
            f"becomes true the exclusion IS load-bearing and this test's "
            f"docstring — and the comment on the constant — are wrong."
        )

    def test_the_lifecycle_key_gate_is_what_refuses_the_manifest(self):
        """The mutation that IS load-bearing, driven end to end.

        Remove the lifecycle-key requirement from the event walk — collect
        every string in the file rather than only those under one of the eight
        ``LIFECYCLE_EVENTS`` — and the two metadata files leak hundreds of
        "registrations". That is the rule doing the work, and it is a
        structural property rather than a name list, which is why the name list
        can be lifted with no effect at all.
        """
        import test_hook_reachability_ratchet as module

        config = PROJECT_ROOT / "plugins" / "autonomous-dev" / "config"
        metadata = [
            config / "install_manifest.json",
            config / "component_classifications.json",
        ]
        assert all(p.is_file() for p in metadata), "premise: both files exist"

        assert _lifecycle_registrations(metadata) == {}, (
            "premise: WITH the lifecycle-key gate the metadata files confer "
            "nothing. If this fails the mutation below proves nothing."
        )

        def _every_string(node: object) -> "list[tuple[str, str]]":
            """The mutant: the key gate removed, everything else identical."""
            if isinstance(node, str):
                return [("PreToolUse", node)]
            if isinstance(node, dict):
                return [p for v in node.values() for p in _every_string(v)]
            if isinstance(node, list):
                return [p for v in node for p in _every_string(v)]
            return []

        original = module._events_in
        try:
            module._events_in = _every_string
            leaked = module._lifecycle_registrations(metadata)
        finally:
            module._events_in = original

        assert len(leaked) >= 50, (
            f"with the lifecycle-key gate removed the metadata files leaked "
            f"only {len(leaked)} registration(s). The gate was supposed to be "
            f"the rule carrying the weight; if removing it changes almost "
            f"nothing then something ELSE is refusing these files and the "
            f"module docstring names the wrong mechanism."
        )
        assert "enforce_tdd.py" in leaked, (
            f"the mutant leaked {len(leaked)} names but not enforce_tdd.py, "
            f"which install_manifest.json ships. The mutation is not reaching "
            f"the shape this test is about."
        )

    def test_no_corpus_hook_is_registered_only_in_a_local_surface(self):
        """The conclusion the tracked-surfaces-only choice rests on.

        Measured over EVERY ``settings*.json`` under ``.claude/`` and
        ``~/.claude/`` rather than the two or three anyone remembers — the
        first pass at this measurement missed ``.claude/settings.mcp_security.
        json`` and reported a clean zero, which is how the docstring came to
        claim ZERO local-only registrations when there are two.

        What matters is not that the number is zero (it is not) but that no
        hook IN THE CORPUS is reachable only through an untracked file. A local
        surface names hooks that do not exist in ``HOOKS_DIR`` at all, so it
        cannot change any verdict this module produces.
        """
        local = sorted(Path.home().joinpath(".claude").glob("settings*.json")) + sorted(
            (PROJECT_ROOT / ".claude").glob("settings*.json")
        )
        tracked = _lifecycle_registrations(_registration_surfaces())
        local_only = set(_lifecycle_registrations(local)) - set(tracked)
        corpus = {p.name for p in _iter_hook_files(HOOKS_DIR)}
        assert not (local_only & corpus), (
            f"{sorted(local_only & corpus)} is registered ONLY in an untracked, "
            f"machine-local settings file: {[str(p) for p in local]}. This "
            f"guard would call it unreachable in CI and reachable here, for the "
            f"same commit. Either register it in a tracked template or accept "
            f"that it is flagged.\n"
            f"Local-only registrations overall (may name hooks outside the "
            f"corpus, which is fine): {sorted(local_only)}"
        )


class TestRatchet:
    """The pinned unreachable set may only shrink."""

    def test_no_new_unreachable_refusers(self):
        """THE RATCHET. A newly-unreachable refuser fails here, named.

        Adding the offender to ``PINNED_UNREACHABLE`` is NOT an acceptable
        resolution — the ceiling below refuses it.
        """
        live = unreachable_refusers()
        new = sorted(set(live) - set(PINNED_UNREACHABLE))
        surfaces = [p.name for p in _registration_surfaces()]
        assert not new, (
            f"Hook(s) can refuse but are reachable by nothing: "
            f"{ {n: live[n] for n in new} }\n"
            f"Refusal evidence: "
            f"{ {n: _refusal_evidence(HOOKS_DIR / n) for n in new} }\n"
            f"Surfaces searched for a lifecycle registration: {surfaces}\n"
            f"Expected: register the hook on the lifecycle event it is meant "
            f"to gate, or — if it is genuinely imported by another hook — "
            f"declare type 'utility' AND give it a real importer. A hook that "
            f"can refuse and is invoked by nothing produces the same zero "
            f"block rows as a guard that is simply never needed, which is the "
            f"state #1612 exists to make visible.\n"
            f"Adding the file to PINNED_UNREACHABLE is NOT a resolution: the "
            f"pin has a ceiling of {REACHABILITY_CEILING} and may only shrink."
        )

    def test_pinned_entries_are_still_genuinely_unreachable(self):
        """The arm that makes this a ratchet rather than a permanent exemption.

        A hook that becomes reachable drops out of the live set and its stale
        pin fails until it is deleted. A hook that becomes reachable by ONE of
        the two routes changes its reasons, and that fails too — so the pin
        shrinks for the RIGHT reason and cannot quietly cover a different
        defect than the one it was written for.
        """
        live = unreachable_refusers()

        stale = sorted(name for name in PINNED_UNREACHABLE if name not in live)
        assert not stale, (
            f"PINNED_UNREACHABLE names {stale}, which are now reachable (or no "
            f"longer refuse at all). Delete them from the pin and lower "
            f"REACHABILITY_CEILING to match — that deletion IS the ratchet "
            f"advancing, and it is how #1612's other half gets recorded."
        )

        drifted = {
            name: {"pinned": sorted(reasons), "live": live[name]}
            for name, reasons in PINNED_UNREACHABLE.items()
            if set(live[name]) != set(reasons)
        }
        assert not drifted, (
            f"Pinned hook(s) now fail DIFFERENT conditions than recorded: "
            f"{drifted}\n"
            f"A pin that does not say which condition it covers cannot tell "
            f"you what changed. Update the reasons — and check whether the "
            f"change means the hook is now partially fixed."
        )

    def test_reachability_pin_has_a_ceiling(self):
        """The escape hatch cannot grow SILENTLY. An uncapped hatch is decorative.

        Four assertions, guarding four different failures. See the comments on
        ``REACHABILITY_CEILING`` and ``CEILING_HIGH_WATER_MARK``, and
        ``TestCeilingIsNotATautology`` for all of them driven end to end over
        mutated copies.
        """
        assert len(PINNED_UNREACHABLE) <= REACHABILITY_CEILING, (
            f"PINNED_UNREACHABLE has grown to {len(PINNED_UNREACHABLE)} entries "
            f"{sorted(PINNED_UNREACHABLE)}, over the ceiling of "
            f"{REACHABILITY_CEILING}. A hook was added to the exemption list "
            f"instead of being wired up. Register it, give it a real importer, "
            f"or delete it."
        )
        assert REACHABILITY_CEILING <= CEILING_HIGH_WATER_MARK, (
            f"REACHABILITY_CEILING was RAISED to {REACHABILITY_CEILING}, over "
            f"the reviewed high-water mark of {CEILING_HIGH_WATER_MARK}. LOWER "
            f"it freely — that is the ratchet advancing as #1612's other half "
            f"resolves each hook. RAISING it is honest in exactly one case: a "
            f"NEW ROUTE or INSTRUMENT made PRE-EXISTING unreachable hooks "
            f"visible. To take that case, in ONE diff: name the route here, "
            f"raise CEILING_HIGH_WATER_MARK alongside it, and justify each new "
            f"entry in the PINNED_UNREACHABLE comment with its evidence. "
            f"Anything else is a hook being pinned instead of wired up."
        )
        assert REACHABILITY_CEILING == len(PINNED_UNREACHABLE), (
            f"REACHABILITY_CEILING ({REACHABILITY_CEILING}) no longer equals "
            f"the pin size ({len(PINNED_UNREACHABLE)}). Slack in the ceiling is "
            f"a pre-authorised exemption for the next hook that fails. Lower "
            f"the ceiling to match — that IS the ratchet advancing."
        )
        assert len(PINNED_UNREACHABLE) <= CEILING_HIGH_WATER_MARK, (
            f"PINNED_UNREACHABLE ({len(PINNED_UNREACHABLE)}) is above the "
            f"highest ceiling ever reviewed ({CEILING_HIGH_WATER_MARK}). The "
            f"pin grew past the reviewed bound; no ceiling edit can authorise "
            f"that on its own."
        )

    def test_the_residual_headroom_is_zero(self):
        """State the hole rather than hide it, and hold it at zero.

        ``CEILING_HIGH_WATER_MARK`` is an upper bound, not a lockstep, so
        lowering ``REACHABILITY_CEILING`` without lowering the mark leaves that
        difference as headroom in which the pin could grow back with every
        ceiling assertion green. Lowering the mark in the same diff zeroes it.

        Deliberately NOT one of the assertions in
        ``test_reachability_pin_has_a_ceiling``: the mutation harness drives
        that test alone, and the sanctioned two-constant edit — wire a hook up,
        lower the pin and the ceiling — must be GREEN there. Keeping this arm
        separate means a maintainer who stops after two constants gets one
        named, one-line instruction here instead of a mutation harness going
        red at them.
        """
        residual = CEILING_HIGH_WATER_MARK - REACHABILITY_CEILING
        assert residual >= 0, (
            f"REACHABILITY_CEILING ({REACHABILITY_CEILING}) is above the "
            f"reviewed high-water mark ({CEILING_HIGH_WATER_MARK}); the bound "
            f"is inverted and the anti-raise assertion is inert."
        )
        assert residual == 0, (
            f"REACHABILITY_CEILING was lowered to {REACHABILITY_CEILING} while "
            f"CEILING_HIGH_WATER_MARK stayed at {CEILING_HIGH_WATER_MARK}. "
            f"That pre-authorises {residual} further pin entr(y/ies) that the "
            f"ceiling assertions would not see. Lower the mark to "
            f"{REACHABILITY_CEILING} — one line, no justification needed, and "
            f"it is the last step of the edit you have already made."
        )

    def test_pinned_reasons_are_drawn_from_the_pinned_vocabulary(self):
        """A new reason must be a deliberate edit, not an incidental one."""
        used: "set[str]" = set()
        for reasons in PINNED_UNREACHABLE.values():
            used |= set(reasons)
        for reasons in unreachable_refusers().values():
            used |= set(reasons)
        unknown = sorted(used - UNREACHABILITY_REASONS)
        assert not unknown, (
            f"unpinned unreachability reason(s) {unknown}. Add them to "
            f"UNREACHABILITY_REASONS deliberately, and say in the "
            f"PINNED_UNREACHABLE comment what new condition they describe."
        )

    def test_registered_refusers_are_permitted(self):
        """A guard that fails on everything is not a guard.

        The five registered gates refuse and MUST pass. This watches the rule
        PERMITTING over the live corpus, which a refusal-only guard never
        proves. The premise assertion is what stops it passing vacuously: each
        must still be DETECTED as a refuser, so it is permitted because it is
        reachable and not because it became invisible.

        ``PreToolUseWrite-protect-sensitive.sh`` is here as of #1588. It is the
        one entry that MOVED from ``PINNED_UNREACHABLE`` to this list, so it is
        also the arm that proves the ratchet advances rather than merely
        refuses: a hook that gets wired up must stop being flagged, and the
        only shell hook in the corpus is the case where that could quietly
        break.
        """
        candidates = refusal_candidates()
        live = unreachable_refusers()
        for name in (
            "unified_pre_tool.py",
            "unified_prompt_validator.py",
            "plan_gate.py",
            "enforce_file_organization.py",
            "PreToolUseWrite-protect-sensitive.sh",
        ):
            assert name in candidates, (
                f"premise: {name} is detected as refusal-capable, so its "
                f"permission below is meaningful rather than vacuous"
            )
            assert name not in live, (
                f"{name} is registered on a lifecycle event but the rule "
                f"flagged it as unreachable. The guard is refusing a "
                f"legitimate case."
            )

    def test_observers_are_ignored_entirely(self):
        """A hook that cannot refuse is out of scope, registered or not.

        ``validate_session_quality.py`` warns (exit 1), declares ``utility``,
        and is registered nowhere — every condition this guard tests except the
        one that matters. It must not be flagged.
        """
        path = HOOKS_DIR / "validate_session_quality.py"
        assert path.exists(), "premise: the observer still exists"
        assert not _refusal_evidence(path), (
            "premise: validate_session_quality.py still has no refusal "
            "evidence. If it started refusing, this is no longer an observer "
            "and the control needs another instance."
        )
        registrations = _lifecycle_registrations(_registration_surfaces())
        assert not registrations.get("validate_session_quality.py"), (
            "premise: the observer is still unregistered, so its exclusion is "
            "due to having no refusal evidence rather than to being registered"
        )
        assert "validate_session_quality.py" not in unreachable_refusers(), (
            "an observer with no refusal evidence was flagged. The rule is "
            "scoped to hooks that CAN refuse; widening it to every unwired "
            "hook is a different issue (see the module docstring)."
        )


class TestBothArmsOnSyntheticCorpora:
    """Watch the rule REFUSING and PERMITTING on shapes the live corpus lacks.

    Synthetic throughout, deliberately: once #1612's other half lands and the
    five pinned hooks are registered or deleted, live-corpus arms would stop
    exercising the refusing case. These keep working either way.

    Every control drives ``unreachable_refusers`` — the SAME function the live
    rule uses — over a synthetic repository. A control that re-implements the
    rule proves nothing about the rule.
    """

    @staticmethod
    def _repo(tmp_path: Path) -> "tuple[Path, Path]":
        """Build a minimal synthetic repo with one empty settings surface.

        Returns:
            ``(project_root, hooks_dir)``.
        """
        hooks = tmp_path / "plugins" / "autonomous-dev" / "hooks"
        hooks.mkdir(parents=True)
        templates = tmp_path / "plugins" / "autonomous-dev" / "templates"
        templates.mkdir(parents=True)
        (templates / "settings.default.json").write_text(
            json.dumps({"hooks": {"PreToolUse": []}}), encoding="utf-8"
        )
        return tmp_path, hooks

    @staticmethod
    def _hook(hooks: Path, name: str, body: str, *, sidecar_type: "str | None" = None):
        (hooks / name).write_text(body, encoding="utf-8")
        if sidecar_type is not None:
            (hooks / f"{Path(name).stem}.hook.json").write_text(
                json.dumps({"name": Path(name).stem, "type": sidecar_type}),
                encoding="utf-8",
            )

    @staticmethod
    def _surface(root: Path) -> Path:
        return (
            root / "plugins" / "autonomous-dev" / "templates" / "settings.default.json"
        )

    @classmethod
    def _register(cls, root: Path, hook_name: str, event: str = "PreToolUse") -> None:
        surface = cls._surface(root)
        data = json.loads(surface.read_text(encoding="utf-8"))
        data["hooks"].setdefault(event, []).append(
            {
                "matcher": "*",
                "hooks": [{"type": "command", "command": f"python3 .claude/hooks/{hook_name}"}],
            }
        )
        surface.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def _inject_under_event(
        cls, root: Path, entry: object, event: str = "PreToolUse"
    ) -> None:
        """Append an arbitrary JSON value under a lifecycle-event key.

        Used to drive shapes that MENTION a hook without invoking it.
        """
        surface = cls._surface(root)
        data = json.loads(surface.read_text(encoding="utf-8"))
        data["hooks"].setdefault(event, []).append(entry)
        surface.write_text(json.dumps(data), encoding="utf-8")

    def test_refusing_arm_unregistered_gate_is_flagged_and_named(self, tmp_path):
        """A gate with refusal evidence and no registration → FLAGGED.

        The refusal shape is deliberately different from all five pinned
        hooks (which use ``permissionDecision: deny``, ``sys.exit(2)`` and
        ``return 2``): this one refuses with ``{"decision": "ask"}``. A control
        shaped like the reproducer proves only that the reproducer is matched.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "synthetic_unwired_gate.py",
            'import json\n'
            'def main():\n'
            '    print(json.dumps({"decision": "ask", "reason": "nope"}))\n',
        )
        result = unreachable_refusers(hooks, root)
        assert set(result) == {"synthetic_unwired_gate.py"}, (
            f"the rule failed to flag a gate that can refuse and is registered "
            f"nowhere — it does not detect the class it exists to detect. "
            f"Got: {result}"
        )
        assert result["synthetic_unwired_gate.py"] == [
            "no-lifecycle-registration",
            "no-utility-declaration",
        ], f"wrong reasons recorded: {result}"

    def test_permitting_arm_registered_gate_is_not_flagged(self, tmp_path):
        """The SAME gate, registered → PERMITTED.

        Without this arm a rule that flagged every file would pass the refusing
        control above while being worthless.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "synthetic_unwired_gate.py",
            'import json\n'
            'def main():\n'
            '    print(json.dumps({"decision": "ask", "reason": "nope"}))\n',
        )
        self._register(root, "synthetic_unwired_gate.py")
        assert unreachable_refusers(hooks, root) == {}, (
            "a gate registered under PreToolUse was flagged as unreachable. "
            "The guard refuses a legitimate case."
        )

    def test_both_arms_discriminated_within_one_scan(self, tmp_path):
        """Refusing and permitting, separated inside a single corpus.

        Proves the rule discriminates per hook rather than keying on some
        property of the corpus as a whole.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(hooks, "aaa_unwired.py", 'print({"permissionDecision": "deny"})\n')
        self._hook(hooks, "bbb_wired.py", 'print({"permissionDecision": "deny"})\n')
        self._register(root, "bbb_wired.py", event="UserPromptSubmit")
        assert sorted(unreachable_refusers(hooks, root)) == ["aaa_unwired.py"], (
            f"the rule did not discriminate within one scan: "
            f"{unreachable_refusers(hooks, root)}"
        )

    def test_observer_with_no_refusal_evidence_is_ignored(self, tmp_path):
        """An unregistered hook that cannot refuse → IGNORED, not flagged."""
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "synthetic_observer.py",
            'import json\n'
            'def main():\n'
            '    print(json.dumps({"permissionDecision": "allow"}))\n'
            '    return 0\n',
        )
        assert unreachable_refusers(hooks, root) == {}, (
            "an observer with no refusal evidence was flagged. The rule must "
            "be scoped to hooks that CAN refuse."
        )

    def test_shell_gate_arm_is_exercised_too(self, tmp_path):
        """The corpus is not Python-only; the shell arm must flag as well.

        A Python-only glob was one of the original #1588 defects, and the shell
        hook is one of the five pinned here.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "synthetic_shell_gate.sh",
            "#!/usr/bin/env bash\n"
            "cat <<EOF\n"
            '{"permissionDecision": "deny", "reason": "nope"}\n'
            "EOF\n",
        )
        assert set(unreachable_refusers(hooks, root)) == {"synthetic_shell_gate.sh"}, (
            "the shell arm failed to flag an unwired shell gate"
        )
        self._register(root, "synthetic_shell_gate.sh")
        assert unreachable_refusers(hooks, root) == {}, (
            "a registered shell gate was flagged; the shell arm has no "
            "permitting case"
        )

    def test_utility_arm_refuses_a_declaration_backed_only_by_a_mention(
        self, tmp_path
    ):
        """THE 51743c87 REPRODUCER. ``utility`` + a docstring mention → FLAGGED.

        This is the reclassification that produced the current state: the
        sidecar says the hook is imported, and the only evidence is prose. If a
        mention sufficed, the guard could be satisfied by exactly the one-line
        edit it exists to police.
        """
        root, hooks = self._repo(tmp_path)
        lib = root / "plugins" / "autonomous-dev" / "lib"
        lib.mkdir(parents=True)
        (lib / "synthetic_consumer.py").write_text(
            '"""Coordinates with synthetic_utility_gate.py for threshold work."""\n'
            "# synthetic_utility_gate.py consumes get_threshold() from here.\n"
            "def get_threshold():\n"
            "    return 3\n",
            encoding="utf-8",
        )
        self._hook(
            hooks,
            "synthetic_utility_gate.py",
            "import sys\n"
            "def main():\n"
            '    sys.stderr.write("BLOCKED\\n")\n'
            "    return 2\n",
            sidecar_type="utility",
        )
        result = unreachable_refusers(hooks, root)
        assert set(result) == {"synthetic_utility_gate.py"}, (
            f"a hook declared type 'utility' on the strength of a docstring "
            f"mention was accepted as reachable. The guard can be satisfied by "
            f"the one-line sidecar edit that produced #1612. Got: {result}"
        )
        assert result["synthetic_utility_gate.py"] == [
            "no-lifecycle-registration",
            "utility-declared-without-importer",
        ], f"wrong reasons recorded: {result}"

    def test_utility_arm_permits_a_declaration_backed_by_a_real_import(
        self, tmp_path
    ):
        """The permitting arm for the utility route: a real import → PERMITTED.

        Same hook, same sidecar, same consumer file — the ONLY difference from
        the arm above is that the mention becomes an ``import``. Holding
        everything else fixed is what makes this discriminate the import from
        the prose rather than some other property of the fixture.
        """
        root, hooks = self._repo(tmp_path)
        lib = root / "plugins" / "autonomous-dev" / "lib"
        lib.mkdir(parents=True)
        (lib / "synthetic_consumer.py").write_text(
            '"""Coordinates with synthetic_utility_gate.py for threshold work."""\n'
            "import synthetic_utility_gate\n"
            "def run():\n"
            "    return synthetic_utility_gate.main()\n",
            encoding="utf-8",
        )
        self._hook(
            hooks,
            "synthetic_utility_gate.py",
            "import sys\n"
            "def main():\n"
            '    sys.stderr.write("BLOCKED\\n")\n'
            "    return 2\n",
            sidecar_type="utility",
        )
        assert unreachable_refusers(hooks, root) == {}, (
            "a utility hook with a real `import` of it was flagged. The guard "
            "refuses the sanctioned import route."
        )

    def test_utility_arm_permits_a_subprocess_invocation(self, tmp_path):
        """A hook run as a subprocess is reachable without being imported."""
        root, hooks = self._repo(tmp_path)
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "synthetic_runner.py").write_text(
            "import subprocess\n"
            "def run():\n"
            '    return subprocess.run(["python3", "hooks/synthetic_utility_gate.py"])\n',
            encoding="utf-8",
        )
        self._hook(
            hooks,
            "synthetic_utility_gate.py",
            "import sys\n"
            "def main():\n"
            '    sys.stderr.write("BLOCKED\\n")\n'
            "    return 2\n",
            sidecar_type="utility",
        )
        assert unreachable_refusers(hooks, root) == {}, (
            "a utility hook invoked via subprocess with its filename as a call "
            "argument was flagged as unreachable"
        )

    #: Single lines that MENTION a hook filename inside a call. Every one of
    #: these cleared a ``utility``-declared gate before the callee check —
    #: measured, all five, plus the ``dict(...)`` shape that the live
    #: ``scripts/capture_baseline.py`` is one refactor away from.
    _MENTION_INSIDE_A_CALL = {
        "logging.info": 'logging.info("synthetic_utility_gate.py is deprecated")',
        "print": 'print("see synthetic_utility_gate.py for details")',
        "raise ValueError": 'raise ValueError("synthetic_utility_gate.py missing")',
        "argparse help": (
            'p.add_argument("--x", help="mirrors synthetic_utility_gate.py")'
        ),
        "dict() constructor": (
            'STDIN_PAYLOADS = dict(a="synthetic_utility_gate.py")'
        ),
        "nested inside a real invocation": (
            'subprocess.run(["echo"], stderr=logging.info("synthetic_utility_gate.py"))'
        ),
    }

    #: Shapes that genuinely RUN the hook. Every one must clear it.
    _REAL_INVOCATION = {
        "subprocess.run list": (
            'subprocess.run(["python3", "hooks/synthetic_utility_gate.py"])'
        ),
        "subprocess.Popen": (
            'subprocess.Popen(["python3", "hooks/synthetic_utility_gate.py"])'
        ),
        "check_call shell string": (
            'subprocess.check_call("python3 hooks/synthetic_utility_gate.py", '
            "shell=True)"
        ),
        "runpy.run_path": 'runpy.run_path("hooks/synthetic_utility_gate.py")',
        "os.system": 'os.system("python3 hooks/synthetic_utility_gate.py")',
    }

    def _utility_repo(self, tmp_path: Path, consumer_body: str):
        """Build a repo with one utility gate and one consumer line."""
        root, hooks = self._repo(tmp_path)
        lib = root / "plugins" / "autonomous-dev" / "lib"
        lib.mkdir(parents=True)
        (lib / "synthetic_consumer.py").write_text(
            "import logging, os, runpy, subprocess\n" + consumer_body + "\n",
            encoding="utf-8",
        )
        self._hook(
            hooks,
            "synthetic_utility_gate.py",
            "import sys\n"
            "def main():\n"
            '    sys.stderr.write("BLOCKED\\n")\n'
            "    return 2\n",
            sidecar_type="utility",
        )
        return root, hooks

    @pytest.mark.parametrize("shape_name", sorted(_MENTION_INSIDE_A_CALL))
    def test_regression_issue_1612_a_mention_inside_a_call_is_not_an_invocation(
        self, tmp_path, shape_name
    ):
        """REFUSING ARM. A string constant in a call is not reachability.

        The reviewer's BLOCKING-2 finding, as BEHAVIOUR. The old rule accepted
        a filename constant anywhere inside ANY ``ast.Call``, so the utility
        arm drew the line at Expr-versus-Call when the property that matters is
        MENTION-versus-INVOCATION. Each line below is a single edit that
        cleared a ``utility``-declared gate.

        Reproduced end to end against the live corpus by the reporter: adding a
        file to ``lib/`` whose entire content was ``import logging`` plus
        ``logging.info("enforce_tdd.py is deprecated; see #1612")`` took the
        flagged set 5 -> 4. No import. No invocation. A log message.

        The live near-miss this also closes: ``scripts/capture_baseline.py``
        names all four ``enforce_*`` hooks in a dict LITERAL, which escaped only
        because a literal is not syntactically a call. Rewritten as
        ``dict(...)`` it becomes one, and four pins would silently clear — the
        ``dict() constructor`` case below is that rewrite.
        """
        root, hooks = self._utility_repo(
            tmp_path, self._MENTION_INSIDE_A_CALL[shape_name]
        )
        result = unreachable_refusers(hooks, root)
        assert set(result) == {"synthetic_utility_gate.py"}, (
            f"the {shape_name!r} mention CLEARED a utility-declared gate. One "
            f"line of prose inside a call is not something running the hook, "
            f"and accepting it means the guard can be satisfied by exactly the "
            f"kind of edit that produced #1612. Got: {result}"
        )
        assert result["synthetic_utility_gate.py"] == [
            "no-lifecycle-registration",
            "utility-declared-without-importer",
        ], f"wrong reasons recorded: {result}"

    @pytest.mark.parametrize("shape_name", sorted(_REAL_INVOCATION))
    def test_permitting_arm_real_invocation_shapes_confer_reachability(
        self, tmp_path, shape_name
    ):
        """PERMITTING ARM. Every sanctioned run-shape must still resolve.

        Same fixture, same hook, same sidecar as the refusing arms above — the
        ONLY difference is that the consumer line RUNS the file. Without this,
        a callee check that had been tightened into rejecting everything would
        pass every refusing arm while being worthless.
        """
        root, hooks = self._utility_repo(tmp_path, self._REAL_INVOCATION[shape_name])
        assert unreachable_refusers(hooks, root) == {}, (
            f"the {shape_name!r} invocation was rejected. The guard refuses a "
            f"sanctioned route: nothing else would make this hook reachable, so "
            f"a correctly-wired utility hook reads as unreachable."
        )

    def test_regression_issue_1612_capture_baseline_dict_literal_still_vouches_for_nothing(
        self, tmp_path
    ):
        """The live near-miss, in both of its forms.

        ``scripts/capture_baseline.py:59-62`` names all five pinned hooks as
        dict KEYS. A literal is not a call, so it never conferred reachability
        — but that is an accident of syntax, not a property anyone chose. This
        drives both the literal and the ``dict(...)`` rewrite through the rule
        and requires the same answer from each, so the escape stops depending
        on which spelling a future refactor happens to pick.
        """
        for label, body in (
            ("dict literal", 'PAYLOADS = {"synthetic_utility_gate.py": "{}"}'),
            ("dict() call", 'PAYLOADS = dict(gate="synthetic_utility_gate.py")'),
        ):
            root, hooks = self._utility_repo(tmp_path / label.replace(" ", "_"), body)
            result = unreachable_refusers(hooks, root)
            assert set(result) == {"synthetic_utility_gate.py"}, (
                f"the {label} form conferred reachability. Naming a hook as "
                f"payload-table data is not invoking it, and the two spellings "
                f"must not disagree. Got: {result}"
            )

    def test_utility_declaration_alone_confers_nothing_without_any_corpus(
        self, tmp_path
    ):
        """Boundary: the sidecar is a claim, not evidence.

        With no invoker corpus at all, a ``utility`` declaration must still
        fail. This is the arm that stops the guard being satisfiable by
        metadata.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "synthetic_claim_only.py",
            "import sys\n"
            "def main():\n"
            "    sys.exit(2)\n",
            sidecar_type="utility",
        )
        result = unreachable_refusers(hooks, root)
        assert result == {
            "synthetic_claim_only.py": [
                "no-lifecycle-registration",
                "utility-declared-without-importer",
            ]
        }, f"a bare utility claim was accepted as reachability: {result}"

    def test_regression_issue_1612_two_utility_hooks_cannot_vouch_for_each_other(
        self, tmp_path
    ):
        """REFUSING ARM. A cycle grounds nothing.

        Two ``utility``-declared gates that invoke each other were BOTH
        permitted — measured ``{}`` on this exact fixture — while neither was
        reachable from any lifecycle event. That is ``51743c87`` with two files
        instead of one sidecar: each hook's reachability claim is backed only
        by the other hook's equally unbacked claim.
        """
        root, hooks = self._repo(tmp_path)
        for this, other in (("gate_a", "gate_b"), ("gate_b", "gate_a")):
            self._hook(
                hooks,
                f"{this}.py",
                "import subprocess, sys\n"
                "def main():\n"
                f'    subprocess.run(["python3", "hooks/{other}.py"])\n'
                "    sys.exit(2)\n",
                sidecar_type="utility",
            )
        result = unreachable_refusers(hooks, root)
        assert sorted(result) == ["gate_a.py", "gate_b.py"], (
            f"two utility gates that invoke ONLY each other were accepted as "
            f"reachable. Neither is registered on any lifecycle event, so "
            f"nothing starts the chain and neither can ever run. Got: {result}"
        )

    def test_permitting_arm_a_chain_that_reaches_a_registered_hook_is_grounded(
        self, tmp_path
    ):
        """PERMITTING ARM. A real chain, two links long, must be accepted.

        ``registered.py`` is on a lifecycle event and invokes ``middle.py``,
        which invokes ``leaf.py``. Every link is a hook and neither utility hook
        is registered — the only structural difference from the cycle above is
        that this chain TERMINATES somewhere that actually runs. A grounding
        rule that rejected it would refuse the sanctioned utility route
        outright, which is why the two arms are written against the same shape.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "registered.py",
            "import subprocess, sys\n"
            "def main():\n"
            '    subprocess.run(["python3", "hooks/middle.py"])\n'
            "    sys.exit(2)\n",
        )
        self._hook(
            hooks,
            "middle.py",
            "import subprocess, sys\n"
            "def main():\n"
            '    subprocess.run(["python3", "hooks/leaf.py"])\n'
            "    sys.exit(2)\n",
            sidecar_type="utility",
        )
        self._hook(
            hooks,
            "leaf.py",
            "import sys\ndef main():\n    sys.exit(2)\n",
            sidecar_type="utility",
        )
        self._register(root, "registered.py")

        assert unreachable_refusers(hooks, root) == {}, (
            "a two-link chain terminating at a registered hook was flagged. "
            "The grounding rule refuses the sanctioned utility route, so a "
            "correctly-wired helper reads as unreachable."
        )

    #: Shell lines that really do EXECUTE a hook. The first is this repo's own
    #: ``templates/settings.default.json`` shape; every one of these was a MISS
    #: before the pattern was widened, which under-reported reachability.
    _SHELL_INVOCATION_SHAPES = (
        'python3 "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}'
        '/.claude/hooks/synthetic_utility_gate.py"',
        '"$PYTHON" plugins/autonomous-dev/hooks/synthetic_utility_gate.py',
        '"$HOOKS_DIR/synthetic_utility_gate.py" || exit 1',
        "plugins/autonomous-dev/hooks/synthetic_utility_gate.py --check",
        "if plugins/autonomous-dev/hooks/synthetic_utility_gate.py; then\n  :\nfi",
        "uv run plugins/autonomous-dev/hooks/synthetic_utility_gate.py",
        "python3 -m synthetic_utility_gate",
        "env python3 hooks/synthetic_utility_gate.py",
        "exec python3 ./hooks/synthetic_utility_gate.py",
    )

    #: Shell lines that NAME a hook without running it. ``[ -f ... ]`` is the
    #: measured live instance (``scripts/test-autonomous-workflow.sh:86``).
    _SHELL_MENTION_SHAPES = (
        'assert_true "hook exists" "[ -f plugins/autonomous-dev/hooks/'
        'synthetic_utility_gate.py ]"',
        'echo "see hooks/synthetic_utility_gate.py for details"',
        "grep -n main plugins/autonomous-dev/hooks/synthetic_utility_gate.py",
        "# python3 plugins/autonomous-dev/hooks/synthetic_utility_gate.py",
        'HOOK_NAME="synthetic_utility_gate.py"',
        'echo "$MSG hooks/synthetic_utility_gate.py"',
        "cp hooks/synthetic_utility_gate.py /tmp/",
    )

    def _shell_repo(self, tmp_path: Path, line: str):
        """Build a repo whose only consumer is one shell script line."""
        root, hooks = self._repo(tmp_path)
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "synthetic_checks.sh").write_text(
            "#!/usr/bin/env bash\n" + line + "\n", encoding="utf-8"
        )
        self._hook(
            hooks,
            "synthetic_utility_gate.py",
            "import sys\ndef main():\n    sys.exit(2)\n",
            sidecar_type="utility",
        )
        return root, hooks

    @pytest.mark.parametrize("line", _SHELL_INVOCATION_SHAPES)
    def test_regression_issue_1612_real_shell_invocation_shapes_are_accepted(
        self, tmp_path, line
    ):
        """PERMITTING ARM. The narrow pattern missed shapes that really run.

        These fail SAFE — a missed invoker under-reports reachability and
        produces a loud false red rather than a silent green — but the module
        presented the narrowing as settled when it was not. The first shape is
        this repo's OWN template command, which the old pattern could not see
        because ``(``, ``)`` and spaces were excluded from the path character
        class and ``${...:-$(...)}`` contains all three.
        """
        root, hooks = self._shell_repo(tmp_path, line)
        assert unreachable_refusers(hooks, root) == {}, (
            f"a shell line that EXECUTES the hook was not accepted as an "
            f"invoker: {line!r}. The hook reads as unreachable while something "
            f"runs it on every session."
        )

    @pytest.mark.parametrize("line", _SHELL_MENTION_SHAPES)
    def test_shell_mention_shapes_are_still_refused(self, tmp_path, line):
        """REFUSING ARM, paired with the widening above.

        Widening a pattern is only safe while the non-invoking shapes still
        miss. ``[ -f ... ]`` is the measured live instance; the rest are the
        neighbouring shapes a looser pattern would sweep up — a path as an
        argument to ``echo``, ``grep`` or ``cp``, a bare assignment, and a
        commented-out command.
        """
        root, hooks = self._shell_repo(tmp_path, line)
        assert set(unreachable_refusers(hooks, root)) == {
            "synthetic_utility_gate.py"
        }, (
            f"a shell line that only NAMES the hook was accepted as an "
            f"invocation: {line!r}. That is presence-as-proof — the file being "
            f"mentioned says nothing about anything running it."
        )

    def test_source_is_not_an_invocation_of_a_python_hook(self, tmp_path):
        """``source gate.py`` does not run Python; it was accepted, and is not.

        The shell reads a ``source``d file as SHELL. Counting it as an invoker
        of a ``.py`` hook accepted a shape that cannot execute the hook at all.
        """
        root, hooks = self._shell_repo(
            tmp_path, "source plugins/autonomous-dev/hooks/synthetic_utility_gate.py"
        )
        assert set(unreachable_refusers(hooks, root)) == {
            "synthetic_utility_gate.py"
        }, (
            "`source` on a .py hook was accepted as an invocation. The shell "
            "would parse it as shell script, so it does not run the hook."
        )

    def test_shell_existence_check_is_not_an_invocation(self, tmp_path):
        """The measured false positive: ``[ -f hook.py ]`` is not reachability.

        ``scripts/test-autonomous-workflow.sh:86`` checks that
        ``enforce_tdd.py`` EXISTS. A loose shell rule counted that as an
        invoker, which is presence-as-proof one level down. Paired with the
        control below so a green here means the rule discriminates rather than
        that the shell arm is inert.
        """
        root, hooks = self._repo(tmp_path)
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "synthetic_checks.sh").write_text(
            "#!/usr/bin/env bash\n"
            'assert_true "hook exists" "[ -f plugins/autonomous-dev/hooks/'
            'synthetic_utility_gate.py ]"\n',
            encoding="utf-8",
        )
        self._hook(
            hooks,
            "synthetic_utility_gate.py",
            "import sys\n"
            "def main():\n"
            "    sys.exit(2)\n",
            sidecar_type="utility",
        )
        assert set(unreachable_refusers(hooks, root)) == {
            "synthetic_utility_gate.py"
        }, (
            "an `[ -f ... ]` existence check was accepted as an invocation. "
            "That is presence-as-proof: the file being on disk says nothing "
            "about anything running it."
        )

        (scripts / "synthetic_checks.sh").write_text(
            "#!/usr/bin/env bash\n"
            "python3 plugins/autonomous-dev/hooks/synthetic_utility_gate.py\n",
            encoding="utf-8",
        )
        assert unreachable_refusers(hooks, root) == {}, (
            "CONTROL: the same file under an interpreter prefix must be "
            "accepted. If this fails too, the shell arm rejects everything and "
            "the assertion above proves nothing."
        )

    def test_empty_surface_enumeration_raises_from_the_rule_itself(self, tmp_path):
        """The hard error must propagate through THE RULE, not just the helper.

        A guard whose helper raises but whose rule swallows it would still
        report a vacuous clean answer.
        """
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "synthetic_gate.py").write_text(
            'print({"permissionDecision": "deny"})\n', encoding="utf-8"
        )
        with pytest.raises(RuntimeError, match="Zero registration surfaces"):
            unreachable_refusers(hooks, tmp_path)

    #: Shapes that NAME a hook under a lifecycle-event key without running it.
    #: The first is the reviewer's measured exploit against the live
    #: ``templates/settings.default.json``: inserting it took the flagged set
    #: 5 -> 4 with nothing invoking the hook.
    _NON_INVOKING_SHAPES = {
        "prose _note": {
            "_note": "TODO(#1612): decide whether synthetic_unwired_gate.py belongs here"
        },
        "_comment field": {"_comment": "synthetic_unwired_gate.py was here"},
        "matcher value": {"matcher": "synthetic_unwired_gate.py", "hooks": []},
        "disabled, commented-out command": {
            "matcher": "*",
            "enabled": False,
            "hooks": [{"command": "# python3 .claude/hooks/synthetic_unwired_gate.py"}],
        },
        "typed but commented-out command": {
            "matcher": "*",
            "hooks": [
                {
                    "type": "command",
                    "command": "# python3 .claude/hooks/synthetic_unwired_gate.py",
                }
            ],
        },
        "command entry with no type": {
            "matcher": "*",
            "hooks": [{"command": "python3 .claude/hooks/synthetic_unwired_gate.py"}],
        },
    }

    @pytest.mark.parametrize("shape_name", sorted(_NON_INVOKING_SHAPES))
    def test_regression_issue_1612_a_mention_under_a_lifecycle_key_is_not_a_registration(
        self, tmp_path, shape_name
    ):
        """REFUSING ARM. Prose under an event key must not clear a hook.

        The reviewer's BLOCKING-1 finding, as BEHAVIOUR rather than as a regex
        assertion: collecting every string leaf under a lifecycle-event key let
        a one-line JSON note confer a registration. Measured against the live
        ``templates/settings.default.json`` — inserting
        ``{"_note": "TODO(#1612): decide whether enforce_tdd.py belongs here"}``
        took the flagged set from 5 to 4 with nothing invoking the hook.

        The failure that mattered was one level up: with the hook cleared,
        ``test_pinned_entries_are_still_genuinely_unreachable`` fires STALE, a
        maintainer deletes the pin entry and lowers the ceiling, and every arm
        goes green over a hook still invoked by nothing. That reads as coverage.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "synthetic_unwired_gate.py",
            "import json\n"
            "def main():\n"
            '    print(json.dumps({"decision": "ask", "reason": "nope"}))\n',
        )
        self._inject_under_event(root, self._NON_INVOKING_SHAPES[shape_name])

        result = unreachable_refusers(hooks, root)
        assert set(result) == {"synthetic_unwired_gate.py"}, (
            f"the {shape_name!r} shape CLEARED an unregistered gate. It names "
            f"the hook under a lifecycle-event key but invokes nothing, so the "
            f"guard is satisfiable by one line of JSON prose — the same "
            f"one-line-edit defect it exists to police, one level up. "
            f"Got: {result}"
        )

    def test_permitting_control_a_real_command_entry_still_registers(self, tmp_path):
        """PERMITTING ARM for the shape above, in the same fixture.

        Identical hook and identical surface; the ONLY difference is that the
        mention becomes a ``{"type": "command", "command": ...}`` entry. Without
        this the refusing arms above would pass just as well against an
        extractor that had stopped resolving anything at all.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "synthetic_unwired_gate.py",
            "import json\n"
            "def main():\n"
            '    print(json.dumps({"decision": "ask", "reason": "nope"}))\n',
        )
        for shape in self._NON_INVOKING_SHAPES.values():
            self._inject_under_event(root, shape)
        self._register(root, "synthetic_unwired_gate.py")

        assert unreachable_refusers(hooks, root) == {}, (
            "a gate with a real command entry was flagged as unreachable even "
            "though the extractor was handed that entry alongside every "
            "non-invoking shape. The registration search refuses the "
            "legitimate case."
        )

    def test_hook_list_is_derived_from_disk_not_hardcoded(self, tmp_path):
        """A hook the guard has never heard of must still be classified.

        A hardcoded list inherits the defect it polices: it can only ever find
        the hooks someone remembered to add.
        """
        root, hooks = self._repo(tmp_path)
        self._hook(
            hooks,
            "zzz_invented_yesterday.py",
            'print({"permissionDecision": "deny", "permissionDecisionReason": "x"})\n',
        )
        assert set(unreachable_refusers(hooks, root)) == {
            "zzz_invented_yesterday.py"
        }, (
            "a hook name that appears nowhere in this module was not "
            "classified. The corpus is not being derived from disk."
        )


class TestCeilingIsNotATautology:
    """The ceiling must fail on GROWTH, not merely on disagreement.

    ``REACHABILITY_CEILING == len(PINNED_UNREACHABLE)`` alone is unfalsifiable
    from inside this file: both operands are constants here, so an edit that
    adds a pinned entry AND bumps the ceiling moves them together and nothing
    fires. That bypass was measured green against the #1588 ceiling before a
    literal was added beside the equality; this class reproduces its harness so
    the same mistake cannot be made twice.

    The arms are driven over MUTATED copies of this module in a subprocess,
    because a constant-versus-constant assertion cannot be falsified in-process.
    The harness gets its own control: the unmutated copy must pass, and the
    selection must report exactly one test — a ``-k`` that matches nothing exits
    0 and would read as green on every arm.

    Every anchor is DERIVED from the module's own constants rather than
    hardcoded. Hardcoding them made the harness break on the ratchet ADVANCING:
    simulating #1612's policy half (one hook wired, pin 5 -> 4, ceiling 5 -> 4)
    produced ``3 failed, 1 passed`` with messages demanding a re-anchor, so
    doing the right thing turned the file red — pressure to leave hooks pinned,
    which is the exact failure the permitting arm below was written to prevent.
    """

    #: Selection used by the future-state arm. Every arm of this class EXCEPT
    #: that arm itself — see its docstring for why the self-exclusion is what
    #: bounds the recursion.
    _FUTURE_STATE_SELECTION = (
        "TestCeilingIsNotATautology and not survives_the_ratchet_advancing"
    )

    @staticmethod
    def _source() -> str:
        return Path(__file__).resolve().read_text(encoding="utf-8")

    @classmethod
    def _substitute(cls, source: str, anchor: str, replacement: str) -> str:
        """Replace ``anchor`` exactly once, refusing a no-op or an ambiguity."""
        count = source.count(anchor)
        assert count == 1, (
            f"mutation anchor {anchor!r} appears {count} times in this module, "
            f"not once. The harness would mutate nothing (or the wrong site) "
            f"and report a green that means nothing. Re-anchor it."
        )
        return source.replace(anchor, replacement)

    @staticmethod
    def _run_ceiling_test(
        tmp_path: Path, source: str
    ) -> "subprocess.CompletedProcess":
        """Run only ``test_reachability_pin_has_a_ceiling`` over ``source``.

        Restricted with ``-k`` because the ceiling test reads nothing but the
        two constants: the copy runs out of tree, so the corpus-reading tests in
        this module would fail for an unrelated reason and blur the signal.
        ``PYTHONPATH`` points back at the real test directory so the mutant can
        still import the #1588 instruments at module scope.
        """
        import os

        mutant = tmp_path / "test_reachability_ceiling_mutant.py"
        mutant.write_text(source, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [_THIS_DIR] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(mutant),
                "-k",
                "test_reachability_pin_has_a_ceiling",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:randomly",
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=env,
            timeout=180,
        )

    def test_control_unmutated_copy_of_this_module_passes(self, tmp_path):
        """NEGATIVE CONTROL for the harness. Without a mutation it must be GREEN.

        Without this, a red from the growth mutant below could just as easily
        mean "a subprocess pytest cannot import this module at all".
        """
        result = self._run_ceiling_test(tmp_path, self._source())
        assert result.returncode == 0, (
            f"the UNMUTATED ceiling test failed in the harness, so every other "
            f"result here is uninterpretable.\n{result.stdout}\n{result.stderr}"
        )
        assert "1 passed" in result.stdout, (
            f"the harness selected {result.stdout!r} — expected exactly one "
            f"test. A `-k` that matches nothing exits 0 and would read as a "
            f"pass on every arm."
        )

    def test_regression_issue_1612_growing_the_pin_and_the_ceiling_together_fails(
        self, tmp_path
    ):
        """THE REPRODUCER, and the refusing arm. Growth must be RED.

        Grow ``PINNED_UNREACHABLE`` past the reviewed high-water mark and raise
        ``REACHABILITY_CEILING`` to match in the same edit — the shape that lets
        the next failing hook be pinned instead of wired up. The mutant's added
        entries name no live hook, so this exercises the ceiling itself rather
        than the corpus detector.

        The target is derived from ``CEILING_HIGH_WATER_MARK`` rather than from
        the current ceiling. Deriving it from the ceiling made the arm go green
        the moment the ratchet advanced: at ceiling 4 with the mark at 5, a
        one-entry growth lands on 5 and satisfies ``5 <= 5``. At today's values
        this is the same one-entry mutation it has always been.
        """
        target = CEILING_HIGH_WATER_MARK + 1
        source = self._source()
        anchor, replacement = _pin_add_mutation(
            source, PINNED_UNREACHABLE, target - len(PINNED_UNREACHABLE)
        )
        source = self._substitute(source, anchor, replacement)
        source = self._substitute(
            source,
            _ceiling_anchor(REACHABILITY_CEILING),
            _ceiling_anchor(target),
        )

        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode != 0, (
            f"PINNED_UNREACHABLE grew to {target} with the ceiling raised to "
            f"{target} to match, and the ceiling test still PASSED. The escape "
            f"hatch has no ceiling: the next hook that fails this guard can be "
            f"pinned instead of wired up, by a two-constant edit that no "
            f"assertion sees.\n{result.stdout}"
        )
        assert "REACHABILITY_CEILING" in result.stdout, (
            f"the mutant failed for some reason other than the ceiling "
            f"assertion, so this proves nothing about it.\n{result.stdout}"
        )

    @pytest.mark.skipif(
        not PINNED_UNREACHABLE,
        reason=(
            "PINNED_UNREACHABLE is empty: #1612 is fully resolved and there is "
            "no entry left to drop. Structurally inapplicable, not a hidden "
            "failure — the refusing arm above still runs in this state."
        ),
    )
    def test_shrinking_the_pin_and_the_ceiling_together_is_permitted(self, tmp_path):
        """THE PERMITTING ARM. Lowering is the ratchet advancing — never blocked.

        Deliberately the opposite direction from the reproducer. A ceiling
        pinned with ``==`` to a literal would catch the growth above and then
        block the very outcome #1612's other half is supposed to produce,
        converting the fix into a new defect.
        """
        source = self._source()
        anchor, replacement = _pin_drop_mutation(source, PINNED_UNREACHABLE)
        source = self._substitute(source, anchor, replacement)
        source = self._substitute(
            source,
            _ceiling_anchor(REACHABILITY_CEILING),
            _ceiling_anchor(REACHABILITY_CEILING - 1),
        )
        # CEILING_HIGH_WATER_MARK is DELIBERATELY left alone here. Lowering it
        # is recommended and zeroes the residual headroom, but the sanctioned
        # edit must be green without it — requiring a third constant edit to
        # avoid a red is pressure on exactly the action this module wants.

        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode == 0, (
            "a hook was wired up and removed from PINNED_UNREACHABLE with the "
            "ceiling lowered to match, and the ceiling test refused it. "
            "Lowering is the ratchet advancing and needs no justification; "
            "blocking it creates pressure to leave fixed hooks pinned.\n"
            f"{result.stdout}\n{result.stderr}"
        )

    def test_raising_the_ceiling_alone_still_fails(self, tmp_path):
        """The anti-slack arm: a ceiling above the pin is a pre-authorisation."""
        raised = CEILING_HIGH_WATER_MARK + 1
        source = self._substitute(
            self._source(),
            _ceiling_anchor(REACHABILITY_CEILING),
            _ceiling_anchor(raised),
        )
        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode != 0, (
            f"REACHABILITY_CEILING was raised to {raised} while the pin stayed "
            f"at {len(PINNED_UNREACHABLE)} and nothing fired. That is a "
            f"pre-authorised exemption.\n{result.stdout}"
        )
        assert "CEILING_HIGH_WATER_MARK" in result.stdout or (
            "REACHABILITY_CEILING" in result.stdout
        ), (
            f"the mutant failed for some reason other than a ceiling "
            f"assertion, so this proves nothing about it.\n{result.stdout}"
        )

    @pytest.mark.skipif(
        not PINNED_UNREACHABLE,
        reason=(
            "PINNED_UNREACHABLE is empty: the future state this simulates has "
            "already arrived. Structurally inapplicable, not a hidden failure."
        ),
    )
    def test_regression_issue_1612_the_harness_survives_the_ratchet_advancing(
        self, tmp_path
    ):
        """THE BLOCKING-3 REPRODUCER. Doing the right thing must not turn it red.

        Simulate #1612's policy half landing — one hook wired, the pin and both
        ceiling constants lowered by one — and run THIS ENTIRE CLASS over that
        future state. With the anchors hardcoded it reported ``3 failed, 1
        passed``, every message demanding a re-anchor, which is pressure to
        leave hooks pinned rather than fix them: the exact failure the
        permitting arm above exists to prevent, reproduced one level up.

        Nested subprocesses, so it is the slowest test here. It earns that by
        being the only arm that watches the harness itself under the edit the
        rest of the module is trying to encourage.

        THIS test is excluded from the inner selection. Without that exclusion
        the inner copy runs it again against a pin one shorter, and so on until
        the pin empties — measured at 110s for a five-entry pin and growing
        with every entry. The exclusion is what keeps the recursion one level
        deep; ``test_the_future_state_selection_excludes_only_this_arm`` proves
        the ``-k`` still selects the other arms rather than nothing.
        """
        import os

        source = self._source()
        anchor, replacement = _pin_drop_mutation(source, PINNED_UNREACHABLE)
        source = self._substitute(source, anchor, replacement)
        source = self._substitute(
            source,
            _ceiling_anchor(REACHABILITY_CEILING),
            _ceiling_anchor(REACHABILITY_CEILING - 1),
        )
        source = self._substitute(
            source,
            _high_water_anchor(CEILING_HIGH_WATER_MARK),
            _high_water_anchor(CEILING_HIGH_WATER_MARK - 1),
        )

        future = tmp_path / "test_reachability_future_state.py"
        future.write_text(source, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [_THIS_DIR] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(future),
                "-k",
                self._FUTURE_STATE_SELECTION,
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:randomly",
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=env,
            timeout=600,
        )
        assert result.returncode == 0, (
            f"the mutation harness went RED against the future state it is "
            f"supposed to encourage (pin "
            f"{len(PINNED_UNREACHABLE) - 1}, ceiling "
            f"{REACHABILITY_CEILING - 1}). A maintainer who wires a hook up and "
            f"lowers the pin correctly is met with failures telling them to "
            f"re-anchor a test harness. That is pressure to leave hooks "
            f"pinned.\n{result.stdout}\n{result.stderr}"
        )
        assert " passed" in result.stdout and "failed" not in result.stdout, (
            f"the future-state run did not report a clean pass: "
            f"{result.stdout!r}"
        )

    def test_the_future_state_selection_excludes_only_this_arm(self):
        """The recursion bound must not silently select NOTHING.

        A ``-k`` that matches no test exits 0, so the arm above would report a
        green future state without running a single assertion in it. This
        collects against the REAL file and pins the selected set to every other
        arm of the class.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(Path(__file__).resolve()),
                "-k",
                self._FUTURE_STATE_SELECTION,
                "--collect-only",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:randomly",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=180,
        )
        # pytest renders ``--collect-only -q`` as bare nodeids by default and as
        # a ``<Function name>`` tree under this repo's ini settings. Parse both
        # so the control does not go vacuous on a pytest or ini change.
        selected = {
            line.rsplit("::", 1)[-1].strip()
            for line in result.stdout.splitlines()
            if "::" in line and "TestCeilingIsNotATautology" in line
        } | set(re.findall(r"<Function (test_\w+)>", result.stdout))
        expected = {
            name
            for name in vars(type(self))
            if name.startswith("test_")
        } - {"test_regression_issue_1612_the_harness_survives_the_ratchet_advancing"}
        assert selected == expected, (
            f"the future-state selection resolves to {sorted(selected)}, not "
            f"{sorted(expected)}. If it collapsed to the empty set the arm "
            f"above would exit 0 without running anything and read as a green "
            f"future state.\n{result.stdout}"
        )


class TestLibraryInstrumentPremises:
    """Verify the library search before trusting one cell of its output.

    A probe that returns zero is not evidence of zero. Every arm here
    gives the walk a positive control (an input it is KNOWN to reach) and
    a negative control (an input it is KNOWN to refuse), because the
    failure mode this whole module exists to detect looks EXACTLY like a
    clean result.
    """

    def test_library_corpus_is_populated_and_derived_from_disk(self):
        """A zero-module corpus makes every verdict below vacuous."""
        corpus = _library_corpus()
        assert len(corpus) >= 150, (
            f"Only {len(corpus)} library module(s) found under {LIB_DIR}. "
            f"The plugin ships well over a hundred; a collapse means "
            f"LIBRARY_CORPUS_GLOBS no longer reaches lib/ and every "
            f"'unreached' verdict is meaningless rather than alarming."
        )
        assert "prior_art_search.py" in corpus, (
            "premise: the #1669 module that proved this gap is still in "
            "the corpus. Without it the worked example below is fiction."
        )
        # NOT ``assert path.is_file()``: ``_library_paths`` already
        # filters on ``is_file()``, so that assertion cannot fail and
        # reads as coverage over a check that is structurally guaranteed.
        # These CAN fail — the key is the join between the pin and disk,
        # and a key that no longer round-trips silently orphans a pin
        # entry.
        lib_root = LIB_DIR.resolve()
        for key, path in corpus.items():
            assert path.resolve().relative_to(lib_root).as_posix() == key, (
                f"corpus key {key!r} does not round-trip to its path "
                f"{path}. PINNED_UNREACHED_LIBRARY is keyed on this "
                f"string; a changed keying scheme makes every pin entry "
                f"stale at once."
            )
            assert path.suffix == ".py", f"{key} is not Python: {path}"
            assert path.name != "__init__.py", (
                f"{key} is a package initialiser. Twenty of them share "
                f"the name, so including them collides the corpus."
            )

    def test_empty_library_corpus_is_a_hard_error(self, tmp_path):
        """Zero modules must RAISE, never silently pass."""
        with pytest.raises(RuntimeError, match="Zero library modules"):
            unreached_library_modules(tmp_path, use_cache=False)

    def test_consumer_node_graph_is_populated(self):
        """An empty node graph would make every module read as unreached."""
        nodes = _consumer_nodes()
        assert len(nodes) >= 200, (
            f"Only {len(nodes)} consumer node(s) resolved. The walk would "
            f"ground almost nothing and flag almost everything."
        )

    def test_content_discovery_finds_surfaces_a_filename_glob_misses(self):
        """The measured reason surfaces are discovered by CONTENT.

        A ``settings*.json`` glob finds five of the seven tracked binding
        surfaces here. The two it misses carry real bindings, and one of
        them (``global_settings_template.json``) holds more command
        entries than any single template. Every number below is MEASURED
        on the live tree, so this fails if either file is renamed into
        (or out of) glob range.
        """
        surfaces = _binding_surfaces()
        names = {p.name for p in surfaces}
        assert len(surfaces) >= 6, (
            f"only {len(surfaces)} binding surface(s) discovered: "
            f"{sorted(names)}. The content walk has stopped resolving."
        )

        glob_visible = {n for n in names if n.startswith("settings")}
        invisible = names - glob_visible
        assert invisible >= {
            "global_settings_template.json",
            "default-settings.json",
        }, (
            f"the surfaces invisible to a settings*.json glob are "
            f"{sorted(invisible)}. Both global_settings_template.json and "
            f".claude-plugin/default-settings.json carry bindings and "
            f"neither matches such a glob — that is WHY discovery is by "
            f"content. If they became glob-visible, re-measure before "
            f"weakening the rule."
        )

        per_surface = {p.name: _bound_stems([p]) for p in surfaces}
        everything = set().union(*per_surface.values())
        only_outside_glob = everything - set().union(
            *[v for k, v in per_surface.items() if k in glob_visible]
        )
        assert only_outside_glob, (
            f"no hook is bound EXCLUSIVELY outside a settings*.json glob, "
            f"so content discovery currently costs nothing and this arm "
            f"is inert. Bound stems: {sorted(everything)}"
        )
        assert {"auto_fix_docs", "enforce_tier_distribution"} <= (
            only_outside_glob
        ), (
            f"expected auto_fix_docs (bound only in default-settings.json) "
            f"and enforce_tier_distribution (bound only in "
            f"global_settings_template.json) among the glob-invisible "
            f"bindings; measured {sorted(only_outside_glob)}"
        )

    def test_positive_control_the_reference_extractor_resolves_a_real_import(self):
        """The walk's Python arm must FIND a genuine import.

        Without an input it is KNOWN to resolve, "no consumer found" is
        indistinguishable from "the extractor is broken", and every
        UNKNOWN verdict in this file is uninterpretable.
        """
        source = "from hook_telemetry import record\nimport json\n"
        assert "hook_telemetry" in _python_referenced_stems(source)
        assert "json" in _python_referenced_stems(source)

        invocation = (
            "import subprocess\n"
            'subprocess.run(["python3", "plugins/x/hooks/some_gate.py"])\n'
        )
        assert "some_gate" in _python_referenced_stems(invocation), (
            "the invocation-shaped-call arm resolved nothing; 28 live "
            "modules are reached by no import at all and would read as "
            "orphans"
        )

    def test_negative_control_a_docstring_mention_is_not_a_consumer(self):
        """MENTION is not CONSUMPTION — on two live files, not fixtures.

        A negative control of a DIFFERENT SHAPE from the reproducer.
        ``lib/secret_patterns.py:6`` lists
        ``- lib/active_security_scanner.py`` as a docstring bullet, and
        ``lib/semantic_gate.py:21`` states that it deliberately does NOT
        import ``intent_classifier``. A filename-level grep reads the
        first as a dependency and the second as its own refutation. These
        are the two files ``test_anthropic_client_ratchet`` already pins
        for exactly this, reused rather than re-invented.
        """
        secret_patterns = LIB_DIR / "secret_patterns.py"
        semantic_gate = LIB_DIR / "semantic_gate.py"
        assert secret_patterns.is_file() and semantic_gate.is_file(), (
            "premise: both negative-control modules still exist"
        )

        patterns_text = secret_patterns.read_text(encoding="utf-8")
        gate_text = semantic_gate.read_text(encoding="utf-8")
        assert "active_security_scanner" in patterns_text, (
            "premise: secret_patterns.py still NAMES active_security_"
            "scanner in prose, so counting the mention would still change "
            "the answer. If it was reworded, pick another instance."
        )
        assert "intent_classifier" in gate_text, (
            "premise: semantic_gate.py still names intent_classifier in "
            "prose (it says it deliberately does NOT import it)"
        )

        assert "active_security_scanner" not in _python_referenced_stems(
            patterns_text
        ), (
            "a docstring bullet naming lib/active_security_scanner.py was "
            "resolved as a consumer. That is presence-as-proof: an AST "
            "instrument exists precisely so prose cannot ground a module."
        )
        assert "intent_classifier" not in _python_referenced_stems(gate_text), (
            "semantic_gate.py's statement that it does NOT import "
            "intent_classifier was resolved as an import"
        )

        result = library_reachability()
        assert "active_security_scanner.py" in result.unknown, (
            "active_security_scanner.py is REACHED, which means something "
            "other than the docstring bullet now grounds it — good, but "
            "this control no longer discriminates. Pick another instance."
        )

    def test_positive_and_negative_controls_for_the_embedded_python_carrier(self):
        """The markdown carrier, on the live file, both ways.

        ``commands/implement.md`` carries ``search_prior_art``'s only
        production consumer inside a ``python3 -c`` script in a ```bash
        fence. Serena ``find_referencing_symbols`` returns exactly one hit
        for that symbol — the module's own ``_main`` — because no LSP
        reads into a markdown fence. THIS instrument is grep-for-the-
        carrier plus AST-for-the-contents, and the disagreement between
        the two is the finding, not something to resolve quietly.
        """
        implement = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / (
            "implement.md"
        )
        assert implement.is_file(), "premise: the command file still exists"
        text = implement.read_text(encoding="utf-8")

        sources = _embedded_python_sources(text)
        assert sources, (
            "no embedded Python was recovered from implement.md at all. "
            "The carrier extractor is inert and every module reached only "
            "through a markdown fence reads as an orphan."
        )
        assert any(
            "prior_art_search" in _python_referenced_stems(s) for s in sources
        ), (
            f"the wired consumer at implement.md:1001 "
            f"(`from prior_art_search import search_prior_art`, inside a "
            f"python3 -c script in a bash fence) was not recovered. "
            f"Recovered {len(sources)} snippet(s)."
        )

        # AND the live path must agree. Flagged by
        # ``test_every_markdown_control_consults_the_live_call_path`` when
        # this was carrier-only: a control that consults one arm of the
        # dispatch and reports on the whole is the round-1 defect, and
        # this test was the last instance of it in the file. Asserting
        # both is also simply stronger — it proves the carrier's output
        # actually survives into the walk rather than being recovered and
        # then dropped.
        assert "prior_art_search" in _references_in(implement), (
            f"the carrier recovered the consumer but THE LIVE CALL PATH "
            f"did not report it. The snippet is being extracted and then "
            f"lost — which would leave prior_art_search.py UNKNOWN while "
            f"this control stayed green. Recovered "
            f"{len(sources)} snippet(s)."
        )

    #: Markdown NARRATIVE shapes that NAME a module without running it.
    #: Every one is drawn from a live line that was grounding modules
    #: before the narrative rule existed; see
    #: ``_SHELL_INVOCATION_INTERPRETED`` for the four sources.
    _MARKDOWN_MENTION_SHAPES = {
        "table row with a glob": (
            "| Schema/model files (`**/schemas/*.py`, `**/synthetic_orphan.py`)"
            " | Schema quality | reviewed |\n"
        ),
        "backticked path in a sentence": (
            "They are declared in `plugins/autonomous-dev/lib/"
            "synthetic_orphan.py`. They are intentional and reviewed.\n"
        ),
        "path.py::symbol citation": (
            "The lifecycle helper `plugins/autonomous-dev/lib/"
            "synthetic_orphan.py::open_or_supersede` is the only "
            "sanctioned path for this.\n"
        ),
        "bare path on its own line": (
            "plugins/autonomous-dev/lib/synthetic_orphan.py\n"
        ),
        "backticked path in parentheses": (
            "(see `plugins/autonomous-dev/lib/synthetic_orphan.py`).\n"
        ),
        "prose naming the file twice": (
            "See `synthetic_orphan.py` for the mechanism, and read\n"
            "plugins/autonomous-dev/lib/synthetic_orphan.py before editing.\n"
        ),
    }

    #: Markdown shapes that really DO run the module. Every one must
    #: still resolve, or the fix above would "pass" by making markdown
    #: ground nothing at all — a different silent failure, and the one
    #: that would quietly re-orphan ``prior_art_search``.
    _MARKDOWN_INVOCATION_SHAPES = {
        "interpreter prefix in narrative": (
            "Run `python3 plugins/autonomous-dev/lib/synthetic_orphan.py "
            "--check` before continuing.\n"
        ),
        "bare path inside a fenced block": (
            "```bash\nplugins/autonomous-dev/lib/synthetic_orphan.py --check\n```\n"
        ),
        "interpreter prefix inside a fenced block": (
            "```bash\npython3 plugins/autonomous-dev/lib/synthetic_orphan.py\n```\n"
        ),
        "module form": ("Run `python3 -m synthetic_orphan` to rebuild.\n"),
        "python fence importing it": (
            "```python\nfrom synthetic_orphan import run\nprint(run())\n```\n"
        ),
    }

    @pytest.mark.parametrize("shape_name", sorted(_MARKDOWN_MENTION_SHAPES))
    def test_regression_issue_1698_markdown_narrative_mentions_ground_nothing(
        self, tmp_path, shape_name
    ):
        """REFUSING ARM, driven through THE LIVE CALL PATH.

        The first cut of this control asserted against
        ``_embedded_python_sources``, which the walk calls SECOND. For a
        ``.md`` file ``_references_in`` runs the shell arm FIRST, so the
        control exercised the half that does not over-credit and passed
        for the wrong reason. Measured on the exact prose below:
        ``_embedded_python_sources`` -> ``[]`` while ``_references_in``
        -> ``['prior_art_search']``.

        That is the defect this very module's ``_without`` docstring
        warns about — a check aimed at a sub-helper rather than the live
        call path — recurring one level down. Every shape here therefore
        goes through ``_references_in`` on a real file on disk.
        """
        note = tmp_path / "note.md"
        note.write_text(
            "# Notes\n\n" + self._MARKDOWN_MENTION_SHAPES[shape_name],
            encoding="utf-8",
        )
        assert "synthetic_orphan" not in _references_in(note), (
            f"the {shape_name!r} shape GROUNDED a module through the live "
            f"call path. Presence in narrative text is not proof of use — "
            f"the rule the rest of this file enforces by AST — and this "
            f"is the one surface where it was unenforced. Four such lines "
            f"were rooting 24 modules.\n"
            f"Content: "
            f"{self._MARKDOWN_MENTION_SHAPES[shape_name]!r}"
        )

    @pytest.mark.parametrize("shape_name", sorted(_MARKDOWN_INVOCATION_SHAPES))
    def test_permitting_arm_markdown_shapes_that_really_run_still_resolve(
        self, tmp_path, shape_name
    ):
        """PERMITTING ARM on the SAME entry point, and load-bearing.

        Without it the narrative fix could "pass" every refusing arm by
        making markdown ground nothing whatsoever — which would re-orphan
        ``prior_art_search`` and every other module whose only carrier is
        a command file. An explicit interpreter token in prose, and the
        full command grammar inside a fence, must both still resolve.
        """
        note = tmp_path / "note.md"
        note.write_text(
            "# Notes\n\n" + self._MARKDOWN_INVOCATION_SHAPES[shape_name],
            encoding="utf-8",
        )
        assert "synthetic_orphan" in _references_in(note), (
            f"the {shape_name!r} shape resolved NOTHING through the live "
            f"call path. Markdown now grounds nothing at all, which "
            f"refuses the sanctioned route and re-orphans every module "
            f"whose only consumer is a command file.\n"
            f"Content: "
            f"{self._MARKDOWN_INVOCATION_SHAPES[shape_name]!r}"
        )

    def test_regression_issue_1698_prose_does_not_ground_through_the_live_call_path(
        self, tmp_path
    ):
        """REGRESSION PIN for the exact fixture that shipped green.

        One fixture, one defect. Named for what it asserts rather than
        for the category — the CATEGORY guard is
        ``test_every_markdown_control_consults_the_live_call_path``, and
        spending the category name on a single-fixture pin is how a
        guard comes to read as coverage it has not earned.

        The pin itself is sound: for markdown, whatever
        ``_references_in`` concludes is the answer, and in round 1 the
        sub-helper was silent on this prose while the live path was not.
        """
        prose = (
            "# Notes\n\n"
            "See `prior_art_search.py` for the search mechanism, and read\n"
            "plugins/autonomous-dev/lib/prior_art_search.py before editing.\n"
        )
        note = tmp_path / "note.md"
        note.write_text(prose, encoding="utf-8")

        sub_helper = set()
        for source in _embedded_python_sources(prose):
            sub_helper |= _python_referenced_stems(source)
        live = _references_in(note)

        assert "prior_art_search" not in sub_helper, (
            "the sub-helper recovered a consumer from pure prose"
        )
        assert "prior_art_search" not in live, (
            f"THE LIVE CALL PATH grounded the module from prose while the "
            f"sub-helper did not: sub-helper={sorted(sub_helper)}, "
            f"live={sorted(live)}. A control aimed at the sub-helper "
            f"passes here and proves nothing — that is exactly how the "
            f"first cut of #1698 shipped."
        )

    #: Synthetic function sources for the category guard's REFUSING arm.
    #: A structural rule observed only over a corpus that already
    #: complies is unproven — the same standard this file holds every
    #: other guard to.
    _BYPASSING_CONTROL_SOURCES = {
        "the round-1 defect, verbatim in shape": (
            "def test_negative_control(self):\n"
            '    prose = "# Notes\\n\\nSee `x.py` for the mechanism."\n'
            "    assert not any(\n"
            '        "x" in _python_referenced_stems(s)\n'
            "        for s in _embedded_python_sources(prose)\n"
            "    )\n"
        ),
        "the recurrence one new test away": (
            "def test_negative_control_for_workflow_yaml(self):\n"
            '    text = "```yaml\\nrun: python3 lib/x.py\\n```\\n"\n'
            '    assert "x" not in _shell_invoked_stems(text)\n'
        ),
        "aimed at the fence walker": (
            "def test_fences_are_split_correctly(self):\n"
            '    blocks = _fenced_code_blocks("```bash\\nrun x.py\\n```")\n'
            "    assert len(blocks) == 1\n"
        ),
    }

    #: The SAME claims, made through a live entry point. Every one must
    #: be permitted, or the rule would simply ban consulting a sub-helper
    #: — which would be a different, and wrong, rule.
    _COMPLIANT_CONTROL_SOURCES = {
        "sub-helper plus the live path, compared": (
            "def test_negative_control(self, tmp_path):\n"
            '    prose = "# Notes\\n\\nSee `x.py` for the mechanism."\n'
            '    note = tmp_path / "n.md"\n'
            "    note.write_text(prose)\n"
            "    assert not _embedded_python_sources(prose)\n"
            '    assert "x" not in _references_in(note)\n'
        ),
        # SELF-CONTAINED on purpose: the closure can only resolve helpers
        # DEFINED in the source it is given, so the helper is included
        # here. Driving this arm without it flagged the fixture — which
        # is the permitting arm doing its job, and is why the five live
        # synthetic-corpus tests (whose ``_unknown`` helper IS in this
        # file) resolve correctly while an isolated snippet would not.
        "live path reached through a helper defined alongside": (
            "def _unknown(root):\n"
            "    return unreached_library_modules(root)\n"
            "\n"
            "def test_synthetic_corpus_arm(tmp_path):\n"
            '    assert not _shell_invoked_stems("noise")\n'
            "    assert _unknown(tmp_path) == []\n"
        ),
    }

    def test_every_markdown_control_consults_the_live_call_path(self):
        """THE CATEGORY GUARD. Not a second pin on one fixture.

        A test that reaches directly for a markdown carrier helper is
        reasoning about how markdown grounds a module, and must also
        reach a live entry point so the two answers are COMPARED. See
        ``controls_bypassing_the_live_call_path`` for why the trigger is
        a direct call and satisfaction is the call closure.
        """
        offenders = controls_bypassing_the_live_call_path(
            Path(__file__).resolve().read_text(encoding="utf-8")
        )
        assert not offenders, (
            f"test(s) consult a markdown carrier helper and NO live entry "
            f"point: {offenders}\n"
            f"Each carrier in {sorted(MARKDOWN_CARRIER_HELPERS)} sees only "
            f"PART of what the walk sees — for a .md file "
            f"``_references_in`` runs the shell arm FIRST and the embedded "
            f"-Python arm second, so a control aimed at one can be silent "
            f"while the walk is loud. That is exactly how the first cut of "
            f"#1698 shipped a green negative control over a live path that "
            f"was grounding 24 modules from prose.\n"
            f"Expected: also call one of "
            f"{sorted(LIVE_REACHABILITY_ENTRY_POINTS)} — directly or "
            f"through a helper defined in this file — and assert the two "
            f"agree. Consulting the sub-helper as well is fine and often "
            f"informative; consulting ONLY the sub-helper is not."
        )

    @pytest.mark.parametrize("shape_name", sorted(_BYPASSING_CONTROL_SOURCES))
    def test_the_category_guard_refuses_a_sub_helper_aimed_control(
        self, shape_name
    ):
        """REFUSING ARM. Watch the structural rule FIRE.

        The live corpus complies, so the arm above is green — and a
        structural check that has only ever been observed green over a
        compliant corpus is indistinguishable from one that matches
        nothing. Each source here is a control aimed at a sub-helper and
        at nothing live; the rule must name every one.
        """
        offenders = controls_bypassing_the_live_call_path(
            self._BYPASSING_CONTROL_SOURCES[shape_name]
        )
        assert offenders, (
            f"POSITIVE CONTROL FAILED: the {shape_name!r} source consults "
            f"a markdown carrier and no live entry point, and the rule did "
            f"NOT flag it. Its empty result over the live corpus is an "
            f"inert probe, not a clean file.\n"
            f"Source:\n{self._BYPASSING_CONTROL_SOURCES[shape_name]}"
        )

    @pytest.mark.parametrize("shape_name", sorted(_COMPLIANT_CONTROL_SOURCES))
    def test_the_category_guard_permits_a_control_that_consults_the_walk(
        self, shape_name
    ):
        """PERMITTING ARM. The rule must not simply ban sub-helpers.

        Both sources consult a carrier AND a live entry point — the
        second reaching it through a class helper, which is why
        satisfaction uses the call closure. A rule that flagged these
        would pass every refusing arm above while forbidding the correct
        pattern, and the cheapest way to satisfy it would be to delete
        the sub-helper assertion, losing the comparison that makes these
        controls worth anything.
        """
        assert (
            controls_bypassing_the_live_call_path(
                self._COMPLIANT_CONTROL_SOURCES[shape_name]
            )
            == []
        ), (
            f"NEGATIVE CONTROL FAILED: the {shape_name!r} source consults "
            f"a live entry point and was still flagged, so the rule "
            f"forbids the correct pattern and its positive results above "
            f"mean nothing.\n"
            f"Source:\n{self._COMPLIANT_CONTROL_SOURCES[shape_name]}"
        )

    def test_the_serena_grep_disagreement_is_measured_not_assumed(self):
        """When two instruments disagree, the disagreement IS the finding.

        Measured on 2026-08-27:

        * Serena ``find_referencing_symbols`` on ``search_prior_art``
          returns exactly ONE hit — ``_main/hits`` at
          ``prior_art_search.py:227``, the module's own CLI entry point.
        * This walk resolves a consumer in ``commands/implement.md``.

        The LSP is not wrong about symbols; it cannot see into a markdown
        fence, which is where the only production consumer lives. Same
        class as the ``importlib`` blind spot CLAUDE.md already records.
        Resolving the disagreement in the LSP's favour would classify a
        wired module as an orphan; resolving it silently either way is
        the failure this arm exists to prevent, so the two populations
        are counted here and the gap is asserted rather than described.
        """
        result = library_reachability()
        python_consumers = sorted(
            path.name
            for path in result.grounded
            if path.suffix == ".py"
            and path.name != "prior_art_search.py"
            and "prior_art_search"
            in _python_referenced_stems(
                path.read_text(encoding="utf-8", errors="replace")
            )
        )
        carrier_consumers = sorted(
            path.name
            for path in result.grounded
            if path.suffix != ".py"
            and "prior_art_search" in _references_in(path)
        )
        assert not python_consumers, (
            f"prior_art_search now has PLAIN-PYTHON consumers "
            f"{python_consumers}, which an LSP resolves without help. The "
            f"instruments no longer disagree here, so this arm measures "
            f"nothing — pick another module whose only carrier is "
            f"markdown, or retire the arm."
        )
        assert carrier_consumers, (
            "neither instrument resolves a consumer of prior_art_search. "
            "The wiring from b5f9e726 is gone, or the carrier extractor "
            "is inert."
        )
        assert "prior_art_search.py" in result.reached, (
            f"the walk found a consumer in {carrier_consumers} and still "
            f"classified the module UNKNOWN — the disagreement was "
            f"resolved in favour of the blinder instrument."
        )

    def test_the_instrument_never_asserts_a_module_is_dead(self):
        """REACHED or UNKNOWN, never ABSENT. Checked, not promised.

        A false "this module is dead" carries mechanical authority and
        would license deleting live code — strictly worse than no
        ratchet. ``prior_art_search`` itself ships this contract
        (``PRIOR ART: UNKNOWN — ...``); this inherits it, and the
        inheritance is verified rather than asserted in prose.
        """
        assert LIBRARY_VERDICTS == {"REACHED", "UNKNOWN"}, (
            f"the verdict vocabulary drifted to {sorted(LIBRARY_VERDICTS)}. "
            f"Any third verdict needs a deliberate edit and a reason."
        )
        assert set(LibraryReachability._fields) == {
            "corpus",
            "reached",
            "unknown",
            "grounded",
            "surfaces",
        }, (
            f"the result shape changed to "
            f"{sorted(LibraryReachability._fields)}. A field named "
            f"'absent', 'dead' or 'unused' would present a search miss as "
            f"a fact about the module."
        )
        # TIE the vocabulary to the result shape. Comparing the frozenset
        # to a literal in this same file costs nothing: both operands are
        # constants here, so the check is decoration. This one binds them
        # — every verdict must name a real bucket, which is the join
        # ``library_verdict`` performs on the live failure path.
        assert {v.lower() for v in LIBRARY_VERDICTS} <= set(
            LibraryReachability._fields
        ), (
            f"verdict(s) {sorted(LIBRARY_VERDICTS)} do not all map to a "
            f"result field {sorted(LibraryReachability._fields)}. "
            f"library_verdict() resolves a verdict by reading the field of "
            f"the same lower-cased name; an unmapped verdict makes it "
            f"raise on every module."
        )

        # And exercise that join, so the vocabulary is load-bearing at
        # runtime rather than only in an assertion.
        result = library_reachability()
        assert library_verdict("prior_art_search.py", result) == "REACHED"
        assert library_verdict(sorted(result.unknown)[0], result) == "UNKNOWN"
        with pytest.raises(KeyError, match="expected exactly one"):
            library_verdict("module_that_is_in_neither_bucket.py", result)

        message = library_failure_message(["synthetic_example.py"]).lower()
        assert "unknown" in message and "no invocation route" in message, (
            f"the failure message no longer states the UNKNOWN contract, "
            f"so a maintainer reads it as a verdict of death: {message}"
        )
        assert "does not mean the module is unused" in message, (
            f"the disclaimer that turns a search miss into a search miss "
            f"— rather than into a verdict — is gone: {message}"
        )
        assert "not authority to remove anything" in message, (
            f"the message no longer says the finding is not authority to "
            f"remove code, which is the whole contract: {message}"
        )
        # Affirmative shapes only: the disclaimer above legitimately
        # contains "the module is unused" inside "does NOT mean ...".
        for forbidden in (
            "module is dead",
            "safe to delete",
            "safe to remove",
            "you may delete",
            "has no consumers",
        ):
            assert forbidden not in message, (
                f"the failure message tells a maintainer the module {forbidden!r}. "
                f"This instrument cannot see a dynamically-constructed "
                f"import, an untracked local settings binding, or a "
                f"carrier it does not enumerate. Saying so is the whole "
                f"contract.\n{message}"
            )

    def test_the_walk_terminates_in_reasonable_time(self):
        """A tier-3 file that takes a minute gets excluded from CI."""
        import time

        _clear_library_reachability_cache()
        start = time.monotonic()
        library_reachability(use_cache=False)
        elapsed = time.monotonic() - start
        assert elapsed < 15.0, (
            f"the library walk took {elapsed:.1f}s. It parses every "
            f"consumer once; a blow-up means a glob started matching a "
            f"mirror tree (.claude/, .worktrees/, .codex/)."
        )


class TestLibraryRatchet:
    """The pinned unreached library set may only shrink."""

    def test_no_new_unreached_library_modules(self):
        """THE RATCHET. A newly-orphaned library module fails here, named.

        Adding the offender to ``PINNED_UNREACHED_LIBRARY`` is NOT an
        acceptable resolution — the ceiling below refuses it.
        """
        live = unreached_library_modules()
        new = sorted(set(live) - PINNED_UNREACHED_LIBRARY)
        assert not new, library_failure_message(new)

    def test_pinned_library_entries_are_still_unreached(self):
        """The arm that makes this a ratchet, not a permanent exemption.

        A module that gets wired drops out of the live set and its stale
        pin fails until it is deleted. That deletion IS the ratchet
        advancing, and it is how the fix gets recorded.
        """
        result = library_reachability()
        live = set(result.unknown)
        stale = sorted(PINNED_UNREACHED_LIBRARY - live)
        assert not stale, (
            f"PINNED_UNREACHED_LIBRARY names {stale}, which now resolve to "
            f"a route: "
            f"{ {k: result.reached.get(k) for k in stale} }\n"
            f"Delete them from the pin and lower "
            f"LIBRARY_REACHABILITY_CEILING and "
            f"LIBRARY_CEILING_HIGH_WATER_MARK to match — that deletion IS "
            f"the ratchet advancing."
        )

    def test_every_pinned_library_module_still_exists(self):
        """A pin entry naming a deleted file is dead weight in the ceiling."""
        corpus = _library_corpus()
        missing = sorted(PINNED_UNREACHED_LIBRARY - set(corpus))
        assert not missing, (
            f"PINNED_UNREACHED_LIBRARY names {missing}, which are no longer "
            f"in the corpus. Remove them and lower "
            f"LIBRARY_REACHABILITY_CEILING from "
            f"{LIBRARY_REACHABILITY_CEILING} to "
            f"{LIBRARY_REACHABILITY_CEILING - len(missing)}."
        )

    def test_library_pin_has_a_ceiling(self):
        """The escape hatch cannot grow SILENTLY.

        Equality against the pin size, plus a reviewed high-water mark so
        that RAISING costs a second visible constant edit. See
        ``TestLibraryCeilingIsNotATautology`` for both driven end to end
        over mutated copies.
        """
        assert len(PINNED_UNREACHED_LIBRARY) == LIBRARY_REACHABILITY_CEILING, (
            f"PINNED_UNREACHED_LIBRARY holds "
            f"{len(PINNED_UNREACHED_LIBRARY)} entries but "
            f"LIBRARY_REACHABILITY_CEILING is "
            f"{LIBRARY_REACHABILITY_CEILING}. These move together: "
            f"equality is what makes a SWAP visible, since equal totals "
            f"prove nothing about equal sets."
        )
        assert LIBRARY_REACHABILITY_CEILING <= LIBRARY_CEILING_HIGH_WATER_MARK, (
            f"LIBRARY_REACHABILITY_CEILING was RAISED to "
            f"{LIBRARY_REACHABILITY_CEILING}, over the reviewed high-water "
            f"mark of {LIBRARY_CEILING_HIGH_WATER_MARK}. LOWER it freely — "
            f"that is the ratchet advancing. RAISING is honest in exactly "
            f"one case: a NEW INVOCATION STYLE or a NEW CORPUS made "
            f"PRE-EXISTING orphans visible. To take that case, in ONE "
            f"diff: name the style here, raise "
            f"LIBRARY_CEILING_HIGH_WATER_MARK alongside it, and justify "
            f"the new entries."
        )

    def test_the_library_residual_headroom_is_zero(self):
        """State the hole rather than hide it, and hold it at zero."""
        residual = LIBRARY_CEILING_HIGH_WATER_MARK - LIBRARY_REACHABILITY_CEILING
        assert residual >= 0, (
            f"LIBRARY_REACHABILITY_CEILING ({LIBRARY_REACHABILITY_CEILING}) "
            f"is above the reviewed high-water mark "
            f"({LIBRARY_CEILING_HIGH_WATER_MARK}); the bound is inverted "
            f"and the anti-raise assertion is inert."
        )
        assert residual == 0, (
            f"the ceiling was lowered to {LIBRARY_REACHABILITY_CEILING} "
            f"while LIBRARY_CEILING_HIGH_WATER_MARK stayed at "
            f"{LIBRARY_CEILING_HIGH_WATER_MARK}. That pre-authorises "
            f"{residual} further pin entr(y/ies) no ceiling assertion "
            f"would see. Lower the mark to "
            f"{LIBRARY_REACHABILITY_CEILING} — one line, no justification "
            f"needed, and it is the last step of the edit you have made."
        )

    def test_regression_issue_1698_the_corpus_cannot_narrow_back_to_hooks_dir(self):
        """The corpus must still BE the library corpus.

        #1612 shipped with ``HOOKS_DIR`` as its whole world. The cheapest
        way to make every arm in this file green again is to point the
        library globs back at ``hooks/`` — every assertion would pass
        against an empty unreached set and the pin would fail loudly, but
        a maintainer under pressure could then "fix" it by emptying the
        pin. This refuses the first step.
        """
        assert any("lib" in glob for glob in LIBRARY_CORPUS_GLOBS), (
            f"LIBRARY_CORPUS_GLOBS no longer names lib/: "
            f"{list(LIBRARY_CORPUS_GLOBS)}"
        )
        corpus = _library_corpus()
        lib_root = LIB_DIR.resolve()
        hooks_root = HOOKS_DIR.resolve()
        for key, path in corpus.items():
            assert lib_root in path.resolve().parents, (
                f"corpus member {key} resolves to {path}, outside "
                f"{lib_root}. The corpus has drifted."
            )
            assert path.resolve().parent != hooks_root, (
                f"corpus member {key} is a HOOK. #1612 already classifies "
                f"hooks; a library ratchet pointed at hooks/ measures "
                f"nothing new."
            )
        hook_names = {p.name for p in _iter_hook_files(HOOKS_DIR)}
        assert not (set(corpus) & hook_names), (
            f"the library corpus and the hook corpus now overlap on "
            f"{sorted(set(corpus) & hook_names)}"
        )

    def test_permitting_arm_modules_reached_only_without_an_import(self):
        """LOAD-BEARING PERMITTING ARM. Import-only analysis deletes code.

        Derived at runtime, never hardcoded: the set of library modules
        that ARE reached and that NO Python ``import`` anywhere in the
        walked corpus names. Every one of them runs as
        ``python3 path/to/X.py`` from a command file, through a settings
        binding, or through Python recovered from a markdown fence.

        A ratchet built on imports alone calls all of them orphans. The
        assertion is on the SHAPE (the set is non-trivial and disjoint
        from the unreached set), not on a count, so it keeps working as
        modules are wired and unwired.
        """
        result = library_reachability()
        imported: "set[str]" = set()
        for path in result.grounded:
            if path.suffix == ".py":
                imported |= _python_referenced_stems(
                    path.read_text(encoding="utf-8", errors="replace")
                )

        non_import_only = sorted(
            key
            for key in result.reached
            if Path(key).stem not in imported
        )
        assert len(non_import_only) >= 10, (
            f"only {len(non_import_only)} reached module(s) resolve "
            f"WITHOUT a Python import: {non_import_only}. Either the "
            f"script-invocation and markdown carriers stopped resolving, "
            f"or the import arm started over-crediting — in both cases "
            f"this arm no longer proves that dropping the non-import "
            f"styles would cost anything."
        )
        # NOT ``set(non_import_only) & set(result.unknown)``: ``reached``
        # and ``unknown`` are built as complements over one corpus and
        # ``non_import_only`` is drawn from ``reached``, so that
        # intersection is empty by construction and the assertion cannot
        # fail. THIS one can: it checks the partition those two buckets
        # are supposed to form, which is the property the complement
        # relied on, and which a future edit to the walk could break.
        assert set(result.reached) | set(result.unknown) == set(result.corpus), (
            f"the walk's buckets do not partition the corpus. "
            f"Neither bucket: "
            f"{sorted(set(result.corpus) - set(result.reached) - set(result.unknown))}; "
            f"outside the corpus: "
            f"{sorted((set(result.reached) | set(result.unknown)) - set(result.corpus))}"
        )
        assert not (set(result.reached) & set(result.unknown)), (
            f"module(s) are BOTH reached and unknown: "
            f"{sorted(set(result.reached) & set(result.unknown))}. "
            f"``library_verdict`` raises on this, so the failure message "
            f"would crash rather than mislead — but the walk is broken."
        )
        lines = sum(
            len(result.corpus[k].read_text(encoding="utf-8", errors="replace")
                .splitlines())
            for k in non_import_only
        )
        assert lines >= 1000, (
            f"the modules reached only by a non-import route total "
            f"{lines} lines. That is the code an import-only ratchet "
            f"would call dead; if it collapsed, re-measure before "
            f"trusting any verdict here."
        )


class TestLibraryGuardIsWatchedFiring:
    """A ratchet only ever observed GREEN is unproven.

    Each arm removes ONE carrier from the live instrument and shows the
    answer changes in the direction that matters. Every arm restores the
    global in ``finally`` and clears the memo, so an arm that fails
    mid-way cannot poison the rest of the file.
    """

    @staticmethod
    @contextlib.contextmanager
    def _without(attribute: str, replacement):
        """Swap a carrier out of THIS module object for the block's duration.

        ``sys.modules[__name__]`` rather than ``import test_hook_
        reachability_ratchet``: this file inserts its own directory on
        ``sys.path``, so an import by name can bind a SECOND module
        object whose globals the live functions never read. Patching that
        copy leaves the walk unchanged and every arm below passes for the
        wrong reason — measured, on the first run of this class.

        A CONTEXT MANAGER, restoring through the SAME captured attribute
        name it patched. The earlier form returned ``(module, original)``
        and left each caller to write ``module._the_name = original`` by
        hand. All three happened to name it correctly, which is luck, not
        structure: one typo would leave a stub installed on a module
        global and silently poison every later test in the file.

        Args:
            attribute: Module-global name to replace.
            replacement: The stub to install.

        Yields:
            The original object, for callers that need to delegate to it.
        """
        module = sys.modules[__name__]
        original = getattr(module, attribute)
        setattr(module, attribute, replacement)
        _clear_library_reachability_cache()
        try:
            yield original
        finally:
            setattr(module, attribute, original)
            _clear_library_reachability_cache()

    def test_removing_the_markdown_carrier_flips_prior_art_search_to_unknown(self):
        """THE WORKED EXAMPLE, watched FIRING on the live corpus.

        ``prior_art_search.py``'s only production consumer is Python
        embedded in a markdown fence. Disable that carrier — which is
        precisely what a Serena-only or import-only instrument does — and
        the module falls out of reach and the ratchet goes RED, naming
        it. This reproduces the state the module actually shipped in for
        a day before ``b5f9e726``.
        """
        before = library_reachability()
        assert "prior_art_search.py" in before.reached, (
            "premise: prior_art_search.py is REACHED today. If it is not, "
            "the wiring in b5f9e726 has been reverted and this arm proves "
            "nothing about the carrier."
        )
        assert "implement.md" in before.reached["prior_art_search.py"], (
            f"premise: the route is the command file, not something else. "
            f"Got: {before.reached['prior_art_search.py']!r}"
        )

        with self._without("_embedded_python_sources", lambda text: []):
            after = library_reachability(use_cache=False)
            new = sorted(set(after.unknown) - PINNED_UNREACHED_LIBRARY)
            # Watch THE RATCHET ITSELF go red, not a re-derivation of it.
            # An arm that only recomputes the set proves the set changed;
            # this proves the assertion a maintainer would see changes too.
            with pytest.raises(AssertionError, match="UNKNOWN"):
                TestLibraryRatchet().test_no_new_unreached_library_modules()

        assert "prior_art_search.py" in after.unknown, (
            "with the markdown carrier disabled prior_art_search.py was "
            "STILL reached, so some other route grounds it and this arm "
            "does not exercise the carrier. Re-pick the instance."
        )
        assert "prior_art_search.py" in new, (
            f"prior_art_search.py fell out of reach but the ratchet's "
            f"new-offender set did not name it: {new}. The guard cannot "
            f"fire on the very case it was built for."
        )

    def test_removing_the_script_invocation_carrier_grows_the_unknown_set(self):
        """Watch the guard fire for the ``python3 path/X.py`` style.

        Paired with ``test_permitting_arm_modules_reached_only_without_
        an_import`` — that arm shows what the style BUYS, this one shows
        the ratchet actually goes red when it is taken away.
        """
        before = set(library_reachability().unknown)
        with self._without(
            "_shell_invoked_stems", lambda text, pattern=None: set()
        ):
            after = set(library_reachability(use_cache=False).unknown)

        gained = sorted(after - before)
        assert gained, (
            "disabling the shell-invocation carrier changed nothing. "
            "Either the carrier resolves nothing today (in which case the "
            "28-module permitting arm is lying) or the swap did not take."
        )
        assert sorted(set(gained) - PINNED_UNREACHED_LIBRARY), (
            f"the {len(gained)} module(s) that fell out of reach are all "
            f"already pinned, so the ratchet would stay GREEN while a "
            f"whole invocation style stopped working: {gained}"
        )

    def test_removing_content_discovery_of_settings_surfaces_changes_the_answer(self):
        """Watch the guard fire for the settings-binding style.

        Restrict surface discovery to what a ``settings*.json`` filename
        glob would find — the instrument failure the #1698 brief names —
        and the walk loses ``global_settings_template.json`` (16 command
        entries) and ``.claude-plugin/default-settings.json``. If nothing
        changed, content discovery would be decorative.
        """
        before = library_reachability()
        assert len(before.surfaces) >= 6, "premise: content discovery resolves"

        content_discovery = _binding_surfaces

        def _glob_only(project_root: Path = PROJECT_ROOT) -> "list[Path]":
            """The mutant: the same walk, filtered to glob-visible names."""
            return [
                p
                for p in content_discovery(project_root)
                if p.name.startswith("settings")
            ]

        with self._without("_binding_surfaces", _glob_only):
            after = library_reachability(use_cache=False)

        assert len(after.surfaces) < len(before.surfaces), (
            "the filename-glob restriction removed no surface, so the two "
            "discovery rules agree here and this arm is inert"
        )
        lost = sorted(set(after.unknown) - set(before.unknown))
        lost_hooks = sorted(
            p.name
            for p in before.grounded
            if p not in after.grounded and p.suffix == ".py"
        )
        assert lost or lost_hooks, (
            "dropping two binding surfaces cost the walk nothing at all. "
            "Content discovery would then be decorative and a filename "
            "glob would do."
        )
        assert {"auto_fix_docs.py", "enforce_tier_distribution.py"} <= set(
            lost_hooks
        ), (
            f"expected the two hooks bound ONLY outside a settings*.json "
            f"glob to lose their grounding; measured {lost_hooks}"
        )


class TestLibraryBothArmsOnSyntheticCorpora:
    """Watch the library rule REFUSING and PERMITTING, per carrier.

    Synthetic throughout, and deliberately so: as the pin shrinks, live
    arms stop exercising the refusing case. These keep working either
    way, and every one drives ``library_reachability`` — the SAME
    function the live rule uses — over a synthetic repository. A control
    that re-implements the rule proves nothing about the rule.
    """

    @staticmethod
    def _repo(tmp_path: Path) -> "tuple[Path, Path]":
        """Build a minimal synthetic tree with an empty settings surface."""
        plugin = tmp_path / "plugins" / "autonomous-dev"
        lib = plugin / "lib"
        lib.mkdir(parents=True)
        (plugin / "hooks").mkdir(parents=True)
        (plugin / "commands").mkdir(parents=True)
        templates = plugin / "templates"
        templates.mkdir(parents=True)
        (templates / "settings.default.json").write_text(
            json.dumps({"hooks": {"PreToolUse": []}}), encoding="utf-8"
        )
        return tmp_path, lib

    @staticmethod
    def _module(lib: Path, name: str, body: str = "def run():\n    return 1\n"):
        (lib / name).write_text(body, encoding="utf-8")

    @staticmethod
    def _command(root: Path, name: str, body: str):
        (root / "plugins" / "autonomous-dev" / "commands" / name).write_text(
            body, encoding="utf-8"
        )

    @staticmethod
    def _unknown(root: Path) -> "list[str]":
        _clear_library_reachability_cache()
        return unreached_library_modules(root, use_cache=False)

    def test_refusing_arm_a_module_with_no_consumer_is_unknown(self, tmp_path):
        """THE #1669 SHAPE. Shipped, tested, deployed, called by nothing."""
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        assert self._unknown(root) == ["synthetic_orphan.py"], (
            "a library module with no consumer in any of the three styles "
            "was not classified UNKNOWN. The rule does not detect the "
            "class it exists to detect."
        )

    def test_permitting_arm_script_invocation_from_a_command_file(self, tmp_path):
        """PERMITTING. ``python3 lib/X.py`` from a command file → REACHED.

        The load-bearing arm: without it the ratchet calls 28 live
        modules orphans. Same module, same tree as the refusing arm above
        — the ONLY difference is one line in a command file.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        self._command(
            root,
            "synthetic.md",
            "# Synthetic\n\n```bash\n"
            "python3 plugins/autonomous-dev/lib/synthetic_orphan.py --check\n"
            "```\n",
        )
        assert self._unknown(root) == [], (
            "a module invoked as `python3 .../synthetic_orphan.py` from a "
            "command file was classified UNKNOWN. An import-only walk "
            "does exactly this, and it is why one must not be used here."
        )

    def test_permitting_arm_markdown_embedded_python_import(self, tmp_path):
        """PERMITTING. The ``search_prior_art`` shape, reproduced exactly.

        A ``python3 -c`` script inside a ```bash fence in a command file.
        Serena resolves nothing here; grep-for-the-carrier plus AST does.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        self._command(
            root,
            "synthetic.md",
            "# Synthetic\n\n```bash\n"
            "BLOCK=$(python3 -c '\n"
            "import sys\n"
            "from synthetic_orphan import run\n"
            "print(run())\n"
            "')\n"
            "```\n",
        )
        assert self._unknown(root) == [], (
            "a module imported by Python embedded in a markdown fence was "
            "classified UNKNOWN. That is the ONLY consumer "
            "prior_art_search.py has, so this instrument would report the "
            "wired state as still dead."
        )

    def test_permitting_arm_settings_binding_under_a_non_lifecycle_event(
        self, tmp_path
    ):
        """PERMITTING. A binding grounds the hook, and the hook the module.

        Bound under ``PreCommit``, which is NOT one of the eight
        ``LIFECYCLE_EVENTS``. That is the live
        ``.claude-plugin/default-settings.json`` shape, and a rule keyed
        on the eight event names refuses it — correct for the hook guard,
        wrong here, where the safe direction is REACHED.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        hook = root / "plugins" / "autonomous-dev" / "hooks" / "synthetic_hook.py"
        hook.write_text(
            "from synthetic_orphan import run\n"
            "def main():\n"
            "    return run()\n",
            encoding="utf-8",
        )
        surface = root / "plugins" / "autonomous-dev" / ".claude-plugin"
        surface.mkdir(parents=True)
        (surface / "default-settings.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreCommit": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": (
                                            "python3 .claude/hooks/"
                                            "synthetic_hook.py"
                                        ),
                                    }
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        assert self._unknown(root) == [], (
            "a module imported by a hook bound in a content-discovered "
            "settings surface was classified UNKNOWN. Discovery by "
            "filename glob would miss this surface entirely."
        )

    def test_refusing_arm_a_mention_in_a_docstring_grounds_nothing(self, tmp_path):
        """REFUSING, negative control of a DIFFERENT SHAPE.

        The consumer file is real, reached, and NAMES the module in a
        docstring, a comment and a string literal — the
        ``secret_patterns.py`` shape. None of that runs anything.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        self._module(
            lib,
            "synthetic_consumer.py",
            '"""Coordinates with synthetic_orphan.py.\n\n'
            "- lib/synthetic_orphan.py (the real work)\n"
            '"""\n'
            "# synthetic_orphan.py is deliberately NOT imported here.\n"
            'NOTE = "see synthetic_orphan.py"\n'
            "def run():\n"
            "    return 1\n",
        )
        self._command(
            root,
            "synthetic.md",
            "```bash\n"
            "python3 plugins/autonomous-dev/lib/synthetic_consumer.py\n"
            "```\n",
        )
        assert self._unknown(root) == ["synthetic_orphan.py"], (
            "a docstring bullet, a comment and a string literal naming "
            "the module grounded it. That is presence-as-proof, and it is "
            "why the instrument is AST rather than grep."
        )

    def test_regression_issue_1698_an_orphan_importer_grounds_nothing(self, tmp_path):
        """LIMITATION 4, as behaviour. The recursion must not stop early.

        ``synthetic_orphan.py`` is imported by ``synthetic_middle.py``,
        which nothing reaches. Before #1698 the equivalent check treated
        any importer outside the hook corpus as grounded on sight, so a
        module reached only by an orphan read as reachable. Paired below
        with the identical tree plus one line that grounds the chain.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        self._module(
            lib,
            "synthetic_middle.py",
            "from synthetic_orphan import run\n"
            "def go():\n"
            "    return run()\n",
        )
        assert self._unknown(root) == [
            "synthetic_middle.py",
            "synthetic_orphan.py",
        ], (
            "a module imported ONLY by an orphan was accepted as reached. "
            "The recursion terminates at a file nothing runs, which is "
            "limitation 4 of this module's docstring, one corpus over."
        )

    def test_permitting_arm_a_chain_that_terminates_at_an_entry_surface(
        self, tmp_path
    ):
        """PERMITTING. The SAME chain, grounded → both modules REACHED.

        Holding the tree fixed and changing only the terminating line is
        what makes the pair discriminate the grounding from some other
        property of the fixture.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        self._module(
            lib,
            "synthetic_middle.py",
            "from synthetic_orphan import run\n"
            "def go():\n"
            "    return run()\n",
        )
        self._command(
            root,
            "synthetic.md",
            "```bash\n"
            "python3 plugins/autonomous-dev/lib/synthetic_middle.py\n"
            "```\n",
        )
        assert self._unknown(root) == [], (
            "a two-link chain terminating at a command file was flagged. "
            "The rule refuses the sanctioned route, so correctly-wired "
            "helpers read as orphans."
        )

    def test_a_fabricated_module_name_is_unknown_without_crashing(self, tmp_path):
        """Boundary: a name this module has never heard of is classified.

        A hardcoded corpus inherits the defect it polices — it can only
        find the modules someone remembered to list.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "zzz_invented_yesterday.py")
        assert self._unknown(root) == ["zzz_invented_yesterday.py"]

    def test_a_test_import_is_not_reachability(self, tmp_path):
        """``prior_art_search`` had nine green tests and no consumers.

        Counting a test import as a route would have reported it reached
        on the day it shipped dead. ``tests`` is in
        ``LIBRARY_EXCLUDED_PATH_PARTS`` for exactly this.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        tests = root / "tests" / "unit"
        tests.mkdir(parents=True)
        (tests / "test_synthetic_orphan.py").write_text(
            "from synthetic_orphan import run\n"
            "def test_run():\n"
            "    assert run() == 1\n",
            encoding="utf-8",
        )
        assert self._unknown(root) == ["synthetic_orphan.py"], (
            "a test import grounded the module. Nine passing tests over a "
            "module nothing calls is the exact state #1669 shipped in."
        )

    def test_documentation_prose_is_not_an_entry_surface(self, tmp_path):
        """``docs/**/*.md`` must not ground anything (#1690's subject).

        Eleven live modules are "invoked" only inside documentation. A
        tutorial showing how to run something is not something running
        it, and crediting it would silently clear eleven orphans.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "synthetic_orphan.py")
        docs = root / "docs"
        docs.mkdir(parents=True)
        (docs / "guide.md").write_text(
            "# Guide\n\n```bash\n"
            "python3 plugins/autonomous-dev/lib/synthetic_orphan.py\n"
            "```\n",
            encoding="utf-8",
        )
        assert self._unknown(root) == ["synthetic_orphan.py"], (
            "a docs/ code block grounded a module. That is #1690's "
            "finding, and crediting it here would clear eleven orphans "
            "with nothing running them."
        )

    # -----------------------------------------------------------------
    # The importlib carrier (MODULE_LOADER_CALLEES) and the repo-root
    # script entry surface (``scripts/*.py``). Both arms of each, and
    # every one drives ``unreached_library_modules`` — the LIVE entry
    # point — never ``_python_referenced_stems`` directly.
    # -----------------------------------------------------------------

    def test_permitting_arm_importlib_spec_from_file_location(self, tmp_path):
        """PERMITTING. ``spec_from_file_location`` IS an invocation route.

        The shape ``hooks/unified_pre_tool.py`` uses in three places. The
        walk read imports and subprocess verbs only, so three modules
        loaded exclusively this way were pinned as unreached while
        running on every PreToolUse event.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "target.py")
        self._module(
            lib,
            "loader.py",
            "import importlib.util\n"
            "from pathlib import Path\n"
            "d = Path(__file__).parent\n"
            "spec = importlib.util.spec_from_file_location("
            '"target", str(d / "target.py"))\n',
        )
        self._command(
            root,
            "synthetic.md",
            "```bash\npython3 plugins/autonomous-dev/lib/loader.py\n```\n",
        )
        assert self._unknown(root) == [], (
            "a module loaded through importlib from a grounded consumer "
            "was classified UNKNOWN. That is the blind spot this carrier "
            "exists to close."
        )

    def test_refusing_arm_a_py_filename_in_a_print_grounds_nothing(self, tmp_path):
        """REFUSING, and it guards #1612's BLOCKING-2 directly.

        The IDENTICAL tree, with the loader call replaced by a ``print``
        naming the same ``.py`` file. If widening the loader route also
        widened ``_argument_constants``, one line of prose would ground
        a module again and this arm goes green when it must not.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "target.py")
        self._module(
            lib,
            "loader.py",
            'print("target.py is deprecated")\n',
        )
        self._command(
            root,
            "synthetic.md",
            "```bash\npython3 plugins/autonomous-dev/lib/loader.py\n```\n",
        )
        assert self._unknown(root) == ["target.py"], (
            "a `.py` filename inside print() grounded the module. "
            "_argument_constants' stop-at-nested-call rule has regressed "
            "and prose confers reachability again (#1612 BLOCKING-2)."
        )

    def test_permitting_arm_a_repo_root_script_is_an_entry_surface(self, tmp_path):
        """PERMITTING. ``scripts/*.py`` runs on operator authority.

        Same authority as the ``scripts/**/*.sh`` already in the tuple.
        Three modules were pinned unreached whose only consumers are
        plain ``from X import`` lines in repo-root scripts.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "target.py")
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "tool.py").write_text(
            "from target import run\n\nprint(run())\n", encoding="utf-8"
        )
        assert self._unknown(root) == [], (
            "a module imported by a repo-root script was classified "
            "UNKNOWN. scripts/*.py is not being read as an entry surface."
        )

    def test_refusing_arm_a_nested_script_is_not_an_entry_surface(self, tmp_path):
        """REFUSING. The glob is NON-RECURSIVE on purpose.

        The identical import, one directory deeper. ``scripts/**/*.py``
        would ground ``scripts/verification/verify_issue94_tdd_red.py``,
        which is itself stale — a stale verifier must vouch for nothing.
        """
        root, lib = self._repo(tmp_path)
        self._module(lib, "target.py")
        nested = root / "scripts" / "verification"
        nested.mkdir(parents=True)
        (nested / "tool.py").write_text(
            "from target import run\n\nprint(run())\n", encoding="utf-8"
        )
        assert self._unknown(root) == ["target.py"], (
            "a nested script grounded a module. The entry-surface glob "
            "has been widened to scripts/**/*.py, which credits stale "
            "verifiers as invocation routes."
        )

    # ---- #1725: the relative-import edge, both arms ---------------------
    #
    # Six controls, and the two that matter most are 3 and 6. Control 3
    # is the DISCRIMINATOR: it is the only arm that goes red if the stem
    # suppression in ``_python_referenced_stems`` is dropped, and stem
    # suppression is the one part of #1725 that can move a module
    # REACHED -> UNKNOWN. Control 6 proves the edge was ADDED rather
    # than the target marked, which is the failure this repo keeps
    # finding: a check whose subject is the description rather than the
    # behaviour.
    #
    # A seventh control was proposed and CUT: a PEP 420 namespace-package
    # negative shape. Measured before cutting — every package directory
    # under ``lib/`` (agent_tracker, ideators, implement_dispatcher,
    # sync_dispatcher, and lib/ itself) carries an ``__init__.py``, so
    # zero namespace packages exist in the corpus this instrument walks.
    # The RESOLUTION RULE it was defending is kept and stated in
    # ``_relative_import_targets``; the control defending a shape that is
    # not present is speculative hardening and was not kept.

    @staticmethod
    def _package(lib: Path, name: str, init_body: str, modules: "dict[str, str]"):
        """Write a package directory with an initialiser and modules."""
        pkg = lib / name
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(init_body, encoding="utf-8")
        for module_name, body in modules.items():
            (pkg / module_name).write_text(body, encoding="utf-8")
        return pkg

    def test_permitting_arm_relative_re_export_reaches_a_package_module(
        self, tmp_path
    ):
        """PERMITTING. The live ``agent_tracker`` shape, minimised.

        A command file names the PACKAGE; the package initialiser reaches
        its own module by relative import. Before #1725 this was UNKNOWN
        twice over: the initialiser collapsed to the stem ``__init__``,
        so the package directory had no address at all, and ``from .sub
        import X`` emitted the stem ``sub`` rather than a path.
        """
        root, lib = self._repo(tmp_path)
        self._package(
            lib,
            "pkg",
            "from .sub import X\n\n__all__ = ['X']\n",
            {"sub.py": "X = 1\n"},
        )
        self._command(
            root,
            "synthetic.md",
            "# Synthetic\n\n```python\nfrom pkg import X\n```\n",
        )
        assert self._unknown(root) == [], (
            "a package module re-exported by its own initialiser, with "
            "the package named by a grounded command file, was "
            "classified UNKNOWN. That is the live agent_tracker defect: "
            "seven modules called dead while ten surfaces named them."
        )

    def test_refusing_arm_the_same_package_with_no_carrier_stays_unknown(
        self, tmp_path
    ):
        """REFUSING. Identical tree, minus the one line that grounds it.

        Paired with the arm above: same package, same relative import,
        the command file simply removed. If this went green the new edge
        would be grounding packages on its own authority, which would
        make the permitting arm meaningless.
        """
        root, lib = self._repo(tmp_path)
        self._package(
            lib,
            "pkg",
            "from .sub import X\n\n__all__ = ['X']\n",
            {"sub.py": "X = 1\n"},
        )
        assert self._unknown(root) == ["pkg/sub.py"], (
            "removing the ONLY carrier that names the package left its "
            "module reached. The relative edge is grounding on its own "
            "authority instead of extending a route that already exists."
        )

    def test_refusing_arm_a_relative_import_does_not_credit_a_namesake(
        self, tmp_path
    ):
        """THE DISCRIMINATOR. Two packages, one ``models.py`` each.

        The synthetic form of the live case: ``agent_tracker/tracker.py``
        says ``from .models import M``, and the bare stem ``models``
        addresses THREE files — ``agent_tracker/``,
        ``implement_dispatcher/`` and ``sync_dispatcher/models.py``.
        Only one of them is the file Python would load.

        This arm is the reason ``_python_referenced_stems`` SUPPRESSES
        the bare stem of a relative import that resolves. Delete that
        suppression and ``orphan_pkg/models.py`` is credited by a
        namesake it has no relationship to, and this test goes red — it
        is the only one in the file that does.
        """
        root, lib = self._repo(tmp_path)
        self._package(
            lib,
            "reached_pkg",
            "from .models import M\n\n__all__ = ['M']\n",
            {"models.py": "M = 1\n"},
        )
        self._package(
            lib,
            "orphan_pkg",
            "from .models import M\n\n__all__ = ['M']\n",
            {"models.py": "M = 2\n"},
        )
        self._command(
            root,
            "synthetic.md",
            "# Synthetic\n\n```python\nfrom reached_pkg import M\n```\n",
        )
        assert self._unknown(root) == ["orphan_pkg/models.py"], (
            "a relative import credited a SAME-NAMED module in an "
            "unrelated package. The bare stem is being emitted alongside "
            "the resolved path, so `from .models import M` reaches every "
            "models.py in the tree instead of its own."
        )

    def test_a_package_initialiser_is_walkable_but_never_pinnable(
        self, tmp_path
    ):
        """REFUSING, on the CORPUS rather than the walk.

        ``_consumer_nodes`` gained the initialiser as a NODE; the corpus
        must not gain it as a MEMBER. If it did, five identically-named
        ``__init__.py`` entries would appear in the pin and against the
        ceiling, and ``test_library_corpus_keys_round_trip`` would be
        asserting something this change had quietly broken.

        Corpus membership and node membership are different questions,
        and this is the arm that keeps them different.
        """
        root, lib = self._repo(tmp_path)
        self._package(
            lib,
            "pkg",
            "from .sub import X\n\n__all__ = ['X']\n",
            {"sub.py": "X = 1\n"},
        )
        self._command(
            root,
            "synthetic.md",
            "# Synthetic\n\n```python\nfrom pkg import X\n```\n",
        )
        _clear_library_reachability_cache()
        result = library_reachability(root, use_cache=False)
        assert not [k for k in result.corpus if k.endswith("__init__.py")], (
            f"a package initialiser entered the CORPUS, where it becomes "
            f"pinnable and counts against the ceiling: "
            f"{sorted(result.corpus)}"
        )
        assert (lib / "pkg" / "__init__.py") in result.grounded, (
            "the initialiser is not in `grounded`, so the package was "
            "never entered and the permitting arm above is passing for "
            "some other reason than the one it claims."
        )

    def test_permitting_arm_an_absolute_import_package_needs_no_new_edge(
        self, tmp_path
    ):
        """PERMITTING, and the new channel contributes NOTHING here.

        The live ``ideators`` shape: ``ideators/__init__.py:16-20`` uses
        ``from autonomous_dev.lib.ideators.security_ideator import ...``
        — fully absolute. The answer is decided entirely by the
        pre-existing STEM channel, and this arm exists so that a future
        change to the relative resolver cannot quietly take credit for
        an absolute-import package.
        """
        root, lib = self._repo(tmp_path)
        self._package(
            lib,
            "pkg",
            "from top.pkg.sub import X\n\n__all__ = ['X']\n",
            {"sub.py": "X = 1\n"},
        )
        self._command(
            root,
            "synthetic.md",
            "# Synthetic\n\n```python\nfrom pkg import X\n```\n",
        )
        assert self._unknown(root) == [], (
            "an absolutely-imported package module was classified "
            "UNKNOWN. This shape worked before #1725 through the stem "
            "channel; if it is failing now, the relative edge has "
            "displaced the stem channel rather than adding to it."
        )

    def test_the_relative_edge_does_not_credit_at_build_time(self, tmp_path):
        """NEGATIVE CONTROL. Proof the EDGE was added, not the TARGET.

        A package that re-exports its own module, with NOTHING naming
        the package anywhere. The re-export exists, the relative import
        resolves on disk, and the initialiser is addressable by its
        directory name — every ingredient of the new channel is present.
        The one missing thing is a route to the package, and that must
        be enough to keep the module UNKNOWN.

        This is the live ``implement_dispatcher`` case: ``validators.py``
        says ``import implement_dispatcher``, which NOW resolves to that
        package's initialiser — but ``validators.py`` is never dequeued,
        so the edge is never traversed. The conditionality falls out of
        the worklist and costs zero lines. Had the credit been applied
        while BUILDING the graph, this test would be red and ten live
        modules would have been marked reached on no evidence.
        """
        root, lib = self._repo(tmp_path)
        self._package(
            lib,
            "pkg",
            "from .sub import X\n\n__all__ = ['X']\n",
            {"sub.py": "X = 1\n"},
        )
        # Present, resolving, and unreachable: nothing dequeues it.
        self._module(lib, "orphan_importer.py", "import pkg\n")
        assert self._unknown(root) == [
            "orphan_importer.py",
            "pkg/sub.py",
        ], (
            "a package module was credited without any route to its "
            "package. The relative edge is being applied while the graph "
            "is BUILT rather than while it is WALKED, which marks the "
            "target instead of adding the edge."
        )


class TestLibraryCorpusCrossReference:
    """Where the hook corpus and the library corpus have to agree."""

    def test_limitation_four_is_measured_not_merely_documented(self):
        """Name every hook whose only voucher is an UNKNOWN library module.

        ``_utility_route_is_grounded`` accepts any importer outside
        ``HOOKS_DIR`` on sight. #1698 does NOT rewrite that rule — it is
        #1612's, and re-verdicting five pinned hooks from here would be
        the two-ratchets-disagree failure — but the condition it cannot
        see is now computable, so it is computed on every run instead of
        being left as a paragraph.

        The set is EMPTY today. That is a measurement, not an assumption:
        the positive control below shows the detector can produce a
        non-empty answer, so a zero here means zero rather than an inert
        probe.
        """
        result = library_reachability()
        registrations = _lifecycle_registrations(_registration_surfaces())
        hooks_root = HOOKS_DIR.resolve()

        vouched_by_an_orphan: "dict[str, list[str]]" = {}
        for path in _iter_hook_files(HOOKS_DIR):
            if not _refusal_evidence(path) or registrations.get(path.name):
                continue
            if _sidecar_type(path) != UTILITY_TYPE:
                continue
            outside = [
                importer
                for importer in _resolve_importers(path)
                if importer.resolve().parent != hooks_root
            ]
            orphaned = [p.name for p in outside if p not in result.grounded]
            if orphaned:
                vouched_by_an_orphan[path.name] = sorted(orphaned)

        assert not vouched_by_an_orphan, (
            f"hook(s) are treated as reachable on the strength of a "
            f"library or script importer that is ITSELF unreached: "
            f"{vouched_by_an_orphan}\n"
            f"That is limitation 4 of this module's docstring, now with a "
            f"live instance. The hook reads as wired, the library file "
            f"reads as wired because nothing asked, and neither runs. "
            f"Wire the importer up, or register the hook directly."
        )

    def test_positive_control_the_cross_reference_can_produce_a_finding(
        self, tmp_path
    ):
        """A probe that returns zero is not evidence of zero.

        The arm above reports an empty set over the live tree. Drive the
        same two rules over a synthetic tree that CONTAINS the shape —
        a ``utility`` hook whose only importer is an orphaned library
        module — and both must produce the pairing.
        """
        plugin = tmp_path / "plugins" / "autonomous-dev"
        hooks = plugin / "hooks"
        lib = plugin / "lib"
        hooks.mkdir(parents=True)
        lib.mkdir(parents=True)
        templates = plugin / "templates"
        templates.mkdir(parents=True)
        (templates / "settings.default.json").write_text(
            json.dumps({"hooks": {"PreToolUse": []}}), encoding="utf-8"
        )
        (hooks / "synthetic_utility_gate.py").write_text(
            "import sys\ndef main():\n    sys.exit(2)\n", encoding="utf-8"
        )
        (hooks / "synthetic_utility_gate.hook.json").write_text(
            json.dumps({"name": "synthetic_utility_gate", "type": "utility"}),
            encoding="utf-8",
        )
        (lib / "synthetic_orphan_consumer.py").write_text(
            "import synthetic_utility_gate\n"
            "def go():\n"
            "    return synthetic_utility_gate.main()\n",
            encoding="utf-8",
        )

        assert unreachable_refusers(hooks, tmp_path) == {}, (
            "POSITIVE CONTROL PREMISE FAILED: the hook rule was supposed "
            "to PERMIT this gate on the strength of its library importer. "
            "If it already refuses it, limitation 4 does not apply here "
            "and this control exercises nothing."
        )

        _clear_library_reachability_cache()
        result = library_reachability(tmp_path, use_cache=False)
        _clear_library_reachability_cache()
        assert "synthetic_orphan_consumer.py" in result.unknown, (
            f"POSITIVE CONTROL FAILED: the library rule found a route to "
            f"the sole voucher, so the cross-reference above could never "
            f"produce a finding and its empty result means nothing. "
            f"Reached: {result.reached}"
        )


class TestLibraryCeilingIsNotATautology:
    """The library ceiling must fail on GROWTH, not merely on disagreement.

    ``LIBRARY_REACHABILITY_CEILING == len(PINNED_UNREACHED_LIBRARY)`` is
    unfalsifiable from inside this file: both operands are constants
    here, so an edit that adds a pinned entry AND bumps the ceiling moves
    them together and nothing fires. The arms below are therefore driven
    over MUTATED copies of this module in a subprocess, reusing
    ``TestCeilingIsNotATautology``'s harness rather than growing a second
    one.
    """

    _SELECTION = "test_library_pin_has_a_ceiling"

    #: Prefix of the single line opening the library pin literal. An
    #: anchor that survives the pin being emptied, so the harness does
    #: not need re-anchoring as the ratchet advances.
    _PIN_PREFIX = "PINNED_UNREACHED_LIBRARY: "

    @staticmethod
    def _source() -> str:
        return Path(__file__).resolve().read_text(encoding="utf-8")

    @staticmethod
    def _library_ceiling_anchor(ceiling: int) -> str:
        return f"\nLIBRARY_REACHABILITY_CEILING = {ceiling}\n"

    @classmethod
    def _grow(cls, source: str, count: int) -> str:
        """Add ``count`` synthetic entries to the library pin."""
        assert count > 0, (
            f"a growth mutation of {count} entries adds nothing; the "
            f"refusing arm would run against an unmutated copy"
        )
        declaration = _unique_line(source, cls._PIN_PREFIX, "library pin")
        entries = "".join(
            f'    "synthetic_library_offender_{i}.py",\n' for i in range(count)
        )
        if "frozenset()" in declaration:
            replacement = declaration.replace(
                "frozenset()", "frozenset({\n" + entries + "})"
            )
        else:
            replacement = declaration + entries
        return TestCeilingIsNotATautology._substitute(
            source, declaration, replacement
        )

    @staticmethod
    def _run(tmp_path: Path, source: str, selection: str):
        """Run one selected test over a mutated copy, out of tree."""
        import os

        mutant = tmp_path / "test_library_ceiling_mutant.py"
        mutant.write_text(source, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [_THIS_DIR] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(mutant),
                "-k",
                selection,
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:randomly",
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=env,
            timeout=180,
        )

    def test_control_unmutated_copy_passes_the_library_ceiling(self, tmp_path):
        """NEGATIVE CONTROL for the harness. No mutation → GREEN.

        Without it, a red below could just as easily mean "a subprocess
        pytest cannot import this module at all".
        """
        result = self._run(tmp_path, self._source(), self._SELECTION)
        assert result.returncode == 0, (
            f"the UNMUTATED library ceiling test failed in the harness, so "
            f"every other result here is uninterpretable.\n"
            f"{result.stdout}\n{result.stderr}"
        )
        assert "1 passed" in result.stdout, (
            f"the harness selected {result.stdout!r} — expected exactly "
            f"one test. A `-k` that matches nothing exits 0 and would read "
            f"as a pass on every arm."
        )

    def test_regression_issue_1698_growing_the_library_pin_and_ceiling_fails(
        self, tmp_path
    ):
        """THE REFUSING ARM. Growth must be RED even when self-consistent.

        Add entries to the pin and raise the ceiling to match, in one
        edit — the shape that lets the next orphan be pinned instead of
        wired up. The target is derived from
        ``LIBRARY_CEILING_HIGH_WATER_MARK`` rather than from the ceiling,
        so the arm keeps biting as the ratchet advances.
        """
        target = LIBRARY_CEILING_HIGH_WATER_MARK + 1
        source = self._grow(
            self._source(), target - len(PINNED_UNREACHED_LIBRARY)
        )
        source = TestCeilingIsNotATautology._substitute(
            source,
            self._library_ceiling_anchor(LIBRARY_REACHABILITY_CEILING),
            self._library_ceiling_anchor(target),
        )
        result = self._run(tmp_path, source, self._SELECTION)
        assert result.returncode != 0, (
            f"PINNED_UNREACHED_LIBRARY grew to {target} with the ceiling "
            f"raised to match, and the ceiling test still PASSED. The "
            f"escape hatch has no ceiling: the next orphan can be pinned "
            f"instead of wired up, by a two-constant edit no assertion "
            f"sees.\n{result.stdout}"
        )
        assert "LIBRARY_CEILING_HIGH_WATER_MARK" in result.stdout, (
            f"the mutant failed for some reason other than the library "
            f"ceiling assertion, so this proves nothing about it.\n"
            f"{result.stdout}"
        )

    def test_growing_the_library_pin_alone_fails(self, tmp_path):
        """The equality arm: pin and ceiling must move together."""
        source = self._grow(self._source(), 1)
        result = self._run(tmp_path, source, self._SELECTION)
        assert result.returncode != 0, (
            f"an entry was added to PINNED_UNREACHED_LIBRARY without "
            f"touching the ceiling and nothing fired.\n{result.stdout}"
        )
        assert "LIBRARY_REACHABILITY_CEILING" in result.stdout

    def test_raising_the_library_ceiling_alone_fails(self, tmp_path):
        """The anti-slack arm: a ceiling above the pin pre-authorises."""
        raised = LIBRARY_CEILING_HIGH_WATER_MARK + 1
        source = TestCeilingIsNotATautology._substitute(
            self._source(),
            self._library_ceiling_anchor(LIBRARY_REACHABILITY_CEILING),
            self._library_ceiling_anchor(raised),
        )
        result = self._run(tmp_path, source, self._SELECTION)
        assert result.returncode != 0, (
            f"LIBRARY_REACHABILITY_CEILING was raised to {raised} while "
            f"the pin stayed at {len(PINNED_UNREACHED_LIBRARY)} and "
            f"nothing fired. That is a pre-authorised exemption.\n"
            f"{result.stdout}"
        )
        # RED is not enough — an unrelated collection error is also red,
        # and would read as a pass here. The two sibling arms assert on
        # the message; this one was the odd one out.
        assert "LIBRARY_REACHABILITY_CEILING" in result.stdout, (
            f"the mutant failed for some reason other than a library "
            f"ceiling assertion, so this proves nothing about it.\n"
            f"{result.stdout}\n{result.stderr}"
        )

    def test_permitting_arm_shrinking_the_library_pin_and_ceiling_is_allowed(
        self, tmp_path
    ):
        """THE PERMITTING ARM. Wiring a module up must never turn this red.

        The opposite direction from the reproducer, and the outcome this
        whole ratchet exists to encourage: a module gets wired, its pin
        entry is deleted, both ceiling constants drop by one. A guard
        that blocked THAT would be pressure to leave orphans pinned.
        """
        assert PINNED_UNREACHED_LIBRARY, "premise: there is an entry to drop"
        dropped = sorted(PINNED_UNREACHED_LIBRARY)[-1]
        source = self._source()
        entry_line = _unique_line(
            source, f'    "{dropped}",', f"library pin entry {dropped}"
        )
        source = TestCeilingIsNotATautology._substitute(source, entry_line, "")
        source = TestCeilingIsNotATautology._substitute(
            source,
            self._library_ceiling_anchor(LIBRARY_REACHABILITY_CEILING),
            self._library_ceiling_anchor(LIBRARY_REACHABILITY_CEILING - 1),
        )
        source = TestCeilingIsNotATautology._substitute(
            source,
            f"\nLIBRARY_CEILING_HIGH_WATER_MARK = "
            f"{LIBRARY_CEILING_HIGH_WATER_MARK}\n",
            f"\nLIBRARY_CEILING_HIGH_WATER_MARK = "
            f"{LIBRARY_CEILING_HIGH_WATER_MARK - 1}\n",
        )
        result = self._run(tmp_path, source, self._SELECTION)
        assert result.returncode == 0, (
            f"a module was wired up, removed from PINNED_UNREACHED_LIBRARY "
            f"and both ceilings lowered to match — and the ceiling test "
            f"refused it. Lowering is the ratchet advancing; blocking it "
            f"creates pressure to leave orphans pinned.\n"
            f"{result.stdout}\n{result.stderr}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
