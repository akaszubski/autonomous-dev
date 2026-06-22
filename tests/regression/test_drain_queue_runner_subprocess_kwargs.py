"""Regression tests locking the Issue #1064 subprocess discipline in ``drain_runner``.

Every ``subprocess.run`` call in ``drain_runner.py`` MUST pass explicit ``cwd=``
and ``env=`` kwargs (never inherit). The pattern is from
``skills/testing-guide/SKILL.md:200-249``. These tests monkeypatch
``subprocess.run`` inside the module under test, capture the full kwargs dict,
and assert on the runtime values — not the cmd list alone.

A static-shape test (``assert cmd == ["git", ...]``) would silently pass even
when ``cwd=`` is dropped; that is the precise bug class Issue #1064 fixed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import drain_runner  # noqa: E402


# =============================================================================
# Helpers
# =============================================================================


def _fake_run_factory(captured: dict, *, stdout: str = "", returncode: int = 0):
    """Build a fake ``subprocess.run`` that captures kwargs into ``captured``."""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout=stdout, stderr=""
        )

    return fake_run


# =============================================================================
# check_clean_worktree
# =============================================================================


class TestCheckCleanWorktreeKwargs:
    def test_passes_cwd_to_repo_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(drain_runner.subprocess, "run", _fake_run_factory(captured))
        drain_runner.check_clean_worktree(tmp_path, env={"PATH": "/usr/bin"})
        assert "cwd" in captured
        assert captured["cwd"] == str(tmp_path)

    def test_passes_env_explicitly(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(drain_runner.subprocess, "run", _fake_run_factory(captured))
        sentinel_env = {"PATH": "/usr/bin", "DRAIN_TEST": "1"}
        drain_runner.check_clean_worktree(tmp_path, env=sentinel_env)
        assert "env" in captured
        assert captured["env"] == sentinel_env

    def test_returns_true_on_empty_stdout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess, "run", _fake_run_factory(captured, stdout="")
        )
        assert drain_runner.check_clean_worktree(tmp_path, env={}) is True

    def test_returns_false_on_dirty_stdout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout=" M foo.py\n"),
        )
        assert drain_runner.check_clean_worktree(tmp_path, env={}) is False


# =============================================================================
# default_branch
# =============================================================================


class TestDefaultBranchKwargs:
    def test_passes_cwd_and_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout="  HEAD branch: main\n"),
        )
        drain_runner.default_branch(tmp_path, env={"X": "1"})
        assert captured["cwd"] == str(tmp_path)
        assert captured["env"] == {"X": "1"}

    def test_parses_main_from_remote_show(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout="* remote origin\n  HEAD branch: main\n"),
        )
        assert drain_runner.default_branch(tmp_path, env={}) == "main"

    def test_falls_back_to_symbolic_ref_then_master(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """First subprocess fails → symbolic-ref returns; verify both calls passed kwargs."""
        capture_list: list = []

        def fake_run(cmd, **kwargs):
            capture_list.append({"cmd": cmd, **kwargs})
            if cmd[:2] == ["git", "remote"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr="fatal: no origin"
                )
            if cmd[:2] == ["git", "symbolic-ref"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="refs/remotes/origin/develop\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        result = drain_runner.default_branch(tmp_path, env={"X": "y"})
        assert result == "develop"
        # BOTH calls must have cwd= and env= set.
        assert len(capture_list) == 2
        for call in capture_list:
            assert call["cwd"] == str(tmp_path)
            assert call["env"] == {"X": "y"}

    def test_falls_back_to_master_when_both_fail(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        assert drain_runner.default_branch(tmp_path, env={}) == "master"


# =============================================================================
# hydrate_issue_labels
# =============================================================================


class TestHydrateIssueLabelsKwargs:
    def test_passes_cwd_and_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout='["bug","auth"]'),
        )
        drain_runner.hydrate_issue_labels(42, tmp_path, env={"GH_TOKEN": "x"})
        assert captured["cwd"] == str(tmp_path)
        assert captured["env"] == {"GH_TOKEN": "x"}

    def test_parses_label_array(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout='["security","auto-improvement"]'),
        )
        labels = drain_runner.hydrate_issue_labels(7, tmp_path, env={})
        assert labels == ["security", "auto-improvement"]

    def test_returns_empty_on_subprocess_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, returncode=1, stdout=""),
        )
        labels = drain_runner.hydrate_issue_labels(7, tmp_path, env={})
        assert labels == []

    def test_returns_empty_on_malformed_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout="not-json"),
        )
        labels = drain_runner.hydrate_issue_labels(7, tmp_path, env={})
        assert labels == []

    def test_invalid_issue_number_returns_empty_without_subprocess(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Defensive check: invalid input bypasses the subprocess entirely."""
        called: list = []
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            lambda *a, **kw: (called.append(True), subprocess.CompletedProcess(a, 0, "", ""))[1],
        )
        assert drain_runner.hydrate_issue_labels(0, tmp_path, env={}) == []
        assert drain_runner.hydrate_issue_labels(-5, tmp_path, env={}) == []
        assert called == []


