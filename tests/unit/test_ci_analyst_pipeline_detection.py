"""Unit tests for CI analyst pipeline detection via pipeline_intent_validator.

TDD Red Phase: These tests validate that:
1. pipeline_intent_validator correctly parses JSONL logs with subagent_type
2. Missing agents are detected by validate_pipeline_intent()
3. The CI analyst agent prompt references subagent_type and pipeline_intent_validator

Issue #394: Pipeline step logging for CI analyst.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Project root and library path setup
PROJECT_ROOT = Path(__file__).parent.parent.parent
LIB_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_PATH))

from pipeline_intent_validator import (
    Finding,
    PipelineEvent,
    parse_session_logs,
    validate_pipeline_intent,
)

CI_ANALYST_MD = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "continuous-improvement-analyst.md"
)


def _write_jsonl(path: Path, entries: list) -> None:
    """Write a list of dicts as JSONL to the given path."""
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _make_agent_entry(
    subagent_type: str,
    timestamp: str,
    *,
    prompt_word_count: int = 500,
    result_word_count: int = 1000,
    success: bool = True,
    session_id: str = "test-session",
) -> dict:
    """Create a mock JSONL log entry for a Task tool agent invocation."""
    return {
        "timestamp": timestamp,
        "hook": "PostToolUse",
        "tool": "Task",
        "input_summary": {
            "pipeline_action": "agent_invocation",
            "subagent_type": subagent_type,
            "prompt_word_count": prompt_word_count,
        },
        "output_summary": {
            "result_word_count": result_word_count,
            "success": success,
        },
        "session_id": session_id,
        "agent": "main",
    }


def _make_test_run_entry(
    timestamp: str,
    *,
    success: bool = True,
    session_id: str = "test-session",
) -> dict:
    """Create a mock JSONL log entry for a Bash test run."""
    return {
        "timestamp": timestamp,
        "hook": "PostToolUse",
        "tool": "Bash",
        "input_summary": {
            "pipeline_action": "test_run",
        },
        "output_summary": {
            "success": success,
        },
        "session_id": session_id,
        "agent": "main",
    }


class TestParseSessionLogsSubagentType:
    """parse_session_logs() must extract PipelineEvent objects with subagent_type."""

    def test_pipeline_intent_validator_detects_agent_invocations(self, tmp_path: Path):
        """JSONL entries with Task tool and subagent_type produce PipelineEvent objects.

        Given a mock JSONL log containing agent invocation entries with
        subagent_type in input_summary, parse_session_logs() should return
        PipelineEvent objects with the correct subagent_type field populated.
        """
        log_file = tmp_path / "activity.jsonl"
        entries = [
            _make_agent_entry("researcher-local", "2026-03-07T10:00:00Z"),
            _make_agent_entry("researcher", "2026-03-07T10:00:01Z"),
            _make_agent_entry("planner", "2026-03-07T10:01:00Z"),
            _make_agent_entry("test-master", "2026-03-07T10:02:00Z"),
            _make_agent_entry("implementer", "2026-03-07T10:05:00Z"),
        ]
        _write_jsonl(log_file, entries)

        events = parse_session_logs(log_file)

        assert len(events) == 5, f"Expected 5 events, got {len(events)}"

        # Verify each event has the correct subagent_type
        subagent_types = [e.subagent_type for e in events]
        assert subagent_types == [
            "researcher-local",
            "researcher",
            "planner",
            "test-master",
            "implementer",
        ]

        # Verify all events are PipelineEvent instances
        for event in events:
            assert isinstance(event, PipelineEvent)
            assert event.tool == "Task"
            assert event.pipeline_action == "agent_invocation"

    def test_parse_session_logs_filters_by_session_id(self, tmp_path: Path):
        """parse_session_logs() should filter entries by session_id when provided."""
        log_file = tmp_path / "activity.jsonl"
        entries = [
            _make_agent_entry("planner", "2026-03-07T10:00:00Z", session_id="session-A"),
            _make_agent_entry("implementer", "2026-03-07T10:01:00Z", session_id="session-B"),
            _make_agent_entry("reviewer", "2026-03-07T10:02:00Z", session_id="session-A"),
        ]
        _write_jsonl(log_file, entries)

        events = parse_session_logs(log_file, session_id="session-A")

        assert len(events) == 2
        assert events[0].subagent_type == "planner"
        assert events[1].subagent_type == "reviewer"

    def test_parse_session_logs_ignores_non_pipeline_entries(self, tmp_path: Path):
        """Entries without pipeline_action='agent_invocation' should be ignored."""
        log_file = tmp_path / "activity.jsonl"
        entries = [
            {
                "timestamp": "2026-03-07T10:00:00Z",
                "hook": "PostToolUse",
                "tool": "Read",
                "input_summary": {"file_path": "README.md"},
                "output_summary": {"success": True},
                "session_id": "test-session",
                "agent": "main",
            },
            _make_agent_entry("planner", "2026-03-07T10:01:00Z"),
        ]
        _write_jsonl(log_file, entries)

        events = parse_session_logs(log_file)

        assert len(events) == 1
        assert events[0].subagent_type == "planner"


class TestValidatePipelineIntentMissingAgents:
    """validate_pipeline_intent() must detect missing agents."""

    def test_pipeline_intent_validator_detects_missing_agents(self, tmp_path: Path):
        """A log with planner + implementer but missing test-master produces a finding.

        When the pipeline has enough agents (>=4) and includes core steps
        (planner, implementer) but is missing test-master, the validator
        should produce a finding about the skipped test-master step.
        """
        log_file = tmp_path / "activity.jsonl"
        entries = [
            _make_agent_entry("researcher-local", "2026-03-07T10:00:00Z"),
            _make_agent_entry("researcher", "2026-03-07T10:00:01Z"),
            _make_agent_entry("planner", "2026-03-07T10:01:00Z"),
            # test-master is MISSING
            _make_agent_entry("implementer", "2026-03-07T10:05:00Z"),
            _make_test_run_entry("2026-03-07T10:04:00Z", success=True),
            _make_agent_entry("reviewer", "2026-03-07T10:06:00Z"),
            _make_agent_entry("security-auditor", "2026-03-07T10:06:01Z"),
        ]
        _write_jsonl(log_file, entries)

        findings = validate_pipeline_intent(log_file)

        # Should detect test-master is missing
        test_master_findings = [
            f for f in findings
            if "test-master" in f.description.lower() or "test_master" in f.pattern_id
        ]
        assert len(test_master_findings) >= 1, (
            f"Expected at least one finding about missing test-master. "
            f"All findings: {[(f.finding_type, f.description) for f in findings]}"
        )

        # The finding should be a step_skipping type with CRITICAL severity
        for finding in test_master_findings:
            assert isinstance(finding, Finding)
            assert finding.severity == "CRITICAL"

    def test_no_finding_when_all_agents_present(self, tmp_path: Path):
        """A complete pipeline with all agents should not produce step_skipping findings."""
        log_file = tmp_path / "activity.jsonl"
        entries = [
            _make_agent_entry("researcher-local", "2026-03-07T10:00:00Z"),
            _make_agent_entry("researcher", "2026-03-07T10:00:01Z"),
            _make_agent_entry("planner", "2026-03-07T10:01:00Z"),
            _make_agent_entry("test-master", "2026-03-07T10:02:00Z"),
            _make_test_run_entry("2026-03-07T10:03:00Z", success=True),
            _make_agent_entry("implementer", "2026-03-07T10:05:00Z"),
            _make_agent_entry("reviewer", "2026-03-07T10:06:00Z"),
            _make_agent_entry("security-auditor", "2026-03-07T10:06:01Z"),
            _make_agent_entry("doc-master", "2026-03-07T10:06:02Z"),
        ]
        _write_jsonl(log_file, entries)

        findings = validate_pipeline_intent(log_file)

        step_skipping = [f for f in findings if f.finding_type == "step_skipping"]
        assert len(step_skipping) == 0, (
            f"Expected no step_skipping findings for complete pipeline. "
            f"Got: {[(f.finding_type, f.description) for f in step_skipping]}"
        )


class TestCIAnalystPromptReferences:
    """CI analyst agent prompt must reference subagent_type and pipeline_intent_validator."""

    @pytest.fixture
    def ci_analyst_content(self) -> str:
        """Load the CI analyst agent prompt."""
        assert CI_ANALYST_MD.exists(), (
            f"continuous-improvement-analyst.md not found at {CI_ANALYST_MD}"
        )
        return CI_ANALYST_MD.read_text()

    def test_ci_analyst_prompt_references_subagent_type(self, ci_analyst_content: str):
        """CI analyst prompt must mention subagent_type for agent detection.

        The CI analyst needs to know that subagent_type is the field in JSONL
        log entries that identifies which pipeline agent ran. Without this
        reference, the analyst cannot properly detect agent invocations.
        """
        assert "subagent_type" in ci_analyst_content, (
            "continuous-improvement-analyst.md does not mention 'subagent_type'. "
            "The analyst needs to know this is the field for detecting which agent ran."
        )

    def test_ci_analyst_prompt_references_pipeline_intent_validator(
        self, ci_analyst_content: str
    ):
        """CI analyst prompt must reference pipeline_intent_validator.

        The CI analyst should use pipeline_intent_validator as its library
        for parsing session logs and detecting pipeline violations.
        """
        assert "pipeline_intent_validator" in ci_analyst_content, (
            "continuous-improvement-analyst.md does not reference pipeline_intent_validator. "
            "The analyst should use this library for intent-level pipeline validation."
        )
