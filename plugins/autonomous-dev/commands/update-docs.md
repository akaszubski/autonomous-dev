---
name: update-docs
description: Documentation synchronization and updates
argument-hint: Optional - specific documentation area to update
allowed-tools: [Task, Read, Write, Edit, Grep, Glob]
---

# Documentation Synchronization

Invoke the **doc-master agent** to synchronize and update documentation.

## Implementation

Invoke the doc-master agent with optional focus area from user.

ARGUMENTS: {{ARGUMENTS}}

Use the Task tool to invoke the doc-master agent with subagent_type="doc-master" and provide any specific focus from ARGUMENTS (or update all docs if no argument provided).

## What This Does

The doc-master agent will:

1. Update README with new features and changes
2. Synchronize API documentation with code
3. Update CHANGELOG with recent changes
4. Ensure docstrings are accurate and complete

**Time**: 1-2 minutes (vs 20-30 min full pipeline)

## Usage

```bash
/update-docs

/update-docs API documentation for new auth endpoints

/update-docs README usage examples
```

## Output

The doc-master provides:

- **README Updates**: New features, usage examples
- **API Documentation**: Synchronized with actual code
- **CHANGELOG**: Recent changes documented
- **Docstrings**: Accurate function/class documentation

## When to Use

Use `/update-docs` when you need:

- Documentation sync after code changes
- Quick doc updates without full pipeline
- README updates for new features
- CHANGELOG entries for releases

## What Gets Updated

The doc-master updates:
- **README.md**: Project overview, installation, usage
- **API Docs**: Endpoint documentation, parameters, responses
- **CHANGELOG.md**: Version history, changes
- **Docstrings**: Function/class documentation in code
- **Examples**: Usage examples and code samples

## Next Steps

After documentation update, you can:

1. **Review docs** - Verify accuracy of updates
2. **Commit** - If docs look good, commit changes
3. **Full pipeline** - Use `/auto-implement <feature>` for complete workflow with docs

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/implement` | 5-10 min | Code implementation |
| `/review` | 2-3 min | Code quality review |
| `/security-scan` | 1-2 min | Security vulnerability scan |
| `/update-docs` | 1-2 min | Documentation sync (this command) |
| `/auto-implement` | 20-30 min | Full pipeline (research → plan → test → implement → review → security → docs) |

## Technical Details

This command invokes the `doc-master` agent with:
- **Model**: Haiku (fast documentation)
- **Tools**: Read, Write, Edit, Grep, Glob
- **Permissions**: Can write documentation files

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/review`, `/security-scan`, `/auto-implement`
