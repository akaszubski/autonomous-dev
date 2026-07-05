---
name: plan
description: "Create a validated planning document with adversarial critique before implementation"
argument-hint: "Feature description [--no-issues] (e.g., '/plan Add JWT authentication for API endpoints')"
allowed-tools: [Task, Read, Bash, Grep, Glob, WebSearch, Write]
disable-model-invocation: false
user-invocable: true
user_facing: true
---

# Create Validated Plan

Create a structured planning document with adversarial critique. Plans are written to `.claude/plans/<slug>.md` and validated by the plan_gate hook before implementation.

## Implementation

**CRITICAL**: Follow these steps in order. Each step builds on the previous.

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Arguments

Parse the `{{ARGUMENTS}}` placeholder for the feature description and flags:

```
--no-issues       Skip automatic GitHub issue creation in Step 6
```

If `--no-issues` is present, set no_issues=true. Strip the flag from the feature description string before use.

If no description provided, prompt the user for a feature description.

---

### STEP 1: Problem Statement (WHY + SCOPE)

Define the problem clearly:

1. **WHY** is this change needed? What problem does it solve?
2. **SCOPE**: What is IN scope and what is OUT of scope?
3. **Success criteria**: How will we know the plan is complete?

Estimate the number of files that will be created or modified.

Invoke the **plan-critic** agent for initial feedback on the problem statement. The plan-critic provides adversarial review to challenge assumptions and find gaps.

**Agent**(subagent_type="plan-critic", model="opus")

---

### STEP 2: Scope Check

Compare the estimated file count from Step 1 against what you discover during research.

**HARD GATE**: If the actual file count exceeds the Step 1 estimate by >50%, halt and re-scope with the user before proceeding.

---

### STEP 3: Existing Solutions

Search for existing solutions before building anything new:

1. **Codebase search**: Use Grep and Glob to find similar patterns
2. **Web search**: Use WebSearch to find libraries, patterns, or prior art
3. **Document findings**: Record what was searched and what was found

This section becomes the "## Existing Solutions" in the plan output.

---

### STEP 4: Minimal Path

Design the smallest change that achieves the goal:

1. List files to create/modify in dependency order
2. Identify what can be deferred to follow-up work
3. Define the critical path

This section becomes the "## Minimal Path" in the plan output.

---

### STEP 5: Adversarial Critique — Iterative Loop

Invoke the **plan-critic** agent with the full plan draft.

**Agent**(subagent_type="plan-critic", model="opus")

**IMPORTANT — MODEL ENFORCEMENT**: The plan-critic MUST run as `model="opus"`. Do NOT invoke plan-critic with sonnet, haiku, or any other model. Opus is required for adversarial critique quality.

Run plan-critic in a **sequential iterative loop**. Each round is a SEPARATE agent invocation. Output from round N is input to round N+1.

**Loop rules:**
- **Minimum**: 3 rounds (not 2 — 2 rounds catches surface issues, 3rd round validates the fixes)
- **Maximum**: 5 rounds (beyond 5, error introduction exceeds correction — per iterative review-fix convergence formula)
- **Convergence**: Stop after round ≥ 3 IF composite score ≥ 3.0 AND no axis below 2. Otherwise continue.
- **NEVER run rounds concurrently** — each round MUST complete before the next starts

**Round protocol:**

**Round 1**: Pass the full plan draft. Instruct: "This is your FIRST critique round — identify issues across all 5 critique axes."

**Round 2+**: Pass the plan (revised if REVISE verdict) AND the previous round's full verdict output. Instruct: "This is ROUND N. Previous round verdict: {verdict}, score: {composite}. Previous findings: {key issues}. Verify fixes and probe deeper."

**After each round**, parse the verdict:
- **PROCEED** (score ≥ 3.0, no axis below 2): If round ≥ 3, exit loop. If round < 3, continue (minimum rounds not met).
- **REVISE**: Revise the plan based on feedback. Feed revised plan + critique into next round.
- **BLOCKED**: Rethink approach. Either revise fundamentally and restart critique loop, or escalate to user.

