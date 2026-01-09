## [3.46.0] - 2026-01-09
### Changed
- Simplify version tracking: Single source of truth via VERSION file (#206)
  - CLAUDE.md now references `plugins/autonomous-dev/VERSION` instead of hardcoded version
  - Removed Version column from Component Versions table
  - Removed version annotations from pipeline step descriptions
  - Added `_read_version_file()` and `_check_no_hardcoded_versions()` validation methods

### Fixed
- Fix doc-master auto-apply (#204)