---
name: content-allocation
description: "One topic, one home. Routes content to its canonical store (CLAUDE.md, PROJECT.md, MEMORY.md, docs/, memory/) and audits for duplication. TRIGGER when: auditing CLAUDE.md/PROJECT.md/MEMORY.md sizes, deduplicating docs, applying the content-allocation pattern to a new repo, running /align --content. DO NOT TRIGGER when: implementing features, writing tests, routine code edits, debugging."
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Content Allocation

A methodology for keeping project context lean and unambiguous. Every piece of content has exactly one canonical home; every other appearance is a one-line pointer.

## Methodology: One Topic, One Home

**Core rule**: If a piece of content lives in two places, one of them is wrong. The canonical store owns the content; every other location is a one-line pointer to it.

Why this matters:

- `CLAUDE.md` and `MEMORY.md` are loaded **every turn**. Every line there has compounding cost across the project's lifetime.
- Duplication drifts. When the same fact lives in two files, the next edit will update one and leave the other stale.
- Readers (humans and assistants) waste tokens hunting through redundant copies for the authoritative version.

The pattern works in three moves:

1. **Identify the canonical home** for a topic using the routing table below.
2. **Move the content** to that home. Compress all other appearances to a single-line pointer (`See: docs/RUNBOOK.md`).
3. **Enforce size budgets** so the canonical home does not bloat into a second copy of the wider docs tree.

---

## Routing Table

The canonical stores in a typical Claude Code project, in load-order:

| Store | Loaded | Owns | Does NOT own |
|-------|--------|------|--------------|
| `~/.claude/CLAUDE.md` (global) | every turn, every repo | Assistant default behaviour; user's machines, SSH, session history queries | Anything project-specific |
| `CLAUDE.md` (project root) | every turn, this repo | Hard rules, gates, canonical paths, pointers, top-N gotchas | Vision, purpose, architecture, history, current state, deep reference |
| `.claude/PROJECT.md` | session start | Purpose, GOALS, SCOPE, CONSTRAINTS, alignment criteria, project philosophy | Behaviour rules; operational sequences; full architecture diagrams; current state |
| `memory/MEMORY.md` + `memory/*.md` | MEMORY auto-loaded; files retrievable | Durable lessons (with *why*), findings, calibration, active state | Hard rules; full architecture |
| `docs/RUNBOOK.md` | on demand | Operational sequences (periodic maintenance, batch finalize, resumes, common queries) | Architecture; rules |
| `docs/architecture/*.md` | on demand | High-level system architecture, layers, diagrams, ADRs | Behaviour rules; deep component internals |
| `docs/<TOPIC>.md` (per-domain) | on demand | Deep reference per topic (testing, security, hooks, libraries) | Behaviour; vision |
| Plugin user-facing `docs/*.md` | on demand | Shipped-with-plugin reference (commands, troubleshooting) | Maintainer-internal flows |
| GitHub issues | on reference | Current/open/closed work, decision threads | Anything else |

If a topic spans two stores: the *narrative* lives in PROJECT.md or docs/; the *rule* lives in CLAUDE.md; both reference each other as 1-line pointers.

---

## Routing Decision Algorithm

When you have new content to place, walk this 9-step ordered list and stop at the first match:

1. **Does it change behaviour every turn?** ("always do X / never do Y") → `CLAUDE.md` Critical Rules section.
2. **Does it describe scope, purpose, or architecture?** ("why this project exists, what's in/out of scope") → `.claude/PROJECT.md`.
3. **Is it a durable lesson + the *why*?** ("we learned X because Y") → `memory/feedback_*.md` (+ one-line index entry in `MEMORY.md`).
4. **Is it active state or a current finding?** ("session N discovered Z, still unresolved") → `memory/finding_*.md` (+ index entry).
5. **Is it an operational sequence?** ("how do I do X — the steps") → `docs/RUNBOOK.md`.
6. **Is it reference data?** (registries: hooks, agents, skills, libraries, commands) → `docs/<REGISTRY>.md`. User-facing command catalogue → plugin's `docs/COMMANDS.md`.
7. **Is it a pitfall or gotcha with a reproducer?** → memory if recent and repeatable; `docs/<TOPIC>.md` if catalogued.
8. **Is it deep architectural detail?** → `docs/<TOPIC>.md` (e.g. `HOOK-COMPOSITION.md`, `SECURITY.md`).
9. **Is it a plugin-user-facing fix?** → plugin's `docs/TROUBLESHOOTING.md`.

If you reach step 9 without a match, the content is probably scratch work or belongs in a GitHub issue.

---

## Size Budgets

Auto-loaded files have hard ceilings. Exceed them and you pay the cost every turn.

| File | Target | Hard ceiling | Why |
|------|--------|--------------|-----|
| `CLAUDE.md` | ≤100 lines | 200 | Loaded every turn. A size-validation hook should warn above 200. |
| `.claude/PROJECT.md` | ≤150 lines | 200 | Loaded at session start. Above 200 = operational drift, not architecture. |
| `MEMORY.md` | ≤150 lines | 200 | Often truncated above 200 when auto-loaded. |
| `memory/*.md` (individual) | 1–3 KB | 3 KB | >3 KB usually means it should be promoted to a `docs/` page. |

