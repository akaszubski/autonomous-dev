---
name: implement-batch
description: Batch processing mode for /implement command
version: 1.0.0
internal: true
---

# BATCH FILE MODE

## Implementation

Invoke the implementer agent to process each feature in the batch file sequentially with worktree isolation.

## Process

Process multiple features from a file with automatic worktree isolation.

**STEP B1: Create Worktree**

Before processing features, create an isolated worktree and change to it:

```bash
# Generate batch ID
BATCH_ID="batch-$(date +%Y%m%d-%H%M%S)"

# Create worktree (requires git worktree support)
git worktree add ".worktrees/$BATCH_ID" HEAD

# Change to worktree directory (automatic in create_batch_worktree)
cd .worktrees/$BATCH_ID

# Store absolute worktree path for agent prompts (CRITICAL!)
WORKTREE_PATH="$(pwd)"

# Sync settings, hooks, and config from parent repo (worktree gets stale copy at creation time)
PARENT_REPO="$(git -C "$WORKTREE_PATH" rev-parse --path-format=absolute --git-common-dir | sed 's|/.git$||')"
cp "$PARENT_REPO/.claude/settings.json" "$WORKTREE_PATH/.claude/settings.json" 2>/dev/null || true
cp -rf "$PARENT_REPO/.claude/hooks/" "$WORKTREE_PATH/.claude/hooks/" 2>/dev/null || true
cp -rf "$PARENT_REPO/.claude/config/" "$WORKTREE_PATH/.claude/config/" 2>/dev/null || true
```

Display:
```
 Created isolated worktree: .worktrees/$BATCH_ID
   Current working directory changed to worktree.
   All batch processing will occur in this worktree.
   Main repository remains untouched until merge.

   Absolute worktree path: $WORKTREE_PATH
```

**CRITICAL**: Store the absolute worktree path in `WORKTREE_PATH` variable. This MUST be passed to ALL agent prompts in STEP B3, as Task-spawned agents do not inherit the parent process's CWD.

Note: The `create_batch_worktree()` function automatically changes the current working directory to the worktree after successful creation. However, Task-spawned agents operate in the original repository directory by default, so the absolute worktree path must be explicitly passed in every agent prompt.

**STEP B2: Parse Features File**

Use the Read tool to read the batch file specified in ARGUMENTS (after `--batch`).

Parse the content:
- Skip lines starting with `#` (comments)
- Skip empty lines
- Collect features into a list

Display:
```
Found N features in [file]:
  1. Feature one
  2. Feature two
  ...

Starting batch processing in worktree: .worktrees/$BATCH_ID
```

**STEP B3: Process Each Feature**

**CRITICAL**: Batch must auto-continue through ALL features without manual intervention.

For each feature in the list:

