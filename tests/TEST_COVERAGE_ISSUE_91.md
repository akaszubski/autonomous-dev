# Test Coverage for Issue #91: Auto-close GitHub Issues

**Status**: TDD Red Phase (Tests Written BEFORE Implementation)
**Date**: 2025-11-18
**Agent**: test-master
**Issue**: #91 - Auto-close GitHub issues after /auto-implement completes successfully

---

## Test Results Summary

**Total Tests**: 54 tests (52 FAILED, 2 PASSED)
**Expected Outcome**: FAIL (no implementation exists yet - TDD red phase)
**Coverage Target**: 95%+ for new code

### Test Breakdown by File

#### 1. Unit Tests - Library (`test_github_issue_closer.py`)
**Tests**: 31 total
**Status**: 31 FAILED (expected)

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestIssueNumberExtraction` | 8 | Pattern matching, edge cases |
| `TestIssueStateValidation` | 5 | gh CLI mocking, error handling |
| `TestCloseSummaryGeneration` | 5 | Summary formatting, sanitization |
| `TestIssueClosing` | 5 | gh CLI execution, audit logging |
| `TestUserConsent` | 4 | User input, retries |
| `TestSecurityValidation` | 4 | CWE-20, CWE-78, CWE-117 compliance |

**Functions Tested**:
- `extract_issue_number()` - 8 tests
- `validate_issue_state()` - 5 tests
- `generate_close_summary()` - 5 tests
- `close_github_issue()` - 5 tests
- `prompt_user_consent()` - 4 tests
- Security validation - 4 tests

#### 2. Unit Tests - Hook Integration (`test_auto_git_workflow_issue_close.py`)
**Tests**: 10 total
**Status**: 8 FAILED, 2 PASSED (expected)

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestHandleIssueClose` | 6 | Workflow integration, graceful degradation |
| `TestIntegrationWithGitWorkflow` | 4 | Hook integration, metadata flow |

**Functions Tested**:
- `handle_issue_close()` - 6 tests
- Git workflow integration - 4 tests

**Note**: 2 tests passed (format validation tests) as they don't require implementation.

#### 3. Integration Tests - End-to-End (`test_issue_close_end_to_end.py`)
**Tests**: 13 total
**Status**: 13 FAILED (expected)

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestIssueCloseEndToEnd` | 5 | Complete workflow scenarios |
| `TestMetadataIntegration` | 2 | Data flow between components |
| `TestErrorRecovery` | 3 | Error handling, graceful degradation |
| `TestSecurityIntegration` | 3 | Security across components |

**Scenarios Tested**:
- Full successful workflow
- No issue number (skip gracefully)
- User declines consent (skip gracefully)
- Issue already closed (idempotent)
- gh CLI not available (graceful degradation)
- Network timeout recovery
- Command injection prevention (CWE-78)
- Log injection prevention (CWE-117)
- Audit logging end-to-end

---

## Test Coverage by Component

### Core Library (`github_issue_closer.py`)

**Functions**: 5 total

1. **`extract_issue_number(command_args: str) -> Optional[int]`**
   - Tests: 8
   - Coverage: Pattern matching (issue #8, #8, Issue 8), case sensitivity, multiple occurrences, edge cases

2. **`validate_issue_state(issue_number: int) -> bool`**
   - Tests: 5
   - Coverage: Open issue validation, closed issue detection, nonexistent issues, timeout handling, network failures

3. **`generate_close_summary(issue_number: int, metadata: dict) -> str`**
   - Tests: 5
   - Coverage: Full metadata, no PR, file truncation (>10 files), output sanitization, 7-agent listing

4. **`close_github_issue(issue_number: int, summary: str) -> bool`**
   - Tests: 5
   - Coverage: Success, idempotent (already closed), nonexistent issue, timeout, audit logging

5. **`prompt_user_consent(issue_number: int) -> bool`**
   - Tests: 4
   - Coverage: Yes/No responses, case insensitivity, invalid input retry

**Custom Exceptions**: 3 total
- `IssueAlreadyClosedError`
- `IssueNotFoundError`
- `GitHubAPIError`

### Hook Modification (`auto_git_workflow.py`)

**New Function**: 1 total

1. **`handle_issue_close(command_args: str, metadata: dict) -> bool`**
   - Tests: 6
   - Coverage: Success path, skip scenarios (no issue, user decline, already closed), gh CLI failure, audit logging

**Integration Points**:
- Called after git push succeeds in `run_hook()`
- Receives command args from user prompt
- Receives metadata from git operations (PR URL, commit hash, files changed, agents passed)

---

## Security Requirements Coverage

All security requirements from planner and researcher are tested:

### CWE-20: Input Validation
- **Tests**: 2
- **Coverage**: Positive integers only, reject negative/zero/non-integers
- **Files**: `test_github_issue_closer.py::TestSecurityValidation::test_validate_positive_integers_only`

### CWE-78: Command Injection Prevention
- **Tests**: 2
- **Coverage**: subprocess list args (never shell=True), command construction validation
- **Files**:
  - `test_github_issue_closer.py::TestSecurityValidation::test_command_injection_prevention`
  - `test_issue_close_end_to_end.py::TestSecurityIntegration::test_command_injection_prevention_end_to_end`

### CWE-117: Log Injection Prevention
- **Tests**: 2
- **Coverage**: Sanitize newlines and control characters from issue titles and summaries
- **Files**:
  - `test_github_issue_closer.py::TestSecurityValidation::test_log_injection_prevention`
  - `test_issue_close_end_to_end.py::TestSecurityIntegration::test_output_sanitization_end_to_end`

### Audit Logging
- **Tests**: 3
- **Coverage**: All gh CLI operations logged, consent decisions logged
- **Files**:
  - `test_github_issue_closer.py::TestSecurityValidation::test_audit_logging_all_operations`
  - `test_auto_git_workflow_issue_close.py::TestHandleIssueClose::test_audit_logging_on_close`
  - `test_issue_close_end_to_end.py::TestSecurityIntegration::test_audit_logging_end_to_end`

---

## Test Patterns Used

### AAA Pattern (Arrange-Act-Assert)
All tests follow the AAA pattern for clarity:

```python
def test_example(self):
    """Test description.

    Given: Initial conditions
    When: Action performed
    Then: Expected outcome
    """
    # Arrange
    mock_setup()

    # Act
    result = function_call()

    # Assert
    assert result == expected
