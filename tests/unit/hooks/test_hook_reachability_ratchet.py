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
4. **A dead LIBRARY still vouches.** ``_utility_route_is_grounded`` treats any
   importer outside ``HOOKS_DIR`` — a ``lib/`` or ``scripts/`` file — as
   grounded without asking whether THAT file is reached. The recursion stops at
   the edge of the hook corpus. Cycles WITHIN the corpus are refused (two
   ``utility`` hooks vouching for each other ground nothing), but a hook invoked
   only by an orphaned library function reads as reachable. Closing this means
   reachability analysis over ``lib/`` as well, which is a wider corpus than
   #1612.
5. It inherits every limitation of the #1588 refusal instruments, including
   their under-reporting of unnamed refusal forms.

Scope note for a later widening: ``validate_claude_md_size.py`` was
reclassified ``utility`` in the same commit and described there as "(orphan,
kept for size enforcement)" — an admission it is unreferenced. It carries no
refusal evidence, so it is an OBSERVER and outside this issue. Check it when
the rule is widened past refusers.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

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
# or delete it. Whether each of these five should be registered or deleted is
# the policy half of #1612 and is deliberately NOT decided here.
#
#  * PreToolUseWrite-protect-sensitive.sh — emits ``permissionDecision: deny``
#    through its own fusing ``deny_and_record`` shell function, and its FILENAME
#    asserts a lifecycle event. Nothing in the repo invokes it. Its relationship
#    to the ``unified_pre_tool.py`` protected-path floor is unresolved (#1612).
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
    "PreToolUseWrite-protect-sensitive.sh": _UNREGISTERED_UTILITY,
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
REACHABILITY_CEILING = 5

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
CEILING_HIGH_WATER_MARK = 5


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

        The four registered gates refuse and MUST pass. This watches the rule
        PERMITTING over the live corpus, which a refusal-only guard never
        proves. The premise assertion is what stops it passing vacuously: each
        must still be DETECTED as a refuser, so it is permitted because it is
        reachable and not because it became invisible.
        """
        candidates = refusal_candidates()
        live = unreachable_refusers()
        for name in (
            "unified_pre_tool.py",
            "unified_prompt_validator.py",
            "plan_gate.py",
            "enforce_file_organization.py",
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
