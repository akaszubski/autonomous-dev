# Implementer Guide: skill-integration-templates Skill

**Issue**: #72 Phase 8.6
**Status**: TDD Red Phase Complete - Ready for Implementation
**Tests**: 53 tests written (all currently FAIL as expected)

---

## Quick Start

### Current Baseline
```
Total agent tokens: 23,162 tokens
Streamlined agents: 0/20
Target reduction: 600-1,000 tokens (3-5%)
```

### Success Criteria
- ✓ Create 11 skill files (1 SKILL.md + 4 docs + 3 templates + 3 examples)
- ✓ Streamline 20 agent files to reference skill
- ✓ Achieve ≥600 tokens reduction (3% minimum)
- ✓ All 53 tests PASS

---

## Implementation Phases

### Phase 1: Create Skill Structure (11 files)

#### 1.1 Create Main Skill File
**File**: `plugins/autonomous-dev/skills/skill-integration-templates/SKILL.md`
**Size**: ~50 tokens (lightweight for progressive disclosure)

**Template**:
```yaml
---
name: skill-integration-templates
type: knowledge
description: "Standardized templates and patterns for integrating skills into agent prompts. Reduces token overhead through reusable skill reference syntax, action verbs, and progressive disclosure usage guidelines."
keywords:
  - skill-reference
  - agent-skills
  - progressive-disclosure
  - integration-patterns
  - skill-section
  - agent-action-verbs
auto_activate: true
---

## Overview

This skill provides standardized templates and patterns for integrating skills into agent prompts, reducing token overhead while maintaining clarity and consistency.

## When to Use

Reference this skill when:
- Adding skill references to agent prompts
- Structuring "Relevant Skills" sections
- Choosing action verbs for skill descriptions
- Implementing progressive disclosure patterns

## Documentation

See `docs/` directory for detailed guidance:
- `skill-reference-syntax.md` - Skill section syntax patterns
- `agent-action-verbs.md` - Action verbs for different contexts
- `progressive-disclosure-usage.md` - How to use progressive disclosure
- `integration-best-practices.md` - Best practices for skill integration

## Templates

See `templates/` directory for reusable patterns:
- `skill-section-template.md` - Standard skill section template
- `intro-sentence-templates.md` - Intro sentence variations
- `closing-sentence-templates.md` - Closing sentence variations

## Examples

See `examples/` directory for real-world usage:
- `planner-skill-section.md` - Planner agent skill section
- `implementer-skill-section.md` - Implementer agent skill section
- `minimal-skill-reference.md` - Minimal reference example
```

**Validation**: Run `test_skill_file_exists` and `test_skill_has_valid_yaml_frontmatter`

#### 1.2 Create Documentation Files (4 files)

**File 1**: `docs/skill-reference-syntax.md` (~800 tokens)

**Content Outline**:
- Basic syntax patterns for skill references
- Single vs. multiple skill references
- Skill section formatting (bullets vs. paragraphs)
- Action verb selection
- Progressive disclosure integration
- Examples of good vs. bad syntax

**File 2**: `docs/agent-action-verbs.md` (~600 tokens)

**Content Outline**:
- Categorized action verbs by agent type:
  - Research agents: "Consult", "Reference", "Use"
  - Planning agents: "Apply", "Leverage", "Integrate"
  - Implementation agents: "Follow", "Adhere to", "Use"
  - Review agents: "Validate against", "Check using", "Compare with"
- Context-appropriate verb selection
- Examples for each category

**File 3**: `docs/progressive-disclosure-usage.md` (~700 tokens)

**Content Outline**:
- How progressive disclosure works in Claude Code 2.0+
- When to reference skills vs. inline content
- Skill activation keywords
- Balancing context overhead vs. on-demand loading
- Best practices for skill references

**File 4**: `docs/integration-best-practices.md` (~500 tokens)

**Content Outline**:
- Keep skill sections concise (<30 lines)
- Reference skills instead of duplicating content
- Use consistent formatting across agents
- Maintain essential agent-specific guidance
- Balance skill references with agent uniqueness

