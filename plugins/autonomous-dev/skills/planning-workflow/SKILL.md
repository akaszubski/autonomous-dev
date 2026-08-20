---
name: planning-workflow
description: "7-step planning workflow for pre-implementation design. Plan EXISTENCE is enforced by the plan_gate hook; the plan-critic CRITIQUE is enforced separately (unified_pre_tool's plan-exit marker gate, and the /implement STEP 5.5b verdict gate). Use when creating plans, design documents, or architecture decisions before implementation. TRIGGER when: plan, planning, /plan, design document, architecture decision. DO NOT TRIGGER when: implementation, coding, testing."
allowed-tools: [Read, Grep, Glob, WebSearch, Bash, Write]
---

# Planning Workflow

A structured 7-step process for creating validated plans before implementation. Plans are critiqued adversarially by the plan-critic agent.

Two different enforcers, two different things enforced — do not conflate them:

| What is enforced | Enforcer |
|------------------|----------|
| A plan EXISTS with the three required sections, before a complex write | `plan_gate.py` hook (PreToolUse). Transport-independent since Issue #1503 — MultiEdit, NotebookEdit, and MCP editors are gated identically to Write/Edit. |
| The plan-critic CRITIQUE actually ran (plan-mode path) | `unified_pre_tool.py` plan-exit marker gate (Issue #926) — the marker must reach `stage: critique_done`. |
| The plan-critic VERDICT is PROCEED (`/implement` path) | `/implement` STEP 5.5b verdict gate. |

`plan_gate.py` does NOT enforce the critique. It checks only that a validated planning document is present.

## When to Use

- Before any complex implementation (>3 files or >100 lines)
- When the approach is uncertain or multiple solutions exist
- When the feature touches multiple components
- When scope needs to be explicitly bounded

## The 7-Step Workflow

| Step | Name | Description | Tools |
|------|------|-------------|-------|
| Step 1 | **Problem Statement** | Define WHY this change is needed and WHAT is in scope | Read, Grep |
| Step 2 | **Scope Check** | Estimate files affected; halt if >50% drift from initial estimate | Glob, Grep |
| Step 3 | **Existing Solutions** | Search codebase + web for prior art before building new | Grep, Glob, WebSearch |
| Step 4 | **Minimal Path** | Design the smallest change that achieves the goal | Read |
| Step 5 | **Adversarial Critique** | plan-critic agent reviews the plan (min 2 rounds) | plan-critic agent |
| Step 6 | **Issue Decomposition** | Break into trackable issues if needed (via /create-issue) | Bash |
| Step 7 | **Plan Output** | Write validated plan to .claude/plans/<slug>.md | Write |

### Step 1: Problem Statement

Define:
- **WHY** this change is needed (not what, not how)
- **SCOPE** boundary -- what is IN and what is OUT
- **Success criteria** -- how do we know it's done?

### Step 2: Scope Check

Estimate the number of files that will be created or modified. If during planning the actual file count exceeds the Step 1 estimate by >50%, halt the workflow and re-scope. This prevents scope creep before it starts.

### Step 3: Existing Solutions

Before building anything new, search for existing solutions:
- **Codebase search**: Use Grep and Glob to find similar patterns in the project
- **Web search**: Use WebSearch to find libraries, patterns, or prior art
- **Document findings**: Even if nothing is found, document what was searched

This step prevents reinventing the wheel and catches cases where a library or existing code already solves the problem.

### Step 4: Minimal Path

Design the smallest change that achieves the goal:
- What files need to change?
- What is the dependency order?
- What can be deferred to a follow-up?

### Step 5: Adversarial Critique

The plan-critic agent reviews the plan across 7 axes:
- Assumption audit
- Scope creep detection
- Existing solution verification
- Minimalism pressure
- Uncertainty flagging
- Operational integration test
- Reachability and enforceability

Minimum 3 critique rounds before PROCEED verdict.

### Step 6: Issue Decomposition

If the plan involves multiple independent work items, decompose into GitHub issues using /create-issue. Each issue should be independently implementable.

### Step 7: Plan Output

Write the final plan to `.claude/plans/<slug>.md` with all required sections.

## Plan File Format

```markdown
# Plan: <Feature Name>

## WHY + SCOPE
Why this change is needed and what is in/out of scope.

## Existing Solutions
What was searched, what was found, why existing solutions do/don't apply.

## Minimal Path
The smallest set of changes to achieve the goal.

## Files to Create/Modify
Ordered list of files with brief description of changes.

## Risks and Unknowns
What might go wrong and how to mitigate.

## Critique History
Summary of plan-critic feedback and resolutions.
```

## Required Plan Sections

Every plan MUST contain these three sections (validated by plan_gate hook):

1. **## WHY + SCOPE** -- Problem definition and boundary
2. **## Existing Solutions** -- Prior art search results
3. **## Minimal Path** -- Smallest viable approach

## Verdicts

The plan-critic agent issues one of three verdicts:

| Verdict | Meaning | Action |
|---------|---------|--------|
| **PROCEED** | Plan is adequate | Continue to implementation |
| **REVISE** | Plan has fixable issues | Address feedback and re-submit |
| **BLOCKED** | Fundamental problems | Rethink the approach |

## Escape Hatches

- `SKIP_PLAN_CHECK=1` environment variable disables the plan_gate hook
- Simple edits (<100 lines) are never blocked by the hook
- Documentation files (.md, CHANGELOG, README) are always exempt
