---
covers:
  - plugins/autonomous-dev/commands/implement.md
  - plugins/autonomous-dev/commands/implement-fix.md
  - plugins/autonomous-dev/commands/implement-batch.md
  - plugins/autonomous-dev/commands/implement-resume.md
---

# `/implement` Pipeline Modes

`/implement` runs different agent sets depending on the mode flag. This doc is the authoritative matrix — which agents run, in what order, and which gates fire.

## Mode Selection

| Mode | Flag | When to use |
|------|------|-------------|
| **Full (default)** | *(none)* — or `--tdd-first` | New features, bug fixes touching logic, anything security-sensitive |
| **Light** | `--light` | Markdown/config edits, docs, renames, typos — no new logic |
| **Fix** | `--fix` | Test failures, flaky tests, broken tests |
| **Batch (file)** | `--batch <file>` | Process a file of features with auto-worktree per feature |
| **Batch (issues)** | `--issues <nums>` | Process GitHub issues with auto-worktree per issue |
| **Resume** | `--resume <run_id>` | Recover from auto-compact / crash mid-pipeline |

**Auto-detection**: If no mode flag is given, `/implement` scans the feature description for signals:
- Fix keywords (`failing test`, `broken test`, `flaky test`) → suggests `--fix`
- Light keywords or file paths (`*.md`, `*.json`, `*.yaml`, docs-only) not matching security patterns → suggests `--light`
- Security-sensitive file (`hooks/*.py`, `lib/*security*`, `*.env*`, etc.) → forces full pipeline

## Agent Matrix

| Agent | Model | Full | `--tdd-first` | `--light` | `--fix` | `--batch` / `--issues` |
|-------|-------|------|---------------|-----------|---------|------------------------|
| alignment-classifier | haiku | ✓ | ✓ | ✓ | ✓ | ✓ per issue |
| researcher-local | haiku | ✓ | ✓ | ✗ | ✗ | ✓ per issue |
| researcher | sonnet | ✓ | ✓ | ✗ | ✗ | ✓ per issue |
| planner | opus / sonnet | ✓ | ✓ | ✓ (sonnet) | ✗ | ✓ per issue |
| plan-critic | opus | ✓ | ✓ | ✓ (1 round) | ✗ | ✓ per issue |
| test-master | opus | ✗ | ✓ | ✗ | ✗ | ✓ (TDD issues) |
| implementer | opus / sonnet | ✓ | ✓ | ✓ | ✓ | ✓ per issue |
| spec-validator | opus | ✓ | ✓ | ✓ | ✓ | ✓ per issue |
| reviewer | sonnet | ✓ | ✓ | ✗ | ✓ (bundled with docs) | ✓ per issue |
| security-auditor | sonnet | ✓ | ✓ | ✗ | ✓ (conditional) | ✓ per issue |
| doc-master | sonnet | ✓ | ✓ | ✓ | ✓ | ✓ per issue |
| continuous-improvement-analyst | sonnet | ✓ (bg) | ✓ (bg) | ✓ (bg) | ✓ (bg) | ✓ post-batch |

