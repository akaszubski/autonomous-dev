#!/usr/bin/env bash
set -euo pipefail

# Issue #1130: Remove .worktrees/* entries whose branch is merged into master.
# Skips: main worktree, unmerged branches, unreachable detached HEADs.
# Maintainer-facing recovery tool — invoked manually, not by harness.

TARGET="master"
DRY_RUN=0

usage() {
    cat <<'USAGE'
Usage: cleanup-worktrees.sh [OPTIONS]

Remove worktrees under .worktrees/ whose branch is merged into master.
Skip everything else (unmerged, detached-unreachable, main worktree).

Options:
  --dry-run    Print what would be removed without removing
  -h, --help   Show this help and exit
USAGE
}

# Argument parsing
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 1 ;;
    esac
done

# Preflight: must be in a git repo
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo "ERROR: not inside a git repository" >&2
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Preflight: target branch must exist
if ! git -C "$REPO_ROOT" rev-parse --verify "$TARGET" > /dev/null 2>&1; then
    echo "ERROR: target branch '$TARGET' not found locally" >&2
    exit 1
fi

# Parse `git worktree list --porcelain` and classify each entry.
# Records are blank-line separated: 'worktree <path>', 'HEAD <sha>', then either
# 'branch refs/heads/<name>' or 'detached'.
REMOVED=0
SKIPPED=0
PRUNED=0
PRUNE_NEEDED=0

# Process one parsed worktree record.
process_record() {
    local path="$1" head="$2" br="$3" detached="$4"
    if [[ -z "$path" ]]; then return; fi

    # MAIN: skip main worktree (repo root itself)
    if [[ "$path" == "$REPO_ROOT" ]]; then
        echo "MAIN: $path"
        return
    fi

    # Missing on disk → prune via git worktree prune later
    if [[ ! -d "$path" ]]; then
        echo "PRUNED: $path (missing)"
        PRUNE_NEEDED=1
        PRUNED=$((PRUNED + 1))
        return
    fi

    # Branched worktree: check merge status
    if [[ $detached -eq 0 && -n "$br" ]]; then
        local branch_name="${br#refs/heads/}"
        if git -C "$REPO_ROOT" merge-base --is-ancestor "$br" "$TARGET" 2>/dev/null; then
            # Merged — safe to remove
            if [[ $DRY_RUN -eq 1 ]]; then
                echo "WOULD REMOVE: $path (branch $branch_name merged)"
                REMOVED=$((REMOVED + 1))
            else
                if git -C "$REPO_ROOT" worktree remove --force "$path" 2>/dev/null; then
                    echo "REMOVED: $path (branch $branch_name merged)"
                    REMOVED=$((REMOVED + 1))
                else
                    echo "ERROR: failed to remove $path" >&2
                fi
            fi
        else
            echo "SKIPPED: $path (branch $branch_name unmerged)"
            SKIPPED=$((SKIPPED + 1))
        fi
        return
    fi

    # Detached HEAD: check reachability from master
    if [[ $detached -eq 1 && -n "$head" ]]; then
        if git -C "$REPO_ROOT" merge-base --is-ancestor "$head" "$TARGET" 2>/dev/null; then
            if [[ $DRY_RUN -eq 1 ]]; then
                echo "WOULD REMOVE: $path (detached, reachable)"
                REMOVED=$((REMOVED + 1))
            else
                if git -C "$REPO_ROOT" worktree remove --force "$path" 2>/dev/null; then
                    echo "REMOVED: $path (detached, reachable)"
                    REMOVED=$((REMOVED + 1))
                else
                    echo "ERROR: failed to remove $path" >&2
                fi
            fi
        else
            echo "SKIPPED: $path (detached, unreachable)"
            SKIPPED=$((SKIPPED + 1))
        fi
        return
    fi
}

# Read porcelain output and process records (blank-line-separated)
wt_path=""
head_sha=""
branch=""
is_detached=0

while IFS= read -r line; do
    if [[ -z "$line" ]]; then
        # End of record — process it
        process_record "$wt_path" "$head_sha" "$branch" "$is_detached"
        wt_path=""; head_sha=""; branch=""; is_detached=0
    elif [[ "$line" =~ ^worktree\ (.+)$ ]]; then
        wt_path="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^HEAD\ (.+)$ ]]; then
        head_sha="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^branch\ (.+)$ ]]; then
        branch="${BASH_REMATCH[1]}"
    elif [[ "$line" == "detached" ]]; then
        is_detached=1
    fi
done < <(git -C "$REPO_ROOT" worktree list --porcelain)

# Process trailing record (porcelain output may not end with blank line)
process_record "$wt_path" "$head_sha" "$branch" "$is_detached"

# Prune stale entries if needed
if [[ $PRUNE_NEEDED -eq 1 && $DRY_RUN -eq 0 ]]; then
    git -C "$REPO_ROOT" worktree prune
fi

# Summary
echo "---"
if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY RUN: would remove worktrees (no changes made). Summary: removed=$REMOVED skipped=$SKIPPED pruned=$PRUNED"
else
    echo "Summary: removed=$REMOVED skipped=$SKIPPED pruned=$PRUNED"
fi
exit 0
