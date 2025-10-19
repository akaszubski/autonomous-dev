# Scripts Manifest - What's Needed

This document lists all scripts that Claude Code and GitHub workflows depend on, ensuring the bootstrap is complete and self-contained.

## Required Scripts (Must Be Included)

### 1. Hooks (Used by Claude Code)
Location: `hooks/`

**auto_format.py** - Multi-language code formatting
- Python: black + isort
- JavaScript: prettier
- Go: gofmt
- Used by: Claude Code post-write hook
- Status: ⏳ Need to create generic version

**auto_test.py** - Test runner with framework detection
- Python: pytest
- JavaScript: jest/vitest
- Go: go test
- Used by: Claude Code pre-commit hook
- Status: ⏳ Need to create generic version

**security_scan.py** - Secret detection and security checks
- Scans for API keys, passwords, tokens
- Language-agnostic pattern matching
- Used by: Claude Code pre-commit hook
- Status: ⏳ Need to create generic version

**pattern_curator.py** - Auto-learn coding patterns
- Extracts patterns from code
- Updates PATTERNS.md automatically
- Used by: Claude Code post-write hook
- Status: ⏳ Need to create generic version

**auto_align_filesystem.py** - File organization enforcement
- Keeps .md files in correct locations
- Enforces directory structure
- Used by: Claude Code post-write hook
- Status: ⏳ Need to create generic version

### 2. GitHub Workflow Scripts
Location: `scripts/` or embedded in workflows

**weekly_cleanup.sh** - Health check script (optional)
- Checks test failures
- Reviews coverage trends
- Creates health report
- Used by: weekly-health-check.yml
- Status: ⏳ Optional, can be embedded in workflow

### 3. Utility Scripts
Location: `scripts/`

**generalize_for_bootstrap.py** - Content generalization
- Used to keep bootstrap updated from source
- Not needed in bootstrap template itself
- Status: ✅ Already created (in [PROJECT_NAME])

**sync_bootstrap_template.sh** - Sync automation
- Used to sync improvements from source
- Not needed in bootstrap template itself
- Status: ✅ Already created (in [PROJECT_NAME])

## Optional Scripts (Nice to Have)

**check_alignment.sh** - Calculate alignment score
- Analyzes .claude/ structure
- Calculates alignment percentage
- Status: ⏳ Could create generic version

**check_tests.sh** - Test runner wrapper
- Runs appropriate test command based on language
- Shows coverage report
- Status: ⏳ Could create generic version

## Script Dependencies Summary

### What Claude Code Needs:
1. hooks/auto_format.py ✓ Required
2. hooks/auto_test.py ✓ Required
3. hooks/security_scan.py ✓ Required
4. hooks/pattern_curator.py ✓ Required
5. hooks/auto_align_filesystem.py ✓ Required

### What GitHub Actions Needs:
1. All logic embedded in workflows ✓ (no external scripts required)
2. Optional: scripts/weekly_cleanup.sh (can embed in workflow)

### What Bootstrap Script Needs:
1. bootstrap.sh ✓ Required (interactive setup)
2. All other logic self-contained

## Completeness Check

For a complete, self-contained bootstrap:

**Minimum Required:**
- [x] agents/*.md (8 files)
- [x] github/workflows/*.yml (3 files)  
- [ ] hooks/*.py (5 files) ← **NEED TO CREATE**
- [ ] templates/*.template (3 files) ← **NEED TO CREATE**
- [ ] test-configs/{python,javascript,go}/ ← **NEED TO CREATE**
- [ ] settings.json.template ← **NEED TO CREATE**
- [ ] bootstrap.sh ← **NEED TO CREATE**

**With Full Features:**
- [ ] skills/*/SKILL.md (11 files) ← **NICE TO HAVE**
- [ ] scripts/check_alignment.sh ← **NICE TO HAVE**
- [ ] scripts/check_tests.sh ← **NICE TO HAVE**

## Next Priority

1. **Create 5 generic hooks** (2 hours) - Most critical
2. **Create bootstrap.sh** (1 hour) - Essential for setup
3. **Create templates** (30 min) - Required for initialization
4. **Extract skills** (1 hour) - Important for full functionality

Total Remaining: ~4.5 hours
