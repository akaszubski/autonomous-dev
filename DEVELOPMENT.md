# Development Guide - Keeping Everything in Sync

**How to develop the autonomous system while keeping repo ↔ local Claude installation in sync**

---

## The Challenge

**Two locations for the plugin**:
1. **Development repo**: `~/Documents/GitHub/claude-code-bootstrap/plugins/autonomous-dev/`
2. **Claude installation**: `~/.claude/plugins/autonomous-dev/`

**The problem**: Changes in repo don't automatically reflect in Claude

---

## Quick Refresh (TL;DR)

**After making changes to agents, commands, skills, or hooks**:

```bash
# From repo root
./scripts/refresh-claude-settings.sh
```

**What it does**:
- Syncs agents, commands, skills, hooks from `plugins/autonomous-dev/` to `.claude/`
- Verifies plugin symlink exists
- Changes active immediately (no restart needed)

**When to run**:
- After editing agent definitions
- After modifying commands
- After updating skills
- After changing hooks
- Before testing changes in Claude

---

## Solution 1: Symlink (Recommended) ⭐

**One-time setup** - Create symlink so repo and Claude share the same files:

```bash
# 1. Uninstall plugin if already installed
/plugin uninstall autonomous-dev

# 2. Remove any existing plugin directory
rm -rf ~/.claude/plugins/autonomous-dev

# 3. Create symlink from Claude to your repo
ln -s ~/Documents/GitHub/claude-code-bootstrap/plugins/autonomous-dev \
      ~/.claude/plugins/autonomous-dev

# 4. Verify symlink
ls -la ~/.claude/plugins/autonomous-dev
# Should show: ... -> ~/Documents/GitHub/claude-code-bootstrap/plugins/autonomous-dev

# 5. Use plugin normally
/setup
```

**Benefits**:
- ✅ **Instant sync** - Edit in repo, use immediately in Claude
- ✅ **One source of truth** - No manual copying
- ✅ **Fast iteration** - Change, test, commit
- ✅ **No reinstall needed** - Changes active immediately

**Workflow**:
```bash
# Edit in your repo
vim ~/Documents/GitHub/claude-code-bootstrap/plugins/autonomous-dev/commands/commit.md

# Use immediately in Claude (no reload needed)
claude /commit --help  # Shows your changes!

# Commit when ready
cd ~/Documents/GitHub/claude-code-bootstrap
git add plugins/autonomous-dev/commands/commit.md
git commit -m "docs: update commit workflow"
git push origin master
```

---

## Solution 2: Manual Sync (Fallback)

If symlinks don't work on your system:

### After Pushing to GitHub

```bash
# 1. Push changes from repo
cd ~/Documents/GitHub/claude-code-bootstrap
git push origin master

# 2. Update Claude installation
cd ~/.claude/plugins/autonomous-dev
git pull origin master

# 3. Or reinstall plugin
/plugin uninstall autonomous-dev
/plugin install autonomous-dev
```

### During Development

```bash
# 1. Make changes in repo
cd ~/Documents/GitHub/claude-code-bootstrap
vim plugins/autonomous-dev/commands/commit.md

# 2. Copy to Claude installation
cp -r plugins/autonomous-dev/* ~/.claude/plugins/autonomous-dev/

# 3. Test in Claude
claude /commit --help

# 4. Commit when ready
git add .
git commit -m "docs: update commit workflow"
git push
```

---

## Solution 3: The Autonomous Loop ⭐ (Future)

**The system improves itself automatically**:

### How It Works

1. **Documentation describes ideal state**
   - We write docs first (like COMMIT-WORKFLOW-COMPLETE.md)
   - Docs describe what SHOULD exist

2. **Layer 3 testing detects drift**
   ```bash
   /test architecture
   # Output: ⚠️  Drift detected: /commit docs don't match implementation
   # ✅ Created issue #45: "Implement progressive commit workflow"
   ```

