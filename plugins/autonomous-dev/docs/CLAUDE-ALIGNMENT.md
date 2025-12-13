# CLAUDE.md Alignment System

**Purpose**: Prevent documentation drift and keep CLAUDE.md synchronized with actual implementation

**Status**: NEW in v3.0.2 (Alignment with Best Practices)

**Problem Solved**: CLAUDE.md defines development standards, but it can drift from reality (outdated versions, wrong counts, archived commands documented as active). When this happens, new developers follow incorrect practices.

---

## What Gets Validated

### 1. Version Consistency

**What**: CLAUDE.md `Last Updated` date should match or be newer than PROJECT.md

**Why**: PROJECT.md changes more frequently (goals/scope updates). CLAUDE.md documents implementation details that should stay current.

**Example Drift**:
```markdown
# CLAUDE.md
**Last Updated**: 2025-10-19

# PROJECT.md
**Last Updated**: 2025-10-27  ← Newer!

Issue: CLAUDE.md is 8 days out of date
Fix: Update CLAUDE.md date to 2025-10-27
```

### 2. Agent Counts

**What**: CLAUDE.md documents agent count; validator checks against actual agents

**Why**: When agents are added/removed, CLAUDE.md must stay accurate

**Current Reality**:
- 10 core workflow agents (orchestrator, researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, advisor, quality-validator)
- 6 utility agents (alignment-validator, commit-message-generator, pr-description-generator, project-progress-tracker, alignment-analyzer, project-bootstrapper)
- **Total: 16 agents**

**Example Drift**:
```markdown
# CLAUDE.md (Wrong)
### Agents (7 specialists)

# Reality
16 agents in plugins/autonomous-dev/agents/

Issue: CLAUDE.md says 7, but 16 exist
Fix: Update heading to "### Agents (16 specialists)"
```

### 3. Command Availability

**What**: All commands mentioned in CLAUDE.md must have corresponding `.md` files

**Why**: If you tell someone "use /auto-implement", that command must exist

