# Brownfield Project Retrofit Guide

**Version**: v3.11.0
**Last Updated**: 2025-11-11
**Issue**: GitHub Issue #59

Transform existing (brownfield) projects into autonomous-dev compatible projects using the `/align-project-retrofit` command.

---

## Overview

The `/align-project-retrofit` command provides a structured 5-phase process to retrofit existing projects for autonomous development. It analyzes your project, assesses alignment gaps, creates a migration plan, executes changes with safety guarantees, and verifies readiness for `/auto-implement` workflows.

### Key Features

- **Non-destructive analysis**: Examines project without making changes
- **Smart planning**: Identifies gaps and creates prioritized migration plan
- **Safe execution**: Automatic backup/rollback with 0o700 permissions
- **Three modes**: DRY_RUN (preview), STEP_BY_STEP (confirm each), AUTO (all)
- **Comprehensive verification**: Validates compliance and /auto-implement readiness
- **Multi-language**: Supports Python, JavaScript, Go, Java, Rust, C++, C#, PHP
- **12-Factor App scoring**: Compliance assessment based on industry standards

---

## Quick Start

### Basic Usage

```bash
/align-project-retrofit
```

The command will guide you through the 5 phases with interactive prompts.

### Dry Run (Preview Only)

```bash
/align-project-retrofit --dry-run
```

Shows what would be changed without making any modifications.

### Automatic Mode (All Changes)

```bash
/align-project-retrofit --auto
```

Applies all recommended changes without requiring confirmation at each step.

---

## The 5-Phase Process

### Phase 0: Project Analysis

**What happens**: Auto-detects project structure and tech stack
**Time**: 30-60 seconds
**Output**: Project analysis summary

The command scans your project to identify:
- Programming language (Python, JavaScript, Go, Java, Rust, etc.)
- Web framework or library (Django, Express, Spring, etc.)
- Package manager (pip, npm, go mod, Maven, Cargo, etc.)
- Existing file organization
- PROJECT.md and CLAUDE.md presence

### Phase 1: Codebase Analysis

**What happens**: Deep scan of directory structure, dependencies, and tests
**Time**: 1-2 minutes
**Output**: Comprehensive codebase report

Analyzes:
- Directory structure and naming conventions
- Dependencies (production vs development)
- Test files and test framework
- Code organization (modular, monolithic, microservices)
- Documentation coverage
- Configuration files

### Phase 2: Alignment Assessment

**What happens**: Compares current state to autonomous-dev standards
**Time**: 30-60 seconds
**Output**: 12-Factor App compliance score and gap list

Evaluates:
- Compliance score (0-100 based on 12-Factor App)
- Missing files (PROJECT.md, CLAUDE.md, .claude directory)
- Documentation quality gaps
- Test coverage assessment
- Prioritized gap list (critical, high, medium, low)

**Example output**:
```
Compliance Score: 45/100

Critical Gaps:
- Missing PROJECT.md (required for /auto-implement)
- Missing .claude/CLAUDE.md (development standards)

High Gaps:
- No pre-commit hooks (auto-format, security, tests)
- Incomplete test coverage estimate

Medium Gaps:
- README needs architecture section
- No .claude/settings.local.json configuration

Low Gaps:
- Documentation could include more examples
```

### Phase 3: Migration Planning

**What happens**: Breaks down gaps into actionable steps with dependencies
**Time**: 30-60 seconds
**Output**: Step-by-step migration plan with estimates

Creates:
- Step-by-step instructions
- Effort estimation per step (XS, S, M, L, XL)
- Impact assessment (LOW, MEDIUM, HIGH)
- Dependency tracking (which steps must happen first)
- Critical path (minimum viable retrofit)
- Verification criteria for each step

### Phase 4: Execution

**What happens**: Applies changes to your project
**Time**: 2-10 minutes (depends on project size and mode)
**Output**: Execution results with created/updated files

Execution modes:
1. **DRY_RUN**: Shows what would change, no modifications
2. **STEP_BY_STEP**: Asks for confirmation before each step
3. **AUTO**: Applies all changes automatically

Safety features:
- Creates automatic backup before any changes
- Timestamped backup location: `/tmp/retrofit_backup_YYYY-MM-DD_HH-MM-SS.tar.gz`
- Backup permissions: 0o700 (user-only access)
- Atomic operations: All steps succeed or all rollback
- Error recovery: Automatic rollback on any failure

