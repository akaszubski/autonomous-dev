# Skill Description Pattern

Reference guide for writing SKILL.md `description` fields in YAML frontmatter.

## Template

```
description: "[What it does - concrete capabilities]. Use when [trigger conditions]. TRIGGER when: [keywords]. DO NOT TRIGGER when: [exclusions]."
```

## Rules

1. **100-500 characters** total length
2. **Start with concrete capabilities** (what it does, not what it is)
3. **Include "Use when"** with 2-3 trigger conditions
4. **Include "TRIGGER when:"** with comma-separated keywords
5. **Include "DO NOT TRIGGER when:"** with exclusion conditions
6. **Active voice only** -- no "A skill that", "This skill", or "Enforcement skill for"
7. **Wrap in quotes** in YAML to handle colons safely

## Examples

### Good

```yaml
description: "File-by-file architecture planning with ADR format, dependency ordering, and testability gates. Use when designing system architecture or creating ADRs. TRIGGER when: architecture plan, system design, ADR, file breakdown, component design. DO NOT TRIGGER when: simple config edits, single-file bug fixes, documentation-only changes."
```

```yaml
description: "10-point code review checklist covering correctness, tests, error handling, type hints, naming, security, and performance. Use when reviewing PRs or evaluating code quality. TRIGGER when: code review, PR review, review checklist, code quality check. DO NOT TRIGGER when: writing new code, debugging, refactoring without review context."
```

### Bad

```yaml
# Too short, no triggers
description: Enforcement skill for consistent code reviews

# Passive voice
description: A skill that helps with code reviews

# Missing DO NOT TRIGGER
description: Code review checklist. Use when reviewing PRs. TRIGGER when: code review.
```

## Validation

Run the test suite to validate all descriptions:

```bash
python -m pytest tests/unit/skills/test_skill_descriptions.py -v
```
