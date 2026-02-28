---
name: improve
description: "Analyze recent sessions for improvement opportunities"
argument-hint: "[--auto-file] [--session <id>] [--date YYYY-MM-DD]"
allowed-tools: [Task, Read, Bash, Glob, Grep]
---

# Continuous Improvement Analysis

Analyze session activity logs to test whether autonomous-dev's automation is working correctly — hooks firing, pipeline executing, HARD GATEs enforcing.

## Usage

```bash
# Analyze today's sessions
/improve

# Also create GitHub issues for findings
/improve --auto-file

# Analyze specific session
/improve --session abc123

# Analyze specific date
/improve --date 2026-02-15
```

## Arguments

- `--auto-file`: Create GitHub issues in `akaszubski/autonomous-dev` for detected problems (default: report only)
- `--session <id>`: Analyze a specific session ID
- `--date YYYY-MM-DD`: Analyze a specific date (default: today)

## Implementation

### STEP 1: Load Activity Logs

Read session logs from `.claude/logs/activity/`:

```bash
# Find available logs
ls -la .claude/logs/activity/*.jsonl 2>/dev/null
```

If `--date` specified, load that date's log. Otherwise load today's.
If `--session` specified, filter entries to that session ID.

If no logs found, report: "No activity logs found. The session_activity_logger hook must be active to generate logs. Check that your settings include all 4 hook layers (UserPromptSubmit, PreToolUse, PostToolUse, Stop)."

### STEP 2: Gather Ground Truth Context

Read autonomous-dev's source-of-truth documents to provide to the analyst:

1. **PROJECT.md**: Read `.claude/PROJECT.md` (or locate via `plugins/autonomous-dev/`) — extract GOALS and enforcement sections
2. **CLAUDE.md**: Read `CLAUDE.md` — extract Critical Rules section
3. **Known bypass patterns**: Read `plugins/autonomous-dev/config/known_bypass_patterns.json`
4. **Recent git history**: `git log --oneline -20`
5. **Repo context (registered hooks)**: Read the target repo's settings.json to calibrate expectations:
   ```bash
   cat .claude/settings.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); hooks=d.get('hooks',{}); print(json.dumps({k: [h.get('command','') for h in v] if isinstance(v,list) else v for k,v in hooks.items()}))" 2>/dev/null || echo "{}"
   ```

### STEP 3: Analyze with Continuous Improvement Agent

Launch the `continuous-improvement-analyst` agent (Task tool, subagent_type: continuous-improvement-analyst) with:

1. **All 4 hook layer entries** from the logs:
   - `UserPromptSubmit` — command routing, workflow nudges
   - `PreToolUse` — tool validation, security checks
   - `PostToolUse` — error detection, activity logging
   - `Stop` — assistant output capture, session summary
2. **PROJECT.md** GOALS and enforcement sections
3. **CLAUDE.md** Critical Rules
4. **known_bypass_patterns.json** content
5. **Registered hooks context** from Step 2.5 (so the analyst can calibrate for consumer repos)
6. Instructions to run all 7 quality checks and cite specific rules for each finding

### STEP 4: Report Findings

Present the analysis report to the user with:
- Critical findings (broken enforcement, hook gaps, HARD GATE violations)
- Warnings (error handling gaps, command routing bypasses)
- Suggestions (optimization opportunities)
- Issue candidates (ready to file)

### STEP 5: Auto-File Issues (if --auto-file)

If `--auto-file` flag is set:

1. Check for duplicate issues in **autonomous-dev repo** (not current repo):
   ```bash
   gh issue list -R akaszubski/autonomous-dev --label auto-improvement --state open
   ```

2. For each non-duplicate finding with severity >= warning:
   ```bash
   gh issue create -R akaszubski/autonomous-dev \
     --title "[CI-{severity}] {title}" \
     --label "continuous-improvement,auto-improvement" \
     --body "{evidence + rule violated + suggested fix}"
   ```

3. Report filed issues with URLs.

**Important**: Issues always go to `akaszubski/autonomous-dev` regardless of which repo this session ran in. The findings are about the automation tooling, not the user's project.

## What It Detects

| Category | Example | Severity |
|----------|---------|----------|
| Hook gap | Missing hook layer (no PreToolUse entries) | Critical |
| HARD GATE violation | Test failures when STEP 6 invoked | Critical |
| Known bypass | Pattern from known_bypass_patterns.json matched | Critical/Warning |
| Novel bypass | Automation circumvented in new way | Critical |
| Command bypass | Nudge fired but raw action taken | Warning |
| Error dropped | PostToolUse error not addressed | Warning |
| Softened language | Stop hook declares success despite errors | Warning |
| Pipeline incomplete | Missing agents or terminal actions | Warning |
| Congruence violation | implement.md updated, implementer.md not | Warning |
| Optimization | Same file read 10+ times in session | Info |
