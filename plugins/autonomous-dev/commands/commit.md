---
description: Progressive commit validation - quick/check/push/release with integrity gateway
---

# Progressive Commit Command

**Four levels of validation from quick commit → full integrity → push → release**

---

## Usage

### Level 1: Quick Commit (< 5s)
```bash
/commit
/commit --quick
```
**Runs**: Format + unit tests + security → Commit locally (no push)
**Use for**: Rapid iteration during development

---

### Level 2: Standard Commit (< 60s)
```bash
/commit --check
/commit --standard
```
**Runs**: All tests + coverage + doc sync check → Commit locally (no push)
**Use for**: Feature completion, before review

---

### Level 3: Push Commit (2-5min) ⭐
```bash
/commit --push
/commit --integrity
```
**Runs**: Full integrity + README rebuild + doc sync + CHANGELOG update + PROJECT.md validation → Commit + Push to GitHub
**Use for**: Before merge, sharing with team

---

### Level 4: Release (5-10min) 🚀
```bash
/commit --release
/commit --release --version=1.2.0
```
**Runs**: Complete validation + version bump + GitHub Release
**Use for**: Production releases

---

## Implementation

Parse the user's command to determine validation level:

```python
# Parse arguments
args = parse_commit_args()  # Returns: level, version, message

if args.level == "quick":
    run_level_1_quick_commit()
elif args.level == "check" or args.level == "standard":
    run_level_2_standard_commit()
elif args.level == "push" or args.level == "integrity":
    run_level_3_push_commit()
elif args.level == "release":
    run_level_4_release_commit(version=args.version)
else:
    # Default to quick commit
    run_level_1_quick_commit()
```

---

## Level 1: Quick Commit

