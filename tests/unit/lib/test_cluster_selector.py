"""Unit tests for cluster_selector module."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"))

from cluster_selector import select_next_cluster


def test_tracker_by_title_prefix():
    """Issue with title '[TRACKER] foo' is skipped; next non-tracker cluster returned."""
    clusters = [
        {
            "issue_numbers": [1],
            "issues": [{"number": 1, "title": "[TRACKER] foo", "body": "", "labels": [], "state": "open"}]
        },
        {
            "issue_numbers": [2],
            "issues": [{"number": 2, "title": "Regular issue", "body": "", "labels": [], "state": "open"}]
        }
    ]
    
    # Mock subprocess to return OPEN for all issues
    def mock_run(cmd, **kwargs):
        result = Mock()
        if "rate_limit" in cmd:
            result.returncode = 0
            result.stdout = "200"
        else:
            result.returncode = 0
            result.stdout = "OPEN"
        return result
    
    with patch("subprocess.run", side_effect=mock_run):
        result = select_next_cluster(clusters)
        assert result["issue_numbers"] == [2]


def test_tracker_by_labels():
    """Issue with labels ['root-cause', 'enhancement', 'pipeline'] is skipped."""
    clusters = [
        {
            "issue_numbers": [1],
            "issues": [{
                "number": 1,
                "title": "Some issue",
                "body": "",
                "labels": ["root-cause", "enhancement", "pipeline"],
                "state": "open"
            }]
        },
        {
            "issue_numbers": [2],
            "issues": [{"number": 2, "title": "Regular issue", "body": "", "labels": [], "state": "open"}]
        }
    ]
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "OPEN"
        result = select_next_cluster(clusters)
        assert result["issue_numbers"] == [2]


def test_tracker_by_phase_plan():
    """Issue with phase headings and issue refs is detected as tracker."""
    body = "### Phase A\nSome text\n### Phase B\nMore text\nFixes #100 and #101"
    clusters = [
        {
            "issue_numbers": [1],
            "issues": [{
                "number": 1,
                "title": "Design doc",
                "body": body,
                "labels": [],
                "state": "open"
            }]
        },
        {
            "issue_numbers": [2],
            "issues": [{"number": 2, "title": "Regular issue", "body": "", "labels": [], "state": "open"}]
        }
    ]
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "OPEN"
        result = select_next_cluster(clusters)
        assert result["issue_numbers"] == [2]


def test_prefers_leaf_over_tracker():
    """Returns lowest-numbered open leaf when tracker references open issues."""
    tracker_body = "### Phase A\nImplement feature\n### Phase B\nValidation\n\nTracks:\n- #1274\n- #1276"
    clusters = [
        {
            "issue_numbers": [1277],
            "issues": [{
                "number": 1277,
                "title": "[TRACKER] Feature implementation",
                "body": tracker_body,
                "labels": [],
                "state": "open"
            }]
        },
        {
            "issue_numbers": [1274],
            "issues": [{
                "number": 1274,
                "title": "Implement part 1",
                "body": "",
                "labels": [],
                "state": "open"
            }]
        },
        {
            "issue_numbers": [1276],
            "issues": [{
                "number": 1276,
                "title": "Implement part 2",
                "body": "",
                "labels": [],
                "state": "open"
            }]
        }
    ]
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "OPEN"
        result = select_next_cluster(clusters)
        assert result["issue_numbers"] == [1274]


def test_regression_issue_1277():
    """Exact spec from issue #1284: tracker #1277 with open leaves #1274, #1276."""
    tracker_body = """## Overview

Design and implementation of proper feature cascade + tracker-aware drainage for ADR-002 (nested architecture documents).

### Phase A: Document Structure

First, we establish the cascading document structure:

- Root ADR document (ADR-002-cascade.md) that defines the overall approach
- Supporting implementation guides for each major component
- Test specifications that map to each implementation piece

Issue: #1274 - Create ADR-002-cascade.md with proper structure

### Phase B: Implementation Strategy

Then implement the actual cascade logic:

- Parser for nested ADR references
- Resolution mechanism for cross-document links
- Validation of cascade depth limits

Issue: #1276 - Implement cascade parser and resolver"""
    
    clusters = [
        {
            "issue_numbers": [1277],
            "root_cause_tag": "adr-cascade",
            "issues": [{
                "number": 1277,
                "title": "[TRACKER] ADR-002 redesign",
                "body": tracker_body,
                "labels": [
                    {"name": "enhancement"},
                    {"name": "auto-improvement"},
                    {"name": "root-cause"},
                    {"name": "pipeline"}
                ],
                "state": "open"
            }]
        },
        {
            "issue_numbers": [1274],
            "root_cause_tag": "adr-cascade",
            "issues": [{
                "number": 1274,
                "title": "Create ADR-002-cascade.md",
                "body": "",
                "labels": [],
                "state": "open"
            }]
        },
        {
            "issue_numbers": [1276],
            "root_cause_tag": "adr-cascade",
            "issues": [{
                "number": 1276,
                "title": "Implement cascade parser",
                "body": "",
                "labels": [],
                "state": "open"
            }]
        }
    ]
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "OPEN"
        result = select_next_cluster(clusters)
        assert result is not None
        assert result["issue_numbers"] == [1274]
        assert 1277 not in result["issue_numbers"]

