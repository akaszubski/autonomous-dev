#!/usr/bin/env python3
"""
Unit tests for Agent Output Health Library - Issues #793, #792

Tests zero-word detection, agent health verdicts, and batch health summary
generation. Regression tests for ghost/absent agent output detection.
"""

import sys
from pathlib import Path

import pytest

# tests/unit/lib/ -> tests/unit/ -> tests/ -> repo root
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

from agent_output_health import (
    AGENT_MIN_WORD_THRESHOLDS,
    DEFAULT_MIN_WORDS,
    GHOST_MAX_DURATION_MS,
    AgentHealthVerdict,
    check_agent_output_health,
    detect_zero_word_completions,
    generate_batch_health_summary,
)
from pipeline_intent_validator import Finding, PipelineEvent


def _make_event(
    subagent_type: str = "implementer",
    pipeline_action: str = "agent_completion",
    result_word_count: int = 200,
    duration_ms: int = 30000,
    tool: str = "Agent",
    timestamp: str = "2026-04-13T10:00:00+00:00",
) -> PipelineEvent:
    """Helper to create PipelineEvent for agent output health tests."""
    return PipelineEvent(
        timestamp=timestamp,
        tool=tool,
        agent="main",
        subagent_type=subagent_type,
        pipeline_action=pipeline_action,
        result_word_count=result_word_count,
        duration_ms=duration_ms,
    )


