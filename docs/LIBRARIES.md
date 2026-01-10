# Shared Libraries Reference

**Last Updated**: 2026-01-09 (Issue #225 - Consolidate exception hierarchy: All state managers now use StateError)
**Purpose**: Comprehensive API documentation for autonomous-dev shared libraries

This document provides detailed API documentation for shared libraries in `plugins/autonomous-dev/lib/` and `plugins/autonomous-dev/scripts/`. For high-level overview, see [CLAUDE.md](../CLAUDE.md) Architecture section.

## Overview

The autonomous-dev plugin includes shared libraries organized into the following categories:

### Core Libraries (51)

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
11. **abstract_state_manager.py** - StateManager ABC for standardized state management (NEW v1.0.0, Issue #220)
12. **batch_state_manager.py** - State persistence for /batch-implement with automatic context management (v3.23.0, Issue #218: deprecated context clearing functions removed v3.46.0, Issue #221: now inherits from StateManager ABC)
13. **github_issue_fetcher.py** - GitHub issue fetching via gh CLI (v3.24.0)
14. **github_issue_closer.py** - Auto-close GitHub issues after /auto-implement (v3.22.0, Issue #91)
15. **path_utils.py** - Dynamic PROJECT_ROOT detection and path resolution (v3.28.0, Issue #79)
16. **validation.py** - Tracking infrastructure security validation (v3.28.0, Issue #79)
17. **failure_classifier.py** - Error classification (transient vs permanent) for /batch-implement (v3.33.0, Issue #89)
18. **batch_retry_manager.py** - Retry orchestration with circuit breaker for /batch-implement (v3.33.0, Issue #89)
19. **batch_retry_consent.py** - First-run consent handling for automatic retry (v3.33.0, Issue #89)
20. **session_tracker.py** - Session logging for agent actions with portable path detection (v3.28.0+, Issue #79)
21. **settings_merger.py** - Merge settings.local.json with template configuration (v3.39.0, Issue #98)
22. **settings_generator.py** - Generate settings.local.json with specific command patterns (NO wildcards) (v3.43.0+, Issue #115)
23. **feature_dependency_analyzer.py** - Smart dependency ordering for /batch-implement (v1.0.0, Issue #157)
24. **acceptance_criteria_parser.py** - Parse acceptance criteria from GitHub issues for UAT generation (v3.45.0+, Issue #161)
25. **test_tier_organizer.py** - Classify and organize tests into unit/integration/uat tiers (v3.45.0+, Issue #161)
26. **test_validator.py** - Execute tests and validate TDD workflow with quality gates (v3.45.0+, Issue #161)
27. **tech_debt_detector.py** - Proactive code quality issue detection (large files, circular imports, dead code, complexity) (v1.0.0, Issue #162)
28. **scope_detector.py** - Scope analysis and complexity detection for issue decomposition (v1.0.0)
29. **completion_verifier.py** - Pipeline verification with loop-back retry and circuit breaker (v1.0.0)
30. **hook_exit_codes.py** - Standardized exit code constants and lifecycle constraints for all hooks (v4.0.0+)
31. **worktree_manager.py** - Git worktree isolation for safe feature development (v1.0.0, Issue #178)
32. **complexity_assessor.py** - Automatic complexity assessment for pipeline scaling (v1.0.0, Issue #181)
33. **pause_controller.py** - File-based pause controls and human input handling for workflows (v1.0.0, Issue #182)
34. **worktree_command.py** - Interactive CLI for git worktree management (list, status, review, merge, discard) (v1.0.0, Issue #180)
35. **sandbox_enforcer.py** - Command classification and sandboxing for permission reduction (v1.0.0, Issue #171)
36. **status_tracker.py** - Test status tracking for pre-commit gate enforcement (v3.48.0+, Issue #174)
37. **headless_mode.py** - CI/CD integration support for headless/non-interactive environments (v1.0.0, Issue #176)
38. **qa_self_healer.py** - Orchestrate automatic test healing with fix iterations (v1.0.0, Issue #184)
39. **failure_analyzer.py** - Parse pytest output to extract failure details (v1.0.0, Issue #184)
40. **code_patcher.py** - Atomic file patching with backup and rollback (v1.0.0, Issue #184)
41. **stuck_detector.py** - Detect infinite healing loops from repeated identical errors (v1.0.0, Issue #184)
42. **ralph_loop_manager.py** - Retry loop orchestration with circuit breaker and validation strategies (v1.0.0, Issue #189)
43. **success_criteria_validator.py** - Validation strategies for agent task completion (v1.0.0, Issue #189)
44. **feature_flags.py** - Optional feature configuration with graceful degradation (v1.0.0, Issue #193)
45. **worktree_conflict_integration.py** - Conflict resolver integration into worktree workflow (v1.0.0, Issue #193)
46. **comprehensive_doc_validator.py** - Cross-reference validation between documentation files (708 lines, v1.0.0, Issue #198)
47. **test_runner.py** - Autonomous test execution with structured TestResult (v1.0.0, Issue #200)
48. **code_path_analyzer.py** - Discover code paths matching patterns for debug-first enforcement (v1.0.0, Issue #200)
49. **doc_update_risk_classifier.py** - Risk classification for documentation updates (auto-apply vs approval) (v1.0.0, Issue #204)
50. **doc_master_auto_apply.py** - Auto-apply LOW_RISK documentation updates with user approval for HIGH_RISK changes (v1.0.0, Issue #204)
51. **auto_implement_pipeline.py** - Pipeline integration for project-progress-tracker invocation after doc-master (v1.0.0, Issue #204)



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

## 70. qa_self_healer.py (16360 bytes, v1.0.0 - Issue #184)

**Purpose**: Orchestrate automatic test healing with fix iterations to resolve test failures without manual intervention.

**Problem**: When tests fail during development, engineers must manually analyze error messages, implement fixes, and re-run tests. This is repetitive and error-prone for simple issues (missing colons, typos, incorrect imports).

**Solution**: Self-healing QA orchestrator that automatically detects failures, analyzes errors, generates fixes, applies patches, and retries until all tests pass or max iterations/stuck detection reached.

**Location**: `plugins/autonomous-dev/lib/qa_self_healer.py`

**Key Features**:
- Iterative healing loop (max 10 iterations by default)
- Multi-failure handling (fix all failures in each iteration)
- Stuck detection (3 identical errors triggers circuit breaker)
- Environment variable controls (SELF_HEAL_ENABLED, SELF_HEAL_MAX_ITERATIONS)
- Audit logging for all healing attempts
- Atomic rollback on patch failure

### Classes

#### `SelfHealingResult`
Result object from healing operation with full history and outcome.

**Attributes**:
- `success: bool` - True if all tests pass after healing
- `iterations: int` - Number of healing iterations performed
- `attempts: List[HealingAttempt]` - Detailed history of each attempt
- `final_test_output: str` - Final pytest output
- `stuck_detected: bool` - True if stuck detector triggered
- `max_iterations_reached: bool` - True if hit iteration limit
- `error_message: str` - Error details if healing failed

#### `HealingAttempt`
Single healing attempt in the loop.

**Attributes**:
- `iteration: int` - Attempt number (1-indexed)
- `failures: List[FailureAnalysis]` - Errors found in test output
- `fixes_generated: int` - Number of fixes attempted
- `fixes_applied: int` - Number of fixes successfully applied
- `timestamp: str` - When attempt occurred

#### `QASelfHealer`
Main orchestrator for self-healing workflow.

**Constructor**:
```python
QASelfHealer(
    test_dir: Optional[Path] = None,
    max_iterations: int = 10,
    enabled: bool = True,
    stuck_threshold: int = 3
)
```

**Parameters**:
- `test_dir` - Test directory (default: current directory)
- `max_iterations` - Max healing iterations (default: 10, overridable via SELF_HEAL_MAX_ITERATIONS env var)
- `enabled` - Enable self-healing (default: True, overridable via SELF_HEAL_ENABLED env var)
- `stuck_threshold` - Stuck detection threshold (default: 3 consecutive identical errors)

### Methods

#### `heal_test_failures(test_command)`

Run self-healing loop to fix all test failures.

**Parameters**:
- `test_command: Optional[List[str]]` - Test command to execute (default: ["pytest"])

**Returns**: `SelfHealingResult` with outcome and full history

**Logic**:
```
Loop (max iterations):
  1. Run tests
  2. If all pass → return SUCCESS
  3. Parse failures from output
  4. Check stuck detector (3 identical errors → STOP)
  5. Generate fixes for all failures
  6. Apply fixes atomically
  7. Record attempt
  8. Repeat
```

### Functions

#### `heal_test_failures(test_command, max_iterations, enabled)`

Convenience function for one-shot healing.

**Parameters**:
- `test_command: Optional[List[str]]` - Test command (default: ["pytest"])
- `max_iterations: int` - Max iterations (default: 10)
- `enabled: bool` - Enable healing (default: True)

**Returns**: `SelfHealingResult`

**Usage**:
```python
from qa_self_healer import heal_test_failures

result = heal_test_failures(["pytest", "tests/"])
if result.success:
    print(f"All tests passing after {result.iterations} iterations!")
elif result.stuck_detected:
    print("Stuck - same error repeating, needs manual fix")
```

#### `run_tests_with_healing(test_command, max_iterations)`

High-level entry point for test execution with automatic healing.

**Parameters**:
- `test_command: Optional[List[str]]` - Test command
- `max_iterations: int` - Max healing iterations

**Returns**: `SelfHealingResult`

### Design Patterns

- **Iterative Healing**: Loop until success, stuck, or max iterations
- **Multi-failure Handling**: Process all failures in each iteration (faster convergence)
- **Circuit Breaker**: Stuck detector prevents infinite loops
- **Atomic Operations**: Patches applied atomically, rollback on failure
- **Audit Trail**: All attempts logged for debugging

### Integration Points

**test-master Agent**: Uses `heal_test_failures()` to automatically fix failing tests after TDD red phase

**Other Libraries**:
- `failure_analyzer.py` - Parse pytest output
- `code_patcher.py` - Apply atomic fixes
- `stuck_detector.py` - Detect infinite loops

### Security

- No arbitrary code execution (only applies pre-generated fixes)
- Path validation via `code_patcher.py` (CWE-22, CWE-59 prevention)
- Atomic writes prevent partial updates
- Backup creation for rollback

### Performance

- Iteration 1: 2-5 seconds (test run + analysis + fix)
- Subsequent iterations: 1-3 seconds each
- Typical convergence: 2-4 iterations for simple fixes
- Max iterations: 10 (configurable)
- Timeout: None (relies on underlying test runner)

### Test Coverage

- Successful healing (syntax errors, typos, missing imports)
- Stuck detection (circuit breaker)
- Max iterations reached
- Atomic rollback on patch failure
- Environment variable control

### Version History

- v1.0.0 (2026-01-02) - Initial release with iterative healing loop (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

## 71. failure_analyzer.py (13606 bytes, v1.0.0 - Issue #184)

**Purpose**: Parse pytest output to extract structured failure information for automated fix generation.

**Problem**: Test failure messages contain mixed stdout/stderr with variable formats. Manual parsing is error-prone. Need structured data (error type, file, line, message) to generate fixes.

**Solution**: Parse pytest output with multi-error type detection and extract file path, line number, error type, and stack trace.

**Location**: `plugins/autonomous-dev/lib/failure_analyzer.py`

**Key Features**:
- Multi-error type detection (syntax, import, assertion, type, runtime)
- File path and line number extraction
- Stack trace extraction for debugging
- Test name extraction from pytest format
- Graceful handling of malformed/empty output

### Classes

#### `FailureAnalysis`
Structured representation of a single test failure.

**Attributes**:
- `test_name: str` - Test function/class name
- `file_path: str` - File containing the error
- `line_number: int` - Line number of error
- `error_type: str` - Classification: syntax, import, assertion, type, runtime
- `error_message: str` - Human-readable error message
- `stack_trace: str` - Full stack trace for debugging

#### `FailureAnalyzer`
Parser for pytest output.

**Constructor**:
```python
FailureAnalyzer()
```

No parameters required.

### Methods

#### `parse_pytest_output(output)`

Parse raw pytest output to extract all failures.

**Parameters**:
- `output: str` - Raw pytest stdout/stderr

**Returns**: `List[FailureAnalysis]` (empty list if no failures or malformed output)

**Error Types**:
- `syntax` - SyntaxError, IndentationError, invalid syntax
- `import` - ImportError, ModuleNotFoundError
- `assertion` - AssertionError, assertion failed
- `type` - TypeError, AttributeError, NameError
- `runtime` - ZeroDivisionError, KeyError, IndexError, ValueError, etc.

**Graceful Degradation**:
- Malformed output returns empty list (no crashes)
- Missing fields populated with defaults
- Graceful handling of variable pytest output formats

### Functions

#### `parse_pytest_output(output)`

Convenience function for one-shot parsing.

**Parameters**:
- `output: str` - Raw pytest output

**Returns**: `List[FailureAnalysis]`

**Usage**:
```python
from failure_analyzer import parse_pytest_output

output = subprocess.check_output(["pytest", "tests/"], text=True)
failures = parse_pytest_output(output)

for failure in failures:
    print(f"{failure.error_type}: {failure.file_path}:{failure.line_number}")
    print(f"  {failure.error_message}")
```

#### `extract_error_details(output)`

Extract detailed error information (alias for parse_pytest_output).

**Parameters**:
- `output: str` - Raw pytest output

**Returns**: `List[FailureAnalysis]`

### Design Patterns

- **Graceful Degradation**: Malformed output doesn't crash
- **Progressive Disclosure**: Only extract needed fields
- **Bounded Output**: No memory exhaustion on large outputs
- **Regex-based Parsing**: No code execution risk

### Integration Points

**qa_self_healer.py**: Uses to parse test failures for fix generation

**test-master Agent**: May use for detailed error analysis

**Other Libraries**:
- No dependencies on other libraries

### Security

- No arbitrary code execution
- Safe regex parsing (no ReDoS vulnerabilities)
- Bounded output (prevents memory exhaustion)
- Sanitized error messages (no injection risk)

### Performance

- Small output (<1KB): <10ms
- Large output (100KB+): <100ms
- Linear time complexity relative to output size
- Memory usage bounded by output size

### Test Coverage

- Multi-error type detection (syntax, import, assertion, type, runtime)
- File path and line number extraction
- Stack trace extraction
- Test name extraction
- Malformed output handling
- Edge cases: Empty output, no failures, large files

### Version History

- v1.0.0 (2026-01-02) - Initial release with multi-error type detection (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

## 72. code_patcher.py (11241 bytes, v1.0.0 - Issue #184)

**Purpose**: Safely apply code fixes with atomic writes, backup creation, and rollback support.

**Problem**: Applying code patches requires careful handling to prevent corruption. Need atomic writes, backup creation, and rollback on failure.

**Solution**: Atomic file patching with backup directory, temporary file writes, and rollback support. Validates paths for security (CWE-22, CWE-59).

**Location**: `plugins/autonomous-dev/lib/code_patcher.py`

**Key Features**:
- Atomic write pattern (temp file -> rename)
- Automatic backup creation before patching
- Rollback support for failed patches
- File permissions preservation
- Security validation (CWE-22, CWE-59)

### Classes

#### `ProposedFix`
Proposed code fix with metadata.

**Attributes**:
- `file_path: str` - File to patch (relative or absolute)
- `original_code: str` - Original code snippet
- `fixed_code: str` - Replacement code
- `strategy: str` - Fix strategy (e.g., "add_colon", "fix_import")
- `confidence: float` - Confidence score (0.0-1.0)

#### `CodePatcher`
Main patcher for atomic file updates.

**Constructor**:
```python
CodePatcher(backup_dir: Optional[Path] = None)
```

**Parameters**:
- `backup_dir` - Directory for backups (default: system temp directory)

### Methods

#### `apply_patch(fix)`

Apply code fix with atomic write and backup.

**Parameters**:
- `fix: ProposedFix` - Fix details

**Returns**: `bool` - True if patch applied successfully

**Process**:
1. Validate patch path (CWE-22, CWE-59)
2. Create backup of original file
3. Apply fix via atomic write (temp + rename)
4. Verify patch applied
5. Return success status

**Error Handling**:
- Path traversal attempts rejected
- Symlink attacks prevented
- Atomic writes ensure no corruption
- Backup preserved on failure

#### `rollback_last_patch()`

Rollback the most recent patch from backup.

**Returns**: `bool` - True if rollback successful

#### `cleanup_backups()`

Remove all backups after successful healing.

**Returns**: `bool` - True if cleanup successful

### Functions

#### `validate_patch_path(file_path)`

Validate file path for security issues.

**Parameters**:
- `file_path: Path` - File path to validate

**Raises**: `ValueError` if path is invalid (path traversal, symlink, etc.)

**Prevents**:
- CWE-22 (path traversal via ..)
- CWE-59 (symlink attacks)
- Absolute paths outside project

#### `apply_patch(fix, backup_dir)`

Convenience function for one-shot patching.

**Parameters**:
- `fix: ProposedFix` - Fix details
- `backup_dir: Optional[Path]` - Backup directory

**Returns**: `bool` - True if patch applied

**Usage**:
```python
from code_patcher import apply_patch, ProposedFix

fix = ProposedFix(
    file_path="test.py",
    original_code="def foo()",
    fixed_code="def foo():",
    strategy="add_colon",
    confidence=0.95
)

if apply_patch(fix):
    print("Patch applied successfully")
else:
    print("Patch failed")
```

#### `create_backup(file_path, backup_dir)`

Create backup of file.

**Parameters**:
- `file_path: Path` - File to backup
- `backup_dir: Optional[Path]` - Backup directory

**Returns**: `Path` - Backup file path

#### `rollback_patch(file_path, backup_dir)`

Rollback file from backup.

**Parameters**:
- `file_path: Path` - File to restore
- `backup_dir: Optional[Path]` - Backup directory

**Returns**: `bool` - True if rollback successful

#### `cleanup_backups(backup_dir)`

Remove all backups.

**Parameters**:
- `backup_dir: Optional[Path]` - Backup directory to clean

**Returns**: `bool` - True if cleanup successful

### Design Patterns

- **Atomic Writes**: Temporary file + rename prevents partial updates
- **Backup First**: Create backup before any modifications
- **Rollback Support**: Quick recovery from failed patches
- **Path Validation**: Security-first approach

### Integration Points

**qa_self_healer.py**: Uses to apply atomic fixes to test files

**Other Libraries**:
- `security_utils.py` - May use for additional path validation

### Security

- CWE-22: Path traversal prevention (reject .., absolute paths)
- CWE-59: Symlink attack prevention (reject symlinks)
- Atomic writes prevent partial updates
- Backup directory isolation
- File permissions preservation

### Performance

- Backup creation: 1-10ms
- Atomic write: 2-20ms
- Rollback: 1-10ms
- Cleanup: 5-50ms
- Scales with file size (large files take longer)

### Test Coverage

- Successful patch application
- Atomic write verification
- Backup creation and rollback
- Path validation (traversal, symlinks)
- File permissions preservation
- Error handling and recovery

### Version History

- v1.0.0 (2026-01-02) - Initial release with atomic writes and backup/rollback (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

## 73. stuck_detector.py (5453 bytes, v1.0.0 - Issue #184)

**Purpose**: Detect infinite healing loops from repeated identical errors to prevent wasted iterations.

**Problem**: Self-healing loop can get stuck if the same error repeats (e.g., fix doesn't address root cause). Need to detect this and stop to avoid infinite iterations.

**Solution**: Track error signatures and trigger circuit breaker when same error appears N consecutive times (default: 3).

**Location**: `plugins/autonomous-dev/lib/stuck_detector.py`

**Key Features**:
- Error signature computation (normalized for comparison)
- Consecutive error tracking
- Configurable stuck threshold (default: 3)
- Reset on successful test run
- Thread-safe operation

### Constants

- `DEFAULT_STUCK_THRESHOLD` - Default threshold for stuck detection (3)

### Classes

#### `StuckDetector`
Detector for infinite healing loops.

**Constructor**:
```python
StuckDetector(threshold: int = 3)
```

**Parameters**:
- `threshold: int` - Consecutive identical errors before stuck (default: 3)

### Methods

#### `record_error(error_signature)`

Record an error signature for stuck detection.

**Parameters**:
- `error_signature: str` - Normalized error signature (file + line + error type)

**Thread-safe**: Uses internal lock

#### `is_stuck()`

Check if stuck detector triggered.

**Returns**: `bool` - True if threshold reached (3+ consecutive identical errors)

#### `reset()`

Reset stuck detector after successful iteration.

**Parameters**: None

#### `compute_error_signature(failures)`

Compute normalized error signature from failures.

**Parameters**:
- `failures: List[FailureAnalysis]` - Parsed test failures

**Returns**: `str` - Normalized signature for comparison

### Functions

#### `is_stuck()`

Check global stuck status (singleton).

**Returns**: `bool` - True if stuck

#### `reset_stuck_detection()`

Reset global stuck detector (singleton).

**Parameters**: None

### Stuck Detection Logic

1. Compute error signature (file + line + error type)
2. Compare with previous errors
3. If same signature appears N times consecutively -> STUCK
4. Otherwise -> continue healing
5. On test success -> reset detector

### Design Patterns

- **Singleton Pattern**: Global stuck detector instance
- **Signature Normalization**: Ignore message text, focus on error location/type
- **Bounded Memory**: Only store recent error history
- **Thread-safe**: Uses locks for concurrent access

### Integration Points

**qa_self_healer.py**: Uses to check for stuck loops before continuing iterations

**Other Libraries**:
- Works with `failure_analyzer.py` for error signatures

### Security

- No code execution
- Bounded memory (only stores recent signatures)
- Thread-safe with locks
- No credential exposure

### Performance

- record_error(): <0.1ms
- is_stuck(): <0.1ms
- reset(): <0.1ms
- compute_error_signature(): <1ms
- Memory usage: O(n) where n = max_history

### Test Coverage

- Error signature computation
- Consecutive error tracking
- Circuit breaker threshold
- Reset on success
- Thread safety
- Edge cases: Empty signature, rapid errors

### Version History

- v1.0.0 (2026-01-02) - Initial release with circuit breaker threshold (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

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

## 5. sync_dispatcher package (Issue #164 - Refactored from 2,074 LOC monolithic file into 4 focused modules)

**Purpose**: Intelligent sync orchestration with version detection and cleanup (Issue #97: Fixed sync directory silent failures)

**Package Structure**: Refactored from monolithic sync_dispatcher.py (2,074 LOC) into focused package with 4 modules (Issue #164):
- models.py (158 lines): Data structures (SyncResult, SyncDispatcherError, SyncError)
- modes.py (749 lines): Mode-specific dispatch functions (marketplace, env, plugin-dev, github)
- dispatcher.py (1,017 lines): Main SyncDispatcher class with orchestration logic and _sync_directory() method
- cli.py (262 lines): CLI interface and convenience functions (dispatch_sync, main)

**Backward Compatibility**: All existing imports continue working via re-export shim (sync_dispatcher.py)

**Import Patterns**:
- Old (still works): `from sync_dispatcher import SyncResult, SyncDispatcher, dispatch_sync`
- New (preferred): `from sync_dispatcher.models import SyncResult` or `from sync_dispatcher.dispatcher import SyncDispatcher`

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

#### main() (CLI wrapper - NEW Issue #127, v3.7.1+)
- **Purpose**: Command-line interface wrapper for sync_dispatcher package
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
- **Implementation**: Embedded in cli.py module
- **Used By**: /sync command (delegates to main() via subprocess)

### Security
- All paths validated via security_utils
- Audit logging to security audit (marketplace_sync events)

### Test Coverage
- Comprehensive testing of all sync modes
- Backward compatibility tests verify re-export shim

### Used By
- /sync command
- sync_marketplace() high-level API
- plugin_updater.py (import utilities)

### Related
- GitHub Issues #47, #50, #51, #164 (refactoring)
- Issue #97 (Fixed sync directory silent failures)
- Issue #127 (CLI wrapper added)

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

## 12. abstract_state_manager.py (428 lines, NEW v1.0.0, Issue #220)

**Purpose**: Abstract Base Class (ABC) for standardized state management across all state managers.

**Problem**: Multiple state managers (batch_state_manager, session_tracker state management) had duplicate implementations of:
- Path validation and security checks (CWE-22 path traversal, CWE-59 symlinks)
- Atomic file writes with temp file + rename
- File locking for thread safety
- Audit logging for security events

**Solution**: StateManager ABC defines the contract for state management with concrete helper methods for security and atomicity.

**Note (Issue #221)**: BatchStateManager now inherits from StateManager[BatchState] to implement standardized state management interface while maintaining backward compatibility.

### Abstract Methods (must be implemented by subclasses)

#### `load_state() -> T`
- **Purpose**: Load state from persistent storage
- **Returns**: State object of type T
- **Raises**: StateError if load fails

#### `save_state(state: T) -> None`
- **Purpose**: Save state to persistent storage
- **Parameters**: `state` - State object to save
- **Raises**: StateError if save fails

#### `cleanup_state() -> None`
- **Purpose**: Clean up state (remove files, etc.)
- **Raises**: StateError if cleanup fails

### Concrete Helper Methods

#### `exists() -> bool`
- **Purpose**: Check if state file exists
- **Returns**: True if state file exists, False otherwise

#### `_validate_state_path(path: Path) -> Path`
- **Purpose**: Validate state file path for security
- **Security**:
  - CWE-22 (Path Traversal): Prevents `../` sequences
  - CWE-59 (Symlink Following): Detects and rejects symlinks
- **Parameters**: `path` - Path to validate
- **Returns**: Resolved, validated path
- **Raises**: ValueError if path is invalid

#### `_atomic_write(path: Path, content: str, mode: int = 0o600) -> None`
- **Purpose**: Write file atomically with permissions
- **Security**:
  - CWE-367 (Race Condition): Temp file + atomic rename
  - CWE-732 (File Permissions): Sets file to read-only (0o600)
- **Parameters**:
  - `path` - File to write
  - `content` - Content to write
  - `mode` - File permissions (default: 0o600)
- **Raises**: IOError if write fails

#### `_get_file_lock(path: Path) -> threading.RLock`
- **Purpose**: Get reentrant lock for thread-safe file access
- **Parameters**: `path` - File path
- **Returns**: Reentrant lock for the file
- **Thread Safety**: Multiple threads can acquire the same lock

#### `_audit_operation(operation: str, status: str, details: Dict[str, Any]) -> None`
- **Purpose**: Log security-relevant operations
- **Parameters**:
  - `operation` - Operation type (e.g., "state_save")
  - `status` - Result status ("success", "failure", "warning")
  - `details` - Context details for audit log

### Usage Pattern

```python
from abc import ABC, TypeVar
from pathlib import Path
from abstract_state_manager import StateManager

T = TypeVar('T')  # Generic state type

class MyState:
    """Your state data class."""
    def to_dict(self) -> dict:
        ...

class MyStateManager(StateManager[MyState]):
    """Custom state manager inheriting from StateManager ABC."""

    def __init__(self, state_file: Path = None):
        self.state_file = state_file or Path(".my_state.json")
        # Validate path using inherited helper
        self.state_file = self._validate_state_path(self.state_file)

    def load_state(self) -> MyState:
        """Load state from file."""
        # Use inherited helpers as needed
        if not self.exists():
            raise StateError("State file not found")
        # ... load logic ...
        return MyState(...)

    def save_state(self, state: MyState) -> None:
        """Save state to file using atomic write."""
        content = json.dumps(state.to_dict())
        # Use inherited _atomic_write for security
        self._atomic_write(self.state_file, content)
        # Log the operation
        self._audit_operation("state_save", "success", {...})

    def cleanup_state(self) -> None:
        """Clean up state file."""
        if self.exists():
            self.state_file.unlink()
```

### Security Features

1. **CWE-22 (Path Traversal Prevention)**:
   - Validates paths don't contain `../` sequences
   - Resolves symlinks and detects traversal

2. **CWE-59 (Symlink Following Prevention)**:
   - Detects and rejects symlinks
   - Prevents TOCTOU (Time-of-check-time-of-use) races

3. **CWE-367 (Atomic Write)**:
   - Writes to temp file first
   - Atomically renames to final location
   - Prevents partial/corrupted state files

4. **CWE-732 (File Permissions)**:
   - Sets files to 0o600 (user read/write only)
   - Prevents unauthorized access

### Design Notes

- **Generic type**: StateManager[T] supports any state data class
- **Delegation pattern**: Subclasses implement abstract methods, use helpers for security
- **Backward compatibility**: Existing managers can inherit without refactoring
- **Phase-based migration**: Issue #220 (ABC foundation), Issue #221 (BatchStateManager), further phases for other managers

### Related

- Issue #220: Create StateManager ABC
- Issue #221: Migrate BatchStateManager to inherit from StateManager ABC
- GitHub: `plugins/autonomous-dev/lib/abstract_state_manager.py`

---

## 13. batch_state_manager.py (692 lines, v3.23.0+, enhanced v3.24.0, Issue #218: v3.46.0)

**Purpose**: State persistence for /batch-implement command with automatic context management via Claude Code

**Note (Issue #218 - v3.46.0)**: Deprecated context clearing functions removed:
- `should_clear_context()` - Removed (Claude Code v2.0+ manages context automatically with 200K budget)
- `pause_batch_for_clear()` - Removed (no longer needed without manual clearing)
- `get_clear_notification_message()` - Removed (no longer needed without manual clearing)
- `@deprecated` decorator - Removed (no longer needed)
- `CONTEXT_THRESHOLD` constant - Removed (Claude Code handles context automatically)

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
- **Raises**: `StateError` (BatchStateError is now an alias, Issue #225) if file not found or corrupted
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

#### `should_auto_clear(state, threshold=160000)`
- **Purpose**: Internal helper - check if context is approaching Claude Code's 200K token limit
- **Parameters**:
  - `state` (BatchState): Current state
  - `threshold` (int): Token threshold (default: 160,000 - internal use only)
- **Returns**: bool (True if approaching token limit)
- **Note**: Used internally for monitoring only. Claude Code manages context automatically with 200K budget. Manual context clearing no longer needed (Issue #218).

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

### Object-Oriented Interface (NEW Issue #221)

#### `BatchStateManager` class (inherits from StateManager[BatchState])

Object-oriented wrapper for batch state functions that inherits from StateManager ABC.

**Constructors**:
- `__init__(state_file: Optional[Path] = None)` - Initialize with optional custom state file path

**Methods** (implementing StateManager ABC):
- `load_state() -> BatchState` - Load batch state from file
- `save_state(state: BatchState) -> None` - Save batch state to file (uses inherited _atomic_write())
- `cleanup_state() -> None` - Clean up state file

**Methods** (batch-specific operations):
- `create_batch_state(features, batch_id=None, issue_numbers=None) -> BatchState` - Create new batch state
- `create_batch(features, features_file=None, batch_id=None, issue_numbers=None) -> BatchState` - Alias for create_batch_state
- `load_batch_state() -> BatchState` - Load batch state (delegates to load_state)
- `save_batch_state(state) -> None` - Save batch state (delegates to save_state)
- `update_batch_progress(feature_index, status, tokens_consumed=0) -> None` - Update batch progress
- `record_auto_clear_event(feature_index, tokens_before) -> None` - Record auto-clear event
- `should_auto_clear(threshold=160000) -> bool` - Check if auto-clear threshold exceeded
- `get_next_pending_feature() -> Optional[str]` - Get next unprocessed feature
- `cleanup_batch_state() -> None` - Cleanup batch (delegates to cleanup_state)

**Example**:
```python
from batch_state_manager import BatchStateManager

# Create manager
manager = BatchStateManager()

# Create new batch
state = manager.create_batch_state(
    features=["Add login", "Add logout"],
    issue_numbers=[72, 73],
)

# Save state
manager.save_batch_state(state)

# Load state
loaded_state = manager.load_batch_state()

# Update progress
manager.update_batch_progress(0, "completed", tokens_consumed=50000)

# Check if auto-clear needed
if manager.should_auto_clear():
    manager.record_auto_clear_event(0, 155000)

# Get next feature to process
next_feature = manager.get_next_pending_feature()

# Cleanup when done
manager.cleanup_batch_state()
```

**Inheritance Pattern**:
BatchStateManager now inherits from StateManager[BatchState] ABC (Issue #221), implementing abstract methods via delegation:
- `load_state()` delegates to `load_batch_state()`
- `save_state()` delegates to `save_batch_state()`
- `cleanup_state()` delegates to `cleanup_batch_state()`

This maintains full backward compatibility while providing standardized state management interface with built-in security helpers from StateManager ABC.

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

## 15. path_utils.py (350+ lines, v3.28.0+ / v3.41.0+ / v3.45.0+)

**Purpose**: Dynamic PROJECT_ROOT detection, path resolution, policy file location, and worktree batch state isolation for tracking infrastructure and tool configuration

**Issues**: GitHub #79 (hardcoded paths), GitHub #226 (worktree isolation)

### Key Features

- **Dynamic PROJECT_ROOT Detection**: Searches upward from current directory for `.git/` or `.claude/` markers
- **Worktree Batch State Isolation** (v3.45.0): Automatically isolates batch state per git worktree for concurrent batch processing
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

#### `get_batch_state_file()` (Enhanced v3.45.0 - Issue #226)
- **Purpose**: Get batch state file path with automatic worktree isolation support
- **Behavior**:
  - **Worktrees**: Returns `WORKTREE_DIR/.claude/batch_state.json` (isolated per worktree)
  - **Main Repository**: Returns `PROJECT_ROOT/.claude/batch_state.json` (backward compatible)
- **Detection**: Automatically calls `is_worktree()` to detect current directory
- **Returns**: `Path` - Batch state file path (note: file itself not created)
- **Creates**: Parent directory (`.claude/`) if missing, with safe permissions (0o755)
- **Fallback**: If worktree detection fails, falls back to main repo behavior
- **Used By**: batch_state_manager.py
- **Security**: Graceful fallback on detection errors, CWE-22 (path traversal), CWE-59 (symlinks) protection

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

#### `is_worktree()` (NEW in v3.45.0 - Issue #226)
- **Purpose**: Check if current directory is a git worktree (lazy-loaded wrapper)
- **Returns**: `bool` - True if in worktree, False otherwise
- **Lazy Import**: Imports git_operations.is_worktree() on first call to avoid circular dependencies
- **Fallback**: Returns False if import fails or detection raises exception
- **Used By**: get_batch_state_file()
- **Caching**: Module-level function cache for performance
- **Testing**: Can be mocked by patching `path_utils.is_worktree`

#### `reset_project_root_cache()`
- **Purpose**: Reset cached project root (testing only)
- **Warning**: Only use in test teardown; production code should maintain cache for process lifetime

#### `reset_worktree_cache()` (NEW in v3.45.0 - Issue #226)
- **Purpose**: Reset cached is_worktree function (testing only)
- **Warning**: Only use in test teardown; production code should maintain cache for process lifetime

### Test Coverage

- **Total**: 45+ tests in `tests/unit/test_tracking_path_resolution.py` + 15 tests in `tests/unit/lib/test_policy_path_resolution.py` + 15 tests in `tests/unit/lib/test_path_utils_worktree.py` + 9 integration tests in `tests/integration/test_worktree_batch_isolation.py` (NEW v3.45.0)
- **Areas**:
  - PROJECT_ROOT detection from various directories
  - Marker file priority (`.git` over `.claude`)
  - Nested `.claude/` handling in git repositories
  - Directory creation with safe permissions
  - Cache behavior and reset
  - Policy file cascading lookup (NEW v3.41.0)
  - Policy file security validation (NEW v3.41.0)
  - Symlink detection in policy files (NEW v3.41.0)
  - Worktree batch state path isolation (NEW v3.45.0 - Issue #226)
  - Concurrent worktree batch operations (NEW v3.45.0)
  - Worktree detection fallback behavior (NEW v3.45.0)
  - Real git worktree integration (NEW v3.45.0)

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

# Get batch state file path (with worktree isolation - v3.45.0)
state_file = get_batch_state_file()
# Main repo: Returns /project/.claude/batch_state.json
# In worktree: Returns /project/worktree-dir/.claude/batch_state.json

# Check if in worktree (v3.45.0)
from plugins.autonomous_dev.lib.path_utils import is_worktree
if is_worktree():
    print("Running in git worktree - batch state isolated")
else:
    print("Running in main repository")

# Get policy file with cascading lookup
policy_file = get_policy_file()
# 1. Tries: .claude/config/auto_approve_policy.json (project-local)
# 2. Falls back to: plugins/autonomous-dev/config/auto_approve_policy.json (plugin default)
# 3. Returns minimal fallback if both missing

# Force re-detection (for tests that change cwd)
from tests.conftest import isolated_project
root = get_project_root(use_cache=False)
policy_file = get_policy_file(use_cache=False)

# Worktree example (v3.45.0)
# In main repo
state_file = get_batch_state_file()  # .claude/batch_state.json

# In worktree
state_file = get_batch_state_file()  # worktree-dir/.claude/batch_state.json (isolated)
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

## 24. agent_tracker package (1,710 lines, v3.44.0+, Issue #165)

**Purpose**: Portable tracking infrastructure for agent execution with dynamic project root detection

**Problem Solved (Issue #79)**: Original `scripts/agent_tracker.py` had hardcoded paths that failed when:
- Running from user projects (no `scripts/` directory)
- Running from project subdirectories (couldn't find project root)
- Commands invoked from installation path vs development path

**Solution (Issue #165 Refactoring)**: Monolithic library file (1,185 lines) split into focused package with 8 modules for maintainability:

**Package Structure** (`plugins/autonomous-dev/lib/agent_tracker/`):
- `__init__.py` (72 lines): Re-exports for backward compatibility
- `models.py` (64 lines): Data structures (AGENT_METADATA, EXPECTED_AGENTS)
- `state.py` (408 lines): Session state management and agent lifecycle
- `tracker.py` (441 lines): Main AgentTracker class with delegation pattern
- `metrics.py` (116 lines): Progress calculation and time estimation
- `verification.py` (311 lines): Parallel execution verification
- `display.py` (200 lines): Status display and visualization
- `cli.py` (98 lines): Command-line interface

**Backward Compatibility**: All imports continue to work via re-exports:
- Old: `from agent_tracker import AgentTracker` ✅ still works
- New: `from agent_tracker.tracker import AgentTracker` (preferred)
- Path utilities also re-exported for legacy code

**Benefits**:
- Dynamic project root detection via path_utils
- Portable path resolution (no hardcoded paths)
- Atomic file writes for data consistency
- Comprehensive error handling with context
- Clearer module responsibilities (each <500 lines)
- Easier testing and maintenance
- Better IDE support and code navigation

### Classes

#### `AgentTracker`
- **Purpose**: Track agent execution with structured logging
- **Location**: `tracker.py` (delegates to state manager)
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
- **Location**: Delegates to `metrics.py`

#### `calculate_progress() -> int`
- **Purpose**: Calculate workflow completion percentage
- **Returns**: Integer 0-100
- **Calculation**: `(agents_completed / agents_expected) * 100`
- **Location**: Delegates to `metrics.py`

#### `get_average_agent_duration() -> Optional[int]`
- **Purpose**: Calculate average duration of completed agents
- **Returns**: Seconds (or None if no agents completed)
- **Uses**: Estimation of remaining time
- **Location**: Delegates to `metrics.py`

#### `estimate_remaining_time() -> Optional[int]`
- **Purpose**: Estimate time until workflow completion
- **Returns**: Seconds (or None if insufficient data)
- **Calculation**: `(pending_agents * average_duration) + safety_buffer`
- **Location**: Delegates to `metrics.py`

#### `get_pending_agents() -> List[str]`
- **Purpose**: List agents not yet started
- **Returns**: List of agent names
- **Uses**: Progress tracking and timeout calculations
- **Location**: Delegates to `state.py`

#### `get_running_agent() -> Optional[str]`
- **Purpose**: Get currently running agent
- **Returns**: Agent name (or None if none running)
- **Uses**: Checkpoint verification, deadlock detection
- **Location**: Delegates to `state.py`

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
- **Location**: Delegates to `verification.py`

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
- **Location**: Delegates to `verification.py`

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
- **Location**: Delegates to `verification.py`

#### `is_pipeline_complete() -> bool`
- **Purpose**: Check if all expected agents completed
- **Returns**: True if all agents in "completed" or "failed" state
- **Uses**: Workflow completion detection
- **Location**: Delegates to `state.py`

#### `is_agent_tracked(agent_name) -> bool`
- **Purpose**: Check if agent has been logged
- **Parameters**: `agent_name` (str): Agent to check
- **Returns**: True if agent found in session
- **Location**: Delegates to `state.py`

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
- **Location**: Delegates to `state.py`

### Formatting & Display Methods

#### `get_agent_emoji(status) -> str`
- **Purpose**: Get emoji for agent status
- **Status Mappings**:
  - "started" → "▶️"
  - "completed" → "✅"
  - "failed" → "❌"
  - "pending" → "⏳"
- **Location**: `display.py`

#### `get_agent_color(status) -> str`
- **Purpose**: Get ANSI color code for status
- **Colors**: Green (completed), Red (failed), Yellow (started), Gray (pending)
- **Location**: `display.py`

#### `get_display_metadata() -> Dict[str, Any]`
- **Purpose**: Get formatted metadata for display
- **Returns**: Dictionary with:
  - `session_id`: Unique session identifier
  - `started`: Human-readable start time
  - `duration`: Total elapsed time
  - `progress`: Completion percentage
  - `agents_summary`: Count by status
- **Location**: `display.py`

#### `get_tree_view_data() -> Dict[str, Any]`
- **Purpose**: Get tree structure for ASCII tree display
- **Returns**: Hierarchical dictionary representing workflow execution
- **Location**: `display.py`

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

#### `AgentTracker.save_agent_checkpoint()` (Issue #79, v3.36.0+)

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
- User projects (no `plugins/` directory) -> skips, returns False
- Import errors (missing dependencies) -> skips, returns False
- Filesystem errors (permission denied) -> skips, returns False
- Unexpected errors -> logs warning, returns False

This allows agents to be portable across development and user environments.

**Design Pattern**: Progressive Enhancement - feature works with or without supporting infrastructure

**Related**: GitHub Issue #79 (Dogfooding bug fix), Issue #82 (Optional checkpoint verification)

### Module Architecture (Issue #165)

**Purpose of Refactoring**: Split monolithic 1,185-line file into focused modules for:
- Easier testing (unit test each responsibility separately)
- Better maintainability (changes isolated to relevant modules)
- Clearer code organization (each module has single responsibility)
- Performance monitoring (metrics in dedicated module)
- Display logic separation (display.py handles all formatting)

**Delegation Pattern**:
- `tracker.py` (441 lines): AgentTracker class coordinates via delegation
- Methods call specialized manager classes from other modules
- Reduces complexity: Main class focuses on public API, not implementation details
- Example: `calculate_progress()` delegates to `metrics.calculate_progress()`

**State Management** (state.py - 408 lines):
- `StateManager` class handles session file I/O
- Tracks agent start/completion times
- Manages JSON serialization and atomic writes
- Enforces security constraints (path validation)

**Metrics Calculation** (metrics.py - 116 lines):
- `MetricsCalculator` class handles all time-based calculations
- Progress percentage, average duration, remaining time estimates
- No I/O operations (pure calculation)
- Easy to unit test

**Verification Logic** (verification.py - 311 lines):
- `ParallelVerifier` class handles parallel execution checks
- Validates checkpoint requirements (agents completed, time thresholds)
- Extracts and formats metrics for display
- Used by CHECKPOINT 1 and CHECKPOINT 4.1

**Display Formatting** (display.py - 200 lines):
- `DisplayFormatter` class handles all output formatting
- ANSI colors, emoji status indicators, tree view generation
- Separated from logic (can swap formatters for testing)
- Enables future HTML/JSON output formats

**Data Models** (models.py - 64 lines):
- Constants: `AGENT_METADATA`, `EXPECTED_AGENTS` per workflow
- Enum for agent status values
- Type hints for consistency

**CLI Wrapper** (cli.py - 98 lines):
- Command-line interface delegating to AgentTracker
- Commands: start, complete, fail, status, set-github-issue
- Argument parsing and error handling

### CLI Wrapper

**File**: `plugins/autonomous-dev/scripts/agent_tracker.py`
- **Purpose**: CLI interface for library functionality
- **Design**: Delegates to `plugins/autonomous-dev/lib/agent_tracker/` package
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
  - For imports: Use `from plugins.autonomous_dev.lib.agent_tracker import AgentTracker`
  - Existing code continues to work (delegates to library implementation)
  - Will be removed in v4.0.0

### Usage Examples

#### Basic Usage (Standard Mode)
```python
from agent_tracker import AgentTracker

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
- GitHub Issue #165 (Package refactoring - monolithic to modular)
- path_utils.py (Dynamic project root detection)
- security_utils.py (Path validation and input bounds checking)

### Design Patterns
- **Two-tier Design**: Library (core logic) + CLI wrapper (interface)
- **Delegation Pattern**: AgentTracker delegates to specialized manager classes
- **Progressive Enhancement**: Features gracefully degrade if infrastructure unavailable
- **Atomic Writes**: Tempfile + rename for consistency
- **Path Portability**: Uses path_utils instead of hardcoded paths
- **Modular Responsibility**: Each module handles single concern (~100-400 lines)

- Comprehensive docstrings with design patterns

### Classes

#### `SessionTracker`
- **Purpose**: Log agent actions to session file instead of keeping in context
- **Base Class**: Inherits from `StateManager[str]` (Issue #224)
  - Generic type is `str` for markdown content
  - Implements abstract methods: `load_state()`, `save_state()`, `cleanup_state()`
  - Uses inherited helpers: `_validate_state_path()`, `_atomic_write()`, `_get_file_lock()`, `_audit_operation()`
- **Initialization**: `SessionTracker(session_file=None, use_cache=True)`
  - `session_file` (Optional[str]): Path to session file for testing
  - `use_cache` (bool): If True, use cached project root (default: True)
  - If None: Creates/finds session file automatically using path_utils
  - Raises `StateError` if session_file path is invalid or outside project
- **Features**:
  - Auto-detects project root from any subdirectory
  - Creates `docs/sessions/` directory if missing
  - Finds or creates session files with timestamp naming: `YYYYMMDD-HHMMSS-session.md`
  - Path validation via shared validation module
  - Directory permission checking (warns on world-writable)
  - Thread-safe file operations with atomic writes

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

#### `load_state() -> str` (StateManager ABC)
- **Purpose**: Load session markdown content from file
- **Returns**: str - Markdown content of session file
- **Raises**: `StateError` if session file not found or load fails
- **Features**:
  - Thread-safe with inherited file locking
  - Validates file path via `_validate_state_path()`
- **Example**:
  ```python
  tracker = SessionTracker()
  content = tracker.load_state()
  print(content)  # Full markdown session content
  ```

#### `save_state(state: str) -> None` (StateManager ABC)
- **Purpose**: Save session markdown content to file with atomic writes
- **Parameters**: `state` (str) - Markdown content to save
- **Raises**: `StateError` if save fails
- **Features**:
  - Uses inherited atomic write pattern (temp file + rename)
  - Thread-safe with file locking
  - Path validation to prevent CWE-22 (path traversal)
  - Sets restrictive permissions (0o600)
- **Example**:
  ```python
  tracker = SessionTracker()
  content = "# Session Log\n\n**12:00:00 - researcher**: Test\n"
  tracker.save_state(content)
  ```

#### `cleanup_state() -> None` (StateManager ABC)
- **Purpose**: Remove session file from disk
- **Raises**: `StateError` if cleanup fails
- **Features**:
  - Thread-safe with file locking
  - Only removes file if it exists
- **Example**:
  ```python
  tracker = SessionTracker()
  tracker.cleanup_state()
  assert not tracker.session_file.exists()
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

StateError exceptions include context and guidance:
```python
try:
    tracker = SessionTracker(session_file="../../etc/passwd")
except StateError as e:
    # Error includes: what went wrong, why, and what's expected
    # Example: "Path traversal attempt detected: /etc/passwd"
    print(e)

try:
    content = tracker.load_state()
except StateError as e:
    # Handles: file not found, read errors, path validation failures
    print(e)
```

Backward Compatibility:
- Exceptions raised during `__init__` (path validation) may raise exceptions inherited from StateError
- StateError is a subclass of AutonomousDevError for consistent error handling

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
- **StateManager ABC Integration** (Issue #224): Standardized state management
  - Inherits from StateManager[str] for type-safe state operations
  - Delegates file operations to inherited helpers for DRY principle
  - Consistent error handling via StateError exception hierarchy
  - Phase 5 of StateManager migration (after BatchStateManager, UserStateManager, CheckpointManager)

### StateManager ABC Methods

See [abstract_state_manager.py](../plugins/autonomous-dev/lib/abstract_state_manager.py) for implementation details.

**Inherited Helper Methods**:
- `exists() -> bool`: Check if state file exists
- `_validate_state_path(path: Path) -> Path`: Validate path against traversal attacks (CWE-22)
- `_atomic_write(path: Path, content: str, mode: int = 0o600) -> None`: Write with atomicity guarantees
- `_get_file_lock(path: Path) -> threading.RLock`: Get thread-safe lock for file operations
- `_audit_operation(operation: str, details: Dict) -> None`: Log security-relevant operations

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

- `unified_pre_tool.py` hook - Layer 2 of unified PreToolUse hook for MCP tool validation (archived: `mcp_security_enforcer.py`)
- Custom MCP server implementations
- Permission validation workflows

### Related

- GitHub Issue #95 (MCP Server Security)
- [MCP-SECURITY.md](MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/unified_pre_tool.py` - Unified hook implementation (Layer 2)
- `plugins/autonomous-dev/hooks/archived/README.md` - Archived hook documentation (Issue #211)
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

- `unified_pre_tool.py` hook - Load profiles on startup (Layer 2: MCP Security Validator)
- `mcp_permission_validator.py` - Fallback to development profile
- Setup and initialization scripts

### Related

- GitHub Issue #95 (MCP Server Security)
- [MCP-SECURITY.md](MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/unified_pre_tool.py` - Unified hook implementation (Layer 2)
- `plugins/autonomous-dev/hooks/archived/README.md` - Archived hook documentation (Issue #211)
- `.mcp/security_policy.json` - Policy configuration file

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

- `unified_pre_tool.py` hook - Apply server-specific validation rules (Layer 2: MCP Security Validator)
- `mcp_permission_validator.py` - Route to appropriate validator

### Related

- GitHub Issue #95 (MCP Server Security)
- [MCP-SECURITY.md](MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/unified_pre_tool.py` - Unified hook implementation (Layer 2)
- `plugins/autonomous-dev/hooks/archived/README.md` - Archived hook documentation (Issue #211)


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

## 56. tech_debt_detector.py (759 lines, v1.0.0 - Issue #162)

**Purpose**: Proactive code quality issue detection with severity classification.

**Module**: plugins/autonomous-dev/lib/tech_debt_detector.py

**Problem Solved**:
- Reviewers need structured detection of common code quality issues
- Manual inspection of large files, circular imports, dead code is error-prone
- Need severity levels to distinguish blocking issues from warnings
- Need integration point for reviewer checklist

**Solution**:
- 7 detection methods for different tech debt patterns
- Severity enum (CRITICAL, HIGH, MEDIUM, LOW)
- Dataclass-based issue representation for structured results
- Convenience function for one-shot project scanning
- Path traversal prevention for security

### Classes

#### Severity

Enumeration for tech debt issue severity levels.

**Values**:
- CRITICAL (4) - Blocks workflow (exit code 1 in hooks)
- HIGH (3) - Warning only (exit code 0, show message)
- MEDIUM (2) - Informational (tracked but not blocking)
- LOW (1) - Minor issues (low priority)

#### TechDebtIssue

Dataclass representing a single tech debt issue.

**Attributes**:
- category (str): Type of issue (e.g., "large_file", "circular_import")
- severity (Severity): Severity level
- file_path (str): Path to affected file
- metric_value (int): Measured value (e.g., LOC count, complexity score)
- threshold (int): Threshold that was exceeded
- message (str): Human-readable description
- recommendation (str): Suggested fix

#### TechDebtReport

Dataclass aggregating all detected issues.

**Attributes**:
- issues (List[TechDebtIssue]): All detected issues
- counts (Dict[Severity, int]): Count by severity level
- blocked (bool): True if CRITICAL issues found

### Detection Methods

#### detect_large_files() -> List[TechDebtIssue]

Identify files exceeding size thresholds.

**Thresholds**:
- 1500+ LOC: CRITICAL
- 1000-1499 LOC: HIGH

**Returns**: List of issues for oversized files

**Use Case**: Large files indicate monolithic design, harder to test and maintain

#### detect_circular_imports() -> List[TechDebtIssue]

Detect import cycles via AST analysis (Python files only).

**Algorithm**: Build import graph, detect cycles using DFS

**Returns**: List of issues for circular dependencies

**Use Case**: Circular imports cause initialization issues, indicate tight coupling

#### detect_red_test_accumulation() -> List[TechDebtIssue]

Count RED test markers (failing tests) in codebase.

**Markers**: Lines containing "RED" or "@skip" or "@xfail"

**Thresholds**:
- 20+ RED markers: CRITICAL
- 10-19 RED markers: HIGH

**Returns**: List of issues for accumulated failed tests

**Use Case**: Accumulating RED tests indicate feature rot, incomplete implementation

#### detect_config_proliferation() -> List[TechDebtIssue]

Identify scattered configuration files.

**Patterns**: .env, .config.json, config.yaml, settings.ini, etc.

**Thresholds**:
- 10+ config files: CRITICAL
- 5-9 config files: HIGH

**Returns**: List of issues for config sprawl

**Use Case**: Config proliferation makes setup complex, increases errors

#### detect_duplicate_directories() -> List[TechDebtIssue]

Find directories with similar names suggesting duplication.

**Patterns**: utils, util, helpers, helper; config, configs, configuration, etc.

**Returns**: List of issues for naming inconsistencies

**Use Case**: Duplicate directories indicate unclear organization

#### detect_dead_code() -> List[TechDebtIssue]

Identify unused imports and function definitions.

**Methods**:
- Unused imports: Import statements with no references
- Unused functions: Function definitions with no calls (conservative approach)

**Returns**: List of issues for dead code

**Use Case**: Dead code accumulates, adds noise, increases maintenance burden

#### calculate_complexity() -> List[TechDebtIssue]

Measure McCabe cyclomatic complexity using radon library (optional dependency).

**Thresholds** (per function):
- 15+ complexity: CRITICAL
- 10-14 complexity: HIGH

**Returns**: List of issues for overly complex functions

**Use Case**: High complexity indicates functions doing too much, harder to test

### Methods

#### __init__(project_root: Path)

Initialize detector with project root path.

**Parameters**:
- project_root (Path): Root directory to analyze

**Validation**: Path must exist and be readable

#### analyze() -> TechDebtReport

Run all detection methods and aggregate results.

**Returns**: Aggregated report with all issues and statistics

**Execution Order**:
1. Large files detection
2. Circular imports detection
3. Red test accumulation
4. Config proliferation
5. Duplicate directories
6. Dead code detection
7. Complexity analysis

### Module Functions

#### scan_project(project_root: Path) -> TechDebtReport

Convenience function for one-shot project scanning.

**Parameters**:
- project_root (Path): Root directory to analyze

**Returns**: Complete tech debt report

**Usage Example**:

```
from tech_debt_detector import scan_project

report = scan_project(Path("/path/to/project"))
if report.blocked:
    print("CRITICAL issues found!")
    for issue in report.issues:
        if issue.severity == Severity.CRITICAL:
            print(f"  {issue.message}")
```

### Integration Points

- reviewer agent - Integrated into code review checklist (CHECKPOINT 4.2 in /auto-implement)
- /health-check command - Optional tech debt analysis
- CI/CD pipelines - Pre-commit quality gate

### Security Features

- Path traversal prevention (CWE-22) via security_utils validation
- Symlink resolution for safe path handling (CWE-59)
- Conservative detection logic to minimize false positives
- No arbitrary code execution (AST parsing only, no eval)

### Performance Characteristics

- Large files: O(n) where n = files scanned
- Circular imports: O(V + E) where V = modules, E = imports
- Config proliferation: O(n) glob pattern matching
- Dead code: O(n*m) where m = lines per file
- Complexity: Depends on radon library (typically less than 100ms per file)
- Typical project (1000 files): 2-5 seconds total

### Test Coverage

**Test File**: tests/unit/lib/test_tech_debt_detector.py

**Coverage Areas**:
- Severity enumeration and values
- Issue dataclass creation and validation
- Large files detection with thresholds
- Circular import detection via AST
- RED test accumulation and counting
- Config proliferation detection
- Duplicate directory detection
- Dead code detection (imports and functions)
- Complexity calculation with radon
- Report aggregation and statistics
- Security (path validation, traversal prevention)
- Error handling (missing files, invalid paths, unreadable directories)

**Target**: 90 percent coverage

### Used By

- reviewer agent - Code quality analysis during /auto-implement
- /health-check command - Optional tech debt scanning
- CI/CD integration - Pre-commit quality gates

### Related Issues

- GitHub Issue #162 - Tech Debt Detection System
- GitHub Issue #141 - Workflow discipline (guides usage of detector)

### Related Components

**Dependencies**:
- pathlib - Path handling
- ast - Python import graph analysis
- radon (optional) - McCabe complexity calculation
- security_utils.py - Path validation (CWE-22, CWE-59 prevention)

**Used By**:
- reviewer.md agent - Code review checklist integration
- health_check.py hook - Optional tech debt analysis


## 57. scope_detector.py (584 lines, v1.0.0)

**Purpose**: Scope analysis and complexity detection for issue decomposition

**Module**: plugins/autonomous-dev/lib/scope_detector.py

**Exports**:
- EffortSize (enum): T-shirt sizing for effort estimation (XS/S/M/L/XL)
- ComplexityAnalysis (dataclass): Results of complexity analysis
- analyze_complexity() - Main analysis function
- estimate_atomic_count() - Estimate number of sub-issues
- generate_decomposition_prompt() - Generate decomposition prompt
- load_config() - Load configuration with fallback

### Key Data Structures

#### EffortSize (Enum)

T-shirt sizing for effort estimation:
- XS: Less than 1 hour
- S: 1-4 hours
- M: 4-8 hours
- L: 1-2 days
- XL: More than 2 days

#### ComplexityAnalysis (Dataclass)

Results of complexity analysis with attributes:
- effort: Estimated effort size (EffortSize enum)
- indicators: Dictionary of detected indicators (keywords, anti-patterns)
- needs_decomposition: Whether request should be broken into sub-issues
- confidence: Confidence score for analysis (0.0-1.0)

### Main Functions

#### analyze_complexity(request, config=None) - Main analysis

Signature: analyze_complexity(request: str, config: Optional[Dict] = None) -> ComplexityAnalysis

- Purpose: Analyze complexity of a feature request
- Parameters:
  - request (str): Feature request text to analyze
  - config (dict|None): Optional configuration (uses defaults if None)
- Returns: ComplexityAnalysis with effort, indicators, decomposition flag, confidence
- Features:
  - Keyword detection: Identifies high/medium complexity indicators
  - Anti-pattern detection: Finds conjunctions, multiple file types, vague terms
  - Effort estimation: Maps indicators to t-shirt sizes
  - Confidence calculation: Scores analysis reliability (0.0-1.0)
  - Decomposition determination: Flags if request needs breaking into sub-issues
- Algorithm:
  1. Detect keywords (complexity_high, complexity_medium, vague, domain, breadth)
  2. Detect anti-patterns (conjunctions, file types, vague keywords)
  3. Estimate effort size based on indicators
  4. Calculate confidence score
  5. Determine if decomposition needed (effort >= threshold OR excessive conjunctions)
- Edge Cases:
  - Empty/None/whitespace input: Returns M effort with low confidence
  - Very long input (>10K chars): Truncated with warning
  - Invalid threshold: Defaults to M

#### estimate_atomic_count(request, complexity, config=None) - Sub-issue count

Signature: estimate_atomic_count(request: str, complexity: ComplexityAnalysis, config: Optional[Dict] = None) -> int

- Purpose: Estimate number of atomic sub-issues needed
- Parameters:
  - request (str): Original feature request
  - complexity (ComplexityAnalysis): Result from analyze_complexity()
  - config (dict|None): Optional configuration
- Returns: int - Number of sub-issues (1-5 default)
- Mapping:
  - XS/S effort: 1 (no decomposition needed)
  - M effort: 3 sub-issues
  - L effort: 4 sub-issues
  - XL effort: 5 sub-issues

#### generate_decomposition_prompt(request, count) - Decomposition prompt

Signature: generate_decomposition_prompt(request: str, count: int) -> str

- Purpose: Generate prompt for decomposing request into atomic sub-issues
- Parameters:
  - request (str): Original feature request
  - count (int): Target number of sub-issues
- Returns: str - Formatted prompt with decomposition instructions
- Features:
  - Preserves original request context
  - Specifies size constraints (1-4 hours per sub-issue)
  - Minimizes inter-issue dependencies
  - Includes testability requirement

#### load_config(config_path=None) - Configuration loading

Signature: load_config(config_path: Optional[Path] = None) -> Dict[str, Any]

- Purpose: Load configuration from file with fallback to defaults
- Parameters: config_path (Path|None): Path to JSON config file
- Returns: Configuration dictionary with all required fields
- Features:
  - Fallback to DEFAULT_CONFIG if file not found
  - Deep merging of keyword_sets and anti_patterns with defaults
  - Graceful error handling (logs errors, uses defaults)

### Configuration

Default Configuration:
- decomposition_threshold: "M" - Minimum effort to trigger decomposition
- max_atomic_issues: 5 - Maximum number of sub-issues
- keyword_sets: Categorized keywords for detection
  - complexity_high: refactor, redesign, migrate, overhaul, rewrite, architect
  - complexity_medium: add, implement, create, build, integrate
  - vague_indicators: improve, enhance, optimize, better, faster, cleaner
  - domain_terms: authentication, oauth, saml, ldap, jwt, api, database, security
  - breadth_indicators: complete, entire, full, comprehensive, system, platform
- anti_patterns:
  - conjunction_limit: 3 - Max "and" conjunctions before flagging
  - file_type_limit: 3 - Max file types before flagging breadth

### Detection Functions

#### detect_keywords(text, keyword_sets)

- Purpose: Detect and count keyword occurrences
- Returns: dict - Mapping of category to match count
- Features: Case-insensitive matching, word boundaries, domain term partial matches

#### detect_anti_patterns(text, anti_patterns)

- Purpose: Detect anti-patterns in feature requests
- Returns: dict with conjunction_count, file_types, vague_keywords
- Features: Identifies scope creep, breadth complexity, unclear requirements

### Performance

- Time Complexity: O(n) where n = request length
- Typical: <10ms for average request (100-500 chars)
- Worst case: <100ms for 10K+ char requests

### Test Coverage

Test File: tests/unit/lib/test_scope_detector.py

Coverage: 49 test cases covering:
- Keyword detection (case insensitivity, word boundaries, partial matches)
- Anti-pattern detection (conjunctions, file types, vague keywords)
- Effort estimation (all effort sizes, edge cases, complexity boosters)
- Confidence calculation (high/low confidence cases)
- Main analysis function (complex features, simple features)
- Atomic count estimation (all effort sizes, respecting limits)
- Decomposition prompt generation (prompt structure, clarity)
- Configuration loading (defaults, file loading, error handling)
- Security (input validation, graceful degradation)

Target: 90+ percent coverage

### Used By

- issue-creator agent - Scope detection and decomposition
- Feature request analysis workflows
- Issue decomposition planning

### Related Components

Dependencies:
- pathlib - Path handling
- json - Configuration loading
- re - Regular expression matching
- logging - Debug logging
- dataclasses - Data structures
- enum - Effort size enumeration

---

## 58. completion_verifier.py (415 lines, v1.0.0)

**Purpose**: Pipeline completion verification with intelligent retry and circuit breaker

**Problem**: Pipeline agents may fail to complete, but users have no way to detect and retry incomplete work

**Solution**: Comprehensive completion verification system with exponential backoff and state persistence

### Data Structures

#### VerificationResult

Immutable verification outcome.

**Attributes**:
- `complete` (bool): True if all 8 agents completed
- `agents_found` (List[str]): Names of agents found in session
- `missing_agents` (List[str]): Names of agents not found (empty if complete)
- `verification_time_ms` (float): Time taken to verify (milliseconds)

**Features**:
- Immutable (frozen dataclass)
- Preserves agent order from EXPECTED_AGENTS constant
- Always includes verification timing for performance monitoring

#### LoopBackState

Mutable retry state with persistence.

**Attributes**:
- `session_id` (str): Session identifier for correlation
- `attempt_count` (int): Current retry attempt number (0 = initial check)
- `max_attempts` (int): Maximum allowed attempts (default: 5)
- `consecutive_failures` (int): Count of consecutive failures (0 = success, increments on failure)
- `circuit_breaker_open` (bool): True if circuit breaker triggered (after 3 consecutive failures)
- `last_attempt_timestamp` (Optional[str]): ISO 8601 timestamp of last attempt
- `missing_agents` (List[str]): Agents not found in last verification

**Features**:
- Serializable to JSON (for state persistence)
- Tracks attempt history for audit logging
- Circuit breaker integration (prevents infinite retries)
- Supports graceful degradation with fallback defaults

### Functions

#### verify_pipeline_completion(session_id, session_data=None, state_dir=None)

Verify that all 8 expected agents completed.

**Signature**:
```python
def verify_pipeline_completion(
    session_id: str,
    session_data: Optional[Dict] = None,
    state_dir: Optional[Path] = None
) -> VerificationResult
```

**Parameters**:
- `session_id` (str): Session identifier
- `session_data` (Optional[Dict]): Pre-loaded session data for testing (bypasses file read)
- `state_dir` (Optional[Path]): State directory (defaults to `./.claude`)

**Returns**: `VerificationResult` with completion status and missing agents

**Expected Agents** (in order):
1. researcher-local
2. researcher-web
3. planner
4. test-master
5. implementer
6. reviewer
7. security-auditor
8. doc-master

**Features**:
- Loads session file from `.claude/sessions/{session_id}.json`
- Extracts agent names from session data
- Compares against EXPECTED_AGENTS constant
- Preserves agent order in results
- Graceful degradation on file not found (returns incomplete)
- Handles JSON parse errors gracefully

**Security**:
- Path validation for state_dir (CWE-22 prevention)
- No execution of code in session data
- Read-only access to session files

**Performance**:
- Typical: <10ms for average session file (500-1000 bytes)
- Worst case: <50ms for large session files (10K+ bytes)

#### should_retry(state: LoopBackState) -> bool

Check if retry should proceed (under max attempts and circuit breaker not triggered).

**Parameters**:
- `state` (LoopBackState): Current loop-back state

**Returns**: True if retry allowed, False otherwise

**Logic**:
1. Check circuit breaker first (if 3+ consecutive failures, return False)
2. Check if circuit breaker open flag set (return False)
3. Check if attempt_count >= max_attempts (return False)
4. Otherwise return True

**Features**:
- Prevents infinite retry loops via circuit breaker
- Prevents resource exhaustion via max attempt limit
- Checks circuit breaker before max attempts check (fail-fast)

#### get_next_retry_delay(attempt: int) -> float

Calculate exponential backoff delay for next retry.

**Parameters**:
- `attempt` (int): Current attempt number (0-based)

**Returns**: Delay in milliseconds as float

**Backoff Schedule**:
- Attempt 0: 100ms (BASE_RETRY_DELAY_MS)
- Attempt 1: 200ms (100 * 2^1)
- Attempt 2: 400ms (100 * 2^2)
- Attempt 3: 800ms (100 * 2^3)
- Attempt 4: 1600ms (100 * 2^4)
- Max: 5000ms (BACKOFF_MAX_MS, capped)

**Formula**:
```
delay = BASE_RETRY_DELAY_MS * (BACKOFF_MULTIPLIER ^ attempt)
delay = min(delay, BACKOFF_MAX_MS)
```

**Features**:
- Exponential backoff prevents server overload on transient failures
- Capped at 5000ms to prevent excessive delays
- Graceful degradation if attempt < 0 (returns BASE_RETRY_DELAY_MS)

#### load_loop_back_state(state_file: Path) -> Optional[LoopBackState]

Load retry state from JSON file.

**Parameters**:
- `state_file` (Path): Path to loop-back state JSON file

**Returns**: `LoopBackState` if file exists and valid, None otherwise

**Features**:
- Handles file not found gracefully (returns None)
- Handles JSON parse errors gracefully (logs error, returns None)
- Deserializes LoopBackState from JSON
- Validates required fields present

**Security**:
- Path validation for state_file
- No code execution from loaded state

#### save_loop_back_state(state: LoopBackState, state_file: Path) -> bool

Save retry state to JSON file.

**Parameters**:
- `state` (LoopBackState): State to save
- `state_file` (Path): Path to write state file

**Returns**: True if save succeeded, False otherwise

**Features**:
- Atomic write via tempfile + rename pattern
- Creates parent directories if needed
- Handles permission errors gracefully
- Updates timestamp on save

**Security**:
- Atomic write prevents corruption on interruption
- No sensitive data in state file (session IDs only)

#### clear_loop_back_state(state_file: Path) -> bool

Delete retry state file after successful completion.

**Parameters**:
- `state_file` (Path): Path to state file to delete

**Returns**: True if deleted or doesn't exist, False if error

**Features**:
- Idempotent (returns True if file doesn't exist)
- Handles permission errors gracefully
- Logs all operations for audit trail

#### create_loop_back_checkpoint(session_id: str, missing_agents: List[str], state_dir: Path) -> bool

Create a loop-back checkpoint for incomplete work.

**Parameters**:
- `session_id` (str): Session identifier
- `missing_agents` (List[str]): List of agent names not found
- `state_dir` (Path): Directory to save state

**Returns**: True if checkpoint created, False otherwise

**Features**:
- Creates LoopBackState with initial values
- Sets attempt_count = 0 (fresh retry attempt)
- Initializes consecutive_failures = 0
- Records timestamp of checkpoint creation
- Saves state atomically

### CompletionVerifier Class

Main verification engine with session file handling.

#### __init__(session_id: str, state_dir: Optional[Path] = None)

Initialize verifier for a session.

**Parameters**:
- `session_id` (str): Session identifier
- `state_dir` (Optional[Path]): State directory (defaults to `./.claude`)

**Features**:
- Stores session_id for later verification
- Resolves state_dir with fallback to `./.claude`
- Prepares state file path (`.claude/loop_back/{session_id}.json`)

#### verify() -> VerificationResult

Run verification check on the session.

**Returns**: `VerificationResult` with completion status

**Features**:
- Calls `verify_pipeline_completion()` with stored session_id
- Returns result for caller to handle retry logic
- Non-blocking (always returns a result)

#### get_retry_state() -> Optional[LoopBackState]

Load current retry state if exists.

**Returns**: `LoopBackState` if state file exists, None otherwise

**Features**:
- Loads from persistent state file
- Returns None if first check or state cleared

#### update_retry_state(state: LoopBackState) -> None

Update retry state with current attempt.

**Parameters**:
- `state` (LoopBackState): State to persist

**Features**:
- Increments attempt_count
- Updates timestamp
- Saves to disk atomically

#### clear_state_on_success() -> bool

Delete state file after successful completion.

**Returns**: True if cleared or doesn't exist, False if error

**Features**:
- Idempotent (safe to call multiple times)
- Graceful degradation on permission errors

#### get_state() -> Optional[LoopBackState]

Alias for `get_retry_state()` for consistency with other APIs.

**Returns**: `LoopBackState` if exists, None otherwise

### Configuration Constants

```python
# Expected agents in pipeline order (8 total)
EXPECTED_AGENTS = [
    "researcher-local",
    "researcher-web",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master"
]

# Retry configuration
MAX_RETRY_ATTEMPTS = 5
CIRCUIT_BREAKER_THRESHOLD = 3
BASE_RETRY_DELAY_MS = 100
BACKOFF_BASE_MS = 100
BACKOFF_MULTIPLIER = 2
BACKOFF_MAX_MS = 5000
```

### Usage Example

Basic verification with retry logic:

```python
from pathlib import Path
from completion_verifier import CompletionVerifier, should_retry
import time

# Initialize verifier
verifier = CompletionVerifier(session_id="session_123")

# Check if complete
result = verifier.verify()
if result.complete:
    print(f"Pipeline complete: {len(result.agents_found)} agents")
    verifier.clear_state_on_success()
else:
    print(f"Missing agents: {result.missing_agents}")

    # Load or create retry state
    state = verifier.get_retry_state()
    if state is None:
        # First check - create new state
        from completion_verifier import create_loop_back_checkpoint
        create_loop_back_checkpoint("session_123", result.missing_agents, Path(".claude"))
        state = verifier.get_retry_state()

    # Check if should retry
    if should_retry(state):
        # Wait with exponential backoff
        from completion_verifier import get_next_retry_delay
        delay_ms = get_next_retry_delay(state.attempt_count)
        time.sleep(delay_ms / 1000)

        # Update attempt counter
        state.attempt_count += 1
        state.last_attempt_timestamp = datetime.now().isoformat()
        verifier.update_retry_state(state)

        # Retry verification (would be called again by hook)
        print(f"Retrying verification (attempt {state.attempt_count}/{state.max_attempts})")
    else:
        print(f"Max retries exceeded or circuit breaker open")
        # Handle permanent failure
```

### Security Considerations

**Path Traversal (CWE-22)**:
- All file operations validated via `security_utils.validate_path()`
- State files isolated to `.claude/loop_back/` directory
- Session IDs must match `^[a-zA-Z0-9_-]+$` pattern

**Denial of Service**:
- Circuit breaker prevents infinite retry loops
- Max attempt limit prevents resource exhaustion
- Exponential backoff prevents server overload

**Data Integrity**:
- Atomic writes via tempfile + rename prevent corruption
- State files contain only non-sensitive metadata

### Test Coverage

Test Files:
- `tests/unit/lib/test_completion_verifier.py` (26 tests)
- `tests/unit/hooks/test_verify_completion_hook.py` (25 tests)

Coverage: 51 test cases covering:
- Verification logic (all 8 agents, missing agents)
- Circuit breaker (opening/closing, state persistence)
- Exponential backoff (all retry attempts, max delay capping)
- State persistence (load/save, file handling)
- Error handling (invalid session, file not found, JSON errors)
- Edge cases (empty session, duplicate agents, agent ordering)
- Integration with hook lifecycle

Target: 90+% coverage

### Used By

- verify_completion.py - SubagentStop hook for pipeline completion
- /auto-implement pipeline - Verifies all agents completed
- Batch processing - Validates pipeline completion per feature

### Related Components

Dependencies:
- pathlib - Path handling
- json - State serialization
- time - Performance timing
- logging - Audit logging
- datetime - Timestamp recording
- dataclasses - Data structures

See Also:
- `plugins/autonomous-dev/hooks/verify_completion.py` - Hook integration
- `docs/HOOKS.md` - Hook documentation
- GitHub Issue #170 - Feature tracking

---


## 59. hook_exit_codes.py (139 lines, v4.0.0+)

**Purpose**: Standardized exit code constants and lifecycle constraints for all hooks

**Location**: `plugins/autonomous-dev/lib/hook_exit_codes.py`

### Overview

Defines symbolic constants for hook exit codes and lifecycle constraints that determine which exit codes are valid for different hook types. Prevents hardcoded exit codes scattered throughout hook implementations.

### Constants

#### Exit Code Constants

```python
EXIT_SUCCESS = 0  # Operation succeeded, continue workflow normally
EXIT_WARNING = 1  # Non-critical issue detected, continue workflow with warning
EXIT_BLOCK = 2    # Critical issue detected, block workflow (if lifecycle supports it)
```

### Lifecycle Constraints

Defines allowed exit codes for each hook lifecycle:

```python
LIFECYCLE_CONSTRAINTS = {
    "PreToolUse": {
        "allowed_exits": [EXIT_SUCCESS],
        "can_block": False,
        "description": "PreToolUse hooks run AFTER user approved tool execution..."
    },
    "SubagentStop": {
        "allowed_exits": [EXIT_SUCCESS],
        "can_block": False,
        "description": "SubagentStop hooks run AFTER agent completes..."
    },
    "PreSubagent": {
        "allowed_exits": [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK],
        "can_block": True,
        "description": "PreSubagent hooks run BEFORE agent spawn..."
    },
}
```

### Functions

#### `can_lifecycle_block(lifecycle: str) -> bool`

**Purpose**: Check if a lifecycle can block workflow

**Parameters**:
- `lifecycle` (str): Hook lifecycle name (PreToolUse, SubagentStop, PreSubagent, etc.)

**Returns**: `bool` - True if lifecycle can exit with EXIT_BLOCK (2)

**Raises**: `KeyError` if lifecycle not defined

**Examples**:
```python
>>> can_lifecycle_block("PreToolUse")
False

>>> can_lifecycle_block("PreSubagent")
True
```

#### `is_exit_allowed(lifecycle: str, exit_code: int) -> bool`

**Purpose**: Check if an exit code is allowed for a given lifecycle

**Parameters**:
- `lifecycle` (str): Hook lifecycle name
- `exit_code` (int): Exit code to check (0, 1, or 2)

**Returns**: `bool` - True if exit code is allowed for lifecycle

**Raises**: `KeyError` if lifecycle not defined

**Examples**:
```python
>>> is_exit_allowed("PreToolUse", EXIT_BLOCK)
False

>>> is_exit_allowed("PreSubagent", EXIT_BLOCK)
True

>>> is_exit_allowed("SubagentStop", EXIT_SUCCESS)
True
```

#### `get_lifecycle_description(lifecycle: str) -> str`

**Purpose**: Get description of lifecycle constraints

**Parameters**:
- `lifecycle` (str): Hook lifecycle name

**Returns**: `str` - Description explaining lifecycle constraints and valid exit codes

**Raises**: `KeyError` if lifecycle not defined

**Examples**:
```python
>>> desc = get_lifecycle_description("PreToolUse")
>>> print(desc)
PreToolUse hooks run before tool execution. They MUST always exit 0...
```

### Lifecycle Breakdown

#### PreToolUse
- **When**: Runs before tool execution
- **Allowed exits**: EXIT_SUCCESS (0) only
- **Can block**: No
- **Why**: User already approved tool, cannot retroactively prevent execution
- **Use**: Logging, permission checks, security validation (all non-blocking)

#### SubagentStop
- **When**: Runs after agent completes
- **Allowed exits**: EXIT_SUCCESS (0) only
- **Can block**: No
- **Why**: Agent work already done, cannot block after completion
- **Use**: Post-processing (git commits), logging, completion verification

#### PreSubagent
- **When**: Runs before agent spawns
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes
- **Why**: Agent hasn't run yet, can prevent invalid work from starting
- **Use**: Quality gates, validation before expensive operations

#### PreCommit
- **When**: Runs before commit
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes
- **Why**: Commit hasn't happened yet, can enforce requirements
- **Use**: Code quality validation, test coverage checks, lint rules

#### PostCommit
- **When**: Runs after commit
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes (won't affect already-committed changes)
- **Use**: Notifications, statistics updates

#### UserPromptSubmit
- **When**: Runs when user submits prompt
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes
- **Why**: Submission not yet processed, can prevent invalid submissions
- **Use**: Input validation, alignment checks

### Usage Examples

**Basic Success Pattern**:
```python
from hook_exit_codes import EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
import sys

if validation_passes:
    sys.exit(EXIT_SUCCESS)  # Exit 0 - Workflow continues
```

**Lifecycle-Aware Exit Code**:
```python
from hook_exit_codes import (
    EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK,
    can_lifecycle_block, get_lifecycle_description
)
import os
import sys

lifecycle = os.environ.get("HOOK_LIFECYCLE", "PreCommit")

if critical_issue_detected:
    if can_lifecycle_block(lifecycle):
        sys.exit(EXIT_BLOCK)  # Exit 2 - Block workflow
    else:
        # This lifecycle cannot block - use warning instead
        print(f"WARNING: {get_lifecycle_description(lifecycle)}")
        sys.exit(EXIT_WARNING)  # Exit 1 - Continue with warning
else:
    sys.exit(EXIT_SUCCESS)
```

**Validation Check Pattern**:
```python
from hook_exit_codes import is_exit_allowed, LIFECYCLE_CONSTRAINTS
import sys

lifecycle = "PreToolUse"
proposed_exit = 2  # EXIT_BLOCK

if not is_exit_allowed(lifecycle, proposed_exit):
    print(f"ERROR: {lifecycle} cannot exit {proposed_exit}")
    print(f"Allowed exits: {LIFECYCLE_CONSTRAINTS[lifecycle]['allowed_exits']}")
    sys.exit(1)
```

### Design Benefits

1. **Semantic Clarity**: `EXIT_BLOCK` clearer than hardcoded `sys.exit(2)`
2. **Self-Documenting**: Constant names explain intent
3. **Prevents Inversion Bugs**: Harder to accidentally swap exit codes
4. **Centralized Definition**: Single source of truth (not scattered across hooks)
5. **Type Safety**: Import errors caught at startup, not runtime
6. **Lifecycle Validation**: Prevents invalid exit codes for hook type
7. **Discoverability**: Easy to view all constraints via LIFECYCLE_CONSTRAINTS dict

### Constraints

**Important Restrictions**:
- PreToolUse hooks: Must always exit 0 (cannot block)
- SubagentStop hooks: Must always exit 0 (cannot block)
- All other hooks: Can exit 0, 1, or 2

**Why**: PreToolUse and SubagentStop run at moments when blocking is impossible (tool already approved, agent already complete).

### Test Coverage

Test File: `tests/unit/lib/test_hook_exit_codes.py` (23 tests)

Coverage includes:
- **Constants**: Exit code values (0, 1, 2), distinctness, type validation, range validation
- **Lifecycle constraints**: All 3 lifecycles exist, constraints complete, required keys present
- **Allowed exits**: Each lifecycle has proper allowed exits list
- **Can block**: Correctly identifies which lifecycles support blocking
- **Documentation**: Module and constraint descriptions exist
- **Helper functions**: All 3 helper functions work correctly
- **Error cases**: Invalid lifecycles raise KeyError, invalid exits detected
- **Usage patterns**: Common patterns (success, warning, block, lifecycle checks) work

Target: 100% coverage of exit code semantics

### Used By

Hooks throughout autonomous-dev:
- All PreCommit hooks
- All PreSubagent hooks
- All PostCommit hooks
- All UserPromptSubmit hooks

Examples:
- `unified_code_quality.py` - PreCommit, can block on test failures
- `verify_completion.py` - SubagentStop, must exit 0
- `auto_tdd_enforcer.py` - PreSubagent, can block on missing tests

### Related

**Documentation**:
- [HOOKS.md - Exit Code Semantics section](HOOKS.md#exit-code-semantics)
- [HOOKS.md - Lifecycle Constraints](HOOKS.md#lifecycle-constraints)

**Implementation**:
- `plugins/autonomous-dev/lib/hook_exit_codes.py` (139 lines)
- `tests/unit/lib/test_hook_exit_codes.py` (23 tests)

**GitHub**: Feature tracking (Issue TBD)


---

## 60. status_tracker.py (363 lines, v1.0.0 - Issue #174)

**Purpose**: Manages test execution status for pre-commit gate hook (block-at-submit validation).

**Problem**: Need reliable test status tracking across different processes so pre-commit hook can check if tests passed before allowing commit.

**Solution**: Provides JSON-based status persistence with cross-process communication between test runners and pre-commit gate hook.

### API

#### `get_status_file_path() -> Path`

**Purpose**: Get path to test status JSON file

**Returns**: Path object pointing to test-status.json in temp directory

**Location**: /tmp/.autonomous-dev/test-status.json (Linux/macOS) or system temp (Windows)

**Security**:
- Returns absolute path (prevents relative path attacks)
- No user input in path construction
- Path is deterministic and not user-controllable

**Examples**:
```python
from status_tracker import get_status_file_path
path = get_status_file_path()
assert path.is_absolute()
assert ".autonomous-dev" in str(path)
```

#### `write_status(passed: bool, timestamp: Optional[str] = None) -> None`

**Purpose**: Write test execution status to JSON file

**Parameters**:
- `passed` (bool): True if tests passed, False if failed
- `timestamp` (str, optional): ISO 8601 timestamp (defaults to current time)

**Raises**:
- `ValueError`: If timestamp format is invalid
- `OSError`: If file cannot be written (permissions, disk full, etc.)

**Security**:
- Atomic writes: Write to temp file, then rename
- Secure permissions: 0600 (user-only read/write)
- Path validation: Prevents traversal and symlink attacks (CWE-22, CWE-59)
- Input validation: Validates timestamp format

**Status File Format**:
```json
{
  "passed": true,
  "timestamp": "2026-01-01T12:00:00Z",
  "last_run": "2026-01-01T12:00:00.123456Z"
}
```

**Usage Examples**:
```python
from status_tracker import write_status

# After successful test run (auto-timestamp)
write_status(passed=True)

# After failed test run (auto-timestamp)
write_status(passed=False)

# With explicit timestamp
write_status(passed=True, timestamp="2026-01-01T12:00:00Z")
```

#### `read_status() -> Dict[str, Any]`

**Purpose**: Read test execution status from JSON file

**Returns**: Dictionary with keys:
- `passed` (bool): True if tests passed, False otherwise
- `timestamp` (str | None): ISO 8601 timestamp of test run
- `last_run` (str | None): ISO 8601 timestamp of status update

**Graceful Degradation**:
- Missing file: Returns safe default (passed=False)
- Corrupted JSON: Returns safe default (passed=False)
- Missing fields: Adds default values
- Invalid types: Returns safe default (passed=False)
- Permission errors: Returns safe default (passed=False)
- Symlinks detected: Returns safe default (passed=False)

**Security**:
- Validates path before reading (prevents traversal - CWE-22)
- Checks for symlinks (prevents attack - CWE-59)
- Handles permission errors gracefully
- Never exposes sensitive data from corrupted files

**Usage Examples**:
```python
from status_tracker import read_status

status = read_status()
if status["passed"]:
    print("Tests passed!")
else:
    print("Tests failed or not run")

# Check timestamp
if status["timestamp"]:
    print(f"Last run: {status['timestamp']}")
```

### Integration

**With pre_commit_gate hook**:
```python
# pre_commit_gate.py reads status to decide whether to block
from status_tracker import read_status

status = read_status()
if status["passed"]:
    sys.exit(EXIT_SUCCESS)  # Allow commit
else:
    sys.exit(EXIT_BLOCK)    # Block commit
```

**With test-master agent in /auto-implement**:
```python
# test-master writes status after running tests
from status_tracker import write_status

# After all tests pass
write_status(passed=True)

# Or if tests fail
write_status(passed=False)
```

### Configuration

**Environment Variables**: None (file path is deterministic)

**Status File Permissions**: 0600 (user-only read/write)

**ISO 8601 Timestamps**: All timestamps use UTC timezone for cross-platform compatibility

### Error Handling

**Atomic Write Strategy**:
- Write to temporary file first
- Rename temp file to target atomically (prevents corruption)
- Clean up temp file on error
- Raises OSError with context if write fails

**Safe Defaults on Read Errors**:
- Any read error returns {"passed": False, ...} (fail-safe)
- Prevents false positives (incorrect "tests passed" claims)
- Never blocks on missing/corrupted status
- Clear error messages in logs for debugging

### Examples

**Basic workflow**:
```python
# 1. Test runner writes status after execution
from status_tracker import write_status
import subprocess

result = subprocess.run(["pytest"], capture_output=True)
if result.returncode == 0:
    write_status(passed=True)
else:
    write_status(passed=False)

# 2. Pre-commit hook reads status
from status_tracker import read_status

status = read_status()
if status["passed"]:
    # Allow commit
    sys.exit(0)
else:
    # Block commit
    sys.exit(2)
```

**With /auto-implement pipeline**:
```python
# test-master agent runs tests and writes status
write_status(passed=all_tests_pass)

# When user commits, pre_commit_gate checks status
# Status is already written by test-master
# Gate blocks or allows based on status
```

### Test Coverage

Test File: tests/unit/lib/status_tracker.py

Coverage includes:
- **Get path**: Path is absolute, contains expected directory
- **Write status**: File created, permissions set, JSON valid
- **Read status**: Returns correct structure, handles missing file
- **Atomic writes**: Temp file cleanup on error
- **Security**: Symlink detection, path validation, permission checks
- **Graceful degradation**: Corrupted JSON handled, missing fields defaulted
- **Timestamp validation**: Valid ISO 8601 accepted, invalid rejected
- **Cross-process**: Multiple writes/reads work correctly

Target: 95% coverage of core functionality

### Used By

- `pre_commit_gate.py` hook - Reads status to determine commit permission
- `test-master` agent in `/auto-implement` - Writes status after test execution
- Manual pytest runs - Users can write status via CLI

### Related

**Documentation**:
- [HOOKS.md - pre_commit_gate.py section](HOOKS.md#pre_commit_gatepy)
- [docs/DEVELOPMENT.md - TDD workflow](docs/DEVELOPMENT.md)

**Implementation**:
- `plugins/autonomous-dev/lib/status_tracker.py` (363 lines)
- `plugins/autonomous-dev/hooks/pre_commit_gate.py` (299 lines)
- `tests/unit/lib/status_tracker.py`

**GitHub**: Issue #174 - Block-at-submit hook with test status tracking


## 61. worktree_manager.py (684 lines, v1.0.0 - Issue #178)

**Purpose**: Safe git worktree isolation for parallel feature development

**Problem**: Developers need to work on multiple features in parallel without affecting the main branch. Standard branching requires switching contexts repeatedly.

**Solution**: Comprehensive git worktree management system with automatic isolation, collision detection, and safe merge operations.

### Features

- **Create worktrees**: Spawn isolated working directories for each feature
- **List worktrees**: Display all active worktrees with metadata (status, branch, commit, creation time)
- **Delete worktrees**: Remove worktrees with optional force flag for uncommitted changes
- **Merge worktrees**: Merge worktree branches back to target branch with conflict detection
- **Prune stale**: Automatically clean up orphaned/old worktrees (configurable age threshold)
- **Path queries**: Get worktree path by feature name
- **Security**: Path traversal prevention (CWE-22), command injection prevention (CWE-78), symlink resolution (CWE-59)
- **Graceful degradation**: Failures don't crash, return error tuples for safe handling
- **Atomic operations**: Collision detection with timestamp suffix for duplicate names
- **Parallel development**: Work on 5+ features simultaneously without branch switching

### Main Components

#### Data Classes

**WorktreeInfo**: Metadata about a worktree

- name: str - Feature name
- path: Path - Absolute path to worktree
- branch: Optional[str] - Branch name (None if detached)
- commit: str - Short commit SHA
- status: str - 'active', 'stale', or 'detached'
- created_at: datetime - Creation timestamp

**MergeResult**: Result of merge operation

- success: bool - Whether merge completed
- conflicts: List[str] - Files with conflicts
- merged_files: List[str] - Successfully merged files
- error_message: str - Error details if failed

#### Main Functions

#### create_worktree(feature_name, base_branch='master') -> Tuple[bool, Union[Path, str]]

- **Purpose**: Create isolated worktree for feature development
- **Parameters**:
  - feature_name (str): Feature name (alphanumeric, hyphens, underscores, dots only)
  - base_branch (str): Base branch to branch from (default: 'master')
- **Returns**: Tuple of (success, result) where result is Path on success or error_message on failure
- **Security**: Validates feature name (CWE-22, CWE-78), uses subprocess list args (no shell), resolves symlinks
- **Collision Handling**: If feature name exists, appends timestamp (YYYYMMDD-HHMMSS)
- **Errors Handled**:
  - Empty/invalid feature name
  - Path traversal attempts
  - Branch already checked out
  - Invalid/missing base branch
  - No disk space
  - Timeout (30s)

#### list_worktrees() -> List[WorktreeInfo]

- **Purpose**: List all git worktrees with metadata
- **Parameters**: None
- **Returns**: List of WorktreeInfo objects (empty list on error)
- **Status Detection**:
  - active: Worktree exists and on a branch
  - stale: Worktree directory doesn't exist
  - detached: Worktree in detached HEAD state
- **Performance**: Uses git porcelain format for efficient parsing

#### delete_worktree(feature_name, force=False) -> Tuple[bool, str]

- **Purpose**: Delete a worktree
- **Parameters**:
  - feature_name (str): Feature name of worktree to delete
  - force (bool): Force deletion even with uncommitted changes (default: False)
- **Returns**: Tuple of (success, message)
- **Validation**: Checks feature name format before deletion
- **Errors Handled**:
  - Worktree not found
  - Uncommitted changes (unless force=True)
  - Permission denied

#### merge_worktree(feature_name, target_branch='master') -> MergeResult

- **Purpose**: Merge worktree branch back to target branch
- **Parameters**:
  - feature_name (str): Feature name to merge
  - target_branch (str): Target branch for merge (default: 'master')
- **Returns**: MergeResult with success/conflicts/merged_files/error_message
- **Merge Flow**:
  1. Validate feature name
  2. Checkout target branch
  3. Merge feature branch
  4. Get list of merged files (if successful)
  5. Detect conflicts (if merge failed)
- **Conflict Detection**: Uses multiple strategies
  - git diff --name-only --diff-filter=U (unmerged)
  - git status --porcelain with status codes (UU, AA, DD, AU, UA, DU, UD)
- **Errors Handled**:
  - Invalid feature name
  - Target branch not found
  - Detached HEAD state
  - Merge conflicts
  - Timeout (30s)

#### prune_stale_worktrees(max_age_days=7) -> int

- **Purpose**: Remove stale/orphaned worktrees
- **Parameters**:
  - max_age_days (int): Maximum age threshold in days (default: 7)
- **Returns**: Number of worktrees pruned
- **Pruning Criteria**:
  - Worktree directory doesn't exist (orphaned)
  - Worktree older than max_age_days (uses directory mtime)
  - Only prunes managed worktrees (containing 'worktrees' in path)
  - Skips main repository

#### get_worktree_path(feature_name) -> Optional[Path]

- **Purpose**: Get path to a worktree by feature name
- **Parameters**: feature_name (str): Feature name
- **Returns**: Path to worktree or None if not found

### Internal Functions

#### _validate_feature_name(name) -> Tuple[bool, str]

- **Purpose**: Security validation for feature names
- **Checks**:
  - Non-empty string
  - No path traversal (.., /)
  - No shell injection (;, &, |, parentheses)
  - Only alphanumeric, hyphens, underscores, dots
- **Returns**: Tuple of (is_valid, error_message)

#### _get_worktree_base_dir() -> Path

- **Purpose**: Get base directory for worktrees (.worktrees/ in cwd)
- **Returns**: Path to .worktrees directory
- **Note**: Uses current working directory, no git calls needed

### Configuration

**Environment Variables**: None (configuration is function parameters)

**Default Worktree Location**: .worktrees/<feature-name>/ in current directory

**Naming Conventions**:
- Feature names: alphanumeric, hyphens, underscores, dots only
- Directory structure: <repo>/.worktrees/<feature-name>/
- Collision handling: <feature-name>-YYYYMMDD-HHMMSS if name exists

### Security Analysis

**Threat Model**:
1. **Path Traversal (CWE-22)**: Blocked by feature name validation (no .., /)
2. **Command Injection (CWE-78)**: Blocked by subprocess list args (no shell=True), feature name validation
3. **Symlink Attacks (CWE-59)**: Blocked by Path.resolve() during worktree path generation

**Validation Layers**:
1. Feature name validation (regex check)
2. subprocess list args (no shell interpolation)
3. Path resolution (symlink detection via resolve())
4. Error messages (no stderr leakage)

### Error Handling Strategy

**All functions return safe tuples/objects**:
- create_worktree(): (bool, Union[Path, str]) - easy error checking
- delete_worktree(): (bool, str) - message for logging
- merge_worktree(): MergeResult dataclass - structured conflict info
- list_worktrees(): List[WorktreeInfo] - empty list on error
- prune_stale_worktrees(): int - 0 on error
- get_worktree_path(): Optional[Path] - None if not found

**Exceptions**: Only raises on programming errors, not operational failures

### Performance

- **Create worktree**: ~1-2 seconds (git worktree add + symlink resolution)
- **List worktrees**: ~50-100ms (porcelain parsing)
- **Merge worktree**: ~0.5-5 seconds (depends on file count)
- **Prune stale**: ~100-500ms (depends on number of worktrees)
- **Get path**: ~5-10ms (list + lookup)

### Test Coverage

**Unit Tests** (40 tests in tests/unit/test_worktree_manager.py):
- Feature name validation (empty, path traversal, injection, invalid chars)
- Worktree creation (success, collision handling, branch errors)
- Worktree listing (parsing, status detection, metadata)
- Worktree deletion (success, force flag, not found)
- Merge operations (success, conflicts, checkout errors)
- Prune operations (stale detection, orphaned cleanup)
- Path queries (found, not found, empty list)
- Mock git commands for offline testing

**Integration Tests** (18 tests in tests/integration/test_worktree_integration.py):
- Real git repository setup/teardown
- Actual worktree creation and listing
- Branch checkout and merge workflows
- Conflict detection and handling
- File operations during merge
- Cleanup after each test

**Coverage Target**: 95% of code paths, 100% of security-critical paths

### Files Added

- plugins/autonomous-dev/lib/worktree_manager.py (684 lines)
- tests/unit/test_worktree_manager.py (927 lines, 40 tests)
- tests/integration/test_worktree_integration.py (702 lines, 18 tests)
- .gitignore updated (added .worktrees/)

### Documentation

- docs/LIBRARIES.md Section 61 (this section)
- Comprehensive docstrings with examples
- Type hints on all functions

### Integration Points

**Used By**:
- /auto-implement command (future feature branch isolation)
- Parallel feature development workflows
- Batch feature processing (potential future use)

**Related**:
- git_operations.py Section 16 - Helper functions (is_worktree, get_worktree_parent)

### GitHub

- Issue #178 - Git worktree isolation feature
- Related: Issue #177 (Stop hook quality gates), #175 (Agent audit), #174 (Test passage enforcement)

### Related Documentation

- docs/GIT-AUTOMATION.md - Git automation workflows
- docs/SECURITY.md - Security hardening guide
- git_operations.py Section 16 - Worktree helper functions

---

## 62. memory_layer.py (766 lines, v1.0.0 - Issue #179)

**Purpose**: Cross-session memory layer for context continuity - persistent memory storage across /auto-implement sessions enabling agents to remember architectural decisions, blockers, patterns, and context without re-research.

**Location**: `plugins/autonomous-dev/lib/memory_layer.py`

### Problem Statement

Issue #179 identified that context resets between /auto-implement sessions force expensive re-research:
- No persistent memory between sessions
- Architectural decisions must be rediscovered
- Blocker knowledge is lost
- Pattern findings don't carry over

### Solution

A JSON-based memory layer stored in `.claude/memory.json` with:
- **Memory types**: feature, decision, blocker, pattern, context
- **Utility scoring**: Recency decay + access frequency ranking
- **PII sanitization**: API keys, passwords, emails, JWT tokens redacted
- **Atomic writes**: Temp file + rename pattern prevents corruption
- **Thread-safe operations**: File locking for concurrent access
- **Graceful degradation**: Storage errors don't crash workflow

### Key Functions

```python
from memory_layer import MemoryLayer, sanitize_pii, calculate_utility_score

# Initialize layer
layer = MemoryLayer()  # Uses .claude/memory.json
layer = MemoryLayer(memory_file=Path("/custom/path.json"))

# Store a memory
memory_id = layer.remember(
    memory_type="decision",
    content={"title": "Database Choice", "summary": "Chose PostgreSQL for ACID compliance"},
    metadata={"tags": ["database", "architecture"]}
)

# Retrieve memories
all_memories = layer.recall()  # All memories, sorted by utility score
decisions = layer.recall(memory_type="decision")  # Filter by type
tagged = layer.recall(filters={"tags": ["database"]})  # Filter by tags
recent = layer.recall(filters={"after": "2026-01-01T00:00:00Z"})  # Date filter

# Forget memories
count = layer.forget(memory_id="mem_123")  # By ID
count = layer.forget(filters={"tags": ["deprecated"]})  # By filter

# Prune old/low-utility memories
removed = layer.prune(max_entries=1000, max_age_days=90)

# Get statistics
summary = layer.get_summary()  # Returns dict with counts, scores, etc.

# PII sanitization (automatic in remember, available standalone)
safe_text = sanitize_pii("API key: sk-1234abcd for user@example.com")
# Returns: "API key: [REDACTED_API_KEY] for [REDACTED_EMAIL]"

# Utility scoring
score = calculate_utility_score(created_at=datetime.now(), access_count=5)
```

### Memory Structure

```json
{
    "version": "1.0.0",
    "memories": [
        {
            "id": "mem_20260102_153042_abc123",
            "type": "decision",
            "content": {
                "title": "Database Choice",
                "summary": "Chose PostgreSQL for ACID compliance"
            },
            "metadata": {
                "created_at": "2026-01-02T15:30:42Z",
                "updated_at": "2026-01-02T15:30:42Z",
                "access_count": 3,
                "tags": ["database", "architecture"],
                "utility_score": 0.85
            }
        }
    ]
}
```

### Security Features

- **CWE-22 Prevention**: Path traversal validation via validate_path()
- **CWE-59 Prevention**: Symlink detection and rejection
- **CWE-359 Prevention**: PII sanitization (API keys, passwords, emails, JWTs)
- **Atomic writes**: Prevents corruption from interrupted writes
- **File locking**: Thread-safe concurrent access
- **Audit logging**: All operations logged (with safe wrapper for test env)

### Utility Scoring Algorithm

```python
utility_score = recency_score * (1 - weight) + frequency_score * weight

# Recency: Exponential decay with 30-day half-life
recency_score = 2 ** (-age_days / 30)

# Frequency: Normalized by max access count (20)
frequency_score = min(1.0, access_count / 20)

# Weight: 0.3 (30% frequency, 70% recency)
```

### Test Coverage

**Unit Tests** (47 tests in tests/unit/lib/test_memory_layer.py):
- Initialization with default and custom paths
- Remember operations (storage, ID generation, PII sanitization)
- Recall operations (filtering, sorting, access tracking)
- Forget operations (by ID, by filter)
- Prune operations (age limit, entry limit)
- PII sanitization (API keys, passwords, emails, JWTs)
- Utility scoring (recency decay, access frequency)
- Security validation (path traversal, symlinks)
- Concurrent access safety

**Integration Tests** (16 tests in tests/integration/test_memory_integration.py):
- Cross-session persistence
- Auto-implement pipeline integration
- Multi-agent memory sharing
- Batch processing cleanup
- Memory migration and versioning

**Coverage Target**: 95% of code paths, 100% of security-critical paths

### Files Added

- plugins/autonomous-dev/lib/memory_layer.py (766 lines)
- tests/unit/lib/test_memory_layer.py (63 tests, ~1000 lines)
- tests/integration/test_memory_integration.py (16 tests, ~600 lines)

### Integration Points

**Used By**:
- /auto-implement command (agent memory persistence)
- Planner agent (recall previous decisions)
- Researcher agent (cache pattern findings)
- Implementer agent (recall blockers)

**Dependencies**:
- security_utils.py - validate_path(), audit_log()
- path_utils.py - get_project_root()

### GitHub

- Issue #179 - Cross-session memory layer for context continuity
- Related: Issue #178 (Git worktree isolation), #180 (Review/merge/discard)

### Related Documentation

- docs/SECURITY.md - Security hardening guide
- docs/LIBRARIES.md Section 6 (security_utils.py) - Path validation
- docs/LIBRARIES.md Section 15 (path_utils.py) - Project root detection
## 63. complexity_assessor.py (441 lines, v1.0.0 - Issue #181)

**Purpose**: Automatic complexity assessment for pipeline scaling

**Key Concepts**:
- Keyword-based heuristics for fast complexity classification
- Confidence scoring to indicate assessment certainty
- Agent count and time recommendations based on complexity
- Security-first approach: COMPLEX keywords override SIMPLE keywords

### Classes

#### `ComplexityLevel` (Enum)

**Values**:
- `SIMPLE` - Simple changes (typos, docs, formatting) - 3 agents, ~8 min
- `STANDARD` - Standard features (bug fixes, small features) - 6 agents, ~15 min
- `COMPLEX` - Complex features (auth, security, APIs) - 8 agents, ~25 min

#### `ComplexityAssessment` (NamedTuple)

**Attributes**:
- `level` (ComplexityLevel): Assessed complexity level (SIMPLE/STANDARD/COMPLEX)
- `confidence` (float): Confidence score for assessment (0.0-1.0)
- `reasoning` (str): Human-readable explanation of classification
- `agent_count` (int): Recommended number of agents (3/6/8)
- `estimated_time` (int): Estimated time in minutes (8/15/25)

#### `ComplexityAssessor` (Class)

**Design**:
- Stateless: No instance variables, all methods can be class methods
- Keyword-based: Fast heuristics for common patterns
- Conservative: Defaults to STANDARD when uncertain
- Security-first: COMPLEX keywords override SIMPLE keywords

**Keyword Sets**:
- SIMPLE_KEYWORDS: typo, spelling, docs, documentation, readme, rename, format, formatting, comment, whitespace, indentation, style, lint, pep8, black
- COMPLEX_KEYWORDS: auth, authentication, authorization, security, encrypt, encryption, jwt, oauth, oauth2, saml, ldap, password, credential, token, api, webhook, database, migration, schema

### Methods

#### `assess(feature_description, github_issue=None)` - Main entry point

**Signature**: `@classmethod assess(feature_description: str, github_issue: Optional[Dict] = None) -> ComplexityAssessment`

**Purpose**: Assess complexity of a feature request

**Parameters**:
- `feature_description` (str): Feature request text to analyze
- `github_issue` (Optional[Dict]): GitHub issue dict with 'title' and 'body' keys (optional)

**Returns**: ComplexityAssessment with level, confidence, reasoning, agent_count, time

**Edge Cases**:
- Handles None input (defaults to STANDARD with 0.4 confidence)
- Handles empty/whitespace input (defaults to STANDARD with 0.4 confidence)
- Truncates input >10000 chars with warning
- Combines feature description with GitHub issue (body weighted higher)

**Example**:
```python
assessor = ComplexityAssessor()
result = assessor.assess("Fix typo in README")
print(f"Level: {result.level}, Agents: {result.agent_count}")
# Output: Level: ComplexityLevel.SIMPLE, Agents: 3
```

#### `_analyze_keywords(text)` - Keyword-based classification

**Signature**: `@classmethod _analyze_keywords(text: str) -> Dict[str, Any]`

**Purpose**: Analyze text for SIMPLE and COMPLEX keyword indicators

**Parameters**: `text` (str): Text to analyze

**Returns**: Dict with 'simple_count', 'complex_count', 'simple_keywords', 'complex_keywords'

**Algorithm**:
- Case-insensitive substring matching for each keyword set
- Returns counts and matched keyword lists
- Fast O(n) algorithm where n = text length

#### `_analyze_scope(text)` - Scope detection analysis

**Signature**: `@classmethod _analyze_scope(text: str) -> Dict[str, Any]`

**Purpose**: Analyze text for scope indicators (file counts, conjunctions)

**Parameters**: `text` (str): Text to analyze

**Returns**: Dict with 'conjunction_count', 'file_type_count', 'word_count', 'alphabetic_count'

**Algorithm**:
- Count conjunctions: and, or, also, plus, additionally (regex-based)
- Count unique file types: .py, .js, .md, etc. (regex-based)
- Calculate word count and alphabetic word count
- Used as secondary indicator for scope breadth

#### `_analyze_security(text)` - Security indicator detection

**Signature**: `@classmethod _analyze_security(text: str) -> Dict[str, Any]`

**Purpose**: Analyze text for security-related indicators

**Parameters**: `text` (str): Text to analyze

**Returns**: Dict with 'has_security_keywords' and 'security_keyword_list'

**Security Keywords**: auth, authentication, authorization, security, encrypt, encryption, jwt, oauth, oauth2, saml, password, credential, token

#### `_determine_level(indicators)` - Complexity level determination

**Signature**: `@classmethod _determine_level(indicators: Dict) -> ComplexityLevel`

**Purpose**: Determine complexity level from indicators

**Priority**:
1. COMPLEX keywords override SIMPLE keywords (security-first approach)
2. SIMPLE keywords with no conflicts
3. STANDARD as default fallback

**Algorithm**:
- If complex_count > 0: return COMPLEX
- Else if simple_count > 0: return SIMPLE
- Else: return STANDARD

#### `_calculate_confidence(indicators)` - Confidence scoring

**Signature**: `@classmethod _calculate_confidence(indicators: Dict) -> float`

**Purpose**: Calculate confidence score (0.0-1.0) for assessment

**Confidence Factors**:
- Single keyword match: 0.85 base
- Multiple keyword matches: +0.05 per additional (max +0.10)
- Conflicting signals: -0.30 penalty
- No keywords but detailed: 0.6 (reasonable default to STANDARD)
- No keywords and vague/garbage: 0.4-0.5 (very ambiguous)

**Algorithm**:
```
If no keywords detected:
  If alphabetic_count == 0: confidence = 0.4 (garbage input)
  Elif word_count < 5: confidence = 0.5 (very ambiguous)
  Else: confidence = 0.6 (detailed request)
Else:
  confidence = 0.85 (base for any keyword match)
  If total_keywords >= 2: confidence += 0.05
  If total_keywords >= 3: confidence += 0.05
  If simple_count > 0 AND complex_count > 0: confidence -= 0.30
  Clamp confidence to [0.0, 1.0]
```

#### `_generate_reasoning(level, indicators, confidence)` - Reasoning generation

**Signature**: `@classmethod _generate_reasoning(level, indicators, confidence) -> str`

**Purpose**: Generate human-readable reasoning for assessment

**Output Format**: "Classified as LEVEL - [keyword details] - confidence level - [conflicts]"

**Example**: "Classified as COMPLEX - detected COMPLEX keywords: auth, encryption, jwt - high confidence - (conflicting signals detected, COMPLEX takes priority)"

### Test Coverage

**Unit Tests** (52 tests in tests/unit/lib/test_complexity_assessor.py):
- Simple typo/documentation classification
- Standard feature/bug fix classification
- Complex authentication/security/API classification
- Conflicting signal handling (SIMPLE + COMPLEX)
- Edge cases (empty input, None, whitespace-only)
- GitHub issue integration (title + body weighting)
- Confidence scoring accuracy
- Agent count and time mapping
- Low confidence scenarios
- Very long input truncation

**Coverage Target**: 95% of code paths, 100% of public API paths

### Files Added

- plugins/autonomous-dev/lib/complexity_assessor.py (441 lines)
- plugins/autonomous-dev/scripts/complexity_assessor.py (CLI wrapper, ~180 lines)
- tests/unit/lib/test_complexity_assessor.py (52 tests, ~500 lines)

### CLI Usage

```bash
# Simple text input
python complexity_assessor.py "Fix typo in README"

# From stdin
echo "Add OAuth2 support" | python complexity_assessor.py --stdin

# From GitHub issue
python complexity_assessor.py --issue 181

# JSON output
python complexity_assessor.py "Add JWT authentication" --json

# Verbose output
python complexity_assessor.py "Implement OAuth2" --verbose
```

### Integration Points

**Used By**:
- /auto-implement command (determine pipeline scaling)
- planner agent (estimate time and agent requirements)
- /create-issue command (estimate scope in issue creation)

**Dependencies**:
- None (standard library only: enum, typing, re, logging)

### Security Features

- Input validation for all user-provided text
- Graceful degradation for invalid inputs
- Max 10000 chars truncation with warning
- No external dependencies on network resources
- Thread-safe logging

### Performance

- Time complexity: O(n) where n = text length
- Space complexity: O(m) where m = number of keywords found
- Typical execution: < 5ms for standard feature descriptions

### GitHub

- Issue #181 - Automatic complexity assessment for pipeline scaling
- Related: Issue #180 (Smart pipeline scaling based on complexity)

### Related Documentation

- docs/PERFORMANCE.md - Pipeline performance metrics
- docs/LIBRARIES.md Section 1 (security_utils.py) - Input validation patterns

---

## 64. pause_controller.py (403 lines, v1.0.0 - Issue #182)

**Purpose**: File-based pause controls and human input handling for autonomous workflows

**Problem**: Long-running autonomous workflows need to pause at checkpoints to accept human feedback, approvals, or instructions without losing state.

**Solution**: Comprehensive pause/resume system with file-based signaling, checkpoint persistence, and secure file operations.

### Key Files

- `.claude/PAUSE` - Touch file to signal pause request
- `.claude/HUMAN_INPUT.md` - Optional file with human instructions/feedback
- `.claude/pause_checkpoint.json` - Checkpoint state for resume

### Functions

#### `check_pause_requested()` -> bool

**Purpose**: Check if pause is requested via .claude/PAUSE file

**Returns**: True if PAUSE file exists and is valid, False otherwise

**Security**:
- Rejects symlinks (CWE-59)
- Returns False if .claude dir doesn't exist
- Path traversal prevention

#### `read_human_input()` -> Optional[str]

**Purpose**: Read content from .claude/HUMAN_INPUT.md file

**Returns**: File content as string, or None if file doesn't exist

**Security**:
- Rejects symlinks (CWE-59)
- 1MB file size limit (DoS prevention)
- Handles unicode properly
- Returns None on permission errors
- Path traversal prevention

**Features**:
- Graceful handling of missing files
- Automatic encoding detection
- Safe error recovery

#### `clear_pause_state()` -> None

**Purpose**: Remove PAUSE and HUMAN_INPUT.md files to resume workflow

**Behavior**:
- Idempotent (no error if files don't exist)
- Preserves checkpoint file (separate lifecycle)
- Removes both signal files

**Security**:
- Validates paths before deletion
- Only removes PAUSE and HUMAN_INPUT.md
- Never follows symlinks

#### `save_checkpoint(agent_name, state)` -> None

**Purpose**: Save checkpoint state to .claude/pause_checkpoint.json for resume

**Parameters**:
- `agent_name` (str): Name of agent saving checkpoint
- `state` (Dict[str, Any]): State dictionary to save

**Security**:
- Atomic write (write to temp file, then rename)
- Input validation for agent_name
- Path validation before write
- Atomic rename prevents partial writes

**Checkpoint Structure**:
```json
{
  "agent": "agent_name",
  "timestamp": "2026-01-02T12:34:56.123456+00:00",
  "step": 3,
  "data": "..."
}
```

#### `load_checkpoint()` -> Optional[Dict[str, Any]]

**Purpose**: Load checkpoint from .claude/pause_checkpoint.json

**Returns**: Checkpoint data as dictionary, or None if:
- File doesn't exist
- JSON is invalid
- File is empty
- Permission denied

**Security**:
- Validates path before reading
- Handles corrupted JSON gracefully
- Rejects invalid file formats
- Returns None for errors (graceful degradation)

#### `validate_pause_path(path)` -> bool

**Purpose**: Validate path for pause-related file operations

**Parameters**: `path` (str): Path to validate

**Returns**: True if path is valid and safe, False otherwise

**Security Validations**:
- CWE-22: Reject path traversal attempts (..)
- CWE-59: Reject symlinks
- Ensure path is within .claude/ directory
- Block null bytes (CWE-158)

### Workflow Integration

**Typical Workflow**:
1. User creates `.claude/PAUSE` file to pause at next checkpoint
2. Optionally: User writes `.claude/HUMAN_INPUT.md` with instructions
3. Workflow checks `check_pause_requested()` at checkpoints
4. If paused: saves state with `save_checkpoint()`
5. Workflow reads instructions with `read_human_input()`
6. User provides feedback/approval
7. User removes `.claude/PAUSE` to signal resume
8. Workflow loads state with `load_checkpoint()` and continues

### Security Features

- **Path Traversal Prevention (CWE-22)**: Strict validation that all paths are within `.claude/` directory
- **Symlink Attack Prevention (CWE-59)**: All file checks detect and reject symlinks
- **Null Byte Injection (CWE-158)**: Blocks null bytes in paths
- **DoS Prevention**: 1MB file size limit on human input
- **Atomic Operations**: Checkpoint writes use temp file + rename for atomicity
- **Graceful Degradation**: All errors return safe defaults (None/False) instead of exceptions

### Test Coverage

- 44 unit tests for all functions
- 24 integration tests for workflow scenarios
- Security tests for path traversal, symlinks, null bytes
- Edge case tests for missing files, permissions, corrupted JSON

### Related

- GitHub Issue #182 - Pause controls with PAUSE file and HUMAN_INPUT.md
- state-management-patterns skill - Checkpoint patterns
- security_utils.py (Section 1) - Common path validation approach

### Documentation

- **API**: This section (LIBRARIES.md Section 64)
- **Workflow**: See HUMAN_INPUT.md for user-facing pause workflow
- **Source**: plugins/autonomous-dev/lib/pause_controller.py (403 lines)


## 65. worktree_command.py (506 lines, v1.0.0 - Issue #180)

**Purpose**: Interactive CLI interface for git worktree management

**Problem**: After features are developed in isolated worktrees, users need a way to review changes, merge to target branch, or discard work safely - all from the command line

**Solution**: Complete CLI with 5 modes (list, status, review, merge, discard) providing full worktree lifecycle management

### Key Features

- **Multi-mode interface**: List, status, review, merge, discard modes
- **Safe operations**: Destructive operations require explicit user approval
- **Formatted output**: Status indicators (clean, dirty, active, stale, detached)
- **Interactive review**: Shows diff and prompts for merge approval
- **Exit codes**: Standard codes (0=success, 1=warning, 2=user reject)

### Modes

#### List Mode (`--list` - DEFAULT)

Shows all active worktrees with status indicators.

**Usage**:
```bash
/worktree                # Default list mode
/worktree --list         # Explicit list mode
```

**Output**:
```
Feature              Branch                         Status
------------------------------------------------------------
feature-auth         feature/feature-auth           clean
feature-logging      feature/feature-logging        dirty
```

**Status Indicators**:
- `clean` - No uncommitted changes
- `dirty` - Has uncommitted changes
- `active` - Currently checked out
- `stale` - Directory missing (orphaned)
- `detached` - Detached HEAD state

#### Status Mode (`--status FEATURE`)

Detailed information for a specific worktree.

**Usage**:
```bash
/worktree --status feature-auth
```

**Output**:
```
Worktree Status: feature-auth
Path:            /project/.worktrees/feature-auth
Branch:          feature/feature-auth
Status:          dirty
Target Branch:   master
Commits Ahead:   5
Commits Behind:  2

Uncommitted Changes (3 files):
  - auth/models.py
  - auth/tests.py
  - README.md
```

**Fields**:
- Path: Full path to worktree directory
- Branch: Current branch name
- Status: clean/dirty/active/stale/detached
- Target Branch: Where commits will be merged
- Commits Ahead/Behind: Against target branch
- Uncommitted Changes: List of modified files

#### Review Mode (`--review FEATURE`)

Interactive diff review with approve/reject workflow.

**Usage**:
```bash
/worktree --review feature-auth
```

**Workflow**:
1. Shows full git diff against target branch
2. Prompts: "Approve or reject changes? [approve/reject]:"
3. If approve: Automatically merges to target branch
4. If reject: Exits without merging

**Output**:
```
Diff for worktree: feature-auth
============================================================
diff --git a/auth/models.py b/auth/models.py
[... full diff output ...]
============================================================

Approve or reject changes? [approve/reject]: approve

Successfully merged 12 files
```

#### Merge Mode (`--merge FEATURE`)

Directly merge worktree to target branch without review.

**Usage**:
```bash
/worktree --merge feature-auth
```

**Behavior**:
- Merges worktree branch to target branch
- Handles merge conflicts (reports and exits with code 1)
- Non-interactive (no approval prompt)

#### Discard Mode (`--discard FEATURE`)

Delete worktree with confirmation.

**Usage**:
```bash
/worktree --discard feature-auth
```

**Behavior**:
- Prompts for confirmation: "Delete worktree feature-auth? [y/N]:"
- If yes: Deletes worktree directory and git worktree entry
- If no: Exits without deleting
- Prevents accidental deletion of uncommitted work

### Implementation Details

**Design Pattern**: Wrapper CLI around worktree_manager.py library

**Architecture**:
- Parse arguments using argparse
- Delegate operations to worktree_manager.py functions
- Handle user interactions (prompts, confirmation)
- Format and display results
- Return appropriate exit codes

**User Prompts**:
- Review mode: Shows diff, prompts approve/reject
- Discard mode: Prompts for confirmation
- Review/merge prompts use Task tool for interactive input

**Error Handling**:
- Clear error messages for failed operations
- Non-blocking graceful degradation (non-git directories)
- Exit codes signal success/warning/user rejection

**Integration**:
- Designed to work with /auto-implement worktree output
- Part of feature review and merge workflow
- Can be used standalone for worktree management

### API Functions

#### `main(args: List[str]) -> int`

**Purpose**: Main entry point for CLI

**Parameters**:
- `args` (List[str]): Command-line arguments (excluding program name)

**Returns**: Exit code (0=success, 1=warning, 2=user reject)

**Modes Dispatched**:
- Empty or `--list` -> list_mode()
- `--status NAME` -> status_mode(NAME)
- `--review NAME` -> review_mode(NAME)
- `--merge NAME` -> merge_mode(NAME)
- `--discard NAME` -> discard_mode(NAME)

#### `list_mode() -> int`

Lists all active worktrees with formatted output.

**Returns**: 0 (always succeeds, even if no worktrees)

#### `status_mode(feature: str) -> int`

Shows detailed status for a worktree.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=success, 1=worktree not found

#### `review_mode(feature: str) -> int`

Interactive diff review and merge.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=merged, 1=merge failed, 2=user rejected

#### `merge_mode(feature: str) -> int`

Direct merge without review.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=success, 1=merge failed

#### `discard_mode(feature: str) -> int`

Delete worktree with confirmation.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=deleted, 1=error, 2=user cancelled

### Data Structures

#### `ParsedArgs` (dataclass)

Parsed command-line arguments.

**Fields**:
- `mode` (str): Operation mode (list, status, review, merge, discard)
- `feature` (Optional[str]): Feature name (None for list mode)

### Security

**Path Validation**:
- Validates worktree paths (CWE-22 path traversal prevention)
- Prevents directory traversal via feature names
- Rejects symlinks and suspicious paths

**Command Injection Prevention** (CWE-78):
- Feature names sanitized before shell commands
- Uses subprocess with list arguments (not shell=True)
- No user input passed directly to shell

**No File Writes**:
- Only reads git state and worktree metadata
- All modifications delegated to worktree_manager.py
- No file creation in user directories

### Test Coverage

**40 unit tests** covering:
- All 5 modes (list, status, review, merge, discard)
- Argument parsing (valid/invalid args)
- Output formatting
- User prompt handling
- Error conditions (missing worktrees, permission errors)
- Edge cases (empty list, special characters in names)

**Files**:
- tests/unit/test_worktree_command.py (40 tests)

### Performance

- List: 50-100ms (git worktree list)
- Status: 100-500ms (git log, git status for one worktree)
- Review: 0.5-5s (git diff, merge operations)
- Merge: 0.5-5s (git merge operation)
- Discard: 1-2s (worktree cleanup)

### Related

- GitHub Issue #180 - /worktree command for git worktree management
- worktree_manager.py (Section 61) - Core library for operations
- git-operations skill - Git integration patterns
- cli-design-patterns skill - CLI argument handling patterns

### Documentation

- **API**: This section (LIBRARIES.md Section 65)
- **Command**: plugins/autonomous-dev/commands/worktree.md (590 lines)
  - Quick start examples
  - Use case descriptions
  - Detailed mode reference
- **Source**: plugins/autonomous-dev/lib/worktree_command.py (506 lines)

## 66. sandbox_enforcer.py (625 lines, v1.0.0 - Issue #171)

**Purpose**: Command classification and OS-specific sandboxing to reduce permission prompts by 84%

**Location**: `plugins/autonomous-dev/lib/sandbox_enforcer.py`

**Version**: 1.0.0 (2026-01-02, Issue #171 - Sandboxing for reduced permission prompts)

### Overview

SandboxEnforcer provides command classification (SAFE/BLOCKED/NEEDS_APPROVAL) and OS-specific sandboxing to eliminate repetitive permission prompts for safe operations.

**Problem It Solves**:
- Users approve 50+ permission prompts per /auto-implement workflow
- 80%+ are for safe read-only commands (cat, ls, grep, git status)
- Each prompt breaks focus and adds 10-20 seconds overhead
- SandboxEnforcer reduces prompts from 50+ to roughly 8-10 (84% reduction)

**Solution**:
- Whitelist-first approach: Safe commands auto-approve without prompts
- Blocked patterns: Dangerous commands denied with audit logging
- OS-specific sandboxing: bwrap (Linux), sandbox-exec (macOS), none (Windows)
- Circuit breaker: Disables after threshold blocks (safety mechanism)

### Architecture

**4-Layer Integration**:
1. **Layer 0 (Sandbox)**: SAFE to auto-approve, BLOCKED to deny, NEEDS_APPROVAL to continue
2. **Layer 1 (MCP Security)**: Path traversal, injection, SSRF validation
3. **Layer 2 (Agent Auth)**: Pipeline agent detection
4. **Layer 3 (Batch Permission)**: Permission batching

**Integrated into**: `unified_pre_tool.py` hook (PreToolUse lifecycle)

**Environment Variables**:
- `SANDBOX_ENABLED` (bool, default: false) - Enable/disable sandbox layer
- `SANDBOX_PROFILE` (str, default: development) - Security profile (development/testing/production)

### Classes

#### `CommandClassification` (Enum)

Command classification results:

```
class CommandClassification(Enum):
    SAFE = "safe"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"
```

#### `SandboxBinary` (Enum)

OS-specific sandbox binaries:

```
class SandboxBinary(Enum):
    BWRAP = "bwrap"
    SANDBOX_EXEC = "sandbox-exec"
    NONE = "none"
```

#### `CommandResult` (Dataclass)

Result of command classification:

```
@dataclass
class CommandResult:
    classification: CommandClassification
    reason: Optional[str] = None
    can_sandbox: bool = False
```

#### `SandboxEnforcer` (Main Class)

Command classifier and sandbox manager.

**Constructor**:
```
SandboxEnforcer(policy_path: Optional[str|Path] = None, profile: str = "development")
```

**Parameters**:
- `policy_path` (optional): Custom policy file (defaults to plugin policy.json)
- `profile` (str): Security profile - "development" (permissive), "testing" (moderate), "production" (strict)

**Key Methods**:

##### `is_command_safe(command: str) -> CommandResult`
Classify a command and determine permission decision.

**Parameters**: `command` (str) - Full command string

**Returns**: `CommandResult` with classification and reason

**Logic**:
1. Check circuit breaker (return BLOCKED if tripped)
2. Check if command is in safe_commands list (return SAFE)
3. Check for blocked patterns (return BLOCKED)
4. Check for shell injection patterns (return BLOCKED)
5. Check for path traversal (return BLOCKED)
6. Check for blocked file paths (return BLOCKED)
7. Return NEEDS_APPROVAL (continue to Layer 1)

**Example**:
```
enforcer = SandboxEnforcer()

result = enforcer.is_command_safe("cat README.md")
assert result.classification == CommandClassification.SAFE

result = enforcer.is_command_safe("rm command")
assert result.classification == CommandClassification.BLOCKED
```

##### `get_sandbox_binary() -> SandboxBinary`
Detect OS-specific sandbox binary availability.

**Returns**: SandboxBinary enum (BWRAP, SANDBOX_EXEC, or NONE)

**Behavior**:
- Linux: Check for `bwrap` (bubblewrap)
- macOS: Check for `sandbox-exec`
- Windows: Return NONE
- Fallback: Return NONE if binary not found

##### `build_sandbox_args(command: str) -> List[str]`
Build OS-specific sandbox arguments for command wrapping.

**Parameters**: `command` (str) - Original command

**Returns**: List[str] - Sandbox wrapper plus original command

**OS-Specific Behavior**:

Linux (bwrap): Wraps with tmpfs isolation and bind mounts

macOS (sandbox-exec): Wraps with operation deny policy

Windows (none): Returns original command as-is (no sandboxing)

### Validation Methods

#### `validate_policy(policy: Dict[str, Any]) -> bool`
Validate policy JSON schema.

**Checks**:
- Version field present
- Profiles dict present
- Each profile has required sections
- Security settings valid

**Raises**: `PolicyValidationError` if validation fails

### Security Features

**Shell Injection Detection** (CWE-78):
- Detects dangerous shell metacharacters
- Blocks commands with unsafe patterns
- Prevents command chaining and execution tricks

**Path Traversal Protection** (CWE-22):
- Detects pattern matching in commands
- Blocks access to sensitive files: .env, .ssh, credential files
- Validates all file paths in commands

**Circuit Breaker** (DoS Prevention):
- Trips after threshold blocks (configurable per profile)
- Automatically disables sandbox after repeated violations
- Prevents brute-force attempts to bypass sandbox

**Audit Logging**:
- Logs all decisions to security audit log
- Records command, classification, reason
- Thread-safe logging with file rotation

### Policy Profiles

**Profile: Development** (Most Permissive)

Safe commands: cat, echo, grep, ls, pwd, which, git status, git diff, pytest

Blocked patterns: rm command, sudo, git push variants, eval, wget patterns, curl patterns

Blocked paths: .env, .ssh/, credentials.json, key files, /etc/shadow

Circuit breaker: 10 blocks before tripping

**Profile: Testing** (Moderate)

Stricter than development with fewer safe commands and 5-block circuit breaker

**Profile: Production** (Strictest)

Minimal auto-approvals with 3-block circuit breaker

### Configuration

**Policy File Location**: `plugins/autonomous-dev/config/sandbox_policy.json`

**Custom Policy** (Project-Local Override):
Create `.claude/config/sandbox_policy.json` with custom profiles

### Integration with unified_pre_tool.py

**Layer 0 Decision Logic**:

Tool call received -> Extract command -> Classify with SandboxEnforcer -> Return decision

### Examples

**Example 1: Safe Read-Only Command**
```
result = enforcer.is_command_safe("grep pattern src/")
Classification: SAFE (grep is in safe_commands list)
Action: Auto-approve, skip permission prompt
```

**Example 2: Blocked Dangerous Pattern**
```
result = enforcer.is_command_safe("rm command /home/user")
Classification: BLOCKED (matches blocked pattern)
Action: Deny with audit log
```

**Example 3: Unknown Command**
```
result = enforcer.is_command_safe("custom-linter options")
Classification: NEEDS_APPROVAL (not in safe list, no blocked patterns)
Action: Continue to Layer 1 (MCP Security validation)
```

**Example 4: Sandboxing on Linux**
```
binary = enforcer.get_sandbox_binary()
if binary == SandboxBinary.BWRAP:
    sandbox_args = enforcer.build_sandbox_args("cat file.txt")
    # Execute with subprocess
```

### Test Coverage

**50+ unit tests** covering:
- Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
- Safe command patterns
- Blocked patterns
- Injection detection
- Path traversal detection
- Blocked file patterns
- Sandbox binary detection
- Policy loading and validation
- Circuit breaker logic
- Cross-platform behavior
- Edge cases

**Files**:
- tests/unit/lib/test_sandbox_enforcer.py (50+ tests)

### Performance

- Command classification: less than 1ms (pattern matching)
- Sandbox binary detection: 5-50ms (first run, cached after)
- Policy loading: 10-20ms (per process startup)
- Circuit breaker check: less than 1ms (in-memory state)

**Optimization Notes**:
- Compiled regex patterns for performance
- Cached binary detection
- No filesystem I/O during classification

### Security Considerations

**What It Protects**:
- Command injection via shell metacharacters
- Path traversal attacks
- Sensitive data exposure via blocked file patterns
- DoS via brute-force bypass attempts

**What It Doesn't Protect**:
- Vulnerabilities in whitelisted commands
- Logic bugs in policy rules
- Malicious code execution
- Privilege escalation beyond blocked patterns

### Related

- GitHub Issue #171 - Sandboxing for reduced permission prompts
- unified_pre_tool.py (HOOKS.md) - Hook integration (Layer 0)
- MCP-SECURITY.md - Overall security architecture
- sandbox_policy.json - Policy configuration file

### Documentation

- **API**: This section (LIBRARIES.md Section 66)
- **User Guide**: docs/SANDBOXING.md (comprehensive user documentation)
- **Hook Integration**: docs/HOOKS.md (unified_pre_tool.py Layer 0)
- **Source**: plugins/autonomous-dev/lib/sandbox_enforcer.py (625 lines)
- **Config**: plugins/autonomous-dev/config/sandbox_policy.json
- **Tests**: tests/unit/lib/test_sandbox_enforcer.py


## 67. status_tracker.py (335 lines, v3.48.0+ - Issue #174)

**Purpose**: Test status tracking for pre-commit gate hook enforcement

**Module**: plugins/autonomous-dev/lib/status_tracker.py

**Problem**: Pre-commit hooks need to know if tests passed before allowing commits. A simple, reliable mechanism is needed for test runners to communicate test status to the commit hook.

**Solution**: Atomic file-based test status tracking with secure permissions and graceful degradation.

**Key Features**:
- **Atomic writes**: Write to temp file, then rename (prevents corruption if process crashes)
- **Secure storage**: /tmp/.autonomous-dev/test-status.json with 0600 file permissions and 0700 directory permissions
- **Graceful degradation**: All I/O errors return safe defaults (assume tests failed)
- **Safe defaults**: read_status() returns {"passed": False} if file missing/corrupted
- **Temporary storage**: Ephemeral in /tmp (cleared on system reboot)
- **Comprehensive validation**: JSON structure validation, type checking, timestamp validation

**API Reference**:

```python
from status_tracker import write_status, read_status, clear_status, get_status_file_path

# After test run completes
write_status(passed=True, details={"total": 100, "failed": 0})
# Returns: bool (True if write succeeded, False if failed)

# In pre-commit hook
status = read_status()
# Returns: Dict with at least {"passed": bool, "timestamp": str or None}
# Safe default on any error: {"passed": False, "timestamp": None}

if status.get("passed"):
    # Allow commit
    pass
else:
    # Block commit
    pass

# Clear status (optional)
clear_status()  # Returns: bool

# Get status file path
path = get_status_file_path()
# Returns: Path object (PosixPath on Unix, WindowsPath on Windows)
```

**Security Features**:
- **CWE-22 Prevention**: Hardcoded /tmp path (no user input, no traversal risk)
- **Atomic operations**: Rename is atomic at filesystem level (prevents race conditions)
- **Restricted permissions**: 0600 on files, 0700 on directory (owner read/write only)
- **Safe defaults**: Any I/O error returns safe "tests failed" default
- **JSON validation**: Validates parsed JSON structure before returning

**Main Functions**:

1. **write_status(passed, details=None) -> bool**
   - Write test status to /tmp/.autonomous-dev/test-status.json
   - Args: passed (bool), details (optional dict with additional data)
   - Returns: True if write succeeded, False if failed
   - Creates directory with 0700 permissions if missing
   - Sets file permissions to 0600 after write
   - Graceful degradation: Returns False on any error (doesn't raise)

2. **read_status() -> Dict[str, Any]**
   - Read test status from file
   - Returns: Dictionary with at least {"passed": bool, "timestamp": str or None}
   - Safe default: {"passed": False, "timestamp": None} on any error
   - Validates JSON structure and field types before returning
   - Graceful degradation: Returns safe default on missing file, parse errors, etc.

3. **clear_status() -> bool**
   - Delete the status file
   - Returns: True if deleted or didn't exist, False if deletion failed
   - Graceful degradation: Returns False on permission errors

4. **get_status_file_path() -> Path**
   - Get path to status file
   - Returns: pathlib.Path object
   - No I/O operations (just returns constant path)

5. **_ensure_status_dir() -> bool** (internal)
   - Ensure /tmp/.autonomous-dev/ exists with 0700 permissions
   - Returns: True if directory exists/was created, False if failed
   - Validates and fixes permissions if directory already existed

**Design Patterns**:
- **Graceful degradation**: All functions return safe defaults on errors, never raise
- **Atomic writes**: Uses temp file + rename pattern for data integrity
- **Safe defaults**: Assume tests failed if anything goes wrong
- **No user input**: Hardcoded paths prevent all traversal attacks

**Error Handling**:
- OSError, PermissionError: Caught and return False (graceful degradation)
- IOError, json.JSONDecodeError: Caught and return safe defaults
- Missing file: Treated as {"passed": False} (safe default)
- Corrupted JSON: Treated as {"passed": False} (safe default)
- Invalid field types: Cleaned up and returned with safe values

**Performance**:
- write_status(): ~2-5ms (file I/O)
- read_status(): ~1-3ms (file I/O + JSON parsing)
- clear_status(): ~1-2ms (file deletion)
- get_status_file_path(): <0.1ms (no I/O)

**Usage Examples**:

```python
# Test runner integration
import subprocess
from status_tracker import write_status

result = subprocess.run(['pytest', 'tests/'], capture_output=True)
write_status(
    passed=(result.returncode == 0),
    details={
        "total": 100,
        "failed": 0 if result.returncode == 0 else 5,
        "duration": 12.3
    }
)

# Pre-commit hook integration
from status_tracker import read_status

status = read_status()
if not status.get("passed"):
    print("Tests failed - commit blocked")
    print(f"Details: {status}")
    exit(1)  # Block commit
```

**Integration**:
- Used by: pre_commit_gate.py hook (blocks commits if tests failed)
- Called by: Test runners after test execution (write status)
- Non-blocking: Library itself has no side effects, hook decides action

**Security Audit**:
- Path validation: Hardcoded path only, no user input
- File permissions: 0600 (owner RW), 0700 (directory owner RWX)
- No symlink following: Verified no symlink traversal
- No subprocess calls: Pure Python file I/O
- No network access: File-local only
- No credential exposure: No passwords or tokens in status file

**Test Coverage**:
- Write operations: File creation, permission setting, temp file cleanup
- Read operations: Missing file, corrupted JSON, invalid field types
- Edge cases: Race conditions (atomic rename), permission errors, disk full
- Security: Path traversal attempts, symlink attacks, permission escalation
- Integration: Hook usage patterns, test runner integration

**Related Documentation**:
- docs/LIBRARIES.md - This section (67)
- docs/HOOKS.md - pre_commit_gate section (uses status_tracker)
- plugins/autonomous-dev/hooks/pre_commit_gate.py - Hook implementation
- Issue #174 - Block-at-submit hook for test passage enforcement

**Testing**:
```bash
# Self-test (included in module)
python plugins/autonomous-dev/lib/status_tracker.py

# Integrated tests
pytest tests/unit/lib/test_status_tracker.py
```

**Backward Compatibility**: N/A (new library)

**Version History**:
- v1.0.0 (2026-01-02) - Initial release with atomic writes, secure permissions, graceful degradation


---

## 68. headless_mode.py (263 lines, v1.0.0 - Issue #176)

**Purpose**: CI/CD integration support for headless/non-interactive environments

**GitHub Issue**: #176 - Headless mode for CI/CD integration

### Functions

#### `detect_headless_flag() -> bool`
- **Purpose**: Detect if --headless flag is present in sys.argv
- **Parameters**: None
- **Returns**: bool - True if --headless flag is present (case-sensitive, exact match)
- **Features**:
  - Case-sensitive matching (--Headless returns False)
  - Exact match only (--headless-verbose would not match)
  - No argument parsing required (simple membership check)

#### `detect_ci_environment() -> bool`
- **Purpose**: Detect if running in a CI/CD environment
- **Parameters**: None
- **Returns**: bool - True if any CI environment variable is detected
- **Features**:
  - Checks common CI environment variables (case-insensitive values):
    - CI=true, CI=1
    - GITHUB_ACTIONS=true, GITHUB_ACTIONS=1
    - GITLAB_CI=true, GITLAB_CI=1
    - CIRCLECI=true, CIRCLECI=1
    - TRAVIS=true, TRAVIS=1
  - JENKINS_HOME: Any non-empty value (typically /var/jenkins_home)
- **Supported CI Systems**:
  - GitHub Actions
  - GitLab CI/CD
  - CircleCI
  - Travis CI
  - Jenkins
  - Any CI that sets CI=true standard

#### `is_headless_mode() -> bool`
- **Purpose**: Determine if running in headless mode (combined detection)
- **Parameters**: None
- **Returns**: bool - True if headless mode is active
- **Detection Logic** (in priority order):
  1. Explicit --headless flag present -> Return True
  2. CI environment AND not TTY -> Return True
  3. Not TTY (stdin not a terminal) -> Return True
  4. Otherwise -> Return False
- **Features**:
  - TTY detection via sys.stdin.isatty()
  - Combines flag-based and environment-based detection
  - Detects CI environments without explicit flag
  - Detects piped input (not TTY)

#### `should_skip_prompts() -> bool`
- **Purpose**: Determine if interactive prompts should be skipped
- **Parameters**: None
- **Returns**: bool - True if prompts should be skipped (alias for is_headless_mode())
- **Usage**: Call this in interactive workflows to decide whether to prompt

#### `format_json_output(status, data, error) -> str`
- **Purpose**: Format output as JSON for machine parsing
- **Parameters**:
  - status (str): Status string ("success" or "error")
  - data (Optional[Dict[str, Any]]): Optional data dictionary to include
  - error (Optional[str]): Optional error message (only for error status)
- **Returns**: str - JSON-formatted string with no trailing newline
- **Output Format**:
  - Success: {"status": "success", ... additional data fields ...}
  - Error: {"status": "error", "error": "error message"}
- **Features**:
  - Merges data fields directly into output dict (flattens structure)
  - Includes error message when present
  - Compact JSON output (no pretty-printing)
  - Machine-readable for CI/CD pipelines

#### `get_exit_code(status, error_type) -> int`
- **Purpose**: Map status/error_type to exit code for CI/CD pipelines
- **Parameters**:
  - status (str): Status string ("success" or "error")
  - error_type (Optional[str]): Optional error type for specific exit codes
- **Returns**: int - Exit code (0-5)
- **Exit Code Mapping**:
  - 0: success (status == "success")
  - 1: generic error (status == "error", no error_type or unknown type)
  - 2: alignment_failed (error_type == "alignment_failed")
  - 3: tests_failed (error_type == "tests_failed")
  - 4: security_failed (error_type == "security_failed")
  - 5: timeout (error_type == "timeout")
- **Features**:
  - Semantic exit codes for CI/CD integration
  - Graceful fallback to 1 for unknown error types
  - Type-safe mapping (uses dict.get with default)

#### `configure_auto_git_for_headless() -> Dict[str, str]`
- **Purpose**: Configure AUTO_GIT environment variables for headless mode
- **Parameters**: None
- **Returns**: dict - Dictionary of configured values with keys: AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR
- **Features**:
  - Sets environment variables if not already set (respects existing configuration)
  - AUTO_GIT_ENABLED: "true" (enables git automation)
  - AUTO_GIT_PUSH: "true" (automatically pushes commits)
  - AUTO_GIT_PR: "false" (no auto-PR in CI, requires manual review)
  - Non-destructive: Does NOT override existing values
  - Returns dict of actual values (configured or existing)

### Design Patterns

- **Progressive Detection**: Flag -> CI environment -> TTY checks (most to least specific)
- **Non-blocking Enhancement**: Headless mode detection never fails, always returns safe defaults
- **Environment-aware**: Respects existing configuration, doesn't override user choices
- **Machine-friendly Output**: JSON format for CI/CD integration, standardized exit codes

### Security Considerations

- No external dependencies (uses only stdlib: os, sys, json)
- No file I/O operations (stateless detection)
- No subprocess calls (pure Python detection)
- No credential exposure (no environment variable logging)
- Case-insensitive CI environment detection (handles variations)
- Exit codes match POSIX conventions (0 = success, 1+ = error variants)

### Error Handling

- All functions return safe defaults (bool or dict) on any error
- No exceptions raised (graceful degradation)
- Missing environment variables treated as False
- Invalid status/error_type strings handled safely (default to generic error code 1)

### Performance

- detect_headless_flag(): less than 0.1ms (list membership check)
- detect_ci_environment(): less than 0.5ms (environment variable lookups)
- is_headless_mode(): less than 1ms (combined detection with TTY check)
- should_skip_prompts(): less than 1ms (calls is_headless_mode())
- format_json_output(): less than 1ms (JSON serialization)
- get_exit_code(): less than 0.1ms (dict lookup)
- configure_auto_git_for_headless(): less than 1ms (environment variable writes)

### Integration Patterns

**Pattern 1: Skip Interactive Prompts in Headless**
```python
from headless_mode import should_skip_prompts

if should_skip_prompts():
    response = "yes"
else:
    response = input("Continue? (yes/no): ")
```

**Pattern 2: JSON Output for CI/CD**
```python
from headless_mode import is_headless_mode, format_json_output

try:
    result = perform_workflow()
    output = format_json_output("success", {"feature": result})
except Exception as e:
    output = format_json_output("error", error=str(e))

if is_headless_mode():
    print(output)
else:
    print("Workflow completed successfully")
```

**Pattern 3: Exit Codes for CI/CD Integration**
```python
from headless_mode import get_exit_code, format_json_output

try:
    result = run_tests()
    if result.passed:
        output = format_json_output("success", {"tests": result.count})
        exit(get_exit_code("success"))
    else:
        output = format_json_output("error", error="Tests failed")
        exit(get_exit_code("error", "tests_failed"))
except TimeoutError:
    output = format_json_output("error", error="Timeout")
    exit(get_exit_code("error", "timeout"))
```

**Pattern 4: Auto-configure Git for Headless**
```python
from headless_mode import is_headless_mode, configure_auto_git_for_headless

if is_headless_mode():
    config = configure_auto_git_for_headless()
```

### Related Libraries

- auto_implement_git_integration.py - Uses AUTO_GIT env vars configured by headless_mode
- status_tracker.py - Provides test status for exit code determination
- hook_exit_codes.py - Standardized exit code constants

### Used By

- /auto-implement command (respects headless mode, skips prompts)
- /batch-implement command (uses headless detection for mode selection)
- GitHub Actions and other CI/CD systems
- Docker containers (non-TTY environments)
- Headless servers and API backends

### Test Coverage

- Environment detection tests (CI vars, TTY checks, flag parsing)
- Exit code mapping tests (all status/error_type combinations)
- JSON output formatting tests (success, error, merged data)
- Integration tests (headless workflows with auto-git configuration)
- Edge cases: Missing env vars, invalid JSON data, type mismatches

### Version History

- v1.0.0 (2026-01-02) - Initial release with CI/CD detection, JSON output, exit codes, and auto-git configuration

### Backward Compatibility

N/A (new library - Issue #176)

---

## 69. conflict_resolver.py (1016 lines, v1.0.0 - Issue #183)

**AI-powered merge conflict resolution with three-tier escalation strategy**

### Purpose

Resolve git merge conflicts intelligently using Claude API. Handles conflicts from simple (whitespace) to complex (multi-conflict semantic issues) with automatic tier escalation.

### Problem

Merge conflicts interrupt development workflows. Manual resolution requires understanding code context, intent, and impact. Simple conflicts are tedious to resolve manually. Complex conflicts need semantic understanding.

### Solution

Three-tier escalation strategy balances automation with accuracy:

1. **Tier 1 (Auto-Merge)**: Trivial conflicts resolved without AI
   - Whitespace-only differences
   - Identical changes on both sides
   - Instant resolution, zero API cost

2. **Tier 2 (Conflict-Only)**: AI analyzes only conflict blocks
   - Focuses on semantic understanding of changes
   - Faster than full-file analysis
   - Suitable for most real conflicts

3. **Tier 3 (Full-File)**: Comprehensive context analysis
   - Reads entire file for maximum context
   - Handles complex multi-conflict scenarios
   - Chunks large files to respect API limits (100KB per chunk)

### Key Classes

**ConflictBlock**
- Represents a single merge conflict
- Tracks: file_path, start_line, end_line, their_changes, our_changes, base_version
- Extracts conflict range for targeted analysis

**ResolutionSuggestion**
- Recommended resolution with metadata
- Fields: file_path, start_line, end_line, resolved_content, confidence (0.0-1.0), reasoning, tier_used
- Applied atomically to file with backup

**ConflictResolutionResult**
- Final result of resolution attempt
- Fields: success (bool), resolution (optional ResolutionSuggestion), error_message, conflict_count, resolved_count

### Key Functions

**parse_conflict_markers(file_path)**
- Parses git conflict markers (<<<<<<<, =======, >>>>>>>)
- Returns: List[ConflictBlock] with all conflicts found
- Validates file path (CWE-22, CWE-59 prevention)

**resolve_tier1_auto_merge(conflict: ConflictBlock)**
- Detects and resolves trivial conflicts
- Whitespace normalization
- Identical side detection
- Returns: Optional[ResolutionSuggestion] (None if needs escalation)

**resolve_tier2_conflict_only(conflict: ConflictBlock, api_key: str)**
- AI analysis of conflict block only
- Prompt: 200-300 tokens (conflict + reasoning request)
- Returns: ResolutionSuggestion with confidence scoring
- Suitable for 90% of conflicts

**resolve_tier3_full_file(file_path: str, conflicts: List[ConflictBlock], api_key: str)**
- AI analysis with entire file context
- Chunks large files (>100KB)
- Processes chunks sequentially with context preservation
- Returns: ConflictResolutionResult with all resolutions

**apply_resolution(file_path: str, resolution: ResolutionSuggestion)**
- Applies resolution to file
- Atomic operations: backup -> update -> verify
- Returns: bool (success/failure)
- Verifies conflict markers removed

**resolve_conflicts(file_path: str, api_key: str)**
- Main entry point with automatic tier escalation
- Implements escalation logic: Tier 1 -> Tier 2 -> Tier 3
- Returns: ConflictResolutionResult
- Handles all errors gracefully

### Three-Tier Strategy

**Why Escalation?**
- Tier 1 (instant) handles common cases
- Tier 2 (fast) handles most conflicts without full context
- Tier 3 (comprehensive) available for complex scenarios
- Reduces API cost while maintaining quality

**When to Use Each Tier**

| Scenario | Tier | Reason |
|----------|------|--------|
| Whitespace only | 1 | Instant, no AI needed |
| Identical changes | 1 | Deterministic resolution |
| Simple semantic conflict | 2 | Context from conflict block sufficient |
| Multiple conflicts | 2 | Tier 2 handles multiple blocks |
| Cross-cutting changes | 3 | Needs full file context |
| Complex refactoring | 3 | Semantic understanding requires file knowledge |

**Tier 2 vs Tier 3 Performance**
- Tier 2: ~3-5 seconds per conflict (200 tokens)
- Tier 3: ~5-10 seconds per file (500-1000 tokens depending on file size)
- Cost: Tier 2 ~100x cheaper than Tier 3

### Security Features

**Path Validation (CWE-22, CWE-59)**
- validate_path() checks for path traversal
- Symlink detection and rejection
- Absolute path normalization
- User project scope validation

**Log Injection Sanitization (CWE-117)**
- Sanitize conflict markers before logging
- Remove control characters and newlines
- Never log API keys or sensitive data

**API Key Protection**
- Never logged or printed
- Passed only to anthropic.Anthropic client
- Removed from error messages
- Used via environment variable (ANTHROPIC_API_KEY)

**Atomic File Operations**
- Backup created before modification
- Changes written to temporary file
- Atomic rename on success
- Rollback on failure

### Usage Example

```python
from conflict_resolver import resolve_conflicts, parse_conflict_markers

# Method 1: Automatic escalation (recommended)
result = resolve_conflicts("path/to/file.py", api_key="sk-ant-...")

if result.success:
    print(f"Resolved {result.resolved_count}/{result.conflict_count} conflicts")
    print(f"Confidence: {result.resolution.confidence:.0%}")
    print(f"Reasoning: {result.resolution.reasoning}")
else:
    print(f"Error: {result.error_message}")
    print("Manual resolution required")

# Method 2: Manual tier control
conflicts = parse_conflict_markers("file.py")

for conflict in conflicts:
    # Try Tier 1
    suggestion = resolve_tier1_auto_merge(conflict)

    if suggestion is None:
        # Escalate to Tier 2
        suggestion = resolve_tier2_conflict_only(conflict, api_key)

    if suggestion and suggestion.confidence >= 0.7:
        apply_resolution("file.py", suggestion)
    else:
        print(f"Manual resolution needed: Line {conflict.start_line}")

# Method 3: Full-file context
conflicts = parse_conflict_markers("file.py")
result = resolve_tier3_full_file("file.py", conflicts, api_key)

if result.success:
    print(f"Resolved all {result.resolved_count} conflicts")
```

### Integration with /worktree Command

The `--ai-merge` flag integrates conflict_resolver with worktree merge workflow:

```bash
# Merge worktree with AI conflict resolution
/worktree --merge my-feature --ai-merge

# Without AI (manual resolution)
/worktree --merge my-feature
```

**Requirements**:
- ANTHROPIC_API_KEY environment variable set
- Merge conflict(s) present
- User approves AI resolution (interactive prompt)

### Error Handling

- Returns ConflictResolutionResult.success = False on any error
- ConflictResolutionResult.error_message contains details
- Graceful degradation: Missing API key, rate limiting, network errors handled
- Backup preserved on failure for manual recovery

### Performance

- Tier 1: <100ms per conflict (no API)
- Tier 2: 3-5 seconds per conflict (one API call)
- Tier 3: 5-10 seconds per file (handles chunking)
- File I/O: ~10-50ms depending on file size
- Parallel: Can resolve multiple conflicts in single API call

### Design Patterns

- **Tier Escalation**: Start simple, escalate only when needed (cost optimization)
- **Atomic Operations**: Backup-modify-verify prevents corruption
- **Graceful Degradation**: Missing API key doesn't crash, just fails with explanation
- **Progressive Disclosure**: API key only requested when needed (Tier 2+)

See library-design-patterns skill for standardized design patterns.

### Integration Points

**Command**: `/worktree --merge <feature> --ai-merge`
- Integrates conflict resolution into merge workflow
- Requires user consent before AI resolution
- Fallback to manual resolution if AI fails

**Other Libraries**: None currently (self-contained)

### Used By

- worktree_command.py - Integrates via --ai-merge flag
- merge_worktree() function in worktree_manager.py
- Future: Other merge workflows

### Test Coverage

- Tier 1 resolution: Whitespace, identical changes
- Tier 2 resolution: Single and multiple conflicts
- Tier 3 resolution: Full-file context, chunking
- Error cases: Missing file, invalid path, API errors
- Security: Path traversal, symlink detection, log injection
- Edge cases: Empty conflicts, very large files (>1MB), missing API key

### Version History

- v1.0.0 (2026-01-02) - Initial release with three-tier escalation (Issue #183)

### Backward Compatibility

N/A (new library - Issue #183)

## 74. agent_pool.py (495 lines, v1.0.0 - Issue #185)

**Scalable parallel agent pool with priority queue and token-aware rate limiting**

### Purpose

Execute multiple agents concurrently with intelligent task scheduling, priority queue management, token budget enforcement, and work-stealing load balancing. Enables scaling from 3 to 12 agents while preventing resource exhaustion.

### Problem

Sequential agent execution is slow. Parallel execution without coordination causes token budget exhaustion and resource contention. No mechanism to prioritize critical tasks (security, tests) over optional work.

### Solution

Scalable agent pool that manages concurrent execution with four key features:

1. **Priority Queue**: Tasks executed by priority (P1_SECURITY greater than P2_TESTS greater than P3_DOCS greater than P4_OPTIONAL)
2. **Token Tracking**: Sliding window budget enforcement prevents token exhaustion
3. **Work Stealing**: Agents pull tasks from queue based on availability (load balancing)
4. **Graceful Failures**: Timeouts and partial results handled cleanly

### Key Classes

**PriorityLevel (Enum)**
- P1_SECURITY: Highest priority (security-critical tasks)
- P2_TESTS: High priority (test generation)
- P3_DOCS: Medium priority (documentation)
- P4_OPTIONAL: Low priority (optional enhancements)

**TaskHandle**
- Represents submitted task
- Fields: task_id, agent_type, priority, submitted_at
- Returned from submit_task() for result tracking

**AgentResult**
- Result from completed task
- Fields: task_id, success, output, tokens_used, duration
- Contains agent output and execution metrics

**PoolStatus**
- Current pool execution state
- Fields: active_tasks, queued_tasks, completed_tasks, token_usage
- Used for monitoring and debugging

**AgentPool**
- Main pool coordinator
- Manages worker threads, task queue, token tracking, result storage
- Thread-safe with internal locking mechanisms

### Key Functions

**AgentPool.__init__(config: PoolConfig)**
- Initialize pool with configuration
- Starts worker threads
- Sets up token tracking
- Raises ValueError if config invalid

**AgentPool.submit_task(agent_type, prompt, priority, estimated_tokens)**
- Submit task to pool for execution
- Args: agent_type (string), prompt (string, less than 10,000 chars), priority (PriorityLevel), estimated_tokens (optional, default 5000)
- Returns: TaskHandle for tracking
- Raises: ValueError (invalid input), RuntimeError (token budget exhausted)
- CWE-22: Validates agent_type pattern prevents path traversal
- CWE-770: Enforces prompt size limit prevents resource exhaustion

**AgentPool.await_all(handles, timeout)**
- Wait for all submitted tasks to complete
- Args: handles (List[TaskHandle]), timeout (optional, seconds)
- Returns: List[AgentResult] (in same order as input handles)
- Raises: TimeoutError if timeout exceeded
- Blocks until all results available or timeout

**AgentPool.get_pool_status()**
- Get current pool execution state
- Returns: PoolStatus with active/queued/completed task counts and token usage
- Non-blocking, real-time status

**AgentPool.shutdown()**
- Gracefully shutdown pool
- Waits for active tasks to complete (5-second timeout per worker)
- Stops accepting new submissions
- Cleans up worker threads

### Design Patterns

- **Priority Queue**: Queue.PriorityQueue with (priority, submission_time, task_id, task_data) tuple ordering
- **Sliding Window**: TokenTracker manages token budget with time-based expiration
- **Work Stealing**: Worker threads pull tasks based on availability (natural load balancing)
- **Thread Safety**: Lock-protected access to shared state (results, status)
- **Graceful Failures**: Timeouts return partial results, exceptions captured per task

### Security Features

**Path Validation (CWE-22)**
- agent_type validated against regex pattern matching ^[a-z0-9_-]+$
- Prevents path traversal via agent type field
- Explicit error message on invalid input

**Resource Limit (CWE-400)**
- Hard cap at 12 concurrent agents (max_agents parameter)
- Token budget enforcement via sliding window
- Reject submissions exceeding budget
- Default 150,000 token budget

**Resource Limit (CWE-770)**
- Prompt size limited to 10,000 characters
- Prevents excessive memory/API usage
- Validated on submission

**Thread Safety**
- Results locked with threading.Lock
- Status locked with threading.Lock
- Supports concurrent agent execution

### Usage Example

```
from agent_pool import AgentPool, PriorityLevel
from pool_config import PoolConfig

# Create pool with 6 agents and 150K token budget
config = PoolConfig(max_agents=6, token_budget=150000)
pool = AgentPool(config=config)

# Submit high-priority security task
security_handle = pool.submit_task(
    agent_type="security-auditor",
    prompt="Audit new authentication module for vulnerabilities",
    priority=PriorityLevel.P1_SECURITY,
    estimated_tokens=8000
)

# Submit medium-priority doc task
doc_handle = pool.submit_task(
    agent_type="doc-master",
    prompt="Update API documentation for new endpoint",
    priority=PriorityLevel.P3_DOCS,
    estimated_tokens=5000
)

# Wait for all tasks to complete
results = pool.await_all([security_handle, doc_handle], timeout=60.0)

# Process results
for result in results:
    if result.success:
        print(f"Task {result.task_id} completed in {result.duration:.1f}s ({result.tokens_used} tokens)")
        print(f"Output: {result.output}")
    else:
        print(f"Task {result.task_id} failed")

# Get pool status
status = pool.get_pool_status()
print(f"Active: {status.active_tasks}, Queued: {status.queued_tasks}, Complete: {status.completed_tasks}")

# Shutdown
pool.shutdown()
```

### Integration Points

**Commands**:
- `/auto-implement` - May use for parallel validation phase (reviewer + security-auditor + doc-master)
- `/batch-implement` - May use for per-feature parallel agents

**Agents**:
- All agents can be submitted to pool (researcher, planner, implementer, test-master, reviewer, security-auditor, doc-master, etc.)
- Agent type must match valid agent names

**Libraries**:
- PoolConfig (configuration management) - Required
- TokenTracker (token budget enforcement) - Required
- Task (Claude Code Task tool) - External dependency for execution

### Performance

- Task submission: less than 1ms (queue insertion)
- Await all: Depends on task duration (typically 2-30 minutes per task)
- Pool startup: approximately 10ms (thread creation)
- Pool shutdown: 5-25 seconds (worker join timeout)
- Memory overhead: approximately 1KB per task in queue

### Test Coverage

- Task submission and validation (agent type, prompt size, token budget)
- Priority queue ordering (P1 greater than P2 greater than P3 greater than P4)
- Token budget enforcement (reject over-budget submissions)
- Concurrent task execution (worker threads)
- Result collection and ordering
- Pool status tracking
- Graceful shutdown
- Security: Path traversal prevention, resource limits
- Error handling: Timeout, invalid config, budget exceeded

### Version History

- v1.0.0 (2026-01-02) - Initial release with priority queue and token tracking (Issue #185)

### Backward Compatibility

N/A (new library - Issue #185)

## 75. pool_config.py (196 lines, v1.0.0 - Issue #185)

**Agent pool configuration with validation and loading**

### Purpose

Manage agent pool configuration with support for defaults, environment variables, and PROJECT.md loading. Provides validated configuration for AgentPool initialization.

### Problem

Agent pool needs configurable max concurrency and token budget. Configuration should support multiple sources (defaults, env vars, PROJECT.md) with validation and graceful degradation.

### Solution

PoolConfig dataclass with multi-source loading and validation:
- Constructor arguments (highest priority)
- Environment variables (AGENT_POOL_*)
- PROJECT.md file (Agent Pool Configuration section)
- Built-in defaults (fallback)

### Key Classes

**PoolConfig**
- Dataclass holding pool configuration
- Fields: max_agents (3-12), token_budget (positive), priority_enabled (bool), token_window_seconds (positive)
- Validates on instantiation via __post_init__
- Provides class methods for loading from multiple sources

### Key Functions

**PoolConfig.__init__(max_agents, token_budget, priority_enabled, token_window_seconds)**
- Initialize configuration with defaults or custom values
- Validates all parameters in __post_init__
- Raises ValueError if validation fails

**PoolConfig._validate()**
- Validate configuration values
- Checks: max_agents (3-12 range), token_budget (greater than 0), token_window_seconds (greater than 0)
- Raises ValueError with descriptive message on failure

**PoolConfig.load_from_env()**
- Load configuration from environment variables
- Variables: AGENT_POOL_MAX_AGENTS, AGENT_POOL_TOKEN_BUDGET, AGENT_POOL_PRIORITY_ENABLED, AGENT_POOL_TOKEN_WINDOW_SECONDS
- Uses constructor defaults as fallback
- Returns: PoolConfig instance
- Raises ValueError if validation fails

**PoolConfig.load_from_project(project_root)**
- Load configuration from PROJECT.md file
- Searches for Agent Pool Configuration JSON block
- Format: max_agents, token_budget, priority_enabled, token_window_seconds
- Falls back to defaults if not found
- Returns: PoolConfig instance
- Graceful degradation on parse errors

### Configuration Sources Priority

1. Constructor arguments (highest - explicit values)
2. Environment variables (AGENT_POOL_* override defaults)
3. PROJECT.md (Agent Pool Configuration section)
4. Built-in defaults (fallback - max_agents=6, token_budget=150000, priority_enabled=true, token_window_seconds=60)

### Environment Variables

| Variable | Description | Valid Range | Default |
|----------|-------------|-------------|---------|
| AGENT_POOL_MAX_AGENTS | Max concurrent agents | 3-12 | 6 |
| AGENT_POOL_TOKEN_BUDGET | Token budget for window | Positive | 150000 |
| AGENT_POOL_PRIORITY_ENABLED | Enable priority queue | true/false | true |
| AGENT_POOL_TOKEN_WINDOW_SECONDS | Sliding window duration | Positive | 60 |

### Security Features

**Input Validation**
- Type checking (int, bool)
- Range validation (max_agents: 3-12)
- Positive value checking (token_budget, token_window_seconds)
- Descriptive error messages

**Graceful Degradation**
- Invalid PROJECT.md doesn't crash, falls back to env/defaults
- Missing env vars use defaults
- Parse errors logged and ignored

**No External Dependencies**
- Pure Python dataclass
- No network calls
- No subprocess execution

### Usage Example

```
from pool_config import PoolConfig
from pathlib import Path

# Use defaults
config = PoolConfig()
print(f"Default: {config.max_agents} agents, {config.token_budget} token budget")

# Load from environment
config = PoolConfig.load_from_env()

# Load from PROJECT.md with fallback
config = PoolConfig.load_from_project(Path(".claude/PROJECT.md"))

# Custom values
config = PoolConfig(max_agents=8, token_budget=200000)

# Pass to AgentPool
from agent_pool import AgentPool
pool = AgentPool(config=config)
```

### Integration Points

**AgentPool**: Required configuration parameter
**Commands**: `/auto-implement`, `/batch-implement` may read config

### Performance

- Load from env: less than 1ms (os.getenv + int conversion)
- Load from PROJECT.md: 5-10ms (file I/O + JSON parsing)
- Validation: less than 1ms (range checks)
- Total overhead: Negligible compared to agent execution

### Test Coverage

- Default construction and validation
- Environment variable loading and override
- PROJECT.md loading and parsing
- Validation: Range checks, positive values, type checking
- Graceful degradation: Missing/invalid sources
- Error messages and exception types

### Version History

- v1.0.0 (2026-01-02) - Initial release with multi-source loading (Issue #185)

### Backward Compatibility

N/A (new library - Issue #185)

## 76. token_tracker.py (177 lines, v1.0.0 - Issue #185)

**Token-aware rate limiting with sliding window**

### Purpose

Track token usage across multiple agents with sliding time window to enforce budget limits and prevent token exhaustion during parallel execution.

### Problem

Parallel agent execution can quickly exhaust token budget without rate limiting. Need mechanism to track total usage, allow budget enforcement, and prevent over-submission.

### Solution

Token tracker with sliding window approach:
- Records usage per agent with timestamp
- Expires old records automatically based on time window
- Enforces budget by rejecting submissions exceeding remaining budget
- Provides usage breakdown by agent for monitoring

### Key Classes

**UsageRecord**
- Represents single token usage event
- Fields: agent_id, tokens, timestamp
- Used internally for sliding window tracking

**TokenTracker**
- Main tracking class
- Manages budget enforcement and usage tracking
- Thread-safe for concurrent agent access

### Key Functions

**TokenTracker.__init__(budget, window_seconds)**
- Initialize tracker with budget and window
- Args: budget (positive int), window_seconds (positive int, default 60)
- Raises ValueError if budget or window_seconds non-positive
- Sets up empty usage records list

**TokenTracker.record_usage(agent_id, tokens)**
- Record token usage for an agent
- Args: agent_id (string), tokens (int)
- Creates UsageRecord with current timestamp
- Appends to usage_records list
- Logs debug message

**TokenTracker.can_submit(estimated_tokens)**
- Check if submission would exceed budget
- Args: estimated_tokens (int)
- Returns: bool (True if within budget, False otherwise)
- Cleans up expired records before checking
- Non-blocking check

**TokenTracker.get_remaining_budget()**
- Get remaining token budget in current window
- Returns: int (remaining budget, greater than or equal to 0)
- Cleans up expired records first
- Calculates total usage in window and subtracts from budget

**TokenTracker._cleanup_expired_records()**
- Remove records outside sliding window
- Private method called before budget checks
- Removes records with timestamp greater than window_seconds ago
- Uses datetime.now() for current time

**TokenTracker.get_usage_by_agent()**
- Get per-agent token usage breakdown
- Returns: Dict[str, int] (agent_id to total tokens)
- Cleans up expired records first
- Useful for monitoring and debugging

### Sliding Window Design

**How it works**:
1. Each token usage recorded with timestamp
2. Before budget check, expired records removed (older than window_seconds)
3. Remaining records summed for total usage
4. Remaining budget = budget - total_usage
5. Submission allowed if remaining greater than or equal to estimated_tokens

**Why it works**:
- Allows temporary spikes within window
- Automatic expiration prevents permanent budget exhaustion
- Window defaults to 60 seconds (configurable)
- Per-agent tracking enables usage monitoring

**Example**:
Budget: 150,000 tokens, Window: 60 seconds

At T=0:
  - Agent A uses 50,000 tokens
  - Remaining: 100,000

At T=30:
  - Agent B uses 70,000 tokens
  - Total usage: 120,000
  - Remaining: 30,000

At T=65:
  - Agent A's usage expired (recorded at T=0, now greater than 60s old)
  - Remaining usage: 70,000 (only Agent B)
  - Remaining budget: 80,000

### Security Features

**Budget Enforcement (CWE-400)**
- Hard budget limits prevent token exhaustion
- Reject submissions exceeding available budget
- Per-agent tracking prevents single agent hogging budget

**No External Dependencies**
- Pure Python implementation
- No network calls
- No subprocess execution
- No file I/O

**Thread-Safe**
- Uses datetime for consistent timestamps
- Stateless operations (no race conditions on list operations in CPython)
- Safe for concurrent agent access

### Usage Example

```
from token_tracker import TokenTracker

# Create tracker: 150K token budget, 60-second window
tracker = TokenTracker(budget=150000, window_seconds=60)

# Check if can submit task
if tracker.can_submit(estimated_tokens=10000):
    # Submit task...
    # After execution, record actual usage
    tracker.record_usage(agent_id="researcher", tokens=8500)
else:
    print("Token budget exhausted, cannot submit new tasks")

# Check remaining budget
remaining = tracker.get_remaining_budget()
print(f"Remaining budget: {remaining} tokens")

# Monitor per-agent usage
usage_by_agent = tracker.get_usage_by_agent()
for agent_id, tokens in usage_by_agent.items():
    print(f"Agent {agent_id}: {tokens} tokens")

# Usage expires automatically after window
# At T=65 seconds, records from T=0 automatically removed
```

### Integration Points

**AgentPool**: Required for token budget enforcement
**PoolConfig**: Provides window_seconds configuration

### Performance

- Record usage: less than 1ms (append to list)
- Get remaining budget: 1-5ms (cleanup + summation, depends on record count)
- Can submit check: 1-5ms (cleanup + comparison)
- Cleanup: O(n) where n equals records in window (typically 1-20 records)

### Test Coverage

- Tracker initialization with valid/invalid budgets
- Recording usage and timestamp tracking
- Can_submit budget checking and remaining calculation
- Usage expiration and cleanup (time-based)
- Per-agent usage breakdown
- Thread safety with concurrent operations
- Edge cases: Empty records, zero budget, very large usage

### Version History

- v1.0.0 (2026-01-02) - Initial release with sliding window (Issue #185)

### Backward Compatibility

N/A (new library - Issue #185)


## 77. ideation_engine.py (431 lines, v1.0.0 - Issue #186)

### Purpose

Orchestrates automated discovery of improvement opportunities across code quality, security, performance, accessibility, and technical debt through multi-category analysis.

### Problem

Manual code review is time-consuming and misses systemic issues. Development teams need automated suggestions for improvements without running separate tools for each category (security scanners, linters, complexity checkers, etc.). Single-category tools miss cross-cutting improvements.

### Solution

Unified analysis framework that runs specialized analyzers (ideators) for five improvement categories, aggregates findings with metadata (severity, confidence, effort, impact), and generates prioritized recommendations and GitHub issue descriptions.

### Key Classes

**IdeationCategory** (Enum)
- SECURITY: Security vulnerabilities and weaknesses
- PERFORMANCE: Performance bottlenecks and inefficiencies
- QUALITY: Code quality issues (tests, duplication, complexity)
- ACCESSIBILITY: User experience and accessibility issues
- TECH_DEBT: Technical debt accumulation

**IdeationSeverity** (Enum)
- CRITICAL: Requires immediate attention
- HIGH: High-priority, address soon
- MEDIUM: Medium-priority for planning
- LOW: Low-priority nice-to-have improvements
- INFO: Informational findings

**IdeationResult** (Dataclass)
- category: IdeationCategory
- severity: IdeationSeverity
- location: str (file:line format)
- title: str (short finding title)
- description: str (detailed issue description)
- suggested_fix: str (recommended fix)
- confidence: float (0.0-1.0)
- impact: str (impact assessment)
- effort: str (effort estimate)
- references: List[str] (CWE, OWASP, etc.)

**IdeationReport** (Dataclass)
- timestamp: str (ISO format)
- categories_analyzed: List[IdeationCategory]
- total_findings: int
- findings_by_severity: Dict[IdeationSeverity, int]
- results: List[IdeationResult]
- analysis_duration: float (seconds)
- Methods:
  - to_markdown() - Generate markdown report
  - filter_by_severity(min_severity) - Filter by severity level

**IdeationEngine** (Main Orchestrator)
- __init__(project_root: Path) - Initialize with project root
- run_ideation(categories: List[IdeationCategory]) - Run analysis for specified categories
- prioritize_results(results: List[IdeationResult]) - Sort by severity and confidence
- generate_issues(results, min_severity) - Create GitHub issue descriptions
- filter_by_minimum_severity(results, min_severity) - Filter by severity threshold

### Key Functions

**IdeationEngine.run_ideation()**
- Coordinates all ideators for requested categories
- Returns IdeationReport with findings aggregated
- Measures analysis duration
- Calculates statistics by severity

**IdeationEngine.prioritize_results()**
- Sorts by severity (CRITICAL > HIGH > MEDIUM > LOW > INFO)
- Secondary sort by confidence score
- Returns highest-priority findings first

**IdeationEngine.generate_issues()**
- Creates GitHub issue descriptions from results
- Filters by minimum severity
- Formats as markdown with metadata

**IdeationReport.filter_by_severity()**
- Returns results at or above specified severity
- Enables severity-based filtering

### Security Features

**Path Traversal Prevention (CWE-22)**
- All paths converted to Path objects
- Relative paths generated using relative_to()
- No string concatenation for paths

**Input Validation**
- Confidence scores validated (0.0-1.0)
- Project root validated as directory
- Category/severity enums restrict values

**Safe File Handling**
- pathlib.Path for all file operations
- read_text() with encoding specified
- Exception handling for file access errors

**No Arbitrary Code Execution**
- Pattern matching only (no eval, exec, import)
- Read-only analysis
- No subprocess calls

### Integration Points

**Ideators Package**: Five specialized analyzers
**IdeationReportGenerator**: Markdown report generation
**Command Integration**: /ideate command can use this engine
**Agent Integration**: planner agent can use for feature discovery

### Performance

- Analysis duration: 2-10 seconds (depends on project size)
- Report generation: less than 500ms

### Test Coverage

- IdeationCategory and IdeationSeverity enums
- IdeationResult dataclass with confidence validation
- IdeationReport creation and aggregation
- Result prioritization and filtering
- Issue generation and formatting
- Edge cases: empty results, single results, duplicate severities

### Version History

- v1.0.0 (2026-01-02) - Initial release with five ideators (Issue #186)

### Backward Compatibility

N/A (new library - Issue #186)

## 78. ideation_report_generator.py (231 lines, v1.0.0 - Issue #186)

### Purpose

Generates formatted markdown reports from ideation analysis results with multiple output formats and filtering options.

### Problem

Raw IdeationReport requires custom formatting for different use cases. Users need multiple report types (full, summary, category-specific, critical-only) with flexible filtering.

### Solution

Dedicated report generator providing multiple report generation methods with flexible filtering and formatting options.

### Key Classes

**IdeationReportGenerator**
- generate(report) - Main entry point
- generate_markdown_report(report, filters) - Full report with optional filtering
- generate_summary_report(report) - Summary only (no detailed findings)
- generate_findings_by_category(report, category) - Category-specific report
- generate_critical_findings_report(report) - Critical issues only

### Key Functions

**generate()**
- Main entry point, delegates to generate_markdown_report()

**generate_markdown_report()**
- Applies optional filtering by min_severity
- Returns formatted markdown string
- Uses IdeationReport.to_markdown() for consistency

**generate_summary_report()**
- Header with timestamp and duration
- Total findings count
- Breakdown by severity and category
- No detailed findings

**generate_findings_by_category()**
- Filters results to single category
- Returns full report for that category

**generate_critical_findings_report()**
- Filters to CRITICAL severity only
- Concise format for urgent action items

### Security Features

**No External Dependencies**
- Pure Python (only stdlib and ideation_engine)
- No network calls
- No subprocess execution

**Safe Report Generation**
- No eval, exec, or arbitrary code execution
- String formatting only

**Input Validation**
- Report and category enum validation
- No string injection vectors

### Integration Points

**IdeationEngine**: Provides IdeationReport objects
**Commands**: /ideate command uses this generator
**Agents**: planner agent can use summary reports

### Performance

- Report generation: less than 500ms
- Summary generation: less than 100ms

### Test Coverage

- Report generation with filtering options
- Summary/category/critical report generation
- Severity filtering (all combinations)
- Edge cases: empty results, mixed severities

### Version History

- v1.0.0 (2026-01-02) - Initial release (Issue #186)

### Backward Compatibility

N/A (new library - Issue #186)

## 79-83. ideators/ package (5 specialized analyzers - Issue #186)

### Purpose

Five specialized Python modules detecting improvement opportunities in specific categories:
- security_ideator.py: Security vulnerabilities
- performance_ideator.py: Performance bottlenecks
- quality_ideator.py: Code quality issues
- accessibility_ideator.py: Accessibility and UX issues
- tech_debt_ideator.py: Technical debt patterns

### 79. security_ideator.py (252 lines)

Detects security vulnerabilities:
- SQL injection (string concatenation in queries)
- XSS vulnerabilities (unescaped HTML output)
- Command injection (shell command construction)
- Path traversal vulnerabilities
- Insecure cryptography usage

Reports: CRITICAL (SQL/command injection), HIGH (XSS, path traversal), MEDIUM (weak crypto)

### 80. performance_ideator.py (198 lines)

Detects performance issues:
- N+1 query problems (ORM queries in loops)
- Inefficient algorithms (nested loops, O(n^2))
- Missing database indexes
- Unoptimized file I/O (repeated reads)
- Memory leaks (unbounded lists)

Reports: HIGH (N+1 queries), MEDIUM (inefficient algorithms), LOW (memory patterns)

### 81. quality_ideator.py (304 lines)

Detects code quality issues:
- Missing test coverage (no test_*.py files)
- Code duplication (similar functions)
- High cyclomatic complexity (deep nesting)
- Missing docstrings
- Long functions/methods

Reports: MEDIUM (missing tests, duplication, complexity), LOW (docstrings, length)

### 82. accessibility_ideator.py (184 lines)

Detects accessibility issues:
- Missing help text (functions without docstrings)
- Poor error messages (generic exceptions)
- Missing validation error messages
- Inaccessible UI patterns
- Missing internationalization

Reports: LOW (accessibility concerns), INFO (best practices)

### 83. tech_debt_ideator.py (225 lines)

Detects technical debt patterns:
- Deprecated API usage
- Outdated dependency versions
- Known vulnerability patterns
- Code style violations
- Inefficient imports

Reports: MEDIUM (deprecated APIs), LOW (style, imports)

### Common Integration Pattern

All ideators follow a standard pattern with __init__ and analyze() methods returning List[IdeationResult].

### Performance Baselines

- Security analysis: 1-2 seconds
- Performance analysis: 1-2 seconds
- Quality analysis: 2-3 seconds (file iteration)
- Accessibility analysis: 1-2 seconds
- Tech debt analysis: 1-3 seconds
- Total: 6-12 seconds for all categories

### Files Added

- plugins/autonomous-dev/lib/ideation_engine.py (431 lines)
- plugins/autonomous-dev/lib/ideation_report_generator.py (231 lines)
- plugins/autonomous-dev/lib/ideators/__init__.py (28 lines)
- plugins/autonomous-dev/lib/ideators/security_ideator.py (252 lines)
- plugins/autonomous-dev/lib/ideators/performance_ideator.py (198 lines)
- plugins/autonomous-dev/lib/ideators/quality_ideator.py (304 lines)
- plugins/autonomous-dev/lib/ideators/accessibility_ideator.py (184 lines)
- plugins/autonomous-dev/lib/ideators/tech_debt_ideator.py (225 lines)
- tests/unit/lib/test_ideation_engine.py (comprehensive tests)

### Version History

- v1.0.0 (2026-01-02) - Initial release with five ideators (Issue #186)

### Backward Compatibility

N/A (new libraries - Issue #186)


## 84. parallel_validation.py (753 lines, v1.0.0 - Issue #188)

### Purpose

Migrates /auto-implement STEP 4.1 parallel validation from prompt engineering to reusable agent_pool library integration. Provides unified parallel validation execution for security-auditor, reviewer, and doc-master agents with security-first priority mode, automatic retry logic, and result aggregation.

### Problem

Previously, /auto-implement Step 4.1 parallel validation relied on prompt engineering and manual coordination within the conversation. This approach:
- Tight coupling between /auto-implement and validation logic
- No reusability for other workflows needing parallel validation
- Manual retry logic and error handling
- Difficult to test in isolation
- Hard to optimize performance independently

### Solution

Dedicated parallel_validation library that:
- Encapsulates validation orchestration in reusable functions
- Integrates with AgentPool library for scalable parallel execution
- Provides security-first priority mode (security blocks on failure)
- Automatic retry with exponential backoff (transient vs permanent error classification)
- Result aggregation and parsing from agent outputs
- Comprehensive error handling and validation

### Key Classes

**ValidationResults** (dataclass)
- security_passed: bool - Security audit pass/fail status
- review_passed: bool - Code review pass/fail status
- docs_updated: bool - Documentation update status
- failed_agents: List[str] - List of agent types that failed
- execution_time_seconds: float - Total execution time
- security_output: str - Raw security agent output
- review_output: str - Raw reviewer output
- docs_output: str - Raw doc-master output

### Key Functions

**execute_parallel_validation()**
- Main entry point for parallel validation
- Args: feature_description, project_root, priority_mode, changed_files, max_retries
- Returns: ValidationResults
- Raises: ValueError (invalid input), SecurityValidationError (security failure in priority mode), ValidationTimeoutError (all agents timeout)
- Behavior: Coordinates agent pool execution and result aggregation

**_execute_security_first()**
- Security-first priority mode execution
- Phase 1: Runs security agent first (blocking)
- Phase 2: If security passes, runs reviewer + doc-master in parallel
- Raises: SecurityValidationError if security audit fails
- Rationale: Security failures should block feature implementation immediately

**_aggregate_results()**
- Parses agent outputs and aggregates into ValidationResults
- Looks for "PASS"/"FAIL" in security-auditor output
- Looks for "APPROVE"/"REQUEST_CHANGES" in reviewer output
- Looks for "UPDATED" in doc-master output
- Handles missing results with appropriate defaults
- Returns: ValidationResults with aggregated status

**retry_with_backoff()**
- Executes agent task with automatic retry on transient errors
- Exponential backoff: 2^n seconds (2s, 4s, 8s, ...)
- Transient errors (timeout, connection) - automatically retried
- Permanent errors (syntax, import, type) - fail fast
- Args: pool, agent_type, prompt, max_retries, priority
- Returns: AgentResult from successful execution
- Raises: Exception on permanent error or max retries exceeded

**is_transient_error()**
- Classify error as transient (should retry)
- Returns: True for TimeoutError, ConnectionError, HTTP 5xx patterns
- Returns: False for permanent errors

**is_permanent_error()**
- Classify error as permanent (fail fast)
- Returns: True for SyntaxError, ImportError, ValueError, PermissionError, TypeError, KeyError, AttributeError
- Returns: False for transient errors

### Key Features

**Parallel Validation Modes**:
- All parallel mode (default): All three agents run simultaneously
- Security-first mode: Security runs first, blocks on failure, then parallel validation

**Automatic Retry**:
- Transient error detection (timeout, network, HTTP 5xx)
- Permanent error detection (syntax, import, type)
- Exponential backoff (2^n seconds)
- Circuit breaker: max_retries limit (default 3)

**Result Aggregation**:
- Parse agent outputs from free-form text
- Track execution time from AgentResult.duration
- Aggregate failures with detailed error messages
- Handle missing agents with appropriate fallbacks

**Security-First Priority**:
- Security agent runs first
- If security fails, raises SecurityValidationError immediately
- Blocks reviewer and doc-master from executing
- Prevents unsafe code from being approved

**Input Validation**:
- Feature description validation (non-empty)
- Project root path validation (Path object, exists)
- File path validation (format check)

### Security Features

**CWE-22 (Path Traversal Prevention)**:
- project_root must be Path object
- project_root.exists() validated
- Only relative paths in changed_files (no absolute paths)

**Input Validation**:
- Feature description non-empty check
- Path object type validation
- File path format validation

**Error Classification**:
- Transient vs permanent error detection
- Prevents retry loops on permanent errors
- Protects against infinite backoff

### Integration Points

**AgentPool Library** (Issue #185)
- Uses AgentPool.submit_task() for agent execution
- Uses AgentPool.await_all() for result retrieval
- Respects PriorityLevel (P1_SECURITY, P2_TESTS, P3_DOCS)
- Gracefully handles pool initialization

**auto-implement Command**
- Called from /auto-implement Step 4.1 (parallel validation phase)
- Replaces prompt engineering with library call
- Passes feature description, project root, changed files

**PoolConfig Library** (Issue #185)
- Uses PoolConfig.load_from_env() for configuration
- Supports environment-based pool settings

### Performance

**Baseline** (3 agents parallel):
- Execution time: 2-5 minutes (depends on agent response time)
- Security audit: 60-90 seconds
- Code review: 45-60 seconds
- Documentation: 45-60 seconds
- Total (parallel): approximately 90 seconds (wall clock, not sequential sum)

**Retry Performance Impact**:
- Transient error retry: +2s per retry (exponential backoff)
- Permanent error: immediate fail (no backoff)
- Typical: 1 retry needed in 5 percent of cases

### Test Coverage

- ValidationResults dataclass creation and serialization
- execute_parallel_validation() with valid/invalid inputs
- _execute_security_first() security blocking behavior
- _aggregate_results() with various agent outputs
- retry_with_backoff() transient and permanent error handling
- is_transient_error() classification accuracy
- is_permanent_error() classification accuracy
- Missing agent result handling
- Timeout and exception propagation
- Integration with mocked AgentPool

**Test Files**:
- tests/unit/lib/test_parallel_validation_library.py (943 lines - comprehensive unit tests)
- tests/integration/test_parallel_validation.py (integration tests with real agent pool)

### Files Added

- plugins/autonomous-dev/lib/parallel_validation.py (753 lines)
- tests/unit/lib/test_parallel_validation_library.py (943 lines)
- tests/integration/test_parallel_validation.py (updated)

### Files Modified

- plugins/autonomous-dev/config/install_manifest.json (added parallel_validation.py to library manifest)

### API Usage Example

```python
from pathlib import Path
from parallel_validation import execute_parallel_validation, SecurityValidationError

# Execute parallel validation with security-first mode
results = execute_parallel_validation(
    feature_description="Add JWT authentication to login endpoint",
    project_root=Path("/path/to/project"),
    priority_mode=True,  # Security blocks on failure
    changed_files=["src/auth/jwt.py", "tests/test_jwt.py"]
)

# Check results
if not results.security_passed:
    raise SecurityValidationError(f"Security failed: {results.security_output}")

print(f"Validation complete:")
print(f"  Security: PASS" if results.security_passed else "  Security: FAIL")
print(f"  Review: PASS" if results.review_passed else "  Review: FAIL")
print(f"  Docs: UPDATED" if results.docs_updated else "  Docs: NOT UPDATED")
print(f"  Duration: {results.execution_time_seconds:.1f}s")

if results.failed_agents:
    print(f"Failed agents: {', '.join(results.failed_agents)}")
```

### Command-Line Usage

```bash
# Execute parallel validation with CLI
python -m autonomous_dev.lib.parallel_validation \
  --feature "Add JWT authentication" \
  --project-root /path/to/project \
  --priority-mode \
  --changed-files src/auth/jwt.py tests/test_jwt.py \
  --output-format json
```

### Dependencies

- **AgentPool** (plugins/autonomous-dev/lib/agent_pool.py) - Agent orchestration
- **PoolConfig** (plugins/autonomous-dev/lib/pool_config.py) - Configuration management
- Standard library: logging, time, dataclasses, pathlib, typing, argparse, json, sys

### Version History

- v1.0.0 (2026-01-02) - Initial release, migrate from /auto-implement prompt engineering (Issue #188)

### Backward Compatibility


## 85. ralph_loop_manager.py (305 lines, v1.0.0 - Issue #189)

**Purpose**: Orchestrate self-correcting agent execution with retry loops, circuit breaker pattern, and token usage tracking.

**Problem**: Agents sometimes complete tasks incompletely or fail silently. Manual retry coordination is error-prone, and cost overruns from infinite loops are possible.

**Solution**: Ralph Loop Manager that tracks iterations, enforces circuit breaker on consecutive failures, limits token usage, and determines when to allow retry vs. blocking further attempts.

**Location**: `plugins/autonomous-dev/lib/ralph_loop_manager.py`

**Key Features**:
- Iteration tracking (max 5 iterations per session)
- Circuit breaker pattern (3 consecutive failures blocks retry)
- Token usage tracking (prevents cost overruns)
- Thread-safe state operations with atomic writes
- Graceful degradation for corrupted state files

**Constants**:
- `MAX_ITERATIONS = 5` - Maximum retry attempts per session
- `CIRCUIT_BREAKER_THRESHOLD = 3` - Consecutive failures to trigger circuit breaker
- `DEFAULT_TOKEN_LIMIT = 50000` - Token limit for entire loop

**Key Classes**:
- `RalphLoopState` (dataclass) - Tracks session state (current iteration, tokens used, consecutive failures, circuit breaker status)
- `RalphLoopManager` - Main orchestrator with methods:
  - `record_attempt(tokens_used)` - Record token consumption for attempt
  - `should_retry()` - Check if retry allowed (respects max iterations, circuit breaker, token limit)
  - `record_success()` - Record successful completion
  - `record_failure(error_msg)` - Record failure and check circuit breaker
  - `get_state()` - Get current state for inspection
  - `reset_state()` - Reset for new session

**Retry Decision Logic**:
1. Check max iterations (5 iterations -> block)
2. Check circuit breaker (3 consecutive failures -> block)
3. Check token limit (exceeded -> block)
4. If all checks pass -> allow retry

**Security Features**:
- Atomic state file writes (temp + rename to prevent corruption)
- Thread-safe operations with locks
- Path validation to prevent directory traversal
- Graceful degradation for corrupted state files (logs warning, continues)
- No code execution from user input

**API Highlights**:
```python
from ralph_loop_manager import RalphLoopManager, MAX_ITERATIONS, CIRCUIT_BREAKER_THRESHOLD

# Create manager for session
manager = RalphLoopManager("session-123", token_limit=50000)

# Record attempt with tokens
manager.record_attempt(tokens_used=5000)

# Check if should retry
if manager.should_retry():
    # Retry execution
    try:
        # Run agent task
        pass
    except Exception as e:
        manager.record_failure(str(e))
else:
    # Stop (max iterations, circuit breaker, or token limit)
    print("Retry blocked: " + manager.get_state().stop_reason)

# Record success
manager.record_success()
```

**State Persistence**:
- State stored in `~/.autonomous-dev/ralph_loop_sessions/[session-id].json`
- Portable path detection works from any directory
- Atomic writes prevent corruption on crash

**Test Coverage**:
- RalphLoopState creation and serialization
- RalphLoopManager initialization and state management
- should_retry() with various state conditions
- record_attempt() token tracking
- record_failure() circuit breaker triggering
- Thread safety with concurrent operations
- State file corruption handling

**Version History**:
- v1.0.0 (2026-01-02) - Initial release for self-correcting agent execution (Issue #189)

**Dependencies**:
- Standard library: json, threading, tempfile, pathlib, dataclasses, datetime

**Files Added**:
- plugins/autonomous-dev/lib/ralph_loop_manager.py (305 lines)
- tests/unit/lib/test_ralph_loop_manager.py (test suite)

---

## 86. success_criteria_validator.py (432 lines, v1.0.0 - Issue #189)

**Purpose**: Provide multiple validation strategies to determine if agent task completed successfully.

**Problem**: Different tasks need different validation approaches. Some need test verification (pytest), others need file existence checks, and still others need output parsing. Each agent implements validation differently, leading to inconsistency and bugs.

**Solution**: Unified validator library supporting five validation strategies with security hardening, timeout enforcement, and clear success/failure messages.

**Location**: `plugins/autonomous-dev/lib/success_criteria_validator.py`

**Key Features**:
- Multiple validation strategies (pytest, safe_word, file_existence, regex, json)
- Security validations (path traversal, ReDoS, command injection)
- Timeout enforcement for long-running operations
- Thread-safe operation
- Clear success/failure messages with context

**Validation Strategies**:

1. **Pytest Strategy**
   - Runs pytest and checks pass/fail
   - Timeout: 30 seconds (configurable)
   - Returns test output and status
   - Use case: Unit/integration test verification

2. **Safe Word Strategy**
   - Searches for completion marker in agent output
   - Case-insensitive matching
   - Returns match position and context
   - Use case: Agent output verification (e.g., "TASK_COMPLETE")

3. **File Existence Strategy**
   - Verifies all expected files exist
   - Checks file paths, rejects symlinks (CWE-59)
   - Returns list of missing files
   - Use case: Output file verification

4. **Regex Strategy**
   - Extracts data via regex pattern
   - ReDoS prevention (1 second timeout)
   - Validates extracted value against expected
   - Use case: Structured output validation

5. **JSON Strategy**
   - Extracts data via JSONPath expression
   - Validates extracted value against expected
   - Provides detailed error context
   - Use case: JSON response validation

**Constants**:
- `DEFAULT_PYTEST_TIMEOUT = 30` - Timeout for pytest runs
- `REGEX_TIMEOUT = 1` - Timeout for regex operations (prevent ReDoS)

**Key Functions**:
```python
# Pytest validation
success, message = validate_pytest("tests/test_feature.py", timeout=10)

# Safe word validation
success, message = validate_safe_word(agent_output, safe_word="SAFE_WORD_COMPLETE")

# File existence validation
success, message = validate_file_existence(["output.txt", "data.json"])

# Output parsing validation
success, message = validate_output_parsing(
    agent_output,
    strategy="regex",
    pattern=r"Result: (\d+)",
    expected="42"
)
```

**Security Features**:
- Path traversal prevention (CWE-22): Validates paths exist and are files/directories
- Symlink rejection (CWE-59): Rejects symlinks to prevent TOCTOU attacks
- Command injection prevention (CWE-78): Uses subprocess.run with list arguments (no shell=True)
- ReDoS prevention: Regex operations timeout after 1 second
- Input validation: Validates patterns, paths, JSONPath expressions
- No code execution from user input

**Validation Result**:
```python
class ValidationResult:
    # Result of validation attempt.
    success: bool          # True if validation passed
    message: str           # Human-readable result message
    strategy: str          # Which strategy was used
    details: Dict          # Additional context (matches, file list, etc.)
    duration_seconds: float # How long validation took
```

**API Highlights**:
```python
from success_criteria_validator import validate_success, validate_pytest

# Generic validator (auto-selects strategy based on criteria type)
result = validate_success(
    criteria={
        "strategy": "pytest",
        "test_file": "tests/test_auth.py"
    }
)

# Specific validator
result = validate_pytest("tests/test_auth.py", timeout=30)

# Check result
if result.success:
    print(f"PASS: {result.message}")
else:
    print(f"FAIL: {result.message}")
    print(f"Details: {result.details}")
```

**Test Coverage**:
- validate_pytest() with passing/failing tests
- validate_safe_word() with various outputs
- validate_file_existence() with existing/missing files
- validate_output_parsing() with regex/json strategies
- Security: Path traversal rejection, symlink detection, injection prevention
- Timeout enforcement for long operations
- Edge cases: Empty patterns, missing files, malformed JSON
- Performance: Validation speed benchmarks

**Version History**:
- v1.0.0 (2026-01-02) - Initial release with five validation strategies (Issue #189)

**Dependencies**:
- Standard library: json, subprocess, re, pathlib, typing, signal, os

**Files Added**:
- plugins/autonomous-dev/lib/success_criteria_validator.py (432 lines)
- tests/unit/lib/test_success_criteria_validator.py (test suite)

---
100 percent compatible - new library, no API changes to existing code. Replaces internal /auto-implement Step 4.1 orchestration without affecting external interfaces.


---

## 87. agent_feedback.py (946 lines, v1.0.0 - Issue #191)

**Purpose**: Machine learning feedback loop for intelligent agent routing optimization based on historical performance metrics.

**Problem**: Agent selection is static. Planner assigns agents without data about their performance on similar tasks. This leads to suboptimal routing and missed optimization opportunities.

**Solution**: Feedback loop system that:
1. Records agent performance after each feature (duration, success, feature type, complexity)
2. Queries historical data to recommend optimal agents for new features
3. Maintains aggregated statistics by agent/feature-type/complexity combination
4. Provides fallback agent suggestions when primary recommendation has low confidence
5. Automatically prunes old data (90-day retention) with monthly aggregation

**Key Features**:

1. **Feature Type Classification**: 7 categories (security, api, ui, refactor, docs, tests, general)
   - Keyword-based classification (e.g., "auth", "oauth" → security)
   - Fallback to "general" for unmatched features
   - Configurable keyword patterns per category

2. **Confidence Scoring**: Statistical confidence metric
   - Formula: confidence = success_rate * sqrt(min(executions, 50) / 50)
   - Low confidence (less than 10 executions): 0.0-0.5
   - Medium confidence (30 executions): 0.77 with 100% success
   - High confidence plateau (50+ executions): success_rate as limiting factor
   - Ensures recommendations backed by sufficient data

3. **Smart Routing**: Query optimal agents per feature
   - Top N recommendations (sorted by confidence)
   - Fallback agents for redundancy
   - Reasoning explanation for each recommendation
   - Success rates and execution counts included

4. **Data Aggregation**: Monthly aggregation of old feedback
   - Preserves daily feedback for recent data (90-day window)
   - Aggregates older data by month for retention
   - Automatically runs during cleanup operations
   - Maintains queryability across all time ranges

5. **Atomic Writes**: Crash-proof state persistence
   - Tempfile + atomic rename (prevents corruption on crash)
   - Lock-based coordination for concurrent access
   - Graceful error handling for corrupted state files
   - Audit logging for all state changes

6. **Security Hardening**:
   - CWE-22 (path traversal): Path validation and exists() checks
   - Input validation: agent_name, complexity, duration, feature types
   - Sanitization: Feature descriptions and metadata
   - No code execution from user input
   - Audit trail logging for all operations

**Dataclasses**:

Single feedback entry (AgentFeedback):
- agent_name: Name of executing agent
- feature_type: Type of feature (security, api, ui, refactor, docs, tests, general)
- complexity: Feature complexity (SIMPLE, STANDARD, COMPLEX)
- duration: Execution time in minutes
- success: Whether agent completed successfully
- timestamp: ISO 8601 timestamp (auto-added)
- metadata: Additional context (owasp_checks, coverage, etc.)

Aggregated statistics (FeedbackStats):
- success_rate: Percentage of successful executions (0.0-1.0)
- avg_duration: Average execution time in minutes
- executions: Total execution count
- last_execution: ISO 8601 timestamp of most recent execution
- confidence: Confidence score (0.0-1.0) based on data volume

Recommendation with fallbacks (RoutingRecommendation):
- agent_name: Primary recommended agent
- confidence: Confidence score (0.0-1.0)
- reasoning: Explanation of recommendation
- fallback_agents: Backup agents if primary unavailable
- stats: Performance metrics for this agent

**State File Structure** (.claude/agent_feedback.json):

JSON structure with version, feedback array, and aggregated monthly statistics:
- version: "1.0"
- feedback: Array of AgentFeedback entries with agent_name, feature_type, complexity, duration, success, timestamp, metadata
- aggregated: Nested object by month/agent/feature_type/complexity with total_executions, success_count, total_duration

**Public API**:

Key functions:
- record_feedback(agent_name, feature_type, complexity, duration, success, metadata=None) - Record agent performance after task completion
- query_recommendations(feature_type, complexity, top_n=3) - Get recommended agents for a feature
- get_agent_stats(agent_name) - Get statistics for specific agent
- classify_feature_type(description) - Classify feature type from description
- cleanup_old_data() - Prune expired data and aggregate old feedback

Usage:
- Record performance after agent completes
- Query recommendations when planning next features
- Classify features automatically from descriptions
- Run periodic cleanup for maintenance

**Usage Example** (Integration in /auto-implement):

After security-auditor completes:
1. Record the execution with agent_name, feature_type, complexity, duration, success flag
2. For future features, planner queries recommendations for security/STANDARD
3. Suggests agents to use based on historical performance

**Constants**:

- DATA_RETENTION_DAYS = 90: Keep daily feedback for 90 days
- CONFIDENCE_SCALE_FACTOR = 50: Executions needed to reach high confidence
- DEFAULT_TOP_N = 3: Default number of recommendations to return
- FEEDBACK_FILE = ".claude/agent_feedback.json"

**Integration Points**:

1. Planner Agent: Query recommendations when assigning agents
2. Agent Exit: Record feedback after agent completion (SubagentStop hook)
3. Maintenance: Periodic cleanup via /health-check command
4. Reporting: Session reports include feedback statistics

**Test Coverage** (73 tests total):

Unit Tests (55 tests):
- Dataclass validation and serialization
- Feature type classification (7 categories, precedence rules)
- record_feedback() with validation, atomicity, timestamp handling
- query_recommendations() with confidence sorting, fallback logic
- get_agent_stats() with filtered results and edge cases
- classify_feature_type() with keyword matching and fallback
- aggregate_feedback() with month bucketing and data preservation
- cleanup_old_data() with expiration and aggregation
- Error handling: Invalid inputs, corrupted state files, missing data
- Atomic writes and crash recovery
- Concurrent access and lock management

Integration Tests (18 tests):
- End-to-end feedback workflow (record to query to recommend)
- Data persistence across restarts
- Feature type classification in real scenarios
- Confidence score accuracy across data volumes
- Aggregation correctness (90-day retention, month bucketing)
- Concurrent record_feedback calls
- Cleanup effectiveness (pruning + aggregation)
- Performance benchmarks (query speed, data size management)
- Fallback routing when primary recommendation unavailable

**Version History**:
- v1.0.0 (2026-01-02) - Initial release with intelligent agent routing (Issue #191)

**Dependencies**:
- Standard library: json, pathlib, typing, datetime, threading, tempfile, os
- Internal: path_utils, validation, audit_logging

**Files Added**:
- plugins/autonomous-dev/lib/agent_feedback.py (946 lines)
- tests/unit/lib/test_agent_feedback.py (1,241 lines, 55 tests)
- tests/integration/test_agent_feedback_integration.py (617 lines, 18 tests)

**Files Modified**:
- plugins/autonomous-dev/config/install_manifest.json - Added agent_feedback.py to lib section

---
100 percent compatible - new library for feedback-driven agent routing without affecting existing workflows. Optional integration point for planner optimization.

---

## 88. memory_relevance.py (287 lines, v1.0.0 - Issue #192)

Purpose: TF-IDF-based relevance scoring for cross-session memories enabling intelligent retrieval of contextually relevant memories from previous sessions.

Problem: Memory injection needs intelligent filtering to avoid context bloat. Too many irrelevant memories waste tokens; too few memories reduce context continuity. No built-in relevance scoring.

Solution: TF-IDF (Term Frequency-Inverse Document Frequency) scoring system that:
1. Extracts keywords from query using stopword removal
2. Calculates relevance scores between query and memory content
3. Applies recency boost to favor recent memories
4. Filters low-relevance memories using threshold (configurable)
5. Returns ranked memories sorted by relevance score (highest first)

Key Features:

1. Keyword Extraction:
   - Extracts keywords from text using simple TF-IDF tokenization
   - Removes stopwords (common words like the, and, to)
   - Case-insensitive matching
   - Returns sorted list of unique keywords

2. Relevance Scoring:
   - TF-IDF formula: overlap_ratio * recency_boost
   - overlap_ratio: Count of matching keywords / total keywords in query
   - Recency boost: 1.0 + (days_old / 30) up to 1.3 max bonus
   - Range: 0.0 (no match) to 1.3 (perfect match + recent)
   - Timestamp-aware (expects ISO 8601 format)

3. Memory Ranking:
   - Sorts memories by relevance score (descending)
   - Filters memories below threshold (default 0.3)
   - Preserves original memory structure with added relevance_score
   - Returns empty list if no matches meet threshold

4. Threshold Filtering:
   - Default threshold: 0.3 (allows partial matches)
   - Configurable per call via threshold parameter
   - High thresholds (0.7+) only include high-relevance memories
   - Low thresholds (0.1) include most memories

Public API:

Key functions:
- extract_keywords(text: str) - Extract keywords from text
- calculate_relevance(query: str, memory_text: str, timestamp: str) - Calculate relevance score between query and memory
- rank_memories(query: str, memories: List, threshold: float) - Rank and filter memories by relevance

Constants:

- STOPWORDS - Set of common English stopwords
- RECENCY_BOOST_MAX = 1.3 - Maximum boost for recent memories
- RECENCY_BOOST_SCALE = 30 - Days to reach max boost
- DEFAULT_THRESHOLD = 0.3 - Minimum relevance score

Integration Points:

1. Memory Injection: Used by auto_inject_memory.py to filter relevant memories
2. Formatting: Ranked memories passed to memory_formatter.py for token-aware formatting
3. SessionStart Hook: Called during memory injection at session start

Test Coverage (32 tests):

Unit Tests:
- extract_keywords() with various text inputs, stopword filtering
- calculate_relevance() with exact/partial/no matches, timestamp variations
- rank_memories() with threshold filtering, sorting, edge cases
- Recency boost calculation and max limits
- Empty/None input handling
- Performance benchmarks for keyword extraction

Version History:
- v1.0.0 (2026-01-02) - Initial release with TF-IDF relevance scoring (Issue #192)

Dependencies:
- Standard library: datetime, typing

Files Added:
- plugins/autonomous-dev/lib/memory_relevance.py (287 lines)
- tests/unit/lib/test_memory_relevance.py (test suite)

---
100 percent compatible - new library for intelligent memory filtering without affecting existing code.

---

## 89. memory_formatter.py (261 lines, v1.0.0 - Issue #192)

Purpose: Token-aware formatting for memories with budget constraints enabling cost-effective memory injection while preventing context bloat.

Problem: Memory injection must respect token budget to prevent context bloat. No built-in token counting or budget-aware formatting. Memories must be formatted for readability with markdown structure.

Solution: Formatting system that:
1. Counts tokens using character-based estimation (accurate within 10%)
2. Formats individual memories with metadata and structure
3. Formats memory blocks with budget awareness
4. Truncates memories when budget exceeded (prioritizes high-relevance)
5. Adds markdown headers and structure for readability

Key Features:

1. Token Counting:
   - Character-based estimation: tokens approx equals character_count / 4
   - Fast estimation (no external models needed)
   - Accurate within 5-10% for typical text
   - Handles edge cases (empty strings, unicode)

2. Memory Block Formatting:
   - Markdown format with metadata header
   - Relevance score displayed prominently
   - Timestamp for temporal context
   - Content with proper line breaks
   - Example: Relevance: 0.85 | 2026-01-02 with content

3. Budget-Aware Formatting:
   - Respects max_tokens constraint
   - Prioritizes high-relevance memories when budget constrained
   - Graceful truncation (shows ... if truncated)
   - Returns formatted markdown block with headers

4. Token Budgeting:
   - Default budget: 500 tokens
   - Configurable per call
   - Includes header/footer tokens in budget calculation
   - Reports actual tokens used

Public API:

Key functions:
- count_tokens(text: str) - Estimate tokens in text
- format_memory_block(memory: Dict) - Format single memory for display
- format_memories_with_budget(memories: List, max_tokens: int) - Format all memories within token budget

Constants:

- TOKENS_PER_CHAR = 4 - Assumed characters per token
- HEADER_TOKENS = 20 - Overhead for markdown headers
- DEFAULT_MAX_TOKENS = 500 - Default budget
- TRUNCATION_MARKER = ... - Indicator of truncated content

Integration Points:

1. Memory Injection: Used by auto_inject_memory.py to format memories
2. Relevance Scoring: Takes output from memory_relevance.py (ranked memories)
3. SessionStart Hook: Formats memories before prompt injection

Test Coverage (28 tests):

Unit Tests:
- count_tokens() with various text lengths, unicode, special chars
- format_memory_block() with all metadata fields, missing fields
- format_memories_with_budget() with budget limits, priority sorting
- Truncation behavior at budget limits
- Edge cases: Empty memories, zero budget, single memory
- Performance benchmarks for formatting speed

Version History:
- v1.0.0 (2026-01-02) - Initial release with token-aware formatting (Issue #192)

Dependencies:
- Standard library: typing

Files Added:
- plugins/autonomous-dev/lib/memory_formatter.py (261 lines)
- tests/unit/lib/test_memory_formatter.py (test suite)

---
100 percent compatible - new library for efficient memory formatting without affecting existing code.

---

## 90. auto_inject_memory.py (9,089 lines, v1.0.0 - Issue #192)

Purpose: Auto-inject relevant memories at SessionStart enabling cross-session context continuity for architectural decisions, blockers, and patterns.

Problem: Agents have no memory between sessions. Architectural decisions, blockers, and patterns must be re-explained. Manual context recovery is slow and error-prone. SessionStart lacks mechanism to inject persistent context.

Solution: SessionStart hook that:
1. Loads memories from .claude/memories/session_memories.json
2. Ranks memories by relevance to current task (TF-IDF)
3. Formats memories within token budget (default: 500)
4. Injects formatted memories into initial prompt as markdown context
5. Environment variable control (MEMORY_INJECTION_ENABLED, default false)

Key Features:

1. Memory Loading:
   - Loads from .claude/memories/session_memories.json
   - Graceful degradation if file missing (logs info, continues)
   - Validates JSON structure before processing
   - Handles corrupted memory files safely

2. Relevance Ranking:
   - Uses TF-IDF scoring to rank memories by relevance
   - Recency boost favors recent memories (1-30 days)
   - Threshold filtering (default: 0.7) removes low-relevance memories
   - Configurable via MEMORY_RELEVANCE_THRESHOLD env var

3. Token Budget Enforcement:
   - Default budget: 500 tokens
   - Configurable via MEMORY_INJECTION_TOKEN_BUDGET env var
   - Prioritizes high-relevance memories when budget constrained
   - Graceful truncation if over budget

4. Prompt Injection:
   - Injects formatted memories into prompt as markdown block
   - Placed at top of prompt for visibility
   - Includes Relevant Context from Previous Sessions header
   - Clean markdown formatting with relevance scores

5. Environment Variable Control:
   - MEMORY_INJECTION_ENABLED (default: false) - Enable/disable injection
   - MEMORY_INJECTION_TOKEN_BUDGET (default: 500) - Max tokens for memories
   - MEMORY_RELEVANCE_THRESHOLD (default: 0.7) - Min relevance score

Public API:

Key functions:
- inject_memories_into_prompt(original_prompt: str, project_root: Path, max_tokens: int) - Inject memories into prompt
- should_inject_memories() - Check if injection enabled
- load_relevant_memories(query: str, project_root: Path, threshold: float) - Load and rank relevant memories

Integration Points:

1. SessionStart Hook: Triggered automatically when new session/conversation starts
2. Memory Layer: Reads memories from memory_layer.py storage
3. Relevance Scoring: Uses memory_relevance.py for ranking
4. Formatting: Uses memory_formatter.py for token-aware formatting
5. Prompt Modification: Modifies initial prompt before agent sees it

Configuration:

Environment variables (set in .env or shell):
- MEMORY_INJECTION_ENABLED=true - Enable memory injection (default: false)
- MEMORY_INJECTION_TOKEN_BUDGET=1000 - Max tokens (default: 500)
- MEMORY_RELEVANCE_THRESHOLD=0.5 - Min score (default: 0.7)

Test Coverage (36 tests):

Unit Tests:
- inject_memories_into_prompt() with various scenarios
- should_inject_memories() with env var states
- load_relevant_memories() with query matching
- Prompt injection formatting
- Memory file loading and validation
- Edge cases: Missing files, corrupted JSON, empty memories
- Performance benchmarks for injection speed

Version History:
- v1.0.0 (2026-01-02) - Initial release with SessionStart memory injection (Issue #192)

Dependencies:
- memory_layer.py - Memory persistence
- memory_relevance.py - Relevance scoring
- memory_formatter.py - Token-aware formatting
- path_utils.py - Path detection
- validation.py - Input validation

Files Added:
- plugins/autonomous-dev/lib/auto_inject_memory.py (9,089 lines)
- tests/unit/lib/test_auto_inject_memory.py (test suite)
- tests/integration/test_auto_inject_memory_integration.py (test suite)

---
100 percent compatible - new SessionStart hook for optional memory injection without affecting existing workflows.


---

## 91. feature_flags.py (230 lines, v1.0.0 - Issue #193)

**Purpose**: Configuration management for optional features with graceful degradation enabling selective feature control without code changes.

**Problem**: Features like conflict_resolver and auto_git_workflow should be configurable. Users need ability to opt-out of features without modifying code. Configuration should have sensible defaults and graceful failure modes.

**Solution**: Feature flag system that:
1. Loads configuration from .claude/feature_flags.json (optional)
2. Defaults all features to ENABLED (opt-out model)
3. Provides graceful degradation for missing/invalid configs
4. Prevents path traversal attacks via validate_path()
5. Has built-in defaults for all known features

**Key Features**:

1. Feature Flag Loading:
   - Loads from .claude/feature_flags.json
   - Opt-out model (all features enabled by default)
   - Missing file returns empty dict (all features enabled)
   - Invalid JSON returns empty dict (graceful degradation)

2. Default Behaviors:
   - conflict_resolver: enabled=true, confidence_threshold=0.8, security_requires_manual=true
   - auto_git_workflow: enabled=true, auto_push=false, auto_pr=false

3. Security:
   - Path validation via validate_path() (CWE-22)
   - No arbitrary code execution
   - JSON parsing with error handling
   - Graceful fallback on errors

4. Configuration File Format:
   - Location: .claude/feature_flags.json
   - Format: JSON with feature names as keys
   - Structure: {"feature_name": {"enabled": true, "key": "value"}}

**Public API**:

Key functions:
- is_feature_enabled(feature_name: str) -> bool - Check if feature is enabled
- get_feature_config(feature_name: str) -> Dict - Get complete feature configuration
- get_default_flags() -> Dict - Get all default flags
- _load_feature_flags() -> Dict - Load flags from configuration file (internal)
- _get_feature_flags_path() -> Optional[Path] - Get path to flags file (internal)
- _find_project_root() -> Optional[Path] - Find project root (internal)

**Configuration**:

Feature Flags File (.claude/feature_flags.json):
```json
{
  "conflict_resolver": {
    "enabled": true,
    "confidence_threshold": 0.8,
    "security_requires_manual": true
  },
  "auto_git_workflow": {
    "enabled": true,
    "auto_push": false,
    "auto_pr": false
  }
}
```

Default Behavior:
- Missing file = all features enabled
- Missing feature = enabled
- Invalid JSON = all features enabled
- Read errors = all features enabled

**Integration Points**:

1. Conflict Resolver: worktree_conflict_integration.py checks conflict_resolver flag
2. Git Automation: auto_git_workflow hook checks auto_git_workflow flag
3. Worktree Manager: merge_worktree() honors conflict_resolver configuration
4. Feature Control: Any system can check is_feature_enabled() before executing

**Test Coverage**:

Unit Tests:
- is_feature_enabled() with file present/missing/corrupted
- get_feature_config() with various configurations
- Default flag loading
- Path validation (CWE-22 prevention)
- Graceful degradation for missing/invalid files
- Edge cases: Empty flags, wrong JSON structure

**Version History**:
- v1.0.0 (2026-01-02) - Initial release for conflict resolver integration (Issue #193)

**Dependencies**:
- security_utils.py - Path validation
- Standard library: json, pathlib, typing

**Files Added**:
- plugins/autonomous-dev/lib/feature_flags.py (230 lines)
- tests/unit/lib/test_feature_flags.py (test suite)

---
100 percent compatible - new optional configuration system without affecting existing features.

---

## 92. worktree_conflict_integration.py (387 lines, v1.0.0 - Issue #193)

**Purpose**: Glue layer integrating AI-powered conflict resolution into worktree workflow with security detection and confidence thresholds enabling automatic merge conflict handling.

**Problem**: /worktree --merge conflicts are 100% manual. Users must edit files, understand conflict markers, resolve manually. This blocks automated workflows and requires human intervention. No way to automatically suggest resolutions or enforce security reviews.

**Solution**: Integration system that:
1. Detects merge conflicts from git output
2. Triggers AI resolution via conflict_resolver.py
3. Enforces confidence thresholds (0.8 default)
4. Requires manual review for security files
5. Provides three-tier escalation strategy
6. Integrates with worktree_manager.merge_worktree()

**Key Features**:

1. Conflict Detection:
   - Parses git merge output for conflict markers
   - Detects files with <<<<<<< or ======= or >>>>>>>
   - Returns list of conflicted file paths

2. Security Detection:
   - Detects security-related files by pattern
   - Patterns: security_*.py, credentials.py, secrets.py, *.key, *.pem, *.crt
   - Path patterns: /security/, /credentials/, /secrets/
   - Forces manual review regardless of confidence

3. Confidence Thresholds:
   - AUTO_COMMIT_THRESHOLD = 0.8 (80%)
   - High confidence (>=0.8) + not security = auto-commit
   - Medium confidence (0.6-0.8) = suggest but manual review
   - Low confidence (<0.6) = fallback to manual
   - Security files always require manual review

4. Three-Tier Escalation:
   - Tier 1: Auto-resolve and auto-commit (high confidence, not security)
   - Tier 2: Suggest resolution, require manual approval (medium confidence or security file)
   - Tier 3: Fallback to manual merge (low confidence or AI error)

5. Feature Flag Integration:
   - Checks conflict_resolver feature flag
   - Returns empty results if feature disabled
   - Graceful degradation if API key missing

**Public API**:

Key functions:
- resolve_worktree_conflicts(conflict_files: List[str], api_key: Optional[str]) -> List[ConflictResolutionResult] - Resolve multiple files
- should_auto_commit(result: ConflictResolutionResult) -> bool - Check if should auto-commit
- get_resolution_confidence(result: ConflictResolutionResult) -> float - Extract confidence score
- detect_conflicts_in_output(git_output: str) -> List[str] - Parse git output for conflicts
- has_conflict_markers(file_path: str) -> bool - Check if file has conflict markers
- is_security_related(file_path: str) -> bool - Detect security files

**Configuration**:

Feature Flags:
- conflict_resolver feature flag (must be enabled)

Environment Variables:
- ANTHROPIC_API_KEY - Required for AI resolution

Constants:
- AUTO_COMMIT_THRESHOLD = 0.8 - Confidence threshold for auto-commit

**Security**:

1. Path Validation:
   - All file paths validated via validate_path() (CWE-22)
   - Rejects relative paths with ..
   - Rejects symlinks

2. Security File Detection:
   - Strict pattern matching (avoids false positives)
   - Requires manual review for security files
   - Always requires manual review regardless of confidence

3. API Key Handling:
   - Read from environment only (never logged)
   - Graceful failure if missing
   - Returns empty results if missing

4. Audit Logging:
   - All resolutions logged via audit_log()
   - All errors logged with context
   - Non-sensitive information only

5. Error Handling:
   - Path validation errors handled gracefully
   - Missing API key returns empty results
   - Resolution failures fallback to manual
   - Missing dependencies handled safely

**Integration Points**:

1. Worktree Manager: Called by merge_worktree(auto_resolve=True)
2. Conflict Resolver: Calls resolve_conflicts() for each file
3. Feature Flags: Checks is_feature_enabled('conflict_resolver')
4. Git Automation: Results feed into auto-commit decision

**Test Coverage**:

Unit Tests:
- is_security_related() with various patterns
- detect_conflicts_in_output() with git merge output
- has_conflict_markers() with conflict marker detection
- resolve_worktree_conflicts() with single/multiple files
- should_auto_commit() with confidence thresholds
- get_resolution_confidence() with valid/missing resolutions
- Path validation and error handling
- Graceful degradation scenarios

Integration Tests:
- End-to-end merge with conflict resolution
- Security file detection and manual review enforcement
- Feature flag integration
- Error scenarios (missing API key, disabled feature)

**Version History**:
- v1.0.0 (2026-01-02) - Initial release integrating conflict resolver into worktree (Issue #193)

**Dependencies**:
- conflict_resolver.py (Issue #183) - AI resolution logic
- feature_flags.py - Feature configuration
- security_utils.py - Path validation and audit logging
- path_utils.py - Dynamic path detection
- Standard library: json, re, subprocess, pathlib, typing

**Files Added**:
- plugins/autonomous-dev/lib/worktree_conflict_integration.py (387 lines)
- tests/unit/lib/test_worktree_conflict_integration.py (test suite)
- tests/integration/test_worktree_merge_with_conflicts.py (integration tests)

---
100 percent compatible - optional integration layer that preserves existing /worktree --merge behavior when disabled or on errors.


## 67. research_persistence.py (700 lines, v1.0.0 - Issue #196)

**Purpose**: Auto-save research findings to docs/research/ with frontmatter metadata and caching, enabling research reuse across sessions and features without duplication.

**Problem**: Research findings are lost when conversation clears with /clear. No caching mechanism for repeated research topics. No centralized research knowledge base. Manual research duplication across features wastes time and introduces inconsistency.

**Solution**: Create research_persistence.py library providing save/load functions, age-based cache checking, and automatic index generation for research catalog.

**Key Features**:

1. **Research Saving** (save_research):
   - Saves to docs/research/TOPIC_NAME.md (SCREAMING_SNAKE_CASE naming)
   - YAML frontmatter: topic, created, updated, sources
   - Markdown content: findings plus automatically generated source links
   - Atomic write pattern (temp file plus replace) for safe concurrent access
   - Preserves created timestamp on updates

2. **Cache Checking** (check_cache):
   - Returns path if recent research exists
   - Age-based checking: max_age_days parameter (default: 30 days)
   - Fast path: file existence plus stat check (O(1))

3. **Research Loading** (load_cached_research):
   - Loads file and parses YAML frontmatter
   - Returns dict with: topic, created, updated, sources, content
   - Handles malformed files gracefully (returns None)

4. **Index Generation** (update_index):
   - Scans all .md files in docs/research/ (except README.md)
   - Generates README.md with research catalog table
   - Columns: Topic, Created, Sources, File

5. **Topic to Filename** (topic_to_filename):
   - Converts JWT Authentication to JWT_AUTHENTICATION.md
   - SCREAMING_SNAKE_CASE naming
   - Sanitizes special characters and truncates to filesystem limits

**Public API**:

Key functions:
- save_research(topic: str, findings: str, sources: List[str]) -> Path
- check_cache(topic: str, max_age_days: int = 30) -> Optional[Path]
- load_cached_research(topic: str) -> Optional[Dict[str, Any]]
- update_index() -> Path
- topic_to_filename(topic: str) -> str

Custom Exception:
- ResearchPersistenceError - Raised on validation/IO errors

**Security Features**:

1. **Atomic Write Pattern**: Temp file plus atomic rename for safe concurrent access
2. **Path Traversal Prevention (CWE-22)**: Sanitized filenames, validated paths
3. **Symlink Rejection (CWE-59)**: Via validate_session_path()
4. **Input Validation**: Topic, findings, sources validation
5. **Error Handling**: Disk full (ENOSPC), permission errors handled gracefully

**Integration with Path Utils**:

- Uses get_research_dir() from path_utils.py (NEW in Issue #196)
- Portable path detection (works from any directory)
- Creates docs/research/ with safe permissions (0o755)

**Configuration**:

Constants:
- Cache age: max_age_days parameter (default: 30 days)
- Filename truncation: 252 chars max (255 - 3 for .md)
- Permissions: 0o644 for research files, 0o755 for directories

**Dependencies**:

Standard Library:
- os - temp file creation, write operations
- re - topic sanitization regex
- tempfile - atomic write pattern
- datetime - timestamp generation
- pathlib - path operations
- typing - type hints

Project Dependencies:
- path_utils.py - get_research_dir() function
- validation.py - validate_session_path() function

**Usage Examples**:

Save research with metadata and sources:
```
from research_persistence import save_research
path = save_research(
    topic=JWT Authentication,
    findings=## Key Findings: 1. JWT is stateless,
    sources=[https://jwt.io]
)
```

Check cache before researching:
```
from research_persistence import check_cache
cached_path = check_cache(JWT Authentication, max_age_days=30)
if cached_path:
    print(Cache hit, use existing research)
```

Load cached research:
```
from research_persistence import load_cached_research
data = load_cached_research(JWT Authentication)
if data:
    print(data[content])
```

Update research catalog:
```
from research_persistence import update_index
readme_path = update_index()
```

**Test Coverage**:

Unit Tests (50+ test cases):
- topic_to_filename conversion (SCREAMING_SNAKE_CASE)
- save_research function (file creation, frontmatter, atomic writes)
- check_cache function (age-based checking)
- load_cached_research function (parsing, error handling)
- update_index function (catalog generation)
- Frontmatter parsing (YAML validation)
- Security validation (CWE-22, CWE-59)
- Error handling (disk full, permissions, corruption)

Integration Tests:
- Save and load round-trip
- Multiple research files with index generation
- Cache hit/miss with age boundaries
- Cross-project portability

**Performance**:

Time Complexity:
- save_research(): O(n) where n = findings size
- check_cache(): O(1) file existence check
- load_cached_research(): O(n) where n = file size
- update_index(): O(m) where m = number of .md files

Typical Performance:
- save_research: less than 50ms for typical research
- check_cache: less than 5ms (file stat check)
- load_cached_research: less than 20ms for typical file
- update_index: less than 100ms for 50 research files

**Version History**:
- v1.0.0 (2026-01-03) - Initial release for research persistence (Issue #196)

**Files Added**:
- plugins/autonomous-dev/lib/research_persistence.py (700 lines)
- tests/unit/lib/test_research_persistence.py (1023 lines)

**Files Modified**:
- plugins/autonomous-dev/lib/path_utils.py - Added get_research_dir() function
- plugins/autonomous-dev/config/install_manifest.json - Added research_persistence.py to lib section

---
100 percent compatible - new optional library for research caching without affecting existing workflows.

## 93. comprehensive_doc_validator.py (708 lines, v1.0.0 - Issue #198)

**Purpose**: Validate cross-references between documentation files to prevent documentation drift and ensure accuracy.

**Problem**: Documentation gets out of sync with code during development. Commands listed in README may not exist in code. Features listed in PROJECT.md may not be implemented. Code examples may have wrong API signatures. No systematic validation catches drift until manual reviews, causing user confusion.

**Solution**: Comprehensive documentation validator with four validation categories (command exports, project features, code examples, counts) plus auto-fix engine for safe patterns. Integrates into /auto-implement pipeline via doc-master agent.

**Key APIs**:

**DataClasses**:
- ValidationIssue: Represents single validation issue
  - category: str - Issue category (command, feature, example, count)
  - severity: str - Issue severity (error, warning, info)
  - message: str - Human-readable description
  - file_path: str - Path to file with issue
  - line_number: int - Line number (0 if unknown)
  - auto_fixable: bool - Whether issue can be auto-fixed safely
  - suggested_fix: str - Suggested fix description

- ValidationReport: Comprehensive validation report
  - issues: List[ValidationIssue] - All issues found
  - has_issues: bool (property) - Whether any issues found
  - has_auto_fixable: bool (property) - Whether any can be auto-fixed
  - has_manual_review: bool (property) - Whether any require manual review
  - auto_fixable_issues: List[ValidationIssue] (property) - Filtered auto-fixable list
  - manual_review_issues: List[ValidationIssue] (property) - Filtered manual review list

**Main Class**:
- ComprehensiveDocValidator:
  - __init__(repo_root: Path, batch_mode: bool = False) - Initialize validator
  - validate_all() -> ValidationReport - Run all validation checks
  - validate_command_exports() -> List[ValidationIssue] - Validate README vs commands/
  - validate_project_features() -> List[ValidationIssue] - Validate PROJECT.md SCOPE vs code
  - validate_code_examples() -> List[ValidationIssue] - Validate API signatures in docs
  - auto_fix_safe_patterns(issues: List[ValidationIssue]) -> int - Auto-fix safe patterns

**Validation Categories**:

1. **Command Export Validation** (validate_command_exports):
   - Scans plugins/autonomous-dev/commands/ for all command files
   - Extracts command names from filenames and docstrings
   - Checks each command has entry in plugins/autonomous-dev/README.md
   - Detects missing command entries (error severity)
   - Detects orphaned command files with no README entries (warning severity)
   - Auto-fix: Generates markdown snippet for missing entries

2. **Project Feature Validation** (validate_project_features):
   - Parses PROJECT.md SCOPE (In Scope) section
   - Extracts implemented features from code files and agents
   - Detects features in PROJECT.md but not implemented (warning severity)
   - Detects implemented features not in PROJECT.md (error severity)
   - Auto-fix: Adds missing features to PROJECT.md SCOPE with descriptions

3. **Code Example Validation** (validate_code_examples):
   - Extracts docstring examples from agent and skill files
   - Parses function signatures from actual code
   - Validates example signatures match implementation
   - Reports line numbers for manual review (warning severity, not auto-fixable)
   - Handles parse errors gracefully (reports as issues, doesn't crash)

4. **Count Validation** (implicit in validate_project_features):
   - Validates agent counts in CLAUDE.md (Agents: X)
   - Validates command counts (Commands: X)
   - Validates skill counts (Skills: X)
   - Detects count mismatches with actual implementation
   - Auto-fix: Updates numbers to match actual counts

**Auto-Fix Engine** (auto_fix_safe_patterns):
- Safely patches documentation with suggested fixes
- Only fixes safe patterns:
  - Missing command entries (appends to README)
  - Count mismatches (updates numbers in-place)
  - Not auto-fixed: feature descriptions, example signatures, complex logic
- Non-blocking: Never raises exceptions
- Logs all fixes to audit trail
- Returns count of successfully fixed issues

**Integration Points**:

- /auto-implement pipeline: Runs after doc-master agent completes
- doc-master agent: Calls ComprehensiveDocValidator before finalizing docs
- /sync command: Includes validation in sync workflow
- PreCommit hook: Optional validation gate before commit (VALIDATE_COMPREHENSIVE_DOCS=true)

**Configuration**:

Environment Variables:
- VALIDATE_COMPREHENSIVE_DOCS: Enable/disable validation (default: false)
  - Set to true in batch mode to enable validation
  - Set to false to disable validation checks

**Security Features**:

- Path validation via security_utils (CWE-22, CWE-59 prevention)
  - Validates all file paths before opening
  - Prevents path traversal attacks
  - Rejects symlinks via validate_path()
- Non-blocking design: Never raises exceptions
  - Logs issues safely
  - Continues validation on errors
  - Graceful error handling for corrupted files
- Input sanitization
  - Topic validation
  - Filename sanitization
  - Content encoding checks
- Audit logging
  - Logs all validation operations
  - Records fixes applied
  - Timestamps all events

**Performance**:

Time Complexity:
- validate_command_exports(): O(m) where m = number of command files
- validate_project_features(): O(n) where n = number of code files
- validate_code_examples(): O(n*k) where n = files, k = avg examples per file
- auto_fix_safe_patterns(): O(p) where p = issues to fix

Typical Performance:
- Small project (10 commands, 50 code files): 100-200ms total
- Medium project (50 commands, 500 code files): 500-1000ms total
- Large project (100+ commands): 1-3 seconds total

Scales linearly with codebase size.

**Files Added**:
- plugins/autonomous-dev/lib/comprehensive_doc_validator.py (708 lines)
- tests/unit/lib/test_comprehensive_doc_validator.py (1082 lines)

**Test Coverage**: 44 tests covering:
- Command export validation (8 tests): Missing entries, orphaned files, cross-reference checks
- Feature validation (10 tests): PROJECT.md SCOPE vs code, missing features, extra features
- Code example validation (12 tests): Docstring parsing, signature extraction, mismatch detection
- Count validation (6 tests): Agent/command/skill counts, detection of mismatches
- Auto-fix engine (5 tests): Safe pattern fixing, count updates, entry generation
- Report generation (3 tests): Filtering, property access, sorting

**Dependencies**:
- security_utils.py - Path validation and audit logging
- pathlib, ast, re, dataclasses - Standard library

**Backward Compatibility**: 100% compatible - new optional validator, does not affect existing validation or commands

**Version History**:
- v1.0.0 (2026-01-03) - Initial release for comprehensive documentation validation (Issue #198)


## 94. test_runner.py (396 lines, v1.0.0 - Issue #200)

**Purpose**: Autonomous test execution with structured results for debug-first enforcement.

**Problem**: Test execution during autonomous development requires structured results (pass/fail counts, duration) rather than just exit codes. Developers need quick verification without manual parsing.

**Solution**: test_runner library that executes pytest and returns TestResult dataclass with pass/fail counts, output, and duration.

### Features

- Execute pytest and return structured TestResult
- Run single test file or function
- Verify all tests pass (boolean check)
- Handle pytest not found gracefully
- Handle timeout gracefully
- Handle test failures gracefully
- Parse pytest output for counts and duration

### API Classes

#### TestResult

Structured test execution result with:
- passed: bool - All tests passed (no failures/errors)
- pass_count: int - Number of passing tests
- fail_count: int - Number of failing tests
- error_count: int - Number of errored tests
- output: str - Raw pytest output
- duration_seconds: float - Test execution time

### Functions

#### run_tests()

Execute pytest and return structured results.

Signature: run_tests(test_dir=None, pattern=None, verbose=False, coverage=False, timeout=300) -> TestResult

Parameters:
- test_dir: str - Directory to run tests in (default: current directory)
- pattern: str - Test file pattern to match
- verbose: bool - Use verbose output (-v)
- coverage: bool - Run with coverage
- timeout: int - Timeout in seconds (default: 300)

Returns: TestResult with test execution results

Example:
    from test_runner import run_tests
    result = run_tests()
    if result.passed:
        print(f'All {result.pass_count} tests passed!')

#### run_single_test()

Run a single test file or function.

Signature: run_single_test(test_path: str, timeout: int = 300) -> TestResult

Parameters:
- test_path: str - Path to test file or function
- timeout: int - Timeout in seconds

Returns: TestResult with test execution results

#### verify_all_tests_pass()

Quick boolean check if all tests pass.

Signature: verify_all_tests_pass(test_dir=None, timeout=300) -> bool

Parameters:
- test_dir: str - Directory to run tests in (default: current directory)
- timeout: int - Timeout in seconds

Returns: True if all tests passed, False otherwise

#### TestRunner class

Stateful test runner for repeated test execution.

Constructor: TestRunner(timeout=300, verbose=False)

Methods:
- run(test_dir=None, pattern=None, coverage=False) -> TestResult
- run_single(test_path: str) -> TestResult
- verify(test_dir=None) -> bool

### Error Handling

- pytest not found: Returns TestResult with passed=False, error_count=1
- Timeout: Returns TestResult with passed=False, error_count=1
- KeyboardInterrupt: Returns TestResult with passed=False, error_count=1
- Other errors: Returns TestResult with passed=False, error_count=1

**Performance**: O(1) - Delegates to pytest (scales with test count), Typical 10 test run: 100-500ms

**Dependencies**: subprocess, pathlib, dataclasses, re - Standard library

**Version History**: v1.0.0 (2026-01-03) - Initial release for debug-first enforcement (Issue #200)

---

## 95. code_path_analyzer.py (291 lines, v1.0.0 - Issue #200)

**Purpose**: Discover all code paths matching a pattern for debug-first enforcement and code discovery.

**Problem**: Developers need to find all locations matching a pattern (e.g., debug statements, TODOs, specific patterns). ripgrep/grep require external tools; need pure Python solution for portability.

**Solution**: code_path_analyzer library that searches project for regex patterns and returns CodePath objects with file location, line number, context.

### Features

- Find all locations matching a regex pattern
- Return CodePath objects with file_path, line_number, context, match_text
- Handle empty results gracefully
- Handle invalid patterns gracefully
- Search recursively in project directory
- Filter by file types (e.g., ["*.py", "*.md"])
- Exclude common directories (.git, __pycache__, node_modules, venv, build, dist)
- Support multiline context (N lines before/after match)

### API Classes

#### CodePath

A code path matching a search pattern with:
- file_path: str - Path to file containing match
- line_number: int - Line number of match (1-indexed)
- context: str - Surrounding lines for context
- match_text: str - The matched text

#### CodePathAnalyzer

Stateful code path analyzer for repeated searches.

Constructor: CodePathAnalyzer(project_root: str, exclude_patterns=None)

Methods:
- find(pattern, file_types=None, context_lines=3, case_sensitive=True) -> List[CodePath]

### Functions

#### find_all_code_paths()

Find all code paths matching a pattern.

Signature: find_all_code_paths(pattern, project_root=None, file_types=None, context_lines=3, case_sensitive=True, exclude_patterns=None) -> List[CodePath]

Parameters:
- pattern: str - Regex pattern to search for
- project_root: str - Root directory to search (default: current directory)
- file_types: List[str] - File type patterns like ["*.py", "*.md"] (None = all)
- context_lines: int - Number of lines before/after match to include
- case_sensitive: bool - Case-sensitive search (default: True)
- exclude_patterns: List[str] - Additional directories to exclude (beyond defaults)

Returns: List of CodePath objects for each match

Raises: ValueError if pattern is invalid regex, FileNotFoundError if project_root does not exist

### Default Exclude Patterns

- .git
- __pycache__
- node_modules
- venv
- .venv
- build
- dist
- .pytest_cache
- .mypy_cache

### Performance

- O(n) where n = number of files in project
- Excludes __pycache__, .git, node_modules by default
- Typical small project (100 files): 100-500ms
- Binary files and permission errors handled gracefully

**Dependencies**: pathlib, dataclasses, re - Standard library

**Version History**: v1.0.0 (2026-01-03) - Initial release for debug-first enforcement (Issue #200)

---

## 96. doc_update_risk_classifier.py (168 lines, v1.0.0 - Issue #204)

**Purpose**: Risk classification for documentation updates to support auto-apply workflow in doc-master agent.

**Problem**: Documentation updates should be auto-applied when they're safe (low-risk) but require user approval when they're strategic changes (high-risk). The doc-master agent needs to classify updates and make intelligent decisions about application.

**Solution**: doc_update_risk_classifier library that classifies documentation changes as LOW_RISK (auto-apply) or HIGH_RISK (requires approval).

### Features

- Classify documentation files by risk level
- LOW_RISK files: CHANGELOG.md, README.md, and PROJECT.md metadata
- HIGH_RISK sections: PROJECT.md GOALS, CONSTRAINTS, SCOPE, ARCHITECTURE
- Confidence scoring for classification (0.0 to 1.0)
- Pattern-based metadata detection (timestamps, component counts, compliance dates)
- Conservative defaults (unknown files classified as HIGH_RISK)

### API Classes

#### RiskLevel

Enumeration of risk levels:
- LOW_RISK: "low_risk" - Auto-apply without prompt
- HIGH_RISK: "high_risk" - Requires user approval

#### RiskClassification

Named tuple with classification result:
- risk_level: RiskLevel - Classified risk level
- confidence: float - Confidence score (0.0 to 1.0)
- reason: str - Human-readable reason for classification
- requires_approval: bool - Whether user approval is required

#### DocUpdateRiskClassifier

Stateless risk classifier for documentation updates.

Class attributes:
- LOW_RISK_FILES: Set[str] = {"CHANGELOG.md", "README.md"}
- HIGH_RISK_SECTIONS: Set[str] = {"GOALS", "CONSTRAINTS", "SCOPE", "ARCHITECTURE"}
- LOW_RISK_PATTERNS: List[str] - Regex patterns for metadata detection

Class methods:
- classify(file_path: str, changes: List[str]) -> RiskClassification - Classify a documentation update
- _classify_project_md(changes: List[str]) -> RiskClassification - Specialized PROJECT.md classification

### Functions

#### classify_doc_update()

Convenience function to classify a documentation update.

Signature: classify_doc_update(file_path: str, changes: List[str]) -> RiskClassification

Parameters:
- file_path: str - Path to the documentation file
- changes: List[str] - List of changed lines or content

Returns: RiskClassification with risk level, confidence, and reason

### Classification Rules

1. CHANGELOG.md: Always LOW_RISK (confidence 0.95)
2. README.md: Always LOW_RISK (confidence 0.95)
3. PROJECT.md with GOALS/CONSTRAINTS/SCOPE/ARCHITECTURE headers: HIGH_RISK (confidence 0.9)
4. PROJECT.md with metadata patterns (timestamps, counts): LOW_RISK (confidence 0.7-0.95)
5. PROJECT.md other content: HIGH_RISK conservative default (confidence 0.6)
6. Unknown files: HIGH_RISK conservative default (confidence 0.5)
7. Empty/None inputs: LOW_RISK with low confidence (0.3) for known files

### Metadata Patterns

Patterns matched for LOW_RISK classification in PROJECT.md:
- **Last Updated**: timestamp
- **Last Compliance Check**: timestamp
- **Last Validated**: timestamp
- Component version table rows (Skills, Commands, Agents, Hooks, Settings)

**Performance**: O(n) where n = number of changes (regex pattern matching)

**Dependencies**: enum, typing, pathlib, re - Standard library

**Version History**: v1.0.0 (2026-01-09) - Initial release for doc-master auto-apply (Issue #204)

---

## 97. doc_master_auto_apply.py (249 lines, v1.0.0 - Issue #204)

**Purpose**: Auto-apply documentation updates with intelligent approval workflow for doc-master agent.

**Problem**: The doc-master agent updates documentation but needs different handling for safe vs strategic changes. Interactive prompts for every change disrupt autonomous workflows; batch mode must skip high-risk changes.

**Solution**: doc_master_auto_apply library that applies LOW_RISK updates automatically and prompts for HIGH_RISK updates in interactive mode (or skips in batch mode).

### Features

- Auto-apply LOW_RISK documentation updates without user interaction
- Interactive approval workflow for HIGH_RISK updates
- Batch mode support (skip HIGH_RISK updates automatically)
- Comprehensive error handling and logging
- Applied/skipped update tracking
- Support for both object-based and parameter-based API calls

### API Classes

#### DocUpdate

Data class representing a documentation update:
- file_path: str - Path to the documentation file
- content: str - New content to write
- risk_classification: RiskClassification - Risk classification result

#### DocUpdateResult

Named tuple with update application result:
- applied: bool - Whether update was applied
- required_approval: bool - Whether update required approval
- user_approved: Optional[bool] - User approval decision (interactive mode only)
- message: str - Human-readable status message
- file_path: str - Path to the documentation file
- error: Optional[str] - Error message if application failed

#### DocUpdateApplier

Stateful applier for documentation updates.

Constructor: DocUpdateApplier(batch_mode: bool = False, auto_approve: bool = False)

Parameters:
- batch_mode: If True, skip HIGH_RISK updates instead of prompting
- auto_approve: If True, auto-approve all updates (testing only)

Methods:
- apply(update: DocUpdate) -> DocUpdateResult - Apply a single documentation update
- _write_update(update: DocUpdate) -> DocUpdateResult - Write update to disk
- skipped_updates: List[DocUpdate] - Property for skipped HIGH_RISK updates
- applied_updates: List[DocUpdateResult] - Property for successfully applied updates

### Functions

#### auto_apply_doc_update()

Convenience function to classify and apply a documentation update.

Signature: auto_apply_doc_update(
    update: Optional[DocUpdate] = None,
    file_path: Optional[str] = None,
    content: Optional[str] = None,
    changes: Optional[List[str]] = None,
    batch_mode: bool = False
) -> DocUpdateResult

Supports two call patterns:

1. Object-based: auto_apply_doc_update(update=DocUpdate(...), batch_mode=False)
2. Parameter-based: auto_apply_doc_update(file_path="...", content="...", changes=[...], batch_mode=False)

Parameters:
- update: Pre-built DocUpdate object
- file_path: Path to the documentation file
- content: New content to write
- changes: List of changed lines (for risk classification)
- batch_mode: If True, skip HIGH_RISK updates

Returns: DocUpdateResult with success status and action taken

#### apply_doc_updates_batch()

Apply multiple documentation updates in batch mode.

Signature: apply_doc_updates_batch(updates: List[DocUpdate], batch_mode: bool = True) -> List[DocUpdateResult]

Parameters:
- updates: List of DocUpdate objects to apply
- batch_mode: If True, skip HIGH_RISK updates (default: True)

Returns: List of DocUpdateResult for each update

### Workflow

1. **Classify**: Risk classifier determines risk level and confidence
2. **LOW_RISK**: Write immediately, return success
3. **HIGH_RISK in batch mode**: Log and skip, return skipped status
4. **HIGH_RISK in interactive mode**: Display warning, prompt user, apply if approved
5. **File system**: Create parent directories, write content, handle errors

### Error Handling

- File write failures: Returns DocUpdateResult with error details
- Invalid inputs: Returns error result with message
- Missing file paths: Creates parent directories automatically
- Permission errors: Returns error result

**Performance**: O(n) where n = size of content being written (file I/O dominated)

**Dependencies**: os, json, logging, pathlib, typing, dataclasses, datetime, doc_update_risk_classifier

**Version History**: v1.0.0 (2026-01-09) - Initial release for doc-master auto-apply (Issue #204)

---

## 98. auto_implement_pipeline.py (257 lines, v1.0.0 - Issue #204)

**Purpose**: Integration of project-progress-tracker into /auto-implement pipeline (Step 4.3).

**Problem**: The /auto-implement pipeline completes doc-master updates (Step 4.1) but doesn't update PROJECT.md with completion status, issue references, and timestamps. Users manually update progress tracking.

**Solution**: auto_implement_pipeline library that invokes project-progress-tracker after doc-master to update PROJECT.md automatically.

### Features

- Invoke project-progress-tracker after doc-master (Step 4.3)
- Update stage completion status in PROJECT.md
- Update issue references from GitHub issue number
- Update Last Updated timestamp with issue reference
- Graceful degradation if PROJECT.md not found
- Support for both legacy context dict and direct parameters
- Comprehensive error handling and result tracking

### API Classes

#### ProgressTrackerResult

Named tuple with progress tracker invocation result:
- success: bool - Whether invocation succeeded
- project_md_updated: bool - Whether PROJECT.md was modified
- error: Optional[str] - Error message if invocation failed
- updates_made: List[str] - List of updates applied (e.g., ["Stage status", "Issue #204 reference", "Last Updated timestamp"])

### Functions

#### invoke_progress_tracker()

Invoke project-progress-tracker after doc-master in the pipeline.

Signature: invoke_progress_tracker(
    issue_number: Optional[int] = None,
    stage: Optional[str] = None,
    workflow_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    doc_master_output: Optional[Dict[str, Any]] = None
) -> ProgressTrackerResult

Parameters:
- issue_number: GitHub issue number for reference
- stage: Current pipeline stage (e.g., "implementation_complete")
- workflow_id: Workflow identifier for tracking
- context: Legacy context dict with workflow_id, issue_number, changed_files
- doc_master_output: Output from doc-master step (optional, for context)

Returns: ProgressTrackerResult with success status and updates made

Supports both call patterns:
1. Direct args: invoke_progress_tracker(issue_number=204, stage="implementation_complete")
2. Legacy context: invoke_progress_tracker(context={"issue_number": 204, "stage": "implementation_complete"})

#### execute_step8_parallel_validation()

Execute Step 4.1 (parallel validation) with progress tracker integration.

Signature: execute_step8_parallel_validation(context: Dict[str, Any]) -> Dict[str, Any]

Parameters:
- context: Pipeline context with issue_number, stage, workflow_id

Returns: Dict with validation results including progress_tracker result

### PROJECT.md Updates

#### 1. Stage Status Update

Pattern: **Stage**: <value> or Current stage: <value>

Updates stage field to reflect current pipeline stage:
- alignment_check
- complexity_assessment
- research
- planning
- implementation
- implementation_complete
- parallel_validation
- git_automation
- context_clear

#### 2. Issue Reference Update

Pattern: **Last Updated**: YYYY-MM-DD (optional issue reference)

Adds or updates issue reference on Last Updated line:
- **Last Updated**: 2026-01-09 (Issue #204)

Checks for existing reference to avoid duplicates.

#### 3. Timestamp Update

Updates Last Updated timestamp to current date with optional issue reference:
- Pattern: **Last Updated**: YYYY-MM-DD
- Replacement: **Last Updated**: <today> (Issue #NNN) if issue_number provided

### Helper Functions

#### _find_project_md()

Find PROJECT.md in current project.

Checks locations:
- .claude/PROJECT.md
- PROJECT.md
- $CWD/.claude/PROJECT.md
- $CWD/PROJECT.md

Returns: Optional[Path] - Path to PROJECT.md or None if not found

#### _update_stage_status(content: str, stage: str) -> tuple[str, bool]

Update stage status in PROJECT.md.

Returns: (new_content, was_updated) tuple

#### _update_issue_reference(content: str, issue_number: int) -> tuple[str, bool]

Add or update issue reference in PROJECT.md.

Returns: (new_content, was_updated) tuple

#### _update_timestamp(content: str, issue_number: Optional[int] = None) -> tuple[str, bool]

Update Last Updated timestamp in PROJECT.md.

Returns: (new_content, was_updated) tuple

### Error Handling

- PROJECT.md not found: Returns success=False with error message
- File write failures: Returns success=False with error details
- Regex pattern not found: Gracefully skips update with no error
- Invalid date: Uses current date from datetime.now()

### Pipeline Integration

Step 4.3 of /auto-implement pipeline:
1. doc-master completes (Step 4.1)
2. invoke_progress_tracker() called with issue_number and stage
3. PROJECT.md updated with completion status
4. Results returned to pipeline
5. Pipeline continues to Step 4.4 (auto_git_workflow)

**Performance**: O(n) where n = size of PROJECT.md file (regex pattern matching)

**Dependencies**: logging, typing, pathlib, datetime, re - Standard library

**Version History**: v1.0.0 (2026-01-09) - Initial release for progress tracker integration (Issue #204)
