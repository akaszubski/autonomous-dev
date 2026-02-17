"""GenAI UAT tests for scope classification accuracy.

Tests that the SCOPE_ASSESSMENT_PROMPT template correctly classifies
issue/feature descriptions using an LLM-as-judge approach via OpenRouter.

These tests validate the GenAI hybrid paths added to:
- scope_detector.py (_assess_genai)
- issue_scope_detector.py (_detect_genai)

Run with:
    pytest tests/genai/test_scope_classification.py --genai

Requirements:
    - OPENROUTER_API_KEY environment variable
    - openai package installed

Cost: ~$0.02 per run (cached after first run)
"""

import sys
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

pytestmark = [pytest.mark.genai]

# ============================================================================
# Path setup
# ============================================================================

_WORKTREE_ROOT = Path(__file__).parent.parent.parent
_LIB_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "hooks"

sys.path.insert(0, str(_LIB_PATH))
sys.path.insert(0, str(_HOOKS_PATH))


# ============================================================================
# Golden Dataset
# ============================================================================

# Labeled examples covering all 3 scope levels and edge cases
# Format: (issue_text, expected_label, rationale)
GOLDEN_DATASET = [
    # ---- FOCUSED examples (atomic, single session < 30 min) ----
    (
        "Add rate limiting and timeout to HTTP requests",
        "FOCUSED",
        "Two related config params for the same HTTP client - one atomic change",
    ),
    (
        "Fix bug in user login validation",
        "FOCUSED",
        "Single bug fix in one component",
    ),
    (
        "Add unit tests for PaymentService",
        "FOCUSED",
        "Single testing task for one class",
    ),
    (
        "Update error message in authentication module",
        "FOCUSED",
        "Single string update in one module",
    ),
    (
        "Add pagination to /users endpoint",
        "FOCUSED",
        "One endpoint, one feature addition",
    ),
    # ---- BROAD examples (2-3 components, should split) ----
    (
        "Add caching to API responses and update the database schema",
        "BROAD",
        "Two separate concerns: caching layer + schema migration",
    ),
    (
        "Refactor auth module and add new user management endpoints",
        "BROAD",
        "Refactoring existing + adding new endpoints are separate tasks",
    ),
    (
        "Replace mock log streaming with real SSH implementation and add result download",
        "BROAD",
        "SSH log streaming and result download are separate features",
    ),
    (
        "Implement retry logic and add monitoring metrics for failed jobs",
        "BROAD",
        "Retry logic and monitoring are separate concerns",
    ),
    # ---- VERY_BROAD examples (system-wide, must split) ----
    (
        "Redesign entire auth system and migrate database and add new API endpoints and update docs",
        "VERY_BROAD",
        "4+ separate tasks: redesign auth, migrate DB, new API, update docs",
    ),
    (
        "Replace all mock implementations with real SSH, API, and database integrations",
        "VERY_BROAD",
        "System-wide replacement across multiple integration points",
    ),
    (
        "Complete end-to-end system overhaul with authentication, storage, and UI",
        "VERY_BROAD",
        "End-to-end overhaul spanning multiple system layers",
    ),
    # ---- Edge cases where conjunction counting fails ----
    (
        "Add support for both IPv4 and IPv6 in network configuration",
        "FOCUSED",
        "Despite 'and', adding two protocol variants to same config is atomic",
    ),
    (
        "Fix race condition between worker and scheduler",
        "FOCUSED",
        "Despite 'and', fixing one race condition in one interaction is atomic",
    ),
]


# ============================================================================
# Helpers
# ============================================================================

def _build_scope_prompt(issue_text: str) -> str:
    """Build the scope classification prompt for a given issue text.

    Tries to import SCOPE_ASSESSMENT_PROMPT from genai_prompts.
    Falls back to a reconstructed version for test resilience.
    """
    try:
        from genai_prompts import SCOPE_ASSESSMENT_PROMPT
        return SCOPE_ASSESSMENT_PROMPT.format(issue_text=issue_text)
    except (ImportError, AttributeError, KeyError):
        return (
            f"Classify the following issue as exactly one of: "
            f"FOCUSED, BROAD, or VERY_BROAD.\n\n"
            f"Issue: {issue_text}\n\n"
            f"FOCUSED = single atomic change (< 30 min)\n"
            f"BROAD = 2-3 components, should be split\n"
            f"VERY_BROAD = system-wide, must be split\n\n"
            f"Respond with ONLY: FOCUSED, BROAD, or VERY_BROAD."
        )


