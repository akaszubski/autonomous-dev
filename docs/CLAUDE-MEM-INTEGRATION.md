# claude-mem Integration Guide

This guide explains how to use [claude-mem](https://github.com/thedotmack/claude-mem) with autonomous-dev for persistent memory across Claude Code sessions.

## What is claude-mem?

claude-mem is a persistent memory plugin that:
- Automatically captures tool observations during sessions
- Compresses context with AI for efficient storage
- Injects relevant history into future sessions
- Provides vector search over past work

## Prerequisites

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Node.js | 18.0.0+ | `node --version` |
| Bun | Latest | `bun --version` |
| uv | Latest | `uv --version` |
| Port 37777 | Available | `/health-check` |

Run `/health-check` to validate all prerequisites.

## Installation

### 1. Install claude-mem

```bash
# Clone the repository
git clone https://github.com/thedotmack/claude-mem ~/.claude-mem

# Install dependencies
cd ~/.claude-mem
bun install

# Start worker service
bun run worker
```

### 2. Configure Hook Ordering

Both autonomous-dev and claude-mem use lifecycle hooks. Configure execution order in your `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {"type": "command", "command": "~/.claude-mem/hooks/session-start.sh"},
          {"type": "command", "command": "python3 ~/.claude/hooks/unified_session_tracker.py"}
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {"type": "command", "command": "~/.claude-mem/hooks/post-tool.sh"},
          {"type": "command", "command": "python3 ~/.claude/hooks/unified_post_tool.py"}
        ]
      }
    ]
  }
}
```

**Order matters**: claude-mem hooks typically run first to capture observations, then autonomous-dev hooks process results.

### 3. Validate Installation

```bash
# Check prerequisites
/health-check

# Search memory (should return empty if new)
/mem-search test
```

## Usage

### Search Past Observations

```bash
# Search for patterns
/mem-search "authentication"

# Find error solutions
/mem-search "error handling database"

# Recall file changes
/mem-search "config.json"
```

### Web UI

Access the claude-mem web interface at http://localhost:37777 when the worker is running.

Features:
- Browse observation timeline
- Search with filters
- View compressed context
- Manage memory settings

### MCP Tools

If you have MCP configured, these tools are available:

| Tool | Description |
|------|-------------|
| `search_observations` | Semantic search over observations |
| `get_timeline` | Get observations in time order |
| `get_recent_context` | Get most recent relevant context |

## Hook Coordination

### How It Works

1. **SessionStart**: claude-mem loads relevant history, autonomous-dev initializes state
2. **PostToolUse**: claude-mem captures observation, autonomous-dev processes result
3. **SessionEnd**: claude-mem compresses and stores context

### Avoiding Conflicts

Both plugins can coexist because:
- They use different storage backends (claude-mem: SQLite/Chroma, autonomous-dev: JSON)
- Hook execution is sequential, not parallel
- Each plugin processes its own concerns

### Troubleshooting Hook Issues

If hooks conflict:

1. Check hook execution order in settings.local.json
2. Verify both services are running
3. Check logs: `~/.claude-mem/logs/` and `~/.claude/logs/`

## Data Storage

| System | Location | Purpose |
|--------|----------|---------|
| claude-mem | `~/.claude-mem/data/` | SQLite DB + Chroma vectors |
| autonomous-dev | `~/.claude/local/` | Session state, memory layer |

**Important**: These are separate systems. Data doesn't migrate between them.

## Comparison

| Feature | claude-mem | autonomous-dev memory |
|---------|------------|----------------------|
| Storage | SQLite + Chroma | JSON files |
| Search | Vector semantic | Keyword |
| Compression | AI-powered | Manual |
| Scope | Cross-project | Per-project |
| UI | Web interface | None |

## When to Use Each

**Use claude-mem for**:
- Long-term memory across projects
- Semantic search ("find similar problems")
- Compressed historical context

**Use autonomous-dev memory for**:
- Session-specific state
- Pipeline tracking
- Project-specific conventions

## Security Considerations

1. **Port 37777**: Localhost-only by default
2. **Data location**: User-controlled in `~/.claude-mem/`
3. **Privacy tags**: Use `<private>` tags to exclude sensitive content
4. **License**: AGPL-3.0 (ragtime/ under PolyForm Noncommercial)

## Troubleshooting

### Worker Not Starting

```bash
cd ~/.claude-mem
bun run worker

# If port in use:
lsof -i :37777
kill <PID>
bun run worker
```

### No Search Results

1. Verify worker is running: `curl http://localhost:37777/health`
2. Check database exists: `ls ~/.claude-mem/data/`
3. Ensure hooks are capturing: Check `~/.claude-mem/logs/`

### Hook Execution Failures

```bash
# Test hooks manually
~/.claude-mem/hooks/session-start.sh
~/.claude-mem/hooks/post-tool.sh

# Check autonomous-dev hooks
python3 ~/.claude/hooks/unified_session_tracker.py
```

### Prerequisites Missing

```bash
# Install Node.js 18+
# macOS
brew install node@18

# Install Bun
curl -fsSL https://bun.sh/install | bash

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Related

- [claude-mem GitHub](https://github.com/thedotmack/claude-mem)
- [autonomous-dev docs](docs/)
- [Issue #327](https://github.com/akaszubski/autonomous-dev/issues/327)

---

**Last Updated**: 2026-02-06
