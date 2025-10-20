# Project Context - Claude Code Bootstrap

**Last Updated**: 2025-10-20
**Project**: Autonomous Development Plugin System with PROJECT.md-First Architecture
**Version**: v2.0.0

---

## GOALS ⭐

**What success looks like for this project**:

1. **Enable team collaboration through co-defined outcomes** - PROJECT.md serves as the shared strategic direction that both human developers and AI agents align to
2. **Maintain software engineering best practices** - Not just automation, but *quality* automation with TDD, code review, security scanning, proper git workflow
3. **Tight GitHub integration for team workflow** - Issues, PRs, milestones, code reviews, CI/CD all integrated seamlessly
4. **Personal productivity + team scalability** - Works for solo developers AND distributed teams working on shared codebase
5. **Prevent scope creep at team level** - Every feature (human or AI-written) validated against PROJECT.md before work begins

**Success Metrics**:
- **Team alignment**: 100% of work (human + AI) validates against PROJECT.md
- **Code quality**: 80%+ test coverage, all PRs reviewed, security scans pass
- **GitHub workflow**: Issues → Branches → PRs → Reviews → Merge (fully integrated)
- **Development speed**: 10x faster than manual (autonomous pipeline + human oversight)
- **Context efficiency**: < 8K tokens per feature (enables long-term collaboration)
- **Adoption**: Easy install for new team members (`/plugin install autonomous-dev`)

---

## SCOPE

**What's IN Scope** ✅ (Features we build):

**Team Collaboration** (PRIMARY FOCUS):
- ✅ **PROJECT.md as shared contract** - Co-defined outcomes that human + AI developers both follow
- ✅ **GitHub-first workflow** - Issues → Branches → PRs → Code Review → CI/CD → Merge
- ✅ **PR automation** - Auto-create PRs, link to issues, request reviews, update based on feedback
- ✅ **Code review integration** - Reviewer agent + human reviewers = quality gate
- ✅ **Milestone/Sprint tracking** - GitHub Milestones define sprints, PROJECT.md references current sprint
- ✅ **Team onboarding** - New developers install plugin, read PROJECT.md, start contributing

**Software Engineering Best Practices**:
- ✅ **TDD enforced** - Tests written before code (test-master → implementer flow)
- ✅ **Git workflow** - Feature branches, conventional commits, protected main branch
- ✅ **Code review** - All PRs reviewed (agent pre-review + human approval)
- ✅ **Security scanning** - Secrets detection, vulnerability scanning, OWASP compliance
- ✅ **Documentation sync** - README, CHANGELOG, API docs updated automatically
- ✅ **Test coverage** - 80%+ minimum enforced by CI/CD

**Autonomous Development Pipeline**:
- ✅ **8-agent coordination** - orchestrator validates PROJECT.md, then coordinates specialist agents
- ✅ **Model optimization** - opus (complex planning), sonnet (balanced), haiku (fast scans)
- ✅ **Context management** - Session files, /clear prompts, scales to 100+ features
- ✅ **/align-project command** - Brings existing projects into alignment with best practices

**Plugin Distribution**:
- ✅ **Plugin marketplace** - One-command install for teams
- ✅ **Multi-language support** - Python, JavaScript/TypeScript, Go, Rust (generic approach)
- ✅ **Customizable** - Teams can fork and adapt to their standards

**What's OUT of Scope** ❌ (Features we avoid):

- ❌ **Replacing human developers** - AI augments teams, doesn't replace them
- ❌ **Skipping code review** - All PRs require human approval (agent review is pre-filter)
- ❌ **Committing directly to main** - Always use feature branches + PRs
- ❌ **SaaS/Cloud hosting** - Local-first, teams own their infrastructure
- ❌ **Paid features** - 100% free, MIT license, community-driven
- ❌ **Language-specific lock-in** - Stay generic, support multiple ecosystems
- ❌ **Breaking existing workflows** - Enhance, don't disrupt team processes

**Boundaries**:
- Focus on automation of repetitive development tasks
- Keep system simple, maintainable, and extensible
- Prioritize developer experience and productivity
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

**Current Architecture** (v2.0.0):
- **Agents**: orchestrator (NEW), planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master (8 total)
- **Skills**: python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards (6 total)
- **Commands**: /align-project (with --safe, --sync-github flags)
- **Hooks**: Auto-format, auto-test, auto-enforce-coverage, security-scan
- **Plugin**: autonomous-dev (contains all components)

**Repository Structure** (CRITICAL):

