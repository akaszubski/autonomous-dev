# Implementation Checklist - Issue #93: Add Auto-Commit to Batch Workflow

**Date**: 2025-12-06
**Issue**: #93 (Add auto-commit to batch workflow)
**Agent**: test-master → implementer (next)
**Phase**: TDD Red → TDD Green transition
**Tests Written**: 55 tests (all currently SKIPPED - awaiting implementation)

---

## Current Status

**TDD Phase**: RED (tests written, implementation pending)

**Test Execution Status**:
- `tests/unit/test_batch_state_git_tracking.py`: SKIPPED (record_git_operation not found)
- `tests/unit/lib/test_batch_git_integration.py`: SKIPPED (in_batch_mode parameter not found)
- `tests/integration/test_batch_git_workflow.py`: SKIPPED (record_git_operation not found)
- `tests/integration/test_batch_git_edge_cases.py`: SKIPPED (in_batch_mode parameter not found)

**Total Tests**: 55 tests ready to verify implementation

---

## Implementation Tasks

### 1. Batch State Manager Schema Changes

**File**: `plugins/autonomous-dev/lib/batch_state_manager.py`

#### 1.1 Update BatchState Dataclass
- [ ] Add `git_operations: Dict[int, Dict[str, Any]] = field(default_factory=dict)` field
- [ ] Update docstring to document git_operations field structure
- [ ] Ensure field included in `to_dict()` method

**Expected Structure**:
```python
git_operations = {
    0: {  # Feature index
        "commit": {
            "success": True,
            "sha": "abc123def456",
            "branch": "feature/batch-1",
            "timestamp": "2025-12-06T10:00:00Z"
        },
        "push": {
            "success": True,
            "remote": "origin",
            "branch": "feature/batch-1",
            "timestamp": "2025-12-06T10:00:05Z"
        },
        "pr": {
            "success": True,
            "number": 123,
            "url": "https://github.com/user/repo/pull/123",
            "timestamp": "2025-12-06T10:00:10Z"
        }
    },
    1: {  # Next feature
        "commit": {
            "success": False,
            "error": "Merge conflict in file.py",
            "timestamp": "2025-12-06T10:05:00Z"
        }
    }
}
```

**Tests**: 3 tests verify field initialization
- `test_batch_state_has_git_operations_field`
- `test_git_operations_field_initializes_as_empty_dict`
- `test_git_operations_field_type_is_dict`

#### 1.2 Implement record_git_operation() Function
- [ ] Create function: `record_git_operation(state, feature_index, operation, success, **kwargs)`
- [ ] Support operation types: 'commit', 'push', 'pr'
- [ ] Record success/failure with appropriate metadata
- [ ] Add timestamp to each operation
- [ ] Return updated state (immutable pattern)
- [ ] Add comprehensive docstring

**Function Signature**:
```python
def record_git_operation(
    state: BatchState,
    feature_index: int,
    operation: str,  # 'commit', 'push', 'pr'
    success: bool,
    commit_sha: Optional[str] = None,
    branch: Optional[str] = None,
    remote: Optional[str] = None,
    pr_number: Optional[int] = None,
    pr_url: Optional[str] = None,
    error_message: Optional[str] = None,
    **kwargs
) -> BatchState:
    """
    Record git operation result for a feature.

    Args:
        state: Current batch state
        feature_index: Index of feature being processed
        operation: Operation type ('commit', 'push', 'pr')
        success: Whether operation succeeded
        commit_sha: Commit SHA (for commit operations)
        branch: Branch name
        remote: Remote name (for push operations)
        pr_number: PR number (for pr operations)
        pr_url: PR URL (for pr operations)
        error_message: Error message (for failures)
        **kwargs: Additional metadata

    Returns:
        Updated batch state with git operation recorded

    Example:
        >>> state = record_git_operation(
        ...     state,
        ...     feature_index=0,
        ...     operation='commit',
        ...     success=True,
        ...     commit_sha='abc123',
        ...     branch='feature/test'
        ... )
    """
```

