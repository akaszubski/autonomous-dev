# Changelog

All notable changes to the autonomous-dev plugin documented here.

Format: [Keep a Changelog](https://keepachangelog.com/)
Versioning: [Semantic Versioning](https://semver.org/)

---

## [Unreleased]

## [2.5.0] - 2025-10-25

### Added
- **Autonomous Workflow** - Complete end-to-end automation pipeline
  - `execute_autonomous_workflow()` in WorkflowCoordinator - orchestrates validate → code → commit → push → PR
  - `_auto_commit()` - Auto-commit with GenAI-generated commit messages
  - `_auto_push()` - Auto-create feature branches and push to remote
  - `_auto_create_pr()` - Auto-create GitHub PRs with GenAI descriptions
  - `_auto_track_progress()` - Auto-update PROJECT.md goal completion
- **3 New Automation Agents**:
  - `commit-message-generator` - GenAI commit messages following conventional commits format
  - `pr-description-generator` - Comprehensive PR descriptions (architecture, testing, security, docs)
  - `project-progress-tracker` - PROJECT.md goal tracking and next priority suggestions
- **alignment-validator Agent** - Semantic PROJECT.md validation using Claude Code native Task tool
- **/status Command** - View PROJECT.md goal progress, active workflows, and next priorities
- **Agent Configurations** - Added 4 new agents to AgentInvoker.AGENT_CONFIGS

### Changed
- **Command Philosophy Shift**: Manual toolkit → Autonomous team
  - User runs 1 command (`/auto-implement`), team handles everything
  - Core philosophy: User states WHAT, team handles HOW
  - Zero manual git operations required
- **PROJECT.md GOALS Section** - Updated to clearly articulate autonomous team vision
  - Primary mission: "Build an Autonomous Development Team"
  - Success example showing 1-command workflow
  - Updated success metrics (autonomous execution, command minimalism)
- **WorkflowCoordinator** - +530 lines of autonomous git operations
  - Subprocess integration for git commands
  - GitHub CLI integration for PR creation
  - GenAI agent invocation for commit/PR content
- **Version**: v2.4.0 → v2.5.0

### Removed
- **16 Manual Git Commands** - Archived to `commands/archive/manual-commands/`:
  - Git operations: commit.md, commit-check.md, commit-push.md, commit-release.md, pr-create.md, issue.md
  - Quality operations: format.md, security-scan.md, sync-docs.md, full-check.md
  - Test operations: test-integration.md, test-unit.md, test-uat.md, test-uat-genai.md, test-architecture.md
  - Other: uninstall.md
- **Python SDK Approach** - Archived to `lib/archive/python-sdk-approach/`:
  - alignment_validator.py (114 lines) - Used Anthropic Python SDK
  - security_validator.py (155 lines) - Used Anthropic Python SDK
  - Reason: Now using Claude Code native agents via Task tool (no separate API key needed)
- **Commands**: 22 → 5 (-77% reduction)

### Impact
- **User Effort**: 13 commands per feature → 1 command (-92%)
- **Time per Feature**: 30 minutes → 5-10 minutes (-67-83%)
- **Git Operations**: Manual → 100% automated
- **PROJECT.md Tracking**: Manual → 100% automated

### Documentation
- Added `docs/AUTONOMOUS-TEAM-VISION.md` - Complete vision and philosophy
- Added `docs/AUTONOMOUS-TRANSFORMATION-SUMMARY.md` - Comprehensive transformation summary
- Added `docs/GENAI-VALIDATION-CLAUDE-CODE-NATIVE.md` - Native GenAI implementation guide
- Added `docs/VALIDATION-AND-ANTI-DRIFT.md` - Anti-drift mechanisms
- Added `docs/GITHUB-SYNC-AND-COMMAND-CLEANUP.md` - Command cleanup analysis
- Added 10+ session summary and analysis documents

### Technical Details
- Uses subprocess for git operations (add, commit, push, checkout)
- Uses `gh` CLI for GitHub PR creation
- GenAI agents use Claude Code Task tool (native subscription)
- All automation agents configured in AgentInvoker
- Graceful error handling for git/GitHub operations
- Progress tracking throughout autonomous pipeline

## [2.2.0] - 2025-10-25

### Added
- **4 New Skills** (50% increase: 6 → 9 skills):
  - `git-workflow`: Commit conventions, branching strategies, PR workflows, CI/CD integration
  - `code-review`: Review standards, constructive feedback, quality checks
  - `architecture-patterns`: Design patterns (GoF), ADRs, system design, SOLID principles
  - `project-management`: PROJECT.md structure, sprint planning, goals (SMART/OKR), roadmaps
- **Auto-Activate for All Skills**: All 9 skills now include `auto_activate: true` for consistent behavior
- Progressive disclosure optimization: Skills use Anthropic's recommended 3-level loading system

### Changed
- **Skills refactored** (6 → 9): Broke up broad `engineering-standards` skill into focused domain skills
- **Skill activation**: Improved keyword coverage and descriptions for better automatic activation
- **Documentation**: Updated README, marketplace.json, and plugin.json to reflect 9 skills
- **Version**: v2.1.0 → v2.2.0

### Removed
- `engineering-standards` skill - Content redistributed to focused skills:
  - Git workflow → `git-workflow` skill
  - Code review → `code-review` skill
  - Architecture → `architecture-patterns` skill
  - Python standards already covered by `python-standards` skill

### Technical Details
- Followed Anthropic's skill-creator best practices for skill design
- All skills follow progressive disclosure pattern (metadata → SKILL.md → resources)
- Skills optimized for context efficiency (<5K words per skill body)
- Comprehensive coverage: Python, testing, security, docs, research, git, reviews, architecture, project management

## [2.1.0] - 2025-10-24

### Added
- **PROJECT.md-First Philosophy Section** in README - Prominent explanation of PROJECT.md-first architecture
- **New Project vs Existing Project Workflows** - Clear guides for greenfield vs retrofit scenarios
- **FAQ Section** clarifying `.claude/` directory usage (not needed for most users)
- **Consistency Validation Checklist** (`docs/CONSISTENCY_CHECKLIST.md`) with 30+ pre-release checks
- Interactive menu pattern for all mode-based commands

### Changed
- **BREAKING**: PROJECT.md location changed from `.claude/PROJECT.md` → `PROJECT.md` (project root)
  - Migration: `mv .claude/PROJECT.md ./PROJECT.md`
  - Reason: PROJECT.md is project-level metadata, not tool-specific config
- **Commands simplified**: 33 → 21 commands via interactive menus
  - Alignment: 5 commands → 1 (`/align-project` with 4-option menu)
  - Documentation: 2 commands → 1 (`/sync-docs` with 6-option menu)
  - Issues: 3 commands → 1 (`/issue` with 5-option menu)
- **README.md completely revised**:
  - Fixed installation troubleshooting (removed incorrect `~/.claude/plugins` path)
  - Added PROJECT.md-first philosophy section
  - Added new vs existing project workflows
  - Clarified `.claude/` directory is optional
- **Plugin README** updated to match root README philosophy
- **Version**: v2.0.0 → v2.1.0

### Removed
- Duplicate `-v2` agent files (8 files) - cleaned up from development
- Redundant command variants:
  - `align-project-safe`, `align-project-fix`, `align-project-dry-run`, `align-project-sync`
  - `sync-docs-auto`
  - `issue-auto`, `issue-from-genai`, `issue-preview`
- Incorrect troubleshooting instructions referencing `~/.claude/plugins`

### Fixed
- Installation instructions now use correct GitHub marketplace method
- All documentation now references PROJECT.md at root (not `.claude/PROJECT.md`)
- Command count updated throughout documentation (21 commands)
- Agent/skill counts verified (8 agents, 6 skills)

### Documentation
- Added comprehensive consistency checklist for maintainers
- Updated all command counts (33 → 25 → 24 → 21)
- Clarified .claude/ structure and when it's needed
- Added migration guide for PROJECT.md location change

---

### Added (Unreleased items moved below)
- **marketplace.json** - Plugin marketplace distribution file for `/plugin marketplace add`
- **/sync-docs command** - Synchronize documentation with code changes (invokes doc-master agent)
  - `--auto` flag: Auto-detect changes via git diff
  - `--organize` flag: Organize .md files into docs/
  - `--api` flag: Update API documentation only
  - `--changelog` flag: Update CHANGELOG only
  - Links to doc-master agent for automated doc sync

### Changed
- **Simplified installation workflow** - No more refresh scripts, just marketplace install/uninstall
- **DEVELOPMENT.md** - Rewritten to focus on simple symlink workflow for developers
- **Documentation cleanup** - Removed complex sync guides (SYNC-GUIDE.md, GLOBAL-COMMANDS-GUIDE.md, REFRESH-SETTINGS.md)
- Updated PROJECT.md with team collaboration intent (co-defined outcomes, GitHub-first workflow)
- Removed legacy `/auto-doc-update` command from global commands
- Removed duplicate `/align-project-safe` from global commands (now `--safe` flag)

### Removed
- **Obsolete development scripts** - sync-plugin.sh, test-installation.sh (no longer needed with symlink workflow)
- **4 sync scripts** - refresh-claude-settings.sh, check-sync-status.sh, find-changes.sh
- **3 sync documentation files** - SYNC-GUIDE.md (550+ lines), GLOBAL-COMMANDS-GUIDE.md, REFRESH-SETTINGS.md
- **DEVELOPMENT_WORKFLOW.md** - Duplicate of DEVELOPMENT.md
- **Complex sync workflow** - Replaced with simple marketplace install/uninstall

### Fixed
- **Marketplace distribution** - Added marketplace.json for proper plugin discovery
- **Documentation references** - Updated all docs to use marketplace workflow instead of refresh scripts
- **Issue command documentation** - Removed unimplemented `/issue from-performance` command references
  - Cleaned up all issue command documentation in `.claude/commands/` and `plugins/autonomous-dev/commands/`
  - Updated command descriptions to reflect actual 5 issue commands (auto, create, from-genai, from-test, preview)
  - Verified documentation accuracy across 33 total discoverable commands

---

## [2.0.0] - 2025-10-20

### Added
- **PROJECT.md-first architecture** - orchestrator validates alignment before every feature
- **orchestrator agent** - Master coordinator with PRIMARY MISSION to validate PROJECT.md
- **Model optimization** - opus (planner), sonnet (balanced), haiku (fast tasks) for 40% cost reduction
- **/align-project command** - Standard alignment validation and scoring
- **/align-project --safe flag** - 3-phase safe alignment (Analyze → Generate → Interactive) with 7 advanced features:
  - Smart Diff View with risk scoring
  - Dry Run with Stash for safe testing
  - Pattern Learning from user decisions
  - Conflict Resolution for PROJECT.md vs reality mismatches
  - Progressive Enhancement (quick wins → deep work)
  - Undo Stack with visual history
  - Simulation Mode for risk-free testing
- **GitHub integration (optional)** - Sprint tracking via .env authentication
- **PROJECT.md template** - Generic, domain-agnostic template for any project type
- **GITHUB_AUTH_SETUP.md** - Complete setup guide with troubleshooting
- **Testing infrastructure** - Automated test script (30 tests) + comprehensive manual testing guide
- **REFERENCES.md** - 30+ reference URLs (Anthropic docs, community resources, reference repos)
- **commands/** component to plugin.json
- **templates/** component to plugin.json
- Model assignments to all agents (frontmatter: `model: opus|sonnet|haiku`)

### Changed
- **8-agent pipeline** (was 7) - Added orchestrator as master coordinator
- **planner agent** - Now uses opus model (was sonnet) for complex planning
- **researcher agent** - Now uses sonnet model (was haiku) for better research quality
- **reviewer agent** - Now uses sonnet model (was haiku) for better quality gates
- **Plugin description** - Updated to highlight PROJECT.md-first architecture
- **README.md** - Comprehensive update with PROJECT.md-first workflow, priority hierarchy, all 7 advanced features
- **plugins/autonomous-dev/README.md** - Updated to v2.0.0 features, 8-agent table, workflows
- **.mcp/README.md** - Updated integration section for PROJECT.md-first workflow
- **UserPromptSubmit hook** - Shows v2.0.0 context with orchestrator and PRIMARY MISSION
- **PROJECT.md** - Updated with team collaboration focus (human + AI co-defined outcomes)

### Fixed
- Documentation structure - Created CHANGELOG.md per documentation-guide skill
- Context management - Clear separation between source (plugins/) and installed (.claude/)

---

## [1.0.0] - 2025-10-19

### Added
- Initial release of autonomous-dev plugin
- 7 specialized agents (planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master)
- 6 core skills (python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards)
- Auto-formatting hooks (black, isort, prettier)
- Auto-testing hooks (pytest, jest)
- Auto-coverage enforcement (80% minimum)
- Security scanning hooks
- Plugin marketplace distribution
- SESSION.md context management
- MCP server configuration

---

## Version History

**v2.0.0** - PROJECT.md-first architecture with orchestrator and team collaboration focus
**v1.0.0** - Initial autonomous development plugin release

---

**Last Updated**: 2025-10-20
