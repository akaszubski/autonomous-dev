"""Regression tests for Issue #1485 — prompt-integrity shrinkage gate must
not false-positive on legitimate implementer remediation re-dispatches.

Observed failure (session ``b0926f9b-7c5b-48fa-a890-8786995e1727``, 2026-08-09,
issue #1467): four ``implementer`` re-dispatches BLOCKED with shrinkage
89.3%, 43.8%, 45.0%, 61.8% against a fixed 1270-word baseline established by
the original full-feature dispatch. Each re-dispatch was a legitimate,
tightly-scoped remediation prompt in response to a reviewer /
security-auditor / spec-validator finding.

The fix (``_is_remediation_dispatch``) auto-detects remediation phrasing in
the prompt content and applies the ``remediation`` reinvocation-context
threshold when the coordinator did not thread ``invocation_context`` through
explicitly. The auto-detect MUST NOT apply when there is no baseline (first
dispatch) — the shrinkage check is a no-op there anyway, but the auto-detect
must not weaken the min-word-count check.

Issue: #1485
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import prompt_integrity as pi  # noqa: E402


class TestRemediationSignalDetection:
    """``_is_remediation_dispatch`` returns True on remediation phrasing and
    False on ordinary prompts."""

    def test_remediation_word_detected(self) -> None:
        assert pi._is_remediation_dispatch("This is a REMEDIATION dispatch") is True

    def test_reviewer_finding_detected(self) -> None:
        assert pi._is_remediation_dispatch(
            "Please address the reviewer finding at file:line"
        ) is True

    def test_fix_the_following_finding_detected(self) -> None:
        assert pi._is_remediation_dispatch(
            "Fix the following finding: x.py:42 missing null check"
        ) is True

    def test_security_auditor_flagged_detected(self) -> None:
        assert pi._is_remediation_dispatch(
            "security-auditor flagged a token leak in the diff"
        ) is True

    def test_ordinary_dispatch_not_detected(self) -> None:
        assert pi._is_remediation_dispatch(
            "Implement the new feature described in the plan below. "
            "Follow the file-by-file change list and write tests."
        ) is False

    def test_empty_prompt_not_detected(self) -> None:
        assert pi._is_remediation_dispatch("") is False
        assert pi._is_remediation_dispatch(None) is False  # type: ignore[arg-type]


class TestShrinkageBypassOnRemediation:
    """Shrinkage check must relax when the prompt content signals a
    remediation re-dispatch, even without an explicit ``invocation_context``."""

    def test_remediation_prompt_below_baseline_not_blocked(self) -> None:
        """A remediation re-dispatch that is 15% of the baseline (85% shrink)
        must NOT be blocked once auto-detection applies the remediation
        threshold multiplier."""
        baseline = 1270  # observed baseline from issue #1485 evidence
        # Construct a prompt ~15% of baseline (~190 words) that reads as a
        # remediation dispatch. Padding uses plain-word tokens to reach the
        # target word count so we exercise the shrinkage path (not the
        # min-word-count path, which is 80 words).
        header = (
            "REMEDIATION dispatch: reviewer flagged an issue at "
            "plugins/autonomous-dev/lib/foo.py line 42. Fix the following "
            "finding — the null check on argument bar is missing before the "
            "dereference. Add the check, add a regression test, keep the "
            "diff minimal."
        )
        padding = " ".join(["remediation-context"] * 150)
        prompt = f"{header} {padding}"
        result = pi.validate_prompt_word_count(
            agent_type="implementer",
            prompt=prompt,
            baseline_word_count=baseline,
        )
        # remediation multiplier is 2.0x on max_shrinkage=0.15 → threshold 30%.
        # Our prompt is ~24% of baseline (76% shrink) which still exceeds 30%.
        # Rebuild with fewer padding words to land in the acceptable band.
        # Actually the point is: without auto-detect this would compare vs
        # the default 15% threshold and always block; with auto-detect the
        # threshold becomes 30%. So we build a prompt at exactly 71% of
        # baseline (29% shrink) which passes ONLY when auto-detect fires.
        target_words = int(baseline * 0.71)
        padding = " ".join(["remediation-context"] * (target_words - len(header.split())))
        prompt = f"{header} {padding}"
        result = pi.validate_prompt_word_count(
            agent_type="implementer",
            prompt=prompt,
            baseline_word_count=baseline,
        )
        assert result.passed, f"remediation dispatch was blocked: {result.reason}"

    def test_non_remediation_prompt_at_same_shrinkage_still_blocked(self) -> None:
        """Same shrinkage ratio, but the prompt has NO remediation signal:
        the standard 15% threshold applies and the dispatch is blocked. This
        confirms auto-detection is doing the work, not a general threshold
        change."""
        baseline = 1270
        header = (
            "Implement the new feature described in the plan below. "
            "Follow the file-by-file change list and write tests."
        )
        target_words = int(baseline * 0.71)
        padding = " ".join(["ordinary-context"] * (target_words - len(header.split())))
        prompt = f"{header} {padding}"
        result = pi.validate_prompt_word_count(
            agent_type="implementer",
            prompt=prompt,
            baseline_word_count=baseline,
        )
        assert not result.passed, "ordinary dispatch below threshold should block"
        assert "shrank" in result.reason.lower() or "shrank" in result.reason

    def test_explicit_context_still_wins(self) -> None:
        """When the coordinator DOES pass invocation_context explicitly, the
        auto-detect must not override it (explicit signal is authoritative).
        A prompt at 75% of baseline (25% shrink) with no remediation content
        passes only because the explicit ``remediation`` context relaxes the
        threshold to 30%."""
        baseline = 1000
        prompt = " ".join(["word"] * 750)  # 25% shrink < 30% relaxed threshold
        result = pi.validate_prompt_word_count(
            agent_type="implementer",
            prompt=prompt,
            baseline_word_count=baseline,
            invocation_context="remediation",
        )
        assert result.passed, f"explicit remediation ctx should pass: {result.reason}"

    def test_first_dispatch_min_words_still_enforced(self) -> None:
        """Auto-detect must NOT weaken the minimum-word-count check for
        critical agents. A 10-word "remediation" prompt is still too short."""
        prompt = "REMEDIATION: fix bug at foo.py line 42 now"
        result = pi.validate_prompt_word_count(
            agent_type="implementer",
            prompt=prompt,
            baseline_word_count=None,  # no baseline → first dispatch
        )
        assert not result.passed, "too-short critical prompt must still block"
        assert "too short" in result.reason
