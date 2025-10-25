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
4. Generate status report with visual progress bars

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

## Related Commands

- `/auto-implement "feature"` - Start autonomous development workflow
- `/align-project` - Check PROJECT.md alignment (read-only analysis)

## Philosophy

**Strategic visibility** - The /status command keeps you focused on PROJECT.md strategic goals, not random features. It answers:
- What have we accomplished?
- What goals are we neglecting?
- What should we work on next?

Use this command frequently to stay aligned with strategic direction.
