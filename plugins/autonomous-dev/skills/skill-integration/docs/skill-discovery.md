# Skill Discovery

How agents automatically discover and activate relevant skills based on task keywords.

## Overview

Skill discovery is the mechanism by which Claude Code 2.0+ determines which skills to load when processing a task. This happens automatically through keyword matching between the task description and skill metadata.

## Keyword Matching

### How It Works

1. **Skill registration**: Each skill defines keywords in its SKILL.md frontmatter
2. **Task analysis**: Claude analyzes the task description for keywords
3. **Automatic activation**: Skills with matching keywords auto-load
4. **Progressive disclosure**: Only matching skills' full content loads into context

### Example

**Skill definition (testing-guide/SKILL.md):**
```yaml
---
name: testing-guide
keywords: test, testing, pytest, tdd, coverage, fixture, unittest
auto_activate: true
---
```

**Task triggers:**
- "Write tests for authentication" → matches "test", "testing"
- "Add pytest fixtures for database" → matches "pytest", "fixture"
- "Improve test coverage to 90%" → matches "testing", "coverage"
- "Follow TDD for new feature" → matches "tdd", "test"

**Result**: testing-guide skill content loads automatically

## Auto-Activation

### Enabling Auto-Activation

Skills must opt-in to automatic discovery:

```yaml
---
name: my-skill
keywords: keyword1, keyword2, keyword3
auto_activate: true  # Required for automatic discovery
---
```

**Without `auto_activate: true`**: Skill must be manually referenced by agents

### When to Use Auto-Activation

✅ **Use auto-activate for:**
- General-purpose skills (testing, code style, security)
- Skills with clear keyword triggers
- Skills that apply to many tasks

❌ **Don't use auto-activate for:**
- Highly specialized skills (used once per project)
- Skills that conflict with others
- Skills that should only load on explicit request

## Keyword Strategy

### Choosing Good Keywords

**Effective keywords:**
- Specific to skill domain
- Common in task descriptions
- Unambiguous (not overloaded terms)
- Cover synonyms and variations

**Example: testing-guide**
```yaml
keywords: test, testing, pytest, tdd, coverage, fixture, unittest, integration test, unit test
```

**Covers:**
- Direct mentions: "test", "testing"
- Tools: "pytest", "unittest"
- Methodologies: "tdd"
- Concepts: "coverage", "fixture"
- Variations: "unit test", "integration test"

### Avoiding Keyword Conflicts

**Bad keywords (too broad):**
```yaml
# ❌ Don't use overly generic keywords
keywords: code, program, software, development
# These match almost every task!
```

**Good keywords (specific):**
```yaml
# ✅ Use domain-specific keywords
keywords: authentication, jwt, oauth, token, session, login
# These clearly indicate authentication-related tasks
```

## Manual Discovery

### Explicit Skill References

Agents can explicitly list relevant skills in their prompts:

```markdown
## Relevant Skills

You have access to these specialized skills:

- **testing-guide**: Pytest patterns, TDD workflow, coverage
- **python-standards**: Code style, type hints, docstrings
- **security-patterns**: Input validation, authentication
```

**Benefits:**
- Agent knows which skills are available for its domain
- User sees what specialized knowledge agent can access
- Helps agent make better decisions about skill consultation

**Trigger**: Skill loads when agent's task is invoked, regardless of task keywords

## Discovery Priority

### Multiple Matching Skills

When multiple skills match task keywords, all matching skills load:

**Example task**: "Write secure API tests with pytest"

**Matches:**
1. testing-guide (keywords: test, pytest)
2. security-patterns (keywords: secure, security)
3. api-design (keywords: api)

**Result**: All three skills' content available to agent

### Load Order

Skills load in this order:
1. **Agent-referenced skills**: Explicitly listed in agent's "Relevant Skills"
2. **Auto-activated skills**: Matched by task keywords
3. **Transitive skills**: Referenced by other loaded skills

## Performance Optimization

### Metadata vs Full Content

**Always in context (minimal tokens):**
```yaml
---
name: testing-guide
type: knowledge
description: Comprehensive pytest patterns, TDD workflow, coverage strategies
keywords: test, testing, pytest, tdd, coverage
auto_activate: true
---
```

**Tokens**: ~50 tokens

**Loaded on-demand (significant tokens):**
```markdown
# Testing Guide Skill

[5,000+ words of testing guidance]
```

**Tokens**: ~5,000 tokens

**Total cost:**
- Metadata for 100 skills: 5,000 tokens (always in context)
- Full content: Only loads when needed