```

### Mocking Strategy

**External Dependencies Mocked**:
- `subprocess.run` - gh CLI calls
- `builtins.input` - User consent prompts
- `log_audit_event` - Audit logging

**Mock Patterns**:
- Return values for success scenarios
- Side effects for exceptions (CalledProcessError, TimeoutExpired)
- Call verification for security validation

### Edge Cases Covered

1. **Issue Number Extraction**:
   - Various patterns (issue #8, #8, Issue 8)
   - Case insensitivity
   - Multiple occurrences
   - No issue number
   - Empty string

2. **Error Handling**:
   - Network timeouts
   - gh CLI not installed
   - Issue not found
   - Issue already closed
   - User interrupts (Ctrl+C)

3. **Security**:
   - Command injection attempts
   - Log injection attempts
   - Invalid input types
   - Malicious metadata

---

## Implementation Checklist

When implementing, verify each test passes:

### Phase 1: Core Library (`github_issue_closer.py`)
- [ ] `extract_issue_number()` - 8 tests
- [ ] `validate_issue_state()` - 5 tests
- [ ] `generate_close_summary()` - 5 tests
- [ ] `close_github_issue()` - 5 tests
- [ ] `prompt_user_consent()` - 4 tests
- [ ] Security validation - 4 tests
- [ ] Custom exceptions - 3 classes

### Phase 2: Hook Integration (`auto_git_workflow.py`)
- [ ] `handle_issue_close()` - 6 tests
- [ ] Integration with existing workflow - 4 tests

### Phase 3: End-to-End Testing
- [ ] Full workflow - 5 tests
- [ ] Metadata integration - 2 tests
- [ ] Error recovery - 3 tests
- [ ] Security integration - 3 tests

---

## Running Tests

```bash
# Run all issue close tests
.venv/bin/python -m pytest \
  tests/unit/lib/test_github_issue_closer.py \
  tests/unit/hooks/test_auto_git_workflow_issue_close.py \
  tests/integration/test_issue_close_end_to_end.py \
  -v

# Run with coverage
.venv/bin/python -m pytest \
  tests/unit/lib/test_github_issue_closer.py \
  --cov=plugins/autonomous-dev/lib/github_issue_closer \
  --cov-report=term-missing

# Run specific test class
.venv/bin/python -m pytest \
  tests/unit/lib/test_github_issue_closer.py::TestIssueNumberExtraction \
  -v
```

---

## Expected Progression

### TDD Red Phase (Current)
**Status**: 52 failed, 2 passed
**Reason**: No implementation exists yet
**Action**: Proceed to implementation phase

### TDD Green Phase (Next)
**Goal**: All 54 tests pass
**Implementation**: Create `github_issue_closer.py`, modify `auto_git_workflow.py`
**Verification**: Run tests after each function implemented

### TDD Refactor Phase (Final)
**Goal**: Maintain 100% test pass rate
**Actions**: Code cleanup, optimization, documentation
**Verification**: Tests continue passing during refactoring

---

## Test File Locations

```
tests/
├── unit/
│   ├── lib/
│   │   └── test_github_issue_closer.py       (31 tests)
│   └── hooks/
│       └── test_auto_git_workflow_issue_close.py  (10 tests)
└── integration/
    └── test_issue_close_end_to_end.py         (13 tests)
```

---

## Notes for Implementer

1. **Follow Test Order**: Implement functions in the order tests are written
2. **Watch Tests Pass**: Run tests after implementing each function
3. **Security First**: Ensure CWE-20, CWE-78, CWE-117 compliance from the start
4. **Graceful Degradation**: All failures should be graceful (return False, log error)
5. **Audit Logging**: Log all security-relevant operations
6. **Idempotent**: Closing already-closed issues should succeed silently

---

**TDD Status**: RED (as expected)
**Next Phase**: Implementation (implementer agent)
**Coverage Goal**: 95%+ achieved when all tests pass
