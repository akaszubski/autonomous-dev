---
covers:
  - plugins/autonomous-dev/hooks/
  - plugins/autonomous-dev/lib/hook_exit_codes.py
---

# Automation Hooks Reference

**Last Updated**: 2026-03-17
**Location**: `plugins/autonomous-dev/hooks/`

See [CLAUDE.md](../CLAUDE.md) for current counts. See [HOOK-REGISTRY.md](HOOK-REGISTRY.md) for environment variables and activation status.

---

## Overview

Hooks provide automated quality enforcement, validation, and workflow automation. They use standard `python3` shebangs and are designed to degrade gracefully — a hook crash never blocks Claude Code (see [Safe Failure Behavior](#safe-failure-behavior) below).

**Architecture**: Unified dispatcher pattern — consolidated hooks replace individual ones for reduced collision and easier maintenance.

---

## Exit Code Semantics

| Code | Constant | Meaning | Workflow Effect |
|------|----------|---------|-----------------|
| **0** | EXIT_SUCCESS | Passed | Continue normally |
| **1** | EXIT_WARNING | Non-critical issue | Continue with warning |
| **2** | EXIT_BLOCK | Critical issue | Block operation (PreCommit/PreSubagent only) |

**Lifecycle constraints**: PreToolUse, SubagentStop, Stop, and TaskCompleted hooks must always exit 0. Only PreCommit and PreSubagent hooks can block.

**Library**: `plugins/autonomous-dev/lib/hook_exit_codes.py` — see [LIBRARIES.md](LIBRARIES.md) for API.

---

## Active Hooks by Lifecycle

### UserPromptSubmit

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **unified_prompt_validator.py** | Compaction recovery re-injection (batch and pipeline state) + workflow bypass detection + quality nudges. On each prompt, checks for `.claude/compaction_recovery.json` and if present re-injects saved batch/pipeline context to stderr, then deletes the marker. Pipeline recovery validates staleness and cwd before injecting. **Plan-mode-exit enforcement was moved to PreToolUse (`unified_pre_tool.py`) per Issue #926** — UserPromptSubmit cannot observe in-turn model tool calls (e.g., `gh issue create`, `Task(implementer)`), so the gate was structurally in the wrong place. The marker file format and writer (`plan_mode_exit_detector.py`) are unchanged. | ENFORCE_WORKFLOW, QUALITY_NUDGE_ENABLED |
| **session_activity_logger.py** | Captures user prompt preview + length into session JSONL log. Pins session start date. Non-blocking. | ACTIVITY_LOGGING |

### PreToolUse

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **unified_pre_tool.py** | Native tool fast path + 4-layer permission validation (sandbox → MCP security → agent auth → batch approval) + pipeline ordering gate + hook extensions. 84% reduction in permission prompts. Blocks git bypass flags (--no-verify, --force push, reset --hard, clean -f). Blocks direct Write/Edit to infrastructure files (`agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md`) outside `/implement` pipeline — scoped to autonomous-dev repos only. Also inspects Bash command bodies for shell file-write patterns (sed -i, cp/mv, redirects, tee, python3 -c writes, cat heredoc `cat > file << EOF`, `dd of=FILE`, `Path.write_text/write_bytes` in python3 -c, python3 heredoc with open()/Path.write_text inside) to the same protected paths, closing the bypass gap where wrapping a write in Bash would evade the gate (Issue #558). Python snippet analysis (python3 -c and heredoc bodies) is backed by `python_write_detector.py` (Issue #589) using AST-based extraction with regex fallback; handles aliased `Path` imports, `shutil.copy/move` destination arguments, and `eval()`/`exec()` with dynamic arguments. Deny cache at `/tmp/.claude_deny_cache.jsonl` tracks repeated bypass attempts within a 60-second window and escalates the block message on second attempt (Issue #558). Detects inline env var spoofing in Bash commands (e.g. `VAR=value cmd` or `export VAR=value`) for protected pipeline variables. Individual variables protected by exact match: CLAUDE_AGENT_NAME, CLAUDE_AGENT_ROLE, PIPELINE_STATE_FILE, ENFORCEMENT_LEVEL, CLAUDE_SESSION_ID. Additionally, any variable whose name starts with the `CLAUDE_` prefix is blocked by prefix-based protection (Issue #606, `PROTECTED_ENV_PREFIXES`), preventing new CLAUDE_* variables from being spoofed without requiring explicit listing. A session-scoped escalation tracker (`_track_spoofing_escalation()`) persists attempt counts to `~/.claude/logs/spoofing_attempts.json` across hook invocations; repeated spoofing attempts within the same session produce an escalated block message — blocks attempts to forge agent identity or downgrade enforcement level. Blocks Write/Edit to `settings.json` and `settings.local.json` during active `/implement` pipeline sessions. Also blocks Bash `python3 -c` / `python -c` commands that contain both a settings file reference (`settings.json` or `settings.local.json`) AND a Python write pattern (`open(`, `json.dump(`, `.write(`, `.write_text(`, `shutil.`, `os.rename(`, `os.replace(`), closing the bypass where variable indirection (`p = 'settings.json'; json.dump(d, open(p,'w'))`) would evade the file-tool gate (Issue #768). Verifies HMAC integrity of pipeline state files to detect tampering. (Issue #557) Alignment gate: when `/implement` is active, blocks coordinator Write/Edit/Bash to code files until STEP 2 (PROJECT.md alignment) has completed — `alignment_passed: true` must be set in the pipeline state before any code changes are permitted; fails closed on HMAC failure or missing state. `alignment_passed` field included in the HMAC message to prevent tampering. (Issue #585) Blocks direct `gh issue create` in Bash outside the `/implement` pipeline, authorized issue-creation agents (`continuous-improvement-analyst`, `issue-creator`), or commands that write a command context file at `/tmp/autonomous_dev_cmd_context.json` (Issue #599, #630). Realign CLI enforcement (Issue #754): in projects detected as realign repos (contain `src/realign/` or `pyproject.toml` with "realign" string), blocks Bash commands that directly invoke `python -m mlx_lm.lora`, `python -m mlx_lm.generate`, `python -m mlx_lm.fuse`, or `python -m mlx.launch`; grep/search/cat references to mlx_lm are allowed. Block message directs the user to use `realign train` or `realign generate` instead. Fails open on project-detection errors. Agent completeness gate (Issues #802, #853): blocks `git commit` when required pipeline agents have not all completed. In batch mode (detected by `.worktrees/batch-` in cwd), iterates ALL issues in the state file and calls `verify_pipeline_agent_completions()` per issue, respecting each issue's `research_skipped` flag; produces a per-issue failure list (`#N: missing agent1, agent2`). In non-batch mode, calls `_check_pipeline_agent_completions()` for the single active issue. Both paths read state via `pipeline_completion_state.py`; bypass via `SKIP_AGENT_COMPLETENESS_GATE=1` or `touch /tmp/skip_agent_completeness_gate` (file-based one-shot bypass — the env var is unreachable from Bash because the hook runs in a separate process; the file is consumed on first check; Issue #802) or inline command prefix `SKIP_AGENT_COMPLETENESS_GATE=1 git commit ...` (the hook parses the Bash command string for the env var prefix, so prefixing the commit command directly also works; `skip_agent_completeness_gate=true` is accepted case-insensitively for the `=true` variant); fails open on state errors. Batch CIA completion gate (Issue #712): blocks `git commit` in batch worktrees when any batch issue is missing `continuous-improvement-analyst` completion; delegates to `verify_batch_cia_completions()` in `pipeline_completion_state.py`; bypass via `SKIP_BATCH_CIA_GATE=1`; fails open on state errors. Batch doc-master completion gate (Issues #786, #837): blocks `git commit` in batch worktrees when any batch issue is missing `doc-master` completion OR when doc-master ran but produced no valid verdict (MISSING/SHALLOW); delegates to `verify_batch_doc_master_completions()` in `pipeline_completion_state.py`; block message differentiates "doc-master never ran" from "ran but produced no valid verdict" to aid diagnosis; bypass via `SKIP_BATCH_DOC_MASTER_GATE=1`; fails open on state errors. pytest-gate ordering enforcement (Issue #838): `pytest-gate` is treated as a virtual agent prerequisite — reviewer, security-auditor, and doc-master are blocked until `pytest-gate` is recorded as completed; `reviewer → security-auditor` ordering is now always enforced (no longer relaxed in parallel mode); bypass via `SKIP_PYTEST_GATE=1` (injects `"pytest-gate"` into the completed set before the ordering check runs); fails open on state errors. | SANDBOX_ENABLED, MCP_AUTO_APPROVE, HOOK_EXTENSIONS_ENABLED, PRE_TOOL_PIPELINE_ORDERING, SKIP_PYTEST_GATE

**Hook Output Format and Visibility Semantics** (Issue #660):

The PreToolUse hook outputs a JSON object with two distinct channels that have different visibility:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Model-visible reason; used for REQUIRED NEXT ACTION carrots"
  },
  "systemMessage": "User-visible message injected into conversation (optional)"
}
```

- **`permissionDecisionReason`** (model-visible on deny): Read by the model when a tool call is blocked. Block messages include a `REQUIRED NEXT ACTION:` carrot directive telling the model exactly what to do next (e.g., "Run /implement", "Use /create-issue", "Wait for prerequisite agents"). This is the primary enforcement mechanism — the carrot is a model-readable instruction, not a user-facing message.
- **`systemMessage`** (user-visible): Injected into the conversation context as a system-level message visible to the human user. Used for escalated or user-facing notifications. `systemMessage` is omitted when not needed; its presence is optional.

This distinction is fundamental: nudges in `systemMessage` are user-readable but the model cannot act on them. Enforcement directives in `permissionDecisionReason` are model-readable and drive corrective behavior. See MEMORY.md entry "Critical Behavioral Issue" for why this distinction matters.

**unified_pre_tool.py Native Tool Fast Path** (v4.1.0+):
- Native Claude Code tools (Read, Write, Edit, Bash, Task, etc.) skip the 4-layer MCP validation
- Governed by settings.json permissions instead
- Eliminates unwanted permission prompts for standard tools
- **Exception — Agent/Task tools**: Pipeline ordering gate and prompt integrity gate run before extensions for Agent/Task tool calls (Issues #625, #629, #632, #695, #716). Prompt integrity minimum word count fires regardless of pipeline state; baseline shrinkage check only during active pipeline.
- Hook extensions still run for all native tools (extensions can block any tool)

**Project Detection Guard** (Issue #662 — non-native MCP tools only):
- Runs immediately after the native tool fast path, before the 4-layer enforcement stack
- Calls `repo_detector.is_autonomous_dev_repo()` on the current working directory
- Non-autonomous-dev projects: returns immediate allow, skipping all enforcement layers
- Fail-closed: when `repo_detector` is unavailable at load time, `_is_adev_project()` returns `True` so enforcement continues rather than being silently skipped
- Has no effect in autonomous-dev repos — all enforcement layers run normally

**unified_pre_tool.py 6-Layer Architecture** (for MCP/external tools in autonomous-dev repos):
- **Layer 0 (Sandbox)**: Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
- **Layer 1 (MCP Security)**: Path traversal (CWE-22), injection (CWE-78), SSRF (CWE-918)
- **Layer 2 (Agent Auth)**: Pipeline agent detection, authorized agent verification
- **Layer 3 (Batch Approver)**: User consent caching, audit logging (merged into unified_pre_tool.py per Issue #348)
- **Layer 4 (Extensions)**: Project/user-specific checks from `.claude/hooks/extensions/*.py` and `~/.claude/hooks/extensions/*.py` — survives `/sync` and `/install` (see Extension Points section)
- **Layer 5 (Infrastructure Protection)**: Write/Edit to `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` are blocked outside the `/implement` pipeline (see Infrastructure Protection section)
- **Layer 6 (Prompt Quality)**: Write/Edit to `agents/*.md` or `commands/*.md` during active pipeline sessions are checked against `prompt_quality_rules.py` anti-patterns; blocks banned persona openers, casual register phrases, and oversized constraint sections (Issue #842)

**Pipeline Ordering Gate** (Issues #625, #629, #632, #686 — native Agent/Task tools only):
- Enforces agent invocation order during active pipeline sessions
- Records agent launch in `pipeline_completion_state.py` before checking prerequisites (Issue #686)
- Reads completion and launch state from `pipeline_completion_state.py` (completions written by `unified_session_tracker.py`)
- Delegates ordering logic to `agent_ordering_gate.py` (pure logic, no I/O)
- Blocks out-of-order agent calls (e.g., implementer before planner/test-master)
- Supports sequential mode (default) and parallel mode (`set_validation_mode()`)
- In parallel mode, distinguishes "running concurrently" (launched, not yet complete — allowed with warning) from "skipped entirely" (never launched — blocked)
- Controlled by env var `PRE_TOOL_PIPELINE_ORDERING` (default: `true`)
- Fails open — ordering check errors never block workflow

**Prompt Integrity Gate** (Issues #695, #716, #723, #789, #791, #794 — native Agent/Task tools only):
- Blocks invocations of compression-critical agents (security-auditor, reviewer, doc-master, implementer, planner) when their prompt falls below the minimum word count
- Minimum word count enforcement fires **regardless of pipeline state** (Issue #716 fix) — this gate is always active for critical agents, not just during `/implement` batches
- Baseline shrinkage check (detecting >= 20% compression vs first-issue baseline — Issue #812 tightened from > 25%) fires **whenever a baseline exists** (Issue #723 — no pipeline-active gate); when no baseline exists, the hook seeds one from the **observed word count** of the current prompt at `issue_number=0` (Issue #759 fix — template-based seeding produced ~1700-word baselines that blocked legitimate ~200-400-word task-specific prompts even with a 0.70 slack factor); template-based seeding via `seed_baselines_from_templates()` is reserved for batch-mode pre-seeding at batch start with appropriate slack
- Uses `validate_prompt_integrity()` which imports `COMPRESSION_CRITICAL_AGENTS` and `MIN_CRITICAL_AGENT_PROMPT_WORDS` from `prompt_integrity.py` (minimum: 80 words)
- Shrinkage check calls `validate_prompt_word_count` with `max_shrinkage=0.20` (20% — Issue #812 tightened from 25%; library default is 15%)
- **Reinvocation context detection** (Issues #789, #791): `_detect_invocation_context()` checks the `PIPELINE_INVOCATION_CONTEXT` env var first, then scans prompt text for markers (`"remediation mode"`, `"re-review"`, `"doc-update-retry"`, `"reduced context"`). When a known reinvocation context (`REINVOCATION_CONTEXTS = {"remediation", "re-review", "doc-update-retry"}`) is detected, the shrinkage threshold is doubled (20% → 40%) to accommodate naturally shorter re-invocation prompts; the effective threshold is noted in the block message. Passed as `invocation_context` to `validate_prompt_word_count`.
- **Cumulative drift check** (Issue #794): After each check passes, `record_batch_observation(agent_type, issue_number, word_count)` records the observation to `prompt_batch_observations.json`. `get_cumulative_shrinkage(agent_type)` then computes total drift from the first to latest observation; if drift is `>= MAX_CUMULATIVE_SHRINKAGE` (30% — Issue #870 calibrated from 20% to reduce false positives on normal inter-issue variance; operator is `>=`), the invocation is blocked with a REQUIRED NEXT ACTION directive — this catches progressive 3–5% per-iteration compression that individually passes the 20% per-issue threshold. Wrapped in try/except (fail-open) so cumulative tracking failures never block agents.
- `clear_prompt_baselines()` now also calls `clear_batch_observations()` at batch start so cumulative drift state resets alongside baselines
- Block message directs the coordinator to reconstruct the prompt with full context and use `get_agent_prompt_template()` to reload the agent base prompt from disk
- Fails open: ImportError when `prompt_integrity` module is unavailable, any Exception during the baseline check, and any Exception in the cumulative drift check

**Plan-Exit Gate** (Issue #926 — Layer for native + MCP tools, marker-driven state machine):
- Moved from UserPromptSubmit (`unified_prompt_validator.py`) to PreToolUse here because in-turn model tool calls (e.g., `gh issue create`, `Task(implementer)`) bypass UserPromptSubmit. Marker writer (`plan_mode_exit_detector.py`) and stage advancer (`unified_session_tracker.py`) are unchanged
- Reads `.claude/plan_mode_exit.json` marker on every PreToolUse event; marker auto-deletes when older than 30 minutes; corrupted/timestamp-missing markers also auto-delete
- **stage=plan_exited**: Read/Glob/Grep pass through; `Task(plan-critic)` passes through; Bash on read-only allowlist (`ls`, `cat`, `head`, `tail`, `wc`, `pwd`, `which`, `echo`, `grep`, `rg`, `tree`, `stat`, `file`, `date`, `whoami`, `id`, `uname`; `git status|log|diff|show|branch|blame|ls-files|rev-parse|remote`; `gh issue|pr|repo view|list`, `gh auth status`) passes through. Write/Edit/NotebookEdit, Task with any other subagent, Bash off-allowlist or with injection metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `<`, `>`, `&&`, `||`, `$(`, `<(`, `<<<`, `<<`, `\n`, `\r`) are denied. MCP tools deny unless on the explicit read-only allowlist (`_PLAN_EXIT_MCP_READONLY` — Playwright snapshot/screenshot/console/network, HuggingFace search/fetch, Gmail list/get, Calendar list/get, Drive list/search/read/metadata)
- **stage=critique_done**: `Bash(gh issue create ...)` and `Task(implementer|issue-creator|continuous-improvement-analyst)` are allowed and consume the marker (one-shot); other tools fall through to later validators
- **Race mitigation**: on tentative deny, sleeps 10ms and re-reads the marker; if stage advanced (writer hook fired during the call), allows the tool
- Fails open: any exception during marker read or comparison is treated as no enforcement (never blocks on hook errors)
- Allowlist is explicit (`frozenset`-based), not regex/heuristic — AC #21 prevents false positives like `mcp__foo__find_and_replace` slipping through

**Infrastructure Protection** (scoped to autonomous-dev repos):
- Write/Edit to `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` are blocked outside the `/implement` pipeline
- Scoped to autonomous-dev repos (detected via `_is_autonomous_dev_repo()`) — does not affect user projects
- User-facing docs (`README.md`, `CHANGELOG.md`, `docs/*.md`), config files (`.json`/`.yaml`), and all non-infrastructure paths are unaffected

**Prompt Quality Gate** (Issue #842 — Layer 6, Write/Edit to agents/*.md and commands/*.md only):
- Blocks writes to `agents/*.md` or `commands/*.md` when the resulting content contains prompt anti-patterns detected by `prompt_quality_rules.py`
- Only enforced during active pipeline sessions (`_is_pipeline_active()` must return true); fails open on all errors
- Content check for Write tool: uses `tool_input["content"]` directly
- Content check for Edit tool: reads the existing file from disk, applies the replacement in memory, then runs anti-pattern checks on the post-edit content; if the file cannot be read, the check is skipped (fail-open)
- Anti-patterns checked: (1) banned persona openers (`You are an expert/senior/world-class/renowned/leading/top`) — legitimate role assignments like `You are the **agent** agent` are allowed; (2) casual register phrases (`check for`, `look for`, `make sure`, `try to`, `you should`, `feel free`) that weaken enforcement; (3) oversized constraint sections exceeding 8 bullet items per `##`-level section
- Block message lists the first three violations (plus count of remaining), and includes a `REQUIRED NEXT ACTION` directive to use formal directive language (`MUST`, `REQUIRED`, `FORBIDDEN`) and keep constraint sections under the threshold
- Rule library (`prompt_quality_rules.py`) is loaded via `importlib.util.spec_from_file_location` at check time; if the module file is missing or import fails, the gate is skipped (fail-open)
- Runs as Layer 6 in the Write/Edit enforcement stack, after Infrastructure Protection (Layer 5) and the Agent Denial Fallback Guard

**Agent Denial Fallback Guard** (Issue #750):
- When the Prompt Integrity Gate denies an Agent/Task invocation due to prompt shrinkage, the orchestrator may fall back to direct Write/Edit calls to the same protected infrastructure files
- `_record_agent_denial(agent_type)` writes a session-scoped JSON state file at `AGENT_DENY_STATE_DIR` (`/tmp/adev-agent-deny-{session_id}.json`) immediately after any prompt-integrity denial
- `_check_agent_denial()` is called at the top of every Write/Edit check; if a denial record exists within `AGENT_DENY_TTL` (300 seconds) for the same session, the Write/Edit to a protected infrastructure path is blocked
- Block message includes a `REQUIRED NEXT ACTION` directive telling the orchestrator to reload the agent prompt template via `get_agent_prompt_template()` and retry the Agent call with a full-length prompt
- Non-infrastructure paths (docs, config, test files) are unaffected — the guard only activates for the same `_is_protected_infrastructure()` paths that the base infrastructure gate covers
- Fails open on all state file errors (`_record_agent_denial` swallows exceptions; `_check_agent_denial` returns `None` on any error) to avoid blocking legitimate work

**Cross-Tool Write-to-Bash Workaround Detection** (Issue #803):
- When a Write/Edit to a protected infrastructure file is denied, `_update_deny_cache(file_path)` is now called at both denial sites — the main infrastructure protection block and the Issue #750 agent-denial-workaround block — so the denied path is recorded in the deny cache at `/tmp/.claude_deny_cache.jsonl`
- Subsequent Bash commands that attempt to write the same file (via heredoc, redirect, `tee`, `echo`, or Python `-c` write patterns) within the 60-second deny window are detected by extracting write targets with `_extract_bash_file_writes()` and checking each against `_check_deny_cache()`
- A match within the 60-second window is blocked with a "cross-tool workaround detected" message including a `REQUIRED NEXT ACTION` directive
- `_check_deny_cache(file_path)` now also falls back to basename matching (`Path.name`) when the full path does not match, handling cross-format path references (absolute vs relative)
- Closes the bypass pattern where an agent switches from Write/Edit to a Bash heredoc after an infrastructure protection denial

**Pipeline State File Deletion Guard** (Issue #804):
- Detects `rm`, `unlink`, `truncate`, redirect-to-empty (`> file`), `python os.remove`/`os.unlink`/`Path.unlink` targeting pipeline state files during active pipeline runs
- Protected state file patterns: `/tmp/implement_pipeline_state.json`, `/tmp/.claude_deny_cache.jsonl`, `/tmp/pipeline_completion_state_*.json`, `/tmp/pipeline_secrets/*`
- `_check_bash_state_deletion(command)` is the detection function; `_is_state_file(path)` is the helper that matches a path against the protected patterns
- Before scanning, the function strips heredoc bodies (`<<'EOF'...EOF`, `<<EOF...EOF`, `<<"EOF"...EOF`, `<<-EOF...EOF`) and `--body`/`--message` quoted argument values from the command string to prevent false positives when prose text in commit messages or issue descriptions happens to mention state file paths (Issue #866)
- Deleting state files during an active pipeline would bypass enforcement by clearing the ordering gate state, deny cache, or pipeline secrets — this guard closes that vector
- Fails open: only fires when the pipeline is active (state file present); passes when no pipeline is running
- Escape hatch: `PIPELINE_CLEANUP_PHASE=1` (or `true`) allows state file deletion — used by STEP 15 / STEP B4 coordinator-authorized cleanup after batch completion (Issue #865)

**Spec Test Deletion Scope Guard** (Issue #790):
- Blocks deletion of `tests/spec_validation/test_spec_issue{N}_*.py` files that belong to a different issue than the current pipeline run
- Detection covers: `Write` tool with empty/whitespace content (truncation vector), `rm`, `unlink`, `truncate`, redirect-to-empty (`> file`), `python os.remove`/`os.unlink`/`Path.unlink`, and `mv` to a non-`tests/archived/` destination
- `_check_spec_test_deletion_scope(file_path)` extracts the issue number from the filename, reads `_get_current_issue_number()`, and blocks when the two differ
- `_extract_bash_spec_test_targets(command)` parses Bash command strings to find spec test paths targeted by deletion or move operations
- Escape hatch: `SKIP_SPEC_DELETION_GUARD=1` bypasses the guard for intentional cross-issue cleanup
- Fail-open: when no pipeline context exists (`current_issue == 0`), the guard passes; detection errors never block
- Required next action on block: `mv {file_path} tests/archived/` — spec tests from other issues must be archived, not deleted

**GitHub Issue Creation Gate** (Issue #599):
- Direct `gh issue create` in Bash is blocked outside approved contexts to enforce the `/create-issue` pipeline (research, duplicate detection, proper formatting)
- Allow-through 1: an active `/implement` pipeline is present (`/tmp/implement_pipeline_state.json`)
- Allow-through 2: the current agent is `continuous-improvement-analyst` or `issue-creator` (authorized for direct issue creation)
- Allow-through 3: a fresh marker file exists at `GH_ISSUE_MARKER_PATH` (`/tmp/autonomous_dev_gh_issue_allowed.marker`, valid for 1 hour) — written only by the active `/implement` pipeline (commands no longer write this file; see Issue #627)
- Allow-through 4 (Issue #630, #647, #663): a command context file exists at `GH_ISSUE_COMMAND_CONTEXT_PATH` (`/tmp/autonomous_dev_cmd_context.json`, valid for 1 hour) with a `command` field set to one of `create-issue`, `plan-to-issues`, `improve`, `refactor`, or `retrospective` — the hook auto-writes this file in the `NATIVE_TOOLS` fast path when it detects a `Skill` tool invocation for one of these commands (before any downstream Bash `gh issue create` check fires); uses file mtime for age check (harder to spoof than an embedded JSON timestamp)
- Block message directs the user to `/create-issue` or `/create-issue --quick`; also includes a FORBIDDEN clause explicitly prohibiting suggestions to run `! gh issue create` or any other bypass method (the `!` prefix runs commands outside the hook system)
- Fails open on any detection error to avoid blocking legitimate work

**Marker File Creation Guard** (Issue #627):
- Blocks direct creation of the marker file `autonomous_dev_gh_issue_allowed.marker` outside approved contexts, closing the bypass where manually writing the marker file would short-circuit the gh issue create gate
- Uses deny-by-default logic: if the substring `autonomous_dev_gh_issue_allowed` appears anywhere in the command, the command is blocked unless the operation is provably read-only or a delete — this prevents bypass via novel write methods (e.g. `python3 -c "..."`, `dd`, `install`, `os.open`) that a fixed allowlist would miss
- Allowed (not blocked): read-only verbs (`cat`, `ls`, `stat`, `test`, `head`, `tail`, `wc`, `file`, `readlink`, `[`), delete (`rm`), reference-only mentions (`grep`; `echo`/`printf` without a redirect targeting the marker file)
- Allow-through 1: active `/implement` pipeline (the pipeline legitimately writes the marker when authorizing issue creation)
- Allow-through 2: agent name in `GH_ISSUE_AGENTS` (`continuous-improvement-analyst`, `issue-creator`)
- Allow-through 3: issue-creating command is active (`_is_issue_command_active()`) — commands such as `/create-issue`, `/plan-to-issues`, `/improve`, `/refactor`, `/retrospective`
- No marker-file allow-through (circular — the guard protects the marker itself)
- Fails open on any detection error to avoid blocking legitimate work

See [SANDBOXING.md](SANDBOXING.md) for complete security architecture.

**plan_gate.py** (Issue #814 — PreToolUse, Write/Edit tools):
- Blocks complex Write/Edit operations when no valid plan exists in `.claude/plans/`
- Simple edits (fewer than 100 new lines) are exempt — only non-trivial changes require a plan
- Documentation files (`.md`, `.rst`, `.txt`, docs/ directory) are always exempt
- Validates plan structure: requires `## WHY + SCOPE`, `## Existing Solutions`, and `## Minimal Path` sections
- Plans older than 72 hours trigger a warning (stderr only, non-blocking) — expired plans do not block work
- Escape hatch: `SKIP_PLAN_CHECK=1` bypasses all checks
- Fails open: any exception or invalid input results in allow
- Block message includes `REQUIRED NEXT ACTION` directive pointing to `/plan`

### PreCommit

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **auto_format.py** | Code formatting (black + isort, prettier) | AUTO_FORMAT |
| **auto_test.py** | Run related test files | AUTO_TEST |
| **security_scan.py** | Secrets detection, vulnerability scanning | SECURITY_SCAN |
| **enforce_tdd.py** | TDD workflow enforcement (tests before code) | ENFORCE_TDD |
| **enforce_prunable_threshold.py** | Blocks commits when prunable test count exceeds `PRUNABLE_THRESHOLD` (100). Uses `TestPruningAnalyzer` for local-only AST scanning (no network calls). Imports threshold from `test_lifecycle_manager`. Graceful degradation on errors (exit 0). Supports `SKIP_PRUNABLE_GATE=1` env var. Strict-mode only. (Issue #863) | SKIP_PRUNABLE_GATE |
| **enforce_regression_test.py** | Blocks `fix:`, `bugfix:`, and `hotfix:` commits when no test files are staged. Uses `bugfix_detector.is_bugfix_commit()` to detect prefixes. Fails open when `bugfix_detector` library is unavailable. Follows stick+carrot pattern: block message includes `REQUIRED NEXT ACTION` directing the committer to add a failing-then-passing regression test. Exception: pass `--no-verify` and document the covering test in the commit body when an existing test already covers the regression. (Issue #737) | — |
| **enforce_orchestrator.py** | PROJECT.md alignment validation | — |
| **validate_project_alignment.py** | PROJECT.md forbidden sections detection | VALIDATE_PROJECT_ALIGNMENT |
| **validate_command_file_ops.py** | Commands execute Python libs, not just describe them | — |
| **validate_session_quality.py** | Session log completeness | — |
| **auto_fix_docs.py** | Documentation consistency auto-fixes | AUTO_FIX_DOCS |
| **validate_claude_md_size.py** | Warns when CLAUDE.md exceeds 200 lines (Anthropic best practice). Non-blocking — always exits 0. | — |

### SubagentStop

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **unified_session_tracker.py** | Session logging, pipeline tracking, progress updates. Reads stdin JSON from Claude Code, computes duration_ms, validates agent_transcript_path, writes JSONL for pipeline_intent_validator ghost detection. Status determination uses `CLAUDE_AGENT_STATUS` env var as authoritative signal when present; falls back to `_determine_success()` text scan only when the env var is absent (Issue #541). Session isolation: when `CLAUDE_SESSION_ID` is set, both `SessionTracker` file selection and `check_pipeline_complete()` filter to the matching session, preventing cross-session contamination when multiple batches run on the same day (Issue #594). Each JSONL entry now includes a `plugin_version` field (e.g. `"3.50.0 (abc1234)"`) populated via `version_reader.get_plugin_version()` for diagnostics and issue triage (Issue #630). **Word count aggregation** (Issue #872/#907): `result_word_count` in JSONL entries is computed by `_count_words_in_transcript()`, which iterates all assistant turns in the JSONL transcript file and sums word counts across both str-content (legacy) and list-of-blocks (modern) content shapes; falls back to splitting the single last-message `agent_output` string when no transcript path is available. This captures multi-turn subagent output rather than only the final turn. **Staged Plan-Exit Pipeline**: when `agent_name == "plan-critic"`, calls `_advance_plan_mode_stage()` to attempt advancing the `.claude/plan_mode_exit.json` marker from `plan_exited` to `critique_done`, unlocking `/implement` and related commands in `unified_pre_tool.py` (Issue #926 — enforcement moved from `unified_prompt_validator.py` to `unified_pre_tool.py` PreToolUse). **PROCEED verdict gate** (Issue #927): `_advance_plan_mode_stage()` now requires `.claude/plan_critic_verdict.json` to exist with `"verdict": "PROCEED"` and a timestamp at least as recent as the plan-mode-exit marker before advancing the stage. REVISE and BLOCKED verdicts leave the gate closed; the verdict file is retained so the plan-critic can re-run. When a PROCEED verdict is accepted, the verdict file is consumed (deleted) to prevent replay. The verdict file is written by the plan-critic agent at the end of every critique round. When the stage successfully advances from `plan_exited` to `critique_done`, the hook emits a `systemMessage` suggesting next steps: `"/plan-to-issues --quick` to create GitHub issues from this plan"` and `"/implement` to begin implementation directly"`. This is an informational nudge only — non-blocking. (Issue #879) | TRACK_SESSIONS, TRACK_PIPELINE, CLAUDE_AGENT_STATUS, CLAUDE_SESSION_ID |

### PostToolUse

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **plan_mode_exit_detector.py** | Detects `ExitPlanMode` tool calls and writes a marker at `.claude/plan_mode_exit.json` with `stage: "plan_exited"`. Implements the **Staged Plan-Exit Pipeline**: stage advances from `plan_exited` → `critique_done` when the plan-critic SubagentStop fires (via `unified_session_tracker.py`). **`unified_pre_tool.py` enforces the two-stage pipeline at PreToolUse** (Issue #926 — moved from `unified_prompt_validator.py`): in `plan_exited` state Write/Edit/non-allowlisted Bash/non-readonly-MCP are denied until plan-critic runs; in `critique_done` state `Bash(gh issue create ...)` and `Task(implementer|issue-creator|continuous-improvement-analyst)` are allowed and consume the marker. Emits a `systemMessage` on ExitPlanMode instructing the model to invoke plan-critic before proceeding. Auto-expires after 30 minutes. Escape hatch: `/implement --skip-review`. Always exits 0. | — |
| **session_activity_logger.py** | Structured JSONL activity logging for continuous improvement analysis. Handles PostToolUse (tool calls) and UserPromptSubmit (user prompts). Sets `"hook": "PostToolUse"` correctly for tool-call entries. Falls back to parsing hook stdin JSON for `session_id` when `CLAUDE_SESSION_ID` env var is absent (common in PostToolUse lifecycle). Session date pinned on first activity to prevent midnight log splits. For Agent/Task tool outputs, extracts `total_tokens`, `tool_uses`, and `agent_duration_ms` from `<usage>` blocks in the result text (Issue #704) — consumed by `pipeline_timing_analyzer.py` for token efficiency analysis. **result_word_count** (Issue #925): `_add_result_word_count()` writes the word count of the agent result into each PostToolUse JSONL entry. Reads `tool_output["content"]` (modern Anthropic Task `toolUseResult` schema — list-of-text-blocks) and delegates to `count_words_in_content()` from `lib/word_count_helpers.py`, which handles both str-content (legacy) and list-of-blocks (modern) shapes. Falls back to splitting `tool_output["output"]` as a flat string when `content` is absent or the word count is 0. Prior to Issue #925, this function read only the flat-string `output` key, logging `result_word_count: 0` for all implementer events (the root cause of 5 false-positive compression closures). Worktree-aware log directory resolution (Issue #755): when the hook's CWD is inside a `.worktrees/` directory, `_find_log_dir()` runs `git rev-parse --git-common-dir` to locate the parent repo's `.claude/logs/activity/` directory, so downstream agent events written from a worktree land in the same log file as main-session events; falls through to normal walk-up resolution on any git error or when the parent `.claude/` directory does not exist. Batch issue attribution (Issue #808): when a BATCH CONTEXT block is detected in an Agent/Task prompt, `batch_issue_number` is extracted by first trying the structured `Issue Number: N` field added to the BATCH CONTEXT template, then falling back to the inline `Issue #N` pattern for backward compatibility; this prevents mis-attribution when free-text issue references appear elsewhere in the prompt. Non-blocking. | ACTIVITY_LOGGING |

### PreCompact

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **pre_compact_batch_saver.sh** | Saves in-progress batch and/or pipeline state to `.claude/compaction_recovery.json` before context compaction. Captures batch_id, current_index, feature list, and RALPH checkpoint data when a batch is active. Also captures `/implement` pipeline state (run_id, feature, current step, steps completed/remaining, modified files) from `/tmp/implement_pipeline_state.json` when a pipeline run is active. No-ops when neither batch nor pipeline is active. Always exits 0. | CHECKPOINT_DIR, PIPELINE_STATE_FILE, PIPELINE_STATE_DIR |

### PostCompact

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **post_compact_enricher.sh** | Enriches the compaction recovery marker with the compact_summary from stdin JSON after compaction completes. No-ops if no recovery marker present. Always exits 0. | — |

**Compaction recovery flow**: PreCompact saves state (batch and/or pipeline) → PostCompact adds summary → UserPromptSubmit (`unified_prompt_validator.py`) detects marker on next prompt, re-injects batch and/or pipeline context into model output, and deletes marker. Pipeline recovery validates staleness (discarded if >900 seconds old) and cwd match before injecting. This ensures both batch pipelines and single `/implement` pipeline runs resume correctly after `/clear` or auto-compact without requiring manual state reconstruction.

### TaskCompleted

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **task_completed_handler.py** | Logs task completion events (task_id, subject, description, teammate, team) to the daily activity JSONL at `.claude/logs/activity/{date}.jsonl`. Preparation handler: TaskCompleted does not currently fire in the Agent-tool pipeline but is registered so infrastructure is ready. Always exits 0. | — |

### Stop

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **stop_quality_gate.py** | End-of-turn quality checks (pytest, ruff, mypy). Auto-detects tools, parallel execution, 60s timeout. Always non-blocking. | ENFORCE_QUALITY_GATE |
| **conversation_archiver.py** | Archives complete Claude Code conversation transcripts to `~/.claude/archive/` on every Stop event for long-term pattern analysis. Writes session metadata to both `~/.claude/archive/index.jsonl` (JSONL, jq/grep compatible) and `~/.claude/archive/sessions.db` (SQLite, queryable via Python sqlite3 or DuckDB). Pure Python stdlib, non-blocking, always exits 0. Enabled via `CONVERSATION_ARCHIVE=true` env var. (Issue #773) | CONVERSATION_ARCHIVE |

### Utility (not lifecycle-triggered)

| Hook | Purpose |
|------|---------|
| **genai_prompts.py** | Prompt templates for GenAI-enhanced hooks |
| **genai_utils.py** | Anthropic SDK wrapper with graceful fallback |
| **setup.py** | Interactive setup wizard for plugin configuration |

---

## Standard Git Hooks

### pre-commit (`scripts/hooks/pre-commit`)

Repository structure validation, command validation, manifest sync, lib import checks, hook documentation checks, and documentation tests.

```bash
# Install
ln -sf ../../scripts/hooks/pre-commit .git/hooks/pre-commit
```

### pre-push (`scripts/hooks/pre-push`)

Fast test suite only (excludes `@pytest.mark.slow`, `@pytest.mark.genai`, `@pytest.mark.integration`). 30s vs 2-5 min full suite.

```bash
# Install
ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
```

---

## Safe Failure Behavior

All 24 hooks wrap their `main()` function with `safe_main()` from `plugins/autonomous-dev/lib/hook_safety.py` (Issue #953). This provides two guarantees:

**1. Hook crashes never block Claude Code.**
If an unhandled exception propagates out of a hook (missing import, runtime bug, etc.), `safe_main()` catches it, prints a `[hook warning] <hook_name>: <ExceptionType>: <message>` line to stderr, and exits with code 0. Claude Code continues normally. Operators can detect failures by scanning stderr for the `[hook warning]` prefix.

**2. `command_registered()` prevents deny-deadlocks.**
Hooks that issue a `deny` decision directing the user to run a slash command (e.g., `/create-issue`) MUST first call `command_registered("create-issue")` from `hook_safety.py`. If the command is not installed, the deny is downgraded to a warning so the user is not stuck between a blocking hook and a missing command. The lookup fails CLOSED (returns `True`) on any error so the existing security barrier remains active.

**Shebang**: All hooks use `#!/usr/bin/env python3` (not `uv`). A pinned `uv` interpreter was itself a deadlock risk — if `uv` was absent from PATH, the hook never reached the `safe_main` safety net. Standard `python3` resolves via PATH without an external tool dependency.

```python
#!/usr/bin/env python3

if __name__ == "__main__":
    from hook_safety import safe_main
    safe_main(main)
```

See `plugins/autonomous-dev/lib/hook_safety.py` for full API documentation.

---

## Archived Hooks

61 hooks have been archived into `plugins/autonomous-dev/hooks/archived/`. These were consolidated into the unified hooks listed above.

See `plugins/autonomous-dev/hooks/archived/README.md` for:
- Complete list of archived hooks
- Migration guides (which unified hook replaced each)
- Historical rationale

---

## Agent Hooks (Experimental)

> **Status**: Proof-of-concept. Advisory only, never enforcement. See [ADR-001-agent-hooks.md](ADR-001-agent-hooks.md) for full rationale.

### type:agent vs type:command

| Property | type:command | type:agent |
|----------|-------------|------------|
| **Format** | Python script (.py) | Markdown prompt (.md) |
| **Execution** | Deterministic Python | LLM subagent (non-deterministic) |
| **Tools available** | Full system access | Read, Grep, Glob only |
| **Limits** | None | 50 tool turns, 60s timeout |
| **Use case** | Enforcement, blocking | Advisory, semantic analysis |

### Key Constraint: Advisory Only

Agent hooks **always** return `{"decision": "approve"}`. They provide informational output (e.g., "these files are missing tests") but never block operations. This is a deliberate design choice:

- LLM non-determinism makes blocking unreliable
- "Hard blocking > nudges" philosophy requires deterministic enforcement
- Advisory output adds value without disrupting workflow

### Available Agent Hooks

| Hook | Event | Purpose |
|------|-------|---------|
| **Stop-verify-test-coverage.md** | Stop | Advisory check: do modified source files have test files? |

### How to Enable (Opt-in)

Agent hooks are **not enabled by default**. To enable, add to `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "agent",
        "prompt": "plugins/autonomous-dev/hooks/Stop-verify-test-coverage.md",
        "description": "Advisory: check test coverage for modified files"
      }
    ]
  }
}
```

To disable, remove the entry. No environment variable controls activation — presence in settings.json is sufficient.

**Warning**: Agent hooks consume tokens on every invocation. Enable only when the advisory output is valuable for your workflow.

---

## Extension Points

Hook extensions allow project-specific or user-specific tool call validation without modifying the core hook files. Extensions survive `/sync` and `/install` updates.

### Extension API Contract

Each extension is a Python file (`.py`) that implements a `check` function:

```python
def check(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """Validate a tool call.

    Args:
        tool_name: Name of the tool (e.g., "Bash", "Edit", "Write").
        tool_input: Tool input parameters dict.

    Returns:
        ("allow", "") to permit the tool call.
        ("deny", "reason") to block it.
    """
    # Example: block raw mlx commands
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if "mlx" in cmd and "realign" not in cmd:
            return ("deny", "Use 'realign train' CLI instead of raw mlx commands")
    return ("allow", "")
```

### Extension Directories

Extensions are discovered from two locations (deduplicated by filename, first occurrence wins):

1. **Global**: `~/.claude/hooks/extensions/*.py` — applies to all projects
2. **Project-level**: `.claude/hooks/extensions/*.py` — project-specific rules

Extensions are loaded in **alphabetical order** within each directory. The first `("deny", reason)` return short-circuits — remaining extensions are not called.

### How Extensions Survive Updates

The `extensions/` directory is **never overwritten** by `/sync`, `/install`, or `deploy-all.sh`. All operations explicitly create or preserve the directory:

- `install.sh`: `mkdir -p ~/.claude/hooks/extensions`
- `sync_dispatcher.py`: `(hooks_dst / "extensions").mkdir(exist_ok=True)`
- `scripts/deploy-all.sh`: rsync uses `--exclude=extensions/` to prevent deletion during `--delete` syncs (Issue #560)

### Environment Variable

| Variable | Default | Effect |
|----------|---------|--------|
| `HOOK_EXTENSIONS_ENABLED` | `true` | Set to `false` to skip all extensions |

### Example Extension

**File**: `~/.claude/hooks/extensions/block_raw_mlx.py`

```python
"""Block raw mlx-lm commands — use realign train CLI instead."""

def check(tool_name: str, tool_input: dict) -> tuple[str, str]:
    if tool_name != "Bash":
        return ("allow", "")
    cmd = tool_input.get("command", "")
    if "mlx_lm" in cmd or "mlx-lm" in cmd:
        if "realign" not in cmd:
            return ("deny", "Use 'realign train' instead of raw mlx-lm commands")
    return ("allow", "")
```

### Security Notes

- **Symlinks are skipped**: Extension files that are symlinks are silently ignored to prevent symlink-based attacks.
- **Per-extension isolation**: Each extension runs in its own try/except block. A crashing extension never affects other extensions or the main hook.
- **No arbitrary code injection**: Extensions are only loaded from the two known directories listed above.

---

## See Also

- [ADR-001-agent-hooks.md](ADR-001-agent-hooks.md) — Architecture Decision Record for agent hooks
- [HOOK-REGISTRY.md](HOOK-REGISTRY.md) — Environment variables, activation status
- [SANDBOXING.md](SANDBOXING.md) — 4-layer security architecture
- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) — Git automation workflow
- [hooks/archived/README.md](/plugins/autonomous-dev/hooks/archived/) — Archived hooks reference
