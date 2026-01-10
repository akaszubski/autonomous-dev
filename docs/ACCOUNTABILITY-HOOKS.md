# Accountability Hooks - Catching Missed Steps

**Purpose**: Use hooks to ensure you don't skip important SDLC steps

**Last Updated**: 2025-11-03

---

## The Key Insight

**Hooks CAN'T**: Detect intent ("implement X") - UserPromptSubmit is buggy

**Hooks CAN**: Validate you followed the process after you're done

---

## PreCommit Hooks - Your Quality Gates

**When**: Before `git commit` completes

**Purpose**: Block commits that skip important steps

### What You Can Enforce

| Step You Might Skip | Hook That Catches It | Status |
|---------------------|---------------------|--------|
| **PROJECT.md alignment** | `validate_project_alignment.py` | ✅ Already have |
| **Writing tests** | `enforce_tdd.py` or `auto_generate_tests.py` | ✅ Already have |
| **Security scanning** | `security_scan.py` | ✅ Already have |
| **Documentation updates** | `auto_update_docs.py` | ✅ Already have |
| **Code formatting** | `auto_format.py` | ✅ Already have |
| **Test coverage minimum** | `auto_enforce_coverage.py` | ⚠️ Need to enable |
| **No TODO/FIXME in code** | `check_todos.py` | ❌ Could add |
| **Commit message format** | `validate_commit_msg.py` | ❌ Could add |
| **Ran orchestrator** | `enforce_orchestrator.py` | ✅ Already have |

---

## Current PreCommit Hooks (What's Already Protecting You)

```json
{
  "hooks": {
    "PreCommit": [
      {
        "description": "Comprehensive validation pipeline",
        "hooks": [
          {
            "command": "python .claude/hooks/validate_project_alignment.py || exit 1"
          },
          {
            "command": "python .claude/hooks/security_scan.py || exit 1"
          },
          {
            "command": "python .claude/hooks/auto_generate_tests.py || exit 1"
          },
          {
            "command": "python .claude/hooks/auto_update_docs.py || exit 1"
          },
          {
            "command": "python .claude/hooks/validate_docs_consistency.py || exit 1"
          },
          {
            "command": "python .claude/hooks/auto_fix_docs.py || exit 1"
          }
        ]
      }
    ]
  }
}
```

**What these do**:

1. **validate_project_alignment.py** ✅
   - Checks: Does this commit align with PROJECT.md?
   - Blocks: Features outside SCOPE
   - Message: "This violates PROJECT.md constraints"

2. **security_scan.py** ✅
   - Checks: Secrets, API keys, vulnerable patterns
   - Blocks: Commits with hardcoded secrets
   - Message: "Found API key in line 42"

3. **auto_generate_tests.py** ✅
   - Checks: Are there tests for new code?
   - Action: Generates tests if missing
   - Blocks: If generation fails

4. **auto_update_docs.py** ✅
   - Checks: Did API change? Docs updated?
   - Action: Updates docs automatically
   - Message: "Updated README with new function"

5. **validate_docs_consistency.py** ✅
   - Checks: Docs match code reality?
   - Blocks: If drift detected
   - Message: "README mentions removed function"

6. **auto_fix_docs.py** ✅
   - Checks: Formatting, links, structure
   - Action: Auto-fixes what it can
   - Message: "Fixed 3 broken links"

---

## Additional Hooks You Could Enable

### 1. Enforce Test Coverage Minimum

**Hook**: `auto_enforce_coverage.py`

**What it does**:
```bash
# Blocks commit if test coverage < 80%
git commit -m "feat: add feature"
# → Hook runs pytest --cov
# → Coverage: 65%
# → ❌ BLOCKED: "Coverage 65% < 80% minimum"
```

**Enable it**:
```json
{
  "hooks": {
    "PreCommit": [
      {
        "hooks": [
          {
            "command": "python .claude/hooks/auto_enforce_coverage.py || exit 1"
          }
        ]
      }
    ]
  }
}
```

**Catches**: Skipping thorough testing

---

### 2. Enforce TDD (Tests Written First)

**Hook**: `enforce_tdd.py`

**What it does**:
```bash
git commit -m "feat: add feature"
# → Checks git history
# → Finds: Code added before tests
# → ❌ BLOCKED: "Tests must be written before implementation (TDD)"
```

**How it works**:
- Looks at git diff
- Checks if `tests/` files were modified AFTER `src/` files in commit history
- Blocks if code came first

**Catches**: Not following TDD (red-green-refactor)

---

### 3. Enforce Orchestrator Usage

**Hook**: `enforce_orchestrator.py`

**What it does**:
```bash
git commit -m "feat: add feature"
# → Checks: Did orchestrator run?
# → Looks for session logs
# → ❌ BLOCKED: "No orchestrator session found. Use /implement"
```

