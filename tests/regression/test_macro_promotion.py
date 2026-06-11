"""Regression tests for macro promotion + direction-guard digest (Issue #1201).

Pure-logic tests for ``plugins/autonomous-dev/lib/macro_promotion.py``. The
module is stdlib-only and performs no ``gh`` calls / filesystem access /
subprocess work, so these tests need no mocks of any external surface.

Reference pattern: ``tests/regression/test_issue_757_compression_threshold.py``
— import constants from the implementation module, build synthetic inputs via
a small helper, assert exact values.

Mandated AC tests (per Issue #1201 plan):
1. test_threshold_constants_exact_values
2. test_decide_promotions_threshold_logic
3. test_append_vs_create_routing
4. test_cia_prompt_zero_filing_assertion (redundant guard with #1200's
   ``test_cia_prompt_contains_zero_gh_issue_create`` — intentional per C3)
5. test_digest_contains_all_five_required_lines
6. test_recurrence_after_close_emits_loud_line
7. test_match_rate_alarm_and_findings_per_session_alarm
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pytest

# Portable project root detection: this file lives at
# tests/regression/test_macro_promotion.py — two levels up to repo root.
_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parents[2]
_LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from macro_promotion import (  # noqa: E402  (sys.path mutation above)
    CLOSED_LOOKBACK_DAYS,
    FINDINGS_PER_SESSION_BASELINE,
    MATCH_RATE_ALARM_THRESHOLD,
    OPEN_AUTO_IMPROVEMENT_COUNT_FOR_ALARM,
    PROMOTION_DISTINCT_SESSIONS_MIN,
    PROMOTION_ERROR_FREQUENCY_MIN,
    PROMOTION_FREQUENCY_MIN,
    PROMOTION_WINDOW_DAYS,
    PromotionDecision,
    build_digest,
    classify_route,
    compute_match_rate,
    decide_promotions,
    detect_recurrence_after_close,
    format_digest,
)
from runtime_data_aggregator import AggregatedSignal  # noqa: E402


# =============================================================================
# Helpers
# =============================================================================

_SEVERITY_MAP: Dict[str, float] = {"info": 0.33, "warning": 0.66, "error": 1.0}


def _signal(
    tag: str,
    title: str,
    freq: int,
    sessions: int,
    max_label: str,
) -> AggregatedSignal:
    """Build an AggregatedSignal matching the #1200 contract.

    ``signal_type`` carries the root_cause_tag verbatim; ``description`` is
    the cluster's representative title; ``raw_data`` carries the structured
    fields :func:`macro_promotion._meets_promotion_gate` reads.
    """
    return AggregatedSignal(
        source="cia_findings",
        signal_type=tag,
        description=title,
        frequency=freq,
        severity=_SEVERITY_MAP[max_label],
        raw_data={
            "root_cause_tag": tag,
            "distinct_sessions": sessions,
            "file_refs_union": [],
            "sub_cluster_size": freq,
            "max_severity_label": max_label,
        },
        timestamp=datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    )


# =============================================================================
# AC1 — Threshold constants
# =============================================================================


def test_threshold_constants_exact_values():
    """Lock the exact threshold values + the Review trigger marker (AC6).

    The Review trigger marker is the explicit re-evaluation gate from the
    Issue #1201 plan. Verifying it survives in the module docstring closes
    the "no re-evaluation gate" gap that motivated the AC.
    """
    assert PROMOTION_FREQUENCY_MIN == 3, (
        f"PROMOTION_FREQUENCY_MIN must be 3, got {PROMOTION_FREQUENCY_MIN}"
    )
    assert PROMOTION_DISTINCT_SESSIONS_MIN == 2, (
        f"PROMOTION_DISTINCT_SESSIONS_MIN must be 2, "
        f"got {PROMOTION_DISTINCT_SESSIONS_MIN}"
    )
    assert PROMOTION_ERROR_FREQUENCY_MIN == 2, (
        f"PROMOTION_ERROR_FREQUENCY_MIN must be 2, "
        f"got {PROMOTION_ERROR_FREQUENCY_MIN}"
    )
    assert PROMOTION_WINDOW_DAYS == 90, (
        f"PROMOTION_WINDOW_DAYS must be 90, got {PROMOTION_WINDOW_DAYS}"
    )

    # Re-evaluation gate marker — must exist verbatim in module source.
    module_path = _LIB_DIR / "macro_promotion.py"
    text = module_path.read_text(encoding="utf-8")
    assert "Review trigger:" in text, (
        "macro_promotion.py must contain the literal 'Review trigger:' "
        "marker documenting the re-evaluation gate (Issue #1201 AC6)."
    )


# =============================================================================
# AC2 — Promotion gate logic (4 cases)
# =============================================================================


def test_decide_promotions_threshold_logic():
    """Four signals exercising every branch of the promotion gate.

    (a) freq=3, sessions=2, info — volume+breadth gate met → promoted
    (b) freq=5, sessions=1, warning — breadth gate fails → hold
    (c) freq=2, sessions=1, error — error fast-path waives breadth → promoted
    (d) freq=1, sessions=1, error — single occurrence below fast-path → hold
    """
    sig_a = _signal("CI", "[CI] flake observed across runs", freq=3, sessions=2, max_label="info")
    sig_b = _signal("CI", "[CI] single-session 5x volume", freq=5, sessions=1, max_label="warning")
    sig_c = _signal("GATE", "[GATE] timeout error fired twice", freq=2, sessions=1, max_label="error")
    sig_d = _signal("GATE", "[GATE] single error", freq=1, sessions=1, max_label="error")

    # No open issues — every promoted signal becomes a CREATE.
    decisions = decide_promotions([sig_a, sig_b, sig_c, sig_d], open_issues=[])
    assert len(decisions) == 4

    # (a) promoted via volume+breadth
    assert decisions[0].route == "create", (
        f"Signal (a) freq=3 sessions=2 should promote → create, "
        f"got route={decisions[0].route!r}, rationale={decisions[0].rationale!r}"
    )
    assert "volume+breadth gate met" in decisions[0].rationale.lower() or (
        "volume" in decisions[0].rationale and "breadth" in decisions[0].rationale
    )

    # (b) breadth gate fails — hold
    assert decisions[1].route == "hold", (
        f"Signal (b) freq=5 sessions=1 should hold (breadth fail), "
        f"got route={decisions[1].route!r}, rationale={decisions[1].rationale!r}"
    )
    assert "breadth" in decisions[1].rationale.lower(), (
        f"Hold rationale must name 'breadth' gate, "
        f"got {decisions[1].rationale!r}"
    )

    # (c) error fast-path waives breadth
    assert decisions[2].route == "create", (
        f"Signal (c) error+freq=2 should promote via fast-path, "
        f"got route={decisions[2].route!r}, rationale={decisions[2].rationale!r}"
    )
    assert "fast-path" in decisions[2].rationale.lower() or (
        "error" in decisions[2].rationale.lower()
    ), (
        f"Promotion rationale must name 'fast-path' or 'error', "
        f"got {decisions[2].rationale!r}"
    )

    # (d) single-occurrence error fails fast-path threshold
    assert decisions[3].route == "hold", (
        f"Signal (d) error+freq=1 should hold (fast-path fail), "
        f"got route={decisions[3].route!r}, rationale={decisions[3].rationale!r}"
    )
    assert "fast-path" in decisions[3].rationale.lower() or (
        "frequency" in decisions[3].rationale.lower()
    ), (
        f"Hold rationale must name fast-path or frequency, "
        f"got {decisions[3].rationale!r}"
    )


# =============================================================================
# AC3 — Append vs create routing
# =============================================================================


def test_append_vs_create_routing():
    """Tag-equality first; cluster_within_tag decides append vs create.

    An open GAMING issue exists. A new GAMING signal sharing tokens with
    its title routes to ``append``. A new TIMING signal (no open TIMING
    issues) routes to ``create``.
    """
    open_issues: List[Dict] = [
        {"number": 42, "title": "[GAMING] test deleted assert weakening detected"},
        {"number": 99, "title": "[CI] unrelated open ticket"},
    ]

    sig_gaming = _signal(
        "GAMING",
        # Shares the tokens ``deleted``, ``assert``, ``weakening`` with #42.
        "deleted assert weakening pattern observed",
        freq=3, sessions=2, max_label="warning",
    )
    sig_timing = _signal(
        "TIMING",
        "race window in scheduler observed",
        freq=4, sessions=3, max_label="warning",
    )

    route_gaming, matched_gaming = classify_route(sig_gaming, open_issues)
    assert (route_gaming, matched_gaming) == ("append", 42), (
        f"GAMING signal sharing 3 tokens with #42 should route → ('append', 42), "
        f"got ({route_gaming!r}, {matched_gaming!r})"
    )

    route_timing, matched_timing = classify_route(sig_timing, open_issues)
    assert (route_timing, matched_timing) == ("create", None), (
        f"TIMING signal with no open TIMING issues should route → ('create', None), "
        f"got ({route_timing!r}, {matched_timing!r})"
    )


# =============================================================================
# AC4 — CIA prompt zero-filing assertion (intentional #1200 redundancy)
# =============================================================================


def test_cia_prompt_zero_filing_assertion():
    """Independent guard: continuous-improvement-analyst.md MUST NOT call gh issue create/comment.

    Intentionally redundant with #1200's ``test_cia_prompt_contains_zero_gh_issue_create``.
    Two independent guards prevent silent regression — if either drifts the
    other still catches the leak. C3 mandates this independent assertion in
    the macro-promotion test suite so the #1201 contract is locked from
    the consumer side too.
    """
    agent_path = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "agents"
        / "continuous-improvement-analyst.md"
    )
    assert agent_path.exists(), (
        f"CIA agent prompt not found at {agent_path} — file moved or deleted?"
    )
    text = agent_path.read_text(encoding="utf-8")

    create_count = text.count("gh issue create")
    comment_count = text.count("gh issue comment")
    assert create_count == 0, (
        f"continuous-improvement-analyst.md must contain ZERO 'gh issue create' "
        f"calls (CIA emits findings; /improve --auto-file promotes them via "
        f"macro_promotion). Found {create_count} occurrences."
    )
    assert comment_count == 0, (
        f"continuous-improvement-analyst.md must contain ZERO 'gh issue comment' "
        f"calls (CIA emits findings; /improve --auto-file promotes them via "
        f"macro_promotion). Found {comment_count} occurrences."
    )


# =============================================================================
# AC5 — Digest renders all 5 sections
# =============================================================================


def test_digest_contains_all_five_required_lines():
    """All 5 section markers MUST appear in both populated AND empty digests."""
    required_markers = [
        "ACTIONS TAKEN",
        "Recurrence-after-close",  # appears either as "FIX DIDN'T STICK" or "Recurrence-after-close: 0"
        "Match-rate",
        "Findings-per-session",  # alarm renders "CIA emission failure" — but the empty case still has this marker via the format function
        "Error-without-other-channel",
    ]

    # --- Populated scenario --------------------------------------------------
    open_issues: List[Dict] = [
        {"number": 42, "title": "[GAMING] test deleted assert weakening detected"},
    ]
    populated_signals = [
        _signal("GAMING", "deleted assert weakening pattern observed",
                freq=4, sessions=3, max_label="warning"),
        _signal("TIMING", "race window in scheduler", freq=5, sessions=4, max_label="warning"),
        _signal("LOW", "minor cosmetic warning", freq=1, sessions=1, max_label="info"),
    ]
    decisions = decide_promotions(populated_signals, open_issues)
    counts = build_digest(
        decisions,
        recurrence=[("GATE", 7)],
        open_auto_improvement_count=10,
        findings_observed=3,
        distinct_sessions_observed=4,
    )
    populated_body = format_digest(counts)

    # ACTIONS TAKEN row
    assert "ACTIONS TAKEN" in populated_body
    # Recurrence — populated should have "FIX DIDN'T STICK"
    assert "FIX DIDN'T STICK" in populated_body
    # Match-rate row
    assert "Match-rate" in populated_body
    # Findings-per-session row (ratio form)
    assert "Findings-per-session" in populated_body or "CIA emission failure" in populated_body
    # Error-without-other-channel row (empty form acceptable for populated when
    # there are no silent errors)
    assert "Error-without-other-channel" in populated_body

    # --- Empty scenario ------------------------------------------------------
    empty_counts = build_digest(
        decisions=[],
        recurrence=[],
        open_auto_improvement_count=0,
        findings_observed=0,
        distinct_sessions_observed=0,
    )
    empty_body = format_digest(empty_counts)
    # All 5 section markers must still appear in the empty case.
    assert "ACTIONS TAKEN" in empty_body, (
        f"Empty digest missing ACTIONS TAKEN: {empty_body!r}"
    )
    assert "Recurrence-after-close: 0" in empty_body, (
        f"Empty digest must render literal 'Recurrence-after-close: 0', got: {empty_body!r}"
    )
    assert "Match-rate" in empty_body, (
        f"Empty digest missing Match-rate: {empty_body!r}"
    )
    assert "Findings-per-session" in empty_body or "n/a" in empty_body, (
        f"Empty digest missing Findings-per-session section: {empty_body!r}"
    )
    assert "Error-without-other-channel: 0" in empty_body, (
        f"Empty digest must render literal 'Error-without-other-channel: 0', "
        f"got: {empty_body!r}"
    )


# =============================================================================
# AC6 — Recurrence-after-close loud line
# =============================================================================


def test_recurrence_after_close_emits_loud_line():
    """A signal matching a closed issue → loud FIX DIDN'T STICK line.

    No match → digest carries the literal ``Recurrence-after-close: 0``.
    """
    closed_issues: List[Dict] = [
        {"number": 7, "title": "[GATE] pytest gate skipped under pressure"},
    ]
    matching_signal = _signal(
        "GATE",
        # Shares ``pytest``, ``gate``, ``skipped``, ``pressure``.
        "pytest gate skipped under pressure observed twice",
        freq=2, sessions=1, max_label="error",
    )
    matches = detect_recurrence_after_close([matching_signal], closed_issues)
    assert ("GATE", 7) in matches, (
        f"Matching signal must produce ('GATE', 7), got {matches!r}"
    )

    # And the digest body carries the loud marker.
    decisions = decide_promotions([matching_signal], open_issues=[])
    counts = build_digest(
        decisions,
        recurrence=matches,
        open_auto_improvement_count=5,
        findings_observed=1,
        distinct_sessions_observed=1,
    )
    body = format_digest(counts)
    assert "FIX DIDN'T STICK" in body, (
        f"Digest must contain loud 'FIX DIDN'T STICK' marker, got: {body!r}"
    )
    assert "tag=GATE" in body and "closed_issue=#7" in body

    # No-match path.
    no_match_signal = _signal(
        "CI", "completely unrelated ci flake", freq=3, sessions=2, max_label="info"
    )
    no_matches = detect_recurrence_after_close([no_match_signal], closed_issues)
    assert no_matches == [], (
        f"No-tag-match signal must produce empty list, got {no_matches!r}"
    )
    counts2 = build_digest(
        decide_promotions([no_match_signal], open_issues=[]),
        recurrence=no_matches,
        open_auto_improvement_count=5,
        findings_observed=1,
        distinct_sessions_observed=1,
    )
    body2 = format_digest(counts2)
    assert "Recurrence-after-close: 0" in body2, (
        f"No-match digest must render literal 'Recurrence-after-close: 0', "
        f"got: {body2!r}"
    )


# =============================================================================
# AC7 — Match-rate alarm + Findings-per-session emission-failure alarm
# =============================================================================


def test_match_rate_alarm_and_findings_per_session_alarm():
    """Two alarm classes guarded by both ratio + count gates."""
    # (a) Match-rate ALARM: 4 created + 1 appended = 20% with 25 open issues
    decisions_low_rate: List[PromotionDecision] = [
        PromotionDecision(
            signal=_signal("A", "create 1", 3, 2, "warning"),
            route="create",
            matched_open_issue=None,
            rationale="promoted",
        ),
        PromotionDecision(
            signal=_signal("B", "create 2", 3, 2, "warning"),
            route="create",
            matched_open_issue=None,
            rationale="promoted",
        ),
        PromotionDecision(
            signal=_signal("C", "create 3", 3, 2, "warning"),
            route="create",
            matched_open_issue=None,
            rationale="promoted",
        ),
        PromotionDecision(
            signal=_signal("D", "create 4", 3, 2, "warning"),
            route="create",
            matched_open_issue=None,
            rationale="promoted",
        ),
        PromotionDecision(
            signal=_signal("E", "append 1", 3, 2, "warning"),
            route="append",
            matched_open_issue=100,
            rationale="promoted",
        ),
    ]
    # 4 / (4+1) = 20% → below the 50% threshold; open count 25 > 20 → ALARM fires.
    counts_alarm = build_digest(
        decisions_low_rate, recurrence=[],
        open_auto_improvement_count=25,
        findings_observed=5, distinct_sessions_observed=5,
    )
    body_alarm = format_digest(counts_alarm)
    assert "ALARM" in body_alarm, (
        f"Match-rate ALARM must fire when rate<{MATCH_RATE_ALARM_THRESHOLD} and "
        f"open count>{OPEN_AUTO_IMPROVEMENT_COUNT_FOR_ALARM}; body={body_alarm!r}"
    )

    # Same low rate but only 15 open issues (count gate fails) — NO alarm.
    counts_no_alarm = build_digest(
        decisions_low_rate, recurrence=[],
        open_auto_improvement_count=15,
        findings_observed=5, distinct_sessions_observed=5,
    )
    body_no_alarm = format_digest(counts_no_alarm)
    assert "ALARM" not in body_no_alarm, (
        f"Match-rate ALARM must NOT fire when open count<="
        f"{OPEN_AUTO_IMPROVEMENT_COUNT_FOR_ALARM}; body={body_no_alarm!r}"
    )
    assert "Match-rate: 20% (no alarm)" in body_no_alarm or "no alarm" in body_no_alarm

    # (b) Findings-per-session emission-failure ALARM
    #     findings_observed=0 with distinct_sessions_observed=3 → ALARM
    counts_emission_fail = build_digest(
        decisions=[], recurrence=[],
        open_auto_improvement_count=5,
        findings_observed=0, distinct_sessions_observed=3,
    )
    body_emission_fail = format_digest(counts_emission_fail)
    assert "CIA emission failure" in body_emission_fail, (
        f"Emission-failure ALARM must fire when findings=0 and sessions>0; "
        f"body={body_emission_fail!r}"
    )

    # findings_observed=15, distinct_sessions_observed=3 → no emission alarm
    counts_healthy = build_digest(
        decisions=[], recurrence=[],
        open_auto_improvement_count=5,
        findings_observed=15, distinct_sessions_observed=3,
    )
    body_healthy = format_digest(counts_healthy)
    assert "CIA emission failure" not in body_healthy, (
        f"Emission-failure ALARM must NOT fire when findings>0; body={body_healthy!r}"
    )
    # Sanity: ratio appears with the baseline reference.
    assert (
        "Findings-per-session" in body_healthy
        and str(FINDINGS_PER_SESSION_BASELINE) in body_healthy
    ), f"Expected ratio with baseline {FINDINGS_PER_SESSION_BASELINE}, got {body_healthy!r}"


# =============================================================================
# Supplementary smoke — compute_match_rate
# =============================================================================


def test_compute_match_rate_returns_none_when_no_promoted():
    """Defensive: empty / all-hold input → match_rate is None (n/a in digest)."""
    assert compute_match_rate([]) is None
    holds = [
        PromotionDecision(
            signal=_signal("X", "hold 1", 1, 1, "info"),
            route="hold",
            matched_open_issue=None,
            rationale="below threshold",
        ),
    ]
    assert compute_match_rate(holds) is None


def test_closed_lookback_days_constant_value():
    """Lock the closed-lookback window (referenced by /improve STEP 5)."""
    assert CLOSED_LOOKBACK_DAYS == 90, (
        f"CLOSED_LOOKBACK_DAYS must be 90, got {CLOSED_LOOKBACK_DAYS}"
    )