class TestDetectZeroWordCompletions:
    """Tests for detect_zero_word_completions() — core fix for issue #793."""

    def test_zero_word_completion_flagged_as_critical(self) -> None:
        """Zero-word completion produces a CRITICAL finding."""
        events = [
            _make_event(
                subagent_type="reviewer",
                result_word_count=0,
                duration_ms=5000,
            ),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 1
        assert findings[0].severity == "CRITICAL"
        assert findings[0].pattern_id == "zero_word_agent_output"
        assert findings[0].finding_type == "zero_word_agent_output"

    def test_zero_word_ghost_flagged(self) -> None:
        """Ghost completion (0 words, <5ms) is still CRITICAL."""
        events = [
            _make_event(
                subagent_type="implementer",
                result_word_count=0,
                duration_ms=3,
            ),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 1
        assert findings[0].severity == "CRITICAL"
        assert "implementer" in findings[0].description

    def test_nonzero_word_completion_not_flagged(self) -> None:
        """Completion with words produces no findings."""
        events = [
            _make_event(result_word_count=50, duration_ms=30000),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 0

    def test_invocation_events_excluded(self) -> None:
        """Invocation events (always 0 words) are not false positives."""
        events = [
            _make_event(
                pipeline_action="agent_invocation",
                result_word_count=0,
                duration_ms=1,
            ),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 0

    def test_doc_master_zero_words_flagged(self) -> None:
        """doc-master with 0 words produces CRITICAL finding (issue #792)."""
        events = [
            _make_event(
                subagent_type="doc-master",
                result_word_count=0,
                duration_ms=15000,
            ),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 1
        assert findings[0].severity == "CRITICAL"
        assert "doc-master" in findings[0].description


class TestCheckAgentOutputHealth:
    """Tests for check_agent_output_health() — per-event health verdicts."""

    def test_healthy_agent_verdict(self) -> None:
        """Agent with sufficient words is 'healthy'."""
        events = [
            _make_event(result_word_count=100, duration_ms=30000),
        ]
        verdicts = check_agent_output_health(events)

        assert len(verdicts) == 1
        assert verdicts[0].status == "healthy"
        assert verdicts[0].word_count == 100

    def test_ghost_agent_verdict(self) -> None:
        """Agent with 0 words and fast completion is 'ghost'."""
        events = [
            _make_event(result_word_count=0, duration_ms=3),
        ]
        verdicts = check_agent_output_health(events)

        assert len(verdicts) == 1
        assert verdicts[0].status == "ghost"

    def test_zero_output_verdict(self) -> None:
        """Agent with 0 words but slow completion is 'zero_output'."""
        events = [
            _make_event(result_word_count=0, duration_ms=30000),
        ]
        verdicts = check_agent_output_health(events)

        assert len(verdicts) == 1
        assert verdicts[0].status == "zero_output"

    def test_shallow_agent_verdict(self) -> None:
        """Agent with words below default threshold is 'shallow'."""
        events = [
            _make_event(
                subagent_type="test-master",  # not in thresholds, uses DEFAULT_MIN_WORDS=10
                result_word_count=5,
                duration_ms=20000,
            ),
        ]
        verdicts = check_agent_output_health(events)

        assert len(verdicts) == 1
        assert verdicts[0].status == "shallow"

    def test_security_auditor_higher_threshold(self) -> None:
        """security-auditor with 40 words (below 50 threshold) is 'shallow'."""
        events = [
            _make_event(
                subagent_type="security-auditor",
                result_word_count=40,
                duration_ms=25000,
            ),
        ]
        verdicts = check_agent_output_health(events)

        assert len(verdicts) == 1
        assert verdicts[0].status == "shallow"


class TestGenerateBatchHealthSummary:
    """Tests for generate_batch_health_summary() — per-agent aggregation."""

    def test_summary_counts_by_agent(self) -> None:
        """Summary correctly aggregates counts per agent type."""
        events = [
            _make_event(subagent_type="reviewer", result_word_count=100, duration_ms=20000),
            _make_event(subagent_type="reviewer", result_word_count=200, duration_ms=30000),
            _make_event(subagent_type="implementer", result_word_count=500, duration_ms=60000),
        ]
        summary = generate_batch_health_summary(events)

        assert "reviewer" in summary
        assert "implementer" in summary
        assert summary["reviewer"]["invocation_count"] == 2
        assert summary["reviewer"]["total_word_count"] == 300
        assert summary["reviewer"]["avg_word_count"] == 150.0
        assert summary["implementer"]["invocation_count"] == 1
        assert summary["implementer"]["total_word_count"] == 500

    def test_summary_with_ghosts(self) -> None:
        """Ghost completions increment ghost_count and zero_word_count."""
        events = [
            _make_event(subagent_type="reviewer", result_word_count=0, duration_ms=3),
            _make_event(subagent_type="reviewer", result_word_count=100, duration_ms=20000),
        ]
        summary = generate_batch_health_summary(events)

        assert summary["reviewer"]["ghost_count"] == 1
        assert summary["reviewer"]["zero_word_count"] == 1
        assert summary["reviewer"]["invocation_count"] == 2

    def test_empty_events_returns_empty_summary(self) -> None:
        """Empty event list returns empty dict."""
        summary = generate_batch_health_summary([])

        assert summary == {}


class TestDedupSkipFilter:
    """Issue #1266: __dedup_skip__:* markers are filtered from ghost/zero-word detection.

    Internal hook dedup-tracking markers (subagent_type starting with
    `__dedup_skip__`) are NOT real agent invocations. They always have
    result_word_count=0 and duration_ms=1, which historically caused
    20+ spurious CRITICAL zero_word_agent_output findings per CIA report.
    """

    def test_dedup_skip_events_filtered_from_zero_word_detection(self) -> None:
        """Positive control: 5 __dedup_skip__ markers + 1 healthy real agent -> 0 findings."""
        events = [
            _make_event(
                subagent_type="__dedup_skip__:implementer",
                result_word_count=0,
                duration_ms=1,
            )
            for _ in range(5)
        ] + [
            _make_event(
                subagent_type="implementer",
                result_word_count=100,
                duration_ms=15000,
            ),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 0, (
            f"Dedup markers must be filtered out, got {len(findings)} findings: "
            f"{[f.description for f in findings]}"
        )

    def test_real_ghost_agent_still_detected(self) -> None:
        """Negative control: 5 dedup markers + 1 genuinely-empty real agent -> 1 finding."""
        events = [
            _make_event(
                subagent_type="__dedup_skip__:implementer",
                result_word_count=0,
                duration_ms=1,
            )
            for _ in range(5)
        ] + [
            _make_event(
                subagent_type="implementer",
                result_word_count=0,
                duration_ms=5000,
            ),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 1, (
            f"Real ghost agent must still surface, got {len(findings)} findings"
        )
        assert "implementer" in findings[0].description
        assert "__dedup_skip__" not in findings[0].description, (
            f"Dedup marker leaked into finding: {findings[0].description}"
        )

    def test_mixed_dedup_and_real_agents(self) -> None:
        """Multiple agent types: only real ghosts surface; markers and healthy agents do not."""
        events = [
            _make_event(
                subagent_type="__dedup_skip__:implementer",
                result_word_count=0,
                duration_ms=1,
            ),
            _make_event(
                subagent_type="__dedup_skip__:reviewer",
                result_word_count=0,
                duration_ms=1,
            ),
            _make_event(
                subagent_type="reviewer",
                result_word_count=0,
                duration_ms=4000,
            ),
            _make_event(
                subagent_type="implementer",
                result_word_count=100,
                duration_ms=15000,
            ),
        ]
        findings = detect_zero_word_completions(events)

        assert len(findings) == 1, (
            f"Expected exactly 1 finding for real reviewer ghost, got {len(findings)}: "
            f"{[f.description for f in findings]}"
        )
        assert "reviewer" in findings[0].description
        assert "__dedup_skip__" not in findings[0].description
