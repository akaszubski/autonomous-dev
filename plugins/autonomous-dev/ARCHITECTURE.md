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

### Must Not Have
- ✗ Agents with both read and write that shouldn't have both
- ✗ All agents using same model
- ✗ Tests written after code
- ✗ Automatic hook enablement without user consent
- ✗ Global configuration affecting multiple projects
- ✗ Security scan as optional
- ✗ Context communication instead of session files

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

**How to validate**: Run `pytest tests/test_architectural_intent.py -v`

**What it checks**:
- All architectural invariants remain true
- Design principles are enforced in code
- Breaking changes are detected

**If tests fail**: Either:
1. Architecture has changed (update this document)
2. Tests are too strict (update tests)
3. Regression detected (fix the code)

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
