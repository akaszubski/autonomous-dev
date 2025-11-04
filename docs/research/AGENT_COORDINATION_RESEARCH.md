# Agent Coordination Research - Industry Patterns vs Our Design

**Date**: 2025-11-04
**Purpose**: Compare industry patterns with our proposed agent chain detection design

---

## Research Summary

### Patterns Discovered

I researched 8+ multi-agent systems (LangGraph, CrewAI, AutoGPT, Anthropic, Microsoft, Claude Code, OpenAI Swarm) and found 5 major coordination patterns:

---

## Pattern 1: Command/Message Passing (LangGraph, OpenAI Swarm)

**How it works**:
- Agents return `Command` objects that specify: next agent + state updates
- In-memory state graph tracks current agent and shared data
- Example: `Command(goto="planner", update={"research": findings})`

**Data Structure**:
```python
Command(
    goto="next_agent",  # Control flow
    update={"key": "value"}  # State updates
)
```

**Pros**:
- ✅ Programmatic control flow
- ✅ Type-safe state updates
- ✅ Real-time coordination

**Cons**:
- ❌ Requires framework (LangGraph SDK)
- ❌ In-memory only (not resumable after restart)
- ❌ Complex setup

**Relevance to Claude Code**: ❌ LOW - Claude Code doesn't use LangGraph SDK

---

## Pattern 2: Task Context Passing (CrewAI)

**How it works**:
- Tasks pass outputs via `context` parameter
- Sequential task chaining: `task2.context = [task1]`
- Agents delegate with built-in tools: `Delegate Work` and `Ask Question`

**Data Structure**:
```python
Task(
    description="...",
    context=[previous_task],  # Sequential handoff
    agent=agent
)
```

**Pros**:
- ✅ Simple sequential workflows
- ✅ Explicit task dependencies
- ✅ Built-in delegation tools

**Cons**:
- ❌ Linear flows only (no branching)
- ❌ Requires CrewAI framework
- ❌ Not resumable

**Relevance to Claude Code**: ❌ LOW - Claude Code doesn't use CrewAI

---

## Pattern 3: Handoff Protocol (Black Dog Labs - MCP Server)

**How it works**:
- MCP server stores structured handoff state in `~/.handoffs/` JSON files
- Reduces context from 10K+ tokens to 1-2K tokens
- Captures: task context, file references, decisions, next steps

**Data Structure**:
```json
{
  "task": {
    "objective": "Add JWT auth",
    "status": "in_progress",
    "progress": "Research complete, planning next"
  },
  "files": [
    {
      "path": "src/auth.py",
      "relevance": "Existing auth implementation",
      "focus_ranges": [[10, 50]]
    }
  ],
  "decisions": [
    {
      "decision": "Use PyJWT library",
      "rationale": "Most maintained",
      "timestamp": "2025-11-04T10:30:00Z"
    }
  ],
  "next_steps": [
    {"action": "Write tests", "priority": "high"}
  ]
}
```

**Pros**:
- ✅ **File-based persistence** (resumable!)
- ✅ Structured JSON format
- ✅ Massive token savings (24%)
- ✅ Context restoration: 10 min → 30 sec

**Cons**:
- ❌ Requires custom MCP server
- ❌ Not standard Claude Code feature
- ❌ Complex setup

**Relevance to Claude Code**: ⭐ **HIGH** - File-based, resumable, proven approach

---

## Pattern 4: Subagent Transcripts (Claude Code Official)

**How it works**:
- Each subagent writes `agent-{agentId}.jsonl` transcript file
- Resumable via `resume` parameter
- Agents have isolated contexts (no shared state)
- **Critical**: Subagents CANNOT spawn other subagents (prevents recursion)

**Data Structure**:
```jsonl
{"timestamp": "...", "role": "user", "content": "..."}
{"timestamp": "...", "role": "assistant", "content": "..."}
```

**Pros**:
- ✅ **Native Claude Code feature**
- ✅ File-based persistence
- ✅ Resumable conversations
- ✅ Simple format (JSONL)

