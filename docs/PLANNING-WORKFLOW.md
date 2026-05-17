# Planning Workflow

A structured 7-step planning process enforced before implementation. Plans are critiqued adversarially and validated by hooks.

## Design Principles

1. **Plan before you build**: Complex changes require explicit design thinking before touching code.
2. **Adversarial review**: Plans are challenged by a critic agent, not rubber-stamped.
3. **Minimalism**: The smallest change that achieves the goal is the best change.
4. **Existing solutions first**: Always search before building. The best code is code you don't write.
5. **Fail-open enforcement**: The hook blocks complex edits without a plan, but never crashes the workflow.
6. **Escape hatches exist**: `SKIP_PLAN_CHECK=1` for legitimate bypasses.

## When to Plan

Use `/plan` before:
- Changes touching more than 3 files
- Changes exceeding 100 lines
- Changes where the approach is uncertain
- Changes touching multiple components or architectural layers

Simple edits (documentation, typo fixes, small patches) are automatically exempt.

## The 7-Step Process

### Step 1: Problem Statement

Define WHY this change is needed and WHAT is in scope. Estimate the files affected. The plan-critic agent reviews the problem statement for clarity and scope.

### Step 2: Scope Check

Compare actual file count against the Step 1 estimate. If drift exceeds 50%, halt and re-scope. This catches scope creep before implementation begins.

### Step 3: Existing Solutions

Search the codebase (Grep, Glob) and web (WebSearch) for prior art. Document what was found. Even "nothing found" is a valid finding that should be recorded.

### Step 4: Minimal Path

Design the smallest set of changes that achieves the goal. List files in dependency order. Identify what can be deferred.

### Step 5: Adversarial Critique

The plan-critic agent reviews the plan across 6 axes:
- **Assumption audit**: What might not be true?
- **Scope creep detection**: Is the plan doing more than needed?
- **Existing solution search**: Has prior art been checked?
- **Minimalism pressure**: What can be removed?
- **Uncertainty flagging**: What's risky?
- **Operational Integration Test**: Are subprocess/network/fs calls tested with runtime-context kwargs (cwd, env, credentials)?

Minimum 3 critique rounds before PROCEED verdict.

### Step 6: Auto-Create GitHub Issues (--quick mode, PROCEED only)

This step runs only after a PROCEED verdict from Step 5. If the plan-critic issued REVISE or BLOCKED, return to Step 5 to address feedback first.

**Guard — `--no-issues` flag**: Pass `--no-issues` to `/plan` to skip issue creation entirely. The plan file records `Issues not created — --no-issues flag was set` in `## Linked Issues`.

**Guard — single work item**: If the Minimal Path contains <2 independent work items, this step is skipped and the plan file records `N/A — single work item` in `## Linked Issues`.

When >=2 independent work items exist after a PROCEED verdict, GitHub issues are created in quick mode (Summary + Implementation Approach + Acceptance Criteria) via `gh issue create` (not via `/create-issue`). Issue creation is **non-blocking**: if `gh` fails for any reason, a warning is logged, plan file creation continues, and `/plan-to-issues` can be run manually afterward.

### Step 7: Plan Output

Write the validated plan to `.claude/plans/<slug>.md`.

## Plan File Format

```markdown
# Plan: <Feature Name>

## WHY + SCOPE
Problem definition and scope boundary.

## Existing Solutions
Prior art search results.

## Minimal Path
Smallest viable approach.

## Files to Create/Modify
Ordered list with descriptions.

## Risks and Unknowns
What might go wrong.

## Critique History
Plan-critic feedback and resolutions.

## Linked Issues
One of:
- `- https://github.com/owner/repo/issues/NNN: Title` for each auto-created issue
- `N/A — single work item` if no issue decomposition was needed
- `Issues not created — --no-issues flag was set` if `--no-issues` was passed
- `Issues not created — run /plan-to-issues` if gh was unavailable or failed
```

## Hook Enforcement

The `plan_gate.py` hook runs on every Write/Edit operation:

1. **Non-Write/Edit tools**: Always allowed
2. **Documentation files** (.md, CHANGELOG, README, docs/): Always allowed
3. **Simple edits** (<100 lines): Always allowed
4. **Complex edits without plan**: Blocked with actionable message
5. **Complex edits with valid plan**: Allowed
6. **Expired plan** (>72h): Allowed with warning

### Block Message

When blocked, the message includes:
- What's wrong (no plan or missing sections)
- **REQUIRED NEXT ACTION: run /plan**
- Required plan sections list
- Escape hatch instructions

## Escape Hatches

| Escape Hatch | When to Use |
|-------------|-------------|
| `SKIP_PLAN_CHECK=1` | Emergency fixes, trivial changes that shouldn't need a plan |
| Small edit (<100 lines) | Automatic exemption for simple changes |
| Doc files | Automatic exemption for documentation |

## Integration

| Component | Role |
|-----------|------|
| `/plan` command | Drives the 7-step workflow |
| `plan-critic` agent | Adversarial reviewer (Opus tier) |
| `plan_gate.py` hook | Enforces plan existence before complex edits |
| `plan_validator.py` lib | Validates plan file contents and sections |
| `planning-workflow` skill | Documents the workflow for context injection |
| `/plan-to-issues` command | Thorough-mode issue creation (full templates); also the fallback when `gh` was unavailable during Step 6 or `--no-issues` was passed |

## Rationale

Plans prevent the pattern of "dive in, realize halfway through it won't work, start over." By requiring explicit design thinking and adversarial review, plans catch problems before they become code. The hook enforcement ensures this isn't just a suggestion -- it's a gate.
