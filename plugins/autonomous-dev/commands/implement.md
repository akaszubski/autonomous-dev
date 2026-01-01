---
name: implement
description: Code implementation to make tests pass
argument-hint: Feature description (e.g., "implement rate limiting")
allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob]
---

# Code Implementation

Invoke the **implementer agent** to write code that makes tests pass.

## Implementation

Invoke the implementer agent with the user's feature description.

ARGUMENTS: {{ARGUMENTS}}

Use the Task tool to invoke the implementer agent with subagent_type="implementer" and provide the feature description from ARGUMENTS.

## What This Does

You describe a feature. The implementer agent will:

1. Write code to make failing tests pass (TDD approach)
2. Follow existing code patterns and conventions
3. Implement clean, maintainable code
4. Ensure all tests pass after implementation

**Time**: 5-10 minutes (vs 20-30 min full pipeline)

## Usage

```bash
/implement rate limiting with Redis backend

/implement JWT authentication with token refresh

/implement blog post CRUD API endpoints
```

## Output

The implementer provides:

- **Working Code**: Implementation that makes tests pass
- **Pattern Compliance**: Follows existing codebase conventions
- **Clean Implementation**: Maintainable, readable code
- **Test Coverage**: All tests passing

## When to Use

Use `/implement` when you need:

- Code generation after tests are written
- Implementation without full pipeline overhead
- Quick feature implementation
- Following TDD workflow (tests already exist)

## Prerequisites

For best results:
1. Tests should already exist (use `/test-feature` or write manually)
2. Have a plan (use `/plan` or know the approach)

If no tests exist, the implementer will still work but may not follow TDD.

## Next Steps

After implementation, you can:

1. **Review code** - Use `/review` for quality check
2. **Security scan** - Use `/security-scan` for vulnerabilities
3. **Update docs** - Use `/update-docs` for documentation
4. **Full pipeline** - Use `/auto-implement <feature>` for complete workflow

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/research` | 2-5 min | Research only |
| `/plan` | 3-5 min | Research + planning |
| `/test-feature` | 2-5 min | TDD test generation |
| `/implement` | 5-10 min | Code implementation (this command) |
| `/review` | 2-3 min | Code quality review |
| `/auto-implement` | 20-30 min | Full pipeline (research → plan → test → implement → review → security → docs) |

## Technical Details

This command invokes the `implementer` agent with:
- **Model**: Sonnet (balanced speed/quality)
- **Tools**: Read, Write, Edit, Grep, Glob, Bash
- **Permissions**: Can write code and run tests

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/test-feature`, `/review`, `/security-scan`