**Example execution creates**:
- `PROJECT.md` - Project goals, scope, architecture
- `.claude/CLAUDE.md` - Development standards
- `.claude/PROJECT.md` - Symlink to root PROJECT.md
- `.claude/settings.local.json` - Local configuration
- Pre-commit hooks - Auto-formatting, security, testing
- Test configuration - Framework setup

### Phase 5: Verification

**What happens**: Validates compliance and /auto-implement readiness
**Time**: 30-90 seconds
**Output**: Readiness assessment and next steps

Verifies:
- All required files created and valid
- .claude directory structure correct
- Configuration files properly formatted
- Test framework operational
- Hook installation successful
- /auto-implement compatibility

**Readiness levels**:
- ✅ **Ready**: Project fully compatible with /auto-implement
- ⚠️ **Needs Minor Fixes**: Small adjustments recommended
- 🚫 **Needs Major Fixes**: Significant work required

---

## Real-World Scenarios

### Scenario 1: Greenfield Python Project

**Before retrofit**:
- Python project with basic structure
- No PROJECT.md or .claude directory
- No pre-commit hooks
- Inconsistent testing approach
- Cannot use /auto-implement

**After retrofit**:
```bash
/align-project-retrofit
# Phase 0: Detects Python, Flask, pip, pytest
# Phase 1: Analyzes structure, finds 18 test files
# Phase 2: Score 62/100 - needs PROJECT.md, hooks, docs
# Phase 3: Plan: 7 steps (2 critical, 3 high, 2 medium)
# Phase 4: Creates PROJECT.md, .claude directory, activates hooks
# Phase 5: Verification passes - Ready for /auto-implement!
```

**Result**: Ready to use `/auto-implement` for autonomous feature development

### Scenario 2: Legacy Node.js Application

**Before retrofit**:
- Node.js app with scattered test files
- No clear architecture documentation
- Manual deployment process
- Wants to adopt autonomous-dev practices

**After retrofit**:
```bash
/align-project-retrofit --step-by-step
# Phase 0: Detects JavaScript, Express, npm, Jest
# Phase 1: Finds 24 tests scattered across directories
# Phase 2: Score 38/100 - major gaps in documentation
# Phase 3: Plan: 12 steps (includes test reorganization)
# Phase 4: User confirms each step
# Phase 5: Verification identifies 2 minor documentation gaps
```

**Result**: Project structure aligned, ready for /auto-implement with documentation cleanup

### Scenario 3: Microservices Architecture

**Before retrofit**:
- Multiple services in separate directories
- Different tech stacks (Python, Go, Node.js)
- Inconsistent hook configurations

**After retrofit**:
```bash
cd my-monorepo
/align-project-retrofit
# Phase 0: Detects mixed tech stack
# Phase 1: Analyzes each service independently
# Phase 2: Provides separate compliance scores per service
# Phase 3: Plan includes per-service retrofit steps
# Phase 4: Creates root PROJECT.md + per-service configurations
# Phase 5: Verification confirms each service ready
```

**Result**: Entire monorepo compatible with /auto-implement

---

## Supported Technologies

### Languages
- Python (3.7+)
- JavaScript/TypeScript (Node.js 14+)
- Go (1.13+)
- Java (11+)
- Rust (2021 edition)
- C++
- C#
- PHP (7.2+)

### Web Frameworks
- **Python**: Django, FastAPI, Flask, Pyramid
- **JavaScript**: Express, Next.js, Nest.js
- **Go**: Gin, Echo, GORM
- **Java**: Spring Boot, Quarkus
- **Rust**: Rocket, Axum, Actix
- **PHP**: Laravel, Symfony

### Package Managers
- pip (Python)
- npm (JavaScript)
- go mod (Go)
- Maven (Java)
- Cargo (Rust)
- Composer (PHP)

### Test Frameworks
- pytest (Python)
- Jest (JavaScript)
- Mocha (JavaScript)
- JUnit (Java)
- Cargo test (Rust)

---

## Execution Modes Explained

### DRY_RUN Mode

```bash
/align-project-retrofit --dry-run
```

**What it does**:
- Analyzes project (Phases 0-3)
- Shows what would be changed
- Generates migration plan
- **Does NOT make any modifications**

**Use when**:
- First time running the command
- Want to preview changes
- Need to review migration plan before execution
- Troubleshooting alignment issues

