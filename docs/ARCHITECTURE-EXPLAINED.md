# Architecture Explained: How autonomous-dev Actually Works

**Last Updated**: 2025-11-03
**Version**: v3.1.0

---

## Overview

autonomous-dev uses a **two-layer architecture** that combines:
1. **Hook-Based Enforcement** (automatic, 100% reliable)
2. **Agent-Based Intelligence** (optional, AI-enhanced assistance)

This document explains what each layer does and how they work together.

---

## Layer 1: Hook-Based Enforcement (The Foundation)

### What It Does

Hooks are Python scripts that run automatically on every commit to enforce quality gates:

**Always Validated:**
- ✅ PROJECT.md alignment (features must serve goals)
- ✅ Security scanning (no secrets, no vulnerabilities)
- ✅ Test generation (missing tests auto-generated)
- ✅ Documentation sync (docs match code)
- ✅ File organization (standard structure enforced)
- ✅ Code quality (formatting, linting)

### How It Works

```
Developer commits code
    ↓
Pre-commit hooks execute (AUTOMATIC)
    ├─ validate_project_alignment.py → Checks PROJECT.md
    ├─ security_scan.py → Scans for secrets/vulnerabilities
    ├─ auto_generate_tests.py → Generates missing tests
    ├─ auto_update_docs.py → Updates documentation
    ├─ validate_docs_consistency.py → Validates doc accuracy
    └─ auto_fix_docs.py → Fixes doc inconsistencies
    ↓
If ALL pass → Commit allowed ✅
If ANY fail → Commit blocked ❌ (Claude sees errors and can fix)
```

### Key Characteristics

**Reliability**: 100% execution rate
- Hooks ALWAYS run on every commit
- No user action required
- Cannot be skipped (except with --no-verify, which is discouraged)

**Enforcement**: Blocking validation
- Failed hooks block commits
- Claude sees error messages
- Claude can fix issues and retry

**Performance**: Fast execution
- All hooks complete in < 10 seconds
- Minimal disruption to workflow

### Available Hooks

**Core Hooks (9)** - Recommended for all projects:
- `validate_project_alignment.py` - PROJECT.md gatekeeper
- `security_scan.py` - Secret and vulnerability detection
- `auto_format.py` - Code formatting (black, prettier)
- `auto_test.py` - Run relevant tests
- `auto_generate_tests.py` - Generate missing tests
- `auto_update_docs.py` - Update documentation
- `validate_docs_consistency.py` - Validate doc accuracy
- `enforce_file_organization.py` - File structure enforcement
- `auto_fix_docs.py` - Auto-fix documentation issues

**Extended Hooks (19)** - Optional advanced features:
- `enforce_orchestrator.py` - Validates orchestrator ran
- `enforce_tdd.py` - Enforces tests-before-code
- `auto_enforce_coverage.py` - 80% minimum coverage
- `auto_add_to_regression.py` - Regression test tracking
- `validate_claude_alignment.py` - CLAUDE.md alignment
- Plus 14 others for specialized enforcement

---

## Layer 2: Agent-Based Intelligence (The Enhancement)

### What It Does

Agents are AI specialists that provide expert assistance when invoked:

**Available Specialists:**
- 🔍 **researcher** - Finds patterns and best practices
- 📐 **planner** - Designs architecture and implementation plans
- ✍️  **test-master** - Creates comprehensive test strategies
- 💻 **implementer** - Writes clean, tested code
- 👀 **reviewer** - Reviews code quality and patterns
- 🔒 **security-auditor** - Scans for security vulnerabilities
- 📖 **doc-master** - Synchronizes documentation

### How It Works

```
User requests feature (manual or /auto-implement)
    ↓
orchestrator agent (optional invocation)
    ├─ Validates PROJECT.md alignment
    ├─ MAY invoke researcher (if research needed)
    ├─ MAY invoke planner (if architecture needed)
    ├─ MAY invoke test-master (if tests needed)
    ├─ MAY invoke implementer (if code needed)
    ├─ MAY invoke reviewer (if review needed)
    ├─ MAY invoke security-auditor (if security check needed)
    └─ MAY invoke doc-master (if docs need updating)
    ↓
Claude implements feature (with or without agent help)
    ↓
Pre-commit hooks validate (AUTOMATIC, GUARANTEED)
    ↓
Quality gates enforced regardless of agent usage
```

