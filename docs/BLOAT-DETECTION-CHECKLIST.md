# Bloat Detection Checklist

**Purpose**: Validate each issue implementation against PROJECT.md intent before and during development

**Last Updated**: 2025-11-03

---

## Core Intent (from PROJECT.md)

**Primary Mission**: Build an **Autonomous Development Team** that executes on PROJECT.md goals using best practices

**Key Principles**:
- ✅ **All SDLC steps required** - Research → Plan → TDD → Implement → Review → Security → Docs
- ✅ **Professional quality enforced** - Hooks validate, agents enhance
- ✅ **Speed via AI** - Each step accelerated, not skipped
- ✅ **Minimal user intervention** - 8 commands total (down from 40)
- ✅ **GenAI-native orchestration** - Claude reasoning > rigid Python automation

---

## Bloat Detection Gates

### Gate 1: Alignment Check (BEFORE Implementation)

**For each issue, answer:**

1. **Does this serve the primary mission?**
   - [ ] Advances autonomous execution
   - [ ] Improves SDLC enforcement
   - [ ] Enhances AI-powered speed
   - [ ] OR: Does NOT add to core mission (potential bloat)

2. **Does this respect constraints?**
   - [ ] Keeps command count ≤ 8 (current: 7)
   - [ ] Uses GenAI reasoning over Python automation
   - [ ] Relies on hooks for enforcement, agents for intelligence
   - [ ] OR: Violates constraints (bloat)

3. **Is this the minimal solution?**
   - [ ] Solves real observed problem (not hypothetical)
   - [ ] Can't be solved by existing features
   - [ ] Can't be solved by documentation/config
   - [ ] OR: Over-engineered solution (bloat)

**Decision**:
- ✅ **Proceed** if all 3 checks pass
- ⚠️ **Redesign** if any check fails
- ❌ **Close** if fundamentally misaligned

---

### Gate 2: Design Review (DURING Planning)

**Before writing code, validate:**

1. **Complexity Check**
   - [ ] Solution requires ≤ 200 lines of code
   - [ ] Adds ≤ 1 new file (prefer editing existing)
   - [ ] Adds ≤ 1 new dependency
   - [ ] OR: Too complex (bloat)

2. **Observability Over Automation**
   - [ ] Makes existing behavior visible (good)
   - [ ] OR: Adds new automated behavior (check if needed)

3. **Duplication Check**
   - [ ] No existing agent/hook/command does this
   - [ ] Can't enhance existing feature instead
   - [ ] OR: Duplicates existing capability (bloat)

**Decision**:
- ✅ **Continue** if checks pass
- ⚠️ **Simplify** if failing complexity/duplication
- ❌ **Stop** if duplicating existing work

---

### Gate 3: Implementation Validation (DURING Coding)

**As you code, monitor:**

1. **Scope Creep Detection**
   - [ ] Only implementing what issue describes
   - [ ] Not adding "nice to have" features
   - [ ] Not refactoring unrelated code
   - [ ] OR: Scope has grown (bloat creeping in)

2. **Abstraction Check**
   - [ ] Using existing patterns/utilities
   - [ ] Not creating new frameworks
   - [ ] Not over-generalizing
   - [ ] OR: Building too much infrastructure (bloat)

3. **Testing Overhead**
   - [ ] Tests are proportional to code (1:1 or 2:1 ratio)
   - [ ] Not testing hypothetical edge cases
   - [ ] OR: Test bloat exceeding implementation value

**Action**:
- ✅ **Commit** if passing all checks
- ⚠️ **Refactor** if scope/abstraction creep detected
- ❌ **Rollback** if bloat has taken over

---

### Gate 4: Post-Implementation Review

**After implementation, before PR:**

1. **Value Delivered**
   - [ ] Solves stated problem completely
   - [ ] Improved autonomous execution measurably
   - [ ] User sees benefit without reading code
   - [ ] OR: Added complexity without clear value (bloat)

2. **Maintenance Burden**
   - [ ] Documentation updated (not just code comments)
   - [ ] Future maintainer can understand in < 5 min
   - [ ] No new ongoing manual processes required
   - [ ] OR: Created maintenance debt (bloat)

3. **Integration Health**
   - [ ] Works with existing hooks/agents/commands
   - [ ] Didn't break existing workflows
   - [ ] Didn't require changes to 3+ other files
   - [ ] OR: Created integration complexity (bloat)

**Decision**:
- ✅ **Merge** if all checks pass
- ⚠️ **Simplify** if maintenance/integration issues
- ❌ **Close PR** if bloat outweighs value

---

## Issue Categorization Template

### ✅ IMPLEMENT (Aligns with intent)

**Criteria**: Directly advances autonomous execution, respects constraints, minimal solution

**Examples**:
- #37: Enable auto-orchestration (core autonomous behavior)
- #38: Update CLAUDE.md (documentation sync)
- Observability features that make existing behavior visible

### ⚠️ REDESIGN (Intent good, approach has bloat)

**Criteria**: Good goal, but solution violates constraints or is over-engineered

**Examples**:
- Issue wants auto-git BUT violates "minimal intervention" principle
- Issue wants new command BUT exceeds 8-command limit
- Issue wants Python orchestration BUT violates "GenAI reasoning" constraint

**Action**: Redesign to achieve goal within constraints

### ❌ CLOSE (Bloat or misaligned)

**Criteria**: Doesn't serve primary mission, solves hypothetical problem, or duplicates existing

**Examples**:
- Features for problems not yet observed in practice
- Automation where observability would suffice
- New commands when existing commands could be enhanced

---

## Red Flags (Immediate Bloat Indicators)

Stop and reassess if you see:

- 🚩 "This will be useful in the future" (hypothetical problem)
- 🚩 "We should also handle X, Y, Z cases" (scope creep)
- 🚩 "Let's create a framework for..." (over-abstraction)
- 🚩 "This needs a new command" (exceeding 8-command limit)
- 🚩 "We need to automate..." (before trying observability)
- 🚩 File count growing > 5% for single feature
- 🚩 Test time increasing > 10% for single feature
- 🚩 Documentation growing > 20% for single feature

---

## Quick Decision Tree

```
Is this issue solving a REAL problem I've observed?
├─ No → CLOSE (hypothetical bloat)
└─ Yes
    └─ Can existing features solve it with config/docs?
        ├─ Yes → CLOSE (use existing, document solution)
        └─ No
            └─ Does solution require ≤ 200 LOC and respect constraints?
                ├─ Yes → IMPLEMENT (validated)
                └─ No → REDESIGN (simplify or scope down)
```

---

## Usage

**Before each implementation:**
1. Run through Gate 1 (Alignment Check)
2. Document decision in issue comments
3. Proceed only if validated

**During implementation:**
1. Check Gate 2 (Design) before coding
2. Monitor Gate 3 (Implementation) while coding
3. Stop if red flags appear

**After implementation:**
1. Run Gate 4 (Post-Implementation)
2. Get reviewer feedback on bloat
3. Merge only if passing all gates

---

**Remember**: The goal is **autonomous execution with professional quality**, not **maximum features**.

Every line of code is a liability. Only add code that directly serves the primary mission.
