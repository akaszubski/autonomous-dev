# Project Context — Autonomous Development Plugin

**Last Updated**: 2026-08-24
**Version**: v3.51.0

🎯 **ACTIVE GOAL**: [Enforcement Proven Everywhere, and Smaller](docs/experiments/GOAL_2026-08-24_enforcement-proven-everywhere.md) — every shipped guard proven refusing AND permitting in every repo it reaches, while the system gets smaller. Baseline MEASURED 2026-08-24: 4 of 8 guards fail open silently; 0 proof artifacts in realign/spektiv; rework-per-fix 86.8%. **v4 re-baseline 2026-08-28** — milestones resequenced to root-cause order after three measurements falsified the v3 plan: `claude -p` is 12.8s against a 5s budget, so the LLM tier could never succeed; `install_manifest.json` ships 0 `tests/` paths, so no detector reaches a consumer repo; 266 hook invocations exceeded budget in one week, silently dropping their checks. **v5 2026-08-29**: §2.0 names the mechanism this file's DEFINITION OF DONE section states — Q1 connected, Q2 works-as-designed, carried by the existing sidecar (+`invoked_by`/`proves`), enforced by the existing manifest, declarations generated, non-conformance ratcheted. **1 slip on the board — one more aborts (§7.5), and no third rewrite.** Mid-point abort review 2026-09-09. Standing rule (§2): a finding that can refuse becomes **a guard, not an issue**.

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
- SaaS / cloud hosting — local-first. **One named exception: web research.**
  Research is inherently a network call, and no local index covers current
  vendor documentation — measured 2026-08-29, a self-hosted SearXNG returned
  3 relevant results in 10 for a Claude Code docs question while the hosted
  tool returned 8 of 8 including the official docs. Agents MAY therefore
  declare a hosted search tool as primary, but ONLY alongside a local one,
  which can never be removed. On a local-model backend the hosted tool does
  not resolve and the local one is used. See INV-8.
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

## ARCHITECTURE (Solution-on-a-Page)

autonomous-dev is a **harness** — the software layer that wraps an AI model to keep it on deterministic rails. Reliability in multi-step AI workflows compounds multiplicatively: a 10-step process with 90% accuracy per step fails over 60% of the time. Prompt-level instructions produce unreliable compliance (research-confirmed: "LLM Agents Are Hypersensitive to Nudges", 2025). The harness implements all 12 elements of harness engineering: state machine, validation loops, isolated sub-agents, virtual file system, human-in-the-loop, hook enforcement, state persistence, context management, deterministic ordering, output validation, observability, error recovery.

**Four-layer system:**

