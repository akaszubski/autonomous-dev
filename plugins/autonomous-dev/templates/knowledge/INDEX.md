# Knowledge Base Index

**Last Updated**: 2025-10-24
**Purpose**: Persistent, organized knowledge for autonomous-dev plugin

---

## How to Use This Knowledge Base

### For Agents
Before researching a topic:
1. Read this INDEX to check if knowledge already exists
2. If found, read the specific file (avoids duplicate research)
3. If not found, research and save new findings here

### For Humans
- Browse by category below
- Each entry includes: topic, file path, date researched, brief description

---

## Best Practices

### Claude Code 2.0
**File**: `best-practices/claude-code-2.0.md`
**Date**: 2025-10-24
**Size**: 10KB
**Description**: Comprehensive best practices for Claude Code 2.0 plugin development including:
- Agent file format (frontmatter, tools, models)
- Skill creation (auto-activation, keywords)
- Hook configuration (lifecycle events, timeouts)
- Command structure (slash commands)
- Artifact-based communication patterns
- Tool restriction security patterns
- Model optimization (opus/sonnet/haiku)
- Common mistakes to avoid

**Topics Covered**:
- Agents, Skills, Commands, Hooks
- File format requirements
- Security best practices
- Context optimization
- Progressive enhancement patterns

---

## Patterns

*(No patterns extracted yet)*

**Planned**:
- `patterns/learned_patterns.json` - Machine-readable pattern database
- `patterns/agent-communication.md` - Inter-agent communication patterns
- `patterns/testing-patterns.md` - TDD and testing workflows

---

## Research

### Agent Search Strategies for Autonomous Development
**File**: `research/agent-search-strategies.md`
**Date**: 2025-10-24
**Size**: 54KB
**Description**: Comprehensive guide for implementing optimal searcher/researcher agents with knowledge base integration, covering search order optimization, codebase search strategies, web research best practices, caching mechanisms, and artifact-based communication patterns.

**Topics Covered**:
- Search order optimization (KB → Codebase → Web)
- Codebase search strategies (Grep, Glob, AST, embeddings)
- Web research query formulation and source prioritization
- Knowledge base management (freshness checks, duplicate detection)
- Artifact-based communication patterns
- Error handling and graceful degradation
- Performance targets and optimization techniques
- Context budget management
- Quality gates and validation
- Multi-agent coordination patterns

**Key Insights**:
- Knowledge base check reduces cost by 100x vs web research
- 5-8 sources optimal for web research (diminishing returns after)
- Artifact files use 200 tokens vs 5,000+ for context passing
- 7-day web cache reduces duplicate API calls
- Parallel tool execution improves speed 2-3x

**Planned**:
- `research/mcp-servers.md` - MCP server integration patterns
- `research/plugin-distribution.md` - Plugin marketplace best practices
- `research/github-actions.md` - CI/CD for plugin development

---

## Cache

**Web Fetch Cache**: `.claude/cache/web-fetch/`
- Cached URL fetches (7-day expiration)
- Reduces duplicate API calls

**API Docs Cache**: `.claude/cache/api-docs/`
- Cached API documentation
- Reduces web fetching overhead

---

## Maintenance

### Lifecycle Rules

**Best Practices**:
- Review quarterly
- Mark as stale if > 6 months old
- Re-research if technology version changes

**Patterns**:
- Auto-expire if not accessed in 30 days
- Merge duplicates monthly

**Research**:
- Archive completed topics to best-practices/
- Delete drafts older than 14 days

**Cache**:
- Auto-expire web-fetch after 7 days
- Manual cleanup as needed

---

## Statistics

- **Best Practices**: 1 document (10KB)
- **Patterns**: 0 documents
- **Research**: 1 document (54KB)
- **Cache Entries**: 0
- **Total Size**: 64KB
- **Last Updated**: 2025-10-24

---

## Quick Links

- [Claude Code 2.0 Best Practices](best-practices/claude-code-2.0.md)
- [Agent Search Strategies](research/agent-search-strategies.md)
- [Session Logs](../../docs/sessions/) - Chronological work history
- [PROJECT.md](../PROJECT.md) - Project goals and constraints
