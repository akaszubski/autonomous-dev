# Testing Guide - PROJECT.md-First Architecture

**Purpose**: Verify that the PROJECT.md-first architecture works correctly after installation.

**Last Updated**: 2025-10-20

---

## Manual Testing (20 minutes)

### Part 1: Installation Test

**Step 1: Create Test Project**

```bash
# Create a fresh test project
mkdir -p /tmp/test-project
cd /tmp/test-project
git init
echo "# Test Project" > README.md
git add README.md
git commit -m "Initial commit"
```

**Step 2: Add Plugin Marketplace**

```bash
# In Claude Code
/plugin marketplace add akaszubski/autonomous-dev
```

**Expected**: Success message

**Step 3: Install Plugin**

```bash
# In Claude Code
/plugin install autonomous-dev
```

**Expected**:
- `.claude/` directory created
- `agents/`, `skills/`, `commands/`, `templates/` subdirectories
- `.env.example` file created

**Step 4: Verify Files**

```bash
ls -la .claude/agents/
# Expected: 8 agent files (orchestrator, planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master)

ls -la .claude/commands/
# Expected: align-project.md, align-project-safe.md (+ optional others)

ls -la .claude/templates/
# Expected: PROJECT.md

ls -la .env.example
# Expected: .env.example exists
```

---

### Part 2: PROJECT.md Alignment Test

**Step 1: Create PROJECT.md**

```bash
# In Claude Code
"Please create a PROJECT.md from the template for a simple todo app project"
```

**Expected**:
- `PROJECT.md` created
- Has GOALS, SCOPE, CONSTRAINTS sections
- Relevant to todo app context

**Step 2: Test Alignment Validation**

```bash
# In Claude Code
"Implement user authentication with OAuth2"
```

**Expected**:
- orchestrator reads PROJECT.md
- Checks if feature aligns with GOALS
- Asks if this is in SCOPE (if not explicitly listed)
- Proceeds only after validation

**Failure Test** (verify orchestrator blocks misaligned work):

```bash
# In Claude Code
"Implement a machine learning recommendation engine"
```

**Expected**:
- orchestrator reads PROJECT.md
- Identifies feature is OUT OF SCOPE for simple todo app
- Asks for confirmation or suggests updating PROJECT.md
- Does NOT proceed without alignment

---

### Part 3: Agent Coordination Test

**Test orchestrator coordinates all agents**

```bash
# In Claude Code
"Add a feature to create and list todos"
```

**Expected workflow** (watch for these steps):

```
1. ✅ orchestrator validates against PROJECT.md
2. 🔍 researcher agent searches for best practices
3. 📋 planner agent creates architecture plan (opus model)
4. ✅ test-master writes FAILING tests first (TDD)
5. 💻 implementer makes tests PASS
6. 👀 reviewer checks code quality
7. 🔒 security-auditor scans for vulnerabilities
8. 📚 doc-master updates documentation
9. 💬 orchestrator prompts: "Run /clear for next feature"
```

**Success indicators**:
- PROJECT.md checked first (PRIMARY)
- All agents execute in order
- TDD enforced (tests before code)
- Prompt to /clear at end

---

### Part 4: /align-project Command Test

**Test Phase 1: Analysis Only**

```bash
# In Claude Code
/align-project
```

**Expected**:
- Read-only analysis (NO changes made)
- Reports on:
  - PROJECT.md status
  - Folder structure
  - Documentation coverage
  - Test coverage
  - Security issues
  - Code quality
- Provides score (0-100)
- Asks questions about unclear items

**Test Phase 2: Generate PROJECT.md**

```bash
# In test project without PROJECT.md
rm PROJECT.md

# In Claude Code
/align-project --generate-project-md
```

**Expected**:
- Analyzes codebase
- Infers GOALS, SCOPE, CONSTRAINTS from code
- Creates DRAFT in `docs/draft/PROJECT.md`
- Does NOT overwrite existing PROJECT.md
- Asks user to review and move to `PROJECT.md`

