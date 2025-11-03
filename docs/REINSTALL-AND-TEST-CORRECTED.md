# Complete Reinstall and Test Instructions (CORRECTED)

**Issue**: Original instructions failed to explicitly say when to START Claude Code after killing it

**This version**: Every `pkill -9 claude` is followed by explicit "Start Claude Code" instruction

---

## Prerequisites

**Terminal 1** (for commands):
```bash
cd /Users/akaszubski/Documents/GitHub/autonomous-dev
```

**Terminal 2** (for monitoring - optional):
```bash
tail -f docs/sessions/$(ls -t docs/sessions/ | grep pipeline | head -1)
```

---

## Step-by-Step Reinstall (WITH EXPLICIT RESTARTS)

### Step 1: Nuclear Clean
```bash
# Remove all plugin files
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
```

### Step 2: Kill All Claude Sessions
```bash
pkill -9 claude
```

**⏸️ WAIT 2 SECONDS**

**▶️ START CLAUDE CODE** (open the application)

### Step 3: Fresh Install
In Claude Code, run:
```
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

### Step 4: Kill and Restart (REQUIRED!)
```bash
pkill -9 claude
```

**⏸️ WAIT 2 SECONDS**

**▶️ START CLAUDE CODE** (open the application)

### Step 5: Verify New Orchestrator
In your terminal:
```bash
grep -n "STEP 1: Invoke Researcher" ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/orchestrator.md
```

**Expected**: Should show line number where "STEP 1: Invoke Researcher" appears

**If not found**: Orchestrator wasn't updated - reinstall failed

### Step 6: Bootstrap Dogfood Setup
In your terminal:
```bash
cd /Users/akaszubski/Documents/GitHub/autonomous-dev
./scripts/resync-dogfood.sh
```

### Step 7: Kill and Restart Again (REQUIRED!)
```bash
pkill -9 claude
```

**⏸️ WAIT 2 SECONDS**

**▶️ START CLAUDE CODE** (open the application)

### Step 8: Test Workflow
In Claude Code, run:
```
/auto-implement "Add a simple greeting function"
```

**⏳ Wait for orchestrator to complete** (may take 1-3 minutes)

### Step 9: Check Pipeline Status
In Claude Code, run:
```
/pipeline-status
```

### Step 10: View JSON Logs
In your terminal:
```bash
cat docs/sessions/$(ls -t docs/sessions/ | grep pipeline | head -1)
```

---

## What You're Looking For

### ✅ SUCCESS: After `/pipeline-status` you should see:

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
Total duration: XXm XXs
```

**If you see this** → Issues #32 and #29 are validated and working! ✅

### ❌ FAILURE: If you see:

```
No agents have run yet in this session
```

**This means** → Orchestrator didn't invoke agents - need to debug why ❌

---

## Key Differences from Original

| Step | Original | Corrected |
|------|----------|-----------|
| Step 2 | `pkill -9 claude` | `pkill -9 claude` + **WAIT 2 SECONDS** + **START CLAUDE CODE** |
| Step 4 | `pkill -9 claude` | `pkill -9 claude` + **WAIT 2 SECONDS** + **START CLAUDE CODE** |
| Step 7 | `pkill -9 claude` | `pkill -9 claude` + **WAIT 2 SECONDS** + **START CLAUDE CODE** |

**Why this matters**: Without explicit restart instructions, plugins aren't reloaded from disk and orchestrator changes don't take effect.

---

## Troubleshooting

### "Command not found" when running `/auto-implement`

**Problem**: Claude Code didn't restart after install

**Fix**:
```bash
pkill -9 claude
# WAIT 2 SECONDS
# START CLAUDE CODE
```

### `/pipeline-status` shows "No agents have run yet"

**Problem**: Orchestrator didn't invoke agents

**Debug**:
1. Check orchestrator was updated:
   ```bash
   grep -n "STEP 1: Invoke Researcher" ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/orchestrator.md
   ```
2. Check session logs for errors:
   ```bash
   cat docs/sessions/$(ls -t docs/sessions/ | grep pipeline | head -1) | grep -i error
   ```

### Orchestrator file shows old content

**Problem**: Install didn't update files

**Fix**: Repeat Steps 1-4 (nuclear clean and fresh install)

---

**Ready to test?** Follow each step in order and report what you see at Step 9! 🧪
