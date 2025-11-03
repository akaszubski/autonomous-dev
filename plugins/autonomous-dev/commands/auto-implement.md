---
description: Autonomously implement a feature using orchestrator agent
argument-hint: Feature description (e.g., "user authentication with JWT tokens")
---

## Implementation

Invoke the orchestrator agent to autonomously implement features with full SDLC workflow (research → plan → test → implement → review → security → documentation).

# Autonomous Implementation

Autonomously implement a feature by invoking the orchestrator agent.

## What This Does

You describe what you want. This command provides **AI-assisted feature implementation**:

1. **Claude validates alignment** - Checks PROJECT.md to ensure feature aligns (REQUIRED)
2. **Claude MAY invoke specialist agents** for help (conditional based on complexity):
   - researcher → Finds patterns and best practices
   - planner → Designs implementation approach
   - test-master → Writes failing tests (TDD)
   - implementer → Implements code
   - reviewer → Quality gate check
   - security-auditor → Vulnerability scanning
   - doc-master → Updates documentation
3. **Claude implements the feature** with or without agent assistance
4. **Pre-commit hooks validate** (AUTOMATIC, GUARANTEED):
   - PROJECT.md alignment ✅
   - Security scanning ✅
   - Test coverage ✅
   - Documentation sync ✅

**Total**: ~20-40 minutes for professional-quality feature with quality gates enforced.

## Usage

Just describe what you want:

```bash
/auto-implement user authentication with JWT tokens

/auto-implement Redis caching layer with 5-minute TTL

/auto-implement REST API for blog posts with CRUD, pagination, full-text search
```

That's it. The orchestrator handles everything.

## How It Works

This command uses **GenAI-native orchestration** (not rigid Python scripts):

1. Claude reads `.claude/PROJECT.md` to understand goals/scope/constraints
2. Claude validates your request aligns with PROJECT.md (BLOCKS if misaligned)
3. If aligned: Claude **may invoke specialist agents** for expert assistance
   - Simple features: May skip some agents
   - Complex features: May use all agents
   - Claude decides adaptively
4. Claude implements the feature (with or without agent help)
5. Pre-commit hooks enforce quality gates (AUTOMATIC, GUARANTEED)

**The key distinction**:
- **Hooks** = enforcement (100% reliable, always run)
- **Agents** = intelligence (conditional, invoked when helpful)

**Why GenAI orchestration over Python?**

| Python-Based | GenAI-Based (This) |
|--------------|-------------------|
| Fixed sequence | Adapts to discoveries |
| Predefined cases | Intelligent reasoning |
| Coded edge cases | Handles naturally |
| Rigid automation | Flexible intelligence |

See PROJECT.md lines 213-221 for full rationale.

## Prerequisites

You need a `.claude/PROJECT.md` file with:

```markdown
# Project Context

## GOALS
- Your primary objectives
- Success metrics

## SCOPE

### In Scope
- Features you're building

### Out of Scope
- Features to avoid

## CONSTRAINTS
- Technical constraints
- Business constraints
```

**Don't have one?** Create it:

```bash
mkdir -p .claude
cat > .claude/PROJECT.md << 'EOF'
# Project Context

## GOALS
- Define your project goals here

## SCOPE

### In Scope
- What you're building

### Out of Scope
- What you're NOT building

## CONSTRAINTS
- Technical or business constraints
EOF

# Edit with your actual project context
vim .claude/PROJECT.md
```

## Examples

### Simple Feature

```bash
/auto-implement health check endpoint that returns JSON status
```

**What orchestrator does**:
- Plans: Simple endpoint, no dependencies
- Tests: Basic GET request test
- Implements: 30 lines of code
- Docs: Updates README with endpoint info

### Medium Complexity

```bash
/auto-implement user authentication with JWT tokens and refresh token rotation
```

**What orchestrator does**:
- Research: JWT best practices, refresh token patterns
- Plan: Token generation, rotation strategy, storage
- Test: Token generation, validation, rotation, expiry
- Implement: Auth service, token management, middleware
- Security: Validates no hardcoded secrets, secure storage
- Docs: Auth flow diagram, usage examples

### High Complexity

```bash
/auto-implement REST API for blog posts with:
- CRUD operations
- Pagination (20 per page)
- Full-text search
- Tag filtering
- Author association
- Draft/published status
- Timestamps
```

**What orchestrator does**:
- Research: REST conventions, search patterns, pagination best practices
- Plan: Database schema, API design, filter logic
- Test: 50+ tests covering all operations and edge cases
- Implement: API endpoints, filtering, search, pagination
- Review: API consistency, error handling
- Security: Input validation, authorization checks
- Docs: API documentation with examples

## What's Guaranteed vs What's Conditional

### ✅ Guaranteed (via Hooks - 100% Reliable)

