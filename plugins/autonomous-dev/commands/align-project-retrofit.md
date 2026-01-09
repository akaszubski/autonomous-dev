---
name: align-project-retrofit
description: Retrofit brownfield projects for autonomous development
argument-hint: (no arguments needed)
allowed-tools: [Bash, Read, Write, Grep, Edit]
version: 1.0.0
category: core
---

# /align-project-retrofit - Brownfield Retrofit Command

**Purpose**: Analyze existing (brownfield) projects and retrofit them to align with autonomous-dev standards for /auto-implement compatibility.

**Target Users**: Teams adopting autonomous-dev on existing codebases

**Workflow**: 5-phase process with backup/rollback safety

---

## How It Works

This command transforms brownfield projects into autonomous-dev compatible projects through a structured 5-phase workflow:

### Phase 1: Analyze Codebase
- **Tool**: CodebaseAnalyzer (codebase_analyzer.py)
- **Action**: Deep scan of project structure, tech stack, dependencies
- **Detects**: Language, framework, package manager, test framework, file organization
- **Output**: Comprehensive codebase analysis report

### Phase 2: Assess Alignment
- **Tool**: AlignmentAssessor (alignment_assessor.py)
- **Action**: Compare current state vs autonomous-dev standards
- **Calculates**: 12-Factor App compliance score, alignment gaps, PROJECT.md draft
- **Output**: Assessment with prioritized gaps and remediation steps

### Phase 3: Generate Migration Plan
- **Tool**: MigrationPlanner (migration_planner.py)
- **Action**: Create step-by-step migration plan with dependencies
- **Estimates**: Effort (XS/S/M/L/XL), impact (LOW/MEDIUM/HIGH), critical path
- **Output**: Optimized migration plan with verification criteria

### Phase 4: Execute Migration
- **Tool**: RetrofitExecutor (retrofit_executor.py)
- **Action**: Execute migration with backup/rollback capability
- **Modes**: DRY_RUN (show only), STEP_BY_STEP (confirm each), AUTO (all steps)
- **Safety**: Automatic backup (0o700 permissions), rollback on failure
- **Output**: Execution results with changes applied

### Phase 5: Verify Results
- **Tool**: RetrofitVerifier (retrofit_verifier.py)
- **Action**: Verify compliance and assess readiness for /auto-implement
- **Checks**: PROJECT.md, file organization, tests, documentation, git config, compatibility
- **Output**: Readiness score (0-100) and blocker list

---

## Execution Modes

**DRY_RUN**: Shows what would change without modifying files
```bash
/align-project-retrofit --dry-run
```

**STEP_BY_STEP**: Confirms before each step (default, safest)
```bash
/align-project-retrofit
```

**AUTO**: Executes all steps automatically (fastest, less control)
```bash
/align-project-retrofit --auto
```

---

## Usage Examples

### Basic Usage (Step-by-Step)
```bash
# Full retrofit with confirmations
/align-project-retrofit

# Analyze project root explicitly
/align-project-retrofit --project-root /path/to/project
```

### Phase-Specific Execution
```bash
# Analyze only
/align-project-retrofit --phase analyze

# Plan only (requires prior analysis)
/align-project-retrofit --phase plan

# Verify only (after manual changes)
/align-project-retrofit --phase verify
```

### Output Formats
```bash
# Human-readable output (default)
/align-project-retrofit

# JSON output for scripting
/align-project-retrofit --json

# Save to file
/align-project-retrofit --json --output retrofit_results.json

# Verbose mode
/align-project-retrofit --verbose
```

---

## What Gets Changed

### Files Created
- `.claude/PROJECT.md` - Project goals, scope, constraints
- `src/` - Source code directory (if missing)
- `tests/` - Test directory (if missing)
- `.github/workflows/` - CI/CD configuration (if missing)

### Files Modified
- `README.md` - Enhanced with autonomous-dev context
- `.gitignore` - Standard exclusions added
- Configuration files - Aligned with standards

### Backup & Rollback
- **Backup Location**: `/tmp/retrofit_backup_YYYYMMDD_HHMMSS/`
- **Backup Permissions**: `0o700` (user-only, secure)
- **Backup Contains**: All modified files + checksums
- **Auto-Rollback**: On any failure in AUTO mode
- **Manual Rollback**: Available in STEP_BY_STEP mode

