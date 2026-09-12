---
covers:
  - bootstrap/control_trust/
  - .github/workflows/control-runner-trust.yml
---

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

## Control-Tool Trust Harness Local Reproduction (F0, #1773)

Pinned local reproduction of `.github/workflows/control-runner-trust.yml`'s job `trust`, step `control-tool-complexity-ratchet` — the SAME frozen suite and measurement profile as CI (`-B -I`, no ambient config/conftest/cache/plugin autoload, isolated `--basetemp`), never byte-identical local/CI argv: CI's `F0_PYTHON` resolves to a runner-specific tool-cache interpreter under its own runner-temp roots, and a local venv path legitimately differs. Report the raw pytest exit this command prints, not a job's overall conclusion — an action's own POST steps can still fail a CI job after this named step's own exit is already recorded. This proof suite carries its own separate 10-minute rung re-proof budget (v12 §5/§8); it does not replace the ordinary `<60s` fast-test and `<10s` hook budgets used elsewhere in this file. Run all of this from the F0 checkout root — `$PWD` below is assumed to be the repository root.

**One-time setup** (needs network; the isolated proof run below does not) — venv creation, the exact-version check, and the pinned dependency install all run inside ONE subshell, so a failed creation or a failed version check stops before `pip install` ever runs:

```bash
(
  python3.11 -m venv /path/to/private/venv || {
    echo "REFUSED: venv creation failed — do not proceed" >&2
    exit 1
  }
  /path/to/private/venv/bin/python -c \
    "import sys; assert sys.version_info[:3] == (3, 11, 14), sys.version" || {
    echo "REFUSED: venv Python is not 3.11.14 — do not proceed" >&2
    exit 1
  }
  /path/to/private/venv/bin/python -m pip install pytest==8.4.2 PyYAML==6.0.2
)
```

**Isolated proof run** (a fresh scratch root per invocation — `mktemp -d` templates end in `X`s so every run gets a unique directory; never reuse or hand-pick `--basetemp`, and never point scratch at the live worktree). Scratch allocation is refused explicitly before anything runs. The raw pytest exit is captured under an `if`/`else` and returned from a subshell. This block re-validates the pinned Python/pytest/PyYAML versions at the top of every invocation and hard-bounds the pytest subprocess to 600s via a small stdlib `subprocess.run(..., timeout=600)` wrapper:

```bash
(
  f0_scratch=$(mktemp -d "${TMPDIR:-/tmp}/f0-proof-run.XXXXXXXX") || {
    echo "REFUSED: could not allocate a scratch root — refusing rather than running with an empty prefix" >&2
    exit 1
  }
  if env -i PATH=/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
       /path/to/private/venv/bin/python -B -I -c '
import importlib.metadata as m, subprocess, sys
assert sys.version_info[:3] == (3, 11, 14), "REFUSED: interpreter is not 3.11.14: " + sys.version
assert m.version("pytest") == "8.4.2", "REFUSED: pytest is not 8.4.2: " + m.version("pytest")
assert m.version("PyYAML") == "6.0.2", "REFUSED: PyYAML is not 6.0.2: " + m.version("PyYAML")
try:
    rc = subprocess.run(
        [sys.executable, "-B", "-X", "pycache_prefix=" + sys.argv[1] + "/pycache", "-I",
         "-m", "pytest", "-p", "no:cacheprovider", "-c", "/dev/null",
         "--rootdir=" + sys.argv[2],
         "--basetemp=" + sys.argv[1] + "/tests", "--noconftest", "-q", sys.argv[2]],
        timeout=600,
    ).returncode
except subprocess.TimeoutExpired:
    print("REFUSED: TIMEOUT - local proof exceeded its 600s bound; the exit code below is a timeout marker, not a genuine pytest exit code", file=sys.stderr)
    sys.exit(124)
print(f"pytest raw exit (inner): {rc}")
sys.exit(rc)
' "$f0_scratch" "$PWD/bootstrap/control_trust/proof"
  then
    rc=0
  else
    rc=$?
  fi
  echo "pytest raw exit (outer wrapper): $rc"
  exit "$rc"
)
```