**What it does**:
1. Run `/format` (black, isort, prettier)
2. Run unit tests only (fast subset)
3. Run `/security-scan` (secrets detection)
4. Analyze `git diff --cached` and `git diff`
5. Generate conventional commit message
6. **Commit locally** (don't push)

**Expected output**:
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

Commit locally (no push)? [Y/n]:
```

**Commands to run**:
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
echo "💡 Run '/commit --push' when ready to push to GitHub"
```

---

## Level 2: Standard Commit

**What it does**:
1. All from Level 1
2. Run ALL tests (unit + integration + UAT)
3. Check test coverage (80%+ required)
4. Check documentation sync status
5. **Commit locally** (don't push)

**Expected output**:
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
Run '/commit --push' to auto-sync documentation

Commit locally? [Y/n]:
```

**Additional commands**:
```bash
# Run all tests
/test

# Check coverage
pytest --cov=src --cov-report=term-missing

# Check doc sync (simplified check)
# - Compare PROJECT.md modification time vs README.md
# - Warn if README older than PROJECT.md
stat -f %m .claude/PROJECT.md
stat -f %m README.md
```

---

## Level 3: Push Commit (Full Integrity)

**What it does**:
1. All from Level 2
2. Check for dependency updates
3. **Rebuild README.md** from PROJECT.md + docs
4. **Sync documentation** cross-references
5. **Update CHANGELOG.md** from commits
6. **Validate PROJECT.md alignment** (GenAI validation)
7. **Create GitHub Issues** for findings
8. **Commit + Push to GitHub**

**Expected output**:
```
Running Level 3: Push Commit (Full Integrity)...

┌─ Full Integrity Workflow ───────────────────────────────────┐
│                                                              │
│ Phase 1: Code Quality ✅                                     │
│  ✅ Format: PASSED                                           │
│  ✅ All Tests: PASSED (65/65, 20.3s)                         │
│  ✅ Coverage: 92%                                            │
│  ✅ Security: PASSED                                         │
│                                                              │
│ Phase 2: Documentation Sync 🔄                               │
│  🔄 Checking dependencies...                                 │
│     ✅ All dependencies up to date                           │
│  🔄 Rebuilding README.md from PROJECT.md...                  │
│     ✅ README.md updated (sections: 3, features: 12)         │
│  🔄 Syncing documentation cross-references...                │
│     ✅ All cross-references valid (48 links checked)         │
│  🔄 Updating CHANGELOG.md...                                 │
│     ✅ Added entry: v1.1.1 - 2025-10-20                      │
│                                                              │
│ Phase 3: Architectural Validation (GenAI) 🤖                 │
│  🔄 Validating PROJECT.md alignment...                       │
│     ✅ All goals aligned                                     │
│     ✅ Within scope                                          │
│     ✅ Constraints respected                                 │
│  🔄 Validating architecture...                               │
│     ✅ 100% aligned with documented intent                   │
│     ⚠️  1 optimization opportunity found                     │
│                                                              │
│ Phase 4: Issue Tracking 📋                                   │
│  ✅ Created issue #42: "Use Haiku for simple tasks"          │
│                                                              │
│ Total time: 3m 42s                                           │
│ Status: PASSED ✅ (1 optimization tracked)                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Files modified during integrity checks:
  M README.md (auto-generated from PROJECT.md)
  M CHANGELOG.md (added v1.1.1 entry)

Staging updated files...

Pushing to GitHub...
✅ Pushed to GitHub
```

**Implementation approach**:

Since this is a complex multi-phase workflow, **use the Task tool with orchestrator agent**:

```markdown
I need to run a Level 3 Push Commit with full integrity validation.

Please orchestrator agent:

1. **Phase 1: Code Quality**
   - Run /format
   - Run /test (all tests)
   - Check coverage (80%+ required)
   - Run /security-scan

2. **Phase 2: Documentation Sync**
   - Check dependencies: pip list --outdated (Python) or npm outdated (JS)
   - Rebuild README.md from PROJECT.md (extract sections, features, commands)
   - Check documentation cross-references (grep for broken links)
   - Update CHANGELOG.md from git log since last release

3. **Phase 3: Architectural Validation**
   - Validate PROJECT.md alignment (read PROJECT.md, compare with changes)
   - Check that changes align with GOALS, are IN SCOPE, respect CONSTRAINTS
   - Identify any architectural drift or optimization opportunities

4. **Phase 4: Issue Tracking**
   - Create GitHub issues for any findings (if gh CLI available)
   - Tag with "automated" label

5. **Commit and Push**
   - Stage all files (including auto-generated README, CHANGELOG)
   - Create commit with validation summary
   - Push to GitHub

Please return a detailed summary of:
- All checks performed
- Files modified
- Issues created
- Commit hash
- Push status
```

---

## Level 4: Release

**What it does**:
1. All from Level 3
2. **Full system integrity check**
3. **Version bump** (semantic versioning)
4. **Generate release notes** from CHANGELOG
5. **Create git tag**
6. **Create GitHub Release**

**Expected output**:
```
Running Level 4: Release Workflow...

┌─ Complete Release Validation ───────────────────────────────┐
│                                                              │
│ Phase 1: Pre-Release Integrity ✅                            │
│  ✅ All tests: PASSED (65/65)                                │
│  ✅ Coverage: 92%                                            │
│  ✅ Security: PASSED (no vulnerabilities)                    │
│  ✅ Dependencies: All up to date                             │
│                                                              │
│ Phase 2: System Synchronization 🔄                           │
│  ✅ README.md rebuilt                                        │
│  ✅ All documentation synchronized                           │
│  ✅ CHANGELOG.md complete                                    │
│  ✅ Version numbers updated (1.2.0)                          │
│                                                              │
│ Phase 3: Architectural Validation 🤖                         │
│  ✅ PROJECT.md alignment: 100%                               │
│  ✅ Architecture: No drift detected                          │
│                                                              │
│ Phase 4: Release Preparation 📦                              │
│  ✅ Git tag created: v1.2.0                                  │
│  ✅ Release notes generated                                  │
│                                                              │
│ Total time: 7m 23s                                           │
│ Status: READY FOR RELEASE ✅                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Proceed with release? [Y/n]:
```

**Implementation**: Use orchestrator agent with extended workflow including:
- Version bump in `package.json`, `setup.py`, `__version__`
- Release notes generation from CHANGELOG.md
- Git tag creation: `git tag -a v{version} -m "Release {version}"`
- GitHub Release: `gh release create v{version} --notes "{notes}"`

---

## Configuration (.env)

**Optional settings**:
```bash
# Commit defaults
COMMIT_DEFAULT_LEVEL=quick  # quick, check, push, release
COMMIT_AUTO_PUSH=false      # Auto-push after commit
COMMIT_AUTO_ISSUE=true      # Auto-create GitHub issues

# Validation
COMMIT_COVERAGE_MIN=80      # Minimum coverage %
COMMIT_SECURITY_SCAN=true   # Run security scan
COMMIT_README_REBUILD=true  # Auto-rebuild README on push

# GitHub integration
GITHUB_AUTO_ISSUE=true      # Create issues for findings
GITHUB_ISSUE_LABEL=automated
```

---

## Commit Message Generation

**Conventional Commits format**:
```
<type>(<scope>): <description>

<body>

<footer>
```

**Type detection logic**:
1. Check git diff for patterns:
   - New files/functions → `feat`
   - Bug-related keywords → `fix`
   - Only docs changed → `docs`
   - Only tests changed → `test`
   - Refactoring keywords → `refactor`
   - Config/build changes → `chore`

2. Scope detection:
   - Extract from file paths (e.g., `src/auth/` → `auth`)
   - Use directory name or module name

3. Description generation:
   - Summarize changes in imperative mood
   - List key changes in body
   - Reference issues if mentioned in code

---

## Error Handling

**If checks fail**:
```
❌ Level 1 Quick Commit FAILED

Issues found:
1. ❌ Format check failed (3 files need formatting)
   Fix: Run /format and retry

2. ❌ Unit tests failed (2/45 failed)
   Fix: Review test failures and fix code

3. ❌ Security scan found issues (1 secret detected)
   Fix: Remove secrets and retry

Cannot proceed with commit. Please fix issues above.
```

**Progressive fallback**:
- If Level 3 fails → Offer to commit at Level 2
- If Level 2 fails → Offer to commit at Level 1
- If Level 1 fails → Block commit until fixed

---

## Quick Reference

| Command | Level | Time | Validates | Pushes |
|---------|-------|------|-----------|--------|
| `/commit` | 1 | 5s | Format, unit tests, security | No |
| `/commit --check` | 2 | 60s | All tests, coverage | No |
| `/commit --push` | 3 | 3min | Full integrity, docs, alignment | Yes |
| `/commit --release` | 4 | 7min | Complete validation, version bump | Yes + Tag |

---

## Related Commands

- `/format` - Format code only
- `/test` - Run tests only
- `/security-scan` - Security check only
- `/full-check` - Run all checks without commit
- `/auto-implement` - Complete autonomous workflow

---

**Use this for progressive validation from quick commit → production release with integrity gateway at each level.**
