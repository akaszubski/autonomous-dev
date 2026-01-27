# Batch Feature Processing

**Last Updated**: 2026-01-19
**Version**: Enhanced in v3.24.0, Simplified in v3.32.0 (Issue #88), Automatic retry added v3.33.0 (Issue #89), Consent bypass added v3.35.0 (Issue #96), Git automation added v3.36.0 (Issue #93), Dependency analysis added v3.44.0 (Issue #157), State persistence fix v3.45.0, Deprecated context clearing functions removed v3.46.0 (Issue #218), Command consolidation v3.47.0 (Issue #203), Quality persistence enforcement added v1.0.0 (Issue #254)
**Command**: `/implement --batch`, `/implement --issues`, `/implement --resume`

> **Migration Note**: The `/implement --batch` command is deprecated. Use `/implement --batch`, `/implement --issues`, or `/implement --resume` instead. See [Migration Guide](#migration-guide).

This document describes the batch feature processing system for sequential multi-feature development with intelligent state management, automatic worktree isolation, and per-feature git automation.

---

## Overview

Process multiple features sequentially with intelligent state management and automatic context management. Supports 50+ features without manual intervention.

**Workflow**: Parse input → Create batch state → For each: `/implement` → Continue (Claude Code handles context automatically)

---

## Usage Options

### 1. File-Based Input

Create a plain text file with one feature per line:

```text
# Authentication
Add user login with JWT
Add password reset flow
```

Then run:

```bash
/implement --batch <features-file>
```

### 2. GitHub Issues Input

Fetch feature titles directly from GitHub issues:

```bash
/implement --issues 72 73 74
# Fetches: "Issue #72: [title]", "Issue #73: [title]", "Issue #74: [title]"
```

### 3. Resume Interrupted Batch

Continue a batch that was interrupted:

```bash
/implement --resume batch-20260110-143022
```

**Requirements**:
- gh CLI v2.0+ installed
- One-time authentication: `gh auth login`

---

## Prerequisites for Unattended Batch Processing (NEW in v3.35.0 - Issue #96)

For fully unattended batch processing (4-5 features, ~2 hours), configure git automation to bypass interactive prompts.

**Why This Matters**: By default, `/implement` prompts for consent on first run. During batch processing, this prompt blocks the entire batch from continuing, defeating the purpose of unattended processing.

### Configure for Unattended Batches

**Option 1: Environment Variable (Recommended)**

Create or update `.env` in your project root:

```bash
# Enable automatic git operations (no prompts during batch)
AUTO_GIT_ENABLED=true

# Optional: Control specific git operations
AUTO_GIT_PUSH=true   # Default: auto-push to remote
AUTO_GIT_PR=true     # Default: auto-create pull requests
```

Then run your batch:

```bash
/implement --batch features.txt
# No prompts - runs fully unattended
```

**Option 2: Environment Variables (Shell)**

Set environment variables before running batch:

```bash
export AUTO_GIT_ENABLED=true
export AUTO_GIT_PUSH=true
export AUTO_GIT_PR=true

/implement --batch features.txt
```

**Option 3: Minimal (Commit Only, No Push)**

If you prefer committing locally without pushing during batch:

```bash
# .env file
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=false    # Don't push during batch
```

Then:

```bash
/implement --batch features.txt
# Features committed locally, not pushed
# Manually push when batch completes: git push
```

### How It Works

**Issue #96 (v3.35.0)**: `/implement` STEP 5 now checks `AUTO_GIT_ENABLED` environment variable BEFORE showing interactive consent prompt.

**Behavior**:
- `AUTO_GIT_ENABLED=true` (or not set): Auto-proceed with git operations, skip prompt
- `AUTO_GIT_ENABLED=false`: Skip git operations entirely, skip prompt
- First run without env var: Shows interactive consent prompt (stored for future runs)

**In Batches**: When processing multiple features, the environment variable is checked for each feature:
- Feature 1: Checks env var → auto-proceeds (no prompt)
- Feature 2: Checks env var → auto-proceeds (no prompt)
- Feature 3-5: Checks env var → auto-proceeds (no prompt)

Result: Fully unattended processing with zero blocking prompts.

### Verification

Before starting your batch, verify configuration:

```bash
# Check environment variable
echo $AUTO_GIT_ENABLED

# Or check .env file
cat .env | grep AUTO_GIT
```

Expected output:
```
AUTO_GIT_ENABLED=true
```

---

## State Management (Enhanced in v3.24.0)

### Persistent State

State tracked in `.claude/batch_state.json`:

```json
{
  "batch_id": "batch-20251116-123456",
  "current_index": 3,
  "completed": ["feature1", "feature2", "feature3"],
  "failed": [],
  "status": "in_progress",
  "context_token_estimate": 85000,
  "issue_numbers": [72, 73, 74],
  "source_type": "github_issues"
}
```

---

## Dependency Analysis (NEW in v3.44.0 - Issue #157)

**Smart dependency ordering for intelligent feature sequencing**

### Overview

When processing multiple features with `/implement --batch`, features may have implicit dependencies (e.g., implementing auth before testing it, or modifying a shared file). The dependency analyzer automatically detects these relationships and reorders features to prevent conflicts.

**How It Works**:

1. **Analyze Phase**: Parse feature descriptions for dependency keywords
2. **Detect Phase**: Build dependency graph from keyword analysis
3. **Order Phase**: Use topological sort to find optimal execution order
4. **Validate Phase**: Detect circular dependencies (prevent impossible orderings)
5. **Execute Phase**: Process features in dependency-optimized order

### Dependency Keywords

The analyzer detects these keywords in feature descriptions:

**Dependency Keywords**:
- `requires` - Feature X requires Feature Y to be implemented first
- `depends` - Feature X depends on Feature Y
- `after` - Feature X should run after Feature Y
- `before` - Feature X should run before Feature Y
- `uses` - Feature X uses/modifies code from Feature Y
- `needs` - Feature X needs Feature Y as a prerequisite

**File References**:
- `.py`, `.md`, `.json`, `.yaml`, `.yml`, `.sh`, `.ts`, `.js`, `.tsx`, `.jsx`

### Example: Dependency Detection

Given these features:

```text
Add JWT authentication module
Add tests for JWT validation (requires JWT authentication)
Add password reset endpoint (requires auth, uses email service)
Add email service module
```

The analyzer detects:

- Feature 1 (tests) depends on Feature 0 (auth)
- Feature 2 (password reset) depends on Feature 0 (auth)
- Feature 2 (password reset) depends on Feature 3 (email)

### Optimal Ordering

Using topological sort (Kahn's algorithm), features are reordered:

```
Original Order:        Optimized Order:
1. Add JWT auth        1. Add JWT auth (no deps)
2. Add tests (dep 1)   2. Add email service (no deps)
3. Add password reset  3. Add tests (depends on JWT)
4. Add email service   4. Add password reset (depends on JWT, email)
```

**Benefits**:
- Tests run after implementation (can pass)
- Features with dependencies run after prerequisites (can access needed code)
- Files modified in correct order (avoid conflicts)

### Circular Dependency Detection

If the analyzer detects circular dependencies, it:

1. **Reports the cycle** - Shows which features form the loop
2. **Gracefully degrades** - Falls back to original order
3. **Continues processing** - Batch doesn't fail, just uses original order

**Example Circular**:
```
Feature A depends on Feature B
Feature B depends on Feature A
```

**Result**: Uses original order, logs warning

### ASCII Graph Visualization

When dependency analysis completes, users see:

```
Dependency Analysis Complete:
  Total dependencies detected: 3
  Independent features: 1
  Dependent features: 3

Feature Dependency Graph
========================

Feature 0: Add JWT authentication
  └─> [no dependencies]

Feature 1: Add tests for JWT (requires JWT)
  └─> [depends on] Feature 0: Add JWT authentication

Feature 2: Add password reset (requires auth, uses email)
  └─> [depends on] Feature 0: Add JWT authentication
  └─> [depends on] Feature 3: Add email service

Feature 3: Add email service
  └─> [no dependencies]
```

### State Storage

Dependency information is stored in batch state:

```json
{
  "batch_id": "batch-20251223-features",
  "feature_order": [0, 3, 1, 2],
  "feature_dependencies": {
    "0": [],
    "1": [0],
    "2": [0, 3],
    "3": []
  },
  "analysis_metadata": {
    "stats": {
      "total_dependencies": 3,
      "independent_features": 1,
      "dependent_features": 3,
      "max_depth": 2,
      "total_features": 4
    },
    "analyzed_at": "2025-12-23T10:00:00Z"
  }
}
```

### Performance

**Analysis Time**:
- Typical (50 features): <100ms
- Large (500 features): <500ms
- Max (1000 features): <1000ms (timeout: 5 seconds)

**Memory**: O(V + E) where V = features, E = dependencies
- Linear in feature count, not exponential
- Safe for 100+ feature batches

**Algorithm**: Kahn's algorithm for topological sort
- Time complexity: O(V + E)
- Space complexity: O(V + E)

### Security

**Input Validation**:
- Text sanitization (max 10,000 chars per feature)
- No shell execution
- Path traversal protection (CWE-22)
- Command injection prevention (CWE-78)

**Resource Limits**:
- MAX_FEATURES: 1000
- TIMEOUT_SECONDS: 5
- Memory limits enforced

### Graceful Degradation

If dependency analysis fails:

```python
try:
    deps = analyze_dependencies(features)
    order = topological_sort(features, deps)
except Exception as e:
    print(f"Dependency analysis failed: {e}")
    order = list(range(len(features)))  # Use original order
    print("Continuing with original order...")
```

**Result**: Batch processing continues with original order, no data loss

### Implementation Details

**File**: `plugins/autonomous-dev/lib/feature_dependency_analyzer.py` (509 lines)

**Key Functions**:
- `analyze_dependencies(features)` - Main entry point
- `topological_sort(features, deps)` - Reorder using Kahn's algorithm
- `visualize_graph(features, deps)` - Generate ASCII visualization
- `get_execution_order_stats(features, deps, order)` - Statistics

See `docs/LIBRARIES.md` section 33 for complete API reference.

### Integration with /implement --batch

STEP 1.5 of `/implement --batch` now analyzes dependencies:

```python
# STEP 1.5: Analyze Dependencies and Optimize Order (Issue #157)

from plugins.autonomous_dev.lib.feature_dependency_analyzer import (
    analyze_dependencies,
    topological_sort,
    visualize_graph,
    get_execution_order_stats
)

try:
    deps = analyze_dependencies(features)
    feature_order = topological_sort(features, deps)
    stats = get_execution_order_stats(features, deps, feature_order)
    graph = visualize_graph(features, deps)

    state.feature_dependencies = deps
    state.feature_order = feature_order
    state.analysis_metadata = {"stats": stats}

    print(f"Dependencies detected: {stats['total_dependencies']}")
    print(graph)

except Exception as e:
    print(f"Dependency analysis failed: {e}")
    feature_order = list(range(len(features)))
    state.feature_order = feature_order
    state.feature_dependencies = {i: [] for i in range(len(features))}
```

Then STEP 2+ uses `state.feature_order` for processing order.

### Related Documentation

- `docs/LIBRARIES.md` section 33 - Complete API reference
- `plugins/autonomous-dev/commands/implement --batch.md` - STEP 1.5 implementation
- `plugins/autonomous-dev/lib/batch_state_manager.py` - State storage

### Examples

**Example 1: Simple Linear Dependency**

```text
Implement database schema
Add migrations for schema
Run migrations in test
```

Detected dependencies:
- Feature 1 depends on Feature 0
- Feature 2 depends on Feature 1

Optimized order: [0, 1, 2] (same as original - already correct)

**Example 2: Multiple Independent Trees**

```text
Add JWT authentication
Add tests for JWT
Add password hashing utility
Add hashing tests
Add login endpoint
```

Detected dependencies:
- Feature 1 (JWT tests) depends on Feature 0 (JWT)
- Feature 3 (hashing tests) depends on Feature 2 (hashing)
- Feature 4 (login) depends on Feature 0 (JWT) and Feature 2 (hashing)

Optimized order: [0, 2, 1, 3, 4]

**Example 3: Circular Dependencies (Graceful Degradation)**

```text
Feature A (requires B)
Feature B (requires C)
Feature C (requires A)
```

Detected: Circular dependency detected among [A, B, C]

Result: Uses original order [0, 1, 2], continues processing

---
## Git Automation (NEW in v3.36.0 - Issue #93, Issue #168 - Auto-close issues)

**Per-feature git commits during batch processing** - Each feature in `/implement --batch` workflow now automatically creates a git commit with conventional commit messages, optional push, optional PR creation, and optionally closes related GitHub issues.

### Overview

When processing multiple features with `/implement --batch`, the workflow now includes automatic git operations for each completed feature:

1. **Feature completes**: All tests pass, docs updated, quality checks done
2. **Git automation triggers**: `execute_git_workflow()` called with `in_batch_mode=True`
3. **Commit created**: Conventional commit message generated and applied
4. **State recorded**: Git operation details saved in `batch_state.json` for audit trail
5. **Continue**: Batch processing moves to next feature

### Configuration

Git automation in batch mode uses the same environment variables as `/implement`:

```bash
# .env file (project root)
AUTO_GIT_ENABLED=true      # Master switch (default: true)
AUTO_GIT_PUSH=false        # Disable push during batch (default: true)
AUTO_GIT_PR=false          # Disable PR creation during batch (default: true)
```

### Batch Mode Differences

Batch mode differs from `/implement` in three ways:

1. **Skips first-run consent prompt** - Uses environment variables silently
2. **No interactive prompts** - All decisions made via `.env` configuration
3. **Audit trail in state** - Git operations recorded in `batch_state.json` for debugging

### Git State Tracking

Each git operation is recorded in `batch_state.json` with complete metadata:

```json
{
  "batch_id": "batch-20251206-feature-1",
  "git_operations": {
    "0": {
      "commit": {
        "success": true,
        "timestamp": "2025-12-06T10:00:00Z",
        "sha": "abc123def456",
        "branch": "feature/auth"
      },
      "push": {
        "success": true,
        "timestamp": "2025-12-06T10:00:15Z",
        "branch": "feature/auth",
        "remote": "origin"
      }
    },
    "1": {
      "commit": {
        "success": true,
        "timestamp": "2025-12-06T10:15:00Z",
        "sha": "def456abc123",
        "branch": "feature/jwt"
      }
    }
  }
}
```

### Per-Feature Commit Messages

Each feature gets its own commit with a conventional commit message:

```
feat(auth): add JWT token validation

- Implement token validation middleware
- Add refresh token support
- Update authentication docs

Co-Authored-By: Claude <noreply@anthropic.com>
```

Generated by the `commit-message-generator` agent based on changed files and feature context.

### Issue Auto-Close (NEW in v3.46.0 - Issue #168)

**Automatic GitHub issue closing after successful push** - If a batch feature closes a GitHub issue (extracted from feature description or issue number list), the issue is automatically closed after push completes with a summary comment.

#### How It Works

When a feature is associated with a GitHub issue, the workflow closes it after push:

1. **Issue extraction**: Issue number extracted from feature description
   - Pattern: `#123`, `closes #123`, `fixes #123`, `issue 123`, `GH-123` (case-insensitive)
   - Or: From `issue_numbers` list for `--issues` flag batches
2. **Consent check**: Only if `AUTO_GIT_ENABLED=true` (same as commit/push/PR)
3. **Push first**: Issue closed after push succeeds (ensures feature is saved to remote)
4. **Idempotent**: Already-closed issues skipped (non-blocking)
5. **Summary comment**: Closing comment includes commit hash, branch, files changed

#### Configuration

Auto-close reuses the same consent mechanism as commit/push/PR:

```bash
# Enable automatic issue closing (requires AUTO_GIT_ENABLED=true)
AUTO_GIT_ENABLED=true

# Or disable all git operations including issue close
AUTO_GIT_ENABLED=false
```

#### Examples

**Batch with issue numbers** (`--issues` flag):

```bash
/implement --issues 72 73 74
# Features: [GitHub titles fetched from issues]
# After feature 0 completes: Issue #72 auto-closed
# After feature 1 completes: Issue #73 auto-closed
# After feature 2 completes: Issue #74 auto-closed
```

**Batch with inline issue references**:

```text
# features.txt
Add JWT validation (fixes #72)
Implement password reset (closes #73)
Add email notifications (related to #74)
```

```bash
/implement --batch features.txt
# After feature 0 completes: Issue #72 auto-closed
# After feature 1 completes: Issue #73 auto-closed
# Feature 2: Issue #74 not auto-closed (doesn't match close patterns)
```

#### Close Summary

When an issue is closed, the closing comment includes:

```markdown
## Feature Completed via /implement --batch

### Commit
- abc123def456...

### Branch
- feature/jwt-validation

---

Generated by autonomous-dev /implement --batch workflow
```

#### Circuit Breaker

If issue closing fails 5 times consecutively, the circuit breaker stops further attempts to prevent API abuse:

```
Consecutive failures: 1, 2, 3, 4, 5 → Circuit breaker triggers
Further features: Issue close skipped with warning
```

To reset the circuit breaker:

```python
# Manual reset (for debugging)
python .claude/batch_issue_closer.py reset-breaker
```

#### Error Handling

Issue close failures are **non-blocking** - batch continues processing:

- **Issue not found**: Logged as warning, batch continues
- **Issue already closed**: Idempotent (logged as success), batch continues
- **gh CLI not installed**: Logged as warning, batch continues
- **Network error**: Logged as failure, circuit breaker tracking
- **No issue number**: Logged as skip, batch continues

To debug issue closing:

```bash
# View issue close results for a batch
cat .claude/batch_state.json | jq '.git_operations[] | select(.issue_close.success == true)'

# View failed closures
cat .claude/batch_state.json | jq '.git_operations[] | select(.issue_close.success == false)'
```

### Error Handling in Batch

If a git operation fails during batch processing:

1. **Commit failure**: Feature marked as completed (git operation failed)
2. **Push failure**: Commit succeeds, push marked as failed, batch continues
3. **PR failure**: Commit and push succeed, PR marked as failed, batch continues

All failures are non-blocking - batch continues to next feature with detailed error recorded.

### Audit Trail

View git operation history for a batch:

```bash
# Check what git operations succeeded
cat .claude/batch_state.json | jq '.git_operations'

# Example output
{
  "0": {
    "commit": {"success": true, "sha": "abc123..."},
    "push": {"success": false, "error": "Permission denied"}
  },
  "1": {
    "commit": {"success": true, "sha": "def456..."},
    "push": {"success": true}
  }
}
```

### Implementation API

The git automation for batch mode is exposed via:

```python
from auto_implement_git_integration import execute_git_workflow

# Batch mode usage
result = execute_git_workflow(
    workflow_id='batch-20251206-feature-1',
    request='Add JWT validation',
    in_batch_mode=True  # Skip first-run prompts
)

# Returns git operation results (commit sha, push success, PR URL, etc.)
```

The `in_batch_mode=True` parameter signals that:
- First-run consent prompt should be skipped
- Environment variable consent is still checked
- This is part of a larger batch workflow

---

## Checkpoint/Resume Mechanism (NEW in v3.50.0 - Issue #276)

**Session snapshots for extended batch processing** - autonomous-dev now creates checkpoints after each feature to enable safe resume from any point, with automatic state capture and rollback capability.

### Overview

The RALPH loop checkpoint mechanism provides:
1. **Automatic checkpoints**: After each feature completes
2. **Resume capability**: Continue from any checkpoint
3. **Context preservation**: Capture full session state (files, state, context)
4. **Rollback support**: Restore previous checkpoint on validation failure
5. **Corrupted checkpoint recovery**: Auto-cleanup with warnings

### Context Threshold (Issue #276)

Context threshold increased to support longer batch sessions:

```
Old threshold: 150K tokens
New threshold: 185K tokens (23% increase)
Rationale: Allow 5-7 concurrent features in memory
```

When context approaches 185K tokens, CheckpointManager automatically creates a checkpoint instead of blocking.

### Checkpoint Creation (Automatic)

Checkpoints are created automatically after each feature completes:

```
Feature 1: Add authentication → COMPLETED
  └─> Checkpoint #1 created
      - State snapshot: batch_state.json
      - Context estimate: 85K tokens
      - Timestamp: 2026-01-28T10:15:30Z
      - Files: 23 changed, 145 added

Feature 2: Add authorization → COMPLETED
  └─> Checkpoint #2 created
      - State snapshot: batch_state.json
      - Context estimate: 120K tokens (increased due to accumulated context)
      - Timestamp: 2026-01-28T10:35:45Z
      - Files: 12 changed, 34 added
```

### Resume from Checkpoint

If batch processing is interrupted (context limit hit, crash, manual stop), resume from the last checkpoint:

```bash
# View available checkpoints
ls -la .claude/checkpoints/

# Resume from last checkpoint
/implement --resume batch-20260128-100000
```

Resume restores:
1. Batch state (completed features, current index)
2. Session context (previous work context)
3. Git state (branch, staging area)
4. Progress tracking (feature completions, failures)

### Checkpoint Storage

Checkpoints stored in `.claude/checkpoints/` directory with manifest:

```json
{
  "checkpoint_id": "batch-20260128-100000-checkpoint-001",
  "batch_id": "batch-20260128-100000",
  "feature_index": 1,
  "timestamp": "2026-01-28T10:35:45Z",
  "context_tokens": 120000,
  "files_changed": 12,
  "files_added": 34,
  "compressed": true,
  "size_bytes": 45230,
  "state_hash": "abc123def456",
  "rollback_available": true,
  "expiry": "2026-02-28T10:35:45Z"
}
```

### Rollback Capability

If a feature fails critical validation after resuming from checkpoint:

```
Feature 3: Add database layer
├─ Resume from Checkpoint #2
├─ Implementation starts
├─ Tests fail: 5 failures
├─ Quality gate: FAILED
├─ Manual rollback requested
└─> Restore Checkpoint #2
    - Restore batch state
    - Revert file changes
    - Continue from previous state
```

Rollback command:

```bash
# Rollback to specific checkpoint
/implement --rollback batch-20260128-100000 checkpoint-001

# Or rollback to previous checkpoint
/implement --rollback batch-20260128-100000 --previous
```

### Troubleshooting Corrupted Checkpoints

**Symptom**: Resume fails with "corrupted checkpoint" error

```
Error: Checkpoint state.json is corrupted (invalid JSON)
├─ Checkpoint ID: batch-20260128-100000-checkpoint-001
├─ Size: 45230 bytes
└─ Attempting recovery...
```

**Auto-recovery process**:

1. **Detection**: Validate checkpoint JSON format
2. **Parsing attempt**: Try to parse despite corruption
3. **Fallback**: Use previous valid checkpoint
4. **Cleanup**: Move corrupted checkpoint to `checkpoints/corrupted/` with timestamp
5. **Audit log**: Record corruption details in `logs/checkpoint_errors.jsonl`

**Manual recovery**:

```bash
# List all checkpoints (including corrupted)
python .claude/checkpoint_manager.py list

# View corruption details
python .claude/checkpoint_manager.py inspect batch-20260128-100000-checkpoint-001

# Restore from previous checkpoint
/implement --resume batch-20260128-100000 --previous

# Clean up corrupted checkpoints
python .claude/checkpoint_manager.py cleanup --corrupted
```

**Prevention**:

- Checkpoint validation happens automatically during creation
- Atomic writes prevent partial saves
- Compression with integrity checks (gzip CRC-32)
- Regular backup of checkpoints to `checkpoints/backups/`

### Checkpoint Metadata

Each checkpoint includes metadata for debugging:

```json
{
  "metadata": {
    "batch_id": "batch-20260128-100000",
    "checkpoint_number": 2,
    "created_by": "batch_processing",
    "context_tokens": 120000,
    "session_id": "session-abc123",
    "python_version": "3.11.0",
    "os": "darwin",
    "autonomous_dev_version": "3.50.0"
  },
  "content_hash": "abc123def456",
  "compression_ratio": 0.65,
  "created_at": "2026-01-28T10:35:45Z",
  "expires_at": "2026-02-28T10:35:45Z"
}
```

### Performance Impact

- **Checkpoint creation**: <500ms per feature (minimal overhead)
- **Compression**: ~35% size reduction (65% of original)
- **Storage**: ~50KB per checkpoint (1000 checkpoints = 50MB)
- **Memory**: Zero additional overhead (loaded on-demand)

### Examples

#### Example 1: Resume from Last Checkpoint

```bash
# Batch was interrupted after feature 3
/implement --resume batch-20260128-100000

# Resume loads Checkpoint #3
├─ Batch state restored: feature_index = 3
├─ Files restored from snapshot
├─ Context summarized (120K tokens → 85K tokens)
└─ Continue with Feature 4
```

#### Example 2: Rollback and Retry

```bash
# Feature 4 fails validation
/implement --rollback batch-20260128-100000 --previous

# Rollback restores Checkpoint #3
├─ Batch state: feature_index = 3
├─ Files: Reverted to Checkpoint #3 snapshot
├─ Git state: Revert uncommitted changes
└─ Retry: /implement Feature 4 with different approach
```

#### Example 3: Corrupted Checkpoint Recovery

```bash
# Resume fails
/implement --resume batch-20260128-100000
# Error: Checkpoint #2 corrupted

# Auto-recovery kicks in
├─ Checkpoint #2 moved to checkpoints/corrupted/
├─ Checkpoint #1 loaded (previous valid)
└─ Continue from Checkpoint #1

# View error details
cat logs/checkpoint_errors.jsonl | tail -20
```

### Configuration

Checkpoint behavior controlled via environment variables:

```bash
# Enable/disable checkpoints (default: enabled)
CHECKPOINT_ENABLED=true

# Checkpoint storage directory (default: .claude/checkpoints/)
CHECKPOINT_DIR=.claude/checkpoints/

# Context threshold for automatic checkpoint (default: 185000 tokens)
CONTEXT_THRESHOLD=185000

# Checkpoint expiry (default: 30 days)
CHECKPOINT_EXPIRY_DAYS=30

# Compression (default: enabled)
CHECKPOINT_COMPRESS=true

# Rollback retention (number of previous checkpoints to keep)
ROLLBACK_DEPTH=5
```

### Implementation Files

- **Checkpoint Manager**: `plugins/autonomous-dev/lib/checkpoint_manager.py` (Issue #276)
- **RALPH Loop**: Updated `plugins/autonomous-dev/lib/ralph_loop_enforcer.py` with checkpoint hooks
- **Batch State Manager**: Enhanced with checkpoint references
- **State files**: `.claude/checkpoints/` directory with manifest
- **Error Log**: `logs/checkpoint_errors.jsonl` (JSONL format)
- **Metadata**: `.claude/checkpoint_manifest.json`

### See Also

- [docs/LIBRARIES.md](LIBRARIES.md#checkpoint-manager) - CheckpointManager API reference
- [docs/SESSION-STATE-PERSISTENCE.md](SESSION-STATE-PERSISTENCE.md) - Session state details

---

## Context Management (Compaction-Resilient)

The batch system uses a compaction-resilient design that survives Claude Code's automatic context summarization, enabling truly unattended operation for large batches.

**How It Works**:

1. **Externalized state**: All progress tracked in `batch_state.json`, not conversation memory
2. **Self-contained features**: Each `/implement` bootstraps fresh from external sources
3. **Auto-compaction safe**: When Claude Code summarizes context, processing continues seamlessly
4. **Git preserves work**: Every completed feature is committed before moving on
5. **Resume for crashes only**: `--resume` only needed if Claude Code actually exits/crashes

**Why This Works**:

Each feature implementation reads from external state:
- **Requirements**: Fetched from GitHub issue (not memory)
- **Codebase state**: Read from filesystem (not memory)
- **Progress**: Tracked in batch_state.json (not memory)
- **Completed work**: Committed to git (permanent)

**Critical: State Must Be Updated** (v3.45.0 fix):

After EVERY feature completes (success or failure), the batch state MUST be updated:

```python
from plugins.autonomous_dev.lib.batch_state_manager import update_batch_progress
from plugins.autonomous_dev.lib.path_utils import get_batch_state_file

update_batch_progress(
    state_file=get_batch_state_file(),
    feature_index=feature_index,
    status="completed",  # or "failed"
)
```

Without this update, context compaction causes the batch to "forget" which features were completed, resulting in prompts like "Would you like me to continue?" instead of automatic continuation.

**Benefits**:
- **Fully unattended**: No manual `/clear` cycles needed
- **Unlimited batch sizes**: 50+ features run continuously
- **Auto-compaction safe**: Claude Code's summarization doesn't break workflow
- **Zero data loss**: State externalized, not dependent on conversation context
- **Crash recovery**: `--resume` available for actual crashes

### Crash Recovery

Resume from last completed feature:

```bash
/implement --resume batch-20251116-123456
```

**Recovery Process**:
1. Loads state from `.claude/batch_state.json`
2. Validates status ("in_progress" for normal resume)
3. Skips completed features
4. Continues from current_index

---

## Automatic Failure Recovery (NEW in v3.33.0 - Issue #89)

Automatic retry with intelligent failure classification for transient errors and safety limits.

### Overview

When a feature fails during `/implement --batch`, the system automatically classifies the error and retries transient failures while skipping permanent errors.

**Key Features**:
- **Transient Retry**: Network errors, timeouts, API rate limits (automatically retried)
- **Permanent Skip**: Syntax errors, import errors, type errors (not retried)
- **Safety Limits**: Max 3 retries per feature, circuit breaker after 5 consecutive failures
- **User Consent**: First-run prompt (opt-in), can be overridden via `.env`
- **Audit Logging**: All retry attempts logged for debugging

### Transient vs Permanent Errors

**Transient (Retriable)**:
- Network errors (ConnectionError, NetworkError)
- Timeout errors (TimeoutError)
- API rate limits (RateLimitError, 429, 503)
- Temporary service failures (502, 504, TemporaryFailure)

**Permanent (Not Retriable)**:
- Syntax errors (SyntaxError, IndentationError)
- Import errors (ImportError, ModuleNotFoundError)
- Type errors (TypeError, AttributeError, NameError)
- Value errors (ValueError, KeyError, IndexError)
- Logic errors (AssertionError)

### Retry Decision Logic

When a feature fails, the system checks in order:

1. **Global Retry Limit**: Max 50 total retries across all features (hard limit)
2. **Circuit Breaker**: Blocks retries after 5 consecutive failures (safety mechanism)
3. **Failure Type**: Permanent errors never retried
4. **Per-Feature Limit**: Max 3 retries per individual feature

If all checks pass, the feature is automatically retried.

### First-Run Consent

On first use, you'll see:

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  🔄 Automatic Retry for /implement --batch (NEW)              ║
║                                                              ║
║  Automatic retry enabled for transient failures:            ║
║    ✓ Network errors                                         ║
║    ✓ API rate limits                                        ║
║    ✓ Temporary service failures                             ║
║                                                              ║
║  Max 3 retries per feature (prevents infinite loops)        ║
║  Circuit breaker after 5 consecutive failures (safety)      ║
║                                                              ║
║  HOW TO DISABLE:                                            ║
║    Add to .env: BATCH_RETRY_ENABLED=false                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Your response is saved to `~/.autonomous-dev/user_state.json` and reused for future runs.

### Environment Variable Override

To control retry behavior via environment variable:

```bash
# Enable automatic retry
export BATCH_RETRY_ENABLED=true

# Disable automatic retry
export BATCH_RETRY_ENABLED=false

# Or in .env file
echo "BATCH_RETRY_ENABLED=true" >> .env
```

### Monitoring Retries

Retry attempts are logged to `.claude/audit/` directory with audit trails:

```bash
# View retry audit log for specific batch
cat .claude/audit/batch-20251118-123456_retry_audit.jsonl
```

Each audit entry includes:
- Timestamp
- Feature index
- Retry attempt number
- Error message (sanitized)
- Global retry count
- Decision reason

### Circuit Breaker

When a batch experiences 5 consecutive failures:

1. **Circuit Breaker Opens**: Retries blocked to prevent resource exhaustion
2. **Continue Processing**: Failed features are marked as failed (not skipped)
3. **Manual Reset**: Use command to reset breaker after investigation:
   ```bash
   python .claude/batch_retry_manager.py reset-breaker batch-20251118-123456
   ```

### State Persistence

Retry state persists in `.claude/batch_*_retry_state.json`:

```json
{
  "batch_id": "batch-20251118-123456",
  "retry_counts": {
    "0": 2,  // Feature 0 retried 2 times
    "5": 1   // Feature 5 retried 1 time
  },
  "global_retry_count": 5,
  "consecutive_failures": 0,
  "circuit_breaker_open": false,
  "created_at": "2025-11-18T10:00:00Z",
  "updated_at": "2025-11-18T10:15:00Z"
}
```

This allows resuming with retry state intact across crashes.

### Security

Automatic retry implements defensive security:

- **CWE-117**: Log injection prevention via error message sanitization
- **CWE-22**: Path validation for state files
- **CWE-59**: Symlink rejection for user state file
- **CWE-400**: Resource exhaustion prevention via circuit breaker
- **CWE-732**: File permissions secured (0o600 for user state file)

---

## Quality Gates (NEW in v1.0.0 - Issue #254)

**Quality Persistence: System enforces real quality standards, never fakes success**

### Overview

Batch processing enforces strict quality gates to prevent features from being marked as complete when they don't actually pass quality requirements. System is honest about what succeeded and what failed.

Quality Gate Rules:
- **100% test pass requirement** - ALL tests must pass (not 80%, not "most")
- **Coverage threshold** - 80%+ code coverage required
- **Retry limits** - Max 3 attempts per feature
- **Transparent reporting** - Shows actual completion status

### Completion Gate Enforcement

A feature is ONLY marked as completed when:

1. **All tests pass** - Exit code 0 from test runner, zero test failures
2. **Coverage threshold met** - 80%+ code coverage
3. **No more retries** - Within max 3 retry attempts

If any gate fails, feature is retried (if attempts remain) or marked failed.

### What Happens on Quality Gate Failure

**During batch processing**:

```
Feature 5: Add authentication module
├─ Test run: 3/10 tests failed
├─ Quality gate: FAILED (coverage too low: 60%)
├─ Retry: Attempt 1 of 3
└─ Next: Focus on fixing failing tests
```

**After exhausting retries**:

```
Feature 5: Add authentication module
├─ Retry 1: Failed (3 test failures)
├─ Retry 2: Failed (2 test failures)
├─ Retry 3: Failed (2 test failures)
├─ Max retries exhausted
└─ Status: FAILED (not COMPLETED)
```

### Issue Closure Behavior (Issue #254)

**Only completed features close their issues**:

| Status | GitHub Issue | Label |
|--------|-------------|-------|
| Completed (passed quality gates) | Auto-close | none |
| Failed (exhausted retries) | Stays OPEN | 'blocked' |
| Skipped (not implemented) | Stays OPEN | 'blocked' |

**Example**:

```
/implement --batch features.txt
├─ Feature 1: Add logging - COMPLETED (all tests pass) → Issue #72 CLOSED
├─ Feature 2: Add auth - FAILED (tests still fail) → Issue #73 OPEN + 'blocked' label
├─ Feature 3: Add cache - SKIPPED → Issue #74 OPEN + 'blocked' label
└─ Batch Summary:
   Completed: 1/3
   Failed: 1/3
   Skipped: 1/3
```

### Retry Strategy Escalation

When a feature fails, system doesn't just retry the same way:

**Attempt 1 (first failure)**
- Strategy: Basic retry
- Focus: Same approach as initial attempt
- Message: "Try again with same approach"

**Attempt 2 (second failure)**
- Strategy: Fix tests first
- Focus: Make all tests pass (may sacrifice some features)
- Message: "Focus on making tests pass"

**Attempt 3 (third failure)**
- Strategy: Different implementation
- Focus: Try alternative approach (different design)
- Message: "Try alternative approach"

**Beyond 3**: Stop retrying
- Mark feature as FAILED
- Add 'blocked' label to GitHub issue
- Continue with next feature

### Honest Batch Summary

At completion, batch shows actual results (never inflated):

```
Batch Summary: batch-20260119-143022
=====================================

Completed: 7/10 (70%)
  - Add logging module (tests: 12/12, coverage: 85%)
  - Add caching layer (tests: 8/8, coverage: 92%)
  - Add monitoring (tests: 15/15, coverage: 88%)
  - Add rate limiting (tests: 6/6, coverage: 80%)
  - Add request validation (tests: 10/10, coverage: 86%)
  - Add response compression (tests: 5/5, coverage: 81%)
  - Add circuit breaker (tests: 20/20, coverage: 89%)

Failed: 2/10 (20%)
  - Add authentication (exhausted 3 retries, 2 tests still fail)
  - Add session management (exhausted 3 retries, 4 tests still fail)

Skipped: 1/10 (10%)
  - Add two-factor auth (complex, deferred for later batch)

Average Coverage: 85.6%

Next Steps:
  1. Investigate failed features (authentication, session management)
  2. Consider simpler scope for next batch
  3. Resume batch to retry failed features: /implement --resume batch-20260119-143022
```

### Configuration

No configuration needed - quality gates are always enforced.

**Optional: Override retry count** (advanced)

```bash
# Retry more than 3 times (not recommended)
export MAX_RETRY_ATTEMPTS=5
/implement --batch features.txt
```

### Examples

#### Example 1: Feature passes on first try

```python
# Test results
test_results = {
    "total": 10,
    "passed": 10,
    "failed": 0,
    "coverage": 85.0
}

# Quality gate check
result = enforce_completion_gate(feature_index=0, test_results=test_results)
# result.passed = True
# Feature marked as COMPLETED
```

#### Example 2: Feature fails coverage threshold

```python
# Test results
test_results = {
    "total": 10,
    "passed": 10,
    "failed": 0,
    "coverage": 75.0  # Below 80% threshold
}

# Quality gate check
result = enforce_completion_gate(feature_index=1, test_results=test_results)
# result.passed = False
# result.reason = "Coverage below threshold: 75.0% < 80%"
# Feature retried (if attempts remain)
```

#### Example 3: Feature exhausts all retries

```
Feature: Add authentication
├─ Attempt 1: 3 test failures → RETRY with basic approach
├─ Attempt 2: 2 test failures → RETRY with fix-tests-first approach
├─ Attempt 3: 2 test failures → STOP (max attempts reached)
├─ Status: FAILED (not COMPLETED)
└─ Issue: #42 stays OPEN with 'blocked' label
```

### Security

- **No Faking**: System never marks features complete when quality gates failed
- **Audit Trail**: All decisions logged with timestamps and reasons
- **Transparent**: Users see actual numbers (not inflated completion rates)
- **Rollback Prevention**: Failed features tracked for investigation

### See Also

- [docs/LIBRARIES.md](LIBRARIES.md#24-quality_persistence_enforcerpy) - quality_persistence_enforcer.py API reference
- [docs/LIBRARIES.md](LIBRARIES.md#22-batch_retry_managerpy) - batch_retry_manager.py retry logic
- [docs/LIBRARIES.md](LIBRARIES.md#14-batch_issue_closerpy) - batch_issue_closer.py issue handling

---

## State Tracking

### Tracked Metrics

- **Completed features**: Successfully processed features
- **Failed features**: Features that encountered errors
- **Processing history**: Timestamps and token estimates for debugging
- **Current index**: Position in feature list
- **Context tokens**: Estimated token count (informational only)
- **Issue numbers**: Original GitHub issue numbers (for --issues flag)
- **Source type**: Input method (file or github_issues)

### Progress Maintenance

- State persists across crashes
- Automatic resume on restart
- No duplicate processing
- Full audit trail of completed work

---

## Use Cases

1. **Sprint Backlogs**: Process 10-50 features from sprint planning
2. **Overnight Processing**: Queue large feature sets for batch processing
3. **Technical Debt**: Clean up 50+ small improvements sequentially
4. **Large Migrations**: Handle 50+ feature migrations with state-based tracking

---

## Performance

- **Per Feature**: ~20-30 minutes (same as `/implement`)
- **Context Management**: Automatic (Claude Code manages 200K token budget)
- **State Save/Load**: <10 seconds per feature (persistent tracking)
- **Scalability**: Tested with 50+ features without manual intervention
- **Recovery**: Resume from exact failure point

---

## Worktree Support (NEW in v3.45.0 - Issue #226)

**Per-worktree batch state isolation for concurrent development**

### Overview

When developing multiple features in parallel using git worktrees, batch state is now automatically isolated per worktree. This enables:
- Running independent batch operations in different worktrees without interference
- Concurrent CI jobs processing different feature sets in parallel
- Worktree deletion automatically cleans up associated batch state

### How It Works

**Detection**: `get_batch_state_file()` automatically detects if the current directory is a git worktree.

**Isolation Behavior**:
- **Worktrees**: Batch state stored in `WORKTREE_DIR/.claude/batch_state.json` (isolated)
- **Main Repository**: Batch state stored in `REPO_ROOT/.claude/batch_state.json` (backward compatible)

**Automatic CWD Change**: When `create_batch_worktree()` successfully creates a worktree, it automatically changes the current working directory to the worktree. This ensures all subsequent operations (file writes, edits, shell commands) execute within the worktree context without manual directory management. The function returns `original_cwd` to allow restoration if needed.

### Batch State Paths

```bash
# In main repository
.claude/batch_state.json

# In worktree
worktree-dir/.claude/batch_state.json
```

Each worktree maintains its own independent batch state, preventing conflicts when multiple developers or CI jobs process features concurrently.

### Concurrent Workflow Example

```bash
# Main repo - start batch processing features 1-5
cd /path/to/repo
/implement --batch features-main.txt

# Concurrent: Developer creates worktree for independent features
git worktree add -b feature-branch worktree-feature
cd worktree-feature
/implement --batch features-worktree.txt
# Uses isolated: worktree-feature/.claude/batch_state.json

# Both batches run independently without interference
```

### Performance

- **Detection**: <1ms (cached git status check)
- **State Isolation**: Zero overhead (uses existing `.claude/batch_state.json` mechanism)
- **Concurrent Batches**: Tested with 3+ parallel worktrees

### Backward Compatibility

Main repository behavior is unchanged:
- Single batch state at project root (`.claude/batch_state.json`)
- Existing batch scripts continue working without modification
- Detection falls back to main repo behavior if worktree detection fails

### Cleanup

When deleting a worktree, its batch state is automatically removed:

```bash
# Delete worktree and its isolated batch state
git worktree remove --force worktree-dir
# worktree-dir/.claude/batch_state.json is deleted with worktree
```

### Security

Worktree path detection includes:
- Graceful fallback to main repo behavior on detection errors
- Path validation to prevent symlink attacks
- Safe `.claude/` directory creation (0o755 permissions)
- CWE-22 (path traversal), CWE-59 (symlinks) protection

### Implementation Details

**File**: `plugins/autonomous-dev/lib/path_utils.py` (Lines 228-294)

**Key Functions**:
- `is_worktree()` - Lazy-loaded wrapper for git_operations.is_worktree()
- `get_batch_state_file()` - Returns isolated path based on worktree detection
- `reset_worktree_cache()` - Clears cached detection (for testing)

**Exception Handling**:
- ImportError (git_operations not available): Falls back to main repo
- Detection exceptions: Falls back to main repo
- Symmetric with existing error handling patterns

### Testing

**Unit Tests** (15 tests - Issue #226):
- Backward compatibility with main repo
- Worktree path isolation
- Edge cases (detection failures, fallback behavior)
- Security validations
- Performance characteristics

**Integration Tests** (9 tests - Issue #226):
- Real git worktrees (not mocks)
- Concurrent batch operations
- State persistence and JSON format
- Worktree cleanup behavior

See `/tests/unit/lib/test_path_utils_worktree.py` and `/tests/integration/test_worktree_batch_isolation.py`.

---

## Migration Guide

**Issue #203**: The `/implement --batch` command has been consolidated into `/implement`.

| Old Command | New Command |
|-------------|-------------|
| `/implement --batch file.txt` | `/implement --batch file.txt` |
| `/implement --batch --issues 1 2 3` | `/implement --issues 1 2 3` |
| `/implement --batch --resume id` | `/implement --resume id` |

The old commands still work via deprecation shims but display a notice:

```
⚠️  DEPRECATED: /implement --batch is deprecated and will be removed in v4.0.0

Migration:
  Old: /implement --batch features.txt
  New: /implement --batch features.txt
```

**New Features in v3.47.0**:
- **Auto-worktree isolation**: Batch modes automatically create isolated worktrees
- **Unified command**: Single `/implement` command with mode flags
- **Consistent flags**: `--batch`, `--issues`, `--resume`, `--quick`

---

## Implementation Files

- **Command**: `plugins/autonomous-dev/commands/implement.md` (unified command - v3.47.0)
- **Orchestrator**: `plugins/autonomous-dev/lib/batch_orchestrator.py` (flag parsing, mode routing - v3.47.0)
- **State Manager**: `plugins/autonomous-dev/lib/batch_state_manager.py` (enhanced v3.33.0 with retry tracking, v3.36.0 with git operations, v3.45.0 with worktree isolation)
- **GitHub Fetcher**: `plugins/autonomous-dev/lib/github_issue_fetcher.py` (v3.24.0)
- **Failure Classifier**: `plugins/autonomous-dev/lib/failure_classifier.py` (v3.33.0 - Issue #89)
- **Retry Manager**: `plugins/autonomous-dev/lib/batch_retry_manager.py` (v3.33.0 - Issue #89)
- **Consent Handler**: `plugins/autonomous-dev/lib/batch_retry_consent.py` (v3.33.0 - Issue #89)
- **Git Integration**: `plugins/autonomous-dev/lib/auto_implement_git_integration.py` (v3.36.0 with `execute_git_workflow()` batch mode support - Issue #93)
- **Path Utilities**: `plugins/autonomous-dev/lib/path_utils.py` (enhanced v3.45.0 with worktree batch state isolation - Issue #226)
- **State File**: `.claude/batch_state.json` (created automatically, includes git_operations field v3.36.0 - Issue #93, isolated per worktree v3.45.0 - Issue #226)
- **Retry State File**: `.claude/batch_*_retry_state.json` (created per batch for retry tracking)
- **Issue Closer**: `plugins/autonomous-dev/lib/batch_issue_closer.py` (v3.46.0 - Issue #168, auto-closes issues after push with circuit breaker)
- **Deprecated Shim**: `plugins/autonomous-dev/commands/implement --batch.md` (redirects to /implement - v3.47.0)

---

## See Also

- [commands/implement.md](/plugins/autonomous-dev/commands/implement.md) - Unified implementation command (v3.47.0)
- [lib/batch_orchestrator.py](/plugins/autonomous-dev/lib/batch_orchestrator.py) - Flag parsing and mode routing
- [lib/batch_state_manager.py](/plugins/autonomous-dev/lib/batch_state_manager.py) - State management implementation
- [lib/github_issue_fetcher.py](/plugins/autonomous-dev/lib/github_issue_fetcher.py) - GitHub integration
- [lib/feature_dependency_analyzer.py](/plugins/autonomous-dev/lib/feature_dependency_analyzer.py) - Dependency ordering (Issue #157)
- [lib/failure_classifier.py](/plugins/autonomous-dev/lib/failure_classifier.py) - Error classification logic (Issue #89)
- [lib/batch_retry_manager.py](/plugins/autonomous-dev/lib/batch_retry_manager.py) - Retry orchestration (Issue #89)
- [lib/batch_retry_consent.py](/plugins/autonomous-dev/lib/batch_retry_consent.py) - User consent handling (Issue #89)
- [docs/LIBRARIES.md](/docs/LIBRARIES.md) - Complete library API reference
