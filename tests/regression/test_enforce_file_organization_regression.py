"""Subprocess-level regression tests for enforce_file_organization (Issue #1034).

These tests invoke the hook as a real subprocess, mirroring how Claude Code
would invoke it. They prove the hook works end-to-end (shebang, imports,
hook_safety wrap, JSON contract) — not just its internal functions.

In-process unit tests live in tests/unit/hooks/test_enforce_file_organization.py.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "enforce_file_organization.py"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
PERF_REPORT_PATH = REPO_ROOT / "scripts" / "hook_perf_report.py"

BLOCK_LOG_RELATIVE = Path(".claude") / "logs" / "hook-blocks.jsonl"


def _load_block_shapes() -> frozenset:
    """Read BLOCK_SHAPES from the real report script.

    Cross-validation, not a hardcoded copy: if the report's notion of which
    decision shapes count as blocks drifts, these tests must move with it
    rather than assert against a stale third copy.
    """
    spec = importlib.util.spec_from_file_location(
        "_hook_perf_report_for_test", PERF_REPORT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BLOCK_SHAPES


def _read_block_rows(root: Path) -> list:
    """Return parsed telemetry rows under ``root``, or [] when absent."""
    log_path = root / BLOCK_LOG_RELATIVE
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _decision(result: subprocess.CompletedProcess) -> str:
    """Extract the permissionDecision, or ``"allow (silent)"`` for no output."""
    if not result.stdout.strip():
        return "allow (silent)"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def _init_repo(repo_dir: Path) -> Path:
    """Initialize ``repo_dir`` as a git repo and return its resolved path."""
    subprocess.run(
        ["git", "init", "--quiet", str(repo_dir)],
        check=True,
        capture_output=True,
    )
    return repo_dir.resolve()


def _run_hook(
    payload: dict,
    *,
    cwd: Path,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the hook as a subprocess with ``payload`` on stdin."""
    full_env = os.environ.copy()
    # Clear bypass by default so tests don't accidentally inherit it.
    full_env.pop("AUTONOMOUS_DEV_BYPASS", None)
    # Issue #1587: telemetry assertions below require the recorder enabled.
    full_env.pop("HOOK_TELEMETRY_DISABLED", None)
    full_env.pop("HOOK_RECOVERY_DISABLED", None)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=full_env,
        timeout=10,
    )


class TestSubprocessHook:
    """Real subprocess invocations covering the end-to-end contract."""

    def test_subprocess_blocks_root_py(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "foo.py")},
        }
        result = _run_hook(payload, cwd=repo)
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        assert result.stdout.strip(), f"expected deny JSON on stdout, got empty (stderr={result.stderr})"
        envelope = json.loads(result.stdout)
        assert envelope["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = envelope["hookSpecificOutput"]["permissionDecisionReason"]
        assert "foo.py" in reason
        assert "scripts/" in reason

    def test_subprocess_allows_subdir_write(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        scripts = repo / "scripts"
        scripts.mkdir()
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(scripts / "foo.py")},
        }
        result = _run_hook(payload, cwd=repo)
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        # Allow path produces NO JSON envelope on stdout.
        assert result.stdout.strip() == "", (
            f"expected silent allow, got stdout={result.stdout!r}"
        )

    def test_subprocess_bypass_env_short_circuits(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "foo.py")},
        }
        result = _run_hook(payload, cwd=repo, env={"AUTONOMOUS_DEV_BYPASS": "1"})
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        # Bypass produces no deny envelope on stdout.
        assert result.stdout.strip() == "", (
            f"bypass should suppress deny output, got: {result.stdout!r}"
        )

    def test_subprocess_in_worktree_uses_worktree_root(self, tmp_path: Path) -> None:
        """When invoked from inside a git worktree, the hook's git rev-parse
        MUST resolve to the worktree's root — not the main repo root. The
        worktree IS its own checkout for path-resolution purposes."""
        # Build a main repo with at least one commit so worktree add works.
        main_repo = tmp_path / "main"
        main_repo.mkdir()
        _init_repo(main_repo)
        # git worktree add requires HEAD to exist. Make one commit.
        subprocess.run(
            ["git", "-C", str(main_repo), "config", "user.email", "test@example.invalid"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(main_repo), "config", "user.name", "Test"],
            check=True, capture_output=True,
        )
        (main_repo / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(main_repo), "add", "README.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(main_repo), "commit", "-m", "seed", "--quiet"],
            check=True, capture_output=True,
        )
        # Create a worktree at tmp_path/wt on a new branch.
        worktree = tmp_path / "wt"
        subprocess.run(
            [
                "git", "-C", str(main_repo), "worktree", "add", "--quiet",
                "-b", "feature-1034", str(worktree),
            ],
            check=True, capture_output=True,
        )
        worktree_resolved = worktree.resolve()

        # Try to write foo.py at worktree root — must be blocked.
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(worktree_resolved / "foo.py")},
        }
        result = _run_hook(payload, cwd=worktree_resolved)
        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        assert result.stdout.strip(), (
            f"expected deny in worktree, got empty stdout (stderr={result.stderr})"
        )
        envelope = json.loads(result.stdout)
        assert envelope["hookSpecificOutput"]["permissionDecision"] == "deny"
        # The suggested folder must reference the *worktree* tree.
        assert "scripts/" in envelope["hookSpecificOutput"]["permissionDecisionReason"]


