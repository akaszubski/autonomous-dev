# Project Context - Autonomous Development Plugin

**Last Updated**: 2025-10-25
**Project**: Software Engineering Operating System - Auto-SDLC Enforcement via "Vibe Coding"
**Version**: v2.4.0 (Streamlined GenAI Validation)

---

## GOALS ⭐

**Primary Mission**: Build an **Autonomous Development Team** - not a toolkit, but a self-managing team of AI agents that execute on PROJECT.md goals using best practices, skills, and consistency. User states WHAT they want, the team autonomously handles HOW.

**Core Philosophy**:
- **Team, not toolkit** - Autonomous agents work together, not manual commands the user orchestrates
- **WHAT, not HOW** - User specifies goals in natural language, team figures out implementation
- **Autonomous git operations** - Team auto-commits, auto-pushes, auto-creates PRs (no manual git commands)
- **PROJECT.md is the mission** - Team executes on PROJECT.md strategic goals, validates alignment automatically
- **Minimal commands** - 5 essential commands maximum (auto-implement, align-project, setup, test, status)

**What success looks like**:

1. **True Autonomous Execution** - User says "implement user authentication" → Team autonomously: researches, plans, writes tests, implements, reviews, audits security, updates docs, commits, pushes, creates PR → User sees: "✅ Feature complete! PR #42: https://..."

2. **PROJECT.md is Team's Mission** - 100% of work validates against PROJECT.md BEFORE execution → Team blocks work if not aligned → Single source of strategic truth → Team updates PROJECT.md progress automatically

3. **Zero Manual Git Operations** - Team autonomously: generates commit messages (GenAI), creates commits, pushes to feature branches, creates PRs with comprehensive descriptions (GenAI) → User never runs git commands manually

4. **Professional Consistency Automated** - All SDLC steps (research, plan, TDD, implement, review, security, docs) enforced by team workflow → Can't skip steps → Quality is automatic → GenAI makes intelligent decisions throughout

5. **Minimal User Intervention** - 5 commands total (not 22) → `/auto-implement <feature>` does everything → `/status` shows progress → `/align-project` validates alignment → `/setup` configures → `/test` for debugging only

**Success Metrics**:
- **Autonomous execution**: 100% of features auto-commit, auto-push, auto-PR (zero manual git)
- **Command minimalism**: ≤ 5 commands total (22 → 5 = -77% complexity)
- **Alignment enforcement**: 0% of work proceeds without PROJECT.md validation
- **SDLC compliance**: 100% of features follow research → plan → TDD → implement → review → security → docs
- **GenAI decision-making**: 95%+ decisions made by GenAI (not regex/hardcoded rules)
- **Test coverage**: 80%+ enforced automatically
- **Context efficiency**: < 8K tokens per feature (team uses agents, not context)
- **User effort**: 1 command per feature (`/auto-implement`) → team handles rest

**Success Example**:
```bash
# User input (simple)
/auto-implement "Add rate limiting to API"

# Team output (automatic, 5-10 minutes)
✅ Feature complete!
   PR #43: https://github.com/user/repo/pull/43
   PROJECT.md: "Performance" goal → 60% complete
```

**Meta-Goal**: This plugin enforces its own principles (autonomous team model) on projects that use it.

---

## SCOPE

**What's IN Scope** ✅ (Features we build):

**Core Auto-Orchestration** (PRIMARY FOCUS):
- ✅ **Feature request detection** - Automatic triggers on "implement", "add", "create", "build", etc.
- ✅ **Orchestrator auto-invocation** - No manual `/auto-implement` needed → Natural language triggers agents
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
- ✅ **8-agent coordination** - orchestrator validates PROJECT.md, then coordinates specialist agents
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

### Technical Constraints

**Required Technology**:
- **Primary**: Markdown (agent/skill/command definitions)
- **Supporting**: Python 3.11+ (hooks/scripts), Bash (testing/automation), JSON (config)
- **Testing**: pytest (Python), jest (JavaScript), automated test script (Bash)
- **Formatting**: black, isort (Python), prettier (JavaScript/TypeScript)
- **Claude Code**: 2.0+ with plugins, agents, hooks, skills, slash commands
- **Git**: For version control and rollback safety

