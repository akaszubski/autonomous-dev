---
name: implement
description: "Smart code implementation with three modes (full pipeline, quick, batch)"
argument-hint: "<feature> | --quick <feature> | --batch <file> | --issues <nums> | --resume <id>"
allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch]
---

# /implement - Unified Smart Implementation

Consolidates `/auto-implement`, `/implement`, and `/batch-implement` into a single smart command.

## Modes

| Mode | Flag | Time | Description |
|------|------|------|-------------|
| **Full Pipeline** | (default) | 15-25 min | Research → Plan → Test → Implement → Review → Security → Docs |
| **Quick** | `--quick` | 2-5 min | Implementer agent only (for pre-planned work) |
| **Batch File** | `--batch <file>` | 20-30 min/feature | Process features from file with auto-worktree |
| **Batch Issues** | `--issues <nums>` | 20-30 min/feature | Process GitHub issues with auto-worktree |
| **Resume** | `--resume <id>` | Continues | Resume interrupted batch from checkpoint |

## Usage

```bash
# Full pipeline (default) - recommended for new features
/implement add user authentication with JWT

# Quick mode - for pre-planned work or docs
/implement --quick fix typo in README

# Batch from file - multiple features with auto-worktree isolation
/implement --batch features.txt

# Batch from GitHub issues - with auto-worktree isolation
/implement --issues 72 73 74

# Resume interrupted batch
/implement --resume batch-20260110-143022
```

---

## Implementation

**You (Claude) are the coordinator for this workflow.**

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Mode and Route

**ACTION REQUIRED**: Parse the ARGUMENTS to determine which mode to use.

Parse flags from ARGUMENTS using this logic:

```python
# Flag detection (conceptual)
args = "{{ARGUMENTS}}"

if "--quick" in args:
    mode = "quick"
    feature = args.replace("--quick", "").strip()
elif "--batch" in args:
    mode = "batch_file"
    batch_file = extract_after_flag(args, "--batch")
elif "--issues" in args:
    mode = "batch_issues"
    issue_numbers = extract_numbers_after_flag(args, "--issues")
elif "--resume" in args:
    mode = "resume"
    batch_id = extract_after_flag(args, "--resume")
else:
    mode = "full_pipeline"
    feature = args.strip()
```

**ACTION REQUIRED**: Before routing, activate the pipeline state file so the workflow enforcement hook allows edits from both subagents and the main process:

```bash
echo '{"session_start": "'$(date -u +%Y-%m-%dT%H:%M:%S)'", "mode": "'$mode'"}' > /tmp/implement_pipeline_state.json
```

**Route based on mode**:
- **full_pipeline** → Continue to STEP 1 (Full Pipeline)
- **quick** → Jump to QUICK MODE section
- **batch_file** → Jump to BATCH FILE MODE section
- **batch_issues** → Jump to BATCH ISSUES MODE section
- **resume** → Jump to RESUME MODE section

---

# FULL PIPELINE MODE (Default)

This is the complete 8-agent SDLC workflow. Execute steps IN ORDER.

---

### STEP 1: Validate PROJECT.md Alignment

**ACTION REQUIRED**: Before any implementation work:

1. Read `.claude/PROJECT.md` from the repository
2. Extract GOALS, SCOPE, and CONSTRAINTS sections
3. Check alignment:
   - Does the feature serve any GOAL?
   - Is the feature explicitly IN SCOPE?
   - Does the feature violate any CONSTRAINT?

**If NOT aligned**, BLOCK immediately and respond:

```
❌ BLOCKED: Feature not aligned with PROJECT.md

Feature requested: [user request]
Why blocked: [specific reason]
  - Not in SCOPE: [what scope says]
  - OR doesn't serve GOALS: [which goals]
  - OR violates CONSTRAINTS: [which constraints]

Options:
1. Modify feature to align with current SCOPE
2. Update PROJECT.md if strategy changed
3. Don't implement
```

**If aligned**, proceed to STEP 2.

---

### STEP 2: Parallel Research (researcher-local + researcher-web Simultaneously)

⚠️ **ACTION REQUIRED NOW**: Invoke TWO research agents in PARALLEL (single response).

**CRITICAL**: You MUST call Task tool TWICE in a single response. This enables parallel execution and reduces research time from 5-6 minutes to 3 minutes (45% faster).

