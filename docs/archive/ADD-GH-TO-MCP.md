# Adding `gh` to MCP Allowed Commands

**Date**: 2025-10-25
**Purpose**: Allow GitHub CLI (`gh`) commands to run via MCP shell server

---

## Quick Answer

If you're using the **MCP Shell Server**, add `gh` to the allowed commands list in your MCP configuration.

---

## Configuration Locations

MCP configuration can be in different locations depending on your setup:

### Option 1: Claude Desktop MCP Config (Most Common)
**File**: `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac)

**Add this**:
```json
{
  "mcpServers": {
    "shell": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-shell"
      ],
      "env": {
        "ALLOWED_COMMANDS": "ls,cat,grep,find,git,gh"
      }
    }
  }
}
```

**Key part**: `"ALLOWED_COMMANDS": "ls,cat,grep,find,git,gh"`
- Added `gh` to the comma-separated list

### Option 2: Standalone MCP Config
**File**: `~/.config/mcp/config.json` or `~/.claude/mcp.json`

```json
{
  "servers": {
    "shell": {
      "command": "mcp-server-shell",
      "allowedCommands": ["ls", "cat", "grep", "find", "git", "gh"]
    }
  }
}
```

### Option 3: Project-Specific MCP
**File**: `.mcp/config.json` (in your project root)

```json
{
  "servers": {
    "shell": {
      "allowedCommands": ["git", "gh", "pytest", "black", "isort"]
    }
  }
}
```

---

## Step-by-Step: Add `gh` to MCP

### 1. Find Your MCP Configuration

```bash
# Check Claude Desktop config
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# OR check standalone MCP config
cat ~/.config/mcp/config.json

# OR check project MCP config
cat .mcp/config.json
```

### 2. Edit the Configuration

**If using Claude Desktop config**:
```bash
# Open in editor
code ~/Library/Application\ Support/Claude/claude_desktop_config.json

# OR
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Add `gh` to `ALLOWED_COMMANDS`**:
```json
{
  "mcpServers": {
    "shell": {
      ...
      "env": {
        "ALLOWED_COMMANDS": "existing,commands,gh"  // Add gh here
      }
    }
  }
}
```

### 3. Restart Claude Desktop

```bash
# Quit Claude completely (Cmd+Q on Mac)
# Reopen Claude Desktop

# OR via terminal
pkill -9 Claude
open -a Claude
```

### 4. Test `gh` Access

In Claude Desktop, ask:
```
Run: gh --version
```

Expected result:
```
gh version 2.x.x (...)
```

---

## Common MCP Shell Commands to Allow

**Recommended for autonomous-dev**:
```json
"ALLOWED_COMMANDS": "ls,cat,grep,find,git,gh,pytest,black,isort,npm,node,python,python3"
```

**Why**:
- `ls`, `cat`, `grep`, `find` - Basic file operations
- `git` - Version control
- `gh` - GitHub CLI (issues, PRs, etc.)
- `pytest` - Running tests
- `black`, `isort` - Code formatting
- `npm`, `node` - JavaScript projects
- `python`, `python3` - Python execution

---

## Troubleshooting

### "gh command not found" after adding to MCP

**Cause**: `gh` not installed on system

**Fix**:
```bash
# Install GitHub CLI
brew install gh         # Mac
# OR
sudo apt install gh     # Linux

# Verify
gh --version

# Restart Claude Desktop
```

### "gh: permission denied" from MCP

**Cause**: Not in ALLOWED_COMMANDS or typo

**Fix**:
```bash
# Check current allowed commands
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | grep ALLOWED

# Should include "gh"
# If not, add it and restart Claude
```

### Changes not taking effect

**Cause**: Claude Desktop caches configuration

**Fix**:
```bash
# Complete restart (kill and reopen)
pkill -9 Claude
sleep 2
open -a Claude
```

---

## Security Note

**Be careful what commands you allow!**

✅ **SAFE**:
- `gh` - GitHub CLI (read/write GitHub, but requires auth)
- `git` - Version control (local operations)
- `pytest`, `black`, `isort` - Development tools

⚠️ **RISKY**:
- `rm` - Can delete files
- `curl`, `wget` - Can download arbitrary files
- `sudo` - Escalated privileges
- `npm install` - Can run arbitrary code

**Recommendation**: Only allow commands you specifically need and trust.

---

## Example: Complete Claude Desktop MCP Config

```json
{
  "mcpServers": {
    "shell": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-shell"
      ],
      "env": {
        "ALLOWED_COMMANDS": "ls,cat,grep,find,git,gh,pytest,black,isort,python3"
      }
    },
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your_token_here"
      }
    }
  }
}
```

**Note**: This example includes both shell server (with `gh` allowed) AND GitHub MCP server (for direct API access).

---

## Alternative: Use GitHub MCP Server

If you want **native GitHub integration** (not just `gh` command), use the GitHub MCP server:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

**Benefits**:
- Direct GitHub API access (no `gh` command needed)
- Create issues, PRs, manage repos via MCP tools
- More integrated than shell commands

**Setup**:
1. Create GitHub Personal Access Token: https://github.com/settings/tokens
2. Scopes needed: `repo`, `workflow`, `write:discussion`
3. Add to config above
4. Restart Claude Desktop

---

## Summary

**To add `gh` to MCP**:

1. ✅ Find your MCP config (likely `~/Library/Application Support/Claude/claude_desktop_config.json`)
2. ✅ Add `gh` to `ALLOWED_COMMANDS`: `"existing,commands,gh"`
3. ✅ Restart Claude Desktop completely (Cmd+Q, reopen)
4. ✅ Test: Ask Claude to run `gh --version`

**Result**: Claude can now use `gh` commands for GitHub operations!

---

**Need help?** Check your specific MCP configuration and let me know what you find.
