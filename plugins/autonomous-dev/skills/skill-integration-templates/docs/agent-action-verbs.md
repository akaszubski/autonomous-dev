# Agent Action Verbs

Standard action verbs for skill references, categorized by agent type and context.

## Verb Taxonomy

### Research Agents
**Context**: Gathering information, discovering patterns, exploring solutions

**Recommended Verbs**:
- **Consult** - For detailed investigation ("Consult skill for patterns")
- **Reference** - For lookups ("Reference skill for examples")
- **Use** - For applying knowledge ("Use skill for best practices")
- **Explore** - For discovery ("Explore skill for alternatives")

**Example**:
```markdown
- **research-patterns**: Consult for search strategies and information gathering techniques
```

### Planning Agents
**Context**: Architecture design, feature planning, strategy development

**Recommended Verbs**:
- **Apply** - For implementing patterns ("Apply skill for architecture decisions")
- **Leverage** - For utilizing resources ("Leverage skill for design patterns")
- **Integrate** - For combining elements ("Integrate skill guidance into plan")
- **Follow** - For adhering to guidelines ("Follow skill for API design")

**Example**:
```markdown
- **architecture-patterns**: Apply for system design and scalability decisions
```

### Implementation Agents
**Context**: Writing code, executing plans, building features

**Recommended Verbs**:
- **Follow** - For coding standards ("Follow skill for conventions")
- **Adhere to** - For strict compliance ("Adhere to skill standards")
- **Use** - For applying techniques ("Use skill for implementation patterns")
- **Implement** - For execution ("Implement skill recommendations")

**Example**:
```markdown
- **python-standards**: Follow for code style, type hints, and docstrings
```

### Review Agents
**Context**: Quality checking, validation, assessment

**Recommended Verbs**:
- **Validate against** - For compliance checking ("Validate against skill standards")
- **Check using** - For verification ("Check using skill criteria")
- **Compare with** - For consistency ("Compare with skill examples")
- **Assess via** - For evaluation ("Assess via skill quality metrics")

**Example**:
```markdown
- **code-review**: Validate against standards for quality, readability, and maintainability
```

### Documentation Agents
**Context**: Writing docs, maintaining consistency, updating references

**Recommended Verbs**:
- **Follow** - For documentation standards ("Follow skill format")
- **Maintain** - For consistency ("Maintain skill conventions")
- **Apply** - For templates ("Apply skill templates")
- **Reference** - For examples ("Reference skill examples")

**Example**:
```markdown
- **documentation-guide**: Follow for docstring templates and README structure
```

### Security Agents
**Context**: Vulnerability scanning, threat assessment, security validation

**Recommended Verbs**:
- **Check for** - For vulnerability detection ("Check for skill patterns")
- **Scan using** - For automated checks ("Scan using skill rules")
- **Validate** - For security compliance ("Validate skill requirements")
- **Assess** - For risk analysis ("Assess via skill criteria")

**Example**:
```markdown
- **security-patterns**: Check for OWASP Top 10 vulnerabilities and secure coding violations
```

## Context-Appropriate Selection

### Active vs. Passive Voice
- **Active** (Preferred): "Follow skill for standards"
- **Passive** (Avoid): "Skill should be followed for standards"

### Specific vs. Generic
- **Specific** (Preferred): "Validate against skill criteria"
- **Generic** (Avoid): "Use skill"

### Action-Oriented vs. Descriptive
- **Action-Oriented** (Preferred): "Apply skill patterns"
- **Descriptive** (Avoid): "Skill contains patterns"

## Common Patterns

### Single-Purpose Skills
When skill has one clear use case:
```markdown
- **testing-guide**: Reference for TDD implementation patterns
```

### Multi-Purpose Skills
When skill supports multiple contexts:
```markdown
- **python-standards**: Follow for code style, type hints, and documentation
```

### Conditional Skills
When skill applies in specific scenarios:
```markdown
- **observability**: Use when adding logging or monitoring
```

## Anti-Patterns

### Too Verbose
```markdown
- **skill-name**: You should use this skill extensively when you encounter situations where you need to [long description]
```

**Fix**: Be concise
```markdown
- **skill-name**: Use for [specific purpose]
```

### Too Vague
```markdown
- **skill-name**: Helpful for stuff
```

**Fix**: Be specific
```markdown
- **skill-name**: Apply for API endpoint design and versioning
```

### Wrong Voice
```markdown
- **skill-name**: This skill provides guidance on [topic]
```

**Fix**: Use active voice
```markdown
- **skill-name**: Follow for [specific guidance]
```

## Quick Reference Table

| Agent Type | Primary Verbs | Context |
|-----------|--------------|---------|
| Research | Consult, Reference, Use | Information gathering |
| Planning | Apply, Leverage, Follow | Architecture design |
| Implementation | Follow, Adhere to, Use | Code execution |
| Review | Validate, Check, Compare | Quality assessment |
| Documentation | Follow, Maintain, Apply | Doc writing |
| Security | Check, Scan, Validate | Security validation |

## Related Documentation

- `skill-reference-syntax.md` - Complete syntax patterns
- `integration-best-practices.md` - Integration guidelines
