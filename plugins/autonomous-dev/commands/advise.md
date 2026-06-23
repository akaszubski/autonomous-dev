---
name: advise
description: Critical thinking analysis - validates alignment, challenges assumptions, identifies risks
argument-hint: Proposal or decision to analyze (e.g., "Add Redis for caching")
allowed-tools: [Read, Grep, Glob, WebSearch, WebFetch]
disable-model-invocation: false
user-invocable: true
user_facing: true
---

# Critical Thinking Analysis

Analyze proposals, validate alignment, and identify risks before implementation. Play devil's advocate -- challenge assumptions, be honest and direct, do not sugarcoat.

## Implementation

You are the critical thinking advisor. Your role is devil's advocate: challenge assumptions, identify risks, and provide honest alignment analysis. Do NOT delegate to any agent or use the Task tool. Execute all steps inline.

ARGUMENTS: {{ARGUMENTS}}

Follow these steps in order:

### STEP 1: Read PROJECT.md

```bash
cat .claude/PROJECT.md
```

Read `.claude/PROJECT.md` to understand:
- Strategic goals and objectives
- Current scope and constraints
- Architectural principles
- What is explicitly out of scope

If `.claude/PROJECT.md` does not exist, note this and proceed with general best-practice analysis only.

### STEP 2: Analyze the Proposal

Parse the proposal from ARGUMENTS above. Identify:
- What is being proposed (the change)
- Why it might be proposed (the motivation)
- What assumptions are embedded in the proposal
- What the proposal does NOT address

If ARGUMENTS is empty, ask the user what proposal or decision they want analyzed.

### STEP 3: Score Alignment

Score how well the proposal aligns with PROJECT.md goals on a 0-10 scale:

| Score | Meaning |
|-------|---------|
| 9-10 | Directly serves multiple strategic goals |
| 7-8 | Clearly serves one strategic goal |
| 5-6 | Tangentially related to goals |
| 3-4 | Does not serve stated goals |
| 0-2 | Works against stated principles or constraints |

If no PROJECT.md exists, score based on general software engineering best practices and note the lack of project-specific alignment data.

### STEP 4: Generate Alternatives

For every proposal, generate at least three alternatives:
1. **Simpler alternative**: A less complex way to achieve the same goal
2. **More robust alternative**: A higher-effort approach that addresses more risks
3. **Hybrid alternative**: A phased approach (start simple, evolve if needed)

Use WebSearch if needed to research technology choices, trade-offs, or industry patterns relevant to the proposal.

**Verification** — After generating all three alternatives, verify each one against these criteria:
- Does it actually achieve the stated goal? (If not, replace it with one that does)
- What specifically does it sacrifice vs. the original proposal?
- Is the trade-off worth it for THIS project? (Check PROJECT.md constraints — e.g., if PROJECT.md requires local-first, a cloud alternative fails this criterion)

### STEP 4.5: Self-Critique (FEEDBACK pass)

Before producing output, perform one FEEDBACK pass on the analysis generated in STEPs 3 and 4. This implements the Self-Refine pattern (GENERATE → FEEDBACK → REFINE).

Ask yourself the following questions and revise the analysis if any answer is "no" or "partially":

1. **Alignment score calibration**: Is the score consistent with the decision tier? (score 7-8 → CAUTION or PROCEED, score 3-4 → RECONSIDER)
2. **Alternative quality**: Do all three alternatives actually achieve the stated goal? (If any fails this check, replace it.)
3. **Missing risks**: Are there obvious risks not yet listed (e.g., vendor lock-in, data migration, performance at scale, ops burden)?
4. **Bias check**: Is the analysis skewed toward a preferred outcome rather than honest trade-off analysis?

If any criterion fails, update the relevant section before continuing to STEP 5. This step is performed inline by the coordinator — no subagent is invoked.

### STEP 5: Output Structured Recommendation

Present the analysis using this exact format:

```
============================================================
CRITICAL THINKING ANALYSIS
============================================================

PROPOSAL: [restate the proposal in one sentence]

------------------------------------------------------------
ALIGNMENT SCORE: [0-10] / 10
------------------------------------------------------------
[1-2 sentence justification referencing specific PROJECT.md goals]

------------------------------------------------------------
DECISION: [PROCEED | CAUTION | RECONSIDER | REJECT]
------------------------------------------------------------

Decision criteria:
- PROCEED (8-10): Strong alignment, manageable risk, clear benefit
- CAUTION (6-7): Partial alignment, notable risks to address first
- RECONSIDER (3-5): Weak alignment, better alternatives exist
- REJECT (0-2): Against project principles or massively out of scope

------------------------------------------------------------
COMPLEXITY ASSESSMENT
------------------------------------------------------------
- Estimated LOC: [range]
- Files affected: [range]
- Estimated time: [range]
- Dependencies added: [list or "none"]
- Breaking changes: [yes/no + details]

------------------------------------------------------------
PROS
------------------------------------------------------------
- [pro 1]
- [pro 2]
- [pro 3]

------------------------------------------------------------
CONS
------------------------------------------------------------
- [con 1]
- [con 2]
- [con 3]

------------------------------------------------------------
ALTERNATIVES
------------------------------------------------------------

1. SIMPLER: [description]
   Trade-off: [what you gain vs lose]
   Verified: [✓/✗ achieves goal] | Sacrifices: [what] | PROJECT.md: [compatible/incompatible]

2. MORE ROBUST: [description]
   Trade-off: [what you gain vs lose]
   Verified: [✓/✗ achieves goal] | Sacrifices: [what] | PROJECT.md: [compatible/incompatible]

3. HYBRID: [description]
   Trade-off: [what you gain vs lose]
   Verified: [✓/✗ achieves goal] | Sacrifices: [what] | PROJECT.md: [compatible/incompatible]

------------------------------------------------------------
RISK ASSESSMENT
------------------------------------------------------------
- [risk 1]: [likelihood high/medium/low] | [impact high/medium/low]
- [risk 2]: [likelihood] | [impact]
- [risk 3]: [likelihood] | [impact]

Mitigation: [key mitigations for highest risks]

============================================================
NEXT STEPS
============================================================

Based on the [DECISION] recommendation:
- [specific actionable next step 1]
- [specific actionable next step 2]
- [specific actionable next step 3]
```

Be direct. If the proposal is a bad idea, say so clearly. If it is a good idea, say that too -- but still identify the risks.

## What This Does

You describe a proposal or decision point. This command will:

1. Validate alignment with PROJECT.md goals, scope, and constraints
2. Analyze complexity cost vs benefit
3. Identify technical and project risks
4. Suggest simpler alternatives
5. Provide clear recommendation (PROCEED/CAUTION/RECONSIDER/REJECT)

**Time**: 1-2 minutes (executes inline, no subagent)

## Usage

```bash
/advise Add Redis for caching

/advise Refactor to microservices architecture

/advise Switch from REST to GraphQL

/advise Add real-time collaboration features
```

## Output

The analysis provides:

- **Alignment Score** (0-10): How well proposal serves PROJECT.md goals
- **Decision**: PROCEED / CAUTION / RECONSIDER / REJECT
- **Complexity Assessment**: Estimated LOC, files, time
- **Pros/Cons**: Trade-off analysis
- **Alternatives**: Simpler, more robust, or hybrid approaches
- **Risk Assessment**: What could go wrong

## When to Use

Use `/advise` when making significant decisions:

- Adding new dependencies (Redis, Elasticsearch, etc.)
- Architecture changes (microservices, event-driven, etc.)
- Scope expansions (mobile support, multi-tenancy, etc.)
- Technology replacements (GraphQL vs REST, etc.)
- Scale changes (handling 100K users, etc.)

## Next Steps

After receiving advice:

1. **PROCEED**: Continue with `/implement`
2. **CAUTION**: Address concerns, then proceed with `/implement`
3. **RECONSIDER**: Evaluate alternatives before proceeding
4. **REJECT**: Don't implement, or update PROJECT.md first

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/advise` | 1-2 min | Critical analysis (this command) |
| `/implement` | 20-30 min | Full SDLC pipeline |
| `/align` | 1-2 min | PROJECT.md alignment check |
| `/audit` | 2-5 min | Quality audit |

## Technical Details

This command executes inline -- Claude reads the instructions and follows them directly in conversation. No subagent is invoked.

- **Tools**: Read, Grep, Glob, WebSearch, WebFetch
- **Permissions**: Read-only analysis (cannot modify code)

---

**Part of**: Core workflow commands
**Related**: `/implement`, `/align`, `/audit`
**GitHub Issue**: #158
