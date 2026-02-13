"""Batch git finalization: commit, merge, and cleanup worktrees.

Orchestrates post-batch git operations after all features in a batch
pipeline have been implemented and tested.

Issue #333: Auto-commit, merge, and cleanup worktrees after batch pipeline.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def commit_batch_changes(
    worktree_path: Path,
    features: List[str],
    issue_numbers: Optional[List[int]] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Commit all staged changes in the worktree.

    Args:
        worktree_path: Absolute path to worktree directory.
        features: List of feature descriptions for commit message.
        issue_numbers: Optional GitHub issue numbers for "Closes #N".

    Returns:
        (success, commit_sha, error) tuple.
    """
    # Check if there are changes to commit
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        return True, None, None

    # Stage all changes
    subprocess.run(
        ["git", "add", "-A"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )

    # Build commit message
    if features:
        feature_list = "\n".join(f"- {f}" for f in features)
        msg = f"feat: batch implementation\n\n{feature_list}"
    else:
        msg = "feat: batch implementation changes"

    if issue_numbers:
        closes = "\n".join(f"Closes #{n}" for n in issue_numbers)
        msg = f"{msg}\n\n{closes}"

    msg += "\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

    # Commit
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, None, f"Commit failed: {result.stderr.strip()}"

    # Get commit SHA
    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    commit_sha = sha_result.stdout.strip()

    return True, commit_sha, None


def cleanup_worktree(worktree_path: Path) -> Tuple[bool, Optional[str]]:
    """Remove a git worktree and prune stale references.

    Args:
        worktree_path: Absolute path to worktree directory.

    Returns:
        (success, error) tuple.
    """
    if not worktree_path.exists():
        return False, f"Worktree not found: {worktree_path}"

    # Find the main repo (parent of .worktrees/)
    # Worktree .git file points to main repo
    git_file = worktree_path / ".git"
    if not git_file.exists():
        return False, f"Not a git worktree: {worktree_path}"

    # Determine main repo path from worktree location
    # Convention: worktrees are in <repo>/.worktrees/<name>
    main_repo = worktree_path.parent.parent
    if not (main_repo / ".git").exists():
        # Try reading .git file for gitdir pointer
        if git_file.is_file():
            content = git_file.read_text().strip()
            if content.startswith("gitdir:"):
                gitdir = content.split(":", 1)[1].strip()
                # gitdir points to <repo>/.git/worktrees/<name>
                main_repo = Path(gitdir).parent.parent.parent
        if not (main_repo / ".git").exists():
            return False, f"Cannot find main repository for worktree: {worktree_path}"

    # Remove worktree directory and prune
    # Use rm + prune for compatibility (git worktree remove requires git 2.17+)
    import shutil
    try:
        shutil.rmtree(worktree_path)
    except OSError as e:
        return False, f"Failed to remove worktree directory: {e}"

    # Prune stale worktree references
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )

    return True, None


def batch_git_finalize(
    worktree_path: Path,
    features: List[str],
    issue_numbers: Optional[List[int]] = None,
    target_branch: str = "master",
    auto_stash: bool = True,
    cleanup: bool = True,
) -> Dict[str, Any]:
    """Finalize batch: commit changes, merge to target branch, cleanup worktree.

    Args:
        worktree_path: Absolute path to worktree directory.
        features: List of feature descriptions.
        issue_numbers: Optional GitHub issue numbers for "Closes #N".
        target_branch: Branch to merge into (default: master).
        auto_stash: Auto-stash uncommitted changes on target branch.
        cleanup: Remove worktree after successful merge.

    Returns:
        Dict with success, commit_sha, merged, worktree_removed, conflicts, error.
    """
    result: Dict[str, Any] = {
        "success": False,
        "commit_sha": None,
        "merged": False,
        "worktree_removed": False,
        "conflicts": [],
        "error": None,
    }

    # Validate worktree
    if not worktree_path.exists():
        result["error"] = f"Worktree not found: {worktree_path}"
        return result

    # Check it's a git directory
    git_marker = worktree_path / ".git"
    if not git_marker.exists():
        result["error"] = f"Not a git directory: {worktree_path}"
        return result

    # Find main repo
    main_repo = worktree_path.parent.parent
    if not (main_repo / ".git").exists():
        if git_marker.is_file():
            content = git_marker.read_text().strip()
            if content.startswith("gitdir:"):
                gitdir = content.split(":", 1)[1].strip()
                main_repo = Path(gitdir).parent.parent.parent

    # Verify target branch exists
    branch_check = subprocess.run(
        ["git", "rev-parse", "--verify", target_branch],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )
    if branch_check.returncode != 0:
        result["error"] = f"Target branch '{target_branch}' does not exist"
        return result

    # Check if target branch is dirty
    if not auto_stash:
        dirty_check = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=main_repo,
            capture_output=True,
            text=True,
        )
        if dirty_check.stdout.strip():
            result["error"] = (
                f"Target branch has uncommitted/dirty changes and auto_stash=False"
            )
            return result

    # Step 1: Commit changes in worktree
    commit_ok, commit_sha, commit_err = commit_batch_changes(
        worktree_path, features, issue_numbers
    )
    if not commit_ok:
        result["error"] = commit_err
        return result
    result["commit_sha"] = commit_sha

    # Step 2: Merge worktree branch to target
    # Get current branch name in worktree
    branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    worktree_branch = branch_result.stdout.strip()

    # Stash if needed
    stashed = False
    if auto_stash:
        stash_check = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=main_repo,
            capture_output=True,
            text=True,
        )
        if stash_check.stdout.strip():
            subprocess.run(
                ["git", "stash", "push", "-m", "batch-finalize-auto-stash"],
                cwd=main_repo,
                capture_output=True,
                text=True,
            )
            stashed = True

    # Merge
    merge_result = subprocess.run(
        ["git", "merge", "--no-ff", worktree_branch, "-m",
         f"Merge batch: {', '.join(features[:3])}{'...' if len(features) > 3 else ''}"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )

    if merge_result.returncode != 0:
        # Check for conflicts
        conflict_check = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=main_repo,
            capture_output=True,
            text=True,
        )
        conflicts = [f.strip() for f in conflict_check.stdout.strip().split("\n") if f.strip()]

        # Abort the failed merge
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=main_repo,
            capture_output=True,
            text=True,
        )

        # Restore stash if we stashed
        if stashed:
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=main_repo,
                capture_output=True,
                text=True,
            )

        result["conflicts"] = conflicts if conflicts else ["unknown conflict"]
        result["error"] = f"Merge failed: {merge_result.stderr.strip()}"
        return result

    result["merged"] = True

    # Restore stash if we stashed
    if stashed:
        subprocess.run(
            ["git", "stash", "pop"],
            cwd=main_repo,
            capture_output=True,
            text=True,
        )

    # Step 3: Cleanup worktree
    if cleanup:
        cleanup_ok, cleanup_err = cleanup_worktree(worktree_path)
        result["worktree_removed"] = cleanup_ok
        if not cleanup_ok:
            # Non-fatal: merge succeeded, just warn about cleanup
            result["success"] = True
            result["error"] = f"Merged successfully but cleanup failed: {cleanup_err}"
            return result

    result["success"] = True
    return result
