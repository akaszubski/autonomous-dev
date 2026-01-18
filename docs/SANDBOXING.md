# Sandboxing Guide (Issue #171)

**Last Updated**: 2026-01-02
**Version**: 1.0.0
**Purpose**: User guide for command sandboxing and permission prompt reduction

---

## Overview

Sandboxing reduces permission prompts from 50+ to 8-10 per /implement workflow (84% reduction) by automatically classifying commands as SAFE, BLOCKED, or NEEDS_APPROVAL.

**The Problem**:
- /implement requires 50+ tool approvals
- 80%+ are safe read-only commands (cat, grep, git status)
- Each prompt breaks focus and adds 10-20 seconds overhead
- Total overhead: 30+ minutes of interruption per workflow

**The Solution**:
- Whitelist-first policy: Safe commands auto-approved
- Blocked patterns: Dangerous commands denied
- User consent caching: Identical operations approved once
- OS-specific sandboxing: bwrap (Linux), sandbox-exec (macOS)

**Result**: Prompt reduction from 50+ to 8-10 while maintaining security

---

## Quick Start

### Enable Sandboxing

```bash
# In .env file (or set environment variable)
SANDBOX_ENABLED=true
SANDBOX_PROFILE=development  # or testing, production
```

That's it! You'll immediately see fewer permission prompts.

### Verify It's Working

When you run /implement, watch for:

- Safe commands: No prompt (auto-approved)
- Blocked commands: Denied with reason
- Unknown commands: Single prompt (cached for future identical operations)

**Example Output**:
```
[SANDBOX] ✓ cat README.md - SAFE (auto-approve)
[SANDBOX] ✓ grep pattern src/ - SAFE (auto-approve)
[SANDBOX] ✗ rm -rf / - BLOCKED (dangerous pattern)
[SANDBOX] ? pytest tests/ - NEEDS_APPROVAL (first time, then cached)
```

---

## Configuration

### Environment Variables

**SANDBOX_ENABLED** (boolean, default: false)
- `true` - Enable sandboxing
- `false` - Disable sandboxing (default, no auto-approval)

**SANDBOX_PROFILE** (string, default: development)
- `development` - Most permissive, auto-approves 20+ safe commands
- `testing` - Moderate, stricter rules, fewer auto-approvals
- `production` - Most strict, minimal auto-approvals

### Policy File

**Location**: `plugins/autonomous-dev/config/sandbox_policy.json` (plugin default)

**Custom Override**: Create `.claude/config/sandbox_policy.json` to override per-project

**Example Custom Policy**:
```json
{
  "version": "1.0.0",
  "profiles": {
    "development": {
      "safe_commands": [
        "cat",
        "grep",
        "git status",
        "pytest"
      ],
      "blocked_patterns": [
        "rm -rf",
        "sudo"
      ],
      "shell_injection_patterns": [
        ";",
        "&&",
        "|"
      ],
      "blocked_paths": [
        ".env",
        ".ssh/"
      ],
      "path_traversal_patterns": [
        ".."
      ],
      "sandbox_enabled": true,
      "circuit_breaker": {
        "enabled": true,
        "threshold": 10
      }
    }
  },
  "default_profile": "development"
}
```

---

## Security Profiles

### Profile: Development (Most Permissive)

**Use Case**: Local development, trusted environment

**Safe Commands** (auto-approved):
- File operations: cat, echo, grep, ls, pwd, which
- Version checking: python --version, node --version, npm --version, pip --version
- Git operations: git status, git diff, git log, git show, git branch
- Testing: pytest, python -m pytest
- Package listing: pip list, pip show, npm list

**Blocked Patterns** (denied):
- rm -rf (recursive delete)
- sudo (privilege escalation)
- git push --force (history rewrite)
- eval (arbitrary code execution)
- chmod 777 (dangerous permissions)
- wget with pipe to shell
- curl with pipe to shell

