# Automation Hooks Reference

**Last Updated**: 2026-01-02 (Issue #172 - UV single-file scripts)
**Location**: `plugins/autonomous-dev/hooks/`

This document provides a complete reference for automation hooks in the autonomous-dev plugin.

---

## Overview

Hooks provide automated quality enforcement, validation, and workflow automation throughout the development process.

---

## UV Single-File Script Support (Issue #172)

All 62 hooks now use UV (Rye's replacement for Virtual Environments) for reproducible script execution with zero environment setup overhead.

### Features

**Benefits of UV Integration**:
- **Instant execution**: No venv activation or dependency installation required
- **Reproducible**: Exact Python version and dependencies specified inline
- **Cross-platform**: Works on macOS, Linux, Windows
- **Zero configuration**: Scripts work directly from git clone
- **Graceful degradation**: Falls back to system Python if UV unavailable

### Hook Format

Each hook now includes:
1. **UV shebang** - Direct execution via UV
2. **PEP 723 metadata block** - Inline dependency and Python version specification
3. **UV detection function** - Checks if running under UV environment

**Example Hook Structure**:
```python
#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Hook docstring..."""

import os
import sys
from pathlib import Path

# UV detection - allows graceful fallback to sys.path setup
def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

# Traditional sys.path setup for non-UV environments
lib_path = Path(__file__).parent.parent / "lib"
if lib_path.exists() and str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))
```

### How It Works

**When a hook runs**:
1. UV shebang `#!/usr/bin/env -S uv run --script --quiet --no-project` executes the script
2. UV parses PEP 723 metadata block and ensures Python >=3.11 and dependencies available
3. Script runs in UV environment with `UV_PROJECT_ENVIRONMENT` set
4. Alternative: If UV unavailable, script falls back to sys.path for library imports
5. Hook runs normally, importing from `plugins/autonomous-dev/lib/`

**Advantages over traditional approach**:
- **No dependency management**: No venv, no requirements.txt, no pip install
- **Immediate execution**: Each hook runs with correct Python version
- **Self-contained**: All configuration in one file (PEP 723 block)
- **Standard format**: PEP 723 becoming Python standard for script dependencies

### Migration Details

**Files Modified** (62 hooks):
- All hooks in `plugins/autonomous-dev/hooks/` updated to UV format
- File permissions set to executable (0755)
- sys.path.insert() fallback preserved for compatibility
- is_running_under_uv() added to each hook for environment detection

**Specific Hook Changes**:
- `pre_commit_gate.py` - PEP 723 block added, UV shebang added
- `health_check.py` - UV detection added, imports maintained
- `auto_format.py` - UV shebang, graceful fallback to sys.path
- All other hooks - Same pattern applied consistently

**No Breaking Changes**:
- Scripts continue to work in traditional environments (no UV)
- Python imports work via sys.path fallback
- Library paths are portable (work from any directory)
- Existing hook activation/configuration unchanged

### Installation Requirements

UV must be installed for optimal performance:

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

**Fallback**: If UV not available, hooks use traditional sys.path mechanism (slower but functional).

### Troubleshooting

**Issue**: "command not found: uv"
- **Solution**: Install UV (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Fallback**: Scripts will still work via sys.path, just slower

**Issue**: "requires-python: 3.11 not available"
- **Solution**: Install Python 3.11+ (`python --version`)
- **Fallback**: Hooks gracefully degrade to available Python version

**Issue**: "No module named 'autonomous_dev'"
- **Solution**: Same as before - ensure plugins/autonomous-dev/lib exists
- **Note**: This is now handled by both UV environment AND sys.path fallback

---

---

## Exit Code Semantics

All hooks use standardized exit codes to communicate status to Claude Code and indicate how the workflow should proceed. Exit code semantics are defined in the `hook_exit_codes` library (see [LIBRARIES.md](#59-hook_exit_codes)).

### Exit Codes

| Code | Constant | Meaning | Workflow Effect |
|------|----------|---------|-----------------|
| **0** | EXIT_SUCCESS | Operation succeeded | Continue normally |
| **1** | EXIT_WARNING | Non-critical issue detected | Continue with warning logged to stderr |
| **2** | EXIT_BLOCK | Critical issue detected | Block workflow (hook must support blocking) |

### Lifecycle Constraints

Different hook lifecycles have different exit code restrictions based on when they run:

#### PreToolUse Hooks (Must exit 0)
- **Allowed exits**: EXIT_SUCCESS (0) only
- **Can block**: No
- **Rationale**: Hooks run after user already approved tool execution, cannot retroactively prevent it
- **Examples**: `unified_pre_tool.py`, `mcp_security_enforcer.py`
- **Use case**: Logging, security validation, permission approval (non-blocking)

#### SubagentStop Hooks (Must exit 0)
- **Allowed exits**: EXIT_SUCCESS (0) only
- **Can block**: No
- **Rationale**: Hooks run after agent completes, work already done, cannot block
- **Examples**: `auto_git_workflow.py`, `log_agent_workflow.py`, `verify_completion.py`
- **Use case**: Post-processing (git automation, logging), completeness verification

#### PreSubagent Hooks (Can block)
- **Allowed exits**: EXIT_SUCCESS (0), EXIT_WARNING (1), EXIT_BLOCK (2)
- **Can block**: Yes
- **Rationale**: Hooks run before agent spawns, can prevent invalid work from starting
- **Examples**: `auto_tdd_enforcer.py`, `enforce_bloat_prevention.py`
- **Use case**: Quality gates, validation before expensive operations

#### PreCommit Hooks (Can block)
- **Allowed exits**: EXIT_SUCCESS (0), EXIT_WARNING (1), EXIT_BLOCK (2)
- **Can block**: Yes
- **Rationale**: Hooks run before commit, can prevent commits that violate requirements
- **Examples**: `unified_code_quality.py`, `unified_structure_enforcer.py`
- **Use case**: Code quality validation, test coverage requirements

#### Stop Hooks (Must exit 0)
- **Allowed exits**: EXIT_SUCCESS (0) only
- **Can block**: No
- **Rationale**: Hooks run after turn/response completes, informational only, cannot block workflow
- **Examples**: `stop_quality_gate.py`
- **Use case**: End-of-turn quality feedback (non-blocking), progress reporting

### Usage Examples

**Success Case** (hook completes without issues):
```python
from hook_exit_codes import EXIT_SUCCESS
if all_checks_pass:
    sys.exit(EXIT_SUCCESS)  # 0 - Workflow continues
```

**Warning Case** (minor issue detected, non-blocking):
```python
from hook_exit_codes import EXIT_WARNING
if minor_issue_detected:
    print("Warning: Minor issue detected", file=sys.stderr)
    sys.exit(EXIT_WARNING)  # 1 - Workflow continues with warning
```

**Block Case** (critical issue, must be fixed):
```python
from hook_exit_codes import EXIT_BLOCK
if critical_issue_detected:
    print("Error: Critical issue detected", file=sys.stderr)
    sys.exit(EXIT_BLOCK)  # 2 - Workflow blocked (only in PreSubagent/PreCommit)
```

**Lifecycle-aware Exit Code** (respect hook lifecycle constraints):
```python
from hook_exit_codes import (
    EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK,
    is_exit_allowed, get_lifecycle_description
)

lifecycle = os.environ.get("HOOK_LIFECYCLE", "Unknown")

# Only allow exits permitted by this lifecycle
if critical_issue and not is_exit_allowed(lifecycle, EXIT_BLOCK):
    # PreToolUse/SubagentStop/Stop hooks cannot block - use warning instead
    print(f"Warning: {get_lifecycle_description(lifecycle)}", file=sys.stderr)
    sys.exit(EXIT_WARNING)
elif critical_issue:
    sys.exit(EXIT_BLOCK)
else:
    sys.exit(EXIT_SUCCESS)
```

### Validation

Hooks should validate they're used in the correct lifecycle:

```python
from hook_exit_codes import LIFECYCLE_CONSTRAINTS, can_lifecycle_block

# Check if this lifecycle supports blocking
lifecycle = "PreToolUse"
if not can_lifecycle_block(lifecycle):
    # This hook cannot block - don't try to exit 2
    if should_block_workflow:
        # Log warning instead
        print("Warning: blocking condition detected but cannot block in PreToolUse", file=sys.stderr)
        sys.exit(EXIT_WARNING)

# View all constraints
for lifecycle, constraint in LIFECYCLE_CONSTRAINTS.items():
    print(f"{lifecycle}: can_block={constraint['can_block']}, allowed_exits={constraint['allowed_exits']}")
```

### Benefits

Using standardized exit codes provides:
1. **Semantic clarity**: EXIT_BLOCK is clearer than hardcoded `sys.exit(2)`
2. **Self-documenting code**: Code explains intent through constant names
3. **Prevents inversion bugs**: Harder to accidentally swap exit codes
4. **Centralized definition**: Single source of truth for all hooks
5. **Type safety**: Import errors caught at startup vs runtime bugs
6. **Lifecycle validation**: Prevents invalid exit codes for hook type

### Related

- Library: `hook_exit_codes.py` (see [LIBRARIES.md section 59](#59-hook_exit_codes))
- Module: `plugins/autonomous-dev/lib/hook_exit_codes.py`
- Tests: `tests/unit/lib/test_hook_exit_codes.py` (23 tests)

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

## Unified Hooks (10) - Issue #144

Consolidated dispatcher hooks that combine multiple individual hooks for reduced collision and easier maintenance.

### unified_prompt_validator.py

**Purpose**: Bypass detection for workflow enforcement + quality workflow nudges
**Consolidates**: detect_feature_request.py, quality_workflow_nudge
**Lifecycle**: UserPromptSubmit
**Environment Variables**: ENFORCE_WORKFLOW, QUALITY_NUDGE_ENABLED

**Features**:
- Detects workflow bypasses (gh issue create, skip /create-issue) - BLOCKING (exit 2)
- Detects implementation intent (implement/add/create/build X) - NON-BLOCKING quality reminder (exit 0 with nudge)
- Non-blocking nudges shown to stderr with helpful guidance
- Controlled via QUALITY_NUDGE_ENABLED (default: true)

### unified_pre_tool.py

**Purpose**: Unified permission decision system with 4-layer validation (sandbox, MCP security, agent auth, batch approval)
**Consolidates**: sandbox_enforcer.py, pre_tool_use.py, enforce_implementation_workflow.py, batch_permission_approver.py
**Lifecycle**: PreToolUse
**Environment Variables**: SANDBOX_ENABLED, SANDBOX_PROFILE, PRE_TOOL_MCP_SECURITY, PRE_TOOL_AGENT_AUTH, PRE_TOOL_BATCH_PERMISSION, MCP_AUTO_APPROVE

**4-Layer Architecture** (Issue #171 - Sandboxing for reduced permission prompts):

Layer 0 (Sandbox Enforcer):
- Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
- Pattern matching against policy (safe_commands, blocked_patterns, shell_injection_patterns)
- Path traversal detection
- Circuit breaker (disables after threshold blocks)
- Decision: SAFE -> auto-approve, BLOCKED -> deny, NEEDS_APPROVAL -> continue to Layer 1

Layer 1 (MCP Security Validator):
- Path traversal validation (CWE-22)
- Command injection detection (CWE-78)
- SSRF prevention (CWE-918)
- Sensitive file access blocking (.env, .ssh, *.key, credentials)
- Decision: Allow -> continue, Deny -> block, Ask -> continue to Layer 2

Layer 2 (Agent Authorization):
- Detects pipeline agents (implementer, test-master, etc.)
- Permits significant code changes for authorized agents
- Blocks autonomous implementation attempts
- Decision: Authorized -> allow, Unauthorized -> continue to Layer 3

Layer 3 (Batch Permission Approver):
- Caches user consent for identical operations
- Reduces prompts from 50+ to ~8-10 per /auto-implement
- Audit logging for compliance
- Decision: Approved -> allow, Denied -> block

**Performance Impact**:
- Layer 0 (Sandbox): Reduces prompts from 50+ to ~8-10 (84% reduction)
- Combined with Layer 3 (Batch): Handles 50+ permission decisions with <10 prompts total

**Environment Variables**:
- SANDBOX_ENABLED (default: false) - Enable/disable sandbox layer
- SANDBOX_PROFILE (default: development) - Security profile (development/testing/production)
- PRE_TOOL_MCP_SECURITY (default: true) - Enable/disable MCP security validation
- PRE_TOOL_AGENT_AUTH (default: true) - Enable/disable agent authorization
- PRE_TOOL_BATCH_PERMISSION (default: false) - Enable/disable batch permission approval
- MCP_AUTO_APPROVE (default: false) - Enable/disable overall auto-approval

**Related Documentation**:
- docs/SANDBOXING.md - User guide for sandbox configuration
- docs/LIBRARIES.md Section 66 - sandbox_enforcer.py API documentation
- plugins/autonomous-dev/config/sandbox_policy.json - Policy configuration file

### unified_post_tool.py

**Purpose**: Tool error capture and logging
**Consolidates**: post_tool_use_error_capture.py
**Lifecycle**: PostToolUse
**Environment Variables**: CAPTURE_TOOL_ERRORS

### unified_session_tracker.py

**Purpose**: Session logging, pipeline tracking, progress updates
**Consolidates**: session_tracker.py, log_agent_completion.py, auto_update_project_progress.py
**Lifecycle**: SubagentStop
**Environment Variables**: TRACK_SESSIONS, TRACK_PIPELINE, AUTO_UPDATE_PROGRESS

### unified_git_automation.py

**Purpose**: Automatic git commit, push, PR creation
**Consolidates**: auto_git_workflow.py
**Lifecycle**: SubagentStop
**Environment Variables**: AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR

### verify_completion.py

**Purpose**: Pipeline completion verification with loop-back retry for incomplete work
**Lifecycle**: SubagentStop
**Trigger**: After doc-master agent completes (last agent in parallel validation)
**Environment Variables**: VERIFY_COMPLETION_ENABLED (default: true)

**Features**:
- Verifies all 8 pipeline agents completed
- Implements circuit breaker (opens after 3 consecutive failures)
- Exponential backoff retry (100ms → 5000ms)
- Max 5 retry attempts
- Creates loop-back checkpoint for incomplete work
- Graceful degradation (always exit 0, non-blocking)
- Audit logging for all verification attempts

**Flow**:
1. Checks if all 8 expected agents present in session
2. If missing agents detected: creates LoopBackState checkpoint
3. If circuit breaker open: logs warning and continues
4. Always exits 0 (hook never blocks pipeline)

**Related**: Issue #170 (completion verification with loop-back)

### unified_code_quality.py

**Purpose**: Code formatting, testing, security scanning, TDD enforcement, coverage
**Consolidates**: auto_format.py, auto_test.py, security_scan.py, enforce_tdd.py, auto_enforce_coverage.py
**Lifecycle**: PreCommit
**Environment Variables**: AUTO_FORMAT, AUTO_TEST, SECURITY_SCAN, ENFORCE_TDD, ENFORCE_COVERAGE

### unified_structure_enforcer.py

**Purpose**: File organization, bloat prevention, command limits, pipeline validation
**Consolidates**: enforce_file_organization.py, enforce_bloat_prevention.py, enforce_command_limit.py, enforce_pipeline_complete.py, enforce_orchestrator.py, verify_agent_pipeline.py
**Lifecycle**: PreCommit
**Environment Variables**: ENFORCE_FILE_ORGANIZATION, ENFORCE_BLOAT_PREVENTION, ENFORCE_COMMAND_LIMIT, ENFORCE_PIPELINE_COMPLETE, ENFORCE_ORCHESTRATOR, VERIFY_AGENT_PIPELINE

### unified_doc_validator.py

**Purpose**: Documentation alignment, consistency, README accuracy
**Consolidates**: validate_project_alignment.py, validate_claude_alignment.py, validate_documentation_alignment.py, validate_docs_consistency.py, validate_readme_accuracy.py, validate_readme_sync.py, validate_readme_with_genai.py, validate_command_file_ops.py, validate_commands.py, validate_hooks_documented.py, validate_command_frontmatter_flags.py
**Lifecycle**: PreCommit
**Environment Variables**: VALIDATE_PROJECT_ALIGNMENT, VALIDATE_CLAUDE_ALIGNMENT, VALIDATE_DOC_ALIGNMENT, VALIDATE_DOCS_CONSISTENCY, VALIDATE_README_ACCURACY, VALIDATE_README_SYNC, VALIDATE_README_GENAI, VALIDATE_COMMAND_FILE_OPS, VALIDATE_COMMANDS, VALIDATE_HOOKS_DOCS, VALIDATE_COMMAND_FRONTMATTER

### unified_doc_auto_fix.py

**Purpose**: Auto-fix documentation, sync development, TDD enforcement, issue tracking
**Consolidates**: auto_fix_docs.py, auto_update_docs.py, auto_add_to_regression.py, auto_generate_tests.py, auto_sync_dev.py, auto_tdd_enforcer.py, auto_track_issues.py, detect_doc_changes.py
**Lifecycle**: PreCommit/PostToolUse
**Environment Variables**: AUTO_FIX_DOCS, AUTO_UPDATE_DOCS, AUTO_ADD_REGRESSION, AUTO_GENERATE_TESTS, AUTO_SYNC_DEV, AUTO_TDD_ENFORCER, AUTO_TRACK_ISSUES, DETECT_DOC_CHANGES

### unified_manifest_sync.py

**Purpose**: Install manifest validation and settings hooks validation
**Consolidates**: validate_install_manifest.py, validate_settings_hooks.py
**Lifecycle**: PreCommit
**Environment Variables**: VALIDATE_MANIFEST, VALIDATE_SETTINGS, AUTO_UPDATE_MANIFEST

---

## Quick Reference by Lifecycle

| Lifecycle | Count | Hooks |
|-----------|-------|-------|
| **SessionStart** | 2 | auto_bootstrap, auto_inject_memory |
| **PreToolUse** | 1 | unified_pre_tool |
| **PostToolUse** | 1 | unified_post_tool |
| **PreCommit** | 5 | unified_code_quality, unified_structure_enforcer, unified_doc_validator, unified_doc_auto_fix, unified_manifest_sync |
| **SubagentStop** | 2 | unified_session_tracker, unified_git_automation |
| **Stop** | 1 | stop_quality_gate |
| **UserPromptSubmit** | 1 | unified_prompt_validator |
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


### auto_inject_memory.py

**Purpose**: Auto-inject relevant memories from previous sessions at SessionStart
**Actions**:
- Loads memories from `.claude/memories/session_memories.json`
- Ranks memories by relevance using TF-IDF scoring
- Formats memories within token budget (500 tokens default)
- Injects formatted memories into initial prompt as markdown context
- Environment variable control (MEMORY_INJECTION_ENABLED default: false)
**Lifecycle**: SessionStart

**Key Features**:
- Memory loading with graceful degradation (continues if file missing)
- Relevance ranking with recency boost (favors recent memories 1-30 days old)
- Token budget enforcement with priority sorting
- Prompt injection at top of prompt for visibility
- Configurable via environment variables

**Environment Variables**:
- MEMORY_INJECTION_ENABLED (default: false) - Enable/disable injection
- MEMORY_INJECTION_TOKEN_BUDGET (default: 500) - Max tokens for memories
- MEMORY_RELEVANCE_THRESHOLD (default: 0.7) - Min relevance score

**Dependencies**:
- memory_layer.py - Memory persistence storage
- memory_relevance.py - TF-IDF relevance scoring
- memory_formatter.py - Token-aware formatting
- path_utils.py - Path detection
- validation.py - Input validation

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

## Core Hooks (14)

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

**Purpose**: PROJECT.md validation (Issue #194 - Forbidden sections detection)
**Checks**:
- Feature alignment with goals, scope, constraints
- Forbidden sections detection (TODO, Roadmap, Future, Backlog, Next Steps, Coming Soon, Planned)
**Lifecycle**: PreCommit

**Forbidden Sections Feature (Issue #194)**:
Prevents strategic documents from becoming task lists. PROJECT.md defines strategic direction (GOALS/SCOPE/CONSTRAINTS); tactical work belongs in GitHub Issues.

**Forbidden Sections**:
- TODO - Indicates incomplete work
- Roadmap - Indicates future planning
- Future - Indicates planned features
- Backlog - Indicates queued work
- Next Steps - Indicates sequential tasks
- Coming Soon - Indicates upcoming work
- Planned - Indicates intentional future work

**Validation Logic**:
- Detects forbidden sections using case-insensitive regex matching
- Provides remediation guidance pointing to `/create-issue`
- Blocks commit until sections are removed or extracted to GitHub Issues
- Works with `/align --project` command for automatic fixing

**Error Message Example**:
```
❌ ERROR: Found forbidden section "TODO" in PROJECT.md
Forbidden sections: TODO, Roadmap, Future, Backlog, Next Steps, Coming Soon, Planned
→ Use /create-issue for feature requests and tactical tasks instead
```

**Integration Points**:
- `/align --project` - Can automatically remove forbidden sections and guide user to `/create-issue`
- `/setup` - Validates new PROJECT.md doesn't contain forbidden sections
- Git PreCommit - Blocks commits with forbidden sections
- Alignment fixer (`alignment_fixer.py`) - Provides section extraction methods for remediation

### validate_claude_alignment.py

**Purpose**: CLAUDE.md alignment checking (v3.0.2+)
**Checks**: Version consistency, agent counts, command availability, feature documentation
**Lifecycle**: PreCommit

### enforce_file_organization.py

**Purpose**: Standard structure enforcement
**Checks**: File placement, directory structure
**Lifecycle**: PreCommit

### enforce_pipeline_complete.py

**Purpose**: Validates all 8 agents ran (v3.2.2+)
**Checks**: researcher-local, researcher-web, planner, test-master, implementer, reviewer, security-auditor, doc-master
**Lifecycle**: PreCommit

### enforce_tdd.py

**Purpose**: Validates tests written before code (v3.0+)
**Checks**: Test file timestamps, TDD workflow compliance
**Lifecycle**: PreCommit

### detect_feature_request.py

**CONSOLIDATED**: Functionality moved to `unified_prompt_validator.py` (Issue #153, v3.43.0+)

**Legacy Purpose**: Enforce workflow discipline - detect feature requests and bypass attempts (Issue #137, v3.41.0+)

**Migration Info**:
- Bypass detection (BLOCK exit 2) → Part of `unified_prompt_validator.py`
- Quality nudge detection (NON-BLOCK) → Part of `unified_prompt_validator.py` with QUALITY_NUDGE_ENABLED control
- Controlled by: ENFORCE_WORKFLOW (bypass blocking) and QUALITY_NUDGE_ENABLED (quality nudges)

**See**: `unified_prompt_validator.py` above for current implementation

### enforce_implementation_workflow.py

**Purpose**: Catch autonomous implementation bypasses - prevent Claude from making significant code changes without proper workflow (Issue #139, v3.41.0+)
**Lifecycle**: PreToolUse (intercepts Edit and Write tool calls on code files)
**Exit Code**: 0 (always - allows Claude Code to process the permission decision)

**How It Works**:
1. Intercepts Edit and Write tool calls before execution
2. Analyzes code changes for significant additions (new functions, classes, >10 lines)
3. If significant: DENIES with guidance to use `/create-issue` or `/auto-implement`
4. If minor (typos, small fixes): ALLOWS through

**Significant Code Patterns Detected**:
- New function definitions (Python `def`, JavaScript `function`, Go `func`, Rust `fn`, etc.)
- New async functions (`async def`, `async function`)
- New class definitions (Python `class`, JavaScript class syntax)
- New exports (JavaScript `export`, TypeScript)
- Significant line additions (>10 new lines)

**Authorized Agents** (allowed to make significant changes):
- `implementer` - Makes code changes as part of /auto-implement workflow
- `test-master` - Writes tests as part of /auto-implement workflow
- `brownfield-analyzer` - Analyzes legacy code during retrofit
- `setup-wizard` - Generates initial project setup code
- `project-bootstrapper` - Creates project scaffolding

**Control**:
- **ENFORCE_IMPLEMENTATION_WORKFLOW** env var (default: `true`)
  - Set to `false` to disable implementation workflow enforcement
  - Recommended: Keep enabled to prevent bypasses
- **CLAUDE_AGENT_NAME** env var: If set to an authorized agent, permits significant changes

**Example Scenarios**:

❌ **Autonomous Implementation (DENIED)**:
```
Claude (not in /auto-implement): Attempts to write a new function to production.py
Hook output: DENIES with message:
  "AUTONOMOUS IMPLEMENTATION DETECTED
   New Python function detected
   File: production.py

   STOP. Use /auto-implement instead for feature implementation."
```

✅ **Authorized Agent (ALLOWED)**:
```
Implementer agent (inside /auto-implement #123): Writes function to implement feature
CLAUDE_AGENT_NAME=implementer set by auto-implement command
Hook output: ALLOWS (passes through)
```

✅ **Minor Fix (ALLOWED)**:
```
Claude: Fixes typo (changes 1 line, no new functions)
Hook output: ALLOWS - "Minor edit, no significant code additions detected"
```

✅ **Non-Code File (ALLOWED)**:
```
Claude: Edits README.md or configuration.yaml
Hook output: ALLOWS - "Non-code file, no enforcement needed"
```

**Why This Matters**:
- Prevents vibe coding (Claude implementing features without validation)
- Enforces TDD (tests must come first via /auto-implement)
- Ensures security review happens (part of /auto-implement pipeline)
- Maintains audit trail of all significant code changes
- Guarantees PROJECT.md alignment check before implementation

**Related**:
- CLAUDE.md Workflow Discipline section (explains philosophy)
- Issue #139 (implementation workflow enforcement)
- Issue #137 (comprehensive workflow discipline)
- `/auto-implement` command (proper feature implementation workflow)
- `/create-issue` command (GitHub issue creation)

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

## Validation Hooks (12)

Hooks for ensuring documentation, commands, codebase stay in sync, and tests pass before commit.

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

### pre_commit_gate.py

**Purpose**: Block commits when tests are failing or haven't been run (Issue #174)
**Actions**:
- Reads test execution status from `status_tracker` library
- Exits with EXIT_SUCCESS (0) if tests passed
- Exits with EXIT_BLOCK (2) if tests failed or status missing
- Can be disabled via ENFORCE_TEST_GATE=false environment variable
- Provides clear error messages with remediation steps
**Lifecycle**: PreCommit (blocks commits with EXIT_BLOCK)
**Library**: Uses `status_tracker.py` from `plugins/autonomous-dev/lib/`

**Problem solved**:
- Prevents broken code from entering version control
- Catches bugs before they reach CI/CD
- Saves team time on debugging broken builds
- Maintains code quality standards

**Configuration**:

Disable the gate in emergency situations (NOT RECOMMENDED):
```bash
ENFORCE_TEST_GATE=false git commit
```

Valid disable values:
- "false" or "False" or "FALSE"
- "0"
- "" (empty string)

All other values enable the gate (default: enabled).

**Exit Codes**:
- EXIT_SUCCESS (0): Tests passed, allow commit
- EXIT_BLOCK (2): Tests failed or not run, block commit

**Error Messages**:

When tests haven't been run:
```
╔════════════════════════════════════════════════════════════════════════╗
║                         COMMIT BLOCKED                                  ║
╚════════════════════════════════════════════════════════════════════════╝

Tests have not been run yet.

Before committing, you must run the test suite:

    pytest

Once tests pass, you can commit:

    git commit
```

When tests are failing:
```
╔════════════════════════════════════════════════════════════════════════╗
║                         COMMIT BLOCKED                                  ║
╚════════════════════════════════════════════════════════════════════════╝

Tests are failing.

Fix failing tests before committing:

    pytest  # Run tests and fix failures

Once all tests pass, you can commit:

    git commit
```

**Integration**:
- Triggered automatically by `git commit`
- No manual invocation required
- Graceful degradation: Returns safe default (blocked) if tracker unavailable
- Non-breaking: Missing status file treated as "tests not run" (requires running tests)

**Testing**:
Works seamlessly with `/auto-implement` pipeline:
- test-master writes status via `write_status(passed=True/False)`
- Commits automatically trigger gate check
- Users can run `pytest` manually and gate checks after

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

## Lifecycle Hooks (3)

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

## SubagentStop Hooks (2)

Hooks that run when a subagent attempts to exit to enforce completion criteria and enable self-correcting execution.

**Purpose**: Validate agent task completion before allowing exit, enable retry loops when validation fails
**Lifecycle**: SubagentStop (can exit 0 or with blocking response JSON)
**Trigger**: When subagent attempts to exit (SubagentStop lifecycle)

### ralph_loop_enforcer.py

**Purpose**: Enforce self-correcting agent execution with validation strategies and retry loop orchestration
**Issue**: #189 (Ralph Loop Pattern for Self-Correcting Agent Execution)
**Lifecycle**: SubagentStop (blocking - can prevent exit)
**Exit Code**: Always EXIT_SUCCESS (0), response sent via JSON

**Features**:
- **Multiple validation strategies**: pytest, safe_word, file_existence, regex, json
- **Retry orchestration**: Respects max iterations, circuit breaker, token limits
- **Security hardening**: Path traversal prevention, ReDoS prevention, no code execution
- **Graceful degradation**: Errors during validation don't crash the hook
- **Opt-in**: RALPH_LOOP_ENABLED environment variable (default: false)

**Validation Strategies**:
1. **pytest** - Run tests and verify pass/fail
2. **safe_word** - Search for completion marker in agent output
3. **file_existence** - Verify expected output files exist
4. **regex** - Extract and validate data via regex pattern
5. **json** - Extract and validate data via JSONPath

**Configuration**:
- **RALPH_LOOP_ENABLED**: Set to "true" to enable (default: false, opt-in)
- **RALPH_LOOP_SESSION_ID**: Session identifier for state tracking (auto-generated if not provided)
- **RALPH_LOOP_TOKEN_LIMIT**: Token limit for entire loop (default: 50000)

**Workflow**:
1. Check if Ralph Loop enabled (RALPH_LOOP_ENABLED=true)
2. If disabled, allow exit (return {"allow": true})
3. If enabled, load validation criteria from environment
4. Call success_criteria_validator library to validate task completion
5. Check if retry allowed (via ralph_loop_manager library):
   - Check max iterations (5 -> block)
   - Check circuit breaker (3 consecutive failures -> block)
   - Check token limit (exceeded -> block)
6. If validation passes, record success and allow exit
7. If validation fails and retry allowed, block exit (return {"allow": false})
8. If validation fails and retry blocked, allow exit with error

**Response Format**:
```json
{
  "allow": true,
  "message": "Task completed successfully",
  "validation_strategy": "pytest",
  "iteration": 1
}
```

Or if blocked:
```json
{
  "allow": false,
  "message": "Validation failed: Tests did not pass. Attempt 1/5",
  "validation_strategy": "pytest",
  "iteration": 1,
  "retry_allowed": true
}
```

**Exit Codes**:
- **EXIT_SUCCESS (0)**: Always - SubagentStop hooks always exit 0
- Allow/block decision communicated via JSON response ({"allow": true/false})

**Error Handling**:
- Validation errors don't crash hook (graceful degradation)
- Malformed criteria logged, validation skipped (default: allow exit)
- Missing validation strategies handled gracefully
- State file corruption handled with fallback to fresh state

**Integration with Libraries**:
- **ralph_loop_manager.py**: Tracks iterations, manages circuit breaker, enforces token limits
- **success_criteria_validator.py**: Validates task completion using specified strategy
- **hook_exit_codes.py**: Exit code constants and lifecycle semantics

**Related**:
- Issue #189 - Ralph Loop Pattern for Self-Correcting Agent Execution
- LIBRARIES.md section 85 - ralph_loop_manager.py (retry orchestration)
- LIBRARIES.md section 86 - success_criteria_validator.py (validation strategies)
- tests/unit/hooks/test_ralph_loop_enforcer.py (test suite)

---

## Stop Hooks (1)

Hooks that run after every turn/response completes to provide non-blocking quality feedback.

**Purpose**: End-of-turn quality gates - detect and report quality issues without blocking workflow
**Lifecycle**: Stop (must exit 0, non-blocking, informational only)
**Trigger**: After every Claude Code turn/response completes

### stop_quality_gate.py

**Purpose**: End-of-turn quality gates with automatic tool detection
**Issue**: #177 (Stop hook for end-of-turn quality gates)
**Lifecycle**: Stop (informational only, never blocks)
**Exit Code**: Always EXIT_SUCCESS (0)

**Features**:
- **Automatic tool detection**: Scans project for pytest, ruff, mypy configuration files
- **Parallel execution**: Runs all available tools simultaneously with 60-second timeout each
- **Graceful degradation**: Handles missing tools, timeouts, and permission errors gracefully
- **Non-blocking**: Always exits 0 (Stop hooks cannot block)
- **Smart output**: Formats results to stderr with emoji indicators and truncated output

**Tools Detected**:
- **pytest**: Test runner (config: pytest.ini, pyproject.toml, setup.cfg, conftest.py)
- **ruff**: Linter (config: ruff.toml, .ruff.toml, pyproject.toml)
- **mypy**: Type checker (config: mypy.ini, .mypy.ini, pyproject.toml, setup.cfg)

**Configuration**:
- **ENFORCE_QUALITY_GATE**: Control quality gate enforcement
  - Set to `false`, `0`, or `no` to disable (case-insensitive)
  - Default: `true` (enabled) - Runs quality checks every turn

**Workflow**:
1. Checks if ENFORCE_QUALITY_GATE enabled (default: yes)
2. Scans project root for configuration files
3. Detects available tools (pytest, ruff, mypy)
4. Runs each available tool with 60-second timeout
5. Captures output (stdout/stderr)
6. Formats results with emoji indicators
7. Outputs to stderr (Claude Code surfaces stderr)
8. Always exits 0 (informational only)

**Output Format**:
```
============================================================
Quality Gate Check Results
============================================================
✅ pytest: passed
❌ ruff: failed (exit code 1)
   Output: foo.py:10:5: E501 Line too long (truncated)
⚠️  mypy: skipped (not configured)
============================================================
```

**Exit Codes**:
- **EXIT_SUCCESS (0)**: Always - Stop hooks cannot block
- Failures reported via stderr, not exit codes

**Error Handling**:
- `FileNotFoundError`: Tool not installed (shown as warning)
- `TimeoutExpired`: Tool timeout after 60s (shown as warning)
- `PermissionError`: Permission denied (shown as warning)
- Any unexpected exception: Graceful degradation (continues without quality checks)

**Environment Control**:
```bash
# Disable quality gate (skip all checks)
export ENFORCE_QUALITY_GATE=false

# Enable quality gate (default)
export ENFORCE_QUALITY_GATE=true
```

**Related**:
- Issue #177 - End-of-turn quality gates (Stop lifecycle)
- LIBRARIES.md section 59 - hook_exit_codes.py (exit code semantics)
- tests/unit/hooks/test_stop_quality_gate.py (54 tests)

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
