# Architectural Intent & Decisions

**Purpose**: This document captures WHY the autonomous-dev plugin is designed the way it is. Tests validate these architectural invariants.

**Last Updated**: 2025-10-20
**Version**: 2.0.0

---

## Core Design Principles

### 1. PROJECT.md-First Architecture

**Intent**: Prevent scope creep and ensure all work aligns with strategic goals.

**How**: Orchestrator validates every feature against PROJECT.md before starting work.

**Why**: Without this, agents implement whatever is asked without considering if it serves project goals. This leads to:
- Feature bloat
- Wasted effort on out-of-scope work
- Inconsistent technical decisions

**Validation**: `test_architectural_intent.py::test_project_md_first_validated`

**Breaking Change If**: Orchestrator no longer validates PROJECT.md, or PROJECT.md becomes optional.

---

### 2. 8-Agent Pipeline

**Intent**: Separate concerns and optimize costs through specialization.

**Pipeline**:
```
orchestrator (coordinator)
    ↓
researcher (5 min, web research)
    ↓
planner (5 min, opus model - expensive but thorough)
    ↓
test-master (5 min, TDD - tests first!)
    ↓
implementer (12 min, makes tests pass)
    ↓
reviewer (2 min, quality gate)
    ↓
security-auditor (2 min, haiku model - fast security scan)
    ↓
doc-master (1 min, haiku model - fast docs update)
```

**Why 8 agents**:
- **Orchestrator**: Validates alignment, manages context budget
- **Researcher**: Web research for best practices (prevents reinventing wheel)
- **Planner**: Architecture decisions (uses opus for deep thinking)
- **Test-master**: TDD enforcement (tests before code)
- **Implementer**: Code implementation (makes tests pass)
- **Reviewer**: Quality gate (catches issues before merge)
- **Security-auditor**: Security scan (fast with haiku)
- **Doc-master**: Documentation sync (fast with haiku)

**Why this order**:
- Validation first (orchestrator)
- Research before design (researcher)
- Design before implementation (planner)
- Tests before code (test-master)
- Implementation to spec (implementer)
- Quality check (reviewer)
- Security check (security-auditor)
- Documentation last (doc-master)

**Validation**: `test_architectural_intent.py::test_eight_agent_pipeline`

**Breaking Change If**: Pipeline order changes, agents are combined, or agents are removed.

---

### 3. Model Optimization (40% Cost Reduction)

**Intent**: Use the right model for the job to minimize costs.

**Strategy**:
- **Opus**: Complex planning (planner agent only)
- **Sonnet**: Most agents (balanced cost/quality)
- **Haiku**: Fast operations (security, docs)

**Why**:
- Opus is expensive (~15x haiku) but needed for architecture decisions
- Haiku is cheap but sufficient for security scans and doc updates
- Sonnet is the default for most work

**Cost Impact**:
- Before: All agents use Sonnet → $X per feature
- After: Planner uses Opus, Security/Docs use Haiku → 40% reduction

**Validation**: `test_architectural_intent.py::test_model_selection_strategy`

**Breaking Change If**: All agents use same model, or expensive models used for cheap operations.

---

### 4. Context Management (Scales to 100+ Features)

**Intent**: Keep context budget under control so system doesn't degrade after 3-4 features.

**Strategy**:
- Session logging to files (not context)
- /clear command after each feature
- Agents log to `docs/sessions/` directory
- Context stays <8K tokens per feature

**Why**:
- Without clearing: Context grows 50K+ after 3-4 features → system fails
- With clearing: Context stays <1K per feature → works for 100+ features

**Validation**: `test_architectural_intent.py::test_context_management_strategy`

**Breaking Change If**: Session logging removed, /clear not promoted, agents communicate in context.

---

### 5. Opt-In Automation (User Control)

**Intent**: Give users choice between manual control and full automation.

**Two Modes**:
1. **Slash Commands** (default): Manual control, run `/format`, `/test` when ready
2. **Automatic Hooks**: Full automation, hooks run on tool use and commit

