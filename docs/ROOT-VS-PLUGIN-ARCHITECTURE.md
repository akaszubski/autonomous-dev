# ROOT vs PLUGIN Architecture

**Decision Date**: 2025-10-21
**Status**: Implemented
**Impact**: All commands, agents, skills, hooks

---

## Problem

This project serves **two audiences**:

1. **Plugin developers** (you) - Building and refining the automation system
2. **Plugin users** (marketplace) - Using the distributed automations in their projects

Previous approach: Single `docs/` location caused confusion about what gets distributed.

## Solution

**Two separate documentation locations with DEV_MODE flag**:

### 1. ROOT `docs/` - Developer Documentation (NOT distributed)

**Audience**: Contributors working **ON** the plugin
**Purpose**: Development, architecture, implementation notes
**Distribution**: Never included in marketplace package

**Files** (from `scripts/validate_structure.py`):
- `CONTRIBUTING.md` - How to contribute
- `DEVELOPMENT.md` - Development workflow
- `CODE-REVIEW-WORKFLOW.md` - Code review process
- `IMPLEMENTATION-STATUS.md` - Implementation tracking
- `ARCHITECTURE.md` - System architecture
- `SESSION-LOGS.md` - Session documentation
- `sessions/` - Session files

### 2. PLUGIN `plugins/autonomous-dev/docs/` - User Documentation (distributed)

**Audience**: Users **USING** the plugin via marketplace
**Purpose**: User guides, commands reference, troubleshooting
**Distribution**: Included in marketplace package

**Files** (from `scripts/validate_structure.py`):
- `QUICKSTART.md` - Quick start guide
- `COMMANDS.md` - Command reference
- `TROUBLESHOOTING.md` - Common issues
- `GITHUB_AUTH_SETUP.md` - GitHub setup
- `CUSTOMIZATION.md` - Customization guide
- `TEAM-ONBOARDING.md` - Team setup
- `GITHUB-ISSUES-INTEGRATION.md` - Issues integration
- `GITHUB-WORKFLOW.md` - GitHub workflow
- `PR-AUTOMATION.md` - PR automation
- `TESTING_GUIDE.md` - Testing guide
- `UPDATES.md` - Update notes
- `commit-workflow.md` - Commit workflow
- `COMMIT-WORKFLOW-COMPLETE.md` - Complete workflow
- `AUTO-ISSUE-TRACKING.md` - Issue tracking
- `COVERAGE-GUIDE.md` - Coverage guide
- `SYSTEM-PERFORMANCE-GUIDE.md` - Performance guide

### 3. DEV_MODE Flag

**Configuration**: `.env` file
**Default**: `DEV_MODE=false` (normal user mode)
**Dev mode**: `DEV_MODE=true` (enables dev-specific features)

```bash
# In your local .env (NOT committed, NOT distributed)
DEV_MODE=true

# In distributed .env.example (default for users)
DEV_MODE=false
```

**Usage in code**:
```python
import os

if os.getenv('DEV_MODE') == 'true':
    # Dev-only feature
    enable_plugin_validation()
```

---

## Architecture Benefits

### Simple (Sustainable)
- ✅ ONE `.claude/` automation set (used for building AND distributed)
- ✅ TWO doc locations (clear separation)
- ✅ ONE flag to control behavior (DEV_MODE)

### Dogfooding
- ✅ Plugin tests itself by using itself to build
- ✅ Real usage exposes bugs early
- ✅ Documentation stays accurate

### Clean Distribution
- ✅ Users never see dev docs
- ✅ No confusing "CONTRIBUTING.md" for users
- ✅ Marketplace package is minimal

---

## Validation

**Automated enforcement**: `scripts/validate_structure.py`

Checks:
- ✅ User docs in `plugins/autonomous-dev/docs/`
- ✅ Dev docs in `docs/`
- ✅ No duplicates between locations
- ✅ Clean root (only essential .md files)

**Run validation**:
```bash
python scripts/validate_structure.py
```

**Pre-commit hook**: Runs automatically before each commit

---

## Affected Components

