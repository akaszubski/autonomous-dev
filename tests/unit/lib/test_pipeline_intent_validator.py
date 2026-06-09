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
    MIN_DOC_SWEEP_WORDS,
    MIN_DOC_VERDICT_WORDS,
    PLANNER_EXEMPT_MODES,
    PipelineEvent,
    VALID_AGENT_TYPES,
    _correlate_invocation_completion,
    detect_batch_cia_skip,
    detect_cia_skip,
    detect_context_dropping,
    detect_doc_verdict_missing,
    detect_doc_verdict_shallow,
    detect_ghost_invocations,
    detect_hard_gate_ordering,
    detect_missing_security_review,
    detect_parallelization_violations,
    detect_progressive_compression,
    get_minimum_prompt_content,
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
    batch_issue_number: int = 0,
    session_id: str = "",
    pipeline_mode: str = "",
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
        batch_issue_number=batch_issue_number,
        session_id=session_id,
        pipeline_mode=pipeline_mode,
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
    pipeline_mode: str = "",
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
                "pipeline_mode": pipeline_mode,
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
                "pipeline_mode": pipeline_mode,
            },
            "output_summary": {"success": success},
            "session_id": session_id,
            "agent": agent,
        }
    return json.dumps(entry)


def _write_clean_pipeline(log_file: Path, session_id: str = "test-session") -> None:
    """Write a clean pipeline JSONL with correct ordering.

    Includes SubagentStop entries for doc-master (and other STEP 6 agents) so
    that detect_doc_verdict_missing can correlate invocations with completions
    without producing false positives. (Issue #562)
    """
    base = datetime(2026, 2, 28, 10, 0, 0)
    # Build a SubagentStop entry for doc-master (simulates real pipeline behavior)
    doc_master_completion = json.dumps({
        "timestamp": (base + timedelta(minutes=14)).isoformat(),
        "hook": "SubagentStop",
        "subagent_type": "doc-master",
        "duration_ms": 180000,
        "result_word_count": 200,
        "session_id": session_id,
        "success": True,
    })
    lines = [
        _make_jsonl_line(subagent_type="researcher-local", timestamp=(base).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="researcher", timestamp=(base + timedelta(seconds=2)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="test-master", timestamp=(base + timedelta(minutes=4)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="implementer", timestamp=(base + timedelta(minutes=6)).isoformat(), session_id=session_id),
        _make_jsonl_line(tool="Bash", pipeline_action="test_run", timestamp=(base + timedelta(minutes=8)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="reviewer", timestamp=(base + timedelta(minutes=10)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="security-auditor", timestamp=(base + timedelta(minutes=12)).isoformat(), session_id=session_id),
        _make_jsonl_line(subagent_type="doc-master", timestamp=(base + timedelta(minutes=10, seconds=4)).isoformat(), session_id=session_id),
        doc_master_completion,
        _make_jsonl_line(subagent_type="continuous-improvement-analyst", timestamp=(base + timedelta(minutes=16)).isoformat(), session_id=session_id),
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

    def test_missing_test_master_not_flagged_in_acceptance_first_mode(self):
        """Absence of test-master must NOT produce a CRITICAL finding.

        In acceptance-first mode (the default), test-master is intentionally skipped.
        Flagging it as CRITICAL is a false positive on every default pipeline run. (#518)
        """
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(subagent_type="researcher-local", timestamp=base.isoformat()),
            _make_event(subagent_type="planner", timestamp=(base + timedelta(minutes=2)).isoformat()),
            _make_event(subagent_type="implementer", timestamp=(base + timedelta(minutes=4)).isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=6)).isoformat()),
        ]
        findings = validate_step_ordering(events)
        test_master_findings = [
            f for f in findings if f.pattern_id == "step_skipping_test_master"
        ]
        assert len(test_master_findings) == 0, (
            "#518: test-master absence must not produce step_skipping_test_master finding "
            "in acceptance-first (default) mode"
        )

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


class TestDetectGhostInvocations:
    """Tests for detect_ghost_invocations function (Issue #442)."""

    def test_ghost_detected_fast_and_low_output(self):
        """Agent with duration <10s AND result_word_count <50 is a ghost."""
        events = [
            PipelineEvent(
                timestamp="2026-02-28T10:00:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="researcher",
                pipeline_action="agent_completion",
                duration_ms=5000,
                result_word_count=10,
            ),
        ]
        findings = detect_ghost_invocations(events)
        assert len(findings) == 1
        assert findings[0].finding_type == "ghost_invocation"
        assert findings[0].severity == "WARNING"
        assert "GHOST" in findings[0].description

    def test_no_ghost_when_duration_high(self):
        """Agent with duration >10s should not be flagged even with low output."""
        events = [
            PipelineEvent(
                timestamp="2026-02-28T10:00:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="researcher",
                pipeline_action="agent_completion",
                duration_ms=15000,
                result_word_count=10,
            ),
        ]
        findings = detect_ghost_invocations(events)
        assert len(findings) == 0

    def test_no_ghost_when_output_high(self):
        """Agent with result_word_count >50 should not be flagged even if fast."""
        events = [
            PipelineEvent(
                timestamp="2026-02-28T10:00:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="implementer",
                pipeline_action="agent_completion",
                duration_ms=5000,
                result_word_count=200,
            ),
        ]
        findings = detect_ghost_invocations(events)
        assert len(findings) == 0

    def test_ghost_skipped_when_duration_zero(self):
        """Agent with duration_ms=0 (not recorded) should not be flagged."""
        events = [
            PipelineEvent(
                timestamp="2026-02-28T10:00:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="researcher",
                pipeline_action="agent_completion",
                duration_ms=0,
                result_word_count=10,
            ),
        ]
        findings = detect_ghost_invocations(events)
        assert len(findings) == 0

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        events = [
            PipelineEvent(
                timestamp="2026-02-28T10:00:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="planner",
                pipeline_action="agent_completion",
                duration_ms=3000,
                result_word_count=30,
            ),
        ]
        # Default thresholds: 10000ms, 50 words -> this IS a ghost
        findings = detect_ghost_invocations(events)
        assert len(findings) == 1
        # Tighter thresholds: 2000ms, 20 words -> NOT a ghost
        findings = detect_ghost_invocations(events, max_duration_ms=2000, max_result_words=20)
        assert len(findings) == 0

    def test_invocation_events_not_flagged_as_ghost(self):
        """Invocation events (pipeline_action='agent_invocation') must NOT be
        flagged as ghost invocations. They always have result_word_count=0 and
        duration_ms=1 because the agent hasn't run yet. Issue #781."""
        events = [
            PipelineEvent(
                timestamp="2026-04-11T09:20:23+00:00",
                tool="Agent",
                agent="main",
                subagent_type="reviewer",
                pipeline_action="agent_invocation",
                duration_ms=1,
                result_word_count=0,
            ),
        ]
        findings = detect_ghost_invocations(events)
        assert len(findings) == 0, (
            "Invocation events should be filtered out — they always have "
            "duration_ms=1 and result_word_count=0 (Issue #781)"
        )

    def test_ghost_integrated_in_validate_pipeline_intent(self, tmp_path):
        """Ghost detection runs as part of validate_pipeline_intent.

        Uses agent_completion (not agent_invocation) since invocation events
        are filtered out by detect_ghost_invocations (Issue #781).
        """
        log_file = tmp_path / "ghost.jsonl"
        entry = {
            "timestamp": "2026-02-28T10:00:00+00:00",
            "hook": "SubagentStop",
            "subagent_type": "researcher",
            "duration_ms": 2000,
            "result_word_count": 5,
            "session_id": "test-session",
            "success": True,
        }
        log_file.write_text(json.dumps(entry) + "\n")
        findings = validate_pipeline_intent(log_file, session_id="test-session")
        ghost_findings = [f for f in findings if f.finding_type == "ghost_invocation"]
        assert len(ghost_findings) == 1


class TestSubagentStopParsing:
    """Tests for SubagentStop JSONL entry parsing."""

    def test_parse_subagent_stop_entry(self, tmp_path):
        """SubagentStop JSONL creates PipelineEvent with pipeline_action=agent_completion."""
        log_file = tmp_path / "session.jsonl"
        entry = {
            "timestamp": "2026-03-17T10:00:00+00:00",
            "hook": "SubagentStop",
            "subagent_type": "researcher",
            "duration_ms": 5000,
            "result_word_count": 150,
            "agent_transcript_path": "/Users/test/.claude/transcripts/abc.jsonl",
            "session_id": "test-session",
            "success": True,
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1
        e = events[0]
        assert e.pipeline_action == "agent_completion"
        assert e.subagent_type == "researcher"
        assert e.tool == "Agent"
        assert e.success is True

    def test_subagent_stop_duration_ms(self, tmp_path):
        """duration_ms is populated from SubagentStop entry."""
        log_file = tmp_path / "session.jsonl"
        entry = {
            "timestamp": "2026-03-17T10:05:00+00:00",
            "hook": "SubagentStop",
            "subagent_type": "implementer",
            "duration_ms": 120000,
            "result_word_count": 500,
            "session_id": "test-session",
            "success": True,
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1
        assert events[0].duration_ms == 120000

    def test_subagent_stop_with_transcript_path(self, tmp_path):
        """agent_transcript_path is populated on PipelineEvent."""
        log_file = tmp_path / "session.jsonl"
        entry = {
            "timestamp": "2026-03-17T10:10:00+00:00",
            "hook": "SubagentStop",
            "subagent_type": "planner",
            "duration_ms": 30000,
            "result_word_count": 200,
            "agent_transcript_path": "/Users/test/.claude/transcripts/planner.jsonl",
            "session_id": "test-session",
            "success": True,
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1
        assert events[0].agent_transcript_path == "/Users/test/.claude/transcripts/planner.jsonl"

    def test_ghost_detection_uses_subagent_stop(self, tmp_path):
        """detect_ghost_invocations works with SubagentStop events (agent_completion)."""
        log_file = tmp_path / "session.jsonl"
        entry = {
            "timestamp": "2026-03-17T10:00:00+00:00",
            "hook": "SubagentStop",
            "subagent_type": "researcher",
            "duration_ms": 3000,
            "result_word_count": 10,
            "session_id": "test-session",
            "success": True,
        }
        log_file.write_text(json.dumps(entry) + "\n")
        events = parse_session_logs(log_file)
        assert len(events) == 1
        # SubagentStop events have tool="Agent" and subagent_type set,
        # so ghost detection should pick them up
        findings = detect_ghost_invocations(events)
        assert len(findings) == 1
        assert findings[0].finding_type == "ghost_invocation"


class TestReviewerBeforeSecurityAuditor:
    """Tests for STEP 6 ordering: reviewer before security-auditor (#495, #498)."""

    def test_reviewer_before_security_auditor_no_finding(self):
        """Reviewer completing before security-auditor produces no ordering violation."""
        base = datetime(2026, 3, 19, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", timestamp=base.isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=10)).isoformat()),
            _make_event(subagent_type="security-auditor", timestamp=(base + timedelta(minutes=15)).isoformat()),
        ]
        findings = validate_step_ordering(events)
        ordering_findings = [f for f in findings if f.finding_type == "step_ordering"]
        assert len(ordering_findings) == 0, "reviewer then security-auditor is correct ordering"

    def test_security_auditor_before_reviewer_flagged(self):
        """Security-auditor running before reviewer is a CRITICAL step_ordering violation."""
        base = datetime(2026, 3, 19, 10, 0, 0)
        events = [
            _make_event(subagent_type="implementer", timestamp=base.isoformat()),
            _make_event(subagent_type="security-auditor", timestamp=(base + timedelta(minutes=10)).isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=15)).isoformat()),
        ]
        findings = validate_step_ordering(events)
        ordering_findings = [f for f in findings if f.finding_type == "step_ordering"]
        assert len(ordering_findings) >= 1, "security-auditor before reviewer should be flagged"
        assert any(f.severity == "CRITICAL" for f in ordering_findings)

    def test_reviewer_security_auditor_parallelized_flagged(self):
        """Reviewer and security-auditor launched within 5s is a parallelization violation."""
        base = datetime(2026, 3, 19, 10, 0, 0)
        events = [
            _make_event(subagent_type="reviewer", timestamp=base.isoformat()),
            _make_event(subagent_type="security-auditor", timestamp=(base + timedelta(seconds=2)).isoformat()),
        ]
        findings = detect_parallelization_violations(events)
        assert len(findings) >= 1, "reviewer+security-auditor within 5s should be flagged"
        assert any(
            f.finding_type == "parallelization_violation" and f.severity == "CRITICAL"
            for f in findings
        )


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
        assert f.recommended_action is None  # default is None
        f2 = Finding(
            finding_type="test",
            severity="INFO",
            pattern_id="test",
            description="test",
            recommended_action="Reload from agents/reviewer.md",
        )
        assert f2.recommended_action == "Reload from agents/reviewer.md"


class TestDetectDocVerdictMissing:
    """Tests for detect_doc_verdict_missing function (Issues #543, #562)."""

    def test_doc_master_with_completion_passes(self):
        """doc-master invocation paired with healthy completion produces NO findings."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                result_word_count=0,  # PostToolUse always 0
                success=True,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:02:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=200,  # SubagentStop has actual output
                success=True,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 0, "#562: healthy completion should produce no findings"

    def test_doc_master_no_completion_flagged(self):
        """doc-master invocation with no matching completion is flagged."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                result_word_count=0,
                success=True,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 1
        assert findings[0].finding_type == "doc_verdict_missing"
        assert findings[0].severity == "CRITICAL"
        assert "[DOC-VERDICT-MISSING]" in findings[0].description

    def test_doc_master_completion_low_output_flagged(self):
        """doc-master completion with very low word count is flagged."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                result_word_count=0,
                success=True,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:02:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=10,  # Below MIN_DOC_VERDICT_WORDS
                success=True,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 1
        assert findings[0].finding_type == "doc_verdict_missing"
        assert "[DOC-VERDICT-MISSING]" in findings[0].description

    def test_doc_master_completion_failed_flagged(self):
        """doc-master completion with success=False is flagged."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                result_word_count=0,
                success=True,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:02:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=200,
                success=False,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 1
        assert findings[0].finding_type == "doc_verdict_missing"
        assert "[DOC-VERDICT-MISSING]" in findings[0].description

    def test_no_doc_master_events_no_findings(self):
        """Events without doc-master produce no findings."""
        events = [
            _make_event(subagent_type="researcher", tool="Agent", result_word_count=500),
            _make_event(subagent_type="implementer", tool="Agent", result_word_count=1000),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 0

    def test_integrated_in_validate_pipeline_intent(self, tmp_path):
        """Verify detect_doc_verdict_missing works through validate_pipeline_intent.

        When a doc-master invocation has result_word_count=0 (PostToolUse) but
        a matching SubagentStop has result_word_count=200, no finding should be produced.
        This is the false positive that Issue #562 fixes.
        """
        log_file = tmp_path / "doc_missing.jsonl"
        # PostToolUse entry (invocation with result_word_count=0)
        invocation_entry = {
            "timestamp": "2026-03-22T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "doc-master",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 500,
            },
            "output_summary": {"success": True, "result_word_count": 0},
            "session_id": "test-session",
            "agent": "main",
        }
        # SubagentStop entry (completion with actual word count)
        completion_entry = {
            "timestamp": "2026-03-22T10:02:00+00:00",
            "hook": "SubagentStop",
            "subagent_type": "doc-master",
            "duration_ms": 30000,
            "result_word_count": 200,
            "session_id": "test-session",
            "success": True,
        }
        log_file.write_text(
            json.dumps(invocation_entry) + "\n" + json.dumps(completion_entry) + "\n"
        )
        findings = validate_pipeline_intent(log_file, session_id="test-session")
        doc_findings = [f for f in findings if f.finding_type == "doc_verdict_missing"]
        assert len(doc_findings) == 0, (
            "#562: doc-master with healthy SubagentStop should NOT produce false positive"
        )

    def test_invocation_only_no_completion_flagged_via_log(self, tmp_path):
        """Verify that an invocation-only log (no SubagentStop) is flagged."""
        log_file = tmp_path / "doc_missing_no_completion.jsonl"
        entry = {
            "timestamp": "2026-03-22T10:00:00+00:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "doc-master",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 500,
            },
            "output_summary": {"success": True, "result_word_count": 0},
            "session_id": "test-session",
            "agent": "main",
        }
        log_file.write_text(json.dumps(entry) + "\n")
        findings = validate_pipeline_intent(log_file, session_id="test-session")
        doc_findings = [f for f in findings if f.finding_type == "doc_verdict_missing"]
        assert len(doc_findings) == 1
        assert "[DOC-VERDICT-MISSING]" in doc_findings[0].description

    def test_correlation_failure_with_healthy_completion_no_false_positive(self):
        """Issue #650: correlation failure should NOT flag when a healthy completion exists.

        When the invocation and completion have timestamps > 600s apart (exceeding
        max_window_seconds), correlation fails and comp is None. But if a healthy
        doc-master completion event exists in the event list, the fallback check
        should suppress the false positive.
        """
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                result_word_count=0,
                success=True,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            # Completion event is 15 minutes later — exceeds 600s correlation window
            PipelineEvent(
                timestamp="2026-03-22T10:15:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=59,  # >= MIN_DOC_VERDICT_WORDS (30)
                success=True,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 0, (
            "#650: correlation failure with healthy completion should NOT produce "
            "false positive — fallback scan should suppress it"
        )

    def test_correlation_failure_without_healthy_completion_still_flags(self):
        """Issue #650: fallback should NOT suppress when no healthy completion exists.

        If correlation fails AND there is no healthy completion in the event list,
        the finding should still be emitted.
        """
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                result_word_count=0,
                success=True,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            # Completion event exists but has low word count — not healthy
            PipelineEvent(
                timestamp="2026-03-22T10:15:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=5,  # Below MIN_DOC_VERDICT_WORDS (30)
                success=True,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 1, (
            "#650: correlation failure with NO healthy completion should still flag"
        )
        assert findings[0].finding_type == "doc_verdict_missing"

    def test_correlation_failure_failed_completion_still_flags(self):
        """Issue #650: fallback should NOT suppress when completion has success=False."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                result_word_count=0,
                success=True,
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            # Completion has enough words but success=False — not healthy
            PipelineEvent(
                timestamp="2026-03-22T10:15:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=200,
                success=False,
            ),
        ]
        findings = detect_doc_verdict_missing(events)
        assert len(findings) == 1, (
            "#650: correlation failure with failed completion should still flag"
        )


class TestDetectDocVerdictShallow:
    """Tests for detect_doc_verdict_shallow function (Issue #672)."""

    def test_doc_master_shallow_output_flagged(self):
        """doc-master with 42 words (between 30 and 100) should produce WARNING finding."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-02-28T10:00:00+00:00",
                result_word_count=0,
                success=True,
            ),
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_completion",
                timestamp="2026-02-28T10:01:00+00:00",
                result_word_count=42,
                success=True,
            ),
        ]
        findings = detect_doc_verdict_shallow(events)
        assert len(findings) == 1
        assert findings[0].finding_type == "doc_verdict_shallow"
        assert findings[0].severity == "WARNING"
        assert findings[0].pattern_id == "doc_verdict_shallow"
        assert "[DOC-VERDICT-SHALLOW]" in findings[0].description
        assert "42" in findings[0].description
        assert str(MIN_DOC_SWEEP_WORDS) in findings[0].description

    def test_doc_master_sufficient_output_passes(self):
        """doc-master with 150 words (>= MIN_DOC_SWEEP_WORDS) should produce no finding."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-02-28T10:00:00+00:00",
                result_word_count=0,
                success=True,
            ),
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_completion",
                timestamp="2026-02-28T10:01:00+00:00",
                result_word_count=150,
                success=True,
            ),
        ]
        findings = detect_doc_verdict_shallow(events)
        assert len(findings) == 0

    def test_doc_master_below_min_not_shallow(self):
        """doc-master with 5 words (below MIN_DOC_VERDICT_WORDS) should NOT be flagged by shallow detector.

        This case is handled by detect_doc_verdict_missing instead.
        """
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-02-28T10:00:00+00:00",
                result_word_count=0,
                success=True,
            ),
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_completion",
                timestamp="2026-02-28T10:01:00+00:00",
                result_word_count=5,
                success=True,
            ),
        ]
        findings = detect_doc_verdict_shallow(events)
        assert len(findings) == 0

    def test_doc_master_failed_not_shallow(self):
        """doc-master with success=False should NOT be flagged by shallow detector."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-02-28T10:00:00+00:00",
                result_word_count=0,
                success=True,
            ),
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_completion",
                timestamp="2026-02-28T10:01:00+00:00",
                result_word_count=42,
                success=False,
            ),
        ]
        findings = detect_doc_verdict_shallow(events)
        assert len(findings) == 0

    def test_no_doc_master_events_no_findings(self):
        """No doc-master events should produce empty findings."""
        events = [
            _make_event(subagent_type="researcher", tool="Agent", result_word_count=500),
            _make_event(subagent_type="implementer", tool="Agent", result_word_count=1000),
        ]
        findings = detect_doc_verdict_shallow(events)
        assert len(findings) == 0


class TestDetectBatchCiaSkip:
    """Tests for detect_batch_cia_skip function (Issue #559)."""

    def _make_batch_event(
        self,
        subagent_type: str,
        issue_number: int,
        timestamp: str = "2026-03-25T10:00:00+00:00",
    ) -> PipelineEvent:
        """Helper to create a batch PipelineEvent with issue number."""
        return PipelineEvent(
            timestamp=timestamp,
            tool="Agent",
            agent="main",
            subagent_type=subagent_type,
            pipeline_action="agent_invocation",
            prompt_word_count=500,
            result_word_count=2000,
            success=True,
            batch_issue_number=issue_number,
        )

    def test_no_batch_events_returns_empty(self):
        """No batch events (batch_issue_number=0) should return no findings."""
        events = [
            _make_event(subagent_type="implementer"),
            _make_event(subagent_type="reviewer"),
        ]
        findings = detect_batch_cia_skip(events)
        assert findings == [], "#559: non-batch events should return empty"

    def test_all_issues_have_cia_returns_empty(self):
        """All batch issues with CIA invoked should return no findings."""
        events = [
            self._make_batch_event("implementer", 100, "2026-03-25T10:00:00+00:00"),
            self._make_batch_event("continuous-improvement-analyst", 100, "2026-03-25T10:05:00+00:00"),
            self._make_batch_event("implementer", 200, "2026-03-25T10:10:00+00:00"),
            self._make_batch_event("continuous-improvement-analyst", 200, "2026-03-25T10:15:00+00:00"),
        ]
        findings = detect_batch_cia_skip(events)
        assert findings == [], "#559: all issues have CIA, no findings"

    def test_last_issue_missing_cia_flagged(self):
        """Last issue missing CIA should be flagged as WARNING with batch_last_issue_cia_skip."""
        events = [
            self._make_batch_event("implementer", 100, "2026-03-25T10:00:00+00:00"),
            self._make_batch_event("continuous-improvement-analyst", 100, "2026-03-25T10:05:00+00:00"),
            self._make_batch_event("implementer", 200, "2026-03-25T10:10:00+00:00"),
            self._make_batch_event("reviewer", 200, "2026-03-25T10:15:00+00:00"),
            # Issue 200 has no CIA
        ]
        findings = detect_batch_cia_skip(events)
        assert len(findings) == 1, "#559: last issue missing CIA should produce one finding"
        assert findings[0].severity == "WARNING"
        assert findings[0].pattern_id == "batch_last_issue_cia_skip"
        assert "200" in findings[0].description
        assert "LAST ISSUE" in findings[0].description

    def test_middle_issue_missing_cia_flagged(self):
        """Non-last issue missing CIA should be flagged as INFO with batch_issue_cia_skip."""
        events = [
            self._make_batch_event("implementer", 100, "2026-03-25T10:00:00+00:00"),
            # Issue 100 has no CIA
            self._make_batch_event("implementer", 200, "2026-03-25T10:10:00+00:00"),
            self._make_batch_event("continuous-improvement-analyst", 200, "2026-03-25T10:15:00+00:00"),
        ]
        findings = detect_batch_cia_skip(events)
        assert len(findings) == 1, "#559: middle issue missing CIA should produce one finding"
        assert findings[0].severity == "INFO"
        assert findings[0].pattern_id == "batch_issue_cia_skip"
        assert "100" in findings[0].description

    def test_single_issue_batch_missing_cia(self):
        """Single-issue batch missing CIA should flag as WARNING (it is both first and last)."""
        events = [
            self._make_batch_event("implementer", 42, "2026-03-25T10:00:00+00:00"),
            self._make_batch_event("reviewer", 42, "2026-03-25T10:05:00+00:00"),
        ]
        findings = detect_batch_cia_skip(events)
        assert len(findings) == 1, "#559: single issue batch missing CIA"
        assert findings[0].severity == "WARNING"
        assert findings[0].pattern_id == "batch_last_issue_cia_skip"
        assert "42" in findings[0].description


class TestCorrelateInvocationCompletion:
    """Tests for _correlate_invocation_completion helper (Issue #562)."""

    def test_pairs_invocation_with_completion(self):
        """Basic pairing: invocation + completion of same type."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:02:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=200,
                success=True,
            ),
        ]
        pairs = _correlate_invocation_completion(events)
        assert len(pairs) == 1
        inv, comp = pairs[0]
        assert inv.pipeline_action == "agent_invocation"
        assert comp is not None
        assert comp.pipeline_action == "agent_completion"
        assert comp.result_word_count == 200

    def test_unmatched_invocation_returns_none(self):
        """Invocation with no matching completion returns (inv, None)."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-03-22T10:00:00+00:00",
            ),
        ]
        pairs = _correlate_invocation_completion(events)
        assert len(pairs) == 1
        inv, comp = pairs[0]
        assert inv.subagent_type == "doc-master"
        assert comp is None

    def test_multiple_agents_paired_correctly(self):
        """Multiple agent types are paired independently."""
        events = [
            _make_event(
                subagent_type="reviewer",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-03-22T10:00:01+00:00",
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:02:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="reviewer",
                pipeline_action="agent_completion",
                result_word_count=300,
                success=True,
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:03:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=200,
                success=True,
            ),
        ]
        pairs = _correlate_invocation_completion(events)
        assert len(pairs) == 2
        reviewer_pairs = [(i, c) for i, c in pairs if i.subagent_type == "reviewer"]
        doc_pairs = [(i, c) for i, c in pairs if i.subagent_type == "doc-master"]
        assert len(reviewer_pairs) == 1
        assert len(doc_pairs) == 1
        assert reviewer_pairs[0][1].result_word_count == 300
        assert doc_pairs[0][1].result_word_count == 200

    def test_completion_before_invocation_not_matched(self):
        """Completion that occurs before invocation should not be matched."""
        events = [
            PipelineEvent(
                timestamp="2026-03-22T09:58:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=200,
                success=True,
            ),
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-03-22T10:00:00+00:00",
            ),
        ]
        pairs = _correlate_invocation_completion(events)
        assert len(pairs) == 1
        inv, comp = pairs[0]
        assert comp is None  # The completion was BEFORE the invocation

    def test_multiple_invocations_of_same_type(self):
        """Multiple invocations of same agent type are each paired with distinct completions."""
        events = [
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-03-22T10:00:00+00:00",
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:02:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=150,
                success=True,
            ),
            _make_event(
                subagent_type="doc-master",
                tool="Agent",
                pipeline_action="agent_invocation",
                timestamp="2026-03-22T10:05:00+00:00",
            ),
            PipelineEvent(
                timestamp="2026-03-22T10:07:00+00:00",
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=180,
                success=True,
            ),
        ]
        pairs = _correlate_invocation_completion(events)
        assert len(pairs) == 2
        assert pairs[0][1].result_word_count == 150
        assert pairs[1][1].result_word_count == 180


