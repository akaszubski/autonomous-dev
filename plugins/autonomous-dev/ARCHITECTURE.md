# Plugin Architecture

**Last Updated**: 2025-10-26
**Plugin**: autonomous-dev v2.3.1
**Purpose**: Document Python infrastructure and component relationships

---

## Overview

The autonomous-dev plugin uses a **hybrid architecture**:

1. **Markdown Layer** (User-Facing)
   - Agents: AI specialists that execute tasks
   - Commands: Slash commands users invoke
   - Hooks: Lifecycle automation

2. **Python Layer** (Infrastructure)
   - Orchestration: Workflow coordination and agent invocation
   - Validation: GenAI-powered quality gates
   - Automation: PR creation, health checks, setup wizards

3. **Integration Layer**
   - Commands invoke Python scripts via Bash tool
   - Python scripts invoke agents via Task tool
   - Hooks trigger Python validation automatically

---

## Component Map

### Markdown Components (User-Facing)

```
plugins/autonomous-dev/
├── agents/ (12 total)
│   ├── Core Workflow (8):
│   │   ├── orchestrator.md        - Master coordinator + PROJECT.md gatekeeper
│   │   ├── researcher.md          - Web research and pattern finding
│   │   ├── planner.md             - Architecture and design planning
│   │   ├── test-master.md         - TDD test writing
│   │   ├── implementer.md         - Code implementation
│   │   ├── reviewer.md            - Code quality review
│   │   ├── security-auditor.md    - Security scanning
│   │   └── doc-master.md          - Documentation updates
│   │
│   └── Utility (4):
│       ├── alignment-validator.md - PROJECT.md validation for Python orchestrator
│       ├── commit-message-generator.md - Generate conventional commits
│       ├── pr-description-generator.md - Generate PR descriptions
│       └── project-progress-tracker.md - Track PROJECT.md progress
│
├── commands/ (8 active)
│   ├── auto-implement.md      - Autonomous feature implementation
│   ├── align-project.md       - PROJECT.md alignment validation
│   ├── setup.md               - Plugin setup wizard
│   ├── test.md                - Run all tests
│   ├── status.md              - Project status overview
│   ├── health-check.md        - Component validation
│   ├── sync-dev.md            - Development sync (plugin authors)
│   └── uninstall.md           - Plugin removal
│
└── hooks/ (15 total)
    ├── Core (7):
    │   ├── detect_feature_request.py     - Auto-trigger orchestrator
    │   ├── validate_project_alignment.py - PROJECT.md gatekeeper
    │   ├── enforce_file_organization.py  - Standard structure
    │   ├── auto_format.py                - Code formatting
    │   ├── auto_test.py                  - Run relevant tests
    │   ├── security_scan.py              - Secret detection
    │   └── validate_docs_consistency.py  - Doc sync validation
    │
    └── Optional (8):
        ├── auto_add_to_regression.py
        ├── auto_enforce_coverage.py
        ├── auto_fix_docs.py
        ├── auto_generate_tests.py
        ├── auto_tdd_enforcer.py
        ├── auto_track_issues.py
        ├── auto_update_docs.py
        └── detect_doc_changes.py
```

### Python Infrastructure (~250KB)

#### Core Orchestration

**lib/workflow_coordinator.py** (34KB, 958 lines)
- **Purpose**: Python-based workflow orchestration (experimental)
- **Responsibilities**:
  - Validate PROJECT.md alignment (via alignment-validator agent)
  - Create workflow artifacts
  - Invoke 8-agent pipeline sequentially
  - Monitor progress and handle errors
  - Generate final reports and commits
- **Entry Points**: Called by `/auto-implement` command
- **Status**: Experimental - not yet fully integrated with agent-based orchestrator
- **Dependencies**: agent_invoker, project_md_parser, artifacts, logging_utils

**lib/orchestrator.py** (920 bytes)
- **Purpose**: Backward compatibility re-exports
- **Note**: Refactored into smaller modules, kept for legacy imports

**lib/agent_invoker.py** (8.5KB, 230 lines)
- **Purpose**: Agent invocation factory
- **Responsibilities**:
  - Invoke agents via Task tool (Claude Code native)
  - Pass context and prompts to agents
  - Handle agent errors and timeouts
  - Support parallel and sequential invocation
- **Used By**: workflow_coordinator, commands
- **Key Methods**: `invoke(agent_name, workflow_id, prompt, context)`

#### Validation & Quality

