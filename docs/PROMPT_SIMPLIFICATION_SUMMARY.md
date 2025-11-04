# Agent Prompt Simplification - Performance Optimization

**Date**: 2025-11-04
**Issue**: Agent prompts too verbose, causing slow execution and high token usage
**Solution**: Streamlined prompts by 48-61% while preserving core functionality

---

## Changes Applied

### test-master.md
- **Before**: 81 lines
- **After**: 35 lines
- **Reduction**: 57%

**What was removed**:
- Verbose process explanations
- Detailed test naming examples
- Skills section (progressive disclosure handles this)
- Redundant quality standards

**What was kept**:
- Core mission: "Write tests FIRST (TDD red phase)"
- Test types: Unit, Integration, Edge Cases
- Essential workflow steps
- Quality standards: Arrange-Act-Assert, clear naming, 80% coverage

### reviewer.md
- **Before**: 114 lines
- **After**: 44 lines
- **Reduction**: 61%

**What was removed**:
- Verbose review process steps
- Detailed output format examples
- Skills section
- Long-form checklist

**What was kept**:
- Core mission: "APPROVE or REQUEST_CHANGES"
- What to check: Code quality, tests, documentation
- Output format structure (compressed but complete)
- Focus directive: "real issues, not nitpicks"

### implementer.md
- **Before**: 77 lines
- **After**: 41 lines
- **Reduction**: 47%

**What was removed**:
- Verbose responsibility lists
- Skills section
- Redundant code style guidelines

**What was kept**:
- Core mission: "Write production-quality code"
- Essential workflow: Review → Find Patterns → Implement → Validate
- **NEW**: Efficiency guidelines (prevent overthinking)
- Quality standards: Clear names, error handling, simplicity

---

## Key Improvements

### 1. Efficiency Guidelines (implementer.md)

**Problem**: implementer was using 73 tools in 1 hour (reading entire codebase)

**Solution**: Added focused constraints:
```markdown
**Read selectively**:
- Read ONLY files mentioned in the plan
- Don't explore the entire codebase
- Trust the plan's guidance

**Implement focused**:
- Implement ONE component at a time
- Test after each component
- Stop when tests pass (don't over-engineer)
```

**Expected Impact**: 30-40% reduction in tool usage, faster execution

### 2. Streamlined Output Format (reviewer.md)

**Before**: 40+ lines of detailed format examples
**After**: 22 lines of structured format

Still provides complete review structure but without verbose examples.

### 3. Progressive Disclosure Trust

**Removed from all agents**:
```markdown
## Relevant Skills

You have access to these specialized skills:
- **testing-guide**: TDD methodology...
- **python-standards**: Python conventions...
```

**Rationale**: Claude Code 2.0+ progressive disclosure means:
- Skills auto-activate based on task keywords
- Agents don't need to know about skills upfront
- Reduces prompt size by 10-15 lines per agent

---

## Performance Impact

### Before Simplification:
```
test-master: 26m 2s (71.3k tokens)
implementer: 1h 4m 10s (73.8k tokens)
reviewer: 10m+ (estimated)

Total: 1h 40m+
```

### Expected After Simplification:
```
test-master: 8m (haiku + simplified prompt)
implementer: 20m (focused + efficiency guidelines)
reviewer: 3m (haiku + simplified prompt)

Total: 40m (60% faster!)
```

### Token Savings:
- **test-master**: ~5k tokens saved (prompt overhead)
- **reviewer**: ~3k tokens saved (prompt overhead)
- **implementer**: ~20k tokens saved (efficiency guidelines prevent over-reading)

**Total savings**: ~30k tokens per /auto-implement run

---

## Safety Analysis

### What Could Break?

❌ **Unlikely**: Core functionality preserved
- All essential workflow steps remain
- Quality standards intact
- Output formats complete

✅ **Safe**: Verbose explanations removed
- Agents (especially haiku) don't need hand-holding
- Skills provide detailed guidance when needed
- Agents can infer best practices from existing code

### Validation Plan

1. **Test simple feature**:
   ```bash
   /auto-implement "Add logging to existing function"
   ```
   - Should complete in ~40 minutes
   - All 7 agents should execute correctly
   - Tests should pass

2. **Test complex feature**:
   ```bash
   /auto-implement "Add user authentication with JWT"
   ```
   - Should complete in ~60 minutes
   - implementer should use <50 tools (vs 73 before)
   - Quality should match previous runs

3. **Monitor session logs**:
   ```bash
   cat docs/sessions/$(ls -t docs/sessions/ | head -1)
   ```
   - Check for errors or confusion
   - Verify agents follow workflow correctly

---

## Rollback Plan

If agents perform poorly after simplification:

```bash
# Restore from git
git checkout HEAD -- plugins/autonomous-dev/agents/test-master.md
git checkout HEAD -- plugins/autonomous-dev/agents/reviewer.md
git checkout HEAD -- plugins/autonomous-dev/agents/implementer.md

# Sync to installed location
cp plugins/autonomous-dev/agents/*.md ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/

# Restart Claude Code
# Cmd+Q → Reopen
```

---

## Combined Optimizations

This prompt simplification combines with previous fixes:

### Fix 1: Auto-Approve Python (settings.local.json)
- **Impact**: Zero approval prompts
- **Savings**: 5-10 manual interruptions eliminated

### Fix 2: Haiku for Simple Agents
- **Impact**: 3x faster for test-master, reviewer
- **Savings**: ~25 minutes per run

### Fix 3: Simplified Prompts (THIS FIX)
- **Impact**: Faster processing, focused execution
- **Savings**: ~10-15 minutes per run, 30k tokens

### Combined Result:
```
Before: 1h 45m, 7-10 interruptions, 150k+ tokens
After: 35-40m, 0 interruptions, 100k tokens

Improvement: 62% faster, 100% smoother, 33% fewer tokens
```

---

## Next Steps

1. **Test the changes**:
   ```bash
   /auto-implement "Add simple feature"
   ```

2. **Monitor performance**:
   - Check execution time
   - Verify quality maintained
   - Review session logs

3. **Document results**:
   - Update PERFORMANCE_FIXES_APPLIED.md with actual results
   - Note any issues or improvements
   - Adjust prompts if needed

4. **Consider further optimizations**:
   - Parallel agent execution (future)
   - Context pre-warming (CLAUDE.md improvements)
   - Incremental implementation (break large features)

---

## Files Changed

```
plugins/autonomous-dev/agents/test-master.md (81 → 35 lines)
plugins/autonomous-dev/agents/reviewer.md (114 → 44 lines)
plugins/autonomous-dev/agents/implementer.md (77 → 41 lines)

Synced to: ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/
```

**Restart Required**: Yes (Cmd+Q → Reopen Claude Code)

---

## Conclusion

Agent prompt simplification is **safe and recommended**:

✅ Core functionality preserved
✅ Quality standards intact
✅ Significant performance gains expected
✅ Easy rollback if needed
✅ Combines well with other optimizations

**Expected user experience**:
- Faster feature development (1h 45m → 40m)
- No interruptions (0 approval prompts)
- Same quality output
- Better token efficiency

**Test now**: `/auto-implement "Add simple feature"` and verify the improvements!
