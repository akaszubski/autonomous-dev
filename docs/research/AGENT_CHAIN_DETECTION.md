# Agent Chain Detection - Design Document

**Status**: Design Phase
**Created**: 2025-11-04
**Purpose**: Enable seamless agent coordination for manual command chains

---

## Problem Statement

**Current Behavior**:
- Manual commands (`/research`, `/plan`, `/implement`) run in isolation
- Each agent starts with no context from previous agents
- User must manually coordinate: "read findings in file X, then do Y"
- Feels disconnected compared to `/auto-implement`

**User Pain Point**:
```bash
# Current: Manual coordination required
/research "JWT auth"
# User reads output, then:
/plan "JWT auth - use findings in docs/sessions/20251104-researcher.md"
# User reads output, then:
/test-feature "JWT auth - follow plan in docs/sessions/20251104-planner.md"
```

**Desired Behavior**:
```bash
# Proposed: Agents auto-detect chain
/research "JWT auth"    # Creates chain manifest
/plan "JWT auth"        # Auto-finds researcher output, uses it
/test-feature "JWT auth"  # Auto-finds plan, follows it
/implement "JWT auth"   # Auto-finds tests, makes them pass
```

---

## Solution: Agent Chain Manifest

### Architecture

Each agent writes/reads a shared **chain manifest** file that tracks the workflow.

**File**: `docs/sessions/.agent-chain.json`

**Format**:
```json
{
  "chain_id": "20251104-090420-jwt-auth",
  "feature": "JWT authentication with token refresh",
  "started": "2025-11-04T09:04:20Z",
  "last_updated": "2025-11-04T09:12:30Z",
  "agents": [
    {
      "name": "researcher",
      "started": "2025-11-04T09:04:20Z",
      "completed": "2025-11-04T09:08:15Z",
      "output_file": "docs/sessions/20251104-090420-researcher.md",
      "summary": "Found existing auth patterns, recommended JWT with Redis",
      "next_suggested": "planner",
      "key_findings": [
        "Existing auth in src/auth/basic_auth.py",
        "Redis available for token storage",
        "Recommended: PyJWT library"
      ]
    },
    {
      "name": "planner",
      "started": "2025-11-04T09:10:00Z",
      "completed": "2025-11-04T09:12:30Z",
      "output_file": "docs/sessions/20251104-090420-planner.md",
      "summary": "3-component design: AuthService, TokenManager, Redis cache",
      "next_suggested": "test-master",
      "components": [
        "src/auth/jwt_service.py - JWT token generation/validation",
        "src/auth/token_manager.py - Token storage in Redis",
        "src/middleware/auth_middleware.py - Request authentication"
      ]
    }
  ],
  "context": {
    "feature_description": "JWT authentication with token refresh",
    "project_md_aligned": true,
    "primary_goal": "Add secure JWT-based authentication",
    "constraints": ["Must use existing Redis", "No new dependencies without approval"]
  },
  "status": "in_progress",
  "ttl": "2025-11-05T09:04:20Z"
}
```

---

## Agent Behavior Changes

### Common Pattern for All Agents

Each agent prompt gets this new section:

```markdown
## Chain Detection (Smart Coordination)

**STEP 0: Check for Existing Chain**

Before starting your work:

1. **Check if chain manifest exists**:
   ```python
   from pathlib import Path
   import json

   chain_file = Path("docs/sessions/.agent-chain.json")
   if chain_file.exists():
       chain_data = json.loads(chain_file.read_text())
       # Chain exists! Continue it.
   else:
       # No chain. Start fresh.
   ```

2. **If chain exists**:
   - Read the chain manifest
   - Find the most recent agent's output
   - Load their context: `chain_data["agents"][-1]["output_file"]`
   - Use their findings as your starting point
   - Add your entry to the chain when done

3. **If no chain exists**:
   - Create new chain manifest
   - You're the first agent in this workflow
   - Work normally, add your entry when done

**STEP FINAL: Update Chain Manifest**

After completing your work:

1. Add your entry to `chain_data["agents"]` array
2. Update `last_updated` timestamp
3. Set `next_suggested` to the logical next agent
4. Write updated manifest back to file

**Example Chain Continuation**:

```python
# Pseudo-code for agent behavior
if chain_exists():
    previous_agent = chain["agents"][-1]
    print(f"📎 Continuing chain from {previous_agent['name']}")
    print(f"   Using context: {previous_agent['output_file']}")

    # Read previous agent's output
    previous_output = read_file(previous_agent['output_file'])

    # Use it in your work
    context_summary = previous_agent['summary']
    # ... do your work with this context ...

else:
    print(f"🆕 Starting new agent chain")
    create_chain_manifest()
