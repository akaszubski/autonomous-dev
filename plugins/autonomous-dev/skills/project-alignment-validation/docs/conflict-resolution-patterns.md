# Conflict Resolution Patterns

Strategies and workflows for resolving alignment conflicts between PROJECT.md and implementation, or between different PROJECT.md sections.

---

## Types of Conflicts

### 1. Goal Conflicts
**Definition**: Feature serves one goal but undermines another

**Example**:
- Goal A: "Fast development velocity"
- Goal B: "High code quality standards"
- Conflict: Strict quality checks slow velocity

**Detection**: Feature benefits one goal while harming another

---

### 2. Scope Conflicts
**Definition**: Feature is in scope but conflicts with out-of-scope boundaries

**Example**:
- In scope: "Basic user authentication"
- Out of scope: "Third-party integrations"
- Conflict: OAuth requires third-party provider integration

**Detection**: Feature touches explicitly excluded areas

---

### 3. Constraint Conflicts
**Definition**: Feature serves goals but violates constraints

**Example**:
- Goal: "Real-time notifications"
- Constraint: "No WebSocket infrastructure"
- Conflict: Real-time requires WebSockets or expensive polling

**Detection**: Feature requires violating stated limitations

---

### 4. Architecture Conflicts
**Definition**: Feature serves goals but breaks architectural principles

**Example**:
- Goal: "Quick MVP launch"
- Architecture: "Microservices with event sourcing"
- Conflict: Microservices add complexity that slows MVP

**Detection**: Feature requires deviating from design patterns

---

### 5. Documentation-Implementation Conflicts
**Definition**: PROJECT.md says one thing, code does another

**Example**:
- PROJECT.md: "Python 3.9+ compatible"
- Code: Uses Python 3.11+ features (match statement)
- Conflict: Documentation doesn't match reality

**Detection**: Automated checks, code reviews, gap assessment

---

## Resolution Strategies

### Strategy 1: Update PROJECT.md

**When to Use**:
- Current implementation is correct
- PROJECT.md is outdated or wrong
- Strategic direction has changed
- Reality better serves goals than documented state

**Process**:
```markdown
1. Verify current state is intentional (not accidental drift)
2. Confirm current state better serves goals
3. Update PROJECT.md to reflect reality
4. Document rationale for change
5. Communicate change to stakeholders
```

**Example**:
```markdown
**Conflict**: PROJECT.md says "REST only", code has GraphQL endpoint

**Analysis**:
- GraphQL endpoint serves "flexible querying" goal better than REST
- GraphQL was added intentionally after PROJECT.md written
- Team agreed GraphQL improves API usability

**Resolution**: Update PROJECT.md scope to include GraphQL
- Update SCOPE: "REST and GraphQL APIs"
- Update ARCHITECTURE: Add GraphQL patterns
- Document why GraphQL added (better goal alignment)

**Outcome**: Documentation matches reality, alignment restored
```

---

### Strategy 2: Modify Implementation

**When to Use**:
- PROJECT.md is correct
- Implementation drifted from plan
- Feature doesn't actually serve goals
- Constraint violation is real problem

**Process**:
```markdown
1. Confirm PROJECT.md represents current strategy
2. Identify what needs to change in code
3. Create refactoring plan
4. Implement changes to align with PROJECT.md
5. Validate alignment restored
```

**Example**:
```markdown
**Conflict**: PROJECT.md says "< 200ms response time", actual is 500ms

**Analysis**:
- Performance constraint is valid (user experience requirement)
- Slow response time hurts "good UX" goal
- No strategic reason to change constraint

**Resolution**: Improve implementation to meet constraint
- Add caching layer (Redis)
- Optimize database queries (add indexes)
- Implement async processing for heavy operations
- Target: Bring response time to < 200ms

**Outcome**: Implementation aligns with constraint, goal served
```

---

### Strategy 3: Negotiate Compromise

**When to Use**:
- Both PROJECT.md and implementation have merit
- Pure adherence to either side creates problems
- Trade-offs needed to serve multiple goals
- Context has changed since PROJECT.md written

**Process**:
```markdown
1. Identify what's valuable in both sides
2. Find middle ground that serves goals
3. Update PROJECT.md to reflect compromise
4. Adjust implementation as needed
5. Document trade-offs and rationale
```

**Example**:
```markdown
**Conflict**:
- PROJECT.md: "80% test coverage minimum"
- Reality: 60% coverage, team struggling to reach 80%

**Analysis**:
- 80% coverage goal serves "quality" objective
- Team velocity suffering trying to reach 80%
- Some code is low-risk, doesn't need extensive tests
- Critical paths are well-tested (authentication, payments)

**Resolution**: Compromise on tiered coverage requirements
- Critical paths: 90% coverage (authentication, payments, security)
- Core features: 75% coverage (main user workflows)
- Utilities: 60% coverage (helpers, formatters)
- Overall target: 70% average (still high quality)

**Updates**:
- PROJECT.md: Update constraint to tiered approach
- Implementation: Focus testing on critical paths first
- Document rationale: Risk-based testing strategy

**Outcome**: Quality maintained where it matters, velocity improved
```

