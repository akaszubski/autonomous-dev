---
name: batch-implement
description: Execute multiple features sequentially with automatic context management
author: Claude
version: 3.0.0
date: 2025-11-16
---

# /batch-implement - Overnight Feature Queue

Process multiple features unattended - queue them up, let it run overnight, wake up to completed work.

## Usage

```bash
/batch-implement features.txt
```

## Input Format

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

## How It Works

**Simple loop**:

1. Read features.txt
2. Parse features (skip comments, empty lines, duplicates)
3. For each feature:
   - `/auto-implement {feature}`
   - `/clear`
   - Next feature
4. Done

---

## Implementation

Invoke the batch orchestration workflow to process features sequentially with automatic context management.

**You (Claude) orchestrate this workflow manually** - read features, loop through each one, invoke /auto-implement, clear context, next.

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

5. **Clear context** using SlashCommand tool:
   ```
   SlashCommand(command="/clear")
   ```

   **CRITICAL**: This prevents context bloat. Without clearing, you'll hit context limits after 3-4 features.

6. **Continue to next feature**

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

Without these, the batch will pause for permission prompts.

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

---

## Tips

1. **Start small**: Test with 2-3 features first to verify setup
2. **Check .env**: Ensure MCP_AUTO_APPROVE=true and AUTO_GIT_ENABLED=true
3. **Feature order**: Put critical features first (in case batch interrupted)
4. **Feature size**: Keep features small and focused (easier to debug failures)
5. **Overnight runs**: Perfect for 10-20 features while you sleep

---

**Version**: 3.0.0 (Simple orchestration - no Python libraries)
**Issue**: #75 (Batch implementation)
**Changed**: Removed complex Python libraries, pure Claude orchestration
