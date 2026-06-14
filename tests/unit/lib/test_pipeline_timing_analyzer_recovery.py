"""Unit tests for Issue #1178: prompt-integrity recovery overhead reporting.

Validates the additions to ``pipeline_timing_analyzer.py``:

1. ``load_prompt_integrity_events`` filters hook-blocks.jsonl rows to PI ones.
2. ``extract_prompt_integrity_recoveries`` pairs block + recovery by id.
3. Orphan blocks (no matching recovery) are counted in the second return.
4. ``format_timing_report`` is backward-compatible when ``recoveries`` is None.
5. ``format_timing_report`` appends a recovery-overhead section when present.
6. ``load_prompt_integrity_events`` handles missing + malformed inputs.

Date: 2026-06-14
Issue: #1178
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_timing_analyzer import (  # noqa: E402
    AgentTiming,
    PromptIntegrityRecovery,
    extract_prompt_integrity_recoveries,
    format_timing_report,
    load_prompt_integrity_events,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _block_row(block_event_id: str, agent_type: str, *, ts: str = "2026-06-14T01:00:00+00:00",
               category: str = "shrinkage_pct_over_threshold") -> dict:
    return {
        "ts": ts,
        "hook_name": "unified_pre_tool.py",
        "decision_shape": "dict",
        "reason": f"prompt_integrity_block:{agent_type}",
        "metadata": {
            "event_type": "prompt_integrity_block",
            "block_event_id": block_event_id,
            "agent_type": agent_type,
            "session_id": "test-session",
            "timestamp": ts,
            "block_reason_category": category,
            "shrinkage_pct": 27.6,
            "baseline_words": 399,
            "current_words": 289,
            "retry_count": 0,
        },
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }


def _recovery_row(block_event_id: str, agent_type: str, *,
                  ts: str = "2026-06-14T01:03:00+00:00",
                  latency_ms: int = 180_000) -> dict:
    return {
        "ts": ts,
        "hook_name": "unified_pre_tool.py",
        "decision_shape": "dict",
        "reason": f"prompt_integrity_recovery:{agent_type}",
        "metadata": {
            "event_type": "prompt_integrity_recovery",
            "block_event_id": block_event_id,
            "agent_type": agent_type,
            "session_id": "test-session",
            "timestamp": ts,
            "recovery_strategy": "template_reload+reconstruct",
            "retry_count": 1,
            "latency_ms_from_block_to_recovery": latency_ms,
        },
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }


def _non_pi_row() -> dict:
    return {
        "ts": "2026-06-14T01:00:00+00:00",
        "hook_name": "unified_pre_tool.py",
        "decision_shape": "tuple",
        "reason": "some other deny",
        "metadata": {"event_type": "some_other_block", "tool_name": "Write"},
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }


# ---------------------------------------------------------------------------
# Test 1: filter prompt_integrity_* rows
# ---------------------------------------------------------------------------


def test_load_prompt_integrity_events_filters_correctly(tmp_path):
    """Only rows with metadata.event_type starting with 'prompt_integrity_' are returned."""
    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"
    _write_jsonl(log_path, [
        _block_row("aaaa", "researcher-local"),
        _non_pi_row(),
        _recovery_row("aaaa", "researcher-local"),
        _non_pi_row(),
    ])
    events = load_prompt_integrity_events(log_path)
    assert len(events) == 2
    types = {e["metadata"]["event_type"] for e in events}
    assert types == {"prompt_integrity_block", "prompt_integrity_recovery"}


# ---------------------------------------------------------------------------
# Test 2: extract_recoveries pairs by block_event_id
# ---------------------------------------------------------------------------


def test_extract_recoveries_pairs_by_block_event_id():
    """A block + recovery sharing block_event_id yields one PromptIntegrityRecovery."""
    events = [
        _block_row("abc-123", "researcher-local"),
        _recovery_row("abc-123", "researcher-local", latency_ms=242_000),
    ]
    paired, orphans = extract_prompt_integrity_recoveries(events)
    assert orphans == 0
    assert len(paired) == 1
    r = paired[0]
    assert isinstance(r, PromptIntegrityRecovery)
    assert r.block_event_id == "abc-123"
    assert r.agent_type == "researcher-local"
    assert r.latency_ms == 242_000
    assert r.block_reason_category == "shrinkage_pct_over_threshold"


# ---------------------------------------------------------------------------
# Test 3: orphan block counted in blocked_without_recovery
# ---------------------------------------------------------------------------


def test_blocks_without_recovery_counted():
    """A block with no matching recovery increments the counter."""
    events = [
        _block_row("paired-1", "planner"),
        _recovery_row("paired-1", "planner"),
        _block_row("orphan-2", "researcher-local"),  # no matching recovery
    ]
    paired, orphans = extract_prompt_integrity_recoveries(events)
    assert len(paired) == 1
    assert orphans == 1


# ---------------------------------------------------------------------------
# Test 4: format_timing_report backward-compatible without recoveries
# ---------------------------------------------------------------------------


def test_format_timing_report_unchanged_when_no_recoveries():
    """Default kwargs preserve the pre-#1178 report shape."""
    timing = AgentTiming(
        agent_type="planner",
        wall_clock_seconds=42.0,
        result_word_count=500,
        invocation_ts="2026-06-14T01:00:00+00:00",
        completion_ts="2026-06-14T01:00:42+00:00",
        step_number=3.0,
    )
    report = format_timing_report([timing], [])
    assert "## Prompt-Integrity Recovery Overhead" not in report
    assert "Total pipeline duration" in report


