# Archived Hooks

This directory contains hooks that have been deprecated or replaced by the unified hook system.

## auto_approve_tool.py

**Archived**: 2026-01-09
**Reason**: Consolidated into unified_pre_tool.py for better maintainability and unified security architecture

**Problem**:
- Originally created for MCP auto-approval (Issue #73)
- Provided batch permission approver functionality (Layer 3 of security)
- Operated as standalone PreToolUse hook
- Duplication of permission logic across multiple hooks
- Difficult to maintain consistent security policies

**Solution**:
- All auto-approval logic now handled by unified_pre_tool.py
- Unified hook provides 4-layer security architecture:
  - Layer 1: Sandbox Enforcer (command classification)
  - Layer 2: MCP Security Validator (path traversal, injection prevention)
  - Layer 3: Agent Authorization (pipeline agent detection)
  - Layer 4: Batch Permission Approver (caches user consent)
- Single entry point for all pre-tool validation
- Easier to maintain, audit, and extend

**Migration**:
- Old: auto_approve_tool.py handled MCP auto-approval independently
- New: unified_pre_tool.py handles all pre-tool validation with auto-approval as Layer 4

**Functionality Preserved**:
- Subagent context detection (CLAUDE_AGENT_NAME env var)
- Agent whitelist checking (trusted vs restricted agents)
- User consent verification (opt-in design)
- Tool call validation (whitelist/blacklist)
- Circuit breaker logic (auto-disable after 10 denials)
- Comprehensive audit logging (every approval/denial)
- Graceful degradation (errors default to manual approval)

**Replacement**: See `plugins/autonomous-dev/hooks/unified_pre_tool.py` for the unified implementation

**Files affected by this change**:
- `hooks/unified_pre_tool.py` - Now contains batch permission approver logic
- `lib/batch_permission_approver.py` - Library for Layer 4 logic (extracted from auto_approve_tool.py)
- `docs/SANDBOXING.md` - Updated to document unified architecture
- `docs/TOOL-AUTO-APPROVAL.md` - Updated with deprecation notice and migration guide

---

## mcp_security_enforcer.py

**Archived**: 2026-01-09
**Reason**: Consolidated into unified_pre_tool.py for unified security validation

**Problem**:
- Originally created for MCP server security validation (Issue #95)
- Provided MCP Security Validator functionality (Layer 1 of security)
- Operated as standalone PreToolUse hook
- Security validation logic split across multiple hooks
- Inconsistent validation order and error handling

**Solution**:
- All MCP security validation now handled by unified_pre_tool.py
- Unified hook provides comprehensive security:
  - Layer 1: Sandbox Enforcer (SAFE/BLOCKED/NEEDS_APPROVAL classification)
  - Layer 2: MCP Security Validator (CWE-22 path traversal, CWE-78 injection, SSRF prevention)
  - Layer 3: Agent Authorization (trusted agent verification)
  - Layer 4: Batch Permission Approver (user consent caching)
- Consistent validation order with clear layer boundaries
- Unified error handling and audit logging

**Migration**:
- Old: mcp_security_enforcer.py validated MCP tool calls independently
- New: unified_pre_tool.py handles all security validation with MCP as Layer 2

**Functionality Preserved**:
- CWE-22: Path Traversal prevention
- CWE-59: Improper Link Resolution prevention
- CWE-78: OS Command Injection prevention
- SSRF: Server-Side Request Forgery prevention
- Security policy enforcement (.mcp/security_policy.json)
- Filesystem, shell, network, environment operation validation
- Graceful degradation (errors default to manual approval)
- Comprehensive audit logging

**Replacement**: See `plugins/autonomous-dev/hooks/unified_pre_tool.py` for the unified implementation

**Files affected by this change**:
- `hooks/unified_pre_tool.py` - Now contains MCP security validator logic
- `lib/mcp_permission_validator.py` - Library for Layer 2 logic (extracted from mcp_security_enforcer.py)
- `docs/SANDBOXING.md` - Updated to document unified 4-layer architecture
- `docs/MCP-SECURITY.md` - Updated with deprecation notice and migration guide

---

## Benefits of Consolidation

**Improved Maintainability**:
- Single file to update for pre-tool validation changes
- Consistent error handling and logging patterns
- Clear layer boundaries with well-defined responsibilities

**Better Security**:
- Defense-in-depth with 4 explicit layers
- Consistent validation order (sandbox → MCP → agent → batch)
- No gaps between security checks
- Unified audit trail for all decisions

**Easier Testing**:
- Single hook to test instead of multiple independent hooks
- Layer-by-layer testing with clear interfaces
- Reduced complexity in test setup

**Performance**:
- Single hook invocation instead of multiple hook chains
- Shared state across layers (no redundant checks)
- Optimized cache usage for policies and validators

---

## auto_git_workflow.py

**Archived**: 2026-01-09
**Reason**: Consolidated into unified_git_automation.py for better maintainability (Issue #144, #212)

**Problem**:
- Originally created for automatic git commit/push/PR after /auto-implement (Issue #58)
- Operated as standalone SubagentStop hook
- Duplicate files existed: both source and archived versions
- Confusion about which file was authoritative
- Two files meant two locations to maintain for git automation logic

**Solution**:
- Auto git workflow logic consolidated into unified_git_automation.py
- Backward compatibility shim at .claude/hooks/auto_git_workflow.py (56 lines)
- Shim redirects to unified_git_automation.py
- Single source of truth for git automation operations
- Archived version removed (this directory), shim provides compatibility

**Migration**:
- Old: auto_git_workflow.py handled git operations independently
- New: unified_git_automation.py handles all git automation (commit/push/PR/issue-close)
- Shim: .claude/hooks/auto_git_workflow.py redirects to unified for backward compatibility

**Functionality Preserved**:
- Automatic commit after feature completion
- Conventional commit message generation
- Automatic push to remote (if AUTO_GIT_PUSH=true)
- Automatic PR creation (if AUTO_GIT_PR=true)
- Issue auto-close after push (if issue number found)
- First-run consent prompt
- Environment variable configuration (AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR)
- Graceful degradation (errors don't block feature completion)
- Comprehensive audit logging (all git operations)
- Batch mode integration (per-feature commits)

**Replacement**: See `plugins/autonomous-dev/hooks/unified_git_automation.py` for the unified implementation

**Files affected by this change**:
- `hooks/unified_git_automation.py` - Now contains git automation logic (Issue #144)
- `.claude/hooks/auto_git_workflow.py` - Backward compatibility shim (redirects to unified)
- `docs/GIT-AUTOMATION.md` - Updated with deprecation notice (Issue #212)
- `docs/HOOKS.md` - Updated with migration context (Issue #144)
- `docs/ARCHITECTURE-OVERVIEW.md` - Documents shim and unified implementation (Issue #212)
- `CHANGELOG.md` - Entry for duplicate resolution (Issue #212)

---

## Benefits of Consolidation

**Improved Maintainability**:
- Single file to update for pre-tool validation changes
- Consistent error handling and logging patterns
- Clear layer boundaries with well-defined responsibilities

**Better Security**:
- Defense-in-depth with 4 explicit layers
- Consistent validation order (sandbox → MCP → agent → batch)
- No gaps between security checks
- Unified audit trail for all decisions

**Easier Testing**:
- Single hook to test instead of multiple independent hooks
- Layer-by-layer testing with clear interfaces
- Reduced complexity in test setup

**Performance**:
- Single hook invocation instead of multiple hook chains
- Shared state across layers (no redundant checks)
- Optimized cache usage for policies and validators

---

**This directory is kept for historical reference and in case we need to restore parts of the logic.**
