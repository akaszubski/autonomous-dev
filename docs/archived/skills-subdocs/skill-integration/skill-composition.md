# Skill Composition

How to effectively combine multiple skills for complex tasks.

## Overview

Skill composition is the practice of combining multiple skills to handle complex tasks that span multiple domains. Progressive disclosure makes this efficient - all skill metadata stays in context, but only relevant content loads on-demand.

## When to Compose Skills

### Single-Skill Tasks

**Simple task**: "Format Python code"
- **Skill needed**: python-standards
- **Token load**: ~50 tokens metadata + ~3,000 tokens content = ~3,050 tokens

### Multi-Skill Tasks

**Complex task**: "Implement secure JWT authentication API with tests"

**Skills needed:**
1. **api-design**: REST API patterns, endpoint design
2. **security-patterns**: JWT validation, authentication best practices
3. **python-standards**: Code style, type hints
4. **testing-guide**: Security testing patterns
5. **documentation-guide**: API documentation

**Token load**: ~250 tokens metadata + ~15,000 tokens content (5 skills) = ~15,250 tokens

**Still efficient**: Only loads what's needed, not all 21 skills

## Composition Patterns

### Pattern 1: Layer Cake (Sequential)

Skills build on each other in layers:

```
┌─────────────────────────────┐
│    Documentation (Layer 4)  │ ← Document the implementation
├─────────────────────────────┤
│    Testing (Layer 3)        │ ← Test the secure API
├─────────────────────────────┤
│    Security (Layer 2)       │ ← Secure the API
├─────────────────────────────┤
│    API Design (Layer 1)     │ ← Design the API
└─────────────────────────────┘
```

**Example**: Implementing authenticated API endpoint
1. **api-design**: Design endpoint structure
2. **security-patterns**: Add authentication
3. **testing-guide**: Write security tests
4. **documentation-guide**: Document API

### Pattern 2: Cross-Cutting (Parallel)

Multiple skills apply simultaneously:

```
┌──────────────┐
│    Task      │
│ Implement    │
│   Feature    │
└──────────────┘
      │
      ├───> python-standards (code style)
      ├───> security-patterns (validation)
      ├───> testing-guide (tests)
      ├───> observability (logging)
      └───> documentation-guide (docs)
```

**Example**: Implementing user registration
- All skills apply to every piece of code
- Agent consults multiple skills throughout

### Pattern 3: Conditional (Branching)

Different skills based on context:

```
┌──────────────┐
│    Task      │
└──────────────┘
      │
      ├───> API? ──> api-design
      ├───> CLI? ──> Best practices (skill TBD)
      └───> UI?  ──> UI patterns (skill TBD)
            │
            └───> (All paths)
                  ├───> python-standards
                  ├───> testing-guide
                  └───> security-patterns
```

## Composition Examples

### Example 1: Feature Implementation

**Task**: "Add PDF export feature to reports"

**Skill composition:**
```markdown
1. research-patterns
   - Find Python PDF libraries
   - Compare approaches (ReportLab, WeasyPrint, etc.)

2. architecture-patterns
   - Design export service architecture
   - Plan integration with existing reports

3. api-design
   - Design /reports/{id}/export endpoint
   - Plan query parameters (format, page size, etc.)

4. python-standards
   - Implement code with proper style
   - Add type hints, docstrings

5. testing-guide
   - Write unit tests for PDF generation
   - Write integration tests for endpoint

6. security-patterns
   - Validate export permissions
   - Prevent path traversal in file output

7. documentation-guide
   - Document API endpoint
   - Update user guide with export feature
```

**Progressive disclosure benefit:**
- Metadata for 7 skills: ~350 tokens (always in context)
- Full content: Loads as agent progresses through implementation
- Total: ~30,000-35,000 tokens (only when needed)

### Example 2: Bug Fix

**Task**: "Fix memory leak in data processing"

**Skill composition:**
```markdown
1. python-standards
   - Review code style, identify anti-patterns
   - Check for proper resource cleanup

2. observability
   - Add memory profiling
   - Add logging for resource tracking

3. testing-guide
   - Write test to reproduce memory leak
   - Add regression test

4. documentation-guide
   - Update troubleshooting guide
   - Document fix in CHANGELOG
```

**Result**: 4 skills, ~15,000 tokens content on-demand

### Example 3: Refactoring

**Task**: "Extract validation logic to separate module"

**Skill composition:**
```markdown
1. architecture-patterns
   - Plan module structure
   - Design validation interface

2. python-standards
   - Follow module naming conventions
   - Add proper imports, type hints

3. testing-guide
   - Ensure all existing tests pass
   - Add tests for new validation module

4. documentation-guide
   - Update architecture docs
   - Document validation module API
```

## Best Practices

### Do's

✅ **Trust progressive disclosure**: Don't worry about loading too many skills
✅ **Reference all relevant skills**: Agent can access any needed
✅ **Let skills work together**: Don't force single-skill approach
✅ **Check skill overlap**: Skills often complement each other

### Don'ts

❌ **Don't limit to one skill**: Complex tasks need multiple skills
❌ **Don't duplicate skill content**: Let skills provide guidance
❌ **Don't create conflicting skills**: Skills should complement, not contradict
❌ **Don't manually compose**: Let progressive disclosure handle it

## Skill Relationships

### Commonly Paired Skills

**Testing + Security:**
- testing-guide: How to test
- security-patterns: What to test for security

**API + Security + Documentation:**
- api-design: Endpoint design
- security-patterns: Authentication, authorization
- documentation-guide: API docs

**Implementation + Style + Testing:**
- python-standards: How to write code
- testing-guide: How to test code
- security-patterns: How to secure code

### Skill Hierarchies

Some skills reference others:

```
python-standards
    ├── testing-guide (for test code style)
    └── documentation-guide (for docstrings)

api-design
    ├── security-patterns (for secure endpoints)
    └── documentation-guide (for API docs)

testing-guide
    ├── python-standards (for test code style)
    └── security-patterns (for security tests)
```

**Benefit**: Natural skill discovery through references

## Token Impact

### Composition vs Duplication

**Without skills (inline guidance):**
```markdown
Agent prompt: 500 tokens
+ Inline testing guidance: 500 tokens
+ Inline security guidance: 400 tokens
+ Inline style guidance: 300 tokens
+ Inline API guidance: 400 tokens
= 2,100 tokens per agent × 20 agents = 42,000 tokens
```

**With skill composition:**
```markdown
Agent prompt: 500 tokens
+ Skill references: 150 tokens
= 650 tokens per agent × 20 agents = 13,000 tokens

Skills (shared across all agents):
21 skills × 50 tokens metadata = 1,050 tokens
+ Content loads on-demand (only when needed)
```

**Result**: 29,000 token savings (69% reduction)

## Summary

Skill composition enables:
- **Multi-domain tasks**: Combine expertise from multiple skills
- **Efficient context**: Progressive disclosure loads only what's needed
- **Scalability**: Support complex tasks without context bloat
- **Maintainability**: Update skill once, affects all agents

**Key principle**: Trust progressive disclosure to handle multi-skill tasks efficiently. Reference all relevant skills, let the system load content on-demand.