Every commit is validated for:
- PROJECT.md alignment
- Security (no secrets, no vulnerabilities)
- Tests exist and pass
- Documentation synchronized
- File organization
- Code quality

**Hooks run automatically. Always.**

### 🤖 Conditional (via Agents - Adaptive)

Agents **may** be invoked when:
- Feature is complex enough to warrant research
- Architecture decisions needed
- Security-sensitive operations
- Claude determines assistance would help

**Agents run conditionally. Not guaranteed.**

## What Happens If Misaligned

```bash
/auto-implement add GraphQL API
```

```
❌ BLOCKED: Feature not aligned with PROJECT.md

PROJECT.md SCOPE says:
  In Scope: REST API endpoints
  Out of Scope: GraphQL

Your request: "add GraphQL API"

This conflicts with project scope.

Options:
1. Update PROJECT.md if strategy changed
2. Modify request to align with current SCOPE
3. Don't implement
```

## Workflow Visibility

The orchestrator shows you progress as it works:

```
🔍 Validating alignment... ✅ Aligned
📚 Researching patterns...  ✅ Found 3 existing implementations
📐 Planning approach...     ✅ Design approved
✍️  Writing tests...        ✅ 15 tests (all failing)
💻 Implementing...          ✅ 45 tests passing
👀 Reviewing code...        ✅ Quality approved
🔒 Security scan...         ✅ No issues
📖 Updating docs...         ✅ Complete

✨ Feature complete! Session: docs/sessions/2025-10-27-...
```

## Context Management

After the feature completes, run:

```bash
/clear
```

This resets your context budget for the next feature. **This is mandatory** for performance (prevents context bloat).

## Why This Is Better Than Python Orchestration

| Aspect | Python-Based | GenAI-Based (This) |
|--------|------------|-----------------|
| Flexibility | Fixed sequence | Adapts to discoveries |
| Error handling | Predefined cases | Intelligent reasoning |
| Edge cases | Coded manually | Claude handles naturally |
| Performance | Overhead (artifacts, JSON) | Lean & direct |
| Extensibility | Requires Python changes | Claude adapts automatically |
| Debugging | Check JSON files | See Claude's reasoning |
| Maintenance | Python complexity | Simple markdown agents |

## How It Actually Works (Behind The Scenes)

1. You run: `/auto-implement your feature description`
2. Claude Code invokes orchestrator agent with your request
3. Orchestrator agent:
   - Reads `.claude/PROJECT.md`
   - Validates alignment (pure reasoning, no code)
   - Invokes researcher agent (via Task tool)
   - Waits for researcher to complete
   - Invokes planner agent
   - Invokes test-master agent
   - ... continues through all 7 agents
4. After each agent completes, orchestrator reviews output
5. Orchestrator prompts: "Run `/clear` for next feature"
6. You're done

No Python scripts. No JSON artifacts. No checkpointing. Just Claude thinking through the problem and coordinating agents.

## Troubleshooting

### "PROJECT.md not found"

Create it:
```bash
mkdir -p .claude
# Copy template from prerequisites section above
vim .claude/PROJECT.md
```

### "Feature doesn't align"

The orchestrator will tell you why and what to do. Either:
1. Modify your feature request to fit scope
2. Update PROJECT.md if strategy changed
3. Don't implement

### "Feature was partially done"

If interrupted, just run the command again. The orchestrator will:
- Start fresh with your request
- Use the existing partially-done code as context
- Continue where it left off (intelligently, not just resuming)

### "I want to change how it works"

You can:
1. Modify `.claude/PROJECT.md` (change scope/constraints)
2. Modify `plugins/autonomous-dev/agents/orchestrator.md` (change coordination logic)
3. Run again - Claude will use new instructions

Everything is transparent and modifiable.

## Advanced: Custom Orchestration

Want different workflow? Create a custom agent:

```bash
# Copy orchestrator as template
cp plugins/autonomous-dev/agents/orchestrator.md \
   plugins/autonomous-dev/agents/orchestrator-custom.md

# Edit your custom orchestrator
vim plugins/autonomous-dev/agents/orchestrator-custom.md

# Use it:
/your-custom-command my feature
```

Your custom agent can:
- Skip steps (no security scan needed?)
- Reorder steps (docs first?)
- Add custom agents (database-migration agent?)
- Change validation logic

Pure GenAI flexibility.

## Philosophy

This command embodies Claude Code's core principle:

> "Not a toolkit. A team."

The orchestrator is a team leader that:
- Thinks about the problem (not rigid sequences)
- Coordinates specialists (researcher, implementer, etc.)
- Adapts based on what it finds
- Handles complexity intelligently
- Trusts the model (Claude's reasoning > Python logic)

---

**That's it.** Just describe your feature and let Claude handle it.

The orchestrator will coordinate everything and show you progress along the way.