**Verdict authorship (Issue #1155)**: A `Verdict: PROCEED` line in a freshly-generated plan MUST come from a completed plan-critic round (round-table row, or section header `### Round N (plan-critic, ...)`). A self-assessed verdict from the planner — typically marked `provisional`, `(provisional)`, or `awaits plan-critic` — does NOT satisfy STEP 5.5a's skip condition in `/implement`. Concretely: if you write the plan file with a self-assessment such as `Verdict: PROCEED (provisional) — awaits plan-critic at /implement time`, the `/implement` 5.5a negative filter (Issue #1155) will detect the `provisional` marker, fall through to 5.5b, and invoke plan-critic as if the file did not exist. To make 5.5a skip legitimately, complete the adversarial loop here in STEP 5 and let plan-critic write the final `Verdict: PROCEED` line.

**Score tracking**: Maintain a running table of scores across rounds:

| Round | Verdict | Composite | Assumption | Scope | Existing | Minimalism | Uncertainty |
|-------|---------|-----------|------------|-------|----------|------------|-------------|

Track delta between rounds. Score regression (lower than previous) is EXPECTED and ACCEPTABLE — it means deeper issues were found.

**Exit condition**: The FINAL round's verdict determines the outcome. Not the best score, not the average — the last round.

**Convergence Trap Detection** — Check after each round:

1. **Plateau/Divergence**: If finding count plateaus or INCREASES across 2+ consecutive rounds → issue BLOCKED (loop is stuck, not converging)
2. **Critic Instability**: If composite score drops > 1 point with NO corresponding plan revision → flag as critic instability, escalate to user: "Critic scores inconsistent — composite dropped {delta} without plan changes. Review manually or continue?"
3. **Sycophantic Drift**: If scores rose but plan text is UNCHANGED between rounds → do NOT accept PROCEED. Force one more round with instruction: "Scores improved without plan changes — re-evaluate from scratch."

**FORBIDDEN**:
- FORBIDDEN: Invoking plan-critic with any model other than `"opus"`
- FORBIDDEN: Omitting the `model="opus"` parameter when calling plan-critic
- FORBIDDEN: Running fewer than 3 critique rounds
- FORBIDDEN: Running critique rounds concurrently (each round MUST complete before the next)
- FORBIDDEN: Proceeding past Step 5 before the final round issues PROCEED
- FORBIDDEN: Using the best or average score instead of the final round's verdict

Do NOT proceed past Step 5 until the plan-critic issues PROCEED.

**HARD GATE: Transition to STEP 6**

After the final PROCEED verdict from Step 5, you MUST:
1. Record that plan-critic passed by calling:
   ```python
   from pipeline_completion_state import record_plan_critic_passed
   session_id = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("AUTONOMOUS_DEV_SESSION_ID") or "unknown"
   record_plan_critic_passed(session_id, plan_slug)
   ```
   where `plan_slug` is the identifier for the plan (e.g., extracted from the plan filename).
2. Then immediately proceed to STEP 6 (issue creation). Do NOT skip to Step 7.

**FORBIDDEN**:
- FORBIDDEN: Writing the plan file (Step 7) before completing Step 6
- FORBIDDEN: Skipping Step 6 without logging an explicit skip reason (--no-issues flag or single work item)

The plan file MUST contain a "## Linked Issues" section with either issue URLs or an explicit skip reason before Step 7 can proceed.

---

### STEP 6: Auto-Create GitHub Issues (--quick mode, PROCEED only)

**This step runs ONLY after a PROCEED verdict from Step 5.** If the plan-critic issued REVISE or BLOCKED, do NOT run this step — return to Step 5 to address the feedback first.

**HARD GATE**: When >=2 independent work items exist, you MUST create GitHub issues before proceeding to Step 7. Issue creation is REQUIRED for multi-item plans — it is not optional.

**FORBIDDEN**:
- FORBIDDEN: Running issue creation after a REVISE verdict
- FORBIDDEN: Running issue creation after a BLOCKED verdict
- FORBIDDEN: Blocking plan file creation (Step 7) if issue creation fails
- FORBIDDEN: Declaring work items as "not independent" to avoid issue creation without specific, stated justification
- FORBIDDEN: Skipping issue creation when >=2 independent work items exist (use --no-issues flag instead if intentional)
- FORBIDDEN: Proceeding to Step 7 without either creating issues or logging an explicit skip reason

#### Guard: --no-issues flag

If `--no-issues` was set in Step 0, log the following and proceed directly to Step 7:

```
Skipping Step 6: --no-issues flag set — issue creation suppressed.
Run /plan-to-issues for thorough issue creation with full section templates.
```

Record `Issues not created — --no-issues flag was set` in the `## Linked Issues` section of the plan file.

**Coordination Note**: If you intend to run `/implement` immediately after `/plan` in the same session, pass `--no-issues` to avoid the `/drain-queue` autonomous drainer picking up your newly-filed issues mid-session. The drainer has no visibility into your session intent; without `--no-issues`, both paths may complete the same work concurrently and produce merge conflicts (see #1373).

#### Guard: single work item

If the Minimal Path from Step 4 contains **<2 independent work items**, log the following and proceed directly to Step 7:

```
Skipping Step 6: plan is a single coherent unit — no issue decomposition needed.
```

Record `N/A — single work item` in the `## Linked Issues` section of the plan file.

#### When to create issues (>=2 independent work items, after PROCEED):

Issue creation uses quick mode: Summary + Implementation Approach + Acceptance Criteria only (no full template).

**Prior-call ordering contract (Issue #1203)**: PreToolUse hook
evaluates each Bash invocation BEFORE it runs. The command-context file
MUST be written in its OWN Bash tool call, separate from and BEFORE any
`gh issue create` call. **FORBIDDEN: Do NOT bundle the context write
and `gh issue create` into one Bash tool call** — the hook will not see
the context at evaluation time and will block (see #1203).

1. **Step 6a — Write the command context file (its OWN Bash tool call, prior
   to any `gh issue create`).** This call MUST be a standalone Bash
   invocation with no `&&` chain to a subsequent `gh issue create`:
   ```bash
   python3 -c "
   import json; from datetime import datetime, timezone
   with open('/tmp/autonomous_dev_cmd_context.json', 'w') as f:
       json.dump({'command': 'plan', 'timestamp': datetime.now(timezone.utc).isoformat()}, f)
   "
   ```

2. **Step 6b — Write each issue body to a temp file** (one Bash call per
   body, or grouped — the body writes do NOT need to be separate from each
   other; they just need to be separate from the `gh issue create` calls):
   ```bash
   cat > /tmp/plan_issue_N.md << 'ISSUE_EOF'
   ## Summary
   <1-2 sentence description of the work item>

   ## Implementation Approach
   <Key steps and technical approach>

   ## Acceptance Criteria
   - [ ] <criterion 1>
   - [ ] <criterion 2>
   ISSUE_EOF
   ```

3. **Step 6c — Create the issue** (separate Bash tool call AFTER 6a and 6b).
   Per-issue temp-file cleanup MUST be chained onto the same call via `;`,
   and the final iteration of the per-issue loop MUST also chain
   `/tmp/autonomous_dev_cmd_context.json` into the same `; rm -f ...` clause.
   Standalone `rm` calls re-introduce a user-visible permission prompt
   (Issue #1204).

   Mid-loop iterations (every iteration EXCEPT the last) chain only their own
   per-issue temp file:
   ```bash
   gh issue create --title "feat: <sanitized item title>" --body-file /tmp/plan_issue_N.md; rm -f /tmp/plan_issue_N.md
   ```

   Final iteration of the loop chains the glob+context cleanup so the
   context-file write from Step 6a is removed only after the LAST
   `gh issue create` succeeds (preserving the #1203 standalone-prior-write
   contract — the WRITE in 6a stays its own call; only the cleanup rides
   the last create):
   ```bash
   gh issue create --title "feat: <sanitized item title>" --body-file /tmp/plan_issue_N.md; rm -f /tmp/plan_issue_*.md /tmp/autonomous_dev_cmd_context.json
   ```

4. Collect created issue URLs (e.g., `https://github.com/owner/repo/issues/101`)
   and display them to the user.

**Non-blocking error handling**: If `gh issue create` fails for any reason (not installed, not authenticated, network error), log a warning and continue to Step 7. Do NOT halt or block plan file creation. Suggest running `/plan-to-issues` manually.

```
Warning: gh issue create failed — <error message>
Run /plan-to-issues after plan creation to create issues manually.
```

---

### STEP 7: Write Plan File

Generate a URL-safe slug from the feature description.

Create the `.claude/plans/` directory if it doesn't exist:
```bash
mkdir -p .claude/plans
```

Write the validated plan to `.claude/plans/<slug>.md` with these required sections:

```markdown
# Plan: <Feature Name>

## WHY + SCOPE
[From Step 1]

## Existing Solutions
[From Step 3]

## Minimal Path
[From Step 4]

## Files to Create/Modify
[From Step 4, ordered by dependency]

## Risks and Unknowns
[Identified during critique]

## Critique History
[Summary of plan-critic rounds and resolutions]

## Linked Issues
[One of:
- "- #NNN: Title (https://github.com/owner/repo/issues/NNN)" for each auto-created issue
- "N/A — single work item" if no issue decomposition was needed
- "Issues not created — --no-issues flag was set" if --no-issues was passed
- "Issues not created — run /plan-to-issues" if gh was unavailable or failed]
```

---

### Output

Display the plan file path, created issues (if any), and next steps:

```
Plan created: .claude/plans/<slug>.md

Issues created:
  https://github.com/owner/repo/issues/101 — feat: <item 1>
  https://github.com/owner/repo/issues/102 — feat: <item 2>

Next steps:
  /implement "feature description"            -- implement the plan directly
  /implement --issues #101,#102              -- implement via linked issues
```

If issues were NOT created (--no-issues flag, single work item, or gh failure):

```
Plan created: .claude/plans/<slug>.md

Next steps:
  /implement "feature description"            -- implement the plan directly
  /plan-to-issues                             -- create GitHub issues (thorough mode)
  /plan-to-issues --quick                     -- create GitHub issues (quick mode)
```

---

## What This Does

| Step | Time | Description |
|------|------|-------------|
| Problem Statement | 1-2 min | Define WHY + SCOPE |
| Scope Check | 30 sec | Validate file count estimate |
| Existing Solutions | 2-3 min | Search codebase + web |
| Minimal Path | 1-2 min | Design smallest change |
| Adversarial Critique | 5-10 min | plan-critic review (3-5 rounds) |
| Issue Decomposition | 0-2 min | Auto-create GitHub issues (--quick mode, PROCEED only) |
| Write Plan | 30 sec | Output to .claude/plans/ |
| **Total** | **8-15 min** | Full planning workflow |

---

## Integration

- **plan_gate hook**: Enforces plan existence before complex Write/Edit operations
- **plan-critic agent**: Provides adversarial review during Step 5
- **planning-workflow skill**: Documents the 7-step workflow
- **/plan-to-issues**: Can use `.claude/plans/` files as input source
- **/implement**: Proceeds with implementation after plan is validated
