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

Sanctioned sink: a SET of two, on the FUSION property
------------------------------------------------------
The sink is not "whatever writes a row". It is "a path on which a refusal
cannot be obtained without the recording happening in the same act". Two paths
have that property and are sanctioned (``SANCTIONED_SINKS``):

* ``hook_telemetry.deny_and_record`` — returns the deny envelope AND records,
  in one call. A caller cannot get the payload without the row.
* ``hook_telemetry.block_event_decorator`` — wraps the hook's sole refusal
  emitter, so every refusal through that emitter records by construction.

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
**out-of-sink is NOT the same as unrecorded.** Two of the three pinned hooks
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
3. **Refusal forms nobody has named yet.** The instruments enumerate the four
   *known* forms. A fifth form invented tomorrow is outside all of them. This
   is the irreducible limit of the approach and the reason the pinned set has
   a ceiling rather than the guard claiming completeness.
4. **Intra-file granularity.** Sink classification is per-FILE and per-NAME: a
   file referencing a sanctioned sink is treated as in-sink. The guard does
   NOT prove every refusal path *within* such a file is fused, only that the
   file's refusals are meant to route through one. A new unfused path added to
   an already-in-sink file will not be flagged.
5. **Name-level, not identity-level, sink matching.** A function coincidentally
   named ``deny_and_record`` that records nothing would read as in-sink.
6. **Non-hook refusers.** Scope is the top-level hooks directory. Refusals
   emitted from ``lib/`` or ``scripts/`` are out of scope.

Holes 1, 2 and 3 all fail in the SAME safe direction — they under-report
candidates, so the guard can miss a violation but cannot invent one. Hole 4 is
the one that fails toward false confidence, and is the strongest argument for
finishing the migration rather than living on the ratchet.
"""

import ast
import re
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
# docstring for why this is two and not one, and not four.
SANCTIONED_SINKS = frozenset({"deny_and_record", "block_event_decorator"})

# Recorders that are NOT sinks: real, legitimate, but unfused. Named so the
# distinction is enforced by a test rather than left in prose.
UNFUSED_RECORDERS = frozenset({"log_block_event", "log_block_with_recovery"})

# Hooks known to refuse OUTSIDE the sanctioned sink. This set may only SHRINK.
#
# Adding an entry is NOT an acceptable resolution for a guard failure: route
# the refusal through ``hook_telemetry.deny_and_record`` (or decorate the
# hook's sole emitter with ``block_event_decorator``) instead.
#
#  * plan_gate.py            — refuses via ``_output_decision("block", ...)``
#    at lines 392 and 410, emitting an out-of-enum ``"block"`` where the
#    protocol expects ``"deny"``. Its only ``log_block_event`` call (line 325)
#    is on the Phase-E SKIP path and is explicitly commented "The enforce path
#    stays silent" — so its refusals record NOTHING. Deliberately NOT migrated
#    here: the enum divergence needs a decision (#1589). It is pinned because
#    tracking it is the entire point of the ratchet.
#  * unified_prompt_validator.py — refuses via a ``{"decision": "block"}``
#    dict literal (line 803) and records via a separate adjacent
#    ``_log_block_event_972`` call (line 810). Two acts.
#  * enforce_orchestrator.py — refuses via ``sys.exit(2)`` (line 320) and
#    records via a separate preceding ``_log_block_event_972`` call (line
#    313). Two acts.
PINNED_OUT_OF_SINK: "frozenset[str]" = frozenset(
    {
        "plan_gate.py",
        "unified_prompt_validator.py",
        "enforce_orchestrator.py",
    }
)

# Ceiling on the pinned set. The set is an escape hatch, and an escape hatch
# without its own ceiling is decorative — the next hook that fails gets added
# to the list instead of migrated.
PINNED_CEILING = 3

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
    * ``decorated_emitter`` — a function wrapped by ``block_event_decorator``,
      which is by definition a refusal emitter. This instrument alone catches
      ``unified_pre_tool.py``, whose refusals carry no literal anywhere.

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

            # Instrument C: exit-code refusal.
            if name == "exit" and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and arg.value == 2:
                    evidence.add("exit2")

        # Instrument D: a function fused to the recorder by decoration is,
        # necessarily, the hook's refusal emitter.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if _called_name(target) == "block_event_decorator":
                    evidence.add(f"decorated_emitter:{node.name}")

    return sorted(evidence)


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
    """Return which sanctioned sinks a hook references.

    Name-level and file-level. See limitations 4 and 5 in the module
    docstring for exactly what this does and does not establish.

    Args:
        path: Hook script path.

    Returns:
        Sorted sanctioned-sink names referenced anywhere in the file.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".sh":
        stripped = "\n".join(_SHELL_COMMENT.sub("", ln) for ln in source.splitlines())
        return sorted(s for s in SANCTIONED_SINKS if re.search(rf"\b{s}\b", stripped))

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    names: "set[str]" = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.rsplit(".", 1)[-1])
            if node.asname:
                names.add(node.asname)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return sorted(SANCTIONED_SINKS & names)


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

    def test_sink_is_a_set_of_exactly_the_two_fusing_paths(self):
        """The sink is two, on the fusion property — not one, and not four."""
        assert SANCTIONED_SINKS == {"deny_and_record", "block_event_decorator"}, (
            f"SANCTIONED_SINKS changed to {sorted(SANCTIONED_SINKS)}. The "
            f"membership rule is FUSION: a refusal cannot be obtained without "
            f"the recording happening in the same act. Adding a bare recorder "
            f"here would collapse a distinct property into a weaker one and "
            f"the ratchet would stop tracking the hooks it exists to track. "
            f"See the module docstring."
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
        """The escape hatch cannot grow. An uncapped hatch is decorative."""
        assert len(PINNED_OUT_OF_SINK) <= PINNED_CEILING, (
            f"PINNED_OUT_OF_SINK has grown to {len(PINNED_OUT_OF_SINK)} entries "
            f"{sorted(PINNED_OUT_OF_SINK)}, over the ceiling of "
            f"{PINNED_CEILING}. A hook was added to the exemption list instead "
            f"of being migrated to the sink. Migrate it."
        )
        assert PINNED_CEILING == 3, (
            f"PINNED_CEILING was raised to {PINNED_CEILING}. The ceiling exists "
            f"to make growth impossible; raising it defeats it. Lower it as "
            f"hooks migrate — never raise it."
        )

    def test_plan_gate_is_tracked_even_though_out_of_scope_for_migration(self):
        """#1589 is deferred, but the ratchet must not lose sight of it.

        ``plan_gate.py`` emits an out-of-enum ``"block"`` and needs a decision
        this change does not have. Deferring the MIGRATION must not defer the
        TRACKING — an untracked known offender is how a ratchet silently
        starts from a wrong baseline.
        """
        assert "plan_gate.py" in PINNED_OUT_OF_SINK, (
            "plan_gate.py must stay pinned until #1589 resolves its enum "
            "divergence and it is migrated to the sink."
        )
        assert "plan_gate.py" in out_of_sink_refusers(), (
            "plan_gate.py no longer reads as an out-of-sink refuser. If it was "
            "migrated, remove it from PINNED_OUT_OF_SINK. If the detector "
            "stopped seeing it, the instrument has regressed."
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
