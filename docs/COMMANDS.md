# Command Reference

**Complete list of all 33 slash commands with descriptions**

---

## Overview

All commands are now **separate, discoverable slash commands** with clear descriptions. When you type `/` in Claude Code, you'll see autocomplete suggestions for all available commands.

**Total Commands**: 33
- **Testing** (7 commands): `/test*`
- **Commit** (4 commands): `/commit*`
- **Alignment** (5 commands): `/align-project*`
- **Issues** (5 commands): `/issue*`
- **Documentation** (5 commands): `/sync-docs*`
- **Quality** (3 commands): `/format`, `/security-scan`, `/full-check`
- **Workflow** (4 commands): `/setup`, `/auto-implement`, `/uninstall`, more

---

## Quick Reference

### Testing Commands (7)

| Command | Time | Description |
|---------|------|-------------|
| `/test` | < 60s | Run all automated tests (unit + integration + UAT) |
| `/test-unit` | < 1s | Unit tests only - fast individual function validation |
| `/test-integration` | < 10s | Integration tests - validate components work together |
| `/test-uat` | < 60s | UAT tests - validate complete user workflows (automated) |
| `/test-uat-genai` | 2-5min | GenAI UX validation - analyze UX quality & goal alignment |
| `/test-architecture` | 2-5min | GenAI architectural validation - detect drift from intent |
| `/test-complete` | 5-10min | Complete pre-release validation (all tests + GenAI) |

### Commit Commands (4)

| Command | Time | Description |
|---------|------|-------------|
| `/commit` | < 5s | Quick commit - format + unit tests + security → local |
| `/commit-check` | < 60s | Standard commit - all tests + coverage → local |
| `/commit-push` | 2-5min | Push commit - full integrity + doc sync → GitHub |
| `/commit-release` | 5-10min | Release - complete validation + version bump + GitHub Release |

### Alignment Commands (5)

| Command | Time | Description |
|---------|------|-------------|
| `/align-project` | 5-10min | Analyze project alignment with PROJECT.md (read-only) |
| `/align-project-fix` | 10-15min | Auto-fix alignment issues (non-interactive) |
| `/align-project-safe` | 15-20min | Interactive 3-phase alignment (asks before changes) ⭐ Recommended |
| `/align-project-sync` | 20-30min | Safe alignment + GitHub sync (push + issues) |
| `/align-project-dry-run` | 5-10min | Preview alignment changes (no modifications) |

### Issue Commands (5)

| Command | Time | Description |
|---------|------|-------------|
| `/issue-auto` | < 5s | Auto-create GitHub Issues from last test run |
| `/issue-from-test` | < 5s | Create GitHub Issue from specific test failure |
| `/issue-from-genai` | < 5s | Create GitHub Issue from GenAI finding |
| `/issue-create` | < 5s | Manually create GitHub Issue (custom) |
| `/issue-preview` | < 5s | Preview issues without creating (dry run) |

### Documentation Commands (5)

| Command | Time | Description |
|---------|------|-------------|
| `/sync-docs` | 5-10min | Sync all documentation (filesystem + API + CHANGELOG) |
| `/sync-docs-api` | 2-3min | Sync API documentation only (extract docstrings) |
| `/sync-docs-changelog` | < 1min | Update CHANGELOG.md from commits |
| `/sync-docs-organize` | < 30s | Organize files - move .md from root to docs/ |
| `/sync-docs-auto` | 1-5min | Auto-detect changes and sync intelligently |

### Quality Commands (3)

| Command | Time | Description |
|---------|------|-------------|
| `/format` | < 5s | Format code (black, isort, prettier, eslint) |
| `/security-scan` | < 30s | Scan for secrets & vulnerabilities |
| `/full-check` | < 60s | Complete check (format + test + security) |

### Workflow Commands (4)

| Command | Time | Description |
|---------|------|-------------|
| `/setup` | 5-10min | Interactive setup wizard for autonomous-dev plugin |
| `/auto-implement` | 20-30min | Autonomous feature implementation (8-agent pipeline) |
| `/uninstall` | < 5s | Uninstall or disable autonomous-dev features |
| More commands available via `/help` |

---

## Command Categories

### Progressive Workflows

**Testing Progression**:
```
/test-unit         →  Fast feedback (< 1s)
/test              →  All automated (< 60s)
/test-uat-genai    →  UX validation (2-5min)
/test-architecture →  Architecture check (2-5min)
/test-complete     →  Pre-release gate (5-10min)
```

