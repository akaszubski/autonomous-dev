---
name: implement-batch
description: Batch processing mode for /implement command
version: 1.0.0
internal: true
---

# BATCH FILE MODE

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
4. After each feature, run `/clear` equivalent (context management)

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

**On success**: Push to remote:
   ```bash
   git push origin master
   ```

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
4. Git automation (see STEP B4) - triggers at end of batch
5. Report summary (see STEP B5)

**CRITICAL**: When invoking agents in batch issues mode, include the **BATCH CONTEXT** block (with `$WORKTREE_PATH`) at the start of EVERY agent prompt, exactly as described in STEP B3.

---

## Batch Mode Error Handling

| Error Type | Behavior |
|------------|----------|
| **Transient** (network, timeout) | Retry up to 3 times |
| **Permanent** (syntax, validation) | Mark failed, continue |
| **Security critical** | Block feature, continue batch |
