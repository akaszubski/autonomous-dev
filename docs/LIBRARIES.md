# Shared Libraries Reference

**Last Updated**: 2025-12-07
**Purpose**: Comprehensive API documentation for autonomous-dev shared libraries

This document provides detailed API documentation for all 37 shared libraries in `plugins/autonomous-dev/lib/`. For high-level overview, see [CLAUDE.md](../CLAUDE.md) Architecture section.

## Overview

The autonomous-dev plugin includes **37 shared libraries** organized into eleven categories:

### Core Libraries (20)

1. **security_utils.py** - Security validation and audit logging
2. **project_md_updater.py** - Atomic PROJECT.md updates with merge conflict detection
3. **version_detector.py** - Semantic version comparison for marketplace sync
4. **orphan_file_cleaner.py** - Orphaned file detection and cleanup
5. **sync_dispatcher.py** - Intelligent sync orchestration (marketplace/env/plugin-dev)
6. **validate_marketplace_version.py** - CLI script for version validation
7. **plugin_updater.py** - Interactive plugin update with backup/rollback
8. **update_plugin.py** - CLI interface for plugin updates
9. **hook_activator.py** - Automatic hook activation during updates
10. **validate_documentation_parity.py** - Documentation consistency validation
11. **auto_implement_git_integration.py** - Automatic git operations (commit/push/PR)
12. **batch_state_manager.py** - State-based auto-clearing for /batch-implement (v3.23.0)
13. **github_issue_fetcher.py** - GitHub issue fetching via gh CLI (v3.24.0)
14. **github_issue_closer.py** - Auto-close GitHub issues after /auto-implement (v3.22.0, Issue #91)
15. **path_utils.py** - Dynamic PROJECT_ROOT detection and path resolution (v3.28.0, Issue #79)
16. **validation.py** - Tracking infrastructure security validation (v3.28.0, Issue #79)
17. **failure_classifier.py** - Error classification (transient vs permanent) for /batch-implement (v3.33.0, Issue #89)
18. **batch_retry_manager.py** - Retry orchestration with circuit breaker for /batch-implement (v3.33.0, Issue #89)
19. **batch_retry_consent.py** - First-run consent handling for automatic retry (v3.33.0, Issue #89)
20. **session_tracker.py** - Session logging for agent actions with portable path detection (v3.28.0+, Issue #79)

### Tracking Libraries (2) - NEW in v3.28.0

21. **agent_tracker.py** (see section 24)
22. **session_tracker.py** (see section 25)

### Installation Libraries (4) - NEW in v3.29.0

23. **file_discovery.py** - Comprehensive file discovery with exclusion patterns (Issue #80)
24. **copy_system.py** - Structure-preserving file copying with permission handling (Issue #80)
25. **installation_validator.py** - Coverage validation and missing file detection (Issue #80)
26. **install_orchestrator.py** - Coordinates complete installation workflows (Issue #80)

### Utility Libraries (2)

27. **math_utils.py** - Fibonacci calculator with multiple algorithms
28. **git_hooks.py** - Git hook utilities for larger projects (500+ tests, Issue #94)

### Brownfield Retrofit Libraries (6)

29. **brownfield_retrofit.py** - Phase 0: Project analysis and tech stack detection
30. **codebase_analyzer.py** - Phase 1: Deep codebase analysis (multi-language)
31. **alignment_assessor.py** - Phase 2: Gap assessment and 12-Factor compliance
32. **migration_planner.py** - Phase 3: Migration plan with dependency tracking
33. **retrofit_executor.py** - Phase 4: Step-by-step execution with rollback
34. **retrofit_verifier.py** - Phase 5: Verification and readiness assessment

### MCP Security Libraries (3) - NEW in v3.37.0

35. **mcp_permission_validator.py** - Permission validation for MCP server operations (Issue #95)
36. **mcp_profile_manager.py** - Pre-configured security profiles for MCP (development, testing, production) (Issue #95)
37. **mcp_server_detector.py** - Identifies MCP server type from tool calls to enable server-specific validation (Issue #95)

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

## 5. sync_dispatcher.py (1117 lines, v3.7.1+)

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

## 9. hook_activator.py (539 lines, v3.8.1+)

**Purpose**: Automatic hook activation during plugin updates

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
- **Purpose**: Activate hooks from new plugin version
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name
- **Returns**: `ActivationResult`
- **Features**:
  - First install detection: Checks for existing settings.json file
  - Automatic hook activation: Activates hooks from plugin.json on first install
  - Smart merging: Preserves existing customizations when updating
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

### Security
- Path validation via security_utils
- Audit logging to `logs/security_audit.log`
- Secure permissions (0o600)

### Error Handling
- Non-blocking (activation failures don't block plugin update)

### Test Coverage
- 41 unit tests (first install, updates, merge logic, error cases, malformed JSON)

### Used By
- plugin_updater.py for /update-plugin command

### Related
- GitHub Issue #50 Phase 2.5 (automatic hook activation)

---

## 10. validate_documentation_parity.py (880 lines, v3.8.1+)

**Purpose**: Documentation consistency validation across CLAUDE.md, PROJECT.md, README.md, and CHANGELOG.md

### Classes

#### `ValidationLevel` (enum)
- `ERROR`: Critical validation failure
- `WARNING`: Non-critical issue
- `INFO`: Informational message

#### `ParityIssue`
- **Purpose**: Representation of a parity validation issue
- **Attributes**:
  - `level` (ValidationLevel): Severity level
  - `category` (str): Issue category
  - `message` (str): Human-readable description
  - `file` (str): File where issue was detected

#### `ParityReport`
- **Purpose**: Validation result dataclass
- **Attributes**:
  - `version_issues` (List[ParityIssue]): Version consistency violations
  - `count_issues` (List[ParityIssue]): Count discrepancy violations
  - `cross_reference_issues` (List[ParityIssue]): Cross-reference validation violations
  - `changelog_issues` (List[ParityIssue]): CHANGELOG parity violations
  - `security_issues` (List[ParityIssue]): Security documentation violations
  - `has_errors` (bool): Whether report has critical errors
  - `exit_code` (int): Exit code for CLI use (0=success, 1=warnings, 2=errors)

### Validation Categories

#### `validate_version_consistency(project_root)`
- **Purpose**: Detect when CLAUDE.md date != PROJECT.md date
- **Returns**: `List[ParityIssue]`

#### `validate_count_discrepancies(project_root)`
- **Purpose**: Detect when documented counts != actual counts (agents, commands, skills, hooks)
- **Returns**: `List[ParityIssue]`

#### `validate_cross_references(project_root)`
- **Purpose**: Detect when documented features don't exist in codebase (or vice versa)
- **Returns**: `List[ParityIssue]`

#### `validate_changelog_parity(project_root)`
- **Purpose**: Detect when plugin.json version missing from CHANGELOG.md
- **Returns**: `List[ParityIssue]`

#### `validate_security_documentation(project_root)`
- **Purpose**: Detect missing or incomplete security documentation
- **Returns**: `List[ParityIssue]`

### Functions

#### `validate_documentation_parity(project_root)` (convenience)
- **Purpose**: High-level API for parity validation
- **Returns**: `ParityReport`

### Features
- Prevents documentation drift
- Enforces accuracy
- Supports CLI with JSON output

### Security
- File size limits (max 10MB per file)
- Path validation via security_utils
- Safe file reading (no execution)

### Error Handling
- Graceful handling of malformed content, missing files, corrupted JSON

### CLI Arguments
- `--project-root`: Project root path (default: current directory)
- `--verbose`, `-v`: Verbose output
- `--json`: Machine-readable JSON output format

### Integration
- Integrated into validate_claude_alignment.py hook for automatic parity validation on commit

### Test Coverage
- 1,145 unit tests (97%+ coverage)
- 666 integration tests (doc-master integration, hook blocking, end-to-end workflows)

### Used By
- doc-master agent (parity checklist)
- validate_claude_alignment.py hook (automatic validation)
- CLI validation scripts

### Related
- GitHub Issue #56 (automatic documentation parity validation in /auto-implement workflow)

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

## 12. math_utils.py (465 lines, v3.23.0+)

**Purpose**: Fibonacci calculator with multiple algorithm implementations

### Public API

#### `calculate_fibonacci(n, method='iterative')`
- **Purpose**: Calculate nth Fibonacci number using specified algorithm
- **Parameters**:
  - `n` (int): Non-negative integer index (0 <= n <= 10000)
  - `method` (str): Algorithm to use - 'iterative' (default), 'recursive', or 'matrix'
- **Returns**: `int` - The nth Fibonacci number
- **Raises**: 
  - `InvalidInputError` - If n is negative, > 10000, or not an integer
  - `MethodNotSupportedError` - If method is not recognized
- **Algorithms**:
  - **iterative**: O(n) time, O(1) space - Best for most cases
  - **recursive**: O(n) time with memoization - Good for n < 50
  - **matrix**: O(log n) time - Fastest for very large n

### Exception Hierarchy

#### `FibonacciError`
- Base exception for all fibonacci calculation errors

#### `InvalidInputError(FibonacciError)`
- Raised when input validation fails
- Includes: negative numbers, non-integers, values > 10000

#### `MethodNotSupportedError(FibonacciError)`
- Raised when unknown algorithm method specified
- Valid methods: 'iterative', 'recursive', 'matrix'

### Internal Functions

#### `_validate_input(n)`
- **Purpose**: Input validation with DoS prevention
- **Validation**:
  - Type check (must be int)
  - Range check (0 <= n <= 10000)
  - Security: Max value prevents DoS attacks

#### `_validate_method(method)`
- **Purpose**: Validate algorithm method selection
- **Allowed**: 'iterative', 'recursive', 'matrix'

#### `_fibonacci_iterative(n)`
- **Algorithm**: Iterative bottom-up calculation
- **Complexity**: O(n) time, O(1) space
- **Best for**: General use, n <= 10000

#### `_fibonacci_recursive(n)`
- **Algorithm**: Recursive with functools.lru_cache memoization
- **Complexity**: O(n) time with cache, O(n) space
- **Best for**: Small n (< 50), educational examples

#### `_fibonacci_matrix(n)`
- **Algorithm**: Matrix exponentiation
- **Complexity**: O(log n) time via divide-and-conquer
- **Best for**: Very large n, performance benchmarking

### Features

- **Multiple Algorithms**: Three implementations for different use cases
- **Input Validation**: Type checking, range validation, DoS prevention
- **Security Integration**: Audit logging via security_utils.py
- **Performance Optimized**: Algorithm selection guidance for different input ranges
- **Exception Hierarchy**: Custom exceptions following error-handling-patterns skill
- **Comprehensive Tests**: 73 unit tests covering all algorithms and edge cases

### Test Coverage

- **Total**: 73 tests in `tests/unit/lib/test_math_utils.py`
- **Coverage Areas**:
  - Input validation (negative, zero, large values, type errors)
  - Algorithm correctness (all three methods)
  - Exception handling (custom exception hierarchy)
  - Edge cases (F(0)=0, F(1)=1, large n)
  - Performance characteristics (algorithm selection)

### Usage Examples

```python
from plugins.autonomous_dev.lib.math_utils import calculate_fibonacci, InvalidInputError

# Basic usage (default iterative)
result = calculate_fibonacci(10)  # Returns: 55

# Explicit algorithm selection
result = calculate_fibonacci(100, method="matrix")  # Returns: 354224848179261915075

# Error handling
try:
    result = calculate_fibonacci(-5)
except InvalidInputError as e:
    print(f"Invalid input: {e}")  # Prints: "n must be non-negative (got -5)"

# Performance comparison
import time
n = 1000
for method in ['iterative', 'recursive', 'matrix']:
    start = time.time()
    result = calculate_fibonacci(n, method=method)
    elapsed = time.time() - start
    print(f"{method}: {elapsed:.6f}s")
```

### Security

- **DoS Prevention**: Maximum n=10000 prevents excessive computation
- **Input Validation**: Type and range checking before computation
- **Audit Logging**: All validation failures logged via security_utils
- **No Arbitrary Code**: Pure mathematical computation, no eval/exec

### Used By

- Educational examples and algorithm demonstrations
- Performance benchmarking and algorithm comparison
- Test data generation for large integer calculations

### Related Documentation

- See `error-handling-patterns` skill for exception hierarchy design
- See CLAUDE.md for library integration patterns

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

## 15. path_utils.py (187 lines, v3.28.0+)

**Purpose**: Dynamic PROJECT_ROOT detection and path resolution for tracking infrastructure

**Issue**: GitHub #79 - Fixes hardcoded paths that failed when running from subdirectories

### Key Features

- **Dynamic PROJECT_ROOT Detection**: Searches upward from current directory for `.git/` or `.claude/` markers
- **Caching**: Module-level cache prevents repeated filesystem searches
- **Flexible Creation**: Creates directories (docs/sessions, .claude) as needed with safe permissions (0o755)
- **Backward Compatible**: Existing usage patterns still work, uses get_project_root() internally

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

#### `reset_project_root_cache()`
- **Purpose**: Reset cached project root (testing only)
- **Warning**: Only use in test teardown; production code should maintain cache for process lifetime

### Test Coverage

- **Total**: 45+ tests in `tests/unit/test_tracking_path_resolution.py`
- **Areas**:
  - PROJECT_ROOT detection from various directories
  - Marker file priority (`.git` over `.claude`)
  - Nested `.claude/` handling in git repositories
  - Directory creation with safe permissions
  - Cache behavior and reset

### Usage Examples

```python
from plugins.autonomous_dev.lib.path_utils import (
    get_project_root,
    get_session_dir,
    get_batch_state_file
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

# Force re-detection (for tests that change cwd)
from tests.conftest import isolated_project
root = get_project_root(use_cache=False)
```

### Security

- **No Path Traversal**: Only searches upward, never downward
- **Safe Permissions**: Creates directories with 0o755 (rwxr-xr-x)
- **Validation**: Validates marker files exist before returning
- **Symlink Handling**: Resolves symlinks to canonical paths

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

### Related Documentation

- See `library-design-patterns` skill for design principles
- See Issue #79 for hardcoded path fixes and security implications

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
- **Reads**: `AGENT_NAME` environment variable set by orchestrator
- **Returns**: True if auto-tracking succeeded
- **Security**: Validates agent name format before logging

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

## 26. git_hooks.py (314 lines, v3.37.0+, Issue #94)

**Purpose**: Git hook utilities for larger projects with 500+ tests

**Problem Solved (Issue #94)**: Original git hooks couldn't scale for larger projects:
- Pre-commit hook used flat test discovery (missed nested directories like `tests/unit/lib/`)
- Pre-push hook ran ALL tests including slow/GenAI tests (2-5 minute execution time)
- No support for nested test structures (500+ tests across multiple levels)

**Solution**: Library-based implementation with:
- Recursive test discovery supporting unlimited nesting depth
- Fast test filtering (exclude slow, genai, integration markers)
- Test duration estimation for performance planning
- Hook generation utilities for installation/updates
- 3x+ performance improvement for pre-push hooks (30s vs 2-5min)

### Functions

#### `discover_tests_recursive(tests_dir: Path) -> List[Path]`
- **Purpose**: Discover all test files recursively in tests directory
- **Parameters**: `tests_dir` (Path): Path to tests directory
- **Returns**: Sorted list of paths to `test_*.py` files
- **Features**:
  - Uses `Path.rglob()` for recursive search
  - Excludes `__pycache__` directories automatically
  - Supports unlimited nesting depth (e.g., `tests/unit/lib/batch/state/`)
  - Returns empty list if tests directory doesn't exist
- **Example**:
  ```python
  tests = discover_tests_recursive(Path("tests"))
  print(f"Found {len(tests)} test files")
  # Output: Found 524 test files
  ```

#### `get_fast_test_command(tests_dir: Path, extra_args: str = "") -> str`
- **Purpose**: Build pytest command for running fast tests only
- **Parameters**:
  - `tests_dir` (Path): Path to tests directory
  - `extra_args` (str): Additional pytest arguments (optional)
- **Returns**: pytest command string with marker filtering
- **Features**:
  - Excludes `@pytest.mark.slow`, `@pytest.mark.genai`, `@pytest.mark.integration`
  - Uses minimal verbosity (`--tb=line -q`) to prevent output bloat
  - Prevents pipe deadlock issues (Issue #90)
- **Example**:
  ```python
  cmd = get_fast_test_command(Path("tests"))
  # Returns: 'pytest tests/ -m "not slow and not genai and not integration" --tb=line -q'
  ```

#### `filter_fast_tests(all_tests: List[str], tests_dir: Path) -> List[str]`
- **Purpose**: Filter test list to only fast tests (exclude slow, genai, integration)
- **Parameters**:
  - `all_tests` (List[str]): List of all test file names
  - `tests_dir` (Path): Path to tests directory
- **Returns**: List of fast test file names
- **Features**:
  - Reads test files to check for pytest markers
  - Tests without markers or with only non-slow markers are considered fast
  - Handles nested test files (tries direct path first, then recursive search)
  - Gracefully handles unreadable files (skips them)
- **Example**:
  ```python
  all_tests = ["test_fast.py", "test_slow.py", "test_genai.py"]
  fast = filter_fast_tests(all_tests, Path("tests"))
  # Returns: ["test_fast.py"]
  ```

#### `estimate_test_duration(tests_dir: Path, fast_only: bool = False) -> float`
- **Purpose**: Estimate test execution duration in seconds
- **Parameters**:
  - `tests_dir` (Path): Path to tests directory
  - `fast_only` (bool): If True, estimate fast tests only
- **Returns**: Estimated duration in seconds
- **Estimation Model**:
  - Fast tests: ~3 seconds each
  - Slow tests: ~30 seconds each
  - GenAI tests: ~60 seconds each
  - Integration tests: ~20 seconds each
- **Example**:
  ```python
  fast_duration = estimate_test_duration(Path("tests"), fast_only=True)
  full_duration = estimate_test_duration(Path("tests"), fast_only=False)
  print(f"Fast: {fast_duration}s, Full: {full_duration}s")
  # Output: Fast: 90s, Full: 450s
  ```

#### `run_pre_push_tests(tests_dir: Path) -> TestRunResult`
- **Purpose**: Run pre-push tests (fast only)
- **Parameters**: `tests_dir` (Path): Path to tests directory
- **Returns**: `TestRunResult` with exit code and output
- **Features**:
  - Executes pytest with fast test filtering
  - Handles pytest not being installed gracefully (non-blocking)
  - Uses `shlex.split()` to properly handle quoted strings
  - Treats "no tests collected" (exit code 5) as success
  - Treats "all deselected" as success (when markers filter everything)
- **Example**:
  ```python
  result = run_pre_push_tests(Path("tests"))
  if result.returncode == 0:
      print("Tests passed!")
  else:
      print(f"Tests failed: {result.output}")
  ```

#### `generate_pre_commit_hook() -> str`
- **Purpose**: Generate pre-commit hook content with recursive test discovery
- **Returns**: Pre-commit hook bash script content
- **Features**:
  - Uses `find tests -type f -name "test_*.py"` for recursion
  - Excludes `__pycache__` directories
  - Counts tests with `wc -l` for validation
- **Example**:
  ```python
  hook_content = generate_pre_commit_hook()
  Path(".git/hooks/pre-commit").write_text(hook_content)
  ```

#### `generate_pre_push_hook() -> str`
- **Purpose**: Generate pre-push hook content with fast test filtering
- **Returns**: Pre-push hook bash script content
- **Features**:
  - Runs only fast tests (excludes slow, genai, integration markers)
  - Uses `--tb=line -q` for minimal output
  - Non-blocking if pytest not installed
  - Clear user guidance on bypass and failure messages
- **Example**:
  ```python
  hook_content = generate_pre_push_hook()
  Path(".git/hooks/pre-push").write_text(hook_content)
  ```

### Classes

#### `TestRunResult`
- **Purpose**: Result of test execution
- **Attributes**:
  - `returncode` (int): Exit code from pytest (0=success, non-zero=failure)
  - `output` (str): Combined stdout and stderr output

### Performance

**Before (Issue #94)**:
- Pre-commit: Missed nested tests (flat discovery only)
- Pre-push: 2-5 minutes (ran all 500+ tests including slow/GenAI)

**After (Issue #94)**:
- Pre-commit: Finds all tests recursively (100% coverage)
- Pre-push: 30 seconds (runs ~30 fast tests only)
- **Improvement**: 3x+ faster pre-push, complete test discovery

### Security

#### Command Execution (CWE-78)
- Uses `shlex.split()` for safe command parsing
- No user input in command construction
- Plugin name validation (alphanumeric, dash, underscore only)

#### Path Handling (CWE-22)
- All paths validated via security_utils (if integrated)
- Uses Path objects for safe path manipulation
- Rejects path traversal patterns

### Error Handling

All functions handle errors gracefully:
- Missing pytest: Non-blocking warning message
- Missing tests directory: Returns empty list
- Unreadable test files: Skips and continues
- No tests collected: Treats as success (not failure)

### Test Coverage
- 28 comprehensive tests in `tests/unit/hooks/test_git_hooks_issue94.py`:
  - 9 pre-commit recursive discovery tests
  - 9 pre-push fast test filtering tests
  - 4 hook generation tests
  - 4 edge case tests
  - 2 integration tests

### Used By
- `scripts/hooks/pre-commit` - Git pre-commit hook (test discovery)
- `scripts/hooks/pre-push` - Git pre-push hook (fast test execution)
- Hook activator during plugin installation/updates

### Related
- GitHub Issue #94 (Git hooks for larger projects with 500+ tests)
- GitHub Issue #90 (Pre-push hook pipe deadlock fix - minimal verbosity)
- `docs/HOOKS.md` - Hook documentation and usage
- `scripts/hooks/` - Hook implementations

### Design Patterns
- **Two-tier Design**: Library (core logic) + Hook scripts (interface)
- **Non-blocking**: Missing pytest or tests don't block git operations
- **Progressive Enhancement**: Hooks work with any test count (1 to 1000+)
- **Security First**: Safe command execution and path handling

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
- [MCP-SECURITY.md](../docs/MCP-SECURITY.md) - Comprehensive security guide
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
- [MCP-SECURITY.md](../docs/MCP-SECURITY.md) - Comprehensive security guide
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
- [MCP-SECURITY.md](../docs/MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/mcp_security_enforcer.py` - Hook implementation

