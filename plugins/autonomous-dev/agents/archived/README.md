# Archived Agents

This directory contains agents that have been deprecated or replaced.

## orchestrator.md

**Archived**: 2025-11-03
**Reason**: Architectural issue - "orchestrator agent" was actually Claude coordinating Claude

**Problem**:
- When Task tool invoked "orchestrator", it loaded orchestrator.md as Claude's system prompt
- But it was still the same Claude instance making decisions
- Created logical impossibility: "Claude, invoke yourself to tell yourself to invoke agents"
- Result: Claude could still make adaptive decisions to skip agents

**Solution**:
- Moved all coordination logic to `commands/auto-implement.md`
- Made Claude's coordination role explicit
- No separate "orchestrator agent" - just coordination instructions directly to Claude
- Same checkpoints, simpler architecture, more honest design

**Migration**:
- Old: `/auto-implement` → invokes orchestrator agent → orchestrator coordinates
- New: `/auto-implement` → Claude reads coordination steps → Claude coordinates directly

**Replacement**: See `plugins/autonomous-dev/commands/auto-implement.md` for the new coordination workflow

**Files affected by this change**:
- `commands/auto-implement.md` - Now contains all coordination logic
- `hooks/enforce_pipeline_complete.py` - New enforcement hook
- All documentation updated to remove "orchestrator agent" references

**This file is kept for historical reference and in case we need to restore parts of the logic.**
