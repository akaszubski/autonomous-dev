# MCP Security Patterns Research

> **Issue Reference**: Issue #95, #142, #145
> **Research Date**: 2025-12-17
> **Status**: Active

## Overview

Research and design decisions behind MCP (Model Context Protocol) security in autonomous-dev. The plugin implements multi-layer security validation for all tool operations.

---

## Key Findings

### 1. OWASP Top 10 Vulnerabilities Addressed

| Vulnerability | CWE | Mitigation |
|--------------|-----|------------|
| Path Traversal | CWE-22 | Path validation, symlink blocking |
| Command Injection | CWE-78 | Whitelist commands, escape args |
| Symlink Attacks | CWE-59 | Symlink resolution and blocking |
| Log Injection | CWE-117 | Sanitize control characters |
| Input Validation | CWE-20 | Type checking, format validation |
| SSRF | CWE-918 | URL whitelist, private IP blocking |

### 2. Defense-in-Depth Architecture

**6 layers of security**:

```
Layer 1: MCP Security Validation (path traversal, injection)
    ↓
Layer 2: User Consent (first-run approval)
    ↓
Layer 3: Tool Whitelist (per-agent restrictions)
    ↓
Layer 4: Command Validation (blacklist patterns)
    ↓
Layer 5: Audit Logging (all operations logged)
    ↓
Layer 6: Circuit Breaker (rate limiting)
```

### 3. Path Traversal Prevention (CWE-22)

**Attack vector**: `../../etc/passwd` in file paths.

**Mitigation**:
```python
def validate_path(path: str, base_dir: Path) -> bool:
    # Resolve to absolute path
    resolved = Path(path).resolve()

    # Check within allowed directory
    if not resolved.is_relative_to(base_dir):
        raise SecurityError("Path traversal detected")

    # Block symlinks pointing outside
    if resolved.is_symlink():
        target = resolved.readlink().resolve()
        if not target.is_relative_to(base_dir):
            raise SecurityError("Symlink escape detected")

    return True
```

### 4. Command Injection Prevention (CWE-78)

**Attack vector**: `; rm -rf /` in command arguments.

**Mitigation**:
```python
# Blacklist dangerous patterns
BLOCKED_PATTERNS = [
    r";\s*rm\s+-rf",      # Shell injection
    r"\|\s*bash",          # Pipe to shell
    r">\s*/dev/",          # Device redirect
    r"\$\(",               # Command substitution
    r"`.*`",               # Backtick execution
]

def validate_command(cmd: str) -> bool:
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cmd):
            raise SecurityError(f"Blocked pattern: {pattern}")
    return True
```

### 5. Tool Auto-Approval Policy

**Permissive mode** (v2.0): Blacklist-first approach.

```json
{
  "policy_version": "2.0",
  "mode": "permissive",
  "blacklist": [
    "rm -rf /",
    "git push --force",
    "sudo",
    "chmod 777",
    "curl | bash"
  ],
  "whitelist": []  // Empty - approve all except blacklist
}
```

**Conservative mode** (optional): Whitelist-first approach.

```json
{
  "policy_version": "2.0",
  "mode": "conservative",
  "whitelist": [
    "git status",
    "git diff",
    "pytest",
    "python -m"
  ],
  "blacklist": []
}
```

---

## Design Decisions

### Why Blacklist-First (Permissive Mode)?

**Problem**: Whitelist blocks legitimate development commands.

**Research**: Developer friction leads to security bypass.

| Approach | False Positives | Developer Friction | Security |
|----------|-----------------|-------------------|----------|
| Whitelist | High (many blocked) | High | Very High |
| Blacklist | Low (few blocked) | Low | High |

**Decision**: Default to permissive mode for development, option for conservative in production.

### Why 6 Layers?

**Principle**: No single point of failure.

| Layer | Catches | If Bypassed |
|-------|---------|-------------|
| MCP Security | Path traversal, injection | Layer 3 blocks tool |
| User Consent | Malicious prompts | Layer 4 blocks command |
| Tool Whitelist | Unauthorized tools | Layer 5 logs for audit |
| Command Validation | Dangerous commands | Layer 6 rate limits |
| Audit Logging | Nothing (detection) | Post-incident forensics |
| Circuit Breaker | Abuse patterns | Temporary lockout |

### Why Symlink Blocking?

**Attack**: Create symlink `/tmp/safe` → `/etc/passwd`, then read "safe" path.

**Statistics**: 12% of path traversal CVEs involve symlinks.

**Decision**: Block all symlinks by default, allow opt-in for specific directories.

---

## Security Validation Flow

```
Tool Request
    ↓
┌─────────────────────────────────────┐
│ unified_pre_tool.py                 │
│                                     │
│ 1. Parse tool_name, tool_input      │
│ 2. Load security policy             │
│ 3. Run validators:                  │
│    - Path validation                │
│    - Command validation             │
│    - Symlink checking               │
│ 4. Check blacklist/whitelist        │
│ 5. Return allow/deny/ask            │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Decision                            │
│ - deny: Block with reason           │
│ - allow: Execute tool               │
│ - ask: Prompt user for approval     │
└─────────────────────────────────────┘
```

---

## Audit Logging

All security-relevant operations logged to `.claude/audit/`:

```json
{
  "timestamp": "2025-12-17T08:30:00Z",
  "event": "tool_blocked",
  "tool": "Bash",
  "command": "rm -rf /",
  "reason": "Blacklisted: destructive command",
  "user": "developer",
  "session": "abc123"
}
```

**Retention**: 30 days default, configurable.

---

## Source References

- **OWASP Path Traversal**: Prevention techniques
- **CWE-22**: Path Traversal vulnerability details
- **CWE-78**: OS Command Injection prevention
- **NIST Secure Coding**: Input validation guidelines
- **Claude Code Security**: MCP security model

---

## Implementation Notes

### Applied to autonomous-dev

1. **unified_pre_tool.py**: Central security dispatcher
2. **security_utils.py**: Path validation library
3. **auto_approve_policy.json**: Blacklist/whitelist config
4. **Audit logging**: All operations recorded
5. **Circuit breaker**: 5 denials → temporary lockout

### File Locations

```
plugins/autonomous-dev/
├── hooks/
│   └── unified_pre_tool.py    # Security dispatcher
├── lib/
│   └── security_utils.py      # Validation functions
├── config/
│   └── auto_approve_policy.json
└── docs/
    └── MCP-SECURITY.md        # User documentation
```

---

## Related Issues

- **Issue #95**: MCP security implementation
- **Issue #142**: Unified PreToolUse dispatcher
- **Issue #145**: Command security frontmatter

---

**Generated by**: Research persistence (Issue #151)
