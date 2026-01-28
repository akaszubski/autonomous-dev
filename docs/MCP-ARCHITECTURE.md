# MCP Architecture - Autonomous Development

**Version**: v3.37.0
**Issue**: #95 (MCP Security Implementation)
**Last Updated**: 2025-12-07

---

## Overview

This document describes the Model Context Protocol (MCP) architecture for autonomous-dev, providing secure access to external tools (bash, git, github, python, web search) through permission-based validation.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude Desktop / Claude Code                │
│                    (MCP Client - User Interface)                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ MCP Protocol (JSON-RPC over stdio)
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                  MCP Security Enforcer Hook                     │
│              (PreToolUse Lifecycle Validation)                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  mcp_permission_validator.py                             │  │
│  │  - Whitelist/denylist checking                           │  │
│  │  - Path traversal prevention (CWE-22)                    │  │
│  │  - Command injection prevention (CWE-78)                 │  │
│  │  - SSRF prevention                                       │  │
│  │  - Audit logging                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Validated requests only
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────▼────────┐ ┌───────▼────────┐ ┌───────▼────────┐
│  Filesystem MCP │ │   Git MCP      │ │  GitHub MCP    │
│   (Official)    │ │  (Official)    │ │  (Official)    │
│                 │ │                │ │                │
│ - read_file     │ │ - git_status   │ │ - create_issue │
│ - write_file    │ │ - git_diff     │ │ - list_repos   │
│ - list_dir      │ │ - git_log      │ │ - create_pr    │
│ - search_files  │ │ - git_commit   │ │ - review_pr    │
└─────────────────┘ └────────────────┘ └────────────────┘

┌─────────────────┐ ┌────────────────┐ ┌────────────────┐
│  Python REPL    │ │  Bash/Shell    │ │  Brave Search  │
│  MCP (Community)│ │  MCP (Comm.)   │ │  (Official)    │
│                 │ │                │ │                │
│ - execute_code  │ │ - run_command  │ │ - web_search   │
│ - get_globals   │ │ - run_script   │ │ - local_search │
│ - reset_session │ │ - get_cwd      │ │ - news_search  │
└─────────────────┘ └────────────────┘ └────────────────┘
```

---

## Component Details

### 1. MCP Servers (Tools Layer)

#### Official Servers (Maintained by Anthropic/GitHub/Brave)

| Server | Source | Purpose | Installation |
|--------|--------|---------|--------------|
| **Filesystem** | `@modelcontextprotocol/server-filesystem` | Secure file operations | `npx -y @modelcontextprotocol/server-filesystem` |
| **Git** | `@modelcontextprotocol/server-git` | Git repository operations | `npx -y @modelcontextprotocol/server-git` |
| **GitHub** | `ghcr.io/github/github-mcp-server` | GitHub API integration | Docker or local binary |
| **Brave Search** | `@brave/brave-search-mcp-server` | Web search capabilities | `npx -y @brave/brave-search-mcp-server` |

#### Community Servers (Vetted & Recommended)

| Server | Source | Purpose | Installation |
|--------|--------|---------|--------------|
| **Python REPL** | `hdresearch/mcp-python` | Python code execution | `uv run mcp_python` |
| **Bash/Shell** | `patrickomatik/mcp-bash` | Shell command execution | `uv run mcp-bash` |

### 2. Security Layer (Permission Validation)

**File**: `plugins/autonomous-dev/lib/mcp_permission_validator.py`

**Features**:
- **Whitelist validation**: Only allowed paths/commands/domains pass
- **Denylist blocking**: Explicitly blocked operations rejected
- **Path traversal prevention** (CWE-22): Blocks `../`, `/etc/passwd`, etc.
- **Symlink protection** (CWE-59): Resolves and validates symlinks
- **Command injection prevention** (CWE-78): Sanitizes shell commands
- **SSRF prevention**: Blocks local/private network requests
- **Audit logging**: All operations logged to `logs/mcp_audit.log`

**Validation Flow**:
```python
# 1. Load security policy
policy = load_policy(".mcp/security_policy.json")

# 2. Validate operation
result = validator.validate_filesystem_read(
    path="src/main.py",
    policy=policy
)

# 3. Check result
if result.allowed:
    # ✅ Allow operation
    execute_mcp_server_call()
else:
    # ❌ Block operation
    log_security_violation(result.reason)
    raise PermissionDenied(result.reason)