**Tests**: 11 tests verify operation recording
- `test_record_commit_operation`
- `test_record_push_operation`
- `test_record_pr_creation`
- `test_record_multiple_operations_same_feature`
- `test_record_commit_failure`
- `test_record_push_failure_network_error`
- `test_record_pr_failure_merge_conflict`

#### 1.3 Implement get_feature_git_status() Function
- [ ] Create function: `get_feature_git_status(state, feature_index)`
- [ ] Return git operations dict for feature
- [ ] Return None if no operations recorded
- [ ] Add comprehensive docstring

**Function Signature**:
```python
def get_feature_git_status(
    state: BatchState,
    feature_index: int
) -> Optional[Dict[str, Any]]:
    """
    Get git operation status for a feature.

    Args:
        state: Current batch state
        feature_index: Index of feature

    Returns:
        Dict of git operations for feature, or None if no operations

    Example:
        >>> status = get_feature_git_status(state, 0)
        >>> if status:
        ...     print(f"Commit: {status['commit']['sha']}")
    """
```

**Tests**: 2 tests verify status queries
- `test_get_feature_git_status_successful_commit`
- `test_get_feature_git_status_no_operations`

#### 1.4 Update JSON Serialization
- [ ] Ensure `git_operations` field serialized to JSON
- [ ] Handle integer keys (JSON converts to strings)
- [ ] Add backward compatibility for loading old state files
- [ ] Test roundtrip save/load preserves git_operations

**Tests**: 3 tests verify persistence
- `test_save_load_roundtrip_with_git_operations`
- `test_json_serialization_preserves_git_operations`
- `test_load_state_without_git_operations_field`

---

### 2. Git Integration Module Changes

**File**: `plugins/autonomous-dev/lib/auto_implement_git_integration.py`

#### 2.1 Add in_batch_mode Parameter
- [ ] Add `in_batch_mode: bool = False` to `execute_git_workflow()` signature
- [ ] Update function docstring
- [ ] Add parameter to `execute_step8_git_operations()` (if exists)

**Updated Signature**:
```python
def execute_git_workflow(
    workflow_id: str,
    request: str,
    branch: Optional[str] = None,
    push: Optional[bool] = None,
    create_pr: bool = False,
    base_branch: str = 'main',
    in_batch_mode: bool = False  # NEW
) -> Dict[str, Any]:
    """
    Execute git automation workflow.

    Args:
        workflow_id: Unique workflow identifier
        request: Feature request description
        branch: Branch name (optional)
        push: Whether to push to remote (optional)
        create_pr: Whether to create PR (default: False)
        base_branch: Base branch for PR (default: 'main')
        in_batch_mode: Skip first-run consent prompts (default: False)

    Returns:
        Dict with success status, commit info, and git operation results
    """
```

**Tests**: 2 tests verify parameter
- `test_execute_git_workflow_accepts_in_batch_mode_parameter`
- `test_in_batch_mode_defaults_to_false`

#### 2.2 Implement Consent Bypass Logic
- [ ] Skip `show_first_run_warning()` when `in_batch_mode=True`
- [ ] Still check `check_consent_via_env()` for AUTO_GIT_ENABLED
- [ ] Respect AUTO_GIT_ENABLED=false even in batch mode
- [ ] Add audit log entry noting batch mode consent source

**Implementation**:
```python
# In execute_git_workflow():
if in_batch_mode:
    # Skip first-run warning in batch mode
    consent = check_consent_via_env()
    audit_log('git_workflow', 'consent', {
        'source': 'environment',
        'batch_mode': True,
        'enabled': consent['enabled'],
        'push': consent['push'],
        'pr': consent['pr']
    })
else:
    # Interactive mode: show first-run warning
    if should_show_warning(DEFAULT_STATE_FILE):
        if not show_first_run_warning(DEFAULT_STATE_FILE):
            return {'success': False, 'git_enabled': False}
    consent = check_consent_via_env()
```

**Tests**: 3 tests verify consent bypass
- `test_batch_mode_skips_first_run_warning`
- `test_batch_mode_respects_env_var_consent`
- `test_batch_mode_respects_disabled_consent`