**Catches**: Manually coding instead of using autonomous workflow

---

### 4. Check for TODOs/FIXMEs

**Hook**: `check_todos.py` (NEW - we could create this)

**What it does**:
```bash
git commit -m "feat: add feature"
# → Scans code for TODO/FIXME
# → Finds: "// TODO: Handle edge case"
# → ⚠️  WARNING: "3 TODOs found. Create issues or fix before merge."
```

**Options**:
- Warn only (allow commit)
- Block (force resolution)
- Auto-create GitHub issues for each TODO

**Catches**: Shipping incomplete code

---

### 5. Validate Commit Message Format

**Hook**: `validate_commit_msg.py` (NEW - we could create this)

**What it does**:
```bash
git commit -m "added stuff"
# → Checks format: type(scope): description
# → ❌ BLOCKED: "Commit message must follow: feat|fix|docs(scope): description"

git commit -m "feat(auth): add JWT authentication"
# → ✅ PASS: Follows conventional commits
```

**Catches**: Poor commit messages

---

### 6. Enforce Code Review

**Hook**: `require_review.py` (NEW)

**What it does**:
```bash
git commit -m "feat: add feature"
# → Checks: Was reviewer agent invoked?
# → Looks for review session
# → ❌ BLOCKED: "Code review required. Run /implement to invoke reviewer."
```

**Catches**: Skipping code review step

---

### 7. Enforce Documentation for Public APIs

**Hook**: `require_docstrings.py` (NEW)

**What it does**:
```python
# In your code:
def public_api_function(param):  # No docstring!
    return param * 2

# Commit:
git commit -m "feat: add API"
# → ❌ BLOCKED: "public_api_function missing docstring"
```

**Catches**: Undocumented public APIs

---

### 8. Check Dependencies Changed

**Hook**: `check_dependencies.py` (NEW)

**What it does**:
```bash
git commit -m "feat: add feature"
# → Detects: New import added
# → Checks: Is it in requirements.txt?
# → ❌ BLOCKED: "requests imported but not in requirements.txt"
```

**Catches**: Missing dependency declarations

---

## PostCommit Hooks - After the Fact

**When**: After commit succeeds (but before push)

**Use cases**:
- Notify team on Slack
- Update project tracking
- Generate changelog
- Run extended tests

**Example**:
```json
{
  "hooks": {
    "PostCommit": [
      {
        "hooks": [
          {
            "command": "python scripts/update_changelog.py"
          },
          {
            "command": "python scripts/notify_team.py"
          }
        ]
      }
    ]
  }
}
```

**Catches**: Nothing (non-blocking), but ensures follow-up actions

---

## PrePush Hooks - Last Line of Defense

**When**: Before `git push` sends to remote

**Use cases**:
- Run full test suite (slow tests)
- Build verification
- Integration tests
- Final security scan

**Example**:
```json
{
  "hooks": {
    "PrePush": [
      {
        "hooks": [
          {
            "command": "pytest tests/ --slow || exit 1"
          },
          {
            "command": "npm run build || exit 1"
          }
        ]
      }
    ]
  }
}
```

**Catches**: Code that passes PreCommit but fails integration

---

## Stop Hook - After Response

**When**: After I (Claude) finish responding

**Use cases**:
- Log response length
- Check if I used agents
- Verify I followed instructions
- Remind about next steps

**Example**:
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "command": "python scripts/check_response_quality.py"
          }
        ]
      }
    ]
  }
}
```

**Catches**:
- Responses without agent invocation (when expected)
- Missing `/clear` reminder
- Incomplete implementations

---

## Accountability Checklist

**Process you want to enforce** → **Hook that ensures it**

### ✅ Already Enforced (Your Current Setup)

- [x] **PROJECT.md alignment** → `validate_project_alignment.py`
- [x] **No secrets committed** → `security_scan.py`
- [x] **Tests exist** → `auto_generate_tests.py`
- [x] **Docs updated** → `auto_update_docs.py`
- [x] **Docs consistent** → `validate_docs_consistency.py`
- [x] **Formatting correct** → `auto_fix_docs.py`

### ⚠️ Could Enable (Hooks Exist)

- [ ] **Test coverage ≥ 80%** → `auto_enforce_coverage.py`
- [ ] **TDD followed** → `enforce_tdd.py`
- [ ] **Orchestrator used** → `enforce_orchestrator.py`

### ❌ Could Create (New Hooks)

- [ ] **No TODOs in code** → `check_todos.py` (new)
- [ ] **Commit msg format** → `validate_commit_msg.py` (new)
- [ ] **Code review done** → `require_review.py` (new)
- [ ] **API documentation** → `require_docstrings.py` (new)
- [ ] **Dependencies declared** → `check_dependencies.py` (new)

---

## How to Add More Accountability

### Step 1: Identify What You Skip

**Ask yourself**: "What important step do I often forget?"

Examples:
- Writing tests before code
- Updating documentation
- Running full test suite
- Creating GitHub issues for TODOs
- Following commit message format

### Step 2: Create or Enable Hook

**Option A**: Enable existing hook
```bash
# Edit .claude/settings.local.json
# Add hook to PreCommit list
```

**Option B**: Create new hook
```bash
# Create .claude/hooks/my_check.py
# Add to PreCommit in settings.local.json
```

### Step 3: Test the Hook

```bash
# Try to commit without following the rule
git commit -m "test"

