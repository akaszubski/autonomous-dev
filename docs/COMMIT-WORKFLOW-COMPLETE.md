# Complete Commit Workflow - Integrity Gateway to Release

**Progressive validation from quick commit → full integrity → push → release**

---

## The Vision

**Commit as a progressive integrity gateway**:
1. `/commit` - Quick integrity checks, commit locally
2. `/commit --push` - Full integrity checks, push to GitHub
3. `/commit --release` - Complete validation + release workflow

**Each level ensures**:
- Code quality
- Documentation sync
- Dependency updates
- README accuracy
- System alignment
- Intent preservation

---

## Four Progressive Levels

### Level 1: Quick Commit (Local)
```bash
/commit
/commit --quick
```

**Runs**:
- ✅ Format code (black, isort, prettier)
- ✅ Unit tests (< 1s)
- ✅ Security scan (secrets detection)
- ✅ Generate conventional commit message
- ✅ **Commit locally** (don't push)

**Time**: < 5s
**Use for**: Rapid iteration during development

---

### Level 2: Standard Commit (Local)
```bash
/commit --check
/commit --standard
```

**Runs**:
- ✅ All from Level 1
- ✅ All tests (unit + integration + UAT)
- ✅ Coverage check (80%+)
- ✅ Documentation sync check
- ✅ **Commit locally** (don't push)

**Time**: < 60s
**Use for**: Feature completion, before review

---

### Level 3: Push Commit (GitHub) ⭐
```bash
/commit --push
/commit --integrity
```

**Runs**:
- ✅ All from Level 2
- ✅ **Update dependencies** (check for updates)
- ✅ **Rebuild README.md** (from PROJECT.md + docs)
- ✅ **Sync documentation** (ensure all cross-refs correct)
- ✅ **Validate PROJECT.md alignment** (architecture validation)
- ✅ **GenAI UX validation** (if UI/UX changes)
- ✅ **Update CHANGELOG.md** (from commits since last release)
- ✅ **Create GitHub Issues** (for any findings)
- ✅ **Commit + Push to GitHub**

**Time**: 2-5min
**Use for**: Before merge, sharing with team

---

### Level 4: Release (Production) 🚀
```bash
/commit --release
/commit --release --version=1.2.0
```

**Runs**:
- ✅ All from Level 3
- ✅ **Full system integrity check**:
  - All documentation synchronized
  - All cross-references valid
  - README.md reflects current state
  - CHANGELOG.md complete
  - Dependencies up to date
  - No security vulnerabilities
- ✅ **Architectural validation** (100% alignment)
- ✅ **System performance analysis** (ROI, costs)
- ✅ **Version bump** (semantic versioning)
- ✅ **Generate release notes** (from CHANGELOG + commits)
- ✅ **Create git tag** (v1.2.0)
- ✅ **Push to GitHub with tags**
- ✅ **Create GitHub Release** (with notes)
- ✅ **Notify** (optional: Slack, Discord, email)

**Time**: 5-10min
**Use for**: Production releases

---

## Detailed Workflows

### Level 1: Quick Commit

```bash
$ /commit

Running Level 1: Quick Commit...

┌─ Quick Integrity Checks ────────────────────┐
│  ✅ Format: PASSED                           │
│  ✅ Unit Tests: PASSED (45/45, 0.8s)         │
│  ✅ Security: PASSED (no secrets detected)   │
└──────────────────────────────────────────────┘

Analyzing changes...
- Modified: src/auth.py (+35, -12)
- Modified: tests/unit/test_auth.py (+18, -0)

Generated commit message:
┌──────────────────────────────────────────────┐
│ feat(auth): add JWT refresh token support   │
│                                              │
│ - Added refresh token endpoint              │
│ - Updated token expiration logic             │
│ - Added tests for refresh flow              │
└──────────────────────────────────────────────┘

Commit locally (no push)? [Y/n]: Y

[main 1a2b3c4] feat(auth): add JWT refresh token support
 2 files changed, 53 insertions(+), 12 deletions(-)

✅ Committed locally
💡 Run '/commit --push' when ready to push to GitHub
```

---

### Level 2: Standard Commit

```bash
$ /commit --check

Running Level 2: Standard Commit...

┌─ Standard Integrity Checks ─────────────────┐
│                                              │
│ Code Quality:                                │
│  ✅ Format: PASSED                           │
│  ✅ Unit Tests: PASSED (45/45, 0.8s)         │
│  ✅ Integration Tests: PASSED (12/12, 4.2s)  │
│  ✅ UAT Tests: PASSED (8/8, 15.3s)           │
│  ✅ Coverage: 92% (target: 80%+) ✅          │
│  ✅ Security: PASSED                         │
│                                              │
│ Documentation:                               │
│  ✅ Docstring coverage: 95%                  │
│  ⚠️  README.md out of sync (minor)           │
│                                              │
│ Total time: 21.5s                            │
│ Status: PASSED (1 warning)                   │
│                                              │
└──────────────────────────────────────────────┘

Warning: README.md may need update
Run '/commit --push' to auto-sync documentation

Commit locally? [Y/n]: Y

[main 5e6f7g8] feat(auth): add JWT refresh token support
 2 files changed, 53 insertions(+), 12 deletions(-)

✅ Committed locally
⚠️  1 warning (will fix on push)
```

---

### Level 3: Push Commit (Full Integrity)

```bash
$ /commit --push

Running Level 3: Push Commit (Full Integrity)...

┌─ Full Integrity Workflow ───────────────────────────────────┐
│                                                              │
│ Phase 1: Code Quality ✅                                     │
│  ✅ Format: PASSED                                           │
│  ✅ All Tests: PASSED (65/65, 20.3s)                         │
│  ✅ Coverage: 92%                                            │
│  ✅ Security: PASSED                                         │
│                                                              │
│ Phase 2: Documentation Sync 🔄                               │
│  🔄 Checking dependencies...                                 │
│     ✅ All dependencies up to date                           │
│  🔄 Rebuilding README.md from PROJECT.md...                  │
│     ✅ README.md updated (sections: 3, features: 12)         │
│  🔄 Syncing documentation cross-references...                │
│     ✅ All cross-references valid (48 links checked)         │
│  🔄 Updating CHANGELOG.md...                                 │
│     ✅ Added entry: v1.1.1 - 2025-10-20                      │
│                                                              │
│ Phase 3: Architectural Validation (GenAI) 🤖                 │
│  🔄 Validating PROJECT.md alignment...                       │
│     ✅ All goals aligned                                     │
│     ✅ Within scope                                          │
│     ✅ Constraints respected                                 │
│  🔄 Validating UX (changed files: src/api/)...               │
│     ✅ UX Score: 8.5/10                                      │
│  🔄 Validating architecture...                               │
│     ✅ 100% aligned with documented intent                   │
│     ⚠️  1 optimization opportunity found                     │
│                                                              │
│ Phase 4: Issue Tracking 📋                                   │
│  ✅ Created issue #42: "Use Haiku for simple tasks (save 9%)"│
│                                                              │
│ Total time: 3m 42s                                           │
│ Status: PASSED ✅ (1 optimization tracked)                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Files modified during integrity checks:
  M README.md (auto-generated from PROJECT.md)
  M CHANGELOG.md (added v1.1.1 entry)

Staging updated files...
git add README.md CHANGELOG.md

Creating commit with integrity validation...
[main 9i0j1k2] feat(auth): add JWT refresh token support

Validation:
- Tests: 65/65 passed (92% coverage)
- UX Score: 8.5/10
- Architecture: 100% aligned
- Issues tracked: 1 optimization

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>

Pushing to GitHub...
Enumerating objects: 8, done.
Counting objects: 100% (8/8), done.
...
To github.com:user/repo.git
   5e6f7g8..9i0j1k2  main -> main

✅ Pushed to GitHub
✅ Documentation synchronized
✅ Issues tracked: gh issue list --label automated
```

---

### Level 4: Release

```bash
$ /commit --release --version=1.2.0

Running Level 4: Release Workflow...

┌─ Complete Release Validation ───────────────────────────────┐
│                                                              │
│ Phase 1: Pre-Release Integrity ✅                            │
│  ✅ All tests: PASSED (65/65)                                │
│  ✅ Coverage: 92%                                            │
│  ✅ Security: PASSED (no vulnerabilities)                    │
│  ✅ Dependencies: All up to date                             │
│                                                              │
│ Phase 2: System Synchronization 🔄                           │
│  🔄 Rebuilding README.md...                                  │
│     ✅ Generated from PROJECT.md + documentation             │
│     ✅ All features documented (15 total)                    │
│     ✅ All commands listed (12 total)                        │
│  🔄 Syncing all documentation...                             │
│     ✅ Cross-references validated (127 links)                │
│     ✅ All guides synchronized                               │
│  🔄 Updating CHANGELOG.md...                                 │
│     ✅ Generated from commits since v1.1.0                   │
│     ✅ Categorized: 5 features, 3 fixes, 2 docs              │
│  🔄 Updating version numbers...                              │
│     ✅ package.json: 1.2.0                                   │
│     ✅ setup.py: 1.2.0                                       │
│     ✅ __version__: 1.2.0                                    │
│                                                              │
│ Phase 3: Architectural Validation (GenAI) 🤖                 │
│  ✅ PROJECT.md alignment: 100%                               │
│  ✅ UX quality: 8.7/10                                       │
│  ✅ Architecture: No drift detected                          │
│  ✅ All invariants: TRUE                                     │
│                                                              │
│ Phase 4: System Performance Analysis 📊                      │
│  ✅ Avg cost/feature: $0.82 (< $1.00 target)                 │
│  ✅ Success rate: 100%                                       │
│  ✅ ROI: 485× (excellent)                                    │
│  ⚠️  2 optimization opportunities                            │
│                                                              │
│ Phase 5: Release Preparation 📦                              │
│  🔄 Generating release notes...                              │
│     ✅ Created from CHANGELOG.md + commits                   │
│  🔄 Creating git tag...                                      │
│     ✅ Tag: v1.2.0                                           │
│  🔄 Committing release files...                              │
│     M README.md                                              │
│     M CHANGELOG.md                                           │
│     M package.json                                           │
│     M setup.py                                               │
│                                                              │
│ Total time: 7m 23s                                           │
│ Status: READY FOR RELEASE ✅                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Release Summary:
- Version: 1.2.0
- Previous: 1.1.0
- Changes: 5 features, 3 fixes, 2 docs
- Tests: 65/65 passed
- Coverage: 92%
- Quality: All validations passed

Release notes:
┌──────────────────────────────────────────────────────────────┐
│ # Release v1.2.0                                             │
│                                                              │
│ ## Features                                                  │
│ - JWT refresh token support                                 │
│ - User profile endpoints                                     │
│ - Email notifications                                        │
│ - Export to CSV/JSON                                         │
│ - Search filters                                             │
│                                                              │
│ ## Fixes                                                     │
│ - Fixed session timeout bug                                  │
│ - Resolved race condition in auth                            │
│ - Fixed export filename encoding                             │
│                                                              │
│ ## Documentation                                             │
│ - Updated API reference                                      │
│ - Added deployment guide                                     │
│                                                              │
│ ## Metrics                                                   │
│ - Tests: 65/65 passed (92% coverage)                         │
│ - UX Score: 8.7/10                                           │
│ - Performance: $0.82/feature (485× ROI)                      │
└──────────────────────────────────────────────────────────────┘

Proceed with release? [Y/n]: Y

Committing release files...
[main 3l4m5n6] release: v1.2.0

Complete system integrity validation passed
- All documentation synchronized
- All dependencies updated
- All cross-references validated
- Architecture 100% aligned

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>

Creating git tag v1.2.0...
✅ Tag created

Pushing to GitHub (with tags)...
To github.com:user/repo.git
   9i0j1k2..3l4m5n6  main -> main
 * [new tag]         v1.2.0 -> v1.2.0

Creating GitHub Release...
✅ Release created: https://github.com/user/repo/releases/tag/v1.2.0

┌─ Release Complete ──────────────────────────────────────────┐
│                                                             │
│ ✅ v1.2.0 Released Successfully                             │
│                                                             │
│ View release:                                               │
│ https://github.com/user/repo/releases/tag/v1.2.0            │
│                                                             │
│ Notifications:                                              │
│  ✅ GitHub release created                                  │
│  ✅ Issues created (2 optimizations)                        │
│                                                             │
│ Next steps:                                                 │
│  - Monitor deployment                                       │
│  - Review optimization issues                               │
│  - Start next sprint                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## System Integrity Components

### 1. Dependency Updates

**Checks and updates**:
```bash
# Python
pip list --outdated
pip-review --auto  # Or manual review

# JavaScript
npm outdated
npm update

# Updates in release commit
```

---

### 2. README.md Rebuild

**Auto-generates from**:
- `PROJECT.md` (goals, scope, features)
- `docs/` (feature descriptions)
- `commands/` (available commands)
- `agents/` (agent descriptions)
- `skills/` (skill descriptions)

**Template**:
```markdown
# {PROJECT_NAME} - Auto-generated from PROJECT.md

{PROJECT_DESCRIPTION}

## Features

{AUTO_GENERATED_FROM_DOCS}

## Commands

{AUTO_GENERATED_FROM_COMMANDS}

## Quick Start

{AUTO_GENERATED_FROM_QUICKSTART}

## Documentation

{AUTO_GENERATED_CROSS_REFS}
```

---

### 3. Documentation Sync

**Validates**:
- All cross-references work (internal links)
- All code examples are current
- All command references exist
- All file paths are correct
- Version numbers match
- CHANGELOG.md complete

**Fixes automatically**:
- Broken links → Update to correct path
- Missing references → Add missing docs
- Outdated examples → Update from actual code
- Version mismatches → Update all to current

---

### 4. CHANGELOG.md Update

**Auto-generates from git commits**:
```markdown
# Changelog

## [1.2.0] - 2025-10-20

### Added (feat:)
- JWT refresh token support (#42)
- User profile endpoints (#43)
- Email notifications (#44)

### Fixed (fix:)
- Session timeout bug (#45)
- Race condition in auth (#46)

### Changed (refactor:)
- Simplified validation logic

### Documentation (docs:)
- Updated API reference
- Added deployment guide

### Performance
- Optimized database queries (20% faster)
```

---

### 5. PROJECT.md Alignment Validation

**Validates**:
```bash
# Reads PROJECT.md GOALS, SCOPE, CONSTRAINTS
# Validates all changes align

Questions answered:
1. ✅ Does this serve documented GOALS?
2. ✅ Is this within SCOPE?
3. ✅ Does this respect CONSTRAINTS?
4. ✅ Is architecture preserved?
5. ✅ Are invariants maintained?
```

---

### 6. Cross-Reference Validation

**Checks all links**:
```bash
# Internal links
[See ARCHITECTURE.md](ARCHITECTURE.md) → ✅ Exists
[commands/test.md](commands/test.md) → ✅ Exists

# External links (optional)
[GitHub](https://github.com/...) → ✅ Reachable

# Code references
`src/auth.py:42` → ✅ File exists, line valid
`/test` command → ✅ Command exists
```

---

## Complete Command Reference

```bash
# Level 1: Quick Commit (local only)
/commit                              # Quick checks, commit
/commit --quick                      # Alias
/commit "custom message"             # With message

# Level 2: Standard Commit (local only)
/commit --check                      # All tests, commit
/commit --standard                   # Alias

# Level 3: Push Commit (full integrity)
/commit --push                       # Full integrity + push
/commit --integrity                  # Alias
/commit --push --track-issues        # With issue tracking (default)

# Level 4: Release
/commit --release                    # Complete release workflow
/commit --release --version=1.2.0    # Specify version
/commit --release --major            # Bump major (2.0.0)
/commit --release --minor            # Bump minor (1.2.0)
/commit --release --patch            # Bump patch (1.1.1)

# Advanced
/commit --push --skip-genai          # Skip GenAI validation
/commit --push --skip-readme         # Don't rebuild README
/commit --push --skip-deps           # Don't check dependencies
/commit --release --dry-run          # Preview release
/commit --force                      # Emergency bypass (NOT recommended)
```

---

## Configuration

### .env Configuration

```bash
# === Commit Workflow ===

# Default level (1=quick, 2=standard, 3=push, 4=release)
COMMIT_DEFAULT_LEVEL=1

# Auto-push on commit (makes /commit → /commit --push)
COMMIT_AUTO_PUSH=false

# === Integrity Checks ===

# Rebuild README.md on push
COMMIT_REBUILD_README=true

# Update dependencies on push
COMMIT_UPDATE_DEPS=true

# Sync documentation on push
COMMIT_SYNC_DOCS=true

# Update CHANGELOG.md on push
COMMIT_UPDATE_CHANGELOG=true

# === Validation ===

# Run GenAI validation on push
COMMIT_GENAI_VALIDATION=true

# Create issues for findings
COMMIT_AUTO_TRACK_ISSUES=true

# === Release ===

# Versioning scheme (semver, calver)
COMMIT_VERSION_SCHEME=semver

# Create GitHub release
COMMIT_CREATE_RELEASE=true

# Notify on release (slack, discord, email)
COMMIT_NOTIFY_ON_RELEASE=false
```

---

### PROJECT.md Configuration

```markdown
## Commit Workflow

**Default Level**: 1 (quick during dev)
**Auto-Push**: false (manual push)

**On Push (Level 3)**:
- ✅ Rebuild README.md from PROJECT.md
- ✅ Update dependencies
- ✅ Sync all documentation
- ✅ Update CHANGELOG.md
- ✅ Run GenAI validation
- ✅ Create issues for findings

**On Release (Level 4)**:
- ✅ All push checks
- ✅ Full system integrity validation
- ✅ Version bump (semantic versioning)
- ✅ Generate release notes
- ✅ Create git tag
- ✅ Create GitHub Release
- ✅ Notify team (Slack)
```

---

## Progressive Integrity Levels

### Why Progressive?

**Not every commit needs full validation**:
- Quick commits during dev (Level 1)
- Feature complete commits (Level 2)
- Sharing with team (Level 3)
- Production releases (Level 4)

**Each level adds**:
- More comprehensive checks
- More documentation sync
- More system alignment validation
- More automation

---

## Benefits

### For Developers
- **Fast iteration**: Level 1 (< 5s) during dev
- **Confidence**: Level 3 ensures integrity before push
- **Automation**: README, CHANGELOG, docs auto-sync
- **No manual work**: Dependencies, docs, all automatic

### For Quality
- **Progressive assurance**: Each level builds on previous
- **System integrity**: All docs sync, all refs valid
- **Architectural alignment**: GenAI validates intent
- **Complete traceability**: Every level documented

### For Teams
- **Consistent releases**: Level 4 always complete
- **Auto-documentation**: README always current
- **Issue tracking**: Nothing gets lost
- **Clear changelog**: Auto-generated from commits

### For System
- **Self-maintaining**: Docs sync automatically
- **Self-validating**: Integrity checks built-in
- **Self-documenting**: README auto-generated
- **Self-improving**: Issues tracked automatically

---

## Summary

**Four Progressive Levels**:

1. **Quick Commit** (< 5s)
   - Format + unit + security
   - Commit locally
   - Use: During development

2. **Standard Commit** (< 60s)
   - All tests + coverage
   - Commit locally
   - Use: Feature complete

3. **Push Commit** (2-5min) ⭐
   - Full integrity validation
   - Rebuild README + sync docs
   - Update dependencies + CHANGELOG
   - GenAI validation
   - Create issues
   - **Push to GitHub**
   - Use: Before merge, sharing

4. **Release** (5-10min) 🚀
   - Complete system integrity
   - Version bump
   - Generate release notes
   - Create tag + GitHub Release
   - Notify team
   - Use: Production releases

**Each level ensures**:
- ✅ Code quality
- ✅ Documentation sync (Level 3+)
- ✅ Dependency updates (Level 3+)
- ✅ README accuracy (Level 3+)
- ✅ System alignment (Level 3+)
- ✅ Intent preservation (Level 3+)
- ✅ Complete traceability (Level 4)

**The autonomous system maintains itself!** 🚀

---

**Next**: Implement this progressive workflow?
