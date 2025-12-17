# Tool Auto-Approval Research

> **Issue Reference**: Issue #142, v3.40.0+
> **Research Date**: 2025-12-17
> **Status**: Active

## Overview

Research and design decisions behind tool auto-approval in autonomous-dev. The plugin reduces permission prompts from 50+ to near-zero during development while maintaining security.

---

## Key Findings

### 1. The Permission Prompt Problem

**Problem**: Claude Code prompts for permission on every tool use.

**Statistics** (typical /auto-implement run):
- Tool calls: 50-100 per feature
- Permission prompts without auto-approval: 50-100
- Time spent on prompts: 10-15 minutes
- Developer frustration: High

**Goal**: Reduce prompts to zero for safe operations.

### 2. Blacklist-First Policy (v2.0)

**Design choice**: Approve everything EXCEPT known dangerous patterns.

```json
{
  "policy_version": "2.0",
  "mode": "permissive",
  "blacklist": [
    "rm -rf /",
    "rm -rf ~",
    "sudo rm",
    "chmod 777",
    "git push --force",
    "git push -f",
    "curl | bash",
    "wget | bash",
    "npm publish",
    "pip upload"
  ],
  "whitelist": []
}
```

**Rationale**: Development requires flexibility. Block only truly dangerous operations.

### 3. Security Layers

**Multi-layer protection** (auto-approval is ONE layer):

```
Layer 1: MCP Security (path traversal, injection)
Layer 2: User Consent (first-run approval)
Layer 3: Tool Whitelist (agent frontmatter)
Layer 4: Auto-Approval (blacklist patterns)   ← This system
Layer 5: Audit Logging
Layer 6: Circuit Breaker
```

**Even if auto-approval passes, other layers can block.**

### 4. Context-Aware Approval

**Main conversation vs Subagents**:

| Context | Default | Override |
|---------|---------|----------|
| Main conversation | Ask | MCP_AUTO_APPROVE=true |
| Subagent execution | Auto-approve | MCP_AUTO_APPROVE=subagent_only |

**Rationale**: Subagents are controlled by main agent, lower risk.

### 5. Comprehensive Blacklist Categories

| Category | Patterns Blocked | Reason |
|----------|-----------------|--------|
| **Destructive** | `rm -rf /`, `rm -rf ~` | Data loss |
| **Privilege** | `sudo`, `su`, `chmod 777` | Security escalation |
| **Force Push** | `git push --force`, `git push -f` | History destruction |
| **Publishing** | `npm publish`, `pip upload` | Unauthorized release |
| **Shell Injection** | `curl | bash`, `wget | sh` | Remote code execution |
| **Credentials** | Commands with passwords | Exposure risk |

---

## Design Decisions

### Why Blacklist-First?

**Considered alternatives**:
1. Whitelist-first (rejected - too restrictive)
2. No auto-approval (rejected - too many prompts)
3. Blacklist-first (chosen - balance of security and usability)

**Comparison**:

| Approach | Prompts | Security | Developer Experience |
|----------|---------|----------|---------------------|
| No auto-approval | 50-100 | Maximum | Poor |
| Whitelist | 10-20 | High | Moderate |
| Blacklist | 0-5 | High | Excellent |

### Why Environment Variable Control?

**Flexibility requirements**:
- Different settings for dev vs CI
- Easy toggle without code changes
- Batch mode needs zero prompts

**Implementation**:
```bash
# Development (permissive)
MCP_AUTO_APPROVE=true

# CI/CD (strict)
MCP_AUTO_APPROVE=false

# Hybrid (subagents only)
MCP_AUTO_APPROVE=subagent_only
```

### Why Audit Logging?

**Problem**: Auto-approval reduces visibility.

**Solution**: Log all decisions for forensics.

```json
{
  "timestamp": "2025-12-17T08:30:00Z",
  "tool": "Bash",
  "command": "pytest tests/",
  "decision": "auto_approved",
  "reason": "Not in blacklist",
  "context": "subagent:implementer"
}
```

---

## Auto-Approval Flow

```
Tool Request: Bash("pytest tests/")
         ↓
┌─────────────────────────────────────┐
│ Check MCP_AUTO_APPROVE setting      │
│ - true: Proceed to validation       │
│ - false: Return "ask"               │
│ - subagent_only: Check context      │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ Load auto_approve_policy.json       │
│ - Get blacklist patterns            │
│ - Get whitelist (if conservative)   │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ Check against blacklist             │
│ - Match found: Return "deny"        │
│ - No match: Return "allow"          │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ Audit log the decision              │
│ - Tool, command, decision, reason   │
└─────────────────────────────────────┘
```

---

## Policy Configuration

### Permissive Mode (Default)

```json
{
  "policy_version": "2.0",
  "mode": "permissive",
  "blacklist": [
    {"pattern": "rm -rf /", "reason": "Root deletion"},
    {"pattern": "rm -rf ~", "reason": "Home deletion"},
    {"pattern": "sudo", "reason": "Privilege escalation"},
    {"pattern": "git push --force", "reason": "Force push"},
    {"pattern": "curl.*\\|.*bash", "reason": "Remote execution"}
  ],
  "whitelist": []
}
```

### Conservative Mode (Optional)

```json
{
  "policy_version": "2.0",
  "mode": "conservative",
  "blacklist": [],
  "whitelist": [
    {"pattern": "git status", "reason": "Safe read-only"},
    {"pattern": "git diff", "reason": "Safe read-only"},
    {"pattern": "pytest", "reason": "Test execution"},
    {"pattern": "python -m", "reason": "Module execution"}
  ]
}
```

---

## Source References

- **OWASP Command Injection**: Prevention techniques
- **Principle of Least Privilege**: Security design pattern
- **Defense in Depth**: Multi-layer security architecture
- **Claude Code Documentation**: Permission system design

---

## Implementation Notes

### Applied to autonomous-dev

1. **unified_pre_tool.py**: Auto-approval dispatcher
2. **auto_approve_policy.json**: Blacklist configuration
3. **Environment variables**: Runtime control
4. **Audit logging**: Decision tracking

### File Locations

```
plugins/autonomous-dev/
├── hooks/
│   └── unified_pre_tool.py        # Approval logic
├── config/
│   └── auto_approve_policy.json   # Blacklist/whitelist
└── docs/
    └── TOOL-AUTO-APPROVAL.md      # User documentation
```

---

## Related Issues

- **Issue #142**: Tool auto-approval implementation
- **Issue #145**: Command security frontmatter

---

**Generated by**: Research persistence (Issue #151)
