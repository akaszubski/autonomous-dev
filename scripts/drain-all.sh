#!/usr/bin/env bash
# Serial single-issue drain of the open-issue backlog.
#
# Lists open issues, excludes epics + already-PR'd, runs /implement N for each
# in headless mode with full harness. Resumable: re-running picks up where it
# left off by skipping issues already attempted.
#
# Usage:
#   bash scripts/drain-all.sh                 # drain everything
#   bash scripts/drain-all.sh --phase1        # only the top auto-improvement cluster (~36 issues)
#   bash scripts/drain-all.sh --dry           # print queue, don't run
#   bash scripts/drain-all.sh --label LABEL   # filter by GH label
#   bash scripts/drain-all.sh --limit 10      # stop after N issues
#
# Background-friendly: run with `nohup bash scripts/drain-all.sh &` and tail
# logs/drain-all/progress.log to watch.

set -euo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="logs/drain-all"
STATE_DIR="$LOG_DIR/state"
PROGRESS_LOG="$LOG_DIR/progress.log"
mkdir -p "$STATE_DIR"

REPO="akaszubski/autonomous-dev"
DRY=0
PHASE1=0
ROOT_CAUSE_ONLY=0
LABEL_FILTER=""
LIMIT=0
TIMEOUT_SEC=2700  # 45 min per issue — kills runaway claude invocations
# Issue #1133: --cluster-mode runs ONE /implement --issues ... --no-worktree
# call for the top triage cluster instead of the per-issue loop.
CLUSTER_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry) DRY=1; shift ;;
    --phase1) PHASE1=1; shift ;;
    --root-cause) ROOT_CAUSE_ONLY=1; shift ;;
    --label) LABEL_FILTER="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --timeout) TIMEOUT_SEC="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --cluster-mode) CLUSTER_MODE=1; shift ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1"; exit 2 ;;
  esac
done

# --root-cause is shorthand for "filter to issues with root-cause label".
if (( ROOT_CAUSE_ONLY )); then
  LABEL_FILTER="root-cause"
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$PROGRESS_LOG"; }

# Build the queue.
QUEUE_FILE="$LOG_DIR/queue.txt"

if (( PHASE1 )); then
  log "Phase 1: using /triage top cluster"
  python3 -c "
import sys, os, json
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p); break
from issue_triage_analyzer import main
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    main(['--auto-improvement', '--repo', '$REPO', '--json'])
data = json.loads(buf.getvalue())
clusters = sorted(data, key=lambda c: -c['rank_score'])
print('\n'.join(str(n) for n in clusters[0]['issue_numbers']))
" > "$QUEUE_FILE"
else
  log "Full drain: listing all open issues (excluding epics + PR-linked)"
  GH_ARGS=(--repo "$REPO" --state open --limit 300 --json number,labels,closedByPullRequestsReferences)
  if [[ -n "$LABEL_FILTER" ]]; then GH_ARGS+=(--label "$LABEL_FILTER"); fi
  gh issue list "${GH_ARGS[@]}" \
    --jq '.[] | select((.labels | map(.name) | contains(["epic"])) | not) | select((.closedByPullRequestsReferences | length) == 0) | .number' \
    | sort -n > "$QUEUE_FILE"
fi

TOTAL=$(wc -l < "$QUEUE_FILE" | tr -d ' ')
log "Queue: $TOTAL issues"

if (( LIMIT > 0 )) && (( LIMIT < TOTAL )); then
  head -n "$LIMIT" "$QUEUE_FILE" > "$QUEUE_FILE.limited" && mv "$QUEUE_FILE.limited" "$QUEUE_FILE"
  TOTAL="$LIMIT"
  log "Limited to first $LIMIT"
fi

if (( DRY )); then
  log "DRY run — queue contents:"
  cat "$QUEUE_FILE"
  exit 0
fi

# Pre-flight checks.
if ! git diff --quiet || ! git diff --cached --quiet; then
  log "ABORT: working tree dirty"
  git status --short
  exit 1
fi

if ! command -v claude >/dev/null; then
  log "ABORT: claude CLI not on PATH"
  exit 1
fi

# Issue #1133: --cluster-mode short-circuits the per-issue loop. Query the
# triage analyzer for the top cluster, filter closed / PR-linked issues
# (mirrors the per-issue loop's pre-flight in the regular drain path), and
# invoke /implement --issues N1 N2 ... --no-worktree once.
if (( CLUSTER_MODE )); then
  log "Cluster mode: invoking /implement --issues ... --no-worktree once for the top cluster"

  TRIAGE_JSON="$LOG_DIR/$(date +%Y%m%d-%H%M%S)-triage.json"
  python3 -c "
import sys, os, json, io, contextlib
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p); break
from issue_triage_analyzer import main
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    main(['--auto-improvement', '--repo', '$REPO', '--json'])
data = json.loads(buf.getvalue())
clusters = data if isinstance(data, list) else data.get('clusters', [])
clusters = sorted(clusters, key=lambda c: -c.get('rank_score', 0))
if clusters:
    print(' '.join(str(n) for n in clusters[0].get('issue_numbers', [])))
