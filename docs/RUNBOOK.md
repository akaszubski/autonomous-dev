# Runbook — autonomous-dev

Operational sequences for maintainers. Not loaded into context; consulted on demand.

For behaviour rules see [`CLAUDE.md`](../CLAUDE.md). For purpose, scope, and architecture see [`.claude/PROJECT.md`](../.claude/PROJECT.md). For content placement rules see [`docs/development/CONTENT_ALLOCATION.md`](development/CONTENT_ALLOCATION.md).

---

## Build & Test

Testing uses the **Diamond Model** (not traditional TDD pyramid). Acceptance criteria drive testing; unit tests are regression locks, not specifications. See [docs/TESTING-STRATEGY.md](TESTING-STRATEGY.md).

**Python 3.14 + cryptography environment workaround** (closed #1286 from 2026-06-22 audit): on machines with Python 3.14 and a system-installed `cryptography` wheel that wasn't built for 3.14, pytest plugin auto-load fails with `ImportError: cannot import name 'exceptions' from 'cryptography.hazmat.bindings._rust'`. Workaround for any `pytest` invocation:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest --override-ini="addopts=" <targets>
```

`/implement`'s test gate, `/implement --fix`'s test context capture, and the implementer agent's verification steps should use this form when the environment trips this error.

```bash
# Full deterministic suite (unit + integration + regression + security + property)
pytest --tb=short -q

# Specific test file
pytest tests/unit/hooks/test_native_tool_auto_approval.py -v

# By layer
pytest tests/unit/                    # Layer 2: Unit tests (regression locks)
pytest tests/property/                # Layer 3: Property-based invariants (Hypothesis)
pytest tests/integration/             # Layer 4: Integration & contract tests
pytest tests/regression/smoke/        # Fast critical-path smoke tests
pytest tests/security/                # Security-specific tests

# GenAI tests (LLM-as-judge, probabilistic — not in default runs)
pytest tests/genai/ --genai           # Layer 5: Semantic validation (~$0.02/run)
pytest tests/genai/ --genai --strict-genai  # Strict mode (no soft failures)

# Property tests with CI thoroughness (200 examples per test vs 50 default)
HYPOTHESIS_PROFILE=ci pytest tests/property/

# Coverage
pytest --cov=plugins/autonomous-dev/hooks --cov=plugins/autonomous-dev/lib --cov-report=term-missing
```

**Test directories → Diamond layers**: `tests/unit/` (L2), `tests/property/` (L3), `tests/integration/` + `tests/regression/` (L4), `tests/genai/` (L5), `tests/spec_validation/` (L5/L6).

---

## Manual perf-smoke procedure (Issue #1133 AC8)

When changing in-place cluster mode (`/implement --batch ... --no-worktree`, `scripts/drain-all.sh --cluster-mode`, or `scripts/triage-and-implement.sh` default flow), run this manual perf-smoke against a real 3-issue cluster to verify the cluster mode achieves the ≥40% wall-clock reduction acceptance target vs. running each issue serially.

**Setup**:

1. Pick a real 3-issue cluster from `/triage --auto-improvement` (any cluster with `issue_numbers` of length 3, no PRs open, no closed-state issues). Record the issue numbers as `N1 N2 N3`.
2. Confirm the working tree is clean: `git diff --quiet && git diff --cached --quiet || echo DIRTY`.
3. Reset to a known-good baseline commit so both runs start from the same state.

**Run A — cluster mode** (one cluster invocation, `--no-worktree`):

```bash
git checkout master && git pull
START_A=$(date +%s)
bash scripts/drain-all.sh --cluster-mode --limit 3
END_A=$(date +%s)
echo "Cluster mode duration: $((END_A - START_A))s"
# Hard-reset so Run B starts from the same baseline as Run A.
git reset --hard origin/master
```

**Run B — per-issue baseline** (the legacy `--no-cluster` per-issue loop):

```bash
git checkout master && git pull
START_B=$(date +%s)
for n in N1 N2 N3; do
  rm -f "${PIPELINE_STATE_FILE:-$(python3 -c 'from pipeline_state import get_legacy_sentinel_path; print(get_legacy_sentinel_path())' 2>/dev/null || echo .claude/local/implement_pipeline_state.json)}" /tmp/implement_pipeline_state.json 2>/dev/null || true
  claude --print --permission-mode acceptEdits "/implement $n"
done
END_B=$(date +%s)
echo "Per-issue baseline duration: $((END_B - START_B))s"
```

**Acceptance criterion** (AC8): The cluster-mode duration MUST be at least 40% lower than the per-issue baseline:

```bash
python3 -c "
A = (END_A - START_A); B = (END_B - START_B)
ratio = (B - A) / B if B else 0
print(f'Cluster {A}s vs Baseline {B}s — reduction {ratio*100:.1f}% (target ≥40%)')
assert ratio >= 0.40, 'FAIL: cluster mode did not achieve ≥40% wall-clock reduction'
"
```

If the reduction is below 40%, file a regression issue with both event-stream logs (`logs/drain-all/*.events.json`) attached and the timing measurements above. Common causes: cluster-mode lost per-issue parallelism (unlikely — both modes are serial), hook gates fire redundantly per-issue inside the cluster, or doc-master / CIA runs are not being shared across the cluster's commits.

---

## Periodic Maintenance

These tasks aren't part of the per-commit workflow — they're run on a maintainer cadence (roughly monthly) to keep load-bearing infrastructure calibrated. Per-event automations have periodic-aggregation counterparts; this is where the periodic side lives.

| Task | Command | When to run |
|------|---------|-------------|
| Refresh intent classifier calibration corpus | `python3 scripts/extract_and_label_intent_corpus.py --source both --cost-cap-usd 0 --max-prompts 200 --output tests/fixtures/intent_classifier_real_corpus.json` | Monthly, or when classifier behavior feels off. Uses your `claude` CLI subscription auth. See [docs/INTENT-CLASSIFICATION.md](INTENT-CLASSIFICATION.md) and [docs/SCRIPTS.md](SCRIPTS.md). |
| Sweep narrative docs for drift | `/refactor --docs` | Monthly, or after multiple feature batches land. doc-master in `/implement` only checks docs covering changed files; narrative docs (README, ARCHITECTURE-OVERVIEW, HARNESS-EVOLUTION) need a periodic full-state pass. For the prior redundancy behavior, use `--docs-redundancy`. |
| Triage CIA-filed auto-improvement issues | `/triage --auto-improvement` | Weekly. CIA files per-session findings; this command groups them by root cause, sequences dependencies, drops noise, and emits a ranked work queue. Idempotent on a clean queue. **Note**: [ADR-002](ADR-002-drain-queue-redesign.md) Phase A is COMPLETE (severity classifier fixed, watchdog self-loop eliminated); Phase B is IN PROGRESS (workflows bypass /drain-queue — issues #1274, #1276). |
| Content allocation sweep | `/refactor --quick` then manual check against [CONTENT_ALLOCATION.md](development/CONTENT_ALLOCATION.md) | Every ~10 sessions or after major refactors. Compress memory duplicates of CLAUDE.md rules to pointers; delete RESOLVED/DONE/SUPERSEDED findings. |

### Periodic-Aggregation Passes (Per-Event Automation ↔ Periodic-Aggregation Duality, Issue #1075)

Per-event automations (doc-master in /implement, CIA in /implement, baseline capture at STEP 1) work well in isolation but each has an unfilled counterpart need: a periodic full-state pass that aggregates across many events. The shape is consistent:

| Per-event automation | Periodic-aggregation pass |
|---|---|
| doc-master per commit (changed-files scope only) | `/refactor --docs` — narrative-doc sweep |
| Test-baseline per session (per-pipeline only) | Machine-readable baseline snapshot across sessions |
| CIA per session (one issue at a time) | Triage pass — root-cause grouping of accumulated `auto-improvement` queue |

A periodic-aggregation pass:
- Runs at maintainer cadence (weekly/monthly), not per-commit.
- Reads accumulated state from prior events.
- Identifies gaps, duplicates, dependencies, drift that per-event scope cannot see.
- Outputs either **updates** (docs reconciled in place) or a **ranked work queue** (triaged issues, baseline snapshot).

This is the architectural layer that catches drift no per-event hook can see — by design, per-event automations have a single-commit blast radius. Periodic passes are additive: they do not replace or modify per-event hooks. Implementations land incrementally — pick one, generalize the pattern, then port to the other variants. The weekly drain sequence — the human-triggered PROPOSE-mode governance loop — is documented in [Weekly Drain Sequence (PROPOSE mode)](#weekly-drain-sequence-propose-mode) below.

### Weekly Drain Sequence (PROPOSE mode)

The weekly drain is the human-triggered governance loop that turns accumulated CIA findings into merged, deployed improvements. It is intentionally human-gated: one digest reviewed per cycle, no plugin scheduling dependency (`/schedule` is an optional harness capability, not a prerequisite).

**Step sequence:**

1. `/triage --auto-improvement` — groups accumulated CIA findings by root cause, sequences dependencies, drops noise, and emits a ranked work queue.
2. Review the output; select the top cluster.
3. `/implement --issues <cluster>` — runs the full SDLC pipeline on the selected cluster.
4. `/improve --auto-file` — collects CIA findings, runs the macro-promotion layer, emits the 5-section direction-guard digest, and persists the report to `.claude/logs/aggregated_reports.jsonl`.
5. `bash scripts/deploy-all.sh` — **MANDATORY final step.** Handles local install, Mac Studio remote deploy, validation, and integrity checks. The validation exit code is both a digest metric and an AUTO-flip prerequisite (see below).
6. Review the digest. The first two weekly reviews **double as the threshold-recalibration checkpoint** for the tunable promotion thresholds (`PROMOTION_FREQUENCY_MIN`, `PROMOTION_DISTINCT_SESSIONS_MIN`, and related constants) in `plugins/autonomous-dev/lib/macro_promotion.py` — that file's inline re-evaluation comment block names this checkpoint as its trigger.

**PROPOSE mode governance:** Human triggers weekly; reviews one digest per cycle; no plugin scheduling dependency — `/schedule` is an optional harness capability, not a prerequisite for this loop. The loop is intentionally human-gated pending the AUTO-flip criteria below.

**AUTO-flip criteria** (all four must be true before automating the drain):

- `#1041 closed`
- `#1195 closed`
- 2 consecutive PROPOSE drains with zero `.claude/.bypass` events (proxy: pipeline ran without emergency hook-disable overrides)
- `bash scripts/deploy-all.sh` validation exit 0 on both of those runs

**Direction guards** (reviewed each cycle):

1. PROJECT.md alignment gate unchanged — `/implement` STEP 2 runs on every drain; features that drift from scope are blocked before any code is written.
2. Worktree isolation — each cluster runs in its own worktree; partial work cannot contaminate the trunk.
3. Nothing merges on red — validation failures in `deploy-all.sh` stop the deploy; the cycle does not advance until the gate is green.
4. Digest metrics reviewed each cycle: open `auto-improvement` issue count trend; recurrence-after-close rate (the `FIX DIDN'T STICK:` loud-line from the digest, surfaced by `detect_recurrence_after_close` in `macro_promotion.py`); test count trend; `deploy-all.sh` validation pass rate; `.claude/.bypass` event count — **alarm if > 0** (if non-zero, investigate before considering AUTO-flip).
5. The digest shape: the 5-section anti-habituation artifact produced by `format_digest` in `macro_promotion.py`: (1) ACTIONS TAKEN — Promoted/Appended/Held/Expired + create-failure surfacing; (2) Recurrence-after-close including `FIX DIDN'T STICK:` lines; (3) Match-rate with count-gated alarm (<50% matched while >20 open auto-improvement issues); (4) Findings-per-session with CIA-emission-failure alarm (0 vs ~5/session baseline); (5) Error-without-other-channel. All 5 sections render even when empty — absence of an expected signal is loud by design.

---

## Session Continuity

`SessionStart-batch-recovery.sh` auto-restores batch state after `/clear` or auto-compact. Activity logged to `.claude/logs/activity/` by `session_activity_logger.py`.

Every Claude Code session is archived by `conversation_archiver.py` (Stop hook). Full transcripts + SQLite index at `~/.claude/archive/`. See [docs/SESSION-ANALYTICS.md](SESSION-ANALYTICS.md) for full schema and [docs/EVALUATION.md](EVALUATION.md) for how this feeds the self-improvement loop.

Session-history SQL examples live in the **global** `~/.claude/CLAUDE.md` since they apply across all repos — don't duplicate them here.

---

## Distribution

**Component counts** (kept here so test_documentation_congruence verifies they stay in sync with disk): 6 settings templates in `plugins/autonomous-dev/templates/`. Agent/skill/command/hook/library counts live in `CLAUDE.md`.

**Bootstrap-First Architecture** — install.sh is the primary installation method.

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**Why bootstrap-first?** autonomous-dev requires global infrastructure that the marketplace cannot configure:
- Global hooks in `~/.claude/hooks/`
- Python libraries in `~/.claude/lib/`
- Specific `~/.claude/settings.json` format

**What install.sh does:**
- Downloads all plugin components
- Installs global infrastructure (hooks, libs)
- Installs project components (commands, agents, config)
- Non-blocking: Missing components don't block workflow

**Uninstall:**
```bash
/sync --uninstall --force
```

**Deploy to multiple repos** (maintainer-only):
```bash
bash scripts/deploy-all.sh             # Local + Mac Studio
bash scripts/deploy-all.sh --local     # Local only
bash scripts/deploy-all.sh --remote    # Mac Studio only
bash scripts/deploy-all.sh --dry-run   # Preview
```

---

## Consumer-side auto-update (launchd)

**Why tag-and-pull instead of CI push?** GitHub Actions has no SSH credentials for arbitrary consumer Macs, and adding per-host SSH keys to repo secrets is operationally fragile (rotation, revocation, audit). Instead, every push to `master` triggers `.github/workflows/auto-tag-on-push.yml`, which emits an annotated tag of the form `autonomous-dev-v<patch>+<sha7>`. Each consumer Mac runs `scripts/pull-plugin-update.sh` on a launchd interval timer; the script fetches tags, compares the latest against a local state file, and runs `bash scripts/deploy-all.sh --local --no-global` only when a new tag is present.

The result is **eventual consistency without inbound credentials**: every consumer converges to the latest tagged master, idempotently, without GitHub needing to know about their hostnames.

### One-time setup per consumer Mac

1. **Verify the script is executable** (it ships with the executable bit set, but verify after a fresh `git clone`):

   ```bash
   chmod 755 ~/Dev/autonomous-dev/scripts/pull-plugin-update.sh
   ```

2. **Manual smoke test** before installing the timer:

   ```bash
   bash ~/Dev/autonomous-dev/scripts/pull-plugin-update.sh --dry-run
   ```

   Expected: log line "DRY-RUN: would checkout master, pull --ff-only, ..." and exit 0. If you see a git error, fix the working-tree state before installing launchd (the timer will surface the same error every 30 minutes otherwise).

3. **Install the launchd plist** (template below). Save as `~/Library/LaunchAgents/com.autonomousdev.pullupdate.plist`:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
     "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.autonomousdev.pullupdate</string>
       <key>ProgramArguments</key>
       <array>
           <string>/bin/bash</string>
           <string>/Users/REPLACE_ME/Dev/autonomous-dev/scripts/pull-plugin-update.sh</string>
       </array>
       <key>StartInterval</key>
       <integer>1800</integer>
       <key>RunAtLoad</key>
       <true/>
       <key>StandardOutPath</key>
       <string>/Users/REPLACE_ME/Dev/autonomous-dev/.claude/logs/pull-plugin-update.stdout.log</string>
       <key>StandardErrorPath</key>
       <string>/Users/REPLACE_ME/Dev/autonomous-dev/.claude/logs/pull-plugin-update.stderr.log</string>
   </dict>
   </plist>
   ```

   Replace `REPLACE_ME` with your username, then load the agent:

   ```bash
   launchctl load ~/Library/LaunchAgents/com.autonomousdev.pullupdate.plist
   ```

   `StartInterval=1800` = run every 30 minutes. Adjust per environment (production: 1800; lab: 300).

### Operations

| Action | Command |
|---|---|
| Disable the timer | `launchctl unload ~/Library/LaunchAgents/com.autonomousdev.pullupdate.plist` |
| Re-enable | `launchctl load ~/Library/LaunchAgents/com.autonomousdev.pullupdate.plist` |
| Force a run now | `bash ~/Dev/autonomous-dev/scripts/pull-plugin-update.sh` |
| Tail logs | `tail -f ~/Dev/autonomous-dev/.claude/logs/pull-plugin-update.log` |
| See last applied tag | `cat ~/Dev/autonomous-dev/.claude/local/last_pulled_tag` |
| Reset state (force re-deploy) | `rm ~/Dev/autonomous-dev/.claude/local/last_pulled_tag` |

### Failure modes

| Symptom in log | Cause | Recovery |
|---|---|---|
| `git fetch origin --tags failed` | Network / GitHub outage | Wait; next tick retries. Investigate if persistent. |
| `git checkout master failed (working tree may be dirty)` | Local edits on consumer Mac | Commit, stash, or discard local changes manually. |
| `git pull --ff-only failed (master may have diverged)` | Consumer Mac has local commits ahead of origin | Reconcile manually; the script will not force-push or rebase. |
| `Tag ... is not an ancestor of HEAD after pull` | Race between fetch and pull, or tag on different branch | Re-run manually; the next tick should recover. |
| `deploy-all.sh failed. State file NOT updated.` | Plugin deployment error | Inspect `pull-plugin-update.log`; the next tick will retry deployment because state was not advanced. |

The script is **idempotent**: if the latest tag matches the state file, it exits 0 silently. Repeated invocations are cheap (one `git fetch`, no checkout, no deploy).

---

## Enforcement

**PROJECT.md is the gatekeeper** — All work validates against this file before execution.

**Blocking enforcement:**
- Feature doesn't serve GOALS → BLOCKED
- Feature is OUT of SCOPE → BLOCKED
- Feature violates CONSTRAINTS → BLOCKED

**Options when blocked:**
1. Update PROJECT.md to include the feature
2. Modify the request to align with current scope
3. Don't implement

PROJECT.md is the source of truth for strategic direction.

---

## Common Queries

Most session-history SQL queries live in the global `~/.claude/CLAUDE.md` (cross-repo). Project-specific examples below.

```bash
# Recent autonomous-dev sessions
sqlite3 -header -column ~/.claude/archive/sessions.db \
  "SELECT substr(session_id,1,8) sid, last_updated, message_count, model,
          substr(first_user_prompt,1,60) prompt
   FROM sessions WHERE project='autonomous-dev'
   ORDER BY last_updated DESC LIMIT 10;"

# Find transcript for a session id prefix
sqlite3 ~/.claude/archive/sessions.db \
  "SELECT archive_path FROM sessions WHERE session_id LIKE 'abc12345%';"
```

For full schema and cross-repo aggregation queries see [SESSION-ANALYTICS.md](SESSION-ANALYTICS.md).
