# The Bootstrap Paradox: Why autonomous-dev Can't Be Marketplace-Only

**TL;DR**: autonomous-dev is a development system, not a simple plugin. It requires global infrastructure (`~/.claude/hooks/`, `~/.claude/lib/`, `~/.claude/settings.json`) that the marketplace can't configure. That's why `install.sh` exists.

---

## The Problem

The Claude Code marketplace is designed for simple plugins:
- Download files to project's `.claude/` directory
- No global system modifications
- No complex dependency chains
- Works in isolation

**autonomous-dev requires global infrastructure:**

1. **Global Hooks** (`~/.claude/hooks/`)
   - `pre_tool_use.py` - MCP security validation and auto-approval
   - `auto_format.py` - Code formatting enforcement
   - Must run for ALL projects, not just this one

2. **Global Libraries** (`~/.claude/lib/`)
   - `mcp_permission_validator.py` - Security validation
   - `auto_approve_policy.json` - Permission policies
   - Python dependencies shared across projects

3. **Global Settings** (`~/.claude/settings.json`)
   - Bash tool permission patterns
   - Timeout configurations
   - Hook lifecycle mappings

**The marketplace can download files, but it CANNOT:**
- Create directories in `~/.claude/`
- Modify `~/.claude/settings.json`
- Install Python dependencies globally
- Configure global hooks for all projects

**Result**: If you install via marketplace alone, you get the plugin files but none of the infrastructure. Commands fail, hooks don't run, and the system doesn't work.

---

## The Solution: Two-Phase Bootstrap

