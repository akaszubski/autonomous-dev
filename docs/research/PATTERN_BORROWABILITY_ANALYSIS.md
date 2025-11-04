# Pattern Borrowability Analysis - Can We Directly Use These?

**Date**: 2025-11-04
**Question**: Are these implementations Claude Code-specific? Can we borrow patterns directly?

---

## TL;DR Answer

**Specificity**: ✅ **ALL 5 are Claude Code-specific**
**Borrowability**: ⚠️ **Patterns YES, Code NO**

You can **borrow the coordination patterns** (JSON files, status tracking, handoffs) but **cannot copy-paste code** because they use different Claude Code features than us.

---

## Detailed Analysis by Implementation

### 1. Agent Farm (Dicklesworthstone) ⭐

**Claude Code-specific?** ✅ **YES - Extremely specific**

**What makes it CC-specific**:
- Uses `claude --dangerously-skip-permissions` CLI flag
- Requires `ENABLE_BACKGROUND_TASKS=1` environment variable
- Spawns multiple Claude Code sessions in tmux panes
- Monitors Claude Code-specific context limits

**Can we borrow?** ⚠️ **Patterns YES, Implementation NO**

**What we can borrow**:
```json
// ✅ Coordination file structure (directly applicable)
{
  "active_work_registry.json": {
    "tasks": [{"agent_id": "...", "status": "in_progress"}]
  },
  "completed_work_log.json": {
    "completed": [{"task": "...", "agent": "..."}]
  }
}

// ✅ Lock file concept
"agent_locks/feature-name.lock"

// ✅ Conflict prevention logic
"Check registry before claiming work"
```

**What we CANNOT borrow**:
- ❌ Tmux orchestration (we use single Claude session)
- ❌ Multiple parallel Claude instances (we use subagents)
- ❌ CLI flag configuration (we use .claude/agents/)
- ❌ Background task spawning (different architecture)

**Adaptation needed**:
- Change from "parallel agents" to "sequential chain"
- Single chain manifest instead of flat work registry
- Use Claude Code's native subagent system

---

### 2. Claude-SPARC (ruvnet)

**Claude Code-specific?** ✅ **YES - Uses Claude Code features**

**What makes it CC-specific**:
- Relies on Claude Code's conversation context
- Uses Claude Code's file system access
- SPARC methodology designed for Claude's reasoning

**Can we borrow?** ✅ **Patterns HIGHLY borrowable**

**What we can borrow**:
```json
// ✅ Status emoji convention (directly usable!)
"🟢 COMPLETE"  // Agent finished successfully
"🟡 IN_PROGRESS"  // Agent working
"🔴 BLOCKED"  // Agent stuck

// ✅ Rich context structure
{
  "agent_id": "researcher-001",
  "current_task": "Research JWT",
  "status": "🟡 IN_PROGRESS",
  "files_modifying": ["docs/research.md"],
  "dependencies": [],
  "last_heartbeat": "2025-11-04T10:30:00Z"
}

// ✅ Agent assignments tracking
{
  "assignments": [
    {"phase": "Research", "agent": "researcher", "status": "🟢"}
  ]
}
```

**What we CANNOT borrow**:
- ❌ Complex directory structure (too much overhead)
- ❌ Per-agent session directories (we want single manifest)
- ❌ SPARC-specific phases (our workflow is different)

**Adaptation needed**:
- Flatten to single chain manifest
- Keep status emojis ✅
- Keep heartbeat concept ✅
- Simplify directory structure

---

### 3. PubNub Pipeline

**Claude Code-specific?** ✅ **YES - Uses subagents**

**What makes it CC-specific**:
- Uses Claude Code subagents (`pm-spec`, `architect-review`)
- Hook system (`on-subagent-stop.sh`)
- `.claude/` directory structure

**Can we borrow?** ✅ **Patterns DIRECTLY borrowable**

