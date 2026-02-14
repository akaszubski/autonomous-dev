## Summary

The `/sync --plugin-dev` command doesn't reliably copy files from `plugins/autonomous-dev/` to `.claude/`. Files remain stale after sync.

## Root Cause

The `/sync` command is a markdown file that Claude interprets. Claude reads the instructions and implements its own sync behavior instead of executing the actual Python `sync_dispatcher.py` code.

**What happens**:
1. User runs `/sync` (auto-detects `--plugin-dev` mode)
2. Claude reads `sync.md` markdown instructions
3. Claude interprets and implements sync behavior ad-hoc
4. Files may not be copied correctly

**What should happen**:
1. User runs `/sync`
2. Command explicitly executes `sync_dispatcher.py`
3. Python code handles file discovery and copying
4. Consistent, reliable sync every time

## Evidence

After editing `plugins/autonomous-dev/commands/sync.md` and running `/sync`:

- Source file (updated): `plugins/autonomous-dev/commands/sync.md` has new description
- Destination file (NOT updated): `.claude/commands/sync.md` still has old description

## Recommended Fix

1. **Add CLI wrapper to sync_dispatcher.py** with argparse for `--plugin-dev`, `--github`, etc.

2. **Update /sync command to explicitly run Python script** instead of relying on Claude interpretation

3. **Add verification step** - after sync, verify file count matches source and show diff of what changed

## Impact

- **Severity**: High - core workflow broken
- **Affected**: All plugin developers using `/sync --plugin-dev`
- **Workaround**: Manually copy files with `cp`

## Broader Impact

This issue affects the entire installation/update pipeline:

1. **install.sh** - Bootstrap installation may have similar issues
2. **/sync --marketplace** - User updates may not copy files correctly
3. **/sync --github** - GitHub fetch may not work as expected
4. **Plugin updates** - Marketplace updates rely on consistent file operations

All file copy operations should use the Python libraries (`sync_dispatcher.py`, `file_discovery.py`, `copy_system.py`) and NOT rely on Claude interpretation.

## Related

- Part of installation/update script reliability improvements
- Similar pattern needed for other commands that should run Python scripts
- Audit all slash commands that perform file operations
