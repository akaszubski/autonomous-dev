# PROJECT.md Auto-Update Feature - TDD Test Summary

**Date**: 2025-11-04
**Feature**: Automatic PROJECT.md progress updates via SubagentStop hook
**Status**: RED PHASE - All tests failing (as expected)

## Test Coverage Summary

**Total Tests Written**: 24 tests
**Current Status**: 24 FAILED (100% failure rate - expected for TDD red phase)
**Target Coverage**: 80%+ when implementation complete

## Test Categories

### 1. ProjectMdUpdater Class - Atomic Writes (4 tests)
- `test_atomic_write_creates_temp_file_first` - FAILED (ModuleNotFoundError)
  - Verifies temp file created before atomic rename
  - Security: Prevents partial/corrupted data visibility

- `test_backup_includes_timestamp` - FAILED (ModuleNotFoundError)
  - Verifies backup created with format: PROJECT.md.backup.YYYYMMDD-HHMMSS
  - Requirement: Traceability and rollback capability

- `test_symlink_detection_prevents_attack` - FAILED (ModuleNotFoundError)
  - Security: Rejects symlinks to prevent arbitrary file writes
  - Attack scenario: PROJECT.md -> /etc/passwd

- `test_path_traversal_blocked` - FAILED (ModuleNotFoundError)
  - Security: Blocks ../../etc/passwd style attacks
  - Validates paths are within project root

### 2. ProjectMdUpdater Class - Goal Updates (5 tests)
- `test_goal_progress_regex_replacement` - FAILED (ModuleNotFoundError)
  - Updates "Goal X: [Y%]" to "Goal X: [Z%]"
  - Preserves other goals unchanged

- `test_metric_value_update` - FAILED (ModuleNotFoundError)
  - Updates metric values in GOALS section
  - Example: "Features completed: 5" -> "Features completed: 6"

- `test_multiple_goals_updated_correctly` - FAILED (ModuleNotFoundError)
  - Batch updates for efficiency
  - Updates multiple goals in single operation

- `test_project_md_syntax_validation` - FAILED (ModuleNotFoundError)
  - Validates PROJECT.md structure after updates
  - Ensures GOALS section headers intact

- `test_merge_conflict_detection` - FAILED (ModuleNotFoundError)
  - Detects <<<<<<< HEAD markers
  - Prevents updates to conflicted files

### 3. SubagentStop Hook - Triggers (6 tests)
- `test_hook_triggers_only_on_doc_master` - FAILED (ModuleNotFoundError)
  - Hook runs only after doc-master completes
  - Other agents don't trigger PROJECT.md update

- `test_hook_requires_pipeline_complete` - FAILED (ModuleNotFoundError)
  - Checks all 7 agents completed successfully
  - Dependency: enforce_pipeline_complete.py passed

- `test_hook_invokes_progress_tracker` - FAILED (ModuleNotFoundError)
  - Invokes project-progress-tracker agent
  - Uses GenAI to assess progress

- `test_hook_parses_yaml_output` - FAILED (ModuleNotFoundError)
  - Parses YAML assessment from agent
  - Format: `assessment:\n  goal_1: 25\n  goal_2: 50`

- `test_hook_handles_agent_timeout` - FAILED (ModuleNotFoundError)
  - Graceful handling of 30s timeout
  - Doesn't block pipeline if assessment hangs

- `test_hook_rolls_back_on_failure` - FAILED (ModuleNotFoundError)
  - Restores from backup on update failure
  - Ensures data consistency

### 4. Integration Tests (3 tests)
- `test_auto_implement_updates_project_md` - FAILED (ModuleNotFoundError)
  - End-to-end workflow verification
  - 7 agents -> doc-master -> hook -> progress-tracker -> PROJECT.md update

- `test_handles_missing_project_md` - FAILED (ModuleNotFoundError)
  - Graceful handling when PROJECT.md doesn't exist
  - Logs warning, doesn't crash

- `test_handles_merge_conflicts` - FAILED (ModuleNotFoundError)
  - Skips update if conflict markers present
  - Preserves conflict markers for user resolution

### 5. Edge Cases (6 tests)
- `test_invalid_yaml_from_agent` - FAILED (ModuleNotFoundError)
  - Handles malformed YAML from progress-tracker
  - Returns None or empty dict gracefully

- `test_negative_progress_percentage` - FAILED (ModuleNotFoundError)
  - Rejects progress < 0%
  - Raises ValueError with clear message

- `test_progress_percentage_over_100` - FAILED (ModuleNotFoundError)
  - Rejects progress > 100%
  - Raises ValueError with clear message

- `test_concurrent_updates_to_project_md` - FAILED (ModuleNotFoundError)
  - Handles two /auto-implement pipelines running simultaneously
  - Last write wins (atomic rename ensures consistency)

- `test_empty_goals_section` - FAILED (ModuleNotFoundError)
  - Handles PROJECT.md with no goals
  - Returns False or None gracefully

- `test_malformed_goal_format` - FAILED (ModuleNotFoundError)
  - Skips goals not matching expected pattern
  - Doesn't crash on unexpected formats

## Security Requirements Tested

