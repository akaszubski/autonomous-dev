---
name: sweep
description: "Codebase hygiene sweep — /refactor --quick alias, or --tests for test pruning analysis"
argument-hint: "[--fix] [--tests]"
user-invocable: true
user_facing: true
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Codebase Hygiene Sweep

This command has two modes:

1. **Default mode** (no `--tests`): Alias for `/refactor --quick` — runs a quick hygiene sweep using the SweepAnalyzer through the RefactorAnalyzer orchestrator.
2. **Test pruning mode** (`--tests`): Runs the TestPruningAnalyzer to detect orphaned, stale, and redundant tests.

## Implementation

ARGUMENTS: {{ARGUMENTS}}

### Mode Selection

**If `--tests` is in the arguments**:

Run the TestPruningAnalyzer directly. Execute the following Python script via Bash:

```bash
cd {{PROJECT_ROOT}} && python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from test_pruning_analyzer import TestPruningAnalyzer
from pathlib import Path

analyzer = TestPruningAnalyzer(Path('.'))
report = analyzer.analyze()
print(report.format_table())
"
```

Display the resulting markdown table to the user. This is an **informational report only** — no files are auto-deleted.

After displaying results, suggest:
- Review HIGH severity findings first
- Files marked `prunable=yes` (T2/T3 tier) are safe candidates for removal
- Files marked `prunable=no` (T0/T1 tier) should NOT be removed without careful review

**If `--tests --prune` is in the arguments** (with optional `--dry-run`):

Run the pruner to delete fully-flagged test files (safe categories only, security tests excluded, tier-protected). Execute:

```bash
cd {{PROJECT_ROOT}} && python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from test_pruning_analyzer import TestPruningAnalyzer
from pathlib import Path

dry_run = '--dry-run' in '{{ARGUMENTS}}'
analyzer = TestPruningAnalyzer(Path('.'))
result = analyzer.prune_tests(dry_run=dry_run)

if dry_run:
    print('DRY RUN — no files deleted')
    print(f'Would delete {len(result.deleted_files)} files:')
    for f in result.deleted_files:
        print(f'  - {f}')
else:
    print(f'Deleted {len(result.deleted_files)} files:')
    for f in result.deleted_files:
        print(f'  - {f}')

if result.skipped_files:
    print(f'Skipped {len(result.skipped_files)} files:')
    for f, reason in result.skipped_files:
        print(f'  - {f}: {reason}')

if result.error_messages:
    print(f'Errors:')
    for err in result.error_messages:
        print(f'  - {err}')
"
```

- `--tests --prune`: Run pruner with `dry_run=False`, display deleted files
- `--tests --prune --dry-run`: Run pruner with `dry_run=True`, show what would be deleted
- `--tests` alone: existing report-only behavior (unchanged)

**If `--tests` is NOT in the arguments** (default mode):

This command redirects to `/refactor --quick`. Pass any additional flags through:

- If `--fix` was provided: Run `/refactor --quick --fix`
- Otherwise: Run `/refactor --quick`

**Action**: Invoke the `/refactor` command with `--quick` prepended to any provided arguments. Do NOT run independent analysis logic — delegate entirely to `/refactor`.
