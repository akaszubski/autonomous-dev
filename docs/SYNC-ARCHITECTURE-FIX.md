# Sync Architecture Fix

**Date**: 2025-11-08
**Issue**: `/sync` command missing after multiple restarts despite file existing

---

## Root Cause

The sync infrastructure has a **critical architectural flaw**: it's a **4-layer sync chain**, but `sync_to_installed.py` only handles the first step.

### The Four-Layer Sync Chain

```
┌─────────────────────────────────────┐
│ Layer 1: Git Repository (dev)      │  ← Source of truth
│ plugins/autonomous-dev/commands/    │
└──────────────┬──────────────────────┘
               │ sync_to_installed.py
               ↓
┌─────────────────────────────────────┐
│ Layer 2: Marketplace Install        │  ← Where plugin is installed
│ ~/.claude/plugins/marketplaces/...  │
└──────────────┬──────────────────────┘
               │ ❌ MISSING SYNC STEP!
               ↓
┌─────────────────────────────────────┐
│ Layer 3: Active Commands            │  ← What Claude Code loads
│ .claude/commands/                   │
└──────────────┬──────────────────────┘
               │ (Optional override)
               ↓
┌─────────────────────────────────────┐
│ Layer 4: Project Plugin Override    │  ← Testing local changes
│ plugins/autonomous-dev/             │  (when working on plugin)
└─────────────────────────────────────┘
```

**The Critical Gap**:
- ✅ Layer 1 → Layer 2: `sync_to_installed.py` works
- ❌ Layer 2 → Layer 3: **NO AUTOMATIC SYNC EXISTS**
- Layer 3 → Layer 4: Handled by Claude Code plugin system

This means users can run `sync_to_installed.py` successfully, see "150 files synced", but **the command still doesn't work** because Layer 3 (`.claude/commands/`) never gets updated.

---

## How Commands Actually Load

Claude Code loads slash commands from:
- `.claude/commands/*.md` - User's active commands
- `~/.claude/plugins/marketplaces/*/commands/*.md` - Installed marketplace plugins (maybe?)

The second location appears to NOT be automatically loaded, which is why commands don't appear after running `sync_to_installed.py`.

---

## Current Workaround

**Manual 3-step process**:

```bash
# Step 1: Sync to marketplace
python plugins/autonomous-dev/hooks/sync_to_installed.py

# Step 2: Copy to active location
cp ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/commands/sync.md .claude/commands/sync.md

# Step 3: FULL RESTART (Cmd+Q, not /exit)
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
# Wait 5 seconds
# Restart Claude Code
```

---

## Long-Term Fix: Complete Multi-Layer Sync

### Proposed Solution: Extend sync_to_installed.py

Modify `sync_to_installed.py` to handle ALL 4 layers of the sync chain:

```python
def sync_plugin_complete(source_dir: Path, target_dir: Path, dry_run: bool = False):
    """Complete multi-layer sync: repo → marketplace → active → project"""

    print("🔄 Multi-Layer Sync:")
    print(f"   Layer 1 (Source): {source_dir}")
    print(f"   Layer 2 (Marketplace): {target_dir}")
    print(f"   Layer 3 (Active): ~/.claude/commands/")
    print(f"   Layer 4 (Project): .claude/ (if exists)")
    print()

    # LAYER 1 → LAYER 2: Existing sync to marketplace
    sync_to_marketplace(source_dir, target_dir, dry_run)

    # LAYER 2 → LAYER 3: NEW - Sync to active commands
    sync_to_active_commands(source_dir, dry_run)

    # LAYER 2 → LAYER 4: NEW - Sync to project override (if working on plugin)
    sync_to_project_override(source_dir, dry_run)

    print()
    print("✅ Multi-layer sync complete!")

def sync_to_active_commands(source_dir: Path, dry_run: bool = False):
    """Sync commands to ~/.claude/commands/ (where Claude Code loads from)"""
    active_commands_dir = Path.home() / ".claude" / "commands"

    if not active_commands_dir.exists():
        print("⚠️  .claude/commands/ not found - skipping Layer 3 sync")
        return

    print()
    print("📁 [Layer 2 → Layer 3] Syncing to active commands...")

    source_commands = source_dir / "commands"
    synced_count = 0

    for cmd_file in source_commands.glob("*.md"):
        # Skip archived commands
        if cmd_file.parent.name == "archived":
            continue

        target_file = active_commands_dir / cmd_file.name

        if dry_run:
            print(f"   [DRY RUN] Would sync: {cmd_file.name}")
        else:
            shutil.copy2(cmd_file, target_file)
            print(f"   ✅ {cmd_file.name}")
            synced_count += 1

    if not dry_run:
        print(f"✅ Synced {synced_count} commands to .claude/commands/")

def sync_to_project_override(source_dir: Path, dry_run: bool = False):
    """Sync to project's .claude/ directory (for plugin developers)"""
    # Find project .claude directory (where we're developing)
    project_claude_dir = source_dir.parent.parent / ".claude"

    if not project_claude_dir.exists():
        print("⚠️  Project .claude/ not found - skipping Layer 4 sync")
        return

    print()
    print("📁 [Layer 2 → Layer 4] Syncing to project override...")

    # Sync commands, agents, hooks, etc. to project .claude/
    sync_dirs = ["commands", "agents", "hooks", "skills"]
    synced_count = 0

    for dir_name in sync_dirs:
        source_subdir = source_dir / dir_name
        target_subdir = project_claude_dir / dir_name

        if not source_subdir.exists():
            continue

        if dry_run:
            print(f"   [DRY RUN] Would sync: {dir_name}/")
            continue

        # Copy directory
        if target_subdir.exists():
            shutil.rmtree(target_subdir)
        shutil.copytree(source_subdir, target_subdir)

        file_count = sum(1 for _ in target_subdir.rglob("*") if _.is_file())
        synced_count += file_count
        print(f"   ✅ {dir_name}/ ({file_count} files)")

    if not dry_run:
        print(f"✅ Synced {synced_count} items to project .claude/")
```

