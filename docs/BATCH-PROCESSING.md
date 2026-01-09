# Batch Feature Processing

**Last Updated**: 2026-01-09
**Version**: Enhanced in v3.24.0, Simplified in v3.32.0 (Issue #88), Automatic retry added v3.33.0 (Issue #89), Consent bypass added v3.35.0 (Issue #96), Git automation added v3.36.0 (Issue #93), Dependency analysis added v3.44.0 (Issue #157), State persistence fix v3.45.0, Deprecated context clearing functions removed v3.46.0 (Issue #218)
**Command**: `/batch-implement`

This document describes the batch feature processing system for sequential multi-feature development with intelligent state management, automatic context management, and per-feature git automation.

---

## Overview

Process multiple features sequentially with intelligent state management and automatic context management. Supports 50+ features without manual intervention.

**Workflow**: Parse input → Create batch state → For each: `/auto-implement` → Continue (Claude Code handles context automatically)

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
/batch-implement <features-file>
```

### 2. GitHub Issues Input (NEW in v3.24.0)

Fetch feature titles directly from GitHub issues:

```bash
/batch-implement --issues 72 73 74
# Fetches: "Issue #72: [title]", "Issue #73: [title]", "Issue #74: [title]"
```

**Requirements**:
- gh CLI v2.0+ installed
- One-time authentication: `gh auth login`

---

## Prerequisites for Unattended Batch Processing (NEW in v3.35.0 - Issue #96)

For fully unattended batch processing (4-5 features, ~2 hours), configure git automation to bypass interactive prompts.

**Why This Matters**: By default, `/auto-implement` prompts for consent on first run. During batch processing, this prompt blocks the entire batch from continuing, defeating the purpose of unattended processing.

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
/batch-implement features.txt
# No prompts - runs fully unattended
```

**Option 2: Environment Variables (Shell)**

Set environment variables before running batch:

```bash
export AUTO_GIT_ENABLED=true
export AUTO_GIT_PUSH=true
export AUTO_GIT_PR=true

/batch-implement features.txt
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
/batch-implement features.txt
# Features committed locally, not pushed
# Manually push when batch completes: git push
```

### How It Works

**Issue #96 (v3.35.0)**: `/auto-implement` STEP 5 now checks `AUTO_GIT_ENABLED` environment variable BEFORE showing interactive consent prompt.

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

When processing multiple features with `/batch-implement`, features may have implicit dependencies (e.g., implementing auth before testing it, or modifying a shared file). The dependency analyzer automatically detects these relationships and reorders features to prevent conflicts.

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

### Integration with /batch-implement

STEP 1.5 of `/batch-implement` now analyzes dependencies:

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
- `plugins/autonomous-dev/commands/batch-implement.md` - STEP 1.5 implementation
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

**Per-feature git commits during batch processing** - Each feature in `/batch-implement` workflow now automatically creates a git commit with conventional commit messages, optional push, optional PR creation, and optionally closes related GitHub issues.

### Overview

When processing multiple features with `/batch-implement`, the workflow now includes automatic git operations for each completed feature:

1. **Feature completes**: All tests pass, docs updated, quality checks done
2. **Git automation triggers**: `execute_git_workflow()` called with `in_batch_mode=True`
3. **Commit created**: Conventional commit message generated and applied
4. **State recorded**: Git operation details saved in `batch_state.json` for audit trail
5. **Continue**: Batch processing moves to next feature

### Configuration

Git automation in batch mode uses the same environment variables as `/auto-implement`:

```bash
# .env file (project root)
AUTO_GIT_ENABLED=true      # Master switch (default: true)
AUTO_GIT_PUSH=false        # Disable push during batch (default: true)
AUTO_GIT_PR=false          # Disable PR creation during batch (default: true)
```

### Batch Mode Differences

Batch mode differs from `/auto-implement` in three ways:

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
/batch-implement --issues 72 73 74
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
/batch-implement features.txt
# After feature 0 completes: Issue #72 auto-closed
# After feature 1 completes: Issue #73 auto-closed
# Feature 2: Issue #74 not auto-closed (doesn't match close patterns)
```

#### Close Summary

When an issue is closed, the closing comment includes:

```markdown
## Feature Completed via /batch-implement

### Commit
- abc123def456...

### Branch
- feature/jwt-validation

---

Generated by autonomous-dev /batch-implement workflow
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

## Context Management (Compaction-Resilient)

The batch system uses a compaction-resilient design that survives Claude Code's automatic context summarization, enabling truly unattended operation for large batches.

**How It Works**:

1. **Externalized state**: All progress tracked in `batch_state.json`, not conversation memory
2. **Self-contained features**: Each `/auto-implement` bootstraps fresh from external sources
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
/batch-implement --resume batch-20251116-123456
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

When a feature fails during `/batch-implement`, the system automatically classifies the error and retries transient failures while skipping permanent errors.

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
║  🔄 Automatic Retry for /batch-implement (NEW)              ║
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

- **Per Feature**: ~20-30 minutes (same as `/auto-implement`)
- **Context Management**: Automatic (Claude Code manages 200K token budget)
- **State Save/Load**: <10 seconds per feature (persistent tracking)
- **Scalability**: Tested with 50+ features without manual intervention
- **Recovery**: Resume from exact failure point

---

## Implementation Files

- **Command**: `plugins/autonomous-dev/commands/batch-implement.md`
- **State Manager**: `plugins/autonomous-dev/lib/batch_state_manager.py` (enhanced v3.33.0 with retry tracking, v3.36.0 with git operations)
- **GitHub Fetcher**: `plugins/autonomous-dev/lib/github_issue_fetcher.py` (v3.24.0)
- **Failure Classifier**: `plugins/autonomous-dev/lib/failure_classifier.py` (v3.33.0 - Issue #89)
- **Retry Manager**: `plugins/autonomous-dev/lib/batch_retry_manager.py` (v3.33.0 - Issue #89)
- **Consent Handler**: `plugins/autonomous-dev/lib/batch_retry_consent.py` (v3.33.0 - Issue #89)
- **Git Integration**: `plugins/autonomous-dev/lib/auto_implement_git_integration.py` (v3.36.0 with `execute_git_workflow()` batch mode support - Issue #93)
- **State File**: `.claude/batch_state.json` (created automatically, includes git_operations field v3.36.0 - Issue #93)
- **Retry State File**: `.claude/batch_*_retry_state.json` (created per batch for retry tracking)
- **Issue Closer**: `plugins/autonomous-dev/lib/batch_issue_closer.py` (v3.46.0 - Issue #168, auto-closes issues after push with circuit breaker)

---

## See Also

- [commands/auto-implement.md](/plugins/autonomous-dev/commands/auto-implement.md) - Individual feature workflow
- [lib/batch_state_manager.py](/plugins/autonomous-dev/lib/batch_state_manager.py) - State management implementation
- [lib/github_issue_fetcher.py](/plugins/autonomous-dev/lib/github_issue_fetcher.py) - GitHub integration
- [lib/feature_dependency_analyzer.py](/plugins/autonomous-dev/lib/feature_dependency_analyzer.py) - Dependency ordering (Issue #157)
- [lib/failure_classifier.py](/plugins/autonomous-dev/lib/failure_classifier.py) - Error classification logic (Issue #89)
- [lib/batch_retry_manager.py](/plugins/autonomous-dev/lib/batch_retry_manager.py) - Retry orchestration (Issue #89)
- [lib/batch_retry_consent.py](/plugins/autonomous-dev/lib/batch_retry_consent.py) - User consent handling (Issue #89)
- [commands/batch-implement.md](/plugins/autonomous-dev/commands/batch-implement.md) - Automatic context management details
- [docs/LIBRARIES.md](/docs/LIBRARIES.md) - Complete library API reference
