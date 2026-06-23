---
name: status
description: View PROJECT.md goal progress with GenAI analysis and strategic recommendations
argument-hint: (no arguments needed)
allowed-tools: [Task, Read, Grep, Glob]
disable-model-invocation: true
user-invocable: true
user_facing: true
---

## Implementation

Invoke the project-progress-tracker agent to analyze goal completion and suggest strategic next priorities.

# Status - Project Goal Progress

**GenAI-powered strategic goal tracking and progress analysis**

---

## Usage

```bash
/status
```

**Time**: 30-60 seconds
**Interactive**: Shows progress, answers questions
**GenAI-Powered**: Uses project-progress-tracker agent for intelligent analysis

---

## How It Works

The project-progress-tracker agent analyzes your strategic direction:

### Analysis Phase

The agent:
- ✅ Reads PROJECT.md goals, scope, constraints
- ✅ Scans session logs for completed features
- ✅ Analyzes git history for feature implementation
- ✅ Calculates progress toward each goal
- ✅ Identifies neglected goals
- ✅ Suggests strategic next priorities

### Report Phase

Shows you:
- 📊 **Goal Progress**: Visual bars for each goal
- ✅ **Completed Features**: What's been accomplished
- ⏳ **In Progress**: What's currently being worked on
- 💡 **Strategic Recommendations**: What to do next
- ⚠️  **Risk Flags**: Neglected or drifting goals

---

## Example Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 PROJECT.md Goal Progress
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Enhanced UX:       [████████░░] 80% (4/5 features)
  ✅ Responsive design
  ✅ Accessibility improvements
  ✅ Dark mode toggle
  ✅ User preferences
  ⏳ Keyboard shortcuts (Next priority - 1 feature away!)

Security:          [██████████] 100% ✅ COMPLETE
  ✅ OAuth integration
  ✅ JWT tokens
  ✅ Password hashing
  ✅ CSRF protection

Performance:       [██░░░░░░░░] 20% (1/5 features)
  ✅ Basic caching
  ⏳ Rate limiting (should start soon)
  ⏳ Query optimization
  ⏳ Compression
  ⏳ CDN integration

Maintainability:   [░░░░░░░░░░] 0% (0/3 features)
  ⏳ Code organization
  ⏳ API versioning
  ⏳ Documentation structure

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Strategic Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Status Summary:
- ✅ Security: COMPLETE (maintain)
- ✅ Enhanced UX: Near completion (4/5 features)
- ⚠️  Performance: Neglected (only 1/5, should balance)
- ❌ Maintainability: Not started (0/3)

Overall: 42% complete (5/11 features)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Recommended Next Priorities
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ⭐ Add keyboard shortcuts
   Goal: Enhanced UX (80% → 100%)
   Impact: Completes a strategic goal
   Effort: medium
   Reason: One feature away from 100% completion

2. Add rate limiting
   Goal: Performance (20% → 40%)
   Impact: Improves stability, advances neglected goal
   Effort: high
   Reason: Performance is underserved (only 20%)