**Why**:
- Beginners need explicit control to learn
- Power users want zero manual intervention
- Forcing automation scares new users

**Configuration**:
- Slash commands: No config needed
- Automatic: Create `.claude/settings.local.json` via `/setup`

**Validation**: `test_architectural_intent.py::test_opt_in_automation`

**Breaking Change If**: Hooks auto-enable, or no manual mode available.

---

### 6. Project-Level vs Global Scope

**Intent**: Plugin works across multiple projects without interference.

**Design**:
- Plugin installed globally in Claude Code
- Setup copies files to project (`.claude/hooks/`, `.claude/templates/`)
- Each project has own PROJECT.md and settings
- `/uninstall` removes project files, keeps plugin global

**Why**:
- Users work on multiple projects
- Each project has different goals/constraints
- Plugin shouldn't interfere between projects

**Validation**: `test_architectural_intent.py::test_project_level_isolation`

**Breaking Change If**: Global configuration affects all projects, or can't use plugin in multiple projects.

---

### 7. TDD Enforcement

**Intent**: Tests are written BEFORE code, not after.

**How**: test-master agent runs before implementer in pipeline.

**Why**:
- Tests written after are often incomplete
- TDD ensures code is testable
- Prevents "we'll add tests later" (which never happens)

**Validation**: `test_architectural_intent.py::test_tdd_enforced`

**Breaking Change If**: Test-master runs after implementer, or tests are optional.

---

### 8. Read-Only Planning

**Intent**: Planner and reviewer can't accidentally modify code.

**How**: These agents don't have Write/Edit tools.