# Hook should block:
# ❌ BLOCKED: [reason]

# Fix the issue, try again:
git commit -m "test"

# Hook should pass:
# ✅ PASS: All checks passed
```

---

## Examples of Accountability in Action

### Example 1: Forgot to Align with PROJECT.md

```bash
# You add a feature outside scope
git add new_feature.py
git commit -m "feat: add GraphQL"

# Hook catches it:
❌ BLOCKED: Feature not aligned with PROJECT.md

PROJECT.md says:
  IN SCOPE: REST API
  OUT OF SCOPE: GraphQL

Your commit adds GraphQL functionality.

Options:
1. Update PROJECT.md to include GraphQL
2. Remove GraphQL code
3. Don't commit

# You're held accountable ✅
```

---

### Example 2: Forgot to Write Tests

```bash
# You write code without tests
git add feature.py
git commit -m "feat: add feature"

# Hook catches it:
⚠️  No tests found for feature.py

Generating tests...
✅ Created tests/test_feature.py with 5 tests

Please review generated tests and re-commit.

# Hook auto-fixes, but makes you review ✅
```

---

### Example 3: Forgot TDD (Tests After Code)

```bash
# You write code first, tests second
git add feature.py
git commit -m "wip: add feature"  # Code first

git add tests/test_feature.py
git commit -m "test: add tests"   # Tests second

# Hook catches it during second commit:
❌ BLOCKED: TDD violation

Tests were added AFTER implementation.
TDD requires tests FIRST (red-green-refactor).

Please:
1. Revert last 2 commits
2. Write tests first
3. Make tests pass

# You're held accountable to process ✅
```

---

### Example 4: Forgot Code Review

```bash
# You implement manually without /implement
vim feature.py
git add feature.py
git commit -m "feat: add feature"

# Hook catches it:
❌ BLOCKED: No code review found

This commit has no review session.

Required: Use /implement to invoke reviewer agent

Or manually:
1. Run: /review feature.py
2. Address feedback
3. Commit again

# Forces you to get review ✅
```

---

## Recommendation: Start Simple, Add More

### Phase 1: What You Have (Keep Using)

```json
{
  "hooks": {
    "PreCommit": [
      "validate_project_alignment",
      "security_scan",
      "auto_generate_tests",
      "auto_update_docs"
    ]
  }
}
```

**This already enforces**:
- Alignment
- Security
- Tests exist
- Docs updated

---

### Phase 2: Add Stricter Enforcement (When Ready)

```json
{
  "hooks": {
    "PreCommit": [
      "validate_project_alignment",
      "security_scan",
      "enforce_tdd",              // ← Add: Force TDD
      "auto_enforce_coverage",    // ← Add: Min 80% coverage
      "enforce_orchestrator",     // ← Add: Must use /implement
      "auto_generate_tests",
      "auto_update_docs"
    ]
  }
}
```

**When to add**: After you're comfortable with Phase 1

---

### Phase 3: Custom Accountability (Future)

```json
{
  "hooks": {
    "PreCommit": [
      "check_todos",              // ← New: No TODOs in code
      "validate_commit_msg",      // ← New: Conventional commits
      "require_docstrings"        // ← New: Document public APIs
    ]
  }
}
```

**When to add**: Based on what you actually skip

---

## Summary

**Your question**: "are there other hooks to hold us to account if we miss the steps we would have liked to have?"

**Answer**: **YES! PreCommit hooks are PERFECT for this.**

**What you already have enforced**:
- ✅ PROJECT.md alignment
- ✅ Security (no secrets)
- ✅ Tests exist
- ✅ Docs updated

**What you could add**:
- ⚠️ Test coverage minimum (80%)
- ⚠️ TDD enforcement (tests first)
- ⚠️ Orchestrator usage (no manual coding)
- ⚠️ Code review required
- ⚠️ No TODOs in commits
- ⚠️ Commit message format

**The approach**:
1. **Commands**: Do the work (`/implement`)
2. **PreCommit Hooks**: Hold you accountable (block bad commits)
3. **Result**: Can't skip important steps even if you try

---

**This is exactly what hooks are FOR - enforcement and accountability!**

Want to enable stricter hooks? I can help you configure them.
