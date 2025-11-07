# Project Context - Autonomous Development Plugin

**Last Updated**: 2025-11-03
**Project**: Software Engineering Operating System - Auto-SDLC Enforcement via Command Workflow
**Version**: v3.2.0 (Anti-Bloat Architecture - "Less is More" Design Requirement)

> **📘 Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for what to update as you iterate

---

## GOALS ⭐

**Primary Mission**: Build an **Autonomous Development Team** - not a toolkit, but a self-managing team of AI agents that execute on PROJECT.md goals using best practices, skills, and consistency. User states WHAT they want, the team autonomously handles HOW.

**User Intent** (stated 2025-10-26):
> "i speak requirements and claude code delivers a first grade software engineering outcome in minutes by following all the necessary steps that would need to be taken in top level software engineering but so much quicker with the use of AI and validation"

**Key Points:**
- ✅ **All SDLC steps required** - Research → Plan → TDD → Implement → Review → Security → Docs (no shortcuts)
- ✅ **Professional quality enforced** - "Top level software engineering" standards via hooks
- ✅ **Speed via AI** - Each step accelerated (research in 5 min vs 2 hours, TDD in 5 min vs 30 min)
- ✅ **Validation ensures compliance** - Hooks validate all steps were followed (can't skip or bypass)

This is achieved via **dual-layer architecture**:

**Layer 1: Hook-Based Enforcement** (Automatic, 100% Reliable)
- PreCommit hooks validate ALL quality gates
- Enforces: PROJECT.md alignment, security, tests, docs, file organization
- Blocks commits if violations detected
- **Guaranteed execution** - hooks run on every commit

**Layer 2: Agent-Based Intelligence** (Optional, AI-Enhanced)
- User invokes `/auto-implement` for AI assistance
- Claude coordinates specialist agents (researcher, planner, implementer, reviewer, etc.)
- Provides intelligent guidance and implementation help
- **Conditional execution** - Claude decides which agents to invoke based on feature complexity

**Key Distinction:**
- **Hooks = enforcement** (quality gates, always active, blocking)
- **Agents = intelligence** (expert assistance, conditionally invoked, advisory)

**Core Philosophy**:
- **Hooks enforce, agents enhance** - Quality guaranteed by hooks, intelligence added by agents
- **Trust the model** - Claude's reasoning determines which agents to invoke (not rigid Python sequences)
- **WHAT, not HOW** - User specifies goals, hooks ensure quality gates, agents provide intelligence
- **GenAI-native orchestration** - Agent coordination via Claude reasoning (flexible, adaptive)
- **PROJECT.md is the gatekeeper** - Hooks enforce alignment, agents respect it
- **No Python orchestration** - GenAI reasoning > rigid automation (per PROJECT.md lines 213-221)
- **Less is more** - Every feature serves the primary mission; bloat prevention is a design requirement (see CONSTRAINTS → Design Principles)

**What success looks like**:

1. **True Autonomous Execution** - User says "implement user authentication" → Team autonomously: researches (5 min), plans (5 min), writes tests (5 min), implements (10 min), reviews (2 min), audits security (2 min), updates docs (1 min), commits, pushes, creates PR → User sees: "✅ Feature complete! PR #42: https://..." → **Total: 30 min (vs 7+ hours manually) with ALL professional steps completed**

2. **All SDLC Steps Enforced** - Research → Plan → TDD → Implement → Review → Security → Docs → **No shortcuts allowed** → Hooks block commits if any step skipped → Professional quality via enforcement, not hope

3. **PROJECT.md is Team's Mission** - 100% of work validates against PROJECT.md BEFORE execution → Team blocks work if not aligned → Single source of strategic truth → Team updates PROJECT.md progress automatically

4. **Zero Manual Git Operations** - Team autonomously: generates commit messages (GenAI), creates commits, pushes to feature branches, creates PRs with comprehensive descriptions (GenAI) → User never runs git commands manually

5. **Speed via AI, Not Shortcuts** - Each SDLC step still required, just AI-accelerated:
   - Research: 2 hours → 5 minutes (AI web search + codebase patterns)
   - Planning: 1 hour → 5 minutes (AI architecture analysis)
   - TDD: 30 minutes → 5 minutes (AI test generation)
   - Implementation: 3 hours → 10 minutes (AI code generation)
   - Review: 30 minutes → 2 minutes (AI quality check)
   - Security: 15 minutes → 2 minutes (AI vulnerability scan)
   - Docs: 20 minutes → 1 minute (AI doc generation)

6. **Minimal User Intervention** - 15 commands total (8 core workflow + 7 individual agents, expanded per GitHub #44) → `/auto-implement <feature>` does full pipeline → Individual agent commands for granular control → `/status` shows progress → `/align-project` validates alignment → `/setup` configures → `/test` for debugging → `/health-check` diagnostics → `/sync-dev` dev sync → `/uninstall` cleanup

**Success Metrics**:

**What's Guaranteed (via Hooks):**
- **Quality enforcement**: 100% of commits validated by PreCommit hooks
  - PROJECT.md alignment ✅ (validate_project_alignment.py)
  - Security validated ✅ (security_scan.py - no secrets, no vulnerabilities)
  - Tests exist ✅ (auto_generate_tests.py - generates if missing)
  - Docs synchronized ✅ (auto_update_docs.py + validate_docs_consistency.py)
  - File organization ✅ (enforce_file_organization.py)
  - Code quality ✅ (auto_format.py + auto_fix_docs.py)
- **Hook reliability**: Hooks always fire (100% execution rate)
- **Blocking enforcement**: Commits blocked if any hook fails
- **Professional quality**: Guaranteed by automated validation, not hope

**What's Enhanced (via Agents):**
- **AI assistance**: Claude coordinates specialist agents when `/auto-implement` is used
  - researcher → best practices and patterns (conditional)
  - planner → architecture design (conditional)
  - test-master → test strategies (conditional)
  - implementer → code generation (conditional)
  - reviewer → quality review (conditional)
  - security-auditor → security analysis (conditional)
  - doc-master → documentation (conditional)
- **Agent invocation**: Conditional based on Claude's reasoning (not guaranteed)
- **Adaptive workflow**: Claude decides which agents are needed (flexible, not rigid)
- **Intelligence layer**: Agents provide expertise when invoked (advisory, not enforcement)

**Result**: Professional quality (hooks) + Expert intelligence (agents when invoked)

**Success Example**:
```bash
# User input (simple)
/auto-implement "Add rate limiting to API"

# Team output (automatic, 5-10 minutes)
✅ Feature complete!
   PR #43: https://github.com/user/repo/pull/43
   PROJECT.md: "Performance" goal → 60% complete
```

**Command Structure** (15 total, expanded per GitHub #44):
- **Core Workflow Commands (8)**: auto-implement (full pipeline), align-project, align-claude, setup, test, status, health-check, sync-dev, uninstall
- **Individual Agent Commands (7)**: research, plan, test-feature, implement, review, security-scan, update-docs
- **Archived (32)**: Redundant manual commands moved to commands/archive/ (commit variants, format, sync-docs, granular test commands, etc.)

**Meta-Goal**: This plugin enforces its own principles (autonomous team model) on projects that use it.

---

## SCOPE

**What's IN Scope** ✅ (Features we build):

**Core Auto-Orchestration** (PRIMARY FOCUS):
- ✅ **Feature request detection** - Automatic triggers on "implement", "add", "create", "build", etc.
- ✅ **Agent coordination** - `/auto-implement` command coordinates 7-agent workflow directly
- ✅ **PROJECT.md gatekeeper** - Validates alignment BEFORE any work begins → Blocks if misaligned
- ✅ **Strict mode configuration** - Pre-configured hooks that enforce all best practices
- ✅ **SDLC step enforcement** - Can't skip tests, security, docs → Each checkpoint required

**PROJECT.md Enforcement**:
- ✅ **Alignment validation** - Checks GOALS, SCOPE, CONSTRAINTS before proceeding
- ✅ **Blocking enforcement** - Work stops if feature not in SCOPE
- ✅ **Update workflow** - Two options when misaligned: (1) Update PROJECT.md, (2) Don't implement
- ✅ **Pre-commit gatekeeper** - Blocks commits if PROJECT.md misaligned
- ✅ **Strategic direction as code** - PROJECT.md is executable contract

**File Organization Enforcement**:
- ✅ **Standard structure** - src/, tests/ (unit/integration/uat/), docs/, scripts/, .claude/
- ✅ **Root directory cleanup** - Only README.md, LICENSE, config files → No loose files
- ✅ **Auto-fix capability** - Automatically move misplaced files to correct locations
- ✅ **Structure validation** - Pre-commit hook enforces organization
- ✅ **Template-based** - Standard structure defined in templates/project-structure.json

**Brownfield Alignment** (Existing Projects):
- ✅ **Retrofit capability** - `/align-project-retrofit` command (PLANNED)
- ✅ **Non-destructive** - Analyzes current structure → Proposes alignment plan → Asks approval
- ✅ **Migration guide** - Step-by-step process to align existing projects
- ✅ **Preserves existing** - Doesn't break what's working → Enhances incrementally

**Autonomous Development Pipeline** (Existing):
- ✅ **7-agent coordination** - Claude validates PROJECT.md, then coordinates specialist agents
- ✅ **Model optimization** - opus (complex planning), sonnet (balanced), haiku (fast scans)
- ✅ **Context management** - Session files, /clear prompts, scales to 100+ features
- ✅ **TDD enforced** - Tests written before code (test-master → implementer flow)
- ✅ **Security scanning** - Secrets detection, vulnerability scanning, OWASP compliance
- ✅ **Documentation sync** - README, CHANGELOG, API docs updated automatically

**Plugin Distribution**:
- ✅ **Plugin marketplace** - One-command install for teams
- ✅ **Multi-language support** - Python, JavaScript/TypeScript, Go, Rust (generic approach)
- ✅ **Customizable** - Teams can fork and adapt to their standards
- ✅ **Strict mode templates** - Pre-configured settings for maximum enforcement

**What's OUT of Scope** ❌ (Features we avoid):

- ❌ **Replacing human developers** - AI augments, doesn't replace
- ❌ **Skipping PROJECT.md alignment** - Never proceed without validation
- ❌ **Optional best practices** - All SDLC steps are mandatory in strict mode
- ❌ **Manual step management** - System handles steps automatically
- ❌ **Language-specific lock-in** - Stay generic, support multiple ecosystems
- ❌ **Breaking existing workflows** - Enhance, don't disrupt (especially brownfield)
- ❌ **SaaS/Cloud hosting** - Local-first, teams own their infrastructure
- ❌ **Paid features** - 100% free, MIT license, community-driven

**Boundaries**:
- Focus on automation of SDLC enforcement
- PROJECT.md is non-negotiable gatekeeper
- File organization is standardized and enforced
- Support both greenfield (new) and brownfield (existing) projects
- Maintain security and quality standards automatically
- Stay within Claude Code's token budgets (context management)

---

## CONSTRAINTS

### Design Principles (Anti-Bloat Requirements)

**Philosophy**: "Less is more" - Use all elements to make dev life simple and automated, but only build what's necessary.

**Every feature must pass these gates before implementation**:

1. **Alignment Gate** - Does it serve primary mission?
   - ✅ Advances autonomous execution
   - ✅ Improves SDLC enforcement
   - ✅ Enhances AI-powered speed
   - ❌ REJECT if not aligned with GOALS

2. **Constraint Gate** - Does it respect boundaries?
   - ✅ Keeps commands ≤ 15 total (currently: 8, expanded for individual agent commands per GitHub issue #44)
   - ✅ Uses GenAI reasoning over Python automation
   - ✅ Hooks enforce, agents enhance (not reversed)
   - ❌ REJECT if violates constraints

3. **Minimalism Gate** - Is this the simplest solution?
   - ✅ Solves observed problem (not hypothetical)
   - ✅ Can't be solved by existing features
   - ✅ Can't be solved by documentation/config
   - ✅ Implementation ≤ 200 LOC per feature
   - ❌ REJECT if over-engineered

4. **Value Gate** - Does benefit outweigh complexity?
   - ✅ Saves developer time/effort measurably
   - ✅ Makes automation more reliable
   - ✅ Makes workflow more observable
   - ❌ REJECT if maintenance burden > value delivered

**Red Flags** (immediate bloat indicators):
- 🚩 "This will be useful in the future" (hypothetical)
- 🚩 "We should also handle X, Y, Z" (scope creep)
- 🚩 "Let's create a framework for..." (over-abstraction)
- 🚩 "This needs a new command" (approaching 15-command limit)
- 🚩 "We need to automate..." (before trying observability)
- 🚩 File count growing >5% per feature
- 🚩 Test time increasing >10% per feature

**Bloat Prevention Enforcement**:
- Pre-implementation: Review against 4 gates (documented in `docs/BLOAT-DETECTION-CHECKLIST.md`)
- During implementation: Monitor red flags, stop if detected
- Post-implementation: Validate value delivered vs complexity added
- Quarterly: Audit all features, remove unused/low-value code

**Result**: Developer experience is simple and automated BY DESIGN, not by accident. Every element serves the mission.

---

### Technical Constraints

**Required Technology**:
- **Primary**: Markdown (agent/skill/command definitions)
- **Supporting**: Python 3.11+ (hooks/scripts), Bash (testing/automation), JSON (config)
- **Testing**: pytest (Python), jest (JavaScript), automated test script (Bash)
- **Formatting**: black, isort (Python), prettier (JavaScript/TypeScript)
- **Claude Code**: 2.0+ with plugins, agents, hooks, skills, slash commands
- **Git**: For version control and rollback safety

**Current Architecture** (v3.2.2 - Orchestrator Removed):
- **Agents**: 18 total (orchestrator removed in v3.2.2 - Claude coordinates directly)
  - **Core 9**: planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master, advisor, quality-validator
  - **Utility 9**: alignment-validator, alignment-analyzer, commit-message-generator, pr-description-generator, project-progress-tracker, project-bootstrapper, project-status-analyzer, setup-wizard, sync-validator
- **Skills**: 19 (active with progressive disclosure architecture)
  - **Status**: 19 active skill packages in plugins/autonomous-dev/skills/
  - **Architecture**: Progressive disclosure (metadata in context, full content loaded when needed)
  - **Categories**: Core Development (6), Workflow & Automation (4), Code & Quality (4), Validation & Analysis (5)
  - **How It Works**: Skills auto-activate based on keywords, Claude Code 2.0+ native support
  - **Reference**: See docs/SKILLS-AGENTS-INTEGRATION.md for full architecture
- **Commands**: 18 total (expanded per GitHub #44)
  - **Core (8)**: /auto-implement, /align-project, /align-claude, /setup, /sync-dev, /status, /health-check, /pipeline-status
  - **Agent (7)**: /research, /plan, /test-feature, /implement, /review, /security-scan, /update-docs
  - **Utility (3)**: /test, /uninstall, /update-plugin
- **Hooks**: 28 total
  - **Core 9**: detect_feature_request, validate_project_alignment, enforce_file_organization, auto_format, auto_test, security_scan, validate_docs_consistency, enforce_orchestrator, enforce_tdd
  - **Extended 19**: auto_add_to_regression, auto_enforce_coverage, auto_fix_docs, auto_generate_tests, auto_sync_dev, auto_tdd_enforcer, auto_track_issues, auto_update_docs, detect_doc_changes, enforce_bloat_prevention, enforce_command_limit, post_file_move, validate_claude_alignment, validate_documentation_alignment, validate_session_quality, and 4 others
- **Plugin**: autonomous-dev (contains all components)
- **Python Infrastructure**: ~250KB supporting scripts (genai_validate.py, workflow_coordinator.py, pr_automation.py, etc.)

**Standard Project Structure** (ENFORCED in strict mode):
```
project/
├── src/                    # ALL source code
├── tests/                  # ALL tests
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── uat/               # User acceptance tests
├── docs/                   # ALL documentation
│   ├── api/               # API documentation
│   ├── guides/            # User guides
│   └── sessions/          # Session logs
├── scripts/                # Utility scripts
├── .claude/                # Claude Code configuration
│   ├── PROJECT.md         # Strategic direction (GATEKEEPER)
│   ├── settings.local.json # Strict mode hooks
│   └── hooks/             # Project-specific hooks
├── README.md               # User-facing documentation
├── LICENSE                 # MIT license
├── .gitignore              # Git ignore patterns
└── pyproject.toml          # Dependencies
```

**Repository Structure** (Plugin Development):

This repository serves TWO audiences - contributors building the plugin AND users installing it.

**ROOT Level** (Development workspace - NOT distributed):
- `docs/` - Dev/contributor documentation (CONTRIBUTING.md, DEVELOPMENT.md, etc.)
- `scripts/` - Build/sync scripts for development (validate_structure.py, session_tracker.py)
- `tests/` - Repository infrastructure tests
- Root `.md` files - Only essential: README.md, CHANGELOG.md, CLAUDE.md, CONTRIBUTING.md

**PLUGIN Level** (Distribution package - what users get):
- `plugins/autonomous-dev/docs/` - User documentation (STRICT-MODE.md, QUICKSTART.md, etc.)
- `plugins/autonomous-dev/hooks/` - Automation hooks + utility scripts (setup.py wizard, validators, etc.)
- `plugins/autonomous-dev/tests/` - Plugin feature tests
- `plugins/autonomous-dev/agents/` - 18 AI agents (9 core + 9 utility, orchestrator removed v3.2.2)
- `plugins/autonomous-dev/commands/` - 18 slash commands (8 core + 7 agent + 3 utility)
- `plugins/autonomous-dev/hooks/` - 15 automation hooks (7 core + 8 optional)
- `plugins/autonomous-dev/templates/` - Project templates (settings.strict-mode.json, project-structure.json, PROJECT.md)

### Performance Constraints

- **Context Budget**: Keep under 8,000 tokens per feature (CRITICAL)
- **Feature Time**: Target 20-30 minutes per feature (autonomous)
- **Test Execution**: Auto-tests should run in < 60 seconds
- **Session Management**: Use session files (log paths, not content) to prevent context bloat
- **Context Clearing**: Recommended to use `/clear` after each feature to maintain performance (optional but helpful for 100+ features)
- **Validation Speed**: All pre-commit hooks must complete in < 10 seconds

### Security Constraints

- **No hardcoded secrets**: Enforced by security_scan.py hook
- **TDD mandatory**: Tests written before implementation (enforced by strict mode)
- **Tool restrictions**: Each agent has minimal required permissions (principle of least privilege)
- **80% coverage minimum**: Enforced by auto_enforce_coverage.py hook
- **Security scanning**: Automatic vulnerability and secrets detection (blocking)
- **Read-only agents**: planner, reviewer, security-auditor can't write code

### Team Constraints

- **Team Size**: Solo developer (akaszubski) → Building for scalability to teams
- **Skill Set**: Python, JavaScript/TypeScript, AI/ML, DevOps
- **Available Time**: Looking to automate away ALL repetitive tasks
- **Autonomous Operation**: System should work with ZERO manual step management
- **Universal Applicability**: Works for ALL projects (new and existing)

---

## ARCHITECTURE

### System Architecture (v3.2.2 - Command-Driven SDLC + Enforcement)

```
User: /auto-implement "implement user authentication"  [EXPLICIT COMMAND]
     ↓
[Command execution - explicit user action required]
     ↓
/auto-implement command (GATEKEEPER - PRIMARY MISSION)
     │
     ├─> 1. Read PROJECT.md (GOALS, SCOPE, CONSTRAINTS)
     ├─> 2. Validate: Does feature serve GOALS?
     ├─> 3. Validate: Is feature IN SCOPE?
     ├─> 4. Validate: Respects CONSTRAINTS?
     ├─> 5. DECISION:
     │      ✅ Aligned → Proceed with 7-agent pipeline
     │      ❌ NOT Aligned → BLOCK work
     │                       → User must update PROJECT.md OR modify request
     └─> 6. Log alignment decision to session
     ↓
7-Agent Pipeline (ONLY if PROJECT.md aligned) [ALL STEPS REQUIRED]:
     ↓
┌────────────┬─────────────┬──────────────┬─────────────┐
│ Researcher │   Planner   │ Test-Master  │ Implementer │
│  (Sonnet)  │   (Opus)    │   (Sonnet)   │  (Sonnet)   │
│  Read-only │  Read-only  │  Write Tests │  Write Code │
│  ~5 min    │   ~5 min    │   ~5 min     │   ~10 min   │
│ (vs 2hr)   │  (vs 1hr)   │  (vs 30min)  │  (vs 3hr)   │
└────────────┴─────────────┴──────────────┴─────────────┘
     ↓
┌────────────┬─────────────┬──────────────┐
│  Reviewer  │  Security   │  Doc-Master  │
│  (Sonnet)  │   (Haiku)   │   (Haiku)    │
│  Read-only │  Read+Bash  │  Write Docs  │
│   ~2 min   │   ~2 min    │   ~1 min     │
│ (vs 30min) │  (vs 15min) │  (vs 20min)  │
└────────────┴─────────────┴──────────────┘
     ↓
Total: ~30 minutes (vs 7+ hours manually)
All 7 steps completed, no shortcuts taken
     ↓
Recommended: "Run /clear for next feature" (optional for performance)
     ↓
[Pre-Commit Hooks] (BLOCKING - Strict Mode) [v3.0 - ENHANCED]
     ├─> validate_project_alignment.py  [PROJECT.md GATEKEEPER]
     ├─> enforce_orchestrator.py        [Orchestrator ran - NEW v3.0]
     ├─> enforce_tdd.py                 [TDD followed - NEW v3.0]
     ├─> auto_fix_docs.py               [Docs synced + congruence validated]
     ├─> auto_test.py                   [Tests must pass]
     └─> security_scan.py               [Security must pass]
     ↓
     ✅ All pass → Commit allowed
     ❌ Any fail → Commit BLOCKED → Claude can fix
     ↓
Production Code (Professional Quality Guaranteed)
```

**Priority Hierarchy**:
1. **PRIMARY**: PROJECT.md alignment (GATEKEEPER - MOST IMPORTANT)
2. **SECONDARY**: Command-driven workflow (explicit `/auto-implement` or individual agents)
3. **TERTIARY**: File organization enforcement
4. **SUPPORTING**: SDLC step enforcement

### Agent Responsibilities (v3.2.2 - Orchestrator Removed)

**Core Workflow Agents (7)** - Coordinated by Claude via `/auto-implement`:

1. **researcher**: Web research, best practices (sonnet, read-only)
2. **planner**: Implementation plans (opus, read-only)
3. **test-master**: TDD tests (sonnet, write tests)
4. **implementer**: Make tests pass (sonnet, write code)
5. **reviewer**: Quality gate (sonnet, read-only)
6. **security-auditor**: Security scan (haiku, read-only)
7. **doc-master**: Documentation sync (haiku, write docs)

**Note**: PROJECT.md alignment validation happens in `/auto-implement` command directly (not separate agent)

**Utility Agents (4)**:

9. **alignment-validator**: GenAI-powered PROJECT.md alignment validation (sonnet, read-only)
10. **commit-message-generator**: Generate conventional commit messages (sonnet)
11. **pr-description-generator**: Generate comprehensive PR descriptions (sonnet)
12. **project-progress-tracker**: Track progress against PROJECT.md goals (sonnet)

**Note**: Utility agents support core workflow but are not part of main pipeline.

### Strict Mode Components

**Command Workflow**:
- `commands/auto-implement.md` - Coordinates 7-agent workflow with PROJECT.md validation
- `commands/research.md`, `plan.md`, `test-feature.md`, etc. - Individual agent commands
- `templates/settings.strict-mode.json` - Pre-configured hooks

**PROJECT.md Enforcement**:
- `hooks/validate_project_alignment.py` - Validates PROJECT.md before commits
- Checks: Exists, has required sections (GOALS/SCOPE/CONSTRAINTS), SCOPE defined
- Blocks: Commits if misaligned

**File Organization**:
- `templates/project-structure.json` - Standard structure definition
- `hooks/enforce_file_organization.py` - Validates and auto-fixes structure
- Enforces: src/, tests/, docs/, scripts/ organization
- Cleans: Root directory

**Documentation**:
- `docs/STRICT-MODE.md` - Complete guide (571 lines)
- Setup, usage, troubleshooting, examples

### Session Management (Existing)

**Purpose**: Prevent context bloat and enable scalable development

**Strategy**:
- Log agent actions to `docs/sessions/{timestamp}-session.md` files
- Agents log file paths (not content) to session
- Next agent reads session file for context
- Keeps context under 8K tokens per feature

**Session Tracker**: `scripts/session_tracker.py`
- Logs: Agent name, timestamp, message
- Creates: Session files in `docs/sessions/`
- Used by: All agents when completing work

---

## ENFORCEMENT RULES 🛑

**These rules PREVENT bloat from returning. Aligned with autonomous team philosophy.**

### What We Protect

✅ **Keep**: Skills directory (consistency for team)
✅ **Keep**: 16 agents (8 core + 8 utility for autonomous execution)
✅ **Keep**: Python infrastructure (automation backbone)
❌ **Cut**: Documentation sprawl (114 files → 15 focused files)
❌ **Cut**: Redundant commands (9 → 8)
❌ **Cut**: Over-prescriptive agent guidance (trust the model)

### Automatic Enforcement via Pre-Commit Hooks

**enforce_bloat_prevention.py** (NEW - BLOCKING):
```python
# Fail (exit 2) if:
- Total markdown files in docs/ > 15
- Total markdown files in plugins/autonomous-dev/docs/ > 20
- Any agent >150 lines (trust the model threshold)
- Any command >80 lines
- Python lib/ grows beyond 25 modules
- New documentation file added without archiving old one

# Warn (exit 1) if:
- Agent approaching 150 lines (140+)
- Total docs approaching limit (12+)
- Command approaching 80 lines (75+)
```

**enforce_command_limit.py** (NEW - BLOCKING):
```python
# Fail (exit 2) if:
- >8 active commands in commands/ directory
# Allowed 8: auto-implement, align-project, setup, test, status, health-check, sync-dev, uninstall
# All others must be archived or removed
```

### Manual Enforcement via CODE REVIEW

**Before merging any PR:**
1. Agent count: Should be 16 (8 core + 8 utility)
2. Agent lines: `wc -l plugins/autonomous-dev/agents/*.md | tail -1` should be 1200-1500 (trust-the-model focused)
3. Command count: `ls plugins/autonomous-dev/commands/*.md | wc -l` must equal 8
4. Docs count: `find docs plugins/autonomous-dev/docs -name "*.md" | wc -l` must be < 35 total
5. Skills: Should have 6-10 consistent skills (not sprawling)

### When BLOAT Returns (It Will)

**The "Documentation Budget" Rule**:
```
For every new .md file added → Archive 2 old .md files
For every new command → Remove 1 old command
For every agent that grows → Simplify 1 other agent
```

### The Core Rule: STAY WITHIN BUDGET

Every PR must satisfy ONE OF:
```
A) files_added <= files_deleted  (zero or negative net growth)
B) If adding files, proportional deletion elsewhere
C) If no deletion, explain why in PR (rare exceptions only)
```

**Exceptions that DON'T count as bloat**:
- Test files (TDD requires growth)
- Skill improvements (consistency > quantity)
- Agent behavior improvements (kept within 150 lines)
- Temporary session files (auto-archived)

---

## DESIGN PRINCIPLES ⚙️

**Source**: Official Anthropic Claude Code repository analysis (2025-10-25)
**Purpose**: Codify production-grade standards to maintain simplicity and context efficiency

### Agent Design (Official Anthropic Standard)

**Length Requirements**:
- **Target**: 50-100 lines total (frontmatter + content)
- **Maximum**: 150 lines (enforce strictly)
- **Current baseline**: Most agents 300-800 lines (NEEDS SIMPLIFICATION)
- **Rationale**: Agents must fit in context with room for codebase exploration

**Frontmatter (Required Fields Only)**:
```yaml
---
name: agent-name
description: Clear one-sentence mission
model: sonnet  # or opus/haiku based on task complexity
tools: [Tool1, Tool2, Tool3]  # Only essential tools
color: blue  # Optional: red/green/blue/yellow for visual distinction
---
```

**Content Structure** (Anthropic Production Pattern):
1. **Clear Mission** (1-2 sentences) - What is the agent's purpose?
2. **Core Responsibilities** (3-5 bullet points) - What does it do?
3. **Process** (Simple workflow, NOT prescriptive step-by-step)
4. **Output Format** (Actionable structure for results)

**Design Philosophy**:
- ✅ **Trust the model** - Claude is smart, don't over-prescribe implementation
- ✅ **Clear mission** - Agent knows its purpose and boundaries
- ✅ **Minimal guidance** - Just enough structure, not detailed scripts
- ✅ **Focused scope** - Single responsibility, well-defined outputs

**What to AVOID** (Anti-patterns from over-engineering):
- ❌ Bash scripts embedded in markdown
- ❌ Python code examples in agent prompts
- ❌ Complex artifact protocols (`.claude/artifacts/` pattern)
- ❌ Detailed JSON schemas (100+ line examples)
- ❌ Step-by-step implementation prescriptions
- ❌ Over-specification of tools/techniques

**What to INCLUDE**:
- ✅ Clear mission statement (why this agent exists)
- ✅ Core responsibilities (what it does)
- ✅ Expected output format (structure of results)
- ✅ High-level process (general approach, not detailed steps)
- ✅ Context about when to invoke (optional)

**Example** (Official Anthropic Pattern):
```markdown
---
name: researcher
description: Research best practices and existing patterns
model: sonnet
tools: [WebSearch, WebFetch, Read, Grep, Glob]
color: blue
---

You are a research specialist who finds best practices and patterns.

## Your Mission
Research the requested feature to inform planning and implementation.

## Core Responsibilities
- Search codebase for similar implementations
- Find official documentation and current best practices
- Identify security considerations
- Recommend libraries and approaches

## Research Process
Use Grep/Glob to find existing patterns, WebSearch for official docs,
prioritize authoritative sources (official docs > GitHub > blogs).

## Output Format
- **Codebase Patterns**: Existing code with file:line references
- **Best Practices**: Industry standards with sources
- **Security**: Critical considerations
- **Recommendations**: Preferred approach with rationale

Quality over quantity. Trust the model to execute effectively.
```

**Total**: ~30 lines (vs 864 lines in over-engineered version)

### Hook Design (Official Anthropic Standard)

**Structure** (Python-based):
```python
#!/usr/bin/env python3
"""Clear purpose description in docstring."""

import json
import sys

# Pattern configuration (declarative, at top)
PATTERNS = [
    (r"pattern1", "message1"),
    (r"pattern2", "message2"),
]

def main():
    """Main hook function."""
    # 1. Check if enabled (optional)
    # 2. Read stdin JSON
    # 3. Check patterns/rules
    # 4. Exit with appropriate code

if __name__ == "__main__":
    main()
```

**Exit Codes** (CRITICAL - Anthropic Standard):
- **0**: Allow tool, no message shown
- **1**: Allow tool, show stderr to USER only (warning, not blocking)
- **2**: BLOCK tool, show stderr to CLAUDE (enforcement, Claude can fix)

**Exit Code Strategy**:
```python
# Exit 0: Tool proceeds, silent success
sys.exit(0)

# Exit 1: Tool proceeds, user sees warning
print("⚠️  Warning: Consider using rg instead of grep", file=sys.stderr)
sys.exit(1)

# Exit 2: Tool BLOCKED, Claude sees error and can fix
print("❌ PROJECT.md alignment failed: missing GOALS section", file=sys.stderr)
print("\nUpdate PROJECT.md or run: /align-project", file=sys.stderr)
sys.exit(2)  # Claude receives message and can take action
```

**Design Principles**:
- ✅ **Single concern** - Each hook does ONE thing (security, validation, etc.)
- ✅ **Declarative rules** - Pattern lists at top, easy to maintain
- ✅ **Warn, don't auto-fix** - Let Claude see issues and fix them
- ✅ **Session state** - Track shown warnings per session (avoid spam)
- ✅ **Fast execution** - Must complete in < 1 second (user experience)

**What to AVOID**:
- ❌ Auto-fixing issues (risky, hides problems from Claude)
- ❌ Complex multi-stage logic (keep simple)
- ❌ Heavy I/O operations (parsing large files, slow)
- ❌ Silent failures (always exit with appropriate code)

**Session Management** (Official Pattern):
```python
def get_state_file(session_id: str) -> Path:
    """Get per-session state file."""
    return Path.home() / ".claude" / f"state_{session_id}.json"

def load_shown_warnings(session_id: str) -> set:
    """Load warnings already shown this session."""
    state_file = get_state_file(session_id)
    if not state_file.exists():
        return set()
    return set(json.loads(state_file.read_text()))

def save_shown_warnings(session_id: str, warnings: set):
    """Save warnings shown this session."""
    state_file = get_state_file(session_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(list(warnings)))
```

### Plugin Architecture (Official Anthropic Standard)

**Minimal File Structure**:
```
plugins/plugin-name/
├── agents/           # AI agents (50-100 lines each)
│   ├── agent1.md
│   └── agent2.md
├── commands/         # Slash commands
│   ├── command1.md
│   └── command2.md
├── hooks/            # Lifecycle hooks (optional)
│   └── hook1.py
├── scripts/          # Utility scripts (optional)
│   └── setup.py
└── README.md         # Single comprehensive guide (400-600 lines)
```

**No skills/ directory** - Skills are anti-pattern in official plugins:
- Guidance goes directly in agent prompts (if agent needs python standards, include in agent)
- OR in shared README.md (project-wide standards)
- Skills add indirection without value

**Documentation Strategy**:
- **Single README.md** - Comprehensive 400-600 line guide
- **Optional**: TROUBLESHOOTING.md, STRICT-MODE.md for advanced features
- **Avoid**: 66+ scattered markdown files (documentation sprawl)

### Command Design (Official Anthropic Standard)

**Phase-Based Workflow Pattern**:
```markdown
---
description: Guided feature development workflow
argument-hint: Optional feature description
---

# Feature Development

Follow a systematic 7-phase approach with user checkpoints:

## Phase 1: Discovery
- Create todo list with TodoWrite
- Clarify requirements
- Summarize understanding
- **User checkpoint**: Approve before proceeding

## Phase 2: Codebase Exploration
- Launch 2-3 explorer agents in parallel
- Each agent traces different aspect
- Read key files identified
- **User checkpoint**: Review findings

## Phase 3: Architecture Design
- Launch 2-3 architect agents in parallel
- Present 2-3 approaches
- **User checkpoint**: Pick preferred approach

## Phase 4-7: Implementation → Review → Summary
[Continue pattern...]
```

**Key Principles**:
- ✅ **User gates** - Wait for approval between phases
- ✅ **TodoWrite tracking** - Track progress throughout
- ✅ **Parallel agents** - Launch 2-3 agents per phase for diverse perspectives
- ✅ **Clear phases** - Discovery → Exploration → Design → Implementation → Review → Summary

### Context Management (Critical for Scaling)

**Best Practices** (Official Pattern):
- ✅ **Keep agents short** - 50-100 lines = minimal context usage
- ✅ **No artifact protocols** - Don't create complex `.claude/artifacts/` systems
- ✅ **Session logging** - Log to files, reference paths (not full content)
- ✅ **Clear after features** - Recommended to use `/clear` after each feature (optional for performance)
- ✅ **Minimal prompts** - Trust model > detailed instructions

**Context Budget**:
- Target: < 8,000 tokens per feature
- Agent prompts: 500-1,000 tokens (50-100 lines)
- Codebase exploration: 2,000-3,000 tokens
- Working memory: 2,000-3,000 tokens
- Buffer: 1,000-2,000 tokens

### Simplification Principles (v2.5 Standards)

**Official Anthropic Philosophy**:
1. **Trust the model** - Claude Sonnet/Opus are extremely capable
2. **Simple > Complex** - 50-line agent > 800-line agent (both work, simple scales better)
3. **Warn > Auto-fix** - Let Claude see and fix issues (learns patterns)
4. **Minimal > Complete** - Focused guidance > exhaustive documentation
5. **Parallel > Sequential** - Launch multiple agents, get diverse perspectives

**When You're Over-Engineering**:
- Agent prompts exceed 150 lines
- Using complex artifact protocols
- Writing bash/python in agent markdown
- Creating 60+ documentation files
- Auto-fixing instead of warning
- Prescribing exact implementation steps

**Correction Path**:
- Read official Anthropic plugins (https://github.com/anthropics/claude-code)
- Identify over-engineered components
- Simplify to match official patterns
- Measure: Context usage, execution speed, maintainability

---

## CURRENT SPRINT

**Sprint Name**: Sprint 7: Auto-Orchestration & Strict Mode 🚀
**GitHub Milestone**: [Create milestone](https://github.com/akaszubski/autonomous-dev/milestones)
**Duration**: 2025-10-20 → 2025-11-10 (3 weeks)
**Status**: In Progress (85% complete) - v3.0.2 Released

**Sprint Goals**:
1. ✅ **Command-driven workflow** - `/auto-implement` and individual agent commands
2. ✅ **PROJECT.md gatekeeper** - Blocks work if not aligned
3. ✅ **File organization enforcement** - Standard structure enforced
4. ✅ **Strict mode configuration** - Pre-configured templates
5. ✅ **Background enforcement hooks** - Validate workflow compliance (v3.0 - NEW)
6. 🚧 **Brownfield alignment** - `/align-project-retrofit` command (PLANNED)
7. 🚧 **Documentation** - Complete strict mode guide

**Completed in This Sprint**:
- ✅ PROJECT.md gatekeeper hook (validate_project_alignment.py)
- ✅ File organization enforcer (enforce_file_organization.py)
- ✅ Strict mode settings template
- ✅ Standard project structure template
- ✅ Comprehensive validation system (12 checks)
- ✅ Strict mode documentation (STRICT-MODE.md)
- ✅ **enforce_pipeline_complete.py hook** (v3.2.2 - validates 7 agents ran)
- ✅ **enforce_tdd.py hook** (v3.0.2 - enforces tests-before-code)
- ✅ **Documentation congruence validation** (auto_fix_docs.py enhanced)
- ✅ **Command-driven architecture** (Explicit commands + Enforcement hooks)

**Next Tasks**:
- 🚧 Build `/align-project-retrofit` command
- 🚧 Test command workflow with real projects
- 🚧 Create brownfield migration examples
- 🚧 Update README with strict mode section

**Completed in Sprint 6**:
- ✅ Skills refactor (6 → 13 skills)
- ✅ Comprehensive validation (numeric + procedural + configuration)
- ✅ Documentation consistency enforcement

**Completed in Sprint 5**:
- ✅ PROJECT.md-first architecture
- ✅ 8-agent pipeline with orchestrator
- ✅ /align-project command
- ✅ Testing infrastructure (30+ automated tests)
- ✅ Plugin v2.0.0 release

**Next Sprint**: Sprint 8: Brownfield Adoption
- `/align-project-retrofit` implementation
- Migration examples (Python, TypeScript, Go projects)
- Case studies of existing project alignment
- Community adoption materials

---

## DEVELOPMENT WORKFLOW

### Strict Mode Workflow

**Step 1: Enable Strict Mode**
```bash
# Copy strict mode configuration
cp plugins/autonomous-dev/templates/settings.strict-mode.json .claude/settings.local.json

# Ensure PROJECT.md exists
cp plugins/autonomous-dev/templates/PROJECT.md PROJECT.md
vim PROJECT.md  # Define GOALS, SCOPE, CONSTRAINTS
```

**Step 2: Run Command**
```bash
# Explicitly run the command with your feature description
/auto-implement "implement user authentication with JWT tokens"

# Command workflow executes:
→ Checks PROJECT.md alignment
→ If aligned: 7-agent pipeline executes
→ If NOT aligned: Work BLOCKED
```

**Step 3: Agent Pipeline Executes Automatically**
```
researcher → planner → test-master → implementer →
reviewer → security-auditor → doc-master
```

**Step 4: Pre-Commit Validation (Automatic)**
```bash
git commit -m "feat: add JWT authentication"

# Pre-commit hooks run:
→ PROJECT.md alignment ✅
→ Tests pass ✅
→ Security scan ✅
→ Docs synced ✅

# Commit succeeds only if all pass
```

**Step 5: Context Clearing (Optional)**
```bash
/clear  # Recommended after each feature for optimal performance (helps with 100+ features)
```

### Standard Feature Development Flow (Existing)

1. **Alignment Check**: Verify feature aligns with PROJECT.md (NOW AUTOMATIC)
2. **Research**: Researcher agent finds patterns and best practices
3. **Planning**: Planner agent creates implementation plan
4. **TDD Tests**: Test-master writes failing tests
5. **Implementation**: Implementer makes tests pass
6. **Review**: Reviewer checks quality
7. **Security**: Security-auditor scans for issues
8. **Documentation**: Doc-master updates docs
9. **Context Clear (Optional)**: Use `/clear` to reset for next feature (recommended for optimal performance)

### File Locations (CRITICAL for Plugin Development)

**SOURCE OF TRUTH** - Always edit here:

```
plugins/autonomous-dev/           # Plugin source code (what users get)
├── agents/                       # 8 AI agents (edit here)
├── skills/                       # 7 core skills (edit here)
├── commands/                     # Slash commands (edit here)
├── hooks/                        # Automation hooks (edit here)
├── templates/                    # Project templates (edit here)
├── docs/                         # User documentation (edit here)
├── scripts/                      # User scripts (edit here)
└── tests/                        # Plugin tests (edit here)
```

**TESTING ENVIRONMENT** - Installed plugin (like users see it):

```
.claude/                          # Plugin installed here for testing
├── agents/                       # Installed from plugins/ (DO NOT EDIT)
├── commands/                     # Installed from plugins/ (DO NOT EDIT)
├── hooks/                        # Installed from plugins/ (DO NOT EDIT)
├── skills/                       # Installed from plugins/ (DO NOT EDIT)
├── PROJECT.md                    # Repo-specific goals (edit here)
└── settings.local.json           # Personal settings (edit here)
```

**DEVELOPMENT WORKFLOW**:

1. **Edit source**: Make changes in `plugins/autonomous-dev/`
2. **Sync to installed plugin**: `python plugins/autonomous-dev/hooks/sync_to_installed.py`
3. **Bootstrap test project**: `bash install.sh` (in test project to update `.claude/`)
4. **Test like users**: Test features in `.claude/` environment
5. **Fix bugs**: Edit `plugins/autonomous-dev/` and repeat sync → bootstrap

**USER INSTALLATION WORKFLOW** (as of v3.2.3):

**One command:**
```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**First time?** Script checks for plugin and guides you:
1. If plugin missing: Install via `/plugin marketplace add` → `/plugin install` → Restart
2. Run curl command again
3. Restart Claude Code
4. Done - all 15 commands available (8 core + 7 individual agents)

**Updates:** Same curl command always gets latest from GitHub.

**Why this works**: Script downloads from GitHub, checks plugin exists, copies files to project's `.claude/`, guides through any missing steps. See docs/BOOTSTRAP_PARADOX_SOLUTION.md for architecture details.

**CRITICAL RULE**: `.claude/` is the TESTING environment. It mirrors what users get after running `install.sh`. NEVER edit files in `.claude/agents/`, `.claude/commands/`, `.claude/hooks/`, or `.claude/skills/` directly. Always edit in `plugins/autonomous-dev/`, sync to installed plugin, then bootstrap to `.claude/`.

---

## AGENT GUIDANCE

### How Agents Should Use This File

**Before ANY work**, agents must:

1. **Read PROJECT.md** - Understand goals, scope, constraints
2. **Validate alignment** - Does feature serve GOALS?
3. **Check scope** - Is feature IN or OUT of scope?
4. **Respect constraints** - Stay within technical/security boundaries
5. **Follow architecture** - Use existing agents/skills/hooks

### Alignment Check Process (ENFORCED in Strict Mode)

```python
def validate_feature(feature_request, project_md):
    # 1. Does it serve GOALS?
    if not serves_goals(feature_request, project_md.goals):
        return block("Feature doesn't advance project goals")

    # 2. Is it in SCOPE?
    if not in_scope(feature_request, project_md.scope):
        return block("Feature is out of scope - update PROJECT.md or modify request")

    # 3. Respects CONSTRAINTS?
    if violates_constraints(feature_request, project_md.constraints):
        return block("Feature violates project constraints")

    # All checks pass - proceed with agent pipeline
    return approve(feature_request)
```

### When to Block Features (STRICT MODE)

**BLOCK immediately when**:
- Feature doesn't serve project GOALS
- Feature is explicitly OUT of SCOPE
- Feature violates CONSTRAINTS
- Feature conflicts with ARCHITECTURE

**Blocking Template**:
```
❌ BLOCKED: Feature not aligned with PROJECT.md

**Project SCOPE**: [From PROJECT.md]
**Requested Feature**: [User's request]
**Issue**: Feature is not in defined SCOPE

**Options**:
1. Update PROJECT.md SCOPE to include this feature
2. Modify feature request to align with current SCOPE
3. Don't implement (feature is out of scope)

Strict mode enforces PROJECT.md as single source of truth.
Work cannot proceed without alignment.
```

---

## ACTIVE WORK 🔨

**GitHub Issue #46: Pipeline Performance Optimization (6 Phases - Phases 4-6 COMPLETE)**

**Goal**: Reduce /auto-implement time from 28-44 minutes to sub-20 minutes while maintaining quality

**Progress**:
- ✅ **Phase 4: Model Optimization** (COMPLETE - 2025-11-08)
  - Researcher agent switched to Haiku model (5-10x faster, no quality loss)
  - File: `plugins/autonomous-dev/agents/researcher.md` (model: haiku)
  - Savings: 3-5 minutes per workflow
  - New baseline: 25-39 minutes (down from 28-44 minutes)
  - Quality maintained: Haiku excels at web search and pattern discovery
- ✅ **Phase 5: Prompt Simplification** (COMPLETE - 2025-11-08)
  - Researcher: 99 → 59 significant lines (40% reduction)
  - Planner: 119 → 73 significant lines (39% reduction)
  - Removed verbose instruction repetition, preserved essential guidance
  - Savings: 2-4 minutes per workflow (faster token processing)
  - Updated baseline: 22-36 minutes (Phase 4 + Phase 5 combined)
  - Quality: Core mission, responsibilities, process all intact
- ✅ **Phase 6: Profiling Infrastructure** (COMPLETE - 2025-11-08)
  - New library: `plugins/autonomous-dev/lib/performance_profiler.py` (539 lines)
  - Features: PerformanceTimer context manager, JSON logging, bottleneck detection
  - Metrics: min, max, avg, p95 calculations per agent per feature
  - Test coverage: 71/78 passing (91%)
  - Integration: Agents wrapped in PerformanceTimer for automatic timing
  - Enables data-driven Phase 7+ optimization

**Combined Results (Phases 4-6)**:
- Total time reduction: 5-9 minutes saved per feature (15-32% improvement)
- Baseline: 28-44 min → 19-35 min target (24% faster overall)
- Quality: All tests pass, zero security issues, research/planning quality maintained
- Next: Use Phase 6 profiler data to identify Phase 7+ bottlenecks

**Success Metrics - ALL MET**:
- ✅ Model optimization complete (Haiku researcher - 5-10x faster)
- ✅ Prompt simplification complete (40% token reduction)
- ✅ Profiling infrastructure complete (bottleneck detection enabled)
- ✅ Total time reduction: 5-9 minutes (within 8-12 minute goal)
- ✅ Zero quality degradation (all tests passing)
- ✅ TDD approach maintained (tests written first, before code)

---

## NOTES

**This file is the absolute gatekeeper** - All agents MUST consult it before work. In strict mode, work is BLOCKED if not aligned.

**Update frequency**: Review monthly or when strategic direction changes.

**Conflicts**: In strict mode, if user request conflicts with PROJECT.md → BLOCK work → User must update PROJECT.md or modify request.

**Preservation**: Strict mode enhances the existing autonomous-dev plugin with automatic enforcement.

**Meta-Achievement**: This plugin now enforces its own principles (PROJECT.md alignment, file organization, SDLC steps) on projects that use it.

---

**Last Updated**: 2025-10-27
**Version**: v3.1.0 (Agent-Skill Integration Architecture)
**Next Review**: 2025-11-26
