# Permission Batching System

**Reduces permission prompts from ~50 to <10 per feature (80% reduction)**

---

## Problem

Permission fatigue during autonomous workflows:
- ~50 permission prompts per `/auto-implement` feature
- Constant interruptions for safe read operations
- Users forced to use `--dangerously-skip-permissions` (unsafe)

## Solution

Intelligent permission classification and batching:
- **SAFE operations**: Auto-approved (Read, Grep, Glob within project)
- **BOUNDARY operations**: Batch approved (Write to src/tests/docs)
- **SENSITIVE operations**: Always prompt (Bash, config files)

## Quick Start

### 1. Enable Permission Batching

Copy the template to your project:

```bash
cp plugins/autonomous-dev/templates/settings.permission-batching.json .claude/settings.local.json
```

### 2. Restart Claude Code

**CRITICAL**: Full restart required (not `/exit`)

```bash
# Mac: Cmd+Q
# Windows/Linux: Ctrl+Q
# Wait 5 seconds
# Restart Claude Code
```

### 3. Verify It's Working

Run `/auto-implement` and observe:
- Read-only agents (researcher, planner, reviewer): **Zero prompts** ✅
- Write agents (implementer, doc-master): **<5 prompts** ✅
- Total prompts per feature: **<10** (vs ~50 before)

---

## How It Works

### Permission Classification

**SAFE** (Auto-approve):
- ✅ Read operations within `src/`, `tests/`, `docs/`, `plugins/`, `scripts/`
- ✅ Grep/Glob operations (always read-only)
- ✅ Bash read-only commands: `ls`, `cat`, `grep`, `echo`, `pwd`

**BOUNDARY** (Batch approval):
- ⚠️ Write operations to `src/`, `tests/`, `docs/`, `plugins/`
- ⚠️ Edit operations in project directories

**SENSITIVE** (Always prompt):
- 🔴 `.env` files (secrets)
- 🔴 `.claude/settings.local.json` (configuration)
- 🔴 `.git/` directory (version control)
- 🔴 System directories: `/etc/`, `/bin/`, `/usr/`
- 🔴 Bash system commands: `rm`, `git`, `sudo`, etc.

### Security Audit

All auto-approved operations are logged:

```bash
# View audit log
cat logs/permission_audit.log

# Example entry:
{
  "timestamp": "2025-11-11T12:00:00",
  "event": "auto_approved",
  "tool": "Read",
  "params": {"file_path": "src/main.py"},
  "level": "safe"
}
```

---

## Configuration

Edit `.claude/settings.local.json`:

```json
{
  "permissionBatching": {
    "enabled": true,                    // Master switch
    "autoApproveSafeReads": true,       // Auto-approve Read/Grep/Glob
    "autoApproveProjectWrites": true,   // Auto-approve Write to src/tests/docs
    "batchWindowSeconds": 5             // Batch related ops within 5 seconds
  }
}
```

### Options

**`enabled`** (default: `false`):
- `true`: Permission batching active
- `false`: Default Claude Code behavior (prompt for everything)

**`autoApproveSafeReads`** (default: `true`):
- `true`: Auto-approve Read/Grep/Glob within project
- `false`: Prompt for all reads

**`autoApproveProjectWrites`** (default: `true`):
- `true`: Auto-approve Write/Edit to `src/`, `tests/`, `docs/`
- `false`: Prompt for all writes

**`batchWindowSeconds`** (default: `5`):
- Batch similar operations within this window
- Higher = more batching, fewer prompts
- Lower = more control, more prompts

---

## Use Cases

### Use Case 1: Read-Only Agents

**Before** (without batching):
```
🤖 researcher agent running...
❓ Approve Read src/main.py? (y/n)
❓ Approve Read src/utils.py? (y/n)
❓ Approve Read tests/test_main.py? (y/n)
... (20 more prompts)
```

**After** (with batching):
```
🤖 researcher agent running...
✅ Auto-approved 23 read operations
✅ Agent completed
```

### Use Case 2: Implementation Agents

**Before** (without batching):
```
🤖 implementer agent running...
❓ Approve Write src/new_feature.py? (y/n)
❓ Approve Write tests/test_new_feature.py? (y/n)
❓ Approve Edit src/main.py? (y/n)
... (15 more prompts)
```

**After** (with batching):
```
🤖 implementer agent running...
✅ Auto-approved 3 write operations to src/
✅ Auto-approved 2 write operations to tests/
❓ Approve Bash command: pytest tests/ ? (y/n)  # Still prompts (sensitive)
✅ Agent completed
```

### Use Case 3: Security-Sensitive Operations

**Always prompts** (regardless of batching):
```
🤖 security-auditor agent running...
✅ Auto-approved 5 read operations
❓ Approve Bash command: grep -r "password" . ? (y/n)  # Prompts (sensitive command)
✅ Agent completed
```

---

## Troubleshooting

### Batching Not Working

**Symptom**: Still getting ~50 prompts per feature

**Solutions**:

1. **Check settings file exists**:
   ```bash
   ls -la .claude/settings.local.json
   # Should exist
   ```