# =============================================================================
# fetch_remote / remote_diverged / push / deploy / files_changed
# =============================================================================


class TestRemoteOperationsKwargs:
    """All other subprocess-bearing helpers must also pass cwd= and env=."""

    def test_fetch_remote_kwargs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(drain_runner.subprocess, "run", _fake_run_factory(captured))
        drain_runner.fetch_remote("main", tmp_path, env={"E": "v"})
        assert captured["cwd"] == str(tmp_path)
        assert captured["env"] == {"E": "v"}

    def test_remote_diverged_kwargs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(drain_runner.subprocess, "run", _fake_run_factory(captured))
        drain_runner.remote_diverged("main", tmp_path, env={"E": "v"})
        assert captured["cwd"] == str(tmp_path)
        assert captured["env"] == {"E": "v"}

    def test_remote_diverged_true_when_log_nonempty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout="abc123 remote commit\n"),
        )
        assert drain_runner.remote_diverged("main", tmp_path, env={}) is True

    def test_push_to_default_branch_kwargs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(drain_runner.subprocess, "run", _fake_run_factory(captured))
        drain_runner.push_to_default_branch("main", tmp_path, env={"E": "v"})
        assert captured["cwd"] == str(tmp_path)
        assert captured["env"] == {"E": "v"}

    def test_relevant_files_changed_kwargs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(drain_runner.subprocess, "run", _fake_run_factory(captured))
        drain_runner.relevant_files_changed(tmp_path, env={"E": "v"})
        assert captured["cwd"] == str(tmp_path)
        assert captured["env"] == {"E": "v"}

    def test_relevant_files_detects_lib_change(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout="plugins/autonomous-dev/lib/foo.py\n"),
        )
        assert drain_runner.relevant_files_changed(tmp_path, env={}) is True

    def test_relevant_files_skips_when_only_docs_changed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(
            drain_runner.subprocess,
            "run",
            _fake_run_factory(captured, stdout="README.md\ndocs/architecture.md\n"),
        )
        assert drain_runner.relevant_files_changed(tmp_path, env={}) is False

    def test_invoke_deploy_all_kwargs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict = {}
        monkeypatch.setattr(drain_runner.subprocess, "run", _fake_run_factory(captured))
        drain_runner.invoke_deploy_all(tmp_path, env={"E": "v"})
        assert captured["cwd"] == str(tmp_path)
        assert captured["env"] == {"E": "v"}
        # Verify the cmd starts with `bash scripts/deploy-all.sh`.
        assert captured["cmd"][:2] == ["bash", "scripts/deploy-all.sh"]


# =============================================================================
# run_drain (top-level facade)
# =============================================================================


class TestRunDrainSubprocessDiscipline:
    """Confirm run_drain in dry-run mode still passes cwd/env to its callees."""

    def test_run_drain_dry_run_passes_cwd_env_throughout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        calls: list = []

        def fake_run(cmd, **kwargs):
            calls.append({"cmd": cmd, **kwargs})
            # Default-branch resolver expects this line in stdout.
            if cmd[:2] == ["git", "remote"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="  HEAD branch: main\n", stderr=""
                )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        result = drain_runner.run_drain(tmp_path, dry_run=True)
        assert result.outcome == "success"
        # Every call must have cwd= and env= set.
        assert len(calls) >= 2  # check_clean_worktree + default_branch
        for call in calls:
            assert "cwd" in call
            assert call["cwd"] == str(tmp_path)
            assert "env" in call


