---
name: batch-implement
description: Execute multiple features sequentially with automatic context management and crash recovery
author: Claude
version: 3.3.0
date: 2025-11-17
---

# /batch-implement - Overnight Feature Queue

Process multiple features unattended - queue them up, let it run overnight, wake up to completed work.

## Usage

```bash
# Start new batch from file
/batch-implement features.txt

# Start new batch from GitHub issues (requires gh CLI)
/batch-implement --issues 72 73 74

# Continue after crash
/batch-implement --resume <batch-id>
```

**Prerequisites for --issues flag**:
- gh CLI v2.0+ installed (`brew install gh`, `apt install gh`, or `winget install GitHub.cli`)
- Authentication: `gh auth login` (one-time setup)

**State Management** (v3.1.0+):
- Persistent state file: `.claude/batch_state.json`
- Automatic compression: Claude Code manages context automatically (no manual intervention)
- Crash recovery: Continue with `--resume <batch-id>` flag
- Progress tracking: Completed features, failed features, processing history

## Input Formats

### Option 1: File-Based

Plain text file, one feature per line:

```text
# Authentication
Add user login with JWT
Add password reset flow

# API features
Add rate limiting to endpoints
Add API versioning
```

**Rules**:
- One feature per line
- Lines starting with `#` are comments (skipped)
- Empty lines are skipped
- Keep features under 500 characters each

### Option 2: GitHub Issues (NEW in v3.2.0)

Fetch issue titles directly from GitHub:

```bash
/batch-implement --issues 72 73 74
```

**How it works**:
1. Parse issue numbers from arguments
2. Validate issue numbers (positive integers, max 100 issues)
3. Fetch issue titles via gh CLI: `gh issue view <number> --json title`
4. Format as features: "Issue #72: [title from GitHub]"
5. Create batch state with `issue_numbers` and `source_type='issues'`

**Requirements**:
- gh CLI v2.0+ installed and authenticated
- Valid issue numbers in current repository
- Network connectivity to GitHub

**Graceful Degradation**:
- If issue not found: Skip and continue with remaining issues
- If gh CLI not installed: Error message with installation instructions
- If authentication missing: Error message with `gh auth login` instructions

**Mutually Exclusive**: Cannot use both `<file>` and `--issues` in same command

## How It Works

**State-based workflow** (v3.1.0+):

1. Read features.txt
2. Parse features (skip comments, empty lines, duplicates)
3. **Create batch state** → Save to `.claude/batch_state.json`
4. For each feature:
   - `/auto-implement {feature}`
   - Update batch state (mark feature complete)
   - Next feature
5. Cleanup state file on success

**Automatic Compression**: Claude Code manages context automatically with its 200K token budget. The system compresses context in the background when needed - no manual intervention required.

**Crash Recovery**: If batch is interrupted:
- State file persists: `.claude/batch_state.json`
- Contains: completed features, current index, failed features, processing history
- Continue: `/batch-implement --resume <batch-id>`
- System automatically skips completed features and continues from current index

**State File Example** (File-based):
```json
{
  "batch_id": "batch-20251116-123456",
  "features_file": "/path/to/features.txt",
  "total_features": 10,
  "current_index": 3,
  "completed_features": [0, 1, 2],
  "failed_features": [],
  "context_token_estimate": 145000,
  "auto_clear_count": 2,
  "auto_clear_events": [
    {"feature_index": 2, "tokens_before": 155000, "timestamp": "2025-11-16T10:30:00Z"}
  ],
  "status": "in_progress",
  "issue_numbers": null,
  "source_type": "file"
}
```

**State File Example** (GitHub Issues):
```json
{
  "batch_id": "batch-20251116-140000",
  "features_file": "",
  "features": [
    "Issue #72: Add logging feature",
    "Issue #73: Fix batch processing bug",
    "Issue #74: Update documentation"
  ],
  "total_features": 3,
  "current_index": 1,
  "completed_features": [0],
  "failed_features": [],
  "context_token_estimate": 85000,
  "auto_clear_count": 0,
  "auto_clear_events": [],
  "status": "in_progress",
  "issue_numbers": [72, 73, 74],
  "source_type": "issues"
}
```

**New Fields** (v3.2.0):
- `issue_numbers`: List of GitHub issue numbers (null for file-based batches)
- `source_type`: Either "file" or "issues" (tracks batch source)

---

## Implementation

Invoke the batch orchestration workflow to process features sequentially with automatic context management.

**You (Claude) orchestrate this workflow** - read features, loop through each one, invoke /auto-implement, next.

ARGUMENTS: {{ARGUMENTS}} (path to features.txt)

### STEP 1: Read and Parse Features

**Action**: Use the Read tool to read the features file

Parse the content:
- Skip lines starting with `#` (comments)
- Skip empty lines (just whitespace)
- Skip duplicate features
- Collect unique features into a list

Display to user:
```
Found N features in features.txt:
  1. Feature one
  2. Feature two
  3. Feature three
  ...

Ready to process N features. This will run unattended.
Starting batch processing...
```

---

### STEP 2: Create Todo List

**Action**: Use TodoWrite tool to create todo items for tracking

Create one todo per feature:
```
[
  {"content": "Feature 1", "status": "pending", "activeForm": "Processing Feature 1"},
  {"content": "Feature 2", "status": "pending", "activeForm": "Processing Feature 2"},
  ...
]
```