**Test Phase 3: Interactive Alignment**

```bash
# In Claude Code
/align-project --interactive
```

**Expected**:
- Proposes ONE change at a time
- Shows before/after diff
- Asks for approval: [Y]es, [N]o, [D]elete, [S]how contents, [Stop]
- Commits after EACH approved change (git commit)
- User can undo by reverting commits

---

### Part 5: GitHub Integration Test (Optional)

**Step 1: Setup GitHub Auth**

```bash
cp .env.example .env

# Edit .env
# Add your token from https://github.com/settings/tokens
# Required scopes: repo, read:org
echo "GITHUB_TOKEN=ghp_your_token_here" >> .env

# Verify .env is gitignored
git status
# Should NOT show .env as untracked
```

**Step 2: Create GitHub Milestone**

```bash
# Create milestone matching sprint in PROJECT.md
gh api repos/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/milestones \
  -f title="Sprint 1" \
  -f description="Test sprint" \
  -f state="open"
```

**Step 3: Update PROJECT.md**

```bash
# In PROJECT.md
## CURRENT SPRINT
**Sprint Name**: Sprint 1
**GitHub Milestone**: Sprint 1
```

**Step 4: Test GitHub Integration**

```bash
# In Claude Code
"Check current sprint status"
```

**Expected**:
- orchestrator loads .env
- Queries GitHub API for "Sprint 1" milestone
- Shows issues in sprint
- Reports progress

**Failure Test** (verify graceful degradation):

```bash
# Remove .env
rm .env

# In Claude Code
"Check current sprint status"
```

**Expected**:
- orchestrator detects no .env
- Warns: "GitHub sync disabled"
- Continues based on PROJECT.md alone
- Does NOT crash or fail

---

### Part 6: Model Optimization Test

**Verify agents use correct models**

```bash
# Check agent frontmatter
grep "^model:" .claude/agents/*.md
```

**Expected output**:
```
orchestrator.md:model: sonnet
planner.md:model: opus
researcher.md:model: sonnet
test-master.md:model: sonnet
implementer.md:model: sonnet
reviewer.md:model: sonnet
security-auditor.md:model: haiku
doc-master.md:model: haiku
```

**Cost test** (verify haiku for fast tasks):

```bash
# In Claude Code
"Run security scan on this project"
```

**Expected**:
- security-auditor uses haiku model (fast & cheap)
- Completes in <5 seconds
- Reports vulnerabilities

---

### Part 7: Context Management Test

**Test context stays under 8K tokens**

```bash
# In Claude Code
"Implement 3 features: add todo, list todos, delete todo"

# After each feature, orchestrator should prompt:
# "Run /clear for next feature"
```

**Expected**:
- After feature 1: orchestrator prompts /clear
- You run: /clear
- After feature 2: orchestrator prompts /clear
- You run: /clear
- After feature 3: orchestrator prompts /clear

**Without /clear test**:

```bash
# Don't run /clear between features
# Implement 5-6 features in a row
```

**Expected**:
- Context grows to 30K+ tokens
- Responses slow down
- Eventually hit context limit
- **This demonstrates WHY /clear is important**

---

## Advanced Feature Tests

### Test 1: Smart Diff View

```bash
# In Claude Code
/align-project --interactive
```

**Expected**:
- Shows unified diff of all proposed changes
- Each change has risk score (LOW, MEDIUM, HIGH)
- Grouped by category (File Organization, Documentation, etc.)

### Test 2: Dry Run with Stash

```bash
# In Claude Code
/align-project --dry-run
```

**Expected**:
- Applies all changes
- Runs tests
- Stashes changes
- Shows results
- Asks: Apply or discard?

### Test 3: Pattern Learning

```bash
# In Claude Code
/align-project --interactive

# When asked about archiving old files:
# Choose: [A]rchive

# Next time:
/align-project --interactive
```

**Expected**:
- Remembers previous "Archive" decision
- Asks: "Automatically archive similar files in future? [Y/N]"
- Saves preference to `.claude/alignment-preferences.json`

