"""Stage 0 architecture-delta precision regression suite (Issue #1600).

``detect_architecture_delta`` used to match ``ARCHITECTURE_DELTA_PHRASES`` as
bare substrings over the whole feature text. Every one of the 30 phrases
therefore admitted a plain *descriptive* sentence that escalated — measured
30/30 against the live module and the repo's own ``.claude/PROJECT.md``. The
bias pointed the wrong way: the gate fired hardest on briefs describing an
invariant violation, which is exactly the brief needed to repair one. It fired
in production twice on 2026-08-21, on the #1586 brief (``fail open``) and on
#1600's own repair brief (``prompt-level advisory``).

The fix is universal sentence-onset gating: a phrase escalates only when the
segment carrying it OPENS with a proposal verb.

Observed BEFORE the fix / AFTER the fix, executed against this repo's
``.claude/PROJECT.md``::

    descriptive sentences reaching the delta branch   30/30  ->  0/30
    positives reaching the delta branch               11/12  ->  11/12
    arch-006 outcome                              ESCALATE  ->  ESCALATE
    #1600 brief (verbatim)                        ESCALATE  ->  CLEAR
    #1586 brief (verbatim trigger sentence)       ESCALATE  ->  CLEAR

ASSERT THE BRANCH, NOT THE VERDICT. Two sentences can both ESCALATE for
entirely different reasons, so every descriptive assertion below checks that
``reason`` does *not* begin with the delta prefix, and every positive assertion
checks that it does. Outcome-only checking is what let misattributed rows
survive three rounds of plan critique.

GitHub Issue: #1600
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from alignment_classifier import (  # noqa: E402
    ARCHITECTURE_DELTA_PHRASES,
    PROPOSAL_ONSET_VERBS,
    ProjectDoc,
    Stage0Outcome,
    detect_architecture_delta,
    parse_project_md,
    parse_project_md_text,
    run_stage0,
)

_PROJECT_MD_PATH = _REPO_ROOT / ".claude" / "PROJECT.md"
_CORPUS_PATH = _REPO_ROOT / "tests" / "fixtures" / "alignment_classifier_corpus.json"

#: The prefix ``run_stage0`` puts on the architecture-delta branch only.
DELTA_REASON_PREFIX = "architecture invariant delta:"


@pytest.fixture(scope="module")
def doc() -> ProjectDoc:
    """The repo's real PROJECT.md — the gate is measured against live state."""
    return parse_project_md(_PROJECT_MD_PATH)


@pytest.fixture(scope="module")
def doc_no_invariants() -> ProjectDoc:
    """A consumer-repo PROJECT.md with SCOPE but no ``### INVARIANTS``."""
    return parse_project_md_text(
        "# PROJECT\n\n## SCOPE\n\nIN:\n- Building the web application\n"
    )


def _on_delta_branch(text: str, doc: ProjectDoc) -> bool:
    """True when ``run_stage0`` escalated via the architecture-delta branch."""
    return run_stage0(text, doc).reason.startswith(DELTA_REASON_PREFIX)


# ---------------------------------------------------------------------------
# 1. The 30 descriptive sentences — one per phrase, derived by execution
# ---------------------------------------------------------------------------
#
# DERIVATION RULE: each sentence below was run through ``run_stage0`` against
# the pre-fix module and KEPT ONLY IF its ``reason`` began with
# ``DELTA_REASON_PREFIX``. Rows escalating via injection or OUT-of-scope were
# discarded and rewritten, never debugged into the suite — a sentence that
# escalated for the wrong reason is not evidence about this fix.

