# Consistency Validation Checklist

**Last Updated**: 2025-10-24
**Purpose**: Ensure total consistency before releases

Run this checklist before every release to maintain quality and clarity.

---

## 1. File Structure ✅

### Commands
```bash
# Count should be 21
ls -1 plugins/autonomous-dev/commands/*.md | wc -l

# List all commands
ls -1 plugins/autonomous-dev/commands/*.md | xargs -n1 basename | sed 's/\.md$//' | sort

# Check for versioned files (should be 0)
find plugins/autonomous-dev -name "*-v[0-9]*" -o -name "*-old*" -o -name "*.bak" | wc -l
```

**Expected**:
- ✅ Exactly 21 command files
- ✅ No `-v2`, `-old`, or `.bak` files
- ✅ All files follow naming convention: lowercase-with-dashes.md

### Agents
```bash
# Count should be 8
ls -1 plugins/autonomous-dev/agents/*.md | wc -l

# List all agents
ls -1 plugins/autonomous-dev/agents/*.md | xargs -n1 basename | sed 's/\.md$//'

# Check for versioned files (should be 0)
find plugins/autonomous-dev/agents -name "*-v[0-9]*" | wc -l
```

**Expected**:
- ✅ Exactly 8 agent files
- ✅ No `-v2` or versioned files
- ✅ Names match PROJECT.md (line 92)

### Skills
```bash
# Count should be 6
ls -1 plugins/autonomous-dev/skills/*/SKILL.md | wc -l

# List all skills
ls -1 plugins/autonomous-dev/skills/*/SKILL.md | xargs -I {} dirname {} | xargs -n1 basename
```

**Expected**:
- ✅ Exactly 6 skill directories
- ✅ Each has SKILL.md file
- ✅ Names match PROJECT.md (line 93)

---

## 2. Documentation Consistency ✅

### Command Count References
```bash
# Should all say "21 commands"
grep -r "commands" README.md plugins/autonomous-dev/README.md | grep -E "[0-9]+"
```

**Check these files**:
- [ ] `README.md` - "All 21 commands" (4 locations)
- [ ] `plugins/autonomous-dev/README.md` - "All 21 commands" (3 locations)
- [ ] `plugins/autonomous-dev/docs/COMMANDS.md` (if exists)

### Agent/Skill Count References
```bash
# Should say "8 agents"
grep -r "8 agents\|Agents (8)" PROJECT.md README.md plugins/autonomous-dev/README.md

# Should say "6 skills"
grep -r "6 skills\|Skills (6)" PROJECT.md README.md plugins/autonomous-dev/README.md
```

**Expected**:
- ✅ All references say "8 agents"
- ✅ All references say "6 skills"
- ✅ No outdated counts

### PROJECT.md Location
```bash
# Should exist at root (not .claude/)
test -f PROJECT.md && echo "✅ Found at root" || echo "❌ Missing"
test -f .claude/PROJECT.md && echo "⚠️  Old location exists" || echo "✅ No old location"
```

**Expected**:
- ✅ `PROJECT.md` exists at project root
- ✅ No `.claude/PROJECT.md` (old location)

---

## 3. Command Patterns ✅

### Interactive Menu Commands
```bash
# These should have "interactive menu" in description
for cmd in align-project sync-docs issue; do
  echo "Checking $cmd..."
  head -5 plugins/autonomous-dev/commands/$cmd.md | grep -i "menu\|interactive"
done
```

**Expected** (3 commands with menus):
- ✅ `align-project.md` - 4-option menu
- ✅ `sync-docs.md` - 6-option menu
- ✅ `issue.md` - 5-option menu

### Test Ladder Commands
```bash
# Should have 7 test commands
ls -1 plugins/autonomous-dev/commands/test*.md | wc -l
ls -1 plugins/autonomous-dev/commands/test*.md | xargs -n1 basename
```

**Expected** (7 test commands):
- ✅ test.md
- ✅ test-unit.md
- ✅ test-integration.md
- ✅ test-uat.md
- ✅ test-uat-genai.md
- ✅ test-architecture.md
- ✅ test-complete.md

### Commit Ladder Commands
```bash
# Should have 4 commit commands
ls -1 plugins/autonomous-dev/commands/commit*.md | wc -l
ls -1 plugins/autonomous-dev/commands/commit*.md | xargs -n1 basename
```

**Expected** (4 commit commands):
- ✅ commit.md
- ✅ commit-check.md
- ✅ commit-push.md
- ✅ commit-release.md

---

## 4. No Duplicate References ✅

### Old Command Names
```bash
# Should return 0 (no references to old commands)
grep -r "align-project-safe\|align-project-fix\|align-project-dry-run\|align-project-sync" \
  plugins/autonomous-dev --include="*.md" --exclude-dir=docs/milestones | wc -l

grep -r "sync-docs-auto\|sync-docs-api\|sync-docs-changelog\|sync-docs-organize" \
  plugins/autonomous-dev --include="*.md" --exclude-dir=docs/milestones | wc -l

grep -r "issue-auto\|issue-from-genai\|issue-from-test\|issue-preview\|issue-create" \
  plugins/autonomous-dev --include="*.md" --exclude-dir=docs/milestones | wc -l
```

**Expected**:
- ✅ 0 references to old alignment commands
- ✅ 0 references to old sync commands
- ✅ 0 references to old issue commands
- ⚠️  Historical docs (docs/milestones/) can have old names

