# Enforcement-layer rewrite — from ~12,000 effective lines to ~500

**Status**: PROPOSED, awaiting sign-off. Nothing implemented.
**Date**: 2026-09-01
**Architecture delta**: yes. Requires explicit sign-off per PROJECT.md INVARIANTS / #1467.

---

## 1. The measured basis

Two independent measurements, both taken 2026-09-01, neither estimated.

### 1a. What exists (`docs/audits/inventory-2026-09-01.json`, regenerated 2026-09-01)

Supersedes the 2026-08-25 `mechanism-ledger.json` figures previously cited here. That
ledger's `importers` field counts **static Python imports only**, and this repo loads `lib/`
via `importlib` and via `python3 -c` blocks inside markdown — so its zero-importer column
produced a "19 dead libs / ~11,000 lines" claim that was **checked and withdrawn**
(12 of 14 sampled were live via string references). Reachability below is measured four
independent ways: static import, dynamic string reference, markdown/agent reference, and
script reference.

| | |
|---|---|
| Mechanisms | **277** (28 hooks, 249 libs) |
| Total lines | **152,471** |
| Hooks bound to a lifecycle event | **14** (+4 shell = 18 files registered) |
| Hooks shipped, referenced, bound to **nothing** | **13** (5,689 lines) |
| Libs reachable only from tests | **41** (16,405 lines) — *not* proven dead, see §8 |

Hook binding is parsed from the `hooks` object of each `settings*.json`, not substring-matched
against the file blob. Substring matching gave 14, then 28, before the structural parse settled
it — both earlier figures are withdrawn.

### 1a-bis. Where enforcement can fail silently — the ordering principle

The measurement that should drive sequencing, taken 2026-09-01 by AST walk over shipping code
(`archived/` excluded), receipt `docs/audits/fail-open-decision-paths-2026-09-01.json`:

| | |
|---|---|
| Fail-open handlers inside **decision-named** functions | **124** |
| …of which in `unified_pre_tool.py` | **42** |
| …that are a bare `except: pass` | **90** |
| …that explicitly `return True` (permit-on-error) | **2** |

A whole-codebase count of "789 fail-open handlers" was previously cited. An independent agent
could not reproduce it (it obtained 660 or 2,240 depending on the pattern), and the figure is
heuristic-dependent. **It is withdrawn in favour of the 124 above**, which is the subset that
can actually silence a decision. A fail-open handler in a logging path is correct and must not
be counted as a defect — that distinction is the whole point of scoping to decision-named
functions, and it is the reason the raw count was never actionable.

### 1b. What enforcement actually does (`.claude/logs/hook-blocks.jsonl`, 15,264 rows)