**Validation**: Run `TestSkillDocumentation` tests

#### 1.3 Create Template Files (3 files)

**File 1**: `templates/skill-section-template.md` (~300 tokens)

**Template Structure**:
```markdown
## Relevant Skills

You have access to these specialized skills [when/during] [agent-specific context]:

- **[skill-name]**: [Action verb] [skill purpose] for [specific use case]
- **[skill-name]**: [Action verb] [skill purpose] for [specific use case]

Consult the [skill-name] skill for [when to use details].
```

**File 2**: `templates/intro-sentence-templates.md` (~400 tokens)

**Template Variations**:
- "You have access to these specialized skills when [context]:"
- "The following skills are available for [purpose]:"
- "Consult these skills during [phase/activity]:"
- "Reference these skills for [specific need]:"

**File 3**: `templates/closing-sentence-templates.md` (~400 tokens)

**Template Variations**:
- "Consult the [skill] skill for [details]."
- "See [skill] skill for [specific guidance]."
- "Reference [skill] skill when [condition]."
- "Use [skill] skill to [action]."

**Validation**: Run `TestSkillTemplates` tests

#### 1.4 Create Example Files (3 files)

**File 1**: `examples/planner-skill-section.md` (~200 tokens)

**Real-World Example from planner.md**:
```markdown
## Relevant Skills

You have access to these specialized skills when planning features:

- **architecture-patterns**: Use for system design decisions
- **api-design**: Reference for API endpoint planning
- **database-design**: Apply for data model planning
- **testing-guide**: Consult for test strategy planning

Consult the skill-integration-templates skill for formatting guidance.
```

**File 2**: `examples/implementer-skill-section.md` (~200 tokens)

**Real-World Example from implementer.md**:
```markdown
## Relevant Skills

You have access to these specialized skills during implementation:

- **python-standards**: Follow for code style and conventions
- **observability**: Use for logging and monitoring patterns
- **testing-guide**: Reference for TDD implementation

Consult the skill-integration-templates skill for formatting guidance.
```

**File 3**: `examples/minimal-skill-reference.md` (~100 tokens)

**Minimal Example**:
```markdown
## Relevant Skills

Consult these skills for specialized guidance:
- **skill-name**: [One-line purpose]

See skill-integration-templates skill for formatting.
```

**Validation**: Run `TestSkillExamples` tests

---

### Phase 2: Streamline Agent Files (20 files)

For each of the 20 agent files, apply the streamlining pattern:

#### Streamlining Pattern

**Before** (verbose inline pattern):
```markdown
## Relevant Skills

You have access to these specialized skills when [agent context]:

- **skill-name**: [Verbose description of skill purpose]
  - Use this skill for [detailed use case 1]
  - Reference when [detailed use case 2]
  - Apply during [detailed use case 3]

- **skill-name**: [Verbose description of skill purpose]
  - Use this skill for [detailed use case 1]
  - Reference when [detailed use case 2]

When integrating skills into your workflow:
1. Read the skill documentation carefully
2. Apply patterns consistently
3. Reference skills instead of duplicating content
4. Use progressive disclosure for on-demand loading

[More verbose guidance about skill integration...]
```

**After** (streamlined with skill reference):
```markdown
## Relevant Skills

You have access to these specialized skills when [agent context]:

- **skill-name**: [Action verb] [concise purpose] for [use case]
- **skill-name**: [Action verb] [concise purpose] for [use case]

Consult the skill-integration-templates skill for formatting guidance.
```

**Token Savings**: ~30-40 tokens per agent

#### Agent Files to Update (20 total)

