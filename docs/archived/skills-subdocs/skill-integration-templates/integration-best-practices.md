# Integration Best Practices

Best practices for integrating skills into agent prompts efficiently and effectively.

## Core Principles

### 1. Keep Skill Sections Concise
**Target**: <30 lines for entire "Relevant Skills" section

**Why**: Verbose skill sections defeat the purpose of progressive disclosure

**Good** (12 lines):
```markdown
## Relevant Skills

You have access to these specialized skills during implementation:

- **python-standards**: Follow for code style and conventions
- **testing-guide**: Reference for TDD implementation
- **observability**: Use for logging patterns

Consult the skill-integration-templates skill for formatting guidance.
```

**Bad** (45+ lines):
```markdown
## Relevant Skills

You have access to a comprehensive set of specialized skills...

- **python-standards**: This skill provides detailed Python coding standards
  - Code style guidelines (PEP 8 compliance)
  - Type hint usage patterns
  - Docstring formatting rules
  - Import organization standards
  [... 20+ more lines of verbose descriptions]
```

### 2. Reference Skills Instead of Duplicating Content
**Do**: Point to skills for detailed guidance
```markdown
- **testing-guide**: Reference for TDD patterns and coverage strategies
```

**Don't**: Duplicate skill content inline
```markdown
## Testing Standards

Tests must be written before code (TDD). Use pytest framework.
Test files must match src/ structure. Fixtures should be in conftest.py.
Coverage must be >80%. Use AAA pattern (Arrange, Act, Assert)...
[... 500+ tokens of duplicated testing-guide content]
```

### 3. Use Consistent Formatting Across Agents
**Standard Format**:
```markdown
## Relevant Skills

[Intro sentence about when skills apply]

- **skill-name**: [Action verb] [purpose] for [use case]
- **skill-name**: [Action verb] [purpose] for [use case]

[Closing sentence referencing skill-integration-templates]
```

### 4. Maintain Essential Agent-Specific Guidance
**Keep Inline**: Unique instructions specific to this agent's workflow
```markdown
## Your Mission

As the implementer agent, make tests pass by writing minimal, focused code.
Never write tests - test-master handles that. Focus only on implementation.
```

**Reference Skill**: Reusable knowledge shared across agents
```markdown
## Relevant Skills

- **python-standards**: Follow for code conventions
```

### 5. Balance Skill References with Agent Uniqueness
Each agent should have:
- **Unique mission statement** (inline, ~200-500 tokens)
- **Agent-specific workflow** (inline, ~300-500 tokens)
- **Skill references** (reference, ~200-400 tokens)
- **Agent-specific constraints** (inline, ~100-200 tokens)

## Integration Patterns

### Pattern 1: Minimal Skill Section (1-2 Skills)
```markdown
## Relevant Skills

Reference the **testing-guide** skill for TDD patterns and coverage strategies.
```

### Pattern 2: Standard Skill Section (3-5 Skills)
```markdown
## Relevant Skills

You have access to these specialized skills when [context]:

- **skill-1**: [Action verb] [purpose]
- **skill-2**: [Action verb] [purpose]
- **skill-3**: [Action verb] [purpose]

Consult the skill-integration-templates skill for formatting guidance.
```

### Pattern 3: Extended Skill Section (6+ Skills)
```markdown
## Relevant Skills

You have access to these specialized skills when [context]:

**Core Skills**:
- **skill-1**: [Action verb] [purpose]
- **skill-2**: [Action verb] [purpose]

**Optional Skills**:
- **skill-3**: Use when [condition]
- **skill-4**: Reference for [specific case]

Consult the skill-integration-templates skill for formatting guidance.
```

## Common Anti-Patterns

### Anti-Pattern 1: Verbose Skill Descriptions
```markdown
- **skill-name**: This skill provides comprehensive guidance on [topic] and includes
  detailed documentation covering [subtopic 1], [subtopic 2], and [subtopic 3].
  Use this skill when you need to [use case 1] or [use case 2].
```

**Fix**: Be concise
```markdown
- **skill-name**: Follow for [topic] guidance on [subtopic 1-3]
```