**lib/genai_validate.py** (33KB, 1,060 lines)
- **Purpose**: GenAI-powered validation framework
- **Responsibilities**:
  - UX quality validation (goal alignment, friction points, error handling)
  - Architecture validation (PROJECT.md drift, principle compliance)
  - Test quality assessment
  - Generate comprehensive reports with scores
- **Entry Points**: `/test-complete`, `/test-uat-genai`, `/test-architecture`
- **Key Functions**:
  - `validate_ux_quality()` - Score user experience (0-10)
  - `validate_architecture()` - Check PROJECT.md alignment (%)
  - `generate_validation_report()` - Comprehensive findings

**lib/health_check.py** (8.7KB, 271 lines)
- **Purpose**: Plugin component validation
- **Responsibilities**:
  - Validate agents exist and are loadable
  - Validate hooks have correct structure
  - Validate commands have implementations
  - Check Python dependencies
- **Entry Point**: `/health-check` command
- **Returns**: Component status + issue count

#### Artifact & State Management

**lib/artifacts.py** (11KB, 359 lines)
- **Purpose**: Workflow artifact management
- **Responsibilities**:
  - Create workflow directories (`.claude/artifacts/{workflow_id}/`)
  - Store agent outputs, plans, test results
  - Manage artifact lifecycle
  - Generate artifact summaries
- **Used By**: workflow_coordinator, agents
- **Storage**: `.claude/artifacts/` (gitignored)

**lib/checkpoint.py** (11KB, 352 lines)
- **Purpose**: Workflow checkpoint management
- **Responsibilities**:
  - Save workflow state at key points
  - Enable resuming interrupted workflows
  - Track completed vs pending steps
  - Rollback on failures
- **Used By**: workflow_coordinator
- **Storage**: `.claude/checkpoints/` (gitignored)

**lib/session_tracker.py** (2.1KB)
- **Purpose**: Session logging for context management
- **Responsibilities**:
  - Log agent actions to `docs/sessions/`
  - Keep context under 8K tokens per feature
  - Provide session summaries
- **Used By**: All agents when completing work
- **Output**: `docs/sessions/{timestamp}-session.md`

#### Automation & Integration

**lib/pr_automation.py** (11KB, 365 lines)
- **Purpose**: GitHub PR automation
- **Responsibilities**:
  - Generate PR descriptions (via pr-description-generator agent)
  - Create PRs with `gh pr create`
  - Link to PROJECT.md progress
  - Auto-assign reviewers
- **Entry Point**: `/pr-create` command
- **Dependencies**: pr-description-generator agent, gh CLI

**lib/search_utils.py** (16KB, 562 lines)
- **Purpose**: Codebase search utilities
- **Responsibilities**:
  - Search for patterns (Grep wrapper)
  - Find files by glob (Glob wrapper)
  - Semantic code search
  - Cache results for performance
- **Used By**: researcher, planner, implementer agents
- **Note**: Simplifies agent tool usage

**lib/logging_utils.py** (12KB, 382 lines)
- **Purpose**: Structured logging for workflows
- **Components**:
  - `WorkflowLogger`: Structured workflow logs
  - `WorkflowProgressTracker`: Track pipeline progress
  - `format_duration()`: Human-readable times
- **Used By**: workflow_coordinator, commands
- **Output**: `.claude/logs/` (gitignored)

**lib/project_md_parser.py** (5.0KB, 137 lines)
- **Purpose**: PROJECT.md parsing
- **Responsibilities**:
  - Extract GOALS, SCOPE, CONSTRAINTS sections
  - Validate PROJECT.md structure
  - Convert to structured dict
- **Used By**: workflow_coordinator, alignment-validator
- **Returns**: `{goals: [], scope: {in: [], out: []}, constraints: []}`

#### User Scripts

**scripts/setup.py** (16KB, 485 lines)
- **Purpose**: Interactive setup wizard
- **Responsibilities**:
  - Configure hooks (ask which to enable)
  - Setup GitHub integration
  - Create PROJECT.md from template
  - Install dependencies
- **Entry Point**: `/setup` command
- **Interactive**: Asks user questions, shows progress

**scripts/health_check.py** (8.8KB, 265 lines)
- **Purpose**: User-facing health check
- **Responsibilities**:
  - Call lib/health_check.py
  - Format output for users
  - Suggest fixes for issues
- **Entry Point**: `/health-check` command

**scripts/sync_to_installed.py** (4.6KB, 160 lines)
- **Purpose**: Development sync utility
- **Responsibilities**:
  - Sync `plugins/autonomous-dev/` → `~/.claude/plugins/.../`
  - Enable testing changes without reinstall
  - Handle symlinks and file copies
- **Entry Point**: `/sync-dev` command
- **Audience**: Plugin developers only

