---
description: Run complete quality check (format + test + security) - the manual equivalent of automatic hooks
---

# Full Quality Check

Run all quality checks in sequence: format → test → security scan.

## Usage

```bash
/full-check
```

## What This Does

Executes the complete quality pipeline:

```
1. Format code       (/format)
   ↓
2. Run tests         (/test)
   ↓
3. Security scan     (/security-scan)
   ↓
4. Generate report
```

## Example Output

```
Running full quality check...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣  FORMATTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Running black...
✅ Reformatted 3 files

Running isort...
✅ Sorted imports in 2 files

Running ruff...
✅ Fixed 1 issue

Formatting: ✅ PASSED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2️⃣  TESTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Running pytest with coverage...

45 tests passed in 2.34s
Coverage: 95% (exceeds 80% threshold)

Testing: ✅ PASSED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3️⃣  SECURITY SCAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Secrets detection: ✅ No secrets found
Code analysis: ✅ No critical issues
Dependencies: ✅ All up to date

Security: ✅ PASSED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 FINAL REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Formatting: PASSED
✅ Testing: PASSED (45 tests, 95% coverage)
✅ Security: PASSED (no critical issues)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 ALL CHECKS PASSED

Your code is ready to commit!
```

## When to Use

### Recommended Usage
- Before every commit
- Before creating pull requests
- Before deploying
- After implementing features

### Quick Check Workflow
```bash
# 1. Implement feature
# (code changes)

# 2. Run full check
/full-check

# 3. If passed, commit
/commit "feat: add user authentication"

# 4. Clear context
/clear
```

## vs. Individual Commands

| Scenario | Command | Why |
|----------|---------|-----|
| Quick formatting | `/format` | Fast, just style fixes |
| Test verification | `/test` | Focus on tests only |
| Security focus | `/security-scan` | Check security only |
| **Before commit** | **`/full-check`** | **Complete validation** |

## Failure Handling

If any check fails, the pipeline stops:

### Formatting Fails
```
❌ black found formatting issues

Fix: Review changes with git diff
Then: Commit formatted files
```

### Tests Fail
```
❌ 3 tests failing

1. tests/test_auth.py::test_login - AssertionError
2. tests/test_user.py::test_create - ValueError
3. tests/test_db.py::test_query - ConnectionError

Fix: Address failing tests
Then: Re-run /full-check
```

### Security Scan Fails
```
❌ 2 critical security issues found

1. src/auth.py:42 - Hardcoded API key
2. src/db.py:67 - SQL injection risk

Fix: Address security issues
Then: Re-run /full-check
```

## Auto-Hooks vs Manual Check

This command is **manual** (you control when it runs).

**Comparison**:

| Aspect | Auto-Hooks | `/full-check` |
|--------|------------|---------------|
| When runs | Automatic (on save/commit) | Manual (you trigger) |
| Control | Less (automatic) | Full (you decide) |
| Feedback | Immediate | On-demand |
| Workflow | Passive | Active |

**Recommended**: Use `/full-check` manually for explicit quality validation.

**Benefit**: You see exactly what's being checked and can address issues before committing.

## Time Estimate

- **Small projects**: ~30 seconds
- **Medium projects**: 1-2 minutes
- **Large projects**: 2-5 minutes

## Optimization Tips

### Faster Checks
```bash
# Format only changed files
black $(git diff --name-only | grep '\.py$')

# Run only failed tests
pytest --last-failed

# Skip slow tests in quick checks
pytest -m "not slow"
```

### Parallel Execution
Formatting and security scans can run in parallel:
```bash
# Format while running security scan
black . & bandit -r src/ -ll
```

## Related Commands

- `/format` - Format code only
- `/test` - Run tests only
- `/security-scan` - Security scan only
- `/commit` - Commit after checks pass
- `/auto-implement` - Full autonomous workflow

---

**This is the manual equivalent of automatic hooks - giving you full control over when quality checks run.**
