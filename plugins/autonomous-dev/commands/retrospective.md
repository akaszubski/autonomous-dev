---
name: retrospective
description: "Analyze recent sessions to detect intent evolution, drift, and propose alignment updates"
argument-hint: "[--sessions N] [--dry-run] [--auto-file] [--date YYYY-MM-DD]"
allowed-tools: [Task, Read, Bash, Glob, Grep]
user-invocable: true
---

# Session Retrospective

Analyze recent session activity to detect intent evolution, repeated corrections, config drift, and stale memory entries. Produces tiered findings (IMMEDIATE/REVIEW/ARCHIVE) with proposed alignment edits.

## Usage

```bash
# Analyze last 20 sessions (default)
/retrospective

# Analyze more sessions
/retrospective --sessions 40

# Dry run — compute findings without launching agent
/retrospective --dry-run

# Also create GitHub issues for findings
/retrospective --auto-file

# Analyze sessions from a specific date
/retrospective --date 2026-03-15
```

## Arguments

- `--sessions N`: Number of sessions to analyze (default: 20, max: 50)
- `--dry-run`: Show raw findings without agent analysis
- `--auto-file`: Create GitHub issues in `akaszubski/autonomous-dev` for IMMEDIATE findings
- `--date YYYY-MM-DD`: Filter to sessions from a specific date

## Implementation

### STEP 1: Parse Arguments

Extract flags from the user's input:
- `--sessions N` → max_sessions (default 20)
- `--dry-run` → skip agent launch
- `--auto-file` → file issues for IMMEDIATE findings
- `--date YYYY-MM-DD` → filter date

### STEP 2: Load Session Summaries

Use the `retrospective_analyzer.py` library to load session data:

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && python3 -c "
import sys, json, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from retrospective_analyzer import load_session_summaries, RetrospectiveConfig
from pathlib import Path

logs_dir = Path('.claude/logs/activity')
if not logs_dir.exists():
    print(json.dumps({'error': 'No activity logs found at .claude/logs/activity/'}))
    sys.exit(0)

config = RetrospectiveConfig(max_sessions=${MAX_SESSIONS:-20})
summaries = load_session_summaries(logs_dir, max_sessions=config.max_sessions)
result = []
for s in summaries:
    result.append({
        'session_id': s.session_id,
        'date': s.date,
        'stop_messages': s.stop_messages[:5],
        'commands_used': s.commands_used,
        'corrections': s.corrections[:10],
    })
print(json.dumps(result, indent=2))
"
```

If `--date` is specified, filter summaries to that date.

If no logs found, report: "No activity logs found. The session_activity_logger hook must be active to generate logs."

### STEP 3: Gather Alignment Context

Read current alignment documents:

1. **PROJECT.md**: Read `.claude/PROJECT.md` — extract goals and scope
2. **CLAUDE.md**: Read `CLAUDE.md` — extract critical rules and commands
3. **Memory files**: Read `.claude/memory/MEMORY.md` if it exists (check both project and global locations)

### STEP 4: Compute Drift Signals

Run all three detection functions:

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && python3 -c "
import sys, json, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from retrospective_analyzer import (
    load_session_summaries, detect_repeated_corrections,
    detect_config_drift, detect_memory_rot, format_as_unified_diff,
    RetrospectiveConfig
)
from pathlib import Path

logs_dir = Path('.claude/logs/activity')
summaries = load_session_summaries(logs_dir, max_sessions=${MAX_SESSIONS:-20})

# 1. Repeated corrections
corrections = detect_repeated_corrections(summaries, min_threshold=${MIN_THRESHOLD:-3})

# 2. Config drift
config_drift = detect_config_drift(Path('.'), baseline_commits=20)

# 3. Memory rot
memory_dir = Path('.claude/memory')
memory_rot = detect_memory_rot(memory_dir, summaries, decay_days=90) if memory_dir.exists() else []

# Format output
findings = []
for f in corrections + config_drift + memory_rot:
    entry = {
        'category': f.category.value,
        'severity': f.severity.value,
        'description': f.description,
        'evidence': f.evidence,
    }
    if f.proposed_edit:
        entry['proposed_diff'] = format_as_unified_diff(f.proposed_edit)
    findings.append(entry)

print(json.dumps(findings, indent=2))
"
```

