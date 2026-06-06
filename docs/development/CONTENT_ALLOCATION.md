# Content allocation

**Rule: one topic, one home.** If a piece of content lives in two places, one is wrong — the canonical home owns it; the other becomes a one-line pointer.

## Where things go

| Store | Loaded | Owns | Does NOT own |
|-------|--------|------|--------------|
| `~/.claude/CLAUDE.md` (global) | every turn, every repo | Assistant default behaviour; user's machines, SSH, session history queries | Anything project-specific |
| `CLAUDE.md` (this repo) | every turn, this repo | Hard rules, gates, canonical paths, pointers, top-N gotchas | Vision, purpose, architecture, history, current state, deep reference |
| `.claude/PROJECT.md` | session start | Purpose, GOALS, SCOPE, CONSTRAINTS, alignment criteria, pipeline philosophy | Behaviour rules; operational sequences; full architecture diagrams; current state |
| → note | `.claude/PROJECT.md` is a **symlink** to the repo-root `PROJECT.md` (git mode `120000`). Edit the root file; the symlink resolves automatically. Do NOT replace the symlink with a copy. |
| `memory/MEMORY.md` + `memory/*.md` | MEMORY auto-loaded; files retrievable | Durable lessons (with *why*), findings, calibration, active state | Hard rules; full architecture |
| `docs/RUNBOOK.md` | on demand | Operational sequences (periodic maintenance, batch finalize, resumes, common queries) | Architecture; rules |
| `docs/ARCHITECTURE-OVERVIEW.md` | on demand | High-level system architecture, layers, pipeline diagram | Behaviour rules; deep component internals |
| `plugins/autonomous-dev/docs/COMMANDS.md` | on demand | User-facing command catalogue (shipped with plugin) | Dev-only flags |
| `docs/HOOKS.md`, `docs/AGENTS.md`, `docs/SKILLS.md`, `docs/LIBRARIES.md` | on demand | Per-domain registries | Behaviour; vision |
| `docs/development/*.md` | on demand | Maintainer-facing methodology (this file, planning workflow, prompt engineering) | User-facing reference |
| `docs/PIPELINE-MODES.md`, `docs/TESTING-STRATEGY.md`, `docs/SECURITY.md`, etc. | on demand | Deep reference per topic | Behaviour; vision |
| `plugins/autonomous-dev/docs/TROUBLESHOOTING.md` | on demand | Plugin-user-facing fixes for stuck states, install issues | Maintainer-internal flows |
| GitHub issues | on reference | Current/open/closed work, decision threads | Anything else |

## Routing rule when adding content

1. **Behaviour rule** ("always do X / never do Y") → `CLAUDE.md` Critical Rules section.
2. **Architecture / scope / why** → `.claude/PROJECT.md`.
3. **Durable lesson + the why** → `memory/feedback_*.md` (+ one-line index entry in `MEMORY.md`).
4. **Active state / current finding** → `memory/finding_*.md` (+ index entry).
5. **Operational sequence** ("how do I do X") → `docs/RUNBOOK.md`.
6. **Reference data** (hooks, agents, skills, libraries) → `docs/<REGISTRY>.md`. User-facing command catalogue → `plugins/autonomous-dev/docs/COMMANDS.md` (scripts/validate_structure.py enforces this filename split).
7. **Pitfall / gotcha** (with reproducer) → memory if recent + repeatable; `docs/<TOPIC>.md` if catalogued.
8. **Deep architectural detail** → `docs/<TOPIC>.md` (e.g. `HOOK-COMPOSITION.md`, `MCP-ARCHITECTURE.md`).
9. **Plugin-user-facing fix** → `plugins/autonomous-dev/docs/TROUBLESHOOTING.md`.

If a topic spans two stores: the *narrative* lives in PROJECT.md or docs; the *rule* lives in CLAUDE.md; both reference each other as 1-line pointers.

## When updating

- Before adding new content, ask: "Does this duplicate something already in another file?" If yes, the older one becomes a pointer.
- Memory files target 1–3 KB. >3 KB → split or move to `docs/`.
- `MEMORY.md` entries must be ≤150 chars. If you can't summarise in one line, the underlying file needs splitting.
- `CLAUDE.md`, `MEMORY.md`, and global `~/.claude/CLAUDE.md` are loaded every turn — adding a line there has compounding cost across the project's lifetime. Default to memory or docs; escalate to CLAUDE.md only if the rule changes behaviour every turn.
- Never duplicate content between global and project CLAUDE.md. Global covers cross-repo assistant defaults; project covers this repo only.

## Size budgets

| File | Target | Hard ceiling | Why |
|------|--------|--------------|-----|
| `CLAUDE.md` | ≤100 lines | 200 | Loaded every turn. Hook `validate_claude_md_size.py` warns above 200. |
| `.claude/PROJECT.md` | ≤150 lines | — | Loaded at session start. Above 150 = operational drift, not architecture. |
| `MEMORY.md` | ≤200 lines | 200 | Truncated above line 200 when auto-loaded. |
| `memory/*.md` (individual) | 1–3 KB | 3 KB | >3 KB usually means it should be a `docs/` page. |

## Periodic hygiene

After major refactors or every ~10 sessions:
1. Search memory for content now in `CLAUDE.md` or `PROJECT.md` → compress to pointer.
2. Search for memory files that contradict each other → resolve.
3. Delete superseded findings (look for "RESOLVED", "DONE", "SUPERSEDED" markers, or `session_*_outcomes.md` files >7 days old).
4. Compress short stubs (<500 bytes, no active finding) to MEMORY.md index entry or delete.
5. Re-run keyword sweep against closed GitHub issues for new "should have" / "root cause" patterns.

## How this pattern was developed

This pattern was proven first in [realign](https://github.com/akaszubski/realign) (CLAUDE.md 254→83, MEMORY.md 259→113, 9 memory files relocated). Dogfooded here on autonomous-dev's own files as Stream A of Issue #1120 before being extracted into the plugin (Stream B, Issues #1121–#1124) so other repos can run `/align --content` to apply it.

If you're applying this pattern to a new repo: copy this file, adapt the table rows to that repo's file layout, run the sweep, then add the file paths to whatever validator the repo uses.
