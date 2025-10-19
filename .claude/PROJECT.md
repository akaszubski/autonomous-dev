# Project Context - Claude Code Bootstrap

**Last Updated**: 2025-10-19
**Project**: Autonomous Development System for Claude Code

---

## GOALS

**What success looks like for this project**:

1. **Build autonomous development system** - Enable Claude Code to handle complete feature development from research through deployment
2. **Reduce development time** - Reduce manual dev time from 40 hours/week to 6 hours/week through automation
3. **Maintain high code quality** - Maintain 80%+ test coverage automatically with TDD enforcement
4. **Enable scalability** - Support 100+ features without context degradation or system failures

**Success Metrics**:
- Development time: Target < 30 minutes per feature (autonomous)
- Test coverage: Target 80%+ (enforced automatically)
- Code quality: Automated enforcement via hooks
- Time to feature: Target 20-30 minutes research-to-production
- Context efficiency: < 8,000 tokens per feature (scalable to 100+ features)

---

## SCOPE

**What's IN Scope** (Features we build):

- ✅ Autonomous development workflow (research → plan → TDD → implement → review)
- ✅ Auto-formatting and auto-testing (Python, JavaScript/TypeScript)
- ✅ Security scanning (secrets detection, vulnerability scanning)
- ✅ Documentation sync (auto-update docs, CHANGELOG)
- ✅ Session-based context management (prevents context bloat)
- ✅ PROJECT.md alignment checks (prevents scope creep)
- ✅ Multi-agent orchestration (researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master)
- ✅ Plugin system for extending functionality

**What's OUT of Scope** (Features we avoid):

- ❌ Manual code reviews (automated via reviewer agent)
- ❌ Manual testing (TDD enforced via test-master)
- ❌ Manual documentation (doc-master handles automatically)
- ❌ Manual security scans (security-auditor handles automatically)
- ❌ Features that don't serve automation goal
- ❌ Complex UI/UX features (focus on developer workflow)
- ❌ Non-development tasks (this is a dev automation system)

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
- Language: Python 3.8+ for hooks/scripts
- Testing: pytest (Python), jest (JavaScript)
- Formatting: black, isort (Python), prettier (JavaScript/TypeScript)
- Claude Code: 2.0+ with plugins, agents, hooks, skills support
- Git: For version control and PR automation

**Current Architecture** (preserve and enhance):
- Agents: planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master
- Skills: python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards
- Hooks: Auto-format, auto-test, auto-enforce-coverage, security-scan
- Plugin: autonomous-dev (contains all agents and skills)

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

## ARCHITECTURE

### Current System Architecture

```
User Request
     ↓
Orchestrator Agent (future enhancement)
     ↓
┌────────────┬─────────────┬──────────────┬─────────────┐
│ Researcher │   Planner   │ Test-Master  │ Implementer │
│  (Haiku)   │  (Sonnet)   │   (Sonnet)   │  (Sonnet)   │
│  Read-only │  Read-only  │  Write Tests │  Write Code │
└────────────┴─────────────┴──────────────┴─────────────┘
     ↓
┌────────────┬─────────────┬──────────────┐
│  Reviewer  │  Security   │  Doc-Master  │
│  (Haiku)   │  (Haiku)    │   (Haiku)    │
│  Read-only │  Read+Bash  │  Write Docs  │
└────────────┴─────────────┴──────────────┘
     ↓
Quality Hooks (auto-format, auto-test, security-scan, coverage)
     ↓
Production Code
```

### Agent Responsibilities

**Current Agents** (in `plugins/autonomous-dev/agents/`):

- **researcher**: Web research for best practices (model: haiku, tools: WebSearch, WebFetch, Grep, Glob, Read)
- **planner**: Creates implementation plans (model: sonnet, tools: Read, Grep, Glob, Bash - read-only)
- **test-master**: Writes TDD tests first (model: sonnet, tools: Read, Write, Bash)
- **implementer**: Makes tests pass (model: sonnet, tools: Read, Write, Edit, Bash)
- **reviewer**: Quality gate checks (model: haiku, tools: Read - read-only)
- **security-auditor**: Security scanning (model: haiku, tools: Read, Bash)
- **doc-master**: Documentation sync (model: haiku, tools: Read, Write, Edit)

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

**Last Updated**: 2025-10-19
**Next Review**: 2025-11-19
