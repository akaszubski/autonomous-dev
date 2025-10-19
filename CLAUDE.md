# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-10-19
**Project**: Autonomous Development System for Claude Code
**Type**: Plugin System / Development Tools

---

## Project Overview

This is the **claude-code-bootstrap** repository, providing production-ready plugins for autonomous development in Claude Code 2.0.

**Core Plugin**: `autonomous-dev` - Complete autonomous development workflow with agents, skills, and hooks

**Purpose**: Enable developers to build features 10x faster through intelligent automation of repetitive tasks (formatting, testing, documentation, security scanning).

---

## Context Management (CRITICAL!)

### Why This Matters

Without proper context management:
- ❌ After 3-4 features: Context reaches 50K+ tokens
- ❌ System becomes slow and unreliable
- ❌ Eventually fails completely

With context management:
- ✅ Context stays under 8K tokens per feature
- ✅ System works efficiently for 100+ features
- ✅ Fast, reliable responses

### After Each Feature: Clear Context

```bash
/clear
```

**What this does**:
- Clears conversation history (not files!)
- Resets context budget
- Maintains system performance

**What stays**:
- All your code, tests, docs
- All agents, skills, hooks
- All configurations
- [PROJECT.md](.claude/PROJECT.md) and goals

### When to Clear

- ✅ After each feature completes (mandatory)
- ✅ Before starting unrelated feature
- ✅ If responses feel slow
- ✅ If context warnings appear

### Context Budget

- **Maximum**: 8,000 tokens per feature
- **Strategy**: Session files (log paths, not content)
- **Monitoring**: Check session files in `docs/sessions/`

### How Session Files Help

Instead of loading full documents into context:

```bash
# ❌ BAD: Load full file into context
research_content = read_file("docs/research/auth.md")  # 5,000 tokens!

# ✅ GOOD: Use session file
session = read_file("docs/sessions/20251019-210332-session.md")  # 200 tokens
# Session contains: "researcher: Complete - docs/research/auth.md"
# Next agent reads file path from session, loads file directly
```

**Result**: Context stays small, system stays fast.

---

## PROJECT.MD - Staying On Track

### What is PROJECT.MD?

[`.claude/PROJECT.md`](.claude/PROJECT.md) defines:
- **GOALS**: What we're trying to achieve
- **SCOPE**: What's in/out of scope
- **CONSTRAINTS**: Technical/security/budget limits
- **ARCHITECTURE**: How the system works

### How to Use PROJECT.MD

**Before starting work on a feature**, check:

1. **Read PROJECT.md**:
   ```bash
   cat .claude/PROJECT.md | grep -A 10 "## GOALS"
   ```

2. **Verify alignment**:
   - Does feature serve the GOALS?
   - Is feature IN SCOPE?
   - Does feature respect CONSTRAINTS?

3. **Proceed or adjust**:
   - If aligned: Proceed with implementation
   - If not aligned: Modify feature or update PROJECT.md

### Example Alignment Check

```
User: "Add blockchain integration to the plugin system"

Check PROJECT.md:
- GOAL: "Build autonomous development system for Claude Code"
- SCOPE: "Autonomous development workflow (research → plan → TDD → implement)"

Result: ❌ NOT ALIGNED
Reason: Blockchain doesn't serve autonomous development goal

Suggestion: Focus on enhancing existing autonomous workflow
```

### When to Update PROJECT.MD

Review and update when:
- Strategic direction changes
- New major goals emerge
- Scope boundaries need adjustment
- Technical constraints change

**Update process**:
```bash
vim .claude/PROJECT.md
git add .claude/PROJECT.md
git commit -m "docs: Update project goals"
```

---

## Autonomous Development Workflow

### Standard Feature Development

1. **Alignment Check**: Verify feature aligns with [PROJECT.md](.claude/PROJECT.md)
2. **Research**: Researcher agent finds patterns and best practices
3. **Planning**: Planner agent creates implementation plan
4. **TDD Tests**: Test-master writes failing tests FIRST
5. **Implementation**: Implementer makes tests pass
6. **Review**: Reviewer checks quality
7. **Security**: Security-auditor scans for issues
8. **Documentation**: Doc-master updates docs + CHANGELOG
9. **Context Clear**: Use `/clear` to reset for next feature

### Session-Based Communication

**Agents log to session files** (not context):
```bash
python scripts/session_tracker.py researcher "Research complete - docs/research/webhooks.md"
```

