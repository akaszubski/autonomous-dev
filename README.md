# Claude Code 2.0 Bootstrap

**Production-ready autonomous development setup for ANY project**

Turn any codebase into an autonomous development environment where Claude handles formatting, testing, documentation, and learns your patterns automatically.

🚀 **5-minute setup** • 🤖 **Auto-format, auto-test** • 📚 **Pattern learning** • 🔒 **Security scanning** • 🌍 **Multi-language**

---

## What You Get

✅ **8 Specialized AI Agents** - planner, researcher, implementer, test-master, reviewer, security-auditor, doc-master, ci-monitor
✅ **5 Automation Hooks** - Auto-format (black/prettier/gofmt), auto-test (pytest/jest/go test), security scan, pattern learning
✅ **Multi-Language Support** - Python, JavaScript, TypeScript, Go, Rust
✅ **Progressive Disclosure** - 79% less context (5.3K vs 25K+ tokens)
✅ **Self-Improving** - Learns YOUR patterns automatically
✅ **80% Coverage Enforced** - Quality gates built-in

**Source**: Extracted from ReAlign (98% alignment, production-ready)

---

## Quick Start

### Option 1: Bootstrap Existing Project

```bash
# 1. Clone this repo
git clone https://github.com/akaszubski/claude-code-bootstrap.git

# 2. Navigate to YOUR project
cd ~/your-project

# 3. Run bootstrap
~/claude-code-bootstrap/bootstrap.sh .

# 4. Done! Claude now manages your project autonomously
```

### Option 2: Start New Project

```bash
# 1. Clone this repo
git clone https://github.com/akaszubski/claude-code-bootstrap.git

# 2. Create new project
mkdir ~/my-new-api && cd ~/my-new-api
git init
touch requirements.txt  # or package.json, go.mod, etc.

# 3. Run bootstrap
~/claude-code-bootstrap/bootstrap.sh .

# 4. Start coding with Claude!
```

---

## What Happens During Bootstrap

```
🔍 Detecting project language... Detected: Python

📦 Installing Claude Code 2.0 setup:
   ✓ 8 specialized agents
   ✓ 5 multi-language hooks
   ✓ 2 GitHub workflows
   ✓ 4 core documentation files
   
🎉 Bootstrap Complete!

Your project now has:
   • Auto-format on every write
   • Auto-test on every change
   • Security scan for secrets
   • Pattern learning (learns YOUR patterns)
   • Progressive disclosure (smart context loading)
```

---

## Supported Languages

| Language | Auto-Detected | Tools Configured |
|----------|---------------|------------------|
| **Python** | `pyproject.toml`, `requirements.txt` | black, isort, pytest, mypy, bandit |
| **JavaScript** | `package.json` | prettier, eslint, jest |
| **TypeScript** | `package.json` + TypeScript | prettier, eslint, jest, tsc strict |
| **Go** | `go.mod` | gofmt, golint, go test, gosec |
| **Rust** | `Cargo.toml` | rustfmt, clippy, cargo test |

---

## What Gets Installed

```
your-project/
├── .claude/
│   ├── agents/              # 8 specialized subagents
│   │   ├── planner.md       # Architecture & design
│   │   ├── researcher.md    # Web research
│   │   ├── implementer.md   # Code implementation
│   │   ├── test-master.md   # TDD + regression
│   │   ├── reviewer.md      # Quality gate
│   │   ├── security-auditor.md # Security scanning
│   │   ├── doc-master.md    # Doc sync
│   │   └── ci-monitor.md    # CI/CD monitoring
│   ├── PROJECT.md           # Single source of truth
│   ├── PATTERNS.md          # Auto-learned patterns
│   ├── STATUS.md            # Health dashboard
│   ├── STANDARDS.md         # Engineering principles
│   └── settings.json        # Hooks configuration
├── scripts/hooks/
│   ├── auto_format.py       # Multi-language formatting
│   ├── auto_test.py         # Test detection & execution
│   ├── security_scan.py     # Secret detection
│   ├── pattern_curator.py   # Pattern learning
│   └── auto_align_filesystem.py # Doc organization
└── .github/workflows/
    ├── safety-net.yml       # CI/CD
    └── claude-code-validation.yml # Structure validation
```

---

## How It Works

### 1. Auto-Format on Every Write

Claude writes code → Hook auto-formats:
```bash
Python: black + isort
JavaScript: prettier
Go: gofmt
```

### 2. Auto-Test on Every Change

Source file changes → Related tests run automatically:
```bash
Python: pytest tests/unit/test_<module>.py
JavaScript: jest <file>.test.js
Go: go test ./pkg/<package>
```

### 3. Security Scan

Every write scanned for:
- API keys, tokens, passwords
- SQL injection patterns
- Security vulnerabilities

### 4. Pattern Learning (Automatic!)

System learns YOUR patterns:
- Sees pattern 1-2 times → "🔄 Candidate"
- Sees pattern 3+ times → "✅ Validated"
- Claude uses validated patterns in future code

**Example**: After you write a database connection pattern 3 times, Claude learns it and applies it automatically to new code.

### 5. Progressive Disclosure

