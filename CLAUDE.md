# autonomous-dev

Development harness for Claude Code. Deterministic enforcement, specialist agents, alignment gates — 12 elements of harness engineering.

## Critical Rules

- **NEVER direct-edit without `/implement`**: `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` — these are functional infrastructure. Hook-enforced: `unified_pre_tool.py` blocks Write/Edit to these paths outside the pipeline.
- **Direct editing is only for**: user-facing docs (README.md, CHANGELOG.md, docs/*.md), config (.json/.yaml), typos (1-2 lines).
- **After plan mode approval → use `/implement`**: The plan IS the input to `/implement`, not a license to bypass it.
- **Run `/improve` after `/implement` sessions.** Use `--auto-file` to create GitHub issues.
- **Deploy with `bash scripts/deploy-all.sh`** — never manual `cp -rf`. Script handles local, remote (Mac Studio), validation, and integrity checks.
- **Don't simplify, redesign, or consolidate agents.** The pipeline, hooks, and enforcement are validated over months of real use. The cost is tokens, not complexity. Complexity is the mechanism.

## Maintainer Escape Hatches

When working **on autonomous-dev itself**, the hook stack can occasionally deadlock — a `/implement` run leaves stuck state, the state-deletion guard (#803) blocks cleanup, and the documented env-var bypasses (`PIPELINE_CLEANUP_PHASE=1`, `ENFORCEMENT_LEVEL=off`, `SKIP_AGENT_COMPLETENESS_GATE=1`) don't propagate to hook subprocesses mid-session (Issue #779). Two file-based escape hatches work mid-session:

| Marker | Scope | Use when |
|---|---|---|
| `.claude/.bypass` | **Universal** — disables ALL hooks for any session whose cwd is in this directory tree (walks up 30 levels) | Emergency. Disables protections including test/security/docs gates. Remove (`rm .claude/.bypass`) as soon as the immediate blocker is past. |
| Self-maintenance mode (auto) | **Targeted** — relaxes only state-deletion (#803) when cwd is inside the canonical autonomous-dev source (detected by `plugins/autonomous-dev/.claude-plugin/marketplace.json`) | Automatic. No action needed. Maintainers can clean up stuck pipeline state with normal `rm /tmp/implement_pipeline_state.json` without env-var bypasses. Other gates (test, security, doc-master, prompt-integrity, workflow-enforcement) remain enforced — dogfooding is preserved. |

The two are complementary: self-maintenance mode is the routine path; `.claude/.bypass` is the nuclear option. If you reach for `.claude/.bypass` more than once in a blue moon, file an issue — the targeted relaxation should grow to cover the case instead.

## Build & Test

Testing uses the **Diamond Model** (not traditional TDD pyramid). Acceptance criteria drive testing; unit tests are regression locks, not specifications. See [docs/TESTING-STRATEGY.md](docs/TESTING-STRATEGY.md).

```bash
# Run full deterministic suite (unit + integration + regression + security + property)
pytest --tb=short -q

# Run specific test file
pytest tests/unit/hooks/test_native_tool_auto_approval.py -v

# Run by layer
pytest tests/unit/                    # Layer 2: Unit tests (regression locks)
pytest tests/property/                # Layer 3: Property-based invariants (Hypothesis)
pytest tests/integration/             # Layer 4: Integration & contract tests
pytest tests/regression/smoke/        # Fast critical-path smoke tests
pytest tests/security/                # Security-specific tests

# GenAI tests (LLM-as-judge, probabilistic — not in default runs)
pytest tests/genai/ --genai           # Layer 5: Semantic validation (~$0.02/run)
pytest tests/genai/ --genai --strict-genai  # Strict mode (no soft failures)

# Property tests with CI thoroughness
HYPOTHESIS_PROFILE=ci pytest tests/property/  # 200 examples per test (vs 50 default)

# Coverage
pytest --cov=plugins/autonomous-dev/hooks --cov=plugins/autonomous-dev/lib --cov-report=term-missing
```

**Test directories → Diamond layers**: `tests/unit/` (L2), `tests/property/` (L3), `tests/integration/` + `tests/regression/` (L4), `tests/genai/` (L5), `tests/spec_validation/` (L5/L6).

## Architecture

- **Pipeline**: 8-step SDLC (15 internal steps) — alignment → research → plan → acceptance tests → implement → validate → verify → git
- **Enforcement**: 24 hooks with JSON `{"decision": "block"}` hard gates (not prompt-level nudges)
- **Agents**: 15 specialists with fresh context per invocation, model-tiered (Haiku/Sonnet/Opus)
- **Skills**: 19 domain packages, progressively injected per-step to prevent context bloat

Component counts: 16 agents, 19 skills, 23 commands, 30 hooks, 220 libraries.

## Commands

`/plan` | `/implement` (full, --light, --batch, --issues, --resume, --fix) | `/create-issue` (--quick) | `/plan-to-issues` (--quick) | `/align` (--project, --docs, --retrofit) | `/audit` (--quick, --security, --docs, --code, --tests) | `/setup` | `/sync` (--github, --env, --all, --uninstall) | `/health-check` | `/advise` | `/worktree` (--list, --status, --merge, --discard) | `/scaffold-genai-uat` | `/status` | `/refactor` (--tests, --docs, --docs-redundancy, --code, --fix, --quick) | `/sweep` | `/improve` (--auto-file) | `/retrospective` | `/mem-search` | `/skill-eval` (--quick, --skill, --update) | `/autoresearch` (--target, --metric, --iterations, --min-improvement, --dry-run) | `/triage` (--auto-improvement, --repo, --limit, --include-fp-acknowledged, --json)

## Key Paths

| What | Where |
|------|-------|
| Alignment source of truth | [.claude/PROJECT.md](.claude/PROJECT.md) |
| Pipeline command | `plugins/autonomous-dev/commands/implement.md` |
| State machine | `plugins/autonomous-dev/lib/pipeline_state.py` |
| Hook enforcement | `plugins/autonomous-dev/hooks/unified_pre_tool.py` |
| Agent definitions | `plugins/autonomous-dev/agents/` |
| Test suite | `tests/` (unit, integration, regression, security, hooks, genai) |
| Activity logs | `.claude/logs/activity/` |
| Architecture details | [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md) |
| Troubleshooting | [plugins/autonomous-dev/docs/TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) |

## Periodic Maintenance

These tasks aren't part of the per-commit workflow — they're run on a maintainer cadence (roughly monthly) to keep load-bearing infrastructure calibrated. Per-event automations have periodic-aggregation counterparts; this is where the periodic side lives.

| Task | Command | When to run |
|------|---------|-------------|
| Refresh intent classifier calibration corpus | `python3 scripts/extract_and_label_intent_corpus.py --source both --cost-cap-usd 0 --max-prompts 200 --output tests/fixtures/intent_classifier_real_corpus.json` | Monthly, or when classifier behavior feels off. Uses your `claude` CLI subscription auth. See [docs/INTENT-CLASSIFICATION.md](docs/INTENT-CLASSIFICATION.md) and [docs/SCRIPTS.md](docs/SCRIPTS.md). |
| Sweep narrative docs for drift | `/refactor --docs` | Monthly, or after multiple feature batches land. doc-master in `/implement` only checks docs covering changed files; narrative docs (README, ARCHITECTURE-OVERVIEW, HARNESS-EVOLUTION) need a periodic full-state pass. For the prior redundancy behavior, use `--docs-redundancy`. |
| Triage CIA-filed auto-improvement issues | `/triage --auto-improvement` | Weekly. CIA files per-session findings; this command groups them by root cause, sequences dependencies, drops noise, and emits a ranked work queue. Idempotent on a clean queue. See [PROJECT.md Layer 4](.claude/PROJECT.md). |

## Session Continuity

`SessionStart-batch-recovery.sh` auto-restores batch state after `/clear` or auto-compact. Activity logged to `.claude/logs/activity/` by `session_activity_logger.py`.

## Session History & Analytics

Every Claude Code session is archived by `conversation_archiver.py` (Stop hook). Full transcripts + SQLite index at `~/.claude/archive/`. See [docs/SESSION-ANALYTICS.md](docs/SESSION-ANALYTICS.md) for full schema and [docs/EVALUATION.md](docs/EVALUATION.md) for how this feeds the self-improvement loop.

**Locations:**
| What | Where |
|------|-------|
| SQLite index (17-column summary per session) | `~/.claude/archive/sessions.db` |
| Full raw transcripts (per-turn, every prompt/response/tool call) | `~/.claude/archive/conversations/{YYYY-MM}/{session_id}.jsonl` |
| JSONL index (dedup'd session metadata) | `~/.claude/archive/index.jsonl` |

**Schema columns:** `session_id, project, cwd, archive_path, first_seen, last_updated, message_count, user_messages, assistant_messages, tool_calls, total_input_tokens, total_output_tokens, transcript_bytes, model, first_user_prompt, cache_read_tokens, cache_creation_tokens`

**Common queries:**

```bash
# Per-repo totals (sessions, tokens, tool calls)
sqlite3 -header -column ~/.claude/archive/sessions.db \
  "SELECT project, COUNT(*) n, SUM(total_output_tokens) out_tok, SUM(tool_calls) tools
   FROM sessions GROUP BY project ORDER BY out_tok DESC;"

# Recent sessions for a specific repo
sqlite3 -header -column ~/.claude/archive/sessions.db \
  "SELECT substr(session_id,1,8) sid, last_updated, message_count, model, substr(first_user_prompt,1,60) prompt
   FROM sessions WHERE project='autonomous-dev' ORDER BY last_updated DESC LIMIT 10;"

# Biggest sessions by output tokens
sqlite3 -header -column ~/.claude/archive/sessions.db \
  "SELECT project, substr(session_id,1,8) sid, total_output_tokens, tool_calls, substr(first_user_prompt,1,50) prompt
   FROM sessions ORDER BY total_output_tokens DESC LIMIT 10;"

# Cache hit rate (higher cache_read_tokens vs input_tokens = better caching)
sqlite3 -header -column ~/.claude/archive/sessions.db \
  "SELECT project, SUM(total_input_tokens) fresh_in, SUM(cache_read_tokens) cache_read,
          ROUND(100.0 * SUM(cache_read_tokens) / NULLIF(SUM(cache_read_tokens + total_input_tokens), 0), 1) cache_pct
   FROM sessions GROUP BY project ORDER BY cache_read DESC;"

# Find transcript file for a session
sqlite3 ~/.claude/archive/sessions.db \
  "SELECT archive_path FROM sessions WHERE session_id LIKE 'abc12345%';"

# Search every transcript for a past prompt or command
grep -l "search term" ~/.claude/archive/conversations/**/*.jsonl
```

**Note on `project` values:** Derived from `cwd` basename — worktrees and subdirectories (e.g., `spektiv/frontend`) get their own project row rather than rolling into the parent repo.

**Last Updated**: 2026-04-21