**Check session logs**:
```bash
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

**Benefits**:
- Context stays minimal
- Full audit trail preserved
- Easy to review what happened

---

## Architecture

### Agents (7 specialists)

Located in: `plugins/autonomous-dev/agents/`

- **researcher**: Web research, pattern discovery (tools: WebSearch, WebFetch, Grep, Glob, Read)
- **planner**: Architecture planning, design (tools: Read, Grep, Glob, Bash)
- **test-master**: TDD, testing specialist (tools: Read, Write, Edit, Bash, Grep, Glob)
- **implementer**: Code implementation (tools: Read, Write, Edit, Bash, Grep, Glob)
- **reviewer**: Code quality gate (tools: Read, Bash, Grep, Glob)
- **security-auditor**: Security scanning (tools: Read, Bash, Grep, Glob)
- **doc-master**: Documentation sync (tools: Read, Write, Edit, Bash, Grep, Glob)

### Skills (6 core competencies)

Located in: `plugins/autonomous-dev/skills/`

- **python-standards**: PEP 8, type hints, docstrings
- **testing-guide**: TDD workflow, pytest patterns
- **security-patterns**: OWASP, secrets management
- **documentation-guide**: Docstring format, README updates
- **research-patterns**: Web search strategies
- **engineering-standards**: Code quality standards

### Hooks (Automation)

Located in: `hooks/`

**PostToolUse hooks** (run after file operations):
- `auto_format.py`: black + isort (Python), prettier (JS/TS)
- `auto_test.py`: pytest on related tests
- `auto_enforce_coverage.py`: 80% minimum coverage
- `security_scan.py`: Secrets detection, vulnerability scanning

**Lifecycle hooks**:
- `UserPromptSubmit`: Display project context
- `SubagentStop`: Log agent completion to session

---

## Code Quality Standards

### Python

**Formatting**: black + isort (automatic via hooks)

**Type Hints**: Required for all public APIs
```python
def process(data: Path, *, validate: bool = True) -> Result:
    """Process data file with optional validation."""
    ...
```

**Docstrings**: Google style
```python
def calculate_metrics(data: pd.DataFrame) -> dict[str, float]:
    """Calculate performance metrics from data.

    Args:
        data: DataFrame with columns 'timestamp', 'value', 'label'

    Returns:
        Dictionary with keys: 'accuracy', 'precision', 'recall', 'f1'

    Raises:
        ValueError: If required columns are missing
    """
```

**Error Messages**: Include context + expected format + link
```python
if not data_file.exists():
    raise ValueError(
        f"File not found: {data_file}\n"
        f"Expected JSON/CSV format. See docs/data-format.md"
    )
```

### JavaScript/TypeScript

**Formatting**: prettier (automatic via hooks)

**Type Safety**: Use TypeScript for new code
```typescript
interface Config {
  apiKey: string;
  endpoint: string;
  retryAttempts?: number;
}

export async function fetchData(config: Config): Promise<Data> {
  // ...
}
```

---

## Testing Requirements

### Test-Driven Development (TDD)

**ALWAYS write tests FIRST** (enforced by workflow):

1. **Test-master writes failing tests**
2. **Implementer makes tests pass**
3. **Never modify tests during implementation**

### Coverage Requirements

- **Minimum**: 80% coverage (enforced by `auto_enforce_coverage.py`)
- **Target**: 90%+ for core logic
- **Measurement**: Automatic on file write

### Test Organization

```
tests/
├── unit/          # Unit tests (fast, isolated)
├── integration/   # Integration tests (slower, e2e)
└── fixtures/      # Test data and fixtures
```

---

## Security Standards

### Secrets Management

**NEVER commit secrets**:
```bash
# ❌ BAD: Hardcoded secret
API_KEY = "sk-1234567890abcdef"

# ✅ GOOD: Environment variable
import os
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable required")
```

**Use .env files** (gitignored):
```bash
# .env (NEVER commit this!)
API_KEY=sk-1234567890abcdef
DATABASE_URL=postgresql://user:pass@localhost/db
```

### Input Validation

Always validate and sanitize user input:
```python
from pathlib import Path

def read_user_file(file_path: str) -> str:
    """Safely read user-provided file path."""
    # Validate path
    path = Path(file_path).resolve()
    allowed_dir = Path("/data/uploads").resolve()

    if not path.is_relative_to(allowed_dir):
        raise ValueError(f"Path outside allowed directory: {path}")

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return path.read_text()
```

---

## Git Workflow

### Branch Strategy

- **main**: Production-ready code
- **feature/***: Feature branches (merge via PR)
- **hotfix/***: Critical bug fixes

### Commit Messages

Follow conventional commits:
```bash
feat: Add webhook handling system
fix: Resolve race condition in async tests
docs: Update README with new installation steps
refactor: Simplify authentication logic
test: Add integration tests for user API
chore: Bump dependency versions
```

### Before Committing

**Automatic via hooks**:
- ✅ Code formatted (black, isort, prettier)
- ✅ Tests run and pass
- ✅ Coverage checked (80%+ minimum)
- ✅ Security scan passed

**If hooks fail**:
```bash
# See detailed error
git commit

# Fix issues
# ... make fixes ...

# Retry
git add .
git commit