**Current Architecture** (v2.4.0 - Streamlined):
- **Agents**: orchestrator (gatekeeper), planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master (8 total)
- **Skills**: python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards, consistency-enforcement (7 total - UPDATED)
- **Commands**: /setup (with --strict-mode), /align-project (with --safe, --sync-github flags), /align-project-retrofit (PLANNED)
- **Hooks**:
  - Auto-orchestration: detect_feature_request.py (UserPromptSubmit)
  - Gatekeeper: validate_project_alignment.py (PreCommit)
  - File organization: enforce_file_organization.py
  - Quality: auto_format.py, auto_test.py, security_scan.py
  - Docs: validate_docs_consistency.py
- **Plugin**: autonomous-dev (contains all components)

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
- `plugins/autonomous-dev/scripts/` - User scripts (setup.py wizard)
- `plugins/autonomous-dev/tests/` - Plugin feature tests
- `plugins/autonomous-dev/agents/` - 8 AI agents
- `plugins/autonomous-dev/skills/` - 7 core skills
- `plugins/autonomous-dev/commands/` - Slash commands
- `plugins/autonomous-dev/hooks/` - Automation hooks (including auto-orchestration)
- `plugins/autonomous-dev/templates/` - Project templates (settings.strict-mode.json, project-structure.json)

### Performance Constraints

- **Context Budget**: Keep under 8,000 tokens per feature (CRITICAL)
- **Feature Time**: Target 20-30 minutes per feature (autonomous)
- **Test Execution**: Auto-tests should run in < 60 seconds
- **Session Management**: Use session files (log paths, not content) to prevent context bloat
- **Context Clearing**: MUST use `/clear` after each feature to maintain performance
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

### System Architecture (v2.4.0 - Streamlined)

```
User: "implement user authentication"  [VIBE CODING]
     ↓
[Feature Detection Hook] (UserPromptSubmit)
detect_feature_request.py
     ├─> Detects: "implement", "add", "create", "build", etc.
     └─> Auto-invokes: orchestrator agent
     ↓
orchestrator (GATEKEEPER - PRIMARY MISSION)
     │
     ├─> 1. Read PROJECT.md (GOALS, SCOPE, CONSTRAINTS)
     ├─> 2. Validate: Does feature serve GOALS?
     ├─> 3. Validate: Is feature IN SCOPE?
     ├─> 4. Validate: Respects CONSTRAINTS?
     ├─> 5. DECISION:
     │      ✅ Aligned → Proceed with agent pipeline
     │      ❌ NOT Aligned → BLOCK work
     │                       → User must update PROJECT.md OR modify request
     └─> 6. Log alignment decision to session
     ↓
7-Agent Pipeline (ONLY if PROJECT.md aligned):
     ↓
┌────────────┬─────────────┬──────────────┬─────────────┐
│ Researcher │   Planner   │ Test-Master  │ Implementer │
│  (Sonnet)  │   (Opus)    │   (Sonnet)   │  (Sonnet)   │
│  Read-only │  Read-only  │  Write Tests │  Write Code │
│  5 min     │   5 min     │    5 min     │   12 min    │
└────────────┴─────────────┴──────────────┴─────────────┘
     ↓
┌────────────┬─────────────┬──────────────┐
│  Reviewer  │  Security   │  Doc-Master  │
│  (Sonnet)  │   (Haiku)   │   (Haiku)    │
│  Read-only │  Read+Bash  │  Write Docs  │
│   2 min    │    2 min    │    1 min     │
└────────────┴─────────────┴──────────────┘
     ↓
Prompt: "Run /clear for next feature"
     ↓
[Pre-Commit Hooks] (BLOCKING - Strict Mode)
     ├─> validate_project_alignment.py  [PROJECT.md GATEKEEPER]
     ├─> auto_test.py                   [Tests must pass]
     ├─> security_scan.py               [Security must pass]
     └─> validate_docs_consistency.py   [Docs must be synced]
     ↓
     ✅ All pass → Commit allowed
     ❌ Any fail → Commit BLOCKED
     ↓
Production Code (Professional Quality Guaranteed)
```

**Priority Hierarchy**:
1. **PRIMARY**: PROJECT.md alignment (GATEKEEPER - MOST IMPORTANT)
2. **SECONDARY**: Auto-orchestration (enables vibe coding)
3. **TERTIARY**: File organization enforcement
4. **SUPPORTING**: SDLC step enforcement

