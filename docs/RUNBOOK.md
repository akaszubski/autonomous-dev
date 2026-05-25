# Runbook — autonomous-dev

Operational sequences for maintainers. Not loaded into context; consulted on demand.

For behaviour rules see [`CLAUDE.md`](../CLAUDE.md). For purpose, scope, and architecture see [`.claude/PROJECT.md`](../.claude/PROJECT.md). For content placement rules see [`docs/development/CONTENT_ALLOCATION.md`](development/CONTENT_ALLOCATION.md).

---

## Build & Test

Testing uses the **Diamond Model** (not traditional TDD pyramid). Acceptance criteria drive testing; unit tests are regression locks, not specifications. See [docs/TESTING-STRATEGY.md](TESTING-STRATEGY.md).

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

## Periodic Maintenance

These tasks aren't part of the per-commit workflow — they're run on a maintainer cadence (roughly monthly) to keep load-bearing infrastructure calibrated. Per-event automations have periodic-aggregation counterparts; this is where the periodic side lives.

| Task | Command | When to run |
|------|---------|-------------|
| Refresh intent classifier calibration corpus | `python3 scripts/extract_and_label_intent_corpus.py --source both --cost-cap-usd 0 --max-prompts 200 --output tests/fixtures/intent_classifier_real_corpus.json` | Monthly, or when classifier behavior feels off. Uses your `claude` CLI subscription auth. See [docs/INTENT-CLASSIFICATION.md](INTENT-CLASSIFICATION.md) and [docs/SCRIPTS.md](SCRIPTS.md). |
| Sweep narrative docs for drift | `/refactor --docs` | Monthly, or after multiple feature batches land. doc-master in `/implement` only checks docs covering changed files; narrative docs (README, ARCHITECTURE-OVERVIEW, HARNESS-EVOLUTION) need a periodic full-state pass. For the prior redundancy behavior, use `--docs-redundancy`. |
| Triage CIA-filed auto-improvement issues | `/triage --auto-improvement` | Weekly. CIA files per-session findings; this command groups them by root cause, sequences dependencies, drops noise, and emits a ranked work queue. Idempotent on a clean queue. |
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

This is the architectural layer that catches drift no per-event hook can see — by design, per-event automations have a single-commit blast radius. Periodic passes are additive: they do not replace or modify per-event hooks. Implementations land incrementally — pick one, generalize the pattern, then port to the other variants.

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
