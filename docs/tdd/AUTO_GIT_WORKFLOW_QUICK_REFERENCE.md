# Auto Git Workflow - TDD Quick Reference

**Status**: TDD Red Phase VERIFIED ✅
**Date**: 2025-11-09
**Total Tests**: 88 tests (all failing as expected)

## Test Files

### 1. Hook Unit Tests
**File**: `tests/unit/hooks/test_auto_git_workflow.py`
**Tests**: 44
**Status**: SKIPPED (module doesn't exist)

### 2. Security Validation Tests
**File**: `tests/unit/test_auto_implement_git_integration.py::TestSecurityValidation`
**Tests**: 23
**Status**: FAILED (functions don't exist)

### 3. Integration Tests
**File**: `tests/integration/test_auto_implement_git_end_to_end.py`
**Tests**: 21
**Status**: SKIPPED (module doesn't exist)

## Run Tests

```bash
# Verify TDD red phase
python tests/verify_auto_git_workflow_tdd_red.py

# Run individual test suites
pytest tests/unit/hooks/test_auto_git_workflow.py -v
pytest tests/unit/test_auto_implement_git_integration.py::TestSecurityValidation -v
pytest tests/integration/test_auto_implement_git_end_to_end.py -v

# Run all auto-git tests
pytest tests/unit/hooks/test_auto_git_workflow.py tests/unit/test_auto_implement_git_integration.py::TestSecurityValidation tests/integration/test_auto_implement_git_end_to_end.py -v
```

## Implementation Checklist

### 1. New Hook File
- [ ] Create `plugins/autonomous-dev/hooks/auto_git_workflow.py`
- [ ] Implement 8 functions (see test file for signatures)
- [ ] Add security validation using security_utils
- [ ] Add comprehensive error handling
- [ ] Add docstrings and type hints

### 2. Security Enhancements
- [ ] Add 4 validation functions to `auto_implement_git_integration.py`
- [ ] `validate_git_state()` - Check git repo state
- [ ] `validate_branch_name()` - Prevent command injection
- [ ] `validate_commit_message()` - Prevent log injection
- [ ] `check_git_credentials()` - Validate git config

### 3. Test Verification
- [ ] Run hook unit tests (should pass)
- [ ] Run security validation tests (should pass)
- [ ] Run integration tests (should pass)
- [ ] Verify 95%+ coverage for hook
- [ ] Verify 100% coverage for security functions
- [ ] Verify 85%+ coverage for integration

## Coverage Targets

- **Hook Unit Tests**: 95%+ (44/44 tests passing)
- **Security Tests**: 100% (23/23 tests passing)
- **Integration Tests**: 85%+ (21/21 tests passing)
- **Overall**: 88/88 tests passing

## Key Functions to Implement

```python
# auto_git_workflow.py
def should_trigger_git_workflow(agent_name: str) -> bool
def check_git_workflow_consent() -> Dict[str, bool]
def get_session_file_path() -> Path
def read_session_data(session_file: Path) -> Dict[str, Any]
def extract_workflow_metadata(session_data: Dict) -> Dict[str, str]
def trigger_git_operations(workflow_id: str, request: str, consent: Dict) -> Dict
def run_hook(agent_name: str) -> Dict
def main() -> int

# auto_implement_git_integration.py
def validate_git_state() -> bool
def validate_branch_name(branch: str) -> str
def validate_commit_message(message: str) -> str
def check_git_credentials(require_gh: bool = True) -> bool
```

## Environment Variables

```bash
# Hook trigger
CLAUDE_AGENT_NAME=quality-validator

# Session file (optional)
CLAUDE_SESSION=/path/to/session.json

# Consent flags
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true
AUTO_GIT_PR=true
```

## Security Coverage (CWE)

- **CWE-22**: Path Traversal (session files)
- **CWE-59**: Symlink Following (session files)
- **CWE-78**: Command Injection (branch names, commit messages)
- **CWE-117**: Log Injection (commit messages, audit logs)
- **CWE-732**: Incorrect Permissions (git directories)

## Test Execution Summary

```
✅ Hook Unit Tests (44) - SKIPPED (module doesn't exist - TDD red)
✅ Security Tests (23) - FAILED (functions don't exist - TDD red)
✅ Integration Tests (21) - SKIPPED (module doesn't exist - TDD red)

Total: 88 tests, all in expected failing state
Ready for implementation (TDD green phase)
```

## Next Steps

1. Implement `auto_git_workflow.py` hook
2. Enhance `auto_implement_git_integration.py` with security functions
3. Run tests to verify implementation
4. Refactor if needed
5. Document and commit
