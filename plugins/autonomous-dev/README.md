# Autonomous Dev - Generic Claude Code Plugin

**Production-ready autonomous development setup for ANY project**

Works with: Python, JavaScript, TypeScript, React, Node.js, and more!

## Quick Install

```bash
# Add the marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install the plugin
/plugin install autonomous-dev
```

Done! Your Claude Code environment now has autonomous agents, skills, and hooks.

## What You Get

### 🤖 7 Specialized Agents

| Agent | Purpose |
|-------|---------|
| **planner** | Architecture & design planning for complex features |
| **researcher** | Web research & best practices discovery |
| **test-master** | TDD workflow, progression tracking, regression prevention |
| **implementer** | Clean code implementation following patterns |
| **reviewer** | Code quality gate before merge |
| **security-auditor** | Security scanning & OWASP compliance |
| **doc-master** | Documentation sync & CHANGELOG automation |

### 📚 6 Core Skills

| Skill | Domain |
|-------|--------|
| **python-standards** | PEP 8, type hints, docstrings (Google style) |
| **testing-guide** | Complete testing methodology (TDD, progression, regression) |
| **security-patterns** | API key management, input validation, secure coding |
| **documentation-guide** | CHANGELOG updates, API docs, filesystem alignment |
| **research-patterns** | Research methodology, pattern discovery |
| **engineering-standards** | Code review, git workflow, best practices |

### ⚡ 8 Automated Hooks

| Hook | Event | Action |
|------|-------|--------|
| **auto_format.py** | File write | Format with black + isort (Python) |
| **auto_test.py** | File write | Run related tests |
| **auto_generate_tests.py** | File write | Generate missing tests |
| **auto_tdd_enforcer.py** | File write | Enforce TDD (test before code) |
| **auto_add_to_regression.py** | Test pass | Add to regression suite |
| **auto_enforce_coverage.py** | Commit | Ensure 80%+ test coverage |
| **auto_update_docs.py** | API change | Update documentation automatically |
| **security_scan.py** | File write | Scan for secrets, vulnerabilities |

## How It Works

### Agents Auto-Invoke

```
You: "Add user authentication"

Claude automatically:
1. planner → Creates architecture plan
2. test-master → Writes FAILING tests (TDD)
3. implementer → Makes tests PASS
4. reviewer → Quality gate check
5. doc-master → Updates docs + CHANGELOG
```

### Skills Auto-Activate

- Write Python → python-standards activates
- Write tests → testing-guide activates
- Handle secrets → security-patterns activates

### Hooks Auto-Run

- Save file → auto_format.py + auto_test.py run
- Commit → auto_enforce_coverage.py checks coverage
- All automatic, no manual steps!

## Requirements

- **Claude Code**: 2.0.0 or higher
- **Python**: 3.11+ (for hooks)
- **Git**: For automation hooks

## Configuration

After install, hooks are configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "on_file_write": ["auto_format.py", "auto_test.py"],
    "pre_commit": ["auto_enforce_coverage.py"],
    "pre_push": ["security_scan.py"]
  }
}
```

Customize as needed for your project!

## Why Use This?

**Before autonomous-dev:**
- Manual code formatting
- Forget to write tests
- Inconsistent code quality
- Documentation gets out of sync
- Security vulnerabilities slip through

**After autonomous-dev:**
- ✅ Auto-formatted code (black + isort)
- ✅ TDD enforced (test before code)
- ✅ 80%+ coverage required
- ✅ Docs auto-updated
- ✅ Security auto-scanned
- ✅ Autonomous workflow

## Extension Plugins

Want MLX/Apple Silicon support? Install the companion plugin:

```bash
/plugin install realign-mlx  # Adds MLX patterns + system monitoring
```

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Documentation**: [Full Docs](https://github.com/akaszubski/claude-code-bootstrap/docs)

## License

MIT License

## Version

**v1.0.0** (2025-10-19)

---

**🤖 Powered by Claude Code** | **Generic & Production-Ready**
