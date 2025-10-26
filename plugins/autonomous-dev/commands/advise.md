---
description: Get critical analysis and trade-off evaluation before making implementation decisions
---

# Advise - Critical Thinking Before Implementation

**Get expert analysis before committing to significant changes**

---

## Usage

```bash
/advise "Proposal or decision to analyze"
```

**Examples:**

```bash
/advise "Add real-time collaboration features"
/advise "Switch from REST to GraphQL"
/advise "Refactor to microservices architecture"
/advise "Add authentication with OAuth2"
/advise "Rewrite the parser in Rust"
```

**Time**: 2-5 minutes  
**Output**: Critical analysis with alignment score, pros/cons, alternatives, risks

---

## What You Get

### 1. Alignment Check
- Does this serve PROJECT.md goals?
- Alignment score (0-10)
- Conflicts with constraints or principles

### 2. Complexity Assessment
- Estimated effort (weeks, LOC, files)
- Complexity ratio vs current codebase
- Overengineering detection

### 3. Pros & Cons
- Benefits with evidence
- Risks with evidence
- Trade-off analysis

### 4. Alternative Approaches
- Simpler option (80/20 solution)
- More robust option (do it right)
- Hybrid option (best of both)

### 5. Risk Assessment
- Technical risks (scalability, security, performance)
- Project risks (timeline, scope, maintenance)
- Mitigation strategies

### 6. Recommendation
- PROCEED / PROCEED WITH CAUTION / RECONSIDER / REJECT
- Rationale and conditions
- Next steps

---

## When to Use

**✅ Use /advise for:**
- Major feature proposals
- Architecture decisions
- Technology choices (database, framework, library)
- Refactoring decisions
- Scope changes
- Adding new dependencies

**❌ Don't use /advise for:**
- Bug fixes (straightforward fixes)
- Implementation details (use /plan instead)
- Code review (use /review instead)
- Trivial changes

---

## Example: Real-Time Collaboration

```bash
/advise "Add real-time collaboration to the editor"
```

**Output:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL ANALYSIS: Real-Time Collaboration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Alignment with PROJECT.md

📊 Alignment Score: 3/10

✅ Serves Goals:
- (none directly)

⚠️ Conflicts with:
- Goal #2: "Keep editor simple and focused"
- Constraint: "Offline-first architecture"
- Scope: "Single-user editing focus" (PROJECT.md:42)

## Complexity Assessment

🔴 VERY HIGH

Estimated Effort: 4-6 weeks, 3000-5000 LOC, 15+ files
Complexity Ratio: 3000 LOC / 2000 LOC = 150% increase

Major additions:
- WebSocket server infrastructure
- Conflict resolution (OT or CRDT algorithms)
- User presence tracking
- Session management
- Reconnection logic

## Pros & Cons

### Pros ✅
1. Multiple users can edit simultaneously
2. See collaborators' cursors in real-time
3. Competitive feature vs other editors

### Cons ⚠️
1. Major architectural shift (offline → always-online)
2. 2.5x increase in codebase complexity
3. Ongoing maintenance burden (WebSocket, sessions)
4. Against stated "simplicity" principle
5. Requires always-on server (hosting costs)

## Trade-Off Analysis

If we proceed:
- ✅ Gain: Real-time collaboration
- ❌ Lose: Simplicity, offline-first
- ⏱️ Time: 4-6 weeks development

If we don't:
- ✅ Keep: Simple, offline-first
- ❌ Miss: Real-time collab
- ⏱️ Save: 4-6 weeks

## Alternative Approaches

### Option A: Share Session Feature
Implementation: Export/import editor state as JSON
Cost: 3 days, 200 LOC

Pros:
- 90% of collaboration benefit
- No server required
- Stays offline-first

Cons:
- Not truly real-time
- Manual sync step

Best for: Occasional collaboration, keeping simplicity

### Option B: Plugin System
Implementation: Allow third-party collab plugins
Cost: 2 weeks, 800 LOC

Pros:
- Users who want collab can add it
- Core stays simple
- Extensibility for other features

Cons:
- Plugin API complexity
- Still need to solve core problems

Best for: Modularity, let users choose

### Option C: Cloud Sync Only
Implementation: Auto-save to cloud, reload on other devices
Cost: 1 week, 300 LOC

Pros:
- Async collaboration
- Simple implementation
- No WebSocket complexity

Cons:
- Not real-time
- Last-write-wins conflicts

Best for: Same user, multiple devices

## Risk Assessment

### Technical Risks 🔧
1. **Conflict Resolution Bugs**
   - Impact: HIGH (data loss)
   - Likelihood: MEDIUM
   - Mitigation: Extensive testing, use proven CRDT library

2. **WebSocket Reliability**
   - Impact: MEDIUM (disconnections)
   - Likelihood: HIGH
   - Mitigation: Reconnection logic, offline fallback

### Project Risks 📋
1. **Scope Creep**
   - Impact: HIGH (derails roadmap)
   - Likelihood: VERY HIGH
   - Mitigation: Strictly scope to MVP

2. **Maintenance Burden**
   - Impact: MEDIUM (40% more complexity)
   - Likelihood: HIGH
   - Mitigation: Accept long-term cost

## Red Flags 🚩

- 🚩 150% increase in codebase (2000 → 5000 LOC)
- 🚩 Fundamental architecture change (offline → online)
- 🚩 Directly conflicts with "simplicity" goal
- 🚩 Out of stated scope (single-user → multi-user)

## Recommendation

⚠️ **RECONSIDER**