DESCRIPTIVE_SENTENCES: List[Tuple[int, str, str]] = [
    # INV-1 — enforcement is hooks, not nudges
    (1, "prompt-level advisory",
     "The rejected RFC would have made everything prompt-level advisory text instead of a gate."),
    (2, "advisory instead of blocking",
     "Today the tier gate is advisory instead of blocking, which is why nothing was refused."),
    (3, "advisory rather than blocking",
     "Reviewers kept treating the tier gate as advisory rather than blocking, so nothing"
     " was refused."),
    (4, "hooks into nudges",
     "The 2025 research explains why turning hooks into nudges produced unreliable compliance."),
    (5, "replace the hooks with",
     "The incident review shows someone tried to replace the hooks with a linter last quarter."),
    (6, "replace the blocking hooks",
     "An earlier proposal to replace the blocking hooks was withdrawn after review."),
    (7, "warning instead of blocking",
     "The check emits a warning instead of blocking, so the violation shipped."),
    # INV-2 — specialists run in fresh context
    (8, "self-attest",
     "The coordinator must not self-attest a judgment a specialist exists to make."),
    (9, "self attest",
     "The audit asks whether any coordinator can self attest a verdict without a specialist."),
    (10, "single agent sharing",
     "The audit found a single agent sharing one context across all four review stages."),
    (11, "sharing one context",
     "The postmortem describes two agents sharing one context window, which INV-2 forbids."),
    (12, "merge the reviewer",
     "Last quarter a proposal to merge the reviewer and auditor roles was rejected."),
    (13, "merge the agents",
     "The FAQ explains why we do not merge the agents into one specialist."),
    (14, "consolidate the agents",
     "An earlier RFC to consolidate the agents was withdrawn after the isolation regression."),
    # INV-3 — the pipeline shape is fixed
    (15, "reorder the pipeline",
     "The postmortem asks whether anyone did reorder the pipeline during the outage."),
    (16, "drop the alignment step",
     "Nothing in the pipeline may drop the alignment step, per PROJECT.md."),
    (17, "remove a pipeline step",
     "The runbook states that no one may remove a pipeline step without an ADR."),
    (18, "drop the acceptance",
     "The incident happened because a batch run did drop the acceptance tests silently."),
    # INV-4 — protected infrastructure is implementer-only
    (19, "outside /implement",
     "Protected paths are never edited outside /implement, which this pipeline satisfies."),
    (20, "direct editing of hooks",
     "CLAUDE md forbids direct editing of hooks outside the pipeline."),
    (21, "direct edits to hooks",
     "The hard floor blocks direct edits to hooks even under a bypass marker."),
    # INV-5 — one topic, one home
    (22, "duplicate the content",
     "The content-allocation rule says never duplicate the content across two homes."),
    (23, "duplicate this content",
     "A reviewer asked whether we should duplicate this content into the runbook;"
     " the answer is no."),
    # INV-6 — deterministic before probabilistic
    (24, "override the deterministic",
     "Currently, LLM judgment can override the deterministic layer, a bug already"
     " logged as #1600."),
    (25, "judgment override the",
     "The postmortem notes that human judgment override the automated verdict happened twice."),
    # INV-7 — gating state is signed and fails closed
    (26, "drop the hmac",
     "The bug report shows the reload path can drop the hmac signature without detection."),
    (27, "unsigned state",
     "The state file is written as unsigned state today, which is the bug."),
    (28, "fail open",
     "Measured: 4 of 7 guards fail open silently under fault injection."),
    # INV-8 — local-first and free
    (29, "paid api",
     "This must not require a paid api, per INV-8."),
    (30, "hosted model",
     "Today it uses a hosted model; the fix removes that dependency."),
]


