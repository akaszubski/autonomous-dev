# Shared Libraries Reference

**Last Updated**: 2025-11-18
**Purpose**: Comprehensive API documentation for autonomous-dev shared libraries

This document provides detailed API documentation for all 27 shared libraries in `plugins/autonomous-dev/lib/`. For high-level overview, see [CLAUDE.md](../CLAUDE.md) Architecture section.

## Overview

The autonomous-dev plugin includes **27 shared libraries** organized into six categories:

### Core Libraries (16)

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

### Installation Libraries (4) - NEW in v3.29.0

17. **file_discovery.py** - Comprehensive file discovery with exclusion patterns (Issue #80)
18. **copy_system.py** - Structure-preserving file copying with permission handling (Issue #80)
19. **installation_validator.py** - Coverage validation and missing file detection (Issue #80)
20. **install_orchestrator.py** - Coordinates complete installation workflows (Issue #80)

### Utility Libraries (1)

21. **math_utils.py** - Fibonacci calculator with multiple algorithms

### Brownfield Retrofit Libraries (6)

22. **brownfield_retrofit.py** - Phase 0: Project analysis and tech stack detection
23. **codebase_analyzer.py** - Phase 1: Deep codebase analysis (multi-language)
24. **alignment_assessor.py** - Phase 2: Gap assessment and 12-Factor compliance
25. **migration_planner.py** - Phase 3: Migration plan with dependency tracking
26. **retrofit_executor.py** - Phase 4: Step-by-step execution with rollback
27. **retrofit_verifier.py** - Phase 5: Verification and readiness assessment (27 total libraries)

## Design Patterns

- **Progressive Enhancement**: String → path → whitelist validation for graceful error recovery
- **Non-blocking Enhancement**: Enhancements don't block core operations
- **Two-tier Design**: Core logic + CLI interface for reusability and testing
- **Security First**: All file operations validated via security_utils.py

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
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

## 5. sync_dispatcher.py (976 lines, v3.7.1+)

**Purpose**: Intelligent sync orchestration with version detection and cleanup

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

# File-based batch
state = create_batch_state(
    features=["Add login", "Add logout"],
    state_file=Path(".claude/batch_state.json"),
    features_file="features.txt"
)

# GitHub issues batch (v3.24.0)
state = create_batch_state(
    features=["Issue #72: Add logging", "Issue #73: Fix bug"],
    state_file=Path(".claude/batch_state.json"),
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
state = create_batch_state(
    features=features,
    state_file=".claude/batch_state.json",
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

## 17. file_discovery.py (310 lines, v3.29.0+)

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

**Built-in patterns** (configurable):
- Cache: `__pycache__`, `.pytest_cache`, `.eggs`, `*.egg-info`
- Build artifacts: `*.pyc`, `*.pyo`, `*.pyd`
- Version control: `.git`, `.gitignore`, `.gitattributes`
- IDE: `.vscode`, `.idea`
- Temp/backup: `*.tmp`, `*.bak`, `*.log`, `*~`, `*.swp`, `*.swo`
- System: `.DS_Store`

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

## 18. copy_system.py (244 lines, v3.29.0+)

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

## 19. installation_validator.py (586 lines, v3.29.0+ → v3.29.1)

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

### Key Methods

#### `InstallationValidator.validate()`
- **Purpose**: Validate complete installation
- **Returns**: `ValidationResult`
- **Features**:
  - File coverage calculation (actual/expected * 100)
  - Missing file detection (source files not in destination)
  - Extra file detection (unexpected files in destination)
  - Directory structure validation
  - Detailed reporting

#### `InstallationValidator.validate_sizes()` - NEW in v3.29.1
- **Purpose**: Validate file sizes against manifest
- **Parameters**: None (uses internal manifest)
- **Returns**: `Dict` with `sizes_match` (bool) and `size_errors` (List[str])
- **Raises**: `ValidationError` if no manifest provided
- **Features**: Detects corrupted downloads or partial installs

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

## 20. install_orchestrator.py (495 lines, v3.29.0+)

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
1. Discover all files
2. Copy with structure preservation
3. Validate coverage (expect 95%+)
4. Create installation marker
5. Activate hooks (optional)

**Upgrade Install**:
1. Create timestamped backup
2. Discover all files
3. Copy with preservation of user files
4. Validate coverage
5. Update installation marker
6. Rollback on failure

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

## Design Pattern

**Progressive Enhancement**: Libraries use string → path → whitelist validation pattern, allowing graceful error recovery

**Non-blocking Enhancements**: Version detection, orphan cleanup, hook activation, parity validation, git automation, issue automation, and brownfield retrofit don't block core operations

**Two-tier Design**:
- Core logic libraries (plugin_updater.py, auto_implement_git_integration.py, brownfield_retrofit.py + 5 phase libraries)
- CLI interface scripts (update_plugin.py, auto_git_workflow.py, align_project_retrofit.py)
- Enables reuse and testing
- Note: /create-issue uses direct gh CLI (no wrapper library)

**Optional Features**: Feature automation and other enhancements are controlled by flags/hooks

---

**For usage examples and integration patterns**: See CLAUDE.md Architecture section and individual command documentation