This gives visual progress tracking during batch execution.

---

### STEP 3: Process Each Feature

**Action**: Loop through features sequentially

**For each feature (1 through N)**:

1. **Mark todo as in_progress** using TodoWrite

2. **Display progress**:
   ```
   ========================================
   Batch Progress: Feature M/N
   ========================================
   Feature: {feature description}
   ```

3. **Invoke /auto-implement** using SlashCommand tool:
   ```
   SlashCommand(command="/auto-implement {feature}")
   ```

   Wait for completion (this runs the full autonomous workflow):
   - Alignment check
   - Research
   - Planning
   - TDD tests
   - Implementation
   - Review + Security + Docs (parallel)
   - Git automation (if enabled)

4. **Mark todo as completed** using TodoWrite

5. **Continue to next feature**

---

### STEP 4: Summary Report

**Action**: After all features processed, display summary

```
========================================
BATCH COMPLETE
========================================

Total features: N
Completed successfully: M
Failed: (N - M)

Time: {estimate based on typical /auto-implement duration}

All features have been processed.
Check git commits for individual feature implementations.
========================================
```

---

## Prerequisites for Unattended Operation

**Required environment variables** (set in `.env` file):

```bash
# Auto-approve tool calls (no permission prompts)
MCP_AUTO_APPROVE=true

# Auto git operations (commit, push, PR)
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true
AUTO_GIT_PR=false  # Optional - set true if you want auto PRs
```

Without these, permission prompts will interrupt the workflow.

---

## Example

**features.txt**:
```text
# Bug fixes
Fix login timeout issue
Fix memory leak in background jobs

# New features
Add email notifications
Add export to CSV
Add dark mode toggle
```

**Command**:
```bash
/batch-implement features.txt
```

**Output**:
```
Found 5 features in features.txt:
  1. Fix login timeout issue
  2. Fix memory leak in background jobs
  3. Add email notifications
  4. Add export to CSV
  5. Add dark mode toggle

Starting batch processing...

========================================
Batch Progress: Feature 1/5
========================================
Feature: Fix login timeout issue

[/auto-implement runs full workflow...]
[Context cleared]

========================================
Batch Progress: Feature 2/5
========================================
Feature: Fix memory leak in background jobs

[/auto-implement runs full workflow...]
[Context cleared]

...

========================================
BATCH COMPLETE
========================================

Total features: 5
Completed successfully: 5
Failed: 0

All features have been processed.
========================================
```

---

## Timing

**Per feature**: ~20-30 minutes (same as single `/auto-implement`)

**Batch of 10 features**: ~3-5 hours
**Batch of 20 features**: ~6-10 hours (perfect for overnight)

**Recommendation**: Queue 10-20 features max per batch.

---

## Error Handling

**If a feature fails**:
- Mark todo as failed (not completed)
- Continue to next feature (don't abort entire batch)
- Report failures in summary

**Continue-on-failure is default** - one bad feature won't stop the batch.

**GitHub Issues --issues flag errors**:

1. **gh CLI not installed**:
   ```
   ERROR: gh CLI not found.
   
   Install gh CLI:
     macOS: brew install gh
     Ubuntu: apt install gh
     Windows: winget install GitHub.cli
   ```

2. **Not authenticated**:
   ```
   ERROR: gh CLI not authenticated.
   
   Run: gh auth login
   ```

3. **Issue not found**:
   ```
   WARNING: Issue #999 not found, skipping...
   Continuing with remaining issues: #72, #73, #74
   ```

4. **Invalid issue numbers**:
   ```
   ERROR: Invalid issue number: -5
   Issue numbers must be positive integers
   ```

5. **Too many issues**:
   ```
   ERROR: Too many issues (150 provided, max 100)
   Please split into multiple batches
   ```

6. **Mutually exclusive arguments**:
   ```
   ERROR: Cannot use both <file> and --issues
   Usage: /batch-implement <file> OR /batch-implement --issues <numbers>
   ```

---

## Automatic Context Management

Claude Code automatically manages context with its 200K token budget. The system compresses and prunes context in the background when needed - fully automatic with no user intervention required.

### How It Works

1. **Claude Code tracks context internally** (200K token budget)
2. **Automatic compression** when approaching limits (transparent to user)
3. **Background pruning** removes less-relevant context
4. **Continuous processing** without pauses or interruptions

### Benefits

- **Fully unattended**: Process 50+ features without interruption
- **No user intervention**: System handles context automatically
- **Simplified workflow**: Continuous processing with no interruptions
- **Trust platform capabilities**: Leverage Claude Code's built-in context management

---

## Tips

1. **Start small**: Test with 2-3 features first to verify setup
2. **Check .env**: Ensure MCP_AUTO_APPROVE=true and AUTO_GIT_ENABLED=true
3. **Feature order**: Put critical features first (in case batch interrupted)
4. **Feature size**: Keep features small and focused (easier to debug failures)
5. **Overnight runs**: Perfect for 10-20 features while you sleep
6. **Trust the platform**: Claude Code manages context automatically - no manual intervention needed

---

**Version**: 3.0.0 (Simple orchestration - no Python libraries)
**Issue**: #75 (Batch implementation)
**Changed**: Removed complex Python libraries, pure Claude orchestration
