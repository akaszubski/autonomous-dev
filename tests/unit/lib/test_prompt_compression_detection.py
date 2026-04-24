#!/usr/bin/env python3
"""
Unit Tests for Prompt Compression Detection (Issue #544)

Tests for detect_progressive_compression() and detect_minimum_prompt_violation()
functions in pipeline_intent_validator.py.
"""

import json
import sys
from datetime import datetime, timedelta
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

from pipeline_intent_validator import (
    COMPRESSION_CRITICAL_AGENTS,
    MAX_PROMPT_SHRINKAGE_RATIO,
    MIN_CRITICAL_AGENT_PROMPT_WORDS,
    Finding,
    PipelineEvent,
    detect_minimum_prompt_violation,
    detect_progressive_compression,
    parse_session_logs,
    validate_pipeline_intent,
)


def _make_batch_event(
    subagent_type: str = "implementer",
    batch_issue_number: int = 1,
    prompt_word_count: int = 500,
    result_word_count: int = 2000,
    tool: str = "Agent",
    timestamp: str = "2026-03-22T10:00:00+00:00",
) -> PipelineEvent:
    """Helper to create a batch PipelineEvent for testing."""
    return PipelineEvent(
        timestamp=timestamp,
        tool=tool,
        agent="main",
        subagent_type=subagent_type,
        pipeline_action="agent_invocation",
        prompt_word_count=prompt_word_count,
        result_word_count=result_word_count,
        batch_issue_number=batch_issue_number,
    )


