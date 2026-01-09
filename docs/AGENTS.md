# Agent Architecture

**Last Updated**: 2025-12-16
**Location**: `plugins/autonomous-dev/agents/`

This document describes the agent architecture, including core workflow agents, utility agents, model tier assignments, and their skill integrations.

---

## Overview

8 active agents with skill integration. Each agent has specific responsibilities and references relevant skills.

**Active Agents**: researcher-local, planner, test-master, implementer, reviewer, security-auditor, doc-master, issue-creator

---

## Model Tier Strategy (Issue #108, Updated #147)

Agent model assignments optimized for cost-performance balance (8 active agents):

### Tier 1: Haiku (3 agents)

Fast, cost-effective for pattern matching:

- **researcher-local**: Search codebase patterns
- **reviewer**: Code quality checks
- **doc-master**: Documentation sync

### Tier 2: Sonnet (4 agents)

Balanced reasoning for implementation:

- **implementer**: Code implementation
- **test-master**: TDD test generation
- **planner**: Architecture planning
- **issue-creator**: GitHub issue creation

### Tier 3: Opus (1 agent)

Maximum depth for security:

- **security-auditor**: OWASP security scanning

### Rationale

- **Tier 1 (Haiku)**: Cost optimization for well-defined tasks (40-60% cost reduction vs Opus)
- **Tier 2 (Sonnet)**: Sweet spot for development work requiring both speed and reasoning
- **Tier 3 (Opus)**: Reserved for high-risk security decisions

**Performance Impact**: Optimized tier assignments reduce costs by 40-60% while maintaining quality.

---

## Token Budget Audit (Issue #175)

**Target**: Under 3,000 tokens per agent
**Last Audit**: 2026-01-01
**Total Agents**: 21
**Total Tokens**: 27,274
**Average**: 1,298 tokens/agent

### Agents by Token Count

| Status | Agent | Tokens | Notes |
|--------|-------|--------|-------|
| ❌ | setup-wizard | 6,520 | 2.17x over target - needs optimization |
| ⚠️ | project-status-analyzer | 2,341 | Under target but large |
| ⚠️ | sync-validator | 2,314 | Under target but large |
| ✅ | brownfield-analyzer | 1,792 | OK |
| ✅ | project-progress-tracker | 1,728 | OK |
| ✅ | doc-master | 1,634 | OK |
| ✅ | security-auditor | 1,231 | OK |
| ✅ | issue-creator | 1,113 | OK |
| ✅ | researcher-local | 1,104 | OK |
| ✅ | planner | 1,025 | OK |
| ✅ | researcher | 898 | OK |
| ✅ | implementer | 830 | OK |
| ✅ | test-master | 677 | OK |
| ✅ | reviewer | 623 | OK |
| ✅ | project-bootstrapper | 581 | OK |
| ✅ | advisor | 561 | OK |
| ✅ | pr-description-generator | 549 | OK |
| ✅ | alignment-analyzer | 470 | OK |
| ✅ | commit-message-generator | 444 | OK |
| ✅ | alignment-validator | 421 | OK |
| ✅ | quality-validator | 418 | OK |

### Summary

- **20/21 agents** (95%) are under the 3K token target ✅
- **1 agent** (setup-wizard) exceeds target and needs optimization
- **Run audit**: `python3 scripts/measure_agent_tokens.py --baseline`

---

## Core Workflow Agents (7 active + 1 utility)

These agents execute the main autonomous development workflow.

### researcher-local

**Purpose**: Search codebase for existing patterns and similar implementations
**Model**: Haiku (Tier 1 - cost optimized for pattern matching)
**Skills**: research-patterns
**Tools**: Read, Grep, Glob (local filesystem access only)
**Execution**: Step 1A of /auto-implement workflow (parallel with researcher-web)
**Output Format**: JSON schema with similar_implementations array plus implementation_guidance and testing_guidance sections
  - **similar_implementations**: Existing patterns matching the feature request
  - **implementation_guidance**: Reusable functions, import patterns, error handling patterns
    - reusable_functions: Functions with file location, purpose, and usage examples
    - import_patterns: Recommended imports with context for when to use
    - error_handling_patterns: Error handling approaches with file/line references
  - **testing_guidance**: Testing patterns found in the codebase
    - test_file_patterns: Structure of tests, pytest patterns, common fixtures
    - edge_cases_to_test: Edge cases identified in similar code with expected behavior
    - mocking_patterns: Mocking approaches used in existing tests with examples
