# Reinstall and Test Instructions

**Purpose**: Load the new orchestrator and pipeline tracking, then test that agents actually fire.

**Time**: ~5 minutes (mostly waiting for restarts)

---

## Step 1: Nuclear Clean - Remove Old Plugin

**Action**: Remove the old plugin completely

```bash
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
```

**Why**: Ensures you get a fresh clone from GitHub, no stale files.

---

## Step 2: Kill All Claude Code Sessions

**Action**: Kill ALL running Claude sessions (not just current terminal)

```bash
pkill -9 claude
```

**Why pkill instead of /exit or Cmd+Q?**
- `/exit` only exits the current terminal session
- `Cmd+Q` may not fully kill the process
- `pkill -9 claude` ensures ALL Claude sessions are terminated (important if multiple terminals)
- Forces fresh agent reload from disk

**Verify all killed**:
```bash
ps aux | grep claude | grep -v grep
```
Should show nothing (or just your grep command).

**Wait 2 seconds**, then reopen Claude Code.

---

## Step 3: Fresh Install from GitHub

**Action**: Run these commands in Claude Code:

```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

**Expected output**:
```
✓ Installed plugin: autonomous-dev from akaszubski/autonomous-dev
```

**This will**:
- Pull latest code from GitHub (includes enhanced orchestrator)
- Install to `~/.claude/plugins/marketplaces/.../autonomous-dev/`

---

## Step 4: Kill and Restart Again

**Action**: Kill Claude and restart to load new agents

```bash
pkill -9 claude
```

**Wait 2 seconds**, then reopen Claude Code.

**Why**: Agents are loaded at startup, so we need to restart to pick up the new orchestrator.

---

## Step 5: Verify Plugin Updated from GitHub

**Action**: Check if the new orchestrator was pulled

```bash
grep -n "STEP 1: Invoke Researcher" ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/orchestrator.md
```

**Expected output** (if plugin updated from GitHub):
```
75:#### **STEP 1: Invoke Researcher**
```

**If you see this line** → Plugin pulled latest code ✅

**If empty/error** → Plugin didn't update, need to troubleshoot ❌

---

## Step 6: Run Bootstrap/Resync

**Action**: Copy plugin files to your project's `.claude/` directory

**For dogfooding** (developing the plugin itself):
```bash
cd /Users/akaszubski/Documents/GitHub/autonomous-dev
./scripts/resync-dogfood.sh
```

**For normal users** (using the plugin):
```bash
bash install.sh
```

**Expected output**:
```
🔄 Resyncing plugin files to .claude/...
✅ 10 commands
✅ 35 hooks
✅ 11 templates
✅ Resync complete!
```

**Why**: This copies commands, hooks, and templates from the installed plugin to your project so they're discoverable.

**Verify**:
```bash
ls .claude/commands/ | wc -l
```
Should show: `10` (or similar - number of commands)

---

## Step 7: Kill and Restart One More Time

**Action**: Final restart to ensure everything loaded

```bash
pkill -9 claude
```

**Wait 2 seconds**, then reopen Claude Code.

**Why**: Ensures all components (agents, hooks, commands) are loaded fresh.

---

## Step 8: Navigate to Project Directory

**Action**: In Claude Code, make sure you're in the project directory:

```bash
cd /Users/akaszubski/Documents/GitHub/autonomous-dev
pwd
```

**Expected output**:
```
/Users/akaszubski/Documents/GitHub/autonomous-dev
```

---

## Step 9: Test the Autonomous Workflow

**Action**: Run this command to test if agents fire:

```bash
/auto-implement "Add a simple greeting function that returns 'Hello, World!'"
```

**What to watch for**:
- Does Claude invoke the orchestrator agent? (Should see "Task tool" being used)
- Does orchestrator invoke researcher?
- Does researcher invoke planner?
- Continue through all 7 agents?

**Expected behavior** (with new orchestrator):
```
I'll invoke the orchestrator agent to handle this feature request.

