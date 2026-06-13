---
name: implement-resume
description: Resume mode for /implement command
version: 1.0.0
user-invocable: false
---

# RESUME MODE

## Implementation

Invoke the implementer agent to resume the interrupted batch from the last checkpoint.

## Single-Run Resume Protocol (Issue #1149)

Codifies the state-recovery sequence the coordinator MUST follow when `/implement --resume <id>` targets a SINGLE-RUN id (not a batch). Prior to Issue #1149 this path was improvised: a coordinator that detected a cached pre-validated plan in STEP 3 would dispatch the planner to "ratify" the plan rather than re-plan, but the legitimacy of that shortcut depended on session-gap, HEAD-state, and alignment conditions that no spec captured. This section is the codified protocol.

### Activation condition

This protocol applies when ARGUMENTS contain `--resume <id>` AND `<id>` matches one of the single-run forms:

- `^[a-f0-9]{16}$` — modern run_id (16-char lowercase hex from `pipeline_state.generate_run_id()`)
- `^\d{8}-\d{6}$` — legacy timestamp form (`YYYYMMDD-HHMMSS`)

Batch resume (`--resume batch-*`) follows the existing STEP R1–R4 protocol below and is NOT subject to this section.

### Pre-resume checks (REQUIRED, ordered, all MUST pass before proceeding)

All four checks MUST pass in this order. If any check fails, the coordinator MUST NOT dispatch any agent from the cached/pre-validated artifacts; the failed-check resolution governs what happens instead.

1. **HEAD hash check** (Issue #1149):
   - Read `PIPELINE_BASE_COMMIT` from the per-run state file at `/tmp/pipeline_state_<run_id>.json` (captured at the original STEP 0).
   - Compare against the current `git rev-parse HEAD`.
   - **If HEAD has moved**: the code surface has changed; the cached plan's referenced files and line numbers may be stale. REQUIRE a full re-plan — re-invoke the planner from STEP 5 with the current HEAD state; do NOT pass the pre-validated plan directly to the implementer.
   - The check applies even when the session gap is short; HEAD-moved is a strict gate regardless of elapsed time.

2. **Staging clean check**:
   - `git diff --cached --name-only` MUST return empty.
   - If staged files are present, BLOCK with the same options as the original STEP 1 pre-staged check (commit-and-restart, unstage-and-restart, or operator escape hatch).

3. **Alignment re-verification**:
   - Re-read `.claude/PROJECT.md` GOALS / SCOPE / CONSTRAINTS sections.
   - Re-verify the feature description (or issue body) against the current alignment.
   - **If alignment has drifted** (e.g., SCOPE rewritten between sessions to exclude the in-flight feature, GOALS reordered to deprioritize it, CONSTRAINTS added that the cached plan does not respect): surface the conflict to the user and ask for explicit confirmation before proceeding. Do NOT proceed silently.

4. **Run lock available**:
   - Call `acquire_run_lock(run_id)` from `pipeline_state.py` (or the project's lock helper).
   - If a concurrent process holds the lock, BLOCK with: `"Another /implement is active on run_id <id>; wait for it to complete or use a fresh run_id."`
   - This prevents two coordinator processes from racing on the same per-run state file.

### Plan staleness gate (Issue #1149)

Even when all pre-resume checks pass, the cached pre-validated plan MAY still be too stale to use directly. Compute the **session gap** as `time.time() - os.path.getmtime(plan_file)` where `plan_file` is the cached plan referenced in `/tmp/pipeline_state_<run_id>.json`.

- **session gap > 24 hours**: REQUIRE a full re-plan. Reason: dependency versions, upstream specs, related-issue state, or external API contracts may have drifted in ways the HEAD check cannot detect. Re-invoke the planner from STEP 5.
- **session gap > 4 hours AND plan references security-sensitive paths**: REQUIRE a plan-critic re-run (one round, all axes) before proceeding to implementation. Security-sensitive paths are: `hooks/*.py`, `lib/*security*`, `lib/*auth*`, `lib/*token*`, `config/auto_approve_policy.json`, `templates/settings.*.json`. The original critic verdict alone is NOT sufficient when these paths are touched after a multi-hour gap because the threat model around them is more sensitive to drift.
- **session gap ≤ 4 hours AND HEAD unchanged AND alignment unchanged**: legitimate "ratify" path. Pass the pre-validated plan content directly to the implementer at STEP 8. The planner is NOT re-invoked. This is the only condition under which the ratify shortcut is sanctioned by the protocol.

### State restoration

Once the pre-resume checks pass and the staleness gate has classified the resume, restore the per-run state:

1. Load completed agents via `get_completed_agents(session_id, run_id=run_id)` from `pipeline_completion_state.py`.
2. Restore `PIPELINE_STATE_FILE` env var to point at `/tmp/pipeline_state_<run_id>.json`.
3. Identify the last-completed agent (or the last successful HARD GATE) in the completions list.
4. Continue the pipeline at the step AFTER that agent or gate. Do NOT re-dispatch agents that already have a completion entry — the prompt-integrity gate and the ordering gate will block legitimate work if a completed agent is re-run without a fresh prompt context.

### FORBIDDEN (Issue #1149)

The following behaviors are explicitly forbidden during single-run resume. They are the failure modes the protocol is codifying against; coordinator judgment alone has historically chosen the wrong branch in each case.

- You MUST NOT skip the HEAD hash check — even if the session gap is short and the cached plan appears fresh.
- You MUST NOT improvise a "ratify" path when HEAD has moved or alignment has drifted; both conditions require a full re-plan or explicit user confirmation respectively.
- You MUST NOT pass a stale plan (session gap > 24h, OR HEAD-moved, OR alignment-drifted) directly to the implementer.
- You MUST NOT bypass the run lock; if another process holds it, surface the conflict and BLOCK rather than proceeding with an unowned per-run state file.
- You MUST NOT silently re-dispatch a completed agent on resume — the prompt-integrity gate and the ordering gate will reject the call, and improvising around them defeats the resume protocol.

## Process

Resume an interrupted batch from checkpoint.

**STEP R1: Find Batch State**

```bash
# Locate batch state in worktree
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
