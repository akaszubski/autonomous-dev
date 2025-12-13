---
name: align
description: Unified alignment command - PROJECT.md validation, CLAUDE.md drift detection, brownfield retrofit
version: 2.0.0
category: core
tools: [Bash, Read, Write, Grep, Edit]
---

# /align - Unified Alignment Command

**Purpose**: Consolidates three alignment modes into a single command for project alignment, documentation drift detection, and brownfield retrofit.

**Modes**:
- `/align --project` - Validate/fix PROJECT.md alignment (replaces `/align-project`)
- `/align --claude` - Detect/fix CLAUDE.md drift (replaces `/align-claude`)
- `/align --retrofit` - Retrofit brownfield projects (replaces `/align-project-retrofit`)

**Issue**: [#121 - Command Simplification](https://github.com/akaszubski/autonomous-dev/issues/121)

---

## Quick Usage

```bash
# PROJECT.md alignment (interactive fixing)
/align --project

# CLAUDE.md drift detection
/align --claude

# Brownfield project retrofit (5-phase process)
/align --retrofit

# With options
/align --retrofit --dry-run
/align --retrofit --auto
```

---

## Mode 1: PROJECT.md Alignment (`--project`)

**Purpose**: Analyze and fix conflicts between PROJECT.md and actual implementation.

**Replaces**: `/align-project` command

**Agent**: alignment-analyzer (GenAI-powered)

**Time**: 5-20 minutes (depending on conflicts)

### How It Works

#### Phase 1: Analysis (GenAI Agent)

The alignment-analyzer agent:
- Reads PROJECT.md (source of truth)
- Scans codebase for actual implementation
- Checks documentation against reality
- Identifies conflicts and misalignments
- Explains each issue in context

#### Phase 2: Interactive Fixing (GenAI + You)

For each conflict found, the agent asks binary questions:

```
PROJECT.md says: "REST API only, no GraphQL"
Reality shows: graphql/ directory with resolvers
Status: GraphQL implementation exists

What should we do?
A) YES - PROJECT.md is correct (remove GraphQL)
B) NO - Update PROJECT.md to include GraphQL

Your choice [A/B]:
```

The agent intelligently:
- Asks binary questions (no ambiguity)
- Explains impact of each choice
- Groups related conflicts
- Suggests fixes based on your answers

#### Phase 3: Execution

After all questions answered, the agent:
- Updates PROJECT.md (if needed)
- Suggests code changes (if needed)
- Creates documentation (if needed)
- Removes scope drift (if needed)
- Commits changes

### Example: Analyzing Misalignment

```
🔍 Analyzing project alignment with PROJECT.md...

Found 5 conflicts:

CONFLICT #1: GraphQL Scope Mismatch
────────────────────────────────────
PROJECT.md says:
  SCOPE (Out of Scope):
    - GraphQL API

Reality shows:
  graphql/ directory exists with resolvers implemented

What should we do?
A) YES - PROJECT.md is correct (remove GraphQL code)
B) NO - Update PROJECT.md to include GraphQL

Your choice [A/B]: A

Action: Remove graphql/ directory and update PROJECT.md
Impact: Removes ~200 lines of code (not in scope)
```

### What Gets Validated

- **GOALS** - Does implementation serve stated goals?
- **SCOPE (In Scope)** - Are in-scope features implemented?
- **SCOPE (Out of Scope)** - Are out-of-scope features absent?
- **CONSTRAINTS** - Does implementation respect constraints?
- **ARCHITECTURE** - Does structure match documented architecture?

---

## Mode 2: CLAUDE.md Drift Detection (`--claude`)

**Purpose**: Check and fix drift between documented standards (CLAUDE.md) and actual implementation.

**Replaces**: `/align-claude` command

**Implementation**: Validation script (`validate_claude_alignment.py`)

**Time**: 1-2 minutes

### What This Does

CLAUDE.md defines development standards. If it drifts from reality (outdated version numbers, wrong agent counts, missing commands), new developers follow incorrect practices.

This mode:
1. **Detects drift** - Compares CLAUDE.md against actual PROJECT.md, agents, commands, hooks
2. **Shows issues** - Version mismatches, count errors, missing features
3. **Guides fixes** - Tells you exactly what to update
4. **Prevents future drift** - Pre-commit hook validates alignment on every commit

### Implementation

```bash
# The command internally runs:
python .claude/hooks/validate_claude_alignment.py
```

### What Gets Checked

#### 1. Version Consistency
- Project CLAUDE.md should match or be newer than PROJECT.md
- Global CLAUDE.md in `~/.claude/` should be reasonable
- All files should have recent "Last Updated" dates

#### 2. Agent Counts
- CLAUDE.md says how many agents exist
- Checks against actual agents in `plugins/autonomous-dev/agents/`
- Currently: 20 agents (9 core + 11 utility)

#### 3. Command Counts
- CLAUDE.md lists all available commands
- Checks against actual commands in `plugins/autonomous-dev/commands/`
- After Issue #121: 8 active commands

#### 4. Hook Documentation
- CLAUDE.md lists hooks
- Checks against actual hooks in `plugins/autonomous-dev/hooks/`

#### 5. Feature Existence
- If CLAUDE.md claims feature exists, verify it actually does
- Check for skills, agents, libraries referenced in docs

### Example Output

```bash
$ /align --claude

Checking CLAUDE.md alignment...

✅ Version consistency: OK
   - Project CLAUDE.md: 2025-12-13
   - PROJECT.md: 2025-12-09

❌ Agent count mismatch:
   - CLAUDE.md claims: 16 agents
   - Reality: 20 agents exist
   - Fix: Update CLAUDE.md to reflect 20 agents

❌ Command count mismatch:
   - CLAUDE.md claims: 15 commands
   - Reality: 10 active commands (after Issue #121)
   - Fix: Update CLAUDE.md command section

✅ Hook documentation: OK
   - All documented hooks exist

Summary: 2 drift issues found
Fix: Edit CLAUDE.md and update agent/command counts
```

### How to Fix Drift

1. Run `/align --claude` to see issues
2. Edit CLAUDE.md to match reality
3. Commit the alignment fix
4. Pre-commit hook validates on next commit

---

## Mode 3: Brownfield Retrofit (`--retrofit`)

**Purpose**: Retrofit existing (brownfield) projects to align with autonomous-dev standards for /auto-implement compatibility.

**Replaces**: `/align-project-retrofit` command

**Agent**: brownfield-analyzer (GenAI-powered)

**Workflow**: 5-phase process with backup/rollback safety

**Time**: 30-90 minutes (depending on project size and complexity)

### How It Works

This mode transforms brownfield projects into autonomous-dev compatible projects through a structured 5-phase workflow:

#### Phase 1: Analyze Codebase
- **Tool**: CodebaseAnalyzer (`codebase_analyzer.py`)
- **Action**: Deep scan of project structure, tech stack, dependencies
- **Detects**: Language, framework, package manager, test framework, file organization
- **Output**: Comprehensive codebase analysis report

#### Phase 2: Assess Alignment
- **Tool**: AlignmentAssessor (`alignment_assessor.py`)
- **Action**: Compare current state vs autonomous-dev standards
- **Calculates**: 12-Factor App compliance score, alignment gaps, PROJECT.md draft
- **Output**: Assessment with prioritized gaps and remediation steps

#### Phase 3: Generate Migration Plan
- **Tool**: MigrationPlanner (`migration_planner.py`)
- **Action**: Create step-by-step migration plan with dependencies
- **Estimates**: Effort (XS/S/M/L/XL), impact (LOW/MEDIUM/HIGH), critical path
- **Output**: Optimized migration plan with verification criteria

#### Phase 4: Execute Migration
- **Tool**: RetrofitExecutor (`retrofit_executor.py`)
- **Action**: Execute migration with backup/rollback capability
- **Modes**: DRY_RUN (show only), STEP_BY_STEP (confirm each), AUTO (all steps)
- **Safety**: Automatic backup (0o700 permissions), rollback on failure
- **Output**: Execution results with changes applied

#### Phase 5: Verify Results
- **Tool**: RetrofitVerifier (`retrofit_verifier.py`)
- **Action**: Verify compliance and assess readiness for /auto-implement
- **Checks**: PROJECT.md, file organization, tests, documentation, git config, compatibility
- **Output**: Readiness score (0-100) and blocker list

### Execution Modes

**DRY_RUN**: Shows what would change without modifying files
```bash
/align --retrofit --dry-run
```

**STEP_BY_STEP**: Confirms before each step (default, safest)
```bash
/align --retrofit
```

**AUTO**: Executes all steps automatically (fastest, less control)
```bash
/align --retrofit --auto
```

### Usage Examples

#### Basic Usage (Step-by-Step)
```bash
# Full retrofit with confirmations
/align --retrofit

# Example interaction:
# Phase 1: Analyzing codebase...
# Found: Python 3.11, FastAPI, pytest, poetry
#
# Phase 2: Assessing alignment...
# Alignment score: 42/100
# Gaps: PROJECT.md missing, file organization non-standard, no CI/CD
#
# Phase 3: Creating migration plan...
# 12 steps identified (4 critical, 8 recommended)
#
# Execute Step 1: Create PROJECT.md?
# [Y/n]: y
#
# ✅ Step 1 complete
#
# Execute Step 2: Reorganize files to .claude/ structure?
# [Y/n]: y
# ...
```

#### Dry Run (Preview Only)
```bash
# See what would change without modifying files
/align --retrofit --dry-run

# Example output:
# DRY RUN MODE - No files will be modified
#
# Would execute 12 steps:
#
# Step 1: Create PROJECT.md
#   - Creates: .claude/PROJECT.md
#   - Template: 12-factor app structure
#   - Impact: LOW
#
# Step 2: Reorganize files
#   - Moves: hooks/ → .claude/hooks/
#   - Moves: commands/ → .claude/commands/
#   - Impact: MEDIUM
# ...
```

#### Automatic Execution
```bash
# Execute all steps without confirmations (use with caution)
/align --retrofit --auto

# Safer: Combine with --dry-run first
/align --retrofit --dry-run  # Review changes
/align --retrofit --auto      # Execute if looks good
```

### What Gets Retrofitted

The retrofit process aligns your project with autonomous-dev standards:

1. **PROJECT.md Creation** - Core project alignment file with GOALS, SCOPE, CONSTRAINTS
2. **File Organization** - Move to `.claude/` structure (hooks, commands, agents, skills)
3. **Test Infrastructure** - Ensure test framework configured, coverage tools available
4. **CI/CD Integration** - Add pre-commit hooks, GitHub Actions workflows
5. **Documentation** - Create CLAUDE.md, CONTRIBUTING.md, README.md sections
6. **Git Configuration** - .gitignore patterns, branch protection, commit conventions

### Safety Features

- **Backup Creation**: Automatic backup before Phase 4 execution (timestamped, 0o700 permissions)
- **Rollback Support**: If migration fails, rollback to backup state
- **Step-by-Step Confirmations**: Default mode asks before each change
- **Dry Run**: Preview all changes without modifying files
- **Verification**: Final phase validates all changes meet standards

### Rollback

If something goes wrong, rollback to backup:

```bash
# Rollback is automatic on failure
# Manual rollback:
python plugins/autonomous-dev/lib/retrofit_executor.py --rollback <timestamp>
```

---

## Migration from Old Commands

| Old Command | New Command |
|-------------|-------------|
| `/align-project` | `/align --project` |
| `/align-claude` | `/align --claude` |
| `/align-project-retrofit` | `/align --retrofit` |
| `/align-project-retrofit --dry-run` | `/align --retrofit --dry-run` |
| `/align-project-retrofit --auto` | `/align --retrofit --auto` |

**Note**: Old commands archived to `commands/archive/` directory (Issue #121).

---

## When to Use Each Mode

### Use `--project` when:
- Starting new feature development
- PROJECT.md and implementation drift apart
- Scope creep detected (out-of-scope features implemented)
- Architecture doesn't match documentation
- Before major releases (ensure alignment)

### Use `--claude` when:
- Updating plugin or project documentation
- After adding/removing agents or commands
- Version numbers change
- Before committing documentation changes
- Onboarding new developers (ensure docs accurate)

### Use `--retrofit` when:
- Adopting autonomous-dev on existing project
- Legacy codebase needs autonomous-dev compatibility
- Team switching to /auto-implement workflow
- Greenfield project using non-standard structure
- Preparing project for autonomous development

---

## Agents Used

- **alignment-analyzer** - GenAI agent for PROJECT.md conflict detection (--project mode)
- **brownfield-analyzer** - GenAI agent for codebase analysis and retrofit (--retrofit mode)

---

## Libraries Used

### --project mode
- `plugins/autonomous-dev/agents/alignment-analyzer.md` - GenAI analysis

### --claude mode
- `.claude/hooks/validate_claude_alignment.py` - Drift detection script

### --retrofit mode
- `plugins/autonomous-dev/lib/codebase_analyzer.py` - Phase 1: Codebase scanning
- `plugins/autonomous-dev/lib/alignment_assessor.py` - Phase 2: Gap assessment
- `plugins/autonomous-dev/lib/migration_planner.py` - Phase 3: Migration planning
- `plugins/autonomous-dev/lib/retrofit_executor.py` - Phase 4: Execution with backup/rollback
- `plugins/autonomous-dev/lib/retrofit_verifier.py` - Phase 5: Compliance verification

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'autonomous_dev'"

**Solution**: Create development symlink for Python imports.
```bash
# macOS/Linux
cd plugins && ln -s autonomous-dev autonomous_dev

# Windows (Command Prompt as Admin)
cd plugins && mklink /D autonomous_dev autonomous-dev
```

### "CLAUDE.md alignment drift detected"

This is expected - run `/align --claude` to see issues and fix:
```bash
/align --claude  # Shows drift issues
vim CLAUDE.md    # Update based on findings
git add CLAUDE.md
git commit -m "docs: fix CLAUDE.md alignment"
```

### "Retrofit fails at Phase 4 execution"

Automatic rollback should restore backup. If not:
```bash
# Check backup directory
ls ~/.autonomous-dev/backups/

# Manual rollback (replace <timestamp> with actual backup)
python plugins/autonomous-dev/lib/retrofit_executor.py --rollback <timestamp>
```

### "PROJECT.md validation fails"

Run `/align --project` to identify conflicts. Agent will guide you through interactive fixing.

---

## Related Commands

- `/auto-implement` - Full autonomous pipeline (uses PROJECT.md for alignment)
- `/setup` - Interactive project setup wizard
- `/health-check` - Plugin integrity validation

---

## References

- **Issue #121**: [Command Simplification](https://github.com/akaszubski/autonomous-dev/issues/121)
- **Migration Guide**: `plugins/autonomous-dev/commands/archive/README.md`
- **Documentation**: See `docs/PROJECT-ALIGNMENT.md` for alignment concepts

---

## Implementation Details

This command consolidates three separate commands into a single unified interface:

1. **Previous**: `/align-project`, `/align-claude`, `/align-project-retrofit` (3 commands)
2. **Current**: `/align --project`, `/align --claude`, `/align --retrofit` (1 command, 3 modes)

**Benefits**:
- Single command to remember (`/align`)
- Consistent interface across alignment modes
- Clearer mental model (alignment = single concept, multiple modes)
- Reduced cognitive overhead (8 active commands vs 20)
