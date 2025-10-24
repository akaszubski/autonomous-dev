# Claude Code 2.0 Plugin Development - Best Practices Research Report

**Date**: 2025-10-24
**Claude Code Version**: 2.0+
**Sources**: Official Claude Code documentation (docs.claude.com), autonomous-dev codebase analysis

---

## Executive Summary

This report documents best practices for creating Claude Code 2.0 plugins based on official documentation and analysis of the autonomous-dev plugin (8 agents, 6 skills, 9 hooks, 33 commands).

---

## Plugin Structure

### Directory Organization

```
plugin-name/
├── .claude-plugin/
│   ├── plugin.json           # Required: Plugin manifest
│   └── marketplace.json      # Optional: Marketplace listing
├── agents/                   # Subagent definitions
├── skills/                   # Agent Skills (model-invoked)
├── commands/                 # Slash commands
├── hooks/                    # Event handlers
├── scripts/                  # Supporting scripts
└── README.md
```

### Required: plugin.json

Minimal format:
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Brief description"
}
```

Full format with custom paths:
```json
{
  "name": "autonomous-dev",
  "version": "2.0.0",
  "description": "PROJECT.md-first autonomous development plugin",
  "author": {"name": "Author Name"},
  "repository": {"type": "git", "url": "https://..."},
  "license": "MIT",
  "components": {
    "agents": "./agents",
    "skills": "./skills",
    "commands": "./commands"
  },
  "requirements": {
    "claude_code_version": ">=2.0.0"
  }
}
```

Key variable: `${CLAUDE_PLUGIN_ROOT}` - absolute path to plugin

---

## Agents (Subagents)

### File Format

**Location**: `agents/agent-name.md`

**Structure**: Markdown with YAML frontmatter

```markdown
---
name: agent-name
description: When this agent should be invoked
tools: [Tool1, Tool2, Tool3]
model: sonnet
---

# Agent Name

System prompt and instructions...
```

### Frontmatter Fields

- `name` (required): Lowercase identifier with hyphens
- `description` (required): Natural language when-to-invoke description
- `tools` (optional): List of allowed tools; omit for all tools
- `model` (optional): `sonnet`, `opus`, `haiku`, or `inherit`

### Tool Examples

**All tools (inherit):**
```yaml
---
name: orchestrator
description: Coordinates the entire pipeline
model: sonnet
---
```

**Restricted (security):**
```yaml
---
name: researcher
tools: [WebSearch, WebFetch, Read, Bash, Grep, Glob]
model: sonnet
---
```

**Read-only:**
```yaml
---
name: planner
tools: [Read, Grep, Glob, Bash]
model: opus
---
```

### Available Core Tools

- Read, Write, Edit, Bash, Grep, Glob
- WebSearch, WebFetch (if available)
- Plus MCP tools if configured

### Model Selection Strategy

From autonomous-dev:
- **opus**: Complex planning, architecture ($$$)
- **sonnet**: General implementation ($$)
- **haiku**: Routine tasks ($)

### Best Practices

1. Clear descriptions: "Research patterns and best practices (v2.0)"
2. Restrict tools: Only grant what's needed
3. Document input/output: Specify artifacts expected/produced
4. Use artifacts for communication: Not bloated context
5. Model optimization: Match complexity to cost

---

## Skills (Agent Skills)

### File Format

**Location**: `skills/skill-name/SKILL.md`

**Structure**: Markdown with YAML frontmatter

```markdown
---
name: skill-name
type: knowledge
description: What it does AND when to use it. Include keywords.
keywords: keyword1, keyword2, keyword3
auto_activate: true
allowed-tools: Read, Grep, Glob
---

# Skill Name

Documentation Claude reads when activated...

## When This Activates
- Scenario 1
- Keywords: "keyword1", "keyword2"
```

### Frontmatter Fields

- `name` (required): Lowercase, hyphens, max 64 chars
- `description` (required): What + when, max 1024 chars
- `type` (optional): `knowledge`
- `keywords` (optional): Comma-separated activation keywords
- `auto_activate` (optional): Boolean, auto-activate on keyword match
- `allowed-tools` (optional): Comma-separated tool restrictions

### Skill vs Agent

**Use Skills:**
- Reference documentation (standards, best practices)
- Keyword-based activation
- No complex workflow
- Information Claude autonomously uses
- Example: `python-standards`, `security-patterns`

**Use Agents:**
- Complex multi-step workflows
- Explicit invocation
- Communicates with other agents
- Produces artifacts
- Example: `planner`, `implementer`

### Best Practices

1. Specific descriptions: "Python code quality standards (PEP 8, type hints, docstrings). Use when writing Python code."
2. Include keywords: `python, pep8, type hints, docstrings`
3. Use auto_activate: For common patterns
4. Restrict tools: Read-only when appropriate
5. Organize by topic: Language standards, domain expertise

---

## Commands (Slash Commands)

### File Format

**Location**: `commands/command-name.md`

**Structure**: Markdown with YAML frontmatter

```markdown
---
description: Brief command description
argument-hint: [optional-arg]
model: sonnet
allowed-tools: Read, Write, Bash
---

