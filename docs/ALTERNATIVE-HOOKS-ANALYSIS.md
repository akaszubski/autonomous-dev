# Alternative Hooks Analysis for Auto-Orchestration

**Question**: Can we use hooks OTHER than UserPromptSubmit to detect "implement X" requests?

**Answer**: No reliable alternatives, but here's the analysis.

---

## All Available Hooks

| Hook | When It Fires | Could It Work? | Why/Why Not |
|------|---------------|----------------|-------------|
| **UserPromptSubmit** | Before Claude processes prompt | ⚠️ Should work | Bug #8810 - unreliable from subdirectories |
| **SessionStart** | Session begins | ❌ No | Too early - user hasn't said anything yet |
| **PreToolUse** | Before tool executes | ❌ No | Too late - Claude already decided what to do |
| **PostToolUse** | After tool completes | ❌ No | Way too late - work already done |
| **Stop** | After Claude finishes | ❌ No | After response complete |
| **SubagentStop** | After subagent finishes | ❌ No | Only for subagents |
| **PreCompact** | Before context compression | ❌ No | Unrelated to user intent |
| **SessionEnd** | Session terminates | ❌ No | Too late |
| **Notification** | Claude sends notification | ❌ No | For permission/idle states |

**Verdict**: **UserPromptSubmit is the ONLY hook that could detect user intent early enough.**

---

## Why Each Alternative Fails

### SessionStart Hook

**When**: Session initialization or resumption

**Idea**: Pre-load instructions like "If user says 'implement X', run /auto-implement"

**Why it fails**:
```
SessionStart: "Remember to auto-detect 'implement X' requests"
User: "implement issue #38"
Me (Claude): I see the instruction, but I still respond conversationally
               because SessionStart just adds context, doesn't trigger actions
```

**Verdict**: ❌ Adds instructions but doesn't enforce behavior

---

### PreToolUse Hook

**When**: After Claude decides on tools, before execution

**Idea**: Intercept tool calls and check if conversation contains "implement X"

**Why it fails**:
```
User: "implement issue #38"
Me: "I'll help! Let me read the issue first..." → decides to use Read tool
PreToolUse Hook: Fires with tool=Read, but too late!
                 User already engaged conversationally
                 Can't redirect to /auto-implement now
```

**Verdict**: ❌ Fires too late in the workflow

---

### PostToolUse Hook

**When**: After tool completes successfully

**Idea**: Track what tools were used, detect patterns

**Why it fails**:
```
User: "implement issue #38"
Me: Uses Read → Edit → Write tools
PostToolUse: Fires after each tool
             Can see pattern retroactively
             But work is already done!
```

**Verdict**: ❌ Too late, work already complete

---

### Stop Hook

**When**: After Claude's complete response

**Idea**: Review response and suggest correction

**Why it fails**:
```
User: "implement issue #38"
Me: Full conversational response with code
Stop Hook: "Hey, you should have used /auto-implement!"
           But response already delivered
```

**Verdict**: ❌ After the fact

---

## Creative Workarounds (That Don't Work)

### Workaround 1: SessionStart + Instructions

**Try**:
```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "echo 'IMPORTANT: When user says implement/add/create, ALWAYS respond with: I detected a feature request. Please use /auto-implement command.'"
      }]
    }]
  }
}
```

