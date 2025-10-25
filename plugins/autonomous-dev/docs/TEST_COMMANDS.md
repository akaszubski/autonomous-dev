# Testing Slash Commands

**After syncing and restarting Claude Code**, follow these steps to test:

---

## Test 1: Verify Fixed Commands Work

### Test `/format` (was broken, now fixed)

```bash
# This should actually RUN formatters, not just show docs
/format
```

**Expected**: You'll see Claude execute:
```bash
black . && isort . && ruff check --fix .
```

**If broken**: You'd just see the command documentation with no execution.

### Test `/test` (was broken, now fixed)

```bash
/test
```

**Expected**: You'll see Claude execute:
```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

### Test `/health-check` (was already working)

```bash
/health-check
```

**Expected**: Executes `health_check.py` script and shows validation report.

---

## Test 2: Verify Validation Script Works

### Check all commands are valid

```bash
python plugins/autonomous-dev/scripts/validate_commands.py
```

**Expected Output**:
```
✅ align-project.md
✅ auto-implement.md
... (22 total)
✅ ALL COMMANDS HAVE PROPER IMPLEMENTATIONS!
```

---

## Test 3: Create A New Command

### Use the generator

```bash
python plugins/autonomous-dev/scripts/new_command.py demo-test
```

**Follow prompts**:
```
One-line description: Demo test command for validation
Command title: Demo Test
Brief overview: This demonstrates the command creation workflow
Closing remark: Use this to test command generation
Implementation type: 1 (bash)
```

**Expected**: Creates `.claude/commands/demo-test.md` with proper structure.

### Verify it validates

```bash
python plugins/autonomous-dev/scripts/validate_commands.py | grep demo-test
```

**Expected**: `✅ demo-test.md`

### Check the generated file

```bash
cat .claude/commands/demo-test.md
```

**Expected**: Should have `## Implementation` section with bash block.

---

## Test 4: Verify Pre-commit Hook Catches Broken Commands

### Create a broken command manually

```bash
cat > .claude/commands/broken-test.md << 'EOF'
---
description: Intentionally broken command for testing
---

# Broken Test

This command has no implementation section.

## Usage
/broken-test

## What This Does
Nothing, because no implementation!
EOF
```

### Try to commit it

```bash
git add .claude/commands/broken-test.md
git commit -m "test: broken command"
```

**Expected**: Commit BLOCKED with error:
```
🔍 Validating slash command implementations...
❌ broken-test.md: No implementation found
RESULTS: 22 valid, 1 invalid
```

### Clean up

```bash
git reset HEAD .claude/commands/broken-test.md
rm .claude/commands/broken-test.md
```

---

## Test 5: Create A Real Command (Full Workflow)

Let's create a real command as an example:

```bash
# 1. Generate
python plugins/autonomous-dev/scripts/new_command.py status
```

**Prompts** (example):
```
One-line description: Show project status and health
Command title: Project Status
Brief overview: Displays current project state, recent commits, and system health
Closing remark: Use this for quick project overview
Implementation type: 1 (bash)
```

**Result**: Creates `.claude/commands/status.md`

```bash
# 2. Edit to customize (replace TODO with real commands)
vim .claude/commands/status.md
```

**Change this**:
```bash
## Implementation

Run the command:

```bash
# TODO: Add your bash commands here
your-command-here
```
\```
```

**To this**:
```bash
## Implementation

Run status commands:

```bash
echo "=== Project Status ==="
git log --oneline -5
echo ""
echo "=== Current Branch ==="
git branch --show-current
echo ""
echo "=== Modified Files ==="
git status --short
```
\```
```

```bash
# 3. Validate
python plugins/autonomous-dev/scripts/validate_commands.py | grep status
```

**Expected**: `✅ status.md`

```bash
# 4. Sync to runtime
python plugins/autonomous-dev/scripts/sync_to_installed.py

# 5. Restart Claude Code (required!)
# Cmd+Q or Ctrl+Q, then restart

# 6. Test the command
/status
```

**Expected**: Claude executes the bash commands and shows git status.

```bash
# 7. Commit
git add .claude/commands/status.md
git commit -m "feat: add /status command for project overview"
```

**Expected**: Pre-commit hook validates, commit succeeds.

---

## Quick Test Checklist

After syncing and restarting:

- [ ] `/format` actually runs formatters (not just docs)
- [ ] `/test` actually runs pytest (not just docs)
- [ ] `/health-check` runs and shows report
- [ ] `validate_commands.py` shows 22 valid
- [ ] Generator creates commands with Implementation section
- [ ] Pre-commit hook blocks broken commands
- [ ] Can create, edit, validate, and commit new command

---

## Troubleshooting

### "Command still just shows docs"

1. Did you sync? `python plugins/autonomous-dev/scripts/sync_to_installed.py`
2. Did you restart Claude Code? (Required after sync!)
3. Check command has Implementation section: `tail -20 .claude/commands/format.md`

### "Generator not found"

```bash
# Check it exists
ls -la plugins/autonomous-dev/scripts/new_command.py

# Make sure it's executable
chmod +x plugins/autonomous-dev/scripts/new_command.py
```

### "Validator fails"

```bash
# See which commands are broken
python plugins/autonomous-dev/scripts/validate_commands.py

# Should show specific errors for broken commands
```

### "Pre-commit hook not running"

```bash
# Check hook exists
ls -la .git/hooks/pre-commit

# Check it's executable
chmod +x .git/hooks/pre-commit

# Test manually
.git/hooks/pre-commit
```

---

## Next: Add Your Own Command

Once testing is complete, create a command you actually need:

```bash
# Example: Add a quick commit command
python plugins/autonomous-dev/scripts/new_command.py quick-commit

# Or: Add a deployment command
python plugins/autonomous-dev/scripts/new_command.py deploy

# Or: Add a cleanup command
python plugins/autonomous-dev/scripts/new_command.py cleanup
```

Follow the workflow in Test 5 above.