**Current Reality** (10 commands, per Issue #121):
- `/auto-implement` - Full feature development pipeline
- `/batch-implement` - Process multiple features with state management
- `/create-issue` - Create GitHub issues with research
- `/align` - Unified alignment (--project, --claude, --retrofit)
- `/setup` - Interactive setup wizard
- `/sync` - Smart sync (dev env, marketplace, or plugin-dev)
- `/status` - View project status
- `/health-check` - Diagnostic health check
- `/pipeline-status` - Track /auto-implement workflow
- `/test` - Run test suite

**Example Drift**:
```markdown
# CLAUDE.md
"Use /format for code formatting"

# Reality
/format doesn't exist (archived in v3.1.0)

Issue: Documenting archived command as active
Fix: Update CLAUDE.md to remove /format, add /auto-implement
```

### 4. Skills Status

**What**: CLAUDE.md should say "Skills (0 - Removed)" per v2.5+ guidance

**Why**: Anthropic's anti-pattern guidance recommends removing skills. Guidance should live in agent prompts and global CLAUDE.md instead.

**Current Status**: Skills removed, guidance consolidated into agent prompts

**Example Drift**:
```markdown
# CLAUDE.md (Wrong)
### Skills (6 core competencies)
Located: `plugins/autonomous-dev/skills/`
- python-standards
- testing-guide
- ...

# Correct
### Skills (0 - Removed)
Per Anthropic anti-pattern guidance (v2.5+), skills were removed.
Guidance now lives directly in agent prompts.
```

### 5. Hook Documentation

**What**: CLAUDE.md lists hooks; validator checks count is reasonable

**Why**: Hook documentation should match implementations

**Current**: 15+ hooks (7 core + 8+ optional)

---

## How the System Works

### 1. Automatic Validation (Pre-Commit Hook)

Every commit triggers the validation hook:

```bash
git add CLAUDE.md  # Make change to CLAUDE.md
git commit -m "docs: update something"

# ↓ Pre-commit hook runs automatically
# ↓ Checks CLAUDE.md alignment
# ↓ Reports any drift

⚠️  CLAUDE.md Alignment: Agent count mismatch...
    (Commit still proceeds, but you see warning)
```

**Hook location**: `plugins/autonomous-dev/hooks/validate_claude_alignment.py`

### 2. Manual Validation

Run the validation script directly:

```bash
python .claude/hooks/validate_claude_alignment.py
```

**Output Examples**:

```
✅ CLAUDE.md Alignment: No issues found
```

Or:

```
======================================================================
CLAUDE.md Alignment Report
======================================================================

❌ ERRORS (1):
  Missing documented commands: auto-implement.
  CLAUDE.md references commands that don't exist.
    Location: plugins/autonomous-dev/commands/

⚠️  WARNINGS (2):
  Agent count drift: CLAUDE.md says 7, but 16 exist.
  ...

======================================================================
Fix:
  1. Update CLAUDE.md with actual values
  2. Commit: git add CLAUDE.md && git commit -m 'docs: ...'
======================================================================
```

### 3. The Command (Interactive)

New `/align-claude` command provides interactive guidance:

```bash
/align-claude
# Shows alignment report
# Suggests specific fixes
# Can auto-fix simple issues (counts, dates)
```

---

## Common Drift Scenarios and Fixes

### Scenario 1: Outdated Version Date

**Problem**: CLAUDE.md has old `Last Updated` date

**Detection**:
```
⚠️  Project CLAUDE.md is outdated (older than PROJECT.md).
```

**Fix**:
```bash
# CLAUDE.md line 3:
- **Last Updated**: 2025-10-19
+ **Last Updated**: 2025-10-27
```

### Scenario 2: Agent Count Changed

**Problem**: New agents added, CLAUDE.md not updated

**Detection**:
```
⚠️  Agent count drift: CLAUDE.md says 7, but 16 exist.
```

**Fix**:
```bash
# CLAUDE.md section:
- ### Agents (7 specialists)
+ ### Agents (16 specialists)

# Then update the description to list all 16:
**Core Workflow Agents (10)**:
- orchestrator: ...
- researcher: ...
...
```

### Scenario 3: Documented Command Doesn't Exist

**Problem**: Documenting archived command as if it still works

**Detection**:
```
❌ ERRORS (1):
  Missing documented commands: format.
  CLAUDE.md references commands that don't exist.
```

**Fix**:
```bash
# CLAUDE.md:
- Remove references to /format
- Add references to current commands like /auto-implement
- Check .md file exists: ls plugins/autonomous-dev/commands/
```

### Scenario 4: Skills Documented as Active

**Problem**: CLAUDE.md still describes skills as available

**Detection**:
```
⚠️  CLAUDE.md still documents skills (should say '0 - Removed' per v2.5+ guidance)
```

**Fix**:
```bash
# CLAUDE.md:
- ### Skills (6 core competencies)
+ ### Skills (0 - Removed)
- Located: `plugins/autonomous-dev/skills/`
- - python-standards: ...
+ Per Anthropic anti-pattern guidance (v2.5+), skills were removed.
+ Guidance now lives directly in agent prompts.
```

---

## Testing the Alignment System

### Run Tests

```bash
pytest plugins/autonomous-dev/tests/test_claude_alignment.py -v
```

**Test Coverage**:
- ✅ Date extraction from markdown
- ✅ Count parsing (agents, commands, hooks)
- ✅ Missing command detection
- ✅ Skills deprecation checking
- ✅ Session-based warning deduplication
- ✅ Real-world scenario validation

### Manual Testing

```bash
# Test 1: Check current alignment
python .claude/hooks/validate_claude_alignment.py

# Test 2: Simulate drift
# Edit CLAUDE.md, change agent count to 7
vim CLAUDE.md
python .claude/hooks/validate_claude_alignment.py
# Should show warning about mismatch

# Test 3: Hook validation
# Make a commit with mismatched CLAUDE.md
git add CLAUDE.md
git commit -m "test: simulate drift"
# Hook should show warning (but commit proceeds)
```

---

## Architecture

### Files

**Validation script**:
```
.claude/hooks/validate_claude_alignment.py
```
- Main validation logic
- Detects all drift types
- Generates detailed reports
- Exit codes: 0 (aligned), 1 (warnings), 2 (critical)

**Pre-commit hook**:
```
plugins/autonomous-dev/hooks/validate_claude_alignment.py
```
- Runs automatically on every commit
- Lightweight version (checks key things only)
- Session-based warning deduplication (no spam)
- Calls validation script under the hood

**Command**:
```
plugins/autonomous-dev/commands/align-claude.md
```
- Interactive interface for users
- Calls validation script
- Suggests fixes
- Can auto-fix simple issues

**Tests**:
```
plugins/autonomous-dev/tests/test_claude_alignment.py
```
- Unit tests for extraction functions
- Integration tests for validator
- Real-world scenario testing

### Data Flow

```
Developer makes changes
    ↓
Developer runs: git commit
    ↓
Pre-commit hook: validate_claude_alignment.py
    ├─ Read CLAUDE.md, PROJECT.md, agents/, commands/, hooks/
    ├─ Extract versions, counts, commands
    ├─ Compare documented vs actual
    ├─ Collect issues
    └─ Check if already shown this session (dedup)
    ↓
If drift detected:
    ├─ Print warning to stderr
    ├─ Show specific issues
    ├─ Suggest fixes
    └─ Exit code 0 or 1 (commit proceeds)
    ↓
Commit succeeds (hook doesn't block)
    ↓
Developer sees warning:
    ⚠️  CLAUDE.md Alignment: Agent count mismatch...
    ↓
Developer can:
    A) Ignore (not recommended)
    B) Fix CLAUDE.md in next commit
    C) Fix immediately: vim CLAUDE.md && git add CLAUDE.md && git commit
```

---

## Best Practices

### For Contributors

1. **After adding agents**: Update CLAUDE.md agent count
2. **After adding commands**: Update CLAUDE.md command list
3. **After major changes**: Run validation before committing

```bash
# Validate before major commits
python .claude/hooks/validate_claude_alignment.py

# If issues found, fix them
vim CLAUDE.md
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md alignment"
```

4. **Keep dates current**: Update `Last Updated` when making significant changes to CLAUDE.md

### For Maintainers

1. **Review alignment on PR**: Check validation passes
2. **Monthly maintenance**: Run validation to catch drift
3. **Update during releases**: Ensure all docs match release changes

### For Users

1. **Trust CLAUDE.md**: It's automatically validated
2. **Report drift**: If you see outdated info, it's a bug
3. **Use `/align-claude`**: Check alignment anytime

```bash
/align-claude  # See current status
```

---

## Troubleshooting

### Issue: Validation script not found

```bash
# Check path:
ls .claude/hooks/validate_claude_alignment.py

# Run directly:
python .claude/hooks/validate_claude_alignment.py

# Or via command:
/align-claude
```

### Issue: False positive - I know this is correct

The validator errs on the side of caution. If you believe an issue is incorrect:

1. Check the actual state:
```bash
# Count agents
ls plugins/autonomous-dev/agents/ | wc -l

# Count commands
ls plugins/autonomous-dev/commands/ | wc -l
```

2. Update CLAUDE.md to match reality
3. Run validator again to confirm

### Issue: Hook runs every commit

**That's intentional!** It ensures CLAUDE.md stays in sync.

To temporarily skip (NOT recommended):
```bash
git commit --no-verify
# But then manually run validation:
python .claude/hooks/validate_claude_alignment.py
```

### Issue: Too many warnings

Warnings are deduplicated per session. Different warnings will show once each.

Clear warnings:
```bash
rm ~/.claude/_validation_state_*.json
```

---

## Integration with Other Systems

### With Pre-Commit Framework

If you use [pre-commit](https://pre-commit.com/), add:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: validate-claude
      name: Validate CLAUDE.md alignment
      entry: python plugins/autonomous-dev/hooks/validate_claude_alignment.py
      language: python
      stages: [commit]
```

### With CI/CD

Add to your CI pipeline:

```bash
# In GitHub Actions, etc.
python .claude/hooks/validate_claude_alignment.py || exit 2
```

This fails the CI build if critical drift is detected.

### With /align-project

The `/align-project` command (PROJECT.md alignment) is separate but complementary:
- **PROJECT.md alignment**: Goals, scope, constraints are accurate
- **CLAUDE.md alignment**: Development practices are documented accurately

Both systems work together for complete documentation accuracy.

---

## FAQ

**Q: Why is CLAUDE.md important?**
A: It documents development practices. If outdated, new developers follow incorrect standards.

**Q: What if I disagree with the documentation?**
A: Update CLAUDE.md and PROJECT.md to match your actual practice. Both are living documents.

**Q: Does this slow down development?**
A: No. Validation is fast (<100ms) and only runs on commit. No manual overhead for developers.

**Q: Can I disable it?**
A: Yes, but not recommended. To skip:
```bash
git commit --no-verify
```

**Q: What if validation detects real issues in the code?**
A: Then fix them! The validator is a quality gate. If it found the issue, it's worth fixing.

**Q: How often should I check alignment?**
A: Automatically on every commit (hook), plus manually after big changes or monthly.

---

## See Also

- **CLAUDE.md**: The standards file being validated
- **PROJECT.md**: Strategic goals (separate alignment system)
- **/align-claude**: Interactive command for checking alignment
- **test_claude_alignment.py**: Test suite
- **Anthropic Design Principles**: https://github.com/anthropics/claude-code

---

**Last Updated**: 2025-10-27
**Version**: v3.0.2
**Status**: Production (Alignment with Best Practices)
