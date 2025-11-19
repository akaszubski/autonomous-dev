# Batch Feature Processing

**Last Updated**: 2025-11-19
**Version**: Enhanced in v3.24.0, Simplified in v3.32.0 (Issue #88), Automatic retry added v3.33.0 (Issue #89)
**Command**: `/batch-implement`

This document describes the batch feature processing system for sequential multi-feature development with intelligent state management and automatic context management.

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

## Automatic Compression

Claude Code automatically manages context with its 200K token budget. The system compresses and prunes context in the background when needed - fully automatic with no user intervention required.

**How It Works**:

1. **Claude Code tracks context internally** (200K token budget)
2. **Automatic compression** when approaching limits (transparent to user)
3. **Background pruning** removes less-relevant context
4. **Continuous processing** without pauses or interruptions

**Benefits**:
- Supports 50+ features without interruption
- No user intervention required
- Simplified workflow (no pause/resume complexity)
- Trusts platform capabilities (Claude Code's built-in context management)

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
- **State Manager**: `plugins/autonomous-dev/lib/batch_state_manager.py` (enhanced v3.33.0 with retry tracking)
- **GitHub Fetcher**: `plugins/autonomous-dev/lib/github_issue_fetcher.py` (v3.24.0)
- **Failure Classifier**: `plugins/autonomous-dev/lib/failure_classifier.py` (v3.33.0 - Issue #89)
- **Retry Manager**: `plugins/autonomous-dev/lib/batch_retry_manager.py` (v3.33.0 - Issue #89)
- **Consent Handler**: `plugins/autonomous-dev/lib/batch_retry_consent.py` (v3.33.0 - Issue #89)
- **State File**: `.claude/batch_state.json` (created automatically)
- **Retry State File**: `.claude/batch_*_retry_state.json` (created per batch for retry tracking)

---

## See Also

- [commands/auto-implement.md](/plugins/autonomous-dev/commands/auto-implement.md) - Individual feature workflow
- [lib/batch_state_manager.py](/plugins/autonomous-dev/lib/batch_state_manager.py) - State management implementation
- [lib/github_issue_fetcher.py](/plugins/autonomous-dev/lib/github_issue_fetcher.py) - GitHub integration
- [lib/failure_classifier.py](/plugins/autonomous-dev/lib/failure_classifier.py) - Error classification logic (Issue #89)
- [lib/batch_retry_manager.py](/plugins/autonomous-dev/lib/batch_retry_manager.py) - Retry orchestration (Issue #89)
- [lib/batch_retry_consent.py](/plugins/autonomous-dev/lib/batch_retry_consent.py) - User consent handling (Issue #89)
- [commands/batch-implement.md](/plugins/autonomous-dev/commands/batch-implement.md) - Automatic context management details
- [docs/LIBRARIES.md](/docs/LIBRARIES.md) - Complete library API reference
