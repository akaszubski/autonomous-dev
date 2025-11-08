# Knowledge Base

**Purpose**: Persistent, organized knowledge storage for autonomous-dev plugin
**Location**: `.claude/knowledge/`
**Version**: 1.0

---

## Overview

This knowledge base stores **synthesized research** and **best practices** so agents don't re-research the same topics multiple times. It's a hybrid approach combining:

- **Persistent knowledge**: Organized by topic, not chronology
- **Session logs**: Chronological history in `docs/sessions/`
- **Cache**: Temporary web fetches in `.claude/cache/`

### Benefits

✅ **Avoids duplicate research** - Check INDEX first before web research
✅ **Faster agent startup** - Read 1 topic file vs 100 session logs
✅ **Lower costs** - Reuse cached web fetches
✅ **Better discoverability** - Find knowledge by topic, not timestamp
✅ **Scales** - 10,000 sessions won't slow down knowledge lookup

---

## Directory Structure

```
.claude/knowledge/
├── INDEX.md                    # Knowledge base index (read this first!)
├── README.md                   # This file
│
├── best-practices/             # Established industry standards
│   ├── claude-code-2.0.md     # Claude Code plugin development
│   └── [topic].md
│
├── patterns/                   # Recurring code patterns
│   ├── learned_patterns.json  # Machine-readable pattern database
│   └── [pattern-type].md
│
└── research/                   # Exploratory research findings
    └── [topic].md
```

---

## How It Works

### For Agents (Automated)

**Researcher Agent Workflow**:
1. Read `.claude/knowledge/INDEX.md` first
2. Check if topic already researched
3. If found: Reuse existing knowledge (skip duplicate research)
4. If not found: Research, then save to knowledge base

**Other Agents**:
- Can reference knowledge base for context
- Example: Planner reads `best-practices/testing-patterns.md` before designing tests

### For Humans (Manual)

**Browse knowledge**:
```bash
# See what's available
cat .claude/knowledge/INDEX.md

# Read specific topic
cat .claude/knowledge/best-practices/claude-code-2.0.md
```

**Add new knowledge** (manual entry):
```bash
# Create new best practices doc
vim .claude/knowledge/best-practices/github-actions.md

# Update INDEX
vim .claude/knowledge/INDEX.md
```

---

## Categories

### Best Practices

**What**: Established industry standards and proven approaches
**When**: After researching a topic and finding consensus
**Examples**:
- `claude-code-2.0.md` - Plugin development best practices
- `python-packaging.md` - Python project structure and setup
- `git-workflows.md` - Branch strategies, commit conventions

**Format**:
```markdown
# {Topic Title}

**Date Researched**: 2025-10-24
**Status**: Current
**Sources**: [list of URLs]

## Summary
{1-2 paragraphs}

## Best Practices
1. **{Practice}**: {rationale} (Source: {url})

## Security Considerations
...

## References
...
```

### Patterns

**What**: Recurring code patterns extracted from codebase or research
**When**: After identifying repeating implementations
**Examples**:
- `learned_patterns.json` - Machine-readable pattern database
- `agent-communication.md` - Inter-agent messaging patterns
- `testing-patterns.md` - Test organization and TDD workflows

**Format** (JSON):
```json
{
  "timestamp": "2025-10-24T12:00:00Z",
  "total_patterns": 100,
  "patterns": [
    {
      "pattern": "Artifact-based agent communication",
      "count": 15,
      "sources": "codebase",
      "learned_at": "2025-10-24T12:00:00Z",
      "relevance_score": 0.95
    }
  ]
}
```

### Research

**What**: Exploratory findings for emerging or uncertain topics
**When**: Initial research before establishing best practices
**Examples**:
- `mcp-server-integration.md` - MCP server options and tradeoffs
- `plugin-distribution.md` - Marketplace publishing strategies

**Lifecycle**: Research docs → Best Practices (when consensus emerges)

---

## Maintenance

### Lifecycle Rules

**Best Practices**:
- Review quarterly
- Mark as "Stale" if > 6 months old and technology changed
- Re-research if major version changes (e.g., Claude Code 3.0)

**Patterns**:
- Auto-expire if not accessed in 30 days
- Merge duplicates monthly
- Update relevance scores based on usage

**Research**:
- Archive to `best-practices/` when consensus emerges
- Delete drafts older than 14 days
- Mark as "Exploratory" if uncertain

**Cache** (`.claude/cache/`):
- Auto-expire web-fetch after 7 days
- Manual cleanup as needed

### Updating INDEX.md

Every time you add knowledge:
1. Add entry to appropriate section (Best Practices, Patterns, Research)
2. Update "Last Updated" timestamp
3. Update statistics section (document count, total size)

