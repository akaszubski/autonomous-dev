# autonomous-dev

Development harness for Claude Code. Deterministic enforcement, specialist agents, alignment gates — 12 elements of harness engineering.

For purpose, scope, and architecture see [`.claude/PROJECT.md`](.claude/PROJECT.md). For operational sequences (build, test, deploy, periodic maintenance) see [`docs/RUNBOOK.md`](docs/RUNBOOK.md). For where content lives (the content allocation pattern dogfooded here) see [`docs/development/CONTENT_ALLOCATION.md`](docs/development/CONTENT_ALLOCATION.md).

## Critical Rules

- **NEVER direct-edit without `/implement`**: `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` — these are functional infrastructure. Hook-enforced: `unified_pre_tool.py` blocks Write/Edit to these paths outside the pipeline.
- **Direct editing is only for**: user-facing docs (README.md, CHANGELOG.md, docs/*.md), editor/lint config files that do NOT drive deployment or enforcement (.editorconfig, pyproject.toml lint sections, .gitignore), and typos (1–2 lines). Deployment manifests (install_manifest.json), policy files (auto_approve_policy.json, hard_floor_hooks.json, sandbox_policy.json), and settings templates (templates/settings.*.json) require `/implement`.
- **After plan mode approval → use `/implement`**: The plan IS the input to `/implement`, not a license to bypass it.
- **Run `/improve` after `/implement` sessions.** Use `--auto-file` to create GitHub issues.
- **Deploy with `bash scripts/deploy-all.sh`** — never manual `cp -rf`. Script handles local, remote (Mac Studio), validation, and integrity checks.
- **Don't simplify, redesign, or consolidate agents.** The pipeline, hooks, and enforcement are validated over months of real use. The cost is tokens, not complexity. Complexity is the mechanism.

## Maintainer Escape Hatches

When working **on autonomous-dev itself**, the hook stack can occasionally deadlock — a `/implement` run leaves stuck state, the state-deletion guard (#803) blocks cleanup, and the documented env-var bypasses (`PIPELINE_CLEANUP_PHASE=1`, `ENFORCEMENT_LEVEL=off`, `SKIP_AGENT_COMPLETENESS_GATE=1`) don't propagate to hook subprocesses mid-session (Issue #779). Two file-based mechanisms work mid-session:

| Marker | Scope | Use when |
|---|---|---|
| `.claude/.bypass` | **Universal** — disables ALL hooks for any session whose cwd is in this directory tree (walks up 30 levels) | (1) **Emergency**: disables ALL protections including test/security/docs gates. Remove (`rm .claude/.bypass`) as soon as the immediate blocker is past. (2) **Durable per-repo opt-out**: consumer repos that do not want autonomous-dev SDLC enforcement can commit `.claude/.bypass` permanently — this is the supported way to opt out of the default-on production-code Write/Edit gate (Phase 1, Issue #1142+). |
| Self-maintenance mode (auto) | **Targeted** — relaxes only state-deletion (#803) when cwd is inside the canonical autonomous-dev source (detected by `plugins/autonomous-dev/.claude-plugin/marketplace.json`) | Automatic. No action needed. Other gates (test, security, doc-master, prompt-integrity, workflow-enforcement) remain enforced — dogfooding is preserved. |
| `SKIP_AGENT_COMPLETENESS_GATE` (Issue #1040) | **Narrow** — bypasses only the agent-completeness gate at `git commit` time (Issues #802, #853) when required pipeline agents (`reviewer`, `security-auditor`, `doc-master`, `continuous-improvement-analyst`) have not all completed. Three forms, in reliability order: (1) `touch /tmp/skip_agent_completeness_gate` as a SEPARATE Bash command first, then retry — file-based one-shot, consumed on first check, works mid-session; (2) `SKIP_AGENT_COMPLETENESS_GATE=1 git commit ...` inline command-string prefix — the hook parses the Bash command string for the env-var prefix (case-insensitive); (3) `export SKIP_AGENT_COMPLETENESS_GATE=1` BEFORE launching claude (env vars do NOT propagate mid-session — the hook runs in a separate process; Issue #779). | Emergencies only — for example, hotfixes outside the normal pipeline flow (CI workflow tweaks, README fixes, urgent production patches). Each bypass is logged to `.claude/logs/activity/<date>.jsonl` with a specific `bypass: ...` reason string (file, inline, env), so auditors can distinguish legitimate skips from gaming. The preferred path for legitimate skips is `record_agent_completion()` for the absent agents (satisfies the gate without bypass). If you find yourself reaching for this bypass more than a couple of times per cycle, file an issue — the gate is mis-scoped. |

Self-maintenance mode is the routine path for autonomous-dev itself; `.claude/.bypass` is the universal escape hatch (emergency kill, or durable per-repo opt-out). The Phase 1 polarity flip (Issue #1142+) replaced the previous `.claude/.enforce` opt-IN marker with default-ON enforcement subject to `.claude/.bypass` opt-out. If you reach for `.claude/.bypass` as an *emergency* more than once in a blue moon, file an issue — targeted relaxation should grow to cover the case instead.

## Architecture

- **Pipeline**: 8-step SDLC (15 internal steps) — alignment → research → plan → acceptance tests → implement → validate → verify → git
- **Enforcement**: 25 hooks with JSON `{"decision": "block"}` hard gates (not prompt-level nudges)
- **Agents**: 16 specialists with fresh context per invocation, model-tiered (Haiku/Sonnet/Opus)
- **Skills**: 20 domain packages, progressively injected per-step to prevent context bloat

Component counts: 16 agents, 20 skills, 24 commands, 25 hooks, 224 libraries. Full diagram and layer breakdown in [`docs/ARCHITECTURE-OVERVIEW.md`](docs/ARCHITECTURE-OVERVIEW.md).

## Commands

`/plan` | `/implement` (full, --light, --batch, --issues, --resume, --fix) | `/create-issue` (--quick) | `/plan-to-issues` (--quick) | `/align` (--project, --docs, --retrofit, --content) | `/audit` (--quick, --security, --docs, --code, --tests) | `/setup` | `/sync` (--github, --env, --all, --uninstall) | `/health-check` | `/advise` | `/worktree` (--list, --status, --merge, --discard) | `/scaffold-genai-uat` | `/status` | `/refactor` (--tests, --docs, --docs-redundancy, --code, --fix, --quick) | `/sweep` | `/improve` (--auto-file) | `/retrospective` | `/mem-search` | `/skill-eval` (--quick, --skill, --update) | `/autoresearch` (--target, --metric, --iterations, --min-improvement, --dry-run) | `/triage` (--auto-improvement, --repo, --limit, --include-fp-acknowledged, --json)

User-facing reference: [`plugins/autonomous-dev/docs/COMMANDS.md`](plugins/autonomous-dev/docs/COMMANDS.md). Source of truth: `plugins/autonomous-dev/commands/<name>.md`.

## Key Paths

| What | Where |
|------|-------|
| Alignment source of truth | [.claude/PROJECT.md](.claude/PROJECT.md) |
| Content allocation rules | [docs/development/CONTENT_ALLOCATION.md](docs/development/CONTENT_ALLOCATION.md) |
| Operational runbook | [docs/RUNBOOK.md](docs/RUNBOOK.md) |
| Pipeline command | `plugins/autonomous-dev/commands/implement.md` |
| State machine | `plugins/autonomous-dev/lib/pipeline_state.py` |
| Hook enforcement | `plugins/autonomous-dev/hooks/unified_pre_tool.py` |
| Agent definitions | `plugins/autonomous-dev/agents/` |
| Test suite | `tests/` (unit, integration, regression, security, hooks, genai) |
| Activity logs | `.claude/logs/activity/` |
| Architecture details | [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md) |
| Troubleshooting | [plugins/autonomous-dev/docs/TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) |

## Session Continuity & History

Session state restored by `SessionStart-batch-recovery.sh` after `/clear` or auto-compact. Activity logged to `.claude/logs/activity/`. Every session is archived by `conversation_archiver.py` to `~/.claude/archive/` — schema and SQL examples live in the global `~/.claude/CLAUDE.md` (cross-repo) and in [`docs/SESSION-ANALYTICS.md`](docs/SESSION-ANALYTICS.md).

**Last Updated**: 2026-05-27
