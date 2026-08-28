"""Both arms of the mutation witness, plus the bypass hunt (Issue #1660).

The mechanism under test lives in ``scripts/mutation_witness.py`` -- beside its
driver ``scripts/mutation_witness_gate.py`` and its sibling harness
``scripts/integration_ceiling.py``, NOT in ``plugins/autonomous-dev/lib/`` -- and
is IMPORTED here, never re-expressed: a second copy inside the reader is the
defect, not the fix (the discipline #1667 established).

This file stays under ``tests/unit/lib/`` rather than following the subject to
``tests/unit/scripts/``: nothing enforces a mirror layout (the driver's own
suite already sits in ``tests/unit/hooks/`` for a ``scripts/`` subject), and
moving it is churn this change did not need. The subject's real location is
named above so a reader is not misled by the directory.

WHY A SYNTHETIC TARGET RATHER THAN THE MOTIVATING ONE: the arms need a target
whose mutation is unambiguous and whose runs are sub-second. ``calc.add`` is the
target from the measurement posted to #1660, and it is NOT the code that
motivated the mechanism -- ``coverage_baseline.py``'s four counters are. Driving
the harness over its own motivating target would scope the proof to that
instance.

WHY OUT OF PROCESS: the property being measured IS a process exit code. There is
no in-process form of "this test failed when the target was wrong".

Date: 2026-08-28
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Tuple

import pytest

# tests/unit/lib/<this file> -> lib -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
SCRIPTS_DIR = REPO_ROOT / "scripts"
#: LIB_DIR is still needed -- ``test_pruning_analyzer`` (the vacuous-test reader
#: cross-checked below) IS a shipped library. The witness is not; it is in
#: SCRIPTS_DIR. Keeping the two paths separate is the point of this change.
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import mutation_witness  # noqa: E402
from mutation_witness import (  # noqa: E402
    VERDICT_BROKEN_CONTROL,
    VERDICT_GENUINE,
    VERDICT_SKIPPED_BUDGET,
    VERDICT_TAMPERED,
    VERDICT_VACUOUS,
    InvalidMutationError,
    MutationClaim,
    check_mutation_witnesses,
    load_claims,
    substitute,
    witness_claim,
)
from test_pruning_analyzer import find_vacuous_tests  # noqa: E402

# --- the synthetic target ----------------------------------------------------

CALC_SOURCE = '''"""Synthetic target for the mutation witness (Issue #1660)."""


def add(a, b):
    # a deliberately boring comment, used as a comment-only mutation anchor
    return a + b
'''

ANCHOR = "return a + b"
REPLACEMENT = "return a - b"

#: One budget constant drives BOTH budget arms, so the pair cannot drift apart.
#: The fast arm runs in well under a second; the slow arm sleeps far past it.
BUDGET_S = 5.0
SLOW_SLEEP_S = 60

#: MEASURED on this repo: an identical run costs 3.53s with pytest plugin
#: autoload on and 0.16s with it off. Every synthetic target here is
#: self-contained (no fixtures, no plugins), so the arms below turn it off and
#: the file runs in seconds instead of minutes. The verdict logic is byte-for-
#: byte the same code path -- only interpreter startup differs -- and
#: ``TestProductionDefaults`` drives one arm on the SHIPPED default so the
#: configuration the pipeline actually uses is not left unobserved.
FAST = {"budget_s": BUDGET_S, "disable_plugin_autoload": True}

GENUINE_TEST = """from calc import add


def test_add_returns_the_sum():
    assert add(2, 3) == 5
"""

#: The shape from the #1660 measurement. It asserts NO constant, so #1667's
#: static detector passes it -- and it survives the mutation.
IS_NOT_NONE_TEST = """from calc import add


def test_add_returns_something():
    assert add(2, 3) is not None
"""

SELF_EQUALITY_TEST = """from calc import add


def test_add_equals_itself():
    assert add(2, 3) == add(2, 3)
"""

MOCKED_TEST = """from unittest.mock import patch

import calc


def test_add_via_mock():
    with patch.object(calc, "add", return_value=5):
        assert calc.add(2, 3) == 5
"""

SLOW_TEST = f"""import time

from calc import add


def test_add_slowly():
    time.sleep({SLOW_SLEEP_S})
    assert add(2, 3) == 5
"""

# ``repr`` rather than a triple-quoted block: CALC_SOURCE opens with its own
# ``"""`` docstring, and nesting the two produced a module that did not parse.
# pytest then exited 4, which the control arm caught -- shape 6 in miniature.
TAMPERING_TEST = f"""from pathlib import Path

ORIGINAL = {CALC_SOURCE!r}


def test_add_after_restoring_its_own_target():
    Path(__file__).with_name("calc.py").write_text(ORIGINAL)
    from calc import add

    assert add(2, 3) == 5
"""

# A judge whose empirical floor is 6; the test threshold sits at 1, below it.
# This is the shape of tests/genai/test_lib_quality.py:209 (`assert score >= 1`).
JUDGE_SOURCE = '''"""Synthetic judge whose empirical floor sits above the assertion."""

EMPIRICAL_FLOOR = 6


def score(document):
    return 10 if "aligned" in document else EMPIRICAL_FLOOR
'''

JUDGE_ANCHOR = 'return 10 if "aligned" in document else EMPIRICAL_FLOOR'
JUDGE_REPLACEMENT = "return EMPIRICAL_FLOOR"

BELOW_FLOOR_TEST = """from judge import score


def test_document_is_aligned():
    assert score("an aligned document") >= 1
"""

AT_FLOOR_TEST = """from judge import score


def test_document_is_aligned():
    assert score("an aligned document") == 10
"""


def _scenario(
    tmp_path: Path,
    test_source: str,
    *,
    target_source: str = CALC_SOURCE,
    target_name: str = "calc.py",
    anchor: str = ANCHOR,
    replacement: str = REPLACEMENT,
) -> Tuple[Path, MutationClaim]:
    """Write a target plus a one-test module and return ``(target, claim)``."""
    target = tmp_path / target_name
    target.write_text(target_source, encoding="utf-8")
    test_file = tmp_path / "test_target.py"
    test_file.write_text(test_source, encoding="utf-8")
    # Anchored on "def test_" specifically: TAMPERING_TEST embeds the target's
    # own source, whose "def add(" would otherwise be picked up instead.
    func = test_source.split("def test_", 1)[1].split("(", 1)[0]
    func = f"test_{func}"
    claim = MutationClaim(
        test=f"test_target.py::{func}",
        target=target,
        anchor=anchor,
        replacement=replacement,
    )
    return target, claim


class TestHarnessPremises:
    """Verify the instrument before trusting one cell of its output."""

    def test_a_stale_anchor_raises_rather_than_matching_nothing(self, tmp_path: Path) -> None:
        """The harness must be able to FAIL. Zero matches is an error, not a pass."""
        target, claim = _scenario(tmp_path, GENUINE_TEST, anchor="return a * b")
        with pytest.raises(InvalidMutationError, match="appears 0 time"):
            witness_claim(claim, repo_root=tmp_path, **FAST)
        assert target.read_text(encoding="utf-8") == CALC_SOURCE

    def test_an_ambiguous_anchor_raises(self) -> None:
        """Two matches mutate more than the claim describes."""
        with pytest.raises(InvalidMutationError, match="appears 2 time"):
            substitute("x = 1\ny = 1\n", "= 1", "= 2")

    def test_a_no_op_replacement_raises(self) -> None:
        """Anchor == replacement produces a mutant identical to the original."""
        with pytest.raises(InvalidMutationError, match="identical"):
            substitute("return a + b\n", "return a + b", "return a + b")

    def test_substitute_permits_a_unique_anchor(self) -> None:
        """NEGATIVE CONTROL: the refusal must not reject every anchor."""
        assert substitute("return a + b\n", ANCHOR, REPLACEMENT) == "return a - b\n"

    def test_a_missing_target_fails_closed(self, tmp_path: Path) -> None:
        """BYPASS SHAPE 5: a claim whose target cannot be located must not no-op."""
        _, claim = _scenario(tmp_path, GENUINE_TEST)
        orphan = MutationClaim(
            test=claim.test,
            target=tmp_path / "does_not_exist.py",
            anchor=ANCHOR,
            replacement=REPLACEMENT,
        )
        with pytest.raises(InvalidMutationError, match="target not found"):
            witness_claim(orphan, repo_root=tmp_path, **FAST)

    @pytest.mark.parametrize(
        "anchor,replacement,why",
        [
            (
                "# a deliberately boring comment, used as a comment-only mutation anchor",
                "# an entirely different comment that changes no behaviour",
                "comment-only",
            ),
            ("def add(a, b):\n", "def add(a, b):\n\n", "whitespace-only"),
        ],
    )
    def test_a_mutation_uncoupled_to_behaviour_is_refused(
        self, tmp_path: Path, anchor: str, replacement: str, why: str
    ) -> None:
        """REFUSING ARM, DIFFERENT SHAPE: an AST no-op proves nothing.

        Every test survives a comment or whitespace edit, so accepting one would
        report every test vacuous. The mutation must be coupled to the assertion.
        """
        _, claim = _scenario(
            tmp_path, GENUINE_TEST, anchor=anchor, replacement=replacement
        )
        with pytest.raises(InvalidMutationError, match="changes no behaviour"):
            witness_claim(claim, repo_root=tmp_path, **FAST)

    def test_a_syntax_breaking_mutation_is_refused(self, tmp_path: Path) -> None:
        """A mutant that cannot import fails every test, certifying all of them."""
        _, claim = _scenario(tmp_path, GENUINE_TEST, replacement="return a + +")
        with pytest.raises(InvalidMutationError, match="unparseable"):
            witness_claim(claim, repo_root=tmp_path, **FAST)

    def test_the_target_is_restored_even_when_the_run_crashes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``finally`` restores unconditionally, so a crash cannot dirty the tree."""
        target, claim = _scenario(tmp_path, GENUINE_TEST)

        def boom(**_kwargs: object) -> None:
            raise RuntimeError("simulated crash inside the mutant run")

        monkeypatch.setattr(mutation_witness, "_run_one_test", boom)
        with pytest.raises(RuntimeError, match="simulated crash"):
            witness_claim(claim, repo_root=tmp_path, **FAST)
        assert target.read_text(encoding="utf-8") == CALC_SOURCE


class TestBothArms:
    """Watched permitting AND refusing, on a target other than the motivator."""

    def test_a_genuine_test_is_permitted(self, tmp_path: Path) -> None:
        """PERMITTING ARM: without it the gate could refuse everything."""
        target, claim = _scenario(tmp_path, GENUINE_TEST)
        result = witness_claim(claim, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_GENUINE, result.message
        assert result.witnessed is True
        assert result.control_returncode == 0
        assert result.mutant_returncode == 1
        assert target.read_text(encoding="utf-8") == CALC_SOURCE

    def test_a_test_that_survives_mutation_is_refused(self, tmp_path: Path) -> None:
        """REFUSING ARM: ``assert add(2,3) is not None`` cannot fail for its reason."""
        _, claim = _scenario(tmp_path, IS_NOT_NONE_TEST)
        result = witness_claim(claim, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_VACUOUS, result.message
        assert result.witnessed is False
        assert result.blocking is True
        assert result.mutant_returncode == 0

    def test_the_refused_shape_is_one_the_static_detector_passes(self) -> None:
        """Proof this closes a NEW gap rather than restating #1667.

        ``find_vacuous_tests`` is the SHIPPED constant-assertion detector. It
        must pass ``is not None`` (no gap closed otherwise) and it must still
        flag a bare ``assert True`` (else the detector, not the shape, is the
        reason -- a probe that cannot fail cannot inform).
        """
        passes_static = find_vacuous_tests(IS_NOT_NONE_TEST, "test_target.py")
        assert [f.name for f in passes_static] == [], (
            "the static detector already flags this shape, so the mutation "
            "witness would be closing a gap that is already closed"
        )
        flagged = find_vacuous_tests(
            "def test_constant():\n    assert True\n", "test_target.py"
        )
        assert [f.name for f in flagged] == ["test_constant"], (
            "POSITIVE CONTROL failed: the static detector flagged nothing at "
            "all, so its silence on `is not None` means nothing."
        )


class TestProductionDefaults:
    """The configuration the pipeline actually runs, not just the fast one."""

    def test_both_arms_hold_under_the_shipped_defaults(self, tmp_path: Path) -> None:
        """No ``FAST`` override: plugin autoload ON, exactly as the gate calls it.

        Committed is not deployed and configured is not executed. Every other
        arm here disables plugin autoload for speed; this one runs the SHIPPED
        default so that speed knob cannot be the reason the arms hold.
        """
        _, genuine = _scenario(tmp_path, GENUINE_TEST)
        assert witness_claim(genuine, repo_root=tmp_path).verdict == VERDICT_GENUINE

        _, vacuous = _scenario(tmp_path, IS_NOT_NONE_TEST)
        assert witness_claim(vacuous, repo_root=tmp_path).verdict == VERDICT_VACUOUS


class TestPerTestBudget:
    """A budget arm needs both a breach and a non-breach at the SAME budget."""

    def test_a_test_over_budget_produces_a_visible_skip(self, tmp_path: Path) -> None:
        """Loud skip, never a silent pass -- and never counted as witnessed."""
        _, claim = _scenario(tmp_path, SLOW_TEST)
        result = witness_claim(claim, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_SKIPPED_BUDGET, result.message
        assert result.witnessed is False
        assert "SKIPPED (budget)" in result.message
        assert f"{BUDGET_S:g}s per-test budget" in result.message

    def test_a_test_under_the_same_budget_is_unaffected(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL: the budget must not skip everything."""
        _, claim = _scenario(tmp_path, GENUINE_TEST)
        result = witness_claim(claim, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_GENUINE, result.message
        assert result.elapsed_s < BUDGET_S * 2


class TestBypassHunt:
    """Issue #1660 evasion shapes. Every entry is an OUTCOME, not an intention.

    Shapes 1-4 are refused by the core mechanism; shape 5 (missing target) and
    shape 7 (stale anchor) are refused in ``TestHarnessPremises``; shape 6 was
    NOT anticipated at the start of this work and is recorded below. Shape 8 --
    flooding the queue so the batch overruns the 60s hook budget -- is handled
    in ``tests/unit/hooks/test_mutation_witness_gate.py``: overflow DEFERS with
    every unverified node id named and requeued, and ``step5_quality_gate``
    composes the same function with no 60s ceiling, so a flood delays
    verification rather than escaping it.

    NAMED SURVIVORS, accepted rather than hidden:
      * A docstring-only mutation changes the AST, so the inertness check lets
        it through and every test then reads VACUOUS. The direction is
        fail-CLOSED (it refuses tests, never certifies them), so it costs a
        false alarm, not a bypass.
      * Declaring no claim at all bypasses the gate entirely. The claims file is
        the enforcement surface; populating it is the coordinator's job and is
        out of this issue's scope. Stated, not fixed.
    """

    def test_shape_1_a_test_that_restores_its_own_target(self, tmp_path: Path) -> None:
        """OUTCOME: DEFENDED (TAMPERED).

        The bytes on disk are read back BEFORE the harness restores them, so a
        test that undoes the mutation is attributed correctly. VACUOUS would
        also have blocked this; the tamper check buys the right MESSAGE, and
        proves the harness notices the write.
        """
        _, claim = _scenario(tmp_path, TAMPERING_TEST)
        result = witness_claim(claim, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_TAMPERED, result.message
        assert result.blocking is True

    def test_shape_2_a_test_asserting_on_a_mocked_value(self, tmp_path: Path) -> None:
        """OUTCOME: DEFENDED (VACUOUS). The real target never executes."""
        _, claim = _scenario(tmp_path, MOCKED_TEST)
        result = witness_claim(claim, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_VACUOUS, result.message

    def test_shape_3_assert_x_equals_x(self, tmp_path: Path) -> None:
        """OUTCOME: DEFENDED (VACUOUS). Self-equality holds under any mutation."""
        _, claim = _scenario(tmp_path, SELF_EQUALITY_TEST)
        result = witness_claim(claim, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_VACUOUS, result.message

    def test_shape_4_a_judge_threshold_below_the_judges_floor(self, tmp_path: Path) -> None:
        """OUTCOME: DEFENDED (VACUOUS). This is ``assert score >= 1`` today.

        Both arms on the SAME target: the below-floor threshold survives, the
        at-value assertion does not. Without the second arm this would only
        show that the judge target is mutable.
        """
        _, below = _scenario(
            tmp_path,
            BELOW_FLOOR_TEST,
            target_source=JUDGE_SOURCE,
            target_name="judge.py",
            anchor=JUDGE_ANCHOR,
            replacement=JUDGE_REPLACEMENT,
        )
        assert (
            witness_claim(below, repo_root=tmp_path, **FAST).verdict
            == VERDICT_VACUOUS
        )

        _, at_value = _scenario(
            tmp_path,
            AT_FLOOR_TEST,
            target_source=JUDGE_SOURCE,
            target_name="judge.py",
            anchor=JUDGE_ANCHOR,
            replacement=JUDGE_REPLACEMENT,
        )
        assert (
            witness_claim(at_value, repo_root=tmp_path, **FAST).verdict
            == VERDICT_GENUINE
        )

    def test_shape_6_exit_code_conflation_on_a_node_id_that_matches_nothing(
        self, tmp_path: Path
    ) -> None:
        """OUTCOME: DEFENDED. Not anticipated when this work started.

        MEASURED: ``pytest missing.py::test_nope`` exits 4, and a claim pointing
        at a nonexistent test would run pytest twice and get a non-zero exit
        BOTH times. A harness reading "non-zero exit == the test detected the
        mutation" would certify a test that does not exist. The control run --
        which must exit 0 AND report at least one pass -- is what refuses it.
        Exit 5 (nothing collected) is the same trap with a different number.
        """
        _, claim = _scenario(tmp_path, GENUINE_TEST)
        phantom = MutationClaim(
            test="test_target.py::test_does_not_exist",
            target=claim.target,
            anchor=ANCHOR,
            replacement=REPLACEMENT,
        )
        result = witness_claim(phantom, repo_root=tmp_path, **FAST)
        assert result.verdict == VERDICT_BROKEN_CONTROL, result.message
        assert result.verdict != VERDICT_GENUINE
        assert result.control_returncode not in (0, None)
        assert result.mutant_returncode is None, (
            "the mutant run must never happen once the control has failed"
        )


class TestGateComposition:
    """``check_mutation_witnesses`` as the driver's sweep entry point.

    An earlier revision composed this function into
    ``lib/step5_quality_gate.run_quality_gate`` "next to the four counters".
    That composition was REMOVED, and the arms that tested it are gone with
    their subject (named in ``TestRegressionIssue1660`` below). The reason is
    not scope: ``step5_quality_gate.py`` is itself pinned in
    ``PINNED_UNREACHED_LIBRARY`` -- "named four times across implement.md and
    implementer.md as the gate that 'blocks', and invoked by neither" -- so the
    composition proved only that an unreached host would have called an
    unreached module. Since #1698 the reachability walk is transitive and said
    so out loud. The remaining consumer is ``scripts/mutation_witness_gate.py``.
    """

    def test_zero_claims_passes_and_says_so(self, tmp_path: Path) -> None:
        """No permanently-red signal on a repo that declares nothing."""
        passed, message = check_mutation_witnesses(repo_root=tmp_path)
        assert passed is True
        assert "0 claims declared" in message

    def test_a_malformed_claims_file_fails_closed(self, tmp_path: Path) -> None:
        """Unreadable input must not be read as 'no claims'."""
        claims_path = tmp_path / "claims.json"
        claims_path.write_text("{not json", encoding="utf-8")
        passed, message = check_mutation_witnesses(
            repo_root=tmp_path, claims_path=claims_path
        )
        assert passed is False
        assert "unreadable" in message

    def test_a_claims_file_of_genuine_tests_passes(self, tmp_path: Path) -> None:
        """PERMITTING ARM at the gate level."""
        _, claim = _scenario(tmp_path, GENUINE_TEST)
        claims_path = tmp_path / "claims.json"
        claims_path.write_text(
            json.dumps(
                {
                    "claims": [
                        {
                            "test": claim.test,
                            "target": "calc.py",
                            "anchor": ANCHOR,
                            "replacement": REPLACEMENT,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        passed, message = check_mutation_witnesses(
            repo_root=tmp_path, claims_path=claims_path, **FAST
        )
        assert passed is True, message
        assert "1/1 claim(s) observed failing" in message

    def test_a_claims_file_with_a_vacuous_test_fails(self, tmp_path: Path) -> None:
        """REFUSING ARM at the gate level."""
        _, claim = _scenario(tmp_path, IS_NOT_NONE_TEST)
        claims_path = tmp_path / "claims.json"
        claims_path.write_text(
            json.dumps(
                [
                    {
                        "test": claim.test,
                        "target": "calc.py",
                        "anchor": ANCHOR,
                        "replacement": REPLACEMENT,
                    }
                ]
            ),
            encoding="utf-8",
        )
        passed, message = check_mutation_witnesses(
            repo_root=tmp_path, claims_path=claims_path, **FAST
        )
        assert passed is False
        assert "VACUOUS" in message
        assert "0/1 claim(s) observed failing" in message

    def test_a_claim_missing_a_key_is_refused(self, tmp_path: Path) -> None:
        """A claim without an anchor cannot mutate anything."""
        claims_path = tmp_path / "claims.json"
        claims_path.write_text(json.dumps([{"test": "a::b"}]), encoding="utf-8")
        with pytest.raises(InvalidMutationError, match="missing key"):
            load_claims(claims_path, repo_root=tmp_path)

    def test_the_sweep_is_bounded_by_a_deadline(self, tmp_path: Path) -> None:
        """Claims past the sweep budget are NAMED, not silently skipped.

        ``overall_budget_s`` is an API-level ceiling on the sweep, independent
        of whatever ceiling a caller carries: at a MEASURED ~7s per claim a
        large queue is minutes of silent single-threaded work, and a caller
        without its own deadline would run it unbounded.
        """
        _, claim = _scenario(tmp_path, GENUINE_TEST)
        claims = [claim] * 3
        passed, message = check_mutation_witnesses(
            claims, repo_root=tmp_path, overall_budget_s=0.0, **FAST
        )
        assert passed is True, "an exhausted sweep budget must not cry wolf"
        assert "SKIPPED (budget)" in message
        assert message.count(claim.test) >= 3, (
            "every unreached claim must be named; a count alone is a silent "
            "truncation wearing a number"
        )
        assert "0/3 claim(s) observed failing" in message

    def test_the_driver_passes_a_per_run_budget_rather_than_an_unbounded_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the KWARG, not just that the call happens (Issue #1064 shape).

        RETARGETED from ``test_step5_passes_a_sweep_budget_...``. The property
        is unchanged -- a consumer must bound each mutation run explicitly, not
        hope the run is short -- but its subject moved: the step5 composition is
        gone, so the arm now measures the one consumer that still exists,
        ``scripts/mutation_witness_gate.run_gate``.
        """
        sys.path.insert(0, str(SCRIPTS_DIR))
        import mutation_witness_gate as driver

        _, claim = _scenario(tmp_path, GENUINE_TEST)
        claims_path = tmp_path / "claims.json"
        claims_path.write_text(
            json.dumps(
                [
                    {
                        "test": claim.test,
                        "target": "calc.py",
                        "anchor": ANCHOR,
                        "replacement": REPLACEMENT,
                    }
                ]
            ),
            encoding="utf-8",
        )

        captured: dict = {}
        real_witness = driver.witness_claim

        def spy(_claim, **kwargs):
            # DELEGATES to the real function: capturing without running would
            # prove the kwarg is passed and nothing about it being honoured.
            captured.update(kwargs)
            return real_witness(_claim, **kwargs)

        monkeypatch.setattr(driver, "witness_claim", spy)
        blocked, message, _remaining = driver.run_gate(
            root=tmp_path,
            claims_path=claims_path,
            deadline=time.monotonic() + 60.0,
            disable_plugin_autoload=True,
        )
        assert blocked is False, f"POSITIVE CONTROL: the genuine claim was refused: {message}"

        assert "budget_s" in captured, (
            "run_gate calls witness_claim with no per-run ceiling; one hung test "
            "would consume the whole SubagentStop slot and the gate would be "
            "killed before it could return a verdict"
        )
        assert 0 < captured["budget_s"] <= driver.PER_RUN_BUDGET_S

    def test_the_driver_import_resolved_in_the_source_copy(self) -> None:
        """The import in the gate driver resolved -- not silently None.

        RETARGETED from ``test_the_gate_is_wired_in_the_source_copy``, which
        measured ``step5_quality_gate._check_mutation_witnesses``. The subject
        moved with the composition; the property -- an ``except ImportError``
        fallback that silently disarms the consumer -- is identical, and now
        measured on the consumer that survives.

        NAMED for what it measures: this imports off the SOURCE tree. The
        installed copy under ``~/.claude/`` is NOT verified here; that is a
        deployment step, and this harness is deliberately deployed nowhere.
        """
        sys.path.insert(0, str(SCRIPTS_DIR))
        import mutation_witness_gate as driver

        assert driver._WITNESS_AVAILABLE is True, (
            "mutation_witness_gate fell back to its ImportError branch, so the "
            "gate is present and unable to witness anything"
        )
        assert driver.witness_claim is witness_claim
        assert Path(mutation_witness.__file__).parent == SCRIPTS_DIR, (
            f"the witness resolved from {mutation_witness.__file__}, not "
            f"{SCRIPTS_DIR}; a stale copy is shadowing the harness"
        )


class TestRegressionIssue1660:
    """The regression arm: red before the mechanism, green after.

    Before ``mutation_witness.py`` existed, EVERY test-acceptance check in the
    pipeline was a counter, and ``assert True`` satisfied all four. The
    mechanism arms below prove the non-counter property exists and holds both
    ways. What they deliberately do NOT claim is that it is wired: see
    ``TestHonestlyUnwired``.
    """

    def test_regression_issue_1660_the_four_counters_are_still_counters(self) -> None:
        """The premise of the whole issue, kept executable.

        RETARGETED from ``..._gate_set_is_not_all_counters``. That arm asserted
        ``"and mutation_passed" in step5_quality_gate.py``; the composition was
        removed on purpose (``TestHonestlyUnwired`` records why), so an
        unchanged assertion would have been a green over a subject that no
        longer exists. What survives is the measurable half: the four counters
        are still all this pipeline accepts a test on.
        """
        import coverage_baseline

        for counter in (
            "check_coverage_regression",
            "check_skip_regression",
            "check_test_count_regression",
            "check_skip_rate",
        ):
            assert hasattr(coverage_baseline, counter), (
                f"{counter} disappeared; this test's premise no longer holds"
            )

        assert not hasattr(coverage_baseline, "check_mutation_witnesses"), (
            "a non-counter appeared in coverage_baseline; if the witness was "
            "wired in there, re-litigate the unwired decision deliberately "
            "instead of letting this arm drift green."
        )

    def test_regression_issue_1660_the_motivating_shape_is_refused(
        self, tmp_path: Path
    ) -> None:
        """The exact pair from the #1660 measurement, both arms, one target."""
        _, vacuous = _scenario(tmp_path, IS_NOT_NONE_TEST)
        assert (
            witness_claim(vacuous, repo_root=tmp_path, **FAST).verdict
            == VERDICT_VACUOUS
        )
        _, genuine = _scenario(tmp_path, GENUINE_TEST)
        assert (
            witness_claim(genuine, repo_root=tmp_path, **FAST).verdict
            == VERDICT_GENUINE
        )


class TestHonestlyUnwired:
    """The harness works and is NOT wired. Both halves stated executably.

    Issue #1660's mechanism is proven refusing AND permitting by the arms
    above. Its enforcement loop is OPEN: nothing in this repo produces a
    mutation claim, so the gate is registered nowhere and installed nowhere.

    An earlier revision hid that by composing ``check_mutation_witnesses`` into
    ``lib/step5_quality_gate.run_quality_gate``. That host is itself pinned in
    ``PINNED_UNREACHED_LIBRARY`` -- "named four times across implement.md and
    implementer.md as the gate that 'blocks', and invoked by neither. A gate
    described in prose is not enforcement (INV-1)" -- and since #1698 the
    reachability walk is transitive, so the composition made the witness
    unreached too. It bought the APPEARANCE of wiring and no enforcement: the
    exact false signal this issue exists to remove.

    These are negative-assertion scope locks. They go red the day someone ships
    or registers the harness, so the decision is re-litigated deliberately
    rather than drifting back in. To lift them: land a producer, then delete
    this class in the SAME diff that registers the gate.
    """

    #: Both halves of the harness, by the path each occupies today.
    HARNESS = ("scripts/mutation_witness.py", "scripts/mutation_witness_gate.py")

    #: Every surface that could install or register either half.
    SURFACES = (
        "plugins/autonomous-dev/install_manifest.json",
        "plugins/autonomous-dev/config/install_manifest.json",
        "plugins/autonomous-dev/config/global_settings_template.json",
        "plugins/autonomous-dev/templates/settings.autonomous-dev.json",
    )

    def test_both_halves_are_where_this_change_put_them(self) -> None:
        """POSITIVE CONTROL for every absence assertion below.

        Absence tests over files that do not exist prove nothing. This one
        fails loudly if the harness moved again.
        """
        for rel in self.HARNESS:
            assert (REPO_ROOT / rel).is_file(), f"{rel} is missing"

    @pytest.mark.parametrize("surface", SURFACES)
    def test_neither_half_appears_in_any_shipping_surface(self, surface: str) -> None:
        """Not in either manifest, not in either settings template.

        The substring ``mutation_witness`` covers both halves, since the
        driver's name contains the library's.
        """
        path = REPO_ROOT / surface
        assert path.is_file(), f"POSITIVE CONTROL: {surface} does not exist"
        assert "mutation_witness" not in path.read_text(encoding="utf-8"), (
            f"{surface} ships or registers part of the mutation harness. It is "
            f"a harness with no producer: shipping it installs a mechanism no "
            f"consumer invokes, and registering it makes every firing a false "
            f"refusal (Issue #1660)."
        )

    def test_the_surfaces_carry_real_registrations(self) -> None:
        """NEGATIVE CONTROL: the parametrized absence must measure something.

        Each named surface must actually list files or bind hooks, otherwise
        "the harness is not in this file" is trivially true of any file on disk.
        """
        for surface in self.SURFACES:
            text = (REPO_ROOT / surface).read_text(encoding="utf-8")
            assert "unified_pre_tool" in text or "step5_quality_gate" in text, (
                f"{surface} lists no known component, so asserting the "
                f"harness's absence from it measures nothing."
            )

    def test_neither_half_sits_in_lib_or_hooks(self) -> None:
        """A harness in ``lib/`` or ``hooks/`` is a MEASURED defect.

        ``lib/mutation_witness.py`` was classified UNKNOWN by
        ``test_no_new_unreached_library_modules``; a refusing
        ``hooks/mutation_witness_gate.py`` was classified an unreachable
        refuser by ``test_no_new_unreachable_refusers``. Pinning is not an
        available resolution for either -- correct classification is.
        """
        lib_dir = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
        hooks_dir = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
        assert lib_dir.is_dir() and hooks_dir.is_dir(), "POSITIVE CONTROL: dirs missing"
        for name in ("mutation_witness.py", "mutation_witness_gate.py"):
            assert not (lib_dir / name).exists(), (
                f"lib/{name} is back. A harness whose only consumer is an "
                f"unreached module is unreached; the ratchet will say so."
            )
            assert not (hooks_dir / name).exists(), (
                f"hooks/{name} is back while registered nowhere; that trips "
                f"the unreachable-refuser ratchet and the manifest guard."
            )

    def test_step5_quality_gate_does_not_compose_the_witness(self) -> None:
        """The removal, kept red-on-return.

        Re-adding the composition to a host that is itself pinned unreached is
        how the appearance of wiring came back last time.
        """
        source = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "step5_quality_gate.py"
        ).read_text(encoding="utf-8")
        assert "def run_quality_gate" in source, (
            "POSITIVE CONTROL: step5_quality_gate.py no longer defines "
            "run_quality_gate, so this absence assertion measures nothing."
        )
        assert "mutation" not in source.lower(), (
            "step5_quality_gate.py composes the mutation witness again. Its "
            "host is pinned in PINNED_UNREACHED_LIBRARY, so this wires a "
            "harness into something nothing invokes -- appearance, not "
            "enforcement. Wire a REACHED consumer, or leave it unwired."
        )
