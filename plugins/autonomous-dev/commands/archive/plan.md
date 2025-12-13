---
description: Architecture and implementation planning for a feature
argument-hint: Feature description (e.g., "user authentication with JWT")
---

# Architecture and Implementation Planning

Invoke the **planner agent** to design the architecture and implementation approach for a feature.

## Implementation

Invoke the planner agent with the user's feature description.

ARGUMENTS: {{ARGUMENTS}}

Use the Task tool to invoke the planner agent with subagent_type="planner" and provide the feature description from ARGUMENTS.

## What This Does

You describe a feature. The planner agent will:

1. Design the architecture and component structure
2. Plan the implementation approach and file organization
3. Identify dependencies and integration points
4. Provide a detailed implementation plan with steps

**Time**: 3-5 minutes (vs 20-30 min full pipeline)

## Usage

```bash
/plan user authentication with JWT tokens and refresh token rotation

/plan REST API for blog posts with CRUD, pagination, and full-text search

/plan rate limiting middleware with Redis backend
```

## Output

The planner provides:

- **Architecture Design**: Component structure and relationships
- **File Organization**: Which files to create/modify with locations
- **Implementation Steps**: Detailed step-by-step plan
- **Integration Points**: How feature connects to existing code
- **Dependencies**: Libraries and tools needed

## When to Use

Use `/plan` when you need:

- Architecture design before coding
- Understanding implementation complexity
- Clear plan to guide manual coding
- Review of approach before full implementation

## Next Steps

After planning, you can:

1. **Review plan** - Adjust approach if needed
2. **Generate tests** - Use `/test-feature <feature>` to write TDD tests
3. **Implement manually** - Follow the plan yourself
4. **Full pipeline** - Use `/auto-implement <feature>` for automated implementation

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/research` | 2-5 min | Research only |
| `/plan` | 3-5 min | Research + planning (this command) |
| `/test-feature` | 2-5 min | TDD test generation |
| `/auto-implement` | 20-30 min | Full pipeline (research → plan → test → implement → review → security → docs) |

## Technical Details

This command invokes the `planner` agent with:
- **Model**: Opus (high-quality planning)
- **Tools**: Read, Grep, Glob, Bash
- **Permissions**: Read-only (cannot modify code)

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/research`, `/test-feature`, `/implement`
