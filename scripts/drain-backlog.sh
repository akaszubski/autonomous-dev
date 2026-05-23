#!/usr/bin/env bash
# Headless drainer for /implement --batch — uses the full harness.
#
# Each batch runs in its own `claude -p` process: fresh context, full hook stack,
# all agents, all enforcement. No --bare, no dangerously-skip-permissions.
# Hooks decide what's allowed; we just don't pause for permission prompts on edits.
#
# Usage:
#   bash scripts/drain-backlog.sh              # run all batches in order
#   bash scripts/drain-backlog.sh --dry        # print plan only
#   bash scripts/drain-backlog.sh --from 5     # resume from batch index 5
#   bash scripts/drain-backlog.sh --only m0    # run a single named batch
#   bash scripts/drain-backlog.sh --budget 25  # USD cap per batch (default 50)
#
# Output:
#   logs/drain/<ts>-<idx>-<name>.log         human-readable session log
#   logs/drain/<ts>-<idx>-<name>.events.json stream-json event stream
#   logs/drain/state.json                    resume marker

set -euo pipefail

cd "$(dirname "$0")/.."

LOG_DIR="logs/drain"
STATE_FILE="$LOG_DIR/state.json"
mkdir -p "$LOG_DIR"

# Ordered batches: name:csv-issues. Security first, big epics excluded.
BATCHES=(
  "security:958,1040,1111,918,984,978,1018"
  "ordering:935,957,936,940,973,1090,1106,1107,1109,1110"
  "hook-fps:1001,1002,1031,1032,1038,917,1055"
  "coordinator:980,987,988,990,1010,1095"
  "plan-critic:903,1006,1073,920,873"
  "install:945,952,894,1036,895,977,1108"
  "m0:1045,1046,1047,1048"
  "m2:1058,1059,1060,1014,1015,961,962,963"
  "m3:974,975,976,1025,1027"
  "m4m5:964,1022,1026,1044"
  "periodic:1099,1100"
  "intent:1070,1072,1074,1076,1078,1079"
  "refactor:1000,1013,1016,1034"
  "doc-drift:900,1061,915"
  "misc:924,931,932,981,983,1009,955,956,959,965,912,913,914,916"
  "new-feat:909,910,911,979"
)

DRY=0
FROM=0
ONLY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry) DRY=1; shift ;;
    --from) FROM="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --budget) shift 2 ;;  # accepted but ignored — subscription auth, no $ cap
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1"; exit 2 ;;
  esac
done

# Pre-flight: working tree must be clean (harness commits per batch).
if [[ -z "${SKIP_GIT_CHECK:-}" ]] && ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: working tree dirty. Commit/stash first, or set SKIP_GIT_CHECK=1."
  git status --short
  exit 1
fi

# Pre-flight: plugin must be loaded.
if ! claude plugin list 2>/dev/null | grep -q autonomous-dev; then
  echo "WARN: autonomous-dev plugin not in 'claude plugin list'. Hooks may not fire."
fi

run_batch() {
  local idx="$1" name="$2" issues="$3"
  local ts; ts="$(date +%Y%m%d-%H%M%S)"
  local base="$LOG_DIR/${ts}-${idx}-${name}"
  local log="${base}.log"
  local events="${base}.events.json"

  echo "[$idx/${#BATCHES[@]}] batch=$name issues=$issues -> $log"

  # Clear any stale pipeline state from a prior crashed run.
  rm -f /tmp/implement_pipeline_state.json /tmp/implement_pipeline_state.lock 2>/dev/null || true

  # Run the harness via headless claude. Hooks + agents + gates all active.
  # --permission-mode acceptEdits: auto-approve file edits BUT hook decisions still block.
  # --output-format stream-json + --include-hook-events: full diagnostic trail.
  claude \
    --print \
    --permission-mode acceptEdits \
    --output-format stream-json \
    --include-hook-events \
    --verbose \
    --name "drain-${name}-${ts}" \
    --setting-sources user,project,local \
    "/implement --batch $issues" \
    > "$events" 2> "$log" || {
      echo "  batch $name FAILED — see $log"
      jq -n --arg name "$name" --arg ts "$ts" --arg log "$log" --arg status failed \
        '{ts:$ts,name:$name,status:$status,log:$log}' \
        >> "$LOG_DIR/state.json"
      return 0  # don't abort the queue
    }

  # Extract last result line for summary.
  jq -n --arg name "$name" --arg ts "$ts" --arg log "$log" --arg status ok \
    '{ts:$ts,name:$name,status:$status,log:$log}' \
    >> "$LOG_DIR/state.json"
  echo "  ok"
}

i=0
for entry in "${BATCHES[@]}"; do
  i=$((i+1))
  name="${entry%%:*}"
  issues="${entry#*:}"

  if [[ -n "$ONLY" && "$ONLY" != "$name" ]]; then continue; fi
  if (( i <= FROM )); then continue; fi

  if (( DRY )); then
    echo "[$i/${#BATCHES[@]}] DRY: claude -p '/implement --batch $issues'"
    continue
  fi

  run_batch "$i" "$name" "$issues"
done

echo
echo "Done. Logs: $LOG_DIR/    State: $STATE_FILE"