# Tests for apply_auto_drain_gates functionality

@patch("subprocess.run")
def test_auto_drain_gates_filters_human_gate_tags(mock_run):
    """When apply_auto_drain_gates=True, clusters with HUMAN_GATE_TAGS are filtered."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1],
            "severity": "low",
            "cluster_size": 1,
            "issues": [{
                "number": 1,
                "title": "Security issue",
                "body": "",
                "labels": [{"name": "security"}],  # This is a HUMAN_GATE_TAG
                "state": "open"
            }]
        },
        {
            "issue_numbers": [2],
            "severity": "low",
            "cluster_size": 1,
            "issues": [{
                "number": 2,
                "title": "Regular issue",
                "body": "",
                "labels": [],
                "state": "open"
            }]
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=True)
    assert result is not None
    assert result["issue_numbers"] == [2]


@patch("subprocess.run")
def test_auto_drain_gates_filters_large_clusters(mock_run):
    """When apply_auto_drain_gates=True, clusters exceeding MAX_CLUSTER_SIZE_AUTO_DRAINABLE are filtered."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1, 2, 3, 4, 5, 6],  # 6 issues > MAX_CLUSTER_SIZE_AUTO_DRAINABLE (5)
            "severity": "low",
            "cluster_size": 6,
            "issues": []
        },
        {
            "issue_numbers": [7, 8],
            "severity": "low",
            "cluster_size": 2,
            "issues": []
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=True)
    assert result is not None
    assert result["issue_numbers"] == [7, 8]


@patch("subprocess.run")
def test_auto_drain_gates_filters_high_severity(mock_run):
    """When apply_auto_drain_gates=True, clusters below AUTO_DRAINABLE_SEVERITY threshold are filtered."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1],
            "severity": "high",  # Not in AUTO_DRAINABLE_SEVERITY
            "cluster_size": 1,
            "issues": []
        },
        {
            "issue_numbers": [2],
            "severity": "medium",  # In AUTO_DRAINABLE_SEVERITY
            "cluster_size": 1,
            "issues": []
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=True)
    assert result is not None
    assert result["issue_numbers"] == [2]


@patch("subprocess.run")
def test_auto_drain_gates_filters_skip_labels(mock_run):
    """When apply_auto_drain_gates=True, clusters with skip labels (blocked/waiting) are filtered."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1],
            "severity": "low",
            "cluster_size": 1,
            "issues": [{
                "number": 1,
                "title": "Blocked issue",
                "body": "",
                "labels": [{"name": "blocked"}],  # Skip label
                "state": "open"
            }]
        },
        {
            "issue_numbers": [2],
            "severity": "low",
            "cluster_size": 1,
            "issues": [{
                "number": 2,
                "title": "Regular issue",
                "body": "",
                "labels": [],
                "state": "open"
            }]
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=True)
    assert result is not None
    assert result["issue_numbers"] == [2]


