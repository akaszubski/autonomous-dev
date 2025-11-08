# Marketplace User Experience - Current State & Fix

**Date**: 2025-11-08
**Issue**: Users installing from marketplace can't easily update or sync

---

## Current Understanding: How Plugin Loading Works

Based on investigation, here's how Claude Code loads plugins:

### Two Loading Locations

**1. Marketplace Installation** (global):
```
~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/
├── commands/
├── agents/
├── skills/
└── hooks/
```

**Status**: ✅ Claude Code appears to auto-load from this location
**How users get here**: `/plugin install autonomous-dev`

**2. Project Override** (local):
```
<project>/.claude/
├── commands/
├── agents/
├── skills/
└── hooks/
```

**Status**: ✅ Claude Code loads from here if present (overrides marketplace)
**How users get here**: Manual setup OR plugin developer workflow

---

## The Problem for Marketplace-Only Users

### Scenario 1: Fresh Install (Works!)

```bash
# User with no repo, just wants to use the plugin
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Full restart (Cmd+Q)
# ✅ Commands work! Claude Code loads from marketplace location
```

**Result**: Everything works because Claude Code auto-loads from `~/.claude/plugins/marketplaces/`.

---

### Scenario 2: Plugin Update (BROKEN!)

```bash
# User wants to update to latest version
/plugin update autonomous-dev
# Full restart (Cmd+Q)
# ❌ MAY NOT GET LATEST COMMANDS!
```

**Problem**:
1. `/plugin update` updates the marketplace location
2. But if user has project `.claude/` directory (from previous setup or manual config), it takes precedence
3. Old commands in project `.claude/` override new marketplace commands
4. User sees old behavior, thinks update failed

**Example**:
- User installed v3.6.0 which had `/sync-dev`
- Plugin created `.claude/commands/sync-dev.md`
- User updates to v3.7.0 which has unified `/sync`
- Marketplace has new `/sync` command
- But `.claude/commands/sync-dev.md` still exists and takes precedence
- `/sync` doesn't work, `/sync-dev` is outdated

---

### Scenario 3: Plugin Developer (Complex!)

```bash
# Developer working on plugin repo
cd autonomous-dev/
python plugins/autonomous-dev/hooks/sync_to_installed.py
# Full restart (Cmd+Q)
# ❌ Commands may not load!
```

**Problem**: Developer workflow requires 4-layer sync (as documented), but current script only does 2 layers.

---

## Root Cause Analysis

The plugin system has **TWO MODES** that conflict:

### Mode 1: Marketplace-Only (Ideal for Users)
```
~/.claude/plugins/marketplaces/autonomous-dev/  (Claude auto-loads)
```
**Pros**: Zero config, auto-updates work
**Cons**: Can't customize or override

### Mode 2: Project Override (Plugin Developers)
```
.claude/commands/  (overrides marketplace)
```
**Pros**: Test local changes without reinstalling
**Cons**: Prevents marketplace updates from applying

**Conflict**: Once a user has `.claude/` directory (from any source), marketplace updates are silently ignored!

---

## Proposed Solutions

### Solution 1: Remove Project Override (Simplest)

**For marketplace-only users**: Delete `.claude/` directory entirely

```bash
# Check if you have project overrides
ls -la .claude/commands/

# If yes, and you're NOT developing the plugin:
rm -rf .claude/commands/ .claude/agents/ .claude/skills/ .claude/hooks/

# Keep only:
# - .claude/PROJECT.md (project config)
# - .claude/CLAUDE.md (project instructions)
# - .claude/settings.json (user settings)

# Full restart (Cmd+Q)
# ✅ Now Claude loads from marketplace - updates work!
```

**When to use**: You're a user, not a plugin developer
**Pros**: Simple, marketplace updates work automatically
**Cons**: Can't customize commands

---

### Solution 2: Sync Script for Users (Recommended)

Create a `/sync` command that marketplace users can run to update their local overrides:

**Implementation**: Add to `commands/sync.md`:

```markdown
# Sync - Update Plugin from Marketplace

**For marketplace-only users**: Updates your local plugin files from the latest marketplace installation.

```bash
/sync --marketplace
```

This copies files from:
`~/.claude/plugins/marketplaces/autonomous-dev/`

To your project:
`.claude/commands/`, `.claude/agents/`, etc.

Then run a full restart (Cmd+Q).
```

**How it works**:
1. User runs `/plugin update autonomous-dev`
2. Full restart (Cmd+Q)
3. Run `/sync --marketplace` (copies marketplace → project)
4. Full restart again (Cmd+Q)
5. ✅ Latest commands now work!

**Pros**:
- Users can update easily
- Preserves project customizations if needed
- Simple 2-step process

**Cons**:
- Requires 2 restarts
- Users must remember to run `/sync`

---

### Solution 3: Post-Install Hook (Ideal)

Make Claude Code automatically sync marketplace → project after updates:

**Add to `plugin.json`**:
```json
{
  "hooks": {
    "post-install": "python hooks/post_install_sync.py",
    "post-update": "python hooks/post_install_sync.py"
  }
}
```

