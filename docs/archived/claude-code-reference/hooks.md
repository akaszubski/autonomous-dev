# Claude Code Hooks - Complete Reference Guide

> **Source**: https://code.claude.com/docs/en/hooks
> **Downloaded**: 2025-12-16

## Table of Contents

1. [Introduction](#introduction)
2. [Hook Configuration](#hook-configuration)
3. [Hook Events Reference](#hook-events-reference)
4. [Hook Input Formats](#hook-input-formats)
5. [Hook Output Formats](#hook-output-formats)
6. [Working with MCP Tools](#working-with-mcp-tools)
7. [Examples](#examples)
8. [Security Considerations](#security-considerations)
9. [Debugging](#debugging)

---

## Introduction

Claude Code hooks are user-defined shell commands or LLM-based prompts that execute at various points in Claude Code's lifecycle. Hooks provide deterministic control over Claude Code's behavior, ensuring certain actions always happen rather than relying on the LLM to choose to run them.

### Common Use Cases

- **Notifications**: Customize how you get notified when Claude Code is awaiting your input or permission
- **Automatic formatting**: Run prettier, gofmt, black, etc. after every file edit
- **Logging**: Track and count all executed commands for compliance or debugging
- **Feedback**: Provide automated feedback when Claude Code produces code that doesn't follow conventions
- **Custom permissions**: Block modifications to production files or sensitive directories
- **Validation**: Validate code quality, security patterns, or compliance rules

---

## Hook Configuration

### Settings Files

Claude Code hooks are configured in your settings files:

- `~/.claude/settings.json` - User settings (applies to all projects)
- `.claude/settings.json` - Project settings (specific to current project)
- `.claude/settings.local.json` - Local project settings (not committed to git)
- Enterprise managed policy settings

### Configuration Structure

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here"
          }
        ]
      }
    ]
  }
}
```

### Configuration Fields

- **EventName**: Hook event type (PreToolUse, PostToolUse, UserPromptSubmit, etc.)
- **matcher**: Pattern to match tool names (case-sensitive)
  - Simple strings match exactly: `Write` matches only Write tool
  - Supports regex: `Edit|Write` or `Notebook.*`
  - Use `*` to match all tools
  - Can be empty string or omitted for non-matching events
- **hooks**: Array of hooks to execute when pattern matches
- **type**: `"command"` (bash) or `"prompt"` (LLM-based)
- **command**: Bash command to execute (can use `$CLAUDE_PROJECT_DIR`)
- **prompt**: Prompt to send to LLM for evaluation
- **timeout**: Optional seconds before canceling (default: 60 seconds)

### Project-Specific Hook Scripts

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-style.sh"
          }
        ]
      }
    ]
  }
}
```

---

## Hook Events Reference

| Event | Timing | Useful For | Can Block |
|-------|--------|------------|-----------|
| `PreToolUse` | Before tool execution | Permissions, validation | Yes |
| `PermissionRequest` | On permission dialog | Custom permission logic | Yes |
| `PostToolUse` | After tool execution | Formatting, validation | Feedback only |
| `UserPromptSubmit` | Before prompt processing | Input validation, context | Yes |
| `Notification` | On notifications | Custom alerts | No |
| `Stop` | When Claude finishes | Decision to continue | Yes |
| `SubagentStop` | When subagent finishes | Decision to continue | Yes |
| `PreCompact` | Before compaction | Prevention logic | No |
| `SessionStart` | Session initialization | Setup, context | No |
| `SessionEnd` | Session cleanup | Logging, cleanup | No |

### PreToolUse

Runs before a tool is executed. Can block or modify the tool call.

**Use cases:**
- Security validation
- Auto-approval for safe operations
- Input validation
- Logging

### PostToolUse

Runs after a tool completes. Cannot block but can provide feedback.

**Use cases:**
- Auto-formatting code
- Validation checks
- Logging results
- Triggering follow-up actions

### UserPromptSubmit

Runs when user submits a prompt, before processing.

**Use cases:**
- Input validation
- Adding context
- Workflow enforcement
- Blocking certain requests

### Stop / SubagentStop

Runs when Claude or a subagent finishes.

**Use cases:**
- Decision to continue working
- Triggering follow-up actions
- Git automation
- Notification

### SessionStart

Runs when a session begins.

**Use cases:**
- Environment setup
- Loading context
- Initialization

### SessionEnd

Runs when a session ends.

**Use cases:**
- Cleanup
- Logging
- State persistence

---

## Hook Input Formats

### Common Fields (All Events)

```json
{
  "session_id": "string",
  "transcript_path": "Path to conversation JSON",
  "cwd": "Current working directory",
  "permission_mode": "default|plan|acceptEdits|bypassPermissions",
  "hook_event_name": "string"
}
```

### PreToolUse Input

```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

### PostToolUse Input

```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": { },
  "tool_response": {
    "filePath": "/path/to/file.txt",
    "success": true
  }
}
```

### UserPromptSubmit Input

```json
{
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Write a function to calculate factorial"
}
```

### SessionStart Input

```json
{
  "hook_event_name": "SessionStart",
  "source": "startup|resume|clear|compact"
}
```

---

## Hook Output Formats

### Exit Codes

- **Exit code 0**: Success (stdout added as context or shown in verbose mode, JSON parsed for control)
- **Exit code 2**: Blocking error (only stderr used, action blocked)
- **Other exit codes**: Non-blocking error (stderr shown, execution continues)

### JSON Output Structure

```json
{
  "continue": true,
  "stopReason": "string",
  "suppressOutput": true,
  "systemMessage": "string"
}
```

### PreToolUse Decision Control

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "reason",
    "updatedInput": { }
  }
}
```

### UserPromptSubmit Decision Control

```json
{
  "decision": "block",
  "reason": "explanation",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "additional context"
  }
}
```

### Stop/SubagentStop Decision Control

```json
{
  "decision": "block",
  "reason": "Must be provided when Claude is blocked"
}
```

---

## Working with MCP Tools

MCP tools follow pattern: `mcp__<server>__<tool>`

Examples:
- `mcp__memory__create_entities`
- `mcp__filesystem__read_file`
- `mcp__github__search_repositories`

### Configuring Hooks for MCP Tools

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory__.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Memory operation' >> ~/log.txt"
          }
        ]
      }
    ]
  }
}
```

---

## Examples

### Example 1: Logging Shell Commands

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.command' >> ~/.claude/bash-commands.log"
          }
        ]
      }
    ]
  }
}
```

