# Documentation Index

**Last Updated**: 2025-10-20
**Version**: v2.0.0

Complete documentation for the autonomous-dev autonomous development plugin.

---

## Quick Navigation

### Getting Started
- [Quick Start](../QUICKSTART.md) - Get running in 2 minutes
- [README](../README.md) - Project overview
- [Plugin Documentation](../plugins/autonomous-dev/README.md) - Complete plugin guide

### User Guides
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Testing Guide](TESTING_GUIDE.md) - Testing practices and patterns
- [Updates](UPDATES.md) - v2.0.0 release notes
- [Migration Guide](MIGRATION.md) - Adopting plugin in existing projects
- [Customization Guide](CUSTOMIZATION.md) - Customize agents, hooks, and workflows

### Team Collaboration (NEW - Sprint 6)
- [Team Onboarding](TEAM-ONBOARDING.md) - Onboard new team members (30-45 min)
- [GitHub Workflow](GITHUB-WORKFLOW.md) - Complete GitHub-first workflow guide
- [PR Automation](PR-AUTOMATION.md) - Auto-create PRs, link issues, request reviews
- [Code Review Workflow](CODE-REVIEW-WORKFLOW.md) - Agent + human review process
- [GitHub Auth Setup](GITHUB_AUTH_SETUP.md) - Configure GitHub integration
- [GitHub Issues Integration](GITHUB-ISSUES-INTEGRATION.md) - Issue tracking automation
- [Commit Workflow](COMMIT-WORKFLOW-COMPLETE.md) - Progressive commit levels (0-4)

### Reference
- [Architecture](architecture/) - System architecture documentation
- [Implementation Status](IMPLEMENTATION-STATUS.md) - What's implemented vs documented
- [References](REFERENCES.md) - External resources

### Contributing
- [Contributing Guide](CONTRIBUTING.md) - How to contribute
- [Code of Conduct](CODE_OF_CONDUCT.md) - Community standards
- [Security Policy](SECURITY.md) - Security reporting

### Development
- [Development Guide](DEVELOPMENT.md) - Keeping repo ↔ local Claude in sync
- [Session Logs](sessions/) - Agent session history

---

## Documentation Structure

```
autonomous-dev/
├── README.md                    # Project overview
├── QUICKSTART.md                # 2-minute quick start
├── CHANGELOG.md                 # Version history
├── CLAUDE.md                    # AI project instructions
├── LICENSE                      # MIT license
│
├── docs/                        # User documentation
│   ├── README.md               # This file (documentation index)
│   ├── TEAM-ONBOARDING.md      # Team member onboarding (NEW)
│   ├── GITHUB-WORKFLOW.md      # GitHub-first workflow (NEW)
│   ├── PR-AUTOMATION.md        # PR automation guide (NEW)
│   ├── CODE-REVIEW-WORKFLOW.md # Code review process (NEW)
│   ├── GITHUB_AUTH_SETUP.md    # GitHub authentication
│   ├── GITHUB-ISSUES-INTEGRATION.md # Issue tracking
│   ├── COMMIT-WORKFLOW-COMPLETE.md # Progressive commits
│   ├── MIGRATION.md            # Migration guide (NEW)
│   ├── CUSTOMIZATION.md        # Customization guide (NEW)
│   ├── CONTRIBUTING.md         # Contribution guide
│   ├── CODE_OF_CONDUCT.md      # Community standards
│   ├── SECURITY.md             # Security policy
│   ├── TROUBLESHOOTING.md      # Common issues
│   ├── DEVELOPMENT.md          # Development setup (simplified)
│   ├── TESTING_GUIDE.md        # Testing practices
│   ├── IMPLEMENTATION-STATUS.md # Feature tracking
│   ├── UPDATES.md              # v2.0.0 release notes
│   ├── REFERENCES.md           # External resources
│   ├── architecture/           # Architecture docs
│   └── sessions/               # Agent session logs
│
├── examples/                    # Example workflows
│   ├── README.md
│   ├── sample-workflow.md
│   ├── sample-installation-output.txt
│   └── sample-settings.json
│
└── plugins/autonomous-dev/      # Plugin source
    ├── README.md               # Complete plugin documentation
    ├── QUICKSTART.md           # Plugin quick start
    ├── ARCHITECTURE.md         # Technical architecture
    ├── INSTALL_TEMPLATE.md     # Post-install guide
    ├── agents/                 # 8 specialized agents
    ├── skills/                 # 6 core skills
    ├── commands/               # Slash commands
    ├── hooks/                  # Automation hooks
    ├── tests/                  # Test suite
    └── docs/                   # Additional plugin docs
```

---

## By Topic

