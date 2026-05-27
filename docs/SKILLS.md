---
covers:
  - plugins/autonomous-dev/skills/
---

# Skills Reference

20 active skill packages at `plugins/autonomous-dev/skills/`. Skills are progressively injected into agent context — loaded only when the task matches the skill's `TRIGGER when:` conditions, so they don't bloat every prompt.

**Design principle**: One domain per skill. Each `SKILL.md` declares when it loads (TRIGGER) and when it doesn't (DO NOT TRIGGER) so the model gets the right knowledge at the right time without over-inclusion.

---

## Skill Catalog

### Engineering Standards

| Skill | Purpose | Trigger When |
|-------|---------|--------------|
| [python-standards](../plugins/autonomous-dev/skills/python-standards/SKILL.md) | PEP 8, Black, type hints, Google-style docstrings | Python files, formatting, type hints |
| [code-review](../plugins/autonomous-dev/skills/code-review/SKILL.md) | 10-point review checklist (correctness, tests, errors, security) | PR review, code quality check |
| [refactoring-patterns](../plugins/autonomous-dev/skills/refactoring-patterns/SKILL.md) | Extract/inline/rename/move/simplify techniques | Refactor, clean up, code smell |
| [error-handling](../plugins/autonomous-dev/skills/error-handling/SKILL.md) | Exception hierarchies, retries, circuit breakers | Designing error paths, resilience |
| [debugging-workflow](../plugins/autonomous-dev/skills/debugging-workflow/SKILL.md) | Reproduce → isolate → bisect → fix → verify | Failing test, traceback, unexpected behavior |

### Architecture & Design

| Skill | Purpose | Trigger When |
|-------|---------|--------------|
| [architecture-patterns](../plugins/autonomous-dev/skills/architecture-patterns/SKILL.md) | File-by-file plans with ADR format, testability gates | System design, ADR, file breakdown |
| [library-design-patterns](../plugins/autonomous-dev/skills/library-design-patterns/SKILL.md) | Two-tier design, progressive enhancement, security-first | Python library, reusable component |
| [api-design](../plugins/autonomous-dev/skills/api-design/SKILL.md) | REST patterns — versioning, pagination, OpenAPI | REST endpoint, HTTP route |
| [state-management-patterns](../plugins/autonomous-dev/skills/state-management-patterns/SKILL.md) | JSON persistence, atomic writes, file locking, crash recovery | Stateful libraries, checkpointing |

### Process & Workflow

| Skill | Purpose | Trigger When |
|-------|---------|--------------|
| [planning-workflow](../plugins/autonomous-dev/skills/planning-workflow/SKILL.md) | 7-step planning; enforced by plan_gate, critiqued by plan-critic | `/plan`, design document, architecture decision |
| [research-patterns](../plugins/autonomous-dev/skills/research-patterns/SKILL.md) | 4-phase methodology (recon, targeted search, analysis, synthesis) | Investigating patterns, evaluating libraries |
| [git-github](../plugins/autonomous-dev/skills/git-github/SKILL.md) | Conventional commits, branch naming, PR workflow, gh CLI | Commits, PRs, gh usage |
| [documentation-guide](../plugins/autonomous-dev/skills/documentation-guide/SKILL.md) | Keep-a-Changelog format, README structure, ADR templates | CHANGELOG entries, README updates |

### Quality & Validation

| Skill | Purpose | Trigger When |
|-------|---------|--------------|
| [testing-guide](../plugins/autonomous-dev/skills/testing-guide/SKILL.md) | GenAI-first testing, structural assertions, tier-based structure | Writing tests, coverage, TDD |
| [scientific-validation](../plugins/autonomous-dev/skills/scientific-validation/SKILL.md) | Pre-registration, power analysis, Bayesian methods | Hypothesis testing, experiments, backtests |
| [security-patterns](../plugins/autonomous-dev/skills/security-patterns/SKILL.md) | API keys, input validation, injection prevention, OWASP | Secrets, user input, security-sensitive code |
| [observability](../plugins/autonomous-dev/skills/observability/SKILL.md) | Structured logging, pdb/ipdb, cProfile/line_profiler | Adding logging, debugging, profiling |

