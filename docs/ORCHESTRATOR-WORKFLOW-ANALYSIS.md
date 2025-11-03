# Orchestrator Workflow Analysis & Solution

**Date**: 2025-11-03
**Issue**: Orchestrator agent doesn't automatically invoke all 7 specialist agents as designed
**Impact**: Features implemented without full quality pipeline (missing tests, security audits, etc.)

---

## Problem Statement

### What Should Happen

When `/auto-implement <feature>` is run:
1. Claude invokes orchestrator agent via Task tool
2. Orchestrator invokes all 7 specialist agents sequentially:
   - researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master
3. Each agent logs to pipeline JSON
4. `/pipeline-status` shows all 7 agents ran
5. Full SDLC workflow guaranteed

### What Actually Happens

When `/auto-implement <feature>` is run:
1. Claude invokes orchestrator agent via Task tool
2. Orchestrator receives the prompt with explicit "YOU MUST USE TASK TOOL" instructions
3. **Orchestrator provides guidance/summary instead of invoking agents**
4. Claude (me) implements the feature directly
5. No agents logged to pipeline
6. `/pipeline-status` shows "No agents have run yet"

### Root Cause

**The orchestrator IS Claude** - When Task tool loads orchestrator.md, it becomes Claude's system prompt. Claude then makes an **adaptive decision** about whether to invoke agents based on:
- Perceived complexity
- Context efficiency
- Time constraints
- Apparent simplicity of task

The orchestrator.md instructions say "YOU MUST" but Claude's underlying reasoning can override this when it seems more efficient to work directly.

---

## Why This Happens

### Conflicting Signals

1. **orchestrator.md says**: "YOU MUST USE THE TASK TOOL" (lines 10-40)
2. **auto-implement.md says**: "Claude MAY invoke specialist agents" (lines 19, 56)
3. **Claude's training says**: "Be efficient, avoid unnecessary steps"

### Claude's Decision Tree

```
Feature request arrives
    ↓
Is it simple? (e.g., create command file)
    ↓ YES
Skip agents, implement directly (efficient!)
    ↓
Result: No pipeline, no tests, no security audit
```

The issue: **Claude judges complexity** and decides agents aren't needed for "simple" tasks.

But the simulation showed that even "simple" tasks benefit from:
- Tests (test-master)
- Security audit (security-auditor found CRITICAL vuln)
- Documentation sync (doc-master)

---

## Solutions Evaluated

### Option 1: Stronger Orchestrator Prompt ❌
**Approach**: Make orchestrator.md more emphatic
**Problem**: Already has "⚠️ ABSOLUTE REQUIREMENTS - NO EXCEPTIONS"
**Verdict**: Tried this, doesn't work - Claude still makes adaptive decisions

### Option 2: Python Orchestrator Script ❌
**Approach**: Replace GenAI orchestrator with Python that forces agent invocation
**Problem**: Loses flexibility, rigid automation, defeats GenAI-native philosophy
**Verdict**: PROJECT.md explicitly rejects this (lines 213-221)

### Option 3: Enforce via Hook ⚠️
**Approach**: Pre-commit hook checks if pipeline ran, blocks if not
**Problem**: Too late (code already written), breaks manual commits
**Verdict**: Partial solution only

### Option 4: Two-Tier Workflow ✅ **RECOMMENDED**
**Approach**:
- `/auto-implement` → ALWAYS runs full 7-agent pipeline (enforced)
- Direct Claude → Allowed for trivial changes (docs, typos)
**Implementation**: Add enforcement mechanism
**Verdict**: Balances automation with flexibility

### Option 5: Agent Invocation Tracking + Feedback Loop ✅ **BEST**
**Approach**:
- Orchestrator tracks which agents it invoked
- If < 7 agents, orchestrator self-corrects mid-execution
- Uses pipeline JSON to verify completeness
**Implementation**: Modify orchestrator.md with self-checking
**Verdict**: Self-healing, GenAI-native, maintains flexibility

---

## Recommended Solution: Self-Checking Orchestrator

### Design

Modify `orchestrator.md` to include **self-verification checkpoints**:

```markdown
## Agent Invocation Protocol

After invoking each agent, YOU MUST:
1. Log the invocation to pipeline JSON
2. Verify the agent completed successfully
3. Check pipeline status: `python scripts/agent_tracker.py status`
4. If agent count < expected, STOP and invoke missing agents

## Mandatory Checkpoints

- After STEP 3 (test-master): Verify 3 agents in pipeline
- After STEP 7 (doc-master): Verify 7 agents in pipeline
- If count is wrong: Self-correct by invoking missing agents
- NEVER proceed without all 7 agents logged

## Self-Correction Example

```bash
# After doc-master, check pipeline
python scripts/agent_tracker.py status

