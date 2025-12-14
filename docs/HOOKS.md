# Automation Hooks Reference

**Last Updated**: 2025-12-14
**Total Hooks**: 50 (added command frontmatter flag validation - GitHub #133)
**Location**: `plugins/autonomous-dev/hooks/`

This document provides a complete reference for all automation hooks in the autonomous-dev plugin, including core hooks, optional hooks, and lifecycle hooks.

---

## Overview

Hooks provide automated quality enforcement, validation, and workflow automation throughout the development process.

---

## Claude Code 2.0 Hook Format (Issue #112)

The autonomous-dev plugin supports Claude Code 2.0 structured hook format with automatic migration from legacy format.

### Format Overview

**Modern Claude Code 2.0 Format**:
```json
{
  "hooks": {
    "PreCommit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/auto_format.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Key Features**:
- Nested structure with matchers containing hook arrays
- Every hook has `type`, `command`, and `timeout` fields
- Supports glob patterns in `matcher` field
- Timeout specified in seconds (default: 5)

### Legacy Format (Claude Code 1.x)

**Old Flat Format**:
```json
{
  "hooks": {
    "PreCommit": ["auto_format.py", "auto_test.py"]
  }
}
```

**Limitations**:
- Flat array of command strings
- No timeout specification
- No matcher support for conditional execution
- No hook type information

### Automatic Migration

The autonomous-dev plugin automatically detects and migrates legacy hook format to Claude Code 2.0 format during:
- Initial plugin installation
- Plugin updates (via `/update-plugin`)
- Hook activation (via `activate_hooks()`)

**Migration Process**:
1. **Detection**: `validate_hook_format()` checks for legacy indicators
   - Missing `timeout` fields
   - Flat string commands instead of dicts
   - Missing nested `hooks` arrays

2. **Backup**: `_backup_settings()` creates timestamped backup
   - Filename: `settings.json.backup.YYYYMMDD_HHMMSS`
   - Secure permissions: 0o600 (user-only)
   - Atomic write via tempfile + rename

3. **Transformation**: `migrate_hook_format_cc2()` converts legacy to modern format
   - Adds `timeout: 5` to all hooks
   - Converts string commands to dicts with `type` and `command`
   - Wraps in nested `hooks` array
   - Adds `matcher: '*'` for catch-all matching
   - Preserves user customizations (custom timeouts, matchers)

4. **Write**: Atomically writes migrated settings
   - Deep copy ensures original unchanged
   - Idempotent (safe to run multiple times)
   - Graceful degradation if write fails

### Detection Examples

**Legacy Format Detected**:
```python
settings = {"hooks": {"PreCommit": ["auto_format.py"]}}
result = validate_hook_format(settings)
# result = {
#   "is_legacy": True,
#   "reason": "Flat structure detected in PreCommit (string commands instead of dicts)"
# }
```

**Modern Format Detected**:
```python
settings = {
  "hooks": {
    "PreCommit": [
      {
        "matcher": "*",
        "hooks": [
          {"type": "command", "command": "python ...", "timeout": 5}
        ]
      }
    ]
  }
}
result = validate_hook_format(settings)
# result = {"is_legacy": False, "reason": "Modern Claude Code 2.0 format"}
```

### Migration Examples

**String Command Migration**:
```python
legacy = {"hooks": {"PrePush": ["auto_test.py"]}}
modern = migrate_hook_format_cc2(legacy)
# Result:
# {
#   "hooks": {
#     "PrePush": [
#       {
#         "matcher": "*",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "python .claude/hooks/auto_test.py",
#             "timeout": 5
#           }
#         ]
#       }
#     ]
#   }
# }
```

**Preserving Custom Settings**:
```python
legacy = {
  "hooks": {
    "PreCommit": [
      {
        "command": "custom_script.sh",
        "timeout": 10,
        "matcher": "*.py"
      }
    ]
  }
}
modern = migrate_hook_format_cc2(legacy)
# Custom timeout (10) and matcher (*.py) preserved in migration
```

### Backwards Compatibility

- Legacy hooks continue to work unchanged if not migrated
- Migration is non-blocking (plugin update succeeds even if migration fails)
- Backup created before any changes (can be restored if needed)
- Idempotent transformation (safe to migrate same settings multiple times)

### Files Involved

- **hook_activator.py**: Core migration logic
  - `validate_hook_format()` - Detect legacy vs modern format
  - `migrate_hook_format_cc2()` - Transform legacy to CC2
  - `_backup_settings()` - Create timestamped backups
  - `activate_hooks()` - Integrated workflow

- **Test Coverage**: 28 migration tests in test_hook_activator.py
  - Format detection (8 tests)
  - Migration conversion (12 tests)
  - Backup creation (5 tests)
  - Error handling (3 tests)

### See Also

- [GitHub Issue #112](https://github.com/akaszubski/autonomous-dev/issues/112)
- docs/LIBRARIES.md section 9 (hook_activator.py API reference)
- plugins/autonomous-dev/lib/hook_activator.py (implementation)

---

## Quick Reference by Lifecycle

| Lifecycle | Count | Hooks |
|-----------|-------|-------|
| **SessionStart** | 1 | auto_bootstrap |
| **PreToolUse** | 2 | pre_tool_use, batch_permission_approver |
| **PostToolUse** | 1 | post_tool_use_error_capture |
| **PreCommit** | 24 | See Core + Validation sections |
| **SubagentStop** | 3 | session_tracker, log_agent_completion, auto_git_workflow |
| **Utility** | 6 | genai_prompts, genai_utils, github_issue_manager, health_check, setup, sync_to_installed |

---

## SessionStart Hooks (1)

### auto_bootstrap.py

**Purpose**: Auto-bootstrap plugin commands when hook files missing
**Actions**:
- Checks if `.claude/commands` exists with essential commands
- Copies all plugin commands from plugin directory if missing
- Creates marker file (`.autonomous-dev-bootstrapped`) to track completion
**Lifecycle**: SessionStart

---

## PostToolUse Hooks (1)

### post_tool_use_error_capture.py

**Purpose**: Captures tool failures for analysis and GitHub issue creation (Issue #124)
**Actions**:
- Captures all tool failures (non-zero exit codes, stderr errors)
- Logs errors to `.claude/logs/errors/{date}.jsonl`
- Classifies errors as transient vs permanent using `failure_classifier.py`
- Redacts secrets (API keys, tokens) from error messages (CWE-532)
- Non-blocking (failures don't interrupt workflow)
**Lifecycle**: PostToolUse
**Dependencies**: `error_analyzer.py`, `failure_classifier.py`, `path_utils.py`

---

## Core Hooks (13)

Essential hooks for autonomous development workflow and security enforcement.

### auto_format.py

**Purpose**: Automatic code formatting
**Formats**: black + isort (Python), prettier (JS/TS)
**Lifecycle**: PreCommit

### auto_test.py

**Purpose**: Run tests on related test files
**Framework**: pytest
**Lifecycle**: PreCommit

### security_scan.py

**Purpose**: Secrets detection and vulnerability scanning
**Checks**: API keys, passwords, known vulnerabilities
**Lifecycle**: PreCommit

### validate_project_alignment.py

**Purpose**: PROJECT.md validation
**Checks**: Feature alignment with goals, scope, constraints
**Lifecycle**: PreCommit

### validate_claude_alignment.py

**Purpose**: CLAUDE.md alignment checking (v3.0.2+)
**Checks**: Version consistency, agent counts, command availability, feature documentation
**Lifecycle**: PreCommit

### enforce_file_organization.py

**Purpose**: Standard structure enforcement
**Checks**: File placement, directory structure
**Lifecycle**: PreCommit

### enforce_pipeline_complete.py

**Purpose**: Validates all 7 agents ran (v3.2.2+)
**Checks**: researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master
**Lifecycle**: PreCommit

### enforce_tdd.py

**Purpose**: Validates tests written before code (v3.0+)
**Checks**: Test file timestamps, TDD workflow compliance
**Lifecycle**: PreCommit

### detect_feature_request.py

**Purpose**: Enforce workflow discipline - detect feature requests and bypass attempts (Issue #137, v3.41.0+)
**Lifecycle**: UserPromptSubmit (runs on every user input)
**Exit Codes**:
- **0 (PASS)**: Not a feature request - proceed normally
- **1 (WARN)**: Feature request detected - suggest `/auto-implement`
- **2 (BLOCK)**: Bypass attempt detected - BLOCK and enforce `/create-issue` workflow

**Functions**:
- `is_feature_request()`: Detects patterns like "implement X", "add X", "create X", "build X"
  - Strong patterns: "can/could/please implement/add/create/build"
  - Excludes: Questions (ending with ?), queries (what/why/how), commands (show/display/list)
- `is_bypass_attempt()`: Detects patterns trying to skip proper pipelines
  - "gh issue create" (direct gh CLI usage)
  - "create/make/open/file issue" (asking Claude to bypass)
  - "skip/bypass /create-issue" (explicit bypass attempts)
  - Returns False for legitimate `/create-issue` command (correct workflow)
- `get_bypass_message()`: Generates blocking message explaining correct workflow

**Control**:
- **ENFORCE_WORKFLOW** env var (default: `true`)
  - Set to `false` to disable all workflow enforcement
  - Recommended: Keep enabled for discipline

**Example Scenarios**:

❌ **Feature Request (Exit 1 - WARN)**:
```
User: "implement JWT authentication"
Hook output: Suggests /auto-implement with PROJECT.md alignment
```

❌ **Bypass Attempt (Exit 2 - BLOCK)**:
```
User: "gh issue create --title JWT auth"
Hook output: BLOCKS prompt, shows blocking message, requires /create-issue
```

✅ **Normal Prompt (Exit 0 - PASS)**:
```
User: "What is JWT?"
Hook output: None - proceeds normally
```

✅ **Correct Workflow**:
```
User: "/create-issue Add JWT authentication"
Hook output: None - correct command, processes normally
```

**Why This Matters**:
- Prevents vibe coding (direct implementation without validation)
- Ensures all issues go through research pipeline
- Maintains audit trail from issue to implementation
- Blocks manual issue creation (use `/create-issue` instead)

**Related**:
- CLAUDE.md Workflow Discipline section (explains philosophy)
- Issue #137 (workflow enforcement)
- `/create-issue` command (proper GitHub issue creation workflow)

### auto_git_workflow.py

**Purpose**: Automatic git operations after /auto-implement (v3.9.0+)
**Actions**: Stage changes, create commit, push, create PR
**Lifecycle**: SubagentStop (triggers on quality-validator completion)

### pre_tool_use.py

**Purpose**: MCP auto-approval + security validation (v3.38.0+), dynamic hook path (v3.44.0+, Issue #113)
**Reduces**: Permission prompts from 50+ to 0
**Lifecycle**: PreToolUse (registered in ~/.claude/settings.json)
**Replaces**: auto_approve_tool.py, mcp_security_enforcer.py, unified_pre_tool_use.py
**Format**: Standalone shell script (reads JSON from stdin, writes to stdout)
**Dynamic Path Resolution** (v3.44.0, Issue #113):
- **Portable path**: Hooks use ~/.claude/hooks/pre_tool_use.py instead of hardcoded absolute paths
- **find_lib_directory()**: Searches multiple locations for lib directory:
  1. Development: plugins/autonomous-dev/lib (relative to hook)
  2. Local install: ~/.claude/lib
  3. Marketplace: ~/.claude/plugins/autonomous-dev/lib
- **Graceful fallback**: If lib not found, hook still validates MCP operations safely
- **Migration**: Use migrate_hook_paths.py to update existing hook configurations

### session_tracker.py

**Purpose**: Log agent completion to prevent context bloat (Issue #84)
**Action**: Writes agent actions to docs/sessions/ instead of conversation
**Lifecycle**: SubagentStop
**Location**: `plugins/autonomous-dev/hooks/session_tracker.py`

### batch_permission_approver.py

**Purpose**: Intelligently reduce permission prompts during `/auto-implement`
**Actions**:
- Classifies operations into SAFE/BOUNDARY/SENSITIVE levels
- Auto-approves SAFE operations (file reads, doc analysis)
- Allows BOUNDARY operations with logging (code modifications)
- Prompts only for SENSITIVE operations (destructive, external API)
**Lifecycle**: PreToolUse
**Dependencies**: `permission_classifier.py`, `security_utils.py`

### log_agent_completion.py

**Purpose**: Log subagent completions to structured JSON for pipeline tracking
**Actions**:
- Extracts agent name, output, status from environment variables
- Auto-tracks agents invoked via Task tool (idempotent)
- Extracts tools used from agent output
- Creates completion entry with summary and timestamp
**Lifecycle**: SubagentStop
**Dependencies**: `agent_tracker.py`

### ~~mcp_security_enforcer.py~~ (DEPRECATED - replaced by pre_tool_use.py)

**Purpose**: MCP server security validation with permission whitelisting (Issue #95)
**Status**: Merged into pre_tool_use.py (v3.38.0+)
**Note**: Hook collision eliminated by using single PreToolUse script

---

## Optional/Extended Hooks (19)

Additional hooks for enhanced workflow automation.

Note: session_tracker.py moved to Core Hooks as essential for context management (Issue #84).

### auto_enforce_coverage.py

**Purpose**: 80% minimum test coverage enforcement
**Framework**: pytest-cov
**Lifecycle**: PreCommit

### auto_fix_docs.py

**Purpose**: Documentation consistency fixes
**Checks**: Cross-references, formatting, parity
**Lifecycle**: PreCommit

### auto_add_to_regression.py

**Purpose**: Regression test tracking
**Action**: Adds new tests to regression suite
**Lifecycle**: PostCommit

### auto_track_issues.py

**Purpose**: GitHub issue tracking
**Integration**: Links commits to issues
**Lifecycle**: PostCommit

### auto_generate_tests.py

**Purpose**: Auto-generate test boilerplate
**Templates**: Unit tests, integration tests
**Lifecycle**: PreCommit

### auto_sync_dev.py

**Purpose**: Sync development changes
**Action**: Updates plugin files from development environment
**Lifecycle**: PrePush

### auto_tdd_enforcer.py

**Purpose**: Strict TDD enforcement
**Checks**: Red-green-refactor cycle compliance
**Lifecycle**: PreCommit

### auto_update_docs.py

**Purpose**: Auto-update documentation
**Updates**: API docs, README, CHANGELOG
**Lifecycle**: PostCommit

### auto_update_project_progress.py

**Purpose**: Auto-update PROJECT.md goals after /auto-implement (v3.4.0+)
**Updates**: Completed features, progress tracking
**Lifecycle**: SubagentStop

### detect_doc_changes.py

**Purpose**: Detect documentation changes
**Action**: Validates documentation updates
**Lifecycle**: PreCommit

### enforce_bloat_prevention.py

**Purpose**: Prevent context bloat
**Checks**: File sizes, session logs, documentation length
**Lifecycle**: PreCommit

### enforce_command_limit.py

**Purpose**: Command count limits
**Checks**: Maximum commands per agent
**Lifecycle**: PreCommit

### post_file_move.py

**Purpose**: Post-move validation
**Checks**: File references, imports
**Lifecycle**: PostFileMove

### validate_documentation_alignment.py

**Purpose**: Documentation alignment checking
**Checks**: Docs match implementation
**Lifecycle**: PreCommit

### validate_session_quality.py

**Purpose**: Session quality validation
**Checks**: Session log completeness
**Lifecycle**: PostCommit

### enforce_orchestrator.py

**Purpose**: Enforce PROJECT.md alignment validation before commits (strict mode)
**Actions**:
- Checks if strict mode enabled in `.claude/settings.local.json`
- Scans recent session files for orchestrator evidence
- Validates commit messages for alignment markers
- Allows docs-only commits without orchestrator validation
**Lifecycle**: PreCommit

---

## Validation Hooks (11)

Hooks for ensuring documentation, commands, and codebase stay in sync.

### validate_command_file_ops.py

**Purpose**: Enforce commands execute Python libraries (not just describe them)
**Actions**:
- Detects if command describes file operations
- Validates Implementation section EXECUTES Python libraries
- Prevents "sync doesn't work" bug (Issue #127)
**Lifecycle**: PreCommit

### validate_commands.py

**Purpose**: Ensure all commands have proper `## Implementation` sections
**Actions**:
- Checks for `## Implementation` section header
- Validates section contains bash blocks or script execution
- Prevents "command does nothing" bug (Issue #13)
**Lifecycle**: PreCommit

### validate_docs_consistency.py

**Purpose**: Validate documentation stays in sync with code (3-layer defense)
**Actions**:
- **Layer 1**: Validates counts match actual files
- **Layer 2**: GenAI semantic verification (optional)
- **Layer 3**: Cross-doc consistency checks
**Lifecycle**: PreCommit
**Dependencies**: `genai_utils.py`, `genai_prompts.py`

### validate_install_manifest.py

**Purpose**: Auto-sync `install_manifest.json` bidirectionally with source
**Actions**:
- Scans hooks/, lib/, agents/, commands/, scripts/, config/, templates/
- Auto-updates manifest when files added or removed
- Supports `--check-only` mode for CI
**Lifecycle**: PreCommit

### validate_readme_accuracy.py

**Purpose**: Validate README.md claims match filesystem reality
**Actions**:
- Counts agents/skills/commands/hooks in filesystem
- Extracts claimed counts from README.md
- Reports errors (blocking) vs warnings (informational)
**Lifecycle**: PreCommit

### validate_readme_sync.py

**Purpose**: Ensure README.md files in root and plugin stay synchronized
**Actions**:
- Extracts key statistics from both README files
- Classifies mismatches as CRITICAL or WARNING
- CRITICAL mismatches block commits (exit 2)
**Lifecycle**: PreCommit

### validate_readme_with_genai.py

**Purpose**: Advanced README validation using GenAI semantic analysis
**Actions**:
- Validates component counts match claims
- Uses Claude Haiku for semantic verification
- Generates detailed audit reports with `--audit` flag
**Lifecycle**: PreCommit
**Dependencies**: `anthropic` SDK (optional)

### verify_agent_pipeline.py

**Purpose**: Verify expected agents ran during feature implementation
**Actions**:
- Detects if commit includes feature code changes
- Checks pipeline JSON for completed agents
- Validates MINIMUM agents ran (researcher, implementer, doc-master)
- Supports `STRICT_PIPELINE=1` to block commits
**Lifecycle**: PreCommit

### validate_settings_hooks.py

**Purpose**: Ensure hooks referenced in settings template exist
**Actions**:
- Parses global_settings_template.json for hook commands
- Validates each referenced hook file exists in hooks/
- Prevents "hook not found" errors after install
**Lifecycle**: PreCommit

### validate_lib_imports.py

**Purpose**: Catch broken library imports
**Actions**:
- Scans all hooks and libs for import statements
- Validates imported libs exist in lib/
- Catches deleted/renamed lib issues before commit
**Lifecycle**: PreCommit

### validate_hooks_documented.py

**Purpose**: Ensure all hooks are documented in HOOKS.md
**Actions**:
- Compares hooks/ directory against HOOKS.md
- Blocks commits if new hooks lack documentation
- Provides format guidance for adding docs
**Lifecycle**: PreCommit

### validate_command_frontmatter_flags.py

**Purpose**: Ensure slash commands document their --flags in frontmatter (GitHub #133)
**Actions**:
- Extracts all --flag options used in command bodies
- Validates flags are documented in frontmatter (description or argument_hint fields)
- Filters false positives (--help, --version, generic examples)
- Reports undocumented flags with fix guidance
**Lifecycle**: PreCommit
**Non-blocking**: Exit 1 (warning), never blocking (exit 2)
**Related**: Issue #131 - Fixed frontmatter for /align, /batch-implement, /create-issue, /sync

---

## Utility Hooks (6)

Helper modules and manual invocation utilities.

### genai_prompts.py

**Purpose**: Centralized prompt management for GenAI-enhanced hooks
**Actions**:
- Defines 6 reusable prompt templates
- Provides GenAI feature flags per hook
- Stores model configuration (Haiku, 100 tokens, 5s timeout)
**Type**: Utility module (not a lifecycle hook)

### genai_utils.py

**Purpose**: Reusable GenAI SDK wrapper with graceful fallback
**Actions**:
- Initializes Anthropic SDK with lazy loading
- Formats and executes prompts with variable substitution
- Parses classification and binary responses
**Type**: Utility module
**Dependencies**: `anthropic` SDK

### github_issue_manager.py

**Purpose**: Create and manage GitHub issues for `/auto-implement`
**Actions**:
- Checks gh CLI availability and authentication
- Creates GitHub issue at pipeline start
- Adds closing comment with agent summary
- Auto-manages labels (in-progress → completed)
**Type**: Utility class
**Dependencies**: `gh` CLI

### health_check.py

**Purpose**: Validate plugin integrity and marketplace sync status
**Actions**:
- Counts actual agents (20), hooks (45), commands (7)
- Validates component file existence
- Checks dev/installed sync and marketplace version
**Type**: Utility (invoked by `/health-check`)
**Dependencies**: `security_utils.py`, `installation_validator.py`

### setup.py

**Purpose**: Interactive setup wizard for plugin configuration
**Actions**:
- Verifies plugin files installed in `.claude/`
- Offers preset configurations (minimal, solo, team, power-user)
- Creates PROJECT.md, sets up GitHub integration
- Supports `--auto --preset=team` for automation
**Type**: Setup command

### sync_to_installed.py

**Purpose**: Sync local plugin changes to installed location for testing
**Actions**:
- Locates installed plugin with three-layer path security
- Syncs agents/, hooks/, commands/, scripts/, lib/, templates/, docs/
- Auto-detects orphaned files with cleanup guidance
**Type**: Manual utility (plugin development)

---

## Lifecycle Hooks (2)

Special hooks that respond to Claude Code lifecycle events.

### UserPromptSubmit

**Purpose**: Display project context
**Action**: Shows PROJECT.md goals, current progress
**Trigger**: When user submits prompt

### SubagentStop

**Purpose**: Log agent completion and trigger automation
**Actions**:
- session_tracker.py: Log agent completion to docs/sessions/ (prevents context bloat - Issue #84)
- Auto-update PROJECT.md progress (v3.4.0+)
- Auto-detect Task tool agents (v3.8.3+)
- auto_git_workflow.py: Trigger git operations on quality-validator completion

**Hooks in this lifecycle**:
- `session_tracker.py`: Logs agent actions to session file
- `auto_git_workflow.py`: Commits and pushes changes after quality validation

**Trigger**: When agent completes execution

---

## Standard Git Hooks (2)

Traditional git hooks enhanced for larger projects (Issue #94).

### pre-commit

**Location**: `scripts/hooks/pre-commit`
**Purpose**: Test discovery validation with recursive support
**Features**:
- Recursive test discovery using `find tests -type f -name "test_*.py"`
- Supports nested directory structures (unlimited depth)
- Excludes `__pycache__` directories automatically
- Counts all test files for validation
**Performance**: Finds 500+ tests across nested directories
**Library**: Uses `git_hooks.discover_tests_recursive()` from `plugins/autonomous-dev/lib/git_hooks.py`

**What it does**:
```bash
# Discovers tests recursively
TEST_COUNT=$(find tests -type f -name "test_*.py" 2>/dev/null | grep -v __pycache__ | wc -l)
echo "Found $TEST_COUNT test files"
```

**Installation**:
```bash
ln -sf ../../scripts/hooks/pre-commit .git/hooks/pre-commit
```

### pre-push

**Location**: `scripts/hooks/pre-push`
**Purpose**: Run fast tests only before pushing (excludes slow, genai, integration markers)
**Features**:
- Pytest marker filtering: `-m "not slow and not genai and not integration"`
- Minimal verbosity: `--tb=line -q` (prevents pipe deadlock - Issue #90)
- Non-blocking: Warning if pytest not installed
- Fast feedback: 30 seconds vs 2-5 minutes for full suite
**Performance**: 3x+ faster than running all tests (30s vs 2-5min)
**Library**: Uses `git_hooks.get_fast_test_command()` from `plugins/autonomous-dev/lib/git_hooks.py`

**What it does**:
```bash
# Run fast tests only
pytest tests/ -m "not slow and not genai and not integration" --tb=line -q
```

**Markers excluded**:
- `@pytest.mark.slow` - Long-running tests (30+ seconds)
- `@pytest.mark.genai` - GenAI API tests (60+ seconds, requires credentials)
- `@pytest.mark.integration` - Integration tests (20+ seconds, require external services)

**Installation**:
```bash
ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
```

**Bypass** (not recommended):
```bash
git push --no-verify
```

**Performance Comparison** (Issue #94):
- **Before**: 2-5 minutes (all 500+ tests)
- **After**: 30 seconds (~30 fast tests only)
- **Improvement**: 3x+ faster

---

## Hook Activation

### Setup During Installation

Hooks are automatically activated during plugin update (v3.8.0+):

```python
# From hook_activator.py
def activate_hooks(hooks_dir: Path, project_root: Path) -> None:
    """Activate hooks by creating symlinks in .git/hooks/"""
```

### Manual Activation

```bash
# Activate specific hook
python .claude/hooks/setup.py --hook auto_format

# Activate all hooks
python .claude/hooks/setup.py --all
```

---

## See Also

- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) - Git automation details
- [hooks/](/plugins/autonomous-dev/hooks/) - Hook implementations
- [lib/hook_activator.py](/plugins/autonomous-dev/lib/hook_activator.py) - Activation system