class TestDescriptiveProseDoesNotEscalate:
    """The 30-phrase census: describing an invariant is not proposing a delta."""

    def test_census_covers_every_phrase_exactly_once(self) -> None:
        """The corpus is a census, not a sample — one row per live phrase.

        Asserted against the live tuple so a phrase added tomorrow without a
        descriptive row fails loudly instead of silently going unmeasured.
        """
        covered = [phrase for _, phrase, _ in DESCRIPTIVE_SENTENCES]
        assert len(covered) == len(set(covered)), "duplicate phrase rows in census"
        assert set(covered) == set(ARCHITECTURE_DELTA_PHRASES), (
            "census drifted from ARCHITECTURE_DELTA_PHRASES: "
            f"uncovered={set(ARCHITECTURE_DELTA_PHRASES) - set(covered)} "
            f"stale={set(covered) - set(ARCHITECTURE_DELTA_PHRASES)}"
        )

    @pytest.mark.parametrize(
        ("row", "phrase", "sentence"),
        DESCRIPTIVE_SENTENCES,
        ids=[f"row{r:02d}-{p.replace(' ', '_')}" for r, p, _ in DESCRIPTIVE_SENTENCES],
    )
    def test_descriptive_sentence_does_not_reach_delta_branch(
        self, row: int, phrase: str, sentence: str, doc: ProjectDoc
    ) -> None:
        """BEFORE the fix all 30 escalated here; AFTER, none do.

        Asserts the BRANCH (``reason``), not merely the outcome — an ESCALATE
        via injection or OUT-of-scope would be a different finding entirely and
        must not be mistaken for this one.
        """
        result = run_stage0(sentence, doc)
        assert not result.reason.startswith(DELTA_REASON_PREFIX), (
            f"row {row} ({phrase!r}) escalated on the architecture-delta branch: "
            f"{result.reason}"
        )
        assert result.architecture_delta_phrase is None, (
            f"row {row} ({phrase!r}) set architecture_delta_phrase="
            f"{result.architecture_delta_phrase!r}"
        )
        assert result.outcome is Stage0Outcome.CLEAR, (
            f"row {row} ({phrase!r}) escalated via another branch — the census "
            f"row is misattributed and must be rewritten, not debugged: "
            f"{result.reason}"
        )

    def test_detect_architecture_delta_returns_none_for_all_descriptive_rows(
        self, doc: ProjectDoc
    ) -> None:
        """Directly at the detector, bypassing run_stage0's branch precedence."""
        offenders = [
            (row, phrase, detect_architecture_delta(sentence, doc))
            for row, phrase, sentence in DESCRIPTIVE_SENTENCES
            if detect_architecture_delta(sentence, doc) is not None
        ]
        assert not offenders, f"detect_architecture_delta fired on prose: {offenders}"


# ---------------------------------------------------------------------------
# 2. Recall — the positives must still escalate
# ---------------------------------------------------------------------------

#: The three proposals stated verbatim in Issue #1600's evidence block.
STATED_PROPOSALS: List[Tuple[str, str]] = [
    ("prop-1", "Let's make the gate fail open when the classifier is unavailable."),
    ("prop-2", "Drop the hmac signing to simplify state handling."),
    ("prop-3", "Reorder the pipeline so review runs before implementation."),
]

#: ``arch-006`` is EXCLUDED here and pinned by its own test below.
_ARCH_006_ID = "arch-006"


def _arch_corpus_entries() -> List[Tuple[str, str]]:
    """The ``arch-*`` entries from the seeded corpus, read live from disk."""
    corpus = json.loads(_CORPUS_PATH.read_text())
    return [
        (e["id"], e["feature_text"])
        for e in corpus["entries"]
        if e["id"].startswith("arch-")
    ]


