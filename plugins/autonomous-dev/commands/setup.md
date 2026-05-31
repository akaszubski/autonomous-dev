---
name: setup
description: Interactive setup wizard - analyzes tech stack, generates PROJECT.md, configures hooks
argument-hint: "[--project-dir <path>]"
allowed-tools: [Read, Write, Bash, Grep, Glob]
disable-model-invocation: true
user-invocable: true
---

# /setup - Project Initialization Wizard

**Purpose**: Initialize autonomous-dev in a project with intelligent PROJECT.md generation.

**Core Value**: Analyzes your codebase and generates comprehensive PROJECT.md (brownfield) or guides you through creation (greenfield).

---

## Quick Start

```bash
/setup
```

**Time**: 2-5 minutes
**Interactive**: Yes (guides you through choices)

---

## Implementation

### Step 1: Install Plugin Files

```bash
# Delegate to sync_dispatcher for reliable file installation
echo "Installing plugin files..."
python3 .claude/lib/sync_dispatcher.py --github

# Fallback if .claude/lib doesn't exist yet (fresh install)
if [ $? -ne 0 ]; then
  # Try from plugins/ directory (dev environment)
  python3 plugins/autonomous-dev/lib/sync_dispatcher.py --github
fi
```

**What this does**:
- Downloads latest files from GitHub
- Copies to `.claude/` directory
- Validates all paths for security
- Non-destructive (preserves existing PROJECT.md, .env)

**If sync fails**: Show error and suggest manual sync with `/sync --github`

---

### Step 1.5: Create .env Configuration

After plugin files are installed, create `.env` from template:

```bash
# Check if .env already exists
if [ ! -f ".env" ]; then
  # Copy from .env.example if it exists (standard convention)
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  else
    # Create minimal .env with essential settings
    cat > .env << 'ENVEOF'
# autonomous-dev Environment Configuration
# See: https://github.com/akaszubski/autonomous-dev#environment-setup

# =============================================================================
# API KEYS (REQUIRED - fill these in!)
# =============================================================================
GITHUB_TOKEN=ghp_your_token_here
# ANTHROPIC_API_KEY=sk-ant-your_key_here

# =============================================================================
# GIT AUTOMATION (enabled by default)
# =============================================================================
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true
AUTO_GIT_PR=false

# =============================================================================
# TOOL AUTO-APPROVAL (reduces permission prompts)
# =============================================================================
MCP_AUTO_APPROVE=true

# =============================================================================
# BATCH PROCESSING
# =============================================================================
BATCH_RETRY_ENABLED=true
ENVEOF
    echo "Created .env with default settings"
  fi
fi

# Ensure .env is in .gitignore
if [ -f ".gitignore" ]; then
  if ! grep -q "^\.env$" .gitignore; then
    echo ".env" >> .gitignore
    echo "Added .env to .gitignore"
  fi
else
  echo ".env" > .gitignore
  echo "Created .gitignore with .env"
fi
```

**After creating .env, ALWAYS prompt the user:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  ACTION REQUIRED: Configure your .env file
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A .env file has been created with default settings. You MUST update the
API keys and tokens for full functionality.

Required (at minimum):
  GITHUB_TOKEN=ghp_your_token_here
    → Create at: https://github.com/settings/tokens
    → Scopes needed: repo, read:org

Optional but recommended:
  ANTHROPIC_API_KEY=sk-ant-your_key_here
    → Get from: https://console.anthropic.com/
    → Enables: GenAI security scanning, test generation, doc fixes

Key settings already enabled:
  AUTO_GIT_ENABLED=true     (auto-commit after /implement)
  AUTO_GIT_PUSH=true        (auto-push commits)
  MCP_AUTO_APPROVE=true     (reduce permission prompts)
  BATCH_RETRY_ENABLED=true  (retry transient failures)

Edit .env now:
  vim .env
  # or
  code .env

See all options: cat .env  (file is fully documented)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Wait for user confirmation before continuing to Step 2.**

---

### Step 1.6: Initialize per-repo .mcp.json (Issue #948)

**Why**: Per-repo `.mcp.json` is the recommended default. MCP servers configured globally in `~/.claude/settings.json` mcpServers inject tool definitions into every prompt — even when irrelevant — costing 5-10K tokens per turn for a typical 5-server setup. Per-repo `.mcp.json` scopes servers to where they're actually used.

