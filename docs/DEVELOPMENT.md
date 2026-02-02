# Development Guide - Dogfooding Setup

**Last Updated**: 2025-11-03
**For**: Contributors developing the autonomous-dev plugin
**Status**: Required reading for all development sessions

---

## TL;DR - Start Here Every Session

```bash
# 1. Check you're in the repo
pwd  # Should show: ${PROJECT_ROOT}

# 2. After ANY file changes, resync
./scripts/resync-dogfood.sh  # Copies plugins/* → .claude/* (no restart needed!)

# 3. Test auto-orchestration works
# Just type: "Add a simple hello function"
# You should see: 🎯 Feature Request Detected

# 4. View what agents did
./scripts/view-last-session.sh

# 5. Make changes → resync → test (fast iteration!)
vim plugins/autonomous-dev/hooks/some-hook.py
./scripts/resync-dogfood.sh  # Live reload!
# Test immediately in Claude Code
```

**That's it.** Resync after changes, test immediately.

---

## Understanding Dogfooding

**Dogfooding** = Using the plugin to develop the plugin itself

**Why this is tricky**:
- You're both a **developer** (writing code) AND a **user** (testing the plugin)
- Plugin files are in the repo, but hooks/agents need to be "active"
- Changes to plugin affect YOUR development workflow immediately
- Need to test features without breaking your ability to develop

**What's different from normal users**:
- Normal users: Install plugin → hooks/agents work automatically
- You: Edit plugin files → need to test they work → commit changes → release to users

---

## Repository Structure (Developer View)

```
autonomous-dev/
├── .claude/                          # YOUR dogfooding config (gitignored locally)
│   ├── PROJECT.md                    # THIS project's strategic direction
│   ├── settings.local.json           # YOUR hooks/config (active in this project)
│   └── hooks/                        # Hooks YOU'RE using while developing
│
├── plugins/autonomous-dev/           # THE PLUGIN (what users get)
│   ├── agents/                       # 22 agent definitions (21 active)
│   ├── skills/                       # 28 skill definitions
│   ├── commands/                     # 7 command definitions (3 archived)
│   ├── hooks/                        # 45 hook implementations
│   └── README.md                     # User-facing docs
│
├── docs/                             # Developer/contributor docs
│   ├── DEVELOPMENT.md               # This file (YOU ARE HERE)
│   ├── BLOAT-DETECTION-CHECKLIST.md # Feature validation gates
│   ├── ISSUE-ALIGNMENT-ANALYSIS.md  # Current issues categorized
│   └── ANTI-BLOAT-PHILOSOPHY.md     # Design principles
│
├── scripts/                          # Development utilities
│   ├── view-last-session.sh         # See what agents did
│   ├── test-autonomous-workflow.sh  # UAT test suite
│   └── session_tracker.py           # Session logging utility
│
└── tests/                            # Plugin tests
    ├── unit/                         # Unit tests
    ├── integration/                  # Integration tests
    └── uat/                          # User acceptance tests
```

**Key distinction**:
- `.claude/` = YOUR development environment (dogfooding)
- `plugins/autonomous-dev/` = THE PRODUCT (what ships to users)

---

## Dogfooding Setup (First Time)

**IMPORTANT**: The `/plugin` commands are buggy. Manual cleanup is required for reliable installs.

### Step 1: Complete Uninstall (If Previously Installed)

```bash
# 1. In Claude Code
/plugin uninstall autonomous-dev

# 2. Exit Claude Code (Cmd+Q or Ctrl+Q)

# 3. Manual cleanup (while Claude Code is CLOSED)
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
rm -f ~/.claude/plugins/installed_plugins.json
rm -f ~/.claude/plugins/known_marketplaces.json

# This ensures completely clean state
```

### Step 2: Reinstall from GitHub

```bash
# 1. Start Claude Code

# 2. Add marketplace
/plugin marketplace add akaszubski/autonomous-dev

# 3. Install plugin
/plugin install autonomous-dev

# This installs to: ~/.claude/plugins/marketplaces/autonomous-dev/

# 4. Exit Claude Code again (REQUIRED!)
```

