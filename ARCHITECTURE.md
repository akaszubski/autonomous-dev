# Plugin Architecture & How It All Works Together

## Overview

This repository provides **two Claude Code plugins** that work together to create a complete autonomous development environment:

1. **autonomous-dev** - Generic base (works for ANY project)
2. **realign-mlx** - MLX-specific extensions (for LLM training on Apple Silicon)

## Plugin Architecture

### Layer 1: Base Infrastructure (autonomous-dev)

**Purpose**: Generic autonomous development for any Python/JavaScript/TypeScript project

**Components**:
- 7 Generic Agents (planning, research, implementation, testing, review, security, documentation)
- 6 Core Skills (Python standards, testing methodology, security patterns, documentation, research, engineering)
- 8 Automation Hooks (formatting, testing, TDD enforcement, coverage, security scanning)

**Use Cases**:
- Web applications (React, Next.js, Express, FastAPI, Django)
- APIs and microservices
- CLI tools
- Libraries and packages
- ANY Python/JavaScript/TypeScript project

### Layer 2: Domain Extensions (realign-mlx)

**Purpose**: MLX-specific tools for LLM training on Apple Silicon

**Extends autonomous-dev with**:
- 2 Monitoring Agents (system health, CI/CD monitoring)
- 7 MLX Skills (MLX patterns, pattern curation, requirements analysis, documentation migration, architecture patterns, GitHub sync, MCP builder)
- 2 Validation Hooks (filesystem alignment, standards validation)

**Use Cases**:
- LLM training on M1/M2/M3/M4 chips
- MLX framework projects
- Apple Silicon optimization
- System health monitoring

## How They Work Together

### Scenario 1: Generic Web App

```bash
cd my-react-app
/plugin install autonomous-dev
```

**Result**:
```
your-project/
├── .claude/
│   ├── agents/
│   │   ├── planner.md           # ← From autonomous-dev
│   │   ├── researcher.md        # ← From autonomous-dev
│   │   ├── test-master.md       # ← From autonomous-dev
│   │   ├── implementer.md       # ← From autonomous-dev
│   │   ├── reviewer.md          # ← From autonomous-dev
│   │   ├── security-auditor.md  # ← From autonomous-dev
│   │   └── doc-master.md        # ← From autonomous-dev
│   ├── skills/
│   │   ├── python-standards/    # ← From autonomous-dev
│   │   ├── testing-guide/       # ← From autonomous-dev
│   │   ├── security-patterns/   # ← From autonomous-dev
│   │   └── documentation-guide/ # ← From autonomous-dev
│   └── settings.json
└── scripts/hooks/
    ├── auto_format.py           # ← From autonomous-dev
    ├── auto_test.py             # ← From autonomous-dev
    └── security_scan.py         # ← From autonomous-dev
```

**What Happens**:
1. Write code → auto_format.py formats it (black/prettier)
2. Save file → auto_test.py runs related tests
3. Commit → auto_enforce_coverage.py checks 80% coverage
4. Complex feature → planner agent creates architecture
5. Need research → researcher agent finds best practices
6. Security issue → security-auditor agent scans code

### Scenario 2: MLX Training Project

```bash
cd my-mlx-project
/plugin install autonomous-dev    # Install base
/plugin install realign-mlx        # Add MLX extensions
```