```bash
# Step 1.6a: Bootstrap .mcp.json from a reference template if absent
if [ -f ".mcp.json" ]; then
  echo "Preserving existing .mcp.json"
else
  TEMPLATE_PATH=""
  for candidate in ".claude/.mcp/config.template.json" ".mcp/config.template.json" "plugins/autonomous-dev/.mcp/config.template.json"; do
    if [ -f "$candidate" ]; then TEMPLATE_PATH="$candidate"; break; fi
  done
  if [ -n "$TEMPLATE_PATH" ]; then
    cp "$TEMPLATE_PATH" .mcp.json
    echo "Created .mcp.json from $TEMPLATE_PATH"
  else
    echo '{"mcpServers": {}}' > .mcp.json
    echo "Created .mcp.json placeholder (no template found)"
  fi
fi

# Step 1.6b: Auto-gitignore .mcp.json if it contains inline secrets
HELPER="plugins/autonomous-dev/scripts/migrate_mcp_to_repo.py"
if [ ! -f "$HELPER" ]; then
  HELPER=".claude/scripts/migrate_mcp_to_repo.py"
fi
HAS_SECRETS="False"
if [ -f "$HELPER" ]; then
  HAS_SECRETS=$(python3 "$HELPER" --check-only --repo . 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('secrets_detected', False))" 2>/dev/null \
    || echo "False")
fi

if [ "$HAS_SECRETS" = "True" ]; then
  if [ -f ".gitignore" ]; then
    if ! grep -q '^\.mcp\.json$' .gitignore; then
      echo ".mcp.json" >> .gitignore
      echo "Added .mcp.json to .gitignore (contains inline secrets)"
    fi
  else
    echo ".mcp.json" > .gitignore
    echo "Created .gitignore with .mcp.json"
  fi
fi
```

**After creating `.mcp.json`, surface this note to the user:**

```
Created .mcp.json with default servers. Edit to add/remove. See
docs/MCP-ARCHITECTURE.md ("Per-repo vs Global Configuration") for the
token-bleed cost of global mcpServers and the recommended migration path.

If you have servers in ~/.claude/settings.json mcpServers that you'd
rather scope to a single repo, run:

  bash install.sh --migrate-mcp-to-repo $(pwd) --server <name>
  # or:
  python3 plugins/autonomous-dev/scripts/migrate_mcp_to_repo.py \
    --server <name> --repo $(pwd)
```

---

### Step 1.7: Claude Code version + compound-bash compatibility check

Check whether the installed Claude Code version requires per-prefix Bash allow entries and
warn the user if their global settings are missing them.

```bash
CC_VERSION=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
if [ -n "$CC_VERSION" ]; then
  python3 -c "
import sys, json
from pathlib import Path

version_str = '$CC_VERSION'
parts = version_str.split('.')
try:
    v = tuple(int(x) for x in parts[:3])
except ValueError:
    sys.exit(0)

if v < (2, 1, 77):
    sys.exit(0)

settings_path = Path.home() / '.claude' / 'settings.json'
if not settings_path.exists():
    sys.exit(0)

try:
    data = json.loads(settings_path.read_text())
except (json.JSONDecodeError, OSError):
    sys.exit(0)

allow_list = data.get('permissions', {}).get('allow', [])
has_bare_bash = 'Bash' in allow_list
has_prefix_bash = any(e.startswith('Bash(') for e in allow_list)

if has_bare_bash and not has_prefix_bash:
    print()
    print('WARNING: Claude Code $CC_VERSION detected — compound-bash auto-approve changed.')
    print()
    print('  Your ~/.claude/settings.json has a bare \"Bash\" allow entry but no per-prefix')
    print('  Bash(<tool>:*) entries. As of CC 2.1.77, compound commands like')
    print('  \"git status && echo done\" are split before matching, so each subcommand must')
    print('  match its own allow entry. Without per-prefix entries you will see a permission')
    print('  prompt on every /implement subcommand.')
    print()
    print('  Recommended fix: merge the granular allow list into ~/.claude/settings.json:')
    print()
    print('    bash scripts/deploy-all.sh --global-settings')
    print()
    print('  Or manually copy the \"permissions.allow\" array from:')
    print('    plugins/autonomous-dev/templates/settings.granular-bash.json')
    print()
    print('  See TROUBLESHOOTING.md § \"Permission prompts after upgrading Claude Code\"')
    print()
"
fi
```

---

### Step 2: Detect Project Type

After files are installed, detect the project type and generate PROJECT.md inline. Follow these steps:

**Detection rules:**
- **BROWNFIELD**: Has README.md, src/, package.json, pyproject.toml, or >10 source files
- **GREENFIELD**: Empty or near-empty project

**For BROWNFIELD:**
- Analyze: README.md, package.json/pyproject.toml, directory structure, git history
- Generate: Comprehensive PROJECT.md (80-90% complete)
- Mark TODOs: Only for CONSTRAINTS and CURRENT SPRINT (user must define)

**For GREENFIELD:**
- Ask: Primary goal, architecture type, tech stack
- Generate: PROJECT.md template with user inputs filled in
- Mark TODOs: More sections need user input

**Then:**
- Offer hook configuration (automatic vs manual workflow)
- Run health check to validate
- Show next steps

---

## What Gets Created

### Always Created

**Directory**: `.claude/`
- `agents/` - 20 AI agents
- `commands/` - 7 slash commands
- `hooks/` - 13 core automation hooks
- `lib/` - 35 Python libraries
- `skills/` - 28 skill packages

### PROJECT.md Generation