else:
    print('')
" > "$TRIAGE_JSON" 2>>"$PROGRESS_LOG"

  CLUSTER_RAW=$(cat "$TRIAGE_JSON")
  CLUSTER_NUMS=""
  for n in $CLUSTER_RAW; do
    view=$(gh issue view "$n" --repo "$REPO" --json state,closedByPullRequestsReferences 2>/dev/null || echo '{"state":"CLOSED"}')
    state=$(echo "$view" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state','CLOSED'))")
    pr_count=$(echo "$view" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('closedByPullRequestsReferences') or []))")
    if [[ "$state" == "OPEN" && "$pr_count" == "0" ]]; then
      CLUSTER_NUMS="${CLUSTER_NUMS:+$CLUSTER_NUMS }$n"
    fi
  done

  if [[ -z "$CLUSTER_NUMS" ]]; then
    log "Nothing actionable — cluster empty (all issues closed or have open PRs)."
    exit 0
  fi

  log "Cluster: $CLUSTER_NUMS"

  if (( DRY )); then
    log "DRY: would run /implement --issues $CLUSTER_NUMS --no-worktree"
    exit 0
  fi

  rm -f /tmp/implement_pipeline_state.json /tmp/implement_pipeline_state.lock 2>/dev/null || true
  CLUSTER_EVENTS="$LOG_DIR/$(date +%Y%m%d-%H%M%S)-cluster.events.json"
  if perl -e 'alarm shift; exec @ARGV or die "exec failed: $!"' "$TIMEOUT_SEC" \
      claude \
      --print \
      --permission-mode acceptEdits \
      --output-format stream-json \
      --include-hook-events \
      --verbose \
      --name "drain-all-cluster" \
      --setting-sources user,project,local \
      "/implement --issues $CLUSTER_NUMS --no-worktree" \
      > "$CLUSTER_EVENTS" 2>>"$PROGRESS_LOG"; then
    log "Cluster OK: $CLUSTER_NUMS"
    exit 0
  else
    rc=$?
    log "Cluster FAIL (rc=$rc; events: $CLUSTER_EVENTS)"
    exit "$rc"
  fi
fi

# Drain loop.
i=0
DONE=0
FAILED=0
SKIPPED=0

while read -r n; do
  i=$((i+1))
  marker="$STATE_DIR/done-$n"
  fail_marker="$STATE_DIR/failed-$n"

  if [[ -f "$marker" ]]; then
    SKIPPED=$((SKIPPED+1))
    log "[$i/$TOTAL] #$n SKIP (already done)"
    continue
  fi
  if [[ -f "$fail_marker" ]]; then
    SKIPPED=$((SKIPPED+1))
    log "[$i/$TOTAL] #$n SKIP (previously failed; rm $fail_marker to retry)"
    continue
  fi

  log "[$i/$TOTAL] #$n START"
  ts="$(date +%Y%m%d-%H%M%S)"
  events="$LOG_DIR/${ts}-${n}.events.json"

  # Refresh state: working tree must be clean before each iteration.
  if ! git diff --quiet || ! git diff --cached --quiet; then
    log "  abort: tree became dirty between iterations — stopping"
    exit 1
  fi

  rm -f /tmp/implement_pipeline_state.json /tmp/implement_pipeline_state.lock 2>/dev/null || true

  # Per-issue timeout via perl alarm — bulletproof, no coreutils dependency.
  # `exec` replaces the perl process with claude so signals propagate cleanly.
  if perl -e 'alarm shift; exec @ARGV or die "exec failed: $!"' "$TIMEOUT_SEC" \
      claude \
      --print \
      --permission-mode acceptEdits \
      --output-format stream-json \
      --include-hook-events \
      --verbose \
      --name "drain-all-${n}" \
      --setting-sources user,project,local \
      "/implement $n" \
      > "$events" 2>>"$PROGRESS_LOG"; then
    touch "$marker"
    DONE=$((DONE+1))
    log "[$i/$TOTAL] #$n OK"
  else
    rc=$?
    touch "$fail_marker"
    FAILED=$((FAILED+1))
    if (( rc == 142 )); then
      log "[$i/$TOTAL] #$n FAIL (TIMEOUT after ${TIMEOUT_SEC}s; events: $events)"
    else
      log "[$i/$TOTAL] #$n FAIL (rc=$rc; events: $events)"
    fi
  fi

  log "  progress: $DONE done, $FAILED failed, $SKIPPED skipped, $((TOTAL - i)) remaining"
done < "$QUEUE_FILE"

log "==="
log "Drain complete. done=$DONE failed=$FAILED skipped=$SKIPPED total=$TOTAL"
log "Failed markers in $STATE_DIR/failed-*"
log "Retry failures by removing markers: rm $STATE_DIR/failed-*"
