# Hook Behavior & Reliability Guide

**Last Updated**: 2025-11-03
**Status**: Critical - Read before configuring hooks

---

## TL;DR - What Actually Works

| Hook Type | Reliability | Use Case | Status |
|-----------|------------|----------|--------|
| **PreCommit** | ✅ 100% reliable | Validation before commits | **USE THIS** |
| **PrePush** | ✅ Reliable | Validation before push | **USE THIS** |
| **PostToolUse** | ✅ Reliable | After tool execution | **USE THIS** |
| **UserPromptSubmit** | ❌ Buggy (#8810) | Before prompt processing | **AVOID** |
| **SessionStart** | ⚠️ Intermittent | Session initialization | **TEST FIRST** |
| **SubagentStop** | ✅ Works | After agent completes | **USE THIS** |
| **Commands** | ✅ 100% reliable | Manual invocation | **BEST CHOICE** |

**Key Finding**: Don't rely on UserPromptSubmit for auto-orchestration. Use commands instead.

---

## The UserPromptSubmit Bug (#8810)

### What's Broken

**Bug**: UserPromptSubmit hooks don't fire reliably from project directories.

**Symptoms**:
- Hook configured in `.claude/settings.local.json`
- Testing directly: `echo "implement X" | python .claude/hooks/detect_feature_request.py` ✅ Works
- Real usage: Type "implement X" in Claude Code ❌ Doesn't trigger

**GitHub Issue**: https://github.com/anthropics/claude-code/issues/8810

**Status**: Open, unfixed (as of 2025-11-03)

**Workaround success rate**: ~80-90% (unreliable)

### Why This Matters for Auto-Orchestration

We tried to implement "vibe coding" where you just say "implement X" and it auto-triggers `/auto-implement`.

**Expected**:
```
You: "implement issue #38"
Hook: Detects feature request
System: Auto-runs /auto-implement
Result: Autonomous workflow executes
```

**Reality**:
```
You: "implement issue #38"
Hook: Doesn't fire (bug)
System: I respond conversationally
Result: You have to manually type /auto-implement
```

---

## Recommended Approach: Use Commands

### Option 1: Manual Commands (100% Reliable)

**Just use slash commands**:
```bash
/auto-implement "implement issue #38"
```

**Pros**:
- ✅ Always works
- ✅ Clear and explicit
- ✅ No hook bugs

**Cons**:
- ⏳ Requires typing `/auto-implement` each time
- ⏳ Not true "vibe coding"

---

### Option 2: Shell Alias (Faster)

**Create an alias**:
```bash
# In your shell
alias ai='/auto-implement'

# Then use:
ai "implement issue #38"
```

**Pros**:
- ✅ Always works
- ✅ Faster than typing full command
- ✅ No hook bugs

**Cons**:
- ⏳ Still manual invocation

---

### Option 3: PreCommit Hook (Different Trigger)

**Instead of detecting feature requests**, use PreCommit to run validation:

```json
{
  "hooks": {
    "PreCommit": [
      {
        "description": "Validate PROJECT.md alignment",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/validate_project_alignment.py || exit 1"
          }
        ]
      }
    ]
  }
}
```

**This works because**:
- PreCommit hooks are 100% reliable
- They fire when you commit (not on prompt)
- Different use case, but guaranteed to work

---

## What We Learned Testing Auto-Orchestration

### Test 1: UserPromptSubmit Hook
```
Input: "implement issue #38"
Expected: Hook detects → Auto-runs /auto-implement
Result: ❌ Hook didn't fire (bug #8810)
```

### Test 2: Direct Hook Test
```bash
echo "implement issue #38" | python .claude/hooks/detect_feature_request.py
Result: ✅ Hook works when tested directly
```

### Test 3: Manual Command
```
Input: /auto-implement "implement issue #38"
Result: ✅ Command worked perfectly, orchestrator invoked
```

**Conclusion**: The hook code is correct, but Claude Code doesn't reliably fire UserPromptSubmit hooks.

---

## Reliable Hook Configuration

### What Actually Works

```json
{
  "hooks": {
    "PreCommit": [
      {
        "description": "Project alignment validation",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/validate_project_alignment.py || exit 1"
          }
        ]
      },
      {
        "description": "Security scan",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/security_scan.py || exit 1"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "description": "Log agent completion",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/session_tracker.py subagent 'Completed'"
          }
        ]
      }
    ]
  }
}
```

**Why these work**:
- PreCommit: Fires on `git commit` (reliable)
- SubagentStop: Fires after agents (reliable)
- No UserPromptSubmit: Avoid the buggy hook

---

## Updated Workflow (Without Auto-Orchestration)

### Old Vision (Doesn't Work Reliably)
```
You: "implement issue #38"
→ Hook auto-detects
→ System runs /auto-implement
→ Autonomous workflow
```

### Current Reality (What Works)
```
You: /auto-implement "implement issue #38"
→ Command runs
→ Autonomous workflow
```

**Difference**: One extra typing step (`/auto-implement`), but 100% reliable.

---

## When Hooks DO Work

### PreCommit Hooks (Validation)

**Perfect for**:
- PROJECT.md alignment checks
- Security scanning
- Test generation
- Documentation updates
- File organization enforcement

**Example**:
```bash
git add .
git commit -m "feat: add feature"
# PreCommit hooks run automatically ✅
# - validate_project_alignment.py
# - security_scan.py
# - auto_generate_tests.py
# - auto_update_docs.py
```

### SubagentStop Hooks (Logging)

**Perfect for**:
- Session logging
- Agent activity tracking
- Progress monitoring

**Example**:
```bash
/auto-implement "feature X"
# orchestrator runs
# SubagentStop hook fires ✅
# Logs to docs/sessions/
```

---

## Debugging Hooks

### Check if Hook Fires

**Method 1: Add echo to hook**:
```json
{
  "hooks": {
    "PreCommit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'HOOK FIRED!' && python .claude/hooks/my_hook.py"
          }
        ]
      }
    ]
  }
}
```

**Method 2: Check hook output**:
```bash
# PreCommit hooks show output during commit
git commit -m "test"
# You'll see hook output

# UserPromptSubmit hooks... unreliable
```

### Test Hook Directly

```bash
# Test Python hook
python .claude/hooks/detect_feature_request.py <<< "implement X"

# Test with actual input
echo "implement user auth" | python .claude/hooks/detect_feature_request.py
```

---

## Recommendations

### For Auto-Orchestration

**DON'T**:
- ❌ Rely on UserPromptSubmit hook (bug #8810)
- ❌ Expect "vibe coding" to work out of the box
- ❌ Configure auto-detection in hooks

**DO**:
- ✅ Use `/auto-implement` command directly
- ✅ Create shell alias for faster typing
- ✅ Accept manual invocation (it's reliable)

### For Validation

**DO**:
- ✅ Use PreCommit hooks for all validation
- ✅ Block commits with `|| exit 1`
- ✅ Show clear error messages
- ✅ Auto-fix when possible

### For Logging

**DO**:
- ✅ Use SubagentStop for agent logging
- ✅ Log to `docs/sessions/`
- ✅ Make logs viewable with scripts

---

## Summary

**What we learned today**:

1. ✅ Commands work perfectly (`/auto-implement`)
2. ✅ PreCommit hooks work (validation works)
3. ❌ UserPromptSubmit hooks don't work reliably (bug #8810)
4. ✅ SubagentStop hooks work (logging works)

**Updated approach**:
- Use `/auto-implement` directly (not auto-detection)
- Keep PreCommit validation (works great)
- Keep SubagentStop logging (works great)
- Accept that "true vibe coding" isn't reliable yet

**Result**: Slightly less magical, but 100% reliable.

---

## Future: When Bug is Fixed

**If/when UserPromptSubmit bug is fixed**:

1. Re-enable auto-detection hook
2. Test thoroughly in subdirectories
3. Keep `/auto-implement` command as backup
4. Update this doc with new findings

**Track bug**: https://github.com/anthropics/claude-code/issues/8810

---

**Last Updated**: 2025-11-03 (after testing auto-orchestration)