This repository serves TWO audiences - contributors building the plugin AND users installing it.

**ROOT Level** (Development workspace - NOT distributed):
- `docs/` - Dev/contributor documentation (CONTRIBUTING.md, DEVELOPMENT.md, CODE-REVIEW-WORKFLOW.md, etc.)
- `scripts/` - Build/sync scripts for development (validate_structure.py, session_tracker.py, etc.)
- `tests/` - Repository infrastructure tests (test build scripts, test structure)
- Root `.md` files - Only essential: README.md, CHANGELOG.md, CLAUDE.md, CONTRIBUTING.md

**PLUGIN Level** (Distribution package - what users get):
- `plugins/autonomous-dev/docs/` - User documentation (COMMANDS.md, QUICKSTART.md, TROUBLESHOOTING.md, etc.)
- `plugins/autonomous-dev/scripts/` - User scripts (setup.py wizard)
- `plugins/autonomous-dev/tests/` - Plugin feature tests (test_uat.py, test_integration.py, test_architecture.py)
- `plugins/autonomous-dev/agents/` - 8 AI agents
- `plugins/autonomous-dev/skills/` - 6 core skills
- `plugins/autonomous-dev/commands/` - 33 slash commands
- `plugins/autonomous-dev/hooks/` - Automation hooks

**Enforcement**:
- `scripts/validate_structure.py` - Automated validation (run before commit)
- Pre-commit hook - Prevents misplaced files from being committed
- See CONTRIBUTING.md for complete file location guidelines

**The Golden Rule**:
1. WHO is this for? (Contributors → ROOT, Users → PLUGIN)
2. WHEN do they need it? (Building → ROOT, Using → PLUGIN)
3. WHAT is it? (Dev tool/doc → ROOT, Plugin feature/doc → PLUGIN)

### Performance Constraints

- **Context Budget**: Keep under 8,000 tokens per feature (CRITICAL)
- **Feature Time**: Target 20-30 minutes per feature (autonomous)
- **Test Execution**: Auto-tests should run in < 60 seconds
- **Session Management**: Use session files (log paths, not content) to prevent context bloat
- **Context Clearing**: MUST use `/clear` after each feature to maintain performance

### Security Constraints

- **No hardcoded secrets**: Enforced by security_scan.py hook
- **TDD mandatory**: Tests written before implementation (enforced by workflow)
- **Tool restrictions**: Each agent has minimal required permissions (principle of least privilege)
- **80% coverage minimum**: Enforced by auto_enforce_coverage.py hook
- **Security scanning**: Automatic vulnerability and secrets detection

### Team Constraints

- **Team Size**: Solo developer (akaszubski)
- **Skill Set**: Python, JavaScript/TypeScript, AI/ML, DevOps
- **Available Time**: Looking to automate away repetitive tasks
- **Autonomous Operation**: System should work with minimal human intervention

---

## DEVELOPMENT WORKFLOW

### File Locations (CRITICAL for Plugin Development)

**This project builds Claude Code automation tools for distribution via marketplace.**

#### ✅ Git-Tracked Locations (ALWAYS edit here)

All changes MUST go to these locations for git tracking and distribution:

```
.claude/                          # Project-specific config
├── commands/                     # Slash commands
├── PROJECT.md                    # Project architecture (this file)
└── hooks/                        # Git hooks

plugins/autonomous-dev/           # Plugin for marketplace distribution
├── commands/                     # Slash commands (synced with .claude/commands/)
├── agents/                       # 8 AI agents (orchestrator, planner, etc.)
├── skills/                       # 6 core skills (python-standards, etc.)
├── hooks/                        # Automation hooks (auto_format, auto_test, etc.)
└── marketplace.json              # Plugin metadata
```

#### ❌ Personal Config (NEVER edit for this project)

These are your personal global settings, NOT for git or distribution:

```
~/.claude/                        # Your personal config (NOT IN GIT)
├── commands/                     # Auto-populated when plugin installs
├── CLAUDE.md                     # Your personal instructions
└── settings.json                 # Your personal settings
```

### Workflow for Changes

**When adding/updating commands**:
```bash
# 1. Edit in plugin source (changes are immediately active via symlink)
vim plugins/autonomous-dev/commands/my-command.md

# 2. Test immediately (symlink makes it active in Claude)
# In Claude Code: /my-command

# 3. Commit and push when ready
git add plugins/autonomous-dev/commands/my-command.md
git commit -m "feat: add my-command"
git push

# 4. Users get update by reinstalling
# In Claude Code: /plugin uninstall autonomous-dev
#                 /plugin install autonomous-dev
```