3. **Automatic issue creation**
   ```bash
   # Pre-push hook runs automatically
   git push
   # → Detects documentation vs implementation gaps
   # → Creates GitHub Issues
   # → Links to documentation
   ```

4. **Use /auto-implement to close the loop**
   ```bash
   /auto-implement --from-issue 45
   # → orchestrator reads issue + documentation
   # → planner designs implementation
   # → test-master writes tests
   # → implementer codes it
   # → reviewer checks quality
   # → doc-master updates docs
   # → System implemented its own improvement!
   ```

### Example: Implementing Progressive Commit

**Current state**:
- ✅ Documentation exists (COMMIT-WORKFLOW-COMPLETE.md)
- ❌ Implementation doesn't exist (current /commit is simple)

**Autonomous implementation**:

```bash
# 1. Create issue
gh issue create \
  --title "Implement progressive commit workflow (4 levels)" \
  --body "See: plugins/autonomous-dev/docs/COMMIT-WORKFLOW-COMPLETE.md" \
  --label enhancement,autonomous

# 2. Let system implement it
/auto-implement --from-issue 45

# The system will:
# - Read COMMIT-WORKFLOW-COMPLETE.md (the spec)
# - Read current commands/commit.md (current state)
# - Design the implementation
# - Write tests first (TDD)
# - Implement features to pass tests
# - Update documentation
# - Create PR

# 3. Review and merge
gh pr review --approve
gh pr merge

# 4. System improved itself!
```

---

## Development Workflows

### Workflow A: Documentation First (Recommended)

**Use when**: Designing new features

```bash
# 1. Write documentation describing ideal state
vim plugins/autonomous-dev/docs/COMMIT-WORKFLOW-COMPLETE.md
# (Describe what /commit SHOULD do)

# 2. Commit documentation
git add docs/
git commit -m "docs: design progressive commit workflow"
git push

# 3. Create issue for implementation
gh issue create \
  --title "Implement progressive commit workflow" \
  --body "See: docs/COMMIT-WORKFLOW-COMPLETE.md"

# 4. Use /auto-implement to build it
/auto-implement --from-issue 45

# 5. System implements based on documentation!
```

**Benefits**:
- ✅ Think through design first
- ✅ Documentation complete before coding
- ✅ System implements from spec
- ✅ No drift (docs = implementation)

---

### Workflow B: Test-Driven Development

**Use when**: Implementing specific features

```bash
# 1. Write failing tests
vim plugins/autonomous-dev/tests/test_commit_workflow.py

def test_commit_push_rebuilds_readme():
    """Test that /commit --push rebuilds README from PROJECT.md"""
    # This test will fail (feature doesn't exist yet)
    result = run_command("/commit --push")
    assert "README.md updated" in result.output

# 2. Commit failing tests
git add tests/
git commit -m "test: add tests for progressive commit workflow"

# 3. Use /auto-implement to make tests pass
/auto-implement "Make test_commit_workflow.py pass"

# 4. System implements just enough to pass tests
```

---

### Workflow C: Incremental Enhancement

**Use when**: Improving existing features

```bash
# 1. Identify improvement
/test architecture
# Output: ⚠️  Missing: README rebuild on /commit --push

# 2. Issue created automatically
# Issue #46: "Add README rebuild to /commit --push"

# 3. Implement improvement
/auto-implement --from-issue 46

# 4. Test and merge
/test all
git push
```

---

## Tracking Implementation vs Documentation

### Manual Check

```bash
# Compare documented features vs implemented features
echo "=== Documented features ==="
grep "^## " plugins/autonomous-dev/docs/COMMIT-WORKFLOW-COMPLETE.md

echo "=== Implemented features ==="
grep "^## " plugins/autonomous-dev/commands/commit.md

# Identify gaps
diff <(grep "## " docs/COMMIT-WORKFLOW-COMPLETE.md) \
     <(grep "## " commands/commit.md)
```

### Automated Check (Future)

