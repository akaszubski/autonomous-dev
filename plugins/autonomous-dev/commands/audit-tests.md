---
name: audit-tests
description: AST-based test coverage analysis - identifies untested code and coverage gaps
argument-hint: Optional flags - --layer [unit|integration|e2e], --no-skip, --fix
allowed-tools: [Task, Bash, Glob, Grep]
---

# Test Coverage Audit

Analyze test coverage using AST-based static analysis and pytest execution. Identifies coverage gaps, skipped tests, and test quality issues.

## Implementation

Invoke the test-coverage-auditor agent to perform coverage analysis.

ARGUMENTS: {{ARGUMENTS}}

Parse the ARGUMENTS for optional flags:
- `--layer [unit|integration|e2e]`: Filter analysis to specific test layer
- `--no-skip`: Omit skipped tests section from report
- `--fix`: Generate test stubs for coverage gaps (future feature)

Use the Task tool to invoke the test-coverage-auditor agent with subagent_type="test-coverage-auditor" and provide the flags.

## What This Does

Performs comprehensive test coverage analysis:

1. **AST Analysis**: Scans source files for testable items (public functions/classes)
2. **Pytest Execution**: Runs tests to determine actual coverage
3. **Gap Detection**: Identifies untested functions and classes
4. **Skip Analysis**: Finds SKIPPED/XFAIL tests with reasons
5. **Layer Coverage**: Analyzes coverage per test layer (unit/integration/e2e)
6. **Quality Metrics**: Calculates coverage percentage, skip rate, warnings

**Time**: 3-5 minutes (depends on test suite size)

## Usage

```bash
# Analyze all test coverage
/audit-tests

# Analyze only unit tests
/audit-tests --layer unit

# Analyze integration tests
/audit-tests --layer integration

# Analyze without skipped tests section
/audit-tests --no-skip

# Combine flags
/audit-tests --layer unit --no-skip
```

## Output

The auditor provides a comprehensive report:

### Coverage Summary
- Total testable items
- Total covered items
- Coverage percentage
- Total tests executed
- Skip rate

### Coverage Gaps
For each untested item:
- Item name (function/class)
- Item type
- File path
- Test layer missing coverage

### Skipped Tests
For each skipped/xfailed test:
- Test identifier
- Skip reason
- Skip type (SKIPPED/XFAIL)

### Layer Coverage
Per-layer statistics:
- Layer name (unit/integration/e2e)
- Total tests
- Passed tests
- Coverage percentage

### Warnings
Quality issues found:
- High skip rate (>10%)
- Syntax errors in source files
- Tests skipped without reasons
- pytest execution failures

## When to Use

Use `/audit-tests` when:

- **Before release**: Ensure adequate test coverage
- **Code review**: Validate new features are tested
- **Refactoring**: Verify tests still cover changed code
- **CI/CD**: Check coverage thresholds
- **Onboarding**: Understand test coverage landscape

## Security

- **Path traversal prevention**: Validates all paths within project root
- **Secret sanitization**: Redacts API keys/tokens from skip reasons
- **No shell injection**: Uses subprocess.run with shell=False
- **Graceful degradation**: Handles syntax errors, missing pytest

## Coverage Targets

**Recommended thresholds**:
- Critical paths: 100%
- New features: 80%+
- Overall project: 70%+

**Skip rate threshold**:
- Warning if >10% of tests are skipped

## Example Output

```
Coverage Summary:
- Total testable items: 45
- Total covered: 38
- Coverage: 84.4%
- Total tests: 120
- Skip rate: 5.8%

Coverage Gaps (7):
- calculate_discount (function) in src/pricing.py [unit]
- PaymentProcessor.refund (class) in src/payments.py [integration]
- export_report (function) in src/reports.py [unit]

Skipped Tests (7):
- test_api.py::test_payment_flow - External API unavailable [SKIPPED]
- test_auth.py::test_oauth_login - Flaky test, needs investigation [SKIPPED]

Layer Coverage:
- unit: 95 tests, 90 passed, 94.7% coverage
- integration: 20 tests, 18 passed, 90.0% coverage
- e2e: 5 tests, 5 passed, 100% coverage

Warnings:
- Test test_auth.py::test_oauth_login skipped without reason
```

## Related Commands

- `/auto-implement`: Implements features with TDD (includes test generation)
- `/health-check`: Validates overall project health (includes test validation)

## Summary

Use `/audit-tests` to understand test coverage, identify gaps, and improve test quality. Focus on critical paths and new features first.
