"""Unit tests for cluster-safety gates in ``drain_queue_state``.

Covers (AC6-AC8):
* Severity gate fires for high/medium clusters.
* Tag gate fires against the HYDRATED ``cluster_labels`` set, NOT a non-existent
  ``cluster.labels`` field (per round-3 plan-critic finding).
* Size gate fires when cluster issue count > 5.
* Skip gate (soft skip on ``blocked``/``waiting`` labels) is distinct from STOP.
* Iteration discipline: try up to 3 clusters then STOP.

Synthetic ``TriageFinding`` instances are constructed directly from the live
dataclass at ``lib/issue_triage_analyzer.py``. We do NOT mock the dataclass —
the tests fail if the field shape drifts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_queue_state import (  # noqa: E402
    AUTO_DRAINABLE_SEVERITY,
    HUMAN_GATE_TAGS,
    MAX_CLUSTER_SIZE_AUTO_DRAINABLE,
    SKIP_LABELS,
    evaluate_cluster_gates,
    severity_gate,
    size_gate,
    skip_gate,
    tag_gate,
)
from issue_triage_analyzer import TriageFinding  # noqa: E402


# =============================================================================
# Helpers
# =============================================================================


def _make_finding(
    *,
    issue_numbers: tuple[int, ...] = (101,),
    severity: str = "low",
) -> TriageFinding:
    """Construct a TriageFinding with sensible defaults — frozen dataclass."""
    return TriageFinding(
        root_cause_tag="TEST",
        sub_cluster_id=1,
        issue_numbers=issue_numbers,
        issue_titles=tuple(f"[TEST] issue {n}" for n in issue_numbers),
        cluster_size=len(issue_numbers),
        severity=severity,
        rank_score=1.0,
        shared_files=(),
        dependency_notes=(),
        suggested_fix_order=1,
    )


# =============================================================================
# Pin: TriageFinding has NO `labels` field
# =============================================================================


class TestDataclassContract:
    """Lock the round-3 plan-critic finding: there is NO `labels` field."""

    def test_triage_finding_has_no_labels_field(self) -> None:
        """If this fails, the field finally exists and v2 hydration can drop."""
        f = _make_finding()
        with pytest.raises(AttributeError):
            _ = f.labels  # type: ignore[attr-defined]

    def test_triage_finding_fields_match_plan(self) -> None:
        """Spot-check the fields the gates depend on."""
        f = _make_finding()
        assert hasattr(f, "severity")
        assert hasattr(f, "issue_numbers")
        assert hasattr(f, "cluster_size")
        assert hasattr(f, "rank_score")


# =============================================================================
# Severity gate
# =============================================================================


class TestSeverityGate:
    def test_low_severity_passes(self) -> None:
        blocked, _ = severity_gate("low")
        assert blocked is False

    def test_info_severity_passes(self) -> None:
        blocked, _ = severity_gate("info")
        assert blocked is False

    def test_medium_severity_passes(self) -> None:
        blocked, reason = severity_gate("medium")
        assert blocked is False
        assert reason == ""

    def test_high_severity_blocks(self) -> None:
        blocked, reason = severity_gate("high")
        assert blocked is True
        assert "high" in reason

    def test_unknown_severity_blocks(self) -> None:
        blocked, reason = severity_gate("")
        assert blocked is True
        assert "unknown" in reason

    def test_severity_gate_constants_consistency(self) -> None:
        # AUTO_DRAINABLE_SEVERITY governs the gate.
        assert "low" in AUTO_DRAINABLE_SEVERITY
        assert "info" in AUTO_DRAINABLE_SEVERITY
        assert "medium" in AUTO_DRAINABLE_SEVERITY
        assert "high" not in AUTO_DRAINABLE_SEVERITY


# =============================================================================
# Severity gate — Phase D relaxation tests
# =============================================================================


class TestSeverityGatePhaseD:
    """Tests for Phase D severity_gate relaxation (this PR).

    severity_gate now blocks only 'high'. 'medium' passes through to be
    decided by confidence_gate (>=0.80 per #1291). Full retirement of
    severity_gate is deferred to a follow-up issue.
    """

    def test_medium_severity_now_passes(self) -> None:
        """medium-severity clusters pass severity_gate (Phase D)."""
        blocked, reason = severity_gate("medium")
        assert blocked is False
        assert reason == ""

    def test_high_severity_still_blocks(self) -> None:
        """high-severity clusters still require human review."""
        blocked, reason = severity_gate("high")
        assert blocked is True
        assert "human review" in reason.lower()

    def test_evaluate_cluster_gates_medium_severity_low_confidence_blocked_by_confidence(self) -> None:
        """confidence_gate is now the real autonomy decision when severity passes.

        With severity=medium AND confidence=0.5 (below 0.80 threshold), the
        cluster MUST be blocked by confidence_gate, not severity_gate.
        Verifies Phase D shift: confidence is the decider.
        """
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="medium",
            cluster_size=1,
            cluster_labels=frozenset({"auto-improvement"}),
            cluster_confidence=0.5,
        )
        assert verdict == "stop"
        assert "confidence" in reason.lower()


# =============================================================================
# Tag gate (against HYDRATED labels)
# =============================================================================


class TestTagGate:
    """Tag gate intersects the hydrated `cluster_labels` set, not a field."""

    def test_no_labels_passes(self) -> None:
        blocked, _ = tag_gate(frozenset())
        assert blocked is False

    def test_unrelated_labels_pass(self) -> None:
        blocked, _ = tag_gate(frozenset({"docs", "good-first-issue"}))
        assert blocked is False

    def test_security_label_blocks(self) -> None:
        blocked, reason = tag_gate(frozenset({"security", "bug"}))
        assert blocked is True
        assert "security" in reason

    def test_breaking_change_label_blocks(self) -> None:
        blocked, reason = tag_gate(frozenset({"breaking-change"}))
        assert blocked is True
        assert "breaking-change" in reason

    def test_major_label_blocks(self) -> None:
        """Renovate major-version gate per round-4 research."""
        blocked, reason = tag_gate(frozenset({"major"}))
        assert blocked is True
        assert "major" in reason

    def test_human_only_label_blocks(self) -> None:
        blocked, reason = tag_gate(frozenset({"human-only"}))
        assert blocked is True

    def test_simulates_hydrated_label_set_from_gh_view(self) -> None:
        """Synthetic `gh issue view --json labels` response → hydrated set."""
        # Two cluster issues, one tagged "auth" → STOP.
        per_issue_responses = [
            ["bug", "auto-improvement"],         # issue 1
            ["auth", "auto-improvement"],         # issue 2 (security gate)
        ]
        cluster_labels = frozenset(
            label for issue_labels in per_issue_responses for label in issue_labels
        )
        blocked, reason = tag_gate(cluster_labels)
        assert blocked is True
        assert "auth" in reason


# =============================================================================
# Size gate
# =============================================================================


class TestSizeGate:
    def test_size_at_max_passes(self) -> None:
        blocked, _ = size_gate(MAX_CLUSTER_SIZE_AUTO_DRAINABLE)
        assert blocked is False

    def test_size_above_max_blocks(self) -> None:
        blocked, reason = size_gate(MAX_CLUSTER_SIZE_AUTO_DRAINABLE + 1)
        assert blocked is True
        assert "compound" in reason

    def test_singleton_cluster_passes(self) -> None:
        blocked, _ = size_gate(1)
        assert blocked is False


# =============================================================================
# Skip gate
# =============================================================================


class TestSkipGate:
    def test_blocked_label_triggers_skip(self) -> None:
        skip, _ = skip_gate(frozenset({"blocked"}))
        assert skip is True

    def test_waiting_label_triggers_skip(self) -> None:
        skip, _ = skip_gate(frozenset({"waiting"}))
        assert skip is True

    def test_unrelated_labels_no_skip(self) -> None:
        skip, _ = skip_gate(frozenset({"bug"}))
        assert skip is False

    def test_empty_labels_no_skip(self) -> None:
        skip, _ = skip_gate(frozenset())
        assert skip is False


# =============================================================================
# Combined evaluation
# =============================================================================


class TestEvaluateClusterGates:
    """All gates checked in order: severity → tag → size → confidence."""

    def test_pass_clean_low_severity_small_safe(self) -> None:
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="low",
            cluster_size=2,
            cluster_labels=frozenset({"auto-improvement", "bug"}),
            cluster_confidence=1.0,
        )
        assert verdict == "pass"
        assert reason == ""

    def test_severity_short_circuits_before_tag(self) -> None:
        # High severity AND a security label — severity reason is reported.
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="high",
            cluster_size=2,
            cluster_labels=frozenset({"security"}),
            cluster_confidence=1.0,
        )
        assert verdict == "stop"
        assert "severity" in reason.lower() or "human review" in reason.lower()

    def test_tag_blocks_when_severity_passes(self) -> None:
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="low",
            cluster_size=3,
            cluster_labels=frozenset({"breaking-change"}),
            cluster_confidence=1.0,
        )
        assert verdict == "stop"
        assert "breaking-change" in reason

    def test_size_blocks_when_severity_and_tags_pass(self) -> None:
        verdict, reason = evaluate_cluster_gates(
            cluster_severity="low",
            cluster_size=MAX_CLUSTER_SIZE_AUTO_DRAINABLE + 2,
            cluster_labels=frozenset({"auto-improvement"}),
            cluster_confidence=1.0,
        )
        assert verdict == "stop"
        assert "compound" in reason


# =============================================================================
# Try-3-clusters iteration discipline
# =============================================================================


class TestSkipIterationLimit:
    """If gate skips ≥ 3 candidates in a row, the orchestrator should STOP."""

    def test_three_skips_then_stop_pattern(self) -> None:
        """Simulate three clusters each with a soft-skip label."""
        clusters = [
            (_make_finding(issue_numbers=(1,)), frozenset({"blocked"})),
            (_make_finding(issue_numbers=(2,)), frozenset({"waiting"})),
            (_make_finding(issue_numbers=(3,)), frozenset({"blocked"})),
        ]
        skipped = 0
        for _f, labels in clusters:
            skip, _ = skip_gate(labels)
            if skip:
                skipped += 1
        assert skipped == 3, (
            "All three sample clusters carry a SKIP_LABELS member — "
            "orchestrator should STOP after 3 skipped clusters"
        )

    def test_drainable_cluster_breaks_skip_run(self) -> None:
        """If the third cluster is clean, drain proceeds."""
        clusters = [
            (_make_finding(issue_numbers=(1,)), frozenset({"blocked"})),
            (_make_finding(issue_numbers=(2,)), frozenset({"waiting"})),
            (_make_finding(issue_numbers=(3,)), frozenset({"auto-improvement"})),
        ]
        drainable_index = None
        for i, (_f, labels) in enumerate(clusters):
            skip, _ = skip_gate(labels)
            if not skip:
                drainable_index = i
                break
        assert drainable_index == 2


# =============================================================================
# Constants consistency
# =============================================================================


class TestConstantsRelationships:
    def test_skip_labels_disjoint_from_human_gate_tags(self) -> None:
        """A soft skip label must not also be a human-gated STOP tag."""
        overlap = SKIP_LABELS & HUMAN_GATE_TAGS
        assert overlap == set(), f"Overlap creates ambiguous gate: {overlap}"