1. `plugins/autonomous-dev/agents/advisor.md`
2. `plugins/autonomous-dev/agents/alignment-analyzer.md`
3. `plugins/autonomous-dev/agents/alignment-validator.md`
4. `plugins/autonomous-dev/agents/brownfield-analyzer.md`
5. `plugins/autonomous-dev/agents/commit-message-generator.md`
6. `plugins/autonomous-dev/agents/doc-master.md`
7. `plugins/autonomous-dev/agents/implementer.md`
8. `plugins/autonomous-dev/agents/issue-creator.md`
9. `plugins/autonomous-dev/agents/planner.md`
10. `plugins/autonomous-dev/agents/pr-description-generator.md`
11. `plugins/autonomous-dev/agents/project-bootstrapper.md`
12. `plugins/autonomous-dev/agents/project-progress-tracker.md`
13. `plugins/autonomous-dev/agents/project-status-analyzer.md`
14. `plugins/autonomous-dev/agents/quality-validator.md`
15. `plugins/autonomous-dev/agents/researcher.md`
16. `plugins/autonomous-dev/agents/reviewer.md`
17. `plugins/autonomous-dev/agents/security-auditor.md`
18. `plugins/autonomous-dev/agents/setup-wizard.md`
19. `plugins/autonomous-dev/agents/sync-validator.md`
20. `plugins/autonomous-dev/agents/test-master.md`

**Validation**: Run `TestAgentStreamlining` parametrized tests

---

### Phase 3: Validate Token Reduction

#### Run Token Measurement Script
```bash
python3 tests/measure_skill_integration_tokens.py
```

**Expected Output**:
```
CURRENT AGENT TOKEN COUNTS
================================================================================
Total agents:       20
Streamlined agents: 20
Token reduction:    ~600-1,000 tokens (3-5%)

✓ MINIMUM TARGET ACHIEVED: [reduction] >= 600 tokens (3%)
```

**Validation**: Run `TestTokenReduction` tests

---

## Running Tests

### Run All Tests
```bash
# Note: pytest may not be available in current environment
# Tests validate structure manually if pytest unavailable

# Manual validation
python3 tests/measure_skill_integration_tokens.py
```

### Manual Test Validation
```bash
# Check skill file exists
ls -la plugins/autonomous-dev/skills/skill-integration-templates/SKILL.md

# Check documentation files
ls -la plugins/autonomous-dev/skills/skill-integration-templates/docs/

# Check template files
ls -la plugins/autonomous-dev/skills/skill-integration-templates/templates/

# Check example files
ls -la plugins/autonomous-dev/skills/skill-integration-templates/examples/

# Check agent references
grep -l "skill-integration-templates" plugins/autonomous-dev/agents/*.md | wc -l
# Should output: 20
```

---

## Token Reduction Targets

### Baseline (Current)
- **Total Tokens**: 23,162 tokens
- **Streamlined Agents**: 0/20
- **Average per Agent**: ~1,158 tokens

### Minimum Target (3%)
- **Reduction**: 600 tokens
- **After**: 22,562 tokens
- **Per Agent**: ~30 tokens × 20 agents

### Stretch Target (5%)
- **Reduction**: 1,000 tokens
- **After**: 22,162 tokens
- **Per Agent**: ~50 tokens × 20 agents

---

## Quality Gates

### Before Committing
- [ ] All 11 skill files created
- [ ] All 20 agent files streamlined
- [ ] Token measurement script shows ≥600 tokens reduction
- [ ] All tests pass (if pytest available)
- [ ] Skill references are concise (<30 lines)
- [ ] Agent quality maintained (essential content preserved)

---

## Common Issues and Solutions

### Issue: Token reduction below target
**Solution**: Check that all 20 agents reference skill. Each agent should save ~30-40 tokens.

### Issue: Tests fail after streamlining
**Solution**: Ensure skill reference follows template pattern. Check for typos in skill name.

### Issue: Agent quality degraded
**Solution**: Keep essential agent-specific guidance. Only remove duplicated skill integration patterns.

### Issue: Skill overhead too high
**Solution**: Keep SKILL.md lightweight (<100 lines). Move detailed content to docs/templates/examples.

---

## Success Metrics

After implementation:
- ✓ 11 skill files created
- ✓ 20 agent files streamlined
- ✓ 600-1,000 tokens saved (3-5%)
- ✓ 53 tests passing
- ✓ Progressive disclosure validated
- ✓ Backward compatibility maintained

---

**Ready for Implementation**: Follow phases 1-3 sequentially, validate at each step.