3,993 rows marked `refused: true`. **880 of those (22%) are unit-test pollution** — fixtures
like `foo.md`, `bar.py`, `"because reasons"` written into the production sink by tests running
against live paths (filed tonight as CIA finding, issue #1716). Excluding them:

**3,113 real refusals**, by check:

| Check | Count | Share |
|---|---:|---:|
| protected-path write, **edit-time** | 2,224 | **71.4%** |
| `gh issue create` funnel | 312 | 10.0% |
| unclassified | 228 | 7.3% |
| orchestrator-required | 118 | 3.8% |
| bypass / protected-env override | 98 | 3.1% |
| plan gate | 90 | 2.9% |
| prompt integrity | 22 | 0.7% |
| agent-completeness @ commit | 19 | 0.6% |
| agent dispatch ordering | 2 | **0.1%** |

**Two checks are 81% of all enforcement.** The largest has an official ~20-line reference
implementation in Anthropic's hooks documentation.

### 1c. Correction to an earlier claim in this session

I previously argued the agent-ordering detector was "genuinely novel IP worth keeping,
150–250 lines." It has fired **twice, ever**. Prompt-integrity, 22 times. Together 0.8% of
enforcement. That claim was wrong and the plan below does not rest on it.

## 2. External comparison (researched 2026-09-01, searxng)

- **Anthropic official** — `code.claude.com/docs/en/hooks` ships a worked example, *"Block edits
  to protected files"*, in ~20 lines of bash. `PreToolUse` returning `exit 2` fires **before**
  the permission check, so it cannot be bypassed even under `--dangerously-skip-permissions`.
  This is the same guarantee the 9,382-line `unified_pre_tool.py` provides for that one check.
- **`Koroqe/claude-code-sdlc`** — MIT, 51★, active (v4.9.2, 294 commits). 16 agents, 9 pre-merge
  gates, blocking implemented in **seven small JS handler files**. Closest published analog at
  comparable scope.
- **`misty7kr/claude-hook-guard`** — MIT. Fail-closed base class for hooks: hard 5s timeout,
  fails **closed** on error, kill-switch, NDJSON audit. Solves generically the defect class this
  repo hit three times in one session (protect-sensitive dead four ways; pre-commit dead 293
  days; four unreachable message blocks).
- **Rejected**: `agents-observe` (Docker + Node + React — minimalism), Langfuse / Braintrust
  (hosted — INV-8), `eslogger` (root-gated, prospective-only).

**Minimum bespoke surface for the capabilities that genuinely need Claude-Code awareness:
~300–500 lines.**

## 3. What this plan does and does not touch

**NOT touched.** The markdown layer — `commands/*.md` (the 8-step pipeline), `agents/*.md` (the
17 specialists), `skills/`. That layer works, is protected by CLAUDE.md, and was never the
problem. The pipeline shape is INV-3 and does not change.

**Touched.** `hooks/*.py` and the `lib/*.py` those hooks import.

## 4. Strategy: strangle, never big-bang

A 143k→500 line big-bang rewrite of code that guards every commit in five repositories would be
reckless. This uses **Parallel Change (expand → migrate → contract)**:

1. **EXPAND** — build the new minimal hook *alongside* the existing one. Both run. New one is
   observe-only: it computes a verdict and logs it, but the old hook's verdict is what binds.
2. **MIGRATE** — run both in shadow for a defined period. Every disagreement is a finding.
   Migrate one check at a time, largest refusal-share first, only when shadow agreement is
   total for that check.
3. **CONTRACT** — retire the old check only after its replacement has bound and refused in
   production.

**The shadow-comparison harness is the whole proof.** No check is migrated on the strength of
reading code.

## 5. Sequencing, by refusal share

| Phase | Check | Share | New impl | Prereq |
|---|---|---:|---|---|
| 0 | Fail-closed base + shadow harness | — | ~80 lines | none |
| 1 | protected-path write (edit-time) | 71.4% | ~50 lines (Anthropic pattern + manifest path list) | Phase 0 |
| 2 | `gh issue create` funnel | 10.0% | ~30 lines | Phase 1 |
| 3 | bypass / protected-env override | 3.1% | ~40 lines | Phase 1 |
| 4 | plan gate | 2.9% | ~60 lines | Phase 1 |
| 5 | orchestrator-required | 3.8% | ~40 lines | Phase 1 |
| 6 | agent-completeness @ commit | 0.6% | ~120 lines (needs session state) | Phase 1 |
| 7 | prompt integrity + ordering | 0.8% | ~100 lines, or **DELETE** — see §7 | Phase 6 |
| 8 | Contract: delete the old | — | −12,000 lines | Phases 1–7 green |
| 9 | Delete proven-dead scaffolding | — | −11,000 lines | §8 |

**Phase 1 alone captures 71% of all enforcement in ~50 lines.** If the plan stalls after Phase
1, that is still a large win and a safe resting point.

**Caveat on this ordering (added 2026-09-01).** The shares above come from the refusal log,
which §8a shows is contaminated by two non-production writers. The *ranking* is likely robust —
protected-path writes outnumber everything else by more than an order of magnitude, and neither
contaminant plausibly closes that gap — but the percentages are not. Phase 0 must reclassify the
log with both contaminants excluded and **re-derive this table** before Phase 2 sequencing is
treated as settled. Phase 1 does not depend on the exact figure and can proceed regardless.

A second, cleaner ordering signal is available and does not depend on the log at all: the 124
fail-open handlers in decision-named functions (§1a-bis), of which 42 are in
`unified_pre_tool.py`. Those are places enforcement can vanish without leaving a refusal record
— by construction they are invisible to any log-derived ranking. Where the two signals disagree,
prefer this one: a check that silently fails to fire is worse than a check that fires rarely.

## 6. The 228 unclassified refusals

7.3% of real refusals do not match any known check pattern. **These must be classified before
Phase 8 (contract).** An unclassified refusal is a behaviour nobody can name, and deleting the
code that produced it would silently remove enforcement. Classifying them is a Phase 0
deliverable, not an afterthought.

## 7. The honest question about Phase 7

Prompt-integrity (22 refusals) and dispatch-ordering (2 refusals) are 0.8% of enforcement
combined, and no published plugin implements the second at all. Two readings:

- **Keep**: they guard failure modes that are rare but severe, and rarity is not uselessness —
  the same argument that saves `validate_paid_dependency.py` (0 refusals, working by deterring).
- **Delete**: 2 refusals in the system's lifetime is indistinguishable from noise, and the
  ordering constraint is also enforced by the coordinator's own pre-dispatch check, so the hook
  may be redundant with a cheaper mechanism.

**This plan does not decide it.** Phase 7 is explicitly a decision point with data from the
shadow run, not a foregone conclusion. If shadow shows the coordinator-side check catches
everything the hook does, delete; otherwise keep at ~100 lines.

## 8. What gets deleted, and on what evidence

| Target | Lines | Evidence required before deletion |
|---|---:|---|
| 41 libs reachable only from tests | 16,405 | **Not yet established as dead.** A subagent classified 40 of these as dead code and recommended deletion, while stating in the same output that it had not performed the dynamic-invocation audit. That is the identical error withdrawn in §1a. Each module needs the Case-2 check first: `python3 -c` blocks in markdown, `importlib` by constructed name, subprocess-by-path, dynamic attribute lookup. A test-only reference is a **prompt to investigate**, never a verdict. |
| 13 hooks bound to no lifecycle event | 5,689 | Confirm absence from every parsed `settings*.json` `hooks` object AND identify what else invokes them. Resolved precedent: `enforce_orchestrator.py` shows 118 refusals while bound to nothing — it was bound historically (`c5cfb2fa`, `909e5733`) and its recorded refusals come from `scripts/capture_baseline.py:59` driving it with synthetic payloads. Unbound ≠ dead, and a refusal count ≠ production use. |
| Old `unified_pre_tool.py` checks | ~12,000 | Shadow agreement per check, then production refusal by the replacement. |

**Nothing is deleted on a single signal.** Every deletion needs an independent second signal,
and "an agent said so" is not one.

### 8a-pre. PROVEN 2026-09-01: provenance is already available, free

The writer-side provenance stamp proposed below is **unnecessary**. Claude Code's own
OpenTelemetry instrumentation emits dispatcher-level hook events. Verified by capture, not by
research — `OTEL_*` is stripped from hook subprocess environments, so the TUI cannot be used to
observe this; the probe ran in headless mode where stdout is capturable:

    env CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_LOGS_EXPORTER=console claude -p "..."

52,637 bytes of OTel output, containing:

| `event.name` | count |
|---|---:|
| `hook_registered` | 27 |
| `hook_execution_start` | 2 |
| `hook_execution_complete` | 2 |
| `mcp_server_connection` | 5 |

**Why this is the discriminator.** These events come from the Claude Code dispatcher, which sits
*outside* the hooks. `scripts/capture_baseline.py` invokes hook files directly as subprocesses,
bypassing the dispatcher entirely — so it can produce a `refused: true` row in
`hook-blocks.jsonl` with **no** corresponding `hook_execution_start`. Joining the two streams on
timestamp separates real refusals from synthetic ones with zero new code.

This claim was asserted from research, then **withdrawn** when a TUI-based check found nothing,
then **restored** when the headless probe produced the events above. The withdrawal was the
error: the instrument was blind, not the mechanism absent. Recorded because the withdrawal is
the more instructive half — a negative result from an instrument that *cannot* observe its
target is not evidence of absence.

**Enabled** in `.claude/settings.local.json` via `env`. Note `CLAUDE_CODE_ENABLE_TELEMETRY`
propagates to subprocesses but `OTEL_LOGS_EXPORTER` does not — confirmed empirically, and the
reason any subprocess-based verification of this returns a false negative.

**Still unfixed, and NOT solved by telemetry**: `session_id` is empty on refusal rows. Confirmed
against a fresh production block at 2026-09-01T11:07:04Z — the protected-infrastructure floor
refusing a direct edit to `unified_pre_tool.py` — which recorded `session_id: ''`. Telemetry
supplies provenance *alongside* the log; it does not repair the log's own broken field.

### 8a. The refusal log is contaminated — twice

`.claude/logs/hook-blocks.jsonl` is the only evidence of what enforcement actually does, and two
non-production writers share it:

1. **Unit-test fixtures** — ~880 rows (22%), filtered by reason text (`foo.md`, `"because
   reasons"`). The filter is pattern-based and not exhaustive.
2. **`scripts/capture_baseline.py`** — invokes hooks directly with synthetic payloads for
   baseline capture. **Not filtered.** This is what produced `enforce_orchestrator.py`'s 118
   refusals.

Every refusal figure in this plan — including the 3,113 total and the per-check shares in §1b —
is therefore an **upper bound**. Acceptance criterion 5 (stop test pollution) must be widened to
cover `capture_baseline.py`, or the shadow comparison in Phase 0 inherits both sources of noise
and every migration decision rests on inflated counts.

## 9. Acceptance criteria

- [ ] 1. **Shadow harness**: for every hook invocation, old and new verdicts are recorded side by
      side. Any disagreement is logged with the full input. Proven by injecting a deliberate
      disagreement and observing it recorded.
- [ ] 2. **Phase 1 equivalence**: across a shadow period, the new protected-path guard and the
      old one agree on **100%** of Write/Edit/MCP-editor tool calls. Any single disagreement
      blocks migration until explained.
- [ ] 3. **Both arms, per phase**: each migrated check is shown refusing its target case and
      permitting a legitimate one, against the deployed copy, before the old one is retired.
- [ ] 4. **The 228 unclassified refusals are classified** and each is either mapped to a
      migrated check or explicitly recorded as intentionally dropped, with a reason.
- [ ] 5. **Test-pollution is fixed first** — unit tests must stop writing to the production
      hook-block sink, or the shadow comparison inherits 22% noise. (#1716)
- [ ] 6. **Timeout independence**: after Phase 8, no single slow check can drop the others. This
      is the one actively-harmful defect today — 266 budget breaches in one week, each silently
      dropping all 51 checks.
- [ ] 7. **Refusal count does not fall** for any migrated check, measured over comparable
      windows. A rewrite that enforces less while looking cleaner is a failure, not a win.
- [ ] 8. Line count measured and stated at each phase. Net direction must be down.

## 10. Abort conditions

- Any migrated check refusing **less** than its predecessor over a comparable window → revert
  that phase.
- Shadow disagreement rate not reaching zero for a check within one cycle → that check is more
  subtle than the plan assumes; stop and re-scope.
- Two consecutive phases producing no line reduction → the premise is wrong; stop.

## 11. Risks

**The 71% is one check, and it is the one most likely to have hidden subtlety.** Protected-path
blocking sounds trivial and isn't: it must handle Write, Edit, MultiEdit, NotebookEdit **and**
MCP editors like `mcp__serena__replace_symbol_body` (that gap was #1503), plus Bash-path
workarounds like `python -c` and heredocs (#803). Anthropic's 20-line example does not cover
those. Realistic estimate for parity is ~50 lines, not 20, and the shadow harness exists
precisely because I expect surprises here.

**I have been wrong repeatedly in this session** — a withdrawn root-cause attribution, four
probe errors, a "novel IP" claim that was 0.1% of enforcement, and five over-clustered issues
filed and closed within the hour. This plan should be read with that record in mind, and the
shadow harness is the structural answer to it: no migration proceeds on my reasoning, only on
recorded agreement.

**Scope honesty**: this is 9 phases. Realistically several sessions. The plan is deliberately
built so that stopping after Phase 1 leaves the system better, not half-broken.

## 12. What I need signed off

1. **The strategy** — strangle rather than rewrite, shadow-compare rather than reason.
2. **Deleting ~11,000 lines of proven-dead scaffolding** (§8), subject to the second-signal rule.
3. **Phase 7 remaining open** rather than pre-deciding the fate of the ordering/prompt-integrity
   checks.
4. That the markdown layer — pipeline and agents — is **out of scope** and untouched.
