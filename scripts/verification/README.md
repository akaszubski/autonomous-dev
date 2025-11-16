# Verification Scripts

One-off verification scripts used during TDD development and issue resolution.

## Purpose

These scripts were created to verify specific TDD phases, fixes, or implementations:
- Verify red phase completion
- Validate test coverage
- Check regression suite
- Measure token reduction
- Apply test corrections

## Lifecycle

These are **historical artifacts**:
1. Created for specific issues/features
2. Used during development to verify TDD compliance
3. Archived here after verification complete
4. Gitignored to prevent repository bloat

## Current Verification Tools

For ongoing development, use:
- `pytest` - Run test suite
- `pytest --cov` - Coverage analysis
- `/test` - Run all automated tests
- `/review` - Code quality review

## See Also

- [tests/README.md](../../tests/README.md) - Test suite overview
- [docs/TESTING.md](../../docs/TESTING.md) - Testing strategy
