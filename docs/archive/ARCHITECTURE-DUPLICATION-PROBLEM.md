# Architecture Duplication Problem - CRITICAL

**Discovered**: 2025-10-21
**Severity**: HIGH - Maintenance nightmare
**Impact**: ALL automation folders, not just docs

---

## The Problem

**We have TWO complete copies of EVERYTHING:**

```
autonomous-dev/
├── .claude/                           # ROOT - Active during dev
│   ├── commands/ (33 files)          # ← Claude Code reads from here
│   ├── agents/ (8 files)             # ← Active agents
│   ├── skills/ (6 files)             # ← Active skills
│   ├── hooks/ (13 files)             # ← Active hooks
│   └── templates/ (2 files)          # ← Active templates
│
├── docs/ (dev docs)                   # ROOT - Developer
├── scripts/ (build tools)             # ROOT - Developer
├── tests/ (infrastructure)            # ROOT - Developer
│
└── plugins/autonomous-dev/            # PLUGIN - Distribution
    ├── commands/ (33 files)          # ← DUPLICATE!
    ├── agents/ (8 files)             # ← DUPLICATE!
    ├── skills/ (6 files)             # ← DUPLICATE!
    ├── hooks/ (13 files)             # ← DUPLICATE!
    ├── templates/ (2 files)          # ← DUPLICATE!
    ├── docs/ (user docs)             # PLUGIN - Users
    ├── scripts/ (setup.py)           # PLUGIN - Users
    └── tests/ (plugin tests)         # PLUGIN - Users
```

**Result**: Edit a command → Must sync to 2 locations. Maintenance hell!

---

## Files Affected - Complete Audit

### 1. **Commands** - 33 files DUPLICATED
- `.claude/commands/*.md` (33 files)
- `plugins/autonomous-dev/commands/*.md` (33 files IDENTICAL)

### 2. **Agents** - 8 files DUPLICATED
- `.claude/agents/*.md` (8 agents)
- `plugins/autonomous-dev/agents/*.md` (8 agents IDENTICAL)

### 3. **Skills** - 6 directories DUPLICATED
- `.claude/skills/*/SKILL.md` (6 skills)
- `plugins/autonomous-dev/skills/*/SKILL.md` (6 skills IDENTICAL)

### 4. **Hooks** - 13 files DUPLICATED
- `.claude/hooks/*.py` (13 hooks)
- `plugins/autonomous-dev/hooks/*.py` (13 hooks IDENTICAL)

### 5. **Templates** - 2 files DUPLICATED
- `.claude/templates/*` (2 templates)
- `plugins/autonomous-dev/templates/*` (2 templates IDENTICAL)

### 6. **Scripts** - DIFFERENT PURPOSES (Good!)
- `scripts/` (ROOT) - Build tools (validate_structure.py, etc.)
- `plugins/autonomous-dev/scripts/` (PLUGIN) - User tools (setup.py)

### 7. **Tests** - DIFFERENT PURPOSES (Good!)
- `tests/` (ROOT) - Infrastructure tests
- `plugins/autonomous-dev/tests/` (PLUGIN) - Plugin feature tests

### 8. **Docs** - DIFFERENT PURPOSES (Good! Already addressed)
- `docs/` (ROOT) - Developer documentation
- `plugins/autonomous-dev/docs/` (PLUGIN) - User documentation

---

## The ROOT Cause

**During development:**
- Claude Code reads from `.claude/` (ROOT level)
- Plugin directory exists but is INACTIVE

**During distribution:**
- Users install `plugins/autonomous-dev/`
- ROOT `.claude/` is NOT distributed

**The Sync Problem:**
```bash
# You make a change here (active during dev):
.claude/commands/test.md

# You must manually copy to (distributed to users):
plugins/autonomous-dev/commands/test.md

# Otherwise: Dev version ≠ User version
```

---

## Three Possible Solutions

### Option 1: Symlinks (Simple but fragile)

```bash
# Make plugin point to ROOT
rm -rf plugins/autonomous-dev/commands
ln -s ../../.claude/commands plugins/autonomous-dev/commands

# Same for agents, skills, hooks, templates
```

**Pros:**
- ✅ Single source of truth
- ✅ No sync needed
- ✅ Instant updates

**Cons:**
- ❌ Git doesn't handle symlinks well
- ❌ Won't work on all platforms
- ❌ Breaks marketplace distribution

---

### Option 2: Build Script (Robust)

**Source of truth**: `.claude/` (ROOT)
**Distribution**: Built from ROOT

