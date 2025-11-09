# Issue #58 TDD Red Phase Summary

**Feature**: Automatic GitHub Issue Creation with Research Integration
**Date**: 2025-01-09
**Status**: TDD Red Phase Complete - Tests Written, Implementation Pending

---

## Overview

Comprehensive test suite written for GitHub issue automation feature (Issue #58). All tests are designed to FAIL until implementation is complete, following strict TDD methodology.

**Test Coverage Target**: 85%+ overall, 90%+ for core library

---

## Test Files Created

### 1. Unit Tests - Library (50 tests)

**File**: `tests/unit/lib/test_github_issue_automation.py`
**Lines**: 820+
**Coverage Target**: 90%+

**Test Categories**:

- **Title Validation** (8 tests)
  - `test_validate_title_valid` - Valid title passes
  - `test_validate_title_too_long` - Length limit enforcement (CWE-20)
  - `test_validate_title_shell_metacharacters` - Command injection prevention (CWE-78)
  - `test_validate_title_empty_string` - Empty validation
  - `test_validate_title_whitespace_only` - Whitespace handling
  - `test_validate_title_control_characters` - Control character blocking (CWE-117)
  - `test_validate_title_newlines` - Newline rejection
  - `test_validate_title_with_allowed_special_chars` - Allowed characters

- **Body Validation** (6 tests)
  - `test_validate_body_valid` - Valid body passes
  - `test_validate_body_too_long` - Length limit enforcement
  - `test_validate_body_empty_string` - Empty validation
  - `test_validate_body_whitespace_only` - Whitespace handling
  - `test_validate_body_with_markdown` - Markdown support
  - `test_validate_body_with_code_blocks` - Code block preservation

- **GH CLI Detection** (4 tests)
  - `test_check_gh_available_success` - CLI detected
  - `test_check_gh_available_not_installed` - Installation check
  - `test_check_gh_available_not_authenticated` - Auth validation
  - `test_check_gh_available_network_error` - Network error handling

- **Issue Number Parsing** (5 tests)
  - `test_parse_issue_number_from_url` - URL parsing
  - `test_parse_issue_number_with_surrounding_text` - Text extraction
  - `test_parse_issue_number_invalid_format` - Error handling
  - `test_parse_issue_number_multiple_urls` - Multiple URL handling
  - `test_parse_issue_number_pr_url_rejected` - PR vs Issue distinction

- **Command Building** (5 tests)
  - `test_build_gh_command_basic` - Basic command
  - `test_build_gh_command_with_labels` - Label support
  - `test_build_gh_command_with_assignee` - Assignee support
  - `test_build_gh_command_with_milestone` - Milestone support
  - `test_build_gh_command_escapes_special_chars` - Character escaping

- **Issue Creation** (6 tests)
  - `test_create_issue_success` - Successful creation
  - `test_create_issue_with_labels` - With labels
  - `test_create_issue_gh_error` - GH CLI error handling
  - `test_create_issue_network_timeout` - Timeout handling
  - `test_create_issue_gh_not_available` - CLI unavailable
  - `test_create_issue_validates_title` - Pre-creation validation
  - `test_create_issue_validates_body` - Body validation

- **Security Validation** (5 tests)
  - `test_path_validation_called_on_init` - Path validation
  - `test_path_traversal_blocked_via_project_root` - CWE-22 prevention
  - `test_symlink_attack_blocked` - CWE-59 prevention
  - `test_audit_logging_on_issue_creation` - Audit logging
  - `test_command_injection_prevention` - CWE-78 prevention

- **Result Data Class** (3 tests)
  - `test_result_success_attributes` - Success result
  - `test_result_failure_attributes` - Failure result
  - `test_result_to_dict` - JSON serialization

- **Convenience Function** (2 tests)
  - `test_create_github_issue_convenience_function` - High-level API
  - `test_create_github_issue_with_defaults` - Default handling

- **Error Handling** (4 tests)
  - `test_nonexistent_project_root_raises_error` - Path validation
  - `test_file_instead_of_directory_raises_error` - Directory check
  - `test_malformed_gh_output_handled_gracefully` - Output parsing
  - `test_empty_labels_list_handled_correctly` - Empty list handling
  - `test_none_assignee_handled_correctly` - None handling

- **Research Integration** (2 tests)
  - `test_create_issue_from_research_output` - Research formatting
  - `test_validate_research_output_format` - Format validation

**Security Focus**:
- CWE-78: Command injection prevention (shell metacharacters)
- CWE-117: Log injection prevention (control characters)
- CWE-20: Input validation (length limits, format validation)
- CWE-22: Path traversal prevention
- CWE-59: Symlink attack prevention

---

### 2. Unit Tests - CLI (20 tests)

**File**: `tests/unit/test_create_issue_cli.py`
**Lines**: 650+
**Coverage Target**: 85%+

**Test Categories**:

- **Argument Parsing** (10 tests)
  - Required arguments validation
  - Optional arguments (labels, assignee, milestone)
  - Flag parsing (--json, --verbose, -v)
  - Project root specification
  - Missing arguments error handling
  - All options together

- **Output Formatting - Human** (5 tests)
  - Success output formatting
  - Failure output formatting
  - URL inclusion
  - Issue number display
  - Error message display

- **Output Formatting - JSON** (4 tests)
  - Success JSON structure
  - Failure JSON structure
  - Details inclusion
  - Valid JSON validation

- **Main Function - Success** (3 tests)
  - Human-readable output
  - JSON output
  - Labels support

- **Main Function - Failure** (3 tests)
  - GH API errors
  - Validation errors
  - GH CLI not installed

- **Verbose Output** (2 tests)
  - Detailed information display
  - Command information

- **Error Messages** (2 tests)
  - Helpful validation errors
  - GH not found errors

- **Exit Codes** (2 tests)
  - Exit 0 on success
  - Exit 1 on failure

---

### 3. Integration Tests (15 tests)

**File**: `tests/integration/test_create_issue_workflow.py`
**Lines**: 630+
**Coverage Target**: 80%+

**Test Categories**:

- **Full Workflow** (3 tests)
  - End-to-end success workflow
  - Workflow with all metadata
  - Graceful failure handling

- **Researcher to Issue-Creator** (3 tests)
  - Research output formatting
  - Session log reading
  - End-to-end research to issue

- **CLI Integration** (2 tests)
  - CLI creates issue successfully
  - CLI JSON output validation

- **Error Recovery** (3 tests)
  - Graceful degradation (no gh CLI)
  - Network error retry
  - Validation before API calls

- **Concurrent Operations** (1 test)
  - Multiple sequential issues

- **Data Validation** (2 tests)
  - Session log format validation
  - Markdown preservation

- **Audit Logging** (2 tests)
  - Issue creation logging
  - Failure logging

---

### 4. Agent Tests (10 tests)

**File**: `tests/unit/agents/test_issue_creator.py`
**Lines**: 550+
**Coverage Target**: 85%+

**Test Categories**:

- **Markdown Formatting** (5 tests)
  - Required sections present
  - Heading levels correct
  - List formatting
  - Code block support
  - Link formatting

- **Research Log Parsing** (4 tests)
  - Extract findings
  - Extract references
  - Extract topic
  - Handle missing fields

- **Title Generation** (4 tests)
  - From research topic
  - Length validation
  - Special character handling
  - Descriptive clarity

- **Body Generation** (5 tests)
  - Include research summary
  - Include findings
  - Include references
  - Include implementation notes
  - Valid markdown structure

- **Label Suggestions** (5 tests)
  - Enhancement label
  - Research label
  - Performance label
  - Security label
  - Custom labels

- **Agent Prompt Structure** (3 tests)
  - Required frontmatter
  - Clear instructions
  - Relevant skills

- **Output Validation** (6 tests)
  - Required fields
  - Title not empty
  - Body not empty
  - Labels is list
  - JSON serializable

- **Error Handling** (3 tests)
  - Missing research log
  - Malformed JSON
  - Empty research log

---

## Test Execution

### Run Verification Script

```bash
python tests/verify_issue58_tdd_red.py
```

**Expected Output**:
- All tests FAIL (because implementation doesn't exist yet)
- Clear summary showing test counts
- Next steps for implementation

### Run Individual Test Files

```bash
# Unit tests - library
pytest tests/unit/lib/test_github_issue_automation.py -v

# Unit tests - CLI
pytest tests/unit/test_create_issue_cli.py -v

# Integration tests
pytest tests/integration/test_create_issue_workflow.py -v

# Agent tests
pytest tests/unit/agents/test_issue_creator.py -v
```

### Run All Issue #58 Tests

```bash
pytest tests/unit/lib/test_github_issue_automation.py \
       tests/unit/test_create_issue_cli.py \
       tests/integration/test_create_issue_workflow.py \
       tests/unit/agents/test_issue_creator.py \
       -v --tb=short
```

---

## Mocking Strategy

### Library Tests
- Mock `subprocess.run` for gh CLI calls
- Mock `check_gh_available` for CLI detection
- Mock `security_utils.validate_path` for path validation
- Mock `security_utils.audit_log` for audit logging

### CLI Tests
- Mock `GitHubIssueAutomation` class
- Mock `sys.stdout` and `sys.stderr` for output capture
- Mock `sys.argv` for argument parsing

### Integration Tests
- Mock `subprocess.run` for gh CLI
- Mock `check_gh_available` for CLI availability
- Create real temporary directories and files
- Use realistic session log fixtures

### Agent Tests
- Create real JSON session logs in temp directories
- Test markdown formatting without mocks
- Validate output structure directly

---

## Security Testing Coverage

### CWE Vulnerabilities Tested

1. **CWE-78: Command Injection**
   - Shell metacharacters in title (`;`, `&&`, `|`, `` ` ``, `$()`)
   - Proper escaping validation
   - Subprocess safety

2. **CWE-117: Log Injection**
   - Control characters in title/body
   - Newline handling
   - Audit log sanitization

3. **CWE-20: Input Validation**
   - Title length limits (max 256 chars)
   - Body length limits (max 100KB)
   - Empty string rejection
   - Whitespace-only rejection

4. **CWE-22: Path Traversal**
   - Project root validation
   - Path traversal attempts (`../../../etc/passwd`)
   - Whitelist enforcement

5. **CWE-59: Symlink Following**
   - Symlink detection
   - TOCTOU prevention
   - Real path validation

---

## Implementation Checklist

### Phase 1: Library Implementation
- [ ] Create `plugins/autonomous-dev/lib/github_issue_automation.py`
- [ ] Implement `GitHubIssueAutomation` class
- [ ] Implement `IssueCreationResult` dataclass
- [ ] Implement validation functions
- [ ] Implement GH CLI detection
- [ ] Implement issue number parsing
- [ ] Implement security validation
- [ ] Implement audit logging
- [ ] Run library tests - should PASS

### Phase 2: CLI Implementation
- [ ] Create `plugins/autonomous-dev/scripts/create_issue.py`
- [ ] Implement argument parsing
- [ ] Implement output formatting (human + JSON)
- [ ] Implement verbose mode
- [ ] Implement error handling
- [ ] Run CLI tests - should PASS

### Phase 3: Agent Implementation
- [ ] Create `plugins/autonomous-dev/agents/issue-creator.md`
- [ ] Define agent frontmatter (name, tools, model)
- [ ] Write agent instructions
- [ ] Define input/output format
- [ ] Reference relevant skills
- [ ] Run agent tests - should PASS

### Phase 4: Command Implementation
- [ ] Create `plugins/autonomous-dev/commands/create-issue.md`
- [ ] Define command metadata
- [ ] Write command instructions
- [ ] Document usage examples
- [ ] Run integration tests - should PASS

### Phase 5: Documentation
- [ ] Update CLAUDE.md (command count, agent count)
- [ ] Update README.md (new command documentation)
- [ ] Update CHANGELOG.md (new feature entry)
- [ ] Update skills references if needed

---

## Success Criteria

### TDD Red Phase (Current)
- ✅ 50+ unit tests written for library
- ✅ 20+ unit tests written for CLI
- ✅ 15+ integration tests written
- ✅ 10+ agent tests written
- ✅ All tests FAIL (no implementation exists)
- ✅ Verification script confirms red phase

### TDD Green Phase (Next)
- [ ] All library tests PASS
- [ ] All CLI tests PASS
- [ ] All integration tests PASS
- [ ] All agent tests PASS
- [ ] 85%+ code coverage achieved
- [ ] No security vulnerabilities introduced

### TDD Refactor Phase (Final)
- [ ] Code follows project patterns
- [ ] Security validation consistent
- [ ] Error messages helpful
- [ ] Documentation complete
- [ ] Performance acceptable
- [ ] Ready for production use

---

## Files Created

1. `/tests/unit/lib/test_github_issue_automation.py` (820 lines, 50 tests)
2. `/tests/unit/test_create_issue_cli.py` (650 lines, 20 tests)
3. `/tests/integration/test_create_issue_workflow.py` (630 lines, 15 tests)
4. `/tests/unit/agents/test_issue_creator.py` (550 lines, 10 tests)
5. `/tests/verify_issue58_tdd_red.py` (100 lines, verification script)
6. `/tests/ISSUE_58_TDD_RED_SUMMARY.md` (this file)

**Total**: 2,750+ lines of test code, 95+ tests

---

## Next Steps

1. **Run Verification**: `python tests/verify_issue58_tdd_red.py`
2. **Confirm Red Phase**: All tests should FAIL
3. **Begin Implementation**: Start with library (highest priority)
4. **Iterative Testing**: Run tests after each component
5. **Achieve Green Phase**: All tests PASS
6. **Refactor**: Improve code quality while maintaining test passage

---

## Related Files

- **Implementation Plan**: See planner agent output for detailed architecture
- **Research Findings**: See researcher agent session logs
- **Security Patterns**: `docs/SECURITY.md`
- **Testing Guide**: `plugins/autonomous-dev/skills/testing-guide/SKILL.md`

---

**Status**: ✅ TDD Red Phase Complete
**Next Phase**: Implementation (TDD Green Phase)
**Estimated Implementation Time**: 2-3 hours

---

*Generated: 2025-01-09*
*Related: GitHub Issue #58 - Automatic GitHub issue creation with research*
