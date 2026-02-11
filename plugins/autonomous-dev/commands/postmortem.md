---
name: postmortem
description: "Analyze pipeline failures and file plugin bug issues"
argument-hint: "[--date YYYY-MM-DD] [--dry-run]"
allowed-tools: [Task, Read, Bash]
---

# Postmortem Analysis - Automated Plugin Bug Detection

Analyze `/implement` pipeline session logs to identify plugin bugs and automatically file GitHub issues.

## What This Does

1. Read session telemetry (errors and violations)
2. Classify findings (plugin bugs vs user code issues)
3. Check for duplicate issues via fingerprint matching
4. File new GitHub issues for plugin bugs
5. Add comments to existing issues for duplicates
6. Generate summary report

## Usage

```bash
# Analyze today's session
/postmortem

# Analyze specific date
/postmortem --date 2026-02-11

# Dry-run (report only, no filing)
/postmortem --dry-run

# Dry-run for specific date
/postmortem --date 2026-02-11 --dry-run
```

## Arguments

- `--date YYYY-MM-DD`: Date to analyze (default: today)
- `--dry-run`: Report findings without filing issues

ARGUMENTS: {{ARGUMENTS}}

---

## Implementation

### STEP 0: Parse Arguments

Parse `{{ARGUMENTS}}` to extract flags:

```
--date YYYY-MM-DD    Analyze specific date (default: today)
--dry-run            Report only, don't file issues
```

Extract the date and dry-run flag. If no date provided, use today.

---

### STEP 1: Invoke Postmortem Analyst Agent

Use the Task tool to invoke the **postmortem-analyst** agent (subagent_type="postmortem-analyst") with:
- Date to analyze (from STEP 0)
- Dry-run flag (from STEP 0)

Pass the parsed arguments to the agent:
```
Analyze session logs for date: {date}
Dry-run mode: {true/false}
```

The agent will:
1. Read session telemetry using session_telemetry_reader.py
2. Classify findings (plugin bugs vs user code issues)
3. Check for duplicate issues via fingerprint matching
4. File GitHub issues (unless dry-run)
5. Generate summary report

---

### STEP 2: Display Summary

Display the agent's summary report to the user.

The report includes:
- Total findings (errors, violations, plugin bugs, user issues)
- Plugin bugs filed (new issues + comments on existing)
- User code issues (informational, not filed)
- Duplicates skipped

---

## Output Format

```
Postmortem Analysis - {date}

FINDINGS:
- Total errors: {count}
- Total violations: {count}
- Plugin bugs: {count}
- User code issues: {count}

PLUGIN BUGS FILED:
1. Issue #{number}: {title}
   - Component: {component}
   - Fingerprint: {fingerprint}
   - Status: New issue / Comment added

USER CODE ISSUES (not filed):
- {count} test failures in user code
- {count} git bypasses detected

SUMMARY:
- {count} new issues filed
- {count} comments added to existing issues
```

---

## Prerequisites

**Required**:
- gh CLI installed: https://cli.github.com/
- gh CLI authenticated: `gh auth login`
- Session log files in `.claude/logs/errors/` and `.claude/logs/workflow_violations.log`

---

## Error Handling

### No Log Files Found

```
No session logs found for {date}

The postmortem command requires:
- .claude/logs/errors/{date}.jsonl
- .claude/logs/workflow_violations.log

These files are created during /implement pipeline runs.

Tip: Run /implement first to generate logs.
```

### gh CLI Not Installed

```
Error: gh CLI is not installed

Install gh CLI:
  macOS: brew install gh
  Linux: See https://cli.github.com/
  Windows: Download from https://cli.github.com/

After installing, authenticate:
  gh auth login
```

### Library Import Error

```
Error: session_telemetry_reader.py not found

This library should be in:
  plugins/autonomous-dev/lib/session_telemetry_reader.py

If you installed the plugin recently, try:
  /sync
  Restart Claude Code (Cmd+Q / Ctrl+Q)
```

---

## Integration

**Part of**: Issue #328 (Postmortem analyst for plugin bug detection)

**Related**:
- `/implement`: Generates session logs analyzed by this command
- `/create-issue`: Manual issue creation (postmortem is automated)
- `session_telemetry_reader.py`: Core library for reading and classifying logs

**Flow**:
1. User runs `/implement` (generates logs in `.claude/logs/`)
2. User runs `/postmortem` (analyzes logs, files issues)
3. Plugin bugs are tracked in GitHub issues
4. Future `/implement` runs won't repeat the same bugs (deduplication)

---

## Technical Details

**Agents Used**:
- **postmortem-analyst**: Read logs, classify, file issues (Haiku model, 2-3 min)

**Tools Used**:
- Task: Invoke postmortem-analyst agent
- Bash: Run session_telemetry_reader.py library
- gh CLI: List existing issues, create issues, add comments

**Libraries Used**:
- `session_telemetry_reader.py`: Read and classify session telemetry
  - Reads `.claude/logs/errors/YYYY-MM-DD.jsonl`
  - Reads `.claude/logs/workflow_violations.log`
  - Classifies: PLUGIN_BUG, USER_CODE_BUG, UNKNOWN
  - Creates fingerprints for deduplication
  - Redacts secrets for safe issue filing

**Security**:
- CWE-532: Secrets are redacted before filing issues
- CWE-78: Command injection prevention (no shell metacharacters)
- CWE-400: Resource limits (max 500 errors per session)

**Performance**:
- Typical run: 2-3 minutes (read logs, classify, check duplicates, file issues)
- Dry-run: 1-2 minutes (no GitHub API calls for issue creation)

---

## Examples

**Analyze today's session**:
```bash
/postmortem
```

**Analyze specific date**:
```bash
/postmortem --date 2026-02-10
```

**Dry-run (report only)**:
```bash
/postmortem --dry-run
```

**Dry-run for specific date**:
```bash
/postmortem --date 2026-02-10 --dry-run
```

---

**Added in**: v3.42.0 (Issue #328)
**Status**: Production-ready
