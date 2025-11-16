# Gap Assessment Methodology

Systematic approach for identifying, prioritizing, and documenting gaps between current state and desired state defined in PROJECT.md.

---

## Overview

**Gap**: Difference between where you are (current state) and where you want to be (desired state per PROJECT.md)

**Gap Assessment**: Process of identifying, analyzing, prioritizing, and documenting these differences

---

## Types of Gaps

### 1. Feature Gaps
**Definition**: Missing functionality needed to achieve goals

**Examples**:
- Goal: "User authentication" → Current: No login system
- Goal: "API rate limiting" → Current: Unlimited API access
- Goal: "Audit logging" → Current: No activity tracking

**Detection**:
- Review GOALS section for desired outcomes
- Compare with current feature list
- Identify missing capabilities

---

### 2. Documentation Gaps
**Definition**: PROJECT.md doesn't reflect actual implementation

**Examples**:
- PROJECT.md: "Python 3.9+" → Reality: Using Python 3.11 features
- PROJECT.md: "REST API only" → Reality: GraphQL endpoint exists
- PROJECT.md: "No caching" → Reality: Redis cache implemented

**Detection**:
- Review PROJECT.md claims
- Compare with actual codebase
- Identify documentation drift

---

### 3. Constraint Violations
**Definition**: Implementation violates stated constraints

**Examples**:
- Constraint: "Response time < 200ms" → Reality: 500ms average
- Constraint: "80% test coverage" → Reality: 45% coverage
- Constraint: "No GPL dependencies" → Reality: Uses GPL library

**Detection**:
- Review CONSTRAINTS section
- Measure actual system behavior
- Identify violations

---

### 4. Architectural Gaps
**Definition**: Code doesn't follow stated design principles

**Examples**:
- Architecture: "Microservices" → Reality: Monolithic codebase
- Architecture: "Event-driven" → Reality: Synchronous calls
- Architecture: "Stateless services" → Reality: In-memory session storage

**Detection**:
- Review ARCHITECTURE section
- Analyze code structure and patterns
- Identify deviations

---

## Gap Identification Process

### Step 1: Baseline Analysis

**Collect Current State**:
```markdown
## Current State Inventory

### Implemented Features
- [List all current features and capabilities]

### Technology Stack
- [List all technologies, frameworks, libraries in use]

### Performance Metrics
- [Current response times, throughput, resource usage]

### Test Coverage
- [Current coverage percentage, test types]

### Architecture Patterns
- [Current design patterns, component structure]
```

---

### Step 2: Desired State Definition

**Extract from PROJECT.md**:
```markdown
## Desired State (from PROJECT.md)

### GOALS
- [List all project goals]

### SCOPE
- In scope: [Features that should exist]
- Out of scope: [Features that should NOT exist]

### CONSTRAINTS
- [Technical, resource, and policy constraints]

### ARCHITECTURE
- [Design principles and patterns]
```

---

### Step 3: Gap Comparison

**Create Comparison Matrix**:
```markdown
| Area          | Desired State (PROJECT.md) | Current State (Reality) | Gap Type | Priority |
|---------------|---------------------------|-------------------------|----------|----------|
| Authentication| JWT-based auth            | No auth system          | Feature  | Critical |
| API Response  | < 200ms                   | ~500ms average          | Constraint| High    |
| Test Coverage | 80% minimum               | 45% actual              | Constraint| Medium  |
| Architecture  | Microservices             | Monolith                | Architectural| Low |
```

---

### Step 4: Root Cause Analysis

For each gap, identify why it exists:

**Common Root Causes**:
1. **Incomplete Implementation**: Feature partially built, not finished
2. **Technical Debt**: Shortcuts taken to meet deadlines
3. **Scope Creep**: Features added without updating PROJECT.md
4. **Changing Requirements**: Goals evolved, documentation didn't
5. **Knowledge Gaps**: Team didn't know about constraint/pattern
6. **Resource Constraints**: Ran out of time/budget/people

**Analysis Template**:
```markdown
## Gap Root Cause Analysis

**Gap**: [Name of gap]

**Root Cause**: [Why gap exists]

**Contributing Factors**:
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

**Impact**: [How gap affects project]

**Trend**: [Getting better / worse / stable]
```

---

## Gap Prioritization

### Two-Dimensional Prioritization

**Dimension 1: Impact** (on project success)
- **Critical**: Blocks primary goals, violates hard constraints, affects users
- **High**: Significantly delays goals, creates technical debt
- **Medium**: Slows progress, reduces quality
- **Low**: Minor inconvenience, cosmetic issues

**Dimension 2: Effort** (to close gap)
- **Quick Win**: 1-2 days, minimal dependencies
- **Tactical**: 1-2 weeks, moderate complexity
- **Strategic**: 1-2 months, significant effort
- **Epic**: 3+ months, major initiative

