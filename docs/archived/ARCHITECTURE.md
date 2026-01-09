> **DEPRECATED**: This file has been consolidated into [ARCHITECTURE-OVERVIEW.md](../ARCHITECTURE-OVERVIEW.md)
> **Archived**: 2026-01-09 (Issue #208)
> **Reason**: Consolidation to prevent documentation drift

# Architecture Overview

**Last Updated**: 2025-11-15

This document explains how autonomous-dev's two-layer architecture works.

---

## Two-Layer Architecture

autonomous-dev combines **deterministic enforcement** (hooks) with **intelligent assistance** (agents):

### Layer 1: Hook-Based Enforcement (Automatic, 100% Reliable)

**42 Python hooks** run automatically to enforce quality gates:

**What hooks do**:
- Run before/after tool calls (Read, Write, Bash, etc.)
- Block operations that violate rules
- No LLM reasoning - pure Python logic
- 100% deterministic and reliable

**Key hooks**:
- `validate_project_alignment.py` - Blocks features outside PROJECT.md scope
- `security_scan.py` - Detects secrets and vulnerabilities
- `auto_format.py` - Formats code (black, isort, prettier)
- `auto_test.py` - Runs tests automatically
- `enforce_tdd.py` - Validates tests written before code
- `auto_git_workflow.py` - Automatic commit/push/PR after `/auto-implement`

**Why hooks?**
- **Guaranteed enforcement** - Can't be skipped or reasoned away
- **Automatic** - Run without explicit commands
- **Fast** - Python execution, no LLM latency
- **Consistent** - Same rules for every developer

**See also**: [docs/HOOKS.md](HOOKS.md) for complete hook inventory and lifecycle details

### Layer 2: Agent Intelligence (Command-Driven, Adaptive)

**20 AI agents** provide intelligent assistance via explicit commands:

**What agents do**:
- Invoked via slash commands (e.g., `/auto-implement`, `/research`)
- Use LLM reasoning to understand context
- Research patterns, plan architecture, review code
- Adaptive to project-specific patterns

**Core Workflow Agents** (9):
1. **researcher** - Web research for patterns and best practices
2. **planner** - Architecture planning and design
3. **test-master** - TDD specialist (writes tests first)
4. **implementer** - Code implementation (makes tests pass)
5. **reviewer** - Quality gate (code review)
6. **security-auditor** - Security scanning and vulnerability detection
7. **doc-master** - Documentation synchronization
8. **advisor** - Critical thinking and validation
9. **quality-validator** - GenAI-powered feature validation

**Utility Agents** (11):
- alignment-validator, commit-message-generator, pr-description-generator
- issue-creator, brownfield-analyzer, project-progress-tracker
- alignment-analyzer, project-bootstrapper, setup-wizard
- project-status-analyzer, sync-validator

**Why agents?**
- **Intelligent** - Adapt to project-specific patterns
- **Researched** - Find best practices before implementing
- **Explainable** - Show reasoning in output
- **Flexible** - Individual commands or full workflow

**See also**: [docs/AGENTS.md](AGENTS.md) for complete agent inventory and skill integration details, or agent prompts in `plugins/autonomous-dev/agents/`

---

## Skills: Progressive Disclosure System

**22 active skills** provide specialized knowledge without context bloat:

**How it works**:
1. Skills auto-activate based on task keywords
2. Only skill metadata stays in context (~50 tokens each)
3. Full content (10,000+ tokens) loads only when needed
4. Scales to 100+ skills without performance issues

**Active Skills** (organized by category):
- **Core Development** (7): api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns, error-handling-patterns
- **Workflow & Automation** (6): git-workflow, github-workflow, project-management, documentation-guide, agent-output-formats, skill-integration
- **Code & Quality** (4): python-standards, observability, consistency-enforcement, file-organization
- **Validation & Analysis** (5): research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers

**Benefits**:
- **Scalable** - Add 100+ skills without context bloat
- **Efficient** - Only load what's needed
- **Consistent** - Agents reference standardized patterns
- **Documented** - Each skill has comprehensive guides

**See also**: [docs/SKILLS-AGENTS-INTEGRATION.md](SKILLS-AGENTS-INTEGRATION.md)

---

## Libraries: Reusable Python Utilities

**25 shared libraries** for security, validation, automation, installation, and brownfield retrofit:

**Core Libraries** (11):
1. security_utils.py - Security validation and audit logging
2. project_md_updater.py - Atomic PROJECT.md updates
3. version_detector.py - Semantic version comparison
4. orphan_file_cleaner.py - Orphaned file detection
5. sync_dispatcher.py - Intelligent sync orchestration
6. validate_marketplace_version.py - Version validation CLI
7. plugin_updater.py - Interactive plugin update
8. update_plugin.py - CLI interface for updates
9. hook_activator.py - Automatic hook activation
10. validate_documentation_parity.py - Documentation consistency
11. auto_implement_git_integration.py - Automatic git operations

**Additional Core Libraries** (5):
12. batch_state_manager.py - State-based auto-clearing for /batch-implement
13. github_issue_fetcher.py - GitHub issue fetching via gh CLI
14. path_utils.py - Dynamic PROJECT_ROOT detection and path resolution
15. validation.py - Tracking infrastructure security validation
16. agent_invoker.py - Subagent invocation and management

**Installation Libraries** (4) - NEW in v3.29.0:
17. file_discovery.py - Comprehensive file discovery with exclusion patterns
18. copy_system.py - Structure-preserving file copying with permission handling
19. installation_validator.py - Coverage validation and missing file detection
20. install_orchestrator.py - Coordinates complete installation workflows

**Brownfield Retrofit Libraries** (6):
21. brownfield_retrofit.py - Phase 0: Project analysis
22. codebase_analyzer.py - Phase 1: Deep codebase analysis
23. alignment_assessor.py - Phase 2: Gap assessment
24. migration_planner.py - Phase 3: Migration planning
25. retrofit_executor.py - Phase 4: Step-by-step execution
26. retrofit_verifier.py - Phase 5: Verification

**Design Pattern**: Progressive enhancement (string → path → whitelist) for graceful error recovery.

**See also**: [docs/LIBRARIES.md](LIBRARIES.md)

---

## PROJECT.md-First Philosophy

**Everything starts with PROJECT.md** - your project's strategic direction documented once, enforced automatically.

### What is PROJECT.md?

A single markdown file at project root with **four required sections**:

```markdown
# PROJECT.md

## GOALS
What success looks like:
- "Build a scalable REST API"
- "Create user-friendly dashboard"

## SCOPE
What's IN and OUT:
- IN: User authentication, payments
- OUT: Mobile apps, analytics

## CONSTRAINTS
Technical and business limits:
- "Must support Python 3.11+"
- "PostgreSQL for data persistence"

## ARCHITECTURE
How the system works:
- "FastAPI backend + React frontend"
- "Microservices with Kubernetes"
```

### Why PROJECT.md-First?

✅ **Single source of truth** - One file defines strategic direction
✅ **Automatic enforcement** - Every feature validates BEFORE work begins
✅ **Zero scope creep** - Features outside SCOPE are blocked
✅ **Team alignment** - Humans and AI work toward same goals
✅ **Survives tools** - Markdown at root survives plugin updates

### How It Works

1. Create PROJECT.md (at project root)
2. Run `/auto-implement "feature"`
3. Command validates alignment:
   - Does feature serve GOALS? ✓
   - Is feature IN SCOPE? ✓
   - Respects CONSTRAINTS? ✓
   - Aligns with ARCHITECTURE? ✓
4. If ANY check fails → BLOCK work
5. Feature proceeds ONLY if fully aligned

**Result**: Zero tolerance for scope drift. Strategic alignment guaranteed.

**See also**: [docs/MAINTAINING-PHILOSOPHY.md](MAINTAINING-PHILOSOPHY.md)

---

## Workflow: `/auto-implement` Pipeline

**Full SDLC automation in 8 steps**:

### Step 1: Alignment Validation
- Validate feature against PROJECT.md
- Check GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
- Block if misaligned

### Step 2: Research
- **researcher agent** searches for patterns
- Web research for best practices
- Security considerations
- Model: Haiku (optimized for speed)

### Step 3: Planning
- **planner agent** designs architecture
- Integration points, components, LOC estimates
- Uses architecture-patterns skill

### Step 4: TDD Tests
- **test-master agent** writes failing tests FIRST
- Unit tests for core logic
- Integration tests for workflows
- Uses testing-guide skill

### Step 5: Implementation
- **implementer agent** makes tests pass
- Follows existing patterns
- Uses python-standards skill

### Step 6: Parallel Validation (3 agents simultaneously)
- **reviewer** checks code quality
- **security-auditor** scans vulnerabilities
- **doc-master** updates documentation
- Execution: 60% faster via parallel tool calls

### Step 7: Quality Validation
- **quality-validator agent** verifies success
- Validates tests pass
- Checks documentation updated
- Confirms security standards met

### Step 8: Automatic Git Operations (optional, consent-based)
- **commit-message-generator agent** creates conventional commit
- Stages changes, commits, pushes
- Optionally creates PR
- Graceful degradation if prerequisites fail

**Performance Baseline**: 22-36 minutes (optimized via Haiku researcher, streamlined prompts, parallel validation)

**See also**: [docs/PERFORMANCE.md](PERFORMANCE.md)

---

## File Organization

**Standard project structure** (enforced via hooks):

```
your-project/
├── .claude/                  # Claude Code configuration
│   ├── PROJECT.md           # Strategic direction (REQUIRED)
│   ├── CLAUDE.md            # Development standards
│   ├── commands/            # Slash commands (18 total)
│   ├── agents/              # AI agent prompts (20 total)
│   ├── hooks/               # Automation hooks (42 total)
│   ├── skills/              # Progressive disclosure (22 total)
│   └── settings.json        # Plugin configuration
│
├── src/                     # Source code
├── tests/                   # Test files
├── docs/                    # Documentation
└── README.md                # Project overview
```

**Hooks enforce**:
- PROJECT.md exists at root
- Standard directory structure
- File naming conventions
- Documentation parity

**See also**: File organization skill in `plugins/autonomous-dev/skills/file-organization/`

---

## Design Principles

### 1. Automation > Reminders > Hope

**Automate** repetitive tasks so you focus on creative work. Use hooks, scripts, CI/CD to enforce quality automatically.

### 2. Research First, Test Coverage Required

Always research before implementing. Always write tests. Always document changes. Make quality automatic, not optional.

### 3. Context is Precious

- Clear context after features (`/clear`)
- Use session files for logs (not context)
- Stay under 8K tokens per feature
- Scale to 100+ features

### 4. Trust GenAI Where It Excels

**Use GenAI for** (agent layer):
- Pattern discovery and research
- Architecture planning
- Code quality review
- Documentation sync

**Use Python for** (hook layer):
- Deterministic validation
- Security checks
- File operations
- Process orchestration

### 5. Progressive Disclosure

Only load content when needed:
- Skills: Full content on-demand (10,000+ tokens → 50 tokens metadata)
- Agents: Reference skills instead of inline docs
- Libraries: Import only when used

**See also**: [docs/MAINTAINING-PHILOSOPHY.md](MAINTAINING-PHILOSOPHY.md), [docs/ANTI-BLOAT-PHILOSOPHY.md](ANTI-BLOAT-PHILOSOPHY.md)

---

## Performance Optimization

**Cumulative improvements** (Issues #63, #64, #72, #46):

- **Phase 4**: Haiku model for researcher (3-5 min saved)
- **Phase 5**: Streamlined prompts (2-4 min saved)
- **Phase 6**: Profiling infrastructure (measurement framework)
- **Phase 7**: Parallel validation checkpoint (60% faster validation)
- **Phase 8**: Agent output format cleanup (~2,900 tokens saved, 11.7% reduction)
- **Phase 8.5**: Profiler integration (real-time performance analysis)
- **Phase 9**: Model downgrade strategy (investigative)

**Total**: 5-10 minutes saved per workflow (15-35% faster)

**See also**: [docs/PERFORMANCE.md](PERFORMANCE.md)

---

## Security

**Multi-layer security**:

- **Input Validation**: All file paths validated (CWE-22, CWE-59)
- **Audit Logging**: All operations logged to `logs/security_audit.log`
- **No Secrets in Logs**: Credentials never exposed
- **Subprocess Safety**: List args (no shell=True) prevents injection
- **Permission Batching**: 80% reduction in permission prompts (opt-in)

**See also**: [docs/SECURITY.md](SECURITY.md)

---

## Learn More

- **[PHILOSOPHY.md](PHILOSOPHY.md)** - Why PROJECT.md-first works
- **[WORKFLOWS.md](WORKFLOWS.md)** - Real-world usage examples
- **[REFERENCE.md](REFERENCE.md)** - Complete command reference
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Contributing guide

**For detailed implementation**: See `plugins/autonomous-dev/` directory
