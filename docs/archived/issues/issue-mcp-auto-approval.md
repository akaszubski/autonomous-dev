# MCP Auto-Approval for Subagent Tool Calls

## Description

Currently, the `/auto-implement` workflow requires the `--dangerously-skip-permissions` flag to avoid manual approval prompts for every tool call made by subagents. During a typical 7-agent pipeline (researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master), subagents invoke 50+ tool calls (WebSearch, Bash, Read, Write, etc.). Each permission prompt adds context overhead and workflow friction.

This issue proposes implementing a safe, configurable MCP (Model Context Protocol) auto-approval system that:
- Automatically approves whitelisted tool calls for subagents only
- Preserves human oversight for main context interactions
- Prevents destructive operations via blacklisting
- Reduces context usage and improves workflow performance

**Why This Matters**:
- **Performance**: Permission prompts slow down the 7-agent pipeline (currently 22-36 minutes baseline)
- **Context Efficiency**: Each prompt adds ~200-500 tokens of context overhead
- **User Experience**: Seamless subagent execution without manual intervention
- **Safety**: Replace `--dangerously-skip-permissions` with controlled, audited auto-approvals

**Alignment with Goals** (PROJECT.md):
- Supports autonomous development workflow (fewer interruptions)
- Improves performance (addresses Issue #46 optimization goals)
- Maintains security (controlled whitelist approach)

## Research Findings

### Existing Patterns

**Current MCP Architecture** (`.mcp/config.json`):
- Filesystem access (read/write repository files)
- Shell commands (git, python, npm, etc.)
- Git operations (status, diff, commit)
- Python interpreter (with virtualenv)
- **Gap**: No granular permission control for subagent contexts

**Current Tool Usage Patterns**:
```python
# Researcher agent (agents/researcher.md)
- WebSearch: ~10-15 calls per feature (pattern discovery)
- Read: ~5-10 calls (reading existing code)

# Implementer agent (agents/implementer.md)
- Bash: ~5-8 calls (running tests, checking syntax)
- Write: ~3-5 calls (writing implementation)
- Read: ~2-4 calls (reading test files)

# Test-Master agent (agents/test-master.md)
- Bash: ~3-5 calls (pytest commands)
- Write: ~2-4 calls (test file creation)
```

**Subagent Detection** (from `hooks/auto_git_workflow.py`):
```python
# Subagents identified via Task tool invocation pattern
CORE_WORKFLOW_AGENTS = [
    "researcher", "planner", "test-master", "implementer",
    "reviewer", "security-auditor", "doc-master"
]
```

### Best Practices

**MCP Permission Models** (from Claude Code 2.0 documentation):
1. **Explicit Approval**: Default - prompt for every tool call
2. **Session-Based**: Approve once per session
3. **Policy-Based**: JSON config with allow/deny rules
4. **Audit-First**: Log all operations, review later

**Recommended Approach**: Policy-based with audit logging (aligns with existing `security_utils.py` patterns)

**Whitelist Design Patterns**:
```json
{
  "auto_approve": {
    "subagents_only": true,
    "tools": {
      "WebSearch": {"enabled": true},
      "Read": {"enabled": true, "paths": ["*"]},
      "Write": {"enabled": true, "paths": ["!.git/*", "!.env"]},
      "Bash": {
        "enabled": true,
        "whitelist": ["pytest", "git status", "git diff", "python -m"],
        "blacklist": ["rm -rf", "sudo", "git push --force", "> /dev/null"]
      }
    }
  }
}
```

### Security Considerations

**CWE-78: OS Command Injection**:
- **Risk**: Auto-approved bash commands could be exploited if subagent is compromised
- **Mitigation**: Whitelist approach with regex validation, subprocess.run with shell=False
- **Audit**: Log all auto-approved commands to `logs/mcp_auto_approve.log`

**CWE-73: External Control of File Name or Path**:
- **Risk**: Auto-approved Write operations could be tricked into writing sensitive files
- **Mitigation**: Path validation using existing `security_utils.validate_path()`
- **Blacklist**: `.git/`, `.env`, `~/.ssh/`, system directories

**Defense in Depth**:
1. **Subagent Isolation**: Auto-approval only when context is subagent (not main)
2. **Command Validation**: Regex matching against whitelist/blacklist before approval
3. **Path Validation**: Reuse `security_utils.py` for all file operations
4. **Audit Logging**: All auto-approvals logged with timestamp, agent, command, result
5. **Circuit Breaker**: Auto-disable after N failures or suspicious patterns

## Implementation Plan

### Components

**1. MCP Configuration Schema** (~100 LOC)
- **File**: `.mcp/auto_approve_policy.json`
- **Purpose**: Define whitelist/blacklist rules for tool calls
- **Features**:
  - Per-tool enable/disable flags
  - Path restrictions for Read/Write
  - Command whitelist/blacklist for Bash
  - Subagent-only enforcement
- **Integration**: Loaded by MCP approval interceptor

**2. MCP Approval Interceptor** (~300 LOC)
- **File**: `plugins/autonomous-dev/lib/mcp_approval_interceptor.py`
- **Purpose**: Intercept tool calls and auto-approve based on policy
- **Functions**:
  - `load_policy()`: Parse JSON config
  - `is_subagent_context()`: Detect if current context is subagent
  - `should_auto_approve(tool, args)`: Check whitelist/blacklist
  - `validate_bash_command(cmd)`: Regex validation for Bash
  - `validate_path(path)`: Reuse `security_utils.validate_path()`
  - `audit_log(tool, args, approved)`: Log to `logs/mcp_auto_approve.log`
- **Integration**: Hook into Claude Code MCP layer (exact integration point TBD based on Claude Code internals)

**3. Subagent Context Detector** (~150 LOC)
- **File**: `plugins/autonomous-dev/lib/subagent_context_detector.py`
- **Purpose**: Identify when context is a subagent vs main conversation
- **Functions**:
  - `detect_subagent_invocation()`: Check for Task tool pattern
  - `get_current_agent()`: Extract agent name from context
  - `is_core_workflow_agent(agent)`: Match against CORE_WORKFLOW_AGENTS list
- **Integration**: Called by MCP approval interceptor

**4. Command Validator** (~200 LOC)
- **File**: `plugins/autonomous-dev/lib/command_validator.py`
- **Purpose**: Validate bash commands against whitelist/blacklist
- **Functions**:
  - `compile_regex_rules(whitelist, blacklist)`: Precompile regex patterns
  - `matches_whitelist(cmd)`: Check if command is whitelisted
  - `matches_blacklist(cmd)`: Check if command is blacklisted
  - `is_destructive(cmd)`: Detect destructive operations (rm -rf, sudo, etc.)
  - `sanitize_command(cmd)`: Remove dangerous flags/redirects
- **Integration**: Used by MCP approval interceptor for Bash tool validation

**5. Audit Logger** (~100 LOC)
- **File**: `plugins/autonomous-dev/lib/mcp_audit_logger.py`
- **Purpose**: Log all auto-approved operations for review
- **Functions**:
  - `log_approval(tool, args, agent, timestamp, result)`: Write to audit log
  - `log_denial(tool, args, agent, reason)`: Log blocked operations
  - `generate_audit_report()`: Summarize auto-approvals for review
- **Integration**: Called by MCP approval interceptor for every decision
- **Security**: Reuse `security_utils.sanitize_for_logging()` to prevent log injection

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Main Context (Human)                  │
│         [Requires manual approval for all tools]        │
└─────────────────────────────────────────────────────────┘
                            │
                    Invokes subagent via Task tool
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Subagent Context (Automated)               │
│  ┌───────────────────────────────────────────────────┐  │
│  │        MCP Approval Interceptor                   │  │
│  │  1. Detect subagent context                       │  │
│  │  2. Load auto_approve_policy.json                 │  │
│  │  3. Validate tool call against policy             │  │
│  │  4. Auto-approve or deny                          │  │
│  │  5. Audit log decision                            │  │
│  └───────────────────────────────────────────────────┘  │
│                            │                            │
│         ┌──────────────────┼──────────────────┐         │
│         ↓                  ↓                  ↓         │
│    WebSearch            Bash              Read/Write    │
│  [Auto-approved]   [Whitelist check]   [Path validation]│
└─────────────────────────────────────────────────────────┘
                            │
                    Audit log to logs/mcp_auto_approve.log
```

### Integration Points

**1. Claude Code MCP Layer**:
- **Challenge**: Exact integration point depends on Claude Code internals (not fully documented)
- **Approach**: Research MCP protocol specification and Claude Code source
- **Alternative**: If direct integration not possible, implement via wrapper script that intercepts tool calls

**2. Subagent Invocation** (existing pattern):
```markdown
# From commands/auto-implement.md
<Task>
name: researcher
agent_file_path: /absolute/path/to/plugins/autonomous-dev/agents/researcher.md
</Task>
```
- **Integration**: Detect `<Task>` tool invocation as trigger for subagent context

**3. Security Utils** (existing library):
```python
# Reuse existing path validation
from plugins.autonomous_dev.lib.security_utils import (
    validate_path,
    sanitize_for_logging
)
```

**4. Audit Logging** (existing pattern):
```python
# Similar to auto_git_workflow.py audit logging
audit_log_path = logs_dir / "mcp_auto_approve.log"
with open(audit_log_path, "a") as f:
    f.write(f"[{timestamp}] APPROVED {tool} by {agent}: {args}\n")
```

### Estimated Complexity

**Overall**: Medium-High

**Breakdown**:
- MCP Configuration Schema: Low (JSON schema definition)
- MCP Approval Interceptor: High (requires understanding Claude Code internals)
- Subagent Context Detector: Medium (pattern matching on Task tool)
- Command Validator: Medium (regex compilation and matching)
- Audit Logger: Low (file I/O with existing patterns)

**Unknowns**:
- Claude Code MCP integration point (may require research/experimentation)
- Performance impact of approval interception (may need optimization)

### Rollout Plan

**Phase 1: Research & Prototyping** (1-2 weeks)
- Research Claude Code MCP protocol and integration points
- Prototype approval interceptor with simple whitelist
- Test with single subagent (researcher) and WebSearch tool
- Validate audit logging works correctly

**Phase 2: Core Implementation** (2-3 weeks)
- Implement full MCP approval interceptor
- Build command validator with regex whitelist/blacklist
- Add path validation for Read/Write tools
- Implement subagent context detection
- Write comprehensive test suite

**Phase 3: Integration & Testing** (1-2 weeks)
- Integrate with `/auto-implement` workflow
- Test with all 7 core workflow agents
- Validate performance improvement (measure context reduction)
- Security audit (penetration testing of whitelist/blacklist)

**Phase 4: Rollout & Documentation** (1 week)
- Update README with auto-approval configuration
- Add troubleshooting guide for permission issues
- Create migration guide from `--dangerously-skip-permissions`
- Release as optional feature (default: disabled)

## Acceptance Criteria

### Functional Requirements
- [ ] MCP approval interceptor correctly identifies subagent contexts (100% accuracy on test suite)
- [ ] WebSearch tool auto-approved for all subagents (no prompts)
- [ ] Read tool auto-approved for all paths except blacklisted directories (.git/, .env, etc.)
- [ ] Write tool auto-approved with path validation (blocked for sensitive paths)
- [ ] Bash tool auto-approved only for whitelisted commands (pytest, git status, etc.)
- [ ] Bash tool denies destructive commands (rm -rf, sudo, git push --force)
- [ ] Main context still requires manual approval (subagent-only enforcement)
- [ ] Configuration loaded from `.mcp/auto_approve_policy.json` (JSON schema)

### Security Requirements
- [ ] All auto-approved operations logged to `logs/mcp_auto_approve.log` with timestamp, agent, tool, args
- [ ] Path validation using `security_utils.validate_path()` for all Read/Write operations
- [ ] Command validation prevents CWE-78 (OS Command Injection) via regex whitelist
- [ ] Audit log sanitized to prevent CWE-117 (Log Injection)
- [ ] Circuit breaker disables auto-approval after 10 consecutive denials (potential attack)
- [ ] No secrets logged (API keys, passwords filtered from audit log)
- [ ] Security audit completed (penetration testing of whitelist/blacklist bypass attempts)

### Performance Requirements
- [ ] Context reduction measured: Before/after comparison shows 15-25% reduction in permission prompt overhead
- [ ] Approval latency: Interceptor adds <50ms overhead per tool call
- [ ] `/auto-implement` workflow time reduced by 2-4 minutes (8-12% improvement)
- [ ] Audit log rotation implemented (max 10MB per file, keep last 5 files)

### Quality Requirements
- [ ] Test coverage ≥80% for all new components
- [ ] Unit tests for command validator (50+ test cases covering whitelist/blacklist edge cases)
- [ ] Integration tests for approval interceptor (test with all 7 core workflow agents)
- [ ] Security tests for path validation (CWE-22, CWE-73 attack vectors)
- [ ] Documentation updated: README, troubleshooting guide, migration guide

### Documentation Requirements
- [ ] `.mcp/auto_approve_policy.json` schema documented with examples
- [ ] README section added: "MCP Auto-Approval Configuration"
- [ ] Troubleshooting guide: "Permission Denied Errors" section
- [ ] Migration guide from `--dangerously-skip-permissions` to auto-approval
- [ ] Security considerations documented (what to whitelist/blacklist and why)

## References

### Relevant Code Files
- `plugins/autonomous-dev/commands/auto-implement.md` - Subagent invocation pattern (Task tool)
- `plugins/autonomous-dev/hooks/auto_git_workflow.py` - Subagent detection logic (CORE_WORKFLOW_AGENTS)
- `plugins/autonomous-dev/lib/security_utils.py` - Path validation and audit logging (reusable for MCP)
- `plugins/autonomous-dev/agents/*.md` - Tool usage patterns (WebSearch, Bash, Read, Write counts)
- `.mcp/config.json` - Current MCP configuration (filesystem, shell, git, python)

### Documentation
- [PROJECT.md](.claude/PROJECT.md) - Project goals and constraints
- [docs/PERFORMANCE.md](docs/PERFORMANCE.md) - Performance baseline and optimization targets (Issue #46)
- [docs/SECURITY.md](docs/SECURITY.md) - Security audit and hardening guidance

### External Resources
- [Claude Code MCP Documentation](https://docs.anthropic.com/claude-code/mcp) (TBD - research needed)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [CWE-73: External Control of File Name or Path](https://cwe.mitre.org/data/definitions/73.html)
- [CWE-117: Improper Output Neutralization for Logs](https://cwe.mitre.org/data/definitions/117.html)

### Related Issues
- Issue #46: Pipeline performance optimization (auto-approval would save 2-4 minutes)
- Issue #61: Zero Manual Git Operations (similar automation philosophy)
- Issue #58: Automatic git operations integration (precedent for safe automation)

## Alternatives Considered

### Alternative 1: Session-Based Approval
**Description**: Prompt once per session, then auto-approve all subsequent calls
**Pros**: Simple implementation, no complex whitelist logic
**Cons**: Less granular control, potential security risk if session compromised
**Decision**: Rejected - too broad, doesn't prevent destructive commands

### Alternative 2: Agent-Specific Whitelists
**Description**: Each agent has its own whitelist (researcher can WebSearch, implementer can Bash, etc.)
**Pros**: Fine-grained control, principle of least privilege
**Cons**: High maintenance overhead, complex configuration
**Decision**: Deferred - start with tool-based whitelist, consider per-agent in v2.0

### Alternative 3: LLM-Based Approval
**Description**: Use Claude to evaluate if tool call is safe before auto-approving
**Pros**: Adaptive, can handle novel patterns
**Cons**: Adds latency, requires additional API calls, potential for hallucination
**Decision**: Rejected - too slow, defeats purpose of auto-approval

## Dependencies

### External Dependencies
- Claude Code MCP protocol documentation (research needed)
- Access to Claude Code source code or API for interception (TBD)

### Internal Dependencies
- `security_utils.py` must support new validation patterns (minimal changes expected)
- Audit logging infrastructure must handle high volume (10-20 logs per agent)

### Blocking Issues
- **BLOCKER**: Need to understand Claude Code MCP integration point
  - **Mitigation**: Research phase dedicated to MCP protocol exploration
  - **Timeline**: 1 week for research, escalate if integration not possible

## Breaking Changes

**None** - This is an additive feature. Existing behavior (manual approval) remains default.

**Migration Path**:
1. Users currently using `--dangerously-skip-permissions` can migrate to auto-approval policy
2. Migration guide will provide JSON config template
3. Default config disables auto-approval (opt-in feature)

## Success Metrics

**Primary Metrics**:
- **Context Reduction**: 15-25% reduction in permission prompt overhead
- **Time Savings**: 2-4 minutes saved per `/auto-implement` workflow
- **Approval Latency**: <50ms overhead per tool call

**Secondary Metrics**:
- **Adoption Rate**: % of users who enable auto-approval (target: 50% within 3 months)
- **Security Incidents**: Zero breaches via auto-approved commands (target: 0)
- **False Denials**: <5% of legitimate commands blocked by whitelist

**Monitoring**:
- Audit log analysis: Track approval/denial rates per tool
- Performance profiling: Measure impact on `/auto-implement` baseline
- User feedback: Survey on UX improvement and friction reduction

---

**Estimated Effort**: 4-6 weeks (1 week research, 2-3 weeks implementation, 1-2 weeks testing, 1 week rollout)

**Priority**: Medium-High (performance optimization, UX improvement, removes `--dangerously-skip-permissions` dependency)

**Risk Level**: Medium (requires Claude Code internals research, security validation critical)
