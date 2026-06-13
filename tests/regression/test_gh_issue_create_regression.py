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


# ---------------------------------------------------------------------------
# Issue #1215 — argv-position-aware direct match (live-evidence regressions)
# ---------------------------------------------------------------------------


class TestIssue1215LiveEvidenceRegression:
    """Live-evidence regression for Issue #1215.

    During the 2026-06-12 cluster-drain batch, the #1203 and #1204 commits
    were blocked by ``_detect_gh_issue_create`` because their commit message
    bodies mentioned the literal command name in prose. Both required
    workarounds: ``git commit -F /tmp/file`` AND body-rewriting with neutral
    phrasing like ``issue-creation call`` instead of the literal command
    name. The fix is to make the direct-match path argv-position-aware
    (``shlex.split`` + leading-verb check) so prose substrings inside
    git-commit message bodies no longer falsely match.

    These tests use the EXACT prose from the #1203 and #1204 commit messages
    (c448acb and aaadfd9) to lock the fix against future regression. If
    either test fails, the false-positive blocking has come back.
    """

    def test_regression_issue_1203_actual_commit_body_allowed(self):
        """Regression for Issue #1215: the #1203 commit body MUST NOT block.

        The actual commit ``c448acb`` body was rewritten at write-time with
        the literal command name replaced by ``issue-creation call``
        because of the false positive. With the #1215 fix in place, the
        original prose (with the literal command name) is allowed.
        """
        # Body excerpt from c448acb, with the literal command name restored
        # in the (3) defect description — this is the prose that was
        # originally going to be in the commit before the workaround.
        body_excerpt = (
            "fix(security): #1203 gh-filing allowance four-defect fix\n\n"
            "Defects fixed: (1) TOCTOU-inverse bundled-call (primary, above).\n"
            "(2) /plan double-broken — 'plan' was missing from GH_ISSUE_COMMANDS.\n"
            "(3) bypass-detector false-positive — the backtick / $() regex matched\n"
            "prose inside --body argument VALUES, blocking legitimate "
            "gh issue create calls (live-confirmed).\n"
            "(4) dead marker READ allow-through — removed.\n"
        )
        cmd = f'git commit -m "{body_excerpt}"'
        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""), \
             patch.object(hook, "_is_issue_command_active", return_value=False), \
             patch.object(hook, "GH_ISSUE_MARKER_PATH", "/tmp/nonexistent_marker_test"):
            result = hook._detect_gh_issue_create(cmd)
            assert result is None, (
                "Issue #1215: the #1203 commit body MUST NOT be blocked; "
                f"got: {result!r}"
            )

    def test_regression_issue_1204_actual_commit_body_allowed(self):
        """Regression for Issue #1215: the #1204 commit body MUST NOT block.

        The actual ``aaadfd9`` commit body contains prose about chaining ``rm``
        cleanup onto consuming commands; the command name appears in
        contextual prose ("gh issue create" in the explanation of why the rm
        cleanup matters). The #1215 fix lets the original prose stand.
        """
        body_excerpt = (
            "fix(skills): #1204 chain rm cleanup onto consuming command\n\n"
            "Skills that create temp files (/create-issue, /plan, /plan-to-issues,\n"
            "/improve, /refactor, /retrospective) previously emitted a SEPARATE\n"
            "standalone rm cleanup Bash call after the file-consuming command.\n"
            "The single user approval for the gh issue create call now covers the\n"
            "trailing rm in the same Bash tool call. The user sees ONE prompt for\n"
            "the gh issue create instead of two prompts.\n"
        )
        cmd = f'git commit -m "{body_excerpt}"'
        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""), \
             patch.object(hook, "_is_issue_command_active", return_value=False), \
             patch.object(hook, "GH_ISSUE_MARKER_PATH", "/tmp/nonexistent_marker_test"):
            result = hook._detect_gh_issue_create(cmd)
            assert result is None, (
                "Issue #1215: the #1204 commit body MUST NOT be blocked; "
                f"got: {result!r}"
            )

    def test_regression_issue_1215_commit_body_with_substring_allowed(self):
        """Bonus regression: the #1215 commit body itself MUST NOT block.

        This is the eat-our-own-dogfood case: the commit that fixes #1215
        will (presumably) mention the literal command name in its body when
        describing what the fix does. The fix MUST allow itself to be
        committed.
        """
        body_excerpt = (
            "fix(security): #1215 argv-position-aware direct match for "
            "gh issue create gate\n\n"
            "The pre-tool hook used a raw substring scan that produced false "
            "positives when the literal 'gh issue create' substring appeared "
            "in prose inside git-commit -m bodies. This fix mirrors the #1203 "
            "shlex-aware pattern from _contains_gh_issue_create_bypass onto "
            "_detect_gh_issue_create.\n"
        )
        cmd = f'git commit -m "{body_excerpt}"'
        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""), \
             patch.object(hook, "_is_issue_command_active", return_value=False), \
             patch.object(hook, "GH_ISSUE_MARKER_PATH", "/tmp/nonexistent_marker_test"):
            result = hook._detect_gh_issue_create(cmd)
            assert result is None, (
                "Issue #1215: the fix commit itself MUST NOT be blocked; "
                f"got: {result!r}"
            )

    def test_regression_real_gh_issue_create_command_still_blocked(self):
        """Sanity: the real command at argv[0] MUST STILL be blocked post-#1215."""
        cmd = 'gh issue create --title "test" --body "details"'
        with patch.object(hook, "_is_pipeline_active", return_value=False), \
             patch.object(hook, "_get_active_agent_name", return_value=""), \
             patch.object(hook, "_is_issue_command_active", return_value=False), \
             patch.object(hook, "GH_ISSUE_MARKER_PATH", "/tmp/nonexistent_marker_test"):
            result = hook._detect_gh_issue_create(cmd)
            assert result is not None, (
                "Issue #1215: the real command at argv[0] must STILL be blocked"
            )
            assert "BLOCKED" in result
