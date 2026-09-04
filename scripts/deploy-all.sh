#!/usr/bin/env bash
#
# Deploy autonomous-dev plugin to all repos on both Macs.
# Combines deploy_local.sh (with validation) and deploy-to-repos.sh (with remote).
#
# Usage:
#   ./scripts/deploy-all.sh                    # Deploy everywhere
#   ./scripts/deploy-all.sh --local            # Local machine only
#   ./scripts/deploy-all.sh --remote           # Mac Studio only
#   ./scripts/deploy-all.sh --dry-run          # Preview what would happen
#   ./scripts/deploy-all.sh --no-global        # Skip global ~/.claude/ sync entirely
#   ./scripts/deploy-all.sh --global-settings  # Opt-in: register hooks in ~/.claude/settings.json
#                                              # (Issue #995: default is project-local hooks only;
#                                              #  --no-global wins over --global-settings)
#   ./scripts/deploy-all.sh --skip-validate    # Skip post-deploy validation
#   ./scripts/deploy-all.sh --dirty            # Ship uncommitted work (Issue #1610).
#                                              # Without it, a dirty deployed subdir is
#                                              # REFUSED by name: this script copies the
#                                              # working tree, so uncommitted code would
#                                              # reach the executing hook stack unreviewed.
#
# Configuration (override via env vars):
#   REMOTE_HOST  - SSH host (auto-detects: 10.55.0.2 on LAN, 100.103.205.63 via Tailscale)
#   LOCAL_REPOS  - Space-separated local repo names (default: autonomous-dev anyclaude realign spektiv)
#   REMOTE_REPOS - Space-separated remote repo names (default: autonomous-dev anyclaude realign spektiv)
#
# What gets deployed:
#   Global (~/.claude/): hooks, lib, config (shared across all repos)
#   Per-repo (<repo>/.claude/): hooks, commands, agents, lib, config, skills, scripts, templates

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_SRC="$REPO_DIR/plugins/autonomous-dev"
GLOBAL_DEST="$HOME/.claude"

# Try local network first, fall back to Tailscale
if [ -z "${REMOTE_HOST:-}" ]; then
    if ssh -o ConnectTimeout=3 -o BatchMode=yes andrewkaszubski@10.55.0.2 true 2>/dev/null; then
        REMOTE_HOST="andrewkaszubski@10.55.0.2"
    else
        REMOTE_HOST="andrewkaszubski@100.103.205.63"
    fi
fi
LOCAL_REPOS="${LOCAL_REPOS:-autonomous-dev realign spektiv homeassistant vllm-mlx}"
REMOTE_REPOS="${REMOTE_REPOS:-autonomous-dev realign spektiv homeassistant vllm-mlx}"
SUBDIRS="hooks commands agents lib templates config skills scripts"
GLOBAL_SUBDIRS="hooks lib config"

# Issue #1610: these patterns are the DEPLOYED SET's definition. They are the
# single source of truth shared with plugins/autonomous-dev/scripts/deploy_state.py
# (`rsync_exclude_patterns()`); a regression test asserts set equality, because a
# pattern added to one and not the other silently changes what the provenance
# gate measures relative to what rsync actually ships.
#
# Measured 2026-08-22: without these, rsync shipped 38 `,cover` files, 13
# .DS_Store, an htmlcov/ tree and a stray coverage.xml into every consumer
# repo's executing .claude/. They are gitignored, so `git status` could not see
# them and the gate reported a clean tree while they were deployed.
#
# NOTE: --delete does NOT remove already-deployed copies of excluded files
# (rsync protects excluded paths on the receiver). Existing strays in consumer
# repos need a one-time manual clean; --delete-excluded is deliberately NOT
# used because it would also delete hooks/extensions/, which is consumer-local
# state that Issue #560 exists to preserve.
DEPLOY_EXCLUDES=(
    --exclude='__pycache__/'
    --exclude='extensions/'
    --exclude='htmlcov/'
    --exclude='.pytest_cache/'
    --exclude='.mypy_cache/'
    --exclude='.ruff_cache/'
    --exclude='*.pyc'
    --exclude='*.pyo'
    --exclude='*,cover'
    --exclude='.DS_Store'
    --exclude='.coverage'
    --exclude='.coverage.*'
    --exclude='coverage.xml'
    --exclude='*.backup'
    --exclude='*.orig'
    --exclude='*.rej'
    --exclude='*.swp'
    # NARROWED (Issue #1610 final remediation): was three FILENAME globs
    # (*-session.md, *-pipeline.json, *.pipeline.json). A filename class is a
    # blind spot with a public name — anything excluded is invisible to the
    # provenance record AND to `check`'s reverse comparison, in both
    # directions, so an attacker-named `payload-session.md` rode in unmeasured.
    # Measured 2026-08-22: every file matching any of the three globs, in the
    # repo and in every deployed tree, lived under docs/sessions/ (one
    # instance); zero instances of either pipeline glob existed anywhere. The
    # path form loses no coverage and closes the naming class.
    --exclude='docs/sessions/'
)

# Key files to validate after deploy
KEY_FILES="hooks/unified_pre_tool.py hooks/session_activity_logger.py lib/pipeline_intent_validator.py"
# Stale hooks that should have been removed in previous cleanup
STALE_HOOKS="pre_tool_use.py auto_approve_tool.py unified_pre_tool_use.py"

