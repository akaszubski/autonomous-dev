# Agent-Skill Integration: Best Practices for Claude Code 2024-2025

**Date**: 2025-10-27
**Status**: Research & Assessment Complete
**Source**: Official Anthropic documentation, API guides, and engineering best practices

---

## Executive Summary

**The Good News**: v2.5 guidance that discouraged skills is **OUTDATED**. Skills are not an anti-pattern—they're now a **core capability** with a mature architecture.

**What Changed**: The problem v2.5 solved was about **skill discovery overhead** and **context bloat**. New "progressive disclosure" architecture solves this elegantly, making agents and skills work together beautifully.

**Recommendation for autonomous-dev**:
- ✅ **Keep and enhance skills** - They're first-class citizens in Claude Code 2.0+
- ✅ **Integrate skills into agent system prompts** - Agents should know about and use available skills
- ✅ **Use progressive disclosure pattern** - Load metadata, then details as needed
- ✅ **This fixes the context budget problem** that plagued v2.5

---

## Part 1: What Skills Actually Are

### Definition
A **Skill** is a modular package containing:
- `SKILL.md` file with structured instructions
- Supporting files (scripts, templates, reference docs)
- Optional executable code (Python, Bash)
- Tool access declarations

Skills are **not plugins or extensions**—they're **reusable knowledge packages** that Claude loads dynamically.

### How They Work

Skills operate through **model invocation**, not explicit delegation:

```
User: "Help me analyze sales data"
    ↓
Claude's system prompt contains skill metadata
    ↓
Claude recognizes "data analysis skill" is relevant
    ↓
Claude reads full SKILL.md content (only when needed!)
    ↓
Claude uses skill instructions to complete task
```

**Key difference from v2.5**: Skills were previously loaded all-at-once. Now they use **progressive disclosure**.

---

## Part 2: Progressive Disclosure Architecture (THE FIX)

### The v2.5 Problem
```
Old approach (broken):
┌─────────────────────────────────────┐
│ System Prompt                        │
├─────────────────────────────────────┤
│ Skill 1 (5KB of instructions)       │
│ Skill 2 (4KB of instructions)       │
│ Skill 3 (6KB of instructions)       │
│ ... (N skills × K bytes)            │
│ = Context bloat, slow inference      │
└─────────────────────────────────────┘

Result: Can only load 3-5 skills before context exhaustion
```

### The New Architecture (ELEGANT SOLUTION)
```
Progressive Disclosure (3 levels):

LEVEL 1: Metadata (always in context)
┌─────────────────────────────┐
│ System Prompt (500 bytes)   │
├─────────────────────────────┤
│ skill_1: "Data analysis"    │
│ skill_2: "Code review"      │
│ skill_3: "Security audit"   │
│ ... (up to 100+ skills)     │
│ ≈ 2-5KB total              │
└─────────────────────────────┘

LEVEL 2: Full Skill (loaded when relevant)
Claude: "I need data analysis for this task"
    ↓
Load: skill_1/SKILL.md (5-20KB)
    ↓
Claude uses detailed instructions

LEVEL 3: Supporting Files (loaded on-demand)
Claude references: "See analysis-templates.md"
    ↓
Load: skill_1/analysis-templates.md (10KB)
    ↓
Claude uses templates
```

**Result**: Unlimited skills in metadata, only active ones in context

### Issue #110: Skills 500-Line Refactoring (v3.41.0)

**Implementation**: All 28 skills refactored to satisfy 500-line official limit.

**Refactoring Pattern** (16 skills refactored):
- **Compact SKILL.md**: Core skill content compressed to 87-315 lines (50-95% reduction)
- **Docs Subdirectories**: Detailed guides moved to skill/docs/ (6,000+ lines of content)
- **Structure**:
  - SKILL.md: Quick reference, trigger words, key concepts
  - docs/detailed-guide-1.md through N: Comprehensive guides with examples
  - docs/: Code examples, edge cases, reference material

**Results**:
- All 28 skills under 500-line limit (100% compliance)
- System prompt 70-80% smaller for skill content
- Detailed content still available via docs/ subdirectories
- Agents load compact metadata, detailed content on-demand
- Scales to 100+ skills without context bloat

**Example Refactoring** (documentation-guide):
- Before: 1,847 lines (single SKILL.md file)
- After: 87 lines (SKILL.md) + 4 detailed guides in docs/
- Reduction: 95% smaller file, 4 detailed guides preserved

**Key Benefit**: Progressive disclosure in practice—compact metadata for context efficiency, detailed content for on-demand learning.

### How It Solves the Problem

| Problem | v2.5 | v2024+ |
|---------|------|--------|
| Skills in context | All loaded (bloat) | Only active (efficient) |
| Number of skills | 3-5 max | 50-100+ possible |
| Context overhead | Huge | Minimal |
| Discovery | Manual listing | Automatic from metadata |
| Scale | Doesn't scale | Scales well |

---

## Part 3: Current Best Practices (Anthropic Official)

### 1. Scope Skills Narrowly

**BAD** ❌
```yaml
name: "General Development"
description: "Helps with any development task"
# Too broad, Claude won't know when to use it
```

**GOOD** ✅
```yaml
name: "Python Performance Analysis"
description: "Analyze Python code for performance bottlenecks, generate flame graphs, profile memory usage. Use when optimizing Python code or investigating slow functions."
# Specific triggers: flame graphs, profiling, memory analysis
```

### 2. Write Trigger-Specific Descriptions

Claude discovers skills via description scanning. Be explicit:

**TRIGGER WORDS TO INCLUDE**:
- File types: ".xlsx files", "JSON config", "Docker containers"
- Operations: "pivot tables", "authentication", "caching"
- Problems: "slow queries", "memory leaks", "security audit"
- Domains: "data analysis", "infrastructure", "security"

**Example**:
```
"Database query optimization. Analyze slow queries, generate execution
plans, suggest indexes. Use when debugging N+1 problems, optimizing
joins, or working with PostgreSQL/MySQL performance issues."
```

### 3. Use Progressive Disclosure in SKILL.md

Structure your skills for progressive loading:

```markdown
# Python Performance Analysis Skill

[Brief intro - Claude reads this first]

## Quick Reference
- List key operations
- Common patterns

## Deep Dive Sections
### Section 1: Flame Graph Analysis
### Section 2: Memory Profiling
### Section 3: Database Query Optimization

## Supporting Files
- See: analysis-templates.md
- See: benchmark-scripts.md
```

Claude loads only what's needed. Organizing sections lets Claude request specific parts.

### 4. Keep Supporting Files Separate

```
skills/python-performance/
├── SKILL.md (2-3KB overview)
├── flame-graph-guide.md (5KB, loaded when flame graphs mentioned)
├── memory-profiling.md (4KB, loaded for memory issues)
├── scripts/
│   ├── profile.py (executable by Claude)
│   └── analyze-perf.py
└── templates/
    ├── benchmark-template.py
    └── report-template.md
```

Claude progressively loads files as needed. No context bloat.

### 5. Include Executable Code Where Appropriate

```yaml
tools: ["bash", "python"]  # Skills can execute deterministic operations
```

Skills can include Python/Bash that Claude executes. Useful for:
- **Sorting algorithms** (cheaper than token generation)
- **Data transformations** (deterministic operations)
- **Environment commands** (checking installed tools)
- **File operations** (reading large files)

### 6. Restrict Tool Access Appropriately

```yaml
allowed-tools: ["read", "write", "bash"]  # This skill only needs these
# Don't grant "bash" to a documentation skill
```

Minimal tool access:
- Reduces attack surface
- Guides Claude toward appropriate actions
- Makes tool access explicit in system prompt

---

## Part 3.5: Agent-to-Skill Mapping (autonomous-dev Implementation)

### Complete Agent-Skill Integration Map