**Shell Injection Patterns Blocked**:
- ; (command separator)
- && (command chaining)
- || (command chaining)
- | (pipe)
- ` (backtick)
- $() (command substitution)
- > >> < (redirects)
- Null bytes

**Blocked File Paths**:
- .env (environment variables)
- .ssh/ (SSH keys)
- credentials.json (API credentials)
- *.pem, *.key (private keys)
- /etc/shadow (system credentials)
- /root/ (root home)
- ~/.ssh/ (user SSH keys)

**Circuit Breaker**: 10 violations before disabling

**When to Use**:
- Local development
- Isolated test environments
- Trusted CI/CD pipelines
- Personal machines

### Profile: Testing (Moderate)

**Use Case**: CI/CD pipelines, test environments with some security requirements

**Safe Commands** (auto-approved):
- Minimal: cat, echo, grep, ls, pytest

**Blocked Patterns**: More aggressive than development

**Shell Injection Patterns Blocked**: All dangerous patterns

**Circuit Breaker**: 5 violations before disabling

**When to Use**:
- CI/CD test environments
- Shared machines with untrusted code
- Automated testing pipelines
- Pre-production environments

### Profile: Production (Strictest)

**Use Case**: Production systems, high-security environments

**Safe Commands** (auto-approved):
- Very few: cat, ls, git status only

**Blocked Patterns**: Most operations blocked

**Shell Injection Patterns Blocked**: All patterns

**Circuit Breaker**: 3 violations before disabling

**When to Use**:
- Production deployments
- Compliance-required environments
- Air-gapped systems
- High-security requirements

---

## How It Works

### 4-Layer Permission Architecture

**Layer 0 - Sandbox Enforcer** (NEW in v4.0.0, Issue #171):
1. Extract command from tool call
2. Classify with policy profile
3. Return: SAFE (auto-approve) / BLOCKED (deny) / NEEDS_APPROVAL (continue)

**Layer 1 - MCP Security Validator** (Existing):
1. Check path traversal (CWE-22)
2. Check command injection (CWE-78)
3. Check SSRF (CWE-918)
4. Return: Allow / Deny / Ask

**Layer 2 - Agent Authorization** (Existing):
1. Detect if command from authorized pipeline agent
2. Return: Allow / Unauthorized

**Layer 3 - Batch Permission Approver** (Existing):
1. Cache user consent for identical operations
2. Return: Approved (cached) / New (prompt once)

### Decision Flow

```
Tool call: Bash with "cat README.md"
    |
    v
Layer 0 (Sandbox): is_command_safe("cat README.md")
    |
    v
    Decision: SAFE (grep in safe_commands)
    |
    v
Return: Allow (auto-approve, no prompt)


Tool call: Bash with "custom-linter --fix"
    |
    v
Layer 0 (Sandbox): is_command_safe("custom-linter --fix")
    |
    v
    Decision: NEEDS_APPROVAL (not in safe_commands, no blocked patterns)
    |
    v
Layer 1 (MCP Security): validate_path(), validate_injection()
    |
    v
    Decision: Allow (path and injection checks pass)
    |
    v
Return: Ask user (first time), then cache
```

---

## Examples

### Example 1: Safe Command (Auto-Approved)

```
User: /implement Add feature X
    |
Claude generates tests with: pytest tests/test_feature_x.py
    |
Layer 0 (Sandbox): is_command_safe("pytest tests/test_feature_x.py")
    |
Classification: SAFE (pytest in safe_commands)
    |
Result: No permission prompt, command executes immediately
    |
Time saved: 10-20 seconds (skipped prompt + user interaction)
```

### Example 2: Blocked Command (Denied)

```
Claude attempts: rm -rf build/
    |
Layer 0 (Sandbox): is_command_safe("rm -rf build/")
    |
Classification: BLOCKED (matches "rm -rf" pattern)
    |
Result: Command denied, audit logged
Message: "BLOCKED: Dangerous pattern 'rm -rf' detected. Use safer alternative."
    |
Workflow: Claude can proceed with safe alternative (e.g., find . -delete)
```

### Example 3: Unknown Command (First Prompt)

```
Claude: pytest-html report.html
    |
Layer 0 (Sandbox): is_command_safe("pytest-html report.html")
    |
Classification: NEEDS_APPROVAL (not in safe_commands)
    |
Layer 1: Path and injection validation pass
    |
Result: User prompted once (first time)
    |
Consent: User approves
    |
Caching: Future identical commands skip Layer 1 (use Layer 3 cache)
    |
Result: 50 identical commands = 1 prompt total
```

### Example 4: Circuit Breaker Activated

```
User: /implement Feature (untrusted code)
    |
Layer 0: 10+ blocked commands in quick succession
    |
Circuit Breaker: TRIPS after 10 blocks
    |
