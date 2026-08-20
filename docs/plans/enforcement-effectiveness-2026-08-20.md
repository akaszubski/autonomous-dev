# Making enforcement measurably effective — session record, 2026-08-20

**Status**: in progress. This document is the durable record of a session whose
findings otherwise live only in a conversation context and a task list.

**Why it exists**: `.claude/plans/` is gitignored (`.gitignore:147`), so nothing
written there survives. `docs/sessions/*.md` is auto-generated and, as of today,
polluted with test-fixture strings ("one two three four five six") written by the
test suite itself — it is not a findings record. Seven GitHub issues and three
commit messages carry pieces of this; nothing carried the whole.

---

## The thesis, in one line

**A convention is not a mechanism, and a mechanism that has never fired is not
enforcement.**

Every mechanism examined closely today was *present*, *readable as protection*,
and *doing nothing*. Not broken — inert. Each one passes a presence check.

---

## What was shipped

| Commit | What |
|---|---|
| `191671de` | #1567 — CI hung, was never slow. Bound every pytest invocation. |
| `209a8e7c` | #1580 — a red unit step was hiding integration and regression entirely. |
| `1e8720d1` | plan-critic Axis 7 (Reachability & Enforceability) + instrument-adequacy + Serena grant. |

### The single most useful result

CI completed for the first time since **2026-05-25**. Every run in that window was
recorded `cancelled` with zero test results. It had been diagnosed as slowness and
the job timeout raised 15 → 60 minutes. **The suite runs in 43 seconds.** One test
never terminated and burned the whole budget.

Root cause: `patch.object(display, 'should_continue', side_effect=[True, False])`
against a boolean *attribute*. `patch.object` installs a `MagicMock`, which is
unconditionally truthy, so the loop's exit condition could never become false and
the `side_effect` list was never consumed. Proven mechanically: truthy 3× running,
`call_count: 0`.

---

## Measurements — the durable evidence

Each of these was one command, and none had been run before. They are the reason
the plan's weak axes were weak: nobody had looked.

### CI, run `32338194218` (first run showing all three suites)

```
unit          242 failed,  9284 passed,  13 skipped, 15 xfailed, 46 xpassed  (45.7s)
integration     0 run,     1745 skipped          -> reports SUCCESS
regression    199 failed,  3163 passed,  89 skipped, 2 errors                (68.8s)
```

