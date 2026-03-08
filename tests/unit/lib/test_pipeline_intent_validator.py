#!/usr/bin/env python3
"""
TDD Tests for Pipeline Intent Validator Library (Issue #367) - RED PHASE

Tests validate pipeline_intent_validator.py which detects intent-level
pipeline violations: step ordering, hard gate bypasses, context dropping,
and parallelization violations.

All tests FAIL initially (lib/pipeline_intent_validator.py doesn't exist yet).
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
    Finding,
    PipelineEvent,
    detect_context_dropping,
    detect_hard_gate_ordering,
    detect_parallelization_violations,
    parse_session_logs,
    validate_pipeline_intent,
    validate_step_ordering,
)


def _make_event(
    agent: str = "main",
    subagent_type: str = "",
    pipeline_action: str = "agent_invocation",
    tool: str = "Task",
    timestamp: str = "2026-02-28T10:00:00+00:00",
    prompt_word_count: int = 500,
    result_word_count: int = 2000,
    success: bool = True,
) -> PipelineEvent:
    """Helper to create PipelineEvent for tests."""
    return PipelineEvent(
        timestamp=timestamp,
        tool=tool,
        agent=agent,
        subagent_type=subagent_type,
        pipeline_action=pipeline_action,
        prompt_word_count=prompt_word_count,
        result_word_count=result_word_count,
        success=success,
    )


def _make_jsonl_line(
    agent: str = "main",
    subagent_type: str = "",
    pipeline_action: str = "agent_invocation",
    tool: str = "Task",
    timestamp: str = "2026-02-28T10:00:00+00:00",
    prompt_word_count: int = 500,
    result_word_count: int = 2000,
    success: bool = True,
    session_id: str = "test-session",
    command: str = "",
) -> str:
    """Helper to create JSONL log line."""
    if tool == "Task":
        entry = {
            "timestamp": timestamp,
            "tool": tool,
            "input_summary": {
                "description": f"Run {subagent_type}",
                "subagent_type": subagent_type,
                "pipeline_action": pipeline_action,
                "prompt_word_count": prompt_word_count,
            },
            "output_summary": {
                "success": success,
                "result_word_count": result_word_count,
            },
            "session_id": session_id,
            "agent": agent,
        }
    else:
        entry = {
            "timestamp": timestamp,
            "tool": tool,
            "input_summary": {
                "command": command or "pytest --tb=short -q",
                "pipeline_action": pipeline_action,
            },
            "output_summary": {"success": success},
            "session_id": session_id,
            "agent": agent,
        }
    return json.dumps(entry)


def _write_clean_pipeline(log_file: Path, session_id: str = "test-session") -> None:
    """Write a clean pipeline JSONL with correct ordering."""
    base = datetime(2026, 2, 28, 10, 0, 0)
    lines = [
        _make_jsonl_line(subagent_type="researcher-local", timestamp=(base).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="researcher", timestamp=(base + timedelta(seconds=2)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="test-master", timestamp=(base + timedelta(minutes=4)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="implementer", timestamp=(base + timedelta(minutes=6)).isoformat(), session_id=session_id),
        _make_jsonl_line(tool="Bash", pipeline_action="test_run", timestamp=(base + timedelta(minutes=8)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="reviewer", timestamp=(base + timedelta(minutes=10)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="security-auditor", timestamp=(base + timedelta(minutes=10, seconds=2)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="doc-master", timestamp=(base + timedelta(minutes=10, seconds=4)).isoformat(), session_id=session_id),
    ]
    log_file.write_text("\n".join(lines) + "\n")


class TestParseSessionLogs:
    """Tests for parse_session_logs function."""

    def test_parses_task_entries_from_jsonl(self, tmp_path):
        """Task tool entries are parsed into PipelineEvent with correct fields."""
        log_file = tmp_path / "session.jsonl"
        log_file.write_text(
            _make_jsonl_line(subagent_type="researcher-local", prompt_word_count=500, result_word_count=2000) + "\n"
        )
        events = parse_session_logs(log_file)
        assert len(events) == 1, "#367: should parse one event"
        e = events[0]
        assert e.subagent_type == "researcher-local", "#367: subagent_type"
        assert e.tool == "Task", "#367: tool"
        assert e.prompt_word_count == 500, "#367: prompt_word_count"
        assert e.result_word_count == 2000, "#367: result_word_count"

    def test_filters_by_session_id(self, tmp_path):
        """Only events matching session_id are returned."""
        log_file = tmp_path / "session.jsonl"
        lines = [
            _make_jsonl_line(subagent_type="researcher", session_id="session-a"),
            _make_jsonl_line(subagent_type="planner", session_id="session-b"),
        ]
        log_file.write_text("\n".join(lines) + "\n")
        events = parse_session_logs(log_file, session_id="session-a")
        assert len(events) == 1, "#367: session filter should return 1 event"
        assert events[0].subagent_type == "researcher"

    def test_handles_empty_file(self, tmp_path):
        """Empty file returns empty list."""
        log_file = tmp_path / "empty.jsonl"
        log_file.write_text("")
        events = parse_session_logs(log_file)
        assert events == [], "#367: empty file should return empty list"

    def test_handles_malformed_lines(self, tmp_path):
        """Malformed JSON lines are skipped."""
        log_file = tmp_path / "bad.jsonl"
        lines = [
            "not json at all",
            _make_jsonl_line(subagent_type="planner"),
            '{"incomplete": true',
        ]
        log_file.write_text("\n".join(lines) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1, "#367: should skip malformed, parse valid"

    def test_includes_bash_test_run(self, tmp_path):
        """Bash entries with pipeline_action=test_run are included."""
        log_file = tmp_path / "session.jsonl"
        log_file.write_text(
            _make_jsonl_line(tool="Bash", pipeline_action="test_run", command="pytest --tb=short -q") + "\n"
        )
        events = parse_session_logs(log_file)
        assert len(events) == 1, "#367: Bash test_run should be included"
        assert events[0].tool == "Bash"
        assert events[0].pipeline_action == "test_run"


class TestParseAgentToolName:
    """Tests for Agent tool name handling (fix for issue #380)."""

    def test_parses_agent_tool_entries(self, tmp_path):
        """Agent tool entries (new Claude Code name) should be parsed into PipelineEvent."""
        log_file = tmp_path / "agent.jsonl"
        # Use "Agent" tool name instead of "Task"
        entry = {
            "timestamp": "2026-03-08T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {
                "description": "Research patterns",
                "subagent_type": "researcher",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 500,
            },
            "output_summary": {"success": True, "result_word_count": 2000},
            "session_id": "test-session",
            "agent": "main",
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1, "#380: Agent tool should be parsed"
        assert events[0].subagent_type == "researcher"
        assert events[0].tool == "Agent"

    def test_mixed_task_and_agent_tools(self, tmp_path):
        """Both Task (old) and Agent (new) tool names should be parsed."""
        log_file = tmp_path / "mixed.jsonl"
        task_entry = {
            "timestamp": "2026-02-28T10:00:00+00:00",
            "tool": "Task",
            "input_summary": {"subagent_type": "planner", "pipeline_action": "agent_invocation"},
            "output_summary": {"success": True},
            "session_id": "test-session",
            "agent": "main",
        }
        agent_entry = {
            "timestamp": "2026-03-08T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {"subagent_type": "implementer", "pipeline_action": "agent_invocation"},
            "output_summary": {"success": True},
            "session_id": "test-session",
            "agent": "main",
        }
        log_file.write_text(json.dumps(task_entry) + "\n" + json.dumps(agent_entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 2, "#380: both Task and Agent should be parsed"
        assert events[0].subagent_type == "planner"
        assert events[1].subagent_type == "implementer"

    def test_step_ordering_with_agent_tool(self):
        """Step ordering validation should work with Agent tool events."""
        base = datetime(2026, 3, 8, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", tool="Agent", timestamp=base.isoformat()),
            _make_event(subagent_type="planner", tool="Agent", timestamp=(base + timedelta(minutes=2)).isoformat()),
        ]
        findings = validate_step_ordering(events)
        assert len(findings) >= 1, "#380: ordering violation should be detected with Agent tool"

    def test_context_dropping_with_agent_tool(self):
        """Context dropping detection should work with Agent tool events."""
        base = datetime(2026, 3, 8, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher", tool="Agent", timestamp=base.isoformat(), result_word_count=2000),
            _make_event(subagent_type="planner", tool="Agent", timestamp=(base + timedelta(minutes=2)).isoformat(), prompt_word_count=50),
        ]
        findings = detect_context_dropping(events)
        assert len(findings) >= 1, "#380: context dropping should be detected with Agent tool"


class TestValidateStepOrdering:
    """Tests for validate_step_ordering function."""

    def test_correct_order_passes(self):
        """Correctly ordered pipeline produces no findings."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher-local", timestamp=base.isoformat()),
            _make_event(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat()),
            _make_event(subagent_type="test-master", timestamp=(base + timedelta(minutes=4)).isoformat()),
            _make_event(subagent_type="implementer", timestamp=(base + timedelta(minutes=6)).isoformat()),
        ]
        findings = validate_step_ordering(events)
        assert len(findings) == 0, "#367: correct order should have no findings"

    def test_implementer_before_planner(self):
        """Implementer running before planner is a CRITICAL finding."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", timestamp=base.isoformat()),
            _make_event(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat()),
        ]
        findings = validate_step_ordering(events)
        assert len(findings) >= 1, "#367: wrong order should produce findings"
        assert any(f.severity == "CRITICAL" for f in findings), "#367: should be CRITICAL"

    def test_missing_step_detected(self):
        """Missing test-master step produces CRITICAL finding."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher-local", timestamp=base.isoformat()),
            _make_event(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat()),
            _make_event(subagent_type="implementer", timestamp=(base + timedelta(minutes=4)).isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=6)).isoformat()),
        ]
        findings = validate_step_ordering(events)
        critical = [f for f in findings if f.severity == "CRITICAL" and "skip" in f.pattern_id.lower()]
        assert len(critical) >= 1, "#367: missing test-master should be CRITICAL step_skipping"

    def test_batch_mode_not_checked(self):
        """Events without full pipeline indicator skip ordering checks."""
        # Single agent invocation - not a full pipeline
        events = [_make_event(subagent_type="implementer")]
        findings = validate_step_ordering(events)
        # Should not flag ordering for incomplete/batch pipelines
        assert not any(f.pattern_id == "step_ordering" for f in findings), (
            "#367: single-agent runs should not trigger ordering checks"
        )


class TestDetectHardGateOrdering:
    """Tests for detect_hard_gate_ordering function."""

    def test_step6_before_pytest_critical(self):
        """STEP 6 agents before any test_run is CRITICAL."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", timestamp=base.isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=1)).isoformat()),
            _make_event(tool="Bash", pipeline_action="test_run", timestamp=(base + timedelta(minutes=5)).isoformat()),
        ]
        findings = detect_hard_gate_ordering(events)
        assert len(findings) >= 1, "#367: step6 before pytest should produce findings"
        assert any(f.severity == "CRITICAL" for f in findings)

    def test_step6_after_pytest_passes(self):
        """STEP 6 agents after pytest produces no findings."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", timestamp=base.isoformat()),
            _make_event(tool="Bash", pipeline_action="test_run", timestamp=(base + timedelta(minutes=2)).isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=4)).isoformat()),
        ]
        findings = detect_hard_gate_ordering(events)
        assert len(findings) == 0, "#367: normal order should have no findings"

    def test_no_pytest_at_all(self):
        """No test_run but STEP 6 agents exist is CRITICAL."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", timestamp=base.isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=2)).isoformat()),
            _make_event(subagent_type="security-auditor", timestamp=(base + timedelta(minutes=3)).isoformat()),
        ]
        findings = detect_hard_gate_ordering(events)
        assert len(findings) >= 1, "#367: no pytest with step6 agents should be CRITICAL"
        assert any(f.severity == "CRITICAL" for f in findings)

    def test_pytest_failed_but_step6_ran(self):
        """Pytest failed (success=false) but STEP 6 ran is CRITICAL."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", timestamp=base.isoformat()),
            _make_event(tool="Bash", pipeline_action="test_run", timestamp=(base + timedelta(minutes=2)).isoformat(), success=False),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=4)).isoformat()),
        ]
        findings = detect_hard_gate_ordering(events)
        assert len(findings) >= 1, "#367: failed pytest + step6 should be CRITICAL"
        assert any(f.severity == "CRITICAL" for f in findings)


class TestDetectContextDropping:
    """Tests for detect_context_dropping function."""

    def test_low_ratio_flagged(self):
        """Prompt much smaller than prior result is WARNING."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher", timestamp=base.isoformat(), result_word_count=2000),
            _make_event(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat(), prompt_word_count=50, result_word_count=1000),
        ]
        findings = detect_context_dropping(events)
        assert len(findings) >= 1, "#367: 50/2000 ratio should flag context dropping"
        assert any(f.finding_type == "context_dropping" for f in findings)

    def test_high_ratio_passes(self):
        """Reasonable prompt/result ratio produces no findings."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher", timestamp=base.isoformat(), result_word_count=2000),
            _make_event(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat(), prompt_word_count=800, result_word_count=1000),
        ]
        findings = detect_context_dropping(events)
        assert len(findings) == 0, "#367: 800/2000 ratio should not flag"

    def test_missing_word_counts_skipped(self):
        """Events without word counts are gracefully skipped."""
        events = [
            _make_event(subagent_type="researcher", result_word_count=0),
            _make_event(subagent_type="planner", prompt_word_count=0),
        ]
        findings = detect_context_dropping(events)
        assert len(findings) == 0, "#367: zero word counts should be skipped"

    def test_threshold_configurable(self):
        """Custom threshold catches more cases."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher", timestamp=base.isoformat(), result_word_count=2000),
            _make_event(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat(), prompt_word_count=800, result_word_count=1000),
        ]
        # Default threshold 0.2 would pass (800/2000=0.4), but 0.5 should flag
        findings = detect_context_dropping(events, threshold=0.5)
        assert len(findings) >= 1, "#367: threshold=0.5 should catch 0.4 ratio"


