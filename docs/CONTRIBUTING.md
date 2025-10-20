# Contributing to Claude Code Bootstrap

**Last Updated**: 2025-10-20

Thank you for your interest in contributing! This plugin is designed to be extensible and community-driven.

---

## How to Contribute

### 1. Contributing New Agents

Agents are autonomous specialists that perform specific tasks.

**Location**: `plugins/autonomous-dev/agents/`

**Template**:
```markdown
---
name: my-agent
description: Short description of what this agent does
tools:
  - Read
  - Write
  - Bash
---

# Agent: My Agent

## Purpose
[Clear description of agent's role]

## When to Use
[Specific scenarios where this agent should be invoked]

## Tools Available
- Read: Read files
- Write: Create new files
- Bash: Execute commands

## Workflow
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Examples
[Sample invocations and expected outputs]
```

**Testing**:
```bash
# Test your agent
./scripts/refresh-claude-settings.sh
# Then use the agent in Claude
```

---

### 2. Contributing New Skills

Skills are reusable knowledge that agents can leverage.

**Location**: `plugins/autonomous-dev/skills/`

**Structure**:
```
skills/
└── my-skill/
    └── SKILL.md
```

**Template**:
```markdown
# Skill: My Skill

## Purpose
[What this skill teaches]

## When to Use
[Scenarios where this skill applies]

## Best Practices
1. [Practice 1]
2. [Practice 2]

## Examples
[Code examples demonstrating the skill]

## Anti-Patterns
[What NOT to do]
```

---

### 3. Contributing New Commands

Commands are user-invokable workflows (e.g., `/test`, `/commit`).

**Location**: `plugins/autonomous-dev/commands/`

**Template**:
```markdown
# Command: /my-command

## Description
[What this command does]

## Usage
```bash
/my-command [options]
```

## Options
- `--option1`: Description
- `--option2`: Description

## Workflow
1. [Step 1]
2. [Step 2]

## Examples
[Usage examples]
```

---

### 4. Contributing New Hooks

Hooks are automatic actions triggered by events.

**Location**: `plugins/autonomous-dev/hooks/`

**Template**:
```python
#!/usr/bin/env python3
"""
Hook Name - Brief description

Triggers:
- When X happens
- During Y

What it does:
1. Action 1
2. Action 2
"""

import sys
from pathlib import Path

def main():
    """Main hook logic."""
    # Your code here
    return 0  # 0 = success, non-zero = failure

if __name__ == "__main__":
    sys.exit(main())
```

**Testing**:
```bash
# Test hook locally
python plugins/autonomous-dev/hooks/my_hook.py

# Refresh settings
./scripts/refresh-claude-settings.sh
```

---

## Development Workflow

### Setup

1. **Fork the repository**
   ```bash
   gh repo fork akaszubski/claude-code-bootstrap
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/claude-code-bootstrap.git
   cd claude-code-bootstrap
   ```

3. **Create development symlink**
   ```bash
   # See DEVELOPMENT.md for complete setup
   ln -s $(pwd)/plugins/autonomous-dev ~/.claude/plugins/autonomous-dev
   ```

4. **Install in development mode**
   ```bash
   /plugin install autonomous-dev
   ```

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-agent
   ```

2. **Make your changes**
   ```bash
   # Edit files in plugins/autonomous-dev/
   vim plugins/autonomous-dev/agents/my-agent.md
   ```

3. **Refresh Claude settings**
   ```bash
   ./scripts/refresh-claude-settings.sh
   ```

4. **Test your changes**
   - Use your new agent/command/skill in Claude
   - Verify it works as expected

5. **Update documentation**
   - Update README.md if adding new components
   - Update CHANGELOG.md with your changes

6. **Run tests** (if applicable)
   ```bash
   /test all
   ```

7. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat(agents): add my-new-agent for X"
   ```

8. **Push to your fork**
   ```bash
   git push origin feature/my-new-agent
   ```

9. **Create a Pull Request**
   ```bash
   gh pr create --title "Add my-new-agent" --body "Description of changes"
   ```

---

## Code Quality Standards

### For Python Code (Hooks, Scripts)

- **Format**: black, isort
- **Type hints**: Required for public APIs
- **Docstrings**: Google style
- **Testing**: Add tests for new functionality

### For Markdown (Agents, Skills, Commands)

- **Formatting**: Clear headers, examples, code blocks
- **Length**: Keep concise (100-300 lines)
- **Examples**: Include practical examples
- **Testing**: Manually test in Claude

### Git Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature (agent, skill, command, hook)
- `fix`: Bug fix
- `docs`: Documentation updates
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

**Examples**:
```
feat(agents): add database-optimizer agent
fix(hooks): auto_format now handles .ts files
docs(README): add troubleshooting section
```

---

## Pull Request Process

1. **Ensure your PR**:
   - Has a clear title and description
   - References any related issues
   - Includes tests (if applicable)
   - Updates documentation
   - Follows code quality standards

2. **PR will be reviewed for**:
   - Code quality
   - Documentation completeness
   - Test coverage
   - Alignment with project goals

3. **After approval**:
   - PR will be merged to main branch
   - Changes will be included in next release

---

## Community Guidelines

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help newcomers get started
- Share knowledge and learn together

---

## Questions?

- **General questions**: Open a [Discussion](https://github.com/akaszubski/claude-code-bootstrap/discussions)
- **Bug reports**: Open an [Issue](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Feature requests**: Open an [Issue](https://github.com/akaszubski/claude-code-bootstrap/issues) with `enhancement` label

---

## Recognition

Contributors will be:
- Added to README.md contributors section
- Mentioned in CHANGELOG.md
- Recognized in release notes

---

Thank you for contributing to making autonomous development better for everyone! 🚀
