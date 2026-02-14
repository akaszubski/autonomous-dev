# Claude Code Plugins - Complete Documentation

> **Source**: https://code.claude.com/docs/en/plugins
> **Downloaded**: 2025-12-16
> **Status**: Plugins in Public Beta for All Claude Code Users

---

## Table of Contents

1. [Overview](#overview)
2. [Plugin Structure](#plugin-structure)
3. [Plugin Manifest](#plugin-manifest-pluginjson)
4. [Creating Plugins](#creating-plugins)
5. [Installing Plugins](#installing-plugins)
6. [Plugin Components](#plugin-components)
7. [Agent Skills](#agent-skills)
8. [Plugin Marketplaces](#plugin-marketplaces)
9. [Configuration](#configuration)
10. [Best Practices](#best-practices)
11. [Limitations & Restrictions](#limitations--restrictions)
12. [Troubleshooting](#troubleshooting)

---

## Overview

### What Are Claude Code Plugins?

Plugins extend Claude Code with custom functionality that can be shared across projects and teams. They allow you to:

- Add custom slash commands (`/command-name`)
- Create specialized subagents for specific tasks
- Implement Agent Skills that Claude autonomously activates
- Define event hooks for workflow automation
- Bundle Model Context Protocol (MCP) servers for external integrations

### Why Use Plugins?

- **Automation**: Automate repetitive development tasks
- **Reusability**: Share tools and workflows across projects
- **Customization**: Tailor Claude Code to your team's needs
- **Integration**: Connect with external services via MCP servers
- **Consistency**: Enforce development standards across teams

### Plugin Status

Plugins are now in **public beta** for all Claude Code users. They work seamlessly across:
- Claude Code CLI (terminal)
- VS Code integration
- Team repositories with consistent tooling

---

## Plugin Structure

### Directory Layout

A complete plugin follows this structure:

```
my-plugin/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest (REQUIRED)
│   ├── marketplace.json         # Marketplace metadata (optional)
│   └── default-settings.json    # Default Claude Code settings (optional)
├── commands/                    # Slash commands (optional)
│   ├── command-name.md
│   └── another-command.md
├── agents/                      # Subagents (optional)
│   ├── agent-name.md
│   └── specialized-agent.md
├── skills/                      # Agent Skills (optional)
│   ├── skill-name/
│   │   └── SKILL.md
│   └── another-skill/
│       └── SKILL.md
├── hooks/                       # Event handlers (optional)
│   └── hooks.json
├── .mcp.json                    # MCP server config (optional)
├── templates/                   # File templates (optional)
│   └── template-name.md
├── lib/                         # Shared libraries (optional)
│   └── utility.py
└── README.md                    # Plugin documentation
```

### For Plugin Marketplaces

If creating a marketplace with multiple plugins:

```
marketplace-name/
├── .claude-plugin/
│   └── marketplace.json         # Marketplace metadata
└── plugin-directory/            # Each plugin in subdirectory
    ├── .claude-plugin/
    │   └── plugin.json
    ├── commands/
    ├── agents/
    └── skills/
```

**Important**: Plugin directories must be at the plugin root, NOT inside `.claude-plugin/`

---

## Plugin Manifest (plugin.json)

### Required Fields

```json
{
  "name": "my-plugin",
  "description": "Brief description of what the plugin does",
  "version": "1.0.0",
  "author": {
    "name": "Your Name",
    "url": "https://github.com/yourname"
  }
}
```

### Complete Manifest Example

```json
{
  "name": "autonomous-dev",
  "version": "3.8.0",
  "description": "PROJECT.md-first autonomous development with 8-agent pipeline",
  "author": {
    "name": "Andrew Kaszubski",
    "url": "https://github.com/akaszubski"
  },
  "repository": {
    "type": "git",
    "url": "https://github.com/akaszubski/autonomous-dev"
  },
  "license": "MIT",
  "components": {
    "agents": "./agents",
    "skills": "./skills",
    "commands": "./commands",
    "templates": "./templates",
    "hooks": "./hooks"
  },
  "requirements": {
    "claude_code_version": ">=2.0.0",
    "python": ">=3.11"
  },
  "tags": [
    "agents",
    "skills",
    "hooks",
    "testing",
    "documentation",
    "automation"
  ],
  "readme": "./README.md"
}
```

### Manifest Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique plugin identifier (kebab-case) |
| `version` | string | Yes | Semantic versioning (MAJOR.MINOR.PATCH) |
| `description` | string | Yes | Brief description for marketplaces |
| `author` | object | Yes | `{name, url}` - Author information |
| `repository` | object | No | Git repository metadata |
| `license` | string | No | License type (e.g., MIT, Apache-2.0) |
| `components` | object | No | Paths to commands/, agents/, skills/, hooks/ |
| `requirements` | object | No | Min Claude Code version, Python version, etc. |
| `tags` | array | No | Search keywords for plugin marketplaces |
| `readme` | string | No | Path to README.md file |

---

## Creating Plugins

### Step 1: Create Plugin Manifest

Create the `.claude-plugin/plugin.json` file:

```bash
mkdir -p my-plugin/.claude-plugin
cat > my-plugin/.claude-plugin/plugin.json << 'EOF'
{
  "name": "my-plugin",
  "description": "A simple greeting plugin",
  "version": "1.0.0",
  "author": {
    "name": "Your Name"
  }
}
EOF
```

### Step 2: Add Components

#### Create a Command

Create `commands/greet.md`:

```markdown
---
title: Greet User
description: A simple greeting command
tools: []
---

Greet the user with a friendly message that includes their name if provided.
```

#### Create an Agent

Create `agents/researcher.md`:

```markdown
---
title: Research Specialist
description: Researches patterns and best practices
tools:
  - Grep
  - Read
  - WebSearch
---

You are a research specialist. Your role is to find existing patterns and best practices
in the codebase and on the web.

When asked to research something:
1. Search the local codebase using Grep and Read tools
2. Search the web for best practices using WebSearch
3. Summarize findings and recommend approaches
```

#### Create a Skill

Create `skills/python-testing/SKILL.md`:

```markdown
---
title: Python Testing
description: TDD and test automation patterns
category: testing
tags: [python, testing, pytest]
allowed-tools:
  - Bash(pytest:*)
  - Bash(python:*)
  - Read(**/*.py)
  - Write(**/*.py)
  - Grep
---

## Python Testing Skill

Teaches Claude Code when and how to write Python tests using pytest.

### When to Use

- Writing test cases for Python code
- Validating implementations with TDD
- Running test suites

### Key Patterns

1. **TDD Workflow**
   - Write failing test first
   - Implement code to pass test
   - Refactor if needed

2. **Test Organization**
   - Unit tests: `tests/unit/`
   - Integration tests: `tests/integration/`
   - UAT tests: `tests/uat/`

### Examples

```python
import pytest

def test_addition():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```
```

### Step 3: Test Locally

Create a test marketplace to verify your plugin:

```bash
# Create a local marketplace
mkdir -p ~/.claude/test-marketplace
cp -r my-plugin ~/.claude/test-marketplace/

# In Claude Code, use /plugin install command with local path
/plugin install ~/.claude/test-marketplace/my-plugin
```

---

## Installing Plugins

### From Marketplace

```bash
/plugin install plugin-name
```

### From Local Path

```bash
/plugin install /path/to/plugin
```

### From GitHub

```bash
/plugin install github:username/repo
# or
/plugin install https://github.com/username/repo
```

### In Team Repository

Create `.claude/plugins.json`:

```json
{
  "marketplaces": [
    "https://marketplace.example.com"
  ],
  "plugins": [
    {
      "name": "plugin-name",
      "marketplace": "official"
    }
  ]
}
```

Team members with access to the repo automatically get these plugins installed.

### Managing Plugins

```bash
# List installed plugins
/plugin list

# Get plugin info
/plugin info plugin-name

# Uninstall plugin
/plugin uninstall plugin-name

# Update plugin
/plugin update plugin-name

# Update all plugins
/plugin update
```

---

## Plugin Components

### 1. Commands

**Location**: `commands/` directory
**File Format**: Markdown with YAML frontmatter

#### Command Frontmatter

```markdown
---
title: Command Display Name
description: What this command does
allowed-tools:
  - Bash(./scripts:*)
  - Read(**/*.md)
  - WebSearch
  - Grep
triggers:
  - "keyword1"
  - "keyword2"
---

Command implementation text...
```

#### Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Display name in command palette |
| `description` | string | Brief description of command function |
| `allowed-tools` | array | Tools this command can use (least privilege) |
| `triggers` | array | Keywords that can trigger this command |
| `hidden` | boolean | Hide from command palette if true |
| `disabled` | boolean | Disable command if true |

### 2. Agents

**Location**: `agents/` directory
**File Format**: Markdown with YAML frontmatter

#### Agent Frontmatter

```markdown
---
title: Agent Display Name
description: What this agent does
model: claude-opus-4-5-20251101
temperature: 0.7
tools:
  - Grep
  - Read
  - WebSearch
  - WebFetch
skills:
  - python-testing
  - security-patterns
context_size: 8000
---

Agent implementation and instructions...
```

#### Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Agent display name |
| `description` | string | What agent does |
| `model` | string | Claude model to use |
| `temperature` | number | Reasoning temperature (0.0-2.0) |
| `tools` | array | Tools agent can invoke |
| `skills` | array | Skill IDs this agent uses |
| `context_size` | number | Max tokens for this agent |

### 3. Agent Skills

**Location**: `skills/skill-name/SKILL.md`
**File Format**: Markdown with YAML frontmatter

#### Skill Frontmatter

```markdown
---
title: Skill Display Name
description: What this skill teaches Claude
category: category-name
tags: [tag1, tag2]
allowed-tools:
  - Bash(python:*)
  - Read(**/*.py)
  - Write(**/*.py)
version: "1.0.0"
---

Skill content...
```

### 4. Hooks

**Location**: `hooks/hooks.json` or inline in `plugin.json`

#### Hook Types

| Event | When Triggered | Use Cases |
|-------|----------------|-----------|
| `UserPromptSubmit` | User submits prompt | Validate user input, check alignment |
| `PreToolUse` | Before tool execution | Security validation, auto-approval |
| `PostToolUse` | After tool execution | Auto-formatting, logging results |
| `SubagentStart` | Subagent begins | Initialize agent state |
| `SubagentStop` | Subagent completes | Process results, trigger automation |

#### Hooks Configuration

```json
{
  "PreToolUse": [
    {
      "matcher": "Write",
      "command": "python3 hooks/auto_format.py",
      "timeout": 5,
      "condition": "env.AUTO_FORMAT == true"
    }
  ],
  "PostToolUse": [
    {
      "matcher": "Bash(git:*)",
      "command": "python3 hooks/git_validator.py",
      "timeout": 10
    }
  ]
}
```

### 5. Model Context Protocol (MCP) Servers

**Location**: `.mcp.json` or inline in `plugin.json`

#### MCP Configuration

```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["-m", "mcp_server_module"],
      "env": {
        "API_KEY": "${API_KEY}",
        "CONFIG_PATH": "/path/to/config"
      }
    }
  }
}
```

---

## Agent Skills

### What Are Agent Skills?

Agent Skills are instruction manuals that teach Claude **when** and **how** to use installed tools and plugins automatically. Unlike explicit commands that users invoke with `/`, skills are **model-invoked**—Claude decides when to use them based on task context.

### Key Characteristics

- **Autonomous**: Claude decides when to apply skills based on context
- **Progressive**: Skills are loaded only when needed (no context bloat)
- **Composable**: Multiple skills can work together for complex tasks
- **Least Privilege**: Each skill declares exactly which tools it needs

### Using Skills in Commands and Agents

#### Declare Skills in Agent Frontmatter

```markdown
---
title: My Agent
description: Agent that uses multiple skills
tools: [Read, Write, Bash]
skills:
  - python-testing
  - security-patterns
  - documentation-sync
---

My agent uses these skills to automatically...
```

---

## Plugin Marketplaces

### Official Plugin Marketplaces

1. **Claude Code Official Marketplace**
   - URL: https://marketplace.anthropic.com/plugins
   - Status: Official Anthropic marketplace

2. **Community Marketplaces**
   - Claude Code Plugins Plus Hub (175+ plugins with Agent Skills v1.2.0)
   - Community-curated collections

### Creating Your Own Marketplace

```json
{
  "name": "My Team Marketplace",
  "description": "Internal plugin marketplace for our team",
  "owner": "Team Name",
  "plugins": [
    "plugin-one",
    "plugin-two"
  ]
}
```

---

## Best Practices

### 1. Design for Reusability

- Create tools that work across multiple projects
- Use generic patterns applicable to different codebases
- Document assumptions and requirements clearly

### 2. Principle of Least Privilege

```markdown
---
allowed-tools:
  - Read(**/*.py)      # Only Python files
  - Bash(python:*)     # Only python command
  - Bash(pytest:*)     # Only pytest
---
```

### 3. Clear Documentation

- Write comprehensive README with examples
- Document each command, agent, and skill clearly
- Include troubleshooting section

### 4. Semantic Versioning

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### 5. Security Best Practices

- **Never hardcode secrets**: Use environment variables
- **Validate inputs**: Check paths, commands, arguments
- **Limit file access**: Use specific glob patterns
- **Audit logging**: Log security-sensitive operations

---

## Limitations & Restrictions

### What Plugins CANNOT Do

1. **Modify Global Settings**
   - Cannot write to `~/.claude/` directories
   - Cannot modify `~/.claude/settings.json`
   - Cannot install to global locations

2. **Security Restrictions**
   ```
   BLOCKED:
   - Bash(sudo:*)          # No privilege escalation
   - Bash(rm -rf /):*      # No destructive operations
   - Read(~/.ssh/**)       # No secret file access
   - Write(/etc/**)        # No system file modification
   ```

3. **Tool Restrictions**
   - Must declare `allowed-tools` in frontmatter
   - Cannot use undeclared tools
   - Tool usage is validated at runtime

### What Plugins CAN Do

1. **Extend Commands** - Add custom slash commands
2. **Create Agents** - Specialized subagents for specific tasks
3. **Implement Hooks** - Automate workflows
4. **Integrate External Tools** - MCP servers for external APIs

---

## Troubleshooting

### Common Issues

#### "Plugin not loading"

1. Verify `plugin.json` syntax
2. Check file permissions
3. Restart Claude Code: Press Cmd+Q and relaunch
4. Review error logs

#### "Command not working"

1. Check command file syntax and frontmatter
2. Verify all declared tools exist
3. Test each tool individually

#### "Agent can't use tool"

Add tool to `allowed-tools` in agent frontmatter:
```markdown
---
allowed-tools:
  - Bash(python:*)
  - Read(**/*.py)
---
```

#### "Hook not triggering"

1. Verify hook script exists and is executable
2. Check matcher pattern
3. Test hook script manually
4. Check timeout isn't too short

---

## Additional Resources

- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [Plugins Reference](https://code.claude.com/docs/en/plugins-reference)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)
