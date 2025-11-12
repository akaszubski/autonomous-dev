# Progressive Disclosure Architecture

Technical details of how progressive disclosure enables efficient context management with 100+ skills.

## Overview

Progressive disclosure is a Claude Code 2.0+ design pattern that separates skill metadata from full content, loading details only when needed. This prevents context bloat while maintaining access to comprehensive specialized knowledge.

## The Problem

### Without Progressive Disclosure

**Traditional approach**: Load all skill content into context

```
Agent Context:
├── Agent prompt: 500 tokens
├── Skill 1 full content: 5,000 tokens
├── Skill 2 full content: 4,000 tokens
├── Skill 3 full content: 6,000 tokens
├── Skill 4 full content: 3,000 tokens
├── Skill 5 full content: 4,500 tokens
├── ... (15 more skills)
└── Total: 50,000+ tokens

Result: Context budget exceeded before task even starts!
```

**Limitations:**
- Can't scale beyond 10-15 skills
- Wastes context on irrelevant skills
- Agent overwhelmed with information
- Poor performance

### With Progressive Disclosure

**Modern approach**: Metadata in context, content on-demand

```
Agent Context (Startup):
├── Agent prompt: 500 tokens
├── Skill 1 metadata: 50 tokens
├── Skill 2 metadata: 50 tokens
├── ... (19 more skills)
├── Skill 21 metadata: 50 tokens
└── Total: ~1,500 tokens

Agent Context (Task Execution):
├── Base context: 1,500 tokens
├── Task description: 200 tokens
├── Skill 1 full content: 5,000 tokens (loaded on-demand)
├── Skill 3 full content: 6,000 tokens (loaded on-demand)
└── Total: ~12,700 tokens

Result: Efficient! Only relevant skills load.
```

**Benefits:**
- Scales to 100+ skills
- Fast context loading
- Only relevant content
- Better performance

## Architecture Components

### 1. Skill Metadata (YAML Frontmatter)

**Always in context** (~50 tokens per skill):

```yaml
---
name: testing-guide
type: knowledge
description: Comprehensive pytest patterns, TDD workflow, and coverage strategies
keywords: test, testing, pytest, tdd, coverage, fixture
auto_activate: true
---
```