```bash
# Layer 3 testing detects drift
/test architecture

# Output:
# ⚠️  Documentation drift detected:
#    - COMMIT-WORKFLOW-COMPLETE.md describes 4 levels
#    - commands/commit.md implements 2 levels
#    - Gap: Levels 3 and 4 missing
# ✅ Created issue #47: "Implement /commit levels 3 and 4"
```

---

## Release Process

### When Documentation Changes

```bash
# 1. Update documentation
vim docs/COMMIT-WORKFLOW-COMPLETE.md

# 2. Commit
git add docs/
git commit -m "docs: add Level 5 for canary releases"

# 3. Push to GitHub
git push origin master

# 4. Create implementation issue
gh issue create --title "Implement Level 5 canary releases"

# 5. Tag documentation release
git tag -a v2.1.0-docs -m "Documentation for Level 5"
git push --tags
```

### When Implementation Changes

```bash
# 1. Implement feature
/auto-implement --from-issue 47

# 2. Verify documentation matches
/test architecture
# Should show: ✅ 100% alignment

# 3. Tag implementation release
git tag -a v2.1.0 -m "Implemented Level 5 canary releases"
git push --tags

# 4. Create GitHub Release
gh release create v2.1.0 \
  --title "v2.1.0 - Canary Release Support" \
  --notes "$(git log v2.0.0..v2.1.0 --pretty=format:'- %s')"
```

---

## Common Issues

### Issue 1: Changes in repo not visible in Claude

**Symptoms**:
- Edit `plugins/autonomous-dev/commands/commit.md`
- Run `/commit --help`
- Old documentation shows

**Fix**:
```bash
# Check if using symlink
ls -la ~/.claude/plugins/autonomous-dev

# If NOT symlink, reinstall
/plugin uninstall autonomous-dev
/plugin install autonomous-dev

# Or copy manually
cp -r plugins/autonomous-dev/* ~/.claude/plugins/autonomous-dev/
```

---

### Issue 2: Documentation and implementation out of sync

**Symptoms**:
- `/test architecture` shows drift
- Documentation describes features that don't exist

**Fix**:
```bash
# Create issue for missing features
gh issue create \
  --title "Implement documented features" \
  --body "Sync implementation with docs"

# Implement
/auto-implement --from-issue X
```

---

### Issue 3: Multiple versions of plugin

**Symptoms**:
- Confused about which version is running
- Changes seem random

**Fix**:
```bash
# Remove all versions
rm -rf ~/.claude/plugins/autonomous-dev

# Reinstall from repo via symlink
ln -s ~/Documents/GitHub/claude-code-bootstrap/plugins/autonomous-dev \
      ~/.claude/plugins/autonomous-dev

# Verify single source
ls -la ~/.claude/plugins/autonomous-dev
# Should show symlink
```

---

## Best Practices

### 1. Documentation First
- ✅ Write docs describing ideal state
- ✅ Create issues for implementation
- ✅ Use /auto-implement to build from docs

### 2. Use Symlinks for Development
- ✅ One source of truth
- ✅ Instant sync
- ✅ Fast iteration

### 3. Test Drift Detection
- ✅ Run `/test architecture` regularly
- ✅ Let system auto-create issues
- ✅ Fix drift incrementally

### 4. Commit Often
- ✅ Documentation commits separate from implementation
- ✅ Tag releases (v2.0.0-docs vs v2.0.0)
- ✅ Use conventional commits

### 5. Let System Improve Itself
- ✅ Create issues for gaps
- ✅ Use /auto-implement
- ✅ Review and merge
- ✅ System evolves autonomously

---

## Summary

**Three sync strategies**:

1. **Symlink** (recommended for development)
   - One-time setup
   - Instant sync
   - No manual copying

2. **Manual sync** (fallback)
   - Copy after changes
   - Reinstall plugin
   - More tedious

3. **Autonomous loop** (future)
   - System detects drift
   - Auto-creates issues
   - Implements itself

**The vision**: The autonomous system maintains its own documentation-implementation alignment automatically! 🚀

---

**Next**: Set up symlink and start using the autonomous loop to implement documented features.
