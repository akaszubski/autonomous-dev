# Skill-Agent Integration Implementation Guide

**Version**: v3.1.0
**Date**: 2025-10-27
**Status**: Active Architecture

---

## Overview

Skills are reusable knowledge packages that agents use intelligently through **progressive disclosure** - metadata stays in system prompts (minimal overhead), full skill content loads only when needed.

This document explains:
1. How skills work in the agent-skill architecture
2. How agents discover and use skills
3. Best practices for skill design and integration
4. How to extend with new skills

---

## Part 1: Architecture Overview

### Progressive Disclosure Pattern

**The Problem (v2.5)**:
```
System Prompt (context limited to 8K tokens)
├─ Skill 1: 5KB of content
├─ Skill 2: 4KB of content
├─ Skill 3: 6KB of content
└─ ... (can only fit 3-5 skills before bloat)

Result: Limited scalability, high context cost
```

**The Solution (v2024+)**:
```
System Prompt (context efficient)
├─ Skill Metadata (2-5KB for 50+ skills!)
│  ├─ skill_1: "Data analysis - when to use it"
│  ├─ skill_2: "Code review - trigger patterns"
│  ├─ skill_3: "Security audit - what it checks"
│  └─ ... (unlimited skills, minimal context)
│
├─ [Agent recognizes task needs expertise]
│
└─ Load Full Skill Content (on-demand)
   ├─ skill_1/SKILL.md (5KB content loaded only when needed)
   ├─ skill_1/examples.md (loaded when referencing examples)
   └─ skill_1/templates/ (loaded when creating from template)

Result: 50+ skills possible, no bloat, full context when needed
```

### How It Works in Practice

**Scenario: Implementing a REST API endpoint**

```
User: "Add authentication endpoints"
        ↓
Agent: Reads system prompt → "I have access to api-design skill"
        ↓
Agent: Recognizes "endpoints" keyword → loads api-design/SKILL.md
        ↓
Agent: Uses skill guidance to design endpoints
        ↓
Agent: Needs error handling example → loads api-design/error-handling.md
        ↓
Result: Professional API design using skill expertise, zero context waste
```

---

## Part 2: 19 Active Skills

### Core Development Skills

**api-design**
- When: Designing REST endpoints, API versioning, error handling
- Keywords: api, rest, endpoint, http, json, openapi, swagger, versioning, pagination
- Usage: `When designing API endpoints, load api-design skill for REST principles and OpenAPI standards`

**architecture-patterns**
- When: System design decisions, ADRs, design patterns, scalability
- Keywords: architecture, design, pattern, decision, tradeoffs, adr, system design, scalability, microservices
- Usage: `When making architectural decisions, use architecture-patterns skill for framework and trade-off analysis`

**code-review**
- When: Code quality assessment, style checking, pattern detection
- Keywords: review, pr, feedback, comment, critique, quality check, code review, pull request review
- Usage: `When reviewing code, use code-review skill for comprehensive quality assessment`

**database-design**
- When: Schema design, migrations, query optimization, ORM patterns
- Keywords: database, schema, migration, query, sql, orm, sqlalchemy, django orm, postgres, mysql, index, transaction
- Usage: `When designing database features, use database-design skill for normalization and optimization`

**testing-guide**
- When: TDD methodology, test patterns, coverage strategies
- Keywords: test, testing, tdd, pytest, coverage, baseline, progression, regression, quality
- Usage: `When writing tests, use testing-guide skill for TDD patterns and coverage strategies`

**security-patterns**
- When: Security vulnerabilities, API key management, input validation
- Keywords: security, api key, secret, validation, injection, owasp, authentication, authorization
- Usage: `When implementing security, use security-patterns skill for vulnerability prevention`

### Workflow & Automation Skills

**git-workflow**
- When: Commit messages, branching strategies, PR workflows
- Keywords: git, commit, branch, pull request, pr, merge, github, conventional commits, workflow
- Usage: `When working with git, use git-workflow skill for conventional commit standards`

**github-workflow**
- When: Issues, PRs, milestones, auto-tracking
- Keywords: github, issue, pr, milestone, workflow, tracking, automation
- Usage: `When managing GitHub, use github-workflow skill for issue tracking patterns`