@patch("subprocess.run")
def test_auto_drain_gates_filters_large_feat(mock_run):
    """When apply_auto_drain_gates=True, large feature clusters (>2 issues with feat: prefix) are filtered."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1, 2, 3],
            "severity": "low",
            "cluster_size": 3,
            "issue_titles": ["feat: big feature", "feat: part 2", "feat: part 3"],
            "issues": []
        },
        {
            "issue_numbers": [4],
            "severity": "low",
            "cluster_size": 1,
            "issue_titles": ["fix: bug fix"],
            "issues": []
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=True)
    assert result is not None
    assert result["issue_numbers"] == [4]


@patch("subprocess.run")
def test_auto_drain_gates_filters_drain_stuck_meta(mock_run):
    """When apply_auto_drain_gates=True, drain-stuck meta issues are filtered."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1],
            "severity": "low",
            "cluster_size": 1,
            "issue_titles": ["[drain-stuck] Watchdog meta issue"],
            "issues": []
        },
        {
            "issue_numbers": [2],
            "severity": "low",
            "cluster_size": 1,
            "issue_titles": ["Regular issue"],
            "issues": []
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=True)
    assert result is not None
    assert result["issue_numbers"] == [2]


@patch("subprocess.run")
def test_auto_drain_gates_default_false_preserves_behavior(mock_run):
    """When apply_auto_drain_gates=False (default), existing tracker/leaf behavior is preserved."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1],
            "severity": "high",  # Would be filtered with gates, but not with default
            "cluster_size": 1,
            "issues": [{
                "number": 1,
                "title": "High severity issue",
                "body": "",
                "labels": [],
                "state": "open"
            }]
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=False)
    assert result is not None
    assert result["issue_numbers"] == [1]
    
    # Without the explicit parameter (testing default)
    result2 = select_next_cluster(clusters)
    assert result2 is not None
    assert result2["issue_numbers"] == [1]


@patch("subprocess.run")
def test_all_workflow_callers_get_same_selection(mock_run):
    """All three workflow callers (drain-driver, drain-watchdog, /drain-queue) get the same selection given the same input."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1],
            "severity": "high",
            "cluster_size": 1,
            "issues": []
        },
        {
            "issue_numbers": [2],
            "severity": "low",  
            "cluster_size": 1,
            "issues": []
        },
        {
            "issue_numbers": [3],
            "severity": "medium",
            "cluster_size": 1,
            "issues": []
        }
    ]
    
    # All callers use apply_auto_drain_gates=True
    result1 = select_next_cluster(clusters, apply_auto_drain_gates=True)
    result2 = select_next_cluster(clusters, apply_auto_drain_gates=True)
    result3 = select_next_cluster(clusters, apply_auto_drain_gates=True)
    
    assert result1 == result2 == result3
    assert result1 is not None
    assert result1["issue_numbers"] == [2]  # Low severity passes gates


@patch("subprocess.run")
def test_no_drainable_cluster_returns_none(mock_run):
    """When all clusters are filtered by gates, returns None."""
    # Mock subprocess to return OPEN for all issues
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "OPEN"
    clusters = [
        {
            "issue_numbers": [1],
            "severity": "high",  # Filtered
            "cluster_size": 1,
            "issues": []
        },
        {
            "issue_numbers": [2, 3, 4, 5, 6, 7],  # Too large
            "severity": "low",
            "cluster_size": 6,
            "issues": []
        }
    ]
    result = select_next_cluster(clusters, apply_auto_drain_gates=True)
    assert result is None