### Agent Responsibilities (v2.4.0)

**orchestrator** (ENHANCED):
- **PRIMARY MISSION**: PROJECT.md gatekeeper
- **Strict Mode**: Validates alignment BEFORE proceeding
- **Blocks work**: If feature not in SCOPE
- **Auto-invoked**: By detect_feature_request.py hook
- Tools: Task, Read, Bash
- Model: sonnet

**Specialist Agents** (Unchanged):
- **researcher**: Web research, best practices (sonnet, read-only)
- **planner**: Implementation plans (opus, read-only)
- **test-master**: TDD tests (sonnet, write tests)
- **implementer**: Make tests pass (sonnet, write code)
- **reviewer**: Quality gate (sonnet, read-only)
- **security-auditor**: Security scan (haiku, read-only)
- **doc-master**: Documentation sync (haiku, write docs)

### Strict Mode Components

**Auto-Orchestration**:
- `hooks/detect_feature_request.py` - Detects vibe coding, auto-invokes orchestrator
- `agents/orchestrator.md` - Enhanced with STRICT MODE gatekeeper logic
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
- ✅ **Clear after features** - Use `/clear` after each feature completes
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
**Status**: In Progress (60% complete)

**Sprint Goals**:
1. ✅ **Auto-orchestration engine** - "Vibe coding" triggers full agent pipeline
2. ✅ **PROJECT.md gatekeeper** - Blocks work if not aligned
3. ✅ **File organization enforcement** - Standard structure enforced
4. ✅ **Strict mode configuration** - Pre-configured templates
5. 🚧 **Brownfield alignment** - `/align-project-retrofit` command (PLANNED)
6. 🚧 **Documentation** - Complete strict mode guide

**Completed in This Sprint**:
- ✅ Feature detection hook (detect_feature_request.py)
- ✅ PROJECT.md gatekeeper hook (validate_project_alignment.py)
- ✅ File organization enforcer (enforce_file_organization.py)
- ✅ Strict mode settings template
- ✅ Standard project structure template
- ✅ Orchestrator enhancement (gatekeeper logic)
- ✅ Comprehensive validation system (12 checks)
- ✅ Strict mode documentation (STRICT-MODE.md)

**Next Tasks**:
- 🚧 Build `/align-project-retrofit` command
- 🚧 Test auto-orchestration with real projects
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

**Step 2: Vibe Coding**
```bash
# Just describe what you want in natural language
"implement user authentication with JWT tokens"

# Auto-orchestration activates:
→ detect_feature_request.py detects feature request
→ Orchestrator auto-invokes
→ Checks PROJECT.md alignment
→ If aligned: Agent pipeline executes
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

**Step 5: Context Clearing**
```bash
/clear  # After each feature (mandatory for performance)
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
9. **Context Clear**: Use `/clear` to reset for next feature

### File Locations (CRITICAL for Plugin Development)

**Git-Tracked Locations** (ALWAYS edit here):

```
plugins/autonomous-dev/           # Plugin for marketplace distribution
├── agents/                       # 8 AI agents
├── skills/                       # 7 core skills
├── commands/                     # Slash commands
├── hooks/                        # Automation hooks (auto-orchestration, etc.)
├── templates/                    # Project templates (strict-mode, structure)
├── docs/                         # User documentation (STRICT-MODE.md, etc.)
├── scripts/                      # User scripts (setup.py)
└── tests/                        # Plugin tests
```

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

## NOTES

**This file is the absolute gatekeeper** - All agents MUST consult it before work. In strict mode, work is BLOCKED if not aligned.

**Update frequency**: Review monthly or when strategic direction changes.

**Conflicts**: In strict mode, if user request conflicts with PROJECT.md → BLOCK work → User must update PROJECT.md or modify request.

**Preservation**: Strict mode enhances the existing autonomous-dev plugin with automatic enforcement.

**Meta-Achievement**: This plugin now enforces its own principles (PROJECT.md alignment, file organization, SDLC steps) on projects that use it.

---

**Last Updated**: 2025-10-25
**Version**: v2.4.0 (Streamlined GenAI Validation)
**Next Review**: 2025-11-25
