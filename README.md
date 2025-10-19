# Claude Code 2.0 Autonomous Development Plugins

**Production-ready plugins for autonomous development**

🚀 **One-command install** • 🤖 **Generic or MLX-specific** • 📚 **Auto-format, auto-test** • 🔒 **Security scanning** • 🌍 **Multi-language**

---

## Quick Start

### Generic Autonomous Development (Works for ANY project)

```bash
# Add this marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install generic autonomous development setup
/plugin install autonomous-dev
```

### MLX/Apple Silicon Extensions (For LLM training)

```bash
# Install base plugin first
/plugin install autonomous-dev

# Then add MLX-specific extensions
/plugin install realign-mlx
```

**Done!** Claude now autonomously handles formatting, testing, documentation, and security.

---

## Available Plugins

### 🤖 autonomous-dev (Generic - Recommended for everyone)

**Works with**: Python, JavaScript, TypeScript, React, Node.js, and more!

**Includes**:
- ✅ 7 specialized agents (planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master)
- ✅ 6 core skills (python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards)
- ✅ 8 automation hooks (auto-format, auto-test, TDD enforcement, coverage enforcement, security scan)

**Perfect for**:
- Web applications (React, Next.js, Express)
- APIs (FastAPI, Django, Node.js)
- CLI tools
- Libraries
- Any Python/JavaScript/TypeScript project

[📖 Full autonomous-dev docs](plugins/autonomous-dev/README.md)

---

### 🍎 realign-mlx (MLX-specific - For LLM training)

**Requires**: autonomous-dev plugin (installed automatically)

**Adds**:
- ✅ 2 monitoring agents (system-aligner, ci-monitor)
- ✅ 7 MLX-specific skills (mlx-patterns, pattern-curator, requirements-analyzer, doc-migrator, architecture-patterns, github-sync, mcp-builder)
- ✅ 2 validation hooks (auto_align_filesystem, validate_standards)

**Perfect for**:
- LLM training on Apple Silicon (M1/M2/M3/M4)
- MLX framework projects
- ReAlign or similar training systems
- System health monitoring

[📖 Full realign-mlx docs](plugins/realign-mlx/README.md)

---

## What You Get

### Autonomous Development Workflow

```
You: "Add user authentication"

Claude automatically:
1. planner → Creates architecture plan
2. test-master → Writes FAILING tests (TDD enforced)
3. implementer → Makes tests PASS
4. reviewer → Quality gate check
5. security-auditor → Security scan
6. doc-master → Updates docs + CHANGELOG

All automatic. No manual steps.
```

### Auto-Everything

- **Auto-format**: Code formatted on every write (black, prettier, gofmt)
- **Auto-test**: Related tests run automatically
- **Auto-coverage**: 80%+ coverage enforced
- **Auto-security**: Secrets and vulnerabilities detected
- **Auto-docs**: Documentation synced with code

### Skills Auto-Activate

- Write Python → python-standards activates
- Write tests → testing-guide activates
- Handle API keys → security-patterns activates
- Use MLX → mlx-patterns activates (if realign-mlx installed)

---

## Installation Methods

### Method 1: Claude Code Plugin (Recommended)

```bash
# One command install
/plugin marketplace add akaszubski/claude-code-bootstrap
/plugin install autonomous-dev

# Updates are automatic
/plugin update autonomous-dev
```

**Benefits**:
- ✅ One-command installation
- ✅ Automatic updates
- ✅ Version management
- ✅ Easy to uninstall

### Method 2: Bootstrap Script (Legacy)

For projects that need custom setup or don't support plugins:

```bash
# Clone this repo
git clone https://github.com/akaszubski/claude-code-bootstrap.git

# Navigate to YOUR project
cd ~/your-project

# Run bootstrap
~/claude-code-bootstrap/bootstrap.sh .
```

**Use this if**:
- You need custom configuration
- You're on older Claude Code (<2.0)
- You want to modify files before installation

---

## What Gets Installed

Both methods install the same components to your project:

```
your-project/
├── .claude/
│   ├── agents/              # Specialized subagents
│   │   ├── planner.md       # Architecture & design
│   │   ├── researcher.md    # Web research
│   │   ├── test-master.md   # TDD + regression
│   │   ├── implementer.md   # Code implementation
│   │   ├── reviewer.md      # Quality gate
│   │   ├── security-auditor.md # Security scanning
│   │   └── doc-master.md    # Doc sync
│   ├── skills/              # Domain knowledge
│   │   ├── python-standards/
│   │   ├── testing-guide/
│   │   ├── security-patterns/
│   │   └── documentation-guide/
│   └── settings.json        # Hook configuration
└── scripts/hooks/
    ├── auto_format.py       # Auto-formatting
    ├── auto_test.py         # Auto-testing
    ├── auto_enforce_coverage.py # Coverage check
    └── security_scan.py     # Security scanning
```