class TestRecallIsPreserved:
    """Stage 0's ESCALATE is un-overridable, so a lost true positive is worse
    than the noise this fix removes. The positive population is named, because
    an unnamed count is unfalsifiable: 3 stated proposals + 9 ``arch-*`` corpus
    entries = 12, of which 11 reach the delta branch."""

    @pytest.mark.parametrize(
        ("entry_id", "text"), STATED_PROPOSALS, ids=[i for i, _ in STATED_PROPOSALS]
    )
    def test_stated_proposal_still_escalates_on_delta_branch(
        self, entry_id: str, text: str, doc: ProjectDoc
    ) -> None:
        result = run_stage0(text, doc)
        assert result.outcome is Stage0Outcome.ESCALATE, f"{entry_id}: {result.reason}"
        assert result.reason.startswith(DELTA_REASON_PREFIX), (
            f"{entry_id} escalated via a different branch: {result.reason}"
        )
        assert result.architecture_delta_phrase is not None

    @pytest.mark.parametrize("entry_id,text", _arch_corpus_entries())
    def test_arch_corpus_entry_still_escalates(
        self, entry_id: str, text: str, doc: ProjectDoc
    ) -> None:
        """Every seeded ``architecture_delta`` entry still escalates.

        ``arch-006`` is asserted on OUTCOME ONLY. ``run_stage0`` checks
        ``injection_signals()`` BEFORE ``detect_architecture_delta``,
        unconditionally, and arch-006 ("Let the LLM judgment override the
        deterministic keyword check when the model is confident.") trips
        ``gate_bypass_request``. It therefore returns
        ``architecture_delta_phrase is None`` both BEFORE and AFTER this fix.
        This fix does not change that precedence. Asserting the delta branch on
        arch-006 would fail for reasons unrelated to the implementation.
        """
        result = run_stage0(text, doc)
        assert result.outcome is Stage0Outcome.ESCALATE, f"{entry_id}: {result.reason}"
        if entry_id == _ARCH_006_ID:
            return
        assert result.reason.startswith(DELTA_REASON_PREFIX), (
            f"{entry_id} escalated via a different branch: {result.reason}"
        )
        assert result.architecture_delta_phrase is not None

    def test_arch_006_escalates_via_injection_precedence_not_delta(
        self, doc: ProjectDoc
    ) -> None:
        """Pin the one documented exception so it cannot drift silently.

        If arch-006 ever starts escalating via the delta branch, the injection
        detector stopped firing on a gate-bypass request — a SAFETY regression
        that this assertion, not the outcome, is what catches.
        """
        entries = dict(_arch_corpus_entries())
        result = run_stage0(entries[_ARCH_006_ID], doc)
        assert result.outcome is Stage0Outcome.ESCALATE
        assert result.injection_detected is True
        assert result.reason.startswith("injection signals detected:"), result.reason
        assert result.architecture_delta_phrase is None

    def test_named_population_yields_eleven_of_twelve_on_delta_branch(
        self, doc: ProjectDoc
    ) -> None:
        """The census figure itself, asserted rather than asserted-about."""
        population = STATED_PROPOSALS + _arch_corpus_entries()
        assert len(population) == 12, f"population drifted: {len(population)}"
        on_branch = [eid for eid, text in population if _on_delta_branch(text, doc)]
        off_branch = [eid for eid, text in population if not _on_delta_branch(text, doc)]
        assert len(on_branch) == 11, f"on delta branch: {on_branch}"
        assert off_branch == [_ARCH_006_ID], f"unexpected off-branch entries: {off_branch}"


# ---------------------------------------------------------------------------
# 3. The detector can still fail — a guard watched only permitting is unproven
# ---------------------------------------------------------------------------


class TestDetectorCanStillFire:
    """Refusing arm. Each input below is a DIFFERENT shape from the census
    rows, so passing here is not an artifact of the corpus construction."""

    def test_imperative_proposal_escalates(self, doc: ProjectDoc) -> None:
        result = run_stage0(
            "Make the alignment gate fail open when the classifier is unavailable.", doc
        )
        assert result.outcome is Stage0Outcome.ESCALATE
        assert result.architecture_delta_phrase == "fail open"

    def test_proposal_lead_in_colon_escalates(self, doc: ProjectDoc) -> None:
        """Segmentation is live: the onset is the token AFTER the colon."""
        result = run_stage0("Proposal: drop the hmac signing from the pipeline state.", doc)
        assert result.reason.startswith(DELTA_REASON_PREFIX), result.reason
        assert result.architecture_delta_phrase == "drop the hmac"

    def test_markdown_bullet_proposal_escalates(self, doc: ProjectDoc) -> None:
        """A proposal written as a list item is not exempted by its bullet.

        Purely punctuational leading tokens are skipped when locating the
        onset; without that, ``- **Let's** merge ...`` would CLEAR and this
        fix would be a recall regression on the most common brief shape.
        """
        result = run_stage0("- **Let's** merge the reviewer and the security auditor.", doc)
        assert result.reason.startswith(DELTA_REASON_PREFIX), result.reason
        assert result.architecture_delta_phrase == "merge the reviewer"

    def test_volitional_lets_contraction_is_an_onset(self, doc: ProjectDoc) -> None:
        """``Let's`` truncates at the apostrophe to ``let``."""
        assert detect_architecture_delta(
            "let's drop the alignment step from the pipeline", doc
        ) == "drop the alignment step"

    def test_third_person_declarative_is_not_an_onset(self, doc: ProjectDoc) -> None:
        """``Replaces`` != ``replace`` — exact token equality is load-bearing.

        This single distinction is why the #1600 repair brief clears.
        """
        assert detect_architecture_delta(
            "Replaces prompt-level advisory text with a hook that returns decision block.", doc
        ) is None
        assert detect_architecture_delta(
            "Replace the prompt-level advisory text with a nudge.", doc
        ) == "prompt-level advisory"


