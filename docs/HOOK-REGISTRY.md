# Hook Registry

**Last Updated: 2026-01-09**

Quick-reference guide for all hooks in the autonomous-dev plugin, including activation status, trigger points, and controlling environment variables.

## Purpose

This registry provides a comprehensive view of:
- All 70 hooks in the plugin
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

The plugin uses 10 unified hooks that consolidate related functionality:

| Hook Name | Lifecycle/Trigger | Status | Key Env Vars | Purpose |
|-----------|------------------|--------|--------------|---------|
| unified_pre_tool | PreToolUse | Enabled | SANDBOX_ENABLED, PRE_TOOL_MCP_SECURITY | 4-layer permission validation (sandbox, MCP security, agent auth, batch approval) |
| unified_post_tool | PostToolUse | Enabled | CAPTURE_TOOL_ERRORS (default: true) | Tool error capture and logging |
| unified_git_automation | SubagentStop (doc-master) | Opt-in (default: false) | AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR | Automatic commit/push/PR after pipeline completes |
| unified_session_tracker | SubagentStop | Enabled | TRACK_SESSIONS (default: true), TRACK_PIPELINE | Track agent execution and pipeline state |
| unified_doc_validator | PreCommit | Enabled | VALIDATE_PROJECT_ALIGNMENT, VALIDATE_CLAUDE_ALIGNMENT | Validate documentation alignment (consolidated validators) |
| unified_doc_auto_fix | PreCommit, PostToolUse | Enabled | AUTO_FIX_DOCS (default: true), AUTO_UPDATE_DOCS | Auto-fix documentation issues |
| unified_prompt_validator | UserPromptSubmit | Enabled | ENFORCE_WORKFLOW, QUALITY_NUDGE_ENABLED | Validate user prompts and provide quality nudges |
| unified_structure_enforcer | PreCommit | Enabled | ENFORCE_FILE_ORGANIZATION, ENFORCE_BLOAT_PREVENTION | Enforce project structure rules |
| unified_code_quality | PreCommit | Enabled | AUTO_FORMAT (default: true), AUTO_TEST, SECURITY_SCAN | Run formatters, tests, and security scans |
| unified_manifest_sync | PreCommit | Enabled | VALIDATE_MANIFEST, AUTO_UPDATE_MANIFEST | Sync and validate plugin manifest (consolidated validators) |

---

## Hooks by Lifecycle

### PreToolUse Hooks

Runs before tool execution (can block with permission decision).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| auto_generate_tests | Opt-in (default: false) | AUTO_GENERATE_TESTS | Auto-generate tests before implementation |

### PostToolUse Hooks

Runs after tool execution (non-blocking, informational).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
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
| pre_commit_gate | Enabled | ENFORCE_TEST_GATE (default: true) | Block commits if tests failed |
| auto_format | Deprecated (consolidated) | AUTO_FORMAT | Legacy formatter |
| auto_test | Deprecated (consolidated) | AUTO_TEST | Legacy test runner |
| security_scan | Deprecated (consolidated) | SECURITY_SCAN | Legacy security scan |
| enforce_tdd | Opt-in (default: false) | ENFORCE_TDD | Enforce TDD workflow (tests before code) |
| enforce_no_bare_except | Enabled | ENFORCE_NO_BARE_EXCEPT (default: true) | Prevent bare except clauses from being committed |
| enforce_logging_only | Opt-in (default: false) | ENFORCE_LOGGING_ONLY | Prevent print statements in production code |
| auto_enforce_coverage | Opt-in (default: false) | ENFORCE_COVERAGE, MIN_COVERAGE (default: 70) | Block commits if coverage drops below threshold |
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

### SubagentStop Hooks

Runs when a subagent completes (can block agent exit with EXIT_BLOCK).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| ralph_loop_enforcer | Opt-in (default: false) | RALPH_LOOP_ENABLED | Validate agent output and retry if needed (RALPH loop) |
| verify_completion | Enabled | - | Verify agent completed successfully |
| verify_agent_pipeline | Enabled | - | Verify pipeline agent execution order |

### Stop Hooks

Runs after every turn/response completes (cannot block, informational only).

| Hook | Status | Key Env Vars | Purpose |
|------|--------|--------------|---------|
| stop_quality_gate | Enabled | ENFORCE_QUALITY_GATE (default: true) | Run quality checks and provide feedback |

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
| PRE_TOOL_BATCH_PERMISSION | false | Pre-tool hook | Enable batch permission approver |

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
| ENFORCE_WORKFLOW | true | Prompt validator | Enforce workflow suggestions (non-blocking) |
| QUALITY_NUDGE_ENABLED | true | Prompt validator | Enable quality nudges |
| ENFORCE_WORKFLOW_STRICT | false | Prompt validator | Enforce /implement workflow strictly |

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

### Enabled by Default (38 hooks)
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
| **SessionStart** | Runs when session starts | When Claude Code starts or /clear | No (initialization only) |
| **PreSubagent** | Runs before subagent starts | Before spawning implementer, test-master, etc. | Yes (EXIT_BLOCK = 2 prevents agent spawn) |

---

## Cross-References

**Detailed Documentation**:
- [HOOKS.md](HOOKS.md) - Complete hook architecture, patterns, and implementation guide
- [SANDBOXING.md](SANDBOXING.md) - Sandbox enforcer, permission system, and MCP security
- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) - Git automation workflow and consent model
- [TESTING-TIERS.md](TESTING-TIERS.md) - Test categorization and hook testing patterns

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
