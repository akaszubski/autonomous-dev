# MCP Server Security - Permission Whitelist System

**Last Updated**: 2025-12-07
**Version**: v3.37.0
**Issue**: #95 (MCP Server Security)
**Agent**: implementer

---

## DEPRECATION NOTICE (Issue #211)

**Status**: The standalone `mcp_security_enforcer.py` hook has been **archived** as of 2026-01-09.

**Reason**: Consolidated into unified security architecture for better maintainability.

**Migration**:
- All MCP security validation now provided by `unified_pre_tool.py` (Layer 2: MCP Security Validator)
- Enable with `PRE_TOOL_MCP_SECURITY=true` (enabled by default)
- No configuration changes required
- Same security guarantees and functionality

**What Changed**:
- Old: Standalone `mcp_security_enforcer.py` hook
- New: Layer 2 of unified `unified_pre_tool.py` hook (4-layer security architecture)

**Benefits of Consolidation**:
- Single entry point for all pre-tool validation
- Consistent validation order (sandbox → MCP security → agent auth → batch approval)
- Better defense-in-depth with explicit layers
- Easier to maintain and extend

**See**: `plugins/autonomous-dev/hooks/archived/README.md` for complete deprecation documentation and functionality preservation details.

**For Users**: No action required. MCP security validation continues to work as documented below.

---

## Overview

The MCP (Model Context Protocol) server security system provides permission whitelisting to prevent common security vulnerabilities while enabling safe automation.

**Implementation**: Layer 2 of the unified `unified_pre_tool.py` hook (previously standalone `mcp_security_enforcer.py`).

**What It Protects Against**:
- **CWE-22**: Path traversal attacks (../../.env)
- **CWE-59**: Improper link resolution before file access (symlink attacks)
- **CWE-78**: OS command injection (shell metacharacters)
- **SSRF**: Server-side request forgery (localhost/metadata service access)
- **Secret exposure**: Environment variable access to API keys, tokens
- **Unauthorized operations**: Reading/writing files outside project scope

**Security Model**: Whitelist-based (allowlist + denylist patterns with glob matching)

**Key Principle**: Always deny by default, allow only explicitly permitted operations

---

## Quick Start

### 1. Initialize Security Policy

Create `.mcp/security_policy.json` with a pre-configured profile:

```bash
# Automatic initialization (recommended)
python plugins/autonomous-dev/lib/mcp_profile_manager.py --init development
```

Or manually create the file with a development profile:

```json
{
  "version": "1.0",
  "profile": "development",
  "filesystem": {
    "read": ["src/**", "tests/**", "docs/**", "*.md", "*.json", "*.yaml", "!**/.env", "!**/.git/**"],
    "write": ["src/**", "tests/**", "docs/**", "!**/.env", "!**/.git/**"]
  },
  "shell": {
    "allowed_commands": ["pytest", "git", "python", "python3", "pip", "npm", "make"],
    "denied_patterns": ["rm -rf /", "dd if=", "mkfs"]
  },
  "network": {
    "allowed_domains": ["*"],
    "denied_ips": ["127.0.0.1", "0.0.0.0", "169.254.169.254"]
  },
  "environment": {
    "allowed_vars": ["PATH", "HOME", "USER", "SHELL", "LANG", "PWD", "TERM"],
    "denied_patterns": ["*_KEY", "*_TOKEN", "*_SECRET", "AWS_*", "GITHUB_TOKEN"]
  }
}
```

### 2. Validate Security Policy

```bash
# Validate policy structure and permissions
python plugins/autonomous-dev/lib/mcp_permission_validator.py --validate .mcp/security_policy.json
```

### 3. Test Operations

```bash
# Test filesystem read permission
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-read "src/main.py"

# Test shell command permission
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-shell "pytest tests/"

# Test environment variable access
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-env "PATH"
```

---

## MCP Server Configuration

### Official MCP Servers

The system now integrates with official MCP servers for each capability:

| Server | Source | Purpose | Documentation |
|--------|--------|---------|---------------|
| **filesystem** | `@modelcontextprotocol/server-filesystem` | Secure file operations | [Official](https://github.com/modelcontextprotocol/servers) |
| **git** | `@modelcontextprotocol/server-git` | Git repository operations | [Official](https://github.com/modelcontextprotocol/servers) |
| **github** | `ghcr.io/github/github-mcp-server` | GitHub API integration | [Official](https://github.com/github/github-mcp-server) |
| **brave-search** | `@brave/brave-search-mcp-server` | Web search | [Official](https://github.com/brave/brave-search-mcp-server) |
| **python-repl** | `hdresearch/mcp-python` | Python code execution | [Community](https://github.com/hdresearch/mcp-python) |
| **bash** | `patrickomatik/mcp-bash` | Shell commands | [Community](https://github.com/patrickomatik/mcp-bash) |

### MCP Configuration File

**Location**: `.mcp/config.json`

**Format**: Standard MCP server configuration (JSON)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/akaszubski/Documents/GitHub/autonomous-dev"
      ]
    },
    "git": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-git",
        "--repository",
        "/Users/akaszubski/Documents/GitHub/autonomous-dev"
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

### Environment Variables

**Create `.env` file** (gitignored):
```bash
# GitHub Personal Access Token (required for github MCP server)
GITHUB_TOKEN=ghp_your_token_here

# Brave Search API Key (required for brave-search MCP server)
BRAVE_API_KEY=your_api_key_here
```

**Security**: The `.env` file is automatically blocked by the security policy and should NEVER be committed to git.

### Server Type Detection

The system automatically detects which MCP server is being called based on tool names and parameters.

**Detection Library**: `plugins/autonomous-dev/lib/mcp_server_detector.py`

**Example**:
```python
from autonomous_dev.lib.mcp_server_detector import detect_mcp_server

# Filesystem detection
result = detect_mcp_server("read_file", {"path": "src/main.py"})
# Returns: MCPServerType.FILESYSTEM

# Bash detection
result = detect_mcp_server("run_command", {"command": "git status"})
# Returns: MCPServerType.BASH

# GitHub detection
result = detect_mcp_server("create_issue", {"owner": "user", "repo": "proj", "title": "Bug"})
# Returns: MCPServerType.GITHUB
```

---

## Configuration

### Security Policy Schema

The security policy JSON file defines what operations are permitted for MCP tools.

**Location**: `.mcp/security_policy.json`

**Root Schema**:

```json
{
  "version": "1.0",
  "profile": "development|testing|production",
  "filesystem": { ... },
  "shell": { ... },
  "network": { ... },
  "environment": { ... }
}
```

### Filesystem Permissions

**Purpose**: Control read/write access to files and directories

**Schema**:

```json
{
  "filesystem": {
    "read": [
      "src/**",           // Allow all files in src/
      "tests/**",         // Allow all test files
      "docs/**",          // Allow documentation
      "*.md",             // Allow markdown files in project root
      "!**/.env",         // Deny .env files
      "!**/.git/**",      // Deny .git directory
      "!**/*.key",        // Deny key files
      "!**/*.pem"         // Deny PEM certificates
    ],
    "write": [
      "src/**",           // Allow writing to src/
      "tests/**",         // Allow writing to tests/
      "docs/**",          // Allow writing to docs/
      "!**/.env",         // Never write .env
      "!**/.git/**"       // Never write to .git
    ]
  }
}
```

**Pattern Syntax** (glob matching):
- `**` - Match any number of directories (recursive wildcard)
- `*` - Match any characters except `/` (single directory level)
- `?` - Match single character
- `!` - Negate pattern (deny)
- Patterns are matched in order (first match wins)

**Examples**:
- `src/**` - All files under src/ at any depth
- `*.py` - Python files in project root only
- `tests/unit/*` - Direct children of tests/unit/
- `!**/.env` - Deny .env files anywhere
- `docs/**/*.md` - Markdown files under docs/

**Sensitive File Detection**:
- Automatically blocks access to: `.env`, `secrets.json`, `credentials.json`, API key files
- Blocks access to: `.ssh`, `.git`, certificate/key files (*.pem, *.key, *.crt)
- Works even if not in deny list (defense in depth)

### Shell Permissions

**Purpose**: Control which commands can be executed

**Schema**:

```json
{
  "shell": {
    "allowed_commands": [
      "pytest",       // Exact match - only pytest can run
      "git",          // Only git commands
      "python",       // Python interpreter
      "python3",      // Python 3 interpreter
      "pip",          // Package installer
      "npm",          // Node package manager
      "make"          // Build automation
    ],
    "denied_patterns": [
      "rm -rf /",     // Block recursive deletion of root
      "dd if=",       // Block disk writer
      "mkfs",         // Block filesystem creation
      "> /dev/",      // Block device redirection
      "curl * | sh",  // Block curl pipe to shell
      "wget * | sh"   // Block wget pipe to shell
    ]
  }
}
```

**Matching**:
- `allowed_commands`: Command must start with one of these values
- `denied_patterns`: Command matching pattern is always blocked
- All shell commands checked for injection characters: `;`, `|`, `&`, `$(`, `` ` ``

**Injection Prevention**:
- Detects and blocks shell metacharacters
- Detects command chaining (`;`, `&&`, `||`)
- Detects pipe operators (`|`)
- Detects command substitution (`$()`, backticks)

### Network Permissions

**Purpose**: Prevent SSRF and unauthorized network access

**Schema**:

```json
{
  "network": {
    "allowed_domains": [
      "api.github.com",      // Allow GitHub API
      "*.example.com",       // Allow subdomains
      "*"                    // Allow all (development only)
    ],
    "denied_ips": [
      "127.0.0.1",           // Deny localhost
      "0.0.0.0",             // Deny all interfaces
      "169.254.169.254"      // Deny AWS metadata service
    ]
  }
}
```

**Private IP Detection** (automatically denied):
- `10.0.0.0/8` - Private network
- `172.16.0.0/12` - Private network
- `192.168.0.0/16` - Private network
- `127.0.0.1` - Localhost
- `169.254.169.254` - AWS metadata service

**Matching**:
- Domain wildcards: `*` matches any subdomain level
- IPv4 CIDR blocks: `10.0.0.0/8` matches all IPs in range
- First matching rule determines result (allow takes precedence)

### Environment Variable Permissions

**Purpose**: Prevent access to sensitive environment variables

**Schema**:

```json
{
  "environment": {
    "allowed_vars": [
      "PATH",         // System path
      "HOME",         // Home directory
      "USER",         // Current user
      "SHELL",        // Shell executable
      "LANG",         // Language settings
      "PWD",          // Current directory
      "TERM"          // Terminal type
    ],
    "denied_patterns": [
      "*_KEY",        // Any variable ending with _KEY
      "*_TOKEN",      // Any variable ending with _TOKEN
      "*_SECRET",     // Any variable ending with _SECRET
      "AWS_*",        // All AWS variables
      "GITHUB_TOKEN", // Specific token
      "DATABASE_*"    // All database variables
    ]
  }
}
```

**Matching**:
- `allowed_vars`: Exact variable names
- `denied_patterns`: Glob patterns (block secrets by name)

---

## Security Profiles

The system includes three pre-configured profiles for different environments.

### Development Profile (Most Permissive)

**Use Case**: Local development environment

**Permissions**:
- **Read**: src/, tests/, docs/, config files
- **Write**: src/, tests/, docs/
- **Shell**: Common dev commands (pytest, git, python, npm, pip, make)
- **Network**: All domains (except metadata service)
- **Environment**: Common vars only (block secrets)

**Command**:
```bash
python plugins/autonomous-dev/lib/mcp_profile_manager.py --profile development
```

**Typical Use**:
```json
{
  "version": "1.0",
  "profile": "development",
  "filesystem": {
    "read": ["src/**", "tests/**", "docs/**", "*.md", "*.json", "!**/.env", "!**/.git/**"],
    "write": ["src/**", "tests/**", "docs/**"]
  },
  "shell": {
    "allowed_commands": ["pytest", "git", "python", "python3", "pip", "npm", "make"],
    "denied_patterns": ["rm -rf /", "dd if=", "mkfs"]
  },
  "network": {
    "allowed_domains": ["*"],
    "denied_ips": ["127.0.0.1", "0.0.0.0", "169.254.169.254"]
  },
  "environment": {
    "allowed_vars": ["PATH", "HOME", "USER", "SHELL", "LANG", "PWD", "TERM"],
    "denied_patterns": ["*_KEY", "*_TOKEN", "*_SECRET", "AWS_*", "GITHUB_TOKEN"]
  }
}
```

### Testing Profile (Moderate Restrictions)

**Use Case**: CI/CD and test environments

**Permissions**:
- **Read**: src/, tests/, config files (no docs)
- **Write**: tests/ only (read-only source)
- **Shell**: Test commands only (pytest)
- **Network**: Specific test APIs only
- **Environment**: Test vars only

**Command**:
```bash
python plugins/autonomous-dev/lib/mcp_profile_manager.py --profile testing
```

### Production Profile (Strictest)

**Use Case**: Production automation and monitoring

**Permissions**:
- **Read**: Specific paths only (no source code)
- **Write**: Restricted to logs/ and data/
- **Shell**: Safe read-only commands only
- **Network**: Specific production APIs only
- **Environment**: Production config only (no secrets)

**Command**:
```bash
python plugins/autonomous-dev/lib/mcp_profile_manager.py --profile production
```

### Custom Profiles

Customize profiles for your specific needs:

```python
from autonomous_dev.lib.mcp_profile_manager import MCPProfileManager, ProfileType, customize_profile

manager = MCPProfileManager()

# Start with development profile
profile = manager.create_profile(ProfileType.DEVELOPMENT)

# Customize for your project
custom = customize_profile(profile, {
    "filesystem": {
        "read": [
            "src/**",
            "config/**",
            "!**/.env.local"
        ]
    },
    "shell": {
        "allowed_commands": ["pytest", "git", "poetry"]
    }
})

# Save to file
manager.save_profile(custom, ".mcp/security_policy.json")
```

---

## Permission Validation API

Use the `MCPPermissionValidator` class to validate operations programmatically.

### Imports

```python
from autonomous_dev.lib.mcp_permission_validator import (
    MCPPermissionValidator,
    ValidationResult
)
```

### Validate Filesystem Read

```python
validator = MCPPermissionValidator(policy_path=".mcp/security_policy.json")

result = validator.validate_fs_read("src/main.py")
if result.approved:
    # Operation is permitted
    with open("src/main.py") as f:
        content = f.read()
else:
    # Operation denied
    print(f"Access denied: {result.reason}")
```

**Return Type**: `ValidationResult`
- `approved: bool` - Whether operation is allowed
- `reason: Optional[str]` - Reason for denial (None if approved)

### Validate Filesystem Write

```python
result = validator.validate_fs_write("src/feature.py")
if result.approved:
    with open("src/feature.py", "w") as f:
        f.write(code)
else:
    print(f"Write denied: {result.reason}")
```

### Validate Shell Command

```python
result = validator.validate_shell_execute("pytest tests/")
if result.approved:
    # Safe to execute
    os.system("pytest tests/")
else:
    print(f"Command denied: {result.reason}")
```

**Checks**:
- Command starts with allowed command
- No shell injection patterns detected
- No denied patterns matched

### Validate Network Access

```python
result = validator.validate_network_access("https://api.github.com/repos/...")
if result.approved:
    # Safe to make HTTP request
    response = requests.get(url)
else:
    print(f"Network access denied: {result.reason}")
```

**Checks**:
- Domain is in allowed_domains
- IP is not in denied_ips
- Not a private/metadata service IP

### Validate Environment Variable

```python
result = validator.validate_env_access("DATABASE_URL")
if result.approved:
    url = os.getenv("DATABASE_URL")
else:
    print(f"Env var access denied: {result.reason}")
```

**Checks**:
- Variable is in allowed_vars
- Variable doesn't match denied_patterns

---

## Security Patterns

Best practices for MCP security.

### Defense in Depth

Apply multiple validation layers:

1. **Glob pattern matching** (allowlist/denylist)
2. **Sensitive file detection** (hardcoded blocks)
3. **Path traversal detection** (.., symlinks)
4. **Injection pattern detection** (shell metacharacters)
5. **Audit logging** (all operations recorded)

Example:
```python
# Path must:
# 1. Match filesystem.read pattern
# 2. Not be in sensitive file list (.env, .ssh, etc.)
# 3. Not contain .. or symlink attacks
# 4. Resolve to within project root
```

### Whitelist + Denylist Combination

Use allowlist for broad permissions, denylist for exceptions:

```json
{
  "filesystem": {
    "read": [
      "**/*.py",        // Broad: allow all Python files
      "!**/.env",       // Narrow: except .env
      "!**/secrets/**"  // Narrow: except secrets directory
    ]
  }
}
```

### Conservative Defaults

Start restrictive, add permissions as needed:

**Development**:
```json
{
  "read": ["src/**", "tests/**"],    // Only necessary directories
  "write": ["src/**", "tests/**"],   // No docs, config, build artifacts
  "shell": ["pytest", "git"],        // Only essential commands
  "environment": ["PATH", "HOME"]    // Only safe variables
}
```

### Principle of Least Privilege

Grant minimum permissions required for the operation:

**For CI/CD**:
- Only read source files
- Write to tests/ and build/ only
- Execute test runner only
- No network access needed
- No secret environment variables

**For Local Development**:
- Read/write src/, tests/, docs/
- Execute dev tools (pytest, git, python, npm)
- Allow network for development APIs
- Allow safe environment variables

---

## Troubleshooting

### Permission Denied Errors

**Symptom**: "Operation denied: Path not in allowed patterns"

**Causes**:
1. File is not in allowlist
2. File matches a denylist pattern
3. File is in sensitive directories (.env, .ssh, .git)
4. File path contains `..` or symlinks

**Solutions**:

```bash
# Check what permissions are currently granted
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-read "path/to/file"

# Add file to allowlist in security_policy.json
# Before:
#   "read": ["src/**", "tests/**"]
# After:
#   "read": ["src/**", "tests/**", "config/**"]

# Then validate policy
python plugins/autonomous-dev/lib/mcp_permission_validator.py --validate .mcp/security_policy.json
```

### Shell Command Blocked

**Symptom**: "Command denied: Contains injection pattern"

**Causes**:
1. Command contains metacharacters (`;`, `|`, `&`, etc.)
2. Command uses command substitution (`$(...)`, backticks)
3. Command not in allowed_commands list
4. Command matches a denied pattern

**Solutions**:

```bash
# Test command permission
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-shell "pytest tests/"

# If blocked by injection detection, break into separate commands:
# Before:
#   "pytest tests/ && git add . && git commit -m 'tests'"
# After:
#   "pytest tests/"
#   "git add ."
#   "git commit -m 'tests'"

# If command not in allowed list, add it:
#   "allowed_commands": ["pytest", "git", "python", "my-custom-tool"]
```

### Network Access Blocked

**Symptom**: "Network access denied: Domain not in allowed_domains"

**Solutions**:

```json
{
  "network": {
    "allowed_domains": [
      "api.github.com",
      "api.example.com",
      "*.internal.company.com"
    ],
    "denied_ips": [
      "127.0.0.1",
      "169.254.169.254"
    ]
  }
}
```

### Audit Logs

Check what operations were attempted and denied:

```bash
# View audit logs (on Unix)
tail -f /tmp/mcp_security_audit.log

# Search for denials
grep "DENIED" /tmp/mcp_security_audit.log

# Analyze patterns
grep "path_traversal" /tmp/mcp_security_audit.log | wc -l
```

**Log Format**:
```
[2025-12-07 10:30:45] PreToolUse DENIED fs:read {path: "../../.env", reason: "Path traversal detected"}
[2025-12-07 10:30:46] PreToolUse APPROVED shell:execute {command: "pytest tests/", status: "OK"}
```

---

## Migration from --dangerously-skip-permissions

If you previously used `--dangerously-skip-permissions` flag, migrate to the security policy system:

### Step 1: Create Security Policy

```bash
python plugins/autonomous-dev/lib/mcp_profile_manager.py --init development
```

This creates `.mcp/security_policy.json` with development profile.

### Step 2: Test Operations

```bash
# Test operations that were running with --dangerously-skip-permissions
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-read "src/main.py"
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-shell "pytest tests/"
```

### Step 3: Update .mcp/config.json

Remove `--dangerously-skip-permissions` flag:

**Before**:
```json
{
  "mcpServers": {
    "autonomous-dev": {
      "command": "python",
      "args": ["mcp_server.py", "--dangerously-skip-permissions"],
      "env": {}
    }
  }
}
```

**After**:
```json
{
  "mcpServers": {
    "autonomous-dev": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {}
    }
  }
}
```

### Step 4: Customize Permissions

If tests fail after migration, update security_policy.json:

```bash
# Identify what needs permission
grep "DENIED" /tmp/mcp_security_audit.log

# Add to allowlist in security_policy.json
vim .mcp/security_policy.json

# Verify changes
python plugins/autonomous-dev/lib/mcp_permission_validator.py --validate .mcp/security_policy.json
```

### Step 5: Restart Claude

Restart Claude Code or Claude Desktop for changes to take effect.

---

## Security Considerations

### Audit Trail

All validation decisions are logged for security auditing:

```python
# Enable audit logging
validator = MCPPermissionValidator(
    policy_path=".mcp/security_policy.json",
    enable_audit_log=True
)

# All operations logged to /tmp/mcp_security_audit.log
```

### Symlink Attacks

The validator detects and blocks dangerous symlink operations:

```python
# Automatically blocked
validator.validate_fs_read("../../../etc/passwd")  # DENIED: symlink traversal
validator.validate_fs_write("./link_to_system")    # DENIED: could be symlink
```

### Command Injection

Shell metacharacters are detected and blocked:

```python
# Automatically blocked
validator.validate_shell_execute("pytest; rm -rf /")     # DENIED: semicolon injection
validator.validate_shell_execute("pytest | sh")          # DENIED: pipe injection
validator.validate_shell_execute("pytest $(evil)")       # DENIED: command substitution
```

### Private IP Blocking

Prevents SSRF attacks:

```python
# Automatically blocked
validator.validate_network_access("http://127.0.0.1:6379")      # DENIED: localhost
validator.validate_network_access("http://169.254.169.254")     # DENIED: AWS metadata
validator.validate_network_access("http://192.168.1.1")         # DENIED: private IP
```

---

## Integration with Autonomous Development

The MCP security system integrates with the autonomous-dev workflow:

1. **Hook Integration**: `mcp_security_enforcer.py` hook validates MCP operations
2. **Policy Loading**: Auto-detects and loads `.mcp/security_policy.json` on startup
3. **Fallback Profile**: Uses development profile if policy file not found
4. **Audit Trail**: All operations logged for compliance and debugging

### How It Works

1. **PreToolUse Hook Triggered**: Before MCP tool executes
2. **Policy Loaded**: `.mcp/security_policy.json` validated
3. **Operation Validated**: MCPPermissionValidator checks request
4. **Result Returned**: Approved/denied decision
5. **Audit Logged**: All attempts recorded (approved and denied)
6. **Tool Execution**: Only approved operations proceed

### Example Workflow

```python
# In Claude Code / Claude Desktop

# 1. Claude asks to read a file
# "Can you read src/main.py?"

# 2. Hook intercepts MCP tool call
# → mcp_security_enforcer.py loads .mcp/security_policy.json
# → MCPPermissionValidator.validate_fs_read("src/main.py") called
# → Checks against patterns, returns APPROVED
# → Tool executes

# 3. Claude asks for sensitive file
# "Can you read .env?"

# 2. Hook intercepts MCP tool call
# → MCPPermissionValidator.validate_fs_read(".env") called
# → Matches "!**/.env" denylist and sensitive file detection
# → Returns DENIED (reason: "Sensitive file - blocked by policy")
# → Tool does NOT execute

# 4. Both operations logged to audit trail
```

---

## API Reference Summary

### MCPPermissionValidator

**Location**: `plugins/autonomous-dev/lib/mcp_permission_validator.py`

**Constructor**:
```python
validator = MCPPermissionValidator(policy_path: Optional[str] = None)
```

**Methods**:
- `validate_fs_read(path: str) -> ValidationResult`
- `validate_fs_write(path: str) -> ValidationResult`
- `validate_shell_execute(command: str) -> ValidationResult`
- `validate_network_access(url: str) -> ValidationResult`
- `validate_env_access(var_name: str) -> ValidationResult`
- `load_policy(policy: Dict[str, Any]) -> None`

### MCPProfileManager

**Location**: `plugins/autonomous-dev/lib/mcp_profile_manager.py`

**Constructor**:
```python
manager = MCPProfileManager()
```

**Methods**:
- `create_profile(profile_type: ProfileType) -> Dict[str, Any]`
- `save_profile(profile: Dict[str, Any], output_path: str) -> None`
- `load_profile(input_path: str) -> Dict[str, Any]`

**Profile Types**:
- `ProfileType.DEVELOPMENT` - Most permissive
- `ProfileType.TESTING` - Moderate restrictions
- `ProfileType.PRODUCTION` - Strictest

### MCPSecurityEnforcer (Hook) - DEPRECATED

**Previous Location**: `plugins/autonomous-dev/hooks/mcp_security_enforcer.py` (Archived 2026-01-09)

**Current Location**: `plugins/autonomous-dev/hooks/unified_pre_tool.py` (Layer 2: MCP Security Validator)

**Lifecycle**: PreToolUse

**Validates**: All MCP tool operations before execution

**Migration**: See deprecation notice at top of this document and `hooks/archived/README.md` for Issue #211 details.

---

## Related Documentation

- **[CLAUDE.md](../CLAUDE.md)** - MCP Server section with configuration instructions
- **[.mcp/README.md](../.mcp/README.md)** - MCP setup and configuration
- **[SECURITY.md](SECURITY.md)** - Comprehensive security audit and hardening
- **[LIBRARIES.md](LIBRARIES.md)** - Complete API documentation for all libraries
- **[HOOKS.md](HOOKS.md)** - Automation hooks reference

---

## Examples

### Example 1: Development Environment Setup

```bash
# 1. Initialize development security policy
python plugins/autonomous-dev/lib/mcp_profile_manager.py --init development

# 2. Verify permissions
python plugins/autonomous-dev/lib/mcp_permission_validator.py --validate .mcp/security_policy.json

# 3. Test common operations
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-read "src/main.py"
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-shell "pytest tests/"
python plugins/autonomous-dev/lib/mcp_permission_validator.py --test-env "PATH"

# 4. Ready for autonomous development
```

### Example 2: Restricting to Production Environment

```python
from autonomous_dev.lib.mcp_profile_manager import MCPProfileManager, ProfileType

manager = MCPProfileManager()

# Create production profile
profile = manager.create_profile(ProfileType.PRODUCTION)

# Save to .mcp/security_policy.json
manager.save_profile(profile, ".mcp/security_policy.json")

# Verify it's loaded on MCP startup
```

### Example 3: Custom Permissions for CI/CD

```python
from autonomous_dev.lib.mcp_profile_manager import (
    MCPProfileManager,
    ProfileType,
    customize_profile
)

manager = MCPProfileManager()

# Start with testing profile
profile = manager.create_profile(ProfileType.TESTING)

# Customize for CI/CD
custom = customize_profile(profile, {
    "shell": {
        "allowed_commands": ["pytest", "git", "python", "docker"]
    },
    "filesystem": {
        "write": ["tests/**", "build/**", "dist/**"]
    },
    "network": {
        "allowed_domains": ["api.github.com", "*.circleci.com"]
    }
})

# Save and deploy
manager.save_profile(custom, ".mcp/security_policy.json")
```

---

**For questions or security concerns, see [SECURITY.md](SECURITY.md) or open an issue on GitHub.**