### STEP 5: Present or Delegate

**If `--dry-run`**: Present findings directly in three tiers (IMMEDIATE, REVIEW, ARCHIVE) without agent analysis.

**Otherwise**: Launch the `retrospective-analyst` agent (Task tool, subagent_type: retrospective-analyst) with:
1. Session summaries from STEP 2
2. Drift findings from STEP 4
3. Alignment context from STEP 3
4. Instructions to categorize, analyze intent shifts, and propose edits

### STEP 6: Report

Present the analysis report:

```
RETROSPECTIVE ANALYSIS
======================
Period: [earliest date] to [latest date]
Sessions analyzed: [N]

IMMEDIATE (requires action now):
[findings with proposed diffs]

REVIEW (investigate when convenient):
[findings with evidence]

ARCHIVE (safe to remove/archive):
[findings with proposed diffs]
```

### STEP 7: Auto-File Issues (if --auto-file)

If `--auto-file` flag is set, file issues for IMMEDIATE findings only:

1. REQUIRED: Verify no duplicate issues exist before creating new ones:
   ```bash
   gh issue list -R akaszubski/autonomous-dev --label retrospective --state open
   ```

2. **Prior-call ordering contract (Issue #1203)**: the PreToolUse hook
   evaluates each Bash invocation BEFORE it runs. **FORBIDDEN: Do NOT
   bundle the context write and `gh issue create` into one Bash tool
   call** — the hook would not see the context at evaluation time and
   would block (see #1203). The context-file WRITE MUST be a separate
   Bash tool call PRECEDING any `gh issue create`; the cleanup MAY (and
   SHOULD) chain onto the consuming command via `;` so the single
   create-approval covers cleanup (Issue #1204) — standalone `rm`
   re-introduces a user-visible permission prompt.

   Step 2a — write the context file ONCE before any creates (its OWN
   STANDALONE Bash tool call):
   ```bash
   python3 -c "
   import json; from datetime import datetime, timezone
   with open('/tmp/autonomous_dev_cmd_context.json', 'w') as f:
       json.dump({'command': 'retrospective', 'timestamp': datetime.now(timezone.utc).isoformat()}, f)
   "
   ```

   Step 2b — for each IMMEDIATE finding, create the issue (separate Bash
   call from the context write). Mid-loop iterations do NOT chain the
   context cleanup; the FINAL `gh issue create` call chains
   `; rm -f /tmp/autonomous_dev_cmd_context.json` so the cleanup runs
   even if the final create fails (Issue #1204):
   ```bash
   # Mid-loop iteration (NON-FINAL — no chained cleanup):
   gh issue create -R akaszubski/autonomous-dev \
     --title "[RETRO] {finding title}" \
     --label "retrospective,auto-improvement" \
     --body "{evidence + proposed edit}

**Plugin Version**: $(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)"

   # FINAL iteration (chains context-file cleanup via `;`):
   gh issue create -R akaszubski/autonomous-dev \
     --title "[RETRO] {finding title}" \
     --label "retrospective,auto-improvement" \
     --body "{evidence + proposed edit}

**Plugin Version**: $(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)"; rm -f /tmp/autonomous_dev_cmd_context.json
   ```

3. Report filed issues with URLs. Cleanup happens inline via the `;`-chain
   on the final create (no separate cleanup step needed).

## What It Detects

| Category | Example | Severity |
|----------|---------|----------|
| Repeated correction | User says "no" / "revert" across 5+ sessions | IMMEDIATE |
| Config drift | PROJECT.md goals changed significantly | REVIEW |
| Memory rot | Memory entry from 6 months ago, never referenced | ARCHIVE |
| Intent shift | Command usage patterns changed (more --fix than new features) | REVIEW |
| Stale goal | PROJECT.md goal marked complete but still listed | ARCHIVE |
