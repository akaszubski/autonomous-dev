---
name: implement-resume
description: Resume mode for /implement command
version: 1.0.0
internal: true
---

# RESUME MODE

Resume an interrupted batch from checkpoint.

**STEP R1: Find Batch State**

```bash
# Look for batch state in worktree
BATCH_ID="[id from ARGUMENTS after --resume]"
STATE_FILE=".worktrees/$BATCH_ID/.claude/batch_state.json"
```

If not found:
```
Batch not found: $BATCH_ID

Available batches:
  [list directories in .worktrees/]

Usage: /implement --resume <batch-id>
```

**STEP R2: Load State and Continue**

Read batch_state.json:
- Get `current_index` (where to resume)
- Get `features` list
- Get `completed_features` list
- Get `worktree_path` (absolute path to worktree)

Store the worktree path:
```bash
# Change to worktree directory
cd .worktrees/$BATCH_ID

# Store absolute worktree path for agent prompts (CRITICAL!)
WORKTREE_PATH="$(pwd)"
```

**OR** if `worktree_path` is stored in batch_state.json:
```bash
WORKTREE_PATH="[value from batch_state.json]"
cd $WORKTREE_PATH
```

Display:
```
Resuming batch: $BATCH_ID
   Worktree path: $WORKTREE_PATH
   Progress: Feature M of N
   Completed: [list completed]
   Remaining: [list remaining]

Continuing from feature M...
```

**STEP R3: Continue Processing**

Continue the batch loop from `current_index`, same as BATCH FILE MODE STEP B3.

See [implement-batch.md](implement-batch.md) for BATCH CONTEXT requirements.

**STEP R4: Git Automation**

After batch completion, trigger git automation (same as BATCH FILE MODE STEP B4).

See [implement-batch.md](implement-batch.md) for finalization steps.

**CRITICAL**: When invoking agents in resume mode, include the **BATCH CONTEXT** block (with `$WORKTREE_PATH`) at the start of EVERY agent prompt, exactly as described in BATCH FILE MODE STEP B3.
