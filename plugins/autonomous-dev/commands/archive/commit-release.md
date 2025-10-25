---
description: Release commit - complete validation + version bump + GitHub Release (5-10min)
---

# Release Commit (Level 4)

**Production release with complete validation, version bump, and GitHub Release**

---

## Usage

```bash
/commit-release
/commit-release --version=1.2.0
```

**Time**: 5-10 minutes
**Validates**: Complete system integrity
**Outputs**: Git tag, GitHub Release, version bump

---

## What This Does

1. All from Level 3 (full integrity + doc sync + PROJECT.md validation)
2. **Full system integrity check**
3. **Version bump** (semantic versioning)
4. **Generate release notes** from CHANGELOG
5. **Create git tag**
6. **Create GitHub Release**

---

## Expected Output

```
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
│  ✅ README.md rebuilt                                        │
│  ✅ All documentation synchronized                           │
│  ✅ CHANGELOG.md complete                                    │
│  ✅ Version numbers updated (1.2.0)                          │
│                                                              │
│ Phase 3: Architectural Validation 🤖                         │
│  ✅ PROJECT.md alignment: 100%                               │
│  ✅ Architecture: No drift detected                          │
│                                                              │
│ Phase 4: Release Preparation 📦                              │
│  ✅ Git tag created: v1.2.0                                  │
│  ✅ Release notes generated                                  │
│                                                              │
│ Total time: 7m 23s                                           │
│ Status: READY FOR RELEASE ✅                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Release Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Version: v1.2.0
Previous: v1.1.0

Features Added:
- feat(auth): JWT refresh token support
- feat(api): Rate limiting middleware
- feat(docs): Auto-sync documentation

Bugs Fixed:
- fix(auth): Token expiration edge case
- fix(api): Memory leak in connection pool

Commits: 12
Files Changed: 24
Tests: 65/65 passing
Coverage: 92%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Released v1.2.0
🔗 https://github.com/user/repo/releases/tag/v1.2.0
```

---

## When to Use

- ✅ Production releases
- ✅ Major milestones
- ✅ Publishing to package registries
- ✅ After QA approval

---

## Related Commands

- `/commit` - Level 1: Quick commit (5s)
- `/commit-check` - Level 2: Full tests without push (60s)
- `/commit-push` - Level 3: Full integrity + push (3min)

---

## Semantic Versioning

**Format**: `MAJOR.MINOR.PATCH` (e.g., `1.2.0`)

**Auto-detection** (if `--version` not specified):
```
- Breaking changes (BREAKING CHANGE in commits) → MAJOR bump
- New features (feat: commits) → MINOR bump
- Bug fixes only (fix: commits) → PATCH bump
```

**Manual override**:
```bash
/commit-release --version=2.0.0
```

---

## Implementation

**Use the Task tool with orchestrator agent**:

```markdown
I need to run a Level 4 Release Commit with complete validation.

Please orchestrator agent:

1. **Phase 1: Pre-Release Integrity**
   - Run /format
   - Run /test (all tests including UAT, architecture)
   - Check coverage (80%+ required)
   - Run /security-scan
   - Check dependencies (all up to date)

2. **Phase 2: System Synchronization**
   - Rebuild README.md from PROJECT.md
   - Sync all documentation
   - Update CHANGELOG.md with release notes
   - Determine version bump (or use provided version)
   - Update version in:
     - package.json (if exists)
     - setup.py (if exists)
     - __version__ (if exists)
     - PROJECT.md metadata

3. **Phase 3: Architectural Validation**
   - Validate PROJECT.md alignment (100% required for release)
   - Check architecture (no drift allowed)
   - Verify all goals met

4. **Phase 4: Release Preparation**
   - Generate release notes from CHANGELOG
   - Create git tag: v{version}
   - Create GitHub Release with notes
   - Attach any artifacts (if configured)

5. **Commit, Tag, and Publish**
   - Stage all files (including version bumps)
   - Create commit: "chore: release v{version}"
   - Create annotated git tag
   - Push to GitHub (with --follow-tags)
   - Create GitHub Release

Please return a detailed summary of:
- Version number (old → new)
- All checks performed
- Files modified
- Commit hash
- Tag name
- GitHub Release URL
```

---

## Version Bump Details

**Files to update**:

**Python**:
```python
# setup.py
version="1.2.0"

# src/__init__.py
__version__ = "1.2.0"
```

**JavaScript/TypeScript**:
```json
// package.json
{
  "version": "1.2.0"
}
```

**PROJECT.md metadata**:
```yaml
---
version: 1.2.0
---
```

---

## Release Notes Generation

**Extract from CHANGELOG.md**:
```markdown
## [1.2.0] - 2025-10-20

### Added
- JWT refresh token support
- Rate limiting middleware
- Auto-sync documentation

### Fixed
- Token expiration edge case
- Memory leak in connection pool

### Changed
- Updated dependencies
```

**Parse conventional commits** (if CHANGELOG not updated):
```bash
# Get commits since last release
git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:"%s"

# Group by type:
# - feat: → Added
# - fix: → Fixed
# - docs: → Documentation
# - refactor: → Changed
# - perf: → Performance
```

---

## Git Tag Creation

```bash
# Get version
VERSION="1.2.0"

# Create annotated tag
git tag -a "v${VERSION}" -m "Release v${VERSION}

Features:
- JWT refresh token support
- Rate limiting middleware

Fixes:
- Token expiration edge case

🤖 Generated with Claude Code"

# Push tag
git push origin --follow-tags
```

---

## GitHub Release Creation

```bash
# Using gh CLI
gh release create "v${VERSION}" \
  --title "Release v${VERSION}" \
  --notes-file release-notes.md \
  --latest

# Or using git tag notes
gh release create "v${VERSION}" \
  --title "Release v${VERSION}" \
  --notes "$(git tag -l --format='%(contents)' v${VERSION})" \
  --latest
```

---

## Configuration (.env)

```bash
# Release settings
RELEASE_AUTO_VERSION=true       # Auto-detect version bump
RELEASE_GENERATE_NOTES=true     # Auto-generate release notes
RELEASE_ATTACH_ARTIFACTS=false  # Attach build artifacts
GITHUB_RELEASE_CREATE=true      # Create GitHub Release
```

---

## Error Handling

**If validation fails**:
```
❌ Level 4 Release FAILED

Phase 1: Pre-Release Integrity ❌ FAILED
  - Coverage: 75% (required: 80%+ for release)
  - 1 security vulnerability found

Cannot proceed with release until all checks pass.

💡 Tip: Fix issues and run '/commit-release' again
```

**Release gate requirements**:
- ✅ All tests passing (100%)
- ✅ Coverage ≥ 80%
- ✅ No security vulnerabilities
- ✅ Dependencies up to date
- ✅ Documentation synchronized
- ✅ PROJECT.md alignment: 100%
- ✅ No architectural drift

**If any requirement fails** → Block release

---

## Post-Release

After successful release:
1. ✅ Tag created: `v1.2.0`
2. ✅ Pushed to GitHub
3. ✅ GitHub Release created
4. ✅ Version bumped in all files

**Next steps**:
```bash
# Deploy to production
# Announce release
# Update package registries (npm, PyPI, etc.)
```

---

**Use this for production releases. Ensures complete quality and creates public release.**