**Research Persistence** (Issue #151): Optionally persists significant research findings to `docs/research/` for future reuse

### researcher-web

**Purpose**: Research web best practices and industry standards
**Model**: Haiku (Tier 1 - cost optimized for pattern matching)
**Skills**: research-patterns, documentation-guide
**Tools**: WebSearch, WebFetch (external research only)
**Execution**: Step 1B of /auto-implement workflow (parallel with researcher-local)
**Output Format**: JSON schema with antipatterns array plus implementation_guidance and testing_guidance sections
  - **antipatterns**: Industry-standard pitfalls and how to avoid them
  - **implementation_guidance**: Best practices for design and performance
    - design_patterns: Patterns like Factory, Strategy, Decorator with usage context and examples
    - performance_tips: Optimization techniques with impact assessment
    - library_integration_tips: Best practices for popular libraries (requests, async, etc)
  - **testing_guidance**: Industry best practices for testing
    - testing_frameworks: Framework recommendations (pytest, unittest) with key features
    - coverage_recommendations: Coverage targets by area (error handling 100%, happy path 80%)
    - testing_antipatterns: Common testing mistakes and preferred alternatives
**Research Persistence** (Issue #151): Persists substantial research findings (2+ best practices, 3+ sources) to `docs/research/` with SCREAMING_SNAKE_CASE naming (e.g., JWT_AUTHENTICATION_RESEARCH.md)
**Related**: Deprecated researcher.md combined functionality split into local/web agents (Issue #128); output expanded in Issue #130

### planner

**Purpose**: Architecture planning and design
**Model**: Sonnet (Tier 2 - balanced reasoning for complex planning)
**Skills**: architecture-patterns, api-design, database-design, testing-guide
**Execution**: Step 2 of /auto-implement workflow (after merging research findings from Step 1.1)

### test-master

**Purpose**: TDD specialist (writes tests first)
**Model**: Sonnet (Tier 2 - strong reasoning for comprehensive test design)
**Skills**: testing-guide, security-patterns
**Execution**: Step 3 of /auto-implement workflow
**Research Context**: Receives testing_guidance from researcher-local and researcher-web (Issue #130)
  - Uses test_file_patterns, edge_cases_to_test, mocking_patterns from researchers
  - Falls back to Grep/Glob pattern discovery if research context not provided
**Context Isolation**: Runs in separate context. Writes tests to disk for implementer. See [TDD-CONTEXT-ISOLATION.md](TDD-CONTEXT-ISOLATION.md).

### implementer

**Purpose**: Code implementation (makes tests pass)
**Model**: Sonnet (Tier 2 - balanced reasoning for code implementation)
**Skills**: python-standards, observability
**Execution**: Step 4 of /auto-implement workflow
**Research Context**: Receives implementation_guidance from researcher-local and researcher-web (Issue #130)
  - Uses reusable_functions, import_patterns, error_handling_patterns from researchers
  - Uses design_patterns, performance_tips, library_integration_tips from web research
  - Falls back to Grep/Glob pattern discovery if research context not provided
**Context Isolation**: Runs in separate context. Reads only test files from disk, not test-master's reasoning. See [TDD-CONTEXT-ISOLATION.md](TDD-CONTEXT-ISOLATION.md).

### reviewer

**Purpose**: Quality gate (code review)
**Model**: Haiku (Tier 1 - cost optimized for pattern-based code review)
**Skills**: code-review, consistency-enforcement, python-standards
**Execution**: Step 5 of /auto-implement workflow (parallel validation - 60% faster with Phase 7 optimization)

### security-auditor

**Purpose**: Security scanning and vulnerability detection
**Model**: Opus (Tier 3 - maximum depth for critical security analysis)
**Skills**: security-patterns, python-standards
**Execution**: Step 5 of /auto-implement workflow (parallel validation - 60% faster with Phase 7 optimization)

### doc-master

**Purpose**: Documentation synchronization and research management
**Model**: Haiku (Tier 1 - cost optimized for structured documentation updates)
**Skills**: documentation-guide, consistency-enforcement, git-workflow, cross-reference-validation, documentation-currency
**Execution**: Step 5 of /auto-implement workflow (parallel validation - 60% faster with Phase 7 optimization)
**Research Documentation** (Issue #151): Validates and maintains research documentation in `docs/research/` - enforces naming conventions, format standards, README sync, and parity validation

### advisor

**Purpose**: Critical thinking and validation (v3.0+)
**Model**: Opus (Tier 3 - maximum depth for risk analysis and trade-offs)
**Skills**: semantic-validation, advisor-triggers, research-patterns
**Execution**: Checkpoint validation during workflow

### quality-validator

**Purpose**: GenAI-powered feature validation (v3.0+)
**Model**: Sonnet (Tier 2 - balanced reasoning for comprehensive validation)
**Skills**: testing-guide, code-review
**Execution**: Step 6 of /auto-implement workflow (Final validation step, triggers SubagentStop hook)

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

## Agent-Skill Integration

All 8 active agents reference relevant skills via `skills:` frontmatter (Issue #35, #143, #147). Claude Code 2.0 auto-loads skills when agents are spawned.

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

- [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) - Overall system architecture
- [SKILLS-AGENTS-INTEGRATION.md](SKILLS-AGENTS-INTEGRATION.md) - Agent-skill mapping
- [commands/auto-implement.md](/plugins/autonomous-dev/commands/auto-implement.md) - Workflow coordination
- [agents/](/plugins/autonomous-dev/agents/) - Individual agent prompts
