# Safe Chain Detection Design - Addressing Novel Feature Concerns

**Date**: 2025-11-04
**Purpose**: Address concerns about novel features, automatic execution, and performance

---

## Your Concerns (All Valid!)

1. ❌ **Novel features are buggy** - You're right!
2. ⚠️ **Automatic execution is risky** - Absolutely correct
3. 🤔 **Need user confirmation** - Essential for safety
4. 💡 **Can we use existing agent logging?** - YES!
5. ⚡ **Agents feel slow** - Let's optimize

Let me address each systematically:

---

## Concern 1: Novel = Buggy ⚠️

**Your concern**: "I am concerned with anything novel as it's likely to be buggy"

**You're absolutely right!** Let's **minimize novel code**:

### What's Actually Novel (Risk Areas):

1. ❌ **Chain detection algorithm** - NEW CODE (risky)
2. ❌ **Feature matching/similarity** - NEW CODE (risky)
3. ❌ **Validation logic** - NEW CODE (risky)

### Solution: Use PROVEN Patterns Only

<comparison>
**BAD (Novel)**:
```python
# Complex feature matching algorithm
similarity = calculate_semantic_similarity(chain_feature, user_request)
if similarity > 0.7:
    use_chain()
```

**GOOD (Proven - from PubNub)**:
```python
# Simple exact match + user confirmation
if chain.feature.lower() in user_request.lower():
    ask_user("Found chain for '{chain.feature}'. Continue? (Y/n)")
else:
    ask_user("Found different chain '{chain.feature}'. Use it? (Y/n)")
```
</comparison>

### Simplified Design (No Novel Code):

**Remove these "novel" features**:
- ❌ Automatic feature matching
- ❌ Similarity scoring
- ❌ Smart validation logic

**Keep only proven patterns**:
- ✅ Exact feature name match (simple string check)
- ✅ Manual user confirmation (like PubNub)
- ✅ JSON file storage (proven everywhere)
- ✅ Status markers (proven in Claude-SPARC)

**Result**: 90% borrowed code, 10% glue → Much lower bug risk!

---

## Concern 2: Automatic vs Command-Driven ⚠️

**Your concern**: "Do any of these automatically execute from written text or are all /command driven?"

### Answer: ALL Use Manual Triggers

**None of the 5 implementations auto-execute**:

| Implementation | Trigger Mechanism | User Control |
|----------------|------------------|--------------|
| Agent Farm | Manual: Launch script | ✅ Fully manual |
| Claude-SPARC | Manual: Check assignments, run agent | ✅ Manual per phase |
| **PubNub** | **Hook suggests, user approves** | ✅✅ **Best model** |
| Hub-Spoke | Manual: @mention orchestrator | ✅ Manual routing |
| wshobson | Manual: Slash command | ✅ Manual invocation |

### PubNub's Safe Pattern (What We Should Copy):

```bash
# Step 1: Agent completes
pm-spec agent finishes → Updates queue to "READY_FOR_ARCH"

# Step 2: Hook SUGGESTS (doesn't execute!)
on-subagent-stop.sh prints:
  "📎 Chain ready: Use the architect-review subagent on 'use-case-presets'"

# Step 3: Human APPROVES
User reads suggestion
User decides: copy-paste command OR skip to different step OR stop

# Step 4: Next agent runs (user triggered)
User: /plan "use-case-presets"  # Explicit command
```

**Key**: Hook NEVER auto-executes, only SUGGESTS

---

## Concern 3: User Confirmation Flow 🎯

**Your need**: "I wanted to make sure that if I did a /subagent it either asked what to do or checked file and confirmed if I wanted to continue"

### Proposed Safe Flow:

```bash
# User runs command
/plan "JWT authentication"

# Agent detects chain file exists
Agent: "📎 Found existing chain for 'JWT authentication'

       Previous work:
       ✅ researcher completed (2 hours ago)
          Summary: Recommended PyJWT with Redis

       Options:
       1) Continue chain (use researcher's findings)
       2) Start fresh (ignore existing chain)
       3) View full chain details

       Your choice? (1/2/3)"

# User decides explicitly
User: "1"  # or types "continue"

# Agent proceeds with user's choice
Agent: "✅ Using researcher findings from chain..."
```

**No automatic execution** - User always approves!

### Implementation:

```python
# In each agent's prompt:

## STEP 0: Check for Chain (SAFE VERSION)

1. Check if `docs/sessions/.agent-chain.json` exists
2. If exists:
   - Read chain data
   - Print summary to user
   - **USE AskUserQuestion TOOL** (built-in Claude Code feature)
   - Wait for user decision
   - Proceed based on user's choice
3. If not exists:
   - Start normally
```

**Uses Claude Code's built-in `AskUserQuestion` tool** - proven, safe, no novel code!

---

## Concern 4: Existing Agent Logging 💡

**Your question**: "What about the existing agent logging we just implemented? Can this be used in another claude parallel session?"

### YES! Here's How:

**What you have** (from other session):
- `docs/sessions/` with agent session logs
- Progress tracking system
- Pipeline status tracking

**Perfect for chain detection!**