**What we can borrow**:
```json
// ✅ Status progression (directly usable!)
"READY_FOR_ARCH"  → "READY_FOR_BUILD" → "DONE"

// ✅ Queue file structure
{
  "features": [
    {
      "name": "use-case-presets",
      "status": "READY_FOR_ARCH",
      "pm_notes": "docs/pm/use-case-presets.md"
    }
  ]
}

// ✅ Hook integration pattern
on-subagent-stop.sh:
  - Read queue.json
  - Print next command
  - User approves
```

**What we CANNOT borrow**:
- ❌ Manual approval requirement (we want auto-detection)
- ❌ 3-stage limitation (we have 7 agents)
- ❌ Hook script language (we use Python hooks)

**Adaptation needed**:
- Replace bash hook with Python hook
- Remove manual approval, add validation
- Generalize from 3 stages to N agents

---

### 4. Hub-and-Spoke (vanzan01)

**Claude Code-specific?** ✅ **YES - Very specific**

**What makes it CC-specific**:
- MCP server support required
- Claude Code hook system
- `.claude/` directory with agents
- `CLAUDE.md` behavioral rules (CC-specific format)

**Can we borrow?** ⚠️ **Concepts YES, Implementation NO**

**What we can borrow**:
```markdown
// ✅ Central coordination concept (adapted)
All agents check manifest before starting

// ✅ Handoff contracts (conceptual)
Agents document:
  - Decisions made
  - Files modified
  - Next specialist suggested

// ✅ Behavioral rules concept
Define how agents should behave in chain
```

**What we CANNOT borrow**:
- ❌ Central orchestrator agent (we want decentralized)
- ❌ Hub-spoke architecture (we want sequential chain)
- ❌ MCP server requirement (we use simpler files)

**Adaptation needed**:
- Decentralize: agents self-coordinate via manifest
- No central router, use validation instead
- File-based handoffs instead of orchestrator

---

### 5. wshobson/agents

**Claude Code-specific?** ✅ **YES - Plugin system**

**What makes it CC-specific**:
- Claude Code plugin system (`plugin.json`)
- `.claude-plugin/marketplace.json`
- Slash command syntax (`/plugin install`)
- Claude Code subagent format (markdown with frontmatter)

**Can we borrow?** ⚠️ **Organizational patterns only**

**What we can borrow**:
```yaml
# ✅ Plugin organization (we already do this!)
plugins/
  agents/
  commands/
  skills/
  hooks/

# ✅ Progressive disclosure concept
Load only what's needed

# ✅ Model optimization pattern
- Sonnet for complex (researcher, planner)
- Haiku for simple (security, docs)
```

**What we CANNOT borrow**:
- ❌ In-memory coordination (we want persistent files)
- ❌ Orchestrator slash commands (different architecture)
- ❌ No state files (we need chain manifest)

**Adaptation needed**:
- Add file-based coordination
- Keep plugin organization ✅
- Keep model optimization ✅

---

## Summary Matrix

| Implementation | CC-Specific? | Can Borrow Patterns? | Can Use Code? | What to Borrow |
|----------------|--------------|---------------------|---------------|----------------|
| **Agent Farm** | ✅ YES | ✅ YES | ❌ NO | JSON file structure, lock concept |
| **Claude-SPARC** | ✅ YES | ✅✅ HIGHLY | ❌ NO | Status emojis, heartbeat, context structure |
| **PubNub** | ✅ YES | ✅✅ DIRECTLY | ⚠️ PARTIAL | Status progression, hook pattern, queue |
| **Hub-Spoke** | ✅ YES | ⚠️ CONCEPTS | ❌ NO | Handoff contracts, behavioral rules |
| **wshobson** | ✅ YES | ✅ ORGANIZATIONAL | ❌ NO | Plugin structure, model optimization |

---

## What We Can Directly Borrow

### ✅ Directly Usable (Copy-Paste Level)

1. **Status emojis** (Claude-SPARC):
   ```json
   {"status": "🟢 completed"}
   {"status": "🟡 in_progress"}
   {"status": "🔴 blocked"}
   ```

2. **Queue file structure** (PubNub):
   ```json
   {
     "chain_id": "...",
     "features": [{
       "name": "jwt-auth",
       "status": "READY_FOR_PLANNER"
     }]
   }
   ```

