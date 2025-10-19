---
version: 1.0.0
created: 2025-10-19
last_reviewed: 2025-10-19
next_review: 2026-01-19
governance: Human approval required for changes
source: Extracted from production [PROJECT_NAME] system (98% alignment)
---

# Claude Code 2.0 Universal Standards

## Purpose
This document defines the architecture and principles for ALL Claude Code 2.0 projects, regardless of language or domain. It is version-controlled and subject to quarterly review.

## Core Principles

### 1. Single Source of Truth ⭐ FOUNDATIONAL
Every project consolidates intent, requirements, and architecture into ONE file: `PROJECT.md`

**Structure:**
- VISION: What and why
- REQUIREMENTS: Functional + non-functional (extracted from code/tests)
- ARCHITECTURE: System design + decisions
- CONTRACTS: Pre/post/invariants
- CURRENT FOCUS: Active goal
- TRACEABILITY: Requirement → code mapping

**Rationale:** Eliminates context bloat (1 file vs 20), prevents drift, enables efficient reasoning

### 2. Progressive Disclosure ⭐ FOUNDATIONAL
Skills load minimal context - only frontmatter until invoked.

**Implementation:** SKILL.md contains metadata (~50 tokens), full content loaded only when triggered.

**Rationale:** Prevents token bloat, improves response time, enables parallelization

### 3. Self-Contained Skills ⭐ FOUNDATIONAL
Each skill is atomic - one folder contains instructions + code + templates + examples.

**Structure:**
```
skill/
├── SKILL.md          # Instructions
├── *.{py,js,go}      # Executable code (language-specific)
├── templates/        # Reusable templates
└── examples/         # Reference examples
```

**Rationale:** No shared state, enables reuse, clear boundaries

### 4. Automated Enforcement ⭐ CRITICAL
Hooks validate and auto-correct folder structure, naming, and placement.

**Implementation:** PreToolUse hooks run validation before every write operation.

**Language Support:** Hooks detect project language and apply appropriate formatters/linters.

### 5. Continuous Consolidation ⭐ CRITICAL
Scattered docs and patterns auto-merge after EVERY edit.

**Implementation:** PostToolUse hooks consolidate docs and patterns.

### 6. Minimal Context Surface ⭐ FOUNDATIONAL
Only 3 core files + invoked skills loaded at any time.

**Budget:**
- PROJECT.md: ~2000 tokens
- PATTERNS.md: ~1500 tokens
- STATUS.md: ~800 tokens
- Active skill: ~1000 tokens
- Total: ~5300 tokens (vs 50,000+ with sprawl)

### 7. Observable & Self-Reflective ⭐ CRITICAL
STATUS.md auto-generated showing system health, alignment score, and metrics.

**Metrics:**
- Alignment score (structure compliance)
- Test coverage (language-dependent)
- Code quality (cyclomatic complexity, type coverage)
- Documentation coverage (API docs vs code)
- Security score (vulnerability scan results)

### 8. Self-Improving Feedback Loop ⭐ META-PRINCIPLE
System learns from actions and proposes improvements automatically.

**Flow:** Action → Log → Learn → Validate → Promote → Propose

### 9. Controlled Agent Use ⭐ BEST PRACTICE
Use sub-agents ONLY for long-horizon or research-heavy tasks (5% of operations).

**Agent Roles:**
- planner: Architecture & design (read-only)
- implementer: Code implementation (write)
- test-master: Testing strategy & execution (write)
- reviewer: Code quality gate (read-only)
- security-auditor: Security scanning (read-only)
- doc-master: Documentation updates (write)
- researcher: Web research & best practices (read-only)

### 10. Versioned Meta-Governance ⭐ FOUNDATIONAL
Standards are version-controlled, semantically versioned, quarterly reviewed.

**Versioning:**
- MAJOR: Breaking changes to principles or structure
- MINOR: New principles or significant refinements
- PATCH: Clarifications or minor corrections

## Update Cadence

| Artifact | Cadence | Trigger | Owner | Human Review |
|----------|---------|---------|-------|--------------|
| PROJECT.md | Continuous | Requirement change | doc-master (via requirements-analyzer skill) | Breaking changes |
| PATTERNS.md | After edit | Pattern learned | pattern-curator skill (automated) | Monthly audit |
| STATUS.md | Every 15min | Metric refresh | system-aligner skill (automated) | Weekly review |
| STANDARDS.md | Quarterly | Claude update | Human-led with researcher agent | Required |

## Language-Specific Adaptations

While these principles are universal, implementation details vary by language:

### Python
- Formatter: black + isort
- Linter: ruff
- Type checker: mypy
- Test framework: pytest
- Coverage target: 80%

### JavaScript/TypeScript
- Formatter: prettier
- Linter: eslint
- Type checker: typescript (strict mode)
- Test framework: jest or vitest
- Coverage target: 80%

### Go
- Formatter: gofmt
- Linter: golint + go vet
- Type checker: built-in
- Test framework: go test
- Coverage target: 80%

## Governance Model

### Quarterly Review Process
1. **Week 1-2:** Collect feedback from system logs and user reports
2. **Week 3:** researcher agent analyzes Claude updates and best practices
3. **Week 4:** Human decision + update STANDARDS.md version
4. **Post-update:** Propagate changes to all active projects

### Change Requirements
- **MAJOR version:** Requires human approval + migration guide
- **MINOR version:** Requires human review
- **PATCH version:** Can be automated with human notification

## Meta-Principles

### Self-Improvement Protocol
The system continuously monitors:
- Alignment drift (actual vs expected structure)
- Pattern emergence (new idioms in code)
- Quality regression (test failures, coverage drops)
- Efficiency metrics (token usage, response time)

When patterns emerge across 3+ instances, pattern-curator proposes promotion to PATTERNS.md.

### Context Optimization
Progressive disclosure ensures:
- Skills are lazy-loaded (frontmatter only until invoked)
- Documentation is tiered (README → guides → detailed docs)
- Agent context is minimal (only relevant files mapped)

### Evidence-Based Requirements
Requirements are extracted FROM code/tests, not written speculatively:
1. requirements-analyzer skill scans tests
2. Extracts assertions as requirements
3. Updates PROJECT.md with traceability links
4. Validates code implements requirements

---

## Version History
- 1.0.0 (2025-10-19): Initial universal standards extracted from [PROJECT_NAME] production system
