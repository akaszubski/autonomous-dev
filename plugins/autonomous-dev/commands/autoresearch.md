---
name: autoresearch
description: "Autonomous experiment loop — hypothesize, modify, benchmark, commit or revert"
argument-hint: "--target <path> --metric <path> [--iterations N] [--min-improvement F] [--dry-run]"
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep]
user-invocable: true
user_facing: true
---

# Autonomous Experiment Loop

Run an autonomous hypothesis-test-measure loop on a single target file. Each iteration: hypothesize an improvement, apply it, run the benchmark, commit if improved or revert if not.

## Implementation

## STEP 0: Parse Arguments and Validate

ARGUMENTS: {{ARGUMENTS}}

Parse these flags from ARGUMENTS:
- `--target <path>` (REQUIRED): File to optimize. Must match `agents/*.md` or `skills/*/SKILL.md`.
- `--metric <path>` (REQUIRED): Python script that outputs `METRIC: <float>` to stdout.
- `--iterations <N>` (optional, default: 20): Maximum experiment iterations.
- `--min-improvement <F>` (optional, default: 0.01): Minimum metric delta to count as improvement.
- `--dry-run` (optional): Skip git operations (no branch, no commits).
- `--max-stall <N>` (optional, default: 3): Halt after N consecutive failures.

### Validation

Run the autoresearch engine validators:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from autoresearch_engine import validate_target, validate_metric
from pathlib import Path

valid, err = validate_target(Path('TARGET_PATH'), repo_root=Path('$REPO_ROOT'))
if not valid:
    print(f'BLOCK: {err}')
    sys.exit(1)

valid, err = validate_metric(Path('METRIC_PATH'))
if not valid:
    print(f'BLOCK: {err}')
    sys.exit(1)

print('Validation passed')
"
```

If validation fails: STOP. Do not proceed.

## STEP 1: Setup and Baseline

1. **Create experiment branch** (skip if `--dry-run`):
   - Branch name: `autoresearch/<target-name>-<timestamp>`
   - Use `autoresearch_engine.create_experiment_branch()`

2. **Run baseline benchmark**:
   - Execute the metric script
   - Parse `METRIC: <float>` from output
   - Record as `baseline_metric`
   - Display: "Baseline metric: <value>"

3. **Initialize experiment history**:
   - History file: `.claude/logs/autoresearch/<target-name>.jsonl`

## STEP 2-6: Experiment Loop

Repeat for each iteration (up to `--iterations`):

### STEP 2: Hypothesize

1. Read the current target file content.
2. Load the last 10 experiment history entries (if any).
3. Based on the file content, history of past attempts (what worked, what didn't), and the metric being optimized, generate ONE specific hypothesis about what change could improve the metric.
4. State the hypothesis clearly before proceeding.

### STEP 3: Apply Change

1. Apply exactly ONE change to the target file using the Edit tool.
2. The change must be focused and testable — no multi-section rewrites.
3. Document what was changed and why.

**HARD GATE**: Only the target file may be modified. No other files.

### STEP 4: Measure

Run the metric script and capture the new metric value:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from autoresearch_engine import run_metric
from pathlib import Path

value, output = run_metric(Path('METRIC_PATH'))
print(f'METRIC_VALUE: {value}')
"
```

Record `metric_after` from the output.

### STEP 5: Decide — Commit or Revert

Calculate: `delta = metric_after - metric_before`

**If improved** (`delta >= min_improvement`):
- Log to experiment history with outcome "improved"
- Commit the change (skip if `--dry-run`): `autoresearch_engine.commit_improvement()`
- Display: "IMPROVED: <metric_before> -> <metric_after> (+<delta>)"
- Update `metric_before = metric_after` for next iteration

**If not improved** (`delta < min_improvement`):
- Log to experiment history with outcome "reverted"
- Revert the target file: `autoresearch_engine.revert_target()`
- Display: "REVERTED: <metric_before> -> <metric_after> (<delta>)"
- `metric_before` stays the same

### STEP 6: Check Stall

Check if the experiment has stalled (too many consecutive failures):

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from autoresearch_engine import ExperimentHistory, check_stall
from pathlib import Path

history = ExperimentHistory(Path('HISTORY_PATH'))
stalled = check_stall(history, max_consecutive=MAX_STALL)
print(f'STALLED: {stalled}')
"
```

If stalled: HALT the loop. Display: "STALLED after N consecutive failures. Halting."

Otherwise: continue to next iteration (back to STEP 2).

## STEP 7: Summary Report

After the loop completes (max iterations reached, stall detected, or all iterations done):

1. Load experiment history summary
2. Display report:

```
=== Autoresearch Summary ===
Target: <target path>
Metric: <metric script>
Baseline: <baseline_metric>
Final:    <final_metric>
Total improvement: <final - baseline>
Iterations: <total>
  Improved: <count>
  Reverted: <count>
  Errors:   <count>
Best single improvement: <best_delta>
Branch: <branch_name> (or "dry-run, no branch")
```

## FORBIDDEN

- FORBIDDEN: Modifying the metric script
- FORBIDDEN: Modifying benchmark datasets or test fixtures
- FORBIDDEN: Committing without metric improvement proof (delta >= min_improvement)
- FORBIDDEN: Skipping revert on failure — every failed experiment MUST be reverted
- FORBIDDEN: Multi-file changes per iteration — ONE target file only
- FORBIDDEN: Running more than max_iterations experiments
- FORBIDDEN: Changing the min_improvement threshold mid-loop
- FORBIDDEN: Ignoring stall detection