### Commands (20 affected)
- `/sync-docs` - Main documentation sync
- `/sync-docs-organize` - File organization
- `/sync-docs-auto` - Auto-detect sync
- `/sync-docs-api` - API docs
- `/sync-docs-changelog` - CHANGELOG
- `/align-project*` (5 variants) - Project alignment
- `/commit*` (4 variants) - Commit workflows
- `/auto-implement` - Auto implementation
- `/setup` - Setup wizard
- `/uninstall` - Uninstall wizard
- `/issue*` (5 variants) - Issue commands
- `/test-architecture` - Architecture testing

### Agents (7 affected)
- `doc-master` - Documentation specialist
- `implementer` - Implementation
- `planner` - Planning
- `security-auditor` - Security
- `researcher` - Research
- `reviewer` - Review
- `orchestrator` - Orchestration

### Skills (6 affected)
- `documentation-guide` - Doc standards
- `testing-guide` - Testing standards
- `python-standards` - Python standards
- `security-patterns` - Security patterns
- `research-patterns` - Research patterns
- `engineering-standards` - Engineering standards

### Hooks (3 affected)
- `auto_update_docs.py` - Auto-update docs
- `auto_track_issues.py` - Auto-track issues
- `auto_tdd_enforcer.py` - TDD enforcement

---

## Migration Guide

### For Commands

**Before**:
```markdown
Move .md files from root → `docs/`
```

**After**:
```markdown
Move user-facing docs → `plugins/autonomous-dev/docs/`
Move dev-facing docs → `docs/`
Validate with `python scripts/validate_structure.py`
```

### For Agents

**Before**:
```markdown
All docs go to docs/
```

**After**:
```markdown
Check scripts/validate_structure.py for rules:
- USER_DOC_FILES → plugins/autonomous-dev/docs/
- DEV_DOC_FILES → docs/
```

### For Skills

**Before**:
```markdown
Documentation goes in docs/
```

**After**:
```markdown
User-facing docs → plugins/autonomous-dev/docs/
Dev-facing docs → docs/
```

### For Hooks

**Before**:
```python
docs_path = Path('docs/')
```

**After**:
```python
from validate_structure import USER_DOC_FILES, DEV_DOC_FILES

if file.name in USER_DOC_FILES:
    docs_path = Path('plugins/autonomous-dev/docs/')
elif file.name in DEV_DOC_FILES:
    docs_path = Path('docs/')
```

---

## Refactoring Checklist

### Phase 1: Documentation
- [x] Create ROOT-VS-PLUGIN-ARCHITECTURE.md
- [ ] Update CONTRIBUTING.md with new rules
- [ ] Update DEVELOPMENT.md with architecture

### Phase 2: Core Components
- [x] doc-master agent
- [x] /sync-docs command
- [x] .env.example (DEV_MODE)
- [ ] documentation-guide skill

### Phase 3: Related Commands
- [ ] /sync-docs-organize
- [ ] /sync-docs-auto
- [ ] /sync-docs-api
- [ ] /sync-docs-changelog
- [ ] /align-project (all variants)
- [ ] /commit-push
- [ ] /commit-release

### Phase 4: All Agents
- [ ] implementer
- [ ] planner
- [ ] security-auditor
- [ ] researcher
- [ ] reviewer
- [ ] orchestrator

### Phase 5: All Skills
- [ ] testing-guide
- [ ] python-standards
- [ ] security-patterns
- [ ] research-patterns
- [ ] engineering-standards

### Phase 6: All Hooks
- [ ] auto_update_docs.py
- [ ] auto_track_issues.py
- [ ] auto_tdd_enforcer.py

### Phase 7: Testing
- [ ] Test /sync-docs with real files
- [ ] Test validation script
- [ ] Test all affected commands
- [ ] Verify no broken references

---

## Success Criteria

- ✅ All components respect ROOT vs PLUGIN
- ✅ `python scripts/validate_structure.py` passes
- ✅ No hardcoded `docs/` paths (use validation rules)
- ✅ All cross-references updated
- ✅ DEV_MODE works as expected

---

**This architecture enables sustainable plugin development while maintaining clean marketplace distribution.**
