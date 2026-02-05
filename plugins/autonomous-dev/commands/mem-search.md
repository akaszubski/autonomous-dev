---
name: mem-search
description: Search past observations and context from claude-mem persistent memory
argument-hint: Search query (e.g., "authentication patterns" or "error handling")
allowed-tools: [Bash, Read]
---

# Search claude-mem Persistent Memory

Search past observations, context, and tool outputs captured by the [claude-mem](https://github.com/thedotmack/claude-mem) persistent memory plugin.

## Prerequisites

This command requires claude-mem to be installed and running:

1. **Install claude-mem**: See https://github.com/thedotmack/claude-mem
2. **Worker service running**: Should be on port 37777
3. **Validate**: Run `/health-check` to verify prerequisites

## Implementation

ARGUMENTS: {{ARGUMENTS}}

### Step 1: Check claude-mem availability

First, verify claude-mem is installed and the worker is running:

```bash
# Check if claude-mem directory exists
if [ ! -d ~/.claude-mem ]; then
    echo "ERROR: claude-mem not installed"
    echo "Install from: https://github.com/thedotmack/claude-mem"
    exit 1
fi

# Check if worker is running on port 37777
if ! curl -s http://localhost:37777/health > /dev/null 2>&1; then
    echo "WARNING: claude-mem worker may not be running"
    echo "Start with: cd ~/.claude-mem && bun run worker"
fi
```

### Step 2: Search using MCP tools

If the MCP server `claude-mem` is available, use its search tool:

```
mcp__claude-mem__search_observations(query="ARGUMENTS")
```

### Step 3: Alternative - Direct database query

If MCP is not available, query the SQLite database directly:

```bash
sqlite3 ~/.claude-mem/data/memory.db "
SELECT timestamp, content
FROM observations
WHERE content LIKE '%QUERY%'
ORDER BY timestamp DESC
LIMIT 20
"
```

Replace `QUERY` with the search term from ARGUMENTS.

### Step 4: Display results

Format and display the search results:

- Show timestamp and content for each match
- Highlight relevance to the query
- Provide file references if available

## What This Does

The claude-mem plugin captures tool observations throughout your sessions:

- **Tool outputs**: Results from Bash, Read, Write, etc.
- **Context**: Surrounding conversation and file contents
- **Timestamps**: When each observation was made

This command searches that history to:
- Find relevant past work
- Recall solutions to similar problems
- Understand project history

## Usage

```bash
# Search for authentication patterns
/mem-search authentication

# Find error handling approaches
/mem-search "error handling"

# Look for specific file mentions
/mem-search config.json

# Search for recent changes
/mem-search "git commit"
```

## Output

Search returns:
- **Timestamp**: When the observation was captured
- **Content**: The tool output or context
- **Relevance**: How closely it matches your query

## Troubleshooting

### claude-mem not found
```
Install from: https://github.com/thedotmack/claude-mem
```

### Worker not running
```
cd ~/.claude-mem && bun run worker
```

### No results found
- Try broader search terms
- Check if claude-mem has been running during relevant sessions
- Verify database exists: `ls ~/.claude-mem/data/`

## Related

- **claude-mem**: https://github.com/thedotmack/claude-mem
- **/health-check**: Validates claude-mem prerequisites
- **Web UI**: http://localhost:37777 (when worker is running)

---

**Part of**: claude-mem integration (GitHub #327)
**Related**: `/health-check`