**Output example**:
```
DRY RUN PREVIEW - No changes will be made

Phase 4: Migration would create/update:
  CREATE: PROJECT.md (847 lines)
  CREATE: .claude/CLAUDE.md (1203 lines)
  CREATE: .claude/settings.local.json (42 lines)
  UPDATE: README.md (add architecture section)
  CREATE: .git/hooks/pre-commit (security scanning)

Total impact: 3 new files, 1 updated, 6 hooks activated

Estimated effort: 45 minutes
Critical path: 4 steps

To apply changes, run: /align-project-retrofit --execute
```

### STEP_BY_STEP Mode

```bash
/align-project-retrofit --step-by-step
```

**What it does**:
- Phases 0-3: Analysis and planning
- Phase 4: Asks for confirmation before each step
- Phase 5: Verification

**Use when**:
- Want fine-grained control
- Some steps may need customization
- Want to review changes before applying
- First time on production-like projects

**User experience**:
```
Step 1 of 7: Create PROJECT.md
  Description: Define project goals and architecture
  Impact: HIGH
  Effort: 15 minutes

Preview:
  GOALS:
    - Enable autonomous feature development
    - Standardize development workflow
    ...

Apply this step? [y/N/skip]
```

### AUTO Mode

```bash
/align-project-retrofit --auto
```

**What it does**:
- Phases 0-3: Analysis and planning
- Phase 4: Applies all steps automatically
- Phase 5: Verification

**Use when**:
- Project is well-understood
- Trust the migration plan
- Want minimal interaction
- Running in CI/CD pipeline

**Output**:
```
AUTO mode - applying all steps...
[████████████████████████████████] 100%

Step 1/7: Create PROJECT.md ✓
Step 2/7: Create .claude/CLAUDE.md ✓
Step 3/7: Create .claude/settings.local.json ✓
Step 4/7: Create pre-commit hooks ✓
Step 5/7: Update README.md ✓
Step 6/7: Configure test framework ✓
Step 7/7: Verify installation ✓

All steps completed successfully!
```

---

## Backup and Rollback

### Automatic Backups

Before Phase 4 execution, the command automatically creates a backup:

```
Location: /tmp/retrofit_backup_YYYY-MM-DD_HH-MM-SS.tar.gz
Permissions: 0o700 (user-only access)
Contents: Complete project snapshot before any changes
```

### Rollback on Failure

If any step fails:
1. Automatic rollback is triggered
2. All changes are reverted to backup
3. Original project state is restored
4. Error details are logged

**Example**:
```
Step 3: Create pre-commit hooks - FAILED
Reason: Permission denied writing to .git/hooks

Automatic rollback in progress...
Restoring from backup...
[████████████████████████████████] 100%

Project restored to original state.
Backup preserved at: /tmp/retrofit_backup_2025-11-11_14-30-45.tar.gz

Error details logged to: logs/retrofit_error.log
Next steps: Fix permissions and retry
```

---

## Troubleshooting

### Issue: "Project root not detected"

**Cause**: Command can't identify project directory

**Solution**:
```bash
# Run from project root
cd /path/to/your/project
/align-project-retrofit
```

### Issue: "Unsupported language detected"

**Cause**: Language not in supported list

**Solution**:
1. Check if your language is listed in Supported Technologies
2. Report issue: GitHub Issue #59
3. Manual retrofit option available (contact maintainers)

### Issue: "Test framework not detected"

**Cause**: Test files exist but framework unclear

**Solution**:
```
The command will ask you during Phase 2 to specify the test framework manually
Example: "Detected test files but framework unclear. Is this pytest?"
```

### Issue: "Permission denied on backup creation"

**Cause**: User doesn't have permissions in /tmp

**Solution**:
```bash
# Check /tmp permissions
ls -ld /tmp

# If needed, use alternate backup location
# Set environment variable before running:
export RETROFIT_BACKUP_DIR=/path/to/backup
/align-project-retrofit
```

### Issue: "TOCTOU error during execution"

**Cause**: Another process modified files during retrofit

**Solution**:
```
Automatic rollback is triggered. Causes:
1. Another developer committing changes during retrofit
2. IDE auto-saving files
3. File watcher (node_modules, etc.)

To prevent:
1. Stop other development activity
2. Close IDE
3. Disable file watchers
4. Retry command
```

---

## What Gets Created/Modified

### New Files

