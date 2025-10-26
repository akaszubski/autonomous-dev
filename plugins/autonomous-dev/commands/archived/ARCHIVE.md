# Archived Commands

**Last Updated**: 2025-10-26

These commands were archived to align with the core philosophy: **"Vibe coding with background enforcement - I speak requirements, Claude delivers professional results in minutes"**

---

## Why Commands Were Archived

**Core Philosophy**:
- ✅ Natural language input → Professional engineering output
- ✅ Background enforcement via hooks (not manual commands)
- ✅ Minimal user intervention
- ✅ Strategic simplicity (4 core commands vs 11)

**Result**: 64% reduction in commands (11 → 4)

---

## Archived Commands

### `/test` - Replaced by Hooks

**Archived Because**: Manual test execution violates background enforcement philosophy

**What Replaced It**:
- `hooks/auto_test.py` - Runs tests automatically at commit
- `hooks/validate_session_quality.py` - Validates test coverage in session files

**Migration**:
```bash
# Before (manual)
/auto-implement "add feature"
/test                          # Manual step

# After (automatic)
/auto-implement "add feature"  # Tests run at commit automatically
```

---

### `/advise` - Replaced by Orchestrator

**Archived Because**: Manual critical thinking step (2-5 min) interrupts vibe coding flow

**What Replaced It**:
- `agents/orchestrator.md` - Validates PROJECT.md alignment automatically
- `hooks/validate_project_alignment.py` - Checks alignment at commit

**Migration**:
```bash
# Before (manual analysis)
/advise "add Redis"            # 2-5 min manual analysis
/auto-implement                # Then implement

# After (automatic validation)
"Add Redis caching"            # orchestrator validates alignment automatically
```

---

### `/align-project` - Replaced by Hooks

**Archived Because**: Manual alignment checking violates background enforcement

**What Replaced It**:
- `hooks/validate_project_alignment.py` - Runs at commit automatically
- `hooks/validate_session_quality.py` - Validates quality markers
- `agents/orchestrator.md` - Checks alignment before feature work

**Migration**:
```bash
# Before (manual)
/align-project                 # Manual alignment check
/auto-implement

# After (automatic)
/auto-implement                # Alignment validated automatically
```

---

### `/bootstrap` - Merged into `/setup`

**Archived Because**: Duplicates `/setup` functionality

**What Replaced It**:
- `/setup` command now includes auto-detection (merged from /bootstrap)
- Tech stack detection built into setup wizard

**Migration**:
```bash
# Before (two commands)
/bootstrap                     # Auto-detect tech stack
/setup                         # Configure plugin

# After (one command)
/setup                         # Does both: auto-detect + configure
```

---

### `/create-project-md` - Merged into `/setup`

**Archived Because**: `/setup` already prompts for PROJECT.md creation

**What Replaced It**:
- `/setup` command includes PROJECT.md creation wizard
- Same functionality, integrated into setup flow

**Migration**:
```bash
# Before (two commands)
/create-project-md --generate  # Create PROJECT.md
/setup                         # Setup plugin

# After (one command)
/setup                         # Prompts for PROJECT.md creation
```

---

### `/sync-dev` - Developer-Only Tool

**Archived Because**: Only for plugin development, not end users

**What Replaced It**:
- Documented in `docs/DEVELOPER.md` instead
- Script still available: `scripts/sync_to_installed.py`
- Not a user-facing command

**For Developers**:
```bash
# Direct script invocation
python scripts/sync_to_installed.py
```

---

### `/health-check` - Diagnostic Tool

**Archived Because**: Not part of core vibe coding workflow

**What Replaced It**:
- Hooks validate component health automatically
- `/setup` verifies installation
- Only needed for debugging (rare)

**If Needed**:
```bash
# Direct script invocation (rare)
python scripts/health_check.py
```

---

## Active Commands (4 Core)

**Keep these aligned with philosophy**:

1. **`/auto-implement`** - Vibe coding entry point
   - Natural language → professional engineering result
   - Core workflow command

2. **`/status`** - Strategic visibility
   - Shows PROJECT.md goal progress
   - Stay aligned with strategy

3. **`/setup`** - Installation wizard
   - One-time setup (merged /bootstrap + /create-project-md)
   - Auto-detects tech stack, creates PROJECT.md, installs hooks

4. **`/uninstall`** - Removal wizard
   - One-time cleanup
   - Guided uninstallation

---

## Philosophy Validation

**Before (11 commands)**:
- 7 manual commands violating background enforcement
- 2 duplicate commands
- 2 developer-only commands
- Cognitive overhead for users

**After (4 commands)**:
- All manual steps automated via hooks
- No duplicates
- Clear purpose for each command
- Minimal cognitive overhead

**Core Workflow**:
```bash
# User workflow
"Add feature X"        # Natural language
# → /auto-implement auto-invokes (strict mode)
# → All validation in background (hooks)
# → Tests, security, quality checked at commit

/clear                 # Context management

"Add feature Y"        # Repeat
```

**Result**: Pure vibe coding with background enforcement ✅

---

## Restoration

If you need an archived command, the files are preserved here. You can restore by moving back to `commands/`:

```bash
# Example: Restore /test command
mv commands/archived/test.md commands/test.md
# Restart Claude Code to pick up changes
```

**However**: Consider whether the hook-based approach is sufficient before restoring. The philosophy of background enforcement vs manual commands is intentional.

---

## Version History

- **v3.0.0-v3.0.2**: 11 commands (pre-simplification)
- **v3.1.0+**: 4 commands (post-simplification, aligned with philosophy)
