---
description: TDD test generation for a feature
argument-hint: Feature description (e.g., "rate limiting tests")
---

# TDD Test Generation

Invoke the **test-master agent** to write comprehensive TDD tests for a feature.

## Implementation

Invoke the test-master agent with the user's feature description.

ARGUMENTS: {{ARGUMENTS}}

Use the Task tool to invoke the test-master agent with subagent_type="test-master" and provide the feature description from ARGUMENTS.

## What This Does

You describe a feature. The test-master agent will:

1. Write comprehensive unit tests (TDD - tests FIRST)
2. Create integration tests for workflows
3. Add edge case and error handling tests
4. Ensure tests FAIL initially (ready for implementation)

**Time**: 2-5 minutes (vs 20-30 min full pipeline)

## Usage

```bash
/test-feature rate limiting with sliding window

/test-feature JWT authentication with token refresh

/test-feature blog post CRUD API with pagination
```

## Output

The test-master provides:

- **Unit Tests**: Core logic tests
- **Integration Tests**: Workflow and system tests
- **Edge Cases**: Boundary conditions and error handling
- **Test Coverage**: Comprehensive test suite (80%+ target)

All tests will FAIL initially (TDD approach - write tests before code).

## When to Use

Use `/test-feature` when you need:

- Tests written before implementation (TDD)
- Comprehensive test coverage planning
- Test suite for manual implementation
- Quick test generation without full pipeline

## Next Steps

After test generation, you can:

1. **Review tests** - Ensure tests cover requirements
2. **Implement feature** - Use `/implement <feature>` to make tests pass
3. **Manual coding** - Write code yourself to make tests pass
4. **Full pipeline** - Use `/auto-implement <feature>` for complete workflow

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/research` | 2-5 min | Research only |
| `/plan` | 3-5 min | Research + planning |
| `/test-feature` | 2-5 min | TDD test generation (this command) |
| `/implement` | 5-10 min | Code implementation |
| `/auto-implement` | 20-30 min | Full pipeline (research → plan → test → implement → review → security → docs) |

## Technical Details

This command invokes the `test-master` agent with:
- **Model**: Sonnet (balanced speed/quality)
- **Tools**: Read, Write, Edit, Grep, Glob, Bash
- **Permissions**: Can write test files only

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/plan`, `/implement`, `/auto-implement`
