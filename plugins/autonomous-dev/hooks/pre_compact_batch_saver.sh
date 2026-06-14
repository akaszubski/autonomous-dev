#!/bin/bash
# pre_compact_batch_saver.sh
# PreCompact hook: saves batch AND pipeline state before context compaction
# Creates .claude/compaction_recovery.json marker for post-compaction recovery
# Always exits 0 (never blocks compaction)
#
# Issue #1206: PIPELINE_STATE_FILE default resolved via hooks/lib/_sentinel.sh
# so the path is per-repo, not machine-global /tmp/...

# Resolve script directory robustly so the `source` works whether the hook is
# invoked via an absolute path, a symlink, or relative from the repo root.
_PCBS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/_sentinel.sh
. "$_PCBS_SCRIPT_DIR/lib/_sentinel.sh"

BATCH_STATE=".claude/batch_state.json"
RECOVERY_MARKER=".claude/compaction_recovery.json"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-.ralph-checkpoints}"
PIPELINE_STATE_FILE="${PIPELINE_STATE_FILE:-$(_default_sentinel)}"
PIPELINE_STATE_DIR="${PIPELINE_STATE_DIR:-/tmp}"

has_batch=false
has_pipeline=false

# ---------------------------------------------------------------------------
# Batch state section
# ---------------------------------------------------------------------------
batch_json=""
if [ -f "$BATCH_STATE" ]; then
  status=$(jq -r '.status // "unknown"' "$BATCH_STATE" 2>/dev/null || echo "unknown")
  if [ "$status" = "in_progress" ]; then
    # Read batch state fields
    batch_id=$(jq -r '.batch_id // ""' "$BATCH_STATE" 2>/dev/null || echo "")
    current_index=$(jq -r '.current_index // 0' "$BATCH_STATE" 2>/dev/null || echo "0")
    total_features=$(jq -r '.total_features // 0' "$BATCH_STATE" 2>/dev/null || echo "0")
    features=$(jq -c '.features // []' "$BATCH_STATE" 2>/dev/null || echo "[]")

    # Try to read RALPH checkpoint if available
    checkpoint_data="{}"
    if [ -n "$batch_id" ]; then
      checkpoint_file="$CHECKPOINT_DIR/ralph-${batch_id}_checkpoint.json"
      if [ -f "$checkpoint_file" ]; then
        checkpoint_data=$(cat "$checkpoint_file" 2>/dev/null || echo "{}")
      fi
    fi

    has_batch=true
  fi
fi

# ---------------------------------------------------------------------------
# Pipeline state section
# ---------------------------------------------------------------------------
pipeline_json=""
if [ -f "$PIPELINE_STATE_FILE" ]; then
  # Read run_id from the signed state file
  run_id=$(jq -r '.run_id // ""' "$PIPELINE_STATE_FILE" 2>/dev/null || echo "")
  pipeline_mode=$(jq -r '.mode // "full"' "$PIPELINE_STATE_FILE" 2>/dev/null || echo "full")

  if [ -n "$run_id" ]; then
    per_run_file="$PIPELINE_STATE_DIR/pipeline_state_${run_id}.json"

    pipeline_feature=""
    pipeline_current_step=""
    pipeline_steps_completed=0
    pipeline_steps_remaining=0
    pipeline_modified_files="[]"
    pipeline_cwd="$(pwd)"

    if [ -f "$per_run_file" ]; then
      pipeline_feature=$(jq -r '.feature // ""' "$per_run_file" 2>/dev/null || echo "")

      # Find current step: last "running", or fallback to last "passed"
      pipeline_current_step=$(jq -r '
        [.steps | to_entries[] | select(.value.status == "running") | .key] | last // ""
      ' "$per_run_file" 2>/dev/null || echo "")

      if [ -z "$pipeline_current_step" ]; then
        pipeline_current_step=$(jq -r '
          [.steps | to_entries[] | select(.value.status == "passed") | .key] | last // ""
        ' "$per_run_file" 2>/dev/null || echo "")
      fi

      # Count completed (passed + skipped) and remaining
      passed_count=$(jq '[.steps | to_entries[] | select(.value.status == "passed")] | length' "$per_run_file" 2>/dev/null || echo "0")
      skipped_count=$(jq '[.steps | to_entries[] | select(.value.status == "skipped")] | length' "$per_run_file" 2>/dev/null || echo "0")
      failed_count=$(jq '[.steps | to_entries[] | select(.value.status == "failed")] | length' "$per_run_file" 2>/dev/null || echo "0")
      pipeline_steps_completed=$((passed_count + skipped_count))
      pipeline_steps_remaining=$((13 - pipeline_steps_completed - failed_count))
      if [ "$pipeline_steps_remaining" -lt 0 ]; then
        pipeline_steps_remaining=0
      fi
    fi

    # Get modified files from git
    pipeline_modified_files=$(git diff --name-only HEAD 2>/dev/null | jq -R -s 'split("\n") | map(select(length > 0))' 2>/dev/null || echo "[]")

    has_pipeline=true
  fi
fi

# ---------------------------------------------------------------------------
# If neither batch nor pipeline exists, nothing to save
# ---------------------------------------------------------------------------
if [ "$has_batch" = false ] && [ "$has_pipeline" = false ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Build recovery marker
# ---------------------------------------------------------------------------
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Start with empty object
marker="{}"

# Add batch fields if present
if [ "$has_batch" = true ]; then
  marker=$(echo "$marker" | jq \
    --arg batch_id "$batch_id" \
    --arg status "$status" \
    --argjson current_index "$current_index" \
    --argjson total_features "$total_features" \
    --argjson features "$features" \
    --argjson checkpoint "$checkpoint_data" \
    --arg saved_at "$timestamp" \
    --arg compact_summary "" \
    '. + {
      batch_id: $batch_id,
      status: $status,
      current_index: $current_index,
      total_features: $total_features,
      features: $features,
      checkpoint: $checkpoint,
      saved_at: $saved_at,
      compact_summary: $compact_summary
    }' 2>/dev/null || echo "{}")
fi

# Add pipeline field if present
if [ "$has_pipeline" = true ]; then
  pipeline_obj=$(jq -n \
    --arg run_id "$run_id" \
    --arg feature "$pipeline_feature" \
    --arg mode "$pipeline_mode" \
    --arg current_step "$pipeline_current_step" \
    --argjson steps_completed "$pipeline_steps_completed" \
    --argjson steps_remaining "$pipeline_steps_remaining" \
    --argjson modified_files "$pipeline_modified_files" \
    --arg state_path "${per_run_file:-}" \
    --arg cwd "$pipeline_cwd" \
    --arg saved_at "$timestamp" \
    '{
      run_id: $run_id,
      feature: $feature,
      mode: $mode,
      current_step: $current_step,
      steps_completed: $steps_completed,
      steps_remaining: $steps_remaining,
      modified_files: $modified_files,
      state_path: $state_path,
      cwd: $cwd,
      saved_at: $saved_at
    }' 2>/dev/null)

  if [ -n "$pipeline_obj" ]; then
    marker=$(echo "$marker" | jq --argjson pipeline "$pipeline_obj" '. + {pipeline: $pipeline}' 2>/dev/null || echo "$marker")
  fi

  # If no batch, still need saved_at at top level
  if [ "$has_batch" = false ]; then
    marker=$(echo "$marker" | jq --arg saved_at "$timestamp" '. + {saved_at: $saved_at}' 2>/dev/null || echo "$marker")
  fi
fi

echo "$marker" > "$RECOVERY_MARKER" 2>/dev/null

exit 0
