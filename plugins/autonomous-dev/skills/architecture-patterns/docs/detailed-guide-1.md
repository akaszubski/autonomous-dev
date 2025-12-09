# Architecture Patterns - Detailed Guide

## When This Skill Activates

- Designing system architecture
- Writing Architecture Decision Records (ADRs)
- Evaluating design patterns
- Making architectural tradeoffs
- System design questions
- Keywords: "architecture", "design", "pattern", "adr", "system design", "scalability"

---

## Architecture Decision Records (ADRs)

### What is an ADR?

An ADR documents an architectural decision - the context, the decision made, and the consequences.

### When to Write an ADR

Write an ADR for decisions that:
- Are hard to reverse
- Impact multiple teams
- Involve significant tradeoffs
- Set precedents for future work

**Examples**:
- ✅ "We chose PostgreSQL over MongoDB"
- ✅ "We split the monolith into microservices"
- ✅ "We adopted event-driven architecture"
- ❌ "We renamed a function" (too trivial)
- ❌ "We fixed a bug" (not architectural)

### ADR Template

```markdown
# ADR-### [Short Title]

**Date**: YYYY-MM-DD
**Status**: [Proposed | Accepted | Deprecated | Superseded]
**Deciders**: [Names/Roles]

## Context

What is the issue we're trying to solve? What are the constraints?

Example:
> Our monolithic application has grown to 200K lines of code.
> Deploy times are 45+ minutes, and teams are blocked on each other.
> We need to improve deployment speed and team autonomy.

## Decision