#### 2.3 Implement Graceful Error Handling
- [ ] Wrap git operations in try/except
- [ ] Return failure dict instead of raising exceptions
- [ ] Include clear error messages in return value
- [ ] Log errors to audit log
- [ ] Don't modify user state file in batch mode

**Error Handling Pattern**:
```python
try:
    # Git operations
    result = auto_commit_and_push(...)
    return {
        'success': True,
        'commit_sha': result['commit_sha'],
        'batch_mode': in_batch_mode
    }
except CalledProcessError as e:
    audit_log('git_workflow', 'error', {
        'batch_mode': in_batch_mode,
        'error': str(e),
        'stderr': e.stderr
    })
    return {
        'success': False,
        'error': format_error_message(e),
        'batch_mode': in_batch_mode
    }
except Exception as e:
    audit_log('git_workflow', 'error', {
        'batch_mode': in_batch_mode,
        'error': str(e)
    })
    return {
        'success': False,
        'error': str(e),
        'batch_mode': in_batch_mode
    }
```

**Tests**: 9 tests verify error handling
- `test_batch_mode_commit_failure_graceful`
- `test_batch_mode_network_failure_graceful`
- `test_batch_mode_git_not_available`
- `test_batch_mode_detached_head_warning`
- `test_batch_mode_git_directory_permission_denied`
- `test_batch_mode_remote_push_permission_denied`
- `test_batch_mode_git_cli_not_installed`
- `test_batch_mode_gh_cli_not_installed`
- `test_batch_mode_doesnt_modify_user_state`

#### 2.4 Add Batch Mode Audit Logging
- [ ] Log all git operations with batch_mode flag
- [ ] Log consent source (env var vs interactive)
- [ ] Log operation results (success/failure)
- [ ] Log error details for failures

**Tests**: 2 tests verify audit logging
- `test_batch_mode_logs_git_operations`
- `test_batch_mode_logs_consent_source`

#### 2.5 Add Return Value Fields
- [ ] Include `batch_mode: bool` in return dict
- [ ] Maintain backward compatibility with existing return structure
- [ ] Document new field in docstring

**Tests**: 2 tests verify return values
- `test_batch_mode_returns_standard_structure`
- `test_batch_mode_includes_batch_flag`

---

### 3. Batch Implement Command Integration

**File**: `plugins/autonomous-dev/commands/batch-implement.md`

#### 3.1 Add Git Workflow Invocation
- [ ] After each feature completes, call `execute_git_workflow()`
- [ ] Pass `in_batch_mode=True` parameter
- [ ] Include feature request in workflow call
- [ ] Log git operation to session file

**Integration Point** (after STEP 4 - feature processing):
```markdown
### STEP 5: Git Automation (Per Feature)

After each feature completes:

1. Check if git automation enabled (AUTO_GIT_ENABLED env var)
2. Execute git workflow in batch mode:
   ```python
   from auto_implement_git_integration import execute_git_workflow

   git_result = execute_git_workflow(
       workflow_id=f'batch-{batch_id}-feature-{current_index}',
       request=current_feature,
       in_batch_mode=True  # Skip first-run consent
   )
   ```
3. Record git operation in batch state:
   ```python
   from batch_state_manager import record_git_operation

   if git_result['success']:
       state = record_git_operation(
           state,
           feature_index=current_index,
           operation='commit',
           success=True,
           commit_sha=git_result['commit_sha'],
           branch=git_result.get('branch')
       )

       if git_result.get('pushed'):
           state = record_git_operation(
               state,
               feature_index=current_index,
               operation='push',
               success=True,
               remote=git_result.get('remote'),
               branch=git_result.get('branch')
           )

       if git_result.get('pr_created'):
           state = record_git_operation(
               state,
               feature_index=current_index,
               operation='pr',
               success=True,
               pr_number=git_result.get('pr_number'),
               pr_url=git_result.get('pr_url')
           )
   else:
       state = record_git_operation(
           state,
           feature_index=current_index,
           operation='commit',
           success=False,
           error_message=git_result.get('error')
       )

   save_batch_state(state, state_file)
   ```
4. Log git operation to session file
5. Continue with next feature (don't abort on git failure)
```