class TestOnsetVerbSetIntegrity:
    """The onset set is a PROPOSAL list, never a suppression list."""

    #: Verbs a repair brief opens with. Admitting any one recreates #1600.
    REPAIR_VERBS = frozenset(
        {
            "fix", "add", "document", "test", "harden", "strengthen",
            "block", "enforce", "restore", "gate", "tighten",
        }
    )

    def test_no_repair_verb_is_an_onset_verb(self) -> None:
        overlap = self.REPAIR_VERBS & PROPOSAL_ONSET_VERBS
        assert not overlap, (
            f"repair verbs leaked into PROPOSAL_ONSET_VERBS: {sorted(overlap)}. "
            "A brief that repairs an invariant violation opens with exactly "
            "these — admitting one recreates Issue #1600."
        )

    def test_onset_verbs_are_lowercase_single_tokens(self) -> None:
        for verb in PROPOSAL_ONSET_VERBS:
            assert verb == verb.lower(), f"{verb!r} is not lowercase"
            assert " " not in verb, f"{verb!r} is not a single token"

    def test_onset_verb_set_is_non_empty_and_frozen(self) -> None:
        assert isinstance(PROPOSAL_ONSET_VERBS, frozenset)
        assert len(PROPOSAL_ONSET_VERBS) >= 20, len(PROPOSAL_ONSET_VERBS)


class TestPhraseTupleIntegrity:
    """Structural invariants of the phrase tuple itself."""

    def test_phrase_tuple_has_thirty_entries(self) -> None:
        """Pinned so a silent addition cannot go unmeasured by the census."""
        assert len(ARCHITECTURE_DELTA_PHRASES) == 30

    def test_no_phrase_contains_a_segment_delimiter(self) -> None:
        """Segmentation safety, asserted over the LIVE tuple.

        A phrase containing ``[\\n.;:!?,]`` would straddle two segments and
        become permanently unmatchable — a silent recall loss. This fails
        loudly the day such a phrase is added.
        """
        delimiter = re.compile(r"[\n.;:!?,]")
        offenders = [p for p in ARCHITECTURE_DELTA_PHRASES if delimiter.search(p)]
        assert not offenders, (
            f"phrases containing a segment delimiter are unmatchable: {offenders}"
        )


# ---------------------------------------------------------------------------
# 4. Negative controls of a DIFFERENT shape
# ---------------------------------------------------------------------------


class TestDifferentShapeNegativeControls:
    """Not sentences from the census — policy prose, a code fence, a table."""

    def test_claude_md_protected_paths_rule_clears(self, doc: ProjectDoc) -> None:
        result = run_stage0(
            "NEVER direct-edit without /implement: agents/*.md, commands/*.md, "
            "hooks/*.py, lib/*.py, skills/*/SKILL.md — these are functional "
            "infrastructure. Hook-enforced: unified_pre_tool.py blocks Write/Edit "
            "to these paths outside /implement.",
            doc,
        )
        assert result.outcome is Stage0Outcome.CLEAR, result.reason
        assert result.architecture_delta_phrase is None

    def test_fenced_command_output_clears(self, doc: ProjectDoc) -> None:
        result = run_stage0(
            "```bash\n$ python3 scripts/proof_of_block.py --fault-injection\n"
            "4 of 7 guards fail open\n```",
            doc,
        )
        assert result.outcome is Stage0Outcome.CLEAR, result.reason
        assert result.architecture_delta_phrase is None

    def test_markdown_table_row_clears(self, doc: ProjectDoc) -> None:
        result = run_stage0(
            "| INV-7 | gating state is signed and fails closed | "
            "unsigned state is the defect |",
            doc,
        )
        assert result.outcome is Stage0Outcome.CLEAR, result.reason
        assert result.architecture_delta_phrase is None


# ---------------------------------------------------------------------------
# 5. Consumer-repo exemption — the executable guard at the top of the detector
# ---------------------------------------------------------------------------


