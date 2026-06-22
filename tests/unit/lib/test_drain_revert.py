"""Unit tests for drain_revert (#1292 ADR-002 Phase C Invariant 4)."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_revert import (
    detect_regression,
    ensure_drain_reverted_label_exists,
    find_fix_commits,
    reopen_issues_with_label,
    revert_drain_commit,
)


class TestDetectRegression:
    def test_equal_failing_counts_no_regression(self):
        before = {"failing_tests": 2, "error": None}
        after = {"failing_tests": 2, "error": None}
        assert detect_regression(before, after) == (False, "no_regression")

    def test_increase_failing_counts_is_regression(self):
        before = {"failing_tests": 0, "error": None}
        after = {"failing_tests": 1, "error": None}
        is_reg, reason = detect_regression(before, after)
        assert is_reg is True
        assert "0" in reason and "1" in reason

    def test_before_error_returns_metrics_incomplete(self):
        before = {"failing_tests": None, "error": "timeout"}
        after = {"failing_tests": 0, "error": None}
        assert detect_regression(before, after) == (False, "metrics_incomplete")

    def test_after_error_returns_metrics_incomplete(self):
        before = {"failing_tests": 0, "error": None}
        after = {"failing_tests": None, "error": "pytest_not_found"}
        assert detect_regression(before, after) == (False, "metrics_incomplete")

    def test_none_failing_tests_returns_metrics_incomplete(self):
        before = {"failing_tests": None, "error": None}
        after = {"failing_tests": 0, "error": None}
        assert detect_regression(before, after) == (False, "metrics_incomplete")


class TestFindFixCommits:
    def test_empty_log_returns_empty_list(self, tmp_path):
        with mock.patch("drain_revert.subprocess.run") as m:
            m.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            result = find_fix_commits(tmp_path, "abc1234def5678" + "0" * 26,
                                       datetime.now(timezone.utc), {})
        assert result == []

    def test_commit_referencing_short_sha_returned(self, tmp_path):
        with mock.patch("drain_revert.subprocess.run") as m:
            m.return_value = mock.Mock(
                returncode=0,
                stdout="fffeeee111122223333\nccccdddd00001111\n",
                stderr="",
            )
            result = find_fix_commits(tmp_path, "abc1234def5678" + "0" * 26,
                                       datetime.now(timezone.utc), {})
        assert "fffeeee111122223333" in result
        assert "ccccdddd00001111" in result

    def test_subprocess_failure_returns_empty(self, tmp_path):
        with mock.patch("drain_revert.subprocess.run") as m:
            m.return_value = mock.Mock(returncode=1, stdout="", stderr="error")
            result = find_fix_commits(tmp_path, "abc1234def5678" + "0" * 26,
                                       datetime.now(timezone.utc), {})
        assert result == []


def _init_git_repo(path: Path) -> str:
    """Helper: initialize a git repo with one commit, return SHA."""
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-b", "main"], cwd=str(path), env=env, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(path), env=env, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(path), env=env, check=True, capture_output=True)
    (path / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=str(path), env=env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(path), env=env, check=True, capture_output=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"],
                         cwd=str(path), env=env, capture_output=True, text=True).stdout.strip()
    return sha


class TestRevertDrainCommit:
    def test_successful_revert_returns_reverted_status(self, tmp_path):
        env = {**os.environ,
               "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"}
        _init_git_repo(tmp_path)
        # Add second commit that we'll revert
        (tmp_path / "b.txt").write_text("world\n")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add b"], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        drain_sha = subprocess.run(["git", "rev-parse", "HEAD"],
                                    cwd=str(tmp_path), env=env, capture_output=True, text=True).stdout.strip()
        result = revert_drain_commit(tmp_path, drain_sha, env)
        assert result["status"] == "reverted"
        assert result["revert_sha"] and len(result["revert_sha"]) == 40
        assert result["error"] is None

    def test_merge_conflict_returns_conflict_status(self, tmp_path):
        env = {**os.environ,
               "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"}
        _init_git_repo(tmp_path)
        # Commit X — adds line
        (tmp_path / "f.txt").write_text("v1\n")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "X"], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        drain_sha = subprocess.run(["git", "rev-parse", "HEAD"],
                                    cwd=str(tmp_path), env=env, capture_output=True, text=True).stdout.strip()
        # Commit Y — modifies same line
        (tmp_path / "f.txt").write_text("v2\n")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Y"], cwd=str(tmp_path), env=env, check=True, capture_output=True)
        # Now revert X — will conflict because Y also touched f.txt
        result = revert_drain_commit(tmp_path, drain_sha, env)
        assert result["status"] in ("conflict", "error")
        # Repo should be clean
        status = subprocess.run(["git", "status", "--porcelain"],
                                cwd=str(tmp_path), env=env, capture_output=True, text=True).stdout
        assert status == "", f"Repo not clean: {status}"

    def test_malformed_sha_returns_error(self, tmp_path):
        _init_git_repo(tmp_path)
        result = revert_drain_commit(tmp_path, "xyz", {})
        assert result["status"] == "error"
        assert result["revert_sha"] is None

    def test_option_smuggling_sha_rejected_cwe88(self, tmp_path):
        """CWE-88 regression: --exec=cmd passes len>=7 but is not hex.

        Without strict hex validation, this string would pass the old
        len(drain_sha) < 7 check and reach `git revert --no-edit --exec=cmd`
        where git interprets --exec as a flag and runs arbitrary commands.
        """
        _init_git_repo(tmp_path)
        result = revert_drain_commit(tmp_path, "--exec=id", {})
        assert result["status"] == "error"
        assert result["error"] == "malformed_sha"

    def test_uppercase_hex_sha_rejected(self, tmp_path):
        """Strict lowercase hex: even valid-looking uppercase SHAs are rejected.

        Git emits lowercase SHAs; an uppercase value in a JSONL record is
        anomalous and rejecting it is defense-in-depth.
        """
        _init_git_repo(tmp_path)
        result = revert_drain_commit(tmp_path, "A" * 40, {})
        assert result["status"] == "error"
        assert result["error"] == "malformed_sha"


class TestReopenIssuesWithLabel:
    def test_happy_path_returns_reopened_per_issue(self, tmp_path):
        # 3 successful subprocess calls per issue (reopen, edit, comment)
        with mock.patch("drain_revert.subprocess.run") as m:
            m.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            outcomes = reopen_issues_with_label(
                tmp_path, [100, 101], "abc1234", "def5678", {}
            )
        assert outcomes == {100: "reopened", 101: "reopened"}

    def test_gh_reopen_failure_returns_error(self, tmp_path):
        with mock.patch("drain_revert.subprocess.run") as m:
            m.return_value = mock.Mock(returncode=1, stdout="", stderr="forbidden")
            outcomes = reopen_issues_with_label(
                tmp_path, [100], "abc1234", "def5678", {}
            )
        assert outcomes[100] == "reopen_failed"


class TestEnsureDrainRevertedLabelExists:
    def test_first_call_creates_label(self, tmp_path):
        with mock.patch("drain_revert.subprocess.run") as m:
            m.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            assert ensure_drain_reverted_label_exists(tmp_path, {}) is True

    def test_already_exists_is_idempotent(self, tmp_path):
        with mock.patch("drain_revert.subprocess.run") as m:
            m.return_value = mock.Mock(returncode=1, stdout="",
                                        stderr="HTTP 422: name already exists")
            assert ensure_drain_reverted_label_exists(tmp_path, {}) is True
