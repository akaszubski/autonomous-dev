## [Unreleased]

### Added
- Document evaluation decision for setup-wizard.md split (#214)
  - Created docs/evaluations/ directory with evaluation documentation
  - Issue #214: Evaluated whether to split setup-wizard.md (1,145 lines) into multiple agents
  - Decision: KEEP UNIFIED with hybrid optimizations (extract reusable libraries)
  - Documented sequential phase dependencies and user experience impact
  - Added evaluation tests to validate assumptions and decision rationale
  - Created docs/evaluations/README.md as index of evaluation documents
  - Established pattern for future architectural evaluations
- Create HOOK-REGISTRY.md with activation status (#209)
  - Comprehensive registry of all 66 hooks with activation status
  - Documents trigger points, environment variables, and purposes
  - Provides quick reference for hook lifecycle integration points
  - Added cross-references to HOOKS.md, SANDBOXING.md, GIT-AUTOMATION.md
  - Added 34 tests for hook registry validation

### Changed
- Consolidate alignment commands into single /align command (#210)
  - Removed legacy commands: `/align-project`, `/align-project-retrofit`, `/align-claude`
  - Consolidated into `/align` with three modes: `project`, `retrofit`, `claude`
  - Updated BROWNFIELD-ADOPTION.md to use `/align --retrofit`
  - Updated WORKFLOWS.md to use `/align` and `/align --retrofit`
  - Added 35 tests for command consolidation validation
- Consolidate ARCHITECTURE.md into ARCHITECTURE-OVERVIEW.md (#208)
  - Archived ARCHITECTURE.md to docs/archived/ with deprecation notice
  - Updated 10+ file references to point to ARCHITECTURE-OVERVIEW.md
  - Added 21 tests for consolidation validation
  - Ensures single source of truth for architecture documentation
- Archive disabled hooks with deprecation docs (#211)
  - Consolidated auto_approve_tool.py and mcp_security_enforcer.py into unified_pre_tool.py
  - Created plugins/autonomous-dev/hooks/archived/README.md with migration guide
  - Updated docs/HOOKS.md with consolidated hook consolidation section
  - Updated docs/SANDBOXING.md with historical note and consolidated architecture explanation
  - Updated docs/TOOL-AUTO-APPROVAL.md with deprecation notice (Layer 4 of unified_pre_tool.py)
  - Updated docs/MCP-SECURITY.md with deprecation notice (Layer 2 of unified_pre_tool.py)
  - Updated docs/HOOK-REGISTRY.md to mark archived hooks as deprecated
  - No functionality changes - all features preserved in unified_pre_tool.py
- Resolve duplicate auto_git_workflow.py (#212)
  - Archived duplicate auto_git_workflow.py hook file
  - Created backward compatibility shim at .claude/hooks/auto_git_workflow.py (56 lines)
  - Shim redirects to unified_git_automation.py for single source of truth
  - Updated docs/GIT-AUTOMATION.md with deprecation notice and migration guidance
  - Updated docs/HOOKS.md with archival context
  - Updated docs/ARCHITECTURE-OVERVIEW.md to document shim and unified implementation
  - Updated plugins/autonomous-dev/hooks/archived/README.md with auto_git_workflow.py archival details
  - All git automation functionality preserved with unified consolidation
- Standardize command YAML frontmatter (#213)
  - Created COMMAND-FRONTMATTER-SCHEMA.md with complete field definitions and examples
  - Updated all 21 command files to use kebab-case field names (argument-hint, allowed-tools)
  - Deprecated `tools:` field in favor of `allowed-tools:` (security-enforced)
  - Added validation hook: validate_command_frontmatter_flags.py
  - Added 28 tests for frontmatter standardization validation
  - Ensures consistent autocomplete metadata and security whitelisting

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