# Quick Performance Fixes - `/auto-implement` Speedup

**TL;DR**: Agents are slow due to context bloat, not just tool approvals. Here are the fixes, ordered by impact.

---

## Fix #1: Use `/clear` After Each Feature (IMMEDIATE - 10 SEC)

**Impact**: 40-60% faster
**Effort**: 10 seconds
**When**: After every feature completes

```bash
# You just finished a feature
/auto-implement "add user authentication"
# ... 20 minutes later, feature complete ...

# CRITICAL: Clear context before next feature
/clear

# Now start next feature (will be much faster)
/auto-implement "add rate limiting"
```

**Why it works**:
- Context accumulates: Feature 1 (10K tokens) + Feature 2 (15K tokens) + Feature 3 (20K tokens) = 45K tokens
- Each agent must process ALL that context before acting
- `/clear` resets to 0 tokens
- First feature: 20 min → Subsequent features without `/clear`: 35+ min → With `/clear`: 20 min

**This is the #1 thing you should do RIGHT NOW.**

---

## Fix #2: Update Settings for Auto-Approvals (5 MIN)

**Impact**: 10-15% faster
**Effort**: 5 minutes
**File**: `.claude/settings.local.json`

**Current problem**: Your local settings override global auto-approvals

**Quick fix**:

```bash
# Backup current settings
cp .claude/settings.local.json .claude/settings.local.json.backup

# Update to fast settings
cat > .claude/settings.local.json << 'EOF'
{
  "description": "Strict Mode - Fast Execution",
  "permissions": {
    "allow": [
      "Read:.*",
      "Write:.*",
      "Edit:.*",
      "Glob:.*",
      "Grep:.*",
      "Bash:python.*",
      "Bash:pytest.*",
      "Bash:git.*",
      "Bash:(ls|cat|find|grep|mkdir|cp|mv).*",
      "WebSearch:.*",
      "WebFetch:.*",
      "Task:.*"
    ],
    "ask": [
      "Bash:rm.*",
      "Bash:sudo.*",
      "Bash:git reset.*",
      "Bash:git push.*force.*"
    ]
  },
  "hooks": {
    ... keep existing hooks ...
  }
}
EOF
```

**Result**: No more approval prompts during normal workflow

---

## Fix #3: Simplify Agent Prompts (1-2 HOURS - WEEKEND PROJECT)

**Impact**: 15-25% faster per agent
**Effort**: 1-2 hours
**Files**: `plugins/autonomous-dev/agents/*.md`

**Current state**:
- planner: 119 lines
- reviewer: 113 lines
- researcher: 99 lines

**Target**: 50-80 lines (trust the model more)

**What to remove**:
1. Example code blocks
2. Step-by-step prescriptions
3. Verbose explanations
4. Redundant instructions

**What to keep**:
1. Clear mission statement
2. Core responsibilities (3-5 bullets)
3. Output format
4. Tool list

**Example simplification**:

Before (113 lines):
```markdown
# Reviewer Agent

You are a code reviewer who ensures quality...

## Process

1. First, read the implementation files
2. Then, check for code smells
3. Next, verify test coverage
4. After that, check documentation
5. Finally, provide feedback

[... 100 more lines of detailed instructions ...]
```

After (60 lines):
```markdown
# Reviewer Agent

Review code quality and provide actionable feedback.

## Responsibilities
- Check code patterns and best practices
- Verify test coverage (80%+ target)
- Ensure documentation is updated
- Identify security issues

## Output
- Summary: Overall quality assessment
- Issues: List of problems found
- Recommendations: Specific fixes needed
```

**Do this when you have time - not urgent.**

---

## Fix #4: Switch Models for Simple Tasks (30 MIN)

**Impact**: 20-30% faster for affected agents
**Effort**: 30 minutes
**Files**: 3 agent files

**Changes**:

1. `plugins/autonomous-dev/agents/security-auditor.md`:
   ```yaml
   ---
   model: sonnet  # CHANGE TO: haiku
   ```

2. `plugins/autonomous-dev/agents/doc-master.md`:
   ```yaml
   ---
   model: sonnet  # CHANGE TO: haiku
   ```

3. `plugins/autonomous-dev/agents/researcher.md`:
   ```yaml
   ---
   model: sonnet  # KEEP AS IS (needs reasoning)
   ```

**Rationale**:
- `haiku`: Fast, cheap, good for pattern matching and simple tasks
- `sonnet`: Balanced, good for reasoning and complex tasks
- `opus`: Slow, expensive, only for critical planning

**When to use each**:
- `haiku`: Security scans, doc updates, simple formatting
- `sonnet`: Research, implementation, testing, review
- `opus`: Architecture planning only

---

## Expected Results

### Before All Fixes
- **First feature**: 20-30 minutes
- **Second feature** (without `/clear`): 35-50 minutes (context bloat)
- **Third feature** (without `/clear`): 50+ minutes (severe bloat)
- **User experience**: Frustrating, feels broken

### After Fix #1 Only (Use `/clear`)
- **Every feature**: 20-30 minutes consistently
- **User experience**: Much better, predictable

### After Fixes #1 + #2 (Auto-approvals)
- **Every feature**: 17-25 minutes
- **User experience**: Smooth, no interruptions

### After All Fixes (#1 + #2 + #3 + #4)
- **Every feature**: 12-18 minutes
- **User experience**: Feels fast and autonomous

---

## Action Plan

**Right now** (10 seconds):
1. Run `/clear` after each feature completes
2. Make this a habit

**Today** (5 minutes):
1. Update `.claude/settings.local.json` for auto-approvals
2. Test with a simple feature

**This weekend** (1-2 hours):
1. Simplify agent prompts to 50-80 lines
2. Change security-auditor and doc-master to `haiku`
3. Test quality is maintained

---

## Measuring Success

**Before**:
```bash
time /auto-implement "add health check endpoint"
# Result: 28 minutes
```

**After Fix #1** (`/clear` usage):
```bash
# Feature 1
time /auto-implement "add health check endpoint"
# Result: 20 minutes

/clear

# Feature 2 (should be similar, not slower)
time /auto-implement "add rate limiting"
# Result: 21 minutes (not 35+ minutes)
```

**After All Fixes**:
```bash
time /auto-implement "add health check endpoint"
# Result: 12-15 minutes
```

---

## FAQ

**Q: Will simplifying agents reduce quality?**
A: No - Anthropic's official agents are 50-100 lines. Trust the model. We're currently over-prescribing.

**Q: Is `/clear` safe?**
A: Yes - it only clears conversation history, not files. Your code is safe.

**Q: What if I forget to `/clear`?**
A: You'll notice agents getting slower. Just run `/clear` and continue.

**Q: Can I automate `/clear`?**
A: Yes - we can add it to `/auto-implement` command to auto-clear after completion. Future enhancement.

---

## Bottom Line

1. **Use `/clear` after each feature** ← DO THIS NOW
2. Update settings for auto-approvals ← DO THIS TODAY
3. Simplify agent prompts ← DO THIS WEEKEND
4. Switch models for simple tasks ← DO THIS WEEKEND

Expected result: **40-60% faster** with just Fix #1, **60-70% faster** with all fixes.

---

**Last Updated**: 2025-11-03
**Full Details**: See `docs/PERFORMANCE_OPTIMIZATION.md`