# If shows: "5 agents ran"
# YOU MUST: Invoke missing 2 agents before finishing
```

### Benefits

1. **Self-healing**: Orchestrator catches its own mistakes
2. **GenAI-native**: Uses reasoning to verify, not rigid enforcement
3. **Flexible**: Can still adapt, but has guardrails
4. **Transparent**: Pipeline status shows what actually ran
5. **Maintains philosophy**: GenAI orchestration with safety nets

---

## Implementation Plan

### Phase 1: Add Self-Verification to Orchestrator ✅

**File**: `plugins/autonomous-dev/agents/orchestrator.md`

**Changes**:
1. Add checkpoint after each agent invocation
2. Add `python scripts/agent_tracker.py status` command
3. Add self-correction logic
4. Add final verification before completion

**Lines to modify**:
- After line 130 (researcher): Add checkpoint
- After line 149 (planner): Add checkpoint
- After line 162 (test-master): Add checkpoint (verify 3 agents)
- After line 177 (implementer): Add checkpoint
- After line 189 (reviewer): Add checkpoint
- After line 199 (security-auditor): Add checkpoint
- After line 210 (doc-master): Add checkpoint + FINAL VERIFICATION

### Phase 2: Update Pipeline Tracker ✅

**File**: `scripts/agent_tracker.py`

**Changes**:
1. Add `get_agent_count()` function
2. Add `get_missing_agents()` function
3. Support orchestrator queries

### Phase 3: Update auto-implement.md ✅

**Changes**:
1. Remove "MAY invoke" language (lines 19, 56)
2. Change to "WILL invoke all 7 agents"
3. Update expectations

### Phase 4: Add Enforcement Hook ⚠️

**File**: `plugins/autonomous-dev/hooks/enforce_orchestrator.py`

**Purpose**: Pre-commit hook that verifies pipeline completeness

**Logic**:
```python
if feature_commit and pipeline_exists:
    agent_count = get_agent_count()
    if agent_count < 7:
        print("❌ Incomplete pipeline: only {agent_count}/7 agents ran")
        print("Missing: {missing_agents}")
        print("Run: /auto-implement again to complete workflow")
        sys.exit(1)
```

**Caveat**: Only enforces for `/auto-implement` commits, allows manual commits

---

## Expected Outcomes

### Before Fix

```bash
/auto-implement "add /sync-dev command"
# Orchestrator invoked → 0 agents actually run → Claude implements directly
# Pipeline: EMPTY
# Tests: NONE
# Security: NOT CHECKED
```

### After Fix

```bash
/auto-implement "add /sync-dev command"
# Orchestrator invoked → Invokes researcher
# Checkpoint 1: ✅ 1 agent logged
# → Invokes planner
# Checkpoint 2: ✅ 2 agents logged
# → Invokes test-master
# Checkpoint 3: ✅ 3 agents logged ← VERIFY
# → Invokes implementer
# Checkpoint 4: ✅ 4 agents logged
# → Invokes reviewer
# Checkpoint 5: ✅ 5 agents logged
# → Invokes security-auditor
# Checkpoint 6: ✅ 6 agents logged
# → Invokes doc-master
# Checkpoint 7: ✅ 7 agents logged ← FINAL VERIFY
# Pipeline: COMPLETE
# Tests: 47 TESTS
# Security: CRITICAL VULN FOUND
```

---

## Testing Strategy

### Test 1: Simple Feature
```bash
/auto-implement "add health check endpoint"
/pipeline-status  # Should show 7 agents
```

### Test 2: Complex Feature
```bash
/auto-implement "add user authentication with JWT"
/pipeline-status  # Should show 7 agents
```

### Test 3: Self-Correction
```bash
# Manually interrupt after researcher
# Orchestrator should detect incomplete pipeline
# Auto-invoke remaining 6 agents
```

---

## Rollout Plan

1. **Update orchestrator.md** with self-verification checkpoints
2. **Update agent_tracker.py** with helper functions
3. **Test with simple feature** to verify all 7 agents run
4. **Update auto-implement.md** to reflect guaranteed agent invocation
5. **Add enforce_orchestrator.py hook** for safety net
6. **Document new workflow** in README and CLAUDE.md

---

## Success Metrics

- ✅ `/pipeline-status` shows 7 agents for every `/auto-implement`
- ✅ Tests created automatically (test-master always runs)
- ✅ Security audits happen (security-auditor always runs)
- ✅ Documentation updated (doc-master always runs)
- ✅ No critical bugs shipped (full workflow prevents)

---

## Alternative: Feature Complexity Tiers

If full 7-agent workflow is too heavy for trivial changes, consider:

### Tier 1: Trivial (Manual)
- Typo fixes, doc updates, README changes
- No `/auto-implement` needed
- Pre-commit hooks only

### Tier 2: Simple (Lightweight - 4 agents)
- Command files, simple config changes
- Agents: planner → implementer → reviewer → doc-master
- Skip: researcher (pattern known), test-master (no code), security-auditor (no risk)

### Tier 3: Standard (Full - 7 agents)
- New features, logic changes, API updates
- All 7 agents required

### Tier 4: Critical (Extended - 7 agents + extra)
- Authentication, security, data handling
- All 7 agents + additional security scans

**Implementation**: Orchestrator decides tier based on feature description, then invokes appropriate agent set.

---

## Conclusion

The orchestrator needs **self-verification checkpoints** to ensure it actually invokes all agents instead of providing summaries. This maintains GenAI flexibility while guaranteeing workflow completeness.

**Next Steps**: Implement Phase 1-4 and test with real feature request.
