# Discord Announcement - Autonomous Dev v2.1.0

**Channel**: #plugins or #show-and-tell

---

## Message

🚀 **Autonomous Dev v2.1.0 Released!**

New Claude Code plugin for autonomous development with auto-bootstrapping knowledge base and PROJECT.md-first architecture.

**What it does**:
✅ Auto-formats code (black, prettier) on save
✅ Auto-runs tests when you change code
✅ Auto-scans for security vulnerabilities
✅ Auto-updates documentation
✅ Auto-creates GitHub Issues from failures

**NEW in v2.1.0 - Knowledge Base System**:
🎯 Auto-bootstraps with Claude Code 2.0 best practices
📚 Caches research findings (90% faster on repeat topics)
💰 67% cost savings on repeat research

**Features**:
• 8 specialized agents (orchestrator → planner → researcher → test-master → implementer → reviewer → security → docs)
• 21 commands (/test, /commit, /align-project, etc.)
• 6 skills (python-standards, testing-guide, security-patterns, etc.)
• Cost-optimized (Opus for planning, Haiku for routine tasks)
• Works with Python, JS, TS, Go

**Installation**:
```
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```
(Exit and restart Claude Code)

**Links**:
📖 Repo: https://github.com/akaszubski/autonomous-dev
📚 Docs: https://github.com/akaszubski/autonomous-dev/blob/main/plugins/autonomous-dev/README.md
⚡ Quickstart: https://github.com/akaszubski/autonomous-dev/blob/main/plugins/autonomous-dev/QUICKSTART.md

**Unique features**:
• Only plugin with auto-bootstrapping knowledge base
• Only plugin with PROJECT.md alignment validation
• Only plugin with 3-layer testing (code + GenAI + meta)

Feedback welcome! ⭐ the repo if you find it useful!

---

## Follow-up (if questions asked)

**Q: How does the knowledge base work?**
A: On first run, researcher agent auto-bootstraps templates with Claude Code 2.0 best practices. When you ask questions, it checks cached research first (7-day TTL) before searching the web. Saves 90% time + 67% cost on repeat topics.

**Q: What's PROJECT.md-first architecture?**
A: Every feature gets validated against your PROJECT.md goals before implementation. Prevents scope creep. orchestrator agent checks alignment, planner designs architecture, test-master writes tests FIRST, implementer makes them pass.

**Q: Does it work with my language?**
A: Yes! Python (black, isort, pytest), JavaScript (prettier, jest), TypeScript (prettier, jest), Go (gofmt, go test), or generic projects.

**Q: What are the hooks?**
A: Optional. Run `/setup` to enable auto-format on save, auto-test on code change, coverage enforcement, security scanning. Or skip setup and use commands manually.

**Q: How much does it cost?**
A: Free and open source (MIT license). The agents use different models to optimize cost (Opus for complex planning, Sonnet for implementation, Haiku for routine tasks like security and docs).