**scripts/validate_commands.py** (3.7KB, 124 lines)
- **Purpose**: Command validation
- **Responsibilities**:
  - Check all commands have `## Implementation` section
  - Validate frontmatter structure
  - Report invalid commands
- **Entry Point**: Pre-commit hook
- **Used By**: enforce_file_organization.py hook

---

## Architecture Patterns

### Two Orchestration Systems

The plugin currently has **two parallel orchestration systems**:

#### 1. Agent-Based Orchestrator (Intended)

```
User: "/auto-implement feature"
  ↓
orchestrator agent
  ├─ Validates PROJECT.md alignment
  ├─ Coordinates agents via Task tool
  └─ Manages context budget
  ↓
researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master
```

**Characteristics**:
- Pure agent-based (no Python infrastructure)
- Native Claude Code integration
- Simple and clean
- **Status**: Intended direction

#### 2. Python-Based Orchestrator (Experimental)

```
User: "/auto-implement feature"
  ↓
lib/workflow_coordinator.py
  ├─ Validates alignment via alignment-validator agent
  ├─ Creates artifacts (.claude/artifacts/)
  ├─ Invokes agents via lib/agent_invoker.py
  ├─ Tracks progress via lib/logging_utils.py
  └─ Manages checkpoints via lib/checkpoint.py
  ↓
[Same 7-agent pipeline]
```

**Characteristics**:
- Python infrastructure with agent invocation
- More features (artifacts, checkpoints, logging)
- More complex
- **Status**: Experimental - marked in `/auto-implement.md`

**Why Both Exist**: Transition in progress. Python system provides features not yet in agent-based system (artifacts, checkpoints, detailed logging). Once agent-based system is feature-complete, Python orchestrator may be deprecated.

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│ COMMANDS (Markdown)                                         │
│  /auto-implement, /align-project, /test-complete, etc.     │
└────────────────────┬────────────────────────────────────────┘
                     │ (invoke via Bash)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ USER SCRIPTS (Python)                                       │
│  scripts/setup.py, scripts/health_check.py                 │
└────────────────────┬────────────────────────────────────────┘
                     │ (import)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ CORE LIBRARIES (Python)                                     │
│                                                              │
│  ┌──────────────────┐        ┌─────────────────────┐       │
│  │ workflow_        │───────→│ agent_invoker      │       │
│  │ coordinator      │        │  (Task tool)       │       │
│  └──────┬───────────┘        └─────────────────────┘       │
│         │                              │                    │
│         ├──────────────┬───────────────┼───────────┐       │
│         ↓              ↓               ↓           ↓       │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐ ┌──────────┐ │
│  │ project_ │   │ artifacts│   │ logging_ │ │checkpoint│ │
│  │ md_parser│   │          │   │ utils    │ │          │ │
│  └──────────┘   └──────────┘   └──────────┘ └──────────┘ │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │ genai_validate   │    │ pr_automation    │             │
│  └──────────────────┘    └──────────────────┘             │
│                                                              │
└────────────────────┬────────────────────────────────────────┘
                     │ (invoke via Task tool)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ AGENTS (Markdown)                                           │
│  orchestrator, researcher, planner, test-master, etc.      │
└─────────────────────────────────────────────────────────────┘
```

---

## Entry Points

### How Commands Invoke Python

Commands use the Bash tool to call Python scripts:

```markdown
# Example: /health-check command

## Implementation

Run health check:
- Use: Bash
- Command: `python scripts/health_check.py`
- Output: Component status report
```

### How Python Invokes Agents

Python scripts use `agent_invoker.py` to call agents via Task tool:

```python
from lib.agent_invoker import AgentInvoker

invoker = AgentInvoker()
result = invoker.invoke(
    agent_name='alignment-validator',
    workflow_id='workflow_123',
    prompt='Validate: add dark mode feature',
    context={'project_md_path': '/path/to/PROJECT.md'}
)
```

### How Agents Log Sessions

Agents use `session_tracker.py` to log actions:

```bash
python scripts/session_tracker.py researcher "Found 3 similar patterns in codebase"
```

Output: `docs/sessions/20251026-143022-session.md`

---

## Development Guide

### Adding a New Agent

1. **Create agent markdown**: `agents/new-agent.md`
2. **Follow pattern**: 50-100 lines, clear mission, minimal guidance
3. **Register**: No registration needed (auto-discovered)
4. **Test**: `/health-check` will validate structure

### Adding a New Command

1. **Create command markdown**: `commands/new-command.md`
2. **Frontmatter**: Include `description`, `argument-hint` (optional)
3. **Implementation section**: REQUIRED - command fails without it
4. **Test**: Run command, check for execution
5. **Validate**: Pre-commit hook checks for `## Implementation`

