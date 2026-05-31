"""Batch git finalization: commit, merge, and cleanup worktrees.

Orchestrates post-batch git operations after all features in a batch
pipeline have been implemented and tested.

Issue #333: Auto-commit, merge, and cleanup worktrees after batch pipeline.
"""

import os
import shutil
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


def cleanup_worktree(worktree_path: Path) -> Tuple[bool, Optional[str], Optional[Path]]:
    """Remove a git worktree and prune stale references.

    Args:
        worktree_path: Absolute path to worktree directory.

    Returns:
        (success, error, safe_cwd) tuple. safe_cwd is the main repo path
        if CWD was inside the worktree and was moved (Issue #410), else None.
    """
    if not worktree_path.exists():
        return False, f"Worktree not found: {worktree_path}", None

    # Find the main repo (parent of .worktrees/)
    # Worktree .git file points to main repo
    git_file = worktree_path / ".git"
    if not git_file.exists():
        return False, f"Not a git worktree: {worktree_path}", None

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
            return False, f"Cannot find main repository for worktree: {worktree_path}", None

    # Issue #410: Check if CWD is inside the worktree before deletion.
    # If so, change to main repo to prevent shell breakage.
    safe_cwd = None
    try:
        current_cwd = Path.cwd()
        worktree_str = str(worktree_path.resolve())
        cwd_str = str(current_cwd.resolve())
        if cwd_str.startswith(worktree_str):
            safe_cwd = main_repo
            if safe_cwd.exists():
                os.chdir(safe_cwd)
    except (OSError, RuntimeError):
        # If we can't determine CWD, proceed anyway
        pass

    # Remove worktree directory and prune
    # Use rm + prune for compatibility (git worktree remove requires git 2.17+)
    try:
        shutil.rmtree(worktree_path)
    except OSError as e:
        return False, f"Failed to remove worktree directory: {e}", safe_cwd

    # Prune stale worktree references
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )

    return True, None, safe_cwd


def batch_git_finalize(
    worktree_path: Path,
    features: List[str],
    issue_numbers: Optional[List[int]] = None,
    target_branch: str = "master",
    auto_stash: bool = True,
    cleanup: bool = True,
    mode: str = "worktree",
) -> Dict[str, Any]:
    """Finalize batch: commit changes, merge to target branch, cleanup worktree.

    Args:
        worktree_path: Absolute path to worktree directory (in worktree mode)
            or current working directory (in no_worktree mode).
        features: List of feature descriptions.
        issue_numbers: Optional GitHub issue numbers for "Closes #N".
        target_branch: Branch to merge into (default: master).
        auto_stash: Auto-stash uncommitted changes on target branch.
        cleanup: Remove worktree after successful merge.
        mode: ``"worktree"`` (default) runs the full commit→merge→cleanup
            sequence. ``"no_worktree"`` (Issue #1133) skips the merge and
            worktree-cleanup steps — only the per-issue commit is performed
            in-place on the current branch. The cluster PR is opened
            separately via :func:`open_cluster_pr`.

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
        "mode": mode,
    }

    # Issue #1133: no_worktree mode — commit in place, skip merge/cleanup
    if mode == "no_worktree":
        if not worktree_path.exists():
            result["error"] = f"Working tree path not found: {worktree_path}"
            return result
        if not (worktree_path / ".git").exists():
            result["error"] = f"Not a git directory: {worktree_path}"
            return result

        commit_ok, commit_sha, commit_err = commit_batch_changes(
            worktree_path, features, issue_numbers
        )
        if not commit_ok:
            result["error"] = commit_err
            return result

        result["commit_sha"] = commit_sha
        # In no_worktree mode, "merged" is implicit (we committed directly
        # to the current branch) and worktree_removed is N/A.
        result["merged"] = True
        result["worktree_removed"] = False
        result["success"] = True
        return result

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
        cleanup_ok, cleanup_err, safe_cwd = cleanup_worktree(worktree_path)
        result["worktree_removed"] = cleanup_ok
        result["safe_cwd"] = str(safe_cwd) if safe_cwd else str(main_repo)
        if not cleanup_ok:
            # Non-fatal: merge succeeded, just warn about cleanup
            result["success"] = True
            result["error"] = f"Merged successfully but cleanup failed: {cleanup_err}"
            return result

    result["success"] = True
    return result


def open_cluster_pr(
    issue_numbers: List[int],
    issue_titles: List[str],
    base_branch: str = "master",
) -> Dict[str, Any]:
    """Open a single multi-issue PR for a cluster of issues.

    Issue #1133: In ``--no-worktree`` cluster mode, one PR is opened at the
    end of the batch that closes all issues in the cluster. The PR title
    uses the ``feat: cluster #N1+#N2+...`` shorthand; the body lists each
    issue with its title and appends ``Closes #N`` lines so GitHub will
    auto-close every issue when the PR merges.

    Args:
        issue_numbers: Issue numbers to include in the PR (must be the
            same length as ``issue_titles``).
        issue_titles: Human-readable titles, one per issue_number.
        base_branch: Target branch for the PR (default: ``master``).

    Returns:
        ``{"success": True, "pr_url": "..."}`` on success or
        ``{"success": False, "error": "..."}`` on failure. Network /
        subprocess errors are caught and returned in the error field —
        callers should NOT treat them as exceptions.
    """
    if not issue_numbers:
        return {"success": False, "error": "Cannot open cluster PR with empty issue list"}

    if len(issue_numbers) != len(issue_titles):
        return {
            "success": False,
            "error": (
                f"issue_numbers ({len(issue_numbers)}) and issue_titles "
                f"({len(issue_titles)}) must be the same length"
            ),
        }

    title = f"feat: cluster {'+'.join(f'#{n}' for n in issue_numbers)}"
    body_lines = ["## Batch summary", ""]
    for n, t in zip(issue_numbers, issue_titles):
        body_lines.append(f"- #{n} {t}")
    body_lines.extend(["", "## Closes"])
    for n in issue_numbers:
        body_lines.append(f"Closes #{n}")
    body = "\n".join(body_lines)

    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--base",
                base_branch,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return {"success": True, "pr_url": result.stdout.strip()}
        return {"success": False, "error": result.stderr.strip() or "gh pr create failed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "gh pr create timed out after 60s"}
    except FileNotFoundError:
        return {"success": False, "error": "gh CLI not installed or not on PATH"}