class TestIssue1587RefusalIsRecorded:
    """Issue #1587: the hook refused correctly but recorded nothing.

    Its zero rows in ``.claude/logs/hook-blocks.jsonl`` meant its refusals
    were invisible — not that it never refused. These tests drive the real
    hook as a subprocess and measure the log, four ways: refusing records,
    permitting does not, telemetry failure cannot break enforcement, and a
    non-git tree stays a silent no-op.

    Every case runs inside a real ``git init`` tree: the hook is a no-op
    outside a git repo (``main()`` step 4 returns early when ``_repo_root()``
    is None), so a probe run in a bare temp dir would silently "pass" while
    proving nothing.

    The telemetry log is anchored to the temp repo root via the hook's
    ``start_dir=repo_root``, so no test row reaches the real
    ``.claude/logs/hook-blocks.jsonl``.
    """

    def test_regression_issue_1587_deny_writes_block_row(self, tmp_path: Path) -> None:
        """A refused root write MUST emit exactly one countable telemetry row."""
        repo = _init_repo(tmp_path)
        assert _read_block_rows(repo) == [], "temp repo must start with no rows"

        payload = {
            "tool_name": "Write",
            "session_id": "sess-1587",
            "tool_input": {"file_path": str(repo / "NOTES.md")},
        }
        result = _run_hook(payload, cwd=repo)

        assert _decision(result) == "deny", f"stderr={result.stderr}"

        rows = _read_block_rows(repo)
        assert len(rows) == 1, f"expected exactly 1 telemetry row, got {len(rows)}"
        row = rows[0]
        assert row["hook_name"] == "enforce_file_organization.py"
        assert row["decision_shape"] in _load_block_shapes(), (
            f"decision_shape={row['decision_shape']!r} is not in BLOCK_SHAPES, "
            "so hook_perf_report.py would not count this refusal as a block"
        )
        assert "NOTES.md" in row["reason"]
        assert row["metadata"]["tool_name"] == "Write"
        assert row["metadata"]["suggested_folder"] == "docs/"
        assert row["session_id"] == "sess-1587"

    def test_regression_issue_1587_allow_writes_no_row(self, tmp_path: Path) -> None:
        """A permitted write MUST stay silent AND record nothing.

        A recorder that also fired on allows would corrupt every count
        derived from the block log.
        """
        repo = _init_repo(tmp_path)
        (repo / "docs").mkdir()
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "docs" / "NOTES.md")},
        }
        result = _run_hook(payload, cwd=repo)

        assert _decision(result) == "allow (silent)", f"stdout={result.stdout!r}"
        assert _read_block_rows(repo) == [], "allow path must not write a row"

    def test_regression_issue_1587_unwritable_log_still_denies(
        self, tmp_path: Path
    ) -> None:
        """An unwritable telemetry log MUST NOT convert a block into an allow.

        ``.claude`` is created as a regular FILE so ``mkdir(parents=True)``
        inside the recorder raises NotADirectoryError. This is uid-independent
        (unlike chmod, which root ignores).
        """
        repo = _init_repo(tmp_path)
        (repo / ".claude").write_text("not a directory\n", encoding="utf-8")

        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "NOTES.md")},
        }
        result = _run_hook(payload, cwd=repo)

        assert _decision(result) == "deny", (
            "telemetry failure must degrade to 'block, unrecorded', never to "
            f"'allow'. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # Positive control: the recorder really did fail (stderr fallback).
        assert "[hook-telemetry]" in result.stderr, (
            "expected the recorder's stderr fallback, proving the write failed; "
            f"stderr={result.stderr!r}"
        )

    def test_regression_issue_1587_raising_recorder_still_denies(
        self, tmp_path: Path
    ) -> None:
        """A recorder that RAISES MUST NOT break the refusal.

        ``log_block_event`` is documented never to raise; this proves the
        guard in ``deny_and_record`` holds anyway. A ``sitecustomize`` shim
        patches the recorder at interpreter startup, before the hook imports
        it, so this is a real subprocess proof rather than an in-process mock.
        """
        repo = _init_repo(tmp_path / "repo")
        shim_dir = tmp_path / "shim"
        shim_dir.mkdir()
        (shim_dir / "sitecustomize.py").write_text(
            "import sys, os\n"
            "sys.path.insert(0, os.environ['AD_LIB'])\n"
            "import hook_telemetry\n"
            "def _boom(**kwargs):\n"
            "    raise RuntimeError('recorder exploded (injected)')\n"
            "hook_telemetry.log_block_event = _boom\n"
            "sys.stderr.write('RECORDER_PATCHED\\n')\n",
            encoding="utf-8",
        )

        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "NOTES.md")},
        }
        result = _run_hook(
            payload,
            cwd=repo,
            env={"AD_LIB": str(LIB_DIR), "PYTHONPATH": str(shim_dir)},
        )

        # Positive control: a probe whose instrument did not engage proves
        # nothing. Confirm the patch actually landed before trusting the deny.
        assert "RECORDER_PATCHED" in result.stderr, (
            f"sitecustomize shim did not run; stderr={result.stderr!r}"
        )
        assert _decision(result) == "deny", (
            f"raising recorder broke enforcement; stdout={result.stdout!r}"
        )
        assert _read_block_rows(repo) == [], "raising recorder cannot have logged"

    def test_regression_issue_1587_outside_git_repo_is_silent_noop(
        self, tmp_path: Path
    ) -> None:
        """Outside a git repo the hook stays a silent no-op — unchanged.

        This is the negative control that caught a broken first probe: a
        bare temp dir makes ``_repo_root()`` return None, so even the deny
        cases come back as silent allows.
        """
        non_git = tmp_path / "plain"
        non_git.mkdir()
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(non_git / "NOTES.md")},
        }
        result = _run_hook(payload, cwd=non_git)

        assert _decision(result) == "allow (silent)", f"stdout={result.stdout!r}"
        assert _read_block_rows(non_git) == []
