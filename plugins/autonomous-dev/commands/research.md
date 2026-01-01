---
name: research
description: Research patterns and best practices for a feature
argument-hint: Feature description (e.g., "JWT authentication patterns")
allowed-tools: [Task, Read, Grep, Glob, WebSearch, WebFetch]
---

# Research Patterns and Best Practices

Invoke the **researcher agent** to find patterns, best practices, and security considerations for a feature.

## Implementation

Invoke the researcher agent with the user's feature description.

ARGUMENTS: {{ARGUMENTS}}

Use the Task tool to invoke the researcher agent with subagent_type="researcher" and provide the feature description from ARGUMENTS.

## What This Does

You describe a feature or technology. The researcher agent will:

1. Search the codebase for similar existing implementations
2. Find official documentation and current best practices
3. Identify security considerations and common pitfalls
4. Recommend libraries, approaches, and patterns

**Time**: 2-5 minutes (vs 20-30 min full pipeline)

## Usage

```bash
/research JWT authentication patterns

/research rate limiting with Redis and sliding window

/research full-text search with PostgreSQL vs Elasticsearch
```

## Output

The researcher provides:

- **Codebase Patterns**: Existing code with file:line references
- **Best Practices**: Industry standards with authoritative sources
- **Security Considerations**: Critical security requirements
- **Recommendations**: Preferred approach with rationale

## When to Use

Use `/research` when you need:

- Quick research without full implementation
- Context before making architecture decisions
- Understanding of existing patterns in your codebase
- Comparison of different approaches

## Next Steps

After research, you can:

1. **Review findings** - Decide if you want to proceed
2. **Plan implementation** - Use `/plan <feature>` to design approach
3. **Full pipeline** - Use `/auto-implement <feature>` if you want everything done

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/research` | 2-5 min | Research only (this command) |
| `/plan` | 3-5 min | Research + planning |
| `/auto-implement` | 20-30 min | Full pipeline (research → plan → test → implement → review → security → docs) |

## Technical Details

This command invokes the `researcher` agent with:
- **Model**: Sonnet (balanced speed/quality)
- **Tools**: WebSearch, WebFetch, Read, Grep, Glob
- **Permissions**: Read-only (cannot modify code)

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/plan`, `/auto-implement`
