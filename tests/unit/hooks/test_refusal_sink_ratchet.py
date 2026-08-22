#!/usr/bin/env python3
"""Ratchet: no hook may refuse outside a sanctioned, recording-fused sink.

Issue #1588. A hook refusal that leaves no row in ``.claude/logs/hook-blocks.jsonl``
is an enforcement action nobody can audit. The operator question "is this guard
doing anything?" becomes unanswerable, and a guard that has silently stopped
firing is indistinguishable from one that never fires because nothing violates it.

The consistency problem, and why counting is downstream of it
------------------------------------------------------------
This repo grew FOUR ways to refuse against FOUR ways to record, with no
structural link between the two lists. Four separate attempts to enumerate
"hooks that can refuse but do not record" produced four *different* wrong
answers, each wrong in a different direction:

* A regex on decision literals matched **prose inside a comment**
  (``validate_session_quality.py:10``: ``- WARNS (exit 1) instead of BLOCKS
  (exit 2)``) and reported a hook that only warns as refusal-capable.
* The same regex **missed** ``unified_pre_tool.py`` — the single largest
  refuser in the repo (8,093 recorded blocks) — because it carries **zero**
  refusal literals and refuses exclusively through a decorated function.
* Serena's ``find_referencing_symbols`` missed a function-local import its
  index does not see, and surfaced a recorder-call path grep had not found.
* A Python-only glob missed the shell hook entirely.

No single instrument is trustworthy, and no better regex fixes that: the
enumeration is hard *because* four refusal forms coexist. **The counting
problem is downstream of the consistency problem.** This module therefore does
not pretend to be a detector. It is a RATCHET over the union of every
instrument available, pinned to a known set that may only shrink.

Sanctioned sink: a SET, on the FUSION property
----------------------------------------------
The sink is not "whatever writes a row". It is "a path on which a refusal
cannot be obtained without the recording happening in the same act". Three
paths have that property and are sanctioned (``SANCTIONED_SINKS``):

* ``hook_telemetry.deny_and_record`` — returns the deny envelope AND records,
  in one call. A caller cannot get the payload without the row.
* ``hook_telemetry.block_event_decorator`` — wraps the hook's sole refusal
  emitter, so every refusal through that emitter records by construction.
* ``hook_safety.HookDecision`` (Issue #1588) — the hook RETURNS its decision
  instead of printing it, and ``hook_safety.safe_main`` owns the output
  channel: it emits the payload and records the refusal in one act. This one
  fuses more strongly than the other two. ``deny_and_record`` fuses the record
  to the *payload* and still trusts the caller to print what it was handed; a
  hook that never reaches stdout has no way to refuse at all except by
  returning a decision. That is the point of #1588 — "is this payload a
  refusal?" is an open question no detector can settle, while "does this file
  write to stdout?" is closed and decidable by an AST walk.

Admitting the third member is NOT a loosening. The membership rule is
unchanged and is still FUSION; a genuinely new fusing mechanism was built, and
a ratchet that refused to learn about it would flag the sanctioned path — the
"guard refusing a legitimate case" failure that
``test_in_sink_refusers_are_permitted`` exists to catch.

Two paths are DELIBERATELY EXCLUDED, and this contradicts the framing in the
brief, which described ``log_block_with_recovery`` as already fusing recording
to refusal. Read against the source it does not:

* ``hook_telemetry.log_block_event`` is a bare recorder. Calling it is a
  SECOND act, adjacent to the refusal and independently forgettable — the
  precise convention Issue #1587 identified as the defect class.
* ``hook_recovery.log_block_with_recovery`` is a deprecated shim that
  delegates to ``log_block_event``. It emits no refusal and fuses nothing. Its
  only live call site (``unified_session_tracker.py:1245``) records a
  ``STAGE_ADVANCE``, which is not a refusal at all.

Admitting either as a sink would collapse a genuinely distinct property
(fused) into a weaker one (a row appeared today), and the ratchet would stop
tracking exactly the hooks it exists to track. Note the consequence:
**out-of-sink is NOT the same as unrecorded.** Two of the five pinned hooks
do record today, via the two-act convention. They are pinned because nothing
structurally prevents a future refusal path in those files from skipping the
second act — which is the condition being ratcheted, not the current row count.

What this guard CANNOT detect
-----------------------------
Stated here rather than papered over; each is a real hole, not a hypothetical:

1. **Dynamically constructed refusals.** Python detection is AST-based, so it
   sees literal decision values and literal call arguments. A refusal whose
   decision string is computed (``d = "de" + "ny"``), splatted (``**payload``),
   read from config, or emitted by ``print(json.dumps(built_at_runtime))`` is
   invisible.
2. **Shell beyond regex.** ``*.sh`` hooks are scanned line-wise with ``#``
   comments stripped. Shell is not parsed; a refusal assembled across
   variables or emitted from a nested heredoc can be missed.
3. **Refusal forms nobody has named yet.** The instruments enumerate the
   *known* forms — six: #1588 added the returned-decision-object form
   (instrument E) and its remediation added the returned-exit-code form
   (``return2``, instrument F) after the latter was found to be both
   documented by ``hook_safety`` and used by a live hook while being invisible
   here. A seventh form invented tomorrow is outside all of them. This is the
   irreducible limit of the approach and the reason the pinned set has a
   ceiling rather than the guard claiming completeness. Note what adding F
   cost: three hooks that had always refused outside the sink became visible
   at once, which is the honest measure of how much an unnamed form can hide.
4. **Intra-file granularity.** Sink classification is per-FILE and per-NAME: a
   file referencing a sanctioned sink is treated as in-sink. The guard does
   NOT prove every refusal path *within* such a file is fused, only that the
   file's refusals are meant to route through one. A new unfused path added to
   an already-in-sink file will not be flagged.
5. **Name-level, not identity-level, sink matching.** A function coincidentally
   named ``deny_and_record`` that records nothing would read as in-sink. For
   Python this is now narrowed: the name must both ARRIVE from ``hook_safety``
   or ``hook_telemetry`` (import or module-qualified access) and appear in
   CALL position, so a bare identifier no longer launders a refusal — the
   previous rule classified any file containing ``HookDecision = None`` as
   in-sink, and that line is shipped by the reference implementation itself.
   Shell keeps the bare regex, because shell has no imports and the one shell
   refuser defines its own fusing ``deny_and_record`` function.
6. **Non-hook refusers.** Scope is the top-level hooks directory. Refusals
   emitted from ``lib/`` or ``scripts/`` are out of scope.

Holes 1, 2 and 3 all fail in the SAME safe direction — they under-report
candidates, so the guard can miss a violation but cannot invent one. Hole 4 is
the one that fails toward false confidence, and is the strongest argument for
finishing the migration rather than living on the ratchet.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

# tests/unit/hooks/test_refusal_sink_ratchet.py
#   -> hooks -> unit -> tests -> repo root = parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# The TRACKED source corpus. NOT ``.claude/hooks/``, which is a gitignored
# deploy artifact — a guard pointed there is red in CI and in every fresh
# clone, and green-or-red locally according to deploy freshness rather than
# according to the change.
HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"

# Decision VALUES that constitute a refusal. Value-awareness is load-bearing:
# ``enforce_tier_distribution.py`` carries eleven ``permissionDecision`` keys
# and every one of them is ``"allow"``. A key-only regex reports it as a
# refuser; it never refuses.
REFUSAL_DECISION_VALUES = frozenset({"deny", "block", "ask"})

# Keys whose value carries a decision. ``"block"`` under ``"decision"`` is the
# out-of-enum value #1589 exists to resolve; it is matched here so the ratchet
# tracks it rather than losing it to a schema argument.
DECISION_KEYS = frozenset({"permissionDecision", "decision"})

# Known refusal-emitting functions, across all four coexisting forms. Private
# aliases are included because two hooks wrap the emitter locally.
REFUSAL_EMITTER_NAMES = frozenset(
    {
        "output_decision",
        "_output_decision",
        "deny_and_record",
        "_deny_and_record",
    }
)

# The sanctioned sink — a SET, on the fusion property. See the module
# docstring for why these three and not the bare recorders.
SANCTIONED_SINKS = frozenset(
    {"deny_and_record", "block_event_decorator", "HookDecision"}
)

# Modules the sanctioned sinks are defined in. Sink membership requires the
# name to ARRIVE from one of these (import or module-qualified access) as well
# as to be CALLED — a bare identifier is not membership. See _sink_evidence.
SINK_MODULES = frozenset({"hook_safety", "hook_telemetry"})

# Issue #1588's refusal form: the hook returns a decision object and
# ``hook_safety.safe_main`` owns stdout. Named here so instrument E below can
# see it — limitation 3 (unnamed forms) bites immediately otherwise.
DECISION_OBJECT_NAME = "HookDecision"

# Classmethod factories on the decision object that refuse by construction,
# with no decision argument to inspect.
DECISION_OBJECT_REFUSAL_FACTORIES = frozenset({"deny"})

# Recorders that are NOT sinks: real, legitimate, but unfused. Named so the
# distinction is enforced by a test rather than left in prose.
UNFUSED_RECORDERS = frozenset({"log_block_event", "log_block_with_recovery"})

# Hooks known to refuse OUTSIDE the sanctioned sink. This set may only SHRINK.
#
# Adding an entry is NOT an acceptable resolution for a guard failure: route
# the refusal through ``hook_telemetry.deny_and_record`` (or decorate the
# hook's sole emitter with ``block_event_decorator``) instead.
#
# MIGRATED OUT (Issue #1611): ``plan_gate.py``. It refused via
# ``_output_decision("block", ...)`` on two paths and recorded nothing — every
# one of its 287 rows in the live log was a Phase-E ``mode_skip``. Its sole
# refusal emitter is now decorated with ``block_event_decorator``, so refusing
# and recording are one act. ``block_event_decorator`` was chosen over
# ``HookDecision`` deliberately: it is the only sink that leaves the EMITTED
# ENVELOPE untouched, and plan_gate's out-of-enum ``"block"`` value must not
# change here — that is #1589's to resolve, and altering what Claude Code
# receives is a separate change with a separate blast radius.
#
#  * unified_prompt_validator.py — refuses via a ``{"decision": "block"}``
#    dict literal (line 803) and records via a separate adjacent
#    ``_log_block_event_972`` call (line 810). Two acts.
#  * enforce_orchestrator.py — refuses via ``sys.exit(2)`` (line 320) and
#    records via a separate preceding ``_log_block_event_972`` call (line
#    313). Two acts.
#
# The three below were NOT added because a hook regressed. They were always
# out of sink; instrument ``return2`` is the first instrument able to SEE
# them. Their evidence is ``['return2']`` and no telemetry call of any kind
# appears in any of the three files, so each refuses today with ZERO rows —
# the same unknowable zero ``enforce_file_organization.py`` had before #1588.
# All three are commit gates that refuse from ``main()`` and print to stderr:
#
#  * enforce_tdd.py                 — ``return 2  # Block commit`` (line 458)
#  * enforce_prunable_threshold.py  — ``return 2`` (line 157)
#  * enforce_regression_test.py     — ``return 2`` (line 183)
PINNED_OUT_OF_SINK: "frozenset[str]" = frozenset(
    {
        "unified_prompt_validator.py",
        "enforce_orchestrator.py",
        "enforce_tdd.py",
        "enforce_prunable_threshold.py",
        "enforce_regression_test.py",
    }
)

# Ceiling on the pinned set. The set is an escape hatch, and an escape hatch
# without its own ceiling is decorative — the next hook that fails gets added
# to the list instead of migrated.
#
# It moved 3 -> 6 in the #1588 remediation, and the distinction that makes
# that legitimate is the ONLY one this constant is allowed to encode:
#
#   * A hook that starts refusing outside the sink is a REGRESSION. The
#     ceiling refuses it. Migrate the hook.
#   * An instrument that starts SEEING a hook which was always out of sink is
#     a BASELINE CORRECTION. The old number was an under-count, and refusing
#     to record the true one just keeps the guard blind — which is the defect
#     ``return2`` was added to fix.
#
# So the raise is admissible only in the same change that adds a member to
# INSTRUMENTS. What is MECHANICAL is that a raise cannot happen quietly:
# ``test_pinned_set_has_a_ceiling`` pins this constant against a literal, so
# any raise turns that test red and its failure message states the one
# admissible justification. Whether the justification offered is real is a
# judgement the reviewer of that diff makes — it is not, and is not claimed to
# be, machine-checked. Lowering needs no justification at all and is not
# blocked by anything here.
#
# 6 -> 5 in Issue #1611: ``plan_gate.py`` was MIGRATED into the sink, not
# reclassified. The literal below moves down with the set, because leaving it
# at 6 would be exactly the slack the anti-growth arm exists to refuse.
PINNED_CEILING = 5

# The evidence vocabulary of the union. Pinned so that adding an instrument is
# a deliberate, visible edit — the ceiling above may only be raised in a change
# that also lands here, which is what separates a baseline correction from a
# regression being waved through.
INSTRUMENTS = frozenset(
    {
        "dict_literal",
        "emitter_call",
        "exit2",
        "return2",
        "decorated_emitter",
        "decision_object",
    }
)

_SHELL_COMMENT = re.compile(r"(?<!\\)#.*$")

# Shell refusal shapes: a decision key paired with a refusing value, or a
# call to a known emitter. Applied only after comment stripping.
_SHELL_DECISION = re.compile(
    r"[\"']?(" + "|".join(sorted(DECISION_KEYS)) + r")[\"']?\s*:\s*[\"'](" +
    "|".join(sorted(REFUSAL_DECISION_VALUES)) + r")[\"']"
)
_SHELL_EMITTER_CALL = re.compile(
    r"^\s*(" + "|".join(sorted(REFUSAL_EMITTER_NAMES)) + r")\b"
)
_SHELL_EXIT2 = re.compile(r"^\s*exit\s+2\s*$")


def _iter_hook_files(hooks_dir: Path) -> "list[Path]":
    """Return top-level hook scripts, Python and shell alike.

    Top-level only: ``archived/`` holds retired hooks that are never
    registered, and ``lib/``/``extensions/`` are not hooks.

    Args:
        hooks_dir: Directory of hook scripts to scan.

    Returns:
        Sorted list of ``*.py`` and ``*.sh`` paths directly inside the dir.
    """
    return sorted(
        p
        for p in hooks_dir.iterdir()
        if p.is_file() and p.suffix in (".py", ".sh")
    )


def _python_refusal_evidence(source: str) -> "list[str]":
    """Return AST-derived evidence that Python source can emit a refusal.

    AST is used rather than a regex specifically so that comments and
    docstrings are invisible by construction — that is the false positive
    which made a literal regex report ``validate_session_quality.py`` as a
    refuser on the strength of the phrase "instead of BLOCKS (exit 2)".

    Four instruments, unioned. Any one alone gives a wrong answer:

    * ``dict_literal`` — a decision key bound to a refusing literal value.
    * ``emitter_call`` — a known emitter called with a refusing first literal.
    * ``exit2`` — ``sys.exit(2)`` / ``exit(2)``, the exit-code refusal form.
    * ``return2`` — ``return 2`` from a ``safe_main``-wrapped hook, which
      ``hook_safety`` converts to ``sys.exit(2)``. Documented at
      ``hook_safety.py:439`` and implemented at ``hook_safety.py:514-516``;
      ``unified_prompt_validator.py:828`` refuses this way today. Bools are
      excluded explicitly, because ``True == 1`` in Python.
    * ``decorated_emitter`` — a function wrapped by ``block_event_decorator``,
      which is by definition a refusal emitter. This instrument alone catches
      ``unified_pre_tool.py``, whose refusals carry no literal anywhere.
    * ``decision_object`` (#1588) — a ``HookDecision`` refusal constructed for
      ``safe_main`` to emit. A migrated hook prints nothing, so without this
      instrument its refusal would be invisible to every other one.

    Args:
        source: Python source text.

    Returns:
        Sorted list of evidence strings; empty when no refusal is detectable.

    Raises:
        SyntaxError: If ``source`` does not parse.
    """
    tree = ast.parse(source)
    evidence: "set[str]" = set()

    for node in ast.walk(tree):
        # Instrument A: dict literal with a refusing decision value.
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value in DECISION_KEYS
                    and isinstance(value, ast.Constant)
                    and value.value in REFUSAL_DECISION_VALUES
                ):
                    evidence.add(f"dict_literal:{key.value}={value.value!r}")

        # Instrument B: a known emitter invoked with a refusing first literal.
        if isinstance(node, ast.Call):
            name = _called_name(node.func)
            if name in REFUSAL_EMITTER_NAMES and node.args:
                first = node.args[0]
                if (
                    isinstance(first, ast.Constant)
                    and first.value in REFUSAL_DECISION_VALUES
                ):
                    evidence.add(f"emitter_call:{name}({first.value!r})")
            # ``deny_and_record`` refuses by construction — it has no
            # decision argument to inspect, denying IS its only mode.
            if name in ("deny_and_record", "_deny_and_record"):
                evidence.add(f"emitter_call:{name}()")

            # Instrument E: the returned-decision-object refusal form.
            if decision_evidence := _decision_object_refusal(node):
                evidence.add(decision_evidence)

            # Instrument C: exit-code refusal.
            if name == "exit" and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and arg.value == 2:
                    evidence.add("exit2")

        # Instrument F: the RETURNED exit-code refusal form. safe_main turns
        # ``return 2`` into ``sys.exit(2)``, so this is the same refusal C
        # catches, written the way hook_safety's own docstring recommends.
        if isinstance(node, ast.Return) and _is_refusing_exit_constant(node.value):
            evidence.add("return2")

        # Instrument D: a function fused to the recorder by decoration is,
        # necessarily, the hook's refusal emitter.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if _called_name(target) == "block_event_decorator":
                    evidence.add(f"decorated_emitter:{node.name}")

    return sorted(evidence)


def _is_refusing_exit_constant(value: "ast.expr | None") -> bool:
    """Return True iff ``value`` is the literal ``2``, and not a bool.

    ``isinstance(True, int)`` is True in Python and ``True == 1``, so an
    identity check on the constant is not enough — the bool type must be
    excluded explicitly or a ``return True`` would be read as an exit code.
    No bool equals 2, so this cannot currently misfire; the guard is here
    because the *class* of confusion is one edit away, not because ``True``
    is a live hazard.

    Args:
        value: The returned expression, or None for a bare ``return``.

    Returns:
        True when the expression is the integer constant 2.
    """
    return (
        isinstance(value, ast.Constant)
        and not isinstance(value.value, bool)
        and value.value == 2
    )


def _decision_object_refusal(node: ast.Call) -> str:
    """Return evidence that ``node`` builds a ``HookDecision`` REFUSAL.

    Value-aware for the same reason instrument A is: a migrated hook may build
    ``HookDecision(decision="allow", ...)`` on its permitting path, and a
    name-only match would report every such hook as a refuser.

    Two shapes are recognised:

    * ``HookDecision.deny(...)`` — a factory that refuses by construction and
      carries no decision argument to inspect.
    * ``HookDecision(decision="deny"|"ask"|"block", ...)`` — the direct
      constructor, positional or keyword.

    Args:
        node: A call node.

    Returns:
        An evidence string, or ``""`` when the call is not a refusal.
    """
    func = node.func

    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == DECISION_OBJECT_NAME
    ):
        if func.attr in DECISION_OBJECT_REFUSAL_FACTORIES:
            return f"decision_object:{DECISION_OBJECT_NAME}.{func.attr}()"
        return ""

    if isinstance(func, ast.Name) and func.id == DECISION_OBJECT_NAME:
        for keyword in node.keywords:
            if (
                keyword.arg == "decision"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value in REFUSAL_DECISION_VALUES
            ):
                return (
                    f"decision_object:{DECISION_OBJECT_NAME}"
                    f"(decision={keyword.value.value!r})"
                )
        for arg in node.args:
            if isinstance(arg, ast.Constant) and arg.value in REFUSAL_DECISION_VALUES:
                return f"decision_object:{DECISION_OBJECT_NAME}({arg.value!r})"

    return ""


def _called_name(func: ast.expr) -> str:
    """Return the bare callable name for a call target.

    ``sys.exit(2)`` and ``exit(2)`` both yield ``"exit"``; an aliased import
    yields the alias. Bare-name matching is deliberate — see limitation 5 in
    the module docstring.

    Args:
        func: The ``func`` expression of an ``ast.Call``.

    Returns:
        The identifier, or ``""`` for call targets that are not simple names.
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _shell_refusal_evidence(source: str) -> "list[str]":
    """Return regex-derived evidence that shell source can emit a refusal.

    Comments are stripped first so that shell prose describing a refusal is
    not mistaken for one — the shell analogue of the comment false positive.
    Shell is NOT parsed; see limitation 2 in the module docstring.

    Args:
        source: Shell source text.

    Returns:
        Sorted list of evidence strings; empty when no refusal is detectable.
    """
    evidence: "set[str]" = set()
    for raw_line in source.splitlines():
        line = _SHELL_COMMENT.sub("", raw_line)
        match = _SHELL_DECISION.search(line)
        if match:
            evidence.add(f"dict_literal:{match.group(1)}={match.group(2)!r}")
        call = _SHELL_EMITTER_CALL.search(line)
        if call:
            evidence.add(f"emitter_call:{call.group(1)}()")
        if _SHELL_EXIT2.search(line):
            evidence.add("exit2")
    return sorted(evidence)


def _refusal_evidence(path: Path) -> "list[str]":
    """Dispatch to the language-appropriate refusal instrument.

    Args:
        path: Hook script path.

    Returns:
        Sorted evidence strings; empty when no refusal is detectable.

    Raises:
        SyntaxError: If a ``.py`` hook does not parse. Deliberately loud — a
            hook this guard cannot parse is a hook it cannot vouch for, and
            silently skipping it is how a ratchet quietly stops guarding.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".py":
        try:
            return _python_refusal_evidence(source)
        except SyntaxError as exc:
            raise SyntaxError(
                f"{path.name} does not parse, so its refusal surface cannot be "
                f"audited: {exc}"
            ) from exc
    return _shell_refusal_evidence(source)


def _sink_evidence(path: Path) -> "list[str]":
    """Return which sanctioned sinks a hook actually USES.

    Two independent facts are required, because either alone is launderable
    by a token:

    1. **Binding** — the name arrives from the module that defines it, either
       as ``from hook_safety|hook_telemetry import <sink>`` (alias honoured)
       or as a module-qualified attribute access (``mod.block_event_decorator``,
       which is how ``unified_pre_tool.py`` obtains its decorator).
    2. **Call position** — the bound name is called, is the receiver of a
       called attribute (``HookDecision.deny(...)``), or is applied as a
       decorator.

    Bare-name matching was the previous rule, and it classified as in-sink any
    file containing ``HookDecision = None`` — the exact line the migrated
    reference hook ships, so an author copying it inherits the laundering
    token without intending to. Requiring the call closes that; requiring the
    binding closes the variant where the import is copied too.

    Shell hooks keep the bare regex: they have no imports, and
    ``PreToolUseWrite-protect-sensitive.sh`` defines its own fusing
    ``deny_and_record`` shell function. See limitation 5.

    Args:
        path: Hook script path.

    Returns:
        Sorted sanctioned-sink names the file both binds and calls.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".sh":
        stripped = "\n".join(_SHELL_COMMENT.sub("", ln) for ln in source.splitlines())
        return sorted(s for s in SANCTIONED_SINKS if re.search(rf"\b{s}\b", stripped))

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # local name -> canonical sink name
    bound: "dict[str, str]" = {}
    called: "set[str]" = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").rsplit(".", 1)[-1]
            if module in SINK_MODULES:
                for alias in node.names:
                    if alias.name in SANCTIONED_SINKS:
                        bound[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Attribute) and node.attr in SANCTIONED_SINKS:
            # ``_hook_telemetry_mod.block_event_decorator`` — module-qualified
            # access is provenance evidence just as an import is.
            bound.setdefault(node.attr, node.attr)

        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
                if isinstance(func.value, ast.Name):
                    called.add(func.value.id)
                elif isinstance(func.value, ast.Attribute):
                    called.add(func.value.attr)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                name = _called_name(target)
                if name:
                    called.add(name)

    return sorted({sink for local, sink in bound.items() if local in called})


def refusal_candidates(hooks_dir: Path = HOOKS_DIR) -> "dict[str, list[str]]":
    """Enumerate hooks that can emit a refusal, by the union of instruments.

    Args:
        hooks_dir: Directory of hook scripts to scan.

    Returns:
        Mapping of hook filename to its refusal evidence, for hooks with any.

    Raises:
        SyntaxError: If a ``.py`` hook does not parse.
    """
    return {
        path.name: evidence
        for path in _iter_hook_files(hooks_dir)
        if (evidence := _refusal_evidence(path))
    }


def out_of_sink_refusers(hooks_dir: Path = HOOKS_DIR) -> "list[str]":
    """THE RULE: hooks that can refuse and reference no sanctioned sink.

    Factored out so the live corpus and every synthetic control drive the
    IDENTICAL code path. A control that re-implements the rule proves nothing
    about the rule.

    Args:
        hooks_dir: Directory of hook scripts to scan.

    Returns:
        Sorted filenames of refusal-capable hooks with no sanctioned sink.

    Raises:
        SyntaxError: If a ``.py`` hook does not parse.
    """
    offenders = []
    for path in _iter_hook_files(hooks_dir):
        if _refusal_evidence(path) and not _sink_evidence(path):
            offenders.append(path.name)
    return sorted(offenders)


class TestInstrumentPremises:
    """Verify the instrument before trusting one cell of its output."""

    def test_corpus_is_populated(self):
        """An empty glob would make every rule below vacuously true."""
        files = _iter_hook_files(HOOKS_DIR)
        assert len(files) >= 20, (
            f"Expected the full hook corpus, found {len(files)} in {HOOKS_DIR}. "
            f"Verify HOOKS_DIR points at the tracked source."
        )
        assert any(p.suffix == ".sh" for p in files), (
            "No shell hooks discovered — a Python-only glob is one of the four "
            "instruments that gave a wrong answer (it missed "
            "PreToolUseWrite-protect-sensitive.sh entirely)."
        )

    def test_refusal_candidates_is_non_empty(self):
        """A detector that finds nothing is not evidence of nothing."""
        candidates = refusal_candidates()
        assert candidates, (
            "Zero refusal candidates discovered across the entire hook corpus. "
            "That is an instrument failure, not a clean repo."
        )

    def test_positive_control_largest_refuser_is_detected(self):
        """``unified_pre_tool.py`` must be found despite having no literals.

        The single largest refuser in the repo (8,093 recorded blocks) carries
        ZERO refusal literals — it refuses exclusively through a decorated
        function. A literal-only instrument misses it. This pins the
        ``decorated_emitter`` instrument as load-bearing.
        """
        candidates = refusal_candidates()
        assert "unified_pre_tool.py" in candidates, (
            "unified_pre_tool.py was not detected as refusal-capable. The "
            "decorated_emitter instrument has regressed and the union is back "
            "to missing the repo's largest refuser."
        )
        evidence = candidates["unified_pre_tool.py"]
        assert any(e.startswith("decorated_emitter:") for e in evidence), (
            f"unified_pre_tool.py was detected, but not via the instrument "
            f"that is supposed to catch it. Evidence: {evidence}"
        )

    def test_negative_control_comment_prose_is_not_a_refusal(self):
        """``validate_session_quality.py`` warns; a regex called it a blocker.

        Its line 10 reads ``- WARNS (exit 1) instead of BLOCKS (exit 2)``. A
        decision-literal regex matched that prose. AST cannot see comments, so
        this asserts the false positive stays dead — and asserts the premise
        (the prose is still there) so the control cannot pass vacuously.
        """
        path = HOOKS_DIR / "validate_session_quality.py"
        assert path.exists(), "premise: the hook that produced the FP still exists"
        assert "BLOCKS (exit 2)" in path.read_text(encoding="utf-8"), (
            "premise: the comment prose that produced the false positive is "
            "still present. If it was reworded, this control no longer "
            "exercises the comment-blindness case — pick another instance."
        )
        assert "validate_session_quality.py" not in refusal_candidates(), (
            "validate_session_quality.py is reported as refusal-capable. It "
            "only warns (exit 1); the detector is matching comment prose again."
        )

    def test_negative_control_allow_only_hook_is_not_a_refusal(self):
        """``enforce_tier_distribution.py`` has 11 decision keys, all ``allow``.

        A key-only regex reports it as a refuser. This pins value-awareness.
        """
        path = HOOKS_DIR / "enforce_tier_distribution.py"
        assert path.exists(), "premise: the allow-only hook still exists"
        assert "permissionDecision" in path.read_text(encoding="utf-8"), (
            "premise: the hook still carries decision keys, so a key-only "
            "instrument would still flag it"
        )
        assert "enforce_tier_distribution.py" not in refusal_candidates(), (
            "enforce_tier_distribution.py is reported as refusal-capable, but "
            "every one of its decision values is 'allow'. The detector has "
            "lost value-awareness."
        )

    def test_shell_hook_is_detected_by_the_union(self):
        """The Python-only glob missed this file; the union must not."""
        candidates = refusal_candidates()
        assert "PreToolUseWrite-protect-sensitive.sh" in candidates, (
            "The shell hook was not detected as refusal-capable. The union has "
            "regressed to Python-only, one of the four wrong answers."
        )


class TestSanctionedSinkDefinition:
    """Pin the sink-versus-set decision so it cannot drift silently."""

    def test_sink_is_exactly_the_fusing_paths(self):
        """The sink is the fusing paths and nothing else — not the recorders."""
        assert SANCTIONED_SINKS == {
            "deny_and_record",
            "block_event_decorator",
            "HookDecision",
        }, (
            f"SANCTIONED_SINKS changed to {sorted(SANCTIONED_SINKS)}. The "
            f"membership rule is FUSION: a refusal cannot be obtained without "
            f"the recording happening in the same act. Adding a bare recorder "
            f"here would collapse a distinct property into a weaker one and "
            f"the ratchet would stop tracking the hooks it exists to track. "
            f"Adding a genuinely new fusing MECHANISM (as #1588 did with "
            f"HookDecision) is legitimate and must be accompanied by a "
            f"fusion-premise test below. See the module docstring."
        )

    def test_bare_recorders_are_not_sinks(self):
        """``log_block_event``/``log_block_with_recovery`` fuse nothing."""
        overlap = SANCTIONED_SINKS & UNFUSED_RECORDERS
        assert not overlap, (
            f"{sorted(overlap)} is classified as a sanctioned sink. These are "
            f"bare recorders: calling one is a SECOND act adjacent to the "
            f"refusal, which is exactly the forgettable convention Issue #1587 "
            f"identified as the defect class."
        )

    def test_deny_and_record_really_does_fuse(self):
        """Premise: the sink's fusion claim is true in the source.

        If ``deny_and_record`` ever stopped recording, every in-sink
        classification in this module would be silently wrong.
        """
        source = (
            PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "hook_telemetry.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        fn = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "deny_and_record"
            ),
            None,
        )
        assert fn is not None, "hook_telemetry.deny_and_record no longer exists"
        calls = {_called_name(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        assert "log_block_event" in calls, (
            "deny_and_record no longer calls log_block_event, so it does not "
            "fuse recording to refusal and is not a sink."
        )

    def test_block_event_decorator_really_does_fuse(self):
        """Premise: the decorator sink records on deny."""
        source = (
            PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "hook_telemetry.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        fn = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "block_event_decorator"
            ),
            None,
        )
        assert fn is not None, "hook_telemetry.block_event_decorator no longer exists"
        calls = {_called_name(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        assert "log_block_event" in calls, (
            "block_event_decorator no longer calls log_block_event, so it does "
            "not fuse recording to refusal and is not a sink."
        )


    def test_hook_decision_really_does_fuse(self):
        """Premise: ``safe_main`` emits AND records a returned refusal.

        The other two premises above are satisfied by an AST check because
        those sinks fuse *within one function*. This one fuses across the
        wrapper boundary, so the check is behavioural: drive the real
        ``safe_main`` with a real refusal and assert BOTH acts happened.

        Without this, ``HookDecision`` would be a name on a list, and every
        in-sink classification that rests on it would be unverified.
        """
        import io
        import json as _json
        import sys as _sys
        from contextlib import redirect_stdout

        # Import the modules the hooks themselves import, from the tracked
        # source tree — not a bespoke importlib copy. Verify the code that
        # executes.
        lib = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
        if str(lib) not in _sys.path:
            _sys.path.insert(0, str(lib))
        import hook_safety
        import hook_telemetry

        assert Path(hook_safety.__file__).resolve() == (lib / "hook_safety.py"), (
            f"imported hook_safety from {hook_safety.__file__}, not the "
            f"tracked source — the premise would be about the wrong copy"
        )

        recorded: "list[dict]" = []

        original = hook_telemetry.log_block_event
        hook_telemetry.log_block_event = (
            lambda **kw: recorded.append(kw)  # type: ignore[assignment]
        )
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer), pytest.raises(SystemExit):
                hook_safety.safe_main(
                    lambda: hook_safety.HookDecision.deny(
                        hook_name="premise.py", reason="nope"
                    )
                )
        finally:
            hook_telemetry.log_block_event = original

        emitted = _json.loads(buffer.getvalue().strip())
        assert (
            emitted["hookSpecificOutput"]["permissionDecision"] == "deny"
        ), "safe_main did not EMIT the returned refusal — half the fusion"
        assert recorded and recorded[0]["hook_name"] == "premise.py", (
            "safe_main did not RECORD the returned refusal, so HookDecision "
            "does not fuse and is not a sink."
        )


class TestRatchet:
    """The pinned out-of-sink set may only shrink."""

    def test_no_new_out_of_sink_refusers(self):
        """THE RATCHET. A newly-unfused refusal fails here, named.

        Adding the offender to ``PINNED_OUT_OF_SINK`` is NOT an acceptable
        resolution — the ceiling below refuses it.
        """
        live = set(out_of_sink_refusers())
        new = sorted(live - PINNED_OUT_OF_SINK)
        assert not new, (
            f"Hook(s) refuse outside the sanctioned sink: {new}\n"
            f"Expected: route the refusal through "
            f"hook_telemetry.deny_and_record(), or decorate the hook's sole "
            f"refusal emitter with block_event_decorator(). Both fuse the "
            f"recording to the refusal so no path can refuse silently.\n"
            f"Adding the file to PINNED_OUT_OF_SINK is NOT a resolution: the "
            f"set has a ceiling of {PINNED_CEILING} and may only shrink.\n"
            f"See: plugins/autonomous-dev/lib/hook_telemetry.py"
        )

    def test_pinned_entries_are_still_genuinely_out_of_sink(self):
        """A migrated hook must be REMOVED from the pin, not left behind.

        This is the arm that makes the ratchet actually shrink: once a pinned
        hook routes through the sink, it drops out of the live set and the
        stale pin fails until it is deleted. Without this, the set would be a
        permanent parking lot.
        """
        live = set(out_of_sink_refusers())
        stale = sorted(PINNED_OUT_OF_SINK - live)
        assert not stale, (
            f"PINNED_OUT_OF_SINK names {stale}, which no longer refuse outside "
            f"the sink (or no longer refuse at all). Delete them from the set — "
            f"that deletion IS the ratchet advancing."
        )

    def test_pinned_set_has_a_ceiling(self):
        """The escape hatch cannot grow SILENTLY. An uncapped hatch is decorative.

        Two assertions, guarding two different failures. Neither replaces the
        other, and the first one is why:

        * **The literal is the anti-GROWTH tripwire.** Tying the ceiling only
          to ``len(PINNED_OUT_OF_SINK)`` makes both operands constants in this
          file, so a change that adds a pinned entry and bumps the ceiling in
          the same edit moves them together and nothing fires. That bypass was
          measured green. ``<=`` rather than ``==`` because the direction is
          the whole point: LOWERING is the ratchet advancing and must never be
          blocked, while raising has exactly one honest justification, named in
          the message below.
        * **The equality is the anti-SLACK tripwire.** A ceiling above the set
          is a pre-authorised exemption for the next hook that fails.

        See ``TestCeilingIsNotATautology`` for both arms driven end to end.
        """
        assert len(PINNED_OUT_OF_SINK) <= PINNED_CEILING, (
            f"PINNED_OUT_OF_SINK has grown to {len(PINNED_OUT_OF_SINK)} entries "
            f"{sorted(PINNED_OUT_OF_SINK)}, over the ceiling of "
            f"{PINNED_CEILING}. A hook was added to the exemption list instead "
            f"of being migrated to the sink. Migrate it."
        )
        assert PINNED_CEILING <= 5, (
            f"PINNED_CEILING was RAISED to {PINNED_CEILING}. LOWER it freely — "
            f"that is the ratchet advancing and this assertion never sees it. "
            f"RAISING it is honest in exactly one case: a NEW INSTRUMENT made "
            f"PRE-EXISTING offenders visible. To take that case, in ONE diff: "
            f"name the instrument here, add it to INSTRUMENTS, and justify each "
            f"new entry in the PINNED_OUT_OF_SINK comment. Anything else is a "
            f"hook being pinned instead of migrated — migrate it. 3 -> 6 was "
            f"such a case (`return2`, revealing enforce_tdd.py / "
            f"enforce_prunable_threshold.py / enforce_regression_test.py, all "
            f"pre-existing bare `return 2` with zero recorder calls; see "
            f"test_return_two_pins_are_genuinely_unrecorded). 6 -> 5 (#1611) "
            f"was a MIGRATION, which needs no justification at all."
        )
        assert PINNED_CEILING == len(PINNED_OUT_OF_SINK), (
            f"PINNED_CEILING ({PINNED_CEILING}) no longer equals the pinned set "
            f"size ({len(PINNED_OUT_OF_SINK)}). Slack in the ceiling is a "
            f"pre-authorised exemption for the next hook that fails. Lower the "
            f"ceiling to match — that IS the ratchet advancing."
        )

    def test_instrument_vocabulary_is_pinned(self):
        """Adding an instrument must be deliberate, not incidental.

        What this test enforces, precisely: every instrument that produced
        evidence over the live corpus is named in ``INSTRUMENTS``, and
        ``return2`` has not been dropped. A new detection form therefore cannot
        reach the corpus without an edit here.

        What it does NOT enforce: it does not reference ``PINNED_CEILING`` and
        cannot make a ceiling raise co-occur with an instrument addition. That
        co-occurrence is a rule addressed to the human raising the ceiling, and
        it lives where they will read it — the failure message on
        ``test_pinned_set_has_a_ceiling``'s literal, which is what actually
        refuses the raise.
        """
        live: "set[str]" = set()
        for evidence in refusal_candidates().values():
            for item in evidence:
                live.add(item.split(":", 1)[0])
        unknown = sorted(live - INSTRUMENTS)
        assert not unknown, (
            f"the live corpus produced evidence from unpinned instrument(s) "
            f"{unknown}. Add them to INSTRUMENTS deliberately — and if the "
            f"addition reveals pre-existing out-of-sink hooks, say so in the "
            f"PINNED_OUT_OF_SINK comment rather than quietly widening the set."
        )
        assert "return2" in INSTRUMENTS, (
            "the `return 2` instrument was removed. hook_safety.py:439 "
            "documents that form and hook_safety.py:514-516 implements it, so "
            "dropping it makes the repo's own documented refusal convention "
            "invisible to this guard again."
        )

    def test_return_two_pins_are_genuinely_unrecorded(self):
        """Premise for the ceiling raise: these three really do record nothing.

        The raise 3 -> 6 rests on the claim that ``return2`` revealed hooks
        that were always out of sink, not that three hooks regressed. If any
        of them were in fact recording, the honest classification would be
        different and the raise would be unjustified — so the claim is checked
        against the source rather than asserted in a comment.
        """
        for name in (
            "enforce_tdd.py",
            "enforce_prunable_threshold.py",
            "enforce_regression_test.py",
        ):
            path = HOOKS_DIR / name
            assert path.exists(), f"premise: {name} still exists"
            assert _refusal_evidence(path) == ["return2"], (
                f"{name} refuses by some form other than `return 2` now; "
                f"re-derive its classification"
            )
            source = path.read_text(encoding="utf-8")
            for recorder in ("log_block_event", "deny_and_record"):
                assert recorder not in source, (
                    f"{name} now references {recorder}. If it started "
                    f"recording, revisit whether it still belongs in "
                    f"PINNED_OUT_OF_SINK — and lower PINNED_CEILING with it."
                )

    def test_plan_gate_migration_holds(self):
        """Issue #1611: plan_gate is IN the sink now, and must stay there.

        The ratchet advancing is only durable if the advance itself is pinned.
        Three assertions, because "not flagged" alone is satisfiable by the
        detector going blind:

        1. It is still SEEN as a refuser — it did not leave the live set by
           becoming invisible.
        2. It is not flagged — it routes through a sanctioned sink.
        3. It is gone from ``PINNED_OUT_OF_SINK`` — the deletion IS the
           ratchet advancing, and re-adding it would need a ceiling raise
           that ``test_pinned_set_has_a_ceiling`` refuses.
        """
        candidates = refusal_candidates()
        assert "plan_gate.py" in candidates, (
            "plan_gate.py is no longer detected as refusal-capable. It still "
            "calls _output_decision('block', ...) on two paths, so this is an "
            "instrument regression, not a migration."
        )
        assert "plan_gate.py" not in out_of_sink_refusers(), (
            f"plan_gate.py refuses outside the sanctioned sink again. Its "
            f"sink evidence is {_sink_evidence(HOOKS_DIR / 'plan_gate.py')}; "
            f"expected block_event_decorator on _output_decision (#1611)."
        )
        assert "plan_gate.py" not in PINNED_OUT_OF_SINK, (
            "plan_gate.py was migrated in #1611 and must not be re-pinned."
        )

    def test_in_sink_refusers_are_permitted(self):
        """A guard that fails on everything is not a guard.

        The three migrated/fused hooks refuse and MUST pass. This watches the
        rule PERMITTING, which is the arm a refusal-only guard never proves.
        """
        candidates = refusal_candidates()
        live = set(out_of_sink_refusers())
        for name in (
            "unified_pre_tool.py",
            "enforce_file_organization.py",
            "PreToolUseWrite-protect-sensitive.sh",
        ):
            assert name in candidates, (
                f"premise: {name} is detected as refusal-capable, so its "
                f"permission below is meaningful rather than vacuous"
            )
            assert name not in live, (
                f"{name} routes its refusals through a sanctioned sink "
                f"({_sink_evidence(HOOKS_DIR / name)}) but the rule flagged it. "
                f"The guard is refusing a legitimate case."
            )


class TestCeilingIsNotATautology:
    """FINDING-8. The ceiling must fail on GROWTH, not merely on disagreement.

    The ceiling briefly consisted only of ``PINNED_CEILING ==
    len(PINNED_OUT_OF_SINK)``. Both operands are constants in this file, so a
    change that adds a pinned entry AND bumps the ceiling in the same edit
    moves them together and the assertion never fires — the anti-growth
    tripwire had been replaced by an anti-slack one. Measured, not argued:
    running the ceiling test against a mutant with both edits applied was
    GREEN.

    These tests drive the real ``test_pinned_set_has_a_ceiling`` over mutated
    copies of THIS module, in a subprocess, and assert the outcome. The
    instrument gets both controls: the unmutated copy must pass (so a red
    result means the mutation, not the harness), and the growth mutant must
    fail (so a green result means the ceiling, not an inert assertion).
    """

    #: Anchors mutated below. Each is asserted unique before substitution, so a
    #: refactor that moves them makes this harness fail loudly rather than
    #: silently mutate nothing and report a false green.
    _CEILING_ANCHOR = "\nPINNED_CEILING = 5\n"
    _ADD_ANCHOR = '        "unified_prompt_validator.py",\n'
    _DROP_ANCHOR = '        "enforce_regression_test.py",\n    }\n)'

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
    def _run_ceiling_test(tmp_path: Path, source: str) -> "subprocess.CompletedProcess":
        """Run only ``test_pinned_set_has_a_ceiling`` over ``source``.

        Restricted with ``-k`` because the ceiling test reads nothing but the
        two constants: the copy runs out-of-tree, so the corpus-reading tests
        in this module would fail for an unrelated reason and blur the signal.
        """
        mutant = tmp_path / "test_ceiling_mutant.py"
        mutant.write_text(source, encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(mutant),
                "-k",
                "test_pinned_set_has_a_ceiling",
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

    def test_regression_issue_1588_growing_the_pin_and_the_ceiling_together_fails(
        self, tmp_path
    ):
        """THE REPRODUCER, and the refusing arm. Growth must be RED.

        This is the exact bypass measured against the tautological form: add a
        member to ``PINNED_OUT_OF_SINK`` and raise ``PINNED_CEILING`` by one in
        the same edit. Under ``PINNED_CEILING == len(PINNED_OUT_OF_SINK)`` the
        two operands move together and nothing fires. A literal beside the
        equality is what makes the raise visible.

        The mutant's added entry is a name no live hook carries, so this
        exercises the ceiling itself rather than the corpus detector.
        """
        source = self._substitute(
            self._source(),
            self._ADD_ANCHOR,
            self._ADD_ANCHOR + '        "synthetic_growth_offender.py",\n',
        )
        source = self._substitute(source, self._CEILING_ANCHOR, "\nPINNED_CEILING = 6\n")

        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode != 0, (
            "PINNED_OUT_OF_SINK grew to 6 with the ceiling raised to match, and "
            "the ceiling test still PASSED. The escape hatch has no ceiling: "
            "the next hook that fails the ratchet can be pinned instead of "
            "migrated, by a two-constant edit that no assertion sees.\n"
            f"{result.stdout}"
        )
        assert "PINNED_CEILING" in result.stdout, (
            f"the mutant failed for some reason other than the ceiling "
            f"assertion, so this proves nothing about it.\n{result.stdout}"
        )

    def test_shrinking_the_pin_and_the_ceiling_together_is_permitted(self, tmp_path):
        """THE PERMITTING ARM. Lowering is the ratchet advancing — never blocked.

        Deliberately the opposite direction from the reproducer. A ceiling
        pinned with ``==`` to a literal would catch the growth above and then
        block the migration this whole module exists to produce, converting the
        fix into a new defect.
        """
        source = self._substitute(self._source(), self._DROP_ANCHOR, "    }\n)")
        source = self._substitute(source, self._CEILING_ANCHOR, "\nPINNED_CEILING = 4\n")

        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode == 0, (
            "a hook was MIGRATED out of PINNED_OUT_OF_SINK and the ceiling "
            "lowered to match, and the ceiling test refused it. Lowering is the "
            "ratchet advancing and needs no justification; blocking it creates "
            "pressure to leave migrated hooks pinned.\n"
            f"{result.stdout}\n{result.stderr}"
        )

    def test_raising_the_ceiling_alone_still_fails(self, tmp_path):
        """The anti-slack arm, kept: a ceiling above the set is a pre-authorisation.

        Slack means the next hook to fail the ratchet is already exempt. This
        arm is what the equality earned; it is retained, not replaced.
        """
        source = self._substitute(
            self._source(), self._CEILING_ANCHOR, "\nPINNED_CEILING = 6\n"
        )
        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode != 0, (
            f"PINNED_CEILING was raised to 6 while the set stayed at 5 and "
            f"nothing fired. That is a pre-authorised exemption.\n{result.stdout}"
        )


class TestNegativeControls:
    """Watch the rule REFUSING and PERMITTING, on shapes it did not start from.

    Every control drives ``out_of_sink_refusers`` — the same function the live
    rule uses — over a synthetic corpus. The synthetic refusals are
    deliberately a DIFFERENT shape from the three live pinned hooks (which use
    ``_output_decision("block")``, a ``{"decision": "block"}`` dict, and
    ``sys.exit(2)``): the controls below refuse via ``permissionDecision:
    "ask"`` and via ``output_decision("deny", ...)``, neither of which any live
    hook emits as a literal. A control shaped like the reproducer proves only
    that the reproducer is still matched.
    """

    @staticmethod
    def _write(tmp_path: Path, name: str, body: str) -> Path:
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_control_synthetic_unfused_refuser_is_flagged_and_named(self, tmp_path):
        """A hook that refuses and records nothing → flagged."""
        self._write(
            tmp_path,
            "synthetic_unfused.py",
            'import json\n'
            'def main():\n'
            '    print(json.dumps({"hookSpecificOutput": {\n'
            '        "permissionDecision": "ask",\n'
            '        "permissionDecisionReason": "nope",\n'
            '    }}))\n',
        )
        assert out_of_sink_refusers(tmp_path) == ["synthetic_unfused.py"], (
            "the rule failed to flag a hook that refuses without recording — "
            "it does not detect the class it exists to detect"
        )

    def test_control_synthetic_fused_refuser_is_permitted(self, tmp_path):
        """A hook that refuses THROUGH the sink → permitted.

        The permitting arm. Without it, a rule that flags every file would
        pass every refusal control above while being worthless.
        """
        self._write(
            tmp_path,
            "synthetic_fused.py",
            'import json\n'
            'from hook_telemetry import deny_and_record\n'
            'def main():\n'
            '    print(json.dumps(deny_and_record(\n'
            '        hook_name="synthetic_fused.py", reason="nope")))\n',
        )
        assert out_of_sink_refusers(tmp_path) == [], (
            "a hook refusing through hook_telemetry.deny_and_record was "
            "flagged. The guard refuses the sanctioned path."
        )

    def test_control_both_arms_in_one_corpus(self, tmp_path):
        """Refusing and permitting, discriminated within a single scan.

        Proves the rule separates the two rather than keying on some property
        of the corpus as a whole.
        """
        self._write(
            tmp_path,
            "aaa_unfused.py",
            'print({"decision": "deny"})\n',
        )
        self._write(
            tmp_path,
            "bbb_decorated.py",
            'from hook_telemetry import block_event_decorator\n'
            '@block_event_decorator("bbb_decorated.py")\n'
            'def output_decision(decision, reason):\n'
            '    print(decision, reason)\n',
        )
        self._write(
            tmp_path,
            "ccc_never_refuses.py",
            'print({"permissionDecision": "allow"})\n',
        )
        assert out_of_sink_refusers(tmp_path) == ["aaa_unfused.py"], (
            "the rule did not discriminate: expected only the unfused refuser, "
            f"got {out_of_sink_refusers(tmp_path)}"
        )
        candidates = refusal_candidates(tmp_path)
        assert "bbb_decorated.py" in candidates, (
            "the decorated hook must still be RECOGNISED as a refuser — it is "
            "permitted because it is fused, not because it is invisible"
        )
        assert "ccc_never_refuses.py" not in candidates, (
            "an allow-only hook must not be a refusal candidate at all"
        )

    def test_control_bare_recorder_does_not_launder_a_refusal(self, tmp_path):
        """Calling ``log_block_event`` next to a refusal is still out-of-sink.

        This is the sink-versus-set decision under test. The synthetic hook
        DOES write a telemetry row — so a rule keyed on "does a row appear"
        would permit it. It must still be flagged, because refusing and
        recording are two acts here and the second is forgettable. This is the
        exact shape of the two live pinned hooks that do record today.
        """
        self._write(
            tmp_path,
            "synthetic_two_act.py",
            'from hook_telemetry import log_block_event\n'
            'def main():\n'
            '    log_block_event(hook_name="synthetic_two_act.py",\n'
            '                    decision_shape="dict", reason="nope")\n'
            '    print({"permissionDecision": "deny"})\n',
        )
        assert out_of_sink_refusers(tmp_path) == ["synthetic_two_act.py"], (
            "a two-act hook (bare recorder beside a refusal) was permitted. "
            "log_block_event has been admitted as a sink, which collapses the "
            "fusion property the sink is defined on."
        )

    def test_control_decision_object_refuser_is_permitted(self, tmp_path):
        """A hook that returns a ``HookDecision`` refusal → permitted.

        The permitting arm for instrument E's sink. Note this hook contains no
        ``print``, no decision dict literal and no ``exit(2)`` — it is
        invisible to instruments A, B, C and D, which is exactly why E exists.
        """
        self._write(
            tmp_path,
            "synthetic_decision_object.py",
            "from hook_safety import HookDecision, safe_main\n"
            "def main():\n"
            '    return HookDecision.deny(hook_name="x", reason="nope")\n'
            'if __name__ == "__main__":\n'
            "    safe_main(main)\n",
        )
        assert out_of_sink_refusers(tmp_path) == [], (
            "a hook refusing by returning a HookDecision to safe_main was "
            "flagged. The guard refuses the sanctioned #1588 path."
        )
        assert "synthetic_decision_object.py" in refusal_candidates(tmp_path), (
            "the hook must still be RECOGNISED as a refuser — it is permitted "
            "because it is fused, not because instrument E cannot see it"
        )

    def test_control_decision_object_is_invisible_to_the_older_instruments(
        self, tmp_path
    ):
        """Premise for the control above: E is load-bearing, not redundant.

        If instruments A-D already caught this shape, the permitting control
        would pass with E deleted and E would be decorative. This drives the
        SAME source through the pre-#1588 instrument set and asserts it sees
        nothing.
        """
        source = (
            "from hook_safety import HookDecision\n"
            "def main():\n"
            '    return HookDecision.deny(hook_name="x", reason="nope")\n'
        )
        evidence = _python_refusal_evidence(source)
        assert evidence == ["decision_object:HookDecision.deny()"], (
            f"expected instrument E to be the ONLY instrument that fires on "
            f"the returned-decision form; got {evidence}"
        )

    def test_control_decision_object_allow_is_not_a_refusal(self, tmp_path):
        """Boundary, and one case past it: ``allow`` must not read as refusal.

        Instrument E must be value-aware for the same reason instrument A is —
        a migrated hook builds decisions on its permitting path too, and a
        name-only match would report every migrated hook as a refuser.
        """
        self._write(
            tmp_path,
            "synthetic_decision_allow.py",
            "from hook_safety import HookDecision\n"
            "def main():\n"
            '    return HookDecision(decision="allow", reason="fine")\n',
        )
        assert refusal_candidates(tmp_path) == {}, (
            f"HookDecision(decision='allow') was matched as a refusal: "
            f"{refusal_candidates(tmp_path)}"
        )

    def test_control_decision_object_direct_constructor_refusal_is_seen(
        self, tmp_path
    ):
        """The keyword-constructor shape, not just the ``.deny()`` factory.

        The hook imports the sink from ``hook_safety`` and calls it, which is
        what sink membership now requires — a bare ``HookDecision`` token no
        longer confers it (see
        ``test_control_laundering_token_does_not_confer_sink_membership``).
        """
        self._write(
            tmp_path,
            "synthetic_decision_kwarg.py",
            "from hook_safety import HookDecision\n"
            "def main():\n"
            '    return HookDecision(decision="ask", reason="hmm")\n',
        )
        assert out_of_sink_refusers(tmp_path) == [], (
            "the hook imports HookDecision from hook_safety and calls it, so "
            "it is in-sink; the assertion below is what proves it was SEEN"
        )
        assert refusal_candidates(tmp_path) == {
            "synthetic_decision_kwarg.py": [
                "decision_object:HookDecision(decision='ask')"
            ]
        }, f"got {refusal_candidates(tmp_path)}"

    def test_control_return_two_is_a_refusal(self, tmp_path):
        """The DOCUMENTED refusal form the union was blind to.

        ``hook_safety.safe_main`` documents (line 439) and implements
        (lines 514-516) ``return 2`` as a refusal, and a live hook uses it
        (``unified_prompt_validator.py:828``). Instrument C matched only
        ``sys.exit(2)``/``exit(2)``, so the honest answer to "can a newly
        written hook refuse outside the sink?" was YES — by following the
        convention the repo itself documents.

        The synthetic hook is shaped like a real one (``safe_main(main)``
        entry point, no literals anywhere) rather than like the reproducer.
        """
        self._write(
            tmp_path,
            "synthetic_return2.py",
            "import sys\n"
            "from hook_safety import safe_main\n"
            "def main():\n"
            '    sys.stderr.write("BLOCKED: nope\\n")\n'
            "    return 2\n"
            'if __name__ == "__main__":\n'
            "    safe_main(main)\n",
        )
        assert refusal_candidates(tmp_path) == {
            "synthetic_return2.py": ["return2"]
        }, (
            f"a hook refusing via the documented `return 2` convention is "
            f"invisible to the union; got {refusal_candidates(tmp_path)}"
        )
        assert out_of_sink_refusers(tmp_path) == ["synthetic_return2.py"], (
            "`return 2` under safe_main refuses and records nothing, so it "
            "must be flagged as out-of-sink"
        )

    def test_control_return_one_is_not_a_refusal(self, tmp_path):
        """Boundary, and one case past it — mirrors the ``exit 1`` control.

        ``return 1`` is the warn convention. A guard that treated it as a
        refusal would flag every hook that merely warns.
        """
        self._write(
            tmp_path,
            "synthetic_return1.py",
            "import sys\n"
            "def main():\n"
            '    sys.stderr.write("warning\\n")\n'
            "    return 1\n",
        )
        assert refusal_candidates(tmp_path) == {}, (
            f"`return 1` was treated as a refusal: {refusal_candidates(tmp_path)}"
        )

    def test_control_return_true_is_not_a_refusal(self, tmp_path):
        """``True == 1`` and ``False == 0`` in Python — and ``2`` has no bool.

        There is no bool that equals 2, so this control cannot fail through
        ``return True``; it exists because the ``return 1`` control CAN, and
        an implementation that compared with ``==`` rather than checking the
        type would misread ``return True`` as the warn form and, worse, would
        be one edit away from misreading a bool elsewhere. Asserted as a set
        with ``return 0``/``return None`` so the type check is exercised.
        """
        self._write(
            tmp_path,
            "synthetic_return_bool.py",
            "def a():\n"
            "    return True\n"
            "def b():\n"
            "    return False\n"
            "def c():\n"
            "    return 0\n"
            "def d():\n"
            "    return None\n",
        )
        assert refusal_candidates(tmp_path) == {}, (
            f"a bool or a non-refusing int return was matched as a refusal: "
            f"{refusal_candidates(tmp_path)}"
        )

    def test_control_laundering_token_does_not_confer_sink_membership(
        self, tmp_path
    ):
        """A bare ``HookDecision`` identifier must not launder a raw refusal.

        ``_sink_evidence`` matched bare NAME tokens, so a file containing
        ``HookDecision = None`` — the exact line the migrated reference hook
        ships at ``enforce_file_organization.py:67`` — plus a printed deny
        envelope read as in-sink. A copy-pasting author writes that line
        without any intent to launder, which is what makes it dangerous.
        """
        self._write(
            tmp_path,
            "synthetic_laundered.py",
            "import json\n"
            "HookDecision = None\n"
            "def main():\n"
            "    print(json.dumps({\"hookSpecificOutput\": {\n"
            '        "permissionDecision": "deny",\n'
            '        "permissionDecisionReason": "nope",\n'
            "    }}))\n",
        )
        assert out_of_sink_refusers(tmp_path) == ["synthetic_laundered.py"], (
            "a raw printed refusal was permitted because the file happened to "
            "contain the identifier `HookDecision`. Sink membership must "
            "require the name to be imported from its module AND called."
        )

    def test_control_importing_the_sink_without_calling_it_is_not_membership(
        self, tmp_path
    ):
        """The other half: importing the sink and then refusing anyway.

        A lazier launderer copies the whole import block and still prints its
        own envelope. Binding evidence alone must not be enough.
        """
        self._write(
            tmp_path,
            "synthetic_imported_unused.py",
            "import json\n"
            "from hook_safety import HookDecision, safe_main\n"
            "def main():\n"
            '    print(json.dumps({"decision": "block"}))\n'
            "    return 0\n",
        )
        assert out_of_sink_refusers(tmp_path) == ["synthetic_imported_unused.py"], (
            "importing the sink without ever calling it was accepted as sink "
            "membership, so any hook can be laundered by adding one import"
        )

    def test_control_shell_refuser_without_a_sink_is_flagged(self, tmp_path):
        """The shell arm must refuse too, not just the Python arm."""
        self._write(
            tmp_path,
            "synthetic_shell.sh",
            "#!/usr/bin/env bash\n"
            "cat <<EOF\n"
            '{"permissionDecision": "deny", "reason": "nope"}\n'
            "EOF\n",
        )
        assert out_of_sink_refusers(tmp_path) == ["synthetic_shell.sh"], (
            "the shell instrument failed to flag an unfused shell refusal"
        )

    def test_control_shell_comment_prose_is_not_a_refusal(self, tmp_path):
        """Shell comments describing a refusal must not read as one."""
        self._write(
            tmp_path,
            "synthetic_shell_comment.sh",
            "#!/usr/bin/env bash\n"
            '# This hook once emitted {"permissionDecision": "deny"} but now\n'
            "# only warns. It never exits 2.\n"
            'echo \'{"permissionDecision": "allow"}\'\n',
        )
        assert refusal_candidates(tmp_path) == {}, (
            f"shell comment prose was matched as a refusal: "
            f"{refusal_candidates(tmp_path)}"
        )

    def test_control_exit2_arm_is_detected(self, tmp_path):
        """The exit-code refusal form, in isolation from the literal forms."""
        self._write(
            tmp_path,
            "synthetic_exit2.py",
            "import sys\n"
            "def main():\n"
            '    sys.stderr.write("refused\\n")\n'
            "    sys.exit(2)\n",
        )
        assert out_of_sink_refusers(tmp_path) == ["synthetic_exit2.py"], (
            "the exit2 instrument failed; a hook refusing by exit code is "
            "invisible to the union"
        )

    def test_control_exit_one_is_not_a_refusal(self, tmp_path):
        """Boundary, and one case past it: exit 1 warns, exit 2 refuses."""
        self._write(
            tmp_path,
            "synthetic_exit1.py",
            "import sys\n"
            "def main():\n"
            '    sys.stderr.write("warning\\n")\n'
            "    sys.exit(1)\n",
        )
        assert refusal_candidates(tmp_path) == {}, (
            "exit 1 was treated as a refusal; the guard would flag every hook "
            "that merely warns"
        )

    def test_control_unparseable_python_fails_loudly(self, tmp_path):
        """A hook the guard cannot parse must raise, never be skipped.

        Silently skipping an unparseable file is how a ratchet stops guarding
        without anyone noticing.
        """
        self._write(tmp_path, "synthetic_broken.py", "def main(:\n    pass\n")
        with pytest.raises(SyntaxError, match="synthetic_broken.py"):
            out_of_sink_refusers(tmp_path)

    def test_control_ratchet_still_refuses_with_an_empty_pinned_set(self, tmp_path):
        """THE CEILING'S CONTROL: the guard keeps teeth once the set empties.

        ``PINNED_OUT_OF_SINK`` is non-empty today, so the ratchet's subtraction
        is exercised by the live corpus. It will not be forever: the set exists
        to shrink to nothing, and at that moment ``live - PINNED`` degenerates
        to ``live``, and an equality-to-empty ceiling would be indistinguishable
        from a guard that stopped running. A ceiling that stops guarding at the
        instant it succeeds is not a ceiling.

        So this drives the SAME rule over a synthetic corpus with the pinned
        set forced EMPTY, and proves it still refuses a real offender and still
        permits a fused one. The mechanism is therefore load-bearing
        independently of whether any live hook is currently pinned.
        """
        self._write(
            tmp_path,
            "post_migration_offender.py",
            'print({"permissionDecision": "ask", "permissionDecisionReason": "no"})\n',
        )
        self._write(
            tmp_path,
            "post_migration_compliant.py",
            "from hook_telemetry import deny_and_record\n"
            "def main():\n"
            '    return deny_and_record(hook_name="x", reason="no")\n',
        )
        empty_pin: "frozenset[str]" = frozenset()
        live = set(out_of_sink_refusers(tmp_path))

        assert sorted(live - empty_pin) == ["post_migration_offender.py"], (
            "with an empty pinned set the ratchet failed to flag a new "
            "out-of-sink refuser — it would stop guarding the moment the "
            "migration completes"
        )
        assert "post_migration_compliant.py" not in live, (
            "with an empty pinned set the ratchet flagged a fused hook — it "
            "would block the sanctioned path after the migration completes"
        )

    def test_control_pinning_genuinely_suppresses_a_real_offender(self, tmp_path):
        """The pin mechanism works, therefore capping it matters.

        If the subtraction did not actually suppress, ``PINNED_OUT_OF_SINK``
        would be decorative and ``test_pinned_set_has_a_ceiling`` would guard
        nothing.
        """
        self._write(
            tmp_path,
            "would_be_pinned.py",
            'print({"permissionDecision": "deny"})\n',
        )
        live = set(out_of_sink_refusers(tmp_path))
        assert live == {"would_be_pinned.py"}, "premise: it IS a live offender"
        assert not (live - frozenset({"would_be_pinned.py"})), (
            "the pin did not suppress a known offender, so PINNED_OUT_OF_SINK "
            "is decorative and its ceiling guards nothing"
        )


class TestSourceCorpusIsNotTheDeployedArtifact:
    """Pin the corpus choice so a future edit cannot quietly repoint it."""

    def test_dot_claude_hooks_is_untracked_and_therefore_not_the_corpus(self):
        """``.claude/hooks/`` is a gitignored deploy artifact, not source."""
        import subprocess

        tracked = subprocess.run(
            ["git", "ls-files", ".claude/hooks/"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert tracked == "", (
            f".claude/hooks/ now has git-tracked files:\n{tracked}\n"
            f"If it became the source of truth, revisit HOOKS_DIR here."
        )

        source_tracked = subprocess.run(
            ["git", "ls-files", "plugins/autonomous-dev/hooks/"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert source_tracked, (
            "plugins/autonomous-dev/hooks/ has no tracked files — HOOKS_DIR "
            "does not point at a tracked corpus."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