1. **Hook-Based Enforcement** (automatic, 100% reliable) — Hooks run on every tool call, commit, and prompt submission. Enforces PROJECT.md alignment, security, tests, docs, file organisation. Blocks on violation. Guaranteed execution.
2. **Agent-Based Intelligence** (user-invoked, AI-enhanced) — `/implement` coordinates specialist agents through the 8-step pipeline. Claude decides which agents based on complexity.
3. **Continuous Improvement Loop** (post-session, self-correcting) — Hook layers log JSONL to `.claude/logs/activity/`. `continuous-improvement-analyst` evaluates logs against PROJECT.md + CLAUDE.md and emits structured finding records via `append_finding()` to `.claude/logs/findings/` (#1200); `/improve --auto-file` promotes recurring findings into issues labeled `auto-improvement`. Runs asynchronously, never blocks active work.
4. **Autonomous Self-Improvement** (closed-loop, evidence-driven) — Effectiveness benchmarks measure reviewer/agent accuracy; runtime signals consolidated into ranked weakness reports; HIGH confidence diagnoses applied autonomously, MEDIUM filed as issues; benchmarks before/after every change, revert if regressed. Today's shipped loop: `continuous-improvement-analyst` agent → `/improve --auto-file` → `/triage --auto-improvement` (issues #579–#584 track the deeper integrations). The originally-named `/self-improve` command was never built; the three above form the current closed loop.

**Periodic-aggregation layer**: per-event automations (doc-master per commit, baseline per session, CIA per session) have periodic counterparts that aggregate across many events (`/refactor --docs`, baseline snapshots, `/triage --auto-improvement`). See [RUNBOOK.md](docs/RUNBOOK.md#periodic-aggregation-passes-per-event-automation--periodic-aggregation-duality-issue-1075).

**Key distinctions:** hooks = enforcement (always active, blocking); agents = intelligence (conditional, advisory); continuous improvement = learning (post-hoc analysis, issue filing); self-improvement = evolution (autonomous closed loop); periodic-aggregation = visibility (cross-event sweeps).

Full diagram (pipeline flow, model tiers, hook lifecycle events, repository structure) lives in [`docs/ARCHITECTURE-OVERVIEW.md`](docs/ARCHITECTURE-OVERVIEW.md). Diamond Testing Model details in [`docs/TESTING-STRATEGY.md`](docs/TESTING-STRATEGY.md).

### INVARIANTS

These are the load-bearing properties of the harness. A proposed change that contradicts one is an **architecture delta** and requires explicit user sign-off before implementation (Issue #1467). Volatile detail — component counts, hook lists, model tiers, step sub-numbering — lives in [`docs/ARCHITECTURE-OVERVIEW.md`](docs/ARCHITECTURE-OVERVIEW.md) and is explicitly NOT invariant.

- **INV-1 — Enforcement is hooks, not nudges.** Anything that must hold is enforced by a hook returning `{"decision": "block"}`. Prompt-level "should" text is advisory and never counts as enforcement.
- **INV-2 — Specialists run in fresh context.** Each pipeline agent is invoked with a clean context window and a single responsibility. The coordinator never self-attests a judgment that a specialist exists to make.
- **INV-3 — The pipeline shape is fixed.** Eight steps: alignment → research → plan → acceptance tests → implement → validate → verify → git. Internal sub-steps may be added; the top-level set and their order do not change without sign-off.
- **INV-4 — Protected infrastructure is implementer-only.** `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` are never edited outside `/implement`; the hard floor holds even under `.claude/.bypass`.
- **INV-5 — One topic, one home.** Every piece of content has exactly one canonical location; everything else links to it rather than restating it.
- **INV-6 — Deterministic before probabilistic.** Where a check can be made mechanically (path match, keyword list, signature verification), the mechanical check runs first, and its BLOCK/ESCALATE outcome cannot be overridden by an LLM judgment.
- **INV-7 — Gating state is signed and fails closed.** State that gates enforcement is HMAC-signed. Any verification failure, missing field, or missing file is treated as "not passed" — never as "passed".
- **INV-8 — Local-first and free.** No gate requires a paid API, a network call, or a hosted service to function. Gates degrade to deterministic-only rather than demanding a key. **Web research is the one named exception** (see SCOPE OUT): it is inherently a network call and cannot be served by a local index. The invariant that still binds it is narrower — an agent may declare a hosted search tool, but never *alone*: a local search tool must always be declared alongside, so the capability degrades rather than disappears when the hosted one cannot reach the backend. An agent declaring a hosted tool with no local companion is refused. Nothing that *enforces* — no hook, no gate, no pipeline step — may depend on a hosted service.

---

## DEFINITION OF DONE — two questions, asked of every artifact

*Added 2026-08-28. This is the missing half of "done", and it is stated here rather than in a
runbook because it changes what may ship, not how work is sequenced.*

Every gate this repo runs today — coverage regression, skip regression, test count, skip rate,
reviewer, security-auditor, doc-master, agent-completeness — inspects **the artifact**. Not one
asks whether the artifact is **connected**, and only one narrow mechanism asks whether it
**behaves as designed**. So "built" acquired a definition of done and "wired" never did, and
work stops where the checking stops.

The cost is measured, not theorised. In a single session (2026-08-28): `prior_art_search.py`
shipped to every consumer repo with 9 green tests and **zero callers**; a mutation harness was
built, hardened through 5 blocking defects, and **wired to nothing**; `--check-timeouts` was
built and **invoked by nothing**; `step5_quality_gate.py` is named four times across
`implement.md` and `implementer.md` as the gate that "blocks" and is **invoked by neither**;
103 tests sat in a flag-gated tier and had **never run**; and `mutmut` was pinned, configured,
and **never executed** while 19 tests passed over it. None of these was visible: an unwired
artifact is byte-for-byte indistinguishable from a wired one — file present, tests green,
manifest entry, deployed.

**Every artifact must answer both questions, and the answer must be mechanical.**

### Q1 — Is this work CONNECTED?

Something must invoke it, and that route must be verifiable by a machine. Prose naming a module
is not a route (INV-1). Presence in a manifest is not a route. A test that mocks the call site
is not a route.

| Artifact | Mechanism | Status 2026-08-28 |
|---|---|---|
| `hooks/` | reachability ratchet (#1612) | COVERED |
| `lib/` | reachability ratchet (#1698) | COVERED — 249 modules, **132 UNKNOWN** |
| `scripts/` (38 files) | — | **UNCOVERED** — where `--check-timeouts` slipped through |
| `config/` (16 files) | — | **UNCOVERED** — where `hook_time_budgets.json` sits |
| `commands/` (26), `agents/` (20) | — | **UNCOVERED**, and hardest: a naive walk credits prose, which is the #1698 defect |
| **the DEPLOYED copy** | — | **UNCOVERED.** Every mechanism above validates SOURCE. Source may say `20` while the executing copy says `5` with nothing red. |

### Q2 — Is this work WORKING AS DESIGNED?

Watched doing its job, and watched *not* doing it when it shouldn't — both arms, on the real
thing, not a fixture. A guard observed only green is unproven.

| Artifact | Mechanism | Status 2026-08-28 |
|---|---|---|
| block-capable hooks (9) | `proof_of_block.py` | ~8 of 9; 7/7 PROVEN in realign |
| the other 19 hooks | — | **UNCOVERED** — they cannot refuse, so nothing drives them |
| `lib/` modules | — | **UNCOVERED** |
| tests themselves | mutation witness (#1660) | BUILT, **not wired** — the harness has no producer |
| `commands/`, `agents/` | — | **UNCOVERED** |

### The rule

**A finding that can refuse becomes a guard, not an issue** — see the active goal §2 and abort
condition §7.6. Extending an existing corpus beats adding a mechanism: the reachability ratchet
is the only thing that has ever caught one of these automatically, and it did so against this
repo's own work, unprompted, within twelve hours of shipping.

## ENFORCEMENT

PROJECT.md is the gatekeeper — all work validates against this file before execution. Feature doesn't serve GOALS → BLOCKED. Feature is OUT of SCOPE → BLOCKED. Feature violates CONSTRAINTS → BLOCKED. Options when blocked: (1) update PROJECT.md to include the feature, (2) modify the request to align with current scope, (3) don't implement.

**Added 2026-08-28**: an artifact that cannot answer Q1 and Q2 above is not done. Shipping it is
a scope decision requiring an explicit, recorded reason — not a default.

---

**For development workflow**: see [`CLAUDE.md`](CLAUDE.md)
**For operational sequences**: see [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
**For user documentation**: see [`README.md`](README.md)
**For troubleshooting**: see [`plugins/autonomous-dev/docs/TROUBLESHOOTING.md`](plugins/autonomous-dev/docs/TROUBLESHOOTING.md)
