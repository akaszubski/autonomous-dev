# Testing User Experience

**Purpose**: Ensure the plugin installation works for real users, not just developers

**Last Updated**: 2025-11-03

---

## Why This Matters

You're developing the plugin (dogfooding), but **users have a different experience**:

- **You**: Edit `plugins/autonomous-dev/` → resync → test locally
- **Users**: `/plugin install` → run bootstrap → use commands

**You need to test BOTH flows** to ensure users don't hit issues you never see.

---

## Quick Test: Does It Work For Users?

```bash
# Run automated test
./scripts/test-user-install.sh

# What this does:
# 1. Creates test project (test-user-project/)
# 2. Runs bootstrap script (as user would)
# 3. Verifies all files copied
# 4. Tests hooks work
# 5. Reports PASS/FAIL
```

**Expected output**:
```
✅ ALL TESTS PASSED
The user installation flow works correctly!
```

**If errors**:
- Fix issues in install.sh or plugin structure
- Run test again
- Don't push to GitHub until test passes

---

## Manual Test: Simulate Real User

**When to do this**: Before releasing a new version

### Step 1: Create Test Project

```bash
# Outside your repo
cd ~/Desktop
mkdir test-autonomous-dev
cd test-autonomous-dev
git init
echo "# Test" > README.md
git add . && git commit -m "init"
```

### Step 2: Install Plugin (As User)

```bash
# In Claude Code
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit Claude Code (Cmd+Q)
```

### Step 3: Run Bootstrap

```bash
# Restart Claude Code
# In test project:
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**What to check**:
- ✅ Script runs without errors
- ✅ `.claude/` directory created
- ✅ Commands copied to `.claude/commands/`
- ✅ Hooks copied to `.claude/hooks/`
- ✅ Templates copied to `.claude/templates/`

### Step 4: Verify Commands Work

```bash
# Restart Claude Code
# Try commands:
/auto-implement "add hello function"
/status
/health-check
/setup
```

**What to check**:
- ✅ Commands are recognized (not "unknown command")
- ✅ Commands run without errors
- ✅ Help text is clear

### Step 5: Test Auto-Orchestration

```bash
# In Claude Code, type:
"implement a simple greeting function"
```

**What to check**:
- ✅ Detection message appears: "🎯 Feature Request Detected"
- ✅ orchestrator is invoked automatically
- ✅ PROJECT.md alignment check runs
- ✅ Other agents invoked if aligned

### Step 6: Test Hooks

```bash
# Make a change
echo "test" > test.py
git add test.py