2. **Verify `enabled: true`**:
   ```bash
   cat .claude/settings.local.json | grep enabled
   # Should show: "enabled": true
   ```

3. **Full restart Claude Code**:
   - Not `/exit` - that doesn't reload settings
   - Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
   - Wait 5 seconds
   - Restart

4. **Check audit log**:
   ```bash
   cat logs/permission_audit.log | tail -20
   # Should show auto_approved entries
   ```

### Too Many Auto-Approvals (Security Concern)

**Symptom**: Worried about auto-approving too much

**Solutions**:

1. **Disable project writes**:
   ```json
   {
     "permissionBatching": {
       "enabled": true,
       "autoApproveSafeReads": true,
       "autoApproveProjectWrites": false  // Still prompt for writes
     }
   }
   ```

2. **Review audit log regularly**:
   ```bash
   cat logs/permission_audit.log | jq '.event' | sort | uniq -c
   # Shows breakdown of auto-approved operations
   ```

3. **Disable batching for specific workflows**:
   ```json
   {
     "permissionBatching": {
       "enabled": false  // Back to default behavior
     }
   }
   ```

### Sensitive File Incorrectly Classified

**Symptom**: File should be sensitive but is auto-approved

**Solution**: Edit `lib/permission_classifier.py`:

```python
# Add to sensitive_paths in __init__
self.sensitive_paths = {
    # ... existing paths ...
    self.project_root / "your/sensitive/file.txt",  # Add this
}
```

Then restart Claude Code.

---

## Performance Impact

**Before Batching**:
- Permission prompts: ~50 per feature
- User interruptions: ~50 per feature
- Time spent on approvals: ~5-10 minutes per feature

**After Batching**:
- Permission prompts: <10 per feature (80% reduction)
- User interruptions: <10 per feature (80% reduction)
- Time spent on approvals: <1 minute per feature (90% reduction)

**Time Savings**: ~4-9 minutes per feature

---

## Security Considerations

### What's Safe to Auto-Approve?

**✅ Safe**:
- Reading project source code
- Searching project files (Grep/Glob)
- Listing directory contents

**Why**: Read-only operations within project scope can't cause harm.

### What's Not Safe to Auto-Approve?

**🔴 Not Safe**:
- Writing to system directories (`/etc`, `/bin`)
- Modifying config files (`.env`, settings)
- Bash commands that modify system (`rm`, `sudo`, `git`)
- Operations outside project directory

**Why**: These can cause data loss, security breaches, or system instability.

### Audit Trail

All auto-approved operations are logged to `logs/permission_audit.log`:

```bash
# Example audit entry
{
  "timestamp": "2025-11-11T12:00:00.123Z",
  "event": "auto_approved",
  "tool": "Read",
  "params": {"file_path": "/project/src/main.py"},
  "level": "safe",
  "user": "username"
}
```

**Review regularly**:
```bash
# Last 50 auto-approved operations
cat logs/permission_audit.log | grep auto_approved | tail -50 | jq .
```

---

## Comparison to `--dangerously-skip-permissions`

### The Unsafe Way (Don't Do This)

```bash
# BAD: Skip all permissions (dangerous)
claude --dangerously-skip-permissions
```

**Problems**:
- ❌ No audit trail
- ❌ No classification (skips everything)
- ❌ Can write to `/etc`, delete files, etc.
- ❌ Security vulnerability

### The Safe Way (Use Permission Batching)

```bash
# GOOD: Enable permission batching (safe)
# 1. Copy template
cp plugins/autonomous-dev/templates/settings.permission-batching.json .claude/settings.local.json

# 2. Restart Claude Code
# 3. Run workflows normally
```

**Benefits**:
- ✅ Full audit trail in `logs/permission_audit.log`
- ✅ Intelligent classification (SAFE/BOUNDARY/SENSITIVE)
- ✅ Still prompts for dangerous operations
- ✅ Security maintained

---

## FAQ

**Q: Will this work with all commands or just /auto-implement?**
A: Works with **all workflows**. Any tool use goes through the permission classifier.

**Q: Can I customize which directories are safe?**
A: Yes. Edit `lib/permission_classifier.py` and add to `safe_paths` or `boundary_paths`.

**Q: Does this work on Windows?**
A: Yes, but sensitive paths are Unix-focused. Windows users may need to customize `sensitive_paths`.

**Q: Will this break my existing workflows?**
A: No. If batching fails (hook error, etc.), it falls back to default Claude Code behavior.

**Q: Can I disable batching for specific tools?**
A: Yes. Modify the `classify()` method in `lib/permission_classifier.py` to return `PermissionLevel.SENSITIVE` for specific tools.

**Q: How do I know what was auto-approved?**
A: Check `logs/permission_audit.log` - every auto-approved operation is logged.

---

## Related

- Issue #60: Permission Batching System (implementation)
- Issue #55: Sandbox Execution (Phases 2-4 rejected - this is Phase 1)
- Issue #41: Fully Autonomous Execution (complete)

---

**Last Updated**: 2025-11-11
**Version**: v3.12.0 (Permission Batching System)
