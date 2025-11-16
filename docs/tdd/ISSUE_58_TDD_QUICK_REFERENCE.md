# Issue #58 TDD Quick Reference

**Feature**: Automatic GitHub Issue Creation with Research
**Status**: RED PHASE COMPLETE ✅

---

## Quick Test Commands

### Verify TDD Red Phase
```bash
python tests/verify_issue58_tdd_red.py
```

**Expected**: All tests FAIL (no implementation exists yet)

---

### Run All Issue #58 Tests
```bash
python -m pytest \
  tests/unit/lib/test_github_issue_automation.py \
  tests/unit/test_create_issue_cli.py \
  tests/integration/test_create_issue_workflow.py \
  tests/unit/agents/test_issue_creator.py \
  -v
```

---

### Run Individual Test Files

**Library tests (50 tests)**:
```bash
python -m pytest tests/unit/lib/test_github_issue_automation.py -v
```

**CLI tests (20 tests)**:
```bash
python -m pytest tests/unit/test_create_issue_cli.py -v
```

**Integration tests (15 tests)**:
```bash
python -m pytest tests/integration/test_create_issue_workflow.py -v
```

**Agent tests (10 tests)**:
```bash
python -m pytest tests/unit/agents/test_issue_creator.py -v
```

---

### Run Tests with Coverage

```bash
python -m pytest \
  tests/unit/lib/test_github_issue_automation.py \
  tests/unit/test_create_issue_cli.py \
  tests/integration/test_create_issue_workflow.py \
  tests/unit/agents/test_issue_creator.py \
  --cov=plugins.autonomous_dev.lib.github_issue_automation \
  --cov=plugins.autonomous_dev.scripts.create_issue \
  --cov-report=term-missing \
  --cov-report=html
```

**Target**: 85%+ overall coverage

---

## Test File Locations

```
tests/
├── unit/
│   ├── lib/
│   │   └── test_github_issue_automation.py  # 50 tests, 820 lines
│   ├── agents/
│   │   └── test_issue_creator.py            # 10 tests, 550 lines
│   └── test_create_issue_cli.py             # 20 tests, 650 lines
├── integration/
│   └── test_create_issue_workflow.py        # 15 tests, 630 lines
├── verify_issue58_tdd_red.py                # Verification script
├── ISSUE_58_TDD_RED_SUMMARY.md              # Detailed summary
└── ISSUE_58_TDD_QUICK_REFERENCE.md          # This file
```

---

## Implementation Files to Create

### Phase 1: Library (Priority 1)
```
plugins/autonomous-dev/lib/github_issue_automation.py
```

**Classes**:
- `GitHubIssueAutomation` - Main automation class
- `IssueCreationResult` - Result dataclass

**Functions**:
- `create_github_issue()` - Convenience function
- `validate_issue_title()` - Title validation
- `validate_issue_body()` - Body validation
- `check_gh_available()` - GH CLI detection
- `parse_issue_number()` - Issue number extraction

---

### Phase 2: CLI Script (Priority 2)
```
plugins/autonomous-dev/scripts/create_issue.py
```

**Functions**:
- `parse_args()` - Argument parsing
- `format_output_human()` - Human-readable output
- `format_output_json()` - JSON output
- `main()` - Entry point

---

### Phase 3: Agent (Priority 3)
```
plugins/autonomous-dev/agents/issue-creator.md
```

**Frontmatter**:
```yaml
name: issue-creator
description: Format research findings into GitHub issue
model: sonnet
tools: [Read, Grep, Write]
```

**Sections**:
- Mission
- Input (research session logs)
- Output Format (title, body, labels)
- Validation rules

---

### Phase 4: Command (Priority 4)
```
plugins/autonomous-dev/commands/create-issue.md
```

**Frontmatter**:
```yaml
name: create-issue
description: Create GitHub issue from research
usage: /create-issue <research-topic>
```

---

## Test Categories & Counts

