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
actionable clusters in the output. Creates `/drain-queue`-compatible GitHub issue batches
for automated processing.

### Safety gates (6 layers)

1. **Max budget** — 1 PR per drain attempt or 5 issues (whichever is smaller)
2. **Severity filter** — only drains LOW severity clusters (MEDIUM+ skipped)
3. **Tag filter** — allows only {tech-debt, test-skip-accumulated, coverage-regression}
4. **Size limit** — auto-drains only clusters with 1–3 issues (4+ requires manual intervention)
5. **Circuit breaker** — halts on 3 failures, 5 skips, or 60s timeout
6. **Push/deploy gate** — skips if not safe to deploy (uncommitted changes, protected files, missing gates)

### Recognized issue tags

- **tech-debt** — general quality issues that accumulate over time
- **test-skip-accumulated** — tests marked with @pytest.mark.skip
- **remediation** — issues from failed STEP 11 remediation cycles
- **security** — issues from security auditor findings
- **performance** — performance-related findings
- **coverage-regression** — test coverage dropped below baseline
- **pre-existing-failure** — failures detected but not caused by current changes
- **doc-drift** — documentation out of sync with implementation

---

## Command Options

Most commands support various flags to control their behavior:

### Common flags

- `--quick` — Fast mode (available for `/create-issue`, `/plan-to-issues`, `/audit`, `/refactor`, `/skill-eval`)
- `--light` — Light pipeline mode (available for `/implement`) 
- `--fix` — Fix mode (available for `/implement`, `/refactor`)
- `--batch` — Batch processing (available for `/implement`)
- `--issues` — Process specific issues (available for `/implement`)
- `--resume` — Resume interrupted batch (available for `/implement`)

### Domain-specific flags

See individual command documentation in `plugins/autonomous-dev/commands/<name>.md` for complete flag reference.

---

## Pipeline Modes

The `/implement` command supports multiple execution modes:

- **Full Pipeline** (default) — Research → Plan → Acceptance Tests → Implement → Review → Security → Docs
- **Light Mode** (`--light`) — Fast pipeline for docs/config: Plan → Implement → Spec-Validator → Docs
- **Fix Mode** (`--fix`) — Minimal pipeline for bug fixes: Align → Test Context → Implement Fix → Review + Docs
- **Batch Mode** (`--batch` or `--issues`) — Process multiple features with auto-worktree management
- **Resume Mode** (`--resume`) — Continue an interrupted batch from checkpoint

---

## Workflow Integration

Commands can be chained for complex workflows:

1. **Planning workflow**: `/align --project` → `/plan` → `/implement`
2. **Maintenance workflow**: `/audit` → `/triage --auto-improvement` → `/drain-queue`
3. **Cleanup workflow**: `/refactor --quick` → `/sweep --tests` → `/implement --fix`
4. **Research workflow**: `/autoresearch --target X --metric Y` → `/create-issue --quick`

---

## See Also

- [ARCHITECTURE-OVERVIEW.md](../../../docs/ARCHITECTURE-OVERVIEW.md) — system architecture
- [PIPELINE-MODES.md](../../../docs/PIPELINE-MODES.md) — detailed pipeline documentation
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) — common issues and solutions