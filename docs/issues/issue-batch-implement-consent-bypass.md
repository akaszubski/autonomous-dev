# Issue: /batch-implement Stops for Git Consent Despite AUTO_GIT_ENABLED=true

## Summary

When running `/batch-implement` with `AUTO_GIT_ENABLED=true`, the workflow unexpectedly stops and prompts the user for git operation consent after each feature completes. This blocks the "unattended overnight batch processing" use case that `/batch-implement` is designed to support.

## Problem Description

### Current Behavior

1. User sets `AUTO_GIT_ENABLED=true` in `.env` (expecting fully automated git operations)
2. User runs `/batch-implement --issues 83 53 55` to process 3 features overnight
3. **First feature completes** → Workflow stops and asks: "Would you like me to commit and push these changes? Reply 'yes' to commit and push..."
4. User must manually type "yes" to continue
5. **Second feature starts** → Same consent prompt again
6. Process repeats for each feature, blocking unattended operation

### Expected Behavior

When `AUTO_GIT_ENABLED=true`:
1. User runs `/batch-implement --issues 83 53 55`
2. All 3 features process sequentially **without interruption**
3. Each feature automatically commits and pushes (no consent prompt)
4. Batch completes overnight without user intervention

## Root Cause Analysis

The issue stems from **two separate consent mechanisms** in the codebase:

### 1. First-Run Consent (Working Correctly)
- **File**: `plugins/autonomous-dev/lib/first_run_warning.py`
- **Storage**: `~/.autonomous-dev/user_state.json`
- **Behavior**: One-time opt-out prompt when first using git automation
- **Status**: ✅ Working as designed

### 2. Per-Feature Consent (Blocking Batch Workflow)
- **File**: `plugins/autonomous-dev/commands/auto-implement.md` (STEP 5, lines 525-630)
- **Behavior**: Prompts for consent **every time** a feature completes
- **Status**: ❌ Blocks batch processing even when `AUTO_GIT_ENABLED=true`

### Code Location

`plugins/autonomous-dev/commands/auto-implement.md`, lines 556-579:

```markdown
#### Offer Commit and Push (User Consent Required)

If prerequisites passed, ask user for consent:

```
✅ Feature implementation complete!

Would you like me to commit and push these changes?

...

Reply 'yes' to commit and push, 'commit-only' to commit without push, or 'no' to skip git operations.
```
```

**Problem**: This prompt appears **regardless of `AUTO_GIT_ENABLED` setting**.

## Impact

### User Experience
- **Blocks unattended batch processing** - Users cannot queue 10-20 features overnight as intended
- **Inconsistent with documentation** - `docs/GIT-AUTOMATION.md` claims automation is "enabled by default" but requires manual confirmation per feature
- **Violates DRY principle** - User gives consent twice (first-run + every feature)

### Affected Workflows
- `/batch-implement` (primary use case)
- `/auto-implement` (minor - single features less affected by prompt)

## Proposed Solution

### Option 1: Check AUTO_GIT_ENABLED Before Prompting (Recommended)

Modify `auto-implement.md` STEP 5 to respect `AUTO_GIT_ENABLED` environment variable:

**Pseudocode**:
```python
if os.getenv("AUTO_GIT_ENABLED") == "true":
    # Skip consent prompt - proceed automatically
    user_response = "yes"
    print("✅ Feature complete! Auto-committing (AUTO_GIT_ENABLED=true)...")
else:
    # Ask for consent (current behavior)
    user_response = input("Would you like me to commit and push? [yes/no]: ")
```

**Benefits**:
- ✅ Enables true unattended batch processing
- ✅ Respects existing environment variable convention
- ✅ Maintains backward compatibility (users without `AUTO_GIT_ENABLED` still get prompted)
- ✅ Consistent with `docs/GIT-AUTOMATION.md` documentation

**Risks**:
- Users with `AUTO_GIT_ENABLED=true` lose per-feature opt-out ability
  - **Mitigation**: They can set `AUTO_GIT_ENABLED=false` temporarily or use `git reset HEAD~1` to undo unwanted commits

