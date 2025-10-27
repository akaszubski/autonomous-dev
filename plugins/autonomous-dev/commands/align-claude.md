---
description: Check and fix CLAUDE.md alignment with codebase
argument-hint: Optional - skip argument to check current alignment
---

## Implementation

```bash
python plugins/autonomous-dev/scripts/validate_claude_alignment.py
```

# CLAUDE.md Alignment Checker

Check and fix drift between documented standards (CLAUDE.md) and actual implementation.

## What This Does

CLAUDE.md defines development standards. If it drifts from reality (outdated version numbers, wrong agent counts, missing commands), new developers follow incorrect practices.

This command:
1. **Detects drift** - Compares CLAUDE.md against actual PROJECT.md, agents, commands, hooks
2. **Shows issues** - Version mismatches, count errors, missing features
3. **Guides fixes** - Tells you exactly what to update
4. **Prevents future drift** - Pre-commit hook validates alignment on every commit

## Usage

```bash
# Check current alignment
/align-claude

# Or just run the validation script directly
python plugins/autonomous-dev/scripts/validate_claude_alignment.py
```

## What Gets Checked

### 1. Version Consistency
- Project CLAUDE.md should match or be newer than PROJECT.md
- Global CLAUDE.md in `~/.claude/` should be reasonable
- All files should have recent "Last Updated" dates

### 2. Agent Counts
- CLAUDE.md says how many agents exist
- Checks against actual agents in `plugins/autonomous-dev/agents/`
- Currently: 16 agents (10 core + 6 utility)

### 3. Command Counts
- CLAUDE.md lists all available commands
- Checks against actual commands in `plugins/autonomous-dev/commands/`
- Currently: 8 commands (auto-implement, align-project, setup, test, status, health-check, sync-dev, uninstall)

### 4. Documented Features Exist
- All commands mentioned in CLAUDE.md must have corresponding files
- All agents mentioned must exist
- All hooks mentioned must have implementations

### 5. Skills Documentation
- Skills were removed in v2.5.0 (Anthropic anti-pattern)
- CLAUDE.md should say "Skills (0 - Removed)"
- Any documentation of actual skills is outdated

### 6. Hook Documentation
- CLAUDE.md describes available hooks
- Validates hook count is reasonable
- Warns if major hooks are missing

## What Drift Looks Like

```
❌ Example 1: Agent Count Drift
   CLAUDE.md says: "Agents (7 specialists)"
   Reality: 16 agents exist
   Fix: Update to "### Agents (16 specialists)"

❌ Example 2: Outdated Version
   CLAUDE.md Last Updated: 2025-10-19
   PROJECT.md Last Updated: 2025-10-27
   Fix: Update CLAUDE.md date to 2025-10-27

❌ Example 3: Missing Command
   CLAUDE.md mentions: /auto-implement
   Reality: Command file doesn't exist
   Fix: Check if command was renamed or removed
```

## Common Fixes

### Update Version Date
```bash
# In CLAUDE.md, change:
# **Last Updated**: 2025-10-19
# To:
# **Last Updated**: 2025-10-27
```

### Fix Agent Count
```bash
# Change: ### Agents (7 specialists)
# To:     ### Agents (16 specialists)
```

### Fix Command Count
```bash
# Change: Done! All commands work: /test, /format, /commit, etc.
# To:     Done! All commands work: /auto-implement, /align-project, /setup, /test, /status, /health-check, /sync-dev, /uninstall
```

### Update Skills Section
```bash
# Old (outdated):
# ### Skills (6 core competencies)
# Located: `plugins/autonomous-dev/skills/`
# - python-standards: ...

# New (correct):
# ### Skills (0 - Removed)
# Per Anthropic anti-pattern guidance (v2.5+), skills were removed.
# Guidance now lives directly in agent prompts and global CLAUDE.md files.
```

## Automated Checking (Hook)

This is also enforced by a pre-commit hook:

```bash
git commit -m "feature: add something"
# ↓
# Pre-commit hook runs validate_claude_alignment.py
# ↓
# If drift detected, warning shown:
#   ⚠️  CLAUDE.md Alignment: Agent count mismatch...
# ↓
# Commit still proceeds, but you see the warning
# (You should fix it next commit or /clear)
```

## Fix Workflow

```bash
# 1. See what's drifted
/align-claude
# Output shows specific issues

# 2. Update CLAUDE.md based on output
vim CLAUDE.md
# Fix version dates, counts, descriptions

# 3. Verify the fix
/align-claude
# Should show: ✅ CLAUDE.md Alignment: No issues found

# 4. Commit the alignment fix
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md alignment"
```

## Why This Matters

**Scenario: New Developer**
```
New dev: "What commands are available?"
Reads CLAUDE.md: "/test, /format, /commit work great"
But: Those commands were archived in v3.1.0

With alignment checking:
→ CLAUDE.md always matches reality
→ Docs are never stale
→ Developers follow current practices
```

## Test Coverage

Validation is tested in:
```
plugins/autonomous-dev/tests/test_claude_alignment.py
```

Tests cover:
- ✅ Date extraction and comparison
- ✅ Count detection (agents, commands, hooks)
- ✅ Missing feature detection
- ✅ Skills deprecation checking
- ✅ Session-based warning deduplication
- ✅ Real-world scenario validation

## Troubleshooting

### "Can't find validation script"

```bash
# Try directly:
python plugins/autonomous-dev/scripts/validate_claude_alignment.py

# If that fails, check path:
ls plugins/autonomous-dev/scripts/
```

### "Shows warnings but I think they're wrong"

Check what changed recently:
```bash
# See git diff
git diff plugins/autonomous-dev/agents/

# See git log
git log plugins/autonomous-dev/ | head -20
```

Maybe the codebase changed but CLAUDE.md wasn't updated.

### "Hook runs before every commit"

That's intentional! It ensures CLAUDE.md stays in sync. If you see a warning:
1. Fix CLAUDE.md
2. Re-commit (or just add CLAUDE.md to next commit)

To temporarily skip (NOT recommended):
```bash
git commit --no-verify
# But then manually run validation later
python plugins/autonomous-dev/scripts/validate_claude_alignment.py
```

## See Also

- **CLAUDE.md**: The standards file being validated
- **PROJECT.md**: Strategic goals and scope (alignment gatekeeper)
- **validate_claude_alignment.py**: The validation script
- **test_claude_alignment.py**: Test suite

---

**Purpose**: Prevent documentation drift, keep CLAUDE.md accurate, help new developers follow current best practices.

**Frequency**: Check whenever CLAUDE.md might be stale (after major updates, weekly cleanup).

**Maintenance**: Pre-commit hook validates automatically; you just need to fix warnings when they appear.