3. **Coordination file names** (Agent Farm):
   ```
   active_work_registry.json  → .agent-chain.json
   completed_work_log.json    → (part of chain history)
   planned_work_queue.json    → (not needed - manual commands)
   ```

### ✅ Easily Adaptable (1-2 hours)

4. **Lock files concept** (Agent Farm):
   ```python
   # Prevent parallel chains for same feature
   lock_file = f"docs/sessions/.chain-lock-{feature_slug}.lock"
   if lock_file.exists():
       print("Another chain in progress for this feature")
   ```

5. **Heartbeat tracking** (Claude-SPARC):
   ```json
   {
     "last_updated": "2025-11-04T10:30:00Z",
     "ttl": "2025-11-05T10:30:00Z"  // 24 hours
   }
   ```

6. **Hook integration** (PubNub):
   ```python
   # hooks/on_agent_complete.py
   def suggest_next_command(chain):
       next_agent = chain.get_next_suggested()
       print(f"📎 Chain ready: run `/{next_agent} '{chain.feature}'`")
   ```

### ⚠️ Requires Significant Adaptation (1 day+)

7. **Complex context structure** (Claude-SPARC):
   - Too complex, need to simplify for our use case
   - Keep: status, files_modified, dependencies
   - Remove: Per-agent directories, separate task queues

8. **Hub-spoke coordination** (vanzan01):
   - Completely different architecture
   - Borrow concept: handoff contracts
   - Adapt: Decentralize via self-coordination

---

## Claude Code-Specific Constraints We Must Respect

### 1. Subagents Cannot Spawn Subagents

**Constraint**: Claude Code docs explicitly state: "subagents cannot spawn other subagents"

**Impact on our design**: ✅ No problem - our chain uses manual commands or main Claude coordinates

**Example**:
```bash
# ✅ Works: Main Claude runs agents
/research → /plan → /implement

# ✅ Works: /auto-implement coordinates agents
Command invokes: researcher → planner → implementer

# ❌ Doesn't work: Agent spawns agent
researcher agent calls Task(subagent_type="planner")  # Not allowed!
```

### 2. Agents Have Separate Contexts

**Constraint**: Each subagent has isolated context window

**Impact on our design**: ✅ This is WHY we need chain manifest!

**Solution**: Chain manifest passes lightweight context between agents

### 3. File-Based Agent Definitions

**Constraint**: Agents defined as markdown files in `.claude/agents/`

**Impact on our design**: ✅ No problem - we already use this

**Format**:
```markdown
---
name: researcher
description: Research patterns and best practices
model: sonnet
tools: [WebSearch, WebFetch, Read, Grep, Glob]
---

You are the researcher agent...
```

### 4. Hook System Requires Restart

**Constraint**: Hook changes require Claude Code restart

**Impact on our design**: ⚠️ Minor - document this for users

**Workaround**: Design hooks to be configurable without code changes

---

## Can We Use Their Code Directly?

### Agent Farm Code: ❌ NO

**Why not**:
- Uses tmux for parallel sessions (we use subagents)
- CLI flags we don't need (`--dangerously-skip-permissions`)
- Different architecture (parallel vs sequential)

**What we can copy**:
- JSON structure for coordination files
- Lock file concept (file naming)

### Claude-SPARC Code: ❌ NO

**Why not**:
- Complex directory structure (overkill)
- SPARC-specific phases (not our workflow)
- Per-agent session dirs (we want single manifest)

**What we can copy**:
- Status emoji convention (exact copy ✅)
- Context structure (simplified version)

### PubNub Code: ⚠️ PARTIAL

**Why partial**:
- ✅ Queue structure is usable
- ✅ Status progression directly applicable
- ❌ Bash hooks (we use Python)
- ❌ Manual approval (we want auto-detection)

**What we can copy**:
- Queue JSON format (80% usable)
- Status naming convention
- Hook trigger logic (adapt to Python)

### Hub-Spoke Code: ❌ NO

