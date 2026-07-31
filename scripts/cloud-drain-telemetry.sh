#!/usr/bin/env bash
# cloud-drain-telemetry.sh — Wrapper for cloud-drain telemetry with commit suppression
#
# Issue #1437: Suppress telemetry commits for no_drainable_cluster to reduce git log noise.
# 96% of cloud-drain fires produce no real work but still emit FIRE_START/FIRE_END commits.
# This wrapper controls when commits are created vs when only JSONL logging occurs.

set -euo pipefail

# Parse arguments
FIRE_TYPE=""
CLUSTER=""
EXIT_REASON=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fire-type)
            FIRE_TYPE="$2"
            shift 2
            ;;
        --cluster)
            CLUSTER="$2"
            shift 2
            ;;
        --exit-reason)
            EXIT_REASON="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$FIRE_TYPE" ]]; then
    echo "Error: --fire-type is required (FIRE_START or FIRE_END)" >&2
    exit 1
fi

# Determine repository root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
JSONL_PATH="${REPO_ROOT}/.claude/logs/cloud-runs.jsonl"

# Create logs directory if needed
mkdir -p "$(dirname "$JSONL_PATH")"

# Generate timestamp
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ISO_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Determine cluster info for commit message
if [[ -n "$CLUSTER" ]]; then
    CLUSTER_INFO="cluster=${CLUSTER}"
else
    CLUSTER_INFO="${EXIT_REASON:-unknown}"
fi

# Always append to JSONL (source of truth)
cat >> "$JSONL_PATH" <<EOF
{"timestamp": "${ISO_TIMESTAMP}", "fire_type": "${FIRE_TYPE}", "cluster": ${CLUSTER:+\"$CLUSTER\"}, "exit_reason": ${EXIT_REASON:+\"$EXIT_REASON\"}, "suppressed_commit": $([ "$EXIT_REASON" = "no_drainable_cluster" ] && echo "true" || echo "false")}
EOF

# Check if we should create a git commit
# Suppress commits for these no-work exit reasons (Issue #1437)
case "$EXIT_REASON" in
    no_drainable_cluster|queue_empty|all_clusters_high_severity)
        echo "Telemetry commit suppressed for exit_reason=${EXIT_REASON} (Issue #1437)" >&2
        exit 0
        ;;
esac

# Create telemetry commit for real events
if git diff --quiet "$JSONL_PATH" 2>/dev/null; then
    # File hasn't changed (shouldn't happen but be safe)
    echo "Warning: JSONL file unchanged, skipping commit" >&2
    exit 0
fi

# Stage the JSONL file
git add "$JSONL_PATH" 2>/dev/null || {
    echo "Warning: Failed to stage JSONL file" >&2
    exit 0
}

# Create the telemetry commit
COMMIT_MSG="telemetry(cloud-drain): ${FIRE_TYPE} ${TIMESTAMP} ${CLUSTER_INFO}"

git commit -m "$COMMIT_MSG" 2>/dev/null || {
    echo "Warning: Failed to create telemetry commit" >&2
    exit 0
}

echo "Created telemetry commit: ${COMMIT_MSG}" >&2