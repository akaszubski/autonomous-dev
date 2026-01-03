## Autonomous Development Plugin

This project uses the **autonomous-dev** plugin for Claude Code, providing AI-powered development automation.

**Quick Reference**:
- `/clear` - Clear context after features (CRITICAL for performance)
- `/auto-implement` - Full development pipeline (research → plan → test → implement → review → security → docs)
- `/batch-implement` - Process multiple features sequentially
- `/align` - Check alignment with PROJECT.md goals
- `/worktree` - Manage git worktrees for isolated feature development

**Context Management**:
- Clear context after EACH feature: `/clear`
- Without clearing: Context bloats to 50K+ tokens → System fails
- With clearing: Context stays under 8K tokens → Works for 100+ features

**Full Documentation**: `plugins/autonomous-dev/README.md` or `CLAUDE.md` (project root)
