#!/usr/bin/env bash
#
# prune_sync — sync a plugin source subdir onto a deploy target WITH deletion
# propagation, behind a preview that is evaluated before anything is removed.
#
# WHY THIS EXISTS
# ---------------
# Three of the six rsync transports in this repo shipped without --delete. A
# module deleted from source therefore survived on those targets forever and
# stayed importable through the sys.path fallback to ~/.claude/lib. Measured:
# the five modules removed in 7c3a527e (workflow_tracker.py, native_tools.py,
# mcp_server_detector.py, git_hooks.py, context_skill_injector.py) were alive
# on all six targets while the deploy printed ALL VALIDATIONS PASSED.
#
# The two transports armed here are the REMOTE ones: five repos plus a home
# directory on another machine, over ssh, normally unattended. Every guard
# below is load-bearing.
#
# CONTRACT
# --------
#   prune_sync <src_dir> <dst_dir> <label>
#
#   src_dir  plugin source directory, WITH trailing slash, relative to the
#            source checkout (git ownership is resolved against it)
#   dst_dir  deploy target directory, WITH trailing slash
#   label    human name for messages, e.g. "spektiv/hooks" or "global/lib"
#
#   Returns 0 when the sync completed, 1 on refusal. On refusal NOTHING has
#   been deleted and NOTHING has been synced: every check runs against a
#   --dry-run preview computed with identical flags, so the refusal happens
#   before rsync is ever asked to modify the target.
#
#   Must be called with the working directory set to the source checkout, so
#   that `git log --all` can answer the ownership question (R3).
#
#   Reads the global array $remote_excludes_arr: the shared 18-pattern
#   exclusion set, already in --exclude=PATTERN form.
#
# WHY --max-delete IS NOT USED
# ----------------------------
# A cap is non-transactional: rsync deletes up to the cap and then fails, and
# it does not roll back. config/ holds 16 files, so a misresolved config path
# would wipe it entirely and still slip under a cap of 50. The preview is a
# SUBSTITUTION for the cap, not an addition — it computes the same deletion
# set with the same flags, and refusing on it means nothing was deleted at all.
#
# WHY THE EXCLUSIONS MUST STAY UNQUALIFIED
# ----------------------------------------
# An unqualified --exclude PROTECTS a receiver-side file from --delete (man
# rsync, FILTER RULES WHEN DELETING). That protection is the only thing keeping
# hooks/extensions/ (Issue #560) and the runtime .claude/ trees a hook wrote
# relative to its own cwd alive on every target. The delete-excluded flag
# removes exactly that protection and MUST NEVER be added here: it would turn
# this narrowing change into a wipe of consumer-local state. That flag is
# banned by test across all three deploy shell files, comments included, which
# is why this paragraph names it without its leading dashes.
#
# WHY THIS IS A SEPARATE FILE
# ---------------------------
# deploy-all.sh inlines this text into its ssh heredoc via
# $(cat "$SCRIPT_DIR/lib/prune_sync.sh"). Command-substitution output undergoes
# no further expansion and is never scanned by the local bash for quotes, so
# these 45 logic lines need no backslash escaping and are exempt from the
# no-apostrophes rule that governs the heredoc body itself. That eliminates the
# two failure classes that matter most there — a dropped backslash on \$target
# yielding an EMPTY rsync destination under --delete, and an apostrophe in a
# comment unbalancing the whole script under bash 3.2 — for exactly the lines
# where they would be catastrophic. It also makes the guard unit-testable by
# source-ing the file.
#
# It must nonetheless parse under bash 3.2 (Apple /bin/bash) and under the
# remote login zsh, which does NOT word-split unquoted parameters — hence the
# read loop rather than `for c in $candidates`.

