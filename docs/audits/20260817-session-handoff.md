# Session handoff — 2026-08-16/17

Written because `SessionStart-batch-recovery.sh` only fires on `source=compact`,
not on a manual restart, so there is no automatic context carry-over. This file
is the carry-over.

Session: `cc5ba4af` · Repo: `autonomous-dev` @ `70a6b896`

---

## Restart guidance

**Restart is needed.** `.claude/settings.json` changed at `2026-08-16 10:35:35`;
sessions started before that hold stale hook registrations. Declarative surfaces
under `.claude/` — settings, commands, agents, skills — load at session start and
cannot change under a running session.

**Caveat on an earlier claim.** I reported "ALL LIVE — 8 fixes × 6 locations".
That verified **files on disk**. It did NOT verify that any running session had
loaded them. The honest chain:

```
committed -> yes (6 commits)
deployed  -> yes (files verified, all tiers, all repos)
loaded    -> UNVERIFIED for sessions started before the deploy
```

This matters for diagnosis: dispatches kept failing after the sentinel fix was
deployed. I attributed that to the cache-pop bug (#1512). A stale in-session
load is an equally good explanation and was never ruled out.

---

## Shipped and verified

| Commit | What |
|---|---|
| `4bd070fe` | atomic sentinel writes, CORRUPT-vs-ABSENT detection, #1503 classifier wired to its production call site |
| `b96d0b2c` | known-failures baseline — suite regains a signal |
| `bbd57827` | proof-of-block harness + `ONE_COPY_ONE_OWNER` proposal |
| `7c745c51` | proof-of-block registry widened to 7 guards |
| `34bf65b6` | proof artifact re-recorded against a clean tree |
| `5c56b28f` | #1518 — 35 spec tests dead since April, repaired |
| `31a6e5a1` | #1523 — skill roster derived from disk; 97 failures -> 10 real findings |
| `d9ecd32a` | #1526 — restored skill context to security-auditor, planner, implementer |
| `70a6b896` | #1528 — archived-code rule + no-counts-in-prose, landed RED on purpose |

**One command answers "is enforcement working?"**

```
python3 /Users/akaszubski/Dev/autonomous-dev/scripts/proof_of_block.py
```

Currently `7/7 guards PROVEN`. Each watched refusing a real action AND permitting
the legitimate one.

**Test suite baseline: 560 -> 436** (`docs/audits/known-failures-baseline.txt`).
Across four clusters, 196 failures examined yielded **3 real bugs**. The rest was
years of unmaintained refactors.

---

## Open, filed with measured evidence

- **#1512** — sentinel: root cause is `pop_invocation()` keyed by `subagent_type`,
  so a phantom `SubagentStop` claims the LIVE dispatch's generation token. The
  queue-drain in `scratchpad/cache_guard.py` is a WORKAROUND, not a fix.
- **#1516** — plans prompt. **Premise now CONFIRMED** by user observation:
  spektiv holds `Edit(.claude/plans/**)` (index 18 of 26, predating the later
  bash rules) and an Edit still prompted. Allow-rules do not override `.claude/`
  sensitivity protection.
- **#1517** — prompt-shrink guard. Blocked 5 dispatches this session; every one
  cleared by padding, which is the behaviour it exists to punish. Also fires
  AFTER `PreToolUse` has armed a sentinel, leaving orphaned state that feeds #1512.
- **#1518** — CLOSED, fixed.
- **#1519** — deploy validator is tier-blind; prints a false error every run.
- **#1521** — runtime != source; only 3 of 224 files were ever compared.
- **#1522** — 4 hooks registered in both tiers, executing twice per event.
  `deploy-all.sh` RE-CREATES the duplicate, so `settings.json` cannot be the fix site.
- **#1523** — 436 remaining failures, triaged by cause.
- **#1524** — `--record` stamps HEAD without checking whether the tree is dirty.
- **#1525** — `BrownfieldRetrofit` accepts a FILE as `project_root`.
- **#1526** — CLOSED, fixed.
- **#1528** — archived-code rule unenforced: 14 real references (count moved
  4 -> 13 -> 20 -> 14; every correction came from a control failing).
- **#1530** — audit of the duplicated-fact class: 6 state dirs, 2 independent
  `is_worktree()` implementations, templates disagreeing about a hook.

---

## Blocked, needs a decision

**`docs/plans/plan-storage-location.md` — plan-critic verdict BLOCKED (1.7).**
Premise confirmed, remedy wrong: moving plans to `docs/plans/` would silently
neuter `plan_gate.py`. That gate works today ONLY because `.claude/plans/` is
gitignored and empty on a fresh clone; `docs/plans/` is tracked and ships
populated, so every clone would arrive pre-satisfied. My own test scenario would
have passed in an empty tmpdir while the production gate was dead.

Also found: `.codex/hooks/plan_gate.py` is a divergent SECOND copy of the gate,
and `skills/planning-workflow/SKILL.md` is injected into the planner — both
missing from my inventory, which was wrong by 4x.

**`ONE_COPY_ONE_OWNER.md` — step 1 verified, step 3 needs approval.**

---

## The finding that matters most

The continuous-improvement-analyst **last ran 2026-08-09**. On that day it filed
16 issues, including:

- `#1484` "Agent-dispatch sentinel is systematically unreliable"
- `#1485` "prompt-integrity shrinkage gate false-positives"

**All 16 are CLOSED. Both defects are still live.** I spent seven dispatches
rediscovering #1484 today; #1485 blocked me five times.

Detection worked. Closure was ceremonial — #1485 was closed with no comment at all.

And the loop is deadlocked: CIA is dispatched at STEP 15, the last step. The
sentinel bug it reported prevented pipelines from reaching STEP 15, so CIA stopped
running, so nothing re-reported it. **The improvement loop was switched off by the
defect it had just reported**, and a silent agent produces no signal, so nothing
noticed for eight days.

Two cheap fixes: move CIA off the terminal step, and add a liveness check
("CIA has not run in N days" is one query).

---

## Method notes worth carrying

- **Instruments lie.** Every count that moved today moved because a CONTROL
  failed, never because anyone re-read more carefully. A probe without a negative
  control produces confident nonsense — it happened four times.
- **Serena for "who depends on this", grep for "where is this string."** Using
  grep for dependency questions gave wrong answers twice: blind to single-word
  names, and unable to tell a symbol reference from a string literal.
- **Land gates RED.** A gate committed green proves nothing.
- Machine state: Mac Studio unreachable (LAN + Tailscale) — remote deploy pending.