# Try to commit (hooks should run)
git commit -m "test"
```

**What to check**:
- ✅ PreCommit hooks run (see output)
- ✅ Validation passes or gives clear errors
- ✅ Commit succeeds if validations pass

### Step 7: Cleanup

```bash
# Delete test project
cd ~/Desktop
rm -rf test-autonomous-dev
```

---

## What To Test Before Each Release

**Before pushing to GitHub**, verify:

### 1. Plugin Structure

```bash
# In your repo
ls -la plugins/autonomous-dev/agents/*.md | wc -l    # Should be 19
ls -la plugins/autonomous-dev/commands/*.md | wc -l  # Should be 7-8
find plugins/autonomous-dev/hooks -name "*.py" | wc -l  # Should be 28+
```

### 2. Bootstrap Script

```bash
# Test bootstrap works
./scripts/test-user-install.sh
# Should show: ✅ ALL TESTS PASSED
```

### 3. Documentation

```bash
# Check README is up to date
cat plugins/autonomous-dev/README.md | grep "Version:"
# Should match current version

# Check install instructions are clear
cat README.md | grep -A 10 "Installation"
```

### 4. Critical Commands

```bash
# Test each command has valid frontmatter
for cmd in plugins/autonomous-dev/commands/*.md; do
    echo "Checking: $(basename $cmd)"
    head -20 "$cmd" | grep -q "^name:" || echo "  ❌ Missing name"
    head -20 "$cmd" | grep -q "^description:" || echo "  ❌ Missing description"
done
```

### 5. Critical Hooks

```bash
# Test hooks run without Python errors
for hook in plugins/autonomous-dev/hooks/*.py; do
    echo "Testing: $(basename $hook)"
    python "$hook" --help 2>&1 | grep -q "Traceback" && echo "  ❌ Python error"
done
```

---

## Common User Issues to Test For

### Issue: Commands Not Found

**Symptom**: User runs `/auto-implement`, Claude says "unknown command"

**Test**:
```bash
# After bootstrap, check:
ls .claude/commands/auto-implement.md
# Should exist

# Check frontmatter:
head -5 .claude/commands/auto-implement.md
# Should have: name: auto-implement
```

**Fix**: Ensure install.sh copies commands correctly

---

### Issue: Hooks Don't Run

**Symptom**: User types feature request, nothing happens

**Test**:
```bash
# Check settings
cat .claude/settings.local.json
# Should have UserPromptSubmit hook

# Test hook directly
echo "implement auth" | python .claude/hooks/detect_feature_request.py
echo $?  # Should be 0
```

**Fix**:
- Ensure install.sh copies hooks
- Update README to mention settings configuration
- Or auto-create settings.local.json in bootstrap

---

### Issue: Agents Not Available

**Symptom**: `/auto-implement` runs but no agents invoked

**Test**:
```bash
# Check agents installed
ls ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/*.md | wc -l
# Should be 19

# Check agent frontmatter
head -10 ~/.claude/plugins/.../agents/orchestrator.md
# Should have valid YAML
```

**Fix**: Ensure agents have correct frontmatter in plugin

---

### Issue: Bootstrap Fails

**Symptom**: `install.sh` exits with error

**Test**:
```bash
# Run bootstrap with debug
bash -x install.sh
# Shows each command executing
```

**Fix**: Check error message, fix install.sh logic

---

## Testing Checklist

**Before releasing v.X.Y.Z:**

- [ ] Run `./scripts/test-user-install.sh` - passes
- [ ] Plugin structure validated (agents/commands/hooks counts correct)
- [ ] Manual test in fresh project - works
- [ ] All 7-8 commands recognized and run
- [ ] Auto-orchestration triggers on feature requests
- [ ] PreCommit hooks run on git commit
- [ ] README installation instructions clear
- [ ] CHANGELOG updated with changes
- [ ] Version bumped in plugin.json
- [ ] Pushed to GitHub
- [ ] GitHub release created (if major version)

---

## Automated Testing (Future)

**Goal**: Run full integration tests in CI

**Planned**:
```bash
# GitHub Actions workflow
.github/workflows/test-user-install.yml

# Runs on every PR:
# 1. Install plugin in clean environment
# 2. Bootstrap test project
# 3. Run test-user-install.sh
# 4. Fail PR if tests fail
```

**For now**: Run `./scripts/test-user-install.sh` manually before each release

---

## Troubleshooting Test Failures

### Test fails: "Plugin not installed"

**Cause**: Need to install plugin first

**Fix**:
```bash
# In Claude Code:
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code
# Run test again
```

---

### Test fails: "Commands incomplete"

**Cause**: install.sh not copying commands correctly

**Fix**:
```bash
# Check plugin has commands
ls ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/commands/

# Check install.sh logic
cat install.sh | grep -A 10 "Copying commands"

# Fix install.sh if broken
vim install.sh
```

---

### Test fails: "Hooks incomplete"

**Cause**: install.sh not copying hooks correctly

**Fix**:
```bash
# Check plugin has hooks
ls ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/

# Check install.sh uses -r flag for recursive copy
cat install.sh | grep "cp.*hooks"

# Fix: Should be: cp -r "$PLUGIN_DIR"/hooks/* "$CLAUDE_DIR/hooks/"
```

---

### Test fails: "Feature detection: FAIL"

**Cause**: Hook has Python errors

**Fix**:
```bash
# Run hook manually to see error
python .claude/hooks/detect_feature_request.py
# Fix Python errors

# Or check Python version
python --version  # Should be 3.11+
```

---

## Summary

**Two testing flows**:

1. **Dogfooding** (what you do daily):
   - Edit `plugins/autonomous-dev/`
   - Run `./scripts/resync-dogfood.sh`
   - Test immediately

2. **User experience** (test before release):
   - Run `./scripts/test-user-install.sh`
   - Or manual test in fresh project
   - Ensure users won't hit issues

**Best practice**:
- Test dogfooding flow constantly (every change)
- Test user flow before every GitHub push
- Automate user flow testing (future goal)

---

**Next**: See `docs/DEVELOPMENT.md` for daily workflow and `docs/RELEASE-PROCESS.md` (TBD) for release checklist