---

### Prioritization Matrix

```
         Low Effort      Medium Effort    High Effort
       ┌──────────────┬──────────────┬──────────────┐
High   │              │              │              │
Impact │  QUICK WINS  │   TACTICAL   │  STRATEGIC   │
       │  (Do First)  │  (Schedule)  │   (Plan)     │
       ├──────────────┼──────────────┼──────────────┤
Medium │              │              │              │
Impact │   TACTICAL   │   BALANCED   │   DEFER      │
       │  (Do Next)   │  (Evaluate)  │ (Low Priority)│
       ├──────────────┼──────────────┼──────────────┤
Low    │              │              │              │
Impact │   BACKLOG    │    DEFER     │  DON'T DO    │
       │  (If Time)   │ (Low Value)  │ (Waste)      │
       └──────────────┴──────────────┴──────────────┘
```

---

### Priority Scoring Formula

**Impact Score** (0-10):
- User impact: 0-3 points
- Business impact: 0-3 points
- Technical impact: 0-2 points
- Risk impact: 0-2 points

**Effort Score** (0-10):
- Time: 0-3 points (more time = higher score)
- Complexity: 0-3 points
- Dependencies: 0-2 points
- Risk: 0-2 points

**Priority Score** = Impact Score - (Effort Score * 0.5)

**Interpretation**:
- Score ≥ 7: Critical priority (Quick Win)
- Score 4-6: High priority (Tactical)
- Score 1-3: Medium priority (Balanced)
- Score ≤ 0: Low priority (Defer)

---

## Gap Documentation

### Standard Gap Report Template

```markdown
# Gap Assessment Report

**Date**: [YYYY-MM-DD]
**Assessed By**: [Name/Team]
**Project**: [Project Name]

---

## Executive Summary

**Total Gaps Identified**: [Number]
- Critical: [Count]
- High: [Count]
- Medium: [Count]
- Low: [Count]

**Recommended Actions**: [High-level summary]

---

## Gap Details

### Gap #1: [Gap Name]

**Type**: [Feature / Documentation / Constraint / Architectural]

**Current State**:
[Describe what exists today]

**Desired State** (per PROJECT.md):
[Describe what PROJECT.md defines]

**Gap Analysis**:
[Explain the specific difference]

**Root Cause**:
[Why gap exists]

**Impact**: [Critical / High / Medium / Low]
- User impact: [Description]
- Business impact: [Description]
- Technical impact: [Description]

**Effort**: [Quick Win / Tactical / Strategic / Epic]
- Estimated time: [Duration]
- Complexity: [Low / Medium / High]
- Dependencies: [List]

**Priority Score**: [Number]

**Recommended Action**:
[Specific steps to close gap]

**Dependencies**:
- [Dependency 1]
- [Dependency 2]

**Risks**:
- [Risk 1]
- [Risk 2]

**Success Criteria**:
[How to verify gap is closed]

---

### Gap #2: [Next gap...]

[Repeat template]

---

## Prioritized Action Plan

### Phase 1: Quick Wins (Week 1-2)
1. [Gap name] - [Brief action]
2. [Gap name] - [Brief action]

### Phase 2: Tactical (Week 3-6)
1. [Gap name] - [Brief action]
2. [Gap name] - [Brief action]

### Phase 3: Strategic (Month 2-3)
1. [Gap name] - [Brief action]
2. [Gap name] - [Brief action]

### Deferred (Re-evaluate Q[X])
1. [Gap name] - [Reason for deferral]
2. [Gap name] - [Reason for deferral]

---

## Risk Assessment

**High-Risk Gaps** (could block project success):
- [Gap name] - [Risk description]

**Mitigation Strategies**:
- [Strategy 1]
- [Strategy 2]

---

## Resource Requirements

**Team Allocation**:
- Developer time: [Hours/days]
- Designer time: [Hours/days]
- QA time: [Hours/days]

**Budget Requirements**:
- Infrastructure: [Cost]
- Tools/licenses: [Cost]
- Training: [Cost]

**Timeline**:
- Start date: [Date]
- Completion target: [Date]

---

## Success Metrics

**How we'll measure progress**:
1. [Metric 1] - Target: [Value]
2. [Metric 2] - Target: [Value]
3. [Metric 3] - Target: [Value]

**Review Cadence**: [Weekly / Biweekly / Monthly]

---

## Appendices

### Appendix A: Full Gap List
[Complete list of all gaps]

### Appendix B: PROJECT.md Reference
[Relevant sections from PROJECT.md]

### Appendix C: Current State Metrics
[Detailed current state measurements]
```

---

## Gap Closure Workflow

### 1. Select Gap to Close

**Criteria**:
- Highest priority score
- Dependencies resolved
- Resources available
- Strategic timing

