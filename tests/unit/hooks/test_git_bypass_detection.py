#!/usr/bin/env python3
"""
Unit tests for git bypass detection in unified_pre_tool.py (Issue #406).

Tests _detect_git_bypass() for --no-verify, -n, --force, -f, git reset --hard,
git clean -f, false positives (git log -n, git fetch -f), and edge cases.

Date: 2026-03-17
Agent: test-master
"""

import sys
from pathlib import Path

import pytest

# Add hooks directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from unified_pre_tool import _detect_git_bypass


class TestGitBypassNoVerify:
    """Tests for --no-verify detection."""

    def test_git_commit_no_verify_blocked(self):
        """git commit --no-verify should be blocked."""
        is_bypass, reason = _detect_git_bypass("git commit -m 'msg' --no-verify")
        assert is_bypass is True
        assert "no-verify" in reason.lower() or "--no-verify" in reason

    def test_git_push_no_verify_blocked(self):
        """git push --no-verify should be blocked."""
        is_bypass, reason = _detect_git_bypass("git push --no-verify origin main")
        assert is_bypass is True
        assert "--no-verify" in reason or "no-verify" in reason.lower()


class TestGitBypassShortN:
    """-n shorthand on push/commit/merge should be blocked, but NOT on log/diff."""

    def test_git_commit_n_blocked(self):
        """git commit -n should be blocked (shorthand for --no-verify)."""
        is_bypass, reason = _detect_git_bypass("git commit -n -m 'msg'")
        assert is_bypass is True
        assert "-n" in reason

    def test_git_push_n_blocked(self):
        """git push -n should be blocked."""
        is_bypass, reason = _detect_git_bypass("git push -n origin main")
        assert is_bypass is True

    def test_git_log_n_not_blocked(self):
        """git log -n 5 should NOT be blocked (-n means count, not no-verify)."""
        is_bypass, reason = _detect_git_bypass("git log -n 5")
        assert is_bypass is False

    def test_git_diff_n_not_blocked(self):
        """git diff -n should NOT be blocked."""
        is_bypass, reason = _detect_git_bypass("git diff -n")
        assert is_bypass is False


class TestGitBypassForce:
    """--force and -f on push should be blocked, but not on fetch."""

    def test_git_push_force_blocked(self):
        """git push --force should be blocked."""
        is_bypass, reason = _detect_git_bypass("git push --force origin main")
        assert is_bypass is True
        assert "force" in reason.lower()

    def test_git_push_f_blocked(self):
        """git push -f should be blocked."""
        is_bypass, reason = _detect_git_bypass("git push -f origin main")
        assert is_bypass is True

    def test_git_fetch_f_not_blocked(self):
        """git fetch -f should NOT be blocked (-f on fetch is not dangerous)."""
        is_bypass, reason = _detect_git_bypass("git fetch -f origin")
        assert is_bypass is False


class TestGitResetAndClean:
    """git reset --hard and git clean -f should be blocked."""

    def test_git_reset_hard_blocked(self):
        """git reset --hard should be blocked."""
        is_bypass, reason = _detect_git_bypass("git reset --hard HEAD~1")
        assert is_bypass is True
        assert "reset" in reason.lower() and "hard" in reason.lower()

    def test_git_clean_f_blocked(self):
        """git clean -f should be blocked."""
        is_bypass, reason = _detect_git_bypass("git clean -f")
        assert is_bypass is True
        assert "clean" in reason.lower()

    def test_git_clean_fd_blocked(self):
        """git clean -fd should be blocked."""
        is_bypass, reason = _detect_git_bypass("git clean -fd")
        assert is_bypass is True