Rationale:
Real-time collaboration conflicts with your project's core 
principle of simplicity. It's a 150% complexity increase for a 
feature outside your stated scope.

Option A (Share Session) achieves 90% of the benefit with 5% 
of the cost and stays aligned with your goals.

If you must have real-time collab, you should UPDATE PROJECT.md 
to reflect this major scope change first.

If proceeding anyway, ensure:
1. Update PROJECT.md to reflect multi-user scope
2. Use proven CRDT library (don't build from scratch)
3. Accept 4-6 week timeline
4. Plan for ongoing WebSocket maintenance

Next Steps:
- [ ] Review alternative approaches (especially Option A)
- [ ] Decide if real-time is truly required
- [ ] If yes, update PROJECT.md scope and goals
- [ ] Get team buy-in on complexity increase

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analysis completed in 3 minutes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Why This Matters

**GenAI excels at:**
- ✅ Critical thinking (challenging assumptions)
- ✅ Trade-off analysis (weighing options)
- ✅ Risk identification (what could go wrong)
- ✅ Alternative generation (what else could we do)

**GenAI struggles with:**
- ❌ Writing perfect code (syntax errors)
- ❌ Understanding implicit context

**Use GenAI for thinking, not just typing.**

The `/advise` command helps you:
1. Catch scope creep early
2. Avoid overengineering
3. Stay aligned with project goals
4. Make informed decisions
5. Consider alternatives you might miss

---

## Integration with Workflow

**Recommended flow:**

```
1. /advise "Proposal"        ← Get critical analysis
2. Review recommendations    ← Make informed decision
3. /plan "Chosen approach"   ← Plan implementation
4. /auto-implement           ← Execute plan
```

**Example session:**

```bash
# Step 1: Get advice
/advise "Add caching layer with Redis"

# Output: "6/10 alignment, consider in-memory cache first"

# Step 2: Decide based on advice
# User chooses simpler in-memory cache

# Step 3: Plan the simpler approach
/plan "Add in-memory cache with LRU eviction"

# Step 4: Implement
/auto-implement
```

---

## Alignment Scoring Guide

**9-10/10**: Directly serves multiple goals, no conflicts  
→ **PROCEED** confidently

**7-8/10**: Serves at least one goal, minor/no conflicts  
→ **PROCEED** with normal caution

**5-6/10**: Tangentially related, some conflicts  
→ **PROCEED WITH CAUTION**, weigh trade-offs carefully

**3-4/10**: Doesn't serve goals, multiple conflicts  
→ **RECONSIDER**, explore alternatives

**0-2/10**: Against project principles  
→ **REJECT**, find different approach

---

## Best Practices

### Before Using /advise

1. ✅ **Read PROJECT.md** - Know your goals and constraints
2. ✅ **Have a clear proposal** - Specific > vague
3. ✅ **Know the context** - What problem are you solving?

### After Getting Advice

1. ✅ **Consider all alternatives** - Don't dismiss simpler options
2. ✅ **Challenge the recommendation** - Question the analysis
3. ✅ **Update PROJECT.md if needed** - Major changes = scope update
4. ✅ **Share with team** - Collaborative decisions

### Red Flags to Watch For

🚩 Alignment score < 5/10  
🚩 Complexity > 50% of current codebase  
🚩 Multiple "HIGH" risk items  
🚩 Conflicts with core principles  
🚩 Many red flag markers in output

---

## Common Scenarios

### Scenario 1: "Should we use X technology?"

```bash
/advise "Switch from SQLite to PostgreSQL"
```

**Advisor will analyze:**
- Does this serve performance goals?
- What's the migration cost?
- Are there simpler options (better indexing)?
- What are the trade-offs (complexity vs scalability)?

### Scenario 2: "Should we add X feature?"

```bash
/advise "Add user authentication system"
```

**Advisor will analyze:**
- Is this in scope?
- What's the complexity cost?
- Do we need full OAuth or is simple auth enough?
- What are the security implications?

### Scenario 3: "Should we refactor X?"

```bash
/advise "Refactor API layer to use GraphQL"
```

**Advisor will analyze:**
- What problem does this solve?
- Is REST with field selection sufficient?
- What's the migration timeline?
- Learning curve for team?

---

## Troubleshooting

### "Alignment score seems wrong"

**Solution**: Make sure PROJECT.md is up-to-date. Run `/align-project` first.

### "Analysis is too conservative"

**Reason**: Advisor is designed to challenge assumptions and prevent scope creep.  
**Solution**: If you're confident, proceed anyway. The analysis is advisory, not mandatory.

### "Want more detail on a specific aspect"

**Solution**: Ask follow-up questions:
```
"Can you elaborate on the complexity assessment?"
"What are more details on Alternative B?"
"What specific risks exist for scalability?"
```

### "Analysis takes too long"

**Reason**: Comprehensive analysis takes 2-5 minutes.  
**Solution**: For quick decisions, skip `/advise` and use judgment.

---

## Implementation

Invoke the **advisor** agent to perform critical analysis of the proposed decision or change.

The agent will:
1. Read PROJECT.md to understand goals and constraints
2. Analyze the proposal for alignment and complexity
3. Perform trade-off analysis
4. Generate alternative approaches
5. Identify risks and mitigation strategies
6. Provide recommendation with rationale

---

**Pro Tip**: Use `/advise` before every significant decision. It takes 3 minutes but can save weeks of work on the wrong approach.

**Remember**: The advisor is your critical thinking partner. It asks hard questions so you don't regret decisions later.
