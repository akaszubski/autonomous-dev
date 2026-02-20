## Autonomous Development Plugin

This project uses the **autonomous-dev** plugin for Claude Code, providing AI-powered development automation.

**Use the right command for every action:**

| Action | Command | Why |
|--------|---------|-----|
| Code changes | `/implement "desc"` | Tests, security review, docs |
| Quick code fix | `/implement --quick "desc"` | Fast test + implement |
| GitHub issues | `/create-issue "desc"` | Research, dedup, alignment |
| Quality check | `/audit` | Coverage, security, docs |
| Alignment | `/align` | PROJECT.md validation |
| Doc updates | `/align --docs` | Sync docs with code |

**Direct editing is only for**: docs (.md), config (.json/.yaml), typos (1-2 lines).

**Context Management**:
- Clear context after EACH feature: `/clear`
- Without clearing: Context bloats to 50K+ tokens → System fails
- With clearing: Context stays under 8K tokens → Works for 100+ features

**Full Documentation**: `plugins/autonomous-dev/README.md` or `CLAUDE.md` (project root)