### Installation & Setup
1. [Quick Start](../QUICKSTART.md) - Fastest way to get started
2. [README](../README.md) - Full installation instructions
3. [Plugin Documentation](../plugins/autonomous-dev/README.md) - Post-install guide
4. [Development Guide](DEVELOPMENT.md) - Development environment setup

### Using the Plugin
1. [Plugin README](../plugins/autonomous-dev/README.md) - Complete usage guide
2. [Testing Guide](TESTING_GUIDE.md) - Running tests
3. [Examples](../examples/) - Sample workflows

### Commands Reference
1. `/auto-implement` - Autonomous feature implementation
2. `/align-project` - Validate alignment with PROJECT.md
3. `/sync-docs` - Sync documentation with code changes
4. `/commit` - Smart commit with conventional message
5. `/full-check` - Complete quality check

### Understanding the System
1. [Architecture Overview](../plugins/autonomous-dev/ARCHITECTURE.md) - System design
2. [Architecture Docs](architecture/) - Detailed architecture decisions
3. [Implementation Status](IMPLEMENTATION-STATUS.md) - What's working vs documented
4. [Updates](UPDATES.md) - v2.0.0 release notes

### Troubleshooting & Support
1. [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues
2. [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues) - Report bugs
3. [GitHub Discussions](https://github.com/akaszubski/autonomous-dev/discussions) - Ask questions
4. [Security Policy](SECURITY.md) - Report security issues

### Contributing
1. [Contributing Guide](CONTRIBUTING.md) - How to contribute
2. [Code of Conduct](CODE_OF_CONDUCT.md) - Community standards
3. [Development Guide](DEVELOPMENT.md) - Developer setup

---

## By Role

### New Users
Start here:
1. [Quick Start](../QUICKSTART.md)
2. [README](../README.md)
3. [Troubleshooting](TROUBLESHOOTING.md)

### Active Users
Reference:
1. [Plugin README](../plugins/autonomous-dev/README.md)
2. [Testing Guide](TESTING_GUIDE.md)
3. [Development Guide](DEVELOPMENT.md) - For plugin developers

### Contributors
Read:
1. [Contributing Guide](CONTRIBUTING.md)
2. [Code of Conduct](CODE_OF_CONDUCT.md)
3. [Development Guide](DEVELOPMENT.md)
4. [Architecture](../plugins/autonomous-dev/ARCHITECTURE.md)

### Plugin Developers
Deep dive:
1. [Architecture](../plugins/autonomous-dev/ARCHITECTURE.md)
2. [Implementation Status](IMPLEMENTATION-STATUS.md)
3. [Development Guide](DEVELOPMENT.md)
4. [References](REFERENCES.md)

---

## Core Concepts

### PROJECT.md-First Architecture (v2.0.0)
- All work validates against `.claude/PROJECT.md`
- Defines GOALS, SCOPE, CONSTRAINTS
- orchestrator agent enforces alignment
- Prevents scope creep at team level

### 8-Agent Pipeline
1. **orchestrator** - Validates PROJECT.md alignment (PRIMARY MISSION)
2. **researcher** - Web research for best practices
3. **planner** - Architecture & implementation planning
4. **test-master** - TDD specialist (writes tests first)
5. **implementer** - Code implementation
6. **reviewer** - Quality gate checks
7. **security-auditor** - Security scanning
8. **doc-master** - Documentation sync

### Context Management
- Use `/clear` after each feature
- Keeps context under 8K tokens
- Enables 100+ features per session
- Session logs in `docs/sessions/`

### Quality Automation
- **Auto-format**: black, isort, prettier
- **Auto-test**: pytest, jest
- **Auto-coverage**: 80%+ minimum
- **Auto-security**: Secrets detection
- **Auto-docs**: README, CHANGELOG sync

---

## Version History

### v2.0.0 (2025-10-20) - PROJECT.md-First Architecture
- Added orchestrator agent (master coordinator)
- PROJECT.md validation before all work
- Model optimization (opus/sonnet/haiku)
- Team collaboration focus
- 8-agent pipeline

### v1.0.0 (2025-10-19) - Initial Release
- 7 specialized agents
- 6 core skills
- Automation hooks
- Plugin marketplace distribution

See [CHANGELOG](../CHANGELOG.md) for complete version history.

---

## External Resources

See [REFERENCES.md](REFERENCES.md) for:
- Anthropic Claude Code documentation
- Community repositories
- Best practices guides
- Reference implementations

---

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Discussions**: [GitHub Discussions](https://github.com/akaszubski/autonomous-dev/discussions)
- **Security**: See [SECURITY.md](SECURITY.md)

---

**Need help? Start with [Troubleshooting](TROUBLESHOOTING.md) or open a [GitHub Discussion](https://github.com/akaszubski/autonomous-dev/discussions).**
