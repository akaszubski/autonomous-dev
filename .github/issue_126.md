## Summary

The installer/updater doesn't clean up old/archived commands when the command structure changes. This causes stale commands to remain in `.claude/commands/` and appear in Claude Code's command list.

## Problem

When Issue #121 simplified commands from 20 to 9:
- Archived commands were moved to `plugins/autonomous-dev/commands/archive/`
- But `.claude/commands/` wasn't cleaned up
- Result: 21 commands appeared in Claude Code instead of 9

## Current Workaround

Manually move files:
```bash
cd .claude/commands
mkdir -p archive
mv align-claude.md align-project.md align-project-retrofit.md implement.md plan.md research.md review.md security-scan.md test-feature.md update-docs.md batch-implement.md update-plugin.md archive/
```

## Expected Behavior

The installer/updater should:
1. Check which commands are in `plugins/autonomous-dev/commands/` (excluding archive/)
2. Remove any commands from `.claude/commands/` that don't exist in source
3. OR: Completely replace `.claude/commands/` with source (backup user customizations first)

## Acceptance Criteria

- [ ] Fresh install only copies active commands (not archived)
- [ ] Update removes stale commands from `.claude/commands/`
- [ ] User customizations in `.claude/commands/` are preserved (if any)
- [ ] Clear messaging when commands are removed

## Related

- #121 - Command simplification (root cause)
- #125 - Doc alignment automation
