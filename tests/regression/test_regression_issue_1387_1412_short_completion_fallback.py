#!/usr/bin/env python3
"""Regression tests for Issue #1387 / #1412 — short-completion false positive.

detect_doc_verdict_missing() correlates a doc-master invocation with the
temporally-closest completion event. When correlation pairs the invocation
with a truncated / heartbeat completion (result_word_count below
MIN_DOC_VERDICT_WORDS) even though a *healthy* full-length doc-master
completion exists elsewhere in the event stream, the low-word-count branch
would emit a false [DOC-VERDICT-MISSING] CRITICAL finding.

Fix #1387/#1412 mirrors the #650 ``any_healthy_completion`` guard (already in
the ``comp is None`` branch) into the low-word-count branch: skip the finding
when ANY doc-master completion in the full event list is healthy
(success=True AND result_word_count >= MIN_DOC_VERDICT_WORDS).

The genuine-failure branch (``not comp.success``) is intentionally NOT guarded
— a failed doc-master must always flag regardless of other healthy events.
"""

import sys
from pathlib import Path

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

from pipeline_intent_validator import (  # noqa: E402
    MIN_DOC_VERDICT_WORDS,
    PipelineEvent,
    detect_doc_verdict_missing,
)


def _invocation(ts: str) -> PipelineEvent:
    """A doc-master PostToolUse invocation (always result_word_count=0)."""
    return PipelineEvent(
        timestamp=ts,
        tool="Agent",
        agent="main",
        subagent_type="doc-master",
        pipeline_action="agent_invocation",
        prompt_word_count=500,
        result_word_count=0,
        success=True,
    )


def _completion(ts: str, *, word_count: int, success: bool = True) -> PipelineEvent:
    """A doc-master SubagentStop completion event."""
    return PipelineEvent(
        timestamp=ts,
        tool="Agent",
        agent="main",
        subagent_type="doc-master",
        pipeline_action="agent_completion",
        prompt_word_count=0,
        result_word_count=word_count,
        success=success,
    )


class TestIssue13871412ShortCompletionFallback:
    """Fix A — #1387/#1412 low-word-count fallback guard."""

    def test_short_completion_with_healthy_elsewhere_no_finding(self):
        """Short paired completion + a healthy completion elsewhere → NO finding.

        The invocation correlates with the closest (short) completion at 10:02,
        triggering the low-word-count branch. A healthy full-length completion
        exists at 10:04. The #1387/#1412 guard should suppress the false
        positive.
        """
        events = [
            _invocation("2026-03-22T10:00:00+00:00"),
            # Closest completion — short/truncated (correlates with the invocation)
            _completion("2026-03-22T10:02:00+00:00", word_count=5),
            # Healthy full-length completion later in the stream
            _completion(
                "2026-03-22T10:04:00+00:00",
                word_count=MIN_DOC_VERDICT_WORDS + 100,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        doc_findings = [f for f in findings if f.finding_type == "doc_verdict_missing"]
        assert doc_findings == [], (
            "#1387/#1412: short paired completion with a healthy completion "
            f"elsewhere must NOT flag DOC-VERDICT-MISSING, got: {doc_findings}"
        )

    def test_short_completion_only_still_flags(self):
        """Short completion with NO healthy completion anywhere → finding STILL emitted."""
        events = [
            _invocation("2026-03-22T10:00:00+00:00"),
            _completion("2026-03-22T10:02:00+00:00", word_count=5),
        ]
        findings = detect_doc_verdict_missing(events)
        doc_findings = [f for f in findings if f.finding_type == "doc_verdict_missing"]
        assert len(doc_findings) == 1, (
            "#1387/#1412: short-only completion with no healthy completion must "
            f"still flag, got: {doc_findings}"
        )
        assert doc_findings[0].severity == "CRITICAL"
        assert "[DOC-VERDICT-MISSING]" in doc_findings[0].description

    def test_failure_branch_unchanged_even_with_healthy_completion(self):
        """The ``not comp.success`` failure branch is NOT masked by a healthy completion.

        The invocation correlates with the closest (failed) completion at 10:02.
        A healthy completion exists at 10:04. Fix A intentionally does NOT touch
        the failure branch, so the finding must STILL be emitted.
        """
        events = [
            _invocation("2026-03-22T10:00:00+00:00"),
            # Closest completion — sufficient words but FAILED (success=False)
            _completion(
                "2026-03-22T10:02:00+00:00",
                word_count=MIN_DOC_VERDICT_WORDS + 100,
                success=False,
            ),
            # Healthy completion later — must NOT suppress the failure finding
            _completion(
                "2026-03-22T10:04:00+00:00",
                word_count=MIN_DOC_VERDICT_WORDS + 100,
                success=True,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        doc_findings = [f for f in findings if f.finding_type == "doc_verdict_missing"]
        assert len(doc_findings) == 1, (
            "#1387/#1412: genuine-failure branch must remain unmasked even when a "
            f"healthy completion exists, got: {doc_findings}"
        )
        # Confirm this is the genuine-failure branch (not the low-word-count one)
        assert "failed (success=False)" in doc_findings[0].description
        assert "[DOC-VERDICT-MISSING]" in doc_findings[0].description


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