# Command Name

**Brief description**

## Usage

```bash
/command-name [arguments]
```

**Time**: Estimated duration

## What This Does

Detailed explanation...

## Example Output

Expected output...
```

### Frontmatter Fields

- `description`: Brief description (shown in `/help`)
- `argument-hint`: Expected arguments format
- `model`: Override default model
- `allowed-tools`: Tool restrictions

### Argument Handling

- `$ARGUMENTS` - All arguments as string
- `$1`, `$2` - Positional arguments

### Naming Conventions

1. Group by function: `/test`, `/test-unit`, `/test-integration`
2. Use verb prefixes: `/align-project`, `/setup`, `/format`
3. Namespacing optional: `/plugin-name:command` or `/command`

### Best Practices

1. Clear descriptions for `/help`
2. Document time estimates
3. Show expected output
4. Include when to use
5. Reference related commands

---

## Hooks (Event Handlers)

### Configuration

**Option 1: hooks/hooks.json**
```json
{
  "description": "Hook purpose",
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/script.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Option 2: Inline in plugin.json**

### Available Hook Events

- `PreToolUse` / `PostToolUse` - Tool execution lifecycle
- `UserPromptSubmit` - User input enrichment
- `Notification` - System notifications
- `Stop` / `SubagentStop` - Agent stoppage
- `SessionStart` / `SessionEnd` - Session lifecycle
- `PreCompact` - Context compaction

### Hook Types

- `command`: Execute shell command
- `validation`: Validate operation (can block)
- `notification`: Display message

### Example Hooks

**Auto-format (PostToolUse):**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write:*.py",
        "hooks": [{
          "type": "command",
          "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/auto_format.py",
          "timeout": 30
        }]
      }
    ]
  }
}
```

**Protect sensitive files (PreToolUse):**
Bash script blocks writes to .env, credentials.json, etc.

**Orchestrator trigger (UserPromptSubmit):**
Detects implementation keywords and activates autonomous mode.

### Best Practices

1. Use hooks for automation, not manual tasks
2. Keep hooks fast with appropriate timeouts
3. Make hooks idempotent
4. Provide clear error messages
5. Shell for simple, Python for complex logic

---

## Common Patterns

### Pattern: Artifact-Based Communication

Good (autonomous-dev):
- Orchestrator creates manifest.json
- Researcher reads manifest, creates research.json
- Planner reads both, creates architecture.json
- Keeps context small (200 tokens vs 5000+)

### Pattern: Progressive Enhancement

Good (autonomous-dev):
- /commit (2 min)
- /commit-check (5 min)
- /commit-push (10 min)
- /commit-release (15 min)

### Pattern: Model Optimization

- opus: Strategic planning (infrequent, complex)
- sonnet: General implementation (frequent)
- haiku: Routine tasks (very frequent)

### Pattern: Tool Restrictions

- Read-only analyst: [Read, Grep, Glob, Bash]
- Researcher: [WebSearch, WebFetch, Read, Grep, Glob]
- Implementer: [Read, Write, Edit, Bash, Grep, Glob]

---

## Common Mistakes

1. Missing frontmatter fields (always include name, description)
2. Unclear descriptions (include WHAT and WHEN)
3. No tool restrictions (security risk)
4. Vague skill keywords
5. Slow hooks without timeout
6. No documentation
7. Monolithic commands (break into focused commands)
8. Context bloat (use artifacts instead)
9. No error messages
10. Testing only after distribution (use local marketplace)

---

## Testing and Distribution

### Local Testing

Create dev marketplace:
```json
{
  "marketplaces": [{
    "name": "dev",
    "url": "./dev-marketplace",
    "plugins": [{"name": "my-plugin", "path": "./plugins/my-plugin"}]
  }]
}
```

Install and iterate:
```bash
/plugin marketplace add ./dev-marketplace
/plugin install my-plugin@dev
# Make changes
/plugin uninstall my-plugin
/plugin install my-plugin@dev
```

### Distribution

Create marketplace.json in GitHub repo:
```json
{
  "name": "my-marketplace",
  "plugins": [{"name": "my-plugin", "path": "./plugins/my-plugin"}]
}
```

Users install:
```bash
/plugin marketplace add username/repository
/plugin install my-plugin@my-marketplace
```

### Versioning

Semantic versioning: MAJOR.MINOR.PATCH
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

---

## Reference Links

**Official Documentation:**
- Plugins: https://docs.claude.com/en/docs/claude-code/plugins
- Subagents: https://docs.claude.com/en/docs/claude-code/sub-agents
- Skills: https://docs.claude.com/en/docs/claude-code/skills
- Hooks: https://docs.claude.com/en/docs/claude-code/hooks
- Commands: https://docs.claude.com/en/docs/claude-code/slash-commands
- Reference: https://docs.claude.com/en/docs/claude-code/plugins-reference

**Example Plugin:**
- autonomous-dev: https://github.com/akaszubski/autonomous-dev
- 8 agents, 6 skills, 9 hooks, 33 commands

---

**End of Report**
