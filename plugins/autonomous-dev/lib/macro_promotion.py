"""Macro Promotion + Direction-Guard Digest for /improve --auto-file (Issue #1201).

Pure-logic library that decides which cross-session CIA findings have crossed
the volume + breadth threshold to be promoted to GitHub issues, classifies
each promoted finding as ``append`` (to an existing matching open issue) or
``create`` (new issue), detects recurrence-after-close ("fix didn't stick")
signals across closed issues, and renders an anti-habituation 5-section
digest summarizing every cycle.

The module is stdlib-only, performs no ``gh`` calls, no filesystem access,
no subprocess work. All side effects (issue creation, comments, JSONL
persistence) live in ``/improve``'s STEP 5 — this library produces the
:class:`PromotionDecision` plan that STEP 5 executes.

Builds on Issue #1200's :func:`runtime_data_aggregator.collect_cia_findings`
contract:

* ``AggregatedSignal.signal_type`` carries the ``root_cause_tag`` verbatim
* ``AggregatedSignal.description`` is the sanitized representative title
* ``AggregatedSignal.raw_data`` contains ``root_cause_tag``,
  ``distinct_sessions``, ``file_refs_union``, ``sub_cluster_size``, and
  ``max_severity_label`` ({"info", "warning", "error"})

C3 promotion contract (this module):
1. A signal is promoted iff it crosses one of two gates:
   * **Volume + breadth**: ``frequency >= PROMOTION_FREQUENCY_MIN`` AND
     ``distinct_sessions >= PROMOTION_DISTINCT_SESSIONS_MIN``
   * **Error fast-path**: ``max_severity_label == "error"`` (string equality
     on the label, NOT severity float comparison — see below) AND
     ``frequency >= PROMOTION_ERROR_FREQUENCY_MIN``
2. Promoted signals are then classified into ``append`` (a matching open
   issue exists) or ``create`` (new). Tag-equality filtering is done FIRST
   to defend against over-clustering across unrelated tags.
3. Non-promoted signals carry route ``"hold"`` with a rationale naming the
   failing gate; STEP 5 surfaces holds in the digest, never as issues.

Severity-label semantics (intentional): the error fast-path uses STRING
LABEL equality ("error"), not the severity float. The float is a derived
display value via ``CIA_FINDING_SEVERITY_MAP`` and is unsafe for promotion
decisions because future changes to the float scale would silently change
behaviour. The label is the source of truth.

GitHub Issue: #1201 (builds on #1200)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# Tunable Thresholds (Issue #1201)
# =============================================================================
#
# What it controls:
#   The macro-promotion gate that decides which CIA findings get filed as
#   GitHub issues, the recurrence-after-close detector, the digest match-rate
#   alarm, and the emission-failure alarm.
#
# Why these initial values:
#   Sentry-style volume AND breadth combined gate — a single noisy session
#   should never promote alone; cross-session recurrence (>= 2 sessions) is
#   the strong signal that a real systemic issue exists.
#   Google SRE dual-window precedent: a 90-day window is long enough that
#   a real recurring bug surfaces with high signal-to-noise; an error fast-
#   path with freq >= 2 catches loud bugs without waiting for breadth
#   accumulation.
#   The match-rate alarm requires both a low ratio AND a non-trivial open-
#   issue COUNT (> 20), so young repos with 3 open issues don't trigger a
#   false alarm.
#
# Data needed to re-evaluate (from at least 2 digests):
#   * Promotion rate per digest (created + appended) / total signals seen
#   * False-positive promotion percentage (issues closed as "not actionable"
#     within 7 days)
#   * Missed-promotion count (signals that should have promoted but didn't,
#     surfaced via /retrospective)
#
# Review trigger: after the user has reviewed the first 2 digests (Issue
# #1201 explicit re-evaluation gate)
# =============================================================================

PROMOTION_FREQUENCY_MIN: int = 3
PROMOTION_DISTINCT_SESSIONS_MIN: int = 2
PROMOTION_ERROR_FREQUENCY_MIN: int = 2
PROMOTION_WINDOW_DAYS: int = 90
MATCH_RATE_ALARM_THRESHOLD: float = 0.50
# A COUNT of open issues, not a percent. Below this count we suppress the
# match-rate alarm to avoid false alarms in young repos.
OPEN_AUTO_IMPROVEMENT_COUNT_FOR_ALARM: int = 20
FINDINGS_PER_SESSION_BASELINE: int = 5
CLOSED_LOOKBACK_DAYS: int = 90

# Robust two-step import (relative-then-flat fallback) — matches the idiom
# used by runtime_data_aggregator and issue_triage_analyzer.
try:
    from .runtime_data_aggregator import AggregatedSignal  # type: ignore
    from .issue_triage_analyzer import (  # type: ignore
        cluster_within_tag,
        extract_root_cause_tag,
    )
except ImportError:
    _lib_dir = Path(__file__).parent.resolve()
    if str(_lib_dir) not in sys.path:
        sys.path.insert(0, str(_lib_dir))
    from runtime_data_aggregator import AggregatedSignal  # type: ignore
    from issue_triage_analyzer import (  # type: ignore
        cluster_within_tag,
        extract_root_cause_tag,
    )


# =============================================================================
# Public Data Classes
# =============================================================================


@dataclass(frozen=True)
class PromotionDecision:
    """A single promotion decision for one :class:`AggregatedSignal`.

    Attributes:
        signal: The input signal.
        route: One of ``"create"``, ``"append"``, ``"hold"``.
        matched_open_issue: When ``route == "append"``, the issue number of
            the matched open issue. ``None`` for ``create`` / ``hold``.
        rationale: Human-readable explanation. For ``hold`` decisions this
            names the gate that failed (e.g. "frequency too low",
            "breadth gate failed", "single occurrence below error fast-path").
    """

    signal: AggregatedSignal
    route: str
    matched_open_issue: Optional[int]
    rationale: str


@dataclass(frozen=True)
class DigestCounts:
    """Counter aggregates rendered into the digest body.

    Attributes:
        promoted: Number of signals that crossed the promotion gate.
        appended: Number of promoted signals routed to ``append``.
        held: Number of signals that did NOT cross the gate.
        expired: Number of signals dropped because they fell outside
            ``PROMOTION_WINDOW_DAYS`` (informational only — the CIA
            collector already does the window filter).
        recurrence_after_close: Tuple of ``(tag, closed_issue_number)``
            pairs indicating fixes that didn't stick.
        match_rate: ``appended / (appended + created)``; ``None`` when the
            denominator is zero (rendered as ``"n/a"``).
        open_auto_improvement_count: Count of open ``auto-improvement``
            issues at digest time. Gates the match-rate alarm.
        findings_per_session: Observed findings divided by observed
            sessions; ``None`` when no sessions were observed.
        error_without_other_channel: Sorted tuple of representative titles
            for error-severity findings that did NOT promote AND matched
            no open issue (silent dropped errors — anti-habituation signal).
        create_failures: Number of ``gh issue create`` failures surfaced
            by STEP 5 (references #1203). Defaults to 0.
    """

    promoted: int
    appended: int
    held: int
    expired: int
    recurrence_after_close: Tuple[Tuple[str, int], ...]
    match_rate: Optional[float]
    open_auto_improvement_count: int
    findings_per_session: Optional[float]
    error_without_other_channel: Tuple[str, ...]
    create_failures: int = 0


# =============================================================================
# Helpers
# =============================================================================


def _raw_data_get(signal: AggregatedSignal, key: str, default: Any = None) -> Any:
    """Defensive accessor for ``signal.raw_data`` (which is a dict)."""
    if not isinstance(signal.raw_data, dict):
        return default
    return signal.raw_data.get(key, default)


def _meets_promotion_gate(
    signal: AggregatedSignal,
    *,
    frequency_min: int,
    distinct_sessions_min: int,
    error_frequency_min: int,
) -> Tuple[bool, str]:
    """Apply the promotion gate to a single signal.

    Returns:
        ``(promoted, rationale)``. When ``promoted`` is ``True`` the
        rationale names the gate that fired. When ``False`` it names the
        gate that failed.
    """
    frequency = int(signal.frequency or 0)
    distinct_sessions = int(_raw_data_get(signal, "distinct_sessions", 0) or 0)
    max_label = str(_raw_data_get(signal, "max_severity_label", "info"))

    volume_breadth_pass = (
        frequency >= frequency_min and distinct_sessions >= distinct_sessions_min
    )
    if volume_breadth_pass:
        return True, (
            f"volume+breadth gate met (frequency={frequency} >= "
            f"{frequency_min}, distinct_sessions={distinct_sessions} >= "
            f"{distinct_sessions_min})"
        )

    # Error fast-path waives breadth: string-label equality is the spec.
    # Never compare against the severity float — see module docstring.
    if max_label == "error" and frequency >= error_frequency_min:
        return True, (
            f"error fast-path met (max_severity_label='error', "
            f"frequency={frequency} >= {error_frequency_min})"
        )

    # Hold: name the failing gate.
    if frequency < frequency_min and not (max_label == "error"):
        return False, (
            f"frequency too low (frequency={frequency} < {frequency_min}, "
            f"max_severity_label={max_label!r})"
        )
    if distinct_sessions < distinct_sessions_min and max_label != "error":
        return False, (
            f"breadth gate failed (distinct_sessions={distinct_sessions} < "
            f"{distinct_sessions_min}, frequency={frequency})"
        )
    if max_label == "error" and frequency < error_frequency_min:
        return False, (
            f"single occurrence below error fast-path (frequency={frequency} "
            f"< {error_frequency_min}, max_severity_label='error')"
        )
    # Defensive fallback.
    return False, (
        f"promotion gate failed (frequency={frequency}, "
        f"distinct_sessions={distinct_sessions}, max_severity_label={max_label!r})"
    )


# =============================================================================
# Routing
# =============================================================================


def classify_route(
    signal: AggregatedSignal,
    open_issues: List[Dict[str, Any]],
) -> Tuple[str, Optional[int]]:
    """Classify a promoted signal as ``append`` or ``create``.

    Algorithm:
    1. Filter ``open_issues`` to those whose ``extract_root_cause_tag(title)``
       equals ``signal.signal_type`` (tag-equality FIRST — over-dedup
       defense: an off-tag cluster sharing many tokens with an unrelated
       open issue should not falsely append).
    2. Insert the synthetic ``{"number": -1, "title": signal.description}``
       into the filtered list and call
       :func:`issue_triage_analyzer.cluster_within_tag`.
    3. If the synthetic ``-1`` lands in a cluster containing at least one
       real (non-negative) issue number, return ``("append", lowest_real_num)``.
    4. Otherwise return ``("create", None)``.

    Args:
        signal: A signal that has already passed the promotion gate.
        open_issues: List of open auto-improvement issue dicts, each with
            ``number`` and ``title`` keys.

    Returns:
        ``(route, matched_open_issue)`` where ``route`` is ``"create"`` or
        ``"append"``.
    """
    tag = signal.signal_type
    same_tag_issues = [
        issue for issue in open_issues
        if isinstance(issue, dict)
        and "number" in issue
        and extract_root_cause_tag(str(issue.get("title", ""))) == tag
    ]

    if not same_tag_issues:
        return "create", None

    # Build the union cluster input. The synthetic title intentionally drops
    # any leading bracket prefix — the description is the cluster's shortest
    # representative title (per the #1200 contract); cluster_within_tag will
    # tokenize it anyway via extract_title_tokens.
    synthetic = {"number": -1, "title": signal.description}
    union = same_tag_issues + [synthetic]
    clusters = cluster_within_tag(union)
    for cluster in clusters:
        if -1 in cluster:
            real_numbers = [n for n in cluster if n >= 0]
            if real_numbers:
                return "append", min(real_numbers)
            return "create", None

    # Defensive: synthetic should always end up in some cluster (its own
    # singleton at minimum). If not, fall through to create.
    return "create", None


# =============================================================================
# Promotion
# =============================================================================


def decide_promotions(
    signals: List[AggregatedSignal],
    open_issues: List[Dict[str, Any]],
    *,
    frequency_min: int = PROMOTION_FREQUENCY_MIN,
    distinct_sessions_min: int = PROMOTION_DISTINCT_SESSIONS_MIN,
    error_frequency_min: int = PROMOTION_ERROR_FREQUENCY_MIN,
) -> List[PromotionDecision]:
    """Decide create/append/hold for every signal.

    Args:
        signals: All CIA-finding signals from
            :func:`runtime_data_aggregator.collect_cia_findings`.
        open_issues: Open auto-improvement issue dicts from
            :func:`runtime_data_aggregator.fetch_issues_with_label`.
        frequency_min: Override for ``PROMOTION_FREQUENCY_MIN``.
        distinct_sessions_min: Override for ``PROMOTION_DISTINCT_SESSIONS_MIN``.
        error_frequency_min: Override for ``PROMOTION_ERROR_FREQUENCY_MIN``.

    Returns:
        One :class:`PromotionDecision` per input signal, in the same order.
    """
    decisions: List[PromotionDecision] = []
    for signal in signals:
        promoted, rationale = _meets_promotion_gate(
            signal,
            frequency_min=frequency_min,
            distinct_sessions_min=distinct_sessions_min,
            error_frequency_min=error_frequency_min,
        )
        if not promoted:
            decisions.append(
                PromotionDecision(
                    signal=signal,
                    route="hold",
                    matched_open_issue=None,
                    rationale=rationale,
                )
            )
            continue

        route, matched = classify_route(signal, open_issues)
        decisions.append(
            PromotionDecision(
                signal=signal,
                route=route,
                matched_open_issue=matched,
                rationale=rationale,
            )
        )

    return decisions


# =============================================================================
# Recurrence-After-Close Detection
# =============================================================================


def detect_recurrence_after_close(
    signals: List[AggregatedSignal],
    closed_issues: List[Dict[str, Any]],
) -> List[Tuple[str, int]]:
    """Find signals whose tag + title match a recently-closed issue.

    Runs over ALL signals (not just promoted) — the recurrence direction-
    guard signal is "measurable in every digest" by design. A recurrence
    indicates the fix for ``closed_issue_number`` didn't actually fix the
    underlying root cause; we want to surface it loudly even if the
    individual signal wouldn't promote on its own.

    Algorithm: tag-equality first (same defense as :func:`classify_route`),
    then :func:`issue_triage_analyzer.cluster_within_tag`. A signal that
    clusters with one or more closed issues emits one ``(tag, closed_number)``
    pair per match — sorted and deduplicated.

    Args:
        signals: All CIA-finding signals.
        closed_issues: Closed auto-improvement issues from
            :func:`runtime_data_aggregator.fetch_issues_with_label(state="closed")`.

    Returns:
        Sorted, deduplicated list of ``(root_cause_tag, closed_issue_number)``
        pairs.
    """
    if not closed_issues:
        return []

    # Pre-index closed issues by tag for cheap lookups.
    by_tag: Dict[str, List[Dict[str, Any]]] = {}
    for issue in closed_issues:
        if not isinstance(issue, dict) or "number" not in issue:
            continue
        tag = extract_root_cause_tag(str(issue.get("title", "")))
        by_tag.setdefault(tag, []).append(issue)

    pairs: set = set()
    for signal in signals:
        tag = signal.signal_type
        same_tag_closed = by_tag.get(tag, [])
        if not same_tag_closed:
            continue
        synthetic = {"number": -1, "title": signal.description}
        union = same_tag_closed + [synthetic]
        clusters = cluster_within_tag(union)
        for cluster in clusters:
            if -1 not in cluster:
                continue
            for n in cluster:
                if n >= 0:
                    pairs.add((tag, int(n)))

    return sorted(pairs)


# =============================================================================
# Match-Rate
# =============================================================================


def compute_match_rate(decisions: List[PromotionDecision]) -> Optional[float]:
    """Compute the append-vs-create match rate.

    Returns:
        ``appended / (appended + created)`` as a float in ``[0, 1]``, or
        ``None`` when no promoted decisions exist (denominator zero — avoids
        div-by-zero; rendered as ``"n/a"`` by :func:`format_digest`).
    """
    appended = sum(1 for d in decisions if d.route == "append")
    created = sum(1 for d in decisions if d.route == "create")
    total = appended + created
    if total == 0:
        return None
    return appended / total


# =============================================================================
# Digest Construction + Rendering
# =============================================================================


def build_digest(
    decisions: List[PromotionDecision],
    recurrence: List[Tuple[str, int]],
    *,
    open_auto_improvement_count: int,
    findings_observed: int,
    distinct_sessions_observed: int,
    expired_count: int = 0,
    create_failures: int = 0,
) -> DigestCounts:
    """Aggregate counter values for the digest.

    Args:
        decisions: Output of :func:`decide_promotions`.
        recurrence: Output of :func:`detect_recurrence_after_close`.
        open_auto_improvement_count: Count of open issues labeled
            ``auto-improvement`` at the time of the digest.
        findings_observed: Total findings observed in the window (>= 0).
            ``0`` triggers the CIA emission-failure alarm.
        distinct_sessions_observed: Total distinct sessions observed in the
            window (>= 0). Used as the denominator for findings-per-session.
        expired_count: Findings dropped because they fell outside the window.
        create_failures: ``gh issue create`` failures from STEP 5 (#1203).

    Returns:
        A frozen :class:`DigestCounts` ready for :func:`format_digest`.
    """
    promoted = sum(1 for d in decisions if d.route in ("create", "append"))
    appended = sum(1 for d in decisions if d.route == "append")
    held = sum(1 for d in decisions if d.route == "hold")

    if distinct_sessions_observed > 0:
        findings_per_session: Optional[float] = (
            float(findings_observed) / float(distinct_sessions_observed)
        )
    else:
        findings_per_session = None

    # Error findings that were NOT promoted AND matched no open issue.
    # These are silent dropped errors; surface them in the digest so they
    # do not get habituated away. Defensive: deduplicate by description.
    silent_errors: List[str] = []
    seen_descriptions: set = set()
    for d in decisions:
        max_label = str(_raw_data_get(d.signal, "max_severity_label", "info"))
        if max_label != "error":
            continue
        if d.route in ("create", "append"):
            continue
        # route == "hold" AND label == "error" — this is a silent error.
        desc = str(d.signal.description)
        if desc in seen_descriptions:
            continue
        seen_descriptions.add(desc)
        silent_errors.append(desc)

    return DigestCounts(
        promoted=promoted,
        appended=appended,
        held=held,
        expired=int(expired_count),
        recurrence_after_close=tuple(recurrence),
        match_rate=compute_match_rate(decisions),
        open_auto_improvement_count=int(open_auto_improvement_count),
        findings_per_session=findings_per_session,
        error_without_other_channel=tuple(sorted(silent_errors)),
        create_failures=int(create_failures),
    )


def _format_match_rate_line(counts: DigestCounts) -> str:
    """Render the match-rate line (alarm-aware)."""
    rate = counts.match_rate
    open_count = counts.open_auto_improvement_count
    if rate is None:
        return "Match-rate: n/a (no alarm)"
    pct = rate * 100.0
    if rate < MATCH_RATE_ALARM_THRESHOLD and open_count > OPEN_AUTO_IMPROVEMENT_COUNT_FOR_ALARM:
        return (
            f"Match-rate: {pct:.0f}% ALARM — possible over-clustering "
            f"({open_count} open auto-improvement issues, threshold "
            f"{int(MATCH_RATE_ALARM_THRESHOLD * 100)}%)"
        )
    return f"Match-rate: {pct:.0f}% (no alarm)"


def _format_findings_per_session_line(counts: DigestCounts) -> str:
    """Render the findings-per-session line (emission-failure alarm-aware)."""
    fps = counts.findings_per_session
    if fps is None:
        # No sessions observed — surface as informational (not an alarm).
        return "Findings-per-session: n/a (no sessions observed)"
    # Heuristic: if findings_per_session is exactly 0.0 AND distinct sessions
    # were observed, that's the emission-failure alarm. We can derive both
    # the findings_observed (numerator) and distinct sessions (denominator)
    # by treating fps == 0.0 with a positive denominator as the alarm.
    if fps == 0.0:
        # The denominator was > 0 (we set fps = None otherwise). Numerator
        # is 0 by construction.
        return (
            f"ALARM: CIA emission failure — 0 findings / "
            f"sessions observed (baseline ~{FINDINGS_PER_SESSION_BASELINE})"
        )
    return (
        f"Findings-per-session: {fps:.2f} "
        f"(baseline ~{FINDINGS_PER_SESSION_BASELINE})"
    )


def format_digest(counts: DigestCounts) -> str:
    """Render the 5-section direction-guard digest.

    All 5 sections are ALWAYS rendered (anti-habituation guarantee, AC4):
    populated AND empty digests carry the same section markers so a reader
    can never miss the absence of an expected signal.

    Sections (in order):
      1. ``ACTIONS TAKEN`` — Promoted / Appended / Held / Expired counts.
         When ``create_failures > 0``, append the failures line (#1203).
      2. ``Recurrence-after-close`` — one ``FIX DIDN'T STICK:`` line per
         match; literal ``Recurrence-after-close: 0`` when none.
      3. ``Match-rate`` — ALARM line when both gates trip; otherwise
         informational.
      4. ``Findings-per-session`` — emission-failure ALARM when zero
         findings against positive sessions; otherwise ratio.
      5. ``Error-without-other-channel`` — silent-error titles; literal
         ``Error-without-other-channel: 0`` when none.

    Args:
        counts: Output of :func:`build_digest`.

    Returns:
        Multi-line digest body (no trailing newline). Always contains
        the section markers listed above.
    """
    lines: List[str] = []

    # Section 1: ACTIONS TAKEN
    lines.append(
        f"ACTIONS TAKEN: Promoted: {counts.promoted} | "
        f"Appended: {counts.appended} | "
        f"Held: {counts.held} | "
        f"Expired: {counts.expired}"
    )
    if counts.create_failures > 0:
        lines.append(
            f"Create failures: {counts.create_failures} (see #1203)"
        )

    # Section 2: Recurrence-after-close
    if counts.recurrence_after_close:
        for tag, closed_num in counts.recurrence_after_close:
            lines.append(
                f"FIX DIDN'T STICK: tag={tag} closed_issue=#{closed_num}"
            )
    else:
        lines.append("Recurrence-after-close: 0")

    # Section 3: Match-rate
    lines.append(_format_match_rate_line(counts))

    # Section 4: Findings-per-session
    lines.append(_format_findings_per_session_line(counts))

    # Section 5: Error-without-other-channel
    if counts.error_without_other_channel:
        lines.append("Error-without-other-channel:")
        for desc in counts.error_without_other_channel:
            lines.append(f"  - {desc}")
    else:
        lines.append("Error-without-other-channel: 0")

    return "\n".join(lines)