**Commit Progression**:
```
/commit            →  Quick iteration (< 5s)
/commit-check      →  Feature complete (< 60s)
/commit-push       →  Share with team (2-5min)
/commit-release    →  Production release (5-10min)
```

**Alignment Progression**:
```
/align-project          →  Analysis only (5-10min)
/align-project-dry-run  →  Preview changes (5-10min)
/align-project-safe     →  Interactive fix (15-20min) ⭐
/align-project-sync     →  Fix + GitHub (20-30min)
```

### Quick Actions

**Fast Development Cycle**:
```bash
# 1. Make changes
# 2. Quick commit
/commit

# 3. Continue development
# 4. Another quick commit
/commit

# 5. Feature complete
/commit-check

# 6. Share with team
/commit-push
```

**Issue Tracking**:
```bash
# Run tests
/test-uat-genai

# Create issues from findings
/issue-auto

# Track specific issue
/issue-from-genai "No progress indicator"
```

**Documentation Sync**:
```bash
# Auto-detect and sync
/sync-docs-auto

# Or sync specific parts
/sync-docs-api       # API docs only
/sync-docs-changelog # CHANGELOG only
```

---

## Common Workflows

### Daily Development

```bash
# Morning: Check alignment
/align-project

# Development cycle
# ... make changes ...
/commit                # Quick commit
# ... more changes ...
/commit                # Another quick commit

# Feature complete
/commit-check          # All tests
/commit-push           # Push to GitHub
```

### Before Code Review

```bash
# Ensure quality
/full-check            # Format + test + security

# Check alignment
/test-architecture     # Architectural validation

# Check UX
/test-uat-genai        # UX validation

# Sync docs
/sync-docs-auto        # Update documentation

# Push for review
/commit-push
```

### Pre-Release

```bash
# Complete validation
/test-complete         # All tests + GenAI

# Track findings
/issue-auto            # Create issues

# Sync everything
/sync-docs             # All documentation

# Release
/commit-release        # Version bump + GitHub Release
```

###Before Merge

```bash
# Final checks
/test-complete         # Complete validation
/align-project         # Check alignment
/commit-push           # Full integrity + push
```

---

## Tips & Best Practices

### Use Progressive Commands

✅ **Start small, scale up**:
- Use `/test-unit` during development (fast feedback)
- Use `/test` before committing (complete automated tests)
- Use `/test-complete` before releases (everything)

✅ **Commit progressively**:
- Use `/commit` for rapid iteration
- Use `/commit-check` for feature completion
- Use `/commit-push` before merge
- Use `/commit-release` for production

### Auto-Detect When Possible

✅ **Smart commands**:
- `/sync-docs-auto` - Only syncs what changed
- `/issue-auto` - Detects all findings automatically
- `/test-complete` - Runs everything in sequence

### Preview Before Acting

✅ **Dry run first**:
- `/align-project-dry-run` - See what will change
- `/issue-preview` - See what issues will be created
- `/align-project` - Analysis before fix

### Use Interactive for Safety

✅ **Interactive mode**:
- `/align-project-safe` - Asks before each change (recommended for first time)
- `/issue-create` - Manual control over issue creation

---

## Configuration

Many commands respect `.env` settings:

```bash
# Commit defaults
COMMIT_DEFAULT_LEVEL=quick      # Default commit level
COMMIT_COVERAGE_MIN=80          # Minimum coverage %

# GitHub integration
GITHUB_AUTO_ISSUE=true          # Auto-create issues
GITHUB_ISSUE_LABEL=automated    # Label for auto-issues

# Documentation
DOCS_AUTO_ORGANIZE=true         # Auto-organize files
DOCS_AUTO_SYNC_ON_COMMIT=true   # Sync before commits

# Testing
TEST_AUTO_TRACK_ISSUES=false    # Auto-create issues from tests
```

---

## Command Discovery

**In Claude Code**:
1. Type `/` to see all commands
2. Type `/test` to see all test commands
3. Type `/commit` to see all commit commands
4. Type `/issue` to see all issue commands

**Each command shows**:
- Short description
- Time estimate
- What it does

**Example**:
```
/test-unit          Unit tests only - fast validation (< 1s)
/test-integration   Integration tests - components together (< 10s)
/test-uat          UAT tests - user workflows (< 60s)
```

---

## Related Documentation

- [Commit Workflow](commit-workflow.md) - Progressive commit details
- [Testing Guide](../plugins/autonomous-dev/commands/test.md) - Complete testing reference
- [PROJECT.md](.claude/PROJECT.md) - Project architecture and goals

---

**All 33 commands are now independently discoverable with clear descriptions!**
