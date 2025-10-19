# MCP Server Configuration

This directory contains the Model Context Protocol (MCP) server configuration for the claude-code-bootstrap repository.

## Overview

The MCP servers provide Claude with enhanced capabilities for interacting with this repository:

- **filesystem**: Read/write access to repository files
- **shell**: Execute allowed commands in the repository
- **git**: Git operations (status, diff, log, etc.)
- **python**: Python interpreter access with virtual environment

## Configuration

**Location**: `.mcp/config.json`

### Servers

#### 1. Filesystem Server (`mcp-filesystem`)

Provides file system access to the repository.

**Permissions**:
- `read`: Read files and directories
- `write`: Create, modify, and delete files

**Root**: `~/Documents/GitHub/claude-code-bootstrap`

#### 2. Shell Server (`mcp-shell`)

Executes shell commands within the repository.

**Working Directory**: `~/Documents/GitHub/claude-code-bootstrap`

**Allowed Commands**:
- `git` - Git version control
- `gh` - GitHub CLI
- `~/Documents/GitHub/claude-code-bootstrap/venv/bin/python` - Python interpreter (virtualenv)
- `bash` - Bash shell
- `zsh` - Zsh shell
- `pnpm` - Package manager
- `npm` - Node package manager
- `make` - Build automation

#### 3. Git Server (`mcp-git`)

Specialized Git operations.

**Repository Root**: `~/Documents/GitHub/claude-code-bootstrap`

**Capabilities**:
- View git status
- Read commit history
- Diff changes
- Branch management
- Remote operations

#### 4. Python Server (`mcp-python`)

Python interpreter with virtual environment support.

**Interpreter**: `~/Documents/GitHub/claude-code-bootstrap/venv/bin/python`

**Virtual Environment**: `~/Documents/GitHub/claude-code-bootstrap/venv`

**Use Cases**:
- Run Python scripts
- Execute tests
- Install packages
- Code analysis

## Setup

### 1. Create Virtual Environment

```bash
cd ~/Documents/GitHub/claude-code-bootstrap
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt  # If requirements.txt exists
```

### 3. Configure Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "claude-code-bootstrap": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "~/Documents/GitHub/claude-code-bootstrap"]
    }
  }
}
```

Or use the full configuration from `.mcp/config.json`.

## Usage

### Filesystem Operations

```bash
# Claude can now:
- Read any file in the repository
- Write new files
- Modify existing files
- Create directories
```

### Shell Commands

```bash
# Example commands Claude can run:
git status
git diff
python scripts/session_tracker.py test "MCP test"
npm install
make build
```

### Git Operations

```bash
# Claude can:
- Check git status
- View commit history
- Create branches
- Commit changes (if configured)
```

### Python Operations

```bash
# Claude can:
- Run Python scripts
- Execute tests (pytest)
- Install packages (pip)
- Run linters and formatters
```

## Security

### Permissions

- **Filesystem**: Read/write limited to repository root
- **Shell**: Only allowed commands can be executed
- **Git**: Repository-scoped operations only
- **Python**: Isolated to virtual environment

### Best Practices

1. **Review commands**: Always review shell commands before Claude executes them
2. **Virtual environment**: Keep Python dependencies isolated
3. **Git safety**: Use branches for experimental changes
4. **Backup**: Ensure important work is committed before extensive operations

## Troubleshooting

### Virtual Environment Not Found

```bash
# Create it:
cd ~/Documents/GitHub/claude-code-bootstrap
python3 -m venv venv
```

### Permission Denied

```bash
# Ensure paths are correct and accessible:
ls -la ~/Documents/GitHub/claude-code-bootstrap
```

### Command Not Allowed

If Claude can't run a command, add it to `allowedCommands` in `.mcp/config.json`:

```json
{
  "allowedCommands": [
    "existing-commands",
    "new-command"
  ]
}
```

## Integration with Claude Code Bootstrap

This MCP server configuration enhances the PROJECT.md-first autonomous development workflow:

1. **PROJECT.md Alignment**: Claude reads PROJECT.md to validate feature alignment with GOALS
2. **Orchestrator**: Access to git history and project structure for coordination
3. **Research**: Read existing code and documentation for pattern discovery
4. **Planning**: Access architecture and design decisions
5. **TDD**: Run tests via Python server (test-master agent)
6. **Implementation**: Write and modify code via filesystem server (implementer agent)
7. **Review**: Execute linters and quality checks (reviewer agent)
8. **Security**: Run security scans (security-auditor agent)
9. **Documentation**: Update docs automatically (doc-master agent)
10. **GitHub Integration**: Query milestones and issues (optional, via gh CLI)

## Example Workflow

```bash
# 1. Claude reads PROJECT.md
# (via filesystem server)

# 2. Checks current git status
# (via git server)

# 3. Creates feature branch
git checkout -b feature/new-feature

# 4. Writes tests
# (via filesystem server)

# 5. Runs tests
python -m pytest tests/

# 6. Implements feature
# (via filesystem server)

# 7. Runs tests again
python -m pytest tests/

# 8. Commits changes
git add .
git commit -m "feat: Add new feature"

# 9. Pushes to remote
git push origin feature/new-feature
```

## References

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Claude Desktop MCP Setup](https://docs.anthropic.com/claude/docs/model-context-protocol)
- [Project Documentation](../CLAUDE.md)

---

**Last Updated**: 2025-10-20
