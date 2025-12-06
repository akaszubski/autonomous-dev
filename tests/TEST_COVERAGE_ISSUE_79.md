# Test Coverage for Issue #79: Dogfooding Bug Fix

**Issue**: Fix /auto-implement and /batch-implement stalling for 7+ hours
**Phase**: TDD Red Phase (tests written FIRST, all FAILING)
**Date**: 2025-12-07

## Overview

Comprehensive test suite for Issue #79 checkpoint integration and command portability fixes. All tests are currently FAILING - implementation has not started yet (TDD red phase).

## Test File Structure

```
tests/
├── unit/
│   └── lib/
│       └── test_agent_tracker_issue79.py (17 tests)
└── integration/
    ├── test_command_portability_issue79.py (12 tests)
    └── test_checkpoint_security_issue79.py (13 tests)
```

**Total Tests**: 42 tests across 3 files

## Test Categories

### 1. Unit Tests - AgentTracker Checkpoint Integration (17 tests)

**File**: `tests/unit/lib/test_agent_tracker_issue79.py`

**Class Method Tests (6 tests)**:
- `test_save_agent_checkpoint_method_exists` - Method exists as @classmethod
- `test_save_agent_checkpoint_signature` - Correct method signature
- `test_save_agent_checkpoint_uses_portable_paths` - Uses path_utils.get_project_root()
- `test_save_agent_checkpoint_creates_session_file` - Creates session file in PROJECT_ROOT
- `test_save_agent_checkpoint_from_subdirectory` - Works from any directory
- `test_save_agent_checkpoint_without_file_variable` - Works in heredoc context

**Graceful Degradation Tests (3 tests)**:
- `test_save_agent_checkpoint_handles_import_error` - Handles missing project root
- `test_save_agent_checkpoint_handles_permission_errors` - Non-blocking failures
- `test_save_agent_checkpoint_clear_error_message` - Clear error messages

**Security Tests (3 tests)**:
- `test_save_agent_checkpoint_validates_agent_name` - Path traversal prevention
- `test_save_agent_checkpoint_prevents_symlink_escape` - Symlink attack prevention
- `test_save_agent_checkpoint_validates_message_length` - Resource exhaustion prevention

**Integration Tests (3 tests)**:
- `test_save_agent_checkpoint_creates_valid_session_structure` - Valid JSON structure
- `test_save_agent_checkpoint_appends_to_existing_session` - Append logic works
- `test_save_agent_checkpoint_with_github_issue` - GitHub issue association

**Documentation Tests (2 tests)**:
- `test_all_agents_have_checkpoint_sections` - All 7 agents documented
- `test_checkpoint_examples_use_class_method` - Examples show correct pattern

### 2. Integration Tests - Command Portability (12 tests)

**File**: `tests/integration/test_command_portability_issue79.py`

**Auto-Implement Tests (4 tests)**:
- `test_auto_implement_checkpoint1_no_subprocess` - CHECKPOINT 1 uses library imports
- `test_auto_implement_checkpoint41_no_subprocess` - CHECKPOINT 4.1 uses library imports
- `test_auto_implement_uses_portable_paths` - Uses portable path detection
- `test_auto_implement_checkpoints_work_from_subdirectory` - Works from subdirectories

**Batch-Implement Tests (2 tests)**:
- `test_batch_implement_no_subprocess_calls` - No subprocess anti-pattern
- `test_batch_implement_uses_library_imports` - Uses library imports

**Pipeline-Status Tests (2 tests)**:
- `test_pipeline_status_no_subprocess` - No subprocess anti-pattern
- `test_pipeline_status_uses_library_imports` - Uses library imports

**Fresh Install Tests (2 tests)**:
- `test_no_hardcoded_developer_paths` - No hardcoded paths in commands
- `test_portable_path_detection_works_anywhere` - Works on any machine

**Dogfooding Tests (2 tests)**:
- `test_auto_implement_does_not_stall` - No 7+ hour stalls (timeout protection)
- `test_checkpoint_verification_finds_agent_tracker` - AgentTracker importable

### 3. Security Tests - Checkpoint Security (13 tests)

**File**: `tests/integration/test_checkpoint_security_issue79.py`

**Path Traversal Prevention (3 tests)**:
- `test_checkpoint_blocks_path_traversal_in_agent_name` - CWE-22 prevention
- `test_checkpoint_blocks_absolute_paths_in_agent_name` - Absolute path rejection
- `test_checkpoint_validates_session_dir_within_project` - Path validation

**Symlink Prevention (2 tests)**:
- `test_checkpoint_does_not_follow_symlink_outside_project` - CWE-59 prevention
- `test_checkpoint_resolves_symlinks_in_validation` - Path resolution

**Command Injection Prevention (2 tests)**:
- `test_checkpoint_does_not_use_shell_commands` - CWE-78 prevention
- `test_checkpoint_uses_pathlib_not_os_system` - Safe API usage

**File Permissions (2 tests)**:
- `test_checkpoint_files_have_restrictive_permissions` - 0o600 for files
- `test_checkpoint_session_dir_permissions` - 0o700 for directories