1. Display progress: `Feature M of N: [feature description]`
2. Execute the **full pipeline (STEPS 1-8)** for this feature, with BATCH CONTEXT prepended to ALL agent prompts
3. If a feature fails, log the failure and continue to the next feature
4. **HARD GATE: Per-Issue Agent Count Verification**

   After each issue's pipeline completes, BEFORE advancing to the next issue, verify ALL required agents ran for this issue.

   **Required agents** (9 total): researcher-local, researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, continuous-improvement-analyst

   **Verification method**: Count the Task tool invocations with distinct `subagent_type` values for the current issue. The coordinator MUST enumerate which agents actually ran.

   **Display after each issue**:
   ```
   Issue #N agent verification:
     researcher-local: ✓/✗
     researcher:       ✓/✗
     planner:          ✓/✗
     test-master:      ✓/✗
     implementer:      ✓/✗
     reviewer:         ✓/✗
     security-auditor: ✓/✗
     doc-master:       ✓/✗
     continuous-improvement-analyst: ✓/✗
   Result: 9/9 PASS | X/9 FAIL — missing: [list]
   ```

   **If any agent is MISSING**: BLOCK. Do NOT advance to the next issue. Complete the missing agents for this issue first. Then re-verify.

   **FORBIDDEN** (violations = batch failure):
   - ❌ Advancing to the next issue with fewer than 9 agents verified
   - ❌ Self-reporting agent completion without enumerating each agent by name
   - ❌ Claiming an agent "was not needed" for this issue (ALL 9 are required, no exceptions)
   - ❌ Combining multiple issues into a single agent invocation to "save time"
   - ❌ Counting the coordinator's own reasoning as an agent invocation

   **Why this gate exists**: Without per-issue verification, the model progressively shortcuts later issues (Issue #362/#363). Issues 1-2 get full pipeline; issues 3+ get 2-3 agents. This gate is fail-closed: if you cannot verify an agent ran, it did not run.

5. **HARD GATE: Background Agent Drain** (Issue #399)

   Before advancing to the next issue, ALL background agents from the current issue MUST complete. Use `TaskOutput` to await each background task.

   **REQUIRED**: STEP 9 (continuous-improvement-analyst) MUST run in **foreground** (`run_in_background: false`) during batch processing. Background agents accumulate across issues and exhaust machine memory.

   **Max concurrent background agents**: 2. If 2 background agents are already running, await one before launching another.

   **FORBIDDEN** (violations = batch failure):
   - ❌ Launching STEP 9 with `run_in_background: true` during batch processing
   - ❌ Advancing to next issue while background agents from current issue are still running
   - ❌ Having more than 2 concurrent background agents at any time during batch
   - ❌ Fire-and-forget agent launches without tracking the task ID for later drain

   **Why this gate exists**: Without drain, each issue's background agents (STEP 9 continuous-improvement-analyst) persist in memory. Across 7+ issues, this accumulates 7+ agents each holding 80-90K tokens of context, exhausting machine memory and crashing the session (Issue #399).

6. After each feature, run `/clear` equivalent (context management)

**CRITICAL - BATCH CONTEXT for ALL Agent Prompts**:

When invoking agents in batch mode (researcher-local, researcher-web, planner, test-master, implementer, reviewer, security-auditor, doc-master), you MUST include this context block at the start of EVERY agent prompt:

```
**BATCH CONTEXT** (CRITICAL - Operating in worktree):
- Worktree Path: $WORKTREE_PATH (absolute path)
- ALL file operations MUST use absolute paths within this worktree
- Read/Write/Edit tools: Use absolute paths like $WORKTREE_PATH/src/file.py
- Bash commands: Run from worktree using: cd $WORKTREE_PATH && [command]
- Example: To edit src/auth.py, use: $WORKTREE_PATH/src/auth.py (not ./src/auth.py)

Task-spawned agents do NOT inherit the parent's working directory.
You MUST use absolute paths in the worktree for all file operations.
```

**Example Agent Invocation in Batch Mode**:

```
subagent_type: "implementer"
description: "Implement [feature name]"
prompt: "**BATCH CONTEXT** (CRITICAL - Operating in worktree):
- Worktree Path: $WORKTREE_PATH (absolute path)
- ALL file operations MUST use absolute paths within this worktree
- Read/Write/Edit tools: Use absolute paths like $WORKTREE_PATH/src/file.py
- Bash commands: Run from worktree using: cd $WORKTREE_PATH && [command]

Implement production-quality code for: [user's feature description].

**Implementation Plan**: [Paste planner output]
**Tests to Pass**: [Paste test-master output summary]

Output: Production-quality code following the architecture plan."

model: "sonnet"
```

**This applies to ALL 8 agents in the full pipeline when running in batch mode.**

**STEP B4: Batch Finalization -- Auto-Commit, Merge, Cleanup (Issue #333)**

After ALL features in batch are processed, YOU (the coordinator) MUST finalize:

1. **Commit all changes** in the worktree:
   ```bash
   cd $WORKTREE_PATH && git add -A && git commit -m "feat: batch implementation

   - Feature 1 description
   - Feature 2 description

   Closes #N1
   Closes #N2

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
   ```

2. **Merge to master** from the main repo:
   ```bash
   cd /path/to/main/repo && git merge --no-ff <worktree-branch> -m "Merge batch: feature summaries"
   ```

3. **Cleanup worktree** after successful merge:
   ```bash
   rm -rf .worktrees/$BATCH_ID && git worktree prune
   ```

4. **Clean up pipeline state**:
   ```bash
   rm -f /tmp/implement_pipeline_state.json
   ```

**On merge conflict**: DO NOT force-merge. Report conflicting files and leave worktree intact for manual resolution. Provide manual merge instructions.

**On success**: Push to remote and close issues:
   ```bash
   git push origin master
   ```

   **Close GitHub issues** (batch issues mode only): For each successfully implemented issue, close it with a reference to the commit:
   ```bash
   COMMIT_SHA=$(git rev-parse --short HEAD)
   gh issue close <number> -c "Implemented in $COMMIT_SHA" 2>/dev/null || echo "Warning: Could not close issue #<number> (gh CLI may not be available)"
   ```

   **HARD GATE**: The coordinator MUST close all successfully implemented issues. Skipping this step is a pipeline completeness violation. If `gh` CLI is unavailable, log a warning but do not fail the batch.

**STEP B5: Batch Summary**

Show results based on STEP B4 outcome:

**If finalization succeeded:**
```
========================================
BATCH COMPLETE
========================================

Worktree: .worktrees/$BATCH_ID (MERGED AND REMOVED)
Total features: N
Completed successfully: M
Failed: (N - M)

Git Operations:
  - Committed: [commit SHA]
  - Merged to master: YES
  - Worktree cleanup: YES
  - Pushed to remote: YES
  - Issues closed: #N1, #N2, ...

========================================
```

**If finalization failed (conflicts):**
```
========================================
BATCH COMPLETE (WITH CONFLICTS)
========================================

Worktree: .worktrees/$BATCH_ID (LEFT FOR MANUAL RESOLUTION)

Conflicts in:
  - path/to/file1.py
  - path/to/file2.py

Manual merge required:
  cd .worktrees/$BATCH_ID
  git add -A && git commit -m "batch changes"
  cd /path/to/main/repo
  git merge <worktree-branch>
  # Resolve conflicts...
  git commit
  rm -rf .worktrees/$BATCH_ID && git worktree prune
========================================
```

---

# BATCH ISSUES MODE

Process multiple GitHub issues with automatic worktree isolation.

**STEP I1: Fetch Issue Titles**

Parse issue numbers from ARGUMENTS (after `--issues`).

For each issue number, fetch the title:
```bash
gh issue view [number] --json title -q '.title'
```

Create feature list: "Issue #N: [title]"

**STEP I2: Create Worktree and Process**

Same as BATCH FILE MODE:
1. Create worktree (see STEP B1)
2. Store absolute worktree path in `WORKTREE_PATH` variable
3. Process each feature (issue title becomes feature description) - **PASS BATCH CONTEXT to ALL agents** (see STEP B3)

   **Per-Issue Pipeline State**: For each issue, create a FRESH pipeline state:
   ```bash
   ISSUE_RUN_ID="issue-${ISSUE_NUMBER}-$(date +%Y%m%d-%H%M%S)"
   python3 -c "
   import sys; sys.path.insert(0, 'plugins/autonomous-dev/lib')
   from pipeline_state import create_pipeline, save_pipeline
   state = create_pipeline('$ISSUE_RUN_ID', 'Issue #$ISSUE_NUMBER: $ISSUE_TITLE', mode='batch')
   save_pipeline(state)
   "
   ```

   After each issue's pipeline completes, cleanup the per-issue pipeline state between issues:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'plugins/autonomous-dev/lib')
   from pipeline_state import cleanup_pipeline
   cleanup_pipeline('$ISSUE_RUN_ID')
   " 2>/dev/null || true
   ```

   **CRITICAL**: Each issue gets a NEW `create_pipeline()` call. Do NOT reuse pipeline state across issues. Create a new pipeline, run the separate pipeline for that issue, then clear/cleanup before starting the next.

   **Per-issue agent verification is MANDATORY** — see STEP B3 point 4 HARD GATE. Every issue must pass the 9-agent verification before the next issue starts.
   **Background agent drain is MANDATORY** — see STEP B3 point 5 HARD GATE. STEP 9 runs in foreground during batch. Max 2 concurrent background agents.
4. Git automation (see STEP B4) - triggers at end of batch
5. Report summary (see STEP B5)
6. Run continuous improvement analysis (see STEP 9 in implement.md) — **in foreground during batch** (not background, per Issue #399)

**CRITICAL**: When invoking agents in batch issues mode, include the **BATCH CONTEXT** block (with `$WORKTREE_PATH`) at the start of EVERY agent prompt, exactly as described in STEP B3.

---

## Batch Mode Error Handling

| Error Type | Behavior |
|------------|----------|
| **Transient** (network, timeout) | Retry up to 3 times |
| **Permanent** (syntax, validation) | Mark failed, continue |
| **Security critical** | Block feature, continue batch |
