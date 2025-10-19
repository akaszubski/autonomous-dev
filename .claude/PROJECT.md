# Project Context - Claude Code Bootstrap

**Last Updated**: 2025-10-20
**Project**: Autonomous Development Plugin System with PROJECT.md-First Architecture
**Version**: v2.0.0

---

## GOALS ⭐

**What success looks like for this project**:

1. **Prevent scope creep through PROJECT.md-first architecture** - Every feature validated against strategic direction before work begins
2. **Enable one-command autonomous development** - Users install once (`/plugin install autonomous-dev`) and achieve 10x faster development
3. **Maintain high code quality automatically** - 80%+ test coverage, TDD enforcement, security scanning without manual effort
4. **Enable scalability** - Support 100+ features without context degradation through session management and `/clear` workflow

**Success Metrics**:
- **Alignment**: 100% of features validated against PROJECT.md before work begins
- **Development time**: Target < 30 minutes per feature (fully autonomous pipeline)
- **Test coverage**: Target 80%+ (enforced automatically by hooks)
- **Context efficiency**: < 8,000 tokens per feature (scales to 100+ features)
- **Installation**: < 60 seconds one-command install (`/plugin install autonomous-dev`)
- **Model costs**: 40% reduction through optimization (opus/sonnet/haiku)

---

## SCOPE

**What's IN Scope** ✅ (Features we build):

**Core Architecture** (v2.0.0):
- ✅ **PROJECT.md-first alignment** - orchestrator validates GOALS/SCOPE/CONSTRAINTS before every feature
- ✅ **8-agent pipeline** - orchestrator + researcher + planner + test-master + implementer + reviewer + security-auditor + doc-master
- ✅ **Model optimization** - opus (planner), sonnet (most), haiku (fast tasks) for 40% cost reduction
- ✅ **/align-project command** - 3-phase safe alignment (Analyze → Generate → Interactive)
- ✅ **GitHub integration (optional)** - Sprint tracking via .env authentication

**Existing Features** (preserved):
- ✅ Session-based context management (prevents context bloat)
- ✅ Auto-formatting and auto-testing (Python, JavaScript/TypeScript)
- ✅ Security scanning (secrets detection, vulnerability scanning)
- ✅ Documentation sync (auto-update docs, CHANGELOG)
- ✅ Plugin marketplace distribution
- ✅ 6 core skills (python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards)

**What's OUT of Scope** ❌ (Features we avoid):

- ❌ Manual code reviews (automated via reviewer agent)
- ❌ Manual testing (TDD enforced via test-master)
- ❌ Manual documentation (doc-master handles automatically)
- ❌ Manual security scans (security-auditor handles automatically)
- ❌ IDE-specific features (only Claude Code 2.0 plugins)
- ❌ Language-specific tools (stay generic, multi-language)
- ❌ Cloud hosting/SaaS (local-only plugins)
- ❌ Paid features (100% free, MIT license)
- ❌ Breaking changes to existing user configurations

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
- **Commands**: /align-project, /align-project-safe (NEW)
- **Hooks**: Auto-format, auto-test, auto-enforce-coverage, security-scan
- **Plugin**: autonomous-dev (contains all components)

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

## CURRENT SPRINT

**Sprint Name**: Sprint 5: Testing & Validation ✅
**GitHub Milestone**: N/A (this is the source repo, not using milestones internally)
**Duration**: 2025-10-20 → Complete
**Status**: 100% complete ✅

**Sprint Goals**:
1. ✅ Implement PROJECT.md-first architecture
2. ✅ Create comprehensive testing infrastructure
3. ✅ Update all documentation (3 README files)
4. ✅ Dogfood: Apply PROJECT.md to claude-code-bootstrap itself
5. ⏸️ Announce v2.0.0 release (NEXT)

**Completed Tasks**:
- ✅ Enhanced orchestrator with PRIMARY MISSION for PROJECT.md alignment
- ✅ Created /align-project command (standard + safe with 3 phases)
- ✅ GitHub integration setup (.env auth, GITHUB_AUTH_SETUP.md)
- ✅ PROJECT.md template (generic, domain-agnostic)
- ✅ Updated root README.md with PROJECT.md-first architecture
- ✅ Updated plugins/autonomous-dev/README.md (v2.0.0 features)
- ✅ Updated .mcp/README.md with integration details
- ✅ Created automated test script (30 tests, all passing)
- ✅ Created comprehensive testing guide (docs/TESTING_GUIDE.md)
- ✅ Created/updated PROJECT.md for this repo (THIS FILE)

**Next Sprint**: Sprint 6: Release & Community
- Announce v2.0.0 on GitHub Discussions
- Create release notes
- Tag v2.0.0 release
- Update marketplace listing

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
