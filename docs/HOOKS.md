# Automation Hooks Reference

**Last Updated**: 2025-12-07
**Total Hooks**: 44 (added mcp_security_enforcer.py - Issue #95)
**Location**: `plugins/autonomous-dev/hooks/`

This document provides a complete reference for all automation hooks in the autonomous-dev plugin, including core hooks, optional hooks, and lifecycle hooks.

---

## Overview

Hooks provide automated quality enforcement, validation, and workflow automation throughout the development process.

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

**Purpose**: Auto-detect feature requests in commits
**Action**: Suggests /auto-implement for feature work
**Lifecycle**: PreCommit

### auto_git_workflow.py

**Purpose**: Automatic git operations after /auto-implement (v3.9.0+)
**Actions**: Stage changes, create commit, push, create PR
**Lifecycle**: SubagentStop (triggers on quality-validator completion)

### pre_tool_use.py

**Purpose**: MCP auto-approval + security validation (v3.38.0+)
**Reduces**: Permission prompts from 50+ to 0
**Lifecycle**: PreToolUse (registered in ~/.claude/settings.json)
**Replaces**: auto_approve_tool.py, mcp_security_enforcer.py, unified_pre_tool_use.py
**Format**: Standalone shell script (reads JSON from stdin, writes to stdout)

### session_tracker.py

**Purpose**: Log agent completion to prevent context bloat (Issue #84)
**Action**: Writes agent actions to docs/sessions/ instead of conversation
**Lifecycle**: SubagentStop
**Location**: `plugins/autonomous-dev/hooks/session_tracker.py`

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

Plus 5 additional hooks for extended enforcement and validation.

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
