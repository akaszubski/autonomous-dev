# Command Reference

**22 user-invocable slash commands + 3 internal sub-commands** — source of truth: `plugins/autonomous-dev/commands/<name>.md` frontmatter.

---

## Active Commands

| Command | Description |
|---------|-------------|
| `/advise` | Critical thinking analysis - validates alignment, challenges assumptions, identifies risks |
| `/align` | Unified alignment command (--project, --docs, --retrofit, --content) |
| `/audit` | Comprehensive quality audit - code quality, documentation, coverage, security |
| `/autoresearch` | Autonomous experiment loop — hypothesize, modify, benchmark, commit or revert |
| `/create-issue` | Create GitHub issue with automated research (--quick for fast mode) |
| `/drain-queue` | Autonomous queue drainer — picks top /triage cluster, applies 6 safety gates (budget, severity, tag, size, circuit breaker, push/deploy) plus 3-layer durability enforcement (STEP 3.6 drain-pending marker + hook-level `Closes #N` commit gate + STEP 12.5 post-push `state=CLOSED` verification), drains via /implement --issues, then pushes and deploys; one invocation = one drain attempt. **Note**: Phase A of [ADR-002](../../../docs/ADR-002-drain-queue-redesign.md) is COMPLETE (severity classifier fixed, watchdog self-loop eliminated). Phase B is IN PROGRESS — workflows currently bypass /drain-queue (issues #1274, #1276). |
| `/health-check` | Validate all plugin components are working correctly (agents, hooks, commands) |
| `/implement` | Smart code implementation with full pipeline and batch modes |
| `/improve` | Analyze recent sessions for improvement opportunities |
| `/mem-search` | Search past observations and context from claude-mem persistent memory |
| `/plan` | Create a validated planning document with adversarial critique before implementation |
| `/plan-to-issues` | Batch-convert plan mode output into GitHub issues (--quick for fast mode) |
| `/refactor` | Unified code, docs, and test optimization -- shape analysis, waste detection, dead code, doc redundancy |
| `/retrospective` | Analyze recent sessions to detect intent evolution, drift, and propose alignment updates |
| `/scaffold-genai-uat` | Scaffold GenAI UAT tests (LLM-as-judge) into the current repo |
| `/setup` | Interactive setup wizard - analyzes tech stack, generates PROJECT.md, configures hooks |
| `/skill-eval` | Measure skill effectiveness — behavioral delta from skill injection |
| `/status` | View PROJECT.md goal progress with GenAI analysis and strategic recommendations |
| `/sweep` | Codebase hygiene sweep — /refactor --quick alias, or --tests for test pruning analysis |
| `/sync` | Sync plugin files (--github default, --env, --marketplace, --plugin-dev, --all, --uninstall) |
| `/triage` | Periodic-aggregation root-cause triage of the open auto-improvement queue |
| `/worktree` | Manage git worktrees (--list default, --status, --review, --merge, --discard) |

---

## Internal Sub-Commands

The following command files exist but are not directly invoked by users — they are dispatched by `/implement`:

- `/implement-batch` — batch processing mode (see `/implement --batch <file>` or `/implement --issues N,M,...`)
- `/implement-fix` — minimal fix pipeline (see `/implement --fix`)
- `/implement-resume` — resume an interrupted batch (see `/implement --resume <id>`)

---

## /triage --auto-improvement

Periodic-aggregation root-cause triage of the open auto-improvement queue. Clusters open
issues by bracket tag (primary) and by Jaccard token similarity within a tag (secondary),
ranks clusters by `cluster_size * severity_weight * recency_decay`, and surfaces
cross-cluster dependencies (clusters sharing a referenced file path).

**Usage**

```bash
# Default human-readable report.
/triage --auto-improvement

# Custom repo and limit.
/triage --auto-improvement --repo owner/repo --limit 100

# Include fp-acknowledged issues (filtered out by default).
/triage --auto-improvement --include-fp-acknowledged

# Machine-readable JSON output.
/triage --auto-improvement --json
```

**Idempotence**

On unchanged queue contents `/triage` produces byte-identical output across runs (rank
score DESC, then root cause tag ASC, then sub-cluster ID ASC, then issue numbers ASC
within each cluster). The only time-varying input is `now` (used for recency decay).

**When to run**

Weekly, or after a CIA-heavy session that filed many `auto-improvement` issues. The
output is a work queue, not a destructive action.

---

## Related Documentation

- [PROJECT.md](../../../.claude/PROJECT.md) — Project goals, scope, constraints
- [CLAUDE.md](../../../CLAUDE.md) — Project workflow rules
