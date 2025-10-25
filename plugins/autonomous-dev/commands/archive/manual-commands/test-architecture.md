---
description: GenAI architectural validation - detect drift from documented intent (2-5min)
---

# Architecture GenAI Validation

**Validate implementation matches architectural intent (GenAI)**

---

## Usage

```bash
/test-architecture
```

**Time**: 2-5 minutes
**Tool**: Claude (GenAI analysis)
**Scope**: Architectural alignment, intent preservation, drift detection

---

## What This Does

Uses Claude to validate:
- ✅ **PROJECT.md-first architecture** enforced?
- ✅ **Agent pipeline order** correct?
- ✅ **Model optimization** followed?
- ✅ **Context management** implemented?
- ✅ **Agent specialization** (no duplication)?
- ✅ **All 14 architectural principles** respected

**Process**:
1. Read PROJECT.md architecture
2. Analyze implementation (code, structure)
3. Compare intent vs implementation
4. Detect architectural drift
5. Generate alignment report

---

## Expected Output

```
Running GenAI Architecture Validation...

Reading PROJECT.md architecture...
Analyzing implementation...
Checking architectural principles...

┌─ Architectural Alignment Report ────────────┐
│                                              │
│ Overall Alignment: 95% ✅                    │
│                                              │
│ ✅ PROJECT.md-First: Enforced                │
│    orchestrator validates before all work    │
│                                              │
│ ✅ Agent Pipeline: Correct Order             │
│    orchestrator → researcher → planner →     │
│    test-master → implementer → reviewer →    │
│    security-auditor → doc-master             │
│                                              │
│ ✅ Model Optimization: Implemented           │
│    - Haiku: security-auditor, doc-master     │
│    - Sonnet: All others                      │
│    - Opus: planner (complex only)            │
│                                              │
│ ✅ Context Management: Working               │
│    - Session files instead of context        │
│    - /clear after features                   │
│    - Agents log to docs/sessions/            │
│                                              │
│ ⚠️  Optimization Opportunities: 1            │
│                                              │
│ 1. Reviewer Agent Model (Low Priority)       │
│    - Currently: Sonnet                       │
│    - Recommendation: Try Haiku for simple    │
│      code reviews (non-architectural)        │
│    - Potential savings: 40% cost reduction   │
│                                              │
│ ✅ Architectural Principles: 14/14           │
│    All principles respected ✅               │
│                                              │
└──────────────────────────────────────────────┘

💡 Would you like me to create GitHub issue for optimization?
   Run: /issue-auto
```

---

## Validation Criteria

**14 Architectural Principles** (from PROJECT.md):

1. PROJECT.md-first (validate alignment before work)
2. 8-agent pipeline (orchestrator coordinates)
3. Model optimization (Haiku for simple, Sonnet/Opus for complex)
4. Context management (< 8K tokens per feature)
5. Agent specialization (no duplication)
6. Session file communication (not context)
7. GitHub integration (optional sprint tracking)
8. Command-driven workflow
9. Skill-based knowledge
10. Hook-based automation
11. Security-first (secrets management)
12. Test-driven (TDD workflow)
13. Documentation sync (auto-update)
14. Progressive validation (commit workflow)

---

## Drift Detection

**Common drift patterns**:
- Agents bypassing orchestrator
- Context bloat (> 8K tokens per feature)
- Model misuse (Opus for simple tasks)
- Agent overlap (duplication of responsibilities)
- Missing PROJECT.md validation
- Documentation out of sync

---

## When to Use

- ✅ After architectural changes
- ✅ Before major releases
- ✅ Periodic alignment checks (monthly)
- ✅ In `/commit-push` (Level 3 push commit)
- ✅ In `/test-complete` (pre-release)

---

## Issue Tracking

**Auto-create GitHub issues**:
```bash
/test-architecture
# Then run:
/issue-auto
```

Each drift or optimization becomes a tracked issue with:
- Current state
- Target state
- Impact (cost, performance, maintainability)
- Recommended actions

---

## Related Commands

- `/test-uat-genai` - GenAI UX validation (2-5min)
- `/test-complete` - Complete pre-release (all + GenAI)
- `/align-project` - Fix architectural drift
- `/issue-auto` - Create issues from findings

---

**Use this to ensure implementation stays aligned with architectural intent over time.**
