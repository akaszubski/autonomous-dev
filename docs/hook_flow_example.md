# Hook Flow Examples - How unified_pre_tool_use.py Works

## Example 1: Safe Command (pytest)

### What Claude Wants to Do
```
Tool: "Bash"
Parameters: {"command": "pytest tests/unit/"}
```

### Hook Execution Flow

#### Step 1: Claude Code Calls Your Hook
```python
on_pre_tool_use(
    tool="Bash",
    parameters={"command": "pytest tests/unit/"}
)
```

#### Step 2: MCP Security Check
```python
# Check: Is this an MCP tool (mcp__* pattern)?
tool.startswith("mcp__")  # False - it's "Bash", not "mcp__*"

# Result: Skip MCP security (only for MCP tools), continue to next validator
return None  # Pass through
```

#### Step 3: Auto-Approval Check
```python
# Check: Does MCP_AUTO_APPROVE=true in .env?
get_auto_approval_mode()  # Returns "everywhere" (from your .env)

# Check: Is "pytest tests/unit/" in whitelist?
# Load policy from: config/auto_approve_policy.json
{
  "bash": {
    "whitelist": [
      "pytest*",  # ← MATCH!
      "git status",
      "ls*"
    ]
  }
}

# Result: APPROVED!
return {"approved": true, "reason": "Matches whitelist pattern: pytest*"}
```

#### Step 4: Claude Code Response
```
Hook returned {"approved": true}
→ Skip permission prompt
→ Execute command immediately
→ Log to: logs/tool_auto_approve_audit.log
```

**User Experience:**
- ✅ Zero prompts
- ⚡ Instant execution
- 📝 Audit trail logged

---

## Example 2: Dangerous Command (rm -rf)

### What Claude Wants to Do
```
Tool: "Bash"
Parameters: {"command": "rm -rf /tmp/important-data"}
```

### Hook Execution Flow

#### Step 1: Claude Code Calls Your Hook
```python
on_pre_tool_use(
    tool="Bash",
    parameters={"command": "rm -rf /tmp/important-data"}
)
```

#### Step 2: MCP Security Check
```python
# Is this an MCP tool?
tool.startswith("mcp__")  # False

# Result: Pass through (not an MCP tool)
return None
```

#### Step 3: Auto-Approval Check
```python
# Check: Is "rm -rf /tmp/important-data" in blacklist?
# Load policy from: config/auto_approve_policy.json
{
  "bash": {
    "blacklist": [
      "rm -rf*",  # ← MATCH!
      "sudo*",
      "eval*"
    ]
  }
}

# Result: DENIED!
return {"approved": false, "reason": "Matches blacklist pattern: rm -rf*"}
```

#### Step 4: Claude Code Response
```
Hook returned {"approved": false}
→ Show manual permission prompt to user
→ User must click [Yes] or [No]
→ Log denial to: logs/tool_auto_approve_audit.log
```

**User Experience:**
- 🛑 Manual prompt appears
- 🤔 You decide if you really want this
- 📝 Denial logged for security audit

---

## Example 3: MCP Tool (Reading Sensitive File)

### What Claude Wants to Do
```
Tool: "mcp__filesystem__read"
Parameters: {"path": "/home/user/.ssh/id_rsa"}
```

### Hook Execution Flow

#### Step 1: Claude Code Calls Your Hook
```python
on_pre_tool_use(
    tool="mcp__filesystem__read",
    parameters={"path": "/home/user/.ssh/id_rsa"}
)
```

#### Step 2: MCP Security Check
```python
# Is this an MCP tool?
tool.startswith("mcp__")  # True! This is MCP security territory

# Parse tool format: mcp__category__operation
category = "filesystem"
operation = "read"

# Check: Is "/home/user/.ssh/id_rsa" allowed?
# Load policy from: .mcp/security_policy.json
{
  "filesystem": {
    "read": {
      "allowed_paths": [
        "/home/*/Documents/**",
        "/tmp/**"
      ],
      "denied_paths": [
        "**/.ssh/**",  # ← MATCH!
        "**/.env"
      ]
    }
  }
}

# Result: DENIED by MCP security!
return {"approved": false, "reason": "Path matches denied pattern: **/.ssh/**"}
```

#### Step 3: Auto-Approval Check
```python
# Never reached! MCP security already denied.
# Hook returns immediately from Step 2.
```

#### Step 4: Claude Code Response
```
Hook returned {"approved": false}
→ Show manual permission prompt to user
→ User must click [Yes] or [No]
→ Log security denial to: logs/tool_auto_approve_audit.log
```

**User Experience:**
- 🔒 Security blocked the dangerous path
- 🛑 Manual prompt for sensitive file
- 📝 Security event logged

---

## How Claude Code Discovers Your Hook

### Plugin Registration

When Claude Code starts, it:

1. **Scans installed plugins:**
   ```
   ~/.claude/plugins/marketplaces/autonomous-dev/
   ```

2. **Reads plugin.json:**
   ```json
   {
     "components": {
       "hooks": "./hooks"
     }
   }
   ```

3. **Scans hooks directory:**
   ```bash
   ~/.claude/plugins/.../hooks/
   ├── unified_pre_tool_use.py ✅ Found!
   ├── auto_format.py
   ├── auto_test.py
   └── ...
   ```

4. **Looks for PreToolUse hooks:**
   ```python
   # Claude Code searches each .py file for:
   def on_pre_tool_use(tool: str, parameters: dict) -> dict:
       ...

   # Found in: unified_pre_tool_use.py
   # Registers this function for all tool calls
   ```

