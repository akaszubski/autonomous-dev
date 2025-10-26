# Professional Claude Code Methodology

**How to Use Claude Code for Consistent, High-Quality Results**

This guide documents the **methodology** for professional software engineering with Claude Code. It's not just about automation - it's about how you work with AI as a development partner.

**Source**: Anthropic best practices + real-world experience with autonomous-dev plugin

---

## 🎯 **Quick Reference: Professional Practices**

| Practice | Why It Matters | Your Plugin Support |
|----------|----------------|---------------------|
| **`/clear` after features** | Prevents context bloat | ✅ Built-in reminder |
| **Small batches (30-60 min)** | Fast feedback, high quality | ✅ `/auto-implement` optimized for this |
| **Trust + Verify** | Anthropic philosophy | ✅ Hooks validate outputs |
| **Warn, don't block** | Better UX, you control | ✅ `validate_session_quality.py` |
| **Use `/status` frequently** | Stay aligned with goals | ✅ Enhanced with quality checks |
| **Review warnings, decide** | Professional judgment | ✅ `exit 1` gives you control |
| **Iterate on quality** | Improve thin outputs | ✅ Warnings show what to improve |

---

## 📖 **Table of Contents**

1. [The Partnership Model](#1-the-partnership-model)
2. [The /clear Discipline](#2-the-clear-discipline)
3. [Trust, but Verify](#3-trust-but-verify)
4. [Warn, Don't Block](#4-warn-dont-block)
5. [Small Batch Development](#5-small-batch-development)
6. [The /status Habit](#6-the-status-habit)
7. [Quality Iteration](#7-quality-iteration)
8. [Common Pitfalls](#common-pitfalls)
9. [Success Patterns](#success-patterns)

---

## 1. The Partnership Model

**Core Principle:** Claude Code is a **partner**, not a replacement or a servant.

### ❌ **Wrong Mindset: Automation Model**

```
"Claude does everything, I just approve"
└─> Result: You lose context on what's happening
└─> Result: Can't debug when things go wrong
└─> Result: Don't learn, can't improve system
```

### ✅ **Right Mindset: Partnership Model**

```
You decide WHAT (requirements, goals, architecture)
Claude helps with HOW (research, implementation, details)
Hooks validate THAT (outputs meet standards)
```

### Example Workflow

**Bad (Automation):**
```bash
You: "Build a user management system"
Claude: [Implements everything]
You: "Okay, ship it"
[Later: bugs, unclear architecture, can't maintain]
```

**Good (Partnership):**
```bash
You: "I want to add user authentication. Let's start with research."

Claude: "Here are 3 approaches:
  1. JWT tokens (stateless, scalable)
  2. Session cookies (simple, server-side)
  3. OAuth (third-party, complex)

  For your project size, I recommend JWT. Thoughts?"

You: "JWT sounds good. How would it integrate with our existing API?"

Claude: [Researches codebase]
        "Your API uses Express middleware. JWT integrates as:
         - Middleware for auth
         - Routes for login/register
         - Database for user storage

         Want me to plan this out?"

You: "Yes, plan it."

Claude: [Creates plan with 5 components]

You: [Reviews plan] "Looks good, implement it."

Claude: [Implements → Tests → Documents]

You: [Reviews code] "Great, commit it."
```

**Key Difference:** You're involved at decision points, steering direction, but not micromanaging implementation.

---

## 2. The /clear Discipline

**Core Principle:** Context bloats over time. Clear it frequently to maintain quality.

### Why This Matters

```
Without /clear:
  Feature 1: 8K tokens → Quality: 95%
  Feature 2: 15K tokens → Quality: 85%
  Feature 3: 25K tokens → Quality: 70%
  Feature 4: 40K tokens → Quality: 50%
  Feature 5: FAILURE (context too large)

With /clear:
  Feature 1: 8K tokens → Quality: 95% → /clear
  Feature 2: 8K tokens → Quality: 95% → /clear
  Feature 3: 8K tokens → Quality: 95% → /clear
  Feature 4: 8K tokens → Quality: 95% → /clear
  Feature 5+: SCALES to 100+ features
```

### The Discipline

**After EVERY feature:**
```bash
# Complete work
git commit -m "feat: add user authentication"

# IMMEDIATELY clear context
/clear

# Start next feature fresh
"add rate limiting"
```

### What /clear Does

- **Clears conversation history** (not files!)
- **Resets context budget** to 0
- **Maintains performance** over many features
- **Prevents "forgetting"** over time

### What /clear Does NOT Do

- ❌ Delete your files
- ❌ Delete session logs (they persist)
- ❌ Reset your git history
- ❌ Remove installed plugins

### Red Flags (You Need /clear)

- Claude's responses are getting slower
- Claude is "forgetting" things you said earlier
- Claude is missing obvious patterns
- You're at feature #3+ without clearing
- Errors about context budget exceeded

### Plugin Support

autonomous-dev reminds you to `/clear` after features complete. **Listen to this reminder!**

---

## 3. Trust, but Verify

**Core Principle:** Trust Claude to produce quality, but verify outputs meet standards.

### Anthropic's Philosophy

From official Claude Code design principles:

> "**Trust the model** - Claude is smart, don't over-prescribe implementation"

This means:
- ✅ Give clear mission and output format
- ✅ Trust Claude to figure out HOW
- ✅ Validate OUTPUTS (not process)
- ❌ Don't prescribe exact bash commands
- ❌ Don't require detailed checkpoints
- ❌ Don't micromanage steps

### How This Works

**Layer 1: Trust**
```markdown
# Agent prompt (Anthropic-compliant)
"Document your research findings clearly in the session file.

Include:
- Patterns found
- Best practices with sources
- Security considerations
- Recommendations

Be thorough but concise."
```

**Layer 2: Verify**
```python
# Hook validates OUTPUT quality
def check_research_quality(session_content):
    has_patterns = "patterns:" in session_content
    has_sources = any(url in session_content for url in ["github.com", ".io"])
    has_recommendations = "recommend" in session_content

    return has_patterns and has_sources and has_recommendations
```

### What Gets Validated

Your hooks validate **outputs**, not **process**:

✅ **Tests exist** (file-based check)
✅ **Tests pass** (run pytest)
✅ **No secrets** (scan files)
✅ **Docs synced** (check content)
✅ **Session quality** (check markers in session files)

❌ **Don't validate:**
- Which agent ran when
- What exact commands were used
- Process checkpoints
- Step-by-step execution

### Why This Matters

**Process validation (doesn't work):**
```
"Agent must call checkpoint.py with exact JSON"
└─> Relies on AI following instructions perfectly
└─> Circular logic (need reliability to enforce reliability)
└─> High false positive rate (10-15%)
└─> Poor developer experience
```

**Output validation (works):**
```
"Session file must contain quality markers"
└─> Checks actual files (deterministic)
└─> Independent of AI reliability
└─> Low false positive rate (2-5%)
└─> Good developer experience
```

---

## 4. Warn, Don't Block

**Core Principle:** Let developers make decisions. Inform, don't command.

### Anthropic's Exit Code Strategy

```
exit 0: Silent success
exit 1: Warning (proceeds, shows to user)
exit 2: Block (only for critical issues)
```

### When to Use Each

**Exit 1 (Warning) - Use for quality issues:**
- Research seems thin (2/3 markers instead of 3/3)
- Planning appears incomplete
- Review phase missing
- Coverage below target (75% vs 80%)
- Documentation could be better

**Why:** Developer should decide if quality is acceptable for their context.

**Exit 2 (Block) - Use only for critical issues:**
- Secrets in code (security risk)
- Tests failing (broken code)
- Syntax errors (won't compile)
- PROJECT.md critical misalignment

**Why:** These are objectively wrong and should be fixed.

### Example: Quality Warning

```bash
$ git commit -m "feat: add caching"

⚠️  SESSION QUALITY WARNING

Research phase appears incomplete (2/3 quality markers)
  - Found: 2 patterns, 1 source
  - Expected: 3 patterns, 2-3 sources

OPTIONS:
1. Review session file: docs/sessions/latest.md
2. Improve research: "Can you expand on caching patterns?"
3. Proceed anyway (your call)

This is a WARNING, not a block.
```

**Developer can:**
- Fix it (improve quality)
- Proceed (quality acceptable for this feature)
- Investigate (check session file themselves)

**Key:** YOU control the decision. Hook INFORMS, not COMMANDS.

---

## 5. Small Batch Development

**Core Principle:** Small features → Quick iterations → Fast feedback → High quality

### The Problem with Large Batches

```
❌ Bad: "Implement complete user management system"
  └─> 3 hours of work
  └─> Context bloats to 40K tokens
  └─> Quality degrades over time
  └─> Hard to debug what went wrong
  └─> All-or-nothing (can't partially commit)
```

### The Solution: Small Batches

```
✅ Good: Break into small features

"Add user authentication" (30 min)
└─> Commit, /clear

"Add user permissions" (30 min)
└─> Commit, /clear

"Add user profiles" (30 min)
└─> Commit, /clear

"Add user settings" (30 min)
└─> Commit, /clear

Total: 2 hours, 4 high-quality commits
```

### Size Guidelines

**Ideal feature size:**
- Time: 30-60 minutes
- Context: < 8K tokens
- Changes: 50-300 lines of code
- Tests: 5-15 tests
- Commits: 1 feature = 1 commit

**Signs feature is too large:**
- Takes > 90 minutes
- Context warnings appear
- Multiple unrelated changes
- Hard to describe in 1 sentence
- "And also..." when describing it

**How to break it down:**
```
Too large: "Add user management"

Better:
1. "Add user registration endpoint"
2. "Add user login endpoint"
3. "Add password hashing"
4. "Add session management"
5. "Add user profile CRUD"
```

### Plugin Support

`/auto-implement` is optimized for 30-60 minute features:
- Research: ~5 min
- Planning: ~5 min
- TDD: ~5 min
- Implementation: ~10 min
- Review: ~2 min
- Security: ~2 min
- Docs: ~1 min
- **Total: ~30 min**

---

## 6. The /status Habit

**Core Principle:** Stay aligned with PROJECT.md strategic goals, not random features.

### Why /status Matters

Without regular status checks:
```
You implement: Random features that seem useful
Result: Scope creep, unfocused development, strategic drift
```

With regular status checks:
```
You implement: Features that advance PROJECT.md goals
Result: Focused development, measurable progress, strategic alignment
```

### When to Use /status

**Start of day:**
```bash
$ /status

PROJECT.md Progress:
  Security: 100% ✅
  Performance: 40%
  UX: 20%

Next Priority: Performance goal (lagging)

$ # Okay, I'll focus on performance today
```

**After each feature:**
```bash
$ "add rate limiting"
[feature complete]

$ /status

Performance: 40% → 60% ✅ (rate limiting added)

$ # Good, advancing the right goal
```

**End of day:**
```bash
$ /status

Today's Progress:
  - Performance: 40% → 80%
  - Completed: rate limiting, caching, connection pooling

Tomorrow's Priority:
  - Complete performance goal (20% remaining)
  - Start UX improvements (currently 20%)
```

### What /status Shows (v3.0+)

1. **Goal Progress** - % complete for each PROJECT.md goal
2. **Session Quality** - Recent sessions with quality markers
3. **Next Priorities** - Suggested features based on goal completion
4. **Quality Warnings** - Which sessions had thin outputs

### Plugin Support

Enhanced `/status` command shows:
- Visual progress bars for goals
- Last 3 sessions with quality indicators
- Warnings if research/planning/review missing
- Specific suggestions ("Consider running: /research")

---

## 7. Quality Iteration

**Core Principle:** When warned about quality, you can iterate to improve it.

### The Iteration Loop

```
Describe → Implement → Commit Attempt → Warning → Iterate → Commit
```

**Not:**
```
Describe → Implement → Commit Attempt → Blocked → Frustrated → Disable hooks
```

### Example Session

```bash
# 1. Implement feature
$ "add caching with Redis"
[Claude implements]

# 2. Try to commit
$ git commit -m "feat: add Redis caching"

⚠️  Warning: Research appears thin
    - Found 2 patterns, expected 3
    - Only 1 source cited, expected 2-3

# 3. Review what's missing
$ cat docs/sessions/latest-session.md
[See that research only mentioned cache-aside pattern,
 didn't compare alternatives or cite official Redis docs]

# 4. Iterate to improve
$ "Can you expand the research? Compare cache-aside with
   write-through and write-behind patterns. Also cite
   official Redis documentation."

[Claude adds detail]

# 5. Commit again
$ git commit -m "feat: add Redis caching"
✅ Session quality validated

$ /clear
```

### When to Iterate vs Proceed

**Iterate when:**
- Feature is important/complex
- You're unfamiliar with the technology
- Security is involved
- It's a public API
- Warning shows significant gap (0/3 markers vs 1/3)

**Proceed anyway when:**
- Feature is simple/familiar
- Time pressure exists
- You reviewed session and quality is acceptable
- Warning is borderline (2/3 markers vs 3/3)
- You plan to iterate later

**Key:** Your judgment, your decision.

---

## Common Pitfalls

### ❌ Pitfall #1: "I'll clear later"

**Problem:**
```
"I'm on a roll, I'll clear after a few more features"
└─> Context bloats
└─> Quality degrades
└─> Hard to debug what went wrong
```

**Solution:** `/clear` is **not optional**. Clear after EVERY feature, even if it feels like overkill.

---

### ❌ Pitfall #2: "I'll ignore the warning"

**Problem:**
```
[Warning appears]
"Eh, probably fine, I'll commit anyway"
└─> Quality debt accumulates
└─> Hard to debug later
└─> Eventually leads to rewrite
```

**Solution:** At least **look** at what's missing. You can proceed, but do it knowingly.

---

### ❌ Pitfall #3: "This feature is too small to commit"

**Problem:**
```
"This is just a small change, I'll group it with the next feature"
└─> Features grow larger
└─> Commits become harder to review
└─> Can't revert cleanly
```

**Solution:** Commit **every** feature, no matter how small. Small commits are good commits.

---

### ❌ Pitfall #4: "I'll disable strict mode for now"

**Problem:**
```
"Hooks are annoying, I'll turn them off temporarily"
└─> "Temporary" becomes permanent
└─> Quality degrades
└─> Eventually worse than no automation
```

**Solution:** If hooks are truly wrong, **fix the hooks**, don't disable them. Or switch to warn-only mode.

---

### ❌ Pitfall #5: "I don't need /status"

**Problem:**
```
"I know what I'm working on"
└─> Scope creep
└─> Random features
└─> Strategic drift
└─> PROJECT.md becomes outdated
```

**Solution:** Use `/status` at least **daily**. It takes 5 seconds and keeps you aligned.

---

## Success Patterns

### ✅ Pattern #1: The Daily Rhythm

```bash
# Morning
/status                    # What's the current state?
# Focus on highest priority goal

# During day
[Small feature]
git commit
/clear

[Small feature]
git commit
/clear

[Small feature]
git commit
/clear

# End of day
/status                    # What did I accomplish?
```

---

### ✅ Pattern #2: The Quality Check

```bash
# Before committing important features
git commit
[Warning appears]

# Don't ignore - investigate
cat docs/sessions/latest-session.md
[Review quality yourself]

# If truly thin, iterate
"Expand research with more patterns and sources"
[Claude improves]

# Commit with confidence
git commit
```

---

### ✅ Pattern #3: The Strategic Sprint

```bash
# Monday morning
/status
# Goal: Performance at 40%, target 80% by Friday

# Plan features that advance goal
"Add rate limiting"      → 40% → 50%
"Add caching"            → 50% → 65%
"Add connection pooling" → 65% → 80%

# Friday afternoon
/status
Performance: 80% ✅ Goal achieved for sprint
```

---

### ✅ Pattern #4: The Warning Dialogue

```bash
# Warning appears
⚠️  Planning phase incomplete

# Ask for specifics
"What's missing from the planning phase?"

Claude: "The plan doesn't include error handling
         approach or testing strategy."

# Iterate
"Add error handling and testing strategy to the plan"
[Claude adds detail]

# Commit
git commit ✅
```

---

## Metrics for Success

Track these to measure if the methodology is working:

**Weekly Metrics:**
- How many `/clear` commands used? (Should be ~= feature count)
- How many quality warnings received? (5-15% of commits is normal)
- How many warnings were iterated on vs proceeded? (Your choice)
- PROJECT.md goal progress % (Should increase steadily)

**Monthly Metrics:**
- Features completed per month (Should be 20-40 for solo dev)
- Quality trend (warnings increasing or decreasing?)
- Strategic alignment (goals advancing or drifting?)
- Context management (hitting token limits or staying under 8K?)

**Health Indicators:**

✅ **Healthy:**
- Regular `/clear` usage
- 5-15% warning rate
- Steady goal progress
- Most sessions have quality markers
- Context stays under 8K

⚠️ **Warning Signs:**
- Skipping `/clear`
- 30%+ warning rate (hooks too strict)
- 0% warning rate (hooks not working)
- Random features, no goal progress
- Context frequently exceeds 15K

---

## Conclusion

**Professional Claude Code usage is a discipline, not just automation.**

The methodology is:
1. **Clear after features** - Prevents context bloat
2. **Small batches** - Fast feedback, high quality
3. **Trust + Verify** - Let Claude work, validate outputs
4. **Warn, don't block** - You control decisions
5. **Check status** - Stay strategically aligned
6. **Iterate on quality** - Improve when it matters

**With this methodology:**
- ✅ 85-95% consistency (sustainable)
- ✅ Scales to 100+ features (proven)
- ✅ Professional quality (validated)
- ✅ Strategic alignment (PROJECT.md-driven)
- ✅ Low frustration (warnings, not blocks)

**Without this methodology:**
- ❌ Quality degrades over time
- ❌ Context bloats, Claude "forgets"
- ❌ Scope creep, strategic drift
- ❌ High frustration, plugin abandoned

**The choice is yours. The methodology works. Use it.**

---

**Last Updated**: 2025-10-26
**Version**: v3.0.2
**Maintainers**: autonomous-dev plugin team
