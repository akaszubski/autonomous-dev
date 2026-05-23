#!/usr/bin/env bash
# Daily auto-triage: tag high-signal issues with `root-cause` label so
# downstream drainers only work on what matters.
#
# Reads /triage --auto-improvement --json output, then:
#   - For each cluster with rank_score >= --rank-threshold (default 5.0)
#     OR cluster_size >= --size-threshold (default 3): apply `root-cause`
#     label to every member.
#   - Optionally close singleton clusters with rank_score < 1.0 as
#     wontfix (--close-singletons, off by default — destructive).
#
# Idempotent — re-running applies the same labels with no side effects.
# Designed for cron/launchd at ~02:00 local, before the drain-all tick.
#
# Usage:
#   bash scripts/auto-triage.sh                            # label only, conservative
#   bash scripts/auto-triage.sh --rank-threshold 10        # stricter
#   bash scripts/auto-triage.sh --close-singletons         # also close low-signal
#   bash scripts/auto-triage.sh --dry                      # print actions, don't apply

set -euo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="logs/auto-triage"
mkdir -p "$LOG_DIR"

REPO="akaszubski/autonomous-dev"
RANK_THRESHOLD="5.0"
SIZE_THRESHOLD="3"
CLOSE_SINGLETONS=0
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rank-threshold) RANK_THRESHOLD="$2"; shift 2 ;;
    --size-threshold) SIZE_THRESHOLD="$2"; shift 2 ;;
    --close-singletons) CLOSE_SINGLETONS=1; shift ;;
    --dry) DRY=1; shift ;;
    --repo) REPO="$2"; shift 2 ;;
    -h|--help) sed -n '1,25p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1"; exit 2 ;;
  esac
done

TS="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/${TS}.log"
JSON="$LOG_DIR/${TS}-triage.json"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "auto-triage start (rank>=$RANK_THRESHOLD or size>=$SIZE_THRESHOLD; close-singletons=$CLOSE_SINGLETONS; dry=$DRY)"

# 1. Run the analyzer.
python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p); break
from issue_triage_analyzer import main
sys.exit(main(['--auto-improvement', '--repo', '$REPO', '--json']))
" > "$JSON" 2>>"$LOG" || {
  log "ABORT: analyzer failed"
  exit 1
}

# 2. Decide which issues get `root-cause` and which singletons close.
DECISIONS=$(python3 - "$JSON" "$RANK_THRESHOLD" "$SIZE_THRESHOLD" "$CLOSE_SINGLETONS" <<'PY'
import json, sys
path, rt, st, close_s = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
data = json.load(open(path))
clusters = data if isinstance(data, list) else data.get("clusters", [])
label_targets = set()
close_targets = set()
for c in clusters:
    rank = c.get("rank_score", 0.0)
    size = c.get("cluster_size", 0)
    nums = c.get("issue_numbers", [])
    if rank >= rt or size >= st:
        for n in nums:
            label_targets.add(int(n))
    elif close_s and size == 1 and rank < 1.0:
        close_targets.update(int(n) for n in nums)
print(json.dumps({"label": sorted(label_targets), "close": sorted(close_targets)}))
PY
)

LABEL_LIST=$(echo "$DECISIONS" | python3 -c "import json,sys; print(' '.join(str(n) for n in json.load(sys.stdin)['label']))")
CLOSE_LIST=$(echo "$DECISIONS" | python3 -c "import json,sys; print(' '.join(str(n) for n in json.load(sys.stdin)['close']))")

log "Decisions: label=$(echo $LABEL_LIST | wc -w | tr -d ' ') issues, close=$(echo $CLOSE_LIST | wc -w | tr -d ' ') issues"

# 3. Apply labels (idempotent — gh ignores already-applied labels).
APPLIED=0
SKIPPED=0
for n in $LABEL_LIST; do
  existing=$(gh issue view "$n" --repo "$REPO" --json labels --jq '.labels | map(.name) | join(",")' 2>/dev/null || echo "")
  if echo "$existing" | grep -qw "root-cause"; then
    SKIPPED=$((SKIPPED+1))
    continue
  fi
  if (( DRY )); then
    log "  DRY: would label #$n root-cause (current: $existing)"
  else
    if gh issue edit "$n" --repo "$REPO" --add-label root-cause >/dev/null 2>>"$LOG"; then
      APPLIED=$((APPLIED+1))
      log "  +label root-cause #$n"
    else
      log "  FAIL: label #$n"
    fi
  fi
done
log "Labeling: $APPLIED applied, $SKIPPED already had it"

# 4. Close low-signal singletons (only if --close-singletons).
CLOSED=0
for n in $CLOSE_LIST; do
  if (( DRY )); then
    log "  DRY: would close #$n as wontfix (low-signal singleton)"
  else
    if gh issue close "$n" --repo "$REPO" --reason "not planned" \
         --comment "Auto-triage: singleton cluster, rank < 1.0. Closing as low-signal noise. Reopen if recurrence justifies investigation." \
         >/dev/null 2>>"$LOG"; then
      gh issue edit "$n" --repo "$REPO" --add-label wontfix >/dev/null 2>>"$LOG" || true
      CLOSED=$((CLOSED+1))
      log "  closed #$n"
    fi
  fi
done

log "Done. labels_applied=$APPLIED labels_skipped=$SKIPPED closed=$CLOSED triage_json=$JSON"