5. **Registers the hook:**
   ```
   PreToolUse hooks registered:
   - unified_pre_tool_use.on_pre_tool_use ✅

   (If multiple found, only FIRST one loads → that was your collision!)
   ```

### Hook Lifecycle

```
Claude Code Startup
      ↓
Scan plugins/ for hooks
      ↓
Register: unified_pre_tool_use.on_pre_tool_use()
      ↓
[Claude Code is running]
      ↓
Claude wants to use tool
      ↓
Call: on_pre_tool_use(tool, params)  ← Your hook runs here!
      ↓
Get: {"approved": true/false}
      ↓
If true: Skip prompt, execute
If false: Show prompt to user
```

---

## Why Two Hooks Broke Everything

### Before (Broken)

```
hooks/
├── auto_approve_tool.py          # Has: def on_pre_tool_use(...)
└── mcp_security_enforcer.py      # Also has: def on_pre_tool_use(...)

Claude Code discovers both:
- "Found PreToolUse hook in auto_approve_tool.py"
- "Found PreToolUse hook in mcp_security_enforcer.py"
- "ERROR: Duplicate on_pre_tool_use! Using first one..."

Result: Only ONE hook loads (undefined which one!)
→ Either auto-approval works OR MCP security works, but NOT both
→ In your case, NEITHER worked (hook collision → no hook loaded)
```

### After (Fixed)

```
hooks/
├── unified_pre_tool_use.py       # Has: def on_pre_tool_use(...) ✅
├── auto_approve_tool.py.disabled # Disabled (no .py extension)
└── mcp_security_enforcer.py.disabled # Disabled (no .py extension)

Claude Code discovers:
- "Found PreToolUse hook in unified_pre_tool_use.py"
- "Registered: unified_pre_tool_use.on_pre_tool_use"

Result: ONE hook that chains BOTH validators
→ MCP security runs first (for mcp__* tools)
→ Auto-approval runs second (for all tools)
→ Both systems work together harmoniously
```

---

## Configuration Files That Control Behavior

### 1. Environment Variables (.env)
```bash
# Enable/disable auto-approval
MCP_AUTO_APPROVE=true              # everywhere (main + subagents)
MCP_AUTO_APPROVE=subagent_only     # only in subagents
MCP_AUTO_APPROVE=false             # disabled

# Enable/disable MCP security
MCP_SECURITY_ENABLED=true          # default
```

### 2. Auto-Approval Policy (config/auto_approve_policy.json)
```json
{
  "bash": {
    "whitelist": [
      "pytest*",
      "git status",
      "git diff*",
      "ls*"
    ],
    "blacklist": [
      "rm -rf*",
      "sudo*",
      "eval*",
      "curl*|*bash"
    ]
  },
  "agents": {
    "trusted": [
      "researcher",
      "planner",
      "implementer"
    ]
  }
}
```

### 3. MCP Security Policy (.mcp/security_policy.json)
```json
{
  "filesystem": {
    "read": {
      "allowed_paths": [
        "/home/*/Documents/**",
        "/tmp/**"
      ],
      "denied_paths": [
        "**/.ssh/**",
        "**/.env",
        "/etc/**"
      ]
    }
  },
  "shell": {
    "allowed_commands": [
      "pytest*",
      "git*"
    ],
    "denied_commands": [
      "rm -rf*",
      "sudo*"
    ]
  }
}
```

### 4. User Consent (~/.autonomous-dev/user_state.json)
```json
{
  "first_run_complete": true,
  "preferences": {
    "mcp_auto_approve_enabled": true
  }
}
```

---

## Audit Log Example

See exactly what your hook is doing:

```bash
tail -f logs/tool_auto_approve_audit.log
```

```json
{
  "timestamp": "2025-12-08T19:30:15.123Z",
  "event": "tool_call_approved",
  "tool": "Bash",
  "agent": "implementer",
  "command": "pytest tests/unit/",
  "reason": "Matches whitelist pattern: pytest*",
  "status": "approved"
}

{
  "timestamp": "2025-12-08T19:30:16.456Z",
  "event": "tool_call_denied",
  "tool": "Bash",
  "agent": "implementer",
  "command": "rm -rf /tmp/data",
  "reason": "Matches blacklist pattern: rm -rf*",
  "status": "denied",
  "security_risk": true
}

{
  "timestamp": "2025-12-08T19:30:17.789Z",
  "event": "mcp_security_blocked",
  "tool": "mcp__filesystem__read",
  "path": "/home/user/.ssh/id_rsa",
  "reason": "Path matches denied pattern: **/.ssh/**",
  "status": "denied",
  "security_risk": true
}
```

---

## Key Takeaways

1. **PreToolUse Hook = Permission Gatekeeper**
   - Sits between Claude and permission prompts
   - Returns approve/deny before prompt shown
   - If approved → skip prompt, execute immediately

2. **Your Unified Hook Chains Two Validators**
   - MCP Security (for sensitive MCP operations)
   - Auto-Approval (for common tasks)

3. **Claude Code Calls Your Hook Every Single Time**
   - BEFORE every tool execution
   - Your hook decides: auto-approve or manual prompt

4. **Restart Required**
   - Hooks load at Claude Code startup
   - `/exit` doesn't reload hooks
   - Must fully quit (Cmd+Q) and restart

5. **Everything is Logged**
   - Every approval: logs/tool_auto_approve_audit.log
   - Every denial: logs/tool_auto_approve_audit.log
   - Full audit trail for compliance

Does this clarify how the hooks actually intercept permissions? Let me know what's still unclear!