### Old Paths
```bash
# Should return 0 (no references to .claude/PROJECT.md)
grep -r "\.claude/PROJECT\.md" plugins/autonomous-dev --include="*.md" --include="*.py" | wc -l
```

**Expected**:
- ✅ 0 references to `.claude/PROJECT.md`
- ✅ All references use `PROJECT.md` (root location)

---

## 5. Git Repository Health ✅

### No Uncommitted Changes
```bash
git status --short
```

**Expected**:
- ✅ No modified tracked files (M)
- ✅ No deleted files (D)
- ✅ Untracked files OK (session logs, artifacts)

### Clean Working Directory
```bash
# Root should only have essential .md files
ls -1 *.md

# Should be validation script
python scripts/validate_structure.py
```

**Expected**:
- ✅ Only README.md, CHANGELOG.md, CLAUDE.md, CONTRIBUTING.md, PROJECT.md at root
- ✅ Structure validation passes

### Recent Commits
```bash
# Last 5 commits should be clean
git log --oneline -5
```

**Check**:
- [ ] Commit messages follow conventional commits
- [ ] No "WIP" or "temp" commits
- [ ] Co-authored by Claude

---

## 6. User Journey Validation ✅

### Install → Setup → Usage
```bash
# Simulate user journey
echo "1. Install check"
test -f plugins/autonomous-dev/marketplace.json && echo "✅ Marketplace file exists"

echo "2. Setup check"
test -f plugins/autonomous-dev/commands/setup.md && echo "✅ Setup command exists"

echo "3. First command check"
test -f plugins/autonomous-dev/commands/align-project.md && echo "✅ Align command exists"
```

**Expected workflow**:
1. ✅ User runs `/plugin install autonomous-dev`
2. ✅ User runs `/setup` (creates PROJECT.md)
3. ✅ User runs `/align-project` (first alignment)
4. ✅ User runs `/test`, `/format`, `/commit` (daily workflow)

### README Clarity
```bash
# Check README has clear quick start
head -50 plugins/autonomous-dev/README.md | grep -i "quick\|install"
```

**Expected**:
- ✅ Quick install section within first 50 lines
- ✅ 3-step install process
- ✅ "Done!" message after install

---

## 7. Command Naming Consistency ✅

### Naming Conventions
```bash
# All commands should follow pattern
ls -1 plugins/autonomous-dev/commands/*.md | while read f; do
  basename "$f" | grep -E "^[a-z-]+\.md$" || echo "❌ Invalid name: $f"
done
```

**Rules**:
- ✅ Lowercase only
- ✅ Hyphens for word separation (no underscores)
- ✅ .md extension
- ✅ Descriptive names (verb-noun pattern preferred)

### Category Grouping
**Check these categories exist**:
- [ ] Testing: test-*
- [ ] Commit: commit-*
- [ ] Alignment: align-*
- [ ] Sync: sync-*
- [ ] Quality: format, security-scan, full-check
- [ ] Workflow: auto-implement, setup, uninstall

---

## 8. Safety & Rollback ✅

### Git Tags
```bash
# Should have version tags
git tag -l "v*" | tail -5
```

**Expected**:
- ✅ Tags follow semantic versioning (v2.0.0)
- ✅ Latest tag matches latest release

### Rollback Instructions
```bash
# Check CHANGELOG has rollback info
grep -A 5 "Rollback" CHANGELOG.md | head -10
```

**Expected**:
- ✅ CHANGELOG documents how to rollback major changes
- ✅ Git revert instructions provided

---

## Quick Validation Script

Run all checks at once:

```bash
#!/bin/bash
echo "=== CONSISTENCY VALIDATION ==="
echo

echo "1. File Counts"
echo "Commands: $(ls -1 plugins/autonomous-dev/commands/*.md | wc -l) (expected: 21)"
echo "Agents: $(ls -1 plugins/autonomous-dev/agents/*.md | wc -l) (expected: 8)"
echo "Skills: $(ls -1 plugins/autonomous-dev/skills/*/SKILL.md | wc -l) (expected: 6)"
echo

echo "2. No Versioned Files"
echo "Found: $(find plugins/autonomous-dev -name "*-v[0-9]*" | wc -l) (expected: 0)"
echo

echo "3. PROJECT.md Location"
test -f PROJECT.md && echo "✅ Found at root" || echo "❌ Missing at root"
test -f .claude/PROJECT.md && echo "⚠️  Old location exists" || echo "✅ No old location"
echo

echo "4. Structure Validation"
python scripts/validate_structure.py
echo

echo "5. Git Status"
git status --short | head -10
echo

echo "=== VALIDATION COMPLETE ==="
```

Save as `scripts/validate_consistency.sh` and run before releases.

---

## Checklist Summary

Before every release, verify:

- [ ] **File counts**: 21 commands, 8 agents, 6 skills
- [ ] **No duplicates**: No `-v2`, `-old`, `.bak` files
- [ ] **Documentation**: All counts updated (21, 8, 6)
- [ ] **PROJECT.md**: At root (not `.claude/`)
- [ ] **Command patterns**: Interactive menus documented
- [ ] **No old references**: Old command names removed
- [ ] **Git clean**: No uncommitted changes
- [ ] **User journey**: Install → Setup → Usage works
- [ ] **Naming**: All lowercase-with-hyphens
- [ ] **Rollback**: Instructions documented

**Total checks**: 30+
**Time**: ~5 minutes
**Frequency**: Before every release

---

**Use this checklist to ensure total consistency and easy understanding!**
