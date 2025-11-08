---
description: Code quality review and feedback
argument-hint: Optional - specific file or component to review
---

# Code Quality Review

Invoke the **reviewer agent** to perform code quality review and provide feedback.

## Implementation

Invoke the reviewer agent with optional focus area from user.

ARGUMENTS: {{ARGUMENTS}}

Use the Task tool to invoke the reviewer agent with subagent_type="reviewer" and provide any specific focus from ARGUMENTS (or review recent changes if no argument provided).

## What This Does

The reviewer agent will:

1. Review code quality and patterns
2. Check for consistency with codebase conventions
3. Identify potential issues and improvements
4. Provide constructive feedback with examples

**Time**: 2-3 minutes (vs 20-30 min full pipeline)

## Usage

```bash
/review

/review src/auth/jwt.py

/review recent authentication changes
```

## Output

The reviewer provides:

- **Code Quality Assessment**: Overall quality rating
- **Issues Found**: Specific problems with locations
- **Recommendations**: How to improve code
- **Best Practices**: Pattern suggestions

## When to Use

Use `/review` when you need:

- Quality check after manual coding
- Second pair of eyes on implementation
- Consistency verification with codebase
- Feedback before committing

## What Gets Reviewed

The reviewer checks:
- **Code Quality**: Clean, maintainable, readable
- **Patterns**: Follows existing conventions
- **Error Handling**: Proper error management
- **Performance**: No obvious performance issues
- **Testing**: Test coverage and quality

## Next Steps

After review, you can:

1. **Fix issues** - Address feedback provided
2. **Security scan** - Use `/security-scan` for vulnerabilities
3. **Update docs** - Use `/update-docs` if API changed
4. **Commit** - If review passes, commit changes

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/implement` | 5-10 min | Code implementation |
| `/review` | 2-3 min | Code quality review (this command) |
| `/security-scan` | 1-2 min | Security vulnerability scan |
| `/update-docs` | 1-2 min | Documentation sync |
| `/auto-implement` | 20-30 min | Full pipeline (research → plan → test → implement → review → security → docs) |

## Technical Details

This command invokes the `reviewer` agent with:
- **Model**: Sonnet (balanced speed/quality)
- **Tools**: Read, Grep, Glob, Bash
- **Permissions**: Read-only (cannot modify code)

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/implement`, `/security-scan`, `/update-docs`