# Emergency bypass (use sparingly!)
git commit --no-verify
```

---

## Documentation Standards

### When to Update Docs

**Update documentation when**:
- API changes (functions, classes, interfaces)
- New features added
- Breaking changes introduced
- Architecture decisions made

### File Organization

```
docs/
├── sessions/       # Session logs (auto-generated)
├── research/       # Research findings (from researcher agent)
├── adr/           # Architecture Decision Records
└── guides/        # User guides and tutorials
```

### README Updates

**The doc-master agent automatically updates**:
- README.md (when features added)
- CHANGELOG.md (all changes)
- API documentation (when signatures change)

---

## Plugin System

### Installing This Plugin

```bash
# Add marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install autonomous-dev
/plugin install autonomous-dev
```

### Plugin Structure

```
plugins/
└── autonomous-dev/
    ├── plugin.json          # Plugin metadata
    ├── README.md           # Plugin documentation
    ├── agents/             # 7 specialized agents
    │   ├── researcher.md
    │   ├── planner.md
    │   ├── test-master.md
    │   ├── implementer.md
    │   ├── reviewer.md
    │   ├── security-auditor.md
    │   └── doc-master.md
    └── skills/             # 6 core skills
        ├── python-standards/
        ├── testing-guide/
        ├── security-patterns/
        ├── documentation-guide/
        ├── research-patterns/
        └── engineering-standards/
```

---

## Common Tasks

### Adding a New Feature

```bash
# 1. Check alignment with goals
cat .claude/PROJECT.md | grep -A 5 "## GOALS"

# 2. Describe feature to Claude
# Claude will automatically:
# - Research patterns (researcher)
# - Create plan (planner)
# - Write tests (test-master)
# - Implement code (implementer)
# - Review quality (reviewer)
# - Scan security (security-auditor)
# - Update docs (doc-master)

# 3. Review session log
cat docs/sessions/$(ls -t docs/sessions/ | head -1)

# 4. Clear context for next feature
/clear
```

### Running Tests Manually

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_auth.py

# With coverage
pytest --cov=src --cov-report=html
```

### Checking Security

```bash
# Manual security scan
python hooks/security_scan.py src/

# Check for secrets
git secrets --scan
```

---

## Troubleshooting

### "Context budget exceeded"

**Solution**:
```bash
/clear
# Then retry
```

### "Feature doesn't align with PROJECT.md"

**Cause**: Feature doesn't serve project goals

**Solution**:
1. Check goals: `cat .claude/PROJECT.md | grep GOALS`
2. Either: Modify feature to align
3. Or: Update PROJECT.md if strategic direction changed

### "Agent can't use tool X"

**Cause**: Tool restrictions enforced for security

**Solution**: This is intentional. If genuinely needed:
```bash
# Check current tools
head -10 plugins/autonomous-dev/agents/[agent].md

# Add tool if needed (carefully!)
vim plugins/autonomous-dev/agents/[agent].md
# Add to tools: [...] list
```

### "Tests failing after auto-format"

**Cause**: Formatting changed code structure

**Solution**:
```bash
# Re-stage formatted files
git add .

# Commit will trigger tests again
git commit
```

---

## Performance Tips

### Context Management

- Use `/clear` after each feature
- Keep session files, not full content in context
- Monitor `docs/sessions/` for audit trail

### Hook Performance

**Auto-format**: < 1 second
**Auto-test**: 2-5 seconds (only related tests)
**Auto-coverage**: Included in test time
**Security scan**: ~5 seconds

**Total overhead per feature**: ~10 seconds (worth it!)

---

## Contributing

### Adding New Agents

1. Create `plugins/autonomous-dev/agents/new-agent.md`
2. Follow existing agent structure (frontmatter + instructions)
3. Add minimal required tools
4. Test thoroughly

### Adding New Skills

1. Create `plugins/autonomous-dev/skills/new-skill/SKILL.md`
2. Document patterns and best practices
3. Test with relevant agents

### Adding New Hooks

1. Create `hooks/new_hook.py`
2. Add to `.claude/settings.local.json`
3. Test with file operations

---

## Support & Resources

### Documentation

- **Project goals**: [.claude/PROJECT.md](.claude/PROJECT.md)
- **Plugin docs**: [plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md)
- **Session logs**: `docs/sessions/`
- **Research findings**: `docs/research/`

### Session Tracking

```bash
# Create session log
python scripts/session_tracker.py agent_name "message"

# View latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### Backup & Rollback

```bash
# Backups created during updates
ls -la .claude/*.backup

# Restore if needed
cp .claude/settings.local.json.backup .claude/settings.local.json
```

---

## Philosophy

### Automation > Reminders > Hope

Automate repetitive tasks so you focus on creative work. Use hooks, scripts, agents to enforce quality automatically.

### Research First, Test Coverage Required

- Always research before implementing (researcher agent)
- Always write tests first (test-master agent)
- Always document changes (doc-master agent)
- Make quality automatic, not optional

### Context is Precious

- Clear context after features
- Use session files for communication
- Stay under 8K tokens per feature
- Scale to 100+ features

---

**Last Updated**: 2025-10-19
**Next Review**: 2025-11-19

**This file contains project-specific instructions. For universal best practices, see [~/.claude/CLAUDE.md](~/.claude/CLAUDE.md).**