**Tests**: 10 tests verify workflow integration
- `test_batch_workflow_commits_each_feature`
- `test_batch_workflow_tracks_git_operations_in_state`
- `test_batch_workflow_respects_disabled_git_automation`
- `test_batch_resume_skips_already_committed_features`
- `test_batch_continues_after_push_failure`
- Plus 5 more workflow tests

#### 3.2 Handle Git Failures Gracefully
- [ ] Don't abort batch if git operations fail
- [ ] Record failure in batch state
- [ ] Log warning to session file
- [ ] Continue with next feature

**Tests**: 12 edge case tests verify graceful degradation

#### 3.3 Update Resume Logic
- [ ] Check git_operations field when resuming
- [ ] Don't re-commit already committed features
- [ ] Log skipped git operations to session file

**Tests**: 2 tests verify resume logic
- `test_batch_resume_skips_already_committed_features`

#### 3.4 Update Documentation
- [ ] Document git automation in batch mode
- [ ] Document consent model (env vars only)
- [ ] Document graceful degradation
- [ ] Document state tracking
- [ ] Add examples

---

### 4. Edge Case Handling

#### 4.1 Network Failures
- [ ] Timeout during push (30s default)
- [ ] Network unreachable
- [ ] DNS resolution failure
- [ ] Graceful degradation for all cases

**Tests**: 3 tests verify network failure handling

#### 4.2 Merge Conflicts
- [ ] Detect merge conflicts during commit
- [ ] Detect merge conflicts during PR creation
- [ ] Return clear error message
- [ ] Don't abort batch

**Tests**: 2 tests verify conflict handling

#### 4.3 Detached HEAD State
- [ ] Detect detached HEAD
- [ ] Include recovery suggestion in error
- [ ] Don't abort batch

**Tests**: 2 tests verify detached HEAD handling

#### 4.4 Permission Errors
- [ ] Local git directory permission denied
- [ ] Remote push permission denied
- [ ] Clear error messages
- [ ] Graceful degradation

**Tests**: 2 tests verify permission error handling

#### 4.5 Missing CLI Tools
- [ ] git CLI not installed
- [ ] gh CLI not installed
- [ ] Clear error messages
- [ ] Skip operations gracefully

**Tests**: 2 tests verify missing tool handling

#### 4.6 Dirty Working Tree
- [ ] Uncommitted changes warning
- [ ] Untracked files excluded
- [ ] Clear warnings in return value

**Tests**: 2 tests verify dirty tree handling

#### 4.7 Branch Protection
- [ ] Push rejected by branch protection
- [ ] PR requires approvals
- [ ] Clear error messages

**Tests**: 2 tests verify branch protection handling

#### 4.8 Agent Failures
- [ ] Commit message agent timeout
- [ ] Commit message agent error
- [ ] Fallback to default message
- [ ] Don't abort git operations

**Tests**: 2 tests verify agent failure handling

#### 4.9 Concurrent Operations
- [ ] Git lock file conflict
- [ ] Clear error message
- [ ] Graceful degradation

**Tests**: 1 test verifies concurrent operation handling

---

## Implementation Order

### Phase 1: Schema Changes (Blocking)
1. ✅ Update `BatchState` dataclass with `git_operations` field
2. ✅ Implement `record_git_operation()` function
3. ✅ Implement `get_feature_git_status()` function
4. ✅ Update JSON serialization
5. ✅ Add backward compatibility

**Expected Result**: 18 unit tests PASS

### Phase 2: API Changes (Blocking)
1. ✅ Add `in_batch_mode` parameter to `execute_git_workflow()`
2. ✅ Implement consent bypass logic
3. ✅ Implement graceful error handling
4. ✅ Add audit logging
5. ✅ Add return value fields

**Expected Result**: 15 unit tests PASS

