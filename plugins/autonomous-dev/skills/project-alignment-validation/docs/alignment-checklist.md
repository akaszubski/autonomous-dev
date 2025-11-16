# PROJECT.md Alignment Checklist

Comprehensive checklist for validating features against PROJECT.md. Use this for systematic validation of GOALS, SCOPE, CONSTRAINTS, and ARCHITECTURE alignment.

---

## Quick Reference

### Four-Section Validation
1. ✓ **GOALS**: Does feature serve project objectives?
2. ✓ **SCOPE**: Is feature in scope and boundaries respected?
3. ✓ **CONSTRAINTS**: Does feature work within limitations?
4. ✓ **ARCHITECTURE**: Does feature follow design principles?

---

## GOALS Alignment Checklist

### Primary Validation
- [ ] **Serves at least one goal**: Feature directly supports a defined project goal
- [ ] **No goal conflicts**: Feature doesn't contradict or undermine other goals
- [ ] **Priority alignment**: Feature priority matches goal importance
- [ ] **Measurable impact**: Can verify feature contributes to goal metrics

### Example Questions
- Which specific goal does this feature serve?
- How does this feature move us toward achieving that goal?
- Are there any goals this feature might conflict with?
- Can we measure success in terms of goal achievement?

### Red Flags
- ❌ Feature doesn't map to any defined goal
- ❌ Feature is "nice to have" but doesn't serve strategy
- ❌ Feature conflicts with higher-priority goals
- ❌ Success metrics don't align with goal metrics

### Resolution
- **Option 1**: Refine feature to serve existing goal
- **Option 2**: Add new goal to PROJECT.md (if strategic)
- **Option 3**: Defer or reject feature (if not strategic)

---

## SCOPE Alignment Checklist

### In-Scope Validation
- [ ] **Explicitly in scope**: Feature matches defined scope boundaries
- [ ] **No out-of-scope overlap**: Feature doesn't touch explicitly excluded areas
- [ ] **Dependency check**: All feature dependencies are in scope
- [ ] **Boundary respect**: Feature doesn't creep beyond defined limits

### Out-of-Scope Validation
- [ ] **Respects exclusions**: Feature avoids explicitly out-of-scope items
- [ ] **No scope creep**: Feature doesn't expand scope without approval
- [ ] **Clear boundaries**: Interfaces with out-of-scope areas are well-defined

### Example Questions
- Is this feature explicitly mentioned in scope?
- Does this feature require anything that's out of scope?
- Are we expanding scope or implementing existing scope?
- What are the boundaries between this feature and out-of-scope areas?

### Red Flags
- ❌ Feature not mentioned in scope (implicit scope assumption)
- ❌ Feature requires out-of-scope dependencies
- ❌ Feature expands scope without PROJECT.md update
- ❌ Unclear boundaries with out-of-scope areas

### Resolution
- **Option 1**: Refine feature to fit within current scope
- **Option 2**: Update PROJECT.md scope to include feature
- **Option 3**: Split feature (in-scope vs out-of-scope parts)
- **Option 4**: Defer feature until scope review

---

## CONSTRAINTS Alignment Checklist

### Technical Constraints
- [ ] **Technology stack**: Uses approved technologies and frameworks
- [ ] **Performance**: Meets defined performance requirements
- [ ] **Scalability**: Works within scalability constraints
- [ ] **Security**: Complies with security policies (CWE validations, audit logs)
- [ ] **Compatibility**: Compatible with existing systems and dependencies

### Resource Constraints
- [ ] **Budget**: Feature cost within budget limits
- [ ] **Timeline**: Development time fits schedule
- [ ] **Team capacity**: Required skills available on team
- [ ] **Infrastructure**: Hosting/compute resources available

### Policy Constraints
- [ ] **Compliance**: Meets regulatory requirements
- [ ] **Licensing**: Uses properly licensed components
- [ ] **Privacy**: Respects data privacy policies
- [ ] **Standards**: Follows organizational standards

### Example Questions
- What technical constraints apply to this feature?
- Do we have the resources (time, budget, people) to implement this?
- Are there any policy or compliance issues?
- What trade-offs are we making against constraints?

### Red Flags
- ❌ Feature violates hard technical constraints
- ❌ Resource requirements exceed available capacity
- ❌ Compliance or policy violations
- ❌ Unstated assumptions about constraints

### Resolution
- **Option 1**: Modify feature to respect constraints
- **Option 2**: Relax constraints (if justified and approved)
- **Option 3**: Document trade-offs and get stakeholder approval
- **Option 4**: Defer feature until constraints change

---

## ARCHITECTURE Alignment Checklist

### Design Principles
- [ ] **Pattern consistency**: Follows established architectural patterns
- [ ] **Integration**: Integrates cleanly with existing components
- [ ] **Modularity**: Maintains separation of concerns
- [ ] **Extensibility**: Designed for future evolution

### Component Alignment
- [ ] **Interface contracts**: Respects existing interfaces
- [ ] **Data flow**: Fits into data architecture
- [ ] **Error handling**: Uses standardized error patterns
- [ ] **Security patterns**: Implements security-first architecture