| Category | Tests | Focus |
|----------|-------|-------|
| **Title Validation** | 8 | Security (CWE-78, CWE-117, CWE-20) |
| **Body Validation** | 6 | Security + Markdown support |
| **GH CLI Detection** | 4 | Environment validation |
| **Issue Number Parsing** | 5 | Output parsing |
| **Command Building** | 5 | gh CLI integration |
| **Issue Creation** | 7 | Core workflow |
| **Security Validation** | 5 | CWE-22, CWE-59, CWE-78 |
| **Result Data Class** | 3 | Data structures |
| **CLI Argument Parsing** | 10 | Command-line interface |
| **CLI Output Formatting** | 9 | Human + JSON output |
| **CLI Main Function** | 6 | Integration |
| **Full Workflow** | 3 | End-to-end |
| **Agent Coordination** | 3 | Multi-agent flow |
| **Markdown Formatting** | 5 | Issue body format |
| **Research Log Parsing** | 4 | Input processing |
| **Error Handling** | 10 | Resilience |
| **TOTAL** | **95+** | Comprehensive coverage |

---

## Security Testing Coverage

### CWE Vulnerabilities Tested

1. **CWE-78: Command Injection** ✅
   - Shell metacharacters rejected
   - Subprocess safety validated
   - 8 test cases

2. **CWE-117: Log Injection** ✅
   - Control characters blocked
   - Audit log sanitization
   - 3 test cases

3. **CWE-20: Input Validation** ✅
   - Length limits enforced
   - Format validation
   - 10 test cases

4. **CWE-22: Path Traversal** ✅
   - Path validation
   - Whitelist enforcement
   - 2 test cases

5. **CWE-59: Symlink Following** ✅
   - Symlink detection
   - TOCTOU prevention
   - 2 test cases

---

## Success Criteria

### Red Phase (Current) ✅
- [x] 95+ tests written
- [x] All tests FAIL (no implementation)
- [x] Verification script confirms red phase
- [x] Test coverage designed for 85%+
- [x] Security tests comprehensive

### Green Phase (Next)
- [ ] Library tests PASS (50/50)
- [ ] CLI tests PASS (20/20)
- [ ] Integration tests PASS (15/15)
- [ ] Agent tests PASS (10/10)
- [ ] Code coverage 85%+
- [ ] No security vulnerabilities

### Refactor Phase (Final)
- [ ] Code follows project patterns
- [ ] Error messages helpful
- [ ] Documentation complete
- [ ] Performance acceptable
- [ ] Ready for production

---

## Common Test Patterns

### Mocking subprocess.run
```python
@patch('subprocess.run')
def test_example(mock_run):
    mock_run.return_value = Mock(
        returncode=0,
        stdout="output",
    )
```

### Mocking check_gh_available
```python
@patch('plugins.autonomous_dev.lib.github_issue_automation.check_gh_available')
def test_example(mock_check):
    mock_check.return_value = True
```

### Testing validation errors
```python
def test_validation_error():
    with pytest.raises(ValueError, match="error message"):
        validate_issue_title("invalid; title")
```

---

## Debugging Failed Tests

### View detailed errors
```bash
python -m pytest tests/unit/lib/test_github_issue_automation.py -vv --tb=long
```

### Run specific test
```bash
python -m pytest tests/unit/lib/test_github_issue_automation.py::TestValidateIssueTitle::test_validate_title_valid -vv
```

### Run tests matching pattern
```bash
python -m pytest tests/unit/lib/test_github_issue_automation.py -k "validation" -v
```

---

## Next Steps

1. ✅ **Complete**: Write comprehensive test suite (95+ tests)
2. **Current**: Verify TDD red phase
3. **Next**: Implement library (`github_issue_automation.py`)
4. **Then**: Implement CLI script (`create_issue.py`)
5. **Then**: Create agent (`issue-creator.md`)
6. **Then**: Create command (`create-issue.md`)
7. **Finally**: Run all tests - should PASS!

---

## Related Documentation

- **Detailed Summary**: `tests/ISSUE_58_TDD_RED_SUMMARY.md`
- **Implementation Plan**: See planner agent output
- **Research Findings**: See researcher agent session logs
- **Security Patterns**: `docs/SECURITY.md`
- **Testing Guide**: `plugins/autonomous-dev/skills/testing-guide/SKILL.md`

---

**Last Updated**: 2025-01-09
**Status**: RED PHASE COMPLETE ✅
**Next**: Begin implementation (GREEN PHASE)