class TestConsumerRepoExemption:
    """realign and spektiv must never be blocked on an axis their PROJECT.md
    does not define. This is the FIRST check in the detector and must stay so."""

    def test_no_invariants_clears_even_with_a_proposal_onset(
        self, doc_no_invariants: ProjectDoc
    ) -> None:
        """A phrase WITH an onset — the shape that escalates in this repo."""
        assert doc_no_invariants.has_invariants is False
        assert detect_architecture_delta(
            "Drop the hmac signing to simplify state handling.", doc_no_invariants
        ) is None
        result = run_stage0("Drop the hmac signing to simplify state handling.", doc_no_invariants)
        assert result.architecture_delta_phrase is None

    def test_empty_feature_text_returns_none(self, doc: ProjectDoc) -> None:
        assert detect_architecture_delta("", doc) is None

    def test_exemption_guard_is_first_and_unchanged(self) -> None:
        """The two guard lines are asserted verbatim, in order, as the first
        statements of the function body — a reorder would let a consumer repo
        be evaluated against invariants it never declared."""
        source = (_LIB_DIR / "alignment_classifier.py").read_text().splitlines()
        start = next(
            i for i, line in enumerate(source)
            if line.startswith("def detect_architecture_delta(")
        )
        body = source[start:]
        end_of_docstring = [
            i for i, line in enumerate(body[:60]) if line.strip() == '"""'
        ]
        assert end_of_docstring, "detect_architecture_delta docstring not found"
        first_stmt = end_of_docstring[0] + 1
        assert body[first_stmt] == (
            "    if not feature_text or not doc.has_invariants:"
        ), body[first_stmt]
        assert body[first_stmt + 1] == "        return None", body[first_stmt + 1]


# ---------------------------------------------------------------------------
# 6. Determinism — INV-6
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Stage 0's ESCALATE is un-overridable by an LLM, so it must not depend on
    one. No network, no model, no import beyond ``re``."""

    def test_detector_is_pure_and_repeatable(self, doc: ProjectDoc) -> None:
        text = "Drop the hmac signing to simplify state handling."
        results = {detect_architecture_delta(text, doc) for _ in range(25)}
        assert results == {"drop the hmac"}

    def test_onset_helpers_use_no_network_or_model_calls(self) -> None:
        """Source-level assertion over the region this issue introduced."""
        source = (_LIB_DIR / "alignment_classifier.py").read_text()
        start = source.index("PROPOSAL_ONSET_VERBS: FrozenSet[str]")
        end = source.index("# Stage 0 orchestration")
        region = source[start:end]
        for forbidden in ("requests", "urllib", "httpx", "subprocess", "openai", "anthropic"):
            assert forbidden not in region, (
                f"{forbidden!r} appears in the Issue #1600 region — Stage 0 must "
                "stay deterministic and offline (INV-6)"
            )


# ---------------------------------------------------------------------------
# 7. Live-brief acceptance — the two production misfires
# ---------------------------------------------------------------------------


class TestProductionMisfiresNoLongerEscalate:
    """The real acceptance signal, not 'tests pass'."""

    def test_issue_1600_repair_brief_clears(self, doc: ProjectDoc) -> None:
        """Verbatim ``feature_text`` from ``.claude/alignment_verdict.json``.

        That artifact records ``stage0_reason: "architecture invariant delta:
        'prompt-level advisory'"`` — the escalation this fix removes — and a
        Stage 1 verdict of ``in_scope`` at confidence 0.9. The two disagreed;
        Stage 0 was the one that was wrong.
        """
        verdict = json.loads((_REPO_ROOT / ".claude" / "alignment_verdict.json").read_text())
        assert verdict.get("issue_number") == "1600", "verdict artifact is not #1600's"
        assert verdict["stage0_reason"].startswith(DELTA_REASON_PREFIX), (
            "the recorded pre-fix escalation is missing — the BEFORE half of "
            f"this regression test is unproven: {verdict['stage0_reason']!r}"
        )
        result = run_stage0(verdict["feature_text"], doc)
        assert result.outcome is Stage0Outcome.CLEAR, result.reason
        assert result.architecture_delta_phrase is None

    def test_issue_1586_measured_finding_clears(self, doc: ProjectDoc) -> None:
        """The sentence quoted in #1600 as the live #1586 STEP 2 trigger."""
        for sentence in (
            "Measured: 4 of 7 guards fail open silently under fault injection.",
            "It found that 4 of 7 guards fail open silently under fault injection.",
        ):
            result = run_stage0(sentence, doc)
            assert result.outcome is Stage0Outcome.CLEAR, f"{sentence!r}: {result.reason}"
            assert result.architecture_delta_phrase is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