We solve this with a **two-phase install architecture** (Issue #132):

### Phase 1: Bootstrap Script (`install.sh`)

**What it does:**
```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

1. **Downloads all plugin files** to `~/.autonomous-dev-staging/` (temporary location)
2. **Creates and populates global infrastructure:**
   - `~/.claude/hooks/` directory with 48 required hooks
   - `~/.claude/lib/` directory with 66 Python libraries
   - `~/.claude/settings.json` with correct permission patterns and hook configurations
3. **Installs all plugin components** to `.claude/`:
   - Commands (7) → `.claude/commands/`
   - Agents (22) → `.claude/agents/`
   - Scripts (11) → `.claude/scripts/`
   - Config (6) → `.claude/config/`
   - Templates (11) → `.claude/templates/`
4. **Non-blocking installation:** Each component installs independently; missing components don't block workflow
5. **Prompts you to restart Claude Code**

**Why this works:** Bash script runs with your user permissions, can create directories and modify files anywhere in your home directory. Single-phase installation means all commands/agents are available immediately after restart.

### Phase 2 (Optional): Setup Wizard (`/setup` command)

**What it does:**
```bash
/setup
```

1. **Detects installation type:**
   - FRESH: No `.claude/` directory exists (or incomplete from install.sh)
   - BROWNFIELD: Existing `.claude/` directory with customizations
   - UPGRADE: Existing autonomous-dev installation

2. **Intelligent file installation:**
   - Copies agents, commands, skills from staging (if missing)
   - Preserves existing PROJECT.md, CLAUDE.md, custom settings
   - Updates only plugin files that are missing or outdated

3. **Guides you through setup** (if FRESH):
   - PROJECT.md creation (defines your goals and constraints)
   - GitHub integration setup (optional)
   - MCP server configuration (optional)

**Why this works:** Claude Code has full context of your project, can make intelligent decisions about what to preserve vs update. Most users won't need this after install.sh completes successfully.

---

## Architecture Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ User runs:                                                  │
│ bash <(curl -sSL .../install.sh)                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ install.sh (Bootstrap Script - Phase 1)                   │
├─────────────────────────────────────────────────────────────┤
│ 1. Download plugin files → ~/.autonomous-dev-staging/      │
│ 2. Create global infrastructure:                           │
│    - ~/.claude/hooks/ (48 hooks)                           │
│    - ~/.claude/lib/ (66 Python libraries)                  │
│    - ~/.claude/settings.json (permissions, hooks)          │
│ 3. Install all plugin components → .claude/:              │
│    - .claude/commands/ (7 commands)                        │
│    - .claude/agents/ (22 agents)                           │
│    - .claude/scripts/ (11 scripts)                         │
│    - .claude/config/ (6 config files)                      │
│    - .claude/templates/ (7 templates)                      │
│ 4. Non-blocking: Each component installs independently      │
│ 5. Prompt: "Restart Claude Code to load all commands"      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ User restarts Claude Code                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ All 7 commands and 22 agents are NOW available!            │
├─────────────────────────────────────────────────────────────┤
│ Ready to use: /implement "your feature"              │
│ (optional: /setup for PROJECT.md creation)                │
└─────────────────────────────────────────────────────────────┘
```

**Changes in v3.42.0+ (Issue #132):**
- install.sh now installs ALL plugin components (not just /setup)
- Single-phase installation (no need to run /setup after restart)
- /setup remains available for PROJECT.md creation and advanced setup
- Non-blocking installation: Missing components don't break workflow

---

## Why the Marketplace Can't Do This

The Claude Code marketplace is designed with intentional limitations for security and simplicity:

1. **Sandboxed to project directory**
   - Can only modify files in current project's `.claude/`
   - Cannot access `~/.claude/` (global configuration)
   - Prevents plugins from modifying system-wide settings

2. **No script execution**
   - Can download files, but can't run installation scripts
   - No `pip install`, no system commands
   - Prevents malicious plugins from executing arbitrary code

3. **No dependency installation**
   - Can't install Python packages globally
   - Can't modify `~/.claude/lib/` directory
   - Each plugin must be self-contained

4. **No settings modification**
   - Can't update `~/.claude/settings.json`
   - Can't add global hook configurations
   - Prevents plugins from breaking other plugins

**These are good security practices for most plugins.** But autonomous-dev is fundamentally different — it's a development system that needs to work across all your projects, not just one.

---

## The Hybrid Approach

**Best of both worlds:**

1. **Primary install: `install.sh`** (recommended)
   - Full functionality
   - Global infrastructure configured
   - Works for all projects

2. **Supplemental: Marketplace**
   - Easy plugin updates
   - Version browsing
   - Change history

**Workflow:**
```bash
# First-time install (required)
bash <(curl -sSL .../install.sh)
# Restart Claude Code
/setup

# Later: Update via marketplace (optional)
# Marketplace updates plugin files in .claude/
# Global infrastructure (~/.claude/) stays intact
```

---

## Step-by-Step Workflow

### First-Time Installation

1. **Run bootstrap script:**
   ```bash
   bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
   ```
   - Takes 30-60 seconds
   - Downloads all plugin files to `~/.autonomous-dev-staging/`
   - Creates global infrastructure (hooks, libs, settings)
   - Installs all plugin components (commands, agents, scripts, config, templates)
   - Reports installation success and any warnings

2. **Restart Claude Code:**
   ```bash
   # Mac: Cmd+Q
   # Linux/Windows: Ctrl+Q
   ```
   - CRITICAL: Must fully quit (not just `/exit`)
   - Allows Claude Code to load new commands, agents, hooks, and settings

3. **Start using immediately:**
   ```bash
   /implement "your feature"
   ```
   - All 7 commands and 22 agents are now available
   - No additional setup required (install.sh configured everything)

4. **Optional - Create PROJECT.md:**
   ```bash
   /setup
   ```
   - Creates `.claude/PROJECT.md` with your goals and constraints
   - Sets up GitHub integration (optional)
   - Configures MCP server (optional)
   - Only needed if you want to customize project settings

### Updating Existing Installation

**Option 1: Built-in update command (recommended)**
```bash
/update-plugin
# Interactive wizard with backup and rollback
# Restart Claude Code
```

**Option 2: Marketplace**
```bash
# Browse marketplace in Claude Code
# Click "Update" on autonomous-dev
# Restart Claude Code
```

**Option 3: Re-run install.sh**
```bash
bash <(curl -sSL .../install.sh)
# Restart Claude Code
/setup
```

All three methods preserve your customizations (PROJECT.md, CLAUDE.md, settings.local.json).

---

## Existing Installation Scenarios

### If you have existing `.claude/` files

**The setup wizard detects this as BROWNFIELD** and:
- Preserves your PROJECT.md, CLAUDE.md, custom settings
- Updates only plugin files (agents, commands, skills)
- Asks before overwriting any customizations
- Creates backups before making changes

### If you have an older autonomous-dev version

**The setup wizard detects this as UPGRADE** and:
- Compares versions (staging vs installed)
- Updates to newer version if available
- Preserves your PROJECT.md goals and constraints
- Migrates settings to new format if needed
- Creates backup of old version

### If you have nothing (fresh project)

**The setup wizard detects this as FRESH** and:
- Copies all plugin files from staging
- Guides you through PROJECT.md creation
- Sets up GitHub integration (optional)
- Configures MCP server (optional)
- Explains next steps

---

## Common Questions

**Q: Can I skip install.sh and just use the marketplace?**

A: No. You'll get the plugin files but none of the global infrastructure. Commands will fail, hooks won't run, and the system won't work.

**Q: Why not make autonomous-dev work without global infrastructure?**

A: That would break core functionality:
- Auto-approval needs to work in ALL projects (not just this one)
- Security validation must be global (shared policies across projects)
- Bash tool permissions must be consistent everywhere

**Q: Can I use the marketplace for updates?**

A: Yes! After initial install via `install.sh`, you can update via:
1. Marketplace (easy)
2. `/update-plugin` command (recommended, has backup/rollback)
3. Re-running `install.sh` (works but unnecessary)

**Q: What if I move my project to another machine?**

A: Run `install.sh` again on the new machine. It will:
1. Set up global infrastructure on new machine
2. Detect existing `.claude/` directory (BROWNFIELD)
3. Preserve your customizations
4. Update only plugin files

**Q: Is this a security risk?**

A: No more than any Bash script:
- You review the script before running (it's on GitHub)
- Runs with your user permissions (no sudo)
- Creates files in your home directory only
- No external dependencies or downloads during execution
- All files downloaded over HTTPS with TLS 1.2+

**Q: Why is this so complicated?**

A: It's not complicated for you — it's just one command. The complexity is in making the installation smart enough to handle:
- Fresh installs
- Brownfield projects
- Version upgrades
- Preserving customizations
- Working across multiple machines

The two-phase design makes this invisible to users.

---

## Related Documentation

- [README.md](../README.md#install-options) - Install options and quick start
- [CLAUDE.md](../CLAUDE.md#installation-bootstrap-first) - Bootstrap-first installation section
- [PROJECT.md](../.claude/PROJECT.md) - Distribution strategy
- [install.sh](../install.sh) - Bootstrap script source code
- [TROUBLESHOOTING.md](../plugins/autonomous-dev/docs/TROUBLESHOOTING.md) - Common installation issues

---

**Last Updated**: 2025-12-13
**Version**: v3.41.0