### Option 2: Add BATCH_MODE Flag

Add a separate `BATCH_MODE` environment variable:

```bash
BATCH_MODE=true  # Skip all interactive prompts during batch processing
```

**Benefits**:
- ✅ Separates batch automation from git automation settings
- ✅ Preserves per-feature consent for interactive `/auto-implement` usage

**Drawbacks**:
- ❌ Adds another environment variable (increases complexity)
- ❌ Less discoverable (users might not know about this setting)

### Option 3: Pass Flag from /batch-implement to /auto-implement

Modify `/batch-implement` to pass a `--batch-mode` flag to `/auto-implement`:

```bash
/auto-implement --batch-mode "feature description"
```

**Benefits**:
- ✅ No environment variables needed
- ✅ Clear distinction between batch and interactive modes

**Drawbacks**:
- ❌ Requires changes to `/auto-implement` command signature
- ❌ Users running `/auto-implement` manually in batch scripts need to remember flag

## Recommendation

**Option 1** (check `AUTO_GIT_ENABLED` before prompting) is recommended because:
1. Uses existing environment variable (no new configuration needed)
2. Matches user expectations (if I set `AUTO_GIT_ENABLED=true`, I expect automation)
3. Simplest implementation (one conditional check)
4. Consistent with existing documentation claims

## Implementation Checklist

- [ ] Update `plugins/autonomous-dev/commands/auto-implement.md` STEP 5 to check `AUTO_GIT_ENABLED`
- [ ] Add pseudocode/logic for automatic approval when `AUTO_GIT_ENABLED=true`
- [ ] Test `/batch-implement` workflow with 3+ features (verify no prompts)
- [ ] Test `/auto-implement` with `AUTO_GIT_ENABLED=false` (verify prompt still appears)
- [ ] Update `docs/GIT-AUTOMATION.md` to document per-feature consent bypass behavior
- [ ] Update `docs/BATCH-PROCESSING.md` prerequisites section (ensure `AUTO_GIT_ENABLED=true` is listed)
- [ ] Add integration test: `tests/integration/test_batch_consent_bypass.py`
- [ ] Update `CHANGELOG.md` with breaking change notice (if applicable)

## Testing Scenarios

### Scenario 1: Batch Processing with AUTO_GIT_ENABLED=true
```bash
# Setup
echo "AUTO_GIT_ENABLED=true" > .env
echo "feature 1\nfeature 2\nfeature 3" > features.txt

# Execute
/batch-implement features.txt

# Expected: All 3 features complete without prompts
# Actual (before fix): Stops after feature 1 and prompts
```

### Scenario 2: Single Feature with AUTO_GIT_ENABLED=false
```bash
# Setup
echo "AUTO_GIT_ENABLED=false" > .env

# Execute
/auto-implement "add logging"

# Expected: Prompt appears asking for consent
# Actual (before fix): Prompt appears (correct behavior)
```

### Scenario 3: Single Feature with AUTO_GIT_ENABLED=true
```bash
# Setup
echo "AUTO_GIT_ENABLED=true" > .env

# Execute
/auto-implement "add logging"

# Expected: No prompt, automatic commit/push
# Actual (before fix): Prompt appears (incorrect behavior)
```

## Related Issues

- Issue #61 - Enable Zero Manual Git Operations by Default
- Issue #75 - Batch Implementation
- Issue #89 - Automatic Retry for Transient Failures

## Related Documentation

- `docs/GIT-AUTOMATION.md` - Git automation documentation
- `docs/BATCH-PROCESSING.md` - Batch processing documentation
- `plugins/autonomous-dev/commands/auto-implement.md` - Auto-implement workflow
- `plugins/autonomous-dev/commands/batch-implement.md` - Batch-implement workflow

## Success Criteria

✅ User can run `/batch-implement features.txt` overnight without interaction (when `AUTO_GIT_ENABLED=true`)
✅ User can still opt-out of git automation per-feature (when `AUTO_GIT_ENABLED=false`)
✅ Documentation accurately reflects behavior
✅ Integration tests cover both automatic and manual consent modes