class TestGetMinimumPromptContent:
    """Tests for get_minimum_prompt_content function (Issue #561)."""

    def test_valid_agent_type_returns_content(self, tmp_path):
        """Valid agent type with existing file returns first 200 words."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        content = " ".join(f"word{i}" for i in range(300))
        (agents_dir / "reviewer.md").write_text(content)
        result = get_minimum_prompt_content("reviewer", agents_dir)
        assert result is not None
        assert len(result.split()) == 200

    def test_invalid_agent_type_returns_none(self, tmp_path):
        """Invalid agent type (not in whitelist) returns None."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        result = get_minimum_prompt_content("../../etc/passwd", agents_dir)
        assert result is None

    def test_unknown_agent_type_returns_none(self, tmp_path):
        """Unknown agent type not in STEP_ORDER returns None."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        result = get_minimum_prompt_content("not-a-real-agent", agents_dir)
        assert result is None

    def test_missing_file_returns_none(self, tmp_path):
        """Valid agent type but missing file returns None."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        result = get_minimum_prompt_content("reviewer", agents_dir)
        assert result is None

    def test_empty_file_returns_none(self, tmp_path):
        """Valid agent type but empty file returns None."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "reviewer.md").write_text("")
        result = get_minimum_prompt_content("reviewer", agents_dir)
        assert result is None

    def test_short_file_returns_all_content(self, tmp_path):
        """File with fewer than 200 words returns all words."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        file_content = "This is a short agent prompt file."
        (agents_dir / "planner.md").write_text(file_content)
        result = get_minimum_prompt_content("planner", agents_dir)
        assert result == file_content


