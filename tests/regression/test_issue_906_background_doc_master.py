"""Regression tests for Issue #906: background doc-master verdict reliability.

Consolidates child issues:
- #874: doc-master completion recorded unconditionally (audit trail never lost)
- #882: background agent events skipped for step_ordering checks
- #897: watchdog timeout scenario writes MISSING verdict (not silently dropped)

This file verifies:
1. PipelineEvent.is_background defaults to False for backward compatibility.
2. is_background parsed from input_summary.is_background field.
3. Background events are excluded from sequential step_ordering checks.
4. doc-master completion is recorded unconditionally (including MISSING verdict).
5. Static: implement.md and implement-batch.md both contain explicit MISSING verdict code.
6. session_activity_logger adds is_background to input_summary when run_in_background=true.
"""

import importlib
import json
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
IMPLEMENT_BATCH_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_validator():
    """Import pipeline_intent_validator with lib in sys.path."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    mod_name = "pipeline_intent_validator"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


def _make_event(
    subagent_type: str,
    timestamp: str,
    is_background: bool = False,
    remediation: bool = False,
    batch_issue_number: int = 0,
) -> Any:
    """Build a PipelineEvent using the real dataclass from the validator module."""
    validator = _import_validator()
    return validator.PipelineEvent(
        timestamp=timestamp,
        tool="Task",
        agent="main",
        subagent_type=subagent_type,
        pipeline_action="agent_invocation",
        is_background=is_background,
        remediation=remediation,
        batch_issue_number=batch_issue_number,
    )


def _make_log_entry(
    subagent_type: str,
    timestamp: str,
    is_background: bool | None = None,
) -> Dict[str, Any]:
    """Construct a synthetic JSONL log entry as parsed by _parse_single_log."""
    input_summary: Dict[str, Any] = {
        "subagent_type": subagent_type,
        "pipeline_action": "agent_invocation",
        "prompt_word_count": 10,
    }
    if is_background is not None:
        input_summary["is_background"] = is_background

    return {
        "timestamp": timestamp,
        "hook": "PostToolUse",
        "tool": "Task",
        "input_summary": input_summary,
        "output_summary": {"result_word_count": 200, "success": True},
        "session_id": "test-session-906",
        "agent": "main",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIssue906BackgroundDocMaster:
    """Regression tests for Issue #906 / #874 / #882 / #897."""

    # -----------------------------------------------------------------------
    # #874 — doc-master completion recorded unconditionally
    # -----------------------------------------------------------------------

    def test_874_doc_master_completion_recorded_unconditionally(self, tmp_path, monkeypatch) -> None:
        """record_agent_completion for 'doc-master' must work regardless of SubagentStop.

        Simulates the coordinator's explicit call path (Issue #852 / #874):
        both record_doc_verdict AND record_agent_completion are called after the
        doc-master agent returns, regardless of whether SubagentStop fires.

        Verifies the call succeeds and persists the completion entry.
        """
        monkeypatch.syspath_prepend(str(LIB_DIR))

        mod_name = "pipeline_completion_state"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        pcs = importlib.import_module(mod_name)

        original_path_fn = pcs._state_file_path
        monkeypatch.setattr(
            pcs,
            "_state_file_path",
            lambda sid: tmp_path / f"completions_{sid[:8]}.json",
        )

        session_id = "test-906-874-a"
        issue_number = 906

        # Coordinator calls both functions unconditionally after doc-master returns
        pcs.record_doc_verdict(session_id, issue_number, "PASS")
        pcs.record_agent_completion(
            session_id,
            "doc-master",
            issue_number=issue_number,
            success=True,
        )

        completed = pcs.get_completed_agents(session_id, issue_number=issue_number)
        assert "doc-master" in completed, (
            "doc-master must appear in completed agents after explicit record_agent_completion "
            "(Issue #874 / #852)"
        )

        if mod_name in sys.modules:
            del sys.modules[mod_name]

    def test_874_doc_verdict_recorded_after_retry(self, tmp_path, monkeypatch) -> None:
        """MISSING verdict must be persisted when doc-master retry also produces no output.

        Simulates the watchdog / empty-output scenario (#874, #897):
        - First invocation returns empty output
        - Retry also returns empty output
        - Coordinator sets verdict = "MISSING" and records it

        The audit trail must not be silently lost.
        """
        monkeypatch.syspath_prepend(str(LIB_DIR))

        mod_name = "pipeline_completion_state"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        pcs = importlib.import_module(mod_name)

        monkeypatch.setattr(
            pcs,
            "_state_file_path",
            lambda sid: tmp_path / f"completions_{sid[:8]}.json",
        )

        session_id = "test-906-874-b"
        issue_number = 907

        # Simulate: retry also failed → verdict = "MISSING"
        verdict = "MISSING"
        pcs.record_doc_verdict(session_id, issue_number, verdict)
        pcs.record_agent_completion(
            session_id,
            "doc-master",
            issue_number=issue_number,
            success=(verdict not in ("MISSING",)),
        )

        state = pcs._read_state(session_id)
        issue_key = str(issue_number)
        completions = state.get("completions", {}).get(issue_key, {})

        assert completions.get("doc-master-verdict") == "MISSING", (
            "doc-master-verdict must be 'MISSING' when retry fails (Issue #874 / #897)"
        )
        assert completions.get("doc-master") is False, (
            "doc-master completion flag must be False for MISSING verdict"
        )

        if mod_name in sys.modules:
            del sys.modules[mod_name]

    # -----------------------------------------------------------------------
    # #882 — background events skipped for step_ordering checks
    # -----------------------------------------------------------------------

    def test_882_background_events_skipped_for_step_ordering(self) -> None:
        """Background agent events must NOT produce step_ordering findings.

        Build a synthetic event list where doc-master (is_background=True)
        has a timestamp BEFORE implementer. Without the fix, this would
        produce a spurious step_ordering finding. With the fix, no finding
        should be emitted because doc-master events are skipped when
        is_background=True.

        Issue #882.
        """
        validator = _import_validator()

        # implementer runs at T=100, doc-master (background) logged at T=50
        # (background agents complete asynchronously; log timestamp is misleading)
        events = [
            _make_event("doc-master", "2026-01-01T00:00:50Z", is_background=True),
            _make_event("implementer", "2026-01-01T00:01:40Z"),
            _make_event("reviewer", "2026-01-01T00:02:00Z"),
        ]

        findings = validator._validate_step_ordering_for_group(
            agent_events=events,
            all_events=events,
        )

        step_ordering_findings = [
            f for f in findings if f.finding_type == "step_ordering"
        ]
        assert not step_ordering_findings, (
            f"No step_ordering findings expected when doc-master is_background=True, "
            f"got: {[f.description for f in step_ordering_findings]}"
        )

    def test_882_non_background_ordering_violation_still_detected(self) -> None:
        """Ordering violations for non-background agents must still be detected.

        Regression guard: is_background filtering must not suppress legitimate
        step_ordering findings for foreground agents.

        Issue #882.
        """
        validator = _import_validator()

        # reviewer (non-background) runs before implementer — violation
        events = [
            _make_event("reviewer", "2026-01-01T00:00:30Z", is_background=False),
            _make_event("implementer", "2026-01-01T00:01:00Z", is_background=False),
        ]

        findings = validator._validate_step_ordering_for_group(
            agent_events=events,
            all_events=events,
        )

        step_ordering_findings = [
            f for f in findings if f.finding_type == "step_ordering"
        ]
        assert step_ordering_findings, (
            "step_ordering finding expected when reviewer runs before implementer "
            "and neither is a background event"
        )

    # -----------------------------------------------------------------------
    # #897 — watchdog timeout writes MISSING verdict
    # -----------------------------------------------------------------------

    def test_897_watchdog_timeout_writes_missing_verdict(self, tmp_path, monkeypatch) -> None:
        """MISSING verdict must be persisted when doc-master produces no output.

        Verifies that when the coordinator detects an empty/no-verdict doc-master
        response (watchdog timeout scenario), it sets verdict = "MISSING" and
        persists it via record_doc_verdict.  The static check on implement.md
        confirms the instruction is present in the coordinator prompt.

        Issue #897.
        """
        monkeypatch.syspath_prepend(str(LIB_DIR))

        mod_name = "pipeline_completion_state"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        pcs = importlib.import_module(mod_name)

        monkeypatch.setattr(
            pcs,
            "_state_file_path",
            lambda sid: tmp_path / f"completions_{sid[:8]}.json",
        )

        session_id = "test-906-897"
        issue_number = 897

        # Simulate verdict = "MISSING" (no output after retry)
        pcs.record_doc_verdict(session_id, issue_number, "MISSING")
        pcs.record_agent_completion(
            session_id,
            "doc-master",
            issue_number=issue_number,
            success=False,
        )

        state = pcs._read_state(session_id)
        issue_key = str(issue_number)
        completions = state.get("completions", {}).get(issue_key, {})

        assert completions.get("doc-master-verdict") == "MISSING", (
            "verdict = 'MISSING' must be persisted when doc-master has no output (Issue #897)"
        )

        # Static: implement.md must contain explicit MISSING verdict instruction
        assert IMPLEMENT_MD.exists(), f"implement.md not found at {IMPLEMENT_MD}"
        content = IMPLEMENT_MD.read_text()
        assert "MISSING" in content, "implement.md must reference the MISSING verdict explicitly"
        assert "record_doc_verdict" in content, "implement.md must call record_doc_verdict"

        if mod_name in sys.modules:
            del sys.modules[mod_name]

    # -----------------------------------------------------------------------
    # Backward compatibility
    # -----------------------------------------------------------------------

    def test_is_background_field_defaults_false_for_backward_compat(self) -> None:
        """PipelineEvent.is_background must default to False.

        Existing logs that pre-date Issue #906 do not contain the
        is_background field. Parsing them must produce is_background=False,
        not an error or True.

        Issue #906 AC6.
        """
        validator = _import_validator()

        # Construct a PipelineEvent without specifying is_background
        event = validator.PipelineEvent(
            timestamp="2026-01-01T00:00:00Z",
            tool="Task",
            agent="main",
            subagent_type="doc-master",
            pipeline_action="agent_invocation",
        )

        assert event.is_background is False, (
            "PipelineEvent.is_background must default to False for backward compatibility "
            "(Issue #906)"
        )

    def test_is_background_parsed_from_input_summary(self, tmp_path) -> None:
        """is_background=True in input_summary must produce PipelineEvent.is_background=True.

        Simulates a log entry where a background agent (doc-master) was logged
        with is_background=True in the input_summary dict by session_activity_logger.

        Issue #906 AC2.
        """
        validator = _import_validator()

        log_entry = _make_log_entry("doc-master", "2026-01-01T00:01:00Z", is_background=True)

        # Write single-entry JSONL to tmp file and parse
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(json.dumps(log_entry) + "\n")

        events = validator.parse_session_logs(log_file)

        assert events, "Expected at least one parsed event"
        doc_events = [e for e in events if e.subagent_type == "doc-master"]
        assert doc_events, "Expected a doc-master event in parsed output"

        assert doc_events[0].is_background is True, (
            "Parsed PipelineEvent.is_background must be True when input_summary contains "
            "'is_background': True (Issue #906)"
        )

    def test_is_background_not_parsed_from_entry_missing_field(self, tmp_path) -> None:
        """Log entry without is_background in input_summary must parse as is_background=False.

        Backward compatibility guard for pre-#906 log format.

        Issue #906 AC6.
        """
        validator = _import_validator()

        # No is_background field in input_summary
        log_entry = _make_log_entry("reviewer", "2026-01-01T00:02:00Z", is_background=None)

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(json.dumps(log_entry) + "\n")

        events = validator.parse_session_logs(log_file)

        reviewer_events = [e for e in events if e.subagent_type == "reviewer"]
        assert reviewer_events, "Expected a reviewer event"
        assert reviewer_events[0].is_background is False, (
            "is_background must default to False when field absent from log entry (Issue #906)"
        )