---

### Strategy 4: Escalate Decision

**When to Use**:
- Conflict involves strategic direction
- Resolution requires business/stakeholder input
- Technical team can't resolve alone
- Impacts other teams or external commitments

**Process**:
```markdown
1. Document conflict clearly
2. Present options with trade-offs
3. Identify stakeholders who should decide
4. Escalate with recommendation
5. Implement decided resolution
6. Update PROJECT.md accordingly
```

**Example**:
```markdown
**Conflict**:
- Goal: "Launch MVP in 6 weeks"
- Architecture: "Event-driven microservices"
- Conflict: Microservices complexity will delay MVP by 8 weeks

**Options for Stakeholders**:

**Option A**: Keep timeline, change architecture
- Pros: Launch on time, prove market fit faster
- Cons: Technical debt, harder to scale later
- Recommendation: Start with monolith, migrate to microservices later

**Option B**: Keep architecture, extend timeline
- Pros: Correct architecture from day 1, easier scaling
- Cons: Delayed launch, market opportunity risk

**Option C**: Hybrid approach
- Pros: Modular monolith, easier migration path
- Cons: Some architectural compromise

**Escalation**: Present to product owner and CTO

**Decision**: Option C - Modular monolith
- Update ARCHITECTURE: "Modular monolith with clear boundaries"
- Update timeline: 7 weeks (1 week buffer)
- Document migration path to microservices for future

**Outcome**: Strategic decision made with full context
```

---

## Conflict Resolution Workflow

### Step 1: Identify Conflict

**Conflict Documentation**:
```markdown
## Conflict Report

**Conflict ID**: [Unique identifier]
**Detected Date**: [YYYY-MM-DD]
**Detected By**: [Name/Tool]

**Type**: [Goal / Scope / Constraint / Architecture / Documentation]

**Description**:
[Clear description of the conflict]

**Affected Sections**:
- PROJECT.md: [Which section(s)]
- Code: [Which component(s)]

**Current State**:
[What exists today]

**Documented State** (PROJECT.md):
[What PROJECT.md says should exist]

**Impact**:
[How conflict affects project]
```

---

### Step 2: Analyze Root Cause

**Analysis Questions**:
1. Why does this conflict exist?
2. When did the conflict first appear?
3. Was the conflict intentional or accidental?
4. Which side (PROJECT.md or code) is "correct"?
5. What would happen if we do nothing?

**Root Cause Template**:
```markdown
## Root Cause Analysis

**Primary Cause**: [Main reason conflict exists]

**Contributing Factors**:
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

**Timeline**:
- [Date]: PROJECT.md stated [X]
- [Date]: Code implemented [Y]
- [Date]: Conflict detected

**Intentional or Drift?**: [Intentional decision / Accidental drift]
```

---

### Step 3: Evaluate Options

**Option Evaluation Template**:
```markdown
## Resolution Options

### Option 1: [Name]
**Approach**: [What we would do]
**Pros**:
- [Pro 1]
- [Pro 2]
**Cons**:
- [Con 1]
- [Con 2]
**Effort**: [Low / Medium / High]
**Risk**: [Low / Medium / High]
**Impact on Goals**: [Positive / Neutral / Negative]

### Option 2: [Name]
[Repeat template]

### Option 3: [Name]
[Repeat template]

### Recommended Option: [Number]
**Rationale**: [Why this option is best]
```

---

### Step 4: Select Resolution Strategy

**Decision Matrix**:
```markdown
| Strategy               | When to Use                    | Risk  | Effort | Timeline |
|------------------------|--------------------------------|-------|--------|----------|
| Update PROJECT.md      | Documentation outdated         | Low   | Low    | 1 day    |
| Modify Implementation  | Code drifted from plan         | Med   | High   | 2 weeks  |
| Negotiate Compromise   | Both sides have merit          | Med   | Med    | 1 week   |
| Escalate Decision      | Strategic/business decision    | Low   | Low    | Varies   |
```

---

### Step 5: Implement Resolution

**Implementation Plan**:
```markdown
## Implementation Plan

**Selected Strategy**: [Name]

**Action Items**:
1. [Task 1] - Owner: [Name] - Due: [Date]
2. [Task 2] - Owner: [Name] - Due: [Date]
3. [Task 3] - Owner: [Name] - Due: [Date]

**PROJECT.md Updates** (if applicable):
- Section: [Name]
- Changes: [What will change]
- Rationale: [Why]

**Code Changes** (if applicable):
- Components: [List]
- Changes: [What will change]
- Testing: [How to validate]

**Communication**:
- Stakeholders: [Who needs to know]
- Message: [What to communicate]
- Timeline: [When to communicate]
```

---

### Step 6: Validate Resolution