3. Start code organization
   Goal: Maintainability (0% → 33%)
   Impact: Begins new strategic area
   Effort: medium
   Reason: Maintainability not started (0%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Historical Progress
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Last 7 days:
  Day 1: Enhanced UX (40% → 60%)
  Day 2: Security (80% → 100%)
  Day 3: Enhanced UX (60% → 80%)
  Day 4-7: No progress (Performance needs work!)

Pace: Averaging 1.4 features per day
Trend: Good on UX, neglecting other goals

Next week: Focus on Performance to balance progress
```

---

## What the Agent Analyzes

### Goal Completion
- Counts completed features per goal
- Calculates percentage (features done / total planned)
- Marks goals 100% complete with ✅
- Flags goals under 20% as "neglected"

### Strategic Balance
- Are we completing goals evenly?
- Are some goals being neglected?
- Is there a risk of missing strategic direction?
- What would provide best overall progress?

### Next Priorities
- Which goal is closest to 100%? (finish it!)
- Which goal is neglected? (start balancing)
- What provides strategic value?
- What should we work on next?

### Risk Flags
- ⚠️ Goals under 20% progress (neglected)
- 🚨 Goals completely untouched (risk)
- 📉 Goals stalled for 7+ days
- 🔄 Scope drift detected (features not mapped to goals)

---

## Example Workflows

### First Feature Completed

```bash
# After implementing "Add OAuth login"
/status

OUTPUT:
Security: [██░░░░░░░░] 20% (1/5 features)
  ✅ Add OAuth login (NEW!)
  ⏳ Password reset
  ⏳ 2FA
  ⏳ Rate limiting
  ⏳ CSRF protection

💡 Recommend: Continue with password reset (momentum)
```

### Checking Strategic Alignment

```bash
# Mid-sprint, checking balance
/status

OUTPUT:
Enhanced UX:       [████████░░] 80% (4/5 features)  ← Near done
Performance:       [░░░░░░░░░░] 0% (0/5 features)   ← Neglected!
Maintainability:   [░░░░░░░░░░] 0% (0/3 features)   ← Not started

⚠️  Warning: Performance and Maintainability are completely untouched
💡 Recommend: After UX, focus on Performance (more neglected)
```

### After Completing a Goal

```bash
# Just finished "Add user preferences" (5th UX feature)
/status

OUTPUT:
Enhanced UX: [██████████] 100% ✅ COMPLETE

🎉 Goal completed! Moving focus to Performance (currently 20%)

💡 Recommend:
  1. Add rate limiting (Performance: 20% → 40%)
  2. Add query optimization (Performance: 40% → 60%)
```

---

## When to Use

**Run /status when**:
- 📊 Starting your day (see progress on strategic goals)
- ✅ Completing a feature (see updated progress)
- 🤔 Deciding what to work on next (gets strategic recommendations)
- 📈 Periodic check-ins (weekly/bi-weekly)
- 👥 Team meetings (show project progress)

**Output tells you**:
- Where are we strategically?
- What goals need attention?
- What should we do next?
- Are we balanced across goals?

---

## Integration with /auto-implement

After using `/auto-implement` to complete a feature:

```bash
# 1. Complete feature
/auto-implement "Add keyboard shortcuts"

# 2. Check updated progress
/status

# Shows: Enhanced UX now 100% complete! 🎉
# Recommends: Next priorities based on new state
```

---

## Understanding the Recommendations

The agent prioritizes based on:

**Priority 1**: Finish nearly-complete goals
- Goal at 80% or higher? Finish it!
- Psychology: Completing goals is motivating
- Impact: Full credit for strategic goal

**Priority 2**: Balance neglected goals
- Goal under 20%? Start making progress
- Risk: Neglected goals become technical debt
- Impact: Distribute effort across strategic areas

**Priority 3**: Address dependencies
- Some features unlock others
- Agent considers ordering
- Maximizes velocity

**Priority 4**: Effort vs. Impact
- Quick wins motivate teams
- High-impact features deliver value
- Balance between quick wins and deep work

---

## Safety Features

✅ **No modifications**: /status never changes anything
✅ **Pure analysis**: Shows progress, recommends direction
✅ **Clear reasoning**: Explains why recommendations
✅ **Strategic focus**: Keeps work aligned with goals

---

## Troubleshooting

### "PROJECT.md not found"

```bash
# Create PROJECT.md first
/setup

# Then check status
/status
```

### "No goals detected"

PROJECT.md exists but has no GOALS section:
```bash
# Update PROJECT.md with goals
vim PROJECT.md

# Add GOALS section with strategic objectives
/status
```

### "Progress not updating"

Progress is tracked in PROJECT.md. After completing features:
```bash
# Update PROJECT.md with completed features
# Then check status
/status
```

---

## Related Commands

- `/auto-implement "feature"` - Implement a feature strategically
- `/align-project` - Ensure implementation matches goals
- `/setup` - Create or update PROJECT.md

---

**Use this to understand strategic progress, identify goals needing attention, and get intelligent recommendations on what to work on next.**