# Parse flags
DO_LOCAL=true
DO_REMOTE=true
DO_GLOBAL=true
# Issue #995: project-local hooks are now the default. Registration of
# autonomous-dev hooks in ~/.claude/settings.json is OPT-IN via --global-settings.
# Hook FILES still cache to ~/.claude/hooks/ via the existing $GLOBAL_SUBDIRS sync;
# this flag only controls whether settings.json registers them as active.
DO_GLOBAL_SETTINGS=false
DRY_RUN=false
SKIP_VALIDATE=false
ERRORS=0
# Issue #1610: this script copies the WORKING TREE, not HEAD. Uncommitted work
# under the deployed subdirs therefore reaches the executing hook stack,
# bypassing the reviewer, the security auditor, doc-master and the commit gate
# at once. Default is refuse-and-name; --dirty is the explicit opt-in for the
# legitimate iterate-and-test loop on hook code.
ALLOW_DIRTY=false
DEPLOY_STATE="$PLUGIN_SRC/scripts/deploy_state.py"
DEPLOYED_TARGETS=()

for arg in "$@"; do
    case "$arg" in
        --local)  DO_REMOTE=false ;;
        --remote) DO_LOCAL=false; DO_GLOBAL=false; DO_GLOBAL_SETTINGS=false ;;
        --dry-run) DRY_RUN=true ;;
        --no-global) DO_GLOBAL=false; DO_GLOBAL_SETTINGS=false ;;
        --global-settings) DO_GLOBAL_SETTINGS=true ;;
        --skip-validate) SKIP_VALIDATE=true ;;
        --dirty) ALLOW_DIRTY=true ;;
        --help|-h)
            # Print the leading comment block (line 2 through the first line
            # that is not a comment).
            #
            # OUT-OF-SCOPE CHANGE, stated rather than smuggled (Issue #1610):
            # this replaced `head -21 "$0" | tail -20`, which was already
            # truncating --help output — the --dirty usage lines this issue adds
            # pushed the block past line 21, so the fixed line numbers would have
            # silently cut the last entries. The awk form is line-number-free, so
            # adding usage lines can never truncate --help again. It is a fix for
            # a class the issue's own change would otherwise have triggered, not
            # a drive-by cleanup.
            awk 'NR>1 { if ($0 !~ /^#/) exit; print }' "$0"
            exit 0
            ;;
        *) echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

# Issue #995 precedence: --no-global wins over --global-settings.
# If --no-global was passed, we already cleared DO_GLOBAL_SETTINGS in its case
# branch above. We re-assert it here in case flag order put --global-settings
# AFTER --no-global on the command line.
if ! $DO_GLOBAL; then
    DO_GLOBAL_SETTINGS=false
fi

# --- Helpers ---

log_ok()   { echo "    ✓ $1"; }
log_fail() { echo "    ✗ $1"; ERRORS=$((ERRORS + 1)); }
log_warn() { echo "    ⚠ $1"; }

checksum() {
    md5 -q "$1" 2>/dev/null || md5sum "$1" 2>/dev/null | cut -d' ' -f1
}

# --- Deploy functions ---

# Issue #1610 (final remediation, BLOCKING C): remove compiled-bytecode caches
# from the deployed tree after every copy.
#
# WHY. `.pyc` is the one excluded class that executes with NO registration step.
# It is excluded from the deployed set, so `deploy_state.py` never digests it and
# `check`'s reverse comparison cannot see it — in either direction. A tampered
# `__pycache__/<mod>.cpython-3XX.pyc` whose 16-byte header is forged to match an
# untouched `.py` is loaded in preference to that source, and the tool reports
# "N files match the deploy record", exit 0, because the `.py` digest genuinely
# does match. A bare sourceless `<mod>.pyc` on the path is importable too, so
# both shapes are removed, not just the cache directory.
#
# The precondition is write access to `.claude/` — identical to the injected-`.py`
# case, which is already treated as blocking. Exposure is not theoretical: 995
# `.pyc` under this repo's `.claude/{hooks,lib}`, 1,001 under `~/.claude`, and
# `unified_pre_tool.py` inserts those directories at `sys.path[0]` at five sites.
# `rsync -a --delete` does NOT clear them, because rsync protects excluded paths
# on the receiver and `--delete-excluded` is deliberately not used (Issue #560).
#
# CHOSEN over the stronger alternative (have `check` recompile each recorded
# `.py` and compare against any cache entry whose magic matches the running
# interpreter). That alternative must report "unverifiable" for every cache entry
# built by a different interpreter — which across a 3.13/3.14, two-machine fleet
# is the COMMON case, not the edge case. A check that says "unverifiable"
# routinely is the cry-wolf failure this project treats as a defect in its own
# right. Purging bounds a planted `.pyc` to a single deploy cycle, is
# deterministic, and has no false-positive surface. It cannot detect one planted
# BETWEEN deploys; nothing cheap can, because the running interpreter regenerates
# these constantly, so presence alone carries no signal.
#
# `extensions/` is pruned: Issue #560 makes it consumer-local state.
purge_bytecode() {
    local target="$1"
    local subdir
    for subdir in $SUBDIRS; do
        [ -d "$target/$subdir" ] || continue
        find "$target/$subdir" \
            -name extensions -type d -prune -o \
            \( -name '__pycache__' -type d -o -name '*.pyc' -o -name '*.pyo' \) \
            -print0 2>/dev/null \
            | xargs -0 rm -rf 2>/dev/null || true
    done
}

fix_permissions() {
    local target="$1"
    # Hooks and scripts must be executable
    find "$target/hooks" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "$target/hooks" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    find "$target/scripts" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "$target/scripts" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    # Libraries should be readable (not executable)
    find "$target/lib" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
}

