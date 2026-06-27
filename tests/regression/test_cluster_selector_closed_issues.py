"""Regression test for cluster selector closed-issue deduplication.

Tests that select_next_cluster() skips clusters where issues are already CLOSED
on GitHub, preventing re-processing of completed work.
"""

from unittest.mock import Mock, patch, MagicMock
import subprocess
import sys
from pathlib import Path

# Add lib to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from cluster_selector import select_next_cluster, _is_cluster_closed, _gh_rate_limit_ok


def test_cluster_with_closed_issue_skipped():
    """Test 1: cluster with CLOSED issue is skipped, next candidate returned."""
    clusters = [
        {
            "issue_numbers": [123],
            "issues": [{"number": 123, "state": "open", "title": "Test", "body": "", "labels": []}],
            "root_cause_tag": "bug"
        },
        {
            "issue_numbers": [456],
            "issues": [{"number": 456, "state": "open", "title": "Test2", "body": "", "labels": []}],
            "root_cause_tag": "enhancement"
        }
    ]
    
    # Mock subprocess to return CLOSED for issue 123, OPEN for 456
    def mock_run(cmd, **kwargs):
        result = Mock()
        if "123" in cmd:
            result.returncode = 0
            result.stdout = "CLOSED"
        elif "456" in cmd:
            result.returncode = 0
            result.stdout = "OPEN"
        elif "rate_limit" in cmd:
            result.returncode = 0
            result.stdout = "200"  # Plenty of rate limit
        else:
            result.returncode = 1
            result.stdout = ""
        return result
    
    with patch("subprocess.run", side_effect=mock_run):
        selected = select_next_cluster(clusters)
        assert selected is not None
        assert selected["issue_numbers"] == [456]


def test_cluster_with_open_issue_selected():
    """Test 2: cluster with OPEN issue is selected."""
    clusters = [
        {
            "issue_numbers": [789],
            "issues": [{"number": 789, "state": "open", "title": "Test", "body": "", "labels": []}],
            "root_cause_tag": "bug"
        }
    ]
    
    # Mock subprocess to return OPEN for issue 789
    def mock_run(cmd, **kwargs):
        result = Mock()
        if "789" in cmd:
            result.returncode = 0
            result.stdout = "OPEN"
        elif "rate_limit" in cmd:
            result.returncode = 0
            result.stdout = "200"
        else:
            result.returncode = 1
            result.stdout = ""
        return result
    
    with patch("subprocess.run", side_effect=mock_run):
        selected = select_next_cluster(clusters)
        assert selected is not None
        assert selected["issue_numbers"] == [789]


def test_rate_limit_low_skips_dedup():
    """Test 3: rate limit <100 skips dedup, first candidate returned regardless."""
    clusters = [
        {
            "issue_numbers": [111],
            "issues": [{"number": 111, "state": "open", "title": "Test", "body": "", "labels": []}],
            "root_cause_tag": "bug"
        }
    ]
    
    # Mock subprocess to return low rate limit (50) and CLOSED issue (which should be ignored)
    def mock_run(cmd, **kwargs):
        result = Mock()
        if "rate_limit" in cmd:
            result.returncode = 0
            result.stdout = "50"  # Below threshold
        elif "111" in cmd:
            # This should NOT be called due to rate limit check
            raise AssertionError("Should not check issue state when rate limit is low")
        else:
            result.returncode = 1
            result.stdout = ""
        return result
    
    with patch("subprocess.run", side_effect=mock_run):
        selected = select_next_cluster(clusters)
        assert selected is not None
        assert selected["issue_numbers"] == [111]


def test_gh_subprocess_fails_gracefully():
    """Test 4: gh subprocess fails, treat as not closed, candidate returned."""
    clusters = [
        {
            "issue_numbers": [222],
            "issues": [{"number": 222, "state": "open", "title": "Test", "body": "", "labels": []}],
            "root_cause_tag": "bug"
        }
    ]
    
    # Mock subprocess to fail for issue check but succeed for rate limit
    def mock_run(cmd, **kwargs):
        if "rate_limit" in cmd:
            result = Mock()
            result.returncode = 0
            result.stdout = "200"
            return result
        elif "222" in cmd:
            # Simulate subprocess failure
            raise subprocess.TimeoutExpired(cmd, timeout=10)
        else:
            result = Mock()
            result.returncode = 1
            result.stdout = ""
            return result
    
    with patch("subprocess.run", side_effect=mock_run):
        selected = select_next_cluster(clusters)
        assert selected is not None
        assert selected["issue_numbers"] == [222]


def test_is_cluster_closed_helper():
    """Test the _is_cluster_closed helper function directly."""
    # Test with CLOSED issue
    cluster = {"issue_numbers": [333]}
    
    def mock_closed(cmd, **kwargs):
        result = Mock()
        result.returncode = 0
        result.stdout = "CLOSED"
        return result
    
    with patch("subprocess.run", side_effect=mock_closed):
        is_closed, reason = _is_cluster_closed(cluster)
        assert is_closed is True
        assert reason == "issue_already_closed"
    
    # Test with OPEN issue
    def mock_open(cmd, **kwargs):
        result = Mock()
        result.returncode = 0
        result.stdout = "open"
        return result
    
    with patch("subprocess.run", side_effect=mock_open):
        is_closed, reason = _is_cluster_closed(cluster)
        assert is_closed is False
        assert reason == ""


def test_gh_rate_limit_ok_helper():
    """Test the _gh_rate_limit_ok helper function directly."""
    # Test with high rate limit
    def mock_high(cmd, **kwargs):
        result = Mock()
        result.returncode = 0
        result.stdout = "500"
        return result
    
    with patch("subprocess.run", side_effect=mock_high):
        assert _gh_rate_limit_ok(100) is True
    
    # Test with low rate limit
    def mock_low(cmd, **kwargs):
        result = Mock()
        result.returncode = 0
        result.stdout = "50"
        return result
    
    with patch("subprocess.run", side_effect=mock_low):
        assert _gh_rate_limit_ok(100) is False
    
    # Test with exactly the threshold
    def mock_exact(cmd, **kwargs):
        result = Mock()
        result.returncode = 0
        result.stdout = "100"
        return result
    
    with patch("subprocess.run", side_effect=mock_exact):
        assert _gh_rate_limit_ok(100) is True  # >= is True
    
    # Test graceful failure handling
    def mock_fail(cmd, **kwargs):
        raise ValueError("Parse error")
    
    with patch("subprocess.run", side_effect=mock_fail):
        assert _gh_rate_limit_ok(100) is True  # Defaults to True on error