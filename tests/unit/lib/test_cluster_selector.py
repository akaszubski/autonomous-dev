"""Unit tests for cluster_selector module."""

import sys
from pathlib import Path
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
    
    result = select_next_cluster(clusters)
    assert result is not None
    assert result["issue_numbers"] == [1274]
    assert 1277 not in result["issue_numbers"]