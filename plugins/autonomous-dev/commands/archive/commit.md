---
description: Quick commit - format + unit tests + security → commit locally (< 5s)
---

# Quick Commit (Level 1)

**Fast validation and commit for rapid iteration during development**

---

## Usage

```bash
/commit
```

**Time**: < 5 seconds
**Validates**: Format, unit tests, security
**Pushes**: No (local commit only)

---

## What This Does

1. Run `/format` (black, isort, prettier)
2. Run unit tests only (fast subset)
3. Run `/security-scan` (secrets detection)
4. Analyze `git diff` to generate conventional commit message
5. **Commit locally** (don't push)

---

## Expected Output

```
Running Level 1: Quick Commit...

┌─ Quick Integrity Checks ────────────────────┐
│  ✅ Format: PASSED                           │
│  ✅ Unit Tests: PASSED (45/45, 0.8s)         │
│  ✅ Security: PASSED (no secrets detected)   │
└──────────────────────────────────────────────┘

Analyzing changes...
- Modified: src/auth.py (+35, -12)
- Modified: tests/unit/test_auth.py (+18, -0)

Generated commit message:
┌──────────────────────────────────────────────┐
│ feat(auth): add JWT refresh token support   │
│                                              │
│ - Added refresh token endpoint              │
│ - Updated token expiration logic             │
│ - Added tests for refresh flow              │
└──────────────────────────────────────────────┘

✅ Committed locally (abc1234)
💡 Run '/commit-push' when ready to push to GitHub
```

---

## When to Use

- ✅ Rapid iteration during development
- ✅ Quick checkpoint commits
- ✅ Before switching branches
- ✅ Early in feature development

---

## Related Commands

- `/commit-check` - Level 2: Full tests + coverage (60s)
- `/commit-push` - Level 3: Full integrity + push to GitHub (3min)
- `/commit-release` - Level 4: Release with version bump (7min)

---

## Implementation

```bash
# 1. Format
/format

# 2. Run unit tests (use pytest -m unit if markers configured)
pytest tests/unit/ -v --tb=short

# 3. Security scan
/security-scan

# 4. Analyze changes
git status
git diff --cached
git diff

# 5. Generate commit message (analyze file changes, test changes, type)
# Type detection:
# - feat: new files, new functions, new features
# - fix: changes to existing code fixing bugs
# - docs: only documentation changes
# - refactor: code restructure without behavior change
# - test: only test changes
# - chore: config, dependencies, build scripts

# 6. Create commit
git add .  # Stage any unstaged changes if needed
git commit -m "$(cat <<'EOF'
{generated_message}

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# 7. Show status
echo "✅ Committed locally"
echo "💡 Run '/commit-push' when ready to push to GitHub"
```

---

## Error Handling

If checks fail:
```
❌ Quick Commit FAILED

Issues found:
1. ❌ Format check failed (3 files need formatting)
   Fix: Run /format and retry

2. ❌ Unit tests failed (2/45 failed)
   Fix: Review test failures and fix code

3. ❌ Security scan found issues (1 secret detected)
   Fix: Remove secrets and retry

Cannot proceed with commit. Please fix issues above.
```

---

**Use this for rapid iteration during development. No push to remote.**
