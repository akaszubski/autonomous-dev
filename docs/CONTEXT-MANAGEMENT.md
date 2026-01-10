# Context Management

**CRITICAL**: Proper context management is essential for scaling to 100+ features without system failure.

---

## Why This Matters

- **Without clearing**: Context bloats to 50K+ tokens after 3-4 features → System fails
- **With clearing**: Context stays under 8K tokens → Works for 100+ features

---

## After Each Feature: Clear Context

```bash
/clear
```

**What this does**: Clears conversation (not files!), resets context budget, maintains performance

**When to clear**:
- After each feature completes (recommended for optimal performance)
- Before starting unrelated feature
- If responses feel slow

---

## Session Files Strategy

Agents log to `docs/sessions/` instead of context:

```bash
# Log action (works from any directory, including user projects)
python plugins/autonomous-dev/scripts/session_tracker.py agent_name "message"

# View latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

**Result**: Context stays small (200 tokens vs 5,000+ tokens)

---

## Portable Library-Based Design

**Issue #79 (v3.28.0+)** moved session tracking to portable library-based design:

**Core Libraries**:
- `plugins/autonomous-dev/lib/path_utils.py` (section 15) - Dynamic project root detection
- `plugins/autonomous-dev/lib/validation.py` (section 16) - Security validation for paths
- `plugins/autonomous-dev/lib/session_tracker.py` - Core logging library (v3.28.0+, Issue #79)
- `plugins/autonomous-dev/lib/agent_tracker.py` (section 24) - Agent checkpoint tracking with `save_agent_checkpoint()` class method (NEW v3.36.0)

**CLI Wrappers**:
- `plugins/autonomous-dev/scripts/session_tracker.py` - CLI wrapper (current location)
- `scripts/session_tracker.py` - DEPRECATED (removed v4.0.0), delegates to lib version

**How It Works**:
- Works from any directory (user projects, subdirectories) via `path_utils.get_session_dir()` and `AgentTracker.save_agent_checkpoint()`
- See `docs/LIBRARIES.md` (sections 15, 16, 24, 25) and GitHub Issue #79 for complete details

---

## Agent Checkpoint Tracking (v3.36.0)

Added `AgentTracker.save_agent_checkpoint()` class method for agent convenience:

**Features**:
- Convenience method for agents to save checkpoints without managing instances
- Solves dogfooding bug where hardcoded paths caused 7+ hour stalls
- Portable path detection works from any directory
- Graceful degradation in user projects (returns False, doesn't block workflow)
- No subprocess calls (uses Python imports instead)

**See**: `docs/DEVELOPMENT.md` Scenario 2.5 for integration pattern

---

## /implement Checkpoint Fixes (Issue #85, v3.30.0+)

Fixed `/implement` checkpoints to use portable path detection:

**Changes**:
- CHECKPOINT 1 (line 109) and CHECKPOINT 4.1 (line 390) replaced hardcoded paths with dynamic detection
- Same portable path detection strategy as tracking infrastructure (path_utils and fallback)
- Works from any directory on any machine (not just developer's path)

**See**: `plugins/autonomous-dev/commands/implement.md` for checkpoint implementation details

---

## Optional Checkpoint Verification (Issue #82, v3.33.0+)

Made checkpoint verification optional with graceful degradation:

**Behavior**:
- **User projects**: AgentTracker unavailable → silent skip with informational message (ℹ️)
- **Dev repo**: AgentTracker available → full verification with efficiency metrics (✅/❌)
- **Broken scripts**: Never blocks workflow, always shows clear warning (⚠️) and continues

**Benefits**:
- Enables `/implement` to work anywhere without requiring plugins/ directory structure
- Checkpoints work in both user projects and autonomous-dev repo

**See**: `plugins/autonomous-dev/commands/implement.md` for graceful degradation pattern

---

## Best Practices

1. **Clear after features** - Run `/clear` after each feature completes
2. **Use session files** - Log to files instead of conversation context
3. **Monitor context** - If responses slow down, clear context immediately
4. **Scale confidently** - With proper clearing, handle 100+ features per session