| File | Purpose | Customizable |
|------|---------|--------------|
| `PROJECT.md` | Project goals, scope, architecture | Yes (before next phase) |
| `.claude/CLAUDE.md` | Development standards | Yes (after retrofit) |
| `.claude/PROJECT.md` | Symlink to root | Auto-created |
| `.claude/settings.local.json` | Local settings | Yes (after retrofit) |
| `.git/hooks/pre-commit` | Auto-format + security + tests | Yes (after retrofit) |

### Modified Files

| File | Modification | Reversible |
|------|--------------|-----------|
| `README.md` | Adds architecture section | Yes (backup included) |
| `.gitignore` | Adds .claude, logs patterns | Yes (backup included) |
| `pyproject.toml` / `package.json` | Adds test configuration | Yes (backup included) |

### Backup Protection

All changes are protected by automatic backup:
- **Location**: `/tmp/retrofit_backup_YYYY-MM-DD_HH-MM-SS.tar.gz`
- **Preserved for**: 7 days (auto-cleanup)
- **Manual cleanup**: `rm /tmp/retrofit_backup_*.tar.gz`

---

## Next Steps After Retrofit

Once `/align-project-retrofit` completes successfully (Phase 5: "Ready"), you can:

### 1. Review Project Documentation

```bash
# Read PROJECT.md
cat PROJECT.md

# Read CLAUDE.md
cat .claude/CLAUDE.md

# Edit for customization (optional)
vim PROJECT.md
vim .claude/CLAUDE.md
```

### 2. Test the Setup

```bash
# Verify pre-commit hooks work
git add .
git commit -m "test: verify retrofit"

# Run tests
/test

# Run health check
/health-check
```

### 3. Start Autonomous Development

```bash
# Develop features with /auto-implement
/auto-implement "Add JWT authentication to API"

# Individual agents available
/research "JWT best practices"
/plan "JWT implementation strategy"
/test-feature "JWT authentication"
/implement "JWT authentication"
```

### 4. Configure Optional Features

```bash
# Enable automatic git operations (optional)
export AUTO_GIT_ENABLED=true
export AUTO_GIT_PUSH=true
export AUTO_GIT_PR=true

# Run /auto-implement with automatic git operations
/auto-implement "Your feature here"
```

---

## Best Practices

### Before Retrofit

1. **Commit your work**: Ensure working directory is clean
   ```bash
   git status  # Should show "working tree clean"
   ```

2. **Review migration plan**: Use DRY_RUN mode first
   ```bash
   /align-project-retrofit --dry-run
   ```

3. **Understand your project**: Know your tech stack
   - What language? (Python, JavaScript, etc.)
   - What framework? (Django, Express, etc.)
   - What test framework? (pytest, Jest, etc.)

### During Retrofit

1. **Don't interrupt execution**: Let all phases complete
2. **Keep backup safe**: Note the backup path
3. **Review confirmation prompts**: Read what's about to change

### After Retrofit

1. **Test immediately**: Run tests and health checks
2. **Review created files**: Check PROJECT.md and CLAUDE.md
3. **Customize if needed**: Adjust settings for your project
4. **Commit the retrofit**: Include in your first commit
   ```bash
   git add .claude PROJECT.md
   git commit -m "feat: retrofit for autonomous-dev compatibility"
   ```

---

## FAQ

**Q: Does retrofit modify my source code?**
A: No. It only creates configuration files (PROJECT.md, CLAUDE.md, hooks) and updates documentation (README.md).

**Q: What if retrofit fails halfway?**
A: Automatic rollback restores your project to original state. No data loss.

**Q: Can I customize PROJECT.md after retrofit?**
A: Yes! The retrofit creates a starting point you can customize to match your actual project goals.

**Q: What if my tech stack isn't supported?**
A: Report to GitHub Issue #59. Meanwhile, you can manually create PROJECT.md following the template.

**Q: How long does retrofit take?**
A: Typically 2-10 minutes depending on project size. DRY_RUN takes 1-2 minutes.

**Q: Can I run retrofit multiple times?**
A: Yes. Subsequent runs detect existing files and skip creation, updating only stale configurations.

**Q: What about /auto-implement after retrofit?**
A: Phase 5 verifies compatibility. If "Ready", you can immediately start using /auto-implement.

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Development workflow and standards
- [PROJECT.md](../PROJECT.md) - Project goals and sprints
- [README.md](../plugins/autonomous-dev/README.md) - Plugin overview
- GitHub Issue #59 - Full implementation details and discussion

---

**Last Updated**: 2025-11-11
**Maintained By**: Doc-Master Agent
