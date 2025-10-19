---
description: Generate conventional commit message and create commit (optionally run quality checks first)
---

# Smart Commit

Generate a conventional commit message and create a commit with optional quality checks.

## Usage

### Simple Commit
```bash
/commit
```
(Analyzes changes and generates commit message)

### Commit with Message
```bash
/commit "feat: add user authentication"
```

### Commit with Full Check
```bash
/commit --check
```
(Runs `/full-check` before committing)

## What This Does

1. **Analyze Changes**:
   - Run `git diff --cached` to see staged changes
   - Identify type of change (feat/fix/docs/refactor/test/chore)
   - Generate descriptive commit message

2. **Format Message** (Conventional Commits):
   ```
   <type>(<scope>): <description>

   [optional body]

   [optional footer]
   ```

3. **Create Commit**:
   - Stage changes if not already staged
   - Create commit with generated message
   - Show commit summary

## Conventional Commit Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature | `feat: add user authentication` |
| `fix` | Bug fix | `fix: resolve login timeout issue` |
| `docs` | Documentation only | `docs: update API reference` |
| `refactor` | Code restructure | `refactor: simplify auth logic` |
| `test` | Test additions | `test: add unit tests for auth` |
| `chore` | Maintenance tasks | `chore: update dependencies` |
| `style` | Code formatting | `style: format with black` |
| `perf` | Performance improvement | `perf: optimize database queries` |
| `ci` | CI/CD changes | `ci: add GitHub Actions workflow` |

## Example Output

```
Analyzing changes...

Files to commit:
  M src/auth.py
  M src/models/user.py
  A tests/unit/test_auth.py
  M CHANGELOG.md

Change analysis:
- Type: Feature (new functionality added)
- Scope: auth
- Files: 4 modified
- Lines: +150 -20

Generated commit message:
┌─────────────────────────────────────────────────────┐
│ feat(auth): add JWT authentication with refresh    │
│                                                     │
│ - Implemented JWT-based authentication              │
│ - Added password hashing with bcrypt                │
│ - Added login and refresh token endpoints           │
│ - Added 80% test coverage for auth module           │
│ - Updated CHANGELOG with authentication feature     │
│                                                     │
│ Closes #42                                          │
└─────────────────────────────────────────────────────┘

Proceed with this commit message? [Y/n]:
```

## Commit Message Guidelines

### Good Commit Messages ✅
```
feat: add user authentication with JWT tokens
fix: resolve race condition in session cleanup
docs: update README with installation instructions
refactor: extract validation logic into separate module
test: add integration tests for payment workflow
```

### Bad Commit Messages ❌
```
update stuff
fixed bug
changes
WIP
asdf
```

## Scope (Optional but Recommended)

Add scope to provide context:

```
feat(auth): add JWT authentication
fix(db): resolve connection pool leak
docs(api): add endpoint documentation
refactor(core): simplify error handling
```

## Breaking Changes

For breaking changes, add `!` and footer:

```
feat(api)!: change authentication endpoint

BREAKING CHANGE: Authentication endpoint moved from /auth to /api/v2/auth
Users must update client code to use new endpoint.

Closes #123
```

## With Quality Checks

```bash
/commit --check
```

This runs:
1. `/format` - Format code
2. `/test` - Run tests
3. `/security-scan` - Security check
4. `/commit` - Create commit (if all passed)

**Output**:
```
Running quality checks before commit...

✅ Formatting: PASSED
✅ Tests: PASSED (45 tests, 95% coverage)
✅ Security: PASSED

All checks passed. Proceeding with commit...

[main 1a2b3c4] feat(auth): add JWT authentication
 4 files changed, 150 insertions(+), 20 deletions(-)
 create mode 100644 tests/unit/test_auth.py
```

## Interactive Mode

When message generated, you can:
- **Accept**: Press `Y` or Enter
- **Edit**: Press `E` to modify message
- **Cancel**: Press `N` or Ctrl+C

## Git Status Integration

Before committing, see what's staged:

```bash
git status
```

**Output**:
```
Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
    modified:   src/auth.py
    modified:   src/models/user.py
    new file:   tests/unit/test_auth.py
    modified:   CHANGELOG.md
```

## Commit History

After committing, view history:

```bash
git log --oneline -5
```

**Output**:
```
1a2b3c4 feat(auth): add JWT authentication
5f6g7h8 fix(db): resolve connection pool leak
9i0j1k2 docs: update README
3l4m5n6 test: add unit tests for user model
7o8p9q0 refactor: simplify validation logic
```

## Best Practices

### Before Committing
1. ✅ Review changes: `git diff`
2. ✅ Run tests: `/test`
3. ✅ Format code: `/format`
4. ✅ Security scan: `/security-scan`
5. ✅ Update CHANGELOG
6. ✅ Stage files: `git add`

**Or simply**: `/commit --check` (does all automatically)

### Commit Frequency
- ✅ Commit logical units of work
- ✅ One feature/fix per commit
- ✅ Commits should be atomic (reversible)
- ❌ Don't commit broken code
- ❌ Don't commit large unrelated changes together

### Message Quality
- ✅ Describe **what** and **why** (not how)
- ✅ Use imperative mood ("add" not "added")
- ✅ Reference issues when applicable
- ✅ Keep subject under 72 characters
- ✅ Use body for detailed explanation

## Troubleshooting

### No changes to commit
```
git status shows nothing staged

Fix:
1. git add <files>
2. OR: git add .
3. Then: /commit
```

### Commit message too short
```
Error: Commit message must be descriptive

Fix: Provide more context in description
```

### Pre-commit hooks fail
```
Hooks detected issues (formatting, tests, security)

Fix:
1. Address hook failures
2. Re-stage files if modified
3. Try /commit again
```

## Related Commands

- `/format` - Format code before commit
- `/test` - Run tests before commit
- `/security-scan` - Security check before commit
- `/full-check` - Run all checks before commit
- `/auto-implement` - Complete autonomous workflow

---

**Use this to create well-formatted, conventional commits with optional quality validation.**