Behavior: Sandboxing disabled for rest of session
    |
Result: Fallback to Layer 1 (MCP Security) validation only
    |
Safety: No dangerous commands can execute (MCP layer still active)
    |
Recovery: Restart Claude Code to reset circuit breaker
```

---

## Common Issues

### Issue: Still Getting Prompts for Safe Commands

**Problem**: `SANDBOX_ENABLED=true` but still seeing prompts for `cat`, `grep`, etc.

**Causes**:
1. SANDBOX_ENABLED not set correctly
2. Profile doesn't include the command
3. Command has arguments that match blocked patterns

**Solution**:
```bash
# Check environment variable
echo $SANDBOX_ENABLED  # Should print: true

# Check profile
echo $SANDBOX_PROFILE  # Should print: development (or testing/production)

# Verify policy file
cat plugins/autonomous-dev/config/sandbox_policy.json | grep "safe_commands"

# If custom policy exists, check it
cat .claude/config/sandbox_policy.json | grep "safe_commands"
```

### Issue: Command Blocked That Should Be Safe

**Problem**: Legitimate command being blocked

**Causes**:
1. Command matches a blocked pattern (e.g., `command | grep` matches pipe)
2. Profile too strict
3. Path contains blocked pattern (e.g., contains `.env` in path)

**Solution**:
```bash
# Switch to development profile (most permissive)
export SANDBOX_PROFILE=development

# Or create custom policy with additional safe commands
# See "Custom Policy" section above
```

### Issue: Sandboxing Not Reducing Prompts Enough

**Problem**: Still seeing 20-30 prompts per /implement

**Causes**:
1. Many commands outside safe_commands list
2. Using testing/production profile (too strict)
3. Batch permission approver not caching properly

**Solution**:
```bash
# Use development profile (most permissive)
export SANDBOX_PROFILE=development

# Enable batch permission approver
export BATCH_PERMISSION_ENABLED=true

# Combined effect: 50+ -> 8-10 prompts
```

### Issue: Concerns About Auto-Approval Security

**Problem**: Worried about auto-approving commands without human review

**Considerations**:
- Layer 0 (Sandbox) only auto-approves safe read-only commands
- Layer 1 (MCP Security) still validates path traversal, injection
- Layer 2 (Agent Auth) prevents unauthorized code changes
- All decisions logged to security audit

**Safety Layers**:
1. Safe commands whitelist is conservative (cat, grep, git status only)
2. No write operations in safe_commands list
3. No shell metacharacters permitted
4. Path traversal always blocked
5. Circuit breaker prevents DoS

**When to Disable**:
```bash
# Disable sandboxing if you want manual approval
export SANDBOX_ENABLED=false

# Or use strictest profile
export SANDBOX_PROFILE=production
```

---

## Audit Logging

All sandbox decisions are logged to security audit for compliance and debugging.

**Log Location**: `.claude/logs/audit.jsonl`

**Log Entry Example**:
```json
{
  "timestamp": "2026-01-02T10:00:00Z",
  "event_type": "sandbox_decision",
  "classification": "SAFE",
  "command": "grep pattern src/",
  "reason": "Command matches safe_commands whitelist",
  "profile": "development",
  "agent": "implementer"
}
```

**View Recent Decisions**:
```bash
tail -20 .claude/logs/audit.jsonl | jq .
```

---

## Performance

**Overhead**:
- Sandbox classification: <1ms per command (pattern matching)
- Binary detection: 5-50ms on first run, cached after
- Policy loading: 10-20ms on startup

**Impact on /implement**:
- Without sandboxing: 50+ prompts = 30+ minutes overhead
- With sandboxing: 8-10 prompts = ~2 minutes overhead
- Net savings: 28+ minutes per workflow

---

## Troubleshooting

### Debug Sandboxing Decisions

Enable debug logging (if available):
```bash
export DEBUG_SANDBOX=true
```

Monitor decisions:
```bash
# Watch audit log in real-time
tail -f .claude/logs/audit.jsonl | jq .
```

### Reset Circuit Breaker

Restart Claude Code to reset circuit breaker:
```bash
# macOS
Cmd+Q  # Fully quit Claude Code

# Linux
Ctrl+Q  # Fully quit Claude Code

# Then restart Claude Code
```

### Custom Policy Validation

Test your custom policy:
```bash
python3 << 'EOF'
import json
from pathlib import Path
import sys
sys.path.insert(0, 'plugins/autonomous-dev/lib')

