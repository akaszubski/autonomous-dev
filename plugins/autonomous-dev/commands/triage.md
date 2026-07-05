---
name: triage
description: "Periodic-aggregation root-cause triage of the open auto-improvement queue"
argument-hint: "[--auto-improvement] [--repo OWNER/REPO] [--limit N] [--include-fp-acknowledged] [--json]"
user-invocable: true
user_facing: true
allowed-tools: [Bash, Read]
---

# Triage: Periodic-Aggregation Root-Cause Triage

`/triage --auto-improvement` reads the open issues labelled `auto-improvement`, clusters
them by root cause, surfaces cross-cluster dependencies, and emits a ranked work queue.

This command is the periodic-aggregation counterpart to per-session `cia.md` issue filing.
CIA files one issue per session finding; this command groups the accumulation by root
cause so a maintainer can drain the queue weekly.

## Implementation

ARGUMENTS: {{ARGUMENTS}}

### STEP 0: Parse arguments

Recognized flags:

- `--auto-improvement`: Triage the `auto-improvement`-labelled queue (currently the only
  supported mode).
- `--repo OWNER/REPO`: GitHub repository (default: `akaszubski/autonomous-dev`).
- `--limit N`: Maximum issues to fetch (default: 200). If the result hits the limit, a
  WARN line is printed to stderr.
- `--include-fp-acknowledged`: Include issues labelled `fp-acknowledged` (filtered out
  by default — these have been triaged as false positives).
- `--json`: Emit machine-readable JSON instead of the human-readable text format.

If no flags are passed, default to `--auto-improvement` (the only mode).

### STEP 1: Invoke the analyzer

```bash
python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from issue_triage_analyzer import main
sys.exit(main({{FLAGS_AS_ARG_LIST}}))
"
```

Replace `{{FLAGS_AS_ARG_LIST}}` with the parsed flag list (e.g.
`['--auto-improvement', '--repo', 'owner/repo']`). If `--json` was passed, the analyzer
emits JSON on stdout; otherwise it emits a human-readable report.

### STEP 2: Display findings

Display the analyzer's stdout verbatim. The default human-readable form groups findings
by `[root_cause_tag] [sub_cluster_id]` with ranking score, severity, cluster size, and
member issue numbers. Cross-cluster dependencies (clusters sharing a file path) are noted
inline. A `--json` invocation returns the same data as a deterministic JSON array suitable
for piping to other tools.

### Idempotence

On a clean queue with unchanged contents the command produces byte-identical output across
runs. Sorts and tie-breakers are total: rank score DESC, then root cause tag ASC, then
sub-cluster ID ASC, then issue numbers within a cluster ASC. The only time-varying input
is `now` (used for recency decay).

### When to run

Weekly, or after a CIA-heavy session that filed many `auto-improvement` issues. The
output is a work queue, not a destructive action. Pair with `gh issue list --label
auto-improvement` to spot-check.


## Filing aggregates

The daily aggregate lifecycle helper `plugins/autonomous-dev/lib/daily_aggregate_manager.py::open_or_supersede_daily_aggregate` is the only sanctioned path for creating aggregate issues with guarded titles.

Direct `gh issue create` commands with titles starting with "Auto-triage findings —" or "[CRITICAL] AI triage —" are HARD-BLOCKED by `unified_pre_tool.py::_detect_daily_aggregate_direct_filing`.

Living-aggregate semantics:
- Idempotent within same UTC day: repeated calls edit the existing aggregate
- Supersedes prior day aggregates: closes old aggregate with "Superseded by #NEW" comment
- Only the triage-aggregate marker command can bypass the title guard

This ensures aggregate issues follow consistent lifecycle patterns and prevent duplicate filing.
