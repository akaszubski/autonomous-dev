"""Unit tests for Issue #1178: prompt-integrity recovery telemetry.

Validates the paired-event telemetry surface added to unified_pre_tool.py:

1. ``_record_agent_denial`` persists the new ``block_event_id`` and
   ``block_timestamp_iso`` fields when supplied.
2. ``_check_agent_denial`` ignores the new fields (additive-safe).
3. ``_read_agent_denial_record`` returns the full state dict.
4. ``_emit_prompt_integrity_event`` writes one JSONL row to
   ``hook-blocks.jsonl`` and gates ``block_reason_detail`` behind
   ``HOOK_TELEMETRY_VERBOSE=1``.
5. The block emission generates a valid uuid4 and classifies the reason.
6. The recovery emission consumes the denial record (single-emit invariant).
7. Telemetry failures must NEVER break the underlying hook decision path.

Date: 2026-06-14
Issue: #1178
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

import pytest

# Add hook + lib dirs to path so we can import unified_pre_tool and hook_telemetry.
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Reset relevant env vars for each test."""
    for key in ("HOOK_TELEMETRY_VERBOSE", "HOOK_TELEMETRY_DISABLED",
                "HOOK_RECOVERY_DISABLED", "CLAUDE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def set_session_id(monkeypatch):
    """Set a known session_id on the hook module."""
    test_sid = "test-session-1178"
    monkeypatch.setattr(hook, "_session_id", test_sid)
    return test_sid


@pytest.fixture
def state_dir(tmp_path, set_session_id, monkeypatch):
    """Provide an isolated temp directory for agent denial state files."""
    monkeypatch.setattr(hook, "AGENT_DENY_STATE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Anchor hook-blocks.jsonl writes inside a temp cwd."""
    monkeypatch.chdir(tmp_path)
    return tmp_path / ".claude" / "logs"


def _read_log_rows(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Test 1: block emission uses uuid4 and category classification
# ---------------------------------------------------------------------------


def test_block_emits_event_with_uuid_and_category(state_dir, log_dir, set_session_id):
    """The block-emission path writes one row with a valid uuid4 + category."""
    block_event_id = str(uuid.uuid4())
    hook._emit_prompt_integrity_event(
        hook._PI_BLOCK_EVENT_TYPE,
        agent_type="researcher-local",
        block_event_id=block_event_id,
        timestamp="2026-06-14T00:00:00+00:00",
        block_reason_category="shrinkage_pct_over_threshold",
        shrinkage_pct=27.6,
        baseline_words=399,
        current_words=289,
        retry_count=0,
    )

    rows = _read_log_rows(log_dir / "hook-blocks.jsonl")
    assert len(rows) == 1
    row = rows[0]
    assert row["hook_name"] == "unified_pre_tool.py"
    metadata = row["metadata"]
    assert metadata["event_type"] == hook._PI_BLOCK_EVENT_TYPE
    assert metadata["block_event_id"] == block_event_id
    # uuid4 has version nibble 4 in the third group.
    assert uuid.UUID(metadata["block_event_id"]).version == 4
    assert metadata["agent_type"] == "researcher-local"
    assert metadata["block_reason_category"] == "shrinkage_pct_over_threshold"
    assert metadata["shrinkage_pct"] == 27.6
    assert metadata["baseline_words"] == 399
    assert metadata["current_words"] == 289


# ---------------------------------------------------------------------------
# Test 2: _record_agent_denial persists new fields
# ---------------------------------------------------------------------------


def test_record_agent_denial_persists_block_event_id_and_timestamp(
    state_dir, set_session_id
):
    """The two new optional kwargs are written into the state JSON."""
    block_event_id = "11111111-2222-4333-8444-555555555555"
    block_ts = "2026-06-14T01:02:03+00:00"
    hook._record_agent_denial(
        "researcher-local",
        block_event_id=block_event_id,
        block_timestamp_iso=block_ts,
    )
    state_path = state_dir / f"adev-agent-deny-{set_session_id}.json"
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert data["agent_type"] == "researcher-local"
    assert data["block_event_id"] == block_event_id
    assert data["block_timestamp_iso"] == block_ts


# ---------------------------------------------------------------------------
# Test 3: _check_agent_denial ignores unknown keys (additive-safe regression)
# ---------------------------------------------------------------------------


def test_check_agent_denial_ignores_unknown_keys(state_dir, set_session_id):
    """The existing _check_agent_denial reader still returns the agent_type
    when the state file includes the new #1178 fields."""
    hook._record_agent_denial(
        "implementer",
        block_event_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        block_timestamp_iso="2026-06-14T01:02:03+00:00",
    )
    assert hook._check_agent_denial() == "implementer"


# ---------------------------------------------------------------------------
# Test 4: recovery emission pairs by block_event_id and consumes the file
# ---------------------------------------------------------------------------


def test_recovery_emits_paired_event_and_consumes_denial_file(
    state_dir, log_dir, set_session_id
):
    """A synthetic denial record + a recovery emission yields a paired row
    with the same block_event_id AND deletes the state file."""
    block_event_id = str(uuid.uuid4())
    block_ts = "2026-06-14T01:00:00+00:00"
    hook._record_agent_denial(
        "researcher-local",
        block_event_id=block_event_id,
        block_timestamp_iso=block_ts,
    )
    state_path = state_dir / f"adev-agent-deny-{set_session_id}.json"
    assert state_path.exists()

    record = hook._read_agent_denial_record()
    assert record is not None
    assert record["block_event_id"] == block_event_id

    hook._emit_prompt_integrity_event(
        hook._PI_RECOVERY_EVENT_TYPE,
        agent_type=record["agent_type"],
        block_event_id=record["block_event_id"],
        timestamp="2026-06-14T01:03:00+00:00",
        recovery_strategy="template_reload+reconstruct",
        retry_count=1,
        latency_ms_from_block_to_recovery=180_000,
    )
    hook._consume_agent_denial_record()

    rows = _read_log_rows(log_dir / "hook-blocks.jsonl")
    recovery_rows = [r for r in rows if r["metadata"]["event_type"] == hook._PI_RECOVERY_EVENT_TYPE]
    assert len(recovery_rows) == 1
    assert recovery_rows[0]["metadata"]["block_event_id"] == block_event_id
    assert recovery_rows[0]["metadata"]["latency_ms_from_block_to_recovery"] == 180_000
    # Single-emit invariant: state file consumed.
    assert not state_path.exists()


# ---------------------------------------------------------------------------
# Test 5: single-emit invariant — second allow after recovery does not re-emit
# ---------------------------------------------------------------------------


def test_second_allow_after_recovery_does_not_re_emit(state_dir, log_dir, set_session_id):
    """After _consume_agent_denial_record, _read_agent_denial_record returns None,
    so any subsequent allow path is a no-op for telemetry."""
    block_event_id = str(uuid.uuid4())
    hook._record_agent_denial(
        "researcher-local",
        block_event_id=block_event_id,
        block_timestamp_iso="2026-06-14T01:00:00+00:00",
    )
    # Simulate the recovery happening then state cleanup
    assert hook._read_agent_denial_record() is not None
    hook._consume_agent_denial_record()
    # Subsequent attempts find nothing
    assert hook._read_agent_denial_record() is None
    # Calling consume again is a no-op (idempotent, fail-open)
    hook._consume_agent_denial_record()  # must not raise


# ---------------------------------------------------------------------------
# Test 6: HOOK_TELEMETRY_VERBOSE gates block_reason_detail
# ---------------------------------------------------------------------------


def test_verbose_mode_includes_block_reason_detail(monkeypatch, log_dir, set_session_id):
    """block_reason_detail (raw deny reason) is gated behind HOOK_TELEMETRY_VERBOSE=1."""
    # Default (no env var): detail stripped
    hook._emit_prompt_integrity_event(
        hook._PI_BLOCK_EVENT_TYPE,
        agent_type="researcher-local",
        block_event_id=str(uuid.uuid4()),
        block_reason_detail="Prompt for 'researcher-local' shrank 27.6% from baseline (399 words -> 289 words)",
    )

    # Verbose ON: detail present
    monkeypatch.setenv("HOOK_TELEMETRY_VERBOSE", "1")
    hook._emit_prompt_integrity_event(
        hook._PI_BLOCK_EVENT_TYPE,
        agent_type="researcher-local",
        block_event_id=str(uuid.uuid4()),
        block_reason_detail="Prompt for 'researcher-local' shrank 27.6% from baseline (399 words -> 289 words)",
    )

    rows = _read_log_rows(log_dir / "hook-blocks.jsonl")
    assert len(rows) == 2
    assert "block_reason_detail" not in rows[0]["metadata"], (
        "Without HOOK_TELEMETRY_VERBOSE, block_reason_detail must be stripped"
    )
    assert "block_reason_detail" in rows[1]["metadata"], (
        "With HOOK_TELEMETRY_VERBOSE=1, block_reason_detail must be preserved"
    )
    assert "shrank 27.6%" in rows[1]["metadata"]["block_reason_detail"]


# ---------------------------------------------------------------------------
# Test 7: telemetry failures must not break the decision path
# ---------------------------------------------------------------------------


def test_telemetry_failure_does_not_break_deny_decision(monkeypatch, set_session_id):
    """If log_block_event raises, _emit_prompt_integrity_event swallows it.

    This is the load-bearing fail-open guarantee: telemetry is best-effort, the
    hook decision path is the user-facing contract.
    """
    def boom(**kwargs):
        raise RuntimeError("filesystem on fire")

    monkeypatch.setattr(hook, "log_block_event", boom)

    # Must not raise.
    hook._emit_prompt_integrity_event(
        hook._PI_BLOCK_EVENT_TYPE,
        agent_type="researcher-local",
        block_event_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Bonus: _parse_pi_numerics extracts the three numerics from a typical reason
# ---------------------------------------------------------------------------


def test_parse_pi_numerics_extracts_shrinkage_and_word_counts():
    """The inline classifier regex handles the typical deny reason format."""
    reason = "Prompt for 'researcher-local' shrank 27.6% from baseline (399 words -> 289 words)"
    pct, baseline, current = hook._parse_pi_numerics(reason)
    assert pct == 27.6
    assert baseline == 399
    assert current == 289

    # Unicode arrow form (real hook output uses this).
    reason_unicode = "Prompt for 'planner' shrank 41.2% from baseline (510 words → 300 words)"
    pct, baseline, current = hook._parse_pi_numerics(reason_unicode)
    assert pct == 41.2
    assert baseline == 510
    assert current == 300

    # Parse failure returns all-None.
    pct, baseline, current = hook._parse_pi_numerics("slot 'feedback' missing required content")
    assert (pct, baseline, current) == (None, None, None)