**project-management**
- When: PROJECT.md creation, goal setting, sprint planning
- Keywords: project.md, milestone, sprint, roadmap, planning, goals, scope, constraints
- Usage: `When planning projects, use project-management skill for PROJECT.md patterns`

**documentation-guide**
- When: API documentation, README updates, consistency
- Keywords: documentation, docs, readme, changelog, guides, api docs, consistency
- Usage: `When writing documentation, use documentation-guide skill for standards and patterns`

### Code & Quality Skills

**python-standards**
- When: Code style, type hints, docstrings, formatting
- Keywords: python, pep8, type hints, docstrings, black, isort, formatting
- Usage: `When writing Python code, use python-standards skill for PEP 8 compliance`

**observability**
- When: Logging, debugging, profiling, performance monitoring
- Keywords: logging, debug, debugger, pdb, profiling, performance, trace, stack trace, metrics, monitoring
- Usage: `When adding instrumentation, use observability skill for logging patterns`

**consistency-enforcement**
- When: Documentation consistency, drift prevention
- Keywords: readme, documentation, commit, sync, update, consistency, drift
- Usage: `When ensuring consistency, use consistency-enforcement skill to prevent drift`

**file-organization**
- When: Project structure, file location standards
- Keywords: file, organization, structure, standard, hierarchy, location
- Usage: `When organizing files, use file-organization skill for structure standards`

### Validation & Analysis Skills

**research-patterns**
- When: Research methodology, pattern discovery
- Keywords: research, investigate, pattern, best practice, design, architecture
- Usage: `When researching features, use research-patterns skill for methodology`

**semantic-validation**
- When: GenAI-powered validation, drift detection
- Keywords: validation, semantic, drift, accuracy, alignment
- Usage: `When validating accuracy, use semantic-validation skill`

**cross-reference-validation**
- When: Documentation link validation, file path checking
- Keywords: reference, validation, link, path, cross-reference
- Usage: `When checking documentation, use cross-reference-validation skill`

**documentation-currency**
- When: Stale documentation detection, version lag
- Keywords: currency, stale, outdated, version, lag, status
- Usage: `When checking documentation age, use documentation-currency skill`

**advisor-triggers**
- When: Critical analysis patterns, decision trade-offs
- Keywords: advise, decision, tradeoff, risk, critical, analysis
- Usage: `When considering major decisions, use advisor-triggers skill`

---

## Part 3: How Agents Use Skills

### Agent System Prompt Pattern

Every agent includes a **Relevant Skills** section:

```markdown
## Relevant Skills

You have access to these specialized skills when [task]:

- **skill-name**: Brief description of what it covers
- **skill-name**: Brief description
- ...

When [specific trigger], consult the relevant skill for [guidance type].
```

**Example** (from reviewer agent):
```markdown
## Relevant Skills

You have access to these specialized skills when reviewing code:

- **code-review**: Code quality assessment, style checking, pattern detection
- **testing-guide**: Test coverage evaluation, test quality assessment
- **python-standards**: Python code style checking
- **security-patterns**: Security pattern review

When reviewing implementation, consult the code-review skill for comprehensive quality assessment.
```

### Skill Discovery Mechanism

Agents discover skills through pattern matching:

1. **Metadata in System Prompt**: Agent reads skill list and descriptions
2. **Keyword Matching**: Agent recognizes keywords in task (e.g., "api design" → api-design skill)
3. **Load Full Content**: Agent loads SKILL.md when recognizing relevance
4. **Use Guidance**: Agent follows skill framework and patterns
5. **Load Supporting Files**: Agent loads examples/templates as needed

Example flow:
```
Task: "Design authentication endpoints"
         ↓
Agent keywords: "endpoints" + "authentication"
         ↓
Matches: api-design (endpoints) + security-patterns (authentication)
         ↓
Load: api-design/SKILL.md + security-patterns/SKILL.md
         ↓
Agent follows both skills' guidance for secure API design
         ↓
References: "See api-design/error-handling.md for auth error responses"
         ↓
Load: api-design/error-handling.md on-demand
```

---

## Part 4: Skill File Organization

### Recommended Structure

