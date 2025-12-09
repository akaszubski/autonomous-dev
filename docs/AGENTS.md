# Agent Architecture

**Last Updated**: 2025-12-09 (Added model tier strategy - Issue #108)
**Agent Count**: 20 specialists (Tier 1: 8, Tier 2: 10, Tier 3: 2)
**Location**: `plugins/autonomous-dev/agents/`

This document describes the complete agent architecture, including core workflow agents, utility agents, model tier assignments, and their skill integrations.

---

## Overview

The autonomous-dev plugin uses 20 specialized agents with active skill integration (GitHub Issue #35, #58, #59). Each agent has specific responsibilities and references relevant skills for enhanced decision-making.

---

## Model Tier Strategy (Issue #108)

Agent model assignments are optimized for cost-performance balance based on task complexity.

### Tier 1: Haiku (8 agents)

Fast, cost-effective models for pattern matching and structured output:

- **researcher**: Pattern discovery and codebase search
- **reviewer**: Code quality checks against style guide
- **doc-master**: Documentation synchronization
- **commit-message-generator**: Conventional commit formatting
- **alignment-validator**: PROJECT.md validation
- **project-progress-tracker**: Progress tracking and reporting
- **sync-validator**: Development environment sync validation
- **pr-description-generator**: PR description formatting

**Use Case**: Tasks with clear patterns, structured output, or simple validation logic.

### Tier 2: Sonnet (10 agents)

Balanced reasoning for implementation and planning tasks:

- **implementer**: Code implementation to make tests pass
- **test-master**: TDD test generation with comprehensive coverage
- **planner**: Architecture and implementation planning
- **issue-creator**: GitHub issue creation with research
- **setup-wizard**: Interactive project setup
- **project-bootstrapper**: Project initialization and tech stack analysis
- **brownfield-analyzer**: Legacy codebase analysis
- **quality-validator**: Final validation orchestration
- **alignment-analyzer**: PROJECT.md conflict resolution
- **project-status-analyzer**: Project status assessment and health metrics

**Use Case**: Complex implementation, test design, and planning requiring strong reasoning capabilities.

### Tier 3: Opus (2 agents)

Maximum depth reasoning for critical analysis:

- **security-auditor**: OWASP security scanning and vulnerability detection
- **advisor**: Critical thinking, trade-off analysis, risk identification

**Use Case**: Critical security and architectural decisions requiring maximum reasoning depth.

### Rationale

- **Tier 1 (Haiku)**: Cost optimization for well-defined tasks (40-60% cost reduction vs Opus)
- **Tier 2 (Sonnet)**: Sweet spot for development work requiring both speed and reasoning
- **Tier 3 (Opus)**: Reserved for high-risk decisions where reasoning depth is critical

**Performance Impact**: Optimized tier assignments reduce costs by 40-60% while maintaining quality standards across all workflows.

---

## Core Workflow Agents (9)

These agents execute the main autonomous development workflow. The orchestrator was deprecated in v3.2.2 - Claude now coordinates directly.

### researcher

**Purpose**: Web research for patterns and best practices
**Model**: Haiku (Tier 1 - cost optimized for pattern matching)
**Skills**: research-patterns
**Execution**: Step 1 of /auto-implement workflow

### planner

**Purpose**: Architecture planning and design
**Model**: Sonnet (Tier 2 - balanced reasoning for complex planning)
**Skills**: architecture-patterns, api-design, database-design, testing-guide
**Execution**: Step 2 of /auto-implement workflow

### test-master

**Purpose**: TDD specialist (writes tests first)
**Model**: Sonnet (Tier 2 - strong reasoning for comprehensive test design)
**Skills**: testing-guide, security-patterns
**Execution**: Step 3 of /auto-implement workflow
**Context Isolation**: Runs in separate context. Writes tests to disk for implementer. See [TDD-CONTEXT-ISOLATION.md](TDD-CONTEXT-ISOLATION.md).

### implementer

**Purpose**: Code implementation (makes tests pass)
**Model**: Sonnet (Tier 2 - balanced reasoning for code implementation)
**Skills**: python-standards, observability
**Execution**: Step 4 of /auto-implement workflow
**Context Isolation**: Runs in separate context. Reads only test files from disk, not test-master's reasoning. See [TDD-CONTEXT-ISOLATION.md](TDD-CONTEXT-ISOLATION.md).

### reviewer

**Purpose**: Quality gate (code review)
**Model**: Haiku (Tier 1 - cost optimized for pattern-based code review)
**Skills**: code-review, consistency-enforcement, python-standards
**Execution**: Step 5 of /auto-implement workflow (parallel validation)

### security-auditor

**Purpose**: Security scanning and vulnerability detection
**Model**: Opus (Tier 3 - maximum depth for critical security analysis)
**Skills**: security-patterns, python-standards
**Execution**: Step 5 of /auto-implement workflow (parallel validation)

### doc-master

**Purpose**: Documentation synchronization
**Model**: Haiku (Tier 1 - cost optimized for structured documentation updates)
**Skills**: documentation-guide, consistency-enforcement, git-workflow, cross-reference-validation, documentation-currency
**Execution**: Step 5 of /auto-implement workflow (parallel validation)

### advisor

**Purpose**: Critical thinking and validation (v3.0+)
**Model**: Opus (Tier 3 - maximum depth for risk analysis and trade-offs)
**Skills**: semantic-validation, advisor-triggers, research-patterns
**Execution**: Checkpoint validation during workflow

### quality-validator

**Purpose**: GenAI-powered feature validation (v3.0+)
**Model**: Sonnet (Tier 2 - balanced reasoning for comprehensive validation)
**Skills**: testing-guide, code-review
**Execution**: Final validation step (triggers SubagentStop hook)

---

## Utility Agents (11)

These agents provide specialized functionality for alignment, git operations, and project management.

### alignment-validator

**Purpose**: PROJECT.md alignment checking
**Model**: Haiku (Tier 1 - cost optimized for validation)
**Skills**: semantic-validation, file-organization
**Command**: Invoked during /auto-implement for feature alignment

### commit-message-generator

**Purpose**: Conventional commit generation
**Model**: Haiku (Tier 1 - cost optimized for structured formatting)
**Skills**: git-workflow, code-review
**Hook**: Auto-invoked by auto_git_workflow.py (SubagentStop lifecycle)

### pr-description-generator

**Purpose**: Pull request descriptions
**Model**: Haiku (Tier 1 - cost optimized for structured formatting)
**Skills**: github-workflow, documentation-guide, code-review
**Command**: Invoked during PR creation workflow

### issue-creator

**Purpose**: Generate well-structured GitHub issue descriptions (v3.10.0+, GitHub #58)
**Model**: Sonnet (Tier 2 - balanced reasoning for structured issues)
**Skills**: github-workflow, documentation-guide, research-patterns
**Command**: /create-issue

### brownfield-analyzer

**Purpose**: Analyze brownfield projects for retrofit readiness (v3.11.0+, GitHub #59)
**Model**: Sonnet (Tier 2 - balanced reasoning for complex analysis)
**Skills**: research-patterns, semantic-validation, file-organization, python-standards
**Command**: /align-project-retrofit

### project-progress-tracker

**Purpose**: Track progress against goals
**Model**: Haiku (Tier 1 - cost optimized for tracking and updates)
**Skills**: project-management
**Command**: /status

### alignment-analyzer

**Purpose**: Detailed alignment analysis
**Model**: Sonnet (Tier 2 - balanced reasoning for conflict resolution)
**Skills**: research-patterns, semantic-validation, file-organization
**Command**: /align-project

### project-bootstrapper

**Purpose**: Tech stack detection and setup (v3.0+)
**Model**: Sonnet (Tier 2 - balanced reasoning for tech analysis)
**Skills**: research-patterns, file-organization, python-standards
**Command**: /setup

### setup-wizard

**Purpose**: Intelligent setup - analyzes tech stack, recommends hooks (v3.1+)
**Model**: Sonnet (Tier 2 - balanced reasoning for interactive setup)
**Skills**: research-patterns, file-organization
**Command**: /setup

### project-status-analyzer

**Purpose**: Real-time project health - goals, metrics, blockers (v3.1+)
**Model**: Sonnet (Tier 2 - balanced reasoning for health assessment)
**Skills**: project-management, code-review, semantic-validation
**Command**: /status

### sync-validator

**Purpose**: Smart dev sync - detects conflicts, validates compatibility (v3.1+)
**Model**: Haiku (Tier 1 - cost optimized for validation and sync)
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
