# /status - View PROJECT.md Goal Progress

Show current progress on PROJECT.md strategic goals, active workflows, and suggested next priorities.

## What This Does

Displays an at-a-glance view of:
- **Goal Progress**: Completion percentage for each PROJECT.md goal
- **Active Workflows**: Currently running autonomous workflows
- **Recent Activity**: Last completed feature
- **Next Priorities**: Suggested features based on goal progress

## Usage

```bash
/status
```

## Output Format

```
PROJECT.md Goal Progress:

Enhanced UX:          [████████░░] 80% (4/5 features)
Security:             [██████████] 100% ✅ COMPLETE
Performance:          [██░░░░░░░░] 20% (1/5 features)
Maintainability:      [░░░░░░░░░░] 0% (0/3 features)

Active Workflows: 0
Last Feature: "Add OAuth login" (2 hours ago)

Next Priorities:
1. Add keyboard shortcuts (completes Enhanced UX goal → 100%)
2. Add rate limiting (advances Performance goal → 40%)
3. Start maintainability work (currently at 0%)
```

## Implementation

Invoke the project-progress-tracker agent to analyze project status and goal completion.

The agent will:
1. Read and parse PROJECT.md
2. Analyze goal completion metadata
3. Calculate progress for each goal
4. Check recent session quality
5. Generate status report with visual progress bars and quality indicators

## Examples

### After Completing a Feature

```bash
/auto-implement "Add dark mode toggle"
# ... autonomous workflow executes ...

/status

PROJECT.md Goal Progress:

Enhanced UX:          [████████░░] 80% (4/5 features)
  ✅ Responsive design
  ✅ Accessibility improvements
  ✅ Dark mode toggle (NEW!)
  ✅ User preferences persistence
  ⏳ Keyboard shortcuts

Security:             [██████████] 100% ✅ COMPLETE
Performance:          [██░░░░░░░░] 20% (1/5 features)

Next Priority: Add keyboard shortcuts (completes UX goal)
```

### During Active Development

```bash
/status

Active Workflows:
- workflow-abc123: "Add rate limiting" (60% complete, implementer phase)

PROJECT.md Goal Progress:
Performance:          [████░░░░░░] 40% (2/5 features - in progress)

Estimated completion: 3 minutes
```

### Session Quality Check

```bash
/status

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 PROJECT.md Goal Progress
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Enhanced UX:          [████████░░] 80% (4/5 features)
Security:             [██████████] 100% ✅ COMPLETE
Performance:          [██░░░░░░░░] 20% (1/5 features)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Recent Session Quality
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Last 3 sessions:
  ✅ session-20251026-200515.md (5 min ago)
     • Research: ✅ 4/3 quality markers
     • Planning: ✅ 5/3 quality markers
     • Review: ✅ 3/2 quality markers
     • Security: ✅ 2/1 quality markers

  ✅ session-20251026-195230.md (15 min ago)
     • Research: ✅ 3/3 quality markers
     • Planning: ✅ 4/3 quality markers
     • Review: ✅ 2/2 quality markers
     • Security: ✅ 1/1 quality markers

  ⚠️  session-20251026-190845.md (1 hour ago)
     • Research: ⚠️ 2/3 quality markers (thin)
     • Planning: ✅ 3/3 quality markers
     • Review: ❌ 0/2 quality markers (missing!)
     • Security: ✅ 1/1 quality markers

     → Review phase appears incomplete
     → Consider running: /review

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Next Actions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Add keyboard shortcuts (completes Enhanced UX goal)
2. Review session-20251026-190845.md for completeness
3. Consider re-running /auto-implement for incomplete work
```

## Related Commands

- `/auto-implement "feature"` - Start autonomous development workflow
- `/align-project` - Check PROJECT.md alignment (read-only analysis)

## Philosophy

**Strategic visibility** - The /status command keeps you focused on PROJECT.md strategic goals, not random features. It answers:
- What have we accomplished?
- What goals are we neglecting?
- What should we work on next?

Use this command frequently to stay aligned with strategic direction.