**Cons**:
- ❌ Full transcript (high token usage)
- ❌ No explicit handoff metadata
- ❌ No agent-to-agent coordination

**Relevance to Claude Code**: ⭐⭐⭐ **VERY HIGH** - Already built-in!

---

## Pattern 5: Orchestrator + External Memory (Anthropic Multi-Agent Research)

**How it works**:
- Lead agent coordinates, subagents work in parallel
- **External memory** stores plans/context outside agent contexts
- Agents store artifacts, pass lightweight references back
- When context exceeds 200K tokens, retrieve from external memory

**Data Structure**:
```python
# Conceptual - not actual code
memory.store("research_plan", plan_data)
# Later:
plan = memory.retrieve("research_plan")
```

**Pros**:
- ✅ Scales to large contexts
- ✅ Lightweight references reduce tokens
- ✅ Persistent across agent boundaries

**Cons**:
- ❌ Requires external memory system
- ❌ Not described in detail (research system)
- ❌ Complexity overhead

**Relevance to Claude Code**: ⭐⭐ **MEDIUM** - Concept is good, but no implementation details

---

## Pattern 6: Schema-Driven Handoffs (Skywork.ai Best Practices)

**How it works**:
- Define **handoff schemas** that specify what data passes between agents
- Central controller validates schema compliance
- Observability layer monitors handoff transitions
- Structured protocols ensure agents understand handoff data

**Data Structure**:
```yaml
# Conceptual schema
handoff_schema:
  from_agent: researcher
  to_agent: planner
  data:
    findings: string
    recommendations: array
    confidence: float
```

**Pros**:
- ✅ Predictable handoffs
- ✅ Validation prevents errors
- ✅ Traceable workflow

**Cons**:
- ❌ Rigid schemas (less flexible)
- ❌ Overhead of schema management
- ❌ Not implemented anywhere specific

**Relevance to Claude Code**: ⭐ **LOW-MEDIUM** - Good principles, but theoretical

---

## Our Proposed Design vs Industry Patterns

### Our Design (Chain Manifest)

**File**: `docs/sessions/.agent-chain.json`

```json
{
  "chain_id": "20251104-090420-jwt-auth",
  "feature": "JWT authentication",
  "agents": [
    {
      "name": "researcher",
      "output_file": "docs/sessions/20251104-090420-researcher.md",
      "summary": "Recommended PyJWT with Redis",
      "next_suggested": "planner",
      "key_findings": ["Finding 1", "Finding 2"]
    }
  ],
  "context": {
    "feature_description": "...",
    "project_md_aligned": true
  }
}
```

**Validation Logic**:
- Check feature similarity
- Validate file exists
- Check freshness (< 24 hours)
- Ask user if uncertain

---

## Comparison Matrix

| Pattern | File-Based | Resumable | Native CC | Token Savings | Complexity |
|---------|-----------|-----------|-----------|---------------|------------|
| **LangGraph Command** | ❌ | ❌ | ❌ | Low | High |
| **CrewAI Context** | ❌ | ❌ | ❌ | Low | Medium |
| **Handoff Protocol** | ✅ | ✅ | ❌ | 24% | High |
| **CC Transcripts** | ✅ | ✅ | ✅ | None | Low |
| **Anthropic Memory** | ✅ | ✅ | ❌ | High | High |
| **Schema Handoffs** | Depends | Depends | ❌ | Medium | Medium |
| **Our Chain Manifest** | ✅ | ✅ | ✅ | High | **Low** |

---

## Key Insights from Research

### What Works (Proven Patterns)

1. **File-based persistence** (Handoff Protocol, CC Transcripts, Anthropic Memory)
   - Resumable workflows
   - Survives restarts
   - Debuggable (can inspect files)

2. **Lightweight references** (Anthropic, Handoff Protocol)
   - Don't pass full context
   - Pass summaries + file paths
   - Massive token savings

3. **Structured metadata** (Handoff Protocol, Schema Handoffs)
   - Task status, decisions, next steps
   - Makes handoffs predictable
   - Enables validation

