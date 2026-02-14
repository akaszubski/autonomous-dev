# Progressive Disclosure Usage

How to leverage Claude Code 2.0+ progressive disclosure architecture for optimal context management.

## What is Progressive Disclosure?

**Progressive disclosure** is a context optimization pattern where:
1. **Skill metadata** stays in base context (YAML frontmatter, ~50 tokens)
2. **Full content** loads on-demand when skill is referenced (docs/templates/examples)
3. **Context stays lightweight** until specific knowledge is needed

## How It Works

### Traditional Approach (Without Progressive Disclosure)
```
Agent context: 25,000 tokens
- Agent prompt: 1,500 tokens
- Inline skill content: 20,000 tokens (10+ skills × 2,000 tokens each)
- Other context: 3,500 tokens

Result: Context bloat, slow responses, limited scalability
```

### Progressive Disclosure Approach
```
Agent context: 8,000 tokens
- Agent prompt: 1,500 tokens
- Skill metadata: 500 tokens (10+ skills × 50 tokens each)
- Loaded skills: 3,000 tokens (1-2 skills loaded on-demand)
- Other context: 3,000 tokens

Result: Lightweight context, fast responses, scales to 100+ skills
```

## When to Reference Skills

### Always Reference (Not Inline)
- **Code standards** - python-standards, javascript-standards
- **Architecture patterns** - architecture-patterns, api-design
- **Testing guidance** - testing-guide, coverage-strategies
- **Documentation templates** - documentation-guide, docstring-standards

### Can Be Inline (Small, Agent-Specific)
- **Agent-specific instructions** - Unique to this agent's workflow
- **Critical safety rules** - Must always be visible (e.g., "never delete user data")
- **Short reminders** - <100 tokens, not reusable across agents

## Skill Activation Keywords

Skills auto-activate based on task keywords in agent prompts or user queries:

### Common Keywords
- **architecture-patterns**: architecture, design, patterns, scalability, ADR
- **testing-guide**: test, TDD, pytest, coverage, unittest
- **python-standards**: python, PEP, typing, docstring, black
- **security-patterns**: security, OWASP, vulnerability, threat, auth
- **api-design**: api, endpoint, REST, GraphQL, versioning
- **documentation-guide**: docs, readme, docstring, changelog

### Custom Keywords
When creating skills, add relevant keywords to YAML frontmatter:
```yaml
keywords:
  - skill-reference
  - agent-skills
  - progressive-disclosure
```

## Best Practices

### 1. Keep Agent Prompts Lightweight
**Do**: Reference skills for reusable knowledge
```markdown
## Relevant Skills

- **python-standards**: Follow for code style and type hints
```

**Don't**: Duplicate skill content inline
```markdown
## Code Standards

Python code must follow PEP 8. Use black for formatting.
Type hints are required for all public APIs.
Docstrings must follow Google style...
[500+ tokens of duplicated content]
```

### 2. Reference Meta-Skills
Point to integration guidance for consistent formatting:
```markdown
Consult the skill-integration-templates skill for formatting guidance.
```

### 3. Use Specific Skill References
**Do**: Reference specific skills for targeted loading
```markdown
- **testing-guide**: Reference for TDD implementation patterns
```

**Don't**: Generic references that don't trigger activation
```markdown
- Use the testing documentation for guidance
```

### 4. Balance Skill References vs. Agent Uniqueness
**Agent-Specific** (Keep Inline):
```markdown
## Your Mission

As the implementer agent, your job is to make tests pass by writing minimal,
focused code that satisfies test requirements.
```

**Reusable Knowledge** (Reference Skill):
```markdown
## Relevant Skills

- **python-standards**: Follow for code conventions
```

## Context Budget Management

### Measuring Context Usage
```python
# Estimate context tokens
agent_prompt_tokens = count_tokens("agent.md")
skill_metadata_tokens = count_tokens("SKILL.md frontmatter")
loaded_skill_tokens = count_tokens("SKILL.md full content")

total_context = agent_prompt_tokens + skill_metadata_tokens + loaded_skill_tokens
```

### Optimization Targets
- **Agent prompt**: <2,000 tokens (concise, references skills)
- **Skill metadata**: <50 tokens per skill (lightweight frontmatter)
- **Loaded skills**: <3,000 tokens (1-2 skills on-demand)
- **Total context**: <8,000 tokens (optimal performance)

### Context Bloat Warning Signs
- Agent prompts >2,500 tokens
- Multiple skills fully loaded when not needed
- Duplicated content across agent prompts
- Inline guidance that could be skill-based

## Progressive Disclosure Patterns

### Pattern 1: Single Skill Reference
```markdown
## Relevant Skills

Reference the **testing-guide** skill for TDD patterns and coverage strategies.
```

### Pattern 2: Multiple Skill References
```markdown
## Relevant Skills

- **architecture-patterns**: Apply for system design
- **api-design**: Follow for endpoint structure
- **database-design**: Use for schema planning
```

### Pattern 3: Conditional Skill References
```markdown
## Relevant Skills

When planning database changes, consult the **database-design** skill for normalization and indexing patterns.
```

### Pattern 4: Meta-Skill References
```markdown
See skill-integration-templates skill for how to structure skill references.
```

## Scaling to 100+ Skills

Progressive disclosure enables massive skill libraries:

### Without Progressive Disclosure
- **Limit**: ~10-15 skills before context bloat
- **Context**: 20,000-30,000 tokens (all skills loaded)
- **Performance**: Slow, high token costs

### With Progressive Disclosure
- **Limit**: 100+ skills (metadata only)
- **Context**: 8,000-10,000 tokens (1-2 skills loaded on-demand)
- **Performance**: Fast, low token costs

## Examples

### Research Agent (3 Skills Referenced)
```markdown
## Relevant Skills

- **research-patterns**: Consult for search strategies
- **architecture-patterns**: Reference for design patterns
- **testing-guide**: Use for test planning

See skill-integration-templates skill for formatting.
```

**Context Impact**:
- Metadata: 150 tokens (3 skills × 50)
- Loaded on-demand: 2,000-3,000 tokens (when referenced)
- Total: <3,500 tokens vs. 6,000+ inline

### Implementer Agent (5 Skills Referenced)
```markdown
## Relevant Skills

- **python-standards**: Follow for code style
- **testing-guide**: Reference for TDD
- **security-patterns**: Check for vulnerabilities
- **observability**: Use for logging
- **error-handling-patterns**: Apply for error handling

See skill-integration-templates skill for formatting.
```

**Context Impact**:
- Metadata: 250 tokens (5 skills × 50)
- Loaded on-demand: 3,000-4,000 tokens (when referenced)
- Total: <4,500 tokens vs. 10,000+ inline

## Related Documentation

- `skill-reference-syntax.md` - Syntax patterns for references
- `integration-best-practices.md` - Integration guidelines
- `agent-action-verbs.md` - Action verb selection
