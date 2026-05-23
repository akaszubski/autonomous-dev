#!/usr/bin/env bash
# Recurring triage-driven implementer.
#
# Designed for /schedule or cron. Workflow:
#   1. Run /triage --auto-improvement --json to rank the queue by root cause.
#   2. Pick the top cluster's first N issues (configurable; default 8).
#   3. Skip issues already merged or with PRs open.
#   4. Run /implement --batch <picked> in headless mode with full harness.
#   5. Commit + push happen inside /implement (STEP 13).
#
# Idempotent on a clean queue: if the top cluster has nothing actionable,
# exits 0 without doing work. Safe to run hourly.
#
# Usage:
#   bash scripts/triage-and-implement.sh                    # default: 8 issues
#   bash scripts/triage-and-implement.sh --max-issues 4
#   bash scripts/triage-and-implement.sh --cluster security # restrict by tag prefix
#   bash scripts/triage-and-implement.sh --dry              # plan only
#
# Output: logs/scheduled/<ts>.{log,events.json,picked.txt}

set -euo pipefail

cd "$(dirname "$0")/.."

LOG_DIR="logs/scheduled"
mkdir -p "$LOG_DIR"

MAX_ISSUES=8
CLUSTER_FILTER=""
DRY=0
BUDGET=30
REPO="akaszubski/autonomous-dev"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-issues) MAX_ISSUES="$2"; shift 2 ;;
    --cluster) CLUSTER_FILTER="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    --dry) DRY=1; shift ;;
    --repo) REPO="$2"; shift 2 ;;
    *) echo "unknown flag: $1"; exit 2 ;;
  esac
done

TS="$(date +%Y%m%d-%H%M%S)"
TRIAGE_JSON="$LOG_DIR/${TS}-triage.json"
PICKED_FILE="$LOG_DIR/${TS}-picked.txt"
LOG_FILE="$LOG_DIR/${TS}.log"
EVENTS_FILE="$LOG_DIR/${TS}.events.json"

echo "=== triage-and-implement run $TS ===" | tee -a "$LOG_FILE"

# Pre-flight: clean tree (cron-safe abort if dirty).
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ABORT: working tree dirty — skipping this tick." | tee -a "$LOG_FILE"
  git status --short | tee -a "$LOG_FILE"
  exit 0
fi

# 1. Run triage analyzer directly (no Claude needed for the rank step).
python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p); break
from issue_triage_analyzer import main
sys.exit(main(['--auto-improvement', '--repo', '$REPO', '--json']))
" > "$TRIAGE_JSON" 2>>"$LOG_FILE" || {
  echo "ABORT: triage analyzer failed" | tee -a "$LOG_FILE"
  exit 1
}

# 2. Pick top cluster's issues (filtered by --cluster prefix if given).
PICKED=$(python3 - "$TRIAGE_JSON" "$MAX_ISSUES" "$CLUSTER_FILTER" <<'PY'
import json, sys
path, max_n, cluster_filter = sys.argv[1], int(sys.argv[2]), sys.argv[3]
data = json.load(open(path))
clusters = data if isinstance(data, list) else data.get("clusters", [])
clusters = sorted(clusters, key=lambda c: -c.get("rank_score", 0))
chosen = []
for c in clusters:
    tag = c.get("root_cause_tag", "")
    if cluster_filter and not tag.lower().startswith(cluster_filter.lower()):
        continue
    nums = c.get("issue_numbers", [])
    for n in nums[:max_n]:
        chosen.append(str(n))
    if chosen:
        break
print(",".join(chosen[:max_n]))
PY
)

if [[ -z "$PICKED" ]]; then
  echo "Nothing actionable — queue empty or all clusters filtered out." | tee -a "$LOG_FILE"
  exit 0
fi

# 3. Filter out closed issues or those already linked to a closing PR.
FINAL=""
for n in ${PICKED//,/ }; do
  view=$(gh issue view "$n" --repo "$REPO" --json state,closedByPullRequestsReferences 2>/dev/null || echo '{"state":"CLOSED"}')
  state=$(echo "$view" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state','CLOSED'))")
  pr_count=$(echo "$view" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('closedByPullRequestsReferences') or []))")
  if [[ "$state" == "OPEN" && "$pr_count" == "0" ]]; then
    FINAL="${FINAL:+$FINAL,}$n"
  fi
done

if [[ -z "$FINAL" ]]; then
  echo "All top-cluster issues already closed or have open PRs." | tee -a "$LOG_FILE"
  exit 0
fi

echo "$FINAL" > "$PICKED_FILE"
echo "Picked: $FINAL" | tee -a "$LOG_FILE"

if (( DRY )); then
  echo "DRY: would run /implement --batch $FINAL" | tee -a "$LOG_FILE"
  exit 0
fi

# 4. Clear stale pipeline state.
rm -f /tmp/implement_pipeline_state.json /tmp/implement_pipeline_state.lock 2>/dev/null || true

# 5. Run the harness headless. Full hooks, full agents, full gates.
claude \
  --print \
  --permission-mode acceptEdits \
  --max-budget-usd "$BUDGET" \
  --output-format stream-json \
  --include-hook-events \
  --verbose \
  --name "scheduled-${TS}" \
  --setting-sources user,project,local \
  "/implement --batch $FINAL" \
  > "$EVENTS_FILE" 2>>"$LOG_FILE" || {
    echo "implement run failed — see $LOG_FILE" | tee -a "$LOG_FILE"
    exit 1
  }

echo "Done. events=$EVENTS_FILE log=$LOG_FILE" | tee -a "$LOG_FILE"