Preserve your venv's own Python executable spelling above — never resolve to a base/system interpreter. What was actually printed decides the outcome, never the outer numeric exit code alone, which cannot injectively encode any of the following: (1) a `REFUSED: TIMEOUT` line on stderr means the 600s wrapper fired before pytest could exit on its own; no `pytest raw exit (inner):` line is printed in this case, because the `except subprocess.TimeoutExpired` branch never reaches that `print`. (2) `pytest raw exit (inner): N` with `N >= 0` means the pytest child exited normally with that status, and ordinary pytest exit codes (0-5) pass through `sys.exit(rc)` unchanged, so the outer wrapper status equals N. (3) `pytest raw exit (inner): N` with `N < 0` means `subprocess.run().returncode` is reporting the pytest child as terminated BY SIGNAL — Python's own convention is that a negative returncode is `-signum` — not that pytest itself exited with a negative status; this is a distinct condition from (1) and (2) and can only be read from this printed line, never inferred from the outer exit alone. `sys.exit(rc)` does not reproduce a negative `rc` at the shell: POSIX process exit statuses are one unsigned byte, so the OS reports `rc & 0xFF` to the wrapping shell (inner `-9` becomes outer `247`) — neither the printed negative value nor bash's own 128+signal convention (137 for a directly signal-killed foreground process), so the outer wrapper status by itself cannot be used to recover which signal killed the child. (4) Neither line was printed at all: the remaining case, most likely a startup/profile failure (a version assertion raising before pytest is invoked) or an interrupted run (killed, disconnected) — treat this as the best available inference from what was captured, not a certainty.

### Documentation-maintenance provenance for this rung (native author → Codex actuator → fresh native verifier)

Temporary F0 maintenance scaffolding for getting this rung's six documentation files corrected during a native-tool-refusal window — not a shipped collector, not evidence for a portable consumer proof, and not a permission bypass; it grants no product state and authorizes nothing beyond the six named files. Three distinct actors, none standing in for another: (1) a read-only native Claude doc-master (Read/Grep/Glob only) that reads the required sources and authors either an unapplied patch or, under a separately recorded exact-delta transport clarification, a JSON array of exact `old`/`new` replacement records against a previously bound, digest-identified draft patch; (2) Codex acting only as the mechanical, exact-byte patch actuator — applying only the exact bytes the author produced, substituting delta records into a newly derived patch when that is the input rather than repairing or paraphrasing them, after independently re-verifying patch (or derived-patch) identity/digest, each target file's preimage hash, the frozen source hashes the patch cites, unchanged git index/base/branch, and the absence of a current hold; (3) a fresh, full-role native doc-master with no memory of the draft, reading the actual resulting files and performing the real semantic sweep. A drafting-agent PASS, a green CLI exit from the actuator, or the parent's own successful patch application is each someone else's claim, not this gate's completion — only the fresh verifier's independent read of the final files is. Before any actor runs: verify Claude.ai Max subscription authentication is active and scrub paid-API/provider override environment variables from the invoking shell — this procedure runs on existing subscription auth, never a metered key. The originating `/implement` run id and Claude session id are retained across all three actors' invocations rather than minted fresh, so completion state and activity logs stay attributable to one pipeline run. Each of the two native doc-master specialists (the draft author and the fresh verifier) gets the complete canonical doc-master role text, not a summarized persona; Codex's actuator role is mechanical patch application only — it is not a native specialist dispatch and has no canonical role text to receive. Each specialist dispatch's actual Agent-tool result and the independently observed file effects (`git diff`, file hashes) are checked directly — a coordinator's own prose summary of what a child did is not evidence of what the child did. Only OBSERVED completion is recorded through the existing agent-completion APIs; recording one that did not run is FORBIDDEN (see `CLAUDE.md`, Critical Rules). The interactive session's own native pre-tool guard does NOT intercept the parent's separate patch-application tool call, so the scope check (exactly the six named target paths, no Add/Delete/Move/symlink/duplicate target), the preimage check, the source-hash check, the index/base/branch-unchanged check, and the no-current-hold check must all be carried over EXPLICITLY by the applying party using the existing exact-applicator invariants — never assumed inherited from the interactive session's own hooks. Any real denial or hold, a mismatched identity/scope/preimage, a partial application, or an unintended effect STOPS this route immediately — never switch tools, retry through a different path, or record synthetic completion to route around the stop; the correct response is to halt and report, not to route around the guard quietly. The SAME run's lock already held for this rung must remain actually held continuously from the final prechecks above through the parent's ordinary patch-application call and its immediate effect checks — a prior author's already-released lock is not standing ownership for a later actor's application or verification. Session capture for each specialist dispatch preserves `--output-format stream-json`, `--include-hook-events`, `--include-partial-messages` (a liveness signal only, never a completeness one), and `--forward-subagent-text`, plus a `--debug-file` capture (a file path, distinct from the `--debug` flag, which writes to stderr instead); where an Agent result is too large to inspect inline, the persisted tool-result artifact it references is read by its own ID-bound path alongside the raw child output — a truncated preview or a parent's own relay of "it worked" is not a substitute for either.