[Uses Task tool to invoke orchestrator]
[Orchestrator validates PROJECT.md alignment]
[Orchestrator invokes researcher agent]
[Researcher completes - logs to pipeline]
[Orchestrator invokes planner agent]
[Planner completes - logs to pipeline]
... (continues through all 7 agents)
```

---

## Step 10: Check Pipeline Status

**Action**: After the feature completes, run:

```bash
/pipeline-status
```

**Expected output** (if agents fired):
```
📊 Agent Pipeline Status (20251103-HHMMSS)

✅ researcher           COMPLETE  HH:MM:SS (XXXs) - ...
✅ planner              COMPLETE  HH:MM:SS (XXXs) - ...
✅ test-master          COMPLETE  HH:MM:SS (XXXs) - ...
✅ implementer          COMPLETE  HH:MM:SS (XXXs) - ...
✅ reviewer             COMPLETE  HH:MM:SS (XXXs) - ...
✅ security-auditor     COMPLETE  HH:MM:SS (XXXs) - ...
✅ doc-master           COMPLETE  HH:MM:SS (XXXs) - ...

======================================================================
Pipeline: COMPLETE ✅
```

---

## Step 11: Check Pipeline JSON File

**Action**: View the raw JSON log:

```bash
cat docs/sessions/$(ls -t docs/sessions/ | grep pipeline | head -1)
```

**Expected**: JSON file with agent entries showing:
- Agent names
- Timestamps
- Duration
- Tools used
- Status: "completed"

---

## Step 12: Report Results

**Tell me what happened**:

### If Agents Fired ✅
"Agents fired! Pipeline shows all 7 agents completed."
→ Issues #32 and #29 are **validated and working**

### If Agents Did NOT Fire ❌
"No agents fired. Pipeline shows empty."
→ Need to debug why orchestrator isn't invoking agents

### If Only SOME Agents Fired ⚠️
"Only X agents fired: [list which ones]"
→ Need to check why pipeline incomplete

---

## Troubleshooting

### "Command /plugin not found"
- Claude Code version might not support plugins
- Check: You're running Claude Code 2.0+

### "Plugin install fails"
- Check internet connection
- Verify GitHub repo is public and accessible
- Try: `/plugin marketplace add akaszubski/autonomous-dev` first

### "Agents still don't fire after reinstall"
- The `/auto-implement` command might not automatically invoke orchestrator
- Try manually: Use Task tool to invoke orchestrator agent
- Check: orchestrator.md actually updated on GitHub

### "/pipeline-status command not found"
- Commands might not have synced
- Check: `ls .claude/commands/ | grep pipeline`
- If missing: Run `./scripts/resync-dogfood.sh`

---

## Success Criteria

✅ Plugin reinstalled successfully
✅ Orchestrator agent invoked when using /auto-implement
✅ All 7 agents executed in sequence
✅ /pipeline-status shows completed pipeline
✅ JSON file has agent execution data

**If all ✅ → Issues #32 and #29 are TRULY complete and validated!**

---

## Quick Reference Card

```bash
# Complete Flow (copy-paste ready)

# 1. Nuclear clean
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev

# 2. Kill all Claude sessions
pkill -9 claude
# Wait 2 seconds, reopen Claude Code

# 3. Fresh install
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev

# 4. Kill and restart
pkill -9 claude
# Wait 2 seconds, reopen Claude Code

# 5. Verify new orchestrator
grep -n "STEP 1: Invoke Researcher" ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/orchestrator.md

# 6. Bootstrap
cd /Users/akaszubski/Documents/GitHub/autonomous-dev
./scripts/resync-dogfood.sh

# 7. Kill and restart again
pkill -9 claude
# Wait 2 seconds, reopen Claude Code

# 8. Test workflow
/auto-implement "Add a simple greeting function"

# 9. Check results
/pipeline-status

# 10. View JSON logs
cat docs/sessions/$(ls -t docs/sessions/ | grep pipeline | head -1)
```

**Key**: Use `pkill -9 claude` (not `/exit` or `Cmd+Q`) to ensure ALL Claude sessions restart and reload agents from disk.

---

**Time to validate if the enhancements actually work!** 🧪
