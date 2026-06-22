"""Unit tests for ADR-002 Phase C confidence-based drain eligibility gate.

GitHub Issue: #1291.

Covers:
* ``AUTO_DRAINABLE_CONFIDENCE_THRESHOLD`` constant pin.
* ``confidence_gate()`` pass/block at boundary, above, below, and on
  malformed inputs.
* ``evaluate_cluster_gates()`` ordering when confidence is the failing gate.
* ``_infer_confidence()`` label-driven and body-heuristic-driven paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_queue_state import (  # noqa: E402
    AUTO_DRAINABLE_CONFIDENCE_THRESHOLD,
    confidence_gate,
    evaluate_cluster_gates,
)
from issue_triage_analyzer import _infer_confidence  # noqa: E402


# =============================================================================
# Threshold constant
# =============================================================================


class TestThresholdConstant:
    def test_threshold_is_eight_tenths(self) -> None:
        assert AUTO_DRAINABLE_CONFIDENCE_THRESHOLD == 0.80

    def test_threshold_is_float(self) -> None:
        assert isinstance(AUTO_DRAINABLE_CONFIDENCE_THRESHOLD, float)


# =============================================================================
# confidence_gate — pure function
# =============================================================================


class TestConfidenceGate:
    def test_full_confidence_passes(self) -> None:
        blocked, reason = confidence_gate(1.0)
        assert blocked is False
        assert reason == ""

    def test_exact_threshold_passes(self) -> None:
        # Boundary: confidence == threshold MUST NOT block.
        blocked, reason = confidence_gate(AUTO_DRAINABLE_CONFIDENCE_THRESHOLD)
        assert blocked is False
        assert reason == ""

    def test_just_above_threshold_passes(self) -> None:
        blocked, _ = confidence_gate(0.81)
        assert blocked is False

    def test_just_below_threshold_blocks(self) -> None:
        blocked, reason = confidence_gate(0.79)
        assert blocked is True
        assert "confidence" in reason.lower()

    def test_half_confidence_blocks(self) -> None:
        blocked, reason = confidence_gate(0.5)
        assert blocked is True
        assert "0.50" in reason
        assert "0.80" in reason

    def test_zero_confidence_blocks(self) -> None:
        blocked, reason = confidence_gate(0.0)
        assert blocked is True
        assert "0.00" in reason

    def test_negative_confidence_blocks(self) -> None:
        blocked, reason = confidence_gate(-0.5)
        assert blocked is True

    def test_none_confidence_blocks_via_coercion(self) -> None:
        blocked, _ = confidence_gate(None)  # type: ignore[arg-type]
        assert blocked is True

    def test_string_confidence_blocks_via_coercion(self) -> None:
        blocked, _ = confidence_gate("not-a-number")  # type: ignore[arg-type]
        assert blocked is True

    def test_int_confidence_coerced(self) -> None:
        blocked, _ = confidence_gate(1)
        assert blocked is False


# =============================================================================
# evaluate_cluster_gates — confidence in ordering
# =============================================================================


class TestEvaluateGatesWithConfidence:
    def test_default_confidence_blocks_low_severity_clean_small(self) -> None:
        """The default cluster_confidence=0.0 must block even a safe cluster."""
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="low",
            cluster_size=2,
            cluster_labels=frozenset({"auto-improvement"}),
        )
        assert verdict == "stop"
        assert "confidence" in reason.lower()

    def test_confidence_threshold_passes_clean_cluster(self) -> None:
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="low",
            cluster_size=2,
            cluster_labels=frozenset({"auto-improvement"}),
            cluster_confidence=AUTO_DRAINABLE_CONFIDENCE_THRESHOLD,
        )
        assert verdict == "pass"
        assert reason == ""

    def test_severity_short_circuits_before_confidence(self) -> None:
        """High severity blocks before confidence is evaluated."""
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="high",
            cluster_size=2,
            cluster_labels=frozenset(),
            cluster_confidence=0.0,
        )
        assert verdict == "stop"
        assert "confidence" not in reason.lower()  # severity took precedence

    def test_size_short_circuits_before_confidence(self) -> None:
        """Compound cluster blocks before confidence is evaluated."""
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="low",
            cluster_size=99,
            cluster_labels=frozenset(),
            cluster_confidence=1.0,
        )
        assert verdict == "stop"
        assert "compound" in reason
        assert "confidence" not in reason.lower()

    def test_low_confidence_is_only_failure(self) -> None:
        """When severity / tag / size all pass, confidence is the gate."""
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="low",
            cluster_size=1,
            cluster_labels=frozenset({"auto-improvement"}),
            cluster_confidence=0.5,
        )
        assert verdict == "stop"
        assert "confidence" in reason.lower()


# =============================================================================
# _infer_confidence — labels + body heuristic
# =============================================================================


class TestInferConfidenceLabels:
    def test_confidence_high_label_returns_one(self) -> None:
        result = _infer_confidence(
            labels=[{"name": "confidence:high"}], body=""
        )
        assert result == 1.0

    def test_confidence_medium_label_returns_zero(self) -> None:
        result = _infer_confidence(
            labels=[{"name": "confidence:medium"}], body=""
        )
        assert result == 0.0

    def test_confidence_low_label_returns_zero(self) -> None:
        result = _infer_confidence(
            labels=[{"name": "confidence:low"}], body=""
        )
        assert result == 0.0

    def test_high_label_wins_over_body_heuristic(self) -> None:
        """Operator-tagged HIGH should be authoritative."""
        body = (
            "## Acceptance Criteria\n- a\n## Proposed fix\nDo X."
        )
        result = _infer_confidence(
            labels=[{"name": "confidence:high"}], body=body
        )
        assert result == 1.0

    def test_bare_string_labels_accepted(self) -> None:
        result = _infer_confidence(labels=["confidence:high"], body="")
        assert result == 1.0

    def test_label_case_insensitive(self) -> None:
        result = _infer_confidence(
            labels=[{"name": "Confidence:High"}], body=""
        )
        assert result == 1.0


class TestInferConfidenceBodyHeuristic:
    def test_body_with_both_sections_returns_point_eight(self) -> None:
        body = (
            "## Acceptance Criteria\n"
            "- [ ] thing works\n"
            "## Proposed fix\n"
            "Patch X."
        )
        result = _infer_confidence(labels=[], body=body)
        assert result == 0.8

    def test_implementation_approach_alias_counts(self) -> None:
        body = (
            "## Acceptance Criteria\nfoo\n## Implementation Approach\nbar"
        )
        result = _infer_confidence(labels=[], body=body)
        assert result == 0.8

    def test_body_with_only_acceptance_returns_zero(self) -> None:
        body = "## Acceptance Criteria\n- a"
        result = _infer_confidence(labels=[], body=body)
        assert result == 0.0

    def test_body_with_only_proposed_returns_zero(self) -> None:
        body = "## Proposed fix\nDo X."
        result = _infer_confidence(labels=[], body=body)
        assert result == 0.0

    def test_empty_body_returns_zero(self) -> None:
        result = _infer_confidence(labels=[], body="")
        assert result == 0.0

    def test_no_labels_no_body_returns_zero(self) -> None:
        result = _infer_confidence(labels=[], body="")
        assert result == 0.0

    def test_none_labels_safe(self) -> None:
        result = _infer_confidence(labels=None, body="")  # type: ignore[arg-type]
        assert result == 0.0

    def test_body_heuristic_case_insensitive(self) -> None:
        body = "ACCEPTANCE CRITERIA\nfoo\nPROPOSED FIX\nbar"
        result = _infer_confidence(labels=[], body=body)
        assert result == 0.8


# =============================================================================
# Integration: heuristic feeds gate
# =============================================================================


class TestConfidenceIntegration:
    def test_well_structured_issue_passes_gate(self) -> None:
        """An issue with AC + Proposed fix (0.8) meets the 0.80 threshold."""
        body = (
            "## Acceptance Criteria\n- works\n## Proposed fix\nPatch."
        )
        conf = _infer_confidence(labels=[], body=body)
        blocked, _ = confidence_gate(conf)
        assert blocked is False

    def test_unstructured_issue_blocked_by_gate(self) -> None:
        """An issue with only a one-line description is blocked."""
        conf = _infer_confidence(labels=[], body="Fix the thing")
        blocked, _ = confidence_gate(conf)
        assert blocked is True
