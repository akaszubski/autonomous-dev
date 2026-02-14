# Project Management - Detailed Guide

## GOALS
1. Make users happy
2. Build good software
3. Ship features
```

**✅ GOOD: Specific goals**
```markdown
## GOALS
1. **Achieve NPS score of 50+** (currently 32)
2. **Reduce P0 bugs to < 5 per month** (currently 15)
3. **Ship search feature by Nov 15** (hard deadline for demo)
```

---

### Include "Why"

**❌ BAD: No rationale**
```markdown
## CONSTRAINTS
- Python 3.11+ required
```

**✅ GOOD: Explains why**
```markdown
## CONSTRAINTS
- **Python 3.11+**: Required for new type hints (improves IDE support) and
  10-25% performance improvements in CPython 3.11
```

---

### Link to Details

**❌ BAD: Everything in PROJECT.md**
```markdown
## ARCHITECTURE
[20 pages of architecture documentation inline]
```

**✅ GOOD: Link to detailed docs**
```markdown
## ARCHITECTURE

**High-Level**: Microservices with event-driven communication

**Details**: See `docs/adr/` for architectural decisions and `docs/architecture.md`
for system diagrams
```

---

## Integration with [PROJECT_NAME]

[PROJECT_NAME] project management practices:

- **PROJECT.md location**: `.claude/PROJECT.md` (version-controlled)
- **Update frequency**: Weekly or after major decisions
- **Alignment checks**: orchestrator agent validates before work begins
- **Sprint tracking**: Optional GitHub integration (issues, milestones)
- **ADRs**: Linked from PROJECT.md, stored in `docs/adr/`

---

## Templates

### Minimal PROJECT.md (Startups/MVPs)

```markdown
# [PROJECT NAME]

**Last Updated**: YYYY-MM-DD

## GOAL
[One sentence: What does success look like?]

## SCOPE
**Building**: [List 3-5 must-have features]
**Not building**: [List 2-3 anti-features]

## CONSTRAINTS
- **Timeline**: [Deadline]
- **Tech stack**: [Key technologies]

## CURRENT FOCUS
[What we're working on this week/sprint]
```

---

### Comprehensive PROJECT.md (Teams/Enterprises)

Use the full template at the top of this skill (includes goals, scope, constraints, architecture, sprints, roadmap, risks, team).

---

## Additional Resources

**Books**:
- "The Lean Startup" by Eric Ries
- "Inspired" by Marty Cagan
- "Measure What Matters" (OKRs) by John Doerr

**Frameworks**:
- SMART goals
- OKRs (Objectives & Key Results)
- MoSCoW prioritization
- SAFe (Scaled Agile Framework)

**Tools**:
- GitHub Issues + Milestones
- Linear, Jira, Asana (project tracking)
- Miro, FigJam (roadmap visualization)

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: architecture-patterns (ADRs), documentation-guide, git-workflow
