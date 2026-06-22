#!/usr/bin/env python3
"""Auto-revert orchestration for regressing drain commits.

Issue #1292 (ADR-002 Phase C Invariant 4). Invoked by .github/workflows/
drain-regression-check.yml every 10 minutes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make plugins/autonomous-dev/lib importable
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_PATH) not in sys.path:
    sys.path.insert(0, str(LIB_PATH))

from drain_queue_state import (  # noqa: E402
    DrainHistory,
    _history_path,
    iter_pending_revert_candidates,
)
from drain_revert import (  # noqa: E402
    detect_regression,
    ensure_drain_reverted_label_exists,
    find_fix_commits,
    reopen_issues_with_label,
    revert_drain_commit,
)


def _build_env() -> dict:
    """Build subprocess env with GH_TOKEN/GITHUB_TOKEN propagated."""
    env = dict(os.environ)
    return env


def _ping_healthcheck(url: str, status: str = "") -> None:
    """Best-effort ping to healthchecks.io URL."""
    if not url:
        return
    target = url.rstrip("/")
    if status:
        target = f"{target}/{status}"
    try:
        subprocess.run(
            ["curl", "-fsS", "-m", "10", "--retry", "3", "-o", "/dev/null", target],
            capture_output=True, text=True, shell=False, check=False, timeout=30,
        )
    except Exception:
        pass


def _rewrite_history_with_update(repo: Path, updated_records: dict) -> None:
    """Atomic rewrite of JSONL with records updated in place.

    updated_records: dict of timestamp -> updated record dict.
    """
    history = DrainHistory.load(repo)
    all_records = history.read_all()
    path = _history_path(repo)
    if not path.exists():
        return
    new_lines = []
    for rec in all_records:
        ts = rec.get("timestamp", "")
        if ts in updated_records:
            new_lines.append(json.dumps(updated_records[ts], sort_keys=True))
        else:
            new_lines.append(json.dumps(rec, sort_keys=True))
    # Atomic write
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    tmp.replace(path)


def _push_to_default_branch(repo: Path, env: dict) -> bool:
    """Push HEAD to origin's current branch. Returns True on success."""
    try:
        # Get current branch
        b = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo), env=env, capture_output=True, text=True,
            shell=False, check=False, timeout=15,
        )
        if b.returncode != 0:
            return False
        branch = b.stdout.strip()
        p = subprocess.run(
            ["git", "push", "origin", f"HEAD:{branch}"],
            cwd=str(repo), env=env, capture_output=True, text=True,
            shell=False, check=False, timeout=60,
        )
        return p.returncode == 0
    except Exception:
        return False


def main() -> int:
    repo = REPO_ROOT
    env = _build_env()
    healthcheck_url = os.environ.get("HEALTHCHECK_DRAIN_REVERT", "")

    history = DrainHistory.load(repo)
    candidates = iter_pending_revert_candidates(history, min_age_seconds=1800)

    if not candidates:
        print("No pending revert candidates.")
        _ping_healthcheck(healthcheck_url)
        return 0

    updated_records: dict = {}
    reverts_performed = 0

    for record in candidates:
        drain_sha = record.get("drain_sha", "")
        ts_str = record.get("timestamp", "")
        before_metrics = record.get("before_metrics") or {}
        after_metrics = record.get("after_metrics") or {}
        issues = record.get("issues", []) or []

        is_regression, reason = detect_regression(before_metrics, after_metrics)
        if not is_regression:
            # Mark "no_regression" so we don't re-check (idempotent)
            updated = dict(record)
            updated["revert_status"] = "no_regression"
            updated["revert_sha"] = None
            updated_records[ts_str] = updated
            print(f"Skip {drain_sha[:7]}: {reason}")
            continue

        # Check for fix commit
        try:
            since = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            updated = dict(record)
            updated["revert_status"] = "error"
            updated["revert_sha"] = None
            updated_records[ts_str] = updated
            continue
        fix_commits = find_fix_commits(repo, drain_sha, since, env)
        if fix_commits:
            updated = dict(record)
            updated["revert_status"] = "fix_in_progress"
            updated["revert_sha"] = None
            updated_records[ts_str] = updated
            print(f"Skip {drain_sha[:7]}: fix commit(s) detected: {fix_commits[:3]}")
            continue

        # Perform revert
        print(f"Reverting {drain_sha[:7]}: {reason}")
        result = revert_drain_commit(repo, drain_sha, env)
        revert_sha = result.get("revert_sha") or ""
        status = result.get("status", "error")

        updated = dict(record)
        updated["revert_status"] = status
        updated["revert_sha"] = revert_sha or None
        updated_records[ts_str] = updated

        if status == "reverted":
            reverts_performed += 1
            # Push
            pushed = _push_to_default_branch(repo, env)
            if not pushed:
                print(f"  WARN: push failed for revert {revert_sha[:7]}")
            # Ensure label exists, then reopen issues
            ensure_drain_reverted_label_exists(repo, env)
            if issues:
                outcomes = reopen_issues_with_label(
                    repo, issues, drain_sha, revert_sha, env,
                )
                print(f"  Issue outcomes: {outcomes}")

    # Rewrite JSONL with updates
    if updated_records:
        _rewrite_history_with_update(repo, updated_records)

    print(f"Done. {reverts_performed} revert(s) performed.")
    _ping_healthcheck(healthcheck_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