**Why not**:
- Central orchestrator pattern (we're decentralized)
- Different architecture entirely

**What we can copy**:
- Handoff contract concept (adapt to JSON)

### wshobson Code: ❌ NO

**Why not**:
- No coordination files (in-memory only)
- Different plugin structure

**What we can copy**:
- Plugin organization (already similar)
- Model selection strategy

---

## Final Borrowability Assessment

### Can Borrow Directly (95%+ code reuse):

1. ✅ **Status emojis** (Claude-SPARC) - EXACT copy
2. ✅ **Queue structure** (PubNub) - 80% reuse
3. ✅ **File naming** (Agent Farm) - Concept copy

### Can Adapt Easily (50-80% code reuse):

4. ✅ **Context structure** (Claude-SPARC) - Simplify
5. ✅ **Hook pattern** (PubNub) - Port to Python
6. ✅ **Heartbeat tracking** (Claude-SPARC) - Copy concept

### Must Write From Scratch (0-20% reuse):

7. ❌ **Chain detection logic** (NOVEL - no one has this)
8. ❌ **Feature matching** (NOVEL)
9. ❌ **Graceful validation** (NOVEL)
10. ❌ **Single manifest** (NOVEL)

---

## Recommendation: Hybrid Approach

### Phase 1: Borrow What Works

```python
# lib/agent_chain.py

# ✅ BORROWED: Status emojis (Claude-SPARC)
STATUS_COMPLETED = "🟢 completed"
STATUS_IN_PROGRESS = "🟡 in_progress"
STATUS_BLOCKED = "🔴 blocked"

# ✅ BORROWED: File structure (Agent Farm)
CHAIN_FILE = "docs/sessions/.agent-chain.json"
LOCK_DIR = "docs/sessions/locks/"

# ✅ BORROWED: Context structure (Claude-SPARC, simplified)
{
  "agent": "researcher",
  "status": STATUS_COMPLETED,
  "summary": "...",
  "files_modified": ["..."],
  "last_updated": "...",
  "next_suggested": "planner"
}
```

### Phase 2: Add Our Novel Features

```python
# ✅ NOVEL: Chain detection
def detect_chain(feature: str) -> Optional[AgentChain]:
    """Auto-detect if chain exists for feature"""

# ✅ NOVEL: Feature matching
def feature_similarity(chain_feature: str, request: str) -> float:
    """Calculate similarity 0-1"""

# ✅ NOVEL: Validation logic
def validate_chain(chain: AgentChain, feature: str) -> ValidationResult:
    """Check if chain is relevant, fresh, files exist"""
```

---

## Updated Implementation Estimate

### Borrowed Components (Save 40% time):

- Status emojis: **0.5 hours** (copy-paste)
- File structure: **1 hour** (adapt from Agent Farm)
- Context format: **2 hours** (simplify Claude-SPARC)
- Hook integration: **4 hours** (port from PubNub to Python)

**Total borrowed**: ~7.5 hours saved

### Novel Components (Must build):

- Chain detection: **4 hours**
- Feature matching: **3 hours**
- Validation logic: **3 hours**
- Agent prompt updates: **6 hours**
- Testing: **6 hours**

**Total novel**: ~22 hours

### Grand Total: ~22 hours (2.75 days)

**Previous estimate**: 24 hours (3 days)
**Savings from borrowing**: 2 hours (8% faster)

---

## Conclusion

**Are they Claude Code-specific?**
✅ YES - All 5 are built specifically for Claude Code

**Can we borrow patterns?**
✅ YES - JSON structures, status conventions, hook patterns

**Can we copy code?**
⚠️ PARTIAL - 30-40% of patterns directly applicable, 60-70% needs adaptation

**Should we proceed?**
✅ YES - Borrowing validates our design and saves ~8% development time

---

**Key Takeaway**: We're building the RIGHT thing (validated by 5 production systems) with NOVEL features (auto-detection) that fill a gap in the ecosystem.

**Next**: Proceed with Option 3 implementation, borrowing status emojis, file structures, and hook patterns where applicable.
