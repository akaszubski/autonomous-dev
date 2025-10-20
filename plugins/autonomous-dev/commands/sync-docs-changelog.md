---
description: Update CHANGELOG.md from recent commits (follows Keep a Changelog)
---

# Update CHANGELOG

**Update CHANGELOG.md from recent commits**

---

## Usage

```bash
/sync-docs-changelog
```

**Scope**: CHANGELOG.md only
**Time**: < 1 minute
**Format**: Keep a Changelog

---

## What This Does

Updates CHANGELOG.md from git commits:
1. Get commits since last release
2. Parse conventional commit messages
3. Group by type (Added, Changed, Fixed, etc.)
4. Add new section to CHANGELOG.md
5. Follow Keep a Changelog format

**Only updates CHANGELOG** - doesn't sync API docs or organize files.

---

## Expected Output

```
Updating CHANGELOG.md...

Getting commits since last release...
  Last release: v1.0.0 (2 weeks ago)
  New commits: 12

Parsing conventional commits...
  ✅ 3 features (feat:)
  ✅ 2 bug fixes (fix:)
  ✅ 1 refactoring (refactor:)
  ✅ 1 documentation (docs:)
  ✅ 5 chores (chore:)

Updating CHANGELOG.md...
  ✅ Added section: [Unreleased]
  ✅ Grouped by type
  ✅ Sorted by priority

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Added to CHANGELOG.md:

## [Unreleased]

### Added
- JWT refresh token support (feat: add JWT refresh token endpoint)
- Rate limiting middleware (feat: add rate limiting to API)
- Auto-sync documentation (feat: add doc-master agent)

### Fixed
- Token expiration edge case (fix: handle token expiration correctly)
- Memory leak in connection pool (fix: close unused connections)

### Changed
- Updated dependencies to latest versions (chore: bump dependencies)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CHANGELOG.md updated
```

---

## Conventional Commits

**Parses commit types**:
- `feat:` → **Added** section
- `fix:` → **Fixed** section
- `refactor:` → **Changed** section
- `perf:` → **Changed** section
- `docs:` → **Documentation** section
- `test:` → Ignored (not user-facing)
- `chore:` → Ignored (not user-facing)

**Example commit**:
```
feat(auth): add JWT refresh token support

Adds new /refresh endpoint for token renewal.
Supports automatic token refresh on expiration.
```

**Becomes CHANGELOG entry**:
```markdown
### Added
- JWT refresh token support
```

---

## Keep a Changelog Format

**Follows standard format**:
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features

### Changed
- Changes to existing features

### Fixed
- Bug fixes

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Security
- Security improvements

## [1.0.0] - 2025-10-01

### Added
- Initial release
```

---

## When to Use

- ✅ Before releases
- ✅ After significant changes
- ✅ In `/commit-push` (Level 3)
- ✅ In `/commit-release` (Level 4)
- ✅ Weekly/monthly updates

---

## Manual Additions

**You can still manually edit CHANGELOG**:
- Add breaking changes
- Add migration guides
- Add contributor credits

**Auto-sync preserves manual entries**.

---

## Configuration (.env)

```bash
# CHANGELOG settings
CHANGELOG_AUTO_UPDATE=true          # Auto-update on sync
CHANGELOG_INCLUDE_CHORES=false      # Include chore commits
CHANGELOG_GROUP_BY_SCOPE=false      # Group by scope (auth, api, etc.)
```

---

## Related Commands

- `/sync-docs` - Sync all documentation
- `/sync-docs-api` - API docs only
- `/sync-docs-organize` - File organization only
- `/commit-release` - Includes CHANGELOG update

---

**Use this before releases to ensure CHANGELOG is current with all changes.**