### CRITICAL
- Path traversal prevention (test_path_traversal_blocked)
- Symlink detection (test_symlink_detection_prevents_attack)
- Atomic file writes (test_atomic_write_creates_temp_file_first)

### HIGH
- Backup creation with timestamp (test_backup_includes_timestamp)
- Merge conflict detection (test_merge_conflict_detection)
- Rollback on failure (test_hook_rolls_back_on_failure)

### MEDIUM
- Syntax validation (test_project_md_syntax_validation)
- Input validation (test_negative_progress_percentage, test_progress_percentage_over_100)
- Concurrent update handling (test_concurrent_updates_to_project_md)

## Feature Requirements Tested

### Core Functionality
1. Hook triggers only after doc-master (test_hook_triggers_only_on_doc_master)
2. Requires pipeline completion (test_hook_requires_pipeline_complete)
3. Invokes progress-tracker agent (test_hook_invokes_progress_tracker)
4. Parses YAML output (test_hook_parses_yaml_output)
5. Updates PROJECT.md atomically (test_atomic_write_creates_temp_file_first)
6. Creates timestamped backups (test_backup_includes_timestamp)

### Error Handling
1. Agent timeout handling (test_hook_handles_agent_timeout)
2. Invalid YAML handling (test_invalid_yaml_from_agent)
3. Missing PROJECT.md handling (test_handles_missing_project_md)
4. Merge conflict handling (test_handles_merge_conflicts)
5. Rollback on failure (test_hook_rolls_back_on_failure)

### Goal Updates
1. Single goal updates (test_goal_progress_regex_replacement)
2. Multiple goal updates (test_multiple_goals_updated_correctly)
3. Metric updates (test_metric_value_update)
4. Validation percentages (test_negative_progress_percentage, test_progress_percentage_over_100)

## Implementation Files Required

Based on test imports, the following files need to be created:

### 1. `/plugins/autonomous-dev/lib/project_md_updater.py`
**Class**: `ProjectMdUpdater`
**Methods**:
- `__init__(self, project_file: Path)`
- `update_goal_progress(self, goal_name: str, percentage: int) -> bool`
- `update_metric(self, metric_name: str, value: int) -> bool`
- `update_multiple_goals(self, updates: Dict[str, int]) -> bool`
- `validate_syntax(self) -> Dict[str, Any]`
- `create_backup(self) -> Path`
- `_atomic_write(self, content: str) -> None`
- `_check_merge_conflicts(self, content: str) -> bool`

**Security Features**:
- Path validation (no symlinks, no traversal)
- Atomic writes (temp file + rename)
- Backup creation with timestamp
- Merge conflict detection

### 2. `/plugins/autonomous-dev/hooks/auto_update_project_progress.py`
**Functions**:
- `should_trigger_update(agent_name: str) -> bool`
- `check_pipeline_complete(session_file: Path) -> bool`
- `invoke_progress_tracker(timeout: int = 30) -> Optional[str]`
- `parse_agent_output(yaml_output: str) -> Optional[Dict]`
- `update_project_with_rollback(project_file: Path, updates: Dict) -> None`
- `run_hook(agent_name: str, session_file: Path, project_file: Path) -> None`

**Lifecycle Hook**: SubagentStop event handler

### 3. Modified Files
- `/plugins/autonomous-dev/agents/project-progress-tracker.md` - Add YAML output format
- `/scripts/agent_tracker.py` - Add SubagentStop lifecycle event support

## Next Steps (Implementation Phase)

1. **Create project_md_updater.py** - Library for atomic PROJECT.md updates
2. **Create auto_update_project_progress.py** - SubagentStop hook
3. **Update project-progress-tracker.md** - Add YAML output specification
4. **Update agent_tracker.py** - Add SubagentStop event
5. **Run tests again** - Verify tests pass (GREEN phase)
6. **Measure coverage** - Ensure 80%+ coverage achieved

## TDD Verification

**RED Phase Status**: COMPLETE
- All 24 tests written BEFORE implementation
- All 24 tests failing due to ModuleNotFoundError (expected)
- Tests describe requirements clearly
- Tests cover security, functionality, edge cases
- Ready for GREEN phase (implementation)

**Test Execution Command**:
```bash
source .venv/bin/activate
python -m pytest tests/test_project_progress_update.py -v --tb=short
```

**Expected Output**: 24 FAILED (ModuleNotFoundError) - CORRECT for TDD red phase

## Test Quality Metrics

- **Clear test names**: All tests use descriptive names (test_what_is_being_tested)
- **Arrange-Act-Assert pattern**: All tests follow AAA structure
- **One assertion per test**: Most tests focus on single behavior
- **Mock external dependencies**: subprocess, file I/O properly mocked
- **Security-first**: Path validation, symlinks, atomic writes all tested
- **Edge cases covered**: Empty sections, malformed data, concurrent updates

## Coverage Goals

When implementation complete, expect:
- **project_md_updater.py**: 85%+ coverage
- **auto_update_project_progress.py**: 85%+ coverage
- **Security paths**: 100% coverage (critical)
- **Error handling**: 90%+ coverage
- **Happy paths**: 100% coverage

---

**Status**: Ready for implementation phase. All tests failing as expected (TDD red phase complete).
