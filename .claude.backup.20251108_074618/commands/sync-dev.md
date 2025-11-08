---
description: Synchronize development environment - detect conflicts, validate dependencies, ensure compatibility
---

# Sync Dev - Development Environment Synchronization

**Smart environment sync powered by the sync-validator agent**

Detects and resolves development environment conflicts including dependency mismatches, configuration drift, pending migrations, and stale build artifacts.

---

## Usage

```bash
/sync-dev
```

**Time**: 30-60 seconds
**Interactive**: Shows sync status, asks for confirmation before fixes
**GenAI-Powered**: Uses sync-validator agent for intelligent conflict detection

---

## How It Works

The sync-validator agent analyzes your development environment:

### Phase 1: Pre-Sync Analysis
- Checks local state (uncommitted changes, stale branches, existing conflicts)
- Checks remote state (new commits, tags, breaking changes)
- Assesses sync risk (low/medium/high)

### Phase 2: Fetch & Analyze Changes
- Fetches latest from upstream
- Analyzes changed files
- Categorizes changes (safe / requires attention / breaking)

### Phase 3: Conflict Detection
- Dependency conflicts (package.json, requirements.txt, Cargo.toml)
- Environment variable mismatches (.env files)
- Pending database migrations
- Stale build artifacts
- Configuration drift between local and upstream

### Phase 4: Validation
- Syntax validation (Python, Bash, JSON)
- Plugin integrity check (all agents present)
- Dependency compatibility
- Hook functionality

### Phase 5: Recovery & Recommendations
- Provides fix recommendations
- Safe rollback if issues detected
- Next steps for manual resolution

---

## Example Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 Development Environment Sync
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pre-Sync Analysis:
  Local state: ✅ Clean (no uncommitted changes)
  Remote state: 7 new commits, 1 new tag (v3.0.3)
  Risk level: LOW

Fetching Changes:
  ✅ Fetched from origin/main
  Files changed: 12

Change Analysis:
  Safe changes (9):
    - docs: update README
    - agents: improve researcher prompt
    - agents: add quality-validator agent

  Requires attention (3):
    - hooks: update auto_format.py (new black option)
    - config: add new setting in PROJECT.md template
    - deps: bump pytest 7.4 → 8.0 (minor version)

Conflict Detection:
  ✅ No merge conflicts
  ✅ Dependencies compatible
  ⚠️  Environment: Missing DB_HOST in .env
  ✅ Build artifacts current
  ✅ No pending migrations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Issues Detected
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Missing environment variable
   Variable: DB_HOST
   File: .env
   Impact: Database connection will fail
   Fix: Add DB_HOST=localhost to .env

2. Dependency update available
   Package: pytest 7.4.0 → 8.0.0
   Type: Minor version bump
   Impact: May have new features/deprecations
   Fix: pip install --upgrade pytest

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Recommendations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proceed with sync? [Y/n]: y

Merging Changes:
  ✅ Merged 12 files from origin/main
  ✅ No conflicts

Validation:
  ✅ Syntax check passed
  ✅ Plugin integrity (19/19 agents)
  ✅ Dependencies compatible
  ⚠️  Environment incomplete (.env needs DB_HOST)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Sync Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
- 7 commits merged successfully
- 12 files updated
- 0 conflicts
- 1 environment issue to fix manually

Next Steps:
1. Add DB_HOST to .env file
2. Run /health-check to verify all components
3. Review updated CLAUDE.md for new features
```

---

## What the Agent Detects

### Dependency Conflicts
- **Python**: requirements.txt, pyproject.toml version conflicts
- **Node.js**: package.json, package-lock.json mismatches
- **Rust**: Cargo.toml, Cargo.lock conflicts
- **Go**: go.mod, go.sum issues

### Environment Issues
- Missing environment variables in .env
- Mismatched values between .env.example and .env
- Required variables not set
- Credential expiration

### Build Artifacts
- Stale __pycache__ directories
- Outdated node_modules
- Old Rust target/ directories
- Stale Docker images

### Database Issues
- Pending migrations not applied
- Schema drift between local and remote
- Missing seed data
- Connection configuration issues

### Configuration Drift
- .claude/settings.local.json out of sync
- PROJECT.md template changes
- Hook configuration updates
- Agent prompt updates

---

## Example Workflows

### After Git Pull

```bash
# Just pulled latest from main
git pull origin main

# Check for environment sync issues
/sync-dev

OUTPUT:
⚠️  3 issues detected:
1. New dependency: requests==2.31.0 not installed
2. Missing env variable: API_KEY
3. Pending migration: add_users_table.sql

Fix automatically? [Y/n]: y

✅ Dependencies installed
✅ API_KEY added to .env (placeholder - update with real key)
⚠️  Migration pending - run: python manage.py migrate
```

### Weekly Environment Check

```bash
# Regular maintenance check
/sync-dev

OUTPUT:
✅ Environment in sync
✅ All dependencies current
✅ No pending migrations
✅ Build artifacts clean
✅ Configuration up-to-date