**Tested streaming-input transport option** (private canary, installed CLI 2.1.236, existing subscription auth, no API key): piping stdin with `--input-format stream-json --output-format stream-json --replay-user-messages --include-hook-events --verbose` accepts newline-delimited user records while the pipe stays open, and each is confirmed by its own exact replayed `user` acknowledgement before its `result` — a `result` message alone is not the final process exit while the pipe remains open; native exit 0 followed the pipe's own close, not either individual result. This does not establish a portable numeric terminal-input-length limit, and does not test or establish mid-tool cancellation, permission callbacks, or resumed-agent delivery guarantees. See [SESSION-ANALYTICS.md](SESSION-ANALYTICS.md) for this rung's own carrier/identifier-join limits, which streaming input does not repair.

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
  # Issue #1411: plain `rm` (no -f/-rf) — the shipped `Bash(rm:-f*)`/`Bash(rm:-rf*)`
  # deny rules hard-block force-delete flags. `--` guards dash-prefixed paths.
  rm -- "${PIPELINE_STATE_FILE:-$(python3 -c 'from pipeline_state import get_legacy_sentinel_path; print(get_legacy_sentinel_path())' 2>/dev/null || echo .claude/local/implement_pipeline_state.json)}" /tmp/implement_pipeline_state.json 2>/dev/null || true
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

## Guard Enforcement Verification (proof-of-block, Issue #1586)

A guard is not enforcement until it has been watched refusing something. `proof_of_block.py`
drives each block-capable guard end-to-end and reports whether it both refused a realistic bad
action and permitted the closest legitimate one — the only artifact in this repo that
demonstrates both control arms, and the only one that runs the same way in a consumer repo.

**Run it**:
```bash
# Source checkout
python3 plugins/autonomous-dev/scripts/proof_of_block.py

# Installed (this repo or a consumer repo, after deploy-all.sh / /sync)
python3 .claude/scripts/proof_of_block.py
```
Exit 0 = every guard PROVEN. Non-zero = see stderr for which guard and why; `--json` for
machine-readable output; `--no-fault` for the faster happy-path-only run used by `/health-check`.

