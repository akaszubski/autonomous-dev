---
description: "AI-powered architectural intent validation - checks if implementation aligns with ARCHITECTURE.md"
---

# Validate Architectural Intent (AI-Powered)

You are an architectural validation specialist. Your mission is to validate that the **actual implementation** aligns with the **documented architectural intent** in ARCHITECTURE.md.

## Your Task

1. **Read ARCHITECTURE.md** - Understand all 14 design principles, their INTENT, WHY, and breaking change definitions

2. **Analyze Current Implementation** - Examine:
   - Agent files (agents/*.md)
   - Skill files (skills/*/SKILL.md)
   - Command files (commands/*.md)
   - Hook files (hooks/*.py)
   - Templates (templates/*)
   - Setup scripts (scripts/setup.py)

3. **Validate Alignment** - For each architectural principle, check:
   - ✅ **ALIGNED**: Implementation matches documented intent
   - ⚠️ **DRIFT DETECTED**: Implementation deviates from intent
   - ❌ **VIOLATION**: Breaking change occurred

4. **Report Findings** - For each principle:

```markdown
## Principle: [Name]

**Status**: ✅ ALIGNED | ⚠️ DRIFT | ❌ VIOLATION

**Intent**: [What the principle says]

**Current Implementation**: [What you found in the code]

**Assessment**: [Does it match? Why or why not?]

**Recommendation**: [If drift/violation, what to fix]
```

## Validation Checklist

Validate each of these 14 principles:

### Core Design Principles

1. ✓ **PROJECT.md-First Architecture**
   - Check: Does orchestrator validate PROJECT.md before starting work?
   - Files: agents/orchestrator.md, commands/auto-implement.md

2. ✓ **8-Agent Pipeline**
   - Check: Exactly 8 agents in correct order?
   - Files: agents/*.md (should be 8 files)

3. ✓ **Model Optimization**
   - Check: Planner uses opus, security/doc use haiku, others use sonnet?
   - Files: agents/*.md (model: in frontmatter)

4. ✓ **Context Management**
   - Check: Session logging documented, /clear promoted, context budget <25K?
   - Files: README.md, commands/*.md, ARCHITECTURE.md

5. ✓ **Opt-In Automation**
   - Check: Both slash commands AND automatic hooks available?
   - Files: commands/*.md, templates/settings.local.json

6. ✓ **Project-Level Isolation**
   - Check: Plugin global, setup copies to project, no cross-project contamination?
   - Files: scripts/setup.py, templates/*

7. ✓ **TDD Enforcement**
   - Check: test-master runs before implementer in pipeline?
   - Files: agents/test-master.md, agents/implementer.md, commands/auto-implement.md

8. ✓ **Read-Only Planning**
   - Check: Planner and reviewer don't have Write/Edit tools?
   - Files: agents/planner.md, agents/reviewer.md (tools: in frontmatter)

9. ✓ **Security-First Design**
   - Check: Security-auditor in pipeline, pre-commit hook exists?
   - Files: agents/security-auditor.md, hooks/security_scan.py

10. ✓ **Documentation Sync**
    - Check: doc-master runs last in pipeline, updates CHANGELOG?
    - Files: agents/doc-master.md, commands/auto-implement.md

### Context & Data Exchange

11. ✓ **Agent Communication Strategy**
    - Check: Session files used (not context), context budget documented?
    - Files: ARCHITECTURE.md, README.md (should mention docs/sessions/)

12. ✓ **Agent Specialization (No Duplication)**
    - Check: Each agent has unique, non-overlapping responsibility?
    - Files: agents/*.md (purpose: should be distinct)

13. ✓ **Skill Boundaries (No Redundancy)**
    - Check: Exactly 6 skills with distinct domains?
    - Files: skills/*/SKILL.md (should be 6 unique domains)

14. ✓ **Data Flow (One Direction)**
    - Check: Pipeline flows forward (no circular dependencies)?
    - Files: commands/auto-implement.md (pipeline order)

## Architectural Invariants

**These MUST remain true**:

- ✓ Exactly 8 agents in pipeline
- ✓ Orchestrator validates PROJECT.md first
- ✓ Test-master runs before implementer
- ✓ Planner uses opus model
- ✓ Security-auditor and doc-master use haiku
- ✓ Planner and reviewer are read-only
- ✓ Plugin is globally installed, files are project-local
- ✓ Hooks are opt-in (not auto-enabled)
- ✓ Context management via /clear + session logging
- ✓ PROJECT.md has GOALS, SCOPE, CONSTRAINTS
- ✓ Each agent has unique, non-overlapping responsibility
- ✓ Each skill covers distinct domain
- ✓ Data flows forward through pipeline
- ✓ Context budget <25K per feature

## Output Format

Provide a comprehensive report:

```markdown
# Architectural Intent Validation Report

**Date**: [Today's date]
**Validator**: Claude (AI)
**Plugin Version**: 2.0.0

---

## Executive Summary

- **Total Principles**: 14
- **✅ Aligned**: X
- **⚠️ Drift Detected**: X
- **❌ Violations**: X

**Overall Status**: PASS | NEEDS ATTENTION | CRITICAL

---

## Detailed Findings

[For each of 14 principles, provide assessment]

---

## Recommendations

[If any drift/violations, provide specific fixes]

---

## Architectural Invariants Check

[Verify all invariants are true]
```

## How This Works

**Why GenAI Validation?**:
- Static tests (pytest) can only check structure (files exist, text contains keywords)
- GenAI can understand **MEANING** and **INTENT**
- Claude can detect subtle drift that regex can't catch
- Claude can explain WHY something is misaligned

**Example**:

Static test:
```python
assert "orchestrator" in content  # Just checks word exists
```

GenAI validation:
```
Read orchestrator.md. Does it actually validate PROJECT.md before
starting work? Look for Task tool calls, PROJECT.md references,
alignment validation logic. Don't just check if the word exists -
check if the BEHAVIOR matches the INTENT.
```

## Run This Validation

```bash
/validate-architecture
```

**When to run**:
- Before each release
- After major changes to agents/skills
- When architectural drift is suspected
- Monthly as part of maintenance

**Output**: Comprehensive AI-powered alignment report

---

**Key Innovation**: Use AI to validate architectural intent, not just static structure.
