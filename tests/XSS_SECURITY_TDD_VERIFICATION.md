# TDD Red Phase Verification - XSS Security Fix

**Status**: RED (All tests failing as expected)
**Date**: 2025-11-05
**Security Level**: MEDIUM severity XSS vulnerability
**Test Files Created**: 2

## Test Suite Summary

### 1. Unit Tests: test_auto_add_to_regression_security.py
**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/hooks/test_auto_add_to_regression_security.py`
**Test Count**: 40 tests
**Status**: FAILING (ImportError - functions don't exist yet)

**Test Categories**:
- validate_python_identifier(): 10 tests
  - Empty string rejection
  - Python keyword rejection
  - Special character rejection
  - Dunder method rejection
  - Length limit enforcement
  - Valid identifier acceptance

- sanitize_user_description(): 15 tests
  - HTML entity escaping
  - XSS payload prevention
  - Control character removal
  - Unicode handling
  - Length truncation

- Integration tests: 15 tests
  - XSS prevention in all 3 generation functions
  - Code injection prevention
  - Valid Python output verification
  - Path traversal prevention
  - Null byte injection prevention

### 2. Regression Tests: test_xss_vulnerability_fix.py
**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/regression/test_xss_vulnerability_fix.py`
**Test Count**: 20 tests
**Status**: FAILING (ImportError - functions don't exist yet)

**Test Categories**:
- XSS vulnerability regression (5 tests)
  - Script tag injection
  - Img onerror injection
  - Event handler injection
  - Code injection via module name
  - All generation functions escape XSS

- Code injection regression (5 tests)
  - Python keyword injection
  - Dunder method injection
  - Path traversal injection
  - Null byte injection
  - SQL injection pattern escaping

- Input validation regression (5 tests)
  - validate_python_identifier() enforced
  - sanitize_user_description() enforced
  - Generation functions call validation
  - No f-string interpolation
  - Maximum length enforced

- Meta test (1 test)
  - Regression suite existence verification

## Current Test Failure

```
ImportError: cannot import name 'validate_python_identifier' from 'auto_add_to_regression'
ImportError: cannot import name 'sanitize_user_description' from 'auto_add_to_regression'
```

**Expected**: These functions do not exist yet (TDD red phase)
**Next Step**: Implementer adds functions to make tests pass

## Implementation Requirements

The tests verify these security functions will exist:

### 1. validate_python_identifier(identifier: str) -> str
**Purpose**: Validate module names to prevent code injection
**Returns**: Validated identifier (raises ValueError if invalid)
**Checks**:
- Not empty
- Not a Python keyword (import, exec, eval, class, def)
- Not a dunder method (__import__, __builtins__)
- No special characters (only alphanumeric + underscore)
- Max 100 characters
- Valid Python identifier syntax
- No path traversal (../, /)
- No null bytes (\x00)

### 2. sanitize_user_description(description: str) -> str
**Purpose**: Sanitize user descriptions to prevent XSS
**Returns**: HTML-entity-encoded description
**Transformations**:
- Escape HTML entities: <, >, &, ", '
- Remove control characters (\x00-\x1F)
- Preserve safe unicode
- Truncate to 500 characters (with "..." indicator)

### 3. Convert Generation Functions to Use Template
**Functions to update**:
- generate_feature_regression_test()
- generate_bugfix_regression_test()
- generate_performance_baseline_test()

**Changes required**:
- Replace f-strings with string.Template
- Call validate_python_identifier() on module names
- Call sanitize_user_description() on user input
- Use safe template substitution (not f-string interpolation)

## Attack Vectors Tested

The test suite verifies protection against:

1. **XSS Attacks**:
   - `<script>alert('XSS')</script>`
   - `<img src=x onerror="alert(1)">`
   - `<a href="#" onclick="malicious()">Click</a>`
   - `<iframe src="javascript:alert(1)"></iframe>`
   - `<svg onload="alert(1)">`

2. **Code Injection**:
   - Python keywords as identifiers: `import`, `exec`, `eval`
   - Dunder methods: `__import__`, `__builtins__`
   - Triple quote escape: `""" + malicious_code + """`

3. **Path Traversal**:
   - `../../../etc/passwd`
   - `module/../../attack`

4. **Null Byte Injection**:
   - `module\x00attack`

5. **SQL Injection**:
   - `'; DROP TABLE users; --`

## Running the Tests

### Check TDD Red Phase (should fail)
```bash
cd /Users/akaszubski/Documents/GitHub/autonomous-dev

# Run unit tests (should fail with ImportError)
.venv/bin/python -m pytest tests/unit/hooks/test_auto_add_to_regression_security.py -v

# Run regression tests (should fail with ImportError)
.venv/bin/python -m pytest tests/regression/test_xss_vulnerability_fix.py -v
```

### After Implementation (should pass)
```bash
# Run all security tests
.venv/bin/python -m pytest tests/unit/hooks/test_auto_add_to_regression_security.py tests/regression/test_xss_vulnerability_fix.py -v

# Run with coverage
.venv/bin/python -m pytest tests/unit/hooks/test_auto_add_to_regression_security.py tests/regression/test_xss_vulnerability_fix.py --cov=plugins/autonomous-dev/hooks/auto_add_to_regression --cov-report=term-missing
```

## Test Quality Metrics

- **Total Tests**: 60 tests
- **Coverage Target**: 100% of security functions
- **Attack Vectors Covered**: 5 categories (XSS, code injection, path traversal, null byte, SQL injection)
- **Regression Protection**: Permanent tests ensure vulnerability never returns
- **TDD Compliance**: Tests written BEFORE implementation (red phase verified)

## Success Criteria

Tests will pass when:
1. validate_python_identifier() function exists and validates correctly
2. sanitize_user_description() function exists and sanitizes correctly
3. All 3 generation functions use Template (not f-strings)
4. All 3 generation functions call validation on module names
5. All 3 generation functions call sanitization on user descriptions
6. Generated Python code is syntactically valid
7. All XSS payloads are escaped (not executable)
8. All code injection attempts are rejected (ValueError raised)

## Security Compliance

This test suite ensures compliance with:
- **OWASP**: Input validation, output encoding
- **CWE-79**: Cross-site Scripting (XSS)
- **CWE-94**: Code Injection
- **CWE-20**: Improper Input Validation

## Next Steps for Implementer

1. Read this verification document
2. Review test failures to understand requirements
3. Implement validate_python_identifier() function
4. Implement sanitize_user_description() function
5. Convert generation functions to use Template
6. Run tests to verify they pass
7. Check test coverage (should be 100% for new functions)

## Reference Documents

- Security Audit: `docs/sessions/SECURITY_AUDIT_REGRESSION_TEST_SUITE_20251105.md`
- Implementation Plan: (planner agent output)
- Test Files:
  - Unit: `tests/unit/hooks/test_auto_add_to_regression_security.py`
  - Regression: `tests/regression/test_xss_vulnerability_fix.py`