**`hooks/post_install_sync.py`**:
```python
"""Auto-sync marketplace files to project .claude/ after install/update"""

def sync_marketplace_to_project():
    marketplace_dir = find_marketplace_installation()
    project_claude = Path.cwd() / ".claude"

    if not project_claude.exists():
        # No project override - marketplace loading works, nothing to do
        return

    # Copy marketplace files to project override
    sync_dirs = ["commands", "agents", "skills", "hooks"]
    for dir_name in sync_dirs:
        source = marketplace_dir / dir_name
        target = project_claude / dir_name

        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)

    print("✅ Synced marketplace files to project .claude/")
    print("⚠️  FULL RESTART REQUIRED (Cmd+Q)")
```

**Pros**:
- Zero user action required
- Updates work automatically
- Best UX

**Cons**:
- Requires Claude Code to support post-install hooks
- Not sure if this is currently supported

---

### Solution 4: Marketplace-Only Mode (Long-term)

**Add setting to disable project overrides**:

```json
// .claude/settings.json
{
  "plugins": {
    "preferMarketplace": true  // Never load from project .claude/
  }
}
```

**Behavior**:
- Ignore `.claude/commands/` entirely
- Always load from marketplace
- Updates work automatically
- Restarts apply changes immediately

**Pros**:
- Perfect for users
- Zero maintenance
- Auto-updates work

**Cons**:
- Requires Claude Code core changes
- Can't test local customizations

---

## Immediate Action Plan

### For This Release (v3.7.0)

**1. Update `/sync` command** to support marketplace sync:
```bash
/sync --marketplace  # Copy marketplace → project .claude/
```

**2. Add to README.md**:
```markdown
## Updating the Plugin

After updating via `/plugin update autonomous-dev`:

1. Full restart (Cmd+Q, NOT /exit)
2. Run: `/sync --marketplace`
3. Full restart again (Cmd+Q)
4. Latest commands now available
```

**3. Add validation to `/health-check`**:
```bash
/health-check  # Should detect version mismatches

# Output:
# ⚠️  Version mismatch detected:
#     Marketplace: v3.7.0 (has /sync)
#     Project: v3.6.0 (has /sync-dev)
#
#     Run: /sync --marketplace
#     Then: Full restart (Cmd+Q)
```

---

### For Next Release (v3.8.0+)

**1. Implement post-install hook** (if Claude Code supports it)

**2. Create guided update command**:
```bash
/update-plugin  # Interactive guide

# Output:
# 🔄 Updating autonomous-dev plugin...
#
# Step 1: Update from marketplace
#   Run: /plugin update autonomous-dev
#   [Press Enter when done]
#
# Step 2: Restart Claude Code
#   Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
#   [Restart, then return here]
#
# Step 3: Sync files
#   /sync --marketplace
#
# Step 4: Restart again
#   Press Cmd+Q
#   [Done!]
```

**3. Add auto-detection**:
```bash
# On startup, check for version mismatch
# If detected, auto-prompt user:

⚠️  Plugin update available!
    Current: v3.6.0
    Latest: v3.7.0

    Run /update-plugin for guided update
```

---

## Testing Plan

### Test Case 1: Fresh Install (Marketplace-Only User)

```bash
# Clean environment
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
rm -rf .claude/

# Install
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Restart (Cmd+Q)

# Verify
/auto-implement  # Should work
/sync            # Should work
ls .claude/      # Should NOT exist (marketplace loading)
```

**Expected**: ✅ All commands work, no project override created

---

### Test Case 2: Update (Marketplace-Only User)

```bash
# Start with v3.6.0 installed
/plugin update autonomous-dev  # Update to v3.7.0
# Restart (Cmd+Q)

# If .claude/ exists:
/sync --marketplace  # Sync marketplace → project
# Restart (Cmd+Q)

# Verify
/sync  # Should work (not /sync-dev)
```

**Expected**: ✅ Latest commands available after sync

---

### Test Case 3: Developer Workflow

```bash
# Working on plugin
vim plugins/autonomous-dev/commands/new-feature.md
python plugins/autonomous-dev/hooks/sync_to_installed.py --all
# Restart (Cmd+Q)

# Verify
/new-feature  # Should work
ls .claude/commands/new-feature.md  # Should exist
```

**Expected**: ✅ Local changes immediately testable

---

## Recommendations

**Immediate (v3.7.0)**:
1. ✅ Implement `/sync --marketplace` mode
2. ✅ Add version mismatch detection to `/health-check`
3. ✅ Update documentation with update workflow

**Short-term (v3.8.0)**:
1. Create guided `/update-plugin` command
2. Add auto-detection of version mismatches
3. Implement orphan file cleanup

**Long-term (v4.0.0)**:
1. Research Claude Code post-install hook support
2. Propose "preferMarketplace" setting to Claude team
3. Investigate auto-update mechanisms

---

**Key Insight**: The root problem is that project `.claude/` overrides marketplace silently. Users don't know they have stale overrides. Solution: Detection + easy sync command.