**Result**:
```
your-project/
├── .claude/
│   ├── agents/
│   │   ├── planner.md           # ← From autonomous-dev
│   │   ├── researcher.md        # ← From autonomous-dev
│   │   ├── test-master.md       # ← From autonomous-dev
│   │   ├── implementer.md       # ← From autonomous-dev
│   │   ├── reviewer.md          # ← From autonomous-dev
│   │   ├── security-auditor.md  # ← From autonomous-dev
│   │   ├── doc-master.md        # ← From autonomous-dev
│   │   ├── system-aligner.md    # ← From realign-mlx
│   │   └── ci-monitor.md        # ← From realign-mlx
│   ├── skills/
│   │   ├── python-standards/    # ← From autonomous-dev
│   │   ├── testing-guide/       # ← From autonomous-dev
│   │   ├── security-patterns/   # ← From autonomous-dev
│   │   ├── documentation-guide/ # ← From autonomous-dev
│   │   ├── mlx-patterns/        # ← From realign-mlx (NEW!)
│   │   ├── pattern-curator/     # ← From realign-mlx
│   │   └── mcp-builder/         # ← From realign-mlx
│   └── settings.json
└── scripts/hooks/
    ├── auto_format.py           # ← From autonomous-dev
    ├── auto_test.py             # ← From autonomous-dev
    ├── security_scan.py         # ← From autonomous-dev
    ├── auto_align_filesystem.py # ← From realign-mlx (NEW!)
    └── validate_standards.py    # ← From realign-mlx (NEW!)
```

**What Happens**:
1. Everything from autonomous-dev (formatting, testing, coverage, etc.)
2. **PLUS** MLX-specific validations:
   - Write `model.layers[i]` → mlx-patterns skill warns: use `model.model.layers[i]`
   - Memory leak → mlx-patterns skill suggests `mx.metal.clear_cache()`
   - Commit → auto_align_filesystem.py validates project structure
   - Weekly → system-aligner agent generates health report

## Component Details

### Agents (How They Work)

Agents are specialized AI assistants that auto-invoke for specific tasks:

```
You: "Add user authentication to my API"

Claude Code workflow:
1. planner agent → Creates architecture plan
2. test-master agent → Writes FAILING tests (TDD)
3. implementer agent → Makes tests PASS
4. security-auditor agent → Scans for vulnerabilities
5. reviewer agent → Code quality check
6. doc-master agent → Updates API documentation
```

**Key Points**:
- Agents run **automatically** when tasks match their expertise
- Each agent has specific knowledge and instructions
- Agents can invoke other agents (planner → test-master → implementer)
- You can manually invoke: `/use planner - design metrics dashboard`

### Skills (How They Work)

Skills are domain knowledge that auto-activates by keywords:

```python
# Writing Python code → python-standards skill activates
def process_data(items: List[Dict]) -> Result:  # ← Type hints enforced
    """Process data items."""                   # ← Docstring enforced

# Using MLX → mlx-patterns skill activates
layer_output = model.model.layers[i](x)  # ← Correct nested structure
mx.metal.clear_cache()                    # ← Memory management

# Handling secrets → security-patterns skill activates
api_key = os.getenv("API_KEY")  # ← Environment variable, not hardcoded
```

**Key Points**:
- Skills activate **automatically** based on context
- Provide "how-to" knowledge for specific domains
- Progressive disclosure: only loaded when needed (~300 tokens/skill)
- Generic skills (autonomous-dev) vs domain skills (realign-mlx)

### Hooks (How They Work)

Hooks are Python scripts that run automatically on file events:

```
Event: File Write
├─> auto_format.py runs → Formats code (black/prettier)
├─> auto_test.py runs → Runs related tests
└─> security_scan.py runs → Scans for secrets

Event: Git Commit
├─> auto_enforce_coverage.py runs → Checks 80% coverage
└─> validate_standards.py runs → Validates type hints, docstrings

Event: Git Push
└─> Full test suite runs → All tests must pass
```

**Key Points**:
- Hooks run **automatically** on events (no manual action)
- Written in Python for cross-platform compatibility
- Can be customized in `.claude/settings.json`
- Generic hooks (autonomous-dev) vs validation hooks (realign-mlx)

## Plugin Composition Patterns

### Pattern 1: Start Generic

```bash
# Day 1: Start with base
/plugin install autonomous-dev

# Week 2: Project needs MLX
/plugin install realign-mlx
```

**Benefit**: Add complexity only when needed

### Pattern 2: Full Stack From Start

```bash
# Install everything upfront
/plugin install autonomous-dev
/plugin install realign-mlx
```

