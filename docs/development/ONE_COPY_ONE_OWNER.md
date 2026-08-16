# One Copy, One Owner

**Proposal — restructure the deployment topology of autonomous-dev**

- Status: **step 1 verified**, awaiting approval for step 2
- Date: 2026-08-16
- Evidence session: `cc5ba4af`
- Related: #1519, #1520, #1521, #1522, #1523

---

## The problem in one sentence

Every file exists in three places, four files decide which copies run, and nothing verifies they agree.

```
one hook lives in:   plugins/autonomous-dev/hooks/
                     <repo>/.claude/hooks/
                     ~/.claude/hooks/

one lib lives in:    plugins/autonomous-dev/lib/
                     <repo>/.claude/lib/
                     ~/.claude/lib/

registration in:     <repo>/.claude/settings.json
                     <repo>/.claude/settings.local.json
                     ~/.claude/settings.json
                     ~/.claude/settings.local.json
```

Three copies x four registration surfaces, across five repos and two machines.

---

## What this cost, measured in one session

| Defect | Cause |
|---|---|
| 7 dead implementer dispatches | Fix kept landing in a copy the failing path doesn't load |
| 4 fixes live in 1 repo of 5 | Copies drift independently; deploy touched one |
| #1522 hooks fire twice | Same hook registered in two tiers |
| #1519 validator always fails | Checks the repo tier against a global-tier expectation |
| A P0 filed that was wrong | One tier measured and reported as the total |
| `deploy-all.sh` silently reverted a fix | The live file is not the source of truth |

Roughly one full working session. This is a normal day for this shape, not an unlucky one.

---

## The tell

Every fix so far has been *"add another checker."* There are now five: `KEY_FILES` validation, tier-aware validators, duplicate detection, settings sync-and-compare, and `check_runtime_drift.py`.

They still missed it. `check_runtime_drift.py` is the sixth. **When the sixth detector is the fix, the structure is wrong.**

---

## STEP 1 — VERIFIED

The proposal originally carried one unverified assumption: whether Claude Code's plugin loader could serve hooks from a single installed location.

**That framing was wrong, in our favour.** Hook registrations in `settings.json` are shell commands carrying a path:

```
python3 "${CLAUDE_PROJECT_DIR:-...}/.claude/hooks/session_activity_logger.py"
```

Nothing forces `.claude/hooks/`. Any absolute path works. No loader feature is required.

Also established: `~/.claude/plugins/data/` contains only `pdf-viewer-inline`. Despite shipping a valid `plugin.json` declaring native `components`, **autonomous-dev has never been installed as a native plugin** — it is entirely hand-deployed by `cp -r`.

### Test: does a hook work from one arbitrary location, with no `.claude/` copies?

Plugin copied to a fresh temp location with a unique marker planted in that copy's lib; target repo created with **no** `.claude/hooks` and **no** `.claude/lib`.

```
TEST 2 (load-bearing) — which lib copy loaded?
  loaded from   : <temp>/installed/autonomous-dev/lib/tool_intent.py
  marker present: True
```

Single-location lib resolution works. Hooks compute lib as `<hook_dir>.parent/'lib'`, so the resolution follows the hook wherever it lives.

### Control — because the first enforcement test returned `allow`

The initial protected-path write was **allowed**, which could have meant enforcement was location-dependent. A control distinguished scenario from location:

```
synthetic repo — same payload, three hook locations:
  single canonical (temp)  -> allow
  repo source              -> allow
  global deployed          -> allow      => scenario, not location

real repo — positive control:
  single canonical (temp)  -> deny  "BLOCKED: Direct edit to 'pipeline_state.py'..."
  global deployed          -> deny  (identical)
```

All locations agree on the synthetic repo, and both deny identically on the real one. **Enforcement is location-independent.** The foundation holds.

---

## What changes

**1. One copy of the code.** Hooks resolve to a single installed location. No `<repo>/.claude/lib`, no `<repo>/.claude/hooks`.

**2. One registration, generated.** A single manifest declares `hook -> event -> matcher`. Settings files are generated from it, never hand-edited. "Do the tiers agree?" stops being a question — there is one input.

**3. Scope decided at runtime.** The hooks already do this: `repo_detector.is_autonomous_dev_repo()` returns "Non-autonomous-dev project — enforcement skipped." A globally-registered hook already knows whether to act. Per-repo registration duplicates a job the hook does better. Opt-out already exists as `.claude/.bypass`.

**4. One health command.** `/health-check` answers: what is running, is it current, is it consistent.

---

## What gets deleted

This is subtractive. It removes code rather than adding it:

- `KEY_FILES` partial validation
- tier-aware validators
- duplicate detection
- settings sync-and-compare logic
- `check_runtime_drift.py` — never needs to land
- 19 hook files registered nowhere: wire them or remove them

---

## What does NOT change

**Nothing about enforcement.** Not one agent, gate, or specialist is removed.

- 17 specialist agents — untouched
- Fresh context per agent — untouched
- HARD GATEs with JSON block decisions — untouched
- The pipeline sequence — untouched

`CLAUDE.md` says *"Don't simplify, redesign, or consolidate agents."* That rule is respected. The agents are the mechanism and they worked correctly throughout the session that produced this document — the #1296 gate refused every direct edit, the write gate blocked an unauthorised script, the completeness gate held. **The gates are why the system is trustworthy. The copies are why it breaks.**

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Enforcement silently stops in a repo | **High** — worse than the current problem | Proof-of-block (#1520) verifies a gate still refuses, at every step |
| Consumer repos without global install lose coverage | High | Runtime scope check (#3); must be proven before removing any tier |
| Half-migrated state across 5 repos + 2 machines | Medium | One repo at a time, each fully verified before the next |
| Effort | Medium | Multiple sessions |

**Rollback:** every step is one redeploy from the current state, as long as `plugins/autonomous-dev/` remains the source of truth. It does.

---

## Migration order

1. ~~Verify the single-location assumption.~~ **DONE — verified above.**
2. **Build proof-of-block (#1520)** — the safety net. Nothing else moves until enforcement can be *demonstrated* rather than assumed.
3. **autonomous-dev only.** Collapse to one copy, one owner. Verify every gate still refuses.
4. **One consumer repo** (suggest `spektiv` — least critical). Verify.
5. **Remaining three.** Verify each.
6. **Mac Studio.**
7. **Delete the now-dead machinery.**

Steps 3-6 are individually reversible.

---

## Why CI never caught any of this

Worth recording, because it explains why "more CI" is not the answer.

Every defect above is **silent by construction**, and the continuous-improvement-analyst is a log reader. A hook that was never registered produces no log lines, so absence of evidence reads as absence of problems.

- **Existence is not execution.** `✓ all settings.json hooks exist on disk` passed while three fixes sat inert.
- **Nothing compares source to runtime.** Only 3 of 224 files were ever compared, and none of the drifted ones were among them.
- **Tests import from source; production loads the deployed copy.** Green tests were true and irrelevant.
- **Reachability is never computed.** 19 hooks registered nowhere look identical to 19 hooks working.
- **A 560-failure red floor swallows any new signal** (#1523).
- **CIA is session-scoped.** Cross-repo, cross-machine deployment state is outside its frame.

You cannot detect a guard that never fires by reading logs, because it produces no logs. That is the argument for #1520: stop waiting to observe enforcement and instead require the guard to refuse something on demand. A guard with no current proof is reported as UNVERIFIED rather than counted as working.
