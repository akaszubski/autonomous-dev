---
description: Standard commit - all tests + coverage + doc check → commit locally (< 60s)
---

# Standard Commit (Level 2)

**Complete test validation before committing - for feature completion**

---

## Usage

```bash
/commit-check
```

**Time**: < 60 seconds
**Validates**: Format, all tests, coverage (80%+), doc sync
**Pushes**: No (local commit only)

---

## What This Does

1. All from Level 1 (format, unit tests, security)
2. Run ALL tests (unit + integration + UAT)
3. Check test coverage (80%+ required)
4. Check documentation sync status
5. **Commit locally** (don't push)

---

## Expected Output

```
Running Level 2: Standard Commit...

┌─ Standard Integrity Checks ─────────────────┐
│                                              │
│ Code Quality:                                │
│  ✅ Format: PASSED                           │
│  ✅ Unit Tests: PASSED (45/45, 0.8s)         │
│  ✅ Integration Tests: PASSED (12/12, 4.2s)  │
│  ✅ UAT Tests: PASSED (8/8, 15.3s)           │
│  ✅ Coverage: 92% (target: 80%+) ✅          │
│  ✅ Security: PASSED                         │
│                                              │
│ Documentation:                               │
│  ✅ Docstring coverage: 95%                  │
│  ⚠️  README.md out of sync (minor)           │
│                                              │
│ Total time: 21.5s                            │
│ Status: PASSED (1 warning)                   │
│                                              │
└──────────────────────────────────────────────┘

Warning: README.md may need update
Run '/commit-push' to auto-sync documentation

✅ Committed locally (def5678)
💡 Run '/commit-push' when ready to push to GitHub
```

---

## When to Use

- ✅ Feature completion
- ✅ Before code review
- ✅ After significant changes
- ✅ Before sharing branch with team

---

## Related Commands

- `/commit` - Level 1: Quick commit (5s)
- `/commit-push` - Level 3: Full integrity + push to GitHub (3min)
- `/commit-release` - Level 4: Release with version bump (7min)

---

## Implementation

```bash
# 1-3. Run Level 1 checks
/format
pytest tests/unit/ -v --tb=short
/security-scan

# 4. Run all tests
/test

# 5. Check coverage
pytest --cov=src --cov-report=term-missing

# 6. Check doc sync (simplified check)
# - Compare PROJECT.md modification time vs README.md
# - Warn if README older than PROJECT.md
stat -f %m PROJECT.md
stat -f %m README.md

# 7. Analyze changes and commit
git status
git diff --cached
git diff

git add .
git commit -m "$(cat <<'EOF'
{generated_message}

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

echo "✅ Committed locally"
echo "💡 Run '/commit-push' when ready to push to GitHub"
```

---

## Coverage Requirements

**Minimum**: 80% line coverage

**What's checked**:
- Line coverage
- Branch coverage
- Missing coverage report

**If coverage < 80%**:
```
❌ Coverage check failed: 72% (target: 80%+)

Missing coverage in:
- src/auth.py: Lines 45-52, 78-82
- src/utils.py: Lines 103-110

Add tests for these areas and retry.
```

---

## Error Handling

If checks fail:
```
❌ Standard Commit FAILED

Issues found:
1. ✅ Format: PASSED
2. ✅ Unit Tests: PASSED
3. ❌ Integration Tests: FAILED (1/12 failed)
   Fix: Review test_api_integration.py:45
4. ❌ Coverage: 72% (target: 80%+)
   Fix: Add tests for src/auth.py lines 45-52

Cannot proceed with commit. Please fix issues above.

💡 Tip: Run '/commit' for quick commit (skips full tests)
```

---

**Use this before code review or when feature is complete. Ensures quality.**
