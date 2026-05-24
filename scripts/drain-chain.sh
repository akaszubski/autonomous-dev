#!/usr/bin/env bash
# Shepherd: wait for an in-flight drain to exit, then auto-start a follow-up.
#
# Used to chain Phase 1.5 (top-cluster retry) → Phase 2 (all auto-improvement)
# without manual intervention. Designed for nohup background use.
#
# Usage:
#   bash scripts/drain-chain.sh --watch-pid 12789 \
#        --then "scripts/drain-all.sh --label auto-improvement --timeout 5400"
#
# Or two-stage:
#   bash scripts/drain-chain.sh --watch-pid PID --then CMD --and-then CMD2

set -euo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="logs/drain-chain"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/shepherd-$(date +%Y%m%d-%H%M%S).log"

WATCH_PID=""
THEN_CMD=""
AND_THEN_CMD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch-pid) WATCH_PID="$2"; shift 2 ;;
    --then) THEN_CMD="$2"; shift 2 ;;
    --and-then) AND_THEN_CMD="$2"; shift 2 ;;
    *) echo "unknown flag: $1"; exit 2 ;;
  esac
done

if [[ -z "$WATCH_PID" || -z "$THEN_CMD" ]]; then
  echo "ERROR: --watch-pid and --then are required" | tee -a "$LOG"
  exit 2
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "shepherd starting; watching PID $WATCH_PID"
log "next: $THEN_CMD"
[[ -n "$AND_THEN_CMD" ]] && log "after: $AND_THEN_CMD"

while kill -0 "$WATCH_PID" 2>/dev/null; do
  sleep 120
done

log "PID $WATCH_PID exited — running next phase"
bash -c "$THEN_CMD" >> "$LOG" 2>&1
rc=$?
log "next phase exited rc=$rc"

if [[ -n "$AND_THEN_CMD" ]]; then
  log "running and-then phase"
  bash -c "$AND_THEN_CMD" >> "$LOG" 2>&1
  log "and-then exited rc=$?"
fi

log "shepherd done"
