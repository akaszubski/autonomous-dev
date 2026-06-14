---
covers:
  - plugins/autonomous-dev/hooks/
---

# Hook Registry

**Last Updated: 2026-04-12**

Quick-reference guide for all hooks in the autonomous-dev plugin, including activation status, trigger points, and controlling environment variables.

## Purpose

This registry provides a comprehensive view of:
- All hooks in the plugin (see [CLAUDE.md](../CLAUDE.md) for current counts)
- Default activation status (enabled/disabled/opt-in)
- Trigger points (when hooks execute)
- Environment variables that control behavior
- Cross-references to detailed documentation

**See also**:
- [HOOKS.md](HOOKS.md) - Detailed hook documentation and architecture
- [SANDBOXING.md](SANDBOXING.md) - Sandbox and permission system details
- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) - Git automation workflow

---

## Quick Reference

### Unified Hooks

The plugin uses 31 active hooks (files on disk in `plugins/autonomous-dev/hooks/`, 62 archived):

| Hook File | Lifecycle/Trigger | Status | Purpose |
|-----------|------------------|--------|---------|
| unified_pre_tool | PreToolUse | Enabled | Native tool fast path + project detection guard (Issue #662) + 6-layer permission validation (sandbox, MCP security, agent auth, batch approval, infrastructure protection, prompt quality) + pipeline ordering gate + prompt integrity gate + hook extensions. Project detection guard: non-native MCP tools in non-autonomous-dev projects receive immediate allow before any enforcement layer runs; fail-closed (enforces when detector unavailable). Pipeline ordering gate (Issues #625, #629, #632) enforces agent invocation order for Agent/Task tool calls during active pipeline sessions using `agent_ordering_gate.py` and `pipeline_completion_state.py`. Prompt integrity gate (Issues #695, #716) blocks compression-critical agents (security-auditor, reviewer) when their prompt is below minimum word count (80 words); minimum word count check fires regardless of pipeline state; baseline shrinkage check only during active pipeline. Infrastructure file protection scoped to autonomous-dev repos. Agent denial fallback guard (Issue #750): when prompt integrity denies an Agent call, `_record_agent_denial()` writes a session-scoped state file; subsequent Write/Edit to protected infrastructure paths within 300 seconds (`AGENT_DENY_TTL`) are blocked with a REQUIRED NEXT ACTION directive to reload the agent prompt template — closing the bypass where the orchestrator falls back to direct edits after a shrinkage denial. Env var spoofing detection blocks forged agent identity in Bash commands — exact-match protection for individually listed pipeline vars plus prefix-based protection for any `CLAUDE_*` variable (Issue #606); session-scoped escalation tracker persists attempts to `~/.claude/logs/spoofing_attempts.json` and escalates block messaging on repeated attempts. settings.json write protection during /implement sessions — Write/Edit file tools and Bash `python3 -c` / `python -c` commands containing both a settings file reference and a Python write pattern are blocked (Issue #768). HMAC pipeline state integrity verification. Realign CLI enforcement via `_detect_realign_bypass()` (Issue #754): blocks direct `python -m mlx_lm.*` and `python -m mlx.launch` invocations in realign projects; detection is project-scoped (checks for `src/realign/` dir or "realign" in `pyproject.toml`) and fails open on detection errors. Agent completeness gate (Issues #802, #853): blocks `git commit` when required pipeline agents have not all completed. In batch mode (detected by `.worktrees/batch-` in cwd), iterates ALL issues in the state file and calls `verify_pipeline_agent_completions()` per issue, respecting each issue's `research_skipped` flag; produces a per-issue failure list (`#N: missing agent1, agent2`). In non-batch mode, calls `_check_pipeline_agent_completions()` for the single active issue (existing behavior). Both paths read state via `pipeline_completion_state.py`; bypass (in order of reliability): (1) `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, then retry — file-based one-shot, works mid-session, file consumed on first check; (2) `export SKIP_AGENT_COMPLETENESS_GATE=1` BEFORE launching claude (env vars don't propagate mid-session — Issue #779); (3) inline command prefix `SKIP_AGENT_COMPLETENESS_GATE=1 git commit ...` (the hook parses the Bash command string for the env var prefix; `skip_agent_completeness_gate=true` accepted case-insensitively); Issue #802); fails open on state errors. Spec test deletion scope guard (Issue #790): blocks deletion or truncation of `tests/spec_validation/test_spec_issue{N}_*.py` files belonging to a different issue than the current pipeline run, covering Write-empty, rm, unlink, truncate, redirect-to-empty, Python remove/unlink, and mv-to-non-archived vectors; escape hatch `SKIP_SPEC_DELETION_GUARD=1`; fails open when no pipeline context exists. Batch doc-master completion gate (Issues #786, #837): blocks `git commit` in batch worktrees when any batch issue is missing `doc-master` completion OR when doc-master ran but produced no valid verdict (MISSING/SHALLOW); block message differentiates "doc-master never ran" vs "ran but produced no valid verdict"; delegates to `verify_batch_doc_master_completions()` from `pipeline_completion_state.py`; bypass via `SKIP_BATCH_DOC_MASTER_GATE=1`; fails open on state errors. Prompt quality gate (Issue #842, Layer 6): blocks Write/Edit to `agents/*.md` or `commands/*.md` during active pipeline sessions when content contains prompt anti-patterns (banned persona openers, casual register phrases, oversized constraint sections) as detected by `prompt_quality_rules.py`; fails open on import errors or when pipeline is not active. For Edit operations, checks are diff-aware (Issue #1038): persona and casual-register checks subtract pre-existing violations so only newly introduced anti-patterns block; constraint-density check uses `check_constraint_density_diff()` and only flags sections that are new or worsened. Write operations use full-content checks (all violations flagged, nothing is "pre-existing"). (Issue #557, #606, #662, #695, #716, #750, #754, #786, #790, #802, #837, #842, #853) |
| unified_prompt_validator | UserPromptSubmit | Enabled | Validate user prompts and provide quality nudges. Phase 1 shadow-mode semantic intent classifier: when `INTENT_CLASSIFIER_ENABLED=true`, annotates each prompt with an `IntentResult` (13 classes: `security_critical`, `implement`, `refactor`, `test`, `doc`, `config`, `typo`, `status_query`, `conversation`, `exploration`, `triage`, `remote_ops`, `scratch` — plus AMBIGUOUS fail-open sentinel) written to activity JSONL. Default OFF; byte-identical behavior when disabled. **Phase D (Issue #998)**: when `INTENT_CLASSIFIER_ENABLED=true`, also writes session-mode artifact to `/tmp/session_mode_<hash>.json` via `lib/session_mode.py`; fail-open. **Phase E (Issue #999)**: `INTENT_CLASSIFIER_ENFORCE=true` activates PreToolUse enforcement in `unified_pre_tool.py`, `plan_gate.py`, and `plan_mode_exit_detector.py` — this hook remains a UserPromptSubmit writer only; enforcement happens downstream. |
| unified_session_tracker | SubagentStop | Enabled | Track agent execution and pipeline state. Records agent completion to `pipeline_completion_state.py` after each SubagentStop (Issues #625, #629, #632) to enable ordering enforcement in `unified_pre_tool.py`. Advances plan mode exit marker from `plan_exited` to `critique_done` when plan-critic completes **only when** `.claude/plan_critic_verdict.json` exists with `"verdict": "PROCEED"` and a fresh timestamp (Issue #927 — PROCEED verdict gate). REVISE and BLOCKED verdicts leave the gate closed; the verdict file is retained for subsequent rounds. On PROCEED, the verdict file is consumed (deleted) to prevent replay. On successful stage advance, emits a `systemMessage` suggesting `/plan-to-issues --quick` or `/implement` as next steps (Issue #879). **SubagentStop dedup guard** (Issue #1176): uses atomic `os.open(O_CREAT|O_EXCL)` file-backed marker in `/tmp` (keyed by `sha256(transcript_path)[:16]`) to detect and suppress duplicate SubagentStop firings caused by dual hook registration. Duplicate firings write a `__dedup_skip__:{agent_name}` JSONL entry and exit 0; fails open on unexpected errors. Markers expire after 300 seconds. **Sentinel heartbeat check** (Issue #989): after recording agent completion, calls `ensure_sentinel_heartbeat(session_id)` from `pipeline_completion_state.py` to verify that `<repo>/.claude/local/implement_pipeline_state.json` (resolved by `get_legacy_sentinel_path()`; was `/tmp/implement_pipeline_state.json` before Issue #1206) still exists with the correct `session_id`. If `clear_stale_state()` in `hook_recovery.py` deleted the sentinel (e.g., because a subprocess ran with a different `CLAUDE_SESSION_ID`), a minimal sentinel `{session_id, recovered: True, recovered_at: iso}` is recreated and `[SENTINEL-HEARTBEAT-MISSING]` is emitted to stderr. Never blocks — fail-open on all errors. |
| auto_fix_docs | PreCommit, PostToolUse | Enabled | Auto-fix documentation issues |
| auto_format | PreCommit | Enabled | Automatic code formatting (black, isort) |
| auto_test | PreCommit | Enabled | Automatic test execution |
| enforce_orchestrator | PreToolUse | Enabled | Enforce orchestrator pattern |
| enforce_tdd | PreCommit | Opt-in | Enforce TDD workflow (tests before code) |
| security_scan | PreCommit | Enabled | Security scanning |
| stop_quality_gate | Stop | Enabled | Quality checks after each turn |
| conversation_archiver | Stop | Enabled | Archive complete conversation transcripts to ~/.claude/archive/ for long-term pattern analysis. Writes JSONL index at ~/.claude/archive/index.jsonl and SQLite index at ~/.claude/archive/sessions.db (queryable via Python sqlite3 or DuckDB). Pure Python stdlib, non-blocking, always exits 0. (Issue #773) |
| validate_command_file_ops | PreToolUse | Enabled | Validate command file operations |
| validate_project_alignment | PreCommit | Enabled | Validate PROJECT.md alignment |
| validate_session_quality | Stop | Enabled | Validate session quality and completeness |
| plan_gate | PreToolUse | Enabled | Pre-implementation planning gate — blocks complex Write/Edit when no valid plan exists in .claude/plans/. Exempts documentation files and simple edits (<100 lines). Validates WHY+SCOPE, Existing Solutions, Minimal Path sections. Escape hatch: SKIP_PLAN_CHECK=1. Fails open. (Issue #814) |
| enforce_file_organization | PreToolUse | Enabled | Blocks Write/Edit creating files at repo root outside an allow-list (README.md, pyproject.toml, CLAUDE.md, top-level config files like *.json/*.toml/*.yaml, hidden files). Allow-list extends via plugins/autonomous-dev/templates/project-structure.json (Root directory > allowed_files). Block message suggests destination folder by extension (.py/.sh → scripts/, .md → docs/, .log/.jsonl → logs/, test_*.py → tests/unit/). Escape hatch: universal AUTONOMOUS_DEV_BYPASS=1 / .claude/.bypass. Standalone (not wired into unified_pre_tool.py); stdlib-only; fails open. (Issue #1034) |
| plan_mode_exit_detector | PostToolUse | Enabled | Detect ExitPlanMode calls and write marker; implements staged plan-exit pipeline: plan_exited → (plan-critic runs) → critique_done → /implement allowed. **AC#3 fast-path (Issue #937/#970)**: if `.claude/plan_critic_verdict.json` holds a PROCEED verdict at ExitPlanMode time, the marker is born `stage: "critique_done"` (not `"plan_exited"`), the verdict file is consumed, and the user is immediately unblocked. Without a PROCEED verdict the marker is born `stage: "plan_exited"` as before. **Per Issue #926, the *enforcement* of this marker moved from UserPromptSubmit to PreToolUse (`unified_pre_tool.py`); marker writer behavior otherwise unchanged** |
| session_activity_logger | PostToolUse + PreToolUse (Task\|Agent) | Enabled | Structured JSONL activity logging for continuous improvement. PreToolUse registration (Task\|Agent matcher) caches subagent invocation data via `subagent_invocation_cache.py` for cross-hook SubagentStop correlation (Issue #1087). PostToolUse registration handles tool-call logging unchanged. |
| task_completed_handler | TaskCompleted | Enabled | Log task completion events to activity JSONL for pipeline observability |
| validate_claude_md_size | PreCommit | Enabled | Warn when context files exceed their target sizes: CLAUDE.md > 200 lines (Anthropic best practice), .claude/PROJECT.md > 150 lines (content-allocation target, see docs/development/CONTENT_ALLOCATION.md), ~/.claude/projects/<slug>/memory/MEMORY.md > 200 lines (Anthropic auto-load threshold). Each check is independent; missing files are silently skipped. Non-blocking — always exits 0. |
| enforce_regression_test | PreCommit | Enabled | Block `fix:`, `bugfix:`, and `hotfix:` commits when no test files are staged. Uses `bugfix_detector.is_bugfix_commit()`. Fails open when library unavailable. (Issue #737) |
| enforce_prunable_threshold | PreCommit | Opt-in (strict-mode only) | Block commits when prunable test count exceeds PRUNABLE_THRESHOLD (100). Uses TestPruningAnalyzer for local-only AST scanning. Bypass: SKIP_PRUNABLE_GATE=1. Fails open when libraries unavailable. (Issue #863) |
| genai_utils | Utility | Library | GenAI utilities for OpenRouter API calls |
| genai_prompts | Utility | Library | Prompt templates for GenAI validation |
| setup | Utility | Command | Setup wizard for PROJECT.md creation |

---

## Hooks by Lifecycle

> **Note**: The per-lifecycle tables below include hooks that have since been archived/consolidated. The "Quick Reference / Unified Hooks" table above reflects the current active set. See `plugins/autonomous-dev/hooks/archived/` for consolidated hooks.

### PreToolUse Hooks

Runs before tool execution (can block with permission decision).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| enforce_pipeline_order | Enabled | ENFORCE_PIPELINE_ORDER (default: true), PIPELINE_STATE_FILE | Prevent skipping agent prerequisites in /implement pipeline - blocks implementer unless researcher-local, researcher-web, planner, and test-master have been invoked first |
| enforce_implementation_workflow | Enabled (default: SUGGEST) | ENFORCEMENT_LEVEL, ENFORCE_WORKFLOW_STRICT | Enforce /implement workflow with graduated levels (OFF, WARN, SUGGEST, BLOCK) |
| auto_generate_tests | Opt-in (default: false) | AUTO_GENERATE_TESTS | Auto-generate tests before implementation |

### PostToolUse Hooks

Runs after tool execution (non-blocking, informational).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| plan_mode_exit_detector | Enabled | — | Detect ExitPlanMode tool calls and write `.claude/plan_mode_exit.json` marker with `stage: plan_exited`; consumed by `unified_pre_tool.py` PreToolUse plan-exit gate (Issue #926 — moved from `unified_prompt_validator.py` UserPromptSubmit) as part of Staged Plan-Exit Pipeline (plan_exited → critique_done → terminal action consumes marker); stage advanced by unified_session_tracker when plan-critic SubagentStop fires |
| post_file_move | Enabled | - | Track file moves for documentation updates |
| auto_update_docs | Enabled | AUTO_UPDATE_DOCS (default: true) | Detect API changes and sync docs |
| auto_add_to_regression | Opt-in (default: false) | AUTO_ADD_REGRESSION | Auto-create regression tests |
| detect_doc_changes | Enabled | - | Detect documentation changes |

### UserPromptSubmit Hooks

Runs when user submits a prompt (can provide nudges/warnings).

No additional hooks beyond unified_prompt_validator.

### PreCommit Hooks

Runs before git commit (can block with EXIT_BLOCK).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| pre_commit_gate | Enabled | ENFORCE_TEST_GATE (default: true) | Block commits if tests failed; stricter enforcement in autonomous-dev |
| auto_format | Deprecated (consolidated) | AUTO_FORMAT | Legacy formatter |
| auto_test | Deprecated (consolidated) | AUTO_TEST | Legacy test runner |
| security_scan | Deprecated (consolidated) | SECURITY_SCAN | Legacy security scan |
| enforce_tdd | Opt-in (default: false) | ENFORCE_TDD | Enforce TDD workflow (tests before code); mandatory in autonomous-dev |
| enforce_no_bare_except | Enabled | ENFORCE_NO_BARE_EXCEPT (default: true) | Prevent bare except clauses from being committed |
| enforce_logging_only | Opt-in (default: false) | ENFORCE_LOGGING_ONLY | Prevent print statements in production code |
| auto_enforce_coverage | Opt-in (default: false) | ENFORCE_COVERAGE, MIN_COVERAGE (default: 70 / 80 in autonomous-dev) | Block commits if coverage drops below threshold; 80% in autonomous-dev (#271) |
| block_git_bypass | Enabled | ALLOW_GIT_BYPASS (default: false) | Block git commit --no-verify and --no-gpg-sign flags, enforce hook validation; no bypass allowed in autonomous-dev |
| validate_claude_alignment | Deprecated (consolidated into unified_doc_validator) | - | Legacy alignment check |
| validate_project_alignment | Deprecated (consolidated into unified_doc_validator) | - | Legacy alignment check |
| validate_docs_consistency | Deprecated (consolidated) | - | Legacy doc check |
| validate_documentation_alignment | Deprecated (consolidated) | - | Legacy doc check |
| validate_component_counts | Enabled | VALIDATE_COMPONENT_COUNTS | Validate component counts in CLAUDE.md match filesystem |
| validate_hooks_documented | Enabled | - | Validate all hooks are documented |
| validate_install_manifest | Deprecated (consolidated) | - | Legacy manifest check |
| validate_lib_imports | Enabled | - | Validate library imports |
| validate_readme_accuracy | Enabled | - | Validate README accuracy |
| validate_readme_sync | Enabled | - | Validate README sync with CLAUDE.md |
| validate_readme_with_genai | Opt-in (default: false) | VALIDATE_README_GENAI | GenAI-powered README validation |
| validate_settings_hooks | Enabled | - | Validate settings.json hooks section |
| validate_session_quality | Enabled | - | Validate session quality and completeness |
| validate_commands | Enabled | - | Validate command files |
| validate_command_file_ops | Enabled | - | Validate command file operations |
| validate_command_frontmatter_flags | Enabled | - | Validate command frontmatter flags |
| validate_claude_md_size | Enabled | - | Warn when context files exceed their target sizes: CLAUDE.md > 200 lines, .claude/PROJECT.md > 150 lines, MEMORY.md > 200 lines. Non-blocking — always exits 0. (Issue #661) |
| enforce_regression_test | Enabled | — | Block `fix:`, `bugfix:`, and `hotfix:` prefixed commits when no test files are staged. Delegates prefix detection to `bugfix_detector.is_bugfix_commit()`. Fails open when library unavailable. (Issue #737) |
| enforce_prunable_threshold | Opt-in (strict-mode only) | SKIP_PRUNABLE_GATE | Block commits when prunable test count exceeds PRUNABLE_THRESHOLD (100). Uses TestPruningAnalyzer for local-only AST scanning. Bypass: SKIP_PRUNABLE_GATE=1. Fails open when libraries unavailable. (Issue #863) |

### SubagentStop Hooks

Runs when a subagent completes (can block agent exit with EXIT_BLOCK).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| ralph_loop_enforcer | Enabled by default (v3.48.0, opt-out) | RALPH_LOOP_DISABLED | Validate agent output and retry if needed (RALPH loop) |
| verify_completion | Enabled | - | Verify agent completed successfully |
| verify_agent_pipeline | Enabled | - | Verify pipeline agent execution order |

### Stop Hooks

Runs after every turn/response completes (cannot block, informational only).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| stop_quality_gate | Enabled | ENFORCE_QUALITY_GATE (default: true) | Run quality checks and provide feedback; stricter enforcement in autonomous-dev (#271) |
| conversation_archiver | Enabled | CONVERSATION_ARCHIVE (default: true) | Archive complete conversation transcripts to ~/.claude/archive/ for long-term pattern analysis. Writes JSONL index at ~/.claude/archive/index.jsonl and SQLite index at ~/.claude/archive/sessions.db. Pure Python stdlib, non-blocking, always exits 0. (Issue #773) |

### TaskCompleted Hooks

Runs when a task completes (non-blocking, informational only). Must always exit 0.

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| task_completed_handler | Enabled | — | Log task completion events (task_id, subject, description, teammate, team) to daily activity JSONL. Preparation handler for future Agent-tool task visibility. |

### SessionStart Hooks

Runs when session starts (initialization hooks).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| auto_bootstrap | Enabled | - | Bootstrap plugin setup if needed |
| health_check | Enabled | - | Validate plugin health on session start |

### PreSubagent Hooks

Runs before subagent starts (can block with EXIT_BLOCK).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| alert_uncommitted_feature | Enabled | DISABLE_UNCOMMITTED_ALERT | Warn about uncommitted changes before subagent |
| auto_tdd_enforcer | Opt-in (default: false) | AUTO_TDD_ENFORCER | Enforce TDD workflow (tests before implementation) |
| auto_inject_memory | Opt-in (default: false) | MEMORY_INJECTION_ENABLED | Inject relevant memories into agent context |

### Utility Hooks

Utility scripts used by other hooks (not directly invoked by lifecycle).

| Hook | Status | Purpose |
|------|--------|---------|
| genai_utils | Library | GenAI utilities for Claude API calls |
| genai_prompts | Library | Prompt templates for GenAI validation |
| github_issue_manager | Library | GitHub issue management utilities |
| setup | Command | Setup wizard for PROJECT.md creation |
| sync_to_installed | Utility | Sync plugin to installed location |
| auto_sync_dev | Enabled | Sync plugin development changes to installed location |
| auto_track_issues | Opt-in (default: false) | Auto-create GitHub issues from TODO comments |
| auto_fix_docs | Deprecated (consolidated) | Legacy doc auto-fix |
| enforce_bloat_prevention | Deprecated (consolidated) | Legacy bloat check |
| enforce_command_limit | Deprecated (consolidated) | Legacy command limit |
| enforce_file_organization | Deprecated (consolidated) | Legacy file org check |
| enforce_orchestrator | Deprecated (consolidated) | Legacy orchestrator check |
| enforce_pipeline_complete | Deprecated (consolidated) | Legacy pipeline check |

### Archived Hooks

These hooks have been archived (consolidated into unified hooks):

| Hook | Status | Replacement | Migration Guide |
|------|--------|-------------|-----------------|
| auto_approve_tool | Archived 2026-01-09 | unified_pre_tool (Layer 4: Batch Permission Approver) | See hooks/archived/README.md |
| mcp_security_enforcer | Archived 2026-01-09 | unified_pre_tool (Layer 2: MCP Security Validator) | See hooks/archived/README.md |
| auto_git_workflow (archived) | Archived | Consolidated into git automation hook | - |
| auto_update_project_progress (archived) | Archived | Opt-in feature in session tracking hook | - |
| batch_permission_approver (archived) | Archived | Consolidated into pre-tool permission hook | - |
| detect_feature_request (archived) | Archived | Consolidated into prompt validation hook | - |
| enforce_implementation_workflow (archived) | Archived | Consolidated into prompt validation hook | - |
| log_agent_completion (archived) | Archived | Consolidated into session tracking hook | - |
| post_tool_use_error_capture (archived) | Archived | Consolidated into post-tool error capture hook | - |
| pre_tool_use (archived) | Archived | Consolidated into pre-tool permission hook | - |
| session_tracker (archived) | Archived | Consolidated into session tracking hook | - |

**Note**: For detailed deprecation rationale and migration guidance, see:
- `plugins/autonomous-dev/hooks/archived/README.md` - Complete archival documentation
- [SANDBOXING.md](SANDBOXING.md) - Unified 4-layer security architecture

---

## Environment Variable Reference

All environment variables with default values:

| Category | Key Variables | Defaults |
|----------|---------------|----------|
| Git Automation | AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR | false, false, false |
| Sandbox & Security | SANDBOX_ENABLED, MCP_AUTO_APPROVE | false, false (opt-in) |
| Code Quality | AUTO_FORMAT, AUTO_TEST, SECURITY_SCAN | true, true, true (enabled) |
| Documentation | AUTO_FIX_DOCS, AUTO_UPDATE_DOCS | true, true (enabled) |
| Workflow | ENFORCE_WORKFLOW, QUALITY_NUDGE_ENABLED | true, true (enabled) |

---

### Git Automation

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| AUTO_GIT_ENABLED | false | Git automation hook | Master switch for git automation |
| AUTO_GIT_PUSH | false | Git automation hook | Enable automatic push to remote |
| AUTO_GIT_PR | false | Git automation hook | Enable automatic PR creation |

### Sandbox & Security

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| SANDBOX_ENABLED | false | Pre-tool hook | Enable sandbox command classification |
| SANDBOX_PROFILE | development | Pre-tool hook | Sandbox profile (development/testing/production) |
| MCP_AUTO_APPROVE | false | Pre-tool hook | Enable MCP auto-approval for trusted operations |
| PRE_TOOL_MCP_SECURITY | true | Pre-tool hook | Enable MCP security validation (path traversal, injection) |
| PRE_TOOL_AGENT_AUTH | true | Pre-tool hook | Enable agent authorization checks |
| PRE_TOOL_BATCH_PERMISSION | false | Pre-tool hook | Enable batch permission caching in unified_pre_tool Layer 3 (Issue #348: merged from batch_permission_approver) |

### Code Quality

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| AUTO_FORMAT | true | Code quality hook | Enable automatic code formatting (black, isort) |
| AUTO_TEST | true | Code quality hook | Enable automatic test execution |
| SECURITY_SCAN | true | Code quality hook | Enable security scanning |
| ENFORCE_TDD | false | enforce_tdd | Enforce TDD workflow (tests before code) |
| ENFORCE_COVERAGE | false | auto_enforce_coverage | Block commits if coverage drops below 80% |
| ENFORCE_TEST_GATE | true | pre_commit_gate | Block commits if tests failed |
| ENFORCE_QUALITY_GATE | true | stop_quality_gate | Run quality checks after each turn |

### Documentation

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| AUTO_FIX_DOCS | true | Doc auto-fix hook | Enable automatic documentation fixes |
| AUTO_UPDATE_DOCS | true | Doc auto-fix hook | Enable automatic API documentation updates |
| VALIDATE_PROJECT_ALIGNMENT | true | Doc validator hook | Validate PROJECT.md alignment |
| VALIDATE_CLAUDE_ALIGNMENT | true | Doc validator hook | Validate CLAUDE.md alignment |
| VALIDATE_README_GENAI | false | validate_readme_with_genai | Enable GenAI-powered README validation |

### Structure & Manifest

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| ENFORCE_FILE_ORGANIZATION | true | Structure enforcer | Enforce file organization rules |
| ENFORCE_BLOAT_PREVENTION | true | Structure enforcer | Prevent file bloat (>1000 lines) |
| ENFORCE_COMMAND_LIMIT | true | Structure enforcer | Limit number of commands |
| ENFORCE_PIPELINE_COMPLETE | true | Structure enforcer | Ensure complete pipeline execution |
| ENFORCE_ORCHESTRATOR | true | Structure enforcer | Enforce orchestrator pattern |
| VALIDATE_MANIFEST | true | Manifest sync hook | Validate plugin manifest |
| AUTO_UPDATE_MANIFEST | true | Manifest sync hook | Auto-update manifest on changes |

### Session Tracking

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| TRACK_SESSIONS | true | Session tracker | Enable session tracking |
| TRACK_PIPELINE | true | Session tracker | Enable pipeline tracking |
| AUTO_UPDATE_PROGRESS | false | Session tracker | Auto-update PROJECT-PROGRESS.md |
| CAPTURE_TOOL_ERRORS | true | Post-tool hook | Capture tool errors for debugging |

### Workflow Enforcement

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| ENFORCE_PIPELINE_ORDER | true | enforce_pipeline_order (PreToolUse) | Enable pipeline order enforcement - prevents implementer unless researcher-local, researcher-web, planner, and test-master have run first |
| PIPELINE_STATE_FILE | `<repo>/.claude/local/implement_pipeline_state.json` (resolved by `pipeline_state.get_legacy_sentinel_path()`; was `/tmp/implement_pipeline_state.json` before Issue #1206) | enforce_pipeline_order (PreToolUse) | Path to pipeline state tracking file (session state, agents invoked, prerequisites met) |
| ENFORCE_WORKFLOW | true | Prompt validator | Enforce workflow suggestions (non-blocking) |
| QUALITY_NUDGE_ENABLED | true | Prompt validator | Enable quality nudges |
| INTENT_CLASSIFIER_ENABLED | false | Prompt validator | Enable semantic intent classifier shadow mode; writes classification to activity JSONL and (Phase D+) to `/tmp/session_mode_<hash>.json` |
| INTENT_CLASSIFIER_ENFORCE | false | unified_pre_tool, plan_gate, plan_mode_exit_detector (Phase E) | Phase E rollout knob. When set to `"true"`, pipeline-gating hooks skip non-floor checks for low-risk intent classes (`doc`, `config`, `typo`, `status_query`, `conversation`, `exploration`, `triage`, `remote_ops`, `scratch`). Hard-floor hooks always fire regardless. Fail-safe: any missing/expired artifact or classifier fail-open causes the hooks to enforce normally. Single env var rollback: unset or set to any non-"true" value to revert to pre-Phase-E behavior. (Issue #999) |
| ENFORCEMENT_LEVEL | suggest | enforce_implementation_workflow (PreToolUse) | Graduated enforcement level (off, warn, suggest, block) for /implement workflow - default SUGGEST allows + suggests |
| ENFORCE_WORKFLOW_STRICT | false | enforce_implementation_workflow (PreToolUse) | Legacy variable for BLOCK enforcement (deprecated, use ENFORCEMENT_LEVEL) |
| ALLOW_GIT_BYPASS | false | block_git_bypass (PreCommit) | Allow git commit --no-verify for emergency situations (not recommended) |
| PIPELINE_CLEANUP_PHASE | (unset) | unified_pre_tool (PreToolUse) | Set to `1` or `true` to allow deletion of pipeline state files — escape hatch for authorized STEP 15 / STEP B4 batch cleanup; bypass for pipeline state file deletion guard (Issue #865) |

### Universal Bypass

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| `AUTONOMOUS_DEV_BYPASS` | (unset) | All hooks | Set to any truthy value (`1`, `true`, `yes`, `on`) to bypass every hook in the harness. Bypass events logged to `.claude/logs/hook-bypass.jsonl`. Equivalent to `touch .claude/.bypass` file flag. File flag walk: `.claude/.bypass` in cwd or any ancestor (up to 30 levels, symlinks not followed). Last-resort recovery when a hook deadlocks and no per-hook escape hatch is available. (Issue #969) |

### Hook Recovery Telemetry

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| `HOOK_RECOVERY_DISABLED` | (unset) | `hook_recovery.py` | Set to any truthy value (`1`, `true`, `yes`, `on`) to disable hook recovery telemetry writes to `.claude/logs/hook-recovery.jsonl` and stale-state cleanup via `clear_stale_state()`. Acts as a rollback valve — disables the entire telemetry surface without redeploying. Falsy values (`0`, `false`, `no`, `off`) leave telemetry active. (Issue #970) |

### Hook Extensions

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| HOOK_EXTENSIONS_ENABLED | true | unified_pre_tool extensions | Set to `false` to skip all hook extension scripts. Extension directories: `~/.claude/hooks/extensions/` (global) and `.claude/hooks/extensions/` (project-level). |

### Advanced Features (Opt-in)

| Variable | Default | Controls | Description |
|----------|---------|----------|-------------|
| RALPH_LOOP_ENABLED | false | ralph_loop_enforcer | Enable RALPH loop (agent output validation & retry) |
| MEMORY_INJECTION_ENABLED | false | auto_inject_memory | Enable memory injection into agent context |
| AUTO_GENERATE_TESTS | false | auto_generate_tests | Auto-generate tests before implementation |
| AUTO_ADD_REGRESSION | false | auto_add_to_regression | Auto-create regression tests for new features |
| AUTO_TRACK_ISSUES | false | auto_track_issues | Auto-create GitHub issues from TODO comments |
| AUTO_TDD_ENFORCER | false | auto_tdd_enforcer | Enforce TDD workflow (tests before implementation) |

---

## Hook Activation Status Summary

### Enabled by Default (39 hooks)
These hooks run automatically without configuration:

**Unified Hooks (9)**:
- 10 consolidated hooks for permission validation, session tracking, documentation, structure, and code quality

**Validation Hooks (14)**:
- 14 hooks for hook documentation, library imports, README accuracy, settings validation, and command validation

**Quality Hooks (4)**:
- 4 hooks for commit gates, quality gates, health checks, and uncommitted feature alerts

**Session Hooks (2)**:
- 2 hooks for bootstrapping and plugin development sync

**Deprecated (still enabled) (11)**:
- 11 legacy hooks for formatting, testing, scanning, and validation (consolidated into unified hooks)

### Opt-in (Disabled by Default) (12 hooks)
These hooks require explicit environment variable to enable:

**Git Automation (1)**:
- 1 hook for automatic commit/push/PR operations

**Advanced Features (11)**:
- 11 hooks for RALPH loop, memory injection, test generation, regression tests, issue tracking, and TDD enforcement

### Utility Libraries (7 hooks)
Not directly invoked by lifecycle (used by other hooks):

- 7 utility scripts for GenAI, GitHub integration, setup, and plugin sync

### Archived (9 hooks)
Consolidated into unified hooks:

- 9 archived hooks (see Archived Hooks section above for full list)

---

## Trigger Point Descriptions

| Trigger | Description | When It Runs | Can Block? |
|---------|-------------|--------------|------------|
| **PreToolUse** | Runs before tool execution | Before Read, Write, Edit, Bash, etc. | Yes (permission decision: allow/deny/ask) |
| **PostToolUse** | Runs after tool execution | After Read, Write, Edit, Bash, etc. | No (informational only) |
| **UserPromptSubmit** | Runs when user submits a prompt | When user presses Enter in chat | No (can provide nudges/warnings) |
| **PreCommit** | Runs before git commit | Before git commit completes | Yes (EXIT_BLOCK = 2 blocks commit) |
| **SubagentStop** | Runs when subagent completes | After agent like implementer, doc-master finishes | Yes (EXIT_BLOCK = 2 prevents agent exit) |
| **Stop** | Runs after every turn/response | After Claude completes response | No (informational only, cannot block) |
| **TaskCompleted** | Runs when a task completes | After a task (TaskUpdate) finishes | No (informational only, must exit 0) |
| **SessionStart** | Runs when session starts | When Claude Code starts or /clear | No (initialization only) |
| **PreSubagent** | Runs before subagent starts | Before spawning implementer, test-master, etc. | Yes (EXIT_BLOCK = 2 prevents agent spawn) |

---

## Cross-References

**Detailed Documentation**:
- [HOOKS.md](HOOKS.md) - Complete hook architecture, patterns, and implementation guide
- [SANDBOXING.md](SANDBOXING.md) - Sandbox enforcer, permission system, and MCP security
- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) - Git automation workflow and consent model
- [TESTING-STRATEGY.md](TESTING-STRATEGY.md) - Test categorization and hook testing patterns

**Related Components**:
- [CLAUDE.md](../CLAUDE.md) - Project instructions and architecture overview
- [LIBRARIES.md](LIBRARIES.md) - Library design patterns and security utilities
- [AGENTS.md](AGENTS.md) - Agent pipeline and workflow enforcement

---

## Notes

**Deprecation Status**:
- Deprecated hooks are still functional but consolidated into unified hooks for better maintainability
- They will be removed in a future version (v4.0.0)
- Migration guide: [HOOKS.md](HOOKS.md)

**Performance Impact**:
- Enabled hooks run on every matching trigger (PreToolUse, PreCommit, etc.)
- Opt-in hooks have zero performance impact when disabled
- Unified hooks have ~15% less overhead than running individual hooks

**Security Considerations**:
- All hooks use `allowed-tools:` frontmatter for least privilege
- MCP security validator prevents path traversal, injection, and SSRF
- Sandbox enforcer provides additional command classification layer
- See [SANDBOXING.md](SANDBOXING.md) for complete security architecture

**Testing**:
- All hooks have unit tests in `tests/hooks/`
- Regression tests in `tests/regression/smoke/` validate critical hooks
- Run `pytest tests/hooks/` to validate hook behavior
