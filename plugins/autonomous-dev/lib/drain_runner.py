"""Subprocess-bearing helpers for the ``/drain-queue`` command.

Every function here that touches a subprocess MUST pass explicit ``cwd=`` and
``env=`` kwargs — never inherit from the parent (Issue #1064). The
companion test file (``tests/regression/test_drain_queue_runner_subprocess_kwargs.py``)
locks this contract by monkeypatching ``subprocess.run`` and asserting the
kwargs are present and correctly set.

Public surface:

* :func:`check_clean_worktree` — ``git status --porcelain`` empty?
* :func:`default_branch` — resolve HEAD branch via ``git remote show origin``.
* :func:`hydrate_issue_labels` — ``gh issue view N --json labels``.
* :func:`fetch_remote` — ``git fetch origin <branch>``.
* :func:`remote_diverged` — ``git log origin/<b>..HEAD`` and reverse.
* :func:`push_to_default_branch` — ``git push origin <branch>``.
* :func:`relevant_files_changed` — globs in the last commit's tree.
* :func:`invoke_deploy_all` — ``bash scripts/deploy-all.sh``.
* :func:`append_stop_notification` — JSONL append to drain_notifications.jsonl.
* :func:`run_drain` — top-level orchestrator (returns :class:`DrainResult`).

The markdown command (``commands/drain-queue.md``) invokes these via
``python3 -c "from drain_runner import ..."`` and consumes the returned
:class:`DrainResult` to emit the ``PushNotification:`` tool line itself —
this Python module never tries to call the Claude tool harness.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# =============================================================================
# Result type
# =============================================================================


@dataclass
class DrainResult:
    """Return shape of :func:`run_drain` (consumed by the markdown command).

    Fields:
        outcome: ``"success"``, ``"stop"``, or ``"queue_empty"``.
        reason: Human-readable explanation (empty on success).
        cluster_id: Identifier of the selected cluster (e.g., ``"CI#3"``) or
            empty string when no cluster was selected.
        issue_numbers: Tuple of integer issue numbers drained.
        wall_seconds: Wall-clock seconds spent by this drain attempt.
        notification_required: True iff the markdown should emit a
            ``PushNotification:`` tool line for this outcome.
    """

    outcome: str
    reason: str = ""
    cluster_id: str = ""
    issue_numbers: tuple[int, ...] = ()
    wall_seconds: float = 0.0
    notification_required: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Subprocess-bearing helpers — every call passes cwd= and env= explicitly
# =============================================================================


def check_clean_worktree(repo_root: Path, env: Dict[str, str]) -> bool:
    """Return True iff ``git status --porcelain`` is empty.

    Args:
        repo_root: Absolute repository root path.
        env: Subprocess environment (passed explicitly per Issue #1064).

    Returns:
        True iff working tree is clean.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def default_branch(repo_root: Path, env: Dict[str, str]) -> str:
    """Resolve the default branch of ``origin`` via ``git remote show origin``.

    Two fallback layers:

    1. Parse ``HEAD branch:`` line from ``git remote show origin``.
    2. ``git symbolic-ref refs/remotes/origin/HEAD`` (strip ``refs/remotes/origin/``).
    3. Conservative literal ``"master"`` if both fail (offline / new repo).

    Args:
        repo_root: Repository root.
        env: Subprocess environment.

    Returns:
        Branch name (e.g., ``"master"``, ``"main"``).
    """
    result = subprocess.run(
        ["git", "remote", "show", "origin"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "HEAD branch:" in line:
                branch = line.split(":", 1)[1].strip()
                if branch and branch != "(unknown)":
                    return branch

    # Second-tier resolver.
    sym = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if sym.returncode == 0:
        ref = sym.stdout.strip()
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix):
            return ref[len(prefix):]

    return "master"


def hydrate_issue_labels(
    issue_number: int, repo_root: Path, env: Dict[str, str]
) -> List[str]:
    """Fetch label names for a single GitHub issue via ``gh issue view``.

    Returns an empty list on any error (network failure, rate limit, missing
    ``gh`` CLI). Caller folds these into a cluster-wide label set.

    Args:
        issue_number: Issue number (positive int).
        repo_root: Repo root (issue is read in this repo's context).
        env: Subprocess environment.

    Returns:
        List of label name strings. Empty on any failure.
    """
    if not isinstance(issue_number, int) or issue_number <= 0:
        return []
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "labels",
            "--jq",
            "[.labels[].name]",
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(x) for x in parsed if isinstance(x, str)]


def fetch_remote(
    branch: str, repo_root: Path, env: Dict[str, str]
) -> bool:
    """Run ``git fetch origin <branch>``. Returns True on success."""
    result = subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def remote_diverged(
    branch: str, repo_root: Path, env: Dict[str, str]
) -> bool:
    """Return True iff ``git log HEAD..origin/<branch>`` is non-empty.

    This is the "remote has commits we don't" case — manual merge required.
    """
    result = subprocess.run(
        ["git", "log", f"HEAD..origin/{branch}", "--oneline"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def push_to_default_branch(
    branch: str, repo_root: Path, env: Dict[str, str]
) -> bool:
    """``git push origin <branch>``. Returns True on success."""
    result = subprocess.run(
        ["git", "push", "origin", branch],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def relevant_files_changed(
    repo_root: Path,
    env: Dict[str, str],
    *,
    ref: str = "HEAD~1",
    patterns: tuple[str, ...] = (
        "hooks/",
        "lib/",
        "commands/",
        "agents/",
        "plugins/autonomous-dev/hooks/",
        "plugins/autonomous-dev/lib/",
        "plugins/autonomous-dev/commands/",
        "plugins/autonomous-dev/agents/",
    ),
) -> bool:
    """Return True iff the last commit changed any file under ``patterns``.

    Used by the deploy gate: skip deploy when nothing functional changed.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", ref, "HEAD"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # On error, assume relevant — fail-safe = deploy.
        return True
    for path in result.stdout.splitlines():
        path = path.strip()
        for pat in patterns:
            if path.startswith(pat):
                return True
    return False


def invoke_deploy_all(
    repo_root: Path, env: Dict[str, str], *, extra_args: tuple[str, ...] = ()
) -> bool:
    """Run ``bash scripts/deploy-all.sh``. Returns True on success.

    The deploy script is expected to live at ``<repo_root>/scripts/deploy-all.sh``.
    """
    cmd = ["bash", "scripts/deploy-all.sh", *extra_args]
    result = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


# =============================================================================
# Notification helper — JSONL append (NOT a PushNotification call)
# =============================================================================


def append_stop_notification(reason: str, drain_log_dir: Path) -> None:
    """Append one JSONL record to ``<drain_log_dir>/drain_notifications.jsonl``.

    This is the ONLY notification side-effect this Python module performs.
    ``PushNotification`` is a Claude Code tool invoked by the model — the
    markdown command emits its tool line separately after this helper writes
    the JSONL row. A headless ``/loop`` parent can tail the JSONL file when
    the PushNotification tool is unreachable.

    Args:
        reason: Stop reason (free-form string).
        drain_log_dir: Directory that contains the drain logs (typically
            ``<repo_root>/.claude/local``).
    """
    drain_log_dir = Path(drain_log_dir)
    try:
        drain_log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        pass
    target = drain_log_dir / "drain_notifications.jsonl"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "drain_stop",
        "reason": str(reason),
    }
    try:
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        # Notification write failure is non-fatal — caller already knows it
        # stopped; nothing depends on this file for control flow.
        pass


# =============================================================================
# Top-level orchestrator
# =============================================================================


def _build_env(repo_root: Path) -> Dict[str, str]:
    """Build the subprocess env per Issue #1064 discipline.

    Inherits the current ``os.environ`` (for PATH, HOME, gh credentials), then
    overrides ``BATCH_NO_WORKTREE=1`` for autonomous-dev itself, where
    ``.claude/`` is gitignored and worktree creation would fail.
    """
    env = dict(os.environ)
    # autonomous-dev self-maintenance: gitignored .claude/ blocks worktree
    # creation. Force the no-worktree branch.
    if _is_autonomous_dev_repo(repo_root):
        env["BATCH_NO_WORKTREE"] = "1"
    return env


def _is_autonomous_dev_repo(repo_root: Path) -> bool:
    """Detect the autonomous-dev source repository.

    A reliable marker is the plugin marketplace file at
    ``plugins/autonomous-dev/.claude-plugin/marketplace.json``.
    """
    marker = (
        Path(repo_root)
        / "plugins"
        / "autonomous-dev"
        / ".claude-plugin"
        / "marketplace.json"
    )
    return marker.exists()


def run_drain(
    repo_root: Path, dry_run: bool = False
) -> DrainResult:
    """Top-level drain orchestrator (Python side).

    This is a thin facade — the markdown command at ``commands/drain-queue.md``
    holds the 12-step playbook. ``run_drain`` is exposed primarily for tests
    and for future programmatic use.

    In dry-run mode it runs only the read-only pre-flight checks (worktree
    clean? default branch resolvable?) and returns the result without any
    state mutation.

    Args:
        repo_root: Absolute repository root.
        dry_run: If True, no state-mutating subprocess is invoked.

    Returns:
        :class:`DrainResult`.
    """
    repo_root = Path(repo_root).resolve()
    env = _build_env(repo_root)

    # Pre-flight read-only checks.
    if not check_clean_worktree(repo_root, env):
        return DrainResult(
            outcome="stop",
            reason="working tree not clean",
            notification_required=True,
        )

    branch = default_branch(repo_root, env)

    if dry_run:
        return DrainResult(
            outcome="success",
            reason="dry-run: pre-flight passed",
            cluster_id="",
            issue_numbers=(),
            wall_seconds=0.0,
            notification_required=False,
            extra={"default_branch": branch},
        )

    # The full drain is orchestrated from the markdown command; here we only
    # surface what the Python module can validate.
    return DrainResult(
        outcome="success",
        reason="run_drain is a thin facade — see commands/drain-queue.md",
        cluster_id="",
        issue_numbers=(),
        wall_seconds=0.0,
        notification_required=False,
        extra={"default_branch": branch},
    )


__all__ = [
    "DrainResult",
    "check_clean_worktree",
    "default_branch",
    "hydrate_issue_labels",
    "fetch_remote",
    "remote_diverged",
    "push_to_default_branch",
    "relevant_files_changed",
    "invoke_deploy_all",
    "append_stop_notification",
    "run_drain",
]
