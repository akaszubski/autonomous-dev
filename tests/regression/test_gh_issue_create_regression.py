"""
Regression tests for gh issue create blocking (Issue #599).

Ensures the gh issue create blocking behavior works end-to-end
and never regresses.

Date: 2026-03-29
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hook and lib directories to path
HOOK_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

LIB_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove pipeline/agent env vars."""
    for key in ["CLAUDE_AGENT_NAME", "PIPELINE_STATE_FILE", "CLAUDE_SESSION_ID"]:
        monkeypatch.delenv(key, raising=False)


class TestGhIssueCreateRegression:
    """Regression tests: direct gh issue create is blocked outside approved contexts."""

    def test_direct_gh_issue_create_blocked_without_pipeline(self):
        """Regression: gh issue create must be blocked when no pipeline is active.

        Bug: Before Issue #599, users could bypass /create-issue by running
        'gh issue create' directly, skipping research and duplicate detection.
        Fix: _detect_gh_issue_create blocks unless pipeline/agent/marker allows.
        """
        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""), \
             patch.object(hook, "GH_ISSUE_MARKER_PATH", "/tmp/nonexistent_marker_test"):
            result = hook._detect_gh_issue_create('gh issue create --title "test"')
            assert result is not None
            assert "BLOCKED" in result

    def test_pipeline_active_allows_gh_issue_create(self):
        """Regression: gh issue create must be allowed when pipeline is active.

        The /implement pipeline creates issues for remediation findings.
        Blocking those would break the pipeline.
        """
        with patch.object(hook, "_is_pipeline_active", return_value=True):
            result = hook._detect_gh_issue_create('gh issue create --title "remediation"')
            assert result is None

    def test_marker_presence_no_longer_grants_allow(self, tmp_path):
        """Regression (#1203): marker file presence MUST NOT grant allow.

        Pre-#1203, the hook had a READ allow-through that granted a 1-hour
        bypass when GH_ISSUE_MARKER_PATH existed and was fresh. That code
        path was dead — nothing has written the marker since #627 made the
        WRITE blocked by _detect_gh_issue_marker_creation. #1203 removed the
        READ allow-through; the WRITE blocker stays as defense-in-depth.

        This test locks the change: a fresh marker on disk MUST be blocked
        without an issue-command-active context.
        """
        marker = tmp_path / "marker"
        marker.touch()  # fresh mtime

        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""), \
             patch.object(hook, "_is_issue_command_active", return_value=False), \
             patch.object(hook, "GH_ISSUE_MARKER_PATH", str(marker)):
            # Fresh marker MUST still be blocked.
            result = hook._detect_gh_issue_create('gh issue create --title "test"')
            assert result is not None, (
                "Issue #1203: marker presence must NOT grant allow"
            )
            assert "BLOCKED" in result

            # Stale marker is also blocked (sanity).
            old_time = time.time() - 7200
            os.utime(str(marker), (old_time, old_time))
            result = hook._detect_gh_issue_create('gh issue create --title "test"')
            assert result is not None
            assert "BLOCKED" in result

    def test_marker_write_still_blocked(self):
        """Regression (#1203): the marker WRITE blocker is preserved.

        #1203 removed the marker READ allow-through but explicitly kept
        _detect_gh_issue_marker_creation (the WRITE blocker) as
        defense-in-depth. This test verifies the WRITE blocker still fires.
        """
        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""):
            cmd = "touch /tmp/autonomous_dev_gh_issue_allowed.marker"
            result = hook._detect_gh_issue_marker_creation(cmd)
            assert result is not None, "Marker WRITE blocker must remain"
            assert "BLOCKED" in result

    def test_non_create_gh_commands_never_blocked(self):
        """Regression: gh issue list/view/close must never be blocked.

        Only 'gh issue create' should be intercepted. Other gh commands
        are read-only or non-issue-creating.
        """
        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""), \
             patch.object(hook, "GH_ISSUE_MARKER_PATH", "/tmp/nonexistent_marker_test"):
            for cmd in [
                "gh issue list --state open",
                "gh issue view 123",
                "gh issue close 456",
                "gh pr create --title 'test'",
                "gh repo view",
            ]:
                result = hook._detect_gh_issue_create(cmd)
                assert result is None, f"Command should not be blocked: {cmd}"