class TestFalsePositives:
    """Commands that contain git-related strings but are NOT bypasses."""

    def test_git_commit_m_no_verify_in_message(self):
        """'no-verify' inside a commit message string should NOT be blocked."""
        is_bypass, reason = _detect_git_bypass("git commit -m 'fix no-verify issue'")
        assert is_bypass is False

    def test_regular_git_commit(self):
        """Normal git commit should not be blocked."""
        is_bypass, reason = _detect_git_bypass("git commit -m 'feat: add feature'")
        assert is_bypass is False

    def test_non_git_command(self):
        """Non-git commands should not be detected as bypass."""
        is_bypass, reason = _detect_git_bypass("python3 test.py")
        assert is_bypass is False

    def test_piped_git_command_only_checks_first(self):
        """Only the command before the pipe should be checked."""
        is_bypass, reason = _detect_git_bypass("git log --oneline | head -5")
        assert is_bypass is False

    def test_empty_command(self):
        """Empty command should not crash."""
        is_bypass, reason = _detect_git_bypass("")
        assert is_bypass is False

    def test_malformed_command(self):
        """Malformed/unterminated quotes should not crash."""
        is_bypass, reason = _detect_git_bypass("git commit -m 'unterminated")
        # Should not crash, behavior is best-effort
        assert isinstance(is_bypass, bool)


class TestGitGlobalValueFlags:
    """Regression tests for Issue #1470.

    Value-taking global flags (-c, -C, --git-dir, --work-tree, --namespace)
    must not fool subcommand extraction into treating their value token as
    the subcommand. If they did, force-push/no-verify detection would be
    silently skipped for constructions like `git -c foo=bar push --force`.
    """

    def test_git_c_kv_push_force_blocked(self):
        """git -c foo=bar push --force must still be detected as force-push."""
        is_bypass, reason = _detect_git_bypass("git -c foo=bar push --force origin main")
        assert is_bypass is True
        assert "force" in reason.lower()

    def test_git_C_path_push_force_with_lease_blocked(self):
        """git -C /repo push --force-with-lease must be detected."""
        is_bypass, reason = _detect_git_bypass("git -C /repo push --force-with-lease origin main")
        assert is_bypass is True
        assert "force" in reason.lower()

    def test_git_git_dir_combined_push_f_blocked(self):
        """git --git-dir=/x push -f (combined --flag=value form) must be detected."""
        is_bypass, reason = _detect_git_bypass("git --git-dir=/x push -f origin main")
        assert is_bypass is True
        assert "force" in reason.lower() or "-f" in reason

    def test_git_git_dir_separated_commit_no_verify_blocked(self):
        """git --git-dir /x commit --no-verify (separated form) must be detected."""
        is_bypass, reason = _detect_git_bypass("git --git-dir /x commit --no-verify -m 'msg'")
        assert is_bypass is True
        assert "no-verify" in reason.lower()

    def test_git_work_tree_push_force_blocked(self):
        """git --work-tree /w push --force must be detected."""
        is_bypass, reason = _detect_git_bypass("git --work-tree /w push --force origin main")
        assert is_bypass is True
        assert "force" in reason.lower()

    def test_git_namespace_push_n_blocked(self):
        """git --namespace ns push -n must be detected as -n bypass."""
        is_bypass, reason = _detect_git_bypass("git --namespace ns push -n origin main")
        assert is_bypass is True
        assert "-n" in reason

    def test_git_c_kv_multiple_then_commit_no_verify_blocked(self):
        """Multiple -c flags followed by commit --no-verify must be detected."""
        is_bypass, reason = _detect_git_bypass(
            "git -c user.name=x -c user.email=y commit --no-verify -m 'msg'"
        )
        assert is_bypass is True
        assert "no-verify" in reason.lower()

    def test_git_C_path_status_benign(self):
        """git -C /repo status (benign subcommand) must NOT be flagged."""
        is_bypass, reason = _detect_git_bypass("git -C /repo status")
        assert is_bypass is False

    def test_git_push_force_no_global_flags_still_blocked(self):
        """Regression guard: existing behavior for plain 'git push --force' unchanged."""
        is_bypass, reason = _detect_git_bypass("git push --force origin main")
        assert is_bypass is True
        assert "force" in reason.lower()

    def test_git_c_kv_log_n_still_benign(self):
        """Regression guard: -n on log is still not flagged even with -c prefix."""
        is_bypass, reason = _detect_git_bypass("git -c color.ui=always log -n 5")
        assert is_bypass is False
