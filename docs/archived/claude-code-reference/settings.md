# Claude Code Settings - Complete Reference

> **Source**: https://code.claude.com/docs/en/settings
> **Downloaded**: 2025-12-16

## Table of Contents

1. [Settings Files](#settings-files)
2. [Available Settings](#available-settings)
3. [Permission Settings](#permission-settings)
4. [Sandbox Settings](#sandbox-settings)
5. [Attribution Settings](#attribution-settings)
6. [Settings Precedence](#settings-precedence)
7. [Environment Variables](#environment-variables)
8. [Tools Available](#tools-available)
9. [Bash Tool Behavior](#bash-tool-behavior)
10. [Plugin Configuration](#plugin-configuration)
11. [Configuration Examples](#configuration-examples)

---

## Settings Files

Claude Code uses hierarchical settings stored in `settings.json` files at multiple levels:

### User Settings (`~/.claude/settings.json`)
- Applies globally to all projects
- Personal preferences and global configuration
- Not shared with team

### Project Settings - Shared (`.claude/settings.json`)
- Team-shared configuration
- Checked into source control
- Shared with entire team

### Project Settings - Local (`.claude/settings.local.json`)
- Personal project-specific preferences
- Automatically added to `.gitignore` when created
- Not shared with team

### Enterprise Managed Settings
- macOS: `/Library/Application Support/ClaudeCode/managed-settings.json`
- Linux/WSL: `/etc/claude-code/managed-settings.json`
- Windows: `C:\Program Files\ClaudeCode\managed-settings.json`

### Enterprise Managed MCP
- macOS: `/Library/Application Support/ClaudeCode/managed-mcp.json`
- Linux/WSL: `/etc/claude-code/managed-mcp.json`
- Windows: `C:\Program Files\ClaudeCode\managed-mcp.json`

### Other Configuration (`~/.claude.json`)
- User preferences (theme, notifications, editor mode)
- OAuth session data
- MCP server configurations
- Per-project state
- Various caches

---

## Available Settings

### General Settings

| Key | Description | Example |
|-----|-------------|---------|
| `apiKeyHelper` | Custom script to generate auth value | `/bin/generate_temp_api_key.sh` |
| `cleanupPeriodDays` | Sessions older than this are deleted. Default: 30 | `20` |
| `companyAnnouncements` | Announcements shown at startup | `["Welcome to Acme Corp!"]` |
| `env` | Environment variables for every session | `{"FOO": "bar"}` |
| `attribution` | Custom attribution for git/PRs | `{"commit": "🤖 Generated", "pr": ""}` |
| `permissions` | Tool permissions configuration | See Permission Settings |
| `hooks` | Custom commands before/after tools | `{"PreToolUse": {...}}` |
| `disableAllHooks` | Disable all hooks | `true` |
| `model` | Override default model | `"claude-sonnet-4-5-20250929"` |
| `statusLine` | Custom status line display | `{"type": "command", "command": "..."}` |
| `outputStyle` | Adjust system prompt style | `"Explanatory"` |
| `forceLoginMethod` | Restrict login: `claudeai` or `console` | `claudeai` |
| `forceLoginOrgUUID` | Auto-select organization UUID | `"xxxxxxxx-xxxx-..."` |
| `enableAllProjectMcpServers` | Auto-approve all MCP servers | `true` |
| `enabledMcpjsonServers` | List of MCP servers to approve | `["memory", "github"]` |
| `disabledMcpjsonServers` | List of MCP servers to reject | `["filesystem"]` |
| `allowedMcpServers` | Managed settings only - MCP allowlist | `[{"serverName": "github"}]` |
| `deniedMcpServers` | Managed settings only - MCP denylist | `[{"serverName": "filesystem"}]` |
| `alwaysThinkingEnabled` | Enable extended thinking by default | `true` |

---

## Permission Settings

### Permission Rules

| Key | Description | Example |
|-----|-------------|---------|
| `allow` | Rules to allow tool use | `["Bash(git diff:*)"]` |
| `ask` | Rules to ask for confirmation | `["Bash(git push:*)"]` |
| `deny` | Rules to deny tool use | `["WebFetch", "Bash(curl:*)"]` |
| `additionalDirectories` | Additional working directories | `["../docs/"]` |
| `defaultMode` | Default permission mode | `"acceptEdits"` |
| `disableBypassPermissionsMode` | Prevent bypassing permissions | `"disable"` |

### Permission Rule Examples

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run test:*)",
      "Bash(git:*)",
      "Read(./src/**)"
    ],
    "ask": [
      "Bash(git push:*)",
      "WebFetch"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Bash(curl:*)",
      "Bash(rm -rf:*)"
    ]
  }
}
```

### Recommended Security Denials

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(./config/credentials.json)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(sudo:*)",
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)"
    ]
  }
}
```

---

## Sandbox Settings

### Configuration Options

| Key | Description | Default | Example |
|-----|-------------|---------|---------|
| `enabled` | Enable bash sandboxing (macOS/Linux only) | `false` | `true` |
| `autoAllowBashIfSandboxed` | Auto-approve sandboxed commands | `true` | `true` |
| `excludedCommands` | Commands to run outside sandbox | — | `["git", "docker"]` |
| `allowUnsandboxedCommands` | Allow `dangerouslyDisableSandbox` | `true` | `false` |
| `network.allowUnixSockets` | Unix socket paths accessible | — | `["~/.ssh/agent-socket"]` |
| `network.allowLocalBinding` | Allow localhost port binding | `false` | `true` |
| `network.httpProxyPort` | Custom HTTP proxy port | Auto | `8080` |
| `network.socksProxyPort` | Custom SOCKS5 proxy port | Auto | `8081` |

### Sandbox Configuration Example

```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["docker"],
    "network": {
      "allowUnixSockets": ["/var/run/docker.sock"],
      "allowLocalBinding": true
    }
  }
}
```

---

## Attribution Settings

### Configuration

| Key | Description |
|-----|-------------|
| `commit` | Attribution for git commits with trailers |
| `pr` | Attribution for pull request descriptions |

### Default Commit Attribution

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Custom Example

```json
{
  "attribution": {
    "commit": "Generated with AI\n\nCo-Authored-By: AI <ai@example.com>",
    "pr": ""
  }
}
```

---

## Settings Precedence

**Order from highest to lowest priority:**

1. **Enterprise Managed Policies** (`managed-settings.json`)
   - Deployed by IT/DevOps
   - Cannot be overridden

2. **Command Line Arguments**
   - Temporary overrides for specific session
   - Example: `claude --model claude-opus-4-5`

3. **Local Project Settings** (`.claude/settings.local.json`)
   - Personal project-specific settings
   - Not shared

4. **Shared Project Settings** (`.claude/settings.json`)
   - Team-shared settings
   - Checked into git

5. **User Settings** (`~/.claude/settings.json`)
   - Personal global settings
   - Lowest priority

**Example:**
```
User: allow Bash(npm run:*)
Project: deny Bash(npm:*)
Result: npm commands are DENIED (project wins)
```

---

## Environment Variables

### API and Authentication

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key for Claude SDK |
| `ANTHROPIC_AUTH_TOKEN` | Custom Authorization header |
| `ANTHROPIC_CUSTOM_HEADERS` | Custom headers (format: `Name: Value`) |

### Model Configuration

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_MODEL` | Model setting name to use |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Override default Haiku |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Override default Opus |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Override default Sonnet |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Subagent model |

### Bash Configuration

| Variable | Description |
|----------|-------------|
| `BASH_DEFAULT_TIMEOUT_MS` | Default bash timeout |
| `BASH_MAX_OUTPUT_LENGTH` | Max chars before truncation |
| `BASH_MAX_TIMEOUT_MS` | Maximum timeout allowed |
| `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR` | Return to project dir |

### Token and Performance

| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | Max output tokens |
| `MAX_MCP_OUTPUT_TOKENS` | Max MCP output (default: 25000) |
| `MAX_THINKING_TOKENS` | Extended thinking budget |
| `SLASH_COMMAND_TOOL_CHAR_BUDGET` | Max slash command chars |

### Cloud Provider

| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_USE_BEDROCK` | Use AWS Bedrock |
| `CLAUDE_CODE_USE_VERTEX` | Use Google Vertex AI |
| `CLAUDE_CODE_USE_FOUNDRY` | Use Microsoft Foundry |

### Network and Proxy

| Variable | Description |
|----------|-------------|
| `HTTP_PROXY` | HTTP proxy server |
| `HTTPS_PROXY` | HTTPS proxy server |
| `NO_PROXY` | Domains/IPs to bypass proxy |

### Telemetry and Reporting

| Variable | Description |
|----------|-------------|
| `DISABLE_TELEMETRY` | Opt out of Statsig |
| `DISABLE_ERROR_REPORTING` | Opt out of Sentry |
| `DISABLE_AUTOUPDATER` | Disable auto-updates |

---

## Tools Available

| Tool | Description | Permission Required |
|------|-------------|-------------------|
| `AskUserQuestion` | Ask multiple choice questions | No |
| `Bash` | Execute shell commands | Yes |
| `BashOutput` | Retrieve background bash output | No |
| `Edit` | Make targeted file edits | Yes |
| `ExitPlanMode` | Prompt to exit plan mode | Yes |
| `Glob` | Find files by pattern | No |
| `Grep` | Search in file contents | No |
| `KillShell` | Kill background bash shell | No |
| `NotebookEdit` | Modify Jupyter notebook cells | Yes |
| `Read` | Read file contents | No |
| `Skill` | Execute a skill | Yes |
| `SlashCommand` | Run custom slash command | Yes |
| `Task` | Run sub-agent for complex tasks | No |
| `TodoWrite` | Create/manage task lists | No |
| `WebFetch` | Fetch URL content | Yes |
| `WebSearch` | Perform web searches | Yes |
| `Write` | Create/overwrite files | Yes |

---

## Bash Tool Behavior

### Working Directory Persistence

- Default: Directory persists between commands
- Override with `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1`

### Environment Variables Do NOT Persist

- Each command runs in fresh shell environment
- Variables set in one command aren't available in next

### Making Environment Variables Persist

**Option 1 - Before starting Claude Code:**
```bash
conda activate myenv
claude
```

**Option 2 - Set CLAUDE_ENV_FILE:**
```bash
export CLAUDE_ENV_FILE=/path/to/env-setup.sh
claude
```

**Option 3 - SessionStart Hook (project-specific):**
```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "startup",
      "hooks": [{
        "type": "command",
        "command": "echo 'conda activate myenv' >> \"$CLAUDE_ENV_FILE\""
      }]
    }]
  }
}
```

---

## Plugin Configuration

### Plugin Settings

```json
{
  "enabledPlugins": {
    "formatter@company-tools": true,
    "deployer@company-tools": true,
    "analyzer@security-plugins": false
  },
  "extraKnownMarketplaces": {
    "company-tools": {
      "source": "github",
      "repo": "company/claude-plugins"
    }
  }
}
```

### Marketplace Source Types

- `github` - GitHub repo (uses `repo` param)
- `git` - Any git URL (uses `url` param)
- `directory` - Local path (uses `path` param, dev only)

### Managing Plugins

Use `/plugin` command to:
- Browse available plugins
- Install/uninstall plugins
- Enable/disable plugins
- View plugin details
- Add/remove marketplaces

---

## Configuration Examples

### Minimal Security

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  }
}
```

### Team Development

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run test:*)",
      "Bash(npm run lint:*)"
    ],
    "deny": [
      "Read(./.env*)",
      "Read(./secrets/**)",
      "Bash(npm publish:*)"
    ]
  },
  "env": {
    "NODE_ENV": "development"
  }
}
```

### Enterprise-Grade

```json
{
  "permissions": {
    "allow": ["Bash(git:*)", "Bash(npm run:*)"],
    "ask": ["Bash(git push:*)", "WebFetch"],
    "deny": ["Read(.env*)", "Read(./secrets/**)", "Bash(rm:*)"]
  },
  "forceLoginMethod": "console",
  "sandbox": {
    "enabled": true,
    "excludedCommands": ["git", "docker"]
  }
}
```

---

## Additional Resources

- [Settings Documentation](https://code.claude.com/docs/en/settings)
- [Permissions Guide](https://code.claude.com/docs/en/permissions)
- [Security Documentation](https://code.claude.com/docs/en/security)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)