```
skills/skill-name/
├── SKILL.md                    # Main skill content (2-3KB)
│   ├── [Brief intro]
│   ├── ## Quick Reference
│   ├── ## Deep Dive Section 1
│   ├── ## Deep Dive Section 2
│   └── ## Supporting Files (references)
│
├── examples.md                 # Detailed examples (5KB, loaded when needed)
├── checklist.md                # Implementation checklist
├── templates/
│   ├── template1.md
│   └── template2.md
└── scripts/
    └── utility.py              # Optional: executable scripts
```

### SKILL.md Content Structure

**Keep concise** (2-3KB target):

```markdown
---
name: skill-name
type: knowledge
description: Narrow, trigger-specific description (include keywords)
keywords: keyword1, keyword2, keyword3, keyword4
auto_activate: true
---

# Skill Title

One-sentence mission statement.

## When This Skill Activates

- When: Specific trigger pattern 1
- When: Specific trigger pattern 2
- Keywords: "keyword1", "keyword2"

---

## Core Guidance

[2-3 sections of core patterns and best practices]

## Supporting Files

- **examples.md**: Detailed examples and case studies
- **checklist.md**: Implementation checklist
- **templates/**: Reusable templates
```

---

## Part 5: Best Practices for Skill Design

### 1. Scope Skills Narrowly

**BAD** ❌
```
name: "Development Helper"
description: "Helps with any development task"
```

**GOOD** ✅
```
name: "REST API Design"
description: "Design REST APIs with proper versioning, error handling,
and pagination. Use when creating HTTP endpoints, designing API
versioning strategies, or implementing error responses. Keywords:
api, rest, endpoint, http, openapi, versioning."
```

### 2. Write Trigger-Specific Descriptions

Include keywords Claude recognizes:

**File Types**: ".json files", "Docker containers", "SQL queries"
**Operations**: "pivot tables", "authentication", "caching", "pagination"
**Problems**: "slow queries", "memory leaks", "security audit", "version mismatch"
**Domains**: "REST API", "database schema", "test coverage", "type hints"

### 3. Use Progressive Disclosure in SKILL.md

```markdown
# Skill Title

[QUICK INTRO - 2-3 sentences]

## Quick Reference

- Bullet list of key points
- Common patterns

## Deep Dive: Topic 1

Detailed guidance for first topic

## Deep Dive: Topic 2

Detailed guidance for second topic

## Supporting Files

- See: examples.md for detailed examples
- See: checklist.md for implementation checklist
- See: templates/ for reusable templates
```

Claude reads intro, loads detailed sections as needed.

### 4. Include Executable Code (Optional)

Skills can include Python/Bash for deterministic operations:

```yaml
tools: ["bash", "python"]
```

Good for:
- Data transformations
- Environment checks
- File operations
- Sorting/analyzing

Bad for:
- Complex business logic (use agents instead)
- API calls (should be in agent flow)

### 5. Keep Supporting Files Modular

```
examples.md          (5KB - examples and case studies)
checklist.md         (2KB - implementation checklist)
templates/           (reusable templates and snippets)
reference.md         (optional - deep reference material)
```

Only main files loaded always. Supporting files load on-demand.

---

## Part 6: Integrating New Skills

### Step 1: Design the Skill

```markdown
# skill-name/SKILL.md

---
name: skill-name
type: knowledge
description: Narrow trigger-specific description with keywords
keywords: key1, key2, key3, key4, key5
auto_activate: true
---

# Skill Title

Clear mission statement.

## When This Activates

- Trigger pattern 1
- Trigger pattern 2
- Keywords: "key1", "key2"

---

## Core Guidance

[Essential patterns and best practices]
```

### Step 2: Add to Agent System Prompts

Update relevant agent prompts to include skill metadata:

```markdown
## Relevant Skills

You have access to these skills when [task]:

- **skill-name**: What it covers
- ... (other relevant skills)

When [specific condition], use skill-name for [guidance type].
```

### Step 3: Update Documentation

1. Add to CLAUDE.md skill list
2. Add to README.md skill list
3. Update agent documentation
4. Add to PROJECT.md if architectural change

### Step 4: Test & Validate