class TestSessionScopedOrdering:
    """Tests for session-scoped ordering checks (Issue #587).

    Validates that step_ordering and related checks operate per session
    to avoid false CRITICAL findings from cross-session event merging.
    """

    def test_cross_session_no_false_ordering_finding(self, tmp_path):
        """Two sessions with reversed ordering across sessions produce no false findings.

        Session A: planner at 10:00, implementer at 10:10 (correct)
        Session B: planner at 09:00, implementer at 09:10 (correct)
        Cross-session: B's implementer (09:10) < A's planner (10:00) — false positive if not scoped
        """
        log_file = tmp_path / "session.jsonl"
        lines = [
            # Session A — correct ordering
            _make_jsonl_line(subagent_type="planner", timestamp="2026-03-28T10:00:00+00:00", session_id="session-a"),
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T10:10:00+00:00", session_id="session-a"),
            # Session B — correct ordering, but earlier timestamps than session-a
            _make_jsonl_line(subagent_type="planner", timestamp="2026-03-28T09:00:00+00:00", session_id="session-b"),
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T09:10:00+00:00", session_id="session-b"),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        findings = validate_pipeline_intent(log_file)
        ordering_findings = [f for f in findings if f.finding_type == "step_ordering"]
        assert len(ordering_findings) == 0, (
            f"#587: Cross-session events must not produce false ordering findings. "
            f"Got: {ordering_findings}"
        )

    def test_single_session_ordering_still_detected(self, tmp_path):
        """A real ordering violation within one session is still detected.

        Single session with implementer before planner — should produce CRITICAL finding.
        """
        log_file = tmp_path / "session.jsonl"
        lines = [
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T10:00:00+00:00", session_id="session-x"),
            _make_jsonl_line(subagent_type="planner", timestamp="2026-03-28T10:10:00+00:00", session_id="session-x"),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        findings = validate_pipeline_intent(log_file)
        ordering_findings = [f for f in findings if f.finding_type == "step_ordering"]
        assert len(ordering_findings) > 0, (
            "#587: Intra-session ordering violation must still be detected"
        )
        critical = [f for f in ordering_findings if f.severity == "CRITICAL"]
        assert len(critical) > 0, "#587: Intra-session ordering violation must be CRITICAL"

    def test_subagent_stop_carries_session_id(self, tmp_path):
        """SubagentStop entries are parsed with session_id populated."""
        log_file = tmp_path / "session.jsonl"
        entry = {
            "timestamp": "2026-03-28T10:00:00+00:00",
            "hook": "SubagentStop",
            "session_id": "test-session-xyz",
            "subagent_type": "implementer",
            "duration_ms": 60000,
            "result_word_count": 500,
            "success": True,
        }
        log_file.write_text(json.dumps(entry) + "\n")

        events = parse_session_logs(log_file)
        completion_events = [e for e in events if e.pipeline_action == "agent_completion"]
        assert len(completion_events) == 1, "#587: SubagentStop should parse to agent_completion event"
        assert completion_events[0].session_id == "test-session-xyz", (
            "#587: SubagentStop event must carry session_id"
        )

    def test_empty_session_id_fallback(self, tmp_path):
        """Events without session_id are grouped together as a fallback group.

        Two events with empty session_id from different timestamps should still
        be checked as a group — if they have a real violation, it should be detected.
        """
        log_file = tmp_path / "session.jsonl"
        # These have no session_id — both go into the "" fallback group
        # Implementer before planner = real violation
        lines = [
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T10:00:00+00:00", session_id=""),
            _make_jsonl_line(subagent_type="planner", timestamp="2026-03-28T10:10:00+00:00", session_id=""),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        findings = validate_pipeline_intent(log_file)
        ordering_findings = [f for f in findings if f.finding_type == "step_ordering"]
        assert len(ordering_findings) > 0, (
            "#587: Events with empty session_id should be grouped together and violations detected"
        )

    def test_validate_pipeline_intent_multi_session(self, tmp_path):
        """Full integration test: multi-session log returns only per-session findings.

        Session A: correct pipeline ordering — no findings
        Session B: correct pipeline ordering — no findings
        Session C: implementer before planner (real violation) — CRITICAL finding
        Expected: exactly one session contributes ordering findings (session C only).
        """
        log_file = tmp_path / "daily.jsonl"
        # Session A — correct
        lines_a = [
            _make_jsonl_line(subagent_type="planner", timestamp="2026-03-28T08:00:00+00:00", session_id="session-a"),
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T08:20:00+00:00", session_id="session-a"),
        ]
        # Session B — correct
        lines_b = [
            _make_jsonl_line(subagent_type="planner", timestamp="2026-03-28T09:00:00+00:00", session_id="session-b"),
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T09:20:00+00:00", session_id="session-b"),
        ]
        # Session C — real violation
        lines_c = [
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T10:00:00+00:00", session_id="session-c"),
            _make_jsonl_line(subagent_type="planner", timestamp="2026-03-28T10:20:00+00:00", session_id="session-c"),
        ]
        log_file.write_text("\n".join(lines_a + lines_b + lines_c) + "\n")

        findings = validate_pipeline_intent(log_file)
        ordering_findings = [f for f in findings if f.finding_type == "step_ordering"]

        # Session C's violation is detected
        assert len(ordering_findings) >= 1, (
            "#587: Session C's real ordering violation must be detected"
        )

        # Verify the finding references implementer/planner — not cross-session artefacts
        violation_descriptions = " ".join(f.description for f in ordering_findings)
        assert "implementer" in violation_descriptions or "planner" in violation_descriptions, (
            "#587: Ordering finding description must reference the violating agents"
        )


# ---------------------------------------------------------------------------
# Regression tests for Issues #617, #615, #620
# ---------------------------------------------------------------------------

class TestParseTimestampMicroseconds:
    """Regression tests for Issue #617: _parse_timestamp fails on microsecond timestamps."""

    def test_timestamp_with_microseconds_and_z_suffix(self):
        """#617: Microsecond timestamp with Z suffix parses to datetime."""
        from pipeline_intent_validator import _parse_timestamp

        result = _parse_timestamp("2026-03-28T10:00:00.123456Z")
        assert result is not None, (
            "#617: Timestamp with microseconds + Z suffix must parse to datetime, got None"
        )
        assert result.microsecond == 123456

    def test_timestamp_with_microseconds_and_utc_offset(self):
        """#617: Microsecond timestamp with +00:00 offset parses to datetime."""
        from pipeline_intent_validator import _parse_timestamp

        result = _parse_timestamp("2026-03-28T10:00:00.123456+00:00")
        assert result is not None, (
            "#617: Timestamp with microseconds + +00:00 offset must parse to datetime, got None"
        )
        assert result.microsecond == 123456

    def test_timestamp_without_microseconds_still_works(self):
        """#617: Timestamps without microseconds continue to parse correctly."""
        from pipeline_intent_validator import _parse_timestamp

        result = _parse_timestamp("2026-03-28T10:00:00+00:00")
        assert result is not None
        assert result.microsecond == 0

    def test_timestamp_with_z_suffix_no_microseconds(self):
        """#617: Z-suffix timestamp without microseconds parses correctly."""
        from pipeline_intent_validator import _parse_timestamp

        result = _parse_timestamp("2026-03-28T10:00:00Z")
        assert result is not None
        assert result.microsecond == 0

    def test_seconds_between_uses_microsecond_timestamps(self):
        """#617: _seconds_between works when both timestamps have microseconds."""
        from pipeline_intent_validator import _seconds_between

        ts1 = "2026-03-28T10:00:00.000000Z"
        ts2 = "2026-03-28T10:00:02.500000Z"
        gap = _seconds_between(ts1, ts2)
        assert gap is not None, (
            "#617: _seconds_between must not return None for microsecond timestamps"
        )
        assert abs(gap - 2.5) < 0.001

    def test_event_correlation_works_with_microsecond_timestamps(self):
        """#617: Event correlation does not break when events use microsecond timestamps.

        Previously _parse_timestamp returned None for microsecond timestamps,
        causing _correlate_invocation_completion to skip all pairs.
        """
        base_ts = "2026-03-28T10:00:00.000000Z"
        comp_ts = "2026-03-28T10:01:30.123456Z"

        events = [
            _make_event(
                subagent_type="doc-master",
                pipeline_action="agent_invocation",
                timestamp=base_ts,
            ),
            PipelineEvent(
                timestamp=comp_ts,
                tool="Agent",
                agent="main",
                subagent_type="doc-master",
                pipeline_action="agent_completion",
                result_word_count=100,
                success=True,
                session_id="",
            ),
        ]

        from pipeline_intent_validator import _correlate_invocation_completion

        pairs = _correlate_invocation_completion(events)
        assert len(pairs) == 1
        inv, comp = pairs[0]
        assert comp is not None, (
            "#617: invocation must be paired with its completion when timestamps have microseconds"
        )


class TestParallelStep10Mode:
    """Regression tests for Issue #615: false positives in parallel STEP 10 mode."""

    def _make_parallel_step10_events(self, base_ts: str = "2026-03-28T10:05:00+00:00") -> list:
        """Build a valid pipeline where STEP 6 agents are launched at the same second."""
        from datetime import datetime, timezone, timedelta

        base = datetime.fromisoformat(base_ts)

        def ts(offset_secs: float) -> str:
            return (base + timedelta(seconds=offset_secs)).isoformat()

        return [
            _make_event(subagent_type="implementer", timestamp=ts(-300)),
            # Successful test run before STEP 6
            _make_event(
                subagent_type="",
                pipeline_action="test_run",
                tool="Bash",
                timestamp=ts(-60),
                success=True,
            ),
            # reviewer and security-auditor launched at nearly the same time (<5s apart)
            _make_event(subagent_type="reviewer", timestamp=ts(0)),
            _make_event(subagent_type="security-auditor", timestamp=ts(2)),
            _make_event(subagent_type="doc-master", timestamp=ts(1)),
        ]

    def test_no_false_positive_when_step6_parallel_within_window(self):
        """#615: reviewer/security-auditor launched within 5s should NOT generate CRITICAL ordering finding."""
        events = self._make_parallel_step10_events()
        findings = validate_step_ordering(events)
        ordering_findings = [
            f for f in findings
            if f.finding_type == "step_ordering"
            and "security-auditor" in f.description
            and "reviewer" in f.description
        ]
        assert len(ordering_findings) == 0, (
            f"#615: Parallel STEP 10 launch must not produce false-positive ordering findings. "
            f"Got: {[f.description for f in ordering_findings]}"
        )

    def test_is_parallel_step10_launch_true_within_window(self):
        """#615: _is_parallel_step10_launch returns True when STEP 6 agents start within window."""
        from pipeline_intent_validator import _is_parallel_step10_launch

        events = self._make_parallel_step10_events()
        assert _is_parallel_step10_launch(events) is True

    def test_is_parallel_step10_launch_false_when_sequential(self):
        """#615: _is_parallel_step10_launch returns False when STEP 6 agents start far apart."""
        from pipeline_intent_validator import _is_parallel_step10_launch
        from datetime import datetime, timezone, timedelta

        base = datetime.fromisoformat("2026-03-28T10:05:00+00:00")

        def ts(offset_secs: float) -> str:
            return (base + timedelta(seconds=offset_secs)).isoformat()

        events = [
            _make_event(subagent_type="reviewer", timestamp=ts(0)),
            # security-auditor starts 60 seconds later — not parallel
            _make_event(subagent_type="security-auditor", timestamp=ts(60)),
        ]
        assert _is_parallel_step10_launch(events) is False

    def test_still_flags_real_step6_after_sequential_launch(self):
        """#615: When STEP 6 agents are not in parallel, ordering violations are still flagged."""
        from datetime import datetime, timezone, timedelta

        base = datetime.fromisoformat("2026-03-28T10:05:00+00:00")

        def ts(offset_secs: float) -> str:
            return (base + timedelta(seconds=offset_secs)).isoformat()

        events = [
            # security-auditor started BEFORE reviewer (60s before), NOT in parallel
            _make_event(subagent_type="security-auditor", timestamp=ts(0)),
            _make_event(subagent_type="reviewer", timestamp=ts(60)),
        ]
        findings = validate_step_ordering(events)
        ordering_findings = [f for f in findings if f.finding_type == "step_ordering"]
        # Should flag that security-auditor ran before reviewer when gap > window
        # (sequential mode — the ordering check applies)
        # Note: this pair IS in SEQUENTIAL_REQUIRED as ("reviewer", "security-auditor")
        assert len(ordering_findings) >= 1, (
            "#615: Non-parallel STEP 6 ordering violation must still be flagged"
        )


class TestRawBashPytestDetection:
    """Regression tests for Issue #620: raw Bash pytest commands not detected."""

    def _make_raw_pytest_bash_jsonl(self, timestamp: str, success: bool = True) -> str:
        """Create a raw PreToolUse Bash entry with pytest in the command (no pipeline_action)."""
        entry = {
            "timestamp": timestamp,
            "tool": "Bash",
            "input_summary": {
                "command": "python -m pytest tests/ -v --tb=short --no-cov",
                # No pipeline_action key — this is a raw PreToolUse Bash entry
            },
            "output_summary": {"success": success},
            "session_id": "test-session",
            "agent": "implementer",
        }
        return json.dumps(entry)

    def test_raw_pytest_bash_counts_as_test_run(self, tmp_path):
        """#620: Raw Bash entry with pytest command is recognised as a test_run event."""
        log_file = tmp_path / "session.jsonl"
        lines = [
            # Implementer invocation
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T10:00:00+00:00"),
            # Raw Bash pytest (no pipeline_action)
            self._make_raw_pytest_bash_jsonl("2026-03-28T10:05:00+00:00", success=True),
            # Reviewer after pytest
            _make_jsonl_line(subagent_type="reviewer", timestamp="2026-03-28T10:10:00+00:00"),
            _make_jsonl_line(subagent_type="security-auditor", timestamp="2026-03-28T10:10:02+00:00"),
            _make_jsonl_line(subagent_type="doc-master", timestamp="2026-03-28T10:10:01+00:00"),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = parse_session_logs(log_file)
        test_run_events = [e for e in events if e.pipeline_action == "test_run"]
        assert len(test_run_events) >= 1, (
            "#620: Raw Bash entry with pytest command must be parsed as a test_run event"
        )

    def test_no_hard_gate_false_positive_with_raw_pytest(self, tmp_path):
        """#620: detect_hard_gate_ordering must not flag bypass when pytest ran via raw Bash."""
        log_file = tmp_path / "session.jsonl"
        lines = [
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T10:00:00+00:00"),
            # Raw Bash pytest — no pipeline_action
            self._make_raw_pytest_bash_jsonl("2026-03-28T10:05:00+00:00", success=True),
            # Reviewer + security-auditor + doc-master in parallel after pytest passes
            _make_jsonl_line(subagent_type="reviewer", timestamp="2026-03-28T10:10:00+00:00"),
            _make_jsonl_line(subagent_type="security-auditor", timestamp="2026-03-28T10:10:02+00:00"),
            _make_jsonl_line(subagent_type="doc-master", timestamp="2026-03-28T10:10:01+00:00"),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = parse_session_logs(log_file)
        findings = detect_hard_gate_ordering(events)
        hard_gate_findings = [f for f in findings if f.finding_type == "hard_gate_ordering"]
        assert len(hard_gate_findings) == 0, (
            f"#620: No hard gate violation when pytest ran via raw Bash. "
            f"Got findings: {[f.description for f in hard_gate_findings]}"
        )

    def test_hard_gate_bypass_still_detected_without_any_pytest(self, tmp_path):
        """#620: Hard gate bypass is still detected when no pytest at all (neither raw nor tagged)."""
        log_file = tmp_path / "session.jsonl"
        lines = [
            _make_jsonl_line(subagent_type="implementer", timestamp="2026-03-28T10:00:00+00:00"),
            # No pytest at all
            _make_jsonl_line(subagent_type="reviewer", timestamp="2026-03-28T10:10:00+00:00"),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = parse_session_logs(log_file)
        findings = detect_hard_gate_ordering(events)
        hard_gate_findings = [f for f in findings if f.finding_type == "hard_gate_ordering"]
        assert len(hard_gate_findings) >= 1, (
            "#620: Hard gate bypass must be detected when no pytest ran at all"
        )

    def test_raw_bash_without_pytest_not_treated_as_test_run(self, tmp_path):
        """#620: Raw Bash entry without pytest in command is NOT a test_run event."""
        log_file = tmp_path / "session.jsonl"
        # Bash entry with a different command
        entry = {
            "timestamp": "2026-03-28T10:05:00+00:00",
            "tool": "Bash",
            "input_summary": {"command": "git status"},
            "output_summary": {"success": True},
            "session_id": "test-session",
            "agent": "main",
        }
        log_file.write_text(json.dumps(entry) + "\n")

        events = parse_session_logs(log_file)
        test_run_events = [e for e in events if e.pipeline_action == "test_run"]
        assert len(test_run_events) == 0, (
            "#620: 'git status' Bash entry must not be treated as a test_run event"
        )


class TestPublicTimestampAPI:
    """Tests for public parse_timestamp and seconds_between aliases (Issue #621)."""

    def test_parse_timestamp_public_api(self):
        """parse_timestamp is importable and returns same result as _parse_timestamp."""
        from pipeline_intent_validator import parse_timestamp, _parse_timestamp

        ts = "2026-03-01T10:00:00+00:00"
        assert parse_timestamp(ts) == _parse_timestamp(ts)
        assert parse_timestamp(ts) is not None

    def test_seconds_between_public_api(self):
        """seconds_between is importable and returns same result as _seconds_between."""
        from pipeline_intent_validator import seconds_between, _seconds_between

        ts1 = "2026-03-01T10:00:00+00:00"
        ts2 = "2026-03-01T10:01:30+00:00"
        assert seconds_between(ts1, ts2) == _seconds_between(ts1, ts2)
        assert seconds_between(ts1, ts2) == 90.0

    def test_parse_timestamp_public_with_microseconds(self):
        """parse_timestamp handles microsecond timestamps."""
        from pipeline_intent_validator import parse_timestamp

        result = parse_timestamp("2026-03-01T10:00:00.123456+00:00")
        assert result is not None


class TestDetectCiaSkip:
    """Tests for detect_cia_skip function (Issue #667)."""

    def test_full_pipeline_missing_cia_flagged(self):
        """Full pipeline (4+ core agents) missing CIA should produce WARNING finding."""
        events = [
            _make_event(subagent_type="planner", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:00:00+00:00"),
            _make_event(subagent_type="implementer", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:05:00+00:00"),
            _make_event(subagent_type="reviewer", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:10:00+00:00"),
            _make_event(subagent_type="security-auditor", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:15:00+00:00"),
            _make_event(subagent_type="doc-master", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:20:00+00:00"),
        ]
        findings = detect_cia_skip(events)
        assert len(findings) == 1, "#667: full pipeline missing CIA should produce one finding"
        assert findings[0].severity == "WARNING"
        assert findings[0].pattern_id == "single_pipeline_cia_skip"
        assert findings[0].finding_type == "cia_skip"
        assert "[INCOMPLETE]" in findings[0].description
        assert "continuous-improvement-analyst" in findings[0].description

    def test_full_pipeline_with_cia_passes(self):
        """Full pipeline with CIA invoked should produce no findings."""
        events = [
            _make_event(subagent_type="planner", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:00:00+00:00"),
            _make_event(subagent_type="implementer", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:05:00+00:00"),
            _make_event(subagent_type="reviewer", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:10:00+00:00"),
            _make_event(subagent_type="security-auditor", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:15:00+00:00"),
            _make_event(subagent_type="continuous-improvement-analyst", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:20:00+00:00"),
        ]
        findings = detect_cia_skip(events)
        assert findings == [], "#667: full pipeline with CIA should have no findings"

    def test_partial_pipeline_missing_cia_not_flagged(self):
        """Partial pipeline (< 3 core agents) missing CIA should not be flagged."""
        events = [
            _make_event(subagent_type="implementer", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:00:00+00:00"),
            _make_event(subagent_type="reviewer", tool="Agent",
                        pipeline_action="agent_invocation",
                        timestamp="2026-03-25T10:05:00+00:00"),
        ]
        findings = detect_cia_skip(events)
        assert findings == [], "#667: partial pipeline should not flag missing CIA"

    def test_batch_events_skipped(self):
        """Events with batch_issue_number > 0 should be skipped (handled by detect_batch_cia_skip)."""
        events = [
            _make_event(subagent_type="planner", tool="Agent",
                        pipeline_action="agent_invocation",
                        batch_issue_number=42,
                        timestamp="2026-03-25T10:00:00+00:00"),
            _make_event(subagent_type="implementer", tool="Agent",
                        pipeline_action="agent_invocation",
                        batch_issue_number=42,
                        timestamp="2026-03-25T10:05:00+00:00"),
            _make_event(subagent_type="reviewer", tool="Agent",
                        pipeline_action="agent_invocation",
                        batch_issue_number=42,
                        timestamp="2026-03-25T10:10:00+00:00"),
            _make_event(subagent_type="security-auditor", tool="Agent",
                        pipeline_action="agent_invocation",
                        batch_issue_number=42,
                        timestamp="2026-03-25T10:15:00+00:00"),
        ]
        findings = detect_cia_skip(events)
        assert findings == [], "#667: batch events should be skipped"

    def test_no_agent_events_no_findings(self):
        """Empty or non-agent events should produce no findings."""
        # Empty list
        assert detect_cia_skip([]) == [], "#667: empty events should return empty"

        # Non-agent events (pipeline_action not agent_invocation/agent_completion)
        events = [
            _make_event(subagent_type="implementer", tool="Agent",
                        pipeline_action="step_start",
                        timestamp="2026-03-25T10:00:00+00:00"),
        ]
        findings = detect_cia_skip(events)
        assert findings == [], "#667: non-agent events should return empty"

    def test_agent_completion_events_also_detected(self):
        """agent_completion events should also be used to build the agents set."""
        events = [
            _make_event(subagent_type="planner", tool="Agent",
                        pipeline_action="agent_completion",
                        timestamp="2026-03-25T10:00:00+00:00"),
            _make_event(subagent_type="implementer", tool="Agent",
                        pipeline_action="agent_completion",
                        timestamp="2026-03-25T10:05:00+00:00"),
            _make_event(subagent_type="reviewer", tool="Agent",
                        pipeline_action="agent_completion",
                        timestamp="2026-03-25T10:10:00+00:00"),
            _make_event(subagent_type="security-auditor", tool="Agent",
                        pipeline_action="agent_completion",
                        timestamp="2026-03-25T10:15:00+00:00"),
        ]
        findings = detect_cia_skip(events)
        assert len(findings) == 1, "#667: agent_completion events should also trigger detection"
        assert findings[0].pattern_id == "single_pipeline_cia_skip"


# ---------------------------------------------------------------------------
# Regression: #680 — validate_step_ordering false CRITICAL in mixed-mode batches
# ---------------------------------------------------------------------------
class TestStepOrderingMixedBatch:
    """Regression tests for Issue #680.

    When a batch mixes --fix mode (implementer-only, no planner/researcher) with
    full-pipeline issues, cross-issue comparisons must NOT produce false CRITICAL
    ordering violations.
    """

    def test_mixed_mode_batch_no_false_critical(self):
        """--fix issue runs implementer first, full issue runs planner later.

        Without the fix, this produces a false CRITICAL:
        'implementer ran before planner (expected planner first)'.
        """
        events = [
            # Issue #100 (--fix mode): implementer only, runs first
            _make_event(
                subagent_type="implementer",
                timestamp="2026-03-25T10:00:00+00:00",
                batch_issue_number=100,
            ),
            # Issue #101 (full pipeline): planner runs after --fix issue
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:05:00+00:00",
                batch_issue_number=101,
            ),
            _make_event(
                subagent_type="implementer",
                timestamp="2026-03-25T10:10:00+00:00",
                batch_issue_number=101,
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) == 0, (
            "#680: Mixed-mode batch should NOT produce false CRITICAL ordering violations"
        )

    def test_mixed_mode_batch_with_researcher_no_false_critical(self):
        """--fix issue (no researcher) runs implementer, full issue runs researcher later."""
        events = [
            # Issue #200 (--fix mode): implementer only
            _make_event(
                subagent_type="implementer",
                timestamp="2026-03-25T10:00:00+00:00",
                batch_issue_number=200,
            ),
            # Issue #201 (full pipeline): researcher → planner → implementer
            _make_event(
                subagent_type="researcher",
                timestamp="2026-03-25T10:05:00+00:00",
                batch_issue_number=201,
            ),
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:10:00+00:00",
                batch_issue_number=201,
            ),
            _make_event(
                subagent_type="implementer",
                timestamp="2026-03-25T10:15:00+00:00",
                batch_issue_number=201,
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) == 0, (
            "#680: Mixed-mode batch with researcher should NOT false-positive"
        )

    def test_within_issue_ordering_still_detected(self):
        """Real ordering violation WITHIN a single batch issue is still caught."""
        events = [
            # Issue #300: implementer runs BEFORE planner (real violation)
            _make_event(
                subagent_type="implementer",
                timestamp="2026-03-25T10:00:00+00:00",
                batch_issue_number=300,
            ),
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:05:00+00:00",
                batch_issue_number=300,
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) >= 1, (
            "#680: Within-issue ordering violations must still be detected"
        )

    def test_non_batch_ordering_still_works(self):
        """Non-batch sessions (batch_issue_number=0) still check ordering normally."""
        events = [
            _make_event(
                subagent_type="implementer",
                timestamp="2026-03-25T10:00:00+00:00",
                batch_issue_number=0,
            ),
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:05:00+00:00",
                batch_issue_number=0,
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) >= 1, (
            "Non-batch ordering violations must still be detected"
        )


# ---------------------------------------------------------------------------
# Regression: #681 — detect_context_dropping false positives in mixed-mode batches
# ---------------------------------------------------------------------------
class TestContextDroppingMixedBatch:
    """Regression tests for Issue #681.

    Cross-issue agent comparisons (reviewer result from issue N -> researcher
    prompt from issue N+1) must NOT produce false context-dropping warnings.
    """

    def test_cross_issue_no_false_positive(self):
        """Reviewer result from issue N, researcher prompt from issue N+1.

        Without the fix, the small researcher prompt relative to the large
        reviewer result triggers a false 'context dropping' warning.
        """
        events = [
            # Issue #100: reviewer produces large result
            _make_event(
                subagent_type="reviewer",
                timestamp="2026-03-25T10:00:00+00:00",
                result_word_count=5000,
                prompt_word_count=1000,
                batch_issue_number=100,
            ),
            # Issue #101: researcher starts with small prompt (normal for new issue)
            _make_event(
                subagent_type="researcher",
                timestamp="2026-03-25T10:05:00+00:00",
                prompt_word_count=200,
                result_word_count=3000,
                batch_issue_number=101,
            ),
        ]
        findings = detect_context_dropping(events)
        assert len(findings) == 0, (
            "#681: Cross-issue comparisons should NOT trigger context dropping"
        )

    def test_within_issue_context_dropping_still_detected(self):
        """Real context dropping WITHIN a single batch issue is still caught."""
        events = [
            # Issue #100: researcher produces large result
            _make_event(
                subagent_type="researcher",
                timestamp="2026-03-25T10:00:00+00:00",
                result_word_count=5000,
                prompt_word_count=1000,
                batch_issue_number=100,
            ),
            # Issue #100: planner gets tiny prompt (real context drop)
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:05:00+00:00",
                prompt_word_count=200,
                result_word_count=3000,
                batch_issue_number=100,
            ),
        ]
        findings = detect_context_dropping(events)
        assert len(findings) >= 1, (
            "#681: Within-issue context dropping must still be detected"
        )

    def test_non_batch_context_dropping_still_works(self):
        """Non-batch sessions still detect context dropping normally."""
        events = [
            _make_event(
                subagent_type="researcher",
                timestamp="2026-03-25T10:00:00+00:00",
                result_word_count=5000,
                prompt_word_count=1000,
                batch_issue_number=0,
            ),
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:05:00+00:00",
                prompt_word_count=200,
                result_word_count=3000,
                batch_issue_number=0,
            ),
        ]
        findings = detect_context_dropping(events)
        assert len(findings) >= 1, (
            "Non-batch context dropping must still be detected"
        )

    def test_multiple_issues_only_within_issue_flagged(self):
        """With 3 issues, only within-issue drops are flagged, not cross-issue."""
        events = [
            # Issue #100: normal
            _make_event(
                subagent_type="researcher",
                timestamp="2026-03-25T10:00:00+00:00",
                result_word_count=5000,
                prompt_word_count=1000,
                batch_issue_number=100,
            ),
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:01:00+00:00",
                prompt_word_count=4000,
                result_word_count=3000,
                batch_issue_number=100,
            ),
            # Issue #101: has a real context drop within it
            _make_event(
                subagent_type="researcher",
                timestamp="2026-03-25T10:05:00+00:00",
                result_word_count=8000,
                prompt_word_count=1000,
                batch_issue_number=101,
            ),
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:06:00+00:00",
                prompt_word_count=100,
                result_word_count=2000,
                batch_issue_number=101,
            ),
            # Issue #102: normal
            _make_event(
                subagent_type="researcher",
                timestamp="2026-03-25T10:10:00+00:00",
                result_word_count=4000,
                prompt_word_count=1000,
                batch_issue_number=102,
            ),
            _make_event(
                subagent_type="planner",
                timestamp="2026-03-25T10:11:00+00:00",
                prompt_word_count=3500,
                result_word_count=2000,
                batch_issue_number=102,
            ),
        ]
        findings = detect_context_dropping(events)
        # Only issue #101 should have a context drop (100/8000 = 1.25%)
        assert len(findings) == 1, (
            "#681: Only within-issue context drops should be flagged"
        )
        assert "planner" in findings[0].description


def _make_write_jsonl_line(
    file_path: str,
    tool: str = "Write",
    session_id: str = "test-session",
    timestamp: str = "2026-02-28T10:05:00+00:00",
) -> str:
    """Helper to create a Write/Edit JSONL log entry for security review tests."""
    entry = {
        "timestamp": timestamp,
        "tool": tool,
        "input_summary": {
            "file_path": file_path,
        },
        "output_summary": {"success": True},
        "session_id": session_id,
        "agent": "main",
    }
    return json.dumps(entry)


class TestFixModeStepOrdering:
    """Tests for fix-mode planner exemption (Issue #788)."""

    def test_fix_mode_no_planner_required(self):
        """Fix-mode events with implementer but no planner produce no CRITICAL findings.

        Regression test for Issue #788: pipeline_intent_validator required planner
        in --fix mode, but fix mode intentionally skips planning.
        """
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
                pipeline_mode="fix",
            ),
            _make_event(
                subagent_type="reviewer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
                pipeline_mode="fix",
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) == 0, (
            "#788: fix mode should not require planner before implementer"
        )

    def test_fix_mode_batch_no_planner_required(self):
        """Batch fix-mode (--fix) events produce no CRITICAL planner findings."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
                pipeline_mode="--fix",
                batch_issue_number=100,
            ),
            _make_event(
                subagent_type="reviewer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
                pipeline_mode="--fix",
                batch_issue_number=100,
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) == 0, (
            "#788: batch --fix mode should not require planner"
        )

    def test_full_mode_requires_planner_before_implementer(self):
        """Full-mode events with implementer before planner produce CRITICAL finding."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
            ),
            _make_event(
                subagent_type="planner",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) >= 1, (
            "Full mode must enforce planner before implementer"
        )

    def test_full_mode_correct_ordering_no_findings(self):
        """Full-mode events with correct ordering produce no findings."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(
                subagent_type="planner",
                timestamp=(base).isoformat(),
            ),
            _make_event(
                subagent_type="implementer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
            ),
            _make_event(
                subagent_type="reviewer",
                timestamp=(base + timedelta(minutes=10)).isoformat(),
            ),
        ]
        findings = validate_step_ordering(events)
        assert len(findings) == 0, (
            "Correct ordering should produce no findings"
        )

    def test_unknown_mode_defaults_to_full(self):
        """Empty pipeline_mode defaults to full enforcement (fail-safe)."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
                pipeline_mode="",
            ),
            _make_event(
                subagent_type="planner",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
                pipeline_mode="",
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) >= 1, (
            "Empty pipeline_mode must default to full enforcement"
        )

    def test_fix_mode_still_requires_implementer_before_reviewer(self):
        """Fix mode only exempts planner — other ordering rules still apply."""
        base = datetime(2026, 2, 28, 10, 0, 0)
        events = [
            _make_event(
                subagent_type="reviewer",
                timestamp=(base).isoformat(),
                pipeline_mode="fix",
            ),
            _make_event(
                subagent_type="implementer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
                pipeline_mode="fix",
            ),
        ]
        findings = validate_step_ordering(events)
        critical_findings = [f for f in findings if f.severity == "CRITICAL"]
        assert len(critical_findings) >= 1, (
            "#788: fix mode must still enforce implementer before reviewer"
        )


class TestMissingSecurityReview:
    """Tests for security-auditor requirement when security files modified (Issue #798)."""

    def test_hooks_file_changed_without_auditor(self, tmp_path):
        """Write to hooks/ without security-auditor produces WARNING finding.

        Regression test for Issue #798: security-sensitive file changes went
        unreviewed in fix mode.
        """
        log_file = tmp_path / "session.jsonl"
        base = datetime(2026, 2, 28, 10, 0, 0)
        lines = [
            _make_jsonl_line(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
            ),
            _make_write_jsonl_line(
                "plugins/autonomous-dev/hooks/foo.py",
                timestamp=(base + timedelta(minutes=2)).isoformat(),
            ),
            _make_jsonl_line(
                subagent_type="reviewer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
            ),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = [
            _make_event(subagent_type="implementer", timestamp=(base).isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=5)).isoformat()),
        ]

        findings = detect_missing_security_review(log_file, events)
        assert len(findings) == 1, "#798: hooks/ change without security-auditor should warn"
        assert findings[0].pattern_id == "missing_security_review"
        assert findings[0].severity == "WARNING"

    def test_hooks_file_changed_with_auditor(self, tmp_path):
        """Write to hooks/ with security-auditor present produces no findings."""
        log_file = tmp_path / "session.jsonl"
        base = datetime(2026, 2, 28, 10, 0, 0)
        lines = [
            _make_jsonl_line(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
            ),
            _make_write_jsonl_line(
                "plugins/autonomous-dev/hooks/foo.py",
                timestamp=(base + timedelta(minutes=2)).isoformat(),
            ),
            _make_jsonl_line(
                subagent_type="security-auditor",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
            ),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = [
            _make_event(subagent_type="implementer", timestamp=(base).isoformat()),
            _make_event(subagent_type="security-auditor", timestamp=(base + timedelta(minutes=5)).isoformat()),
        ]

        findings = detect_missing_security_review(log_file, events)
        assert len(findings) == 0, "No warning when security-auditor is present"

    def test_non_security_file_no_warning(self, tmp_path):
        """Write to non-security file produces no findings even without auditor."""
        log_file = tmp_path / "session.jsonl"
        base = datetime(2026, 2, 28, 10, 0, 0)
        lines = [
            _make_jsonl_line(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
            ),
            _make_write_jsonl_line(
                "docs/readme.md",
                timestamp=(base + timedelta(minutes=2)).isoformat(),
            ),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = [
            _make_event(subagent_type="implementer", timestamp=(base).isoformat()),
        ]

        findings = detect_missing_security_review(log_file, events)
        assert len(findings) == 0, "Non-security files should not trigger warning"

    def test_test_file_modifying_hooks_no_warning(self, tmp_path):
        """Write to tests/unit/hooks/ does not trigger security warning."""
        log_file = tmp_path / "session.jsonl"
        base = datetime(2026, 2, 28, 10, 0, 0)
        lines = [
            _make_jsonl_line(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
            ),
            _make_write_jsonl_line(
                "tests/unit/hooks/test_foo.py",
                timestamp=(base + timedelta(minutes=2)).isoformat(),
            ),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = [
            _make_event(subagent_type="implementer", timestamp=(base).isoformat()),
        ]

        findings = detect_missing_security_review(log_file, events)
        assert len(findings) == 0, "Test files should be excluded from security check"

    def test_fix_mode_security_file_triggers_warning(self, tmp_path):
        """Fix-mode pipeline with hooks/ change and no security-auditor warns.

        Regression test for Issue #798: fix mode did not require security-auditor
        when hook files were changed.
        """
        log_file = tmp_path / "session.jsonl"
        base = datetime(2026, 2, 28, 10, 0, 0)
        lines = [
            _make_jsonl_line(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
                pipeline_mode="--fix",
            ),
            _make_write_jsonl_line(
                "plugins/autonomous-dev/hooks/unified_pre_tool.py",
                timestamp=(base + timedelta(minutes=2)).isoformat(),
            ),
            _make_jsonl_line(
                subagent_type="reviewer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
                pipeline_mode="--fix",
            ),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = [
            _make_event(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
                pipeline_mode="--fix",
            ),
            _make_event(
                subagent_type="reviewer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
                pipeline_mode="--fix",
            ),
        ]

        findings = detect_missing_security_review(log_file, events)
        assert len(findings) == 1, "#798: fix mode with hooks/ change must warn"
        assert findings[0].pattern_id == "missing_security_review"

    def test_absolute_path_tests_exclusion(self, tmp_path):
        """Absolute-path test files under tests/ must be excluded from security review.

        Regression test for Issue #1088 (F2): JSONL activity logs record absolute
        file paths (e.g. /Users/foo/repo/tests/unit/hooks/test_x.py). A bare
        ``startswith("tests/")`` check silently misses these, producing
        false-positive missing_security_review warnings on every test edit.
        """
        log_file = tmp_path / "session.jsonl"
        base = datetime(2026, 2, 28, 10, 0, 0)
        # Use an absolute path under tests/ — what real JSONL logs contain.
        abs_test_path = str(tmp_path / "repo" / "tests" / "unit" / "hooks" / "test_conversation_archiver.py")
        lines = [
            _make_jsonl_line(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
            ),
            _make_write_jsonl_line(
                abs_test_path,
                timestamp=(base + timedelta(minutes=2)).isoformat(),
            ),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = [
            _make_event(subagent_type="implementer", timestamp=(base).isoformat()),
        ]

        findings = detect_missing_security_review(log_file, events)
        assert len(findings) == 0, (
            "#1088 F2: absolute-path test files must be excluded. "
            f"Got findings: {[f.description for f in findings]}"
        )

    def test_absolute_path_non_test_file_still_flags(self, tmp_path):
        """Absolute-path non-test security file must still trigger the warning.

        Companion to test_absolute_path_tests_exclusion — proves the fix narrows
        the exclusion to test paths only, not all absolute paths. Issue #1088 (F2).
        """
        log_file = tmp_path / "session.jsonl"
        base = datetime(2026, 2, 28, 10, 0, 0)
        # Absolute path under hooks/ (NOT under tests/) — must still flag.
        abs_hook_path = str(tmp_path / "repo" / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py")
        lines = [
            _make_jsonl_line(
                subagent_type="implementer",
                timestamp=(base).isoformat(),
            ),
            _make_write_jsonl_line(
                abs_hook_path,
                timestamp=(base + timedelta(minutes=2)).isoformat(),
            ),
            _make_jsonl_line(
                subagent_type="reviewer",
                timestamp=(base + timedelta(minutes=5)).isoformat(),
            ),
        ]
        log_file.write_text("\n".join(lines) + "\n")

        events = [
            _make_event(subagent_type="implementer", timestamp=(base).isoformat()),
            _make_event(subagent_type="reviewer", timestamp=(base + timedelta(minutes=5)).isoformat()),
        ]

        findings = detect_missing_security_review(log_file, events)
        assert len(findings) == 1, (
            "#1088 F2: absolute-path non-test security file must still trigger warning. "
            f"Got findings: {[f.description for f in findings]}"
        )
        assert findings[0].pattern_id == "missing_security_review"


def test_spec_validator_registered_in_step_order_and_sequential_pairs():
    """Issue #1158: spec-validator must be registered in STEP_ORDER and SEQUENTIAL_REQUIRED.

    Closes audit D4. The /implement command's STEP 8.5 invokes spec-validator
    after pytest-gate and before reviewer. The pipeline_intent_validator must
    know about this agent for step-ordering and sequential-pair enforcement.
    """
    import pipeline_intent_validator as piv

    # STEP_ORDER registration: spec-validator at 5.7 (between pytest-gate 5.5 and reviewer 6.0)
    assert piv.STEP_ORDER["spec-validator"] == 5.7, (
        f"spec-validator must be at step 5.7, got {piv.STEP_ORDER.get('spec-validator')}"
    )
    assert 5.5 < piv.STEP_ORDER["spec-validator"] < 6.0, (
        "spec-validator must sort between pytest-gate (5.5) and reviewer (6.0)"
    )

    # SEQUENTIAL_REQUIRED registration: three new pairs
    required_pairs = {
        ("implementer", "spec-validator"),
        ("pytest-gate", "spec-validator"),
        ("spec-validator", "reviewer"),
    }
    actual_pairs = set(piv.SEQUENTIAL_REQUIRED)
    missing = required_pairs - actual_pairs
    assert not missing, f"Missing sequential pairs for spec-validator: {missing}"