```bash
# scripts/build_plugin.sh
#!/bin/bash
# Build plugin from ROOT .claude/

echo "Building plugin from ROOT..."

# Copy automations
cp -r .claude/commands/ plugins/autonomous-dev/commands/
cp -r .claude/agents/ plugins/autonomous-dev/agents/
cp -r .claude/skills/ plugins/autonomous-dev/skills/
cp -r .claude/hooks/ plugins/autonomous-dev/hooks/
cp -r .claude/templates/ plugins/autonomous-dev/templates/

# Validate
python scripts/validate_structure.py

echo "✅ Plugin built successfully"
```

**Workflow:**
```bash
# 1. Edit in ROOT
vim .claude/commands/test.md

# 2. Build plugin
./scripts/build_plugin.sh

# 3. Test dogfooding (install plugin)
/plugin install autonomous-dev

# 4. Commit both
git add .claude/ plugins/autonomous-dev/
git commit -m "Update test command"
```

**Pros:**
- ✅ Single source of truth (ROOT)
- ✅ Explicit build step
- ✅ Can add transformations (e.g., strip DEV_MODE features)
- ✅ Works everywhere

**Cons:**
- ❌ Extra build step
- ❌ Can forget to build

**Mitigation**: Pre-commit hook runs build automatically

---

### Option 3: Reverse Flow (Dogfooding first)

**Source of truth**: `plugins/autonomous-dev/` (PLUGIN)
**Development**: Install plugin to ROOT

```bash
# During development:
/plugin install autonomous-dev

# This creates symlink:
.claude/ → plugins/autonomous-dev/

# Edit plugin directly:
vim plugins/autonomous-dev/commands/test.md

# Changes immediately active (symlink)
```

**Workflow:**
```bash
# 1. Edit plugin directly
vim plugins/autonomous-dev/commands/test.md

# 2. Test (already active via symlink)
/test

# 3. Commit
git add plugins/autonomous-dev/
git commit -m "Update test command"

# 4. No ROOT .claude/ to maintain!
```

**Pros:**
- ✅ Single source of truth (PLUGIN)
- ✅ True dogfooding (test what you ship)
- ✅ No sync needed
- ✅ No build step

**Cons:**
- ❌ ROOT `.claude/` becomes symlink (unusual)
- ❌ Need to handle DEV_MODE features differently

---

## Recommended Solution: **Option 2 (Build Script)**

**Why:**
1. **Explicit** - Build step makes it clear what gets distributed
2. **Flexible** - Can strip DEV_MODE features during build
3. **Validated** - Can run checks during build
4. **Standard** - Common pattern in software development

**Implementation Plan:**

### Phase 1: Create Build System
1. ✅ Create `scripts/build_plugin.sh`
2. ✅ Create `scripts/validate_build.sh`
3. ✅ Add pre-commit hook to auto-build
4. ✅ Update CONTRIBUTING.md with build workflow

### Phase 2: Establish Source of Truth
1. ✅ Declare ROOT `.claude/` as source
2. ✅ Add `.gitattributes` to mark `plugins/*/commands/` as generated
3. ✅ Update README with build process

### Phase 3: Add Smart Features
1. ✅ Strip DEV_MODE-only commands during build
2. ✅ Inject version numbers during build
3. ✅ Validate structure during build

---

## DEV_MODE Commands (Don't distribute)

These commands should ONLY exist in ROOT `.claude/commands/`:

```bash
# Dev-only commands (not in plugin build):
.claude/commands/build-plugin.md          # Build plugin
.claude/commands/validate-plugin.md       # Validate plugin
.claude/commands/test-marketplace.md      # Test marketplace install
.claude/commands/sync-to-plugin.md        # Manual sync
```

During build: **Filter these out** from plugin distribution.

---

## Action Items

### Immediate
- [ ] Create `scripts/build_plugin.sh`
- [ ] Create `scripts/validate_build.sh`
- [ ] Document build workflow in CONTRIBUTING.md
- [ ] Add pre-commit hook for auto-build

### Short-term
- [ ] Create DEV_MODE-only commands
- [ ] Add build validation to CI/CD
- [ ] Update all documentation references

### Long-term
- [ ] Add version injection during build
- [ ] Create marketplace package automation
- [ ] Add telemetry to track dev vs user issues

---

## Current Status

**Problem Severity**: HIGH
**Current Workaround**: Manual sync (error-prone)
**Recommended Fix**: Build script (Option 2)
**Estimated Implementation**: 2-4 hours

---

**This architectural issue affects 95% of the codebase. Must fix before next release.**
