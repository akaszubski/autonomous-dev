# Project Context — Autonomous Development Plugin

**Last Updated**: 2026-05-26
**Version**: v3.51.0

For behaviour rules see [`CLAUDE.md`](CLAUDE.md). For operational sequences see [`docs/RUNBOOK.md`](docs/RUNBOOK.md). For content placement see [`docs/development/CONTENT_ALLOCATION.md`](docs/development/CONTENT_ALLOCATION.md).

---

## GOALS

**Mission**: Make Claude Code CLI follow the full software development lifecycle — requirements, architecture, coding, testing, review, security, documentation, deployment — with the discipline of a senior engineering team.

**Why this exists**: Claude is trained as a generalist to get things done. It executes brilliantly but lacks judgment about *what* to do, *when*, and *why*. It will skip tests, bypass process, and drift from intent — not out of malice, but because its training optimises for immediate completion, not sustainable engineering. CLAUDE.md instructions drift under context pressure. The context window is finite and the world is bigger than the window. You cannot teach judgment through rules — rules say "always do X" while judgment says "it depends."

autonomous-dev compensates by enforcing process through hooks (deterministic, can't be argued with) and injecting the right context at the right time (PROJECT.md, GitHub issues, research). The system doesn't replace human judgment — it ensures Claude follows the SDLC steps where human judgment has already determined what "good" looks like.

**The core tension**: enforcement works but is expensive in tokens. Every session re-teaches fundamentals. This is a known cost, not a design flaw — it's the price of working with a generalist that doesn't yet carry domain judgment in its weights.

autonomous-dev provides **macro alignment with micro flexibility**: PROJECT.md defines goals, scope, constraints — Claude checks alignment before every feature. Claude can still improve the implementation when it finds better patterns.

**User Intent** (stated 2025-10-26):
> "I speak requirements and Claude Code delivers a first grade software engineering outcome in minutes by following all the necessary steps that would need to be taken in top level software engineering but so much quicker with the use of AI and validation"

**Current Direction** (stated 2026-03-28):
> Building complete autonomous improvements using real-time runtime data as it's used. The system should get better every week without anyone thinking about it.

---

## SCOPE

**IN Scope:**
- Feature request detection and auto-orchestration
- 8-step pipeline: alignment → research → plan → test → implement → validate → verify → git
- PROJECT.md alignment validation before any work begins
- File organisation enforcement (src/, tests/, docs/)
- Brownfield project support (`/align --retrofit`, `/align --content`)
- Batch processing with crash recovery (`/implement --batch`, `--issues`, `--resume`)
- Automated git operations (commit, push, PR creation)
- MCP security validation and tool auto-approval
- Continuous improvement (session activity logging → drift detection → auto-filed issues)
- GenAI intent testing (LLM-as-judge validation of architecture, congruence, and alignment)
- Hook-settings bidirectional sync enforcement (hooks ↔ settings templates ↔ manifest)
- HARD GATE enforcement patterns for pipeline quality
- Alignment validation enforcement (strengthening PROJECT.md scope checks beyond advisory text)
- Effectiveness benchmarking (labeled datasets, balanced-accuracy scoring per-category and per-difficulty)
- Skill-based standards enforcement (skills as explicit evaluation criteria, not just documentation)
- Autonomous self-improvement (runtime aggregation → diagnosis → fix → benchmark verify → deploy, closed loop)
- Content allocation pattern (this file's shape — one topic, one home — extended to other repos via `/align --content`)

**OUT of Scope:**
- Replacing human developers — AI augments, doesn't replace
- Skipping PROJECT.md alignment — never proceed without validation
- Optional best practices — all SDLC steps are mandatory
- Language-specific lock-in — stay generic
- SaaS / cloud hosting — local-first
- Paid features — 100% free, MIT licence

---

## CONSTRAINTS

**Philosophy**: "Less is more" — every element serves the mission.

**Anti-bloat gates** (every feature must pass):
1. **Alignment** — does it serve the primary mission?
2. **Constraint** — does it respect boundaries?
3. **Minimalism** — is this the simplest solution?
4. **Value** — does benefit outweigh complexity?

**Red flags** (immediate bloat indicators): "This will be useful in the future", "We should also handle X, Y, Z", "Let's create a framework for…".

**HARD GATE pattern** (proven through #206 test gate, #310 anti-stubbing, #348 hook registration): advisory text gets ignored under context pressure. What works: (1) explicit FORBIDDEN list naming the bad behaviours, (2) required actions naming the resolution options, (3) gate position between work step and validation step.

**Operational wiring rule**: every infrastructure component (hook, agent, command) must have registration in all relevant settings templates and manifests, a wiring test verifying registration and no archived references, and an entry in the appropriate registry doc.

**Archived code rule**: active code must never import or reference archived components. Archived code lives in `*/archived/` directories and is dead code.

**Technical requirements**: Markdown (agent/skill/command definitions), Python 3.11+ (hooks/scripts), Bash (automation), JSON (config). pytest. Claude Code 2.0+ with plugins, agents, hooks, skills, slash commands.

**Performance budgets**: < 8,000 tokens per feature; 15–30 minutes per feature; < 60s test execution; < 10s validation hooks.

**Security requirements**: no hardcoded secrets (enforced by `security_scan.py`); acceptance-first testing mandatory; tool restrictions per agent (principle of least privilege); 80% minimum test coverage; MCP security validation (path traversal, injection prevention).

---

## ARCHITECTURE (high level)

autonomous-dev is a **harness** — the software layer that wraps an AI model to keep it on deterministic rails. Reliability in multi-step AI workflows compounds multiplicatively: a 10-step process with 90% accuracy per step fails over 60% of the time. Prompt-level instructions produce unreliable compliance (research-confirmed: "LLM Agents Are Hypersensitive to Nudges", 2025). The harness implements all 12 elements of harness engineering: state machine, validation loops, isolated sub-agents, virtual file system, human-in-the-loop, hook enforcement, state persistence, context management, deterministic ordering, output validation, observability, error recovery.

**Four-layer system:**

1. **Hook-Based Enforcement** (automatic, 100% reliable) — Hooks run on every tool call, commit, and prompt submission. Enforces PROJECT.md alignment, security, tests, docs, file organisation. Blocks on violation. Guaranteed execution.
2. **Agent-Based Intelligence** (user-invoked, AI-enhanced) — `/implement` coordinates specialist agents through the 8-step pipeline. Claude decides which agents based on complexity.
3. **Continuous Improvement Loop** (post-session, self-correcting) — Hook layers log JSONL to `.claude/logs/activity/`. `continuous-improvement-analyst` evaluates logs against PROJECT.md + CLAUDE.md and emits structured finding records via `append_finding()` to `.claude/logs/findings/` (#1200); `/improve --auto-file` promotes recurring findings into issues labeled `auto-improvement`. Runs asynchronously, never blocks active work.
4. **Autonomous Self-Improvement** (closed-loop, evidence-driven) — Effectiveness benchmarks measure reviewer/agent accuracy; runtime signals consolidated into ranked weakness reports; HIGH confidence diagnoses applied autonomously, MEDIUM filed as issues; benchmarks before/after every change, revert if regressed. Today's shipped loop: `continuous-improvement-analyst` agent → `/improve --auto-file` → `/triage --auto-improvement` (issues #579–#584 track the deeper integrations). The originally-named `/self-improve` command was never built; the three above form the current closed loop.

**Periodic-aggregation layer**: per-event automations (doc-master per commit, baseline per session, CIA per session) have periodic counterparts that aggregate across many events (`/refactor --docs`, baseline snapshots, `/triage --auto-improvement`). See [RUNBOOK.md](docs/RUNBOOK.md#periodic-aggregation-passes-per-event-automation--periodic-aggregation-duality-issue-1075).

**Key distinctions:** hooks = enforcement (always active, blocking); agents = intelligence (conditional, advisory); continuous improvement = learning (post-hoc analysis, issue filing); self-improvement = evolution (autonomous closed loop); periodic-aggregation = visibility (cross-event sweeps).

Full diagram (pipeline flow, model tiers, hook lifecycle events, repository structure) lives in [`docs/ARCHITECTURE-OVERVIEW.md`](docs/ARCHITECTURE-OVERVIEW.md). Diamond Testing Model details in [`docs/TESTING-STRATEGY.md`](docs/TESTING-STRATEGY.md).

---

## ENFORCEMENT

PROJECT.md is the gatekeeper — all work validates against this file before execution. Feature doesn't serve GOALS → BLOCKED. Feature is OUT of SCOPE → BLOCKED. Feature violates CONSTRAINTS → BLOCKED. Options when blocked: (1) update PROJECT.md to include the feature, (2) modify the request to align with current scope, (3) don't implement.

---

**For development workflow**: see [`CLAUDE.md`](CLAUDE.md)
**For operational sequences**: see [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
**For user documentation**: see [`README.md`](README.md)
**For troubleshooting**: see [`plugins/autonomous-dev/docs/TROUBLESHOOTING.md`](plugins/autonomous-dev/docs/TROUBLESHOOTING.md)