### Benefits of Multi-Layer Sync

1. **One command does everything**: `python hooks/sync_to_installed.py`
2. **Automatic propagation**: Changes flow through all 4 layers
3. **Idempotent**: Safe to run multiple times
4. **Clear reporting**: Shows what's synced where
5. **Dry-run support**: `--dry-run` to preview changes

### Sync Flow After Fix

```bash
# Developer workflow (working on plugin)
vim plugins/autonomous-dev/commands/new-feature.md
python plugins/autonomous-dev/hooks/sync_to_installed.py

# Output:
# 🔄 Multi-Layer Sync:
#    Layer 1 (Source): plugins/autonomous-dev/
#    Layer 2 (Marketplace): ~/.claude/plugins/marketplaces/...
#    Layer 3 (Active): ~/.claude/commands/
#    Layer 4 (Project): .claude/ (if exists)
#
# ✅ Synced to marketplace (150 files)
# ✅ Synced to active commands (18 files)
# ✅ Synced to project override (52 files)
# ✅ Multi-layer sync complete!

# Then: Full restart (Cmd+Q, not /exit)
# Command immediately available: /new-feature
```

---

## Immediate Action Required

1. **Fix sync_to_installed.py** to copy to both locations
2. **Update documentation** to explain the three-layer architecture
3. **Add validation** to check `.claude/commands/` after sync
4. **Create command** to verify command files are in correct location

---

## Testing the Fix

After implementing the fix:

```bash
# Step 1: Create new command file
echo "Test command" > plugins/autonomous-dev/commands/test-sync.md

# Step 2: Run sync
python plugins/autonomous-dev/hooks/sync_to_installed.py

# Step 3: Verify both locations
ls -la ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/commands/test-sync.md
ls -la .claude/commands/test-sync.md

# Both should exist!

# Step 4: Full restart
# Press Cmd+Q, wait, restart

# Step 5: Test command
/test-sync  # Should work!

# Step 6: Clean up
rm plugins/autonomous-dev/commands/test-sync.md
python plugins/autonomous-dev/hooks/sync_to_installed.py  # Sync deletion
```

---

## Why This Was Hard to Debug

1. **Silent failure**: Commands just don't appear, no error message
2. **Multiple locations**: Three different paths for the same file
3. **Caching**: `/exit` doesn't reload commands, only full restart works
4. **Incomplete sync**: `sync_to_installed.py` works but doesn't sync to active location

---

## Lessons Learned

1. **Command loading requires `.claude/commands/`**: Marketplace location is not enough
2. **Full restart is mandatory**: Even after fixing files, Cmd+Q required
3. **Sync architecture needs rethinking**: Current approach has too many layers
4. **Validation is critical**: Need automated checks for file locations

---

**Recommendation**: Implement Option 1 (extend sync_to_installed.py) ASAP to prevent this issue from recurring.