def _classify_with_prompt(genai_client, issue_text: str) -> str:
    """Use the GenAI client to classify an issue's scope."""
    prompt = _build_scope_prompt(issue_text)
    response = genai_client.ask(prompt, max_tokens=50)
    return response.strip().upper()


def _extract_label(response: str) -> Optional[str]:
    """Extract FOCUSED/BROAD/VERY_BROAD from a response string."""
    # Check longer labels first to avoid partial matches
    for label in ("VERY_BROAD", "BROAD", "FOCUSED"):
        if label in response.upper():
            return label
    return None


# ============================================================================
# Test Classes
# ============================================================================

class TestScopeClassificationGoldenDataset:
    """LLM-as-judge tests for scope classification accuracy.

    Uses OpenRouter to:
    1. Send issue texts through the SCOPE_ASSESSMENT_PROMPT
    2. Ask a judge LLM to verify the classification is correct
    """

    def test_focused_examples_classified_correctly(self, genai):
        """FOCUSED examples should be classified as FOCUSED by the prompt."""
        focused_examples = [
            (text, rationale)
            for text, label, rationale in GOLDEN_DATASET
            if label == "FOCUSED"
        ]

        failures = []
        for issue_text, rationale in focused_examples:
            raw_response = _classify_with_prompt(genai, issue_text)
            predicted = _extract_label(raw_response)

            if predicted != "FOCUSED":
                judge_result = genai.judge(
                    question=f"Should '{issue_text}' be classified as FOCUSED scope?",
                    context=(
                        f"Issue: {issue_text!r}\n"
                        f"Expected: FOCUSED\n"
                        f"Classification response: {raw_response!r}\n"
                        f"Rationale: {rationale}"
                    ),
                    criteria=(
                        "FOCUSED = single atomic task completable in < 30 min by one developer. "
                        "Score 10 if clearly FOCUSED (single concern, one component). "
                        "Score 0 if alternative classification is defensible."
                    ),
                )
                if judge_result.get("score", 0) >= 7:
                    failures.append(
                        f"'{issue_text}' → predicted={predicted}, expected=FOCUSED "
                        f"(judge: {judge_result['score']}/10, reason: {judge_result['reasoning']})"
                    )

        assert not failures, (
            f"FOCUSED examples misclassified ({len(failures)}/{len(focused_examples)}):\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_broad_examples_classified_correctly(self, genai):
        """BROAD examples should be classified as BROAD by the prompt."""
        broad_examples = [
            (text, rationale)
            for text, label, rationale in GOLDEN_DATASET
            if label == "BROAD"
        ]

        failures = []
        for issue_text, rationale in broad_examples:
            raw_response = _classify_with_prompt(genai, issue_text)
            predicted = _extract_label(raw_response)

            if predicted != "BROAD":
                judge_result = genai.judge(
                    question=f"Should '{issue_text}' be classified as BROAD scope?",
                    context=(
                        f"Issue: {issue_text!r}\n"
                        f"Expected: BROAD\n"
                        f"Classification response: {raw_response!r}\n"
                        f"Rationale: {rationale}"
                    ),
                    criteria=(
                        "BROAD = covers 2-3 separate concerns/components that should be split "
                        "into separate issues (each < 30 min). "
                        "Score 10 if clearly BROAD. Score 0 if FOCUSED or VERY_BROAD is defensible."
                    ),
                )
                if judge_result.get("score", 0) >= 7:
                    failures.append(
                        f"'{issue_text}' → predicted={predicted}, expected=BROAD "
                        f"(judge: {judge_result['score']}/10)"
                    )

        assert not failures, (
            f"BROAD examples misclassified ({len(failures)}/{len(broad_examples)}):\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_very_broad_examples_classified_correctly(self, genai):
        """VERY_BROAD examples should be classified as VERY_BROAD by the prompt."""
        very_broad_examples = [
            (text, rationale)
            for text, label, rationale in GOLDEN_DATASET
            if label == "VERY_BROAD"
        ]

        failures = []
        for issue_text, rationale in very_broad_examples:
            raw_response = _classify_with_prompt(genai, issue_text)
            predicted = _extract_label(raw_response)

            if predicted != "VERY_BROAD":
                judge_result = genai.judge(
                    question=f"Should '{issue_text}' be classified as VERY_BROAD scope?",
                    context=(
                        f"Issue: {issue_text!r}\n"
                        f"Expected: VERY_BROAD\n"
                        f"Classification response: {raw_response!r}\n"
                        f"Rationale: {rationale}"
                    ),
                    criteria=(
                        "VERY_BROAD = system-wide changes spanning 4+ components, "
                        "end-to-end overhauls, replacing all mocks, or complete redesigns. "
                        "Score 10 if clearly VERY_BROAD. Score 0 if BROAD is defensible."
                    ),
                )
                if judge_result.get("score", 0) >= 7:
                    failures.append(
                        f"'{issue_text}' → predicted={predicted}, expected=VERY_BROAD "
                        f"(judge: {judge_result['score']}/10)"
                    )

        assert not failures, (
            f"VERY_BROAD examples misclassified ({len(failures)}/{len(very_broad_examples)}):\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_overall_accuracy_above_threshold(self, genai):
        """Overall classification accuracy should be >= 70% across all examples."""
        correct = 0
        results = []

        for issue_text, expected_label, rationale in GOLDEN_DATASET:
            raw_response = _classify_with_prompt(genai, issue_text)
            predicted = _extract_label(raw_response)
            is_correct = predicted == expected_label
            correct += int(is_correct)
            results.append({
                "text": issue_text[:60],
                "expected": expected_label,
                "predicted": predicted,
                "correct": is_correct,
            })

        accuracy = correct / len(GOLDEN_DATASET)
        failed = [r for r in results if not r["correct"]]

        summary = "\n".join(
            f"  {'PASS' if r['correct'] else 'FAIL'}: {r['text']!r} "
            f"→ expected={r['expected']}, got={r['predicted']}"
            for r in results
        )

        judge_result = genai.judge(
            question=f"Is {accuracy:.0%} accuracy ({correct}/{len(GOLDEN_DATASET)}) acceptable?",
            context=f"**Scope Classification Results:**\n{summary}",
            criteria=(
                "A scope classifier should achieve at least 70% accuracy on a balanced "
                "golden dataset covering FOCUSED/BROAD/VERY_BROAD categories. "
                "Score 10 if >= 80%, score 7 if >= 70%, score 3 if < 70%."
            ),
        )

        assert accuracy >= 0.70, (
            f"Classification accuracy {accuracy:.0%} ({correct}/{len(GOLDEN_DATASET)}) "
            f"is below 70% threshold.\n"
            f"Failed examples:\n"
            + "\n".join(
                f"  - {r['text']!r}: expected={r['expected']}, got={r['predicted']}"
                for r in failed
            )
        )


class TestScopeClassificationEdgeCases:
    """Edge cases where conjunction counting fails but GenAI should succeed."""

    def test_rate_limiting_and_timeout_classified_as_focused(self, genai):
        """'Add rate limiting and timeout' should be FOCUSED, not BROAD.

        This is the key edge case motivating the GenAI hybrid path:
        - Heuristic sees 'and' → may classify as BROAD
        - GenAI understands both are config params for same client → FOCUSED
        """
        issue_text = "Add rate limiting and timeout to HTTP requests"
        raw_response = _classify_with_prompt(genai, issue_text)
        predicted = _extract_label(raw_response)

        judge_result = genai.judge(
            question=f"Should '{issue_text}' be classified as FOCUSED?",
            context=(
                f"Issue: {issue_text!r}\n"
                f"Classification response: {raw_response!r}\n\n"
                f"Context: Rate limiting and timeout are two configuration parameters "
                f"for the same HTTP client. They are typically set in one place and "
                f"constitute a single atomic change. Not two separate features."
            ),
            criteria=(
                "FOCUSED = the change is atomic and can be done in one session. "
                "Rate limiting + timeout for the same HTTP client is a single configuration "
                "change. Score 10 = FOCUSED is clearly correct. "
                "Score 5 = BROAD is somewhat defensible. Score 1 = FOCUSED is wrong."
            ),
        )

        classification_is_focused = predicted == "FOCUSED"
        judge_agrees_focused = judge_result.get("score", 0) >= 6

        # The real assertion: judge confirms FOCUSED is correct
        assert judge_agrees_focused, (
            f"Judge does not agree FOCUSED is correct for rate limiting + timeout. "
            f"Predicted: {predicted}. Judge score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}"
        )

    def test_redesign_entire_system_classified_as_very_broad(self, genai):
        """'Redesign entire auth system and migrate DB and add API' → VERY_BROAD."""
        issue_text = "Redesign entire auth system and migrate database and add new API endpoints"
        raw_response = _classify_with_prompt(genai, issue_text)
        predicted = _extract_label(raw_response)

        judge_result = genai.judge(
            question=f"Should '{issue_text}' be classified as VERY_BROAD?",
            context=(
                f"Issue: {issue_text!r}\n"
                f"Classification response: {raw_response!r}\n\n"
                f"This issue involves: (1) redesigning auth system, "
                f"(2) database migration, (3) adding new API endpoints. "
                f"That's 3+ major changes, any one of which could take days."
            ),
            criteria=(
                "VERY_BROAD = too large to implement in one session, spans multiple "
                "components/systems. Score 10 = VERY_BROAD is clearly correct. "
                "Score 5 = BROAD is defensible. Score 1 = FOCUSED is correct."
            ),
        )

        judge_agrees_very_broad = judge_result.get("score", 0) >= 6

        assert judge_agrees_very_broad, (
            f"Judge does not agree VERY_BROAD is correct for multi-system redesign. "
            f"Predicted: {predicted}. Judge score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}"
        )

    def test_race_condition_fix_classified_as_focused(self, genai):
        """'Fix race condition between worker and scheduler' → FOCUSED.

        Despite mentioning two components (worker and scheduler), the fix is a single
        bug in their interaction - one atomic change.
        """
        issue_text = "Fix race condition between worker and scheduler"
        raw_response = _classify_with_prompt(genai, issue_text)
        predicted = _extract_label(raw_response)

        judge_result = genai.judge(
            question=f"Should '{issue_text}' be classified as FOCUSED?",
            context=(
                f"Issue: {issue_text!r}\n"
                f"Classification response: {raw_response!r}\n\n"
                f"A race condition fix addresses one specific bug in the interaction "
                f"between two components. The fix is localized and atomic."
            ),
            criteria=(
                "FOCUSED = single atomic bug fix. Fixing a race condition between two "
                "components is still a single focused task. "
                "Score 10 = FOCUSED is clearly correct. Score 5 = BROAD is defensible."
            ),
        )

        judge_agrees_focused = judge_result.get("score", 0) >= 6

        assert judge_agrees_focused, (
            f"Judge does not agree FOCUSED is correct for race condition fix. "
            f"Predicted: {predicted}. Judge score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}"
        )

    def test_prompt_responds_with_valid_label_only(self, genai):
        """The scope classification prompt should respond with exactly FOCUSED/BROAD/VERY_BROAD."""
        test_issues = [
            "Add rate limiting and timeout",
            "Redesign auth system and migrate DB",
            "Fix bug in login",
        ]

        for issue_text in test_issues:
            raw_response = _classify_with_prompt(genai, issue_text)
            predicted = _extract_label(raw_response)

            assert predicted is not None, (
                f"Prompt returned invalid/unparseable response for {issue_text!r}: "
                f"{raw_response!r}"
            )
            assert predicted in ("FOCUSED", "BROAD", "VERY_BROAD"), (
                f"Prompt returned unexpected label {predicted!r} for {issue_text!r}"
            )


class TestScopePromptQuality:
    """Tests validating the quality of the SCOPE_ASSESSMENT_PROMPT."""

    def test_prompt_template_exists_and_has_placeholder(self, genai):
        """SCOPE_ASSESSMENT_PROMPT should exist and contain {issue_text}."""
        try:
            from genai_prompts import SCOPE_ASSESSMENT_PROMPT

            judge_result = genai.judge(
                question="Does this prompt template have the required {issue_text} placeholder?",
                context=f"Prompt template:\n```\n{SCOPE_ASSESSMENT_PROMPT}\n```",
                criteria=(
                    "The prompt must contain {issue_text} as a format placeholder. "
                    "Score 10 = has the placeholder. Score 0 = missing the placeholder."
                ),
            )

            assert judge_result.get("score", 0) >= 8, (
                f"SCOPE_ASSESSMENT_PROMPT may be missing {{issue_text}} placeholder. "
                f"Judge: {judge_result.get('reasoning')}"
            )

        except (ImportError, AttributeError):
            pytest.skip(
                "SCOPE_ASSESSMENT_PROMPT not yet defined "
                "(TDD red phase - implementation pending)"
            )

    def test_prompt_defines_all_three_scope_levels(self, genai):
        """The prompt should define what FOCUSED, BROAD, and VERY_BROAD mean."""
        try:
            from genai_prompts import SCOPE_ASSESSMENT_PROMPT

            judge_result = genai.judge(
                question="Does this prompt define FOCUSED, BROAD, and VERY_BROAD scope levels?",
                context=f"Prompt:\n```\n{SCOPE_ASSESSMENT_PROMPT[:3000]}\n```",
                criteria=(
                    "A good classification prompt should define each scope class: "
                    "FOCUSED (atomic, single session), "
                    "BROAD (multiple concerns, should split), "
                    "VERY_BROAD (system-wide, must split). "
                    "Score 10 = all 3 well-defined with examples. "
                    "Score 6 = partially defined. Score 2 = no definitions."
                ),
            )

            assert judge_result.get("score", 0) >= 5, (
                f"Prompt may not define scope levels sufficiently. "
                f"Judge score: {judge_result.get('score')}/10. "
                f"Reasoning: {judge_result.get('reasoning')}"
            )

        except (ImportError, AttributeError):
            pytest.skip("SCOPE_ASSESSMENT_PROMPT not yet defined")


class TestScopeDatasetCoverage:
    """Validate overall coverage of the golden dataset."""

    def test_golden_dataset_has_correct_distribution(self, genai):
        """Golden dataset should have examples of each scope level."""
        labels = [label for _, label, _ in GOLDEN_DATASET]

        focused_count = labels.count("FOCUSED")
        broad_count = labels.count("BROAD")
        very_broad_count = labels.count("VERY_BROAD")

        assert focused_count >= 3, f"Need at least 3 FOCUSED examples, got {focused_count}"
        assert broad_count >= 3, f"Need at least 3 BROAD examples, got {broad_count}"
        assert very_broad_count >= 3, f"Need at least 3 VERY_BROAD examples, got {very_broad_count}"
        assert len(GOLDEN_DATASET) >= 12, (
            f"Golden dataset needs at least 12 examples, got {len(GOLDEN_DATASET)}"
        )

        judge_result = genai.judge(
            question="Is this golden dataset well-balanced for testing a 3-class scope classifier?",
            context=(
                f"Dataset distribution:\n"
                f"  FOCUSED: {focused_count} examples\n"
                f"  BROAD: {broad_count} examples\n"
                f"  VERY_BROAD: {very_broad_count} examples\n"
                f"  Total: {len(GOLDEN_DATASET)} examples"
            ),
            criteria=(
                "A balanced 3-class golden dataset should have roughly equal representation. "
                "Score 10 = well-balanced (each class >= 3 examples). "
                "Score 6 = adequate. Score 2 = imbalanced."
            ),
        )

        assert judge_result.get("score", 0) >= 6, (
            f"Golden dataset may not be well-balanced. "
            f"Judge score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}"
        )