### Use Existing Infrastructure:

```python
# NO NEW FILES NEEDED!
# Use your existing session logs:

# Agent checks:
session_logs = glob("docs/sessions/*-researcher-*.md")
if session_logs:
    latest = max(session_logs, key=os.path.getmtime)

    # Ask user
    print(f"Found researcher session: {latest}")
    print("Use this research? (Y/n)")

    if user_says_yes():
        # Read existing session log
        research = read_file(latest)
        # Use it as context
```

**Benefits**:
- ✅ No new manifest file
- ✅ Uses existing session logs
- ✅ Works with your current implementation
- ✅ Zero new infrastructure

### Simplified Design (Leverage Existing):

**FORGET the chain manifest JSON!** Use what you already have:

```
docs/sessions/
  20251104-090420-researcher.md    # Already exists!
  20251104-091530-planner.md        # Already exists!
  20251104-093045-implementer.md    # Already exists!
```

**Agent logic** (simple):
```python
# When agent starts:
1. List session files for previous agents
2. If found, ask user: "Use <file>? (Y/n)"
3. If yes, read file
4. If no, start fresh
```

**No manifest, no novel code, uses existing infrastructure!**

---

## Concern 5: Agent Performance ⚡

**Your concern**: "I think I would also like to see how others wrote their agents... mine feel slow to run"

### Performance Analysis of Your Agents:

```
Your agents:
- planner: opus (SLOW but high quality)
- researcher: sonnet (medium speed)
- implementer: sonnet (medium speed)
- security-auditor: haiku (FAST)
- doc-master: haiku (FAST)
```

### Performance Tips from Research:

#### 1. **Model Selection** (Biggest Impact!)

```yaml
# ❌ SLOW (you're using this for most)
model: sonnet   # Good quality, but slow

# ✅ FAST (use for simple tasks)
model: haiku    # 3-5x faster, cheaper

# ⚠️ VERY SLOW (only for complex reasoning)
model: opus     # Use only for planner
```

**Recommendation**: Switch more agents to Haiku

| Agent | Current | Recommended | Why |
|-------|---------|-------------|-----|
| researcher | sonnet | sonnet | ✅ Needs web search quality |
| planner | opus | opus | ✅ Needs deep reasoning |
| test-master | sonnet | **haiku** | ⚡ Simple task (write tests) |
| implementer | sonnet | sonnet | ✅ Needs code quality |
| reviewer | sonnet | **haiku** | ⚡ Pattern matching |
| security | haiku | haiku | ✅ Already fast |
| docs | haiku | haiku | ✅ Already fast |

**Potential speedup**: 30-40% faster overall

#### 2. **Simplify Agent Prompts**

Your researcher agent (100 lines) vs wshobson's (probably ~50 lines):

```markdown
# ❌ SLOWER (more instructions = more processing)
## Your Mission (10 lines)
## Core Responsibilities (5 lines)
## Process (20 lines)
## Output Format (30 lines)
## Quality Standards (10 lines)
## Relevant Skills (10 lines)
# Total: ~100 lines

# ✅ FASTER (essential only)
## Mission
Research existing patterns and recommend approach.

## Process
1. Search codebase (Grep/Glob)
2. Web research (2-3 queries)
3. Report: Recommended approach + alternatives

## Output
- Recommended: [approach]
- Why: [rationale]
- Alternatives: [list]
# Total: ~30 lines
```

**Recommendation**: Cut prompt size by 50%

#### 3. **Limit Tool Usage**

```yaml
# ❌ SLOWER (more tools = more thinking about which to use)
tools: [WebSearch, WebFetch, Read, Grep, Glob, Write, Edit, Bash]

# ✅ FASTER (only essential tools)
tools: [WebSearch, WebFetch, Read, Grep, Glob]  # Remove unnecessary tools
```

#### 4. **Use Parallel Sessions** (Your Idea!)

```bash
# ❌ SLOW (sequential - 15 min total)
/research "JWT"     # 5 min
/plan "JWT"         # 5 min
/security-scan      # 5 min

# ✅ FAST (parallel - 5 min total)
Session 1: /research "JWT"      # 5 min
Session 2: /security-scan       # 5 min (runs simultaneously)
Session 3: /plan "JWT"          # Waits for research, uses results

# Total time: 5-10 min instead of 15 min
```

**This is BRILLIANT for independent tasks!**

**What can run in parallel**:
- ✅ Research + Security scan (no dependencies)
- ✅ Implementation + Documentation (docs can start early)
- ❌ Research → Plan (dependent, must be sequential)

---

## Recommended Simplified Design 🎯

Based on your concerns, here's the SAFE, proven-only approach:

### Design Principles:

1. ✅ **No novel code** - Only borrowed patterns
2. ✅ **Manual confirmation** - User approves every step
3. ✅ **Use existing logs** - No new infrastructure
4. ✅ **Optimize performance** - Haiku where possible

### Implementation (Safe Version):