### Test 4: Conflict Resolution

```bash
# Create conflict: PROJECT.md says "Sprint 2", GitHub says "Sprint 4"

# In Claude Code
/align-project --interactive
```

**Expected**:
- Detects conflict
- Shows: "PROJECT.md says: Sprint 2 | Reality is: Sprint 4"
- Asks: "[P]ROJECT.md correct or [R]eality correct?"
- Updates based on user choice

### Test 5: Progressive Enhancement

```bash
# In Claude Code
/align-project --level 1  # Quick wins (5 min)
```

**Expected**:
- Only LOW risk changes
- Score increases: 45 → 70

```bash
/align-project --level 2  # Structural (15 min)
```

**Expected**:
- MEDIUM risk changes
- Score increases: 70 → 85

```bash
/align-project --level 3  # Deep work (30 min)
```

**Expected**:
- HIGH risk changes
- Score increases: 85 → 100

### Test 6: Undo Stack

```bash
# In Claude Code
/align-project --interactive

# Make several changes, then:
# Press [U]ndo
```

**Expected**:
- Shows visual history:
  ```
  ✅ 6. Updated pytest.ini
  ✅ 5. Added .env to .gitignore
  ❌ 3. Moved test/ to tests/   ← YOU ARE HERE
  ```
- Options: [U]ndo [R]edo [J]ump to N [F]inish
- Each undo reverts a git commit

### Test 7: Simulation Mode

```bash
# In Claude Code
/align-project --simulate
```

**Expected**:
- Creates temp copy: `/tmp/project-simulation/`
- Applies ALL changes to copy
- Shows path
- User can `cd` to explore
- Then: Apply all or discard all

---

## Troubleshooting

### Issue: orchestrator doesn't check PROJECT.md

**Diagnosis**:
```bash
grep "PRIMARY MISSION" .claude/agents/orchestrator.md
```

**Expected**: Should find "PRIMARY MISSION: Ensure all work aligns with PROJECT.md"

**Fix**: Reinstall plugin or manually update orchestrator.md

### Issue: Agents use wrong models

**Diagnosis**:
```bash
grep "^model:" .claude/agents/planner.md
```

**Expected**: `model: opus`

**Fix**: Update agent frontmatter with correct model

### Issue: /align-project command not found

**Diagnosis**:
```bash
ls .claude/commands/align-project*.md
```

**Expected**: Both `align-project.md` and `align-project-safe.md`

**Fix**: Reinstall plugin

### Issue: GitHub integration not working

**Diagnosis**:
```bash
cat .env | grep GITHUB_TOKEN
```

**Expected**: `GITHUB_TOKEN=ghp_...`

**Fix**:
1. Create token at https://github.com/settings/tokens
2. Add to `.env`
3. Verify `.env` in `.gitignore`

### Issue: Context budget exceeded

**Diagnosis**: Forgot to run `/clear` between features

**Fix**:
```bash
# In Claude Code
/clear
```

**Prevention**: Run `/clear` after EVERY feature (orchestrator prompts you)

---

## Success Criteria

✅ All automated tests pass (green checkmarks)
✅ orchestrator validates PROJECT.md before features
✅ All 8 agents coordinate correctly
✅ /align-project runs 3 phases successfully
✅ GitHub integration works (if configured) or degrades gracefully
✅ Correct models used (opus/sonnet/haiku)
✅ Context stays under 8K with /clear
✅ All 7 advanced features work

---

## Cleanup

```bash
# Remove test project
rm -rf /tmp/test-project

# Or keep for future testing
```

---

## Reporting Issues

If any tests fail:

1. **Check version**:
   ```bash
   grep "^## Version" plugins/autonomous-dev/README.md
   ```
   Expected: v2.0.0 or higher

2. **Report issue**:
   - Go to: https://github.com/akaszubski/autonomous-dev/issues
   - Title: "Test failed: [describe which test]"
   - Include: test-results.txt output
   - Include: Steps to reproduce

---

**Last Updated**: 2025-10-20
