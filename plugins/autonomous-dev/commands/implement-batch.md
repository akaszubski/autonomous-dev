---
name: implement-batch
description: Batch processing mode for /implement command
version: 1.0.0
user-invocable: false
user_facing: false
---

# BATCH FILE MODE

> The key words "MUST", "MUST NOT", "SHOULD", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## Implementation

Invoke the implementer agent to process each feature in the batch file sequentially with worktree isolation.

## Process

Process multiple features from a file with automatic worktree isolation.

## No-Worktree Mode (Issue #1133)

When `--no-worktree` is added to `--batch` or `--issues`, the batch runs **in-place on the current branch** instead of creating a git worktree:

- **When to use**: Repos where `.claude/*` is gitignored — `git worktree add` produces a worktree with empty `.claude/hooks/` and `.claude/config/`, deadlocking the PreToolUse hook stack. autonomous-dev itself is the canonical example.
- **What it does**: Skips `git worktree add`, runs the per-issue pipeline serially on the current branch, produces **one commit per issue** (per-issue commit format: `feat(scope): #N <title>\n\nCloses #N`), then opens a **single multi-issue PR** via `open_cluster_pr()` at the end of the batch (PR title: `feat: cluster #N1+#N2+...`).
- **HARD GATE — `Closes #N` enforcement (drain-queue durability plan)**: For EVERY per-issue commit the body MUST include `Closes #N` (case-insensitive) for the issue currently being processed. The synthesis step MUST inject `Closes #N` before invoking `git commit` if the drafted message lacks it. The hook gate at `plugins/autonomous-dev/hooks/unified_pre_tool.py` (`_check_drain_pending_commit_gate`) deterministically blocks any `git commit` that fails this check when a `.claude/local/drain_pending.json` marker is present (set by `/drain-queue` STEP 3.6). The same enforcement applies to the batch-cluster commit at the end of `--no-worktree` mode: ALL N in the cluster MUST appear as `Closes #N` lines in the cluster commit body, not just the first.
- **Signaling**: Sets `BATCH_NO_WORKTREE=1` in the environment. The `unified_pre_tool.py` `_is_batch_context(cwd)` helper recognizes this env var alongside the `.worktrees/batch-*` cwd signal, so all batch hook gates (CIA completion, doc-master completion, agent completeness) keep firing.
- **Pre-condition (HARD GATE)**: Working tree MUST be clean. The pre-staged check is extended to ALSO block on `git diff --name-only` (unstaged tracked changes), not just `git diff --cached`. In-place mode runs `git reset --hard HEAD` between failed issues, which would otherwise silently discard local work.
- **Cleanup on per-issue failure**: `git reset --hard HEAD` reverts tracked-file changes for that issue. `.claude/` files are gitignored — they are untracked from git's perspective and are therefore NOT touched by `git reset --hard`.
- **Batch state**: Persisted at `<cwd>/.claude/batch_state.json` with `"no_worktree": true` so `--resume` can re-enter the in-place flow.
- **NOT for**: single-issue runs, `--fix`, `--light`, `--resume` (resume reads the stored state's `no_worktree` flag automatically).

## Batch Mode Progress Protocol

Batch mode adds two layers on top of the full pipeline's progress protocol:

**Batch Header** — output at start of batch:
```
========================================
BATCH START — N features
Mode: acceptance-first | Worktree: .worktrees/$BATCH_ID
========================================
```

**Per-Feature Header** — output before each feature's pipeline:
```
----------------------------------------
Feature M/N — "feature description"
----------------------------------------
```

**Per-Feature Footer** — output after each feature's pipeline:
```
  Feature M/N complete (Xs) | Tests: P passed | Running total: M/N done
```

Within each feature, follow the full pipeline's step banner and agent completion format.

**Batch Summary Timing** — enhance STEP B5 with per-feature timing:
```
  Feature 1: "description"       2:30
  Feature 2: "description"       3:15
  Feature 3: "description"       FAILED (reason)
```

**STEP B0: Pre-Staged Files Check — HARD GATE**

**Progress**: Output batch header after worktree creation. Output gate result for pre-staged check.

```bash
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)
if [ -n "$STAGED_FILES" ]; then
  echo "BLOCKED: Pre-staged files detected"
  echo "$STAGED_FILES"
fi
```

If `STAGED_FILES` is non-empty: **BLOCK** the pipeline. Display:

```
BLOCKED — Pre-staged files detected.

The following files are already staged from a previous session:
[list files]

Pre-staged files propagate into worktrees, contaminating batch isolation.

Options:
A) Unstage: git reset HEAD
B) Commit first: git commit -m "wip: staged changes from previous session"
C) Review: git diff --cached
```

Do NOT proceed to STEP B1 until the staging area is clean.

**FORBIDDEN**:
- ❌ Proceeding with pre-staged files present
- ❌ Silently unstaging files without user confirmation
- ❌ Creating worktrees with pre-staged files in the index

**STEP B1: Create Worktree**

**Progress**: Capture `BATCH_START=$(date +%s)` after worktree creation.

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

**Progress**: Output feature count summary.

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

1. Display progress using per-feature header: `Feature M/N — "feature description" [mode]` (see Batch Mode Progress Protocol). The `[mode]` suffix shows the detected pipeline mode (full/--fix/--light) from STEP I1.5. After each feature completes, output per-feature footer with elapsed time and running total.
2. Execute the **detected pipeline** for this feature, with BATCH CONTEXT prepended to ALL agent prompts. The pipeline variant is determined by the issue's mode from STEP I1.5:
   - `full` → full pipeline (STEPS 1-8)
   - `fix` → fix pipeline (implement-fix.md)
   - `light` → light pipeline (implement.md --light)
3. If a feature fails, log the failure and continue to the next feature

**Per-Issue Validator Artifact Write** (Issue #991): After reviewer and security-auditor both return for each issue, persist their verbatim outputs so the CIA can compute the Validator Diversity Score:
```bash
ISSUE_RUN_ID="${BATCH_ID}-issue${ISSUE_NUMBER}"
mkdir -p ".claude/logs/activity/validators/$ISSUE_RUN_ID"
cat > ".claude/logs/activity/validators/$ISSUE_RUN_ID/reviewer.txt" << 'REVIEWER_EOF'
{reviewer verbatim output for this issue}
REVIEWER_EOF
cat > ".claude/logs/activity/validators/$ISSUE_RUN_ID/security-auditor.txt" << 'SECURITY_EOF'
{security-auditor verbatim output for this issue}
SECURITY_EOF
```

**Per-Issue Doc-Drift Verdict Collection** (Issue #559):

After doc-master completes for each issue, parse its output for the `DOC-DRIFT-VERDICT`. This mirrors the single-issue verdict parsing in implement.md STEP 12.

IMPORTANT: Use the Agent tool's return value text — do NOT grep transcript files directly.
The return value contains the agent's full output including DOC-DRIFT-VERDICT.
If the return value is empty, wait 3 seconds before retrying (filesystem flush delay — Issue #682).

- If `DOC-DRIFT-VERDICT: PASS`: record `doc-drift-verdict: PASS` and proceed
- If `DOC-DRIFT-VERDICT: FAIL`: **BLOCK** the per-issue pipeline. Do NOT advance to the next issue until doc-drift is resolved.
- **Shallow Verdict Detection**: Count the words in the doc-master output. If the output is fewer than 100 words, treat it as `DOC-VERDICT-SHALLOW` — the output is too short to confirm a real semantic sweep occurred. Log `[DOC-VERDICT-SHALLOW] doc-master produced N words (minimum: 100) for issue #N` and retry once with reduced context (only changed file list + feature description). If retry also produces fewer than 100 words or no verdict, log `[DOC-VERDICT-SHALLOW-RETRY-FAILED] doc-master still shallow after retry for issue #N — proceeding with warning` and record `doc-drift-verdict: SHALLOW`.
- If doc-master returned empty output or no `DOC-DRIFT-VERDICT` found: wait 3 seconds for filesystem flush (Issue #682), then **retry once** with reduced context (only changed file list + feature description). Log `[DOC-VERDICT-MISSING] Re-invoking doc-master with reduced context for issue #N`
  - If retry produces a verdict: use that verdict
  - If retry also fails: log `[DOC-VERDICT-MISSING] doc-master produced no verdict after retry for issue #N — proceeding with warning` and record `doc-drift-verdict: MISSING`

**REQUIRED: Persist verdict to completion state** (Issues #837, #852):
After parsing the doc-master verdict for each issue, the coordinator MUST call `record_doc_verdict(session_id, issue_number, verdict)` AND `record_agent_completion(session_id, 'doc-master', ...)` from `pipeline_completion_state.py`. The `record_doc_verdict` call persists the verdict for the batch gate hook. The `record_agent_completion` call is required because SubagentStop doesn't fire reliably for background agents, causing 'doc-master' to be absent from the completed agents set (Issue #852). Without both calls, the commit-time gate may block even when doc-master completed.

```python
from pipeline_completion_state import record_doc_verdict, record_agent_completion
record_doc_verdict(session_id, issue_number, verdict)  # e.g., "PASS", "FAIL", "MISSING", "SHALLOW"
# Issue #852: Explicitly record doc-master completion since SubagentStop
# doesn't fire reliably for background agents
record_agent_completion(session_id, 'doc-master', issue_number=issue_number, success=(verdict not in ('MISSING',)))
```

Include `doc-drift-verdict: PASS/FAIL/MISSING/SHALLOW` in the per-issue agent verification display:
```
Issue #N agent verification:
  ...
  doc-master:       ✓/✗  (doc-drift-verdict: PASS/FAIL/MISSING/SHALLOW)
  ...
```

> In batch mode, see implement-batch.md STEP B3 for per-issue doc-drift verdict collection. For single-issue doc-drift, see implement.md STEP 12.

4. **HARD GATE: Per-Issue Agent Count Verification**

   After each issue's pipeline completes, BEFORE advancing to the next issue (or to STEP B3.5/B4 if this is the last issue), verify ALL required agents ran for this issue. **This verification applies to ALL issues in the batch, including the LAST issue.**

   **Required agents** (mode-conditional):
   - **Default mode** (acceptance-first): 8 agents — researcher-local, researcher, planner, implementer, reviewer, security-auditor, doc-master, continuous-improvement-analyst
   - **TDD-first mode** (`--tdd-first`): 9 agents — add test-master
   - **Fix mode** (`--fix`): 4 agents — implementer, reviewer, doc-master, continuous-improvement-analyst
   - **Light mode** (`--light`): 4 agents — planner, implementer, doc-master, continuous-improvement-analyst

   **Verification method**: Count the Task tool invocations with distinct `subagent_type` values for the current issue. The coordinator MUST enumerate which agents actually ran.

   **Display after each issue**:
   ```
   Issue #N agent verification:
     researcher-local: ✓/✗
     researcher:       ✓/✗
     planner:          ✓/✗
     test-master:      ✓/✗ (--tdd-first mode only)
     implementer:      ✓/✗
     reviewer:         ✓/✗
     security-auditor: ✓/✗
     doc-master:       ✓/✗
     continuous-improvement-analyst: ✓/✗
   Result: 8/8 PASS (default) | 9/9 PASS (--tdd-first) | 4/4 PASS (--fix) | 4/4 PASS (--light) | X/N FAIL — missing: [list]
   ```

   **If any agent is MISSING**: BLOCK. Do NOT advance to the next issue. Complete the missing agents for this issue first. Then re-verify.

   **FORBIDDEN** (violations = batch failure):
   - ❌ Advancing to the next issue with fewer than the required agents verified for the current mode
   - ❌ Self-reporting agent completion without enumerating each agent by name
   - ❌ Claiming an agent "was not needed" for this issue (all required agents for the current mode must run, no exceptions)
   - ❌ Combining multiple issues into a single agent invocation to "save time"
   - ❌ Counting the coordinator's own reasoning as an agent invocation
   - ❌ Skipping CI analyst for the last issue in the batch (known regression: Issue #505)

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

When invoking agents in batch mode (researcher-local, researcher-web, planner, plan-critic, implementer, reviewer, security-auditor, doc-master — plus test-master if `--tdd-first`), you MUST include this context block at the start of EVERY agent prompt:

```
**BATCH CONTEXT** (CRITICAL - Operating in worktree):
- Worktree Path: $WORKTREE_PATH (absolute path)
- Issue Number: $ISSUE_NUMBER
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
- Issue Number: $ISSUE_NUMBER
- ALL file operations MUST use absolute paths within this worktree
- Read/Write/Edit tools: Use absolute paths like $WORKTREE_PATH/src/file.py
- Bash commands: Run from worktree using: cd $WORKTREE_PATH && [command]

Implement production-quality code for Issue [issue number]: [user's feature description].

**Implementation Plan**: [Paste planner output]
**Tests to Pass**: [Paste test-master output summary]

**Requirements** (HARD GATES — all must be met before returning):
- Write WORKING code — no stubs, no NotImplementedError, no pass placeholders
- Write unit tests alongside implementation (not after — test-driven)
- ALL tests must pass — 0 failures, 0 errors before returning
- If any test fails: fix it, adjust its expectation, or document a specific blocker

Output: Implementation summary with files changed, tests written, and final pytest result (0 failures required)."

model: "sonnet"

model: "sonnet"
```

**This applies to ALL pipeline agents when running in batch mode (7 in default acceptance-first mode, 8 in `--tdd-first` mode).**

**HARD GATE: Prompt Integrity Across Issues** (Issue #544)

The coordinator MUST maintain consistent prompt quality across all issues in the batch. Progressive prompt compression — where later issues receive shorter, summarized, or truncated prompts — is a known regression pattern that degrades security review quality.

**Requirements**:
- Each agent MUST receive prompts of comparable length across all issues in the batch
- Security-critical agents (security-auditor, reviewer, doc-master, implementer, planner) MUST receive at least 80 words in their prompts
- The coordinator MUST log prompt word counts per agent per issue for post-hoc analysis
- The pipeline_intent_validator detects shrinkage >= 20% from the baseline (first issue) automatically (Issue #812)

**Proactive Prevention (Issue #851)**: The per-issue Proactive Template Reload (see STEP B3 per-issue setup) complements this reactive detection. Proactive reload eliminates most compression drift at source; this validation catches any remaining drift as a backstop.

**FORBIDDEN** (violations = batch failure):
- Passing progressively shorter prompts to security-auditor or reviewer in later batch issues
- Omitting diff context or implementation details from validation agent prompts due to context pressure
- Summarizing implementer output for validation agents when full output was passed in earlier issues
- Reducing prompt detail for any agent as the batch progresses (all issues deserve equal analysis depth)

**REQUIRED** (prompt integrity prevention -- Issue #601, #603):

Before each agent invocation in batch mode, the coordinator MUST:

1. **First issue**: After invoking each agent, call `record_prompt_baseline(agent_type, issue_number, word_count)` to establish the baseline
2. **Subsequent issues**: Before invoking each agent:
   a. Get baseline: `baseline = get_prompt_baseline(agent_type)`
   b. Validate: `result = validate_prompt_word_count(agent_type, constructed_prompt, baseline)`
   c. If `result.should_reload` is True: re-read the agent's source file using `get_agent_prompt_template(agent_type)` and reconstruct the prompt from source + issue-specific context, NOT from context memory
   d. Log: include word count in per-issue agent verification display
3. **Batch start**: Call `clear_prompt_baselines()` to reset from any prior batch. Baselines are established automatically from the first observed prompt for each agent per issue — do NOT call `seed_baselines_from_templates()` (deprecated, Issue #810).

The library functions are in `plugins/autonomous-dev/lib/prompt_integrity.py`.

**BATCH LOGGING: Coordinator-Side Agent Completion Log** (Issue #526)

The session_activity_logger hook may miss agent completions in batch context (Issue #526). To ensure complete observability, the coordinator MUST emit a structured log entry after EACH agent returns in batch mode:

```bash
python3 -c "
import json, datetime, os
from pathlib import Path

entry = {
    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'hook': 'BatchCoordinatorLog',
    'tool': 'Agent',
    'subagent_type': 'AGENT_TYPE_HERE',
    'issue_number': ISSUE_NUMBER_HERE,
    'batch_id': '$BATCH_ID',
    'result_word_count': WORD_COUNT_HERE,
    'duration_seconds': DURATION_HERE,
    'session_id': os.environ.get('CLAUDE_SESSION_ID', 'unknown'),
}

# Find log directory
cwd = Path.cwd()
for parent in [cwd] + list(cwd.parents):
    claude_dir = parent / '.claude'
    if claude_dir.exists():
        log_dir = claude_dir / 'logs' / 'activity'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / (datetime.datetime.now().strftime('%Y-%m-%d') + '.jsonl')
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        break
"
```

This provides a backup log of all agent completions even when the PostToolUse hook misses them. The continuous-improvement-analyst can parse `BatchCoordinatorLog` entries alongside regular `PostToolUse` entries.

**REQUIRED**: Emit this log after EVERY agent completion in batch mode (all 7-8 agents per issue).

**STEP B4: Batch Finalization -- Auto-Commit, Merge, Cleanup (Issue #333)**

After ALL features in batch are processed, YOU (the coordinator) MUST finalize:

0. **Drain all remaining agents and verify writes** (Issue #536, #537):
   ```bash
   # Ensure ALL background agents have completed before committing
   # This prevents doc-master writes from being lost
   ```

   **REQUIRED**: Before committing, verify:
   a. ALL background agents (especially doc-master from the last issue) have completed. Use TaskOutput to drain any remaining background tasks.
   b. The post-batch CI analysis (STEP B3.5) has been launched (it can complete after commit, but must be launched before worktree cleanup).
   c. Run `cd $WORKTREE_PATH && git status` to confirm all modified files are visible.

   **FORBIDDEN** (Issue #536):
   - ❌ Running `git add -A && git commit` while any background agent may still be writing files
   - ❌ Deleting the worktree before the post-batch CIA has read the session log
   - ❌ Proceeding to merge without verifying doc-master's file modifications are staged

   **HOOK ENFORCEMENT: Batch CIA Gate** (Issue #712):
   The `unified_pre_tool.py` hook deterministically blocks `git commit` in batch worktrees
   (CWD contains `.worktrees/batch-`) when any issue is missing CIA completion. This is a
   hook-level hard gate — the coordinator cannot bypass it. If the gate fires, run the
   continuous-improvement-analyst for all missing issues before retrying the commit.
   Escape hatch: `SKIP_BATCH_CIA_GATE=1` (environment variable).

1. **Commit all changes** in the worktree:
   ```bash
   cd $WORKTREE_PATH && git add -A && git commit -m "feat: batch implementation

   - Feature 1 description
   - Feature 2 description

   Closes #N1
   Closes #N2

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
   ```

   **HARD GATE (drain-queue durability)**: When this batch was invoked from
   `/drain-queue`, a `.claude/local/drain_pending.json` marker is present and
   the `unified_pre_tool.py` commit gate will REJECT a commit that omits
   `Closes #N` for any cluster issue. The synthesizer MUST list one
   `Closes #N` line per N in `--issues N1,N2,...` before invoking
   `git commit`. See `_check_drain_pending_commit_gate` in the hook for the
   exact match semantics (regex `(?:Closes|Fixes)\s+#(\d+)`, case-insensitive).

2. **Merge to master** from the main repo:
   ```bash
   cd /path/to/main/repo && git merge --no-ff <worktree-branch> -m "Merge batch: feature summaries"
   ```

3. **Cleanup worktree** after successful merge:
   ```bash
   # CRITICAL (Issue #410): Change CWD back to main repo BEFORE deleting worktree.
   # Deleting the worktree while CWD is inside it bricks the shell session.
   cd $PARENT_REPO && rm -rf .worktrees/$BATCH_ID && git worktree prune
   ```

   **FORBIDDEN** (Issue #410):
   - ❌ Deleting a worktree directory while your shell CWD is inside it. ALWAYS `cd` to the main repository FIRST, then delete.

4. **Clean up pipeline state** (MUST happen AFTER confirming post-batch CIA in STEP B3.5 has been launched):
   ```bash
   # CRITICAL: Only clean up AFTER STEP B3.5 CIA is confirmed launched
   # The CIA reads pipeline state — cleaning up before launch loses context
   rm -f "${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}"
   ```

   **FORBIDDEN** (Issue #559):
   - ❌ Cleaning up pipeline state before confirming STEP B3.5 CIA agent launch succeeded
   - ❌ Removing ${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json} before STEP B3.5 CIA has a valid task ID

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

Include per-feature timing breakdown in the summary (see Batch Mode Progress Protocol).

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

**STEP I1: Fetch Issue Details**

Parse issue numbers from ARGUMENTS (after `--issues`).

For each issue number, fetch title, body, and labels:
```bash
gh issue view [number] --json title,body,labels
```

Create feature list: "Issue #N: [title]"

**STEP I1.3: Already-Done Detection**

Before mode detection, check each issue against prior commits using `already_done_detector.check_issue_already_implemented()`. The detector returns a `MatchResult(sha, subject, classification)` NamedTuple only when a HEAD-ancestor commit contains an explicit closure marker (`Closes #N`, `Fixes #N`, `Completed: #N`); it returns `None` for all other cases (no reference, anti-marker like `Pending: #N` or `Preflight-skipped: #N`, or stale-branch commits not in HEAD ancestry).

```python
from already_done_detector import check_issue_already_implemented

for issue_number, title, body in issues:
    result = check_issue_already_implemented(
        issue_number=issue_number,
        title=title,
        body=body,
        repo_root=Path.cwd(),
    )
    if result is not None:
        # result.classification is always "closes" for non-None returns.
        # ("anti" and "stale_branch" results are filtered to None internally
        # so the caller stays simple — no need to switch on classification.)
        print(
            f"SKIP: Issue #{issue_number} already implemented in commit "
            f"{result.sha} (classification={result.classification}): {result.subject}"
        )
        # Auto-close: gh issue comment {issue_number} --body "Already implemented in {result.sha}"
        # Remove from feature list; do not process further.
```

If a match is found, skip that issue (remove from the batch feature list) and optionally add a comment on the GitHub issue referencing the implementing commit. Continue processing remaining issues normally.

**Classification semantics** (informational; the caller does not need to switch on these):
- `closes` — explicit closure marker (`Closes #N`, `Fixes #N`, `Completed: #N`) on a HEAD-ancestor commit. The only classification ever returned to the caller.
- `anti` — explicit non-closure marker (`Pending: #N`, `Preflight-skipped: #N`, `Deferred: #N`). Filtered to `None` internally.
- `stale_branch` — closure marker present but the commit is not reachable from HEAD (unmerged side branch). Filtered to `None` internally.
- `mention` — bare `#N` reference with no marker. Filtered to `None` internally.

**STEP I1.5: Mode Detection and Confirmation**

Use `batch_mode_detector.detect_batch_modes()` to analyze each issue's title, body, and labels.
Display the mode summary table using `format_mode_summary_table()`:

```
Per-Issue Pipeline Mode Detection:

Issue  Title                          Detected Mode  Signals
#101   Fix failing auth test          --fix          "failing test" (title)
#102   Add JWT authentication         full           (no signals)
#103   Update README setup section    --light        "readme" (title)
```

Accept user overrides if provided (e.g., "change #102 to --fix").
Store final modes in `BatchState.feature_modes` (maps feature index to mode string).

Each issue's detected mode determines which pipeline variant runs in STEP B3:
- `full` → full pipeline (implement.md STEPS 1-8)
- `fix` → fix pipeline (implement-fix.md)
- `light` → light pipeline (implement.md --light)

**STEP I2: Create Worktree and Process**

Same as BATCH FILE MODE:
1. Create worktree (see STEP B1)
2. Store absolute worktree path in `WORKTREE_PATH` variable
3. Process each feature (issue title becomes feature description) - **PASS BATCH CONTEXT to ALL agents** (see STEP B3)

   **Per-Issue Pipeline State**: For each issue, create a FRESH pipeline state:
   ```bash
   ISSUE_RUN_ID="issue-${ISSUE_NUMBER}-$(date +%Y%m%d-%H%M%S)"
   python3 -c "
   import sys, os as _os
   for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
       if _os.path.isdir(_p):
           sys.path.insert(0, _p)
           break
   from pipeline_state import create_pipeline, save_pipeline
   state = create_pipeline('$ISSUE_RUN_ID', 'Issue #$ISSUE_NUMBER: $ISSUE_TITLE', mode='batch')
   save_pipeline(state)
   "
   ```

   Before each issue's pipeline starts, set the issue number for ordering enforcement:
   ```bash
   export PIPELINE_ISSUE_NUMBER=$ISSUE_NUMBER
   ```

   **HARD GATE: Proactive Template Reload (Issue #851)**

   Before dispatching ANY agent for this issue, the coordinator MUST proactively reload all critical agent templates from disk. This prevents progressive prompt compression where the coordinator's in-memory prompt representations drift across batch issues.

   ```bash
   python3 -c "
   import sys, os as _os
   for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
       if _os.path.isdir(_p):
           sys.path.insert(0, _p)
           break
   from prompt_integrity import COMPRESSION_CRITICAL_AGENTS, get_agent_prompt_template
   for agent in sorted(COMPRESSION_CRITICAL_AGENTS):
       template = get_agent_prompt_template(agent)
       print(f'{agent}: {len(template.split())} words (fresh from disk)')
   "
   ```

   The coordinator MUST use these fresh-from-disk templates as the basis for constructing agent prompts — do NOT rely on templates from context memory. When constructing each agent's prompt, call `get_agent_prompt_template(agent_type)` to obtain the current template text and append issue-specific context to it.

   **FORBIDDEN**:
   - ❌ Constructing agent prompts from context memory without first reloading from disk
   - ❌ Skipping the proactive reload under context pressure or time constraints
   - ❌ Reusing template text from a previous issue's agent invocation

   After each issue's pipeline completes, cleanup the per-issue pipeline state between issues:
   ```bash
   python3 -c "
   import sys, os as _os
   for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
       if _os.path.isdir(_p):
           sys.path.insert(0, _p)
           break
   from pipeline_state import cleanup_pipeline
   cleanup_pipeline('$ISSUE_RUN_ID')
   " 2>/dev/null || true
   ```

   **Note**: Agent ordering is now hook-enforced by `unified_pre_tool.py` Layer 4 (Issues #625, #629, #632). The hook reads completion state written by `unified_session_tracker.py` and blocks out-of-order agent invocations per-issue.

   The coordinator MUST also follow the **Pre-Dispatch Ordering Protocol** defined in [implement.md](implement.md) before every agent dispatch within each issue's pipeline. The hook is a backstop; the protocol is first-line defense. Issue #850.

### Post-Dispatch Completion Recording Protocol — REQUIRED (Issue #1174)

Symmetric to the Pre-Dispatch Ordering Protocol; same session-ID fallback chain. After EVERY Agent tool returns inside a per-issue pipeline, the batch coordinator MUST synchronously call `record_agent_completion()` BEFORE the next Pre-Dispatch Ordering check. This closes the race documented in Issue #1174 (widening of Issue #852): SubagentStop fires asynchronously, the next pre-dispatch check is synchronous, and a stale read forces manual `record_agent_completion()` injections to satisfy the ordering gate. Recording synchronously at the call site eliminates dependence on SubagentStop timing.

```bash
python3 -c "
import sys, os, json, time
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break

# Reuse the same session-ID fallback chain as Pre-Dispatch (Issue #904):
#   1. CLAUDE_SESSION_ID env var
#   2. ${PIPELINE_STATE_FILE}['session_id'] sentinel (mtime < 3600s)
#   3. 'unknown'
def _resolve_session_id():
    sid = os.environ.get('CLAUDE_SESSION_ID', '').strip()
    if sid and sid != 'unknown':
        return sid
    sentinel = os.environ.get('PIPELINE_STATE_FILE', '/tmp/implement_pipeline_state.json')
    try:
        if os.path.exists(sentinel):
            mtime = os.path.getmtime(sentinel)
            if time.time() - mtime < 3600:
                with open(sentinel) as _f:
                    _state = json.load(_f)
                _recovered = str(_state.get('session_id', '')).strip()
                if _recovered and _recovered != 'unknown':
                    return _recovered
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return 'unknown'

from pipeline_completion_state import record_agent_completion
# Issue #1174: synchronously record completion of the agent that just returned
# so the next Pre-Dispatch Ordering check (within this per-issue pipeline) sees
# fresh state. Safe to call when SubagentStop also fires —
# record_agent_completion is fcntl-locked, tri-scope, last-write-wins (#1046).
record_agent_completion(
    _resolve_session_id(),
    '<AGENT_TYPE>',
    issue_number=ISSUE_NUMBER,
    success=True,
)
print(f'POST-DISPATCH OK: recorded <AGENT_TYPE> for issue #{int(<ISSUE_NUMBER>)}')
"
```

Replace `<AGENT_TYPE>` with the agent that just returned. Replace `ISSUE_NUMBER` with the current issue number being processed in the batch.

**Exception clause**: doc-master in batch mode already satisfies this protocol via the `record_doc_verdict` + `record_agent_completion` block near line 205 (Issue #852). Do NOT double-call for that site.

**Idempotency**: Safe when SubagentStop also fires for the same agent — tri-scope, fcntl-locked, last-write-wins (Issue #1046).

**HARD GATE**: After every Agent dispatch inside a per-issue pipeline, the next observable action MUST be the post-dispatch `record_agent_completion()` call.

**FORBIDDEN**: Dispatching the next Agent within a per-issue pipeline without first synchronously recording the previous Agent's completion.

   **CRITICAL**: Each issue gets a NEW `create_pipeline()` call. Do NOT reuse pipeline state across issues. Create a new pipeline, run the separate pipeline for that issue, then clear/cleanup before starting the next.

   **Per-issue agent verification is MANDATORY** — see STEP B3 point 4 HARD GATE. Every issue must pass the mode-appropriate agent verification (8 in default mode, 9 in `--tdd-first` mode) before the next issue starts.
   **Background agent drain is MANDATORY** — see STEP B3 point 5 HARD GATE. STEP 9 runs in foreground during batch. Max 2 concurrent background agents.

   **Per-issue STEP 9 (Batch Mode CI)**: After each issue's pipeline completes (and passes the agent verification gate), invoke the continuous-improvement-analyst in **batch mode** — a fast, lightweight check (3-5 REQUIRED tool calls, <30 seconds). Pass the agent verification results as context:

   ```
   subagent_type: "continuous-improvement-analyst"
   description: "CI batch analysis — Issue #N"
   prompt: "BATCH MODE (per-issue analysis).
   Agents that ran for Issue #N: [list from verification step with ✓/✗]
   Agent timings: [list agent name + duration + tool use count if available]
   Errors observed: [any errors from implementer/reviewer/security-auditor]
   Pipeline mode: [fix|full|light|tdd-first]
   Expected agents for this mode: [list from get_required_agents() — e.g., "implementer, reviewer, doc-master, continuous-improvement-analyst (4 agents)" for --fix]

   REQUIRED TOOL ACTIONS (you MUST perform these — do not report from context alone):
   1. Run: git diff HEAD -- tests/ | INSPECT for @pytest.mark.skip additions, NotImplementedError, weakened assertions
   2. Read: .claude/config/known_bypass_patterns.json | Verify no undocumented bypasses
   3. Run: grep -r 'pytest.mark.skip' tests/ --include='*.py' -c | Report skip marker count

   After performing ALL required tool actions above, provide a short findings list. Do NOT file issues — defer to post-batch."
   ```

   This replaces the previous heavy per-issue CI analysis. Full analysis happens once post-batch.

   **HARD GATE: Last Issue CI** (Issue #505, #559)

   The final issue in the batch MUST have its per-issue CI analyst check completed BEFORE proceeding to STEP B3.5 (Post-Batch Full CI Analysis) or STEP B4 (Batch Finalization). Skipping CI for the last issue is a known regression pattern.

   Before starting the last issue's CI, output:
   ```
   BATCH FINAL ITEM — Issue #N (last of M)
   ```

   After CI completes, the coordinator MUST verify:
   1. The continuous-improvement-analyst agent was invoked (not skipped)
   2. The agent returned a result (result_word_count > 0)
   3. The per-issue agent verification shows ✓ for continuous-improvement-analyst

   **FORBIDDEN** (violations = batch failure):
   - ❌ Proceeding to STEP B3.5 or STEP B4 without CI analyst completion for the last issue
   - ❌ Treating the last issue differently from any other issue in CI requirements
   - ❌ Skipping CIA for the last issue due to context pressure or time constraints (BLOCK the pipeline instead)
   - ❌ Substituting coordinator-side analysis for the CIA agent invocation on the last issue
   - ❌ Declaring the batch "complete enough" without the last issue's CIA result

4. Git automation (see STEP B4) - triggers at end of batch
5. Report summary (see STEP B5)

**STEP B3.5: Post-Batch Full CI Analysis**

After ALL issues are processed but BEFORE git finalization (STEP B4), run the continuous-improvement-analyst **once** in full mode in the **background** so it does not block STEP B4 git finalization:

```
subagent_type: "continuous-improvement-analyst"
description: "Post-batch CI analysis"
run_in_background: true
prompt: "FULL MODE (post-batch analysis).
Batch contained N issues: [list issue numbers and titles]
Per-issue findings: [aggregate per-issue batch mode results]
Parse session logs for cross-issue patterns. File issues for significant findings.
Session date: YYYY-MM-DD"
```

This single comprehensive analysis replaces N heavy per-issue analyses. It detects cross-issue patterns (progressive shortcutting, recurring bypasses) that per-issue checks cannot see.

**CRITICAL (Issue #537)**: The post-batch CIA MUST be launched BEFORE worktree cleanup (STEP B4 step 3). The CIA needs to read session logs from the worktree. Launch order:
1. STEP B3.5: Launch CIA in background
2. STEP B4 step 1: Commit in worktree (CIA is reading logs in parallel)
3. STEP B4 step 2: Merge to master
4. STEP B4 step 3: Cleanup worktree (CIA has already read what it needs)

If CIA has not been launched yet when you reach STEP B4 step 3, BLOCK worktree cleanup until CIA is launched.

**CRITICAL**: When invoking agents in batch issues mode, include the **BATCH CONTEXT** block (with `$WORKTREE_PATH`) at the start of EVERY agent prompt, exactly as described in STEP B3.

---

## Batch Mode Error Handling

| Error Type | Behavior |
|------------|----------|
| **Transient** (network, timeout) | Retry up to 3 times |
| **Permanent** (syntax, validation) | Mark failed, continue |
| **Security critical** | Block feature, continue batch |