### Context Budget Impact

**Without progressive disclosure:**
```
20 skills × 500 tokens/skill = 10,000 tokens
Agent can't start work until all skills loaded
```

**With progressive disclosure:**
```
20 skills × 50 tokens/skill metadata = 1,000 tokens
+ 2-3 matching skills × 5,000 tokens = 10,000 tokens
Total: 11,000 tokens (only relevant skills loaded)
```

## Best Practices

### For Skill Authors

✅ **Do:**
- Choose specific, relevant keywords
- Enable auto-activate for general-purpose skills
- Keep metadata concise (name, description, keywords)
- Test keyword matching with real tasks

❌ **Don't:**
- Use overly generic keywords (e.g., "code", "development")
- Include keyword list in skill content (redundant)
- Rely only on auto-activation (agents should explicitly reference too)
- Create keyword conflicts with other skills

### For Agent Authors

✅ **Do:**
- Explicitly list relevant skills in agent prompt
- Trust skill discovery mechanism
- Use concise skill references (~150 tokens)
- Let skills provide detailed guidance

❌ **Don't:**
- Duplicate skill content in agent prompt
- List all 21 skills (redundant)
- Provide conflicting guidance to skills
- Assume users know which skills exist

## Troubleshooting

### Skill Not Loading

**Problem**: Skill should match task but doesn't load

**Debugging:**
1. Check `auto_activate: true` in SKILL.md frontmatter
2. Verify keywords match task description terms
3. Check for typos in keywords
4. Test with direct keyword mention in task

### Wrong Skill Loading

**Problem**: Skill loads for unrelated tasks

**Solution:**
1. Review keyword list for overly broad terms
2. Make keywords more specific
3. Consider removing auto-activate (manual reference only)
4. Add more context to skill description

### Performance Issues

**Problem**: Too many skills loading, context bloated

**Solution:**
1. Review keywords for overlaps between skills
2. Make keywords more specific to reduce false matches
3. Consider disabling auto-activate for rarely-used skills
4. Use explicit agent references instead of auto-activation

## Examples

### Example 1: testing-guide Discovery

**Skill metadata:**
```yaml
---
name: testing-guide
keywords: test, testing, pytest, tdd, coverage, fixture
auto_activate: true
---
```

**Tasks that trigger:**
- ✅ "Write tests for user service"
- ✅ "Add pytest fixtures for database"
- ✅ "Improve test coverage to 90%"
- ✅ "Follow TDD for authentication"
- ❌ "Deploy to production" (no keyword match)
- ❌ "Update documentation" (no keyword match)

### Example 2: security-patterns Discovery

**Skill metadata:**
```yaml
---
name: security-patterns
keywords: security, secure, authentication, authorization, encryption, validation, xss, sql injection, owasp
auto_activate: true
---
```

**Tasks that trigger:**
- ✅ "Implement secure JWT authentication"
- ✅ "Add input validation for user data"
- ✅ "Fix SQL injection vulnerability"
- ✅ "Review code for security issues"
- ❌ "Format code with black" (no keyword match)
- ❌ "Write unit tests" (no keyword match)

### Example 3: Multi-Skill Discovery

**Task**: "Write secure API tests with pytest coverage"

**Matching skills:**
1. **testing-guide** (matches: tests, pytest, coverage)
2. **security-patterns** (matches: secure)
3. **api-design** (matches: api)

**Result**: All three skills load automatically, agent has comprehensive guidance

## Integration with Agent Prompts

### Recommended Pattern

```markdown
## Relevant Skills

You have access to these specialized skills when implementing features:

- **python-standards**: Code style, type hints, docstring conventions
- **testing-guide**: Pytest patterns, TDD workflow, coverage strategies
- **security-patterns**: Input validation, secure coding practices

**Note**: Skills load automatically based on task keywords. Consult skills for detailed guidance on specific patterns.
```

**Why this works:**
- Agent knows which skills are available
- User sees specialized knowledge accessible
- Progressive disclosure still applies (metadata in context, content on-demand)
- Trust skill discovery for other relevant skills

## Summary

Skill discovery enables:
- **Automatic activation**: Skills load based on task keywords
- **Progressive disclosure**: Only relevant skills' full content loads
- **Scalability**: Support 100+ skills without context bloat
- **Flexibility**: Both automatic and manual discovery supported

**Key principles:**
- Choose specific, relevant keywords
- Enable auto-activate for general-purpose skills
- Trust the discovery mechanism
- Let progressive disclosure handle performance
