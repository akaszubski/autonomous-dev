# Batch Feature Processing

**Last Updated**: 2025-11-17
**Version**: Enhanced in v3.24.0, Context Clearing Workflow added in v3.31.0 (Issue #88)
**Command**: `/batch-implement`

This document describes the batch feature processing system for sequential multi-feature development with intelligent state management and automatic context clearing.

---

## Overview

Process multiple features sequentially with intelligent state management and automatic context clearing. Supports 50+ features without context bloat.

**Workflow**: Parse input → Create batch state → For each: `/auto-implement` + pause at 150K tokens → User manual /clear + auto-resume → Continue

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

## State Management (Enhanced in v3.24.0, Context Clearing in v3.31.0)

### Persistent State

State tracked in `.claude/batch_state.json`:

```json
{
  "batch_id": "batch-20251116-123456",
  "current_index": 3,
  "completed": ["feature1", "feature2", "feature3"],
  "failed": [],
  "status": "paused",
  "context_token_estimate": 155000,
  "context_tokens_before_clear": 155000,
  "paused_at_feature_index": 3,
  "auto_clear_count": 1,
  "auto_clear_events": [
    {
      "feature_index": 3,
      "context_tokens_before_clear": 155000,
      "timestamp": "2025-11-17T12:34:56Z"
    }
  ],
  "issue_numbers": [72, 73, 74],
  "source_type": "github_issues"
}
```

### Context Clearing Workflow (NEW in v3.31.0 - Issue #88)

**Problem**: `/clear` command cannot be programmatically invoked (architectural limitation).

**Solution**: Hybrid approach - detect threshold, pause batch, notify user, wait for manual /clear, auto-resume.

**User Workflow**:

1. **System processes features normally** - Features complete until context reaches threshold
2. **Threshold detected at 150K tokens** - `should_clear_context(state)` returns True
3. **Batch pauses automatically** - `pause_batch_for_clear()` sets status="paused"
4. **User receives notification** with batch ID and next steps
5. **User manually runs /clear** - Clears conversation (system-native command)
6. **User resumes batch** - `/batch-implement --resume <batch-id>`
7. **System resets token estimate** and continues from next feature
8. **Process repeats** for large batches (20+ features may pause multiple times)

**Benefits**:
- Supports 50+ features without context bloat
- Graceful UX (clear, actionable instructions)
- No architectural workarounds
- State persists across clear events
- Backward compatible with existing batches

### Auto-Clear Threshold

- System pauses at 150K tokens (conservative threshold)
- User manually runs `/clear` to reset context
- Batch automatically resumes after `/clear`
- Multiple pause/resume cycles supported
- Maintains <8K tokens indefinitely

### Crash Recovery

Resume from last completed feature:

```bash
/batch-implement --resume batch-20251116-123456
```

**Recovery Process**:
1. Loads state from `.claude/batch_state.json`
2. Validates status ("paused" for normal resume, other statuses for crash recovery)
3. Resets context token estimate (assumes context was cleared)
4. Skips completed features
5. Continues from current_index

---

## State Tracking

### Tracked Metrics

- **Completed features**: Successfully processed features
- **Failed features**: Features that encountered errors
- **Auto-clear events**: Pause events with timestamps and token counts
- **Current index**: Position in feature list
- **Context tokens**: Before/after clear estimates
- **Pause points**: Feature indices where batch paused
- **Issue numbers**: Original GitHub issue numbers (for --issues flag)
- **Source type**: Input method (file or github_issues)

### Progress Maintenance

- State persists across crashes and context clears
- Automatic resume on restart or after /clear
- No duplicate processing
- Full audit trail of completed work and pause events

---

## Use Cases

1. **Sprint Backlogs**: Process 10-50 features from sprint planning
2. **Overnight Processing**: Queue large feature sets for batch processing
3. **Technical Debt**: Clean up 50+ small improvements sequentially
4. **Large Migrations**: Handle 50+ feature migrations with state-based tracking

---

## Performance

- **Per Feature**: ~20-30 minutes (same as `/auto-implement`)
- **Context Management**: Hybrid approach (pause + manual /clear) maintains <8K tokens
- **Pause/Resume Overhead**: <10 seconds per pause (state save/load)
- **Scalability**: Tested with 50+ features without context bloat
- **Recovery**: Resume from exact failure point or pause point

---

## Implementation Files

- **Command**: `plugins/autonomous-dev/commands/batch-implement.md`
- **State Manager**: `plugins/autonomous-dev/lib/batch_state_manager.py`
- **GitHub Fetcher**: `plugins/autonomous-dev/lib/github_issue_fetcher.py` (v3.24.0)
- **State File**: `.claude/batch_state.json` (created automatically)

---

## See Also

- [commands/auto-implement.md](/plugins/autonomous-dev/commands/auto-implement.md) - Individual feature workflow
- [lib/batch_state_manager.py](/plugins/autonomous-dev/lib/batch_state_manager.py) - State management implementation
- [lib/github_issue_fetcher.py](/plugins/autonomous-dev/lib/github_issue_fetcher.py) - GitHub integration
- [commands/batch-implement.md](/plugins/autonomous-dev/commands/batch-implement.md) - Context clearing workflow details