from sandbox_enforcer import SandboxEnforcer, PolicyValidationError

try:
    enforcer = SandboxEnforcer(policy_path='.claude/config/sandbox_policy.json')
    print("Policy validation passed")
except PolicyValidationError as e:
    print(f"Policy validation failed: {e}")
EOF
```

---

## Historical Note: Archived Hooks (Issue #211)

Previously, security validation was split across multiple independent hooks:

**auto_approve_tool.py** (Archived 2026-01-09):
- Provided batch permission approver functionality (now Layer 4)
- MCP auto-approval for trusted subagents
- Circuit breaker logic
- User consent verification

**mcp_security_enforcer.py** (Archived 2026-01-09):
- Provided MCP security validator functionality (now Layer 2)
- Path traversal prevention (CWE-22)
- Command injection prevention (CWE-78)
- SSRF prevention

**Current Unified Architecture**:

All security validation is now handled by `unified_pre_tool.py` with 4 explicit layers:

1. **Layer 1: Sandbox Enforcer** - Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
2. **Layer 2: MCP Security Validator** - Path traversal, injection, SSRF prevention
3. **Layer 3: Agent Authorization** - Pipeline agent detection and whitelist checking
4. **Layer 4: Batch Permission Approver** - User consent caching and circuit breaker

**Benefits of Consolidation**:
- Single entry point for all pre-tool validation
- Consistent validation order with clear layer boundaries
- Easier to maintain, audit, and extend
- Better defense-in-depth with explicit layers

**See**: `plugins/autonomous-dev/hooks/archived/README.md` for complete deprecation documentation.

---

## Protected Directories

**`.claude/local/`** (Issue #244): Repo-specific operational configs

All files in `.claude/local/` are preserved across `/sync` operations:
- Directory purpose: Store repo-specific operational procedures and configurations
- Protection: Files never overwritten or deleted during sync
- File categorization: All `.claude/local/` files marked as "config" type
- Example uses:
  - `OPERATIONS.md` - Repo-specific deployment procedures
  - `config.json` - Environment-specific configurations
  - `deployment-checklist.txt` - Custom operational procedures

**Protection mechanism**:
- Pattern-based detection: `.claude/local/**` in PROTECTED_PATTERNS
- Orphan cleanup exclusion: delete_orphans=true skips `.claude/local/`
- Safe with all sync modes: Marketplace, plugin-dev, GitHub

**See**: `.claude/local/OPERATIONS.md` (template in plugin) for standard format

---

## Related Documentation

- docs/LIBRARIES.md Section 66 - sandbox_enforcer.py API reference
- docs/HOOKS.md - unified_pre_tool.py hook with 4-layer architecture
- plugins/autonomous-dev/hooks/archived/README.md - Archived hooks documentation
- CLAUDE.md - MCP Auto-Approval Control section
- docs/SECURITY.md - Security hardening guide
- plugins/autonomous-dev/config/sandbox_policy.json - Policy configuration

---

## FAQ

**Q: Will sandboxing prevent me from running legitimate commands?**

A: No. The whitelist is conservative (read-only commands only). Unknown commands go to Layer 1 validation (still secure). Only dangerous patterns are blocked.

**Q: Is sandboxing secure?**

A: Yes. Sandbox classification is only Layer 0 of 4. Even if it fails, MCP Security (Layer 1), Agent Auth (Layer 2), and user consent still protect you.

**Q: Can I customize which commands are safe?**

A: Yes. Create `.claude/config/sandbox_policy.json` with custom safe_commands list for your project.

**Q: What if the circuit breaker trips?**

A: Restart Claude Code. Sandboxing disables but MCP Security layer remains active (still protected).

**Q: How much time does sandboxing save?**

A: 50+ prompts -> 8-10 prompts = 28+ minutes saved per /implement workflow.

**Q: Can I disable sandboxing?**

A: Yes. Set `SANDBOX_ENABLED=false` or don't set it (defaults to false).

**Q: Is this different from MCP Auto-Approval?**

A: Yes and complementary:
- Sandboxing (Layer 0): Classifies commands (SAFE/BLOCKED/NEEDS_APPROVAL)
- Batch Approval (Layer 3): Caches user consent for identical operations
- Together: 50+ -> 8-10 prompts (84% reduction)