**Minimum agents per mode** (agents tracked by the STEP 9.5 agent-count / completeness gate — see `agent_ordering_gate.py`; `alignment-classifier` is dispatched at STEP 2 / L1 / F1 / I1.6 in every mode but is NOT yet a member of these gate-enforced sets, Issue #1467):
- Full (default, acceptance-first): 8 — researcher-local, researcher, planner, plan-critic, implementer, spec-validator, reviewer, security-auditor, doc-master (+CI analyst bg)
- `--tdd-first`: 9 — adds test-master before implementer
- `--light`: 5 — planner, plan-critic, implementer, spec-validator, doc-master (+CI analyst bg)
- `--fix`: 5 (6 if security-sensitive) — implementer, spec-validator (F3.5), reviewer+docs bundled, CI analyst bg; +security-auditor when Security-Sensitivity Detection flags files
- `--batch` / `--issues`: full pipeline per issue + 1 post-batch CI analyst

**Research skip** (full mode only): If the feature description names a specific file path AND a specific modification instruction AND does NOT reference security-sensitive files or keywords (hooks, auth, secrets, tokens, SSO, OAuth, etc.), STEP 4 (research) is skipped. Research is NEVER skipped when touching `hooks/*.py`, `lib/*security*`, `lib/*auth*`, `*.env*`, `config/auto_approve_policy.json`, or migrations.

## Step-by-Step Sequence (Full Pipeline)

```
STEP 1   Pre-staged files check ......... HARD GATE
STEP 2   PROJECT.md alignment (Stage 0 deterministic pre-check +
         alignment-classifier dispatch, Haiku) ... HARD GATE (#1467)
STEP 3   Research cache check
STEP 3.5 Fully-specified detection (may skip STEP 4)
STEP 4   Research (researcher-local + researcher in parallel)
STEP 4.5 Research completeness critique (inline)
STEP 4.7 Pre-validated plan detection (inline)
STEP 4.8 Plan freshness re-verification (inline, conditional)
STEP 4.9 Prior-art search (inline, no agent) — mechanical closed-issue
         lookup pasted verbatim into the STEP 5 planner prompt (#1669)
STEP 5   Planning (planner)
STEP 5.5 Plan validation gate (plan-critic + structural checks) HARD GATE
STEP 6   Acceptance tests generation
STEP 7   Test-master (--tdd-first only)
STEP 8   Implementation + test gate ..... HARD GATE (0 failures)
STEP 8.5 Spec-blind validation (spec-validator) HARD GATE
STEP 9   Hook registration check ........ HARD GATE
STEP 9.5 Agent count gate ............... HARD GATE
STEP 9.7 Conditional UI testing (ui-tester if HTML/TSX changed)
STEP 9.8 Conditional mobile testing (mobile-tester if Swift/Kotlin/Dart changed)
STEP 10  Validation (reviewer + security-auditor + doc-master)
         — parallel if no security-sensitive files
         — sequential (reviewer → security) if hooks/*.py or *auth* changed
STEP 11  Remediation gate (max 2 cycles) HARD GATE
STEP 11.5 Skill effectiveness gate (if skills/ modified)
STEP 12  Final verification + doc-drift gate HARD GATE
STEP 12.7 Commit via create_commit_with_agent_message (Closes #N injection) HARD GATE (#1226)
STEP 13  Report and finalize + push (if AUTO_GIT_PUSH=true)
STEP 14  Documentation congruence ....... HARD GATE
STEP 15  Continuous improvement (bg analyst)
```

## Light Pipeline Sequence

```
L0  Pre-staged files check HARD GATE
L1  PROJECT.md alignment (same alignment-classifier protocol as STEP 2) HARD GATE (#1467)
L2  Planning (planner, sonnet)
L2.5 Plan structural validation HARD GATE
L3  Implementation + test gate HARD GATE
L3.5 Spec-blind validation HARD GATE
L4   Documentation (doc-master)
L4.7 Commit via create_commit_with_agent_message (Closes #N injection) HARD GATE (#1226)
L5   Report and finalize + push + CI analyst bg
```

## Fix Pipeline Sequence

```
F1    Alignment check (same alignment-classifier protocol as STEP 2 — Issue #1467)
F2    Test context (read failing tests, locate fixtures)
F3    Fix implementation (implementer) — regression test REQUIRED
F3.5  Spec-blind validation HARD GATE (spec-validator)
F4    Review + docs (bundled) + security-auditor if Security-Sensitivity Detection flags files
F5    CI analysis (bg)
```

The fix pipeline is minimal because the user is reacting to a known failure. It DOES enforce the regression test gate (any fix must add a test that would have caught the bug).

## Gate Types

**HARD GATE** = JSON `{"decision": "block"}` returned by a hook. Prompt-level instructions ("please run tests") produce unreliable compliance (see [LLM Agents Are Hypersensitive to Nudges, 2025]). Hard gates are deterministic and can't be argued around.

**Advisory** = Warning surfaced in output, not blocking.

Gates in order of appearance:
1. Pre-staged files (no in-flight staging area) — STEP 1 / L0
2. PROJECT.md alignment — two-stage gate: deterministic Stage 0 pre-check + alignment-classifier (Haiku) verdict (Issue #1467) — STEP 2 / L1 / F1 / I1.6
3. Plan structural validation (file paths, acceptance criteria, testing strategy) — STEP 5.5c / L2.5
4. Plan-critic verdict (composite ≥ 3.0 to PROCEED) — STEP 5.5b
5. Test gate (0 pytest failures) — STEP 8 / L3 / F3
6. Regression test gate (bug fixes must add a test) — STEP 8 / F3
7. Plan-implementation alignment (< 50% scope divergence) — STEP 8
8. Spec-blind validation verdict (PASS required) — STEP 8.5 / L3.5
9. Hook registration (if new hooks) — STEP 9
10. Agent count gate (minimum agents ran) — STEP 9.5
11. Remediation gate (validators APPROVE / PASS) — STEP 11
12. Skill effectiveness gate (delta > -0.10 if skills modified) — STEP 11.5
13. Doc-drift gate (doc-master PASS, no stale docs) — STEP 12
14. Documentation congruence (counts match reality) — STEP 14

## How to Resume

If the pipeline is interrupted (auto-compact, crash, user `/clear`):

```bash
/implement --resume <run_id>
```

The `run_id` is printed at STEP 0. `--resume <id>` auto-detects the id format via `classify_resume_id()` (Issue #1047):

| Form | Format | Behavior |
|------|--------|----------|
| `batch-*` | Starts with `batch-` | Delegates to [implement-resume.md](../commands/implement-resume.md) (worktree batch recovery) |
| 16-char hex | Exactly 16 lowercase hex chars | Single-run resume — skips RUN_ID generation, sets `RUN_ID=<id>`; completions actually survive because STEP 0 re-runs `record_run_start(sid, RUN_ID)` with the same id against the existing session-hashed state file (see "Run-identity stamping" below), **not** because of a `run_id`-scoped state file — `get_completed_agents(sid, run_id=<id>)` reads a physically different file that no production writer populates and always returns empty (pre-existing gap, characterized not fixed, Issue #1045/#1047) |
| Legacy timestamp | `YYYYMMDD-HHMMSS` | Back-compat single-run resume (pre-#1047 format) |

Any other format is rejected with a message listing all three accepted forms.

Pipeline state for a single run is kept in `/tmp/implement_pipeline_<run_id>.json` (exported as `PIPELINE_STATE_FILE` at STEP 0) and the legacy sentinel `<repo>/.claude/local/implement_pipeline_state.json` (session-level, written for subshell fallback; resolved per-repo via `pipeline_state.get_legacy_sentinel_path()` since Issue #1206 — was machine-global `/tmp/implement_pipeline_state.json`). `SessionStart-batch-recovery.sh` auto-restores batch state after `/clear` or auto-compact.

**Stale-state garbage collection (Issue #1048)**: At STEP 0, immediately before generating a new `RUN_ID`, `pipeline_completion_state._gc_stale_states()` removes any `/tmp` artifacts older than 7200 seconds (2× the staleness TTL): `pipeline_agent_completions_*.json` (both sha256 and run_id paths), `implement_pipeline_*.json` (per-run sentinel files), and `pipeline_*.lock` (orphaned lockfiles). This prevents `/tmp` accumulation from long-lived Claude Code sessions without relying on OS temp-file reaping. All shell references to the sentinel file in `implement.md`, `implement-batch.md`, and `implement-fix.md` use the env-var-aware form `${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}` so the override is respected everywhere. Note: `PIPELINE_STATE_FILE` now defaults to the per-repo path `<repo>/.claude/local/implement_pipeline_state.json` (resolved by `get_legacy_sentinel_path()`) rather than the legacy `/tmp/` literal (Issue #1206).

**PIPELINE_BASE_COMMIT anchoring (Issue #1069)**: At STEP 0 (full pipeline) and STEP F1 (fix pipeline), the coordinator captures `git rev-parse HEAD` as `PIPELINE_BASE_COMMIT` and persists it to the legacy sentinel state file via `pipeline_state.set_pipeline_base_commit()`. At STEP 8.5 (spec-validator dispatch) and STEP F3.5 / STEP F4 (fix-mode spec-validator and security-sensitivity scan), the value is recovered with `pipeline_state.get_pipeline_base_commit()` and used to anchor `git diff --name-only` commands. Without anchoring, `git diff --name-only HEAD` includes files that were modified in the working tree BEFORE the pipeline started, causing spec-validator to emit false-positive FAIL verdicts for acceptance criteria that reference "files in the diff". Callers fall back to `HEAD` when `PIPELINE_BASE_COMMIT` is empty (e.g., no-commit repository, legacy pipelines, missing state file).

**Run-identity stamping fixes a session/run confused-deputy (Issue #1045)**: STEP 0 (`implement.md`) and the per-issue block in `--batch` mode (`implement-batch.md`) also call `pipeline_completion_state.record_run_start(session_id, run_id)` — BEFORE any agent runs, and before generating the run id above. Without it, the agent-completeness gate was keyed by SESSION rather than RUN: a second `/implement` invocation inside one Claude Code session inherited the first run's recorded agent completions and could pass the gate having executed nothing. The import is wrapped in `try/except ImportError` and a `record_run_start` failure exits 1 with `[RUN-START-FAILED run_id=...]`, naming `bash scripts/deploy-all.sh` — a stale deployment must not silently fall back to the pre-fix session-scoped gate. Full five-state policy table and the read-side filter (`get_completed_agents`'s `_filter_to_current_run`) are documented in `docs/LIBRARIES.md`'s `pipeline_completion_state.py` entry.

## Session-ID Propagation Contract

**Added**: Issue #904 (ROOT-CAUSE consolidation of #898 subshell propagation,
#902 remediation false-positive, #875 cross-pipeline isolation).

### Fallback Chain — `env → sentinel → activity-log → 'unknown'`

Every coordinator subshell that needs the current pipeline session id MUST
resolve it with this four-step fallback. The chain is implemented in
`resolve_session_id()` in `lib/pipeline_completion_state.py` (Issue #1093)
and called from `commands/implement.md` at each `python3 -c "..."` heredoc
that reads `CLAUDE_SESSION_ID`:

1. **Environment variable** — `os.environ.get('CLAUDE_SESSION_ID')`
   - Primary source. Claude Code sets this in-process before the coordinator
     runs. This is the only step that works for the very first command in
     a fresh pipeline.
2. **Sentinel file** — `<repo>/.claude/local/implement_pipeline_state.json` → `state['session_id']` (resolved by `pipeline_state.get_legacy_sentinel_path()`; was `/tmp/implement_pipeline_state.json` before Issue #1206)
   - Written by STEP 0 immediately after the env var is read. Provides a
     recovery path when a subshell loses the env var (nested heredocs, pipe
     subshells, `xargs` trampolines, worktree re-entry on `--resume`).
   - **TTL guard (3600s)**: the sentinel is only trusted when its mtime is
     within the last hour. Older sentinels from crashed prior pipelines are
     NOT merged — this prevents cross-pipeline bleed (#875).
   - **Boot-time sentinel skip**: if the sentinel's `session_id` field is the
     literal string `"unknown"` (written before the real session id is
     available), this step is skipped and the chain falls through to the
     activity-log scan. This prevents locking in "unknown" when a real id
     is discoverable from the log.
3. **Activity log scan** — `.claude/logs/activity/{YYYY-MM-DD}.jsonl`
   - Scans today's activity log (written by `session_activity_logger.py`)
     for the most recent entry whose `session_id` field is a non-empty,
     non-"unknown" string. This is the load-bearing fallback for Bash
     subprocess contexts where both env and sentinel carry "unknown" — a
     known boot-time race where STEP 0 writes the sentinel before the real
     session id is available. (Issue #1093)
4. **Literal `'unknown'`** — preserved legacy sentinel.
   - Returned only when env, sentinel, and activity log are all unavailable.
     Downstream code treats `'unknown'` as a first-class session id that
     stores state in its own file.

### Why `'unknown'` is Preserved

Removing `'unknown'` would break the in-flight-boot case documented in
Issues #738 and #777: the coordinator can record some agent completions
under `session_id='unknown'` BEFORE the coordinator's STEP 0 has written
the sentinel. `get_completed_agents()` then MERGES the 'unknown' state into
the primary session's completions so no agent work is lost.

The merge is now gated by the staleness TTL (`STALE_UNKNOWN_TTL_SECONDS =
3600` in `pipeline_completion_state.py`). An 'unknown' state file whose
mtime is older than 3600s is treated as contamination from a crashed prior
pipeline and ignored. Fresh 'unknown' state (mtime < 3600s) is still merged
— preserving the in-flight behavior from #738 / #777.

### Validator Grouping — `(session_id, batch_issue_number)`

`validate_step_ordering()` in `pipeline_intent_validator.py` groups agent
events by the tuple `(session_id, batch_issue_number)` before checking
sequential-pair ordering. The tuple key ensures that two independent
pipeline runs writing to the same daily JSONL file never cross-contaminate
each other's ordering checks (#875).

Non-batch events with an empty `session_id` and `batch_issue_number=0`
still group under the single key `('', 0)` — behavior is unchanged for
legacy single-session logs. The per-issue isolation added in #680 is
preserved because different `batch_issue_number` values still produce
distinct groups even within the same `session_id`.

### Remediation Flag — `is_remediation=True`

`record_agent_completion(..., is_remediation=True)` marks a completion as
part of a remediation cycle (e.g., reviewer re-run after BLOCKING findings
from security-auditor). Events flagged as remediation are SKIPPED by the
duplicate-agent ordering check in `_validate_step_ordering_for_group()`,
which prevents #902's false CRITICAL: "reviewer ran before reviewer".

The flag is persisted in the completion state JSON as:

```json
{"completions": {"0": {"reviewer": {"success": true, "remediation": true}}}}
```

Legacy plain-bool entries continue to work unchanged (`{"reviewer": true}`
still reads as success). See `_completion_is_success()` in
`pipeline_completion_state.py` for the dual-shape reader.

### Background Agent Flag — `is_background=True` (Issue #906 / #882)

`PipelineEvent.is_background` marks activity-log events that originate from
agents launched with `run_in_background=true` (e.g., the continuous-improvement
analyst at STEP 15, or doc-master in parallel-validation mode).

**Why it matters for ordering checks**: A background agent's JSONL timestamp
reflects when the coordinator dispatched it, not when the agent actually
finished. In practice this means doc-master's log entry can appear *before*
foreground agents (reviewer, security-auditor) even though it ran concurrently
or after them. Without the exemption, `_validate_step_ordering_for_group()`
would emit a false CRITICAL `step_ordering` finding:
"doc-master ran before reviewer" when in fact both ran in STEP 10 and the
ordering was intentionally parallel.

**How it works**:

1. `session_activity_logger.py` writes `is_background: true` into the
   `input_summary` dict of any Agent/Task log entry that has
   `tool_input.run_in_background=true`. The field is absent (falsy) for
   foreground agents — clean log format.
2. `_parse_single_log()` in `pipeline_intent_validator.py` reads
   `input_summary.is_background` and sets `PipelineEvent.is_background`
   accordingly. Missing field defaults to `False` for backward compatibility
   with logs that pre-date this feature.
3. `_validate_step_ordering_for_group()` filters `is_background=True` events
   out of both `first_events` and `second_events` before performing any
   sequential-pair timestamp comparison. Background events are therefore
   invisible to step-ordering checks — only foreground agent events
   participate.

**What is still enforced**: Background agents are not exempt from *other*
validator checks (context-dropping, hard-gate ordering, minimum agent count).
The exemption is narrow: sequential *timestamp* ordering only.

### Background Agents Never Fire Stop/SubagentStop (Anthropic #25147)

Agents launched with `run_in_background=true` **never fire the `Stop` or
`SubagentStop` hook events** — this is a Claude Code platform limitation
(Anthropic #25147, marked won't-fix). No hook can auto-record a background
agent's completion, because the hook that would record it never runs.

**How background-agent completion is recorded**: coordinator-side. When a
background agent returns, the coordinator (`commands/implement.md`) calls
`record_agent_completion()` directly for that agent. This is the intended
design, **not a bug** — the completeness gate reads those coordinator-written
records exactly as it reads hook-written ones.

**What the SubagentStop hook does instead** (`unified_session_tracker.py`):
best-effort handling for the *foreground / internal* firings that DO reach the
hook. Four behaviors (two from #1396, one from #1436, one from #1512) apply
only to those firings:

0. **Phantom-stop classification** (Issue #1512) — runs first, before the
   #1087 cache pop below. A `SubagentStop` naming an `agent_transcript_path`
   that does not exist on disk (after a short grace/poll window) is a
   *phantom*: it previously won the #1087 invocation cache and used the
   recovered #1484 generation token to disarm a still-running dispatch's
   `agent_dispatch_sentinel`. A phantom classification skips both the cache
   pop and the sentinel `clear()` call, and is logged as a
   `__phantom_stop__:<agent_name>` JSONL audit entry (no
   `record_agent_completion()` call). An empty or out-of-`~/.claude` path is
   classified UNKNOWN, not phantom, and falls through to today's behavior.
1. **Agent-type recovery** — when the payload and the #1087 PreToolUse cache
   both omit `agent_type`, `_resolve_agent_type_from_transcript()` scans the
   subagent transcript's early entries for the agent identity (best-effort;
   undocumented schema, Anthropic #27423 / #27755).
2. **Heartbeat drop** — internal SubagentStop firings with no usable identity
   (empty `agent_type`, zero duration, no cache hit, no transcript-resolved
   identity) are dropped rather than recorded, cutting the bulk (~95 of ~113)
   of noise events per run. The drop is ordered before the #1414 phantom-dedup
   block so it never perturbs `_PHANTOM_DEDUP_CACHE`.
3. **Unattributable-firing guard** (Issue #1436) — a firing with a non-zero
   duration or substantive output survives the heartbeat drop above but can
   still lack a real identity (`agent_type` empty, whitespace-only, or the
   literal `"unknown"`). `_is_unattributable()` checks for this class BEFORE
   the #1414 `phantom_key` is computed, so it never enters
   `_PHANTOM_DEDUP_CACHE` — keying on `(session_id, "")` would otherwise
   collapse two distinct empty-identity firings into one and silently
   suppress a genuine completion. The firing is still logged as a
   `__unattributable__:<agent_name>` JSONL audit entry, and
   `record_agent_completion()` is still called for #1396 backward-compat, but
   `_is_gate_countable_agent()` in `pipeline_completion_state.py` makes that
   call a no-op — unattributable identities are never persisted into
   completion state and can never satisfy the agent-completeness gate
   (fail-closed). `get_completed_agents()` and `agent_output_health.py`'s
   `_get_agent_completions()` apply the equivalent filter on read, so
   pre-existing empty/`"unknown"` completion-state keys and `__`-prefixed
   sentinel markers in the activity log are both excluded.

None of these behaviors touches background agents (they never reach the hook). For the
complementary read-side recovery at the `git commit` completeness gate — where
a Bash subprocess may evaluate the wrong session id — see the #1228 read-side
session-id fallback in `unified_pre_tool.py::_check_pipeline_agent_completions`.

## Related

- [commands/implement.md](../plugins/autonomous-dev/commands/implement.md) — authoritative pipeline definition
- [AGENTS.md](AGENTS.md) — agent specs and model tiers
- [HOOKS.md](HOOKS.md) — which hooks enforce which gates
- [BATCH-PROCESSING.md](BATCH-PROCESSING.md) — batch mode deep-dive
- [WORKFLOW-DISCIPLINE.md](WORKFLOW-DISCIPLINE.md) — why hard gates over nudges
- [EVALUATION.md](EVALUATION.md) — how the CI analyst observes pipeline integrity