---

### 2. Plan Closure

**Create Action Plan**:
```markdown
## Gap Closure Plan

**Gap**: [Name]

**Approach**: [How we'll close the gap]

**Tasks**:
1. [Task 1] - Owner: [Name] - Due: [Date]
2. [Task 2] - Owner: [Name] - Due: [Date]
3. [Task 3] - Owner: [Name] - Due: [Date]

**Milestones**:
- [Milestone 1] - [Date]
- [Milestone 2] - [Date]

**Validation**:
[How we'll verify gap is closed]
```

---

### 3. Execute Plan

**Track Progress**:
- Daily standups for status updates
- Weekly reviews of milestone completion
- Blockers escalated immediately
- Scope changes documented and approved

---

### 4. Validate Closure

**Verification Checklist**:
- [ ] Current state matches desired state
- [ ] Tests pass (if applicable)
- [ ] Documentation updated
- [ ] Stakeholders approve
- [ ] No new gaps introduced
- [ ] PROJECT.md updated (if needed)

---

### 5. Document Results

**Closure Report**:
```markdown
## Gap Closure Report

**Gap**: [Name]
**Closed Date**: [Date]

**Actions Taken**:
1. [Action 1]
2. [Action 2]
3. [Action 3]

**Outcome**: ✓ Success / ⚠ Partial / ✗ Failed

**Lessons Learned**:
- [Lesson 1]
- [Lesson 2]

**Follow-up Items**:
- [Item 1]
- [Item 2]
```

---

## Continuous Gap Assessment

### Regular Reviews

**Cadence**:
- **Weekly**: Review critical gaps progress
- **Monthly**: Full gap assessment for new gaps
- **Quarterly**: Strategic review and re-prioritization

**Review Process**:
1. Check for new gaps (code changes, PROJECT.md updates)
2. Re-assess priority of existing gaps (context may have changed)
3. Validate closed gaps (ensure they stay closed)
4. Update action plan based on progress and changes

---

### Gap Trend Analysis

**Track Over Time**:
```markdown
## Gap Trend Analysis

**Period**: [Start Date] to [End Date]

**Gap Count Trend**:
- Week 1: [Count] gaps
- Week 2: [Count] gaps
- Week 3: [Count] gaps
- Week 4: [Count] gaps

**Trend**: ↗ Increasing / → Stable / ↘ Decreasing

**Analysis**:
[Why is trend moving this direction?]

**Corrective Actions** (if increasing):
1. [Action to reduce gap creation]
2. [Action to accelerate gap closure]
```

---

## Common Pitfalls

### 1. Ignoring Small Gaps
**Problem**: "It's just a small documentation issue"
**Impact**: Small gaps accumulate into large drift over time
**Solution**: Fix small gaps immediately (5-minute rule)

### 2. Analysis Paralysis
**Problem**: Spending weeks analyzing instead of closing gaps
**Impact**: Gaps grow while you plan
**Solution**: Time-box analysis (max 2 days), then start closing

### 3. Perfectionism
**Problem**: "We can't proceed until all gaps are closed"
**Impact**: Project stalls waiting for 100% alignment
**Solution**: Close critical gaps, manage others as tech debt

### 4. Ignoring Root Causes
**Problem**: Closing gaps without fixing underlying issues
**Impact**: Same gaps reappear
**Solution**: Always identify and address root cause

### 5. Poor Prioritization
**Problem**: Working on low-impact gaps first
**Impact**: Critical gaps remain while resources spent on nice-to-haves
**Solution**: Use impact/effort matrix religiously

---

## Best Practices

1. **Automate Detection**: Use scripts to detect common gaps (version mismatches, constraint violations)
2. **Integrate with CI/CD**: Run gap checks on every commit
3. **Visualize Trends**: Charts and dashboards for gap trends
4. **Celebrate Closures**: Recognize team for closing gaps
5. **Learn from Gaps**: Each gap is a learning opportunity
6. **Keep PROJECT.md Updated**: Prevent documentation gaps by updating regularly

---

## Success Criteria

Gap assessment is successful when:
- ✓ All gaps identified and documented
- ✓ Priorities clearly defined with rationale
- ✓ Action plan created and resourced
- ✓ Progress tracked and visible
- ✓ Gaps closing faster than new gaps appearing
- ✓ Root causes addressed, not just symptoms
- ✓ Stakeholders aligned on priorities and timeline

---

**See Also**:
- `alignment-checklist.md` - Systematic validation to prevent gaps
- `semantic-validation-approach.md` - Understanding intent to identify real gaps
- `conflict-resolution-patterns.md` - Resolving gaps between competing requirements
- `../templates/gap-assessment-template.md` - Template for gap documentation
- `../examples/misalignment-examples.md` - Real-world gap examples