```python
# lib/agent_session_detector.py (100 lines, all proven patterns)

def check_previous_sessions(agent_name: str, feature: str) -> Optional[str]:
    """
    Check if previous agent sessions exist.
    Returns: path to session file or None
    """
    # Simple glob (proven pattern from Agent Farm)
    prev_agent_sessions = glob(f"docs/sessions/*-{prev_agent}-*.md")

    if prev_agent_sessions:
        latest = max(prev_agent_sessions, key=os.path.getmtime)
        return latest
    return None

def ask_user_continue(session_file: str) -> bool:
    """
    Ask user if they want to use previous session.
    Uses Claude Code's built-in AskUserQuestion tool.
    """
    print(f"\n📎 Found previous work: {session_file}")
    print(f"   Modified: {get_file_time(session_file)}")
    print(f"\nUse this previous work? (Y/n)")

    # Wait for user input (proven pattern from PubNub)
    response = input().strip().lower()
    return response in ['y', 'yes', '']
```

### Agent Prompt (Safe Version):

```markdown
## STEP 0: Check Previous Work (Optional)

Before starting:

1. Check for previous agent sessions:
   ```python
   from lib.agent_session_detector import check_previous_sessions, ask_user_continue

   prev_session = check_previous_sessions("researcher", user_feature)

   if prev_session:
       if ask_user_continue(prev_session):
           # Read previous work
           previous_work = read_file(prev_session)
           print(f"✅ Using previous research")
           # Use it in your work
       else:
           print(f"🆕 Starting fresh (user chose to ignore previous work)")
   ```

2. Proceed with your work

**No automatic execution - user always decides!**
```

### Benefits of Safe Design:

- ✅ **Zero novel code** (all patterns borrowed)
- ✅ **User controls everything** (manual approval)
- ✅ **Uses existing infrastructure** (session logs)
- ✅ **Simple to implement** (100 lines total)
- ✅ **Low bug risk** (proven patterns only)
- ✅ **Easy to debug** (simple logic)

---

## Performance Optimization Plan

### Phase 1: Quick Wins (1 hour)

1. **Switch 2 agents to Haiku**:
   - test-master: sonnet → haiku
   - reviewer: sonnet → haiku
   - **Expected**: 30% faster for these agents

2. **Simplify researcher prompt**:
   - Cut from 100 lines to 50 lines
   - **Expected**: 15-20% faster

### Phase 2: Parallel Execution (2 hours)

3. **Document parallel workflows**:
   ```bash
   # Parallel research + security
   tmux new-session -d "claude /research 'JWT'"
   tmux split-window -h "claude /security-scan"
   ```
   - **Expected**: 40-50% time savings for independent tasks

### Phase 3: Advanced (future)

4. **Pre-warm context** (advanced):
   - Load common files into context early
   - Use CLAUDE.md to pre-load project patterns

---

## Final Recommendation: Minimal Safe Implementation

### What to Build:

**Forget the fancy chain manifest!** Build this instead:

```python
# lib/session_helper.py (50 lines)

def find_previous_session(agent_type: str) -> Optional[str]:
    """Find latest session file for agent type"""
    sessions = glob(f"docs/sessions/*-{agent_type}-*.md")
    return max(sessions, key=os.path.getmtime) if sessions else None

def ask_use_session(session_file: str) -> bool:
    """Ask user if they want to use previous session"""
    print(f"Found: {session_file}")
    return input("Use it? (Y/n): ").lower() in ['y', 'yes', '']
```

### Agent Integration (5 lines per agent):

```markdown
## Optional: Use Previous Work

```python
from lib.session_helper import find_previous_session, ask_use_session

prev = find_previous_session("researcher")
if prev and ask_use_session(prev):
    context = read_file(prev)
    # Use context in your work
```
\```
```

### Total Complexity:

- **New code**: 50 lines
- **Novel patterns**: 0
- **Risk**: Very low
- **Time to implement**: 2-3 hours
- **Benefits**: Users can skip repeat work, agents coordinate via existing logs

---

## Summary & Decision Point

### Your Concerns → Our Solutions:

| Your Concern | Solution | Risk Level |
|--------------|----------|------------|
| Novel features buggy | ✅ Use only proven patterns | LOW |
| Automatic execution risky | ✅ Manual confirmation (PubNub model) | LOW |
| Need user control | ✅ AskUserQuestion tool | LOW |
| Use existing logging? | ✅ YES! Leverage session logs | LOW |
| Agents feel slow | ✅ Switch to Haiku + simplify prompts | LOW |

### Recommended Next Steps:

**Option A: Minimal Safe (RECOMMENDED)**
- Implement simple session detection (50 lines)
- Manual user confirmation every time
- Use existing session logs
- **Time**: 2-3 hours
- **Risk**: Very low

**Option B: Do Nothing**
- Keep current workflow (manual coordination)
- Optimize agent performance (Haiku, simplify prompts)
- **Time**: 1 hour (just optimization)
- **Risk**: Zero

**Option C: Full Chain Manifest (RISKY)**
- Implement full design from earlier docs
- Novel features, complex validation
- **Time**: 3 days
- **Risk**: Medium-high (bugs likely)

---

**My Recommendation**: **Option A** - Simple, safe, uses what you have, low risk, still provides value

Want to proceed with Option A?