### Step 3: Run Bootstrap Script

```bash
# 1. Restart Claude Code

# 2. In your autonomous-dev repo:
cd ${PROJECT_ROOT}

# 3. Run bootstrap (copies plugin files to project)
bash install.sh

# What this does:
# - Copies commands to .claude/commands/
# - Copies hooks to .claude/hooks/
# - Copies templates to .claude/templates/
# - Creates .autonomous-dev-bootstrapped marker
```

**Why bootstrap is required**:
- `/plugin install` only installs to `~/.claude/plugins/`
- Commands must be in `.claude/commands/` (per-project)
- Hooks must be in `.claude/hooks/` (per-project)
- Bootstrap copies: plugin → your project

### Step 4: Verify Installation

```bash
# Check commands copied
ls -la .claude/commands/*.md | wc -l    # Should be 7-8

# Check hooks copied
ls -la .claude/hooks/*.py | wc -l      # Should be 28+

# Check settings configured
cat .claude/settings.local.json | grep detect_feature_request
```

### Step 4.5: Create Development Symlink

**Why This Is Needed**: Python package names cannot contain hyphens. The plugin
directory is `autonomous-dev` (with hyphen for clarity), but Python imports require
`autonomous_dev` (with underscore). A symlink bridges this gap.

**Security Note**: This symlink is safe - it uses a relative path within the repository
and is automatically gitignored.

#### macOS/Linux

```bash
cd plugins
ln -s autonomous-dev autonomous_dev
```

#### Windows (Command Prompt - Run as Administrator)

```cmd
cd plugins
mklink /D autonomous_dev autonomous-dev
```

#### Windows (PowerShell - Run as Administrator)

```powershell
cd plugins
New-Item -ItemType SymbolicLink -Path "autonomous_dev" -Target "autonomous-dev"
```

#### Verify Symlink Creation

**macOS/Linux**:
```bash
ls -la plugins/ | grep autonomous_dev
# Expected output: autonomous_dev -> autonomous-dev
```

**Windows**:
```cmd
dir plugins\ | findstr autonomous_dev
# Expected output: <SYMLINKD> autonomous_dev [autonomous-dev]
```

#### Test Import

```bash
python -c "from autonomous_dev.lib import security_utils; print('✓ Import works')"
# Should print: ✓ Import works
```

**Troubleshooting**: If you encounter `ModuleNotFoundError`, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**Note**: The symlink is gitignored automatically (see `.gitignore`). Do not commit it to the repository.

### Step 5: Restart Claude Code One More Time

```bash
# Exit Claude Code (Cmd+Q)
# Restart Claude Code
# All commands should now work
```

### Step 6: Check Local Config

```bash
# Verify .claude/settings.local.json exists
cat .claude/settings.local.json

# Should include:
# - UserPromptSubmit hook with detect_feature_request.py
# - PreCommit hooks for validation
# - SubagentStop hook for session logging
```

**If `.claude/settings.local.json` doesn't exist**, create it:

```bash
# Copy from template (if one exists)
cp .claude/settings.json.template .claude/settings.local.json

# Or create minimal config:
cat > .claude/settings.local.json << 'EOF'
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "description": "Auto-detect feature requests",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/detect_feature_request.py"
          }
        ]
      }
    ]
  }
}
EOF
```

### Step 3: Test Hooks Work

```bash
# Test feature detection
echo "implement user authentication" | python .claude/hooks/detect_feature_request.py
# Should exit 0 (feature detected)

echo "what is the weather" | python .claude/hooks/detect_feature_request.py
# Should exit 1 (not a feature)

# Test session viewer
./scripts/view-last-session.sh
# Should show "No sessions found" or last session details
```

### Step 4: Test Auto-Orchestration

**In Claude Code**, type a feature request:
```
Add a simple hello world function
```