**Implementation Status**: All 18 agents now include "Relevant Skills" sections in their prompts (GitHub Issue #35)

#### Core Workflow Agents (9 agents, 22 skill references)

| Agent | Function | Relevant Skills | Pattern |
|-------|----------|-----------------|---------|
| **researcher** | Web research, pattern discovery | research-patterns | Learns from existing implementations and best practices |
| **planner** | Architecture design, planning | architecture-patterns, api-design, database-design, testing-guide | Designs systems using established patterns |
| **test-master** | TDD, test generation | testing-guide, security-patterns | Writes secure, comprehensive tests first |
| **implementer** | Code implementation | python-standards, observability, documentation-guide | Optimizes performance, adds observability and documentation |
| **reviewer** | Code quality, anti-patterns | code-review, consistency-enforcement, python-standards, documentation-guide | Ensures code quality and documentation consistency |
| **security-auditor** | Vulnerability scanning, OWASP | security-patterns, python-standards | Detects security issues with pattern knowledge |
| **doc-master** | Documentation sync | documentation-guide, consistency-enforcement, git-workflow, cross-reference-validation, documentation-currency | Maintains accurate, consistent documentation |
| **advisor** | Critical thinking, validation | semantic-validation, advisor-triggers, research-patterns | Validates proposals against best practices |
| **quality-validator** | Feature validation | testing-guide, code-review | Ensures features meet quality standards |

#### Utility Agents (9 agents, 25 skill references)

| Agent | Function | Relevant Skills | Pattern |
|-------|----------|-----------------|---------|
| **alignment-validator** | PROJECT.md alignment | semantic-validation, file-organization | Validates alignment using semantic patterns |
| **alignment-analyzer** | Detailed alignment analysis | research-patterns, semantic-validation, file-organization, documentation-guide | Research-backed alignment and documentation analysis |
| **commit-message-generator** | Conventional commits | git-workflow, code-review | Follows git conventions, reviews changes |
| **pr-description-generator** | PR descriptions | github-workflow, documentation-guide, code-review | Professional PR documentation |
| **project-bootstrapper** | Tech stack detection | research-patterns, file-organization, python-standards, documentation-guide | Discovers project patterns and generates documentation |
| **setup-wizard** | Setup guidance | research-patterns, file-organization, documentation-guide | Analyzes tech stack and generates setup documentation |
| **project-progress-tracker** | Goal tracking | project-management | Assesses progress against SMART goals |
| **project-status-analyzer** | Project health | project-management, code-review, semantic-validation, documentation-guide | Holistic project health assessment with documentation |
| **issue-creator** | GitHub issue creation | github-workflow, documentation-guide, research-patterns | Creates well-structured GitHub issues with research |
| **sync-validator** | Environment sync | consistency-enforcement, file-organization, python-standards, security-patterns | Multi-layer synchronization validation |

#### Skill Coverage Summary

#### Skill Coverage Summary

**Total Unique Skills Referenced**: 21 of 21 available skills (100% coverage)

**New Skills (v3.14.0)**:
- **agent-output-formats** (Issue #72): Referenced by all 20 agents for standardized output formatting
- **error-handling-patterns** (Issue #64): Referenced by 22 libraries for standardized error handling

**Skills by Reference Count** (sorted by usage):
- **Ultra-High-Use Skills** (20-22 references): error-handling-patterns (22 libraries), agent-output-formats (20 agents)
- **High-Use Skills** (5+ agents): semantic-validation (3), file-organization (5), python-standards (5), research-patterns (4), code-review (5), project-management (2), testing-guide (3), security-patterns (3)
- **Medium-Use Skills** (2-9 agents): documentation-guide (9), consistency-enforcement (3), git-workflow (2)
- **Specialized Skills** (1 agent): github-workflow (1), advisor-triggers (1), cross-reference-validation (1), documentation-currency (1), database-design (1), api-design (1), architecture-patterns (1), observability (1)

**Agent-Skill Integration Details**:
- Core workflow agents (9 agents): 22 skill references + agent-output-formats references
- Utility agents (11 agents): 25 skill references + agent-output-formats references
- All 20 agents: Standardized output formats via agent-output-formats skill (Issue #72)
- All libraries (22 libraries): error-handling-patterns references

**Token Reduction Impact** (Issues #63, #64, #72):
- Agent prompts (Issues #63-64): ~7,500 tokens saved (15 agents × 500 tokens average)
- Library docstrings (Issues #63-64): ~3,000 tokens saved (22 libraries × 200 tokens average, net reduction)
- Agent output format cleanup (Issue #72): ~1,183 tokens saved (5 agents streamlined, 20 agents now reference skill)
- Combined total savings: ~11,683 tokens (20-28% reduction)
- Quality: Preserved via progressive disclosure (skills load on-demand)

#### Progressive Disclosure in Action

**Context Efficiency Example**:
```
Without Progressive Disclosure:
- Doc-master prompt would include full contents of 5 SKILL.md files
- Each SKILL.md: 5-20KB
- Total: 25-100KB loaded for every doc-master invocation
- Context overhead: Large, inefficient

With Progressive Disclosure (Current Implementation):
- Doc-master prompt includes: "Available skills: documentation-guide, consistency-enforcement, ..."
- Metadata only: ~200 bytes
- When doc-master tasks requires specialized knowledge (e.g., API docs):
  - Full documentation-guide SKILL.md loaded (5-20KB)
  - On-demand, only when needed
- Context overhead: Minimal (200 bytes vs 25-100KB)
```

#### Design Decisions

**Why Each Agent Has Specific Skills**:

1. **researcher**: Needs research-patterns to find established best practices
2. **planner**: Needs architecture-patterns, api-design, database-design, testing-guide for comprehensive system design
3. **test-master**: Needs testing-guide (core) + security-patterns (writes secure tests)
4. **implementer**: Needs python-standards (language) + observability (adds metrics/logging)
5. **reviewer**: Needs code-review (domain), consistency-enforcement (style), python-standards (language)
6. **security-auditor**: Needs security-patterns (domain) + python-standards (understands vulnerable patterns)
7. **doc-master**: Most skill-rich (5 skills) because documentation is cross-cutting concern
8. **advisor**: Needs semantic-validation (checks proposals), research-patterns (facts), advisor-triggers (recognizes when advice needed)
9. **quality-validator**: Needs testing-guide (test validation) + code-review (code quality)

### Skill Activation Pattern

**How Agents Discover and Use Skills**:

1. **Agent Prompt Includes Skill List**: Each agent sees available skills in its system prompt
2. **Claude Recognizes Task Type**: Agent receives task, recognizes which skills are relevant
3. **Progressive Loading**: Claude loads skill SKILL.md only when task requires it
4. **Skilled Execution**: Agent completes task using skill knowledge
5. **Efficient Context**: Unused skill content never loaded

**Example Workflow**:
```
User asks doc-master: "Update API documentation"
    ↓
doc-master sees: "Available skills: documentation-guide, consistency-enforcement, ..."
    ↓
Claude recognizes: "This is API documentation - need documentation-guide skill"
    ↓
Claude loads: documentation-guide/SKILL.md (only this skill)
    ↓
doc-master uses: Documentation patterns, formatting standards from SKILL.md
    ↓
Result: Professional API docs using established patterns
    ↓
Unused skills (git-workflow, etc.) never loaded to context
```

---

## Part 4: Agent-Skill Integration Patterns

### Pattern 1: Main Agent with Skill Access

```
User → Main Agent (orchestrator)
            ↓
        [Skill metadata in system prompt]
        ↓
        Recognizes: "This task needs Python Performance skill"
        ↓
        Loads: SKILL.md automatically
        ↓
        Uses skill instructions to complete task
```

**Best For**: Single coherent agent doing diverse work
**Example**: Orchestrator with access to 20 specialized skills

### Pattern 2: Sub-Agent Pipeline with Shared Skills

```
User → Orchestrator
    ↓
    Sub-Agent 1 (Researcher)
    [Skill: Web research, code pattern discovery]
        ↓
    Sub-Agent 2 (Planner)
    [Skill: Architecture patterns, TDD methodology]
        ↓
    Sub-Agent 3 (Implementer)
    [Skill: Code optimization, performance analysis]
        ↓
    Sub-Agent 4 (Reviewer)
    [Skill: Code review standards, security patterns]
```

**Best For**: Sequential workflow where each agent has specialized skills
**Example**: Feature implementation pipeline

### Pattern 3: Skill-Aware Agent Discovery

```
# Agent system prompt includes:

## Available Skills
- code-review: Analyze code quality, suggest improvements
- security-audit: Find vulnerabilities, compliance issues
- database-optimization: Query analysis, index suggestions
- documentation-guide: API docs, readme, changelog patterns

When appropriate, you may invoke sub-agents that specialize in these skills.
```

**Best For**: Intelligent delegation based on available expertise
**Example**: Advisor agent routing to specialist sub-agents

### Pattern 4: API Skills Container Model

```python
# When using Claude API (not just interactive)
messages = client.messages.create(
    model="claude-opus-4-1",
    max_tokens=4096,
    system=system_prompt,
    tools=[
        {
            "type": "skill",
            "skill": "python-optimization",
            "version": "latest"
        },
        {
            "type": "skill",
            "skill": "security-patterns",
            "version": "latest"
        }
    ],
    messages=messages
)

# Only these 2 skills loaded; can specify up to 8
```

**Best For**: Programmatic agent usage with precise skill control
**Example**: Automated CI/CD pipelines invoking specialized agents

---

## Part 5: Why Skills Work Well with Agents NOW

### The Three-Part Solution

**1. Model Capability**
- Modern Claude (opus-4.1+) understands structured skill metadata
- Can read and follow complex instructions
- Intelligently decides when to load full skill content

**2. Progressive Disclosure**
- Metadata in system prompt ≈ 2-5KB for 50+ skills
- Full skill content ≈ 5-20KB, loaded only when needed
- Supporting files loaded on-demand

**3. Tool Access Boundaries**
- Skills declare what tools they can access
- Claude respects boundaries
- Prevents inappropriate tool usage

**Result**: Agents can reliably use 20-50 specialized skills without context bloat

---

## Part 6: How This Applies to autonomous-dev

### Current State Analysis

**Skills Folder**: `plugins/autonomous-dev/skills/` (18 SKILL.md files)
- These are not "anti-pattern" anymore ✅
- They should be actively used by agents ✅
- They represent valuable distilled expertise ✅

### Recommended Architecture

```
autonomous-dev v3.1.0 (Agent-Skill Integration):

Main Agents (orchestrator, researcher, planner, etc.)
    ↓
[System prompt includes skill metadata - 2-5KB]
    ↓
Agents recognize relevant skills and load full SKILL.md
    ↓
Available Skills:
  - api-design (REST design, versioning)
  - architecture-patterns (design decisions, ADRs)
  - code-review (quality gates, patterns)
  - database-design (schemas, migrations, ORM)
  - documentation-guide (API docs, consistency)
  - git-workflow (commits, branching, PRs)
  - observability (logging, profiling, monitoring)
  - project-management (planning, goals, scope)
  - python-standards (PEP 8, type hints, docstrings)
  - security-patterns (API keys, input validation)
  - testing-guide (TDD, coverage, regression)
  ... (18 total)
```

### Implementation Strategy

1. **Keep all skills** - They're valuable expertise packages
2. **Update skill metadata** - Make sure descriptions are trigger-specific
3. **Add skills to agent prompts** - Let agents know what skills are available
4. **Use progressive disclosure** - Organize SKILL.md with overview + details
5. **Document skill-agent relationships** - Which agents use which skills

### Example: How orchestrator Could Use Skills

```yaml
# orchestrator.md system prompt

## Available Skills
You have access to the following specialized skill packages:
- api-design: Use when designing REST endpoints, versioning, error handling
- architecture-patterns: Use when making architectural decisions, creating ADRs
- code-review: Use to establish quality gates, review against patterns
- database-design: Use when designing schemas, planning migrations
- security-patterns: Use when reviewing security aspects, validating input handling
- testing-guide: Use when establishing test strategy, TDD patterns
... (all 18 skills)

## Delegation Pattern
When you recognize a task requires specialized expertise, you may:
1. Use the relevant skill directly (load SKILL.md for detailed guidance)
2. Delegate to a specialized sub-agent with that skill focus
```

---

## Part 7: Comparison: v2.5 vs v2024+ Architecture

### v2.5 (Anti-Pattern Guidance)
```
Problem: Skills loaded entirely into context
Result: Context bloat, can't scale
Decision: "Avoid skills"

Agents worked alone with tool access only
```

### v2024+ (Integrated Architecture)
```
Solution: Progressive disclosure (metadata + lazy loading)
Result: Unlimited skills, context-efficient
Decision: "Skills are core capability"

Agents + Skills = Powerful partnership
- Agents handle orchestration and decision-making
- Skills provide specialized knowledge when needed
```

---

## Part 8: Risk Assessment & Recommendations

### Is It Safe to Re-Enable Skills?
**YES** ✅

**Evidence**:
- Official Anthropic documentation recommends skills
- Progressive disclosure architecture eliminates v2.5 problems
- Modern Claude models handle skills reliably
- Thousands of users leveraging skills in production

### Action Items for autonomous-dev

**IMMEDIATE** (This session):
1. ✅ Document that skills are now best practice
2. ✅ Update CLAUDE.md to reflect current guidance
3. ✅ Audit existing skills for trigger-specific descriptions

**SHORT TERM** (Next iteration):
1. Update agent system prompts to reference available skills
2. Enhance skill metadata with specific trigger words
3. Organize SKILL.md files for progressive disclosure
4. Add skill relationships to agent documentation

**MEDIUM TERM** (Future releases):
1. Consider skill-based agent specialization
2. Implement skill versioning strategy
3. Create skill discovery/suggestion mechanism
4. Build skill testing framework

---

## Part 9: Specific Recommendations for autonomous-dev Skills

### Complete Skill Inventory (27 Active Skills - v3.26.0)

**Core Development (7 skills)**:
1. api-design - REST API design with versioning and error handling
2. architecture-patterns - System architecture and ADR creation
3. code-review - Code quality assessment and pattern detection
4. database-design - Database schema and modeling patterns
5. testing-guide - Test-driven development and testing patterns
6. security-patterns - Security implementation and vulnerability prevention
7. error-handling-patterns - Standardized error handling and validation

**Workflow & Automation (7 skills)** - v3.26.0 Addition:
8. git-workflow - Git operations and commit strategies
9. github-workflow - GitHub automation and PR workflows
10. project-management - Project tracking and goal management
11. documentation-guide - Documentation standards and best practices
12. agent-output-formats - Standardized agent output formatting
13. skill-integration - Skill discovery, composition, and progressive disclosure
14. skill-integration-templates - Skill reference syntax, action verbs, progressive disclosure usage (NEW v3.26.0)

**Code & Quality (4 skills)**:
15. python-standards - Python coding standards and best practices
16. observability - Logging, monitoring, and metrics patterns
17. consistency-enforcement - Code consistency and standardization
18. file-organization - Project structure and file organization

**Validation & Analysis (6 skills)** - v3.25.0 Addition:
19. research-patterns - Research methodology and pattern discovery
20. semantic-validation - Semantic analysis and validation patterns
21. cross-reference-validation - Documentation cross-reference checking
22. documentation-currency - Documentation freshness and synchronization
23. advisor-triggers - Critical thinking and advisory prompts
24. project-alignment-validation - Gap assessment, semantic validation, conflict resolution, alignment checklists (NEW v3.25.0)

**Library Design (3 skills)** - v3.24.1 Addition:
25. library-design-patterns - Progressive enhancement, two-tier architecture, security validation, docstring standards
26. state-management-patterns - JSON state persistence, atomic write operations, file locking patterns
27. api-integration-patterns - GitHub API integration, retry logic, subprocess security, command injection prevention



### Skill-Integration-Templates Skill Details (NEW v3.26.0 - Issue #72 Phase 8.6)

**Location**: `/plugins/autonomous-dev/skills/skill-integration-templates/`

**Purpose**: Standardized templates and patterns for integrating skills into agent prompts, reducing token overhead while maintaining clarity and consistency

**Contents**:
- **SKILL.md** (~50 lines) - Overview and quick reference with progressive disclosure keywords
- **Documentation Files (4)**:
  - `skill-reference-syntax.md` (~280 lines) - Standard syntax patterns for skill sections
  - `agent-action-verbs.md` (~320 lines) - Action verbs for different skill usage contexts
  - `progressive-disclosure-usage.md` (~240 lines) - How to use progressive disclosure effectively
  - `integration-best-practices.md` (~290 lines) - Best practices for skill integration patterns
- **Template Files (3)**:
  - `skill-section-template.md` (~120 lines) - Standard skill section template
  - `intro-sentence-templates.md` (~80 lines) - Introduction sentence variations
  - `closing-sentence-templates.md` (~60 lines) - Closing sentence variations
- **Example Files (3)**:
  - `planner-skill-section.md` (~90 lines) - Planner agent skill section example
  - `implementer-skill-section.md` (~85 lines) - Implementer agent skill section example
  - `minimal-skill-reference.md` (~45 lines) - Minimal reference example

**Total**: 11 files, ~1,200 tokens of integration patterns available on-demand

**Key Patterns**:
1. **Skill Reference Syntax**: Standardized format for "Relevant Skills" sections
2. **Action Verbs**: Context-appropriate verbs (Consult, Reference, Use, Apply)
3. **Progressive Disclosure**: Only show metadata in context, full content on-demand
4. **Integration Best Practices**: Consistent formatting across all agents

**Agents Using This Skill**:
All 20 agents now reference skill-integration-templates for standardized skill section formatting:
- **advisor** - Uses skill-reference-syntax.md for advisory skill references
- **alignment-analyzer** - Uses integration-best-practices.md for alignment skill formatting
- **alignment-validator** - Uses skill-section-template.md for validation skill structure
- **brownfield-analyzer** - Uses agent-action-verbs.md for brownfield analysis contexts
- **commit-message-generator** - Uses minimal-skill-reference.md for concise git skill references
- **doc-master** - Uses planner-skill-section.md as documentation skill reference model
- **implementer** - Uses implementer-skill-section.md for implementation skill guidance
- **issue-creator** - Uses skill-reference-syntax.md for issue creation skill formatting
- **planner** - Uses planner-skill-section.md for planning skill references
- **pr-description-generator** - Uses integration-best-practices.md for PR skill structure
- **project-bootstrapper** - Uses skill-section-template.md for bootstrap skill formatting
- **project-progress-tracker** - Uses skill-reference-syntax.md for tracking skill references
- **project-status-analyzer** - Uses integration-best-practices.md for status analysis formatting
- **quality-validator** - Uses agent-action-verbs.md for quality validation contexts
- **researcher** - Uses progressive-disclosure-usage.md for research skill optimization
- **reviewer** - Uses skill-reference-syntax.md for review skill references
- **security-auditor** - Uses integration-best-practices.md for security skill formatting
- **setup-wizard** - Uses skill-section-template.md for wizard skill structure
- **sync-validator** - Uses skill-reference-syntax.md for sync skill references
- **test-master** - Uses agent-action-verbs.md for testing skill contexts

**Token Reduction Impact**:
- **Before Phase 8.6**: ~21,755 tokens across all 20 agents
- **After Phase 8.6**: ~19,902 tokens across all 20 agents
- **Savings**: ~800 tokens (~3.5% reduction)
- **Progressive Disclosure**: ~1,200 tokens available on-demand, only ~50 tokens SKILL.md overhead

**Test Coverage**:
- **Unit Tests (23)**: Skill structure validation, documentation completeness, template coverage
- **Integration Tests (7)**: Skill integration workflow, pattern application validation
- **Test Files**: `tests/unit/skills/test_skill_integration_templates_skill.py`, `tests/integration/test_skill_integration_templates_workflow.py`

### Project-Alignment-Validation Skill Details (NEW v3.25.0 - Issue #72 Phase 8.7)

**Location**: `/plugins/autonomous-dev/skills/project-alignment-validation/`

**Purpose**: Standardized patterns for PROJECT.md alignment validation, gap assessment, and conflict resolution

**Contents**:
- **SKILL.md** (~50 lines) - Overview and quick reference
- **Documentation Files (4)**:
  - `gap-assessment-methodology.md` (~550 lines) - Comprehensive gap assessment framework
  - `semantic-validation-approach.md` (~480 lines) - Semantic validation methodology
  - `conflict-resolution-patterns.md` (~420 lines) - Conflict resolution strategies
  - `alignment-checklist.md` (~320 lines) - Alignment verification checklist
- **Template Files (3)**:
  - `gap-assessment-template.md` (~180 lines) - Gap assessment report template
  - `alignment-report-template.md` (~150 lines) - Alignment report template
  - `conflict-resolution-template.md` (~120 lines) - Conflict resolution guide template
- **Example Files (3)**:
  - `project-md-structure-example.md` (~280 lines) - Well-structured PROJECT.md example
  - `alignment-scenarios.md` (~320 lines) - Real-world alignment scenarios
  - `misalignment-examples.md` (~290 lines) - Common misalignment patterns and fixes

**Total**: 11 files, ~2,200 tokens of alignment validation patterns

**Key Patterns**:
1. **Gap Assessment**: Systematic comparison of documented vs actual project state
2. **Semantic Validation**: Deep validation beyond syntax (intent, scope, constraints)
3. **Conflict Resolution**: Strategies for handling competing requirements and priorities
4. **Alignment Checklists**: Verification procedures for PROJECT.md compliance

**Agents Using This Skill**:
- **alignment-validator** - Uses gap-assessment-methodology.md for validation strategy
- **alignment-analyzer** - Uses semantic-validation-approach.md for deep analysis
- **project-bootstrapper** - Uses alignment-checklist.md for initialization
- **brownfield-analyzer** - Uses gap-assessment-methodology.md for retrofit assessment
- **sync-validator** - Uses conflict-resolution-patterns.md for sync conflict handling

**Hooks Using This Skill**:
- **detect_feature_request.py** - Uses alignment-checklist.md to verify feature alignment
- **enforce_pipeline_complete.py** - Uses semantic-validation-approach.md to validate pipeline completion
- **validate_project_alignment.py** - Uses all patterns for comprehensive alignment validation
- **validate_documentation_alignment.py** - Uses alignment-checklist.md for documentation validation

**Libraries Using This Skill**:
- **project_md_updater.py** - References conflict-resolution-patterns.md for merge handling
- **alignment_assessor.py** - References gap-assessment-methodology.md and semantic-validation-approach.md
- **brownfield_retrofit.py** - References gap-assessment-methodology.md for assessment phase
- **migration_planner.py** - References conflict-resolution-patterns.md for dependency resolution
- **retrofit_executor.py** - References alignment-checklist.md for verification
- **retrofit_verifier.py** - References semantic-validation-approach.md for verification
- **sync_dispatcher.py** - References conflict-resolution-patterns.md for sync handling
- **genai_validate.py** - References semantic-validation-approach.md for validation
- **checkpoint.py** - References alignment-checklist.md for checkpoint validation

**Impact**:
- 12 files enhanced with standardized alignment patterns
- ~800-1,200 tokens saved (2-4% reduction across alignment agents and libraries)
- ~2,200 tokens of alignment patterns available on-demand via progressive disclosure
- 86 tests validate skill structure and integration (65 unit + 21 integration)
- Progressive disclosure: Only ~50 tokens SKILL.md overhead in context

---

### Library Design Skills Details (NEW v3.24.1 - Issue #72 Phase 8.8)

**Purpose**: Standardized patterns for library architecture, state management, and external API integration

**1. library-design-patterns** (532 lines)

**Location**: `/plugins/autonomous-dev/skills/library-design-patterns/`

**Contents**:
- **SKILL.md** (98 lines) - Overview and quick reference
- **Documentation Files (4)**:
  - `progressive-enhancement.md` (138 lines) - Progressive enhancement pattern (string → path → whitelist)
  - `two-tier-design.md` (124 lines) - Two-tier architecture (core logic + CLI interface)
  - `security-patterns.md` (89 lines) - Security validation patterns (CWE mitigations)
  - `docstring-standards.md` (83 lines) - Google-style docstring standards
- **Template Files (3)**:
  - `library-template.py` (145 lines) - Complete library structure template
  - `cli-template.py` (98 lines) - CLI interface template
  - `docstring-template.py` (76 lines) - Docstring examples template
- **Example Files (3)**:
  - `progressive-enhancement-example.py` (112 lines) - Progressive enhancement in action
  - `two-tier-example.py` (134 lines) - Two-tier architecture example
  - `security-validation-example.py` (87 lines) - Security validation patterns

**Key Patterns**:
1. **Progressive Enhancement**: Graceful degradation (string → Path → whitelist validation)
2. **Two-Tier Design**: Core library + CLI interface separation for reusability
3. **Security Validation**: CWE-22 (path traversal), CWE-59 (symlinks), CWE-117 (log injection) mitigations
4. **Docstring Standards**: Google-style with Args, Returns, Raises, Examples, Security Notes

**2. state-management-patterns** (289 lines)

**Location**: `/plugins/autonomous-dev/skills/state-management-patterns/`

**Contents**:
- **SKILL.md** (74 lines) - Overview and quick reference
- **Documentation Files (1)**:
  - `json-persistence.md` (97 lines) - JSON state persistence patterns
- **Template Files (3)**:
  - `state-manager-template.py` (156 lines) - Complete state manager with atomic writes
  - `atomic-write-template.py` (89 lines) - Atomic write pattern (mkstemp → write → rename)
  - `file-lock-template.py` (73 lines) - File locking with reentrant locks

**Key Patterns**:
1. **JSON Persistence**: Atomic writes, crash recovery, schema validation
2. **Atomic Operations**: mkstemp() → os.write() → os.close() → os.chmod() → Path.replace()
3. **File Locking**: Reentrant locks, deadlock prevention, timeout handling
4. **Crash Recovery**: Persistent state files, resume operations, progress tracking

**3. api-integration-patterns** (357 lines)

**Location**: `/plugins/autonomous-dev/skills/api-integration-patterns/`

**Contents**:
- **SKILL.md** (76 lines) - Overview and quick reference
- **Template Files (4)**:
  - `github-api-template.py` (134 lines) - GitHub API integration with retry logic
  - `retry-decorator-template.py` (87 lines) - Exponential backoff retry decorator
  - `subprocess-executor-template.py` (98 lines) - Safe subprocess execution
- **Example Files (1)**:
  - `safe-subprocess-example.py` (62 lines) - Command injection prevention patterns

**Key Patterns**:
1. **GitHub API Integration**: Authentication, rate limiting, error handling, retry logic
2. **Retry Logic**: Exponential backoff, jitter, max attempts, timeout handling
3. **Subprocess Security**: List args (prevent injection), shell=False, input validation
4. **Command Injection Prevention**: CWE-78 mitigations, whitelist validation, audit logging

**Combined Impact**: 
- 35 libraries enhanced with standardized patterns
- ~1,880 tokens saved (6-8% reduction)
- ~3,500 tokens of library patterns available on-demand via progressive disclosure
- 181 tests validate skill structure and integration


### Skill-Integration Skill Details (NEW v3.19.0 - Issue #67-68)

**Location**: `/plugins/autonomous-dev/skills/skill-integration/`

**Purpose**: Standardized patterns for how agents discover, reference, and use skills effectively

**Contents**:
- **SKILL.md** (385 lines) - Overview and quick reference
- **Documentation Files (3)**:
  - `progressive-disclosure.md` (1,247 lines) - Complete architecture guide
  - `skill-discovery.md` (892 lines) - Keyword-based activation patterns
  - `skill-composition.md` (1,156 lines) - Multi-skill combination patterns
- **Example Files (3)**:
  - `agent-skill-reference-template.md` (287 lines) - Agent prompt template
  - `progressive-disclosure-diagram.md` (421 lines) - Visual guides
  - `skill-composition-example.md` (368 lines) - Real-world examples

**Key Concepts**:
1. **Progressive Disclosure**: Metadata stays in context, full content loads on-demand
2. **Skill Discovery**: Keyword-based auto-activation or manual referencing
3. **Skill Composition**: Combining multiple skills for complex tasks
4. **Context Efficiency**: Support 50-100+ skills without bloat

**Impact**: Standardizes how all agents and libraries reference and compose skills, enabling unlimited skill scaling while maintaining context efficiency.

### Current Skills That Need Updates

**1. api-design**
- Current: Generic API design
- Recommended: Narrow to "REST API design with versioning, rate limiting, error handling"
- Triggers: HTTP status codes, REST endpoints, API versioning

**2. architecture-patterns**
- Current: Design patterns
- Recommended: "System architecture and ADR (Architecture Decision Record) creation"
- Triggers: ADR, system design, architectural tradeoffs

**3. code-review**
- Current: Code review
- Recommended: "Code quality assessment, style checking, pattern detection"
- Triggers: Code style, quality gates, anti-patterns

**4. testing-guide**
- Current: Testing methodology
- Recommended: "Test-driven development (TDD), test patterns, coverage strategies"
- Triggers: Test writing, TDD, coverage metrics, regression testing

**5. security-patterns**
- Current: Security best practices
- Recommended: "Security implementation (API keys, input validation, encryption patterns)"
- Triggers: Secrets management, OWASP, validation, security audit

### Skills Structure for Progressive Disclosure

```
skills/api-design/
├── SKILL.md
│   ├── [Brief: "Design REST APIs with proper versioning, error handling"]
│   ├── ## Quick Reference
│   │   └── Common patterns (bullets)
│   ├── ## REST Design
│   │   └── Endpoints, methods, status codes
│   ├── ## Error Handling
│   │   └── Standard error responses
│   └── ## Supporting Files
│       └── See: examples.md, checklist.md
├── examples.md (detailed examples)
├── checklist.md (design review checklist)
└── templates/
    └── error-response-template.json
```

Claude loads SKILL.md, then only loads examples.md when analyzing existing API.

---

## Summary: Why Agents + Skills = Better Than Before

| Aspect | Skills Alone | Agents Alone | Agents + Skills |
|--------|--------------|--------------|-----------------|
| **Specialization** | ✅ Focused | ❌ Broad | ✅✅ Both |
| **Scalability** | ✅ Good (20+) | ❌ Limited | ✅✅ Unlimited |
| **Context Efficiency** | ✅ Progressive | ❌ Full load | ✅✅ Progressive |
| **Discoverability** | ✅ Metadata | ❌ Manual | ✅✅ Automatic |
| **Orchestration** | ❌ No | ✅ Yes | ✅✅ Intelligent |
| **Tool Control** | ✅ Boundary | ❌ Full access | ✅✅ Scoped |

**The real power**: Agents as orchestrators, Skills as knowledge packages. Each does what it does best.

---

## Part 8: Native Claude Code 2.0 Skill Integration (Issue #143)

### The Solution: Claude Code 2.0 Native Skills Frontmatter

**Problem Solved** (Issue #140 v1 → Issue #143 v2):
- Old approach (Issue #140): Required explicit skill injection via `skill_loader.py` in every Task call
- New approach (Issue #143): Claude Code 2.0 natively handles skills via agent frontmatter `skills:` field

**How It Works**:

Each agent declares required skills in its frontmatter:

```yaml
---
name: test-master
description: Testing specialist - TDD workflow
model: sonnet
tools: [Read, Write, Edit, Bash, Grep, Glob]
skills: testing-guide, python-standards
---
```

When Claude Code spawns the agent via Task tool:
1. **Parse frontmatter**: Claude Code detects `skills:` field
2. **Auto-load skills**: Declared skills automatically loaded from `plugins/autonomous-dev/skills/`
3. **Inject context**: Skill content injected into agent context (no manual work needed)
4. **Execute**: Agent receives full context with skills pre-loaded

**Result**: Agents access relevant skills automatically without any special code in commands or Task prompts.

### Agent-Skill Mapping (Source of Truth)

Mapping defined in `skill_loader.py` AGENT_SKILL_MAP (matches frontmatter declarations):

| Agent | Skills Declared |
|-------|-----------------|
| test-master | testing-guide, python-standards |
| implementer | python-standards, testing-guide, error-handling-patterns |
| reviewer | code-review, python-standards |
| security-auditor | security-patterns, error-handling-patterns |
| doc-master | documentation-guide, git-workflow |
| planner | architecture-patterns, project-management |
| researcher-local | research-patterns |
| researcher-web | research-patterns |
| issue-creator | github-workflow, research-patterns |
| project-bootstrapper | project-management, documentation-guide |
| setup-wizard | project-management |
| alignment-analyzer | project-alignment-validation |
| brownfield-analyzer | research-patterns, documentation-guide |
| quality-validator | code-review, testing-guide |
| advisor | advisor-triggers, security-patterns |
| commit-message-generator | git-workflow |
| pr-description-generator | git-workflow, github-workflow |
| project-progress-tracker | project-management |
| project-status-analyzer | project-management |
| alignment-validator | project-alignment-validation |
| sync-validator | git-workflow |

### Implementation Details

**Frontmatter Format**:
```yaml
skills: skill1, skill2, skill3  # Comma-separated list (no brackets needed)
```

**Skill Loading**:
- Skills loaded from: `plugins/autonomous-dev/skills/[skill-name]/SKILL.md`
- Content progressively disclosed: Compact SKILL.md files with detailed docs in subdirectories
- Missing skills: Logged as warning, workflow continues (graceful degradation)

**No Manual Work Required**:
- No skill_loader.py calls needed in commands
- No subprocess management needed
- No token budget calculation needed
- Claude Code handles everything

### Token Efficiency

- **Compact SKILL.md files**: 87-315 lines each (Issue #110 refactoring)
- **Detailed content**: Moved to docs/ subdirectories (6,000+ lines preserved)
- **Progressive disclosure**: Agents access metadata (quick) + details on-demand
- **Overall reduction**: ~16,833-17,233 tokens saved vs monolithic skills (26-35% reduction)

### Verification

Check agent-skill mapping:
```bash
# Show mapping source of truth
cat plugins/autonomous-dev/lib/skill_loader.py | grep -A 100 "AGENT_SKILL_MAP"

# Verify skill files exist
ls plugins/autonomous-dev/skills/*/SKILL.md
```

### Graceful Degradation

If skill file missing:
- Claude Code logs warning
- Agent continues without that skill
- Workflow not blocked
- Other agents unaffected

### Backwards Compatibility

The `skill_loader.py` library remains available for:
- Manual skill loading queries: `python3 plugins/autonomous-dev/lib/skill_loader.py --list`
- Developer verification: `python3 plugins/autonomous-dev/lib/skill_loader.py --map`
- Custom integrations: Manual skill content retrieval if needed

**Primary usage** (Issue #143): Deprecated for Task-based workflows (Claude Code 2.0 handles it natively)

---

## References

- **Official Anthropic Skills Guide**: https://docs.claude.com/en/docs/claude-code/skills.md
- **Claude Code Best Practices**: https://www.anthropic.com/engineering/claude-code-best-practices
- **Agent Skills Architecture**: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- **API Skills Guide**: https://docs.claude.com/en/api/skills-guide
- **Sub-Agents Documentation**: https://docs.claude.com/en/docs/claude-code/sub-agents.md

---

**Conclusion**: Integrate skills with agents in autonomous-dev. They're no longer anti-pattern—they're first-class architecture.
