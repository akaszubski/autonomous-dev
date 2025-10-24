# Autonomous Dev v2.1.0 - Knowledge Base System + PROJECT.md-First Architecture

**TL;DR**: New plugin for autonomous development with auto-bootstrapping knowledge base, PROJECT.md alignment validation, and 8 specialized agents. Handles formatting, testing, security, and docs automatically so you can focus on features.

---

## 🚀 What It Does

Transform your Claude Code workflow with autonomous agents that handle the tedious work:

**Automatic Quality Enforcement**:
- ✅ Auto-formats code (black, prettier) on every save
- ✅ Auto-runs tests when you change code
- ✅ Auto-scans for security vulnerabilities
- ✅ Auto-updates documentation
- ✅ Auto-creates GitHub Issues from test failures

**Knowledge Base System** (NEW in v2.1.0):
- 🎯 Auto-bootstraps with Claude Code 2.0 best practices on first run
- 📚 Caches research findings (90% faster on repeat topics)
- 🔍 Search utilities with quality scoring and freshness checks
- 💰 67% cost savings on repeat research (7-day cache)

**PROJECT.md-First Architecture**:
- 🎯 Validates every feature against strategic goals before implementation
- 📋 Alignment check prevents scope creep
- 🔄 Agents coordinate via artifacts (200 tokens vs 5000+)

---

## 📦 Installation

```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
# Done! All commands work immediately.
```

Optional: Enable automatic hooks (format on save, test on change):
```bash
/setup
```

---

## 🤖 8 Specialized Agents

Cost-optimized model selection:

- **orchestrator**: Master coordinator (validates PROJECT.md alignment)
- **planner**: Architecture design (uses Opus for complex planning)
- **researcher**: Pattern discovery + web research (⭐ auto-bootstraps knowledge base)
- **test-master**: TDD specialist (writes tests FIRST!)
- **implementer**: Production code implementation
- **reviewer**: Quality gate (patterns, tests, docs)
- **security-auditor**: OWASP compliance (uses Haiku for cost efficiency)
- **doc-master**: Documentation sync (uses Haiku)

---

## 🎯 21 Discoverable Commands

**Testing** (7 commands):
- `/test` - All tests (unit + integration + UAT)
- `/test-unit` - Fast unit tests only
- `/test-integration` - Component integration
- `/test-uat` - User acceptance tests
- `/test-uat-genai` - GenAI UX validation
- `/test-architecture` - GenAI architecture drift detection
- `/test-complete` - Pre-release validation (all tests + GenAI)

**Commits** (4 commands):
- `/commit` - Quick commit (format + unit tests, <5s)
- `/commit-check` - Standard commit (all tests + coverage, <60s)
- `/commit-push` - Push commit (full integrity + doc sync, 2-5min)
- `/commit-release` - Release commit (complete validation + version bump, 5-10min)

**Alignment** (5 commands):
- `/align-project` - Check alignment (read-only)
- `/align-project-dry-run` - Preview fixes
- `/align-project-safe` - Interactive 3-phase fix
- `/align-project-fix` - Auto-fix (non-interactive)
- `/align-project-sync` - Safe alignment + GitHub sync

**And more**: Issues (5), Docs (5), Quality (3), Workflow (4)

---

## 🌟 What's New in v2.1.0

**Knowledge Base System**:
- Auto-bootstraps on first run (zero config!)
- Starter templates: Claude Code 2.0 best practices, agent search strategies
- Search utilities: `WebFetchCache`, `score_source()`, `score_pattern()`, `check_knowledge_freshness()`
- Template architecture: Following industry patterns (git, Docker, VSCode)
- Results: 90% time savings (1-2 min vs 15-20 min), 67% cost savings

**Before v2.1.0**:
```
User: "How do I structure agents in Claude Code 2.0?"
Researcher: [Searches web for 15-20 minutes, burns $0.30 in API costs]
```

**After v2.1.0**:
```
User: "How do I structure agents in Claude Code 2.0?"
Researcher: [Checks knowledge base, finds cached answer in 1-2 minutes, costs $0.10]
```

---

## 💡 Why This Plugin?

**For Solo Developers**:
- Zero-config knowledge base (get best practices automatically)
- 90% faster research on repeat topics (saves time + API costs)
- Auto-format, test, and secure code (focus on features)

**For Teams**:
- PROJECT.md alignment ensures everyone stays on track
- Shared knowledge base (optional via git)
- Consistent code quality (automatic enforcement)
- Progressive commit workflow (quick to full release)

**For Enterprises**:
- Security scanning (OWASP compliance)
- Automatic documentation (API docs, CHANGELOG)
- GitHub integration (auto-create issues)
- Audit trail (session logs)

---

## 🔍 Unique Selling Points

1. **Only plugin** with auto-bootstrapping knowledge base
2. **Only plugin** with PROJECT.md-first alignment validation
3. **Only plugin** with 3-layer testing (code + GenAI + meta)
4. **Cost-optimized** agent models (opus for planning, haiku for routine)
5. **Template architecture** follows industry patterns (git, Docker, VSCode)

---

## 📚 Documentation

- **Quickstart**: [QUICKSTART.md](https://github.com/akaszubski/autonomous-dev/blob/main/plugins/autonomous-dev/QUICKSTART.md)
- **Architecture**: [ARCHITECTURE.md](https://github.com/akaszubski/autonomous-dev/blob/main/plugins/autonomous-dev/ARCHITECTURE.md)
- **Full README**: [README.md](https://github.com/akaszubski/autonomous-dev/blob/main/plugins/autonomous-dev/README.md)
- **Changelog**: [CHANGELOG.md](https://github.com/akaszubski/autonomous-dev/blob/main/CHANGELOG.md)

---

## 🛠️ Supported Languages

Works with any project:
- ✅ Python (black, isort, pytest)
- ✅ JavaScript (prettier, jest)
- ✅ TypeScript (prettier, jest)
- ✅ Go (gofmt, go test)
- ✅ Generic projects (hooks, agents, skills, commands)

---

## 🎬 Example Workflow

```
User: "Add user authentication feature"

orchestrator:
  ✅ Checks PROJECT.md alignment
  ✅ Validates feature is in scope

planner (Opus):
  ✅ Designs architecture
  ✅ Creates implementation plan

test-master:
  ✅ Writes failing tests FIRST

implementer:
  ✅ Makes tests pass

reviewer:
  ✅ Checks code quality

security-auditor (Haiku):
  ✅ Scans for vulnerabilities

doc-master (Haiku):
  ✅ Updates API docs

Result: Production-ready feature with tests, docs, and security validation
```

---

## 🤝 Contributing

Feedback welcome! If you:
- Find bugs → [Open an issue](https://github.com/akaszubski/autonomous-dev/issues)
- Want features → [Start a discussion](https://github.com/akaszubski/autonomous-dev/discussions)
- Have improvements → [Read CONTRIBUTING.md](https://github.com/akaszubski/autonomous-dev/blob/main/CONTRIBUTING.md)

---

## 📊 Stats

- **Version**: 2.1.0
- **License**: MIT
- **Agents**: 8
- **Skills**: 6
- **Commands**: 21
- **Hooks**: 9
- **Commits**: 90+
- **Documentation**: 15+ files

---

## 🔗 Links

- **Repository**: https://github.com/akaszubski/autonomous-dev
- **Installation**: `/plugin marketplace add akaszubski/autonomous-dev`
- **Marketplace**: Listed at [Claude Code Commands Directory](https://claudecodecommands.directory)

---

**Star the repo if you find it useful!** ⭐

Questions? Comments? Let me know below! 👇