4. **Graceful degradation** (Implicit in best practices)
   - Ask user when uncertain
   - Validate before using chain
   - Fall back to normal operation

### What Doesn't Work

1. **In-memory only** (LangGraph, CrewAI)
   - Lost on restart
   - Not debuggable
   - Framework-dependent

2. **Full transcripts** (CC Transcripts)
   - High token usage
   - No metadata structure
   - Hard to extract key info

3. **Rigid schemas** (Schema Handoffs)
   - Maintenance overhead
   - Less flexible
   - Requires central validation

---

## Options for Our Implementation

### Option 1: Minimal - Extend CC Transcripts ⭐ **RECOMMENDED**

**Concept**: Use Claude Code's existing `agent-{agentId}.jsonl` pattern, add lightweight chain manifest

**Implementation**:
```json
// docs/sessions/.agent-chain.json
{
  "chain_id": "20251104-090420-jwt-auth",
  "feature": "JWT authentication",
  "agents": [
    {
      "name": "researcher",
      "transcript": "agent-researcher-abc123.jsonl",  // Use CC format
      "summary": "1-sentence summary",
      "next_suggested": "planner"
    }
  ]
}
```

**Pros**:
- ✅ Uses native Claude Code feature (JSONL transcripts)
- ✅ Minimal new code (just chain manifest)
- ✅ Backwards compatible
- ✅ **Lowest complexity**

**Cons**:
- ❌ Still stores full transcripts (high tokens)
- ❌ Less token savings than Handoff Protocol

**Effort**: 1-2 days

---

### Option 2: Handoff Protocol Lite

**Concept**: Borrow Handoff Protocol structure, skip MCP server

**Implementation**:
```json
// docs/sessions/{chain_id}-{agent_name}-handoff.json
{
  "agent": "researcher",
  "task": {
    "objective": "Research JWT auth",
    "status": "completed",
    "progress": "Found PyJWT library recommended"
  },
  "key_findings": ["Finding 1", "Finding 2"],
  "files_referenced": [
    {"path": "src/auth.py", "relevance": "Existing auth"}
  ],
  "decisions": [
    {"decision": "Use PyJWT", "rationale": "Most maintained"}
  ],
  "next_steps": ["Write plan"]
}
```

**Chain manifest**:
```json
{
  "chain_id": "...",
  "agents": [
    {
      "name": "researcher",
      "handoff_file": "20251104-researcher-handoff.json"
    }
  ]
}
```

**Pros**:
- ✅ Structured handoff data (like proven Handoff Protocol)
- ✅ High token savings (24%+ like MCP version)
- ✅ No MCP server needed
- ✅ Rich metadata (decisions, next steps)

**Cons**:
- ❌ More complex than Option 1
- ❌ Custom format (not CC native)

**Effort**: 2-3 days

---

### Option 3: Hybrid - Chain Manifest + Summaries

**Concept**: Chain manifest with agent summaries (no full transcripts)

**Implementation**:
```json
// docs/sessions/.agent-chain.json
{
  "chain_id": "...",
  "feature": "JWT authentication",
  "agents": [
    {
      "name": "researcher",
      "completed": "2025-11-04T09:08:15Z",
      "summary": "Recommended PyJWT with Redis for token storage",
      "key_outputs": {
        "recommended_library": "PyJWT",
        "storage_solution": "Redis",
        "security_considerations": ["Use RS256", "Rotate keys"]
      },
      "files_written": [
        "docs/sessions/20251104-researcher-findings.md"
      ],
      "next_suggested": "planner"
    }
  ],
  "validation": {
    "feature_match": true,
    "files_exist": true,
    "freshness": "< 4 hours"
  }
}
```

**Pros**:
- ✅ **Best token efficiency** (summaries only)
- ✅ Rich structured data for next agent
- ✅ Graceful degradation built-in (validation)
- ✅ Resumable + debuggable

**Cons**:
- ❌ Medium complexity (custom format)
- ❌ Requires agents to write good summaries

**Effort**: 2-3 days

---