### Anti-Pattern 2: Duplicated Skill Content
```markdown
## Code Standards

Python code must follow PEP 8...
[500+ tokens from python-standards skill]

## Relevant Skills

- **python-standards**: Python coding conventions
```

**Fix**: Remove inline duplication, keep only skill reference
```markdown
## Relevant Skills

- **python-standards**: Follow for code style and conventions
```

### Anti-Pattern 3: Missing Skill References
```markdown
## Implementation Guidelines

When writing code, follow Python conventions, use type hints,
write docstrings, handle errors properly, add logging...
[... inline guidance that exists in skills]
```

**Fix**: Reference relevant skills
```markdown
## Relevant Skills

- **python-standards**: Follow for code conventions and type hints
- **error-handling-patterns**: Apply for error handling
- **observability**: Use for logging patterns
```

### Anti-Pattern 4: Generic Skill References
```markdown
- **skill-name**: Use this skill for stuff
```

**Fix**: Be specific
```markdown
- **skill-name**: Apply for API endpoint design and versioning
```

## Quality Checklist

Before committing agent changes, verify:

- [ ] "Relevant Skills" section exists
- [ ] Section is <30 lines total
- [ ] Skills formatted as bullet list (if 2+ skills)
- [ ] Action verbs match agent context (see agent-action-verbs.md)
- [ ] Closing sentence references skill-integration-templates
- [ ] No duplicated skill content inline
- [ ] Essential agent-specific guidance preserved
- [ ] Skill names are correct (match skill directory names)
- [ ] Purpose statements are concise (1 line per skill)

## Token Reduction Targets

### Per-Agent Targets
- **Minimum**: 30 tokens saved per agent
- **Target**: 40-50 tokens saved per agent
- **Stretch**: 60+ tokens saved per agent

### Project-Wide Targets (20 Agents)
- **Minimum**: 600 tokens (30 × 20)
- **Target**: 800-1,000 tokens (40-50 × 20)
- **Stretch**: 1,200+ tokens (60 × 20)

## Measuring Success

### Before Streamlining
```bash
# Measure agent token count
python3 tests/measure_skill_integration_tokens.py

# Output:
# Total agents: 20
# Total tokens: 23,162
# Streamlined agents: 0/20
```

### After Streamlining
```bash
# Measure again
python3 tests/measure_skill_integration_tokens.py

# Expected output:
# Total agents: 20
# Total tokens: 22,162-22,562
# Streamlined agents: 20/20
# Token reduction: 600-1,000 (3-5%)
```

## Examples

### Good Integration
```markdown
## Relevant Skills

You have access to these specialized skills during code review:

- **code-review**: Validate against quality standards
- **python-standards**: Check style and conventions
- **security-patterns**: Scan for vulnerabilities
- **testing-guide**: Assess test coverage and quality

Consult the skill-integration-templates skill for formatting guidance.
```

**Why Good**:
- Concise (10 lines)
- Clear action verbs
- Specific purposes
- References meta-skill
- No duplicated content

### Bad Integration
```markdown
## Relevant Skills and Guidelines

You have access to an extensive library of specialized skills that can assist
you throughout your workflow. These skills contain detailed documentation,
templates, and examples for various aspects of software development.

- **code-review**: This skill provides comprehensive code review guidelines
  including quality standards, readability metrics, maintainability patterns,
  and best practices. Use this skill when you need to:
  - Review code for quality issues
  - Check for common anti-patterns
  - Validate coding standards compliance
  - Assess code maintainability

- **python-standards**: This skill contains extensive Python coding standards
  covering PEP 8 compliance, type hint usage, docstring formatting, import
  organization, and more. Reference this skill when:
  - Writing new Python code
  - Reviewing Python code style
  - Formatting docstrings
  [... continues for 50+ lines]
```

**Why Bad**:
- Verbose (60+ lines)
- Duplicates skill content
- Redundant descriptions
- Missing meta-skill reference
- Defeats progressive disclosure purpose

## Related Documentation

- `skill-reference-syntax.md` - Syntax patterns
- `agent-action-verbs.md` - Action verb taxonomy
- `progressive-disclosure-usage.md` - Progressive disclosure patterns
