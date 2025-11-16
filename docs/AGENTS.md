# Agent Architecture

**Last Updated**: 2025-11-16
**Agent Count**: 20 specialists
**Location**: `plugins/autonomous-dev/agents/`

This document describes the complete agent architecture, including core workflow agents, utility agents, and their skill integrations.

---

## Overview

The autonomous-dev plugin uses 20 specialized agents with active skill integration (GitHub Issue #35, #58, #59). Each agent has specific responsibilities and references relevant skills for enhanced decision-making.

---

## Core Workflow Agents (9)

These agents execute the main autonomous development workflow. The orchestrator was deprecated in v3.2.2 - Claude now coordinates directly.

### researcher

**Purpose**: Web research for patterns and best practices
**Model**: Haiku (optimized for speed)
**Skills**: research-patterns
**Execution**: Step 1 of /auto-implement workflow

### planner

**Purpose**: Architecture planning and design
**Skills**: architecture-patterns, api-design, database-design, testing-guide
**Execution**: Step 2 of /auto-implement workflow

### test-master

**Purpose**: TDD specialist (writes tests first)
**Skills**: testing-guide, security-patterns
**Execution**: Step 3 of /auto-implement workflow

### implementer

**Purpose**: Code implementation (makes tests pass)
**Skills**: python-standards, observability
**Execution**: Step 4 of /auto-implement workflow

### reviewer

**Purpose**: Quality gate (code review)
**Skills**: code-review, consistency-enforcement, python-standards
**Execution**: Step 5 of /auto-implement workflow (parallel validation)

### security-auditor

**Purpose**: Security scanning and vulnerability detection
**Skills**: security-patterns, python-standards
**Execution**: Step 5 of /auto-implement workflow (parallel validation)

### doc-master

**Purpose**: Documentation synchronization
**Skills**: documentation-guide, consistency-enforcement, git-workflow, cross-reference-validation, documentation-currency
**Execution**: Step 5 of /auto-implement workflow (parallel validation)

### advisor

**Purpose**: Critical thinking and validation (v3.0+)
**Skills**: semantic-validation, advisor-triggers, research-patterns
**Execution**: Checkpoint validation during workflow

### quality-validator

**Purpose**: GenAI-powered feature validation (v3.0+)
**Skills**: testing-guide, code-review
**Execution**: Final validation step (triggers SubagentStop hook)

---

## Utility Agents (11)

These agents provide specialized functionality for alignment, git operations, and project management.

### alignment-validator

**Purpose**: PROJECT.md alignment checking
**Skills**: semantic-validation, file-organization
**Command**: Invoked during /auto-implement for feature alignment

### commit-message-generator

**Purpose**: Conventional commit generation
**Skills**: git-workflow, code-review
**Hook**: Auto-invoked by auto_git_workflow.py (SubagentStop lifecycle)

### pr-description-generator

**Purpose**: Pull request descriptions
**Skills**: github-workflow, documentation-guide, code-review
**Command**: Invoked during PR creation workflow

### issue-creator

**Purpose**: Generate well-structured GitHub issue descriptions (v3.10.0+, GitHub #58)
**Skills**: github-workflow, documentation-guide, research-patterns
**Command**: /create-issue

### brownfield-analyzer

**Purpose**: Analyze brownfield projects for retrofit readiness (v3.11.0+, GitHub #59)
**Skills**: research-patterns, semantic-validation, file-organization, python-standards
**Command**: /align-project-retrofit

### project-progress-tracker

**Purpose**: Track progress against goals
**Skills**: project-management
**Command**: /status

### alignment-analyzer

**Purpose**: Detailed alignment analysis
**Skills**: research-patterns, semantic-validation, file-organization
**Command**: /align-project

### project-bootstrapper

**Purpose**: Tech stack detection and setup (v3.0+)
**Skills**: research-patterns, file-organization, python-standards
**Command**: /setup

### setup-wizard

**Purpose**: Intelligent setup - analyzes tech stack, recommends hooks (v3.1+)
**Skills**: research-patterns, file-organization
**Command**: /setup

### project-status-analyzer

**Purpose**: Real-time project health - goals, metrics, blockers (v3.1+)
**Skills**: project-management, code-review, semantic-validation
**Command**: /status

### sync-validator

**Purpose**: Smart dev sync - detects conflicts, validates compatibility (v3.1+)
**Skills**: consistency-enforcement, file-organization, python-standards, security-patterns
**Command**: /sync

---

## Orchestrator Removal (v3.2.2)

**Historical Note**: The "orchestrator" agent was removed because it created a logical impossibility - it was Claude coordinating Claude.

**Problem**: When `/auto-implement` invoked the orchestrator agent, it just loaded orchestrator.md as Claude's system prompt, but it was still the same Claude instance making decisions. This allowed Claude to skip agents by reasoning they weren't needed.

**Solution**: Moved all coordination logic directly into `commands/auto-implement.md`. Now Claude explicitly coordinates the 7-agent workflow without pretending to be a separate orchestrator.

**Result**: Same checkpoints, simpler architecture, more reliable execution.

**Archive**: See `agents/archived/orchestrator.md` for history.

---

## Agent-Skill Integration

All 20 agents explicitly reference relevant skills for enhanced decision-making (Issue #35). This prevents hallucination while maintaining scalability through progressive disclosure.

**How It Works**:
1. Each agent's prompt includes a "Relevant Skills" section
2. Skills auto-activate based on task keywords
3. Claude loads full SKILL.md content only when relevant
4. Context stays efficient while providing specialized knowledge

**See Also**: [SKILLS-AGENTS-INTEGRATION.md](SKILLS-AGENTS-INTEGRATION.md) for complete mapping table.

---

## Parallel Validation (Phase 7)

Three agents execute in parallel during Step 5 of /auto-implement:

- **reviewer**: Code quality validation
- **security-auditor**: Security scanning
- **doc-master**: Documentation updates

**Performance**: Sequential 5 minutes → Parallel 2 minutes (60% faster)

**Implementation**: Three Task tool calls in single response enables parallel execution

---

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) - Overall system architecture
- [SKILLS-AGENTS-INTEGRATION.md](SKILLS-AGENTS-INTEGRATION.md) - Agent-skill mapping
- [commands/auto-implement.md](/plugins/autonomous-dev/commands/auto-implement.md) - Workflow coordination
- [agents/](/plugins/autonomous-dev/agents/) - Individual agent prompts