**Input Validation (4 tests)**:
- `test_checkpoint_validates_agent_name_length` - Max 255 chars
- `test_checkpoint_validates_agent_name_characters` - Alphanumeric + hyphen/underscore
- `test_checkpoint_validates_message_size` - Max 10KB
- `test_checkpoint_validates_github_issue_number` - Valid issue numbers

## Coverage by Implementation Phase

### Phase 1: Agent Checkpoint Integration (20 tests)
- Unit tests for `AgentTracker.save_agent_checkpoint()`
- Portable path detection
- Graceful degradation
- Session file structure
- GitHub issue association
- Agent documentation

### Phase 2: Remove Subprocess Anti-Pattern (6 tests)
- auto-implement.md checkpoint updates
- batch-implement.md library imports
- pipeline-status.md library imports

### Phase 3: Documentation (2 tests)
- Agent checkpoint sections
- Example code correctness

### Phase 4: Validation (14 tests)
- Fresh install portability
- Dogfooding workflow
- Security validation (5 CWE categories)
- Permission verification

## Security Coverage

**CWE Categories Tested**:
1. **CWE-22**: Path Traversal (6 tests)
2. **CWE-59**: Link Following (2 tests)
3. **CWE-78**: OS Command Injection (2 tests)
4. **Information Disclosure**: File Permissions (2 tests)
5. **Resource Exhaustion**: Input Validation (4 tests)

**Total Security Tests**: 16 tests across 5 vulnerability categories

## Acceptance Criteria Coverage

| Acceptance Criteria | Test Coverage | Status |
|---------------------|---------------|--------|
| All 7 agents save checkpoints via Python imports | `test_all_agents_have_checkpoint_sections` | FAILING |
| No subprocess anti-pattern in commands | `test_*_no_subprocess*` (6 tests) | FAILING |
| Portable paths work from any directory | `test_*_portable_paths*` (4 tests) | FAILING |
| Graceful degradation in user projects | `test_*_graceful*` (3 tests) | FAILING |
| Dogfooding works (plugin on itself) | `test_*_dogfooding*` (2 tests) | FAILING |
| Fresh install works on non-developer machine | `test_*_fresh_install*` (2 tests) | FAILING |
| No 7+ hour stalls | `test_auto_implement_does_not_stall` | FAILING |
| Clear error messages | `test_*_clear_error*` (1 test) | FAILING |
| All security tests pass | All security tests (16 tests) | FAILING |

**Total Coverage**: 9/9 acceptance criteria (100%)

## Expected Test Results (Red Phase)

All 42 tests should FAIL with these error patterns:

**Unit Tests**:
- `AttributeError: type object 'AgentTracker' has no attribute 'save_agent_checkpoint'`
- `AssertionError: AgentTracker.save_agent_checkpoint() method does not exist`

**Integration Tests**:
- `AssertionError: CHECKPOINT 1 still uses subprocess anti-pattern`
- `AssertionError: batch-implement.md still uses subprocess anti-pattern`
- `AssertionError: Commands contain hardcoded developer paths`

**Security Tests**:
- `AssertionError: Path traversal attack succeeded`
- `AssertionError: Checkpoint followed symlink outside project`
- `AssertionError: Session file has incorrect permissions`

## Running the Tests

**Run all Issue #79 tests**:
```bash
pytest tests/unit/lib/test_agent_tracker_issue79.py \
       tests/integration/test_command_portability_issue79.py \
       tests/integration/test_checkpoint_security_issue79.py \
       --tb=line -q -v
```

**Run by category**:
```bash
# Unit tests only
pytest tests/unit/lib/test_agent_tracker_issue79.py -v

# Integration tests only
pytest tests/integration/test_command_portability_issue79.py -v

# Security tests only
pytest tests/integration/test_checkpoint_security_issue79.py -v
```

**Run with coverage**:
```bash
pytest tests/unit/lib/test_agent_tracker_issue79.py \
       tests/integration/test_command_portability_issue79.py \
       tests/integration/test_checkpoint_security_issue79.py \
       --cov=plugins.autonomous_dev.lib.agent_tracker \
       --cov-report=term-missing
```

## Green Phase Criteria

Tests should pass after implementation completes:

1. **AgentTracker.save_agent_checkpoint()** implemented as @classmethod
2. **Commands updated** to use library imports (no subprocess)
3. **Portable paths** used everywhere (no hardcoded paths)
4. **Graceful degradation** implemented
5. **Security validation** for all inputs
6. **File permissions** set to 0o600/0o700
7. **Documentation** added to all 7 agent files
8. **No 7+ hour stalls** (dogfooding works)

## Test Execution Time

**Estimated**:
- Unit tests: ~5 seconds
- Integration tests: ~10 seconds
- Security tests: ~8 seconds
- **Total**: ~23 seconds

**Actual** (after implementation): TBD

## Notes

- Tests use minimal pytest verbosity (`--tb=line -q`) to prevent subprocess pipe deadlock (Issue #90)
- Timeout protection on dogfooding test (300s max, not 7+ hours)
- All tests use `tmp_path` fixture (no side effects on real filesystem)
- Security tests simulate real attack vectors
- Mock patches used for portable path detection to avoid filesystem dependencies

## Related Documentation

- GitHub Issue: #79
- Implementation Plan: (planner agent output)
- Research Findings: (researcher agent output)
- Security Audit: `docs/SECURITY_AUDIT_ISSUE_79.md` (to be created)
