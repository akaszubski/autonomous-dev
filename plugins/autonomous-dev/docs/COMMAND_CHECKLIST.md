# Slash Command Creation Checklist

**Last Updated**: 2025-10-25

This checklist prevents the "command does nothing" bug where commands are just documentation without actual implementation.

---

## ✅ Command Creation Checklist

When creating a new slash command in `.claude/commands/`, ensure ALL of these:

### 1. Frontmatter (Required)
```markdown
---
description: One-line description of what the command does
---
```

### 2. Documentation (Required)
- [ ] Clear title (`# Command Name`)
- [ ] Usage section with example (`## Usage`)
- [ ] What it does (`## What This Does`)
- [ ] Expected output examples
- [ ] When to use it
- [ ] Troubleshooting section (if complex)
- [ ] Related commands

### 3. **IMPLEMENTATION (CRITICAL - MOST COMMONLY FORGOTTEN!)**

**Every command MUST have ONE of these:**

#### Option A: Bash Script
```markdown
## Implementation

Run the command:

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```
\```
```

#### Option B: Python Script
```markdown
## Implementation

Run the script:

```bash
python "$(dirname "$0")/../scripts/script_name.py"
```
\```
```

#### Option C: Agent Invocation
```markdown
## Implementation

Invoke the <agent-name> agent with prompt:

```
<Detailed instructions for the agent>

1. Do X
2. Do Y
3. Report Z
```
\```
```

#### Option D: Tool Invocation (gh, git, npm, etc.)
```markdown
## Implementation

Run GitHub CLI:

```bash
gh pr create --title "Title" --body "Body"
```
\```
```

---

## 🚨 Common Mistakes

### ❌ WRONG: No Implementation
```markdown
# Format Code

This command formats your code.

## Usage
/format

## What This Does
Runs black, isort, ruff on your code.
```

**Problem**: Describes what should happen, but doesn't tell Claude HOW to do it!

### ✅ CORRECT: With Implementation
```markdown
# Format Code

This command formats your code.

## Usage
/format

## What This Does
Runs black, isort, ruff on your code.

## Implementation

Run formatters:

```bash
black . && isort . && ruff check --fix .
```
\```
```

---

## 🧪 Testing Your Command

### Before Committing

1. **Run validation**:
   ```bash
   python plugins/autonomous-dev/scripts/validate_commands.py
   ```

   Should show: `✅ your-command.md`

2. **Test manually**:
   - Restart Claude Code
   - Run `/your-command`
   - Verify it executes (not just shows docs)

3. **Check pre-commit hook**:
   ```bash
   git add .claude/commands/your-command.md
   git commit -m "test"
   ```

   Pre-commit hook will run validation automatically.

### Validation Checks

The validator (`validate_commands.py`) checks for:
- ✅ Bash code blocks with actual commands
- ✅ Agent invocation instructions ("Invoke the X agent")
- ✅ Script execution (`python script.py`)

If missing ALL of these → ❌ FAIL

---

## 📋 Command Template

Copy this template for new commands:

```markdown
---
description: One-line description of what this command does
---

# Command Name

Brief overview paragraph.

---

## Usage

\```bash
/command-name [optional-args]
\```

**Time**: < X seconds/minutes
**Scope**: What it affects

---

## What This Does

Bullet points or numbered list explaining:
1. First step
2. Second step
3. Third step

---

## Expected Output

\```
Example output here...
\```

---

## When to Use

- ✅ Scenario 1
- ✅ Scenario 2
- ✅ Scenario 3

---

## Implementation

[CRITICAL - CHOOSE ONE PATTERN BELOW]

[Option A: Bash Script]
Run the command:

\```bash
your-bash-command-here
\```

[Option B: Python Script]
Run the script:

\```bash
python "$(dirname "$0")/../scripts/your_script.py"
\```

[Option C: Agent Invocation]
Invoke the <agent-name> agent with prompt:

\```
Detailed instructions for agent:

1. Do X
2. Do Y
3. Report Z
\```

---

## Troubleshooting

Common issues and solutions.

---

## Related Commands

- `/other-command` - Related functionality

---

**Final note summarizing the command's purpose.**
```

---

## 🔧 Automated Prevention

This issue is now prevented automatically:

### Pre-commit Hook
Located: `.git/hooks/pre-commit`

Runs `validate_commands.py` before every commit. Will **BLOCK** commits with commands missing implementations.

### CI/CD (If configured)
Add to your CI pipeline:
```yaml
- name: Validate Commands
  run: python plugins/autonomous-dev/scripts/validate_commands.py
```

### Manual Check
Run anytime:
```bash
python plugins/autonomous-dev/scripts/validate_commands.py
```

---

## 📊 Stats (As of 2025-10-25)

- **Total commands**: 22
- **Commands with implementations**: 22 (100%)
- **Commands fixed**: 15 (were missing implementations)
- **Validation script created**: 2025-10-25
- **Pre-commit hook updated**: 2025-10-25

---

## 🎯 Why This Matters

**Before validation**:
- 15/22 commands (68%) were broken
- Commands showed docs but did nothing
- Users frustrated, filed duplicate bug reports
- Wasted hours debugging "why doesn't this work?"

**After validation**:
- 22/22 commands (100%) have implementations
- Impossible to commit broken command
- Caught at creation time, not runtime
- Quality enforced automatically

---

## 🚀 Next Steps

### Easy Way: Use The Generator (Recommended)

```bash
python plugins/autonomous-dev/scripts/new_command.py my-command
```

The generator:
- ✅ Creates command with proper structure
- ✅ Forces you to choose implementation type
- ✅ Includes `## Implementation` section automatically
- ✅ Validates immediately after creation
- ✅ Shows next steps

### Manual Way: Copy Template

If you prefer manual creation:

1. Copy the template above
2. Fill in documentation
3. **Add implementation section** (don't forget!)
4. Run `validate_commands.py`
5. Test manually
6. Commit (pre-commit hook will validate again)

---

**Remember**: A command without implementation is just documentation. It does nothing.

**Make it executable, not just descriptive!**