deploy_global() {
    echo "Global (~/.claude):"
    if $DRY_RUN; then
        echo "  [dry-run] Would sync $GLOBAL_SUBDIRS"
        if $DO_GLOBAL_SETTINGS; then
            echo "  [dry-run] Would sync global settings.json hooks"
        else
            echo "  [dry-run] Would skip global settings.json hooks (use --global-settings to opt in)"
        fi
        return
    fi

    # DELETION PROPAGATES HERE TOO (follow-up to Issue #1610).
    #
    # `7c3a527e` deleted five lib modules from source. This script printed ALL
    # VALIDATIONS PASSED and all five survived in ~/.claude/lib, because this
    # was the only LOCAL transport without `--delete` (:281 has always had it,
    # and purged 5 of 5 across five repos). `sys.path` falls back to
    # ~/.claude/lib, so `import workflow_tracker` still resolved a module that
    # exists in no source tree and in no consumer repo. deploy_state.py:608-609
    # had already named this transport by hand; #1610 built the detector and
    # chose to REPORT. This makes it refuse. The REMOTE global target (:490)
    # keeps the identical defect on purpose — see :391-394 — and is a follow-up.
    #
    # THE INVARIANT: deletion scope ⊂ measurement scope. $DEPLOY_EXCLUDES is
    # deliberately NOT touched: it is set-equality-pinned to deploy_state.py's
    # rsync_exclude_patterns() and it defines what the provenance gate MEASURES
    # for every target. The two exclusions below are local to this one call, so
    # they narrow what `--delete` may REMOVE without narrowing what `target_only`
    # can SEE. Runtime state protected here stays listed as target-only.
    #
    #   --exclude='.claude/'   A CLASS, not an enumeration. rsync matches a
    #                          pattern with no internal slash against the final
    #                          path component at ANY depth, and an exclude
    #                          PROTECTS a receiver-side file from --delete (man
    #                          rsync, FILTER RULES WHEN DELETING). Any .claude/
    #                          nested inside a deployed subdir is runtime state
    #                          a hook wrote relative to its own cwd: on this
    #                          machine ~/.claude/hooks/.claude/logs/activity/
    #                          holds 52,502 bytes of telemetry in no commit,
    #                          plus the live session's heartbeat. The source
    #                          carries no such directory under hooks/lib/config,
    #                          so the pattern is a no-op on the send side and
    #                          pure protection on the receive side.
    #   --exclude=extensions/  Issue #560 consumer-local state; same shape :281
    #                          already uses.
    #
    # --max-delete=50 is the SECOND line of defence, not the first. Largest
    # legitimate deletion evidenced in this repo: 5 files (7c3a527e). Measured
    # 2026-09-05, regular files excluding __pycache__: hooks 176, lib 314,
    # config 16. A wholesale wipe of hooks or lib trips the cap; a misresolved
    # `config` would delete only 16 and slip UNDER it — which is exactly why the
    # pre-flight below is the primary guard.
    for subdir in $GLOBAL_SUBDIRS; do
        if [ -d "$PLUGIN_SRC/$subdir" ]; then
            # PRE-FLIGHT (primary guard). An empty or misresolved source subdir
            # plus --delete empties the matching subtree inside $HOME. `|| true`
            # absorbs the SIGPIPE `head -1` sends to `find`, which would
            # otherwise fail the pipeline under `set -o pipefail` (:31).
            local src_probe
            src_probe=$(find "$PLUGIN_SRC/$subdir" -type f 2>/dev/null | head -1 || true)
            if [ -z "$src_probe" ]; then
                echo "  ✗ REFUSED: source subdir '$subdir' holds no regular files"
                echo "    source: $PLUGIN_SRC/$subdir"
                echo "    Syncing it with --delete would empty $GLOBAL_DEST/$subdir/."
                echo "    Nothing was deleted for '$subdir'."
                echo "    REQUIRED NEXT ACTION: verify the checkout is complete —"
                echo "      git status && git checkout -- plugins/autonomous-dev/$subdir"
                echo "    then re-run this script."
                exit 1
            fi
            mkdir -p "$GLOBAL_DEST/$subdir"
            local rc=0
            rsync -a --delete --max-delete=50 --exclude=extensions/ --exclude='.claude/' "${DEPLOY_EXCLUDES[@]}" "$PLUGIN_SRC/$subdir/" "$GLOBAL_DEST/$subdir/" || rc=$?
            if [ "$rc" -eq 25 ]; then
                # A bare exit 25 with no explanation is the shape that trains
                # bypass. Name the subdir, the cap, and the next action.
                echo "  ✗ REFUSED: pruning '$subdir' hit --max-delete=50"
                echo "    target: $GLOBAL_DEST/$subdir/"
                echo "    More than 50 files in the global target are unaccounted for by"
                echo "    $PLUGIN_SRC/$subdir. That is far beyond any legitimate deletion"
                echo "    (largest evidenced: 5 files), so this is treated as a wipe."
                echo "    WARNING: rsync does NOT roll back — files deleted before the cap"
                echo "    was reached stay deleted."
                echo "    REQUIRED NEXT ACTION: inspect what the target holds that no source"
                echo "    accounts for —"
                echo "      python3 plugins/autonomous-dev/scripts/deploy_state.py check --repo ~"
                exit 1
            elif [ "$rc" -ne 0 ]; then
                echo "  ✗ rsync failed for '$subdir' (exit $rc) — global target may be partial"
                exit "$rc"
            fi
        fi
    done
    purge_bytecode "$GLOBAL_DEST"
    fix_permissions "$GLOBAL_DEST"
    DEPLOYED_TARGETS+=("$GLOBAL_DEST")
    echo "  Synced: $GLOBAL_SUBDIRS"

    # Sync settings.json hook registrations (opt-in via --global-settings, Issue #995)
    if $DO_GLOBAL_SETTINGS; then
        python3 "$PLUGIN_SRC/scripts/sync_settings_hooks.py" --global 2>/dev/null \
            && echo "  Synced global settings.json hooks" \
            || echo "  ⚠ global settings hook sync failed"
    else
        echo "  Skipped global settings.json hooks (use --global-settings to opt in)"
    fi
}