### Key Characteristics

**Invocation**: Manual or conditional
- User explicitly requests via `/auto-implement`
- orchestrator MAY invoke agents (not guaranteed)
- Claude decides based on feature complexity

**Intelligence**: Adaptive reasoning
- Claude determines which agents are needed
- Simple features may skip some agents
- Complex features may use all agents

**Flexibility**: Not rigid
- Agents can be invoked in different orders
- Some agents may be skipped if unnecessary
- Claude adapts based on discoveries

### Agent Invocation Patterns

**Simple Feature** (< 50 lines):
```
/auto-implement "add health check endpoint"
→ May invoke: researcher + implementer only
→ Total: 2-3 agents
```

**Medium Feature** (50-200 lines):
```
/auto-implement "add Redis caching layer"
→ May invoke: researcher + planner + implementer + reviewer
→ Total: 4-5 agents
```

**Complex Feature** (200+ lines):
```
/auto-implement "implement JWT authentication with refresh tokens"
→ May invoke: ALL 7 agents
→ Total: 7 agents (full pipeline)
```

**Security-Sensitive Feature**:
```
/auto-implement "add API key management"
→ ALWAYS invokes: security-auditor (in addition to others)
→ Guaranteed security review
```

---

## How the Layers Work Together

### Example: Adding JWT Authentication

**User Action:**
```bash
/auto-implement "implement JWT authentication with refresh token rotation"
```

**orchestrator Agent (Layer 2 - Intelligence):**
1. Reads PROJECT.md
2. Validates: "Authentication is in SCOPE ✅"
3. Decides: "This is complex and security-sensitive"
4. Invokes researcher: "Find JWT best practices"
5. Invokes planner: "Design auth architecture"
6. Invokes test-master: "Write comprehensive auth tests"
7. Invokes implementer: "Implement based on tests"
8. Invokes reviewer: "Review auth code quality"
9. Invokes security-auditor: "Scan for auth vulnerabilities"
10. Invokes doc-master: "Document auth flow"

**Developer Implementation:**
- Code written following agent guidance
- Tests created first (TDD)
- Documentation updated

**Pre-commit Hooks (Layer 1 - Enforcement):**
```bash
git commit -m "feat: add JWT authentication"

→ validate_project_alignment.py ✅ (Auth is in PROJECT.md SCOPE)
→ security_scan.py ✅ (No hardcoded secrets)
→ auto_generate_tests.py ✅ (Tests exist)
→ auto_update_docs.py ✅ (Docs updated)
→ validate_docs_consistency.py ✅ (Docs accurate)

Commit allowed ✅
```

**Result:** Professional-quality feature with:
- AI-enhanced design (agents)
- Guaranteed quality gates (hooks)
- Full SDLC compliance

---

## What's Guaranteed vs What's Optional

### ✅ Guaranteed (Hooks - 100% Reliable)

**Every commit is validated for:**
- PROJECT.md alignment
- Security (no secrets, no vulnerabilities)
- Tests exist and pass
- Documentation synchronized
- File organization standards
- Code quality standards

**These run automatically. No exceptions.**

### 🤖 Optional (Agents - AI-Enhanced)

**Agents provide assistance when:**
- User invokes `/auto-implement`
- orchestrator decides agents would help
- Feature is complex enough to warrant research/planning
- User explicitly asks agent for help

**These run conditionally. Not guaranteed.**

---

## Philosophy: Why This Design?

From PROJECT.md:

> **The key difference**: Instead of rigid Python sequences, Claude's reasoning adapts based on what it discovers:
> - Finds unexpected patterns? → Adjusts approach
> - Discovers missing test coverage? → Adds tests
> - Realizes docs are incomplete? → Updates them more thoroughly
> - Encounters edge cases? → Handles them intelligently

### Design Principles

**1. Trust the Model**
- Claude is smart enough to decide which agents to invoke
- Don't force rigid sequences
- Let AI reasoning adapt to context

**2. Enforce Quality via Hooks**
- Hooks catch violations 100% of the time
- Agents provide intelligence, hooks provide safety
- Quality is guaranteed, not hoped for

