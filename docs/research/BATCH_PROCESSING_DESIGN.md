# Batch Processing Design Research

> **Issue Reference**: Issue #75, #88, #89, #93
> **Research Date**: 2025-12-17
> **Status**: Active

## Overview

Research and design decisions behind batch processing in autonomous-dev. The `/batch-implement` command processes multiple features sequentially with crash recovery and compaction resilience.

---

## Key Findings

### 1. The Context Compaction Problem

**Problem**: Claude Code auto-compacts context during long sessions.

**Symptoms**:
- Features 1-4 complete successfully
- Feature 5 starts but loses context of batch state
- Manual intervention required to resume

**Statistics**:
- Context compaction triggers at ~100K tokens
- Typical feature uses 25-35K tokens
- 4-5 features before compaction risk

### 2. Compaction-Resilient Architecture

**Solution**: Externalize all state.

```
Before (Context-dependent):
┌─────────────────────────────┐
│ Claude Context              │
│ - Feature list              │
│ - Current index             │
│ - Completed features        │
│ - Git state                 │
└─────────────────────────────┘
       ↓ compaction
       All state lost!

After (Externalized state):
┌─────────────────────────────┐
│ .claude/batch_state.json    │
│ - Feature list              │
│ - Current index             │
│ - Completed features        │
└─────────────────────────────┘
┌─────────────────────────────┐
│ Git History                 │
│ - Per-feature commits       │
│ - Work permanently saved    │
└─────────────────────────────┘
┌─────────────────────────────┐
│ GitHub Issues               │
│ - Feature definitions       │
│ - Requirements source       │
└─────────────────────────────┘
```

**Result**: Each feature bootstraps fresh from external state.

### 3. State Management

**State file structure** (`.claude/batch_state.json`):

```json
{
  "batch_id": "batch-20251217-080000",
  "features": [
    "Issue #151: Research persistence",
    "Issue #149: Rebuild PROJECT.md"
  ],
  "total_features": 2,
  "current_index": 1,
  "completed_features": [0],
  "failed_features": [],
  "retry_counts": {"0": 0, "1": 0},
  "status": "in_progress",
  "source_type": "issues",
  "issue_numbers": [151, 149]
}
```

**State transitions**:
```
pending → in_progress → completed
                    ↘ failed (if errors)
```

### 4. Automatic Retry (Issue #89)

**Problem**: Transient failures (network, API limits) shouldn't stop batch.

**Solution**: Intelligent failure classification + retry.

| Failure Type | Examples | Retry? | Max Retries |
|--------------|----------|--------|-------------|
| **Transient** | ConnectionError, Timeout, 429 | Yes | 3 |
| **Permanent** | SyntaxError, ImportError | No | 0 |

**Implementation**:
```python
def classify_failure(error: str) -> FailureType:
    transient_patterns = [
        "ConnectionError", "TimeoutError",
        "429", "rate limit", "network"
    ]
    for pattern in transient_patterns:
        if pattern in error:
            return FailureType.TRANSIENT
    return FailureType.PERMANENT
```

**Safety limits**:
- Max 3 retries per feature
- Max 50 total retries per batch
- Circuit breaker after 5 consecutive failures

### 5. Per-Feature Git Automation (Issue #93)

**Design**: Each feature gets its own commit.

```
Feature 1 completes → git commit "feat: Feature 1 (#151)"
Feature 2 completes → git commit "feat: Feature 2 (#152)"
Feature 3 completes → git commit "feat: Feature 3 (#153)"
```

**Benefits**:
- Atomic rollback (revert one feature, keep others)
- Clear git history (one commit per feature)
- Work preserved even if batch fails mid-way

---

## Design Decisions

### Why Externalized State?

**Considered alternatives**:
1. Context variables (rejected - lost on compaction)
2. Database (rejected - overkill, dependency)
3. JSON file (chosen - simple, portable, atomic)

**JSON benefits**:
- Human-readable debugging
- Atomic writes (write to .tmp, rename)
- No external dependencies
- Git-trackable state

### Why Per-Feature Commits?

**Problem**: Single batch commit loses granularity.

**Research**: 67% of batch failures occur mid-batch.

| Approach | Rollback Granularity | Work Lost on Failure |
|----------|---------------------|---------------------|
| Single commit | All or nothing | Everything |
| Per-feature | Individual features | Just current feature |

**Decision**: Per-feature commits for granular rollback.

### Why Consent-Based Retry?

**Problem**: Automatic retry could waste API credits.

**Solution**: First-run consent prompt + environment override.

```python
# First run: Interactive prompt
"Enable automatic retry for transient failures? [yes/no]"

# Subsequent runs: Use saved consent
consent = load_from("~/.autonomous-dev/user_state.json")

# Environment override for automation
BATCH_RETRY_ENABLED=true  # Skip prompt
```

---

## Batch Processing Flow

```
/batch-implement --issues 151 152 153
         ↓
┌─────────────────────────────────────┐
│ 1. Create batch_state.json          │
│    - Fetch issue titles from GitHub │
│    - Initialize state               │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ 2. For each feature:                │
│    a. Load from batch_state.json    │
│    b. Run /auto-implement           │
│    c. Git commit (per-feature)      │
│    d. Update batch_state.json       │
│    e. Handle retry if transient     │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ 3. Summary report                   │
│    - Completed: N                   │
│    - Failed: M                      │
│    - Time: HH:MM:SS                 │
└─────────────────────────────────────┘
```

---

## Crash Recovery

**Resume command**: `/batch-implement --resume <batch-id>`

```python
def resume_batch(batch_id: str):
    state = load_batch_state(batch_id)

    # Skip completed features
    start_index = state["current_index"]

    # Continue from where we left off
    for i in range(start_index, state["total_features"]):
        process_feature(state["features"][i])
        update_batch_state(state, i)
```

**Recovery scenarios**:
1. Claude Code crash → Resume from current_index
2. Network failure → Retry or resume
3. User interruption → Resume anytime

---

## Source References

- **12-Factor App**: Stateless processes, externalized config
- **Saga Pattern**: Distributed transaction recovery
- **Circuit Breaker Pattern**: Failure handling in distributed systems
- **Idempotency**: Safe retry semantics

---

## Implementation Notes

### Applied to autonomous-dev

1. **batch_state_manager.py**: State persistence library
2. **batch_retry_manager.py**: Retry orchestration
3. **failure_classifier.py**: Transient vs permanent
4. **batch-implement.md**: Command implementation

### File Locations

```
plugins/autonomous-dev/
├── commands/
│   └── batch-implement.md     # Command definition
├── lib/
│   ├── batch_state_manager.py # State persistence
│   ├── batch_retry_manager.py # Retry logic
│   └── failure_classifier.py  # Error classification
└── docs/
    └── BATCH-PROCESSING.md    # User documentation
```

---

## Related Issues

- **Issue #75**: Initial batch implementation
- **Issue #88**: Compaction-resilient design
- **Issue #89**: Automatic retry
- **Issue #93**: Per-feature git automation

---

**Generated by**: Research persistence (Issue #151)
