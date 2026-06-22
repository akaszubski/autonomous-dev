#!/usr/bin/env python3
"""Tests for DrainHistory revert_status/revert_sha fields (Issue #1292)."""

import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_queue_state import DrainHistory  # noqa: E402


def test_revert_status_field_persists_through_append_read_cycle(tmp_path):
    """Verify revert_status field round-trips through append/read."""
    history = DrainHistory.load(tmp_path)
    history.append({
        "outcome": "success",
        "cluster_id": "test#1",
        "revert_status": "pending",
    })
    records = history.read_all()
    assert len(records) == 1
    assert records[0]["revert_status"] == "pending"


def test_revert_sha_field_persists(tmp_path):
    """Verify revert_sha field round-trips through append/read."""
    history = DrainHistory.load(tmp_path)
    history.append({
        "outcome": "success",
        "cluster_id": "test#2",
        "revert_status": "reverted",
        "revert_sha": "abc1234",
    })
    records = history.read_all()
    assert len(records) == 1
    assert records[0]["revert_sha"] == "abc1234"


def test_records_without_revert_fields_still_readable(tmp_path):
    """Legacy records (no revert_status/revert_sha) read back without error."""
    history = DrainHistory.load(tmp_path)
    history.append({
        "outcome": "success",
        "cluster_id": "legacy#1",
    })
    records = history.read_all()
    assert len(records) == 1
    assert "revert_status" not in records[0]
    assert "revert_sha" not in records[0]


def test_latest_pending_reverts_returns_only_pending_success(tmp_path):
    """latest_pending_reverts returns only success+pending records."""
    history = DrainHistory.load(tmp_path)
    # Add 3 records: success+pending, success+reverted, blocked+pending
    history.append({
        "outcome": "success",
        "cluster_id": "test#1",
        "revert_status": "pending",
    })
    history.append({
        "outcome": "success",
        "cluster_id": "test#2", 
        "revert_status": "reverted",
    })
    history.append({
        "outcome": "blocked",
        "cluster_id": "test#3",
        "revert_status": "pending",
    })
    
    pending = DrainHistory.latest_pending_reverts(tmp_path)
    assert len(pending) == 1
    assert pending[0]["cluster_id"] == "test#1"