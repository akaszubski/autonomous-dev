#!/bin/bash
# SessionStart-batch-recovery.sh
# Fires AFTER auto-compaction to re-inject batch workflow methodology
# Claude Code 2.0: SessionStart with "compact" matcher
# Issue: Batch processing forgot to use /auto-implement after compaction

set -e

input=$(cat)
source=$(echo "$input" | jq -r '.source // ""')

# Only fire after compaction (not normal session start)
if [ "$source" != "compact" ]; then
  exit 0
fi

# Check if batch is in progress
BATCH_STATE=".claude/batch_state.json"
if [ ! -f "$BATCH_STATE" ]; then
  exit 0
fi

# Read batch state
status=$(jq -r '.status // "unknown"' "$BATCH_STATE" 2>/dev/null || echo "unknown")
if [ "$status" != "in_progress" ]; then
  exit 0
fi

# Extract progress info
current_index=$(jq -r '.current_index // 0' "$BATCH_STATE")
total_features=$(jq -r '.total_features // 0' "$BATCH_STATE")
batch_id=$(jq -r '.batch_id // "unknown"' "$BATCH_STATE")

# Re-inject methodology
cat <<EOF

**BATCH PROCESSING RESUMED AFTER COMPACTION**

Batch ID: $batch_id
Progress: Feature $((current_index + 1)) of $total_features

CRITICAL WORKFLOW REQUIREMENT:
- Use /auto-implement for EACH remaining feature
- NEVER implement directly (skips research, TDD, security audit, docs)
- Check .claude/batch_state.json for current feature
- Pipeline: research -> plan -> TDD -> implement -> review -> security -> docs -> git

The batch will continue automatically. Each feature MUST go through /auto-implement.

EOF

exit 0
