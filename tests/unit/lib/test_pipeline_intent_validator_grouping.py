"""Tests for (session_id, batch_issue_number) grouping and remediation skip.

Covers Issue #904 (ROOT-CAUSE consolidation):
- Issue #875: cross-pipeline isolation via tuple grouping key.
- Issue #902: remediation events skipped in duplicate-agent checks.
"""

import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_intent_validator import (  # noqa: E402
    PipelineEvent,
    validate_step_ordering,
)


def _evt(
    subagent_type: str,
    timestamp: str,
    *,
    session_id: str = "",
    batch_issue_number: int = 0,
    remediation: bool = False,
) -> PipelineEvent:
    """Build a minimal PipelineEvent for ordering tests."""
    return PipelineEvent(
        timestamp=timestamp,
        tool="Task",
        agent="main",
        subagent_type=subagent_type,
        pipeline_action="agent_invocation",
        session_id=session_id,
        batch_issue_number=batch_issue_number,
        remediation=remediation,
    )


class TestSessionIsolation:
    """Issue #875: two sessions in one log must not cross-contaminate."""

    def test_grouping_isolates_sessions(self):
        """Same batch_issue_number, different session_id → independent groups.

        Without the tuple grouping, session A's implementer at T0 followed
        by session B's planner at T1 would look like "implementer before
        planner" (a false CRITICAL). With tuple grouping, the two events
        are in different groups and no finding fires.
        """
        events = [
            # Session A: implementer-only (e.g., --fix issue)
            _evt(
                "implementer",
                "2026-04-24T10:00:00+00:00",
                session_id="session-A",
                batch_issue_number=0,
            ),
            # Session B: planner runs later
            _evt(
                "planner",
                "2026-04-24T10:05:00+00:00",
                session_id="session-B",
                batch_issue_number=0,
            ),
            _evt(
                "implementer",
                "2026-04-24T10:10:00+00:00",
                session_id="session-B",
                batch_issue_number=0,
            ),
        ]
        findings = validate_step_ordering(events)
        critical = [f for f in findings if f.severity == "CRITICAL"]
        assert critical == [], (
            "Issue #875: cross-session events must not produce CRITICAL ordering findings. "
            f"Got: {[f.description for f in critical]}"
        )

    def test_grouping_handles_empty_session_id_batch_mode(self):
        """Empty session_id still groups by batch_issue_number (back-compat)."""
        events = [
            _evt(
                "implementer",
                "2026-04-24T10:00:00+00:00",
                session_id="",
                batch_issue_number=100,
            ),
            _evt(
                "planner",
                "2026-04-24T10:05:00+00:00",
                session_id="",
                batch_issue_number=101,
            ),
            _evt(
                "implementer",
                "2026-04-24T10:10:00+00:00",
                session_id="",
                batch_issue_number=101,
            ),
        ]
        findings = validate_step_ordering(events)
        critical = [f for f in findings if f.severity == "CRITICAL"]
        assert critical == [], (
            "Empty-session batch events must still group by issue (preserves #680)."
        )

    def test_non_batch_events_still_group_together(self):
        """Legacy single-session logs (session_id='', issue=0) stay in one group."""
        events = [
            _evt("implementer", "2026-04-24T10:00:00+00:00"),
            _evt("planner", "2026-04-24T10:05:00+00:00"),
        ]
        findings = validate_step_ordering(events)
        critical = [f for f in findings if f.severity == "CRITICAL"]
        # Real ordering violation within the group — must still be caught.
        assert len(critical) >= 1, (
            "Non-batch single-session ordering violation must still be detected."
        )


class TestRemediationSkip:
    """Issue #902: remediation events must not trigger duplicate-agent findings."""

    def test_remediation_events_skipped_in_duplicate_check(self):
        """Re-invoked reviewer with remediation=True must not fire CRITICAL."""
        events = [
            _evt(
                "implementer",
                "2026-04-24T10:00:00+00:00",
                session_id="session-X",
            ),
            _evt(
                "reviewer",
                "2026-04-24T10:05:00+00:00",
                session_id="session-X",
            ),
            _evt(
                "security-auditor",
                "2026-04-24T10:06:00+00:00",
                session_id="session-X",
            ),
            # Reviewer re-run after BLOCKING findings — flagged remediation.
            _evt(
                "reviewer",
                "2026-04-24T10:10:00+00:00",
                session_id="session-X",
                remediation=True,
            ),
        ]
        findings = validate_step_ordering(events)
        # None of the CRITICAL findings should mention reviewer duplication.
        critical = [f for f in findings if f.severity == "CRITICAL"]
        reviewer_issues = [
            f for f in critical
            if "reviewer" in f.description and "reviewer" == f.description.split()[0]
        ]
        assert reviewer_issues == [], (
            "Issue #902: remediation-flagged reviewer must not produce duplicate CRITICAL. "
            f"Got: {[f.description for f in critical]}"
        )

    def test_remediation_false_still_enforces_ordering(self):
        """Non-remediation ordering violations are still caught."""
        events = [
            _evt(
                "implementer",
                "2026-04-24T10:00:00+00:00",
                session_id="session-Y",
            ),
            _evt(
                "planner",  # planner AFTER implementer — real violation
                "2026-04-24T10:05:00+00:00",
                session_id="session-Y",
            ),
        ]
        findings = validate_step_ordering(events)
        critical = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical) >= 1, (
            "Real ordering violation within a session must still fire CRITICAL."
        )