---

## Exit Codes

- **0**: Success - Ready for /auto-implement
- **1**: Error - Command failed
- **2**: Blockers present - Not ready for /auto-implement

---

## Readiness Criteria

**Ready for /auto-implement** when:
- ✅ PROJECT.md exists with GOALS, SCOPE, CONSTRAINTS
- ✅ File organization follows standards (src/, tests/, docs/)
- ✅ Test framework configured
- ✅ Git repository initialized with .gitignore
- ✅ Package manager configured (requirements.txt, pyproject.toml, etc.)
- ✅ Readiness score ≥ 70%
- ✅ No critical blockers

---

## Implementation

### Command Execution

```bash
# Claude coordinates this workflow via BrownfieldRetrofit facade
python plugins/autonomous-dev/scripts/align_project_retrofit.py [options]
```

### Architecture

**Facade Pattern**: BrownfieldRetrofit (brownfield_retrofit.py) coordinates all phases

**Libraries**:
- `codebase_analyzer.py` - Tech stack and structure detection
- `alignment_assessor.py` - Alignment gap analysis and scoring
- `migration_planner.py` - Migration step generation and optimization
- `retrofit_executor.py` - Safe execution with backup/rollback
- `retrofit_verifier.py` - Compliance verification and readiness assessment

**Security**: All libraries use security_utils for path validation (CWE-22), symlink detection (CWE-59), and audit logging (CWE-117)

---

## Example Session

```bash
$ /align-project-retrofit

PHASE 1: Analyzing codebase...
  Tech Stack: Python 3.9
  Framework: Flask
  Files: 47
  Tests: 12

PHASE 2: Assessing alignment...
  12-Factor Score: 65.0%
  Alignment Gaps: 8
  PROJECT.md Confidence: 0.75

PHASE 3: Generating migration plan...
  Migration Steps: 8
  Total Effort: 12.5 hours
  Critical Path: 8.0 hours

PHASE 4: EXECUTING migration...
  Completed: 8
  Failed: 0
  Backup: /tmp/retrofit_backup_20231109_143022/

PHASE 5: Verifying results...
  Readiness Score: 85.0%
  Compliance Checks: 5/5 passed
  Blockers: 0
  Ready for /auto-implement: YES

=== Retrofit Complete ===

Readiness Score: 85.0%
Compliance: 5/5 checks passed
Blockers: 0
Ready for /auto-implement: YES
```

---

## Troubleshooting

### "Not a Git repository"
**Fix**: Initialize git first
```bash
git init
git add .
git commit -m "Initial commit"
```

### "No package manager configuration found"
**Fix**: Create requirements.txt or pyproject.toml
```bash
pip freeze > requirements.txt
```

### "Readiness score < 70%"
**Fix**: Review verification report for specific gaps
```bash
/align-project-retrofit --phase verify --verbose
```

### "Rollback performed"
**Fix**: Check logs for failure reason
```bash
cat logs/security_audit.log | grep retrofit_execution_failed
```

---

## Agent Integration

**Brownfield Analyzer Agent**: Available via `/brownfield-analyzer` for specialized analysis

**Agent File**: `plugins/autonomous-dev/agents/brownfield-analyzer.md`

**Skills Used**:
- research-patterns - Pattern discovery
- architecture-patterns - Architecture assessment
- file-organization - Structure validation
- python-standards - Python-specific checks
- testing-guide - Test coverage analysis

---

## Related Commands

- `/setup` - Initial project setup (greenfield)
- `/align-project` - Fix PROJECT.md conflicts
- `/health-check` - Validate plugin integrity
- `/status` - Track project progress

---

## Success Metrics

**Successful retrofit achieved when**:
1. All 5 phases complete without errors
2. Readiness score ≥ 70%
3. Zero critical blockers
4. All compliance checks pass
5. /auto-implement ready

---

## Best Practices

1. **Commit before retrofit**: Ensure clean working directory
2. **Review dry-run first**: Use `--dry-run` to preview changes
3. **Test after retrofit**: Run test suite to verify compatibility
4. **Customize PROJECT.md**: Review and enhance generated content
5. **Gradual adoption**: Start with analyze/assess phases, execute when ready

---

**Related**: GitHub Issue #59 - Brownfield retrofit command implementation