deploy_repo() {
    local repo_path="$1"
    local name="$(basename "$repo_path")"
    local target="$repo_path/.claude"

    if [ ! -d "$repo_path" ]; then
        echo "  SKIP $name (not found)"
        return
    fi
    if [ ! -d "$target" ]; then
        echo "  SKIP $name (no .claude/)"
        return
    fi

    if $DRY_RUN; then
        echo "  [dry-run] Would deploy to $name"
        return
    fi

    for subdir in $SUBDIRS; do
        if [ -d "$PLUGIN_SRC/$subdir" ]; then
            mkdir -p "$target/$subdir"
            rsync -a --delete --exclude=extensions/ "${DEPLOY_EXCLUDES[@]}" "$PLUGIN_SRC/$subdir/" "$target/$subdir/"
        fi
    done
    purge_bytecode "$target"
    fix_permissions "$target"
    DEPLOYED_TARGETS+=("$target")
    echo "  Deployed: $name"

    # Sync settings.json hook registrations
    python3 "$PLUGIN_SRC/scripts/sync_settings_hooks.py" --repo "$repo_path" 2>/dev/null && echo "  Synced $name settings.json hooks" || echo "  ⚠ $name settings hook sync failed"
}

deploy_remote() {
    echo "=== Remote ($REMOTE_HOST) ==="

    # Check connectivity first
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "echo ok" >/dev/null 2>&1; then
        echo "  SKIP (cannot connect to $REMOTE_HOST)"
        return
    fi

    if $DRY_RUN; then
        echo "  [dry-run] Would git pull + deploy to $REMOTE_REPOS"
        return
    fi

    # Build validation script for remote
    local validate_script=""
    if ! $SKIP_VALIDATE; then
        validate_script="
echo ''
echo '  Post-deploy validation:'
errors=0
for repo in $REMOTE_REPOS; do
    target=\"\$HOME/Dev/\$repo/.claude\"
    [ ! -d \"\$target\" ] && continue
    # Syntax check
    if python3 -c \"import ast; ast.parse(open('\$target/hooks/unified_pre_tool.py').read())\" 2>/dev/null; then
        echo \"    ✓ \$repo: unified_pre_tool.py parses cleanly\"
    else
        echo \"    ✗ \$repo: unified_pre_tool.py SYNTAX ERROR\"
        errors=\$((errors + 1))
    fi
    # NATIVE_TOOLS check
    if grep -q 'NATIVE_TOOLS' \"\$target/hooks/unified_pre_tool.py\" 2>/dev/null; then
        echo \"    ✓ \$repo: NATIVE_TOOLS fast path present\"
    else
        echo \"    ✗ \$repo: NATIVE_TOOLS fast path MISSING\"
        errors=\$((errors + 1))
    fi
    # Agent tool fix check (the observability fix we just made)
    if grep -q '\"Agent\"' \"\$target/hooks/session_activity_logger.py\" 2>/dev/null; then
        echo \"    ✓ \$repo: session_activity_logger handles Agent tool\"
    else
        echo \"    ✗ \$repo: session_activity_logger MISSING Agent tool handling\"
        errors=\$((errors + 1))
    fi
    # pipeline_intent_validator check
    if grep -q 'AGENT_TOOL_NAMES' \"\$target/lib/pipeline_intent_validator.py\" 2>/dev/null; then
        echo \"    ✓ \$repo: pipeline_intent_validator uses AGENT_TOOL_NAMES\"
    else
        echo \"    ✗ \$repo: pipeline_intent_validator MISSING AGENT_TOOL_NAMES\"
        errors=\$((errors + 1))
    fi
done
if [ \$errors -eq 0 ]; then
    echo '  All remote validations passed'
else
    echo \"  \$errors remote validation errors\"
fi
"
    fi

    # Issue #1610 (remediation of W-B): the remote is NOT immune to the defect
    # this gate exists for. `git pull --ff-only` succeeds with modified-tracked
    # and untracked files present, and the `cp -rf` below then copies the
    # REMOTE's working tree (with no --delete). So the remote needs the same
    # gate and the same stamp — otherwise /health-check on the Mac Studio prints
    # UNKNOWN in every repo forever, with a REQUIRED NEXT ACTION that deploying
    # from the laptop can never satisfy. Both run from the remote's own checkout
    # so the recorded commit belongs to the bytes that were copied.
    #
    # Deliberately array-free and word-splitting-free: `ssh host "cmd"` runs cmd
    # under the remote user's LOGIN shell (zsh on current macOS), which does not
    # split unquoted parameters on IFS. Everything variable is interpolated
    # locally into literal text before the heredoc is sent.
    local remote_dirty=""
    if $ALLOW_DIRTY; then
        remote_dirty="--dirty"
    fi

    # Issue #1610 (final remediation, BLOCKING B): the remote copy was
    # `cp -rf plugins/autonomous-dev/$subdir/* "$target/$subdir/"` with NO
    # exclusions, while the remote gate added above measures
    # `source_deployed_files()` — the walk MINUS these same patterns. So the gate
    # printed "clean tree" on the Mac Studio while `cp -rf` shipped the excluded
    # set into all five remote repos, and the remote stamp then recorded a digest
    # map that omitted them. That is #1610's own defect, still live on one of the
    # two deploy paths, now MASKED by a gate affirming cleanliness. Driven, same
    # source through both mechanisms: `cp -rf` delivered a `.pyc`, a `,cover` and
    # a session markdown that rsync did not.
    #
    # The comment on the main gate claiming parity "by construction" covered only
    # rsync. This closes it by using the same tool with the same patterns on both
    # sides. Verified on the remote before choosing this: rsync 3.4.1 at
    # /opt/homebrew/bin/rsync. The `command -v rsync` guard below is not
    # defensive padding — without rsync the remote CANNOT be made measurable, and
    # shipping unmeasured content is precisely the defect, so it aborts and says
    # so rather than silently falling back to the copy that caused this.
    #
    # `--delete` is deliberately NOT added: `cp -rf` never deleted, and adding it
    # would newly remove consumer-local files across five remote repos. That is a
    # destructive change this finding did not ask for. Strays that accumulate are
    # now REPORTED instead, via the target_only arm added in the same pass.
    #
    # Built as literal text locally, like $remote_dirty and $SUBDIRS above: the
    # remote runs a LOGIN shell (zsh), so no array or IFS behaviour is relied on.
    local remote_excludes=""
    local pat
    for pat in "${DEPLOY_EXCLUDES[@]}"; do
        remote_excludes="$remote_excludes --exclude='${pat#--exclude=}'"
    done

    ssh "$REMOTE_HOST" "$(cat <<REMOTE_EOF
set -euo pipefail
echo "  Pulling latest from master..."
cd ~/Dev/autonomous-dev && git pull --ff-only || { echo '  git pull failed'; exit 1; }

if ! command -v rsync >/dev/null 2>&1; then
    echo '  REMOTE ABORT: rsync not found. The remote copy must apply the same'
    echo '  exclusions the remote provenance gate measures, or the gate affirms a'
    echo '  cleanliness that the copy does not deliver (Issue #1610). Install rsync'
    echo '  on the remote, then re-run.'
    exit 1
fi

REMOTE_DEPLOY_STATE="\$PWD/plugins/autonomous-dev/scripts/deploy_state.py"
if [ -f "\$REMOTE_DEPLOY_STATE" ]; then
    remote_gate_rc=0
    python3 "\$REMOTE_DEPLOY_STATE" gate --source "\$PWD" \
        --plugin-src "\$PWD/plugins/autonomous-dev" $remote_dirty || remote_gate_rc=\$?
    if [ "\$remote_gate_rc" -eq 1 ]; then
        echo '  REMOTE DEPLOY-GATE REFUSED — nothing was copied on the remote'
        exit 1
    elif [ "\$remote_gate_rc" -ne 0 ]; then
        echo "  ⚠ remote DEPLOY-GATE broke (exit \$remote_gate_rc) — proceeding WITHOUT provenance verification"
    fi
else
    echo '  ⚠ deploy_state.py missing on remote — remote provenance will NOT be recorded'
fi

echo "  Deploying to repos..."
for repo in $REMOTE_REPOS; do
    target="\$HOME/Dev/\$repo/.claude"
    if [ ! -d "\$target" ]; then
        echo "  SKIP \$repo (no .claude/)"
        continue
    fi
    for subdir in $SUBDIRS; do
        if [ -d "plugins/autonomous-dev/\$subdir" ]; then
            mkdir -p "\$target/\$subdir"
            rsync -a --exclude='extensions/' $remote_excludes "plugins/autonomous-dev/\$subdir/" "\$target/\$subdir/"
        fi
    done
    # Issue #1610 BLOCKING C: bytecode caches execute with no registration step
    # and survive an excluded-pattern sync. Bound their life to one deploy cycle.
    for subdir in $SUBDIRS; do
        [ -d "\$target/\$subdir" ] || continue
        find "\$target/\$subdir" -name extensions -type d -prune -o \
            \( -name '__pycache__' -type d -o -name '*.pyc' -o -name '*.pyo' \) -print0 2>/dev/null \
            | xargs -0 rm -rf 2>/dev/null || true
    done
    # Fix permissions
    find "\$target/hooks" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/hooks" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/scripts" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/scripts" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
    find "\$target/lib" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
    echo "  Deployed: \$repo"
    # Sync settings.json hook registrations
    python3 "plugins/autonomous-dev/scripts/sync_settings_hooks.py" --repo "\$HOME/Dev/\$repo" 2>/dev/null && echo "  Synced \$repo settings.json hooks" || echo "  ⚠ \$repo settings hook sync failed"
    # Issue #1610: stamp from the checkout on the REMOTE, one invocation per
    # target (no arrays — see the login-shell note above). NOTE: no apostrophes
    # anywhere inside this heredoc — bash 3.2 scans \$( ... ) without honouring
    # comments, so a lone apostrophe in a COMMENT here is read as an unbalanced
    # quote and the whole script fails to parse under /bin/bash on macOS.
    if [ -f "\$REMOTE_DEPLOY_STATE" ]; then
        python3 "\$REMOTE_DEPLOY_STATE" stamp --source "\$PWD" \
            --plugin-src "\$PWD/plugins/autonomous-dev" --target "\$target" $remote_dirty \
            || echo "  ⚠ \$repo deploy provenance stamp failed"
    fi
done

# Issue #938: Global hook deployment is intentional but scope-aware.
# When deployed to ~/.claude/hooks, plan_mode_exit_detector.py and
# unified_pre_tool.py's plan-exit gates check repo_detector.is_autonomous_dev_repo()
# and silently fall through in foreign projects (no marker, no deny). This
# replaces pre-#938 behavior where the hooks fired in every project regardless
# of whether autonomous-dev's pipeline applied.
#
# Escape hatches (work in any project, even autonomous-dev itself):
#   AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1   (env var, cross-session, recommended)
#   .claude/SKIP_PLAN_REVIEW            (sentinel file, gitignored, local-only)
#   AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT=1 (opt-in: re-enable in foreign projects)
# Also deploy global hooks/lib/config
echo "  Deploying global (~/.claude)..."
for subdir in hooks lib config; do
    if [ -d "plugins/autonomous-dev/\$subdir" ]; then
        mkdir -p "\$HOME/.claude/\$subdir"
        rsync -a --exclude='extensions/' $remote_excludes "plugins/autonomous-dev/\$subdir/" "\$HOME/.claude/\$subdir/"
    fi
done
for subdir in hooks lib config; do
    [ -d "\$HOME/.claude/\$subdir" ] || continue
    find "\$HOME/.claude/\$subdir" -name extensions -type d -prune -o \
        \( -name '__pycache__' -type d -o -name '*.pyc' -o -name '*.pyo' \) -print0 2>/dev/null \
        | xargs -0 rm -rf 2>/dev/null || true
done
find "\$HOME/.claude/hooks" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
find "\$HOME/.claude/hooks" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
find "\$HOME/.claude/lib" -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
echo "  Synced global: hooks lib config"
if [ -f "\$REMOTE_DEPLOY_STATE" ]; then
    python3 "\$REMOTE_DEPLOY_STATE" stamp --source "\$PWD" \
        --plugin-src "\$PWD/plugins/autonomous-dev" --target "\$HOME/.claude" --log-activity $remote_dirty \
        || echo '  ⚠ remote global deploy provenance stamp failed'
fi
# Sync global settings.json hook registrations (opt-in via --global-settings, Issue #995)
# Note: \$DO_GLOBAL_SETTINGS is interpolated LOCALLY before the SSH heredoc is sent,
# so the remote shell sees a literal "true" or "false".
if [ "$DO_GLOBAL_SETTINGS" = "true" ]; then
    python3 "plugins/autonomous-dev/scripts/sync_settings_hooks.py" --global 2>/dev/null && echo "  Synced global settings.json hooks" || echo "  ⚠ global settings hook sync failed"
else
    echo "  Skipped global settings.json hooks (use --global-settings to opt in)"
fi
$validate_script
REMOTE_EOF
)"
}