Each agent loads ONLY what it needs:
- Main agent: ~1,500 tokens
- Planner: ~5,600 tokens (vision + patterns)
- Implementer: ~4,700 tokens (architecture + patterns)

**79% less context** = Faster, cheaper, more focused.

---

## After Bootstrap

### 1. Customize Your Vision

Edit `.claude/PROJECT.md`:

```markdown
## VISION
**What**: A CLI tool for analyzing git repositories
**Why**: Understand code evolution and contributor patterns
**For whom**: Engineering managers

## REQUIREMENTS
1. Parse git log and extract commits
2. Generate contributor statistics
3. Visualize code churn over time
```

### 2. Start Coding

Claude will automatically:
- ✅ Format your code
- ✅ Run tests on changes
- ✅ Scan for security issues
- ✅ Learn patterns from your code
- ✅ Keep documentation aligned

### 3. Watch Patterns Emerge

Check `.claude/PATTERNS.md` after a week:

```markdown
### Database Connection Pattern (✅ Validated)

Seen: 5 times

\`\`\`python
def get_db():
    return DatabaseConnection(
        host=os.getenv("DB_HOST"),
        pool_size=10
    )
\`\`\`

**When to use**: All database access
**Status**: ✅ Validated
```

---

## Examples

### Example: Bootstrap a Node.js API

```bash
# Clone an existing API
git clone https://github.com/someone/api-project.git
cd api-project

# Bootstrap it
~/claude-code-bootstrap/bootstrap.sh .

# Output:
🔍 Detected: JavaScript
✓ Copied 8 agents
✓ Configured prettier, jest, eslint
🎉 Complete!

# Commit the setup
git add .claude/ .github/ scripts/
git commit -m "feat: add Claude Code 2.0 autonomous setup"

# Start coding - Claude handles the rest!
```

### Example: New Python Library

```bash
mkdir my-lib && cd my-lib
git init
touch requirements.txt

~/claude-code-bootstrap/bootstrap.sh .

# Output:
🔍 Detected: Python
✓ Configured black, pytest, mypy
🎉 Complete!

# Customize vision
vim .claude/PROJECT.md

# Start coding!
```

---

## Production Example: ReAlign

This bootstrap is extracted from **ReAlign** - a production MLX training toolkit achieving:

- 98% alignment score
- 80%+ test coverage (enforced)
- 6 hours/week dev time (vs 40 hours manual)
- Fully autonomous development

See it in action: [github.com/akaszubski/realign](https://github.com/akaszubski/realign)

---

## Documentation

| Guide | Purpose |
|-------|---------|
| **README.md** (this file) | Quick start guide |
| **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** | Complete technical explanation |
| **[USAGE.md](USAGE.md)** | Detailed usage examples |
| **[BOOTSTRAP_TEST_REPORT.md](BOOTSTRAP_TEST_REPORT.md)** | Test results (4 languages) |

---

## FAQ

**Q: Does this work with my language?**
A: Yes! Supports Python, JavaScript, TypeScript, Go, Rust. More languages coming soon.

**Q: Will it overwrite my existing code?**
A: No! Bootstrap only adds `.claude/`, `scripts/hooks/`, and `.github/workflows/`. Your code is untouched.

**Q: Can I customize the agents/hooks?**
A: Absolutely! Edit `.claude/agents/*.md`, `scripts/hooks/*.py`, `.claude/settings.json` as needed.

**Q: Does this send my code anywhere?**
A: No. Everything runs locally. Hooks are just Python scripts on your machine.

**Q: What if I don't like it?**
A: Just delete `.claude/`, `scripts/hooks/`, `.github/workflows/`. Your code is unchanged.

**Q: Is this beginner-friendly?**
A: Yes! Just run `./bootstrap.sh .` and start coding. Claude handles the complexity.

---

## Requirements

- Python 3.11+ (for hooks)
- Git
- Language-specific tools (installed automatically):
  - Python: `pip install black isort pytest mypy bandit`
  - JavaScript: `npm install -D prettier eslint jest`
  - Go: (built-in tools: gofmt, go test)

---

## Troubleshooting

### "Language not detected"

Add a language marker:
```bash
# Python
touch requirements.txt

# JavaScript
npm init -y

# Go
go mod init github.com/user/project
```

### "Hooks not running"

Check permissions:
```bash
chmod +x scripts/hooks/*.py
```

### "Bootstrap template not found"

Use absolute path:
```bash
/full/path/to/claude-code-bootstrap/bootstrap.sh .
```

---

## Support

- **Issues**: [github.com/akaszubski/claude-code-bootstrap/issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Discussions**: [github.com/akaszubski/claude-code-bootstrap/discussions](https://github.com/akaszubski/claude-code-bootstrap/discussions)
- **Source Example**: [ReAlign Project](https://github.com/akaszubski/realign)

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Credits

Extracted from [ReAlign](https://github.com/akaszubski/realign) v3.0.0 by [@akaszubski](https://github.com/akaszubski)

Powered by [Claude Code 2.0](https://claude.com/claude-code)

---

**🚀 Transform your development workflow in 5 minutes**

```bash
git clone https://github.com/akaszubski/claude-code-bootstrap.git
cd your-project
~/claude-code-bootstrap/bootstrap.sh .
```

**Happy autonomous coding! 🤖✨**
