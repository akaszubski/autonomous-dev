# How to Use Claude Code 2.0 Bootstrap

This guide explains how to apply ReAlign's Claude Code 2.0 setup to your own projects.

---

## Quick Start

### Option 1: Bootstrap a New Project

```bash
# 1. Clone ReAlign (or your fork)
git clone https://github.com/akaszubski/realign.git ~/realign

# 2. Create your new project
mkdir ~/my-awesome-project
cd ~/my-awesome-project
git init

# 3. Run bootstrap script
~/realign/scripts/bootstrap_project.sh .

# 4. Start coding!
# Claude will auto-format, test, and learn patterns
```

### Option 2: Bootstrap an Existing Project

```bash
# 1. Clone ReAlign
git clone https://github.com/akaszubski/realign.git ~/realign

# 2. Navigate to your existing project
cd ~/existing-project

# 3. Run bootstrap script
~/realign/scripts/bootstrap_project.sh .

# 4. Review and commit
git status
git add .claude/ .github/ scripts/
git commit -m "feat: add Claude Code 2.0 setup"
```

---

## What Gets Installed

### Generic Components (No ReAlign/MLX Specifics)

✅ **8 Agents** (`.claude/agents/`):
- `planner.md` - Architecture & design
- `researcher.md` - Web research
- `implementer.md` - Code implementation
- `test-master.md` - TDD + progression + regression
- `reviewer.md` - Code quality gate
- `security-auditor.md` - Security scanning
- `doc-master.md` - Documentation sync
- `ci-monitor.md` - CI/CD monitoring

✅ **5 Multi-Language Hooks** (`scripts/hooks/`):
- `auto_format.py` - Supports Python (black), JS (prettier), Go (gofmt)
- `auto_test.py` - Supports pytest, jest, go test
- `security_scan.py` - Secret detection, bandit, npm audit, gosec
- `pattern_curator.py` - Auto-learns coding patterns
- `auto_align_filesystem.py` - Keeps docs organized

✅ **2 GitHub Workflows** (`.github/workflows/`):
- `safety-net.yml` - Multi-language CI/CD
- `claude-code-validation.yml` - Structure validation

✅ **4 Core Files** (`.claude/`):
- `PROJECT.md` - Single source of truth
- `PATTERNS.md` - Auto-learned patterns
- `STATUS.md` - Health dashboard
- `STANDARDS.md` - Engineering standards
- `settings.json` - Hooks configuration

---

## Supported Languages

The bootstrap automatically detects your project language:

| Language | Detection | Tools Configured |
|----------|-----------|------------------|
| **Python** | `pyproject.toml`, `setup.py`, `requirements.txt` | black, isort, pytest, mypy, bandit |
| **JavaScript** | `package.json` (no TypeScript) | prettier, eslint, jest |
| **TypeScript** | `package.json` + TypeScript dependency | prettier, eslint, jest, tsc |
| **Go** | `go.mod` | gofmt, golint, go test, gosec |
| **Rust** | `Cargo.toml` | rustfmt, cargo test |

---

## What Happens After Bootstrap

### 1. Auto-Format on Write

Every time Claude writes code, it's automatically formatted:
```bash
# Python: black + isort
# JavaScript: prettier
# Go: gofmt
```

### 2. Auto-Test on Write

Tests run automatically when source files change:
```bash
# Python: pytest (related tests only)
# JavaScript: jest (related tests only)
# Go: go test (related packages only)
```

### 3. Security Scan

Every write is scanned for:
- API keys, tokens, passwords
- Security vulnerabilities (bandit, npm audit, gosec)
- Common anti-patterns

### 4. Pattern Learning

The `pattern-curator` hook learns from your code:
- Sees pattern 1-2 times → "Candidate" in PATTERNS.md
- Sees pattern 3+ times → "Validated" in PATTERNS.md
- Claude uses these patterns in future code

### 5. Documentation Alignment

`.md` files are automatically organized:
- Root: Only README, CHANGELOG, LICENSE, CLAUDE.md
- Everything else → `docs/` subdirectory

---

## Customization

### Edit PROJECT.md

This is your **single source of truth**:

```markdown
## VISION
**Purpose**: What is this project trying to achieve?

## REQUIREMENTS
1. Functional requirements
2. Non-functional requirements

## ARCHITECTURE
**Components**: High-level design
**Data Flow**: How data moves through system

## CURRENT FOCUS
**This Week**: Active tasks
**Blockers**: What's blocking progress
```

### Configure Hooks

Edit `.claude/settings.json`:

```json
{
  "hooks": [
    {
      "event": "PostToolUse",
      "matcher": {"tool": "Write", "file_pattern": "src/**/*.py"},
      "command": "python scripts/hooks/auto_format.py $CLAUDE_FILE_PATHS",
      "description": "Auto-format Python files"
    }
  ]
}
```