**3. Human-in-the-Loop Enhancement**
- Agents assist, don't replace human judgment
- User can invoke agents manually when needed
- Progressive disclosure (load intelligence when valuable)

**4. No Python Orchestration**
- GenAI reasoning > rigid Python logic
- Flexibility > predictability
- Intelligence > automation

---

## Common Questions

### Q: How do I know agents actually ran?

**A:** Check session logs in `docs/sessions/`. Each agent logs its execution.

Future enhancement (Issue #29): Add `/pipeline-status` command to show agent execution.

### Q: What if agents don't run but I wanted them to?

**A:** You can invoke agents manually:
- "Ask the researcher agent about JWT best practices"
- "Have the planner agent design the architecture"
- "Let the security-auditor review this code"

### Q: Are hooks enough without agents?

**A:** Yes. Hooks guarantee quality gates. Agents add intelligence but aren't required.

**Example workflow without agents:**
1. Developer implements feature manually
2. Commits code
3. Hooks validate everything
4. If hooks pass → professional quality guaranteed

**With agents:** Same outcome + AI-enhanced design decisions.

### Q: Can I disable hooks?

**A:** Yes, but not recommended. Edit `.claude/settings.local.json` and remove hooks.

**Warning:** Disabling hooks removes quality guarantees. Agents alone don't enforce standards.

### Q: Can I force agents to always run?

**A:** Not with GenAI approach (by design - trust the model).

Future enhancement (Issue #32): Make orchestrator prompt more directive to increase likelihood of agent invocation.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  autonomous-dev: Two-Layer Architecture                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Agent-Based Intelligence (OPTIONAL)               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  orchestrator → Validates PROJECT.md alignment       │   │
│  │      ↓                                               │   │
│  │  researcher → Finds patterns & best practices        │   │
│  │      ↓                                               │   │
│  │  planner → Designs architecture                      │   │
│  │      ↓                                               │   │
│  │  test-master → Writes tests (TDD)                    │   │
│  │      ↓                                               │   │
│  │  implementer → Writes code                           │   │
│  │      ↓                                               │   │
│  │  reviewer → Reviews quality                          │   │
│  │      ↓                                               │   │
│  │  security-auditor → Scans security                   │   │
│  │      ↓                                               │   │
│  │  doc-master → Updates docs                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Result: AI-enhanced design & implementation                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Hook-Based Enforcement (AUTOMATIC, 100% RELIABLE) │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Pre-Commit Hooks (run on every commit)             │   │
│  │    ├─ validate_project_alignment.py                 │   │
│  │    ├─ security_scan.py                              │   │
│  │    ├─ auto_generate_tests.py                        │   │
│  │    ├─ auto_update_docs.py                           │   │
│  │    ├─ validate_docs_consistency.py                  │   │
│  │    └─ auto_fix_docs.py                              │   │
│  │                                                      │   │
│  │  If ALL pass → Commit allowed ✅                    │   │
│  │  If ANY fail → Commit blocked ❌                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Result: Guaranteed professional quality                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Value Proposition

### What You Get

**With Hooks Alone:**
- ✅ Professional quality guaranteed
- ✅ Security enforced
- ✅ Tests required
- ✅ Documentation synchronized
- ✅ PROJECT.md alignment validated

**With Hooks + Agents:**
- ✅ Everything above, PLUS:
- 🤖 AI-researched best practices
- 🤖 AI-designed architectures
- 🤖 AI-generated test strategies
- 🤖 AI-reviewed code quality
- 🤖 AI-enhanced documentation

**Result:** Professional quality (hooks) + Expert intelligence (agents)

---

## Next Steps

**For New Users:**
1. Start with hooks only (reliable foundation)
2. Learn `/auto-implement` command (agent orchestration)
3. Experiment with manual agent invocation
4. Customize which hooks to enable

**For Contributors:**
1. Read this architecture guide
2. Review PROJECT.md for philosophy
3. Check CLAUDE.md for development standards
4. See plugin/autonomous-dev/README.md for setup

**For Troubleshooting:**
- Hooks failing? Check error messages (clear and actionable)
- Agents not running? Check `docs/sessions/` for logs
- Questions? See docs/TROUBLESHOOTING.md

---

**Summary:** autonomous-dev combines deterministic enforcement (hooks) with intelligent assistance (agents) to deliver professional-quality code with AI enhancement.