Rules of thumb:

- `MEMORY.md` entries should be **≤150 chars per line**. If you cannot summarise a finding in one line, the underlying file needs splitting.
- Memory files below **500 bytes** with no active finding should be compressed to an index entry or deleted.
- Never duplicate content between global and project `CLAUDE.md`. Global covers cross-repo assistant defaults; project covers this repo only.

---

## Periodic Hygiene Sweep

Run after major refactors or every ~10 sessions:

1. **Audit for duplication** — search `memory/` for content now in `CLAUDE.md` or `PROJECT.md`. Compress duplicates to pointers.
2. **Resolve contradictions** — search for memory files that disagree with each other. The newer or more thoroughly grounded entry wins; the other becomes a "superseded by" pointer.
3. **Delete superseded findings** — look for `RESOLVED`, `DONE`, `SUPERSEDED` markers, or `session_*_outcomes.md` files older than 7 days.
4. **Compress short stubs** — memory files <500 bytes with no active finding become an `MEMORY.md` index entry or get deleted.
5. **Sweep closed issues** — re-run a keyword search against closed GitHub issues for new "should have" / "root cause" patterns that need promotion to durable memory.

---

## Adaptation by Repo Type

The table above is the *default*. Adapt it to the repo you are applying it to:

### Code repository (typical case)

Use the table as-is. The pattern was developed for code repos with a normal `docs/` tree and a Claude Code plugin installed.

### Operational repository (deployments, infra, runbooks)

- Promote `docs/RUNBOOK.md` to the **primary** store for operational content; demote `PROJECT.md` to a brief overview.
- `memory/` mostly holds **incident postmortems** rather than feature findings.
- Add a `docs/runbooks/*.md` subtree for per-service playbooks.

### Knowledge repository (notes, research, papers)

- `CLAUDE.md` should be short — usually just pointers to `docs/` indexes.
- Treat `docs/` as the primary store; `memory/` is small and reserved for editorial decisions ("we chose X writing style because Y").
- `PROJECT.md` may be omitted entirely if the repo has no goal beyond "collect notes."

### Adjustment guidance

When in doubt, ask: **"Which file would a new collaborator open first to answer this question?"** That file is the canonical home.

---

## How `/align --content` Uses This Skill

The `/align --content` command runs a 4-phase workflow that operationalises this skill:

### AUDIT

- Read `CLAUDE.md`, `PROJECT.md`, `MEMORY.md`, all `memory/*.md`, and the top-level `docs/` listing.
- Measure each file against the size budget table.
- Search for duplicated headings, repeated rules, and content that lives in the wrong tier.

### PROPOSE

- Emit a structured plan: for each over-budget file or duplicated chunk, name the canonical home, the proposed move/pointer, and the expected size impact.
- Group proposals by tier (CLAUDE.md → memory → docs) so the reviewer can approve in batches.

### APPROVE

- The user reviews each proposed move and approves or rejects.
- `--dry-run` skips this and only emits the plan.
- `--auto` accepts all proposals that fall below a risk threshold (e.g. compressions and deletions); content moves between tiers still require explicit approval.

### EXECUTE

- Apply the approved moves: rewrite source files, insert pointer lines, update cross-references.
- Re-measure size budgets after the run.
- Print a delta summary: lines removed from auto-loaded files, files compressed, files deleted.

The skill is the methodology; the command is the workflow runner; the template (`templates/CONTENT_ALLOCATION.md`) is the drop-in artefact for repos that want a local copy of the routing rules.

---

## HARD GATE: Allocation Discipline

**FORBIDDEN**:

- Adding new content to `CLAUDE.md` without first asking: "Does this change behaviour every turn?" — if no, route to memory or docs.
- Letting `CLAUDE.md` exceed 200 lines or `MEMORY.md` exceed 200 lines without a hygiene sweep.
- Duplicating a rule between global `~/.claude/CLAUDE.md` and project `CLAUDE.md`.
- Creating a new memory file when an existing one covers the same topic — extend the existing file instead.
- Leaving a "narrative" copy of a rule in both `PROJECT.md` and `CLAUDE.md` — pick one and use a pointer from the other.

**REQUIRED**:

- Every duplicated chunk MUST be reduced to one canonical copy plus pointers.
- Every `MEMORY.md` index entry MUST be ≤150 chars and point to its source file.
- Every memory file >3 KB MUST either be split or promoted to `docs/`.
- Every `/align --content` PROPOSE phase MUST list the canonical home for each move.

---

## Cross-References

- **planning-workflow** — How content allocation interacts with plan/implement cycles
- **documentation-guide** — Doc style for the content that ends up in `docs/`
- **refactoring-patterns** — When restructuring docs counts as refactoring (same content, different home)