```

### 3. Security Profiles

**File**: `plugins/autonomous-dev/lib/mcp_profile_manager.py`

Three pre-configured security profiles:

#### Development Profile (Permissive)
```json
{
  "filesystem": {
    "allowed_paths": ["**/*"],
    "denied_paths": [".env", ".git", ".ssh", "**/.env"]
  },
  "shell": {
    "allowed_commands": ["git", "pytest", "python", "npm", "make"],
    "denied_patterns": ["rm -rf", "sudo", "chmod 777"]
  }
}
```

#### Testing Profile (Moderate)
```json
{
  "filesystem": {
    "allowed_paths": ["src/**", "tests/**", "docs/**"],
    "denied_paths": [".env", ".git", ".ssh"]
  },
  "shell": {
    "allowed_commands": ["git status", "git diff", "pytest"],
    "denied_patterns": ["rm", "sudo", "chmod", "curl", "wget"]
  }
}
```

#### Production Profile (Strict)
```json
{
  "filesystem": {
    "allowed_paths": ["docs/**/*.md"],
    "denied_paths": ["**/*"]
  },
  "shell": {
    "allowed_commands": [],
    "denied_patterns": ["**/*"]
  }
}
```

### 4. Hook Integration

**File**: `plugins/autonomous-dev/hooks/unified_pre_tool.py` (Layer 2: MCP Security Validator)

**Legacy**: `mcp_security_enforcer.py` (Archived 2026-01-09, see `hooks/archived/README.md` - Issue #211)

**Lifecycle**: `PreToolUse` (intercepts all MCP tool calls BEFORE execution)

**Logic**:
```python
def on_pre_tool_use(tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    PreToolUse hook for MCP security enforcement.

    Called before EVERY MCP tool execution.

    Returns:
        {"approved": True} - Allow operation
        {"approved": False, "reason": "..."} - Block operation
    """
    # Step 1: Load security policy
    policy = load_policy(".mcp/security_policy.json")

    # Step 2: Determine MCP server type
    server_type = detect_mcp_server(tool, parameters)

    # Step 3: Validate based on server type
    if server_type == "filesystem":
        result = validate_filesystem_operation(parameters, policy)
    elif server_type == "shell":
        result = validate_shell_operation(parameters, policy)
    elif server_type == "web":
        result = validate_web_operation(parameters, policy)
    # ... etc

    # Step 4: Log decision
    audit_log(tool, parameters, result)

    # Step 5: Return approval decision
    return {
        "approved": result.allowed,
        "reason": result.reason if not result.allowed else None
    }
```

---

## Directory Structure

```
.mcp/
├── config.json                    # MCP server configuration
├── security_policy.json           # Permission policy (user-customizable)
├── security_policy.development.json   # Development profile template
├── security_policy.testing.json       # Testing profile template
├── security_policy.production.json    # Production profile template
└── README.md                      # Setup instructions

plugins/autonomous-dev/
├── lib/
│   ├── mcp_permission_validator.py    # Core validation logic
│   ├── mcp_profile_manager.py         # Profile initialization
│   └── mcp_server_detector.py         # Server type detection (NEW)
├── hooks/
│   └── mcp_security_enforcer.py       # PreToolUse hook
└── config/
    └── mcp_default_policy.json        # Factory default policy

logs/
└── mcp_audit.log                  # Security audit trail
```

---

## Security Features

### 1. Path Traversal Prevention (CWE-22)

**Threat**: Malicious path like `../../etc/passwd`

**Defense**:
```python
def validate_path(path: str, allowed_base: Path) -> ValidationResult:
    # Resolve to absolute path
    abs_path = Path(path).resolve()

    # Check if within allowed base
    if not abs_path.is_relative_to(allowed_base):
        return ValidationResult(
            allowed=False,
            reason=f"Path traversal detected: {path} outside {allowed_base}"
        )

    # Check denylist
    if matches_denylist(abs_path, policy.denied_paths):
        return ValidationResult(
            allowed=False,
            reason=f"Path denied by policy: {path}"
        )

    return ValidationResult(allowed=True)
```

### 2. Command Injection Prevention (CWE-78)

**Threat**: Malicious command like `git status; rm -rf /`

**Defense**:
```python
def validate_shell_command(command: str, policy: Policy) -> ValidationResult:
    # Check for shell metacharacters
    dangerous_chars = [';', '|', '&', '`', '$', '(', ')']
    if any(char in command for char in dangerous_chars):
        return ValidationResult(
            allowed=False,
            reason=f"Shell metacharacters detected: {command}"
        )

    # Whitelist validation
    command_parts = command.split()
    base_command = command_parts[0]

    if base_command not in policy.allowed_commands:
        return ValidationResult(
            allowed=False,
            reason=f"Command not whitelisted: {base_command}"
        )

    return ValidationResult(allowed=True)
```

### 3. SSRF Prevention

**Threat**: Request to local network like `http://192.168.1.1/admin`

**Defense**:
```python
def validate_web_request(url: str, policy: Policy) -> ValidationResult:
    parsed = urllib.parse.urlparse(url)

    # Block local/private IPs
    private_ranges = ['127.', '192.168.', '10.', '172.16.']
    if any(parsed.hostname.startswith(prefix) for prefix in private_ranges):
        return ValidationResult(
            allowed=False,
            reason=f"Private IP address blocked: {url}"
        )

    # Whitelist domains
    if policy.allowed_domains and parsed.hostname not in policy.allowed_domains:
        return ValidationResult(
            allowed=False,
            reason=f"Domain not whitelisted: {parsed.hostname}"
        )

    return ValidationResult(allowed=True)
```

### 4. Audit Logging

**File**: `logs/mcp_audit.log`

**Format** (JSON Lines):
```json
{"timestamp": "2025-12-07T10:00:00Z", "server": "filesystem", "operation": "read_file", "path": "src/main.py", "allowed": true, "reason": null}
{"timestamp": "2025-12-07T10:00:05Z", "server": "shell", "operation": "run_command", "command": "rm -rf /", "allowed": false, "reason": "Denied by policy: destructive command"}
{"timestamp": "2025-12-07T10:00:10Z", "server": "web", "operation": "fetch", "url": "http://192.168.1.1", "allowed": false, "reason": "SSRF: Private IP blocked"}
```

---

## Configuration Examples

### Minimal Configuration (Development)

**.mcp/config.json**:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${PROJECT_ROOT}"]
    },
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git", "--repository", "${PROJECT_ROOT}"]
    },
    "github": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/github/github-mcp-server"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

**.mcp/security_policy.json**:
```json
{
  "profile": "development",
  "filesystem": {
    "allowed_paths": [
      "src/**/*",
      "tests/**/*",
      "docs/**/*",
      "plugins/**/*"
    ],
    "denied_paths": [
      "**/.env",
      "**/.git/**",
      "**/.ssh/**",
      "**/secrets/**"
    ]
  },
  "shell": {
    "allowed_commands": [
      "git",
      "pytest",
      "python",
      "python3",
      "npm",
      "make",
      "grep",
      "find"
    ],
    "denied_patterns": [
      "rm -rf",
      "sudo",
      "chmod 777",
      "curl *bash",
      "wget *bash"
    ]
  },
  "web": {
    "allowed_domains": [
      "github.com",
      "api.github.com",
      "search.brave.com",
      "pypi.org",
      "npmjs.com"
    ],
    "blocked_ips": [
      "127.0.0.1",
      "192.168.*",
      "10.*",
      "172.16.*"
    ]
  }
}
```

### Full Configuration (All Servers)

**.mcp/config.json**:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "${PROJECT_ROOT}"
      ]
    },
    "git": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-git",
        "--repository",
        "${PROJECT_ROOT}"
      ]
    },
    "github": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "-e",
        "GITHUB_TOOLSETS=repos,issues,pull_requests,actions",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_TOOLSETS": "repos,issues,pull_requests,actions"
      }
    },
    "python-repl": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp-python",
        "mcp_python"
      ]
    },
    "bash": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp-bash",
        "mcp-bash"
      ]
    },
    "brave-search": {
      "command": "npx",
      "args": [
        "-y",
        "@brave/brave-search-mcp-server"
      ],
      "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
      }
    }
  }
}
```

---

## Setup Instructions

### 1. Initialize Security Policy

```bash
# Choose a profile (development, testing, production)
python plugins/autonomous-dev/lib/mcp_profile_manager.py --init development

# Or create custom policy
cp .mcp/security_policy.development.json .mcp/security_policy.json
vim .mcp/security_policy.json  # Customize
```

### 2. Configure Environment Variables

**Create `.env` file** (already gitignored):
```bash
# GitHub Personal Access Token (required for github MCP server)
GITHUB_TOKEN=ghp_your_token_here

# Brave Search API Key (required for brave-search MCP server)
BRAVE_API_KEY=your_api_key_here
```

### 3. Configure MCP Servers

**Create `.mcp/config.json`**:
```bash
# Use the minimal config above, or customize
cp docs/MCP-ARCHITECTURE.md .mcp/config.json  # Extract JSON
```

### 4. Test Configuration

```bash
# Validate security policy
python plugins/autonomous-dev/lib/mcp_permission_validator.py --validate .mcp/security_policy.json

# Test filesystem operation
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-read "src/main.py"

# Test shell operation
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-shell "git status"

# Test web operation
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-web "https://github.com"
```

### 5. Enable Hook (Optional)

The mcp_security_enforcer.py hook is automatically registered if you have `.mcp/security_policy.json`.

To manually enable:
```bash
# Add to .claude/settings.local.json
{
  "hooks": {
    "PreToolUse": {
      "description": "MCP Security Enforcement (unified_pre_tool.py Layer 2)",
      "command": "python plugins/autonomous-dev/hooks/unified_pre_tool.py"
    }
  }
}
```

**Note**: The legacy `mcp_security_enforcer.py` hook has been consolidated into `unified_pre_tool.py` as of Issue #211 (2026-01-09). See `hooks/archived/README.md` for migration details.

---

## Usage

### From Claude Desktop

1. Open Claude Desktop
2. MCP servers auto-load from `.mcp/config.json`
3. Security policy enforces permissions automatically
4. Check audit log: `tail -f logs/mcp_audit.log`

### From Claude Code

1. MCP servers available via built-in tools
2. Security hook intercepts operations
3. Violations blocked with clear error messages

### From Autonomous-Dev Agents

Agents can now use MCP servers without prompts:

```bash
/implement "add rate limiting feature"

# Behind the scenes:
# 1. researcher agent → filesystem MCP (read existing code)
# 2. planner agent → web search MCP (find best practices)
# 3. test-master agent → filesystem MCP (write tests)
# 4. implementer agent → filesystem MCP (write code)
# 5. reviewer agent → filesystem MCP (read code)
# 6. All operations validated by security policy
# 7. All operations logged to audit.log
```

---

## Troubleshooting

### "Permission denied: path outside allowed base"

**Cause**: Path traversal attempt or path not whitelisted

**Fix**: Add path to `allowed_paths` in `.mcp/security_policy.json`

### "Command not whitelisted: curl"

**Cause**: Shell command not in allowed list

**Fix**: Add command to `allowed_commands` in security policy

### "SSRF: Private IP blocked"

**Cause**: Web request to local/private IP

**Fix**: This is intentional security. Don't allow private IPs in production.

### "MCP server not found: filesystem"

**Cause**: MCP server not installed or not in PATH

**Fix**: Install server: `npx -y @modelcontextprotocol/server-filesystem`

---

## Best Practices

### 1. Principle of Least Privilege

Start with strict policy, relax as needed:
```bash
# Start with testing profile
python plugins/autonomous-dev/lib/mcp_profile_manager.py --init testing

# Add permissions incrementally
vim .mcp/security_policy.json
```

### 2. Regular Audit Review

```bash
# Check recent operations
tail -100 logs/mcp_audit.log | grep "allowed\":false"

# Find blocked operations
grep "allowed\":false" logs/mcp_audit.log | jq '.reason' | sort | uniq -c
```

### 3. Token Security

```bash
# Store in .env (gitignored)
echo "GITHUB_TOKEN=ghp_..." >> .env
echo "BRAVE_API_KEY=..." >> .env

# Never commit tokens
git status  # Should NOT show .env
```

### 4. Profile Per Environment

```bash
# Development: Permissive
ln -s security_policy.development.json .mcp/security_policy.json

# Production: Strict
ln -s security_policy.production.json .mcp/security_policy.json
```

---

## Future Enhancements

### Phase 2 (v3.38.0)
- [ ] Rate limiting per MCP server
- [ ] Token usage tracking
- [ ] Automated security policy learning

### Phase 3 (v3.39.0)
- [ ] WebSocket MCP server support
- [ ] Remote MCP server proxying
- [ ] Multi-tenant policy isolation

---

## References

- **MCP Specification**: https://modelcontextprotocol.io/
- **Official Servers**: https://github.com/modelcontextprotocol/servers
- **GitHub MCP Server**: https://github.com/github/github-mcp-server
- **Brave Search MCP**: https://github.com/brave/brave-search-mcp-server
- **Security Policy Schema**: `plugins/autonomous-dev/config/mcp_policy_schema.json`

---

**Last Updated**: 2025-12-07
**Maintained By**: autonomous-dev contributors
**Issue**: #95 (MCP Security Implementation)
