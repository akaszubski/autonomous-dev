---
covers:
  - scripts/
---

# Scripts Reference

Operational tooling at `scripts/`. These are the scripts you run directly (bash/python CLI), separate from hooks (automatic) and commands (slash commands).

---

## Deploy & Sync

### `scripts/deploy-all.sh` — **The canonical deploy**

```bash
bash scripts/deploy-all.sh
bash scripts/deploy-all.sh --global-settings  # also register hooks in ~/.claude/settings.json
```

Deploys the plugin to all configured targets: local machine + all dogfooding repos + Mac Studio via SSH. Auto-detects Mac Studio reachability (LAN `10.55.0.2` with 3s probe; falls back to Tailscale `100.103.205.63`). Idempotent — safe to re-run. Performs per-target validation (hooks parse, match source SHA, all registered). Exits non-zero if any target fails validation.

**Default behavior (Issue #995)**: Hook FILES are cached to `~/.claude/hooks/` (library cache for future foreign-repo opt-in), but hooks are **NOT** registered in `~/.claude/settings.json` by default. Per-repo `<repo>/.claude/settings.json` registration is unchanged — autonomous-dev itself continues to work. To also register hooks globally, pass `--global-settings`.

**Flags:**
- `--global-settings` — opt-in: register hooks in `~/.claude/settings.json` (Issue #995)
- `--no-global` — skip global `~/.claude/` sync entirely (takes precedence over `--global-settings`)
- `--local` — local machine only
- `--remote` — Mac Studio only
- `--dry-run` — preview without writing
- `--skip-validate` — skip post-deploy validation

**Environment:**
- `REMOTE_HOST` — override remote target (default: auto-detect)
- `SKIP_REMOTE=1` — skip remote push entirely

**Related**: `scripts/deploy_local.sh` (local-only), `scripts/deploy-to-repos.sh` (dogfood repos only).

### `scripts/dogfood-bootstrap.sh`

Bootstrap dogfooding on a new repo — install plugin, configure `~/.claude/settings.json` for that repo's cwd, verify hooks fire.

### `scripts/resync-dogfood.sh`

Re-sync dogfood repos after upstream changes without full reinstall.

---

## Validation

| Script | Purpose |
|--------|---------|
| `scripts/validate_structure.py` | Plugin directory layout, dogfooding architecture, no duplicates. Also enforces the canonical `"Component counts:"` line in `CLAUDE.md` against live file counts (Issue #1140): blocks if agents/skills/commands/hooks/libraries counts diverge. |
| `scripts/validate_manifest.py` | `install_manifest.json` in sync with source files |
| `scripts/validate_hook_paths.py` | All hook paths in settings.*.json exist on disk |
| `scripts/validate_component_classifications.py` | Component classifications match registry |
| `scripts/validate_test_categorization.py` | Tests in correct tier directory (`unit/`, `property/`, `integration/`, `security/`, `hooks/`, `structural/`, etc.) |
| `scripts/pre-commit-hook-check.sh` | Quick sanity check before committing |
| `scripts/audit_hook_recovery.py` | CI gate (Issue #970): scans `unified_pre_tool.py` for `output_decision("deny", ...)` sites that lack a paired `log_block_with_recovery(` call in the same function. Default mode (WARN-ONLY) prints findings and exits 0. `--strict` flag (or `AUDIT_HOOK_RECOVERY_STRICT=1` env var) exits 1. Ensures deny-emitting hooks leave structured recovery telemetry for users. |
| `scripts/audit_tool_intent_coverage.py` | CI gate (Issue #971): every distinct tool name observed in activity logs over the last N days must have a defined classification in `tool_intent.py`. Flags uncovered tool names so new native tools are never silently misclassified. Usage: `python scripts/audit_tool_intent_coverage.py [--days 7] [--strict] [--print-classifications] [--logs-dir path]`. Exit 0 when all observed tools are covered; exit 1 when uncovered tools found and `--strict` is set. Importable as `audit(logs_dir, days, strict=False)`. |
| `scripts/check_doc_links.py` | Stdlib Markdown link validator (Issue #972). Replaces the `markdown-link-check` Node dependency. Parses `[text](target)` links in all `docs/*.md` files and reports broken internal links (file not found) and anchors that don't match any heading. Exit 0 when all links resolve; exit 1 on any broken link. Invoked by `tests/integration/test_hook_composition_doc_links.py` as a CI gate. **Security (Issue #994)**: path-traversal guard added — links whose resolved path escapes the project root (detected via `_find_project_root()` walking up to `.git` or `pyproject.toml`) are rejected with `"link escapes project root: <target>"` before any `exists()` check, preventing the checker from being used as a filesystem oracle for paths like `../../../../etc/passwd`. |

All validators are invoked automatically by the pre-commit hook. You rarely need to run them manually — only when debugging validation failures.

---

## Hook Telemetry

### `scripts/hook_perf_report.py` — **Hook timing performance report** (Issue #1012)

```bash
python scripts/hook_perf_report.py                         # last day, top 20 by p95
python scripts/hook_perf_report.py --last 6h --json        # JSON output for piping
python scripts/hook_perf_report.py --since 2026-05-07T00:00:00Z
python scripts/hook_perf_report.py --top 5
python scripts/hook_perf_report.py --start-dir baselines/  # read from a baseline dir
```

Reads the daily-rotated timing JSONL at `~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl` (written by `hook_timing.py`) and produces a p50/p95/p99 latency table with allow/block counts and block ratio per hook. Used by `scripts/capture_baseline.py` and `scripts/publish_hook_baseline.py` for aggregation.

### `scripts/capture_baseline.py` — **Baseline capture driver** (Issue #1012)

```bash
python scripts/capture_baseline.py \
    --output baselines/$(date -u +%Y-%m)-<label>.jsonl \
    --runs 5 \
    --verbose
```

Drives synthetic hook invocations (~5 runs × 24 hooks = ~120 rows) and writes the raw JSONL to the given output path. The resulting file is the source of truth for a baseline snapshot; derived summary artifacts are produced by `scripts/publish_hook_baseline.py`. Captured baselines with `row_count < 500` or a timespan under 1h are classified `synthetic-v0` and do NOT satisfy AC1 of issue #1022.

### `scripts/publish_hook_baseline.py` — **Baseline publisher** (Issue #1022)

```bash
# Dry-run: write .summary.json and .summary.md next to the .jsonl.
python scripts/publish_hook_baseline.py \
    --jsonl baselines/2026-05-pre-refactor.jsonl

# Cross-post to GitHub issue #943 (idempotent via sentinel comment).
python scripts/publish_hook_baseline.py \
    --jsonl baselines/2026-05-pre-refactor.jsonl \
    --post --issue 943
```

Reads a baseline JSONL produced by `scripts/capture_baseline.py` and emits two derived artifacts next to it:
- `<stem>.summary.json` — machine-readable aggregated stats with metadata block (`captured_at`, `generated_at`, `git_sha`, `platform`, `schema_version`, `source_jsonl`, `row_count`, `data_kind`).
- `<stem>.summary.md` — human-readable report with Top-5 slowest hooks (by p95), Top-5 most-blocked gates (by block ratio), and a Baseline policy section.

The `data_kind` field distinguishes `synthetic-v0` (row count < 500 OR timespan < 1h) from `real-workday`. Optional `--post --issue N` cross-posts to a GitHub issue idempotently using an embedded sentinel comment `<!-- hook-timing-baseline:<label> -->`; existing comments are updated rather than duplicated. All `gh` calls use list-arg subprocess invocations (`shell=False`, 15-second timeout). Comment bodies are truncated to 60,000 chars (under GitHub's 65,536 limit).

**AC1 deferral**: the committed `2026-05-pre-refactor` baseline is `synthetic-v0` (119 rows) and does not satisfy AC1 of issue #1022. A real-workday capture (≥4h active session) is operational follow-up. See `baselines/README.md` for the full `BASELINE_POLICY`.

### `scripts/hook_block_summary.py` — **Hook block triage**

```bash
python scripts/hook_block_summary.py                       # summary of all blocks
python scripts/hook_block_summary.py --last 7d --top 10   # last 7 days, top 10 hooks
python scripts/hook_block_summary.py --since 2026-04-01 --json  # JSON output
```

Reads `.claude/logs/hook-blocks.jsonl` (unified telemetry from Issue #972) and, for one release cycle, the legacy `.claude/logs/hook-recovery.jsonl` (from Issue #970). Rows are deduplicated by `(timestamp, hook_name, reason)`. Produces per-hook block counts, category breakdowns, and bypass-usage rates — reproducing the empirical numbers from the #942 triage (verified against `tests/regression/fixtures/942_empirical_numbers.json`). Supports `--last <duration>` (e.g., `7d`, `24h`), `--since <ISO date>`, `--top N`, and `--json` flags. (~280 LOC, Issue #972)

---

## Intent Classifier Calibration (Issue #1043)

### `scripts/extract_and_label_intent_corpus.py` — **Corpus extraction + single-judge labeling**

```bash
# Synthetic-fallback (no claude CLI required)
python scripts/extract_and_label_intent_corpus.py \
    --output tests/fixtures/intent_classifier_real_corpus.json \
    --dry-run

# Real labeling from sessions.db only (default — preserves previous behavior)
python scripts/extract_and_label_intent_corpus.py \
    --output tests/fixtures/intent_classifier_real_corpus.json \
    --max-prompts 150

# Subscription auth (claude Max / claude -p) — bypass the fictional dollar cap
# Per-call cost is $0 under subscription, so the $0.50 default cap fires at entry ~83.
# Set --cost-cap-usd 0 to disable the dollar cap; --max-calls 500 remains as the
# real runaway-loop safety net.
python scripts/extract_and_label_intent_corpus.py \
    --output tests/fixtures/intent_classifier_real_corpus.json \
    --max-prompts 150 \
    --cost-cap-usd 0

# Mine mid-conversation prompts from transcript JSONLs (closes class-imbalance gap
# for refactor/remote_ops/security_critical/test/typo classes — Issue #1072)
python scripts/extract_and_label_intent_corpus.py \
    --output tests/fixtures/intent_classifier_real_corpus.json \
    --source transcripts \
    --max-prompts 150 \
    --cost-cap-usd 0

# Union of both sources — recommended for subscription users refreshing their
# own corpus; sqlite wins on cross-source prompt collision (deduped by md5 hash)
python scripts/extract_and_label_intent_corpus.py \
    --output tests/fixtures/intent_classifier_real_corpus.json \
    --source both \
    --max-prompts 300 \
    --cost-cap-usd 0
```

Extracts real user prompts and labels them with a single LLM-as-judge via `claude -p` subprocess invocation (reuses your Claude Code subscription auth — no API keys needed). Falls back to synthetic-fallback when `claude` is not on PATH. Two prompt sources are supported:

- **`sqlite` (default)**: pulls `first_user_prompt` values from `~/.claude/archive/sessions.db` (all projects, last 30 days). Preserves behavior prior to Issue #1072.
- **`transcripts`**: walks `~/.claude/archive/conversations/{YYYY-MM}/*.jsonl` and extracts all user-typed messages (not just session-entry prompts), closing the class-imbalance gap for classes like `refactor`, `remote_ops`, `test`, and `typo` that rarely appear as session-entry prompts.
- **`both`**: union of both sources, deduplicated by md5 hash; sqlite entries win on collision. Recommended for subscription users refreshing their own corpus against actual workflow.

All sources apply PII scrubbing, deduplication, and length filtering before labeling.

**CLI flags** (Issue #1070): `--cost-cap-usd FLOAT` (default `0.50`) — set to `0` to disable the dollar cap when running under subscription auth where per-call cost is `$0`. `--max-calls INT` (default `500`) — the real runaway-loop safety net; set to `0` to disable. Both caps are independent; `would_exceed_cap` returns `True` if either active cap would be exceeded.

**CLI flags** (Issue #1072): `--source {sqlite,transcripts,both}` (default `sqlite`) — selects the prompt extraction source as described above.

Reads `sessions.db` from `~/.claude/archive/` (same source as `scripts/mine_session_logs.py`). Output corpus consumed by `scripts/measure_intent_classifier.py`.

### `scripts/measure_intent_classifier.py` — **Per-class accuracy measurement**

```bash
python scripts/measure_intent_classifier.py \
    --corpus-path tests/fixtures/intent_classifier_real_corpus.json \
    --baseline-output docs/intent_classifier_calibration.json \
    --update-docs
```

Runs the real `IntentClassifier` from `lib/intent_classifier.py` against each entry in the corpus file, computes per-class precision/recall/F1, builds a confusion matrix, and identifies the lowest-F1 underperforming classes. Optionally writes results to `docs/intent_classifier_calibration.json` (baseline for CI regression) and splices a Markdown report into `docs/INTENT-CLASSIFICATION.md` (idempotent, via `<!-- BEGIN: M2 calibration metrics -->` / `<!-- END: ... -->` sentinels).

**Related**: `tests/fixtures/intent_classifier_real_corpus.json` (108 corpus entries), `docs/intent_classifier_calibration.json` (baseline metrics), `tests/regression/test_intent_classifier_corpus.py` (CI gate, gated on `claude` CLI presence via `shutil.which`).

### `scripts/measure_intent_classifier.py --validate-from-telemetry` — Telemetry-driven FN rate (Issue #1077)

```bash
# Default paths
python3 scripts/measure_intent_classifier.py --validate-from-telemetry

# Custom paths
python3 scripts/measure_intent_classifier.py --validate-from-telemetry \
    --telemetry-log .claude/logs/hook-blocks.jsonl \
    --sessions-db ~/.claude/archive/sessions.db \
    --telemetry-output docs/intent_classifier_telemetry_validation.json
```

Reads `mode_skip` rows from hook telemetry, joins against the session archive,
and reports the observed false-negative rate of intent-classifier-driven
session-mode skipping with a Wilson 95% CI. Used as the gating measurement
for flipping `INTENT_CLASSIFIER_ENFORCE` from `false` to `true`. See
`.claude/plans/mode-gating-rollout.md` Phase B and `docs/INTENT-CLASSIFICATION.md`
"Rollout to Enforce Mode" section.

Filters out synthetic `phase-e-test-*` session IDs. Idempotent — same
inputs produce byte-identical output (modulo `_meta.generated_at`).

---

## Benchmarks & Measurement

### `scripts/run_reviewer_benchmark.py` — **Agent accuracy measurement**

```bash
python3 scripts/run_reviewer_benchmark.py
```

Runs the reviewer agent against `tests/benchmarks/reviewer/dataset.json` (146+ labeled diffs). Reports balanced accuracy, FPR, FNR, per-category and per-difficulty breakdown. Output is the ground truth for measuring reviewer-agent changes.

**See**: [EVALUATION.md](EVALUATION.md) for the full measurement surface.

### `scripts/skill-effectiveness-check.sh` — **Skill behavioral delta**

```bash
scripts/skill-effectiveness-check.sh --quick
scripts/skill-effectiveness-check.sh --skill python-standards
```

Measures whether injecting a skill into agent context actually changes output quality. Invoked by the `/skill-eval` command and by STEP 11.5 of the `/implement` pipeline (skill effectiveness gate).

Requires `OPENROUTER_API_KEY`. See [SKILLS.md](SKILLS.md#skill-effectiveness).

### `scripts/measure_agent_tokens.py`

Counts tokens in each agent's system prompt. Used to validate that agent prompts stay within the per-agent token budget (Issue #175 audit).

### `scripts/improve_reviewer.py`

Autoresearch helper — runs reviewer benchmark, modifies `agents/reviewer.md`, re-benchmarks, commits on improvement / reverts on regression. Called by `/autoresearch --target agents/reviewer.md`.

### `scripts/run_mutation_tests.sh`

Mutation testing for core libraries — introduces controlled bugs and verifies tests catch them. Measures test-suite effectiveness, not just coverage percentage.

---

## Mining & Analysis

### `scripts/mine_session_logs.py`

Aggregates `~/.claude/logs/activity/*.jsonl` into patterns — most-run commands, most-hit gates, hook firing frequency, pipeline mode distribution. Used by `continuous-improvement-analyst` and `/improve` for trends analysis.

### `scripts/mine_git_samples.py`

Generates new benchmark samples by mining the project's git history for real bug fixes. Finds commits matching "fix:", extracts the diff, labels it BUG. Paired with clean commits labeled CLEAN for balanced datasets.

### `scripts/measure_output_format_sections.py`

Audits agent output against the expected output-format contract (Evidence Manifest, verdict lines, etc.). Detects prompt-integrity regressions.

### `scripts/build_covers_index.py`

Builds an index of which doc files cover which code paths (via `covers:` frontmatter). Used by doc-master to find stale docs.

---

## Session Inspection

### `scripts/view-last-session.sh`

Prints a summary of the most recent session from `~/.claude/archive/`. Convenience wrapper around the sessions.db query — shows token counts, tool calls, duration, first prompt.

### `scripts/session_tracker.py`

Library helper used by hooks to update session state. Not typically invoked directly.

---

## Hook Management

| Script | Purpose |
|--------|---------|
| `scripts/add_uv_support_to_hooks.py` | One-shot migration: add `uv run --script` shebang to hook files |
| `scripts/update_hooks_for_uv.py` | Update hook files to use uv-managed dependencies |
| `scripts/generate_hook_config.py` | Regenerate settings.json hook registration from sidecar files |

These are migration utilities — run once, check in the result. Not part of regular workflow.

---

## Dev Workflow

### `scripts/test-autonomous-workflow.sh`

End-to-end smoke test — runs `/implement` against a synthetic feature, verifies the full pipeline completes with no bypasses, captures timing and agent invocations. Used as a regression gate before releases.

### `scripts/test-user-install.sh`

Simulates a fresh user install from a clean environment. Validates that `install.sh` produces a working configuration.

### `scripts/setup_mcp_gh.sh`

One-time setup for the GitHub MCP server (if you want gh via MCP rather than CLI).

### `scripts/agent_tracker.py`

Helper invoked by agents to record completion state. Not typically used directly.

---

## Legacy / Migration

Some scripts are one-shot migrations kept for historical reference:

- `scripts/add_fallback_placeholders.py` — added fallback text to test fixtures
- `scripts/bulk_add_skill_versions.py` — backfilled `version:` frontmatter on skill files
- `scripts/fix_versions.sh` — bumped plugin version across files

These aren't part of regular workflow — they may be deleted in future cleanups.

---

## Adding New Scripts

Scripts should:
1. Be idempotent — safe to re-run
2. Use absolute paths (never `cd` implicitly)
3. Exit 0 on success, non-zero on any failure
4. Print progress to stdout, errors to stderr
5. Include a header comment explaining when to run them

If the script fills a recurring need, add an entry to this doc. If it's truly one-shot, delete it after use or move to `scripts/archived/`.

## Related

- [HOOKS.md](HOOKS.md) — automatic scripts that fire on events
- [EVALUATION.md](EVALUATION.md) — where benchmarks and skill-eval fit in the self-improvement loop
- [SESSION-ANALYTICS.md](SESSION-ANALYTICS.md) — the `~/.claude/archive/` data that `mine_session_logs.py` consumes