class TestDetectProgressiveCompression:
    """Tests for detect_progressive_compression function."""

    def test_no_compression_no_findings(self):
        """Events with consistent prompt sizes produce no findings."""
        events = [
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=1,
                prompt_word_count=500,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=2,
                prompt_word_count=480,
                timestamp="2026-03-22T10:10:00+00:00",
            ),
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=3,
                prompt_word_count=460,
                timestamp="2026-03-22T10:20:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 0, "#544: consistent prompts should produce no findings"

    def test_30_percent_compression_not_flagged(self):
        """30% shrinkage does NOT exceed 40% threshold (Issue #757)."""
        events = [
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=2,
                prompt_word_count=700,  # 30% shrinkage from 1000
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 0, "#757: 30% shrinkage should NOT be flagged with 40% threshold"

    def test_40_percent_boundary(self):
        """Exactly 40% shrinkage means ratio = 0.60, which equals the threshold.

        The check is `ratio < (1 - MAX_PROMPT_SHRINKAGE_RATIO)` = `ratio < 0.60`.
        So at exactly 40% shrinkage (ratio = 0.60), it should NOT be flagged.
        Just past 40% (ratio slightly < 0.60) SHOULD be flagged.
        """
        # Exactly at boundary: 600/1000 = 0.60, NOT flagged (ratio is not < 0.60)
        events_boundary = [
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=2,
                prompt_word_count=600,
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events_boundary)
        assert len(findings) == 0, "#757: exactly 40% shrinkage (ratio=0.60) should not flag"

        # Just past boundary: 599/1000 = 0.599, IS flagged (ratio < 0.60)
        events_past = [
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=2,
                prompt_word_count=599,
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events_past)
        assert len(findings) == 1, "#757: >40% shrinkage (ratio=0.599) should flag"

    def test_39_percent_passes(self):
        """39% shrinkage does not exceed 40% threshold (Issue #757)."""
        events = [
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=2,
                prompt_word_count=610,  # 39% shrinkage, ratio = 0.61 > 0.60
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 0, "#757: 39% shrinkage should not be flagged"

    def test_critical_severity_for_security_agents(self):
        """Security-critical agents (reviewer, security-auditor) get CRITICAL severity."""
        for agent_type in ["reviewer", "security-auditor"]:
            events = [
                _make_batch_event(
                    subagent_type=agent_type,
                    batch_issue_number=1,
                    prompt_word_count=1000,
                    timestamp="2026-03-22T10:00:00+00:00",
                ),
                _make_batch_event(
                    subagent_type=agent_type,
                    batch_issue_number=3,
                    prompt_word_count=500,  # 50% shrinkage
                    timestamp="2026-03-22T10:30:00+00:00",
                ),
            ]
            findings = detect_progressive_compression(events)
            assert len(findings) == 1, f"#544: {agent_type} compression should be flagged"
            assert findings[0].severity == "CRITICAL", (
                f"#544: {agent_type} should get CRITICAL severity"
            )

    def test_warning_severity_for_non_critical_agents(self):
        """Non-critical agents get WARNING severity."""
        events = [
            _make_batch_event(
                subagent_type="scaffolder",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="scaffolder",
                batch_issue_number=2,
                prompt_word_count=500,  # 50% shrinkage
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 1, "#544: non-critical compression should be flagged"
        assert findings[0].severity == "WARNING", "#544: non-critical should get WARNING"

    def test_no_batch_events_skipped(self):
        """Events with batch_issue_number=0 (non-batch) are skipped entirely."""
        events = [
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=0,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=0,
                prompt_word_count=100,
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 0, "#544: non-batch events should be skipped"

    def test_single_issue_batch_no_findings(self):
        """Batch with only one issue cannot have compression — no findings."""
        events = [
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=1,
                prompt_word_count=500,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 0, "#544: single-issue batch should have no findings"

    def test_multiple_agents_independent(self):
        """Compression is checked independently per agent type."""
        events = [
            # reviewer: consistent (no compression)
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=1,
                prompt_word_count=500,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=2,
                prompt_word_count=490,
                timestamp="2026-03-22T10:10:00+00:00",
            ),
            # implementer: compressed (should flag)
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:05:00+00:00",
            ),
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=2,
                prompt_word_count=300,  # 70% shrinkage
                timestamp="2026-03-22T10:15:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 1, "#544: only implementer should be flagged"
        assert "implementer" in findings[0].description


class TestDetectMinimumPromptViolation:
    """Tests for detect_minimum_prompt_violation function."""

    def test_below_minimum_flagged(self):
        """Security-critical agent with prompt below minimum is CRITICAL."""
        events = [
            _make_batch_event(
                subagent_type="security-auditor",
                prompt_word_count=50,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
        ]
        findings = detect_minimum_prompt_violation(events)
        assert len(findings) == 1, "#544: below minimum should be flagged"
        assert findings[0].severity == "CRITICAL"
        assert findings[0].finding_type == "minimum_prompt_violation"

    def test_above_minimum_passes(self):
        """Security-critical agent above minimum produces no findings."""
        events = [
            _make_batch_event(
                subagent_type="reviewer",
                prompt_word_count=200,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
        ]
        findings = detect_minimum_prompt_violation(events)
        assert len(findings) == 0, "#544: above minimum should produce no findings"

    def test_non_critical_agent_not_checked(self):
        """Non-critical agents are not subject to minimum prompt checks."""
        events = [
            _make_batch_event(
                subagent_type="scaffolder",
                prompt_word_count=30,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="aligner",
                prompt_word_count=20,
                timestamp="2026-03-22T10:05:00+00:00",
            ),
        ]
        findings = detect_minimum_prompt_violation(events)
        assert len(findings) == 0, "#544: non-critical agents should not be checked"

    def test_zero_word_count_skipped(self):
        """Events with prompt_word_count=0 are skipped (not recorded)."""
        events = [
            _make_batch_event(
                subagent_type="reviewer",
                prompt_word_count=0,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
        ]
        findings = detect_minimum_prompt_violation(events)
        assert len(findings) == 0, "#544: zero word count should be skipped"

    def test_exact_minimum_passes(self):
        """Exactly at minimum (80 words) should pass."""
        events = [
            _make_batch_event(
                subagent_type="security-auditor",
                prompt_word_count=MIN_CRITICAL_AGENT_PROMPT_WORDS,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
        ]
        findings = detect_minimum_prompt_violation(events)
        assert len(findings) == 0, "#544: exact minimum should pass"


class TestIntegration:
    """Integration tests for orchestrator wiring."""

    def test_validate_pipeline_intent_does_not_call_detect_progressive_compression(self, tmp_path):
        """validate_pipeline_intent() no longer wires detect_progressive_compression (Issue #925).

        Cross-issue baseline ratio produced 5 false positives (#757 #723 #867 #805 #923).
        Detection of downstream-prompt vs upstream-result compression is now handled by
        detect_context_dropping (spec-compliant within-issue ratio).
        """
        log_file = tmp_path / "batch.jsonl"
        base = datetime(2026, 3, 22, 10, 0, 0)
        lines = []
        for issue_num, word_count in [(1, 1000), (2, 400)]:
            entry = {
                "timestamp": (base + timedelta(minutes=issue_num * 10)).isoformat(),
                "tool": "Agent",
                "input_summary": {
                    "subagent_type": "security-auditor",
                    "pipeline_action": "agent_invocation",
                    "prompt_word_count": word_count,
                    "batch_issue_number": issue_num,
                },
                "output_summary": {"success": True, "result_word_count": 500},
                "session_id": "batch-test",
                "agent": "main",
            }
            lines.append(json.dumps(entry))
        log_file.write_text("\n".join(lines) + "\n")

        findings = validate_pipeline_intent(log_file, session_id="batch-test")
        compression_findings = [
            f for f in findings if f.finding_type == "progressive_compression"
        ]
        assert len(compression_findings) == 0, (
            "Issue #925: progressive_compression is no longer wired into validate_pipeline_intent. "
            "Cross-issue baseline produced 5 prior false-positive closures and has been disabled."
        )

    def test_validate_pipeline_intent_includes_minimum_prompt_violation(self, tmp_path):
        """validate_pipeline_intent() calls detect_minimum_prompt_violation()."""
        log_file = tmp_path / "min_prompt.jsonl"
        entry = {
            "timestamp": "2026-03-22T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "reviewer",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 30,
                "batch_issue_number": 0,
            },
            "output_summary": {"success": True, "result_word_count": 500},
            "session_id": "min-test",
            "agent": "main",
        }
        log_file.write_text(json.dumps(entry) + "\n")

        findings = validate_pipeline_intent(log_file, session_id="min-test")
        min_findings = [
            f for f in findings if f.finding_type == "minimum_prompt_violation"
        ]
        assert len(min_findings) >= 1, (
            "#544: validate_pipeline_intent should include minimum prompt violation findings"
        )


class TestConstants:
    """Tests for Issue #544 constants and data model."""

    def test_compression_critical_agents_defined(self):
        """COMPRESSION_CRITICAL_AGENTS constant contains expected agents."""
        assert "security-auditor" in COMPRESSION_CRITICAL_AGENTS
        assert "reviewer" in COMPRESSION_CRITICAL_AGENTS
        assert "researcher-local" in COMPRESSION_CRITICAL_AGENTS
        assert "researcher" in COMPRESSION_CRITICAL_AGENTS

    def test_max_prompt_shrinkage_ratio(self):
        """MAX_PROMPT_SHRINKAGE_RATIO is 0.40 (40%) per Issue #757."""
        assert MAX_PROMPT_SHRINKAGE_RATIO == 0.40

    def test_min_critical_agent_prompt_words(self):
        """MIN_CRITICAL_AGENT_PROMPT_WORDS is 80."""
        assert MIN_CRITICAL_AGENT_PROMPT_WORDS == 80

    def test_pipeline_event_has_batch_issue_number(self):
        """PipelineEvent dataclass has batch_issue_number field with default 0."""
        event = PipelineEvent(
            timestamp="2026-03-22T10:00:00+00:00",
            tool="Agent",
            agent="main",
            subagent_type="reviewer",
            pipeline_action="agent_invocation",
        )
        assert event.batch_issue_number == 0, "#544: default batch_issue_number should be 0"

    def test_pipeline_event_batch_issue_number_settable(self):
        """PipelineEvent batch_issue_number can be set to any positive int."""
        event = PipelineEvent(
            timestamp="2026-03-22T10:00:00+00:00",
            tool="Agent",
            agent="main",
            subagent_type="reviewer",
            pipeline_action="agent_invocation",
            batch_issue_number=5,
        )
        assert event.batch_issue_number == 5


class TestParseSessionLogsBatchIssueNumber:
    """Tests for batch_issue_number extraction in parse_session_logs."""

    def test_batch_issue_number_parsed_from_input_summary(self, tmp_path):
        """batch_issue_number is extracted from input_summary."""
        log_file = tmp_path / "batch.jsonl"
        entry = {
            "timestamp": "2026-03-22T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "reviewer",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 500,
                "batch_issue_number": 3,
            },
            "output_summary": {"success": True, "result_word_count": 500},
            "session_id": "test",
            "agent": "main",
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1
        assert events[0].batch_issue_number == 3

    def test_batch_issue_number_defaults_to_zero(self, tmp_path):
        """Missing batch_issue_number defaults to 0."""
        log_file = tmp_path / "nobatch.jsonl"
        entry = {
            "timestamp": "2026-03-22T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "reviewer",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 500,
            },
            "output_summary": {"success": True, "result_word_count": 500},
            "session_id": "test",
            "agent": "main",
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1
        assert events[0].batch_issue_number == 0

    def test_batch_issue_number_invalid_type_defaults_to_zero(self, tmp_path):
        """Non-integer batch_issue_number defaults to 0."""
        log_file = tmp_path / "invalid.jsonl"
        entry = {
            "timestamp": "2026-03-22T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "reviewer",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 500,
                "batch_issue_number": "not-a-number",
            },
            "output_summary": {"success": True, "result_word_count": 500},
            "session_id": "test",
            "agent": "main",
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1
        assert events[0].batch_issue_number == 0


class TestCompressionPrevention:
    """Tests for compression prevention -- recommended_action field (Issue #561)."""

    def test_compression_finding_has_recommended_action(self):
        """Compression findings must include non-None recommended_action."""
        events = [
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="reviewer",
                batch_issue_number=3,
                prompt_word_count=500,  # 50% shrinkage
                timestamp="2026-03-22T10:30:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 1
        assert findings[0].recommended_action is not None
        assert "agents/reviewer.md" in findings[0].recommended_action
        assert "Reload" in findings[0].recommended_action

    def test_compression_with_agents_dir_includes_prompt_path(self, tmp_path):
        """When agents_dir is provided, evidence includes prompt source path."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "implementer.md").write_text("agent prompt content here")

        events = [
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=2,
                prompt_word_count=500,  # 50% shrinkage
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events, agents_dir=agents_dir)
        assert len(findings) == 1
        prompt_source_evidence = [e for e in findings[0].evidence if "prompt_source" in e]
        assert len(prompt_source_evidence) == 1
        assert "implementer.md" in prompt_source_evidence[0]

    def test_no_agents_dir_no_prompt_path(self):
        """Without agents_dir, evidence does not include prompt source path."""
        events = [
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=1,
                prompt_word_count=1000,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_batch_event(
                subagent_type="implementer",
                batch_issue_number=2,
                prompt_word_count=500,
                timestamp="2026-03-22T10:10:00+00:00",
            ),
        ]
        findings = detect_progressive_compression(events)
        assert len(findings) == 1
        prompt_source_evidence = [e for e in findings[0].evidence if "prompt_source" in e]
        assert len(prompt_source_evidence) == 0

