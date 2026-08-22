#!/usr/bin/env python3
"""Guard: a hook that can emit a refusal must have a refusal-RECORDING path.

Issue #1611. This is the arm the #1588 ratchet does not cover, and the reason
``plan_gate.py`` went unnoticed for months.

Why the sink ratchet was not enough
-----------------------------------
``test_refusal_sink_ratchet.py`` asks "does this hook refuse through a FUSED
sink?" and permits a pinned set of hooks that do not. That question is the
right one for preventing new unfused refusals, but it says nothing about
whether a pinned hook records its refusals at all — and "out-of-sink" is
explicitly NOT the same as "unrecorded" (two pinned hooks do record, via the
two-act convention).

``plan_gate.py`` sat in the gap between those two facts. It was pinned. It
DID call ``log_block_event``. Any guard asking "does this file reference a
recorder?" would have passed it. But its single recorder call was on the
Phase-E SKIP path and carried ``decision_shape="mode_skip"`` — a NON-refusal
shape. Every one of its 287 rows in the live block log was a skip; its two
``_output_decision("block", ...)`` paths recorded nothing. The log was
under-counting a real gate to exactly zero, and the only way to notice was to
read the source by hand. Twice, that is what happened.

THE RULE
--------
A hook with refusal evidence must satisfy ONE of:

1. **Fused** — it routes refusals through a sanctioned sink
   (``deny_and_record`` / ``block_event_decorator`` / ``HookDecision``).
   Recording is then structural.
2. **Two-act, but with a REFUSAL SHAPE** — it calls a bare recorder with a
   ``decision_shape`` in ``hook_telemetry.BLOCK_SHAPES``. Forgettable, hence
   still pinned by the sink ratchet, but at least its refusals produce rows a
   reader will count.

A hook that refuses and whose only recorder calls carry NON-refusal shapes
records nothing about its refusals. That is the ``plan_gate`` defect, and it
fails here, named.

Instruments are IMPORTED, not reimplemented
-------------------------------------------
``_python_refusal_evidence``, ``_shell_refusal_evidence``, ``_iter_hook_files``
and ``_sink_evidence`` all come from ``test_refusal_sink_ratchet``. A control
that re-implements the rule proves nothing about the rule, and a second copy
of a six-instrument union is a second thing that can drift. The hook list is
derived from disk on every run; nothing here is hardcoded except the pinned
set of known offenders, which may only shrink.

The ceiling on the pin, and who watches it
------------------------------------------
``PINNED_UNRECORDED_REFUSERS`` is bounded by TWO constants, not one:
``UNRECORDED_CEILING`` and the separately-reviewed
``UNRECORDED_CEILING_HIGH_WATER_MARK``. A single literal beside the equality
was tried first and is not enough — after one legitimate advance the pin can be
re-grown to its historical high-water mark with every assertion passing. That
is the hole ``test_the_residual_headroom_is_zero`` closed in #1612, the
immediately preceding issue, and it is closed here the same way rather than
re-opened.

``TestCeilingIsNotATautology`` drives the ceiling over MUTATED copies of this
module in a subprocess, because a constant-versus-constant assertion cannot be
falsified in-process: growth must be watched going RED and the sanctioned
advance watched staying GREEN, or the ceiling is an unwatched claim.

What this guard CANNOT detect
-----------------------------
It inherits every limitation of the refusal instruments it imports (see that
module's docstring: dynamic refusals, shell beyond regex, unnamed refusal
forms, intra-file granularity, name-level sink matching, non-hook refusers).
It adds one of its own: **the recorder's shape argument must be a literal.**
A hook computing ``decision_shape`` at runtime reads as having no shape at
all and would be flagged. That fails in the safe direction — a false alarm
is visible and fixable; a false clearance is what produced this issue.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.hooks.test_refusal_sink_ratchet import (
    HOOKS_DIR,
    PROJECT_ROOT,
    _called_name,
    _iter_hook_files,
    _python_refusal_evidence,
    _refusal_evidence,
    _shell_refusal_evidence,
    _sink_evidence,
)

# The canonical refusal vocabulary, imported from beside the WRITER (#1611).
# Not redefined here: this guard exists because a constant living in one
# reader and nowhere else is not a mechanism.
_LIB = Path(PROJECT_ROOT) / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from hook_telemetry import BLOCK_SHAPES  # noqa: E402

#: Repo root, for the mutation harness's ``PYTHONPATH`` — the mutant copy runs
#: out of tree and still has to resolve ``tests.unit.hooks...`` at module
#: scope. Derived, never hardcoded.
_REPO_ROOT = str(Path(PROJECT_ROOT))

# Bare recorders a hook may call as a SECOND act. Matched by substring on the
# callee name so local aliases are caught: ``unified_prompt_validator.py`` and
# ``enforce_orchestrator.py`` both call a private ``_log_block_event_972``
# wrapper, and an exact-name list would have declared both unrecorded.
RECORDER_NAME_FRAGMENTS = ("log_block_event", "log_block_with_recovery")

# Hooks known to refuse with NO recording path of any kind. This set may only
# SHRINK. Adding an entry is NOT an acceptable resolution for a failure here:
# route the refusal through a sanctioned sink instead.
#
# All three are commit gates that refuse via a bare ``return 2`` from
# ``main()`` and print to stderr. They contain no telemetry call whatsoever,
# so each refuses today with ZERO rows — the same unknowable zero that
# ``enforce_file_organization.py`` had before #1588 and ``plan_gate.py`` had
# before #1611. They are pinned rather than migrated because migrating a
# commit gate changes what git sees, which is a separate blast radius.
PINNED_UNRECORDED_REFUSERS: "frozenset[str]" = frozenset(
    {
        "enforce_tdd.py",
        "enforce_prunable_threshold.py",
        "enforce_regression_test.py",
    }
)

# Ceiling on the pin. An escape hatch without its own ceiling is decorative.
# Lowering is the ratchet advancing and is never blocked. Raising has one
# honest justification — a new instrument revealing PRE-EXISTING offenders —
# and cannot happen quietly, because it is bounded by the separately-reviewed
# high-water mark below.
#
# It has never been raised. It went 4 -> 3 in #1611 when ``plan_gate.py`` was
# migrated into the sink.
UNRECORDED_CEILING = 3

# The highest ceiling ever REVIEWED. Its only job is to make a RAISE cost a
# second, visible constant edit.
#
# The first form of this ceiling used a bare literal (``UNRECORDED_CEILING <=
# 3``) beside the equality, copying the #1588 structure. Review found that
# insufficient one issue earlier, in #1612, and it is insufficient here for the
# same measured reason: after one legitimate advance (pin 3 -> 2, ceiling
# 3 -> 2), the literal would have to be edited down too, and if it is not, the
# pin can be RE-GROWN to 3 with every assertion green. Measured on the
# two-constant form:
#
#     today   pin=3 ceil=3 -> pin<=ceil True, ceil<=3 True, ceil==pin True
#     advance pin=2 ceil=2 -> True, True, True
#     REGROWN pin=3 ceil=3 -> True, True, True   <- all green, hole open
#
# ``test_the_residual_headroom_is_zero`` closes it by holding
# ``UNRECORDED_CEILING_HIGH_WATER_MARK - UNRECORDED_CEILING`` at zero.
#
# KNOWN, BOUNDED RESIDUAL — stated rather than hidden, and identical to the
# #1612 constant this mirrors. This is an upper bound, not a lockstep: lowering
# ``UNRECORDED_CEILING`` without lowering this leaves exactly the difference as
# headroom. Lower both in the same diff and the residual is zero. It is an
# upper bound rather than an equality on purpose — an equality would turn the
# sanctioned edit (migrate a hook, lower the pin and the ceiling) red until a
# third constant was also touched, and pressure on the correct action is the
# failure mode this whole class exists to prevent.
UNRECORDED_CEILING_HIGH_WATER_MARK = 3


def _ceiling_anchor(ceiling: int) -> str:
    """Build the mutation anchor for ``UNRECORDED_CEILING``.

    Derived from the constant rather than hardcoded. A hardcoded ``= 3`` anchor
    stops resolving the moment the ratchet advances, which turns the correct
    maintenance action — migrating a hook and lowering the pin — into red tests
    demanding a re-anchor. That is pressure to leave hooks pinned, which is the
    failure this module exists to prevent, one level up.

    Args:
        ceiling: The ceiling value the anchor should match.

    Returns:
        The exact source text of the ceiling assignment line.
    """
    return f"\nUNRECORDED_CEILING = {ceiling}\n"


def _high_water_anchor(mark: int) -> str:
    """Build the mutation anchor for ``UNRECORDED_CEILING_HIGH_WATER_MARK``.

    Args:
        mark: The high-water value the anchor should match.

    Returns:
        The exact source text of the high-water assignment line.
    """
    return f"\nUNRECORDED_CEILING_HIGH_WATER_MARK = {mark}\n"


def _pin_member_anchor(pin: "frozenset[str]") -> str:
    """Return the source line of the pin's alphabetically-last member.

    Used as both the ADD site (append after it) and the DROP site (remove it),
    so neither mutation needs a hardcoded filename that rots as the set
    changes.

    Args:
        pin: The pinned set, read from the module under mutation.

    Returns:
        The exact source text of one member line, including indentation.

    Raises:
        ValueError: If the pin is empty and no member line exists.
    """
    if not pin:
        raise ValueError(
            "the pin is empty, so no member line exists to anchor on. Callers "
            "must skip the mutation that needs it rather than anchor on "
            "nothing."
        )
    return f'        "{sorted(pin)[-1]}",\n'


def recorder_shapes(path) -> "set[str]":
    """Return the literal ``decision_shape`` values a hook records with.

    Only Python is analysed. The one shell refuser defines its own fusing
    ``deny_and_record`` function and is classified as in-sink before this is
    ever consulted.

    A recorder call with no literal ``decision_shape`` contributes the
    sentinel ``"<non-literal>"``, which is not in ``BLOCK_SHAPES`` and so does
    not clear the hook. See the "CANNOT detect" note in the module docstring.

    Args:
        path: Hook script path.

    Returns:
        The set of shape values passed to bare recorders; empty when the hook
        calls no recorder at all.
    """
    if path.suffix != ".py":
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()

    shapes: "set[str]" = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node.func)
        if not any(frag in name for frag in RECORDER_NAME_FRAGMENTS):
            continue
        literal = "<non-literal>"
        for keyword in node.keywords:
            if keyword.arg == "decision_shape" and isinstance(
                keyword.value, ast.Constant
            ):
                literal = keyword.value.value
        shapes.add(literal)
    return shapes


def records_its_refusals(path) -> bool:
    """THE RULE: does this hook have a path on which a refusal produces a row?

    Args:
        path: Hook script path.

    Returns:
        True when the hook is fused to a sanctioned sink, or calls a bare
        recorder with a refusal-shaped ``decision_shape``.
    """
    if _sink_evidence(path):
        return True
    return any(shape in BLOCK_SHAPES for shape in recorder_shapes(path))


def unrecorded_refusers(hooks_dir=HOOKS_DIR) -> "list[str]":
    """Enumerate hooks that can refuse but record nothing when they do.

    Factored out so the live corpus and every synthetic control drive the
    IDENTICAL code path.

    Args:
        hooks_dir: Directory of hook scripts to scan.

    Returns:
        Sorted filenames of refusal-capable hooks with no refusal-recording
        path.

    Raises:
        SyntaxError: If a ``.py`` hook does not parse.
    """
    return sorted(
        path.name
        for path in _iter_hook_files(hooks_dir)
        if _refusal_evidence(path) and not records_its_refusals(path)
    )


class TestInstrumentPremises:
    """Verify the instrument before trusting one cell of its output."""

    def test_imported_instruments_are_the_ratchet_originals(self):
        """Premise: nothing here reimplements the refusal detector.

        If these ever became local copies, this guard could pass while the
        real detector regressed — the two would drift and neither would say
        so.
        """
        import tests.unit.hooks.test_refusal_sink_ratchet as ratchet

        assert _python_refusal_evidence is ratchet._python_refusal_evidence
        assert _shell_refusal_evidence is ratchet._shell_refusal_evidence
        assert _iter_hook_files is ratchet._iter_hook_files
        assert _sink_evidence is ratchet._sink_evidence

    def test_block_shapes_comes_from_the_writer(self):
        """Premise: the vocabulary is the shared one, not a local copy."""
        import hook_telemetry

        assert BLOCK_SHAPES is hook_telemetry.BLOCK_SHAPES
        assert "mode_skip" not in BLOCK_SHAPES, (
            "mode_skip is enforcement being SKIPPED. If it enters "
            "BLOCK_SHAPES, this guard stops distinguishing the plan_gate "
            "defect from a healthy hook."
        )

    def test_corpus_contains_refusal_candidates(self):
        """A detector that finds nothing is not evidence of nothing."""
        candidates = [
            p.name for p in _iter_hook_files(HOOKS_DIR) if _refusal_evidence(p)
        ]
        assert len(candidates) >= 5, (
            f"Only {len(candidates)} refusal candidates across the corpus "
            f"({candidates}). That is an instrument failure, not a clean repo."
        )

    def test_positive_control_a_pinned_hook_really_records_nothing(self):
        """Premise for the pin: the three really do call no recorder.

        Asserted against the source rather than left in a comment, so the pin
        cannot outlive the condition that justified it.
        """
        for name in sorted(PINNED_UNRECORDED_REFUSERS):
            path = HOOKS_DIR / name
            assert path.exists(), f"premise: {name} still exists"
            assert _refusal_evidence(path), f"premise: {name} still refuses"
            assert recorder_shapes(path) == set(), (
                f"{name} now calls a recorder. If it started recording "
                f"refusals, delete it from PINNED_UNRECORDED_REFUSERS and "
                f"lower UNRECORDED_CEILING with it."
            )

    def test_negative_control_a_two_act_recorder_is_permitted(self):
        """``unified_prompt_validator.py`` is out-of-sink AND records.

        It is pinned by the SINK ratchet but must pass HERE — the two guards
        ask different questions, and conflating them would make this one flag
        every hook the other pins.
        """
        path = HOOKS_DIR / "unified_prompt_validator.py"
        assert path.exists(), "premise: the two-act hook still exists"
        assert not _sink_evidence(path), (
            "premise: it is still OUT of the sanctioned sink, so its "
            "permission below comes from the shape rule and not from fusion"
        )
        assert records_its_refusals(path), (
            f"a hook that records refusals with shape "
            f"{recorder_shapes(path)} was flagged as unrecorded"
        )


class TestTheGuard:
    """The live corpus. The pinned set may only shrink."""

    def test_no_hook_refuses_without_recording(self):
        """THE GUARD. A refusal with no recording path fails here, named."""
        live = set(unrecorded_refusers())
        new = sorted(live - PINNED_UNRECORDED_REFUSERS)
        assert not new, (
            f"Hook(s) can emit a refusal but have NO path that records one: "
            f"{new}\n"
            f"Every refusal they make is invisible to "
            f".claude/logs/hook-blocks.jsonl, so 'has this guard ever fired?' "
            f"is unanswerable for them.\n"
            f"Expected: route the refusal through "
            f"hook_telemetry.deny_and_record(), decorate the hook's sole "
            f"emitter with block_event_decorator(), or return a "
            f"hook_safety.HookDecision. All three fuse recording to the "
            f"refusal.\n"
            f"Adding the file to PINNED_UNRECORDED_REFUSERS is NOT a "
            f"resolution: the set has a ceiling of {UNRECORDED_CEILING} and "
            f"may only shrink.\n"
            f"See: plugins/autonomous-dev/lib/hook_telemetry.py"
        )

    def test_regression_issue_1611_plan_gate_records_its_refusals(self):
        """THE REPRODUCER. plan_gate refused 287 times and recorded 0 blocks.

        Before #1611 this hook had a ``log_block_event`` call — so a naive
        "does it reference a recorder?" check passed it — but that call sat on
        the Phase-E skip path with ``decision_shape="mode_skip"``. Its two
        ``_output_decision("block", ...)`` paths recorded nothing.

        Three assertions, because the interesting failure is a partial fix:
        the hook must be fused, must still be SEEN as a refuser, and its
        ``mode_skip`` path must survive — deleting the skip rows would destroy
        real signal about when enforcement was relaxed.
        """
        path = HOOKS_DIR / "plan_gate.py"
        assert _refusal_evidence(path), (
            "plan_gate.py no longer reads as refusal-capable; the instrument "
            "regressed rather than the hook being fixed"
        )
        assert "block_event_decorator" in _sink_evidence(path), (
            f"plan_gate.py is not fused to the sink. Sink evidence: "
            f"{_sink_evidence(path)}"
        )
        assert "mode_skip" in recorder_shapes(path), (
            "plan_gate.py's Phase-E mode_skip row was removed. The defect was "
            "the channel, not the record — knowing enforcement was skipped, "
            "and why, is real signal."
        )
        assert "plan_gate.py" not in unrecorded_refusers()

    def test_unrecorded_pin_has_a_ceiling(self):
        """The escape hatch cannot grow SILENTLY.

        Four assertions, guarding four different failures — the structure
        ``test_hook_reachability_ratchet.py`` arrived at in #1612 after review
        found the two-constant form insufficient:

        * **The high-water mark is the anti-GROWTH tripwire.** Tying the
          ceiling only to ``len(PINNED_UNRECORDED_REFUSERS)`` makes both
          operands constants in this file, so an edit that adds a member AND
          bumps the ceiling moves them together and nothing fires. A bare
          literal beside the equality fixes that only until the ratchet
          advances past it; a named constant makes the raise cost a second,
          separately-reviewed edit forever.
        * **The equality is the anti-SLACK tripwire.** A ceiling above the set
          is a pre-authorised exemption for the next hook that fails.
        * **The last arm bounds the PIN itself**, so no ceiling edit alone can
          authorise the set growing past what was ever reviewed.

        ``<=`` on the mark, not ``==``: lowering is the ratchet advancing and
        must never be blocked. ``test_the_residual_headroom_is_zero`` is
        deliberately NOT one of these assertions — see its docstring.
        """
        assert len(PINNED_UNRECORDED_REFUSERS) <= UNRECORDED_CEILING, (
            f"PINNED_UNRECORDED_REFUSERS grew to "
            f"{len(PINNED_UNRECORDED_REFUSERS)} entries "
            f"{sorted(PINNED_UNRECORDED_REFUSERS)}, over the ceiling of "
            f"{UNRECORDED_CEILING}. A hook was pinned instead of migrated."
        )
        assert UNRECORDED_CEILING <= UNRECORDED_CEILING_HIGH_WATER_MARK, (
            f"UNRECORDED_CEILING was RAISED to {UNRECORDED_CEILING}, over the "
            f"reviewed high-water mark of "
            f"{UNRECORDED_CEILING_HIGH_WATER_MARK}. LOWER it freely — that is "
            f"the ratchet advancing. RAISING it is honest in exactly one case: "
            f"a NEW refusal instrument made PRE-EXISTING offenders visible. To "
            f"take that case, in ONE diff: name the instrument in the "
            f"PINNED_UNRECORDED_REFUSERS comment, raise "
            f"UNRECORDED_CEILING_HIGH_WATER_MARK alongside it, and justify "
            f"each new entry. Anything else is a hook being pinned instead of "
            f"migrated."
        )
        assert UNRECORDED_CEILING == len(PINNED_UNRECORDED_REFUSERS), (
            f"UNRECORDED_CEILING ({UNRECORDED_CEILING}) no longer equals the "
            f"pinned set size ({len(PINNED_UNRECORDED_REFUSERS)}). Slack is a "
            f"pre-authorised exemption for the next hook that fails."
        )
        assert (
            len(PINNED_UNRECORDED_REFUSERS)
            <= UNRECORDED_CEILING_HIGH_WATER_MARK
        ), (
            f"PINNED_UNRECORDED_REFUSERS ({len(PINNED_UNRECORDED_REFUSERS)}) "
            f"is above the highest ceiling ever reviewed "
            f"({UNRECORDED_CEILING_HIGH_WATER_MARK}). The pin grew past the "
            f"reviewed bound; no ceiling edit can authorise that on its own."
        )

    def test_the_residual_headroom_is_zero(self):
        """State the hole rather than hide it, and hold it at zero.

        ``UNRECORDED_CEILING_HIGH_WATER_MARK`` is an upper bound, not a
        lockstep, so lowering ``UNRECORDED_CEILING`` without lowering the mark
        leaves that difference as headroom in which the pin could grow back
        with every ceiling assertion green. Lowering the mark in the same diff
        zeroes it.

        Deliberately NOT one of the assertions in
        ``test_unrecorded_pin_has_a_ceiling``: the mutation harness drives that
        test alone, and the sanctioned two-constant edit — migrate a hook,
        lower the pin and the ceiling — must be GREEN there. Keeping this arm
        separate means a maintainer who stops after two constants gets one
        named, one-line instruction here instead of a mutation harness going
        red at them.
        """
        residual = UNRECORDED_CEILING_HIGH_WATER_MARK - UNRECORDED_CEILING
        assert residual >= 0, (
            f"UNRECORDED_CEILING ({UNRECORDED_CEILING}) is above the reviewed "
            f"high-water mark ({UNRECORDED_CEILING_HIGH_WATER_MARK}); the "
            f"bound is inverted and the anti-raise assertion is inert."
        )
        assert residual == 0, (
            f"UNRECORDED_CEILING was lowered to {UNRECORDED_CEILING} while "
            f"UNRECORDED_CEILING_HIGH_WATER_MARK stayed at "
            f"{UNRECORDED_CEILING_HIGH_WATER_MARK}. That pre-authorises "
            f"{residual} further pin entr(y/ies) that the ceiling assertions "
            f"would not see. Lower the mark to {UNRECORDED_CEILING} — one "
            f"line, no justification needed, and it is the last step of the "
            f"edit you have already made."
        )

    def test_pinned_entries_are_still_genuinely_unrecorded(self):
        """A hook that starts recording must be REMOVED from the pin.

        This is the arm that makes the set actually shrink. Without it the pin
        is a permanent parking lot.
        """
        live = set(unrecorded_refusers())
        stale = sorted(PINNED_UNRECORDED_REFUSERS - live)
        assert not stale, (
            f"PINNED_UNRECORDED_REFUSERS names {stale}, which now record "
            f"their refusals (or no longer refuse). Delete them from the set "
            f"and lower UNRECORDED_CEILING — that deletion IS the ratchet "
            f"advancing."
        )


class TestBothArms:
    """Watch the rule REFUSING and PERMITTING, on shapes it did not start from.

    Every control drives ``unrecorded_refusers`` — the same function the live
    rule uses.

    The refusing controls are deliberately shaped UNLIKE the reproducer.
    ``plan_gate`` refused via ``_output_decision("block", ...)`` with a
    ``mode_skip`` recorder; the synthetics below refuse via a printed
    ``permissionDecision: "ask"`` envelope, via ``sys.exit(2)``, and via a
    ``return 2``, and record with ``"allow"`` or with no shape at all. The
    class the guard covers is therefore "any detectable refusal form paired
    with any non-refusal recording", not "the one file that prompted it".
    """

    @staticmethod
    def _write(tmp_path, name: str, body: str):
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_control_refusal_with_only_a_mode_skip_recorder_is_flagged(
        self, tmp_path
    ):
        """The plan_gate CLASS, on a different refusal shape.

        The hook DOES call ``log_block_event`` — a recorder-presence check
        clears it. Its refusal is an ``ask`` envelope, a form plan_gate never
        emitted, and its row is a ``mode_skip``. It must be flagged.
        """
        self._write(
            tmp_path,
            "synthetic_skip_only.py",
            "import json\n"
            "from hook_telemetry import log_block_event\n"
            "def main():\n"
            '    log_block_event(hook_name="synthetic_skip_only.py",\n'
            '                    decision_shape="mode_skip", reason="relaxed")\n'
            '    print(json.dumps({"hookSpecificOutput": {\n'
            '        "permissionDecision": "ask",\n'
            '        "permissionDecisionReason": "nope",\n'
            "    }}))\n",
        )
        assert unrecorded_refusers(tmp_path) == ["synthetic_skip_only.py"], (
            "a hook whose only recorder call carries a NON-refusal shape was "
            "permitted. That is the plan_gate defect exactly: present "
            "recorder, absent refusal row."
        )

    def test_control_refusal_with_an_allow_shaped_recorder_is_flagged(
        self, tmp_path
    ):
        """Boundary, and one case past it: ``allow`` is not a refusal either.

        ``mode_skip`` is not the only non-refusal shape, and a guard that
        special-cased that one literal would be scoped to the instance that
        prompted it. This refuses via ``sys.exit(2)`` — a third form.
        """
        self._write(
            tmp_path,
            "synthetic_allow_shape.py",
            "import sys\n"
            "from hook_telemetry import log_block_event\n"
            "def main():\n"
            '    log_block_event(hook_name="synthetic_allow_shape.py",\n'
            '                    decision_shape="allow", reason="fine")\n'
            "    sys.exit(2)\n",
        )
        assert unrecorded_refusers(tmp_path) == ["synthetic_allow_shape.py"], (
            "an 'allow'-shaped recording was accepted as a refusal record"
        )

    def test_control_refusal_with_a_nonliteral_shape_is_flagged(self, tmp_path):
        """A computed shape is not evidence of a refusal row. Fail visible.

        The refusal here is a bare ``return 2`` — the form the sink ratchet
        needed a sixth instrument to see at all.
        """
        self._write(
            tmp_path,
            "synthetic_dynamic_shape.py",
            "from hook_telemetry import log_block_event\n"
            "SHAPE = 'di' + 'ct'\n"
            "def main():\n"
            '    log_block_event(hook_name="x", decision_shape=SHAPE,\n'
            '                    reason="nope")\n'
            "    return 2\n",
        )
        assert unrecorded_refusers(tmp_path) == ["synthetic_dynamic_shape.py"], (
            "a non-literal decision_shape cleared the guard. It must fail in "
            "the visible direction, not the silent one."
        )

    def test_control_two_act_refusal_with_a_refusal_shape_is_permitted(
        self, tmp_path
    ):
        """THE PERMITTING ARM. Unfused but recording → permitted.

        Without this, a rule that flagged every file would pass every
        refusing control above while being worthless. This is also the shape
        of two live pinned-by-the-SINK-ratchet hooks, so it must not be
        conflated with the sink question.
        """
        self._write(
            tmp_path,
            "synthetic_two_act.py",
            "import json\n"
            "from hook_telemetry import log_block_event\n"
            "def main():\n"
            '    log_block_event(hook_name="synthetic_two_act.py",\n'
            '                    decision_shape="dict", reason="nope")\n'
            '    print(json.dumps({"decision": "block"}))\n',
        )
        assert unrecorded_refusers(tmp_path) == [], (
            "a hook that records its refusal with a refusal shape was "
            "flagged. The guard refuses a legitimate case."
        )

    def test_control_fused_refusal_is_permitted(self, tmp_path):
        """The other permitting arm: a sanctioned sink needs no shape check."""
        self._write(
            tmp_path,
            "synthetic_fused.py",
            "import json\n"
            "from hook_telemetry import deny_and_record\n"
            "def main():\n"
            "    print(json.dumps(deny_and_record(\n"
            '        hook_name="synthetic_fused.py", reason="nope")))\n',
        )
        assert unrecorded_refusers(tmp_path) == [], (
            "a hook refusing through the sanctioned sink was flagged"
        )

    def test_control_decorated_emitter_is_permitted(self, tmp_path):
        """The plan_gate FIX shape, driven through the rule.

        A hook whose sole emitter is decorated has no unfused refusal path,
        and its adjacent ``mode_skip`` recorder must not change that verdict.
        """
        self._write(
            tmp_path,
            "synthetic_decorated.py",
            "from hook_telemetry import block_event_decorator, log_block_event\n"
            '@block_event_decorator("synthetic_decorated.py",\n'
            '                       decision_shape="dict",\n'
            '                       refusal_values=frozenset({"block"}))\n'
            "def _output_decision(decision, reason):\n"
            "    print(decision, reason)\n"
            "def main():\n"
            '    log_block_event(hook_name="x", decision_shape="mode_skip",\n'
            '                    reason="relaxed")\n'
            '    _output_decision("block", "nope")\n',
        )
        assert unrecorded_refusers(tmp_path) == [], (
            "the migrated plan_gate shape was flagged. The guard refuses the "
            "sanctioned path."
        )

    def test_control_non_refuser_is_not_examined(self, tmp_path):
        """A hook that never refuses is not a candidate at all."""
        self._write(
            tmp_path,
            "synthetic_allow_only.py",
            'print({"permissionDecision": "allow"})\n',
        )
        assert unrecorded_refusers(tmp_path) == [], (
            "an allow-only hook was flagged; the guard is not gating on "
            "refusal evidence"
        )

    def test_control_both_arms_in_one_corpus(self, tmp_path):
        """Refusing and permitting, discriminated within a single scan.

        Proves the rule separates the two rather than keying on some property
        of the corpus as a whole.
        """
        self._write(
            tmp_path,
            "aaa_skip_only.py",
            "from hook_telemetry import log_block_event\n"
            "def main():\n"
            '    log_block_event(hook_name="a", decision_shape="mode_skip",\n'
            '                    reason="r")\n'
            '    print({"permissionDecision": "deny"})\n',
        )
        self._write(
            tmp_path,
            "bbb_records.py",
            "from hook_telemetry import log_block_event\n"
            "def main():\n"
            '    log_block_event(hook_name="b", decision_shape="exit2",\n'
            '                    reason="r")\n'
            '    print({"permissionDecision": "deny"})\n',
        )
        self._write(
            tmp_path,
            "ccc_allow_only.py",
            'print({"permissionDecision": "allow"})\n',
        )
        assert unrecorded_refusers(tmp_path) == ["aaa_skip_only.py"], (
            f"the rule did not discriminate; got "
            f"{unrecorded_refusers(tmp_path)}"
        )

    def test_control_unparseable_python_fails_loudly(self, tmp_path):
        """A hook the guard cannot parse must raise, never be skipped."""
        self._write(tmp_path, "synthetic_broken.py", "def main(:\n    pass\n")
        with pytest.raises(SyntaxError, match="synthetic_broken.py"):
            unrecorded_refusers(tmp_path)

    def test_control_guard_still_refuses_with_an_empty_pin(self, tmp_path):
        """The pin's own control: the guard keeps teeth once the set empties.

        ``PINNED_UNRECORDED_REFUSERS`` exists to shrink to nothing. At that
        moment ``live - PINNED`` degenerates to ``live``, and a guard that
        stopped working at the instant it succeeded would be indistinguishable
        from one that stopped running.
        """
        self._write(
            tmp_path,
            "post_migration_offender.py",
            "from hook_telemetry import log_block_event\n"
            "def main():\n"
            '    log_block_event(hook_name="x", decision_shape="mode_skip",\n'
            '                    reason="r")\n'
            '    print({"permissionDecision": "ask"})\n',
        )
        self._write(
            tmp_path,
            "post_migration_compliant.py",
            "from hook_telemetry import deny_and_record\n"
            "def main():\n"
            '    return deny_and_record(hook_name="x", reason="r")\n',
        )
        empty: "frozenset[str]" = frozenset()
        live = set(unrecorded_refusers(tmp_path))
        assert sorted(live - empty) == ["post_migration_offender.py"]
        assert "post_migration_compliant.py" not in live


class TestCeilingIsNotATautology:
    """The ceiling must fail on GROWTH, not merely on disagreement.

    ``UNRECORDED_CEILING == len(PINNED_UNRECORDED_REFUSERS)`` alone is
    unfalsifiable from inside this file: both operands are constants here, so
    an edit that adds a pinned entry AND bumps the ceiling moves them together
    and nothing fires. A bare literal beside the equality narrows the hole but
    does not close it — after one legitimate advance (pin 3 -> 2, ceiling
    3 -> 2) the pin can be re-grown to 3 with every assertion green, which is
    exactly what #1612's review found one issue earlier. The named
    high-water mark is what closes it, and this class is what WATCHES it.

    Every arm drives the real ``test_unrecorded_pin_has_a_ceiling`` over a
    MUTATED copy of this module, in a subprocess, and asserts the outcome. The
    harness gets its own controls: the unmutated copy must PASS (so a red
    elsewhere means the mutation, not a broken harness), and the selection must
    report exactly ONE test — a ``-k`` that matches nothing exits 0 and would
    read as green on every arm.

    Anchors are DERIVED from the module's own constants, never hardcoded, for
    the reason ``_ceiling_anchor`` states: a hardcoded anchor makes the ratchet
    ADVANCING turn this file red and demand a re-anchor, which is pressure to
    leave hooks pinned.
    """

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
        """Run only ``test_unrecorded_pin_has_a_ceiling`` over ``source``.

        Restricted with ``-k`` because the ceiling test reads nothing but the
        two constants: the copy runs out of tree, so the corpus-reading tests
        in this module would fail for an unrelated reason and blur the signal.
        ``PYTHONPATH`` carries the repo root so the mutant can still resolve
        its ``tests.unit.hooks.test_refusal_sink_ratchet`` import at module
        scope.
        """
        mutant = tmp_path / "test_unrecorded_ceiling_mutant.py"
        mutant.write_text(source, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [_REPO_ROOT] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(mutant),
                "-k",
                "test_unrecorded_pin_has_a_ceiling",
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

    def test_regression_issue_1611_growing_the_pin_and_the_ceiling_together_fails(
        self, tmp_path
    ):
        """THE REPRODUCER, and the refusing arm. Growth must be RED.

        Add a member to ``PINNED_UNRECORDED_REFUSERS`` and raise
        ``UNRECORDED_CEILING`` to match, in the same edit — the shape that lets
        the next failing hook be pinned instead of migrated. The added entry
        names no live hook, so this exercises the ceiling itself rather than
        the corpus detector.

        The target is derived from the HIGH-WATER MARK, not from the current
        ceiling. Deriving it from the ceiling would make this arm go green the
        moment the ratchet advances: at ceiling 2 with the mark at 3, a
        one-entry growth lands on 3 and satisfies ``3 <= 3``.
        """
        target = UNRECORDED_CEILING_HIGH_WATER_MARK + 1
        source = self._source()
        member = _pin_member_anchor(PINNED_UNRECORDED_REFUSERS)
        additions = "".join(
            f'        "synthetic_growth_offender_{i}.py",\n'
            for i in range(target - len(PINNED_UNRECORDED_REFUSERS))
        )
        source = self._substitute(source, member, member + additions)
        source = self._substitute(
            source, _ceiling_anchor(UNRECORDED_CEILING), _ceiling_anchor(target)
        )

        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode != 0, (
            f"PINNED_UNRECORDED_REFUSERS grew to {target} with the ceiling "
            f"raised to {target} to match, and the ceiling test still PASSED. "
            f"The escape hatch has no ceiling: the next hook that refuses "
            f"without recording can be pinned instead of migrated, by a "
            f"two-constant edit that no assertion sees.\n{result.stdout}"
        )
        assert "UNRECORDED_CEILING" in result.stdout, (
            f"the mutant failed for some reason other than a ceiling "
            f"assertion, so this proves nothing about it.\n{result.stdout}"
        )

    def test_regression_issue_1612_regrowth_after_an_advance_fails(
        self, tmp_path
    ):
        """THE #1612 HOLE, driven end to end on THIS ceiling.

        The two-constant form (literal ``<= 3`` beside the equality) is green
        for all three of: today, one advance, and re-growth back to the
        historical mark. This arm simulates the last of those — the pin and
        ceiling are left at today's values while the HIGH-WATER MARK is lowered
        to what it would be after one advance, which is the state a maintainer
        who advanced correctly leaves behind. Under the two-constant form this
        was GREEN; under the mark it must be RED.

        Applies at every pin size, the empty pin included: with pin 0 and
        ceiling 0, lowering the mark to -1 makes ``0 <= -1`` fail just as it
        does today. No structural exemption is needed and none is taken.
        """
        source = self._substitute(
            self._source(),
            _high_water_anchor(UNRECORDED_CEILING_HIGH_WATER_MARK),
            _high_water_anchor(UNRECORDED_CEILING_HIGH_WATER_MARK - 1),
        )
        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode != 0, (
            f"the ceiling stayed at {UNRECORDED_CEILING} while the reviewed "
            f"high-water mark was lowered to "
            f"{UNRECORDED_CEILING_HIGH_WATER_MARK - 1}, and nothing fired. "
            f"That is the #1612 re-growth hole: after one advance the pin "
            f"climbs back to its historical mark with every assertion "
            f"green.\n{result.stdout}"
        )
        assert "HIGH_WATER_MARK" in result.stdout, (
            f"the mutant failed for some reason other than the high-water "
            f"assertion, so this proves nothing about it.\n{result.stdout}"
        )

    @pytest.mark.skipif(
        not PINNED_UNRECORDED_REFUSERS,
        reason=(
            "PINNED_UNRECORDED_REFUSERS is empty: every hook records its "
            "refusals and there is no entry left to drop, so the advance this "
            "arm simulates has already fully arrived. Structurally "
            "inapplicable, not a hidden failure — the refusing arms above all "
            "still run in that state. Evaluates False today (the pin holds 3), "
            "so this adds no skip to the suite."
        ),
    )
    def test_shrinking_the_pin_and_the_ceiling_together_is_permitted(
        self, tmp_path
    ):
        """THE PERMITTING ARM. Lowering is the ratchet advancing — never blocked.

        Deliberately the opposite direction from the reproducer. A ceiling
        pinned with ``==`` to a literal would catch the growth above and then
        block the very outcome this module exists to produce, converting the
        fix into a new defect.

        ``UNRECORDED_CEILING_HIGH_WATER_MARK`` is DELIBERATELY left alone here.
        Lowering it is recommended and zeroes the residual headroom, but the
        sanctioned edit must be green WITHOUT it — requiring a third constant
        edit to avoid a red is pressure on exactly the action this module
        wants. That is why ``test_the_residual_headroom_is_zero`` is a separate
        test and not a fourth assertion in the one driven here.
        """
        source = self._substitute(
            self._source(), _pin_member_anchor(PINNED_UNRECORDED_REFUSERS), ""
        )
        source = self._substitute(
            source,
            _ceiling_anchor(UNRECORDED_CEILING),
            _ceiling_anchor(UNRECORDED_CEILING - 1),
        )

        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode == 0, (
            f"a hook was migrated out of PINNED_UNRECORDED_REFUSERS with the "
            f"ceiling lowered to match, and the ceiling test refused it. "
            f"Lowering is the ratchet advancing and needs no justification; "
            f"blocking it creates pressure to leave migrated hooks "
            f"pinned.\n{result.stdout}\n{result.stderr}"
        )

    def test_raising_the_ceiling_alone_still_fails(self, tmp_path):
        """The anti-slack arm: a ceiling above the pin is a pre-authorisation."""
        raised = UNRECORDED_CEILING_HIGH_WATER_MARK + 1
        source = self._substitute(
            self._source(),
            _ceiling_anchor(UNRECORDED_CEILING),
            _ceiling_anchor(raised),
        )
        result = self._run_ceiling_test(tmp_path, source)
        assert result.returncode != 0, (
            f"UNRECORDED_CEILING was raised to {raised} while the pin stayed "
            f"at {len(PINNED_UNRECORDED_REFUSERS)} and nothing fired. That is "
            f"a pre-authorised exemption.\n{result.stdout}"
        )
        assert "UNRECORDED_CEILING" in result.stdout, (
            f"the mutant failed for some reason other than a ceiling "
            f"assertion, so this proves nothing about it.\n{result.stdout}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
