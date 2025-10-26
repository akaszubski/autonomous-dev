# Customization Guide

**Last Updated**: 2025-10-20

How to customize agents, skills, commands, and hooks for your team's workflow.

---

## Quick Links

- **Customize Agents**: Modify `.claude/agents/*.md`
- **Customize Skills**: Edit `.claude/skills/*/SKILL.md`
- **Customize Commands**: Edit `.claude/commands/*.md`
- **Customize Hooks**: Edit `.claude/hooks/*.py`
- **Customize Settings**: Edit `.claude/settings.local.json`

---

## Customizing Agents

### Add Tools to Agent

Edit agent frontmatter in `.claude/agents/agent-name.md`:

```markdown
---
name: my-agent
tools:
  - Read
  - Write
  - Bash
  - WebSearch  # Add new tool
---
```

### Change Agent Model

```markdown
---
model: opus  # or sonnet, haiku
---
```

### Customize Agent Behavior

Edit agent instructions in body of `.claude/agents/agent-name.md`

---

## Customizing Skills

### Edit Skill Content

```bash
vim .claude/skills/python-standards/SKILL.md
```

### Add New Skill

```bash
mkdir -p .claude/skills/my-skill
cat > .claude/skills/my-skill/SKILL.md <<'EOF'
# Skill: My Custom Skill

## Purpose
[Description]

## Best Practices
[Guidelines]
EOF
```

---

## Customizing Commands

### Modify Existing Command

```bash
vim .claude/commands/test.md
```

### Add New Command

```bash
cat > .claude/commands/my-command.md <<'EOF'
# Command: /my-command

Executes custom workflow.

## Usage
/my-command
EOF
```

---

## Customizing Hooks

### Modify Hook Behavior

```bash
vim .claude/hooks/auto_format.py
```

### Add Custom Hook

See docs/CONTRIBUTING.md for hook development guide.

---

## Customizing Quality Thresholds

### Test Coverage

Edit in hooks or CI config:
```python
# .claude/hooks/auto_enforce_coverage.py
COVERAGE_THRESHOLD = 80  # Change to your preference
```

### Security Scan Severity

```python
# .claude/hooks/security_scan.py
FAIL_ON = ['HIGH', 'CRITICAL']  # Customize severity levels
```

---

## Team-Specific Customization

### For Your Team

1. Fork this repository
2. Customize agents, skills, hooks
3. Publish as team-specific plugin
4. Team installs: `/plugin install your-org/custom-plugin`

---

**For detailed examples**, see:
- Contributing Guide: `docs/CONTRIBUTING.md`
- Plugin Architecture: `plugins/autonomous-dev/ARCHITECTURE.md`