### Phase 3: Workflow Integration
1. ✅ Add git workflow invocation to `/batch-implement`
2. ✅ Record git operations in state
3. ✅ Handle failures gracefully
4. ✅ Update resume logic

**Expected Result**: 10 integration tests PASS

### Phase 4: Edge Cases
1. ✅ Network failures
2. ✅ Merge conflicts
3. ✅ Detached HEAD
4. ✅ Permission errors
5. ✅ Missing tools
6. ✅ Dirty tree
7. ✅ Branch protection
8. ✅ Agent failures
9. ✅ Concurrent operations

**Expected Result**: 12 integration tests PASS

---

## Verification Steps

### Step 1: Unit Tests
```bash
# Test batch state git tracking
source .venv/bin/activate
pytest tests/unit/test_batch_state_git_tracking.py --tb=line -q -v

# Expected: 18 tests PASS
```

### Step 2: Integration Tests
```bash
# Test batch git integration
pytest tests/unit/lib/test_batch_git_integration.py --tb=line -q -v

# Expected: 15 tests PASS
```

### Step 3: Workflow Tests
```bash
# Test batch git workflow
pytest tests/integration/test_batch_git_workflow.py --tb=line -q -v

# Expected: 10 tests PASS
```

### Step 4: Edge Case Tests
```bash
# Test batch git edge cases
pytest tests/integration/test_batch_git_edge_cases.py --tb=line -q -v

# Expected: 12 tests PASS
```

### Step 5: Full Suite
```bash
# Run all Issue #93 tests
pytest tests/unit/test_batch_state_git_tracking.py \
       tests/unit/lib/test_batch_git_integration.py \
       tests/integration/test_batch_git_workflow.py \
       tests/integration/test_batch_git_edge_cases.py \
       --tb=line -q -v

# Expected: 55 tests PASS ✅
```

### Step 6: Coverage Report
```bash
# Generate coverage report
pytest tests/unit/test_batch_state_git_tracking.py \
       tests/unit/lib/test_batch_git_integration.py \
       tests/integration/test_batch_git_workflow.py \
       tests/integration/test_batch_git_edge_cases.py \
       --cov=plugins/autonomous-dev/lib/batch_state_manager \
       --cov=plugins/autonomous-dev/lib/auto_implement_git_integration \
       --cov-report=term-missing \
       --cov-report=html

# Expected: 90%+ coverage ✅
```

---

## Success Criteria

### Code Complete
- [ ] All 55 tests PASS
- [ ] Code coverage ≥ 90%
- [ ] All edge cases handled
- [ ] Documentation updated
- [ ] No regressions in existing tests

### Functional Complete
- [ ] Batch workflow commits each feature
- [ ] Git operations tracked in state
- [ ] Resume skips committed features
- [ ] Graceful error handling works
- [ ] Audit trail complete

### Quality Complete
- [ ] Type hints on all new functions
- [ ] Docstrings on all new functions
- [ ] Clear error messages
- [ ] Security audit passed
- [ ] Code review approved

---

## Related Files

### Test Files
- `tests/unit/test_batch_state_git_tracking.py`
- `tests/unit/lib/test_batch_git_integration.py`
- `tests/integration/test_batch_git_workflow.py`
- `tests/integration/test_batch_git_edge_cases.py`

### Implementation Files
- `plugins/autonomous-dev/lib/batch_state_manager.py`
- `plugins/autonomous-dev/lib/auto_implement_git_integration.py`
- `plugins/autonomous-dev/commands/batch-implement.md`

### Documentation Files
- `tests/TDD_SUMMARY_ISSUE_93.md`
- `tests/TEST_COVERAGE_ISSUE_93.md`
- `tests/IMPLEMENTATION_CHECKLIST_ISSUE_93.md` (this file)

---

**Current Phase**: TDD Red (tests written, awaiting implementation)
**Next Agent**: implementer
**Next Phase**: TDD Green (make tests pass)

---

**Last Updated**: 2025-12-06
**Issue**: #93 (Add auto-commit to batch workflow)
**Agent**: test-master
