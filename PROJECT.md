# Project Context — Autonomous Development Plugin

**Last Updated**: 2026-08-30
**Version**: v3.51.0

> **This is a gate input, not documentation.** The alignment gate reads it on every
> `/implement` run and refuses work that contradicts it — twice on 2026-08-30 alone.
> **Only statements capable of REFUSING belong here.** Two tests before adding a line:
> *what would this refuse?* (nothing → it belongs in
> [`docs/ARCHITECTURE-OVERVIEW.md`](docs/ARCHITECTURE-OVERVIEW.md)) and *can it be checked?*
> (a count with no stated method is unfalsifiable). Same mechanism in every repo, different
> content — keep it short and portable. Hard ceiling 225 lines, target 150; it loads every
> turn. Contract added 2026-08-30, #1708.

🎯 **ACTIVE GOAL**: [Enforcement Proven Everywhere, and Smaller](docs/experiments/GOAL_2026-08-24_enforcement-proven-everywhere.md) — every shipped guard proven refusing AND permitting in every repo it reaches, while the system gets smaller. Baseline MEASURED 2026-08-24: 4 of 8 guards fail open silently; 0 proof artifacts in realign/spektiv; rework-per-fix 86.8%. **v4 re-baseline 2026-08-28** — milestones resequenced to root-cause order after three measurements falsified the v3 plan: `claude -p` is 12.8s against a 5s budget, so the LLM tier could never succeed; `install_manifest.json` ships 0 `tests/` paths, so no detector reaches a consumer repo; 266 hook invocations exceeded budget in one week, silently dropping their checks. **v5 2026-08-29**: §2.0 names the mechanism this file's DEFINITION OF DONE section states — Q1 connected, Q2 works-as-designed, carried by the existing sidecar (+`invoked_by`/`proves`), enforced by the existing manifest, declarations generated, non-conformance ratcheted. **1 slip on the board — one more aborts (§7.5), and no third rewrite.** Mid-point abort review 2026-09-09. Standing rule (§2): a finding that can refuse becomes **a guard, not an issue**.

For behaviour rules see [`CLAUDE.md`](CLAUDE.md). For operational sequences see [`docs/RUNBOOK.md`](docs/RUNBOOK.md). For content placement see [`docs/development/CONTENT_ALLOCATION.md`](docs/development/CONTENT_ALLOCATION.md).

---

## GOALS

**Mission**: Make Claude Code CLI follow the full software development lifecycle — requirements,
architecture, coding, testing, review, security, documentation, deployment — **consistently**,
and prove **continuously** that each control is working. Following the steps is not the goal; a
control that ran, refused when it should have, permitted when it should have, and left a receipt
saying so — that is the goal.

**Why controls and not instructions**: adherence cannot be assumed. The operator forgets between
sessions, rationalises around prose in both directions, and asserts what it has not verified. So
each step is administered by something that *refuses*.

**Why assurance and not trust**: the controls themselves drift, die, and misreport. Measured
2026-08-30: a shipped guard was dead four independent ways and its own test suite agreed with it.

**Direction** (2026-03-28): the system should get better every week without anyone thinking about
it. That requires it to be measurable before it is autonomous, and small enough to reason about
before it is trusted.

*Rationale, failure taxonomy and history: [`docs/MAINTAINING-PHILOSOPHY.md`](docs/MAINTAINING-PHILOSOPHY.md).*

---

## SCOPE

**IN Scope:**
*Compressed 2026-08-30 from 17 bullets to 9. "enforcement" appeared in 5, "alignment" in 4,
"improvement" in 2, "benchmark" in 2 — the list had become an inventory of what was built
rather than a boundary. A permission list refuses only by omission, and this one had grown to
permit nearly everything: when the gate refused on 2026-08-30 it cited the Mission, not any
of these.*

- The 8-step pipeline — alignment → research → plan → test → implement → validate → verify →
  git — including feature detection, batch modes, and crash recovery
- PROJECT.md alignment validation, and the enforcement that makes it non-advisory rather than
  advisory text
- HARD GATE enforcement patterns: hooks that refuse, registered on a lifecycle event, and
  proven on both arms
- Operational wiring — hooks ↔ settings templates ↔ manifest — and file organisation
- Continuous → autonomous self-improvement: runtime data → diagnosis → fix → verify → deploy,
  as a closed loop
- Effectiveness measurement: GenAI intent testing, benchmarking against labelled datasets, and
  skills as explicit evaluation criteria
- MCP security validation and tool auto-approval
- Automated git operations (commit, push, PR creation)
- Brownfield support (`/align --retrofit`, `--content`) and the content allocation pattern —
  one topic, one home

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

A **harness** — the layer that keeps a model on deterministic rails, because reliability
compounds multiplicatively: ten steps at 90% fails more than 60% of the time. Four layers, in
descending order of guarantee: **hooks** (enforcement, blocking, always run) → **agents**
(intelligence, conditional) → **continuous improvement** (post-hoc analysis, files issues) →
**autonomous self-improvement** (closed loop, evidence-driven).

*Layer detail, diagram, pipeline flow, model tiers and repository structure:
[`docs/ARCHITECTURE-OVERVIEW.md`](docs/ARCHITECTURE-OVERVIEW.md). Testing model:
[`docs/TESTING-STRATEGY.md`](docs/TESTING-STRATEGY.md).*

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

*Added 2026-08-28. Stated here, not in a runbook, because it changes what may SHIP.*

Every gate this repo runs inspects **the artifact**. None asks whether it is **connected**, and
one narrow mechanism asks whether it **behaves as designed**. An unwired artifact is
byte-for-byte indistinguishable from a wired one — file present, tests green, manifest entry,
deployed. Six such artifacts shipped in one session on 2026-08-28; a guard dead four ways
shipped to five repos and its own suite agreed with it on 2026-08-30. Cases:
[`docs/MAINTAINING-PHILOSOPHY.md`](docs/MAINTAINING-PHILOSOPHY.md).

**Every artifact must answer both questions, and the answer must be mechanical.**

### Q1 — Is this work CONNECTED?

Something must invoke it, and that route must be verifiable by a machine. Prose naming a module
is not a route (INV-1). Presence in a manifest is not a route. A test that mocks the call site
is not a route.

Covered today by the reachability ratchets (#1612, #1698). **Uncovered: `scripts/`, `config/`,
`commands/`, `agents/`, and — the one that keeps biting — the DEPLOYED copy.** Every mechanism
validates SOURCE; source and runtime diverged three times in the two days to 2026-08-30.

### Q2 — Is this work WORKING AS DESIGNED?

Watched doing its job, and watched *not* doing it when it shouldn't — both arms, on the real
thing, not a fixture. A guard observed only green is unproven.

Covered today by `proof_of_block.py` for block-capable hooks. **Uncovered: hooks that cannot
refuse, `lib/` modules, `commands/`, `agents/`, and the tests themselves** — the mutation
witness (#1660) is built and wired to nothing.

*Per-artifact status counts live in [`docs/ARCHITECTURE-OVERVIEW.md`](docs/ARCHITECTURE-OVERVIEW.md),
not here: they drift, and this file must stay refusable rather than current. The 2026-08-28
table this replaced asserted `249 lib modules` — three counting methods give 229 / 249 / 254.*

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