class TestDetectParallelizationViolations:
    """Tests for detect_parallelization_violations function."""

    def test_sequential_agents_parallelized_critical(self):
        """test-master and implementer within 5s is CRITICAL."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="test-master", timestamp=base.isoformat()),
            _make_event(subagent_type="implementer", timestamp=(base + timedelta(seconds=3)).isoformat()),
        ]
        findings = detect_parallelization_violations(events)
        assert len(findings) >= 1, "#367: sequential agents parallelized should be CRITICAL"
        assert any(f.severity == "CRITICAL" for f in findings)

    def test_parallel_agents_serialized_info(self):
        """researcher-local and researcher >30s apart is INFO."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher-local", timestamp=base.isoformat()),
            _make_event(subagent_type="researcher", timestamp=(base + timedelta(seconds=45)).isoformat()),
        ]
        findings = detect_parallelization_violations(events)
        assert len(findings) >= 1, "#367: parallel agents serialized should produce finding"
        assert any(f.severity == "INFO" for f in findings)

    def test_correct_parallelization_passes(self):
        """Correct parallelization produces no findings."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher-local", timestamp=base.isoformat()),
            _make_event(subagent_type="researcher", timestamp=(base + timedelta(seconds=2)).isoformat()),
            _make_event(subagent_type="test-master", timestamp=(base + timedelta(minutes=5)).isoformat()),
            _make_event(subagent_type="implementer", timestamp=(base + timedelta(minutes=10)).isoformat()),
        ]
        findings = detect_parallelization_violations(events)
        assert len(findings) == 0, "#367: correct parallelization should have no findings"


class TestValidatePipelineIntent:
    """Tests for validate_pipeline_intent orchestrator function."""

    def test_clean_pipeline_no_findings(self, tmp_path):
        """Clean pipeline JSONL produces no findings."""
        log_file = tmp_path / "clean.jsonl"
        _write_clean_pipeline(log_file)
        findings = validate_pipeline_intent(log_file, session_id="test-session")
        assert len(findings) == 0, "#367: clean pipeline should have no findings"

    def test_multiple_violations_detected(self, tmp_path):
        """JSONL with multiple issues detects all of them."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        log_file = tmp_path / "bad.jsonl"
        lines = [
            # Implementer before planner (ordering violation)
            _make_jsonl_line(subagent_type="implementer", timestamp=base.isoformat()),
            _make_jsonl_line(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat()),
            # Reviewer before any pytest (hard gate violation)
            _make_jsonl_line(subagent_type="reviewer", timestamp=(base + timedelta(minutes=3)).isoformat()),
        ]
        log_file.write_text("\n".join(lines) + "\n")
        findings = validate_pipeline_intent(log_file, session_id="test-session")
        assert len(findings) >= 2, "#367: multiple violations should all be detected"


class TestDataStructures:
    """Tests for PipelineEvent and Finding dataclasses."""

    def test_pipeline_event_fields(self):
        """PipelineEvent has all required fields."""
        e = PipelineEvent(
            timestamp="2026-02-28T10:00:00+00:00",
            tool="Task",
            agent="main",
            subagent_type="researcher",
            pipeline_action="agent_invocation",
            prompt_word_count=500,
            result_word_count=2000,
        )
        assert e.timestamp == "2026-02-28T10:00:00+00:00"
        assert e.tool == "Task"
        assert e.subagent_type == "researcher"

    def test_finding_fields(self):
        """Finding has all required fields."""
        f = Finding(
            finding_type="step_ordering",
            severity="CRITICAL",
            pattern_id="implementer_before_planner",
            description="Implementer ran before planner",
            evidence=["timestamp1", "timestamp2"],
        )
        assert f.severity == "CRITICAL"
        assert f.finding_type == "step_ordering"
        assert len(f.evidence) == 2