```

**Result**: Manual command chains work seamlessly without user coordination.
```

---

## Per-Agent Specifics

### Researcher Agent

**Chain Detection Logic**:
- If NO chain: Research from scratch, create chain manifest
- If chain exists BUT no researcher entry: You're first, create entry
- If chain exists WITH researcher entry: Skip (already researched), just return findings

**What to Write**:
```json
{
  "summary": "1-sentence summary of recommendations",
  "next_suggested": "planner",
  "key_findings": [
    "Finding 1",
    "Finding 2"
  ]
}
```

### Planner Agent

**Chain Detection Logic**:
- If chain has researcher: Read research findings, use in planning
- If NO researcher: Read project structure, plan from scratch
- Always suggest "test-master" next

**What to Read**:
- `chain["agents"][-1]["output_file"]` (researcher's findings)
- `chain["agents"][-1]["key_findings"]` (quick summary)

**What to Write**:
```json
{
  "summary": "1-sentence architecture summary",
  "next_suggested": "test-master",
  "components": [
    "file.py - Purpose",
    "file2.py - Purpose"
  ]
}
```

### Test-Master Agent

**Chain Detection Logic**:
- If chain has planner: Read plan, write tests for specified components
- If NO planner: Search codebase, write tests for feature
- Always suggest "implementer" next

**What to Write**:
```json
{
  "summary": "Tests written for X components",
  "next_suggested": "implementer",
  "test_files": [
    "tests/test_jwt.py - 8 tests",
    "tests/test_token_manager.py - 6 tests"
  ]
}
```

### Implementer Agent

**Chain Detection Logic**:
- If chain has test-master: Read tests, make them pass
- If NO tests: Read plan or research, implement from scratch
- Always suggest "reviewer" next

### Reviewer Agent

**Chain Detection Logic**:
- If chain has implementer: Review their code
- Read all previous context for alignment check
- Suggest "security-auditor" next

### Security-Auditor Agent

**Chain Detection Logic**:
- Read implementer's code files
- Check security concerns from researcher
- Suggest "doc-master" next

### Doc-Master Agent

**Chain Detection Logic**:
- Read all previous agents' outputs
- Update docs based on implementation
- Mark chain as "completed"

---

## Chain Management

### Chain Lifecycle

1. **Creation**: First agent creates manifest
2. **Growth**: Each agent adds entry
3. **Completion**: Last agent marks status="completed"
4. **Cleanup**: TTL expires after 24 hours, file auto-deleted

### Chain ID Format

```
YYYYMMDD-HHMMSS-feature-slug
Example: 20251104-090420-jwt-auth
```

**Generation**:
```python
from datetime import datetime
import re

def generate_chain_id(feature_description: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r'[^a-z0-9]+', '-', feature_description.lower())[:30]
    return f"{timestamp}-{slug}"
```

### Parallel Chains

**Problem**: Multiple features being developed simultaneously

**Solution**: Chain ID uniqueness
- Each chain has unique timestamp prefix
- Agents can detect if multiple chains exist
- User must specify which chain to continue (or start new)

**Detection**:
```python
chains = list(Path("docs/sessions").glob(".agent-chain-*.json"))
if len(chains) > 1:
    # Multiple active chains - ask user which to continue
    print("Multiple chains found:")
    for chain in chains:
        data = json.loads(chain.read_text())
        print(f"  {data['chain_id']}: {data['feature']}")
```

### Chain Expiration

**TTL**: 24 hours from last_updated
**Cleanup**: Pre-commit hook or background task deletes expired chains

---

## Implementation Plan

### Phase 1: Core Infrastructure (Day 1)

1. **Create `lib/agent_chain.py` utility**:
   ```python
   class AgentChain:
       def __init__(self, feature_description: str):
           self.chain_file = Path("docs/sessions/.agent-chain.json")

       def exists(self) -> bool:
           return self.chain_file.exists()

       def create(self, feature: str) -> None:
           # Create new chain manifest

       def get_latest_agent(self) -> dict:
           # Return most recent agent entry

       def add_agent(self, agent_name: str, output_file: str, summary: str, **kwargs):
           # Add new agent to chain

       def mark_complete(self):
           # Set status="completed"
   ```

2. **Create chain manifest schema**: JSON schema for validation

3. **Test chain utilities**: Unit tests for chain creation, updates, retrieval

### Phase 2: Agent Integration (Day 2)

1. **Update agent prompts** (7 agents):
   - Add "Chain Detection" section to each agent's markdown
   - Specify what to read (previous agent's output)
   - Specify what to write (chain entry format)

2. **Test each agent**:
   - Test agent works WITHOUT chain (backwards compatible)
   - Test agent works WITH chain (auto-detects and uses context)

### Phase 3: Command Integration (Day 2)

1. **Update individual commands** (`/research`, `/plan`, etc.):
   - No changes needed! Commands just invoke agents
   - Agents handle chain detection automatically

2. **Test manual command chains**:
   ```bash
   /research "feature X"
   /plan "feature X"
   /test-feature "feature X"
   /implement "feature X"
   ```
   - Verify each command auto-detects chain
   - Verify context flows between agents
   - Verify output is coherent (not redundant)

### Phase 4: Documentation & Polish (Day 3)

1. **User documentation**:
   - Update README.md with chain detection feature
   - Add examples of manual command chains
   - Document when chains are useful vs `/auto-implement`

2. **Troubleshooting guide**:
   - How to view active chains
   - How to clear stale chains
   - How to manually continue a chain from days ago

---

## User Experience

### Before (Current)

```bash
User: /research "JWT authentication"
Researcher: [does research, writes docs/sessions/20251104-researcher.md]

User: /plan "JWT authentication - use findings in docs/sessions/20251104-researcher.md"
Planner: [reads specified file, creates plan]

User: /test-feature "JWT authentication - follow plan in docs/sessions/20251104-planner.md"
Test-master: [reads specified file, writes tests]
```

**Pain**: User must manually track filenames and tell each agent what to read

### After (Proposed)

```bash
User: /research "JWT authentication"
Researcher: [does research]
             🆕 Created agent chain: jwt-auth
             📄 Findings: docs/sessions/20251104-090420-researcher.md

User: /plan "JWT authentication"
Planner: [auto-detects chain]
         📎 Continuing chain: jwt-auth
         📖 Using research from: docs/sessions/20251104-090420-researcher.md
         [creates plan]
         📄 Plan: docs/sessions/20251104-090420-planner.md

User: /test-feature "JWT authentication"
Test-master: [auto-detects chain]
             📎 Continuing chain: jwt-auth
             📖 Using plan from: docs/sessions/20251104-090420-planner.md
             [writes tests]
             📄 Tests: tests/test_jwt_auth.py
```

**Benefit**: Agents coordinate automatically, user just runs commands sequentially

---

## Comparison: Manual Chains vs /auto-implement

| Aspect | Manual Chain | /auto-implement |
|--------|-------------|-----------------|
| **Coordination** | Automatic (via chain manifest) | Automatic (via Claude in main context) |
| **Speed** | User controls pace (pause between agents) | 20-30 min continuous |
| **Control** | Full (skip agents, run out of order) | Limited (all 7 agents run) |
| **Context passing** | File-based (chain manifest) | Prompt-based (Claude summarizes) |
| **Resume** | Can resume days later | Must complete in one session |
| **Token usage** | Lower (only agents you run) | Higher (all 7 agents) |
| **Best for** | Exploring, learning, iterating | Production features, speed |

---

## Open Questions

1. **Chain naming**: Should users be able to name chains? `/research "JWT auth" --chain-name=my-auth-feature`
2. **Chain merging**: What if user wants to merge two chains?
3. **Chain branching**: What if user wants to try alternative approach mid-chain?
4. **Chain visualization**: Should we have `/chain-status` command to show current chain?
5. **Parallel features**: How to prevent accidental chain mixing when working on 2 features?

---

## Success Metrics

After implementation, measure:

1. **Usage**: % of manual commands that use chain detection
2. **Completeness**: % of chains that reach "completed" status
3. **User satisfaction**: Survey users on manual command UX
4. **Error rate**: % of chains that fail due to missing context
5. **Token savings**: Compare token usage manual chains vs `/auto-implement`

---

## Recommendation

**IMPLEMENT THIS FEATURE**

**Why**:
- ✅ Solves real pain point (manual coordination)
- ✅ Natural evolution of existing session file architecture
- ✅ Backwards compatible (agents work without chains)
- ✅ Enables powerful new workflows (pause/resume, granular control)
- ✅ Medium complexity (2-3 days implementation)
- ✅ High user value (makes manual commands actually useful)

**Priority**: Medium-High (after critical bugs, before nice-to-haves)

**Effort**: 2-3 developer days

**Risk**: Low (isolated change, easy to rollback if issues)

---

**Next Steps**:
1. Review this design with team
2. Create GitHub issue for tracking
3. Break into smaller PRs:
   - PR1: Core chain utilities (`lib/agent_chain.py`)
   - PR2: Researcher + Planner agent integration
   - PR3: Test-master + Implementer integration
   - PR4: Reviewer + Security + Docs integration
   - PR5: Documentation + examples
