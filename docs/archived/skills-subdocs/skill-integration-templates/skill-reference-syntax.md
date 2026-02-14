# Skill Reference Syntax

This document defines standardized syntax patterns for referencing skills in agent prompts.

## Basic Syntax

### Single Skill Reference
```markdown
## Relevant Skills

You have access to the **[skill-name]** skill for [purpose].
```

### Multiple Skill References
```markdown
## Relevant Skills

You have access to these specialized skills when [context]:

- **[skill-name]**: [Action verb] [purpose] for [use case]
- **[skill-name]**: [Action verb] [purpose] for [use case]
```

## Formatting Patterns

### Bullet List Format (Recommended)
Use for 2+ skills. Provides clear scanability and consistent structure.

```markdown
## Relevant Skills

- **skill-name**: Concise purpose statement
- **skill-name**: Concise purpose statement
```

### Paragraph Format
Use for single skill or when context requires prose.

```markdown
## Relevant Skills

When [condition], consult the **skill-name** skill for [specific guidance].
```

## Action Verb Selection

Choose action verbs based on agent type and context:

- **Research agents**: "Consult", "Reference", "Use"
- **Planning agents**: "Apply", "Leverage", "Integrate"
- **Implementation agents**: "Follow", "Adhere to", "Use"
- **Review agents**: "Validate against", "Check using", "Compare with"

See `agent-action-verbs.md` for complete verb taxonomy.

## Progressive Disclosure Integration

Reference skills to trigger progressive disclosure (on-demand loading):

```markdown
## Relevant Skills

- **architecture-patterns**: Use for system design decisions
- **testing-guide**: Consult for test strategy planning

See skill-integration-templates skill for formatting guidance.
```

When skills are referenced, Claude Code loads full content only when needed, keeping base context lightweight.

## Examples

### Good Syntax (Concise, Clear)
```markdown
## Relevant Skills

You have access to these specialized skills during implementation:

- **python-standards**: Follow for code style and conventions
- **testing-guide**: Reference for TDD implementation

Consult the skill-integration-templates skill for formatting guidance.
```

### Bad Syntax (Verbose, Redundant)
```markdown
## Relevant Skills

You have access to a number of specialized skills that can help you during the implementation phase:

- **python-standards**: This skill contains comprehensive Python coding standards and conventions
  - Use this skill when you need to check code style
  - Reference this skill for naming conventions
  - Apply this skill for documentation standards

- **testing-guide**: This skill provides detailed testing guidance
  - Use when writing tests
  - Reference for test patterns
  - Apply for coverage strategies

When integrating skills:
1. Read the skill documentation first
2. Apply patterns consistently
3. Reference skills instead of duplicating content
```

**Why Bad**: Verbose descriptions (30+ tokens per skill), duplicated guidance, excessive structure.

## Best Practices

1. **Keep skill sections concise** - Target <30 lines total
2. **Use consistent formatting** - Bullet lists for 2+ skills
3. **Choose appropriate action verbs** - Match agent type/context
4. **Reference meta-skill** - Point to skill-integration-templates for guidance
5. **Avoid duplication** - Reference skills instead of repeating content

## Integration Checklist

- [ ] Section titled "## Relevant Skills"
- [ ] Skills formatted as bullet list (if 2+)
- [ ] Action verbs match agent context
- [ ] Closing sentence references skill-integration-templates
- [ ] Total section <30 lines
- [ ] No duplicated skill content

## Related Documentation

- `agent-action-verbs.md` - Action verb taxonomy
- `progressive-disclosure-usage.md` - Progressive disclosure patterns
- `integration-best-practices.md` - Integration best practices
