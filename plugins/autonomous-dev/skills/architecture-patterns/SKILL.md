---
name: architecture-patterns
version: 1.0.0
type: knowledge
description: Enforcement skill for consistent architectural planning
keywords: [architecture, planning, design, adr, file-breakdown, dependencies]
auto_activate: true
allowed-tools: [Read, Grep, Glob]
---

# Architecture Patterns Enforcement Skill

Ensures every architecture plan is thorough, actionable, and testable. Used by the planner agent.

## Decision Framework

Every architectural decision MUST follow this structure:

### 1. Problem Statement
- What problem are we solving?
- What are the constraints (performance, compatibility, timeline)?
- What does PROJECT.md say about scope?

### 2. Options Analysis
- Minimum 2 alternatives considered
- Each option has explicit pros and cons
- Effort estimate for each (low/medium/high)

### 3. Recommendation
- Which option and why
- What tradeoffs are we accepting
- What risks remain

---

## Plan Structure Requirements

Every architecture plan MUST include:

### File-by-File Breakdown
```
## Files to Create/Modify

### 1. lib/new_module.py (CREATE)
- Purpose: [what this file does]
- Key classes/functions: [list]
- Dependencies: [what it imports]
- Tests: tests/unit/test_new_module.py

### 2. lib/existing_module.py (MODIFY)
- Changes: [what changes and why]
- Lines affected: ~[range]
- Risk: [low/medium/high]
```

### Ordered Steps with Dependencies
```
## Implementation Order

1. Create lib/new_module.py (no dependencies)
2. Create tests/unit/test_new_module.py (depends on step 1)
3. Modify lib/existing_module.py (depends on step 1)
4. Update integration tests (depends on steps 1-3)
```

Steps MUST be ordered so each step can be tested independently before proceeding.

### Testing Strategy
- Unit tests for each new module
- Integration tests for cross-module interactions
- What to mock and why
- Expected test count estimate

### Integration Points
- What existing code is affected
- API contracts between modules
- Backward compatibility considerations

---

## ADR Format for Major Decisions

For decisions that affect architecture (new patterns, technology choices, major refactors):

```markdown
# ADR-NNN: [Title]

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded

## Context
[Problem and constraints]

## Decision
[What we chose and why]

## Consequences
[Positive and negative outcomes]

## Alternatives Considered
[Other options and why rejected]
```

---

## This Project's Patterns

When planning for this codebase, follow these established patterns:

### Two-Tier Design
- **Core lib** (`plugins/autonomous-dev/lib/`): Pure Python, no side effects, testable
- **CLI layer** (`plugins/autonomous-dev/commands/`): Markdown prompts that invoke lib

### Progressive Enhancement
- Base functionality works without optional dependencies
- GenAI reasoning enhances but never replaces deterministic checks
- Skills loaded on-demand, not all at once

### HARD GATE Enforcement
- Critical rules use FORBIDDEN/REQUIRED language
- Hooks validate at commit/push time (100% reliable)
- Agents enforce at review time (conditional intelligence)

### Hook-Based Validation
- Pre-commit hooks for formatting, secrets, alignment
- Pre-push hooks for tests, coverage
- Pre-tool hooks for security and workflow enforcement

---

## HARD GATE: Plan Quality

**FORBIDDEN**:
- Plans without specific file paths (e.g., "create a new module" without saying where)
- "TBD" or "to be determined" placeholders — decide now or state why you cannot
- Plans with no testing strategy
- Plans that skip scope validation against PROJECT.md
- Monolithic steps that cannot be tested incrementally
- Plans that ignore existing codebase patterns
- Hand-wavy "refactor later" promises

**REQUIRED**:
- File-by-file breakdown with CREATE/MODIFY labels
- Dependency ordering (what must come before what)
- Error handling strategy (what happens when things fail)
- At least 2 alternatives considered for major decisions
- Testing strategy with expected test locations
- Rollback plan (how to undo if the plan fails)
- Scope check against PROJECT.md goals

---

## Anti-Patterns

### BAD: Hand-wavy plan
```
"We should refactor the auth module to be more modular.
We can add better error handling later."
```
No file paths, no steps, no testing, no "later" promises.

### GOOD: Actionable plan
```
## Files to Modify
1. lib/auth.py (MODIFY) — Extract token validation into TokenValidator class
2. lib/token_validator.py (CREATE) — Pure validation logic, no side effects
3. tests/unit/test_token_validator.py (CREATE) — 8 tests covering valid/invalid/expired

## Order
1. Create token_validator.py + tests (independent)
2. Modify auth.py to use TokenValidator (depends on step 1)
3. Run full test suite to verify no regressions
```

### BAD: Monolithic steps
```
Step 1: Rewrite the entire authentication system
Step 2: Test everything
```
Cannot test incrementally, cannot roll back partially.

### GOOD: Incremental steps
Each step produces a testable, committable unit of work.

### BAD: Missing rollback plan
If the migration fails halfway through, what happens? Every plan needs a recovery path.

---

## Cross-References

- **research-patterns**: Research feeds into architecture planning
- **project-alignment**: Plans must align with PROJECT.md
- **code-review**: Plans are reviewed against these quality standards
- **documentation-guide**: ADR format and documentation requirements
