# Claude Code 2.0 Official Documentation Reference

> **Purpose**: Offline reference for official Claude Code documentation
> **Downloaded**: 2025-12-16
> **Source**: https://code.claude.com/docs/

This directory contains key Claude Code 2.0 documentation downloaded for offline reference and quick access.

---

## Documents

| Document | Description | Source |
|----------|-------------|--------|
| [best-practices.md](best-practices.md) | Agentic coding patterns, workflows, multi-Claude strategies | [Anthropic Engineering](https://www.anthropic.com/engineering/claude-code-best-practices) |
| [security.md](security.md) | Permission architecture, protections, prompt injection defense | [Security Docs](https://code.claude.com/docs/en/security) |
| [plugins.md](plugins.md) | Plugin structure, components, marketplaces, creation guide | [Plugins Docs](https://code.claude.com/docs/en/plugins) |
| [hooks.md](hooks.md) | Hook events, configuration, input/output formats, examples | [Hooks Docs](https://code.claude.com/docs/en/hooks) |
| [settings.md](settings.md) | Settings files, permissions, environment variables, tools | [Settings Docs](https://code.claude.com/docs/en/settings) |

---

## Quick Reference

### Key Concepts

**Plugins**
- Install to project `.claude/` directory only (NOT global `~/.claude/`)
- Cannot modify global settings or hooks
- Use `allowed-tools` for least privilege

**Hooks**
- Exit code 0 = success, exit code 2 = block
- JSON via stdin, JSON output for control
- Matcher patterns: `*`, `Write`, `Edit|Write`, `mcp__*`

**Settings Precedence** (highest to lowest)
1. Enterprise managed policies
2. Command line arguments
3. Local project settings (`.claude/settings.local.json`)
4. Shared project settings (`.claude/settings.json`)
5. User settings (`~/.claude/settings.json`)

**Security**
- Write access restricted to project folder and subfolders
- Cannot modify parent directories without explicit permission
- Sensitive files (`.env`, `.ssh`) should be denied

---

## Why These Docs Matter for autonomous-dev

### Plugin Limitations Explain install.sh

The [plugins.md](plugins.md) documentation confirms that the Claude Code marketplace:
- Can only install to project `.claude/` directory
- Cannot write to `~/.claude/` (global)
- Cannot modify `~/.claude/settings.json`
- Cannot run installation scripts

This is why autonomous-dev requires `install.sh` - it needs global hooks and libs that plugins cannot configure.

### Hooks Reference for Hook Development

The [hooks.md](hooks.md) documentation provides:
- All 10 hook event types
- Input/output JSON formats
- Exit code conventions
- Security best practices

Essential for developing `unified_pre_tool.py`, `unified_prompt_validator.py`, etc.

### Settings Reference for Configuration

The [settings.md](settings.md) documentation covers:
- All available settings options
- Permission patterns for allow/deny/ask
- Environment variables (70+)
- Tool reference

---

## Keeping Docs Updated

These docs should be refreshed periodically as Claude Code evolves:

```bash
# Check for updates
# 1. Visit https://code.claude.com/docs/
# 2. Compare with local versions
# 3. Re-download if significant changes
```

**Last sync**: 2025-12-16

---

## Official Documentation Links

- **Main Docs**: https://code.claude.com/docs/
- **Plugins**: https://code.claude.com/docs/en/plugins
- **Hooks**: https://code.claude.com/docs/en/hooks
- **Settings**: https://code.claude.com/docs/en/settings
- **Security**: https://code.claude.com/docs/en/security
- **Best Practices**: https://www.anthropic.com/engineering/claude-code-best-practices
- **MCP**: https://code.claude.com/docs/en/mcp
- **Subagents**: https://code.claude.com/docs/en/sub-agents
- **Skills**: https://code.claude.com/docs/en/skills
