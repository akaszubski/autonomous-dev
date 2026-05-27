# Content allocation

**Rule: one topic, one home.** If a piece of content lives in two places, one is wrong — the canonical home owns it; the other becomes a one-line pointer.

## Where things go

| Store | Loaded | Owns | Does NOT own |
|-------|--------|------|--------------|
| `~/.claude/CLAUDE.md` (global) | every turn, every repo | Assistant default behaviour; user's machines, SSH, session history queries | Anything project-specific |
| `CLAUDE.md` (this repo) | every turn, this repo | Hard rules, gates, canonical paths, pointers, top-N gotchas | Vision, purpose, architecture, history, current state, deep reference |
| `.claude/PROJECT.md` | session start | Purpose, GOALS, SCOPE, CONSTRAINTS, alignment criteria, project philosophy | Behaviour rules; operational sequences; full architecture diagrams; current state |
| `memory/MEMORY.md` + `memory/*.md` | MEMORY auto-loaded; files retrievable | Durable lessons (with *why*), findings, calibration, active state | Hard rules; full architecture |
| `docs/RUNBOOK.md` | on demand | Operational sequences (periodic maintenance, common queries, how-do-I) | Architecture; rules |
| `docs/architecture/*.md` | on demand | High-level system architecture, layers, diagrams, ADRs | Behaviour rules; deep component internals |
| `docs/<TOPIC>.md` (per-domain) | on demand | Deep reference per topic (testing, security, hooks, libraries) | Behaviour; vision |
| GitHub issues | on reference | Current/open/closed work, decision threads | Anything else |

## Routing decision algorithm

When adding new content, walk this 9-step ordered list and stop at the first match:

1. **Behaviour rule** ("always do X / never do Y") → `CLAUDE.md` Critical Rules section.
2. **Scope / architecture / why** → `.claude/PROJECT.md`.
3. **Durable lesson + the *why*** → `memory/feedback_*.md` (+ one-line index entry in `MEMORY.md`).
4. **Active state / current finding** → `memory/finding_*.md` (+ index entry).
5. **Operational sequence** ("how do I do X") → `docs/RUNBOOK.md`.
6. **Reference data** (registries) → `docs/<REGISTRY>.md`.
7. **Pitfall / gotcha** (with reproducer) → memory if recent + repeatable; `docs/<TOPIC>.md` if catalogued.
8. **Deep architectural detail** → `docs/<TOPIC>.md`.
9. **Plugin-user-facing fix** → plugin's `docs/TROUBLESHOOTING.md`.

If a topic spans two stores: the *narrative* lives in PROJECT.md or docs; the *rule* lives in CLAUDE.md; both reference each other as 1-line pointers.

## Size budgets

| File | Target | Hard ceiling | Why |
|------|--------|--------------|-----|
| `CLAUDE.md` | ≤100 lines | 200 | Loaded every turn. Hook should warn above 200. |
| `.claude/PROJECT.md` | ≤150 lines | 200 | Loaded at session start. Above 200 = operational drift. |
| `MEMORY.md` | ≤150 lines | 200 | Truncated above line 200 when auto-loaded. |
| `memory/*.md` (individual) | 1–3 KB | 3 KB | >3 KB usually means it should be a `docs/` page. |

Additional rules:

- `MEMORY.md` entries must be ≤150 chars. If you cannot summarise in one line, the underlying file needs splitting.
- Memory files below 500 bytes with no active finding should be compressed to an index entry or deleted.
- Never duplicate content between global and project `CLAUDE.md`. Global covers cross-repo defaults; project covers this repo only.

## Periodic hygiene

After major refactors or every ~10 sessions:

1. Search memory for content now in `CLAUDE.md` or `PROJECT.md` → compress to pointer.
2. Search for memory files that contradict each other → resolve.
3. Delete superseded findings (look for `RESOLVED`, `DONE`, `SUPERSEDED` markers, or `session_*_outcomes.md` files >7 days old).
4. Compress short stubs (<500 bytes, no active finding) to `MEMORY.md` index entry or delete.
5. Re-run keyword sweep against closed GitHub issues for new "should have" / "root cause" patterns.

## Adaptation by repo type

The table above is the *default*. Adapt it to the repo you are applying it to:

- **Code repository (typical)**: use the table as-is.
- **Operational repository** (deployments, infra, runbooks): promote `docs/RUNBOOK.md` to the primary store; `memory/` holds incident postmortems instead of feature findings.
- **Knowledge repository** (notes, research): `CLAUDE.md` is short and mostly pointers; `docs/` is the primary store; `PROJECT.md` may be omitted.

When in doubt, ask: **"Which file would a new collaborator open first to answer this question?"** That file is the canonical home.

## Applying this to a new repo

1. Copy this file to `docs/development/CONTENT_ALLOCATION.md` of the target repo.
2. Adapt the table rows to the repo's actual file layout.
3. Run the periodic hygiene sweep against existing content.
4. Add a one-line pointer in the target repo's `CLAUDE.md` so future contributors discover the rules.

Run `/align --content` to audit and apply this pattern automatically.
