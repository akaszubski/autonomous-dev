## [Unreleased]

### Changed
- Consolidate ARCHITECTURE.md into ARCHITECTURE-OVERVIEW.md (#208)
  - Archived ARCHITECTURE.md to docs/archived/ with deprecation notice
  - Updated 10+ file references to point to ARCHITECTURE-OVERVIEW.md
  - Added 21 tests for consolidation validation
  - Ensures single source of truth for architecture documentation

## [3.46.0] - 2026-01-09
### Changed
- Update component counts across all documentation (#207)
  - Commands: 9 → 24 (consolidated /implement variations, added /worktree and others)
  - Hooks: 64 → 67 (added pre-commit hook variations)
  - Libraries: 69 → 145 (expanded automation, validation, infrastructure libraries)
  - Updated CLAUDE.md Component Versions table
  - Updated docs/ARCHITECTURE-OVERVIEW.md counts
  - Updated docs/DOCUMENTATION_INDEX.md counts
- Simplify version tracking: Single source of truth via VERSION file (#206)
  - CLAUDE.md now references `plugins/autonomous-dev/VERSION` instead of hardcoded version
  - Removed Version column from Component Versions table
  - Removed version annotations from pipeline step descriptions
  - Added `_read_version_file()` and `_check_no_hardcoded_versions()` validation methods

### Fixed
- Fix doc-master auto-apply (#204)