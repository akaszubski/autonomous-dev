---
description: Analyze and fix project alignment with PROJECT.md using GenAI
---

## Implementation

Invoke the alignment-analyzer agent to find conflicts between PROJECT.md and reality, then guide interactive fixing.

# Align Project

**GenAI-powered project alignment analysis and interactive fixing**

---

## Usage

```bash
/align-project
```

**Time**: 5-20 minutes (depending on issues found)
**Interactive**: Agent asks about each conflict found
**GenAI-Powered**: Uses alignment-analyzer agent for intelligent analysis

---

## How It Works

The alignment-analyzer agent works with you to align your project:

### Phase 1: Analysis (GenAI Agent)

The agent:
- ✅ Reads PROJECT.md (source of truth)
- ✅ Scans your codebase for actual implementation
- ✅ Checks documentation against reality
- ✅ Identifies conflicts and misalignments
- ✅ Explains each issue in context

### Phase 2: Interactive Fixing (GenAI + You)

For each conflict found, the agent asks:

```
PROJECT.md says: "REST API only, no GraphQL"
Reality shows: graphql/ directory with resolvers
Status: GraphQL implementation exists

What should we do?
A) YES - PROJECT.md is correct (remove GraphQL)
B) NO - Update PROJECT.md to include GraphQL

Your choice [A/B]:
```

The agent intelligently:
- Asks binary questions (no ambiguity)
- Explains impact of each choice
- Groups related conflicts
- Suggests fixes based on your answers

### Phase 3: Execution

After all questions answered, the agent:
- ✅ Updates PROJECT.md (if needed)
- ✅ Suggests code changes (if needed)
- ✅ Creates documentation (if needed)
- ✅ Removes scope drift (if needed)
- ✅ Commits changes

---

## Example: Analyzing Misalignment

```
🔍 Analyzing project alignment with PROJECT.md...

Found 5 conflicts:

CONFLICT #1: GraphQL Scope Mismatch
────────────────────────────────────
PROJECT.md says:
  SCOPE (Out of Scope):
    - GraphQL API

Reality shows:
  graphql/ directory exists with resolvers implemented

What should we do?
A) YES - PROJECT.md is correct (remove GraphQL code)
B) NO - Update PROJECT.md to include GraphQL

Your choice [A/B]: A

Action: Remove graphql/ directory and update PROJECT.md
Impact: Removes ~200 lines of code (not in scope)
```

## Example: Completing a Conflict

```
CONFLICT #2: Missing Test Structure
────────────────────────────────────
PROJECT.md says:
  Tests organized in: tests/unit/, tests/integration/

Reality shows:
  Only tests/ directory exists (no subdirectories)

What should we do?
A) YES - PROJECT.md is correct (organize tests)
B) NO - Update PROJECT.md to reflect current structure

Your choice [A/B]: A

Action: Organize existing tests into unit/integration/uat
Impact: Makes testing structure match documentation
```

---

## Typical Workflow

### First Time Setup

```bash
# 1. Run alignment
/align-project

# 2. Agent analyzes and asks about each conflict
# 3. You choose A (PROJECT.md correct) or B (update PROJECT.md)
# 4. Agent implements your choices
# 5. Agent commits changes with summary
```

### Periodic Checks

```bash
# Check alignment
/align-project

# If fully aligned:
# ✅ No conflicts found - project is well-aligned!

# If conflicts found:
# Answer each question to resolve
```

---

## What the Agent Does

### Analysis Phase
- ✅ Reads PROJECT.md entirely
- ✅ Scans codebase (src/, lib/, components/, etc.)
- ✅ Checks documentation (README, docs/, etc.)
- ✅ Identifies conflicts between stated goals and reality
- ✅ Groups related issues together

### Question Phase
- ✅ Asks binary questions (clear A or B choices)
- ✅ Explains context for each conflict
- ✅ Shows what code exists vs. what PROJECT.md says
- ✅ Suggests practical fixes

### Execution Phase
- ✅ Updates PROJECT.md (if you choose B)
- ✅ Removes unscoped code (if you choose A)
- ✅ Organizes files to match scope
- ✅ Commits changes with clear messages

---

## Safety Features

✅ **Analysis before action**: Agent shows conflicts before making changes
✅ **Binary questions**: No ambiguity - clear choices
✅ **Clear impact**: Agent explains what each choice does
✅ **Reversible**: Changes are committed (easy rollback)
✅ **Stop anytime**: Can exit at any point

---

## When to Use This Command

**Run /align-project when**:
- 🆕 First time setup (understand project scope)
- 📊 After major development (ensure docs match code)
- 🔄 After PROJECT.md changes (verify implementation updated)
- 🔍 Before releases (ensure scope is accurate)
- 👥 Onboarding team members (clarify what's in/out of scope)

**No need if**:
- Project already aligned (agent will say "no conflicts found")
- You just want to code quickly (can skip)

---

## Troubleshooting

### "PROJECT.md not found"

```bash
# Create PROJECT.md first
/setup

# Then run alignment
/align-project
```

### "Agent can't find files"

- Check that PROJECT.md exists and is readable
- Verify codebase has typical structure (src/, lib/, etc.)
- Agent may need broader scope to find features

### "Disagreeing with agent's analysis"

Agent analyzes based on PROJECT.md being the source of truth. If you disagree:
- Choose `B) NO` to update PROJECT.md instead
- Agent will adapt the documentation to match reality

---

## Related Commands

- `/setup` - Create or update PROJECT.md
- `/test` - Run tests after alignment
- `/auto-implement` - Autonomous feature development

---

**Use this to find conflicts between your documented goals and actual implementation. Agent intelligently guides you to alignment.**
