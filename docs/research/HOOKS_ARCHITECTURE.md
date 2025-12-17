# Hooks Architecture Research

> **Issue Reference**: Core architecture (v1.0+)
> **Research Date**: 2025-12-17
> **Status**: Active

## Overview

Research and design decisions behind the autonomous-dev hooks architecture. The plugin uses 53 hooks across 5 lifecycle events to provide automated quality enforcement, validation, and workflow automation.

---

## Key Findings

### 1. Hook Lifecycle Events

Claude Code 2.0 provides 5 hook lifecycle events:

| Event | Trigger | Use Case |
|-------|---------|----------|
| **PreToolUse** | Before any tool execution | Security validation, permission checking |
| **PostToolUse** | After tool completes | Logging, state updates |
| **PreCommit** | Before git commit | Code quality, formatting, tests |
| **PostCommit** | After git commit | Notifications, syncing |
| **SubagentStop** | After agent completes | Pipeline coordination, git automation |

### 2. Dispatcher Pattern

**Problem**: Multiple validators needed for same lifecycle event (e.g., PreToolUse needs security + permissions + batch approval).

**Solution**: Unified dispatcher pattern (Issue #142).

```python
# Instead of 3 separate hooks:
# - pre_tool_use.py (security)
# - enforce_implementation_workflow.py (agent auth)
# - batch_permission_approver.py (batching)

# Single dispatcher with env var control:
unified_pre_tool.py
  - PRE_TOOL_MCP_SECURITY=true (default)
  - PRE_TOOL_AGENT_AUTH=true (default)
  - PRE_TOOL_BATCH_PERMISSION=false (default)
```

**Benefits**:
- Single entry point (reduced hook count from 3 to 1)
- Environment variable control (toggle features without code changes)
- Clear decision logic (deny > allow > ask)
- Better debugging (one log stream)

### 3. Graceful Degradation

**Principle**: Hooks should never block workflow due to infrastructure issues.

**Implementation**:
```python
# Pattern: Try/except with informational logging
try:
    lib_dir = find_lib_directory(hook_path)
    if lib_dir:
        sys.path.insert(0, str(lib_dir))
        from security_utils import validate_path
except ImportError:
    # Log warning but continue
    print("ℹ️  Security validation skipped (library not available)")
    return "allow"  # Don't block
```

**Rules**:
1. Missing libraries → skip feature, continue workflow
2. Network timeouts → log warning, continue
3. Permission errors → inform user, don't crash
4. Parse errors → safe defaults

### 4. Claude Code 2.0 Hook Format

**Modern format** (Issue #112):
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

**Key elements**:
- `matcher`: Glob pattern for conditional execution
- `type`: "command" for shell commands
- `command`: Full command with path
- `timeout`: Seconds before hook times out (default: 5)

### 5. Dynamic Library Resolution

**Problem**: Hooks run in different contexts (development, local install, marketplace).

**Solution**: Multi-location library search (Issue #113).

```python
def find_lib_directory(hook_path: Path) -> Path | None:
    # Priority order:
    # 1. Development: plugins/autonomous-dev/lib
    # 2. Local install: ~/.claude/lib
    # 3. Marketplace: ~/.claude/plugins/autonomous-dev/lib

    locations = [
        hook_path.parent.parent / "lib",
        Path.home() / ".claude" / "lib",
        Path.home() / ".claude" / "plugins" / "autonomous-dev" / "lib"
    ]

    for loc in locations:
        if loc.exists() and loc.is_dir():
            return loc
    return None
```

---

## Design Decisions

### Why Environment Variables for Toggle?

**Considered alternatives**:
1. Config file (rejected - extra file management)
2. Command-line args (rejected - hook interface fixed)
3. Environment variables (chosen - universal, no file I/O)

**Implementation**:
```python
mcp_security_enabled = os.getenv("PRE_TOOL_MCP_SECURITY", "true").lower() == "true"
agent_auth_enabled = os.getenv("PRE_TOOL_AGENT_AUTH", "true").lower() == "true"
```

### Why Unified Dispatchers?

**Problem**: Hook count explosion (51+ hooks → maintenance burden).

**Solution**: Consolidate related hooks into dispatchers.

| Before | After |
|--------|-------|
| pre_tool_use.py | unified_pre_tool.py |
| enforce_implementation_workflow.py | (consolidated) |
| batch_permission_approver.py | (consolidated) |
| auto_format.py | unified_code_quality.py |
| auto_lint.py | (consolidated) |
| auto_test.py | (consolidated) |

**Result**: Fewer files, same functionality, easier debugging.

### Why Timeout Defaults?

**Research**: Most hooks complete in <2 seconds. 5-second default provides buffer.

| Hook Type | Typical Time | Timeout |
|-----------|-------------|---------|
| Security validation | 50-200ms | 5s |
| Code formatting | 1-3s | 10s |
| Test execution | 5-30s | 60s |
| Git operations | 1-5s | 30s |

---

## Hook Categories

### 1. Validation Hooks (PreToolUse, PreCommit)

**Purpose**: Block operations that violate rules.

| Hook | Function |
|------|----------|
| unified_pre_tool.py | Security + permissions + batching |
| unified_prompt_validator.py | Input validation |
| validate_project_alignment.py | PROJECT.md alignment |
| validate_claude_alignment.py | CLAUDE.md drift detection |
| security_scan.py | Secret detection |

### 2. Automation Hooks (PostToolUse, PostCommit)

**Purpose**: Trigger actions after events.

| Hook | Function |
|------|----------|
| unified_post_tool.py | Logging + state updates |
| unified_session_tracker.py | Session logging |
| auto_git_workflow.py | Auto-commit/push |
| unified_manifest_sync.py | Manifest updates |

### 3. Quality Hooks (PreCommit)

**Purpose**: Enforce code quality standards.

| Hook | Function |
|------|----------|
| unified_code_quality.py | Format + lint + type check |
| enforce_tdd.py | TDD enforcement |
| auto_test.py | Test execution |
| auto_enforce_coverage.py | Coverage validation |

### 4. Coordination Hooks (SubagentStop)

**Purpose**: Coordinate multi-agent workflows.

| Hook | Function |
|------|----------|
| verify_agent_pipeline.py | Pipeline completion check |
| auto_git_workflow.py | Post-agent git ops |

---

## Source References

- **Claude Code Documentation**: Hook lifecycle events and format
- **OWASP Secure Coding**: Graceful degradation patterns
- **12-Factor App**: Environment variable configuration
- **Unix Philosophy**: Do one thing well (dispatcher pattern)

---

## Implementation Notes

### Applied to autonomous-dev

1. **53 hooks** across 5 lifecycle events
2. **Dispatcher pattern** reduces cognitive load
3. **Environment variables** for runtime configuration
4. **Graceful degradation** prevents workflow blocking
5. **Dynamic library resolution** for portable installation

### File Locations

```
plugins/autonomous-dev/hooks/
├── unified_pre_tool.py       # PreToolUse dispatcher
├── unified_post_tool.py      # PostToolUse dispatcher
├── unified_code_quality.py   # Code quality dispatcher
├── unified_doc_validator.py  # Documentation dispatcher
├── validate_*.py             # Validation hooks
├── auto_*.py                 # Automation hooks
└── enforce_*.py              # Enforcement hooks
```

---

## Related Issues

- **Issue #112**: Claude Code 2.0 hook format migration
- **Issue #113**: Dynamic library resolution
- **Issue #142**: Unified PreToolUse hook dispatcher

---

**Generated by**: Research persistence (Issue #151)