prune_sync() {
    local src_dir="$1"
    local dst_dir="$2"
    local label="$3"

    # The exclusion set is not optional. An empty array here is
    # indistinguishable at the rsync call site from an unguarded --delete.
    if [ -z "${remote_excludes_arr+set}" ] || [ "${#remote_excludes_arr[@]}" -eq 0 ]; then
        echo "  ✗ REFUSED [$label]: the shared exclusion set is empty"
        echo "    Syncing with --delete and no exclusions would remove consumer-local"
        echo "    state (hooks/extensions/, Issue #560) and runtime .claude/ trees from"
        echo "    $dst_dir"
        echo "    Nothing was deleted and nothing was synced for $label."
        echo "    REQUIRED NEXT ACTION: rebuild the exclusion list and re-run —"
        echo "      python3 plugins/autonomous-dev/scripts/deploy_state.py excludes"
        return 1
    fi

    # PRE-FLIGHT (primary guard). An empty or misresolved source subdir plus
    # --delete empties the matching subtree on the target. `|| true` absorbs the
    # SIGPIPE that `head -1` sends to `find`, which would otherwise fail the
    # pipeline under `set -o pipefail`.
    local probe
    probe=$(find "$src_dir" -type f 2>/dev/null | head -1 || true)
    if [ -z "$probe" ]; then
        echo "  ✗ REFUSED [$label]: source holds no regular files"
        echo "    source: $src_dir"
        echo "    Syncing it with --delete would empty $dst_dir"
        echo "    Nothing was deleted and nothing was synced for $label."
        echo "    REQUIRED NEXT ACTION: verify the checkout is complete —"
        echo "      git status && git checkout -- $src_dir"
        echo "    then re-run scripts/deploy-all.sh."
        return 1
    fi

    # PREVIEW. Identical flags to the live sync below, minus --dry-run, so the
    # deletion set computed here is exactly the one that would be executed —
    # including the receiver-side protection the excludes confer.
    local preview
    preview=$(rsync -a --delete --delete-after --dry-run --itemize-changes --exclude='extensions/' --exclude='.claude/' "${remote_excludes_arr[@]}" "$src_dir" "$dst_dir" 2>&1) || {
        echo "  ✗ REFUSED [$label]: the deletion preview itself failed"
        echo "    source: $src_dir"
        echo "    target: $dst_dir"
        echo "$preview"
        echo "    Nothing was deleted and nothing was synced for $label."
        echo "    REQUIRED NEXT ACTION: run the preview by hand and read the rsync error above."
        return 1
    }

    local candidates
    candidates=$(printf "%s\n" "$preview" | grep '^\*deleting' | sed 's/^\*deleting *//' || true)

    local count
    count=$(printf "%s" "$candidates" | grep -c . || true)

    # R1 — wipe cap. Largest legitimate deletion evidenced in this repo: 5 files
    # (7c3a527e). Unlike --max-delete this is evaluated BEFORE anything is
    # removed, so it is a refusal rather than a half-finished wipe.
    if [ "$count" -gt 50 ]; then
        echo "  ✗ REFUSED [$label]: $count deletion candidates exceeds the cap of 50"
        echo "    target: $dst_dir"
        echo "    That is far beyond any legitimate deletion, so it is treated as a wipe."
        echo "    Nothing was deleted and nothing was synced for $label."
        echo "    REQUIRED NEXT ACTION: inspect what the target holds that no source accounts for —"
        echo "      python3 plugins/autonomous-dev/scripts/deploy_state.py check --repo <target repo>"
        return 1
    fi

    # R2 — protection self-check, a negative control wired into production.
    # rsync must never offer a candidate under .claude/ or extensions/, because
    # both are excluded and an exclude protects the receiver side. If one shows
    # up, the exclusion machinery is not doing what this function assumes, and
    # the correct response is to stop rather than to trust the rest of the set.
    local unprotected
    unprotected=$(printf "%s\n" "$candidates" | grep -E '(^|/)(\.claude|extensions)(/|$)' || true)
    if [ -n "$unprotected" ]; then
        echo "  ✗ REFUSED [$label]: a protected path appeared in the deletion set"
        echo "$unprotected" | sed 's/^/      /'
        echo "    target: $dst_dir"
        echo "    These are excluded, so rsync should have protected them on the receiver."
        echo "    Their presence here means the exclusion set did not reach this call."
        echo "    Nothing was deleted and nothing was synced for $label."
        echo "    REQUIRED NEXT ACTION: verify the exclusion array reached rsync intact, then re-run."
        return 1
    fi

    # R3 — ownership via git history. For each candidate, ask the source
    # checkout whether the plugin has EVER owned that path. A human-authored
    # .claude/agents/my-agent.md has never existed under the plugin source path,
    # has no history, and the sync refuses. This removes the category rather
    # than enumerating known-stale filenames, and it fails CLOSED on a shallow
    # or absent checkout, where every lookup comes back empty.
    local unowned=""
    local candidate
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        if [ -z "$(git log --all --oneline -1 -- "$src_dir$candidate" 2>/dev/null)" ]; then
            unowned="$unowned
      $candidate"
        fi
    done <<PRUNE_SYNC_CANDIDATES
$candidates
PRUNE_SYNC_CANDIDATES

    if [ -n "$unowned" ]; then
        echo "  ✗ REFUSED [$label]: deletion candidate(s) the plugin has never owned"
        echo "$unowned" | sed '/^[[:space:]]*$/d'
        echo "    target: $dst_dir"
        echo "    No commit reachable from any ref has ever carried these under $src_dir,"
        echo "    so they are consumer-local or human-authored, not stale plugin artifacts."
        echo "    A shallow checkout produces the same answer, deliberately: this fails closed."
        echo "    Nothing was deleted and nothing was synced for $label."
        echo "    REQUIRED NEXT ACTION: move the file out of the deployed subdir, or add it to"
        echo "    the plugin source, then re-run scripts/deploy-all.sh."
        return 1
    fi

    # LIVE SYNC. Same flags as the preview, minus --dry-run. --delete-after
    # defers deletion until the transfer completes, so a mid-transfer failure
    # leaves nothing deleted.
    rsync -a --delete --delete-after --exclude='extensions/' --exclude='.claude/' "${remote_excludes_arr[@]}" "$src_dir" "$dst_dir" || {
        echo "  ✗ [$label]: rsync failed during the live sync — target may be partial"
        echo "    source: $src_dir"
        echo "    target: $dst_dir"
        echo "    REQUIRED NEXT ACTION: re-run scripts/deploy-all.sh; if it fails again, read the rsync error above."
        return 1
    }

    if [ "$count" -gt 0 ]; then
        echo "    pruned $count stale file(s) from $label"
    fi
    return 0
}
