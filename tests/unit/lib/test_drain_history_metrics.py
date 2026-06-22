"""Test DrainHistory with pytest metrics fields (Issue #1290).

Tests that before_metrics and after_metrics optional fields persist through
append/read cycles and maintain backward compatibility with legacy records.
"""

import json
import pytest
from pathlib import Path
from typing import Any, Dict, List

# Import after adding to path
import sys
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_queue_state import DrainHistory


def test_append_with_both_metrics(tmp_path):
    """Append record with both before_metrics and after_metrics, verify roundtrip."""
    history = DrainHistory.load(tmp_path)
    
    before_metrics = {
        "test_count": 250,
        "coverage_pct": 85.3,
        "failing_tests": ["test_foo", "test_bar"]
    }
    after_metrics = {
        "test_count": 252,
        "coverage_pct": 85.5,
        "failing_tests": []
    }
    
    history.append({
        "outcome": "success",
        "cluster_id": "test#1",
        "before_metrics": before_metrics,
        "after_metrics": after_metrics
    })
    
    records = history.read_all()
    assert len(records) == 1
    assert records[0]["before_metrics"] == before_metrics
    assert records[0]["after_metrics"] == after_metrics
    assert records[0]["outcome"] == "success"
    assert records[0]["cluster_id"] == "test#1"


def test_append_without_metrics_backward_compat(tmp_path):
    """Append legacy record without metrics, verify backward compatibility."""
    history = DrainHistory.load(tmp_path)
    
    # Append a legacy record (no metrics fields)
    history.append({
        "outcome": "success",
        "cluster_id": "legacy#1",
        "issue_numbers": [123, 456],
        "wall_seconds": 45.2
    })
    
    records = history.read_all()
    assert len(records) == 1
    assert "before_metrics" not in records[0]
    assert "after_metrics" not in records[0]
    assert records[0]["outcome"] == "success"
    assert records[0]["cluster_id"] == "legacy#1"
    assert records[0]["issue_numbers"] == [123, 456]
    assert records[0]["wall_seconds"] == 45.2


def test_append_with_partial_metrics(tmp_path):
    """Append records with only before_metrics or only after_metrics."""
    history = DrainHistory.load(tmp_path)
    
    # Record with only before_metrics
    before_only = {
        "test_count": 100,
        "coverage_pct": 75.0,
        "failing_tests": ["test_x"]
    }
    history.append({
        "outcome": "success",
        "cluster_id": "partial#1",
        "before_metrics": before_only
    })
    
    # Record with only after_metrics
    after_only = {
        "test_count": 102,
        "coverage_pct": 75.5,
        "failing_tests": []
    }
    history.append({
        "outcome": "success",
        "cluster_id": "partial#2",
        "after_metrics": after_only
    })
    
    records = history.read_all()
    assert len(records) == 2
    
    # First record has only before_metrics
    assert records[0]["before_metrics"] == before_only
    assert "after_metrics" not in records[0]
    assert records[0]["cluster_id"] == "partial#1"
    
    # Second record has only after_metrics
    assert "before_metrics" not in records[1]
    assert records[1]["after_metrics"] == after_only
    assert records[1]["cluster_id"] == "partial#2"


def test_jsonl_roundtrip_preserves_metrics(tmp_path):
    """Multiple records with varying metrics persist correctly through JSONL."""
    history = DrainHistory.load(tmp_path)
    
    # Append various types of records
    records_to_write = [
        # Legacy record
        {
            "outcome": "success",
            "cluster_id": "mixed#1"
        },
        # Record with full metrics
        {
            "outcome": "success",
            "cluster_id": "mixed#2",
            "before_metrics": {"test_count": 200, "coverage_pct": 80.0, "failing_tests": []},
            "after_metrics": {"test_count": 201, "coverage_pct": 80.1, "failing_tests": []}
        },
        # Record with partial metrics
        {
            "outcome": "failure",
            "cluster_id": "mixed#3",
            "before_metrics": {"test_count": 150, "coverage_pct": 70.0, "failing_tests": ["test_z"]}
        },
        # Another legacy record
        {
            "outcome": "success",
            "cluster_id": "mixed#4",
            "issue_numbers": [789]
        }
    ]
    
    for record in records_to_write:
        history.append(record)
    
    # Read back and verify
    read_records = history.read_all()
    assert len(read_records) == 4
    
    # Check each record preserves its structure
    assert "before_metrics" not in read_records[0]
    assert "after_metrics" not in read_records[0]
    
    assert read_records[1]["before_metrics"]["test_count"] == 200
    assert read_records[1]["after_metrics"]["coverage_pct"] == 80.1
    
    assert read_records[2]["before_metrics"]["failing_tests"] == ["test_z"]
    assert "after_metrics" not in read_records[2]
    
    assert "before_metrics" not in read_records[3]
    assert read_records[3]["issue_numbers"] == [789]


def test_malformed_metrics_still_persisted(tmp_path):
    """Malformed metrics are still persisted (no schema enforcement)."""
    history = DrainHistory.load(tmp_path)
    
    # Append record with non-standard metrics structure
    malformed_metrics = {
        "unexpected_key": "value",
        "nested": {"data": [1, 2, 3]},
        "coverage_pct": "not_a_number"  # Wrong type
    }
    
    history.append({
        "outcome": "success",
        "cluster_id": "malformed#1",
        "before_metrics": malformed_metrics,
        "after_metrics": {"completely": "different"}
    })
    
    records = history.read_all()
    assert len(records) == 1
    
    # Verify malformed data is preserved as-is (passthrough)
    assert records[0]["before_metrics"] == malformed_metrics
    assert records[0]["after_metrics"] == {"completely": "different"}
    assert records[0]["cluster_id"] == "malformed#1"