### Quality Attributes
- [ ] **Maintainability**: Code is understandable and modifiable
- [ ] **Testability**: Unit tests and integration tests feasible
- [ ] **Observability**: Logging, metrics, and debugging support
- [ ] **Documentation**: Architecture documented clearly

### Example Questions
- Does this feature follow our architectural patterns?
- How does this integrate with existing components?
- Are we introducing architectural inconsistencies?
- Will this feature create technical debt?

### Red Flags
- ❌ Feature breaks established patterns without justification
- ❌ Poor integration with existing architecture
- ❌ Creates tight coupling or circular dependencies
- ❌ Introduces significant technical debt

### Resolution
- **Option 1**: Refactor feature to align with architecture
- **Option 2**: Update architecture (if feature reveals better pattern)
- **Option 3**: Document architectural deviation and rationale
- **Option 4**: Create migration plan to align over time

---

## Combined Validation

### Holistic Assessment
After validating each section individually, assess overall alignment:

- [ ] **Internal consistency**: All four sections align with each other
- [ ] **No conflicts**: GOALS and SCOPE don't contradict CONSTRAINTS and ARCHITECTURE
- [ ] **Strategic fit**: Feature serves overall project vision
- [ ] **Risk assessment**: Risks identified and mitigation planned

### Overall Questions
- Does this feature make the project better in all dimensions?
- Are there any hidden conflicts between sections?
- What's the total impact on project health?
- Should we proceed, modify, or reject this feature?

---

## Validation Report Template

```markdown
## Feature Alignment Validation

### Feature: [Feature Name]

### GOALS Alignment: ✓ / ⚠ / ✗
- Serves goal: [Goal name]
- Impact: [How it serves the goal]
- Conflicts: [None or list conflicts]

### SCOPE Alignment: ✓ / ⚠ / ✗
- In scope: [Yes/No - cite scope section]
- Dependencies: [All in scope / List out-of-scope]
- Boundaries: [Clear / Needs clarification]

### CONSTRAINTS Alignment: ✓ / ⚠ / ✗
- Technical: [Compliant / List violations]
- Resources: [Available / List gaps]
- Policy: [Compliant / List issues]

### ARCHITECTURE Alignment: ✓ / ⚠ / ✗
- Patterns: [Consistent / List deviations]
- Integration: [Clean / List concerns]
- Quality: [High / List issues]

### Overall Assessment: ✓ ALIGNED / ⚠ NEEDS WORK / ✗ NOT ALIGNED

### Recommendation:
[Proceed / Modify / Defer / Reject]

### Next Steps:
1. [Action item]
2. [Action item]
3. [Action item]
```

---

## Usage Examples

### Example 1: Feature Fully Aligned
**Feature**: "Add JWT authentication for API endpoints"

**Validation**:
- ✓ GOALS: Serves "secure user access" goal
- ✓ SCOPE: Authentication explicitly in scope
- ✓ CONSTRAINTS: JWT library approved, meets security requirements
- ✓ ARCHITECTURE: Follows existing auth patterns

**Recommendation**: Proceed with implementation

---

### Example 2: Feature Needs Modification
**Feature**: "Add real-time collaboration with WebSockets"

**Validation**:
- ⚠ GOALS: Serves "improve user experience" goal (partial)
- ✗ SCOPE: Real-time features explicitly out of scope
- ⚠ CONSTRAINTS: WebSockets not in approved tech stack
- ⚠ ARCHITECTURE: No existing real-time infrastructure

**Recommendation**: Modify feature or update PROJECT.md scope

**Resolution**: Split into "collaborative editing" (in scope, async) vs "real-time sync" (out of scope, defer)

---

### Example 3: Feature Conflicts with Constraints
**Feature**: "Add machine learning model for recommendations"

**Validation**:
- ✓ GOALS: Serves "personalization" goal
- ✓ SCOPE: Recommendations in scope
- ✗ CONSTRAINTS: Violates performance constraint (model too large)
- ⚠ ARCHITECTURE: No ML infrastructure in architecture

**Recommendation**: Defer until constraints can be relaxed or use lighter approach

**Resolution**: Use rule-based recommendations (fits constraints) with ML as future enhancement

---

## Best Practices

1. **Validate early**: Check alignment before detailed design
2. **Document all checks**: Even "obvious" alignments should be recorded
3. **Update iteratively**: Re-validate as feature evolves
4. **Involve stakeholders**: Get input on strategic alignment
5. **Be honest**: Don't force alignment if feature doesn't fit
6. **Consider trade-offs**: All features have costs; ensure benefits outweigh costs

---

## Common Pitfalls

1. **Assuming implicit scope**: "Everyone knows we need this" - make it explicit
2. **Ignoring constraints**: "We can relax that later" - address constraints upfront
3. **Skipping architecture**: "Just get it working" - technical debt compounds
4. **Goal creep**: Adding features that don't serve stated goals
5. **Literal validation**: Matching keywords instead of understanding intent

---

**See Also**:
- `semantic-validation-approach.md` - Philosophy behind validation approach
- `gap-assessment-methodology.md` - How to identify and prioritize gaps
- `conflict-resolution-patterns.md` - Resolving alignment conflicts
- `../templates/alignment-report-template.md` - Report template
- `../examples/alignment-scenarios.md` - Real-world scenarios
