#!/usr/bin/env python3
"""
Cloud drain telemetry controller — suppresses telemetry commits for no_drainable_cluster.

Issue #1437: 96% of cloud-drain fires exit with no_drainable_cluster while emitting
FIRE_START/FIRE_END telemetry commits. This hook controls when telemetry commits
are created vs when only JSONL logging occurs.
"""

# Issue #953 pattern (added for #1471): Hook safety — wrap main() with
# safe_main so hook crashes never block Claude Code.
import sys as _sys_953
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any


def should_emit_telemetry_commit(exit_reason: str) -> bool:
    """
    Determine if a telemetry commit should be created based on exit reason.
    
    Returns False for no_drainable_cluster (no work done).
    Returns True for all other exit reasons (real events).
    """
    # These exit reasons indicate no real work was attempted
    no_work_reasons = {
        "no_drainable_cluster",
        "queue_empty",
        "all_clusters_high_severity",
    }
    
    return exit_reason not in no_work_reasons


def append_to_cloud_runs_jsonl(
    fire_type: str,
    cluster: Optional[str] = None,
    exit_reason: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> None:
    """
    Always append to .claude/logs/cloud-runs.jsonl regardless of commit decision.
    
    The JSONL is the source of truth; git commits are just visibility.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    log_path = repo_root / ".claude" / "logs" / "cloud-runs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fire_type": fire_type,
        "cluster": cluster,
        "exit_reason": exit_reason,
        "suppressed_commit": not should_emit_telemetry_commit(exit_reason or ""),
    }
    
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def create_telemetry_commit(
    fire_type: str,
    cluster: Optional[str] = None,
    exit_reason: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> bool:
    """
    Create a telemetry commit if appropriate for the exit reason.
    
    Returns True if commit was created, False if suppressed.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    # Always log to JSONL
    append_to_cloud_runs_jsonl(fire_type, cluster, exit_reason, repo_root)
    
    # Check if we should create a git commit
    if not should_emit_telemetry_commit(exit_reason or ""):
        print(
            f"Telemetry commit suppressed for exit_reason={exit_reason} (Issue #1437)",
            file=sys.stderr
        )
        return False
    
    # Create the telemetry commit
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cluster_info = f"cluster={cluster}" if cluster else (exit_reason or "unknown")
    
    message = f"telemetry(cloud-drain): {fire_type} {timestamp} {cluster_info}"
    
    try:
        # Stage the JSONL file
        subprocess.run(
            ["git", "add", ".claude/logs/cloud-runs.jsonl"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
        )
        
        # Create the commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
        )
        
        print(f"Created telemetry commit: {message}", file=sys.stderr)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to create telemetry commit: {e}", file=sys.stderr)
        return False


def main():
    """
    Hook entry point for CloudSchedule events.
    
    This can be invoked directly or integrated with the drain workflow.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Cloud drain telemetry controller")
    parser.add_argument("--fire-type", choices=["FIRE_START", "FIRE_END"], required=True)
    parser.add_argument("--cluster", help="Cluster being drained (comma-separated issue numbers)")
    parser.add_argument("--exit-reason", help="Exit reason (e.g., no_drainable_cluster)")
    parser.add_argument("--repo-root", type=Path, help="Repository root path")
    
    args = parser.parse_args()
    
    created = create_telemetry_commit(
        fire_type=args.fire_type,
        cluster=args.cluster,
        exit_reason=args.exit_reason,
        repo_root=args.repo_root,
    )
    
    sys.exit(0 if created or not should_emit_telemetry_commit(args.exit_reason or "") else 1)


if __name__ == "__main__":
    _safe_main_953(main)