- **Integration is green because it runs nothing.** `conftest.py:112` registers an
  opt-in `--run-integration` flag that CI never passes. `pytest` exits 0 on an
  all-skipped run, so green means "nothing ran", not "everything passed". (#1582)
- **46 xpassed** — tests marked expected-to-fail that now pass. A signal drifting
  out of sync in the opposite direction. Not yet investigated.
- Of the 237 unit failures in the earlier run, **77 (32%) are import errors** from
  dependencies CI never installs. The remaining ~160 include **91 AssertionError**
  (the genuine population) and **10 NotImplementedError** — worth checking against
  the anti-stubbing HARD GATE. (#1579)

### Test surface actually executed by CI

12 test directories contain tests. CI executes **3**.

Never run: `hooks/` (5 files), `lib/` (2), `perf/` (1), `property/` (13),
**`security/` (7)**, `spec_validation/` (65), `structural/` (2) = 95 files.
Plus `genai/` (56 files), gated on an org variable that does not exist
(`gh api .../actions/variables` → `total_count: 0`), so it has never run.

### Hook telemetry — `~/.claude/logs/hook_timings_*.jsonl`, 31 days

> Note the paths: `logs/` directly, **not** `logs/timing/`; the record field is
> `hook`, **not** `hook_name`. I got both wrong on first attempt.

```
355,035 rows — 308,971 "exception" (87%), 46,064 "allow"
```

Perfectly bimodal by hook, **zero mixed hooks** — the signature of a code-path
artifact, not real crashes:

```
100% exception:  unified_pre_tool.py (154,969), session_activity_logger.py (149,808),
                 conversation_archiver.py (4,094), task_completed_handler.py (108)
100% allow:      unified_session_tracker.py (22,775), plan_gate.py (11,925),
                 unified_prompt_validator.py (4,781), stop_quality_gate.py (3,659),
                 enforce_file_organization.py (2,691), plan_mode_exit_detector.py (232),
                 validate_project_alignment.py (2)
```

Three-way control (both controls behaved, so the instrument is trustworthy):

```
normal return      -> allow      (negative control OK)
sys.exit(0)        -> exception  <- THE BUG: this is the SUCCESS path
RuntimeError       -> exception  (positive control OK)
```

**A successful hook and a crashing hook are recorded identically.**

### `proof_of_block.py` — the only thing that proves a guard refuses

7 guards, each with positive **and** negative controls (the design is right).
All 7 exercise `unified_pre_tool.py` — **1 of 27 hooks**. Root-pinned via
`parents[1]`. **Not in `install_manifest.json`** (21 script entries ship; this is
not among them), so consumer repos get the hooks with no way to verify they fire.

This is the concrete mechanism behind #1551's 7,140 blocks in autonomous-dev vs
584 in realign on an identical install: not that enforcement differs, but that
only one repo can see whether it fired.

### Merge gating

`ci.yml:260,264` print **"blocking merge"**. `master` has no branch protection and
no required status checks (both endpoints 404). The repo does use PRs — 5 exist,
3 merged. (#1581)

---

## The defect shape — one pattern, many instances

Every finding is the same shape: **a relationship was never asserted, only a
presence.**

| Instance | Present | Inert because |
|---|---|---|
| `ProgressDisplay.stop()` | method exists, docstring claims signal-handler use | zero callers |
| `truncate_message()` | helper exists next to the renderer | zero callers; output overflows |
| smoke `--timeout=300` | a bound exists | equals its own 300s job cap — races the cancellation |
| `test_every_ci_pytest_invocation_...` | a guard exists, named for the class | read one file, one job; 3 of 6 unbounded |
| integration step | a suite exists and is green | 1,745 skipped, 0 executed |
| "blocking merge" | a message exists | nothing can block |
| Axis 7 score row | an axis exists | regex had no `&` — silently unparseable |
| `decision_shape` column | a column exists, 31 days of data | success and crash indistinguishable |

The fix in every case was to assert a **relationship** — flag vs cap, name vs
search space, definition vs call site, collected vs executed — not existence.

### The self-referential proof

The Axis 7 case is the strongest evidence the axis was needed.
`plan_critic_verdict.py` parsed axis names with `[A-Za-z0-9 _\-/]` — no ampersand.
A row `| Reachability & Enforceability | 2 |` did not match: no exception, no
warning, axis absent from `axis_scores`. The consuming hook requires only
"at least 3 numeric entries" (`unified_session_tracker.py:1209`), so a 7-axis
critique would have persisted 6 and **every gate would have reported success**.

The axis introduced to catch mechanisms that cannot fire would itself have been
unable to fire. Fixed the regex rather than renaming the axis — renaming would
have been the fix scoped to the instance.

---

## Corrected model — hook inventory and invocation graph (measured 2026-08-20, second pass)

An earlier section of this document says "27 hooks". **That is wrong** — it counted
`*.py` only. Recording the correction here rather than editing the original, so the
error and its cause both stay visible.

### There are 32 hooks

```
26 python + 6 shell = 32
```

The six shell hooks were invisible to every count in this document's first pass.
One of them, `PreToolUseWrite-protect-sensitive.sh`, is **refusal-capable** and has
never been measured.

### Three registration surfaces, and none is complete alone

| Surface | What it declares |
|---|---|
| settings files (5 of them, incl. global `~/.claude/settings.json`) | the **event** binding |
| per-hook `.hook.json` sidecar (32) | `type` (utility 21 / lifecycle 12) and `active` — **never an event** |
| programmatic invocation | utilities called by other code |

Only **10 hooks are event-bound**. The rest are utilities invoked programmatically.
A sidecar says *what a hook is*, never *when it fires* — so neither surface answers
"does this run?" on its own.

This resolved the `enforce_orchestrator` puzzle: 248 real blocks across 48 days from
a hook registered in no settings file. It is `type: utility` with three programmatic
invokers. Working as designed; the earlier confusion came from treating the settings
template as the registry.

### The refusal-capable set — six hooks, three proven

| Hook | Protocol | Real blocks |
|---|---|---|
| `unified_pre_tool.py` | `permissionDecision: deny` | 8,093 |
| `unified_prompt_validator.py` | `decision` (UserPromptSubmit) | 254 |
| `enforce_orchestrator.py` | `exit 2` | 248 |
| `plan_gate.py` | `permissionDecision: "block"` — **not in the enum** | **0** (#1589) |
| `enforce_file_organization.py` | `_deny()`, no recording call | **0** — unknowable |
| `PreToolUseWrite-protect-sensitive.sh` | shell | **unmeasured** |

Three refuse and are observed doing it. Three do not appear in the block log at all,
for three *different* reasons: an invalid enum value, a missing recording call, and
never having been looked at.

### Two protocols, not drift

```
PreToolUse       -> permissionDecision : allow | deny | ask
UserPromptSubmit -> decision           : block
```

Both are genuine Claude Code contracts tied to different events. Any canonical sink
must take the protocol as a parameter rather than collapsing them.

### Corrections this pass made to this document's own numbers

1. **"27 hooks"** -> 32. Counted `*.py` only.
2. **"9,103 block records"** -> 9,163 rows, of which **8,595** are refusals. `mode_skip`
   (488) is skip telemetry, not a block. `hook_perf_report.py:39` already encoded the
   distinction in `BLOCK_SHAPES`.
3. **"5 hooks have blocked"** -> 3. `plan_gate` and `plan_mode_exit_detector` appear in
   the log only as `mode_skip`, and only from test-marked sessions.
4. **A heuristic treating empty `session_id` as a test marker** was refuted by a positive
   control: a genuine block from this session (the one that refused a write to
   `plan-critic.md`) carries an empty `session_id`. It would have misclassified 8,594
   real blocks as test noise.

Every one of these is the same error: confirming that records exist, then assuming what
they are. The positive control is what caught the fourth before it was published.

## Issues filed

| # | Finding | Needs |
|---|---|---|
| #1576 | `safety-net.yml` red 40/40 runs — `--cov=src`, no `src/` exists | disposition |
| #1577 | Two display defects the hang hid since May | fix |
| #1578 | reviewer fabricated a test-gate convention; lacks `testing-guide` skill | fix |
| #1579 | 77 of 237 unit failures are missing CI deps | fix |
| #1580 | red unit step suppressed two suites | **shipped** `209a8e7c` |
| #1581 | "blocking merge" vs unprotected master | **user decision** |
| #1582 | integration green over 0 of 1745 tests | fix |

---

## Open work, in dependency order

**Pre-rescore** (the plan sat at 2.83 because its weak axes rested on unverified
premises; these produce the evidence):

1. ~~plan-critic Axis 7 + instrument adequacy~~ — **done**, `1e8720d1`
2. `hook_timing.py:375` + `hook_safety.py` — in progress. See the trap below.
3. `proof_of_block.py` — portable via `repo_detector.py`, then add to manifest.

**Then**: rescore the plan against the corrected critic, and persist the result.

**Independent**: #1576, #1577, #1579, #1582 (fixes); #1581 (decision);
#1570 (stashed, FAIL-Critical, do not ship).

---

## Cautions — things that will bite whoever picks this up

- **`hook_timing.py:375` has a trap.** The one-file fix is actively wrong.
  `hook_safety.py:110` (`except BaseException`) converts crashes into
  `SystemExit(0)` — so excluding `SystemExit` at `:375` would make genuine crashes
  record as `"allow"`. That is worse than today: currently uselessly pessimistic,
  then confidently wrong in the direction that hides failures. The crash must be
  marked before the `SystemExit` propagates through the timer.

- **Do not predict counts; measure them.** I stated 136 import failures by counting
  log *occurrences* rather than unique tests — each test emits the line twice. The
  real number is 77. Corrected on #1579 after filing.

- **Do not trust a probe that returns zero.** Two of my probes returned nothing
  because I had the wrong log directory and the wrong field name. A zero from an
  unverified instrument is worth nothing.

- **Beware fixture data in logs.** I nearly reported "11,324 passed" — that string
  is a *parametrized test argument* inside
  `test_fix_forward_capture_failure.py::test_summary_shapes`, not a result.

- **`@pytest.mark.skip` is forbidden** (`skills/testing-guide/SKILL.md:643`,
  `commands/implement.md:1165`) — two resolutions, not three. A reviewer demanded
  skip markers citing a three-option convention that does not exist. Rejected;
  the tests stay red and visible under #1577. My own memory file carried the same
  stale rule and has been corrected.

- **Stashes**: `stash@{0}` = #1570 (FAIL-Critical, DO NOT SHIP),
  `stash@{1}` = #1569. Never `git stash` while these exist.

---

## Known gaps, stated rather than hidden

- **Budget mode still scores 4 axes.** `implement.md` STEP 5.5b — so the
  in-pipeline critique gate, the one that runs most often, does **not** score
  reachability. Adding it touches 5 files wired to separate spec tests.
- **`proof_of_block.py` covers 7 guards across 27 hooks.** Portability first;
  widening coverage is separate work.
- **`plan-critic` is absent from `READ_ONLY_AGENTS`** in
  `test_agent_registry_consistency.py:51`, so INV-4 never checks it despite it
  being read-only by design.
- **`test_granted_serena_tools_cover_the_navigation_prose` is instance-scoped** —
  it hardcodes a 4-agent dict rather than deriving every agent declaring a Serena
  tool, so plan-critic is invisible to it.
- **`plan-critic.md`'s PROCEED template says "minimum 2 rounds"** while its own
  HARD GATE says 3.
- **The plan never converged**: 2.0 → 2.17 → 2.83 → 2.83 → 2.83. Flat for three
  rounds is the skill's own *stuck* signal, not *converged*.
- **`docs/sessions/*.md` is polluted by test runs** — the suite writes fixture
  strings into it. Not filed.