**Validation Checklist**:
```markdown
## Resolution Validation

- [ ] Conflict resolved (no longer exists)
- [ ] PROJECT.md updated (if needed)
- [ ] Code updated (if needed)
- [ ] Tests pass
- [ ] Documentation reflects changes
- [ ] Stakeholders informed
- [ ] No new conflicts introduced
- [ ] Rationale documented
```

---

### Step 7: Document Outcome

**Resolution Report**:
```markdown
## Conflict Resolution Report

**Conflict**: [ID and description]
**Resolution Date**: [YYYY-MM-DD]
**Resolved By**: [Name/Team]

**Strategy Used**: [Which strategy]

**Actions Taken**:
1. [Action 1]
2. [Action 2]
3. [Action 3]

**Changes Made**:
- PROJECT.md: [Changes or "No changes"]
- Code: [Changes or "No changes"]

**Rationale**:
[Why this resolution was chosen]

**Outcome**: ✓ Success / ⚠ Partial / ✗ Failed

**Lessons Learned**:
- [Lesson 1]
- [Lesson 2]

**Follow-up Items**:
- [Item 1] - Due: [Date]
- [Item 2] - Due: [Date]
```

---

## Common Conflict Scenarios

### Scenario 1: Fast Iteration vs High Quality

**Conflict**: Goal tension between speed and quality

**Resolution Pattern**: Time-boxed quality levels
```markdown
**Compromise**:
- MVP phase: 60% test coverage, basic code review
- Beta phase: 75% test coverage, thorough review
- Production: 80% test coverage, strict review

**Rationale**: Quality scales with product maturity
```

---

### Scenario 2: Feature Scope vs Timeline Constraint

**Conflict**: Desired features exceed timeline budget

**Resolution Pattern**: Phased delivery
```markdown
**Compromise**:
- Phase 1 (MVP): Core features only, meet deadline
- Phase 2 (Enhancement): Additional features, +2 weeks
- Phase 3 (Polish): Nice-to-haves, +2 weeks

**Rationale**: Incremental value delivery
```

---

### Scenario 3: Ideal Architecture vs Resource Constraint

**Conflict**: Best architecture requires more resources than available

**Resolution Pattern**: Progressive enhancement
```markdown
**Compromise**:
- Start: Simple architecture within constraints
- Build: Add complexity as resources allow
- Evolve: Refactor toward ideal over time

**Rationale**: Pragmatic architecture evolution
```

---

### Scenario 4: Documentation Outdated vs Code Correct

**Conflict**: Code evolved, documentation didn't

**Resolution Pattern**: Documentation sprint
```markdown
**Resolution**:
- Schedule documentation update sprint
- Update PROJECT.md to match current reality
- Add documentation to CI/CD checks
- Prevent future drift

**Rationale**: Keep documentation as code artifact
```

---

## Prevention Strategies

### 1. Regular Alignment Reviews
- **Frequency**: Monthly
- **Scope**: Check PROJECT.md vs reality
- **Outcome**: Early conflict detection

### 2. Documentation in PR Process
- **Requirement**: PR checklist includes PROJECT.md check
- **Review**: Reviewer validates alignment
- **Update**: PROJECT.md updated with feature if needed

### 3. Automated Checks
- **CI/CD**: Run alignment validation on every commit
- **Alerts**: Notify team of potential conflicts
- **Reports**: Weekly alignment health report

### 4. Living Documentation
- **Mindset**: PROJECT.md is code, not static doc
- **Updates**: Update PROJECT.md as you learn
- **Reviews**: Quarterly PROJECT.md health check

---

## Escalation Criteria

**Escalate to Tech Lead when**:
- Conflict involves architecture decisions
- Multiple approaches have equal trade-offs
- Impact spans multiple teams

**Escalate to Product Owner when**:
- Conflict involves product strategy
- Scope/timeline trade-offs needed
- Business priority unclear

**Escalate to Stakeholders when**:
- Conflict involves budget or resources
- Strategic direction decision needed
- External commitments at risk

---

## Best Practices

1. **Address conflicts early**: Don't let them fester
2. **Document rationale**: Record why decisions made
3. **Involve right people**: Don't resolve strategic conflicts alone
4. **Update PROJECT.md**: Keep documentation current
5. **Learn from conflicts**: Each one teaches something
6. **Prevent recurrence**: Fix process that allowed conflict

---

## Success Criteria

Conflict resolution is successful when:
- ✓ Conflict no longer exists
- ✓ Resolution serves project goals
- ✓ All stakeholders aligned
- ✓ PROJECT.md and code consistent
- ✓ Rationale documented
- ✓ No new conflicts introduced
- ✓ Process improved to prevent similar conflicts

---

**See Also**:
- `alignment-checklist.md` - Prevent conflicts through systematic validation
- `semantic-validation-approach.md` - Understand intent to resolve conflicts better
- `gap-assessment-methodology.md` - Identify conflicts as gaps
- `../templates/conflict-resolution-template.md` - Template for conflict resolution
- `../examples/alignment-scenarios.md` - Real-world conflict resolutions
