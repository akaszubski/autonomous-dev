"""Fail-closed enforcement for the prompt-integrity shrinkage HARD GATE (Issue #1471).

Background — the bug this file locks out:

``validate_prompt_integrity`` in ``unified_pre_tool.py`` wrapped its entire
baseline-shrinkage block in a bare ``except Exception: pass``. When the
``PromptIntegrityResult`` field was renamed (``shrinkage_percent`` ->
``shrinkage_pct``) the hook's deny-message f-string kept reading
``result.shrinkage_pct``, which raised ``AttributeError``. The broad handler
swallowed it and execution fell through to ``return ("allow", ...)`` — so the
HARD GATE was silently fail-OPEN for every compression-critical agent.

The fix splits the handler:

* ``ImportError`` (module genuinely unavailable) -> fail OPEN, by design.
* ``IOError`` / ``OSError`` / ``json.JSONDecodeError`` (baseline file I/O)
  -> fail OPEN, by design; disk problems must not block agents.
* Any *other* ``Exception`` -> fail CLOSED (``deny``) plus an ERROR log, because
  it means the gate itself is broken and cannot vouch for the prompt.

Every test below asserts on the decision AND on the presence of a log record,
because a silent failure was the whole defect.

Path depth: tests/unit/hooks/ -> parents[3] == repo root.
"""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook
from prompt_integrity import PromptIntegrityResult


def _make_prompt(word_count: int) -> str:
    """Build a prompt with exactly ``word_count`` whitespace-separated words."""
    return " ".join(f"word{i}" for i in range(word_count))


# 150 words clears MIN_CRITICAL_AGENT_PROMPT_WORDS so execution reaches the
# baseline-shrinkage block (the code under test) rather than the floor check.
ADEQUATE_PROMPT = _make_prompt(150)

INTERNAL_ERRORS = [
    pytest.param(AttributeError("'PromptIntegrityResult' object has no attribute 'shrinkage_pct'"), id="AttributeError"),
    pytest.param(TypeError("unsupported format string passed to NoneType.__format__"), id="TypeError"),
    pytest.param(KeyError("shrinkage_pct"), id="KeyError"),
]


class TestGateInternalErrorsFailClosed:
    """Programming errors inside the gate must DENY, never silently allow."""

    @pytest.mark.parametrize("exc", INTERNAL_ERRORS)
    def test_validate_word_count_internal_error_denies(self, exc: Exception, caplog) -> None:
        """AttributeError/TypeError/KeyError from the validator must not fail open."""
        with caplog.at_level(logging.ERROR):
            with (
                patch("prompt_integrity.get_prompt_baseline", return_value=169),
                patch("prompt_integrity.validate_prompt_word_count", side_effect=exc),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision != "allow", (
            f"Gate failed OPEN on {type(exc).__name__} — this is the Issue #1471 defect. "
            f"reason={reason!r}"
        )
        assert type(exc).__name__ in reason, (
            f"Deny message must name the failing exception type. reason={reason!r}"
        )
        assert caplog.records, "A gate-internal failure must emit a log record, not fail silently"

    def test_cumulative_shrinkage_internal_error_denies(self, caplog) -> None:
        """An AttributeError in the cumulative-drift block must also fail closed."""
        passing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=150,
            baseline_word_count=169,
            passed=True,
            reason="OK",
            shrinkage_pct=11.2,
            should_reload=False,
        )
        with caplog.at_level(logging.ERROR):
            with (
                patch("prompt_integrity.get_prompt_baseline", return_value=169),
                patch("prompt_integrity.validate_prompt_word_count", return_value=passing_result),
                patch("prompt_integrity.record_batch_observation"),
                patch(
                    "prompt_integrity.get_cumulative_shrinkage",
                    side_effect=AttributeError("boom"),
                ),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision != "allow", (
            f"Cumulative-drift block failed OPEN on AttributeError. reason={reason!r}"
        )
        assert caplog.records, "Cumulative-drift failure must emit a log record"


class TestDocumentedFailOpenPreserved:
    """I/O problems are an intentional fail-open — disks must not block agents."""

    def test_baseline_io_error_still_allows(self, caplog) -> None:
        """get_prompt_baseline raising IOError keeps the documented fail-open."""
        with caplog.at_level(logging.WARNING):
            with (
                patch(
                    "prompt_integrity.get_prompt_baseline",
                    side_effect=IOError("baselines file unreadable"),
                ),
                patch("prompt_integrity.record_batch_observation"),
                patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision == "allow", (
            f"Baseline I/O errors must fail OPEN by design. reason={reason!r}"
        )
        assert caplog.records, "Even a fail-open path must leave a warning trace"

    def test_baseline_json_decode_error_still_allows(self, caplog) -> None:
        """A corrupt baselines JSON file is an I/O-class fault -> fail open."""
        with caplog.at_level(logging.WARNING):
            with (
                patch(
                    "prompt_integrity.get_prompt_baseline",
                    side_effect=json.JSONDecodeError("bad", "{", 0),
                ),
                patch("prompt_integrity.record_batch_observation"),
                patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision == "allow", (
            f"Corrupt baseline JSON must fail OPEN by design. reason={reason!r}"
        )
        assert caplog.records, "Even a fail-open path must leave a warning trace"


class TestIssue1471AttributeErrorCannotRecur:
    """Anti-regression: exercise the deny path with a REAL result object.

    The other tests use mocks, which would happily satisfy any attribute name.
    This one constructs an actual ``PromptIntegrityResult`` and drives the
    failing branch, so the deny-message f-string must read a field that really
    exists on the dataclass. If someone renames the field again without updating
    the hook, this test fails instead of the gate silently opening.
    """

    def test_real_result_renders_shrinkage_in_deny_message(self) -> None:
        failing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=84,
            baseline_word_count=169,
            passed=False,
            reason="Prompt for reviewer shrank 50.3% from baseline.",
            shrinkage_pct=50.3,
            should_reload=True,
        )

        # sanity: the field the hook's deny message formats must exist on the
        # real dataclass — the Issue #1471 root cause was exactly this drift.
        assert hasattr(failing_result, "shrinkage_pct"), (
            "PromptIntegrityResult must expose shrinkage_pct — the hook formats it"
        )

        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch("prompt_integrity.validate_prompt_word_count", return_value=failing_result),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": _make_prompt(84)},
            )

        assert decision == "deny", (
            f"A real failing result must produce a deny, not a swallowed error. reason={reason!r}"
        )
        # The rendered percentage proves the f-string evaluated the real field.
        assert "50.3%" in reason, f"Deny message lost the shrinkage figure: {reason!r}"
        assert "REQUIRED NEXT ACTION" in reason
        assert "get_agent_prompt_template" in reason
