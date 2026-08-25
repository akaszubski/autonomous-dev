# GOAL — Enforcement Proven Everywhere, and Smaller

**Created**: 2026-08-24 · **Revised**: 2026-08-25 (v3 — two adversarial evaluations against stated intent; #1663 answered; 13 internal contradictions fixed)
**Status**: ACTIVE
**Owner**: Andrew Kaszubski (solo dev)
**Supersedes**: `GOAL_2026-07-31.md`

---

## 1. Mission

The product's claim is that its guarantees hold. Measured 2026-08-24, they do not: **4 of 8
block-capable guards fail open silently** under fault injection *in this repo with the full
install*, and realign and spektiv have 27 hooks apiece with **0 proof artifacts**. Meanwhile
the system carries **142,869 lines** of enforcement code, 1,733 lines of agent-improvement
machinery invoked by nothing, 414 tests that have never run in CI, and 262 open issues.

**Correction, 2026-08-25 (MEASURED).** This paragraph originally listed a `SoftFailureTracker`
"requested by 0 tests but advertised in 2 docs" as a sixth dead mechanism. That was **wrong**.
`tests/unit/genai/test_genai_client.py` and `tests/unit/genai/test_soft_failure_thresholds.py`
hold 51 tests that exercise it and pass **51/51** (`pytest tests/unit/genai/ -q`). They read as
absent because both use a bare `from conftest import ...` (introduced 2026-04-11 in #772), which
binds to `tests/integration/conftest.py` whenever `tests/unit` and `tests/integration` are
collected together — so both files raise `ImportError` at collection under the repo's own
`CANONICAL_BASELINE_CMD`. The original "0" was inherited from a run in which they never executed:
**a count over a population that failed to collect, which is the same defect as a pass over zero.**
`SoftFailureTracker` is therefore resolved **WIRED**, not a deletion candidate — acting on the
original line would have deleted 51 passing tests. The import defect is filed separately.

Both halves are the same disease. Unproven guards create false security; unused machinery
creates the impression of coverage. This goal makes enforcement **provable** and the system
**smaller** — and treats an increase in enforcement code without a matching increase in proven
guards as a failure, not progress.

Five properties, from the stated intent: **effective** (guards demonstrably fire), **simple**
(less code, no dead mechanisms), **accurate** (both arms, measured error rates), **durable**
(holds in every repo), **consistent** (one canonical mechanism per rule).

## 2. Definition of Done

**Effective — guards demonstrably fire**
- [ ] `proof_of_block.py` reports **0 guards failing open silently** (baseline: 4 of 8)
- [ ] Every guard shows a **REFUSES and a PERMITS** row — one arm does not count (#1617)
- [ ] Committed proof artifacts in **realign AND spektiv** (baseline: 0 in both)
- [ ] **CORRECTED 2026-08-25 — "27 hooks apiece" counts files, not enforcement.** MEASURED across
      project, project-local and user-global settings layers in both repos: **33 hook files on
      disk, 6 bound in settings, and exactly ONE of the six is a blocking gate**
      (`unified_pre_tool.py`; two of the other five are `session_activity_logger.py`, which
      logs). Identical in realign and spektiv because both match `settings.default.json`.
      autonomous-dev binds **16** for itself; the strictest consumer template binds **8**. So the
      product applies ~2× the enforcement to itself that it ships to anyone, and `plan_gate.py`,
      `enforce_file_organization.py`, `stop_quality_gate.py` and `unified_prompt_validator.py`
      reach **no** consumer template at all — not even strict mode. Recorded on #1640.
      **Not proven:** that the 27 unbound files are dead — `batch_permission_approver.py` is
      dispatched from inside `unified_pre_tool.py` rather than bound, so some may be reachable
      through the one gate that is. That distinction is #1674. Quote 6-of-33; do not quote
      "27 dead".

**Simple — fewer mechanisms, not fewer lines**
- [ ] **Count MECHANISMS, not lines.** Line count is the wrong denominator — `lib/*.py` is
      120,001 of the 142,869 and is mostly non-enforcement code, so "net lines down" is
      satisfiable by deleting unrelated library code. The metric is the **named dead-mechanism
      list**, each item resolved to `WIRED` or `DELETED`, no item left `UNRESOLVED`:
      | Mechanism | Baseline | Target |
      |---|---|---|
      | Dead guards (#1612) | **CORRECTED 2026-08-25: not 5.** `enforce_orchestrator.py` is LIVE — 42 recorded refusals, latest 2026-08-24, through an invoker found in no settings file and no tracked source (#1675). `PreToolUseWrite-protect-sensitive.sh` is a deferred policy decision, not dead code (#1673). The remaining 3 are unregistered and have never refused, but are **not provably unreachable**: no sink distinguishes "never invoked" from "invoked and allowed" (#1674). Deletion halted, nothing removed. | 3 pending #1674 |
      | ~~`SoftFailureTracker`~~ | **RESOLVED WIRED 2026-08-25** — the "0 tests" baseline was false; 51 tests exercise it and pass 51/51. See the Correction above. | done |
      | Mutation testing (#1668) | **ADDED 2026-08-25.** `mutmut` pinned, `[mutmut]` in setup.cfg, runner script executable, baseline report committed — and it has **never run**: every cell is `TBD`, `import mutmut` fails, and the script is referenced by no CI job, manifest, command or runbook. Issue #770 was **closed as done** on it 2026-04-11. | 0 unresolved |
      | `SessionStart-batch-recovery` (#1672) | **ADDED 2026-08-25, CORRECTED same day.** My first entry said it "ships (`install_manifest.json:101-102`)" — **wrong**; those lines are `deploy_state.py` and `genai_install_wrapper.py`, and the hook appears **nowhere** in the manifest. So it neither ships nor is bound, while `CLAUDE.md:69` documents it as *the* session-continuity mechanism — consumers never receive the file. The wrong line number was inherited from a glance rather than measured at point of use. | 0 unresolved |
      | `enforce_file_organization.py` (#1672 comment) | **ADDED 2026-08-25.** Ships in the manifest and is declared `PreToolUse` in `settings.autonomous-dev.json`, but is bound in **no live settings layer** and is **absent from `settings.default.json`** — the template consumers install. Meanwhile `PROJECT.md:38` lists "File organisation enforcement" as in-scope and `PROJECT.md:95` names it as hook-enforced. | 0 unresolved |
      | Reviewer improvement machinery | 1,733 lines, 0 invocations | 0 unresolved |
      | genai tests calling no judge | 176 | 0 unresolved |
      | Dark test files | 95 across 7 dirs | 0 unresolved |
      | **A whole second test suite** (ADDED 2026-08-25) | **MEASURED: `plugins/autonomous-dev/tests/` holds 500 collectable tests that nothing runs.** It has its own `plugins/autonomous-dev/pytest.ini` — 6 markers where the root declares 15, `--strict-markers` on in both, **no `--cov` at all** (so no coverage floor; a sixth declaration site for #1677), and no `norecursedirs`, so it collects `archived`. The root suite cannot reach it (`testpaths = tests` resolves to the repo-root tree), and `.github/` + `scripts/` contain **zero** references to the path. It also has **3 live collection errors** (`test_claude_alignment.py`, `test_doc_change_detection.py`, `test_enforce_logging_only.py`). Not in `install_manifest.json`, so it does not ship. **May overlap the 95-dark-files row above — that row does not name its 7 dirs, so the overlap is unquantified and these must not be summed.** | 0 unresolved |
- [ ] **No net new mechanism without a retirement.** Each mechanism added under this goal names
      one retired or wired in the same change. Enforced by review, recorded in the ledger.
- [ ] Every deletion **names what it removed and why** — a bulk removal does not satisfy this

**Accurate — claims are measured**
- [ ] `test-master` cannot emit a test without an **observed failure against a mutated
      target**, enforced by hook (#1660 at the agent boundary)
- [ ] The improvement loop produces a **first weakness report** for at least one agent using
      **deterministic checks only** — cited `file:line` resolves, claimed commands were
      actually run, verdict stability across identical input. No LLM, no cost, not blocked.
      **Threshold: ≥3 findings, each independently confirmed true by re-running the check.**
      "≥1 finding" is satisfiable without doing the work — the #1660 defect, and it was in
      v2 of this document.
- [ ] Every mechanism shipped under this goal has a **bypass-hunt record**.
      **Threshold: ≥5 distinct evasion shapes attempted, each with a recorded outcome, and at
      least one drawn from a category the mechanism's author did not anticipate.** Ships when
      the successful-evasion list is empty or the survivors are named and accepted.

**Outcome — did the system get better at its job, not just better guarded**

Every other criterion here is internal (guards fire, mechanisms resolved, tiers bounded). This
one asks whether the product improved. Without it the goal can be fully met while the tool is
no more useful than today.

- [ ] **Rework-per-fix falls below the 2026-08-24 baseline.** MEASURED from existing git
      history, no new instrumentation: a `fix(...)` commit re-touching a production file that
      another `fix(...)` touched ≤7 days earlier, excluding `CHANGELOG.md`, `docs/`, `tests/`,
      `.claude/` and all `*.md` (those are touched by convention on every fix — counting them
      measures hygiene, not rework, and doing so inflated the raw figure from 66 to 180).
      | Window | Fixes | Rework | Rework-per-fix |
      |---|---|---|---|
      | 60→30 days ago | 40 | 15 | **37.5%** |
      | last 30 days | 76 | 66 | **86.8%** |
      Concentrated in `unified_pre_tool.py` (10×), `pipeline_completion_state.py` (6×),
      `agent_dispatch_sentinel.py` (5×).
- [ ] **The metric is controlled before it gates anything.** It currently discriminates between
      periods, which is a positive control. It still lacks a negative control: it cannot
      distinguish "fixed badly, three times" from "fixed deliberately in three passes." Until
      that is resolved the number is *tracked and reported*, never used to block.
- [ ] **Remediation cycles per pipeline run** are recorded per run and trend down. Baseline
      2026-08-24: three remediation cycles on a two-line comment fix.

**GenAI transport — standing constraint**
- [ ] **All GenAI in this system runs via `claude -p`.** Not OpenRouter, not a paid
      `ANTHROPIC_API_KEY`. Known call sites that violate this today:
      `scripts/run_reviewer_benchmark.py:69` (`Anthropic(api_key=...)`),
      `plugins/autonomous-dev/lib/genai_validate.py:82-118`, `tests/genai/conftest.py:224-232`.
- [ ] The `claude -p` invocation is **one shared helper**, not copied per call site — extending
      the proven one at `scripts/extract_and_label_intent_corpus.py:717-790`
      (`--output-format json`, `--max-turns 1`, `cwd=Path.home()` for #1064, fence stripping
      for #1065, envelope error checks)
- [x] Design assumes the **CI-measured** cost, not the laptop one. MEASURED in Actions
      2026-08-25 (spike run 32762603032), 5 sequential judge-sized calls:
      3469 / 3951 / 3850 / 5250 / 4923 ms → **median 3.95s**, roughly 2× faster than the 7.6s
      measured locally. Recomputed: 137 judges × 1 trial = **9.0 min** (now inside a 10-min
      cap); × 5 trials = **45.1 min** (still nightly). Calibrating against the local number
      would have over-estimated by 2× — the same wrong-environment error as the 512 pin.
- [ ] **Parse the envelope, never the exit code.** MEASURED: the negative control returned
      **exit 0** while failing, with the failure carried in `is_error: true` inside the JSON.
      Any helper that checks `$?` will read auth failure as success.
- [ ] Concurrency re-tested rather than assumed away. MEASURED: no `~/.claude/.credentials.json`
      exists in Actions (`P5_CREDS_ABSENT`), so GH #24317's file-corruption mode appears
      inapplicable there. If parallelism is safe, the 45 min falls substantially.

**Durable — it holds outside this repo**
- [ ] Every tier reports **EXECUTED=N**; a tier reporting success over zero **fails**
- [ ] `.claude/.bypass` is no longer all-or-nothing (#1647)
- [ ] Every rule discovered during this goal ends as a **hook, a shipped script, or an
      explicitly-recorded known gap** — never as prose alone
- [x] **#1663 ANSWERED 2026-08-25** (spike run 32762603032, workflow since deleted).
      `claude -p` **does** authenticate in GitHub Actions on `CLAUDE_CODE_OAUTH_TOKEN`:
      exit 0, `is_error:false`, 4s. The negative control (same call, token removed) returned
      `is_error:true`, so the token is what made it work. `--bare` returned
      `"Not logged in · Please run /login"` — **GH #38022 confirmed** in this environment.
      Unverified and worth checking against billing: the envelope reported
      `total_cost_usd: 0.037342` per call, which on a Max subscription is probably nominal
      accounting rather than a charge — but "it's $0" has not been proven.

**Consistent**
- [ ] No rule has two mechanisms; no mechanism has two divergent copies (the duplicate
      `GenAIClient` in `templates/genai-uat/` is the known instance)
- [ ] **The coverage floor is one number, not five (#1677, ADDED 2026-08-25).** MEASURED: one
      rule declared at five sites with two values — `pytest.ini:24` = **4**;
      `auto_test.py:98`, `safety-net.yml:133`, `PROJECT.md:85` and the shipped
      `python-standards/SKILL.md:184` = **80**. The lowest is the only one that executes on
      every local run, and its "never decrease this value" instruction (`pytest.ini:23`) has
      **no mechanism whatsoever** — no test, hook, script or workflow reads it. A ratchet whose
      entire enforcement is a code comment is the INV-1 case in miniature. Actual coverage is
      **UNKNOWN** and must be measured before any floor is moved, or the fix becomes #1576's
      cry-wolf pattern a second time.

**Self-applying — the detector is subject to its own rules**
- [ ] Every mechanism built under this goal is **itself** subject to the rules it enforces: it
      has both arms observed, a bypass-hunt record, and an entry in the dead-mechanism ledger
      if it stops being invoked. No mechanism is exempt because it is the one doing the checking.
- [ ] **When the detector misses something, that becomes a filed finding against the detector.**
      Concretely: any defect found by a human, an agent, or a later session that a shipped gate
      *should* have caught results in an issue naming the gate that missed it — not only the
      defect. Baseline evidence this is needed: the four silent fail-opens were found by fault
      injection, not by any gate; the #1620 fix was flagged as undeployed four times by a
      findings store nobody read; and this goal's own v2 contained the exact tautology defect
      filed as #1660 four hours earlier.

## 3. Scope Boundaries

**In scope** — the 4 silent fail-opens; cross-repo proof in realign and spektiv; deletion of
dead mechanisms; `test-master` output enforcement; the deterministic half of the agent
improvement loop; tier-execution honesty; bypass granularity (#1647); ~~the #1663 spike~~
(**done 2026-08-25**); the known-red running tiers (§7a).

**Out of scope, with reasons** — draining the 262 backlog (volume is the symptom; it grew from
108 while guards rotted). The genai tier's LLM half and agent calibration corpora (#1566,
#1664): **no longer transport-blocked as of 2026-08-25** — the spike showed `claude -p` works
in Actions at a CI-measured 3.95s median, so one non-repeated pass over 137 judges is ~9 min
and fits a 10-min cap, while 5-trial calibration at ~45 min does not. They stay out of scope
here because they still need a corpus that does not exist and a redesign around nightly or
sampled execution — but the reason is now scope, not impossibility. anyclaude: no install
detected.

## 4. Success Criteria

| Criterion | Verification | Threshold | Source |
|---|---|---|---|
| No silent fail-open | `python3 plugins/autonomous-dev/scripts/proof_of_block.py` | 0 silent fail-opens | MEASURED: 4 of 8 |
| Both arms per guard | same | every guard REFUSES **and** PERMITS | #1617 |
| Proof in consumer repos | run in `~/Dev/realign`, `~/Dev/spektiv` | artifact committed, exit 0 | MEASURED: 0 |
| Dead mechanisms resolved | per-item check against the §2 table | **0 items UNRESOLVED** | 5 guards, tracker, 1,733 lines, 176 tests, 95 files |
| test-master enforcement | write a test with no failure-proof | REFUSED; proven one PERMITTED | #1660 |
| First weakness report | the deterministic loop | **≥3 findings, each re-confirmed**, 0 LLM calls | §2 |
| Bypass-hunt per mechanism | the record | **≥5 evasion shapes, ≥1 unanticipated** | §2 |
| Tier honesty | CI on master | every tier prints EXECUTED=N; N=0 fails | integration precedent |

## 5. Milestones

| Date | Deliverable | Verification |
|---|---|---|
| ~~2026-08-27~~ **DONE 2026-08-25** | ~~#1663 spike~~ — pulled forward and answered | Run 32762603032; `claude -p` authenticates, 3.95s median; abort 2 retired |
| **2026-08-27** | **`test-master` failure-proof enforcement** — mechanics before tests | Both arms observed; bypass-hunt ≥5 shapes recorded |
| 2026-08-29 | Deterministic weakness report for one agent | **≥3 findings, each re-confirmed**, 0 LLM calls |
| 2026-08-31 | 4 silent fail-opens fixed | `proof_of_block` → 0 silent fail-opens, both arms per guard |
| 2026-09-03 | Dead mechanisms deleted or wired | **0 items UNRESOLVED in the §2 table** (not a line count — that metric was retired as gameable) |
| **2026-09-07** | **MID-POINT ABORT REVIEW (§7)** | ≥1 consumer proof artifact; 0 UNRESOLVED items ≤ baseline |
| 2026-09-14 | Collected-floor generalised; dark tiers resolved | EXECUTED=N per tier; each of the 95 files run or removed with a stated reason |
| 2026-09-21 | Cross-repo proof in realign and spektiv | Committed artifacts, both repos |

## 6. Tracking

**Must close**: #1612, #1617, #1636, #1647, #1660, #1661, #1662
**Answered, close on next pass**: #1663 (spike run 32762603032, 2026-08-25)
**Re-scope**: #1566, #1664 — **no longer gated on #1663**; both now need a corpus that does not
exist and a nightly/sampled design around the CI-measured 3.95s, not a transport decision
**Artifacts**: this document; `tests/proofs/` in realign and spektiv; the bypass-hunt records;
the first deterministic weakness report
**Memory**: `feedback_enforcement_not_memory.md`, `project_pipeline_gate_history.md`

## 7. Abort Conditions

1. **Mid-point stall (2026-09-07)** — no consumer-repo proof artifact by this date. Pivot:
   re-scope to autonomous-dev only; file the cross-repo work as its own goal.
2. ~~**Transport dead-end** — #1663 returns no $0 path.~~ **RETIRED 2026-08-25.** The spike
   answered it: `claude -p` authenticates in Actions on `CLAUDE_CODE_OAUTH_TOKEN`, median
   3.95s per judge-sized call. This condition can no longer fire. Replaced by: **if the
   `total_cost_usd` reported per call turns out to be a real charge rather than nominal
   subscription accounting, STOP** — that would make every GenAI gate a paid dependency and
   violate INV-8.
3. **Enforcement regression** — `proof_of_block.py` reports more than 4 silent fail-opens at
   any milestone. Pivot: freeze feature work, fix the regression first.
4. **Complexity regression** — the dead-mechanism list has **more UNRESOLVED items** at the
   mid-point than at baseline, or a mechanism was added without a retirement. Pivot: stop
   adding, resolve first. Adding to a system already carrying 142k lines of unproven
   enforcement is how this state was reached.
5. **Schedule abort (v3 — the time-box must bite).** If **two or more milestones** slip past
   their dates, STOP and re-scope. v2 said slip "is expected and is not itself an abort
   trigger," which neutered the time-box that was chosen as the kill switch — a schedule with
   no consequence is decoration. Velocity evidence for the scepticism: on 2026-08-24 a
   **two-line comment fix** consumed a full pipeline and three remediation cycles. Milestone
   dates below are estimates against that observed rate, not aspirations.

## 7a. Known-red CI is in scope, not deferred

"Consistent" cannot hold while tiers that DO run fail constantly. Baseline MEASURED
2026-08-24: unit **104** failures, regression **205**, integration **521** (ratcheted).
- [ ] Every running tier has a **pinned failure ceiling that may only decrease** — the
      integration ratchet generalised, so a tier that runs and fails 205 times is bounded
      rather than ignored
- [ ] No tier is left both running and unbounded. A permanently-red unbounded tier trains
      dismissal of the whole class, which is how the integration tier stayed dark for months.

## 8. Progress Ledger

- `proof_of_block.py` — headline metric, on demand
- The **§2 dead-mechanism table** — the simplicity metric. Count items still `UNRESOLVED`.
  Deliberately NOT `wc -l` on hooks+lib: that was v2's metric and it is gameable, since
  `lib/*.py` is 120,001 of the 142,869 lines and mostly is not enforcement code.
- `gh issue list --state open | wc -l` — 262 at baseline (MEASURED 2026-08-24)
- **Headline metric RE-MEASURED live 2026-08-25** (not inherited): `proof_of_block.py` reports
  **8/8 guards PROVEN, 4 failing open silently** — the 2026-08-24 baseline holds. The instrument
  passed all seven of its own controls (fault positive, fault negative, trace positive, trace
  negative, and three classifier arms), so the number is trustworthy at the point of use.
  **Root-caused the same day: 3 of the 4 are ONE defect, not three** (#1682). `_ti_is_write()`'s
  fallback at `unified_pre_tool.py:132` is a literal four-tuple of *native* tool names, so with
  `tool_intent` unavailable every MCP write transport classifies as a non-write. Driven
  end-to-end against the real hook: `Write`→DENY, `Edit`→DENY,
  `mcp__serena__replace_symbol_body`→**ALLOW**, `mcp__serena__rename_symbol`→**ALLOW**,
  `Read`→ALLOW (correct). So `CLAUDE.md`'s promise that the #1435 floor holds for "an MCP editor
  such as `mcp__serena__replace_symbol_body`… even under bypass" is false under fault.
  **And the prover cannot see it**: its hard-floor scenario is `/ Write`, the one transport the
  fallback tuple saves — a guard certified by the arm that survives. The 4th fail-open
  (`plan-exit-gate` / `state_corrupt`) is a genuinely separate cause and looks like an INV-7
  breach: a corrupt marker is treated as "stage not active", i.e. as *fewer* restrictions.
- **A set diff needs an environment control too** (MEASURED 2026-08-25). The *Outcome* criterion
  tracks rework-per-fix, and the operating rule is "attribute by set, not count". That rule is
  necessary and **not sufficient**. Attributing `tests/unit` failures for #1666 via a `git
  worktree` baseline produced 3 "new failures" and 16 "fixes" — a credible-looking regression
  signal in which **all 19 were artifacts**: `.claude/lib` is gitignored (`.gitignore:147`), so a
  worktree has no installed copy, and tests asserting the installed copy exists flip against
  tests asserting it does not. Zero were attributable to the change. The instrument that held was
  structural, not comparative — no file under `tests/unit/` outside `tests/unit/genai/` references
  the changed modules, so the change could not reach them. **Any rework-per-fix figure taken from
  a worktree run in this repo is contaminated by ~19 tests before it measures anything.**
- **Both-arms observations recorded as they happen** — the goal's headline criterion is one
  REFUSES row and one PERMITS row per guard, so they are logged when observed rather than
  reconstructed later:
  - `agent_ordering_gate` — **PERMITS** `implementer` after `planner` completed (`ORDERING OK`);
    **REFUSES** `doc-master` before the pytest gate closed, and `continuous-improvement-analyst`
    before `doc-master` (`ORDERING VIOLATION ... requires [pytest-gate] to complete first`).
    Both arms, same session, 2026-08-25. ✅
  - `prompt_integrity` — **REFUSES** an implementer dispatch compressed 24% below the 980-word
    baseline; **PERMITS** the reconstructed dispatch carrying the planner's full output. The
    refusal was *correct*: the coordinator had paraphrased the plan instead of passing it
    verbatim, which is the FORBIDDEN behaviour the gate exists to catch. Both arms. ✅
  - `test_issue_1666_no_bare_conftest_import` — **REFUSES** two scratch files (`from conftest
    import Foo`, `import conftest`); **PERMITS** a package-qualified import *and* a
    different-shaped near-miss (`import conftest_helpers`) that a naive prefix match would have
    false-flagged. Verified by the coordinator independently of the implementer's own run. ✅
- **The four-number attrition chain** (MEASURED 2026-08-25) — the denominator this goal actually
  needs, because each step silently drops guards the previous step counted:
  **33 on disk → 26 shipped → 15 bound in any template → 12 bound in live settings.**
  Enumerate ALL settings layers (project, project-local, user-global, managed) — reading only
  `.claude/settings.json` reported 10 unbound where the true figure is 3, because seven are
  bound via `~/.claude/settings.json`. Caveats that must travel with the number: several
  manifest entries are not lifecycle hooks (`genai_utils.py`, `genai_prompts.py`, `setup.py`,
  `*.hook.json`), and at least one — `batch_permission_approver.py` — is dispatched from
  `unified_pre_tool.py` rather than bound in settings, so "not bound" is **not** "dead". That
  ambiguity is #1674, and it bounds how far this chain can be read as a coverage figure.
- `collect_cia_findings()` over `.claude/logs/findings/` — readable since #1658
- This document, updated per milestone with deltas named

---

**Risks stated at creation.** (a) The headline metric depends on two repos whose roadmaps this
goal does not own — abort 1 catches that at the mid-point. (b) The dead-mechanism criterion can
be gamed by deleting tests rather than dead code; every deletion must name what it removed and
why, and the dark-tier item requires a stated reason per file rather than a bulk removal.
(c) Seven milestones in four weeks against a 262-issue backlog and a red CI is aggressive —
and **two slipped milestones abort the goal (§7.5)**. That is deliberate: the time-box was
chosen as the kill switch, so it has to bite.

> **v2→v3 correction.** v2's footer read "milestone slip is expected and is not itself an abort
> trigger — only the four conditions above are." That sentence cancelled abort 5 while abort 5
> sat forty lines above it, and it miscounted the conditions. It survived because I edited
> sections without re-reading the document end to end — the same drift this goal exists to
> catch, found only by printing the whole thing. Logged rather than silently overwritten.
