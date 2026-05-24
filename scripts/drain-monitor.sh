#!/usr/bin/env bash
# Drain pipeline monitor + auto-unblock.
# Designed for hourly invocation (via /loop, launchd, or cron).
#
# Checks the running drain (and its shepherd, if any), reports status,
# and takes corrective action for known-bad states:
#
#   - claude subprocess stuck past timeout (>110 min since last progress):
#       kill it; drain will mark failed and continue
#   - drain process died unexpectedly mid-queue:
#       restart with same flags; state markers prevent rework
#   - shepherd died but drain still running:
#       log warning (Phase 2 won't auto-fire — needs manual chain)
#
# Exit code: 0 = normal, 1 = took action, 2 = needs human attention

set -uo pipefail
cd "$(dirname "$0")/.."

PID_FILE="logs/drain-all/pid"
SHEPHERD_PID_FILE="logs/drain-chain/shepherd.pid"
PROGRESS_LOG="logs/drain-all/progress.log"
MONITOR_LOG="logs/drain-all/monitor.log"
STATE_DIR="logs/drain-all/state"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$MONITOR_LOG"; }

DRAIN_PID=""; SHEPHERD_PID=""
[[ -f "$PID_FILE" ]] && DRAIN_PID=$(cat "$PID_FILE")
[[ -f "$SHEPHERD_PID_FILE" ]] && SHEPHERD_PID=$(cat "$SHEPHERD_PID_FILE")

drain_alive=no; shepherd_alive=no
[[ -n "$DRAIN_PID" ]] && kill -0 "$DRAIN_PID" 2>/dev/null && drain_alive=yes
[[ -n "$SHEPHERD_PID" ]] && kill -0 "$SHEPHERD_PID" 2>/dev/null && shepherd_alive=yes

last_prog_time=$(stat -f "%m" "$PROGRESS_LOG" 2>/dev/null || echo 0)
now=$(date +%s)
stale_sec=$((now - last_prog_time))
stale_min=$((stale_sec / 60))

done_n=$(ls "$STATE_DIR"/done-* 2>/dev/null | wc -l | tr -d ' ')
fail_n=$(ls "$STATE_DIR"/failed-* 2>/dev/null | wc -l | tr -d ' ')

log "==="
log "drain: pid=$DRAIN_PID alive=$drain_alive    shepherd: pid=$SHEPHERD_PID alive=$shepherd_alive"
log "stats: done=$done_n failed=$fail_n    last_progress=${stale_min}m ago"
log "tail:"
tail -3 "$PROGRESS_LOG" 2>/dev/null | sed 's/^/  /' | tee -a "$MONITOR_LOG"

ACTION_TAKEN=0
NEEDS_ATTENTION=0

# ── State machine ────────────────────────────────────────────────────────────

if [[ "$drain_alive" == "yes" && "$stale_min" -gt 110 ]]; then
  # Drain alive but >110 min since last update. Timeout is 90 min, so something
  # is stuck past the timeout — likely a claude subprocess that ignored SIGALRM.
  log "STUCK: drain alive but no progress in ${stale_min}m (timeout is 90m)"
  child=$(pgrep -P "$DRAIN_PID" 2>/dev/null | head -3)
  if [[ -n "$child" ]]; then
    for c in $child; do
      cmd=$(ps -p "$c" -o comm= 2>/dev/null | head -1)
      log "  child PID $c: $cmd"
      log "  killing $c"
      kill -TERM "$c" 2>/dev/null
    done
    sleep 8
    for c in $child; do
      kill -0 "$c" 2>/dev/null && { log "  force-killing $c"; kill -9 "$c" 2>/dev/null; }
    done
    ACTION_TAKEN=1
  else
    log "  no children found — drain itself may be hung"
    NEEDS_ATTENTION=1
  fi

elif [[ "$drain_alive" == "no" && "$shepherd_alive" == "yes" ]]; then
  log "TRANSITION: drain done, shepherd waiting/transitioning"
  # Tail the shepherd log to see where it is
  latest_shep=$(ls -t logs/drain-chain/shepherd-*.log 2>/dev/null | head -1)
  [[ -n "$latest_shep" ]] && tail -3 "$latest_shep" | sed 's/^/  shep: /' | tee -a "$MONITOR_LOG"

elif [[ "$drain_alive" == "no" && "$shepherd_alive" == "no" ]]; then
  # Both dead. Either pipeline complete (queue exhausted) or aborted.
  # Distinguish by reading the last line of progress.log.
  last_line=$(tail -1 "$PROGRESS_LOG" 2>/dev/null)
  if echo "$last_line" | grep -q "Drain complete"; then
    log "COMPLETE: pipeline finished successfully"
  elif echo "$last_line" | grep -qE "ABORT|FAIL"; then
    log "ABORTED: $last_line"
    NEEDS_ATTENTION=1
  else
    log "UNCLEAR: drain not alive, no clear completion. Last line:"
    echo "  $last_line" | tee -a "$MONITOR_LOG"
    NEEDS_ATTENTION=1
  fi

elif [[ "$drain_alive" == "yes" ]]; then
  log "OK: drain running, last update ${stale_min}m ago"
fi

# ── Exit code conveys state to caller ────────────────────────────────────────

if (( NEEDS_ATTENTION )); then exit 2; fi
if (( ACTION_TAKEN )); then exit 1; fi
exit 0