# =============================================================================
# append_stop_notification (no subprocess)
# =============================================================================


class TestCapturePytestSnapshotSubprocessContract:
    """capture_pytest_snapshot must pass cwd= and env= to subprocess.run.

    Regression for Issue #1290 (Phase C metrics capture). The subprocess
    discipline from Issue #1064 applies: static-shape tests on cmd alone would
    silently pass even when cwd= or env= is wrong.
    """

    def test_passes_cwd_and_env_to_subprocess(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """capture_pytest_snapshot captures cwd=str(repo) and env=env in subprocess."""
        captured: dict = {}

        def fake_run(cmd, **kwargs):
            # Only capture the pytest invocation (not any git stash/checkout calls).
            if cmd and cmd[0] == "pytest":
                captured.update({"cmd": cmd, **kwargs})
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="3 passed in 0.12s\n", stderr=""
            )

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        sentinel_env = {"PATH": "/usr/bin", "DRAIN_TEST": "capture_snapshot"}
        drain_runner.capture_pytest_snapshot(tmp_path, sentinel_env)

        assert "cwd" in captured, "subprocess.run must receive cwd="
        assert captured["cwd"] == str(tmp_path), (
            f"cwd must equal str(repo); got {captured['cwd']!r}"
        )
        assert "env" in captured, "subprocess.run must receive env="
        assert captured["env"] == sentinel_env, (
            f"env must be the passed-in env dict; got {captured['env']!r}"
        )

    def test_snapshot_result_has_expected_keys(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Return value always has test_count, failing_tests, coverage_pct, error."""

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="5 passed in 0.20s\n", stderr=""
            )

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        result = drain_runner.capture_pytest_snapshot(tmp_path, env={})
        assert set(result.keys()) == {"test_count", "failing_tests", "coverage_pct", "error"}

    def test_parses_passed_count_from_pytest_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Parses '5 passed' from pytest stdout."""

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="5 passed in 0.20s\n", stderr=""
            )

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        result = drain_runner.capture_pytest_snapshot(tmp_path, env={})
        assert result["test_count"] == 5
        assert result["failing_tests"] == 0
        assert result["error"] is None

    def test_parses_mixed_passed_failed_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Parses '3 passed, 2 failed, 1 error' from pytest stdout."""

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="3 passed, 2 failed, 1 error in 1.00s\n",
                stderr="",
            )

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        result = drain_runner.capture_pytest_snapshot(tmp_path, env={})
        assert result["test_count"] == 6
        assert result["failing_tests"] == 3
        assert result["error"] is None

    def test_returns_empty_metrics_on_file_not_found(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """FileNotFoundError (pytest not installed) → error='pytest_not_found'."""

        def fake_run(cmd, **kwargs):
            if cmd and cmd[0] == "pytest":
                raise FileNotFoundError("pytest not found")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(drain_runner.subprocess, "run", fake_run)
        result = drain_runner.capture_pytest_snapshot(tmp_path, env={})
        assert result["error"] == "pytest_not_found"
        assert result["test_count"] is None
        assert result["failing_tests"] is None


class TestAppendStopNotification:
    def test_writes_jsonl_record(self, tmp_path: Path) -> None:
        drain_runner.append_stop_notification("budget exhausted", tmp_path)
        target = tmp_path / "drain_notifications.jsonl"
        assert target.exists()
        lines = target.read_text().strip().splitlines()
        assert len(lines) == 1
        import json as _json
        rec = _json.loads(lines[0])
        assert rec["reason"] == "budget exhausted"
        assert rec["kind"] == "drain_stop"
        assert "timestamp" in rec

    def test_appends_multiple_records(self, tmp_path: Path) -> None:
        drain_runner.append_stop_notification("first", tmp_path)
        drain_runner.append_stop_notification("second", tmp_path)
        lines = (tmp_path / "drain_notifications.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_creates_log_dir_if_missing(self, tmp_path: Path) -> None:
        target_dir = tmp_path / "new_log_dir"
        # Directory does not exist yet.
        drain_runner.append_stop_notification("hello", target_dir)
        assert target_dir.exists()
        assert (target_dir / "drain_notifications.jsonl").exists()