No action needed!
```

### After Plugin Update

```bash
# Just updated autonomous-dev plugin
/plugin install autonomous-dev

# Check compatibility
/sync-dev

OUTPUT:
Detected: Plugin updated to v3.2.0
Checking compatibility...

⚠️  Local hooks outdated (v3.1.0 → v3.2.0)

Fix: Copy updated hooks from plugin

Update hooks? [Y/n]: y

✅ Hooks updated
✅ All 19 agents loaded
✅ Commands accessible

Plugin sync complete!
```

### Conflict Resolution

```bash
# Merge conflict detected
/sync-dev

OUTPUT:
❌ Merge conflict detected

File: .claude/PROJECT.md
Conflict markers: 3

Options:
  [1] Accept upstream (use latest from main)
  [2] Accept local (keep your changes)
  [3] Manual resolve (guide me through it)
  [4] Abort sync (rollback changes)

Your choice: 3

[Agent guides through manual resolution...]

✅ Conflict resolved
✅ Sync complete
```

---

## When to Use

**Run /sync-dev when**:
- 📥 After git pull (detect environment sync issues)
- 🔄 After plugin updates (verify compatibility)
- 🚀 Before starting new features (ensure clean state)
- 🐛 Debugging environment issues (find misconfigurations)
- 📅 Weekly maintenance (keep environment healthy)
- 👥 After teammate adds dependencies (sync your environment)

**Output tells you**:
- What changed upstream?
- Are there conflicts?
- Is my environment compatible?
- What needs to be fixed?
- Can it be auto-fixed?

---

## Integration with Other Commands

### With /health-check
```bash
# After sync, verify integrity
/sync-dev
/health-check  # Confirms all components working
```

### With /auto-implement
```bash
# Before starting new feature
/sync-dev      # Ensure environment clean
/auto-implement "Add user authentication"  # Safe to proceed
```

### With /setup
```bash
# After major plugin update
/sync-dev      # Detect what changed
/setup         # Reconfigure if needed
```

---

## Safety Features

✅ **No destructive actions without confirmation**: Always asks before applying fixes
✅ **Rollback support**: Can abort and restore previous state
✅ **Conflict detection**: Identifies issues before they break your environment
✅ **Validation after changes**: Ensures fixes worked correctly
✅ **Clear communication**: Explains what's happening and why

---

## Troubleshooting

### "Uncommitted changes detected"

```bash
# Commit or stash changes first
git stash
/sync-dev
git stash pop
```

### "Dependency install failed"

```bash
# Check specific dependency
/sync-dev

OUTPUT:
❌ Failed to install: requests==2.31.0
Reason: SSL certificate verification failed

Manual fix required:
  pip install --trusted-host pypi.org requests==2.31.0
```

### "Merge conflict can't auto-resolve"

```bash
/sync-dev

OUTPUT:
❌ Complex merge conflict in src/core/config.py

This requires manual resolution:
1. Open src/core/config.py
2. Search for <<<<<<< HEAD
3. Resolve each conflict
4. Run: git add src/core/config.py
5. Run: /sync-dev again
```

---

## Security Considerations

### Important Notes on Development Environment Sync

**Configuration Trust**: This command reads Claude Code's plugin configuration from `~/.claude/plugins/installed_plugins.json` to determine where the autonomous-dev plugin is installed. Ensure this file is protected with appropriate file permissions (mode 600: owner read/write only).

**Path Validation**: The sync-validator agent validates all paths before performing destructive operations (deletions, overwrites). Operations are never executed without explicit confirmation.

**Shared Systems**: If using a shared development machine, ensure:
- Your `~/.claude` directory has restrictive permissions (700)
- Environment files (.env) contain only placeholders until configured locally
- Never commit real credentials or API keys to version control

**Rollback Support**: All synchronization operations support rollback:
- If conflicts are detected, sync can be aborted before making changes
- Critical operations create backups before modifying files
- Use `git status` to verify changes before committing

**Audit Trail**: All sync operations are logged in your git history. Review changes:
```bash
git log --oneline | head -10  # See recent sync activity
git diff HEAD~1 HEAD          # Inspect last sync changes
```

---

## Related Commands

- `/health-check` - Validate plugin component integrity after sync
- `/setup` - Reconfigure plugin after major updates
- `/status` - Check project progress after environment sync
- `/auto-implement` - Start feature development in clean environment

---

## Implementation

Invoke the sync-validator agent to analyze and synchronize the development environment.

The agent will:
1. Analyze local and remote state
2. Detect conflicts and issues
3. Categorize changes by risk
4. Provide fix recommendations
5. Execute fixes with confirmation
6. Validate results

**Use this command to keep your development environment synchronized, detect conflicts early, and ensure compatibility after upstream changes.**

---

**For detailed security audit findings**: See `docs/sessions/SECURITY_AUDIT_SYNC_DEV.md` for comprehensive security analysis, vulnerability assessment, and remediation guidance.