### Option 4: Full Handoff Protocol (MCP Server)

**Concept**: Implement complete Handoff Protocol with MCP server

**Implementation**: As described in Black Dog Labs article

**Pros**:
- ✅ Proven approach (24% token savings)
- ✅ Full featured (decisions, next steps, file ranges)
- ✅ MCP integration

**Cons**:
- ❌ High complexity (MCP server setup)
- ❌ Overkill for our needs
- ❌ Requires users to install MCP server

**Effort**: 5-7 days

---

## Recommendation: Option 3 (Hybrid)

### Why Option 3?

**Balances all priorities**:
- ✅ File-based (resumable like Handoff Protocol)
- ✅ High token savings (summaries like Anthropic Memory)
- ✅ Graceful degradation (validation logic)
- ✅ Native to our system (no external dependencies)
- ✅ Reasonable complexity (2-3 days)

**Borrows best patterns**:
1. **File-based persistence** (Handoff Protocol, CC Transcripts) → Chain manifest
2. **Lightweight references** (Anthropic, Handoff Protocol) → Summaries + file paths
3. **Structured metadata** (Handoff Protocol) → key_outputs, validation
4. **Graceful degradation** (Best practices) → Validation checks + user questions

**Fits our use case**:
- Users run manual commands: `/research` → `/plan` → `/implement`
- Agents auto-detect chain and use previous context
- Falls back gracefully when chain irrelevant/stale
- Works with or without `/auto-implement`

---

## Implementation Plan (Option 3)

### Phase 1: Core Infrastructure (Day 1)

**1.1 Create chain manifest utility** (`lib/agent_chain.py`):
```python
class AgentChain:
    def __init__(self):
        self.chain_file = Path("docs/sessions/.agent-chain.json")

    def exists(self) -> bool
    def create(self, feature: str) -> str  # Returns chain_id
    def get_latest_agent(self) -> dict
    def add_agent(self, agent_name: str, summary: str, key_outputs: dict, **kwargs)
    def validate(self) -> dict  # Returns validation results
    def is_fresh(self, max_age_hours: int = 24) -> bool
    def feature_matches(self, requested_feature: str) -> float  # 0-1 similarity
```

**1.2 Create validation logic**:
```python
def validate_chain_for_agent(chain: AgentChain, feature: str) -> dict:
    """
    Returns:
        {
            "valid": True/False,
            "feature_match": 0-1 score,
            "files_exist": True/False,
            "freshness": "< 4 hours" | "> 24 hours",
            "recommendation": "use" | "ask_user" | "ignore"
        }
    """
```

**1.3 Test utilities**:
- Unit tests for chain creation, updates, validation
- Test parallel chains (multiple features)
- Test edge cases (missing files, stale chains)

### Phase 2: Agent Integration (Day 2)

**2.1 Update agent prompts** (7 agents):

Add this section to each agent markdown:

```markdown
## Chain Detection (Auto-Coordination)

**STEP 0: Check for Agent Chain**

Before starting work:

1. Check if `docs/sessions/.agent-chain.json` exists:
   ```python
   from lib.agent_chain import AgentChain, validate_chain_for_agent

   chain = AgentChain()
   if chain.exists():
       validation = validate_chain_for_agent(chain, user_feature_request)

       if validation["recommendation"] == "use":
           # Auto-use chain context
           previous_agent = chain.get_latest_agent()
           print(f"📎 Continuing chain: {chain.chain_id}")
           print(f"   Using context from: {previous_agent['name']}")
           # Read their summary and key_outputs

       elif validation["recommendation"] == "ask_user":
           # Chain exists but uncertain - ask user
           print(f"⚠️  Found chain about '{chain.feature}' but you're asking about '{user_feature_request}'")
           print(f"   Continue that chain or start fresh?")
           # Use AskUserQuestion tool

       else:  # "ignore"
           # Chain too stale or irrelevant
           print(f"🆕 Starting fresh (existing chain not relevant)")
   ```

2. If chain is relevant, read previous agent's context:
   ```python
   prev = chain.get_latest_agent()
   summary = prev["summary"]  # 1-sentence overview
   key_outputs = prev["key_outputs"]  # Structured data
   files = prev.get("files_written", [])  # Output files to read
   ```

3. Work with that context in mind

**STEP FINAL: Update Chain**

After completing work:

```python
chain.add_agent(
    agent_name="researcher",  # Your agent name
    summary="1-sentence summary of what you did",
    key_outputs={
        "recommended_approach": "PyJWT library",
        "security_notes": ["Use RS256", "Rotate keys"],
        # ... agent-specific structured data
    },
    files_written=["docs/sessions/20251104-researcher.md"],
    next_suggested="planner"  # Logical next agent
)
```
```

