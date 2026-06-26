---
name: goa
description: "Governance, Observability, Audit — autonomous infra-health observer for autonomous-dev itself. Subcommands: start | stop | status."
argument-hint: "start|stop|status [--record-trigger-id id1,id2,id3]"
allowed-tools: [Bash, Read]
user-invocable: true
user_facing: true
---

# /goa — Governance, Observability, Audit

Autonomous infrastructure-health observer for autonomous-dev. Monitors cron-job
drop rates and healthchecks.io down-event counts, and files GitHub issues
automatically when thresholds are breached.

**Issue #1320 — MVP, Conservative mode only.**

---

## Usage

```
/goa start [--record-trigger-id id1,id2,id3]
/goa stop
/goa status
```

---

## Implementation

```bash
python3 plugins/autonomous-dev/lib/goa_cli.py <subcommand> "$@"
```

Dispatch the subcommand (`start`, `stop`, or `status`) to the GOA CLI.
Substitute `<subcommand>` with the subcommand the user invoked and `"$@"`
with any additional arguments (e.g. `--record-trigger-id`).

---

## Subcommands

### /goa start

Creates the GOA manifest at `.claude/local/goa_manifest.json` and prints three
`/schedule create` lines for you to run:

| Routine | Cron | Purpose |
|---------|------|---------|
| `goa-watcher` | `*/30 * * * *` | Runs `goa_cli watch` — checks drop rate and down events |
| `goa-ping` | `*/15 * * * *` | Pings the healthchecks.io URL (requires `HEALTHCHECKS_PING_URL`) |
| Deadman | — | Create manually in healthchecks.io; paste UUID into manifest |

After running `/schedule create` for each routine, copy the trigger IDs and run:

```
/goa start --record-trigger-id <watcher-id>,<ping-id>,<deadman-id>
```

This records the IDs so `/goa stop` can cancel them later.

### /goa stop

Reads trigger IDs from the manifest, prints `/schedule cancel <id>` lines, then
deletes the manifest.

### /goa status

Displays the active manifest (thresholds, trigger IDs, healthcheck UUID) and lists
all open `goa`-labelled GitHub issues.

---

## Conservative Mode Thresholds (MVP Default)

| Metric | Default | Window |
|--------|---------|--------|
| `drop_rate_pct` | 70% | 12 h |
| `down_events` | 2 events | 12 h |

To override thresholds, edit `.claude/local/goa_manifest.json` directly.

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `HEALTHCHECKS_API_KEY` | Optional | Enables querying healthchecks.io flip history (required for down-event detection) |
| `HEALTHCHECKS_PING_URL` | Optional | Enables goa-ping cron routine |

---

## Frequency Gate

At most **3 GOA issues** are filed per 24-hour window. If 3 issues have already
been filed today, `goa_watcher` silently skips further filings until the window
resets.

---

## Deduplication

Before filing a new issue, `goa_watcher` calls `gh issue list --label goa
--state open` and uses the same Jaccard token-similarity logic as `/triage` to
detect duplicate titles.  If an equivalent open issue exists, no new issue is
filed.

---

## Spec-First /schedule Integration

The `/goa start` output is **informational** — it prints the `/schedule create`
commands for the operator to run.  This MVP does not attempt to call
`/schedule create` programmatically.  The operator pastes the printed lines.

This design avoids depending on `/schedule` internals and makes the workflow
auditable.

---

## Manifest Schema

```json
{
  "version": 1,
  "created_utc": "2026-06-26T...",
  "trigger_ids": {
    "watcher": "<cron-trigger-id>",
    "ping": "<cron-trigger-id>",
    "deadman": "<healthchecks-check-id>"
  },
  "thresholds": {
    "drop_rate_pct": 70,
    "drop_window_h": 12,
    "down_events": 2,
    "down_window_h": 12
  },
  "healthcheck_uuid": "<uuid>"
}
```

---

## Queued Follow-up Issues

The following enhancements are queued for future implementation:

1. **Aggressive mode thresholds** — drop_rate_pct 40%, down_events 1.
2. **Programmatic /schedule create** — auto-register crons from `/goa start`.
3. **Manifest-driven threshold overrides** — `--mode aggressive` flag.
4. **GOA dashboard** — `goa_status` renders a rich table with recent filings.
5. **Healthchecks.io check auto-create** — provision the UUID via the HC API.
6. **Trend aggregation** — surface recurring breaches in `/improve --trends`.
7. **Slack/webhook notification** — optional side-channel alert on breach.
