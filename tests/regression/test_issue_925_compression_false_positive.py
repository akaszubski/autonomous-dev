"""Regression test for Issue #925 — progressive-compression detector false positives.

5 prior false-positive closures (#757, #723, #867, #805, #923).
Root cause: session_activity_logger._add_result_word_count read tool_output["output"]
as flat string, but Anthropic Task toolUseResult uses tool_output["content"] as
list-of-text-blocks. Detector falls back to cross-issue baseline -> false positives.

This test asserts:
1. Bug fix: implementer events with content list-of-blocks correctly populate result_word_count
2. Disconnect: detect_progressive_compression no longer wired into validate_pipeline_intent
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import session_activity_logger as sal
from pipeline_intent_validator import validate_pipeline_intent


def test_implementer_result_word_count_populated_from_content_list():
    """The exact tool_output shape from real Agent transcripts must yield non-zero word count."""
    tool_output = {
        "content": [
            {"type": "text", "text": "implementer completed task with multiple words of output here"}
        ]
    }
    summary = sal._add_result_word_count("Agent", tool_output, {})
    assert summary["result_word_count"] > 0, (
        "Issue #925: content list-of-blocks shape must populate result_word_count. "
        "If this fails, the multi-turn aggregation fix has regressed."
    )
    # Specific value check: 9 words in the text block above
    # "implementer completed task with multiple words of output here" = 9 words
    assert summary["result_word_count"] == 9


def test_validate_pipeline_intent_does_not_produce_progressive_compression_on_75_percent_shrinkage(tmp_path):
    """The exact false-positive pattern from #757/#723/#867/#805/#923 must not fire.

    Before #925: reviewer prompt shrinking 800 -> 200 across issues (75%) triggered
    a CRITICAL finding. This is the pattern that caused 5 prior closures.
    After #925: detect_progressive_compression is no longer wired; no finding.
    """
    log_file = tmp_path / "test.jsonl"
    events = [
        {
            "timestamp": "2026-04-25T10:00:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "reviewer",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 800,
                "batch_issue_number": 1,
            },
            "output_summary": {"success": True, "result_word_count": 500},
            "session_id": "test",
            "agent": "main",
        },
        {
            "timestamp": "2026-04-25T10:05:00",
            "tool": "Agent",
            "input_summary": {
                "subagent_type": "reviewer",
                "pipeline_action": "agent_invocation",
                "prompt_word_count": 200,
                "batch_issue_number": 2,
            },
            "output_summary": {"success": True, "result_word_count": 500},
            "session_id": "test",
            "agent": "main",
        },
    ]
    with open(log_file, "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    findings = validate_pipeline_intent(log_file, session_id="test")
    progressive_findings = [
        f for f in findings if f.finding_type == "progressive_compression"
    ]
    assert len(progressive_findings) == 0, (
        f"Issue #925: 75% cross-issue shrinkage was the exact false-positive pattern from "
        f"#757, #723, #867, #805, #923. detect_progressive_compression must no longer fire "
        f"through validate_pipeline_intent. Got: {progressive_findings}"
    )
