# autonomous-dev

Development harness for Claude Code. Deterministic enforcement, specialist agents, alignment gates — 12 elements of harness engineering.

## Critical Rules

- **NEVER direct-edit without `/implement`**: `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` — these are functional infrastructure. Hook-enforced: `unified_pre_tool.py` blocks Write/Edit to these paths outside the pipeline.
- **Direct editing is only for**: user-facing docs (README.md, CHANGELOG.md, docs/*.md), config (.json/.yaml), typos (1-2 lines).
- **After plan mode approval → use `/implement`**: The plan IS the input to `/implement`, not a license to bypass it.
- **Run `/improve` after `/implement` sessions.** Use `--auto-file` to create GitHub issues.
- **Use `/clear` after each feature.** Prevents context bloat.
- **Deploy with `bash scripts/deploy-all.sh`** — never manual `cp -rf`. Script handles local, remote (Mac Studio), validation, and integrity checks.
- **Process applies WHEN doing software development.** The pipeline, hooks, and enforcement exist to ensure thoroughness on real feature work for repos. They should NOT fire on testing, exploration, scratch edits, or non-repo work. The job is to detect *when* software development is happening and apply the right level of process — not to gate every edit. Context-blind enforcement is the bug; intent-aware enforcement is the goal.
- **Hook deadlock protocol**: If a hook blocks legitimate work, surface the block to the user with the proposed bypass and *wait for approval*. Do NOT autonomously create `.claude/.bypass` or set `AUTONOMOUS_DEV_BYPASS=1` — those signals exist for the user to authorize, not for the model to invoke. See [plugins/autonomous-dev/docs/TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) for bypass mechanics.
- **Plugin source of truth**: `~/Dev/autonomous-dev/plugins/autonomous-dev/` is canonical. Consumer repos (anyclaude, realign, spektiv, homeassistant) receive *copies* via `bash scripts/deploy-all.sh` — never symlinks. A symlink found by `find ~/Dev -maxdepth 4 -name plugins -type l` is a silent cross-repo write trap (Issue #1021); replace with a `deploy-all.sh` copy. See [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md#distribution-model).

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

Component counts: 16 agents, 19 skills, 23 commands, 30 hooks, 210 libraries.

## Commands

`/plan` | `/implement` (full, --light, --batch, --issues, --resume, --fix) | `/create-issue` (--quick) | `/plan-to-issues` (--quick) | `/align` (--project, --docs, --retrofit) | `/audit` (--quick, --security, --docs, --code, --tests) | `/setup` | `/sync` (--github, --env, --all, --uninstall) | `/health-check` | `/advise` | `/worktree` (--list, --status, --merge, --discard) | `/scaffold-genai-uat` | `/status` | `/refactor` (--tests, --docs, --code, --fix, --quick) | `/sweep` | `/improve` (--auto-file) | `/retrospective` | `/mem-search` | `/skill-eval` (--quick, --skill, --update) | `/autoresearch` (--target, --metric, --iterations, --min-improvement, --dry-run)

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
## Documentation Alignment

CLAUDE.md alignment system prevents documentation drift. Automatic validation that CLAUDE.md stays in sync with PROJECT.md and codebase.

**How to check**:
```bash
# Automatic (every commit)
git commit  # Pre-commit hook validates CLAUDE.md alignment

# Manual check
python plugins/autonomous-dev/scripts/validate_claude_alignment.py
```

**What gets validated**:
- Version dates (CLAUDE.md shouldn't be older than PROJECT.md)
- Agent counts (documented count matches reality)
- Command availability (documented commands exist)
- Skills status (removed per v2.5.0 guidance)
- Hook documentation (matches implemented hooks)

**If drift detected**:
1. Run validation script to see specific issues
2. Update CLAUDE.md to match actual state
3. Commit the fix
4. Pre-commit hook validates on next commit

## Maintaining Core Philosophy

**The Golden Rule**: UPDATE PROJECT.md FIRST, everything else follows
- PROJECT.md = source of truth for alignment
- orchestrator reads it before any feature work
- Hooks validate against it on every commit

**Priority Updates**:
1. 🔴 ALWAYS: PROJECT.md, orchestrator.md, settings.local.json
2. 🟡 FREQUENTLY: Agent prompts, GenAI prompts, skills
3. 🟢 PERIODICALLY: Documentation, session logs, hooks

**Philosophy Checklist** (before major changes):
- ✅ Trust the model? (GenAI reasoning > rigid Python)
- ✅ Enforce via hooks? (100% reliable blocking)
- ✅ Enhance via agents? (conditional intelligence)
- ✅ PROJECT.md controls alignment? (dynamic scope)
- ✅ Skills used progressively? (no context bloat)
- ✅ Documentation auto-syncs? (no drift)

See `docs/MAINTAINING-PHILOSOPHY.md` for comprehensive guide.