**Example**:
```markdown
### GitHub Actions Best Practices
**File**: `best-practices/github-actions.md`
**Date**: 2025-10-24
**Size**: 8KB
**Description**: CI/CD workflows for plugin development

**Topics Covered**:
- Automated testing
- Version bumping
- Marketplace publishing
```

---

## Cache System

### Web Fetch Cache

**Location**: `.claude/cache/web-fetch/`
**Purpose**: Avoid re-fetching same URLs
**Expiration**: 7 days

**Format**:
```markdown
# Cached Web Fetch

**URL**: https://example.com/article
**Fetched**: 2025-10-24T12:00:00Z
**Expires**: 2025-10-31T12:00:00Z

---

{fetched content}
```

### API Docs Cache

**Location**: `.claude/cache/api-docs/`
**Purpose**: Store frequently referenced API documentation
**Expiration**: Manual (API docs change infrequently)

---

## Statistics

Run to get current stats:
```bash
# Document counts
echo "Best Practices: $(ls .claude/knowledge/best-practices/*.md 2>/dev/null | wc -l)"
echo "Patterns: $(ls .claude/knowledge/patterns/*.md 2>/dev/null | wc -l)"
echo "Research: $(ls .claude/knowledge/research/*.md 2>/dev/null | wc -l)"

# Total size
du -sh .claude/knowledge/
```

---

## Comparison: Knowledge Base vs Session Logs

| Aspect | Knowledge Base | Session Logs |
|--------|---------------|--------------|
| **Organization** | By topic | By timestamp |
| **Discoverability** | Excellent (INDEX) | Poor (search needed) |
| **Synthesis** | Distilled knowledge | Raw logs |
| **Reusability** | High (check INDEX first) | Low (hard to find) |
| **Context Size** | Small (1 topic file) | Large (100+ sessions) |
| **Lifecycle** | Persistent, reviewed | Chronological, archived |
| **Use Case** | Find answers | Audit history |

**Recommendation**: Use both!
- **Knowledge base** for "What's our approach to X?"
- **Session logs** for "What did we do on Oct 24?"

---

## Example Workflow

### Scenario: Research "MCP server integration"

**Step 1: Check INDEX**
```bash
grep -i "mcp" .claude/knowledge/INDEX.md
# Result: Not found
```

**Step 2: Research (researcher agent)**
- WebSearch: "MCP server best practices 2025"
- WebFetch: Top 5 sources
- Synthesize findings

**Step 3: Save to knowledge base**
```bash
# Create research doc
.claude/knowledge/research/mcp-server-integration.md

# Update INDEX
vim .claude/knowledge/INDEX.md
# Add under "Research" section

# Cache web fetches
.claude/cache/web-fetch/{url_hash}.md
```

**Step 4: Reuse in future**
```bash
# 2 weeks later, another feature needs MCP research
grep -i "mcp" .claude/knowledge/INDEX.md
# Result: Found! Read existing knowledge instead of re-researching
```

**Cost savings**: 5-7 minutes research + API costs saved

---

## Best Practices for Knowledge Base

1. **Check INDEX first** - Always read before researching
2. **Update INDEX immediately** - Don't let it get stale
3. **Categorize correctly** - Best Practices vs Research vs Patterns
4. **Include sources** - Always link to original URLs
5. **Date everything** - Track when knowledge was researched
6. **Review quarterly** - Mark stale docs, archive old research
7. **Use cache** - Don't re-fetch same URLs
8. **Synthesize, don't dump** - Distill findings, not raw logs

---

## Integration with Plugin

The knowledge base is **part of the plugin** and will be:
- ✅ Included in `.claude/` directory
- ✅ Used automatically by researcher agent
- ✅ Available to all agents for context
- ✅ Synced to `plugins/autonomous-dev/` for distribution

---

## Future Enhancements

**Planned**:
- [ ] Automatic staleness detection (check source URLs)
- [ ] Knowledge base search command (`/kb-search "MCP server"`)
- [ ] Pattern extraction from codebase (automated)
- [ ] Web fetch cache auto-expiration (7-day cleanup)
- [ ] Knowledge versioning (track updates to docs)

---

## Questions?

- **How do I add knowledge manually?** Create `.md` file in appropriate category, update INDEX.md
- **How do agents use this?** Researcher reads INDEX first, reuses existing knowledge
- **What if knowledge is outdated?** Mark as "Stale" in INDEX, re-research and update
- **Do I need to maintain this?** Quarterly review recommended, otherwise automatic via researcher agent

---

**Last Updated**: 2025-10-24
**Version**: 1.0
