# Skills Progressive Disclosure Research

> **Issue Reference**: Issue #35, #140, #143
> **Research Date**: 2025-12-17
> **Status**: Active

## Overview

Research and design decisions behind the skills system in autonomous-dev. The plugin uses 28 skills with progressive disclosure to manage context budget while providing specialized knowledge to agents.

---

## Key Findings

### 1. The Context Budget Problem

**Problem**: Claude Code has limited context window. Loading all knowledge upfront causes:
- Context exhaustion mid-workflow
- Slower responses (more tokens to process)
- Irrelevant information diluting relevant knowledge

**Statistics**:
- Full agent knowledge: ~50,000 tokens
- Target per feature: <8,000 tokens
- Reduction needed: 84%

### 2. Progressive Disclosure Pattern

**Solution**: Load knowledge on-demand, not upfront.

```
Level 1: Skill Header (50-100 tokens)
  - Purpose, when to use, quick reference
  - Always loaded when skill referenced

Level 2: Detailed Docs (500-2000 tokens)
  - Full implementation guides
  - Loaded only when agent needs deep knowledge

Level 3: Examples (200-500 tokens)
  - Code examples, templates
  - Loaded only for implementation tasks
```

**Implementation**:
```
skills/
├── security-patterns/
│   ├── SKILL.md           # Level 1: 80 lines
│   └── docs/
│       ├── input-validation.md    # Level 2
│       ├── secrets-management.md  # Level 2
│       └── examples/
│           └── api-key-rotation.md # Level 3
```

### 3. Claude Code 2.0 Skill Integration

**Native integration** (Issue #143): Agents declare skills in frontmatter.

```yaml
---
name: security-auditor
model: opus
skills: [security-patterns, observability]
tools: [Read, Grep, Glob, Bash]
---
```

**How it works**:
1. Agent spawned → Claude Code reads frontmatter
2. Skills field parsed → SKILL.md files loaded
3. Agent receives skill context automatically
4. No manual skill invocation needed

### 4. Token Optimization Results

| Approach | Tokens | Notes |
|----------|--------|-------|
| All knowledge upfront | 50,000 | Baseline |
| Skill headers only | 2,800 | 94% reduction |
| Headers + 1 detailed doc | 4,500 | 91% reduction |
| Full skill (all levels) | 8,000 | 84% reduction |

**Target achieved**: <8,000 tokens per feature.

### 5. Skill Categories

| Category | Skills | Purpose |
|----------|--------|---------|
| **Patterns** | security-patterns, error-handling-patterns, api-integration-patterns | Reusable design patterns |
| **Standards** | python-standards, testing-guide, documentation-guide | Code quality standards |
| **Workflows** | git-workflow, github-workflow, research-patterns | Process guidance |
| **Validation** | project-alignment, cross-reference-validation | Quality checks |

---

## Design Decisions

### Why Skills Instead of System Prompts?

**Considered alternatives**:
1. Long system prompts (rejected - context bloat)
2. RAG retrieval (rejected - latency, complexity)
3. Skills (chosen - declarative, progressive)

**Skills advantages**:
- Declarative (frontmatter, not code)
- Progressive (load what's needed)
- Composable (agents pick skills)
- Maintainable (separate files)

### Why Frontmatter Declaration?

**Problem**: How do agents know which skills they need?

**Solution**: Explicit declaration in agent frontmatter.

```yaml
# Agent declares its skills
skills: [security-patterns, testing-guide]

# Claude Code auto-loads these skills when agent spawned
```

**Benefits**:
- No runtime skill selection logic
- Clear agent capabilities
- Easy to audit skill usage
- Single source of truth

### Why SKILL.md + docs/ Structure?

**Problem**: Some skills need 50 lines, others need 500.

**Solution**: Two-tier structure.

```
skill/
├── SKILL.md    # Always loaded (header, quick ref)
└── docs/       # Loaded on demand (detailed guides)
```

**Rules**:
- SKILL.md: <500 lines (hard limit)
- docs/*: Unlimited (loaded selectively)
- No skill loads everything automatically

---

## Skill Structure Template

```markdown
# Skill Name

**Version**: 1.0.0
**Purpose**: One-line description

## Quick Reference

[50-100 lines of essential knowledge]

## When to Use

- Trigger condition 1
- Trigger condition 2

## Key Patterns

[Core patterns, always loaded]

## Detailed Guides

See docs/ directory:
- docs/topic-1.md - Deep dive on topic 1
- docs/topic-2.md - Deep dive on topic 2
```

---

## Source References

- **Nielsen Norman Group**: Progressive disclosure in UI/UX design
- **Software Architecture Patterns**: Lazy loading and on-demand resources
- **Claude Code Documentation**: Skills and frontmatter format
- **Context Window Research**: Token budget optimization strategies

---

## Implementation Notes

### Applied to autonomous-dev

1. **28 skills** with progressive disclosure
2. **Two-tier structure** (SKILL.md + docs/)
3. **Native frontmatter** integration (Issue #143)
4. **<8,000 token** budget per feature
5. **Skill versioning** (1.0.0 format)

### Skill Distribution

| Agent | Skills | Token Budget |
|-------|--------|--------------|
| security-auditor | 2 | ~1,200 |
| implementer | 3 | ~1,800 |
| test-master | 2 | ~1,400 |
| doc-master | 2 | ~1,000 |
| planner | 2 | ~1,200 |

### Directory Structure

```
plugins/autonomous-dev/skills/
├── security-patterns/
├── testing-guide/
├── documentation-guide/
├── python-standards/
├── error-handling-patterns/
└── ... (28 total)
```

---

## Related Issues

- **Issue #35**: Initial skill integration
- **Issue #140**: Skill injection system
- **Issue #143**: Native frontmatter skills
- **Issue #146**: Skill tool restrictions

---

**Generated by**: Research persistence (Issue #151)
