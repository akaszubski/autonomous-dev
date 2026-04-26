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
```

Deploys the plugin to all configured targets: local machine + all dogfooding repos + Mac Studio via SSH. Auto-detects Mac Studio reachability (LAN `10.55.0.2` with 3s probe; falls back to Tailscale `100.103.205.63`). Idempotent — safe to re-run. Performs per-target validation (hooks parse, match source SHA, all registered). Exits non-zero if any target fails validation.

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
| `scripts/validate_structure.py` | Plugin directory layout, dogfooding architecture, no duplicates |
| `scripts/validate_manifest.py` | `install_manifest.json` in sync with source files |
| `scripts/validate_hook_paths.py` | All hook paths in settings.*.json exist on disk |
| `scripts/validate_component_classifications.py` | Component classifications match registry |
| `scripts/validate_test_categorization.py` | Tests in correct tier directory (`unit/`, `property/`, `integration/`, etc.) |
| `scripts/pre-commit-hook-check.sh` | Quick sanity check before committing |
| `scripts/audit_hook_recovery.py` | CI gate (Issue #970): scans `unified_pre_tool.py` for `output_decision("deny", ...)` sites that lack a paired `log_block_with_recovery(` call in the same function. Default mode (WARN-ONLY) prints findings and exits 0. `--strict` flag (or `AUDIT_HOOK_RECOVERY_STRICT=1` env var) exits 1. Ensures deny-emitting hooks leave structured recovery telemetry for users. |
| `scripts/audit_tool_intent_coverage.py` | CI gate (Issue #971): every distinct tool name observed in activity logs over the last N days must have a defined classification in `tool_intent.py`. Flags uncovered tool names so new native tools are never silently misclassified. Usage: `python scripts/audit_tool_intent_coverage.py [--days 7] [--strict] [--print-classifications] [--logs-dir path]`. Exit 0 when all observed tools are covered; exit 1 when uncovered tools found and `--strict` is set. Importable as `audit(logs_dir, days, strict=False)`. |

All validators are invoked automatically by the pre-commit hook. You rarely need to run them manually — only when debugging validation failures.

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