**Benefit**: All tools available immediately

### Pattern 3: Generic Only (Most Common)

```bash
# Most projects only need base
/plugin install autonomous-dev
```

**Benefit**: Lightweight, no domain bloat

## Configuration After Installation

Both plugins install to `.claude/` directory. Customize via `.claude/settings.json`:

```json
{
  "hooks": {
    "on_file_write": [
      "auto_format.py",
      "auto_test.py",
      "security_scan.py"
    ],
    "pre_commit": [
      "auto_enforce_coverage.py",
      "validate_standards.py"
    ]
  },
  "permissions": {
    "allow": [
      {"tool": "Bash", "pattern": "pytest *"},
      {"tool": "Bash", "pattern": "black *"},
      {"tool": "Bash", "pattern": "git *"}
    ]
  }
}
```

**Customization Options**:
- Enable/disable specific hooks
- Change hook event triggers
- Add custom permissions
- Configure agent auto-invocation

## Version Management

### Plugin Updates

```bash
# Check for updates
/plugin list

# Update single plugin
/plugin update autonomous-dev

# Update all plugins
/plugin update --all
```

### Version Compatibility

- **autonomous-dev v1.x** - Generic, stable
- **realign-mlx v3.x** - Matches ReAlign v3.0.0 release
- Always use latest autonomous-dev with any realign-mlx version

## Comparison: Plugins vs Bootstrap Script

| Feature | Plugins | Bootstrap Script |
|---------|---------|------------------|
| **Installation** | One command | Clone + run script |
| **Updates** | Automatic | Manual re-run |
| **Version Control** | Built-in | Git tags |
| **Discoverability** | Plugin marketplace | GitHub search |
| **Customization** | After install | Before install |
| **Speed** | Instant | ~30 seconds |

**When to use bootstrap script**:
- Need heavy customization before install
- Offline installation
- Claude Code <2.0
- Want to inspect before installing

**When to use plugins** (recommended):
- Standard installation
- Want automatic updates
- Using Claude Code 2.0+
- Trust the source

## Real-World Examples

### Example 1: FastAPI Microservice

```bash
cd my-api
/plugin install autonomous-dev

# What you get:
# ✅ Auto-format with black
# ✅ Auto-test with pytest
# ✅ Security scanning (detect hardcoded keys)
# ✅ API documentation sync
# ✅ 80% coverage enforcement
```

### Example 2: React Dashboard

```bash
cd my-dashboard
/plugin install autonomous-dev

# What you get:
# ✅ Auto-format with prettier
# ✅ Auto-test with jest
# ✅ Component testing workflow
# ✅ TDD enforcement
# ✅ Documentation generation
```

### Example 3: MLX Model Training

```bash
cd my-training-project
/plugin install autonomous-dev
/plugin install realign-mlx

# What you get:
# ✅ Everything from autonomous-dev
# ✅ MLX pattern enforcement
# ✅ Memory management validation
# ✅ System health monitoring
# ✅ Training-specific hooks
```

## Troubleshooting

### "Plugin not found"

```bash
# Make sure marketplace is added
/plugin marketplace add akaszubski/claude-code-bootstrap

# Then install
/plugin install autonomous-dev
```

### "Hooks not running"

Check `.claude/settings.json` has hooks configured:

```json
{
  "hooks": {
    "on_file_write": ["auto_format.py", "auto_test.py"]
  }
}
```

### "Permission denied"

Make hooks executable:

```bash
chmod +x scripts/hooks/*.py
```

## Further Reading

- **[README.md](README.md)** - Plugin marketplace overview
- **[plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md)** - Generic plugin docs
- **[plugins/realign-mlx/README.md](plugins/realign-mlx/README.md)** - MLX plugin docs
- **[USAGE.md](USAGE.md)** - Detailed usage examples
- **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** - Technical deep-dive

---

**Last Updated**: 2025-10-19
**Plugin Versions**: autonomous-dev v1.0.0, realign-mlx v3.0.0
