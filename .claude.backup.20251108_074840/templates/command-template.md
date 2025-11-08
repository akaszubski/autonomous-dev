---
description: Brief one-line description of what this command does (< 80 chars)
---

# Command Name

**Brief description of the command's purpose**

---

## Usage

```bash
/command-name [optional-arg]
```

**Time**: Estimated execution time
**Scope**: What the command operates on

---

## What This Does

Clear explanation of:
- What the command accomplishes
- What happens when you run it
- What it doesn't do (if clarification needed)

Example:
```bash
# Show expected command output or behavior
```

---

## When to Use

**Run this command when**:
- ✅ Scenario 1
- ✅ Scenario 2
- ✅ Scenario 3

**Don't need it if**:
- ❌ Scenario where command isn't needed
- ❌ Alternative approach exists

---

## Related Commands

- `/other-command` - How it relates to this command
- `/another-command` - Why you might use both

---

## Implementation

**REQUIRED SECTION** - Must include one of:

### Option A: Script Execution
```bash
python "$(dirname "$0")/../scripts/your_script.py"
```

### Option B: Agent Invocation
Invoke the [agent-name] agent to [what it does].

The agent will:
1. Step 1
2. Step 2
3. Step 3

### Option C: Direct Bash Commands
```bash
# Execute commands directly
pytest tests/ --cov=src -v
```

---

## Command Authoring Guidelines

### Required Sections
1. **Frontmatter** (`---description: ...---`)
2. **Header** (`# Command Name`)
3. **Usage** (with code block showing syntax)
4. **What This Does** (clear explanation)
5. **Implementation** (execution instructions)

### Optional But Recommended
- **When to Use** (helps users know if command applies)
- **Related Commands** (shows ecosystem connections)
- **Examples** (concrete use cases)
- **Troubleshooting** (common issues)

### Best Practices

**DO**:
- ✅ Start with clear, concise description
- ✅ Show actual command syntax in usage block
- ✅ Explain what happens step-by-step
- ✅ Include concrete examples
- ✅ End with Implementation section showing how to execute
- ✅ Use consistent formatting (headers, code blocks, lists)

**DON'T**:
- ❌ Skip the Implementation section (causes silent failures!)
- ❌ Use vague descriptions ("does stuff")
- ❌ Forget to show actual command syntax
- ❌ Include implementation details in What This Does (save for Implementation)
- ❌ Create commands that duplicate existing functionality

---

## Testing Your Command

Before committing:

1. **Validate structure**:
   ```bash
   python scripts/validate_commands.py
   ```

2. **Test execution**:
   - Run the command: `/your-command`
   - Verify it executes (doesn't just show docs)
   - Check output matches documentation

3. **Check for issues**:
   - Does it have Implementation section? ✓
   - Does validation pass? ✓
   - Does it execute without errors? ✓

---

## Why Implementation Section is Required

**Without Implementation section**:
- ❌ Command only shows documentation (silent failure)
- ❌ Users confused: "It doesn't do anything!"
- ❌ Wastes user time with trial-and-error

**With Implementation section**:
- ✅ Command actually executes
- ✅ Clear what code/agent runs
- ✅ Validation can verify execution path exists

**This is Issue #13** - Commands without Implementation sections cause silent failures. Always include this section!

---

## Examples

See existing commands for reference:
- `commands/test.md` - Direct bash execution
- `commands/health-check.md` - Script execution
- `commands/align-project.md` - Agent invocation
- `commands/auto-implement.md` - Orchestrator invocation

---

**Template Version**: 1.0.0
**Last Updated**: 2025-10-26
**Required for**: Issue #13 fix (prevent silent failures)