---

## Comparison: Generic vs MLX

| Feature | autonomous-dev | + realign-mlx |
|---------|---------------|---------------|
| **Agents** | 7 core | +2 monitoring |
| **Skills** | 6 generic | +7 MLX-specific |
| **Hooks** | 8 automation | +2 validation |
| **Languages** | Python, JS, TS, Go, Rust | Python + MLX |
| **Use Case** | Any project | LLM training |
| **Apple Silicon** | Works | Optimized |

---

## Examples

### Example 1: Generic Web App

```bash
cd my-react-app
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with prettier
# ✓ Auto-test with jest
# ✓ 80% coverage enforcement
# ✓ Security scanning
# ✓ TDD workflow
```

### Example 2: LLM Training Project

```bash
cd my-mlx-project
/plugin install autonomous-dev    # Base autonomous development
/plugin install realign-mlx        # Add MLX-specific tools

# Claude now handles:
# ✓ Everything from autonomous-dev
# ✓ MLX pattern enforcement (model.model.layers[i])
# ✓ Memory management (mx.metal.clear_cache())
# ✓ System health monitoring
# ✓ CI/CD monitoring
```

### Example 3: Python CLI Tool

```bash
cd my-cli-tool
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with black + isort
# ✓ Auto-test with pytest
# ✓ Type hints enforcement
# ✓ Docstring validation
# ✓ Security scanning
```

---

## Production Example: ReAlign

These plugins were extracted from **ReAlign** - a production MLX training toolkit achieving:

- **98% alignment score**
- **80%+ test coverage** (enforced)
- **6 hours/week dev time** (vs 40 hours manual)
- **Fully autonomous development**

See it in action: [github.com/akaszubski/realign](https://github.com/akaszubski/realign)

---

## Documentation

| Guide | Purpose |
|-------|---------|
| **README.md** (this file) | Plugin marketplace overview |
| **[plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md)** | Generic plugin docs |
| **[plugins/realign-mlx/README.md](plugins/realign-mlx/README.md)** | MLX plugin docs |
| **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** | Technical deep-dive |
| **[USAGE.md](USAGE.md)** | Usage examples |

---

## FAQ

**Q: Which plugin should I use?**
A: Start with `autonomous-dev` for any project. Add `realign-mlx` only if you're training LLMs on Apple Silicon.

**Q: Can I use both plugins?**
A: Yes! `realign-mlx` extends `autonomous-dev` with MLX-specific tools.

**Q: Will it overwrite my existing code?**
A: No! Plugins only add `.claude/` and `scripts/hooks/`. Your code is untouched.

**Q: Can I customize the agents/hooks?**
A: Absolutely! After installation, edit `.claude/agents/*.md`, `scripts/hooks/*.py`, `.claude/settings.json` as needed.

**Q: Does this send my code anywhere?**
A: No. Everything runs locally. Hooks are just Python scripts on your machine.

**Q: How do I uninstall?**
A: `/plugin uninstall autonomous-dev` or manually delete `.claude/` and `scripts/hooks/`.

**Q: Can I use the old bootstrap script?**
A: Yes! The bootstrap script is still available for custom setups. See "Method 2" above.

**Q: Is this beginner-friendly?**
A: Yes! Just run `/plugin install autonomous-dev` and start coding. Claude handles everything else.

---

## Requirements

- **Claude Code**: 2.0.0 or higher
- **Python**: 3.11+ (for hooks)
- **Git**: For automation hooks

---

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Discussions**: [GitHub Discussions](https://github.com/akaszubski/claude-code-bootstrap/discussions)
- **Main Project**: [ReAlign Repository](https://github.com/akaszubski/realign)

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Credits

Extracted from [ReAlign](https://github.com/akaszubski/realign) v3.0.0 by [@akaszubski](https://github.com/akaszubski)

Powered by [Claude Code 2.0](https://claude.com/claude-code)

---

**🚀 Transform your development workflow in one command**

```bash
/plugin marketplace add akaszubski/claude-code-bootstrap
/plugin install autonomous-dev
```

**Happy autonomous coding! 🤖✨**
