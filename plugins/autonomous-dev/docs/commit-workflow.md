# Progressive Commit Workflow

**Four levels of validation from quick commit → production release**

---

## Quick Reference

| Command | Level | Time | Validates | Pushes | Use When |
|---------|-------|------|-----------|--------|----------|
| `/commit` | 1 | 5s | Format, unit tests, security | No | Rapid iteration |
| `/commit-check` | 2 | 60s | All tests, coverage (80%+) | No | Feature complete |
| `/commit-push` | 3 | 3min | Full integrity, docs, PROJECT.md | Yes | Before merge |
| `/commit-release` | 4 | 7min | Complete + version bump | Yes + Tag | Production |

---

## Level 1: Quick Commit `/commit`

**Purpose**: Fast validation for rapid iteration

**What it does**:
- ✅ Format code (black, isort, prettier)
- ✅ Run unit tests only
- ✅ Scan for secrets
- ✅ Generate conventional commit message
- ✅ Commit locally (don't push)

**When to use**:
- During active development
- Quick checkpoint commits
- Before switching branches
- Early in feature development

**Example**:
```bash
/commit
# ✅ Committed locally (abc1234)
# 💡 Run '/commit-push' when ready to push
```

---

## Level 2: Standard Commit `/commit-check`

**Purpose**: Complete test validation before committing

**What it does**:
- ✅ All from Level 1
- ✅ Run ALL tests (unit + integration + UAT)
- ✅ Check coverage (80%+ required)
- ✅ Check doc sync status
- ✅ Commit locally (don't push)

**When to use**:
- Feature completion
- Before code review
- After significant changes
- Before sharing branch

**Example**:
```bash
/commit-check
# ✅ All tests: PASSED (65/65)
# ✅ Coverage: 92%
# ✅ Committed locally (def5678)
```

---

## Level 3: Push Commit `/commit-push`

**Purpose**: Full integrity validation with push to GitHub

**What it does**:
- ✅ All from Level 2
- ✅ Check dependency updates
- ✅ Rebuild README.md from PROJECT.md
- ✅ Sync documentation cross-references
- ✅ Update CHANGELOG.md
- ✅ Validate PROJECT.md alignment (GenAI)
- ✅ Create GitHub Issues for findings
- ✅ Commit + Push to GitHub

**When to use**:
- Before merge to main
- Sharing complete feature with team
- End of development session
- Before production deployment

**Example**:
```bash
/commit-push
# Phase 1: Code Quality ✅
# Phase 2: Documentation Sync ✅
# Phase 3: Architectural Validation ✅
# Phase 4: Issue Tracking ✅
# ✅ Pushed to GitHub (ghi9012)
```

---

## Level 4: Release `/commit-release`

**Purpose**: Production release with version bump and GitHub Release

**What it does**:
- ✅ All from Level 3
- ✅ Full system integrity check
- ✅ Version bump (semantic versioning)
- ✅ Generate release notes from CHANGELOG
- ✅ Create git tag
- ✅ Create GitHub Release
- ✅ Push everything

**When to use**:
- Production releases
- Major milestones
- Publishing to package registries
- After QA approval

**Example**:
```bash
/commit-release
/commit-release --version=1.2.0

# ✅ Released v1.2.0
# 🔗 https://github.com/user/repo/releases/tag/v1.2.0
```

---

## Commit Message Format

All levels use **Conventional Commits** format:

```
<type>(<scope>): <description>

<body>

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code restructure
- `test`: Tests only
- `chore`: Config, dependencies

**Auto-detection**:
- New files/functions → `feat`
- Bug-related keywords → `fix`
- Only docs changed → `docs`
- Only tests changed → `test`

---

## Progressive Fallback

If higher level fails, you can fallback:

```
❌ Level 3 Push Commit FAILED
   - README.md rebuild failed

💡 Tip: Run '/commit-check' to commit without push
💡 Or: Run '/commit' for quick commit
```

---

## Configuration (.env)

```bash
# Commit defaults
COMMIT_DEFAULT_LEVEL=quick      # quick, check, push, release
COMMIT_AUTO_PUSH=false          # Auto-push after commit
COMMIT_AUTO_ISSUE=true          # Auto-create GitHub issues

# Validation
COMMIT_COVERAGE_MIN=80          # Minimum coverage %
COMMIT_SECURITY_SCAN=true       # Run security scan
COMMIT_README_REBUILD=true      # Auto-rebuild README on push

# GitHub integration
GITHUB_AUTO_ISSUE=true          # Create issues for findings
GITHUB_ISSUE_LABEL=automated    # Label for auto-issues
```

---

## Typical Workflow

### Daily Development

```bash
# Feature development
# ... make changes ...
/commit                    # Quick commit (5s)

# ... more changes ...
/commit                    # Another quick commit

# Feature complete
/commit-check              # Full tests (60s)

# Ready to share
/commit-push               # Push to GitHub (3min)
```

### Release Flow

```bash
# Development complete
/commit-check              # Verify all tests pass

# Pre-release validation
/commit-push               # Full integrity + docs

# Production release
/commit-release            # Version bump + GitHub Release
```

---

## Error Handling

**If checks fail**:
```
❌ Quick Commit FAILED

Issues found:
1. ❌ Format check failed (3 files)
2. ❌ Unit tests failed (2/45)
3. ❌ Security: 1 secret detected

Fix issues and retry.
```

**Progressive gates**:
- Level 1 fails → Must fix to proceed
- Level 2 fails → Can fallback to Level 1
- Level 3 fails → Can fallback to Level 2
- Level 4 fails → Must meet all release gates

---

## Release Gates (Level 4)

**Requirements for production release**:
- ✅ All tests passing (100%)
- ✅ Coverage ≥ 80%
- ✅ No security vulnerabilities
- ✅ Dependencies up to date
- ✅ Documentation synchronized
- ✅ PROJECT.md alignment: 100%
- ✅ No architectural drift

**If any fails** → Release blocked

---

## Related Docs

- [Commands Documentation](../plugins/autonomous-dev/commands/)
- [Testing Guide](../plugins/autonomous-dev/commands/test.md)
- [Security Scan](../plugins/autonomous-dev/commands/security-scan.md)
- [PROJECT.md Guide](.claude/PROJECT.md)

---

**Progressive validation ensures quality at every level, from quick commits to production releases.**