### Example 2: File Protection Hook

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -c \"import json, sys; data=json.load(sys.stdin); path=data.get('tool_input',{}).get('file_path',''); sys.exit(2 if any(p in path for p in ['.env', '.git/']) else 0)\""
          }
        ]
      }
    ]
  }
}
```

### Example 3: Auto-Approval for Documentation

```python
#!/usr/bin/env python3
import json
import sys

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(1)

if input_data.get("tool_name") == "Read":
    file_path = input_data.get("tool_input", {}).get("file_path", "")
    if file_path.endswith((".md", ".mdx", ".txt")):
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Documentation auto-approved"
            }
        }
        print(json.dumps(output))
        sys.exit(0)

sys.exit(0)
```

### Example 4: SessionStart Environment Setup

```bash
#!/bin/bash

if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo 'export NODE_ENV=production' >> "$CLAUDE_ENV_FILE"
  echo 'export PATH="$PATH:./node_modules/.bin"' >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

### Example 5: Auto-Format After Write

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/auto_format.py"
          }
        ]
      }
    ]
  }
}
```

```python
#!/usr/bin/env python3
"""Auto-format files after writing."""
import json
import sys
import subprocess
from pathlib import Path

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")

if file_path.endswith(".py"):
    subprocess.run(["black", file_path], check=False)
elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
    subprocess.run(["prettier", "--write", file_path], check=False)

sys.exit(0)
```

---

## Security Considerations

### Disclaimer

**USE AT YOUR OWN RISK**: Claude Code hooks execute arbitrary shell commands automatically.

You acknowledge that:
- You are responsible for configured commands
- Hooks can modify, delete, or access any files your user account can
- Malicious or poorly written hooks can cause data loss
- Anthropic provides no warranty for damages

### Security Best Practices

1. **Validate and sanitize inputs**: Never trust input data blindly
2. **Quote shell variables**: Use `"$VAR"` not `$VAR`
3. **Block path traversal**: Check for `..` in file paths
4. **Use absolute paths**: Use `$CLAUDE_PROJECT_DIR` for relative paths
5. **Skip sensitive files**: Avoid `.env`, `.git/`, keys, etc.
6. **Limit permissions**: Use least-privilege principle
7. **Audit logging**: Log security-sensitive operations

---

## Debugging

### Basic Troubleshooting

1. Run `/hooks` to see if hook is registered
2. Verify JSON syntax in settings
3. Test commands manually first
4. Check script permissions
5. Use `claude --debug` for detailed execution logs

### Common Issues

- **Quotes not escaped**: Use `\"` in JSON strings
- **Wrong matcher**: Tool names are case-sensitive
- **Command not found**: Use full paths for scripts
- **Timeout too short**: Increase timeout value
- **Exit code wrong**: Remember exit 2 = block, exit 0 = success

### Debug Mode

Enable debug output:

```bash
export CLAUDE_CODE_DEBUG=true
claude-code
```

---

## Quick Reference: Matcher Patterns

| Pattern | Matches |
|---------|---------|
| `*` | All tools |
| `Write` | Write tool only |
| `Edit\|Write` | Edit or Write |
| `Bash` | Bash commands |
| `Read` | File reads |
| `mcp__memory__.*` | Memory MCP tools |
| `Notebook.*` | Notebook tools |

---

## Hook Execution Details

- **Timeout**: 60 seconds default (configurable per command)
- **Parallelization**: All matching hooks run in parallel
- **Environment variables**: `CLAUDE_PROJECT_DIR`, `CLAUDE_CODE_REMOTE`, all standard vars
- **Input**: JSON via stdin
- **Output handling**: Varies by event (verbose mode, debug, context injection)

---

## Additional Resources

- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [Security Documentation](https://code.claude.com/docs/en/security)
- [Plugin Components](https://code.claude.com/docs/en/plugins-reference#hooks)
