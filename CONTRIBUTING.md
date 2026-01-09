# Contributing to Autonomous Dev Plugin

**Thank you for your interest in contributing!**

---

## Quick Start

1. **Clone the repo**:
   ```bash
   git clone https://github.com/akaszubski/autonomous-dev.git
   cd autonomous-dev
   ```

2. **Set up development environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

3. **Run tests**:
   ```bash
   pytest tests/
   ```

4. **Make changes, commit, push**:
   ```bash
   git add -A
   git commit -m "feat: your change"
   git push
   ```

---

## Repository Structure

This repo has **two audiences**:

| Audience | Location | Purpose |
|----------|----------|---------|
| **Contributors** | Root level | Building/developing the plugin |
| **Users** | `plugins/autonomous-dev/` | Using the plugin |

```
autonomous-dev/
├── README.md                    # User-facing documentation
├── CLAUDE.md                    # Instructions for Claude Code
├── PROJECT.md                   # Project goals, scope, constraints
├── CONTRIBUTING.md              # This file
├── CHANGELOG.md                 # Version history
│
├── plugins/autonomous-dev/      # THE PLUGIN (distributed to users)
│   ├── commands/                # 10 slash commands (9 core + 1 utility)
│   ├── agents/                  # 20 AI agents
│   ├── skills/                  # 28 skill packages
│   ├── hooks/                   # Automation hooks
│   ├── lib/                     # 29 Python libraries
│   ├── scripts/                 # User scripts (setup.py, etc.)
│   ├── templates/               # Templates for settings, projects
│   ├── config/                  # Configuration files
│   └── docs/                    # User documentation
│
├── docs/                        # Developer documentation
│   ├── ARCHITECTURE-OVERVIEW.md # System architecture
│   ├── DEVELOPMENT.md           # Development guide
│   ├── AGENTS.md                # Agent reference
│   └── ...                      # Other dev docs
│
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── ...
│
└── scripts/                     # Development scripts
```

---

## What Goes Where

### Plugin Directory (`plugins/autonomous-dev/`)

**For users** - Gets installed when someone uses the plugin.

- `commands/` - Slash command definitions (`.md` files)
- `agents/` - AI agent prompts (`.md` files)
- `skills/` - Knowledge packages for agents
- `hooks/` - Python automation scripts
- `lib/` - Reusable Python libraries
- `docs/` - User-facing documentation (TROUBLESHOOTING, COMMANDS, etc.)

### Root Directory

**For contributors** - Development resources, not distributed.

- `docs/` - Developer documentation (ARCHITECTURE, DEVELOPMENT, etc.)
- `tests/` - Test suite
- `scripts/` - Development scripts

---

## Adding New Features

### Adding a Command

1. Create the command file:
   ```bash
   vim plugins/autonomous-dev/commands/my-command.md
   ```

2. Follow the command template:
   ```markdown
   ---
   description: Short description for autocomplete
   ---

   # /my-command

   [Command instructions here]
   ```

3. Test and commit:
   ```bash
   pytest tests/
   git add plugins/autonomous-dev/commands/my-command.md
   git commit -m "feat: add /my-command"
   ```

### Adding an Agent

1. Create the agent file:
   ```bash
   vim plugins/autonomous-dev/agents/my-agent.md
   ```

2. Follow agent conventions (see existing agents for examples)

3. Register in CLAUDE.md if it's a core workflow agent

### Adding a Skill

1. Create skill directory:
   ```bash
   mkdir plugins/autonomous-dev/skills/my-skill
   vim plugins/autonomous-dev/skills/my-skill/SKILL.md
   ```

2. Follow skill template (see existing skills)

### Adding a Library

1. Create in `plugins/autonomous-dev/lib/`:
   ```bash
   vim plugins/autonomous-dev/lib/my_library.py
   ```

2. Follow the two-tier design pattern:
   - Core logic as functions/classes
   - CLI wrapper with `if __name__ == "__main__"`

3. Add tests in `tests/`

4. Document in `docs/LIBRARIES.md`

---

## Code Standards

### Python

- **Style**: PEP 8, enforced by black/ruff
- **Type hints**: Required for public APIs
- **Docstrings**: Google style
- **Security**: Use `lib/security_utils.py` for path/input validation

### Markdown

- **Commands**: Must have YAML frontmatter with `description`
- **Agents**: Clear purpose, tool restrictions, output format
- **Skills**: Progressive disclosure (summary → details)

### Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix a bug
docs: update documentation
chore: maintenance tasks
refactor: code refactoring
test: add or update tests
```

---

## Testing

### Run All Tests

```bash
pytest tests/
```

### Run Specific Tests

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_security_utils.py
```

### Pre-commit Validation

The repo has pre-commit hooks that run automatically:
- Structure validation
- Command implementation checks
- Documentation link validation

---

## Pull Request Process

1. **Create a branch**:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make changes and test**:
   ```bash
   pytest tests/
   ```

3. **Commit with descriptive message**:
   ```bash
   git commit -m "feat: add feature X for issue #123"
   ```

4. **Push and create PR**:
   ```bash
   git push -u origin feat/my-feature
   gh pr create --title "feat: add feature X" --body "Description..."
   ```

5. **Address review feedback**

6. **Merge when approved**

---

## Development Tips

### Restart Claude Code After Changes

Claude Code caches commands at startup. After modifying commands:

1. Fully quit Claude Code (`Cmd+Q` / `Ctrl+Q`)
2. Wait 5 seconds
3. Restart Claude Code

### Sync Plugin to .claude/

For local testing, sync plugin files to your project's `.claude/`:

```bash
/sync --dev
```

### Check Health

Verify plugin integrity:

```bash
/health-check
```

---

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Documentation**: See `docs/` folder
- **Architecture**: `docs/ARCHITECTURE-OVERVIEW.md`
- **Development Guide**: `docs/DEVELOPMENT.md`

---

## License

MIT License - See [LICENSE](LICENSE) for details.