### Add Language-Specific Patterns

Edit `.claude/PATTERNS.md`:

```markdown
### Database Connection Pattern

\`\`\`python
def get_db():
    return DatabaseConnection(
        host=os.getenv("DB_HOST"),
        pool_size=10
    )
\`\`\`

**When to use**: All database access
**Status**: ✅ Validated (seen 5 times)
```

---

## Comparison: ReAlign vs Bootstrap

| Feature | ReAlign (Source) | Bootstrap (Generic) |
|---------|------------------|---------------------|
| **Language** | Python only | Python, JS, TS, Go, Rust |
| **Domain** | MLX training | Any project |
| **Agents** | 9 (includes system-aligner) | 8 (generic only) |
| **Hooks** | 11 (Python-specific) | 5 (multi-language) |
| **Skills** | 19 (includes MLX patterns) | 0 (you add your own) |
| **Patterns** | MLX, LoRA, DPO | Your patterns |

**Key Difference**: Bootstrap has **NO** ReAlign/MLX-specific content. It's a clean slate for your project.

---

## Syncing Updates from ReAlign

As ReAlign improves, you can sync updates:

```bash
# 1. Pull latest ReAlign
cd ~/realign
git pull

# 2. Re-run bootstrap in your project (safe, won't overwrite custom changes)
cd ~/my-project
~/realign/scripts/bootstrap_project.sh .

# 3. Review changes
git diff .claude/

# 4. Commit if desired
git add .claude/
git commit -m "chore: update Claude Code 2.0 setup from ReAlign"
```

**Note**: The script won't overwrite your `PROJECT.md`, `PATTERNS.md`, or custom changes. It only updates agents/hooks/workflows.

---

## Troubleshooting

### "Bootstrap template not found"

**Problem**: Script can't find `.claude/bootstrap-template/`

**Solution**:
```bash
# Make sure you're running from ReAlign root
cd ~/realign
./scripts/bootstrap_project.sh /path/to/target
```

### "Hooks not running"

**Problem**: Claude Code hooks aren't executing

**Solution**:
1. Check `.claude/settings.json` exists
2. Verify `scripts/hooks/*.py` are executable: `chmod +x scripts/hooks/*.py`
3. Check Claude Code settings in IDE/CLI

### "Language not detected"

**Problem**: Script shows "Unknown language"

**Solution**:
1. Create language marker file:
   - Python: `touch pyproject.toml` or `requirements.txt`
   - JavaScript: `npm init -y`
   - Go: `go mod init <module-name>`
2. Re-run bootstrap script

---

## Examples

### Example 1: New Python Library

```bash
mkdir my-python-lib
cd my-python-lib
git init

# Create Python marker
cat > pyproject.toml << EOF
[project]
name = "my-python-lib"
version = "0.1.0"
EOF

# Bootstrap
~/realign/scripts/bootstrap_project.sh .

# Result: Python-specific setup with black, pytest, mypy
```

### Example 2: Existing Node.js API

```bash
cd ~/existing-nodejs-api
# (already has package.json)

# Bootstrap
~/realign/scripts/bootstrap_project.sh .

# Result: JavaScript-specific setup with prettier, jest, eslint
```

### Example 3: Go Microservice

```bash
mkdir my-go-service
cd my-go-service
go mod init github.com/me/my-service

# Bootstrap
~/realign/scripts/bootstrap_project.sh .

# Result: Go-specific setup with gofmt, go test, gosec
```

---

## What NOT to Expect

❌ This bootstrap does **NOT** include:
- ReAlign-specific MLX patterns
- Training/fine-tuning logic
- LoRA, DPO, or other ML methods
- HuggingFace model discovery
- ReAlign's 19 domain-specific skills

✅ This bootstrap **DOES** include:
- Generic autonomous development setup
- Multi-language support
- Auto-format, auto-test, security scan
- Pattern learning from YOUR code
- Progressive disclosure (5,300 token budget)
- Specialized agents for planning, testing, reviewing

---

## Next Steps After Bootstrap

1. **Define Vision** - Edit `.claude/PROJECT.md` with your project goals
2. **Set Standards** - Customize `.claude/STANDARDS.md` for your team
3. **Start Coding** - Claude will auto-format, test, and learn
4. **Review Patterns** - Check `.claude/PATTERNS.md` after 1 week
5. **Monitor Health** - Review `.claude/STATUS.md` weekly
6. **Iterate** - As you code, the system learns and improves

---

## Getting Help

- **ReAlign Example**: See `~/realign/` for production usage
- **Issues**: Open issue in ReAlign repo (if using this version)
- **Customization**: Edit `.claude/settings.json`, agents, hooks as needed

---

**Happy autonomous coding! 🤖✨**