**Brownfield** (existing project):
```markdown
# Auto-generated sections (from codebase analysis):
- Project Vision (from README.md)
- Goals (from README roadmap/features)
- Architecture (detected from structure)
- Tech Stack (detected from package files)
- File Organization (detected patterns)
- Testing Strategy (detected from tests/)
- Documentation Map (detected from docs/)

# TODO sections (user must fill):
- CONSTRAINTS (performance, scale limits)
- CURRENT SPRINT (active work)
```

**Greenfield** (new project):
```markdown
# Generated from user responses:
- Project Vision
- Goals (based on primary goal selection)
- Architecture (based on architecture choice)

# TODO sections (more user input needed):
- SCOPE (in/out of scope)
- CONSTRAINTS
- CURRENT SPRINT
- File Organization
```

### Optional: Hook Configuration

**Manual Mode** (default):
- No additional config needed
- User runs formatting and testing tools manually

**Automatic Hooks Mode**:
- Hooks are configured automatically in settings.local.json
- Post-edit formatting via auto_format.py
- Pre-tool-use validation via unified_pre_tool.py
- See `.claude/settings.local.json` for full hook configuration

---

## Example Flow

### Brownfield Project (existing code)

```
/setup

Step 1: Installing plugin files...
✓ Synced 47 files from GitHub

Step 2: Detecting project type...
✓ BROWNFIELD detected (Python project with 213 commits)

Analyzing codebase...
✓ Found README.md (extracting vision)
✓ Found pyproject.toml (Python 3.11, FastAPI)
✓ Analyzing src/ (47 files, layered architecture)
✓ Analyzing tests/ (unit + integration)
✓ Analyzing git history (TDD workflow detected)

Generating PROJECT.md...
✓ Created PROJECT.md at root (412 lines, 95% complete)

Sections auto-generated:
  ✓ Project Vision
  ✓ Goals (from README)
  ✓ Architecture (Layered API pattern)
  ✓ Tech Stack (Python, FastAPI, PostgreSQL)
  ✓ File Organization
  ✓ Testing Strategy

Sections needing your input:
  📝 CONSTRAINTS - Define performance/scale limits
  📝 CURRENT SPRINT - Define active work

Step 3: Hook configuration
How would you like to run quality checks?
[1] Slash Commands (manual control - recommended for beginners)
[2] Automatic Hooks (auto-format, auto-test)
> 1

✓ Slash commands mode selected (no additional config)

Step 4: Validation
Running health check...
✓ 20/20 agents loaded
✓ 13/13 hooks executable
✓ 7/7 commands present
✓ PROJECT.md exists

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Setup Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next steps:
1. Review PROJECT.md and fill in TODO sections
2. Try: /implement "add a simple feature"
3. When done: /clear (reset context for next feature)
```

### Greenfield Project (new/empty)

```
/setup

Step 1: Installing plugin files...
✓ Synced 47 files from GitHub

Step 2: Detecting project type...
✓ GREENFIELD detected (minimal/empty project)

Let's create your PROJECT.md:

What is your project's primary goal?
[1] Production application (full-featured app)
[2] Library/SDK (reusable code for developers)
[3] Internal tool (company/team utility)
[4] Learning project (experimental)
> 1

What architecture pattern?
[1] Monolith (single codebase)
[2] Microservices (distributed)
[3] API + Frontend (layered)
[4] CLI tool
> 3

Primary language?
[1] Python
[2] TypeScript/JavaScript
[3] Go
[4] Other
> 1

Generating PROJECT.md...
✓ Created PROJECT.md at root (287 lines)

Fill in these sections:
  📝 GOALS - What success looks like
  📝 SCOPE - What's in/out of scope
  📝 CONSTRAINTS - Technical limits
  📝 CURRENT SPRINT - First sprint goals

Step 3: Hook configuration...
[Same as brownfield]

Step 4: Validation...
[Same as brownfield]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Setup Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Troubleshooting

### "Sync failed: Network error"

```bash
# Check internet connection
curl -I https://raw.githubusercontent.com

# Manual sync
/sync --github
```

### "PROJECT.md generation incomplete"

This is expected for greenfield projects. Fill in TODO sections manually:

```bash
# Open and edit
vim PROJECT.md

# Then validate
/align --project
```

### "Hooks not running"

Full restart required after setup:
```bash
# Quit Claude Code completely (Cmd+Q / Ctrl+Q)
# Wait 5 seconds
# Restart Claude Code
```

---

## Related Commands

- `/sync` - Sync/update plugin files
- `/align --project` - Validate PROJECT.md alignment
- `/health-check` - Validate plugin integrity

---

## Architecture

```
/setup
   │
   ├── Step 1: sync_dispatcher.py --github
   │   └── Reliable file installation (Python library)
   │
   ├── Step 2: Detect & Generate (inline)
   │   ├── Detect brownfield/greenfield
   │   ├── Analyze codebase (if brownfield)
   │   └── Generate PROJECT.md
   │
   ├── Step 3: Hook configuration
   │   └── Optional settings.local.json creation
   │
   └── Step 4: validate installation
       └── Validate installation
```

**Key Design**: Delegates file installation to `sync_dispatcher.py` (reliable), handles PROJECT.md generation inline (detection + generation executed directly by Claude).

---

**Last Updated**: 2025-12-13