**Result**:
- ❌ I (Claude) see the instruction
- ❌ But I still respond naturally (instructions aren't commands)
- ❌ No enforcement

---

### Workaround 2: PreToolUse Blocker

**Try**:
```json
{
  "hooks": {
    "PreToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "check_if_feature_request.py && exit 1"
      }]
    }]
  }
}
```

**Idea**: Block ALL tools if feature request detected, force user to use command

**Result**:
- ❌ By the time PreToolUse fires, conversational response already started
- ❌ Blocking tools breaks the conversation awkwardly
- ❌ User gets confused: "Why can't Claude use tools?"

---

### Workaround 3: PostToolUse Reminder

**Try**:
```json
{
  "hooks": {
    "PostToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "echo '💡 Tip: Use /auto-implement for feature requests'"
      }]
    }]
  }
}
```

**Result**:
- ✅ Shows reminder after each tool
- ❌ But work already done
- ❌ Just adds noise

---

## The Hard Truth

**Only UserPromptSubmit can detect intent early enough.**

**Timeline**:
```
User types prompt
   ↓
UserPromptSubmit fires ← ONLY CHANCE to detect & redirect
   ↓
Claude processes prompt
   ↓
Claude decides on tools
   ↓
PreToolUse fires ← Too late, conversational response started
   ↓
Tools execute
   ↓
PostToolUse fires ← Too late, work done
   ↓
Claude completes response
   ↓
Stop fires ← Way too late
```

**UserPromptSubmit is the ONLY interception point before Claude commits to an approach.**

---

## What About Combining Hooks?

**Idea**: Use multiple hooks together?

**Example**:
```
SessionStart: Load "detect feature requests" instructions
UserPromptSubmit: Actually detect and block
PreToolUse: Verify we're using right approach
```

**Result**:
- ❌ Still depends on UserPromptSubmit working (bug #8810)
- ❌ Other hooks don't add reliability
- ❌ Just adds complexity

---

## Alternative Strategies (That DO Work)

### Strategy 1: Accept Manual Commands ✅

**Approach**: Just use `/auto-implement` directly

```
You: /auto-implement "implement issue #38"
```

**Pros**:
- ✅ 100% reliable
- ✅ Clear and explicit
- ✅ No hook bugs

**Cons**:
- ⏳ Manual typing

**Verdict**: ✅ **Recommended - this is what works**

---

### Strategy 2: Shell Alias ✅

**Approach**: Create shortcut in your shell

```bash
alias ai="echo '/auto-implement' | pbcopy && echo 'Command copied! Paste in Claude Code'"
```

**Pros**:
- ✅ Faster typing
- ✅ Still reliable

**Cons**:
- ⏳ Still manual step

**Verdict**: ✅ **Good compromise**

---

### Strategy 3: PreCommit Validation ✅

**Approach**: Don't detect intent, but validate AFTER implementation

```json
{
  "hooks": {
    "PreCommit": [{
      "hooks": [{
        "type": "command",
        "command": "python .claude/hooks/validate_project_alignment.py || exit 1"
      }]
    }]
  }
}
```

**Pros**:
- ✅ Catches mistakes before commit
- ✅ 100% reliable (PreCommit works)
- ✅ Blocks bad code

**Cons**:
- ⏳ Reactive (catches problems), not proactive (prevents them)

**Verdict**: ✅ **Use this for validation, not detection**

---

### Strategy 4: Wait for Bug Fix ⏰

**Approach**: Wait for UserPromptSubmit bug #8810 to be fixed

**Status**:
- Bug reported: Oct 2025
- Status: Open, unfixed
- ETA: Unknown

**Pros**:
- ✅ Would enable true auto-detection

**Cons**:
- ⏳ No timeline
- ⏳ Can't rely on it now

**Verdict**: ⏰ **Monitor, but don't wait**

---

## Recommendations

### For Auto-Orchestration

**DO**:
- ✅ Use `/auto-implement` command directly
- ✅ Create shell aliases for speed
- ✅ Document the workflow clearly

**DON'T**:
- ❌ Try to use PreToolUse/PostToolUse for detection
- ❌ Wait for UserPromptSubmit bug fix
- ❌ Over-engineer workarounds

---

### For Validation

**DO**:
- ✅ Use PreCommit hooks for validation
- ✅ Block commits that violate rules
- ✅ Auto-fix what you can

**DON'T**:
- ❌ Try to validate in SessionStart
- ❌ Use PostToolUse for enforcement (too late)

---

## Conclusion

**Question**: Are there other hooks to use apart from UserPromptSubmit?

**Answer**: **No reliable alternatives for intent detection.**

- UserPromptSubmit is the ONLY hook that fires early enough
- It's buggy (#8810), but no other hook can replace it
- Other hooks (PreToolUse, PostToolUse, Stop) fire too late
- SessionStart can't enforce behavior, only add context

**Best approach**: Accept manual `/auto-implement` command invocation.

**It's not as magical as auto-detection, but it's 100% reliable.**

---

## Updated Hook Strategy

**What to use each hook for**:

| Hook | Use For | Status |
|------|---------|--------|
| UserPromptSubmit | ❌ Auto-detection (buggy) | Wait for fix |
| PreCommit | ✅ Validation before commit | **Use this** |
| PostToolUse | ✅ Tracking/logging | **Use this** |
| SubagentStop | ✅ Agent completion logging | **Use this** |
| SessionStart | ✅ Loading context/instructions | Optional |
| PreToolUse | ⚠️ Tool approval (niche cases) | Rarely |
| Stop | ⚠️ Post-response cleanup | Rarely |
| SessionEnd | ⚠️ Cleanup/logging | Rarely |

**Focus on**: PreCommit (validation) + Commands (actions)

**Avoid**: Trying to make UserPromptSubmit work (buggy)

---

**Last Updated**: 2025-11-03 (after thorough hook analysis)