**Re-record the baseline** after adding/removing a guard, or after an intentional change to which
guards fail open silently:
```bash
python3 plugins/autonomous-dev/scripts/proof_of_block.py --record --artifacts tests/proofs
```
Commit the result at `tests/proofs/proof-of-block.json` — deliberately **not** under
`.claude/proofs/` (the harness's own default `--record` target), which `.gitignore:146` (`.claude/*`) ignores;
a baseline recorded there could never be re-committed and the pin would go silently stale.

**CI**: the `smoke` job in `.github/workflows/ci.yml` runs it with `continue-on-error: true`
(tracked: #1604). A pristine `actions/checkout` has no installed `.claude/` marker, so four
protected-infrastructure guards correctly decline to fire and the run reports 3/7 rather than
7/7 — an environment difference, not a regression. The `--check-silent-regression --baseline
tests/proofs/proof-of-block.json` ratchet is deliberately not yet passed in CI for the same
reason; see the workflow file for the closing condition.

---

## Post-deletion consumer-repo sweep (one-time, manual)

**Superseded for the remote transports.** This sequence was written for a defect
where three of six rsync deploy transports shipped without `--delete` — a module
removed from source stayed live and importable via the `sys.path` fallback on
every remote target indefinitely, since `bash scripts/deploy-all.sh` never
deleted it there. Both remote transports (Mac Studio home directory, and each of
the five remote repos) now delete automatically on every `deploy-all.sh` run,
behind a preview guard (`scripts/lib/prune_sync.sh`) that refuses BEFORE
deleting anything if the candidate set looks wrong — see
[`docs/SCRIPTS.md`](SCRIPTS.md#deploy--sync). The manual SSH check below is no
longer required to make deletion happen; it remains useful only as an
independent audit of a deploy that already ran, or for repos this deploy does
not reach.

**Who runs this: a maintainer, by hand, once per deletion of a shipped module.**
It is deliberately NOT an automated test and NOT a CI step — see "Why not a
test" below. Naming the runner is the point: an assertion with no named
execution path is half a control.

When a module that was previously listed in `install_manifest.json` is deleted,
a deploy now removes the stale copy from `~/.claude/lib/` on every configured
target, local and remote, in the same `deploy-all.sh` run. Before the
`prune_sync` guard existed, remote consumer repos kept the already-installed
copy until someone deleted it by hand over SSH — that is the scenario this
sequence audits.

**Sequence** — run after `bash scripts/deploy-all.sh`, once:

```bash
# 1. Local tree must be clean: nothing the source cannot account for.
python3 plugins/autonomous-dev/scripts/deploy_state.py check --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); \
      print("target_only:", d.get("target_only")); \
      print("dirty:", d.get("dirty")); \
      sys.exit(0 if not d.get("target_only") and not d.get("dirty") else 1)'

# 2. On each consumer Mac, the deleted files must be GONE, not merely stale.
#    Any of them still present means the deploy did not delete, only overwrite.
ssh andrewkaszubski@100.103.205.63 'ls ~/.claude/lib/ | grep -E \
  "auto_approval_engine|auto_approval_consent|mcp_permission_validator|\
tool_approval_audit|batch_retry_consent|batch_retry_manager" || echo "CLEAN"'
```

Expected: step 1 exits 0 with an empty `target_only` and `dirty: false`; step 2
prints `CLEAN`. Anything else means the deletion has not reached the machines
that run the code, and the local green is measuring the wrong copy.

**Why not a test.** The interesting state — six named files sitting in a remote
`target_only` — exists only in the window between the deletion commit and the
next deploy. A committed test asserting those six names would pass in that
window and then be permanently vacuous, green forever over a condition it can no
longer observe, and would itself need deleting. `deploy_state.py`'s standing
`target_only` / `dirty` checks already cover the durable form of this class for
every file, not just these six; this sequence is the one-time, deletion-specific
sweep layered on top.

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

### Exit Code Reference

Commands in the autonomous-dev pipeline use the following exit codes:

| Exit Code | Meaning | Context |
|-----------|---------|---------|
| 0 | Success | Normal completion |
| 1 | General failure | Standard error condition |
| 2 | Cross-machine conflict | Another instance holds the claim (implement-batch) |

---

## Launchd-as-heartbeat (drain-driver durable cron)

### Why

GHA's built-in `schedule:` cron is unreliable under high repository load — documented to drop 5-15% of fires during busy periods. The Mac Studio launchd job (`com.akaszubski.drain-driver-cron`, installed 2026-06-22) already exists as a dispatch fallback: it triggers `gh workflow run drain-driver.yml` when the last GHA run is stale (>90 min). But that alone is not a heartbeat — when GHA is current (last run <90 min ago), launchd sees no need to dispatch and stays silent. Healthchecks.io gets no ping → DOWN alert.

**The fix**: `scripts/launchd/drain-driver-cron.sh` pings `HEALTHCHECK_PING_URL` on every successful invocation (`skip`, `ok`, and `DISPATCHED`). Healthchecks alerting is now decoupled from GHA dispatch: as long as Mac Studio is awake and launchd is loaded, the check stays green. GHA becomes the worker; launchd becomes the heartbeat.

Empirical data (2026-06-26): 4 skip events in 7 hours (16% of cycles). Under the old design, 3+ consecutive skips at 30-min cadence would exhaust the 90-min healthchecks threshold (period 60 + grace 30; tightened 2026-06-27 from the prior 240 min once #1326 made Mac Studio the reliable heartbeat source) and page. With skip-branch pinging, that failure mode is closed.

### One-time setup per Mac Studio

1. **Copy script and plist**:

   ```bash
   cp scripts/launchd/drain-driver-cron.sh ~/bin/drain-driver-cron.sh
   chmod 755 ~/bin/drain-driver-cron.sh
   cp scripts/launchd/com.akaszubski.drain-driver-cron.plist \
     ~/Library/LaunchAgents/com.akaszubski.drain-driver-cron.plist
   ```

2. **Substitute the healthchecks UUID** (obtain from healthchecks.io dashboard):

   ```bash
   sed -i '' 's|<your-healthchecks-uuid>|ACTUAL-UUID-HERE|g' \
     ~/Library/LaunchAgents/com.akaszubski.drain-driver-cron.plist
   ```

3. **Verify substitution** — output must show a real URL, NOT contain the literal string `<your-`:

   ```bash
   grep HEALTHCHECK_PING_URL ~/Library/LaunchAgents/com.akaszubski.drain-driver-cron.plist
   ```

   Expected: `<string>https://hc-ping.com/ACTUAL-UUID-HERE</string>`

4. **Prevent Mac Studio from sleeping** (it is a server — sleep causes launchd to skip fires):

   ```bash
   pmset -g | grep -i sleep
   # If "sleep" value is non-zero:
   sudo pmset -a sleep 0
   ```

5. **Load the plist**:

   ```bash
   launchctl unload ~/Library/LaunchAgents/com.akaszubski.drain-driver-cron.plist 2>/dev/null || true
   launchctl load ~/Library/LaunchAgents/com.akaszubski.drain-driver-cron.plist
   ```

6. **Verify loaded**:

   ```bash
   launchctl list | grep drain-driver-cron
   ```

   Expected: a row with the label `com.akaszubski.drain-driver-cron`.

### T+0 fault-injection assertions (run at deploy)

Run all four assertions immediately after loading the plist. Each proves a distinct load-bearing behaviour.

#### (a) `ok` branch ping verification

Tail the log and wait up to one 30-min cycle:

```bash
tail -f ~/Library/Logs/drain-driver-cron.log
```

Expect at least one line containing `ok` within 30 minutes. Then verify healthchecks received the ping:

```bash
curl -s "https://healthchecks.io/api/v3/checks/<uuid>/" -H "X-Api-Key: $HEALTHCHECKS_API_KEY" \
  | jq -r .last_ping
```

The timestamp returned MUST be within the last 30 minutes. If `last_ping` is older or null, the curl in `_ping_ok()` is failing — check Mac Studio network connectivity and `HEALTHCHECK_PING_URL` value.

#### (b) `skip` branch ping verification

Force a skip by dispatching an active run in the background, then wait for the next launchd fire:

```bash
gh workflow run drain-driver.yml --repo akaszubski/autonomous-dev --ref master &
sleep 60
```

Within the next 30-min launchd cycle, the log MUST contain a `skip (active=...)` line. Within 5 minutes of that skip, re-check `last_ping` — it MUST have advanced. Proves the skip branch pings and closes the consecutive-skip starvation gap.

#### (c) Placeholder preflight regression test

Verify the script exits 1 immediately if the placeholder was never substituted:

```bash
# Copy plist with placeholder still present to a throwaway label
cp ~/Library/LaunchAgents/com.akaszubski.drain-driver-cron.plist /tmp/com.test.placeholder-check.plist
# Edit the throwaway to revert to placeholder (if your plist already has real UUID, fake it)
sed -i '' 's|hc-ping.com/[^<]*|hc-ping.com/<your-test-placeholder>|g' /tmp/com.test.placeholder-check.plist
# Adjust the label so it doesn't clash:
sed -i '' 's|com.akaszubski.drain-driver-cron|com.test.placeholder-check|g' /tmp/com.test.placeholder-check.plist
launchctl load /tmp/com.test.placeholder-check.plist
# Wait one fire (or manually run the script with the placeholder URL):
HEALTHCHECK_PING_URL="https://hc-ping.com/<your-test-placeholder>" bash ~/bin/drain-driver-cron.sh || true
grep "ERROR: HEALTHCHECK_PING_URL placeholder not substituted" ~/Library/Logs/drain-driver-cron.log
# Cleanup:
launchctl unload /tmp/com.test.placeholder-check.plist 2>/dev/null || true
rm /tmp/com.test.placeholder-check.plist
```

MUST produce the `ERROR: HEALTHCHECK_PING_URL placeholder not substituted` log line. Proves the script fails fast on deploy-time misconfiguration instead of silently pinging nothing.

#### (d) Skip-only-removal negative test (destructive — restore after)

This test proves the skip-branch ping is load-bearing (not dead code):

```bash
# Temporarily comment out _ping_ok in the skip branch only:
sed -i '' 's/^    _ping_ok$/    # _ping_ok  # NEGATIVE-TEST: temporarily removed/' \
  ~/bin/drain-driver-cron.sh
```

On a day with active GHA runs (high-skip probability), watch `last_ping` for 90+ min. If skip is the only branch firing, `last_ping` will NOT advance → healthchecks would alert after 90 min (period 60 + grace 30, tightened 2026-06-27). This proves skip-branch ping is not redundant. Restore immediately:

```bash
sed -i '' 's/^    # _ping_ok  # NEGATIVE-TEST: temporarily removed$/    _ping_ok/' \
  ~/bin/drain-driver-cron.sh
```

### T+7 days success verification

Seven days after deploy, run:

```bash
curl -s "https://healthchecks.io/api/v3/checks/<uuid>/flips/?seconds=604800" \
  -H "X-Api-Key: $HEALTHCHECKS_API_KEY" \
  | jq '[.flips[] | select(.up == 0)] | length'
```

- **0** → PASS. No DOWN flips in the 7-day window. The fix is working.
- **≥1** → FAIL. Investigate: tail `~/Library/Logs/drain-driver-cron.log` for the failure window, check `launchctl list | grep drain-driver-cron` (PID column shows last exit code), verify Mac Studio was not asleep (`pmset -g log | grep -i "sleep" | tail -20`).

### Consecutive-skip starvation risk

Empirical observation (2026-06-26): 4 skip events in a 7-hour window = 16% skip rate. Under the pre-fix design at the current 90-min threshold (period 60 + grace 30, tightened 2026-06-27), just 3 consecutive skips at 30-min cadence would exhaust the window and page (the prior 240-min threshold tolerated 8 skips, but #1326 made Mac Studio reliable enough to tighten). The `_ping_ok` call in the skip branch closes this gap: every skip cycle now advances `last_ping`, so consecutive skips never starve the check. This is why `_ping_ok` in the skip branch is NOT optional and NOT equivalent to `_ping_ok` in only the `ok`/`DISPATCHED` branches — and the tighter threshold makes this property even more load-bearing.