**2.2 Per-agent key_outputs**:

Define what each agent should output:

- **Researcher**: `recommended_approach`, `alternatives`, `security_notes`, `codebase_patterns`
- **Planner**: `components`, `file_structure`, `dependencies`, `integration_points`
- **Test-master**: `test_files`, `coverage_target`, `test_count`
- **Implementer**: `files_modified`, `tests_passing`, `implementation_notes`
- **Reviewer**: `issues_found`, `quality_score`, `suggestions`
- **Security-auditor**: `vulnerabilities`, `security_score`, `fixes_needed`
- **Doc-master**: `docs_updated`, `changelog_entry`

### Phase 3: Testing & Validation (Day 3)

**3.1 Integration tests**:
```bash
# Test full manual chain
/research "JWT authentication"
# Verify chain created

/plan "JWT authentication"
# Verify auto-detected chain, used research context

/test-feature "JWT authentication"
# Verify used plan context

/implement "JWT authentication"
# Verify used tests
```

**3.2 Edge case tests**:
- Different feature while chain exists
- Missing output files
- Stale chain (24+ hours old)
- Parallel chains (2 features simultaneously)

**3.3 Validation**:
- Token usage comparison (manual chain vs `/auto-implement`)
- User experience (does auto-detection feel natural?)
- Error rate (how often does validation catch issues?)

### Phase 4: Documentation (Day 3)

**4.1 User documentation**:
- Update README.md with agent chain feature
- Add examples of manual command chains
- Document when to use manual vs `/auto-implement`

**4.2 Troubleshooting**:
- How to view active chains: `cat docs/sessions/.agent-chain.json | jq`
- How to clear stale chains: `rm docs/sessions/.agent-chain.json`
- How to manually continue old chain: Agent prompts handle this automatically

---

## Success Metrics

After implementation:

1. **Adoption**: % of manual commands that successfully use chain detection
2. **Accuracy**: % of chains where validation correctly predicted use/ask/ignore
3. **Token savings**: Compare manual chain token usage vs baseline
4. **User satisfaction**: Survey users on manual command UX improvement
5. **Completion rate**: % of chains that reach final agent (doc-master)

**Target Goals**:
- 80%+ adoption (users use manual chains instead of just `/auto-implement`)
- 90%+ validation accuracy (rarely asks user unnecessarily)
- 30%+ token savings vs passing full transcripts
- 4+ user satisfaction score (out of 5)
- 60%+ completion rate (chains finish full workflow)

---

## Conclusion

**Option 3 (Hybrid Chain Manifest) is recommended** because:

1. ✅ Borrows proven patterns from industry (Handoff Protocol, Anthropic Memory, Claude Code Transcripts)
2. ✅ Native to our system (no external dependencies)
3. ✅ Balanced complexity (2-3 days, not 1 week)
4. ✅ High token savings (summaries vs full transcripts)
5. ✅ Graceful degradation (validation logic prevents errors)
6. ✅ Resumable and debuggable (file-based)
7. ✅ Works with existing architecture (agents, session files)

**Next Steps**:
1. Review this research with team
2. Get approval for Option 3
3. Create GitHub issue with Phase 1-4 breakdown
4. Start implementation

---

**Research completed**: 2025-11-04
**Patterns analyzed**: 8 frameworks, 6 patterns
**Recommendation**: Option 3 - Hybrid Chain Manifest
