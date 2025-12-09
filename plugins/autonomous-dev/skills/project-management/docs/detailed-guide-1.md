# Project Management - Detailed Guide

## When This Skill Activates

- Creating or updating PROJECT.md files
- Defining project goals and scope
- Planning sprints or milestones
- Validating alignment with goals
- Project roadmap creation
- Keywords: "project.md", "goals", "scope", "sprint", "milestone", "roadmap"

---

## PROJECT.md Template

### Core Structure

```markdown
# Project Context - [PROJECT NAME]

**Last Updated**: YYYY-MM-DD
**Project**: [Brief one-line description]
**Version**: vX.Y.Z

---

## GOALS ⭐

**What success looks like for this project**:

1. **[Primary Goal]** - [Description of what "done" means]
2. **[Secondary Goal]** - [Description]
3. **[Tertiary Goal]** - [Description]

**Success Metrics**:
- **[Metric 1]**: [Target value] (how we measure goal 1)
- **[Metric 2]**: [Target value] (how we measure goal 2)
- **[Metric 3]**: [Target value] (how we measure goal 3)

---

## SCOPE

**What's IN Scope** ✅ (Features we build):

**[Category 1]**:
- ✅ **[Feature 1]** - [Description]
- ✅ **[Feature 2]** - [Description]

**[Category 2]**:
- ✅ **[Feature 3]** - [Description]
- ✅ **[Feature 4]** - [Description]

**What's OUT of Scope** ❌ (Explicitly not building):

- ❌ **[Anti-feature 1]** - [Why we're not building this]
- ❌ **[Anti-feature 2]** - [Why we're not building this]

---

## CONSTRAINTS

**Technical Constraints**:
- **[Constraint 1]**: [Description and rationale]
- **[Constraint 2]**: [Description and rationale]

**Resource Constraints**:
- **Budget**: [Amount/limit]
- **Timeline**: [Deadline or duration]
- **Team size**: [Number of developers]

**External Dependencies**:
- **[Dependency 1]**: [Impact on project]
- **[Dependency 2]**: [Impact on project]

---

## ARCHITECTURE

**High-Level Design**:
[Brief description of system architecture]

**Key Technologies**:
- **Language**: [Python, JavaScript, etc.]
- **Framework**: [Django, React, etc.]
- **Database**: [PostgreSQL, MongoDB, etc.]
- **Infrastructure**: [AWS, Docker, Kubernetes, etc.]

**Design Principles**:
1. **[Principle 1]** - [Why this matters]
2. **[Principle 2]** - [Why this matters]

---

## CURRENT SPRINT

**Sprint**: [Sprint name or number]
**Dates**: [Start] to [End]
**Goal**: [What we're achieving this sprint]

**In Progress**:
- [ ] [Task 1] (assigned to [name])
- [ ] [Task 2] (assigned to [name])

**Planned**:
- [ ] [Task 3]
- [ ] [Task 4]

---

## ROADMAP

### Phase 1: [Name] (Months 1-2)
- [ ] [Milestone 1]
- [ ] [Milestone 2]

### Phase 2: [Name] (Months 3-4)
- [ ] [Milestone 3]
- [ ] [Milestone 4]

### Phase 3: [Name] (Months 5-6)
- [ ] [Milestone 5]
- [ ] [Milestone 6]

---

## DECISIONS

**Key Architectural Decisions**:
1. **[Decision 1]** - [Rationale] (see ADR-001)
2. **[Decision 2]** - [Rationale] (see ADR-002)

**Deferred Decisions**:
- **[Decision]** - [Why we're waiting and what we need to know]

---

## RISKS

**High Priority**:
- **[Risk 1]**: [Impact] - [Mitigation strategy]

**Medium Priority**:
- **[Risk 2]**: [Impact] - [Mitigation strategy]

---

## TEAM

**Roles**:
- **Tech Lead**: [Name]
- **Product Owner**: [Name]
- **Developers**: [Names]
- **Reviewers**: [Names]

**Communication**:
- **Daily standup**: [Time and location]
- **Sprint planning**: [Frequency]
- **Retro**: [Frequency]

---

**For detailed ADRs**: See `docs/adr/`
**For sprint history**: See `docs/sprints/`
```

---

## Goal-Setting Frameworks

### SMART Goals

**S**pecific - **M**easurable - **A**chievable - **R**elevant - **T**ime-bound

#### Bad Goal (Vague)
```markdown
## GOALS