**Purpose:**
- Skill discovery (keyword matching)
- Skill selection (agent references)
- Context navigation (what's available)

### 2. Skill Content (Markdown Body)

**Loaded on-demand** (~5,000-15,000 tokens per skill):

```markdown
# Testing Guide Skill

[Comprehensive testing guidance...]

## Pytest Patterns
[Detailed pytest guidance...]

## TDD Workflow
[Detailed TDD guidance...]

## Coverage Strategies
[Detailed coverage guidance...]
```

**Purpose:**
- Detailed specialized guidance
- Code examples
- Best practices
- Troubleshooting

### 3. Activation Mechanism

**Automatic (keyword-based):**
```
Task: "Write tests for authentication"
        ↓ (contains "tests")
Keywords match "testing-guide" skill
        ↓
Full skill content loads
```

**Manual (agent-referenced):**
```
Agent: implementer
        ↓ (explicitly lists)
Relevant Skills: testing-guide, python-standards
        ↓
Both skills' content available on-demand
```

## Load Behavior

### Startup Phase

```
1. Claude Code starts
2. Scan skills/ directory
3. Load all SKILL.md files
4. Extract frontmatter metadata
5. Keep metadata in context (lightweight)
6. Discard full content (will load later)

Result: ~1,000-2,000 tokens for 21 skills
```

### Task Execution Phase

```
1. User provides task
2. Analyze task for keywords
3. Match keywords to skill metadata
4. Load full content for matching skills
5. Agent processes task with skills

Result: Only relevant skills (~5,000-15,000 tokens)
```

### Multi-Stage Loading

Progressive disclosure can load skills at any point:

```
Stage 1: Agent starts task
  → Load core skills (python-standards, testing-guide)

Stage 2: Agent encounters security requirement
  → Load security-patterns skill on-demand

Stage 3: Agent needs API documentation
  → Load documentation-guide skill on-demand

Result: Skills load as needed, not all upfront
```

## Performance Characteristics

### Token Efficiency

| Approach | Metadata | Content | Total (Startup) | Total (Task) |
|----------|----------|---------|-----------------|--------------|
| **Traditional** | N/A | 20 skills × 5K = 100K | 100K tokens | 100K+ tokens |
| **Progressive** | 21 × 50 = 1K | On-demand | 1K tokens | ~15K tokens |

**Improvement**: 85% reduction in startup tokens, 85% reduction in task tokens

### Scaling Characteristics

| Number of Skills | Traditional (All Load) | Progressive (Metadata) |
|------------------|------------------------|------------------------|
| 10 skills | 50K tokens | 500 tokens |
| 20 skills | 100K tokens | 1K tokens |
| 50 skills | 250K tokens | 2.5K tokens |
| 100 skills | 500K tokens | 5K tokens |

**Result**: Progressive disclosure scales linearly with metadata size, not content size

## Implementation Details

### Skill File Structure

```
skills/
├── testing-guide/
│   ├── SKILL.md                    # Metadata (50 tokens) + Content (5K tokens)
│   ├── docs/
│   │   ├── pytest-patterns.md      # Additional docs (loaded on-demand)
│   │   └── coverage-strategies.md
│   └── examples/
│       └── test-template.py        # Examples (loaded on-demand)
```

**Progressive disclosure behavior:**
- `SKILL.md` frontmatter: Always in context
- `SKILL.md` body: Loads when skill activated
- `docs/*.md`: Loads when referenced in SKILL.md
- `examples/*`: Loads when referenced in SKILL.md

### Loading Sequence

```python
# Pseudocode for progressive disclosure

# Startup
def load_skills():
    skills = []
    for skill_file in glob("skills/*/SKILL.md"):
        frontmatter = extract_frontmatter(skill_file)
        skills.append({
            "name": frontmatter["name"],
            "metadata": frontmatter,  # Keep in context
            "content_path": skill_file  # Load later
        })
    return skills  # Metadata only (~50 tokens each)

# Task execution
def activate_skill(skill_name):
    skill_file = get_skill_path(skill_name)
    full_content = read_skill_content(skill_file)
    return full_content  # Load on-demand (~5K tokens)
```

## Token Budget Management

### Context Allocation

```
Total context budget: 200,000 tokens

Allocation:
├── Agent prompt: ~500 tokens (0.25%)
├── Skill metadata: ~1,000 tokens (0.5%)
├── Task description: ~500 tokens (0.25%)
├── Available for skill content: ~180,000 tokens (90%)
└── Available for agent work: ~18,000 tokens (9%)

Result: ~98% of budget available for actual work
```

### Dynamic Loading

Skills load dynamically throughout task execution:

```
T0: Agent starts
    Context: 2,000 tokens (agent + metadata + task)

T1: Agent encounters testing requirement
    Load testing-guide: +5,000 tokens
    Context: 7,000 tokens

T2: Agent encounters security requirement
    Load security-patterns: +6,000 tokens
    Context: 13,000 tokens

T3: Agent needs API documentation
    Load documentation-guide: +4,000 tokens
    Context: 17,000 tokens

Total: 17,000 tokens (8.5% of budget used)
```

## Best Practices

### For Skill Authors

✅ **Do:**
- Keep frontmatter concise (~50 tokens)
- Structure content for progressive disclosure
- Use clear section headers
- Include cross-references to other skills

❌ **Don't:**
- Include content in frontmatter (belongs in body)
- Create overly long single-file skills (split into docs/)
- Duplicate content across skills
- Reference external resources that aren't cached

### For Agent Authors

✅ **Do:**
- List relevant skills in agent prompt
- Trust progressive disclosure mechanism
- Reference skills by name in "Relevant Skills" section
- Keep skill references concise

❌ **Don't:**
- Duplicate skill content in agent prompt
- Try to manually control skill loading
- List all 21 skills (redundant)
- Provide conflicting guidance to skills

## Troubleshooting

### Context Budget Exceeded

**Symptom**: "Context budget exceeded" error mid-task

**Causes:**
1. Too many skills loaded simultaneously
2. Individual skill too large
3. Task description too verbose

**Solutions:**
1. Split large skills into multiple focused skills
2. Move detailed content to docs/ subdirectory
3. Use more specific keywords to reduce false matches

### Skill Not Loading

**Symptom**: Agent doesn't have access to expected skill

**Causes:**
1. Skill missing `auto_activate: true`
2. Keywords don't match task
3. Agent doesn't explicitly reference skill

**Solutions:**
1. Add `auto_activate: true` to SKILL.md frontmatter
2. Add more relevant keywords
3. Add skill to agent's "Relevant Skills" section

### Performance Degradation

**Symptom**: Slow agent response times

**Causes:**
1. Loading too many large skills
2. Inefficient keyword matching

**Solutions:**
1. Make keywords more specific
2. Split large skills into smaller focused skills
3. Use explicit agent references instead of auto-activation

## Summary

Progressive disclosure architecture:
- **Separates metadata from content**: Metadata always in context, content on-demand
- **Enables scalability**: Support 100+ skills without context bloat
- **Improves performance**: Only relevant skills load
- **Maintains access**: All skills available when needed

**Key metrics:**
- 85% reduction in context usage
- Scales linearly with skill count
- Supports 100+ skills efficiently

**Remember**: Progressive disclosure is automatic in Claude Code 2.0+. Just structure skills correctly (metadata in frontmatter, content in body) and the system handles the rest.
