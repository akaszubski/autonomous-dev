# MCP Auto-Approval for Tool Calls

**Version**: v3.38.0 (Extended for Main Conversation Support)
**Last Updated**: 2025-12-08
**Status**: Opt-in feature (disabled by default, requires explicit enablement)
**GitHub Issue**: #73 (original), #TBD (main conversation support)

---

## Table of Contents

- [Overview](#overview)
- [What's New in v3.38.0](#whats-new-in-v3380)
- [Why MCP Auto-Approval?](#why-mcp-auto-approval)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Security Model](#security-model)
- [How It Works](#how-it-works)
- [Policy File Reference](#policy-file-reference)
- [Troubleshooting](#troubleshooting)
- [For Contributors](#for-contributors)
- [Architecture](#architecture)

---

## Overview

**MCP Auto-Approval** is an opt-in feature that automatically approves MCP (Model Context Protocol) tool calls from both **main conversation** and **subagent workflows**. This eliminates the need for manual approval prompts for trusted operations, creating a seamless development experience.

**Key Benefits**:
- **Zero Interruptions**: No manual approval prompts for trusted operations
- **Flexible Modes**: Auto-approve everywhere or only in subagents
- **Security**: 5 layers of defense-in-depth validation (6 in subagent mode)
- **Performance**: < 5ms validation overhead per tool call
- **Audit Trail**: Every approval/denial logged for compliance
- **Circuit Breaker**: Auto-disable after 10 consecutive denials (prevents runaway automation)

**Typical Workflows**:

**Everywhere Mode** (default when enabled):
```
Main conversation:
User: "what github issues should I work on next"
Claude: [Bash: gh issue list] → [AUTO-APPROVED] → Shows issues

Subagent workflow:
User → /auto-implement → researcher agent → [Bash: pytest] → [AUTO-APPROVED] → ...
```

**Subagent-Only Mode** (legacy behavior):
```
Main conversation:
User: "what github issues should I work on next"
Claude: [Bash: gh issue list] → [PROMPT: Approve tool use?] → User approves

Subagent workflow:
User → /auto-implement → researcher agent → [Bash: pytest] → [AUTO-APPROVED] → ...
```

---

## What's New in v3.38.0

**Main Conversation Support**: Auto-approval now works in both main conversation and subagent workflows.

**Changes**:
- **New default**: `MCP_AUTO_APPROVE=true` now enables auto-approval everywhere (main + subagents)
- **Legacy mode**: Use `MCP_AUTO_APPROVE=subagent_only` to restore old behavior (subagents only)
- **Security unchanged**: Same whitelist/blacklist/path validation in both modes
- **Agent whitelist**:
  - **Everywhere mode** (`MCP_AUTO_APPROVE=true`): Whitelist check SKIPPED - all agents trusted
  - **Subagent-only mode** (`MCP_AUTO_APPROVE=subagent_only`): Whitelist check ENFORCED - only listed agents trusted

**Migration**: Existing users with `MCP_AUTO_APPROVE=true` will automatically get the new everywhere mode. To restore old behavior, set `MCP_AUTO_APPROVE=subagent_only`.

---

## Why MCP Auto-Approval?

### The Problem

Claude Code 2.0 introduced MCP (Model Context Protocol) for enhanced tool integration. However, by default, every tool call from a subagent requires manual approval:

```
Researcher agent: "I'll run pytest tests/unit/"
[PROMPT] Approve Bash tool use for command: pytest tests/unit/? (y/n)
User: y

Researcher agent: "I'll check git status"
[PROMPT] Approve Bash tool use for command: git status? (y/n)
User: y

Researcher agent: "I'll read the test file"
[PROMPT] Approve Read tool use for file: tests/unit/test_foo.py? (y/n)
User: y

... (50+ prompts per /auto-implement run)
```

This defeats the purpose of autonomous development - the user becomes a "permission clicker" instead of focusing on creative work.

### The Solution

MCP Auto-Approval implements **defense-in-depth validation** to safely auto-approve trusted operations:

**Core Security Layers** (all modes):
1. **User Consent**: Must explicitly opt-in via `MCP_AUTO_APPROVE=true`
2. **Tool Whitelist**: Only approved tools (Bash, Read, Write, Grep, etc.)
3. **Command/Path Validation**: Whitelist/blacklist enforcement (e.g., allow `gh issue list`, deny `rm -rf`)
4. **Audit Logging**: Full trail of every approval/denial
5. **Circuit Breaker**: Auto-disable after 10 consecutive denials

**Additional Layer in Subagent Mode**:
6. **Agent Whitelist** (subagent_only mode): Only trusted agents can auto-approve (researcher, planner, test-master, implementer, reviewer, doc-master). In everywhere mode, all agents are trusted.

**Result**: Zero prompts for trusted operations, manual approval for dangerous operations, full audit trail for compliance.

---

## Quick Start

### Step 1: Configure Claude Code Permissions

Add to `~/.claude/settings.json` (user-level) for auto-approval of all tools:

```json
{
  "permissions": {
    "allow": [
      "Bash(:*)",
      "Read(**)",
      "Write(**)",
      "Edit(**)",
      "Glob",
      "Grep",
      "NotebookEdit",
      "Task",
      "WebFetch",
      "WebSearch",
      "TodoWrite",
      "ExitPlanMode",
      "BashOutput",
      "KillShell",
      "AskUserQuestion",
      "Skill",
      "SlashCommand",
      "EnterPlanMode",
      "AgentOutputTool",
      "mcp__"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)",
      "Read(./secrets/**)",
      "Read(**/credentials/**)",
      "Write(~/.ssh/**)",
      "Write(~/.aws/**)",
      "Write(/etc/**)",
      "Write(/usr/**)",
      "Write(/System/**)",
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)",
      "Bash(sudo:*)",
      "Bash(chmod 777:*)",
      "Bash(eval:*)",
      "Bash(dd:*)",
      "Bash(mkfs:*)",
      "Bash(shutdown:*)",
      "Bash(reboot:*)"
    ],
    "ask": []
  }
}
```

**Permission Format Reference** (from [official Claude Code docs](https://code.claude.com/docs/en/settings)):

| Tool | Format | Example |
|------|--------|---------|
| Bash (all) | `Bash(:*)` | Allows all shell commands |
| Bash (prefix) | `Bash(npm run:*)` | Allows `npm run test`, `npm run build`, etc. |
| Read (all) | `Read(**)` | Allows reading any file |
| Read (path) | `Read(./src/**)` | Allows reading files in src/ |
| Write (all) | `Write(**)` | Allows writing any file |
| Edit (all) | `Edit(**)` | Allows editing any file |
| Other tools | `Glob`, `Grep`, `WebFetch` | Just the tool name |
| MCP tools | `mcp__` | Prefix for all MCP server tools |

**Important**: Claude Code uses **prefix matching** for Bash, not regex. Use `:*` at the end for wildcards.

**Sources**:
- [Claude Code Settings - Official Docs](https://code.claude.com/docs/en/settings)
- [ggrigo/claude-code-tools - SETTINGS_JSON_GUIDE.md](https://github.com/ggrigo/claude-code-tools/blob/main/docs/SETTINGS_JSON_GUIDE.md)
- [Claude Code Built-in Tools Reference](https://www.vtrivedy.com/posts/claudecode-tools-reference)

### Step 2: Enable Auto-Approval Environment Variable

Add to `.env` file in your project root:

```bash
# Enable MCP auto-approval everywhere (main conversation + subagents)
MCP_AUTO_APPROVE=true

# OR: Only auto-approve in subagent workflows (legacy mode)
# MCP_AUTO_APPROVE=subagent_only
```

### Step 3: Run /auto-implement

```bash
# First run - you'll see consent prompt
/auto-implement "Add user authentication feature"

# On first subagent tool call, you see:
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  🚀 MCP Auto-Approval for Subagent Tool Calls                ║
║                                                              ║
║  Automatic tool approval enabled for trusted operations:    ║
║                                                              ║
║    ✓ Trusted agents: researcher, planner, implementer, ...  ║
║    ✓ Safe commands: pytest, git status, ls, cat, grep, ...  ║
║    ✓ Project files only (no /etc, /var, /root access)       ║
║    ✓ Dangerous commands blocked (rm -rf, sudo, eval, ...)   ║
║                                                              ║
║  HOW TO OPT OUT:                                            ║
║                                                              ║
║  Remove or set to false in .env file:                       ║
║    MCP_AUTO_APPROVE=false                                   ║
║                                                              ║
║  See docs/TOOL-AUTO-APPROVAL.md for details                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Do you want to enable automatic tool approval? (Y/n):

# Choose Y (default) or n
# Your choice is saved in ~/.autonomous-dev/user_state.json
```

### Step 4: Enjoy Zero-Interruption Workflow

After consent, all trusted operations are auto-approved:

```
Researcher agent invokes Bash: pytest tests/unit/
[AUTO-APPROVED] ✓ (whitelist match: pytest*)

Implementer agent invokes Write: /path/to/project/src/auth.py
[AUTO-APPROVED] ✓ (project directory, trusted agent)

Security-auditor agent invokes Bash: rm -rf /tmp/sensitive
[DENIED] ✗ (blacklist match: rm -rf*, manual approval required)
```

---

## Configuration

### Settings Templates (NEW in v3.38.0)

Choose the template that matches your security/convenience preference:

| Template | Description | Use When |
|----------|-------------|----------|
| **settings.autonomous-dev.json** | Full auto-approval with layered security (RECOMMENDED) | You want zero prompts with defense-in-depth |
| **settings.strict-mode.json** | Vibe coding with full enforcement | You want auto-orchestration on natural language |
| **settings.permission-batching.json** | 80% prompt reduction, batches writes | You want some oversight on writes |
| **settings.granular-bash.json** | Paranoid mode with explicit command whitelist | You want full control over every bash command |
| **settings.local.json** | Basic auto-approval | Simple setup with sensible defaults |

**Quick Setup** (copy to your project):
```bash
# Recommended: Full auto-approval with layered security
cp plugins/autonomous-dev/templates/settings.autonomous-dev.json .claude/settings.local.json

# Alternative: Paranoid mode with explicit bash whitelisting
cp plugins/autonomous-dev/templates/settings.granular-bash.json .claude/settings.local.json

# Alternative: Permission batching (80% reduction, still prompts for writes)
cp plugins/autonomous-dev/templates/settings.permission-batching.json .claude/settings.local.json
```

**Template Features Comparison**:

| Feature | autonomous-dev | strict-mode | permission-batching | granular-bash |
|---------|---------------|-------------|---------------------|---------------|
| Native `permissions` block | ✅ | ✅ | ✅ | ✅ |
| `mcp__` prefix for MCP tools | ✅ | ✅ | ✅ | ✅ |
| `disableBypassPermissionsMode` | ❌ | ✅ | ❌ | ✅ |
| `ask` level for specific tools | ✅ | ❌ | ✅ | ✅ |
| Granular bash patterns | ❌ | ❌ | ❌ | ✅ |
| PreToolUse hook | ✅ | ✅ | ✅ | ✅ |
| Auto-orchestration | ❌ | ✅ | ❌ | ❌ |

### Permission Format Reference

Claude Code uses **prefix matching** for permissions (not regex):

| Permission | Format | Example Matches |
|------------|--------|-----------------|
| All bash commands | `Bash(:*)` | Any bash command |
| Bash prefix | `Bash(pytest:*)` | `pytest`, `pytest tests/`, `pytest -v` |
| All file reads | `Read(**)` | Any file path |
| Specific directory | `Read(./src/**)` | Files in src/ directory |
| All file writes | `Write(**)` | Any file path |
| All file edits | `Edit(**)` | Any file path |
| Simple tools | `Glob`, `Grep`, `WebFetch` | Just the tool name |
| All MCP tools | `mcp__` | Any MCP server tool (prefix match) |

**Three Permission Levels**:
- **`allow`**: Auto-approve immediately (no prompt)
- **`ask`**: Prompt user for confirmation
- **`deny`**: Block silently (no prompt, operation fails)

**Security Setting**:
```json
{
  "permissions": {
    "disableBypassPermissionsMode": "disable"
  }
}
```
This prevents users from using `--dangerously-skip-permissions` flag, forcing reliance on configured policies.

### Environment Variables

Add to `.env` file in project root:

```bash
# Master switch - enables MCP auto-approval for subagent tool calls
MCP_AUTO_APPROVE=false       # Default: false (opt-in design)

# Custom policy file path (optional)
AUTO_APPROVE_POLICY_FILE=/path/to/custom_policy.json  # Default: plugins/autonomous-dev/config/auto_approve_policy.json
```

### Policy File

Default location: `plugins/autonomous-dev/config/auto_approve_policy.json`

**Structure**:
```json
{
  "version": "1.0",
  "description": "MCP Auto-Approval Policy - Whitelist/Blacklist for Safe Tool Execution",
  "bash": {
    "whitelist": [
      "pytest*",
      "git status",
      "git diff*",
      "git log*",
      "ls*",
      "cat*",
      "grep*"
    ],
    "blacklist": [
      "rm -rf*",
      "sudo*",
      "chmod 777*",
      "curl*|*bash",
      "eval*"
    ]
  },
  "file_paths": {
    "whitelist": [
      "/Users/*/Documents/GitHub/*",
      "/tmp/pytest-*"
    ],
    "blacklist": [
      "/etc/*",
      "/var/*",
      "/root/*",
      "*/.env",
      "*/secrets/*",
      "*/.ssh/*"
    ]
  },
  "agents": {
    "trusted": [
      "researcher",
      "planner",
      "test-master",
      "implementer",
      "reviewer",
      "doc-master"
    ],
    "restricted": [
      "security-auditor"
    ]
  }
}
```

**Glob Patterns**:
- `*` matches any characters within a path segment
- `?` matches a single character
- `[abc]` matches any character in brackets
- Examples:
  - `pytest*` matches `pytest`, `pytest tests/`, `pytest -v`
  - `git diff*` matches `git diff`, `git diff --cached`, `git diff HEAD~1`
  - `/tmp/*` matches any file in `/tmp/`

---

## Security Model

### 6 Layers of Defense-in-Depth

**1. Subagent Context Isolation**

Only auto-approve tool calls from subagents (not from main Claude session):

```python
# Check CLAUDE_AGENT_NAME environment variable
agent_name = os.getenv("CLAUDE_AGENT_NAME")
if not agent_name:
    # Not in subagent context → manual approval
    return {"approved": False, "reason": "Not in subagent context"}
```

**Why**: Prevents accidental auto-approval of user's manual tool invocations. Only autonomous workflows use auto-approval.

**2. Agent Whitelist** (subagent_only mode)

Agent whitelist enforcement depends on the auto-approval mode:

```json
{
  "agents": {
    "trusted": ["researcher", "planner", "test-master", "implementer", "reviewer", "doc-master"],
    "restricted": ["security-auditor"]
  }
}
```

**Enforcement**:
- **Everywhere mode** (`MCP_AUTO_APPROVE=true`): Whitelist check **SKIPPED** - all agents trusted
- **Subagent-only mode** (`MCP_AUTO_APPROVE=subagent_only`): Whitelist check **ENFORCED** - only listed agents trusted

**Why**: In everywhere mode, the user has opted to trust all agents (main + subagent workflows). In subagent_only mode, the whitelist provides granular control over which agents can auto-approve (e.g., security-auditor may need manual oversight).

**3. Tool Whitelist**

Only approved MCP tools are auto-approved:

```python
ALLOWED_TOOLS = ["Bash", "Read", "Write", "Grep", "Edit"]

if tool_name not in ALLOWED_TOOLS:
    # Unknown tool → manual approval
    return {"approved": False, "reason": f"Tool not whitelisted: {tool_name}"}
```

**Why**: Prevents auto-approval of future unknown tools that may have security implications.

**4. Command/Path Validation**

**Bash Commands** - Whitelist/Blacklist Enforcement:

```python
# Whitelist examples (safe commands)
"pytest*"           # Run tests
"git status"        # Check git status
"git diff*"         # View changes
"ls*"               # List files
"cat*"              # Read files
"grep*"             # Search files

# Blacklist examples (dangerous commands)
"rm -rf*"           # Recursive delete (data loss)
"sudo*"             # Privilege escalation
"chmod 777*"        # Insecure permissions
"curl*|*bash"       # Remote code execution
"eval*"             # Arbitrary code execution
```

**File Paths** - Path Traversal Prevention (CWE-22):

```python
# Whitelist examples (safe paths)
"/Users/*/Documents/GitHub/*"  # Project directories
"/tmp/pytest-*"                # Pytest temp directories
"/tmp/tmp*"                    # Temp files

# Blacklist examples (dangerous paths)
"/etc/*"                       # System configuration
"/var/*"                       # System data
"/root/*"                      # Root home directory
"*/.env"                       # Environment secrets
"*/secrets/*"                  # Credentials
"*/.ssh/*"                     # SSH keys
"*/id_rsa*"                    # Private keys
```

**Command Injection Prevention** (CWE-78):

```python
# Detect command chaining and injection
INJECTION_PATTERNS = [
    r';\s*\w+',           # Command chaining with semicolon
    r'&&\s+\w+',          # AND command chaining
    r'\|\|\s+\w+',        # OR command chaining
    r'\|\s+bash\b',       # Pipe to bash
    r'`[^`]+`',           # Backticks command substitution
    r'\$\([^)]+\)',       # $() command substitution
    r'\n\s*\w+',          # Newline command injection
]

if any(pattern.search(command) for pattern in INJECTION_PATTERNS):
    # Command injection detected → deny
    return {"approved": False, "reason": "Command injection detected"}
```

**5. Audit Logging**

Every approval/denial is logged to `logs/tool_approval_audit.log`:

```json
{
  "timestamp": "2025-11-15T10:30:45.123456Z",
  "event": "tool_call_approved",
  "tool": "Bash",
  "agent": "researcher",
  "command": "pytest tests/unit/",
  "reason": "Whitelist match: pytest*",
  "status": "approved"
}

{
  "timestamp": "2025-11-15T10:30:46.789012Z",
  "event": "tool_call_denied",
  "tool": "Bash",
  "agent": "implementer",
  "command": "rm -rf /tmp/important-data",
  "reason": "Blacklist match: rm -rf*",
  "status": "denied"
}
```

**Why**: Provides full audit trail for compliance, security monitoring, and debugging. Can integrate with SIEM systems (Splunk, ELK, etc.).

**6. Circuit Breaker**

Auto-disable after 10 consecutive denials:

```python
if denial_count >= CIRCUIT_BREAKER_THRESHOLD:
    # Circuit breaker tripped → disable auto-approval
    audit_log("circuit_breaker_tripped", {"denial_count": denial_count})
    # All future requests denied → manual approval required
```

**Why**: Prevents runaway automation if policy is misconfigured or agent behavior is unexpected. User must manually reset by restarting session.

---

## How It Works

### Request Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Subagent invokes MCP tool                                │
│    Example: researcher agent → Bash("pytest tests/")        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Claude Code 2.0 PreToolUse Hook                          │
│    Triggers: pre_tool_use.py (standalone script)            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Check MCP_AUTO_APPROVE environment variable              │
│    If false: return {"approved": False} (manual approval)   │
│    If true: continue to validation                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Check User Consent                                       │
│    First run: display consent prompt → save to user state   │
│    Subsequent runs: check ~/.autonomous-dev/user_state.json │
│    If consent denied: return {"approved": False}            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Validate Subagent Context                                │
│    Check CLAUDE_AGENT_NAME env var                          │
│    If not set: return {"approved": False}                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Validate Agent Whitelist                                 │
│    Check if agent in trusted list                           │
│    If restricted: return {"approved": False}                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Validate Tool Call (ToolValidator)                       │
│    - Check tool whitelist (Bash, Read, Write, Grep, Edit)   │
│    - Validate Bash command (whitelist/blacklist)            │
│    - Validate file paths (CWE-22 prevention)                │
│    - Detect command injection (CWE-78 prevention)           │
│    If validation fails: return {"approved": False}          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Audit Log Decision (ToolApprovalAuditor)                 │
│    Log to logs/tool_approval_audit.log                      │
│    Metrics: approval_count, denial_count, last_used         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Check Circuit Breaker                                    │
│    If denial_count >= 10: trip circuit breaker              │
│    If tripped: all future requests denied                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. Return Decision                                         │
│     {"approved": True, "reason": "Whitelist match: pytest*"}│
│     OR                                                       │
│     {"approved": False, "reason": "Blacklist match: rm -rf"}│
└─────────────────────────────────────────────────────────────┘
```

---

## Policy File Reference

### Full Default Policy

Location: `plugins/autonomous-dev/config/auto_approve_policy.json`

```json
{
  "version": "1.1",
  "description": "MCP Auto-Approval Policy - Whitelist/Blacklist for Safe Tool Execution",
  "bash": {
    "whitelist": [
      "pytest*",
      "git status",
      "git diff*",
      "git log*",
      "git branch*",
      "git add*",
      "git commit*",
      "git push*",
      "git pull*",
      "gh issue list*",
      "gh issue view*",
      "gh issue close*",
      "gh issue create*",
      "gh issue comment*",
      "gh pr list*",
      "gh pr view*",
      "gh pr create*",
      "gh pr close*",
      "gh pr checkout*",
      "gh pr comment*",
      "gh auth status",
      "gh repo view*",
      "ls*",
      "cat*",
      "head*",
      "tail*",
      "grep*",
      "wc*",
      "find*",
      "echo*",
      "pwd",
      "which*",
      "python -m pytest*",
      "python -c*",
      "python3 -m pytest*",
      "python3 -c*",
      "pip list",
      "pip show*",
      "cp *",
      "mv *",
      "mkdir*",
      "touch*"
    ],
    "blacklist": [
      "rm -rf*",
      "sudo*",
      "chmod 777*",
      "curl*|*bash",
      "wget*|*bash",
      "eval*",
      "exec*",
      "dd*",
      "mkfs*",
      "fdisk*",
      "kill -9*",
      "killall*",
      "> /dev/*",
      "shutdown*",
      "reboot*",
      "init 0*",
      "init 6*"
    ]
  },
  "file_paths": {
    "whitelist": [
      "/Users/*/Documents/GitHub/*",
      "/tmp/pytest-*",
      "/tmp/tmp*",
      "/private/tmp/pytest-*",
      "/private/tmp/tmp*"
    ],
    "blacklist": [
      "/etc/*",
      "/var/*",
      "/root/*",
      "*/.env",
      "*/secrets/*",
      "*/credentials/*",
      "*/.ssh/*",
      "*/id_rsa*",
      "*/id_ed25519*"
    ]
  },
  "agents": {
    "trusted": [
      "researcher",
      "planner",
      "test-master",
      "implementer",
      "reviewer",
      "doc-master"
    ],
    "restricted": [
      "security-auditor"
    ]
  }
}
```

### Customizing the Policy

**Option 1: Override Policy File**

Create custom policy file and set environment variable:

```bash
# .env
MCP_AUTO_APPROVE=true
AUTO_APPROVE_POLICY_FILE=/path/to/custom_policy.json
```

**Option 2: Extend Default Policy**

Copy default policy and add your own rules:

```bash
cp plugins/autonomous-dev/config/auto_approve_policy.json custom_policy.json
vim custom_policy.json
# Add your custom whitelist/blacklist entries
```

**Example: Add npm Commands**

```json
{
  "bash": {
    "whitelist": [
      "pytest*",
      "npm test",
      "npm run lint",
      "npm run build",
      "npm list"
    ],
    "blacklist": [
      "rm -rf*",
      "npm publish*"  // Prevent accidental publishing
    ]
  }
}
```

**Example: Allow Docker Commands (with restrictions)**

```json
{
  "bash": {
    "whitelist": [
      "docker ps",
      "docker images",
      "docker logs*",
      "docker exec* -- cat*"  // Read-only operations
    ],
    "blacklist": [
      "docker rm -f*",
      "docker rmi -f*",
      "docker system prune*"
    ]
  }
}
```

---

## Troubleshooting

### Auto-Approval Not Working

**Symptom**: Still seeing manual approval prompts for tool calls

**Diagnosis**:
```bash
# 1. Check environment variable
grep MCP_AUTO_APPROVE .env
# Should show: MCP_AUTO_APPROVE=true

# 2. Check user state file
cat ~/.autonomous-dev/user_state.json
# Should show: {"mcp_auto_approve_consent": true}

# 3. Check audit log
tail -20 logs/tool_approval_audit.log
# Look for denial reasons
```

**Common Fixes**:

1. **Environment variable not set**:
   ```bash
   echo "MCP_AUTO_APPROVE=true" >> .env
   ```

2. **User consent denied**:
   ```bash
   # Reset user state
   rm ~/.autonomous-dev/user_state.json
   # Re-run /auto-implement and choose "Y" at consent prompt
   ```

3. **Command not in whitelist**:
   ```bash
   # Check audit log for denied command
   grep "tool_call_denied" logs/tool_approval_audit.log | tail -5
   # Add command to whitelist in policy file
   ```

### Circuit Breaker Tripped

**Symptom**: All tool calls denied after multiple denials

**Diagnosis**:
```bash
# Check audit log for circuit breaker event
grep "circuit_breaker_tripped" logs/tool_approval_audit.log
```

**Fix**:
```bash
# Restart Claude Code session to reset circuit breaker
# (Circuit breaker state is in-memory, resets on restart)
pkill -9 claude
# Wait 2 seconds, then reopen Claude Code
```

### Path Validation Errors

**Symptom**: File read/write operations denied even though path looks safe

**Diagnosis**:
```bash
# Check audit log for path validation failures
grep "path_traversal" logs/tool_approval_audit.log
# OR
grep "path validation failed" logs/tool_approval_audit.log
```

**Common Fixes**:

1. **Path not in whitelist**:
   ```json
   // Add to policy file
   {
     "file_paths": {
       "whitelist": [
         "/Users/*/Documents/GitHub/*",
         "/Users/*/Documents/MyProject/*"  // Add custom path
       ]
     }
   }
   ```

2. **Symbolic link issues**:
   ```bash
   # security_utils.validate_path() resolves symlinks
   # Ensure resolved path is in whitelist
   realpath /path/to/file  # Check where symlink points
   ```

### Command Injection False Positives

**Symptom**: Legitimate commands with special characters denied

**Example**:
```bash
# Denied because of pipe character
pytest tests/ -v | grep "FAILED"
```

**Fix**:

Option 1: Add to whitelist with escaped pattern:
```json
{
  "bash": {
    "whitelist": [
      "pytest* | grep*"  // Allow pytest piped to grep
    ]
  }
}
```

Option 2: Refactor command to avoid injection patterns:
```bash
# Instead of:
pytest tests/ -v | grep "FAILED"

# Use pytest's built-in filtering:
pytest tests/ -v --tb=short -x
```

### Audit Log Not Writing

**Symptom**: `logs/tool_approval_audit.log` file missing or empty

**Diagnosis**:
```bash
# Check if logs directory exists
ls -la logs/

# Check file permissions
ls -la logs/tool_approval_audit.log
```

**Fix**:
```bash
# Create logs directory if missing
mkdir -p logs

# Fix permissions
chmod 755 logs
chmod 644 logs/tool_approval_audit.log
```

---

## For Contributors

### Extending Whitelist/Blacklist

**Step 1: Identify New Commands**

Run `/auto-implement` with `MCP_AUTO_APPROVE=false` and note denied commands:

```bash
# Check audit log for denied commands
grep "tool_call_denied" logs/tool_approval_audit.log | grep "whitelist" | tail -20
```

**Step 2: Evaluate Safety**

Ask yourself:
- ✅ Is this command read-only? (safe)
- ✅ Does it only affect project files? (safe)
- ✅ Can it cause data loss? (unsafe → blacklist)
- ✅ Can it escalate privileges? (unsafe → blacklist)
- ✅ Can it exfiltrate data? (unsafe → blacklist)

**Step 3: Add to Policy**

Edit `plugins/autonomous-dev/config/auto_approve_policy.json`:

```json
{
  "bash": {
    "whitelist": [
      // Existing commands...
      "your-new-command*"  // Add new safe command
    ],
    "blacklist": [
      // Existing commands...
      "dangerous-command*"  // Add new unsafe command
    ]
  }
}
```

**Step 4: Test**

```bash
# 1. Create test case
cat > tests/unit/lib/test_tool_validator_custom.py << 'EOF'
def test_validate_custom_command_approved():
    validator = ToolValidator()
    result = validator.validate_bash_command("your-new-command --flag")
    assert result.approved
    assert "whitelist" in result.reason.lower()

def test_validate_dangerous_command_denied():
    validator = ToolValidator()
    result = validator.validate_bash_command("dangerous-command --flag")
    assert not result.approved
    assert "blacklist" in result.reason.lower()
EOF

# 2. Run tests
pytest tests/unit/lib/test_tool_validator_custom.py -v

# 3. Test in real workflow
MCP_AUTO_APPROVE=true /auto-implement "Feature that uses your-new-command"
```

**Step 5: Document**

Add to this file's "Policy File Reference" section:

```markdown
### Custom Commands - [Your Domain]

**your-new-command**: Brief description of what it does and why it's safe
```

### Adding New Agent to Whitelist (subagent_only mode)

**Note**: In everywhere mode (`MCP_AUTO_APPROVE=true`), all agents are trusted automatically. This section only applies to `MCP_AUTO_APPROVE=subagent_only` mode.

**Step 1: Evaluate Agent Trustworthiness**

Ask yourself:
- ✅ Does this agent only read/analyze code? (safe)
- ✅ Does this agent modify code? (needs validation)
- ✅ Does this agent access sensitive data? (restricted)

**Step 2: Add to Policy**

```json
{
  "agents": {
    "trusted": [
      "researcher",
      "planner",
      "test-master",
      "implementer",
      "reviewer",
      "doc-master",
      "your-new-agent"  // Add here if trusted
    ],
    "restricted": [
      "security-auditor",
      "your-sensitive-agent"  // Add here if needs manual approval
    ]
  }
}
```

**Step 3: Test**

```bash
# Create test case (Note: unified_pre_tool_use replaces auto_approve_tool)
cat > tests/unit/hooks/test_unified_pre_tool_use_custom_agent.py << 'EOF'
from plugins.autonomous_dev.hooks.unified_pre_tool_use import on_pre_tool_use
import os

def test_custom_agent_auto_approved():
    # Set CLAUDE_AGENT_NAME to your new agent
    os.environ["CLAUDE_AGENT_NAME"] = "your-new-agent"
    os.environ["MCP_AUTO_APPROVE"] = "true"

    result = on_pre_tool_use(tool="Bash", parameters={"command": "pytest tests/"})

    # Check new Claude Code format
    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "your-new-agent" in result["hookSpecificOutput"]["permissionDecisionReason"]
EOF

pytest tests/unit/hooks/test_unified_pre_tool_use_custom_agent.py -v
```

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code 2.0                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PreToolUse Hook Lifecycle                              │ │
│  │                                                        │ │
│  │  Executes: python3 pre_tool_use.py                    │ │
│  │  Input: stdin (JSON with tool_name + tool_input)      │ │
│  │  Output: stdout (JSON with permissionDecision)        │ │
│  └─────────────────────┬──────────────────────────────────┘ │
│                        │                                     │
└────────────────────────┼─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         pre_tool_use.py (Standalone Hook Script)            │
│                                                              │
│  1. Read JSON from stdin (tool_name, tool_input)            │
│  2. Load .env file (MCP_AUTO_APPROVE, etc.)                 │
│  3. Call auto_approval_engine.should_auto_approve()         │
│  4. Format decision as hookSpecificOutput                   │
│  5. Write JSON to stdout                                    │
│  6. Exit 0 (always)                                         │
└────────┬────────────────────────────┬───────────────────────┘
         │                            │
         ▼                            ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│   ToolValidator      │    │   ToolApprovalAuditor        │
│   (tool_validator.py)│    │   (tool_approval_audit.py)   │
│                      │    │                              │
│ - load_policy()      │    │ - log_approval()             │
│ - validate_bash()    │    │ - log_denial()               │
│ - validate_path()    │    │ - get_metrics()              │
│ - detect_injection() │    │ - circuit_breaker_check()    │
└──────────────────────┘    └──────────────────────────────┘
         │                            │
         │                            │
         ▼                            ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│  auto_approve_       │    │  logs/tool_approval_         │
│  policy.json         │    │  audit.log                   │
│                      │    │                              │
│ - bash whitelist     │    │ - ISO 8601 timestamps        │
│ - bash blacklist     │    │ - JSON event format          │
│ - path whitelist     │    │ - Per-tool metrics           │
│ - path blacklist     │    │ - SIEM integration           │
│ - agent whitelist    │    │                              │
└──────────────────────┘    └──────────────────────────────┘
```

### File Structure

```
plugins/autonomous-dev/
├── hooks/
│   ├── pre_tool_use.py              (PreToolUse hook script - ACTIVE)
│   └── unified_pre_tool_use.py      (Legacy library code - DEPRECATED)
├── lib/
│   ├── auto_approval_engine.py      (Core auto-approval logic)
│   ├── tool_validator.py            (Whitelist/blacklist validation)
│   ├── tool_approval_audit.py       (Audit logging system)
│   ├── auto_approval_consent.py     (User consent management)
│   └── security_utils.py            (Path validation, CWE-22 prevention)
├── config/
│   └── auto_approve_policy.json     (Policy configuration)
└── tests/
    ├── unit/
    │   ├── lib/
    │   │   ├── test_tool_validator.py
    │   │   ├── test_tool_approval_audit.py
    │   │   └── test_user_state_manager_auto_approval.py
    │   └── hooks/
    │       └── test_auto_approve_tool.py
    ├── integration/
    │   └── test_tool_auto_approval_end_to_end.py
    └── security/
        └── test_tool_auto_approval_security.py
```

### Hook Registration

The hook must be registered in `~/.claude/settings.json` (not in plugin manifest):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /absolute/path/to/plugins/autonomous-dev/hooks/pre_tool_use.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Important**:
- Use absolute path to the script
- Claude Code only supports `"type": "command"` (shell execution)
- No Python module imports supported
- Must restart Claude Code after registration (Cmd+Q, not just `/exit`)

### API Reference

#### ToolValidator

**Location**: `plugins/autonomous-dev/lib/tool_validator.py`

**Class**: `ToolValidator`

**Constructor**:
```python
ToolValidator(policy_file: Path = DEFAULT_POLICY_FILE)
```

**Methods**:

- `validate_tool_call(tool: str, parameters: Dict[str, Any], agent_name: str) -> ValidationResult`
  - Validates complete tool call (tool + parameters + agent)
  - Returns: `ValidationResult(approved: bool, reason: str)`

- `validate_bash_command(command: str) -> ValidationResult`
  - Validates Bash command against whitelist/blacklist
  - Detects command injection patterns (CWE-78)
  - Returns: `ValidationResult(approved: bool, reason: str)`

- `validate_file_path(path: str) -> ValidationResult`
  - Validates file path against whitelist/blacklist
  - Prevents path traversal (CWE-22)
  - Returns: `ValidationResult(approved: bool, reason: str)`

**Example**:
```python
from tool_validator import ToolValidator

validator = ToolValidator()

# Validate Bash command
result = validator.validate_bash_command("pytest tests/")
if result.approved:
    print(f"Approved: {result.reason}")
else:
    print(f"Denied: {result.reason}")

# Validate file path
result = validator.validate_file_path("/tmp/output.txt")
if result.approved:
    print(f"Safe path: {result.reason}")

# Validate full tool call
result = validator.validate_tool_call(
    tool="Bash",
    parameters={"command": "git status"},
    agent_name="researcher"
)
```

#### ToolApprovalAuditor

**Location**: `plugins/autonomous-dev/lib/tool_approval_audit.py`

**Class**: `ToolApprovalAuditor`

**Constructor**:
```python
ToolApprovalAuditor(log_file: Path = DEFAULT_LOG_FILE)
```

**Methods**:

- `log_approval(tool: str, agent: str, details: Dict[str, Any])`
  - Logs approved tool call
  - Writes JSON event to audit log
  - Updates per-tool metrics

- `log_denial(tool: str, agent: str, reason: str, details: Dict[str, Any])`
  - Logs denied tool call
  - Writes JSON event to audit log
  - Updates per-tool metrics

- `get_tool_metrics() -> Dict[str, Any]`
  - Returns per-tool approval/denial counts
  - Format: `{tool_name: {"approval_count": int, "denial_count": int, "last_used": str}}`

**Example**:
```python
from tool_approval_audit import ToolApprovalAuditor

auditor = ToolApprovalAuditor()

# Log approval
auditor.log_approval(
    tool="Bash",
    agent="researcher",
    details={"command": "pytest tests/"}
)

# Log denial
auditor.log_denial(
    tool="Bash",
    agent="implementer",
    reason="Blacklist match: rm -rf*",
    details={"command": "rm -rf /tmp/data"}
)

# Get metrics
metrics = auditor.get_tool_metrics()
print(f"Bash approvals: {metrics['Bash']['approval_count']}")
print(f"Bash denials: {metrics['Bash']['denial_count']}")
```

---

## Changelog

### v3.39.0 (2025-12-08)

**Simplified**:
- Standalone `pre_tool_use.py` script replaces `unified_pre_tool_use.py` (library format)
- Hook registration now uses standard Claude Code shell command format
- Reads JSON from stdin, outputs JSON to stdout, exits 0
- Registered in `~/.claude/settings.json` (not plugin manifest)
- All existing validation logic preserved (just simpler interface)

**Rationale**:
- Claude Code only supports `"type": "command"` (shell execution), not Python module imports
- Previous approach (`"type": "python"`) was never supported by Claude Code
- Simplified architecture = fewer points of failure

### v3.38.0 (2025-12-08)

**Updated**:
- Unified PreToolUse hook (`unified_pre_tool_use.py`) replaced `auto_approve_tool.py`
- Hook return format updated to Claude Code official spec (hookSpecificOutput format)
- Eliminated hook collision between auto_approve_tool and mcp_security_enforcer
- Core auto-approval logic extracted to `auto_approval_engine.py` library

### v3.21.0 (2025-11-15)

**Added**:
- Initial implementation of MCP auto-approval feature
- PreToolUse hook handler (`auto_approve_tool.py`)
- Whitelist/blacklist validation engine (`tool_validator.py`)
- Audit logging system (`tool_approval_audit.py`)
- User consent management (`auto_approval_consent.py`)
- Default policy configuration (`auto_approve_policy.json`)

**Security**:
- 6 layers of defense-in-depth validation
- Path traversal prevention (CWE-22)
- Command injection prevention (CWE-78)
- Audit logging for compliance
- Circuit breaker protection

---

## References

- **GitHub Issue**: #73 (MCP Auto-Approval for Subagent Tool Calls)
- **CHANGELOG.md**: v3.21.0 release notes
- **CLAUDE.md**: MCP Auto-Approval Control section
- **plugins/autonomous-dev/README.md**: MCP Auto-Approval feature section
- **CWE-22**: Path Traversal - https://cwe.mitre.org/data/definitions/22.html
- **CWE-78**: OS Command Injection - https://cwe.mitre.org/data/definitions/78.html
- **CWE-117**: Log Injection - https://cwe.mitre.org/data/definitions/117.html

---

**Last Updated**: 2025-11-15
**Version**: v3.21.0
**Maintainer**: autonomous-dev plugin team
