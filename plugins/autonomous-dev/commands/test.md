---
description: Run test suite (pytest) or GenAI validation - supports unit, integration, UAT, uat-genai, architecture-genai
---

# Run Tests & Validation

Execute automated tests (pytest) or GenAI quality validation - all under one command.

## Usage

```bash
# Automated Tests (pytest) - Fast
/test                   # All automated tests (default)
/test unit              # Unit tests only (< 1s)
/test integration       # Integration tests only (< 10s)
/test uat               # UAT tests only (< 60s, automated)
/test all               # Explicit: all automated tests

# GenAI Validation - Comprehensive
/test uat-genai         # GenAI: UX quality & goal alignment (2-5min)
/test architecture      # GenAI: Architectural intent validation (2-5min)

# Combined Workflows
/test unit integration  # Multiple test layers
/test all uat-genai architecture  # Complete pre-release validation
```

## What This Does

Two modes in one command: **automated testing** (pytest) and **GenAI validation** (Claude).

### Mode 1: Automated Tests (pytest)

| Target | Directory | Speed | Tool | Validates |
|--------|-----------|-------|------|-----------|
| `unit` | `tests/unit/` | < 1s | pytest | Individual functions |
| `integration` | `tests/integration/` | < 10s | pytest | Components together |
| `uat` | `tests/uat/` | < 60s | pytest | User workflows work |
| `all` | `tests/` | < 60s+ | pytest | Everything |

**Runs**:
```bash
# Python
pytest tests/[target]/ --cov=src --cov-report=term-missing -v

# JavaScript/TypeScript
npm test -- --coverage
```

---

### Mode 2: GenAI Validation (Claude)

| Target | Speed | Tool | Validates |
|--------|-------|------|-----------|
| `uat-genai` | 2-5min | Claude | UX quality, goal alignment, friction points |
| `architecture` | 2-5min | Claude | Intent preservation, drift detection |

**What It Does**:

#### `/test uat-genai`
Analyzes user workflows and assesses:
- ✅ Goal alignment (from PROJECT.md)
- ✅ UX quality (friction points, clarity)
- ✅ Error handling quality
- ✅ Performance vs targets
- ✅ Accessibility

**Output**: UX score (X/10) + recommendations

---

#### `/test architecture`
Validates implementation matches documented intent:
- ✅ PROJECT.md-first architecture enforced?
- ✅ 8-agent pipeline order correct?
- ✅ Model optimization followed?
- ✅ Context management implemented?
- ✅ Agent specialization (no duplication)?
- ✅ All 14 architectural principles

**Output**: Alignment report (✅/⚠️/❌) + drift detection

---

### Why One Command?

**Unified interface**: All quality checks under `/test`
- `/test unit` → Fast automated testing
- `/test uat-genai` → Comprehensive UX validation
- `/test architecture` → Intent validation

**Clear semantics**: Different targets, not different commands
- Automated: `unit`, `integration`, `uat`, `all`
- GenAI: `uat-genai`, `architecture`

## Example Output

```
Running test suite...

=================== test session starts ====================
collected 45 items

tests/unit/test_auth.py::test_login PASSED           [ 2%]
tests/unit/test_auth.py::test_logout PASSED          [ 4%]
tests/unit/test_user.py::test_create_user PASSED     [ 6%]
...
tests/integration/test_workflow.py::test_full_flow PASSED [100%]

=================== 45 passed in 2.34s =====================

Coverage Report:
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
src/auth.py               42      3    93%   45-48
src/user.py               35      2    94%   67-68
src/models/base.py        28      0   100%
-----------------------------------------------------
TOTAL                    105      5    95%

✅ All tests passing
✅ Coverage: 95% (exceeds 80% threshold)

HTML report: file://./htmlcov/index.html
```

## When to Use

- After implementing features
- After making code changes
- Before committing code
- To verify bug fixes
- To check test coverage

## Coverage Thresholds

- **Target**: ≥80% coverage on all code
- **Fails**: If coverage drops below 80% (configurable)

## Test Categories

Tests are organized by type:

```
tests/
├── unit/              # Fast, isolated tests
├── integration/       # Multi-component tests
├── progression/       # Baseline tracking tests
└── regression/        # Bug prevention tests
```

## Troubleshooting

### Tests not found
```bash
# Ensure pytest installed
pip install pytest pytest-cov

# Or for JS/TS
npm install
```

### Tests failing
1. Check error messages in output
2. Run specific test: `pytest tests/unit/test_auth.py::test_login -v`
3. Use debugger: `pytest --pdb`

### Low coverage
1. View HTML report: `open htmlcov/index.html`
2. Add tests for uncovered lines
3. Use `/test` again to verify

## Auto-Run vs Manual

This command is **manual** (you control when it runs).

**Alternative**: The `auto_test.py` hook can run automatically:
- On file save (related tests only)
- Before git commit (pre-commit hook)
- Before git push (pre-push hook)

**Recommended**: Use `/test` manually for full control.

## Complete Testing Workflow

### Daily Development (Fast)
```bash
/test unit              # < 1s, instant feedback
```

### Before Commit (Quick)
```bash
/test unit integration  # < 10s, pre-commit check
```

### Before Release (Comprehensive)
```bash
# Step 1: Automated tests
/test all               # < 60s, all pytest tests

# Step 2: Quality validation
/test uat-genai architecture  # 2-5min each, GenAI validation
```

### Monthly Maintenance
```bash
/test architecture      # Check for architectural drift
```

**See**: `docs/TESTING-DECISION-MATRIX.md` for complete guide

## Related Commands

- `/format` - Format code before testing
- `/security-scan` - Security scan after tests pass
- `/full-check` - Run all checks (format + test + security)

---

## Quick Reference

| Command | Tool | Speed | Validates | When |
|---------|------|-------|-----------|------|
| `/test unit` | pytest | < 1s | Functions | During dev |
| `/test integration` | pytest | < 10s | Workflows | Before commit |
| `/test uat` | pytest | < 60s | User journeys | Before release |
| `/test all` | pytest | < 60s+ | Everything | Pre-commit, pre-release |
| `/test uat-genai` | Claude | 2-5min | UX quality | Before release |
| `/test architecture` | Claude | 2-5min | Intent | Before release, monthly |

---

## Why This Design?

**One command, multiple targets**: All quality checks unified
- Easier to remember (`/test` for everything)
- Clear what each target does
- Easy to combine: `/test all uat-genai architecture`

**Two validation modes**:
- **Automated** (`unit`, `integration`, `uat`) → Fast pytest
- **GenAI** (`uat-genai`, `architecture`) → Comprehensive Claude

**Result**: Complete testing strategy under one intuitive command

---

**Run `/test` with specific targets for fast feedback, or combine multiple targets for comprehensive validation.**
