---
name: command-management
description: Command creation and deployment workflow. Use when creating, editing, or deploying slash commands to ensure visibility. (project)
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# Command Management Skill

**Purpose**: Ensure slash commands are created correctly, deployed properly, and become visible in Claude Code.

**Use this skill when**:
- User wants to create a new slash command
- User wants to edit an existing command
- User asks why a command isn't visible
- User asks how to deploy commands

---

## The Problem This Solves

**Two-Location Issue**:
- Commands edited in dev location: `.claude/commands/`
- Claude reads from runtime location: `~/.claude/plugins/.../commands/`
- Without sync + restart, commands not visible

**Implementation Issue**:
- Commands without `## Implementation` section are just docs
- They show up but don't execute anything

---

## Workflow: Create New Command

When user wants to create a new command:

### 1. Generate Command Structure

```bash
python plugins/autonomous-dev/scripts/new_command.py <command-name>
```

**Prompts user for**:
- Description
- Title
- Overview
- Implementation type (bash/script/agent)

**Creates**: `.claude/commands/<command-name>.md` with proper structure.

### 2. Customize Implementation

Read the generated file and identify TODOs:
```bash
grep -n "TODO" .claude/commands/<command-name>.md
```

Edit to replace TODOs with actual implementation:
- Bash commands
- Script path
- Agent invocation

### 3. Validate

```bash
python plugins/autonomous-dev/scripts/validate_commands.py | grep <command-name>
```

Must show: `✅ <command-name>.md`

### 4. Deploy

```bash
python plugins/autonomous-dev/scripts/deploy_command.py <command-name>
```

This:
- Validates implementation
- Syncs to runtime location
- Shows restart instructions
- Provides verification steps
- Shows commit command

### 5. Instruct User

Tell user:
```
✅ Command created and deployed!

CRITICAL: You must restart Claude Code now:
  • Mac: Cmd+Q then reopen
  • Linux/Windows: Ctrl+Q then reopen

After restart, test:
  /<command-name>

Then commit:
  git add .claude/commands/<command-name>.md
  git commit -m "feat: add /<command-name> command"
```

---

## Workflow: Edit Existing Command

When user wants to modify a command:

### 1. Identify Command File

```bash
ls .claude/commands/ | grep <command-name>
```

### 2. Make Edits

Use Edit tool to modify the command file.

### 3. Validate

```bash
python plugins/autonomous-dev/scripts/validate_commands.py | grep <command-name>
```

### 4. Deploy

```bash
python plugins/autonomous-dev/scripts/deploy_command.py <command-name>
```

### 5. Instruct User

Same as create workflow - restart required.

---

## Workflow: Command Not Visible

When user says "command isn't showing up":

### 1. Diagnose

Check if command file exists:
```bash
ls .claude/commands/<command-name>.md
```

Check if synced to runtime:
```bash
find ~/.claude/plugins/marketplaces -name "<command-name>.md"
```

### 2. Sync If Needed

```bash
python plugins/autonomous-dev/scripts/deploy_command.py <command-name>
```

### 3. Remind About Restart

```
⚠️  Did you restart Claude Code after deploying?

Commands won't appear until restart:
  • Quit: Cmd+Q or Ctrl+Q
  • Reopen Claude Code

After restart, type /<command-name>
```

### 4. Verify With Health Check

After restart, user should run:
```
/health-check
```

Should show command in the list as PASS.

---

## Workflow: Deploy All Commands

When user wants to deploy multiple commands:

```bash
python plugins/autonomous-dev/scripts/deploy_command.py --all
```

This validates and syncs all commands at once.

---

## Implementation Patterns

### Bash Command Pattern

```markdown
## Implementation

Run the command:

```bash
echo "Hello World"
# Your bash commands here
```
\```
```

### Python Script Pattern

```markdown
## Implementation

Run the script:

```bash
python "$(dirname "$0")/../scripts/my_script.py"
```
\```
```

### Agent Invocation Pattern

```markdown
## Implementation

Invoke the <agent-name> agent with prompt:

```
Detailed instructions for agent:

1. Do X
2. Do Y
3. Report Z
```
\```
```

---

## Validation Rules

Commands MUST have ONE of:
- ✅ Bash code block with commands
- ✅ Script execution path
- ✅ Agent invocation instructions

Commands CANNOT:
- ❌ Have only documentation
- ❌ Have TODO placeholders in Implementation
- ❌ Missing Implementation section entirely

---

## Common Errors & Fixes

### "Command shows docs but doesn't execute"

**Cause**: Missing or incomplete Implementation section

**Fix**:
```bash
# Check implementation
tail -20 .claude/commands/<command-name>.md

# Should show ## Implementation with bash/script/agent

# If missing, edit to add it
vim .claude/commands/<command-name>.md

# Validate
python plugins/autonomous-dev/scripts/validate_commands.py

# Deploy
python plugins/autonomous-dev/scripts/deploy_command.py <command-name>
```

### "Command not in autocomplete"

**Cause**: Not synced or not restarted

**Fix**:
```bash
# Deploy (syncs automatically)
python plugins/autonomous-dev/scripts/deploy_command.py <command-name>

# User MUST restart
# After restart, should appear
```

### "Validation fails"

**Cause**: Implementation section incorrect or missing

**Fix**:
```bash
# See specific error
python plugins/autonomous-dev/scripts/validate_commands.py

# Fix the implementation
# Must include bash commands, script path, or agent invocation

# Validate again
python plugins/autonomous-dev/scripts/validate_commands.py
```

---

## Best Practices

### 1. Always Use Generator

Don't create commands manually. Use:
```bash
python plugins/autonomous-dev/scripts/new_command.py <name>
```

This ensures proper structure.

### 2. Always Use Deploy Script

Don't sync manually. Use:
```bash
python plugins/autonomous-dev/scripts/deploy_command.py <name>
```

This ensures complete workflow.

### 3. Always Validate First

Before deploying:
```bash
python plugins/autonomous-dev/scripts/validate_commands.py
```

Catches issues early.

### 4. Always Remind About Restart

Commands won't appear without restart. Always tell user to restart.

### 5. Always Verify After Restart

User should test command works:
```
/<command-name>
/health-check  # Should show command as PASS
```

---

## Quick Reference

**Create command**:
```bash
python plugins/autonomous-dev/scripts/new_command.py <name>
vim .claude/commands/<name>.md  # Customize
python plugins/autonomous-dev/scripts/deploy_command.py <name>
# Restart Claude Code
/<name>  # Test
git commit  # Commit
```

**Edit command**:
```bash
vim .claude/commands/<name>.md
python plugins/autonomous-dev/scripts/deploy_command.py <name>
# Restart Claude Code
/<name>  # Test
```

**Deploy all**:
```bash
python plugins/autonomous-dev/scripts/deploy_command.py --all
# Restart Claude Code
```

---

## When To Use This Skill

Invoke this skill when user:
- "Create a new command for X"
- "Add a slash command that does Y"
- "Why isn't /my-command showing up?"
- "How do I deploy commands?"
- "Command exists but doesn't work"
- "Update /existing-command to do Z"

**Do NOT invoke for**:
- Using existing commands (just run them)
- Asking what a command does (just explain)
- General questions about commands (answer directly)

---

**This skill ensures commands are always visible and working by enforcing the complete workflow.**
