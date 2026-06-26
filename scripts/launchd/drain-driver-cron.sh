#!/usr/bin/env bash
# drain-driver-cron.sh — Mac Studio launchd heartbeat + GHA dispatch trigger
#
# Architecture: this script IS the healthchecks.io heartbeat. On every successful
# invocation (skip, ok, or DISPATCHED) it pings HEALTHCHECK_PING_URL directly.
# GHA drain-driver.yml is the worker; this script is the keep-alive.
#
# See docs/RUNBOOK.md "Launchd-as-heartbeat (drain-driver durable cron)" for
# deploy procedure, T+0 assertions, and T+7 verification.
# See .github/workflows/drain-driver.yml:201-215 for GHA-side redundant ping.

set -euo pipefail

REPO="akaszubski/autonomous-dev"
WORKFLOW="drain-driver.yml"
STALE_THRESHOLD_SECONDS=5400  # 90 min: dispatch if last GHA run older than this
LOG="${HOME}/Library/Logs/drain-driver-cron.log"
GH="/opt/homebrew/bin/gh"

# ── Preflight: HEALTHCHECK_PING_URL must be set and substituted ───────────────
: "${HEALTHCHECK_PING_URL:?HEALTHCHECK_PING_URL must be set in plist EnvironmentVariables}"
if [[ "$HEALTHCHECK_PING_URL" == *"<your-"* ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  ERROR: HEALTHCHECK_PING_URL placeholder not substituted — edit ~/Library/LaunchAgents/com.akaszubski.drain-driver-cron.plist" >> "$LOG"
    exit 1
fi

# ── Preflight: gh CLI must be authenticated ───────────────────────────────────
"$GH" auth status >/dev/null 2>&1 || {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  ERROR: gh CLI unauthenticated — run: gh auth login" >> "$LOG"
    exit 1
}

# ── Heartbeat helper ──────────────────────────────────────────────────────────
_ping_ok() {
    # Heartbeat ping to healthchecks.io after any successful determination
    # (ok, skip, DISPATCHED). See docs/RUNBOOK.md "Launchd-as-heartbeat" +
    # .github/workflows/drain-driver.yml:201-215.
    curl -fsS -m 10 --retry 3 -o /dev/null "$HEALTHCHECK_PING_URL" || true
}

# ── Main logic ────────────────────────────────────────────────────────────────
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Skip if a drain-driver run is already active (queued or in_progress)
ACTIVE="$("$GH" run list --repo "$REPO" --workflow "$WORKFLOW" \
    --json status --jq '[.[] | select(.status=="in_progress" or .status=="queued")] | length')"

if [[ "$ACTIVE" -gt 0 ]]; then
    echo "${TS}  skip (active=${ACTIVE})" >> "$LOG"
    _ping_ok
    exit 0
fi

# Fetch timestamp of the most recent completed run
LAST_RUN="$("$GH" run list --repo "$REPO" --workflow "$WORKFLOW" \
    --json updatedAt --jq '.[0].updatedAt' 2>/dev/null || true)"

if [[ -z "$LAST_RUN" ]]; then
    echo "${TS}  ERROR: could not fetch last run timestamp" >> "$LOG"
    exit 1  # Fail-open: eats one heartbeat; recovers next cycle
fi

# Compute age of last run in seconds
LAST_EPOCH="$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$LAST_RUN" "+%s" 2>/dev/null \
    || date -d "$LAST_RUN" "+%s")"
NOW_EPOCH="$(date -u "+%s")"
AGE=$(( NOW_EPOCH - LAST_EPOCH ))

if [[ "$AGE" -gt "$STALE_THRESHOLD_SECONDS" ]]; then
    # Last run is stale — dispatch a new workflow run
    "$GH" workflow run "$WORKFLOW" --repo "$REPO" --ref master
    echo "${TS}  DISPATCHED (age=${AGE}s > threshold=${STALE_THRESHOLD_SECONDS}s)" >> "$LOG"
    _ping_ok
else
    echo "${TS}  ok (age=${AGE}s, last_run=${LAST_RUN})" >> "$LOG"
    _ping_ok
fi
