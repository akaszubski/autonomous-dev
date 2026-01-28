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

# Check if RALPH checkpoint exists
batch_id=$(jq -r '.batch_id // ""' "$BATCH_STATE" 2>/dev/null || echo "")
if [ -z "$batch_id" ]; then
  exit 0
fi

# Determine checkpoint directory
CHECKPOINT_DIR="${CHECKPOINT_DIR:-.ralph-checkpoints}"
checkpoint_file="$CHECKPOINT_DIR/ralph-${batch_id}_checkpoint.json"
if [ ! -f "$checkpoint_file" ]; then
  exit 0
fi

# Read batch state
status=$(jq -r '.status // "unknown"' "$BATCH_STATE" 2>/dev/null || echo "unknown")
if [ "$status" != "in_progress" ]; then
  exit 0
fi

# Load checkpoint using Python helper
# Find project root (where plugins/ directory exists)
project_root=""
current_dir="$PWD"
while [ "$current_dir" != "/" ]; do
  if [ -d "$current_dir/plugins/autonomous-dev/lib" ]; then
    project_root="$current_dir"
    break
  fi
  current_dir=$(dirname "$current_dir")
done

# Fallback to relative paths if not found
if [ -z "$project_root" ]; then
  if [ -d "plugins/autonomous-dev/lib" ]; then
    project_root="."
  elif [ -d "../plugins/autonomous-dev/lib" ]; then
    project_root=".."
  elif [ -d "../../plugins/autonomous-dev/lib" ]; then
    project_root="../.."
  else
    # Last resort: use CWD
    project_root="."
  fi
fi

helper_path="$project_root/plugins/autonomous-dev/lib/batch_resume_helper.py"

# Check if helper exists
if [ ! -f "$helper_path" ]; then
  # Fallback to batch_state.json if helper not found
  current_index=$(jq -r '.current_index // 0' "$BATCH_STATE")
  total_features=$(jq -r '.total_features // 0' "$BATCH_STATE")
  next_feature_num=$((current_index + 1))

  cat <<EOF

**BATCH PROCESSING RESUMED AFTER COMPACTION**

Batch ID: $batch_id
Progress: Feature $next_feature_num of $total_features
(Helper script unavailable - using batch_state.json)

CRITICAL WORKFLOW REQUIREMENT:
- Use /auto-implement for EACH remaining feature
- NEVER implement directly (skips research, TDD, security audit, docs)
- Check .claude/batch_state.json for current feature
- Pipeline: research -> plan -> TDD -> implement -> review -> security -> docs -> git

The batch will continue automatically. Each feature MUST go through /auto-implement.

EOF
  exit 0
fi

# Load checkpoint via Python helper
checkpoint_json=$(CHECKPOINT_DIR="$CHECKPOINT_DIR" python3 "$helper_path" "$batch_id" 2>/dev/null)
helper_exit=$?

# Handle checkpoint loading errors
if [ $helper_exit -ne 0 ]; then
  # Fallback to batch_state.json if checkpoint load fails
  current_index=$(jq -r '.current_index // 0' "$BATCH_STATE")
  total_features=$(jq -r '.total_features // 0' "$BATCH_STATE")
  next_feature_num=$((current_index + 1))

  cat <<EOF

**BATCH PROCESSING RESUMED AFTER COMPACTION**

Batch ID: $batch_id
Progress: Feature $next_feature_num of $total_features
(Checkpoint unavailable - using batch_state.json)

CRITICAL WORKFLOW REQUIREMENT:
- Use /auto-implement for EACH remaining feature
- NEVER implement directly (skips research, TDD, security audit, docs)
- Check .claude/batch_state.json for current feature
- Pipeline: research -> plan -> TDD -> implement -> review -> security -> docs -> git

The batch will continue automatically. Each feature MUST go through /auto-implement.

EOF
  exit 0
fi

# Parse checkpoint JSON
current_index=$(echo "$checkpoint_json" | jq -r '.current_feature_index // 0')
total_features=$(echo "$checkpoint_json" | jq -r '.total_features // 0')
completed_count=$(echo "$checkpoint_json" | jq -r '.completed_features | length // 0')
failed_count=$(echo "$checkpoint_json" | jq -r '.failed_features | length // 0')
next_feature_num=$((current_index + 1))

# Get next feature description
next_feature_desc=$(echo "$checkpoint_json" | jq -r ".features[$current_index] // \"Feature $next_feature_num\"")

# Display batch resumption context with checkpoint data
cat <<EOF

**BATCH PROCESSING RESUMED AFTER COMPACTION**

Batch ID: $batch_id
Progress: Feature $next_feature_num of $total_features
Completed: $completed_count | Failed: $failed_count

Next Feature:
  $next_feature_desc

CRITICAL WORKFLOW REQUIREMENT:
- Use /auto-implement for EACH remaining feature
- NEVER implement directly (skips research, TDD, security audit, docs)
- Check .claude/batch_state.json for current feature
- Pipeline: research -> plan -> TDD -> implement -> review -> security -> docs -> git

The batch will continue automatically. Each feature MUST go through /auto-implement.

Checkpoint: $checkpoint_file

EOF

exit 0
