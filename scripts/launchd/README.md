# Scheduled triage-and-implement on macOS

Two ways to wire `scripts/triage-and-implement.sh` to a daily 02:30 local run.

## Option A — launchd (recommended)

Native macOS. Survives reboots. No logged-in Terminal required.

```bash
# Install
cp scripts/launchd/com.autonomous-dev.triage.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.autonomous-dev.triage.plist

# Verify it's loaded
launchctl list | grep autonomous-dev

# Run once manually (useful for testing the wiring)
launchctl start com.autonomous-dev.triage

# Tail logs
tail -f logs/scheduled/launchd.{out,err}.log

# Disable temporarily
launchctl unload ~/Library/LaunchAgents/com.autonomous-dev.triage.plist

# Permanently remove
launchctl unload ~/Library/LaunchAgents/com.autonomous-dev.triage.plist
rm ~/Library/LaunchAgents/com.autonomous-dev.triage.plist
```

The schedule is `02:30` system-local (in `StartCalendarInterval`). Edit those fields to change it; `launchctl unload && load` to apply.

## Option B — crontab

Simpler but more fragile on macOS (Catalina+ blocks `cron` from many paths unless you grant Full Disk Access in System Settings → Privacy & Security → Full Disk Access → `/usr/sbin/cron`).

```bash
crontab -e
```

Append:

```
30 2 * * * cd /Users/akaszubski/Dev/autonomous-dev && /bin/bash scripts/triage-and-implement.sh --max-issues 6 --budget 25 >> logs/scheduled/cron.log 2>&1
```

Save. Verify:

```bash
crontab -l
```

## What the scheduled run does

1. Aborts if working tree is dirty (cron-safe; never destroys uncommitted work).
2. Runs `/triage --auto-improvement --json` to rank the queue.
3. Picks up to 6 issues from the top cluster.
4. Filters out issues already closed or with open PRs.
5. Runs `claude -p "/implement --batch <picked>"` headless — full harness, all hooks, all agents, all gates. `--permission-mode acceptEdits` only (no `--bare`, no `dangerously-skip-permissions`).
6. /implement commits and (if STEP 13 is configured) pushes.
7. Logs to `logs/scheduled/<timestamp>.{log,events.json,picked.txt}`.

Budget cap per run: $25. Adjust in the plist or crontab line.

## Sanity checks before enabling

```bash
# Triage runs without Claude
python3 -c "import sys, os; sys.path.insert(0, 'plugins/autonomous-dev/lib'); from issue_triage_analyzer import main; sys.exit(main(['--auto-improvement', '--json']))" | jq '.[0].root_cause_tag, .[0].members[:3]'

# Dry-run the full pipeline (no claude invocation)
bash scripts/triage-and-implement.sh --dry

# Make sure gh, claude, python3 are on the PATH launchd will use
/bin/bash -lc 'which claude gh python3 git'
```
