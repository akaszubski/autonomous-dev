---
name: improve
description: "Analyze recent sessions for improvement opportunities"
argument-hint: "[--auto-file] [--session <id>] [--date YYYY-MM-DD]"
allowed-tools: [Task, Read, Bash, Glob, Grep]
---

# Continuous Improvement Analysis

Analyze session activity logs to detect workflow issues, test drift, doc staleness, and improvement opportunities.

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

- `--auto-file`: Create GitHub issues for detected problems (default: report only)
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

If no logs found, report: "No activity logs found. The session_activity_logger hook must be active to generate logs. Check that your settings include the PostToolUse hook."

### STEP 2: Analyze with Continuous Improvement Agent

Launch the `continuous-improvement-analyst` agent (Task tool, subagent_type: general-purpose) with:
- The loaded log data
- Instructions to analyze for: workflow bypasses, test drift, doc staleness, hook false positives, congruence violations

Provide the agent with:
1. The log content (or summary if very large)
2. Current state of known congruence pairs (implement.md ↔ implementer.md, manifest ↔ disk, policy ↔ hooks)
3. Recent git changes: `git log --oneline -20`
4. PROJECT.md goals: Read `.claude/PROJECT.md` and include the GOALS section so the analyst can tag findings as `[ALIGNED]` or `[TANGENTIAL]`

### STEP 3: Report Findings

Present the analysis report to the user with:
- Critical findings (broken enforcement, security issues)
- Warnings (doc drift, test drift)
- Suggestions (optimization opportunities)
- Issue candidates (ready to file)

### STEP 4: Auto-File Issues (if --auto-file)

If `--auto-file` flag is set:

1. Check for duplicate issues:
   ```bash
   gh issue list --label continuous-improvement --state open
   ```

2. For each non-duplicate finding with severity >= warning:
   ```bash
   gh issue create \
     --title "[CI-{severity}] {title}" \
     --label "continuous-improvement" \
     --body "{evidence + suggested fix}"
   ```

3. Report filed issues with URLs.

## What It Detects

| Category | Example | Severity |
|----------|---------|----------|
| Workflow bypass | Hook exempt_path bug | Critical |
| Test drift | Tests skipped that previously passed | Warning |
| Doc staleness | Agent changed, CLAUDE.md not updated | Warning |
| Hook false positive | Hook blocks legitimate pattern 5+ times | Warning |
| Congruence violation | implement.md updated, implementer.md not | Warning |
| Optimization | Same file read 10+ times in session | Info |
