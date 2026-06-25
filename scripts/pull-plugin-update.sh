#!/usr/bin/env bash
#
# pull-plugin-update.sh - Idempotent consumer-side pull-and-deploy.
#
# Purpose:
#   Run from a launchd timer on each consumer Mac. Fetches the latest
#   autonomous-dev tag, pulls master if a new tag is present, and runs the
#   local deployment. Idempotent: if the latest tag matches the last-applied
#   tag, the script exits 0 without action.
#
# Usage:
#   bash scripts/pull-plugin-update.sh                # Pull + deploy if new tag
#   bash scripts/pull-plugin-update.sh --dry-run      # Show what would happen
#   bash scripts/pull-plugin-update.sh --no-deploy    # Pull only, skip deploy
#   bash scripts/pull-plugin-update.sh --help         # Show this help
#
# State:
#   Last-applied tag is recorded in .claude/local/last_pulled_tag
#   Logs are appended to .claude/logs/pull-plugin-update.log
#
# Issue: #1302 (Phase E sub-C auto-deploy on master push)

set -euo pipefail

# -----------------------------------------------------------------------------
# Flag parsing
# -----------------------------------------------------------------------------

DRY_RUN=0
NO_DEPLOY=0

show_help() {
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --no-deploy)
            NO_DEPLOY=1
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Run with --help for usage." >&2
            exit 2
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Paths and constants
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TAG_PREFIX="autonomous-dev-v"
STATE_FILE="${REPO_DIR}/.claude/local/last_pulled_tag"
LOG_FILE="${REPO_DIR}/.claude/logs/pull-plugin-update.log"

mkdir -p "$(dirname "$STATE_FILE")"
mkdir -p "$(dirname "$LOG_FILE")"

# -----------------------------------------------------------------------------
# Logging helper
# -----------------------------------------------------------------------------

log() {
    local ts msg
    ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    msg="[${ts}] $*"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

# -----------------------------------------------------------------------------
# Pre-flight: must run inside a git repo
# -----------------------------------------------------------------------------

cd "$REPO_DIR"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log "ERROR: ${REPO_DIR} is not a git repository. Aborting."
    exit 1
fi

# -----------------------------------------------------------------------------
# Fetch latest tags from origin
# -----------------------------------------------------------------------------

if ! git fetch origin --tags --quiet 2>>"$LOG_FILE"; then
    log "ERROR: git fetch origin --tags failed. See $LOG_FILE for details."
    exit 1
fi

# -----------------------------------------------------------------------------
# Determine latest tag matching prefix
# -----------------------------------------------------------------------------

LATEST_TAG="$(git tag --list "${TAG_PREFIX}*" --sort=-creatordate | head -1 || true)"

if [ -z "$LATEST_TAG" ]; then
    log "No tags matching '${TAG_PREFIX}*' found. Nothing to do."
    exit 0
fi

# -----------------------------------------------------------------------------
# Idempotency check: compare against last-applied tag
# -----------------------------------------------------------------------------

LAST_APPLIED=""
if [ -f "$STATE_FILE" ]; then
    LAST_APPLIED="$(cat "$STATE_FILE" 2>/dev/null || true)"
fi

if [ "$LATEST_TAG" = "$LAST_APPLIED" ]; then
    log "Latest tag ${LATEST_TAG} already applied. Nothing to do."
    exit 0
fi

log "New tag detected: ${LATEST_TAG} (previously applied: ${LAST_APPLIED:-<none>})"

# -----------------------------------------------------------------------------
# Dry-run short-circuit
# -----------------------------------------------------------------------------

if [ "$DRY_RUN" -eq 1 ]; then
    log "DRY-RUN: would checkout master, pull --ff-only, and run deploy-all.sh --local --no-global"
    exit 0
fi

# -----------------------------------------------------------------------------
# Checkout master (must be clean) and fast-forward
# -----------------------------------------------------------------------------

if ! git checkout master --quiet 2>>"$LOG_FILE"; then
    log "ERROR: git checkout master failed (working tree may be dirty). Inspect ${REPO_DIR} manually."
    exit 1
fi

if ! git pull --ff-only --quiet 2>>"$LOG_FILE"; then
    log "ERROR: git pull --ff-only failed (master may have diverged from origin). Inspect ${REPO_DIR} manually."
    exit 1
fi

# -----------------------------------------------------------------------------
# Verify the new tag is reachable from current HEAD
# -----------------------------------------------------------------------------

if ! git merge-base --is-ancestor "$LATEST_TAG" HEAD 2>>"$LOG_FILE"; then
    log "ERROR: Tag ${LATEST_TAG} is not an ancestor of HEAD after pull. Aborting."
    exit 1
fi

log "Pulled master cleanly. ${LATEST_TAG} is reachable."

# -----------------------------------------------------------------------------
# Deploy
# -----------------------------------------------------------------------------

if [ "$NO_DEPLOY" -eq 1 ]; then
    log "--no-deploy specified. Skipping deploy-all.sh."
    # Record the tag so a subsequent run does not re-trigger deploy for the same tag.
    echo "$LATEST_TAG" > "$STATE_FILE"
    log "Recorded ${LATEST_TAG} in ${STATE_FILE}."
    exit 0
fi

DEPLOY_SCRIPT="${REPO_DIR}/scripts/deploy-all.sh"
if [ ! -x "$DEPLOY_SCRIPT" ]; then
    log "ERROR: ${DEPLOY_SCRIPT} not found or not executable. Aborting."
    exit 1
fi

log "Running: bash ${DEPLOY_SCRIPT} --local --no-global"
if bash "$DEPLOY_SCRIPT" --local --no-global >>"$LOG_FILE" 2>&1; then
    echo "$LATEST_TAG" > "$STATE_FILE"
    log "Deploy succeeded. Recorded ${LATEST_TAG} in ${STATE_FILE}."
    exit 0
else
    log "ERROR: deploy-all.sh failed. State file NOT updated. Inspect ${LOG_FILE}."
    exit 1
fi
