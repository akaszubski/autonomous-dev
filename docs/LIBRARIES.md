# Shared Libraries Reference

**Last Updated: 2025-12-25
**Purpose**: Comprehensive API documentation for autonomous-dev shared libraries

This document provides detailed API documentation for shared libraries in `plugins/autonomous-dev/lib/` and `plugins/autonomous-dev/scripts/`. For high-level overview, see [CLAUDE.md](../CLAUDE.md) Architecture section.

## Overview

The autonomous-dev plugin includes shared libraries organized into the following categories:

### Core Libraries (25)

1. **security_utils.py** - Security validation and audit logging
2. **project_md_updater.py** - Atomic PROJECT.md updates with merge conflict detection
3. **version_detector.py** - Semantic version comparison for marketplace sync
4. **orphan_file_cleaner.py** - Orphaned file detection and cleanup
5. **sync_dispatcher.py** - Intelligent sync orchestration (marketplace/env/plugin-dev)
6. **validate_marketplace_version.py** - CLI script for version validation
7. **plugin_updater.py** - Interactive plugin update with backup/rollback
8. **update_plugin.py** - CLI interface for plugin updates
9. **hook_activator.py** - Automatic hook activation during updates
10. **auto_implement_git_integration.py** - Automatic git operations (commit/push/PR)
11. **batch_state_manager.py** - State-based auto-clearing for /batch-implement (v3.23.0)
12. **github_issue_fetcher.py** - GitHub issue fetching via gh CLI (v3.24.0)
13. **github_issue_closer.py** - Auto-close GitHub issues after /auto-implement (v3.22.0, Issue #91)
14. **path_utils.py** - Dynamic PROJECT_ROOT detection and path resolution (v3.28.0, Issue #79)
15. **validation.py** - Tracking infrastructure security validation (v3.28.0, Issue #79)
16. **failure_classifier.py** - Error classification (transient vs permanent) for /batch-implement (v3.33.0, Issue #89)
17. **batch_retry_manager.py** - Retry orchestration with circuit breaker for /batch-implement (v3.33.0, Issue #89)
18. **batch_retry_consent.py** - First-run consent handling for automatic retry (v3.33.0, Issue #89)
19. **session_tracker.py** - Session logging for agent actions with portable path detection (v3.28.0+, Issue #79)
20. **settings_merger.py** - Merge settings.local.json with template configuration (v3.39.0, Issue #98)
21. **settings_generator.py** - Generate settings.local.json with specific command patterns (NO wildcards) (v3.43.0+, Issue #115)
22. **feature_dependency_analyzer.py** - Smart dependency ordering for /batch-implement (v1.0.0, Issue #157)
23. **acceptance_criteria_parser.py** - Parse acceptance criteria from GitHub issues for UAT generation (v3.45.0+, Issue #161)
24. **test_tier_organizer.py** - Classify and organize tests into unit/integration/uat tiers (v3.45.0+, Issue #161)
25. **test_validator.py** - Execute tests and validate TDD workflow with quality gates (v3.45.0+, Issue #161)

### Tracking Libraries (3) - NEW in v3.28.0, ENHANCED in v3.48.0

22. **agent_tracker.py** (see section 24)
23. **session_tracker.py** (see section 25)
24. **workflow_tracker.py** (see section 26) - Workflow state tracking for preference learning (Issue #155)

### Installation Libraries (4) - NEW in v3.29.0

25. **file_discovery.py** - Comprehensive file discovery with exclusion patterns (Issue #80)
26. **copy_system.py** - Structure-preserving file copying with permission handling (Issue #80)
27. **installation_validator.py** - Coverage validation and missing file detection (Issue #80)
28. **install_orchestrator.py** - Coordinates complete installation workflows (Issue #80)

### Brownfield Retrofit Libraries (6)

31. **brownfield_retrofit.py** - Phase 0: Project analysis and tech stack detection
32. **codebase_analyzer.py** - Phase 1: Deep codebase analysis (multi-language)
33. **alignment_assessor.py** - Phase 2: Gap assessment and 12-Factor compliance
34. **migration_planner.py** - Phase 3: Migration plan with dependency tracking
35. **retrofit_executor.py** - Phase 4: Step-by-step execution with rollback
36. **retrofit_verifier.py** - Phase 5: Verification and readiness assessment

### MCP Security Libraries (3) - NEW in v3.37.0

39. **mcp_permission_validator.py** - Permission validation for MCP server operations (Issue #95)
40. **mcp_profile_manager.py** - Pre-configured security profiles for MCP (development, testing, production) (Issue #95)
41. **mcp_server_detector.py** - Identifies MCP server type from tool calls to enable server-specific validation (Issue #95)

### Script Utilities (2) - NEW in v3.42.0, ENHANCED in v3.44.0

42. **genai_install_wrapper.py** - CLI wrapper for setup-wizard Phase 0 GenAI-first installation with JSON output (Issue #109)
43. **migrate_hook_paths.py** - Migrate PreToolUse hook paths from hardcoded to portable ~/.claude/hooks/pre_tool_use.py (Issue #113)

## Design Patterns

- **Progressive Enhancement**: String → path → whitelist validation for graceful error recovery
- **Non-blocking Enhancement**: Enhancements don't block core operations
- **Two-tier Design**: Core logic + CLI interface for reusability and testing
- **Security First**: All file operations validated via security_utils.py

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [MCP-SECURITY.md](MCP-SECURITY.md) - MCP security configuration and API reference
- [PERFORMANCE.md](PERFORMANCE.md) - Performance optimization tracking
- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) - Git automation workflow
- [SECURITY.md](SECURITY.md) - Security hardening guide

---

# Library Reference

## 1. security_utils.py (628 lines, v3.4.3+)

**Purpose**: Centralized security validation and audit logging

### Functions

#### `validate_path(path, operation)`
- **Purpose**: 4-layer whitelist defense against path traversal attacks
- **Parameters**:
  - `path` (str|Path): Path to validate
  - `operation` (str): Operation type (e.g., "read", "write")
- **Returns**: `Path` object (validated and resolved)
- **Raises**: `SecurityError` if path violates security rules
- **Security Coverage**: CWE-22 (path traversal), CWE-59 (symlink resolution)
- **Validation Layers**:
  1. String checks (no "..", no absolute system paths)
  2. Symlink detection (blocks symlink attacks)
  3. Path resolution (resolves to canonical path)
  4. Whitelist validation (must be within allowed directories)

#### `validate_pytest_path(path)`
- **Purpose**: Special path validation for pytest execution
- **Parameters**: `path` (str|Path): Path to validate
- **Returns**: `Path` object (validated)
- **Features**: Auto-detects pytest environment, allows system temp while blocking system directories

#### `validate_input_length(input_str, max_length, field_name)`
- **Purpose**: Input length validation to prevent DoS attacks
- **Parameters**:
  - `input_str` (str): Input string to validate
  - `max_length` (int): Maximum allowed length
  - `field_name` (str): Field name for error messages
- **Raises**: `ValueError` if input exceeds max_length

#### `validate_agent_name(agent_name)`
- **Purpose**: Validate agent name format (alphanumeric, dash, underscore only)
- **Parameters**: `agent_name` (str): Agent name to validate
- **Raises**: `ValueError` if format is invalid

#### `validate_github_issue(issue_number)`
- **Purpose**: Validate GitHub issue number format
- **Parameters**: `issue_number` (int|str): Issue number to validate
- **Raises**: `ValueError` if format is invalid

#### `audit_log(event_type, details, level)`
- **Purpose**: Thread-safe JSON logging to security audit log
- **Parameters**:
  - `event_type` (str): Event type (e.g., "path_validation", "marketplace_sync")
  - `details` (dict): Event details
  - `level` (str): Log level ("INFO", "WARNING", "ERROR")
- **Features**: 10MB rotation, 5 backups, thread-safe

### Test Coverage
- 638 unit tests (98.3% coverage)

### Used By
- agent_tracker.py
- project_md_updater.py
- version_detector.py
- orphan_file_cleaner.py
- All security-critical operations

### Documentation
See `docs/SECURITY.md` for comprehensive security guide

---

## 2. project_md_updater.py (247 lines, v3.4.0+)

**Purpose**: Atomic PROJECT.md updates with security validation

### Functions

#### `update_goal_progress()` - Update goal progress atomically

**Signature**: `update_goal_progress(project_root, goal_title, progress_percent, notes)`

- **Purpose**: Update goal progress in PROJECT.md atomically
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `goal_title` (str): Goal title to update
  - `progress_percent` (int): Progress percentage (0-100)
  - `notes` (str): Optional progress notes
- **Returns**: `bool` (True if update succeeded)
- **Features**: Atomic writes, merge conflict detection, backup before update

### Internal Methods

#### `_atomic_write(file_path, content)`
- **Purpose**: Write file atomically using temp file + rename pattern
- **Security**: Uses mkstemp() for temp file creation, atomic rename

#### `_validate_update(project_root, goal_title, progress_percent)`
- **Purpose**: Validate update parameters
- **Raises**: `ValueError` if parameters are invalid

#### `_backup_before_update(file_path)`
- **Purpose**: Create backup before modifying PROJECT.md
- **Returns**: `Path` to backup file

#### `_detect_merge_conflicts(file_path)`
- **Purpose**: Detect if PROJECT.md has merge conflicts
- **Returns**: `bool` (True if conflicts detected)
- **Features**: Prevents data loss if PROJECT.md changed during update

### Test Coverage
- 24 unit tests (95.8% coverage)

### Used By
- auto_update_project_progress.py hook (SubagentStop)

---

## 3. version_detector.py (531 lines, v3.7.1+)

**Purpose**: Semantic version detection and comparison

### Classes

#### `Version`
- **Purpose**: Semantic version object with comparison operators
- **Attributes**:
  - `major` (int): Major version
  - `minor` (int): Minor version
  - `patch` (int): Patch version
  - `prerelease` (str|None): Pre-release identifier
- **Methods**:
  - `__eq__`, `__lt__`, `__le__`, `__gt__`, `__ge__`: Comparison operators
  - `__str__`: String representation (e.g., "3.7.1" or "3.7.1-beta")

#### `VersionComparison`
- **Purpose**: Result dataclass for version comparison
- **Attributes**:
  - `marketplace_version` (Version): Marketplace plugin version
  - `project_version` (Version): Local project plugin version
  - `is_upgrade` (bool): True if marketplace version is newer
  - `is_downgrade` (bool): True if marketplace version is older
  - `is_same` (bool): True if versions match
  - `message` (str): Human-readable comparison message

### Functions

#### `VersionDetector.detect_version_mismatch(marketplace_path, project_root)`
- **Purpose**: Compare marketplace plugin version vs local project version
- **Parameters**:
  - `marketplace_path` (str|Path): Path to marketplace plugin directory
  - `project_root` (str|Path): Project root directory
- **Returns**: `VersionComparison` object
- **Features**: Handles pre-release versions, semantic version comparison

#### `detect_version_mismatch(marketplace_path, project_root)` (convenience)
- **Purpose**: High-level API for version detection
- **Returns**: `VersionComparison` object

### Security
- Path validation via security_utils
- Audit logging (CWE-22, CWE-59 protection)

### Error Handling
- Clear error messages with context and expected format

### Pre-release Support
- Correctly handles `MAJOR.MINOR.PATCH` and `MAJOR.MINOR.PATCH-PRERELEASE` patterns

### Test Coverage
- 20 unit tests (version parsing, comparison, edge cases)

### Used By
- sync_dispatcher.py for marketplace version detection

### Related
- GitHub Issue #50

---

## 4. orphan_file_cleaner.py (778 lines, v3.7.1+ → v3.29.1)

**Purpose**: Orphaned file detection and cleanup + duplicate library prevention

**New in v3.29.1 (Issue #81)**: Duplicate library detection and pre-install cleanup to prevent `.claude/lib/` import conflicts

### Classes

#### `OrphanFile`
- **Purpose**: Representation of an orphaned file
- **Attributes**:
  - `path` (Path): Full path to orphaned file
  - `category` (str): File category ("command", "hook", "agent")
  - `is_orphan` (bool): Whether file is confirmed orphan (always True)
  - `reason` (str): Human-readable reason why file is orphaned

#### `CleanupResult`
- **Purpose**: Result dataclass for cleanup operation
- **Attributes**:
  - `orphans_detected` (int): Number of orphans detected
  - `orphans_deleted` (int): Number of orphans deleted
  - `dry_run` (bool): Whether this was a dry-run (no deletions)
  - `errors` (int): Number of errors encountered
  - `orphans` (List[OrphanFile]): List of detected orphan files
  - `success` (bool): Whether cleanup succeeded
  - `error_message` (str): Optional error message for failed operations
  - `files_removed` (int): Alias for orphans_deleted (for pre-install cleanup compatibility)
- **Properties**:
  - `summary` (str): Auto-generated human-readable summary of cleanup result

### Functions

#### `detect_orphans()` - Detect orphaned files

**Signature**: `detect_orphans(project_root, plugin_name="autonomous-dev")`

- **Purpose**: Detect orphaned files in commands/hooks/agents directories
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name (default: "autonomous-dev")
- **Returns**: `List[OrphanFile]`
- **Features**: Detects files not registered in plugin.json

#### `cleanup_orphans(project_root, dry_run, confirm, plugin_name)`
- **Purpose**: Clean up orphaned files with mode control
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `dry_run` (bool): If True, report only (don't delete), default: True
  - `confirm` (bool): If True, ask user before each deletion, default: False
  - `plugin_name` (str): Plugin name (default: "autonomous-dev")
- **Returns**: `CleanupResult`
- **Modes**:
  - `dry_run=True`: Report orphans without deleting
  - `confirm=True`: Ask user to confirm each deletion
  - `dry_run=False, confirm=False`: Auto mode - delete all orphans without prompts

#### `OrphanFileCleaner.find_duplicate_libs()` - NEW in v3.29.1

**Signature**: `find_duplicate_libs() -> List[Path]`

- **Purpose**: Detect Python files in `.claude/lib/` directory (duplicate library location)
- **Details**:
  - Identifies duplicate libraries in legacy `.claude/lib/` location
  - These files conflict with canonical location: `plugins/autonomous-dev/lib/`
  - Prevents import conflicts (CWE-627) when installing/updating plugin
- **Returns**: List of Path objects for duplicate library files found
  - Excludes `__init__.py` and `__pycache__` directories
  - Includes files in nested subdirectories
  - Returns empty list if `.claude/lib/` doesn't exist
- **Security**: All paths validated via `security_utils.validate_path()`
- **Example**:
  ```python
  cleaner = OrphanFileCleaner(project_root)
  duplicates = cleaner.find_duplicate_libs()
  print(f"Found {len(duplicates)} duplicate libraries")
  ```

#### `OrphanFileCleaner.pre_install_cleanup()` - NEW in v3.29.1

**Signature**: `pre_install_cleanup() -> CleanupResult`

- **Purpose**: Remove `.claude/lib/` directory before installation to prevent duplicates
- **Details**:
  - Performs pre-installation cleanup by removing legacy `.claude/lib/` directory
  - Prevents import conflicts when installing or updating plugin
  - Idempotent: Safe to call even if `.claude/lib/` doesn't exist
- **Returns**: `CleanupResult` with:
  - `success` (bool): Whether cleanup succeeded
  - `files_removed` (int): Count of duplicate files removed
  - `error_message` (str): Error description if cleanup failed
- **Behavior**:
  - Returns success immediately if `.claude/lib/` doesn't exist (idempotent)
  - Handles symlinks safely: removes symlink itself, preserves target (CWE-59)
  - Logs all operations to audit trail with timestamp and file count
  - Gracefully handles permission errors with clear error messages
  - Validates all paths before removal (CWE-22 prevention)
- **Integration**: Called by:
  - `install_orchestrator.py` (fresh install and upgrade)
  - `plugin_updater.py` (plugin update workflow)
- **Example**:
  ```python
  cleaner = OrphanFileCleaner(project_root)
  result = cleaner.pre_install_cleanup()
  if result.success:
      print(f"Removed {result.files_removed} duplicate files")
  else:
      print(f"Error: {result.error_message}")
  ```

### Security
- Path validation via security_utils.validate_path()
  - Prevents path traversal attacks (CWE-22)
  - Blocks symlink-based attacks (CWE-59)
  - Rejects path traversal patterns (.., absolute system paths)
- Audit logging:
  - Global security audit log (security_utils.audit_log)
  - Project-specific audit log: `logs/orphan_cleanup_audit.log` (JSON format)
  - All file operations logged with timestamp, user, operation type

### Error Handling
- Graceful per-file failures (one orphan failure doesn't block others)
- Permission errors reported clearly without aborting cleanup
- Symlinks handled specially to prevent CWE-59 attacks

### Test Coverage
- 62 unit tests (v3.29.1 additions):
  - Detection: 6 tests (empty dir, missing dir, nested files, etc.)
  - Cleanup: 6 tests (idempotent, symlinks, readonly files, etc.)
  - Integration: 10+ tests (install_orchestrator, plugin_updater)
  - Edge cases: 8 tests (large directories, permission errors, etc.)
- Original 22 tests for orphan detection/cleanup maintained
- Total coverage: 62+ tests

### Used By
- sync_dispatcher.py for marketplace sync cleanup
- install_orchestrator.py for fresh install and upgrade (pre_install_cleanup)
- plugin_updater.py for plugin update workflow (pre_install_cleanup)
- installation_validator.py for validation warnings (find_duplicate_libs)

### Related
- GitHub Issue #50 (Fix Marketplace Update UX)
- GitHub Issue #81 (Prevent .claude/lib/ Duplicate Library Imports) - NEW

---

## 5. sync_dispatcher.py (1530 lines, v3.7.1+ - Issue #127 CLI wrapper added)

**Purpose**: Intelligent sync orchestration with version detection and cleanup (Issue #97: Fixed sync directory silent failures)

### Classes

#### `SyncMode` (enum)
- `MARKETPLACE`: Sync from marketplace
- `ENV`: Sync development environment
- `PLUGIN_DEV`: Plugin development sync

#### `SyncResult`
- **Purpose**: Result dataclass for sync operation
- **Attributes**:
  - `success` (bool): Whether sync succeeded
  - `mode` (SyncMode): Which sync mode executed
  - `message` (str): Human-readable result
  - `details` (dict): Additional details (files updated, conflicts, etc.)
  - `version_comparison` (VersionComparison|None): Version comparison (marketplace mode only)
  - `orphan_cleanup` (CleanupResult|None): Cleanup result (marketplace mode only)
- **Properties**:
  - `summary` (str): Auto-generated comprehensive summary including version and cleanup info

### Functions

#### `SyncDispatcher._sync_directory(src, dst, pattern, description)` (v3.37.1+)
- **Purpose**: Sync directory with per-file operations (fixes Issue #97 shutil.copytree bug)
- **Parameters**:
  - `src` (Path): Source directory path
  - `dst` (Path): Destination directory path
  - `pattern` (str): File pattern to match (e.g., "*.md", "*.py", default "*")
  - `description` (str): Human-readable description for logging
- **Returns**: `int` - Number of files successfully copied
- **Raises**: `ValueError` if source doesn't exist or path validation fails
- **Features**:
  - Replaces buggy `shutil.copytree(dirs_exist_ok=True)` which silently fails to copy new files
  - Uses `FileDiscovery` to enumerate all matching files
  - Per-file copy operations with `copy2()` to preserve metadata
  - Preserves directory structure via `relative_to()` and mkdir parents
  - Security: Validates paths to prevent CWE-22 (path traversal) and CWE-59 (symlink attacks)
  - Continues on individual file errors (doesn't fail entire sync)
  - Audit logging per operation for debugging
- **Examples**:
  - `files = dispatcher._sync_directory(plugin_dir / "commands", claude_dir / "commands", "*.md", "command files")`
  - `files = dispatcher._sync_directory(plugin_dir / "hooks", claude_dir / "hooks", "*.py", "hook files")`

#### `SyncDispatcher.sync(mode, project_root, cleanup_orphans)`
- **Purpose**: Main entry point for sync operations
- **Parameters**:
  - `mode` (SyncMode): Sync mode
  - `project_root` (str|Path): Project root directory
  - `cleanup_orphans` (bool): Whether to clean up orphaned files (marketplace mode only)
- **Returns**: `SyncResult`

#### `sync_marketplace(project_root, cleanup_orphans)` (convenience)
- **Purpose**: High-level API for marketplace sync with enhancements
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `cleanup_orphans` (bool): Whether to clean up orphaned files
- **Returns**: `SyncResult`
- **Features**:
  - Version detection: Runs detect_version_mismatch() for marketplace vs. project comparison
  - Orphan cleanup: Conditional (cleanup_orphans parameter), with dry-run support
  - Error handling: Non-blocking - enhancements don't block core sync
  - Messaging: Shows upgrade/downgrade/up-to-date status and cleanup results

#### main() (CLI wrapper - NEW Issue #127)
- **Purpose**: Command-line interface wrapper for sync_dispatcher.py
- **Returns**: int - Exit code (0 success, 1 failure, 2 invalid args)
- **CLI Arguments**:
  - --github: Fetch latest files from GitHub (default if no flags)
  - --env: Sync environment (delegates to sync-validator agent)
  - --marketplace: Copy files from installed plugin
  - --plugin-dev: Sync plugin development files
  - --all: Execute all sync modes in sequence
- **Mutually Exclusive**: Only one mode flag allowed per invocation
- **Features**:
  - Auto-detection of sync mode based on CLI flags
  - Sensible default: GITHUB mode when no flags specified
  - Argument validation via argparse (returns exit code 2 for invalid args)
  - Helpful error messages and usage examples
  - Graceful handling of KeyboardInterrupt (user cancellation)
  - Exit code 0 for --help flag (standard argparse behavior)
- **Stdin/Stdout Handling**:
  - Success messages printed to stdout
  - Error messages printed to stderr
  - Preserves argparse exit behavior for --help and invalid args
- **Examples**:
  - python3 sync_dispatcher.py - Default GitHub mode
  - python3 sync_dispatcher.py --github - Explicit GitHub mode
  - python3 sync_dispatcher.py --env - Environment sync
  - python3 sync_dispatcher.py --marketplace - Marketplace sync
  - python3 sync_dispatcher.py --plugin-dev - Plugin development sync
  - python3 sync_dispatcher.py --all - All modes in sequence
  - python3 sync_dispatcher.py --help - Show usage information
- **Implementation**: Replaces manual mode detection, now directly embedded as if __name__ == "__main__": block
- **Used By**: /sync command (delegates to main() via subprocess)

### Security
- All paths validated via security_utils
- Audit logging to security audit (marketplace_sync events)

### Test Coverage
- Comprehensive testing of all sync modes

### Used By
- /sync command
- sync_marketplace() high-level API

### Related
- GitHub Issues #47, #50, #51

---

## 6. validate_marketplace_version.py (371 lines, v3.7.2+)

**Purpose**: CLI script for /health-check marketplace integration

### Functions

#### `validate_marketplace_version(project_root, verbose, json_output)`
- **Purpose**: Main entry point for version validation
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `verbose` (bool): Verbose output
  - `json_output` (bool): Machine-readable JSON output
- **Returns**: `VersionComparison` object

#### `_parse_version(version_str)`
- **Purpose**: Parse semantic version string
- **Parameters**: `version_str` (str): Version string (e.g., "3.7.1")
- **Returns**: `Version` object

#### `_format_output(version_comparison, json_output)`
- **Purpose**: Format output for CLI display
- **Parameters**:
  - `version_comparison` (VersionComparison): Version comparison result
  - `json_output` (bool): Whether to output JSON
- **Returns**: `str` (formatted output)

### CLI Arguments
- `--project-root`: Project root path (required)
- `--verbose`: Verbose output
- `--json`: Machine-readable JSON output format

### Output Formats
- **Human-readable**: "Project v3.7.0 vs Marketplace v3.7.1 - Update available"
- **JSON**: Structured result with version comparison data

### Security
- Path validation via security_utils.validate_path()
- Audit logging to security audit

### Error Handling
- Non-blocking errors (marketplace not found is not fatal)
- Exit code 1 on errors

### Integration
- Called by health_check.py `_validate_marketplace_version()` method

### Test Coverage
- 7 unit tests (version comparison, output formatting, error cases)

### Used By
- health-check command (CLI invocation)
- /health-check validation

### Related
- GitHub Issue #50 Phase 1 (marketplace version validation integration into /health-check)

---

## 7. plugin_updater.py (868 lines, v3.8.2+)

**Purpose**: Interactive plugin update with version detection, backup, rollback, and security hardening

### Classes

#### `UpdateError` (base exception)
- Base class for all update-related errors

#### `BackupError` (UpdateError)
- Raised when backup operations fail

#### `VerificationError` (UpdateError)
- Raised when verification fails

#### `UpdateResult`
- **Purpose**: Result dataclass for update operation
- **Attributes**:
  - `success` (bool): Whether update succeeded
  - `updated` (bool): Whether plugin was actually updated
  - `message` (str): Human-readable result
  - `old_version` (str|None): Previous plugin version
  - `new_version` (str|None): New plugin version
  - `backup_path` (str|None): Path to backup (if created)
  - `rollback_performed` (bool): Whether rollback was performed
  - `hooks_activated` (bool): Whether hooks were activated
  - `hooks_added` (List[str]): List of hooks added
  - `details` (dict): Additional details

### Key Methods

#### `PluginUpdater.check_for_updates(project_root, plugin_name)`
- **Purpose**: Check for available updates without performing update
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name (default: "autonomous-dev")
- **Returns**: `VersionComparison` object

#### `PluginUpdater.update(project_root, plugin_name, interactive, auto_backup)`
- **Purpose**: Perform interactive or non-interactive update
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name
  - `interactive` (bool): Whether to prompt for confirmation
  - `auto_backup` (bool): Whether to create backup before update
- **Returns**: `UpdateResult`
- **Features**:
  - Interactive confirmation prompts (customizable)
  - Automatic backup before update (timestamped, in /tmp, 0o700 permissions)
  - Automatic rollback on any failure (sync, verification, unexpected errors)
  - Verification: checks version matches expected, validates critical files exist
  - Cleanup: removes backup after successful update
  - Hook activation: Auto-activates hooks from new version (first install only)

#### `_create_backup(project_root, plugin_name)`
- **Purpose**: Create timestamped backup
- **Security**: 0o700 permissions, symlink detection
- **Returns**: `Path` to backup directory

#### `_rollback(backup_path, project_root, plugin_name)`
- **Purpose**: Restore from backup on failure
- **Security**: Path validation, symlink blocking

#### `_cleanup_backup(backup_path)`
- **Purpose**: Remove backup after successful update

#### `_verify_update(project_root, plugin_name, expected_version)`
- **Purpose**: Verify update succeeded
- **Features**: Version validation, critical file validation

#### `_activate_hooks(project_root, plugin_name)`
- **Purpose**: Activate hooks from new plugin version
- **Integration**: Calls hook_activator.py


#### _sync_lib_files (NEW - Issue #123)
- **Purpose**: Sync lib files from plugin to ~/.claude/lib/ (non-blocking)
- **Workflow**:
  1. Read installation_manifest.json to verify lib directory should be synced
  2. Create ~/.claude/lib/ if doesn't exist
  3. Copy each .py file from plugin/lib/ to ~/.claude/lib/
  4. Validate all paths for security (CWE-22, CWE-59)
  5. Audit log all operations
  6. Handle errors gracefully (non-blocking)
- **Returns**: Number of lib files successfully synced (0 on complete failure)
- **Security**:
  - Target path validation: Ensures ~/.claude/lib is within user home
  - Source path validation: Prevents CWE-22 (path traversal)
  - Symlink rejection: Prevents CWE-59 (symlink attacks)
  - Manifest validation: Ensures lib files explicitly listed
  - Audit logging for all operations
- **Non-Blocking**: Lib sync failures don't block plugin update
- **Features**:
  - Graceful degradation: Missing manifest or source files handled cleanly
  - Returns lib_files_synced count in UpdateResult.details
  - Skips __init__.py (not needed in global lib)

#### _validate_and_fix_permissions (NEW - Issue #123)
- **Purpose**: Validate and fix settings.local.json permissions (non-blocking)
- **Workflow**:
  1. Check if settings.local.json exists (skip if not)
  2. Load and validate permissions
  3. If issues found:
     - Backup existing file with timestamp
     - Generate template with correct patterns
     - Fix using fix_permission_patterns()
     - Write fixed settings atomically
  4. Return result with action taken
- **Returns**: PermissionFixResult with action, issues found, and fixes applied
- **Actions**:
  - validated: No issues found, settings already correct
  - fixed: Issues found and fixed
  - regenerated: Corrupted JSON regenerated from template
  - skipped: No settings.local.json found
  - failed: Validation or fix failed
- **Backup Strategy**:
  - Timestamped filename: settings.local.json.backup-YYYYMMDD-HHMMSS-NNNNNN
  - Location: .claude/backups/
  - Permissions: Inherits from original file
- **Non-Blocking**: Permission fix failures don't block plugin operations
- **Security**:
  - Atomic writes: Uses tempfile plus rename
  - Path validation: CWE-22 and CWE-59 prevention
  - Backup creation: Before any modifications
  - Audit logging: All operations logged with context

#### PermissionFixResult (NEW - Issue #123)
- **Purpose**: Dataclass tracking permission validation/fix results
- **Attributes**:
  - success (bool): Whether validation/fix succeeded
  - action (str): Action taken (validated, fixed, regenerated, skipped, failed)
  - issues_found (int): Count of detected permission issues
  - fixes_applied (List[str]): List of fixes that were applied
  - backup_path (Path or None): Path to backup file (if created)
  - message (str): Human-readable result message
### Security (GitHub Issue #52 - 5 CWE vulnerabilities addressed)
- **CWE-22 (Path Traversal)**: Marketplace path validation, rollback path validation, user home directory check
- **CWE-78 (Command Injection)**: Plugin name length + format validation (alphanumeric, dash, underscore only)
- **CWE-59 (Symlink Following/TOCTOU)**: Backup path re-validation after creation, symlink detection
- **CWE-117 (Log Injection)**: Audit log input sanitization, audit log signature standardized
- **CWE-732 (Permissions)**: Backup directory permissions 0o700 (user-only)
- All validations use security_utils module for consistency
- Audit logging for all security operations to security_audit.log

### Test Coverage
- 53 unit tests (39 existing + 14 new security tests, 46 passing, 7 design issues to fix)

### Used By
- update_plugin.py CLI script
- /update-plugin command

### Related
- GitHub Issue #50 Phase 2 (interactive plugin update)
- GitHub Issue #52 (security hardening)

---

## 8. update_plugin.py (380 lines, v3.8.0+)

**Purpose**: CLI script for interactive plugin updates

### Functions

#### `parse_args()`
- **Purpose**: Parse command-line arguments
- **Returns**: `argparse.Namespace`

#### `main()`
- **Purpose**: Main entry point
- **Returns**: Exit code (0=success, 1=error, 2=no update needed)

#### `_format_version_output(version_comparison)`
- **Purpose**: Format version comparison for display
- **Returns**: `str` (formatted output)

#### `_prompt_for_confirmation(message)`
- **Purpose**: Interactive confirmation prompt
- **Returns**: `bool` (True if user confirmed)

### CLI Arguments
- `--check-only`: Check for updates without performing update (dry-run)
- `--yes`, `-y`: Skip confirmation prompts (non-interactive mode)
- `--auto-backup`: Create backup before update (default: enabled)
- `--no-backup`: Skip backup creation (advanced users only)
- `--verbose`, `-v`: Enable verbose logging
- `--json`: Output JSON for scripting (machine-readable)
- `--project-root`: Path to project root (default: current directory)
- `--plugin-name`: Name of plugin to update (default: autonomous-dev)

### Exit Codes
- `0`: Success (update performed or already up-to-date)
- `1`: Error (update failed)
- `2`: No update needed (when --check-only)

### Output Modes
- **Human-readable**: Rich ASCII tables with status indicators and progress
- **JSON**: Machine-readable structured output for scripting
- **Verbose**: Detailed logging of all operations (backups, verifications, rollbacks)

### Integration
- Invokes PluginUpdater from plugin_updater.py

### Security
- Path validation via security_utils
- Audit logging

### Error Handling
- Clear error messages with context and guidance

### Test Coverage
- Comprehensive unit tests (argument parsing, output formatting, interactive flow)

### Used By
- /update-plugin command (bash invocation)

### Related
- GitHub Issue #50 Phase 2 (interactive plugin update command)

---

## 9. hook_activator.py (938 lines, v3.8.1+, format migration v3.44.0+)

**Purpose**: Automatic hook activation during plugin updates with Claude Code 2.0 format migration (Issue #112)

### Classes

#### `ActivationError` (base exception)
- Base class for activation-related errors

#### `SettingsValidationError` (ActivationError)
- Raised when settings validation fails

#### `ActivationResult`
- **Purpose**: Result dataclass for activation operation
- **Attributes**:
  - `activated` (bool): Whether hooks were activated
  - `first_install` (bool): Whether this was first install
  - `message` (str): Human-readable result
  - `hooks_added` (List[str]): List of hooks added
  - `settings_path` (str): Path to settings.json
  - `details` (dict): Additional details

### Key Methods

#### `HookActivator.activate_hooks(project_root, plugin_name)`
- **Purpose**: Activate hooks from new plugin version with automatic format migration
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name
- **Returns**: `ActivationResult`
- **Features**:
  - First install detection: Checks for existing settings.json file
  - Automatic hook activation: Activates hooks from plugin.json on first install
  - Smart merging: Preserves existing customizations when updating
  - Format migration: Detects legacy format and auto-migrates to Claude Code 2.0 (Issue #112)
  - Atomic writes: Prevents corruption via tempfile + rename pattern
  - Validation: Structure validation (required fields, hook format)
  - Error recovery: Graceful handling of malformed JSON, permissions issues

#### `detect_first_install(project_root)`
- **Purpose**: Check if settings.json exists (first install vs update detection)
- **Returns**: `bool`

#### `_read_settings(settings_path)`
- **Purpose**: Read and parse existing settings.json
- **Returns**: `dict`
- **Error Handling**: Graceful handling of malformed JSON

#### `_merge_hooks(existing_hooks, new_hooks)`
- **Purpose**: Merge new hooks with existing settings
- **Features**: Preserves existing customizations

#### `_validate_settings(settings)`
- **Purpose**: Validate settings structure and content
- **Raises**: `SettingsValidationError` if validation fails

#### `_ensure_claude_dir(claude_dir)`
- **Purpose**: Create .claude directory if missing
- **Security**: Correct permissions

#### `_atomic_write(settings_path, settings)`
- **Purpose**: Write settings.json atomically
- **Pattern**: Tempfile + rename

#### `validate_hook_format(settings_data)` (NEW - Issue #112)
- **Purpose**: Detect legacy vs Claude Code 2.0 hook format
- **Parameters**:
  - `settings_data` (Dict): Settings dictionary to validate
- **Returns**: `Dict` with `is_legacy` (bool) and `reason` (str)
- **Detection Criteria**:
  - Legacy indicators: Missing `timeout` fields, flat command strings, missing nested `hooks` arrays
  - Modern CC2: All hooks have `timeout`, nested dicts with matchers containing `hooks` arrays
- **Raises**: `SettingsValidationError` if structure is malformed
- **Example**:
  ```python
  result = validate_hook_format(settings)
  if result['is_legacy']:
      print(f"Legacy format: {result['reason']}")
  ```

#### `migrate_hook_format_cc2(settings_data)` (NEW - Issue #112)
- **Purpose**: Auto-migrate legacy hook format to Claude Code 2.0 format
- **Parameters**:
  - `settings_data` (Dict): Settings to migrate (can be legacy or modern)
- **Returns**: `Dict` with migrated settings (deep copy, original unchanged)
- **Transformations**:
  - Adds `timeout: 5` to all hooks missing it
  - Converts flat string commands to nested dict structure
  - Wraps commands in nested `hooks` array if missing
  - Adds `matcher: '*'` if missing
  - Preserves user customizations (custom timeouts, matchers)
- **Idempotent**: Running multiple times produces same result
- **Example**:
  ```python
  legacy = {"hooks": {"PrePush": ["auto_test.py"]}}
  modern = migrate_hook_format_cc2(legacy)
  # Result: modern['hooks']['PrePush'][0]['hooks'][0]['timeout'] == 5
  ```

#### migrate_hooks_to_object_format(settings_path) (NEW - Issue #135)
- **Purpose**: Auto-migrate hooks from array format to object format during /sync --marketplace (Claude Code v2.0.69+ compatibility)
- **Parameters**:
  - settings_path (Path): Path to settings.json (typically user home/.claude/settings.json)
- **Returns**: Dict with keys:
  - migrated (bool): True if migration was performed
  - backup_path (Optional[Path]): Path to timestamped backup if migrated
  - format (str): Detected format - array (needs migration), object (already modern), invalid, or missing
  - error (Optional[str]): Error message if migration failed
- **Format Detection**:
  - **Array format** (pre-v2.0.69): Array of hook objects with event and command fields
  - **Object format** (v2.0.69+): Object keyed by event name with nested matcher and hooks arrays
- **Migration Steps**:
  1. Check if file exists (returns format: missing if not)
  2. Read and parse JSON (graceful error handling for corrupted files)
  3. Detect format (array vs object)
  4. If array format: Create timestamped backup, transform array to object structure, write atomically (tempfile + rename), return success with backup path
  5. If migration fails: Rollback from backup (no partial migrations)
- **Security** (CWE-22, CWE-362, CWE-404 prevention):
  - Path validation (settings must be in user home/.claude/)
  - Atomic writes prevent corruption
  - Backup creation before modifications
  - No secrets exposed in logs
  - Full rollback on error
- **Integration**: Called automatically during /sync --marketplace after settings merge
- **Non-blocking**: Migration failures do not stop sync (graceful degradation)

### Security
- Path validation via security_utils
- Audit logging to logs/security_audit.log
- Secure permissions (0o600)
- Backup creation before format migration

### Error Handling
- Non-blocking (activation failures do not block plugin update)
- Graceful degradation if migration fails (existing settings preserved)

### Format Migration (Issue #112 and Issue #135)
- **Issue #112**: Automatic migration during activate_hooks() if legacy format detected
- **Issue #135**: Automatic migration during /sync --marketplace for user settings
- **Transparent**: Backup created before any changes
- **Idempotent**: Safe to run multiple times
- **Backwards Compatible**: Legacy settings continue to work unchanged

### Test Coverage
- 41 unit tests (first install, updates, merge logic, error cases, malformed JSON)
- 28 migration tests (format detection, legacy-to-CC2 conversion, backup creation)
- 12 tests for Issue #135 migration (array-to-object format, backup creation, rollback)

### Used By
- plugin_updater.py for /update-plugin command
- activate_hooks() for automatic format migration during install/update
- sync_dispatcher.py for /sync --marketplace command (Issue #135)

### Related
- GitHub Issue #112 (Hook Format Migration to Claude Code 2.0)
- GitHub Issue #135 (Auto-migrate settings.json hooks format during /sync)

---

## 11. auto_implement_git_integration.py (1,466 lines, v3.9.0+)

**Purpose**: Automatic git operations orchestration

### Key Functions

#### `execute_step8_git_operations(workflow_id, request, branch, push, create_pr, base_branch)`
- **Purpose**: Main entry point orchestrating complete workflow (commit, push, PR creation)
- **Parameters**:
  - `workflow_id` (str): Workflow identifier
  - `request` (str): Feature request description
  - `branch` (str): Branch name
  - `push` (bool): Whether to push to remote
  - `create_pr` (bool): Whether to create PR
  - `base_branch` (str): Base branch for PR
- **Returns**: `ExecutionResult`

#### `check_consent_via_env()`
- **Purpose**: Parse consent from environment variables
- **Returns**: `dict` with `AUTO_GIT_ENABLED`, `AUTO_GIT_PUSH`, `AUTO_GIT_PR` values

#### `invoke_commit_message_agent(workflow_id, request)`
- **Purpose**: Call commit-message-generator agent
- **Returns**: `dict` with commit message

#### `invoke_pr_description_agent(workflow_id, request, branch, base_branch)`
- **Purpose**: Call pr-description-generator agent
- **Returns**: `dict` with PR description

#### `create_commit_with_agent_message(commit_message)`
- **Purpose**: Stage changes and commit with agent-generated message
- **Returns**: `str` (commit SHA)

#### `push_and_create_pr(branch, pr_description, base_branch)`
- **Purpose**: Push to remote and optionally create PR via gh CLI
- **Returns**: `dict` with PR URL

### Validation Functions

#### `validate_agent_output(agent_output)`
- **Purpose**: Verify agent response is usable
- **Checks**: success key, message length, format

#### `validate_git_state()`
- **Purpose**: Check repository state
- **Checks**: not detached, no merge conflicts, clean working directory

#### `validate_branch_name(branch_name)`
- **Purpose**: Ensure branch name follows conventions

#### `validate_commit_message(message)`
- **Purpose**: Validate commit message format (conventional commits)

### Prerequisite Checks

#### `check_git_credentials()`, `check_git_available()`, `check_gh_available()`
- **Purpose**: Validate prerequisites before operations

### Fallback Functions

#### `build_manual_git_instructions(commit_message)`, `build_fallback_pr_command(pr_description, branch, base_branch)`
- **Purpose**: Generate fallback instructions if automation fails

### ExecutionResult

**Attributes**:
- `success` (bool): Whether operation succeeded
- `commit_sha` (str|None): Commit SHA (if created)
- `pushed` (bool): Whether pushed to remote
- `pr_created` (bool): Whether PR was created
- `pr_url` (str|None): PR URL (if created)
- `error` (str|None): Error message (if failed)
- `details` (dict): Additional details
- `manual_instructions` (str|None): Fallback instructions

### Features
- Consent-based automation via environment variables (defaults: all disabled for safety)
- Agent-driven commit and PR descriptions (uses existing agents)
- Graceful degradation with manual fallback instructions (non-blocking)
- Prerequisite validation before operations
- Subprocess safety (command injection prevention)
- Comprehensive error handling with actionable messages

### Security
- Uses security_utils.validate_path() for all paths
- Audit logs to security_audit.log
- Safe subprocess calls

### Integration
- Invoked by auto_git_workflow.py hook (SubagentStop lifecycle) after quality-validator completes

### Error Handling
- Non-blocking - git operation failures don't affect feature completion (graceful degradation)

### Used By
- auto_git_workflow.py hook
- /auto-implement Step 8 (automatic git operations)

### Related
- GitHub Issue #58 (automatic git operations integration)

---

## 12. github_issue_closer.py (583 lines, v3.22.0+, Issue #91)

**Purpose**: Auto-close GitHub issues after successful `/auto-implement` workflow

### Functions

#### `extract_issue_number(command_args)`
- **Purpose**: Extract GitHub issue number from feature request
- **Parameters**: `command_args` (str): Feature request text
- **Returns**: `int | None` - Issue number (1-999999) or None if not found
- **Features**: Flexible pattern matching
  - Patterns: `"issue #8"`, `"#8"`, `"Issue 8"` (case-insensitive)
  - Extracts first occurrence if multiple mentions
  - Validates issue number is positive integer (1-999999)
- **Security**: CWE-20 (input validation), range checking
- **Examples**:
  ```python
  extract_issue_number("implement issue #8")  # Returns: 8
  extract_issue_number("Add feature for #42")  # Returns: 42
  extract_issue_number("Issue 91 implementation")  # Returns: 91
  ```

#### `prompt_user_consent(issue_number)`
- **Purpose**: Interactive consent prompt before closing issue
- **Parameters**: `issue_number` (int): GitHub issue number
- **Returns**: `bool` - True if user consents, False if declines
- **Features**:
  - Displays issue title (via `gh issue view`)
  - Prompt: `"Close issue #8 (issue title)? [yes/no]:`
  - Accepts: "yes", "y" (True), "no", "n" (False)
  - Ctrl+C propagates KeyboardInterrupt (cancels workflow)
- **Error Handling**: Network errors fall back to generic prompt
- **Non-blocking**: Graceful degradation if gh CLI unavailable

#### `validate_issue_state(issue_number)`
- **Purpose**: Verify issue exists and is open via gh CLI
- **Parameters**: `issue_number` (int): GitHub issue number
- **Raises**: `IssueNotFoundError` if issue doesn't exist or is closed
- **Features**:
  - Calls `gh issue view <number>`
  - Checks issue state (open/closed)
  - Validates user has permission to close
- **Security**: CWE-20 (validates issue number)
- **Idempotent**: Already closed issues skip gracefully

#### `generate_close_summary(issue_number, metadata)`
- **Purpose**: Generate markdown summary for issue close comment
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `metadata` (dict): Workflow metadata
    - `pr_url` (str): Pull request URL
    - `commit_hash` (str): Commit hash
    - `files_changed` (list): Changed file names
    - `agents_passed` (list): Agent names (researcher, planner, etc.)
- **Returns**: `str` - Markdown summary
- **Features**: Professional formatting with workflow metadata
- **Security**: CWE-117 (sanitizes newlines/control chars from file names)

#### `close_github_issue(issue_number, summary)`
- **Purpose**: Close GitHub issue via gh CLI with summary
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `summary` (str): Markdown summary for close comment
- **Returns**: `dict` - Result with success/failure info
- **Security**:
  - CWE-20: Validates issue number (1-999999)
  - CWE-78: Subprocess list args (shell=False)
  - CWE-117: Sanitizes summary text
  - Audit logs all gh CLI operations
- **Error Handling**: Returns error dict (non-blocking)

### Exceptions

#### `GitHubAPIError`
- Base exception for GitHub API errors
- Contains: error message, original exception, traceback

#### `IssueNotFoundError`
- Raised when issue doesn't exist or is closed
- Subclass of GitHubAPIError

#### `IssueAlreadyClosedError`
- Raised when issue is already closed (can be ignored - idempotent)
- Subclass of GitHubAPIError

### Integration

- Invoked by auto_git_workflow.py hook (SubagentStop) after git push
- STEP 8 of /auto-implement workflow: Auto-close GitHub issue
- Non-blocking feature (feature success independent of issue close)

### Security Features

- **CWE-20** (Input Validation): Issue number range checking (1-999999)
- **CWE-78** (Command Injection): Subprocess list args (shell=False)
- **CWE-117** (Log Injection): Sanitizes newlines/control chars
- **Audit Logging**: All gh CLI operations logged to security_audit.log

### Error Handling

All errors gracefully degrade:
- Issue not found: Skip with warning (feature still successful)
- Issue already closed: Skip gracefully (idempotent)
- gh CLI unavailable: Skip with manual instructions (non-blocking)
- Network error: Skip with retry instructions (feature still successful)
- User declines consent: Skip (user control)

### Used By
- auto_git_workflow.py hook
- /auto-implement Step 8 (auto-close GitHub issue)

### Related
- GitHub Issue #91 (Auto-close GitHub issues after /auto-implement)
- github_issue_fetcher.py (Issue fetching via gh CLI)

---

## 21-26. Brownfield Retrofit Libraries (v3.11.0+)

**Purpose**: 5-phase brownfield project retrofit system for existing project adoption

### 21. brownfield_retrofit.py (470 lines) - Phase 0 Analysis

#### Classes
- `BrownfieldProject`: Project descriptor
- `BrownfieldAnalysis`: Analysis result
- `RetrofitPhase`: Phase enum
- `BrownfieldRetrofitter`: Main coordinator

#### Key Functions
- `analyze_brownfield_project(project_root)`: Main entry point for Phase 0 analysis
- `detect_project_root()`: Auto-detect project root from current directory
- `validate_project_structure()`: Verify valid project directory
- `_detect_tech_stack()`: Identify language, framework, package manager
- `_check_existing_structure()`: Check for PROJECT.md, CLAUDE.md, .claude directory
- `build_retrofit_plan()`: Generate high-level retrofit plan

#### Features
- Tech stack auto-detection (Python, JavaScript, Go, Java, Rust, etc.)
- Existing structure analysis (identifies missing or incomplete files)
- Project root validation (verifies directory structure)
- Plan generation with all 5 phases outlined

#### Used By
- align_project_retrofit.py script
- /align-project-retrofit command PHASE 0

### 22. codebase_analyzer.py (870 lines) - Phase 1 Deep Analysis

#### Key Functions
- `analyze_codebase(project_root, tech_stack_hint)`: Comprehensive codebase analysis
- `_scan_directory_structure()`: Recursively analyze directory organization
- `_detect_language_and_framework()`: Language and framework detection
- `_analyze_dependencies()`: Parse requirements.txt, package.json, go.mod, Cargo.toml, etc.
- `_find_test_files()`: Locate and categorize test files
- `_detect_code_organization()`: Analyze module organization and naming conventions
- `_scan_documentation()`: Find README, docs, docstrings coverage
- `_identify_configuration_files()`: Locate config files (.env, .yaml, .json, etc.)

#### Features
- Multi-language support (Python, JavaScript, Go, Java, Rust, C++, etc.)
- Framework detection (Django, FastAPI, Express, Spring, etc.)
- Dependency analysis (dev vs production, versions)
- Test file detection and categorization (unit, integration, e2e)
- Code organization assessment (modular, monolithic, microservices)
- Documentation coverage analysis
- Configuration file inventory

### 23. alignment_assessor.py (666 lines) - Phase 2 Gap Assessment

#### Key Functions
- `assess_alignment(codebase_analysis, project_root)`: Assessment of alignment gaps
- `_calculate_compliance_score()`: Calculate 12-Factor App compliance (0-100 scale)
- `_check_project_structure()`: Verify PROJECT.md, CLAUDE.md presence
- `_check_documentation_quality()`: Assess README, API docs, architecture docs
- `_check_test_coverage()`: Estimate test coverage from test file locations
- `_detect_alignment_gaps()`: Identify missing autonomous-dev standards
- `_prioritize_gaps()`: Sort gaps by criticality and effort
- `_generate_project_md_draft()`: Create initial PROJECT.md structure

#### Features
- 12-Factor App compliance assessment (codebase, dependencies, config, etc.)
- Alignment gap detection (missing files, incomplete structure)
- Gap prioritization (critical, high, medium, low)
- PROJECT.md draft generation (ready to customize)
- Readiness assessment (ready, needs_work, not_ready)
- Estimated retrofit effort (XS, S, M, L, XL)

### 24. migration_planner.py (578 lines) - Phase 3 Plan Generation

#### Key Functions
- `generate_migration_plan(alignment_assessment, project_root, tech_stack)`: Generate migration plan
- `_break_down_gaps_into_steps()`: Convert gaps into actionable steps
- `_estimate_effort()`: Estimate effort for each step (XS-XL scale)
- `_assess_impact()`: Assess impact level (LOW, MEDIUM, HIGH)
- `_detect_step_dependencies()`: Identify prerequisite steps
- `_create_critical_path()`: Order steps by dependencies
- `_generate_verification_criteria()`: Define success criteria for each step
- `_estimate_total_effort()`: Sum effort for complete plan

#### Features
- Gap-to-step conversion with clear instructions
- Multi-factor effort estimation (complexity, scope, skill level)
- Dependency tracking (prerequisites, blocking relationships)
- Critical path analysis (minimum viable retrofit path)
- Verification criteria (how to confirm step success)
- Step grouping by phase (setup, structure, tests, docs, integration)
- Rollback considerations for each step

### 25. retrofit_executor.py (725 lines) - Phase 4 Execution

#### Key Functions
- `execute_migration(migration_plan, mode, project_root)`: Execute migration plan
- `_create_backup()`: Create timestamped backup (0o700 permissions, symlink detection)
- `_execute_step()`: Execute single step (create files, update configs, etc.)
- `_apply_template()`: Apply .claude template to project
- `_create_project_md()`: Create PROJECT.md with customization
- `_create_claude_md()`: Create CLAUDE.md tailored to project
- `_setup_test_framework()`: Configure test framework
- `_setup_git_hooks()`: Install project hooks
- `_rollback_all_changes()`: Restore from backup on failure
- `_validate_step_result()`: Verify step succeeded

#### Features
- Execution mode support: DRY_RUN (show only), STEP_BY_STEP (confirm each), AUTO (all)
- Automatic backup before changes (timestamped, 0o700 permissions)
- Rollback on any failure (atomic: all succeed or all rollback)
- Step-by-step confirmation prompts (customizable)
- Template application (PROJECT.md, CLAUDE.md, .claude directory)
- Test framework setup (auto-detect and configure)
- Hook installation and activation
- Detailed progress reporting

#### Security
- Path validation via security_utils
- Audit logging
- Symlink detection
- 0o700 permissions
- CWE-22/59/732 hardening

### 26. retrofit_verifier.py (689 lines) - Phase 5 Verification

#### Key Functions
- `verify_retrofit_complete(execution_result, project_root, original_analysis)`: Verify retrofit
- `_verify_files_created()`: Verify all required files exist and are valid
- `_verify_file_structure()`: Check .claude directory structure and permissions
- `_verify_configuration()`: Validate PROJECT.md and CLAUDE.md content
- `_verify_test_setup()`: Confirm test framework is operational
- `_verify_hooks_installed()`: Check hook activation status
- `_verify_auto_implement_readiness()`: Verify /auto-implement compatibility
- `_run_smoke_tests()`: Execute basic validation tests
- `_assess_final_readiness()`: Determine readiness for /auto-implement

#### Features
- File existence and integrity verification
- Configuration validation (PROJECT.md structure, CLAUDE.md alignment)
- Test framework operational check
- Hook installation verification
- /auto-implement compatibility check
- Smoke test execution (optional)
- Readiness assessment (ready, needs_minor_fixes, needs_major_fixes)
- Remediation recommendations for failures

### All Brownfield Libraries Share
- Security: Path validation via security_utils, audit logging to security_audit.log
- Integration: Called by /align-project-retrofit command (respective phases)
- Related: GitHub Issue #59 (brownfield project retrofit)



---

## 13. batch_state_manager.py (692 lines, v3.23.0+, enhanced v3.24.0)

**Purpose**: State-based auto-clearing for /batch-implement command with persistent state management

### Data Classes

#### `BatchState`
Batch processing state with persistent storage.

**Attributes**:
- `batch_id` (str): Unique batch identifier (format: "batch-YYYYMMDD-HHMMSS")
- `features_file` (str): Path to features file (empty for --issues batches)
- `total_features` (int): Total number of features in batch
- `features` (List[str]): List of feature descriptions
- `current_index` (int): Index of current feature being processed
- `completed_features` (List[int]): List of completed feature indices
- `failed_features` (List[Dict]): List of failed feature records
- `context_token_estimate` (int): Estimated context token count
- `auto_clear_count` (int): Number of auto-clear events
- `auto_clear_events` (List[Dict]): List of auto-clear event records
- `created_at` (str): ISO 8601 timestamp of batch creation
- `updated_at` (str): ISO 8601 timestamp of last update
- `status` (str): Batch status ("in_progress", "completed", "failed")
- `issue_numbers` (Optional[List[int]]): GitHub issue numbers for --issues flag (v3.24.0)
- `source_type` (str): Source type ("file" or "issues") (v3.24.0)
- `state_file` (str): Path to state file

### Functions

#### `create_batch_state(features, state_file, features_file="", issue_numbers=None, source_type="file")`
- **Purpose**: Create new batch state with atomic write
- **Parameters**:
  - `features` (List[str]): List of feature descriptions
  - `state_file` (Path): Path to state file
  - `features_file` (str): Original features file path (optional)
  - `issue_numbers` (Optional[List[int]]): GitHub issue numbers (v3.24.0)
  - `source_type` (str): "file" or "issues" (v3.24.0)
- **Returns**: BatchState object
- **Security**: CWE-22 (path validation), CWE-732 (file permissions 0o600)

**Example**:
```python
from batch_state_manager import create_batch_state
from path_utils import get_batch_state_file

# File-based batch
state = create_batch_state(
    features=["Add login", "Add logout"],
    state_file=get_batch_state_file(),
    features_file="features.txt"
)

# GitHub issues batch (v3.24.0)
state = create_batch_state(
    features=["Issue #72: Add logging", "Issue #73: Fix bug"],
    state_file=get_batch_state_file(),
    issue_numbers=[72, 73],
    source_type="issues"
)
```

#### `save_batch_state(state)`
- **Purpose**: Save batch state with atomic write
- **Parameters**: `state` (BatchState): State to save
- **Returns**: None
- **Security**: Atomic write (temp file + rename), file permissions 0o600

#### `load_batch_state(state_file)`
- **Purpose**: Load batch state from file
- **Parameters**: `state_file` (Path): Path to state file
- **Returns**: BatchState object
- **Raises**: `BatchStateError` if file not found or corrupted
- **Backward Compatibility**: Old state files load with defaults (issue_numbers=None, source_type="file")

#### `update_batch_progress(state, feature_index, status="completed", error=None)`
- **Purpose**: Update batch progress after feature completion
- **Parameters**:
  - `state` (BatchState): Current state
  - `feature_index` (int): Index of completed feature
  - `status` (str): "completed" or "failed"
  - `error` (Optional[str]): Error message if failed
- **Returns**: Updated BatchState object

#### `record_auto_clear_event(state, tokens_before)`
- **Purpose**: Record auto-clear event in state
- **Parameters**:
  - `state` (BatchState): Current state
  - `tokens_before` (int): Token count before clearing
- **Returns**: Updated BatchState object

#### `should_auto_clear(state, threshold=150000)`
- **Purpose**: Check if context should be auto-cleared
- **Parameters**:
  - `state` (BatchState): Current state
  - `threshold` (int): Token threshold (default: 150,000)
- **Returns**: bool (True if should clear)

#### `get_next_pending_feature(state)`
- **Purpose**: Get next feature to process
- **Parameters**: `state` (BatchState): Current state
- **Returns**: Optional[Tuple[int, str]] (index, feature description) or None if complete

#### `cleanup_batch_state(state_file)`
- **Purpose**: Delete state file after successful batch completion
- **Parameters**: `state_file` (Path): Path to state file
- **Returns**: None

### Security Features

1. **CWE-22 (Path Traversal Prevention)**: All paths validated via security_utils.validate_path()
2. **CWE-59 (Symlink Resolution)**: Symlink detection before file operations
3. **CWE-117 (Log Injection Prevention)**: Sanitize all log messages
4. **CWE-732 (File Permissions)**: State files created with 0o600 permissions
5. **Thread Safety**: Reentrant file locks for concurrent access protection
6. **Atomic Writes**: Temp file + rename pattern prevents corrupted state

### Integration

- **Command**: `/batch-implement` (file-based and --issues flag)
- **State File**: `.claude/batch_state.json` (persistent across crashes)
- **Related**: GitHub Issues #76 (state management), #77 (--issues flag)

### Enhanced Fields (v3.24.0)

```python
@dataclass
class BatchState:
    # ... existing fields ...
    issue_numbers: Optional[List[int]] = None  # NEW: GitHub issue numbers
    source_type: str = "file"  # NEW: "file" or "issues"
```

**Backward Compatibility**: Old state files (v3.23.0) load with default values:
- `issue_numbers = None`
- `source_type = "file"`

---

## 14. github_issue_fetcher.py (462 lines, v3.24.0+)

**Purpose**: Fetch GitHub issue titles via gh CLI for /batch-implement --issues flag

### Functions

#### `validate_issue_numbers(issue_numbers)`
- **Purpose**: Validate issue numbers before subprocess calls
- **Parameters**: `issue_numbers` (List[int]): List of issue numbers to validate
- **Returns**: None (raises on validation failure)
- **Raises**: `ValueError` if validation fails
- **Security**: CWE-20 (Input Validation)
- **Validations**:
  1. All numbers are positive integers
  2. No duplicates
  3. Maximum 100 issues per batch (prevent resource exhaustion)

**Example**:
```python
from github_issue_fetcher import validate_issue_numbers

# Valid
validate_issue_numbers([72, 73, 74])  # OK

# Invalid
validate_issue_numbers([-5])  # ValueError: negative number
validate_issue_numbers([72, 72])  # ValueError: duplicates
validate_issue_numbers(range(150))  # ValueError: too many
```

#### `fetch_issue_title(issue_number, timeout=10)`
- **Purpose**: Fetch single issue title via gh CLI
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `timeout` (int): Subprocess timeout in seconds (default: 10)
- **Returns**: str (issue title)
- **Raises**: 
  - `IssueNotFoundError` if issue doesn't exist
  - `GitHubAPIError` for other gh CLI errors
- **Security**: CWE-78 (Command Injection Prevention)
- **Implementation**: subprocess.run with list args, shell=False

**Example**:
```python
from github_issue_fetcher import fetch_issue_title

title = fetch_issue_title(72)
# Returns: "Add logging feature"
```

#### `fetch_issue_titles(issue_numbers, skip_missing=True)`
- **Purpose**: Batch fetch multiple issue titles
- **Parameters**:
  - `issue_numbers` (List[int]): List of issue numbers
  - `skip_missing` (bool): If True, skip missing issues; if False, raise error (default: True)
- **Returns**: Dict[int, str] (mapping of issue number to title)
- **Raises**: `GitHubAPIError` if skip_missing=False and issue not found
- **Graceful Degradation**: Skips missing issues by default, continues with available issues

**Example**:
```python
from github_issue_fetcher import fetch_issue_titles

titles = fetch_issue_titles([72, 73, 999])
# Returns: {72: "Add logging", 73: "Fix bug"}
# (999 skipped because it doesn't exist)
```

#### `format_feature_description(issue_number, title)`
- **Purpose**: Format issue as feature description for /batch-implement
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `title` (str): Issue title from GitHub
- **Returns**: str (formatted feature description)

**Example**:
```python
from github_issue_fetcher import format_feature_description

feature = format_feature_description(72, "Add logging feature")
# Returns: "Issue #72: Add logging feature"
```

### Security Features

1. **CWE-20 (Input Validation)**:
   - Positive integers only
   - Maximum 100 issues per batch
   - No duplicates

2. **CWE-78 (Command Injection Prevention)**:
   - subprocess.run with list args (not string)
   - shell=False
   - No user input in command string

3. **CWE-117 (Log Injection Prevention)**:
   - Sanitize newlines and control characters in log messages
   - Truncate titles to 200 characters

4. **Audit Logging**:
   - All gh CLI operations logged to security_audit.log
   - Includes: issue numbers, operation type, success/failure

### Integration

- **Command**: `/batch-implement --issues 72 73 74`
- **State Manager**: Enhanced batch_state_manager.py with issue_numbers and source_type fields
- **Requirements**: gh CLI v2.0+, authenticated (gh auth login)
- **Related**: GitHub Issue #77 (Add --issues flag to /batch-implement)

### Usage Workflow

```python
from github_issue_fetcher import (
    validate_issue_numbers,
    fetch_issue_titles,
    format_feature_description,
)
from batch_state_manager import create_batch_state

# 1. Parse issue numbers from command args
issue_numbers = [72, 73, 74]

# 2. Validate
validate_issue_numbers(issue_numbers)

# 3. Fetch titles
issue_titles = fetch_issue_titles(issue_numbers)
# Returns: {72: "Add logging", 73: "Fix bug", 74: "Update docs"}

# 4. Format as features
features = [
    format_feature_description(num, title)
    for num, title in issue_titles.items()
]
# Returns: [
#   "Issue #72: Add logging",
#   "Issue #73: Fix bug",
#   "Issue #74: Update docs"
# ]

# 5. Create batch state
from path_utils import get_batch_state_file

state = create_batch_state(
    features=features,
    state_file=get_batch_state_file(),
    issue_numbers=issue_numbers,
    source_type="issues"
)
```

### Error Handling

```python
from github_issue_fetcher import (
    fetch_issue_titles,
    GitHubAPIError,
    IssueNotFoundError,
)

try:
    titles = fetch_issue_titles([72, 73, 74])
except IssueNotFoundError as e:
    # Issue doesn't exist (only raised if skip_missing=False)
    print(f"Issue not found: {e}")
except GitHubAPIError as e:
    # Other GitHub API errors (gh CLI not found, not authenticated, etc.)
    print(f"GitHub API error: {e}")
```

---

## 15. path_utils.py (320 lines, v3.28.0+ / v3.41.0+)

**Purpose**: Dynamic PROJECT_ROOT detection, path resolution, and policy file location for tracking infrastructure and tool configuration

**Issue**: GitHub #79 - Fixes hardcoded paths that failed when running from subdirectories

### Key Features

- **Dynamic PROJECT_ROOT Detection**: Searches upward from current directory for `.git/` or `.claude/` markers
- **Caching**: Module-level cache prevents repeated filesystem searches
- **Flexible Creation**: Creates directories (docs/sessions, .claude) as needed with safe permissions (0o755)
- **Backward Compatible**: Existing usage patterns still work, uses get_project_root() internally
- **Security Validation**: Rejects symlinks and invalid JSON in policy files (CWE-59)

### Public API

#### `find_project_root(marker_files=None, start_path=None)`
- **Purpose**: Search upward for project root directory
- **Parameters**:
  - `marker_files` (list): Files/directories to search for. Defaults to `[".git", ".claude"]` (priority order)
  - `start_path` (Path): Starting directory for search. Defaults to current working directory
- **Returns**: `Path` - Project root directory
- **Raises**: `FileNotFoundError` - If no marker found up to filesystem root
- **Priority Strategy**: Searches all the way up for `.git` before considering `.claude` (ensures nested `.claude` dirs work correctly)

#### `get_project_root(use_cache=True)`
- **Purpose**: Get cached project root (detects and caches if first call)
- **Parameters**: `use_cache` (bool): Use cached value or force re-detection (default: True)
- **Returns**: `Path` - Project root directory
- **Thread Safety**: Not thread-safe (uses module-level cache); wrap with threading.Lock for multi-threading
- **Best For**: Performance-critical code that calls repeatedly

#### `get_session_dir(create=True, use_cache=True)`
- **Purpose**: Get session directory path (`PROJECT_ROOT/docs/sessions`)
- **Parameters**:
  - `create` (bool): Create directory if missing (default: True)
  - `use_cache` (bool): Use cached project root (default: True)
- **Returns**: `Path` - Session directory
- **Creates**: Parent directories with safe permissions (0o755 = rwxr-xr-x)
- **Used By**: session_tracker.py, agent_tracker.py

#### `get_batch_state_file()`
- **Purpose**: Get batch state file path (`PROJECT_ROOT/.claude/batch_state.json`)
- **Returns**: `Path` - Batch state file path (note: file itself not created)
- **Creates**: Parent directory (`.claude/`) if missing, with safe permissions
- **Used By**: batch_state_manager.py

#### `get_policy_file(use_cache=True)` (NEW in v3.41.0)
- **Purpose**: Get policy file path via cascading lookup with fallback
- **Parameters**: `use_cache` (bool): Use cached value or force re-detection (default: True). Set to False in tests that change working directory.
- **Returns**: `Path` - Policy file (validated and readable)
- **Cascading Lookup Order**:
  1. `.claude/config/auto_approve_policy.json` (project-local) - enables per-project customization
  2. `plugins/autonomous-dev/config/auto_approve_policy.json` (plugin default) - stable fallback
  3. Minimal fallback path (may not exist) - graceful degradation
- **Security Validations**:
  - Rejects symlinks (CWE-59)
  - Prevents path traversal (CWE-22)
  - Validates JSON format
  - Handles permission errors gracefully
- **Thread Safety**: Not thread-safe (uses module-level cache); wrap with threading.Lock for multi-threading
- **Used By**: tool_validator.py, auto_approval_engine.py
- **Use Cases**:
  - Customize policy per project (place policy in `.claude/config/auto_approve_policy.json`)
  - Inherit plugin defaults (omit custom policy)
  - Test with different policies (call with `use_cache=False`)

#### `reset_project_root_cache()`
- **Purpose**: Reset cached project root (testing only)
- **Warning**: Only use in test teardown; production code should maintain cache for process lifetime

### Test Coverage

- **Total**: 45+ tests in `tests/unit/test_tracking_path_resolution.py` + 15 tests in `tests/unit/lib/test_policy_path_resolution.py`
- **Areas**:
  - PROJECT_ROOT detection from various directories
  - Marker file priority (`.git` over `.claude`)
  - Nested `.claude/` handling in git repositories
  - Directory creation with safe permissions
  - Cache behavior and reset
  - Policy file cascading lookup (NEW v3.41.0)
  - Policy file security validation (NEW v3.41.0)
  - Symlink detection in policy files (NEW v3.41.0)

### Usage Examples

```python
from plugins.autonomous_dev.lib.path_utils import (
    get_project_root,
    get_session_dir,
    get_batch_state_file,
    get_policy_file
)

# Get project root (cached after first call)
root = get_project_root()
print(root)  # /path/to/autonomous-dev

# Get session directory (creates if missing)
session_dir = get_session_dir()
session_file = session_dir / "20251117-session.md"

# Get batch state file path
state_file = get_batch_state_file()
# Returns: /project/.claude/batch_state.json

# Get policy file with cascading lookup
policy_file = get_policy_file()
# 1. Tries: .claude/config/auto_approve_policy.json (project-local)
# 2. Falls back to: plugins/autonomous-dev/config/auto_approve_policy.json (plugin default)
# 3. Returns minimal fallback if both missing

# Force re-detection (for tests that change cwd)
from tests.conftest import isolated_project
root = get_project_root(use_cache=False)
policy_file = get_policy_file(use_cache=False)
```

### Security

- **No Path Traversal**: Only searches upward, never downward
- **Safe Permissions**: Creates directories with 0o755 (rwxr-xr-x)
- **Validation**: Validates marker files exist before returning
- **Symlink Handling**: Resolves symlinks to canonical paths
- **Policy File Security** (v3.41.0):
  - Rejects symlinks in policy file locations (CWE-59)
  - Validates JSON format before use (prevents malformed policy)
  - Handles permission denied errors gracefully
  - Prefers project-local customization for per-project policies

### Migration from Hardcoded Paths

**Before** (Issue #79 - fails from subdirectories):
```python
# Hardcoded path in session_tracker.py line 25
session_dir = Path("docs/sessions")  # Fails if cwd != project root
```

**After** (v3.28.0+):
```python
from path_utils import get_session_dir
session_dir = get_session_dir()  # Works from any subdirectory
```

### Policy File Customization (NEW in v3.41.0)

Per-project policy customization enables different auto-approval policies for different projects:

**Project-Local Policy** (takes priority):
```bash
# Create custom policy in your project
mkdir -p .claude/config/
cp plugins/autonomous-dev/config/auto_approve_policy.json .claude/config/auto_approve_policy.json
# Edit .claude/config/auto_approve_policy.json for project-specific rules
```

**Automatic Fallback**:
```python
# Code automatically uses:
# 1. .claude/config/auto_approve_policy.json (if it exists and is valid)
# 2. plugins/autonomous-dev/config/auto_approve_policy.json (plugin default)
policy_file = get_policy_file()  # No configuration needed!
```

### Related Documentation

- See `library-design-patterns` skill for design principles
- See Issue #79 for hardcoded path fixes and security implications
- See Issue #100 for policy file portability and cascading lookup design
- See `docs/TOOL-AUTO-APPROVAL.md` section "Policy File Location" for user guide

---

## 16. validation.py (286 lines, v3.28.0+)

**Purpose**: Tracking infrastructure security validation (input sanitization and path traversal prevention)

**Issue**: GitHub #79 - Fixes security gaps in tracking modules (path traversal, control character injection)

### Key Features

- **Path Traversal Prevention**: Rejects paths with `..` sequences, validates within allowed directories
- **Symlink Attack Prevention**: Rejects symlinks that could bypass path restrictions
- **Input Validation**: Agent names, messages with length limits and character validation
- **Control Character Filtering**: Prevents log injection attacks
- **Clear Error Messages**: Helpful guidance for developers using these APIs

### Public API

#### `validate_session_path(path, purpose="session tracking")`
- **Purpose**: Validate session path to prevent path traversal attacks
- **Parameters**:
  - `path` (str|Path): Path to validate
  - `purpose` (str): Description for error messages
- **Returns**: `Path` - Validated and resolved path
- **Raises**: `ValueError` - If path contains traversal sequences, is outside allowed dirs, or is symlink
- **Allowed Directories**:
  - `PROJECT_ROOT/docs/sessions/` (session files)
  - `PROJECT_ROOT/.claude/` (state files)
- **Security Coverage**: CWE-22 (path traversal), CWE-59 (symlink resolution)

#### `validate_agent_name(name, purpose="agent tracking")`
- **Purpose**: Validate agent name (alphanumeric, hyphen, underscore only)
- **Parameters**:
  - `name` (str): Agent name to validate
  - `purpose` (str): Description for error messages
- **Returns**: `str` - Validated agent name (whitespace stripped)
- **Raises**: `ValueError` - If name is empty, too long (>255 chars), or contains invalid characters
- **Allowed Characters**: Letters (a-z, A-Z), numbers (0-9), hyphen (-), underscore (_)
- **Security Coverage**: Input injection prevention

#### `validate_message(message, purpose="message logging")`
- **Purpose**: Validate message (length limits, no control characters)
- **Parameters**:
  - `message` (str): Message to validate
  - `purpose` (str): Description for error messages
- **Returns**: `str` - Validated message (stripped of leading/trailing whitespace)
- **Raises**: `ValueError` - If message exceeds 10KB or contains control characters
- **Allowed Characters**: Printable ASCII, tabs, newlines, carriage returns
- **Blocked Characters**: Control characters (ASCII 0-31 except tab/newline/CR)
- **Security Coverage**: Log injection prevention, DoS prevention (input limits)

### Constants

- `MAX_MESSAGE_LENGTH = 10000` - Maximum message length (10KB)
- `MAX_AGENT_NAME_LENGTH = 255` - Maximum agent name length

### Test Coverage

- **Total**: 35+ tests in `tests/unit/test_tracking_security.py`
- **Areas**:
  - Path traversal attack detection (various `.` and `..` patterns)
  - Symlink attack detection
  - Path outside allowed directories
  - Agent name validation (empty, too long, invalid characters)
  - Message validation (too long, control characters)
  - Helpful error messages

### Usage Examples

```python
from plugins.autonomous_dev.lib.validation import (
    validate_session_path,
    validate_agent_name,
    validate_message
)

# Validate session path
try:
    safe_path = validate_session_path("/project/docs/sessions/file.json")
except ValueError as e:
    print(f"Invalid path: {e}")

# Validate agent name
try:
    name = validate_agent_name("researcher-v2")
    print(f"Valid name: {name}")
except ValueError as e:
    print(f"Invalid name: {e}")

# Validate message
try:
    msg = validate_message("Research complete - 5 patterns found")
    print(f"Valid message: {msg}")
except ValueError as e:
    print(f"Invalid message: {e}")

# Security: These raise ValueError
validate_session_path("../../etc/passwd")  # Path traversal
validate_session_path("/etc/passwd")  # Outside allowed dirs
validate_agent_name("../../etc/passwd")  # Invalid chars
validate_agent_name("")  # Empty
validate_message("x" * 20000)  # Too long
validate_message("msg\x00with\x01control")  # Control chars
```

### Security Principles

- **Whitelist Validation**: Only allow specific characters and paths
- **Fail Closed**: Reject unknown inputs (not permissive)
- **Clear Errors**: Error messages guide developers to correct usage
- **Defense in Depth**: Multiple validation layers prevent bypasses
- **No Eval/Exec**: Pure validation, no code execution

### Used By

- `session_tracker.py` - Session file path and agent name validation
- `batch_state_manager.py` - Batch state file path validation
- `agent_tracker.py` - Agent name validation for session tracking

### Related Documentation

- See `security-patterns` skill for validation principles
- See `library-design-patterns` skill for input validation design
- See Issue #79 for security implications and threat model

---

## 17. file_discovery.py (354 lines, v3.29.0+)

**Purpose**: Comprehensive file discovery with intelligent exclusion patterns for 100% coverage

### Classes

#### `DiscoveryResult`
- **Purpose**: Result dataclass for file discovery operation
- **Attributes**:
  - `files` (List[Path]): List of discovered files (absolute paths)
  - `count` (int): Total number of files discovered
  - `excluded_count` (int): Number of files excluded
  - `directories` (List[Path]): List of discovered directories

### Key Methods

#### `FileDiscovery.discover_all_files()`
- **Purpose**: Recursively discover all files in plugin directory
- **Returns**: `DiscoveryResult`
- **Features**:
  - Recursive directory traversal (finds all 201+ files)
  - Intelligent exclusion patterns (cache, build artifacts, hidden files)
  - Nested skill structure support (skills/[name].skill/docs/...)
  - Performance optimized (patterns compiled, single pass)

#### `FileDiscovery.discover_by_type(file_type)`
- **Purpose**: Discover files matching specific type
- **Parameters**: `file_type` (str): File type (e.g., "py", "md", "json")
- **Returns**: `DiscoveryResult`

#### `FileDiscovery.generate_manifest()`
- **Purpose**: Generate installation manifest from discovered files
- **Returns**: `dict` (manifest structure)
- **Features**: Categorizes files (agents, commands, hooks, skills, lib, scripts, config, templates)

#### `FileDiscovery.validate_against_manifest(manifest)`
- **Purpose**: Compare discovered files vs manifest
- **Returns**: `dict` with missing/extra files
- **Features**: Detects file coverage gaps

### Exclusion Patterns

**Built-in patterns** (configurable, with two-tier matching strategy):

**Exact Patterns** (EXCLUDE_PATTERNS set):
- Cache: `__pycache__`, `.pytest_cache`, `.eggs`, `*.egg-info`, `*.egg`
- Build artifacts: `*.pyc`, `*.pyo`, `*.pyd`, `build`, `dist`
- Version control: `.git`, `.gitignore`, `.gitattributes`
- IDE: `.vscode`, `.idea`
- Temp/backup: `*.tmp`, `*.bak`, `*.log`, `*~`, `*.swp`, `*.swo`
- System: `.DS_Store`

**Partial Patterns** (EXCLUDE_DIR_PATTERNS list - enhanced in v3.29.0+):
- Directory name pattern matching: `.egg-info`, `__pycache__`, `.pytest_cache`, `.git`, `.eggs`, `build`, `dist`
- Detects patterns within directory names (e.g., `foo-1.0.0.egg-info` matches `.egg-info` pattern)
- Prevents false negatives from naming variations

### Security
- Path validation via security_utils
- Symlink detection and handling
- Safe recursive traversal (prevents infinite loops)

### Test Coverage
- 60+ unit tests (discovery, exclusions, nested structures, edge cases)
- Integration tests with actual plugin directory

### Used By
- install_orchestrator.py for installation planning
- copy_system.py for determining what to copy

### Related
- GitHub Issue #80 (Bootstrap overhaul - 100% file coverage)

---

## 18. copy_system.py (274 lines, v3.29.0+)

**Purpose**: Structure-preserving file copying with permission handling

### Classes

#### `CopyError`
- **Purpose**: Exception raised during copy operations

#### `CopyResult`
- **Purpose**: Result dataclass for copy operation
- **Attributes**:
  - `success` (bool): Whether copy succeeded
  - `copied_count` (int): Number of files successfully copied
  - `failed_count` (int): Number of files that failed
  - `message` (str): Human-readable result
  - `failed_files` (List[dict]): Details of failed copies

### Key Methods

#### `CopySystem.copy_all()`
- **Purpose**: Copy all discovered files with structure preservation
- **Returns**: `CopyResult`
- **Features**:
  - Directory structure preservation (lib/foo.py → .claude/lib/foo.py)
  - Executable permissions for scripts (scripts/*.py get +x)
  - Timestamp preservation
  - Progress reporting with callbacks
  - Error handling with optional continuation

#### `CopySystem.copy_file(source, destination)`
- **Purpose**: Copy single file with validation
- **Parameters**:
  - `source` (Path): Source file
  - `destination` (Path): Destination file
- **Returns**: `bool`
- **Features**: Creates parent directories, validates permissions

#### `CopySystem.set_executable_permission(file_path)`
- **Purpose**: Set executable bit for scripts
- **Parameters**: `file_path` (Path): File to make executable
- **Security**: Only applies to allowed patterns (scripts/*.py, hooks/*.py)

#### `CopySystem.rollback(backup_dir, dest_dir)` - ENHANCED in v3.29.0+
- **Purpose**: Restore installation from backup on failure (with early validation)
- **Parameters**:
  - `backup_dir` (Path): Path to backup directory
  - `dest_dir` (Path): Destination directory to restore to
- **Returns**: `bool` (True if rollback succeeded, False otherwise)
- **Features**:
  - Early validation: Checks backup exists before removing destination
  - Safe removal: Only removes destination if backup is available
  - Atomic restore: Copies entire backup directory structure
  - Security: Path validation, symlink protection
- **Enhancement (v3.29.0+)**: Added early backup existence check before removing destination
  - Prevents accidental deletion if backup is missing
  - More robust error handling and recovery

### Progress Callback

#### `CopySystem.copy_all(progress_callback=callback)`
- **Signature**: `callback(current: int, total: int, file_path: Path)`
- **Purpose**: Real-time progress reporting during copy
- **Example**: Display progress bar, log operations

### Security
- Path validation via security_utils
- Destination path must be within allowed directories
- Permission preservation (respects umask)
- Rollback support (can recover from partial copies)

### Error Handling
- Per-file error handling (one failure doesn't block others)
- Optional strict mode (fail on first error)
- Detailed error information (source, destination, reason)

### Test Coverage
- 45+ unit tests (file copying, permissions, nested dirs, rollback, error cases)
- Integration tests with real filesystem

### Used By
- install_orchestrator.py for file installation

### Related
- GitHub Issue #80 (Bootstrap overhaul - structure-preserving copy)

---

## 19. installation_validator.py (632 lines, v3.29.0+ → v3.29.1)

**Purpose**: Ensures complete file coverage and detects installation issues + duplicate library validation

**Enhanced in v3.29.1 (Issue #81)**: Added duplicate library detection and cleanup recommendations

### Classes

#### `ValidationError`
- **Purpose**: Exception raised when validation encounters critical error

#### `ValidationResult`
- **Purpose**: Result dataclass for validation operation
- **Attributes**:
  - `status` (str): "complete" if 100% coverage, "incomplete" otherwise
  - `coverage` (float): File coverage percentage (0-100)
  - `total_expected` (int): Total files expected from source
  - `total_found` (int): Total files found in destination
  - `missing_files` (int): Count of missing files
  - `extra_files` (int): Count of extra files
  - `missing_file_list` (List[str]): Paths of missing files
  - `extra_file_list` (List[str]): Paths of extra files
  - `structure_valid` (bool): Whether directory structure is valid
  - `errors` (List[str]): List of error messages
  - `sizes_match` (bool|None): Whether file sizes match manifest (if applicable)
  - `size_errors` (List[str]|None): Files with size mismatches (if applicable)
  - `missing_by_category` (Dict[str, int]|None): Missing files categorized by directory (NEW in v3.29.0+)
  - `critical_missing` (List[str]|None): List of critical missing files (NEW in v3.29.0+)

### Key Methods

#### `InstallationValidator.validate(threshold=100.0)`
- **Purpose**: Validate complete installation
- **Parameters**:
  - `threshold` (float, optional): Coverage threshold percentage (default: 100.0, can be 99.5 for flexible validation)
- **Returns**: `ValidationResult`
- **Features**:
  - File coverage calculation (actual/expected * 100)
  - Missing file detection (source files not in destination)
  - Extra file detection (unexpected files in destination)
  - Directory structure validation
  - File categorization by directory (NEW in v3.29.0+)
  - Critical file identification (NEW in v3.29.0+)
  - File size validation (NEW in v3.29.0+)
  - Threshold-based status determination (flexible pass/fail criteria)
  - Detailed reporting

#### `InstallationValidator.validate_sizes()` - NEW in v3.29.1
- **Purpose**: Validate file sizes against manifest
- **Parameters**: None (uses internal manifest)
- **Returns**: `Dict` with `sizes_match` (bool) and `size_errors` (List[str])
- **Raises**: `ValidationError` if no manifest provided
- **Features**: Detects corrupted downloads or partial installs

#### `InstallationValidator.categorize_missing_files(missing_file_list)` - NEW in v3.29.0+

**Signature**: `categorize_missing_files(missing_file_list: List[str]) -> Dict[str, int]`

- **Purpose**: Categorize missing files by directory for detailed reporting
- **Parameters**: `missing_file_list` (List[str]): List of missing file paths
- **Returns**: `Dict[str, int]` mapping directory to count
  - Example: `{"scripts": 2, "lib": 5, "agents": 1}`
- **Features**:
  - Groups missing files by first directory component
  - Provides summary for quick problem diagnosis
  - Used in `validate()` method to populate `missing_by_category`

#### `InstallationValidator.identify_critical_files(missing_file_list)` - NEW in v3.29.0+

**Signature**: `identify_critical_files(missing_file_list: List[str]) -> List[str]`

- **Purpose**: Identify critical missing files that must be installed
- **Parameters**: `missing_file_list` (List[str]): List of missing file paths
- **Returns**: `List[str]` of critical missing files
- **Critical Patterns**:
  - `scripts/setup.py`
  - `lib/security_utils.py`
  - `lib/install_orchestrator.py`
  - `lib/file_discovery.py`
  - `lib/copy_system.py`
  - `lib/installation_validator.py`
- **Features**:
  - Identifies essential files for plugin operation
  - Used in `validate()` method to populate `critical_missing`
  - Helps prioritize missing file recovery

#### `InstallationValidator.validate_no_duplicate_libs()` - NEW in v3.29.1

**Signature**: `validate_no_duplicate_libs() -> List[str]`

- **Purpose**: Validate that no duplicate libraries exist in `.claude/lib/`
- **Details**:
  - Checks for Python files in `.claude/lib/` that conflict with canonical location
  - Uses `OrphanFileCleaner.find_duplicate_libs()` for detection
  - Returns warning messages with cleanup instructions if duplicates found
- **Returns**: `List[str]` of warning messages
  - Empty list if no duplicates found
  - Warnings include file count and cleanup instructions if duplicates detected
- **Behavior**:
  - Returns empty list if `.claude/lib/` doesn't exist
  - Returns empty list if `.claude/lib/` is empty
  - Provides clear remediation steps in warning messages
  - Audit logs detection results
- **Example**:
  ```python
  validator = InstallationValidator(source_dir, dest_dir)
  warnings = validator.validate_no_duplicate_libs()
  if warnings:
      for warning in warnings:
          print(f"WARNING: {warning}")
  ```

#### `InstallationValidator.from_manifest(manifest_path, dest_dir)` (classmethod)
- **Purpose**: Validate using installation manifest
- **Parameters**:
  - `manifest_path` (Path): Path to installation_manifest.json
  - `dest_dir` (Path): Installation destination directory
- **Returns**: `InstallationValidator` instance

#### `InstallationValidator.from_manifest_dict(manifest, dest_dir)` (classmethod)
- **Purpose**: Create validator from manifest dictionary
- **Parameters**:
  - `manifest` (Dict): Manifest dictionary
  - `dest_dir` (Path): Installation destination directory
- **Returns**: `InstallationValidator` instance
- **New in v3.29.1**: For testing and programmatic use

#### `InstallationValidator.generate_report(result)`
- **Purpose**: Generate human-readable validation report
- **Parameters**: `result` (ValidationResult): Validation result to format
- **Returns**: `str` (formatted report with symbols and sections)
- **Features**:
  - Coverage percentage with status symbols
  - Missing and extra files listing (first 10 shown)
  - Directory structure validation status
  - File size validation status (if applicable)
  - Detailed error messages

#### `InstallationValidator.calculate_coverage(expected, actual)`
- **Purpose**: Calculate coverage percentage
- **Parameters**:
  - `expected` (int): Number of expected files
  - `actual` (int): Number of actual files
- **Returns**: `float` Coverage percentage (0-100, rounded to 2 decimal places)

#### `InstallationValidator.find_missing_files(expected_files, actual_files)`
- **Purpose**: Find files that are expected but not present
- **Parameters**:
  - `expected_files` (List[Path]): Expected file paths
  - `actual_files` (List[Path]): Actual file paths
- **Returns**: `List[str]` of missing file paths (sorted)

### Coverage Requirements

**100% Coverage Baseline**:
- All 201+ files in plugin directory expected
- Current baseline: 76% coverage (152/201 files)
- Goal: 95%+ coverage (190+ files)

### Validation Levels

1. **Critical**: Directory structure issues (lib/ missing, etc.) OR duplicate libraries found
2. **High**: Key files missing (agents/*.md, commands/*.md)
3. **Medium**: Optional enhancements missing (some lib files)
4. **Low**: Metadata files missing (*.log, session files)

### Security
- Path validation via security_utils.validate_path()
  - Prevents path traversal attacks (CWE-22)
  - Blocks symlink-based attacks (CWE-59)
- File size limits on reading
- Safe manifest parsing (JSON schema validation)
- Duplicate library detection prevents import conflicts (CWE-627)

### Test Coverage
- 60+ unit tests (v3.29.1 additions):
  - Basic validation: 10 tests
  - Duplicate detection: 6 tests (empty, missing, warnings, counts)
  - Cleanup instructions: 3 tests
  - Edge cases: 5+ tests
- Original 40+ tests for coverage/manifest validation maintained
- Total coverage: 60+ tests

### Used By
- install_orchestrator.py for post-installation verification
- plugin_updater.py for pre-update duplicate validation
- /health-check command for installation integrity validation
- orphan_file_cleaner.py for duplicate library warnings

### Related
- GitHub Issue #80 (Bootstrap overhaul - coverage validation)
- GitHub Issue #81 (Prevent .claude/lib/ Duplicate Library Imports) - NEW

---

## 20. install_orchestrator.py (602 lines, v3.29.0+)

**Purpose**: Coordinates complete installation workflow (fresh install, upgrade, rollback)

### Classes

#### `InstallationType` (enum)
- `FRESH`: New installation
- `UPGRADE`: Update existing installation
- `REPAIR`: Fix broken installation

#### `InstallationResult`
- **Purpose**: Result dataclass for installation operation
- **Attributes**:
  - `success` (bool): Whether installation succeeded
  - `installation_type` (InstallationType): Type of installation performed
  - `message` (str): Human-readable result
  - `files_installed` (int): Number of files installed
  - `coverage_percent` (float): File coverage percentage
  - `backup_path` (Path|None): Path to backup (if created during upgrade)
  - `rollback_performed` (bool): Whether rollback was executed
  - `validation_result` (ValidationResult): Post-installation validation

### Key Methods

#### `InstallOrchestrator.fresh_install()`
- **Purpose**: Perform fresh installation
- **Returns**: `InstallationResult`
- **Features**:
  - Discovers all files
  - Creates installation marker
  - Validates coverage (expects 95%+)
  - No backup needed (new installation)

#### `InstallOrchestrator.upgrade_install()`
- **Purpose**: Upgrade existing installation
- **Returns**: `InstallationResult`
- **Features**:
  - Automatic backup before upgrade
  - Preserves user settings and customizations
  - Validates coverage after upgrade
  - Rollback on validation failure

#### `InstallOrchestrator.repair_install()`
- **Purpose**: Repair broken installation
- **Returns**: `InstallationResult`
- **Features**:
  - Detects missing files
  - Recopies missing files
  - Preserves existing correct files
  - Full validation after repair

#### `InstallOrchestrator.auto_detect(project_dir)` (classmethod)
- **Purpose**: Auto-detect installation type and execute
- **Parameters**: `project_dir` (Path): Project directory
- **Returns**: `InstallationResult`
- **Logic**:
  - No .claude/: FRESH installation
  - Has .claude/ + recent marker: UPGRADE
  - Has .claude/ + old/missing files: REPAIR

#### `InstallOrchestrator.rollback(backup_dir)`
- **Purpose**: Restore from backup on failure
- **Parameters**: `backup_dir` (Path): Path to backup directory
- **Security**: Path validation, symlink blocking

### Manifest System

**Installation Manifest** (`config/installation_manifest.json`):
- Lists all required directories
- Defines exclusion patterns
- Specifies executable patterns
- Marks files to preserve on upgrade

### Installation Marker

**Purpose**: Track installation state and coverage

**Location**: `.claude/.install_marker.json`

**Content**:
```json
{
  "version": "3.29.0",
  "installed_at": "2025-11-17T10:30:00Z",
  "installation_type": "fresh",
  "coverage_percent": 98.5,
  "files_installed": 201,
  "marker_version": 1
}
```

### Workflow Integration

**Fresh Install**:
1. Pre-install cleanup (remove duplicate .claude/lib/ libraries)
2. Discover all files
3. Copy with structure preservation
4. Validate coverage (expect 95%+)
5. Create installation marker
6. Activate hooks (optional)

**Upgrade Install**:
1. Pre-install cleanup (remove duplicate .claude/lib/ libraries)
2. Create timestamped backup
3. Discover files
4. Copy files (preserving user customizations if possible)
5. Set permissions
6. Update marker file
7. Validate
8. On failure: rollback

**Repair Install**:
1. Detect missing files (compare against manifest)
2. Copy missing files only
3. Validate coverage
4. Update installation marker

### Security
- All paths validated via security_utils
- Backup directory permissions 0o700 (user-only)
- Atomic marker file writes (tempfile + rename)
- Audit logging to security audit

### Test Coverage
- 60+ unit tests (fresh install, upgrade, repair, rollback scenarios)
- Integration tests with complete workflows

### Used By
- `install.sh` bootstrap script
- `/setup` command
- `/health-check` command (validation)

### Related
- GitHub Issue #80 (Bootstrap overhaul - orchestrated installation)

---

## 21. failure_classifier.py (343 lines, v3.33.0+)

**Purpose**: Classify /auto-implement failures as transient vs permanent for intelligent retry logic.

### Overview

Analyzes error messages to determine if a failed feature attempt should be retried (transient errors like network issues) or marked failed (permanent errors like syntax errors). Used by batch_retry_manager.py to make retry decisions.

### Enums

#### `FailureType`
- `TRANSIENT` - Retriable error (network, timeout, rate limit)
- `PERMANENT` - Non-retriable error (syntax, import, type errors)

### Functions

#### `classify_failure(error_message)`
- **Purpose**: Classify error message as transient or permanent
- **Parameters**: `error_message` (str|None): Raw error message
- **Returns**: `FailureType.TRANSIENT` or `FailureType.PERMANENT`
- **Logic**:
  1. Check transient patterns (network, timeout, rate limit)
  2. Check permanent patterns (syntax, import, type errors)
  3. Default to PERMANENT for safety (unknown errors not retried)
- **Examples**:
  ```python
  classify_failure("ConnectionError: Failed to connect")  # TRANSIENT
  classify_failure("SyntaxError: invalid syntax")  # PERMANENT
  classify_failure("WeirdUnknownError")  # PERMANENT (safe default)
  ```

#### `is_transient_error(error_message)`
- **Purpose**: Check if error indicates transient failure
- **Parameters**: `error_message` (str|None): Error message
- **Returns**: `True` if transient, `False` otherwise
- **Patterns Detected**:
  - ConnectionError, NetworkError
  - TimeoutError
  - RateLimitError, HTTP 429/503
  - HTTP 502/504 (Bad Gateway, Gateway Timeout)
  - TemporaryFailure, Service Unavailable

#### `is_permanent_error(error_message)`
- **Purpose**: Check if error indicates permanent failure
- **Parameters**: `error_message` (str|None): Error message
- **Returns**: `True` if permanent, `False` otherwise
- **Patterns Detected**:
  - SyntaxError, IndentationError
  - ImportError, ModuleNotFoundError
  - TypeError, AttributeError, NameError
  - ValueError, KeyError, IndexError
  - AssertionError, ZeroDivisionError

#### `sanitize_error_message(error_message)`
- **Purpose**: Sanitize error message for safe logging (CWE-117 prevention)
- **Parameters**: `error_message` (str|None): Raw error message
- **Returns**: `str` (sanitized message)
- **Security**:
  - Removes newlines (prevent log injection)
  - Removes carriage returns (prevent log injection)
  - Truncates to 1000 chars (prevent resource exhaustion)
- **Examples**:
  ```python
  sanitize_error_message("Error\nFAKE LOG: Admin")  # "Error FAKE LOG: Admin"
  sanitize_error_message("E" * 10000)  # "EEEE...[truncated]"
  ```

#### `extract_error_context(error_message, feature_name)`
- **Purpose**: Extract rich error context for debugging
- **Parameters**:
  - `error_message` (str|None): Raw error message
  - `feature_name` (str): Name of feature being processed
- **Returns**: `Dict` with error context
- **Context Fields**:
  - `error_type` (str): Type extracted from message
  - `error_message` (str): Sanitized message
  - `feature_name` (str): Original feature name
  - `timestamp` (str): ISO 8601 timestamp
  - `failure_type` (str): "transient" or "permanent"
- **Examples**:
  ```python
  context = extract_error_context("SyntaxError: invalid", "Add auth")
  # {
  #   "error_type": "SyntaxError",
  #   "error_message": "SyntaxError: invalid",
  #   "feature_name": "Add auth",
  #   "timestamp": "2025-11-19T10:00:00Z",
  #   "failure_type": "permanent"
  # }
  ```

### Security
- **CWE-117**: Log injection prevention via newline/carriage return removal
- **Resource Exhaustion**: Max 1000-char error messages prevent DOS
- **Safe Defaults**: Unknown errors → permanent (don't retry)

### Constants

- `TRANSIENT_ERROR_PATTERNS`: List of 15+ regex patterns for transient errors
- `PERMANENT_ERROR_PATTERNS`: List of 15+ regex patterns for permanent errors
- `MAX_ERROR_MESSAGE_LENGTH`: 1000 chars (truncate longer messages)

### Test Coverage
- 25+ unit tests covering classification, sanitization, context extraction
- Edge cases: None, empty, unknown error types, long messages

### Used By
- batch_retry_manager.py for retry decisions
- /batch-implement command for retry logic

### Related
- GitHub Issue #89 (Automatic Failure Recovery for /batch-implement)
- error-handling-patterns skill for exception hierarchy

---

## 22. batch_retry_manager.py (544 lines, v3.33.0+)

**Purpose**: Orchestrate retry logic with safety limits and circuit breaker for /batch-implement.

### Overview

Manages automatic retry of failed features with intelligent safeguards:
- Per-feature retry tracking (max 3 per feature)
- Circuit breaker (pause after 5 consecutive failures)
- Global retry limit (max 50 total retries)
- Persistent state (survive crashes)
- Audit logging (all retries tracked)

### Data Classes

#### `RetryDecision`
- **Purpose**: Decision about whether to retry a feature
- **Attributes**:
  - `should_retry` (bool): Whether to retry
  - `reason` (str): Reason for decision (e.g., "under_retry_limit", "circuit_breaker_open")
  - `retry_count` (int): Current retry count for feature

#### `RetryState`
- **Purpose**: Persistent retry state for a batch
- **Attributes**:
  - `batch_id` (str): Batch identifier
  - `retry_counts` (Dict[int, int]): Per-feature retry counts
  - `global_retry_count` (int): Total retries across all features
  - `consecutive_failures` (int): Consecutive failures (for circuit breaker)
  - `circuit_breaker_open` (bool): Whether circuit breaker is triggered
  - `created_at` (str): ISO 8601 creation timestamp
  - `updated_at` (str): ISO 8601 last update timestamp

### Main Class

#### `BatchRetryManager`
- **Purpose**: Main class for retry orchestration

##### Constructor
```python
BatchRetryManager(batch_id: str, state_dir: Optional[Path] = None)
```

##### Key Methods

###### `should_retry_feature(feature_index, failure_type)`
- **Purpose**: Decide if feature should be retried
- **Parameters**:
  - `feature_index` (int): Index of failed feature
  - `failure_type` (FailureType): Classification of failure
- **Returns**: `RetryDecision` with decision and reason
- **Decision Logic** (in order):
  1. Check global retry limit (max 50 total retries)
  2. Check circuit breaker (5 consecutive failures)
  3. Check failure type (permanent → no retry)
  4. Check per-feature limit (max 3 retries)
  5. If all pass → allow retry
- **Examples**:
  ```python
  manager = BatchRetryManager("batch-123")
  decision = manager.should_retry_feature(0, FailureType.TRANSIENT)
  if decision.should_retry:
      # Retry feature...
  ```

###### `record_retry_attempt(feature_index, error_message)`
- **Purpose**: Record a retry attempt
- **Parameters**:
  - `feature_index` (int): Index of feature being retried
  - `error_message` (str): Error from failed attempt
- **Side Effects**:
  - Increments per-feature retry count
  - Increments global retry count
  - Increments consecutive failure count
  - Checks circuit breaker threshold
  - Saves state atomically
  - Logs to audit trail

###### `record_success(feature_index)`
- **Purpose**: Record successful feature completion
- **Parameters**: `feature_index` (int): Index of successful feature
- **Side Effects**:
  - Resets consecutive failure count (circuit breaker reset)
  - Saves state atomically

###### `check_circuit_breaker()`
- **Purpose**: Check if circuit breaker is open
- **Returns**: `True` if open (retries blocked), `False` otherwise

###### `reset_circuit_breaker()`
- **Purpose**: Manually reset circuit breaker after investigation
- **Use Case**: After investigating root cause of consecutive failures

###### `get_retry_count(feature_index)`
- **Purpose**: Get retry count for specific feature
- **Parameters**: `feature_index` (int): Feature index
- **Returns**: `int` (number of retries, 0 if never retried)

###### `get_global_retry_count()`
- **Purpose**: Get total retries across all features
- **Returns**: `int` (total retries)

### Constants

- `MAX_RETRIES_PER_FEATURE = 3`: Max retries per feature
- `CIRCUIT_BREAKER_THRESHOLD = 5`: Consecutive failures to open circuit
- `MAX_TOTAL_RETRIES = 50`: Global retry limit across batch

### Convenience Functions

Module provides standalone functions for quick use without class:

- `should_retry_feature(batch_id, feature_index, failure_type, state_dir)` - Check if retry allowed
- `record_retry_attempt(batch_id, feature_index, error_message, state_dir)` - Record attempt
- `check_circuit_breaker(batch_id, state_dir)` - Check breaker status
- `get_retry_count(batch_id, feature_index, state_dir)` - Get retry count
- `reset_circuit_breaker(batch_id, state_dir)` - Reset breaker

### State Persistence

Retry state saved to `.claude/batch_*_retry_state.json`:

```json
{
  "batch_id": "batch-20251118-123456",
  "retry_counts": { "0": 2, "5": 1 },
  "global_retry_count": 5,
  "consecutive_failures": 0,
  "circuit_breaker_open": false,
  "created_at": "2025-11-19T10:00:00Z",
  "updated_at": "2025-11-19T10:15:00Z"
}
```

State file uses atomic writes (tempfile + rename) for crash safety.

### Audit Logging

All retry attempts logged to `.claude/audit/batch_*_retry_audit.jsonl` with entries:

```json
{
  "timestamp": "2025-11-19T10:00:00Z",
  "event_type": "retry_attempt",
  "batch_id": "batch-123",
  "feature_index": 0,
  "retry_count": 1,
  "global_retry_count": 5,
  "error_message": "ConnectionError: Failed"
}
```

### Security
- Atomic writes (temp file + rename)
- Path validation for state directories
- Error message sanitization (CWE-117)
- Circuit breaker prevents resource exhaustion
- Audit logging for all decisions

### Test Coverage
- 40+ unit tests covering:
  - Retry decision logic (all 5 checks)
  - State persistence (load/save)
  - Circuit breaker (open/close/reset)
  - Consecutive failure tracking
  - Edge cases (corrupted state, missing files)

### Used By
- /batch-implement command for automatic retry
- failure_classifier.py for error classification

### Related
- GitHub Issue #89 (Automatic Failure Recovery for /batch-implement)
- state-management-patterns skill for persistence patterns

---

## 23. batch_retry_consent.py (360 lines, v3.33.0+)

**Purpose**: First-run consent prompt and persistent state for automatic retry feature.

### Overview

Interactive consent system for /batch-implement automatic retry:
- First-run prompt (explains feature, safety limits)
- Persistent state storage (`~/.autonomous-dev/user_state.json`)
- Environment variable override (`BATCH_RETRY_ENABLED`)
- Secure file permissions (0o600 user-only)
- Path validation (prevent symlink attacks)

### Constants

- `DEFAULT_USER_STATE_FILE = ~/.autonomous-dev/user_state.json`: Default state location
- `ENV_VAR_BATCH_RETRY = "BATCH_RETRY_ENABLED"`: Environment variable name

### Main Functions

#### `check_retry_consent()`
- **Purpose**: Check if user has consented to automatic retry
- **Workflow**:
  1. Check if already set in state file
  2. If not set, prompt user
  3. Save response to state file
  4. Return response
- **Returns**: `True` if enabled, `False` if disabled
- **First Run**: Displays consent prompt, saves choice to `~/.autonomous-dev/user_state.json`
- **Subsequent Runs**: Reads from state file (no prompt)

#### `is_retry_enabled()`
- **Purpose**: Check if automatic retry is enabled
- **Priority Order**:
  1. Check environment variable `BATCH_RETRY_ENABLED` (highest priority)
  2. Check user state file `~/.autonomous-dev/user_state.json`
  3. Prompt user if not set (with check_retry_consent)
- **Returns**: `True` if enabled, `False` if disabled
- **Examples**:
  ```python
  # Environment variable overrides state file
  os.environ["BATCH_RETRY_ENABLED"] = "false"
  is_retry_enabled()  # False (env var checked first)

  # Fall back to state file if env var not set
  os.environ.pop("BATCH_RETRY_ENABLED", None)
  is_retry_enabled()  # Reads from state file or prompts
  ```

#### `prompt_for_retry_consent()`
- **Purpose**: Display first-run consent prompt and get user response
- **Returns**: `True` if user consented (yes/y/Y/Enter), `False` otherwise
- **Prompt Displays**:
  - Automatic retry feature explanation
  - Types of errors retried (network, timeout, rate limit)
  - Max 3 retries per feature
  - Circuit breaker after 5 consecutive failures
  - How to disable via `.env` file
- **Default Behavior**: Enter/no response → False (conservative default)

### State File Management

#### `save_consent_state(retry_enabled)`
- **Purpose**: Save consent decision to state file
- **Parameters**: `retry_enabled` (bool): Whether retry is enabled
- **Features**:
  - Creates directory if needed: `~/.autonomous-dev/`
  - Sets file permissions to 0o600 (user-only read/write)
  - Atomic write (tempfile + rename)
  - Preserves existing state (merges with existing keys)

#### `load_consent_state()`
- **Purpose**: Load saved consent decision
- **Returns**: `True` if enabled, `False` if disabled, `None` if not set
- **Security**: Rejects symlinks (CWE-59 prevention)
- **Graceful**: Returns `None` if file corrupted or missing

#### `get_user_state_file()`
- **Purpose**: Get path to user state file
- **Returns**: `Path` object pointing to `~/.autonomous-dev/user_state.json`
- **Note**: Can be overridden for testing

### Exceptions

#### `ConsentError`
- **Purpose**: Exception for consent-related errors
- **Raised When**:
  - User state file is a symlink (CWE-59)
  - Cannot write to user state directory
  - File corruption prevents parsing

### Security

- **CWE-22**: Path validation (rejects traversal attempts)
- **CWE-59**: Symlink rejection for user state file (prevents symlink attacks)
- **CWE-732**: File permissions secured to 0o600 (user-only read/write)
- **Atomic Writes**: Temp file + rename prevents partial writes

### State File Format

User state stored in `~/.autonomous-dev/user_state.json`:

```json
{
  "batch_retry_enabled": true,
  "other_keys": "..."
}
```

### Test Coverage
- 20+ unit tests covering:
  - Consent prompt (yes/no/invalid responses)
  - State file persistence (save/load)
  - Environment variable override
  - Symlink detection and rejection
  - File permissions validation
  - First-run vs subsequent-run behavior

### Used By
- /batch-implement command (check before retry)
- batch_retry_manager.py (respects consent setting)

### Related
- GitHub Issue #89 (Automatic Failure Recovery for /batch-implement)
- error-handling-patterns skill for exception hierarchy

## 24. agent_tracker.py (1,185 lines, v3.34.0+, Issue #79)

**Purpose**: Portable tracking infrastructure for agent execution with dynamic project root detection

**Problem Solved (Issue #79)**: Original `scripts/agent_tracker.py` had hardcoded paths that failed when:
- Running from user projects (no `scripts/` directory)
- Running from project subdirectories (couldn't find project root)
- Commands invoked from installation path vs development path

**Solution**: Library-based implementation in `plugins/autonomous-dev/lib/agent_tracker.py` with:
- Dynamic project root detection via path_utils
- Portable path resolution (no hardcoded paths)
- Atomic file writes for data consistency
- Comprehensive error handling with context

### Classes

#### `AgentTracker`
- **Purpose**: Track agent execution with structured logging
- **Initialization**: `AgentTracker(session_file=None)`
  - `session_file` (Optional[str]): Path to session file for testing
  - If None: Creates/finds session file automatically using path_utils
  - Raises `ValueError` if session_file path is outside project (path traversal prevention)
- **Features**:
  - Auto-detects project root from any subdirectory
  - Creates `docs/sessions/` directory if missing
  - Finds or creates JSON session files with timestamp naming: `YYYYMMDD-HHMMSS-pipeline.json`
  - Atomic writes using tempfile + rename pattern (Issue #45 security)
  - Path validation via shared security_utils module

### Public Methods

#### Agent Lifecycle Methods

#### `start_agent(agent_name, message)`
- **Purpose**: Log agent start time
- **Parameters**:
  - `agent_name` (str): Agent name (validated via security_utils)
  - `message` (str): Start message (max 10KB)
- **Records**:
  - Start timestamp (ISO format)
  - Agent name and status ("started")
  - Initial message
- **Security**: Input validation prevents injection attacks

#### `complete_agent(agent_name, message, tools=None, tools_used=None, github_issue=None)`
- **Purpose**: Log agent completion with optional metrics
- **Parameters**:
  - `agent_name` (str): Agent name
  - `message` (str): Completion message
  - `tools` (Optional[List[str]]): Tools declared to use (metadata)
  - `tools_used` (Optional[List[str]]): Tools actually used (audit trail)
  - `github_issue` (Optional[int]): Linked GitHub issue number
- **Records**:
  - Completion timestamp (ISO format)
  - Duration in seconds (auto-calculated from start)
  - Message and tool usage
  - Links to GitHub issue if provided
- **Returns**: Boolean indicating success
- **Error Handling**: Logs errors without raising (non-blocking)

#### `fail_agent(agent_name, message)`
- **Purpose**: Log agent failure
- **Parameters**:
  - `agent_name` (str): Agent name
  - `message` (str): Failure message
- **Records**:
  - Failure timestamp
  - Error message with context
  - Status set to "failed"
- **Security**: Error messages sanitized to prevent log injection

#### Pipeline Status Methods

#### `set_github_issue(issue_number)`
- **Purpose**: Link session to GitHub issue number
- **Parameters**: `issue_number` (int): GitHub issue (1-999999)
- **Uses**: GitHub Issue metadata in STEP 5 checkpoints

#### `show_status()`
- **Purpose**: Display current pipeline status with colors and emojis
- **Output**:
  - Session ID and start time
  - List of agents (started/completed/failed/pending)
  - Progress percentage (agents completed / total expected)
  - Tree view of execution flow
  - Duration metrics (actual, average, estimated remaining)
- **Color Coding**: Uses ANSI colors for status visualization

#### Progress Tracking Methods

#### `get_expected_agents() -> List[str]`
- **Purpose**: Return list of expected agents for workflow
- **Returns**: List of agent names (hardcoded per workflow type)
- **Used By**: Progress calculations, pipeline verification

#### `calculate_progress() -> int`
- **Purpose**: Calculate workflow completion percentage
- **Returns**: Integer 0-100
- **Calculation**: `(agents_completed / agents_expected) * 100`

#### `get_average_agent_duration() -> Optional[int]`
- **Purpose**: Calculate average duration of completed agents
- **Returns**: Seconds (or None if no agents completed)
- **Uses**: Estimation of remaining time

#### `estimate_remaining_time() -> Optional[int]`
- **Purpose**: Estimate time until workflow completion
- **Returns**: Seconds (or None if insufficient data)
- **Calculation**: `(pending_agents * average_duration) + safety_buffer`

#### `get_pending_agents() -> List[str]`
- **Purpose**: List agents not yet started
- **Returns**: List of agent names
- **Uses**: Progress tracking and timeout calculations

#### `get_running_agent() -> Optional[str]`
- **Purpose**: Get currently running agent
- **Returns**: Agent name (or None if none running)
- **Uses**: Checkpoint verification, deadlock detection

#### Verification Methods

#### `verify_parallel_exploration() -> bool`
- **Purpose**: Verify parallel exploration checkpoint (STEP 1)
- **Checks**:
  - researcher agent completed
  - planner agent completed
  - Execution time ≤ 10 minutes (typical: 5-8 minutes)
- **Returns**: True if verification passed
- **Output**: Displays efficiency metrics and time saved
- **Used By**: auto-implement.md CHECKPOINT 1 (line 109)
- **Graceful Degradation**: Returns False if AgentTracker unavailable (non-blocking)

#### `verify_parallel_validation() -> bool`
- **Purpose**: Verify parallel validation checkpoint (STEP 4.1)
- **Checks**:
  - reviewer agent completed
  - security-auditor agent completed
  - doc-master agent completed
  - Execution time ≤ 5 minutes (typical: 2-3 minutes)
- **Returns**: True if verification passed
- **Output**: Displays efficiency metrics
- **Used By**: auto-implement.md CHECKPOINT 4.1 (line 390)
- **Graceful Degradation**: Returns False if unavailable (non-blocking)

#### `get_parallel_validation_metrics() -> Dict[str, Any]`
- **Purpose**: Extract metrics from parallel validation execution
- **Returns**: Dictionary with:
  - `reviewer_duration`: seconds
  - `security_auditor_duration`: seconds
  - `doc_master_duration`: seconds
  - `parallel_time`: max of above (actual duration)
  - `sequential_time`: sum of above (if run sequentially)
  - `time_saved`: sequential - parallel
  - `efficiency_percent`: (time_saved / sequential) * 100
- **Uses**: Checkpoint display and performance analysis

#### `is_pipeline_complete() -> bool`
- **Purpose**: Check if all expected agents completed
- **Returns**: True if all agents in "completed" or "failed" state
- **Uses**: Workflow completion detection

#### `is_agent_tracked(agent_name) -> bool`
- **Purpose**: Check if agent has been logged
- **Parameters**: `agent_name` (str): Agent to check
- **Returns**: True if agent found in session

#### Environment Tracking

#### `auto_track_from_environment(message=None) -> bool`
- **Purpose**: Auto-detect running agent from environment variable
- **Parameters**: `message` (Optional[str]): Optional override message
- **Reads**: `CLAUDE_AGENT_NAME` environment variable (set by Task tool and Claude Code)
- **Returns**:
  - `True` if agent was newly tracked (created start entry)
  - `False` if agent already tracked (idempotent - no duplicate)
  - `False` if environment variable not set (graceful degradation)
- **Security**: Validates agent name format before logging
- **Used By**:
  - SubagentStop hook (log_agent_completion.py) - Issue #104
  - Explicit checkpoint tracking in auto-implement.md
- **Task Tool Integration (Issue #104)**:
  - Task tool sets `CLAUDE_AGENT_NAME` when invoking agents
  - SubagentStop hook calls this method before `complete_agent()`
  - Ensures parallel Task tool agents (reviewer, security-auditor, doc-master) are tracked
  - Prevents incomplete entries (completion without start)
  - Idempotent design prevents duplicates when combined with explicit tracking

### Formatting & Display Methods

#### `get_agent_emoji(status) -> str`
- **Purpose**: Get emoji for agent status
- **Status Mappings**:
  - "started" → "▶️"
  - "completed" → "✅"
  - "failed" → "❌"
  - "pending" → "⏳"

#### `get_agent_color(status) -> str`
- **Purpose**: Get ANSI color code for status
- **Colors**: Green (completed), Red (failed), Yellow (started), Gray (pending)

#### `get_display_metadata() -> Dict[str, Any]`
- **Purpose**: Get formatted metadata for display
- **Returns**: Dictionary with:
  - `session_id`: Unique session identifier
  - `started`: Human-readable start time
  - `duration`: Total elapsed time
  - `progress`: Completion percentage
  - `agents_summary`: Count by status

#### `get_tree_view_data() -> Dict[str, Any]`
- **Purpose**: Get tree structure for ASCII tree display
- **Returns**: Hierarchical dictionary representing workflow execution

### Session Data Format

JSON session files stored in `docs/sessions/YYYYMMDD-HHMMSS-pipeline.json`:

```json
{
  "session_id": "20251119-143022",
  "started": "2025-11-19T14:30:22.123456",
  "github_issue": 79,
  "agents": [
    {
      "agent": "researcher",
      "status": "completed",
      "started_at": "2025-11-19T14:30:25",
      "completed_at": "2025-11-19T14:35:10",
      "duration_seconds": 285,
      "message": "Found 3 JWT patterns",
      "tools_used": ["WebSearch", "Grep", "Read"]
    }
  ]
}
```

### Security Features

#### Path Traversal Prevention (CWE-22)
- All paths validated to stay within project root
- Rejects `..` sequences in path strings
- Uses shared `validate_path()` from security_utils
- Audit logging of all validation attempts

#### Symlink Attack Prevention (CWE-59)
- Rejects symlinks that could bypass restrictions
- Path normalization prevents escape attempts
- Atomic file writes prevent partial reads

#### Input Validation
- Agent names: 1-255 chars, alphanumeric + hyphen/underscore only
- Messages: Max 10KB to prevent log bloat
- GitHub issue: Positive integers 1-999999 only
- Control character filtering prevents log injection (CWE-117)

#### Atomic File Writes (Issue #45)
- Uses tempfile + rename pattern for consistency
- Process crash during write: Original file unchanged
- Prevents readers from seeing corrupted/partial JSON
- On POSIX: Rename is guaranteed atomic by OS

### Class Methods

#### `AgentTracker.save_agent_checkpoint()` (NEW - Issue #79, v3.36.0+)

**Signature**:
```python
@classmethod
def save_agent_checkpoint(
    cls,
    agent_name: str,
    message: str,
    github_issue: Optional[int] = None,
    tools_used: Optional[List[str]] = None
) -> bool
```

**Purpose**: Convenience class method for agents to save checkpoints without creating AgentTracker instances. Solves the dogfooding bug (Issue #79) where hardcoded paths caused `/auto-implement` to stall for 7+ hours.

**Parameters**:
- `agent_name` (str): Agent name (e.g., 'researcher', 'planner'). Must be alphanumeric + hyphen/underscore.
- `message` (str): Brief completion summary. Maximum 10KB.
- `github_issue` (Optional[int]): GitHub issue number being worked on. Range: 1-999999.
- `tools_used` (Optional[List[str]]): List of tools used during execution. Stored in session file for audit trail.

**Returns**: `bool`
- `True` if checkpoint saved successfully
- `False` if skipped due to graceful degradation (user project, import error, filesystem error)

**Behavior**:
- Uses portable path detection (works from any directory)
- Creates AgentTracker internally (caller doesn't manage instance)
- Validates all inputs before saving
- Gracefully degrades in user projects (prints info message, returns False)
- Never raises exceptions (non-blocking design)

**Examples**:

```python
# Basic usage (works from any directory)
from agent_tracker import AgentTracker

success = AgentTracker.save_agent_checkpoint(
    'researcher',
    'Found 3 JWT patterns in codebase'
)
if success:
    print("✅ Checkpoint saved")
else:
    print("ℹ️ Skipped (user project)")

# With all parameters
success = AgentTracker.save_agent_checkpoint(
    agent_name='planner',
    message='Architecture designed - see docs/design/auth.md',
    github_issue=79,
    tools_used=['FileSearch', 'Read', 'Write']
)

# In agent code (automatic error handling)
AgentTracker.save_agent_checkpoint(
    agent_name='implementer',
    message='Implementation complete - 450 lines of code',
    tools_used=['Read', 'Write', 'Execute']
)
# Even if this fails, agent continues working
```

**Security**:
- Input validation: agent_name, message, github_issue all validated
- Path validation: All paths checked against project root (CWE-22)
- No subprocess calls: Uses library imports (prevents CWE-78)
- Message length limit: Prevents log bloat attacks
- Graceful degradation: No sensitive error leakage

**Graceful Degradation**:
When running in environments without tracking infrastructure:
- User projects (no `plugins/` directory) → skips, returns False
- Import errors (missing dependencies) → skips, returns False
- Filesystem errors (permission denied) → skips, returns False
- Unexpected errors → logs warning, returns False

This allows agents to be portable across development and user environments.

**Design Pattern**: Progressive Enhancement - feature works with or without supporting infrastructure

**Related**: GitHub Issue #79 (Dogfooding bug fix), Issue #82 (Optional checkpoint verification)


### CLI Wrapper

**File**: `plugins/autonomous-dev/scripts/agent_tracker.py`
- **Purpose**: CLI interface for library functionality
- **Design**: Delegates to `plugins/autonomous-dev/lib/agent_tracker.py`
- **Commands**:
  - `start <agent_name> <message>`: Start agent tracking
  - `complete <agent_name> <message> [--tools tool1,tool2]`: Complete agent
  - `fail <agent_name> <message>`: Log failure
  - `status`: Display current status
- **Backward Compatibility**: Installed plugin uses lib version directly

### Deprecation (Issue #79)

**Deprecated**: `scripts/agent_tracker.py` (original location)
- **Reason**: Hardcoded paths fail in user projects and subdirectories
- **Migration**:
  - For CLI: Use `plugins/autonomous-dev/scripts/agent_tracker.py` (installed plugin)
  - For imports: Use `from plugins.autonomous-dev.lib.agent_tracker import AgentTracker`
  - Existing code continues to work (delegates to library implementation)
  - Will be removed in v4.0.0

### Usage Examples

#### Basic Usage (Standard Mode)
```python
from plugins.autonomous_dev.lib.agent_tracker import AgentTracker

# Create tracker (auto-detects project root)
tracker = AgentTracker()

# Log agent start
tracker.start_agent("researcher", "Researching JWT patterns")

# Log agent completion
tracker.complete_agent("researcher", "Found 3 patterns",
                       tools_used=["WebSearch", "Grep", "Read"],
                       github_issue=79)

# Display status
tracker.show_status()
```

#### Testing with Explicit Session File
```python
from pathlib import Path
tracker = AgentTracker(session_file="/tmp/test-session.json")
tracker.start_agent("test-agent", "Testing")
```

#### Checkpoint Verification (auto-implement.md)
```python
tracker = AgentTracker()

# Verify parallel exploration (STEP 1)
if tracker.verify_parallel_exploration():
    print("✅ PARALLEL EXPLORATION: SUCCESS")
    metrics = tracker.get_parallel_validation_metrics()
    print(f"Time saved: {metrics['time_saved']}s ({metrics['efficiency_percent']}%)")
else:
    print("⚠️ Parallel exploration verification failed")
    # Workflow continues regardless (graceful degradation)
```

### Error Handling

All exceptions include context and guidance:
```python
try:
    tracker = AgentTracker(session_file="../../etc/passwd")
except ValueError as e:
    # Error includes: what went wrong, why, and what's expected
    # Example: "Path traversal attempt detected: /etc/passwd"
    print(e)
```

### Test Coverage
- 66+ unit tests (85.7% coverage) in `tests/unit/lib/test_agent_tracker_issue79.py`
- Integration tests for checkpoint verification
- Path resolution from nested subdirectories
- Atomic write pattern verification
- Security validation (path traversal, symlinks, input bounds)

### Used By
- `/auto-implement` command checkpoints (parallel exploration, parallel validation)
- `/batch-implement` for pipeline tracking
- Dogfooding infrastructure in autonomous-dev repo
- Optional checkpoint verification (graceful degradation in user projects)

### Related
- GitHub Issue #79 (Dogfooding bug - tracking infrastructure hardcoded paths)
- GitHub Issue #82 (Optional checkpoint verification with graceful degradation)
- GitHub Issue #45 (Atomic write pattern and security hardening)
- path_utils.py (Dynamic project root detection)
- security_utils.py (Path validation and input bounds checking)

### Design Patterns
- **Two-tier Design**: Library (core logic) + CLI wrapper (interface)
- **Progressive Enhancement**: Features gracefully degrade if infrastructure unavailable
- **Atomic Writes**: Tempfile + rename for consistency
- **Path Portability**: Uses path_utils instead of hardcoded paths

## 25. session_tracker.py (165 lines, v3.28.0+, Issue #79)

**Purpose**: Session logging for agent actions with portable path detection

**Problem Solved (Issue #79)**: Original session tracking had hardcoded `docs/sessions/` path that failed when:
- Running from user projects (no `docs/` directory available)
- Running from project subdirectories (couldn't dynamically find project root)
- Commands invoked from installation path vs development path

**Solution**: Library-based implementation in `plugins/autonomous-dev/lib/session_tracker.py` with:
- Dynamic session directory detection via path_utils
- Portable path resolution (no hardcoded paths)
- Graceful error handling with fallbacks
- Comprehensive docstrings with design patterns

### Classes

#### `SessionTracker`
- **Purpose**: Log agent actions to session file instead of keeping in context
- **Initialization**: `SessionTracker(session_file=None, use_cache=True)`
  - `session_file` (Optional[str]): Path to session file for testing
  - `use_cache` (bool): If True, use cached project root (default: True)
  - If None: Creates/finds session file automatically using path_utils
  - Raises `ValueError` if session_file path is outside project
- **Features**:
  - Auto-detects project root from any subdirectory
  - Creates `docs/sessions/` directory if missing
  - Finds or creates session files with timestamp naming: `YYYYMMDD-HHMMSS-session.md`
  - Path validation via shared validation module
  - Directory permission checking (warns on world-writable)

### Public Methods

#### `log(agent_name, message) -> None`
- **Purpose**: Log agent action to session file
- **Parameters**:
  - `agent_name` (str): Agent identifier (e.g., "researcher", "implementer")
  - `message` (str): Action message (e.g., "Research complete - docs/research/auth.md")
- **Output**:
  - Appends to session file with timestamp
  - Prints confirmation to console
- **Format**: `**HH:MM:SS - agent_name**: message`
- **Example Output**:
  ```
  **14:30:22 - researcher**: Research complete - docs/research/auth.md
  ```

### Helper Functions

#### `get_default_session_file() -> Path`
- **Purpose**: Get default session file path with timestamp
- **Returns**: Path object for new session file
- **Format**: `<session_dir>/session-YYYY-MM-DD-HHMMSS.md`
- **Uses**: path_utils.get_session_dir() for portable resolution
- **Example**:
  ```python
  path = get_default_session_file()
  print(path.name)  # session-2025-11-19-143022.md
  ```

### File Format

Session files stored in `docs/sessions/YYYYMMDD-HHMMSS-session.md`:

```markdown
# Session 20251119-143022

**Started**: 2025-11-19 14:30:22

---

**14:30:25 - researcher**: Research complete - docs/research/jwt-patterns.md

**14:35:10 - planner**: Plan complete - docs/design/auth-architecture.md

**14:45:30 - test-master**: Tests written - 12 test cases

**15:02:15 - implementer**: Implementation complete - src/auth/jwt_handler.py
```

### Security Features

#### Path Validation (CWE-22)
- All paths validated via validation module
- Rejects paths outside project directory
- Uses path_utils for consistent resolution
- Audit logging on validation errors

#### Permission Checking (CWE-732)
- Warns if session directory is world-writable
- Checks ownership on POSIX systems
- Gracefully handles Windows (different permission model)

#### Input Validation
- Agent names must match `/^[a-zA-Z0-9_-]+$/` (via validation module)
- Messages limited to reasonable length
- Control characters filtered to prevent log injection

### CLI Wrapper

**File**: `plugins/autonomous-dev/scripts/session_tracker.py`
- **Purpose**: CLI interface for library functionality
- **Design**: Delegates to `plugins/autonomous-dev/lib/session_tracker.py`
- **Usage**: `python plugins/autonomous-dev/scripts/session_tracker.py <agent_name> <message>`
- **Example**: `python plugins/autonomous-dev/scripts/session_tracker.py researcher "Found 3 JWT patterns"`

### Deprecation (Issue #79)

**Deprecated**: `scripts/session_tracker.py` (original location)
- **Reason**: Hardcoded paths fail in user projects and subdirectories
- **Migration**:
  - For CLI: Use `plugins/autonomous-dev/scripts/session_tracker.py` (installed plugin)
  - For imports: Use `from plugins.autonomous-dev.lib.session_tracker import SessionTracker`
  - Existing code continues to work (delegates to library implementation)
  - Will be removed in v4.0.0

### Usage Examples

#### Basic Session Logging
```python
from plugins.autonomous_dev.lib.session_tracker import SessionTracker

# Create tracker (auto-detects project root)
tracker = SessionTracker()

# Log agent actions
tracker.log("researcher", "Found 3 JWT patterns in codebase")
tracker.log("planner", "Architecture designed - see docs/design/auth.md")
tracker.log("test-master", "12 test cases written")
tracker.log("implementer", "Implementation complete - 450 lines of code")
```

#### Testing with Explicit Session File
```python
from pathlib import Path
tracker = SessionTracker(session_file="/tmp/test-session.md")
tracker.log("test-agent", "Testing portable path detection")
```

#### From auto-implement Checkpoints
```bash
# Log from bash (CHECKPOINT 1)
python plugins/autonomous-dev/scripts/session_tracker.py auto-implement "Parallel exploration completed"

# Log from bash (CHECKPOINT 4.1)
python plugins/autonomous-dev/scripts/session_tracker.py auto-implement "Parallel validation completed"
```

### Error Handling

All exceptions include context and guidance:
```python
try:
    tracker = SessionTracker(session_file="../../etc/passwd")
except ValueError as e:
    # Error includes: what went wrong, why, and what's expected
    # Example: "Path traversal attempt detected: /etc/passwd"
    print(e)
```

### Test Coverage
- 30+ unit tests in `tests/unit/lib/test_session_tracker.py`
- Path resolution from nested subdirectories
- Session file creation and appending
- Directory permission checking
- Input validation (agent names, messages)
- Security validation (path traversal, symlinks)

### Used By
- `/auto-implement` command checkpoints (progress tracking)
- `/batch-implement` for feature logging
- Dogfooding infrastructure (session logs in docs/sessions/)
- CI/CD pipelines for audit trails
- Optional checkpoint logging (graceful degradation in user projects)

### Related
- GitHub Issue #79 (Tracking infrastructure hardcoded paths)
- GitHub Issue #82 (Optional checkpoint verification with graceful degradation)
- GitHub Issue #85 (Portable checkpoint implementation)
- GitHub Issue #45 (Atomic write pattern and security hardening)
- path_utils.py (Dynamic project root detection)
- validation.py (Path and input validation)
- agent_tracker.py (Agent execution tracking)

### Design Patterns
- **Two-tier Design**: Library (core logic) + CLI wrapper (interface)
- **Progressive Enhancement**: Features gracefully degrade if unavailable
- **Portable Paths**: Uses path_utils instead of hardcoded paths
- **Non-blocking**: Logging failures don't break workflows

---

## 26. workflow_tracker.py (528 lines, v3.48.0+, Issue #155)

**Purpose**: Workflow state tracking for preference learning - records which quality workflow steps were taken/skipped, detects user corrections from feedback, and learns preferences over time.

**Location**: `plugins/autonomous-dev/lib/workflow_tracker.py`

**Problem Solved (Issue #155)**: Claude can't remember workflow preferences across sessions. This library enables learning from user corrections to improve workflow decisions over time.

### Key Features

- **Step tracking**: Records which quality steps were taken (research, testing, planning, review, security, docs, etc.) vs skipped
- **Correction detection**: Parses user feedback patterns to detect improvement signals
- **Preference learning**: Derives user preferences from correction patterns over time
- **Privacy-preserving**: Local storage only (~/.autonomous-dev/workflow_state.json), no cloud sync
- **Atomic persistence**: Thread-safe with file locking for concurrent access
- **Time-based decay**: Preferences evolve as user practices change (configurable 30-day window)

### Quick Start

```python
from workflow_tracker import WorkflowTracker, detect_correction

# Track workflow steps
tracker = WorkflowTracker()
tracker.start_session()
tracker.record_step("research", taken=True)
tracker.record_step("testing", taken=False, reason="quick fix")
tracker.save()

# Detect corrections in user feedback
correction = detect_correction("you should have researched first")
if correction:
    tracker.record_correction(correction["step"], correction["text"])

# Get learned preferences
prefs = tracker.get_preferences()
recommended = tracker.get_recommended_steps()
```

### Workflow Steps

8 quality workflow steps tracked:

- `alignment` - PROJECT.md alignment check
- `research` - Codebase/web research
- `planning` - Implementation planning
- `testing` - TDD tests
- `implementation` - Code implementation
- `review` - Code review
- `security` - Security audit
- `documentation` - Doc updates

### Public API

#### `detect_correction(user_input: str) -> Optional[Dict[str, str]]`

**Purpose**: Detect correction signals in user feedback using pattern matching

**Parameters**:
- `user_input` (str): User's message text

**Returns**: Dict with 'step', 'text', 'pattern', 'keyword' if detected, None otherwise

**Patterns Detected**:
- "you should have X" → `should_have` pattern
- "need to X first" → `need_to` pattern
- "forgot to X" → `forgot` pattern
- "should always X" → `always_should` pattern
- "didn't X" → `didnt` pattern
- "should X before" → `should_before` pattern

**Example**:
```python
result = detect_correction("you should have researched first")
# Returns: {
#   'step': 'research',
#   'text': 'you should have researched first',
#   'pattern': 'should_have',
#   'keyword': 'researched'
# }
```

#### `class WorkflowTracker`

Main tracker for session and preference management.

**Constructor**:
```python
tracker = WorkflowTracker(state_file: Optional[Path] = None)
```

**Parameters**:
- `state_file` (Optional[Path]): Custom state file path (default: ~/.autonomous-dev/workflow_state.json)

**Attributes**:
- `state_file: Path` - Path to workflow state JSON file
- `_state: Dict[str, Any]` - In-memory state dict
- `_current_session: Optional[Dict[str, Any]]` - Current active session

### Session Management Methods

#### `start_session(task_type: Optional[str] = None) -> str`

Start a new workflow session.

**Parameters**:
- `task_type` (Optional[str]): Task type for context (e.g., 'feature', 'bugfix', 'docs')

**Returns**: Session ID (UUID string)

**Example**:
```python
session_id = tracker.start_session(task_type="feature")
```

#### `end_session() -> None`

End current session and add to history. Automatically saves state.

**Trimming**: Keeps max 50 most recent sessions to prevent unbounded growth

#### `get_sessions() -> List[Dict[str, Any]]`

Get all recorded sessions.

**Returns**: List of session dicts with session_id, started_at, ended_at, steps, task_type

#### `get_current_session_steps() -> List[Dict[str, Any]]`

Get steps from current active session.

**Returns**: List of step records with step name, taken (bool), timestamp, optional reason

### Step Tracking Methods

#### `record_step(step: str, taken: bool, reason: Optional[str] = None) -> None`

Record a workflow step taken or skipped.

**Parameters**:
- `step` (str): Step name (alignment, research, testing, etc.)
- `taken` (bool): True if step was taken, False if skipped
- `reason` (Optional[str]): Why step was skipped (e.g., 'quick fix', 'already researched')

**Example**:
```python
tracker.record_step("testing", taken=False, reason="quick fix")
tracker.record_step("documentation", taken=True)
```

### Correction Tracking Methods

#### `record_correction(step: str, text: str, task_type: Optional[str] = None) -> None`

Record a user correction to update preferences.

**Parameters**:
- `step` (str): Step that was corrected
- `text` (str): Original user text that contained correction
- `task_type` (Optional[str]): Task type for context-specific learning

**Behavior**: Increments correction count for the step and updates task-type preferences

**Example**:
```python
tracker.record_correction("research", "you should have researched first", task_type="feature")
```

#### `get_corrections() -> List[Dict[str, Any]]`

Get all recorded corrections.

**Returns**: List of correction dicts with step, text, timestamp, task_type

### Preference Learning Methods

#### `get_preferences() -> Dict[str, Any]`

Get learned preferences.

**Returns**: Dict with:
- `emphasized_steps` (Dict[str, int]): step → correction count
- `task_type_preferences` (Dict[str, Dict[str, int]]): task_type → {step → count}

#### `get_recommended_steps(task_type: Optional[str] = None) -> List[str]`

Get recommended workflow steps based on learned preferences.

**Parameters**:
- `task_type` (Optional[str]): Task type for context-specific recommendations

**Returns**: List of step names in priority order (most corrections first)

**Algorithm**:
- Steps above `CORRECTION_THRESHOLD` (default: 3) are recommended
- Task-type specific steps merged with general preferences
- Results sorted by correction count (highest priority first)

**Example**:
```python
# After 3+ corrections for research step
recommended = tracker.get_recommended_steps()
# Returns: ['research', ...]

# Task-specific recommendations
recommended = tracker.get_recommended_steps(task_type="bugfix")
# Returns: ['security', 'testing', ...] if those were corrected for bugfixes
```

#### `apply_preference_decay() -> None`

Apply time-based decay to old corrections.

**Behavior**:
- Removes corrections older than `PREFERENCE_DECAY_DAYS` (default: 30)
- Allows preferences to evolve as user practices change
- Updates emphasized_steps from recent corrections only

**Example**:
```python
# Run weekly to keep preferences fresh
tracker.apply_preference_decay()
tracker.save()
```

### Persistence Methods

#### `save() -> bool`

Save state to file using atomic write.

**Returns**: True if save succeeded, False otherwise

**Implementation**:
- Atomic write: Tempfile + rename pattern
- Creates ~/.autonomous-dev/ directory if missing
- Updates metadata timestamps
- Graceful error handling (non-blocking)

### State File Format

**Location**: ~/.autonomous-dev/workflow_state.json

**Structure**:
```json
{
  "version": "1.0",
  "sessions": [
    {
      "session_id": "abc123-...",
      "started_at": "2025-12-17T10:30:00Z",
      "ended_at": "2025-12-17T10:45:00Z",
      "task_type": "feature",
      "steps": [
        {
          "step": "research",
          "taken": true,
          "timestamp": "2025-12-17T10:30:05Z"
        },
        {
          "step": "testing",
          "taken": false,
          "reason": "quick fix",
          "timestamp": "2025-12-17T10:30:10Z"
        }
      ]
    }
  ],
  "preferences": {
    "emphasized_steps": {
      "research": 5,
      "security": 3
    },
    "task_type_preferences": {
      "feature": {
        "testing": 4,
        "research": 3
      }
    }
  },
  "corrections": [
    {
      "step": "research",
      "text": "you should have researched first",
      "timestamp": "2025-12-17T10:45:00Z",
      "task_type": "feature"
    }
  ],
  "metadata": {
    "created_at": "2025-12-17T10:00:00Z",
    "updated_at": "2025-12-17T10:45:00Z"
  }
}
```

### Configuration Constants

- `MAX_SESSIONS = 50` - Maximum sessions to keep
- `CORRECTION_THRESHOLD = 3` - Minimum corrections to emphasize a step
- `PREFERENCE_DECAY_DAYS = 30` - Days before old corrections decay
- `WORKFLOW_STEPS` - List of 8 quality workflow steps

### Keyword Matching

Step detection from user text uses keyword mappings:

```python
STEP_KEYWORDS = {
    "research": ["research", "searched", "looked", "checked", "investigated"],
    "testing": ["test", "tested", "tests", "tdd", "unittest", "write"],
    "planning": ["plan", "planned", "planning", "design"],
    "review": ["review", "reviewed", "check", "checked"],
    "security": ["security", "secure", "audit", "audited", "vulnerability", "run"],
    "documentation": ["document", "documented", "docs", "readme"],
    "alignment": ["align", "aligned", "project", "goals"],
    "implementation": ["implement", "implemented", "code", "coded"],
}
```

### Thread Safety

- Thread-safe with `threading.RLock()` for concurrent access
- Atomic file writes prevent corruption
- In-memory state protected by lock

### Error Handling

All errors are non-blocking:
- Load errors (corrupted JSON, missing file) → return defaults
- Save errors (permission denied, disk full) → log and continue
- Invalid inputs → logged but don't raise exceptions

### CLI Entry Point

```bash
# Detect correction in text
python plugins/autonomous-dev/lib/workflow_tracker.py detect "you should have researched first"

# Show learned preferences
python plugins/autonomous-dev/lib/workflow_tracker.py preferences

# Show session count
python plugins/autonomous-dev/lib/workflow_tracker.py sessions
```

### Usage Examples

#### Tracking a feature development workflow
```python
from workflow_tracker import WorkflowTracker

tracker = WorkflowTracker()
tracker.start_session(task_type="feature")

# Took research step
tracker.record_step("research", taken=True)

# Skipped testing due to small change
tracker.record_step("testing", taken=False, reason="small change")

# Took other steps
tracker.record_step("implementation", taken=True)
tracker.record_step("review", taken=True)
tracker.record_step("security", taken=True)

tracker.end_session()
tracker.save()
```

#### Learning from user feedback
```python
from workflow_tracker import WorkflowTracker, detect_correction

tracker = WorkflowTracker()

# User says: "you should have written tests before implementing"
feedback = "you should have written tests before implementing"
correction = detect_correction(feedback)

if correction:
    # correction = {'step': 'testing', 'text': '...', 'pattern': 'should_have', 'keyword': 'written'}
    tracker.record_correction(correction['step'], feedback, task_type="feature")
    tracker.save()

# After 3+ corrections on testing for features
tracker.apply_preference_decay()
recommended = tracker.get_recommended_steps(task_type="feature")
# recommended = ['testing', ...] (emphasized because of corrections)
```

#### Preference-based workflow recommendations
```python
tracker = WorkflowTracker()

# Get user's learned preferences
prefs = tracker.get_preferences()
emphasized = prefs.get("emphasized_steps", {})

# Use in decision-making
if "testing" in emphasized and emphasized["testing"] >= 3:
    # User frequently corrected skipping tests
    # Recommend always taking testing step
    print("Based on your feedback, testing is important")
```

### Design Patterns

- **Non-blocking**: All saves gracefully degrade if they fail
- **Atomic writes**: Tempfile + rename prevents corruption
- **Thread-safe**: RLock protects concurrent access
- **Preference decay**: Old corrections naturally fade (30 days default)
- **Progressive learning**: Tracks both sessions and corrections

### Performance Characteristics

- **Session storage**: Max 50 sessions × ~500 bytes = 25KB typical
- **Correction tracking**: Unlimited, but old corrections decay
- **Save latency**: <100ms for typical state size
- **Memory footprint**: <10MB with 50 sessions + history

### Security Features

- **Local storage only**: No cloud sync, no network calls
- **User home directory**: ~/.autonomous-dev/ owned by user
- **Atomic writes**: Prevents partial corruption
- **No sensitive data**: No passwords, keys, or PII stored
- **Privacy preserving**: Data never leaves machine

### Related Components

**Imports**:
- `threading` - Thread-safe access
- `tempfile` - Atomic writes
- `json` - State serialization
- `pathlib.Path` - Path handling
- `uuid` - Session ID generation
- `datetime` - Timestamp recording
- `dataclasses` - Optional future enhancement
- `regex` - Correction pattern detection

**Used By**:
- Future: Agent learning system (preference-based decision making)
- Future: Claude's workflow optimization
- Testing: Preference learning validation

**Related Issues**:
- GitHub Issue #155 - Workflow state tracking for preference learning
- GitHub Issue #140 - Agent skills and knowledge injection (related)
- GitHub Issue #148 - Claude Code 2.0 compliance (context)

### Troubleshooting

**Permissions Denied**: If ~/.autonomous-dev/ creation fails:
```bash
mkdir -p ~/.autonomous-dev
chmod 700 ~/.autonomous-dev
```

**State File Corruption**: Corrupted JSON is automatically handled:
```python
# Corrupted file is ignored, fresh state created
tracker = WorkflowTracker()
tracker.save()  # Creates new clean state file
```

**Preference Not Learning**: Check correction recording:
```python
tracker = WorkflowTracker()
corrections = tracker.get_corrections()
prefs = tracker.get_preferences()
print(f"Corrections: {len(corrections)}")
print(f"Preferences: {prefs}")
```

---


## Design Pattern

**Progressive Enhancement**: Libraries use string → path → whitelist validation pattern, allowing graceful error recovery

**Non-blocking Enhancements**: Version detection, orphan cleanup, hook activation, parity validation, git automation, issue automation, and brownfield retrofit don't block core operations

**Two-tier Design**:
- Core logic libraries (plugin_updater.py, auto_implement_git_integration.py, brownfield_retrofit.py + 5 phase libraries)
- CLI interface scripts (update_plugin.py, auto_git_workflow.py, align_project_retrofit.py)
- Enables reuse and testing
- Note: /create-issue uses direct gh CLI (no wrapper library)

**Optional Features**: Feature automation and other enhancements are controlled by flags/hooks

## 35. mcp_permission_validator.py (862 lines, v3.37.0)

**Purpose**: Security validation for MCP server operations with whitelist-based permission system

**Issue**: #95 (MCP Server Security)

### Classes

#### `ValidationResult` (dataclass)

Permission validation result.

**Attributes**:
- `approved: bool` - Whether operation is approved
- `reason: Optional[str]` - Reason for denial (None if approved)

**Methods**:
- `to_dict() -> Dict[str, Any]` - Serialize to dictionary

#### `MCPPermissionValidator` (862 lines)

Main validation class for MCP operations.

**Constructor**:
```python
validator = MCPPermissionValidator(policy_path: Optional[str] = None)
```

**Methods**:

##### `validate_fs_read(path: str) -> ValidationResult`
- Validates filesystem read operations
- Checks glob patterns, sensitive files, path traversal
- Returns approval/denial with reason
- **Example**:
  ```python
  result = validator.validate_fs_read("src/main.py")
  if result.approved:
      with open("src/main.py") as f:
          content = f.read()
  ```

##### `validate_fs_write(path: str) -> ValidationResult`
- Validates filesystem write operations
- Checks write patterns, prevents sensitive file overwrites
- Returns approval/denial with reason

##### `validate_shell_execute(command: str) -> ValidationResult`
- Validates shell command execution
- Checks allowed commands, detects injection patterns
- Blocks semicolons, pipes, command substitution
- Returns approval/denial with reason

##### `validate_network_access(url: str) -> ValidationResult`
- Validates network access requests
- Blocks localhost, private IPs, metadata services
- Checks domain allowlist
- Returns approval/denial with reason

##### `validate_env_access(var_name: str) -> ValidationResult`
- Validates environment variable access
- Blocks secret variables (API keys, tokens)
- Checks variable allowlist
- Returns approval/denial with reason

##### `load_policy(policy: Dict[str, Any]) -> None`
- Load security policy from dictionary
- Validates policy structure
- Updates validator state

### Internal Methods

**Glob Pattern Matching**:
- `matches_glob_pattern(path: str, pattern: str) -> bool` - Glob matching with ** and * support

**Threat Detection**:
- `_is_path_traversal(path: str) -> bool` - Detects .. and absolute paths
- `_is_dangerous_symlink(path: str) -> bool` - Blocks symlink attacks
- `_has_command_injection(command: str) -> bool` - Detects shell metacharacters
- `_is_private_ip(hostname: str) -> bool` - Blocks private IP ranges
- `_is_sensitive_file(path: str) -> bool` - Hardcoded sensitive file detection

**Pattern Matching**:
- `_matches_any_pattern(path: str, patterns: List[str]) -> bool` - Check path against patterns
- `_matches_any_domain(hostname: str, domains: List[str]) -> bool` - Check domain against patterns

**Audit Logging**:
- `_audit_log(operation: str, status: str, context: Dict[str, Any]) -> None` - Log all validation decisions

### Module-level Functions

Convenience functions for single-use validation:

```python
from autonomous_dev.lib.mcp_permission_validator import (
    validate_fs_read,
    validate_fs_write,
    validate_shell_execute,
    validate_network_access,
    validate_env_access,
    matches_glob_pattern
)

# Single operation validation
result = validate_fs_read("src/main.py", policy_path=".mcp/security_policy.json")
```

### Default Security Policy

If no policy file specified, uses safe development defaults:
- Read: src/**, tests/**, docs/**, config files
- Write: src/**, tests/**, docs/**
- Shell: pytest, git, python, pip, npm, make
- Network: All domains (except localhost/private)
- Environment: Safe variables only

### Security Coverage

Prevents:
- **CWE-22**: Path traversal (../../.env)
- **CWE-59**: Symlink attacks
- **CWE-78**: OS command injection
- **SSRF**: Server-side request forgery
- **Secret exposure**: API key/token access

### Used By

- `mcp_security_enforcer.py` hook - PreToolUse hook for MCP tool validation
- Custom MCP server implementations
- Permission validation workflows

### Related

- GitHub Issue #95 (MCP Server Security)
- [MCP-SECURITY.md](MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/mcp_security_enforcer.py` - Hook implementation
- `.mcp/security_policy.json` - Policy configuration file

---

## 36. mcp_profile_manager.py (533 lines, v3.37.0)

**Purpose**: Pre-configured security profiles for MCP server operations

**Issue**: #95 (MCP Server Security)

### Enums

#### `ProfileType`

Pre-configured security profiles.

**Values**:
- `DEVELOPMENT` - Most permissive (local development)
- `TESTING` - Moderate restrictions (CI/CD, test environments)
- `PRODUCTION` - Strictest (production automation)

**Methods**:
- `from_string(value: str) -> ProfileType` - Parse string to enum

### Dataclasses

#### `SecurityProfile`

Security profile configuration.

**Attributes**:
- `version: str` - Profile schema version
- `profile: str` - Profile name (development, testing, production)
- `filesystem: Dict[str, List[str]]` - Read/write allowlists
- `shell: Dict[str, Any]` - Command allowlists
- `network: Dict[str, List[str]]` - Domain/IP allowlists
- `environment: Dict[str, List[str]]` - Variable allowlists

**Methods**:
- `from_dict(data: Dict[str, Any]) -> SecurityProfile` - Deserialize from dictionary
- `to_dict() -> Dict[str, Any]` - Serialize to dictionary
- `validate() -> ValidationResult` - Validate profile structure

### Classes

#### `MCPProfileManager`

Manage and generate security profiles.

**Constructor**:
```python
manager = MCPProfileManager()
```

**Methods**:

##### `create_profile(profile_type: ProfileType) -> Dict[str, Any]`
- Generate pre-configured profile
- **Example**:
  ```python
  profile = manager.create_profile(ProfileType.DEVELOPMENT)
  ```

##### `save_profile(profile: Dict[str, Any], output_path: str) -> None`
- Write profile to JSON file
- **Example**:
  ```python
  manager.save_profile(profile, ".mcp/security_policy.json")
  ```

##### `load_profile(input_path: str) -> Dict[str, Any]`
- Read profile from JSON file
- Validates structure on load
- **Example**:
  ```python
  profile = manager.load_profile(".mcp/security_policy.json")
  ```

### Profile Generation Functions

Standalone functions for generating profiles:

```python
from autonomous_dev.lib.mcp_profile_manager import (
    generate_development_profile,
    generate_testing_profile,
    generate_production_profile
)

dev = generate_development_profile()
test = generate_testing_profile()
prod = generate_production_profile()
```

#### `generate_development_profile() -> Dict[str, Any]`

Most permissive profile for local development.

**Permissions**:
- Read: src/**, tests/**, docs/**, *.md, *.json, config files
- Write: src/**, tests/**, docs/**
- Shell: pytest, git, python, python3, pip, npm, make
- Network: All domains (except localhost/private)
- Environment: Safe variables only (PATH, HOME, USER, SHELL, LANG, PWD, TERM)
- Blocks: .env, .git, .ssh, keys, tokens, secrets

#### `generate_testing_profile() -> Dict[str, Any]`

Moderate restrictions for CI/CD and test environments.

**Permissions**:
- Read: src/**, tests/**, config (no docs)
- Write: tests/** only (read-only source)
- Shell: pytest only
- Network: Specific test APIs only
- Environment: Test variables only

#### `generate_production_profile() -> Dict[str, Any]`

Strictest profile for production automation.

**Permissions**:
- Read: Specific paths only (no source)
- Write: logs/**, data/** only
- Shell: Safe read-only commands only
- Network: Specific production APIs only
- Environment: Production config only (no secrets)

### Profile Customization

#### `customize_profile(profile: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]`

Customize profile with override values.

**Example**:
```python
from autonomous_dev.lib.mcp_profile_manager import customize_profile

custom = customize_profile(profile, {
    "filesystem": {
        "read": ["src/**", "config/**"]
    },
    "shell": {
        "allowed_commands": ["pytest", "git", "poetry"]
    }
})
```

**Behavior**:
- Deep merge with profile dict
- Override values replace profile values
- New keys added to profile

### Validation

#### `validate_profile_schema(profile: Dict[str, Any]) -> ValidationResult`

Validate profile structure.

**Checks**:
- Required fields present
- Correct types
- Policy structure matches schema

**Returns**: ValidationResult with approval/denial

### Export

#### `export_profile(profile: Dict[str, Any], output_format: str = "json") -> str`

Export profile to string format.

**Formats**:
- json - JSON string
- yaml - YAML string (if PyYAML available)

### Used By

- `mcp_security_enforcer.py` hook - Load profiles on startup
- `mcp_permission_validator.py` - Fallback to development profile
- Setup and initialization scripts

### Related

- GitHub Issue #95 (MCP Server Security)
- [MCP-SECURITY.md](MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/mcp_security_enforcer.py` - Hook implementation
- `.mcp/security_policy.json` - Policy configuration file

---

---

**For usage examples and integration patterns**: See CLAUDE.md Architecture section and individual command documentation

## 37. mcp_server_detector.py (180+ lines, v3.37.0)

**Purpose**: Detect MCP server type from tool calls and parameters for server-specific validation

**Issue**: #95 (MCP Server Security)

### Enums

#### `MCPServerType`

MCP server types with detection support.

**Members**:
- `FILESYSTEM` - Filesystem operations (read_file, write_file, list_files)
- `GIT` - Git repository operations (git_status, git_commit)
- `GITHUB` - GitHub API (create_issue, get_repo, list_prs)
- `PYTHON` - Python REPL execution (execute_code, evaluate)
- `BASH` - Shell command execution (run_command, execute_sh)
- `WEB` - Web operations (search_web, fetch_url)
- `UNKNOWN` - Unrecognized server type

### Functions

#### `detect_mcp_server(tool_name: str, params: Dict[str, Any]) -> MCPServerType`

Detect MCP server type from tool name and parameters.

**Parameters**:
- `tool_name` (str): MCP tool function name
- `params` (Dict[str, Any]): Tool parameters

**Returns**: `MCPServerType` enum value

**Detection Logic**:
1. Tool name analysis - Common filesystem patterns (read_file, write_file)
2. Parameter structure - Presence of specific keys (command → bash, repo → git)
3. Context clues - API references (github.com → GITHUB)

**Example**:
```python
from mcp_server_detector import detect_mcp_server, MCPServerType

# Filesystem detection
server = detect_mcp_server("read_file", {"path": "src/main.py"})
assert server == MCPServerType.FILESYSTEM

# Git detection
server = detect_mcp_server("git_status", {"repo": "/project"})
assert server == MCPServerType.GIT

# Bash detection
server = detect_mcp_server("run_command", {"command": "pytest tests/"})
assert server == MCPServerType.BASH

# Unknown
server = detect_mcp_server("unknown_tool", {})
assert server == MCPServerType.UNKNOWN
```

### Tool Name Patterns

Detection patterns for each server type:

**Filesystem**:
- `read_file`, `write_file`, `list_files`, `file_operations`

**Git**:
- `git_*` prefix patterns (git_status, git_commit, git_push)
- Parameters: `repo`, `repository`, `branch`

**GitHub**:
- `github_*`, `create_issue`, `get_repo`, `list_prs`
- Parameters: `repo`, `owner`, `pull_request`
- Tool description contains "github"

**Python**:
- `python_execute`, `evaluate_code`, `python_repl`
- Parameters: `code`, `script`

**Bash**:
- `run_command`, `execute_sh`, `shell_execute`
- Parameters: `command`, `shell_command`

**Web**:
- `search_web`, `fetch_url`, `http_get`
- Parameters: `url`, `domain`, `query`

### Used By

- `mcp_security_enforcer.py` hook - Apply server-specific validation rules
- `mcp_permission_validator.py` - Route to appropriate validator

### Related

- GitHub Issue #95 (MCP Server Security)
- [MCP-SECURITY.md](MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/mcp_security_enforcer.py` - Hook implementation


## 38. auto_approval_engine.py (489 lines, v3.38.0)

**Purpose**: Core engine for MCP tool auto-approval with 6-layer defense-in-depth validation

**Issue**: #73 (MCP Auto-Approval), #98 (PreToolUse Consolidation)

### Classes

#### `AutoApprovalEngine`

Main engine for tool approval decisions with comprehensive security validation.

**Methods**:

##### `evaluate_tool_call(tool_name: str, params: Dict[str, Any]) -> ApprovalDecision`

Evaluate whether a tool call should be auto-approved.

**Parameters**:
- `tool_name` (str): Name of the MCP tool to evaluate
- `params` (Dict[str, Any]): Tool parameters/arguments

**Returns**: `ApprovalDecision` dataclass with fields:
- `approved` (bool): Whether call is approved
- `reason` (str): Explanation of decision
- `layer_violations` (List[str]): Failed validation layers
- `confidence_score` (float): 0.0-1.0 confidence in decision

**Validation Layers** (defense-in-depth):
1. **Subagent Context** - Only auto-approve if running as subagent (`CLAUDE_AGENT_NAME` set)
2. **User Consent** - Verify user has opted in via `MCP_AUTO_APPROVE` env var
3. **Agent Whitelist** - Check if current agent is in allowed list
4. **Tool Whitelist** - Validate tool name against approved tools list
5. **Parameter Validation** - Check parameters for dangerous patterns
6. **Circuit Breaker** - Auto-disable after repeated denials

**Example**:
```python
from auto_approval_engine import AutoApprovalEngine

engine = AutoApprovalEngine()

# Approve safe tool call
decision = engine.evaluate_tool_call(
    "Read",
    {"file_path": "src/main.py"}
)
assert decision.approved == True
assert "parameter validation passed" in decision.reason

# Deny dangerous tool call
decision = engine.evaluate_tool_call(
    "Bash",
    {"command": "rm -rf /"}
)
assert decision.approved == False
assert "parameter validation" in decision.layer_violations
```

### Related

- GitHub Issue #73 (MCP Auto-Approval for Subagent Tool Calls)
- GitHub Issue #98 (PreToolUse Hook Consolidation)
- `plugins/autonomous-dev/hooks/pre_tool_use.py` - Standalone hook implementation
- `plugins/autonomous-dev/hooks/unified_pre_tool_use.py` - Library-based hook
- `docs/TOOL-AUTO-APPROVAL.md` - User-facing documentation

---

## 39. tool_validator.py (900 lines, v3.40.0)

**Purpose**: Tool call validation with whitelist/blacklist, injection detection, path containment validation, and parameter analysis

**Issue**: #73 (MCP Auto-Approval), #98 (PreToolUse Consolidation)

**New in v3.40.0**: Path extraction and containment validation for destructive shell commands (rm, mv, cp, chmod, chown) - prevents CWE-22 (path traversal) and CWE-59 (symlink attacks) when files are modified.

### Classes

#### `ToolValidator`

Validates MCP tool calls against security policies with path-aware containment validation for destructive commands.

**Methods**:

##### `validate_tool(tool_name: str, params: Dict[str, Any]) -> ValidationResult`

Comprehensive validation of tool calls.

**Parameters**:
- `tool_name` (str): Tool name to validate
- `params` (Dict[str, Any]): Tool parameters

**Returns**: `ValidationResult` dataclass with:
- `valid` (bool): Overall validation result
- `violations` (List[str]): Security violations found
- `severity` (str): "critical", "high", "medium", "low", "none"
- `recommendations` (List[str]): How to fix violations

**Validation Checks**:
1. **Whitelist Check** - Tool must be in approved list
2. **Blacklist Check** - Tool must not be explicitly denied
3. **Path Traversal** - Detect `..`, `/etc/passwd`, symlink attacks
4. **Injection Patterns** - Detect shell metacharacters, command chaining
5. **Path Containment** (NEW v3.40.0) - Validate extracted paths are within project boundaries
6. **Sensitive Files** - Block access to `.env`, `.ssh`, secrets
7. **SSRF Detection** - Detect localhost, private IPs, metadata services
8. **Parameter Size** - Reject suspiciously large parameters

**Example**:
```python
from tool_validator import ToolValidator, ValidationResult

validator = ToolValidator()

# Valid tool call
result = validator.validate_tool("Read", {"file_path": "src/main.py"})
assert result.valid == True
assert result.severity == "none"

# Invalid - path traversal
result = validator.validate_tool(
    "Read",
    {"file_path": "../../.env"}
)
assert result.valid == False
assert result.severity == "critical"
assert any("path traversal" in v for v in result.violations)

# Valid - rm within project boundaries
result = validator.validate_bash_command("rm src/temp.py")
assert result.approved == True

# Invalid - rm outside project
result = validator.validate_bash_command("rm ../../../etc/passwd")
assert result.approved == False
assert "path traversal" in result.reason
```

##### `_extract_paths_from_command(command: str) -> List[str]` (NEW v3.40.0)

Extract file paths from destructive shell commands for containment validation.

**Purpose**: Identifies files that will be modified by rm/mv/cp/chmod/chown commands so they can be validated against project boundaries.

**Supported Commands**:
- `rm` - Remove files/directories
- `mv` - Move files/directories
- `cp` - Copy files/directories
- `chmod` - Change file permissions
- `chown` - Change file ownership

**Parameters**:
- `command` (str): Shell command string to parse

**Returns**: List of file paths extracted from command, or empty list if:
- Command is non-destructive (ls, cat, etc.)
- Command contains wildcards (asterisk or question mark) - cannot validate at static analysis time
- Command is empty or malformed (unclosed quotes)

**Behavior**:
- Uses shlex.split() for proper quote/escape handling
- Filters out flags (arguments starting with dash)
- Skips mode/ownership arguments for chmod/chown
- Gracefully handles malformed commands (returns empty list)

**Security Notes**:
- Wildcard commands return empty list (conservative approach - cannot validate)
- Symlinks are resolved and validated separately by _validate_path_containment()
- Only destructive commands checked (non-destructive commands skip validation)

**Example**:
```python
validator = ToolValidator()

# Extract paths from rm command
paths = validator._extract_paths_from_command("rm file.txt")
# Returns: ["file.txt"]

# Extract multiple paths from mv
paths = validator._extract_paths_from_command("mv src.txt dst.txt")
# Returns: ["src.txt", "dst.txt"]

# Wildcards skip validation (conservative)
paths = validator._extract_paths_from_command("rm *.txt")
# Returns: []  # Cannot validate wildcard expansion

# Non-destructive commands skip validation
paths = validator._extract_paths_from_command("ls file.txt")
# Returns: []  # No containment validation needed
```

##### `_validate_path_containment(paths: List[str], project_root: Path) -> Tuple[bool, Optional[str]]` (NEW v3.40.0)

Validate that all paths are contained within project boundaries.

**Purpose**: Prevents CWE-22 (path traversal) and CWE-59 (symlink attacks) by ensuring destructive operations only affect files within the project.

**Validation Checks**:
- **Path Traversal** - Reject traversal style escapes like ../../../etc/passwd
- **Absolute Paths** - Reject /etc/passwd outside project
- **Symlinks** - Reject symlinks pointing outside project
- **Home Directory** - Reject ~/ expansion (except whitelisted ~/.claude/)
- **Invalid Characters** - Reject paths with null bytes or newlines

**Parameters**:
- `paths` (List[str]): File paths to validate
- `project_root` (Path): Project root directory (containment boundary)

**Returns**: Tuple of:
- (True, None) - All paths valid and contained
- (False, error_message) - First invalid path with description

**Special Cases**:
- **Empty list**: Always valid (no paths to validate)
- **~/.claude/**: Whitelisted for Claude Code system files
- **Other ~/ paths**: Rejected (outside project boundaries)

**Security Features**:
- Checks for null bytes and newlines - injection risk
- Expands tilde to absolute path before validation
- Resolves symlinks and validates target location
- Uses is_relative_to() for containment check (Python 3.9+) with fallback for 3.8
- Distinguishes between path traversal vs absolute path violations in error messages

**Example**:
```python
validator = ToolValidator()
project_root = Path("/tmp/project")  # Example project root

# Valid - relative path within project
is_valid, error = validator._validate_path_containment(
    ["src/main.py"],
    project_root
)
assert is_valid == True
assert error is None

# Invalid - path traversal attempt
is_valid, error = validator._validate_path_containment(
    ["../../../etc/passwd"],
    project_root
)
assert is_valid == False
assert "path traversal" in error

# Invalid - absolute path outside project
is_valid, error = validator._validate_path_containment(
    ["/etc/passwd"],
    project_root
)
assert is_valid == False
assert "absolute path" in error and "outside" in error

# Invalid - symlink to outside
is_valid, error = validator._validate_path_containment(
    ["link_to_etc"],
    project_root
)
assert is_valid == False
assert "symlink" in error

# Whitelisted - .claude directory
is_valid, error = validator._validate_path_containment(
    ["~/.claude/config.json"],
    project_root
)
assert is_valid == True

# Invalid - other home directory paths
is_valid, error = validator._validate_path_containment(
    ["~/.ssh/id_rsa"],
    project_root
)
assert is_valid == False
assert "home directory" in error
```

### Integration with validate_bash_command()

When validate_bash_command() processes a command:
1. Checks command against blacklist
2. NEW v3.40.0: Extracts paths from destructive commands
3. NEW v3.40.0: Validates paths are contained within project boundaries
4. Checks for command injection patterns
5. Checks against whitelist
6. Denies by default (conservative approach)

This ensures commands like rm ../../../etc/passwd are blocked before execution, even if they pass other validation layers.

### Related

- GitHub Issue #73 (MCP Auto-Approval)
- GitHub Issue #98 (PreToolUse Consolidation)
- auto_approval_engine.py - Uses validator in approval decision
- docs/TOOL-AUTO-APPROVAL.md - Security validation documentation
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- CWE-59: Improper Link Resolution Before File Access

---

## 40. unified_pre_tool_use.py (467 lines, v3.38.0)

**Purpose**: Library-based PreToolUse hook implementation combining auto-approval and security validation

**Issue**: #95 (MCP Security), #98 (PreToolUse Consolidation)

### Main Class

#### `UnifiedPreToolUseHook`

Main hook handler that coordinates auto-approval and security validation.

**Methods**:

##### `on_pre_tool_use(tool_call: Dict[str, Any]) -> Dict[str, Any]`

Claude Code PreToolUse lifecycle hook handler.

**Parameters**:
- `tool_call` (Dict[str, Any]): Tool call with `tool_name` and `tool_input`

**Returns**: Hook response dict with:
- `hookSpecificOutput`: Dict containing:
  - `hookEventName`: "PreToolUse"
  - `permissionDecision`: "allow" or "deny"
  - `permissionDecisionReason`: Explanation

**Workflow**:
1. Parse tool call from JSON input
2. Run auto-approval engine
3. If not auto-approved, run security validation
4. Log decision to audit trail
5. Return decision to Claude Code

**Example**:
```python
from unified_pre_tool_use import UnifiedPreToolUseHook

hook = UnifiedPreToolUseHook()

# Tool call
tool_call = {
    "tool_name": "Bash",
    "tool_input": {"command": "pytest tests/"}
}

# Get decision
response = hook.on_pre_tool_use(tool_call)
assert response["hookSpecificOutput"]["permissionDecision"] == "allow"
```

### Integration

This library is used by both:
1. `plugins/autonomous-dev/hooks/pre_tool_use.py` - Standalone shell script wrapper
2. Direct Python imports in custom hooks

### Related

- GitHub Issue #95 (MCP Server Security)
- GitHub Issue #98 (PreToolUse Consolidation)
- `auto_approval_engine.py` - Auto-approval logic
- `tool_validator.py` - Security validation
- `plugins/autonomous-dev/hooks/pre_tool_use.py` - Standalone wrapper
- `docs/TOOL-AUTO-APPROVAL.md` - Usage guide
---

## 41. settings_merger.py (432 lines, v3.39.0)

**Purpose**: Merge template settings.local.json with user settings while preserving customizations

**Issue**: #98 (Settings Merge on Marketplace Sync)

### Main Class

#### `SettingsMerger`

Handles merging template settings with user settings during marketplace sync operations.

**Constructor**:
```python
def __init__(self, project_root: str)
```

**Parameters**:
- `project_root` (str): Project root directory for path validation

**Methods**:

##### `merge_settings(template_path: Path, user_path: Path, write_result: bool = True) -> MergeResult`

Merge template settings with user settings, preserving customizations.

**Parameters**:
- `template_path` (Path): Path to template settings.local.json
- `user_path` (Path): Path to user settings.local.json
- `write_result` (bool): Whether to write merged settings (False for dry-run)

**Returns**: `MergeResult` dataclass with:
- `success` (bool): Whether merge succeeded
- `message` (str): Human-readable result message
- `settings_path` (Optional[str]): Path to merged settings file
- `hooks_added` (int): Number of hooks added from template
- `hooks_preserved` (int): Number of existing hooks preserved
- `details` (Dict[str, Any]): Additional context (errors, warnings)

**Workflow**:
1. Validate both paths (security: CWE-22, CWE-59)
2. Read template and user settings files
3. Deep merge dictionaries (nested objects preserved)
4. Merge hooks by lifecycle event (avoid duplicates)
5. Atomic write to user path (secure permissions 0o600)
6. Audit log the operation

**Example**:
```python
from autonomous_dev.lib.settings_merger import SettingsMerger

merger = SettingsMerger(project_root="/path/to/project")

# Merge template with user settings
result = merger.merge_settings(
    template_path=Path("templates/settings.local.json"),
    user_path=Path(".claude/settings.local.json"),
    write_result=True
)

if result.success:
    print(f"Merged {result.hooks_added} new hooks")
    print(f"Preserved {result.hooks_preserved} existing hooks")
else:
    print(f"Merge failed: {result.message}")
```

### Data Classes

#### `MergeResult`

Result of settings merge operation.

**Attributes**:
- `success` (bool): Whether merge succeeded
- `message` (str): Human-readable result message
- `settings_path` (Optional[str]): Path to merged settings file (None if merge failed)
- `hooks_added` (int): Number of hooks added from template
- `hooks_preserved` (int): Number of existing hooks preserved
- `details` (Dict[str, Any]): Additional result details (errors, warnings)

### Security Features

**Path Validation**:
- Validates both template and user paths against project root
- Blocks path traversal attacks (CWE-22)
- Rejects symlinks and suspicious paths (CWE-59)
- Uses `security_utils.validate_path()` for comprehensive validation

**Atomic Writes**:
- Creates temp file in same directory as target
- Sets secure permissions (0o600 - user read/write only)
- Atomic rename to target path (POSIX-safe)
- Cleans up temp files on error

**Audit Logging**:
- All operations logged via `security_utils.audit_log()`
- Tracks merge success/failure with context
- Records path validation decisions
- Enables security audits and compliance

**Deep Merge Logic**:
- Nested dictionaries merged recursively (preserves structure)
- Lists replaced, not merged (prevents duplicate items)
- Special handling for hooks: merge by lifecycle event
- User customizations always preserved

### Integration with sync_dispatcher.py

Used by `SyncDispatcher.sync_marketplace()` to automatically merge PreToolUse hooks:

**Workflow**:
1. Marketplace sync starts
2. Locate plugin's template settings.local.json
3. Create SettingsMerger instance
4. Call `merge_settings()` with template and user paths
5. Record merge result in `SyncResult.settings_merged`
6. Continue sync (non-blocking if merge fails)

**Example**:
```python
from autonomous_dev.lib.sync_dispatcher import SyncDispatcher

dispatcher = SyncDispatcher(project_root="/path/to/project")
result = dispatcher.sync_marketplace(installed_plugins_path)

if result.settings_merged and result.settings_merged.success:
    print(f"Settings synced: {result.settings_merged.hooks_added} hooks added")
```

### Error Handling

All errors are graceful and non-blocking:

**Template Errors**:
- Template path validation fails: Return MergeResult with `success=False`
- Template file not found: Return MergeResult with `success=False`
- Template JSON invalid: Return MergeResult with `success=False`

**User Settings Errors**:
- User path validation fails: Return MergeResult with `success=False`
- User settings JSON invalid: Return MergeResult with `success=False`
- User settings file missing: Create new file from template (success=True)

**Write Errors**:
- Cannot create parent directories: Return MergeResult with `success=False`
- File write fails: Return MergeResult with `success=False` (temp file cleaned up)
- Permission denied: Return MergeResult with `success=False`

**Note**: Marketplace sync continues even if settings merge fails (non-blocking design)

### Testing

**Test Coverage**: 25 tests (15 core + 4 edge cases + 3 security + 3 integration)
- Core functionality tests for merge operations
- Edge case handling (missing files, invalid JSON, path errors)
- Security tests (path traversal, symlink attacks, validation)
- Integration tests with sync_dispatcher

### Related

- GitHub Issue #98 (Settings Merge on Marketplace Sync)
- `sync_dispatcher.py` - Uses SettingsMerger in sync_marketplace() method
- `security_utils.py` - Provides path validation and audit logging
- `docs/TOOL-AUTO-APPROVAL.md` - PreToolUse hook configuration reference
- `plugins/autonomous-dev/templates/settings.local.json` - Default template

---

## 42. staging_manager.py (340 lines, v3.41.0+)

**Purpose**: Manage staging directory for GenAI-first installation system

**Issue**: #106 (GenAI-first installation system)

### Overview

The staging manager handles staged plugin files during the GenAI-first installation workflow. It validates staging directories, lists files with metadata, detects conflicts with target installations, and manages cleanup operations.

**Key Features**:
- Staging directory validation and initialization
- File listing with SHA256 hashes and metadata
- Conflict detection (file exists in both locations with different content)
- Security validation (path traversal prevention, symlink detection)
- Selective and full cleanup operations

### Main Class

#### `StagingManager`

Manages a staging directory for plugin files.

**Constructor**:
```python
def __init__(self, staging_dir: Path | str)
```

**Parameters**:
- `staging_dir` (Path | str): Path to staging directory (created if doesn't exist)

**Raises**:
- `ValueError`: If path is a file (not a directory)

**Methods**:

##### `list_files() -> List[Dict[str, Any]]`

List all files in staging directory with metadata.

**Returns**: List of dicts with keys:
- `path` (str): Relative path from staging directory (normalized)
- `size` (int): File size in bytes
- `hash` (str): SHA256 hex digest

##### `get_file_hash(relative_path: str) -> Optional[str]`

Get SHA256 hash of a specific file.

**Parameters**:
- `relative_path` (str): Relative path from staging directory

**Returns**: SHA256 hex digest or None if file not found

**Raises**:
- `ValueError`: If path contains traversal or symlinks

##### `detect_conflicts(target_dir: Path | str) -> List[Dict[str, Any]]`

Detect conflicts between staged files and target directory.

A conflict occurs when:
- File exists in both locations
- File content differs (different hashes)

**Parameters**:
- `target_dir` (Path | str): Target directory to compare against

**Returns**: List of conflict dicts with file, reason, staging_hash, target_hash

##### `cleanup() -> None`

Remove all files and directories from staging directory.

##### `cleanup_files(file_paths: List[str]) -> None`

Remove specific files from staging directory.

**Parameters**:
- `file_paths` (List[str]): Relative paths to remove

##### `is_secure() -> bool`

Check if staging directory has secure permissions.

**Returns**: True if readable and writable

##### `validate_path(relative_path: str) -> None`

Validate path for security issues.

**Raises**:
- `ValueError`: If path contains traversal (..), is absolute, or is a symlink

### Security Features

**Path Traversal Prevention**:
- Blocks paths containing `..`
- Rejects absolute paths
- Validates paths are within staging directory (CWE-22)

**Symlink Detection**:
- Prevents symlink-based attacks (CWE-59)
- Validates resolved path is within staging directory

**File Hashing**:
- SHA256 for content comparison
- Enables conflict detection without loading full file contents

### Testing

**Test Coverage**: 18 tests
- Directory initialization and validation
- File listing with correct metadata
- Conflict detection (same content, different content, missing files)
- Path traversal prevention (.. attempts, absolute paths)
- Symlink detection and rejection
- Cleanup operations (full and selective)
- Security permission checks

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `protected_file_detector.py` - Identifies files to preserve during installation
- `installation_analyzer.py` - Analyzes installation type and strategy
- `install_audit.py` - Audit logging for installation operations
- `copy_system.py` - Performs actual file copying to target

---

---

## 47. settings_generator.py (749 lines, v3.43.0+)

**Purpose**: Generate settings.local.json with specific command patterns and comprehensive deny list

**Issue**: #115 (Settings Generator - NO wildcards, specific patterns only)

### Overview

The settings generator creates `.claude/settings.local.json` with security-first design:
- **Specific command patterns only** - NO wildcards like `Bash(*)`
- **Comprehensive deny list** - Blocks dangerous operations (rm -rf, sudo, eval, etc.)
- **Command auto-discovery** - Scans `plugins/autonomous-dev/commands/*.md`
- **User customization preservation** - Merges with existing settings during upgrades
- **Atomic writes** - Secure permissions (0o600)

**Key Features**:
- Generates specific patterns: `Bash(git:*)`, `Bash(pytest:*)`, `Bash(python:*)`
- Auto-discovers slash commands from plugin directory
- Preserves user customizations during marketplace sync
- Secure file operations with path validation
- Comprehensive audit logging

### Main Class

#### `SettingsGenerator`

Generates settings.local.json with command-specific patterns and security controls.

**Constructor**:
```python
def __init__(self, plugin_dir: Path)
```

**Parameters**:
- `plugin_dir` (Path): Path to plugin directory (plugins/autonomous-dev)

**Raises**:
- `SettingsGeneratorError`: If plugin_dir or commands/ directory not found

**Attributes**:
- `plugin_dir` (Path): Plugin root directory
- `commands_dir` (Path): Commands directory (plugin_dir/commands)
- `discovered_commands` (List[str]): Auto-discovered command names
- `_validated` (bool): Whether initialization succeeded

**Methods**:

##### `discover_commands() -> List[str]`

Discover slash commands from `plugins/autonomous-dev/commands/*.md` files.

**Returns**: List of command names (without leading slash)

**Example**:
```python
generator = SettingsGenerator(Path("plugins/autonomous-dev"))
commands = generator.discover_commands()
# Returns: ['auto-implement', 'batch-implement', 'align-project', ...]
```

**Validation**:
- Command names must match pattern: `^[a-z][a-z0-9-]*$`
- Invalid names logged and skipped
- Prevents command injection attacks

##### `build_command_patterns() -> List[str]`

Build allow patterns from discovered commands and safe operations.

**Returns**: List of allow patterns

**Includes**:
- **File operations**: `Read(**)`, `Write(**)`, `Edit(**)`, `Glob(**)`, `Grep(**)`
- **Safe Bash patterns**: `Bash(git:*)`, `Bash(python:*)`, `Bash(pytest:*)`, `Bash(pip:*)`
- **Discovered commands**: `Task(researcher)`, `Task(planner)`, etc.
- **Standalone tools**: `Task`, `WebFetch`, `WebSearch`, `TodoWrite`, `NotebookEdit`

**Example Output**:
```python
[
    "Read(**)",
    "Write(**)",
    "Bash(git:*)",
    "Bash(pytest:*)",
    "Task(researcher)",
    "Task(planner)",
    ...
]
```

##### `build_deny_list() -> List[str]` (static method)

Build comprehensive deny list of dangerous operations.

**Returns**: List of deny patterns

**Blocks**:
- **Destructive operations**: `Bash(rm:-rf*)`, `Bash(shred:*)`, `Bash(dd:*)`
- **Privilege escalation**: `Bash(sudo:*)`, `Bash(chmod:*)`, `Bash(chown:*)`
- **Code execution**: `Bash(eval:*)`, `Bash(exec:*)`, `Bash(*|*sh*)`
- **Network tools**: `Bash(nc:*)`, `Bash(curl:*|*sh*)`
- **Dangerous git**: `Bash(git:*--force*)`, `Bash(git:*reset*--hard*)`
- **Package publishing**: `Bash(npm:publish*)`, `Bash(pip:upload*)`
- **Sensitive files**: `Read(./.env)`, `Read(~/.ssh/**)`, `Write(/etc/**)`

**Example**:
```python
deny_list = SettingsGenerator.build_deny_list()
# Static method - no instance needed
```

##### `generate_settings(merge_with: Optional[Dict] = None) -> Dict`

Generate complete settings dictionary with patterns and metadata.

**Parameters**:
- `merge_with` (Optional[Dict]): Existing settings to merge with (preserves user customizations)

**Returns**: Settings dictionary ready for JSON serialization

**Structure**:
```python
{
    "permissions": {
        "allow": [...],
        "deny": [...]
    },
    "hooks": {...},  # Preserved from merge_with
    "generated_by": "autonomous-dev",
    "version": "1.0.0",
    "timestamp": "2025-12-12T10:30:00Z"
}
```

##### `write_settings(output_path: Path, merge_existing: bool = False, backup: bool = False) -> GeneratorResult`

Write settings.local.json to disk with optional merge and backup.

**Parameters**:
- `output_path` (Path): Path to write settings.local.json
- `merge_existing` (bool): Whether to merge with existing settings (preserves customizations)
- `backup` (bool): Whether to backup existing file before overwrite

**Returns**: `GeneratorResult` dataclass

**Workflow**:
1. Validate output path (security checks)
2. Create .claude/ directory if missing (with secure permissions)
3. Backup existing file if requested
4. Read and merge with existing settings if requested
5. Generate new settings dictionary
6. Atomic write with secure permissions (0o600)
7. Audit log the operation

**Example**:
```python
from pathlib import Path
from autonomous_dev.lib.settings_generator import SettingsGenerator

generator = SettingsGenerator(Path("plugins/autonomous-dev"))

# Fresh install
result = generator.write_settings(
    output_path=Path(".claude/settings.local.json")
)

# Upgrade with merge and backup
result = generator.write_settings(
    output_path=Path(".claude/settings.local.json"),
    merge_existing=True,
    backup=True
)

if result.success:
    print(f"Settings written: {result.patterns_added} patterns")
    print(f"Preserved: {result.patterns_preserved} user patterns")
```


##### `validate_permission_patterns(settings: Dict) -> ValidationResult` (v3.44.0+, Issue #114)

Validate permission patterns in settings for dangerous wildcards and missing deny list.

**Parameters**:
- `settings` (Dict): Settings dictionary to validate

**Returns**: `ValidationResult` dataclass with detected issues

**Detects**:
- **Bash(*) wildcard** → severity "error" (too permissive, approves all Bash commands)
- **Bash(:*) wildcard** → severity "warning" (rare edge case, usually unintended)
- **Missing deny list** → severity "error" (no protection against dangerous commands)
- **Empty deny list** → severity "error" (no protection against dangerous commands)

**Example**:
```python
from settings_generator import validate_permission_patterns

# Settings with dangerous patterns
settings = {
    "permissions": {
        "allow": ["Bash(*)", "Read(**)"],
        "deny": []
    }
}

result = validate_permission_patterns(settings)
if not result.valid:
    for issue in result.issues:
        print(f"{issue.severity.upper()}: {issue.description}")
        # ERROR: Dangerous wildcard pattern detected: Bash(*)
        # ERROR: Deny list is empty - no protection against dangerous commands

# Clean settings
good_settings = {
    "permissions": {
        "allow": ["Bash(git:*)", "Read(**)"],
        "deny": ["Bash(rm:-rf*)", "Bash(sudo:*)"]
    }
}

result = validate_permission_patterns(good_settings)
print(result.valid)  # True
```

**Related**: GitHub Issue #114 (Permission validation during updates)

##### `fix_permission_patterns(user_settings: Dict, template_settings: Optional[Dict] = None) -> Dict` (v3.44.0+, Issue #114)

Fix permission patterns while preserving user customizations.

**Parameters**:
- `user_settings` (Dict): User's existing settings to fix
- `template_settings` (Optional[Dict]): Template settings (unused, for compatibility)

**Returns**: Fixed settings dictionary

**Raises**:
- `ValueError`: If user_settings is None or not a dictionary

**Process**:
1. Preserve user hooks (don't touch)
2. Preserve valid custom allow patterns (non-wildcard patterns)
3. Replace wildcards with specific patterns (Bash(*) → Bash(git:*), Bash(pytest:*), etc.)
4. Add comprehensive deny list if missing
5. Validate result

**Example**:
```python
from settings_generator import fix_permission_patterns

# User settings with dangerous wildcards
user_settings = {
    "permissions": {
        "allow": ["Bash(*)", "MyCustomPattern"],  # Has wildcard + custom
        "deny": []
    },
    "hooks": {
        "my_custom_hook": "path/to/hook.py"
    }
}

# Fix patterns
fixed = fix_permission_patterns(user_settings)

# Result preserves customizations:
# - "MyCustomPattern" kept (valid custom pattern)
# - "Bash(*)" replaced with specific patterns
# - Deny list added
# - Hooks preserved
print(fixed["permissions"]["allow"])
# ['MyCustomPattern', 'Bash(git:*)', 'Bash(pytest:*)', 'Read(**)', ...]

print(fixed["hooks"])
# {'my_custom_hook': 'path/to/hook.py'}  # Preserved!
```

**Preservation Logic**:
- **Hooks**: Always preserved (user customization)
- **Valid patterns**: Preserved if not Bash(*) or Bash(:*)
- **Wildcards**: Replaced with safe specific patterns
- **Deny list**: Added if missing (50+ dangerous patterns)

**Related**: GitHub Issue #114 (Permission fixing during updates)

##### `merge_global_settings(global_path: Path, template_path: Path, fix_wildcards: bool = True, create_backup: bool = True) -> Dict[str, Any]` (v3.46.0+, Issue #117)

Merge global settings preserving user customizations while fixing broken patterns.

**Purpose**: Merge template settings with existing user settings, fixing broken Bash(:*) patterns while preserving user hooks and custom patterns. Used during plugin installation/update to safely merge new patterns.

**Parameters**:
- `global_path` (Path): Path to global settings file (~/.claude/settings.json)
- `template_path` (Path): Path to template file (plugins/autonomous-dev/config/global_settings_template.json)
- `fix_wildcards` (bool): Whether to fix broken wildcard patterns (default: True)
- `create_backup` (bool): Whether to create backup before modification (default: True)

**Returns**: Merged settings dictionary ready for use

**Raises**:
- `SettingsGeneratorError`: If template not found, template invalid JSON, or write fails

**Process**:
1. Validate template exists and is valid JSON
2. Read existing user settings from global_path (if exists)
3. Detect broken patterns in user settings (Bash(:*))
4. Fix broken patterns: Bash(:*) to [Bash(git:*), Bash(python:*), ...]
5. Deep merge: template patterns + user patterns (union)
6. Preserve user hooks completely (never modified)
7. Backup existing file before writing (if create_backup=True)
8. Write merged settings atomically with secure permissions
9. Audit log all operations

**Merge Strategy**:
- **Template**: Source of truth for safe patterns
- **User settings**: Provides customizations and valid patterns
- **Merge result**: Union of all patterns (template + user)
- **User hooks**: Always preserved unchanged
- **Wildcard fix**: Broken patterns replaced, valid patterns kept

**Example**:
```python
from pathlib import Path
from autonomous_dev.lib.settings_generator import SettingsGenerator

generator = SettingsGenerator(Path("plugins/autonomous-dev"))

# Merge global settings with user customizations
merged_settings = generator.merge_global_settings(
    global_path=Path.home() / ".claude" / "settings.json",
    template_path=Path("plugins/autonomous-dev/config/global_settings_template.json"),
    fix_wildcards=True,
    create_backup=True
)

print(f"Merged settings: {merged_settings}")
print(f"Patterns available: {len(merged_settings.get('allowedTools', {}).get('Bash', {}).get('allow_patterns', []))} allows")
```

**Backup Behavior**:
- Creates ~/.claude/settings.json.backup before modifying existing file
- Only creates backup if file exists and will be modified
- Old backup automatically replaced (one backup per merge)
- Corrupted files backed up as .json.corrupted with automatic regeneration

**Error Recovery**:
- **Missing template**: Raises SettingsGeneratorError with helpful message
- **Invalid template JSON**: Raises SettingsGeneratorError with JSON error details
- **Permission denied**: Raises PermissionError (allows testing/handling in caller)
- **Write failure**: Cleans up temp file and raises SettingsGeneratorError
- **Corrupted user file**: Creates .json.corrupted backup and starts fresh

**Security**:
- Atomic writes: Tempfile in same directory + atomic rename prevents corruption
- Secure permissions: 0o600 (user read/write only)
- Path validation: All paths validated against CWE-22 (path traversal), CWE-59 (symlinks)
- Audit logging: All operations logged with context

**Related**: GitHub Issue #117 (Global Settings Configuration - Merge Broken Patterns)

### Data Classes (Issue #114)

#### `PermissionIssue` (v3.44.0+)

Details about a detected permission issue.

**Attributes**:
- `issue_type` (str): Type of issue (wildcard_pattern, missing_deny_list, empty_deny_list, outdated_pattern)
- `description` (str): Human-readable description of the issue
- `pattern` (str): Pattern affected by this issue (empty string if N/A)
- `severity` (str): Severity level ("warning" or "error")

**Example**:
```python
issue = PermissionIssue(
    issue_type="wildcard_pattern",
    description="Dangerous wildcard pattern detected: Bash(*)",
    pattern="Bash(*)",
    severity="error"
)
```

#### `ValidationResult` (v3.44.0+)

Result of permission validation.

**Attributes**:
- `valid` (bool): Whether validation passed (True if no issues)
- `issues` (List[PermissionIssue]): List of detected issues
- `needs_fix` (bool): Whether fixes should be applied

**Example**:
```python
from settings_generator import validate_permission_patterns

settings = {"permissions": {"allow": ["Bash(*)"], "deny": []}}
result = validate_permission_patterns(settings)

if not result.valid:
    print(f"Found {len(result.issues)} issues:")
    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.description}")
    if result.needs_fix:
        print("Automatic fix available via fix_permission_patterns()")
```


### Data Classes

#### `GeneratorResult`

Result of settings generation operation.

**Attributes**:
- `success` (bool): Whether generation succeeded
- `message` (str): Human-readable result message
- `settings_path` (Optional[str]): Path to generated settings file (None if failed)
- `patterns_added` (int): Number of new patterns added
- `patterns_preserved` (int): Number of user patterns preserved (upgrade only)
- `denies_added` (int): Number of deny patterns added
- `details` (Dict[str, Any]): Additional result details

### Security Features

**NO Wildcards**:
- Never uses `Bash(*)` (too permissive)
- Always uses specific patterns: `Bash(git:*)`, `Bash(pytest:*)`
- Prevents accidental approval of dangerous commands

**Comprehensive Deny List**:
- 50+ deny patterns blocking dangerous operations
- Covers CWE-78 (command injection), privilege escalation, data destruction
- Blocks piping to shell: `Bash(*|*sh*)`, `Bash(*|*bash*)`
- Prevents command substitution patterns

**Path Validation**:
- Validates output path against project root (CWE-22)
- Rejects symlinks and suspicious paths (CWE-59)
- Uses `security_utils.validate_path()` for comprehensive validation

**Atomic Writes**:
- Creates temp file in same directory as target
- Sets secure permissions (0o600 - user read/write only)
- Atomic rename to target path (POSIX-safe)
- Cleans up temp files on error

**Audit Logging**:
- All operations logged via `security_utils.audit_log()`
- Tracks generation success/failure with context
- Records merge operations and pattern counts
- Enables security audits and compliance

### Integration

**Used By**:
- `/setup` command - Fresh installation
- `/sync` command - Marketplace sync with merge
- Installation system - Auto-generates during plugin install

**Workflow in Installation**:
1. Plugin installed to `~/.config/claude/installed_plugins/`
2. SettingsGenerator discovers commands from plugin
3. Generates settings.local.json with specific patterns
4. Merges with existing user settings (preserves customizations)
5. Writes to `.claude/settings.local.json` with secure permissions

### Testing

**Test Coverage**: 85 tests (56 unit + 29 integration)

**Unit Tests** (`tests/unit/lib/test_settings_generator.py`):
- Command discovery and validation (12 tests)
- Pattern building (allow and deny lists) (8 tests)
- Settings generation and merge logic (15 tests)
- Path validation and security (10 tests)
- Error handling and edge cases (11 tests)

**Integration Tests** (`tests/integration/test_install_settings_generation.py`):
- End-to-end settings generation (8 tests)
- Merge with existing settings (7 tests)
- Backup and rollback scenarios (6 tests)
- Permission and security validation (8 tests)

### Related

- GitHub Issue #115 (Settings Generator - NO wildcards)
- `settings_merger.py` - Merges template settings during marketplace sync
- `security_utils.py` - Provides path validation and audit logging
- `docs/TOOL-AUTO-APPROVAL.md` - Tool approval configuration reference
- `plugins/autonomous-dev/templates/settings.default.json` - Default template with safe patterns


## 43. protected_file_detector.py (316 lines, v3.41.0+)

**Purpose**: Detect user artifacts and protected files during installation

**Issue**: #106 (GenAI-first installation system)

### Overview

The protected file detector identifies files that should NOT be overwritten during installation. This includes:
- User configuration files (.env, PROJECT.md)
- State files (batch state, session state)
- Custom hooks created by users
- Modified plugin files (detected by hash comparison)

**Key Features**:
- Always-protected file list (hardcoded critical files)
- Custom hook detection (glob patterns)
- Plugin default comparison (hash-based)
- Flexible glob pattern matching
- File categorization (config, state, custom_hook, modified_plugin)

### Class

#### `ProtectedFileDetector`

Detects files that should be protected during installation.

**Constructor**:
```python
def __init__(
    self,
    additional_patterns: Optional[List[str]] = None,
    plugin_defaults: Optional[Dict[str, str]] = None
)
```

**Parameters**:
- `additional_patterns` (Optional[List[str]]): Extra glob patterns to protect
- `plugin_defaults` (Optional[Dict[str, str]]): Dict mapping file paths to their default SHA256 hashes

**Attributes**:
- `ALWAYS_PROTECTED` (List[str]): Always-protected files
- `PROTECTED_PATTERNS` (List[str]): Default glob patterns

### Methods

##### `detect_protected_files(project_dir: Path | str) -> List[Dict[str, Any]]`

Identify all protected files in a project directory.

**Parameters**:
- `project_dir` (Path | str): Path to project directory

**Returns**: List of protected file dicts with file, category, protection_reason, hash

##### `get_protected_patterns() -> List[str]`

Get all protected glob patterns (built-in + custom).

**Returns**: List of glob patterns

##### `has_plugin_default(file_path: str) -> bool`

Check if plugin has a default for this file.

**Parameters**:
- `file_path` (str): File path to check

**Returns**: True if file has a default hash in plugin_defaults

##### `matches_pattern(file_path: str) -> bool`

Check if file path matches any protected pattern.

**Parameters**:
- `file_path` (str): File path to check

**Returns**: True if matches any protected pattern

##### `matches_plugin_default(file_path: Path, relative_path: str) -> bool`

Check if file matches plugin default (unmodified).

**Parameters**:
- `file_path` (Path): Full path to file
- `relative_path` (str): Relative path from project root

**Returns**: True if file content matches default hash

##### `calculate_hash(file_path: Path) -> str`

Calculate SHA256 hash of a file.

**Parameters**:
- `file_path` (Path): Path to file

**Returns**: SHA256 hex digest

### File Categories

**Config Files**: `.env`, `*.env`, `.claude/PROJECT.md` - Never overwritten

**State Files**: `.claude/batch_state.json`, `.claude/session_state.json` - Preserves workflow state

**Custom Hooks**: Files matching `.claude/hooks/custom_*.py` pattern - Never removed

**Modified Plugin Files**: Plugin files with different hashes - Protected to preserve customizations

### Security Features

**Hash-Based Comparison**:
- Compares file content, not timestamps
- Detects modified plugin files even if timestamps change
- Enables reliable conflict detection across machines

**Pattern Matching**:
- fnmatch-style glob patterns
- Flexible protection rules
- Supports wildcards (*, ?, [...])

### Testing

**Test Coverage**: 22 tests

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `staging_manager.py` - Manages staged files
- `installation_analyzer.py` - Analyzes protection impact
- `install_audit.py` - Logs protected file decisions
- `copy_system.py` - Uses protection info for safe copying

---

## 44. installation_analyzer.py (374 lines, v3.41.0+)

**Purpose**: Analyze installation type and recommend installation strategy

**Issue**: #106 (GenAI-first installation system)

### Overview

The installation analyzer examines project state and plugin staging to determine the installation type (fresh, brownfield, or upgrade) and recommend an appropriate installation strategy with risk assessment.

**Key Features**:
- Installation type detection (fresh/brownfield/upgrade)
- Comprehensive conflict analysis
- Risk assessment (low/medium/high)
- Strategy recommendation with action items
- Detailed analysis reports

### Enumerations

#### `InstallationType`

Installation type enumeration.

**Values**:
- `FRESH = "fresh"` - New project with no existing plugin
- `BROWNFIELD = "brownfield"` - Existing project with plugin artifacts
- `UPGRADE = "upgrade"` - Existing plugin being updated

### Main Class

#### `InstallationAnalyzer`

Analyzes installation scenarios and recommends strategies.

**Constructor**:
```python
def __init__(self, project_dir: Path | str)
```

**Parameters**:
- `project_dir` (Path | str): Path to project directory

**Raises**:
- `ValueError`: If project directory doesn't exist

### Methods

##### `detect_installation_type() -> InstallationType`

Determine installation type based on project state.

**Returns**: InstallationType enum value

##### `generate_conflict_report(staging_dir: Path | str) -> Dict[str, Any]`

Generate detailed conflict analysis report.

**Parameters**:
- `staging_dir` (Path | str): Staging directory with new files

**Returns**: Report dict with total_conflicts, conflicts, protected_files, risk_level

##### `recommend_strategy() -> Dict[str, Any]`

Recommend installation strategy based on project state.

**Returns**: Strategy dict with type, strategy, action_items, warnings, approval_required

##### `assess_risk() -> Dict[str, Any]`

Assess installation risk level.

**Returns**: Risk assessment dict with level, factors, conflicts_count, protected_files_count, recommendation

**Risk Levels**:
- `low` - No conflicts, protected files intact
- `medium` - Some conflicts with protected files
- `high` - Many conflicts, potential data loss

##### `generate_analysis_report(staging_dir: Path | str) -> Dict[str, Any]`

Generate comprehensive analysis report combining all analysis.

**Parameters**:
- `staging_dir` (Path | str): Staging directory

**Returns**: Complete analysis report dict

### Integration with GenAI-First Installation

This analyzer is used by the GenAI-first installation system to:

1. **Pre-Analysis Phase**: Analyze project before staging files
2. **Strategy Recommendation**: Recommend installation approach
3. **Risk Assessment**: Identify potential issues
4. **Conflict Resolution**: Guide conflict resolution strategy
5. **Approval Decision**: Determine if human approval required

### Testing

**Test Coverage**: 24 tests

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `staging_manager.py` - Provides conflict detection
- `protected_file_detector.py` - Identifies protected files
- `install_audit.py` - Logs analysis results
- `copy_system.py` - Executes recommended strategy

---

## 45. install_audit.py (493 lines, v3.41.0+)

**Purpose**: Audit logging for GenAI-first installation system

**Issue**: #106 (GenAI-first installation system)

### Overview

The install audit module provides append-only audit logging for installation operations. It tracks installation attempts, protected files, conflicts, resolutions, and outcomes using JSONL format (one JSON object per line). This enables crash recovery, audit trails, and installation reports.

**Key Features**:
- JSONL format (append-only, crash-resistant)
- Unique installation IDs for tracking
- Protected file recording with categorization
- Conflict tracking and resolution logging
- Report generation from audit trail
- Multiple query methods (by ID, by status)

### Data Classes

#### `AuditEntry`

Represents a single audit log entry.

**Constructor**:
```python
def __init__(
    self,
    event: str,
    install_id: str,
    timestamp: Optional[str] = None,
    **kwargs
)
```

**Parameters**:
- `event` (str): Event type
- `install_id` (str): Unique installation ID
- `timestamp` (Optional[str]): ISO 8601 timestamp (auto-generated if None)
- `**kwargs`: Additional event-specific fields

**Methods**:

##### `to_dict() -> Dict[str, Any]`

Convert entry to dictionary for JSON serialization.

**Returns**: Dict with event, install_id, timestamp, and all kwargs

### Main Class

#### `InstallAudit`

Manages audit logging for installations.

**Constructor**:
```python
def __init__(self, audit_file: Path | str)
```

**Parameters**:
- `audit_file` (Path | str): Path to JSONL audit log file

### Methods

##### `start_installation(install_type: str) -> str`

Start a new installation session and generate unique ID.

**Parameters**:
- `install_type` (str): Type of installation ("fresh", "brownfield", "upgrade")

**Returns**: Unique installation ID (UUID format)

##### `log_success(install_id: str, files_copied: int, **kwargs) -> None`

Log successful installation completion.

**Parameters**:
- `install_id` (str): Installation ID
- `files_copied` (int): Number of files copied
- `**kwargs`: Additional context (duration, etc.)

##### `log_failure(install_id: str, error: str, **kwargs) -> None`

Log installation failure.

**Parameters**:
- `install_id` (str): Installation ID
- `error` (str): Error message
- `**kwargs`: Additional context

##### `record_protected_file(install_id: str, file_path: str, category: str) -> None`

Record a protected file that won't be overwritten.

**Parameters**:
- `install_id` (str): Installation ID
- `file_path` (str): Relative path to protected file
- `category` (str): Protection category

##### `record_conflict(install_id: str, file_path: str, conflict_type: str, **kwargs) -> None`

Record a file conflict during installation.

**Parameters**:
- `install_id` (str): Installation ID
- `file_path` (str): Path to conflicting file
- `conflict_type` (str): Type of conflict
- `**kwargs`: Additional context (hashes, sizes, etc.)

##### `record_conflict_resolution(install_id: str, file_path: str, resolution: str, **kwargs) -> None`

Record how a conflict was resolved.

**Parameters**:
- `install_id` (str): Installation ID
- `file_path` (str): Path to file
- `resolution` (str): Resolution action (skip, overwrite, merge, manual_review)
- `**kwargs`: Additional context

##### `generate_report(install_id: str) -> Dict[str, Any]`

Generate a report for a specific installation.

**Parameters**:
- `install_id` (str): Installation ID

**Returns**: Report dict with install_id, status, duration, protected_files, conflicts, files_copied, summary

##### `export_report(install_id: str, report_file: Path | str) -> None`

Export a report to JSON file.

**Parameters**:
- `install_id` (str): Installation ID
- `report_file` (Path | str): Path to write report JSON

##### `get_all_installations() -> List[Dict[str, Any]]`

Get all installation records from audit log.

**Returns**: List of installation dicts with status, timestamp, type

##### `get_installations_by_status(status: str) -> List[Dict[str, Any]]`

Get installations filtered by status.

**Parameters**:
- `status` (str): "success" or "failure"

**Returns**: List of matching installations

### JSONL Format

The audit log is JSONL (JSON Lines) format - one JSON object per line.

### Security Features

**Path Validation**:
- Validates all file paths to prevent injection
- Blocks paths with suspicious patterns

**Append-Only Design**:
- All entries appended (never modified)
- Supports recovery from crashes
- Enables forensic analysis

**Timestamp Tracking**:
- All entries timestamped (ISO 8601)
- Tracks operation order and duration
- Enables performance analysis

### Testing

**Test Coverage**: 26 tests

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `staging_manager.py` - Triggers conflict logging
- `protected_file_detector.py` - Categorizes protected files
- `installation_analyzer.py` - Analyzes installation strategy
- `copy_system.py` - Executes operations that are logged

## 46. genai_install_wrapper.py (596 lines, v3.42.0+)

**Purpose**: CLI wrapper for setup-wizard Phase 0 GenAI-first installation with JSON output for agent consumption

**Type**: Script utility

**Location**: `plugins/autonomous-dev/scripts/genai_install_wrapper.py`

**Issue**: GitHub Issue #109 (Setup-wizard GenAI integration)

### Overview

Provides CLI interface for setup-wizard Phase 0 (GenAI installation), wrapping core installation libraries with JSON output for intelligent agent decision-making. Enables setup-wizard to use pre-downloaded plugin files with automated conflict resolution and protected file preservation.

### Features

**5 CLI Commands**:
- `check-staging` - Validate staging directory exists
- `analyze` - Analyze installation type (fresh/brownfield/upgrade)
- `execute` - Perform installation with protected file handling
- `cleanup` - Remove staging directory (idempotent)
- `summary` - Generate installation summary report

**Design**:
- JSON output for agent parsing
- Non-blocking error handling (graceful degradation to Phase 1)
- Atomic and idempotent commands (safe to retry)
- Full audit trail via InstallAudit

### Exports

#### Main Functions

##### `check_staging(staging_path: str) -> Dict[str, Any]`

Validate staging directory exists and contains critical directories.

**Parameters**:
- `staging_path` (str): Path to staging directory

**Returns**:
```json
{
  "status": "valid|missing|invalid",
  "staging_path": "...",
  "fallback_needed": bool,
  "missing_dirs": ["..."],
  "message": "..."
}
```

**Purpose**: Detect if Phase 0 can proceed; if missing, skip to Phase 1

##### `analyze_installation_type(project_path: str) -> Dict[str, Any]`

Analyze project state to determine installation type and protected files.

**Parameters**:
- `project_path` (str): Path to project directory

**Returns**:
```json
{
  "type": "fresh|brownfield|upgrade",
  "has_project_md": bool,
  "has_claude_dir": bool,
  "existing_files": ["..."],
  "protected_files": ["..."]
}
```

**Purpose**: Display to user before installation; inform about protected files

**Installation Types**:
- **fresh**: No `.claude/` directory (new installation)
- **brownfield**: Has PROJECT.md or user artifacts (preserve user files)
- **upgrade**: Has existing plugin files (create backups)

##### `execute_installation(staging_path: str, project_path: str, install_type: str) -> Dict[str, Any]`

Execute installation from staging to project with protected file handling.

**Parameters**:
- `staging_path` (str): Path to staging directory
- `project_path` (str): Path to target project directory
- `install_type` (str): "fresh", "brownfield", or "upgrade"

**Returns**:
```json
{
  "status": "success|error",
  "files_copied": int,
  "skipped_files": ["..."],
  "backups_created": ["..."],
  "error": "..."
}
```

**Purpose**: Perform actual installation from staging to project

**Behavior**:
- Validates install_type parameter
- Validates staging directory exists
- Creates project directory if needed
- Detects protected files (ALWAYS_PROTECTED list + user artifacts)
- Logs protected files in audit trail
- Uses CopySystem with appropriate conflict strategy
- Records installation in audit log

**Conflict Strategies**:
- **brownfield/fresh**: `skip` - Do not overwrite protected files
- **upgrade**: `backup` - Create backups before overwriting

**Error Handling**:
- Returns status: "error" if install_type invalid
- Returns status: "error" if staging does not exist
- Returns status: "error" if copy operation fails
- All errors recorded in audit trail

##### `cleanup_staging(staging_path: str) -> Dict[str, Any]`

Remove staging directory (idempotent - safe to call multiple times).

**Parameters**:
- `staging_path` (str): Path to staging directory

**Returns**:
```json
{
  "status": "success|error",
  "message": "..."
}
```

**Purpose**: Clean up after installation completes

**Idempotent**: Returns success if staging already removed

##### `generate_summary(install_type: str, install_result: Dict[str, Any] | str, project_path: str) -> Dict[str, Any]`

Generate installation summary report with next steps.

**Parameters**:
- `install_type` (str): "fresh", "brownfield", or "upgrade"
- `install_result` (Dict | str): Result from execute_installation (or path to JSON file)
- `project_path` (str): Path to project directory

**Returns**:
```json
{
  "status": "success",
  "summary": {
    "install_type": "...",
    "files_copied": int,
    "skipped_files": int,
    "backups_created": int
  },
  "next_steps": ["..."]
}
```

**Purpose**: Display results to user with recommended next steps

**Next Steps by Type**:
- **fresh**: Configure PROJECT.md, environment variables, test with /status
- **brownfield**: Review protected files, run /align-project, test
- **upgrade**: Review backups, test with /status, run /health-check

##### `main() -> int`

CLI entry point.

**Exit Codes**:
- 0: Success
- 1: Error (missing arguments or command failure)

### Setup-Wizard Phase 0 Workflow

Orchestrates 6-step installation process:

1. **Phase 0.1**: Check for staging directory
   - Call: `check_staging(staging_path)`
   - If fallback_needed: Skip to Phase 1

2. **Phase 0.2**: Analyze installation type
   - Call: `analyze_installation_type(project_path)`
   - Display analysis to user (type, protected files)

3. **Phase 0.3**: Execute installation
   - Call: `execute_installation(staging_path, project_path, type)`
   - Display progress (files copied, skipped, backups)

4. **Phase 0.4**: Validate critical directories exist
   - Verify: plugins/autonomous-dev/commands/
   - Verify: plugins/autonomous-dev/agents/
   - Verify: plugins/autonomous-dev/hooks/
   - Verify: plugins/autonomous-dev/lib/
   - Verify: plugins/autonomous-dev/skills/
   - Verify: .claude/

5. **Phase 0.5**: Generate summary
   - Call: `generate_summary(type, result, project_path)`
   - Display summary and next steps

6. **Phase 0.6**: Cleanup staging
   - Call: `cleanup_staging(staging_path)`
   - Remove staging directory

**Error Recovery**: Any step failure falls back to Phase 1 (manual setup) without data loss

### Integration Points

**Uses**:
- `staging_manager.py`: Check directory validity, list files
- `installation_analyzer.py`: Analyze installation type
- `protected_file_detector.py`: Identify protected files
- `copy_system.py`: Execute file copying with protection
- `install_audit.py`: Record all operations in audit trail

**Called By**:
- `setup-wizard.md` (Phase 0 workflow)

### Security Features

**Path Traversal Prevention (CWE-22)**:
- Validates all paths before operations
- Rejects paths with `../` sequences
- Uses `Path.resolve()` for absolute path validation

**Symlink Attack Prevention (CWE-59)**:
- Detects symlinks via `is_symlink()`
- Validates resolved targets are within project

**Protected File Detection**:
- ALWAYS_PROTECTED list: .env, .claude/PROJECT.md, .claude/batch_state.json, etc.
- Custom detection for user hooks via glob patterns
- Hash-based detection for modified plugin files

**Audit Logging**:
- All operations logged in `.claude/install_audit.jsonl`
- Enables forensic analysis and debugging
- Supports recovery from crashes

### Error Handling

**Graceful Degradation**:
- CLI failures do not interrupt setup wizard
- Phase 0 failures fall back to Phase 1 (manual setup)
- Non-blocking: Errors return status field for agent decision-making

**JSON Error Format**:
```json
{
  "status": "error",
  "error": "Error message",
  "command": "command_name"
}
```

### Usage Examples

**Check Staging**:
```bash
python genai_install_wrapper.py check-staging "$HOME/.autonomous-dev-staging"
```

**Analyze Project**:
```bash
python genai_install_wrapper.py analyze "$(pwd)"
```

**Execute Installation**:
```bash
python genai_install_wrapper.py execute \
  "$HOME/.autonomous-dev-staging" \
  "$(pwd)" \
  "fresh"
```

**Generate Summary**:
```bash
python genai_install_wrapper.py summary \
  "fresh" \
  "/tmp/install_result.json" \
  "$(pwd)"
```

**Cleanup**:
```bash
python genai_install_wrapper.py cleanup "$HOME/.autonomous-dev-staging"
```

### Design Patterns

**Non-Blocking CLI**:
- All commands return JSON
- Failures are graceful (do not crash wrapper)
- Agent can decide next action based on status field

**Atomic Commands**:
- Each command is independent
- Can be retried safely
- Idempotent operations (cleanup can run multiple times)

**Integration Layer**:
- Wraps core installation libraries
- Orchestrates workflow steps
- Provides human-friendly output templates

### Testing

**Test Coverage**: Comprehensive integration tests

**Scenarios**:
- Phase 0 complete workflow (all 6 steps)
- Missing staging directory (fallback to Phase 1)
- Invalid installation types (error handling)
- Protected file preservation (brownfield/upgrade)
- Backup creation for upgrades
- Error recovery and audit trail

### Related

- GitHub Issue #109 (Setup-wizard GenAI integration)
- `setup-wizard.md` - Phase 0 workflow documentation
- `staging_manager.py` - Directory validation and file listing
- `installation_analyzer.py` - Installation type detection
- `protected_file_detector.py` - Protected file identification
- `copy_system.py` - File copying with protection
- `install_audit.py` - Audit logging and reporting

---

## 49. configure_global_settings.py (CLI Wrapper, v3.46.0+, Issue #116)

**Purpose**: Configure fresh installs and upgrades with ~/.claude/settings.json permission patterns

**Called By**: `install.sh` during bootstrap Phase 1 (fresh install, updates, upgrades)

**Status**: Production (integrated into install.sh bootstrap workflow)

### Overview

CLI wrapper for `SettingsGenerator.merge_global_settings()`. Creates or updates `~/.claude/settings.json` with correct permission patterns for Claude Code 2.0. Handles both fresh installs (create from template) and upgrades (preserve user customizations while fixing broken patterns).

### Key Features

1. **Fresh Install**: Creates `~/.claude/settings.json` from template on first install
2. **Upgrade Path**: Preserves user customizations while fixing broken `Bash(:*)` patterns
3. **Non-Blocking**: Always exits 0 for graceful degradation (installation continues even on errors)
4. **Backup Safety**: Creates timestamped backup before modifying existing files
5. **JSON Output**: Returns structured status JSON for `install.sh` consumption
6. **Atomic Writes**: Uses tempfile + rename for safe file operations
7. **Directory Creation**: Creates `~/.claude/` if missing with secure permissions

### Command-Line Interface

**Basic Usage**:
```bash
# Fresh install (no existing settings)
python3 configure_global_settings.py --template /path/to/template.json

# Upgrade (existing settings, preserve customizations)
python3 configure_global_settings.py --template /path/to/template.json --home ~/.claude
```

**Arguments**:
- `--template PATH`: Path to settings template file (required)
  - Typically: `plugins/autonomous-dev/config/global_settings_template.json`
  - Must be valid JSON with `permissions` object
- `--home PATH`: Path to home directory (optional, default: `~/.claude`)
  - Rarely used, for testing with different directories

### Output Format

**Success Response**:
```json
{
  "success": true,
  "created": true,
  "message": "Created ~/.claude/settings.json from template",
  "path": "~/.claude/settings.json",
  "permissions": 384,
  "patterns_added": 45,
  "timestamp": "2025-12-13T15:30:45.123456"
}
```

**Upgrade Response** (preserving customizations):
```json
{
  "success": true,
  "created": false,
  "message": "Updated ~/.claude/settings.json (preserved customizations)",
  "path": "~/.claude/settings.json",
  "backup_path": "~/.claude/settings.json.backup.20251213_153045",
  "patterns_fixed": 2,
  "patterns_preserved": 5,
  "timestamp": "2025-12-13T15:30:45.123456"
}
```

**Error Response** (non-blocking):
```json
{
  "success": false,
  "created": false,
  "message": "Template file not found: /path/to/template.json",
  "path": null,
  "timestamp": "2025-12-13T15:30:45.123456"
}
```

**Exit Code**: Always 0 (non-blocking - installation continues)

### Integration with install.sh

Called from `install.sh` after downloading plugin files to configure global settings.

**Related Files**:
- `plugins/autonomous-dev/config/global_settings_template.json` - Template source
- `plugins/autonomous-dev/lib/settings_generator.py` - Python API
- `plugins/autonomous-dev/lib/validation.py` - Path validation
- `tests/unit/scripts/test_configure_global_settings.py` - Unit tests
- `tests/integration/test_install_settings_configuration.py` - Integration tests

### Configuration Processing

**Fresh Install Workflow**:
1. Check if template exists and is valid JSON
2. Create `~/.claude/` directory if missing (permissions: 0o700)
3. Merge template with empty user settings
4. Write merged settings to `~/.claude/settings.json` (permissions: 0o600)
5. Return JSON with `created: true`

**Upgrade Workflow**:
1. Check if template exists and is valid JSON
2. Read existing `~/.claude/settings.json`
3. Detect broken patterns (e.g., `Bash(:*)`)
4. Fix broken patterns: Replace `Bash(:*)` with safe specific patterns
5. Deep merge: template patterns + user patterns (union)
6. Preserve user hooks completely (never modified)
7. Create backup: `settings.json.backup.YYYYMMDD_HHMMSS`
8. Write merged settings atomically
9. Return JSON with `created: false`, backup path, and fix count

### Security

**Input Validation**:
- Path validation (CWE-22, CWE-59): Prevent path traversal, symlink attacks
- Template validation: Must be valid JSON
- Home directory validation: Must be under home directory

**Output Safety**:
- Atomic writes: Tempfile + rename pattern
- Secure permissions: 0o600 for settings (user-only access)
- No credential exposure in JSON output

**Backup Safety**:
- Timestamped filenames: `settings.json.backup.YYYYMMDD_HHMMSS`
- Only created if file will be modified
- Secure permissions: 0o600 (user-only access)
- Old backups automatically replaced (one backup per session)

### Error Handling

All errors are non-blocking (exit 0) for graceful degradation:

| Error | Message | Behavior |
|-------|---------|----------|
| Template not found | "Template file not found: ..." | Returns error JSON, continues installation |
| Invalid template JSON | "Template is invalid JSON: ..." | Returns error JSON, continues installation |
| Permission denied (read) | "Cannot read template: ..." | Returns error JSON, continues installation |
| Permission denied (write) | "Cannot write settings: ..." | Returns error JSON, continues installation |
| Corrupted settings.json | "Settings file corrupted: ..." | Backs up corrupted file, creates fresh copy |
| Path traversal attempt | "Invalid path: ..." | Rejected, continues installation |

Installation Impact: Non-blocking errors allow installation to continue. Manual configuration may be needed if settings.json not created.

### Testing

**Test Coverage**: 19 tests across 2 files

**Unit Tests** (11 tests):
- Fresh install creates settings from template
- Existing settings preserved during upgrade
- Broken Bash(:*) patterns fixed
- Missing template handled gracefully
- Directory creation with proper permissions
- JSON output format validation
- Exit code always 0 (non-blocking)
- Integration with SettingsGenerator
- Backup creation before modification
- Permission error handling
- Settings generator integration

**Integration Tests** (8 tests):
- Settings have correct Claude Code 2.0 format
- All 45+ required patterns present
- Deny list comprehensive
- PreToolUse hook configured
- Fresh install end-to-end
- Upgrade preserves customizations
- install.sh integration
- Idempotency (no duplication on repeated runs)

Coverage Target: 95%+ for CLI script

### Related Components

**Calls**:
- `SettingsGenerator.merge_global_settings()` - Core merge and fix logic

**Called By**:
- `install.sh` - Bootstrap Phase 1 (fresh install, updates, upgrades)

**Related Issues**:
- GitHub Issue #116 - Fresh install permission configuration (implementation)
- GitHub Issue #117 - Global settings configuration (related feature)
- GitHub Issue #114 - Permission fixing during updates (broken pattern detection)

### See Also

- **BOOTSTRAP_PARADOX_SOLUTION.md** - Why global infrastructure needed
- **VERIFICATION-ISSUE-116.md** - Documentation verification report
- **SettingsGenerator** - Python API for settings merge and fix logic

---

## 43. skill_loader.py (320 lines, v3.43.0+, Issue #140)

**Purpose**: Load and inject skill content into subagent prompts spawned via Task tool.

**Location**: `plugins/autonomous-dev/lib/skill_loader.py`

**Problem Solved**: Subagents spawned via Task tool do not inherit skills from the main conversation. Skills must be explicitly injected into Task prompts.

### Quick Start

```bash
# Load skills for an agent
python3 plugins/autonomous-dev/lib/skill_loader.py implementer

# List available skills
python3 plugins/autonomous-dev/lib/skill_loader.py --list

# Show agent-skill mapping
python3 plugins/autonomous-dev/lib/skill_loader.py --map
```

### Core Functions

#### `load_skills_for_agent(agent_name: str) -> Dict[str, str]`

Load all relevant skills for an agent.

**Parameters**:
- `agent_name` (str): Name of the agent (e.g., "implementer")

**Returns**: Dict mapping skill names to their content

#### `format_skills_for_prompt(skills: Dict[str, str], max_total_lines: int = 1500) -> str`

Format loaded skills as XML tags for prompt injection.

**Parameters**:
- `skills` (Dict[str, str]): Dict mapping skill names to content
- `max_total_lines` (int): Maximum total lines across all skills (default 1500)

**Returns**: Formatted string with skills in XML tags

#### `get_skill_injection_for_agent(agent_name: str) -> str`

Convenience function to get formatted skill injection for an agent.

**Parameters**:
- `agent_name` (str): Name of the agent

**Returns**: Formatted skill content ready for prompt injection

### Agent-Skill Mapping

| Agent | Skills |
|-------|--------|
| test-master | testing-guide, python-standards |
| implementer | python-standards, testing-guide, error-handling-patterns |
| reviewer | code-review, python-standards |
| security-auditor | security-patterns, error-handling-patterns |
| doc-master | documentation-guide, git-workflow |
| planner | architecture-patterns, project-management |

### Security Features

- **Trusted Directory Only**: Skills loaded from `plugins/autonomous-dev/skills/` only
- **No Path Traversal**: Rejects skill names with `/`, `\`, or `..`
- **Text Injection Only**: Skill content is not executed, only injected as text
- **Audit Logging**: Missing skills logged to stderr for debugging

### Integration with auto-implement.md

The `/auto-implement` command uses skill_loader.py before each Task call:

```markdown
**SKILL INJECTION** (Issue #140): Before calling Task, load skills:
\`\`\`bash
python3 plugins/autonomous-dev/lib/skill_loader.py test-master
\`\`\`
Prepend the output to the prompt below.
```

### Related Components

**Imports**:
- `path_utils.get_project_root()` - Project root detection

**Used By**:
- `auto-implement.md` - Skill injection before Task calls

**Related Issues**:
- GitHub Issue #140 - Skills not available to subagents
- GitHub Issue #35 - Agents should actively use skills
- GitHub Issue #110 - Skills refactoring to under 500 lines

---

## 50. context_skill_injector.py (320 lines, v3.47.0+, Issue #154)

**Purpose**: Auto-inject relevant skills based on conversation context patterns, not just agent frontmatter declarations.

**Location**: `plugins/autonomous-dev/lib/context_skill_injector.py`

**Problem Solved**: Agents with fixed skill_loader mappings miss skills relevant to dynamic user prompts. Pattern-based detection enables adaptive skill injection that responds to actual conversation context.

### Quick Start

```bash
# Detect patterns in a prompt
python3 plugins/autonomous-dev/lib/context_skill_injector.py "implement secure API endpoint"

# Typical output:
# Prompt: implement secure API endpoint
# Detected patterns: {'security', 'api'}
# Selected skills: ['security-patterns', 'api-design', 'api-integration-patterns']
```

### Core Functions

#### `detect_context_patterns(user_prompt: Optional[str]) -> Set[str]`

Detect context patterns in user prompt using regex matching.

**Parameters**:
- `user_prompt` (str): User's prompt text

**Returns**: Set of pattern category names (e.g., {"security", "api"})

**Pattern Categories**:
- `security` - auth, tokens, passwords, JWT, encryption
- `api` - REST endpoints, HTTP methods, webhooks
- `database` - SQL, migrations, schemas, ORMs
- `git` - commits, branches, pull requests
- `testing` - unit tests, pytest, TDD, mocks
- `python` - type hints, docstrings, PEP standards

#### `select_skills_for_context(user_prompt: Optional[str], max_skills: int = 5) -> List[str]`

Select relevant skills based on detected context patterns.

**Parameters**:
- `user_prompt` (str): User's prompt text
- `max_skills` (int): Maximum number of skills to return (default: 5)

**Returns**: Prioritized list of skill names limited to max_skills

**Priority Order**: Security → Testing → API → Database → Python → Git

#### `get_context_skill_injection(user_prompt: Optional[str], max_skills: int = 5) -> str`

Main entry point: combine pattern detection, skill selection, and skill loading.

**Parameters**:
- `user_prompt` (str): User's prompt text
- `max_skills` (int): Maximum number of skills to inject

**Returns**: Formatted skill content string (XML-tagged) or empty string

### Usage Example

```python
from context_skill_injector import get_context_skill_injection

# Automatically select and load skills based on prompt
prompt = "implement JWT authentication with secure password hashing"
skill_content = get_context_skill_injection(prompt)

# Returns security-patterns skill (detected: "JWT", "auth", "password")
# Max 5 skills injected to prevent context bloat
```

### Pattern Detection

Patterns use case-insensitive regex with word boundaries to avoid partial matches:

```python
CONTEXT_PATTERNS = {
    "security": [
        r"\b(auth|authenticat\w*|authoriz\w*)\b",
        r"\b(token|jwt|oauth|api.?key)\b",
        r"\b(password|secret|credential|encrypt)\b",
        # ... more patterns
    ],
    # ... other categories
}
```

### Performance Characteristics

- **Latency**: <100ms for pattern detection (regex, not LLM)
- **Context Impact**: 5 skills × 50-100 lines each = 250-500 tokens (controllable)
- **Graceful Degradation**: Missing skills don't block workflow (returns empty string)

### Integration Points

**Imports**:
- `skill_loader.load_skill_content()` - Load actual skill files
- `skill_loader.format_skills_for_prompt()` - Format for injection

**Used By**:
- Agent prompts (future) - Can augment skill_loader agent-based injection
- Custom commands - Can use for dynamic skill selection

### Security Features

- **Trusted Directory Only**: Skills loaded from `plugins/autonomous-dev/skills/` only
- **No LLM**: Pattern detection via regex only (deterministic, auditable)
- **Text Injection Only**: Skill content is not executed, only injected
- **Limited Context**: Max 5 skills prevents unbounded context growth

### Related Components

**Depends On**:
- `skill_loader.py` - Load and format skill content
- `CONTEXT_PATTERNS` dict - Regex patterns for detection
- `PATTERN_SKILL_MAP` dict - Pattern-to-skill mappings

**Related Issues**:
- GitHub Issue #154 - Context-triggered skill injection
- GitHub Issue #140 - Skills not available to subagents (related work)
- GitHub Issue #35 - Agents should actively use skills (related goal)


---

## 33. feature_dependency_analyzer.py (509 lines, v1.0.0 - Issue #157)

**Purpose**: Analyze feature descriptions for dependencies and optimize batch execution order using topological sort

**Location**: plugins/autonomous-dev/lib/feature_dependency_analyzer.py

**Dependencies**: validation.py (optional, graceful degradation)

### Classes

#### FeatureDependencyError

Base exception for feature dependency operations.

#### CircularDependencyError

Raised when circular dependencies are detected in the dependency graph.

#### TimeoutError

Raised when analysis exceeds 5-second timeout.

### Functions

#### detect_keywords(feature_text: str) -> Set[str]

Extract dependency keywords from feature text.

**Parameters**:
- feature_text (str): Feature description text

**Returns**: Set of detected keywords (lowercase)

**Detects**:
- Dependency keywords: requires, depends, after, before, uses, needs
- File references: .py, .md, .json, .yaml, .yml, .sh, .ts, .js, .tsx, .jsx

**Example**:
```python
keywords = detect_keywords("Add tests for auth (requires auth implementation)")
# Returns: {"requires", "tests", "auth"}
```

#### build_dependency_graph(features: List[str], keywords: Dict[int, Set[str]]) -> Dict[int, List[int]]

Build directed dependency graph from feature keywords.

**Parameters**:
- features (List[str]): List of feature descriptions
- keywords (Dict[int, Set[str]]): Keywords detected per feature (from detect_keywords)

**Returns**: Dependency graph where deps[i] = [j, k] means features i depends on j and k

**Algorithm**: Analyzes feature names for references to other features using keyword matching and file similarity.

#### analyze_dependencies(features: List[str]) -> Dict[int, List[int]]

Main entry point: analyze features for dependencies.

**Parameters**:
- features (List[str]): List of feature descriptions

**Returns**: Dependency graph (Dict[int, List[int]])

**Execution**:
1. Validates input (max 1000 features, sanitizes text)
2. Detects keywords for each feature
3. Builds dependency graph
4. Detects circular dependencies
5. Returns graph with timeout protection (5 seconds)

**Graceful Degradation**: Returns empty dict (no dependencies) if analysis fails

#### topological_sort(features: List[str], deps: Dict[int, List[int]]) -> List[int]

Order features using topological sort (Kahn's algorithm).

**Parameters**:
- features (List[str]): Feature descriptions
- deps (Dict[int, List[int]]): Dependency graph from analyze_dependencies()

**Returns**: Feature indices in dependency order

**Algorithm**: Kahn's algorithm for topological sort
- Time complexity: O(V + E) where V = features, E = dependencies
- Circular dependencies raise CircularDependencyError

**Example**:
```python
features = ["Add auth", "Add tests for auth"]
deps = analyze_dependencies(features)
order = topological_sort(features, deps)
# Returns: [0, 1] (implement auth before testing)
```

#### visualize_graph(features: List[str], deps: Dict[int, List[int]]) -> str

Generate ASCII visualization of dependency graph.

**Parameters**:
- features (List[str]): Feature descriptions
- deps (Dict[int, List[int]]): Dependency graph

**Returns**: Formatted ASCII string showing graph relationships

**Example Output**:
```
Feature Dependency Graph
========================

Feature 0: Add auth
  └─> [depends on] (no dependencies)

Feature 1: Add tests for auth
  └─> [depends on] Feature 0: Add auth

Feature 2: Add password reset
  └─> [depends on] Feature 0: Add auth
```

#### detect_circular_dependencies(deps: Dict[int, List[int]]) -> List[List[int]]

Detect circular dependency cycles in graph.

**Parameters**:
- deps (Dict[int, List[int]]): Dependency graph

**Returns**: List of cycles (each cycle is list of feature indices)

**Returns empty list if no cycles detected**

#### get_execution_order_stats(features: List[str], deps: Dict[int, List[int]], order: List[int]) -> Dict[str, Any]

Generate statistics about execution order.

**Parameters**:
- features (List[str]): Feature descriptions
- deps (Dict[int, List[int]]): Dependency graph
- order (List[int]): Topologically sorted order

**Returns**: Dictionary with statistics:
```python
{
    "total_dependencies": 3,      # Total edges in graph
    "independent_features": 1,    # Features with no dependencies
    "dependent_features": 2,      # Features with dependencies
    "max_depth": 2,              # Longest dependency chain
    "total_features": 3,
}
```

### Security

**Input Validation** (CWE-22, CWE-78):
- Text sanitization via validation.sanitize_text_input() (max 10,000 chars per feature)
- No shell execution
- Path traversal protection via safe regex matching
- Command injection prevention - only text analysis

**Resource Limits**:
- MAX_FEATURES: 1000 (prevents unbounded processing)
- TIMEOUT_SECONDS: 5 (prevents infinite loops in circular detection)
- Memory: O(V + E) for graph storage (linear in feature count)

### Performance Characteristics

- **Analysis Time**: <100ms for typical batches (50 features)
- **Memory**: O(V + E) where V = features, E = dependencies
- **Topological Sort**: O(V + E) via Kahn's algorithm
- **Circular Detection**: O(V + E) via DFS
- **Graph Visualization**: O(V + E) for ASCII rendering

### Error Handling

**Graceful Degradation**:
- If analysis fails: Returns empty dict (no dependencies detected)
- If topological sort fails: CircularDependencyError raised
- If timeout exceeded: TimeoutError raised
- If validation fails: Returns fallback (original order)

### Test Coverage

**Test File**: tests/unit/lib/test_feature_dependency_analyzer.py

**Coverage Areas**:
- Keyword detection (requires, depends, after, before, uses, needs)
- File reference detection (.py, .md, .json, etc.)
- Dependency graph construction
- Topological sort correctness
- Circular dependency detection
- ASCII visualization formatting
- Timeout protection
- Memory limits for large batches
- Security validations (CWE-22, CWE-78)
- Graceful degradation with invalid inputs

**Target**: 90%+ coverage

### Used By

- /batch-implement command (STEP 1.5 - Analyze Dependencies)
- batch_state_manager.py - Stores optimized order and dependency info
- Batch processing workflow for reordering features

### Related Issues

- GitHub Issue #157 - Smart dependency ordering for /batch-implement
- GitHub Issue #88 - Batch processing support
- GitHub Issue #89 - Automatic retry for batch features
- GitHub Issue #93 - Git automation for batch mode

### Related Components

**Dependencies**:
- validation.py - Input sanitization (optional, graceful degradation)

**Used By**:
- batch_state_manager.py - Stores dependency metadata
- /batch-implement command - STEP 1.5 dependency analysis

### Example Workflow

```python
from plugins.autonomous_dev.lib.feature_dependency_analyzer import (
    analyze_dependencies,
    topological_sort,
    visualize_graph,
    get_execution_order_stats
)

# Features to process
features = [
    "Add JWT authentication module",
    "Add tests for JWT validation",
    "Add password reset endpoint (requires auth)"
]

# Analyze dependencies
deps = analyze_dependencies(features)

# Get optimized order
order = topological_sort(features, deps)

# Get statistics
stats = get_execution_order_stats(features, deps, order)

# Visualize for user
graph = visualize_graph(features, deps)

print(f"Dependencies detected: {stats['total_dependencies']}")
print(f"Independent features: {stats['independent_features']}")
print(graph)

# Use optimized order in batch processing
for idx in order:
    process_feature(features[idx])
```

### Integration with /batch-implement

STEP 1.5 in /batch-implement command now calls this analyzer:

```python
# Import analyzer
from plugins.autonomous_dev.lib.feature_dependency_analyzer import (
    analyze_dependencies,
    topological_sort,
    visualize_graph,
    get_execution_order_stats
)

# Analyze and optimize order
try:
    deps = analyze_dependencies(features)
    feature_order = topological_sort(features, deps)
    stats = get_execution_order_stats(features, deps, feature_order)
    graph = visualize_graph(features, deps)

    # Store in batch state
    state.feature_dependencies = deps
    state.feature_order = feature_order
    state.analysis_metadata = {"stats": stats}

    # Show user
    print(f"Dependencies detected: {stats['total_dependencies']}")
    print(graph)
except Exception as e:
    # Graceful degradation
    print(f"Dependency analysis failed: {e}")
    feature_order = list(range(len(features)))
    state.feature_order = feature_order
```

---

## 51. genai_manifest_validator.py (474 lines, v3.44.0+ - Issue #160)

**Purpose**: GenAI-powered manifest alignment validation using Claude Sonnet 4.5 with structured output.

**Module**: plugins/autonomous-dev/lib/genai_manifest_validator.py

**Problem Solved**:
- Manual CLAUDE.md updates may create drift between documented component counts and actual manifest
- Regex-only validation misses semantic inconsistencies and version conflicts
- Need LLM reasoning to catch complex alignment issues

**Solution**:
- Uses Claude Sonnet 4.5 with structured JSON output for manifest validation
- Validates manifest (plugin.json) against documentation (CLAUDE.md)
- Detects count mismatches, version drift, missing components, inconsistent configurations
- Returns None when API key absent (enables fallback to regex validator)
- Supports both Anthropic and OpenRouter API keys for flexibility

### Core Classes

#### ManifestIssue
Represents a single manifest alignment issue with severity level.

#### IssueLevel
Enum for validation issue severity levels with ERROR, WARNING, and INFO levels.

#### ManifestValidationResult
Complete validation result with component breakdown, counts, versions, and timestamp.

#### GenAIManifestValidator
Main validator class using Claude Sonnet 4.5 with structured output.

### API Reference

#### GenAIManifestValidator.validate()

Main validation entry point.

**Returns**: Optional[ManifestValidationResult]
- ManifestValidationResult on successful validation
- None if API key missing (graceful fallback)

**Raises**:
- json.JSONDecodeError - If plugin.json is malformed
- FileNotFoundError - If plugin.json or CLAUDE.md not found
- Exception - If API call fails (will be caught and logged)

**Security**:
- Path validation via security_utils (CWE-22, CWE-59)
- Token budget enforcement (max 8K tokens)
- API key never logged
- Input sanitization

### Validation Checks

GenAI validator checks for:
1. Count Mismatches: Documented vs actual component counts
2. Version Drift: Documented versions vs manifest versions
3. Missing Components: Components in manifest but not documented
4. Undocumented Components: Components documented but not in manifest
5. Configuration Inconsistencies: Settings conflicts between manifest and docs
6. Dependency Issues: Component dependencies that cannot be satisfied

### LLM Reasoning

Uses Claude Sonnet 4.5 for semantic validation:
- Understands natural language descriptions in CLAUDE.md
- Detects logical inconsistencies (e.g., documented 8 agents but manifest shows 7)
- Catches version mismatches across multiple files
- Identifies scope creep (features documented but not implemented)
- Validates architectural claims against actual implementation

### API Support

**Primary API**: Anthropic (ANTHROPIC_API_KEY)

**Fallback API**: OpenRouter (OPENROUTER_API_KEY)

### Security

**Input Validation** (CWE-22, CWE-59):
- Path validation via security_utils.validate_path()
- Only allows project root and system temp directories
- Symlink resolution and normalization

**Token Budget**:
- MAX_TOKENS = 8000
- Enforced in prompt construction
- Prevents runaway API costs

**API Key Handling**:
- Keys read from environment only
- Never logged or exposed in output
- Graceful degradation if missing

**Data Handling**:
- No sensitive data in audit logs
- Results include only validation metadata
- No raw file contents in output

### Performance Characteristics

- API Latency: 5-15 seconds (Anthropic/OpenRouter)
- Local Processing: less than 100ms
- Total Time: 5-15 seconds per validation
- Token Usage: 2-4K tokens typical (within 8K budget)
- Memory: less than 50MB

### Error Handling

**Graceful Degradation**:
- API key missing: Returns None (signals fallback)
- API call fails: Logs error, returns None
- Invalid JSON: Raises JSONDecodeError (should be caught by hybrid validator)
- File not found: Returns None (signals regex fallback)
- Token budget exceeded: Truncates input gracefully

### Test Coverage

**Test File**: tests/unit/lib/test_genai_manifest_validator.py

**Coverage Areas**:
- API key detection (Anthropic, OpenRouter, missing)
- Manifest loading and validation
- CLAUDE.md parsing
- Count mismatch detection
- Version drift detection
- Missing component detection
- Prompt construction with token budget
- LLM response parsing
- Error handling (missing files, invalid JSON)
- Security validations (path traversal, injection)
- Graceful degradation

**Target**: 85 percent coverage

### Used By

- hybrid_validator.py - Primary GenAI validator (tries first, falls back if no API key)
- /health-check command - Optional GenAI validation if API key available
- CI/CD validation - For GenAI-powered alignment checks

### Related Issues

- GitHub Issue #160 - GenAI manifest alignment validation
- GitHub Issue #148 - Claude Code 2.0 compliance
- GitHub Issue #146 - Tool least privilege enforcement

### Related Components

**Dependencies**:
- security_utils.py - Path validation and audit logging
- anthropic package (optional) - Anthropic API
- openai package (optional) - OpenRouter API via OpenAI client

**Used By**:
- hybrid_validator.py - Orchestrator that wraps this validator
- validate_documentation_parity.py - Complements parity validation

### Fallback Mechanism

GenAI validator is designed to fail gracefully. When API key is missing, it returns None which signals the hybrid validator to fall back to regex validation. This enables LLM-powered validation in environments with API keys while maintaining regex-based validation for users without them.

---

## 52. hybrid_validator.py (378 lines, v3.44.0+ - Issue #160)

**Purpose**: Orchestrates GenAI and regex manifest validation with automatic fallback.

**Module**: plugins/autonomous-dev/lib/hybrid_validator.py

**Problem Solved**:
- Users with API keys get LLM-powered validation (better accuracy)
- Users without API keys get regex validation (still catches issues)
- Need unified API for both approaches

**Solution**:
- Three validation modes: AUTO (default), GENAI_ONLY, REGEX_ONLY
- AUTO mode tries GenAI first, falls back to regex if API key missing
- Returns consistent HybridValidationReport format
- Used by /health-check and CI/CD validation pipelines

### Core Classes

#### ValidationMode
Enum for validation execution modes with AUTO, GENAI_ONLY, and REGEX_ONLY values.

#### HybridValidationReport
Extended validation report with hybrid metadata tracking which validator was used.

#### HybridManifestValidator
Main validator orchestrator with mode-specific behavior.

### API Reference

#### HybridManifestValidator.__init__()

Initialize validator with mode selection.

**Parameters**:
- repo_root (Path): Repository root directory
- mode (ValidationMode): Validation mode (default: AUTO)

**Raises**:
- ValueError - If repo_root invalid or outside allowed locations

#### HybridManifestValidator.validate()

Main validation entry point with mode-specific behavior.

**Returns**: HybridValidationReport
- Always returns a report (never None)
- validator_used field indicates which backend was used

**Raises**:
- RuntimeError - Only in GENAI_ONLY mode if no API key
- FileNotFoundError - If required files missing

### Validation Modes

#### AUTO Mode (Default)

Strategy: LLM first, regex fallback

1. Try GenAI: Attempt validation with Claude Sonnet 4.5
2. Success Path: Return GenAI result (validator_used="genai")
3. Fallback Path: If API key missing, use regex validation
4. Final Result: Always returns HybridValidationReport

Best For: Production environments where API key may be available

#### GENAI_ONLY Mode

Strategy: Strict LLM validation

1. Check API Key: Verify ANTHROPIC_API_KEY or OPENROUTER_API_KEY
2. Fail if Missing: Raise RuntimeError
3. Validate: Use Claude Sonnet 4.5 validation

Best For: CI/CD pipelines that require LLM-powered validation

#### REGEX_ONLY Mode

Strategy: Pattern-based validation

1. Use Regex: Validate with pattern matching (no API call)
2. Return Result: Always succeeds (validator_used="regex")

Best For: Quick validation without API latency, offline environments

### Validation Report

All modes return HybridValidationReport with:
- validator_used: "genai" or "regex"
- version_issues: Version mismatches
- count_issues: Count discrepancies
- cross_reference_issues: Missing references
- error_count: Number of errors
- warning_count: Number of warnings
- info_count: Number of info messages
- is_valid: True if error_count equals zero

### Security

**Input Validation** (CWE-22, CWE-59):
- Path validation via security_utils.validate_path()
- Repository root must be within project boundaries
- No path traversal allowed

**API Key Handling**:
- Keys read from environment only
- Never exposed in output or logs
- Missing key triggers graceful fallback (AUTO mode)

**Data Flow**:
- GenAI validator: Processes manifest and docs, returns issues
- Regex validator: Pattern matching only, no LLM calls
- Report: Contains only validation metadata, no sensitive data

### Performance Characteristics

**AUTO Mode**:
- With API Key: 5-15 seconds (GenAI latency)
- Without API Key: less than 1 second (regex fallback)
- Typical: 1-3 seconds (regex)

**GENAI_ONLY Mode**:
- With API Key: 5-15 seconds
- Without API Key: RuntimeError (fails immediately)

**REGEX_ONLY Mode**:
- Always: less than 1 second
- Memory: less than 10MB

### Error Handling

**Graceful Degradation**:
- AUTO mode: Missing API key -> Falls back to regex
- GENAI_ONLY mode: Missing API key -> Raises RuntimeError
- REGEX_ONLY mode: Always succeeds (worst case: minimal validation)
- Invalid paths: Raises ValueError early (before validation)
- Missing files: Returns report with errors (no exception)

### Test Coverage

**Test File**: tests/unit/lib/test_hybrid_validator.py

**Coverage Areas**:
- Mode selection (AUTO, GENAI_ONLY, REGEX_ONLY)
- API key detection and fallback
- GenAI validation integration
- Regex validation fallback
- Report generation and formatting
- Error handling (missing files, invalid paths)
- Graceful degradation
- Security validations (path traversal)

**Target**: 85 percent coverage

### Used By

- /health-check command - Manifest alignment validation
- CI/CD validation pipelines - Automated alignment checks
- genai_manifest_validator.py - Wrapped by this orchestrator
- validate_documentation_parity.py - Complementary validation

### Related Issues

- GitHub Issue #160 - GenAI manifest alignment validation
- GitHub Issue #148 - Claude Code 2.0 compliance
- GitHub Issue #50 - /health-check command

### Related Components

**Dependencies**:
- genai_manifest_validator.py - LLM-powered validation
- validate_manifest_doc_alignment.py - Regex-based validation
- validate_documentation_parity.py - Parity validation (shared models)
- security_utils.py - Path validation

**Used By**:
- /health-check command
- CI/CD validation scripts

---
## 53. acceptance_criteria_parser.py (269 lines, v3.45.0+ - Issue #161)

**Purpose**: Parse and format acceptance criteria from GitHub issues for UAT test generation.

**Module**: plugins/autonomous-dev/lib/acceptance_criteria_parser.py

**Problem Solved**:
- Test-master needs to extract acceptance criteria from GitHub issues
- Manual parsing is error-prone and time-consuming
- Need standardized format for UAT test generation with Gherkin-style scenarios

**Solution**:
- Fetch issue body via gh CLI with security validation
- Parse categorized acceptance criteria (### headers)
- Format criteria as Gherkin-style test scenarios
- Handle malformed/missing criteria gracefully

### Functions

#### fetch_issue_body(issue_number: int) -> str

Fetch GitHub issue body via gh CLI.

**Parameters**:
- issue_number (int): GitHub issue number (must be positive)

**Returns**: Issue body as string

**Raises**:
- ValueError: If issue not found (404)
- RuntimeError: If gh CLI not installed or network error

**Security**:
- Uses subprocess.run with list args (no shell=True)
- Validates issue_number is positive integer
- No credential exposure in logs

#### parse_acceptance_criteria(issue_body: str) -> Dict[str, List[str]]

Parse GitHub issue body into categorized acceptance criteria.

**Parameters**:
- issue_body (str): Raw GitHub issue body

**Returns**: Dictionary with category names as keys and lists of criteria as values

#### format_for_uat(criteria: Dict[str, List[str]]) -> List[Dict[str, str]]

Format acceptance criteria as Gherkin-style UAT scenarios.

**Parameters**:
- criteria (Dict): Parsed acceptance criteria

**Returns**: List of UAT scenario dictionaries with "scenario" and "description" keys

### Test Coverage

**Test File**: tests/unit/lib/test_acceptance_criteria_parser.py (530 lines, 16 tests)

**Coverage Areas**:
- Fetch issue body (gh CLI integration, error handling)
- Parse acceptance criteria (categorization, formatting)
- Format for UAT (Gherkin-style scenarios)
- Error handling (missing issues, network errors, malformed criteria)
- Security (subprocess list args, input validation)

**Target**: 90 percent coverage

### Used By

- test-master agent - UAT test generation during TDD phase
- /auto-implement command - Acceptance criteria parsing in test phase

### Related Issues

- GitHub Issue #161 - Enhanced test-master for 3-tier test coverage

### Related Components

**Dependencies**:
- gh CLI (external) - GitHub issue fetching
- subprocess module (stdlib) - Command execution

**Used By**:
- test_tier_organizer.py - Test tier classification
- test_validator.py - Test validation after organization

---

## 54. test_tier_organizer.py (399 lines, v3.45.0+ - Issue #161)

**Purpose**: Classify and organize tests into unit/integration/uat tiers with pyramid validation.

**Module**: plugins/autonomous-dev/lib/test_tier_organizer.py

**Problem Solved**:
- Tests generated by test-master need intelligent tier classification
- Manual test organization is error-prone
- Need to enforce test pyramid (70% unit, 20% integration, 10% UAT)

**Solution**:
- Content-based tier classification (imports, decorators, patterns)
- Filename-based tier hints
- Tier directory structure creation (tests/{unit,integration,uat}/)
- Test pyramid validation with statistics

### Functions

#### determine_tier(test_content: str) -> str

Determine test tier from test file content analysis.

**Parameters**:
- test_content (str): Test file content as string

**Returns**: "unit", "integration", or "uat"

**Classification Logic**:
- UAT: pytest-bdd imports, Gherkin decorators (@scenario, @given, @when, @then), explicit "test_uat_" naming
- Integration: Multiple imports, subprocess, file I/O, "integration" in function names, tmp_path/tmpdir fixtures
- Unit: Default (single function, mocking, isolated)

#### determine_tier_from_filename(filename: str) -> str

Hint for test tier from filename patterns.

**Parameters**:
- filename (str): Test filename

**Returns**: "unit", "integration", or "uat" (or None for no hint)

#### create_tier_directories(base_path: Path, subdirs: List[str] = None) -> None

Create tier directory structure.

**Parameters**:
- base_path (Path): Repository root
- subdirs (List[str]): Optional subdirectories

**Creates**: tests/unit/, tests/integration/, tests/uat/

#### organize_tests_by_tier(test_files: List[Path], base_path: Path = None) -> Dict[str, List[Path]]

Move tests to tier directories with collision handling.

**Parameters**:
- test_files (List[Path]): List of test file paths
- base_path (Path): Repository root (auto-detected if None)

**Returns**: Dictionary mapping tier names to file paths

#### get_tier_statistics(tests_path: Path) -> Dict[str, int]

Count tests in each tier directory.

**Parameters**:
- tests_path (Path): Path to tests directory

**Returns**: Dictionary with unit/integration/uat/total counts

#### validate_test_pyramid(tests_path: Path) -> Tuple[bool, List[str]]

Validate test pyramid ratios (70% unit, 20% integration, 10% UAT).

**Parameters**:
- tests_path (Path): Path to tests directory

**Returns**: Tuple of (is_valid, warning_messages)

### Test Coverage

**Test File**: tests/unit/lib/test_test_tier_organizer.py (490 lines, 31 tests)

**Coverage Areas**:
- Tier determination (content and filename analysis)
- Directory structure creation
- Test file organization (with collision handling)
- Tier statistics and counting
- Test pyramid validation
- Error handling (missing directories, invalid paths)

**Target**: 90 percent coverage

### Used By

- test-master agent - Organizing generated tests after creation
- /auto-implement command - Test organization in pipeline

### Related Issues

- GitHub Issue #161 - Enhanced test-master for 3-tier test coverage

### Related Components

**Dependencies**:
- pathlib - Path handling
- test_validator.py - Test validation after organization

**Used By**:
- test_validator.py - Validation gate before commit

---

## 55. test_validator.py (388 lines, v3.45.0+ - Issue #161)

**Purpose**: Execute tests, validate TDD workflow, and enforce quality gates.

**Module**: plugins/autonomous-dev/lib/test_validator.py

**Problem Solved**:
- Need to validate TDD red phase (tests must fail before implementation)
- Need to run validation gate (all tests must pass before commit)
- Need to detect syntax errors vs runtime errors
- Need to enforce coverage thresholds

**Solution**:
- Run pytest with minimal verbosity (--tb=line -q per Issue #90)
- Parse test output for pass/fail/error counts
- Enforce TDD red phase validation
- Detect and report syntax errors separately
- Validate coverage thresholds

### Functions

#### run_tests(test_path: Path, timeout: int = 300, pytest_args: List[str] = None) -> Dict[str, Any]

Execute pytest and return results.

**Parameters**:
- test_path (Path): Path to test directory or file
- timeout (int): Timeout in seconds (default 5 minutes)
- pytest_args (List[str]): Optional custom pytest arguments

**Returns**: Dictionary with results including success, passed, failed, errors, skipped, total, stdout, stderr, no_tests_collected

**Raises**:
- TimeoutError: If tests exceed timeout
- RuntimeError: If pytest not installed

**Minimal Verbosity** (Issue #90):
- Uses --tb=line -q to prevent pipe deadlock
- Reduces output from 2,300 lines to 50 lines
- Better for subprocess communication

#### parse_pytest_output(output: str) -> Dict[str, int]

Parse pytest output for test counts.

**Parameters**:
- output (str): pytest stdout

**Returns**: Dictionary with "passed", "failed", "errors", "skipped" counts

#### validate_red_phase(test_result: Dict[str, Any]) -> None

Enforce TDD red phase (tests must fail before implementation).

**Parameters**:
- test_result (Dict): Result from run_tests()

**Raises**:
- AssertionError: If tests pass prematurely (red phase not satisfied)

**Purpose**:
- Called before implementation starts
- Ensures test file is valid (has tests, no syntax errors)
- Ensures tests actually fail before code written

#### detect_syntax_errors(pytest_output: str) -> Tuple[bool, List[str]]

Detect and extract syntax errors from pytest output.

**Parameters**:
- pytest_output (str): pytest stderr or combined output

**Returns**: Tuple of (has_errors, error_messages)

**Error Types**:
- SyntaxError
- ImportError
- IndentationError
- NameError

#### validate_test_syntax(test_result: Dict[str, Any]) -> None

Validate test file syntax and raise if errors detected.

**Parameters**:
- test_result (Dict): Result from run_tests()

**Raises**:
- RuntimeError: If syntax errors detected

**Used By**:
- TDD red phase to verify test file is syntactically valid

#### run_validation_gate(test_path: Path, timeout: int = 300) -> Dict[str, Any]

Run complete validation gate (all tests must pass).

**Parameters**:
- test_path (Path): Path to test directory or file
- timeout (int): Timeout in seconds

**Returns**: Dictionary with gate_passed, tests_passed, syntax_valid, coverage_valid, error_count, passed, failed, message

**Pre-commit Checks**:
- All tests must pass
- No syntax errors
- Coverage threshold met (if configured)
- No test collection errors

#### validate_coverage(coverage_output: str, threshold: float = 80.0) -> None

Validate code coverage threshold.

**Parameters**:
- coverage_output (str): Coverage output from pytest --cov
- threshold (float): Minimum coverage percentage (default 80%)

**Raises**:
- AssertionError: If coverage below threshold

### Test Coverage

**Test File**: tests/unit/lib/test_test_validator.py (668 lines, 33 tests)

**Coverage Areas**:
- Test execution (pytest integration, timeout handling)
- Output parsing (pass/fail/error counts)
- TDD red phase validation
- Syntax error detection
- Validation gate (pre-commit checks)
- Coverage threshold validation
- Error handling (pytest not found, timeout, syntax errors)

**Target**: 90 percent coverage

### Used By

- test-master agent - TDD validation during /auto-implement
- /auto-implement command - Pre-commit quality gate

### Related Issues

- GitHub Issue #161 - Enhanced test-master for 3-tier test coverage
- GitHub Issue #90 - Minimal pytest verbosity (--tb=line -q)

### Related Components

**Dependencies**:
- pytest (external) - Test execution
- pytest-cov (optional) - Coverage measurement
- subprocess module (stdlib) - Command execution

**Used By**:
- test_tier_organizer.py - After test organization
- acceptance_criteria_parser.py - Works with parsed criteria

---