- Verify skill metadata is discoverable
- Test keyword matching
- Ensure agents reference it appropriately
- Check for context efficiency

---

## Part 7: Skill Usage Examples

### Example 1: Implementing API Endpoints

```
Agent Task: "Implement user authentication endpoints"

Process:
1. Recognize "endpoints" + "authentication" keywords
2. Load: api-design/SKILL.md + security-patterns/SKILL.md
3. Follow: REST principles from api-design
4. Follow: Security patterns from security-patterns
5. Reference: "See api-design/error-handling.md"
6. Load: api-design/error-handling.md on-demand
7. Result: Secure, well-designed endpoints following both skills
```

### Example 2: Database Schema Design

```
Agent Task: "Design user profile schema with relationships"

Process:
1. Recognize "schema" + "database" keywords
2. Load: database-design/SKILL.md
3. Follow: Normalization guidance
4. Reference: "See templates/schema-template.sql"
5. Load: database-design/templates/schema-template.sql
6. Adapt template for user profiles
7. Result: Well-normalized schema following best practices
```

### Example 3: Code Review

```
Agent Task: "Review implemented authentication code"

Process:
1. Recognize "review" keyword
2. Load: code-review/SKILL.md + security-patterns/SKILL.md
3. Follow: Code quality checklist
4. Follow: Security vulnerability patterns
5. Reference: "See code-review/checklist.md"
6. Load: code-review/checklist.md
7. Provide: Structured review with quality + security assessment
8. Result: Comprehensive review using both skills
```

---

## Part 8: Troubleshooting

### Skills Not Being Used

**Check**:
1. Are keywords in skill description? (Make more specific)
2. Is agent's system prompt listing skill? (Add it)
3. Are skill metadata clear? (Make descriptions concrete)

**Fix**:
- Update skill description with more specific keywords
- Add skill to agent's "Relevant Skills" section
- Test with specific trigger phrases

### Skill Content Not Matching Task

**Check**:
1. Is skill scope correct? (Too broad or narrow?)
2. Are keywords triggering correctly?
3. Is SKILL.md content addressing the task?

**Fix**:
- Narrow skill scope if too broad
- Add more specific keywords
- Reorganize SKILL.md content for clarity

### Context Growing Too Large

**Check**:
1. Are SKILL.md files > 3KB? (Too large)
2. Are supporting files being included unnecessarily?
3. Are agents loading irrelevant skills?

**Fix**:
- Keep SKILL.md to 2-3KB max
- Move details to supporting files
- Verify keyword matching is specific

---

## Part 9: Migration from v2.5 "Anti-Pattern"

If updating from v2.5 where skills were discouraged:

### What Changed

| Aspect | v2.5 | v2024+ |
|--------|------|--------|
| Skills in context | All loaded (bloat) | Only metadata (efficient) |
| Scalability | 3-5 skills max | 50+ skills possible |
| Architecture | Discouraged | First-class citizens |
| Loading | All-at-once | Progressive disclosure |

### Migration Path

1. **Keep existing skills** - They're valuable!
2. **Add skill metadata sections** to agent prompts
3. **Organize supporting files** into progressive disclosure structure
4. **Update documentation** to reflect new architecture
5. **Test** with agents to ensure discovery works

---

## Summary: Why Agent-Skill Integration Works

| Aspect | Skills Alone | Agents Alone | Agents + Skills |
|--------|--------------|--------------|-----------------|
| Specialization | ✅ Focused | ❌ Broad | ✅✅ Both |
| Scalability | ✅ 50+ skills | ❌ Limited | ✅✅ Unlimited |
| Context Efficiency | ✅ Progressive | ❌ Full load | ✅✅ Progressive |
| Discoverability | ✅ Metadata | ❌ Manual | ✅✅ Automatic |
| Orchestration | ❌ No | ✅ Yes | ✅✅ Intelligent |
| Tool Control | ✅ Boundary | ❌ Full | ✅✅ Scoped |

**The real power**: Agents orchestrate and make decisions, skills provide specialized expertise when needed. Each does what it does best.

---

**Last Updated**: 2025-10-27
**Status**: Active Architecture (v3.1.0+)
**Related**: `docs/SKILLS-AGENTS-INTEGRATION.md` (research document)