validate_local() {
    local repo_path="$1"
    local name="$(basename "$repo_path")"
    local dest="$repo_path/.claude"

    [ ! -d "$repo_path" ] && return
    [ ! -d "$dest" ] && return

    echo "  $name:"

    # 1. Syntax check on key hooks
    if python3 -c "import ast; ast.parse(open('$dest/hooks/unified_pre_tool.py').read())" 2>/dev/null; then
        log_ok "unified_pre_tool.py parses cleanly"
    else
        log_fail "unified_pre_tool.py SYNTAX ERROR"
    fi

    # 2. NATIVE_TOOLS fast path
    if grep -q "NATIVE_TOOLS" "$dest/hooks/unified_pre_tool.py" 2>/dev/null; then
        log_ok "NATIVE_TOOLS fast path present"
    else
        log_fail "NATIVE_TOOLS fast path MISSING"
    fi

    # 3. No stale auto_approval_engine import
    if grep -q "from auto_approval_engine import" "$dest/hooks/unified_pre_tool.py" 2>/dev/null; then
        log_fail "still imports auto_approval_engine"
    else
        log_ok "no auto_approval_engine dependency"
    fi

    # 4. Agent tool fix (observability - issue #380)
    if grep -q '"Agent"' "$dest/hooks/session_activity_logger.py" 2>/dev/null; then
        log_ok "session_activity_logger handles Agent tool"
    else
        log_fail "session_activity_logger MISSING Agent tool handling"
    fi

    # 5. AGENT_TOOL_NAMES constant (pipeline_intent_validator)
    if grep -q "AGENT_TOOL_NAMES" "$dest/lib/pipeline_intent_validator.py" 2>/dev/null; then
        log_ok "pipeline_intent_validator uses AGENT_TOOL_NAMES"
    else
        log_fail "pipeline_intent_validator MISSING AGENT_TOOL_NAMES"
    fi

    # 6. Key files match source (checksum)
    for key_file in $KEY_FILES; do
        if [ -f "$dest/$key_file" ] && [ -f "$PLUGIN_SRC/$key_file" ]; then
            local src_hash dest_hash
            src_hash=$(checksum "$PLUGIN_SRC/$key_file")
            dest_hash=$(checksum "$dest/$key_file")
            if [ "$src_hash" = "$dest_hash" ]; then
                log_ok "$(basename "$key_file") matches source"
            else
                log_fail "$(basename "$key_file") DIFFERS from source"
            fi
        fi
    done

    # 7. Settings.json hooks exist on disk
    if [ -f "$dest/settings.json" ]; then
        local missing_hooks
        missing_hooks=$(python3 -c "
import json, os
with open('$dest/settings.json') as f:
    s = json.load(f)
missing = []
repo = '$repo_path'
for event, matchers in s.get('hooks', {}).items():
    for matcher in matchers:
        for hook in matcher.get('hooks', []):
            cmd = hook.get('command', '')
            # Substitute shell expansions that Python can't resolve.
            # Issue #1036: the canonical path is now wrapped in
            # \${CLAUDE_PROJECT_DIR:-\$(git rev-parse --show-toplevel)}. Resolve
            # the full expression AND the bare \$CLAUDE_PROJECT_DIR forms to the
            # repo root, then keep the legacy bare git-substitution replace.
            cmd_resolved = cmd
            cmd_resolved = cmd_resolved.replace('\${CLAUDE_PROJECT_DIR:-\$(git rev-parse --show-toplevel)}', repo)
            cmd_resolved = cmd_resolved.replace('\${CLAUDE_PROJECT_DIR}', repo)
            cmd_resolved = cmd_resolved.replace('\$CLAUDE_PROJECT_DIR', repo)
            cmd_resolved = cmd_resolved.replace('\$(git rev-parse --show-toplevel)', repo)
            for word in cmd_resolved.split():
                word = word.strip(chr(34) + chr(39))
                if word.endswith('.py') or word.endswith('.sh'):
                    if word.startswith('~'):
                        path = os.path.expanduser(word)
                    elif word.startswith('/'):
                        path = word
                    else:
                        path = os.path.join(repo, word)
                    if not os.path.exists(path):
                        missing.append(word)
if missing:
    print(' '.join(missing))
" 2>/dev/null || true)
        if [ -z "$missing_hooks" ]; then
            log_ok "all settings.json hooks exist on disk"
        else
            log_fail "hooks missing on disk: $missing_hooks"
        fi
    fi

    # 8. Hook registration count (Issue #1672: union across project +
    # project-local + global settings.json — the previous per-file count
    # was unreachable by construction because registration is split by
    # design, so the check was permanently red in every repo).
    EXPECTED_HOOK_EVENTS=8
    if [ -f "$dest/settings.json" ] || [ -f "$dest/settings.local.json" ] || [ -f "$HOME/.claude/settings.json" ]; then
        hook_count=$(python3 "$PLUGIN_SRC/lib/count_hook_registrations.py" \
            "$dest/settings.json" \
            "$dest/settings.local.json" \
            "$HOME/.claude/settings.json" 2>/dev/null || echo "0")
        if [ "$hook_count" -ge "$EXPECTED_HOOK_EVENTS" ]; then
            log_ok "hook registrations: $hook_count lifecycle events (union >= $EXPECTED_HOOK_EVENTS)"
        else
            log_fail "hook registrations: $hook_count lifecycle events (union, expected >= $EXPECTED_HOOK_EVENTS)"
        fi
    fi

    # 9. Stale hooks
    local found_stale=""
    for stale in $STALE_HOOKS; do
        if [ -f "$dest/hooks/$stale" ]; then
            found_stale="$found_stale $stale"
        fi
    done
    if [ -n "$found_stale" ]; then
        log_warn "stale hooks found:$found_stale"
    fi

    # 10. CLAUDE.md size guard
    if [ -f "$repo_path/CLAUDE.md" ]; then
        local line_count
        line_count=$(wc -l < "$repo_path/CLAUDE.md")
        if [ "$line_count" -gt 200 ]; then
            log_warn "CLAUDE.md size: $line_count lines (Anthropic best practice: keep under 200)"
        else
            log_ok "CLAUDE.md size: $line_count lines (<= 200)"
        fi
    fi

    # 11. Permission pattern syntax validation
    if [ -f "$dest/settings.json" ]; then
        local bad_patterns
        bad_patterns=$(python3 -c "
import json, re
with open('$dest/settings.json') as f:
    d = json.load(f)
deny = d.get('permissions', {}).get('deny', [])
bad = []
for p in deny:
    m = re.match(r'^(\w+)\((.+)\)\$', p)
    if m:
        content = m.group(2)
        # :* must only appear at the end (prefix matching)
        if ':*' in content and not content.endswith(':*'):
            bad.append(p)
if bad:
    print(' '.join(bad))
" 2>/dev/null || true)
        if [ -z "$bad_patterns" ]; then
            log_ok "permission patterns: all deny rules syntactically valid"
        else
            log_fail "permission patterns: invalid deny rules: $bad_patterns"
        fi
    fi

    # 12. No duplicate hook registrations between settings.json and settings.local.json (#1183)
    local audit_result audit_exit
    audit_result=$(python3 "$PLUGIN_SRC/scripts/strip_duplicate_hooks.py" --audit "$repo_path" 2>&1)
    audit_exit=$?
    if [ "$audit_exit" -eq 0 ]; then
        log_ok "no duplicate hook registrations between settings.json and settings.local.json"
    else
        log_fail "duplicate hook registrations detected (Issue #1183)"
        echo "$audit_result"
    fi
}

# --- Main ---

echo "=== autonomous-dev deploy-all ==="
echo "Source: $PLUGIN_SRC"
echo "Local repos: $LOCAL_REPOS"
echo "Remote repos: $REMOTE_REPOS ($REMOTE_HOST)"
echo ""

# 0. Provenance gate (Issue #1610) — MUST run before anything is copied.
#    Refusal (not a warning) is deliberate: a warning that fires routinely is
#    ignored, and this one would fire on every ordinary dev cycle.
#
#    CORRECTION (remediation of #1610): this comment previously claimed that a
#    clean `git status` meant the working tree was byte-identical to HEAD for
#    every path this script copies. That was FALSE and is left recorded rather
#    than quietly deleted, because a false safety claim in a comment is exactly
#    what lets a live defect past review. `git status` omits gitignored paths;
#    `rsync -a` shipped 46 of them (38 `,cover`, 13 .DS_Store, a stray session
#    markdown) into consumer repos while the gate printed "clean tree".
#
#    The claim is true NOW, by a different construction: the gate compares the
#    set rsync actually ships (filesystem walk, minus $DEPLOY_EXCLUDES above)
#    against `git ls-tree HEAD` plus `git diff HEAD`. Anything shipped that is
#    not in HEAD is named. So a permitted deploy really does carry HEAD content
#    for every copied path — still WITHOUT changing where anything is copied.
if [ -f "$DEPLOY_STATE" ]; then
    gate_args=(gate --source "$REPO_DIR" --plugin-src "$PLUGIN_SRC")
    $ALLOW_DIRTY && gate_args+=(--dirty)
    gate_rc=0
    python3 "$DEPLOY_STATE" "${gate_args[@]}" || gate_rc=$?
    # 0 = permitted, 1 = REFUSED, anything else = the gate itself broke.
    # A broken gate must not lock the operator out of deploying, but it must
    # NOT be indistinguishable from a pass either (#1471's silent fail-open).
    if [ "$gate_rc" -eq 1 ]; then
        exit 1
    elif [ "$gate_rc" -ne 0 ]; then
        echo "  ⚠ DEPLOY-GATE broke (exit $gate_rc) — proceeding WITHOUT provenance verification"
    fi
    echo ""
else
    echo "  ⚠ deploy_state.py missing — deploy provenance will NOT be recorded"
    echo ""
fi

# 1. Global deploy
if $DO_GLOBAL; then
    deploy_global
    echo ""
fi

# 2. Local repos
if $DO_LOCAL; then
    echo "=== Local machine ==="
    for repo_name in $LOCAL_REPOS; do
        deploy_repo "$HOME/Dev/$repo_name"
    done
    echo ""
fi

# 2b. Stamp provenance onto every LOCAL target we just wrote (Issue #1610).
#     Converts "what is running?" from unanswerable into a file read.
#     Remote targets are stamped by deploy_remote() from the remote's OWN
#     checkout — see the gate+stamp block inside its ssh heredoc. Stamping them
#     from here would record this machine's commit against that machine's bytes.
if [ ${#DEPLOYED_TARGETS[@]} -gt 0 ] && [ -f "$DEPLOY_STATE" ]; then
    stamp_args=(stamp --source "$REPO_DIR" --plugin-src "$PLUGIN_SRC" --log-activity)
    $ALLOW_DIRTY && stamp_args+=(--dirty)
    for t in "${DEPLOYED_TARGETS[@]}"; do
        stamp_args+=(--target "$t")
    done
    python3 "$DEPLOY_STATE" "${stamp_args[@]}" || echo "  ⚠ deploy provenance stamp failed"
    echo ""
fi

# 3. Remote
#
#    ORDERING DECISION (Issue #1610 final remediation). A remote gate refusal
#    exits the ssh heredoc with 1, so `ssh` returns 1, so under `set -euo
#    pipefail` the whole script died HERE — before step 4 validated the LOCAL
#    deploy that steps 1-2 already completed and stamped. That ordering is
#    wrong: a remote-side problem left a finished local deploy unvalidated, and
#    the operator saw a bare non-zero exit with no local summary.
#
#    It is wrong in the other direction too — silently continuing would make a
#    remote refusal invisible. So: capture the failure, keep going so the local
#    deploy IS validated, surface it in the summary, and still exit non-zero at
#    the end. The refusal keeps its teeth; the local validation stops being
#    collateral damage.
REMOTE_FAILED=false
if $DO_REMOTE; then
    deploy_remote || REMOTE_FAILED=true
    if $REMOTE_FAILED; then
        echo "  ✗ remote deploy FAILED (gate refusal or transport error) — see above"
        ERRORS=$((ERRORS + 1))
    fi
    echo ""
fi

# 4. Post-deploy validation (local)
if $DO_LOCAL && ! $DRY_RUN && ! $SKIP_VALIDATE; then
    echo "=== Post-deploy validation ==="
    echo ""

    # Validate global (only if we actually deployed global this run — Issue #1313)
    if $DO_GLOBAL; then
        echo "  ~/.claude:"
        if python3 -c "import ast; ast.parse(open('$GLOBAL_DEST/hooks/unified_pre_tool.py').read())" 2>/dev/null; then
            log_ok "global hook parses cleanly"
        else
            log_fail "global hook SYNTAX ERROR"
        fi
        src_hash=$(checksum "$PLUGIN_SRC/hooks/unified_pre_tool.py")
        dest_hash=$(checksum "$GLOBAL_DEST/hooks/unified_pre_tool.py")
        if [ "$src_hash" = "$dest_hash" ]; then
            log_ok "global hook matches source"
        else
            log_fail "global hook DIFFERS from source"
        fi
        echo ""
    fi

    # Validate each local repo
    for repo_name in $LOCAL_REPOS; do
        validate_local "$HOME/Dev/$repo_name"
    done
    echo ""

    # Summary
    if [ $ERRORS -eq 0 ]; then
        echo "=== ALL VALIDATIONS PASSED ==="
    else
        echo "=== $ERRORS VALIDATION ERRORS ==="
        echo "Fix errors above before using Claude Code in affected repos."
    fi
fi

echo ""
echo "Done. Restart Claude Code (Cmd+Q) in affected repos to pick up changes."

# A remote refusal must still fail the command — it just no longer cancels the
# local post-deploy validation on its way out (see the step 3 ordering note).
if $REMOTE_FAILED; then
    echo "Remote deploy did not succeed. Local deploy above was still validated."
    exit 1
fi