**Why**:
- Planning should be separate from implementation
- Review should be objective (can't fix issues, only report them)
- Forces clear handoffs between pipeline stages

**Validation**: `test_architectural_intent.py::test_read_only_planning`

**Breaking Change If**: Planner or reviewer gain Write/Edit tools.

---

### 9. Security-First Design

**Intent**: Security issues caught before commit.

**How**:
- Security-auditor runs in pipeline (for /auto-implement)
- Security scan runs pre-commit (if automatic hooks)
- Uses haiku for speed (can afford to run often)

**Why**:
- Security issues are expensive to fix later
- Automated scanning prevents human error
- Fast model means no developer friction

**Validation**: `test_architectural_intent.py::test_security_first`

**Breaking Change If**: Security scan becomes optional or removed from pipeline.

---

### 10. Documentation Sync

**Intent**: Documentation never falls out of sync with code.

**How**:
- doc-master runs last in pipeline
- Updates CHANGELOG, README, API docs automatically
- Uses haiku for speed

**Why**:
- Manual doc updates are often forgotten
- Stale docs are worse than no docs
- Automated sync ensures accuracy

**Validation**: `test_architectural_intent.py::test_documentation_sync`

**Breaking Change If**: Doc updates become manual or removed from pipeline.

---

## Context & Data Exchange

### 11. Agent Communication Strategy

**Intent**: Agents communicate via session files, not context.

**How**:
- Agents log actions to `docs/sessions/YYYYMMDD-HHMMSS-session.md`
- Context contains only current work
- Session files contain history

**Why**:
- Context has hard limit (200K tokens)
- Session files are unlimited
- Keeps context focused on current task
- Historical data doesn't bloat current work

**Context Budget**:
- Orchestrator: <500 tokens (coordination only)
- Researcher: 2-5K tokens (web results)
- Planner: 3-5K tokens (architecture design)
- Test-master: 2-3K tokens (test specs)
- Implementer: 5-10K tokens (code generation)
- Reviewer: 1-2K tokens (review comments)
- Security-auditor: 500-1K tokens (scan results)
- Doc-master: 500-1K tokens (doc updates)

**Total per feature**: 15-25K tokens (well under 200K limit)

**Validation**: `test_architectural_intent.py::test_context_budget_management`

**Breaking Change If**: Agents communicate via context instead of files, or single agent uses >25K tokens.

---

### 12. Agent Specialization (No Duplication)

**Intent**: Each agent has unique, non-overlapping responsibility.

**Responsibilities**:
| Agent | Unique Role | NOT Responsible For |
|-------|-------------|-------------------|
| orchestrator | Validates alignment, coordinates pipeline | Does not implement |
| researcher | Web research for best practices | Does not plan architecture |
| planner | Architecture decisions | Does not write code |
| test-master | Writes tests first (TDD) | Does not implement features |
| implementer | Makes tests pass | Does not design architecture |
| reviewer | Quality gate, identifies issues | Does not fix issues |
| security-auditor | Security scanning | Does not fix vulnerabilities |
| doc-master | Updates documentation | Does not write features |

**Why No Overlap**:
- Clear separation of concerns
- Prevents conflicting decisions
- Each agent optimized for its task
- No wasted effort on duplicate work

**Validation**: `test_architectural_intent.py::test_agent_specialization_no_overlap`

**Breaking Change If**: Agents gain overlapping responsibilities or single agent does multiple jobs.

---

### 13. Skill Boundaries (No Redundancy)

**Intent**: Each skill covers unique domain expertise.

**Skill Domains**:
| Skill | Coverage | Does NOT Cover |
|-------|----------|----------------|
| python-standards | PEP 8, type hints, docstrings | Not testing or security |
| testing-guide | TDD, pytest, coverage | Not language-specific syntax |
| security-patterns | Secrets, OWASP, vulnerabilities | Not code quality |
| documentation-guide | CHANGELOG, API docs, README | Not code implementation |
| research-patterns | Web search, pattern discovery | Not specific to one language |
| engineering-standards | Git workflow, code review | Not language or domain specific |

**Why No Redundancy**:
- Clear expertise boundaries
- Skills can be combined (e.g., python-standards + testing-guide)
- Prevents conflicting advice
- Each skill activates based on context

**Validation**: `test_architectural_intent.py::test_skill_boundaries_no_redundancy`

**Breaking Change If**: Skills cover overlapping domains or give conflicting guidance.

---

### 14. Data Flow (One Direction)

**Intent**: Information flows forward through pipeline, not backward.

**Flow Direction**:
```
orchestrator → PROJECT.md validation
    ↓ (feature description)
researcher → best practices
    ↓ (research findings)
planner → architecture design
    ↓ (implementation plan)
test-master → test specifications
    ↓ (failing tests)
implementer → working code
    ↓ (code + tests)
reviewer → quality report
    ↓ (issues found)
security-auditor → security scan results
    ↓ (vulnerabilities)
doc-master → updated documentation
    ↓ (CHANGELOG, README)
```

**Why One Direction**:
- Prevents circular dependencies
- Clear handoffs between stages
- Each agent builds on previous work
- No rework loops (except on failure)

**Validation**: `test_architectural_intent.py::test_data_flow_one_direction`

**Breaking Change If**: Agents communicate backward in pipeline or have circular dependencies.

---

## Architectural Invariants

**These MUST remain true, or the architecture has fundamentally changed:**

### Must Have
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

### Must Not Have
- ✗ Agents with both read and write that shouldn't have both
- ✗ All agents using same model
- ✗ Tests written after code
- ✗ Automatic hook enablement without user consent
- ✗ Global configuration affecting multiple projects
- ✗ Security scan as optional
- ✗ Context communication instead of session files
- ✗ Overlapping agent responsibilities
- ✗ Redundant skills
- ✗ Circular data flow
- ✗ Single agent using >25K tokens

---

## Design Decisions & Rationale

### Why Markdown for Agent/Skill Definitions?

**Decision**: Agents and skills are `.md` files, not code.

**Why**:
- Human readable and editable
- Version control friendly
- Claude Code's native format
- Easy for users to customize

**Alternative Considered**: Python classes
**Rejected Because**: Harder for non-programmers to modify

---

### Why Separate Templates Directory?

**Decision**: Templates in `templates/`, not `examples/`.

**Why**:
- Clear intent: These are meant to be copied
- Setup script knows where to find them
- Separates reference material from working files

---

### Why Gitignore .claude/settings.local.json?

**Decision**: Hook configuration is gitignored.

**Why**:
- Personal preference (some devs want hooks, others don't)
- Prevents team conflicts
- Each developer chooses their workflow

---

### Why Both /setup Command AND setup.py Script?

**Decision**: Interactive command + automated script.

**Why**:
- Interactive: Great for individuals
- Script: Great for team standardization and CI/CD
- Flexibility for different use cases

---

### Why Named Presets (team, solo, power-user)?

**Decision**: Pre-configured workflows instead of raw options.

**Why**:
- Reduces decision paralysis
- Tested configurations
- Easy onboarding for new users
- Can still customize after

---

## Change History

### v2.0.0 (2025-10-20)
- **MAJOR**: Added orchestrator agent (PRIMARY MISSION)
- **MAJOR**: PROJECT.md-first architecture (alignment validation)
- **FEATURE**: Model optimization (opus/sonnet/haiku)
- **FEATURE**: Context management strategy (/clear + session logs)
- **FEATURE**: /setup and /uninstall commands
- **FEATURE**: Opt-in automation (slash commands vs hooks)

### v1.0.0 (Previous)
- Initial 7-agent pipeline
- Basic hook system
- Command structure

---

## Testing This Document

### Two-Layer Validation Strategy

**Why Two Layers?**
- **Static tests** (pytest) catch obvious structural violations
- **GenAI validation** (Claude) detects subtle intent drift
- Both are needed for comprehensive coverage

---

### Layer 1: GenAI-Powered Validation (PRIMARY) ⭐

**How to validate**: Run `/validate-architecture`

**What it checks**:
- Does implementation **actually** align with documented **INTENT**?
- Are agents **behaving** as designed (not just structured correctly)?
- Does the **meaning** of the code match the **purpose** documented?
- Subtle architectural drift that static tests can't catch

**Why GenAI?**:
- Claude understands **MEANING**, not just structure
- Can evaluate if behavior matches intent
- Detects drift like: "orchestrator.md mentions PROJECT.md validation, but doesn't actually implement it"
- Provides contextual explanations of WHY something violates intent

**Example**:

Static test limitation:
```python
# Can only check if word exists
assert "PROJECT.md" in orchestrator_content
```

GenAI validation:
```
Read orchestrator.md. Does it actually validate PROJECT.md
before starting work? Look for Task tool calls, alignment
validation logic, blocking behavior if out of scope.
Don't just check if word exists - validate the BEHAVIOR.
```

**When to run**:
- Before each release (mandatory)
- After major changes to agents/skills
- Monthly maintenance check
- When architectural drift suspected

---

### Layer 2: Static Tests (FALLBACK)

**How to validate**: Run `pytest tests/test_architectural_intent.py -v`

**What it checks**:
- All architectural invariants remain true (8 agents, 6 skills, etc.)
- File structure is correct
- Keywords and patterns present
- Breaking changes detected (file count, agent removal)

**Limitations**:
- Can't understand MEANING or INTENT
- Only validates structure, not behavior
- Misses subtle drift (agent exists but doesn't do what it should)

**When to run**:
- CI/CD pipeline (fast, automated)
- Pre-commit checks
- Quick sanity checks during development

---

### Recommended Workflow

1. **During Development**: Static tests (fast feedback)
   ```bash
   pytest tests/test_architectural_intent.py -v
   ```

2. **Before Release**: GenAI validation (comprehensive)
   ```bash
   /validate-architecture
   ```

3. **If GenAI Finds Issues**: Fix code or update ARCHITECTURE.md

4. **If Static Tests Fail**: Either:
   - Architecture changed → Update ARCHITECTURE.md
   - Tests too strict → Update tests
   - Regression detected → Fix the code

---

## When to Update This Document

**Update when**:
- Adding/removing agents
- Changing agent order in pipeline
- Modifying model assignments
- Changing workflow modes
- Adding new architectural principles
- Making breaking changes

**Don't update for**:
- Bug fixes
- Documentation improvements
- Minor optimizations
- New features that fit existing architecture
