#!/usr/bin/env python3
"""Cron orchestration script for drain regression checking and automatic revert.

Reads DrainHistory pending entries, checks for regressions, applies grace periods,
and performs reverts when warranted. Atomically rewrites JSONL via tempfile + os.replace.

Grace periods:
- 30 minutes wall-clock grace after drain commit
- Fix-commit grace: skip revert if fix commits found referencing the drain SHA
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Add lib to path
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_queue_state import DrainHistory, _parse_iso, _utc_now, _iso
from drain_revert import (
    detect_regression,
    find_fix_commits,
    revert_drain_commit,
    reopen_issues_with_label,
    ensure_drain_reverted_label_exists,
    _build_env
)


def should_check_regression(record: Dict) -> bool:
    """Determine if a record should be checked for regression.
    
    Only checks records with revert_status == "pending" that are older than 30 minutes.
    """
    if record.get("revert_status") != "pending":
        return False
    
    timestamp_str = record.get("timestamp")
    if not timestamp_str:
        return False
    
    timestamp = _parse_iso(timestamp_str)
    if not timestamp:
        return False
    
    # Apply 30-minute wall-clock grace period
    grace_cutoff = _utc_now() - timedelta(minutes=30)
    return timestamp < grace_cutoff


def process_pending_record(record: Dict, repo_root: Path, env: Dict[str, str]) -> Dict:
    """Process a single pending record, checking for regression and reverting if needed.
    
    Returns updated record with new revert_status and optionally revert_sha.
    """
    updated = dict(record)
    
    # Extract metrics
    before_metrics = record.get("before_metrics", {})
    after_metrics = record.get("after_metrics", {})
    drain_sha = record.get("commit_sha", "")
    issues = record.get("issues", [])
    
    if not drain_sha or len(drain_sha) != 40:
        # Can't process without valid SHA
        updated["revert_status"] = "not_needed"
        updated["revert_reason"] = "invalid_or_missing_sha"
        return updated
    
    # Check for fix commits (grace period)
    fix_commits = find_fix_commits(drain_sha, repo_root, env)
    if fix_commits:
        updated["revert_status"] = "not_needed"
        updated["revert_reason"] = f"fix_commits_found: {','.join(fix_commits[:3])}"
        return updated
    
    # Check for regression
    if not detect_regression(before_metrics, after_metrics, repo_root):
        updated["revert_status"] = "not_needed"
        updated["revert_reason"] = "no_regression_detected"
        return updated
    
    # Perform revert
    success, revert_sha_or_error = revert_drain_commit(drain_sha, repo_root, env)
    
    if success:
        updated["revert_status"] = "reverted"
        updated["revert_sha"] = revert_sha_or_error
        updated["revert_timestamp"] = _iso(_utc_now())
        
        # Reopen issues with label
        if issues:
            reopened = reopen_issues_with_label(
                issues, drain_sha, revert_sha_or_error, repo_root, env
            )
            updated["issues_reopened"] = reopened
    else:
        # Revert failed - mark as not_needed to avoid retry thrashing
        updated["revert_status"] = "not_needed"
        updated["revert_reason"] = f"revert_failed: {revert_sha_or_error}"
    
    return updated


def atomic_update_history(history_path: Path, updated_records: List[Dict]) -> None:
    """Atomically rewrite the JSONL history file with updated records.
    
    Uses tempfile + os.replace for atomic update.
    """
    # Write to temp file first
    temp_fd, temp_path = tempfile.mkstemp(
        dir=history_path.parent,
        prefix=".drain_log_",
        suffix=".tmp"
    )
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            for record in updated_records:
                line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                f.write(line)
        
        # Atomic replace
        os.replace(temp_path, history_path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def main() -> int:
    """Main orchestration entry point.
    
    Returns:
        0 on success, non-zero on error
    """
    repo_root = _REPO_ROOT
    env = _build_env(repo_root)
    
    # Load history
    history = DrainHistory.load(repo_root)
    records = history.read_all()
    
    if not records:
        print("No drain history found")
        return 0
    
    # Track if we made any updates
    updates_made = False
    updated_records = []
    
    for record in records:
        if should_check_regression(record):
            print(f"Checking regression for drain {record.get('commit_sha', '')[:8]}...")
            updated_record = process_pending_record(record, repo_root, env)
            updated_records.append(updated_record)
            
            if updated_record != record:
                updates_made = True
                status = updated_record.get("revert_status")
                if status == "reverted":
                    print(f"  ✓ Reverted: {updated_record.get('revert_sha', '')[:8]}")
                elif status == "not_needed":
                    reason = updated_record.get("revert_reason", "unknown")
                    print(f"  - No revert needed: {reason}")
        else:
            # Keep record unchanged
            updated_records.append(record)
    
    # Atomically update history if we made changes
    if updates_made:
        history_path = history.repo_root / ".claude" / "local" / "drain_log.jsonl"
        atomic_update_history(history_path, updated_records)
        print(f"Updated {sum(1 for r in updated_records if r.get('revert_status') == 'reverted')} records")
    else:
        print("No pending records to process")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())