#### Task Tool Call 1: researcher-local

Use the Task tool with these parameters:
- **subagent_type**: `"researcher-local"`
- **model**: `"haiku"`
- **description**: `"Search codebase for [feature name]"`
- **prompt**: Search codebase for patterns related to [user's feature]. Find existing patterns, files to update, architecture notes, similar implementations. Output JSON.

#### Task Tool Call 2: Web Research (using general-purpose)

Use the Task tool with these parameters:
- **subagent_type**: `"general-purpose"`
- **model**: `"sonnet"`
- **description**: `"Research best practices for [feature name]"`
- **prompt**: "You are a web researcher. You MUST use the WebSearch tool to search the web. Search for best practices and standards for: [user's feature description]. Use WebSearch to find: industry best practices (2024-2025), recommended libraries, security considerations (OWASP), common pitfalls. IMPORTANT: Actually call WebSearch - do not answer from memory. Output JSON with best_practices, recommended_libraries, security_considerations, common_pitfalls, and include source URLs."

**DO BOTH NOW IN ONE RESPONSE**.

---

### STEP 2.1: Validate Web Research (MANDATORY)

⚠️ **BEFORE MERGING**: Check the tool use counts from both agents:

| Agent | Expected | If 0 tool uses |
|-------|----------|----------------|
| researcher-local | 10-30 tool uses | Acceptable if codebase is small |
| web research (general-purpose) | **1+ tool uses** | ❌ **FAIL - web search didn't happen** |

**If web research shows 0 tool uses**: Retry the web research agent.

**Only proceed to merge if web research shows 1+ tool uses.**

---

### STEP 2.2: Merge Research Findings

Combine codebase context and external guidance into unified context for planner.

---

### STEP 3: Invoke Planner Agent

⚠️ **ACTION REQUIRED**: Invoke planner NOW with merged research findings.

**Call Task tool with**:

```
subagent_type: "planner"
description: "Plan [feature name]"
prompt: "Create detailed implementation plan for: [user's feature description].

**Codebase Context**: [Paste researcher-local output]
**External Guidance**: [Paste researcher-web output]

Include: File structure, dependencies, integration points, edge cases, security requirements, testing strategy.

Output: Step-by-step implementation plan with file-by-file breakdown."

model: "sonnet"
```

---

### STEP 4: Invoke Test-Master Agent (TDD)

⚠️ **ACTION REQUIRED**: Tests MUST be written BEFORE implementation.

**Call Task tool with**:

```
subagent_type: "test-master"
description: "Write tests for [feature name]"
prompt: "Write comprehensive tests for: [user's feature description].

**Implementation Plan**: [Paste planner output]

Output: Comprehensive test files with unit tests, integration tests, edge case coverage."

model: "sonnet"
```

---

### STEP 5: Invoke Implementer Agent

⚠️ **ACTION REQUIRED**: Now that tests exist, implement to make them pass.

**Call Task tool with**:

```
subagent_type: "implementer"
description: "Implement [feature name]"
prompt: "Implement production-quality code for: [user's feature description].

**Implementation Plan**: [Paste planner output]
**Tests to Pass**: [Paste test-master output summary]

Output: Production-quality code following the architecture plan."

model: "sonnet"
```

**After implementer completes**, YOU (the coordinator) MUST run tests and resolve ALL failures before STEP 6:

```bash
pytest --tb=short -q
```

**Read the output carefully. If there are ANY failures, you are NOT done with STEP 5.**

⚠️ **HARD GATE - DO NOT PROCEED UNTIL RESOLVED**:

ALL tests MUST show **0 failures, 0 errors** before moving to STEP 6. This is NON-NEGOTIABLE.

**If ANY test fails, you MUST do one of these three things for EACH failing test:**

1. **Fix it** - Debug and fix the code or test until it passes
2. **Mark it as not implemented** - Add `@pytest.mark.skip(reason="Not yet implemented: [description]")` with a clear reason
3. **Make it work** - Adjust the test expectations to match correct behavior

**You are FORBIDDEN from:**
- ❌ Saying "X% passing is good enough" and proceeding
- ❌ Describing failures as a "solid foundation"
- ❌ Categorizing failures as "expected" without fixing or skipping them
- ❌ Proceeding to STEP 6 with ANY test failures or errors
- ❌ Blaming infrastructure (SQLite, mocks, etc.) without resolving

**Run `pytest --tb=short -q` and verify the output shows 0 failures. If not, loop back and resolve EVERY failure.**

**Only when pytest output shows `X passed, 0 failed` (or all failures are marked as skipped) may you proceed.**

---

### STEP 6: Parallel Validation (3 Agents Simultaneously)

⚠️ **ACTION REQUIRED**: Invoke THREE validation agents in PARALLEL (single response).

#### Validator 1: Reviewer

```
subagent_type: "reviewer"
description: "Review [feature name]"
prompt: "Review implementation in: [list files]. Check code quality, pattern consistency, test coverage, error handling, edge cases, documentation. Output: APPROVAL or list of issues."
model: "sonnet"
```

#### Validator 2: Security-Auditor

```
subagent_type: "security-auditor"
description: "Security scan [feature name]"
prompt: "Scan implementation in: [list files]. Check for hardcoded secrets, SQL injection, XSS, insecure dependencies, OWASP Top 10. Output: Security PASS/FAIL."
model: "haiku"
```

#### Validator 3: Doc-Master

```
subagent_type: "doc-master"
description: "Update docs for [feature name]"
prompt: "Update documentation for feature: [feature name]. Update README.md, CHANGELOG.md, docstrings. Output: All documentation updated."
model: "haiku"
```

**DO ALL THREE NOW IN ONE RESPONSE**.

---

### STEP 7: Final Verification

⚠️ **CHECKPOINT**: Verify all 8 agents ran:
1. researcher-local ✅
2. researcher-web ✅
3. planner ✅
4. test-master ✅
5. implementer ✅
6. reviewer ✅
7. security-auditor ✅
8. doc-master ✅

**If count != 8, invoke missing agents NOW.**

---

### STEP 8: Report Completion

```
✅ Feature complete! All 8 agents executed successfully.

📊 Pipeline Summary:
1. researcher-local: [1-line summary]
2. researcher-web: [1-line summary]
3. planner: [1-line summary]
4. test-master: [1-line summary]
5. implementer: [1-line summary]
6. reviewer: [1-line summary]
7. security-auditor: [1-line summary]
8. doc-master: [1-line summary]

📁 Files changed: [count] files
🧪 Tests: [count] tests created/updated
🔒 Security: [PASS/FAIL]
📖 Documentation: [list docs updated]

Feature is ready to commit!
```

**Cleanup**: Remove the pipeline state file:
```bash
rm -f /tmp/implement_pipeline_state.json
```

---

# QUICK MODE

Quick mode invokes only the implementer agent for pre-planned work.

**When to use**: Documentation updates, config changes, pre-planned features where tests already exist.

**ACTION REQUIRED**: Invoke the implementer agent.

```
subagent_type: "implementer"
description: "Implement [feature name]"
prompt: "Implement code for: [feature description from ARGUMENTS minus --quick flag].

Follow existing patterns. Make tests pass if they exist."

model: "sonnet"
```

After completion, report:

```
✅ Quick implementation complete!

📁 Files changed: [list]
🧪 Tests: Run `pytest` to verify

Consider running `/implement [feature]` (without --quick) for full pipeline.
```

**Cleanup**: Remove the pipeline state file:
```bash
rm -f /tmp/implement_pipeline_state.json
```

---

### STEP Q2: Git Automation (Issue #258)

**After quick mode completes**, trigger git automation if enabled:

```bash
# Check if AUTO_GIT_ENABLED and trigger git workflow
if [ "$AUTO_GIT_ENABLED" = "true" ]; then
  FORCE_GIT_TRIGGER=true python3 ~/.claude/hooks/unified_git_automation.py 2>/dev/null || true
fi
```

This ensures git automation works in quick mode (where doc-master doesn't run).

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
🌲 Created isolated worktree: .worktrees/$BATCH_ID
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

**STEP B3: Process Each Feature (Auto-Continuation Loop)**

**CRITICAL**: Batch must auto-continue through ALL features without manual intervention.

Execute this loop until all features are processed:

```bash
# Process all features with auto-continuation
while true; do
    # Load current batch state
    STATE_FILE=".worktrees/$BATCH_ID/.claude/batch_state.json"

    # Get next pending feature using batch_state_manager API
    NEXT_FEATURE=$(python3 -c "
import sys
from pathlib import Path

# Add lib to path
project_root = Path.cwd()
lib_path = project_root / 'plugins' / 'autonomous-dev' / 'lib'
sys.path.insert(0, str(lib_path))

from batch_state_manager import load_batch_state, get_next_pending_feature

state = load_batch_state('$STATE_FILE')
next_feat = get_next_pending_feature(state)
print(next_feat if next_feat else '')
")

    # Exit loop if no more features
    if [ -z "$NEXT_FEATURE" ]; then
        echo "All features processed. Exiting batch loop."
        break
    fi

    # Get current feature index and total for progress tracking
    FEATURE_INDEX=$(python3 -c "
import sys
from pathlib import Path

project_root = Path.cwd()
lib_path = project_root / 'plugins' / 'autonomous-dev' / 'lib'
sys.path.insert(0, str(lib_path))

from batch_state_manager import load_batch_state

state = load_batch_state('$STATE_FILE')
print(state.current_index)
")

    TOTAL_FEATURES=$(python3 -c "
import sys
from pathlib import Path

project_root = Path.cwd()
lib_path = project_root / 'plugins' / 'autonomous-dev' / 'lib'
sys.path.insert(0, str(lib_path))

from batch_state_manager import load_batch_state

state = load_batch_state('$STATE_FILE')
print(state.total_features)
")

    # Display progress
    echo ""
    echo "=========================================="
    echo "Batch Progress: Feature $((FEATURE_INDEX + 1))/$TOTAL_FEATURES"
    echo "Processing: $NEXT_FEATURE"
    echo "=========================================="
    echo ""

    # Invoke full pipeline (STEPS 1-8) with BATCH CONTEXT
    # CRITICAL: Include BATCH CONTEXT in ALL agent prompts (see section below)
    #
    # Execute full 8-agent pipeline for this feature:
    # 1. researcher-local
    # 2. researcher-web
    # 3. planner
    # 4. test-master
    # 5. implementer
    # 6. reviewer
    # 7. security-auditor
    # 8. doc-master
    #
    # All agents MUST receive BATCH CONTEXT (worktree path) in their prompts

    # Track whether feature succeeded or failed
    FEATURE_SUCCESS=true
    ERROR_MESSAGE=""

    # Execute pipeline (replace with actual pipeline invocation)
    # For now, this is pseudocode showing the error handling pattern
    if ! invoke_full_pipeline_for_feature "$NEXT_FEATURE" "$WORKTREE_PATH"; then
        FEATURE_SUCCESS=false
        ERROR_MESSAGE="Pipeline failed for Feature $((FEATURE_INDEX + 1))"
    fi

    # Update batch progress based on success/failure
    if [ "$FEATURE_SUCCESS" = true ]; then
        # Feature succeeded - mark as completed
        python3 -c "
import sys
from pathlib import Path

project_root = Path.cwd()
lib_path = project_root / 'plugins' / 'autonomous-dev' / 'lib'
sys.path.insert(0, str(lib_path))

from batch_state_manager import update_batch_progress

update_batch_progress(
    '$STATE_FILE',
    $FEATURE_INDEX,
    'completed',
    context_token_delta=5000  # Estimate tokens used
)
print('Feature $((FEATURE_INDEX + 1)) completed successfully')
"
    else
        # Feature failed - mark as failed and continue to next
        python3 -c "
import sys
from pathlib import Path

project_root = Path.cwd()
lib_path = project_root / 'plugins' / 'autonomous-dev' / 'lib'
sys.path.insert(0, str(lib_path))

from batch_state_manager import update_batch_progress

update_batch_progress(
    '$STATE_FILE',
    $FEATURE_INDEX,
    'failed',
    context_token_delta=5000,  # Estimate tokens used
    error_message='$ERROR_MESSAGE'
)
print('⚠️ Feature $((FEATURE_INDEX + 1)) failed: $ERROR_MESSAGE')
print('Continuing to next feature...')
"
    fi

    # Loop continues to next feature automatically
done
```

**Key Implementation Points**:

1. **Loop APIs** (already implemented in `batch_state_manager.py`):
   - `get_next_pending_feature(state)` - Returns next feature or None when complete
   - `update_batch_progress()` - Updates state after each feature

2. **Error Handling**: Failed features are recorded but batch continues

3. **Infinite Loop Prevention**: Explicit None check from `get_next_pending_feature()`

4. **Resume Support**: Same loop pattern works for both initial run and resume

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

**STEP B4: Git Automation (Issue #258)**

After ALL features in batch are processed, trigger git automation if enabled:

```bash
# Trigger git automation for batch completion
if [ "$AUTO_GIT_ENABLED" = "true" ]; then
  FORCE_GIT_TRIGGER=true python3 ~/.claude/hooks/unified_git_automation.py 2>/dev/null || true
fi
```

**STEP B5: Batch Summary**

```
========================================
BATCH COMPLETE
========================================

Worktree: .worktrees/$BATCH_ID
Total features: N
Completed successfully: M
Failed: (N - M)

To merge to main:
  cd .worktrees/$BATCH_ID
  git checkout main && git merge $BATCH_ID

To discard:
  git worktree remove .worktrees/$BATCH_ID
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
1. Create worktree (see BATCH FILE MODE STEP B1)
2. Store absolute worktree path in `WORKTREE_PATH` variable
3. Process each feature (issue title becomes feature description) - **PASS BATCH CONTEXT to ALL agents** (see BATCH FILE MODE STEP B3)
4. Git automation (see BATCH FILE MODE STEP B4) - triggers at end of batch
5. Report summary (see BATCH FILE MODE STEP B5)

**CRITICAL**: When invoking agents in batch issues mode, include the **BATCH CONTEXT** block (with `$WORKTREE_PATH`) at the start of EVERY agent prompt, exactly as described in BATCH FILE MODE STEP B3.

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
❌ Batch not found: $BATCH_ID

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
🔄 Resuming batch: $BATCH_ID
   Worktree path: $WORKTREE_PATH
   Progress: Feature M of N
   Completed: [list completed]
   Remaining: [list remaining]

Continuing from feature M...
```

**STEP R3: Continue Processing**

Continue the batch loop from `current_index`, same as BATCH FILE MODE STEP B3.

**STEP R4: Git Automation**

After batch completion, trigger git automation (same as BATCH FILE MODE STEP B4).

**CRITICAL**: When invoking agents in resume mode, include the **BATCH CONTEXT** block (with `$WORKTREE_PATH`) at the start of EVERY agent prompt, exactly as described in BATCH FILE MODE STEP B3.

---

## Batch Mode Error Handling

In batch modes, errors are recorded but non-blocking:

| Error Type | Behavior |
|------------|----------|
| **Transient** (network, timeout) | Retry up to 3 times |
| **Permanent** (syntax, validation) | Mark failed, continue |
| **Security critical** | Block feature, continue batch |

---

## Environment Variables

```bash
# Auto-approve for unattended operation
MCP_AUTO_APPROVE=true

# Git automation
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true

# Force git trigger (used internally by /implement for quick/batch modes)
# Issue #258: Ensures git automation works in all modes
FORCE_GIT_TRIGGER=true

# Batch retry
BATCH_RETRY_ENABLED=true
```

---

## Migration from Old Commands

| Old Command | New Command |
|-------------|-------------|
| `/auto-implement "feature"` | `/implement "feature"` |
| `/implement "feature"` | `/implement --quick "feature"` |
| `/batch-implement file.txt` | `/implement --batch file.txt` |
| `/batch-implement --issues 1 2 3` | `/implement --issues 1 2 3` |
| `/batch-implement --resume id` | `/implement --resume id` |

The old commands still work via deprecation shims but show a notice.

---

## Technical Details

**Agents Used** (full pipeline):
1. researcher-local (Haiku) - Codebase patterns
2. researcher-web (Sonnet) - Best practices
3. planner (Sonnet) - Implementation plan
4. test-master (Sonnet) - TDD tests
5. implementer (Sonnet) - Production code
6. reviewer (Sonnet) - Quality gate
7. security-auditor (Haiku) - Vulnerability scan
8. doc-master (Haiku) - Documentation

**Libraries**:
- `batch_orchestrator.py` - Flag parsing, mode routing, worktree creation
- `batch_state_manager.py` - Persistent state management
- `path_utils.py` - Worktree-aware path resolution

---

**Issue**: GitHub #203 (Command consolidation)
**Version**: 3.47.0
**Related**: `/worktree`, `/sync`