**Expected behavior**:
1. 🎯 Detection message appears
2. I (Claude) automatically invoke `/implement`
3. orchestrator validates PROJECT.md
4. Agents run (you'll see me using Task tool)
5. Session logs created in `docs/sessions/`

**If nothing happens**:
- Hook isn't active in this session
- Check: `cat .claude/settings.local.json`
- Verify: Hook file exists at `.claude/hooks/detect_feature_request.py`
- May need to restart Claude Code

---

## Daily Development Workflow

### Starting a Development Session

**Every time you start working on this repo:**

1. **Orient yourself**:
   ```bash
   pwd  # Confirm you're in autonomous-dev repo
   git status  # Check what's changed
   cat .claude/PROJECT.md | head -20  # Review goals
   ```

2. **Check dogfooding is active**:
   ```bash
   # Quick test - this should detect feature
   echo "implement auth" | python .claude/hooks/detect_feature_request.py && echo "✅ Hooks work"
   ```

3. **Review current priorities**:
   ```bash
   cat docs/ISSUE-ALIGNMENT-ANALYSIS.md | grep "Tier 1"
   gh issue list --label enhancement | head -5
   ```

4. **Update Claude** (tell me in chat):
   ```
   I'm working on autonomous-dev plugin development.
   Current focus: [your focus area]
   Review docs/DEVELOPMENT.md for context.
   ```

### Quick Resync (Use This Constantly!)

**After ANY change to plugin files**, resync to .claude/:

```bash
# Fast - just copies changed files
./scripts/resync-dogfood.sh

# What it does:
# - Copies plugins/autonomous-dev/commands/*.md → .claude/commands/
# - Copies plugins/autonomous-dev/hooks/*.py → .claude/hooks/
# - Copies plugins/autonomous-dev/templates/* → .claude/templates/
# - No restart needed (live reload)!
```

**When to resync**:
- ✅ Changed a hook → `./scripts/resync-dogfood.sh` + **FULL RESTART REQUIRED**
- ✅ Changed a command → `./scripts/resync-dogfood.sh` + **FULL RESTART REQUIRED**
- ✅ Changed a template → `./scripts/resync-dogfood.sh` (no restart needed)
- ⚠️ Changed settings.local.json → **FULL RESTART REQUIRED**
- ⚠️ Changed an agent → must push to GitHub + reinstall + **FULL RESTART REQUIRED**

**CRITICAL: Understanding Restarts**

Claude Code caches command definitions and hooks in memory at startup. **`/exit` is NOT enough** to reload changes!

**What doesn't work**:
- ❌ `/exit` - Only ends conversation, process keeps running
- ❌ Closing window - Process may run in background
- ❌ `/clear` - Only clears conversation history

**What works**:
- ✅ Press `Cmd+Q` (Mac) or `Ctrl+Q` (Windows/Linux) to fully quit
- ✅ Verify process is dead: `ps aux | grep claude | grep -v grep` (should return nothing)
- ✅ Wait 5 seconds
- ✅ Restart Claude Code

**Typical workflow**:
```bash
# 1. Edit command
vim plugins/autonomous-dev/commands/new-feature.md

# 2. Resync to .claude/
./scripts/resync-dogfood.sh

# 3. FULL RESTART (CRITICAL!)
# Press Cmd+Q to fully quit Claude Code
# Verify: ps aux | grep claude | grep -v grep
# Wait 5 seconds
# Restart Claude Code

# 4. Test the command
/new-feature  # Should now work with your changes
```

---

### Making Changes

**When implementing a feature:**

1. **Validate against bloat gates**:
   ```bash
   # Before coding, review gates
   cat docs/BLOAT-DETECTION-CHECKLIST.md

   # Does this feature pass all 4 gates?
   # - Alignment: Serves primary mission?
   # - Constraint: Respects boundaries?
   # - Minimalism: Simplest solution?
   # - Value: Benefit > complexity?
   ```

2. **Document your decision**:
   ```bash
   # In GitHub issue, add comment:
   gh issue comment <number> --body "
   ✅ Bloat Check Passed:
   - Alignment: [why this serves mission]
   - Constraint: [how it respects limits]
   - Minimalism: [why this is simplest]
   - Value: [benefit vs complexity]
   "
   ```

3. **Implement with TDD**:
   ```bash
   # Write test first
   vim tests/unit/test_<feature>.py

   # Run test (should fail)
   pytest tests/unit/test_<feature>.py -v

   # Implement feature
   vim plugins/autonomous-dev/<area>/<file>

   # Run test (should pass)
   pytest tests/unit/test_<feature>.py -v
   ```

4. **Test locally before committing**:
   ```bash
   # Test the feature works
   # (e.g., if you added a hook, test it runs)

   # View session logs to see what happened
   ./scripts/view-last-session.sh

   # Run full test suite
   ./scripts/test-autonomous-workflow.sh
   ```

5. **Commit with validation**:
   ```bash
   git add .
   git commit -m "feat: add <feature>"

   # PreCommit hooks will run:
   # - unified_doc_validator.py (consolidates validate_project_alignment, validate_docs_consistency, etc.)
   # - unified_code_quality.py (consolidates security_scan, auto_generate_tests, etc.)
   # - unified_doc_auto_fix.py (consolidates auto_update_docs, auto_fix_docs, etc.)

   # If any fail, fix issues and retry
   ```

### Testing Changes

**After implementing a feature:**

```bash
# 1. Unit tests
pytest tests/unit/ -v

# 2. Integration tests
pytest tests/integration/ -v

# 3. UAT test (full workflow)
./scripts/test-autonomous-workflow.sh

# 4. Manual test (dogfood it!)
# Use the feature in YOUR development
# Does it make YOUR life easier?

# 5. View session logs
./scripts/view-last-session.sh
# Did agents run as expected?
```

### Ending a Development Session

**Before you stop working:**

```bash
# 1. Commit or stash work
git status
git add .
git commit -m "wip: <description>" || git stash

# 2. Document next steps
echo "Next session: [what to work on]" >> docs/sessions/next-steps.txt

# 3. Clear Claude context (if needed)
# Just type: /clear
# This helps next session start fresh
```

---

## Common Development Scenarios

### Scenario 1: Testing Auto-Orchestration

**Goal**: Verify feature detection → orchestrator → agents pipeline

```bash
# 1. Verify hook is configured
cat .claude/settings.local.json | grep detect_feature_request

# 2. Test hook directly
echo "implement auth" | python .claude/hooks/detect_feature_request.py
echo $?  # Should be 0

# 3. Test in Claude Code (type this in chat):
"Add a simple greeting function"

# 4. Check if orchestrator ran
./scripts/view-last-session.sh | grep orchestrator

# 5. Check if session logs created
ls -lt docs/sessions/ | head -5
```

**Expected**: Feature detected → orchestrator validates → agents run → session logged

**If broken**: Check settings.local.json, verify hook file exists, restart Claude Code

---

### Scenario 2: Adding a New Agent

**Goal**: Create a new specialist agent and test it

```bash
# 1. Create agent file
vim plugins/autonomous-dev/agents/my-new-agent.md

# 2. Follow agent template structure:
# ---
# name: my-new-agent
# description: What this agent does
# tools: [Read, Write, Edit, Bash, Grep, Glob]
# model: sonnet
# ---
# [Agent system prompt here]

# 3. Test agent manually
# In Claude Code: /plugin invoke my-new-agent "test task"

# 4. Update agent count in docs
# - .claude/PROJECT.md (update agent count)
# - CLAUDE.md (update agent count)
# - README.md (add agent to list)

# 5. Run alignment check (unified_doc_validator consolidates alignment checks)
python .claude/hooks/unified_doc_validator.py

# 6. Commit
git add plugins/autonomous-dev/agents/my-new-agent.md
git commit -m "feat: add my-new-agent specialist"
```

### Scenario 2.5: Integrating Checkpoints in Agents (Issue #79)

**Goal**: Add checkpoint tracking to an agent without hardcoded paths

```bash
# 1. Use the class method (no instance management needed)
from agent_tracker import AgentTracker

# Save checkpoint when agent completes
success = AgentTracker.save_agent_checkpoint(
    agent_name='my-agent',
    message='Completed task description',
    github_issue=79,
    tools_used=['Read', 'Write', 'Bash']
)

# Returns True if saved, False if skipped (graceful degradation)
if success:
    print("✅ Checkpoint saved to docs/sessions/")

# 2. Works from any directory:
#    - User projects (no plugins/ directory)
#    - Project subdirectories
#    - Fresh installs on different machines

# 3. No hardcoded paths:
#    - Uses path_utils for dynamic project root detection
#    - Path validation prevents traversal attacks (CWE-22)
#    - Graceful degradation if infrastructure unavailable

# 4. Example in agent workflow:
#    ---
#    name: my-agent
#    ...
#    ---
#    Agent is researching patterns...
#    
#    (agent does work)
#    
#    from agent_tracker import AgentTracker
#    AgentTracker.save_agent_checkpoint(
#        agent_name='my-agent',
#        message='Found 5 patterns in codebase'
#    )

# 5. Test checkpoint was saved:
ls -lt docs/sessions/ | head -3  # Should show recent session file
cat docs/sessions/$(ls -t docs/sessions/ | head -1)  # View session data
```

**Key Design Patterns**:
- **Progressive Enhancement**: Works with or without tracking infrastructure
- **Portable Paths**: Uses path_utils instead of hardcoded paths (solves Issue #79)
- **Two-tier Design**: Library method (not subprocess call)
- **Non-blocking**: Never raises exceptions, always allows workflow to continue

**Security**:
- Input validation: agent_name, message, github_issue all validated
- Path validation: All paths checked against project root
- No subprocess: Uses library imports (prevents shell injection)
- Graceful degradation: User projects work without error

**Related**: GitHub Issue #79 (Dogfooding bug - hardcoded paths), Issue #82 (Optional checkpoint verification)

See: LIBRARIES.md Section 24 (agent_tracker.py) for complete API documentation


---

### Scenario 3: Modifying a Hook

**Goal**: Change hook behavior and test it

```bash
# 1. Edit hook file
vim plugins/autonomous-dev/hooks/<hook-name>.py

# 2. Test hook directly (before committing)
python plugins/autonomous-dev/hooks/<hook-name>.py

# 3. Test hook in workflow
git add .
git commit -m "test"  # Hook will run

# 4. If hook fails, see error
# Fix and retry

# 5. If hook passes, amend commit message
git commit --amend -m "feat: improve <hook-name>"
```

---

### Scenario 4: Validating Against Bloat

**Goal**: Check if a feature proposal passes bloat gates

```bash
# 1. Read the proposal
gh issue view <number>

# 2. Run through checklist
cat docs/BLOAT-DETECTION-CHECKLIST.md

# 3. Answer 4 gates:
# Gate 1 (Alignment): Does it serve primary mission?
#   - Autonomous execution? Y/N
#   - SDLC enforcement? Y/N
#   - AI-powered speed? Y/N

# Gate 2 (Constraint): Does it respect boundaries?
#   - Commands ≤ 8? (current: 7) Y/N
#   - GenAI reasoning? Y/N
#   - Hooks enforce, agents enhance? Y/N

# Gate 3 (Minimalism): Simplest solution?
#   - Solves observed problem? Y/N
#   - Can't use existing features? Y/N
#   - Implementation ≤ 200 LOC? Y/N

# Gate 4 (Value): Benefit > complexity?
#   - Saves time measurably? Y/N
#   - Makes automation reliable? Y/N
#   - Makes workflow observable? Y/N

# 4. Document decision
gh issue comment <number> --body "✅ All gates passed"
# OR
gh issue comment <number> --body "❌ Gate X failed: [reason]"
gh issue close <number>
```

---

## Troubleshooting

### Hook Not Running

**Symptom**: Type feature request, nothing happens

**Diagnose**:
```bash
# 1. Check hook configured
cat .claude/settings.local.json | grep detect_feature_request

# 2. Check hook file exists
ls -la .claude/hooks/detect_feature_request.py

# 3. Test hook directly
echo "implement auth" | python .claude/hooks/detect_feature_request.py
echo $?  # Should be 0
```

**Fix**:
- If missing from settings: Add to `.claude/settings.local.json`
- If file missing: Copy from `plugins/autonomous-dev/hooks/`
- If test fails: Check Python errors, fix hook

---

### Session Logs Not Created

**Symptom**: `./scripts/view-last-session.sh` shows "No sessions found"

**Diagnose**:
```bash
# 1. Check session directory exists
ls -la docs/sessions/

# 2. Check SubagentStop hook configured
cat .claude/settings.local.json | grep SubagentStop

# 3. Check session tracker script exists (deprecated v3.28.0+, see Issue #79)
ls -la scripts/session_tracker.py
# OR: ls -la plugins/autonomous-dev/scripts/session_tracker.py (current location)
```

**Fix**:
- If directory missing: `mkdir -p docs/sessions/`
- If hook missing: Add SubagentStop hook to settings
- If script missing (root): Now delegated to lib version, use plugin version instead
- **Note**: `scripts/session_tracker.py` deprecated v3.28.0 (Issue #79), will be removed v4.0.0
  - Use `plugins/autonomous-dev/scripts/session_tracker.py` for current implementations
  - Library: `plugins/autonomous-dev/lib/path_utils.py` handles dynamic project root detection

---

### Agents Not Invoking

**Symptom**: orchestrator runs but doesn't invoke other agents

**Diagnose**:
```bash
# 1. Check orchestrator prompt
cat plugins/autonomous-dev/agents/orchestrator.md | grep -A 10 "invoke"

# 2. Check session logs for orchestrator decision
./scripts/view-last-session.sh | grep -i "invoke\|agent"

# 3. Check if agents exist
ls -la plugins/autonomous-dev/agents/ | wc -l  # Should be 19
```

**Fix**:
- If orchestrator prompt weak: Enhance to explicitly invoke agents
- If agents missing: Verify plugin structure
- If orchestrator doesn't mention agents: See issue #32

---

### PreCommit Hooks Failing

**Symptom**: `git commit` blocked by hook failure

**Diagnose**:
```bash
# 1. See which hook failed (shown in commit output)
# Example: "unified_doc_validator.py failed" (consolidates validate_project_alignment, validate_claude_alignment, etc.)

# 2. Run hook manually to see error
python .claude/hooks/<hook-name>.py

# 3. Check what the hook validates (note: see docstring for env vars to control validators)
cat .claude/hooks/<hook-name>.py | head -50
```

**Fix**:
- Read error message carefully
- Fix the validation issue (e.g., update PROJECT.md alignment)
- Retry commit
- If hook is broken, fix hook and commit

---

## Reference: Key Commands

```bash
# Check dogfooding setup
cat .claude/settings.local.json | grep -E "detect_feature|SubagentStop"

# View last session
./scripts/view-last-session.sh

# Test workflow
./scripts/test-autonomous-workflow.sh

# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Check bloat gates
cat docs/BLOAT-DETECTION-CHECKLIST.md

# View issue analysis
cat docs/ISSUE-ALIGNMENT-ANALYSIS.md

# Check PROJECT.md alignment
cat .claude/PROJECT.md | grep -A 5 "GOALS"

# View anti-bloat philosophy
cat docs/ANTI-BLOAT-PHILOSOPHY.md

# Check hook exists
ls -la .claude/hooks/<hook-name>.py

# Test hook directly
python .claude/hooks/<hook-name>.py

# View commit hooks configured
cat .claude/settings.local.json | jq .hooks.PreCommit

# Check agent count
ls -la plugins/autonomous-dev/agents/ | wc -l

# Check command count
ls -la plugins/autonomous-dev/commands/*.md | wc -l
```

---

## Code Quality Standards (Ruff Linting)

**Tool**: Ruff is used for automated code quality checks across the Python codebase.

**Configuration**: See `pyproject.toml` for complete Ruff settings including line length, import rules, and error codes.

**Running Linting**:
```bash
# Check for all issues (no fixes)
ruff check plugins/autonomous-dev/ tests/

# Check specific rule (e.g., unused imports F401)
ruff check --select F401 plugins/autonomous-dev/ tests/

# Auto-fix issues (import organization, formatting)
ruff check --fix plugins/autonomous-dev/ tests/

# Auto-format code
ruff format plugins/autonomous-dev/ tests/
```

**Common Rules**:
- **F401**: Unused imports (dead code) - Fixed via `ruff check --fix`
- **E501**: Line too long - Check via `ruff check`, configure max length in pyproject.toml
- **I**: Import organization - Fixed automatically
- **UP**: Python upgrade suggestions - Check via `ruff check`

**Pre-Commit Integration**:
Ruff checks run as part of PreCommit hooks. Fix issues before committing:
```bash
# Run before committing
ruff check --fix plugins/autonomous-dev/ tests/
git add -A
git commit -m "refactor: Fix linting issues"
```

**Dead Code Cleanup History**:
- **Issue #163** (v3.45.0): Removed 157 unused imports across 104 Python files using Ruff F401 rule
  - Scope: Core plugin code, agents, hooks, libraries, and test files
  - Impact: Improved code cleanliness, reduced namespace pollution

---

## Quick Validation Checklist

**Before starting any session:**
- [ ] In autonomous-dev repo (`pwd` check)
- [ ] Dogfooding config active (settings.local.json exists)
- [ ] Hooks work (test detect_feature_request.py)
- [ ] Session viewer works (`./scripts/view-last-session.sh`)

**Before implementing a feature:**
- [ ] Issue passes all 4 bloat gates
- [ ] Decision documented in issue comments
- [ ] Implementation plan clear
- [ ] ≤ 200 LOC estimated

**Before committing:**
- [ ] Tests written and passing
- [ ] Feature tested locally (dogfooded)
- [ ] Session logs show expected behavior
- [ ] Documentation updated

**After committing:**
- [ ] PreCommit hooks passed
- [ ] Changes pushed to GitHub
- [ ] Issue updated with progress
- [ ] Next steps documented

---

## Planning & Issue Management (Hybrid Approach)

### The Hybrid System

**High-level plan** (in repo): `DEVELOPMENT_PLAN.md`
- Overview of phases
- Success criteria
- Progress tracking
- Links to GitHub issues

**Detailed tasks** (on GitHub): Issues, Projects, Milestones
- Specific implementation details
- Comments and discussion
- Native GitHub features (automation, tracking, labels)

**Benefits**: Best of both worlds - plan survives GitHub, GitHub handles tracking

### Working with the Plan

**View the current plan**:
```bash
cat DEVELOPMENT_PLAN.md

# Or view on GitHub:
https://github.com/akaszubski/autonomous-dev/blob/master/DEVELOPMENT_PLAN.md
```

**Find issues to work on**:
```bash
# View Phase 1 (current focus)
gh issue list --label "Tier-1"

# View all open issues
gh issue list

# View specific phase
gh issue list --label "Tier-2"
```

**When working on an issue**:
```bash
# 1. Pick an issue from current phase
gh issue view 38

# 2. Validate against bloat gates
cat docs/BLOAT-DETECTION-CHECKLIST.md

# 3. Comment to claim it
gh issue comment 38 --body "Working on this now"

# 4. Implement (see "Making Changes" section above)

# 5. Close when done
gh issue close 38 --comment "✅ Completed: [description]"
```

**Update the plan** (weekly or when phases change):
```bash
vim DEVELOPMENT_PLAN.md

# Update:
# - Progress percentages
# - Completed issues (move to "Recently Completed")
# - Phase status
# - Metrics

git add DEVELOPMENT_PLAN.md
git commit -m "docs: update development plan progress"
git push
```

### Creating New Issues

**When you identify new work**:
```bash
# Create issue with appropriate labels
gh issue create \
  --title "Feature: Add X" \
  --body "Description..." \
  --label "Tier-1"  # or Tier-2, Tier-3, validate-need

# Link to epic if relevant
gh issue comment <new-issue> --body "Part of #41"
```

### Issue Labels

- **Tier-1**: Phase 1 (Foundation) - Critical, current focus
- **Tier-2**: Phase 2 (Automation) - Important, planned next
- **Tier-3**: Phase 3 (Polish) - Future enhancements
- **validate-need**: Backlog, need validation before implementing
- **enhancement**: New feature
- **bug**: Something broken
- **documentation**: Docs only

**View issues by label**:
```bash
gh issue list --label "Tier-1"
gh issue list --label "validate-need"
```

---

## Next Steps

**You should now**:

1. **Save this file** (it's your development bible)
2. **Test dogfooding setup**:
   ```bash
   ./scripts/view-last-session.sh
   echo "implement auth" | python .claude/hooks/detect_feature_request.py
   ```
3. **Review the development plan**:
   ```bash
   cat DEVELOPMENT_PLAN.md
   ```
4. **Pick an issue from Phase 1**:
   ```bash
   gh issue list --label "Tier-1"
   ```
5. **Tell Claude at session start** (use Appendix A template)

---

**Remember**: This file exists so you DON'T have to explain setup every session. Just point Claude here!

---

## Appendix A: Session Start Template

**Copy-paste this at the start of every development session:**

```
I'm working on autonomous-dev plugin development (dogfooding mode).

Context:
- Repo: ${PROJECT_ROOT}
- Role: Plugin developer (not user)
- Setup: Read docs/DEVELOPMENT.md for full context

Current status:
- Version: v3.2.0 (Anti-Bloat Architecture)
- Focus: [describe what you're working on]
- Last session: [what you did last time]

Priority issues (from docs/ISSUE-ALIGNMENT-ANALYSIS.md):
- Tier 1 (Critical): #37 ✅ done, #38, #29, #32
- Tier 2 (Important): #40, #34, #35, #41, #27, #25

Validation checklist:
✅ Dogfooding config active (.claude/settings.local.json)
✅ Hooks working (detect_feature_request.py)
✅ Session viewer working (./scripts/view-last-session.sh)
⏸️  [anything you need to check]

Ready to: [what you want to accomplish this session]
```

**Why this helps**:
- I (Claude) immediately understand context
- I know you're a developer, not a user
- I reference the right docs (DEVELOPMENT.md, not README.md)
- I know current priorities and status
- We don't waste time re-explaining setup

---

## Appendix B: Commit Message Guide

**Follow conventional commits:**

```bash
# Format
<type>(<scope>): <description>

# Types
feat: New feature
fix: Bug fix
docs: Documentation only
refactor: Code change that neither fixes bug nor adds feature
test: Adding missing tests
chore: Changes to build process or auxiliary tools

# Examples
feat(agents): add quality-validator specialist
fix(hooks): detect_feature_request now handles edge cases
docs(development): add dogfooding setup guide
refactor(orchestrator): simplify agent invocation logic
test(workflow): add UAT for full autonomous pipeline
chore(deps): update pytest to 7.4.0
```

**Always include in description**:
- What changed
- Why it changed (if not obvious)
- Related issue number: `(#123)`

**Example**:
```bash
git commit -m "feat(agents): add quality-validator specialist (#35)

Adds GenAI-powered quality validation agent that:
- Validates feature completeness
- Checks test coverage
- Reviews documentation sync

Passes all 4 bloat gates:
- Alignment: Improves SDLC enforcement
- Constraint: Uses GenAI reasoning
- Minimalism: 150 LOC
- Value: Catches quality issues hooks miss

Issue: #35"
```