### Adding Python Infrastructure

1. **Location**: Add to `lib/` for libraries, `scripts/` for user-facing
2. **Dependencies**: Document in module docstring
3. **Naming**: Use `snake_case.py` for modules
4. **Imports**: Use absolute imports (`from lib.artifacts import ...`)
5. **Update ARCHITECTURE.md**: Document new component

### Testing Changes

**Plugin Authors** (developing the plugin itself):
1. Edit: `plugins/autonomous-dev/`
2. Sync: `/sync-dev` (faster) OR reinstall plugin (complete)
3. Test: Use commands as users would
4. Commit: Standard git workflow

**Plugin Users** (using the plugin):
1. Install: `/plugin install autonomous-dev`
2. Use: Commands just work
3. Update: Uninstall → restart → reinstall → restart

---

## Known Issues & Decisions

### Issue #10: Experimental Python Orchestrator

**Status**: Open
**Problem**: Two parallel orchestration systems
**Options**:
- A) Complete Python orchestrator → production-ready
- B) Deprecate Python orchestrator → pure agent-based
- C) Integrate Python as implementation detail

**Current**: Marked experimental, both systems functional

### Issue #17: Duplicate Agents (alignment-validator vs orchestrator)

**Status**: Deferred
**Problem**: Both do PROJECT.md validation
**Analysis**: Part of two different systems (Python vs agent-based)
**Decision**: Deferred until Issue #10 resolved

### Issue #12: Python Infrastructure Documentation

**Status**: Resolved in this document
**Problem**: ~250KB undocumented Python code
**Solution**: This ARCHITECTURE.md

---

## Performance Considerations

### Context Budget Management

**Target**: <8K tokens per feature

**Strategy**:
- Keep agents short (50-100 lines)
- Log to session files (not context)
- Use `/clear` after each feature
- Avoid loading large files into context

**Measured**:
- Agent prompts: 500-1,000 tokens (per agent)
- Codebase exploration: 2,000-3,000 tokens
- Working memory: 2,000-3,000 tokens
- Buffer: 1,000-2,000 tokens

### Execution Speed

**Targets**:
- `/health-check`: <5 seconds
- `/test`: <60 seconds
- `/auto-implement`: 20-30 minutes
- Pre-commit hooks: <10 seconds

**Bottlenecks**:
- GenAI validation (2-5 minutes per validation)
- Agent invocation overhead (Task tool)
- Network latency (Claude API calls)

---

## Security Considerations

### Agent Permissions (Principle of Least Privilege)

**Read-only agents**: researcher, planner, reviewer, security-auditor, alignment-validator
**Write agents**: test-master (tests), implementer (code), doc-master (docs)
**Admin agents**: orchestrator (Task tool, coordinates all)

### Secret Management

- **Scanning**: `hooks/security_scan.py` checks for hardcoded secrets
- **Storage**: Use `.env` files (gitignored)
- **GitHub**: Use `gh` CLI (reads from `~/.config/gh/`)
- **Never**: Hardcode API keys in code or agents

### Hook Security

- **Exit codes**: 0 (allow), 1 (warn), 2 (block)
- **Validation**: All inputs validated before execution
- **Sandboxing**: Hooks run in same environment as Claude Code
- **Logging**: All hook executions logged (`.claude/logs/`)

---

## Future Directions

### Planned Improvements

1. **Resolve Python orchestrator status** (Issue #10)
   - Decision needed: Complete, deprecate, or integrate
   - Impacts: alignment-validator consolidation, artifact system, checkpointing

2. **Simplify utility agents** (Issue #4 follow-up)
   - pr-description-generator: 283 lines → ~70 lines target
   - project-progress-tracker: 266 lines → ~70 lines target

3. **Unified orchestration** (post-Issue #10)
   - Single orchestration path
   - Clear agent vs Python boundaries
   - Simplified mental model

### Plugin Roadmap

- **v2.4.0** (current): Documentation accuracy fixes
- **v2.5.0** (next): Resolve experimental status + Python orchestrator decision
- **v3.0.0** (future): Unified orchestration, simplified architecture

---

**This document is the source of truth for Python infrastructure. Update when adding/removing components.**

**Last Updated**: 2025-10-26
**Maintainer**: akaszubski
**Related Issues**: #10 (experimental status), #11 (PROJECT.md sync - resolved), #12 (this document), #17 (duplicate agents - deferred)