# ---------------------------------------------------------------------------
# Test 5: recovery section appears when present
# ---------------------------------------------------------------------------


def test_format_timing_report_includes_recovery_section_when_present():
    """When recoveries are non-empty, the new section is appended."""
    timing = AgentTiming(
        agent_type="planner",
        wall_clock_seconds=42.0,
        result_word_count=500,
        invocation_ts="2026-06-14T01:00:00+00:00",
        completion_ts="2026-06-14T01:00:42+00:00",
        step_number=3.0,
    )
    recoveries = [
        PromptIntegrityRecovery(
            block_event_id="r1",
            agent_type="planner",
            block_timestamp_iso="2026-06-14T01:00:00+00:00",
            recovery_timestamp_iso="2026-06-14T01:02:30+00:00",
            latency_ms=150_000,
            block_reason_category="shrinkage_pct_over_threshold",
        ),
        PromptIntegrityRecovery(
            block_event_id="r2",
            agent_type="planner",
            block_timestamp_iso="2026-06-14T01:05:00+00:00",
            recovery_timestamp_iso="2026-06-14T01:07:14+00:00",
            latency_ms=134_000,
            block_reason_category="shrinkage_pct_over_threshold",
        ),
        PromptIntegrityRecovery(
            block_event_id="r3",
            agent_type="researcher-local",
            block_timestamp_iso="2026-06-14T01:10:00+00:00",
            recovery_timestamp_iso="2026-06-14T01:12:40+00:00",
            latency_ms=160_000,
            block_reason_category="shrinkage_pct_over_threshold",
        ),
    ]
    report = format_timing_report(
        [timing], [],
        recoveries=recoveries,
        blocked_without_recovery=0,
    )
    assert "## Prompt-Integrity Recovery Overhead" in report
    assert "Total recoveries: 3" in report
    # 150_000 + 134_000 + 160_000 = 444_000 ms -> "7m 24s"
    assert "7m 24s" in report
    assert "444,000 ms" in report
    assert "Blocks without observed recovery: 0" in report
    # Breakdown by agent: alphabetical
    assert "planner=2" in report
    assert "researcher-local=1" in report


# ---------------------------------------------------------------------------
# Test 6: missing file -> []; malformed JSON skipped
# ---------------------------------------------------------------------------


def test_load_handles_missing_or_malformed_file(tmp_path):
    """Missing file returns []; malformed lines are skipped silently."""
    # Missing file
    missing = tmp_path / "does_not_exist.jsonl"
    assert load_prompt_integrity_events(missing) == []

    # Malformed file: only some lines parse
    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "not-json-at-all\n"
        + json.dumps(_block_row("ok-1", "planner")) + "\n"
        + "{ partial json\n"
        + json.dumps(_recovery_row("ok-1", "planner")) + "\n"
    )
    events = load_prompt_integrity_events(log_path)
    assert len(events) == 2
    types = sorted(e["metadata"]["event_type"] for e in events)
    assert types == ["prompt_integrity_block", "prompt_integrity_recovery"]