### Integration

| Skill | Purpose | Trigger When |
|-------|---------|--------------|
| [api-integration-patterns](../plugins/autonomous-dev/skills/api-integration-patterns/SKILL.md) | Subprocess safety, gh CLI, retry logic, rate limiting | External API, subprocess, authentication |
| [prompt-engineering](../plugins/autonomous-dev/skills/prompt-engineering/SKILL.md) | Constraint budgets, register shifting, HARD GATE patterns | Writing agents/*.md or skills/*/SKILL.md |

### Process & Workflow (continued)

| Skill | Purpose | Trigger When |
|-------|---------|--------------|
| [content-allocation](../plugins/autonomous-dev/skills/content-allocation/SKILL.md) | One-topic-one-home routing, size budgets, de-dup sweep for CLAUDE.md/PROJECT.md/MEMORY.md | Auditing CLAUDE.md/PROJECT.md/MEMORY.md sizes, running `/align --content`, applying content-allocation pattern to a new repo |

---

## How Skills Load

Skills aren't auto-included in every agent prompt. The matching logic lives in the coordinator and agent prompts — when an agent references a skill in its `skills:` frontmatter, it's asserting "load this when you handle tasks that match the TRIGGER conditions."

Example from `agents/implementer.md`:
```yaml
---
name: implementer
skills: [python-standards, testing-guide, error-handling, security-patterns]
---
```

The implementer agent's prompt references those four skills when tasks involve Python, tests, error paths, or security-sensitive code — not all four every time.

## Skill Effectiveness

Each skill is measurable via `/skill-eval`:

```bash
/skill-eval                       # Full eval — all 20 skills
/skill-eval --quick               # Fast mode (fewer prompts per skill)
/skill-eval --skill python-standards   # One skill only
/skill-eval --update              # Update baseline after confirmed improvement
```

See [EVALUATION.md](EVALUATION.md) for the measurement surface and closed-loop self-improvement workflow that runs benchmarks before/after every skill edit.

Skill Effectiveness Gate (STEP 11.5 of `/implement`): When any `skills/*/SKILL.md` file is modified, the pipeline runs skill-eval on the changed skills and blocks if the delta drops more than 0.10. Requires `OPENROUTER_API_KEY` env var — skipped with warning if unset.

## Authoring a New Skill

Each skill lives in its own directory at `plugins/autonomous-dev/skills/<slug>/SKILL.md`. Required frontmatter:

```yaml
---
name: <slug>                   # matches directory name
description: "<one sentence> Use when ..."
trigger: "TRIGGER when: ..."   # matching keywords
do_not_trigger: "DO NOT TRIGGER when: ..."
version: "1.0.0"
---
```

Design principles:
- **One domain per skill**. Don't bundle "Python standards + testing + Git" into one file.
- **TRIGGER and DO NOT TRIGGER lines are required** — they prevent over-inclusion that bloats context.
- **Keep the body short** — skills are read whole into context when they match. 100-200 lines is typical.
- **Agents must reference skills by slug** in their frontmatter, or the skill won't load even when triggered.

Validation: `python3 scripts/validate_structure.py` and `pytest tests/unit/test_documentation_congruence.py` check skill layout and frontmatter.

## Archived Skills

`plugins/autonomous-dev/skills/archived/` holds retired skills no longer loaded into any agent. They remain for historical reference but do not fire. See `docs/HARNESS-EVOLUTION.md` for retirement rationale.

## Related

- [AGENTS.md](AGENTS.md) — which agents reference which skills (skill frontmatter + agent skill-integration section)
- [PROMPT-ENGINEERING.md](PROMPT-ENGINEERING.md) — why progressive skill injection works (constraint budgets, register shifting)
- [EVALUATION.md](EVALUATION.md) — skill-eval command and effectiveness measurement
- [PIPELINE-MODES.md](PIPELINE-MODES.md) — when the skill effectiveness gate fires (STEP 11.5)