**When adding/updating agents, skills, hooks**:
```bash
# Edit directly in plugin directory
vim plugins/autonomous-dev/agents/my-agent.md

# Commit and push
git add plugins/autonomous-dev/
git commit -m "feat: add my-agent"
git push
```

### Distribution

Users install via marketplace:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

This copies everything from `plugins/autonomous-dev/` to their personal `~/.claude/` folder.

### Key Principle

**This repository is the SOURCE OF TRUTH for the autonomous-dev plugin.**

- Personal `~/.claude/` = where plugin gets INSTALLED (runtime)
- `.claude/` and `plugins/autonomous-dev/` = where we DEVELOP (source)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed workflow.

---

## CURRENT SPRINT

**Sprint Name**: Sprint 6: Team Collaboration Features 🚧
**GitHub Milestone**: [Create milestone](https://github.com/akaszubski/autonomous-dev/milestones)
**Duration**: 2025-10-20 → 2025-11-03 (2 weeks)
**Status**: In Progress (10% complete)

**Sprint Goals**:
1. 🚧 **PR automation** - Auto-create PRs, link to issues, request human reviews
2. ⏸️ **Enhanced GitHub integration** - Bidirectional sync (issues → branches → PRs → merge)
3. ⏸️ **Team onboarding workflow** - New dev guide, PROJECT.md template examples
4. ⏸️ **Code review integration** - Agent pre-review + human approval workflow
5. ⏸️ **Update PROJECT.md with actual intent** - Team collaboration focus (IN PROGRESS)

**Current Tasks**:
- 🚧 Updated PROJECT.md with team collaboration intent
- 🚧 Added REFERENCES & DOCUMENTATION section (30+ resources)
- ⏸️ Test orchestrator with real PROJECT.md
- ⏸️ Implement PR creation automation
- ⏸️ Add reviewer + human review workflow
- ⏸️ Create team onboarding guide

**Completed in Sprint 5**:
- ✅ PROJECT.md-first architecture
- ✅ 8-agent pipeline with orchestrator
- ✅ /align-project command
- ✅ Testing infrastructure (30 automated tests)
- ✅ Plugin v2.0.0 release

**Next Sprint**: Sprint 7: Community & Adoption
- Announce v2.0.0 on GitHub Discussions
- Create case studies / examples
- Team collaboration demo video
- Onboard first external contributor

---

## ARCHITECTURE

### Current System Architecture (v2.0.0)

```
User Request
     ↓
orchestrator (PRIMARY MISSION: Validate PROJECT.md Alignment)
     │
     ├─> 1. Read .claude/PROJECT.md
     ├─> 2. Validate: GOALS alignment?
     ├─> 3. Validate: IN SCOPE?
     ├─> 4. Validate: CONSTRAINTS respected?
     ├─> 5. [Optional] Query GitHub Milestone (.env auth)
     └─> 6. Only proceed if aligned ✅
     ↓
7-Agent Pipeline (if aligned):
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
Quality Hooks (auto-format, auto-test, security-scan, coverage)
     ↓
Production Code
```

**Priority Hierarchy**:
1. **PRIMARY**: PROJECT.md alignment (MOST IMPORTANT)
2. **SECONDARY**: GitHub integration (optional, supporting)
3. **SUPPORTING**: Safe alignment workflow

### Agent Responsibilities

**Current Agents** (in `plugins/autonomous-dev/agents/`) - v2.0.0:

- **orchestrator** (NEW): Master coordinator with PRIMARY MISSION to validate PROJECT.md alignment (model: sonnet, tools: Task, Read, Bash)
- **planner**: Creates implementation plans (model: opus - UPDATED for complex planning, tools: Read, Grep, Glob, Bash)
- **researcher**: Web research for best practices (model: sonnet - UPDATED, tools: WebSearch, WebFetch, Grep, Glob, Read)
- **test-master**: Writes TDD tests first (model: sonnet, tools: Read, Write, Edit, Bash, Grep, Glob)
- **implementer**: Makes tests pass (model: sonnet, tools: Read, Write, Edit, Bash, Grep, Glob)
- **reviewer**: Quality gate checks (model: sonnet - UPDATED, tools: Read, Bash, Grep, Glob)
- **security-auditor**: Security scanning (model: haiku, tools: Read, Bash, Grep, Glob)
- **doc-master**: Documentation sync (model: haiku, tools: Read, Write, Edit, Bash, Grep, Glob)

### Skills System (Current)

**Existing Skills** (in `plugins/autonomous-dev/skills/`):

- `python-standards`: PEP 8, type hints, docstrings
- `testing-guide`: TDD workflow, pytest patterns
- `security-patterns`: OWASP, secrets management
- `documentation-guide`: Docstring format, README updates
- `research-patterns`: Web search strategies
- `engineering-standards`: Code quality standards

### Hooks System (Current)

**Existing Hooks** (in `hooks/`):

- `auto_format.py`: black + isort for Python, prettier for JS/TS
- `auto_test.py`: pytest on related tests
- `auto_enforce_coverage.py`: 80% minimum coverage enforcement
- `security_scan.py`: Secret detection, vulnerability scanning

**Hook Integration** (in `.claude/settings.local.json`):
- UserPromptSubmit: Display project context
- SubagentStop: Log completion (to be added)
- PostToolUse: Trigger formatting, testing, coverage, security

### Session Management (New)

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

### Context Clearing (Critical)

**Why**: Without clearing context:
- After 3-4 features: Context reaches 50K+ tokens
- System becomes slow and unreliable
- Eventually fails completely

**How**: Use `/clear` after each feature completes
- Clears conversation history (not files!)
- Resets context budget
- Maintains system performance

**When**:
- After each feature completes (mandatory)
- Before starting unrelated feature
- If responses feel slow
- If context warnings appear

---

## AGENT GUIDANCE

### How Agents Should Use This File

**Before ANY work**, agents must:

1. **Read PROJECT.md** - Understand goals, scope, constraints
2. **Validate alignment** - Does feature serve GOALS?
3. **Check scope** - Is feature IN or OUT of scope?
4. **Respect constraints** - Stay within technical/security boundaries
5. **Follow architecture** - Use existing agents/skills/hooks

### Alignment Check Process

```python
def validate_feature(feature_request, project_md):
    # 1. Does it serve GOALS?
    if not serves_goals(feature_request, project_md.goals):
        return reject("Feature doesn't advance project goals")

    # 2. Is it in SCOPE?
    if not in_scope(feature_request, project_md.scope):
        return reject("Feature is out of scope")

    # 3. Respects CONSTRAINTS?
    if violates_constraints(feature_request, project_md.constraints):
        return reject("Feature violates project constraints")

    # All checks pass
    return approve(feature_request)
```

### When to Reject Features

Politely reject when:
- Feature doesn't serve project GOALS
- Feature is explicitly OUT of SCOPE
- Feature violates CONSTRAINTS
- Feature conflicts with ARCHITECTURE

**Rejection Template**:
```
⚠️ Feature Alignment Issue

**Project Goal**: [Goal from PROJECT.md]
**Requested**: [Feature]
**Issue**: [Why it doesn't align]

**Suggestion**: [Alternative approach that aligns]

Would you like to:
1. Modify feature to align with goals
2. Update PROJECT.md goals (requires conscious decision)
3. Explore alternative approach
```

---

## DEVELOPMENT WORKFLOW

### Standard Feature Development Flow

1. **Alignment Check**: Verify feature aligns with PROJECT.md
2. **Research**: Researcher agent finds patterns and best practices
3. **Planning**: Planner agent creates implementation plan
4. **TDD Tests**: Test-master writes failing tests
5. **Implementation**: Implementer makes tests pass
6. **Review**: Reviewer checks quality
7. **Security**: Security-auditor scans for issues
8. **Documentation**: Doc-master updates docs
9. **Context Clear**: Use `/clear` to reset for next feature

### Session-Based Communication

**Agents log to session** (not context):
```bash
python scripts/session_tracker.py researcher "Research complete - docs/research/auth.md"
```

**Next agent reads session** (not full files):
```bash
SESSION_FILE=$(ls -t docs/sessions/ | head -1)
cat docs/sessions/$SESSION_FILE  # See file paths, load files directly
```

**Result**: Context stays small, system stays fast

---

## NOTES

**This file is the north star** - All agents consult it before work.

**Update frequency**: Review monthly or when strategic direction changes.

**Conflicts**: If user request conflicts with PROJECT.md, discuss rather than auto-reject.

**Preservation**: This system enhances the existing autonomous-dev plugin, not replaces it.

---

**Last Updated**: 2025-10-20
**Version**: v2.0.0
**Next Review**: 2025-11-20
